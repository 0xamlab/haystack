from __future__ import annotations

import pytest

from tests.integration import test_go_live_full_real as go_live


def test_print_summary_lists_failed_suite_names(capsys) -> None:
    failed = go_live._print_summary([
        ("Connectivity", True, 12.3),
        ("Live MCP", False, 45.6),
        ("Source matrix", True, 123.4),
        ("Mojo A-Z", False, 67.8),
    ])

    captured = capsys.readouterr().out

    assert failed == 2
    assert "Passed suites: 2" in captured
    assert "Failed suites: 2" in captured
    assert "Failed suite names:" in captured
    assert "  - Live MCP" in captured
    assert "  - Mojo A-Z" in captured
    assert "  - ✅ Source matrix: 123.4s" in captured
    assert "  - ❌ Mojo A-Z: 67.8s" in captured


@pytest.mark.parametrize("attempts_before_success", [1])
def test_run_live_suite_with_fresh_server_retries_startup_once(monkeypatch, attempts_before_success: int) -> None:
    ports = iter([55101, 55102])
    wait_calls: list[tuple[str, float]] = []
    start_calls: list[tuple[int, str]] = []
    stop_calls: list[object] = []

    async def fake_seed_api_key(_database_url: str) -> tuple[str, str]:
        return ("de_test_key", "org_test")

    class _Proc:
        def __init__(self, port: int) -> None:
            self.port = port
            self.algenta_log_path = f"/tmp/fake-{port}.log"

    def fake_start_api_server(port: int, sources_dir, env):
        start_calls.append((port, str(sources_dir)))
        return _Proc(port)

    def fake_wait_for_http(url: str, timeout: float, *, proc=None, log_path=None) -> None:
        wait_calls.append((url, timeout))
        if len(wait_calls) <= attempts_before_success:
            raise RuntimeError("connection refused")

    def fake_run_suite(name: str, cmd: list[str], *, env: dict[str, str], timeout: int):
        return True, 12.5, ""

    monkeypatch.setattr(go_live, "free_port", lambda: next(ports))
    monkeypatch.setattr(go_live, "seed_api_key", fake_seed_api_key)
    monkeypatch.setattr(go_live, "start_api_server", fake_start_api_server)
    monkeypatch.setattr(go_live, "wait_for_http", fake_wait_for_http)
    monkeypatch.setattr(go_live, "run_suite", fake_run_suite)
    monkeypatch.setattr(go_live, "stop_process", lambda proc: stop_calls.append(proc))
    monkeypatch.setattr(go_live.time, "sleep", lambda _seconds: None)

    ok, elapsed = go_live.run_live_suite_with_fresh_server(
        "Live Runtime",
        ["python", "tests/integration/test_algenta_runtime_live.py"],
        env_base={"PYTHONPATH": "."},
        timeout=120,
    )

    assert ok is True
    assert elapsed == 12.5
    assert len(start_calls) == 2
    assert len(wait_calls) == 2
    assert wait_calls[0][1] == 120.0
    assert len(stop_calls) >= 1


def test_run_live_suite_with_fresh_server_raises_after_second_startup_failure(monkeypatch) -> None:
    ports = iter([55201, 55202])
    stop_calls: list[object] = []

    async def fake_seed_api_key(_database_url: str) -> tuple[str, str]:
        return ("de_test_key", "org_test")

    class _Proc:
        def __init__(self, port: int) -> None:
            self.port = port
            self.algenta_log_path = f"/tmp/fake-{port}.log"

    def fake_start_api_server(port: int, sources_dir, env):
        return _Proc(port)

    def fake_wait_for_http(url: str, timeout: float, *, proc=None, log_path=None) -> None:
        raise RuntimeError("still starting")

    monkeypatch.setattr(go_live, "free_port", lambda: next(ports))
    monkeypatch.setattr(go_live, "seed_api_key", fake_seed_api_key)
    monkeypatch.setattr(go_live, "start_api_server", fake_start_api_server)
    monkeypatch.setattr(go_live, "wait_for_http", fake_wait_for_http)
    monkeypatch.setattr(go_live, "stop_process", lambda proc: stop_calls.append(proc))
    monkeypatch.setattr(go_live.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="still starting"):
        go_live.run_live_suite_with_fresh_server(
            "Live Runtime",
            ["python", "tests/integration/test_algenta_runtime_live.py"],
            env_base={"PYTHONPATH": "."},
            timeout=120,
        )

    assert len(stop_calls) >= 2
