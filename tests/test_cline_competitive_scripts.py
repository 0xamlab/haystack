from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from apps.api_server.services.cline_competitive_measurements import (
    build_cursor_mcp_comparison_artifact,
    build_warm_cache_comparison_artifact,
)
from apps.api_server.services.cline_proof_common import (
    build_proof_context,
    create_artifact_provenance,
)
from apps.api_server.services.cline_proof_common import sha256_hex, write_json


ROOT = Path(__file__).resolve().parents[1]
CURSOR_SCRIPT = ROOT / "scripts" / "generate_cline_cursor_mcp_comparison.py"
WARM_SCRIPT = ROOT / "scripts" / "generate_cline_warm_cache_comparison.py"
COMPETITIVE_SCRIPT = ROOT / "scripts" / "generate_cline_competitive_report.py"
LIVE_ARTIFACTS_SCRIPT = ROOT / "scripts" / "generate_cline_competitive_live_artifacts.py"


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


def test_generate_cursor_mcp_comparison_script_writes_artifact(tmp_path: Path) -> None:
    g0_path = write_json(tmp_path / "g0.json", _g0_payload())
    direct_path = write_json(
        tmp_path / "direct.json",
        {
            "agent": {
                "usage": {
                    "input_tokens": 900,
                    "output_tokens": 100,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 20,
                }
            }
        },
    )
    mcp_path = write_json(
        tmp_path / "mcp.json",
        {
            "agent": {
                "usage": {
                    "input_tokens": 936,
                    "output_tokens": 104,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 20,
                }
            }
        },
    )
    output_path = tmp_path / "cursor-mcp.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(CURSOR_SCRIPT),
            "--g0-artifact",
            str(g0_path),
            "--direct-json",
            str(direct_path),
            "--mcp-json",
            str(mcp_path),
            "--direct-wall-seconds",
            "10.0",
            "--mcp-wall-seconds",
            "10.8",
            "--output",
            str(output_path),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["benchmark_fixture_hash"] == sha256_hex("g0-fixtures-only-v1")
    assert payload["usage_source"] == "runtime_accumulated_usage"
    assert payload["direct_total_tokens"] == 1000.0
    assert payload["mcp_total_tokens"] == 1040.0


def test_generate_warm_cache_comparison_script_writes_artifact(tmp_path: Path) -> None:
    g0_path = write_json(tmp_path / "g0.json", _g0_payload())
    cold_path = write_json(
        tmp_path / "cold.json",
        {
            "usage": {
                "inputTokens": 1000,
                "outputTokens": 150,
                "cacheReadTokens": 0,
                "cacheWriteTokens": 40,
            }
        },
    )
    warm_path = write_json(
        tmp_path / "warm.json",
        {
            "usage": {
                "inputTokens": 1000,
                "outputTokens": 150,
                "cacheReadTokens": 350,
                "cacheWriteTokens": 40,
            }
        },
    )
    output_path = tmp_path / "warm-cache.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(WARM_SCRIPT),
            "--g0-artifact",
            str(g0_path),
            "--cold-json",
            str(cold_path),
            "--warm-json",
            str(warm_path),
            "--output",
            str(output_path),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["benchmark_fixture_hash"] == sha256_hex("g0-fixtures-only-v1")
    assert payload["usage_source"] == "runtime_accumulated_usage"
    assert payload["cold_billed_input_tokens"] == 1000.0
    assert payload["warm_billed_input_tokens"] == 650.0
    assert payload["warm_cache_read_tokens"] == 350.0


def test_generate_competitive_report_script_writes_artifact(tmp_path: Path) -> None:
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
            "fixtures": ["greet_literal", "sum_returns_zero"],
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
            "eligibility_rules": {
                "eligible_task": "task included in the frozen benchmark suite",
                "excluded_task": "task omitted from the frozen benchmark suite",
                "attempt": "single benchmark attempt per fixture/rep",
                "rerun_policy": "no reruns unless benchmark fixture changes",
                "timeout_policy": "400s fixed timeout",
                "partial_success": "counts as unresolved",
                "human_intervention": "forbidden",
                "benchmark_fixture_hash": sha256_hex("g0-fixtures-only-v1"),
            },
            "resolution_threshold_absolute_pp": 5.0,
            "resolution_threshold_mode": "absolute_percentage_points",
        },
    )
    cursor_path = tmp_path / "cursor-mcp.json"
    warm_path = tmp_path / "warm-cache.json"
    build_cursor_mcp_comparison_artifact(
        g0_payload=_g0_payload(),
        direct_payload={
            "agent": {
                "usage": {
                    "input_tokens": 900,
                    "output_tokens": 100,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 20,
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
        output_path=cursor_path,
    )
    build_warm_cache_comparison_artifact(
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
            }
        },
        root=ROOT,
        output_path=warm_path,
    )
    output_path = tmp_path / "competitive.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(COMPETITIVE_SCRIPT),
            "--g0-artifact",
            str(g0_path),
            "--cursor-mcp-json",
            str(cursor_path),
            "--warm-cache-json",
            str(warm_path),
            "--output",
            str(output_path),
            "--allow-dirty-tree",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["source_validation_errors"] == []


def test_generate_competitive_report_script_writes_blocked_artifact_without_inputs(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "competitive.json"
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ALGENTA_AGENT_CORE_URL", None)
    env.pop("ALGENTA_API_KEY", None)
    env.pop("DE_API_KEY", None)

    completed = subprocess.run(
        [
            sys.executable,
            str(COMPETITIVE_SCRIPT),
            "--output",
            str(output_path),
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked_missing_live_runtime"
    assert payload["metrics_available"] is False
    assert payload["source_validation_errors"] == [
        "missing benchmark artifact path: g0_artifact",
        "missing benchmark artifact path: cursor_mcp_artifact",
        "missing benchmark artifact path: warm_cache_artifact",
    ]


def test_generate_competitive_live_artifacts_script_exposes_help() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(LIVE_ARTIFACTS_SCRIPT),
            "--help",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Generate live Cursor-vs-direct and warm-cache competitive proof artifacts." in (
        completed.stdout
    )
