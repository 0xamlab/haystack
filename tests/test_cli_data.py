from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy

import pytest

from apps.cli import main as cli
from apps.platform_contract import load_platform_contract_manifest
from tests._manifest_backed_integrations import (
    MANIFEST_BACKED_INTEGRATIONS_DISPLAY,
    MANIFEST_BACKED_READ_ONLY_DISPLAY,
    assert_manifest_backed_integrations,
)


def _capture_stdout(fn, *args, **kwargs) -> str:  # type: ignore[no-untyped-def]
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args, **kwargs)
    return buf.getvalue()


def _capture_stderr(fn, *args, **kwargs) -> str:  # type: ignore[no-untyped-def]
    buf = io.StringIO()
    with redirect_stderr(buf):
        fn(*args, **kwargs)
    return buf.getvalue()


def _platform_contract_payload() -> dict[str, object]:
    return deepcopy(load_platform_contract_manifest())


def test_cmd_data_connect_with_request_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "connect.json"
    request_path.write_text(
        json.dumps(
            {
                "connection_type": "file_upload",
                "dataset_name": "Sales",
                "csv": "amount\n10\n20\n",
            }
        )
    )

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/data/connect"
        assert body["dataset_name"] == "Sales"
        return 200, {
            "status": "ready",
            "dataset_id": "ds_sales",
            "dataset_name": "Sales",
            "connection_type": "file_upload",
            "provider": "file",
            "visibility": "private",
            "schema_summary": {
                "row_count": 2,
                "columns": 1,
                "roles_summary": {"derived_measure": 1},
            },
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_data_connect, str(request_path), "table")
    assert "Dataset ID" in output
    assert "ds_sales" in output


def test_cmd_data_list_prints_datasets(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            {
                "datasets": [
                    {
                        "dataset_id": "ds_1",
                        "dataset_name": "Orders",
                        "visibility": "private",
                        "row_count": 10,
                        "columns": 3,
                    },
                ]
            },
        ),
    )
    output = _capture_stdout(cli.cmd_data_list, "table")
    assert "Datasets (1 returned / 1 total)" in output
    assert "ds_1" in output


def test_cmd_data_list_supports_discovery_filters_and_compact(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert (
            path
            == "/v1/data?page=1&limit=5&search=otp&status=ready&source_name=ops_postgres&compact=1"
        )
        return 200, {
            "datasets": [
                {
                    "dataset_id": "ds_otp",
                    "name": "OTP Monthly",
                    "status": "ready",
                    "source_names": ["ops_postgres"],
                    "column_count": 42,
                    "registered_at": "2026-05-20T10:00:00Z",
                }
            ],
            "total": 12,
            "matched_total": 1,
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(
        cli.cmd_data_list,
        "table",
        search="otp",
        status_filter="ready",
        source_name="ops_postgres",
        page=1,
        limit=5,
        compact=True,
    )
    assert "1 matched / 12 total" in output
    assert "OTP Monthly" in output
    assert "ops_postgres" in output


def test_cmd_data_summary_prints_low_token_summary(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            {
                "dataset_id": "ds_otp",
                "name": "OTP Monthly",
                "status": "ready",
                "source_names": ["ops_postgres"],
                "row_count": 1200,
                "column_count": 42,
                "registered_at": "2026-05-20T10:00:00Z",
                "query_hints": ["otp_rate", "flight_month"],
            },
        ),
    )
    output = _capture_stdout(cli.cmd_data_summary, "ds_otp", "table")
    assert "Dataset summary: OTP Monthly (ds_otp)" in output
    assert "otp_rate" in output
    assert "1200 / 42" in output


def test_cmd_connectors_create_posts_request_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "connector_create.json"
    request_path.write_text(
        json.dumps(
            {
                "name": "Orders REST",
                "connector_type": "rest",
                "config": {"url": "http://127.0.0.1:9999/payload.json", "data_path": "items"},
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        captured["method"] = method
        captured["path"] = path
        captured["body"] = body
        return 201, {
            "id": "conn_123",
            "name": "Orders REST",
            "connector_type": "rest",
            "status": "untested",
            "visibility": "private",
            "description": None,
            "last_tested_at": None,
            "created_at": "2026-05-25T12:00:00Z",
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)

    output = _capture_stdout(cli.cmd_connectors_create, str(request_path), "table")

    assert captured == {
        "method": "POST",
        "path": "/v1/connectors",
        "body": {
            "name": "Orders REST",
            "connector_type": "rest",
            "config": {"url": "http://127.0.0.1:9999/payload.json", "data_path": "items"},
        },
    }
    assert "Connector ID:     conn_123" in output
    assert "Type:             rest" in output


def test_cmd_connectors_list_prints_inventory(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/connectors?page=2&limit=10"
        return 200, [
            {
                "id": "conn_123",
                "name": "Orders REST",
                "connector_type": "rest",
                "status": "live",
            }
        ]

    monkeypatch.setattr(cli, "api_request", _fake_api_request)

    output = _capture_stdout(cli.cmd_connectors_list, page=2, limit=10, format="table")

    assert "Connectors (1 total):" in output
    assert "conn_123 [rest] Orders REST status=live" in output


@pytest.mark.parametrize(
    ("func_name", "path", "payload", "expected_fragment"),
    [
        (
            "cmd_connectors_get",
            "/v1/connectors/conn_123",
            {
                "id": "conn_123",
                "name": "Orders REST",
                "connector_type": "rest",
                "status": "untested",
                "visibility": "private",
                "description": "Connector description",
                "last_tested_at": None,
                "created_at": "2026-05-25T12:00:00Z",
            },
            "Orders REST",
        ),
        (
            "cmd_connectors_update",
            "/v1/connectors/conn_123",
            {
                "id": "conn_123",
                "name": "Orders REST Updated",
                "connector_type": "rest",
                "status": "untested",
                "visibility": "private",
                "description": "Updated description",
                "last_tested_at": None,
                "created_at": "2026-05-25T12:00:00Z",
            },
            "Orders REST Updated",
        ),
        (
            "cmd_connectors_test",
            "/v1/connectors/conn_123/test",
            {
                "success": True,
                "status": "live",
                "latency_ms": 12.5,
                "recoverable": False,
                "message": "Connector reachable",
            },
            "Connector reachable",
        ),
        (
            "cmd_connectors_browse",
            "/v1/connectors/conn_123/browse",
            {
                "connector_type": "rest",
                "total": 2,
                "message": "Discovered 2 items",
                "items": [{"name": "orders"}, {"name": "customers"}],
            },
            "Discovered 2 items",
        ),
    ],
)
def test_connector_commands_render_table_output(
    monkeypatch,
    tmp_path,
    func_name: str,
    path: str,
    payload: dict[str, object],
    expected_fragment: str,
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "connector_update.json"
    request_path.write_text(json.dumps({"name": "Orders REST Updated"}), encoding="utf-8")

    def _fake_api_request(method: str, request_path_value: str, body=None):
        expected_method = "GET"
        expected_body = None
        if func_name == "cmd_connectors_update":
            expected_method = "PATCH"
            expected_body = {"name": "Orders REST Updated"}
        elif func_name == "cmd_connectors_test":
            expected_method = "POST"
        assert (method, request_path_value) == (expected_method, path)
        assert body == expected_body
        return 200, payload

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    func = getattr(cli, func_name)
    if func_name == "cmd_connectors_update":
        output = _capture_stdout(func, "conn_123", str(request_path), "table")
    else:
        output = _capture_stdout(func, "conn_123", "table")

    assert expected_fragment in output


def test_cmd_connectors_delete_prints_deleted_payload(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert (method, path, body) == ("DELETE", "/v1/connectors/conn_123", None)
        return 204, {}

    monkeypatch.setattr(cli, "api_request", _fake_api_request)

    output = _capture_stdout(cli.cmd_connectors_delete, "conn_123", "json")

    assert '"connector_id": "conn_123"' in output
    assert '"deleted": true' in output


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


@pytest.mark.parametrize(
    ("func_name", "path", "payload", "expected_fragment"),
    [
        (
            "cmd_connectors_preview_test",
            "/v1/connectors/test",
            {
                "success": True,
                "status": "live",
                "latency_ms": 9.25,
                "recoverable": False,
                "message": "Inline connector reachable",
            },
            "Inline connector reachable",
        ),
        (
            "cmd_connectors_preview_browse",
            "/v1/connectors/browse",
            {
                "connector_type": "rest",
                "total": 2,
                "message": "Preview discovered 2 items",
                "items": [{"name": "orders"}, {"name": "customers"}],
            },
            "Preview discovered 2 items",
        ),
    ],
)
def test_connector_preview_commands_post_inline_request(
    monkeypatch,
    tmp_path,
    func_name: str,
    path: str,
    payload: dict[str, object],
    expected_fragment: str,
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "connector_preview.json"
    request_path.write_text(
        json.dumps(
            {
                "connector_type": "rest",
                "config": {"url": "http://127.0.0.1:9999/payload.json", "data_path": "items"},
            }
        ),
        encoding="utf-8",
    )

    def _fake_api_request(method: str, request_path_value: str, body=None):
        assert (method, request_path_value) == ("POST", path)
        assert body == {
            "connector_type": "rest",
            "config": {"url": "http://127.0.0.1:9999/payload.json", "data_path": "items"},
        }
        return 200, payload

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(getattr(cli, func_name), str(request_path), "table")

    assert expected_fragment in output


def test_cmd_llm_models_prints_available_models(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            {
                "data": [
                    {
                        "id": "text.tokenizer",
                        "runtime_module": "tokenizer",
                        "capabilities": ["tokenize", "count_tokens"],
                        "supported_endpoints": ["/v1/models", "/v1/tokenize"],
                    },
                    {
                        "id": "embeddings.cosine_similarity",
                        "runtime_module": "embeddings",
                        "capabilities": ["similarity"],
                        "supported_endpoints": ["/v1/embeddings/similarity", "/v1/rerank"],
                    },
                    {
                        "id": "provider.router",
                        "runtime_module": "provider.router",
                        "capabilities": ["chat_completions", "embeddings"],
                        "supported_endpoints": [
                            "/v1/models",
                            "/v1/chat/completions",
                            "/v1/embeddings",
                        ],
                        "provider_backend": "router",
                        "routing_targets": ["provider.primary"],
                        "resolved_routing_targets": ["provider.primary"],
                        "chat_routing_targets": ["provider.fast", "provider.primary"],
                        "resolved_chat_routing_targets": [
                            "provider.fast",
                            "provider.primary",
                        ],
                        "embedding_routing_targets": ["provider.primary"],
                        "resolved_embedding_routing_targets": ["provider.primary"],
                        "routing_fallback_policy": "retryable_only",
                        "chat_routing_fallback_policy": "retryable_only",
                        "embedding_routing_fallback_policy": "disabled",
                        "routing_fallback_on": ["provider_rate_limited", "provider_timeout"],
                        "chat_routing_fallback_on": ["provider_rate_limited"],
                        "embedding_routing_fallback_on": ["provider_backend_error"],
                        "routing_max_attempts": 2,
                        "chat_routing_max_attempts": 2,
                        "embedding_routing_max_attempts": 1,
                        "timeout_seconds": 18.0,
                        "chat_timeout_seconds": 12.5,
                        "embedding_timeout_seconds": 9.0,
                        "required_provider_headers": ["OpenAI-Organization"],
                        "chat_required_provider_headers": [
                            "OpenAI-Organization",
                            "X-Groq-Project",
                        ],
                        "embedding_required_provider_headers": ["OpenAI-Organization"],
                        "provider_auth_env_vars": ["OPENAI_API_KEY", "OPENAI_ORG_ID"],
                        "chat_provider_auth_env_vars": [
                            "GROQ_API_KEY",
                            "GROQ_PROJECT_ID",
                            "OPENAI_API_KEY",
                            "OPENAI_ORG_ID",
                        ],
                        "embedding_provider_auth_env_vars": [
                            "OPENAI_API_KEY",
                            "OPENAI_ORG_ID",
                        ],
                        "provider_auth_configured": True,
                        "chat_provider_auth_configured": True,
                        "embedding_provider_auth_configured": False,
                    },
                ]
            },
        ),
    )

    output = _capture_stdout(cli.cmd_llm_models, "table")

    assert "Algenta models (3 available)" in output
    assert "text.tokenizer  [tokenizer]" in output
    assert "capabilities: tokenize, count_tokens" in output
    assert "/v1/embeddings/similarity, /v1/rerank" in output
    assert "provider.router  [provider.router]" in output
    assert "provider:     router" in output
    assert "declared:     provider.primary" in output
    assert "chat route:   provider.fast, provider.primary" in output
    assert "chat leafs:   provider.fast, provider.primary" in output
    assert "embed route:  provider.primary" in output
    assert "embed leafs:  provider.primary" in output
    assert "fallback:     retryable_only" in output
    assert "chat failover: retryable_only" in output
    assert "embed failover: disabled" in output
    assert "on errors:    provider_rate_limited, provider_timeout" in output
    assert "chat on:      provider_rate_limited" in output
    assert "embed on:     provider_backend_error" in output
    assert "attempts:     2" in output
    assert "chat tries:   2" in output
    assert "embed tries:  1" in output
    assert "timeout:      18.0s" in output
    assert "chat timeout: 12.5s" in output
    assert "embed timeout: 9.0s" in output
    assert "headers:      OpenAI-Organization" in output
    assert "chat headers: OpenAI-Organization, X-Groq-Project" in output
    assert "embed headers: OpenAI-Organization" in output
    assert "auth envs:    OPENAI_API_KEY, OPENAI_ORG_ID" in output
    assert "chat envs:    GROQ_API_KEY, GROQ_PROJECT_ID, OPENAI_API_KEY, OPENAI_ORG_ID" in output
    assert "embed envs:   OPENAI_API_KEY, OPENAI_ORG_ID" in output
    assert "auth ready:   True" in output
    assert "chat ready:   True" in output
    assert "embed ready:  False" in output


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


def test_cmd_llm_tokenize_posts_payload_and_prints_tokens(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/tokenize"
        assert body == {"input": "hello world", "model": "text.tokenizer"}
        return 200, {
            "model": "text.tokenizer",
            "tokenizer_kind": "bpe",
            "token_count": 2,
            "tokens": ["hello", "world"],
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_llm_tokenize, "hello world", "text.tokenizer", "table")

    assert "Model:          text.tokenizer" in output
    assert "Tokenizer kind: bpe" in output
    assert "Token count:    2" in output
    assert "Tokens:         hello, world" in output


def test_cmd_llm_resolve_artifact_posts_payload_and_prints_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "artifact_resolve.json"
    request_path.write_text(
        json.dumps(
            {
                "repo_id": "org/model",
                "filename": "model.safetensors",
                "revision": "main",
                "local_files_only": True,
            }
        )
    )

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/artifacts/resolve"
        assert body == {
            "repo_id": "org/model",
            "filename": "model.safetensors",
            "revision": "main",
            "local_files_only": True,
        }
        return 200, {
            "backend": "huggingface_hub",
            "artifact_backend": "safetensors",
            "repo_id": "org/model",
            "filename": "model.safetensors",
            "revision": "main",
            "status": "not_cached",
            "cache_root": "/tmp/algenta-hf-cache",
            "local_files_only": True,
            "auth_configured": True,
            "auth_env_var_used": "HF_TOKEN",
            "resolved_path": None,
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_llm_resolve_artifact, str(request_path), "table")

    assert "Backend:         huggingface_hub" in output
    assert "Filename:        model.safetensors" in output
    assert "Status:          not_cached" in output
    assert "Resolved path:   (not cached)" in output


@pytest.mark.parametrize(
    ("func_name", "path", "payload", "response", "expected_lines"),
    [
        (
            "cmd_llm_chat",
            "/v1/chat/completions",
            {
                "model": "text.tokenizer",
                "messages": [{"role": "user", "content": "hello"}],
            },
            {
                "id": "chatcmpl_123",
                "model": "text.tokenizer",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "HELLO"},
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            },
            ["Completion ID:  chatcmpl_123", "Assistant:      HELLO"],
        ),
        (
            "cmd_llm_responses",
            "/v1/responses",
            {"model": "text.tokenizer", "input": "hello"},
            {
                "id": "resp_123",
                "model": "text.tokenizer",
                "status": "completed",
                "output": [{"type": "output_text", "text": "HELLO"}],
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
            ["Response ID:    resp_123", "Output items:   1"],
        ),
        (
            "cmd_llm_embeddings",
            "/v1/embeddings",
            {"model": "text.lexical_embedding", "input": ["hello"]},
            {
                "model": "text.lexical_embedding",
                "dimensions": 4,
                "data": [{"index": 0, "embedding": [0.1, 0.2, 0.3, 0.4]}],
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
            ["Model:          text.lexical_embedding", "Vectors:        1"],
        ),
        (
            "cmd_llm_embedding_similarity",
            "/v1/embeddings/similarity",
            {
                "model": "embeddings.cosine_similarity",
                "left": [1.0, 0.0],
                "right": [0.5, 0.5],
            },
            {
                "model": "embeddings.cosine_similarity",
                "similarity_metric": "cosine",
                "dimension": 2,
                "score": 0.71,
            },
            ["Similarity metric: cosine", "Score:            0.71"],
        ),
        (
            "cmd_llm_rerank",
            "/v1/rerank",
            {
                "model": "embeddings.cosine_similarity",
                "query_embedding": [1.0, 0.0],
                "documents": [
                    {"id": "doc_1", "embedding": [1.0, 0.0]},
                    {"id": "doc_2", "embedding": [0.0, 1.0]},
                ],
            },
            {
                "model": "embeddings.cosine_similarity",
                "similarity_metric": "cosine",
                "returned_documents": 2,
                "total_documents": 2,
                "data": [
                    {"id": "doc_1", "rank": 1, "score": 1.0},
                    {"id": "doc_2", "rank": 2, "score": 0.0},
                ],
            },
            ["Documents:         2 returned / 2 total", "#1 doc_1 score=1.0"],
        ),
    ],
)
def test_llm_request_commands_post_payload_and_render_summary(
    monkeypatch,
    tmp_path,
    func_name: str,
    path: str,
    payload: dict[str, object],
    response: dict[str, object],
    expected_lines: list[str],
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / f"{func_name}.json"
    request_path.write_text(json.dumps(payload))

    def _fake_api_request(method: str, requested_path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert requested_path == path
        assert body == payload
        return 200, response

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(getattr(cli, func_name), str(request_path), "table")

    for expected in expected_lines:
        assert expected in output


@pytest.mark.parametrize(
    ("func_name", "path", "payload", "streamed_payloads"),
    [
        (
            "cmd_llm_chat",
            "/v1/chat/completions",
            {
                "model": "text.tokenizer",
                "messages": [{"role": "user", "content": "hello"}],
            },
            [
                {
                    "id": "chatcmpl_123",
                    "object": "chat.completion.chunk",
                    "model": "text.tokenizer",
                    "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
                },
                {
                    "id": "chatcmpl_123",
                    "object": "chat.completion.chunk",
                    "model": "text.tokenizer",
                    "choices": [{"index": 0, "delta": {"content": "HELLO"}, "finish_reason": None}],
                },
            ],
        ),
        (
            "cmd_llm_responses",
            "/v1/responses",
            {"model": "text.tokenizer", "input": "hello"},
            [
                {
                    "type": "response.created",
                    "response": {
                        "id": "resp_123",
                        "object": "response",
                        "status": "in_progress",
                        "model": "text.tokenizer",
                    },
                },
                {
                    "type": "response.completed",
                    "response": {
                        "id": "resp_123",
                        "object": "response",
                        "status": "completed",
                        "model": "text.tokenizer",
                    },
                },
            ],
        ),
    ],
)
def test_llm_stream_commands_post_stream_payload_and_render_json_lines(
    monkeypatch,
    tmp_path,
    func_name: str,
    path: str,
    payload: dict[str, object],
    streamed_payloads: list[dict[str, object]],
) -> None:
    request_path = tmp_path / f"{func_name}.json"
    request_path.write_text(json.dumps(payload))

    def _fake_api_stream_request(method: str, requested_path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert requested_path == path
        assert body == {**payload, "stream": True}
        return iter(streamed_payloads)

    monkeypatch.setattr(cli, "api_stream_request", _fake_api_stream_request)
    output = _capture_stdout(getattr(cli, func_name), str(request_path), "json", stream=True)
    lines = [json.loads(line) for line in output.splitlines() if line.strip()]
    assert lines == streamed_payloads


def test_cmd_llm_chat_stream_renders_table_summary(monkeypatch, tmp_path) -> None:
    request_path = tmp_path / "chat-stream.json"
    request_path.write_text(
        json.dumps(
            {
                "model": "text.tokenizer",
                "messages": [{"role": "user", "content": "hello"}],
            }
        )
    )

    monkeypatch.setattr(
        cli,
        "api_stream_request",
        lambda method, path, body=None: iter(  # type: ignore[no-untyped-def]
            [
                {
                    "id": "chatcmpl_123",
                    "object": "chat.completion.chunk",
                    "model": "text.tokenizer",
                    "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
                },
                {
                    "id": "chatcmpl_123",
                    "object": "chat.completion.chunk",
                    "model": "text.tokenizer",
                    "choices": [{"index": 0, "delta": {"content": "HEL"}, "finish_reason": None}],
                },
                {
                    "id": "chatcmpl_123",
                    "object": "chat.completion.chunk",
                    "model": "text.tokenizer",
                    "choices": [{"index": 0, "delta": {"content": "LO"}, "finish_reason": None}],
                },
                {
                    "id": "chatcmpl_123",
                    "object": "chat.completion.chunk",
                    "model": "text.tokenizer",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                },
            ]
        ),
    )

    output = _capture_stdout(cli.cmd_llm_chat, str(request_path), "table", stream=True)

    assert "Completion ID:  chatcmpl_123" in output
    assert "Model:          text.tokenizer" in output
    assert "Assistant:      HELLO" in output
    assert "Finish reason:  stop" in output


def test_cmd_llm_responses_stream_renders_table_summary(monkeypatch, tmp_path) -> None:
    request_path = tmp_path / "responses-stream.json"
    request_path.write_text(json.dumps({"model": "text.tokenizer", "input": "hello"}))

    monkeypatch.setattr(
        cli,
        "api_stream_request",
        lambda method, path, body=None: iter(  # type: ignore[no-untyped-def]
            [
                {
                    "type": "response.created",
                    "response": {
                        "id": "resp_123",
                        "status": "in_progress",
                        "model": "text.tokenizer",
                    },
                },
                {
                    "type": "response.output_item.done",
                    "output_index": 0,
                    "item": {"content": [{"type": "output_text", "text": "HELLO"}]},
                },
                {
                    "type": "response.completed",
                    "response": {
                        "id": "resp_123",
                        "status": "completed",
                        "usage": {"total_tokens": 1},
                    },
                },
            ]
        ),
    )

    output = _capture_stdout(cli.cmd_llm_responses, str(request_path), "table", stream=True)

    assert "Response created: resp_123 status=in_progress model=text.tokenizer" in output
    assert "Output item #0: HELLO" in output
    assert "Response completed: resp_123 status=completed total_tokens=1" in output


def test_cmd_llm_chat_rejects_non_object_request_payload(tmp_path) -> None:
    request_path = tmp_path / "chat.json"
    request_path.write_text(json.dumps(["not", "an", "object"]))

    with pytest.raises(ValueError, match="Request payload must be a JSON object."):
        cli.cmd_llm_chat(str(request_path), "table")


def test_cmd_decision_plan_posts_request_and_prints_plan_summary(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "plan.json"
    payload = {
        "simulation_type": "monte_carlo",
        "parameters": {"trials": 500},
    }
    request_path.write_text(json.dumps(payload))

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/decisions/plan"
        assert body == payload
        return 200, {
            "recommended_action": "expand_capacity",
            "confidence": 0.83,
            "expected_value": 125000.0,
            "risk": {"p5": -1000.0, "p95": 220000.0, "probability_of_loss": 0.12},
            "rationale": "Expected upside dominates downside risk.",
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_decision_plan, str(request_path), "table")

    assert "Recommended:    expand_capacity" in output
    assert "Confidence:     0.83" in output
    assert "Expected value: 125000.0" in output
    assert "Risk:           p5=-1000.0 p95=220000.0 pol=0.12" in output


def test_cmd_decisions_log_posts_request_and_prints_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "decision-log.json"
    payload = {
        "chosen_action": "expand",
        "context": "Launch planning",
        "expected_value": 128000.0,
    }
    request_path.write_text(json.dumps(payload))

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/decisions"
        assert body == payload
        return 201, {
            "id": "decision_123",
            "chosen_action": "expand",
            "confidence": 0.82,
            "expected_value": 128000.0,
            "policy_snapshot_id": "policy-v1",
            "schema_snapshot_id": "schema-v1",
            "manifest_version": "runtime-manifest-v1",
            "created_at": "2026-05-24T12:00:00Z",
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_decisions_log, str(request_path), "table")

    assert "Decision ID:     decision_123" in output
    assert "Chosen action:   expand" in output
    assert "Confidence:      0.82" in output
    assert "Policy snapshot: policy-v1" in output
    assert "Schema snapshot: schema-v1" in output
    assert "Manifest:        runtime-manifest-v1" in output


def test_cmd_decisions_list_gets_paginated_results_and_prints_rows(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/decisions?page=1&limit=20&with_outcome_only=true"
        assert body is None
        return 200, {
            "page": 1,
            "pages": 1,
            "total": 1,
            "limit": 20,
            "decisions": [
                {
                    "id": "decision_123",
                    "chosen_action": "expand",
                    "expected_value": 128000.0,
                    "actual_outcome": 141000.0,
                    "outcome_delta": 13000.0,
                    "policy_snapshot_id": "policy-v1",
                    "schema_snapshot_id": "schema-v1",
                }
            ],
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(
        cli.cmd_decisions_list,
        page=1,
        limit=20,
        with_outcome_only=True,
        format="table",
    )

    assert "Page: 1 / 1  Total: 1  Limit: 20" in output
    assert (
        "decision_123 action=expand expected=128000.0 actual=141000.0 delta=13000.0 "
        "policy=policy-v1 schema=schema-v1"
    ) in output


def test_cmd_decisions_get_fetches_record_and_prints_detail(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/decisions/decision_123"
        assert body is None
        return 200, {
            "id": "decision_123",
            "chosen_action": "expand",
            "context": "Launch planning",
            "expected_value": 128000.0,
            "actual_outcome": 141000.0,
            "outcome_delta": 13000.0,
            "execution_status": "delivered",
            "policy_snapshot_id": "policy-v1",
            "schema_snapshot_id": "schema-v1",
            "manifest_version": "runtime-manifest-v1",
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_decisions_get, "decision_123", "table")

    assert "Decision ID:     decision_123" in output
    assert "Context:         Launch planning" in output
    assert "Execution:       delivered" in output
    assert "Policy snapshot: policy-v1" in output
    assert "Schema snapshot: schema-v1" in output
    assert "Manifest:        runtime-manifest-v1" in output


def test_cmd_decisions_outcome_patches_payload_and_prints_delta(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "decision-outcome.json"
    payload = {"actual_outcome": 141000.0, "outcome_notes": "Launch outperformed baseline"}
    request_path.write_text(json.dumps(payload))

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "PATCH"
        assert path == "/v1/decisions/decision_123/outcome"
        assert body == payload
        return 200, {
            "id": "decision_123",
            "actual_outcome": 141000.0,
            "outcome_delta": 13000.0,
            "policy_snapshot_id": "policy-v1",
            "schema_snapshot_id": "schema-v1",
            "manifest_version": "runtime-manifest-v1",
            "outcome_recorded_at": "2026-05-24T12:30:00Z",
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_decisions_outcome, "decision_123", str(request_path), "table")

    assert "Actual outcome:  141000.0" in output
    assert "Outcome delta:   13000.0" in output
    assert "Policy snapshot: policy-v1" in output
    assert "Schema snapshot: schema-v1" in output
    assert "Manifest:        runtime-manifest-v1" in output


def test_cmd_decisions_execute_posts_payload_and_prints_receipt(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "decision-execute.json"
    payload = {"webhook_url": "https://hooks.example.test/decision", "timeout_seconds": 15}
    request_path.write_text(json.dumps(payload))

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/decisions/decision_123/execute"
        assert body == payload
        return 200, {
            "decision_id": "decision_123",
            "webhook_url": "https://hooks.example.test/decision",
            "execution_status": "delivered",
            "response_code": 202,
            "executed_at": "2026-05-24T12:05:00Z",
            "policy_snapshot_id": "execution-policy-v1-r2:abcd1234abcd1234",
            "schema_snapshot_id": "schema-v1",
            "manifest_version": "runtime-manifest-v1",
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_decisions_execute, "decision_123", str(request_path), "table")

    assert "Decision ID:     decision_123" in output
    assert "Status:          delivered" in output
    assert "Response code:   202" in output
    assert "Policy snapshot: execution-policy-v1-r2:abcd1234abcd1234" in output
    assert "Schema snapshot: schema-v1" in output
    assert "Manifest:        runtime-manifest-v1" in output


def test_cmd_decisions_delete_uses_delete_and_prints_confirmation(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "DELETE"
        assert path == "/v1/decisions/decision_123"
        assert body is None
        return 204, {}

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_decisions_delete, "decision_123", "table")

    assert "Decision deleted: decision_123" in output


def test_cmd_decision_score_posts_request_and_prints_score_summary(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "score.json"
    payload = {
        "request": {
            "mode": "expert",
            "simulation": {
                "variables": [
                    {"name": "outcome", "distribution": "fixed", "params": {"value": 100}}
                ],
                "objective_function": "outcome",
            },
        },
        "scoring_weights": {"expected_value": 0.7, "downside_risk": 0.3},
    }
    request_path.write_text(json.dumps(payload))

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/score"
        assert body == payload
        return 200, {
            "envelope": {
                "recommended_action": "expand_capacity",
                "expected_value": 125000.0,
                "probability_of_loss": 0.12,
            },
            "score": 0.87,
            "score_breakdown": {
                "expected_value_component": 0.61,
                "downside_risk_component": 0.26,
            },
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_decision_score, str(request_path), "table")

    assert "Recommended:    expand_capacity" in output
    assert "Score:          0.87" in output
    assert "Expected value: 125000.0" in output
    assert "Probability of loss: 0.12" in output


def test_cmd_decision_batch_posts_request_and_prints_batch_summary(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "batch.json"
    payload = {
        "items": [
            {
                "mode": "expert",
                "simulation": {
                    "variables": [
                        {"name": "outcome", "distribution": "fixed", "params": {"value": 100}}
                    ],
                    "objective_function": "outcome",
                },
            },
            {
                "mode": "expert",
                "simulation": {
                    "variables": [
                        {"name": "outcome", "distribution": "fixed", "params": {"value": 120}}
                    ],
                    "objective_function": "outcome",
                },
            },
        ]
    }
    request_path.write_text(json.dumps(payload))

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/batch"
        assert body == payload
        return 200, {
            "total": 2,
            "succeeded": 1,
            "failed": 1,
            "results": [
                {
                    "index": 0,
                    "success": True,
                    "envelope": {
                        "recommended_action": "proceed",
                        "expected_value": 125000.0,
                    },
                },
                {"index": 1, "success": False, "error": "bad payload"},
            ],
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_decision_batch, str(request_path), "table")

    assert "Total:          2" in output
    assert "Succeeded:      1" in output
    assert "Failed:         1" in output
    assert "#0 success action=proceed expected_value=125000.0" in output
    assert "#1 failed error=bad payload" in output


def test_cmd_decision_compare_posts_request_and_prints_compare_summary(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "compare.json"
    payload = {
        "scenarios": [
            {
                "name": "base",
                "request": {
                    "mode": "expert",
                    "simulation": {
                        "variables": [
                            {"name": "outcome", "distribution": "fixed", "params": {"value": 100}}
                        ],
                        "objective_function": "outcome",
                    },
                },
            },
            {
                "name": "stretch",
                "request": {
                    "mode": "expert",
                    "simulation": {
                        "variables": [
                            {"name": "outcome", "distribution": "fixed", "params": {"value": 120}}
                        ],
                        "objective_function": "outcome",
                    },
                },
            },
        ]
    }
    request_path.write_text(json.dumps(payload))

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/compare"
        assert body == payload
        return 200, {
            "winner": "stretch",
            "margin": {
                "expected_value_delta": 20.0,
                "probability_of_loss_delta": -0.05,
                "score_delta": 0.11,
            },
            "scenarios": [
                {
                    "name": "base",
                    "envelope": {
                        "recommended_action": "hold",
                        "expected_value": 100.0,
                        "probability_of_loss": 0.2,
                    },
                    "delta_vs_best": {"score_delta": -0.11},
                },
                {
                    "name": "stretch",
                    "envelope": {
                        "recommended_action": "proceed",
                        "expected_value": 120.0,
                        "probability_of_loss": 0.15,
                    },
                    "delta_vs_best": {"score_delta": 0.0},
                },
            ],
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_decision_compare, str(request_path), "table")

    assert "Winner:         stretch" in output
    assert "Margin:         ev=20.0 pol=-0.05 score=0.11" in output
    assert "base: action=hold expected_value=100.0 pol=0.2 delta_score=-0.11" in output
    assert "stretch: action=proceed expected_value=120.0 pol=0.15 delta_score=0.0" in output


@pytest.mark.parametrize(
    ("func_name", "path", "payload", "response", "expected_lines"),
    [
        (
            "cmd_product_decision",
            "/v1/decision",
            {"inputs": [{"name": "revenue", "value": 125000.0}]},
            {
                "decision_id": "decision_product_123",
                "action": "proceed",
                "confidence": 0.82,
                "expected_outcome": 125000.0,
                "probability_of_loss": 0.14,
                "reasoning": "Expected value remains attractive within risk tolerance.",
            },
            ["Decision ID:       decision_product_123", "Action:            proceed"],
        ),
        (
            "cmd_product_agent_run",
            "/v1/agent/run",
            {"task": "Summarize launch blockers"},
            {
                "run_id": "agent_product_123",
                "status": "completed",
                "tools_used": ["search", "simulate"],
                "steps": [{"step": 1, "action": "search"}],
                "latency_ms": 88.4,
            },
            ["Run ID:            agent_product_123", "Tools used:        search, simulate"],
        ),
        (
            "cmd_product_optimize",
            "/v1/optimize",
            {"objective": "maximize_margin", "variables": [{"name": "price", "min": 95, "max": 140}]},
            {
                "optimization_id": "opt_123",
                "status": "completed",
                "objective_value": 183000.0,
                "optimal_values": {"price": 119.0},
                "iterations_run": 1200,
            },
            ["Optimization ID:   opt_123", "Objective value:   183000.0"],
        ),
        (
            "cmd_product_retrieve",
            "/v1/retrieve",
            {"query": "launch checklist", "documents": [{"content": "Launch checklist"}]},
            {
                "retrieval_id": "ret_123",
                "query": "launch checklist",
                "results": [{"rank": 1, "document_id": "doc_1", "relevance_score": 0.93}],
            },
            ["Retrieval ID:      ret_123", "#1 doc_1 score=0.93"],
        ),
        (
            "cmd_product_forecast",
            "/v1/forecast",
            {"metric": "monthly_revenue", "history": [118000.0, 121000.0, 125000.0]},
            {
                "forecast_id": "forecast_123",
                "metric": "monthly_revenue",
                "forecast_mean": 149000.0,
                "total_change_pct": 19.2,
                "periods": [{"period": 1, "forecast": 129000.0}],
            },
            ["Forecast ID:       forecast_123", "Total change pct:  19.2"],
        ),
    ],
)
def test_product_commands_post_request_and_print_summary(
    monkeypatch,
    tmp_path,
    func_name: str,
    path: str,
    payload: dict[str, object],
    response: dict[str, object],
    expected_lines: list[str],
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / f"{func_name}.json"
    request_path.write_text(json.dumps(payload))

    def _fake_api_request(method: str, requested_path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert requested_path == path
        assert body == payload
        return 200, response

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(getattr(cli, func_name), str(request_path), "table")

    for line in expected_lines:
        assert line in output


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


def test_cmd_contract_prints_machine_readable_contract_summary(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (200, _platform_contract_payload()),
    )

    output = _capture_stdout(cli.cmd_contract, "table")

    assert "Algenta contract: v1.3" in output
    assert "/v1/meta/contract" in output
    assert "get_contract() / get_contract()" in output
    assert "getContract() / getContract()" in output
    assert MANIFEST_BACKED_INTEGRATIONS_DISPLAY in output
    assert f"Read-only:       {MANIFEST_BACKED_READ_ONLY_DISPLAY}" in output
    assert "de contract" in output
    assert "get_contract" in output
    assert "record_predicates selectors=column, dimension_hint" in output
    assert "eq, gt, gte, lt, lte, in, is_null, is_not_null" in output


def test_cmd_contract_json_emits_manifest_backed_integration_inventory(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    expected_payload = _platform_contract_payload()
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (200, expected_payload),
    )

    output = _capture_stdout(cli.cmd_contract, "json")
    body = json.loads(output)
    assert_manifest_backed_integrations(body["integrations"])


def test_cmd_contract_falls_back_to_openapi_extension(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):
        assert body is None
        if (method, path) == ("GET", "/v1/meta/contract"):
            return 404, {"error": {"code": "not_found"}}
        if (method, path) == ("GET", "/openapi.json"):
            return 200, {
                "openapi": "3.1.0",
                "x-primary-data-query-contract": {
                    "api": {
                        "contract_endpoint": "/v1/meta/contract",
                        "summary_endpoint": "/v1/data/{dataset_id}/summary",
                        "query_endpoint": "/v1/query",
                        "query_batch_endpoint": "/v1/query/batch",
                        "query_sql_report_endpoint": "/v1/query/sql-report",
                    },
                    "governed_filter_contract": {
                        "kind": "record_predicates",
                        "selector_fields": ["column", "dimension_hint"],
                        "operators": {
                            "scalar": ["eq", "gt", "gte", "lt", "lte"],
                            "list": ["in"],
                            "nullary": ["is_null", "is_not_null"],
                        },
                    },
                    "direct_sdk": {
                        "python": {"contract_method": "get_contract"},
                        "typescript": {"contract_method": "getContract"},
                    },
                    "runtime_sdk": {
                        "python": {"contract_method": "get_contract"},
                        "typescript": {"contract_method": "getContract"},
                    },
                    "cli": {"contract_command": "de contract"},
                    "mcp": {"contract_tool": "get_contract"},
                },
            }
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    monkeypatch.setattr(cli, "_get_base_url", lambda: "https://example.test/self-host")

    output = _capture_stdout(cli.cmd_contract, "table")

    assert "https://example.test/self-host" in output
    assert "/v1/meta/contract" in output
    assert MANIFEST_BACKED_INTEGRATIONS_DISPLAY in output
    assert f"Read-only:       {MANIFEST_BACKED_READ_ONLY_DISPLAY}" in output
    assert "de contract" in output
    assert "record_predicates selectors=column, dimension_hint" in output


def test_cmd_contract_json_falls_back_to_openapi_extension(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):
        assert body is None
        if (method, path) == ("GET", "/v1/meta/contract"):
            return 404, {"error": {"code": "not_found"}}
        if (method, path) == ("GET", "/openapi.json"):
            return 200, {
                "openapi": "3.1.0",
                "x-primary-data-query-contract": {
                    "api": {
                        "contract_endpoint": "/v1/meta/contract",
                        "query_batch_endpoint": "/v1/query/batch",
                    },
                    "mcp": {"contract_tool": "get_contract"},
                },
            }
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    monkeypatch.setattr(cli, "_get_base_url", lambda: "https://example.test/self-host")

    output = _capture_stdout(cli.cmd_contract, "json")
    body = json.loads(output)

    assert body["api_base_url"] == "https://example.test/self-host"
    assert body["mcp_endpoint"] == "https://example.test/self-host/mcp/sse"
    assert body["mcp_tools_endpoint"] == "https://example.test/self-host/mcp/tools"
    assert body["primary_data_query_contract"]["api"]["query_batch_endpoint"] == "/v1/query/batch"
    assert_manifest_backed_integrations(body["integrations"])


def test_cmd_contract_rejects_invalid_openapi_fallback(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):
        assert body is None
        if (method, path) == ("GET", "/v1/meta/contract"):
            return 404, {"error": {"code": "not_found"}}
        if (method, path) == ("GET", "/openapi.json"):
            return 200, {"openapi": "3.1.0"}
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    monkeypatch.setattr(cli, "_get_base_url", lambda: "https://example.test/self-host")

    with pytest.raises(
        RuntimeError,
        match="contract_extension_missing",
    ):
        _capture_stdout(cli.cmd_contract, "table")


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


def test_cmd_contract_rejects_openapi_fallback_missing_api_section(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):
        assert body is None
        if (method, path) == ("GET", "/v1/meta/contract"):
            return 404, {"error": {"code": "not_found"}}
        if (method, path) == ("GET", "/openapi.json"):
            return 200, {
                "openapi": "3.1.0",
                "x-primary-data-query-contract": {
                    "mcp": {"contract_tool": "get_contract"},
                },
            }
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    monkeypatch.setattr(cli, "_get_base_url", lambda: "https://example.test/self-host")

    with pytest.raises(
        RuntimeError,
        match="invalid_contract_payload",
    ):
        _capture_stdout(cli.cmd_contract, "table")


def test_cmd_contract_rejects_openapi_fallback_missing_contract_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):
        assert body is None
        if (method, path) == ("GET", "/v1/meta/contract"):
            return 404, {"error": {"code": "not_found"}}
        if (method, path) == ("GET", "/openapi.json"):
            return 200, {
                "openapi": "3.1.0",
                "x-primary-data-query-contract": {
                    "api": {"query_batch_endpoint": "/v1/query/batch"},
                    "mcp": {"contract_tool": "get_contract"},
                },
            }
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    monkeypatch.setattr(cli, "_get_base_url", lambda: "https://example.test/self-host")

    with pytest.raises(
        RuntimeError,
        match="invalid_contract_payload",
    ):
        _capture_stdout(cli.cmd_contract, "table")


def test_cmd_contract_rejects_openapi_fallback_invalid_nested_contract_override(
    monkeypatch,
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):
        assert body is None
        if (method, path) == ("GET", "/v1/meta/contract"):
            return 404, {"error": {"code": "not_found"}}
        if (method, path) == ("GET", "/openapi.json"):
            return 200, {
                "openapi": "3.1.0",
                "x-primary-data-query-contract": {
                    "api": {"contract_endpoint": "/v1/meta/contract"},
                    "mcp": {"contract_tool": "get_contract"},
                    "runtime_sdk": {
                        "typescript": {"runtime_class": None},
                    },
                },
            }
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    monkeypatch.setattr(cli, "_get_base_url", lambda: "https://example.test/self-host")

    with pytest.raises(
        RuntimeError,
        match="invalid_contract_payload",
    ):
        _capture_stdout(cli.cmd_contract, "table")


def test_cmd_contract_rejects_invalid_payload(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            {
                "contract_version": "v1.3",
                "brand": "Algenta",
                "api_base_url": "https://api.algenta.ai",
                "mcp_endpoint": "https://api.algenta.ai/mcp/sse",
                "mcp_tools_endpoint": "https://api.algenta.ai/mcp/tools",
                "auth_scheme": "bearer_api_key",
                "api_key_prefixes": {"live": "de_live_"},
                "compatibility": {
                    "legacy_headers": ["X-API-Key"],
                    "legacy_env_vars": ["DE_API_KEY", "DE_BASE_URL", "ALGENTA_API_URL"],
                    "legacy_domains": ["api.algenta.io"],
                    "deprecation_window_days": 90,
                },
                "defaults": {
                    "read_only_default": True,
                    "write_confirmation_required": True,
                    "plan_limits": {
                        "enterprise": {"simulations_per_month": "unlimited"},
                    },
                },
                "primary_data_query_contract": {
                    "api": {"contract_endpoint": "/v1/meta/contract"},
                    "mcp": {"contract_tool": "get_contract"},
                },
                "integrations": [],
            },
        ),
    )

    with pytest.raises(
        RuntimeError,
        match=r"invalid payload: api_key_prefixes\.test",
    ):
        _capture_stdout(cli.cmd_contract, "table")


def test_cmd_runtime_manifest_prints_runtime_foundation_summary(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    monkeypatch.setattr(cli, "_RICH", False)
    manifest = get_runtime_manifest().model_dump(mode="json")
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            manifest,
        ),
    )

    output = _capture_stdout(cli.cmd_runtime_manifest, "table")

    assert "Algenta runtime manifest:" in output
    assert "llm-core-v1" in output
    assert "22 shipping / 22 listed" in output
    assert "Functions:       209" in output
    assert "python_sdk, typescript_sdk, cli, mcp" in output
    assert "channel_covered=22" in output
    assert "manifest-listed" in output

    json_output = _capture_stdout(cli.cmd_runtime_manifest, "json")
    payload = json.loads(json_output)
    provider_routing_overhead = next(
        entry for entry in payload["benchmarking"]["classes"] if entry["code"] == "B8"
    )
    assert provider_routing_overhead["description"] == "provider routing overhead"
    assert provider_routing_overhead["evidence_paths"] == [
        "build/provider_routing_overhead_benchmark.json",
        "benchmarks/provider_routing_overhead_benchmark.py",
        "tests/test_provider_routing_overhead_benchmark.py",
    ]
    checkpoint_overhead = next(
        entry for entry in payload["benchmarking"]["classes"] if entry["code"] == "B6"
    )
    assert checkpoint_overhead["description"] == "checkpoint and replay overhead"
    assert checkpoint_overhead["evidence_paths"] == []


def test_cmd_runtime_manifest_rejects_invalid_signed_payload(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    monkeypatch.setattr(cli, "_RICH", False)
    manifest = get_runtime_manifest().model_dump(mode="json")
    manifest["maturity"]["bpe_tokenizer"] = "legendary"
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, manifest))

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: maturity\.bpe_tokenizer",
    ):
        cli.cmd_runtime_manifest("table")


def test_cmd_runtime_validate_prints_release_verdict(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    monkeypatch.setattr(cli, "_RICH", False)
    validation = get_runtime_release_validation().model_dump(mode="json")
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            validation,
        ),
    )

    output = _capture_stdout(cli.cmd_runtime_validate, "table")

    assert "Algenta runtime release validation:" in output
    assert "-> valid" in output
    assert "manifest-listed: pass" in output
    assert "deployment-mode validated: pass" in output


def test_cmd_runtime_validate_prefers_raw_deployment_mode_when_typed_mode_is_missing(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    monkeypatch.setattr(cli, "_RICH", False)
    validation = get_runtime_release_validation().model_dump(mode="json")
    validation["deployment_mode"] = None
    validation["deployment_mode_raw"] = "shadow_realm"
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            validation,
        ),
    )

    output = _capture_stdout(cli.cmd_runtime_validate, "table")

    assert "Deployment:      shadow_realm" in output


def test_cmd_runtime_validate_rejects_invalid_signed_payload(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    monkeypatch.setattr(cli, "_RICH", False)
    validation = get_runtime_release_validation().model_dump(mode="json")
    validation["conditions"][0]["condition"] = "teleport-validated"
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, validation))

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: conditions\.0\.condition",
    ):
        cli.cmd_runtime_validate("table")


def test_cmd_runtime_validate_rejects_invalid_signed_model_instance(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    monkeypatch.setattr(cli, "_RICH", False)
    payload = get_runtime_release_validation().model_copy(deep=True)
    payload.conditions[0].condition = "teleport-validated"
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, payload))

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: conditions\.0\.condition",
    ):
        cli.cmd_runtime_validate("json")


def test_cmd_runtime_admin_modules_prints_signed_module_catalog(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    monkeypatch.setattr(cli, "_RICH", False)
    payload = get_runtime_admin_modules().model_dump(mode="json")
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            payload,
        ),
    )

    output = _capture_stdout(cli.cmd_runtime_admin_modules, "table")

    assert "Algenta runtime module catalog:" in output
    assert "22 modules / 209 functions" in output
    assert "mojo_llm_runtime_core [channel_covered]" in output
    assert "bpe_tokenizer" in output


def test_cmd_runtime_admin_modules_rejects_invalid_signed_payload(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    monkeypatch.setattr(cli, "_RICH", False)
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["proof_matrix"][0]["status"] = "unknown_status"
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, payload))

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: proof_matrix\.0\.status",
    ):
        cli.cmd_runtime_admin_modules("table")


def test_cmd_runtime_admin_modules_rejects_invalid_signed_model_instance(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    monkeypatch.setattr(cli, "_RICH", False)
    payload = get_runtime_admin_modules().model_copy(deep=True)
    payload.modules[0].name = "wormhole_kernel"
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, payload))

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: modules\.0\.name",
    ):
        cli.cmd_runtime_admin_modules("json")


def test_cmd_runtime_admin_benchmarks_prints_signed_benchmark_catalog(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    monkeypatch.setattr(cli, "_RICH", False)
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            payload,
        ),
    )

    output = _capture_stdout(cli.cmd_runtime_admin_benchmarks, "table")

    assert "Algenta runtime benchmark catalog:" in output
    discovery = payload["benchmark_discovery_lane"]
    assert (
        f"{discovery['discovered_source_modules']} source modules / "
        f"{discovery['shipping_manifest_modules']} shipping modules"
    ) in output
    assert "runtime_manifest_load: p95 25.0 ms / ceiling 100.0 ms" in output
    assert "Evaluation:      10 dimensions / 8 methods / 6 release blockers" in output
    assert "Quality gates:   replay=on, tool_call=on, rag=on, decision=on" in output
    assert "Benchmark classes:" in output
    assert "B1: microkernel latency" in output
    assert "benchmarks/summary.json, tests/benchmark_mojo_vs_python.py" in output
    assert "Quality gate benchmark classes:" in output
    assert "B6: checkpoint and replay overhead [evidence: none]" in output
    assert "bpe_tokenizer" in output


def test_cmd_runtime_admin_benchmarks_json_keeps_benchmark_class_evidence_paths(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            payload,
        ),
    )

    output = _capture_stdout(cli.cmd_runtime_admin_benchmarks, "json")
    parsed = json.loads(output)

    provider_routing_overhead = next(
        entry for entry in parsed["benchmarking"]["classes"] if entry["code"] == "B8"
    )
    assert provider_routing_overhead["description"] == "provider routing overhead"
    assert provider_routing_overhead["evidence_paths"] == [
        "build/provider_routing_overhead_benchmark.json",
        "benchmarks/provider_routing_overhead_benchmark.py",
        "tests/test_provider_routing_overhead_benchmark.py",
    ]
    checkpoint_overhead = next(
        entry
        for entry in parsed["quality_gate_benchmark_classes"]
        if entry["code"] == "B6"
    )
    assert checkpoint_overhead["description"] == "checkpoint and replay overhead"
    assert checkpoint_overhead["evidence_paths"] == []
    assert {entry["code"] for entry in parsed["quality_gate_benchmark_classes"]} == {
        "B6",
        "B7",
        "B9",
        "B10",
    }
    assert [entry["name"] for entry in parsed["quality_gate_slo_budgets"]] == [
        "mcp_call_first_party",
        "decision_plan_creation",
        "replay",
    ]
    assert parsed["evaluation_summary"]["replay_gate_enabled"] is True
    assert parsed["evaluation_summary"]["tool_call_quality_gate_enabled"] is True
    assert parsed["evaluation_summary"]["rag_quality_gate_enabled"] is True
    assert parsed["evaluation_summary"]["decision_quality_gate_enabled"] is True


def test_cmd_runtime_admin_benchmarks_rejects_invalid_signed_payload(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    monkeypatch.setattr(cli, "_RICH", False)
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["module_benchmarks"][0]["name"] = "wormhole_kernel"
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, payload))

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: module_benchmarks\.0\.name",
    ):
        cli.cmd_runtime_admin_benchmarks("table")


def test_cmd_runtime_admin_benchmarks_rejects_invalid_signed_model_instance(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    monkeypatch.setattr(cli, "_RICH", False)
    payload = get_runtime_admin_benchmarks().model_copy(deep=True)
    payload.module_benchmarks[0].name = "wormhole_kernel"
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, payload))

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: module_benchmarks\.0\.name",
    ):
        cli.cmd_runtime_admin_benchmarks("json")


def test_cmd_deployments_regions_prints_provider_inventory(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    payload = {
        "providers": [
            {
                "id": "algenta_shared",
                "name": "Algenta Managed",
                "regions": [
                    {"id": "algenta-shared", "label": "Algenta Shared", "location": "Global"}
                ],
            }
        ]
    }
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, payload))

    output = _capture_stdout(cli.cmd_deployments_regions, "table")

    assert "Deployment providers:" in output
    assert "algenta_shared: Algenta Managed" in output
    assert "Algenta Shared" in output


def test_cmd_deployments_get_prints_active_deployment(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    payload = {
        "deployment_id": "dep_123",
        "provider": "algenta_shared",
        "region": "algenta-shared",
        "status": "requested",
        "endpoint_url": "https://example.test/runtime",
        "cost_usd_month": 12.5,
        "billable_cost_usd_month": 15.0,
        "billing_markup_pct": 20.0,
    }
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, payload))

    output = _capture_stdout(cli.cmd_deployments_get, "table")

    assert "Deployment ID:       dep_123" in output
    assert "Provider:            algenta_shared" in output
    assert "Status:              requested" in output


def test_cmd_deployments_create_posts_request_file_and_prints_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "deployment_request.json"
    request_path.write_text(
        json.dumps(
            {
                "provider": "aws",
                "region": "us-east-1",
                "config": {"instance_size": "medium"},
                "billing_markup_pct": 25.0,
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
            202,
            {
                "deployment_id": "dep_123",
                "provider": "aws",
                "region": "us-east-1",
                "status": "requested",
                "billing_markup_pct": 25.0,
            },
        )

    monkeypatch.setattr(cli, "api_request", _fake_api_request)

    output = _capture_stdout(cli.cmd_deployments_create, str(request_path), "table")

    assert captured == {
        "method": "POST",
        "path": "/v1/deployments",
        "body": {
            "provider": "aws",
            "region": "us-east-1",
            "config": {"instance_size": "medium"},
            "billing_markup_pct": 25.0,
        },
    }
    assert "Deployment ID:       dep_123" in output
    assert "Billing markup pct:  25.0" in output


def test_cmd_deployments_cost_prints_cost_summary(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    payload = {
        "deployment_id": "dep_123",
        "provider": "algenta_shared",
        "region": "algenta-shared",
        "year": 2026,
        "month": 5,
        "cost_usd_month": 12.5,
        "billable_cost_usd_month": 15.0,
        "billing_markup_pct": 20.0,
        "last_updated": "2026-05-24T12:30:00Z",
    }
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, payload))

    output = _capture_stdout(cli.cmd_deployments_cost, "dep_123", "table")

    assert "Deployment ID:       dep_123" in output
    assert "Month:               2026-05" in output
    assert "Cost USD/month:      12.5" in output


def test_cmd_deployments_delete_prints_transition(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    payload = {"status": "deprovisioning", "deployment_id": "dep_123"}
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (202, payload))

    output = _capture_stdout(cli.cmd_deployments_delete, "dep_123", "table")

    assert "Deployment ID: dep_123" in output
    assert "Status:        deprovisioning" in output


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


def test_cmd_data_inspect_prints_schema(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            {
                "dataset": {
                    "dataset_name": "Orders",
                    "dataset_id": "ds_1",
                    "visibility": "private",
                    "refreshable": True,
                },
                "schema": {
                    "row_count": 10,
                    "columns": [{"name": "amount", "role": "derived_measure"}],
                },
            },
        ),
    )
    output = _capture_stdout(cli.cmd_data_inspect, "ds_1", "table")
    assert "Dataset: Orders (ds_1)" in output
    assert "amount [derived_measure]" in output


def test_cmd_data_refresh_prints_ready(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            {
                "status": "ready",
                "dataset_id": "ds_1",
                "dataset_name": "Orders",
                "connection_type": "database",
                "provider": "sqlite",
                "visibility": "private",
                "schema_summary": {"row_count": 10, "columns": 1, "roles_summary": {}},
            },
        ),
    )
    output = _capture_stdout(cli.cmd_data_refresh, "ds_1", "table")
    assert "Dataset ID" in output
    assert "sqlite" in output


def test_cmd_data_query_batch_prints_ordered_result_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "batch.json"
    request_path.write_text(
        json.dumps(
            {
                "defaults": {"dataset_id": "otp_events"},
                "queries": [
                    {
                        "key": "overall_otp",
                        "request": {"metric": {"role": "metric", "hint": "otp_rate"}},
                    }
                ],
            }
        )
    )

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/query/batch"
        assert body["defaults"]["dataset_id"] == "otp_events"
        return 200, {
            "request_id": "req_batch",
            "results": [
                {
                    "key": "overall_otp",
                    "data": {"resolved_column": "otp_rate_pct", "row_count": 1},
                    "metadata": {"latency_ms": 12.4},
                },
                {
                    "key": "avg_delay",
                    "error": {"code": "metric_not_found", "message": "missing"},
                },
            ],
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_data_query_batch, str(request_path), "table")
    assert "Query batch request: req_batch" in output
    assert "overall_otp" in output
    assert "metric_not_found" in output


def test_cmd_data_sql_report_prints_report_preview(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "report.json"
    request_path.write_text(
        json.dumps(
            {
                "sources": [{"dataset_id": "ds_otp", "alias": "otp"}],
                "sql": "select flight_month, otp_rate_pct from otp",
                "max_rows": 100,
            }
        )
    )

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/query/sql-report"
        assert body["sources"][0]["alias"] == "otp"
        return 200, {
            "request_id": "req_sql",
            "columns": ["flight_month", "otp_rate_pct"],
            "rows": [{"flight_month": "2026-04-01", "otp_rate_pct": 92.4}],
            "row_count": 1,
            "truncated": False,
            "latency_ms": 24.1,
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_data_sql_report, str(request_path), "table")
    assert "SQL report request: req_sql" in output
    assert "flight_month, otp_rate_pct" in output
    assert "2026-04-01 | 92.4" in output


def test_cmd_data_disconnect_prints_deleted(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            {"dataset_id": "ds_1", "status": "deleted", "connection_deleted": True},
        ),
    )
    output = _capture_stdout(cli.cmd_data_disconnect, "ds_1", assume_yes=True, format="table")
    assert "Deleted dataset ds_1" in output


def test_cmd_data_disconnect_requires_yes_in_noninteractive_mode(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)

    with pytest.raises(SystemExit) as exc_info:
        cli.cmd_data_disconnect("ds_1", assume_yes=False, format="json")

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "--yes" in captured.err


def test_main_dispatches_data_list(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd_data_list(format: str = "table", **kwargs) -> None:  # type: ignore[no-untyped-def]
        called["format"] = format
        called.update(kwargs)

    monkeypatch.setattr(cli, "cmd_data_list", _fake_cmd_data_list)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "de",
            "data",
            "list",
            "--format",
            "json",
            "--search",
            "otp",
            "--status",
            "ready",
            "--source-name",
            "ops_postgres",
            "--page",
            "2",
            "--limit",
            "5",
            "--compact",
        ],
    )

    cli.main()

    assert called == {
        "format": "json",
        "search": "otp",
        "status_filter": "ready",
        "source_name": "ops_postgres",
        "page": 2,
        "limit": 5,
        "compact": True,
    }


def test_main_dispatches_data_summary(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd_data_summary(dataset_id: str, format: str = "table") -> None:
        called["dataset_id"] = dataset_id
        called["format"] = format

    monkeypatch.setattr(cli, "cmd_data_summary", _fake_cmd_data_summary)
    monkeypatch.setattr(cli.sys, "argv", ["de", "data", "summary", "ds_otp", "--format", "json"])

    cli.main()

    assert called == {"dataset_id": "ds_otp", "format": "json"}


def test_main_dispatches_data_query_batch_and_sql_report(monkeypatch) -> None:
    called: list[tuple[str, str, str]] = []

    def _fake_cmd_data_query_batch(request_path: str, format: str = "table") -> None:
        called.append(("batch", request_path, format))

    def _fake_cmd_data_sql_report(request_path: str, format: str = "table") -> None:
        called.append(("sql", request_path, format))

    monkeypatch.setattr(cli, "cmd_data_query_batch", _fake_cmd_data_query_batch)
    monkeypatch.setattr(cli, "cmd_data_sql_report", _fake_cmd_data_sql_report)

    monkeypatch.setattr(
        cli.sys, "argv", ["de", "data", "query-batch", "batch.json", "--format", "json"]
    )
    cli.main()

    monkeypatch.setattr(cli.sys, "argv", ["de", "data", "sql-report", "report.json"])
    cli.main()

    assert called == [("batch", "batch.json", "json"), ("sql", "report.json", "table")]


def test_main_dispatches_connector_commands(monkeypatch) -> None:
    called: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def _record(name: str):
        def _fake(*args: object, **kwargs: object) -> None:
            called.append((name, args, kwargs))

        return _fake

    monkeypatch.setattr(cli, "cmd_connectors_create", _record("create"))
    monkeypatch.setattr(cli, "cmd_connectors_list", _record("list"))
    monkeypatch.setattr(cli, "cmd_connectors_get", _record("get"))
    monkeypatch.setattr(cli, "cmd_connectors_update", _record("update"))
    monkeypatch.setattr(cli, "cmd_connectors_test", _record("test"))
    monkeypatch.setattr(cli, "cmd_connectors_preview_test", _record("preview-test"))
    monkeypatch.setattr(cli, "cmd_connectors_browse", _record("browse"))
    monkeypatch.setattr(cli, "cmd_connectors_preview_browse", _record("preview-browse"))
    monkeypatch.setattr(cli, "cmd_connectors_delete", _record("delete"))

    for argv in (
        ["de", "connectors", "create", "connector.json", "--format", "json"],
        ["de", "connectors", "list", "--page", "2", "--limit", "10", "--format", "json"],
        ["de", "connectors", "get", "conn_123", "--format", "json"],
        ["de", "connectors", "update", "conn_123", "update.json", "--format", "json"],
        ["de", "connectors", "test", "conn_123", "--format", "json"],
        ["de", "connectors", "preview-test", "preview.json", "--format", "json"],
        ["de", "connectors", "browse", "conn_123", "--format", "json"],
        ["de", "connectors", "preview-browse", "preview.json", "--format", "json"],
        ["de", "connectors", "delete", "conn_123", "--format", "json"],
    ):
        monkeypatch.setattr(cli.sys, "argv", argv)
        cli.main()

    assert called == [
        ("create", ("connector.json", "json"), {}),
        ("list", (), {"page": 2, "limit": 10, "format": "json"}),
        ("get", ("conn_123", "json"), {}),
        ("update", ("conn_123", "update.json", "json"), {}),
        ("test", ("conn_123", "json"), {}),
        ("preview-test", ("preview.json", "json"), {}),
        ("browse", ("conn_123", "json"), {}),
        ("preview-browse", ("preview.json", "json"), {}),
        ("delete", ("conn_123", "json"), {}),
    ]


def test_main_dispatches_contract(monkeypatch) -> None:
    called: list[str] = []

    def _fake_cmd_contract(format: str = "table") -> None:
        called.append(format)

    monkeypatch.setattr(cli, "cmd_contract", _fake_cmd_contract)
    monkeypatch.setattr(cli.sys, "argv", ["de", "contract", "--format", "json"])

    cli.main()

    assert called == ["json"]


def test_main_dispatches_llm_models(monkeypatch) -> None:
    called: list[str] = []

    def _fake_cmd_llm_models(format: str = "table") -> None:
        called.append(format)

    monkeypatch.setattr(cli, "cmd_llm_models", _fake_cmd_llm_models)
    monkeypatch.setattr(cli.sys, "argv", ["de", "llm", "models", "--format", "json"])

    cli.main()

    assert called == ["json"]


def test_main_dispatches_llm_tokenize(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd_llm_tokenize(
        text: str, model: str = "text.tokenizer", format: str = "table"
    ) -> None:
        called["text"] = text
        called["model"] = model
        called["format"] = format

    monkeypatch.setattr(cli, "cmd_llm_tokenize", _fake_cmd_llm_tokenize)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "de",
            "llm",
            "tokenize",
            "--input",
            "hello world",
            "--model",
            "text.tokenizer",
            "--format",
            "json",
        ],
    )

    cli.main()

    assert called == {
        "text": "hello world",
        "model": "text.tokenizer",
        "format": "json",
    }


def test_main_dispatches_llm_resolve_artifact(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd_llm_resolve_artifact(request_path: str, format: str = "table") -> None:
        called["request_path"] = request_path
        called["format"] = format

    monkeypatch.setattr(cli, "cmd_llm_resolve_artifact", _fake_cmd_llm_resolve_artifact)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["de", "llm", "resolve-artifact", "artifact.json", "--format", "json"],
    )

    cli.main()

    assert called == {"request_path": "artifact.json", "format": "json"}


def test_main_dispatches_decision_plan(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd_decision_plan(request_path: str, format: str = "table") -> None:
        called["request_path"] = request_path
        called["format"] = format

    monkeypatch.setattr(cli, "cmd_decision_plan", _fake_cmd_decision_plan)
    monkeypatch.setattr(cli.sys, "argv", ["de", "decision", "plan", "plan.json"])

    cli.main()

    assert called == {"request_path": "plan.json", "format": "table"}


@pytest.mark.parametrize(
    ("argv", "handler_name", "expected"),
    [
        (
            ["de", "decisions", "log", "decision.json", "--format", "json"],
            "cmd_decisions_log",
            {"request_path": "decision.json", "format": "json"},
        ),
        (
            ["de", "decisions", "list", "--limit", "20", "--with-outcome-only"],
            "cmd_decisions_list",
            {
                "page": 1,
                "limit": 20,
                "page_size": None,
                "with_outcome_only": True,
                "format": "table",
            },
        ),
        (
            ["de", "decisions", "get", "decision_123"],
            "cmd_decisions_get",
            {"decision_id": "decision_123", "format": "table"},
        ),
        (
            ["de", "decisions", "outcome", "decision_123", "outcome.json", "--format", "json"],
            "cmd_decisions_outcome",
            {
                "decision_id": "decision_123",
                "request_path": "outcome.json",
                "format": "json",
            },
        ),
        (
            ["de", "decisions", "execute", "decision_123", "execute.json"],
            "cmd_decisions_execute",
            {
                "decision_id": "decision_123",
                "request_path": "execute.json",
                "format": "table",
            },
        ),
        (
            ["de", "decisions", "delete", "decision_123", "--format", "json"],
            "cmd_decisions_delete",
            {"decision_id": "decision_123", "format": "json"},
        ),
    ],
)
def test_main_dispatches_decision_memory_commands(
    monkeypatch,
    argv: list[str],
    handler_name: str,
    expected: dict[str, object],
) -> None:
    called: dict[str, object] = {}

    if handler_name == "cmd_decisions_list":
        def _fake_cmd(
            *,
            page: int = 1,
            limit: int | None = None,
            page_size: int | None = None,
            with_outcome_only: bool = False,
            format: str = "table",
        ) -> None:
            called["page"] = page
            called["limit"] = limit
            called["page_size"] = page_size
            called["with_outcome_only"] = with_outcome_only
            called["format"] = format
    elif handler_name in {"cmd_decisions_get", "cmd_decisions_delete"}:
        def _fake_cmd(decision_id: str, format: str = "table") -> None:
            called["decision_id"] = decision_id
            called["format"] = format
    elif handler_name in {"cmd_decisions_outcome", "cmd_decisions_execute"}:
        def _fake_cmd(decision_id: str, request_path: str, format: str = "table") -> None:
            called["decision_id"] = decision_id
            called["request_path"] = request_path
            called["format"] = format
    else:
        def _fake_cmd(request_path: str, format: str = "table") -> None:
            called["request_path"] = request_path
            called["format"] = format

    monkeypatch.setattr(cli, handler_name, _fake_cmd)
    monkeypatch.setattr(cli.sys, "argv", argv)

    cli.main()

    assert called == expected


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
            ["de", "deployments", "regions", "--format", "json"],
            "cmd_deployments_regions",
            {"format": "json"},
        ),
        (
            ["de", "deployments", "get"],
            "cmd_deployments_get",
            {"format": "table"},
        ),
        (
            ["de", "deployments", "create", "deployment.json", "--format", "json"],
            "cmd_deployments_create",
            {"request_path": "deployment.json", "format": "json"},
        ),
        (
            ["de", "deployments", "cost", "dep_123"],
            "cmd_deployments_cost",
            {"deployment_id": "dep_123", "format": "table"},
        ),
        (
            ["de", "deployments", "delete", "dep_123", "--format", "json"],
            "cmd_deployments_delete",
            {"deployment_id": "dep_123", "format": "json"},
        ),
    ],
)
def test_main_dispatches_deployment_commands(
    monkeypatch,
    argv: list[str],
    handler_name: str,
    expected: dict[str, object],
) -> None:
    called: dict[str, object] = {}

    if handler_name == "cmd_deployments_create":
        def _fake_cmd(request_path: str, format: str = "table") -> None:
            called["request_path"] = request_path
            called["format"] = format
    elif handler_name in {"cmd_deployments_cost", "cmd_deployments_delete"}:
        def _fake_cmd(deployment_id: str, format: str = "table") -> None:
            called["deployment_id"] = deployment_id
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


@pytest.mark.parametrize(
    ("argv", "handler_name", "expected"),
    [
        (
            ["de", "decision", "score", "score.json", "--format", "json"],
            "cmd_decision_score",
            {"request_path": "score.json", "format": "json"},
        ),
        (
            ["de", "decision", "batch", "batch.json"],
            "cmd_decision_batch",
            {"request_path": "batch.json", "format": "table"},
        ),
        (
            ["de", "decision", "compare", "compare.json"],
            "cmd_decision_compare",
            {"request_path": "compare.json", "format": "table"},
        ),
    ],
)
def test_main_dispatches_decision_runtime_commands(
    monkeypatch,
    argv: list[str],
    handler_name: str,
    expected: dict[str, object],
) -> None:
    called: dict[str, object] = {}

    def _fake_cmd(request_path: str, format: str = "table") -> None:
        called["request_path"] = request_path
        called["format"] = format

    monkeypatch.setattr(cli, handler_name, _fake_cmd)
    monkeypatch.setattr(cli.sys, "argv", argv)

    cli.main()

    assert called == expected


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


@pytest.mark.parametrize(
    ("argv", "handler_name", "expected"),
    [
        (
            ["de", "product", "decision", "decision.json", "--format", "json"],
            "cmd_product_decision",
            {"request_path": "decision.json", "format": "json"},
        ),
        (
            ["de", "product", "agent-run", "agent-run.json"],
            "cmd_product_agent_run",
            {"request_path": "agent-run.json", "format": "table"},
        ),
        (
            ["de", "product", "optimize", "optimize.json"],
            "cmd_product_optimize",
            {"request_path": "optimize.json", "format": "table"},
        ),
        (
            ["de", "product", "retrieve", "retrieve.json"],
            "cmd_product_retrieve",
            {"request_path": "retrieve.json", "format": "table"},
        ),
        (
            ["de", "product", "forecast", "forecast.json", "--format", "json"],
            "cmd_product_forecast",
            {"request_path": "forecast.json", "format": "json"},
        ),
    ],
)
def test_main_dispatches_product_commands(
    monkeypatch,
    argv: list[str],
    handler_name: str,
    expected: dict[str, object],
) -> None:
    called: dict[str, object] = {}

    def _fake_cmd(request_path: str, format: str = "table") -> None:
        called["request_path"] = request_path
        called["format"] = format

    monkeypatch.setattr(cli, handler_name, _fake_cmd)
    monkeypatch.setattr(cli.sys, "argv", argv)

    cli.main()

    assert called == expected


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (
            ["de", "llm", "chat", "chat.json", "--stream", "--format", "json"],
            {"request_path": "chat.json", "format": "json", "stream": True},
        ),
        (
            ["de", "llm", "responses", "responses.json", "--stream"],
            {"request_path": "responses.json", "format": "table", "stream": True},
        ),
    ],
)
def test_main_dispatches_llm_stream_commands(monkeypatch, argv: list[str], expected: dict[str, object]) -> None:
    called: dict[str, object] = {}

    def _fake_cmd(request_path: str, format: str = "table", *, stream: bool = False) -> None:
        called["request_path"] = request_path
        called["format"] = format
        called["stream"] = stream

    target = "cmd_llm_chat" if argv[2] == "chat" else "cmd_llm_responses"
    monkeypatch.setattr(cli, target, _fake_cmd)
    monkeypatch.setattr(cli.sys, "argv", argv)

    cli.main()

    assert called == expected


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


def test_cmd_runtime_history_prints_recent_events(monkeypatch, tmp_path) -> None:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    ledger = runtime_dir / "history.jsonl"
    ledger.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": 1_700_000_000,
                        "status": "started",
                        "target": "monte_carlo.run",
                        "engine_used": None,
                        "latency_ms": None,
                        "error": None,
                    }
                ),
                json.dumps(
                    {
                        "timestamp": 1_700_000_001,
                        "status": "completed",
                        "target": "monte_carlo.run",
                        "engine_used": "python-fallback",
                        "latency_ms": 12.34,
                        "error": None,
                    }
                ),
            ]
        )
    )
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(runtime_dir))
    output = _capture_stdout(cli.cmd_runtime_history, 10, "table")
    assert "Runtime history (2 events)" in output
    assert "monte_carlo.run" in output
    assert "python-fallback" in output


def test_main_dispatches_runtime_history(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd_runtime_history(limit: int = 20, format: str = "table") -> None:
        called["limit"] = limit
        called["format"] = format

    monkeypatch.setattr(cli, "cmd_runtime_history", _fake_cmd_runtime_history)
    monkeypatch.setattr(
        cli.sys, "argv", ["de", "runtime", "history", "--limit", "5", "--format", "json"]
    )

    cli.main()

    assert called == {"limit": 5, "format": "json"}


def test_main_dispatches_runtime_admin_modules(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd_runtime_admin_modules(format: str = "table") -> None:
        called["format"] = format

    monkeypatch.setattr(cli, "cmd_runtime_admin_modules", _fake_cmd_runtime_admin_modules)
    monkeypatch.setattr(
        cli.sys, "argv", ["de", "runtime", "admin-modules", "--format", "json"]
    )

    cli.main()

    assert called == {"format": "json"}


def test_main_dispatches_runtime_admin_benchmarks(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd_runtime_admin_benchmarks(format: str = "table") -> None:
        called["format"] = format

    monkeypatch.setattr(cli, "cmd_runtime_admin_benchmarks", _fake_cmd_runtime_admin_benchmarks)
    monkeypatch.setattr(
        cli.sys, "argv", ["de", "runtime", "admin-benchmarks", "--format", "json"]
    )

    cli.main()

    assert called == {"format": "json"}
