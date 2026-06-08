from __future__ import annotations

import asyncio
import time
from typing import Any

from apps.api_server.services.connector_egress import (
    connector_audit_context,
    connector_host_destination,
    enforce_connector_destination,
    snowflake_account_destination,
)

from .tester_common import (
    ConnectorTestOutcome,
    elapsed_ms,
    failure_outcome,
    success_outcome,
)


async def test_postgres_connector(config: dict[str, Any]) -> ConnectorTestOutcome:
    try:
        import asyncpg
    except ImportError:
        return failure_outcome(
            message="PostgreSQL connector requires asyncpg — run: pip install asyncpg",
            latency_ms=0,
            error_type="invalid_config",
            recoverable=True,
        )

    host = config.get("host", "localhost")
    port = int(config.get("port", 5432))
    database = config.get("database", "postgres")
    user = config.get("user", "postgres")
    password = config.get("password", "")
    ssl_mode = config.get("ssl_mode", "prefer")

    started_at = time.perf_counter()
    try:
        enforce_connector_destination(
            connector_host_destination(str(host), port=port),
            surface="tester_postgres_connector",
            audit_context=connector_audit_context(config),
        )
        ssl = ssl_mode if ssl_mode in ("require", "verify-full") else None
        conn = await asyncpg.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            ssl=ssl,
            timeout=8,
        )
        await conn.fetchval("SELECT 1")
        await conn.close()
        return success_outcome(
            f"PostgreSQL connection successful ({host}:{port}/{database})",
            elapsed_ms(started_at),
        )
    except Exception as exc:
        return failure_outcome(
            message=f"PostgreSQL connection failed: {exc}",
            latency_ms=elapsed_ms(started_at),
            exception=exc,
        )


async def test_sqlite_connector(config: dict[str, Any]) -> ConnectorTestOutcome:
    import sqlite3

    connection_string = str(config.get("connection_string", "") or "")
    path = str(config.get("path", "") or "")
    if connection_string.startswith("sqlite:///"):
        path = connection_string.removeprefix("sqlite:///")
    elif connection_string.startswith("sqlite+pysqlite:///"):
        path = connection_string.removeprefix("sqlite+pysqlite:///")
    elif connection_string == "sqlite:///:memory:":
        path = ":memory:"

    if not path:
        return failure_outcome(
            message="SQLite connector requires path or connection_string",
            latency_ms=0,
            error_type="invalid_config",
            recoverable=True,
        )

    started_at = time.perf_counter()
    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        conn.close()
        return success_outcome(
            f"SQLite connection successful ({path})",
            elapsed_ms(started_at),
        )
    except Exception as exc:
        return failure_outcome(
            message=f"SQLite connection failed: {exc}",
            latency_ms=elapsed_ms(started_at),
            exception=exc,
        )


async def test_clickhouse_connector(config: dict[str, Any]) -> ConnectorTestOutcome:
    from apps.api_server.connectors.sql_connector import SQLConnector
    from apps.api_server.services.data_connection_browse import _build_database_connection_string

    try:
        import clickhouse_connect  # noqa: F401
    except ImportError:
        return failure_outcome(
            message=(
                "ClickHouse connector requires clickhouse-connect — "
                "run: pip install clickhouse-connect"
            ),
            latency_ms=0,
            error_type="invalid_config",
            recoverable=True,
        )

    started_at = time.perf_counter()
    try:
        connection_string = _build_database_connection_string("clickhouse", config)
        await asyncio.to_thread(
            SQLConnector._validate_clickhouse_sync,
            connection_string,
            connector_audit_context(config),
        )
        parsed = SQLConnector._parse_clickhouse_dsn(connection_string)
        return success_outcome(
            (
                "ClickHouse connection successful "
                f"({parsed['host']}:{parsed['port']}/{parsed['database']})"
            ),
            elapsed_ms(started_at),
        )
    except Exception as exc:
        return failure_outcome(
            message=f"ClickHouse error: {exc}",
            latency_ms=elapsed_ms(started_at),
            exception=exc,
        )


async def test_elasticsearch_connector(config: dict[str, Any]) -> ConnectorTestOutcome:
    from apps.api_server.connectors.elasticsearch_connector import ElasticsearchConnector

    started_at = time.perf_counter()
    try:
        settings = ElasticsearchConnector._connection_settings(config)
        await asyncio.to_thread(
            ElasticsearchConnector._validate_sync,
            settings,
            connector_audit_context(config),
        )
        return success_outcome(
            (f"Elasticsearch connection successful ({settings['host']}:{settings['port']})"),
            elapsed_ms(started_at),
        )
    except Exception as exc:
        return failure_outcome(
            message=f"Elasticsearch error: {exc}",
            latency_ms=elapsed_ms(started_at),
            exception=exc,
        )


async def test_redis_connector(config: dict[str, Any]) -> ConnectorTestOutcome:
    from apps.api_server.connectors.redis_connector import RedisConnector

    try:
        import redis  # noqa: F401
    except ImportError:
        return failure_outcome(
            message="Redis connector requires redis — run: pip install redis",
            latency_ms=0,
            error_type="invalid_config",
            recoverable=True,
        )

    started_at = time.perf_counter()
    try:
        connection_url = RedisConnector._connection_url(config)
        await asyncio.to_thread(
            RedisConnector._validate_sync,
            connection_url,
            connector_audit_context(config),
        )
        parsed = RedisConnector._parse_connection_url(connection_url)
        return success_outcome(
            f"Redis connection successful ({parsed['host']}:{parsed['port']}/{parsed['database']})",
            elapsed_ms(started_at),
        )
    except Exception as exc:
        return failure_outcome(
            message=f"Redis error: {exc}",
            latency_ms=elapsed_ms(started_at),
            exception=exc,
        )


async def test_neo4j_connector(config: dict[str, Any]) -> ConnectorTestOutcome:
    from apps.api_server.connectors.neo4j_connector import Neo4jConnector

    try:
        import neo4j  # noqa: F401
    except ImportError:
        return failure_outcome(
            message="Neo4j connector requires neo4j — run: pip install neo4j",
            latency_ms=0,
            error_type="invalid_config",
            recoverable=True,
        )

    started_at = time.perf_counter()
    try:
        settings = Neo4jConnector._connection_settings(config)
        await asyncio.to_thread(
            Neo4jConnector._validate_sync,
            settings,
            connector_audit_context(config),
        )
        location = settings["host"]
        if settings["port"]:
            location = f"{location}:{settings['port']}"
        database = settings["database"] or "<default>"
        return success_outcome(
            f"Neo4j connection successful ({location}/{database})",
            elapsed_ms(started_at),
        )
    except Exception as exc:
        return failure_outcome(
            message=f"Neo4j error: {exc}",
            latency_ms=elapsed_ms(started_at),
            exception=exc,
        )


async def test_snowflake_connector(config: dict[str, Any]) -> ConnectorTestOutcome:
    from apps.api_server.connectors.sql_connector import SQLConnector

    try:
        import snowflake.connector
    except ImportError:
        return failure_outcome(
            message=(
                "Snowflake connector requires snowflake-connector-python — "
                "run: pip install snowflake-connector-python"
            ),
            latency_ms=0,
            error_type="invalid_config",
            recoverable=True,
        )

    started_at = time.perf_counter()
    try:
        enforce_connector_destination(
            snowflake_account_destination(str(config.get("account", "") or "")),
            surface="tester_snowflake_connector",
            audit_context=connector_audit_context(config),
        )
        conn = snowflake.connector.connect(
            account=config.get("account", ""),
            user=config.get("user", ""),
            password=config.get("password", ""),
            warehouse=config.get("warehouse"),
            database=config.get("database"),
            schema=config.get("schema"),
            login_timeout=8,
        )
        SQLConnector._activate_snowflake_session_context(
            conn,
            warehouse=str(config.get("warehouse", "") or ""),
            database=str(config.get("database", "") or ""),
            schema=str(config.get("schema", "") or ""),
        )
        conn.cursor().execute("SELECT CURRENT_VERSION()")
        conn.close()
        return success_outcome(
            f"Snowflake connection successful ({config.get('account')})",
            elapsed_ms(started_at),
        )
    except Exception as exc:
        return failure_outcome(
            message=f"Snowflake error: {exc}",
            latency_ms=elapsed_ms(started_at),
            exception=exc,
        )
