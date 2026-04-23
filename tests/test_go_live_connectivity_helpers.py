from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration import test_go_live_connectivity_real as connectivity


class _DummyProcess:
    def poll(self) -> None:
        return None


class _ExitedProcess:
    def __init__(self, exit_code: int, log_path: Path | None = None) -> None:
        self._exit_code = exit_code
        self.algenta_log_path = str(log_path) if log_path is not None else None

    def poll(self) -> int:
        return self._exit_code


def test_start_api_server_uses_de_mojo_workers_for_pool_size(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured_env: dict[str, str] = {}

    def fake_popen(*_args, **kwargs):
        nonlocal captured_env
        captured_env = kwargs["env"]
        return _DummyProcess()

    monkeypatch.setattr(connectivity.subprocess, "Popen", fake_popen)

    sources_dir = tmp_path / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)

    connectivity.start_api_server(
        50123,
        sources_dir,
        {"DE_MOJO_WORKERS": "4"},
    )

    assert captured_env["MOJO_POOL_SIZE"] == "4"
    assert captured_env["ALGENTA_SOURCES_DIR"] == str(sources_dir)
    assert captured_env["PYTHONPATH"] == str(connectivity.ROOT)


def test_start_api_server_preserves_explicit_mojo_pool_size(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured_env: dict[str, str] = {}

    def fake_popen(*_args, **kwargs):
        nonlocal captured_env
        captured_env = kwargs["env"]
        return _DummyProcess()

    monkeypatch.setattr(connectivity.subprocess, "Popen", fake_popen)

    sources_dir = tmp_path / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)

    connectivity.start_api_server(
        50124,
        sources_dir,
        {
            "DE_MOJO_WORKERS": "4",
            "MOJO_POOL_SIZE": "2",
        },
    )

    assert captured_env["MOJO_POOL_SIZE"] == "2"


def test_wait_for_http_reports_process_exit_and_log_tail(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "api.log"
    log_path.write_text("booting\nfatal startup error", encoding="utf-8")

    monkeypatch.setattr(connectivity.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        connectivity.httpx,
        "get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("connection refused")),
    )

    monotonic_values = iter([0.0, 0.01])
    monkeypatch.setattr(connectivity.time, "monotonic", lambda: next(monotonic_values))

    with pytest.raises(RuntimeError, match="Process exited with code 7"):
        connectivity.wait_for_http(
            "http://127.0.0.1:59999/v1/health",
            timeout=1.0,
            proc=_ExitedProcess(7, log_path),
        )


def test_wait_for_http_includes_log_tail_on_timeout(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "api.log"
    log_path.write_text("still starting", encoding="utf-8")

    monkeypatch.setattr(connectivity.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        connectivity.httpx,
        "get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("connection refused")),
    )

    monotonic_values = iter([0.0, 0.5, 1.1])
    monkeypatch.setattr(connectivity.time, "monotonic", lambda: next(monotonic_values))

    with pytest.raises(RuntimeError, match="still starting"):
        connectivity.wait_for_http(
            "http://127.0.0.1:59999/v1/health",
            timeout=1.0,
            log_path=log_path,
        )
