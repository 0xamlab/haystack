"""SQL-specific browse helpers and connection-string normalization."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from threading import Lock
from typing import Any
from urllib.parse import quote, unquote, urlparse

from fastapi import HTTPException

from apps.api_server.services.connector_egress import (
    connector_audit_context,
    enforce_sql_connection_egress,
)

_DATABASE_TYPES = {
    "postgres",
    "postgresql",
    "mysql",
    "mssql",
    "oracle",
    "redshift",
    "clickhouse",
    "snowflake",
    "bigquery",
    "sqlite",
    "elasticsearch",
    "neo4j",
    "redis",
}
_SYNC_BROWSE_ENGINES: dict[str, Any] = {}
_SYNC_BROWSE_ENGINES_LOCK = Lock()

__all__ = [
    "_DATABASE_TYPES",
    "_build_database_connection_string",
    "_browse_postgres_compatible_sql",
    "_browse_sql",
    "_clear_sync_browse_engine_cache",
    "_sql_source_selection_query",
    "_sql_source_selection_query_for_provider",
    "strip_none",
    "truthy",
]


def _safe_optional_int(raw_value: Any) -> int | None:
    if raw_value in (None, ""):
        return None
    try:
        if isinstance(raw_value, str):
            normalized = raw_value.strip().replace(",", "")
            if not normalized:
                return None
            return int(float(normalized))
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def strip_none(mapping: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if value is not None}


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, int | float):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _sync_browse_engine(connection_string: str) -> Any:
    from sqlalchemy import create_engine

    with _SYNC_BROWSE_ENGINES_LOCK:
        engine = _SYNC_BROWSE_ENGINES.get(connection_string)
        if engine is None:
            engine = create_engine(connection_string, pool_pre_ping=True)
            _SYNC_BROWSE_ENGINES[connection_string] = engine
        return engine


def _discard_sync_browse_engine(connection_string: str, engine: Any) -> None:
    with _SYNC_BROWSE_ENGINES_LOCK:
        cached = _SYNC_BROWSE_ENGINES.get(connection_string)
        if cached is engine:
            _SYNC_BROWSE_ENGINES.pop(connection_string, None)
    _dispose_sync_browse_engine(engine)


def _dispose_sync_browse_engine(engine: Any) -> None:
    with suppress(Exception):
        engine.dispose()


def _clear_sync_browse_engine_cache() -> None:
    with _SYNC_BROWSE_ENGINES_LOCK:
        engines = list(_SYNC_BROWSE_ENGINES.values())
        _SYNC_BROWSE_ENGINES.clear()
    for engine in engines:
        _dispose_sync_browse_engine(engine)


def _build_database_connection_string(provider: str, config: dict[str, Any]) -> str:
    if config.get("connection_string"):
        raw_connection_string = str(config["connection_string"])
        if provider != "clickhouse":
            return raw_connection_string
        if raw_connection_string.startswith(("clickhouse://", "clickhouses://")):
            return raw_connection_string
        config = {
            **config,
            "url": raw_connection_string,
        }

    host = str(config.get("host", "localhost"))
    port = config.get("port")
    database = str(config.get("database", ""))
    user = str(config.get("user", config.get("username", "")))
    password = str(config.get("password", ""))

    if provider in {"postgres", "redshift"}:
        port_value = int(port or 5432)
        return f"postgresql://{user}:{password}@{host}:{port_value}/{database}"
    if provider == "clickhouse":
        raw_url = str(config.get("url", "") or "").strip()
        parsed_url = urlparse(raw_url) if raw_url else None
        host_value = (
            parsed_url.hostname
            if parsed_url is not None and parsed_url.hostname
            else str(config.get("host", "")).strip()
        )
        if not host_value:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "missing_connection_string",
                        "message": (
                            "clickhouse connections require connection_string or url/host."
                        ),
                    }
                },
            )
        secure = truthy(config.get("secure")) or (
            parsed_url is not None and parsed_url.scheme == "https"
        )
        default_port = 8443 if secure else 8123
        port_value = int(port or (parsed_url.port if parsed_url is not None else 0) or default_port)
        database_value = str(
            config.get("database")
            or (parsed_url.path.lstrip("/") if parsed_url is not None else "")
            or "default"
        ).strip()
        if not database_value:
            database_value = "default"
        user_value = user or (
            unquote(parsed_url.username)
            if parsed_url is not None and parsed_url.username is not None
            else ""
        )
        password_value = password or (
            unquote(parsed_url.password)
            if parsed_url is not None and parsed_url.password is not None
            else ""
        )
        auth_user = quote(user_value or "default", safe="")
        auth_password = quote(password_value, safe="")
        return (
            f"clickhouse://{auth_user}:{auth_password}@{host_value}:{port_value}/"
            f"{quote(database_value, safe='')}?secure={'true' if secure else 'false'}"
        )
    if provider == "mysql":
        port_value = int(port or 3306)
        return f"mysql+pymysql://{user}:{password}@{host}:{port_value}/{database}"
    if provider == "mssql":
        port_value = int(port or 1433)
        driver = str(config.get("driver", "ODBC Driver 18 for SQL Server"))
        return (
            f"mssql+pyodbc://{user}:{password}@{host}:{port_value}/{database}"
            f"?driver={driver.replace(' ', '+')}"
        )
    if provider == "oracle":
        service_name = str(config.get("service_name") or database).strip()
        if not (host and user and password and service_name):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "missing_connection_string",
                        "message": (
                            "oracle connections require connection_string or "
                            "host/user/password/service_name."
                        ),
                    }
                },
            )
        port_value = int(port or (1522 if config.get("wallet_location") else 1521))
        return (
            f"oracle+oracledb://{quote(user, safe='')}:{quote(password, safe='')}@"
            f"{host}:{port_value}/?service_name={quote(service_name, safe='')}"
        )
    if provider == "sqlite":
        path = str(config.get("path", ""))
        if not path:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "missing_connection_string",
                        "message": "sqlite connections require path or connection_string.",
                    }
                },
            )
        if path == ":memory:":
            return "sqlite:///:memory:"
        return f"sqlite:///{path}"
    if provider == "snowflake":
        account = str(config.get("account", ""))
        warehouse = str(config.get("warehouse", ""))
        schema = str(config.get("schema", ""))
        if not (account and user and password and database):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "missing_connection_string",
                        "message": (
                            "snowflake connections require connection_string or "
                            "account/user/password/database."
                        ),
                    }
                },
            )
        suffix = f"/{database}"
        if schema:
            suffix += f"/{schema}"
        query = f"?warehouse={warehouse}" if warehouse else ""
        return f"snowflake://{user}:{password}@{account}{suffix}{query}"
    if provider == "bigquery":
        project_id = str(config.get("project_id", ""))
        if not project_id:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "missing_connection_string",
                        "message": (
                            "bigquery connections require connection_string or project_id."
                        ),
                    }
                },
            )
        return f"bigquery://{project_id}"
    raise HTTPException(
        status_code=422,
        detail={
            "error": {
                "code": "invalid_connection_provider",
                "message": f"Unsupported database provider '{provider}'.",
            }
        },
    )


def _sql_source_selection_query(table_name: str) -> str:
    return _sql_source_selection_query_for_provider(table_name, provider="postgres")


def _sql_source_selection_query_for_provider(table_name: str, *, provider: str) -> str:
    parts = [part.strip().strip('"').strip("`") for part in table_name.split(".") if part.strip()]
    if not parts:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "invalid_selection",
                    "message": "selection.table cannot be empty.",
                }
            },
        )
    if provider == "clickhouse":
        quoted = ".".join(f"`{part}`" for part in parts)
    else:
        quoted = ".".join(f'"{part}"' for part in parts)
    return f"SELECT * FROM {quoted}"  # noqa: S608 - identifiers are stripped and quoted


async def _browse_sql(
    config: dict[str, Any],
    *,
    provider: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    normalized_provider = (provider or "postgres").strip().lower()
    if normalized_provider == "oracle":
        from apps.api_server.connectors.oracle_connector import OracleConnector

        items = await asyncio.to_thread(OracleConnector._browse_sync, config)
        return items, f"Found {len(items)} browsable database objects"
    connection_string = _build_database_connection_string(
        normalized_provider,
        config,
    )
    enforce_sql_connection_egress(
        connection_string,
        surface="browse_sql_connector",
        audit_context=connector_audit_context(config),
    )
    if normalized_provider == "clickhouse":
        return await _browse_clickhouse(config, connection_string=connection_string)
    if normalized_provider in {"postgres", "postgresql", "redshift"}:
        return await _browse_postgres_compatible_sql(
            config,
            connection_string=connection_string,
        )
    try:
        from sqlalchemy import inspect
        from sqlalchemy.ext.asyncio import create_async_engine
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"SQL browsing requires SQLAlchemy: {exc}") from exc

    system_schemas = {"information_schema", "pg_catalog", "pg_toast", "sys", "sqlite_master"}
    requested_schema = str(config.get("schema", "") or "").strip()

    def _collect(sync_conn: Any) -> list[dict[str, Any]]:
        inspector = inspect(sync_conn)
        items: list[dict[str, Any]] = []
        if requested_schema:
            schema_names = [requested_schema]
        else:
            schema_names = inspector.get_schema_names()
        max_items = None if requested_schema else 200
        for schema in schema_names:
            if schema in system_schemas:
                continue
            for table_name in inspector.get_table_names(schema=schema):
                label = f"{schema}.{table_name}" if schema and schema != "main" else table_name
                items.append(
                    {
                        "id": label,
                        "label": label,
                        "kind": "table",
                        "selection": {"table": label},
                        "schema": schema,
                        "name": table_name,
                    }
                )
                if max_items is not None and len(items) >= max_items:
                    return items
            for view_name in inspector.get_view_names(schema=schema):
                label = f"{schema}.{view_name}" if schema and schema != "main" else view_name
                items.append(
                    {
                        "id": label,
                        "label": label,
                        "kind": "view",
                        "selection": {"table": label},
                        "schema": schema,
                        "name": view_name,
                    }
                )
                if max_items is not None and len(items) >= max_items:
                    return items
        return items

    if any(
        marker in connection_string
        for marker in ("+asyncpg", "+aiosqlite", "+asyncmy", "+aiomysql", "+aioodbc")
    ):
        engine = create_async_engine(connection_string, pool_pre_ping=True)
        try:
            async with engine.connect() as conn:
                items = await conn.run_sync(_collect)
        finally:
            await engine.dispose()
    else:

        def _sync_browse() -> list[dict[str, Any]]:
            engine = _sync_browse_engine(connection_string)
            try:
                with engine.connect() as conn:
                    return _collect(conn)
            except Exception:
                _discard_sync_browse_engine(connection_string, engine)
                raise

        items = await asyncio.to_thread(_sync_browse)

    return items, f"Found {len(items)} browsable database objects"


def _postgres_catalog_query(*, scoped_schema: bool) -> str:
    query = """
        SELECT
            n.nspname AS schema_name,
            c.relname AS object_name,
            CASE
                WHEN c.relkind IN ('v', 'm') THEN 'view'
                ELSE 'table'
            END AS object_kind,
            CASE
                WHEN c.relkind = 'v' THEN NULL
                WHEN s.n_live_tup IS NOT NULL AND s.n_live_tup >= 0 THEN s.n_live_tup::bigint
                WHEN c.reltuples >= 0 THEN c.reltuples::bigint
                ELSE NULL
            END AS row_count
        FROM pg_class c
        INNER JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_stat_all_tables s ON s.relid = c.oid
        WHERE c.relkind IN ('r', 'p', 'v', 'm', 'f')
          AND n.nspname NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
    """
    if scoped_schema:
        query += "\n  AND n.nspname = :schema_name"
    query += "\nORDER BY n.nspname, c.relname"
    if not scoped_schema:
        query += "\nLIMIT 200"
    return query


def _browse_postgres_rows_to_items(
    rows: list[tuple[str, str, str, int | None]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for schema_name, object_name, object_kind, row_count in rows:
        label = (
            f"{schema_name}.{object_name}" if schema_name and schema_name != "main" else object_name
        )
        item: dict[str, Any] = {
            "id": label,
            "label": label,
            "kind": str(object_kind),
            "selection": {"table": label},
            "schema": schema_name,
            "name": object_name,
        }
        normalized_row_count = _safe_optional_int(row_count)
        if normalized_row_count is not None:
            item["row_count"] = normalized_row_count
        items.append(item)
    return items


async def _browse_postgres_compatible_sql(
    config: dict[str, Any],
    *,
    connection_string: str,
) -> tuple[list[dict[str, Any]], str]:
    requested_schema = str(config.get("schema", "") or "").strip()
    scoped_schema = bool(requested_schema)
    query = _postgres_catalog_query(scoped_schema=scoped_schema)
    params = {"schema_name": requested_schema} if scoped_schema else {}

    from sqlalchemy import text

    if any(
        marker in connection_string
        for marker in ("+asyncpg", "+aiosqlite", "+asyncmy", "+aiomysql", "+aioodbc")
    ):
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(connection_string, pool_pre_ping=True)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text(query), params)
                rows = [
                    (
                        str(row[0]),
                        str(row[1]),
                        str(row[2]),
                        _safe_optional_int(row[3]),
                    )
                    for row in result.fetchall()
                ]
        finally:
            await engine.dispose()
    else:

        def _sync_browse() -> list[tuple[str, str, str, int | None]]:
            engine = _sync_browse_engine(connection_string)
            try:
                with engine.connect() as conn:
                    result = conn.execute(text(query), params)
                    return [
                        (
                            str(row[0]),
                            str(row[1]),
                            str(row[2]),
                            _safe_optional_int(row[3]),
                        )
                        for row in result.fetchall()
                    ]
            except Exception:
                _discard_sync_browse_engine(connection_string, engine)
                raise

        rows = await asyncio.to_thread(_sync_browse)

    items = _browse_postgres_rows_to_items(rows)
    return items, f"Found {len(items)} browsable database objects"


async def _browse_clickhouse(
    config: dict[str, Any],
    *,
    connection_string: str,
) -> tuple[list[dict[str, Any]], str]:
    from apps.api_server.connectors.sql_connector import SQLConnector

    requested_database = str(config.get("schema", "") or config.get("database", "")).strip()
    has_explicit_scope = bool(requested_database)

    def _sync_browse() -> list[dict[str, Any]]:
        client = SQLConnector._acquire_clickhouse_client(connection_string)
        discard_client = False
        try:
            query = (
                "SELECT database, name, engine, total_rows "
                "FROM system.tables "
                "WHERE database NOT IN ('system', 'information_schema', 'INFORMATION_SCHEMA') "
            )
            parameters: dict[str, Any] = {}
            if requested_database:
                query += "AND database = {database:String} "
                parameters["database"] = requested_database
            query += "ORDER BY database, name"
            if not has_explicit_scope:
                query += " LIMIT 200"
            result = client.query(query, parameters=parameters)
            items: list[dict[str, Any]] = []
            for database_name, table_name, engine, total_rows in result.result_rows:
                label = f"{database_name}.{table_name}"
                item: dict[str, Any] = {
                    "id": label,
                    "label": label,
                    "kind": "view" if "view" in str(engine).lower() else "table",
                    "selection": {"table": label},
                    "schema": database_name,
                    "name": table_name,
                }
                normalized_row_count = _safe_optional_int(total_rows)
                if normalized_row_count is not None:
                    item["row_count"] = normalized_row_count
                items.append(item)
            return items
        except Exception:
            discard_client = True
            raise
        finally:
            SQLConnector._release_clickhouse_client(
                connection_string,
                client,
                discard=discard_client,
            )

    items = await asyncio.to_thread(_sync_browse)
    return items, f"Found {len(items)} browsable database objects"
