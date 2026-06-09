from __future__ import annotations

import fcntl
import hashlib
import os
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from apps.api_server.models.data_connector import DataConnector
from apps.api_server.schemas.repositories import (
    RepositoryDecisionPlanCreateRequest,
    RepositoryDecisionPlanResponse,
)
from apps.api_server.schemas.response import (
    DecisionOption,
    DecisionPlan,
    RepositoryAnalysis,
    RiskProfile,
    TokenReductionMetrics,
)
from apps.api_server.services import (
    repository_intelligence_runtime as repository_runtime,
)
from apps.api_server.services import (
    repository_intelligence_storage as repository_storage,
)
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)
from apps.api_server.services.repository_intelligence_shared import (
    _hash_payload,
    _stable_identifier,
    _utc_now,
)
from apps.api_server.services.runtime_internal_contracts import (
    PatchImpactReportRecord,
    parquet_bytes_from_records,
)

_RequireRepositoryConnector = Callable[[DataConnector], None]
_ResolveRepositoryModel = Callable[[str | None], str]
_ReadJson = Callable[[Path], dict[str, Any]]
_GenerateRepositoryPatchPlan = Callable[..., Awaitable[dict[str, Any]]]
_ValidatePatchAgainstSnapshot = Callable[..., None]
_PatchChangedFiles = Callable[[str], dict[str, list[tuple[int, int]]]]
_TopLevelService = Callable[[str], str]
_IsTestPath = Callable[[str], bool]


def _decision_plan_lookup_key(
    *,
    snapshot_id: str,
    workspace_evidence_bundle_ref: str,
    model_id: str,
    engine_revision: str,
) -> str:
    return _stable_identifier(
        "decision_plan_lookup",
        {
            "engine_revision": engine_revision,
            "snapshot_id": snapshot_id,
            "workspace_evidence_bundle_ref": workspace_evidence_bundle_ref,
            "model_id": model_id,
        },
    )


@contextmanager
def _decision_plan_generation_lock(lookup_dir: Path, lookup_key: str):
    """Serialize decision-plan generation for one lookup_key across workers.

    Without this, two concurrent cache misses for the same key — critically the
    nondeterministic ``verified_agentic`` tier — would each run a planner and
    race to persist divergent plans. A host-local advisory ``flock`` is enough
    for the file-based runtime store; the production multi-tenant deployment
    swaps this for a Postgres advisory / Redis lock on the same key (plan §6).
    """
    lookup_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lookup_dir / f"{lookup_key}.lock"
    # 0o600: the advisory flock anchor holds no data and is owner-only by design;
    # world-readable (0o644) is unnecessary and trips py/overly-permissive-file.
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _patch_impact_summary(
    snapshot_manifest: dict[str, Any],
    patch_diff: str,
    *,
    patch_changed_files: _PatchChangedFiles,
    top_level_service: _TopLevelService,
    is_test_path: _IsTestPath,
) -> dict[str, Any]:
    changed_files = patch_changed_files(patch_diff)
    if not changed_files:
        raise RepositoryIntelligenceError(
            code="invalid_patch_diff",
            message="Generated patch diff does not declare any changed files.",
            status_code=422,
        )
    files_by_path = {entry["file_path"]: entry for entry in snapshot_manifest["files"]}
    impacted_symbols: set[str] = set()
    impacted_services: set[str] = set()
    likely_failing_tests: set[str] = set()
    api_break_candidates = 0
    dependency_fanout = 0
    records: list[dict[str, Any]] = []

    for file_path, ranges in changed_files.items():
        file_entry = files_by_path.get(file_path)
        if file_entry is None:
            raise RepositoryIntelligenceError(
                code="patch_targets_unknown_file",
                message=(
                    f"Generated patch targets '{file_path}', which is not present in "
                    f"snapshot '{snapshot_manifest['snapshot_id']}'."
                ),
                status_code=422,
            )
        impacted_services.add(top_level_service(file_path))
        file_symbols = file_entry["symbols"]
        matched_symbols = [
            symbol
            for symbol in file_symbols
            if any(
                symbol["start_line"] <= end and symbol["end_line"] >= start
                for start, end in ranges
            )
        ]
        if not matched_symbols:
            matched_symbols = list(file_symbols)
        for symbol in matched_symbols:
            impacted_symbols.add(symbol["symbol_name"])
            if Path(file_path).parts[:1] in [("packages",), ("src",)]:
                api_break_candidates += 1
            records.append(
                {
                    "impacted_file": file_path,
                    "impacted_symbol": symbol["symbol_name"],
                    "risk_type": "symbol_change",
                    "severity": (
                        "high"
                        if symbol["symbol_kind"] in {"class", "function", "async_function"}
                        else "medium"
                    ),
                    "likely_failing_test": None,
                    "dependency_target": None,
                }
            )
        for candidate in snapshot_manifest["files"]:
            dependencies = candidate["dependencies"]
            for dependency in dependencies:
                if dependency.get("target_file") == file_path:
                    dependency_fanout += 1
                    if is_test_path(candidate["file_path"]):
                        likely_failing_tests.add(candidate["file_path"])
                    records.append(
                        {
                            "impacted_file": file_path,
                            "impacted_symbol": None,
                            "risk_type": "dependency_fanout",
                            "severity": "medium",
                            "likely_failing_test": (
                                candidate["file_path"]
                                if is_test_path(candidate["file_path"])
                                else None
                            ),
                            "dependency_target": candidate["file_path"],
                        }
                    )
    rollback_complexity = (
        "high"
        if len(changed_files) >= 6 or api_break_candidates >= 2
        else "medium"
        if len(changed_files) >= 3
        else "low"
    )
    blast_radius = (
        "high"
        if dependency_fanout >= 10 or len(impacted_services) >= 3
        else "medium"
        if dependency_fanout >= 4 or len(changed_files) >= 3
        else "low"
    )
    risk_score = min(
        0.95,
        0.08 * len(changed_files)
        + 0.03 * dependency_fanout
        + 0.12 * api_break_candidates
        + 0.01 * len(impacted_symbols),
    )
    return {
        "changed_files": sorted(changed_files),
        "impacted_services": sorted(impacted_services),
        "impacted_symbols": sorted(impacted_symbols),
        "likely_failing_tests": sorted(likely_failing_tests),
        "rollback_complexity": rollback_complexity,
        "blast_radius": blast_radius,
        "risk_score": risk_score,
        "api_break_candidates": api_break_candidates,
        "dependency_fanout": dependency_fanout,
        "records": records,
    }


def _decision_plan_integrity(
    snapshot_id: str,
    evidence_bundle_ref: str,
    patch_diff: str,
    plan_payload: dict[str, Any],
    *,
    agent_run_id: str | None = None,
) -> dict[str, str]:
    request_hash = _hash_payload(
        {
            "snapshot_id": snapshot_id,
            "evidence_bundle_ref": evidence_bundle_ref,
            "patch_hash": hashlib.sha256(patch_diff.encode("utf-8")).hexdigest(),
        }
    )
    # For a nondeterministic agentic run the result_hash fingerprints THIS
    # recorded run (it binds in agent_run_id), not a reproducible answer to the
    # inputs. Non-agentic tiers keep the original input-addressed semantics.
    result_payload: dict[str, Any] = (
        {"plan": plan_payload, "agent_run_id": agent_run_id}
        if agent_run_id is not None
        else plan_payload
    )
    result_hash = _hash_payload(result_payload)
    return {"request_hash": request_hash, "result_hash": result_hash}


def _option_risk(risk_score: float) -> RiskProfile:
    penalty = max(5.0, round(risk_score * 100.0, 2))
    return RiskProfile(
        p5=-penalty,
        p95=max(10.0, 125.0 - penalty),
        probability_of_loss=min(max(risk_score, 0.0), 1.0),
        var_95=-penalty,
    )


async def create_repository_decision_plan(
    *,
    connector: DataConnector,
    request: RepositoryDecisionPlanCreateRequest,
    engine_revision: str,
    require_repository_connector: _RequireRepositoryConnector,
    resolve_repository_model: _ResolveRepositoryModel,
    read_json: _ReadJson,
    generate_repository_patch_plan: _GenerateRepositoryPatchPlan,
    validate_patch_against_snapshot: _ValidatePatchAgainstSnapshot,
    patch_impact_summary: Callable[[dict[str, Any], str], dict[str, Any]],
) -> RepositoryDecisionPlanResponse:
    require_repository_connector(connector)
    org_id = str(connector.org_id)
    repository_id = str(connector.id)
    model_id = resolve_repository_model(request.model)
    triage_manifest = repository_storage._load_triage_manifest(
        org_id=org_id,
        repository_id=repository_id,
        evidence_bundle_ref=request.workspace_evidence_bundle_ref,
    )
    triage_snapshot_id = str(triage_manifest.get("snapshot_id") or "").strip()
    if not triage_snapshot_id:
        raise RepositoryIntelligenceError(
            code="workspace_evidence_bundle_invalid",
            message=(
                "Workspace evidence bundle is missing a snapshot_id and cannot seed "
                "repository decision planning."
            ),
            status_code=422,
            details={
                "repository_id": repository_id,
                "workspace_evidence_bundle_ref": request.workspace_evidence_bundle_ref,
            },
        )
    resolved_snapshot_id = request.snapshot_id
    if resolved_snapshot_id and triage_snapshot_id != resolved_snapshot_id:
        raise RepositoryIntelligenceError(
            code="repository_decision_plan_snapshot_mismatch",
            message=(
                "Repository decision plan workspace_evidence_bundle_ref does not "
                "match the requested snapshot_id."
            ),
            status_code=409,
            details={
                "repository_id": repository_id,
                "requested_snapshot_id": resolved_snapshot_id,
                "workspace_evidence_bundle_ref": request.workspace_evidence_bundle_ref,
                "triage_snapshot_id": triage_snapshot_id,
            },
        )
    resolved_snapshot_id = triage_snapshot_id
    lookup_key = _decision_plan_lookup_key(
        snapshot_id=resolved_snapshot_id,
        workspace_evidence_bundle_ref=request.workspace_evidence_bundle_ref,
        model_id=model_id,
        engine_revision=engine_revision,
    )
    lookup_path = repository_runtime._decision_plan_lookup_dir(org_id, repository_id) / (
        f"{lookup_key}.json"
    )
    def _read_cached_decision_plan() -> RepositoryDecisionPlanResponse | None:
        if not lookup_path.exists():
            return None
        decision_plan_lookup = read_json(lookup_path)
        decision_plan_id = str(decision_plan_lookup.get("decision_plan_id") or "").strip()
        if not decision_plan_id:
            return None
        plan_path = repository_runtime._decision_plans_dir(
            org_id,
            repository_id,
        ) / f"{decision_plan_id}.json"
        if not plan_path.exists():
            return None
        cached_response = repository_runtime._lookup_response_payload(decision_plan_lookup)
        if cached_response is not None:
            return RepositoryDecisionPlanResponse.model_validate(cached_response)
        response = RepositoryDecisionPlanResponse.model_validate(read_json(plan_path))
        repository_runtime._write_json(
            lookup_path,
            {
                "decision_plan_id": decision_plan_id,
                "snapshot_id": resolved_snapshot_id,
                "workspace_evidence_bundle_ref": request.workspace_evidence_bundle_ref,
                "model_id": model_id,
                "created_at": decision_plan_lookup.get("created_at") or _utc_now().isoformat(),
                "response": response.model_dump(mode="json"),
            },
        )
        return response

    cached = _read_cached_decision_plan()
    if cached is not None:
        return cached

    # Cache miss. Serialize generation for this lookup_key so concurrent workers —
    # critically the nondeterministic verified_agentic tier — do not each run a
    # planner and persist divergent plans (the model_id sentinel already partitions
    # the cache by planner tier). Decision plans are append-only: the first completed
    # run populates the key and is served stably thereafter, never recomputed-and-
    # compared. failed/aborted/no_change runs raise inside the planner before this
    # point, so they are never cached.
    with _decision_plan_generation_lock(lookup_path.parent, lookup_key):
        cached = _read_cached_decision_plan()
        if cached is not None:
            return cached

        snapshot_manifest = repository_storage._load_snapshot_manifest(
            org_id=org_id,
            repository_id=repository_id,
            snapshot_id=resolved_snapshot_id,
        )
        plan_result = await generate_repository_patch_plan(
            model_id=model_id,
            snapshot_manifest=snapshot_manifest,
            triage_manifest=triage_manifest,
        )
        patch_diff = str(plan_result["patch_diff"])
        validate_patch_against_snapshot(
            snapshot_manifest=snapshot_manifest,
            patch_diff=patch_diff,
        )

        # Agentic provenance is recorded in the INTERNAL audit record only and binds
        # into result_hash; it never reaches the public DecisionPlan (red lines #3/#4).
        planner_execution_mode = str(plan_result.get("planner_execution_mode") or "").strip()
        is_agentic_plan = planner_execution_mode == "verified_agentic"
        agent_run_id = plan_result.get("agent_run_id") if is_agentic_plan else None

        created_at = _utc_now()
        patch_artifact_id = _stable_identifier(
            "patch",
            {
                "snapshot_id": resolved_snapshot_id,
                "patch_hash": hashlib.sha256(patch_diff.encode("utf-8")).hexdigest(),
            },
        )
        patch_path = repository_runtime._patches_dir(org_id, repository_id) / (
            f"{patch_artifact_id}.diff"
        )
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        patch_path.write_text(patch_diff, encoding="utf-8")

        impact_summary = patch_impact_summary(snapshot_manifest, patch_diff)
        patch_impact_report_id = _stable_identifier(
            "patch_impact",
            {
                "snapshot_id": resolved_snapshot_id,
                "patch_hash": hashlib.sha256(patch_diff.encode("utf-8")).hexdigest(),
                "impact": impact_summary,
            },
        )
        patch_impact_path = repository_runtime._patch_impact_dir(org_id, repository_id) / (
            f"{patch_impact_report_id}.json"
        )
        patch_impact_parquet = repository_runtime._patch_impact_dir(org_id, repository_id) / (
            f"{patch_impact_report_id}.parquet"
        )
        if not patch_impact_path.exists():
            patch_impact_path.parent.mkdir(parents=True, exist_ok=True)
            records = [
                PatchImpactReportRecord(
                    repository_id=repository_id,
                    snapshot_id=resolved_snapshot_id,
                    patch_impact_report_id=patch_impact_report_id,
                    impacted_file=row["impacted_file"],
                    impacted_symbol=row["impacted_symbol"],
                    risk_type=row["risk_type"],
                    severity=row["severity"],
                    likely_failing_test=row["likely_failing_test"],
                    dependency_target=row["dependency_target"],
                    created_at=created_at,
                )
                for row in impact_summary["records"]
            ]
            patch_impact_parquet.write_bytes(
                parquet_bytes_from_records(records, record_type=PatchImpactReportRecord)
                if records
                else parquet_bytes_from_records([], record_type=PatchImpactReportRecord)
            )
            repository_runtime._write_json(
                patch_impact_path,
                {
                    "patch_impact_report_id": patch_impact_report_id,
                    "snapshot_id": resolved_snapshot_id,
                    "created_at": created_at.isoformat(),
                    **impact_summary,
                    "patch_impact_artifact": repository_storage._artifact_ref(
                        artifact_id=_stable_identifier(
                            "artifact",
                            {"kind": "patch_impact_report", "id": patch_impact_report_id},
                        ),
                        artifact_kind="PatchImpactReport",
                        content_hash=repository_storage._hash_file(patch_impact_parquet),
                        storage_path=patch_impact_parquet,
                        schema_revision="runtime-internal-contracts-v1",
                        created_at=created_at,
                    ).model_dump(mode="json"),
                },
            )

        risk_profile = _option_risk(float(impact_summary["risk_score"]))
        candidate_fixes = plan_result.get("candidate_fixes")
        if isinstance(candidate_fixes, str):
            candidate_fix_list = [candidate_fixes]
        elif isinstance(candidate_fixes, list):
            candidate_fix_list = [str(item) for item in candidate_fixes if str(item).strip()]
        else:
            candidate_fix_list = []
        if not candidate_fix_list:
            candidate_fix_list = [
                str(plan_result.get("recommended_action") or "Apply repository patch").strip()
            ]

        confidence = float(plan_result.get("confidence") or 0.5)
        confidence = min(max(confidence, 0.0), 1.0)
        expected_value = round(
            max(1.0, confidence * 100.0 - float(impact_summary["risk_score"]) * 55.0),
            3,
        )
        token_metrics = TokenReductionMetrics(
            raw_repo_token_estimate=int(triage_manifest["raw_repo_token_estimate"]),
            evidence_bundle_token_count=int(triage_manifest["evidence_bundle_token_count"]),
            reduction_ratio=float(triage_manifest["reduction_ratio"]),
        )
        repository_analysis = RepositoryAnalysis(
            root_cause=str(plan_result.get("root_cause") or "").strip()
            or "Repository issue localized from bounded evidence bundle.",
            planner_model_id=str(plan_result.get("planner_model_id") or model_id).strip()
            or model_id,
            planner_execution_mode=str(
                plan_result.get("planner_execution_mode") or "provider_backed_chat"
            ).strip()
            or "provider_backed_chat",
            planner_provider_backend=(
                str(plan_result.get("planner_provider_backend")).strip()
                if plan_result.get("planner_provider_backend") is not None
                else None
            ),
            candidate_fixes=candidate_fix_list,
            impacted_services=list(impact_summary["impacted_services"]),
            impacted_symbols=list(impact_summary["impacted_symbols"]),
            likely_failing_tests=list(impact_summary["likely_failing_tests"]),
            rollback_complexity=str(impact_summary["rollback_complexity"]),
            blast_radius=str(impact_summary["blast_radius"]),
            workspace_evidence_refs=[request.workspace_evidence_bundle_ref],
            generated_patch_ref=patch_artifact_id,
            patch_impact_report_ref=patch_impact_report_id,
            token_reduction_metrics=token_metrics,
        )
        options = [
            DecisionOption(
                name=fix,
                rank=index,
                expected_value=max(expected_value - ((index - 1) * 7.5), 0.0),
                risk=risk_profile,
                score=max(confidence - ((index - 1) * 0.08), 0.0),
            )
            for index, fix in enumerate(candidate_fix_list[:5], start=1)
        ]
        plan_payload = {
            "recommended_action": str(
                plan_result.get("recommended_action") or candidate_fix_list[0]
            ).strip(),
            "confidence": confidence,
            "expected_value": expected_value,
            "risk": risk_profile.model_dump(mode="json"),
            "options": [option.model_dump(mode="json") for option in options],
            "rationale": str(plan_result.get("rationale") or "").strip()
            or "Candidate patch generated from bounded repository evidence.",
            "calibration": None,
            "repository_analysis": repository_analysis.model_dump(mode="json"),
        }
        integrity = _decision_plan_integrity(
            snapshot_id=resolved_snapshot_id,
            evidence_bundle_ref=request.workspace_evidence_bundle_ref,
            patch_diff=patch_diff,
            plan_payload=plan_payload,
            agent_run_id=agent_run_id,
        )
        decision_plan = DecisionPlan.model_validate(plan_payload | {"integrity": integrity})
        decision_plan_id = _stable_identifier(
            "decision_plan",
            {
                "snapshot_id": resolved_snapshot_id,
                "workspace_evidence_bundle_ref": request.workspace_evidence_bundle_ref,
                "plan": decision_plan.model_dump(mode="json"),
            },
        )
        plan_path = repository_runtime._decision_plans_dir(org_id, repository_id) / (
            f"{decision_plan_id}.json"
        )
        if not plan_path.exists():
            plan_path.parent.mkdir(parents=True, exist_ok=True)
            repository_runtime._write_json(
                plan_path,
                {
                    "repository_id": repository_id,
                    "snapshot_id": resolved_snapshot_id,
                    "decision_plan_id": decision_plan_id,
                    "workspace_evidence_bundle_ref": request.workspace_evidence_bundle_ref,
                    "patch_path": str(patch_path),
                    "created_at": created_at.isoformat(),
                    "decision_plan": decision_plan.model_dump(mode="json"),
                    # Internal audit provenance — ignored by RepositoryDecisionPlanResponse,
                    # so planner_engine="cline_fork"/transcript never reach the public API.
                    **(
                        {
                            "agent_provenance": {
                                "planner_engine": plan_result.get("planner_engine"),
                                "agent_run_id": plan_result.get("agent_run_id"),
                                "transcript_ref": plan_result.get("transcript_ref"),
                                "planner_execution_mode": planner_execution_mode,
                            }
                        }
                        if is_agentic_plan
                        else {}
                    ),
                },
            )
        response = RepositoryDecisionPlanResponse.model_validate(read_json(plan_path))
        repository_runtime._write_json(
            lookup_path,
            {
                "decision_plan_id": decision_plan_id,
                "snapshot_id": resolved_snapshot_id,
                "workspace_evidence_bundle_ref": request.workspace_evidence_bundle_ref,
                "model_id": model_id,
                "created_at": created_at.isoformat(),
                "response": response.model_dump(mode="json"),
            },
        )
        return response
