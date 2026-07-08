"""Dynamic model discovery: a provider entry with model_name "*" discovers its backend's live models via
the provider's list-models API — egress-guarded (GET), TTL-cached, best-effort, routable as <entry>:<model>.

Mirrors test_llm_provider_egress.py's monkeypatch style (no respx): stub egress_guard.async_http_request.
"""
from __future__ import annotations

import json

import pytest

from apps.api_server.services import egress_guard, llm_provider_service
from apps.api_server.services.llm_provider_service._config import ProviderModelConfig
from apps.api_server.services.llm_provider_service import _discovery
from apps.api_server.services.llm_provider_service._discovery import (
    _parse_models,
    discover_provider_models,
    discovered_model_id,
    is_discovery_entry,
    resolve_discovered_model,
)
from apps.api_server.services.llm_provider_service._http_layer import get_configured_provider_model


def _discovery_config(backend: str = "openai", base_url: str = "https://provider.example/v1") -> ProviderModelConfig:
    return ProviderModelConfig(
        model_id=f"provider.{backend}",
        backend=backend,
        base_url=base_url,
        upstream_model="*",  # the discovery sentinel
        api_key_env=None,  # no env key needed → auth headers are Content-Type only
        description="",
        capabilities=("chat_completions", "embeddings"),
    )


class _FakeResponse:
    def __init__(self, body: dict, status: int = 200):
        self.status_code = status
        self._body = body

    def json(self) -> dict:
        return self._body

    @property
    def text(self) -> str:
        return json.dumps(self._body)


@pytest.fixture(autouse=True)
def _clear(monkeypatch):
    _discovery.clear_discovery_cache()
    yield
    _discovery.clear_discovery_cache()


# ── per-backend response parsing ─────────────────────────────────────────────────
def test_parse_models_openai_shape():
    assert _parse_models("openai", {"data": [{"id": "gpt-5"}, {"id": "gpt-5-mini"}, {"id": ""}]}) == ["gpt-5", "gpt-5-mini"]


def test_parse_models_ollama_shape():
    assert _parse_models("ollama", {"models": [{"name": "gemma3:latest"}, {"model": "llama3"}]}) == ["gemma3:latest", "llama3"]


def test_parse_models_google_native_strips_prefix():
    data = {"models": [{"name": "models/gemini-3-flash"}, {"name": "models/text-embedding-004"}]}
    assert _parse_models("google_genai", data) == ["gemini-3-flash", "text-embedding-004"]


def test_parse_models_dedups_preserving_order():
    assert _parse_models("openai", {"data": [{"id": "a"}, {"id": "b"}, {"id": "a"}]}) == ["a", "b"]


# ── discovery routes through the egress guard as a GET ────────────────────────────
async def test_discover_routes_through_egress_as_get(monkeypatch):
    captured = {}

    async def _fake(**kwargs):
        captured.update(kwargs)
        return _FakeResponse({"data": [{"id": "gpt-5"}, {"id": "o4-mini"}]})

    monkeypatch.setattr(egress_guard, "async_http_request", _fake)
    models = await discover_provider_models(_discovery_config("openai"))
    assert models == ["gpt-5", "o4-mini"]
    assert captured["method"] == "GET"
    assert captured["url"] == "https://provider.example/v1/models"
    assert captured["surface"] == "llm_provider_discover"
    assert captured["egress_class"] == "customer_connector"
    assert captured["explicit_configured"] is True
    assert "json" not in captured  # GET has no body


async def test_discover_ollama_uses_tags_endpoint(monkeypatch):
    captured = {}

    async def _fake(**kwargs):
        captured.update(kwargs)
        return _FakeResponse({"models": [{"name": "gemma3"}]})

    monkeypatch.setattr(egress_guard, "async_http_request", _fake)
    models = await discover_provider_models(_discovery_config("ollama", "http://127.0.0.1:11434"))
    assert models == ["gemma3"]
    assert captured["url"] == "http://127.0.0.1:11434/api/tags"


# ── caching + best-effort ────────────────────────────────────────────────────────
async def test_discover_is_cached(monkeypatch):
    calls = {"n": 0}

    async def _fake(**kwargs):
        calls["n"] += 1
        return _FakeResponse({"data": [{"id": "gpt-5"}]})

    monkeypatch.setattr(egress_guard, "async_http_request", _fake)
    cfg = _discovery_config("openai")
    await discover_provider_models(cfg, now=1000.0)
    await discover_provider_models(cfg, now=1000.0)  # within TTL → no second HTTP
    assert calls["n"] == 1


async def test_discover_best_effort_on_failure(monkeypatch):
    async def _boom(**kwargs):
        raise egress_guard.EgressPolicyDeniedError("denied")

    monkeypatch.setattr(egress_guard, "async_http_request", _boom)
    # A provider/egress failure must degrade to [] — never raise (the catalog must not 500).
    assert await discover_provider_models(_discovery_config("openai")) == []


# ── namespaced routing ───────────────────────────────────────────────────────────
def _set_registry(monkeypatch, entries: list[dict]):
    monkeypatch.setenv("ALGENTA_LLM_PROVIDER_MODELS_JSON", json.dumps(entries))
    llm_provider_service.load_provider_model_configs.cache_clear()


def test_resolve_discovered_model(monkeypatch):
    _set_registry(monkeypatch, [
        {"id": "provider.openai", "backend": "openai", "model_name": "*",
         "base_url": "https://api.openai.com/v1", "api_key_env": "OPENAI_API_KEY"},
    ])
    resolved = resolve_discovered_model("provider.openai:gpt-5")
    assert resolved is not None
    assert resolved.backend == "openai"
    assert resolved.upstream_model == "gpt-5"          # discovered model becomes the upstream
    assert resolved.model_id == "provider.openai:gpt-5"
    # bare entry id + unknown prefixes don't resolve
    assert resolve_discovered_model("provider.openai") is None
    assert resolve_discovered_model("nope:x") is None
    llm_provider_service.load_provider_model_configs.cache_clear()


def test_get_configured_provider_model_discovery(monkeypatch):
    _set_registry(monkeypatch, [
        {"id": "provider.openai", "backend": "openai", "model_name": "*",
         "base_url": "https://api.openai.com/v1", "api_key_env": "OPENAI_API_KEY"},
        {"id": "provider.pinned", "backend": "openai", "model_name": "gpt-5",
         "base_url": "https://api.openai.com/v1", "api_key_env": "OPENAI_API_KEY"},
    ])
    # the "*" entry itself is NOT a callable model
    assert get_configured_provider_model("provider.openai") is None
    # a discovered child routes to the backend with that upstream
    child = get_configured_provider_model("provider.openai:gpt-5")
    assert child is not None and child.upstream_model == "gpt-5"
    # a normal pinned entry still resolves exactly
    pinned = get_configured_provider_model("provider.pinned")
    assert pinned is not None and pinned.upstream_model == "gpt-5"
    llm_provider_service.load_provider_model_configs.cache_clear()


def test_is_discovery_entry_and_id_helpers():
    assert is_discovery_entry(_discovery_config("openai")) is True
    assert discovered_model_id(_discovery_config("openai"), "gpt-5") == "provider.openai:gpt-5"
