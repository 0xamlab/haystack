from tests.integration.live_local_defaults import (
    DEFAULT_LOCAL_LIVE_API_KEY,
    has_configured_local_live_api_key,
    resolve_local_live_api_key,
)


def test_resolve_local_live_api_key_uses_placeholder_when_env_missing() -> None:
    assert resolve_local_live_api_key({}) == DEFAULT_LOCAL_LIVE_API_KEY
    assert has_configured_local_live_api_key({}) is False


def test_resolve_local_live_api_key_uses_explicit_env_value() -> None:
    env = {"DE_API_KEY": "de_live_explicit_test_key_123"}
    assert resolve_local_live_api_key(env) == env["DE_API_KEY"]
    assert has_configured_local_live_api_key(env) is True
