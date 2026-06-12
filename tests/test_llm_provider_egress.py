"""B10 PR1: the LLM provider chokepoint (_provider_post_json) routes through the egress guard.

Every chat + embeddings call funnels through _provider_post_json; routing it through
egress_guard.async_http_request means the self_hosted/air_gapped fail-closed policy + SSRF check
apply to the customer-configured provider base_url. A policy denial surfaces as a typed
LLMAPIError('egress_denied') before any socket opens; an allowlisted host passes through unchanged."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.api_server.config import get_settings
from apps.api_server.services import egress_guard
from apps.api_server.services.llm_api_service import LLMAPIError
from apps.api_server.services.llm_provider_service._config import ProviderModelConfig
from apps.api_server.services.llm_provider_service._http_layer import _provider_post_json

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _config(base_url: str) -> ProviderModelConfig:
    # api_key_env=None -> _provider_auth_headers needs no env key (Content-Type only).
    return ProviderModelConfig(
        model_id="test-model",
        backend="openai",
        base_url=base_url,
        upstream_model="gpt-test",
        api_key_env=None,
        description="",
        capabilities=(),
    )


class _FakeResponse:
    status_code = 200

    def json(self) -> dict:
        return {"ok": True, "choices": []}

    @property
    def text(self) -> str:
        return "{}"


class _RaisingAsyncClient:
    """Constructing this fails the test — proves no socket was opened past a policy deny."""

    def __init__(self, *args, **kwargs):
        raise AssertionError("httpx.AsyncClient must not be constructed when egress is denied")


class _FakeAsyncClient:
    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, **kwargs):
        return _FakeResponse()

    async def request(self, **kwargs):
        return _FakeResponse()


async def _post(config: ProviderModelConfig) -> dict:
    return await _provider_post_json(
        config=config, path="/chat/completions", payload={"x": 1}, timeout_seconds=5.0
    )


async def test_chokepoint_routes_through_egress_guard_with_privacy_params(monkeypatch):
    captured = {}

    async def _fake_async_http_request(**kwargs):
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr(egress_guard, "async_http_request", _fake_async_http_request)

    out = await _post(_config("https://provider.example/v1"))

    assert out == {"ok": True, "choices": []}
    assert captured["method"] == "POST"
    assert captured["url"] == "https://provider.example/v1/chat/completions"
    assert captured["surface"] == "llm_provider_post"
    assert captured["egress_class"] == "customer_connector"
    assert captured["explicit_configured"] is True
    assert captured["json"] == {"x": 1}


async def test_deny_raises_egress_denied_before_socket(monkeypatch):
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "")
    get_settings.cache_clear()
    # if any dispatch is attempted past the deny, constructing the client fails the test
    monkeypatch.setattr(egress_guard.httpx, "AsyncClient", _RaisingAsyncClient)
    try:
        with pytest.raises(LLMAPIError) as excinfo:
            await _post(_config("https://api.unallowlisted-public.example/v1"))
        assert excinfo.value.code == "egress_denied"
    finally:
        get_settings.cache_clear()


async def test_allow_passes_through_when_allowlisted(monkeypatch):
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "*.customer.internal")
    get_settings.cache_clear()
    monkeypatch.setattr(egress_guard.httpx, "AsyncClient", _FakeAsyncClient)
    try:
        out = await _post(_config("https://provider.customer.internal/v1"))
        assert out == {"ok": True, "choices": []}
    finally:
        get_settings.cache_clear()


def test_no_raw_egress_baseline_regression():
    # The raw httpx.AsyncClient line is gone from source AND from the baseline, so a future
    # reintroduction fails the raw_egress guard fatally (the ratchet is live).
    src = (_REPO_ROOT / "apps/api_server/services/llm_provider_service/_http_layer.py").read_text()
    assert "httpx.AsyncClient(" not in src
    baseline = json.loads((_REPO_ROOT / "scripts/reliability_guards/baseline.json").read_text())
    assert not any(
        "_http_layer.py" in entry and "httpx.AsyncClient" in entry
        for entry in baseline.get("raw_egress", [])
    )
