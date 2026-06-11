from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from apps.api_server.services import cline_competitive_live_runs as live_runs
from apps.api_server.services.cline_proof_common import (
    CLINE_DOCS_SNAPSHOT_HASH_PATH,
    CLINE_DOCS_SNAPSHOT_PATH,
    read_json,
    sha256_hex,
    write_json,
)


def _write_docs_snapshot(root: Path) -> None:
    snapshot_text = "\n".join(
        [
            "ClineCore",
            "Sessions",
            "Events",
            "Permission Handling",
            "Writing Plugins",
            "MCP",
            "ACP",
            "GitHub",
        ]
    )
    snapshot_path = root / CLINE_DOCS_SNAPSHOT_PATH
    snapshot_hash_path = root / CLINE_DOCS_SNAPSHOT_HASH_PATH
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(snapshot_text, encoding="utf-8")
    snapshot_hash_path.write_text(sha256_hex(snapshot_text), encoding="utf-8")


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


def _verified_agentic_envelope(*, input_tokens: float, output_tokens: float) -> dict[str, object]:
    return {
        "repository": {"id": "repo_123", "ref": "main", "worktree": None},
        "pipeline": {
            "snapshot_id": "snapshot_123",
            "triage_id": "bundle_123",
            "plan_id": "plan_123",
            "simulation_id": "simulation_123",
            "apply_id": None,
        },
        "agent": {
            "agent_run_id": "run_123",
            "session_id": "session_123",
            "runtime_kind": "cline",
            "is_stub": False,
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_tokens": 300.0,
                "cache_write_tokens": 50.0,
                "cost_usd": 0.01,
            },
        },
        "telemetry": {
            "tool_calls_by_name": {},
            "engine_calls_by_name": {},
            "govern_hook_status": "unknown",
            "approval_events": [],
        },
        "gate": {"decision": "apply_allowed", "reasons": []},
        "artifacts": {"pipeline_response": {"status": "ok"}},
    }


@contextlib.contextmanager
def _fake_context(value: str):
    yield value


def test_collect_live_cursor_mcp_comparison_artifact_writes_raw_and_derived_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_docs_snapshot(tmp_path)
    g0_artifact_path = write_json(tmp_path / "g0.json", _g0_payload())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setattr(live_runs, "agent_core_runtime", lambda *args, **kwargs: _fake_context("http://agent"))
    monkeypatch.setattr(live_runs, "local_api_server", lambda *args, **kwargs: _fake_context("http://api"))
    monkeypatch.setattr(
        live_runs,
        "_measure_direct_repository_pipeline",
        lambda **kwargs: live_runs._MeasuredPayload(
            payload=_verified_agentic_envelope(input_tokens=1200.0, output_tokens=120.0),
            wall_time_seconds=8.0,
        ),
    )
    monkeypatch.setattr(
        live_runs,
        "_measure_mcp_repository_pipeline",
        lambda **kwargs: live_runs._MeasuredPayload(
            payload=_verified_agentic_envelope(input_tokens=1212.0, output_tokens=120.0),
            wall_time_seconds=8.64,
        ),
    )

    artifact = live_runs.collect_live_cursor_mcp_comparison_artifact(
        api_key="de_live_test_key",
        root=tmp_path,
        g0_artifact_path=g0_artifact_path,
    )

    assert artifact["direct_total_tokens"] == 1320.0
    assert artifact["mcp_total_tokens"] == 1332.0
    assert round((artifact["mcp_wall_time_seconds"] - artifact["direct_wall_time_seconds"]) / artifact["direct_wall_time_seconds"], 2) == 0.08
    assert read_json(tmp_path / live_runs.DIRECT_REPOSITORY_PIPELINE_PATH)["channel"] == "api"
    assert read_json(tmp_path / live_runs.MCP_REPOSITORY_PIPELINE_PATH)["channel"] == "mcp"
    assert read_json(tmp_path / "build/proofs/cline/cursor_mcp_comparison.json")["usage_source"] == (
        "runtime_accumulated_usage"
    )


def test_collect_live_warm_cache_comparison_artifact_writes_raw_and_derived_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_docs_snapshot(tmp_path)
    g0_artifact_path = write_json(tmp_path / "g0.json", _g0_payload())
    fixture_dir = tmp_path / "warm-cache-fixture"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setattr(live_runs, "agent_core_runtime", lambda *args, **kwargs: _fake_context("http://agent"))

    @contextlib.contextmanager
    def _fixture(task):
        assert task.name == "fixture-task"
        yield fixture_dir

    payloads = iter(
        [
            {
                "status": "completed",
                "terminal_state": "completed",
                "provider": "anthropic",
                "model": "claude-sonnet-4-6",
                "prompt_family": "g0_repository_fix_v1",
                "tool_profile": "no_exploration_local_validation",
                "usage": {
                    "inputTokens": 1000,
                    "outputTokens": 150,
                    "cacheReadTokens": 0,
                    "cacheWriteTokens": 40,
                    "costUsd": 0.02,
                },
                "event_derived_usage": {"cache_read_tokens": 0},
            },
            {
                "status": "completed",
                "terminal_state": "completed",
                "provider": "anthropic",
                "model": "claude-sonnet-4-6",
                "prompt_family": "g0_repository_fix_v1",
                "tool_profile": "no_exploration_local_validation",
                "usage": {
                    "inputTokens": 1000,
                    "outputTokens": 150,
                    "cacheReadTokens": 350,
                    "cacheWriteTokens": 40,
                    "costUsd": 0.01,
                },
                "event_derived_usage": {"cache_read_tokens": 350},
            },
        ]
    )
    monkeypatch.setattr(
        live_runs,
        "WARM_CACHE_TASKS",
        (
            live_runs._WarmCacheTask(
                name="fixture-task",
                files={"greet.py": 'def greet():\n    return "bye"\n'},
                prompt="fix it",
                injected_context="context",
            ),
        ),
    )
    monkeypatch.setattr(live_runs, "_warm_cache_fixture", _fixture)
    monkeypatch.setattr(live_runs, "_reset_warm_cache_fixture", lambda repo_dir, task: None)
    monkeypatch.setattr(live_runs, "_sidecar_run", lambda **kwargs: next(payloads))

    artifact = live_runs.collect_live_warm_cache_comparison_artifact(
        root=tmp_path,
        g0_artifact_path=g0_artifact_path,
        warm_repetitions=1,
    )

    assert artifact["cold_billed_input_tokens"] == 1000.0
    assert artifact["warm_billed_input_tokens"] == 650.0
    assert artifact["warm_cache_read_tokens"] == 350.0
    assert read_json(tmp_path / live_runs.WARM_CACHE_COLD_RUN_PATH)["channel"] == "agent_core_direct"
    assert read_json(tmp_path / live_runs.WARM_CACHE_WARM_RUN_PATH)["channel"] == "agent_core_direct"
    assert read_json(tmp_path / "build/proofs/cline/warm_cache_comparison.json")["usage_source"] == (
        "runtime_accumulated_usage"
    )
