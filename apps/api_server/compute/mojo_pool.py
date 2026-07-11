"""
Algenta Runtime Worker Pool — long-lived processes with Unix domain socket IPC.

Replaces asyncio.create_subprocess_exec() per-request (~22ms OS fork+exec)
with a pre-warmed pool of persistent runtime worker processes (~0.5ms IPC).

Architecture:
  - MOJO_POOL_SIZE workers spawned at FastAPI startup
  - Each worker = 1 runtime process + 1 persistent asyncio StreamReader/Writer pair
  - Workers stored in asyncio.Queue — acquire/release with no locks needed
  - Health monitor task restarts crashed workers within 50ms
  - Graceful shutdown: drain queue, send SIGTERM, wait for exit

Wire protocol (same both directions):
  [4 bytes big-endian uint32: payload length] [N bytes: UTF-8 JSON]

Phase 5: framed responses include "_proto":1 for protocol versioning.
Phase 1: MOJO_ALLOW_SUBPROCESS_FALLBACK env var controls fallback behavior.
         Pool startup fast-fails when MOJO_ALLOW_SUBPROCESS_FALLBACK=false
         and the binary does not support --server mode.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import struct
import tempfile
import threading
import time
import uuid
from asyncio import Queue
from pathlib import Path
from typing import Any

import structlog

from apps.api_server.compute.mojo_errors import MojoEngineError
from apps.api_server.middleware.metrics import record_mojo_pool_wait, record_worker_restart
from apps.runtime.native_worker import resolve_native_worker

logger = structlog.get_logger(__name__)

__all__ = ["MojoEngineError", "MojoWorkerPool", "get_pool_sync", "invoke_via_pool", "set_pool"]

_REPO_ROOT = Path(__file__).parents[3]


def _default_binary_path() -> Path:
    resolved = resolve_native_worker(require_verified=False)
    if resolved is not None and not resolved.public_error:
        return resolved.path
    return _REPO_ROOT / "mojo_build" / "simulate"


_BINARY_PATH = _default_binary_path()
_SOCKET_DIR = Path(tempfile.gettempdir()) / "algenta-mojo"


def _env_flag(name: str, default: str = "true") -> bool:
    return os.environ.get(name, default).lower() == "true"


# Number of long-lived Mojo worker processes
MOJO_POOL_SIZE = int(os.environ.get("MOJO_POOL_SIZE", str(max(1, (os.cpu_count() or 4) - 1))))

# How long to wait for a worker to become available
ACQUIRE_TIMEOUT_S = float(os.environ.get("MOJO_ACQUIRE_TIMEOUT_S", "10.0"))

# How long to wait for a single computation
COMPUTE_TIMEOUT_S = float(os.environ.get("MOJO_COMPUTE_TIMEOUT_S", "60.0"))

# How long to wait for worker to signal ready after spawn
WORKER_READY_TIMEOUT_S = float(os.environ.get("MOJO_WORKER_READY_TIMEOUT_S", "5.0"))

# Startup server-mode probe budgets. Generous by default: at API boot the whole VM is under heavy
# load (large app import + multiple uvicorn workers each starting a pool + DB/Redis connects), so a
# cold native binary loading its runtime libs can take far longer than the old hardcoded 2s to bind
# its socket — losing that race made the pool fall back even though the binary works (proven via
# single-shot + isolated --server). Env-tunable; the probe is also retried a few times.
PROBE_SOCKET_TIMEOUT_S = float(os.environ.get("MOJO_PROBE_SOCKET_TIMEOUT_S", "30.0"))
PROBE_FRAME_TIMEOUT_S = float(os.environ.get("MOJO_PROBE_FRAME_TIMEOUT_S", "10.0"))
PROBE_ATTEMPTS = int(os.environ.get("MOJO_PROBE_ATTEMPTS", "3"))
WORKER_START_ATTEMPTS = int(os.environ.get("MOJO_WORKER_START_ATTEMPTS", "3"))
WORKER_START_RETRY_DELAY_S = float(os.environ.get("MOJO_WORKER_START_RETRY_DELAY_S", "0.1"))

# Phase 1: Control subprocess fallback policy.
# "true"  — allow transparent subprocess fallback (dev default, slower but safe)
# "false" — hard fail if pool cannot start; no subprocess fallback (production)
_ALLOW_SUBPROCESS_FALLBACK = _env_flag("MOJO_ALLOW_SUBPROCESS_FALLBACK")
_ALLOW_PARTIAL_POOL = _env_flag("MOJO_POOL_ALLOW_PARTIAL", "false")


class _Worker:
    """One Mojo worker process + its persistent socket connection."""

    __slots__ = ("id", "socket_path", "proc", "reader", "writer", "healthy")

    def __init__(self, worker_id: int) -> None:
        self.id = worker_id
        self.socket_path = _SOCKET_DIR / f"worker-{worker_id}-{uuid.uuid4().hex[:8]}.sock"
        self.proc: asyncio.subprocess.Process | None = None
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.healthy: bool = False

    async def start(self) -> None:
        """Spawn the Mojo process and connect to its Unix socket."""
        _SOCKET_DIR.mkdir(parents=True, exist_ok=True)

        if self.socket_path.exists():
            self.socket_path.unlink()

        self.proc = await asyncio.create_subprocess_exec(  # noqa: S603
            str(_BINARY_PATH),
            "--server",
            str(self.socket_path),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        deadline = time.monotonic() + WORKER_READY_TIMEOUT_S
        while not self.socket_path.exists():
            if time.monotonic() > deadline:
                raise MojoEngineError(
                    f"Worker {self.id} did not create socket within {WORKER_READY_TIMEOUT_S}s",
                    code="worker_start_timeout",
                    recoverable=True,
                    stage="worker_start",
                    details={"worker_id": self.id},
                )
            await asyncio.sleep(0.01)

        self.reader, self.writer = await asyncio.open_unix_connection(str(self.socket_path))

        try:
            ready_data = await asyncio.wait_for(self._recv_frame(), timeout=WORKER_READY_TIMEOUT_S)
            ready = json.loads(ready_data)
            if ready.get("status") != "ready":
                raise MojoEngineError(
                    f"Worker {self.id} sent unexpected handshake: {ready}",
                    code="worker_handshake_invalid",
                    recoverable=True,
                    stage="worker_start",
                    details={"worker_id": self.id},
                )
        except TimeoutError as exc:
            raise MojoEngineError(
                f"Worker {self.id} did not send ready handshake",
                code="worker_handshake_timeout",
                recoverable=True,
                stage="worker_start",
                details={"worker_id": self.id},
            ) from exc

        self.healthy = True
        logger.debug("mojo_worker_ready", worker_id=self.id, socket=str(self.socket_path))

    async def invoke(
        self,
        payload: dict[str, Any],
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """
        Send payload to worker, return result.
        Phase 1: fallback re-dispatch REMOVED — Mojo now handles all 11 engine types
        in server mode. No subprocess fallback from the worker layer.
        Phase 5: check _proto version in response for forward-compatibility.
        """
        assert self.reader is not None and self.writer is not None

        data = json.dumps(payload).encode("utf-8")
        frame = struct.pack(">I", len(data)) + data
        self.writer.write(frame)
        await self.writer.drain()

        compute_timeout = timeout if timeout is not None else COMPUTE_TIMEOUT_S
        try:
            raw = await asyncio.wait_for(self._recv_frame(), timeout=compute_timeout)
        except TimeoutError as exc:
            self.healthy = False
            raise MojoEngineError(
                f"Worker {self.id} timed out after {compute_timeout}s",
                exit_code=124,
                code="timeout",
                recoverable=True,
                engine_type=str(payload.get("engine_type") or "unknown"),
                stage="worker_exec",
                details={"worker_id": self.id},
            ) from exc

        result = json.loads(raw)
        if "error" in result:
            raise MojoEngineError(
                result["error"],
                exit_code=1,
                code="engine_reported_error",
                recoverable=False,
                engine_type=str(payload.get("engine_type") or "unknown"),
                stage="worker_exec",
                details={"worker_id": self.id},
            )

        # Phase 5: protocol version check — v1 is current JSON, v2+ = future binary
        proto = result.get("_proto", 1)
        if proto > 1:
            logger.warning(
                "mojo_pool_unknown_proto",
                proto=proto,
                hint="Update mojo_pool.py to handle this protocol version",
            )

        # Phase 1: NO subprocess fallback re-dispatch here.
        # All engines return proper results in server mode since Phase 1 fix.
        # If a "fallback" key somehow appears, it is treated as an error in production.
        if result.get("fallback") == "subprocess":
            if not _ALLOW_SUBPROCESS_FALLBACK:
                raise MojoEngineError(
                    f"Engine {payload.get('engine_type')} returned subprocess fallback "
                    "but MOJO_ALLOW_SUBPROCESS_FALLBACK=false. "
                    "Install an Algenta build with a healthy bundled runtime.",
                    exit_code=1,
                    code="unexpected_subprocess_fallback",
                    recoverable=False,
                    engine_type=str(payload.get("engine_type") or "unknown"),
                    stage="worker_exec",
                    details={"worker_id": self.id},
                )
            logger.warning(
                "mojo_pool_unexpected_fallback",
                engine_type=payload.get("engine_type"),
                reason=result.get("reason", ""),
                hint=(
                    "All engines should be handled in server mode. "
                    "Install a healthy bundled runtime."
                ),
            )
            # In dev mode only: fall through to subprocess if explicitly allowed
            from apps.api_server.compute.mojo_adapter import _invoke_subprocess

            return await _invoke_subprocess(payload)

        return dict(result)

    async def _recv_frame(self) -> bytes:
        """Read one length-prefixed frame from the worker."""
        assert self.reader is not None
        header = await self.reader.readexactly(4)
        length = struct.unpack(">I", header)[0]
        return await self.reader.readexactly(length)

    async def stop(self) -> None:
        """Close connection and terminate the worker process."""
        self.healthy = False
        try:
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
        except Exception as exc:
            logger.debug("mojo_worker_close_failed", worker_id=self.id, error=str(exc))
        try:
            if self.proc and self.proc.returncode is None:
                self.proc.terminate()
                try:
                    await asyncio.wait_for(self.proc.wait(), timeout=3.0)
                except TimeoutError:
                    self.proc.kill()
        except Exception as exc:
            logger.debug("mojo_worker_terminate_failed", worker_id=self.id, error=str(exc))
        try:
            if self.socket_path.exists():
                self.socket_path.unlink()
        except Exception as exc:
            logger.debug("mojo_worker_socket_cleanup_failed", worker_id=self.id, error=str(exc))


class MojoWorkerPool:
    """
    Pool of long-lived Mojo worker processes.

    Workers communicate via Unix domain socket (persistent connection).
    Requests are dispatched from an asyncio.Queue — no locks needed.
    Health monitor replaces crashed workers automatically.

    Phase 1: Logs mojo_runtime_mode at startup ("pool" or "subprocess_fallback").
    Phase 1: Hard-fails at startup when MOJO_ALLOW_SUBPROCESS_FALLBACK=false
             and binary doesn't support --server mode.
    """

    def __init__(self, size: int = MOJO_POOL_SIZE) -> None:
        self._size = size
        self._workers: list[_Worker] = []
        self._queue: Queue[_Worker] = Queue()
        self._monitor: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread_id: int | None = None
        self._running = False

    async def _binary_supports_server_mode(self) -> bool:
        """
        Full health check: spawn binary in --server mode, connect via Unix socket,
        send a known test payload, and verify the result is numerically correct.

        A socket appearing is necessary but not sufficient — some binary builds
        accept the connection but return all-zero statistics (broken server-mode
        implementation). We validate by running a fixed simulation and checking
        that mean > 0.

        Timeout: 3 seconds total.
        """
        test_sock = _SOCKET_DIR / f"probe-{os.getpid()}.sock"
        _SOCKET_DIR.mkdir(parents=True, exist_ok=True)
        probe = None
        reader = None
        writer = None
        try:
            probe = await asyncio.create_subprocess_exec(  # noqa: S603
                str(_BINARY_PATH),
                "--server",
                str(test_sock),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )

            # Wait for socket to appear
            deadline = asyncio.get_event_loop().time() + PROBE_SOCKET_TIMEOUT_S
            while asyncio.get_event_loop().time() < deadline:
                if test_sock.exists():
                    break
                if probe.returncode is not None:
                    return False
                await asyncio.sleep(0.05)
            else:
                return False  # socket never appeared

            # Connect and exchange handshake
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(str(test_sock)), timeout=PROBE_FRAME_TIMEOUT_S
            )
            header = await asyncio.wait_for(reader.readexactly(4), timeout=PROBE_FRAME_TIMEOUT_S)
            length = struct.unpack(">I", header)[0]
            ready_data = await asyncio.wait_for(
                reader.readexactly(length), timeout=PROBE_FRAME_TIMEOUT_S
            )
            ready = json.loads(ready_data)
            if ready.get("status") != "ready":
                return False

            # Send a deterministic test payload — fixed distribution so mean == 100.0
            test_payload = {
                "engine_type": "monte_carlo",
                "runs": 100,
                "seed": 1,
                "variables": [
                    {"name": "x", "distribution": "fixed", "params": {"value": 100.0}},
                ],
                "objective_function": "x",
                "correlations": [],
                "scoring": {"expected_value": 1.0, "downside_risk": 0.0},
            }
            data = json.dumps(test_payload).encode("utf-8")
            frame = struct.pack(">I", len(data)) + data
            writer.write(frame)
            await writer.drain()

            # Read result and validate
            header = await asyncio.wait_for(reader.readexactly(4), timeout=PROBE_FRAME_TIMEOUT_S)
            length = struct.unpack(">I", header)[0]
            raw = await asyncio.wait_for(reader.readexactly(length), timeout=PROBE_FRAME_TIMEOUT_S)
            result = json.loads(raw)

            mean = float(result.get("summary", {}).get("mean", 0.0))
            if mean == 0.0:
                logger.warning(
                    "mojo_server_mode_compute_broken",
                    mean=mean,
                    hint="Binary creates socket but returns zero statistics. "
                    "Falling back to subprocess mode. Install a healthy bundled runtime.",
                )
                return False

            return True

        except Exception as exc:
            logger.debug("mojo_server_mode_probe_failed", error=str(exc))
            return False
        finally:
            try:
                if writer:
                    writer.close()
            except Exception as exc:
                logger.debug("mojo_probe_writer_close_failed", error=str(exc))
            try:
                if probe and probe.returncode is None:
                    probe.terminate()
            except Exception as exc:
                logger.debug("mojo_probe_terminate_failed", error=str(exc))
            try:
                test_sock.unlink()
            except Exception as exc:
                logger.debug("mojo_probe_socket_cleanup_failed", error=str(exc))

    async def start(self) -> None:
        """
        Spawn all workers and start health monitor.
        Phase 1: logs mojo_runtime_mode; hard-fails if fallback forbidden.
        """
        if not _BINARY_PATH.exists() or not os.access(_BINARY_PATH, os.X_OK):
            msg = (
                f"Algenta runtime worker not found at {_BINARY_PATH}. "
                "Install an Algenta build that includes the bundled runtime for this platform."
            )
            if not _ALLOW_SUBPROCESS_FALLBACK:
                raise MojoEngineError(
                    msg,
                    code="binary_missing",
                    recoverable=True,
                    stage="pool_start",
                )
            logger.warning("mojo_pool_binary_missing", hint=msg)
            logger.info(
                "mojo_runtime_mode",
                mode="subprocess_fallback",
                reason="binary_not_found",
                allow_fallback=_ALLOW_SUBPROCESS_FALLBACK,
            )
            self._running = False
            return

        supports_server = False
        for _attempt in range(max(1, PROBE_ATTEMPTS)):
            supports_server = await self._binary_supports_server_mode()
            if supports_server:
                break
            if _attempt + 1 < max(1, PROBE_ATTEMPTS):
                logger.warning(
                    "mojo_server_mode_probe_retry",
                    attempt=_attempt + 1,
                    attempts=PROBE_ATTEMPTS,
                )
                await asyncio.sleep(1.0)
        if not supports_server:
            reason = "binary_does_not_support_server_mode"
            if not _ALLOW_SUBPROCESS_FALLBACK:
                raise MojoEngineError(
                    f"Algenta runtime worker at {_BINARY_PATH} does not support server mode "
                    "and runtime fallbacks are denied. "
                    "Install a build with a healthy bundled runtime.",
                    code="server_mode_unavailable",
                    recoverable=True,
                    stage="pool_start",
                )
            logger.warning(
                "mojo_pool_server_mode_not_supported",
                hint="Runtime worker does not support server mode. "
                "Simulations will use subprocess fallback when allowed.",
            )
            logger.info(
                "mojo_runtime_mode", mode="subprocess_fallback", reason=reason, allow_fallback=True
            )
            self._running = False
            return

        self._loop = asyncio.get_running_loop()
        self._loop_thread_id = threading.get_ident()
        self._running = True
        logger.info("mojo_pool_starting", size=self._size, binary=str(_BINARY_PATH))
        logger.info("mojo_runtime_mode", mode="pool", workers=self._size, binary=str(_BINARY_PATH))

        spawn_tasks = [self._spawn_worker(i) for i in range(self._size)]
        await asyncio.gather(*spawn_tasks)
        if len(self._workers) != self._size:
            missing = self._size - len(self._workers)
            if _ALLOW_PARTIAL_POOL and self._workers:
                logger.warning(
                    "mojo_pool_ready_partial",
                    workers=len(self._workers),
                    expected=self._size,
                    missing=missing,
                )
            else:
                await self._stop_started_workers()
                self._running = False
                message = (
                    f"Algenta runtime worker pool started {self.available}/{self._size} workers; "
                    "refusing to run a partial pool."
                )
                if not _ALLOW_SUBPROCESS_FALLBACK:
                    raise MojoEngineError(
                        message,
                        code="worker_pool_incomplete",
                        recoverable=True,
                        stage="pool_start",
                        details={"workers_started": self.available, "workers_expected": self._size},
                    )
                logger.warning(
                    "mojo_pool_start_incomplete",
                    workers=self.available,
                    expected=self._size,
                    reason="partial_pool_refused",
                )
                logger.info(
                    "mojo_runtime_mode",
                    mode="subprocess_fallback",
                    reason="worker_pool_incomplete",
                    allow_fallback=True,
                )
                return

        self._monitor = asyncio.create_task(self._health_monitor(), name="mojo-health-monitor")
        logger.info("mojo_pool_ready", workers=len(self._workers))

    async def _stop_started_workers(self) -> None:
        stop_tasks = [worker.stop() for worker in self._workers]
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)
        self._workers.clear()
        self._queue = Queue()

    async def _spawn_worker(self, worker_id: int) -> bool:
        """Spawn one worker and add it to the available queue."""
        attempts = max(1, WORKER_START_ATTEMPTS)
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            worker = _Worker(worker_id)
            try:
                await worker.start()
                self._workers.append(worker)
                await self._queue.put(worker)
                return True
            except Exception as exc:
                last_error = exc
                await worker.stop()
                if attempt < attempts:
                    logger.warning(
                        "mojo_worker_spawn_retry",
                        worker_id=worker_id,
                        attempt=attempt,
                        attempts=attempts,
                        error=str(exc),
                    )
                    await asyncio.sleep(WORKER_START_RETRY_DELAY_S)
        logger.error(
            "mojo_worker_spawn_failed",
            worker_id=worker_id,
            attempts=attempts,
            error=str(last_error) if last_error else "unknown",
        )
        return False

    async def invoke(
        self,
        payload: dict[str, Any],
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """
        Dispatch payload to an available worker.
        Raises MojoEngineError("Mojo pool is not running") when pool is inactive —
        mojo_adapter.py catches this and routes to subprocess fallback (if allowed).
        """
        if not self._running:
            raise MojoEngineError(
                "Mojo pool is not running",
                code="pool_not_running",
                recoverable=True,
                stage="pool_dispatch",
            )

        acquire_started = time.perf_counter()
        try:
            worker = await asyncio.wait_for(self._queue.get(), timeout=ACQUIRE_TIMEOUT_S)
        except TimeoutError as exc:
            raise MojoEngineError(
                f"All {self._size} Mojo workers busy — no worker available after "
                f"{ACQUIRE_TIMEOUT_S}s. Increase MOJO_POOL_SIZE or reduce request rate.",
                code="workers_busy",
                recoverable=True,
                engine_type=str(payload.get("engine_type") or "unknown"),
                stage="pool_acquire",
            ) from exc

        try:
            record_mojo_pool_wait(time.perf_counter() - acquire_started)
        except Exception as exc:
            logger.warning("mojo_pool_wait_metric_failed", error=str(exc))

        try:
            result = await worker.invoke(payload, timeout=timeout)
            return result
        except MojoEngineError as exc:
            if not worker.healthy:
                logger.warning("mojo_worker_unhealthy", worker_id=worker.id)
                asyncio.create_task(self._replace_worker(worker))
                raise MojoEngineError(
                    f"Worker {worker.id} became unhealthy during engine execution.",
                    exit_code=getattr(exc, "exit_code", 1),
                    code="worker_unhealthy",
                    recoverable=True,
                    engine_type=str(payload.get("engine_type") or "unknown"),
                    stage="pool_dispatch",
                    details={"worker_id": worker.id, "cause": exc.code},
                ) from exc
            raise
        finally:
            if worker.healthy:
                await self._queue.put(worker)

    async def _replace_worker(self, dead_worker: _Worker) -> None:
        """Replace a crashed worker with a fresh one."""
        logger.info("mojo_worker_replacing", worker_id=dead_worker.id)
        try:
            self._workers.remove(dead_worker)
        except ValueError:
            pass
        await dead_worker.stop()
        await asyncio.sleep(0.1)
        replaced = await self._spawn_worker(dead_worker.id)
        if replaced:
            try:
                record_worker_restart()
            except Exception as exc:
                logger.warning("mojo_worker_restart_metric_failed", error=str(exc))

    async def _health_monitor(self) -> None:
        """Periodically check workers, replace crashed ones."""
        while self._running:
            await asyncio.sleep(5.0)
            for worker in list(self._workers):
                if worker.proc and worker.proc.returncode is not None:
                    logger.warning(
                        "mojo_worker_died",
                        worker_id=worker.id,
                        exit_code=worker.proc.returncode,
                    )
                    worker.healthy = False
                    asyncio.create_task(self._replace_worker(worker))

    async def stop(self) -> None:
        """Stop all workers and cancel health monitor."""
        self._running = False
        self._loop = None
        self._loop_thread_id = None

        if self._monitor:
            self._monitor.cancel()
            try:
                await self._monitor
            except asyncio.CancelledError:
                pass

        stop_tasks = [w.stop() for w in self._workers]
        await asyncio.gather(*stop_tasks, return_exceptions=True)
        self._workers.clear()

        logger.info("mojo_pool_stopped")

    @property
    def size(self) -> int:
        return self._size

    @property
    def running(self) -> bool:
        return self._running

    @property
    def available(self) -> int:
        return self._queue.qsize()

    def invoke_sync(self, payload: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
        """
        Synchronous bridge into the running Mojo pool.

        Used by synchronous planner code that is intentionally offloaded to a
        worker thread. This must never block the pool's owning event-loop
        thread; callers on that thread must use the async invoke path directly.
        """
        if not self._running:
            raise MojoEngineError(
                "Mojo pool is not running",
                code="pool_not_running",
                recoverable=True,
                stage="pool_dispatch",
            )
        if self._loop is None or self._loop.is_closed():
            raise MojoEngineError(
                "Mojo pool loop is not available",
                code="pool_loop_unavailable",
                recoverable=True,
                stage="pool_dispatch",
            )
        if self._loop_thread_id == threading.get_ident():
            raise MojoEngineError(
                "Mojo pool sync invocation cannot run on the pool event-loop thread",
                code="sync_on_pool_thread",
                recoverable=True,
                stage="pool_dispatch",
            )

        wait_timeout = timeout if timeout is not None else (ACQUIRE_TIMEOUT_S + COMPUTE_TIMEOUT_S)
        try:
            future = asyncio.run_coroutine_threadsafe(
                self.invoke(payload, timeout=timeout),
                self._loop,
            )
        except RuntimeError as exc:
            raise MojoEngineError(
                "Mojo pool loop is not available",
                code="pool_loop_unavailable",
                recoverable=True,
                stage="pool_dispatch",
            ) from exc

        try:
            return future.result(timeout=wait_timeout)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise MojoEngineError(
                f"Mojo pool sync invoke timed out after {wait_timeout}s",
                exit_code=124,
                code="timeout",
                recoverable=True,
                engine_type=str(payload.get("engine_type") or "unknown"),
                stage="pool_dispatch",
            ) from exc


# ─── Module-level singleton ────────────────────────────────────────────────────

_pool: MojoWorkerPool | None = None


def set_pool(pool: MojoWorkerPool | None) -> None:
    global _pool
    _pool = pool


def get_pool_sync() -> MojoWorkerPool:
    if _pool is None:
        raise MojoEngineError(
            "Mojo pool not initialized. Check FastAPI lifespan.",
            code="pool_not_initialized",
            recoverable=True,
            stage="pool_dispatch",
        )
    return _pool


async def invoke_via_pool(payload: dict[str, Any]) -> dict[str, Any]:
    """Thin wrapper — delegates to the singleton pool. Called by mojo_adapter."""
    return await get_pool_sync().invoke(payload)
