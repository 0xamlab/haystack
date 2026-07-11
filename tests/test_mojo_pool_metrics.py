from __future__ import annotations

from typing import Any

import pytest

from apps.api_server.compute import mojo_pool


class _FakeWorker:
    def __init__(self, worker_id: int = 1) -> None:
        self.id = worker_id
        self.healthy = True

    async def invoke(
        self, payload: dict[str, Any], *, timeout: float | None = None
    ) -> dict[str, Any]:
        return {"payload": payload, "timeout": timeout}

    async def stop(self) -> None:
        return None


@pytest.mark.anyio
async def test_pool_invoke_records_acquire_wait(monkeypatch) -> None:
    observed: list[float] = []
    monkeypatch.setattr(mojo_pool, "record_mojo_pool_wait", observed.append)
    pool = mojo_pool.MojoWorkerPool(size=1)
    pool._running = True
    worker = _FakeWorker()
    await pool._queue.put(worker)  # type: ignore[arg-type]

    result = await pool.invoke({"engine_type": "test"}, timeout=1.0)

    assert result["payload"] == {"engine_type": "test"}
    assert len(observed) == 1
    assert observed[0] >= 0


@pytest.mark.anyio
async def test_successful_worker_replacement_records_restart(monkeypatch) -> None:
    restarts: list[bool] = []
    worker = _FakeWorker()
    pool = mojo_pool.MojoWorkerPool(size=1)
    pool._workers = [worker]  # type: ignore[list-item]

    async def spawn(worker_id: int) -> bool:
        assert worker_id == worker.id
        return True

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(pool, "_spawn_worker", spawn)
    monkeypatch.setattr(mojo_pool.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(mojo_pool, "record_worker_restart", lambda: restarts.append(True))

    await pool._replace_worker(worker)  # type: ignore[arg-type]

    assert restarts == [True]
