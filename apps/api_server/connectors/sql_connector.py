"""SQL database connector (Postgres, MySQL, SQLite, Snowflake, ClickHouse)."""

from __future__ import annotations

import asyncio
from queue import Empty, Full, LifoQueue
from threading import Lock
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from apps.api_server.services.columnar_loader import records_to_arrow_table
from apps.api_server.services.connector_egress import (
    connector_audit_context,
    enforce_sql_connection_egress,
)

from .base import BaseConnector, ConnectorRegistry


@ConnectorRegistry.register
class SQLConnector(BaseConnector):
    """Fetch data from SQL databases via SQLAlchemy.

    Config keys:
        connection_string:  SQLAlchemy-compatible DSN (required).
        query:              SQL SELECT statement (required).
        limit:              Optional max rows to return.
    """

    connector_type: str = "sql"
    _SYNC_FETCH_TABLE_CHUNK_SIZE = 100_000
    _CLICKHOUSE_POOL_MAXSIZE = 4
    _CLICKHOUSE_CLIENT_POOLS: dict[str, LifoQueue[Any]] = {}
    _CLICKHOUSE_POOL_LOCK = Lock()

    @staticmethod
    def _optional_limit(raw_value: object) -> int | None:
        if raw_value in (None, ""):
            return None
        if isinstance(raw_value, bool):
            return int(raw_value)
        if isinstance(raw_value, int):
            return raw_value
        if isinstance(raw_value, float):
            return int(raw_value)
        if isinstance(raw_value, str):
            try:
                return int(raw_value)
            except ValueError as exc:
                raise ValueError("SQL connector limit must be an integer.") from exc
        raise ValueError("SQL connector limit must be an integer.")

    async def fetch_data(self) -> list[dict[str, Any]]:
        connection_string: str = self.config.get("connection_string", "")
        query: str = self.config.get("query", "")
        limit = self._optional_limit(self.config.get("limit"))

        if not connection_string or not query:
            raise ValueError("connection_string and query are required")

        from sqlalchemy import text

        audit_context = connector_audit_context(self.config)
        query_body, wrapped_query = self._build_wrapped_query(query=query, limit=limit)

        if self._is_clickhouse_dsn(connection_string):
            return await asyncio.to_thread(
                self._fetch_clickhouse_sync,
                connection_string,
                query_body,
                limit,
                audit_context,
            )

        if self._is_snowflake_dsn(connection_string):
            return await asyncio.to_thread(
                self._fetch_snowflake_sync,
                connection_string,
                query_body,
                limit,
                audit_context,
            )

        if self._is_async_dsn(connection_string):
            from sqlalchemy.ext.asyncio import create_async_engine

            enforce_sql_connection_egress(
                connection_string,
                surface="sql_connector_fetch",
                audit_context=audit_context,
            )
            engine = create_async_engine(connection_string, pool_size=1)
            try:
                async with engine.connect() as conn:
                    params = {"_algenta_limit": limit} if limit is not None else {}
                    result = await conn.stream(text(wrapped_query), params)
                    rows: list[dict[str, Any]] = []
                    async for row in result.mappings():
                        rows.append(dict(row))
                    return rows
            finally:
                await engine.dispose()

        from sqlalchemy import create_engine

        def _fetch_sync() -> list[dict[str, Any]]:
            enforce_sql_connection_egress(
                connection_string,
                surface="sql_connector_fetch",
                audit_context=audit_context,
            )
            engine = create_engine(connection_string, pool_pre_ping=True)
            try:
                with engine.connect() as conn:
                    params = {"_algenta_limit": limit} if limit is not None else {}
                    result = conn.execute(text(wrapped_query), params)
                    return [dict(row._mapping) for row in result]
            finally:
                engine.dispose()

        return await asyncio.to_thread(_fetch_sync)

    async def fetch_table(self) -> Any | None:
        connection_string: str = self.config.get("connection_string", "")
        query: str = self.config.get("query", "")
        limit = self._optional_limit(self.config.get("limit"))

        if not connection_string or not query:
            raise ValueError("connection_string and query are required")

        audit_context = connector_audit_context(self.config)
        if (
            self._is_clickhouse_dsn(connection_string)
            or self._is_snowflake_dsn(connection_string)
            or self._is_async_dsn(connection_string)
        ):
            records = await self.fetch_data()
            if not records:
                return None
            return records_to_arrow_table(records)

        _, wrapped_query = self._build_wrapped_query(query=query, limit=limit)
        return await asyncio.to_thread(
            self._fetch_table_sync,
            connection_string,
            wrapped_query,
            limit,
            audit_context,
        )

    @classmethod
    def _build_wrapped_query(cls, *, query: str, limit: int | None) -> tuple[str, str]:
        query_body = query.strip().rstrip(";")
        wrapped_query = query_body
        if limit is not None:
            wrapped_query = f"SELECT * FROM ({query_body}) AS algenta_source LIMIT :_algenta_limit"  # noqa: S608 - query text is the explicit connector contract input
        return query_body, wrapped_query

    @classmethod
    def _fetch_table_sync(
        cls,
        connection_string: str,
        wrapped_query: str,
        limit: int | None,
        audit_context: object | None = None,
    ) -> Any | None:
        import pandas as pd
        import pyarrow as pa
        from sqlalchemy import create_engine, text

        enforce_sql_connection_egress(
            connection_string,
            surface="sql_connector_fetch_table",
            audit_context=audit_context,
        )
        engine = create_engine(connection_string, pool_pre_ping=True)
        try:
            with engine.connect() as conn:
                params = {"_algenta_limit": limit} if limit is not None else None
                chunks = pd.read_sql_query(
                    text(wrapped_query),
                    conn,
                    params=params,
                    chunksize=cls._SYNC_FETCH_TABLE_CHUNK_SIZE,
                )
                tables: list[Any] = []
                for chunk in chunks:
                    if chunk.empty:
                        continue
                    tables.append(pa.Table.from_pandas(chunk, preserve_index=False))
                if not tables:
                    return None
                return cls._concat_chunk_tables(tables)
        finally:
            engine.dispose()

    @staticmethod
    def _concat_chunk_tables(tables: list[Any]) -> Any:
        import pyarrow as pa

        if len(tables) == 1:
            return tables[0]
        return pa.concat_tables(tables, promote_options="permissive")

    async def validate_connection(self) -> tuple[bool, str]:
        """Run ``SELECT 1`` to verify the database is reachable."""
        try:
            connection_string = self.config.get("connection_string", "")
            audit_context = connector_audit_context(self.config)
            if self._is_clickhouse_dsn(connection_string):
                await asyncio.to_thread(
                    self._validate_clickhouse_sync,
                    connection_string,
                    audit_context,
                )
                return True, "Connected successfully."
            if self._is_snowflake_dsn(connection_string):
                await asyncio.to_thread(
                    self._validate_snowflake_sync,
                    connection_string,
                    audit_context,
                )
                return True, "Connected successfully."
            if self._is_async_dsn(self.config.get("connection_string", "")):
                from sqlalchemy import text
                from sqlalchemy.ext.asyncio import create_async_engine

                enforce_sql_connection_egress(
                    connection_string,
                    surface="sql_connector_validate",
                    audit_context=audit_context,
                )
                engine = create_async_engine(self.config.get("connection_string", ""), pool_size=1)
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                await engine.dispose()
                return True, "Connected successfully."

            from sqlalchemy import create_engine, text

            def _validate_sync() -> None:
                enforce_sql_connection_egress(
                    connection_string,
                    surface="sql_connector_validate",
                    audit_context=audit_context,
                )
                engine = create_engine(
                    self.config.get("connection_string", ""),
                    pool_pre_ping=True,
                )
                try:
                    with engine.connect() as conn:
                        conn.execute(text("SELECT 1"))
                finally:
                    engine.dispose()

            await asyncio.to_thread(_validate_sync)
            return True, "Connected successfully."
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    @staticmethod
    def _fetch_clickhouse_sync(
        connection_string: str,
        query_body: str,
        limit: int | None,
        audit_context: object | None = None,
    ) -> list[dict[str, Any]]:
        enforce_sql_connection_egress(
            connection_string,
            surface="sql_connector_clickhouse_fetch",
            audit_context=audit_context,
        )
        wrapped_query = query_body
        if limit is not None:
            wrapped_query = f"SELECT * FROM ({query_body}) AS algenta_source LIMIT {int(limit)}"  # noqa: S608 - query text is the explicit connector contract input
        client = SQLConnector._acquire_clickhouse_client(connection_string)
        discard_client = False
        try:
            result = client.query(wrapped_query)
            column_names = tuple(str(name) for name in getattr(result, "column_names", ()) or ())
            if column_names:
                return [dict(zip(column_names, row, strict=False)) for row in result.result_rows]
            return [dict(row) for row in result.named_results()]
        except Exception:
            discard_client = True
            raise
        finally:
            SQLConnector._release_clickhouse_client(
                connection_string,
                client,
                discard=discard_client,
            )

    @staticmethod
    def _validate_clickhouse_sync(
        connection_string: str,
        audit_context: object | None = None,
    ) -> None:
        enforce_sql_connection_egress(
            connection_string,
            surface="sql_connector_clickhouse_validate",
            audit_context=audit_context,
        )
        client = SQLConnector._acquire_clickhouse_client(connection_string)
        discard_client = False
        try:
            client.command("SELECT 1")
        except Exception:
            discard_client = True
            raise
        finally:
            SQLConnector._release_clickhouse_client(
                connection_string,
                client,
                discard=discard_client,
            )

    @staticmethod
    def _fetch_snowflake_sync(
        connection_string: str,
        query_body: str,
        limit: int | None,
        audit_context: object | None = None,
    ) -> list[dict[str, Any]]:
        enforce_sql_connection_egress(
            connection_string,
            surface="sql_connector_snowflake_fetch",
            audit_context=audit_context,
        )
        wrapped_query = query_body
        if limit is not None:
            wrapped_query = f"SELECT * FROM ({query_body}) AS algenta_source LIMIT {int(limit)}"  # noqa: S608 - query text is the explicit connector contract input
        conn = SQLConnector._snowflake_connect(connection_string)
        try:
            import snowflake.connector

            with conn.cursor(snowflake.connector.DictCursor) as cursor:
                cursor.execute(wrapped_query)
                return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def _validate_snowflake_sync(
        connection_string: str,
        audit_context: object | None = None,
    ) -> None:
        enforce_sql_connection_egress(
            connection_string,
            surface="sql_connector_snowflake_validate",
            audit_context=audit_context,
        )
        conn = SQLConnector._snowflake_connect(connection_string)
        try:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT 1")
            finally:
                cursor.close()
        finally:
            conn.close()

    @staticmethod
    def _snowflake_connect(connection_string: str) -> Any:
        import snowflake.connector

        config = SQLConnector._parse_snowflake_dsn(connection_string)
        conn = snowflake.connector.connect(
            account=config["account"],
            user=config["user"],
            password=config["password"],
            warehouse=config.get("warehouse"),
            database=config.get("database"),
            schema=config.get("schema"),
            login_timeout=8,
        )
        SQLConnector._activate_snowflake_session_context(
            conn,
            warehouse=config.get("warehouse", ""),
            database=config.get("database", ""),
            schema=config.get("schema", ""),
        )
        return conn

    @staticmethod
    def _activate_snowflake_session_context(
        conn: Any,
        *,
        warehouse: str = "",
        database: str = "",
        schema: str = "",
    ) -> None:
        statements: list[str] = []
        if warehouse:
            quoted_warehouse = SQLConnector._quote_snowflake_identifier(warehouse)
            statements.append(f"USE WAREHOUSE {quoted_warehouse}")
        if not statements:
            return
        cursor = conn.cursor()
        try:
            for statement in statements:
                try:
                    cursor.execute(statement)
                except Exception as exc:
                    if warehouse and statement.startswith("USE WAREHOUSE "):
                        current_role = SQLConnector._snowflake_current_role(conn) or "unknown"
                        raise RuntimeError(
                            "Snowflake warehouse "
                            f"'{warehouse}' is not accessible for current role "
                            f"'{current_role}'. Grant warehouse usage to that role "
                            "or use a login permitted for a role with "
                            "warehouse access."
                        ) from exc
                    raise
        finally:
            cursor.close()

    @staticmethod
    def _quote_snowflake_identifier(identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'

    @staticmethod
    def _snowflake_current_role(conn: Any) -> str:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT CURRENT_ROLE()")
            row = cursor.fetchone()
        except Exception:
            return ""
        finally:
            cursor.close()
        if not row:
            return ""
        if isinstance(row, dict):
            for value in row.values():
                if isinstance(value, str):
                    return value
            return ""
        if isinstance(row, (list, tuple)) and row:
            first = row[0]
            return first if isinstance(first, str) else ""
        return ""

    @staticmethod
    def _parse_snowflake_dsn(connection_string: str) -> dict[str, str]:
        parsed = urlparse(connection_string)
        if parsed.scheme != "snowflake":
            raise ValueError(f"Unsupported Snowflake connection string: {connection_string}")
        if not parsed.username or not parsed.password or not parsed.hostname:
            raise ValueError("Snowflake connection string requires account, user, and password")
        path_parts = [part for part in parsed.path.split("/") if part]
        database = path_parts[0] if len(path_parts) >= 1 else ""
        schema = path_parts[1] if len(path_parts) >= 2 else ""
        params = parse_qs(parsed.query or "", keep_blank_values=False)
        warehouse = params.get("warehouse", [""])[0]
        return {
            "account": parsed.hostname,
            "user": unquote(parsed.username),
            "password": unquote(parsed.password),
            "warehouse": unquote(warehouse),
            "database": unquote(database),
            "schema": unquote(schema),
        }

    @staticmethod
    def _clickhouse_connect(connection_string: str) -> Any:
        from clickhouse_connect import get_client

        config = SQLConnector._parse_clickhouse_dsn(connection_string)
        return get_client(
            host=config["host"],
            port=int(config["port"]),
            username=config["user"],
            password=config["password"],
            database=config["database"],
            secure=bool(config["secure"]),
            connect_timeout=8,
        )

    @classmethod
    def _acquire_clickhouse_client(cls, connection_string: str) -> Any:
        pool = cls._clickhouse_client_pool(connection_string)
        try:
            return pool.get_nowait()
        except Empty:
            return cls._clickhouse_connect(connection_string)

    @classmethod
    def _release_clickhouse_client(
        cls,
        connection_string: str,
        client: Any,
        *,
        discard: bool,
    ) -> None:
        if discard:
            cls._close_clickhouse_client(client)
            return
        pool = cls._clickhouse_client_pool(connection_string)
        try:
            pool.put_nowait(client)
        except Full:
            cls._close_clickhouse_client(client)

    @classmethod
    def _clickhouse_client_pool(cls, connection_string: str) -> LifoQueue[Any]:
        with cls._CLICKHOUSE_POOL_LOCK:
            pool = cls._CLICKHOUSE_CLIENT_POOLS.get(connection_string)
            if pool is None:
                pool = LifoQueue(maxsize=cls._CLICKHOUSE_POOL_MAXSIZE)
                cls._CLICKHOUSE_CLIENT_POOLS[connection_string] = pool
            return pool

    @staticmethod
    def _close_clickhouse_client(client: Any) -> None:
        try:
            client.close()
        except Exception:
            return

    @classmethod
    def _clear_clickhouse_client_pools(cls) -> None:
        with cls._CLICKHOUSE_POOL_LOCK:
            pools = list(cls._CLICKHOUSE_CLIENT_POOLS.values())
            cls._CLICKHOUSE_CLIENT_POOLS = {}
        for pool in pools:
            while True:
                try:
                    client = pool.get_nowait()
                except Empty:
                    break
                cls._close_clickhouse_client(client)

    @staticmethod
    def _parse_clickhouse_dsn(connection_string: str) -> dict[str, Any]:
        parsed = urlparse(connection_string)
        if parsed.scheme not in {"clickhouse", "clickhouses", "http", "https"}:
            raise ValueError(f"Unsupported ClickHouse connection string: {connection_string}")
        if not parsed.hostname:
            raise ValueError("ClickHouse connection string requires host")
        params = parse_qs(parsed.query or "", keep_blank_values=False)
        secure_raw = params.get("secure", [""])[0].strip().lower()
        secure = parsed.scheme in {"clickhouses", "https"} or secure_raw in {
            "1",
            "true",
            "yes",
            "on",
        }
        path_parts = [part for part in parsed.path.split("/") if part]
        database = unquote(path_parts[0]) if path_parts else "default"
        port = parsed.port or (8443 if secure else 8123)
        return {
            "host": parsed.hostname,
            "port": int(port),
            "user": unquote(parsed.username or "default"),
            "password": unquote(parsed.password or ""),
            "database": database,
            "secure": secure,
        }

    @staticmethod
    def _is_async_dsn(connection_string: str) -> bool:
        async_markers = (
            "+asyncpg",
            "+aiosqlite",
            "+asyncmy",
            "+aiomysql",
            "+aioodbc",
        )
        return any(marker in connection_string for marker in async_markers)

    @staticmethod
    def _is_clickhouse_dsn(connection_string: str) -> bool:
        return connection_string.startswith(
            ("clickhouse://", "clickhouses://", "http://", "https://")
        )

    @staticmethod
    def _is_snowflake_dsn(connection_string: str) -> bool:
        return connection_string.startswith("snowflake://")
