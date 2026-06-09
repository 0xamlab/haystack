"""Tests for test_data_connections: connect_data_a.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_3967a6fe-cb7-3/tests/test_data_connections.py during modularization.
"""
from __future__ import annotations

from tests._test_data_connections_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
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

    async def _fake_browse_connector_real_detailed(
        _connector_type: str, _config: dict[str, object]
    ):
        return (
            [
                {
                    "id": "main.orders",
                    "label": "main.orders",
                    "selection": {"table": "main.orders"},
                },
                {
                    "id": "main.customers",
                    "label": "main.customers",
                    "selection": {"table": "main.customers"},
                },
            ],
            "Found 2 tables",
            {
                "scope_noun": "catalog",
                "returned_count": 2,
                "count_kind": "exact",
                "matching_total_count": 2,
                "scope_total_count": 2,
                "more_available": False,
                "sampling_reason": None,
            },
        )

    monkeypatch.setattr(dcs, "create_or_reuse_connector", _fake_create_or_reuse_connector)
    monkeypatch.setattr(dcs, "_test_and_persist_connector", _fake_test_and_persist_connector)
    monkeypatch.setattr(dcs, "browse_connector_real_detailed", _fake_browse_connector_real_detailed)

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
    assert result["labels"] == {
        "entity_noun": "table",
        "entity_noun_plural": "tables",
        "row_noun": "row",
        "row_noun_plural": "rows",
        "rows_unavailable": False,
        "sampled": False,
    }
    assert result["discovery"]["scope_noun"] == "catalog"
    assert result["discovery"]["count_kind"] == "exact"
    assert len(result["choices"]) == 2


@pytest.mark.anyio
async def test_connect_data_returns_needs_selection_for_elasticsearch(monkeypatch) -> None:
    connector = SimpleNamespace(
        id=uuid.uuid4(),
        connector_type=SimpleNamespace(value="elasticsearch"),
        visibility="private",
        config_json=json.dumps({"url": "https://elastic.example.com:443", "api_key": "secret"}),
    )

    async def _fake_create_or_reuse_connector(**_kwargs):
        return connector

    async def _fake_test_and_persist_connector(_connector, _db):
        return True, "ok", 12

    async def _fake_browse_connector_real_detailed(
        _connector_type: str, _config: dict[str, object]
    ):
        return (
            [
                {"id": "logs-a", "label": "logs-a", "selection": {"index": "logs-a"}},
                {"id": "logs-b", "label": "logs-b", "selection": {"index": "logs-b"}},
            ],
            "Found 2 browsable Elasticsearch indices",
            {
                "scope_noun": "index catalog",
                "returned_count": 2,
                "count_kind": "exact",
                "matching_total_count": 2,
                "scope_total_count": 2,
                "more_available": False,
                "sampling_reason": None,
            },
        )

    monkeypatch.setattr(dcs, "create_or_reuse_connector", _fake_create_or_reuse_connector)
    monkeypatch.setattr(dcs, "_test_and_persist_connector", _fake_test_and_persist_connector)
    monkeypatch.setattr(dcs, "browse_connector_real_detailed", _fake_browse_connector_real_detailed)

    result = await dcs.connect_data(
        db=object(),  # type: ignore[arg-type]
        auth={"org_id": "org_a", "role": "owner"},
        payload={
            "connection_type": "database",
            "provider": "elasticsearch",
            "connection_config": {"url": "https://elastic.example.com:443", "api_key": "secret"},
            "dataset_name": "Elastic logs",
        },
    )

    assert result["status"] == "needs_selection"
    assert result["provider"] == "elasticsearch"
    assert result["labels"] == {
        "entity_noun": "index",
        "entity_noun_plural": "indices",
        "row_noun": "document",
        "row_noun_plural": "documents",
        "rows_unavailable": False,
        "sampled": False,
    }
    assert result["discovery"]["scope_noun"] == "index catalog"
    assert len(result["choices"]) == 2


@pytest.mark.anyio
async def test_connect_data_returns_needs_selection_for_redis(monkeypatch) -> None:
    connector = SimpleNamespace(
        id=uuid.uuid4(),
        connector_type=SimpleNamespace(value="redis"),
        visibility="private",
        config_json=json.dumps(
            {"url": "redis://default:pass@redis.example.com:6379/0", "limit": 2}
        ),
    )

    async def _fake_create_or_reuse_connector(**_kwargs):
        return connector

    async def _fake_test_and_persist_connector(_connector, _db):
        return True, "ok", 9

    async def _fake_browse_connector_real_detailed(
        _connector_type: str, _config: dict[str, object]
    ):
        return (
            [
                {"id": "orders:1", "label": "orders:1", "selection": {"keys": ["orders:1"]}},
                {"id": "orders:2", "label": "orders:2", "selection": {"keys": ["orders:2"]}},
            ],
            "Found 2 browsable Redis keys",
            {
                "scope_noun": "keyspace",
                "returned_count": 2,
                "count_kind": "sample",
                "matching_total_count": None,
                "scope_total_count": 10,
                "more_available": True,
                "sampling_reason": "keyspace_scan_limit",
            },
        )

    monkeypatch.setattr(dcs, "create_or_reuse_connector", _fake_create_or_reuse_connector)
    monkeypatch.setattr(dcs, "_test_and_persist_connector", _fake_test_and_persist_connector)
    monkeypatch.setattr(dcs, "browse_connector_real_detailed", _fake_browse_connector_real_detailed)

    result = await dcs.connect_data(
        db=object(),  # type: ignore[arg-type]
        auth={"org_id": "org_a", "role": "owner"},
        payload={
            "connection_type": "database",
            "provider": "redis",
            "connection_config": {
                "url": "redis://default:pass@redis.example.com:6379/0",
                "limit": 2,
            },
            "dataset_name": "Redis cache",
        },
    )

    assert result["status"] == "needs_selection"
    assert result["provider"] == "redis"
    assert result["labels"] == {
        "entity_noun": "key",
        "entity_noun_plural": "keys",
        "row_noun": "value",
        "row_noun_plural": "values",
        "rows_unavailable": True,
        "sampled": True,
    }
    assert result["discovery"] == {
        "scope_noun": "keyspace",
        "returned_count": 2,
        "count_kind": "sample",
        "matching_total_count": None,
        "scope_total_count": 10,
        "more_available": True,
        "sampling_reason": "keyspace_scan_limit",
    }
    assert len(result["choices"]) == 2


@pytest.mark.anyio
async def test_connect_data_returns_needs_selection_for_neo4j(monkeypatch) -> None:
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
                "limit": 2,
            }
        ),
    )

    async def _fake_create_or_reuse_connector(**_kwargs):
        return connector

    async def _fake_test_and_persist_connector(_connector, _db):
        return True, "ok", 11

    async def _fake_browse_connector_real_detailed(
        _connector_type: str, _config: dict[str, object]
    ):
        return (
            [
                {"id": "label:Airport", "label": "Airport", "selection": {"label": "Airport"}},
                {
                    "id": "relationship_type:ROUTES_TO",
                    "label": "ROUTES_TO",
                    "selection": {"relationship_type": "ROUTES_TO"},
                },
            ],
            "Found 2 browsable Neo4j labels and relationship types",
            {
                "scope_noun": "graph catalog",
                "returned_count": 2,
                "count_kind": "exact",
                "matching_total_count": 2,
                "scope_total_count": 2,
                "more_available": False,
                "sampling_reason": None,
            },
        )

    monkeypatch.setattr(dcs, "create_or_reuse_connector", _fake_create_or_reuse_connector)
    monkeypatch.setattr(dcs, "_test_and_persist_connector", _fake_test_and_persist_connector)
    monkeypatch.setattr(dcs, "browse_connector_real_detailed", _fake_browse_connector_real_detailed)

    result = await dcs.connect_data(
        db=object(),  # type: ignore[arg-type]
        auth={"org_id": "org_a", "role": "owner"},
        payload={
            "connection_type": "database",
            "provider": "neo4j",
            "connection_config": {
                "uri": "neo4j+s://graph.example.com",
                "username": "neo4j",
                "password": "secret",
                "database": "neo4j",
                "limit": 2,
            },
            "dataset_name": "Route graph",
        },
    )

    assert result["status"] == "needs_selection"
    assert result["provider"] == "neo4j"
    assert result["labels"] == {
        "entity_noun": "graph type",
        "entity_noun_plural": "graph types",
        "row_noun": "record",
        "row_noun_plural": "records",
        "rows_unavailable": True,
        "sampled": False,
    }
    assert result["discovery"]["scope_noun"] == "graph catalog"
    assert len(result["choices"]) == 2


@pytest.mark.anyio
async def test_connect_data_returns_full_database_choices_when_schema_is_explicit(
    monkeypatch,
) -> None:
    connector = SimpleNamespace(
        id=uuid.uuid4(),
        connector_type=SimpleNamespace(value="postgres"),
        visibility="private",
        config_json=json.dumps(
            {
                "host": "localhost",
                "port": 5432,
                "database": "aerogenie",
                "user": "angel",
                "password": "",
                "schema": "erp_augmented",
            }
        ),
    )

    async def _fake_create_or_reuse_connector(**_kwargs):
        return connector

    async def _fake_test_and_persist_connector(_connector, _db):
        return True, "ok", 18

    async def _fake_browse_connector_real_detailed(
        _connector_type: str, _config: dict[str, object]
    ):
        return (
            [
                {
                    "id": f"erp_augmented.table_{idx:03d}",
                    "label": f"erp_augmented.table_{idx:03d}",
                    "selection": {"table": f"erp_augmented.table_{idx:03d}"},
                }
                for idx in range(80)
            ],
            "Found 80 tables",
            {
                "scope_noun": "catalog",
                "returned_count": 80,
                "count_kind": "exact",
                "matching_total_count": 80,
                "scope_total_count": 80,
                "more_available": False,
                "sampling_reason": None,
            },
        )

    monkeypatch.setattr(dcs, "create_or_reuse_connector", _fake_create_or_reuse_connector)
    monkeypatch.setattr(dcs, "_test_and_persist_connector", _fake_test_and_persist_connector)
    monkeypatch.setattr(dcs, "browse_connector_real_detailed", _fake_browse_connector_real_detailed)

    result = await dcs.connect_data(
        db=object(),  # type: ignore[arg-type]
        auth={"org_id": "org_a", "role": "owner"},
        payload={
            "connection_type": "database",
            "provider": "postgres",
            "connection_config": {
                "host": "localhost",
                "port": 5432,
                "database": "aerogenie",
                "user": "angel",
                "password": "",
                "schema": "erp_augmented",
            },
            "dataset_name": "ERP",
        },
    )

    assert result["status"] == "needs_selection"
    assert result["labels"]["entity_noun"] == "table"
    assert result["labels"]["sampled"] is False
    assert result["discovery"]["count_kind"] == "exact"
    assert len(result["choices"]) == 80


@pytest.mark.anyio
async def test_connect_data_truncates_database_choices_without_schema_scope(
    monkeypatch,
) -> None:
    connector = SimpleNamespace(
        id=uuid.uuid4(),
        connector_type=SimpleNamespace(value="postgres"),
        visibility="private",
        config_json=json.dumps(
            {
                "host": "localhost",
                "port": 5432,
                "database": "aerogenie",
                "user": "angel",
                "password": "",
            }
        ),
    )

    async def _fake_create_or_reuse_connector(**_kwargs):
        return connector

    async def _fake_test_and_persist_connector(_connector, _db):
        return True, "ok", 18

    async def _fake_browse_connector_real_detailed(
        _connector_type: str, _config: dict[str, object]
    ):
        return (
            [
                {
                    "id": f"schema.table_{idx:03d}",
                    "label": f"schema.table_{idx:03d}",
                    "selection": {"table": f"schema.table_{idx:03d}"},
                }
                for idx in range(80)
            ],
            "Found 80 tables",
            {
                "scope_noun": "catalog",
                "returned_count": 80,
                "count_kind": "sample",
                "matching_total_count": None,
                "scope_total_count": None,
                "more_available": True,
                "sampling_reason": "browse_limit",
            },
        )

    monkeypatch.setattr(dcs, "create_or_reuse_connector", _fake_create_or_reuse_connector)
    monkeypatch.setattr(dcs, "_test_and_persist_connector", _fake_test_and_persist_connector)
    monkeypatch.setattr(dcs, "browse_connector_real_detailed", _fake_browse_connector_real_detailed)

    result = await dcs.connect_data(
        db=object(),  # type: ignore[arg-type]
        auth={"org_id": "org_a", "role": "owner"},
        payload={
            "connection_type": "database",
            "provider": "postgres",
            "connection_config": {
                "host": "localhost",
                "port": 5432,
                "database": "aerogenie",
                "user": "angel",
                "password": "",
            },
            "dataset_name": "ERP",
        },
    )

    assert result["status"] == "needs_selection"
    assert result["labels"]["entity_noun"] == "table"
    assert result["labels"]["sampled"] is True
    assert result["discovery"]["count_kind"] == "sample"
    assert len(result["choices"]) == 50


@pytest.mark.anyio
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

    async def _fake_browse_connector_real_detailed(
        _connector_type: str, _config: dict[str, object]
    ):
        raise RuntimeError("boom")

    monkeypatch.setattr(dcs, "create_or_reuse_connector", _fake_create_or_reuse_connector)
    monkeypatch.setattr(dcs, "_test_and_persist_connector", _fake_test_and_persist_connector)
    monkeypatch.setattr(dcs, "browse_connector_real_detailed", _fake_browse_connector_real_detailed)

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
        "message": "Browse failed.",
        "error": {
            "code": "browse_failed",
            "message": "Browse failed.",
        },
        "connection_id": str(connector.id),
        "connection_type": "database",
        "provider": "sqlite",
        "visibility": "private",
        "latency_ms": 12,
    }


@pytest.mark.anyio
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


@pytest.mark.anyio
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
    monkeypatch.setattr(
        "apps.api_server.routers.sources._register_source_impl", _fake_register_source_impl
    )

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
    assert (
        captured["payload"].source.connection["query"]
        == 'SELECT * FROM "aa_golive"."data_connect_backlog"'
    )


@pytest.mark.anyio
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

    monkeypatch.setattr(
        "apps.api_server.routers.sources._register_source_impl", _fake_register_source_impl
    )

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


@pytest.mark.anyio
async def test_connect_data_accepts_canonical_database_connector(monkeypatch) -> None:
    connector = SimpleNamespace(
        id=uuid.uuid4(),
        connector_type=SimpleNamespace(value="postgres"),
        visibility="private",
        config_json=json.dumps(
            {"connection_string": "postgresql://analytics:secret@localhost:5432/orders"}
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
            "source_id": "pg_dataset",
            "schema": {
                "row_count": 3,
                "columns": [{"name": "amount"}],
                "roles_summary": {"derived_measure": 1},
            },
            "latency_ms": 21,
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
            "dataset_name": "Orders",
            "connector": {
                "type": "postgres",
                "location": {
                    "connection_string": "postgresql://analytics:secret@localhost:5432/orders",
                    "schema": "public",
                    "table": "orders",
                },
            },
        },
    )

    assert result["status"] == "ready"
    assert result["provider"] == "postgres"
    assert result["connection_id"] == str(connector.id)
    assert captured["kwargs"]["selection"] == {"table": "public.orders"}
    assert captured["payload"].source.connection["query"] == 'SELECT * FROM "public"."orders"'


