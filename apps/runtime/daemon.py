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

logger = structlog.get_logger(__name__)

# ── Path config ───────────────────────────────────────────────────────────────

_RUNTIME_DIR = Path(os.environ.get("ALGENTA_RUNTIME_DIR", Path.home() / ".algenta" / "runtime"))
_PID_FILE = _RUNTIME_DIR / "daemon.pid"
_LOG_FILE = _RUNTIME_DIR / "daemon.log"
_TEMP_DIR = Path(tempfile.gettempdir())

# Mojo binary
_REPO_ROOT = Path(__file__).parent.parent.parent
_MOJO_BINARY = Path(os.environ.get("ALGENTA_MOJO_BINARY", _REPO_ROOT / "mojo_build" / "simulate"))
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


def _validate_daemon_startup_prerequisites() -> None:
    from apps.runtime.license import load_license
    from apps.privacy_policy import policy_from_environment

    privacy_policy = policy_from_environment()
    if not privacy_policy.require_local_license:
        return

    api_key = os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "")
    license_record = load_license(api_key)
    if not license_record.valid:
        raise RuntimeError(
            license_record.message
            or "A valid local signed license is required before starting the runtime daemon."
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
        """Start the Mojo binary. Returns True if started, False if binary not found."""
        if not _MOJO_BINARY.exists():
            logger.warning(
                "mojo_binary_not_found",
                path=str(_MOJO_BINARY),
                hint=(
                    "Run: cd mojo_env && pixi run mojo build "
                    "../mojo/engine/main.mojo -o ../mojo_build/simulate"
                ),
            )
            return False

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
        logger.info("mojo_process_started", pid=self._proc.pid, sock=_MOJO_SOCK)
        return True

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            logger.info("mojo_process_stopped", pid=self._proc.pid)
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


async def _run_daemon() -> None:
    from apps.runtime.executor import Executor
    from apps.runtime.metering import metering
    from apps.runtime.mojo_library_runner import library_runtime_available
    from apps.runtime.server import RuntimeServer

    start_time = time.monotonic()
    _validate_daemon_startup_prerequisites()
    _write_pid()

    mojo = MojoProcess()
    mojo_started = mojo.start()
    if mojo_started:
        ready = mojo.wait_ready(timeout=8.0)
        if ready:
            logger.info("mojo_ready", sock=_MOJO_SOCK)
        else:
            logger.warning("mojo_socket_not_ready", timeout=8.0)
    else:
        logger.info("mojo_binary_unavailable_runtime_continues")

    executor = Executor(mojo_sock=_MOJO_SOCK)
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
    runtime_mode = "mojo" if mojo_started and library_runtime_available() else "unavailable"

    _emit(
        f"Algenta Runtime {_VERSION} started in {elapsed}ms  "
        f"[{runtime_mode}]  unix={_DAEMON_SOCK}  tcp={_DAEMON_TCP}"
    )

    # Block until signal
    await shutdown_event.wait()

    # Graceful shutdown
    metering.stop()
    await server.stop(grace=5.0)
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
            f"  Mojo unix socket: {_MOJO_SOCK}  ({'ok' if mojo_ok else 'not present'})\n"
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
