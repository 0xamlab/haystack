"""Tests for CLI agent_runs commands.

Extracted from tests/test_cli_data.py during modularization.
"""
from __future__ import annotations

import json

import pytest

from apps.cli import main as cli
from tests._manifest_backed_integrations import (
    MANIFEST_BACKED_INTEGRATIONS_DISPLAY,
    MANIFEST_BACKED_READ_ONLY_DISPLAY,
    assert_manifest_backed_integrations,
)
from tests._cli_data_helpers import (
    _capture_stdout,
    _capture_stderr,
    _platform_contract_payload,
)


def test_cmd_agent_run_query_checkpoints_prints_summary(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert (
            path
            == "/v1/agent/runs/checkpoints?page=2&limit=10&status=completed&request_hash=hash_123"
            "&policy_snapshot_id=policy-v1&schema_snapshot_id=schema-v1&run_id=run_123&checkpoint_id=cp_2"
        )
        return 200, {
            "object": "list",
            "data": [
                {
                    "checkpoint_id": "cp_2",
                    "checkpoint_index": 2,
                    "run_id": "run_123",
                    "run_status": "completed",
                    "parent_checkpoint_id": "cp_1",
                    "status": "completed",
                    "event_start_index": 3,
                    "event_end_index": 5,
                    "request_hash": "hash_123",
                    "decision_hash": "b" * 64,
                    "content_hash": "c" * 64,
                    "policy_snapshot_id": "policy-v1",
                    "schema_snapshot_id": "schema-v1",
                    "manifest_version": "runtime-manifest-v1",
                    "artifact_refs": ["art_1"],
                    "created_at": "2026-05-24T12:00:03Z",
                }
            ],
            "total": 1,
            "page": 2,
            "limit": 10,
            "pages": 3,
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(
        cli.cmd_agent_run_query_checkpoints,
        page=2,
        limit=10,
        status_filter="completed",
        request_hash="hash_123",
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        run_id="run_123",
        checkpoint_id="cp_2",
        format="table",
    )

    assert "Checkpoints: 1" in output
    assert "Page:        2 / 3" in output
    assert "run_123" in output
    assert "cp_2" in output


def test_cmd_agent_run_create_posts_request_and_prints_status(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "agent-run.json"
    payload = {"task": "Summarize current benchmarks", "approval_mode": "never"}
    request_path.write_text(json.dumps(payload))

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/agent/runs"
        assert body == payload
        return 200, {
            "run_id": "run_123",
            "status": "requires_approval",
            "task": "Summarize current benchmarks",
            "approval_mode": "never",
            "pending_action": "approve",
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_agent_run_create, str(request_path), "table")

    assert "Run ID:         run_123" in output
    assert "Status:         requires_approval" in output
    assert "Pending action: approve" in output


def test_cmd_agent_run_list_prints_run_summary(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert (
            path
            == "/v1/agent/runs?page=1&limit=25&status=requires_approval&policy_snapshot_id=policy-v1"
        )
        assert body is None
        return 200, {
            "total": 1,
            "page": 1,
            "limit": 25,
            "pages": 1,
            "data": [
                {
                    "created_at": "2026-05-24T12:00:00Z",
                    "run_id": "run_123",
                    "status": "requires_approval",
                    "selected_tool": "search",
                    "policy_snapshot_id": "policy-v1",
                }
            ],
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(
        cli.cmd_agent_run_list,
        page=1,
        limit=25,
        status_filter="requires_approval",
        policy_snapshot_id="policy-v1",
        format="table",
    )

    assert "Total runs:     1" in output
    assert "Page:           1 / 1" in output
    assert "2026-05-24T12:00:00Z  run_123  requires_approval  search  policy-v1" in output


def test_cmd_agent_run_events_uses_limit_and_prints_events(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/agent/runs/run_123/events?limit=25"
        assert body is None
        return 200, {
            "run_id": "run_123",
            "total_events": 2,
            "data": [
                {
                    "created_at": "2026-05-24T12:00:00Z",
                    "event_type": "run_created",
                    "status": "queued",
                    "message": "Run created",
                },
                {
                    "created_at": "2026-05-24T12:00:02Z",
                    "event_type": "tool_selected",
                    "status": "running",
                    "message": "Selected tokenizer",
                },
            ],
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_agent_run_events, "run_123", 25, "table")

    assert "Run ID:        run_123" in output
    assert "Total events:  2" in output
    assert "2026-05-24T12:00:00Z  run_created  queued  Run created" in output
    assert "2026-05-24T12:00:02Z  tool_selected  running  Selected tokenizer" in output


def test_cmd_agent_run_events_stream_uses_stream_path_and_prints_json_lines(monkeypatch) -> None:
    streamed_payloads = [
        {
            "type": "agent.run.event",
            "run_id": "run_123",
            "event": {
                "event_type": "run_created",
                "status": "queued",
                "message": "Run created",
            },
        },
        {
            "type": "agent.run.completed",
            "run_id": "run_123",
            "status": "completed",
            "total_events": 1,
        },
    ]

    def _fake_api_stream_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/agent/runs/run_123/events?limit=25&stream=true"
        assert body is None
        return iter(streamed_payloads)

    monkeypatch.setattr(cli, "api_stream_request", _fake_api_stream_request)
    output = _capture_stdout(cli.cmd_agent_run_events, "run_123", 25, "json", stream=True)
    lines = [json.loads(line) for line in output.splitlines() if line.strip()]
    assert lines == streamed_payloads


def test_cmd_agent_run_events_stream_renders_table_summary(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "api_stream_request",
        lambda method, path, body=None: iter(  # type: ignore[no-untyped-def]
            [
                {
                    "type": "agent.run.event",
                    "run_id": "run_123",
                    "event": {
                        "created_at": "2026-05-24T12:00:00Z",
                        "event_type": "run_created",
                        "status": "queued",
                        "message": "Run created",
                    },
                },
                {
                    "type": "agent.run.completed",
                    "run_id": "run_123",
                    "status": "completed",
                    "total_events": 1,
                },
            ]
        ),
    )

    output = _capture_stdout(cli.cmd_agent_run_events, "run_123", 25, "table", stream=True)

    assert "2026-05-24T12:00:00Z  run_created  queued  Run created" in output
    assert "Run completed:  run_123  status=completed total_events=1" in output


def test_cmd_agent_run_checkpoints_prints_checkpoint_summary(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/agent/runs/run_123/checkpoints"
        assert body is None
        return 200, {
            "run_id": "run_123",
            "total_checkpoints": 2,
            "data": [
                {
                    "checkpoint_id": "cp_1",
                    "checkpoint_index": 1,
                    "status": "requires_approval",
                    "event_start_index": 0,
                    "event_end_index": 2,
                },
                {
                    "checkpoint_id": "cp_2",
                    "checkpoint_index": 2,
                    "status": "completed",
                    "event_start_index": 3,
                    "event_end_index": 5,
                },
            ],
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_agent_run_checkpoints, "run_123", "table")

    assert "Run ID:            run_123" in output
    assert "Total checkpoints: 2" in output
    assert "#1  cp_1  requires_approval  events 0..2" in output
    assert "#2  cp_2  completed  events 3..5" in output


def test_cmd_agent_run_mission_events_prints_event_summary(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/agent/runs/run_123/mission-events?limit=25"
        assert body is None
        return 200, {
            "run_id": "run_123",
            "total_events": 1,
            "data": [
                {
                    "event_ts": "2026-05-24T12:00:00Z",
                    "event_type": "run_created",
                    "superstep": 1,
                    "checkpoint_id": None,
                }
            ],
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_agent_run_mission_events, "run_123", 25, "table")

    assert "Run ID:        run_123" in output
    assert "Total events:  1" in output
    assert "2026-05-24T12:00:00Z  run_created  superstep=1  checkpoint=-" in output


def test_cmd_agent_run_telemetry_prints_batch_summary(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/agent/runs/run_123/telemetry?limit=25"
        assert body is None
        return 200, {
            "run_id": "run_123",
            "total_batches": 1,
            "data": [
                {
                    "started_at": "2026-05-24T12:00:00Z",
                    "ended_at": "2026-05-24T12:00:03Z",
                    "telemetry_kind": "agent_run_completion",
                    "latency_ms_p95": 21.5,
                    "success_count": 1,
                    "failure_count": 0,
                }
            ],
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_agent_run_telemetry, "run_123", 25, "table")

    assert "Run ID:         run_123" in output
    assert "Total batches:  1" in output
    assert "agent_run_completion  p95=21.5ms  success=1 failure=0" in output


def test_cmd_agent_run_query_mission_events_prints_cross_run_summary(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert (
            path
            == "/v1/agent/runs/mission-events?page=1&limit=25&status=completed&request_hash="
            + ("a" * 64)
            + "&policy_snapshot_id=policy-v1&schema_snapshot_id=schema-v1&run_id=run_123&event_type=run_completed"
        )
        assert body is None
        return 200, {
            "total": 1,
            "page": 1,
            "pages": 1,
            "data": [
                {
                    "event_ts": "2026-05-24T12:00:03Z",
                    "run_id": "run_123",
                    "run_status": "completed",
                    "event_type": "run_completed",
                    "superstep": 2,
                }
            ],
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(
        cli.cmd_agent_run_query_mission_events,
        page=1,
        limit=25,
        status_filter="completed",
        request_hash="a" * 64,
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        run_id="run_123",
        event_type="run_completed",
        format="table",
    )

    assert "Mission events: 1" in output
    assert "Page:           1 / 1" in output
    assert "run_123  completed  run_completed  superstep=2" in output


def test_cmd_agent_run_query_telemetry_prints_cross_run_summary(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert (
            path
            == "/v1/agent/runs/telemetry?page=1&limit=25&status=completed&request_hash="
            + ("a" * 64)
            + "&policy_snapshot_id=policy-v1&schema_snapshot_id=schema-v1&run_id=run_123&telemetry_kind=agent_run_completion&module_name=agent_run_service"
        )
        assert body is None
        return 200, {
            "total": 1,
            "page": 1,
            "pages": 1,
            "data": [
                {
                    "started_at": "2026-05-24T12:00:00Z",
                    "run_id": "run_123",
                    "run_status": "completed",
                    "telemetry_kind": "agent_run_completion",
                    "latency_ms_p95": 21.5,
                }
            ],
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(
        cli.cmd_agent_run_query_telemetry,
        page=1,
        limit=25,
        status_filter="completed",
        request_hash="a" * 64,
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        run_id="run_123",
        telemetry_kind="agent_run_completion",
        module_name="agent_run_service",
        format="table",
    )

    assert "Telemetry batches: 1" in output
    assert "Page:              1 / 1" in output
    assert "run_123  completed  agent_run_completion  p95=21.5ms" in output


@pytest.mark.parametrize(
    ("func_name", "path", "expected_status", "expected_pending_action"),
    [
        ("cmd_agent_run_resume", "/v1/agent/runs/run_123/resume", "running", None),
        ("cmd_agent_run_cancel", "/v1/agent/runs/run_123/cancel", "cancelled", None),
        (
            "cmd_agent_run_approve",
            "/v1/agent/runs/run_123/approve",
            "completed",
            "none",
        ),
    ],
)
def test_agent_run_transition_commands_post_empty_body_and_print_status(
    monkeypatch,
    func_name: str,
    path: str,
    expected_status: str,
    expected_pending_action: str | None,
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, requested_path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert requested_path == path
        assert body == {}
        return 200, {
            "run_id": "run_123",
            "status": expected_status,
            "pending_action": expected_pending_action,
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(getattr(cli, func_name), "run_123", "table")

    assert "Run ID:         run_123" in output
    assert f"Status:         {expected_status}" in output
    assert f"Pending action: {expected_pending_action}" in output


def test_main_dispatches_agent_run_events(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd_agent_run_events(
        run_id: str, limit: int = 1000, format: str = "table", *, stream: bool = False
    ) -> None:
        called["run_id"] = run_id
        called["limit"] = limit
        called["format"] = format
        called["stream"] = stream

    monkeypatch.setattr(cli, "cmd_agent_run_events", _fake_cmd_agent_run_events)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["de", "agent-runs", "events", "run_123", "--limit", "25", "--format", "json", "--stream"],
    )

    cli.main()

    assert called == {"run_id": "run_123", "limit": 25, "format": "json", "stream": True}


@pytest.mark.parametrize(
    ("subcommand", "expected_func"),
    [
        ("list", "cmd_agent_run_list"),
        ("checkpoints", "cmd_agent_run_checkpoints"),
        ("query-checkpoints", "cmd_agent_run_query_checkpoints"),
        ("mission-events", "cmd_agent_run_mission_events"),
        ("query-mission-events", "cmd_agent_run_query_mission_events"),
        ("telemetry", "cmd_agent_run_telemetry"),
        ("query-telemetry", "cmd_agent_run_query_telemetry"),
    ],
)
def test_main_dispatches_agent_run_read_commands(
    monkeypatch, subcommand: str, expected_func: str
) -> None:
    called: dict[str, object] = {}

    def _fake_reader(*args, **kwargs):  # type: ignore[no-untyped-def]
        called["args"] = args
        called["kwargs"] = kwargs

    monkeypatch.setattr(cli, expected_func, _fake_reader)
    argv = ["de", "agent-runs", subcommand]
    if subcommand in {"checkpoints", "mission-events", "telemetry"}:
        argv.append("run_123")
    argv.extend(["--format", "json"])
    if subcommand in {"mission-events", "telemetry"}:
        argv.extend(["--limit", "25"])
    if subcommand == "list":
        argv.extend(["--status", "requires_approval", "--page", "2", "--limit", "10"])
    if subcommand == "query-mission-events":
        argv.extend(
            [
                "--status",
                "completed",
                "--request-hash",
                "hash_123",
                "--policy-snapshot-id",
                "policy-v1",
                "--schema-snapshot-id",
                "schema-v1",
                "--run-id",
                "run_123",
                "--event-type",
                "run_completed",
                "--page",
                "2",
                "--limit",
                "10",
            ]
        )
    if subcommand == "query-checkpoints":
        argv.extend(
            [
                "--status",
                "completed",
                "--request-hash",
                "hash_123",
                "--policy-snapshot-id",
                "policy-v1",
                "--schema-snapshot-id",
                "schema-v1",
                "--run-id",
                "run_123",
                "--checkpoint-id",
                "cp_2",
                "--page",
                "2",
                "--limit",
                "10",
            ]
        )
    if subcommand == "query-telemetry":
        argv.extend(
            [
                "--status",
                "completed",
                "--request-hash",
                "hash_123",
                "--policy-snapshot-id",
                "policy-v1",
                "--schema-snapshot-id",
                "schema-v1",
                "--run-id",
                "run_123",
                "--telemetry-kind",
                "agent_run_completion",
                "--module-name",
                "agent_run_service",
                "--page",
                "2",
                "--limit",
                "10",
            ]
        )
    monkeypatch.setattr(cli.sys, "argv", argv)

    cli.main()

    if subcommand == "list":
        assert called == {
            "args": (),
            "kwargs": {
                "page": 2,
                "limit": 10,
                "status_filter": "requires_approval",
                "request_hash": None,
                "policy_snapshot_id": None,
                "schema_snapshot_id": None,
                "format": "json",
            },
        }
    elif subcommand == "checkpoints":
        assert called == {"args": ("run_123", "json"), "kwargs": {}}
    elif subcommand == "query-checkpoints":
        assert called == {
            "args": (),
            "kwargs": {
                "page": 2,
                "limit": 10,
                "status_filter": "completed",
                "request_hash": "hash_123",
                "policy_snapshot_id": "policy-v1",
                "schema_snapshot_id": "schema-v1",
                "run_id": "run_123",
                "checkpoint_id": "cp_2",
                "format": "json",
            },
        }
    elif subcommand == "query-mission-events":
        assert called == {
            "args": (),
            "kwargs": {
                "page": 2,
                "limit": 10,
                "status_filter": "completed",
                "request_hash": "hash_123",
                "policy_snapshot_id": "policy-v1",
                "schema_snapshot_id": "schema-v1",
                "run_id": "run_123",
                "event_type": "run_completed",
                "format": "json",
            },
        }
    elif subcommand == "query-telemetry":
        assert called == {
            "args": (),
            "kwargs": {
                "page": 2,
                "limit": 10,
                "status_filter": "completed",
                "request_hash": "hash_123",
                "policy_snapshot_id": "policy-v1",
                "schema_snapshot_id": "schema-v1",
                "run_id": "run_123",
                "telemetry_kind": "agent_run_completion",
                "module_name": "agent_run_service",
                "format": "json",
            },
        }
    else:
        assert called == {"args": ("run_123", 25, "json"), "kwargs": {}}


@pytest.mark.parametrize(
    ("subcommand", "expected_func"),
    [
        ("resume", "cmd_agent_run_resume"),
        ("cancel", "cmd_agent_run_cancel"),
        ("approve", "cmd_agent_run_approve"),
    ],
)
def test_main_dispatches_agent_run_transitions(
    monkeypatch, subcommand: str, expected_func: str
) -> None:
    called: dict[str, object] = {}

    def _fake_transition(run_id: str, format: str = "table") -> None:
        called["run_id"] = run_id
        called["format"] = format

    monkeypatch.setattr(cli, expected_func, _fake_transition)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["de", "agent-runs", subcommand, "run_123", "--format", "json"],
    )

    cli.main()

    assert called == {"run_id": "run_123", "format": "json"}


