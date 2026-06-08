from __future__ import annotations

from scripts.local_operator_contract import (
    DEFAULT_LOCAL_OPERATOR_BASE_URL,
    resolve_operator_api_key,
    resolve_operator_base_url,
)


def test_resolve_operator_api_key_prefers_explicit_value() -> None:
    env = {"ALGENTA_API_KEY": "algenta-env", "DE_API_KEY": "legacy-env"}
    assert resolve_operator_api_key("explicit-key", env) == "explicit-key"


def test_resolve_operator_api_key_prefers_algenta_env_then_legacy_env() -> None:
    assert resolve_operator_api_key("", {"ALGENTA_API_KEY": "algenta-env", "DE_API_KEY": "legacy"}) == "algenta-env"
    assert resolve_operator_api_key("", {"DE_API_KEY": "legacy-env"}) == "legacy-env"
    assert resolve_operator_api_key("", {}) == ""


def test_resolve_operator_base_url_prefers_explicit_then_env_then_default() -> None:
    env = {
        "ALGENTA_BASE_URL": "https://algenta-base.example",
        "DE_BASE_URL": "https://legacy-base.example",
        "ALGENTA_API_URL": "https://api-url.example",
    }
    assert resolve_operator_base_url("https://explicit.example", env) == "https://explicit.example"
    assert resolve_operator_base_url("", env) == "https://algenta-base.example"
    assert resolve_operator_base_url("", {"DE_BASE_URL": "https://legacy-base.example"}) == "https://legacy-base.example"
    assert resolve_operator_base_url("", {"ALGENTA_API_URL": "https://api-url.example"}) == "https://api-url.example"
    assert resolve_operator_base_url("", {}) == DEFAULT_LOCAL_OPERATOR_BASE_URL


def test_resolve_operator_base_url_can_strip_trailing_slash() -> None:
    env = {"ALGENTA_BASE_URL": "http://localhost:8000/"}
    assert resolve_operator_base_url("", env, strip_trailing_slash=True) == "http://localhost:8000"


def test_resolve_operator_base_url_requires_explicit_origin_in_private_profile() -> None:
    env = {"ALGENTA_DEPLOYMENT_MODE": "self_hosted"}

    try:
        resolve_operator_base_url("", env, surface="verify_live_api.py")
    except ValueError as exc:
        assert "verify_live_api.py private profiles require an explicit self-hosted API origin" in str(exc)
    else:
        raise AssertionError("expected private-profile base URL resolution to fail closed")
