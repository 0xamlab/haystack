"""
Algenta local runtime daemon.

Responsibilities:
  1. Start / manage the Mojo binary subprocess (server mode)
  2. Start the gRPC server (server.py)
  3. Write / remove PID file
  4. Handle signals for clean shutdown
  5. Log startup diagnostics

Entry points:
  python -m apps.runtime.daemon start    # foreground (blocks)
  python -m apps.runtime.daemon status   # check if running
  python -m apps.runtime.daemon stop     # send SIGTERM to PID

Or via CLI:
  algenta runtime start
  algenta runtime stop
  algenta runtime status
"""

from __future__ import annotations

import asyncio
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import structlog

from apps.runtime.mojo_binary_freshness import inspect_mojo_binary_freshness
from apps.runtime.native_worker import resolve_native_worker
from apps.runtime.runtime_shards import (
    ShardMapError,
    ShardWorkerPool,
    load_runtime_shard_map,
    max_lazy_shard_workers,
)

logger = structlog.get_logger(__name__)

# ── Path config ───────────────────────────────────────────────────────────────

_RUNTIME_DIR = Path(os.environ.get("ALGENTA_RUNTIME_DIR", Path.home() / ".algenta" / "runtime"))
_PID_FILE = _RUNTIME_DIR / "daemon.pid"
_LOG_FILE = _RUNTIME_DIR / "daemon.log"
_TEMP_DIR = Path(tempfile.gettempdir())

# Bundled runtime worker executable. ALGENTA_MOJO_BINARY remains as a legacy dev override.
_REPO_ROOT = Path(__file__).parent.parent.parent
_RESOLVED_WORKER = resolve_native_worker(require_verified=False)
_MOJO_BINARY = Path(
    os.environ.get(
        "ALGENTA_NATIVE_WORKER",
        os.environ.get(
            "ALGENTA_RUNTIME_WORKER",
            os.environ.get(
                "ALGENTA_MOJO_BINARY",
                str(
                    _RESOLVED_WORKER.path
                    if _RESOLVED_WORKER
                    else _REPO_ROOT / "mojo_build" / "simulate"
                ),
            ),
        ),
    )
)
_MOJO_BINARY_SOURCE = _RESOLVED_WORKER.source if _RESOLVED_WORKER else "repo-dev runtime"
_MOJO_BINARY_VERIFIED = bool(_RESOLVED_WORKER and _RESOLVED_WORKER.verified)
_MOJO_SOCK = os.environ.get(
    "ALGENTA_MOJO_SOCK",
    str(_TEMP_DIR / "algenta-mojo" / "worker-0.sock"),
)

# gRPC daemon socket (consumed by SDK clients)
_DAEMON_SOCK = os.environ.get(
    "ALGENTA_DAEMON_SOCK",
    str(_TEMP_DIR / "algenta-runtime" / "daemon.sock"),
)
_DAEMON_TCP = os.environ.get("ALGENTA_DAEMON_TCP", "127.0.0.1:50099")

_VERSION = "0.1.0"


def _emit(message: str) -> None:
    """Write a user-facing daemon status line to stdout."""
    sys.stdout.write(f"{message}\n")


def _tcp_target_ready() -> bool:
    host, port = _DAEMON_TCP.rsplit(":", 1)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, int(port))) == 0


async def _daemon_health_ready() -> bool:
    from apps.runtime.client import DaemonClient

    client = DaemonClient(timeout=1.0)
    health = await client.health()
    return health.get("status") == "ok"


def _in_running_event_loop() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


def _detached_daemon_health_ready() -> bool:
    # Async callers such as the SDK perform a second awaited health check after
    # cmd_start(). In that path, socket or TCP readiness is enough here and
    # avoids calling asyncio.run() from an active event loop.
    if _in_running_event_loop():
        return True

    health_probe = _daemon_health_ready()
    try:
        return asyncio.run(health_probe)
    except Exception:
        health_probe.close()
        return False


def _wait_for_detached_daemon_ready(timeout_seconds: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not is_running():
            time.sleep(0.05)
            continue
        if Path(_DAEMON_SOCK).exists() or _tcp_target_ready():
            if _detached_daemon_health_ready():
                return True
        time.sleep(0.1)
    return False


def _require_verified_native_worker() -> bool:
    """Production hardening flag: boot ONLY with the verified, signed native worker. Default OFF so
    self-host/dev (locally-built or repo-dev workers) are unaffected; a production deployment sets
    it so license enforcement can't be run in a patched Python-only process without the signed
    native runtime — the 'native-daemon-only verification' guarantee."""
    return (os.environ.get("ALGENTA_REQUIRE_VERIFIED_NATIVE_WORKER", "").strip().lower()
            in {"1", "true", "yes", "on"})


def _validate_daemon_startup_prerequisites() -> None:
    from apps.privacy_policy import policy_from_environment
    from apps.runtime.license import load_license

    # Native-daemon verification (before anything else): in a hardened production deployment the
    # runtime must be the verified, signed native worker — refuse to start on an unverified/patched
    # runtime so the license gate below can't be bypassed by swapping in a dev/Python-only process.
    if _require_verified_native_worker() and not _MOJO_BINARY_VERIFIED:
        raise RuntimeError(
            "ALGENTA_REQUIRE_VERIFIED_NATIVE_WORKER=1 but the resolved native worker is unverified "
            f"(source={_MOJO_BINARY_SOURCE!r}); refusing to start — install the signed native worker."
        )

    privacy_policy = policy_from_environment()
    # P5: gate on EITHER the require_local_license profile OR the (default-OFF)
    # enforce_license_validation opt-in, so flipping enforce ON later makes the daemon fail
    # closed too — not just the credits path. Both default OFF → returns early, unchanged.
    if not privacy_policy.require_local_license and not privacy_policy.enforce_license_validation:
        return

    api_key = os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "")
    license_record = load_license(api_key)
    if not license_record.valid:
        raise RuntimeError(
            license_record.message
            or "A valid local signed license is required before starting the runtime daemon."
        )

    # Offline node-cap L1: a device-bound self-host license may run only on its bound node.
    # Fail closed at boot (air-gap-safe, no network). Enforcing is True here, after
    # the dark predicate returned early above. The L2 peer census (shared-Redis
    # clusters) runs later in RuntimeServer.start().
    from apps.runtime import node_broker

    node_broker.assert_node_binding(license_record, enforcing=True)
    # Deployment (server) scope: the local Compute-Unit ceiling for a pinned single-node
    # deployment — a node bigger than the whole purchased pool can never boot. No-op for
    # personal-device licenses. The distributed pool sum (floating pool) is the L3/Relay path.
    node_broker.assert_deployment_capacity(license_record, enforcing=True)
    # Device (desktop) scope: refuse a desktop license running on server-class hardware and point
    # to a Server/Enterprise license. No-op for deployment scope or a license with no vCPU ceiling.
    # DARK-first — observe-only (logs) until ALGENTA_ENFORCE_DEVICE_VCPU is set, since wrongly
    # refusing a paying desktop user on a big workstation would brick them.
    node_broker.assert_device_capacity(
        license_record, enforcing=node_broker.device_vcpu_enforcing()
    )


# ── Mojo process manager ──────────────────────────────────────────────────────


class MojoProcess:
    """
    Manages the lifecycle of the Mojo binary subprocess in server mode.
    The binary listens on a unix socket and handles execution requests.
    """

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None  # type: ignore[type-arg]

    def start(self) -> bool:
        """Start the Mojo binary. Returns False only when the binary is absent."""
        freshness = inspect_mojo_binary_freshness(_MOJO_BINARY)
        if not freshness.exists:
            logger.warning(
                "mojo_binary_not_found",
                path=str(_MOJO_BINARY),
                hint=(
                    "Install an Algenta build that includes the bundled runtime "
                    "for this platform."
                ),
            )
            return False
        if not _MOJO_BINARY_VERIFIED and not freshness.is_fresh:
            raise RuntimeError(freshness.failure_message())

        # Ensure socket directory exists
        Path(_MOJO_SOCK).parent.mkdir(parents=True, exist_ok=True)

        # Remove stale socket
        sock = Path(_MOJO_SOCK)
        if sock.exists():
            sock.unlink()

        self._proc = subprocess.Popen(  # noqa: S603
            [str(_MOJO_BINARY), "--server", _MOJO_SOCK],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        logger.info(
            "runtime_worker_started",
            pid=self._proc.pid,
            sock=_MOJO_SOCK,
            source=_MOJO_BINARY_SOURCE,
        )
        return True

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            logger.info("runtime_worker_stopped", pid=self._proc.pid)
        self._proc = None

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def wait_ready(self, timeout: float = 5.0) -> bool:
        """Poll until the Mojo socket appears (binary is ready to accept connections)."""
        deadline = time.monotonic() + timeout
        sock = Path(_MOJO_SOCK)
        while time.monotonic() < deadline:
            if sock.exists():
                return True
            time.sleep(0.05)
        return False


# ── PID management ────────────────────────────────────────────────────────────


def _write_pid() -> None:
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(os.getpid()))


def _remove_pid() -> None:
    try:
        _PID_FILE.unlink(missing_ok=True)
    except Exception as exc:
        logger.debug("pid_file_remove_failed", path=str(_PID_FILE), error=str(exc))


def read_pid() -> int | None:
    try:
        return int(_PID_FILE.read_text().strip())
    except Exception:
        return None


def is_running() -> bool:
    pid = read_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, 0)  # signal 0 = existence check
        return True
    except (ProcessLookupError, PermissionError):
        return False


# ── Main daemon loop ──────────────────────────────────────────────────────────


def _autoconfigure_bundle_runtime() -> None:
    """Zero-setup wiring when the daemon runs from the managed runtime BUNDLE.

    The bundle (scripts/build_runtime_bundle.py) ships, next to the sharded precompiled
    workers, a baked runtime-library inventory and a trimmed CPython home — but no Mojo
    toolchain and no .mojo source. When that layout is detected (runtime-shards.json AND
    runtime_library_inventory.json next to the resolved worker) the library plane is pointed
    at the baked inventory + precompiled-worker mode, and the worker's embedded CPython is
    pointed at the bundled stdlib, so the runtime works with no toolchain and no checkout.
    In the full workspace or an installed wheel none of these file pairs exist next to the
    worker, so this is a no-op and behavior is unchanged.
    """
    engine_dir = _MOJO_BINARY.resolve().parent
    shard_map = engine_dir / "runtime-shards.json"
    inventory = engine_dir / "runtime_library_inventory.json"
    if not (shard_map.is_file() and inventory.is_file()):
        return
    os.environ.setdefault("ALGENTA_RUNTIME_LIBRARY_INVENTORY", str(inventory))
    os.environ.setdefault("ALGENTA_RUNTIME_LIBRARY_PRECOMPILED", "1")

    # The workers embed CPython; on a clean machine the stdlib home is the bundle's own
    # trimmed copy (<bundle-root>/python/lib/pythonX.Y). Point PYTHONHOME + the Mojo
    # python-library override at the bundle so Py_Initialize finds it without any
    # system interpreter. MOJO_PYTHON_LIBRARY targets the libpython staged next to the
    # workers (the staging script relinks them to loader-relative paths).
    bundle_root = engine_dir.parent
    python_prefix = bundle_root / "python"
    if os.environ.get("PYTHONHOME") is None:
        lib_dir = python_prefix / "lib"
        if lib_dir.is_dir():
            homes = sorted(
                entry for entry in lib_dir.iterdir()
                if entry.is_dir() and entry.name.startswith("python3.")
            )
            if homes and (homes[0] / "os.py").is_file():
                os.environ["PYTHONHOME"] = str(python_prefix)
    if os.environ.get("MOJO_PYTHON_LIBRARY") is None:
        for pattern in ("libpython3*.so*", "libpython3*.dylib"):
            candidates = sorted(engine_dir.glob(pattern))
            if candidates:
                os.environ["MOJO_PYTHON_LIBRARY"] = str(candidates[0])
                break
    logger.info(
        "bundle_runtime_autoconfigured",
        engine_dir=str(engine_dir),
        pythonhome=os.environ.get("PYTHONHOME"),
    )


def _build_shard_pool() -> ShardWorkerPool | None:
    """A shard worker pool when a VALID runtime-shards.json sits next to the worker.

    Returns None — silently falling back to the historical single-worker path —
    when there is no shard map (dev builds, env-override workers, repo-dev
    binaries) or when the map is invalid (logged; the daemon must not refuse to
    boot over a bad map, it just loses per-module routing).
    """
    engine_dir = _MOJO_BINARY.resolve().parent
    try:
        shard_map = load_runtime_shard_map(engine_dir)
    except ShardMapError as exc:
        logger.warning(
            "runtime_shard_map_invalid_falling_back_to_single_worker",
            path=str(engine_dir / "runtime-shards.json"),
            error=str(exc),
        )
        return None
    if shard_map is None:
        return None
    return ShardWorkerPool(
        shard_map,
        engine_dir,
        _MOJO_SOCK,
        worker_source=_MOJO_BINARY_SOURCE,
        verified=_MOJO_BINARY_VERIFIED,
        max_lazy_workers=max_lazy_shard_workers(),
    )


async def _run_daemon() -> None:
    _autoconfigure_bundle_runtime()

    from apps.runtime.executor import Executor
    from apps.runtime.metering import metering
    from apps.runtime.mojo_library_runner import library_runtime_available
    from apps.runtime.server import RuntimeServer

    start_time = time.monotonic()
    _validate_daemon_startup_prerequisites()
    _write_pid()

    # Shard-aware mode: when a runtime-shards.json routes modules across shard
    # workers, the pool owns the eagerly-started default worker plus lazily
    # spawned shards. No map → the historical single MojoProcess, unchanged.
    shard_pool = _build_shard_pool()
    mojo: MojoProcess | None = None
    if shard_pool is not None:
        mojo_started = shard_pool.start_default()
        logger.info(
            "runtime_shard_pool_configured",
            default_worker=shard_pool.shard_map.default_worker,
            shard_count=shard_pool.shard_map.shard_count,
            module_count=len(shard_pool.shard_map.module_workers),
            max_lazy_workers=max_lazy_shard_workers(),
        )
    else:
        mojo = MojoProcess()
        mojo_started = mojo.start()
    if mojo_started:
        ready = (
            shard_pool.wait_default_ready(timeout=8.0)
            if shard_pool is not None
            else mojo.wait_ready(timeout=8.0)
        )
        if ready:
            logger.info("runtime_worker_ready", sock=_MOJO_SOCK)
        else:
            logger.warning("runtime_worker_socket_not_ready", timeout=8.0)
    else:
        logger.info("runtime_worker_unavailable_runtime_continues")

    executor = Executor(mojo_sock=_MOJO_SOCK, shard_pool=shard_pool)
    server = RuntimeServer(executor=executor, start_time=start_time)
    await server.start()

    # Start async metering flusher
    loop = asyncio.get_event_loop()
    metering.start_background_flush(loop)

    # Shutdown handler
    shutdown_event = asyncio.Event()

    def _handle_signal(sig: int) -> None:
        logger.info("shutdown_signal", sig=sig)
        shutdown_event.set()

    loop.add_signal_handler(signal.SIGTERM, _handle_signal, signal.SIGTERM)
    loop.add_signal_handler(signal.SIGINT, _handle_signal, signal.SIGINT)

    elapsed = round((time.monotonic() - start_time) * 1000, 1)
    runtime_mode = "worker" if mojo_started and library_runtime_available() else "unavailable"

    _emit(
        f"Algenta Runtime {_VERSION} started in {elapsed}ms  "
        f"[{runtime_mode}]  unix={_DAEMON_SOCK}  tcp={_DAEMON_TCP}"
    )

    # Block until signal
    await shutdown_event.wait()

    # Graceful shutdown
    metering.stop()
    await server.stop(grace=5.0)
    if shard_pool is not None:
        shard_pool.stop_all()
    if mojo is not None:
        mojo.stop()
    _remove_pid()
    logger.info("daemon_shutdown_complete")


# ── CLI entry points ──────────────────────────────────────────────────────────


def cmd_start(foreground: bool = True) -> None:
    """Start the daemon (blocking in foreground mode)."""
    if is_running():
        _emit(f"Algenta Runtime already running (pid={read_pid()})")
        return

    if not foreground:
        try:
            _validate_daemon_startup_prerequisites()
        except Exception as exc:
            _emit(f"Algenta Runtime failed to start: {exc}")
            return
        # Spawn detached subprocess
        _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        args = [sys.executable, "-m", "apps.runtime.daemon", "start"]
        with _LOG_FILE.open("a") as log_handle:
            proc = subprocess.Popen(  # noqa: S603
                args,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                cwd=str(_REPO_ROOT),
            )
        if _wait_for_detached_daemon_ready():
            _emit(f"Algenta Runtime started (pid={proc.pid})")
        else:
            _emit(f"Algenta Runtime failed to start; check logs: {_LOG_FILE}")
        return

    asyncio.run(_run_daemon())


def cmd_stop() -> None:
    """Stop the running daemon."""
    pid = read_pid()
    if pid is None or not is_running():
        _emit("Algenta Runtime is not running.")
        return
    os.kill(pid, signal.SIGTERM)
    # Wait for pid file to be removed
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if not is_running():
            _emit("Algenta Runtime stopped.")
            return
        time.sleep(0.1)
    _emit("Algenta Runtime did not stop cleanly; sending SIGKILL.")
    os.kill(pid, signal.SIGKILL)
    _remove_pid()


def cmd_status() -> None:
    """Print runtime status."""
    if is_running():
        pid = read_pid()
        sock_ok = Path(_DAEMON_SOCK).exists()
        mojo_ok = Path(_MOJO_SOCK).exists()
        _emit(
            f"Algenta Runtime running (pid={pid})\n"
            f"  gRPC unix socket: {_DAEMON_SOCK}  ({'ok' if sock_ok else 'missing'})\n"
            f"  Runtime worker socket: {_MOJO_SOCK}  ({'ok' if mojo_ok else 'not present'})\n"
            f"  TCP:              {_DAEMON_TCP}"
        )
    else:
        _emit("Algenta Runtime is not running.")
        _emit("  Start with: algenta runtime start")


# ── __main__ ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    if cmd == "start":
        cmd_start(foreground=True)
    elif cmd == "stop":
        cmd_stop()
    elif cmd == "status":
        cmd_status()
    else:
        _emit(f"Unknown command: {cmd}. Use: start | stop | status")
        sys.exit(1)
