from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from apps.api_server.models.data_connector import DataConnector
from apps.api_server.schemas.repositories import (
    RepositoryApplyMode,
    RepositoryApplyRequest,
    RepositoryApplyResponse,
    RepositorySimulatePatchRequest,
    RepositorySimulationRequest,
)
from apps.api_server.schemas.response import DecisionEnvelope, DecisionPlan, RiskProfile
from apps.api_server.schemas.simulate import SimulateRequestExpert
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)
from apps.api_server.services.repository_intelligence_shared import _coerce_scope_uuid

_RequireRepositoryConnector = Callable[[DataConnector], None]
_GetPolicy = Callable[[str], Any]
_LoadManifest = Callable[..., dict[str, Any]]
_SimulationLookupKey = Callable[..., str]
_DirBuilder = Callable[[str, str], Path]
_ReadJson = Callable[[Path], dict[str, Any]]
_LookupResponsePayload = Callable[[dict[str, Any]], dict[str, Any] | None]
_WriteJson = Callable[[Path, dict[str, Any]], None]
_RunSimulationFast = Callable[..., Any]
_UtcNow = Callable[[], Any]
_StableIdentifier = Callable[..., str]
_ParseConnectorConfig = Callable[[DataConnector], dict[str, Any]]
_ResolvedRepositorySource = Callable[..., Any]
_GitCommand = Callable[..., str]
_RepositoryUrl = Callable[[dict[str, Any], str], str | None]
_AuthenticatedRepositoryUrl = Callable[[str, str, dict[str, Any]], str]
_RepoAccessToken = Callable[[dict[str, Any]], str | None]
_PatchChangedFiles = Callable[[str], dict[str, list[tuple[int, int]]]]


# Adaptive Monte Carlo scenario count. A trivial, high-confidence, low-blast patch (a
# one-line tsconfig fix) does not need the same sample budget as a high-blast,
# low-confidence, many-symbol change: MC standard error scales ~1/sqrt(runs), and a wider
# cost distribution (higher blast/rollback/impact) needs more samples to estimate the
# var_95 tail at equal precision. So scale `runs` with complexity + uncertainty, bounded
# by a floor (always enough for a stable estimate) and a ceiling (latency cap). The count
# is deterministic for fixed inputs, so cold/hot snapshots and the stored-plan vs
# working-tree-patch paths stay reproducible. Pin a fixed count (kill-switch / golden
# fixtures) with ALGENTA_REPOSITORY_SIMULATION_RUNS=<int>.
_SIMULATION_RUNS_FLOOR = 1_000
_SIMULATION_RUNS_CEILING = 20_000
_SIMULATION_RUNS_BASE = 1_000
_SIMULATION_RUNS_PER_UNIT = 2_000
_BLAST_RUNS_UNITS = {"low": 0.0, "medium": 1.0, "high": 3.0}
_ROLLBACK_RUNS_UNITS = {"low": 0.0, "medium": 1.0, "high": 2.0}


def _adaptive_simulation_runs(
    *,
    blast_radius: str,
    rollback_complexity: str,
    impacted_symbol_count: int,
    likely_failing_test_count: int,
    confidence: float,
) -> int:
    """Monte Carlo scenario count scaled by patch complexity + decision uncertainty.

    Deterministic for fixed inputs. Set ALGENTA_REPOSITORY_SIMULATION_RUNS=<int> to pin a
    fixed count (e.g. =5000 to restore the previous static behavior)."""
    override = os.environ.get("ALGENTA_REPOSITORY_SIMULATION_RUNS")
    if override:
        try:
            return max(1, int(override))
        except ValueError:
            pass
    clamped_confidence = max(0.0, min(1.0, confidence))
    units = (
        _BLAST_RUNS_UNITS.get(blast_radius, 1.0)
        + _ROLLBACK_RUNS_UNITS.get(rollback_complexity, 1.0)
        + min(impacted_symbol_count, 50) / 10.0  # up to +5 units
        + min(likely_failing_test_count, 30) / 10.0  # up to +3 units
        + (1.0 - clamped_confidence) * 4.0  # lower confidence -> more samples
    )
    runs = _SIMULATION_RUNS_BASE + int(round(units * _SIMULATION_RUNS_PER_UNIT))
    return max(_SIMULATION_RUNS_FLOOR, min(_SIMULATION_RUNS_CEILING, runs))


def _simulation_request_payload(
    *,
    blast_radius: str,
    rollback_complexity: str,
    impacted_symbol_count: int,
    likely_failing_test_count: int,
    confidence: float,
) -> SimulateRequestExpert:
    """Map decision risk signals -> the Monte Carlo expert request. Shared by the
    stored-plan path and the in-flight working-tree-patch path so both stay identical."""
    blast_radius_penalty = {"low": 10.0, "medium": 25.0, "high": 50.0}[blast_radius]
    rollback_penalty = {"low": 8.0, "medium": 18.0, "high": 35.0}[rollback_complexity]
    api_break_penalty = float(impacted_symbol_count * 2.5)
    likely_test_penalty = float(likely_failing_test_count * 2.0)
    success_mode = max(25.0, confidence * 100.0)
    payload = {
        "mode": "expert",
        "simulation_model": "monte_carlo",
        "runs": _adaptive_simulation_runs(
            blast_radius=blast_radius,
            rollback_complexity=rollback_complexity,
            impacted_symbol_count=impacted_symbol_count,
            likely_failing_test_count=likely_failing_test_count,
            confidence=confidence,
        ),
        "seed": 42,
        "simulation": {
            "variables": [
                {
                    "name": "repair_value",
                    "distribution": "triangular",
                    "params": {
                        "low": success_mode * 0.6,
                        "mode": success_mode,
                        "high": success_mode * 1.3,
                    },
                },
                {
                    "name": "blast_radius_cost",
                    "distribution": "triangular",
                    "params": {
                        "low": blast_radius_penalty * 0.5,
                        "mode": blast_radius_penalty,
                        "high": blast_radius_penalty * 1.5,
                    },
                },
                {
                    "name": "rollback_cost",
                    "distribution": "triangular",
                    "params": {
                        "low": rollback_penalty * 0.5,
                        "mode": rollback_penalty,
                        "high": rollback_penalty * 1.6,
                    },
                },
                {
                    "name": "api_break_cost",
                    "distribution": "triangular",
                    "params": {
                        "low": api_break_penalty * 0.5,
                        "mode": api_break_penalty,
                        "high": max(api_break_penalty * 1.5, 1.0),
                    },
                },
                {
                    "name": "test_failure_cost",
                    "distribution": "triangular",
                    "params": {
                        "low": likely_test_penalty * 0.5,
                        "mode": likely_test_penalty,
                        "high": max(likely_test_penalty * 1.5, 1.0),
                    },
                },
            ],
            "objective_function": (
                "repair_value - blast_radius_cost - rollback_cost - api_break_cost - "
                "test_failure_cost"
            ),
            "scoring": {"expected_value": 0.55, "downside_risk": 0.45},
        },
    }
    return SimulateRequestExpert.model_validate(payload)


def _simulation_request_from_plan(plan: DecisionPlan) -> SimulateRequestExpert:
    analysis = plan.repository_analysis
    if analysis is None or analysis.patch_impact_report_ref is None:
        raise RepositoryIntelligenceError(
            code="repository_analysis_required",
            message="Decision plan is missing repository analysis or patch impact data.",
            status_code=409,
        )
    return _simulation_request_payload(
        blast_radius=analysis.blast_radius,
        rollback_complexity=analysis.rollback_complexity,
        impacted_symbol_count=len(analysis.impacted_symbols),
        likely_failing_test_count=len(analysis.likely_failing_tests),
        confidence=plan.confidence,
    )


def _simulation_request_from_patch_impact(
    impact: dict[str, Any], confidence: float
) -> SimulateRequestExpert:
    return _simulation_request_payload(
        blast_radius=str(impact["blast_radius"]),
        rollback_complexity=str(impact["rollback_complexity"]),
        impacted_symbol_count=len(impact.get("impacted_symbols", [])),
        likely_failing_test_count=len(impact.get("likely_failing_tests", [])),
        confidence=confidence,
    )


async def simulate_repository_patch(
    *,
    connector: DataConnector,
    request: RepositorySimulatePatchRequest,
    require_repository_connector: _RequireRepositoryConnector,
    get_policy: _GetPolicy,
    load_snapshot_manifest: _LoadManifest,
    validate_patch_against_snapshot: Callable[..., None],
    patch_impact_summary: Callable[..., dict[str, Any]],
    run_simulation_fast: _RunSimulationFast,
) -> DecisionEnvelope:
    """Simulate an IN-FLIGHT working-tree patch via the Mojo engine — no stored
    decision plan required.

    The verified_agentic agent edits files mid-run; this lets it verify the patch
    BEFORE finishing (Python still recomputes the authoritative diff downstream).
    The sim inputs come straight from the patch impact, and the same calibrated-risk
    gate as the stored-plan path decides apply_patch vs hold_patch.
    """
    require_repository_connector(connector)
    org_id = str(connector.org_id)
    repository_id = str(connector.id)
    policy = get_policy(org_id)
    snapshot_manifest = load_snapshot_manifest(
        org_id=org_id,
        repository_id=repository_id,
        snapshot_id=request.snapshot_id,
    )
    validate_patch_against_snapshot(
        snapshot_manifest=snapshot_manifest, patch_diff=request.patch_diff
    )
    impact = patch_impact_summary(snapshot_manifest, request.patch_diff)
    confidence = min(
        max(float(request.confidence if request.confidence is not None else 0.6), 0.0), 1.0
    )
    simulation_request = _simulation_request_from_patch_impact(impact, confidence)
    envelope, _persist_meta = await run_simulation_fast(
        simulation_request,
        org_id=_coerce_scope_uuid(connector.org_id),
        api_key_id=_coerce_scope_uuid(connector.owner_key_id) if connector.owner_key_id else None,
    )
    var_95 = abs(float(envelope.metrics.var_95 or 0.0))
    gate_passed = envelope.confidence >= policy.min_confidence and (
        policy.risk_floor is None or var_95 <= policy.risk_floor
    )
    return envelope.model_copy(
        update={"recommended_action": "apply_patch" if gate_passed else "hold_patch"}
    )


def _mirror_simulation_manifest_to_object_store(
    *,
    org_id: str,
    repository_id: str,
    simulation_id: str,
    manifest: dict[str, Any],
) -> str | None:
    """B8 durability: mirror the simulation MANIFEST to the durable, tenant-scoped object store when
    it's enabled (``ALGENTA_RI_OBJECT_STORE=s3``), so it's recoverable from any replica. The
    node-local copy stays the fast path. Returns ``None`` in local mode (no-op, backward
    compatible). Fails closed (502) when the durable write fails.

    This helper imports the object-store primitives DIRECTLY (it does NOT route through the injected
    ``write_json`` callable the workflow uses for the local write) — it is identity + dict only, so
    it behaves identically regardless of how the local write was performed.

    MANIFEST-DURABILITY ONLY for ``seed=None`` runs: Monte-Carlo simulation with no seed is
    non-deterministic and the simulation lookup index stays node-local in this slice, so two
    replicas that both miss the local lookup can persist divergent envelopes (the per-id append-only
    guard only dedups identical ids). Cross-replica dedup (lookup-index migration + a cross-node
    lock) is a flagged Wave-C follow-up. The key is NOT self-recorded — the read path re-derives it
    from identity."""
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
        kind="simulations",
        artifact_id=simulation_id,
    )
    try:
        get_object_store().put_json(key, manifest)
    except Exception as exc:  # noqa: BLE001 — surface as a fail-closed simulation error
        raise RepositoryIntelligenceError(
            code="simulation_manifest_persist_failed",
            message=f"failed to persist the simulation manifest to the object store: {exc}",
            status_code=502,
        ) from exc
    return key


async def simulate_repository_decision(
    *,
    connector: DataConnector,
    request: RepositorySimulationRequest,
    require_repository_connector: _RequireRepositoryConnector,
    get_policy: _GetPolicy,
    load_decision_plan_manifest: _LoadManifest,
    simulation_lookup_key: _SimulationLookupKey,
    simulation_lookup_dir: _DirBuilder,
    read_json: _ReadJson,
    simulations_dir: _DirBuilder,
    lookup_response_payload: _LookupResponsePayload,
    write_json: _WriteJson,
    load_snapshot_manifest: _LoadManifest,
    load_patch_impact_manifest: _LoadManifest,
    run_simulation_fast: _RunSimulationFast,
    utc_now: _UtcNow,
    stable_identifier: _StableIdentifier,
) -> DecisionEnvelope:
    require_repository_connector(connector)
    org_id = str(connector.org_id)
    repository_id = str(connector.id)
    policy = get_policy(org_id)
    plan_manifest = load_decision_plan_manifest(
        org_id=org_id,
        repository_id=repository_id,
        decision_plan_id=request.decision_plan_id,
    )
    plan_snapshot_id = str(plan_manifest.get("snapshot_id") or "").strip()
    if not plan_snapshot_id:
        raise RepositoryIntelligenceError(
            code="decision_plan_invalid",
            message="Repository decision plan is missing snapshot_id required for simulation.",
            status_code=409,
            details={
                "repository_id": repository_id,
                "decision_plan_id": request.decision_plan_id,
            },
        )
    resolved_snapshot_id = request.snapshot_id
    if resolved_snapshot_id and resolved_snapshot_id != plan_snapshot_id:
        raise RepositoryIntelligenceError(
            code="repository_simulation_snapshot_mismatch",
            message="Repository simulation snapshot_id does not match the decision plan snapshot.",
            status_code=409,
            details={
                "repository_id": repository_id,
                "requested_snapshot_id": resolved_snapshot_id,
                "decision_plan_id": request.decision_plan_id,
                "decision_plan_snapshot_id": plan_snapshot_id,
            },
        )
    resolved_snapshot_id = plan_snapshot_id
    lookup_key = simulation_lookup_key(
        snapshot_id=resolved_snapshot_id,
        decision_plan_id=request.decision_plan_id,
        policy_snapshot_id=policy.snapshot_id,
        runs=request.runs,
        seed=request.seed,
    )
    lookup_path = simulation_lookup_dir(org_id, repository_id) / f"{lookup_key}.json"
    if lookup_path.exists():
        simulation_lookup = read_json(lookup_path)
        simulation_id = str(simulation_lookup.get("simulation_id") or "").strip()
        if simulation_id:
            simulation_path = simulations_dir(org_id, repository_id) / f"{simulation_id}.json"
            if simulation_path.exists():
                cached_response = lookup_response_payload(simulation_lookup)
                if cached_response is not None:
                    return DecisionEnvelope.model_validate(cached_response)
                simulation_manifest = read_json(simulation_path)
                response = DecisionEnvelope.model_validate(simulation_manifest["envelope"])
                write_json(
                    lookup_path,
                    {
                        "simulation_id": simulation_id,
                        "snapshot_id": resolved_snapshot_id,
                        "decision_plan_id": request.decision_plan_id,
                        "policy_snapshot_id": policy.snapshot_id,
                        "runs": request.runs,
                        "seed": request.seed,
                        "created_at": simulation_lookup.get("created_at")
                        or utc_now().isoformat(),
                        "response": response.model_dump(mode="json"),
                    },
                )
                return response
    snapshot_manifest = load_snapshot_manifest(
        org_id=org_id,
        repository_id=repository_id,
        snapshot_id=resolved_snapshot_id,
    )
    decision_plan = DecisionPlan.model_validate(plan_manifest["decision_plan"])
    if (
        decision_plan.repository_analysis is None
        or decision_plan.repository_analysis.patch_impact_report_ref is None
    ):
        raise RepositoryIntelligenceError(
            code="repository_analysis_required",
            message="Decision plan is missing patch impact metadata required for simulation.",
            status_code=409,
        )
    patch_impact_manifest = load_patch_impact_manifest(
        org_id=org_id,
        repository_id=repository_id,
        patch_impact_report_id=decision_plan.repository_analysis.patch_impact_report_ref,
    )
    # Omitted runs => keep the complexity-adaptive count from _simulation_request_from_plan;
    # an explicit request.runs pins it. Same for seed (never override with None).
    simulation_overrides: dict[str, Any] = {}
    if request.runs is not None:
        simulation_overrides["runs"] = request.runs
    if request.seed is not None:
        simulation_overrides["seed"] = request.seed
    simulation_request = _simulation_request_from_plan(decision_plan).model_copy(
        update=simulation_overrides
    )
    envelope, _persist_meta = await run_simulation_fast(
        simulation_request,
        org_id=_coerce_scope_uuid(connector.org_id),
        api_key_id=_coerce_scope_uuid(connector.owner_key_id) if connector.owner_key_id else None,
    )
    risk_floor = policy.risk_floor
    var_95 = abs(float(envelope.metrics.var_95 or 0.0))
    gate_passed = envelope.confidence >= policy.min_confidence and (
        risk_floor is None or var_95 <= risk_floor
    )
    action = "apply_patch" if gate_passed else "hold_patch"
    decision_plan = decision_plan.model_copy(
        update={
            "confidence": envelope.confidence,
            "expected_value": envelope.metrics.expected_value,
            "risk": RiskProfile(
                p5=envelope.percentiles.p5,
                p95=envelope.percentiles.p95,
                probability_of_loss=envelope.metrics.probability_of_loss,
                var_95=envelope.metrics.var_95,
            ),
        }
    )
    simulation_id = stable_identifier(
        "simulation",
        {
            "snapshot_id": resolved_snapshot_id,
            "decision_plan_id": request.decision_plan_id,
            "policy_snapshot_id": policy.snapshot_id,
            "runs": request.runs,
            "seed": request.seed,
        },
    )
    score_breakdown = {
        "repository_risk_score": float(patch_impact_manifest["risk_score"]),
        "apply_gate": {
            "passed": gate_passed,
            "policy_snapshot_id": policy.snapshot_id,
            "min_confidence": policy.min_confidence,
            "risk_floor": risk_floor,
            "var_95": envelope.metrics.var_95,
        },
        "patch_impact": {
            "changed_files": patch_impact_manifest["changed_files"],
            "blast_radius": patch_impact_manifest["blast_radius"],
            "rollback_complexity": patch_impact_manifest["rollback_complexity"],
            "dependency_fanout": patch_impact_manifest["dependency_fanout"],
            "api_break_candidates": patch_impact_manifest["api_break_candidates"],
        },
    }
    validated_inputs = dict(envelope.validated_inputs or {})
    validated_inputs.update(
        {
            "repository_id": repository_id,
            "snapshot_id": resolved_snapshot_id,
            "decision_plan_id": request.decision_plan_id,
            "simulation_id": simulation_id,
            "resolved_revision": snapshot_manifest["resolved_revision"],
        }
    )
    envelope.recommended_action = action
    envelope.rationale = (
        "Patch simulation satisfied policy thresholds."
        if gate_passed
        else "Patch simulation did not satisfy policy thresholds."
    )
    envelope.score_breakdown = score_breakdown
    envelope.validated_inputs = validated_inputs
    envelope.decision_plan = decision_plan
    simulation_path = simulations_dir(org_id, repository_id) / f"{simulation_id}.json"
    if not simulation_path.exists():
        simulation_path.parent.mkdir(parents=True, exist_ok=True)
        simulation_manifest = {
            "repository_id": repository_id,
            "snapshot_id": resolved_snapshot_id,
            "decision_plan_id": request.decision_plan_id,
            "simulation_id": simulation_id,
            "apply_gate": score_breakdown["apply_gate"],
            "created_at": utc_now().isoformat(),
            "envelope": envelope.model_dump(mode="json"),
        }
        write_json(simulation_path, simulation_manifest)
        # B8: mirror the simulation manifest to the durable object store. Manifest-durability only
        # for seed=None Monte-Carlo (non-deterministic + node-local lookup => no cross-replica
        # dedup). No-op in local mode; fails closed (502) in s3. The lookup index below stays local.
        _mirror_simulation_manifest_to_object_store(
            org_id=org_id,
            repository_id=repository_id,
            simulation_id=simulation_id,
            manifest=simulation_manifest,
        )
    write_json(
        lookup_path,
        {
            "simulation_id": simulation_id,
            "snapshot_id": resolved_snapshot_id,
            "decision_plan_id": request.decision_plan_id,
            "policy_snapshot_id": policy.snapshot_id,
            "runs": request.runs,
            "seed": request.seed,
            "created_at": utc_now().isoformat(),
            "response": envelope.model_dump(mode="json"),
        },
    )
    return envelope


def _patch_text_for_plan(
    *, org_id: str, repository_id: str, decision_plan_manifest: dict[str, Any]
) -> str:
    patch_path = Path(decision_plan_manifest["patch_path"])
    if not patch_path.exists():
        raise RepositoryIntelligenceError(
            code="generated_patch_not_found",
            message=f"Generated patch artifact '{patch_path.name}' was not found.",
            status_code=404,
        )
    return patch_path.read_text(encoding="utf-8")


def _ensure_clean_git_worktree(path: Path, *, git_command: _GitCommand) -> None:
    status = str(git_command(["git", "-C", str(path), "status", "--porcelain"], timeout=20.0))
    if status.strip():
        raise RepositoryIntelligenceError(
            code="repository_worktree_not_clean",
            message=f"Repository worktree '{path}' contains uncommitted changes. Apply is blocked.",
            status_code=409,
        )


def _apply_patch_to_git_checkout(
    *,
    checkout_path: Path,
    patch_text: str,
    branch_name: str,
    commit_message: str,
    base_branch: str | None,
    git_command: _GitCommand,
) -> str:
    _ensure_clean_git_worktree(checkout_path, git_command=git_command)
    git_command(
        ["git", "-C", str(checkout_path), "config", "user.name", "Algenta Repository Intelligence"],
        timeout=20.0,
    )
    git_command(
        [
            "git",
            "-C",
            str(checkout_path),
            "config",
            "user.email",
            "repository-intelligence@algenta.local",
        ],
        timeout=20.0,
    )
    if base_branch:
        git_command(["git", "-C", str(checkout_path), "checkout", base_branch], timeout=60.0)
    git_command(["git", "-C", str(checkout_path), "checkout", "-b", branch_name], timeout=60.0)
    patch_path = checkout_path / ".algenta.patch.diff"
    patch_path.write_text(patch_text, encoding="utf-8")
    git_command(
        ["git", "-C", str(checkout_path), "apply", "--index", str(patch_path)],
        timeout=60.0,
    )
    git_command(["git", "-C", str(checkout_path), "commit", "-m", commit_message], timeout=60.0)
    return str(git_command(["git", "-C", str(checkout_path), "rev-parse", "HEAD"], timeout=20.0))


def _config_remote_metadata(
    connector_type: str, config: dict[str, Any], repository_url: str
) -> dict[str, str]:
    parsed = urlparse(
        repository_url.replace("git@", "ssh://git@").replace(":", "/", 1)
        if repository_url.startswith("git@")
        else repository_url
    )
    path = parsed.path.removeprefix("/").removesuffix(".git")
    parts = [part for part in path.split("/") if part]
    if connector_type == "github_repo":
        if len(parts) < 2:
            raise RepositoryIntelligenceError(
                code="invalid_repository_config",
                message="GitHub repository_url must include owner and repo.",
                status_code=422,
            )
        return {"owner": parts[-2], "repo": parts[-1]}
    if connector_type == "gitlab_repo":
        return {"project_path": "/".join(parts)}
    if connector_type == "bitbucket_repo":
        if len(parts) < 2:
            raise RepositoryIntelligenceError(
                code="invalid_repository_config",
                message="Bitbucket repository_url must include workspace and repo slug.",
                status_code=422,
            )
        return {"workspace": parts[-2], "repo_slug": parts[-1]}
    raise RepositoryIntelligenceError(
        code="repository_remote_metadata_unsupported",
        message=f"Connector type '{connector_type}' does not support remote pull request creation.",
        status_code=409,
    )


async def _create_pull_request(
    *,
    connector_type: str,
    config: dict[str, Any],
    repository_url: str,
    source_branch: str,
    target_branch: str,
    title: str,
    body: str,
    repo_access_token: _RepoAccessToken,
) -> str:
    token = repo_access_token(config)
    if token is None:
        raise RepositoryIntelligenceError(
            code="repository_write_credentials_required",
            message=(
                f"{connector_type} remote PR creation requires access_token in "
                "connector config."
            ),
            status_code=409,
        )
    metadata = _config_remote_metadata(connector_type, config, repository_url)
    headers: dict[str, str]
    request_url: str
    payload: dict[str, Any]
    if connector_type == "github_repo":
        api_base = str(config.get("api_base_url") or "https://api.github.com").rstrip("/")
        request_url = f"{api_base}/repos/{metadata['owner']}/{metadata['repo']}/pulls"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        payload = {"title": title, "head": source_branch, "base": target_branch, "body": body}
    elif connector_type == "gitlab_repo":
        api_base = str(config.get("api_base_url") or "https://gitlab.com/api/v4").rstrip("/")
        request_url = (
            f"{api_base}/projects/{quote(metadata['project_path'], safe='')}/merge_requests"
        )
        headers = {"PRIVATE-TOKEN": token}
        payload = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
            "description": body,
        }
    else:
        api_base = str(config.get("api_base_url") or "https://api.bitbucket.org/2.0").rstrip("/")
        request_url = (
            f"{api_base}/repositories/{metadata['workspace']}/{metadata['repo_slug']}/pullrequests"
        )
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "title": title,
            "source": {"branch": {"name": source_branch}},
            "destination": {"branch": {"name": target_branch}},
            "description": body,
        }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(request_url, headers=headers, json=payload)
    if response.status_code >= 400:
        raise RepositoryIntelligenceError(
            code="remote_pull_request_failed",
            message=f"Remote pull request creation failed with status {response.status_code}.",
            status_code=502,
            details={"response": response.text},
        )
    data = response.json()
    pr_url = (
        data.get("html_url")
        or data.get("web_url")
        or data.get("links", {}).get("html", {}).get("href")
        or data.get("links", {}).get("self", {}).get("href")
    )
    if not isinstance(pr_url, str) or not pr_url:
        raise RepositoryIntelligenceError(
            code="remote_pull_request_missing_url",
            message="Provider created a pull request but did not return a browser URL.",
            status_code=502,
        )
    return pr_url


async def apply_repository_decision(
    *,
    connector: DataConnector,
    request: RepositoryApplyRequest,
    require_repository_connector: _RequireRepositoryConnector,
    parse_connector_config: _ParseConnectorConfig,
    load_decision_plan_manifest: _LoadManifest,
    load_simulation_manifest: _LoadManifest,
    load_snapshot_manifest: _LoadManifest,
    utc_now: _UtcNow,
    patch_changed_files: _PatchChangedFiles,
    resolved_repository_source: _ResolvedRepositorySource,
    git_command: _GitCommand,
    repository_url: _RepositoryUrl,
    authenticated_repository_url: _AuthenticatedRepositoryUrl,
    repo_access_token: _RepoAccessToken,
    stable_identifier: _StableIdentifier,
    apply_dir: _DirBuilder,
    write_json: _WriteJson,
) -> RepositoryApplyResponse:
    require_repository_connector(connector)
    config = parse_connector_config(connector)
    org_id = str(connector.org_id)
    repository_id = str(connector.id)
    plan_manifest = load_decision_plan_manifest(
        org_id=org_id,
        repository_id=repository_id,
        decision_plan_id=request.decision_plan_id,
    )
    simulation_manifest = load_simulation_manifest(
        org_id=org_id,
        repository_id=repository_id,
        simulation_id=request.simulation_id,
    )
    plan_snapshot_id = str(plan_manifest.get("snapshot_id") or "").strip()
    simulation_snapshot_id = str(simulation_manifest.get("snapshot_id") or "").strip()
    if not plan_snapshot_id or not simulation_snapshot_id:
        raise RepositoryIntelligenceError(
            code="repository_apply_snapshot_missing",
            message=(
                "Repository apply requires snapshot_id on both the decision plan "
                "and simulation artifacts."
            ),
            status_code=409,
            details={
                "repository_id": repository_id,
                "decision_plan_id": request.decision_plan_id,
                "simulation_id": request.simulation_id,
            },
        )
    if plan_snapshot_id != simulation_snapshot_id:
        raise RepositoryIntelligenceError(
            code="repository_apply_snapshot_mismatch",
            message=(
                "Repository apply decision plan and simulation artifacts refer "
                "to different snapshots."
            ),
            status_code=409,
            details={
                "repository_id": repository_id,
                "decision_plan_id": request.decision_plan_id,
                "simulation_id": request.simulation_id,
                "decision_plan_snapshot_id": plan_snapshot_id,
                "simulation_snapshot_id": simulation_snapshot_id,
            },
        )
    resolved_snapshot_id = request.snapshot_id
    if resolved_snapshot_id and resolved_snapshot_id != plan_snapshot_id:
        raise RepositoryIntelligenceError(
            code="repository_apply_requested_snapshot_mismatch",
            message=(
                "Repository apply snapshot_id does not match the decision plan "
                "and simulation snapshot."
            ),
            status_code=409,
            details={
                "repository_id": repository_id,
                "requested_snapshot_id": resolved_snapshot_id,
                "decision_plan_snapshot_id": plan_snapshot_id,
                "simulation_snapshot_id": simulation_snapshot_id,
            },
        )
    resolved_snapshot_id = plan_snapshot_id
    load_snapshot_manifest(
        org_id=org_id,
        repository_id=repository_id,
        snapshot_id=resolved_snapshot_id,
    )
    apply_gate = simulation_manifest["apply_gate"]
    patch_text = _patch_text_for_plan(
        org_id=org_id,
        repository_id=repository_id,
        decision_plan_manifest=plan_manifest,
    )
    created_at = utc_now()
    branch_name = request.branch_name or f"algenta/{request.decision_plan_id[:12]}"
    commit_message = (
        request.commit_message
        or f"Algenta repository intelligence patch {request.decision_plan_id}"
    )
    validation_summary = {"patch_files": sorted(patch_changed_files(patch_text))}
    target_branch = request.base_branch or str(config.get("default_branch") or "main")

    if request.mode == RepositoryApplyMode.PATCH_ONLY:
        return RepositoryApplyResponse(
            repository_id=repository_id,
            snapshot_id=resolved_snapshot_id,
            decision_plan_id=request.decision_plan_id,
            simulation_id=request.simulation_id,
            mode=request.mode,
            applied=False,
            created_at=created_at,
            patch=patch_text,
            apply_gate=apply_gate,
            validation_summary=validation_summary,
        )
    if not bool(apply_gate.get("passed")):
        raise RepositoryIntelligenceError(
            code="repository_apply_gate_failed",
            message=(
                "Repository apply is blocked because simulation did not satisfy "
                "policy thresholds."
            ),
            status_code=409,
            details=apply_gate,
        )
    if not request.write_permission:
        raise RepositoryIntelligenceError(
            code="repository_write_permission_required",
            message="Repository write modes require write_permission=true.",
            status_code=409,
        )

    with resolved_repository_source(
        connector=connector,
        config=config,
        ref=request.base_branch,
        allow_writes=True,
        worktree_name=branch_name.replace("/", "-"),
    ) as source:
        checkout_path = source.root_path
        if not source.is_git:
            git_command(["git", "-C", str(checkout_path), "init", "-q"], timeout=20.0)
            git_command(["git", "-C", str(checkout_path), "add", "."], timeout=60.0)
            git_command(
                ["git", "-C", str(checkout_path), "commit", "-m", "Initial snapshot"],
                timeout=60.0,
            )
        commit_sha = _apply_patch_to_git_checkout(
            checkout_path=checkout_path,
            patch_text=patch_text,
            branch_name=branch_name,
            commit_message=commit_message,
            base_branch=request.base_branch,
            git_command=git_command,
        )
        pull_request_url: str | None = None
        if request.mode == RepositoryApplyMode.REMOTE_PR:
            resolved_repository_url = repository_url(config, source.connector_type)
            if resolved_repository_url is None or not source.is_git:
                raise RepositoryIntelligenceError(
                    code="remote_pr_unsupported_for_connector",
                    message=(
                        f"Connector type '{source.connector_type}' does not support "
                        "remote PR creation."
                    ),
                    status_code=409,
                )
            push_url = authenticated_repository_url(
                source.connector_type,
                resolved_repository_url,
                config,
            )
            git_command(
                ["git", "-C", str(checkout_path), "push", push_url, f"HEAD:{branch_name}"],
                timeout=180.0,
            )
            pull_request_url = await _create_pull_request(
                connector_type=source.connector_type,
                config=config,
                repository_url=resolved_repository_url,
                source_branch=branch_name,
                target_branch=target_branch,
                title=request.pull_request_title or commit_message,
                body=request.pull_request_body
                or f"Repository intelligence decision plan: {request.decision_plan_id}",
                repo_access_token=repo_access_token,
            )
        response = RepositoryApplyResponse(
            repository_id=repository_id,
            snapshot_id=resolved_snapshot_id,
            decision_plan_id=request.decision_plan_id,
            simulation_id=request.simulation_id,
            mode=request.mode,
            applied=True,
            created_at=created_at,
            patch=patch_text,
            branch_name=branch_name,
            commit_sha=commit_sha,
            local_checkout_path=str(checkout_path),
            pull_request_url=pull_request_url,
            apply_gate=apply_gate,
            validation_summary=validation_summary,
        )
        apply_id = stable_identifier(
            "apply",
            {
                "decision_plan_id": request.decision_plan_id,
                "simulation_id": request.simulation_id,
                "mode": request.mode.value,
                "branch_name": branch_name,
            },
        )
        apply_path = apply_dir(org_id, repository_id) / f"{apply_id}.json"
        if not apply_path.exists():
            apply_path.parent.mkdir(parents=True, exist_ok=True)
            write_json(apply_path, response.model_dump(mode="json"))
        return response
