from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.api_server.compute import mojo_adapter


class _FakeProcess:
    def __init__(self, stdout: bytes, stderr: bytes = b"", returncode: int = 0) -> None:
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self, input: bytes | None = None) -> tuple[bytes, bytes]:
        return self._stdout, self._stderr

    def kill(self) -> None:
        return None


class _BrokenCommunicateProcess(_FakeProcess):
    async def communicate(self, input: bytes | None = None) -> tuple[bytes, bytes]:
        raise RuntimeError("unable to perform operation on <WriteUnixTransport closed=True>")


@pytest.mark.anyio
async def test_invoke_subprocess_raises_on_engine_error_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mojo_adapter, "_BINARY_PATH", Path(__file__))
    monkeypatch.setattr(mojo_adapter.os, "access", lambda path, mode: True)

    async def _fake_create_subprocess_exec(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _FakeProcess(stdout=b'{"error":"bootstrap_config required"}')

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    with pytest.raises(mojo_adapter.MojoEngineError) as exc_info:
        await mojo_adapter._invoke_subprocess({"engine_type": "bootstrap"})

    assert "bootstrap_config required" in str(exc_info.value)


@pytest.mark.anyio
async def test_invoke_subprocess_returns_json_payload_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mojo_adapter, "_BINARY_PATH", Path(__file__))
    monkeypatch.setattr(mojo_adapter.os, "access", lambda path, mode: True)

    async def _fake_create_subprocess_exec(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _FakeProcess(stdout=b'{"simulation_model":"monte_carlo","summary":{"mean":42.0}}')

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    result = await mojo_adapter._invoke_subprocess({"engine_type": "monte_carlo"})

    assert result["simulation_model"] == "monte_carlo"
    assert result["summary"]["mean"] == 42.0


@pytest.mark.anyio
async def test_invoke_subprocess_uses_python_fallback_when_binary_missing_and_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mojo_adapter, "_BINARY_PATH", Path("/tmp/does-not-exist-mojo"))
    monkeypatch.setattr(mojo_adapter.os, "access", lambda path, mode: False)
    monkeypatch.setattr(mojo_adapter.settings, "runtime_fallback_mode", "allow")

    async def _fake_invoke_python_fallback(payload: dict[str, object]) -> dict[str, object]:
        return {
            "engine_version": "0.1.0-python-fallback",
            "scenarios_run": payload["runs"],
            "summary": {"mean": 123.0},
            "percentiles": {"p5": 1.0, "p25": 2.0, "p50": 3.0, "p75": 4.0, "p95": 5.0},
            "risk": {"probability_of_loss": 0.0, "var_95": 1.0},
            "simulation_model": payload["engine_type"],
            "engine_type": payload["engine_type"],
        }

    monkeypatch.setattr(mojo_adapter, "_invoke_python_fallback", _fake_invoke_python_fallback)

    result = await mojo_adapter._invoke_subprocess({"engine_type": "lhs", "runs": 250})

    assert result["engine_version"] == "0.1.0-python-fallback"
    assert result["simulation_model"] == "lhs"
    assert result["engine_type"] == "lhs"
    assert result["scenarios_run"] == 250


@pytest.mark.anyio
async def test_invoke_subprocess_suppresses_repeated_missing_binary_warnings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mojo_adapter, "_BINARY_PATH", Path("/tmp/does-not-exist-mojo"))
    monkeypatch.setattr(mojo_adapter.os, "access", lambda path, mode: False)
    monkeypatch.setattr(mojo_adapter.settings, "runtime_fallback_mode", "allow")
    monkeypatch.setattr(mojo_adapter, "_FALLBACK_WARNING_STATE", {})

    warnings: list[tuple[str, dict[str, object | None]]] = []
    debugs: list[tuple[str, dict[str, object | None]]] = []
    monotonic_values = [0.0, 1.0]

    async def _fake_invoke_python_fallback(payload: dict[str, object]) -> dict[str, object]:
        return {
            "engine_version": "0.1.0-python-fallback",
            "summary": {"mean": 123.0},
            "simulation_model": payload["engine_type"],
            "engine_type": payload["engine_type"],
        }

    monkeypatch.setattr(
        mojo_adapter.logger,
        "warning",
        lambda event, **kwargs: warnings.append((event, kwargs)),
    )
    monkeypatch.setattr(
        mojo_adapter.logger,
        "debug",
        lambda event, **kwargs: debugs.append((event, kwargs)),
    )
    monkeypatch.setattr(
        mojo_adapter.time,
        "monotonic",
        lambda: monotonic_values.pop(0) if monotonic_values else 1.0,
    )
    monkeypatch.setattr(mojo_adapter, "_invoke_python_fallback", _fake_invoke_python_fallback)

    await mojo_adapter._invoke_subprocess({"engine_type": "lhs", "runs": 10})
    await mojo_adapter._invoke_subprocess({"engine_type": "lhs", "runs": 10})

    assert [event for event, _ in warnings] == ["mojo_binary_missing_using_python_fallback"]
    assert [event for event, _ in debugs] == [
        "mojo_binary_missing_using_python_fallback_suppressed"
    ]


@pytest.mark.anyio
async def test_invoke_subprocess_uses_python_fallback_when_engine_crashes_and_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mojo_adapter, "_BINARY_PATH", Path(__file__))
    monkeypatch.setattr(mojo_adapter.os, "access", lambda path, mode: True)
    monkeypatch.setattr(mojo_adapter.settings, "runtime_fallback_mode", "allow")

    async def _fake_create_subprocess_exec(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _FakeProcess(stdout=b"", stderr=b"segfault", returncode=-5)

    async def _fake_invoke_python_fallback(payload: dict[str, object]) -> dict[str, object]:
        return {
            "engine_version": "0.1.0-python-fallback",
            "scenarios_run": payload["runs"],
            "summary": {"mean": 123.0},
            "percentiles": {"p5": 1.0, "p25": 2.0, "p50": 3.0, "p75": 4.0, "p95": 5.0},
            "risk": {"probability_of_loss": 0.0, "var_95": 1.0},
            "simulation_model": payload["engine_type"],
            "engine_type": payload["engine_type"],
        }

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)
    monkeypatch.setattr(mojo_adapter, "_invoke_python_fallback", _fake_invoke_python_fallback)

    result = await mojo_adapter._invoke_subprocess({"engine_type": "monte_carlo", "runs": 250})

    assert result["engine_version"] == "0.1.0-python-fallback"
    assert result["simulation_model"] == "monte_carlo"
    assert result["engine_type"] == "monte_carlo"
    assert result["scenarios_run"] == 250


@pytest.mark.anyio
async def test_invoke_subprocess_uses_python_fallback_when_binary_is_unexecutable_and_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mojo_adapter, "_BINARY_PATH", Path(__file__))
    monkeypatch.setattr(mojo_adapter.os, "access", lambda path, mode: True)
    monkeypatch.setattr(mojo_adapter.settings, "runtime_fallback_mode", "allow")

    async def _fake_create_subprocess_exec(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise OSError(8, "Exec format error")

    async def _fake_invoke_python_fallback(payload: dict[str, object]) -> dict[str, object]:
        return {
            "engine_version": "0.1.0-python-fallback",
            "scenarios_run": payload["runs"],
            "summary": {"mean": 123.0},
            "percentiles": {"p5": 1.0, "p25": 2.0, "p50": 3.0, "p75": 4.0, "p95": 5.0},
            "risk": {"probability_of_loss": 0.0, "var_95": 1.0},
            "simulation_model": payload["engine_type"],
            "engine_type": payload["engine_type"],
        }

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)
    monkeypatch.setattr(mojo_adapter, "_invoke_python_fallback", _fake_invoke_python_fallback)

    result = await mojo_adapter._invoke_subprocess({"engine_type": "monte_carlo", "runs": 250})

    assert result["engine_version"] == "0.1.0-python-fallback"
    assert result["simulation_model"] == "monte_carlo"
    assert result["engine_type"] == "monte_carlo"
    assert result["scenarios_run"] == 250


@pytest.mark.anyio
async def test_invoke_subprocess_uses_python_fallback_when_subprocess_io_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mojo_adapter, "_BINARY_PATH", Path(__file__))
    monkeypatch.setattr(mojo_adapter.os, "access", lambda path, mode: True)
    monkeypatch.setattr(mojo_adapter.settings, "runtime_fallback_mode", "allow")

    async def _fake_create_subprocess_exec(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _BrokenCommunicateProcess(stdout=b"", stderr=b"", returncode=None)

    async def _fake_invoke_python_fallback(payload: dict[str, object]) -> dict[str, object]:
        return {
            "engine_version": "0.1.0-python-fallback",
            "scenarios_run": payload["runs"],
            "summary": {"mean": 123.0},
            "percentiles": {"p5": 1.0, "p25": 2.0, "p50": 3.0, "p75": 4.0, "p95": 5.0},
            "risk": {"probability_of_loss": 0.0, "var_95": 1.0},
            "simulation_model": payload["engine_type"],
            "engine_type": payload["engine_type"],
        }

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)
    monkeypatch.setattr(mojo_adapter, "_invoke_python_fallback", _fake_invoke_python_fallback)

    result = await mojo_adapter._invoke_subprocess({"engine_type": "monte_carlo", "runs": 250})

    assert result["engine_version"] == "0.1.0-python-fallback"
    assert result["simulation_model"] == "monte_carlo"
    assert result["engine_type"] == "monte_carlo"
    assert result["scenarios_run"] == 250


def test_invoke_subprocess_sync_rewarns_after_cooldown_when_engine_crashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mojo_adapter, "_BINARY_PATH", Path(__file__))
    monkeypatch.setattr(mojo_adapter.os, "access", lambda path, mode: True)
    monkeypatch.setattr(mojo_adapter.settings, "runtime_fallback_mode", "allow")
    monkeypatch.setattr(mojo_adapter, "_FALLBACK_WARNING_STATE", {})

    warnings: list[tuple[str, dict[str, object | None]]] = []
    debugs: list[tuple[str, dict[str, object | None]]] = []
    monotonic_values = [0.0, 1.0, 61.0]

    class _FakeCompletedProcess:
        returncode = -5
        stdout = b""
        stderr = b"segfault"

    def _fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _FakeCompletedProcess()

    def _fake_invoke_python_fallback_sync(payload: dict[str, object]) -> dict[str, object]:
        return {
            "engine_version": "0.1.0-python-fallback",
            "summary": {"mean": 123.0},
            "simulation_model": payload["engine_type"],
            "engine_type": payload["engine_type"],
        }

    monkeypatch.setattr(
        mojo_adapter.logger,
        "warning",
        lambda event, **kwargs: warnings.append((event, kwargs)),
    )
    monkeypatch.setattr(
        mojo_adapter.logger,
        "debug",
        lambda event, **kwargs: debugs.append((event, kwargs)),
    )
    monkeypatch.setattr(
        mojo_adapter.time,
        "monotonic",
        lambda: monotonic_values.pop(0) if monotonic_values else 61.0,
    )
    monkeypatch.setattr(mojo_adapter.subprocess, "run", _fake_run)
    monkeypatch.setattr(
        mojo_adapter,
        "_invoke_python_fallback_sync",
        _fake_invoke_python_fallback_sync,
    )

    mojo_adapter._invoke_subprocess_sync({"engine_type": "monte_carlo", "runs": 10})
    mojo_adapter._invoke_subprocess_sync({"engine_type": "monte_carlo", "runs": 10})
    mojo_adapter._invoke_subprocess_sync({"engine_type": "monte_carlo", "runs": 10})

    assert [event for event, _ in warnings] == [
        "mojo_engine_crashed_using_python_fallback",
        "mojo_engine_crashed_using_python_fallback",
    ]
    assert [event for event, _ in debugs] == [
        "mojo_engine_crashed_using_python_fallback_suppressed"
    ]


@pytest.mark.anyio
async def test_invoke_python_fallback_returns_supported_engine_identity() -> None:
    result = await mojo_adapter._invoke_python_fallback(
        {
            "engine_type": "qmc_sobol",
            "runs": 10,
            "seed": 7,
            "variables": [
                {
                    "name": "revenue",
                    "distribution": "fixed",
                    "params": {"value": 42.0},
                }
            ],
            "objective_function": "revenue",
        }
    )

    assert result["engine_version"] == "0.1.0-python-fallback"
    assert result["simulation_model"] == "qmc_sobol"
    assert result["engine_type"] == "qmc_sobol"
    assert result["summary"]["mean"] == 42.0


@pytest.mark.anyio
async def test_invoke_python_fallback_loads_adapter_by_file_path_when_mojo_is_shadowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved_modules = {
        name: sys.modules.get(name)
        for name in ("mojo", "mojo.bindings", "mojo.bindings.python_adapter")
    }

    try:
        mojo_adapter._load_python_fallback_runner.cache_clear()
        for name in saved_modules:
            sys.modules.pop(name, None)

        shadow_mojo = types.ModuleType("mojo")
        shadow_mojo.__path__ = ["/tmp/shadow-mojo"]
        sys.modules["mojo"] = shadow_mojo

        result = await mojo_adapter._invoke_python_fallback(
            {
                "engine_type": "monte_carlo",
                "runs": 5,
                "seed": 1,
                "variables": [
                    {
                        "name": "x",
                        "distribution": "fixed",
                        "params": {"value": 11.0},
                    }
                ],
                "objective_function": "x",
            }
        )

        assert result["summary"]["mean"] == 11.0
    finally:
        mojo_adapter._load_python_fallback_runner.cache_clear()
        for name, module in saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


@pytest.mark.anyio
async def test_invoke_subprocess_raises_when_binary_missing_and_runtime_fallbacks_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mojo_adapter, "_BINARY_PATH", Path("/tmp/does-not-exist-mojo"))
    monkeypatch.setattr(mojo_adapter.os, "access", lambda path, mode: False)
    monkeypatch.setattr(mojo_adapter.settings, "runtime_fallback_mode", "deny")

    with pytest.raises(mojo_adapter.MojoEngineError) as exc_info:
        await mojo_adapter._invoke_subprocess({"engine_type": "monte_carlo", "runs": 100})

    assert "Mojo binary not found" in str(exc_info.value)
    assert exc_info.value.code == "binary_missing"


@pytest.mark.anyio
async def test_invoke_engine_rejects_invalid_payload_before_touching_mojo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    async def _should_not_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal called
        called = True
        raise AssertionError("Mojo path must not run for invalid payloads")

    monkeypatch.setattr(mojo_adapter, "_invoke_subprocess", _should_not_run)

    with pytest.raises(mojo_adapter.MojoEngineError) as exc_info:
        await mojo_adapter.invoke_engine({"runs": 100})

    assert called is False
    assert exc_info.value.code == "invalid_payload"


@pytest.mark.anyio
async def test_invoke_engine_routes_inactive_pool_to_fallback_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.api_server.compute import mojo_pool

    class _InactivePool:
        async def invoke(
            self,
            payload: dict[str, object],
            *,
            timeout: float | None = None,
        ) -> dict[str, object]:
            raise mojo_pool.MojoEngineError("Mojo pool is not running")

    monkeypatch.setattr(mojo_pool, "get_pool_sync", lambda: _InactivePool())

    async def _fake_invoke_subprocess(
        payload: dict[str, object],
        *,
        timeout: float = 60.0,
    ) -> dict[str, object]:
        assert timeout == 60.0
        return {
            "engine_version": "0.1.0-python-fallback",
            "summary": {"mean": 42.0},
            "percentiles": {"p5": 1.0, "p25": 2.0, "p50": 3.0, "p75": 4.0, "p95": 5.0},
            "risk": {"probability_of_loss": 0.0, "var_95": 1.0},
            "simulation_model": payload["engine_type"],
            "engine_type": payload["engine_type"],
            "scenarios_run": 100,
        }

    monkeypatch.setattr(mojo_adapter, "_invoke_subprocess", _fake_invoke_subprocess)

    result = await mojo_adapter.invoke_engine({"engine_type": "monte_carlo", "runs": 100})

    assert result["engine_version"] == "0.1.0-python-fallback"
    assert result["simulation_model"] == "monte_carlo"


@pytest.mark.anyio
async def test_invoke_engine_routes_unhealthy_pool_worker_to_fallback_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.api_server.compute import mojo_pool

    class _UnhealthyPool:
        async def invoke(
            self,
            payload: dict[str, object],
            *,
            timeout: float | None = None,
        ) -> dict[str, object]:
            raise mojo_pool.MojoEngineError(
                "Worker 2 became unhealthy during engine execution.",
                code="worker_unhealthy",
                recoverable=True,
                engine_type=str(payload.get("engine_type") or "unknown"),
                stage="pool_dispatch",
                details={"worker_id": 2},
            )

    monkeypatch.setattr(mojo_pool, "get_pool_sync", lambda: _UnhealthyPool())

    async def _fake_invoke_subprocess(
        payload: dict[str, object],
        *,
        timeout: float = 60.0,
    ) -> dict[str, object]:
        assert timeout == 60.0
        return {
            "engine_version": "0.1.0-python-fallback",
            "summary": {"mean": 42.0},
            "simulation_model": payload["engine_type"],
            "engine_type": payload["engine_type"],
            "scenarios_run": 100,
        }

    monkeypatch.setattr(mojo_adapter, "_invoke_subprocess", _fake_invoke_subprocess)

    result = await mojo_adapter.invoke_engine({"engine_type": "monte_carlo", "runs": 100})

    assert result["engine_version"] == "0.1.0-python-fallback"
    assert result["simulation_model"] == "monte_carlo"


def test_invoke_engine_sync_prefers_pool_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.api_server.compute import mojo_pool

    class _FakePool:
        def invoke_sync(
            self, payload: dict[str, object], timeout: float | None = None
        ) -> dict[str, object]:
            assert timeout == 7.0
            assert payload["engine_type"] == "field_map"
            return {"engine_type": "field_map", "mapped": True}

    monkeypatch.setattr(mojo_pool, "get_pool_sync", lambda: _FakePool())

    result = mojo_adapter.invoke_engine_sync({"engine_type": "field_map"}, timeout=7.0)

    assert result == {"engine_type": "field_map", "mapped": True}


def test_invoke_engine_sync_routes_inactive_pool_to_sync_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.api_server.compute import mojo_pool

    class _InactivePool:
        def invoke_sync(
            self, payload: dict[str, object], timeout: float | None = None
        ) -> dict[str, object]:
            raise mojo_pool.MojoEngineError("Mojo pool is not running")

    monkeypatch.setattr(mojo_pool, "get_pool_sync", lambda: _InactivePool())

    def _fake_invoke_subprocess_sync(
        payload: dict[str, object], *, timeout: float = 60.0
    ) -> dict[str, object]:
        assert payload["engine_type"] == "field_map"
        assert timeout == 5.0
        return {"engine_type": "field_map", "mapped": True}

    monkeypatch.setattr(mojo_adapter, "_invoke_subprocess_sync", _fake_invoke_subprocess_sync)

    result = mojo_adapter.invoke_engine_sync({"engine_type": "field_map"}, timeout=5.0)

    assert result == {"engine_type": "field_map", "mapped": True}


def test_invoke_subprocess_sync_uses_python_fallback_when_engine_crashes_and_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mojo_adapter, "_BINARY_PATH", Path(__file__))
    monkeypatch.setattr(mojo_adapter.os, "access", lambda path, mode: True)
    monkeypatch.setattr(mojo_adapter.settings, "runtime_fallback_mode", "allow")

    class _FakeCompletedProcess:
        returncode = -5
        stdout = b""
        stderr = b"segfault"

    def _fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _FakeCompletedProcess()

    def _fake_invoke_python_fallback_sync(payload: dict[str, object]) -> dict[str, object]:
        return {
            "engine_version": "0.1.0-python-fallback",
            "scenarios_run": payload["runs"],
            "summary": {"mean": 123.0},
            "percentiles": {"p5": 1.0, "p25": 2.0, "p50": 3.0, "p75": 4.0, "p95": 5.0},
            "risk": {"probability_of_loss": 0.0, "var_95": 1.0},
            "simulation_model": payload["engine_type"],
            "engine_type": payload["engine_type"],
        }

    monkeypatch.setattr(mojo_adapter.subprocess, "run", _fake_run)
    monkeypatch.setattr(
        mojo_adapter,
        "_invoke_python_fallback_sync",
        _fake_invoke_python_fallback_sync,
    )

    result = mojo_adapter._invoke_subprocess_sync({"engine_type": "monte_carlo", "runs": 250})

    assert result["engine_version"] == "0.1.0-python-fallback"
    assert result["simulation_model"] == "monte_carlo"
    assert result["engine_type"] == "monte_carlo"
    assert result["scenarios_run"] == 250


def test_invoke_subprocess_sync_uses_python_fallback_when_binary_is_unexecutable_and_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mojo_adapter, "_BINARY_PATH", Path(__file__))
    monkeypatch.setattr(mojo_adapter.os, "access", lambda path, mode: True)
    monkeypatch.setattr(mojo_adapter.settings, "runtime_fallback_mode", "allow")

    def _fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise OSError(8, "Exec format error")

    def _fake_invoke_python_fallback_sync(payload: dict[str, object]) -> dict[str, object]:
        return {
            "engine_version": "0.1.0-python-fallback",
            "scenarios_run": payload["runs"],
            "summary": {"mean": 123.0},
            "percentiles": {"p5": 1.0, "p25": 2.0, "p50": 3.0, "p75": 4.0, "p95": 5.0},
            "risk": {"probability_of_loss": 0.0, "var_95": 1.0},
            "simulation_model": payload["engine_type"],
            "engine_type": payload["engine_type"],
        }

    monkeypatch.setattr(mojo_adapter.subprocess, "run", _fake_run)
    monkeypatch.setattr(
        mojo_adapter,
        "_invoke_python_fallback_sync",
        _fake_invoke_python_fallback_sync,
    )

    result = mojo_adapter._invoke_subprocess_sync({"engine_type": "monte_carlo", "runs": 250})

    assert result["engine_version"] == "0.1.0-python-fallback"
    assert result["simulation_model"] == "monte_carlo"
    assert result["engine_type"] == "monte_carlo"
    assert result["scenarios_run"] == 250


@pytest.mark.anyio
async def test_pool_invoke_raises_structured_error_when_worker_becomes_unhealthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.api_server.compute import mojo_pool

    class _DeadWorker:
        id = 7
        healthy = False

        async def invoke(
            self,
            payload: dict[str, object],
            *,
            timeout: float | None = None,
        ) -> dict[str, object]:
            raise mojo_pool.MojoEngineError(
                "Worker 7 timed out after 60s",
                code="timeout",
                recoverable=True,
                engine_type=str(payload.get("engine_type") or "unknown"),
                stage="worker_exec",
                details={"worker_id": 7},
            )

    scheduled: list[str] = []

    def _fake_create_task(coro):  # type: ignore[no-untyped-def]
        scheduled.append("replace")
        coro.close()
        return SimpleNamespace()

    pool = mojo_pool.MojoWorkerPool(size=1)
    pool._running = True
    await pool._queue.put(_DeadWorker())
    monkeypatch.setattr(asyncio, "create_task", _fake_create_task)

    with pytest.raises(mojo_pool.MojoEngineError) as exc_info:
        await pool.invoke({"engine_type": "field_map"})

    assert exc_info.value.code == "worker_unhealthy"
    assert scheduled == ["replace"]
