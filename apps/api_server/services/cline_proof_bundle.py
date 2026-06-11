from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Mapping

from apps.api_server.services.cline_competitive_live_runs import (
    COMPETITIVE_RUNS_DIR,
    collect_live_cursor_mcp_comparison_artifact,
    collect_live_warm_cache_comparison_artifact,
)
from apps.api_server.services.cline_competitive_measurements import (
    CURSOR_MCP_COMPARISON_PATH,
    WARM_CACHE_COMPARISON_PATH,
)
from apps.api_server.services.cline_competitive_report import (
    COMPETITIVE_REPORT_PATH,
    build_competitive_experience_report,
    build_competitive_input_from_artifact_paths,
)
from apps.api_server.services.cline_competitive_status import (
    build_blocked_competitive_experience_report,
)
from apps.api_server.services.cline_live_matrix_results import (
    LIVE_MATRIX_RESULTS_PATH,
    LIVE_MATRIX_RUNS_DIR,
    build_live_matrix_results_artifact,
)
from apps.api_server.services.cline_live_matrix_selection import (
    ADAPTER_REGISTRY_PATH,
    LIVE_MATRIX_SELECTION_PATH,
)
from apps.api_server.services.cline_live_run_proof import (
    LIVE_RUN_PROOF_PATH,
    collect_live_run_proof,
)
from apps.api_server.services.cline_parity_report import (
    CHANNEL_PARITY_REPORT_PATH,
    PARITY_LEDGER_PATH,
    PARITY_REPORT_PATH,
    build_cline_parity_artifacts,
)
from apps.api_server.services.cline_proof_common import (
    CLINE_PROOFS_DIR,
    CLINE_RUNS_DIR,
    artifact_relative_path,
    build_proof_context,
    create_artifact_provenance,
    read_json,
    repo_root,
    validate_artifact_provenance,
    write_json,
)
from apps.api_server.services.cline_runtime_contract import (
    RUNTIME_CONTRACT_REPORT_PATH,
    collect_runtime_contract_report,
)


PROOF_BUNDLE_REPORT_PATH = CLINE_PROOFS_DIR / "proof_bundle_report.json"
DEFAULT_G0_ARTIFACT_PATH = CLINE_PROOFS_DIR / "g0_token_benchmark.json"


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
        return
    path.unlink(missing_ok=True)


def _owned_stage_paths(
    root: Path,
    *,
    execute_live_matrix: bool,
    execute_competitive: bool,
) -> tuple[Path, ...]:
    paths = [
        root / RUNTIME_CONTRACT_REPORT_PATH,
        root / LIVE_RUN_PROOF_PATH,
        root / ADAPTER_REGISTRY_PATH,
        root / LIVE_MATRIX_SELECTION_PATH,
        root / LIVE_MATRIX_RESULTS_PATH,
        root / PARITY_LEDGER_PATH,
        root / PARITY_REPORT_PATH,
        root / CHANNEL_PARITY_REPORT_PATH,
        root / PROOF_BUNDLE_REPORT_PATH,
        root / CLINE_RUNS_DIR,
    ]
    if execute_live_matrix:
        paths.append(root / LIVE_MATRIX_RUNS_DIR)
    if execute_competitive:
        paths.extend(
            [
                root / CURSOR_MCP_COMPARISON_PATH,
                root / WARM_CACHE_COMPARISON_PATH,
                root / COMPETITIVE_REPORT_PATH,
                root / COMPETITIVE_RUNS_DIR,
            ]
        )
    return tuple(paths)


def _prepare_owned_outputs(
    root: Path,
    *,
    execute_live_matrix: bool,
    execute_competitive: bool,
) -> None:
    for path in _owned_stage_paths(
        root,
        execute_live_matrix=execute_live_matrix,
        execute_competitive=execute_competitive,
    ):
        _remove_path(path)


def _runtime_contract_passed(payload: dict[str, Any]) -> bool:
    runtime_manifest = payload.get("runtime_manifest")
    session_contract = payload.get("session_contract")
    if not isinstance(runtime_manifest, dict) or not isinstance(session_contract, dict):
        return False
    manifest_payload = runtime_manifest.get("payload")
    if runtime_manifest.get("status_code") != 200 or not isinstance(manifest_payload, dict):
        return False
    runtime = manifest_payload.get("runtime")
    if not isinstance(runtime, dict):
        return False
    if runtime.get("kind") != "cline" or runtime.get("is_stub") is not False:
        return False
    required_status_codes = {
        "create": 201,
        "list": 200,
        "get": 200,
        "messages": 200,
        "usage": 200,
        "events": 200,
        "events_ndjson": 200,
        "events_sse": 200,
        "delete": 200,
    }
    for field_name, expected_code in required_status_codes.items():
        field_payload = session_contract.get(field_name)
        if not isinstance(field_payload, dict) or field_payload.get("status_code") != expected_code:
            return False
    start_payload = session_contract.get("start")
    if not isinstance(start_payload, dict):
        return False
    start_status = start_payload.get("status_code")
    if start_status == 200:
        pass
    elif start_status == 409:
        error_payload = start_payload.get("payload")
        if not isinstance(error_payload, dict):
            return False
        error = error_payload.get("error")
        if not isinstance(error, dict) or error.get("code") != "session_start_failed":
            return False
    else:
        return False
    run_compatibility = session_contract.get("run_compatibility")
    if not isinstance(run_compatibility, dict):
        return False
    return (
        run_compatibility.get("status_code") == 200
        and run_compatibility.get("final_frame_present") is True
    )


def _live_matrix_passed(payload: dict[str, Any], *, execute_live_matrix: bool) -> bool:
    status = payload.get("status")
    if execute_live_matrix:
        return status == "passed"
    return status == "ready_for_execution"


def _competitive_source_paths(
    root: Path,
    *,
    g0_artifact_path: Path | str | None,
) -> dict[str, Path]:
    return {
        "g0_artifact": (
            root / DEFAULT_G0_ARTIFACT_PATH
            if g0_artifact_path is None
            else Path(g0_artifact_path).resolve()
        ),
        "cursor_mcp_artifact": root / CURSOR_MCP_COMPARISON_PATH,
        "warm_cache_artifact": root / WARM_CACHE_COMPARISON_PATH,
    }


def _resolve_local_competitive_api_key(env: Mapping[str, str | None] | None) -> str:
    resolved_env = os.environ if env is None else env
    for key_name in ("ALGENTA_API_KEY", "DE_API_KEY"):
        value = resolved_env.get(key_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise RuntimeError(
        "missing required local API key environment variable: ALGENTA_API_KEY or DE_API_KEY"
    )


def _validated_competitive_input(
    *,
    root: Path,
    allow_dirty_tree: bool,
    g0_artifact_path: Path | str | None,
) -> tuple[dict[str, Any] | None, list[str], dict[str, Path]]:
    context = build_proof_context(root)
    artifact_paths = _competitive_source_paths(root, g0_artifact_path=g0_artifact_path)
    missing_files = [
        f"missing benchmark artifact file: {path}"
        for path in artifact_paths.values()
        if not path.exists()
    ]
    if missing_files:
        return None, missing_files, artifact_paths
    provenance_errors: list[str] = []
    for path in artifact_paths.values():
        payload = read_json(path)
        if not isinstance(payload, dict):
            provenance_errors.append(f"{path} must contain a JSON object")
            continue
        provenance_errors.extend(
            validate_artifact_provenance(
                payload=payload,
                context=context,
                artifact_path=path,
                allow_dirty_tree=allow_dirty_tree,
            )
        )
    benchmark_input = build_competitive_input_from_artifact_paths(
        g0_artifact_path=artifact_paths["g0_artifact"],
        cursor_mcp_artifact_path=artifact_paths["cursor_mcp_artifact"],
        warm_cache_artifact_path=artifact_paths["warm_cache_artifact"],
        root=root,
        allow_dirty_tree=allow_dirty_tree,
    )
    source_validation_errors = benchmark_input.setdefault("source_validation_errors", [])
    if not isinstance(source_validation_errors, list):
        raise ValueError("competitive benchmark input source_validation_errors must be a list")
    source_validation_errors.extend(provenance_errors)
    return benchmark_input, provenance_errors, artifact_paths


def _collect_or_reuse_competitive_report(
    *,
    root: Path,
    allow_dirty_tree: bool,
    execute_competitive: bool,
    cursor_repetitions: int,
    warm_repetitions: int,
    g0_artifact_path: Path | str | None,
    env: Mapping[str, str | None] | None,
) -> dict[str, Any]:
    artifact_paths = _competitive_source_paths(root, g0_artifact_path=g0_artifact_path)
    try:
        if execute_competitive:
            local_api_key = _resolve_local_competitive_api_key(env)
            collect_live_cursor_mcp_comparison_artifact(
                api_key=local_api_key,
                root=root,
                g0_artifact_path=artifact_paths["g0_artifact"],
                repetitions=cursor_repetitions,
            )
            collect_live_warm_cache_comparison_artifact(
                root=root,
                g0_artifact_path=artifact_paths["g0_artifact"],
                warm_repetitions=warm_repetitions,
            )
        benchmark_input, _provenance_errors, artifact_paths = _validated_competitive_input(
            root=root,
            allow_dirty_tree=allow_dirty_tree,
            g0_artifact_path=artifact_paths["g0_artifact"],
        )
        if benchmark_input is None:
            return build_blocked_competitive_experience_report(
                root=root,
                env=env,
                g0_artifact_path=artifact_paths["g0_artifact"],
                cursor_mcp_artifact_path=artifact_paths["cursor_mcp_artifact"],
                warm_cache_artifact_path=artifact_paths["warm_cache_artifact"],
            )
        return build_competitive_experience_report(
            benchmark_input=benchmark_input,
            root=root,
        )
    except Exception as exc:  # noqa: BLE001
        blocked = build_blocked_competitive_experience_report(
            root=root,
            env=env,
            g0_artifact_path=(
                artifact_paths["g0_artifact"] if artifact_paths["g0_artifact"].exists() else None
            ),
            cursor_mcp_artifact_path=(
                artifact_paths["cursor_mcp_artifact"]
                if artifact_paths["cursor_mcp_artifact"].exists()
                else None
            ),
            warm_cache_artifact_path=(
                artifact_paths["warm_cache_artifact"]
                if artifact_paths["warm_cache_artifact"].exists()
                else None
            ),
        )
        blockers = blocked.setdefault("blockers", [])
        if not isinstance(blockers, list):
            blockers = []
            blocked["blockers"] = blockers
        blockers.append(f"competitive proof generation failed: {type(exc).__name__}: {exc}")
        destination = root / COMPETITIVE_REPORT_PATH
        write_json(destination, blocked)
        blocked["artifact_path"] = artifact_relative_path(root, destination)
        return blocked


def _stage_result(
    *,
    stage: str,
    requested: bool,
    passed: bool,
    status: str,
    artifact_path: str | None,
    error: str | None = None,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "requested": requested,
        "passed": passed,
        "status": status,
        "artifact_path": artifact_path,
        "error": error,
        "blockers": [] if blockers is None else blockers,
    }


def build_cline_proof_bundle(
    *,
    root: Path | str | None = None,
    allow_dirty_tree: bool = False,
    allow_offline_live_docs: bool = True,
    execute_live_matrix: bool = False,
    max_live_matrix_languages: int | None = None,
    execute_competitive: bool = False,
    cursor_repetitions: int = 4,
    warm_repetitions: int = 5,
    g0_artifact_path: Path | str | None = None,
    env: Mapping[str, str | None] | None = None,
) -> dict[str, Any]:
    resolved_root = repo_root() if root is None else Path(root).resolve()
    context = build_proof_context(resolved_root)
    resolved_env = os.environ if env is None else env
    _prepare_owned_outputs(
        resolved_root,
        execute_live_matrix=execute_live_matrix,
        execute_competitive=execute_competitive,
    )

    stage_results: list[dict[str, Any]] = []
    artifacts: dict[str, str | None] = {
        "g0_benchmark": (
            artifact_relative_path(
                resolved_root,
                resolved_root / DEFAULT_G0_ARTIFACT_PATH,
            )
            if (resolved_root / DEFAULT_G0_ARTIFACT_PATH).exists()
            else None
        )
    }

    try:
        runtime_contract = collect_runtime_contract_report(root=resolved_root)
        artifacts["runtime_contract_report"] = runtime_contract.get("artifact_path")
        stage_results.append(
            _stage_result(
                stage="runtime_contract",
                requested=True,
                passed=_runtime_contract_passed(runtime_contract),
                status="passed" if _runtime_contract_passed(runtime_contract) else "failed",
                artifact_path=runtime_contract.get("artifact_path"),
            )
        )
    except Exception as exc:  # noqa: BLE001
        artifacts["runtime_contract_report"] = None
        stage_results.append(
            _stage_result(
                stage="runtime_contract",
                requested=True,
                passed=False,
                status="failed",
                artifact_path=None,
                error=f"{type(exc).__name__}: {exc}",
            )
        )

    try:
        live_run_proof = collect_live_run_proof(root=resolved_root)
        artifacts["live_run_proof"] = live_run_proof.get("artifact_path")
        stage_results.append(
            _stage_result(
                stage="live_run_proof",
                requested=True,
                passed=live_run_proof.get("status") == "passed",
                status=str(live_run_proof.get("status", "failed")),
                artifact_path=live_run_proof.get("artifact_path"),
                blockers=(
                    []
                    if live_run_proof.get("status") == "passed"
                    else [str(live_run_proof.get("terminal_state", "unknown"))]
                ),
            )
        )
    except Exception as exc:  # noqa: BLE001
        artifacts["live_run_proof"] = None
        stage_results.append(
            _stage_result(
                stage="live_run_proof",
                requested=True,
                passed=False,
                status="failed",
                artifact_path=None,
                error=f"{type(exc).__name__}: {exc}",
            )
        )

    try:
        live_matrix_results = build_live_matrix_results_artifact(
            root=resolved_root,
            env=resolved_env,
            execute=execute_live_matrix,
            max_languages=max_live_matrix_languages,
        )
        live_matrix_artifact_path = artifact_relative_path(
            resolved_root,
            resolved_root / LIVE_MATRIX_RESULTS_PATH,
        )
        artifacts["adapter_registry"] = artifact_relative_path(
            resolved_root,
            resolved_root / ADAPTER_REGISTRY_PATH,
        )
        artifacts["live_matrix_selection"] = artifact_relative_path(
            resolved_root,
            resolved_root / LIVE_MATRIX_SELECTION_PATH,
        )
        artifacts["live_matrix_results"] = live_matrix_artifact_path
        stage_results.append(
            _stage_result(
                stage="live_matrix",
                requested=True,
                passed=_live_matrix_passed(
                    live_matrix_results,
                    execute_live_matrix=execute_live_matrix,
                ),
                status=str(live_matrix_results.get("status", "failed")),
                artifact_path=live_matrix_artifact_path,
                blockers=[
                    str(blocker)
                    for blocker in live_matrix_results.get("blockers", [])
                    if isinstance(blocker, str) and blocker
                ],
            )
        )
    except Exception as exc:  # noqa: BLE001
        artifacts["adapter_registry"] = None
        artifacts["live_matrix_selection"] = None
        artifacts["live_matrix_results"] = None
        stage_results.append(
            _stage_result(
                stage="live_matrix",
                requested=True,
                passed=False,
                status="failed",
                artifact_path=None,
                error=f"{type(exc).__name__}: {exc}",
            )
        )

    try:
        _ledger, parity_report, _channel_report = build_cline_parity_artifacts(
            root=resolved_root,
            allow_offline_live_docs=allow_offline_live_docs,
            allow_dirty_tree=allow_dirty_tree,
        )
        artifacts["parity_ledger"] = artifact_relative_path(
            resolved_root,
            resolved_root / PARITY_LEDGER_PATH,
        )
        artifacts["parity_report"] = artifact_relative_path(
            resolved_root,
            resolved_root / PARITY_REPORT_PATH,
        )
        artifacts["channel_parity_report"] = artifact_relative_path(
            resolved_root,
            resolved_root / CHANNEL_PARITY_REPORT_PATH,
        )
        stage_results.append(
            _stage_result(
                stage="parity",
                requested=True,
                passed=parity_report.get("status") == "passed",
                status=str(parity_report.get("status", "failed")),
                artifact_path=artifacts["parity_report"],
                blockers=[
                    str(capability)
                    for capability in parity_report.get(
                        "unresolved_required_capabilities",
                        [],
                    )
                    if isinstance(capability, str) and capability
                ],
            )
        )
    except Exception as exc:  # noqa: BLE001
        artifacts["parity_ledger"] = None
        artifacts["parity_report"] = None
        artifacts["channel_parity_report"] = None
        stage_results.append(
            _stage_result(
                stage="parity",
                requested=True,
                passed=False,
                status="failed",
                artifact_path=None,
                error=f"{type(exc).__name__}: {exc}",
            )
        )

    competitive_report = _collect_or_reuse_competitive_report(
        root=resolved_root,
        allow_dirty_tree=allow_dirty_tree,
        execute_competitive=execute_competitive,
        cursor_repetitions=cursor_repetitions,
        warm_repetitions=warm_repetitions,
        g0_artifact_path=g0_artifact_path,
        env=resolved_env,
    )
    artifacts["competitive_experience_report"] = competitive_report.get("artifact_path")
    stage_results.append(
        _stage_result(
            stage="competitive",
            requested=execute_competitive,
            passed=competitive_report.get("status") == "passed",
            status=str(competitive_report.get("status", "failed")),
            artifact_path=competitive_report.get("artifact_path"),
            blockers=[
                str(blocker)
                for blocker in competitive_report.get("blockers", [])
                if isinstance(blocker, str) and blocker
            ]
            + [
                str(error)
                for error in competitive_report.get("source_validation_errors", [])
                if isinstance(error, str) and error
            ],
        )
    )

    requested_stages = [stage for stage in stage_results if stage["requested"]]
    passed_requested_stages = [stage for stage in requested_stages if stage["passed"]]
    payload = {
        **create_artifact_provenance(
            context,
            run_id="cline_proof_bundle",
            schema_version="cline-proof-bundle-report/v1",
        ),
        "status": (
            "passed"
            if len(passed_requested_stages) == len(requested_stages)
            else "failed"
        ),
        "options": {
            "allow_dirty_tree": allow_dirty_tree,
            "allow_offline_live_docs": allow_offline_live_docs,
            "execute_live_matrix": execute_live_matrix,
            "max_live_matrix_languages": max_live_matrix_languages,
            "execute_competitive": execute_competitive,
            "cursor_repetitions": cursor_repetitions,
            "warm_repetitions": warm_repetitions,
            "g0_artifact_path": (
                artifact_relative_path(
                    resolved_root,
                    (
                        resolved_root / DEFAULT_G0_ARTIFACT_PATH
                        if g0_artifact_path is None
                        else Path(g0_artifact_path).resolve()
                    ),
                )
                if (
                    (resolved_root / DEFAULT_G0_ARTIFACT_PATH).exists()
                    if g0_artifact_path is None
                    else Path(g0_artifact_path).resolve().exists()
                )
                else None
            ),
        },
        "requested_stage_count": len(requested_stages),
        "passed_requested_stage_count": len(passed_requested_stages),
        "progress_percent": round(
            (
                len(passed_requested_stages) / len(requested_stages) * 100.0
                if requested_stages
                else 100.0
            ),
            2,
        ),
        "stage_results": stage_results,
        "artifacts": artifacts,
    }
    destination = resolved_root / PROOF_BUNDLE_REPORT_PATH
    write_json(destination, payload)
    payload["artifact_path"] = artifact_relative_path(resolved_root, destination)
    return payload
