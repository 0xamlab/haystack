from __future__ import annotations

from typing import Any

import pytest

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_current_org


class _FakeDB:
    async def commit(self) -> None:
        return None


async def _override_db():
    yield _FakeDB()


@pytest.fixture
def fake_auth() -> dict[str, Any]:
    return {"org_id": "org_a", "role": "member", "user_id": "u1", "key_id": "k1"}


@pytest.fixture
async def data_client(app, client, fake_auth):
    app.dependency_overrides[get_current_org] = lambda: fake_auth
    app.dependency_overrides[get_db] = _override_db
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_connect_data_route_returns_service_payload(monkeypatch, data_client) -> None:
    async def _fake_connect_data(*, db, auth, payload):  # type: ignore[no-untyped-def]
        assert payload["dataset_name"] == "Sales"
        return {"status": "ready", "dataset_id": "ds_sales"}

    monkeypatch.setattr("apps.api_server.routers.data.connect_data", _fake_connect_data)

    resp = await data_client.post(
        "/v1/data/connect",
        json={"connection_type": "file_upload", "dataset_name": "Sales", "csv": "amount\n10\n"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready", "dataset_id": "ds_sales"}
    assert "X-Execution-Ms" in resp.headers
    assert resp.headers["X-Mojo-Ms"] == "0"
    assert "X-Request-Id" in resp.headers


@pytest.mark.anyio
async def test_list_data_route_filters_visible_entries(monkeypatch, data_client) -> None:
    monkeypatch.setattr(
        "apps.api_server.routers.data.sreg.list_sources",
        lambda _org_id: [
            {
                "id": "shared_ds",
                "name": "Shared",
                "dataset_name": "Shared",
                "visibility": "shared",
                "row_count": 3,
                "columns": 2,
                "discovery_labels": {"entity_noun": "index", "row_noun": "document"},
                "discovery_metadata": {"scope_noun": "index catalog", "count_kind": "exact"},
            },
            {
                "id": "mine_ds",
                "name": "Mine",
                "dataset_name": "Mine",
                "visibility": "private",
                "owner_user_id": "u1",
                "row_count": 5,
                "columns": 3,
                "discovery_labels": {"entity_noun": "table", "row_noun": "row"},
                "discovery_metadata": {"scope_noun": "catalog", "count_kind": "exact"},
            },
            {
                "id": "other_ds",
                "name": "Other",
                "dataset_name": "Other",
                "visibility": "private",
                "owner_user_id": "u2",
                "row_count": 8,
                "columns": 4,
            },
        ],
    )

    resp = await data_client.get("/v1/data")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["limit"] == 2
    assert body["pages"] == 1
    assert [item["dataset_id"] for item in body["datasets"]] == ["shared_ds", "mine_ds"]
    assert body["datasets"][0]["discovery_labels"] == {
        "entity_noun": "index",
        "row_noun": "document",
    }
    assert body["datasets"][0]["discovery_metadata"] == {
        "scope_noun": "index catalog",
        "count_kind": "exact",
    }
    assert body["datasets"][1]["discovery_labels"] == {
        "entity_noun": "table",
        "row_noun": "row",
    }


@pytest.mark.anyio
async def test_list_data_route_supports_search_filters_and_compact_mode(
    monkeypatch,
    data_client,
) -> None:
    monkeypatch.setattr(
        "apps.api_server.routers.data.sreg.list_sources",
        lambda _org_id: [
            {
                "id": "otp_exact",
                "name": "OTP Monthly Performance",
                "dataset_name": "OTP Monthly Performance",
                "visibility": "shared",
                "status": "ready",
                "registered_at": "2026-05-20T10:00:00Z",
                "column_count": 42,
                "source_names": ["ops_postgres"],
            },
            {
                "id": "otp_prefix",
                "name": "OTP Delay Breakdown",
                "dataset_name": "OTP Delay Breakdown",
                "visibility": "shared",
                "status": "ready",
                "registered_at": "2026-05-20T11:00:00Z",
                "column_count": 12,
                "source_names": ["ops_postgres"],
            },
            {
                "id": "delay_substring",
                "name": "Monthly Delay Performance",
                "dataset_name": "Monthly Delay Performance",
                "visibility": "shared",
                "status": "training",
                "registered_at": "2026-05-20T12:00:00Z",
                "column_count": 9,
                "source_names": ["warehouse_postgres"],
            },
        ],
    )

    resp = await data_client.get(
        "/v1/data",
        params={
            "search": "otp",
            "status": "ready",
            "source_name": "ops_postgres",
            "compact": "1",
            "page": 1,
            "limit": 20,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["matched_total"] == 2
    assert body["count"] == 2
    assert [item["dataset_id"] for item in body["datasets"]] == ["otp_prefix", "otp_exact"]
    assert body["datasets"][0] == {
        "dataset_id": "otp_prefix",
        "source_id": "otp_prefix",
        "dataset_name": "OTP Delay Breakdown",
        "name": "OTP Delay Breakdown",
        "status": "ready",
        "source_names": ["ops_postgres"],
        "column_count": 12,
        "registered_at": "2026-05-20T11:00:00Z",
    }


@pytest.mark.anyio
async def test_list_datasets_route_mirrors_discovery_filters_and_compact_shape(
    monkeypatch,
    data_client,
) -> None:
    monkeypatch.setattr(
        "apps.api_server.routers.datasets.ds.list_datasets",
        lambda _org_id: [
            {
                "dataset_id": "otp_exact",
                "name": "OTP",
                "schema_hash": "h1",
                "status": "ready",
                "model_tier": "schema",
                "column_count": 8,
                "registered_at": "2026-05-20T10:00:00Z",
                "source_names": ["ops_postgres"],
            },
            {
                "dataset_id": "otp_monthly",
                "name": "OTP Monthly",
                "schema_hash": "h2",
                "status": "ready",
                "model_tier": "base",
                "column_count": 12,
                "registered_at": "2026-05-20T11:00:00Z",
                "source_names": ["ops_postgres"],
            },
            {
                "dataset_id": "warehouse_delay",
                "name": "Delay Warehouse",
                "schema_hash": "h3",
                "status": "training",
                "model_tier": "none",
                "column_count": 4,
                "registered_at": "2026-05-20T12:00:00Z",
                "source_names": ["warehouse_postgres"],
            },
        ],
    )

    resp = await data_client.get(
        "/v1/datasets",
        params={
            "search": "otp",
            "status": "ready",
            "source_name": "ops_postgres",
            "compact": "1",
            "page": 1,
            "limit": 20,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["matched_total"] == 2
    assert [item["dataset_id"] for item in body["datasets"]] == ["otp_exact", "otp_monthly"]
    assert body["datasets"][0] == {
        "dataset_id": "otp_exact",
        "name": "OTP",
        "status": "ready",
        "source_names": ["ops_postgres"],
        "column_count": 8,
        "registered_at": "2026-05-20T10:00:00Z",
    }


@pytest.mark.anyio
async def test_get_data_route_returns_dataset_and_schema(monkeypatch, data_client) -> None:
    monkeypatch.setattr(
        "apps.api_server.routers.data.get_visible_dataset_entry",
        lambda _org_id, _dataset_id, _auth: {
            "id": "ds_alpha",
            "name": "Alpha",
            "dataset_name": "Alpha",
            "visibility": "private",
            "discovery_labels": {"entity_noun": "key", "row_noun": "value"},
            "discovery_metadata": {"scope_noun": "keyspace", "count_kind": "sample"},
        },
    )
    monkeypatch.setattr(
        "apps.api_server.routers.data.sreg.get_source_meta",
        lambda _org_id, _dataset_id: {"row_count": 2, "columns": [{"name": "amount"}]},
    )

    resp = await data_client.get("/v1/data/ds_alpha")
    assert resp.status_code == 200
    body = resp.json()
    assert body["dataset"]["dataset_id"] == "ds_alpha"
    assert body["dataset"]["discovery_labels"] == {
        "entity_noun": "key",
        "row_noun": "value",
    }
    assert body["dataset"]["discovery_metadata"] == {
        "scope_noun": "keyspace",
        "count_kind": "sample",
    }
    assert body["schema"]["row_count"] == 2


@pytest.mark.anyio
async def test_get_data_summary_route_returns_low_token_selection_payload(
    monkeypatch,
    data_client,
) -> None:
    monkeypatch.setattr(
        "apps.api_server.routers.data.get_visible_dataset_entry",
        lambda _org_id, _dataset_id, _auth: {
            "id": "ds_alpha",
            "name": "Alpha",
            "dataset_name": "Alpha",
            "visibility": "private",
            "registered_at": "2026-05-20T10:00:00Z",
            "row_count": 25,
            "column_count": 7,
            "source_names": ["warehouse_postgres"],
        },
    )
    monkeypatch.setattr(
        "apps.api_server.routers.data.sreg.get_source_meta",
        lambda _org_id, _dataset_id: {
            "row_count": 30,
            "columns": [{"name": "amount"}, {"name": "month"}],
            "query_hints": [{"hint": f"hint_{idx}"} for idx in range(12)],
        },
    )

    resp = await data_client.get("/v1/data/ds_alpha/summary")
    assert resp.status_code == 200
    assert resp.json() == {
        "dataset_id": "ds_alpha",
        "name": "Alpha",
        "status": "ready",
        "source_names": ["warehouse_postgres"],
        "row_count": 30,
        "column_count": 2,
        "registered_at": "2026-05-20T10:00:00Z",
        "query_hints": [{"hint": f"hint_{idx}"} for idx in range(10)],
    }


@pytest.mark.anyio
async def test_refresh_data_route_delegates(monkeypatch, data_client) -> None:
    async def _fake_refresh_dataset(*, db, auth, dataset_id):  # type: ignore[no-untyped-def]
        assert dataset_id == "ds_refresh"
        return {"status": "ready", "dataset_id": dataset_id}

    monkeypatch.setattr("apps.api_server.routers.data.refresh_dataset", _fake_refresh_dataset)

    resp = await data_client.post("/v1/data/ds_refresh/refresh")
    assert resp.status_code == 200
    assert resp.json()["dataset_id"] == "ds_refresh"


@pytest.mark.anyio
async def test_disconnect_data_route_deletes_dataset(monkeypatch, data_client) -> None:
    monkeypatch.setattr(
        "apps.api_server.routers.data.get_visible_dataset_entry",
        lambda _org_id, _dataset_id, _auth: {
            "id": "ds_dead",
            "dataset_name": "Dead",
            "visibility": "private",
            "owner_user_id": "u1",
            "connector_id": None,
        },
    )
    monkeypatch.setattr(
        "apps.api_server.routers.data.sreg.delete_source", lambda _org_id, _dataset_id: True
    )
    monkeypatch.setattr("apps.api_server.routers.data.sreg.list_sources", lambda _org_id: [])

    resp = await data_client.delete("/v1/data/ds_dead")
    assert resp.status_code == 200
    assert resp.json() == {
        "dataset_id": "ds_dead",
        "status": "deleted",
        "connection_deleted": False,
    }
