from __future__ import annotations

import json

import pytest

from apps.mcp_server.tools import connectors


def test_connector_tool_specs_cover_saved_connector_lifecycle() -> None:
    assert connectors.LIST_CONNECTORS_SPEC["name"] == "list_connectors"
    assert connectors.CREATE_CONNECTOR_SPEC["name"] == "create_connector"
    assert connectors.GET_CONNECTOR_SPEC["name"] == "get_connector"
    assert connectors.UPDATE_CONNECTOR_SPEC["name"] == "update_connector"
    assert connectors.TEST_CONNECTOR_SPEC["name"] == "test_connector"
    assert connectors.BROWSE_CONNECTOR_SPEC["name"] == "browse_connector"
    assert connectors.PREVIEW_TEST_CONNECTOR_SPEC["name"] == "preview_test_connector"
    assert connectors.PREVIEW_BROWSE_CONNECTOR_SPEC["name"] == "preview_browse_connector"
    assert connectors.DELETE_CONNECTOR_SPEC["name"] == "delete_connector"
    assert connectors.CREATE_CONNECTOR_SPEC["inputSchema"]["required"] == ["name", "connector_type"]
    assert connectors.GET_CONNECTOR_SPEC["inputSchema"]["required"] == ["connector_id"]


@pytest.mark.anyio
async def test_connector_handlers_forward_canonical_saved_connector_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, object]] = []

    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((method, path, kwargs.get("json")))
        if (method, path) == ("GET", "/v1/connectors?page=2&limit=10"):
            return [
                {
                    "id": "conn_123",
                    "name": "Orders REST",
                    "connector_type": "rest",
                    "status": "live",
                }
            ]
        if (method, path) == ("POST", "/v1/connectors"):
            return {
                "id": "conn_123",
                "name": "Orders REST",
                "connector_type": "rest",
                "status": "untested",
            }
        if (method, path) == ("GET", "/v1/connectors/conn_123"):
            return {
                "id": "conn_123",
                "name": "Orders REST",
                "connector_type": "rest",
                "status": "untested",
            }
        if (method, path) == ("PATCH", "/v1/connectors/conn_123"):
            return {
                "id": "conn_123",
                "name": "Orders REST Updated",
                "connector_type": "rest",
                "status": "untested",
            }
        if (method, path) == ("POST", "/v1/connectors/conn_123/test"):
            return {
                "success": True,
                "status": "live",
                "latency_ms": 9.5,
                "message": "Connector reachable",
            }
        if (method, path) == ("POST", "/v1/connectors/test"):
            return {
                "success": True,
                "status": "live",
                "latency_ms": 8.0,
                "message": "Inline connector reachable",
            }
        if (method, path) == ("GET", "/v1/connectors/conn_123/browse"):
            return {
                "connector_type": "rest",
                "total": 2,
                "message": "Discovered 2 items",
                "items": [{"name": "orders"}, {"name": "customers"}],
            }
        if (method, path) == ("POST", "/v1/connectors/browse"):
            return {
                "connector_type": "rest",
                "total": 2,
                "message": "Preview discovered 2 items",
                "items": [{"name": "orders"}, {"name": "customers"}],
            }
        if (method, path) == ("DELETE", "/v1/connectors/conn_123"):
            return {}
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(connectors, "api", _fake_api)

    listed = json.loads(await connectors.list_connectors_handler({"page": 2, "limit": 10}))
    created = json.loads(
        await connectors.create_connector_handler(
            {
                "name": "Orders REST",
                "connector_type": "rest",
                "config": {"url": "http://127.0.0.1:9999/payload.json", "data_path": "items"},
            }
        )
    )
    fetched = json.loads(await connectors.get_connector_handler({"connector_id": "conn_123"}))
    updated = json.loads(
        await connectors.update_connector_handler(
            {"connector_id": "conn_123", "name": "Orders REST Updated"}
        )
    )
    tested = json.loads(await connectors.test_connector_handler({"connector_id": "conn_123"}))
    preview_tested = json.loads(
        await connectors.preview_test_connector_handler(
            {
                "connector_type": "rest",
                "config": {"url": "http://127.0.0.1:9999/payload.json", "data_path": "items"},
            }
        )
    )
    browsed = json.loads(await connectors.browse_connector_handler({"connector_id": "conn_123"}))
    preview_browsed = json.loads(
        await connectors.preview_browse_connector_handler(
            {
                "connector_type": "rest",
                "config": {"url": "http://127.0.0.1:9999/payload.json", "data_path": "items"},
            }
        )
    )
    deleted = json.loads(await connectors.delete_connector_handler({"connector_id": "conn_123"}))

    assert listed["page"] == 2
    assert listed["connectors"][0]["id"] == "conn_123"
    assert created["id"] == "conn_123"
    assert fetched["name"] == "Orders REST"
    assert updated["name"] == "Orders REST Updated"
    assert tested["status"] == "live"
    assert preview_tested["status"] == "live"
    assert browsed["total"] == 2
    assert preview_browsed["total"] == 2
    assert deleted == {"connector_id": "conn_123", "deleted": True}
    assert calls == [
        ("GET", "/v1/connectors?page=2&limit=10", None),
        (
            "POST",
            "/v1/connectors",
            {
                "name": "Orders REST",
                "connector_type": "rest",
                "config": {"url": "http://127.0.0.1:9999/payload.json", "data_path": "items"},
            },
        ),
        ("GET", "/v1/connectors/conn_123", None),
        ("PATCH", "/v1/connectors/conn_123", {"name": "Orders REST Updated"}),
        ("POST", "/v1/connectors/conn_123/test", None),
        (
            "POST",
            "/v1/connectors/test",
            {
                "connector_type": "rest",
                "config": {"url": "http://127.0.0.1:9999/payload.json", "data_path": "items"},
            },
        ),
        ("GET", "/v1/connectors/conn_123/browse", None),
        (
            "POST",
            "/v1/connectors/browse",
            {
                "connector_type": "rest",
                "config": {"url": "http://127.0.0.1:9999/payload.json", "data_path": "items"},
            },
        ),
        ("DELETE", "/v1/connectors/conn_123", None),
    ]


@pytest.mark.anyio
async def test_connector_handlers_validate_required_arguments() -> None:
    assert json.loads(await connectors.create_connector_handler({})) == {"error": "name is required"}
    assert json.loads(await connectors.get_connector_handler({})) == {"error": "connector_id is required"}
    assert json.loads(await connectors.update_connector_handler({"connector_id": "conn_123"})) == {
        "error": "update_connector requires at least one field to update"
    }
    assert json.loads(await connectors.test_connector_handler({})) == {"error": "connector_id is required"}
    assert json.loads(await connectors.preview_test_connector_handler({})) == {
        "error": "connector_type is required"
    }
    assert json.loads(await connectors.browse_connector_handler({})) == {"error": "connector_id is required"}
    assert json.loads(await connectors.preview_browse_connector_handler({})) == {
        "error": "connector_type is required"
    }
    assert json.loads(await connectors.delete_connector_handler({})) == {"error": "connector_id is required"}
