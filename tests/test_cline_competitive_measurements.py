from __future__ import annotations

from pathlib import Path

import pytest

from apps.api_server.services.cline_competitive_measurements import (
    build_cursor_mcp_comparison_artifact,
    build_warm_cache_comparison_artifact,
)
from apps.api_server.services.cline_proof_common import sha256_hex


ROOT = Path(__file__).resolve().parents[1]


def _g0_payload() -> dict[str, object]:
    return {
        "benchmark_suite": "g0_token_benchmark",
        "benchmark_suite_hash": sha256_hex("g0-fixtures-v1"),
        "benchmark_fixture_hash": sha256_hex("g0-fixtures-only-v1"),
        "prompt_family": "g0_repository_fix_v1",
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "provider_model_class": "anthropic:claude-sonnet-4-6",
        "tool_policy_profile": "repository_fix_gated",
        "max_iterations": 10,
        "timeout_seconds": 400,
        "task_count": 2,
        "usage_source": "runtime_accumulated_usage",
    }


def test_build_cursor_mcp_comparison_artifact_from_repository_envelopes(
    tmp_path: Path,
) -> None:
    artifact = build_cursor_mcp_comparison_artifact(
        g0_payload=_g0_payload(),
        direct_payload={
            "agent": {
                "usage": {
                    "input_tokens": 900,
                    "output_tokens": 100,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 20,
                }
            },
            "event_derived_usage": {"input_tokens": 900, "output_tokens": 100},
        },
        mcp_payload={
            "agent": {
                "usage": {
                    "input_tokens": 936,
                    "output_tokens": 104,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 20,
                }
            }
        },
        direct_wall_time_seconds=10.0,
        mcp_wall_time_seconds=10.8,
        root=ROOT,
        output_path=tmp_path / "cursor-mcp.json",
    )

    assert artifact["benchmark_suite"] == "g0_token_benchmark"
    assert artifact["benchmark_fixture_hash"] == sha256_hex("g0-fixtures-only-v1")
    assert artifact["provider_model_class"] == "anthropic:claude-sonnet-4-6"
    assert artifact["task_count"] == 2
    assert artifact["usage_source"] == "runtime_accumulated_usage"
    assert artifact["direct_total_tokens"] == 1000.0
    assert artifact["mcp_total_tokens"] == 1040.0
    assert artifact["direct_usage"]["billed_input_tokens"] == 900.0
    assert artifact["direct_token_observations"] == {
        "input_tokens": 900,
        "output_tokens": 100,
    }


def test_build_warm_cache_comparison_artifact_supports_camel_case_usage(
    tmp_path: Path,
) -> None:
    artifact = build_warm_cache_comparison_artifact(
        g0_payload=_g0_payload(),
        cold_payload={
            "usage": {
                "inputTokens": 1000,
                "outputTokens": 150,
                "cacheReadTokens": 0,
                "cacheWriteTokens": 40,
            }
        },
        warm_payload={
            "usage": {
                "inputTokens": 1000,
                "outputTokens": 150,
                "cacheReadTokens": 350,
                "cacheWriteTokens": 40,
            },
            "token_observations": {"cacheReadTokens": 350},
        },
        root=ROOT,
        output_path=tmp_path / "warm-cache.json",
    )

    assert artifact["cold_billed_input_tokens"] == 1000.0
    assert artifact["warm_billed_input_tokens"] == 650.0
    assert artifact["warm_cache_read_tokens"] == 350.0
    assert artifact["benchmark_fixture_hash"] == sha256_hex("g0-fixtures-only-v1")
    assert artifact["usage_source"] == "runtime_accumulated_usage"
    assert artifact["warm_token_observations"] == {"cacheReadTokens": 350}


def test_build_cursor_mcp_comparison_fails_closed_on_missing_usage_fields(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="must be numeric"):
        build_cursor_mcp_comparison_artifact(
            g0_payload=_g0_payload(),
            direct_payload={
                "agent": {
                    "usage": {
                        "input_tokens": 900,
                        "output_tokens": 100,
                        "cache_read_tokens": 0,
                    }
                }
            },
            mcp_payload={
                "agent": {
                    "usage": {
                        "input_tokens": 936,
                        "output_tokens": 104,
                        "cache_read_tokens": 0,
                        "cache_write_tokens": 20,
                    }
                }
            },
            direct_wall_time_seconds=10.0,
            mcp_wall_time_seconds=10.8,
            root=ROOT,
            output_path=tmp_path / "cursor-mcp.json",
        )
