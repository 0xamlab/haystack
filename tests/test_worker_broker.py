"""Local worker-concurrency broker (P2b).

Verifies the per-node cap that enforces a v2 license's ``concurrent_worker_limit``:
unlimited (limit 0) is a transparent no-op, a real cap bounds concurrency (queueing
excess callers), non-blocking acquisition rejects at capacity, and the singleton is
DARK by default — it only activates for a v2 license that sets the limit.
"""

from __future__ import annotations

import asyncio

import pytest

from apps.runtime.worker_broker import (
    WorkerBroker,
    WorkerCapacityError,
    configure_from_license,
    get_worker_broker,
    reset_worker_broker,
    worker_slot,
)


class _Lic:
    """Minimal DeviceLicense stand-in for the broker's license resolution."""

    def __init__(self, valid: bool, wl: int, activation_id: str = "") -> None:
        self.valid = valid
        self._wl = wl
        self.activation_id = activation_id

    def worker_limit(self) -> int:
        return self._wl


@pytest.fixture(autouse=True)
def _clean_singleton():
    reset_worker_broker()
    yield
    reset_worker_broker()


# ── Primitive: unlimited is a no-op ───────────────────────────────────────────


def test_unlimited_broker_never_blocks() -> None:
    async def _run() -> None:
        broker = WorkerBroker(0)
        assert broker.limit == 0
        release = asyncio.Event()
        peak = 0

        async def task() -> None:
            nonlocal peak
            async with broker.slot():
                peak = max(peak, broker.active)
                await release.wait()

        tasks = [asyncio.create_task(task()) for _ in range(8)]
        await asyncio.sleep(0.02)
        assert broker.active == 8  # all 8 admitted — no cap
        release.set()
        await asyncio.gather(*tasks)
        assert broker.active == 0
        assert peak == 8

    asyncio.run(_run())


# ── Primitive: a real cap bounds concurrency (queue) ──────────────────────────


def test_limit_bounds_concurrency_and_queues_excess() -> None:
    async def _run() -> None:
        broker = WorkerBroker(2)
        release = asyncio.Event()
        peak = 0
        entered = 0

        async def task() -> None:
            nonlocal peak, entered
            async with broker.slot():
                entered += 1
                peak = max(peak, broker.active)
                await release.wait()

        tasks = [asyncio.create_task(task()) for _ in range(5)]
        await asyncio.sleep(0.03)
        assert broker.active == 2  # only 2 admitted; 3 queued
        assert entered == 2
        release.set()
        await asyncio.gather(*tasks)
        assert entered == 5  # the queued callers eventually ran
        assert peak == 2  # never exceeded the cap
        assert broker.active == 0

    asyncio.run(_run())


# ── Primitive: non-blocking rejects at capacity ───────────────────────────────


def test_nonblocking_acquire_rejects_when_full() -> None:
    async def _run() -> None:
        broker = WorkerBroker(1)
        release = asyncio.Event()

        async def holder() -> None:
            async with broker.slot():
                await release.wait()

        t = asyncio.create_task(holder())
        await asyncio.sleep(0.01)
        assert broker.active == 1

        with pytest.raises(WorkerCapacityError):
            async with broker.slot(block=False):
                pass
        assert broker.active == 1  # the rejected acquisition left the count intact

        release.set()
        await t
        assert broker.active == 0

        # With a free slot, non-blocking succeeds.
        async with broker.slot(block=False):
            assert broker.active == 1
        assert broker.active == 0

    asyncio.run(_run())


# ── Primitive: status + configure + no underflow ──────────────────────────────


def test_status_reports_node_identity_and_availability() -> None:
    broker = WorkerBroker(3, node_id="act_node_1")
    st = broker.status()
    assert st == {
        "node_id": "act_node_1",
        "worker_limit": 3,
        "active_workers": 0,
        "available": 3,
    }
    # unlimited → availability is "n/a" (None), not a number
    assert WorkerBroker(0).status()["available"] is None


def test_configure_resets_limit_and_node() -> None:
    broker = WorkerBroker(0)
    broker.configure(5, node_id="n2")
    assert broker.limit == 5
    assert broker.node_id == "n2"
    broker.configure(-7)  # negative clamps to unlimited
    assert broker.limit == 0
    assert broker.node_id == "n2"  # node_id unchanged when not passed


def test_release_never_underflows() -> None:
    async def _run() -> None:
        broker = WorkerBroker(0)
        async with broker.slot():
            pass
        assert broker.active == 0
        # extra release can't drive the counter negative
        await broker._release()
        assert broker.active == 0

    asyncio.run(_run())


# ── Singleton wiring: DARK by default ─────────────────────────────────────────


def test_configure_from_license_v1_is_dark(monkeypatch) -> None:
    monkeypatch.setattr("apps.runtime.license.load_license", lambda key="": _Lic(True, 0))
    broker = configure_from_license()
    assert broker.limit == 0  # v1 / unspecified → no cap
    assert broker.node_id == ""


def test_configure_from_license_activates_for_v2(monkeypatch) -> None:
    monkeypatch.setattr(
        "apps.runtime.license.load_license", lambda key="": _Lic(True, 4, "act_42")
    )
    broker = configure_from_license()
    assert broker.limit == 4
    assert broker.node_id == "act_42"  # binds to the activation id


def test_configure_from_license_falls_back_to_device_id(monkeypatch) -> None:
    monkeypatch.setattr("apps.runtime.license.load_license", lambda key="": _Lic(True, 2, ""))
    monkeypatch.setattr("apps.runtime.device.get_device_id", lambda: "dev_node_abc")
    broker = configure_from_license()
    assert broker.limit == 2
    assert broker.node_id == "dev_node_abc"


def test_configure_from_license_invalid_or_error_is_dark(monkeypatch) -> None:
    monkeypatch.setattr("apps.runtime.license.load_license", lambda key="": _Lic(False, 99))
    assert configure_from_license().limit == 0  # invalid license never caps
    reset_worker_broker()

    def _boom(key: str = "") -> _Lic:
        raise RuntimeError("license backend down")

    monkeypatch.setattr("apps.runtime.license.load_license", _boom)
    assert configure_from_license().limit == 0  # resolution failure → dark, never raises


def test_configure_from_license_caches_until_forced(monkeypatch) -> None:
    monkeypatch.setattr("apps.runtime.license.load_license", lambda key="": _Lic(True, 0))
    assert configure_from_license().limit == 0
    # license changes, but cached resolution stands until force=True
    monkeypatch.setattr(
        "apps.runtime.license.load_license", lambda key="": _Lic(True, 8, "act_x")
    )
    assert configure_from_license().limit == 0  # cached
    assert configure_from_license(force=True).limit == 8  # re-resolved
    assert get_worker_broker().node_id == "act_x"


def test_worker_slot_uses_singleton_and_is_dark(monkeypatch) -> None:
    monkeypatch.setattr("apps.runtime.license.load_license", lambda key="": _Lic(True, 0))

    async def _run() -> None:
        async with worker_slot():
            assert get_worker_broker().active == 1  # tracked even when unlimited
        assert get_worker_broker().active == 0

    asyncio.run(_run())
