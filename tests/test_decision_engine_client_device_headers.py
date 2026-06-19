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


def test_sync_client_builds_hosted_device_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("decision_engine.client_facade")
    monkeypatch.setenv("ALGENTA_DEVICE_ID", "python-device-0001")
    monkeypatch.setattr(
        module,
        "_get_httpx",
        lambda: SimpleNamespace(Client=lambda **kwargs: kwargs),
    )

    client = module.DecisionEngineClient(
        api_key="de_live_test_key",
        base_url="https://example.test",
    )
    built = client._build_http_client()

    headers = built["headers"]
    assert headers["Authorization"] == "Bearer de_live_test_key"
    assert headers["User-Agent"] == "algenta-python/1.0.0"
    assert headers["X-Algenta-Device-Id"] == "python-device-0001"
    assert headers["X-Algenta-Hostname-Hash"]
    assert headers["X-Algenta-SDK-Version"] == "algenta-python/1.0.0"


@pytest.mark.anyio
async def test_async_client_builds_hosted_device_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("decision_engine.async_client_facade")
    monkeypatch.setenv("ALGENTA_DEVICE_ID", "python-async-device-0001")
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

    headers = built["headers"]
    assert headers["Authorization"] == "Bearer de_live_test_key"
    assert headers["User-Agent"] == "algenta-python/1.0.0"
    assert headers["X-Algenta-Device-Id"] == "python-async-device-0001"
    assert headers["X-Algenta-Hostname-Hash"]
    assert headers["X-Algenta-SDK-Version"] == "algenta-python/1.0.0"


def test_sync_client_rejects_invalid_env_device_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("decision_engine.client_facade")
    monkeypatch.setenv("ALGENTA_DEVICE_ID", "short")
    monkeypatch.setattr(
        module,
        "_get_httpx",
        lambda: SimpleNamespace(Client=lambda **kwargs: kwargs),
    )

    client = module.DecisionEngineClient(
        api_key="de_live_test_key",
        base_url="https://example.test",
    )

    with pytest.raises(ValueError, match="ALGENTA_DEVICE_ID"):
        client._build_http_client()


def test_build_device_headers_uses_machine_seed_when_hostname_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("decision_engine.device_headers")
    monkeypatch.delenv("ALGENTA_DEVICE_ID", raising=False)
    monkeypatch.delenv("DE_DEVICE_ID", raising=False)
    monkeypatch.setattr(module.platform, "node", lambda: "")
    monkeypatch.setattr(module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(module, "_read_linux_machine_id", lambda: "python-machine-seed")

    headers = module.build_device_headers(
        sdk_version="algenta-python/1.0.0",
        user_agent="algenta-python/1.0.0",
    )

    assert headers["X-Algenta-Device-Id"]
    assert headers["X-Algenta-Hostname-Hash"]


def test_build_device_headers_keeps_hostname_hash_with_explicit_env_device_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("decision_engine.device_headers")
    monkeypatch.setenv("ALGENTA_DEVICE_ID", "python-device-0001")
    monkeypatch.setattr(module.platform, "node", lambda: "")
    monkeypatch.setattr(module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(module, "_read_linux_machine_id", lambda: "python-machine-seed")

    headers = module.build_device_headers(
        sdk_version="algenta-python/1.0.0",
        user_agent="algenta-python/1.0.0",
    )

    assert headers["X-Algenta-Device-Id"] == "python-device-0001"
    assert headers["X-Algenta-Hostname-Hash"]
