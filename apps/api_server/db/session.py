"""
Async SQLAlchemy engine and session factory.

Production setup:
  - Primary engine: read/write to primary PostgreSQL (via PgBouncer port 6432)
  - Read replica engine: SELECT-only queries (via PgBouncer replica port 6433)
  - pool_pre_ping: detects stale connections from PgBouncer
  - pool_size/max_overflow: tuned for 100k org workloads

PgBouncer config (infra/pgbouncer/pgbouncer.ini):
  [databases]
  algenta = host=postgres port=5432 dbname=algenta
  algenta_replica = host=postgres-replica port=5432 dbname=algenta

  [pgbouncer]
  listen_port = 6432
  pool_mode = transaction    # Required for asyncio + asyncpg
  max_client_conn = 10000
  default_pool_size = 25
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from apps.api_server.config import get_settings

settings = get_settings()


def _running_under_pytest() -> bool:
    return os.environ.get("PYTEST_RUNNING") == "1"


def _async_engine_kwargs(
    *,
    url: str,
    echo: bool,
    pool_size: int,
    max_overflow: int,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "echo": echo,
        "pool_pre_ping": True,  # detect stale PgBouncer connections
    }
    if url.startswith("postgresql"):
        kwargs["connect_args"] = {
            "prepared_statement_cache_size": 0,  # required for PgBouncer transaction mode
        }

    if _running_under_pytest():
        # pytest-asyncio creates multiple loops across the full suite; avoid
        # reusing asyncpg connections that were opened on a different loop.
        kwargs["poolclass"] = NullPool
    else:
        kwargs.update(
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=3600,  # recycle connections every hour
        )

    return kwargs


# ─── Primary (read + write) ───────────────────────────────────────────────────

engine = create_async_engine(
    settings.database_url,
    **_async_engine_kwargs(
        url=settings.database_url,
        echo=settings.is_development,
        pool_size=10,
        max_overflow=20,
    ),
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# ─── Read replica (SELECT-only — lower latency for analytics/list endpoints) ──
# Falls back to primary when DATABASE_READ_REPLICA_URL is not set.

_REPLICA_URL = os.environ.get("DATABASE_READ_REPLICA_URL", settings.database_url)

_read_engine = create_async_engine(
    _REPLICA_URL,
    **_async_engine_kwargs(
        url=_REPLICA_URL,
        echo=False,
        pool_size=8,
        max_overflow=16,
    ),
)

AsyncReadSessionLocal = async_sessionmaker(
    bind=_read_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ─── FastAPI dependencies ─────────────────────────────────────────────────────


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Read/write session — use for INSERT, UPDATE, DELETE."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_read_db() -> AsyncGenerator[AsyncSession, None]:
    """Read-only session (replica) — use for SELECT, analytics, list endpoints."""
    async with AsyncReadSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Type aliases for router signatures
AsyncSessionDep = Annotated[AsyncSession, Depends(get_db)]
AsyncReadSessionDep = Annotated[AsyncSession, Depends(get_read_db)]
