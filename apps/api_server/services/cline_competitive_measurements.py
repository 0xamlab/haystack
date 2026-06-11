from __future__ import annotations

from pathlib import Path
from typing import Any

from apps.api_server.services.cline_proof_common import (
    CLINE_PROOFS_DIR,
    artifact_relative_path,
    build_proof_context,
    create_artifact_provenance,
    repo_root,
    write_json,
)


CURSOR_MCP_COMPARISON_PATH = CLINE_PROOFS_DIR / "cursor_mcp_comparison.json"
WARM_CACHE_COMPARISON_PATH = CLINE_PROOFS_DIR / "warm_cache_comparison.json"


def _required_mapping(payload: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = payload.get(field_name)
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return value


def _required_string(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _required_int(payload: dict[str, Any], field_name: str) -> int:
    value = payload.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _required_number(payload: dict[str, Any], *aliases: str) -> float:
    for alias in aliases:
        value = payload.get(alias)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    joined = ", ".join(aliases)
    raise ValueError(f"one of {joined} must be numeric")


def _optional_mapping(payload: dict[str, Any], *aliases: str) -> dict[str, Any] | None:
    for alias in aliases:
        value = payload.get(alias)
        if isinstance(value, dict):
            return value
    return None


def _extract_usage_metrics(payload: dict[str, Any]) -> dict[str, float]:
    usage_source = _optional_mapping(
        payload,
        "usage",
    )
    if usage_source is None:
        usage_source = _optional_mapping(_required_mapping(payload, "agent"), "usage")
    input_tokens = _required_number(usage_source, "input_tokens", "inputTokens")
    output_tokens = _required_number(usage_source, "output_tokens", "outputTokens")
    cache_read_tokens = _required_number(
        usage_source,
        "cache_read_tokens",
        "cacheReadTokens",
    )
    cache_write_tokens = _required_number(
        usage_source,
        "cache_write_tokens",
        "cacheWriteTokens",
    )
    total_tokens = input_tokens + output_tokens
    billed_input_tokens = max(input_tokens - cache_read_tokens, 0.0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
        "total_tokens": total_tokens,
        "billed_input_tokens": billed_input_tokens,
    }


def _extract_raw_token_observations(payload: dict[str, Any]) -> dict[str, Any] | None:
    return _optional_mapping(
        payload,
        "event_derived_usage",
        "token_observations",
        "raw_event_usage",
    )


def _build_benchmark_metadata(g0_payload: dict[str, Any]) -> dict[str, Any]:
    task_count = g0_payload.get("task_count")
    if task_count is None:
        fixtures = g0_payload.get("fixtures")
        reps = g0_payload.get("reps")
        if isinstance(fixtures, list) and isinstance(reps, int) and not isinstance(reps, bool):
            task_count = len(fixtures) * reps
        else:
            raise ValueError("g0_payload must include task_count or fixtures/reps")
    return {
        "benchmark_suite": _required_string(g0_payload, "benchmark_suite"),
        "benchmark_suite_hash": _required_string(g0_payload, "benchmark_suite_hash"),
        "benchmark_fixture_hash": _required_string(
            g0_payload,
            "benchmark_fixture_hash",
        ),
        "prompt_family": _required_string(g0_payload, "prompt_family"),
        "provider": _required_string(g0_payload, "provider"),
        "model": _required_string(g0_payload, "model"),
        "provider_model_class": _required_string(
            g0_payload,
            "provider_model_class",
        ),
        "tool_policy_profile": _required_string(g0_payload, "tool_policy_profile"),
        "max_iterations": _required_int(g0_payload, "max_iterations"),
        "timeout_seconds": _required_int(g0_payload, "timeout_seconds"),
        "task_count": int(task_count),
        "usage_source": _required_string(g0_payload, "usage_source"),
    }


def build_cursor_mcp_comparison_artifact(
    *,
    g0_payload: dict[str, Any],
    direct_payload: dict[str, Any],
    mcp_payload: dict[str, Any],
    direct_wall_time_seconds: float,
    mcp_wall_time_seconds: float,
    root: Path | None = None,
    output_path: Path | None = None,
    direct_source_path: Path | None = None,
    mcp_source_path: Path | None = None,
) -> dict[str, Any]:
    if direct_wall_time_seconds <= 0 or mcp_wall_time_seconds <= 0:
        raise ValueError("wall times must be > 0")
    resolved_root = repo_root() if root is None else Path(root).resolve()
    context = build_proof_context(resolved_root)
    metadata = _build_benchmark_metadata(g0_payload)
    direct_usage = _extract_usage_metrics(direct_payload)
    mcp_usage = _extract_usage_metrics(mcp_payload)
    artifact = {
        **create_artifact_provenance(
            context,
            run_id="cursor_mcp_comparison",
            schema_version="cline-cursor-mcp-comparison/v1",
        ),
        **metadata,
        "direct_source_artifact": (
            artifact_relative_path(resolved_root, direct_source_path)
            if direct_source_path is not None
            else None
        ),
        "mcp_source_artifact": (
            artifact_relative_path(resolved_root, mcp_source_path)
            if mcp_source_path is not None
            else None
        ),
        "direct_wall_time_seconds": float(direct_wall_time_seconds),
        "mcp_wall_time_seconds": float(mcp_wall_time_seconds),
        "direct_total_tokens": direct_usage["total_tokens"],
        "mcp_total_tokens": mcp_usage["total_tokens"],
        "direct_usage": direct_usage,
        "mcp_usage": mcp_usage,
        "direct_token_observations": _extract_raw_token_observations(direct_payload),
        "mcp_token_observations": _extract_raw_token_observations(mcp_payload),
    }
    destination = (
        resolved_root / CURSOR_MCP_COMPARISON_PATH
        if output_path is None
        else Path(output_path).resolve()
    )
    write_json(destination, artifact)
    return artifact


def build_warm_cache_comparison_artifact(
    *,
    g0_payload: dict[str, Any],
    cold_payload: dict[str, Any],
    warm_payload: dict[str, Any],
    root: Path | None = None,
    output_path: Path | None = None,
    cold_source_path: Path | None = None,
    warm_source_path: Path | None = None,
) -> dict[str, Any]:
    resolved_root = repo_root() if root is None else Path(root).resolve()
    context = build_proof_context(resolved_root)
    metadata = _build_benchmark_metadata(g0_payload)
    cold_usage = _extract_usage_metrics(cold_payload)
    warm_usage = _extract_usage_metrics(warm_payload)
    artifact = {
        **create_artifact_provenance(
            context,
            run_id="warm_cache_comparison",
            schema_version="cline-warm-cache-comparison/v1",
        ),
        **metadata,
        "cold_source_artifact": (
            artifact_relative_path(resolved_root, cold_source_path)
            if cold_source_path is not None
            else None
        ),
        "warm_source_artifact": (
            artifact_relative_path(resolved_root, warm_source_path)
            if warm_source_path is not None
            else None
        ),
        "cold_billed_input_tokens": cold_usage["billed_input_tokens"],
        "warm_billed_input_tokens": warm_usage["billed_input_tokens"],
        "warm_cache_read_tokens": warm_usage["cache_read_tokens"],
        "cold_usage": cold_usage,
        "warm_usage": warm_usage,
        "cold_token_observations": _extract_raw_token_observations(cold_payload),
        "warm_token_observations": _extract_raw_token_observations(warm_payload),
    }
    destination = (
        resolved_root / WARM_CACHE_COMPARISON_PATH
        if output_path is None
        else Path(output_path).resolve()
    )
    write_json(destination, artifact)
    return artifact
