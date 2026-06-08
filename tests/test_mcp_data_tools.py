from __future__ import annotations

import json

import pytest

from apps.mcp_server.tools import connectors, data, datasets, meta, query
from apps.platform_contract import load_platform_contract_manifest_model
from tests._manifest_backed_integrations import (
    assert_manifest_backed_integrations,
)

pytestmark = pytest.mark.anyio


def test_get_contract_tool_spec_mentions_governed_filter_rules() -> None:
    assert "governed filter rules" in meta.GET_CONTRACT_SPEC["description"]


async def test_get_contract_handler_returns_governed_filter_contract(monkeypatch) -> None:
    contract_payload = load_platform_contract_manifest_model().model_dump(mode="json")

    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/meta/contract"
        return 200, contract_payload

    monkeypatch.setattr(meta, "api_with_status", _fake_api_with_status)

    raw = await meta.get_contract_handler({})
    body = json.loads(raw)
    filter_contract = body["primary_data_query_contract"]["governed_filter_contract"]
    assert filter_contract["kind"] == "record_predicates"
    assert filter_contract["selector_fields"] == ["column", "dimension_hint"]
    assert filter_contract["operators"]["nullary"] == ["is_null", "is_not_null"]
    assert filter_contract["supports_non_sql_backends"] is True
    assert_manifest_backed_integrations(body["integrations"])


def test_list_data_tool_spec_exposes_discovery_filters() -> None:
    props = data.LIST_SPEC["inputSchema"]["properties"]
    for name in ("search", "status", "source_name", "compact"):
        assert name in props


def test_list_datasets_tool_spec_exposes_discovery_filters() -> None:
    props = datasets.LIST_SPEC["inputSchema"]["properties"]
    for name in ("search", "status", "source_name", "compact"):
        assert name in props


async def test_connect_data_tool_returns_needs_selection(monkeypatch) -> None:
    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/data/connect"
        assert kwargs["json"]["dataset_name"] == "Orders"
        assert kwargs["timeout"] == data.config.CONNECT_TIMEOUT
        return {
            "status": "needs_selection",
            "connection_id": "conn_1",
            "choices": [{"id": "main.orders", "selection": {"table": "main.orders"}}],
        }

    monkeypatch.setattr(data, "api", _fake_api)

    raw = await data.connect_handler(
        {
            "connection_type": "database",
            "provider": "sqlite",
            "dataset_name": "Orders",
            "connection_config": {"path": "/tmp/orders.db"},
        }
    )
    body = json.loads(raw)
    assert body["status"] == "needs_selection"
    assert body["connection_id"] == "conn_1"
    assert body["choices"][0]["selection"]["table"] == "main.orders"


async def test_connect_data_tool_forwards_object_storage_descriptor(monkeypatch) -> None:
    seen: dict[str, object] = {}

    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        seen["json"] = kwargs["json"]
        return {
            "status": "ready",
            "dataset_id": "ds_object",
            "connection_type": "object_storage",
            "provider": "s3",
        }

    monkeypatch.setattr(data, "api", _fake_api)

    raw = await data.connect_handler(
        {
            "connection_type": "object_storage",
            "provider": "s3",
            "dataset_name": "WarehouseExport",
            "connection_config": {"bucket": "algenta-fixtures", "region": "us-east-1"},
            "selection": {"object_path": "exports/orders.parquet"},
        }
    )
    body = json.loads(raw)
    assert seen["json"] == {
        "connection_type": "object_storage",
        "dataset_name": "WarehouseExport",
        "provider": "s3",
        "connection_config": {"bucket": "algenta-fixtures", "region": "us-east-1"},
        "selection": {"object_path": "exports/orders.parquet"},
    }
    assert body["dataset_id"] == "ds_object"


async def test_connect_data_tool_forwards_api_descriptor(monkeypatch) -> None:
    seen: dict[str, object] = {}

    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        seen["json"] = kwargs["json"]
        return {
            "status": "ready",
            "dataset_id": "ds_api",
            "connection_type": "api",
            "provider": "rest",
        }

    monkeypatch.setattr(data, "api", _fake_api)

    raw = await data.connect_handler(
        {
            "connection_type": "api",
            "provider": "rest",
            "dataset_name": "OrdersApi",
            "connection_config": {
                "url": "https://example.com/orders",
                "headers": {"Authorization": "Bearer test"},
                "data_path": "items",
            },
        }
    )
    body = json.loads(raw)
    assert seen["json"] == {
        "connection_type": "api",
        "dataset_name": "OrdersApi",
        "provider": "rest",
        "connection_config": {
            "url": "https://example.com/orders",
            "headers": {"Authorization": "Bearer test"},
            "data_path": "items",
        },
    }
    assert body["dataset_id"] == "ds_api"


async def test_connect_data_tool_forwards_canonical_connector_envelope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        seen["json"] = kwargs["json"]
        return {
            "status": "ready",
            "dataset_id": "ds_connector",
            "connection_type": "database",
            "provider": "postgres",
        }

    monkeypatch.setattr(data, "api", _fake_api)

    raw = await data.connect_handler(
        {
            "dataset_name": "OrdersPg",
            "connector": {
                "type": "postgres",
                "location": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "orders",
                    "schema": "public",
                    "table": "orders",
                },
                "auth": {"credentials": {"user": "analytics", "password": "secret"}},
            },
        }
    )
    body = json.loads(raw)
    assert seen["json"] == {
        "dataset_name": "OrdersPg",
        "connector": {
            "type": "postgres",
            "location": {
                "host": "localhost",
                "port": 5432,
                "database": "orders",
                "schema": "public",
                "table": "orders",
            },
            "auth": {"credentials": {"user": "analytics", "password": "secret"}},
        },
    }
    assert body["dataset_id"] == "ds_connector"


async def test_list_data_tool_formats_datasets(monkeypatch) -> None:
    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/data"
        return {
            "matched_total": 1,
            "datasets": [
                {
                    "dataset_id": "ds_1",
                    "dataset_name": "Orders",
                    "row_count": 10,
                    "columns": 3,
                    "visibility": "private",
                },
            ],
        }

    monkeypatch.setattr(data, "api", _fake_api)

    raw = await data.list_handler({})
    body = json.loads(raw)
    assert body["count"] == 1
    assert body["matched_total"] == 1
    assert body["datasets"][0]["dataset_id"] == "ds_1"


async def test_list_data_tool_forwards_discovery_filters_and_compact_shape(monkeypatch) -> None:
    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/data"
        assert kwargs["params"] == {
            "page": 2,
            "limit": 25,
            "search": "otp",
            "status": "ready",
            "source_name": "ops_postgres",
            "compact": True,
        }
        return {
            "count": 1,
            "total": 8,
            "matched_total": 1,
            "page": 2,
            "limit": 25,
            "pages": 1,
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
        }

    monkeypatch.setattr(data, "api", _fake_api)

    raw = await data.list_handler(
        {
            "page": 2,
            "limit": 25,
            "search": "otp",
            "status": "ready",
            "source_name": "ops_postgres",
            "compact": True,
        }
    )
    body = json.loads(raw)
    assert body["matched_total"] == 1
    assert body["datasets"][0]["dataset_id"] == "ds_otp"
    assert body["datasets"][0]["dataset_name"] == "OTP Monthly"
    assert body["datasets"][0]["name"] == "OTP Monthly"
    assert body["datasets"][0]["status"] == "ready"
    assert body["datasets"][0]["source_names"] == ["ops_postgres"]
    assert body["datasets"][0]["column_count"] == 42


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


async def test_get_data_summary_tool_formats_selection_payload(monkeypatch) -> None:
    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/data/ds_1/summary"
        return {
            "dataset_id": "ds_1",
            "name": "Orders",
            "status": "ready",
            "source_names": ["ops_postgres"],
            "row_count": 10,
            "column_count": 3,
            "registered_at": "2026-05-20T10:00:00Z",
            "query_hints": ["sum amount by month"],
        }

    monkeypatch.setattr(data, "api", _fake_api)

    raw = await data.summary_handler({"dataset_id": "ds_1"})
    body = json.loads(raw)
    assert body["dataset_id"] == "ds_1"
    assert body["name"] == "Orders"
    assert body["source_names"] == ["ops_postgres"]
    assert body["query_hints"] == ["sum amount by month"]


async def test_list_datasets_tool_forwards_discovery_filters_and_compact_shape(monkeypatch) -> None:
    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/datasets"
        assert kwargs["params"] == {
            "page": 2,
            "limit": 25,
            "search": "otp",
            "status": "ready",
            "source_name": "ops_postgres",
            "compact": True,
        }
        return {
            "count": 1,
            "total": 8,
            "matched_total": 1,
            "page": 2,
            "limit": 25,
            "pages": 1,
            "datasets": [
                {
                    "dataset_id": "ds_otp",
                    "name": "OTP Monthly",
                    "status": "ready",
                    "model_tier": "schema",
                    "source_names": ["ops_postgres"],
                    "column_count": 42,
                    "registered_at": "2026-05-20T10:00:00Z",
                }
            ],
        }

    monkeypatch.setattr(datasets, "api", _fake_api)

    raw = await datasets.list_handler(
        {
            "page": 2,
            "limit": 25,
            "search": "otp",
            "status": "ready",
            "source_name": "ops_postgres",
            "compact": True,
        }
    )
    body = json.loads(raw)
    assert body["matched_total"] == 1
    assert body["datasets"][0]["dataset_id"] == "ds_otp"
    assert body["datasets"][0]["dataset_name"] == "OTP Monthly"
    assert body["datasets"][0]["source_names"] == ["ops_postgres"]
    assert body["datasets"][0]["column_count"] == 42


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
    filter_props = query.SPEC["inputSchema"]["properties"]["filter"]["properties"]
    assert "conditions" in filter_props
    assert filter_props["conditions"]["items"]["properties"]["op"]["enum"] == [
        "eq",
        "in",
        "gt",
        "gte",
        "lt",
        "lte",
        "is_null",
        "is_not_null",
    ]


def test_query_batch_tool_spec_supports_defaults_and_queries() -> None:
    props = query.QUERY_BATCH_SPEC["inputSchema"]["properties"]
    assert "defaults" in props
    assert "queries" in props
    assert "queries" in query.QUERY_BATCH_SPEC["inputSchema"]["required"]
    assert "conditions" in props["defaults"]["properties"]["filter"]["properties"]


def test_query_sql_report_tool_spec_supports_sources_and_sql() -> None:
    props = query.QUERY_SQL_REPORT_SPEC["inputSchema"]["properties"]
    assert "sources" in props
    assert "sql" in props
    assert "max_rows" in props
    assert set(query.QUERY_SQL_REPORT_SPEC["inputSchema"]["required"]) == {"sources", "sql"}


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


async def test_query_batch_tool_handler_forwards_request_and_formats_results(monkeypatch) -> None:
    seen: dict[str, object] = {}

    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        seen["json"] = kwargs["json"]
        assert method == "POST"
        assert path == "/v1/query/batch"
        return {
            "request_id": "req_batch",
            "results": [
                {
                    "key": "overall_otp",
                    "data": {
                        "result_type": "scalar",
                        "confidence": 0.99,
                        "decision_path": "exact_spec",
                        "planner_mode": "registry_planner",
                        "plan_hash": "plan_otp",
                        "schema_revision": "schema_rev_otp",
                        "source_set": ["otp_events"],
                        "join_path": [],
                        "validated": True,
                        "clarification_required": False,
                        "rejection_reason": None,
                        "request_id": "req_item",
                        "resolved_column": "otp_rate_pct",
                        "resolved_role": "metric",
                        "resolved_source": "otp_events",
                        "row_count": 1,
                        "result": 0.924,
                        "plan": ["resolve metric", "execute query"],
                    },
                    "metadata": {"request_id": "req_item", "latency_ms": 12.5},
                    "error": None,
                },
                {
                    "key": "avg_delay",
                    "data": None,
                    "metadata": None,
                    "error": {
                        "code": "metric_not_found",
                        "message": "average_delay_minutes was not found",
                        "details": {},
                    },
                },
            ],
        }

    monkeypatch.setattr(query, "api", _fake_api)

    request = {
        "defaults": {
            "dataset_id": "otp_events",
            "filter": {"time_filter": "last_year"},
            "limit": 12,
            "order": "desc",
        },
        "queries": [
            {"key": "overall_otp", "request": {"metric": {"role": "metric", "hint": "otp_rate"}}},
            {
                "key": "avg_delay",
                "request": {"metric": {"role": "metric", "hint": "average_delay_minutes"}},
            },
        ],
    }
    raw = await query.query_batch_handler(request)
    body = json.loads(raw)
    assert seen["json"] == request
    assert body["request_id"] == "req_batch"
    assert body["results"][0]["key"] == "overall_otp"
    assert body["results"][0]["data"]["resolved_source"] == "otp_events"
    assert body["results"][0]["metadata"]["latency_ms"] == 12.5
    assert body["results"][1]["error"]["code"] == "metric_not_found"
    assert body["results"][1]["data"] is None


async def test_query_sql_report_tool_handler_forwards_request_and_formats_rows(monkeypatch) -> None:
    seen: dict[str, object] = {}

    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        seen["json"] = kwargs["json"]
        assert method == "POST"
        assert path == "/v1/query/sql-report"
        return {
            "columns": ["flight_month", "otp_rate_pct"],
            "rows": [
                {"flight_month": "2026-01-01", "otp_rate_pct": 91.1},
                {"flight_month": "2026-02-01", "otp_rate_pct": 92.4},
            ],
            "row_count": 2,
            "truncated": False,
            "request_id": "req_sql",
            "latency_ms": 24.1,
        }

    monkeypatch.setattr(query, "api", _fake_api)

    request = {
        "sources": [{"dataset_id": "ds_otp", "alias": "otp"}],
        "sql": "select flight_month, otp_rate_pct from otp order by flight_month",
        "max_rows": 100,
    }
    raw = await query.query_sql_report_handler(request)
    body = json.loads(raw)
    assert seen["json"] == request
    assert body["columns"] == ["flight_month", "otp_rate_pct"]
    assert body["rows"][0]["flight_month"] == "2026-01-01"
    assert body["row_count"] == 2
    assert body["truncated"] is False
    assert body["request_id"] == "req_sql"
    assert body["latency_ms"] == 24.1


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
