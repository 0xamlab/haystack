from __future__ import annotations

from pathlib import Path
from typing import Any

from apps.api_server.services.cline_proof_common import (
    CLINE_PROOFS_DIR,
    artifact_relative_path,
    build_proof_context,
    create_artifact_provenance,
    read_json,
    repo_root,
    validate_artifact_provenance,
    write_json,
)


COMPETITIVE_REPORT_PATH = CLINE_PROOFS_DIR / "competitive_experience_report.json"
COMPETITIVE_USAGE_SOURCE = "runtime_accumulated_usage"
DEFAULT_RESOLUTION_THRESHOLD_ABSOLUTE_PP = 5.0
DEFAULT_RESOLUTION_THRESHOLD_MODE = "absolute_percentage_points"
REQUIRED_ELIGIBILITY_RULE_FIELDS = (
    "eligible_task",
    "excluded_task",
    "attempt",
    "rerun_policy",
    "timeout_policy",
    "partial_success",
    "human_intervention",
    "benchmark_fixture_hash",
)


def _required_mapping(payload: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = payload.get(field_name)
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return value


def _required_string(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _required_number(payload: dict[str, Any], field_name: str) -> float:
    value = payload.get(field_name)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    return float(value)


def _required_int(payload: dict[str, Any], field_name: str) -> int:
    value = payload.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _required_mapping_or_default(
    payload: dict[str, Any],
    field_name: str,
    *,
    default: dict[str, Any],
) -> dict[str, Any]:
    value = payload.get(field_name)
    if value is None:
        return default
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return value


def _default_eligibility_rules(
    *,
    benchmark_fixture_hash: str,
    timeout_seconds: int,
) -> dict[str, str]:
    return {
        "eligible_task": "task included in the frozen benchmark suite",
        "excluded_task": "task omitted from the frozen benchmark suite",
        "attempt": "single benchmark attempt per fixture/rep",
        "rerun_policy": "no reruns unless benchmark fixture changes",
        "timeout_policy": f"{timeout_seconds}s fixed timeout",
        "partial_success": "counts as unresolved",
        "human_intervention": "forbidden",
        "benchmark_fixture_hash": benchmark_fixture_hash,
    }


def _validate_eligibility_rules(
    eligibility_rules: dict[str, Any],
    *,
    benchmark_fixture_hash: str,
) -> list[str]:
    errors: list[str] = []
    for field_name in REQUIRED_ELIGIBILITY_RULE_FIELDS:
        value = eligibility_rules.get(field_name)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"eligibility_rules.{field_name} must be a non-empty string")
    if eligibility_rules.get("benchmark_fixture_hash") != benchmark_fixture_hash:
        errors.append(
            "eligibility_rules.benchmark_fixture_hash differs from benchmark_fixture_hash"
        )
    return errors


def _validate_source_artifact_provenance(
    *,
    context: Any,
    payload: dict[str, Any],
    artifact_path: Path,
    allow_dirty_tree: bool,
) -> list[str]:
    return validate_artifact_provenance(
        payload=payload,
        context=context,
        artifact_path=artifact_path,
        allow_dirty_tree=allow_dirty_tree,
    )


def _resolution_rate(run: dict[str, Any], *, field_prefix: str) -> float:
    if "resolution_rate" in run:
        return _required_number(run, "resolution_rate")
    resolved_count = _required_int(run, "resolved_count")
    eligible_task_count = _required_int(run, "eligible_task_count")
    if eligible_task_count <= 0:
        raise ValueError(f"{field_prefix}.eligible_task_count must be > 0")
    return resolved_count / eligible_task_count


def _validate_metadata_match(
    baseline: dict[str, Any],
    optimized: dict[str, Any],
    cursor_comparison: dict[str, Any],
    warm_cache: dict[str, Any],
    *,
    benchmark_suite_hash: str,
    benchmark_fixture_hash: str,
) -> list[str]:
    errors: list[str] = []
    comparable_fields = (
        "prompt_family",
        "provider",
        "model",
        "provider_model_class",
        "tool_policy_profile",
        "max_iterations",
        "timeout_seconds",
        "task_count",
        "usage_source",
    )
    for field_name in comparable_fields:
        baseline_value = baseline.get(field_name)
        optimized_value = optimized.get(field_name)
        if baseline_value != optimized_value:
            errors.append(
                f"baseline and optimized {field_name} differ: {baseline_value!r} != {optimized_value!r}"
            )
        cursor_value = cursor_comparison.get(field_name)
        if cursor_value != baseline_value:
            errors.append(
                f"cursor comparison {field_name} differs from baseline: {cursor_value!r} != {baseline_value!r}"
            )
        warm_value = warm_cache.get(field_name)
        if warm_value != baseline_value:
            errors.append(
                f"warm cache {field_name} differs from baseline: {warm_value!r} != {baseline_value!r}"
            )
    for label, payload in (
        ("baseline", baseline),
        ("optimized", optimized),
        ("cursor comparison", cursor_comparison),
        ("warm cache", warm_cache),
    ):
        if payload.get("benchmark_suite_hash") != benchmark_suite_hash:
            errors.append(
                f"{label} benchmark_suite_hash differs: {payload.get('benchmark_suite_hash')!r} != {benchmark_suite_hash!r}"
            )
        if payload.get("benchmark_fixture_hash") != benchmark_fixture_hash:
            errors.append(
                f"{label} benchmark_fixture_hash differs: {payload.get('benchmark_fixture_hash')!r} != {benchmark_fixture_hash!r}"
            )
    return errors


def build_competitive_input_from_g0_artifact(
    *,
    g0_payload: dict[str, Any],
    cursor_mcp_comparison: dict[str, Any],
    warm_cache_comparison: dict[str, Any],
    g0_source_path: Path | None = None,
    cursor_mcp_source_path: Path | None = None,
    warm_cache_source_path: Path | None = None,
    root: Path | None = None,
    allow_dirty_tree: bool = False,
) -> dict[str, Any]:
    aggregates = _required_mapping(g0_payload, "aggregates")
    baseline = aggregates.get("A")
    optimized = aggregates.get("C")
    if not isinstance(baseline, dict) or not isinstance(optimized, dict):
        raise ValueError("g0_payload.aggregates must include both A and C arms")
    if int(baseline.get("n", 0) or 0) <= 0 or int(optimized.get("n", 0) or 0) <= 0:
        raise ValueError("g0_payload.aggregates A and C arms must both contain benchmark data")
    benchmark_suite_hash = _required_string(g0_payload, "benchmark_suite_hash")
    benchmark_fixture_hash = _required_string(
        g0_payload,
        "benchmark_fixture_hash",
    )
    provider = _required_string(g0_payload, "provider")
    model = _required_string(g0_payload, "model")
    provider_model_class = _required_string(g0_payload, "provider_model_class")
    prompt_family = _required_string(g0_payload, "prompt_family")
    tool_policy_profile = _required_string(g0_payload, "tool_policy_profile")
    max_iterations = _required_int(g0_payload, "max_iterations")
    timeout_seconds = _required_int(g0_payload, "timeout_seconds")
    task_count = _required_int(g0_payload, "task_count")
    usage_source = _required_string(g0_payload, "usage_source")
    fixtures = g0_payload.get("fixtures")
    if not isinstance(fixtures, list):
        raise ValueError("g0_payload.fixtures must be a list")

    if task_count != len(fixtures) * _required_int(g0_payload, "reps"):
        raise ValueError("g0_payload.task_count must equal len(fixtures) * reps")
    baseline_resolution_rate = _resolution_rate(baseline, field_prefix="aggregates.A")
    eligibility_rules = _required_mapping_or_default(
        g0_payload,
        "eligibility_rules",
        default=_default_eligibility_rules(
            benchmark_fixture_hash=benchmark_fixture_hash,
            timeout_seconds=timeout_seconds,
        ),
    )

    source_validation_errors: list[str] = []
    if (
        g0_source_path is not None
        or cursor_mcp_source_path is not None
        or warm_cache_source_path is not None
    ):
        resolved_root = repo_root() if root is None else Path(root).resolve()
        context = build_proof_context(resolved_root)
        for label, payload, source_path in (
            ("g0_artifact", g0_payload, g0_source_path),
            ("cursor_mcp_artifact", cursor_mcp_comparison, cursor_mcp_source_path),
            ("warm_cache_artifact", warm_cache_comparison, warm_cache_source_path),
        ):
            if source_path is None:
                source_validation_errors.append(f"{label} path is required")
                continue
            source_validation_errors.extend(
                _validate_source_artifact_provenance(
                    context=context,
                    payload=payload,
                    artifact_path=Path(source_path).resolve(),
                    allow_dirty_tree=allow_dirty_tree,
                )
            )

    def _run_payload(name: str, aggregate: dict[str, Any], resolved_count: int) -> dict[str, Any]:
        return {
            "name": name,
            "benchmark_suite_hash": benchmark_suite_hash,
            "benchmark_fixture_hash": benchmark_fixture_hash,
            "prompt_family": prompt_family,
            "provider": provider,
            "model": model,
            "provider_model_class": provider_model_class,
            "tool_policy_profile": tool_policy_profile,
            "max_iterations": max_iterations,
            "timeout_seconds": timeout_seconds,
            "task_count": task_count,
            "usage_source": usage_source,
            "eligible_task_count": aggregate["n"],
            "resolved_count": resolved_count,
            "resolution_rate": _resolution_rate(aggregate, field_prefix=name),
            "mean_total_tokens": aggregate["mean_total_tokens"],
        }

    baseline_resolved = round(baseline_resolution_rate * baseline["n"])
    optimized_resolution_rate = _resolution_rate(optimized, field_prefix="aggregates.C")
    optimized_resolved = round(optimized_resolution_rate * optimized["n"])
    return {
        "schema_version": "cline-competitive-benchmark-input/v1",
        "benchmark_suite": _required_string(g0_payload, "benchmark_suite"),
        "benchmark_suite_hash": benchmark_suite_hash,
        "benchmark_fixture_hash": benchmark_fixture_hash,
        "provider_model_class": provider_model_class,
        "usage_source": usage_source,
        "eligibility_rules": eligibility_rules,
        "baseline_name": "vanilla_agentic",
        "baseline": _run_payload("vanilla_agentic", baseline, baseline_resolved),
        "baseline_artifact": str(Path(g0_source_path).resolve()) if g0_source_path is not None else None,
        "optimized_name": "verified_agentic",
        "optimized": _run_payload("verified_agentic", optimized, optimized_resolved),
        "optimized_artifact": str(Path(g0_source_path).resolve()) if g0_source_path is not None else None,
        "best_verified_resolution_rate": baseline_resolution_rate,
        "cursor_mcp_comparison": cursor_mcp_comparison,
        "cursor_mcp_artifact": (
            str(Path(cursor_mcp_source_path).resolve())
            if cursor_mcp_source_path is not None
            else None
        ),
        "warm_cache_comparison": warm_cache_comparison,
        "warm_cache_artifact": (
            str(Path(warm_cache_source_path).resolve())
            if warm_cache_source_path is not None
            else None
        ),
        "source_validation_errors": source_validation_errors,
        "resolution_threshold_absolute_pp": float(
            g0_payload.get(
                "resolution_threshold_absolute_pp",
                DEFAULT_RESOLUTION_THRESHOLD_ABSOLUTE_PP,
            )
        ),
        "resolution_threshold_mode": str(
            g0_payload.get(
                "resolution_threshold_mode",
                DEFAULT_RESOLUTION_THRESHOLD_MODE,
            )
        ),
        "variance_exception_accepted": False,
        "variance_exception_reason": None,
    }


def build_competitive_input_from_artifact_paths(
    *,
    g0_artifact_path: Path | str,
    cursor_mcp_artifact_path: Path | str,
    warm_cache_artifact_path: Path | str,
    root: Path | None = None,
    allow_dirty_tree: bool = False,
) -> dict[str, Any]:
    resolved_g0_path = Path(g0_artifact_path).resolve()
    resolved_cursor_path = Path(cursor_mcp_artifact_path).resolve()
    resolved_warm_path = Path(warm_cache_artifact_path).resolve()
    return build_competitive_input_from_g0_artifact(
        g0_payload=load_json(resolved_g0_path),
        cursor_mcp_comparison=load_json(resolved_cursor_path),
        warm_cache_comparison=load_json(resolved_warm_path),
        g0_source_path=resolved_g0_path,
        cursor_mcp_source_path=resolved_cursor_path,
        warm_cache_source_path=resolved_warm_path,
        root=root,
        allow_dirty_tree=allow_dirty_tree,
    )


def build_competitive_experience_report(
    *,
    benchmark_input: dict[str, Any],
    root: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    resolved_root = repo_root() if root is None else Path(root).resolve()
    context = build_proof_context(resolved_root)
    benchmark_suite = _required_string(benchmark_input, "benchmark_suite")
    benchmark_suite_hash = _required_string(benchmark_input, "benchmark_suite_hash")
    benchmark_fixture_hash = _required_string(benchmark_input, "benchmark_fixture_hash")
    baseline_name = _required_string(benchmark_input, "baseline_name")
    baseline = _required_mapping(benchmark_input, "baseline")
    optimized = _required_mapping(benchmark_input, "optimized")
    cursor_comparison = _required_mapping(benchmark_input, "cursor_mcp_comparison")
    warm_cache = _required_mapping(benchmark_input, "warm_cache_comparison")
    provider_model_class = _required_string(benchmark_input, "provider_model_class")
    usage_source = _required_string(benchmark_input, "usage_source")
    best_verified_resolution_rate = _required_number(
        benchmark_input,
        "best_verified_resolution_rate",
    )
    resolution_threshold_absolute_pp = _required_number(
        benchmark_input,
        "resolution_threshold_absolute_pp",
    )
    resolution_threshold_mode = _required_string(
        benchmark_input,
        "resolution_threshold_mode",
    )
    variance_exception_accepted = bool(benchmark_input.get("variance_exception_accepted", False))
    variance_exception_reason = benchmark_input.get("variance_exception_reason")
    if variance_exception_reason is not None and (
        not isinstance(variance_exception_reason, str) or not variance_exception_reason.strip()
    ):
        raise ValueError("variance_exception_reason must be a non-empty string when provided")
    source_validation_errors = benchmark_input.get("source_validation_errors", [])
    if not isinstance(source_validation_errors, list):
        raise ValueError("source_validation_errors must be a list")
    if any(not isinstance(error, str) or not error for error in source_validation_errors):
        raise ValueError("source_validation_errors entries must be non-empty strings")
    eligibility_rules = _required_mapping_or_default(
        benchmark_input,
        "eligibility_rules",
        default=_default_eligibility_rules(
            benchmark_fixture_hash=benchmark_fixture_hash,
            timeout_seconds=_required_int(optimized, "timeout_seconds"),
        ),
    )
    eligibility_validation_errors = _validate_eligibility_rules(
        eligibility_rules,
        benchmark_fixture_hash=benchmark_fixture_hash,
    )

    validation_errors = _validate_metadata_match(
        baseline,
        optimized,
        cursor_comparison,
        warm_cache,
        benchmark_suite_hash=benchmark_suite_hash,
        benchmark_fixture_hash=benchmark_fixture_hash,
    )

    optimized_resolution_rate = _resolution_rate(optimized, field_prefix="optimized")
    baseline_mean_tokens = _required_number(baseline, "mean_total_tokens")
    optimized_mean_tokens = _required_number(optimized, "mean_total_tokens")
    if baseline_mean_tokens <= 0:
        raise ValueError("baseline.mean_total_tokens must be > 0")
    tokens_vs_vanilla_agentic_ratio = optimized_mean_tokens / baseline_mean_tokens

    direct_wall = _required_number(cursor_comparison, "direct_wall_time_seconds")
    mcp_wall = _required_number(cursor_comparison, "mcp_wall_time_seconds")
    direct_tokens = _required_number(cursor_comparison, "direct_total_tokens")
    mcp_tokens = _required_number(cursor_comparison, "mcp_total_tokens")
    if direct_wall <= 0:
        raise ValueError("cursor_mcp_comparison.direct_wall_time_seconds must be > 0")
    if direct_tokens <= 0:
        raise ValueError("cursor_mcp_comparison.direct_total_tokens must be > 0")
    cursor_mcp_wall_time_overhead_ratio = (mcp_wall - direct_wall) / direct_wall
    cursor_mcp_token_overhead_ratio = (mcp_tokens - direct_tokens) / direct_tokens

    cold_billed_input_tokens = _required_number(warm_cache, "cold_billed_input_tokens")
    warm_billed_input_tokens = _required_number(warm_cache, "warm_billed_input_tokens")
    warm_cache_read_tokens = _required_number(warm_cache, "warm_cache_read_tokens")
    if cold_billed_input_tokens <= 0:
        raise ValueError("warm_cache_comparison.cold_billed_input_tokens must be > 0")
    warm_billed_input_token_ratio = warm_billed_input_tokens / cold_billed_input_tokens

    delta_pp = (optimized_resolution_rate - best_verified_resolution_rate) * 100.0
    resolution_gate_passed = (
        delta_pp >= -resolution_threshold_absolute_pp or variance_exception_accepted
    )
    tokens_gate_passed = tokens_vs_vanilla_agentic_ratio <= 0.25
    cursor_wall_gate_passed = cursor_mcp_wall_time_overhead_ratio <= 0.10
    cursor_token_gate_passed = cursor_mcp_token_overhead_ratio <= 0.05
    warm_cache_gate_passed = warm_cache_read_tokens > 0 and warm_billed_input_token_ratio <= 0.70

    status = (
        "passed"
        if not validation_errors
        and not source_validation_errors
        and not eligibility_validation_errors
        and resolution_gate_passed
        and tokens_gate_passed
        and cursor_wall_gate_passed
        and cursor_token_gate_passed
        and warm_cache_gate_passed
        else "failed"
    )

    report = {
        **create_artifact_provenance(
            context,
            run_id="competitive_experience_report",
            schema_version="competitive-experience-report/v1",
        ),
        "status": status,
        "benchmark_suite": benchmark_suite,
        "benchmark_suite_hash": benchmark_suite_hash,
        "benchmark_fixture_hash": benchmark_fixture_hash,
        "baseline_name": baseline_name,
        "baseline_artifact": benchmark_input.get("baseline_artifact"),
        "optimized_artifact": benchmark_input.get("optimized_artifact"),
        "cursor_mcp_artifact": benchmark_input.get("cursor_mcp_artifact"),
        "warm_cache_artifact": benchmark_input.get("warm_cache_artifact"),
        "provider": _required_string(optimized, "provider"),
        "model": _required_string(optimized, "model"),
        "provider_model_class": provider_model_class,
        "usage_source": usage_source,
        "task_count": _required_int(optimized, "task_count"),
        "eligible_task_count": _required_int(optimized, "eligible_task_count"),
        "resolved_count": _required_int(optimized, "resolved_count"),
        "resolution_rate": optimized_resolution_rate,
        "best_verified_resolution_rate": best_verified_resolution_rate,
        "delta_pp": delta_pp,
        "resolution_threshold_absolute_pp": resolution_threshold_absolute_pp,
        "resolution_threshold_mode": resolution_threshold_mode,
        "variance_exception_accepted": variance_exception_accepted,
        "variance_exception_reason": variance_exception_reason,
        "tokens_vs_vanilla_agentic_ratio": tokens_vs_vanilla_agentic_ratio,
        "cursor_mcp_wall_time_overhead_ratio": cursor_mcp_wall_time_overhead_ratio,
        "cursor_mcp_token_overhead_ratio": cursor_mcp_token_overhead_ratio,
        "warm_billed_input_token_ratio": warm_billed_input_token_ratio,
        "warm_cache_read_tokens_positive": warm_cache_read_tokens > 0,
        "source_validation_errors": source_validation_errors,
        "eligibility_validation_errors": eligibility_validation_errors,
        "validation_errors": validation_errors,
        "gate_results": {
            "resolution_within_5pp": resolution_gate_passed,
            "tokens_at_or_below_quarter": tokens_gate_passed,
            "cursor_wall_overhead_within_10pct": cursor_wall_gate_passed,
            "cursor_token_overhead_within_5pct": cursor_token_gate_passed,
            "warm_cache_positive_and_billed_ratio_within_70pct": warm_cache_gate_passed,
        },
        "eligibility_rules": eligibility_rules,
    }
    resolved_output_path = (
        resolved_root / COMPETITIVE_REPORT_PATH if output_path is None else Path(output_path)
    )
    write_json(resolved_output_path, report)
    report["artifact_path"] = artifact_relative_path(resolved_root, resolved_output_path)
    return report


def load_json(path: Path | str) -> dict[str, Any]:
    payload = read_json(Path(path))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload
