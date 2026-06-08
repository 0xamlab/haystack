"""Tests for test_llm_api_service: list_llm_b.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-2/tests/test_llm_api_service.py during modularization.
"""
from __future__ import annotations

from tests._test_llm_api_service_helpers import *  # noqa: F401,F403


def test_list_llm_model_descriptors_respects_disabled_router_fallback_in_resolved_metadata(
    monkeypatch,
) -> None:
    monkeypatch.setattr(llm_api_service, "list_public_runtime_library_descriptors", lambda: ())
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(
            status="ok",
            engine="mojo",
            module_count=0,
            runtime_available=True,
        ),
    )
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.primary",
                    "backend": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "model_name": "gpt-4o-mini",
                    "api_key_env": "OPENAI_API_KEY",
                    "header_envs": {"OpenAI-Organization": "OPENAI_ORG_ID"},
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.backup",
                    "backend": "openai_compatible",
                    "base_url": "https://provider.test/v1",
                    "model_name": "gpt-4.1-mini",
                    "api_key_env": "BACKUP_API_KEY",
                    "header_envs": {"X-Provider-Tenant": "BACKUP_TENANT_ID"},
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.router",
                    "backend": "router",
                    "capabilities": ["chat_completions"],
                    "targets": ["provider.primary", "provider.backup"],
                    "fallback_policy": "disabled",
                },
            ]
        ),
    )
    llm_api_service.llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        descriptors = llm_api_service.list_llm_model_descriptors()
    finally:
        llm_api_service.llm_provider_service.load_provider_model_configs.cache_clear()

    router_descriptor = next(
        descriptor for descriptor in descriptors if descriptor.model_id == "provider.router"
    )
    assert router_descriptor.routing_targets == ("provider.primary", "provider.backup")
    assert router_descriptor.resolved_routing_targets == ("provider.primary",)
    assert router_descriptor.resolved_chat_routing_targets == ("provider.primary",)
    assert router_descriptor.required_provider_headers == ("OpenAI-Organization",)
    assert router_descriptor.provider_auth_env_vars == ("OPENAI_API_KEY", "OPENAI_ORG_ID")


def test_list_llm_model_descriptors_disabled_fallback_skips_incapable_targets(
    monkeypatch,
) -> None:
    monkeypatch.setattr(llm_api_service, "list_public_runtime_library_descriptors", lambda: ())
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(
            status="ok",
            engine="mojo",
            module_count=0,
            runtime_available=True,
        ),
    )
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.fast",
                    "backend": "groq",
                    "base_url": "https://api.groq.com/openai/v1",
                    "model_name": "llama-3.3-70b-versatile",
                    "api_key_env": "GROQ_API_KEY",
                    "header_envs": {"X-Groq-Team": "GROQ_TEAM_ID"},
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.embedder",
                    "backend": "openai_compatible",
                    "base_url": "https://provider.test/v1",
                    "model_name": "text-embedding-3-small",
                    "api_key_env": "OPENAI_API_KEY",
                    "header_envs": {"X-Provider-Tenant": "OPENAI_TENANT_ID"},
                    "capabilities": ["embeddings"],
                },
                {
                    "id": "provider.router",
                    "backend": "router",
                    "capabilities": ["chat_completions", "embeddings"],
                    "targets": ["provider.fast", "provider.embedder"],
                    "fallback_policy": "disabled",
                },
            ]
        ),
    )
    llm_api_service.llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        descriptors = llm_api_service.list_llm_model_descriptors()
    finally:
        llm_api_service.llm_provider_service.load_provider_model_configs.cache_clear()

    router_descriptor = next(
        descriptor for descriptor in descriptors if descriptor.model_id == "provider.router"
    )
    assert router_descriptor.routing_targets == ("provider.fast", "provider.embedder")
    assert router_descriptor.resolved_routing_targets == ("provider.fast", "provider.embedder")
    assert router_descriptor.resolved_chat_routing_targets == ("provider.fast",)
    assert router_descriptor.resolved_embedding_routing_targets == ("provider.embedder",)
    assert router_descriptor.required_provider_headers == (
        "X-Groq-Team",
        "X-Provider-Tenant",
    )
    assert router_descriptor.chat_required_provider_headers == ("X-Groq-Team",)
    assert router_descriptor.embedding_required_provider_headers == ("X-Provider-Tenant",)
    assert router_descriptor.provider_auth_env_vars == (
        "GROQ_API_KEY",
        "GROQ_TEAM_ID",
        "OPENAI_API_KEY",
        "OPENAI_TENANT_ID",
    )
    assert router_descriptor.chat_provider_auth_env_vars == ("GROQ_API_KEY", "GROQ_TEAM_ID")
    assert router_descriptor.embedding_provider_auth_env_vars == (
        "OPENAI_API_KEY",
        "OPENAI_TENANT_ID",
    )
    assert router_descriptor.chat_provider_auth_configured is False
    assert router_descriptor.embedding_provider_auth_configured is False


def test_list_llm_model_descriptors_fails_closed_for_invalid_provider_config(monkeypatch) -> None:
    monkeypatch.setattr(llm_api_service, "list_public_runtime_library_descriptors", lambda: ())
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(
            status="ok",
            engine="mojo",
            module_count=0,
            runtime_available=True,
        ),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "load_provider_model_configs",
        lambda: (_ for _ in ()).throw(ValueError("bad provider config")),
    )

    with pytest.raises(LLMAPIError, match="Provider model configuration is invalid."):
        llm_api_service.list_llm_model_descriptors()


