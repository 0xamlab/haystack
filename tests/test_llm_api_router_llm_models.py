"""Tests for test_llm_api_router: llm_models.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-4/tests/test_llm_api_router.py during modularization.
"""
from __future__ import annotations

from tests._test_llm_api_router_helpers import *  # noqa: F401,F403


def test_llm_models_route_requires_authentication() -> None:
    async def _fake_db():
        yield object()

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.get("/v1/models")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_llm_models_route_lists_truthful_tokenizer_catalog(monkeypatch) -> None:
    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(
        llm_router,
        "list_llm_model_descriptors",
        lambda: (_tokenizer_model_descriptor(),),
    )
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.get("/v1/models")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["object"] == "list"
    assert payload["data"] == [
        {
            "id": "text.tokenizer",
            "object": "model",
            "owned_by": "algenta",
            "runtime_module": "text.tokenizer",
            "description": "Deterministic word tokenizer backed by the runtime library catalog.",
            "capabilities": ["tokenize", "count_tokens", "chat_completions"],
            "supported_endpoints": [
                "/v1/models",
                "/v1/tokenize",
                "/v1/count_tokens",
                "/v1/chat/completions",
                "/v1/responses",
            ],
            "runtime_functions": ["word_tokenize", "sentence_tokenize"],
            "tokenizer_kind": "word",
            "similarity_metric": None,
            "provider_backend": None,
            "routing_targets": [],
            "resolved_routing_targets": [],
            "chat_routing_targets": [],
            "resolved_chat_routing_targets": [],
            "embedding_routing_targets": [],
            "resolved_embedding_routing_targets": [],
            "routing_fallback_policy": None,
            "chat_routing_fallback_policy": None,
            "embedding_routing_fallback_policy": None,
            "routing_fallback_on": [],
            "chat_routing_fallback_on": [],
            "embedding_routing_fallback_on": [],
            "routing_max_attempts": None,
            "chat_routing_max_attempts": None,
            "embedding_routing_max_attempts": None,
            "timeout_seconds": None,
            "chat_timeout_seconds": None,
            "embedding_timeout_seconds": None,
            "required_provider_headers": [],
            "chat_required_provider_headers": [],
            "embedding_required_provider_headers": [],
            "provider_auth_env_vars": [],
            "chat_provider_auth_env_vars": [],
            "embedding_provider_auth_env_vars": [],
            "provider_auth_configured": False,
            "chat_provider_auth_configured": False,
            "embedding_provider_auth_configured": False,
            "bridge_cache_root": "/tmp/algenta-hf-cache",
            "bridge_auth_env_vars": ["HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"],
            "bridge_auth_configured": True,
            "bridge_tokenizer_backends": ["tiktoken", "sentencepiece"],
            "bridge_artifact_backends": ["safetensors", "huggingface_hub"],
            "available": True,
        }
    ]


def test_llm_models_route_surfaces_router_target_metadata(monkeypatch) -> None:
    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(
        llm_router,
        "list_llm_model_descriptors",
        lambda: (
            LLMModelDescriptor(
                model_id="provider.router",
                runtime_module="provider.router",
                description="Ordered provider router alias.",
                capabilities=("chat_completions", "embeddings"),
                supported_endpoints=(
                    "/v1/models",
                    "/v1/chat/completions",
                    "/v1/embeddings",
                    "/v1/responses",
                ),
                runtime_functions=(),
                tokenizer_kind=None,
                similarity_metric=None,
                provider_backend="router",
                routing_targets=(),
                resolved_routing_targets=(),
                chat_routing_targets=("provider.fast", "provider.primary"),
                resolved_chat_routing_targets=("provider.fast", "provider.primary"),
                embedding_routing_targets=("provider.embedder", "provider.primary"),
                resolved_embedding_routing_targets=("provider.embedder", "provider.primary"),
                routing_fallback_policy="disabled",
                chat_routing_fallback_policy="retryable_only",
                embedding_routing_fallback_policy="disabled",
                routing_fallback_on=("provider_timeout",),
                chat_routing_fallback_on=("provider_rate_limited",),
                embedding_routing_fallback_on=("provider_backend_error",),
                routing_max_attempts=2,
                chat_routing_max_attempts=1,
                embedding_routing_max_attempts=2,
                timeout_seconds=18.0,
                chat_timeout_seconds=12.5,
                embedding_timeout_seconds=9.0,
                required_provider_headers=("OpenAI-Organization",),
                chat_required_provider_headers=("X-Groq-Team",),
                embedding_required_provider_headers=("OpenAI-Organization",),
                provider_auth_env_vars=("GROQ_API_KEY", "OPENAI_API_KEY", "OPENAI_ORG_ID"),
                chat_provider_auth_env_vars=("GROQ_API_KEY", "GROQ_TEAM_ID"),
                embedding_provider_auth_env_vars=("OPENAI_API_KEY", "OPENAI_ORG_ID"),
                provider_auth_configured=True,
                chat_provider_auth_configured=True,
                embedding_provider_auth_configured=False,
                bridge_cache_root=None,
                bridge_auth_env_vars=(),
                bridge_auth_configured=False,
                bridge_tokenizer_backends=(),
                bridge_artifact_backends=(),
                available=True,
            ),
        ),
    )
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.get("/v1/models")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"][0]["provider_backend"] == "router"
    assert payload["data"][0]["routing_targets"] == []
    assert payload["data"][0]["resolved_routing_targets"] == []
    assert payload["data"][0]["chat_routing_targets"] == ["provider.fast", "provider.primary"]
    assert payload["data"][0]["resolved_chat_routing_targets"] == [
        "provider.fast",
        "provider.primary",
    ]
    assert payload["data"][0]["embedding_routing_targets"] == [
        "provider.embedder",
        "provider.primary",
    ]
    assert payload["data"][0]["resolved_embedding_routing_targets"] == [
        "provider.embedder",
        "provider.primary",
    ]
    assert payload["data"][0]["routing_fallback_policy"] == "disabled"
    assert payload["data"][0]["chat_routing_fallback_policy"] == "retryable_only"
    assert payload["data"][0]["embedding_routing_fallback_policy"] == "disabled"
    assert payload["data"][0]["routing_fallback_on"] == ["provider_timeout"]
    assert payload["data"][0]["chat_routing_fallback_on"] == ["provider_rate_limited"]
    assert payload["data"][0]["embedding_routing_fallback_on"] == ["provider_backend_error"]
    assert payload["data"][0]["routing_max_attempts"] == 2
    assert payload["data"][0]["chat_routing_max_attempts"] == 1
    assert payload["data"][0]["embedding_routing_max_attempts"] == 2
    assert payload["data"][0]["timeout_seconds"] == 18.0
    assert payload["data"][0]["chat_timeout_seconds"] == 12.5
    assert payload["data"][0]["embedding_timeout_seconds"] == 9.0
    assert payload["data"][0]["required_provider_headers"] == ["OpenAI-Organization"]
    assert payload["data"][0]["chat_required_provider_headers"] == ["X-Groq-Team"]
    assert payload["data"][0]["embedding_required_provider_headers"] == [
        "OpenAI-Organization"
    ]
    assert payload["data"][0]["provider_auth_env_vars"] == [
        "GROQ_API_KEY",
        "OPENAI_API_KEY",
        "OPENAI_ORG_ID",
    ]
    assert payload["data"][0]["chat_provider_auth_env_vars"] == [
        "GROQ_API_KEY",
        "GROQ_TEAM_ID",
    ]
    assert payload["data"][0]["embedding_provider_auth_env_vars"] == [
        "OPENAI_API_KEY",
        "OPENAI_ORG_ID",
    ]
    assert payload["data"][0]["provider_auth_configured"] is True
    assert payload["data"][0]["chat_provider_auth_configured"] is True
    assert payload["data"][0]["embedding_provider_auth_configured"] is False


