"""B10 PR10/PR11: per-tenant LLM/engine key resolution seam.

Precedence: per-request/per-run org override (per backend) > (single-tenant) pooled env key. In an
explicit multi-tenant deployment (ALGENTA_REQUIRE_PER_TENANT_KEYS=1) a missing override FAILS CLOSED
— the shared global env key is never reused across tenants. Default (no override, flag off) is
byte-for-byte the current env behavior. PR11 makes the override per-(org, backend) via OrgKeys."""

from __future__ import annotations

import uuid

import pytest

from apps.api_server.services import tenant_keys as tk
from apps.api_server.services.llm_api_service import LLMAPIError
from apps.api_server.services.llm_provider_service._config import ProviderModelConfig
from apps.api_server.services.llm_provider_service._http_layer import _provider_auth_headers
from apps.api_server.services.tenant_keys import OrgKeys


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("ALGENTA_REQUIRE_PER_TENANT_KEYS", raising=False)
    monkeypatch.delenv("MY_KEY", raising=False)
    monkeypatch.delenv("ALGENTA_ENGINE_API_KEY", raising=False)
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)


def _cfg() -> ProviderModelConfig:
    return ProviderModelConfig(
        model_id="m",
        backend="openai",
        base_url="http://provider.example",
        upstream_model="u",
        api_key_env="MY_KEY",
        description="",
        capabilities=(),
    )


def _provider_override(backend: str, key: str):
    return tk.set_org_keys_override(OrgKeys(org_id=uuid.uuid4(), provider_keys={backend: key}))


# --- resolve_provider_api_key ------------------------------------------------------------------


def test_provider_single_tenant_uses_env(monkeypatch):
    monkeypatch.setenv("MY_KEY", "env-key")
    assert tk.resolve_provider_api_key("MY_KEY", "openai") == "env-key"


def test_provider_env_unset_is_none():
    assert tk.resolve_provider_api_key("MY_KEY", "openai") is None


def test_provider_override_wins_then_resets(monkeypatch):
    monkeypatch.setenv("MY_KEY", "env-key")
    token = _provider_override("openai", "org-key")
    try:
        assert tk.resolve_provider_api_key("MY_KEY", "openai") == "org-key"
    finally:
        tk.reset_org_keys_override(token)
    assert tk.resolve_provider_api_key("MY_KEY", "openai") == "env-key"  # back to env after reset


def test_provider_override_is_per_backend(monkeypatch):
    # An org that brought an Anthropic key but uses pooled OpenAI: the anthropic override must NOT
    # satisfy an openai request — that one falls back to the pooled env key.
    monkeypatch.setenv("MY_KEY", "env-openai")
    token = _provider_override("anthropic", "org-anthropic")
    try:
        assert tk.resolve_provider_api_key("ANTHROPIC_KEY", "anthropic") == "org-anthropic"
        assert tk.resolve_provider_api_key("MY_KEY", "openai") == "env-openai"
    finally:
        tk.reset_org_keys_override(token)


def test_provider_multitenant_fails_closed_even_with_env_set(monkeypatch):
    monkeypatch.setenv("ALGENTA_REQUIRE_PER_TENANT_KEYS", "1")
    monkeypatch.setenv("MY_KEY", "env-key")
    assert tk.resolve_provider_api_key("MY_KEY", "openai") is None  # no override -> no shared borrow


def test_provider_multitenant_with_override(monkeypatch):
    monkeypatch.setenv("ALGENTA_REQUIRE_PER_TENANT_KEYS", "1")
    token = _provider_override("openai", "org-key")
    try:
        assert tk.resolve_provider_api_key("MY_KEY", "openai") == "org-key"
    finally:
        tk.reset_org_keys_override(token)


# --- resolve_engine_api_key --------------------------------------------------------------------


def test_engine_single_tenant_uses_env(monkeypatch):
    monkeypatch.setenv("ALGENTA_ENGINE_API_KEY", "engine-env")
    assert tk.resolve_engine_api_key() == "engine-env"


def test_engine_multitenant_fails_closed_even_with_env(monkeypatch):
    monkeypatch.setenv("ALGENTA_REQUIRE_PER_TENANT_KEYS", "1")
    monkeypatch.setenv("ALGENTA_ENGINE_API_KEY", "engine-env")
    assert tk.resolve_engine_api_key() is None


def test_engine_override_wins(monkeypatch):
    monkeypatch.setenv("ALGENTA_ENGINE_API_KEY", "engine-env")
    token = tk.set_org_keys_override(OrgKeys(org_id=uuid.uuid4(), engine_key="org-engine"))
    try:
        assert tk.resolve_engine_api_key() == "org-engine"
    finally:
        tk.reset_org_keys_override(token)


# --- OrgKeys never leaks key material ----------------------------------------------------------


def test_org_keys_repr_redacts_key_material():
    keys = OrgKeys(
        org_id=uuid.uuid4(),
        provider_keys={"openai": "sk-SECRET-VALUE"},
        engine_key="engine-SECRET",
    )
    text = repr(keys)
    assert "sk-SECRET-VALUE" not in text
    assert "engine-SECRET" not in text
    assert "openai" in text and "set" in text  # backends + presence shown, values not


# --- integration: _provider_auth_headers -------------------------------------------------------


def test_auth_headers_single_tenant_env_is_unchanged(monkeypatch):
    monkeypatch.setenv("MY_KEY", "env-key")
    headers = _provider_auth_headers(_cfg())
    assert headers["Authorization"] == "Bearer env-key"


def test_auth_headers_use_per_request_override(monkeypatch):
    token = _provider_override("openai", "org-key")  # env unset (fixture)
    try:
        headers = _provider_auth_headers(_cfg())
        assert headers["Authorization"] == "Bearer org-key"
    finally:
        tk.reset_org_keys_override(token)


def test_auth_headers_fail_closed_in_multitenant_without_override(monkeypatch):
    monkeypatch.setenv("ALGENTA_REQUIRE_PER_TENANT_KEYS", "1")
    monkeypatch.setenv("MY_KEY", "env-key")  # env set, but multi-tenant + no override
    with pytest.raises(LLMAPIError) as excinfo:
        _provider_auth_headers(_cfg())
    assert excinfo.value.code == "backend_unavailable"
