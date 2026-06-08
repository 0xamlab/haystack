"""Tests for CLI jobs commands.

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


def test_cmd_job_list_prints_summary(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/jobs/list?page=2&limit=10&status=queued"
        return 200, {
            "jobs": [
                {
                    "job_id": "job_123",
                    "status": "queued",
                    "queue_name": "default",
                    "retry_count": 0,
                }
            ],
            "total": 1,
            "page": 2,
            "limit": 10,
            "pages": 3,
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_job_list, page=2, limit=10, status_filter="queued")

    assert "Jobs (1 total, page 2/3)" in output
    assert "job_123" in output
    assert "queue=default" in output


def test_cmd_job_result_prints_payload(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/jobs/job_123/result"
        return 200, {"status": "completed", "result": {"recommended_action": "proceed"}}

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_job_result, "job_123", "json")

    assert '"status": "completed"' in output
    assert '"recommended_action": "proceed"' in output


def test_cmd_job_status_prints_payload(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/jobs/job_123"
        return 200, {"job_id": "job_123", "status": "running"}

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_job_status, "job_123", "json")

    assert '"job_id": "job_123"' in output
    assert '"status": "running"' in output


def test_cmd_job_cancel_prints_payload(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/jobs/job_123/cancel"
        return 200, {"job_id": "job_123", "status": "cancelled"}

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_job_cancel, "job_123", "json")

    assert '"job_id": "job_123"' in output
    assert '"status": "cancelled"' in output


def test_cmd_job_wait_prints_completed_result(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    calls: list[tuple[str, str]] = []

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        calls.append((method, path))
        if path == "/v1/jobs/job_123":
            return 200, {"job_id": "job_123", "status": "completed"}
        assert path == "/v1/jobs/job_123/result"
        return 200, {"status": "completed", "result": {"recommended_action": "proceed"}}

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_job_wait, "job_123", 30, "json")

    assert "Waiting for job job_123" in output
    assert "Job completed!" in output
    assert '"recommended_action": "proceed"' in output
    assert calls == [
        ("GET", "/v1/jobs/job_123"),
        ("GET", "/v1/jobs/job_123/result"),
    ]


def test_cmd_job_wait_fails_fast_on_status_api_error(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (404, {"error": {"code": "job_not_found"}}),
    )

    with pytest.raises(SystemExit, match="1"):
        _capture_stderr(cli.cmd_job_wait, "job_123", 30, "json")


def test_cmd_triggers_register_posts_request_and_prints_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "trigger.json"
    payload = {
        "name": "Revenue alert",
        "condition": {
            "source_id": "src_orders",
            "metric_hint": "revenue",
            "threshold": 200000,
            "direction": "above",
        },
        "simulation_template": {"mode": "auto"},
        "auto_execute": True,
    }
    request_path.write_text(json.dumps(payload))

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/triggers"
        assert body == payload
        return 201, {
            "trigger_id": "trigger_123",
            "name": "Revenue alert",
            "status": "active",
            "condition": payload["condition"],
            "auto_execute": True,
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_triggers_register, str(request_path), "table")

    assert "Trigger ID:    trigger_123" in output
    assert "Name:          Revenue alert" in output
    assert "Status:        active" in output
    assert "Condition:     revenue above 200000" in output
    assert "Auto execute:  True" in output


def test_cmd_triggers_list_prints_summary(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/triggers?status=paused&page=2&limit=10"
        return 200, {
            "triggers": [
                {
                    "trigger_id": "trigger_123",
                    "status": "paused",
                    "name": "Revenue alert",
                    "condition": {"metric_hint": "revenue", "direction": "above", "threshold": 200000},
                }
            ],
            "total": 1,
            "page": 2,
            "pages": 3,
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(
        cli.cmd_triggers_list,
        format="table",
        status_filter="paused",
        page=2,
        limit=10,
    )

    assert "Triggers (1 total, page 2/3)" in output
    assert "trigger_123  [paused] Revenue alert" in output


def test_cmd_triggers_fire_pause_resume_and_delete_print_json(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    calls: list[tuple[str, str, object]] = []

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        calls.append((method, path, body))
        if (method, path) == ("POST", "/v1/triggers/trigger_123/fire"):
            return 200, {
                "trigger_id": "trigger_123",
                "condition_met": True,
                "fired": True,
                "simulation_run_id": "run_123",
                "recommended_action": "proceed",
                "message": "Trigger fired.",
            }
        if (method, path) == ("PATCH", "/v1/triggers/trigger_123/pause?paused=true"):
            return 200, {"trigger_id": "trigger_123", "status": "paused"}
        if (method, path) == ("PATCH", "/v1/triggers/trigger_123/pause?paused=false"):
            return 200, {"trigger_id": "trigger_123", "status": "active"}
        if (method, path) == ("DELETE", "/v1/triggers/trigger_123"):
            return 204, {}
        raise AssertionError(f"Unexpected call {(method, path)}")

    monkeypatch.setattr(cli, "api_request", _fake_api_request)

    fired = _capture_stdout(cli.cmd_triggers_fire, "trigger_123", "json", force=True)
    paused = _capture_stdout(cli.cmd_triggers_pause, "trigger_123", "json", paused=True)
    resumed = _capture_stdout(cli.cmd_triggers_pause, "trigger_123", "json", paused=False)
    deleted = _capture_stdout(cli.cmd_triggers_delete, "trigger_123", "json")

    assert json.loads(fired)["simulation_run_id"] == "run_123"
    assert json.loads(paused)["status"] == "paused"
    assert json.loads(resumed)["status"] == "active"
    assert json.loads(deleted) == {"trigger_id": "trigger_123", "deleted": True}
    assert calls == [
        ("POST", "/v1/triggers/trigger_123/fire", {"force": True}),
        ("PATCH", "/v1/triggers/trigger_123/pause?paused=true", None),
        ("PATCH", "/v1/triggers/trigger_123/pause?paused=false", None),
        ("DELETE", "/v1/triggers/trigger_123", None),
    ]


def test_cmd_webhook_test_prints_payload(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/webhooks/test"
        assert body == {"callback_url": "https://example.com/webhook"}
        return 200, {"success": True, "status_code": 200, "message": "delivered"}

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_webhook_test, "https://example.com/webhook", "json")

    assert '"success": true' in output.lower()
    assert '"status_code": 200' in output
    assert '"message": "delivered"' in output


def test_main_dispatches_job_list(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd(
        page: int = 1,
        limit: int = 25,
        status_filter: str | None = None,
        format: str = "table",
    ) -> None:
        called["page"] = page
        called["limit"] = limit
        called["status_filter"] = status_filter
        called["format"] = format

    monkeypatch.setattr(cli, "cmd_job_list", _fake_cmd)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["de", "job", "list", "--page", "2", "--limit", "10", "--status", "queued", "--format", "json"],
    )

    cli.main()

    assert called == {
        "page": 2,
        "limit": 10,
        "status_filter": "queued",
        "format": "json",
    }


@pytest.mark.parametrize(
    ("argv", "handler_name", "expected"),
    [
        (
            ["de", "job", "status", "job_123", "--format", "json"],
            "cmd_job_status",
            {"job_id": "job_123", "format": "json"},
        ),
        (
            ["de", "job", "result", "job_123", "--format", "json"],
            "cmd_job_result",
            {"job_id": "job_123", "format": "json"},
        ),
        (
            ["de", "job", "cancel", "job_123", "--format", "json"],
            "cmd_job_cancel",
            {"job_id": "job_123", "format": "json"},
        ),
        (
            ["de", "job", "wait", "job_123", "--timeout", "30", "--format", "json"],
            "cmd_job_wait",
            {"job_id": "job_123", "timeout": 30, "format": "json"},
        ),
    ],
)
def test_main_dispatches_job_status_result_cancel_and_wait(
    monkeypatch,
    argv: list[str],
    handler_name: str,
    expected: dict[str, object],
) -> None:
    called: dict[str, object] = {}

    def _fake_cmd(job_id: str, *extra: object) -> None:
        called["job_id"] = job_id
        if handler_name == "cmd_job_wait":
            called["timeout"] = extra[0] if len(extra) > 0 else 300
            called["format"] = extra[1] if len(extra) > 1 else "table"
            return
        called["format"] = extra[0] if len(extra) > 0 else "table"

    monkeypatch.setattr(cli, handler_name, _fake_cmd)
    monkeypatch.setattr(cli.sys, "argv", argv)

    cli.main()

    assert called == expected


def test_main_dispatches_trigger_commands(monkeypatch) -> None:
    called: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def _record(name: str):
        def _fake(*args: object, **kwargs: object) -> None:
            called.append((name, args, kwargs))

        return _fake

    monkeypatch.setattr(cli, "cmd_triggers_register", _record("register"))
    monkeypatch.setattr(cli, "cmd_triggers_list", _record("list"))
    monkeypatch.setattr(cli, "cmd_triggers_fire", _record("fire"))
    monkeypatch.setattr(cli, "cmd_triggers_pause", _record("pause"))
    monkeypatch.setattr(cli, "cmd_triggers_delete", _record("delete"))

    for argv in (
        ["de", "triggers", "register", "trigger.json", "--format", "json"],
        [
            "de",
            "triggers",
            "list",
            "--status",
            "paused",
            "--page",
            "2",
            "--limit",
            "10",
            "--format",
            "json",
        ],
        ["de", "triggers", "fire", "trigger_123", "--force", "--format", "json"],
        ["de", "triggers", "pause", "trigger_123", "--format", "json"],
        ["de", "triggers", "resume", "trigger_123", "--format", "json"],
        ["de", "triggers", "delete", "trigger_123", "--format", "json"],
    ):
        monkeypatch.setattr(cli.sys, "argv", argv)
        cli.main()

    assert called == [
        ("register", ("trigger.json", "json"), {}),
        ("list", (), {"format": "json", "status_filter": "paused", "page": 2, "limit": 10}),
        ("fire", ("trigger_123", "json"), {"force": True}),
        ("pause", ("trigger_123", "json"), {"paused": True}),
        ("pause", ("trigger_123", "json"), {"paused": False}),
        ("delete", ("trigger_123", "json"), {}),
    ]


def test_main_dispatches_webhook_test(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd(callback_url: str, format: str = "table") -> None:
        called["callback_url"] = callback_url
        called["format"] = format

    monkeypatch.setattr(cli, "cmd_webhook_test", _fake_cmd)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["de", "webhook", "test", "https://example.com/webhook", "--format", "json"],
    )

    cli.main()

    assert called == {"callback_url": "https://example.com/webhook", "format": "json"}


