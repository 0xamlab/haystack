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


def test_binding_token_store_round_trip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = importlib.import_module("decision_engine.device_binding")
    module._MEMORY_STORE.clear()
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))

    module.store_device_binding_token(
        base_url="https://example.test",
        api_key="de_live_test_key",
        device_id="python-device-0001",
        binding_token="binding-token-000000000000000001",
    )

    stored = module.load_device_binding_token(
        base_url="https://example.test",
        api_key="de_live_test_key",
        device_id="python-device-0001",
    )

    assert stored == "binding-token-000000000000000001"


def test_binding_token_store_falls_back_to_memory_when_disk_write_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = importlib.import_module("decision_engine.device_binding")
    module._MEMORY_STORE.clear()
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setattr(
        module, "_write_store", lambda payload: (_ for _ in ()).throw(PermissionError)
    )

    module.store_device_binding_token(
        base_url="https://example.test/",
        api_key="de_live_test_key",
        device_id="python-device-0001",
        binding_token="binding-token-000000000000000001",
    )

    stored = module.load_device_binding_token(
        base_url="https://example.test",
        api_key="de_live_test_key",
        device_id="python-device-0001",
    )

    assert stored == "binding-token-000000000000000001"


def test_sync_client_loads_persisted_binding_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    binding_module = importlib.import_module("decision_engine.device_binding")
    binding_module._MEMORY_STORE.clear()
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("ALGENTA_DEVICE_ID", "python-device-0001")
    module = importlib.import_module("decision_engine.client_facade")
    monkeypatch.setattr(
        module,
        "_get_httpx",
        lambda: SimpleNamespace(Client=lambda **kwargs: kwargs),
    )
    binding_module.store_device_binding_token(
        base_url="https://example.test",
        api_key="de_live_test_key",
        device_id="python-device-0001",
        binding_token="binding-token-000000000000000001",
    )

    client = module.DecisionEngineClient(
        api_key="de_live_test_key",
        base_url="https://example.test",
    )
    built = client._build_http_client()

    assert built["headers"]["X-Algenta-Device-Binding-Token"] == "binding-token-000000000000000001"


def test_sync_client_persists_binding_token_from_response(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    binding_module = importlib.import_module("decision_engine.device_binding")
    binding_module._MEMORY_STORE.clear()
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    module = importlib.import_module("decision_engine.client_facade")
    monkeypatch.setenv("ALGENTA_DEVICE_ID", "python-device-0001")
    monkeypatch.setattr(
        module,
        "_get_httpx",
        lambda: SimpleNamespace(Client=lambda **kwargs: SimpleNamespace(headers=kwargs["headers"])),
    )

    client = module.DecisionEngineClient(
        api_key="de_live_test_key",
        base_url="https://example.test",
    )
    client._build_http_client()

    response = SimpleNamespace(
        headers={
            "X-Algenta-Device-Binding-Token": "binding-token-000000000000000001",
        }
    )
    client._store_device_binding_token(response)

    stored = binding_module.load_device_binding_token(
        base_url="https://example.test",
        api_key="de_live_test_key",
        device_id="python-device-0001",
    )
    assert stored == "binding-token-000000000000000001"
    assert client._client.headers["X-Algenta-Device-Binding-Token"] == stored


@pytest.mark.anyio
async def test_async_client_loads_persisted_binding_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    binding_module = importlib.import_module("decision_engine.device_binding")
    binding_module._MEMORY_STORE.clear()
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("ALGENTA_DEVICE_ID", "python-async-device-0001")
    binding_module.store_device_binding_token(
        base_url="https://example.test",
        api_key="de_live_test_key",
        device_id="python-async-device-0001",
        binding_token="binding-token-000000000000000001",
    )

    module = importlib.import_module("decision_engine.async_client_facade")
    monkeypatch.setattr(
        module,
        "_get_httpx",
        lambda: SimpleNamespace(AsyncClient=lambda **kwargs: kwargs),
    )

    client = module.AsyncDecisionEngineClient(
        api_key="de_live_test_key",
        base_url="https://example.test",
    )
    built = client._build_http_client()

    assert built["headers"]["X-Algenta-Device-Binding-Token"] == "binding-token-000000000000000001"
