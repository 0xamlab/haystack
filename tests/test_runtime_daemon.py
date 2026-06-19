from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import apps.runtime.daemon as daemon


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
        f"  Mojo unix socket: {tmp_path / 'mojo.sock'}  (not present)\n"
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
