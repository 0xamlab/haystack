from __future__ import annotations

import sys
import types
import uuid

import pytest
from fastapi import HTTPException
from fastapi.background import BackgroundTasks

import apps.api_server.routers.simulate as simulate_router


class _PersistSimulationStub:
    def __init__(self, exc: Exception | None = None) -> None:
        self._exc = exc
        self.calls: list[dict] = []

    def delay(self, **kwargs):  # type: ignore[no-untyped-def]
        if self._exc is not None:
            raise self._exc
        self.calls.append(kwargs)
        return None


def _install_worker_task_module(
    monkeypatch: pytest.MonkeyPatch,
    persist_stub: _PersistSimulationStub,
) -> None:
    module = types.ModuleType("apps.worker.tasks.simulation_task")
    module.persist_simulation = persist_stub
    monkeypatch.setitem(sys.modules, "apps.worker.tasks.simulation_task", module)


def _auth_context() -> dict[str, object]:
    return {
        "org_id": uuid.uuid4(),
        "key_id": uuid.uuid4(),
        "plan": "pro",
        "email": "owner@example.com",
    }


def test_dispatch_persist_uses_background_task_when_fallbacks_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persist_stub = _PersistSimulationStub(exc=RuntimeError("broker down"))
    _install_worker_task_module(monkeypatch, persist_stub)
    monkeypatch.setattr(simulate_router.settings, "runtime_fallback_mode", "allow")

    background_tasks = BackgroundTasks()
    simulate_router._dispatch_persist(
        persist_meta={"run_id": "run_123"},
        auth=_auth_context(),
        client_ip="127.0.0.1",
        background_tasks=background_tasks,
        redis_client=object(),
        request_id="req_123",
    )

    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].func is simulate_router._persist_in_process


def test_dispatch_persist_fails_closed_when_fallbacks_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persist_stub = _PersistSimulationStub(exc=RuntimeError("broker down"))
    _install_worker_task_module(monkeypatch, persist_stub)
    monkeypatch.setattr(simulate_router.settings, "runtime_fallback_mode", "deny")

    background_tasks = BackgroundTasks()
    with pytest.raises(HTTPException) as exc_info:
        simulate_router._dispatch_persist(
            persist_meta={"run_id": "run_123"},
            auth=_auth_context(),
            client_ip="127.0.0.1",
            background_tasks=background_tasks,
            redis_client=object(),
            request_id="req_123",
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["error"]["code"] == "persistence_backend_unavailable"
    assert background_tasks.tasks == []


def test_dispatch_persist_uses_background_task_when_transport_forced_in_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persist_stub = _PersistSimulationStub()
    _install_worker_task_module(monkeypatch, persist_stub)
    monkeypatch.setattr(simulate_router.settings, "simulation_persist_transport", "in_process")

    background_tasks = BackgroundTasks()
    simulate_router._dispatch_persist(
        persist_meta={"run_id": "run_123"},
        auth=_auth_context(),
        client_ip="127.0.0.1",
        background_tasks=background_tasks,
        redis_client=object(),
        request_id="req_123",
    )

    assert persist_stub.calls == []
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].func is simulate_router._persist_in_process
