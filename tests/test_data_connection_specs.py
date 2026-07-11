from __future__ import annotations

import pytest

from apps.api_server.services import data_connection_browse as browse
from apps.api_server.services import data_connection_specs as specs


class _FakeResult:
    def __init__(self, rows: list[tuple[str, str, str, int | None]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[str, str, str, int | None]]:
        return list(self._rows)


class _FakeConnectionContext:
    def __init__(self, rows: list[tuple[str, str, str, int | None]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, dict[str, object]]] = []

    def __enter__(self) -> object:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def execute(self, query, params=None):  # type: ignore[no-untyped-def]
        self.calls.append((str(query), dict(params or {})))
        return _FakeResult(self.rows)


class _FakeEngine:
    def __init__(self, rows: list[tuple[str, str, str, int | None]]) -> None:
        self.disposed = False
        self.connection = _FakeConnectionContext(rows)

    def connect(self) -> _FakeConnectionContext:
        return self.connection

    def dispose(self) -> None:
        self.disposed = True


@pytest.mark.anyio
async def test_browse_sql_returns_full_schema_when_schema_filter_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [("erp_augmented", f"table_{idx:03d}", "table", idx) for idx in range(250)]
    engine = _FakeEngine(rows)

    monkeypatch.setattr("sqlalchemy.create_engine", lambda *_args, **_kwargs: engine)
    monkeypatch.setattr(
        "apps.api_server.services.data_connection_browse_sql.enforce_sql_connection_egress",
        lambda *_args, **_kwargs: None,
    )

    items, message = await specs._browse_sql(
        {
            "connection_string": "postgresql://angel:@localhost:5432/aerogenie",
            "schema": "erp_augmented",
        },
        provider="postgres",
    )

    assert len(items) == 250
    assert all(item["schema"] == "erp_augmented" for item in items)
    assert items[3]["row_count"] == 3
    assert message == "Found 250 browsable database objects"
    query_text, params = engine.connection.calls[0]
    assert "FROM pg_class" in query_text
    assert "n.nspname = :schema_name" in query_text
    assert params == {"schema_name": "erp_augmented"}
    assert engine.disposed is False
    specs._clear_sync_browse_engine_cache()
    assert engine.disposed is True


@pytest.mark.anyio
async def test_browse_sql_preserves_global_cap_without_schema_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [("public", f"table_{idx:03d}", "table", idx) for idx in range(200)]
    engine = _FakeEngine(rows)

    monkeypatch.setattr("sqlalchemy.create_engine", lambda *_args, **_kwargs: engine)
    monkeypatch.setattr(
        "apps.api_server.services.data_connection_browse_sql.enforce_sql_connection_egress",
        lambda *_args, **_kwargs: None,
    )

    items, message = await specs._browse_sql(
        {
            "connection_string": "postgresql://angel:@localhost:5432/aerogenie",
        },
        provider="postgres",
    )

    assert len(items) == 200
    assert message == "Found 200 browsable database objects"
    query_text, params = engine.connection.calls[0]
    assert "FROM pg_class" in query_text
    assert "LIMIT 200" in query_text
    assert params == {}
    assert engine.disposed is False
    specs._clear_sync_browse_engine_cache()
    assert engine.disposed is True


@pytest.mark.anyio
async def test_browse_postgres_reuses_sync_engine_between_cache_misses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [("public", "orders", "table", 42)]
    create_calls = 0
    engine = _FakeEngine(rows)
    specs._clear_sync_browse_engine_cache()

    def _fake_create_engine(*_args, **_kwargs):
        nonlocal create_calls
        create_calls += 1
        return engine

    monkeypatch.setattr("sqlalchemy.create_engine", _fake_create_engine)

    first_items, first_message = await specs._browse_postgres_compatible_sql(
        {"connection_string": "postgresql://angel:@localhost:5432/aerogenie"},
        connection_string="postgresql://angel:@localhost:5432/aerogenie",
    )
    second_items, second_message = await specs._browse_postgres_compatible_sql(
        {"connection_string": "postgresql://angel:@localhost:5432/aerogenie"},
        connection_string="postgresql://angel:@localhost:5432/aerogenie",
    )

    assert create_calls == 1
    assert first_items == second_items
    assert first_items[0]["row_count"] == 42
    assert first_message == second_message == "Found 1 browsable database objects"
    specs._clear_sync_browse_engine_cache()
    assert engine.disposed is True


def test_build_source_spec_omits_database_limit_by_default() -> None:
    source, refreshable, _ = specs.build_source_spec(
        dataset_name="ERP table",
        connection_type="database",
        provider="postgres",
        connection_config={
            "host": "localhost",
            "port": 5432,
            "database": "aerogenie",
            "user": "angel",
            "password": "",
            "schema": "erp_augmented",
        },
        selection={"table": "erp_augmented.dbo__scheduled_tasks_history"},
        direct_payload={},
    )

    assert refreshable is True
    assert source.connection["type"] == "sql"
    assert source.connection["query"] == (
        'SELECT * FROM "erp_augmented"."dbo__scheduled_tasks_history"'
    )
    assert "limit" not in source.connection


def test_build_source_spec_preserves_explicit_database_limit() -> None:
    source, refreshable, _ = specs.build_source_spec(
        dataset_name="ERP table sample",
        connection_type="database",
        provider="postgres",
        connection_config={
            "host": "localhost",
            "port": 5432,
            "database": "aerogenie",
            "user": "angel",
            "password": "",
            "limit": 250,
        },
        selection={"table": "public.sample_table"},
        direct_payload={},
    )

    assert refreshable is True
    assert source.connection["limit"] == 250


def test_normalize_connection_provider_maps_database_clickhouse() -> None:
    broad, provider = specs.normalize_connection_provider(
        "database",
        {"provider": "clickhouse", "url": "https://clickhouse.example.com:8443"},
    )

    assert broad == "database"
    assert provider == "clickhouse"


def test_normalize_connection_provider_maps_database_oracle() -> None:
    broad, provider = specs.normalize_connection_provider(
        "database",
        {
            "service_name": "analytics_low",
            "host": "adb.example.oraclecloud.com",
        },
    )

    assert broad == "database"
    assert provider == "oracle"


def test_build_source_spec_builds_oracle_wallet_connection() -> None:
    source, refreshable, _ = specs.build_source_spec(
        dataset_name="Oracle orders",
        connection_type="database",
        provider="oracle",
        connection_config={
            "host": "adb.example.oraclecloud.com",
            "port": 1522,
            "service_name": "analytics_low",
            "user": "APP_READER",
            "password": "secret",
            "dsn": "tcps://adb.example.oraclecloud.com:1522/analytics_low",
            "wallet_location": "/secure/wallet",
            "wallet_password": "wallet-secret",
            "limit": 250,
        },
        selection={"table": "REPORTING.ORDERS"},
        direct_payload={},
    )

    assert refreshable is True
    assert source.connection == {
        "type": "oracle",
        "user": "APP_READER",
        "password": "secret",
        "dsn": "tcps://adb.example.oraclecloud.com:1522/analytics_low",
        "host": "adb.example.oraclecloud.com",
        "port": 1522,
        "service_name": "analytics_low",
        "wallet_location": "/secure/wallet",
        "wallet_password": "wallet-secret",
        "query": 'SELECT * FROM "REPORTING"."ORDERS"',
        "limit": 250,
    }


def test_build_database_connection_string_builds_oracle_url() -> None:
    connection_string = specs._build_database_connection_string(
        "oracle",
        {
            "host": "oracle.internal",
            "port": 1521,
            "service_name": "analytics",
            "user": "reader",
            "password": "p@ss word",
        },
    )

    assert connection_string == (
        "oracle+oracledb://reader:p%40ss%20word@oracle.internal:1521/?service_name=analytics"
    )


@pytest.mark.parametrize(
    ("connector_type", "config", "items", "expected"),
    [
        (
            "postgres",
            {},
            [{"id": "public.orders"}],
            {
                "entity_noun": "table",
                "entity_noun_plural": "tables",
                "row_noun": "row",
                "row_noun_plural": "rows",
                "rows_unavailable": False,
                "sampled": False,
            },
        ),
        (
            "clickhouse",
            {"database": "default"},
            [{"id": "default.execution_outcome_events"}],
            {
                "entity_noun": "table",
                "entity_noun_plural": "tables",
                "row_noun": "row",
                "row_noun_plural": "rows",
                "rows_unavailable": False,
                "sampled": False,
            },
        ),
        (
            "elasticsearch",
            {"limit": 2},
            [{"id": "logs-a"}, {"id": "logs-b"}],
            {
                "entity_noun": "index",
                "entity_noun_plural": "indices",
                "row_noun": "document",
                "row_noun_plural": "documents",
                "rows_unavailable": False,
                "sampled": True,
            },
        ),
        (
            "redis",
            {"limit": 2},
            [{"id": "orders:1"}, {"id": "orders:2"}],
            {
                "entity_noun": "key",
                "entity_noun_plural": "keys",
                "row_noun": "value",
                "row_noun_plural": "values",
                "rows_unavailable": True,
                "sampled": True,
            },
        ),
        (
            "neo4j",
            {"limit": 2},
            [{"id": "label:Airport"}, {"id": "relationship_type:ROUTES_TO"}],
            {
                "entity_noun": "graph type",
                "entity_noun_plural": "graph types",
                "row_noun": "record",
                "row_noun_plural": "records",
                "rows_unavailable": True,
                "sampled": True,
            },
        ),
    ],
)
def test_build_discovery_labels_matches_provider_semantics(
    connector_type: str,
    config: dict[str, object],
    items: list[dict[str, str]],
    expected: dict[str, object],
) -> None:
    labels = specs.build_discovery_labels(connector_type, config=config, items=items)

    assert labels == expected


def test_build_discovery_labels_marks_sql_sampling_only_without_explicit_scope() -> None:
    sampled_items = [{"id": f"public.table_{idx:03d}"} for idx in range(200)]

    postgres_unscoped = specs.build_discovery_labels(
        "postgres",
        config={},
        items=sampled_items,
    )
    postgres_scoped = specs.build_discovery_labels(
        "postgres",
        config={"schema": "erp_augmented"},
        items=sampled_items,
    )
    clickhouse_scoped = specs.build_discovery_labels(
        "clickhouse",
        config={"database": "default"},
        items=sampled_items,
    )

    assert postgres_unscoped["sampled"] is True
    assert postgres_scoped["sampled"] is False
    assert clickhouse_scoped["sampled"] is False


def test_build_discovery_metadata_captures_universal_sampling_state() -> None:
    elastic = specs.build_discovery_metadata(
        "elasticsearch",
        config={"limit": 2},
        items=[{"id": "logs-a"}, {"id": "logs-b"}],
    )
    redis = specs.build_discovery_metadata(
        "redis",
        config={"limit": 2},
        items=[{"id": "orders:1"}, {"id": "orders:2"}],
        provider_metadata={
            "keyspace_total_count": 10,
            "scan_exhausted": False,
        },
    )

    assert elastic == {
        "scope_noun": "index catalog",
        "returned_count": 2,
        "count_kind": "sample",
        "matching_total_count": None,
        "scope_total_count": None,
        "more_available": True,
        "sampling_reason": "browse_limit",
    }
    assert redis == {
        "scope_noun": "keyspace",
        "returned_count": 2,
        "count_kind": "sample",
        "matching_total_count": None,
        "scope_total_count": 10,
        "more_available": True,
        "sampling_reason": "keyspace_scan_limit",
    }


@pytest.mark.parametrize(
    ("config", "expected_provider"),
    [
        (
            {
                "provider": "elasticsearch",
                "url": "https://elastic.example.com:443",
                "api_key": "secret",
            },
            "elasticsearch",
        ),
        (
            {
                "provider": "neo4j",
                "uri": "neo4j+s://graph.example.com",
                "username": "neo4j",
                "password": "secret",
            },
            "neo4j",
        ),
        (
            {
                "provider": "redis",
                "url": "redis://default:pass@redis.example.com:6379/0",
            },
            "redis",
        ),
    ],
)
def test_normalize_connection_provider_accepts_connector_backends(
    config: dict[str, str],
    expected_provider: str,
) -> None:
    broad, provider = specs.normalize_connection_provider("database", config)

    assert broad == "database"
    assert provider == expected_provider


def test_build_source_spec_builds_clickhouse_query_with_backticks() -> None:
    source, refreshable, _ = specs.build_source_spec(
        dataset_name="ClickHouse decisions",
        connection_type="database",
        provider="clickhouse",
        connection_config={
            "url": "https://clickhouse.example.com:8443",
            "user": "default",
            "password": "pass",
            "database": "default",
        },
        selection={"table": "default.fees_decisions"},
        direct_payload={},
    )

    assert refreshable is True
    assert source.connection["type"] == "sql"
    assert source.connection["connection_string"] == (
        "clickhouse://default:pass@clickhouse.example.com:8443/default?secure=true"
    )
    assert source.connection["query"] == "SELECT * FROM `default`.`fees_decisions`"


def test_build_source_spec_builds_elasticsearch_connection() -> None:
    source, refreshable, _ = specs.build_source_spec(
        dataset_name="Elastic logs",
        connection_type="database",
        provider="elasticsearch",
        connection_config={
            "url": "https://elastic.example.com:443",
            "api_key": "secret",
        },
        selection={"index": "logs-*"},
        direct_payload={},
    )

    assert refreshable is True
    assert source.connection == {
        "type": "elasticsearch",
        "url": "https://elastic.example.com:443",
        "api_key": "secret",
        "index": "logs-*",
    }


def test_build_source_spec_builds_neo4j_connection_from_label_selection() -> None:
    source, refreshable, _ = specs.build_source_spec(
        dataset_name="Graph nodes",
        connection_type="database",
        provider="neo4j",
        connection_config={
            "uri": "neo4j+s://graph.example.com",
            "username": "neo4j",
            "password": "secret",
            "database": "neo4j",
            "limit": 25,
        },
        selection={"label": "Airport"},
        direct_payload={},
    )

    assert refreshable is True
    assert source.connection == {
        "type": "neo4j",
        "uri": "neo4j+s://graph.example.com",
        "username": "neo4j",
        "password": "secret",
        "database": "neo4j",
        "query": "MATCH (n:`Airport`) RETURN n LIMIT $limit",
        "parameters": {"limit": 25},
        "limit": 25,
    }


def test_build_source_spec_builds_redis_connection_from_key_selection() -> None:
    source, refreshable, _ = specs.build_source_spec(
        dataset_name="Redis keys",
        connection_type="database",
        provider="redis",
        connection_config={
            "url": "redis://default:pass@redis.example.com:6379/0",
            "value_max_items": 25,
        },
        selection={"keys": ["orders:1", "orders:2"]},
        direct_payload={},
    )

    assert refreshable is True
    assert source.connection == {
        "type": "redis",
        "url": "redis://default:pass@redis.example.com:6379/0",
        "keys": ["orders:1", "orders:2"],
        "value_max_items": 25,
    }


def test_build_database_connection_string_accepts_clickhouse_https_connection_string() -> None:
    connection_string = specs._build_database_connection_string(
        "clickhouse",
        {
            "connection_string": "https://default:pass@clickhouse.example.com:8443/default",
        },
    )

    assert connection_string == (
        "clickhouse://default:pass@clickhouse.example.com:8443/default?secure=true"
    )


@pytest.mark.anyio
async def test_browse_sql_clickhouse_returns_browsable_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeResult:
        result_rows = [
            ("default", "fees_decisions", "SharedMergeTree", 15234),
            ("default", "fees_decision_view", "View", None),
        ]

    class _FakeClickHouseClient:
        def __init__(self) -> None:
            self.closed = False
            self.queries: list[tuple[str, dict[str, object]]] = []

        def query(self, query: str, parameters: dict[str, object] | None = None):
            self.queries.append((query, parameters or {}))
            return _FakeResult()

        def close(self) -> None:
            self.closed = True

    client = _FakeClickHouseClient()

    monkeypatch.setattr(
        "apps.api_server.connectors.sql_connector.SQLConnector._clickhouse_connect",
        lambda _connection_string: client,
    )
    monkeypatch.setattr(
        "apps.api_server.connectors.sql_connector.SQLConnector._CLICKHOUSE_CLIENT_POOLS",
        {},
    )

    items, message = await specs._browse_sql(
        {
            "url": "https://clickhouse.example.com:8443",
            "user": "default",
            "password": "pass",
            "database": "default",
        },
        provider="clickhouse",
    )

    assert items == [
        {
            "id": "default.fees_decisions",
            "label": "default.fees_decisions",
            "kind": "table",
            "selection": {"table": "default.fees_decisions"},
            "schema": "default",
            "name": "fees_decisions",
            "row_count": 15234,
        },
        {
            "id": "default.fees_decision_view",
            "label": "default.fees_decision_view",
            "kind": "view",
            "selection": {"table": "default.fees_decision_view"},
            "schema": "default",
            "name": "fees_decision_view",
        },
    ]
    assert message == "Found 2 browsable database objects"
    assert client.closed is False
    from apps.api_server.connectors.sql_connector import SQLConnector

    SQLConnector._clear_clickhouse_client_pools()
    assert client.closed is True


@pytest.mark.anyio
async def test_browse_connector_real_supports_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def _fake_browse_redis_detailed(
        config: dict[str, object],
    ) -> tuple[list[dict[str, object]], dict[str, object]]:
        connection_url = str(config["url"])
        pattern = str(config.get("key_pattern", "*"))
        limit = int(config["limit"])
        captured["connection_url"] = connection_url
        captured["pattern"] = pattern
        captured["limit"] = limit
        return (
            [
                {
                    "id": "orders:1",
                    "label": "orders:1",
                    "kind": "key",
                    "selection": {"keys": ["orders:1"]},
                    "value_type": "hash",
                    "ttl_seconds": 60,
                }
            ],
            {
                "keyspace_total_count": 12,
                "scan_exhausted": True,
                "scan_cap": 100,
                "pattern": pattern,
                "returned_count": 1,
            },
        )

    monkeypatch.setattr(browse, "_browse_redis_detailed", _fake_browse_redis_detailed)

    items, message = await browse.browse_connector_real(
        "redis",
        {
            "url": "redis://default:pass@redis.example.com:15638/0",
            "key_pattern": "orders:*",
            "limit": 5,
        },
    )

    assert captured == {
        "connection_url": "redis://default:pass@redis.example.com:15638/0",
        "pattern": "orders:*",
        "limit": 5,
    }
    assert items == [
        {
            "id": "orders:1",
            "label": "orders:1",
            "kind": "key",
            "selection": {"keys": ["orders:1"]},
            "value_type": "hash",
            "ttl_seconds": 60,
        }
    ]
    assert message == "Found 1 browsable Redis keys"


@pytest.mark.anyio
async def test_browse_connector_real_supports_elasticsearch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_browse_sync(
        settings: dict[str, object],
        *,
        limit: int,
        include_hidden: bool,
        audit_context=None,
    ) -> list[dict[str, object]]:
        captured["settings"] = settings
        captured["limit"] = limit
        captured["include_hidden"] = include_hidden
        return [
            {
                "id": "market_data_parts_aar",
                "label": "market_data_parts_aar",
                "kind": "index",
                "selection": {"index": "market_data_parts_aar"},
                "health": "green",
                "status": "open",
                "docs_count": "3542699",
                "row_count": 3542699,
                "store_size": "1.1gb",
            }
        ]

    monkeypatch.setattr(
        "apps.api_server.connectors.elasticsearch_connector.ElasticsearchConnector._browse_sync",
        staticmethod(_fake_browse_sync),
    )

    items, message = await browse.browse_connector_real(
        "elasticsearch",
        {
            "url": "https://elastic.example.com:443",
            "api_key": "secret-key",
            "limit": 5,
        },
    )

    assert captured == {
        "settings": {
            "base_url": "https://elastic.example.com:443",
            "api_key": "secret-key",
            "host": "elastic.example.com",
            "port": 443,
        },
        "limit": 5,
        "include_hidden": False,
    }
    assert items == [
        {
            "id": "market_data_parts_aar",
            "label": "market_data_parts_aar",
            "kind": "index",
            "selection": {"index": "market_data_parts_aar"},
            "health": "green",
            "status": "open",
            "docs_count": "3542699",
            "row_count": 3542699,
            "store_size": "1.1gb",
        }
    ]
    assert message == "Found 1 browsable Elasticsearch indices"


@pytest.mark.anyio
async def test_browse_connector_real_reuses_short_ttl_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    browse._clear_browse_result_cache()

    async def _fake_browse_elasticsearch(
        _config: dict[str, object],
    ) -> tuple[list[dict[str, object]], str]:
        nonlocal calls
        calls += 1
        return (
            [
                {
                    "id": "logs-a",
                    "label": "logs-a",
                    "kind": "index",
                    "selection": {"index": "logs-a"},
                }
            ],
            "Found 1 browsable Elasticsearch indices",
        )

    monkeypatch.setattr(browse, "_browse_elasticsearch", _fake_browse_elasticsearch)

    first_items, first_message = await browse.browse_connector_real(
        "elasticsearch",
        {"url": "https://elastic.example.com:443", "api_key": "secret", "limit": 20},
    )
    second_items, second_message = await browse.browse_connector_real(
        "elasticsearch",
        {"url": "https://elastic.example.com:443", "api_key": "secret", "limit": 20},
    )

    assert calls == 1
    assert first_message == second_message == "Found 1 browsable Elasticsearch indices"
    assert first_items == second_items
    assert first_items is not second_items
    browse._clear_browse_result_cache()


@pytest.mark.anyio
async def test_browse_connector_real_cache_expires_quickly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    current_time = [100.0]
    browse._clear_browse_result_cache()

    async def _fake_browse_redis_detailed(
        _config: dict[str, object],
    ) -> tuple[list[dict[str, object]], dict[str, object]]:
        nonlocal calls
        calls += 1
        return (
            [
                {
                    "id": "orders:1",
                    "label": "orders:1",
                    "kind": "key",
                    "selection": {"keys": ["orders:1"]},
                }
            ],
            {
                "keyspace_total_count": 10,
                "scan_exhausted": False,
                "scan_cap": 50,
                "pattern": "*",
                "returned_count": 1,
            },
        )

    monkeypatch.setattr(browse, "_browse_redis_detailed", _fake_browse_redis_detailed)
    monkeypatch.setattr(browse.time, "monotonic", lambda: current_time[0])

    await browse.browse_connector_real(
        "redis",
        {"url": "redis://default:pass@redis.example.com:6379/0", "limit": 20},
    )
    current_time[0] = 104.0
    await browse.browse_connector_real(
        "redis",
        {"url": "redis://default:pass@redis.example.com:6379/0", "limit": 20},
    )
    current_time[0] = 106.0
    await browse.browse_connector_real(
        "redis",
        {"url": "redis://default:pass@redis.example.com:6379/0", "limit": 20},
    )

    assert calls == 2
    browse._clear_browse_result_cache()
