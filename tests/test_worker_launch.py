"""apps/runtime/worker_launch.py — the vetting that sits between operator env vars and the
worker's argv in daemon.py: override precedence, launch-time executable checks (absolute, regular
file, executable bit) and the unix-socket path shape. Plus the integration on BOTH spawn paths —
daemon.MojoProcess (no shard map) and runtime_shards.ShardWorkerProcess (the ShardWorkerPool path
_run_daemon takes when runtime-shards.json sits beside the binary): a worker path or socket path
that fails vetting is refused before anything is spawned or unlinked.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import socket
import stat
import sys
import tempfile
from pathlib import Path

import pytest

from apps.runtime import daemon, runtime_shards, worker_launch
from apps.runtime.native_worker import NativeWorkerUnavailable
from apps.runtime.worker_launch import (
    WORKER_OVERRIDE_ENV_VARS,
    WORKER_SOCKET_ENV_VAR,
    launchable_worker_executable,
    launchable_worker_socket,
    worker_override_path,
    worker_socket_path,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch):
    for var in (*WORKER_OVERRIDE_ENV_VARS, WORKER_SOCKET_ENV_VAR):
        monkeypatch.delenv(var, raising=False)
    yield


@pytest.fixture
def short_dir():
    """A SHORT scratch dir: pytest's tmp_path on macOS is far longer than sun_path allows, so
    socket-path tests anchor under /tmp instead (cleaned up afterwards)."""
    path = Path(tempfile.mkdtemp(prefix="wl-", dir="/tmp"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _executable(path: Path) -> Path:
    path.write_text(f"#!{sys.executable}\nraise SystemExit(0)\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


# ── override precedence ──────────────────────────────────────────────────────────


def test_no_override_when_nothing_is_set() -> None:
    assert worker_override_path() is None


@pytest.mark.parametrize("var", WORKER_OVERRIDE_ENV_VARS)
def test_each_override_var_is_honoured(monkeypatch, var: str, tmp_path: Path) -> None:
    monkeypatch.setenv(var, str(tmp_path / "worker"))
    assert worker_override_path() == tmp_path / "worker"


def test_precedence_is_native_then_runtime_then_legacy(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ALGENTA_MOJO_BINARY", str(tmp_path / "legacy"))
    monkeypatch.setenv("ALGENTA_RUNTIME_WORKER", str(tmp_path / "runtime"))
    assert worker_override_path() == tmp_path / "runtime"
    monkeypatch.setenv("ALGENTA_NATIVE_WORKER", str(tmp_path / "native"))
    assert worker_override_path() == tmp_path / "native"


def test_empty_override_counts_as_unset(monkeypatch, tmp_path: Path) -> None:
    # Previously an empty ALGENTA_NATIVE_WORKER resolved to Path("") — the current directory.
    monkeypatch.setenv("ALGENTA_NATIVE_WORKER", "   ")
    monkeypatch.setenv("ALGENTA_MOJO_BINARY", str(tmp_path / "legacy"))
    assert worker_override_path() == tmp_path / "legacy"


# ── launch-time executable vetting ───────────────────────────────────────────────


def test_accepts_an_absolute_executable_regular_file(tmp_path: Path) -> None:
    worker = _executable(tmp_path / "simulate")
    assert launchable_worker_executable(worker) == worker
    assert launchable_worker_executable(str(worker)) == worker


def test_rejects_a_relative_path_even_if_it_would_resolve(tmp_path: Path, monkeypatch) -> None:
    _executable(tmp_path / "simulate")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(NativeWorkerUnavailable, match="absolute"):
        launchable_worker_executable(Path("simulate"))
    with pytest.raises(NativeWorkerUnavailable, match="absolute"):
        launchable_worker_executable("./simulate")


def test_rejects_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(NativeWorkerUnavailable, match="not a regular file"):
        launchable_worker_executable(tmp_path / "nope")


def test_rejects_a_directory(tmp_path: Path) -> None:
    with pytest.raises(NativeWorkerUnavailable, match="not a regular file"):
        launchable_worker_executable(tmp_path)


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX executable bit")
def test_rejects_a_non_executable_file(tmp_path: Path) -> None:
    blob = tmp_path / "simulate"
    blob.write_bytes(b"\x7fELF not really")
    blob.chmod(0o644)
    if os.access(blob, os.X_OK):  # running as root: every file is executable
        pytest.skip("os.access reports X_OK for everything under this uid")
    with pytest.raises(NativeWorkerUnavailable, match="not executable"):
        launchable_worker_executable(blob)


# ── socket path: resolution (import-safe) ────────────────────────────────────────


def test_socket_defaults_when_unset(short_dir: Path) -> None:
    default = short_dir / "algenta-mojo" / "worker-0.sock"
    assert worker_socket_path(default=default) == str(default)


def test_socket_env_override_is_used_and_stripped(monkeypatch, short_dir: Path) -> None:
    monkeypatch.setenv(WORKER_SOCKET_ENV_VAR, f" {short_dir / 'w.sock'} ")
    assert worker_socket_path(default=short_dir / "unused.sock") == str(short_dir / "w.sock")


def test_empty_socket_env_falls_back_to_default(monkeypatch, short_dir: Path) -> None:
    monkeypatch.setenv(WORKER_SOCKET_ENV_VAR, "")
    assert worker_socket_path(default=short_dir / "d.sock") == str(short_dir / "d.sock")


def test_relative_socket_path_is_anchored_at_cwd(monkeypatch, short_dir: Path) -> None:
    monkeypatch.chdir(short_dir)
    monkeypatch.setenv(WORKER_SOCKET_ENV_VAR, "w.sock")
    # Compare against the process cwd (on macOS /tmp is a symlink to /private/tmp, and
    # Path.absolute() anchors at os.getcwd()'s real path).
    assert worker_socket_path(default="/unused.sock") == str(Path.cwd() / "w.sock")


def test_socket_resolution_never_raises_on_a_long_path(monkeypatch) -> None:
    # Resolution runs at daemon import; only the launch-time check may refuse.
    long_path = "/" + "x" * 200 + ".sock"
    monkeypatch.setenv(WORKER_SOCKET_ENV_VAR, long_path)
    assert worker_socket_path(default="/unused.sock") == long_path


# ── socket path: launch-time vetting ─────────────────────────────────────────────


def test_socket_path_too_long_for_sockaddr_un_is_refused() -> None:
    with pytest.raises(ValueError, match="too long"):
        launchable_worker_socket("/" + "x" * 200 + ".sock")


def test_socket_path_just_under_the_limit_is_accepted() -> None:
    limit = worker_launch._SUN_PATH_MAX
    path = "/" + "y" * (limit - 2)  # limit-1 bytes: the longest that still fits with the NUL
    assert launchable_worker_socket(path) == path


def test_socket_path_at_an_existing_regular_file_is_refused(short_dir: Path) -> None:
    victim = short_dir / "precious.txt"
    victim.write_text("do not unlink me", encoding="utf-8")
    with pytest.raises(ValueError, match="non-socket"):
        launchable_worker_socket(str(victim))
    assert victim.read_text(encoding="utf-8") == "do not unlink me"


def test_socket_path_at_an_existing_directory_is_refused(short_dir: Path) -> None:
    with pytest.raises(ValueError, match="non-socket"):
        launchable_worker_socket(str(short_dir))


def test_socket_path_at_a_stale_socket_is_accepted(short_dir: Path) -> None:
    stale = short_dir / "stale.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as srv:
        srv.bind(str(stale))
    assert stale.is_socket()
    assert launchable_worker_socket(str(stale)) == str(stale)


def test_absent_socket_path_is_accepted(short_dir: Path) -> None:
    fresh = short_dir / "run" / "w.sock"
    assert launchable_worker_socket(str(fresh)) == str(fresh)


# ── daemon integration: the vetting runs right before Popen ──────────────────────


def test_daemon_refuses_to_spawn_a_non_executable_worker(
    monkeypatch, tmp_path: Path, short_dir: Path
) -> None:
    blob = tmp_path / "simulate"
    blob.write_bytes(b"not a program")
    blob.chmod(0o644)
    if os.access(blob, os.X_OK):
        pytest.skip("os.access reports X_OK for everything under this uid")
    spawned: list[list[str]] = []
    monkeypatch.setattr(daemon, "_MOJO_BINARY", blob)
    monkeypatch.setattr(daemon, "_MOJO_BINARY_VERIFIED", True)  # skip the freshness gate
    monkeypatch.setattr(daemon, "_MOJO_SOCK", str(short_dir / "w.sock"))
    monkeypatch.setattr(daemon.subprocess, "Popen", lambda argv, **kw: spawned.append(argv) or None)
    with pytest.raises(NativeWorkerUnavailable, match="not executable"):
        daemon.MojoProcess().start()
    assert spawned == []  # refused BEFORE anything was handed to the OS


def test_daemon_refuses_a_socket_path_that_is_a_regular_file(
    monkeypatch, tmp_path: Path, short_dir: Path
) -> None:
    # Before: start() unlinked WHATEVER ALGENTA_MOJO_SOCK pointed at. Now a non-socket there is
    # refused, and the file survives.
    worker = _executable(tmp_path / "simulate")
    victim = short_dir / "notes.txt"
    victim.write_text("keep", encoding="utf-8")
    spawned: list[list[str]] = []
    monkeypatch.setattr(daemon, "_MOJO_BINARY", worker)
    monkeypatch.setattr(daemon, "_MOJO_BINARY_VERIFIED", True)
    monkeypatch.setattr(daemon, "_MOJO_SOCK", str(victim))
    monkeypatch.setattr(daemon.subprocess, "Popen", lambda argv, **kw: spawned.append(argv) or None)
    with pytest.raises(ValueError, match="non-socket"):
        daemon.MojoProcess().start()
    assert spawned == []
    assert victim.read_text(encoding="utf-8") == "keep"


def test_daemon_spawns_the_vetted_worker_with_the_socket(
    monkeypatch, tmp_path: Path, short_dir: Path
) -> None:
    worker = _executable(tmp_path / "simulate")
    sock = short_dir / "run" / "w.sock"
    spawned: list[list[str]] = []

    class _Proc:
        pid = 4242

    monkeypatch.setattr(daemon, "_MOJO_BINARY", worker)
    monkeypatch.setattr(daemon, "_MOJO_BINARY_VERIFIED", True)
    monkeypatch.setattr(daemon, "_MOJO_SOCK", str(sock))
    monkeypatch.setattr(
        daemon.subprocess, "Popen", lambda argv, **kw: spawned.append(argv) or _Proc()
    )
    assert daemon.MojoProcess().start() is True
    assert spawned == [[str(worker), "--server", str(sock)]]
    assert sock.parent.is_dir()  # socket directory is still created for the worker


def test_daemon_module_binary_and_socket_come_from_worker_launch() -> None:
    # The daemon's module-level values are whatever worker_launch resolves — no second env
    # read in daemon.py that could disagree with the vetting.
    assert isinstance(daemon._MOJO_BINARY, Path)
    assert Path(daemon._MOJO_SOCK).is_absolute()


# ── shard-pool integration: ShardWorkerProcess.start() runs the same vetting ─────
#
# With a runtime-shards.json beside the worker, _run_daemon boots through ShardWorkerPool
# instead of MojoProcess: the default shard via start_default() and every other shard lazily
# from acquire(). Both end in ShardWorkerProcess.start(), whose binary is <engine dir>/<worker
# name> with the engine dir derived from the operator's worker override, and whose socket sits
# beside ALGENTA_MOJO_SOCK -- so it must refuse exactly what MojoProcess.start() refuses.

DEFAULT_SHARD = "algenta-runtime-worker"
LAZY_SHARD = "algenta-runtime-worker-001"


def _shard_worker(binary: Path, sock: Path) -> runtime_shards.ShardWorkerProcess:
    # verified=True skips the source-freshness gate, which is not what is under test here.
    return runtime_shards.ShardWorkerProcess(
        name=binary.name, binary=binary, sock=str(sock), source="test-fixture", verified=True
    )


def _shard_pool(engine_dir: Path, default_sock: Path) -> runtime_shards.ShardWorkerPool:
    shard_map = runtime_shards.RuntimeShardMap(
        default_worker=DEFAULT_SHARD,
        module_workers={"core.default": DEFAULT_SHARD, "lazy.kernels": LAZY_SHARD},
    )
    return runtime_shards.ShardWorkerPool(
        shard_map, engine_dir, str(default_sock), worker_source="test-fixture", verified=True
    )


def test_shard_worker_refuses_to_spawn_a_non_executable_worker(
    monkeypatch, tmp_path: Path, short_dir: Path
) -> None:
    blob = tmp_path / DEFAULT_SHARD
    blob.write_bytes(b"not a program")
    blob.chmod(0o644)
    if os.access(blob, os.X_OK):
        pytest.skip("os.access reports X_OK for everything under this uid")
    spawned: list[list[str]] = []
    monkeypatch.setattr(
        runtime_shards.subprocess, "Popen", lambda argv, **kw: spawned.append(argv) or None
    )
    with pytest.raises(NativeWorkerUnavailable, match="not executable"):
        _shard_worker(blob, short_dir / "worker-0.sock").start()
    assert spawned == []  # refused BEFORE anything was handed to the OS


def test_shard_worker_refuses_a_socket_path_that_is_a_regular_file(
    monkeypatch, tmp_path: Path, short_dir: Path
) -> None:
    # Before: start() returned True, Popen received [worker, "--server", precious.txt] and
    # precious.txt had been unlinked. Now the non-socket is refused and the file survives.
    worker = _executable(tmp_path / DEFAULT_SHARD)
    victim = short_dir / "precious.txt"
    victim.write_text("do not unlink me", encoding="utf-8")
    spawned: list[list[str]] = []
    monkeypatch.setattr(
        runtime_shards.subprocess, "Popen", lambda argv, **kw: spawned.append(argv) or None
    )
    with pytest.raises(ValueError, match="non-socket"):
        _shard_worker(worker, victim).start()
    assert spawned == []
    assert victim.read_text(encoding="utf-8") == "do not unlink me"


def test_shard_worker_spawns_the_vetted_worker_with_the_socket(
    monkeypatch, tmp_path: Path, short_dir: Path
) -> None:
    worker = _executable(tmp_path / DEFAULT_SHARD)
    sock = short_dir / "run" / "worker-0.sock"
    spawned: list[list[str]] = []

    class _Proc:
        pid = 4243

    monkeypatch.setattr(
        runtime_shards.subprocess, "Popen", lambda argv, **kw: spawned.append(argv) or _Proc()
    )
    assert _shard_worker(worker, sock).start() is True
    assert spawned == [[str(worker), "--server", str(sock)]]
    assert sock.parent.is_dir()  # socket directory is still created for the worker


def test_shard_pool_lazy_shard_refuses_a_socket_path_that_is_a_regular_file(
    monkeypatch, tmp_path: Path, short_dir: Path
) -> None:
    # acquire() spawns a non-default shard on first use, on worker-NNN.sock beside the default
    # socket. A regular file there is refused as the TYPED error the executor reports, nothing
    # is spawned, and the file survives.
    _executable(tmp_path / DEFAULT_SHARD)
    _executable(tmp_path / LAZY_SHARD)
    victim = short_dir / "worker-001.sock"
    victim.write_text("keep", encoding="utf-8")
    spawned: list[list[str]] = []
    monkeypatch.setattr(
        runtime_shards.subprocess, "Popen", lambda argv, **kw: spawned.append(argv) or None
    )
    pool = _shard_pool(tmp_path, short_dir / "worker-0.sock")
    with pytest.raises(runtime_shards.ShardWorkerUnavailable, match="non-socket"):
        asyncio.run(pool.acquire("lazy.kernels"))
    assert spawned == []
    assert victim.read_text(encoding="utf-8") == "keep"


def test_shard_pool_lazy_shard_refuses_a_non_executable_worker(
    monkeypatch, tmp_path: Path, short_dir: Path
) -> None:
    _executable(tmp_path / DEFAULT_SHARD)
    blob = tmp_path / LAZY_SHARD
    blob.write_bytes(b"not a program")
    blob.chmod(0o644)
    if os.access(blob, os.X_OK):
        pytest.skip("os.access reports X_OK for everything under this uid")
    spawned: list[list[str]] = []
    monkeypatch.setattr(
        runtime_shards.subprocess, "Popen", lambda argv, **kw: spawned.append(argv) or None
    )
    pool = _shard_pool(tmp_path, short_dir / "worker-0.sock")
    with pytest.raises(runtime_shards.ShardWorkerUnavailable, match="not executable"):
        asyncio.run(pool.acquire("lazy.kernels"))
    assert spawned == []
