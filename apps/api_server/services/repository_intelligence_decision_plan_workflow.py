from __future__ import annotations

import fcntl
import hashlib
import os
from collections.abc import Awaitable, Callable
from contextlib import AbstractContextManager
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
from apps.api_server.services import (
    repository_intelligence_telemetry as telemetry,
)
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)
from apps.api_server.services.repository_intelligence_coordination import (
    coordinated_generation_lock,
    get_coordination_redis,
)
from apps.api_server.services.repository_intelligence_proof_store import mirror_proof_artifacts
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


def _planner_usage_from_telemetry(data: dict[str, Any]) -> dict[str, Any]:
    counters = data.get("counters", {})
    if not isinstance(counters, dict):
        return {}
    uncached = counters.get("llm_input_tokens_uncached", 0)
    cache_read = counters.get("llm_input_tokens_cached_read", 0)
    cache_write = counters.get("llm_input_tokens_cached_write", 0)
    output = counters.get("llm_output_tokens", 0)
    numeric_values = (uncached, cache_read, cache_write, output)
    if not any(isinstance(value, (int, float)) and not isinstance(value, bool) for value in numeric_values):
        return {}
    return {
        "input_tokens": float(uncached) + float(cache_read) + float(cache_write),
        "output_tokens": float(output),
        "cache_read_tokens": float(cache_read),
        "cache_write_tokens": float(cache_write),
        "cost_usd": None,
    }


def _planner_usage_from_plan_result(plan_result: dict[str, Any]) -> dict[str, Any]:
    usage = plan_result.get("planner_usage")
    if not isinstance(usage, dict):
        return {}
    required_keys = (
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
    )
    if not all(isinstance(usage.get(key), (int, float)) for key in required_keys):
        return {}
    return {
        "input_tokens": float(usage["input_tokens"]),
        "output_tokens": float(usage["output_tokens"]),
        "cache_read_tokens": float(usage["cache_read_tokens"]),
        "cache_write_tokens": float(usage["cache_write_tokens"]),
        "cost_usd": (
            float(usage["cost_usd"])
            if isinstance(usage.get("cost_usd"), (int, float))
            and not isinstance(usage.get("cost_usd"), bool)
            else None
        ),
    }


def _planner_usage_has_non_zero_tokens(usage: dict[str, Any]) -> bool:
    for key in (
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
    ):
        value = usage.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            return True
    return False


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


class _DecisionPlanGenerationLock(AbstractContextManager[None]):
    """Serialize decision-plan generation for one lookup_key across workers.

    Without this, two concurrent cache misses for the same key — critically the
    nondeterministic ``verified_agentic`` tier — would each run a planner and
    race to persist divergent plans. A host-local advisory ``flock`` is enough
    for the file-based runtime store; the production multi-tenant deployment
    swaps this for a Postgres advisory / Redis lock on the same key (plan §6).
    """

    def __init__(self, lookup_dir: Path, lookup_key: str) -> None:
        self._lookup_dir = lookup_dir
        self._lookup_key = lookup_key
        self._fd: int | None = None

    def __enter__(self) -> None:
        self._lookup_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self._lookup_dir / f"{self._lookup_key}.lock"
        # 0o600: the advisory flock anchor holds no data and is owner-only by design;
        # world-readable (0o644) is unnecessary and trips py/overly-permissive-file.
        self._fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> bool:
        if self._fd is None:
            return False
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            os.close(self._fd)
            self._fd = None
        return False


def _decision_plan_generation_lock(
    lookup_dir: Path,
    lookup_key: str,
) -> AbstractContextManager[None]:
    return _DecisionPlanGenerationLock(lookup_dir, lookup_key)


# Wave-C cross-node generation lock sizing. The lease auto-renews every TTL/3, so the TTL only bounds
# how long a stale lease survives if renewal STOPS (Redis trouble); the wait deadline bounds how long
# a losing replica waits for the winner before failing closed (retryable — the job path retries).
# Generous defaults cover a long verified_agentic run; env-tunable for ops.
_COORD_LOCK_TTL_S = int(os.environ.get("ALGENTA_COORDINATION_LOCK_TTL_S") or "900")
_COORD_WAIT_S = float(os.environ.get("ALGENTA_COORDINATION_WAIT_S") or "900")


def _decision_plan_lookup_artifact_key(org_id: str, repository_id: str, lookup_key: str) -> str:
    from apps.api_server.services.repository_intelligence_object_store import artifact_key

    return artifact_key(
        org_id=org_id, repository_id=repository_id, kind="decision_plan_lookup", artifact_id=lookup_key
    )


def _read_decision_plan_lookup_shared(
    org_id: str, repository_id: str, lookup_key: str
) -> dict[str, Any] | None:
    """Read the cross-replica decision-plan dedup lookup from the durable object store (s3 mode only;
    None in local mode). A genuine miss returns None; an object-store availability fault PROPAGATES
    (the dedup read must not fail-OPEN into a divergent regeneration — the caller fails closed and
    retries)."""
    from apps.api_server.services.repository_intelligence_object_store import (
        get_object_store,
        object_store_mode,
    )

    if object_store_mode() != "s3":
        return None
    return get_object_store().get_json(
        _decision_plan_lookup_artifact_key(org_id, repository_id, lookup_key)
    )


def _mirror_decision_plan_lookup(
    org_id: str, repository_id: str, lookup_key: str, payload: dict[str, Any]
) -> None:
    """Mirror the decision-plan dedup lookup to the durable object store (s3 only; no-op local). The
    shared lookup IS the cross-replica dedup mechanism, so a failed mirror fails closed (502) — a
    sibling replica must be able to see this plan rather than regenerate a divergent one."""
    from apps.api_server.services.repository_intelligence_object_store import (
        get_object_store,
        object_store_mode,
    )

    if object_store_mode() != "s3":
        return
    try:
        get_object_store().put_json(
            _decision_plan_lookup_artifact_key(org_id, repository_id, lookup_key), payload
        )
    except Exception as exc:  # noqa: BLE001 — fail closed; the run retries
        raise RepositoryIntelligenceError(
            code="decision_plan_lookup_persist_failed",
            message=f"failed to persist the decision-plan dedup lookup to the object store: {exc}",
            status_code=502,
        ) from exc


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


def _mirror_decision_plan_manifest_to_object_store(
    *,
    org_id: str,
    repository_id: str,
    decision_plan_id: str,
    manifest: dict[str, Any],
) -> str | None:
    """B8 durability: mirror the decision-plan MANIFEST to the durable, tenant-scoped object store
    when it's enabled (``ALGENTA_RI_OBJECT_STORE=s3``), so it's recoverable from any replica. The
    node-local copy stays the fast path. Returns ``None`` in local mode (no-op, backward
    compatible). Fails closed (502) when the durable write fails.

    MANIFEST-DURABILITY ONLY — this does NOT provide cross-replica dedup: the verified-agentic
    planner is non-deterministic and the decision-plan lookup index stays node-local in this slice,
    so two replicas that both miss the local lookup can each run the planner and durably persist
    DIVERGENT plans (the per-id append-only guard only dedups identical ids). The fix (migrating
    the lookup index + a cross-node advisory lock to replace the node-local flock) is a flagged
    Wave-C follow-up. The embedded ``patch_path`` (.diff) stays node-local (a separate bytes
    slice). The key is NOT self-recorded — the read path re-derives it from identity."""
    from apps.api_server.services.repository_intelligence_object_store import (
        artifact_key,
        get_object_store,
        object_store_mode,
    )

    if object_store_mode() != "s3":
        return None
    key = artifact_key(
        org_id=org_id,
        repository_id=repository_id,
        kind="decision_plans",
        artifact_id=decision_plan_id,
    )
    try:
        get_object_store().put_json(key, manifest)
    except Exception as exc:  # noqa: BLE001 — surface as a fail-closed decision-plan error
        raise RepositoryIntelligenceError(
            code="decision_plan_manifest_persist_failed",
            message=f"failed to persist the decision-plan manifest to the object store: {exc}",
            status_code=502,
        ) from exc
    return key


def _mirror_patch_impact_manifest_to_object_store(
    *,
    org_id: str,
    repository_id: str,
    patch_impact_report_id: str,
    manifest: dict[str, Any],
) -> str | None:
    """B8 durability: mirror the patch-impact-report MANIFEST to the durable, tenant-scoped object
    store when it's enabled (``ALGENTA_RI_OBJECT_STORE=s3``), so it's recoverable from any replica.
    The node-local copy stays the fast path. Returns ``None`` in local mode (no-op, backward
    compatible). Fails closed (502) when the durable write fails.

    The patch-impact summary is a deterministic function of the patch + snapshot, so a cross-replica
    recompute reproduces the same report — no divergence caveat. The embedded report Parquet sidecar
    stays node-local (a separate bytes slice). The key is NOT self-recorded — the read path
    re-derives it from identity."""
    from apps.api_server.services.repository_intelligence_object_store import (
        artifact_key,
        get_object_store,
        object_store_mode,
    )

    if object_store_mode() != "s3":
        return None
    key = artifact_key(
        org_id=org_id,
        repository_id=repository_id,
        kind="patch_impacts",
        artifact_id=patch_impact_report_id,
    )
    try:
        get_object_store().put_json(key, manifest)
    except Exception as exc:  # noqa: BLE001 — surface as a fail-closed patch-impact error
        raise RepositoryIntelligenceError(
            code="patch_impact_manifest_persist_failed",
            message=f"failed to persist the patch-impact manifest to the object store: {exc}",
            status_code=502,
        ) from exc
    return key


def _mirror_patch_diff_to_object_store(
    *,
    org_id: str,
    repository_id: str,
    patch_artifact_id: str,
    patch_diff: str,
) -> str | None:
    """B8 durability: mirror the generated patch ``.diff`` to the durable, tenant-scoped object store
    (``ALGENTA_RI_OBJECT_STORE=s3``) so APPLY works cross-replica — the .diff is otherwise node-local
    and ``_patch_text_for_plan`` reads it from ``patch_path`` (a plan generated on one replica can't
    be applied on another). Returns ``None`` in local mode (no-op, backward compatible); fails closed
    (502) when the durable write fails. ``patch_artifact_id`` hashes the diff, so the content is
    recover-by-identity; the key is NOT self-recorded (the apply path re-derives it from the
    manifest's ``patch_path`` filename stem)."""
    from apps.api_server.services.repository_intelligence_object_store import (
        artifact_key,
        get_object_store,
        object_store_mode,
    )

    if object_store_mode() != "s3":
        return None
    key = artifact_key(
        org_id=org_id,
        repository_id=repository_id,
        kind="patches",
        artifact_id=patch_artifact_id,
    )
    try:
        get_object_store().put_bytes(key, patch_diff.encode("utf-8"), content_type="text/x-diff")
    except Exception as exc:  # noqa: BLE001 — surface as a fail-closed patch error
        raise RepositoryIntelligenceError(
            code="patch_diff_persist_failed",
            message=f"failed to persist the generated patch diff to the object store: {exc}",
            status_code=502,
        ) from exc
    return key


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
        # Wave-C: node-local L1 first (fast path); on a local miss consult the SHARED cross-replica
        # lookup (the winner may have published on another replica). A genuine shared miss -> None;
        # an object-store availability fault propagates (fail closed, never a divergent regen).
        if lookup_path.exists():
            decision_plan_lookup = read_json(lookup_path)
        else:
            decision_plan_lookup = _read_decision_plan_lookup_shared(
                org_id, repository_id, lookup_key
            )
            if decision_plan_lookup is None:
                return None
        decision_plan_id = str(decision_plan_lookup.get("decision_plan_id") or "").strip()
        if not decision_plan_id:
            return None
        # Wave-C: serve the embedded response WITHOUT requiring a node-local plan_path — the winner's
        # plan manifest lives on another replica; the lookup carries the full response. (The old
        # `if not plan_path.exists(): return None` gate made a cross-replica loser regenerate even
        # though it could already see the winner's lookup — the #94 gap.)
        cached_response = repository_runtime._lookup_response_payload(decision_plan_lookup)
        if cached_response is not None:
            return RepositoryDecisionPlanResponse.model_validate(cached_response)
        # Legacy lookup without an embedded response: recover the plan manifest via the shared-aware
        # loader (B8 added the object-store fallback), then re-cache the response locally + shared.
        try:
            recovered = repository_storage._load_decision_plan_manifest(
                org_id=org_id, repository_id=repository_id, decision_plan_id=decision_plan_id
            )
        except RepositoryIntelligenceError:
            return None
        response = RepositoryDecisionPlanResponse.model_validate(recovered)
        _recache_payload = {
            "decision_plan_id": decision_plan_id,
            "snapshot_id": resolved_snapshot_id,
            "workspace_evidence_bundle_ref": request.workspace_evidence_bundle_ref,
            "model_id": model_id,
            "created_at": decision_plan_lookup.get("created_at") or _utc_now().isoformat(),
            "response": response.model_dump(mode="json"),
        }
        repository_runtime._write_json(lookup_path, _recache_payload)
        _mirror_decision_plan_lookup(org_id, repository_id, lookup_key, _recache_payload)
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
    # Wave-C: serialize generation ACROSS replicas. The cross-node lock makes a losing replica BLOCK
    # until the winner releases, then the in-lock re-check below reads the winner's SHARED lookup and
    # serves it — closing the #94 divergence. deterministic=False (the verified_agentic planner is
    # non-deterministic): on a true wait-deadline it fails closed (retryable) rather than regenerating.
    # Redis None (single process / coordination disabled) degrades to the host-local flock.
    async with coordinated_generation_lock(
        key=lookup_key,
        ttl_seconds=_COORD_LOCK_TTL_S,
        wait_timeout_seconds=_COORD_WAIT_S,
        deterministic=False,
        redis=get_coordination_redis(),
        local_fallback=lambda: _decision_plan_generation_lock(lookup_path.parent, lookup_key),
    ):
        cached = _read_cached_decision_plan()
        if cached is not None:
            return cached

        snapshot_manifest = repository_storage._load_snapshot_manifest(
            org_id=org_id,
            repository_id=repository_id,
            snapshot_id=resolved_snapshot_id,
        )
        with telemetry.collect_or_current() as planner_telemetry:
            plan_result = await generate_repository_patch_plan(
                model_id=model_id,
                snapshot_manifest=snapshot_manifest,
                triage_manifest=triage_manifest,
            )
            planner_usage = _planner_usage_from_telemetry(planner_telemetry)
            plan_result_usage = _planner_usage_from_plan_result(plan_result)
            if plan_result_usage and not _planner_usage_has_non_zero_tokens(planner_usage):
                planner_usage = plan_result_usage
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
        # B8: mirror the .diff to the durable object store so apply works cross-replica (no-op local;
        # fails closed in s3). Recovered by identity in execution_workflow._patch_text_for_plan.
        _mirror_patch_diff_to_object_store(
            org_id=org_id,
            repository_id=repository_id,
            patch_artifact_id=patch_artifact_id,
            patch_diff=patch_diff,
        )

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
            patch_impact_manifest = {
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
            }
            repository_runtime._write_json(patch_impact_path, patch_impact_manifest)
            # B8: mirror the patch-impact manifest (deterministic recompute -> no divergence). The
            # report Parquet sidecar stays node-local. No-op in local mode; fails closed (502) in s3.
            _mirror_patch_impact_manifest_to_object_store(
                org_id=org_id,
                repository_id=repository_id,
                patch_impact_report_id=patch_impact_report_id,
                manifest=patch_impact_manifest,
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
            plan_manifest = {
                "repository_id": repository_id,
                "snapshot_id": resolved_snapshot_id,
                "decision_plan_id": decision_plan_id,
                "workspace_evidence_bundle_ref": request.workspace_evidence_bundle_ref,
                "patch_path": str(patch_path),
                "created_at": created_at.isoformat(),
                "decision_plan": decision_plan.model_dump(mode="json"),
                "planner_usage": planner_usage,
                "agent_run_id": str(plan_result.get("agent_run_id") or "").strip() or None,
                "session_id": str(plan_result.get("session_id") or "").strip() or None,
                "runtime_kind": str(plan_result.get("runtime_kind") or "").strip() or None,
                "is_stub": (
                    plan_result.get("is_stub")
                    if isinstance(plan_result.get("is_stub"), bool)
                    else None
                ),
                "runtime_provider": (
                    str(plan_result.get("runtime_provider")).strip()
                    if plan_result.get("runtime_provider") is not None
                    else None
                ),
                "runtime_model": (
                    str(plan_result.get("runtime_model")).strip()
                    if plan_result.get("runtime_model") is not None
                    else None
                ),
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
            }
            repository_runtime._write_json(plan_path, plan_manifest)
            # B8: mirror the decision-plan manifest (manifest-durability only — non-deterministic
            # planner + node-local lookup means cross-replica dedup is NOT provided; the embedded
            # patch_path .diff stays node-local). No-op in local mode; fails closed (502) in s3.
            _mirror_decision_plan_manifest_to_object_store(
                org_id=org_id,
                repository_id=repository_id,
                decision_plan_id=decision_plan_id,
                manifest=plan_manifest,
            )
        response = RepositoryDecisionPlanResponse.model_validate(read_json(plan_path))
        _lookup_payload = {
            "decision_plan_id": decision_plan_id,
            "snapshot_id": resolved_snapshot_id,
            "workspace_evidence_bundle_ref": request.workspace_evidence_bundle_ref,
            "model_id": model_id,
            "created_at": created_at.isoformat(),
            "response": response.model_dump(mode="json"),
        }
        repository_runtime._write_json(lookup_path, _lookup_payload)
        # Wave-C: publish the lookup to the SHARED index so a waiting sibling replica serves THIS
        # plan (with its embedded response) instead of regenerating. Fail-closed in s3 (the shared
        # lookup is the dedup mechanism); no-op in local mode.
        _mirror_decision_plan_lookup(org_id, repository_id, lookup_key, _lookup_payload)
        # B9: mirror this run's proof bundle (runtime_manifest/messages/usage/gate/...) to the
        # durable object store for cross-replica recovery. Best-effort — never fails the plan; a
        # no-op for non-agentic plans (agent_run_id is None) and in local mode.
        await mirror_proof_artifacts(
            org_id=org_id, repository_id=repository_id, agent_run_id=agent_run_id
        )
        return response
