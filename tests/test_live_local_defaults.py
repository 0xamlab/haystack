from tests.integration.live_local_defaults import (
    DEFAULT_LOCAL_LIVE_API_KEY,
    DEFAULT_LOCAL_LIVE_BASE_URL,
    configured_local_live_base_url,
    has_configured_local_live_api_key,
    resolve_local_live_api_key,
    resolve_local_live_base_url,
    should_ignore_hosted_live_credentials,
)


def test_resolve_local_live_api_key_uses_placeholder_when_env_missing() -> None:
    assert resolve_local_live_api_key({}) == DEFAULT_LOCAL_LIVE_API_KEY
    assert has_configured_local_live_api_key({}) is False


def test_resolve_local_live_api_key_uses_explicit_env_value() -> None:
    env = {"DE_API_KEY": "de_live_explicit_test_key_123"}
    assert resolve_local_live_api_key(env) == env["DE_API_KEY"]
    assert has_configured_local_live_api_key(env) is True


def test_explicit_empty_env_mapping_does_not_read_process_env(monkeypatch) -> None:
    monkeypatch.setenv("DE_API_KEY", "de_live_process_env_should_not_leak")

    assert resolve_local_live_api_key({}) == DEFAULT_LOCAL_LIVE_API_KEY
    assert has_configured_local_live_api_key({}) is False


def test_ignore_hosted_live_credentials_forces_local_placeholders() -> None:
    env = {
        "ALGENTA_TEST_IGNORE_HOSTED_LIVE_CREDENTIALS": "1",
        "DE_API_KEY": "de_live_hosted_key_should_not_be_used",
        "DE_BASE_URL": "https://api.algenta.ai",
    }

    assert should_ignore_hosted_live_credentials(env) is True
    assert resolve_local_live_api_key(env) == DEFAULT_LOCAL_LIVE_API_KEY
    assert has_configured_local_live_api_key(env) is False
    assert configured_local_live_base_url(env) is None
    assert resolve_local_live_base_url(env) == DEFAULT_LOCAL_LIVE_BASE_URL
