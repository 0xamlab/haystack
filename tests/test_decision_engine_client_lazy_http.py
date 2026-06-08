from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
if str(PYTHON_SDK) not in sys.path:
    sys.path.insert(0, str(PYTHON_SDK))


def test_decision_engine_client_init_defers_httpx_until_first_transport_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("decision_engine.client_facade")
    client = module.DecisionEngineClient(api_key="de_test_abc123")
    builds = 0
    closes = 0

    class _FakeTransport:
        def request(self, method: str, path: str, **kwargs):
            return {"method": method, "path": path, "kwargs": kwargs}

        def close(self) -> None:
            nonlocal closes
            closes += 1

    def _build_client(**kwargs):
        nonlocal builds
        builds += 1
        return _FakeTransport()

    fake_httpx = SimpleNamespace(Client=_build_client)
    monkeypatch.setattr(module, "_get_httpx", lambda: fake_httpx)

    client.close()
    assert builds == 0
    assert closes == 0

    result = client._client.request("GET", "/v1/health")

    assert result["path"] == "/v1/health"
    assert builds == 1

    client.close()
    assert closes == 1


@pytest.mark.anyio
async def test_async_decision_engine_client_init_defers_httpx_until_first_transport_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("decision_engine.async_client_facade")
    client = module.AsyncDecisionEngineClient(api_key="de_test_abc123")
    builds = 0
    closes = 0

    class _FakeTransport:
        async def request(self, method: str, path: str, **kwargs):
            return {"method": method, "path": path, "kwargs": kwargs}

        async def aclose(self) -> None:
            nonlocal closes
            closes += 1

    def _build_client(**kwargs):
        nonlocal builds
        builds += 1
        return _FakeTransport()

    fake_httpx = SimpleNamespace(AsyncClient=_build_client)
    monkeypatch.setattr(module, "_get_httpx", lambda: fake_httpx)

    await client.aclose()
    assert builds == 0
    assert closes == 0

    result = await client._client.request("GET", "/v1/health")

    assert result["path"] == "/v1/health"
    assert builds == 1

    await client.aclose()
    assert closes == 1


def test_sync_lazy_http_client_preserves_instance_request_overrides() -> None:
    module = importlib.import_module("decision_engine.client_facade")
    client = module.DecisionEngineClient(api_key="de_test_override")
    attempts = 0

    def _override(method: str, path: str, **kwargs):
        nonlocal attempts
        attempts += 1
        return {"method": method, "path": path, "kwargs": kwargs}

    client._client.request = _override  # type: ignore[method-assign]

    result = client._client.request("POST", "/v1/test", json={"ok": True})

    assert result["path"] == "/v1/test"
    assert attempts == 1


@pytest.mark.anyio
async def test_async_lazy_http_client_preserves_instance_request_overrides() -> None:
    module = importlib.import_module("decision_engine.async_client_facade")
    client = module.AsyncDecisionEngineClient(api_key="de_test_override")
    attempts = 0

    async def _override(method: str, path: str, **kwargs):
        nonlocal attempts
        attempts += 1
        return {"method": method, "path": path, "kwargs": kwargs}

    client._client.request = _override  # type: ignore[method-assign]

    result = await client._client.request("POST", "/v1/test", json={"ok": True})

    assert result["path"] == "/v1/test"
    assert attempts == 1
    await client.aclose()
