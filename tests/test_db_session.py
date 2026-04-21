from __future__ import annotations

from sqlalchemy.pool import NullPool

from apps.api_server.db import session


def test_async_engine_kwargs_uses_null_pool_under_pytest(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PYTEST_RUNNING", "1")

    kwargs = session._async_engine_kwargs(
        url="postgresql+asyncpg://postgres:postgres@localhost:5432/test_db",
        echo=True,
        pool_size=10,
        max_overflow=20,
    )

    assert kwargs["poolclass"] is NullPool
    assert "pool_size" not in kwargs
    assert kwargs["connect_args"]["prepared_statement_cache_size"] == 0


def test_async_engine_kwargs_keeps_queue_pool_settings_outside_pytest(
    monkeypatch,
) -> None:
    monkeypatch.delenv("PYTEST_RUNNING", raising=False)

    kwargs = session._async_engine_kwargs(
        url="postgresql+asyncpg://postgres:postgres@localhost:5432/test_db",
        echo=False,
        pool_size=8,
        max_overflow=16,
    )

    assert "poolclass" not in kwargs
    assert kwargs["pool_size"] == 8
    assert kwargs["max_overflow"] == 16
    assert kwargs["pool_recycle"] == 3600
