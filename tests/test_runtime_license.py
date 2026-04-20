from __future__ import annotations

from apps.api_server.config import get_settings
from apps.api_server.services.device_service import _issue_license_jwt
from apps.runtime.license import _parse_token


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
