from __future__ import annotations

from typing import Any

from sqlalchemy.pool import NullPool

from apps.worker.tasks import simulation_task


def test_worker_session_factory_uses_nullpool_and_pid_cache(monkeypatch) -> None:
    simulation_task._WORKER_SESSION_FACTORIES.clear()

    captured: list[dict[str, Any]] = []

    class _Settings:
        database_url = "postgresql+asyncpg://algenta:secret@postgres:5432/algenta"

    def _fake_create_async_engine(url: str, **kwargs: Any) -> object:
        captured.append({"url": url, "kwargs": kwargs})
        return object()

    monkeypatch.setattr(simulation_task, "create_async_engine", _fake_create_async_engine)
    monkeypatch.setattr("apps.api_server.config.get_settings", lambda: _Settings())
    monkeypatch.setattr(simulation_task.os, "getpid", lambda: 1234)

    first = simulation_task._get_worker_session_factory()
    second = simulation_task._get_worker_session_factory()

    assert first is second
    assert len(captured) == 1
    assert captured[0]["url"] == _Settings.database_url
    assert captured[0]["kwargs"]["poolclass"] is NullPool
    assert captured[0]["kwargs"]["pool_pre_ping"] is True
    assert captured[0]["kwargs"]["connect_args"] == {"prepared_statement_cache_size": 0}


def test_worker_session_factory_builds_new_factory_for_new_pid(monkeypatch) -> None:
    simulation_task._WORKER_SESSION_FACTORIES.clear()

    class _Settings:
        database_url = "sqlite+aiosqlite:///tmp/algenta.db"

    created = {"count": 0}

    def _fake_create_async_engine(url: str, **kwargs: Any) -> object:
        created["count"] += 1
        return object()

    monkeypatch.setattr(simulation_task, "create_async_engine", _fake_create_async_engine)
    monkeypatch.setattr("apps.api_server.config.get_settings", lambda: _Settings())

    pid_values = iter([2001, 2002])
    monkeypatch.setattr(simulation_task.os, "getpid", lambda: next(pid_values))

    first = simulation_task._get_worker_session_factory()
    second = simulation_task._get_worker_session_factory()

    assert first is not second
    assert created["count"] == 2
