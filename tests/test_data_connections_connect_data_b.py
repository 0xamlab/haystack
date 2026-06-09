"""Tests for test_data_connections: connect_data_b.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_3967a6fe-cb7-3/tests/test_data_connections.py during modularization.
"""
from __future__ import annotations

from tests._test_data_connections_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
async def test_connect_data_accepts_canonical_neo4j_connector(monkeypatch) -> None:
    connector = SimpleNamespace(
        id=uuid.uuid4(),
        connector_type=SimpleNamespace(value="neo4j"),
        visibility="private",
        config_json=json.dumps(
            {
                "uri": "neo4j+s://graph.example.com",
                "username": "neo4j",
                "password": "secret",
                "database": "neo4j",
            }
        ),
    )
    captured: dict[str, object] = {}

    async def _fake_create_or_reuse_connector(**_kwargs):
        return connector

    async def _fake_test_and_persist_connector(_connector, _db):
        return True, "ok", 9

    async def _fake_register_source_impl(payload, auth, **kwargs):  # type: ignore[no-untyped-def]
        captured["payload"] = payload
        captured["auth"] = auth
        captured["kwargs"] = kwargs
        return {
            "source_id": "graph_dataset",
            "schema": {
                "row_count": 3,
                "columns": [{"name": "code"}],
                "roles_summary": {"other": 1},
            },
            "latency_ms": 17,
        }

    monkeypatch.setattr(dcs, "create_or_reuse_connector", _fake_create_or_reuse_connector)
    monkeypatch.setattr(dcs, "_test_and_persist_connector", _fake_test_and_persist_connector)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._register_source_impl", _fake_register_source_impl
    )

    result = await dcs.connect_data(
        db=object(),  # type: ignore[arg-type]
        auth={"org_id": "org_a", "role": "owner"},
        payload={
            "dataset_name": "Graph airports",
            "connector": {
                "type": "neo4j",
                "location": {
                    "uri": "neo4j+s://graph.example.com",
                    "database": "neo4j",
                    "label": "Airport",
                },
                "auth": {"credentials": {"username": "neo4j", "password": "secret"}},
            },
        },
    )

    assert result["status"] == "ready"
    assert result["provider"] == "neo4j"
    assert result["connection_id"] == str(connector.id)
    assert captured["payload"].source.connection["type"] == "neo4j"
    assert (
        captured["payload"].source.connection["query"]
        == "MATCH (n:`Airport`) RETURN n LIMIT $limit"
    )
    assert captured["payload"].source.connection["parameters"] == {"limit": 1000}


@pytest.mark.anyio
async def test_connect_data_returns_structured_400_when_registration_processing_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "tickets.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("create table tickets(ticket_id integer primary key, total_usd real)")
        conn.execute("insert into tickets(ticket_id, total_usd) values (1, 19.5), (2, 21.0)")
        conn.commit()
    finally:
        conn.close()

    connector = SimpleNamespace(
        id=uuid.uuid4(),
        connector_type=SimpleNamespace(value="sqlite"),
        visibility="private",
        config_json=json.dumps({"path": str(db_path)}),
    )

    async def _fake_create_or_reuse_connector(**_kwargs):
        return connector

    async def _fake_test_and_persist_connector(_connector, _db):
        return True, "ok", 7

    def _raise_schema_graph(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("schema graph boom")

    monkeypatch.setattr(
        "apps.api_server.services.source_registry._SOURCES_DIR",
        Path(tmp_path) / "sources",
    )
    monkeypatch.setattr(dcs, "create_or_reuse_connector", _fake_create_or_reuse_connector)
    monkeypatch.setattr(dcs, "_test_and_persist_connector", _fake_test_and_persist_connector)
    monkeypatch.setattr("apps.api_server.routers.sources.build_schema_graph", _raise_schema_graph)

    with pytest.raises(HTTPException) as exc_info:
        await dcs.connect_data(
            db=object(),  # type: ignore[arg-type]
            auth={"org_id": "org_a", "role": "owner"},
            payload={
                "connection_type": "database",
                "provider": "sqlite",
                "dataset_name": "tickets",
                "connection_config": {"path": str(db_path)},
                "selection": {"table": "tickets"},
            },
        )

    assert exc_info.value.status_code == 400
    detail = exc_info.value.detail["error"]
    assert detail["code"] == "source_registration_failed"
    assert detail["details"]["stage"] == "build_schema_graph"
    assert detail["details"]["error_type"] == "RuntimeError"
    assert "schema graph boom" in detail["message"]


@pytest.mark.anyio
async def test_connect_data_accepts_canonical_file_connector_path(
    monkeypatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text("amount,qty\n10,1\n20,2\n", encoding="utf-8")

    async def _fake_register_source_impl(payload, auth, **kwargs):  # type: ignore[no-untyped-def]
        captured["payload"] = payload
        captured["auth"] = auth
        captured["kwargs"] = kwargs
        return {
            "source_id": "ds_file",
            "schema": {
                "row_count": 2,
                "columns": [{"name": "amount"}],
                "roles_summary": {"derived_measure": 1},
            },
            "latency_ms": 11,
        }

    monkeypatch.setattr(
        "apps.api_server.routers.sources._register_source_impl", _fake_register_source_impl
    )

    result = await dcs.connect_data(
        db=object(),  # type: ignore[arg-type]
        auth={"org_id": "org_a", "role": "owner"},
        payload={
            "dataset_name": "Orders CSV",
            "connector": {
                "type": "csv",
                "location": {"path": str(csv_path)},
                "options": {"delimiter": ","},
            },
        },
    )

    assert result["status"] == "ready"
    assert result["provider"] == "file"
    assert result["refreshable"] is True
    assert captured["payload"].source.connection == {
        "type": "file",
        "file_type": "csv",
        "file_path": str(csv_path),
        "delimiter": ",",
    }
    assert captured["kwargs"]["source_definition"] == {
        "direct": {"path": str(csv_path), "file_type": "csv"}
    }


