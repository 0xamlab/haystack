from __future__ import annotations

import pytest

from apps.api_server.config import get_settings
from apps.api_server.connectors.neo4j_connector import Neo4jConnector
from apps.api_server.connectors.redis_connector import RedisConnector
from apps.api_server.connectors.sql_connector import SQLConnector
from apps.api_server.services.connector_egress import (
    neo4j_settings_destination,
    redis_connection_destination,
    snowflake_account_destination,
    sql_connection_destination,
)
from apps.api_server.services.egress_guard import EgressPolicyDeniedError


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("connection_string", "expected"),
    [
        ("postgresql://reader:secret@postgres.internal/analytics", "postgres.internal:5432"),
        ("mysql+pymysql://reader:secret@mysql.internal/orders", "mysql.internal:3306"),
        (
            "oracle+oracledb://reader:secret@oracle.internal:1521/?service_name=analytics",
            "oracle.internal:1521",
        ),
        (
            "clickhouse://default:secret@clickhouse.internal:8443/default?secure=true",
            "clickhouse.internal:8443",
        ),
        (
            "snowflake://reader:secret@acct-xyz/SNOWFLAKE_SAMPLE_DATA",
            "acct-xyz.snowflakecomputing.com:443",
        ),
        ("bigquery://analytics-project", "https://bigquery.googleapis.com"),
        ("sqlite:////tmp/example.db", None),
    ],
)
def test_sql_connection_destination_normalizes_supported_connector_targets(
    connection_string: str,
    expected: str | None,
) -> None:
    assert sql_connection_destination(connection_string) == expected


def test_redis_and_neo4j_destinations_normalize_default_ports() -> None:
    assert redis_connection_destination("rediss://default:secret@redis.internal/2") == (
        "redis.internal:6380"
    )
    settings = Neo4jConnector._connection_settings(
        {
            "uri": "neo4j+s://graph.internal",
            "username": "neo4j",
            "password": "secret",
        }
    )
    assert neo4j_settings_destination(settings) == "graph.internal:7687"
    assert snowflake_account_destination("acct-private") == (
        "acct-private.snowflakecomputing.com:443"
    )


@pytest.mark.anyio
async def test_sql_connector_blocks_unallowlisted_postgres_fetch_in_self_hosted_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def _unexpected_create_engine(*args, **kwargs):
        create_calls.append((args, kwargs))
        raise AssertionError("create_engine should not be called when egress is blocked")

    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_ALLOW_OUTBOUND_NETWORK", "0")
    monkeypatch.delenv("ALGENTA_EGRESS_ALLOWLIST", raising=False)
    monkeypatch.setattr("sqlalchemy.create_engine", _unexpected_create_engine)

    connector = SQLConnector(
        {
            "connection_string": "postgresql://reader:secret@warehouse.customer.example:5432/analytics",
            "query": "SELECT 1",
        }
    )

    with pytest.raises(EgressPolicyDeniedError, match="privacy policy"):
        await connector.fetch_data()

    assert create_calls == []


@pytest.mark.anyio
async def test_sql_connector_allows_allowlisted_postgres_validation_in_self_hosted_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    class _FakeConnection:
        def __enter__(self) -> _FakeConnection:
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def execute(self, _query) -> object:
            return object()

    class _FakeEngine:
        def __init__(self) -> None:
            self.disposed = False

        def connect(self) -> _FakeConnection:
            return _FakeConnection()

        def dispose(self) -> None:
            self.disposed = True

    fake_engine = _FakeEngine()

    def _fake_create_engine(*args, **kwargs):
        create_calls.append((args, kwargs))
        return fake_engine

    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_ALLOW_OUTBOUND_NETWORK", "0")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "warehouse.customer.example:5432")
    monkeypatch.setattr("sqlalchemy.create_engine", _fake_create_engine)

    connector = SQLConnector(
        {
            "connection_string": "postgresql://reader:secret@warehouse.customer.example:5432/analytics",
            "query": "SELECT 1",
        }
    )

    ok, message = await connector.validate_connection()

    assert ok is True
    assert message == "Connected successfully."
    assert len(create_calls) == 1
    assert fake_engine.disposed is True


@pytest.mark.anyio
async def test_redis_connector_blocks_unallowlisted_validation_in_self_hosted_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connect_calls: list[str] = []

    def _unexpected_connect(connection_url: str):
        connect_calls.append(connection_url)
        raise AssertionError("redis connect should not run when egress is blocked")

    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_ALLOW_OUTBOUND_NETWORK", "0")
    monkeypatch.delenv("ALGENTA_EGRESS_ALLOWLIST", raising=False)
    monkeypatch.setattr(
        RedisConnector,
        "_connect_sync",
        staticmethod(_unexpected_connect),
    )

    connector = RedisConnector({"url": "redis://default:secret@redis.customer.example:6379/0"})

    ok, message = await connector.validate_connection()

    assert ok is False
    assert "privacy policy" in message
    assert connect_calls == []


@pytest.mark.anyio
async def test_neo4j_connector_blocks_unallowlisted_validation_in_self_hosted_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connect_calls: list[dict[str, str]] = []

    def _unexpected_connect(settings: dict[str, str]):
        connect_calls.append(dict(settings))
        raise AssertionError("neo4j driver should not initialize when egress is blocked")

    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_ALLOW_OUTBOUND_NETWORK", "0")
    monkeypatch.delenv("ALGENTA_EGRESS_ALLOWLIST", raising=False)
    monkeypatch.setattr(
        Neo4jConnector,
        "_connect_sync",
        staticmethod(_unexpected_connect),
    )

    connector = Neo4jConnector(
        {
            "uri": "neo4j+s://graph.customer.example",
            "username": "neo4j",
            "password": "secret",
        }
    )

    ok, message = await connector.validate_connection()

    assert ok is False
    assert "privacy policy" in message
    assert connect_calls == []
