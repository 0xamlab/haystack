from __future__ import annotations

import asyncio
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
