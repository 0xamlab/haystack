from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from apps.api_server.services import data_connection_service as dcs


def test_normalize_visibility_blocks_shared_for_member() -> None:
    with pytest.raises(HTTPException) as exc:
        dcs.normalize_visibility("shared", {"org_id": "org_a", "role": "member"})
    assert exc.value.status_code == 403
    assert exc.value.detail["error"]["code"] == "access_scope_denied"


def test_normalize_connection_provider_maps_database_sqlite() -> None:
    broad, provider = dcs.normalize_connection_provider(
        "database",
        {"connection_string": "sqlite+pysqlite:////tmp/test.db"},
    )
    assert broad == "database"
    assert provider == "sqlite"


@pytest.mark.asyncio
async def test_browse_connector_real_sqlite_uses_explicit_provider(tmp_path: Path) -> None:
    db_path = tmp_path / "sample.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("create table backlog(id integer primary key, amount real)")
        conn.commit()
    finally:
        conn.close()

    items, message = await dcs.browse_connector_real("sqlite", {"path": str(db_path)})
    assert len(items) == 1
    assert items[0]["selection"] == {"table": "backlog"}
    assert "Found 1" in message


@pytest.mark.asyncio
async def test_connect_data_returns_needs_selection_for_database(monkeypatch) -> None:
    connector = SimpleNamespace(
        id=uuid.uuid4(),
        connector_type=SimpleNamespace(value="sqlite"),
        visibility="private",
        config_json=json.dumps({"path": "/tmp/example.db"}),
    )

    async def _fake_create_or_reuse_connector(**_kwargs):
        return connector

    async def _fake_test_and_persist_connector(_connector, _db):
        return True, "ok", 12

    async def _fake_browse_connector_real(_connector_type: str, _config: dict[str, object]):
        return (
            [
                {"id": "main.orders", "label": "main.orders", "selection": {"table": "main.orders"}},
                {"id": "main.customers", "label": "main.customers", "selection": {"table": "main.customers"}},
            ],
            "Found 2 tables",
        )

    monkeypatch.setattr(dcs, "create_or_reuse_connector", _fake_create_or_reuse_connector)
    monkeypatch.setattr(dcs, "_test_and_persist_connector", _fake_test_and_persist_connector)
    monkeypatch.setattr(dcs, "browse_connector_real", _fake_browse_connector_real)

    result = await dcs.connect_data(
        db=object(),  # type: ignore[arg-type]
        auth={"org_id": "org_a", "role": "owner"},
        payload={
            "connection_type": "database",
            "provider": "sqlite",
            "connection_config": {"path": "/tmp/example.db"},
            "dataset_name": "Orders",
        },
    )

    assert result["status"] == "needs_selection"
    assert result["connection_id"] == str(connector.id)
    assert len(result["choices"]) == 2


@pytest.mark.asyncio
async def test_connect_data_returns_failed_when_browse_fails(monkeypatch) -> None:
    connector = SimpleNamespace(
        id=uuid.uuid4(),
        connector_type=SimpleNamespace(value="sqlite"),
        visibility="private",
        config_json=json.dumps({"path": "/tmp/example.db"}),
    )

    async def _fake_create_or_reuse_connector(**_kwargs):
        return connector

    async def _fake_test_and_persist_connector(_connector, _db):
        return True, "ok", 12

    async def _fake_browse_connector_real(_connector_type: str, _config: dict[str, object]):
        raise RuntimeError("boom")

    monkeypatch.setattr(dcs, "create_or_reuse_connector", _fake_create_or_reuse_connector)
    monkeypatch.setattr(dcs, "_test_and_persist_connector", _fake_test_and_persist_connector)
    monkeypatch.setattr(dcs, "browse_connector_real", _fake_browse_connector_real)

    result = await dcs.connect_data(
        db=object(),  # type: ignore[arg-type]
        auth={"org_id": "org_a", "role": "owner"},
        payload={
            "connection_type": "database",
            "provider": "sqlite",
            "connection_config": {"path": "/tmp/example.db"},
            "dataset_name": "Orders",
        },
    )

    assert result == {
        "status": "failed",
        "message": "Browse failed: boom",
        "connection_id": str(connector.id),
        "connection_type": "database",
        "provider": "sqlite",
        "visibility": "private",
        "latency_ms": 12,
    }


@pytest.mark.asyncio
async def test_connect_data_returns_failed_when_connector_test_fails(monkeypatch) -> None:
    connector = SimpleNamespace(
        id=uuid.uuid4(),
        connector_type=SimpleNamespace(value="sqlite"),
        visibility="private",
        config_json=json.dumps({"path": "/tmp/example.db"}),
    )

    async def _fake_create_or_reuse_connector(**_kwargs):
        return connector

    async def _fake_test_and_persist_connector(_connector, _db):
        return False, "boom", 7

    monkeypatch.setattr(dcs, "create_or_reuse_connector", _fake_create_or_reuse_connector)
    monkeypatch.setattr(dcs, "_test_and_persist_connector", _fake_test_and_persist_connector)

    result = await dcs.connect_data(
        db=object(),  # type: ignore[arg-type]
        auth={"org_id": "org_a", "role": "owner"},
        payload={
            "connection_type": "database",
            "provider": "sqlite",
            "connection_config": {"path": "/tmp/example.db"},
            "dataset_name": "Orders",
        },
    )

    assert result == {
        "status": "failed",
        "message": "boom",
        "connection_id": str(connector.id),
        "connection_type": "database",
        "provider": "sqlite",
        "visibility": "private",
        "latency_ms": 7,
    }


@pytest.mark.asyncio
async def test_connect_data_resumes_database_selection_from_saved_connector(monkeypatch) -> None:
    connector = SimpleNamespace(
        id=uuid.uuid4(),
        connector_type=SimpleNamespace(value="postgres"),
        visibility="private",
        config_json=json.dumps(
            {
                "host": "localhost",
                "port": 5432,
                "database": "decision_engine",
                "user": "angel",
                "password": "",
            }
        ),
    )
    captured: dict[str, object] = {}

    async def _fake_get_visible_connector(_db, connector_id, _auth):
        assert connector_id == connector.id
        return connector

    async def _fake_test_and_persist_connector(_connector, _db):
        return True, "ok", 9

    async def _fake_register_source_impl(payload, auth, **kwargs):  # type: ignore[no-untyped-def]
        captured["payload"] = payload
        captured["auth"] = auth
        captured["kwargs"] = kwargs
        return {
            "source_id": "pg_dataset",
            "schema": {
                "row_count": 3,
                "columns": [{"name": "amount"}],
                "roles_summary": {"derived_measure": 1},
            },
            "latency_ms": 21,
        }

    monkeypatch.setattr(dcs, "get_visible_connector", _fake_get_visible_connector)
    monkeypatch.setattr(dcs, "_test_and_persist_connector", _fake_test_and_persist_connector)
    monkeypatch.setattr("apps.api_server.routers.sources._register_source_impl", _fake_register_source_impl)

    result = await dcs.connect_data(
        db=object(),  # type: ignore[arg-type]
        auth={"org_id": "org_a", "role": "owner"},
        payload={
            "connection_type": "database",
            "dataset_name": "Orders",
            "connection_id": str(connector.id),
            "selection": {"table": "aa_golive.data_connect_backlog"},
        },
    )

    assert result["status"] == "ready"
    assert result["provider"] == "postgres"
    assert result["connection_id"] == str(connector.id)
    assert captured["kwargs"]["connector_id"] == str(connector.id)
    assert captured["kwargs"]["selection"] == {"table": "aa_golive.data_connect_backlog"}
    assert captured["payload"].source.connection["query"] == 'SELECT * FROM "aa_golive"."data_connect_backlog"'


@pytest.mark.asyncio
async def test_connect_data_returns_ready_for_direct_file_upload(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def _fake_register_source_impl(payload, auth, **kwargs):  # type: ignore[no-untyped-def]
        captured["payload"] = payload
        captured["auth"] = auth
        captured["kwargs"] = kwargs
        return {
            "source_id": "ds_ready",
            "schema": {
                "row_count": 2,
                "columns": [{"name": "amount"}],
                "roles_summary": {"derived_measure": 1},
            },
            "latency_ms": 15,
        }

    monkeypatch.setattr("apps.api_server.routers.sources._register_source_impl", _fake_register_source_impl)

    auth = {
        "org_id": "org_a",
        "role": "owner",
        "user_id": uuid.uuid4(),
        "key_id": uuid.uuid4(),
    }
    result = await dcs.connect_data(
        db=object(),  # type: ignore[arg-type]
        auth=auth,
        payload={
            "connection_type": "file_upload",
            "dataset_name": "Sales",
            "csv": "amount,qty\n10,1\n20,2\n",
            "visibility": "shared",
            "description": "sales upload",
        },
    )

    assert result["status"] == "ready"
    assert result["dataset_id"] == "ds_ready"
    assert result["schema_summary"]["columns"] == 1
    assert captured["kwargs"]["dataset_name"] == "Sales"
    assert captured["kwargs"]["visibility"] == "shared"
    assert captured["kwargs"]["refreshable"] is False


def test_dataset_visibility_filters_private_and_shared() -> None:
    auth = {"org_id": "org_a", "role": "member", "user_id": "u1", "key_id": "k1"}
    entries = [
        {"id": "shared_ds", "visibility": "shared"},
        {"id": "private_owned", "visibility": "private", "owner_user_id": "u1"},
        {"id": "private_other", "visibility": "private", "owner_user_id": "u2"},
    ]
    visible = dcs.filter_visible_datasets(entries, auth)
    assert [entry["id"] for entry in visible] == ["shared_ds", "private_owned"]


def test_build_object_storage_connection_supports_public_azure_blob_url() -> None:
    connection = dcs._build_object_storage_connection(  # type: ignore[attr-defined]
        "azure",
        {
            "blob_url": "https://example.blob.core.windows.net/samplefiles/StormEvents.csv",
            "account_url": "https://example.blob.core.windows.net",
            "container": "samplefiles",
            "anonymous": True,
        },
        {},
    )

    assert connection["type"] == "azure_blob"
    assert connection["blob_url"].endswith("/StormEvents.csv")
    assert connection["blob"] == "StormEvents.csv"
    assert connection["anonymous"] is True
