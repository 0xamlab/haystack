"""Shard-aware runtime worker management for the local daemon.

The managed runtime bundle ships the runtime as a set of precompiled shard
workers (``algenta-runtime-worker``, ``algenta-runtime-worker-001`` …) plus a
``runtime-shards.json`` routing map (schema v1: module → owning worker). The
Python SDK path resolves the per-module worker binary itself and spawns one
session per worker; the daemon path historically executed everything through
ONE worker socket (the default shard), so any module outside the default shard
failed with ``module_not_registered``.

This module gives the daemon the same routing:

* ``load_runtime_shard_map`` parses and validates the shard map next to the
  resolved worker binary. When no map exists it returns ``None`` and the daemon
  keeps its historical single-worker behavior exactly (back-compat).

* ``ShardWorkerPool`` manages one worker process per shard. Lifecycle policy:

  - The DEFAULT shard worker starts eagerly at daemon boot (exactly as the
    single worker did before) and is never evicted — simulation engines, the
    query plane and every unrouted module land on it, so it is the hot path.
  - Every other shard worker spawns LAZILY on the first request routed to it
    (never all 26 upfront) and then stays resident: keep-alive is unbounded
    while the process is under the cap, because a running shard has already
    paid its startup cost and only the cap needs to bound total memory.
  - The cap is ``ALGENTA_RUNTIME_MAX_SHARD_WORKERS`` (default 4, minimum 1)
    lazy shard workers resident at once. Each shard worker is a fully compiled
    Mojo binary with an embedded CPython, so the cap bounds daemon memory on
    desktop hardware while the LRU keeps the hot working set warm. When a new
    shard would exceed the cap, the least-recently-used IDLE shard worker is
    stopped; its next request respawns it. If every lazy worker is in flight
    the cap is temporarily exceeded rather than refusing a request (concurrency
    is already bounded upstream by the licensed worker slots).
  - A worker that died is respawned transparently on the next acquire.

The map format and worker-name grammar mirror ``packages/algenta/algenta/
native/worker.py`` (the SDK's own shard routing) and ``scripts/
build_runtime_shards.py`` (the producer).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from apps.runtime.mojo_binary_freshness import inspect_mojo_binary_freshness
from apps.runtime.worker_launch import launchable_worker_executable, launchable_worker_socket

logger = structlog.get_logger(__name__)

SHARD_MAP_NAME = "runtime-shards.json"
DEFAULT_MAX_LAZY_WORKERS = 4
_MAX_LAZY_WORKERS_ENV = "ALGENTA_RUNTIME_MAX_SHARD_WORKERS"
_WORKER_READY_TIMEOUT_SECONDS = 8.0
_WORKER_NAME_RE = re.compile(r"algenta-runtime-worker(?:-\d{3})?(?:\.exe)?$")
_MODULE_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*$")


class ShardMapError(ValueError):
    """The runtime shard map is present but unusable. Fail back to one worker."""


class ShardWorkerUnavailable(RuntimeError):  # noqa: N818
    """A routed shard worker cannot be spawned or did not become ready."""


@dataclass(frozen=True)
class RuntimeShardMap:
    default_worker: str
    module_workers: dict[str, str]

    @property
    def workers(self) -> frozenset[str]:
        return frozenset(self.module_workers.values())

    @property
    def shard_count(self) -> int:
        return len(self.workers)

    def route(self, module_name: str | None) -> str:
        """The worker that owns ``module_name``.

        Mirrors the SDK: unknown modules fall back to the default worker, which
        then answers with its own ``module_not_registered`` — same as today.
        ``None`` routes to the default worker (simulation engines, the query
        plane, and any coarse message with no single routing module).
        """
        if module_name is None:
            return self.default_worker
        return self.module_workers.get(module_name, self.default_worker)


def load_runtime_shard_map(engine_dir: Path) -> RuntimeShardMap | None:
    """Parse and validate ``runtime-shards.json`` next to the worker binary.

    Returns ``None`` when no map exists (the single-worker back-compat path).
    Raises ``ShardMapError`` for a map that fails validation — callers fall
    back to single-worker mode with a warning rather than refusing to boot.
    """
    path = engine_dir / SHARD_MAP_NAME
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ShardMapError(f"runtime shard map is unreadable: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ShardMapError("runtime shard map must use schema_version 1")
    default_worker = payload.get("default_worker")
    module_workers = payload.get("module_workers")
    if not isinstance(default_worker, str) or not _WORKER_NAME_RE.fullmatch(default_worker):
        raise ShardMapError("runtime shard map has an invalid default worker")
    if not isinstance(module_workers, dict) or not module_workers:
        raise ShardMapError("runtime shard map has no module routes")
    normalized: dict[str, str] = {}
    for module_name, worker_name in module_workers.items():
        if not isinstance(module_name, str) or not _MODULE_NAME_RE.fullmatch(module_name):
            raise ShardMapError(f"runtime shard map has an invalid module name: {module_name!r}")
        if not isinstance(worker_name, str) or not _WORKER_NAME_RE.fullmatch(worker_name):
            raise ShardMapError(f"runtime shard map has an invalid worker name: {worker_name!r}")
        normalized[module_name] = worker_name
    workers = set(normalized.values())
    if default_worker not in workers:
        raise ShardMapError("runtime shard map default worker is unrouted")
    if payload.get("module_count") != len(normalized):
        raise ShardMapError("runtime shard map module_count is inconsistent")
    if payload.get("shard_count") != len(workers):
        raise ShardMapError("runtime shard map shard_count is inconsistent")
    return RuntimeShardMap(default_worker=default_worker, module_workers=normalized)


def max_lazy_shard_workers() -> int:
    """Resident-lazy-worker cap from ``ALGENTA_RUNTIME_MAX_SHARD_WORKERS``."""
    raw = os.environ.get(_MAX_LAZY_WORKERS_ENV, "").strip()
    if not raw:
        return DEFAULT_MAX_LAZY_WORKERS
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "runtime_shard_worker_cap_invalid",
            value=raw,
            default=DEFAULT_MAX_LAZY_WORKERS,
        )
        return DEFAULT_MAX_LAZY_WORKERS
    return max(1, value)


class ShardWorkerProcess:
    """One runtime worker binary listening on one unix socket (server mode)."""

    def __init__(
        self,
        *,
        name: str,
        binary: Path,
        sock: str,
        source: str,
        verified: bool,
    ) -> None:
        self._name = name
        self._binary = binary
        self._sock = sock
        self._source = source
        self._verified = verified
        self._proc: subprocess.Popen | None = None  # type: ignore[type-arg]

    @property
    def name(self) -> str:
        return self._name

    @property
    def sock(self) -> str:
        return self._sock

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc is not None else None

    def start(self) -> bool:
        """Start the worker. Returns False only when the binary is absent.

        Raises RuntimeError when an unverified binary is stale relative to its
        sources — the same fail-fast the historical single-worker boot had — and
        fails closed, exactly like ``daemon.MojoProcess.start()``, when a launch
        parameter does not pass ``apps.runtime.worker_launch`` vetting:
        ``NativeWorkerUnavailable`` (a RuntimeError) for a worker path that is
        not an absolute, executable regular file; ``ValueError`` for a socket
        path that is too long to bind or names an existing non-socket.
        """
        freshness = inspect_mojo_binary_freshness(self._binary)
        if not freshness.exists:
            logger.warning(
                "runtime_worker_not_found",
                worker=self._name,
                path=str(self._binary),
                hint=(
                    "Install an Algenta build that includes the bundled runtime for this platform."
                ),
            )
            return False
        if not self._verified and not freshness.is_fresh:
            raise RuntimeError(freshness.failure_message())

        # Vet both launch parameters right here, before anything touches the filesystem
        # or the OS -- the same gate daemon.MojoProcess.start() runs. The engine dir (and
        # so every shard binary) derives from the operator's worker override and the shard
        # sockets sit beside ALGENTA_MOJO_SOCK, so neither is trusted: the socket path must
        # be bindable and never an existing non-socket (the stale-socket unlink below must
        # not be pointable at an arbitrary file); the executable must be an absolute path
        # to an executable regular file. Fail closed on either.
        sock_path = launchable_worker_socket(self._sock)
        worker = launchable_worker_executable(self._binary)

        sock = Path(sock_path)
        sock.parent.mkdir(parents=True, exist_ok=True)
        if sock.exists():
            sock.unlink()

        self._proc = subprocess.Popen(  # noqa: S603
            [str(worker), "--server", sock_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        logger.info(
            "runtime_worker_started",
            worker=self._name,
            pid=self._proc.pid,
            sock=self._sock,
            source=self._source,
        )
        return True

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            logger.info("runtime_worker_stopped", worker=self._name, pid=self._proc.pid)
        self._proc = None

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def wait_ready(self, timeout: float = _WORKER_READY_TIMEOUT_SECONDS) -> bool:
        """Poll until the worker socket appears (binary is ready to accept)."""
        deadline = time.monotonic() + timeout
        sock = Path(self._sock)
        while time.monotonic() < deadline:
            if sock.exists():
                return True
            time.sleep(0.05)
        return False

    async def wait_ready_async(self, timeout: float = _WORKER_READY_TIMEOUT_SECONDS) -> bool:
        """Async variant for lazy in-request spawns — never blocks the event loop."""
        deadline = time.monotonic() + timeout
        sock = Path(self._sock)
        while time.monotonic() < deadline:
            if sock.exists():
                return True
            await asyncio.sleep(0.05)
        return False


class ShardWorkerPool:
    """Routes modules to shard workers and manages their process lifecycle.

    See the module docstring for the lifecycle policy. The pool owns the
    default worker too, so boot, lazy spawns, respawns, health and shutdown all
    go through one manager when a shard map is present.
    """

    def __init__(
        self,
        shard_map: RuntimeShardMap,
        engine_dir: Path,
        default_sock: str,
        *,
        worker_source: str,
        verified: bool,
        max_lazy_workers: int = DEFAULT_MAX_LAZY_WORKERS,
    ) -> None:
        self._shard_map = shard_map
        self._engine_dir = engine_dir
        self._default_sock = default_sock
        self._worker_source = worker_source
        self._verified = verified
        self._max_lazy_workers = max(1, max_lazy_workers)
        self._default_worker = ShardWorkerProcess(
            name=shard_map.default_worker,
            binary=engine_dir / shard_map.default_worker,
            sock=default_sock,
            source=worker_source,
            verified=verified,
        )
        self._lazy_workers: dict[str, ShardWorkerProcess] = {}
        self._last_used: dict[str, float] = {}
        self._in_flight: dict[str, int] = {}
        self._lock = asyncio.Lock()

    @property
    def shard_map(self) -> RuntimeShardMap:
        return self._shard_map

    @property
    def default_sock(self) -> str:
        return self._default_sock

    # ── Boot ──────────────────────────────────────────────────────────────

    def start_default(self) -> bool:
        """Eagerly start the default shard worker at daemon boot."""
        started = self._default_worker.start()
        if started:
            self._last_used[self._shard_map.default_worker] = time.monotonic()
        return started

    def wait_default_ready(self, timeout: float = _WORKER_READY_TIMEOUT_SECONDS) -> bool:
        return self._default_worker.wait_ready(timeout)

    # ── Routing / lifecycle ───────────────────────────────────────────────

    def _sock_for(self, worker_name: str) -> str:
        """The unix socket for a shard worker.

        Shard sockets follow the default socket's existing ``worker-N.sock``
        convention (the default shard is shard 0 → ``worker-0.sock``), which
        keeps the path SHORT: macOS caps AF_UNIX paths at 104 bytes and the
        default dir (``$TMPDIR/algenta-mojo``) already consumes most of it, so
        spelling the full worker binary name into the socket would overflow.
        """
        if worker_name == self._shard_map.default_worker:
            return self._default_sock
        suffix = worker_name.rsplit("-", 1)[-1]  # "...-NNN" → "NNN"
        return str(Path(self._default_sock).parent / f"worker-{suffix}.sock")

    def _spawn_lazy_worker(self, worker_name: str) -> ShardWorkerProcess:
        return ShardWorkerProcess(
            name=worker_name,
            binary=self._engine_dir / worker_name,
            sock=self._sock_for(worker_name),
            source=self._worker_source,
            verified=self._verified,
        )

    def _evict_idle_locked(self) -> None:
        """Stop the least-recently-used idle lazy worker (never the default).

        Called with ``self._lock`` held. When every lazy worker is in flight,
        nothing is evicted and the cap is temporarily exceeded instead of
        refusing the request.
        """
        candidates = [
            (self._last_used.get(name, 0.0), name)
            for name, worker in self._lazy_workers.items()
            if worker.is_running() and self._in_flight.get(name, 0) == 0
        ]
        if not candidates:
            logger.warning(
                "runtime_shard_worker_cap_exceeded_all_busy",
                cap=self._max_lazy_workers,
                resident=len(self._lazy_workers),
            )
            return
        _, evict_name = min(candidates)
        evicted = self._lazy_workers.pop(evict_name)
        evicted.stop()
        self._in_flight.pop(evict_name, None)
        self._last_used.pop(evict_name, None)
        logger.info(
            "runtime_shard_worker_evicted",
            worker=evict_name,
            cap=self._max_lazy_workers,
        )

    async def acquire(self, module_name: str | None) -> str:
        """Return the socket serving ``module_name``, spawning its shard lazily.

        Raises ``ShardWorkerUnavailable`` when the shard binary is missing or
        the worker does not become ready.
        """
        worker_name = self._shard_map.route(module_name)
        async with self._lock:
            if worker_name == self._shard_map.default_worker:
                worker = self._default_worker
            else:
                worker = self._lazy_workers.get(worker_name)
                if worker is None or not worker.is_running():
                    if worker is not None:
                        # Dead since the last request — drop it before respawning.
                        self._lazy_workers.pop(worker_name, None)
                        self._in_flight.pop(worker_name, None)
                    while len(self._lazy_workers) >= self._max_lazy_workers:
                        before = len(self._lazy_workers)
                        self._evict_idle_locked()
                        if len(self._lazy_workers) >= before:
                            break  # nothing idle left to evict — exceed the cap
                    worker = self._spawn_lazy_worker(worker_name)
                    self._lazy_workers[worker_name] = worker
            if not worker.is_running():
                try:
                    started = worker.start()
                except (RuntimeError, ValueError) as exc:
                    # RuntimeError: stale unverified binary, or a worker path that failed
                    # launch vetting. ValueError: a shard socket path that failed vetting.
                    # Both surface as the typed error the executor reports to the caller.
                    raise ShardWorkerUnavailable(
                        f"runtime shard worker '{worker_name}' refused to start: {exc}"
                    ) from exc
                if not started:
                    self._lazy_workers.pop(worker_name, None)
                    raise ShardWorkerUnavailable(
                        f"runtime shard worker binary '{worker_name}' is missing."
                    )
                if not await worker.wait_ready_async():
                    worker.stop()
                    self._lazy_workers.pop(worker_name, None)
                    raise ShardWorkerUnavailable(
                        f"runtime shard worker '{worker_name}' did not become ready."
                    )
            self._last_used[worker_name] = time.monotonic()
            self._in_flight[worker_name] = self._in_flight.get(worker_name, 0) + 1
            return worker.sock

    def release(self, module_name: str | None) -> None:
        """Mark one in-flight call against the routed worker as finished."""
        worker_name = self._shard_map.route(module_name)
        self._in_flight[worker_name] = max(0, self._in_flight.get(worker_name, 0) - 1)

    # ── Health / shutdown ─────────────────────────────────────────────────

    def status(self) -> dict[str, dict[str, Any]]:
        """Per-worker lifecycle state (default first) for health reporting."""
        entries: dict[str, dict[str, Any]] = {}
        workers = [
            (self._shard_map.default_worker, self._default_worker),
            *self._lazy_workers.items(),
        ]
        for name, worker in workers:
            entries[name] = {
                "default": name == self._shard_map.default_worker,
                "running": worker.is_running(),
                "pid": worker.pid,
                "socket": worker.sock,
                "in_flight": self._in_flight.get(name, 0),
            }
        return entries

    def stop_all(self) -> None:
        self._default_worker.stop()
        for worker in self._lazy_workers.values():
            worker.stop()
        self._lazy_workers.clear()
        self._in_flight.clear()
        self._last_used.clear()
