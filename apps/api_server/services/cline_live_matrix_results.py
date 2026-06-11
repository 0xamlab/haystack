from __future__ import annotations

import os
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Mapping

from apps.api_server.services.cline_live_matrix_fixtures import (
    build_live_matrix_fixture,
)
from apps.api_server.services.cline_live_matrix_selection import (
    DEFAULT_TOP_RANKED_LANGUAGE_COUNT,
    build_cline_live_matrix_artifacts,
)
from apps.api_server.services.cline_live_run_proof import collect_live_run_proof
from apps.api_server.services.cline_proof_common import (
    CLINE_PROOFS_DIR,
    artifact_relative_path,
    build_proof_context,
    create_artifact_provenance,
    repo_root,
    write_json,
)

LIVE_MATRIX_RESULTS_PATH = CLINE_PROOFS_DIR / "live_matrix_results.json"
LIVE_MATRIX_RUNS_DIR = CLINE_PROOFS_DIR / "live_matrix_runs"
# The live matrix uses the local proof runner, which boots its own isolated
# runtime and proof provider instead of requiring an external agent-core URL or
# remote model key.
REQUIRED_LIVE_ENVIRONMENT_KEYS: tuple[str, ...] = ()
OPTIONAL_LIVE_ENVIRONMENT_KEYS = (
    "ANTHROPIC_API_KEY",
    "ALGENTA_API_KEY",
    "DE_API_KEY",
)
LiveRunCollector = Callable[..., dict[str, Any]]


def _environment_status(env: Mapping[str, str | None]) -> dict[str, bool]:
    keys = (*REQUIRED_LIVE_ENVIRONMENT_KEYS, *OPTIONAL_LIVE_ENVIRONMENT_KEYS)
    return {key.lower(): bool(env.get(key)) for key in keys}


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or "language"


def _usage_value(payload: dict[str, Any], *aliases: str) -> int:
    for alias in aliases:
        value = payload.get(alias)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
    return 0


def _normalize_usage(proof_payload: dict[str, Any]) -> dict[str, int]:
    usage_payload = proof_payload.get("usage")
    if not isinstance(usage_payload, dict):
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
        }
    nested_usage = usage_payload.get("usage")
    metrics = nested_usage if isinstance(nested_usage, dict) else usage_payload
    return {
        "input_tokens": _usage_value(metrics, "inputTokens", "input_tokens"),
        "output_tokens": _usage_value(metrics, "outputTokens", "output_tokens"),
        "cache_read_tokens": _usage_value(metrics, "cacheReadTokens", "cache_read_tokens"),
        "cache_write_tokens": _usage_value(metrics, "cacheWriteTokens", "cache_write_tokens"),
    }


def _engine_call_counts(proof_payload: dict[str, Any]) -> dict[str, int]:
    engine_requests = proof_payload.get("engine_requests")
    if not isinstance(engine_requests, dict):
        return {"triage": 0, "graph_query": 0, "simulate_patch": 0}
    return {
        "triage": int(engine_requests.get("triage_calls", 0) or 0),
        "graph_query": int(engine_requests.get("graph_query_calls", 0) or 0),
        "simulate_patch": int(engine_requests.get("simulate_patch_calls", 0) or 0),
    }


def _tool_call_counts(proof_payload: dict[str, Any]) -> dict[str, int]:
    tool_calls = proof_payload.get("tool_calls")
    if not isinstance(tool_calls, dict):
        return {}
    tool_calls_by_name = tool_calls.get("tool_calls_by_name")
    if not isinstance(tool_calls_by_name, dict):
        return {}
    counts: dict[str, int] = {}
    for name, metadata in tool_calls_by_name.items():
        if not isinstance(name, str) or not isinstance(metadata, dict):
            continue
        count = metadata.get("count")
        if isinstance(count, int) and not isinstance(count, bool):
            counts[name] = count
    return counts


def _build_result_entry(
    *,
    root: Path,
    selection_entry: dict[str, Any],
    target_file: str,
    latency_seconds: float,
    proof_payload: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    usage = _normalize_usage(proof_payload or {})
    backend = (
        proof_payload.get("runtime_manifest", {}).get("backend", {})
        if isinstance(proof_payload, dict)
        else {}
    )
    gate = proof_payload.get("gate", {}) if isinstance(proof_payload, dict) else {}
    tool_calls = proof_payload.get("tool_calls", {}) if isinstance(proof_payload, dict) else {}
    return {
        "language": selection_entry["language"],
        "rank": selection_entry["rank"],
        "adapter_family": selection_entry["adapter_family"],
        "selection_reason": selection_entry["selection_reason"],
        "status": proof_payload.get("status") if isinstance(proof_payload, dict) else "failed",
        "target_file": target_file,
        "latency_seconds": round(latency_seconds, 3),
        "session_id": proof_payload.get("session_id") if isinstance(proof_payload, dict) else None,
        "agent_run_id": proof_payload.get("agent_run_id") if isinstance(proof_payload, dict) else None,
        "terminal_state": (
            proof_payload.get("terminal_state") if isinstance(proof_payload, dict) else None
        ),
        "provider": backend.get("provider") if isinstance(backend, dict) else None,
        "model": backend.get("model") if isinstance(backend, dict) else None,
        "usage": usage,
        "tool_calls_by_name": _tool_call_counts(proof_payload or {}),
        "engine_calls_by_name": _engine_call_counts(proof_payload or {}),
        "govern_hook_status": (
            tool_calls.get("govern_hook", {}).get("status")
            if isinstance(tool_calls, dict)
            else None
        ),
        "gate_terminal_state": gate.get("terminal_state") if isinstance(gate, dict) else None,
        "gate_apply_allowed": gate.get("apply_allowed") if isinstance(gate, dict) else None,
        "artifact_path": (
            artifact_relative_path(root, root / proof_payload["artifact_path"])
            if isinstance(proof_payload, dict) and isinstance(proof_payload.get("artifact_path"), str)
            else None
        ),
        "error": error,
    }


def _execute_live_matrix_runs(
    *,
    root: Path,
    selection_entries: list[dict[str, Any]],
    max_languages: int | None,
    live_run_collector: LiveRunCollector | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    if max_languages is not None and max_languages <= 0:
        raise ValueError("max_languages must be positive when provided")
    collector = collect_live_run_proof if live_run_collector is None else live_run_collector
    selected_entries = selection_entries[:max_languages] if max_languages is not None else selection_entries
    results: list[dict[str, Any]] = []
    blockers: list[str] = []
    for entry in selected_entries:
        language = entry["language"]
        rank = int(entry["rank"])
        fixture = build_live_matrix_fixture(language=language, rank=rank)
        started_at = time.perf_counter()
        output_path = root / LIVE_MATRIX_RUNS_DIR / f"{rank:03d}-{_slug(language)}.json"
        try:
            proof_payload = collector(
                root=root,
                output_path=output_path,
                target_file=fixture.target_file,
                language=language,
                scenario_label=f"live-matrix-{rank:03d}-{_slug(language)}",
            )
            latency_seconds = time.perf_counter() - started_at
            results.append(
                _build_result_entry(
                    root=root,
                    selection_entry=entry,
                    target_file=fixture.target_file,
                    latency_seconds=latency_seconds,
                    proof_payload=proof_payload,
                )
            )
            if proof_payload.get("status") != "passed":
                blockers.append(
                    f"live matrix run failed for {language}: {proof_payload.get('terminal_state')}"
                )
        except Exception as exc:  # noqa: BLE001
            latency_seconds = time.perf_counter() - started_at
            blockers.append(f"live matrix run failed for {language}: {type(exc).__name__}: {exc}")
            results.append(
                _build_result_entry(
                    root=root,
                    selection_entry=entry,
                    target_file=fixture.target_file,
                    latency_seconds=latency_seconds,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
    if max_languages is not None and len(results) < len(selection_entries):
        blockers.append(
            f"live matrix execution limited to {len(results)} of {len(selection_entries)} selected languages"
        )
    return results, blockers


def build_live_matrix_results_artifact(
    *,
    root: Path | str | None = None,
    env: Mapping[str, str | None] | None = None,
    top_ranked_language_count: int = DEFAULT_TOP_RANKED_LANGUAGE_COUNT,
    execute: bool = False,
    max_languages: int | None = None,
    live_run_collector: LiveRunCollector | None = None,
) -> dict[str, Any]:
    resolved_root = repo_root() if root is None else Path(root).resolve()
    context = build_proof_context(resolved_root)
    selection_artifacts = build_cline_live_matrix_artifacts(
        root=resolved_root,
        top_ranked_language_count=top_ranked_language_count,
    )
    resolved_env = os.environ if env is None else env
    env_status = _environment_status(resolved_env)
    selection_entries = selection_artifacts.live_matrix_selection_payload["selected_live_languages"]
    if execute:
        results, blockers = _execute_live_matrix_runs(
            root=resolved_root,
            selection_entries=selection_entries,
            max_languages=max_languages,
            live_run_collector=live_run_collector,
        )
        executed_run_count = len(results)
        failed_run_count = sum(1 for result in results if result["status"] != "passed")
        status = (
            "failed"
            if failed_run_count
            else (
                "passed"
                if executed_run_count == len(selection_entries)
                else "partial_execution"
            )
        )
    else:
        status = "ready_for_execution"
        blockers = []
        results = []
        executed_run_count = 0
        failed_run_count = 0
    live_progress_percent = round(
        (executed_run_count / len(selection_entries)) * 100.0,
        2,
    ) if selection_entries else 100.0
    payload = {
        **create_artifact_provenance(
            context,
            run_id="live_matrix_results",
            schema_version="cline-live-matrix-results/v1",
        ),
        "status": status,
        "execution_mode": "local_proof" if execute else "inventory_only",
        "selected_language_count": len(selection_entries),
        "selected_live_languages": selection_entries,
        "environment_status": env_status,
        "required_environment": list(REQUIRED_LIVE_ENVIRONMENT_KEYS),
        "optional_environment": list(OPTIONAL_LIVE_ENVIRONMENT_KEYS),
        "blockers": blockers,
        "executed_run_count": executed_run_count,
        "failed_run_count": failed_run_count,
        "live_progress_percent": live_progress_percent,
        "results": results,
    }
    write_json(resolved_root / LIVE_MATRIX_RESULTS_PATH, payload)
    return payload
