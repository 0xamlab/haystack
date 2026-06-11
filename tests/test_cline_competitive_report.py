from __future__ import annotations

import json
from pathlib import Path

from apps.api_server.services.cline_competitive_report import (
    build_competitive_experience_report,
    build_competitive_input_from_artifact_paths,
    build_competitive_input_from_g0_artifact,
)
from apps.api_server.services.cline_proof_common import (
    build_proof_context,
    create_artifact_provenance,
    sha256_hex,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]


def _g0_payload() -> dict[str, object]:
    fixtures = ["greet_literal", "sum_returns_zero"]
    benchmark_suite_hash = sha256_hex("g0-fixtures-v1")
    benchmark_fixture_hash = sha256_hex("g0-fixtures-only-v1")
    return {
        "benchmark_suite": "g0_token_benchmark",
        "benchmark_suite_hash": benchmark_suite_hash,
        "benchmark_fixture_hash": benchmark_fixture_hash,
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "provider_model_class": "anthropic:claude-sonnet-4-6",
        "prompt_family": "g0_repository_fix_v1",
        "tool_policy_profile": "repository_fix_gated",
        "max_iterations": 10,
        "timeout_seconds": 400,
        "task_count": 2,
        "usage_source": "runtime_accumulated_usage",
        "resolution_threshold_absolute_pp": 5.0,
        "resolution_threshold_mode": "absolute_percentage_points",
        "eligibility_rules": {
            "eligible_task": "task included in the frozen benchmark suite",
            "excluded_task": "task omitted from the frozen benchmark suite",
            "attempt": "single benchmark attempt per fixture/rep",
            "rerun_policy": "no reruns unless benchmark fixture changes",
            "timeout_policy": "400s fixed timeout",
            "partial_success": "counts as unresolved",
            "human_intervention": "forbidden",
            "benchmark_fixture_hash": benchmark_fixture_hash,
        },
        "fixtures": fixtures,
        "reps": 1,
        "aggregates": {
            "A": {
                "n": 2,
                "resolution_rate": 1.0,
                "mean_total_tokens": 1000,
            },
            "C": {
                "n": 2,
                "resolution_rate": 1.0,
                "mean_total_tokens": 200,
            },
        },
    }


def _cursor_payload(
    benchmark_suite_hash: str,
    benchmark_fixture_hash: str,
) -> dict[str, object]:
    return {
        "benchmark_suite_hash": benchmark_suite_hash,
        "benchmark_fixture_hash": benchmark_fixture_hash,
        "prompt_family": "g0_repository_fix_v1",
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "provider_model_class": "anthropic:claude-sonnet-4-6",
        "tool_policy_profile": "repository_fix_gated",
        "max_iterations": 10,
        "timeout_seconds": 400,
        "task_count": 2,
        "usage_source": "runtime_accumulated_usage",
        "direct_wall_time_seconds": 10.0,
        "mcp_wall_time_seconds": 10.8,
        "direct_total_tokens": 1000,
        "mcp_total_tokens": 1040,
    }


def _warm_payload(
    benchmark_suite_hash: str,
    benchmark_fixture_hash: str,
) -> dict[str, object]:
    return {
        "benchmark_suite_hash": benchmark_suite_hash,
        "benchmark_fixture_hash": benchmark_fixture_hash,
        "prompt_family": "g0_repository_fix_v1",
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "provider_model_class": "anthropic:claude-sonnet-4-6",
        "tool_policy_profile": "repository_fix_gated",
        "max_iterations": 10,
        "timeout_seconds": 400,
        "task_count": 2,
        "usage_source": "runtime_accumulated_usage",
        "cold_billed_input_tokens": 1000,
        "warm_billed_input_tokens": 650,
        "warm_cache_read_tokens": 100,
    }


def test_build_competitive_experience_report_passes_on_valid_gate_input(tmp_path: Path) -> None:
    g0_payload = _g0_payload()
    benchmark_suite_hash = g0_payload["benchmark_suite_hash"]
    benchmark_fixture_hash = g0_payload["benchmark_fixture_hash"]
    benchmark_input = build_competitive_input_from_g0_artifact(
        g0_payload=g0_payload,
        cursor_mcp_comparison=_cursor_payload(
            str(benchmark_suite_hash),
            str(benchmark_fixture_hash),
        ),
        warm_cache_comparison=_warm_payload(
            str(benchmark_suite_hash),
            str(benchmark_fixture_hash),
        ),
    )

    report = build_competitive_experience_report(
        benchmark_input=benchmark_input,
        root=ROOT,
        output_path=tmp_path / "competitive.json",
    )

    assert report["status"] == "passed"
    assert report["delta_pp"] == 0.0
    assert report["benchmark_fixture_hash"] == sha256_hex("g0-fixtures-only-v1")
    assert report["provider_model_class"] == "anthropic:claude-sonnet-4-6"
    assert report["usage_source"] == "runtime_accumulated_usage"
    assert report["resolution_threshold_absolute_pp"] == 5.0
    assert report["resolution_threshold_mode"] == "absolute_percentage_points"
    assert report["tokens_vs_vanilla_agentic_ratio"] == 0.2
    assert round(report["cursor_mcp_wall_time_overhead_ratio"], 2) == 0.08
    assert round(report["cursor_mcp_token_overhead_ratio"], 2) == 0.04
    assert report["warm_billed_input_token_ratio"] == 0.65
    assert report["warm_cache_read_tokens_positive"] is True
    assert report["source_validation_errors"] == []
    assert report["eligibility_validation_errors"] == []


def test_build_competitive_experience_report_fails_on_prompt_drift_and_overhead(tmp_path: Path) -> None:
    g0_payload = _g0_payload()
    benchmark_suite_hash = str(g0_payload["benchmark_suite_hash"])
    benchmark_fixture_hash = str(g0_payload["benchmark_fixture_hash"])
    cursor_payload = _cursor_payload(benchmark_suite_hash, benchmark_fixture_hash)
    cursor_payload["prompt_family"] = "different_prompt"
    cursor_payload["mcp_wall_time_seconds"] = 12.0
    cursor_payload["mcp_total_tokens"] = 1200
    warm_payload = _warm_payload(benchmark_suite_hash, benchmark_fixture_hash)
    warm_payload["warm_billed_input_tokens"] = 900
    warm_payload["warm_cache_read_tokens"] = 0

    benchmark_input = build_competitive_input_from_g0_artifact(
        g0_payload=g0_payload,
        cursor_mcp_comparison=cursor_payload,
        warm_cache_comparison=warm_payload,
    )

    report = build_competitive_experience_report(
        benchmark_input=benchmark_input,
        root=ROOT,
        output_path=tmp_path / "competitive.json",
    )

    assert report["status"] == "failed"
    assert report["validation_errors"]
    assert report["gate_results"]["cursor_wall_overhead_within_10pct"] is False
    assert report["gate_results"]["cursor_token_overhead_within_5pct"] is False
    assert report["gate_results"]["warm_cache_positive_and_billed_ratio_within_70pct"] is False


def test_build_competitive_input_from_artifact_paths_fails_closed_on_stale_provenance(
    tmp_path: Path,
) -> None:
    context = build_proof_context(ROOT)
    g0_path = write_json(
        tmp_path / "g0.json",
        {
            **create_artifact_provenance(
                context,
                run_id="g0_token_benchmark",
                schema_version="cline-g0-benchmark-results/v1",
            ),
            **_g0_payload(),
        },
    )
    cursor_path = write_json(
        tmp_path / "cursor.json",
        {
            **create_artifact_provenance(
                context,
                run_id="cursor_mcp_comparison",
                schema_version="cline-cursor-mcp-comparison/v1",
            ),
            **_cursor_payload(
                str(_g0_payload()["benchmark_suite_hash"]),
                str(_g0_payload()["benchmark_fixture_hash"]),
            ),
        },
    )
    warm_path = write_json(
        tmp_path / "warm.json",
        {
            **create_artifact_provenance(
                context,
                run_id="warm_cache_comparison",
                schema_version="cline-warm-cache-comparison/v1",
            ),
            **_warm_payload(
                str(_g0_payload()["benchmark_suite_hash"]),
                str(_g0_payload()["benchmark_fixture_hash"]),
            ),
        },
    )
    stale_payload = json.loads(g0_path.read_text(encoding="utf-8"))
    stale_payload["git_commit"] = "stale-commit"
    g0_path.write_text(json.dumps(stale_payload), encoding="utf-8")

    benchmark_input = build_competitive_input_from_artifact_paths(
        g0_artifact_path=g0_path,
        cursor_mcp_artifact_path=cursor_path,
        warm_cache_artifact_path=warm_path,
        root=ROOT,
        allow_dirty_tree=True,
    )
    report = build_competitive_experience_report(
        benchmark_input=benchmark_input,
        root=ROOT,
        output_path=tmp_path / "competitive.json",
    )

    assert report["status"] == "failed"
    assert report["source_validation_errors"]
