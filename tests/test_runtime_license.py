from __future__ import annotations

import importlib
import io
import json
import sys
import urllib.error
from unittest.mock import patch

from apps.api_server.config import get_settings
from apps.api_server.services.device_service import _issue_license_jwt
from apps.runtime.license import _parse_token


def _reload_runtime_license():
    module_name = "apps.runtime.license"
    if module_name in sys.modules:
        return importlib.reload(sys.modules[module_name])
    return importlib.import_module(module_name)


def test_parse_control_plane_license_with_explicit_signing_secret(monkeypatch):
    monkeypatch.setenv("LICENSE_SIGNING_SECRET", "local-license-secret")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    get_settings.cache_clear()

    token = _issue_license_jwt(
        device_id="device-1234567890",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_test",
    )

    parsed = _parse_token(token, "de_live_test_key")
    assert parsed is not None
    assert parsed.valid is True
    assert parsed.plan == "developer"
    assert parsed.device_id == "device-1234567890"
    assert parsed.device_limit == 5
    assert parsed.source == "control-plane"

    get_settings.cache_clear()


def test_parse_control_plane_license_with_derived_jwt_secret(monkeypatch):
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    get_settings.cache_clear()

    token = _issue_license_jwt(
        device_id="device-abcdefghij",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_test",
    )

    parsed = _parse_token(token, "de_live_test_key")
    assert parsed is not None
    assert parsed.valid is True
    assert parsed.source == "control-plane"

    get_settings.cache_clear()


def test_load_license_prefers_stored_control_plane_token_when_offline(monkeypatch, tmp_path):
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    get_settings.cache_clear()

    license_mod = _reload_runtime_license()
    token = _issue_license_jwt(
        device_id="device-offline-123",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_test",
    )
    license_mod._save_license(token)

    with patch.object(
        license_mod,
        "_exchange_api_key_for_license",
        side_effect=AssertionError("stored license path must not hit control plane"),
    ):
        parsed = license_mod.load_license("de_live_test_key")

    assert parsed.valid is True
    assert parsed.device_id == "device-offline-123"
    assert parsed.source == "control-plane"

    get_settings.cache_clear()


def test_load_license_without_stored_token_blocks_first_time_offline(monkeypatch, tmp_path):
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    get_settings.cache_clear()

    license_mod = _reload_runtime_license()
    with patch.object(license_mod, "_exchange_api_key_for_license", return_value=None):
        parsed = license_mod.load_license("de_live_test_key")

    assert parsed.valid is False
    assert "control plane" in parsed.message.lower()
    assert "reachable control plane" in parsed.message.lower()

    get_settings.cache_clear()


class _FakeHTTPResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeHTTPResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        return self._payload


def test_exchange_api_key_retries_retryable_failures_with_stable_idempotency_key(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    get_settings.cache_clear()

    license_mod = _reload_runtime_license()
    token = _issue_license_jwt(
        device_id="device-retry-123456",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_test",
    )
    payload = json.dumps(
        {
            "license_token": token,
            "plan": "developer",
            "device_count": 1,
            "device_limit": 5,
            "credits_granted": 25,
            "credits_billing_period": "2026-04",
            "credits_expires_at": 4_000_000_000,
        }
    ).encode("utf-8")

    attempts: list[tuple[str, float, str]] = []
    sleep_calls: list[float] = []

    class _Store:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def initialize_sync(
            self,
            *,
            credits_granted: int,
            billing_period: str,
            ttl_seconds: int,
        ) -> None:
            self.calls.append(
                {
                    "credits_granted": credits_granted,
                    "billing_period": billing_period,
                    "ttl_seconds": ttl_seconds,
                }
            )

    store = _Store()

    def fake_urlopen(req, timeout):  # noqa: ANN001
        idempotency_key = next(
            value
            for key, value in req.header_items()
            if key.lower() == "idempotency-key"
        )
        attempts.append((req.full_url, timeout, idempotency_key))
        if len(attempts) == 1:
            raise TimeoutError("timed out")
        if len(attempts) == 2:
            raise urllib.error.HTTPError(
                req.full_url,
                409,
                "Conflict",
                hdrs=None,
                fp=io.BytesIO(
                    json.dumps(
                        {
                            "error": {
                                "code": "resource_write_conflict",
                                "message": "Another write is already in progress.",
                            }
                        }
                    ).encode("utf-8")
                ),
            )
        return _FakeHTTPResponse(payload)

    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
        patch("apps.runtime.credits.get_store", return_value=store),
        patch.object(license_mod.time, "sleep", side_effect=sleep_calls.append),
    ):
        returned = license_mod._exchange_api_key_for_license(
            "de_live_test_key",
            {
                "device_id": "device-retry-123456",
                "platform": "darwin",
                "platform_version": "15.0",
                "hostname_hash": "hosthash",
                "sdk_version": "1.0.0",
            },
        )

    assert returned == token
    assert len(attempts) == 3
    assert all(
        timeout == license_mod._CONTROL_PLANE_TIMEOUT_SECONDS
        for _, timeout, _ in attempts
    )
    assert attempts[0][2] == attempts[1][2] == attempts[2][2]
    assert attempts[0][2].startswith("device-register:")
    assert sleep_calls == [
        license_mod._license_retry_delay_seconds(1),
        license_mod._license_retry_delay_seconds(2),
    ]
    assert len(store.calls) == 1
    assert store.calls[0]["credits_granted"] == 25
    assert store.calls[0]["billing_period"] == "2026-04"
    assert store.calls[0]["ttl_seconds"] > 0

    get_settings.cache_clear()
