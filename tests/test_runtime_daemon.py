from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import apps.runtime.daemon as daemon
from apps.runtime import runtime_shards
from apps.runtime.executor import Executor, _mojo_call


def test_daemon_startup_prereqs_noop_by_default(monkeypatch) -> None:
    # P5: require_local_license OFF + enforce_license_validation OFF (defaults) → the daemon
    # starts with no license required, exactly as today (no load_license call).
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_ENFORCE_LICENSE_VALIDATION", raising=False)
    monkeypatch.delenv("ALGENTA_REQUIRE_LOCAL_LICENSE", raising=False)
    with patch("apps.runtime.license.load_license") as mocked:
        daemon._validate_daemon_startup_prerequisites()
    mocked.assert_not_called()


def test_daemon_startup_prereqs_enforced_when_flag_on(monkeypatch) -> None:
    # P5: opting into enforce_license_validation makes the daemon fail closed without a valid
    # license — even though require_local_license is still OFF.
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_ENFORCE_LICENSE_VALIDATION", "1")
    monkeypatch.delenv("ALGENTA_REQUIRE_LOCAL_LICENSE", raising=False)
    invalid = SimpleNamespace(valid=False, message="license required")
    with patch("apps.runtime.license.load_license", return_value=invalid):
        with pytest.raises(RuntimeError):
            daemon._validate_daemon_startup_prerequisites()
    valid = SimpleNamespace(valid=True, message="")
    with patch("apps.runtime.license.load_license", return_value=valid):
        daemon._validate_daemon_startup_prerequisites()  # valid license → no raise


def test_wait_for_detached_daemon_ready_retries_until_health_ok(monkeypatch) -> None:
    health_results = iter([False, True])
    monotonic_values = iter([0.0, 0.0, 0.1, 0.2])
    sleep_calls: list[float] = []

    monkeypatch.setattr(daemon, "is_running", lambda: True)
    monkeypatch.setattr(daemon, "_tcp_target_ready", lambda: False)
    monkeypatch.setattr(Path, "exists", lambda self: True)

    def _fake_asyncio_run(coro):
        coro.close()
        return next(health_results)

    monkeypatch.setattr(daemon.asyncio, "run", _fake_asyncio_run)
    monkeypatch.setattr(daemon.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(daemon.time, "sleep", lambda delay: sleep_calls.append(delay))

    assert daemon._wait_for_detached_daemon_ready(timeout_seconds=1.0) is True
    assert sleep_calls == [0.1]


def test_wait_for_detached_daemon_ready_uses_socket_probe_inside_running_event_loop(
    monkeypatch,
) -> None:
    monotonic_values = iter([0.0, 0.0])

    monkeypatch.setattr(daemon, "is_running", lambda: True)
    monkeypatch.setattr(daemon, "_tcp_target_ready", lambda: False)
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(daemon.asyncio, "get_running_loop", lambda: object())
    monkeypatch.setattr(
        daemon.asyncio,
        "run",
        lambda coro: (_ for _ in ()).throw(AssertionError("asyncio.run should not execute")),
    )
    monkeypatch.setattr(daemon.time, "monotonic", lambda: next(monotonic_values))

    assert daemon._wait_for_detached_daemon_ready(timeout_seconds=1.0) is True


def test_cmd_start_detached_emits_success_after_real_readiness_probe(
    monkeypatch, tmp_path: Path
) -> None:
    emitted: list[str] = []
    log_path = tmp_path / "daemon.log"

    monkeypatch.setattr(daemon, "is_running", lambda: False)
    monkeypatch.setattr(daemon, "_wait_for_detached_daemon_ready", lambda timeout_seconds=10.0: True)
    monkeypatch.setattr(daemon, "_emit", emitted.append)
    monkeypatch.setattr(daemon, "_RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(daemon, "_LOG_FILE", log_path)
    monkeypatch.setattr(daemon.subprocess, "Popen", lambda *args, **kwargs: SimpleNamespace(pid=43210))

    daemon.cmd_start(foreground=False)

    assert emitted == ["Algenta Runtime started (pid=43210)"]


def test_cmd_start_detached_emits_failure_when_daemon_never_becomes_ready(
    monkeypatch, tmp_path: Path
) -> None:
    emitted: list[str] = []
    log_path = tmp_path / "daemon.log"

    monkeypatch.setattr(daemon, "is_running", lambda: False)
    monkeypatch.setattr(daemon, "_wait_for_detached_daemon_ready", lambda timeout_seconds=10.0: False)
    monkeypatch.setattr(daemon, "_emit", emitted.append)
    monkeypatch.setattr(daemon, "_RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(daemon, "_LOG_FILE", log_path)
    monkeypatch.setattr(daemon.subprocess, "Popen", lambda *args, **kwargs: SimpleNamespace(pid=54321))

    daemon.cmd_start(foreground=False)

    assert emitted == [f"Algenta Runtime failed to start; check logs: {log_path}"]


def test_cmd_status_reports_configured_tcp_target(monkeypatch, tmp_path: Path) -> None:
    daemon_sock = tmp_path / "daemon.sock"
    daemon_sock.touch()
    emitted: list[str] = []

    monkeypatch.setattr(daemon, "is_running", lambda: True)
    monkeypatch.setattr(daemon, "read_pid", lambda: 24680)
    monkeypatch.setattr(daemon, "_DAEMON_SOCK", str(daemon_sock))
    monkeypatch.setattr(daemon, "_MOJO_SOCK", str(tmp_path / "mojo.sock"))
    monkeypatch.setattr(daemon, "_DAEMON_TCP", "127.0.0.1:51234")
    monkeypatch.setattr(daemon, "_emit", emitted.append)

    daemon.cmd_status()

    assert emitted == [
        "Algenta Runtime running (pid=24680)\n"
        f"  gRPC unix socket: {daemon_sock}  (ok)\n"
        f"  Runtime worker socket: {tmp_path / 'mojo.sock'}  (not present)\n"
        "  TCP:              127.0.0.1:51234"
    ]


def test_cmd_start_detached_fails_fast_when_local_license_is_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    emitted: list[str] = []
    invalid_license = SimpleNamespace(valid=False, message="offline license missing")

    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")
    monkeypatch.setattr(daemon, "is_running", lambda: False)
    monkeypatch.setattr(daemon, "_emit", emitted.append)

    with (
        patch("apps.runtime.license.load_license", return_value=invalid_license),
        patch.object(
            daemon.subprocess,
            "Popen",
            side_effect=AssertionError("detached start must not spawn when validation fails"),
        ),
    ):
        daemon.cmd_start(foreground=False)

    assert emitted == ["Algenta Runtime failed to start: offline license missing"]


@pytest.mark.anyio
async def test_run_daemon_requires_local_license_before_pid_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    invalid_license = SimpleNamespace(valid=False, message="offline license missing")

    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")

    with (
        patch("apps.runtime.license.load_license", return_value=invalid_license),
        patch.object(
            daemon,
            "_write_pid",
            side_effect=AssertionError("pid must not be written before license validation"),
        ),
    ):
        with pytest.raises(RuntimeError, match="offline license missing"):
            await daemon._run_daemon()


# ── Shard-aware daemon ────────────────────────────────────────────────────────
#
# The managed runtime ships as sharded workers (runtime-shards.json: module →
# owning worker). These tests run the daemon's shard machinery against FAKE
# worker executables that speak the real length-prefixed JSON socket protocol
# (ready handshake, one response per framed request) — the same wire grammar
# the compiled Mojo workers use — so routing / lazy spawn / eviction / health
# are covered without building any real shard set. The CI pattern of compiling
# small FILTERED shards stays with the dispatch-server suite; nothing here
# builds 27 workers.

DEFAULT_WORKER = "algenta-runtime-worker"
SHARD_WORKER_001 = "algenta-runtime-worker-001"
SHARD_WORKER_002 = "algenta-runtime-worker-002"

FAKE_WORKER_SOURCE = '''\
import json
import os
import socket
import struct
import sys


def send_frame(conn, payload):
    data = json.dumps(payload).encode("utf-8")
    conn.sendall(struct.pack(">I", len(data)) + data)


def recv_frame(conn):
    header = b""
    while len(header) < 4:
        chunk = conn.recv(4 - len(header))
        if not chunk:
            return None
        header += chunk
    (length,) = struct.unpack(">I", header)
    body = b""
    while len(body) < length:
        chunk = conn.recv(length - len(body))
        if not chunk:
            return None
        body += chunk
    return json.loads(body.decode("utf-8"))


def main():
    worker_name = os.path.basename(sys.argv[0])
    sock_path = sys.argv[sys.argv.index("--server") + 1]
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(sock_path)
    server.listen(8)
    while True:
        conn, _ = server.accept()
        shutdown_requested = False
        try:
            send_frame(conn, {"status": "ready"})
            while True:
                request = recv_frame(conn)
                if request is None:
                    break
                if request.get("type") == "shutdown":
                    send_frame(conn, {"status": "bye"})
                    shutdown_requested = True
                    break
                send_frame(conn, {
                    "result": worker_name,
                    "worker": worker_name,
                    "request": request,
                })
        finally:
            conn.close()
        if shutdown_requested:
            break


main()
'''


def _write_fake_worker(engine_dir: Path, worker_name: str) -> Path:
    binary = engine_dir / worker_name
    binary.write_text(f"#!{sys.executable}\n{FAKE_WORKER_SOURCE}", encoding="utf-8")
    binary.chmod(0o755)
    return binary


def _write_shard_map(
    engine_dir: Path,
    module_workers: dict[str, str],
    *,
    default_worker: str = DEFAULT_WORKER,
) -> Path:
    payload = {
        "schema_version": 1,
        "module_count": len(module_workers),
        "shard_count": len(set(module_workers.values())),
        "default_worker": default_worker,
        "module_workers": module_workers,
    }
    shard_map = engine_dir / "runtime-shards.json"
    shard_map.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return shard_map


def _make_engine(
    tmp_path: Path,
    module_workers: dict[str, str],
    *,
    workers: tuple[str, ...] = (DEFAULT_WORKER, SHARD_WORKER_001, SHARD_WORKER_002),
) -> Path:
    engine_dir = tmp_path / "engine"
    engine_dir.mkdir()
    for worker_name in workers:
        _write_fake_worker(engine_dir, worker_name)
    _write_shard_map(engine_dir, module_workers)
    return engine_dir


def _shard_sock_name(worker_name: str) -> str:
    # Mirrors ShardWorkerPool._sock_for: "...-NNN" → "worker-NNN.sock".
    return f"worker-{worker_name.rsplit('-', 1)[-1]}.sock"


@pytest.fixture
def sock_dir(tmp_path: Path):
    # macOS caps AF_UNIX paths at 104 bytes and pytest's tmp_path is already
    # deep; keep worker sockets in a short directory of their own.
    import shutil
    import tempfile

    short = Path(tempfile.mkdtemp(prefix="ash", dir="/tmp"))
    yield short
    shutil.rmtree(short, ignore_errors=True)


def _make_pool(
    engine_dir: Path,
    sock_dir: Path,
    *,
    max_lazy_workers: int = 4,
) -> tuple[runtime_shards.ShardWorkerPool, str]:
    shard_map = runtime_shards.load_runtime_shard_map(engine_dir)
    assert shard_map is not None
    default_sock = str(sock_dir / "worker-0.sock")
    pool = runtime_shards.ShardWorkerPool(
        shard_map,
        engine_dir,
        default_sock,
        worker_source="test-fixture",
        verified=False,
        max_lazy_workers=max_lazy_workers,
    )
    return pool, default_sock


@pytest.fixture
def engine(tmp_path: Path) -> Path:
    return _make_engine(
        tmp_path,
        {
            # The default shard's own modules route to the default worker...
            "default_mod.core": DEFAULT_WORKER,
            # ...and these two live on NON-default shards.
            "shard_alpha.kernels": SHARD_WORKER_001,
            "shard_beta.stats": SHARD_WORKER_002,
        },
    )


def test_load_runtime_shard_map_parses_valid_map(engine: Path) -> None:
    shard_map = runtime_shards.load_runtime_shard_map(engine)
    assert shard_map is not None
    assert shard_map.default_worker == DEFAULT_WORKER
    assert shard_map.shard_count == 3
    # Routing: listed modules hit their owning shard, everything else the default.
    assert shard_map.route("shard_alpha.kernels") == SHARD_WORKER_001
    assert shard_map.route("shard_beta.stats") == SHARD_WORKER_002
    assert shard_map.route("default_mod.core") == DEFAULT_WORKER
    assert shard_map.route("not.in.the.map") == DEFAULT_WORKER
    assert shard_map.route(None) == DEFAULT_WORKER


def test_load_runtime_shard_map_absent_returns_none(tmp_path: Path) -> None:
    assert runtime_shards.load_runtime_shard_map(tmp_path) is None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update(schema_version=2),
        lambda payload: payload.update(default_worker="../escape"),
        lambda payload: payload.update(module_workers={}),
        lambda payload: payload.update(module_workers={"bad module!": DEFAULT_WORKER}),
        lambda payload: payload.update(
            module_workers={"ok.module": "not-a-worker-name"}
        ),
        lambda payload: payload.update(module_count=999),
        lambda payload: payload.update(shard_count=999),
    ],
    ids=[
        "bad-schema-version",
        "bad-default-worker",
        "no-routes",
        "bad-module-name",
        "bad-worker-name",
        "inconsistent-module-count",
        "inconsistent-shard-count",
    ],
)
def test_load_runtime_shard_map_rejects_invalid_maps(
    tmp_path: Path,
    mutate,
) -> None:
    module_workers = {"default_mod.core": DEFAULT_WORKER}
    shard_map_path = _write_shard_map(tmp_path, module_workers)
    payload = json.loads(shard_map_path.read_text(encoding="utf-8"))
    mutate(payload)
    shard_map_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(runtime_shards.ShardMapError):
        runtime_shards.load_runtime_shard_map(tmp_path)


def test_build_shard_pool_falls_back_without_map(monkeypatch, tmp_path: Path) -> None:
    # No runtime-shards.json next to the worker → single-worker back-compat.
    fake_binary = tmp_path / DEFAULT_WORKER
    _write_fake_worker(tmp_path, DEFAULT_WORKER)
    monkeypatch.setattr(daemon, "_MOJO_BINARY", fake_binary)
    assert daemon._build_shard_pool() is None


def test_build_shard_pool_falls_back_on_invalid_map(monkeypatch, tmp_path: Path) -> None:
    # A corrupt map must not keep the daemon from booting — it degrades to the
    # historical single worker instead.
    fake_binary = tmp_path / DEFAULT_WORKER
    _write_fake_worker(tmp_path, DEFAULT_WORKER)
    (tmp_path / "runtime-shards.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(daemon, "_MOJO_BINARY", fake_binary)
    assert daemon._build_shard_pool() is None


def test_build_shard_pool_honors_worker_cap_env(monkeypatch, tmp_path: Path) -> None:
    engine_dir = _make_engine(
        tmp_path,
        {
            "default_mod.core": DEFAULT_WORKER,
            "shard_alpha.kernels": SHARD_WORKER_001,
        },
    )
    monkeypatch.setattr(daemon, "_MOJO_BINARY", engine_dir / DEFAULT_WORKER)
    monkeypatch.setenv("ALGENTA_RUNTIME_MAX_SHARD_WORKERS", "2")
    pool = daemon._build_shard_pool()
    assert pool is not None
    assert pool._max_lazy_workers == 2


@pytest.mark.anyio
async def test_pool_routes_module_to_owning_shard_worker(
    sock_dir: Path,
    engine: Path,
) -> None:
    pool, default_sock = _make_pool(engine, sock_dir)
    assert pool.start_default() is True
    assert pool.wait_default_ready(timeout=5.0) is True
    try:
        # A non-default-shard module lands on ITS shard's socket, and the fake
        # worker on the other end identifies itself as that shard binary.
        sock = await pool.acquire("shard_alpha.kernels")
        try:
            assert sock == str(sock_dir / _shard_sock_name(SHARD_WORKER_001))
            response = await _mojo_call(
                {"type": "library_execute", "module": "shard_alpha.kernels"}, sock
            )
            assert response["worker"] == SHARD_WORKER_001
        finally:
            pool.release("shard_alpha.kernels")

        # A default-shard module stays on the default socket/worker.
        sock = await pool.acquire("default_mod.core")
        try:
            assert sock == default_sock
            response = await _mojo_call(
                {"type": "library_execute", "module": "default_mod.core"}, sock
            )
            assert response["worker"] == DEFAULT_WORKER
        finally:
            pool.release("default_mod.core")

        # Unrouted modules fall back to the default worker (SDK parity).
        sock = await pool.acquire("not.in.the.map")
        try:
            assert sock == default_sock
        finally:
            pool.release("not.in.the.map")
    finally:
        pool.stop_all()


@pytest.mark.anyio
async def test_pool_spawns_shard_workers_lazily_and_caches_them(
    sock_dir: Path,
    engine: Path,
) -> None:
    pool, default_sock = _make_pool(engine, sock_dir)
    assert pool.start_default() is True
    assert pool.wait_default_ready(timeout=5.0) is True
    try:
        status = pool.status()
        assert status[DEFAULT_WORKER]["running"] is True
        # Nothing but the default worker is resident before the first request.
        assert set(status) == {DEFAULT_WORKER}
        assert not (sock_dir / _shard_sock_name(SHARD_WORKER_001)).exists()

        await pool.acquire("shard_alpha.kernels")
        pool.release("shard_alpha.kernels")
        status = pool.status()
        assert status[SHARD_WORKER_001]["running"] is True
        first_pid = status[SHARD_WORKER_001]["pid"]
        assert first_pid is not None

        # Second request reuses the cached worker — no respawn.
        await pool.acquire("shard_alpha.kernels")
        pool.release("shard_alpha.kernels")
        assert pool.status()[SHARD_WORKER_001]["pid"] == first_pid
    finally:
        pool.stop_all()


@pytest.mark.anyio
async def test_pool_lru_evicts_idle_shard_past_cap(sock_dir: Path, engine: Path) -> None:
    pool, _ = _make_pool(engine, sock_dir, max_lazy_workers=1)
    assert pool.start_default() is True
    assert pool.wait_default_ready(timeout=5.0) is True
    try:
        await pool.acquire("shard_alpha.kernels")
        pool.release("shard_alpha.kernels")
        first_alpha_pid = pool.status()[SHARD_WORKER_001]["pid"]

        # Cap is 1: bringing shard_beta in evicts the idle shard_alpha. (The
        # evicted worker's socket FILE lingers — stop() never unlinks, the next
        # start() does, same as the historical MojoProcess — so absence is
        # asserted on the resident-worker table, not the filesystem.)
        await pool.acquire("shard_beta.stats")
        pool.release("shard_beta.stats")
        status = pool.status()
        assert SHARD_WORKER_001 not in status
        assert status[SHARD_WORKER_002]["running"] is True

        # Re-acquiring the evicted shard respawns it (new pid).
        await pool.acquire("shard_alpha.kernels")
        pool.release("shard_alpha.kernels")
        status = pool.status()
        assert status[SHARD_WORKER_001]["running"] is True
        assert status[SHARD_WORKER_001]["pid"] != first_alpha_pid
    finally:
        pool.stop_all()


@pytest.mark.anyio
async def test_pool_never_evicts_default_worker(sock_dir: Path, engine: Path) -> None:
    pool, default_sock = _make_pool(engine, sock_dir, max_lazy_workers=1)
    assert pool.start_default() is True
    assert pool.wait_default_ready(timeout=5.0) is True
    try:
        default_pid = pool.status()[DEFAULT_WORKER]["pid"]
        await pool.acquire("shard_alpha.kernels")
        pool.release("shard_alpha.kernels")
        await pool.acquire("shard_beta.stats")
        pool.release("shard_beta.stats")
        # Even past the lazy cap the default worker is untouched.
        status = pool.status()
        assert status[DEFAULT_WORKER]["running"] is True
        assert status[DEFAULT_WORKER]["pid"] == default_pid
        assert status[DEFAULT_WORKER]["socket"] == default_sock
    finally:
        pool.stop_all()


@pytest.mark.anyio
async def test_pool_never_evicts_in_flight_shard(sock_dir: Path, engine: Path) -> None:
    pool, _ = _make_pool(engine, sock_dir, max_lazy_workers=1)
    assert pool.start_default() is True
    assert pool.wait_default_ready(timeout=5.0) is True
    try:
        # alpha stays in flight while beta arrives: nothing idle to evict, so
        # the cap is exceeded rather than killing a worker mid-request.
        await pool.acquire("shard_alpha.kernels")
        await pool.acquire("shard_beta.stats")
        status = pool.status()
        assert status[SHARD_WORKER_001]["running"] is True
        assert status[SHARD_WORKER_002]["running"] is True
        pool.release("shard_alpha.kernels")
        pool.release("shard_beta.stats")
    finally:
        pool.stop_all()


@pytest.mark.anyio
async def test_pool_revives_dead_worker_on_next_acquire(
    sock_dir: Path,
    engine: Path,
) -> None:
    pool, _ = _make_pool(engine, sock_dir)
    assert pool.start_default() is True
    assert pool.wait_default_ready(timeout=5.0) is True
    try:
        await pool.acquire("shard_alpha.kernels")
        pool.release("shard_alpha.kernels")
        first_pid = pool.status()[SHARD_WORKER_001]["pid"]

        # Kill the shard behind the pool's back (crash simulation). Reap via
        # the pool's own status (which polls the Popen) — never os.waitpid,
        # which would race the Popen's internal reaping.
        os.kill(first_pid, signal.SIGKILL)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if not pool.status()[SHARD_WORKER_001]["running"]:
                break
            time.sleep(0.05)
        assert pool.status()[SHARD_WORKER_001]["running"] is False

        # Next request transparently respawns it.
        sock = await pool.acquire("shard_alpha.kernels")
        try:
            response = await _mojo_call(
                {"type": "library_execute", "module": "shard_alpha.kernels"}, sock
            )
            assert response["worker"] == SHARD_WORKER_001
        finally:
            pool.release("shard_alpha.kernels")
        assert pool.status()[SHARD_WORKER_001]["pid"] != first_pid
    finally:
        pool.stop_all()


@pytest.mark.anyio
async def test_pool_missing_shard_binary_is_typed_unavailable(
    sock_dir: Path,
    engine: Path,
) -> None:
    (engine / SHARD_WORKER_002).unlink()  # shard_beta's binary is "not shipped"
    pool, _ = _make_pool(engine, sock_dir)
    assert pool.start_default() is True
    assert pool.wait_default_ready(timeout=5.0) is True
    try:
        with pytest.raises(runtime_shards.ShardWorkerUnavailable):
            await pool.acquire("shard_beta.stats")
    finally:
        pool.stop_all()


@pytest.mark.anyio
async def test_pool_health_reports_every_resident_worker(
    sock_dir: Path,
    engine: Path,
) -> None:
    pool, default_sock = _make_pool(engine, sock_dir)
    assert pool.start_default() is True
    assert pool.wait_default_ready(timeout=5.0) is True
    try:
        await pool.acquire("shard_alpha.kernels")
        await pool.acquire("shard_beta.stats")

        status = pool.status()
        assert set(status) == {DEFAULT_WORKER, SHARD_WORKER_001, SHARD_WORKER_002}
        assert status[DEFAULT_WORKER]["default"] is True
        assert status[DEFAULT_WORKER]["socket"] == default_sock
        for worker_name in (SHARD_WORKER_001, SHARD_WORKER_002):
            assert status[worker_name]["default"] is False
            assert status[worker_name]["running"] is True
            assert status[worker_name]["pid"]
            assert status[worker_name]["in_flight"] == 1
        pool.release("shard_alpha.kernels")
        pool.release("shard_beta.stats")
        assert pool.status()[SHARD_WORKER_001]["in_flight"] == 0

        pool.stop_all()
        status = pool.status()
        assert status[DEFAULT_WORKER]["running"] is False
        assert set(status) == {DEFAULT_WORKER}  # lazy workers dropped on shutdown
    finally:
        pool.stop_all()


def _patch_executor_plumbing(monkeypatch, tmp_path: Path) -> None:
    """Credits + ledger isolation and pass-through spec handling for the
    executor-level routing tests (the subject under test is WHICH worker serves
    the request, not the inventory-driven request building)."""
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime-state"))
    monkeypatch.setattr(
        "apps.runtime.credits.consume_credit", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(
        "apps.runtime.executor.build_runtime_library_worker_request",
        lambda module, function, args: (
            None,
            {
                "type": "library_execute",
                "engine_type": "library_execute",
                "module": module,
                "function": function,
                "args": args,
            },
        ),
    )
    monkeypatch.setattr(
        "apps.runtime.executor.parse_runtime_library_worker_response",
        lambda module, function, response, function_spec=None: response,
    )


@pytest.mark.anyio
async def test_executor_routes_library_execute_to_owning_shard(
    monkeypatch,
    tmp_path: Path,
    sock_dir: Path,
    engine: Path,
) -> None:
    _patch_executor_plumbing(monkeypatch, tmp_path)
    pool, default_sock = _make_pool(engine, sock_dir)
    assert pool.start_default() is True
    assert pool.wait_default_ready(timeout=5.0) is True
    try:
        executor = Executor(mojo_sock=default_sock, shard_pool=pool)

        # Non-default-shard module → served by shard worker 001.
        result = await executor.execute_module(
            "shard_alpha.kernels", "compute", [1, 2], request_id="shard-route"
        )
        assert result["success"] is True, result["error"]
        assert json.loads(result["result_json"])["worker"] == SHARD_WORKER_001

        # Default-shard module → served by the default worker.
        result = await executor.execute_module(
            "default_mod.core", "compute", [], request_id="default-route"
        )
        assert result["success"] is True, result["error"]
        assert json.loads(result["result_json"])["worker"] == DEFAULT_WORKER

        # Simulation engines always run on the default shard, even with a pool.
        # The sim branch returns raw["result"] — the fake worker echoes its own
        # name there — so the payload is the bare worker-name string.
        result = await executor.execute_module(
            "monte_carlo", "run", {"trials": 1}, request_id="sim-route"
        )
        assert result["success"] is True, result["error"]
        assert json.loads(result["result_json"]) == DEFAULT_WORKER
    finally:
        pool.stop_all()


@pytest.mark.anyio
async def test_executor_without_pool_keeps_single_worker_path(
    monkeypatch,
    tmp_path: Path,
    sock_dir: Path,
) -> None:
    # Back-compat: no shard map → the historical single socket, byte for byte.
    _patch_executor_plumbing(monkeypatch, tmp_path)
    engine_dir = tmp_path / "engine"
    engine_dir.mkdir()
    _write_fake_worker(engine_dir, DEFAULT_WORKER)
    sock = str(sock_dir / "worker-0.sock")

    worker = runtime_shards.ShardWorkerProcess(
        name=DEFAULT_WORKER,
        binary=engine_dir / DEFAULT_WORKER,
        sock=sock,
        source="test-fixture",
        verified=False,
    )
    assert worker.start() is True
    assert worker.wait_ready(timeout=5.0) is True
    try:
        executor = Executor(mojo_sock=sock)  # no shard_pool
        result = await executor.execute_module(
            "shard_alpha.kernels", "compute", [1], request_id="single-worker"
        )
        assert result["success"] is True, result["error"]
        assert json.loads(result["result_json"])["worker"] == DEFAULT_WORKER
    finally:
        worker.stop()


@pytest.mark.anyio
async def test_executor_reports_typed_error_when_shard_missing(
    monkeypatch,
    tmp_path: Path,
    sock_dir: Path,
    engine: Path,
) -> None:
    _patch_executor_plumbing(monkeypatch, tmp_path)
    (engine / SHARD_WORKER_002).unlink()
    pool, default_sock = _make_pool(engine, sock_dir)
    assert pool.start_default() is True
    assert pool.wait_default_ready(timeout=5.0) is True
    try:
        executor = Executor(mojo_sock=default_sock, shard_pool=pool)
        result = await executor.execute_module(
            "shard_beta.stats", "compute", [], request_id="missing-shard"
        )
        assert result["success"] is False
        assert result["engine_used"] == "unavailable"
        assert result["error"].startswith("compute_runtime_unavailable")
        assert SHARD_WORKER_002 in result["error"]
    finally:
        pool.stop_all()
