"""Local worker-concurrency broker — enforces a license's ``concurrent_worker_limit``
on a single runtime node.

Enforcement is split (see ``apps/runtime/license.py`` + the licensing plan):

* The **control plane** enforces GLOBAL pools — active nodes, named seats — at
  activation / renewal / reconciliation.
* This **broker** enforces the LOCAL per-node cap: at most ``concurrent_worker_limit``
  executions run at once on this node, regardless of how many client processes funnel
  through the daemon. It is the runtime counterpart to the control plane's active-node
  reconciliation, and it surfaces this node's identity + live slot usage (``status()``)
  for that reconciliation.

The daemon is the per-node choke point: every local execution funnels through one
daemon, so bounding concurrency here bounds the node — 100 client processes on one box
cannot exceed the licensed worker count.

DARK BY DEFAULT — a limit of ``0`` ("unspecified": every v1/legacy license, and any v2
license that does not set ``concurrent_worker_limit``) makes the broker a transparent
no-op that never caps or queues. Only a v2 license with ``concurrent_worker_limit > 0``
activates the cap. Enforcement of *missing* licenses (fail-closed) stays P5.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog

logger = structlog.get_logger(__name__)


class WorkerCapacityError(RuntimeError):
    """Raised by a non-blocking ``slot()`` acquisition when the node is at capacity."""


class WorkerBroker:
    """A per-node concurrency gate sized to the license's worker limit.

    ``limit <= 0`` means unlimited — the broker tracks the live count for ``status()``
    but never blocks or rejects. ``limit > 0`` caps concurrent slots: ``slot(block=True)``
    (the default) queues callers beyond the cap until a slot frees; ``slot(block=False)``
    rejects immediately with :class:`WorkerCapacityError`.
    """

    def __init__(self, limit: int = 0, *, node_id: str = "") -> None:
        self._limit = max(0, int(limit))
        self._node_id = node_id
        self._active = 0
        self._cond = asyncio.Condition()

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def active(self) -> int:
        return self._active

    @property
    def node_id(self) -> str:
        return self._node_id

    def configure(self, limit: int, *, node_id: str | None = None) -> None:
        """(Re)set the cap — e.g. at daemon startup or after a license renewal.

        ``limit <= 0`` => unlimited. The new cap applies to slots acquired *after* this
        call; in-flight slots are unaffected (they decrement the live counter on release
        regardless of the current limit). Call between batches / when idle: this does not
        wake callers already queued under the old limit.
        """
        self._limit = max(0, int(limit))
        if node_id is not None:
            self._node_id = node_id

    @asynccontextmanager
    async def slot(self, *, block: bool = True) -> AsyncIterator[None]:
        """Hold one worker slot for the duration of the ``async with`` body."""
        await self._acquire(block=block)
        try:
            yield
        finally:
            await self._release()

    async def _acquire(self, *, block: bool) -> None:
        if self._limit <= 0:  # unlimited — transparent no-op fast path
            self._active += 1
            return
        async with self._cond:
            if self._active >= self._limit:
                if not block:
                    logger.warning(
                        "worker_capacity_exceeded",
                        node_id=self._node_id[:8],
                        limit=self._limit,
                        active=self._active,
                    )
                    raise WorkerCapacityError(
                        f"node at worker capacity ({self._active}/{self._limit})"
                    )
                while self._active >= self._limit:
                    await self._cond.wait()
            self._active += 1

    async def _release(self) -> None:
        if self._limit <= 0:
            self._active = max(0, self._active - 1)
            return
        async with self._cond:
            self._active = max(0, self._active - 1)
            self._cond.notify(1)

    def status(self) -> dict[str, object]:
        """Live slot usage for control-plane reconciliation."""
        return {
            "node_id": self._node_id,
            "worker_limit": self._limit,
            "active_workers": self._active,
            "available": (self._limit - self._active) if self._limit > 0 else None,
        }


# ── Process-wide singleton, wired to the local license ────────────────────────

_broker: WorkerBroker | None = None
_resolved = False


def get_worker_broker() -> WorkerBroker:
    """Return the process-wide broker (unlimited until configured from a license)."""
    global _broker
    if _broker is None:
        _broker = WorkerBroker(0)
    return _broker


def configure_from_license(*, force: bool = False) -> WorkerBroker:
    """Sync the broker's cap from the local license (lazy, cached).

    Resolved once on first use; pass ``force=True`` (e.g. from the renewal heartbeat) to
    re-read after the license changes. Never raises — any resolution failure leaves the
    broker unlimited (dark), so license plumbing can never break execution.
    """
    global _resolved
    broker = get_worker_broker()
    if _resolved and not force:
        return broker
    try:
        from apps.runtime.device import get_device_id
        from apps.runtime.license import load_license

        api_key = os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "")
        lic = load_license(api_key)
        limit = lic.worker_limit() if getattr(lic, "valid", False) else 0
        node = (getattr(lic, "activation_id", "") or get_device_id()) if limit > 0 else ""
        broker.configure(limit, node_id=node)
    except Exception:  # noqa: BLE001 — broker resolution must never break execution
        logger.debug("worker_broker_license_unresolved", exc_info=True)
        broker.configure(0)
    _resolved = True
    return broker


def reset_worker_broker() -> None:
    """Drop the singleton (tests / daemon restart)."""
    global _broker, _resolved
    _broker = None
    _resolved = False


@asynccontextmanager
async def worker_slot(*, block: bool = True) -> AsyncIterator[None]:
    """Hold one licensed worker slot, sizing the broker from the license on first use."""
    broker = configure_from_license()
    async with broker.slot(block=block):
        yield
