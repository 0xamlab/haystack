from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
for path in (str(ROOT), str(PYTHON_SDK), str(ALGENTA_CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)

from examples.shared.privacy_profile import resolve_example_api_base_url, resolve_example_api_key


def _load_module(module_name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / relative_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_example_api_base_url_defaults_to_cloud_managed() -> None:
    assert (
        resolve_example_api_base_url(
            component="Example contract test",
            env={},
        )
        == "https://api.codna.ai"
    )


def test_resolve_example_api_base_url_rejects_hosted_default_in_private_profile() -> None:
    with pytest.raises(ValueError, match="cannot target Codna-owned cloud URLs"):
        resolve_example_api_base_url(
            component="Example contract test",
            env={
                "ALGENTA_DEPLOYMENT_MODE": "self_hosted",
                "ALGENTA_DISABLE_CLOUD": "1",
            },
        )


def test_resolve_example_api_base_url_accepts_algenta_api_url_fallback() -> None:
    assert (
        resolve_example_api_base_url(
            component="Example contract test",
            env={
                "ALGENTA_DEPLOYMENT_MODE": "self_hosted",
                "ALGENTA_DISABLE_CLOUD": "1",
                "ALGENTA_API_URL": "http://localhost:8002",
            },
        )
        == "http://localhost:8002"
    )


def test_resolve_example_api_key_prefers_algenta_env_then_legacy_env() -> None:
    assert (
        resolve_example_api_key(
            component="Example contract test",
            env={
                "ALGENTA_API_KEY": "algenta-key",
                "DE_API_KEY": "legacy-key",
            },
        )
        == "algenta-key"
    )


def test_resolve_example_api_key_accepts_legacy_env_when_canonical_env_is_absent() -> None:
    assert (
        resolve_example_api_key(
            component="Example contract test",
            env={"DE_API_KEY": "legacy-key"},
        )
        == "legacy-key"
    )


def test_resolve_example_api_key_requires_configured_api_key() -> None:
    with pytest.raises(ValueError, match="ALGENTA_API_KEY or DE_API_KEY"):
        resolve_example_api_key(
            component="Example contract test",
            env={},
        )


def test_multihop_python_public_client_uses_privacy_aware_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module(
        "multihop_public_client_example",
        "examples/multi-hop/python_public_client_flow.py",
    )
    captured: dict[str, str] = {}

    class _FakeClient:
        def __init__(self, *, api_key: str, base_url: str) -> None:
            captured["api_key"] = api_key
            captured["base_url"] = base_url

    monkeypatch.setattr(module, "AlgentaClient", _FakeClient)
    monkeypatch.setenv("ALGENTA_API_KEY", "de_test_example")
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.setenv("ALGENTA_BASE_URL", "http://localhost:8000")
    monkeypatch.delenv("DE_BASE_URL", raising=False)

    module._client()

    assert captured == {
        "api_key": "de_test_example",
        "base_url": "http://localhost:8000",
    }


def test_multihop_python_public_client_accepts_legacy_api_key_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module(
        "multihop_public_client_example_legacy_env",
        "examples/multi-hop/python_public_client_flow.py",
    )
    captured: dict[str, str] = {}

    class _FakeClient:
        def __init__(self, *, api_key: str, base_url: str) -> None:
            captured["api_key"] = api_key
            captured["base_url"] = base_url

    monkeypatch.setattr(module, "AlgentaClient", _FakeClient)
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.setenv("DE_API_KEY", "de_legacy_example")
    monkeypatch.delenv("ALGENTA_DEPLOYMENT_MODE", raising=False)
    monkeypatch.delenv("ALGENTA_DISABLE_CLOUD", raising=False)
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)

    module._client()

    assert captured == {
        "api_key": "de_legacy_example",
        "base_url": "https://api.codna.ai",
    }


def test_python_runtime_library_example_runtime_config_accepts_legacy_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module(
        "multihop_runtime_library_example_legacy_env",
        "examples/multi-hop/python_runtime_library_flow.py",
    )
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.setenv("DE_API_KEY", "de_legacy_example")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.setenv("DE_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("ALGENTA_AUTO_START_DAEMON", "0")

    assert module._runtime_config() == {
        "mode": "local",
        "auto_start_daemon": False,
        "api_key": "de_legacy_example",
        "base_url": "http://localhost:8000",
    }


def test_python_runtime_library_example_runtime_config_accepts_algenta_api_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module(
        "multihop_runtime_library_example_algenta_api_url",
        "examples/multi-hop/python_runtime_library_flow.py",
    )
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.setenv("DE_API_KEY", "de_legacy_example")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.setenv("ALGENTA_API_URL", "http://localhost:8002")
    monkeypatch.setenv("ALGENTA_AUTO_START_DAEMON", "0")

    assert module._runtime_config() == {
        "mode": "local",
        "auto_start_daemon": False,
        "api_key": "de_legacy_example",
        "base_url": "http://localhost:8002",
    }


def test_langgraph_example_defaults_to_localhost() -> None:
    module = _load_module(
        "langgraph_example_privacy",
        "examples/langgraph/decision_tool.py",
    )
    original_environ = os.environ.copy()
    try:
        for key in ("ALGENTA_DEPLOYMENT_MODE", "ALGENTA_DISABLE_CLOUD", "ALGENTA_BASE_URL", "DE_BASE_URL"):
            os.environ.pop(key, None)
        assert module._resolve_base_url() == "http://localhost:8000"
    finally:
        os.environ.clear()
        os.environ.update(original_environ)


def test_langgraph_example_rejects_algenta_cloud_in_private_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module(
        "langgraph_example_privacy_fail_closed",
        "examples/langgraph/decision_tool.py",
    )
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.setenv("ALGENTA_BASE_URL", "https://api.codna.ai")

    with pytest.raises(ValueError, match="cannot target Codna-owned cloud URLs"):
        module._resolve_base_url()
