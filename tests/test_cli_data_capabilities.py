"""Tests for CLI capabilities commands.

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


def test_cmd_capabilities_providers_prints_inventory(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    payload = [
        {
            "provider_id": "provider.skill_pack.algenta",
            "provider_type": "skill_pack",
            "name": "Algenta Skill Pack",
            "active": True,
        }
    ]
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, payload))

    output = _capture_stdout(cli.cmd_capabilities_providers, "table")

    assert "Capability providers (1):" in output
    assert "provider.skill_pack.algenta [skill_pack] Algenta Skill Pack active=True" in output


def test_cmd_capabilities_provider_prints_summary(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/capability-providers/provider.skill_pack.algenta"
        return 200, {
            "provider_id": "provider.skill_pack.algenta",
            "provider_type": "skill_pack",
            "name": "Algenta Skill Pack",
            "active": True,
            "supported_execution_owners": ["algenta_managed", "client_managed"],
            "description": "Canonical skill pack provider.",
            "profiles": [
                {
                    "profile_id": "profile.skill_pack.default",
                    "binding_scope_default": "user",
                    "auth_kind": "none",
                }
            ],
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)

    output = _capture_stdout(
        cli.cmd_capabilities_provider,
        "provider.skill_pack.algenta",
        "table",
    )

    assert "Provider ID:      provider.skill_pack.algenta" in output
    assert "Execution owners: algenta_managed, client_managed" in output
    assert "profile.skill_pack.default scope=user auth=none" in output


def test_cmd_capabilities_provider_exits_on_api_error(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            404,
            {
                "error": {
                    "code": "provider_not_found",
                    "message": "Capability provider was not found.",
                }
            },
        ),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.cmd_capabilities_provider("provider.skill_pack.missing", "table")

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Error 404" in captured.err
    assert "provider_not_found" in captured.err


def test_cmd_capabilities_bindings_supports_filters(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert (
            path
            == "/v1/capability-bindings?provider_id=provider.skill_pack.algenta&scope=workspace"
        )
        return 200, [
            {
                "binding_id": "binding-123",
                "provider_id": "provider.skill_pack.algenta",
                "scope": "workspace",
                "status": "ready",
            }
        ]

    monkeypatch.setattr(cli, "api_request", _fake_api_request)

    output = _capture_stdout(
        cli.cmd_capabilities_bindings,
        provider_id="provider.skill_pack.algenta",
        scope="workspace",
        format="table",
    )

    assert "Capability bindings (1):" in output
    assert (
        "binding-123 provider=provider.skill_pack.algenta scope=workspace status=ready"
        in output
    )


def test_cmd_capabilities_list_supports_filters(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert (
            path
            == "/v1/capabilities?kinds=skill&kinds=mcp_tool&provider_ids=provider.skill_pack.algenta"
            "&binding_ids=binding-123"
        )
        return 200, [
            {
                "capability_id": "cap.skill.escalation",
                "kind": "skill",
                "name": "Escalation Skill",
                "execution_owner": "client_managed",
            }
        ]

    monkeypatch.setattr(cli, "api_request", _fake_api_request)

    output = _capture_stdout(
        cli.cmd_capabilities_list,
        kinds=["skill", "mcp_tool"],
        provider_ids=["provider.skill_pack.algenta"],
        binding_ids=["binding-123"],
        format="table",
    )

    assert "Capabilities (1):" in output
    assert "cap.skill.escalation [skill] Escalation Skill owner=client_managed" in output


def test_cmd_capabilities_route_posts_request_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "capability_route.json"
    request_path.write_text(
        json.dumps(
            {
                "objective": "Escalate incident",
                "kinds": ["skill"],
                "artifact_affinities": ["incident"],
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
                "selected_capability_id": "cap.skill.escalation",
                "selected_provider_id": "provider.skill_pack.algenta",
                "selected_binding_id": "binding-123",
                "kind": "skill",
                "execution_owner": "client_managed",
                "requires_approval": False,
                "confidence": 0.93,
                "reason": "Best semantic match.",
            },
        )

    monkeypatch.setattr(cli, "api_request", _fake_api_request)

    output = _capture_stdout(cli.cmd_capabilities_route, str(request_path), "table")

    assert captured == {
        "method": "POST",
        "path": "/v1/capabilities/route",
        "body": {
            "objective": "Escalate incident",
            "kinds": ["skill"],
            "artifact_affinities": ["incident"],
        },
    }
    assert "Capability ID:    cap.skill.escalation" in output
    assert "Execution owner:  client_managed" in output


def test_cmd_capabilities_execute_posts_request_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "capability_execute.json"
    request_path.write_text(
        json.dumps(
            {
                "capability_id": "cap.skill.escalation",
                "binding_id": "binding-123",
                "arguments": {"incident_id": "inc_42"},
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        captured["method"] = method
        captured["path"] = path
        captured["body"] = body
        return 200, {
            "execution_session_id": "exec-123",
            "capability_id": "cap.skill.escalation",
            "provider_id": "provider.skill_pack.algenta",
            "binding_id": "binding-123",
            "execution_owner": "algenta_managed",
            "status": "completed",
            "started_at": "2026-05-29T16:30:00Z",
            "completed_at": "2026-05-29T16:30:01Z",
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)

    output = _capture_stdout(cli.cmd_capabilities_execute, str(request_path), "table")

    assert captured == {
        "method": "POST",
        "path": "/v1/capabilities/execute",
        "body": {
            "capability_id": "cap.skill.escalation",
            "binding_id": "binding-123",
            "arguments": {"incident_id": "inc_42"},
        },
    }
    assert "Execution ID:     exec-123" in output
    assert "Status:           completed" in output


def test_main_capabilities_providers_dispatches_to_command(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_cmd(fmt: str) -> None:
        captured["format"] = fmt

    monkeypatch.setattr(cli, "cmd_capabilities_providers", _fake_cmd)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["de", "capabilities", "providers", "--format", "json"],
    )

    cli.main()

    assert captured == {"format": "json"}


def test_main_capabilities_provider_dispatches_to_command(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_cmd(provider_id: str, fmt: str) -> None:
        captured["provider_id"] = provider_id
        captured["format"] = fmt

    monkeypatch.setattr(cli, "cmd_capabilities_provider", _fake_cmd)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "de",
            "capabilities",
            "provider",
            "provider.skill_pack.algenta",
            "--format",
            "json",
        ],
    )

    cli.main()

    assert captured == {
        "provider_id": "provider.skill_pack.algenta",
        "format": "json",
    }


def test_main_capabilities_bindings_dispatches_to_command(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_cmd(
        *,
        provider_id: str | None = None,
        scope: str | None = None,
        format: str = "table",
    ) -> None:
        captured["provider_id"] = provider_id
        captured["scope"] = scope
        captured["format"] = format

    monkeypatch.setattr(cli, "cmd_capabilities_bindings", _fake_cmd)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "de",
            "capabilities",
            "bindings",
            "--provider-id",
            "provider.skill_pack.algenta",
            "--scope",
            "workspace",
            "--format",
            "json",
        ],
    )

    cli.main()

    assert captured == {
        "provider_id": "provider.skill_pack.algenta",
        "scope": "workspace",
        "format": "json",
    }


def test_main_capabilities_list_dispatches_to_command(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_cmd(
        *,
        kinds: list[str] | None = None,
        provider_ids: list[str] | None = None,
        binding_ids: list[str] | None = None,
        format: str = "table",
    ) -> None:
        captured["kinds"] = kinds
        captured["provider_ids"] = provider_ids
        captured["binding_ids"] = binding_ids
        captured["format"] = format

    monkeypatch.setattr(cli, "cmd_capabilities_list", _fake_cmd)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "de",
            "capabilities",
            "list",
            "--kind",
            "skill,mcp_tool",
            "--provider-id",
            "provider.skill_pack.algenta",
            "--binding-id",
            "binding-123,binding-456",
            "--format",
            "json",
        ],
    )

    cli.main()

    assert captured == {
        "kinds": ["skill", "mcp_tool"],
        "provider_ids": ["provider.skill_pack.algenta"],
        "binding_ids": ["binding-123", "binding-456"],
        "format": "json",
    }


def test_main_capabilities_route_dispatches_to_command(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_cmd(request_path: str, fmt: str) -> None:
        captured["request_path"] = request_path
        captured["format"] = fmt

    monkeypatch.setattr(cli, "cmd_capabilities_route", _fake_cmd)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["de", "capabilities", "route", "request.json", "--format", "json"],
    )

    cli.main()

    assert captured == {"request_path": "request.json", "format": "json"}


def test_main_capabilities_without_subcommand_prints_usage(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.sys, "argv", ["de", "capabilities"])

    cli.main()

    captured = capsys.readouterr()
    assert "Usage: de capabilities" in captured.out
    assert "provider <provider_id>" in captured.out
    assert "--scope <user|workspace|organization>" in captured.out


def test_main_capabilities_execute_dispatches_to_command(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_cmd(request_path: str, fmt: str) -> None:
        captured["request_path"] = request_path
        captured["format"] = fmt

    monkeypatch.setattr(cli, "cmd_capabilities_execute", _fake_cmd)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["de", "capabilities", "execute", "request.json", "--format", "json"],
    )

    cli.main()

    assert captured == {"request_path": "request.json", "format": "json"}


