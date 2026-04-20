from __future__ import annotations

import json

import pytest

from apps.mcp_server.tools import connectors, data, query


@pytest.mark.asyncio
async def test_connect_data_tool_returns_needs_selection(monkeypatch) -> None:
    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/data/connect"
        assert kwargs["json"]["dataset_name"] == "Orders"
        return {
            "status": "needs_selection",
            "connection_id": "conn_1",
            "choices": [{"id": "main.orders", "selection": {"table": "main.orders"}}],
        }

    monkeypatch.setattr(data, "api", _fake_api)

    raw = await data.connect_handler({
        "connection_type": "database",
        "provider": "sqlite",
        "dataset_name": "Orders",
        "connection_config": {"path": "/tmp/orders.db"},
    })
    body = json.loads(raw)
    assert body["status"] == "needs_selection"
    assert body["connection_id"] == "conn_1"
    assert body["choices"][0]["selection"]["table"] == "main.orders"


@pytest.mark.asyncio
async def test_list_data_tool_formats_datasets(monkeypatch) -> None:
    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/data"
        return {
            "datasets": [
                {"dataset_id": "ds_1", "dataset_name": "Orders", "row_count": 10, "columns": 3, "visibility": "private"},
            ]
        }

    monkeypatch.setattr(data, "api", _fake_api)

    raw = await data.list_handler({})
    body = json.loads(raw)
    assert body["count"] == 1
    assert body["datasets"][0]["dataset_id"] == "ds_1"


@pytest.mark.asyncio
async def test_get_data_schema_tool_formats_schema(monkeypatch) -> None:
    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/data/ds_1"
        return {
            "dataset": {"dataset_id": "ds_1", "dataset_name": "Orders"},
            "schema": {"row_count": 10, "columns": [{"name": "amount", "role": "derived_measure"}]},
        }

    monkeypatch.setattr(data, "api", _fake_api)

    raw = await data.schema_handler({"dataset_id": "ds_1"})
    body = json.loads(raw)
    assert body["dataset"]["dataset_name"] == "Orders"
    assert body["schema"]["columns"][0]["name"] == "amount"


@pytest.mark.asyncio
async def test_disconnect_data_tool_hits_delete(monkeypatch) -> None:
    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert method == "DELETE"
        assert path == "/v1/data/ds_1"
        return {"dataset_id": "ds_1", "status": "deleted"}

    monkeypatch.setattr(data, "api", _fake_api)

    raw = await data.disconnect_handler({"dataset_id": "ds_1"})
    assert json.loads(raw)["status"] == "deleted"


def test_query_tool_spec_supports_dataset_id() -> None:
    assert "dataset_id" in query.SPEC["inputSchema"]["properties"]
    assert "sources" not in query.SPEC["inputSchema"].get("required", [])


@pytest.mark.asyncio
async def test_query_tool_handler_forwards_dataset_id(monkeypatch) -> None:
    seen: dict[str, object] = {}

    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        seen["json"] = kwargs["json"]
        return {
            "result_type": "scalar",
            "confidence": 0.98,
            "decision_path": "planner_hint",
            "planner_mode": "registry_planner",
            "plan_hash": "plan_123",
            "schema_revision": "schema_rev_1",
            "source_set": ["Orders"],
            "join_path": [],
            "validated": True,
            "clarification_required": False,
            "rejection_reason": None,
            "request_id": "req_123",
            "resolved_column": "amount",
            "resolved_role": "derived_measure",
            "resolved_source": "Orders",
            "row_count": 1,
            "result": 30,
            "plan": [],
        }

    monkeypatch.setattr(query, "api", _fake_api)

    raw = await query.handler({"dataset_id": "ds_1", "metric": {"role": "metric"}})
    body = json.loads(raw)
    assert seen["json"] == {"dataset_id": "ds_1", "metric": {"role": "metric"}}
    assert body["resolved_source"] == "Orders"
    assert body["planner_mode"] == "registry_planner"
    assert body["source_set"] == ["Orders"]
    assert body["plan_hash"] == "plan_123"
    assert body["validated"] is True
    assert body["request_id"] == "req_123"


@pytest.mark.asyncio
async def test_list_connectors_tool_handles_list_response(monkeypatch) -> None:
    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        return [
            {"id": "c1", "name": "Pg", "connector_type": "postgres", "status": "live"},
        ]

    monkeypatch.setattr(connectors, "api", _fake_api)

    raw = await connectors.handler({})
    body = json.loads(raw)
    assert body["total"] == 1
    assert body["connectors"][0]["id"] == "c1"
