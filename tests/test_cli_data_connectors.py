"""Tests for CLI connectors commands.

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


