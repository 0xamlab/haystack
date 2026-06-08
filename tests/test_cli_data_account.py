"""Tests for CLI account commands.

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


@pytest.mark.parametrize(
    ("func_name", "path", "payload", "expected_fragment"),
    [
        (
            "cmd_account_me",
            "/v1/me",
            {
                "email": "owner@example.com",
                "org_id": "org_123",
                "org_name": "Mission Ops",
                "plan": "enterprise",
            },
            "owner@example.com",
        ),
        (
            "cmd_account_update",
            "/v1/me",
            {
                "user": {
                    "email": "owner@example.com",
                    "name": "Mission Ops",
                },
                "org": {
                    "name": "Mission Control",
                    "plan": "enterprise",
                },
            },
            "Mission Control",
        ),
        (
            "cmd_account_usage",
            "/v1/usage",
            {
                "billing_period": "2026-05",
                "simulations_run": 120,
                "api_calls": 340,
                "quota_limit": 1000,
                "quota_used_pct": 12.0,
            },
            "2026-05",
        ),
        (
            "cmd_account_limits",
            "/v1/limits",
            {
                "plan": "enterprise",
                "simulations_per_month": "unlimited",
                "rate_limit_per_minute": 600,
                "connectors": 100,
                "jobs_enabled": True,
            },
            "enterprise",
        ),
        (
            "cmd_account_distributions",
            "/v1/distributions",
            [
                {
                    "name": "normal",
                    "description": "Normal distribution.",
                    "required_params": ["mean", "std"],
                    "optional_params": [],
                    "example": {"mean": 100, "std": 12},
                }
            ],
            "normal",
        ),
        (
            "cmd_account_templates",
            "/v1/templates",
            [
                {
                    "id": "product-launch",
                    "name": "Product Launch Decision",
                    "category": "business",
                    "description": "Compare launch scenarios.",
                    "example_request": {"mode": "auto"},
                }
            ],
            "product-launch",
        ),
        (
            "cmd_billing_info",
            "/v1/billing/info",
            {
                "plan": "enterprise",
                "stripe_customer_id": "cus_123",
                "subscription_status": "active",
                "current_period_end": "2026-06-30T00:00:00Z",
            },
            "enterprise",
        ),
    ],
)
def test_account_commands_render_table_output(
    monkeypatch,
    func_name: str,
    path: str,
    payload: object,
    expected_fragment: str,
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    if func_name == "cmd_account_update":
        request_path = cli.Path("/tmp/account_update.json")
        monkeypatch.setattr(cli.Path, "read_text", lambda _self: json.dumps({"name": "Mission Ops"}))
    else:
        request_path = None

    def _fake_api_request(method: str, request_path: str, body=None):
        expected_method = "PATCH" if func_name == "cmd_account_update" else "GET"
        assert (method, request_path) == (expected_method, path)
        if func_name == "cmd_account_update":
            assert body == {"name": "Mission Ops"}
        else:
            assert body is None
        return 200, payload

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    if request_path is None:
        output = _capture_stdout(getattr(cli, func_name), "table")
    else:
        output = _capture_stdout(getattr(cli, func_name), str(request_path), "table")
    assert expected_fragment in output


def test_billing_checkout_and_portal_commands_render_urls(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    calls: list[tuple[str, str, object]] = []

    def _fake_api_request(method: str, path: str, body=None):
        calls.append((method, path, body))
        if (method, path) == ("POST", "/v1/billing/checkout"):
            return 200, {"url": "https://billing.example/checkout/session_123"}
        if (method, path) == ("POST", "/v1/billing/portal"):
            return 200, {"url": "https://billing.example/portal/session_123"}
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(cli, "api_request", _fake_api_request)

    checkout = _capture_stdout(cli.cmd_billing_checkout, "pro", "table")
    portal = _capture_stdout(cli.cmd_billing_portal, "table")

    assert "Checkout URL: https://billing.example/checkout/session_123" in checkout
    assert "Portal URL: https://billing.example/portal/session_123" in portal
    assert calls == [
        ("POST", "/v1/billing/checkout", {"plan": "pro"}),
        ("POST", "/v1/billing/portal", {}),
    ]


def test_credits_refresh_command_renders_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "credits-refresh.json"
    request_path.write_text(
        json.dumps(
            {
                "device_id": "device_cli_123",
                "billing_period": "2026-05",
                "credits_used": 5,
            }
        )
    )
    calls: list[tuple[str, str, object]] = []

    def _fake_api_request(method: str, path: str, body=None):
        calls.append((method, path, body))
        assert (method, path) == ("POST", "/v1/credits/refresh")
        return 200, {
            "credits_granted": 10000,
            "credits_issued_this_month": 25000,
            "monthly_limit": 500000,
            "monthly_remaining": 475000,
            "billing_period": "2026-05",
            "expires_at": 1716547200,
            "refresh_after": 1716545040,
            "server_time": 1716460800,
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)

    output = _capture_stdout(cli.cmd_credits_refresh, str(request_path), "table")

    assert "Credits granted:        10000" in output
    assert "Issued this month:      25000" in output
    assert "Monthly remaining:      475000" in output
    assert calls == [
        (
            "POST",
            "/v1/credits/refresh",
            {
                "device_id": "device_cli_123",
                "billing_period": "2026-05",
                "credits_used": 5,
            },
        )
    ]


def test_metering_ingest_command_renders_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "metering.json"
    request_path.write_text(
        json.dumps(
            {
                "device_id": "device_cli_123",
                "events": [
                    {"event_type": "query", "latency_ms": 12.5, "success": True},
                    {"module": "pricing", "timestamp": 1716547200},
                ],
            }
        )
    )
    calls: list[tuple[str, str, object]] = []

    def _fake_api_request(method: str, path: str, body=None):
        calls.append((method, path, body))
        assert (method, path) == ("POST", "/v1/metering")
        return 200, {"accepted": 2, "billing_period": "2026-05"}

    monkeypatch.setattr(cli, "api_request", _fake_api_request)

    output = _capture_stdout(cli.cmd_metering_ingest, str(request_path), "table")

    assert "Accepted events: 2" in output
    assert "Billing period:  2026-05" in output
    assert calls == [
        (
            "POST",
            "/v1/metering",
            {
                "device_id": "device_cli_123",
                "events": [
                    {"event_type": "query", "latency_ms": 12.5, "success": True},
                    {"module": "pricing", "timestamp": 1716547200.0},
                ],
            },
        )
    ]


def test_key_commands_render_and_use_canonical_api_key_paths(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    calls: list[tuple[str, str, object]] = []

    def _fake_api_request(method: str, path: str, body=None):
        calls.append((method, path, body))
        if (method, path) == ("GET", "/v1/api-keys"):
            return 200, [
                {
                    "id": "key_1",
                    "label": "Mission Runtime Key",
                    "key_prefix": "de_live_abcd",
                    "device_limit": 2,
                    "status": "active",
                }
            ]
        if (method, path) == ("POST", "/v1/api-keys"):
            return 201, {
                "id": "key_2",
                "label": "Mission Rotation Key",
                "key_prefix": "de_live_efgh",
                "device_limit": 3,
                "raw_key": "de_live_efgh_secret_value",
                "expires_at": "2028-05-19T00:00:00Z",
            }
        if (method, path) == ("DELETE", "/v1/api-keys/key_2"):
            return 204, {}
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(cli, "api_request", _fake_api_request)

    listed = _capture_stdout(cli.cmd_keys_list, "table")
    created = _capture_stdout(
        cli.cmd_keys_create,
        "Mission Rotation Key",
        expires_at="2028-05-19T00:00:00Z",
        device_limit=3,
        format="table",
    )
    revoked = _capture_stdout(cli.cmd_keys_revoke, "key_2", "table")

    assert "Mission Runtime Key" in listed
    assert "device_limit=2" in listed
    assert "de_live_efgh_secret_value" in created
    assert "Revoked API key: key_2" in revoked
    assert calls == [
        ("GET", "/v1/api-keys", None),
        (
            "POST",
            "/v1/api-keys",
            {
                "label": "Mission Rotation Key",
                "expires_at": "2028-05-19T00:00:00Z",
                "device_limit": 3,
            },
        ),
        ("DELETE", "/v1/api-keys/key_2", None),
    ]


def test_cmd_team_list_prints_members(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    payload = [
        {
            "user_id": "user_1",
            "name": "Owner",
            "email": "owner@example.com",
            "role": "owner",
            "status": "active",
            "last_active": None,
        }
    ]
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, payload))

    output = _capture_stdout(cli.cmd_team_list, "table")

    assert "Team members (1):" in output
    assert "owner@example.com [owner] — active" in output


def test_cmd_team_invite_prints_invite_summary(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            201,
            {"message": "Invitation sent.", "invite_id": "invite_123"},
        ),
    )

    output = _capture_stdout(cli.cmd_team_invite, "new@example.com", "admin", "table")

    assert "Invitation: invite_123" in output
    assert "Message:    Invitation sent." in output


def test_cmd_team_update_role_prints_transition(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            {"message": "Role updated.", "user_id": "user_123"},
        ),
    )

    output = _capture_stdout(cli.cmd_team_update_role, "user_123", "viewer", "table")

    assert "User ID: user_123" in output
    assert "Message: Role updated." in output


def test_cmd_team_remove_prints_transition(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (204, {}))

    output = _capture_stdout(cli.cmd_team_remove, "user_123", "table")

    assert "Removed: True" in output
    assert "User ID: user_123" in output


def test_cmd_team_audit_logs_prints_entries(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    payload = {
        "entries": [
            {
                "id": "evt_1",
                "timestamp": "2026-05-24T12:30:00Z",
                "actor_email": "owner@example.com",
                "action": "invite_member",
                "resource_type": "team_member",
                "resource_id": "user_2",
                "ip_address": "203.0.113.11",
                "result": "success",
                "metadata": {"policy_snapshot_id": "policy-v1"},
            }
        ],
        "total": 1,
        "page": 1,
        "limit": 25,
        "pages": 1,
    }
    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert (
            path
            == "/v1/audit-logs?page=2&limit=10&actor_email=owner%40example.com&action=invite_member"
            "&resource_type=team_member&result=success&policy_snapshot_id=policy-v1"
            "&schema_snapshot_id=schema-v1&manifest_version=runtime-manifest-v1&request_hash=hash_123"
        )
        return 200, payload

    monkeypatch.setattr(cli, "api_request", _fake_api_request)

    output = _capture_stdout(
        cli.cmd_team_audit_logs,
        "table",
        page=2,
        limit=10,
        actor_email="owner@example.com",
        action="invite_member",
        resource_type="team_member",
        result="success",
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        manifest_version="runtime-manifest-v1",
        request_hash="hash_123",
    )

    assert "Audit log entries (1 total, page 1/1):" in output
    assert "invite_member team_member [success]" in output
    assert '{"policy_snapshot_id": "policy-v1"}' in output


def test_cmd_team_audit_artifacts_prints_entries(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    payload = {
        "entries": [
            {
                "id": "evt_1",
                "timestamp": "2026-05-24T12:30:00Z",
                "actor_email": "owner@example.com",
                "action": "invite_member",
                "resource_type": "team_member",
                "resource_id": "user_2",
                "ip_address": "203.0.113.11",
                "result": "success",
                "content_hash": "content_hash_1",
                "metadata": {"policy_snapshot_id": "policy-v1"},
            }
        ],
        "total": 1,
        "page": 1,
        "limit": 5,
        "pages": 1,
    }

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert (
            path
            == "/v1/audit-logs/artifacts?page=1&limit=5&actor_email=owner%40example.com&action=invite_member"
            "&resource_type=team_member&result=success&policy_snapshot_id=policy-v1"
            "&schema_snapshot_id=schema-v1&manifest_version=runtime-manifest-v1&request_hash=hash_123"
            "&content_hash=content_hash_1"
        )
        return 200, payload

    monkeypatch.setattr(cli, "api_request", _fake_api_request)

    output = _capture_stdout(
        cli.cmd_team_audit_artifacts,
        "table",
        page=1,
        limit=5,
        actor_email="owner@example.com",
        action="invite_member",
        resource_type="team_member",
        result="success",
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        manifest_version="runtime-manifest-v1",
        request_hash="hash_123",
        content_hash="content_hash_1",
    )

    assert "Audit artifacts (1 total, page 1/1):" in output
    assert "content_hash=content_hash_1" in output
    assert '{"policy_snapshot_id": "policy-v1"}' in output


def test_cmd_execution_policy_get_prints_policy(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    payload = {
        "org_id": "org_123",
        "min_confidence": 0.75,
        "risk_floor": 25000.0,
        "require_calibration": True,
        "allow_reexecution": False,
        "snapshot_id": "execution-policy-v1-r2:abcd1234abcd1234",
        "revision": 2,
        "updated_at": "2026-05-24T12:30:00Z",
    }
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, payload))

    output = _capture_stdout(cli.cmd_execution_policy_get, "table")

    assert "Org ID:               org_123" in output
    assert "Min confidence:       0.75" in output
    assert "Require calibration:  True" in output
    assert "Snapshot ID:          execution-policy-v1-r2:abcd1234abcd1234" in output


def test_cmd_execution_policy_snapshots_prints_summary(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    payload = {
        "org_id": "org_123",
        "total_snapshots": 2,
        "data": [
            {
                "snapshot_id": "execution-policy-v1-r2:abcd1234abcd1234",
                "revision": 2,
                "min_confidence": 0.75,
                "risk_floor": 25000.0,
            },
            {
                "snapshot_id": "execution-policy-v1-r1:1111222233334444",
                "revision": 1,
                "min_confidence": 0.7,
                "risk_floor": 20000.0,
            },
        ],
    }
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, payload))

    output = _capture_stdout(cli.cmd_execution_policy_snapshots, "table")

    assert "Execution Policy Snapshots: 2" in output
    assert "r2 execution-policy-v1-r2:abcd1234abcd1234 min_conf=0.75 risk_floor=25000.0" in output
    assert "r1 execution-policy-v1-r1:1111222233334444 min_conf=0.7 risk_floor=20000.0" in output


def test_cmd_execution_policy_update_patches_request_file_and_prints_policy(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "execution_policy.json"
    request_path.write_text(
        json.dumps(
            {
                "min_confidence": 0.8,
                "risk_floor": 15000.0,
                "require_calibration": False,
                "allow_reexecution": True,
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        captured["method"] = method
        captured["path"] = path
        captured["body"] = body
        return (
            200,
            {
                "org_id": "org_123",
                "min_confidence": 0.8,
                "risk_floor": 15000.0,
                "require_calibration": False,
                "allow_reexecution": True,
                "snapshot_id": "execution-policy-v1-r3:fedcfedcfedcfedc",
                "revision": 3,
                "updated_at": "2026-05-24T12:35:00Z",
            },
        )

    monkeypatch.setattr(cli, "api_request", _fake_api_request)

    output = _capture_stdout(cli.cmd_execution_policy_update, str(request_path), "table")

    assert captured == {
        "method": "PATCH",
        "path": "/v1/execution/policy",
        "body": {
            "min_confidence": 0.8,
            "risk_floor": 15000.0,
            "require_calibration": False,
            "allow_reexecution": True,
        },
    }
    assert "Org ID:               org_123" in output
    assert "Allow reexecution:    True" in output
    assert "Revision:             3" in output


@pytest.mark.parametrize(
    ("argv", "handler_name", "expected"),
    [
        (["de", "account", "me", "--format", "json"], "cmd_account_me", {"format": "json"}),
        (
            ["de", "account", "update", "account.json", "--format", "json"],
            "cmd_account_update",
            {"request_path": "account.json", "format": "json"},
        ),
        (["de", "account", "usage"], "cmd_account_usage", {"format": "table"}),
        (["de", "account", "limits"], "cmd_account_limits", {"format": "table"}),
        (["de", "account", "distributions"], "cmd_account_distributions", {"format": "table"}),
        (["de", "account", "templates"], "cmd_account_templates", {"format": "table"}),
    ],
)
def test_main_dispatches_account_commands(
    monkeypatch,
    argv: list[str],
    handler_name: str,
    expected: dict[str, object],
) -> None:
    called: dict[str, object] = {}

    if handler_name == "cmd_account_update":
        def _fake_cmd(request_path: str, format: str = "table") -> None:
            called["request_path"] = request_path
            called["format"] = format
    else:
        def _fake_cmd(format: str = "table") -> None:
            called["format"] = format

    monkeypatch.setattr(cli, handler_name, _fake_cmd)
    monkeypatch.setattr(cli.sys, "argv", argv)

    cli.main()

    assert called == expected


@pytest.mark.parametrize(
    ("argv", "handler_name", "expected"),
    [
        (
            ["de", "billing", "info", "--format", "json"],
            "cmd_billing_info",
            {"format": "json"},
        ),
        (
            ["de", "billing", "checkout", "pro"],
            "cmd_billing_checkout",
            {"plan": "pro", "format": "table"},
        ),
        (
            ["de", "billing", "portal"],
            "cmd_billing_portal",
            {"format": "table"},
        ),
    ],
)
def test_main_dispatches_billing_commands(
    monkeypatch,
    argv: list[str],
    handler_name: str,
    expected: dict[str, object],
) -> None:
    called: dict[str, object] = {}

    if handler_name == "cmd_billing_checkout":
        def _fake_cmd(plan: str | None = None, format: str = "table") -> None:
            called["plan"] = plan
            called["format"] = format
    else:
        def _fake_cmd(format: str = "table") -> None:
            called["format"] = format

    monkeypatch.setattr(cli, handler_name, _fake_cmd)
    monkeypatch.setattr(cli.sys, "argv", argv)

    cli.main()

    assert called == expected


def test_main_dispatches_credit_refresh_commands(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd(request_path: str, format: str = "table") -> None:
        called["request_path"] = request_path
        called["format"] = format

    monkeypatch.setattr(cli, "cmd_credits_refresh", _fake_cmd)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["de", "credits", "refresh", "/tmp/credits-refresh.json", "--format", "json"],
    )

    cli.main()

    assert called == {"request_path": "/tmp/credits-refresh.json", "format": "json"}


def test_main_dispatches_metering_commands(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd(request_path: str, format: str = "table") -> None:
        called["request_path"] = request_path
        called["format"] = format

    monkeypatch.setattr(cli, "cmd_metering_ingest", _fake_cmd)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["de", "metering", "ingest", "/tmp/metering.json", "--format", "json"],
    )

    cli.main()

    assert called == {"request_path": "/tmp/metering.json", "format": "json"}


@pytest.mark.parametrize(
    ("argv", "handler_name", "expected"),
    [
        (
            ["de", "team", "list", "--format", "json"],
            "cmd_team_list",
            {"format": "json"},
        ),
        (
            ["de", "team", "invite", "new@example.com", "admin"],
            "cmd_team_invite",
            {"email": "new@example.com", "role": "admin", "format": "table"},
        ),
        (
            ["de", "team", "update-role", "user_123", "viewer"],
            "cmd_team_update_role",
            {"user_id": "user_123", "role": "viewer", "format": "table"},
        ),
        (
            ["de", "team", "remove", "user_123", "--format", "json"],
            "cmd_team_remove",
            {"user_id": "user_123", "format": "json"},
        ),
        (
            ["de", "team", "audit-logs"],
            "cmd_team_audit_logs",
            {
                "page": 1,
                "limit": 25,
                "format": "table",
                "actor_email": None,
                "action": None,
                "resource_type": None,
                "result": None,
                "policy_snapshot_id": None,
                "schema_snapshot_id": None,
                "manifest_version": None,
                "request_hash": None,
            },
        ),
        (
            ["de", "team", "audit-artifacts"],
            "cmd_team_audit_artifacts",
            {
                "page": 1,
                "limit": 25,
                "format": "table",
                "actor_email": None,
                "action": None,
                "resource_type": None,
                "result": None,
                "policy_snapshot_id": None,
                "schema_snapshot_id": None,
                "manifest_version": None,
                "request_hash": None,
                "content_hash": None,
            },
        ),
    ],
)
def test_main_dispatches_team_commands(
    monkeypatch,
    argv: list[str],
    handler_name: str,
    expected: dict[str, object],
) -> None:
    called: dict[str, object] = {}

    def _fake_cmd(*args: object, **kwargs: object) -> None:
        if handler_name == "cmd_team_invite":
            called["email"] = args[0]
            called["role"] = args[1]
            called["format"] = args[2]
        elif handler_name == "cmd_team_update_role":
            called["user_id"] = args[0]
            called["role"] = args[1]
            called["format"] = args[2]
        elif handler_name == "cmd_team_remove":
            called["user_id"] = args[0]
            called["format"] = args[1]
        elif handler_name in {"cmd_team_audit_logs", "cmd_team_audit_artifacts"}:
            called["format"] = args[0] if args else kwargs.get("format", "table")
            called.update(kwargs)
        else:
            called["format"] = args[0] if args else "table"

    monkeypatch.setattr(cli, handler_name, _fake_cmd)
    monkeypatch.setattr(cli.sys, "argv", argv)

    cli.main()

    assert called == expected


@pytest.mark.parametrize(
    ("argv", "handler_name", "expected"),
    [
        (
            ["de", "devices", "list", "--format", "json"],
            "cmd_devices_list",
            {"format": "json"},
        ),
        (
            ["de", "devices", "revoke", "reg_123"],
            "cmd_devices_revoke",
            {"registration_id": "reg_123", "format": "table"},
        ),
    ],
)
def test_main_dispatches_device_commands(
    monkeypatch,
    argv: list[str],
    handler_name: str,
    expected: dict[str, object],
) -> None:
    called: dict[str, object] = {}

    if handler_name == "cmd_devices_revoke":
        def _fake_cmd(registration_id: str, format: str = "table") -> None:
            called["registration_id"] = registration_id
            called["format"] = format
    else:
        def _fake_cmd(format: str = "table") -> None:
            called["format"] = format

    monkeypatch.setattr(cli, handler_name, _fake_cmd)
    monkeypatch.setattr(cli.sys, "argv", argv)

    cli.main()

    assert called == expected


@pytest.mark.parametrize(
    ("argv", "handler_name", "expected"),
    [
        (
            ["de", "execution-policy", "get", "--format", "json"],
            "cmd_execution_policy_get",
            {"format": "json"},
        ),
        (
            ["de", "execution-policy", "snapshots"],
            "cmd_execution_policy_snapshots",
            {"format": "table"},
        ),
        (
            ["de", "execution-policy", "update", "policy.json"],
            "cmd_execution_policy_update",
            {"request_path": "policy.json", "format": "table"},
        ),
    ],
)
def test_main_dispatches_execution_policy_commands(
    monkeypatch,
    argv: list[str],
    handler_name: str,
    expected: dict[str, object],
) -> None:
    called: dict[str, object] = {}

    if handler_name == "cmd_execution_policy_update":
        def _fake_cmd(request_path: str, format: str = "table") -> None:
            called["request_path"] = request_path
            called["format"] = format
    else:
        def _fake_cmd(format: str = "table") -> None:
            called["format"] = format

    monkeypatch.setattr(cli, handler_name, _fake_cmd)
    monkeypatch.setattr(cli.sys, "argv", argv)

    cli.main()

    assert called == expected


@pytest.mark.parametrize(
    ("argv", "handler_name", "expected"),
    [
        (["de", "keys", "list", "--format", "json"], "cmd_keys_list", {"format": "json"}),
        (
            ["de", "keys", "create", "Mission Rotation Key", "--device-limit", "3"],
            "cmd_keys_create",
            {
                "label": "Mission Rotation Key",
                "expires_at": None,
                "device_limit": 3,
                "format": "table",
            },
        ),
        (
            ["de", "keys", "revoke", "key_2", "--format", "json"],
            "cmd_keys_revoke",
            {"key_id": "key_2", "format": "json"},
        ),
    ],
)
def test_main_dispatches_key_commands(
    monkeypatch,
    argv: list[str],
    handler_name: str,
    expected: dict[str, object],
) -> None:
    called: dict[str, object] = {}

    if handler_name == "cmd_keys_create":
        def _fake_cmd(
            label: str,
            *,
            expires_at: str | None = None,
            device_limit: int | None = None,
            format: str = "table",
        ) -> None:
            called["label"] = label
            called["expires_at"] = expires_at
            called["device_limit"] = device_limit
            called["format"] = format
    elif handler_name == "cmd_keys_revoke":
        def _fake_cmd(key_id: str, format: str = "table") -> None:
            called["key_id"] = key_id
            called["format"] = format
    else:
        def _fake_cmd(format: str = "table") -> None:
            called["format"] = format

    monkeypatch.setattr(cli, handler_name, _fake_cmd)
    monkeypatch.setattr(cli.sys, "argv", argv)

    cli.main()

    assert called == expected


