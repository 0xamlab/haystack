from __future__ import annotations

import io
import socket
from contextlib import redirect_stdout
from types import SimpleNamespace

import pytest

from tests.integration import test_typescript_runtime_live as live_ts


def test_pnpm_command_prefers_corepack_when_direct_pnpm_missing(monkeypatch) -> None:
    def _fake_which(name: str) -> str | None:
        if name == "corepack":
            return "/usr/bin/corepack"
        return None

    monkeypatch.setattr(live_ts.shutil, "which", _fake_which)

    assert live_ts._pnpm_command() == ["corepack", "pnpm"]


def test_ts_build_command_falls_back_to_local_tsc(monkeypatch, tmp_path) -> None:
    sdk_dir = tmp_path / "ts-sdk"
    tsc_path = sdk_dir / "node_modules" / ".bin" / "tsc"
    tsc_path.parent.mkdir(parents=True)
    tsc_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    monkeypatch.setattr(live_ts, "TS_SDK_DIR", sdk_dir)
    monkeypatch.setattr(
        live_ts, "_pnpm_command", lambda: (_ for _ in ()).throw(FileNotFoundError("missing"))
    )

    assert live_ts._ts_build_command() == [
        str(tsc_path),
        "-p",
        str(sdk_dir / "tsconfig.json"),
    ]


def test_runtime_daemon_env_uses_isolated_runtime_paths(tmp_path) -> None:
    runtime_dir = tmp_path / "runtime"

    env = live_ts._runtime_daemon_env(runtime_dir, 50123, "de_live_example")

    assert env["ALGENTA_RUNTIME_DIR"] == str(runtime_dir)
    assert env["ALGENTA_DAEMON_SOCK"] == str(runtime_dir / "daemon.sock")
    assert env["ALGENTA_MOJO_SOCK"] == str(runtime_dir / "mojo.sock")
    assert env["ALGENTA_DAEMON_TCP"] == "127.0.0.1:50123"
    assert env["DE_BASE_URL"] == live_ts.BASE_URL
    assert env["DE_API_KEY"] == "de_live_example"
    assert "ALGENTA_RUNTIME_DEV_MODE" not in env


def test_runtime_daemon_env_enables_explicit_dev_mode_without_api_key(tmp_path) -> None:
    runtime_dir = tmp_path / "runtime"

    env = live_ts._runtime_daemon_env(runtime_dir, 50123, "")

    assert env["ALGENTA_RUNTIME_DEV_MODE"] == "1"


def test_runtime_daemon_api_key_ignores_placeholder_live_key(monkeypatch) -> None:
    monkeypatch.setattr(live_ts, "API_KEY", live_ts.resolve_local_live_api_key({}))
    monkeypatch.setattr(live_ts, "API_KEY_CONFIGURED", False)

    assert live_ts._runtime_daemon_api_key() == ""


def test_runtime_daemon_api_key_keeps_real_live_key(monkeypatch) -> None:
    monkeypatch.setattr(live_ts, "API_KEY", "de_live_real_test_key")
    monkeypatch.setattr(live_ts, "API_KEY_CONFIGURED", True)

    assert live_ts._runtime_daemon_api_key() == "de_live_real_test_key"


def test_isolated_api_server_requested_respects_truthy_flag(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_TEST_START_API_SERVER", "yes")

    assert live_ts._isolated_api_server_requested() is True


def test_isolated_api_server_env_uses_writable_temp_dirs(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ALGENTA_SOURCE_ARTIFACT_CACHE_DIR", raising=False)
    monkeypatch.delenv("ALGENTA_EGRESS_ALLOWLIST", raising=False)

    env = live_ts._isolated_api_server_env(tmp_path, 50124)

    assert env["PYTHONPATH"] == str(live_ts.ROOT)
    assert env["ALGENTA_SOURCES_DIR"] == str(tmp_path / "sources")
    assert env["ALGENTA_RUNTIME_DIR"] == str(tmp_path / "runtime")
    assert env["ALGENTA_SOURCE_ARTIFACT_CACHE_DIR"] == str(tmp_path / "artifact_cache")
    assert env["ALGENTA_EGRESS_ALLOWLIST"] == "127.0.0.1,localhost,::1"
    assert env["DE_BASE_URL"] == "http://127.0.0.1:50124"
    assert env["ALGENTA_BASE_URL"] == "http://127.0.0.1:50124"
    assert (tmp_path / "sources").is_dir()
    assert (tmp_path / "runtime").is_dir()
    assert (tmp_path / "artifact_cache").is_dir()


def test_license_verification_env_reads_api_settings_when_process_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("ALGENTA_LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("ALGENTA_JWT_SECRET", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)

    env_updates = live_ts._license_verification_env()

    assert "ALGENTA_JWT_SECRET" in env_updates or "ALGENTA_LICENSE_SIGNING_SECRET" in env_updates


def test_run_api_migrations_uses_repo_alembic_config(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_run(cmd, **kwargs):
        called["cmd"] = cmd
        called["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(live_ts.subprocess, "run", _fake_run)

    env = {"PYTHONPATH": str(live_ts.ROOT), "DATABASE_URL_SYNC": "postgresql://example"}
    live_ts._run_api_migrations(env)

    assert called["cmd"] == [
        live_ts.sys.executable,
        "-m",
        "alembic",
        "-c",
        str(live_ts.ROOT / "apps" / "api_server" / "alembic.ini"),
        "upgrade",
        "head",
    ]
    kwargs = called["kwargs"]
    assert kwargs["cwd"] == str(live_ts.ROOT)
    assert kwargs["env"] is env


def test_connector_matrix_skips_without_api_key(monkeypatch) -> None:
    monkeypatch.setattr(live_ts, "API_KEY", "")

    with pytest.raises(live_ts.SkippedCheckError, match="DE_API_KEY is not set"):
        live_ts.run_typescript_runtime_connector_matrix()


def test_api_key_lifecycle_skips_without_api_key(monkeypatch) -> None:
    monkeypatch.setattr(live_ts, "API_KEY", "")

    with pytest.raises(live_ts.SkippedCheckError, match="DE_API_KEY is not set"):
        live_ts.run_typescript_api_key_lifecycle()


def test_free_tcp_port_returns_bindable_loopback_port() -> None:
    port = live_ts._free_tcp_port()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))


def test_check_emits_running_and_success_lines() -> None:
    output = io.StringIO()
    original_results = list(live_ts.results)
    live_ts.results.clear()
    try:
        with redirect_stdout(output):
            value = live_ts.check("sample check", lambda: 7)
    finally:
        live_ts.results[:] = original_results

    assert value == 7
    rendered = output.getvalue()
    assert "  ... sample check" in rendered
    assert f"  {live_ts.PASS} sample check (" in rendered
    assert rendered.rstrip().endswith(")")
