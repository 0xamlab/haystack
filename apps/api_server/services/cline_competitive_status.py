from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from apps.api_server.services.cline_competitive_report import (
    COMPETITIVE_REPORT_PATH,
    DEFAULT_RESOLUTION_THRESHOLD_ABSOLUTE_PP,
    DEFAULT_RESOLUTION_THRESHOLD_MODE,
)
from apps.api_server.services.cline_proof_common import (
    artifact_relative_path,
    build_proof_context,
    create_artifact_provenance,
    read_json,
    repo_root,
    write_json,
)

REQUIRED_COMPETITIVE_ENVIRONMENT_KEYS = ("ANTHROPIC_API_KEY",)
OPTIONAL_COMPETITIVE_ENVIRONMENT_KEYS = (
    "ALGENTA_API_KEY",
    "DE_API_KEY",
)


def _environment_status(env: Mapping[str, str | None]) -> dict[str, bool]:
    keys = (*REQUIRED_COMPETITIVE_ENVIRONMENT_KEYS, *OPTIONAL_COMPETITIVE_ENVIRONMENT_KEYS)
    return {key.lower(): bool(env.get(key)) for key in keys}


def _optional_object(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _string_or_none(payload: dict[str, Any] | None, field_name: str) -> str | None:
    if payload is None:
        return None
    value = payload.get(field_name)
    return value if isinstance(value, str) and value.strip() else None


def _int_or_zero(payload: dict[str, Any] | None, field_name: str) -> int:
    if payload is None:
        return 0
    value = payload.get(field_name)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return 0


def build_blocked_competitive_experience_report(
    *,
    root: Path | str | None = None,
    env: Mapping[str, str | None] | None = None,
    output_path: Path | str | None = None,
    g0_artifact_path: Path | str | None = None,
    cursor_mcp_artifact_path: Path | str | None = None,
    warm_cache_artifact_path: Path | str | None = None,
) -> dict[str, Any]:
    resolved_root = repo_root() if root is None else Path(root).resolve()
    context = build_proof_context(resolved_root)
    resolved_env = os.environ if env is None else env
    env_status = _environment_status(resolved_env)
    missing_env = [
        key for key in REQUIRED_COMPETITIVE_ENVIRONMENT_KEYS if not resolved_env.get(key)
    ]

    resolved_g0_path = (
        Path(g0_artifact_path).resolve() if g0_artifact_path is not None else None
    )
    resolved_cursor_path = (
        Path(cursor_mcp_artifact_path).resolve()
        if cursor_mcp_artifact_path is not None
        else None
    )
    resolved_warm_path = (
        Path(warm_cache_artifact_path).resolve()
        if warm_cache_artifact_path is not None
        else None
    )
    g0_payload = _optional_object(resolved_g0_path)

    artifact_paths = {
        "g0_artifact": resolved_g0_path,
        "cursor_mcp_artifact": resolved_cursor_path,
        "warm_cache_artifact": resolved_warm_path,
    }
    source_validation_errors = [
        f"missing benchmark artifact path: {label}"
        for label, path in artifact_paths.items()
        if path is None
    ]
    source_validation_errors.extend(
        f"missing benchmark artifact file: {path}"
        for path in artifact_paths.values()
        if path is not None and not path.exists()
    )

    if missing_env:
        status = "blocked_missing_live_runtime"
        blockers = [
            f"missing required live environment variable: {key}" for key in missing_env
        ]
    elif source_validation_errors:
        status = "blocked_missing_benchmark_artifacts"
        blockers = list(source_validation_errors)
    else:
        status = "ready_for_report_generation"
        blockers = []

    benchmark_suite = _string_or_none(g0_payload, "benchmark_suite") or "g0_token_benchmark"
    benchmark_suite_hash = _string_or_none(g0_payload, "benchmark_suite_hash")
    benchmark_fixture_hash = _string_or_none(g0_payload, "benchmark_fixture_hash")
    provider = _string_or_none(g0_payload, "provider")
    model = _string_or_none(g0_payload, "model")
    provider_model_class = _string_or_none(g0_payload, "provider_model_class")
    usage_source = _string_or_none(g0_payload, "usage_source")
    task_count = _int_or_zero(g0_payload, "task_count")

    payload = {
        **create_artifact_provenance(
            context,
            run_id="competitive_experience_report",
            schema_version="competitive-experience-report/v1",
        ),
        "status": status,
        "benchmark_suite": benchmark_suite,
        "benchmark_suite_hash": benchmark_suite_hash,
        "benchmark_fixture_hash": benchmark_fixture_hash,
        "baseline_name": "vanilla_agentic",
        "baseline_artifact": (
            artifact_relative_path(resolved_root, resolved_g0_path)
            if resolved_g0_path is not None and resolved_g0_path.exists()
            else None
        ),
        "optimized_artifact": (
            artifact_relative_path(resolved_root, resolved_g0_path)
            if resolved_g0_path is not None and resolved_g0_path.exists()
            else None
        ),
        "cursor_mcp_artifact": (
            artifact_relative_path(resolved_root, resolved_cursor_path)
            if resolved_cursor_path is not None and resolved_cursor_path.exists()
            else None
        ),
        "warm_cache_artifact": (
            artifact_relative_path(resolved_root, resolved_warm_path)
            if resolved_warm_path is not None and resolved_warm_path.exists()
            else None
        ),
        "provider": provider,
        "model": model,
        "provider_model_class": provider_model_class,
        "usage_source": usage_source,
        "task_count": task_count,
        "eligible_task_count": 0,
        "resolved_count": 0,
        "resolution_rate": None,
        "best_verified_resolution_rate": None,
        "delta_pp": None,
        "resolution_threshold_absolute_pp": (
            float(g0_payload["resolution_threshold_absolute_pp"])
            if g0_payload is not None and "resolution_threshold_absolute_pp" in g0_payload
            else DEFAULT_RESOLUTION_THRESHOLD_ABSOLUTE_PP
        ),
        "resolution_threshold_mode": (
            str(g0_payload["resolution_threshold_mode"])
            if g0_payload is not None and "resolution_threshold_mode" in g0_payload
            else DEFAULT_RESOLUTION_THRESHOLD_MODE
        ),
        "variance_exception_accepted": False,
        "variance_exception_reason": None,
        "tokens_vs_vanilla_agentic_ratio": None,
        "cursor_mcp_wall_time_overhead_ratio": None,
        "cursor_mcp_token_overhead_ratio": None,
        "warm_billed_input_token_ratio": None,
        "warm_cache_read_tokens_positive": False,
        "validation_errors": [],
        "eligibility_validation_errors": [],
        "source_validation_errors": source_validation_errors,
        "gate_results": {
            "resolution_within_5pp": False,
            "tokens_at_or_below_quarter": False,
            "cursor_wall_overhead_within_10pct": False,
            "cursor_token_overhead_within_5pct": False,
            "warm_cache_positive_and_billed_ratio_within_70pct": False,
        },
        "environment_status": env_status,
        "required_environment": list(REQUIRED_COMPETITIVE_ENVIRONMENT_KEYS),
        "optional_environment": list(OPTIONAL_COMPETITIVE_ENVIRONMENT_KEYS),
        "blockers": blockers,
        "metrics_available": False,
        "eligibility_rules": (
            g0_payload.get("eligibility_rules", {}) if g0_payload is not None else {}
        ),
    }
    resolved_output_path = (
        resolved_root / COMPETITIVE_REPORT_PATH
        if output_path is None
        else Path(output_path).resolve()
    )
    write_json(resolved_output_path, payload)
    payload["artifact_path"] = artifact_relative_path(resolved_root, resolved_output_path)
    return payload
