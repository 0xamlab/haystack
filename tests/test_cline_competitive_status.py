from __future__ import annotations

from pathlib import Path

from apps.api_server.services.cline_competitive_status import (
    build_blocked_competitive_experience_report,
)
from apps.api_server.services.cline_proof_common import read_json, sha256_hex, write_json


ROOT = Path(__file__).resolve().parents[1]


def test_build_blocked_competitive_experience_report_blocks_on_missing_live_runtime(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "competitive.json"

    report = build_blocked_competitive_experience_report(
        root=ROOT,
        env={},
        output_path=output_path,
    )

    assert report["status"] == "blocked_missing_live_runtime"
    assert report["metrics_available"] is False
    assert report["environment_status"]["anthropic_api_key"] is False
    assert report["source_validation_errors"] == [
        "missing benchmark artifact path: g0_artifact",
        "missing benchmark artifact path: cursor_mcp_artifact",
        "missing benchmark artifact path: warm_cache_artifact",
    ]
    assert "missing required live environment variable: ANTHROPIC_API_KEY" in report["blockers"]
    assert read_json(output_path)["status"] == "blocked_missing_live_runtime"


def test_build_blocked_competitive_experience_report_blocks_on_missing_artifacts(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "competitive.json"

    report = build_blocked_competitive_experience_report(
        root=ROOT,
        env={
            "ANTHROPIC_API_KEY": "test-key",
        },
        output_path=output_path,
    )

    assert report["status"] == "blocked_missing_benchmark_artifacts"
    assert report["environment_status"]["anthropic_api_key"] is True
    assert report["blockers"] == report["source_validation_errors"]
    assert read_json(output_path)["status"] == "blocked_missing_benchmark_artifacts"


def test_build_blocked_competitive_experience_report_reads_available_benchmark_metadata(
    tmp_path: Path,
) -> None:
    g0_path = write_json(
        tmp_path / "g0.json",
        {
            "benchmark_suite": "g0_token_benchmark",
            "benchmark_suite_hash": sha256_hex("suite-v1"),
            "benchmark_fixture_hash": sha256_hex("fixtures-v1"),
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "provider_model_class": "anthropic:claude-sonnet-4-6",
            "task_count": 24,
            "usage_source": "runtime_accumulated_usage",
            "resolution_threshold_absolute_pp": 5.0,
            "resolution_threshold_mode": "absolute_percentage_points",
            "eligibility_rules": {
                "eligible_task": "task included in suite",
            },
        },
    )
    cursor_path = write_json(tmp_path / "cursor.json", {})
    warm_path = write_json(tmp_path / "warm.json", {})
    output_path = tmp_path / "competitive.json"

    report = build_blocked_competitive_experience_report(
        root=ROOT,
        env={
            "ANTHROPIC_API_KEY": "test-key",
        },
        output_path=output_path,
        g0_artifact_path=g0_path,
        cursor_mcp_artifact_path=cursor_path,
        warm_cache_artifact_path=warm_path,
    )

    assert report["status"] == "ready_for_report_generation"
    assert report["benchmark_suite_hash"] == sha256_hex("suite-v1")
    assert report["benchmark_fixture_hash"] == sha256_hex("fixtures-v1")
    assert report["provider_model_class"] == "anthropic:claude-sonnet-4-6"
    assert report["usage_source"] == "runtime_accumulated_usage"
    assert report["task_count"] == 24
    assert report["source_validation_errors"] == []
    assert report["eligibility_rules"] == {"eligible_task": "task included in suite"}
