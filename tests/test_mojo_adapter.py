from __future__ import annotations

import asyncio
import sys
from pathlib import Path

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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_invoke_python_fallback_reinserts_repo_root_before_import(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = str(Path(mojo_adapter.__file__).resolve().parents[3])
    saved_modules = {
        name: sys.modules.get(name)
        for name in ("mojo", "mojo.bindings", "mojo.bindings.python_adapter")
    }

    try:
        for name in saved_modules:
            sys.modules.pop(name, None)

        filtered_path = [entry for entry in sys.path if entry and entry != repo_root]
        monkeypatch.setattr(sys, "path", filtered_path)
        monkeypatch.chdir(tmp_path)

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

        assert sys.path[0] == repo_root
        assert result["summary"]["mean"] == 11.0
    finally:
        for name, module in saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


@pytest.mark.asyncio
async def test_invoke_subprocess_raises_when_binary_missing_and_runtime_fallbacks_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mojo_adapter, "_BINARY_PATH", Path("/tmp/does-not-exist-mojo"))
    monkeypatch.setattr(mojo_adapter.os, "access", lambda path, mode: False)
    monkeypatch.setattr(mojo_adapter.settings, "runtime_fallback_mode", "deny")

    with pytest.raises(mojo_adapter.MojoEngineError) as exc_info:
        await mojo_adapter._invoke_subprocess({"engine_type": "monte_carlo", "runs": 100})

    assert "Mojo binary not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_invoke_engine_routes_inactive_pool_to_fallback_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.api_server.compute import mojo_pool

    class _InactivePool:
        async def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            raise mojo_pool.MojoEngineError("Mojo pool is not running")

    monkeypatch.setattr(mojo_pool, "get_pool_sync", lambda: _InactivePool())

    async def _fake_invoke_subprocess(payload: dict[str, object]) -> dict[str, object]:
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
