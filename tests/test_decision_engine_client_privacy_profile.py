from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
if str(PYTHON_SDK) not in sys.path:
    sys.path.insert(0, str(PYTHON_SDK))


def test_sync_client_private_profile_requires_self_hosted_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("decision_engine.client_facade")
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.delenv("ALGENTA_API_URL", raising=False)

    with pytest.raises(ValueError) as excinfo:
        module.DecisionEngineClient(api_key="de_test_abc123")

    message = str(excinfo.value)
    assert "private profiles cannot target Codna-owned cloud URLs" in message
    assert "ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL" in message


def test_sync_client_private_profile_uses_env_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("decision_engine.client_facade")
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.setenv("ALGENTA_BASE_URL", "http://localhost:8000")
    monkeypatch.delenv("DE_BASE_URL", raising=False)

    client = module.DecisionEngineClient(api_key="de_test_abc123")

    assert client._base_url == "http://localhost:8000"
    client.close()


def test_async_client_private_profile_requires_self_hosted_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("decision_engine.async_client_facade")
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.delenv("ALGENTA_API_URL", raising=False)

    with pytest.raises(ValueError) as excinfo:
        module.AsyncDecisionEngineClient(api_key="de_test_abc123")

    message = str(excinfo.value)
    assert "private profiles cannot target Codna-owned cloud URLs" in message
    assert "ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL" in message


def test_sync_client_private_profile_accepts_algenta_api_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("decision_engine.client_facade")
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.setenv("ALGENTA_API_URL", "http://localhost:8000")

    client = module.DecisionEngineClient(api_key="de_test_abc123")

    assert client._base_url == "http://localhost:8000"
    client.close()


def test_async_client_private_profile_rejects_algenta_owned_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("decision_engine.async_client_facade")
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")

    with pytest.raises(ValueError, match="private profiles cannot target Codna-owned cloud URLs"):
        module.AsyncDecisionEngineClient(
            api_key="de_test_abc123",
            base_url="https://api.codna.ai",
        )


def test_sync_client_missing_api_key_uses_cloud_managed_dashboard_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("decision_engine.client_facade")
    monkeypatch.delenv("ALGENTA_DEPLOYMENT_MODE", raising=False)
    monkeypatch.delenv("ALGENTA_DISABLE_CLOUD", raising=False)
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.delenv("DE_API_KEY", raising=False)

    with pytest.raises(ValueError, match=r"https://app\.algenta\.ai/dashboard/api-keys"):
        module.DecisionEngineClient(base_url="https://api.codna.ai")


def test_sync_client_missing_api_key_private_profile_uses_self_hosted_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("decision_engine.client_facade")
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.setenv("ALGENTA_BASE_URL", "http://localhost:8000")
    monkeypatch.delenv("ALGENTA_APP_BASE_URL", raising=False)
    monkeypatch.delenv("APP_BASE_URL", raising=False)
    monkeypatch.delenv("DE_APP_BASE_URL", raising=False)
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.delenv("DE_API_KEY", raising=False)

    with pytest.raises(ValueError) as excinfo:
        module.DecisionEngineClient(base_url="http://localhost:8000")

    message = str(excinfo.value)
    assert "ALGENTA_API_KEY / DE_API_KEY environment variables" in message
    assert "self-hosted admin surface or API base URL: http://localhost:8000" in message
    assert "codna.ai/dashboard/api-keys" not in message


def test_async_client_missing_api_key_uses_cloud_managed_dashboard_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("decision_engine.async_client_facade")
    monkeypatch.delenv("ALGENTA_DEPLOYMENT_MODE", raising=False)
    monkeypatch.delenv("ALGENTA_DISABLE_CLOUD", raising=False)
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.delenv("DE_API_KEY", raising=False)

    with pytest.raises(ValueError, match=r"https://app\.algenta\.ai/dashboard/api-keys"):
        module.AsyncDecisionEngineClient(base_url="https://api.codna.ai")


def test_async_client_missing_api_key_private_profile_uses_self_hosted_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("decision_engine.async_client_facade")
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.setenv("ALGENTA_BASE_URL", "http://localhost:8000")
    monkeypatch.delenv("ALGENTA_APP_BASE_URL", raising=False)
    monkeypatch.delenv("APP_BASE_URL", raising=False)
    monkeypatch.delenv("DE_APP_BASE_URL", raising=False)
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.delenv("DE_API_KEY", raising=False)

    with pytest.raises(ValueError) as excinfo:
        module.AsyncDecisionEngineClient(base_url="http://localhost:8000")

    message = str(excinfo.value)
    assert "ALGENTA_API_KEY / DE_API_KEY environment variables" in message
    assert "self-hosted admin surface or API base URL: http://localhost:8000" in message
    assert "codna.ai/dashboard/api-keys" not in message


def test_privacy_profile_console_base_url_requires_explicit_origin_in_private_profiles() -> None:
    module = importlib.import_module("decision_engine.privacy_profile")

    with pytest.raises(ValueError, match="explicit self-hosted dashboard or API base_url"):
        module.resolve_console_base_url(
            component="DecisionEngineClient",
            env={
                "ALGENTA_DEPLOYMENT_MODE": "self_hosted",
                "ALGENTA_DISABLE_CLOUD": "1",
            },
        )


def test_privacy_profile_console_base_url_accepts_legacy_dashboard_alias() -> None:
    module = importlib.import_module("decision_engine.privacy_profile")

    assert (
        module.resolve_console_base_url(
            component="DecisionEngineClient",
            env={
                "ALGENTA_DEPLOYMENT_MODE": "air_gapped",
                "ALGENTA_DISABLE_CLOUD": "1",
                "DE_APP_BASE_URL": "https://console.customer.internal",
            },
        )
        == "https://console.customer.internal"
    )


def test_privacy_profile_console_base_url_rejects_algenta_owned_dashboard_alias() -> None:
    module = importlib.import_module("decision_engine.privacy_profile")

    with pytest.raises(
        ValueError,
        match="ALGENTA_APP_BASE_URL / APP_BASE_URL / DE_APP_BASE_URL or a self-hosted base_url",
    ):
        module.resolve_console_base_url(
            component="DecisionEngineClient",
            env={
                "ALGENTA_DEPLOYMENT_MODE": "self_hosted",
                "ALGENTA_DISABLE_CLOUD": "1",
                "ALGENTA_APP_BASE_URL": "https://app.codna.ai",
            },
        )
