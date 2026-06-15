from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

algenta = importlib.import_module("algenta")
decision = importlib.import_module("algenta.decision")
forecast = importlib.import_module("algenta.forecast")
simulate = importlib.import_module("algenta.simulate")


class _FakeResponse:
    status_code = 200

    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def test_algenta_client_private_profile_requires_self_hosted_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.delenv("ALGENTA_API_URL", raising=False)

    with pytest.raises(ValueError) as excinfo:
        algenta.CodnaClient(api_key="de_test_abc123")

    message = str(excinfo.value)
    assert "private profiles cannot target Codna-owned cloud URLs" in message
    assert "ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL" in message


def test_algenta_client_private_profile_uses_env_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.setenv("ALGENTA_BASE_URL", "http://localhost:8000")
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.delenv("ALGENTA_API_URL", raising=False)

    client = algenta.CodnaClient(api_key="de_test_abc123")

    assert client.base_url == "http://localhost:8000"


def test_algenta_client_private_profile_accepts_algenta_api_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.setenv("ALGENTA_API_URL", "http://localhost:8000")

    client = algenta.CodnaClient(api_key="de_test_abc123")

    assert client.base_url == "http://localhost:8000"


def test_runtime_api_mode_private_profile_requires_self_hosted_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.delenv("ALGENTA_API_URL", raising=False)

    with pytest.raises(ValueError, match="private profiles cannot target Codna-owned cloud URLs"):
        algenta.Runtime(mode="api", api_key="de_test_abc123")


def test_simulate_cloud_mode_uses_env_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.setenv("ALGENTA_BASE_URL", "http://localhost:8000")

    def _post(url, *, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeResponse(
            {
                "metrics": {
                    "expected_value": 100.0,
                    "std_deviation": 10.0,
                    "probability_of_loss": 0.2,
                },
                "percentiles": {
                    "p5": 80.0,
                    "p25": 90.0,
                    "p50": 100.0,
                    "p75": 110.0,
                    "p95": 120.0,
                },
                "scenarios_run": 50,
                "execution_ms": 5,
            }
        )

    monkeypatch.setitem(sys.modules, "httpx", SimpleNamespace(post=_post))

    result = simulate.risk(
        revenue=100.0,
        cost=70.0,
        runs=50,
        mode="cloud",
        api_key="de_test_abc123",
    )

    assert captured["url"] == "http://localhost:8000/v1/simulate"
    assert result.engine == "cloud"


def test_decision_cloud_mode_uses_env_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.setenv("ALGENTA_BASE_URL", "http://localhost:8000")

    def _post(url, *, json, headers, timeout):
        captured["url"] = url
        return _FakeResponse(
            {
                "action": "proceed",
                "confidence": 0.9,
                "reasoning": "good",
                "expected_outcome": 123.0,
                "downside_risk": 80.0,
                "upside_potential": 150.0,
                "probability_of_loss": 0.1,
                "scenarios_evaluated": 100,
            }
        )

    monkeypatch.setitem(sys.modules, "httpx", SimpleNamespace(post=_post))

    result = decision.analyze(
        revenue=100.0,
        cost=70.0,
        runs=100,
        mode="cloud",
        api_key="de_test_abc123",
    )

    assert captured["url"] == "http://localhost:8000/v1/decision"
    assert result.engine == "cloud"


def test_forecast_cloud_mode_requires_self_hosted_base_url_in_private_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.delenv("ALGENTA_API_URL", raising=False)

    with pytest.raises(ValueError, match="private profiles cannot target Codna-owned cloud URLs"):
        forecast.predict(
            [10.0, 12.0, 14.0],
            horizon=3,
            mode="cloud",
            api_key="de_test_abc123",
        )


def test_algenta_client_missing_api_key_uses_cloud_managed_dashboard_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALGENTA_DEPLOYMENT_MODE", raising=False)
    monkeypatch.delenv("ALGENTA_DISABLE_CLOUD", raising=False)
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.delenv("DE_API_KEY", raising=False)

    with pytest.raises(ValueError, match=r"https://app\.algenta\.ai/dashboard/api-keys"):
        algenta.CodnaClient(api_key=None, base_url="https://api.codna.ai")


def test_algenta_client_missing_api_key_private_profile_uses_self_hosted_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.setenv("ALGENTA_BASE_URL", "http://localhost:8000")
    monkeypatch.delenv("ALGENTA_APP_BASE_URL", raising=False)
    monkeypatch.delenv("APP_BASE_URL", raising=False)
    monkeypatch.delenv("DE_APP_BASE_URL", raising=False)
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.delenv("DE_API_KEY", raising=False)

    with pytest.raises(ValueError) as excinfo:
        algenta.CodnaClient(api_key=None, base_url="http://localhost:8000")

    message = str(excinfo.value)
    assert "ALGENTA_API_KEY / DE_API_KEY environment variables" in message
    assert "self-hosted admin surface or API base URL: http://localhost:8000" in message
    assert "codna.ai/dashboard/api-keys" not in message


def test_algenta_privacy_profile_console_base_url_requires_explicit_origin_in_private_profiles() -> None:
    privacy = importlib.import_module("algenta.privacy_profile")

    with pytest.raises(ValueError, match="explicit self-hosted dashboard or API base_url"):
        privacy.resolve_console_base_url(
            component="CodnaClient",
            env={
                "ALGENTA_DEPLOYMENT_MODE": "self_hosted",
                "ALGENTA_DISABLE_CLOUD": "1",
            },
        )


def test_algenta_privacy_profile_console_base_url_accepts_legacy_dashboard_alias() -> None:
    privacy = importlib.import_module("algenta.privacy_profile")

    assert (
        privacy.resolve_console_base_url(
            component="CodnaClient",
            env={
                "ALGENTA_DEPLOYMENT_MODE": "air_gapped",
                "ALGENTA_DISABLE_CLOUD": "1",
                "DE_APP_BASE_URL": "https://console.customer.internal",
            },
        )
        == "https://console.customer.internal"
    )


def test_algenta_privacy_profile_console_base_url_rejects_algenta_owned_dashboard_alias() -> None:
    privacy = importlib.import_module("algenta.privacy_profile")

    with pytest.raises(
        ValueError,
        match="ALGENTA_APP_BASE_URL / APP_BASE_URL / DE_APP_BASE_URL or a self-hosted base_url",
    ):
        privacy.resolve_console_base_url(
            component="CodnaClient",
            env={
                "ALGENTA_DEPLOYMENT_MODE": "self_hosted",
                "ALGENTA_DISABLE_CLOUD": "1",
                "ALGENTA_APP_BASE_URL": "https://app.codna.ai",
            },
        )
