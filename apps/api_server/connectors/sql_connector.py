"""SQL database connector (Postgres, MySQL, SQLite)."""
from __future__ import annotations

import asyncio
from typing import Any

from apps.api_server.services.columnar_loader import records_to_arrow_table

from .base import BaseConnector, ConnectorRegistry


@ConnectorRegistry.register
class SQLConnector(BaseConnector):
    """Fetch data from SQL databases via SQLAlchemy.

    Config keys:
        connection_string:  SQLAlchemy-compatible DSN (required).
        query:              SQL SELECT statement (required).
        limit:              Max rows to return (default 10_000).
    """

    connector_type: str = "sql"

    async def fetch_data(self) -> list[dict[str, Any]]:
        connection_string: str = self.config.get("connection_string", "")
        query: str = self.config.get("query", "")
        limit: int = self.config.get("limit", 10_000)

        if not connection_string or not query:
            raise ValueError("connection_string and query are required")

        from sqlalchemy import text

        query_body = query.strip().rstrip(";")
        wrapped_query = (
            f"SELECT * FROM ({query_body}) AS algenta_source LIMIT :_algenta_limit"  # noqa: S608 - query text is the explicit connector contract input
        )

        if self._is_async_dsn(connection_string):
            from sqlalchemy.ext.asyncio import create_async_engine

            engine = create_async_engine(connection_string, pool_size=1)
            try:
                async with engine.connect() as conn:
                    result = await conn.stream(
                        text(wrapped_query),
                        {"_algenta_limit": int(limit)},
                    )
                    rows: list[dict[str, Any]] = []
                    async for row in result.mappings():
                        rows.append(dict(row))
                    return rows
            finally:
                await engine.dispose()

        from sqlalchemy import create_engine

        def _fetch_sync() -> list[dict[str, Any]]:
            engine = create_engine(connection_string, pool_pre_ping=True)
            try:
                with engine.connect() as conn:
                    result = conn.execute(
                        text(wrapped_query),
                        {"_algenta_limit": int(limit)},
                    )
                    return [dict(row._mapping) for row in result]
            finally:
                engine.dispose()

        return await asyncio.to_thread(_fetch_sync)

    async def fetch_table(self) -> Any | None:
        records = await self.fetch_data()
        if not records:
            return None
        return records_to_arrow_table(records)

    async def validate_connection(self) -> tuple[bool, str]:
        """Run ``SELECT 1`` to verify the database is reachable."""
        try:
            if self._is_async_dsn(self.config.get("connection_string", "")):
                from sqlalchemy import text
                from sqlalchemy.ext.asyncio import create_async_engine

                engine = create_async_engine(
                    self.config.get("connection_string", ""), pool_size=1
                )
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                await engine.dispose()
                return True, "Connected successfully."

            from sqlalchemy import create_engine, text

            def _validate_sync() -> None:
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
    def _is_async_dsn(connection_string: str) -> bool:
        async_markers = (
            "+asyncpg",
            "+aiosqlite",
            "+asyncmy",
            "+aiomysql",
            "+aioodbc",
        )
        return any(marker in connection_string for marker in async_markers)
