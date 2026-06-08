from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
if str(PYTHON_SDK) not in sys.path:
    sys.path.insert(0, str(PYTHON_SDK))

decision_engine = importlib.import_module("decision_engine")
AsyncDecisionEngineClient = decision_engine.AsyncDecisionEngineClient
ConnectorBrowseResult = decision_engine.ConnectorBrowseResult
ConnectorInfo = decision_engine.ConnectorInfo
ConnectorListResult = decision_engine.ConnectorListResult
ConnectorTestInfo = decision_engine.ConnectorTestInfo
DatasetConnectResult = decision_engine.DatasetConnectResult
DatasetDeleteResult = decision_engine.DatasetDeleteResult
DatasetDetailResult = decision_engine.DatasetDetailResult
DatasetListResult = decision_engine.DatasetListResult
DatasetSummaryResult = decision_engine.DatasetSummaryResult
DecisionEngineClient = decision_engine.DecisionEngineClient
RateLimitError = decision_engine.RateLimitError


def test_decision_engine_client_connector_methods_return_typed_models(monkeypatch) -> None:
    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")

    def _fake_request(method: str, path: str, **kwargs):
        if (method, path) == ("POST", "/v1/connectors"):
            return {
                "id": "conn_123",
                "name": "Warehouse Postgres",
                "connector_type": "postgres",
                "status": "untested",
                "visibility": "private",
            }
        if (method, path) == ("GET", "/v1/connectors"):
            assert kwargs["params"] == {"page": 1, "limit": 200}
            return {
                "connectors": [
                    {
                        "id": "conn_123",
                        "name": "Warehouse Postgres",
                        "connector_type": "postgres",
                        "status": "live",
                        "visibility": "private",
                    }
                ],
                "total": 1,
                "page": 1,
                "limit": 200,
                "pages": 1,
            }
        if (method, path) == ("GET", "/v1/connectors/conn_123"):
            return {
                "id": "conn_123",
                "name": "Warehouse Postgres",
                "connector_type": "postgres",
                "status": "live",
                "visibility": "private",
            }
        if (method, path) == ("PATCH", "/v1/connectors/conn_123"):
            assert kwargs["json"] == {
                "description": "analytics warehouse",
                "visibility": "workspace",
            }
            return {
                "id": "conn_123",
                "name": "Warehouse Postgres",
                "description": "analytics warehouse",
                "connector_type": "postgres",
                "status": "untested",
                "visibility": "workspace",
            }
        if (method, path) == ("POST", "/v1/connectors/conn_123/test"):
            return {"success": True, "message": "ok", "latency_ms": 10}
        if (method, path) == ("POST", "/v1/connectors/test"):
            assert kwargs["json"] == {
                "connector_type": "redis",
                "config": {"url": "redis://localhost:6379"},
            }
            return {"success": True, "message": "ok", "latency_ms": 8}
        if (method, path) == ("GET", "/v1/connectors/conn_123/browse"):
            return {
                "connector_type": "postgres",
                "items": [{"label": "orders"}],
                "total": 1,
                "message": "ok",
                "labels": {"entity_noun": "table"},
                "discovery": {"scope_noun": "schema"},
            }
        if (method, path) == ("POST", "/v1/connectors/browse"):
            assert kwargs["json"] == {
                "connector_type": "redis",
                "config": {"url": "redis://localhost:6379"},
            }
            return {
                "connector_type": "redis",
                "items": [{"label": "cache:key"}],
                "total": 1,
                "message": "ok",
                "labels": {"entity_noun": "key"},
                "discovery": {"scope_noun": "keyspace"},
            }
        raise AssertionError(f"unexpected request: {(method, path, kwargs)}")

    monkeypatch.setattr(client, "_request", _fake_request)

    created = client.create_connector(name="Warehouse Postgres", connector_type="postgres")
    listed = client.list_connectors()
    detail = client.get_connector("conn_123")
    updated = client.update_connector(
        "conn_123",
        description="analytics warehouse",
        visibility="workspace",
    )
    tested = client.test_connector("conn_123")
    preview_tested = client.preview_test_connector(
        connector_type="redis",
        config={"url": "redis://localhost:6379"},
    )
    browsed = client.browse_connector("conn_123")
    preview_browsed = client.preview_browse_connector(
        connector_type="redis",
        config={"url": "redis://localhost:6379"},
    )

    assert isinstance(created, ConnectorInfo)
    assert isinstance(listed, ConnectorListResult)
    assert isinstance(detail, ConnectorInfo)
    assert isinstance(updated, ConnectorInfo)
    assert isinstance(tested, ConnectorTestInfo)
    assert isinstance(preview_tested, ConnectorTestInfo)
    assert isinstance(browsed, ConnectorBrowseResult)
    assert isinstance(preview_browsed, ConnectorBrowseResult)


@pytest.mark.anyio
async def test_async_decision_engine_client_connector_methods_return_typed_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncDecisionEngineClient(api_key="de_test_async", base_url="http://localhost:8000")

    async def _fake_request(method: str, path: str, **kwargs: Any):
        if (method, path) == ("POST", "/v1/connectors"):
            return {
                "id": "conn_123",
                "name": "Warehouse Postgres",
                "connector_type": "postgres",
                "status": "untested",
                "visibility": "private",
            }
        if (method, path) == ("GET", "/v1/connectors"):
            assert kwargs["params"] == {"page": 1, "limit": 200}
            return {
                "connectors": [
                    {
                        "id": "conn_123",
                        "name": "Warehouse Postgres",
                        "connector_type": "postgres",
                        "status": "live",
                        "visibility": "private",
                    }
                ],
                "total": 1,
                "page": 1,
                "limit": 200,
                "pages": 1,
            }
        if (method, path) == ("GET", "/v1/connectors/conn_123"):
            return {
                "id": "conn_123",
                "name": "Warehouse Postgres",
                "connector_type": "postgres",
                "status": "live",
                "visibility": "private",
            }
        if (method, path) == ("PATCH", "/v1/connectors/conn_123"):
            assert kwargs["json"] == {
                "description": "analytics warehouse",
                "visibility": "workspace",
            }
            return {
                "id": "conn_123",
                "name": "Warehouse Postgres",
                "description": "analytics warehouse",
                "connector_type": "postgres",
                "status": "untested",
                "visibility": "workspace",
            }
        if (method, path) == ("POST", "/v1/connectors/conn_123/test"):
            return {"success": True, "message": "ok", "latency_ms": 10}
        if (method, path) == ("POST", "/v1/connectors/test"):
            assert kwargs["json"] == {
                "connector_type": "redis",
                "config": {"url": "redis://localhost:6379"},
            }
            return {"success": True, "message": "ok", "latency_ms": 8}
        if (method, path) == ("GET", "/v1/connectors/conn_123/browse"):
            return {
                "connector_type": "postgres",
                "items": [{"label": "orders"}],
                "total": 1,
                "message": "ok",
                "labels": {"entity_noun": "table"},
                "discovery": {"scope_noun": "schema"},
            }
        if (method, path) == ("POST", "/v1/connectors/browse"):
            assert kwargs["json"] == {
                "connector_type": "redis",
                "config": {"url": "redis://localhost:6379"},
            }
            return {
                "connector_type": "redis",
                "items": [{"label": "cache:key"}],
                "total": 1,
                "message": "ok",
                "labels": {"entity_noun": "key"},
                "discovery": {"scope_noun": "keyspace"},
            }
        raise AssertionError(f"unexpected request: {(method, path, kwargs)}")

    monkeypatch.setattr(client, "_request", _fake_request)

    created = await client.create_connector(name="Warehouse Postgres", connector_type="postgres")
    listed = await client.list_connectors()
    detail = await client.get_connector("conn_123")
    updated = await client.update_connector(
        "conn_123",
        description="analytics warehouse",
        visibility="workspace",
    )
    tested = await client.test_connector("conn_123")
    preview_tested = await client.preview_test_connector(
        connector_type="redis",
        config={"url": "redis://localhost:6379"},
    )
    browsed = await client.browse_connector("conn_123")
    preview_browsed = await client.preview_browse_connector(
        connector_type="redis",
        config={"url": "redis://localhost:6379"},
    )

    assert isinstance(created, ConnectorInfo)
    assert isinstance(listed, ConnectorListResult)
    assert isinstance(detail, ConnectorInfo)
    assert isinstance(updated, ConnectorInfo)
    assert isinstance(tested, ConnectorTestInfo)
    assert isinstance(preview_tested, ConnectorTestInfo)
    assert isinstance(browsed, ConnectorBrowseResult)
    assert isinstance(preview_browsed, ConnectorBrowseResult)


def test_decision_engine_client_dataset_methods_return_typed_models(monkeypatch) -> None:
    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")

    def _fake_request(method: str, path: str, **kwargs):
        if (method, path) == ("POST", "/v1/data/connect"):
            return {"status": "ready", "dataset_id": "ds_123", "source_id": "ds_123"}
        if (method, path) == ("GET", "/v1/data"):
            assert kwargs["params"] == {"page": 1, "limit": 200}
            return {
                "datasets": [{"dataset_id": "ds_123", "dataset_name": "orders"}],
                "count": 1,
                "total": 1,
                "page": 1,
                "limit": 200,
                "pages": 1,
            }
        if (method, path) == ("GET", "/v1/data/ds_123"):
            return {
                "dataset": {"dataset_id": "ds_123", "dataset_name": "orders"},
                "schema": {"fields": ["amount"]},
            }
        if (method, path) == ("POST", "/v1/data/ds_123/refresh"):
            return {"status": "ready", "dataset_id": "ds_123", "source_id": "ds_123"}
        if (method, path) == ("DELETE", "/v1/data/ds_123"):
            return {
                "dataset_id": "ds_123",
                "status": "deleted",
                "connection_deleted": True,
            }
        raise AssertionError(f"unexpected request: {(method, path, kwargs)}")

    monkeypatch.setattr(client, "_request", _fake_request)

    connected = client.connect_data({"dataset_name": "orders", "connector_id": "conn_123"})
    listed = client.list_datasets()
    detail = client.get_dataset("ds_123")
    refreshed = client.refresh_dataset("ds_123")
    deleted = client.delete_dataset("ds_123")

    assert isinstance(connected, DatasetConnectResult)
    assert isinstance(listed, DatasetListResult)
    assert isinstance(detail, DatasetDetailResult)
    assert isinstance(refreshed, DatasetConnectResult)
    assert isinstance(deleted, DatasetDeleteResult)


@pytest.mark.anyio
async def test_async_decision_engine_client_dataset_methods_return_typed_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncDecisionEngineClient(api_key="de_test_async", base_url="http://localhost:8000")

    async def _fake_request(method: str, path: str, **kwargs: Any):
        if (method, path) == ("POST", "/v1/data/connect"):
            return {"status": "ready", "dataset_id": "ds_123", "source_id": "ds_123"}
        if (method, path) == ("GET", "/v1/data"):
            assert kwargs["params"] == {"page": 1, "limit": 200}
            return {
                "datasets": [{"dataset_id": "ds_123", "dataset_name": "orders"}],
                "count": 1,
                "total": 1,
                "page": 1,
                "limit": 200,
                "pages": 1,
            }
        if (method, path) == ("GET", "/v1/data/ds_123"):
            return {
                "dataset": {"dataset_id": "ds_123", "dataset_name": "orders"},
                "schema": {"fields": ["amount"]},
            }
        if (method, path) == ("POST", "/v1/data/ds_123/refresh"):
            return {"status": "ready", "dataset_id": "ds_123", "source_id": "ds_123"}
        if (method, path) == ("DELETE", "/v1/data/ds_123"):
            return {
                "dataset_id": "ds_123",
                "status": "deleted",
                "connection_deleted": True,
            }
        raise AssertionError(f"unexpected request: {(method, path, kwargs)}")

    monkeypatch.setattr(client, "_request", _fake_request)

    connected = await client.connect_data({"dataset_name": "orders", "connector_id": "conn_123"})
    listed = await client.list_datasets()
    detail = await client.get_dataset("ds_123")
    refreshed = await client.refresh_dataset("ds_123")
    deleted = await client.delete_dataset("ds_123")

    assert isinstance(connected, DatasetConnectResult)
    assert isinstance(listed, DatasetListResult)
    assert isinstance(detail, DatasetDetailResult)
    assert isinstance(refreshed, DatasetConnectResult)
    assert isinstance(deleted, DatasetDeleteResult)


def test_decision_engine_client_dataset_discovery_filters_and_summary(monkeypatch) -> None:
    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")

    def _fake_request(method: str, path: str, **kwargs):
        if (method, path) == ("GET", "/v1/data"):
            assert kwargs["params"] == {
                "page": 2,
                "limit": 50,
                "search": "otp",
                "status": "ready",
                "source_name": "ops_postgres",
                "compact": "1",
            }
            return {
                "datasets": [
                    {
                        "dataset_id": "ds_otp",
                        "dataset_name": "OTP Monthly",
                        "name": "OTP Monthly",
                        "status": "ready",
                        "source_names": ["ops_postgres"],
                        "column_count": 12,
                        "registered_at": "2026-05-20T10:00:00Z",
                    }
                ],
                "count": 1,
                "total": 15,
                "matched_total": 1,
                "page": 2,
                "limit": 50,
                "pages": 1,
            }
        if (method, path) == ("GET", "/v1/data/ds_otp/summary"):
            return {
                "dataset_id": "ds_otp",
                "name": "OTP Monthly",
                "status": "ready",
                "source_names": ["ops_postgres"],
                "row_count": 5000,
                "column_count": 12,
                "registered_at": "2026-05-20T10:00:00Z",
                "query_hints": [{"hint": "otp_rate"}],
            }
        raise AssertionError(f"unexpected request: {(method, path, kwargs)}")

    monkeypatch.setattr(client, "_request", _fake_request)

    listed = client.list_datasets(
        page=2,
        limit=50,
        search="otp",
        status="ready",
        source_name="ops_postgres",
        compact=True,
    )
    summary = client.get_dataset_summary("ds_otp")

    assert isinstance(listed, DatasetListResult)
    assert listed.matched_total == 1
    assert listed.datasets[0].status == "ready"
    assert isinstance(summary, DatasetSummaryResult)
    assert summary.query_hints == [{"hint": "otp_rate"}]


@pytest.mark.anyio
async def test_async_decision_engine_client_dataset_discovery_filters_and_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncDecisionEngineClient(api_key="de_test_async", base_url="http://localhost:8000")

    async def _fake_request(method: str, path: str, **kwargs: Any):
        if (method, path) == ("GET", "/v1/data"):
            assert kwargs["params"] == {
                "page": 2,
                "limit": 50,
                "search": "otp",
                "status": "ready",
                "source_name": "ops_postgres",
                "compact": "1",
            }
            return {
                "datasets": [
                    {
                        "dataset_id": "ds_otp",
                        "dataset_name": "OTP Monthly",
                        "name": "OTP Monthly",
                        "status": "ready",
                        "source_names": ["ops_postgres"],
                        "column_count": 12,
                        "registered_at": "2026-05-20T10:00:00Z",
                    }
                ],
                "count": 1,
                "total": 15,
                "matched_total": 1,
                "page": 2,
                "limit": 50,
                "pages": 1,
            }
        if (method, path) == ("GET", "/v1/data/ds_otp/summary"):
            return {
                "dataset_id": "ds_otp",
                "name": "OTP Monthly",
                "status": "ready",
                "source_names": ["ops_postgres"],
                "row_count": 5000,
                "column_count": 12,
                "registered_at": "2026-05-20T10:00:00Z",
                "query_hints": [{"hint": "otp_rate"}],
            }
        raise AssertionError(f"unexpected request: {(method, path, kwargs)}")

    monkeypatch.setattr(client, "_request", _fake_request)

    listed = await client.list_datasets(
        page=2,
        limit=50,
        search="otp",
        status="ready",
        source_name="ops_postgres",
        compact=True,
    )
    summary = await client.get_dataset_summary("ds_otp")

    assert isinstance(listed, DatasetListResult)
    assert listed.matched_total == 1
    assert listed.datasets[0].status == "ready"
    assert isinstance(summary, DatasetSummaryResult)
    assert summary.query_hints == [{"hint": "otp_rate"}]


def test_decision_engine_client_list_methods_accept_legacy_raw_array_shapes(
    monkeypatch,
) -> None:
    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")

    def _fake_request(method: str, path: str, **kwargs):
        if (method, path) == ("GET", "/v1/connectors"):
            assert kwargs["params"] == {"page": 1, "limit": 200}
            return [
                {
                    "id": "conn_123",
                    "name": "Warehouse Postgres",
                    "connector_type": "postgres",
                    "status": "live",
                    "visibility": "private",
                }
            ]
        if (method, path) == ("GET", "/v1/data"):
            assert kwargs["params"] == {"page": 1, "limit": 200}
            return [
                {
                    "dataset_id": "ds_123",
                    "dataset_name": "orders",
                }
            ]
        raise AssertionError(f"unexpected request: {(method, path, kwargs)}")

    monkeypatch.setattr(client, "_request", _fake_request)

    connectors = client.list_connectors()
    datasets = client.list_datasets()

    assert isinstance(connectors, ConnectorListResult)
    assert [connector.id for connector in connectors.connectors] == ["conn_123"]
    assert connectors.total == 1
    assert connectors.page == 1
    assert connectors.limit == 1
    assert connectors.pages == 1

    assert isinstance(datasets, DatasetListResult)
    assert [dataset.dataset_id for dataset in datasets.datasets] == ["ds_123"]
    assert datasets.count == 1
    assert datasets.total == 1
    assert datasets.page == 1
    assert datasets.limit == 1
    assert datasets.pages == 1


@pytest.mark.anyio
async def test_async_decision_engine_client_list_methods_accept_legacy_raw_array_shapes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncDecisionEngineClient(api_key="de_test_async", base_url="http://localhost:8000")

    async def _fake_request(method: str, path: str, **kwargs: Any):
        if (method, path) == ("GET", "/v1/connectors"):
            assert kwargs["params"] == {"page": 1, "limit": 200}
            return [
                {
                    "id": "conn_123",
                    "name": "Warehouse Postgres",
                    "connector_type": "postgres",
                    "status": "live",
                    "visibility": "private",
                }
            ]
        if (method, path) == ("GET", "/v1/data"):
            assert kwargs["params"] == {"page": 1, "limit": 200}
            return [
                {
                    "dataset_id": "ds_123",
                    "dataset_name": "orders",
                }
            ]
        raise AssertionError(f"unexpected request: {(method, path, kwargs)}")

    monkeypatch.setattr(client, "_request", _fake_request)

    connectors = await client.list_connectors()
    datasets = await client.list_datasets()

    assert isinstance(connectors, ConnectorListResult)
    assert [connector.id for connector in connectors.connectors] == ["conn_123"]
    assert connectors.total == 1
    assert connectors.page == 1
    assert connectors.limit == 1
    assert connectors.pages == 1

    assert isinstance(datasets, DatasetListResult)
    assert [dataset.dataset_id for dataset in datasets.datasets] == ["ds_123"]
    assert datasets.count == 1
    assert datasets.total == 1
    assert datasets.page == 1
    assert datasets.limit == 1
    assert datasets.pages == 1


def test_decision_engine_client_list_methods_reject_raw_array_past_first_page(
    monkeypatch,
) -> None:
    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")

    def _fake_request(method: str, path: str, **kwargs):
        assert method == "GET"
        assert path in {"/v1/connectors", "/v1/data"}
        return []

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(ValueError, match="page=2"):
        client.list_connectors(page=2)

    with pytest.raises(ValueError, match="page=2"):
        client.list_datasets(page=2)


@pytest.mark.anyio
async def test_async_decision_engine_client_list_methods_reject_raw_array_past_first_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncDecisionEngineClient(api_key="de_test_async", base_url="http://localhost:8000")

    async def _fake_request(method: str, path: str, **kwargs: Any):
        assert method == "GET"
        assert path in {"/v1/connectors", "/v1/data"}
        return []

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(ValueError, match="page=2"):
        await client.list_connectors(page=2)

    with pytest.raises(ValueError, match="page=2"):
        await client.list_datasets(page=2)


def test_decision_engine_client_iterators_support_pagination_and_max_items(monkeypatch) -> None:
    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    calls: list[tuple[str, str, dict]] = []

    def _fake_request(method: str, path: str, **kwargs):
        calls.append((method, path, kwargs))
        if (method, path) == ("GET", "/v1/connectors"):
            params = kwargs["params"]
            if params["page"] == 1:
                return {
                    "connectors": [
                        {
                            "id": "conn_1",
                            "name": "Warehouse 1",
                            "connector_type": "postgres",
                            "status": "live",
                            "visibility": "private",
                        }
                    ],
                    "total": 2,
                    "page": 1,
                    "limit": params["limit"],
                    "pages": 2,
                }
            return {
                "connectors": [
                    {
                        "id": "conn_2",
                        "name": "Warehouse 2",
                        "connector_type": "postgres",
                        "status": "live",
                        "visibility": "private",
                    }
                ],
                "total": 2,
                "page": 2,
                "limit": params["limit"],
                "pages": 2,
            }
        if (method, path) == ("GET", "/v1/data"):
            params = kwargs["params"]
            return {
                "datasets": [
                    {
                        "dataset_id": f"ds_{params['page']}",
                        "dataset_name": f"orders_{params['page']}",
                    }
                ],
                "count": 1,
                "total": 3,
                "page": params["page"],
                "limit": params["limit"],
                "pages": 3,
            }
        raise AssertionError(f"unexpected request: {(method, path, kwargs)}")

    monkeypatch.setattr(client, "_request", _fake_request)

    connectors = list(client.iter_connectors(limit=1))
    datasets = list(client.iter_datasets(limit=1, max_items=2))

    assert [connector.id for connector in connectors] == ["conn_1", "conn_2"]
    assert [dataset.dataset_id for dataset in datasets] == ["ds_1", "ds_2"]


@pytest.mark.anyio
async def test_async_decision_engine_client_iterators_support_pagination_and_max_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncDecisionEngineClient(api_key="de_test_async", base_url="http://localhost:8000")
    calls: list[tuple[str, str, dict[str, Any]]] = []

    async def _fake_request(method: str, path: str, **kwargs: Any):
        calls.append((method, path, kwargs))
        if (method, path) == ("GET", "/v1/connectors"):
            params = kwargs["params"]
            if params["page"] == 1:
                return {
                    "connectors": [
                        {
                            "id": "conn_1",
                            "name": "Warehouse 1",
                            "connector_type": "postgres",
                            "status": "live",
                            "visibility": "private",
                        }
                    ],
                    "total": 2,
                    "page": 1,
                    "limit": params["limit"],
                    "pages": 2,
                }
            return {
                "connectors": [
                    {
                        "id": "conn_2",
                        "name": "Warehouse 2",
                        "connector_type": "postgres",
                        "status": "live",
                        "visibility": "private",
                    }
                ],
                "total": 2,
                "page": 2,
                "limit": params["limit"],
                "pages": 2,
            }
        if (method, path) == ("GET", "/v1/data"):
            params = kwargs["params"]
            return {
                "datasets": [
                    {
                        "dataset_id": f"ds_{params['page']}",
                        "dataset_name": f"orders_{params['page']}",
                    }
                ],
                "count": 1,
                "total": 3,
                "page": params["page"],
                "limit": params["limit"],
                "pages": 3,
            }
        raise AssertionError(f"unexpected request: {(method, path, kwargs)}")

    monkeypatch.setattr(client, "_request", _fake_request)

    connectors = [connector async for connector in client.iter_connectors(limit=1)]
    datasets = [dataset async for dataset in client.iter_datasets(limit=1, max_items=2)]

    assert [connector.id for connector in connectors] == ["conn_1", "conn_2"]
    assert [dataset.dataset_id for dataset in datasets] == ["ds_1", "ds_2"]
    assert calls


def test_decision_engine_client_inline_preview_rate_limit_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = DecisionEngineClient(
        api_key="de_test", base_url="http://localhost:8000", max_retries=3
    )
    attempts = 0

    def _rate_limited(_method: str, _path: str, **_kwargs):
        nonlocal attempts
        attempts += 1
        raise RateLimitError(
            "Inline connector previews are rate limited.",
            retry_after=60,
            status_code=429,
            response_body={
                "error": {
                    "code": "inline_preview_rate_limited",
                    "message": "Inline connector previews are rate limited.",
                }
            },
        )

    def _no_sleep(_seconds: float) -> None:
        raise AssertionError("inline preview rate limits must fail immediately without retry sleep")

    monkeypatch.setattr(client._client, "request", _rate_limited)
    monkeypatch.setattr(time, "sleep", _no_sleep)

    with pytest.raises(RateLimitError, match="rate limited"):
        client.preview_test_connector(
            connector_type="redis",
            config={"url": "redis://localhost:6379"},
        )

    assert attempts == 1


@pytest.mark.anyio
async def test_async_decision_engine_client_inline_preview_rate_limit_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncDecisionEngineClient(
        api_key="de_test_async",
        base_url="http://localhost:8000",
        max_retries=3,
    )
    attempts = 0

    async def _rate_limited(_method: str, _path: str, **_kwargs: Any):
        nonlocal attempts
        attempts += 1
        raise RateLimitError(
            "Inline connector previews are rate limited.",
            retry_after=60,
            status_code=429,
            response_body={
                "error": {
                    "code": "inline_preview_rate_limited",
                    "message": "Inline connector previews are rate limited.",
                }
            },
        )

    async def _no_sleep(_seconds: float) -> None:
        raise AssertionError("inline preview rate limits must fail immediately without retry sleep")

    monkeypatch.setattr(client._client, "request", _rate_limited)
    monkeypatch.setattr(importlib.import_module("decision_engine.async_client_transport").asyncio, "sleep", _no_sleep)

    with pytest.raises(RateLimitError, match="rate limited"):
        await client.preview_test_connector(
            connector_type="redis",
            config={"url": "redis://localhost:6379"},
        )

    assert attempts == 1
