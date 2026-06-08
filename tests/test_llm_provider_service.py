from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from apps.api_server.services import llm_provider_service
from apps.api_server.services.llm_api_service import LLMAPIError


def test_load_provider_model_configs_parses_supported_backends(monkeypatch) -> None:
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.gpt-4o-mini",
                    "backend": "openai_compatible",
                    "base_url": "https://provider.test/v1/",
                    "model_name": "gpt-4o-mini",
                    "api_key_env": "OPENAI_API_KEY",
                    "chat_timeout_seconds": 12.5,
                    "header_envs": {"OpenAI-Organization": "OPENAI_ORG_ID"},
                    "capabilities": ["chat_completions", "embeddings"],
                },
                {
                    "id": "provider.claude-sonnet",
                    "backend": "anthropic",
                    "base_url": "https://api.anthropic.com/v1/",
                    "model_name": "claude-3-5-sonnet-latest",
                    "api_key_env": "ANTHROPIC_API_KEY",
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.ollama-gemma3",
                    "backend": "ollama",
                    "base_url": "http://localhost:11434",
                    "model_name": "gemma3",
                    "capabilities": ["chat_completions", "embeddings"],
                },
                {
                    "id": "provider.gemini-flash",
                    "backend": "google_genai",
                    "base_url": "https://generativelanguage.googleapis.com/v1beta",
                    "model_name": "gemini-2.5-flash",
                    "api_key_env": "GEMINI_API_KEY",
                    "capabilities": ["chat_completions", "embeddings"],
                },
                {
                    "id": "provider.mistral-small",
                    "backend": "mistral",
                    "base_url": "https://api.mistral.ai/v1",
                    "model_name": "mistral-small-latest",
                    "api_key_env": "MISTRAL_API_KEY",
                    "capabilities": ["chat_completions", "embeddings"],
                },
                {
                    "id": "provider.command-a",
                    "backend": "cohere",
                    "base_url": "https://api.cohere.com",
                    "model_name": "command-a-03-2025",
                    "api_key_env": "COHERE_API_KEY",
                    "embedding_input_type": "classification",
                    "capabilities": ["chat_completions", "embeddings"],
                },
                {
                    "id": "provider.groq-llama",
                    "backend": "groq",
                    "base_url": "https://api.groq.com/openai/v1",
                    "model_name": "llama-3.3-70b-versatile",
                    "api_key_env": "GROQ_API_KEY",
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.xai-grok",
                    "backend": "xai",
                    "base_url": "https://api.x.ai/v1",
                    "model_name": "grok-4.3",
                    "api_key_env": "XAI_API_KEY",
                },
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        configs = llm_provider_service.load_provider_model_configs()
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()

    assert len(configs) == 8
    assert configs[0].model_id == "provider.gpt-4o-mini"
    assert configs[0].base_url == "https://provider.test/v1"
    assert configs[0].capabilities == ("chat_completions", "embeddings")
    assert configs[0].chat_timeout_seconds == 12.5
    assert configs[0].header_envs == (("OpenAI-Organization", "OPENAI_ORG_ID"),)
    assert configs[1].backend == "anthropic"
    assert configs[1].base_url == "https://api.anthropic.com/v1"
    assert configs[1].capabilities == ("chat_completions",)
    assert configs[2].backend == "ollama"
    assert configs[2].api_key_env is None
    assert configs[2].base_url == "http://localhost:11434"
    assert configs[2].capabilities == ("chat_completions", "embeddings")
    assert configs[3].backend == "google_genai"
    assert configs[3].api_key_env == "GEMINI_API_KEY"
    assert configs[3].base_url == "https://generativelanguage.googleapis.com/v1beta"
    assert configs[3].capabilities == ("chat_completions", "embeddings")
    assert configs[4].backend == "mistral"
    assert configs[4].api_key_env == "MISTRAL_API_KEY"
    assert configs[4].base_url == "https://api.mistral.ai/v1"
    assert configs[4].capabilities == ("chat_completions", "embeddings")
    assert configs[5].backend == "cohere"
    assert configs[5].api_key_env == "COHERE_API_KEY"
    assert configs[5].base_url == "https://api.cohere.com"
    assert configs[5].capabilities == ("chat_completions", "embeddings")
    assert configs[5].embedding_input_type == "classification"
    assert configs[6].backend == "groq"
    assert configs[6].api_key_env == "GROQ_API_KEY"
    assert configs[6].base_url == "https://api.groq.com/openai/v1"
    assert configs[6].capabilities == ("chat_completions",)
    assert configs[7].backend == "xai"
    assert configs[7].api_key_env == "XAI_API_KEY"
    assert configs[7].base_url == "https://api.x.ai/v1"
    assert configs[7].capabilities == ("chat_completions", "embeddings")


def test_load_provider_model_configs_rejects_conflicting_model_name_and_upstream_model(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.gpt-4o-mini",
                    "backend": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "model_name": "gpt-4o-mini",
                    "upstream_model": "gpt-4.1-mini",
                    "api_key_env": "OPENAI_API_KEY",
                    "capabilities": ["chat_completions", "embeddings"],
                }
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        with pytest.raises(ValueError, match="model_name and .*upstream_model must match"):
            llm_provider_service.load_provider_model_configs()
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()


def test_load_provider_model_configs_defaults_capabilities_from_backend(monkeypatch) -> None:
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.claude-sonnet",
                    "backend": "anthropic",
                    "base_url": "https://api.anthropic.com/v1",
                    "model_name": "claude-3-5-sonnet-latest",
                    "api_key_env": "ANTHROPIC_API_KEY",
                },
                {
                    "id": "provider.command-a",
                    "backend": "cohere",
                    "base_url": "https://api.cohere.com",
                    "model_name": "command-a-03-2025",
                    "api_key_env": "COHERE_API_KEY",
                },
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        configs = llm_provider_service.load_provider_model_configs()
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()

    assert configs[0].capabilities == ("chat_completions",)
    assert configs[1].capabilities == ("chat_completions", "embeddings")


def test_load_provider_model_configs_rejects_reserved_header_env_name(monkeypatch) -> None:
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.gpt-4o-mini",
                    "backend": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "model_name": "gpt-4o-mini",
                    "api_key_env": "OPENAI_API_KEY",
                    "header_envs": {"Authorization": "OPENAI_ALT_AUTH"},
                    "capabilities": ["chat_completions", "embeddings"],
                }
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        with pytest.raises(ValueError, match="cannot override reserved header 'Authorization'"):
            llm_provider_service.load_provider_model_configs()
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()


def test_get_provider_required_auth_env_vars_for_router_unions_targets(monkeypatch) -> None:
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
                    "capabilities": ["chat_completions", "embeddings"],
                },
                {
                    "id": "provider.fast",
                    "backend": "groq",
                    "base_url": "https://api.groq.com/openai/v1",
                    "model_name": "llama-3.3-70b-versatile",
                    "api_key_env": "GROQ_API_KEY",
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.router",
                    "backend": "router",
                    "capabilities": ["chat_completions", "embeddings"],
                    "chat_targets": ["provider.fast", "provider.primary"],
                    "embedding_targets": ["provider.primary"],
                },
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        assert llm_provider_service.get_provider_required_auth_env_vars(
            model_id="provider.router"
        ) == ("GROQ_API_KEY", "OPENAI_API_KEY", "OPENAI_ORG_ID")
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()


def test_get_provider_required_auth_env_vars_for_router_respects_max_attempts(
    monkeypatch,
) -> None:
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
                    "max_attempts": 1,
                },
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        assert llm_provider_service.get_provider_route_targets(
            model_id="provider.router",
            capability="chat_completions",
        ) == (
            llm_provider_service.get_configured_provider_model("provider.primary"),
        )
        assert llm_provider_service.get_provider_required_auth_env_vars(
            model_id="provider.router"
        ) == ("OPENAI_API_KEY", "OPENAI_ORG_ID")
        assert llm_provider_service.get_provider_required_header_names(
            model_id="provider.router"
        ) == ("OpenAI-Organization",)
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()


def test_get_provider_capability_specific_auth_metadata_for_router(monkeypatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "groq-test")
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
                    "capabilities": ["embeddings"],
                },
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
                    "id": "provider.router",
                    "backend": "router",
                    "capabilities": ["chat_completions", "embeddings"],
                    "chat_targets": ["provider.fast"],
                    "embedding_targets": ["provider.primary"],
                },
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        assert llm_provider_service.get_provider_required_header_names_for_capability(
            model_id="provider.router",
            capability="chat_completions",
        ) == ("X-Groq-Team",)
        assert llm_provider_service.get_provider_required_header_names_for_capability(
            model_id="provider.router",
            capability="embeddings",
        ) == ("OpenAI-Organization",)
        assert llm_provider_service.get_provider_required_auth_env_vars_for_capability(
            model_id="provider.router",
            capability="chat_completions",
        ) == ("GROQ_API_KEY", "GROQ_TEAM_ID")
        assert llm_provider_service.get_provider_required_auth_env_vars_for_capability(
            model_id="provider.router",
            capability="embeddings",
        ) == ("OPENAI_API_KEY", "OPENAI_ORG_ID")
        assert (
            llm_provider_service.provider_auth_configured_for_capability(
                model_id="provider.router",
                capability="chat_completions",
            )
            is False
        )
        assert (
            llm_provider_service.provider_auth_configured_for_capability(
                model_id="provider.router",
                capability="embeddings",
            )
            is False
        )
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()


def test_load_provider_model_configs_supports_router_targets(monkeypatch) -> None:
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
                    "capabilities": ["chat_completions", "embeddings"],
                },
                {
                    "id": "provider.fast",
                    "backend": "groq",
                    "base_url": "https://api.groq.com/openai/v1",
                    "model_name": "llama-3.3-70b-versatile",
                    "api_key_env": "GROQ_API_KEY",
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.router",
                    "backend": "router",
                    "capabilities": ["chat_completions", "embeddings"],
                    "targets": ["provider.fast", "provider.primary"],
                    "fallback_policy": "retryable_only",
                },
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        configs = llm_provider_service.load_provider_model_configs()
        route_targets = llm_provider_service.get_provider_route_targets(
            model_id="provider.router",
            capability="chat_completions",
        )
        embedding_targets = llm_provider_service.get_provider_route_targets(
            model_id="provider.router",
            capability="embeddings",
        )
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()

    assert configs[2].backend == "router"
    assert configs[2].routing_targets == ("provider.fast", "provider.primary")
    assert configs[2].routing_fallback_policy == "retryable_only"
    assert configs[2].chat_routing_fallback_policy is None
    assert configs[2].embedding_routing_fallback_policy is None
    assert configs[2].routing_fallback_on == ()
    assert configs[2].chat_routing_fallback_on == ()
    assert configs[2].embedding_routing_fallback_on == ()
    assert [target.model_id for target in route_targets] == [
        "provider.fast",
        "provider.primary",
    ]
    assert [target.model_id for target in embedding_targets] == ["provider.primary"]
    assert llm_provider_service.get_provider_resolved_route_targets(
        model_id="provider.router"
    ) == ("provider.fast", "provider.primary")
    assert llm_provider_service.get_provider_resolved_chat_route_targets(
        model_id="provider.router"
    ) == ("provider.fast", "provider.primary")
    assert llm_provider_service.get_provider_resolved_embedding_route_targets(
        model_id="provider.router"
    ) == ("provider.primary",)


def test_load_provider_model_configs_supports_capability_specific_router_targets(
    monkeypatch,
) -> None:
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
                    "capabilities": ["chat_completions", "embeddings"],
                },
                {
                    "id": "provider.fast",
                    "backend": "groq",
                    "base_url": "https://api.groq.com/openai/v1",
                    "model_name": "llama-3.3-70b-versatile",
                    "api_key_env": "GROQ_API_KEY",
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.embedder",
                    "backend": "openai_compatible",
                    "base_url": "https://provider.test/v1",
                    "model_name": "text-embedding-3-small",
                    "api_key_env": "OPENAI_API_KEY",
                    "capabilities": ["embeddings"],
                },
                {
                    "id": "provider.router",
                    "backend": "router",
                    "capabilities": ["chat_completions", "embeddings"],
                    "chat_targets": ["provider.fast", "provider.primary"],
                    "embedding_targets": ["provider.embedder", "provider.primary"],
                    "fallback_policy": "disabled",
                    "chat_fallback_policy": "retryable_only",
                    "embedding_fallback_policy": "disabled",
                    "fallback_on": ["provider_timeout"],
                    "chat_fallback_on": ["provider_rate_limited"],
                    "max_attempts": 2,
                    "chat_max_attempts": 1,
                    "embedding_max_attempts": 2,
                },
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        configs = llm_provider_service.load_provider_model_configs()
        route_targets = llm_provider_service.get_provider_route_targets(
            model_id="provider.router",
            capability="chat_completions",
        )
        embedding_targets = llm_provider_service.get_provider_route_targets(
            model_id="provider.router",
            capability="embeddings",
        )
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()

    assert configs[3].backend == "router"
    assert configs[3].routing_targets == ()
    assert configs[3].chat_routing_targets == ("provider.fast", "provider.primary")
    assert configs[3].embedding_routing_targets == (
        "provider.embedder",
        "provider.primary",
    )
    assert configs[3].routing_fallback_policy == "disabled"
    assert configs[3].chat_routing_fallback_policy == "retryable_only"
    assert configs[3].embedding_routing_fallback_policy == "disabled"
    assert configs[3].routing_fallback_on == ("provider_timeout",)
    assert configs[3].chat_routing_fallback_on == ("provider_rate_limited",)
    assert configs[3].embedding_routing_fallback_on == ()
    assert configs[3].routing_max_attempts == 2
    assert configs[3].chat_routing_max_attempts == 1
    assert configs[3].embedding_routing_max_attempts == 2
    assert [target.model_id for target in route_targets] == ["provider.fast"]
    assert [target.model_id for target in embedding_targets] == ["provider.embedder"]
    assert llm_provider_service.get_provider_resolved_route_targets(
        model_id="provider.router"
    ) == ("provider.fast", "provider.embedder")
    assert llm_provider_service.get_provider_resolved_chat_route_targets(
        model_id="provider.router"
    ) == ("provider.fast",)
    assert llm_provider_service.get_provider_resolved_embedding_route_targets(
        model_id="provider.router"
    ) == ("provider.embedder",)


def test_load_provider_model_configs_disabled_fallback_skips_incapable_targets(
    monkeypatch,
) -> None:
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
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.embedder",
                    "backend": "openai_compatible",
                    "base_url": "https://provider.test/v1",
                    "model_name": "text-embedding-3-small",
                    "api_key_env": "OPENAI_API_KEY",
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
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        configs = llm_provider_service.load_provider_model_configs()
        chat_targets = llm_provider_service.get_provider_route_targets(
            model_id="provider.router",
            capability="chat_completions",
        )
        embedding_targets = llm_provider_service.get_provider_route_targets(
            model_id="provider.router",
            capability="embeddings",
        )
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()

    assert configs[2].routing_fallback_policy == "disabled"
    assert [target.model_id for target in chat_targets] == ["provider.fast"]
    assert [target.model_id for target in embedding_targets] == ["provider.embedder"]
    assert llm_provider_service.get_provider_resolved_route_targets(
        model_id="provider.router"
    ) == ("provider.fast", "provider.embedder")
    assert llm_provider_service.get_provider_resolved_chat_route_targets(
        model_id="provider.router"
    ) == ("provider.fast",)
    assert llm_provider_service.get_provider_resolved_embedding_route_targets(
        model_id="provider.router"
    ) == ("provider.embedder",)


def test_load_provider_model_configs_rejects_router_without_matching_targets(monkeypatch) -> None:
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
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.router",
                    "backend": "router",
                    "capabilities": ["embeddings"],
                    "targets": ["provider.fast"],
                },
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        with pytest.raises(ValueError, match="has no targets for capability 'embeddings'"):
            llm_provider_service.load_provider_model_configs()
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()


def test_load_provider_model_configs_max_attempts_counts_capability_valid_targets(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.embedder",
                    "backend": "openai_compatible",
                    "base_url": "https://provider.test/v1",
                    "model_name": "text-embedding-3-small",
                    "api_key_env": "OPENAI_API_KEY",
                    "capabilities": ["embeddings"],
                },
                {
                    "id": "provider.primary",
                    "backend": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "model_name": "gpt-4o-mini",
                    "api_key_env": "OPENAI_API_KEY",
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.router",
                    "backend": "router",
                    "capabilities": ["chat_completions"],
                    "targets": ["provider.embedder", "provider.primary"],
                    "max_attempts": 1,
                },
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        configs = llm_provider_service.load_provider_model_configs()
        route_targets = llm_provider_service.get_provider_route_targets(
            model_id="provider.router",
            capability="chat_completions",
        )
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()

    assert configs[2].routing_max_attempts == 1
    assert [target.model_id for target in route_targets] == ["provider.primary"]
    assert llm_provider_service.get_provider_resolved_chat_route_targets(
        model_id="provider.router"
    ) == ("provider.primary",)


def test_load_provider_model_configs_capability_specific_max_attempts_count_capability_valid_targets(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.embedder",
                    "backend": "openai_compatible",
                    "base_url": "https://provider.test/v1",
                    "model_name": "text-embedding-3-small",
                    "api_key_env": "OPENAI_API_KEY",
                    "capabilities": ["embeddings"],
                },
                {
                    "id": "provider.primary",
                    "backend": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "model_name": "gpt-4o-mini",
                    "api_key_env": "OPENAI_API_KEY",
                    "capabilities": ["chat_completions", "embeddings"],
                },
                {
                    "id": "provider.router",
                    "backend": "router",
                    "capabilities": ["chat_completions", "embeddings"],
                    "chat_targets": ["provider.embedder", "provider.primary"],
                    "embedding_targets": ["provider.primary"],
                    "chat_max_attempts": 1,
                },
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        configs = llm_provider_service.load_provider_model_configs()
        route_targets = llm_provider_service.get_provider_route_targets(
            model_id="provider.router",
            capability="chat_completions",
        )
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()

    assert configs[2].chat_routing_max_attempts == 1
    assert [target.model_id for target in route_targets] == ["provider.primary"]
    assert llm_provider_service.get_provider_resolved_chat_route_targets(
        model_id="provider.router"
    ) == ("provider.primary",)


def test_load_provider_model_configs_rejects_capability_targets_for_non_router(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.gpt-4o-mini",
                    "backend": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "model_name": "gpt-4o-mini",
                    "api_key_env": "OPENAI_API_KEY",
                    "chat_targets": ["provider.other"],
                    "capabilities": ["chat_completions", "embeddings"],
                }
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        with pytest.raises(ValueError, match="chat_targets is only supported for backend 'router'"):
            llm_provider_service.load_provider_model_configs()
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()


def test_load_provider_model_configs_rejects_invalid_router_fallback_policy(
    monkeypatch,
) -> None:
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
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.router",
                    "backend": "router",
                    "capabilities": ["chat_completions"],
                    "targets": ["provider.primary"],
                    "fallback_policy": "always",
                },
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        with pytest.raises(ValueError, match="fallback_policy must be one of"):
            llm_provider_service.load_provider_model_configs()
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()


def test_load_provider_model_configs_rejects_capability_specific_fallback_policy_for_missing_capability(
    monkeypatch,
) -> None:
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
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.router",
                    "backend": "router",
                    "capabilities": ["chat_completions"],
                    "targets": ["provider.primary"],
                    "embedding_fallback_policy": "retryable_only",
                },
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        with pytest.raises(ValueError, match="embedding_fallback_policy requires capability 'embeddings'"):
            llm_provider_service.load_provider_model_configs()
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()


def test_load_provider_model_configs_rejects_invalid_router_fallback_on_error_code(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.router",
                    "backend": "router",
                    "capabilities": ["chat_completions"],
                    "targets": ["provider.primary"],
                    "fallback_policy": "retryable_only",
                    "fallback_on": ["invalid_provider_request"],
                }
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        with pytest.raises(ValueError, match="fallback_on.0 must be one of"):
            llm_provider_service.load_provider_model_configs()
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()


def test_load_provider_model_configs_rejects_capability_specific_fallback_on_for_missing_capability(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.router",
                    "backend": "router",
                    "capabilities": ["chat_completions"],
                    "targets": ["provider.primary"],
                    "fallback_policy": "retryable_only",
                    "embedding_fallback_on": ["provider_timeout"],
                }
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        with pytest.raises(ValueError, match="embedding_fallback_on requires capability 'embeddings'"):
            llm_provider_service.load_provider_model_configs()
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()


def test_load_provider_model_configs_rejects_fallback_on_without_retryable_policy(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.router",
                    "backend": "router",
                    "capabilities": ["chat_completions"],
                    "targets": ["provider.primary"],
                    "fallback_policy": "disabled",
                    "fallback_on": ["provider_timeout"],
                }
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        with pytest.raises(ValueError, match="fallback_on requires at least one retryable_only fallback policy"):
            llm_provider_service.load_provider_model_configs()
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()


def test_load_provider_model_configs_rejects_invalid_router_max_attempts(monkeypatch) -> None:
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
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.router",
                    "backend": "router",
                    "capabilities": ["chat_completions"],
                    "targets": ["provider.primary"],
                    "max_attempts": 0,
                },
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        with pytest.raises(ValueError, match="max_attempts must be a positive integer"):
            llm_provider_service.load_provider_model_configs()
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()


def test_load_provider_model_configs_rejects_capability_specific_max_attempts_for_missing_capability(
    monkeypatch,
) -> None:
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
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.router",
                    "backend": "router",
                    "capabilities": ["chat_completions"],
                    "targets": ["provider.primary"],
                    "embedding_max_attempts": 1,
                },
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        with pytest.raises(ValueError, match="embedding_max_attempts requires capability 'embeddings'"):
            llm_provider_service.load_provider_model_configs()
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()


def test_load_provider_model_configs_rejects_capability_specific_timeout_for_missing_capability(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.groq-llama",
                    "backend": "groq",
                    "base_url": "https://api.groq.com/openai/v1",
                    "model_name": "llama-3.3-70b-versatile",
                    "api_key_env": "GROQ_API_KEY",
                    "capabilities": ["chat_completions"],
                    "embedding_timeout_seconds": 9.0,
                }
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        with pytest.raises(ValueError, match="embedding_timeout_seconds requires capability 'embeddings'"):
            llm_provider_service.load_provider_model_configs()
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()


@pytest.mark.anyio
async def test_provider_chat_completion_maps_groq_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.groq-llama",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Provider-backed Groq chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("GROQ_API_KEY", "gq-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "https://api.groq.com/openai/v1/chat/completions"
            assert json == {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": "Summarize"}],
                "stream": False,
            }
            assert headers["Authorization"] == "Bearer gq-test"
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl_groq_123",
                    "choices": [{"message": {"content": "Groq response."}}],
                    "usage": {"prompt_tokens": 6, "completion_tokens": 4},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    result = await llm_provider_service.provider_chat_completion(
        config=config,
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "chatcmpl_groq_123"
    assert result.content == "Groq response."
    assert result.prompt_tokens == 6
    assert result.completion_tokens == 4
    assert result.provider is not None
    assert result.provider.provider_backend == "groq"
    assert result.provider.provider_model_id == "provider.groq-llama"
    assert [(item.provider_backend, item.provider_model_id, item.outcome, item.error_code) for item in result.provider_attempts] == [
        ("groq", "provider.groq-llama", "selected", None)
    ]


@pytest.mark.anyio
async def test_provider_chat_completion_maps_xai_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.xai-grok",
        backend="xai",
        base_url="https://api.x.ai/v1",
        upstream_model="grok-4.3",
        api_key_env="XAI_API_KEY",
        description="Provider-backed xAI chat model.",
        capabilities=("chat_completions", "embeddings"),
    )
    monkeypatch.setenv("XAI_API_KEY", "xai-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "https://api.x.ai/v1/chat/completions"
            assert json == {
                "model": "grok-4.3",
                "messages": [{"role": "user", "content": "Summarize"}],
                "stream": False,
            }
            assert headers["Authorization"] == "Bearer xai-test"
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl_xai_123",
                    "choices": [{"message": {"content": "xAI response."}}],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 4},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    result = await llm_provider_service.provider_chat_completion(
        config=config,
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "chatcmpl_xai_123"
    assert result.content == "xAI response."
    assert result.prompt_tokens == 5
    assert result.completion_tokens == 4
    assert result.provider is not None
    assert result.provider.provider_backend == "xai"
    assert result.provider.provider_model_id == "provider.xai-grok"
    assert [(item.provider_backend, item.provider_model_id, item.outcome, item.error_code) for item in result.provider_attempts] == [
        ("xai", "provider.xai-grok", "selected", None)
    ]


@pytest.mark.anyio
async def test_provider_chat_completion_maps_rate_limit_status_to_retryable_error(
    monkeypatch,
) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.groq-llama",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Provider-backed Groq chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("GROQ_API_KEY", "gq-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            del url, json, headers
            return httpx.Response(429, json={"error": {"message": "rate limited"}})

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    with pytest.raises(LLMAPIError, match="rate limited model") as exc_info:
        await llm_provider_service.provider_chat_completion(
            config=config,
            messages=[{"role": "user", "content": "Summarize"}],
        )
    assert exc_info.value.code == "provider_rate_limited"


@pytest.mark.anyio
async def test_provider_chat_completion_maps_auth_failure_status_to_non_retryable_error(
    monkeypatch,
) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.groq-llama",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Provider-backed Groq chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("GROQ_API_KEY", "gq-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            del url, json, headers
            return httpx.Response(401, json={"error": {"message": "bad key"}})

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    with pytest.raises(LLMAPIError, match="rejected credentials") as exc_info:
        await llm_provider_service.provider_chat_completion(
            config=config,
            messages=[{"role": "user", "content": "Summarize"}],
        )
    assert exc_info.value.code == "provider_authentication_failed"


@pytest.mark.anyio
async def test_provider_chat_completion_maps_invalid_request_status_to_non_retryable_error(
    monkeypatch,
) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.groq-llama",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Provider-backed Groq chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("GROQ_API_KEY", "gq-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            del url, json, headers
            return httpx.Response(400, json={"error": {"message": "bad payload"}})

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    with pytest.raises(LLMAPIError, match="rejected the request") as exc_info:
        await llm_provider_service.provider_chat_completion(
            config=config,
            messages=[{"role": "user", "content": "Summarize"}],
        )
    assert exc_info.value.code == "invalid_provider_request"


@pytest.mark.anyio
async def test_routed_provider_chat_completion_fails_over_retryable_errors(monkeypatch) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.fast", "provider.primary"),
        routing_fallback_policy="disabled",
        chat_routing_fallback_policy="retryable_only",
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.fast",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Fast route",
        capabilities=("chat_completions",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Primary route",
        capabilities=("chat_completions", "embeddings"),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_provider_route_targets",
        lambda **kwargs: (primary, fallback),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: router_config if model_id == "provider.router" else None,
    )

    async def _fake_provider_chat_completion(
        *,
        config: llm_provider_service.ProviderModelConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float | None = None,
    ):
        assert messages == [{"role": "user", "content": "Summarize"}]
        assert timeout_seconds is None
        if config.model_id == "provider.fast":
            raise LLMAPIError(
                "provider_backend_error",
                "transient upstream error",
                {"model": config.model_id},
            )
        return SimpleNamespace(
            completion_id="chatcmpl_fallback_123",
            content="Fallback response.",
            prompt_tokens=4,
            completion_tokens=3,
            provider=SimpleNamespace(
                provider_backend="openai",
                provider_model_id="provider.primary",
            ),
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_chat_completion",
        _fake_provider_chat_completion,
    )

    result = await llm_provider_service.routed_provider_chat_completion(
        model_id="provider.router",
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "chatcmpl_fallback_123"
    assert result.content == "Fallback response."
    assert result.provider.provider_backend == "openai"
    assert result.provider.provider_model_id == "provider.primary"
    assert [
        (item.provider_backend, item.provider_model_id, item.outcome, item.error_code)
        for item in result.provider_attempts
    ] == [
        ("groq", "provider.fast", "failed", "provider_backend_error"),
        ("openai", "provider.primary", "selected", None),
    ]


@pytest.mark.anyio
async def test_routed_provider_chat_completion_fails_over_rate_limited_errors(
    monkeypatch,
) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.fast", "provider.primary"),
        routing_fallback_policy="disabled",
        chat_routing_fallback_policy="retryable_only",
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.fast",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Fast route",
        capabilities=("chat_completions",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Primary route",
        capabilities=("chat_completions", "embeddings"),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_provider_route_targets",
        lambda **kwargs: (primary, fallback),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: router_config if model_id == "provider.router" else None,
    )

    async def _fake_provider_chat_completion(
        *,
        config: llm_provider_service.ProviderModelConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float | None = None,
    ):
        assert messages == [{"role": "user", "content": "Summarize"}]
        assert timeout_seconds is None
        if config.model_id == "provider.fast":
            raise LLMAPIError(
                "provider_rate_limited",
                "provider quota exhausted",
                {"model": config.model_id},
            )
        return SimpleNamespace(
            completion_id="chatcmpl_fallback_123",
            content="Fallback response.",
            prompt_tokens=4,
            completion_tokens=3,
            provider=SimpleNamespace(
                provider_backend="openai",
                provider_model_id="provider.primary",
            ),
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_chat_completion",
        _fake_provider_chat_completion,
    )

    result = await llm_provider_service.routed_provider_chat_completion(
        model_id="provider.router",
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert [
        (item.provider_backend, item.provider_model_id, item.outcome, item.error_code)
        for item in result.provider_attempts
    ] == [
        ("groq", "provider.fast", "failed", "provider_rate_limited"),
        ("openai", "provider.primary", "selected", None),
    ]


@pytest.mark.anyio
async def test_routed_provider_chat_completion_respects_capability_specific_fallback_on(
    monkeypatch,
) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.fast", "provider.primary"),
        chat_routing_fallback_policy="retryable_only",
        chat_routing_fallback_on=("provider_rate_limited",),
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.fast",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Fast route",
        capabilities=("chat_completions",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Primary route",
        capabilities=("chat_completions", "embeddings"),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_provider_route_targets",
        lambda **kwargs: (primary, fallback),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: router_config if model_id == "provider.router" else None,
    )

    async def _fake_provider_chat_completion(
        *,
        config: llm_provider_service.ProviderModelConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float | None = None,
    ):
        assert messages == [{"role": "user", "content": "Summarize"}]
        assert timeout_seconds is None
        if config.model_id == "provider.fast":
            raise LLMAPIError(
                "provider_backend_error",
                "transient upstream error",
                {"model": config.model_id},
            )
        return SimpleNamespace(
            completion_id="chatcmpl_fallback_123",
            content="Fallback response.",
            prompt_tokens=4,
            completion_tokens=3,
            provider=SimpleNamespace(
                provider_backend="openai",
                provider_model_id="provider.primary",
            ),
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_chat_completion",
        _fake_provider_chat_completion,
    )

    with pytest.raises(LLMAPIError, match="transient upstream error"):
        await llm_provider_service.routed_provider_chat_completion(
            model_id="provider.router",
            messages=[{"role": "user", "content": "Summarize"}],
        )


@pytest.mark.anyio
async def test_routed_provider_chat_completion_does_not_fallback_without_explicit_policy(
    monkeypatch,
) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.fast", "provider.primary"),
        routing_fallback_policy="disabled",
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.fast",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Fast route",
        capabilities=("chat_completions",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Primary route",
        capabilities=("chat_completions",),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_provider_route_targets",
        lambda **kwargs: (primary, fallback),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: router_config if model_id == "provider.router" else None,
    )

    async def _fake_provider_chat_completion(
        *,
        config: llm_provider_service.ProviderModelConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float | None = None,
    ):
        assert messages == [{"role": "user", "content": "Summarize"}]
        assert timeout_seconds is None
        if config.model_id == "provider.fast":
            raise LLMAPIError(
                "provider_backend_error",
                "transient upstream error",
                {"model": config.model_id},
            )
        return SimpleNamespace(
            completion_id="chatcmpl_fallback_123",
            content="Fallback response.",
            prompt_tokens=4,
            completion_tokens=3,
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_chat_completion",
        _fake_provider_chat_completion,
    )

    with pytest.raises(LLMAPIError, match="transient upstream error"):
        await llm_provider_service.routed_provider_chat_completion(
            model_id="provider.router",
            messages=[{"role": "user", "content": "Summarize"}],
        )


@pytest.mark.anyio
async def test_routed_provider_chat_completion_does_not_fallback_on_invalid_provider_request(
    monkeypatch,
) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.fast", "provider.primary"),
        routing_fallback_policy="disabled",
        chat_routing_fallback_policy="retryable_only",
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.fast",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Fast route",
        capabilities=("chat_completions",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Primary route",
        capabilities=("chat_completions",),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_provider_route_targets",
        lambda **kwargs: (primary, fallback),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: router_config if model_id == "provider.router" else None,
    )

    async def _fake_provider_chat_completion(
        *,
        config: llm_provider_service.ProviderModelConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float | None = None,
    ):
        assert messages == [{"role": "user", "content": "Summarize"}]
        assert timeout_seconds is None
        if config.model_id == "provider.fast":
            raise LLMAPIError(
                "invalid_provider_request",
                "provider rejected payload",
                {"model": config.model_id},
            )
        pytest.fail("fallback target should not execute for invalid provider requests")

    monkeypatch.setattr(
        llm_provider_service,
        "provider_chat_completion",
        _fake_provider_chat_completion,
    )

    with pytest.raises(LLMAPIError, match="provider rejected payload"):
        await llm_provider_service.routed_provider_chat_completion(
            model_id="provider.router",
            messages=[{"role": "user", "content": "Summarize"}],
        )


@pytest.mark.anyio
async def test_routed_provider_chat_completion_respects_shared_max_attempts(
    monkeypatch,
) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.fast", "provider.primary"),
        routing_fallback_policy="retryable_only",
        routing_max_attempts=1,
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.fast",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Fast route",
        capabilities=("chat_completions",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Primary route",
        capabilities=("chat_completions",),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_provider_route_targets",
        lambda **kwargs: (primary, fallback),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: router_config if model_id == "provider.router" else None,
    )

    seen_targets: list[str] = []

    async def _fake_provider_chat_completion(
        *,
        config: llm_provider_service.ProviderModelConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float | None = None,
    ):
        del messages
        assert timeout_seconds is None
        seen_targets.append(config.model_id)
        raise LLMAPIError(
            "provider_rate_limited",
            "provider quota exhausted",
            {"model": config.model_id},
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_chat_completion",
        _fake_provider_chat_completion,
    )

    with pytest.raises(LLMAPIError, match="All configured provider targets failed"):
        await llm_provider_service.routed_provider_chat_completion(
            model_id="provider.router",
            messages=[{"role": "user", "content": "Summarize"}],
        )

    assert seen_targets == ["provider.fast"]


@pytest.mark.anyio
async def test_routed_provider_chat_completion_uses_router_timeout_override(
    monkeypatch,
) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.fast", "provider.primary"),
        chat_timeout_seconds=7.5,
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.fast",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Fast route",
        capabilities=("chat_completions",),
        chat_timeout_seconds=15.0,
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Primary route",
        capabilities=("chat_completions", "embeddings"),
        chat_timeout_seconds=20.0,
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_provider_route_targets",
        lambda **kwargs: (primary, fallback),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: router_config if model_id == "provider.router" else None,
    )

    async def _fake_provider_chat_completion(
        *,
        config: llm_provider_service.ProviderModelConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float | None = None,
    ):
        assert messages == [{"role": "user", "content": "Summarize"}]
        assert timeout_seconds == 7.5
        return SimpleNamespace(
            completion_id="chatcmpl_router_123",
            content="Router response.",
            prompt_tokens=4,
            completion_tokens=3,
            provider=SimpleNamespace(
                provider_backend=config.backend,
                provider_model_id=config.model_id,
            ),
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_chat_completion",
        _fake_provider_chat_completion,
    )

    result = await llm_provider_service.routed_provider_chat_completion(
        model_id="provider.router",
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "chatcmpl_router_123"


@pytest.mark.anyio
async def test_routed_provider_chat_completion_honors_nested_router_policy(
    monkeypatch,
) -> None:
    outer_router = llm_provider_service.ProviderModelConfig(
        model_id="provider.router.outer",
        backend="router",
        base_url="",
        upstream_model="provider.router.outer",
        api_key_env=None,
        description="Outer router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.router.inner", "provider.primary"),
        routing_fallback_policy="disabled",
    )
    inner_router = llm_provider_service.ProviderModelConfig(
        model_id="provider.router.inner",
        backend="router",
        base_url="",
        upstream_model="provider.router.inner",
        api_key_env=None,
        description="Inner router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.fast", "provider.primary"),
        chat_routing_fallback_policy="retryable_only",
        chat_timeout_seconds=9.5,
    )
    fast = llm_provider_service.ProviderModelConfig(
        model_id="provider.fast",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Fast route",
        capabilities=("chat_completions",),
        chat_timeout_seconds=30.0,
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Primary route",
        capabilities=("chat_completions",),
        chat_timeout_seconds=20.0,
    )
    configs = {
        item.model_id: item
        for item in (outer_router, inner_router, fast, primary)
    }
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: configs.get(model_id),
    )

    seen_calls: list[tuple[str, float | None]] = []

    async def _fake_provider_chat_completion(
        *,
        config: llm_provider_service.ProviderModelConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float | None = None,
    ):
        assert messages == [{"role": "user", "content": "Summarize"}]
        seen_calls.append((config.model_id, timeout_seconds))
        if config.model_id == "provider.fast":
            raise LLMAPIError(
                "provider_rate_limited",
                "provider quota exhausted",
                {"model": config.model_id},
            )
        assert config.model_id == "provider.primary"
        return SimpleNamespace(
            completion_id="chatcmpl_nested_router_123",
            content="Nested router response.",
            prompt_tokens=4,
            completion_tokens=3,
            provider=SimpleNamespace(
                provider_backend="openai",
                provider_model_id="provider.primary",
            ),
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_chat_completion",
        _fake_provider_chat_completion,
    )

    result = await llm_provider_service.routed_provider_chat_completion(
        model_id="provider.router.outer",
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "chatcmpl_nested_router_123"
    assert seen_calls == [("provider.fast", 9.5), ("provider.primary", 9.5)]
    assert [
        (item.provider_backend, item.provider_model_id, item.outcome, item.error_code)
        for item in result.provider_attempts
    ] == [
        ("groq", "provider.fast", "failed", "provider_rate_limited"),
        ("openai", "provider.primary", "selected", None),
    ]


@pytest.mark.anyio
async def test_routed_provider_chat_completion_nested_router_skips_incapable_targets_under_max_attempts(
    monkeypatch,
) -> None:
    outer_router = llm_provider_service.ProviderModelConfig(
        model_id="provider.router.outer",
        backend="router",
        base_url="",
        upstream_model="provider.router.outer",
        api_key_env=None,
        description="Outer router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.embedder", "provider.router.inner"),
        routing_fallback_policy="disabled",
        routing_max_attempts=1,
    )
    inner_router = llm_provider_service.ProviderModelConfig(
        model_id="provider.router.inner",
        backend="router",
        base_url="",
        upstream_model="provider.router.inner",
        api_key_env=None,
        description="Inner router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.primary",),
        routing_fallback_policy="disabled",
    )
    embedder = llm_provider_service.ProviderModelConfig(
        model_id="provider.embedder",
        backend="openai_compatible",
        base_url="https://provider.test/v1",
        upstream_model="text-embedding-3-small",
        api_key_env="OPENAI_API_KEY",
        description="Embeddings-only route",
        capabilities=("embeddings",),
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Primary route",
        capabilities=("chat_completions",),
    )
    configs = {
        item.model_id: item
        for item in (outer_router, inner_router, embedder, primary)
    }
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: configs.get(model_id),
    )

    seen_calls: list[str] = []

    async def _fake_provider_chat_completion(
        *,
        config: llm_provider_service.ProviderModelConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float | None = None,
    ):
        assert messages == [{"role": "user", "content": "Summarize"}]
        seen_calls.append(config.model_id)
        return SimpleNamespace(
            completion_id="chatcmpl_capability_aware_router_123",
            content="Capability-aware nested router response.",
            prompt_tokens=4,
            completion_tokens=3,
            provider=SimpleNamespace(
                provider_backend="openai",
                provider_model_id="provider.primary",
            ),
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_chat_completion",
        _fake_provider_chat_completion,
    )

    result = await llm_provider_service.routed_provider_chat_completion(
        model_id="provider.router.outer",
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "chatcmpl_capability_aware_router_123"
    assert seen_calls == ["provider.primary"]
    assert getattr(result, "provider_attempts", ()) == ()


@pytest.mark.anyio
async def test_routed_provider_embeddings_fails_over_retryable_errors(monkeypatch) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("embeddings",),
        routing_targets=("provider.embed-fast", "provider.embed-primary"),
        routing_fallback_policy="disabled",
        embedding_routing_fallback_policy="retryable_only",
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-fast",
        backend="openai_compatible",
        base_url="https://provider-fast.test/v1",
        upstream_model="text-embedding-fast",
        api_key_env="OPENAI_API_KEY",
        description="Fast embed route",
        capabilities=("embeddings",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="text-embedding-3-small",
        api_key_env="OPENAI_API_KEY",
        description="Primary embed route",
        capabilities=("embeddings",),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_provider_route_targets",
        lambda **kwargs: (primary, fallback),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: router_config if model_id == "provider.router" else None,
    )

    async def _fake_provider_embeddings(
        *,
        config: llm_provider_service.ProviderModelConfig,
        inputs: list[str],
        dimensions: int,
        timeout_seconds: float | None = None,
    ):
        assert inputs == ["hello"]
        assert dimensions == 3
        assert timeout_seconds is None
        if config.model_id == "provider.embed-fast":
            raise LLMAPIError(
                "provider_timeout",
                "transient upstream timeout",
                {"model": config.model_id},
            )
        return (
            [
                SimpleNamespace(
                    index=0,
                    embedding=[0.1, 0.2, 0.3],
                    token_count=2,
                    provider=SimpleNamespace(
                        provider_backend="openai",
                        provider_model_id="provider.embed-primary",
                    ),
                )
            ],
            2,
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_embeddings",
        _fake_provider_embeddings,
    )

    generated, total_tokens = await llm_provider_service.routed_provider_embeddings(
        model_id="provider.router",
        inputs=["hello"],
        dimensions=3,
    )

    assert total_tokens == 2
    assert generated[0].embedding == [0.1, 0.2, 0.3]
    assert generated[0].provider.provider_backend == "openai"
    assert generated[0].provider.provider_model_id == "provider.embed-primary"
    assert [
        (item.provider_backend, item.provider_model_id, item.outcome, item.error_code)
        for item in generated[0].provider_attempts
    ] == [
        ("openai_compatible", "provider.embed-fast", "failed", "provider_timeout"),
        ("openai", "provider.embed-primary", "selected", None),
    ]


@pytest.mark.anyio
async def test_routed_provider_embeddings_disabled_fallback_skips_incapable_targets(
    monkeypatch,
) -> None:
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
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.embedder",
                    "backend": "openai_compatible",
                    "base_url": "https://provider.test/v1",
                    "model_name": "text-embedding-3-small",
                    "api_key_env": "OPENAI_API_KEY",
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
    llm_provider_service.load_provider_model_configs.cache_clear()

    seen_calls: list[str] = []

    async def _fake_provider_embeddings(
        *,
        config: llm_provider_service.ProviderModelConfig,
        inputs: list[str],
        dimensions: int,
        timeout_seconds: float | None = None,
    ):
        assert inputs == ["hello"]
        assert dimensions == 3
        seen_calls.append(config.model_id)
        return (
            [
                SimpleNamespace(
                    index=0,
                    embedding=[0.1, 0.2, 0.3],
                    token_count=2,
                    provider=SimpleNamespace(
                        provider_backend="openai_compatible",
                        provider_model_id=config.model_id,
                    ),
                )
            ],
            2,
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_embeddings",
        _fake_provider_embeddings,
    )

    try:
        generated, total_tokens = await llm_provider_service.routed_provider_embeddings(
            model_id="provider.router",
            inputs=["hello"],
            dimensions=3,
        )
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()

    assert total_tokens == 2
    assert seen_calls == ["provider.embedder"]
    assert generated[0].provider.provider_model_id == "provider.embedder"
    assert getattr(generated[0], "provider_attempts", ()) == ()


@pytest.mark.anyio
async def test_routed_provider_embeddings_does_not_fallback_without_explicit_policy(
    monkeypatch,
) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("embeddings",),
        routing_targets=("provider.embed-fast", "provider.embed-primary"),
        routing_fallback_policy="disabled",
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-fast",
        backend="openai_compatible",
        base_url="https://provider-fast.test/v1",
        upstream_model="text-embedding-fast",
        api_key_env="OPENAI_API_KEY",
        description="Fast embed route",
        capabilities=("embeddings",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="text-embedding-3-small",
        api_key_env="OPENAI_API_KEY",
        description="Primary embed route",
        capabilities=("embeddings",),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_provider_route_targets",
        lambda **kwargs: (primary, fallback),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: router_config if model_id == "provider.router" else None,
    )

    async def _fake_provider_embeddings(
        *,
        config: llm_provider_service.ProviderModelConfig,
        inputs: list[str],
        dimensions: int,
        timeout_seconds: float | None = None,
    ):
        assert inputs == ["hello"]
        assert dimensions == 3
        assert timeout_seconds is None
        if config.model_id == "provider.embed-fast":
            raise LLMAPIError(
                "provider_timeout",
                "transient upstream timeout",
                {"model": config.model_id},
            )
        return (
            [SimpleNamespace(index=0, embedding=[0.1, 0.2, 0.3], token_count=2)],
            2,
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_embeddings",
        _fake_provider_embeddings,
    )

    with pytest.raises(LLMAPIError, match="transient upstream timeout"):
        await llm_provider_service.routed_provider_embeddings(
            model_id="provider.router",
            inputs=["hello"],
            dimensions=3,
        )


@pytest.mark.anyio
async def test_routed_provider_embeddings_uses_shared_fallback_policy_when_capability_override_missing(
    monkeypatch,
) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("chat_completions", "embeddings"),
        routing_targets=("provider.embed-fast", "provider.embed-primary"),
        routing_fallback_policy="retryable_only",
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-fast",
        backend="openai_compatible",
        base_url="https://provider-fast.test/v1",
        upstream_model="text-embedding-fast",
        api_key_env="OPENAI_API_KEY",
        description="Fast embed route",
        capabilities=("embeddings",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="text-embedding-3-small",
        api_key_env="OPENAI_API_KEY",
        description="Primary embed route",
        capabilities=("embeddings",),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_provider_route_targets",
        lambda **kwargs: (primary, fallback),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: router_config if model_id == "provider.router" else None,
    )

    async def _fake_provider_embeddings(
        *,
        config: llm_provider_service.ProviderModelConfig,
        inputs: list[str],
        dimensions: int,
        timeout_seconds: float | None = None,
    ):
        assert inputs == ["hello"]
        assert dimensions == 3
        assert timeout_seconds is None
        if config.model_id == "provider.embed-fast":
            raise LLMAPIError(
                "provider_timeout",
                "transient upstream timeout",
                {"model": config.model_id},
            )
        return (
            [SimpleNamespace(index=0, embedding=[0.1, 0.2, 0.3], token_count=2)],
            2,
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_embeddings",
        _fake_provider_embeddings,
    )

    generated, total_tokens = await llm_provider_service.routed_provider_embeddings(
        model_id="provider.router",
        inputs=["hello"],
        dimensions=3,
    )

    assert total_tokens == 2
    assert generated[0].embedding == [0.1, 0.2, 0.3]
    assert [
        (item.provider_backend, item.provider_model_id, item.outcome, item.error_code)
        for item in generated[0].provider_attempts
    ] == [
        ("openai_compatible", "provider.embed-fast", "failed", "provider_timeout"),
        ("openai", "provider.embed-primary", "selected", None),
    ]


@pytest.mark.anyio
async def test_routed_provider_embeddings_respects_shared_fallback_on(
    monkeypatch,
) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("chat_completions", "embeddings"),
        routing_targets=("provider.embed-fast", "provider.embed-primary"),
        routing_fallback_policy="retryable_only",
        routing_fallback_on=("provider_rate_limited",),
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-fast",
        backend="openai_compatible",
        base_url="https://provider-fast.test/v1",
        upstream_model="text-embedding-fast",
        api_key_env="OPENAI_API_KEY",
        description="Fast embed route",
        capabilities=("embeddings",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="text-embedding-3-small",
        api_key_env="OPENAI_API_KEY",
        description="Primary embed route",
        capabilities=("embeddings",),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_provider_route_targets",
        lambda **kwargs: (primary, fallback),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: router_config if model_id == "provider.router" else None,
    )

    async def _fake_provider_embeddings(
        *,
        config: llm_provider_service.ProviderModelConfig,
        inputs: list[str],
        dimensions: int,
        timeout_seconds: float | None = None,
    ):
        assert inputs == ["hello"]
        assert dimensions == 3
        assert timeout_seconds is None
        if config.model_id == "provider.embed-fast":
            raise LLMAPIError(
                "provider_timeout",
                "transient upstream timeout",
                {"model": config.model_id},
            )
        return (
            [SimpleNamespace(index=0, embedding=[0.1, 0.2, 0.3], token_count=2)],
            2,
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_embeddings",
        _fake_provider_embeddings,
    )

    with pytest.raises(LLMAPIError, match="transient upstream timeout"):
        await llm_provider_service.routed_provider_embeddings(
            model_id="provider.router",
            inputs=["hello"],
            dimensions=3,
        )


@pytest.mark.anyio
async def test_routed_provider_embeddings_respects_capability_specific_max_attempts(
    monkeypatch,
) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("chat_completions", "embeddings"),
        routing_targets=("provider.embed-fast", "provider.embed-primary"),
        routing_fallback_policy="retryable_only",
        embedding_routing_max_attempts=1,
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-fast",
        backend="openai_compatible",
        base_url="https://provider-fast.test/v1",
        upstream_model="text-embedding-fast",
        api_key_env="OPENAI_API_KEY",
        description="Fast embed route",
        capabilities=("embeddings",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="text-embedding-3-small",
        api_key_env="OPENAI_API_KEY",
        description="Primary embed route",
        capabilities=("embeddings",),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_provider_route_targets",
        lambda **kwargs: (primary, fallback),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: router_config if model_id == "provider.router" else None,
    )

    seen_targets: list[str] = []

    async def _fake_provider_embeddings(
        *,
        config: llm_provider_service.ProviderModelConfig,
        inputs: list[str],
        dimensions: int,
        timeout_seconds: float | None = None,
    ):
        del inputs, dimensions
        assert timeout_seconds is None
        seen_targets.append(config.model_id)
        raise LLMAPIError(
            "provider_timeout",
            "transient upstream timeout",
            {"model": config.model_id},
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_embeddings",
        _fake_provider_embeddings,
    )

    with pytest.raises(LLMAPIError, match="All configured provider targets failed"):
        await llm_provider_service.routed_provider_embeddings(
            model_id="provider.router",
            inputs=["hello"],
            dimensions=3,
        )

    assert seen_targets == ["provider.embed-fast"]


@pytest.mark.anyio
async def test_routed_provider_embeddings_honor_nested_router_policy(
    monkeypatch,
) -> None:
    outer_router = llm_provider_service.ProviderModelConfig(
        model_id="provider.router.outer",
        backend="router",
        base_url="",
        upstream_model="provider.router.outer",
        api_key_env=None,
        description="Outer router alias",
        capabilities=("embeddings",),
        routing_targets=("provider.router.inner", "provider.embed-backup"),
        routing_fallback_policy="disabled",
    )
    inner_router = llm_provider_service.ProviderModelConfig(
        model_id="provider.router.inner",
        backend="router",
        base_url="",
        upstream_model="provider.router.inner",
        api_key_env=None,
        description="Inner router alias",
        capabilities=("embeddings",),
        routing_targets=("provider.embed-fast", "provider.embed-primary"),
        embedding_routing_fallback_policy="retryable_only",
        embedding_timeout_seconds=6.25,
    )
    fast = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-fast",
        backend="openai_compatible",
        base_url="https://provider-fast.test/v1",
        upstream_model="text-embedding-fast",
        api_key_env="OPENAI_API_KEY",
        description="Fast embed route",
        capabilities=("embeddings",),
        embedding_timeout_seconds=18.0,
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="text-embedding-3-small",
        api_key_env="OPENAI_API_KEY",
        description="Primary embed route",
        capabilities=("embeddings",),
        embedding_timeout_seconds=22.0,
    )
    backup = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-backup",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="text-embedding-3-small",
        api_key_env="OPENAI_API_KEY",
        description="Backup embed route",
        capabilities=("embeddings",),
    )
    configs = {
        item.model_id: item
        for item in (outer_router, inner_router, fast, primary, backup)
    }
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: configs.get(model_id),
    )

    seen_calls: list[tuple[str, float | None]] = []

    async def _fake_provider_embeddings(
        *,
        config: llm_provider_service.ProviderModelConfig,
        inputs: list[str],
        dimensions: int,
        timeout_seconds: float | None = None,
    ):
        assert inputs == ["hello"]
        assert dimensions == 3
        seen_calls.append((config.model_id, timeout_seconds))
        if config.model_id == "provider.embed-fast":
            raise LLMAPIError(
                "provider_timeout",
                "transient upstream timeout",
                {"model": config.model_id},
            )
        assert config.model_id == "provider.embed-primary"
        return (
            [
                SimpleNamespace(
                    index=0,
                    embedding=[0.1, 0.2, 0.3],
                    token_count=2,
                    provider=SimpleNamespace(
                        provider_backend="openai",
                        provider_model_id="provider.embed-primary",
                    ),
                )
            ],
            2,
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_embeddings",
        _fake_provider_embeddings,
    )

    generated, total_tokens = await llm_provider_service.routed_provider_embeddings(
        model_id="provider.router.outer",
        inputs=["hello"],
        dimensions=3,
    )

    assert total_tokens == 2
    assert seen_calls == [
        ("provider.embed-fast", 6.25),
        ("provider.embed-primary", 6.25),
    ]
    assert [
        (item.provider_backend, item.provider_model_id, item.outcome, item.error_code)
        for item in generated[0].provider_attempts
    ] == [
        ("openai_compatible", "provider.embed-fast", "failed", "provider_timeout"),
        ("openai", "provider.embed-primary", "selected", None),
    ]


def test_load_provider_model_configs_rejects_embedding_input_type_for_non_cohere(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.gpt-4o-mini",
                    "backend": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "model_name": "gpt-4o-mini",
                    "api_key_env": "OPENAI_API_KEY",
                    "embedding_input_type": "classification",
                    "capabilities": ["chat_completions", "embeddings"],
                }
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        with pytest.raises(ValueError, match="embedding_input_type is only supported"):
            llm_provider_service.load_provider_model_configs()
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()


def test_load_provider_model_configs_rejects_unsupported_capabilities(monkeypatch) -> None:
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.gpt-4o-mini",
                    "backend": "openai_compatible",
                    "base_url": "https://provider.test/v1",
                    "api_key_env": "OPENAI_API_KEY",
                    "capabilities": ["responses"],
                }
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        with pytest.raises(ValueError, match="capabilities.0"):
            llm_provider_service.load_provider_model_configs()
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()


def test_load_provider_model_configs_rejects_backend_capability_mismatch(monkeypatch) -> None:
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.claude-sonnet",
                    "backend": "anthropic",
                    "base_url": "https://api.anthropic.com/v1",
                    "api_key_env": "ANTHROPIC_API_KEY",
                    "capabilities": ["embeddings"],
                }
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        with pytest.raises(ValueError, match="unsupported entries for backend 'anthropic'"):
            llm_provider_service.load_provider_model_configs()
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()


@pytest.mark.anyio
async def test_provider_chat_completion_maps_openai_compatible_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.gpt-4o-mini",
        backend="openai_compatible",
        base_url="https://provider.test/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Provider-backed chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "https://provider.test/v1/chat/completions"
            assert json == {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "Summarize"}],
                "stream": False,
            }
            assert headers["Authorization"] == "Bearer sk-test"
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl_provider_123",
                    "choices": [{"message": {"content": "Provider response."}}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 2},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    result = await llm_provider_service.provider_chat_completion(
        config=config,
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "chatcmpl_provider_123"
    assert result.content == "Provider response."
    assert result.prompt_tokens == 3
    assert result.completion_tokens == 2
    assert result.provider is not None
    assert result.provider.provider_backend == "openai_compatible"
    assert result.provider.provider_model_id == "provider.gpt-4o-mini"


@pytest.mark.anyio
async def test_provider_chat_completion_includes_required_header_envs(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.gpt-4o-mini",
        backend="openai_compatible",
        base_url="https://provider.test/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Provider-backed chat model.",
        capabilities=("chat_completions",),
        header_envs=(("OpenAI-Organization", "OPENAI_ORG_ID"),),
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_ORG_ID", "org_test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "https://provider.test/v1/chat/completions"
            assert headers["Authorization"] == "Bearer sk-test"
            assert headers["OpenAI-Organization"] == "org_test"
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl_provider_123",
                    "choices": [{"message": {"content": "Provider response."}}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 2},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    result = await llm_provider_service.provider_chat_completion(
        config=config,
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.provider is not None
    assert result.provider.provider_model_id == "provider.gpt-4o-mini"


@pytest.mark.anyio
async def test_provider_chat_completion_requires_configured_header_env(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.gpt-4o-mini",
        backend="openai_compatible",
        base_url="https://provider.test/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Provider-backed chat model.",
        capabilities=("chat_completions",),
        header_envs=(("OpenAI-Organization", "OPENAI_ORG_ID"),),
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("OPENAI_ORG_ID", raising=False)

    with pytest.raises(LLMAPIError, match="requires header 'OpenAI-Organization'"):
        await llm_provider_service.provider_chat_completion(
            config=config,
            messages=[{"role": "user", "content": "Summarize"}],
        )


@pytest.mark.anyio
async def test_provider_chat_completion_uses_capability_specific_timeout(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.gpt-4o-mini",
        backend="openai_compatible",
        base_url="https://provider.test/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Provider-backed chat model.",
        capabilities=("chat_completions", "embeddings"),
        timeout_seconds=30.0,
        chat_timeout_seconds=12.5,
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            assert kwargs["timeout"] == 12.5

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "https://provider.test/v1/chat/completions"
            assert json["model"] == "gpt-4o-mini"
            assert headers["Authorization"] == "Bearer sk-test"
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl_provider_123",
                    "choices": [{"message": {"content": "Provider response."}}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 2},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    result = await llm_provider_service.provider_chat_completion(
        config=config,
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "chatcmpl_provider_123"


@pytest.mark.anyio
async def test_provider_chat_completion_maps_anthropic_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.claude-sonnet",
        backend="anthropic",
        base_url="https://api.anthropic.com/v1",
        upstream_model="claude-3-5-sonnet-latest",
        api_key_env="ANTHROPIC_API_KEY",
        description="Provider-backed chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ak-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "https://api.anthropic.com/v1/messages"
            assert json == {
                "model": "claude-3-5-sonnet-latest",
                "messages": [{"role": "user", "content": "Summarize"}],
                "max_tokens": 512,
                "system": "Keep it terse.",
            }
            assert headers["x-api-key"] == "ak-test"
            assert headers["anthropic-version"] == "2023-06-01"
            return httpx.Response(
                200,
                json={
                    "id": "msg_123",
                    "content": [{"type": "text", "text": "Anthropic response."}],
                    "usage": {"input_tokens": 7, "output_tokens": 4},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    result = await llm_provider_service.provider_chat_completion(
        config=config,
        messages=[
            {"role": "system", "content": "Keep it terse."},
            {"role": "user", "content": "Summarize"},
        ],
    )

    assert result.completion_id == "msg_123"
    assert result.content == "Anthropic response."
    assert result.prompt_tokens == 7
    assert result.completion_tokens == 4
    assert result.provider is not None
    assert result.provider.provider_backend == "anthropic"
    assert result.provider.provider_model_id == "provider.claude-sonnet"


@pytest.mark.anyio
async def test_provider_chat_completion_maps_ollama_payload_without_auth(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.ollama-gemma3",
        backend="ollama",
        base_url="http://localhost:11434",
        upstream_model="gemma3",
        api_key_env=None,
        description="Provider-backed chat model.",
        capabilities=("chat_completions",),
    )

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "http://localhost:11434/api/chat"
            assert json == {
                "model": "gemma3",
                "messages": [{"role": "user", "content": "Summarize"}],
                "stream": False,
            }
            assert headers == {"Content-Type": "application/json"}
            return httpx.Response(
                200,
                json={
                    "id": "chat_ollama_123",
                    "message": {"content": "Ollama response."},
                    "prompt_eval_count": 6,
                    "eval_count": 4,
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    result = await llm_provider_service.provider_chat_completion(
        config=config,
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "chat_ollama_123"
    assert result.content == "Ollama response."
    assert result.prompt_tokens == 6
    assert result.completion_tokens == 4
    assert result.provider is not None
    assert result.provider.provider_backend == "ollama"
    assert result.provider.provider_model_id == "provider.ollama-gemma3"


@pytest.mark.anyio
async def test_provider_chat_completion_maps_google_genai_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.gemini-flash",
        backend="google_genai",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        upstream_model="gemini-2.5-flash",
        api_key_env="GEMINI_API_KEY",
        description="Provider-backed chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("GEMINI_API_KEY", "gm-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert (
                url
                == "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
            )
            assert json == {
                "contents": [{"role": "user", "parts": [{"text": "Summarize"}]}],
                "systemInstruction": {"parts": [{"text": "Keep it terse."}]},
            }
            assert headers["x-goog-api-key"] == "gm-test"
            return httpx.Response(
                200,
                json={
                    "responseId": "gemini-response-123",
                    "candidates": [
                        {
                            "content": {
                                "parts": [{"text": "Gemini response."}],
                            }
                        }
                    ],
                    "usageMetadata": {
                        "promptTokenCount": 8,
                        "candidatesTokenCount": 5,
                    },
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    result = await llm_provider_service.provider_chat_completion(
        config=config,
        messages=[
            {"role": "system", "content": "Keep it terse."},
            {"role": "user", "content": "Summarize"},
        ],
    )

    assert result.completion_id == "gemini-response-123"
    assert result.content == "Gemini response."
    assert result.prompt_tokens == 8
    assert result.completion_tokens == 5
    assert result.provider is not None
    assert result.provider.provider_backend == "google_genai"
    assert result.provider.provider_model_id == "provider.gemini-flash"


@pytest.mark.anyio
async def test_provider_chat_completion_maps_mistral_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.mistral-small",
        backend="mistral",
        base_url="https://api.mistral.ai/v1",
        upstream_model="mistral-small-latest",
        api_key_env="MISTRAL_API_KEY",
        description="Provider-backed Mistral chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("MISTRAL_API_KEY", "ms-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "https://api.mistral.ai/v1/chat/completions"
            assert json == {
                "model": "mistral-small-latest",
                "messages": [{"role": "user", "content": "Summarize"}],
                "stream": False,
            }
            assert headers["Authorization"] == "Bearer ms-test"
            return httpx.Response(
                200,
                json={
                    "id": "cmpl_mistral_123",
                    "choices": [{"message": {"content": "Mistral response."}}],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 3},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    result = await llm_provider_service.provider_chat_completion(
        config=config,
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "cmpl_mistral_123"
    assert result.content == "Mistral response."
    assert result.prompt_tokens == 5
    assert result.completion_tokens == 3
    assert result.provider is not None
    assert result.provider.provider_backend == "mistral"
    assert result.provider.provider_model_id == "provider.mistral-small"


@pytest.mark.anyio
async def test_provider_chat_completion_maps_cohere_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.command-a",
        backend="cohere",
        base_url="https://api.cohere.com",
        upstream_model="command-a-03-2025",
        api_key_env="COHERE_API_KEY",
        description="Provider-backed Cohere chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("COHERE_API_KEY", "co-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "https://api.cohere.com/v2/chat"
            assert json == {
                "model": "command-a-03-2025",
                "messages": [{"role": "user", "content": "Summarize"}],
                "stream": False,
            }
            assert headers["Authorization"] == "Bearer co-test"
            return httpx.Response(
                200,
                json={
                    "id": "cohere-chat-123",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "Cohere response."}],
                    },
                    "meta": {
                        "tokens": {"input_tokens": 11, "output_tokens": 4},
                    },
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    result = await llm_provider_service.provider_chat_completion(
        config=config,
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "cohere-chat-123"
    assert result.content == "Cohere response."
    assert result.prompt_tokens == 11
    assert result.completion_tokens == 4
    assert result.provider is not None
    assert result.provider.provider_backend == "cohere"
    assert result.provider.provider_model_id == "provider.command-a"


@pytest.mark.anyio
async def test_provider_embeddings_require_configured_api_key(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.gpt-4o-mini",
        backend="openai_compatible",
        base_url="https://provider.test/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Provider-backed embeddings.",
        capabilities=("embeddings",),
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(LLMAPIError, match="environment variable 'OPENAI_API_KEY' is not set"):
        await llm_provider_service.provider_embeddings(
            config=config,
            inputs=["alpha beta"],
            dimensions=3,
        )


@pytest.mark.anyio
async def test_provider_embeddings_reject_anthropic_backend(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.claude-sonnet",
        backend="anthropic",
        base_url="https://api.anthropic.com/v1",
        upstream_model="claude-3-5-sonnet-latest",
        api_key_env="ANTHROPIC_API_KEY",
        description="Provider-backed chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ak-test")

    with pytest.raises(LLMAPIError, match="does not support embeddings"):
        await llm_provider_service.provider_embeddings(
            config=config,
            inputs=["alpha beta"],
            dimensions=3,
        )


@pytest.mark.anyio
async def test_provider_embeddings_maps_ollama_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.ollama-embeddinggemma",
        backend="ollama",
        base_url="http://localhost:11434",
        upstream_model="embeddinggemma",
        api_key_env=None,
        description="Provider-backed embeddings.",
        capabilities=("embeddings",),
    )

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "http://localhost:11434/api/embed"
            assert json == {
                "model": "embeddinggemma",
                "input": ["alpha beta", "gamma delta"],
                "dimensions": 3,
            }
            assert headers == {"Content-Type": "application/json"}
            return httpx.Response(
                200,
                json={
                    "embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
                    "prompt_eval_count": 8,
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    generated, total_tokens = await llm_provider_service.provider_embeddings(
        config=config,
        inputs=["alpha beta", "gamma delta"],
        dimensions=3,
    )

    assert total_tokens == 8
    assert generated[0].embedding == [0.1, 0.2, 0.3]
    assert generated[0].token_count == 0
    assert generated[0].provider is not None
    assert generated[0].provider.provider_backend == "ollama"
    assert generated[0].provider.provider_model_id == "provider.ollama-embeddinggemma"
    assert generated[1].embedding == [0.4, 0.5, 0.6]
    assert generated[1].token_count == 0


@pytest.mark.anyio
async def test_provider_embeddings_uses_capability_specific_timeout(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.ollama-embeddinggemma",
        backend="ollama",
        base_url="http://localhost:11434",
        upstream_model="embeddinggemma",
        api_key_env=None,
        description="Provider-backed embeddings.",
        capabilities=("embeddings",),
        timeout_seconds=30.0,
        embedding_timeout_seconds=6.0,
    )

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            assert kwargs["timeout"] == 6.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "http://localhost:11434/api/embed"
            assert json["model"] == "embeddinggemma"
            assert headers == {"Content-Type": "application/json"}
            return httpx.Response(
                200,
                json={
                    "embeddings": [[0.1, 0.2, 0.3]],
                    "prompt_eval_count": 4,
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    generated, total_tokens = await llm_provider_service.provider_embeddings(
        config=config,
        inputs=["alpha beta"],
        dimensions=3,
    )

    assert total_tokens == 4
    assert generated[0].embedding == [0.1, 0.2, 0.3]


@pytest.mark.anyio
async def test_provider_embeddings_maps_google_genai_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.gemini-embedding",
        backend="google_genai",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        upstream_model="gemini-embedding-001",
        api_key_env="GEMINI_API_KEY",
        description="Provider-backed embeddings.",
        capabilities=("embeddings",),
    )
    monkeypatch.setenv("GEMINI_API_KEY", "gm-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert (
                url
                == "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"
            )
            assert json == {
                "requests": [
                    {
                        "model": "models/gemini-embedding-001",
                        "content": {"parts": [{"text": "alpha beta"}]},
                        "embedContentConfig": {"outputDimensionality": 3},
                    },
                    {
                        "model": "models/gemini-embedding-001",
                        "content": {"parts": [{"text": "gamma delta"}]},
                        "embedContentConfig": {"outputDimensionality": 3},
                    },
                ]
            }
            assert headers["x-goog-api-key"] == "gm-test"
            return httpx.Response(
                200,
                json={
                    "embeddings": [
                        {"values": [0.1, 0.2, 0.3]},
                        {"values": [0.4, 0.5, 0.6]},
                    ],
                    "usageMetadata": {"promptTokenCount": 7},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    generated, total_tokens = await llm_provider_service.provider_embeddings(
        config=config,
        inputs=["alpha beta", "gamma delta"],
        dimensions=3,
    )

    assert total_tokens == 7
    assert generated[0].embedding == [0.1, 0.2, 0.3]
    assert generated[0].token_count == 0
    assert generated[0].provider is not None
    assert generated[0].provider.provider_backend == "google_genai"
    assert generated[0].provider.provider_model_id == "provider.gemini-embedding"
    assert generated[1].embedding == [0.4, 0.5, 0.6]
    assert generated[1].token_count == 0


@pytest.mark.anyio
async def test_provider_embeddings_maps_google_genai_single_input_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.gemini-embedding",
        backend="google_genai",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        upstream_model="gemini-embedding-001",
        api_key_env="GEMINI_API_KEY",
        description="Provider-backed embeddings.",
        capabilities=("embeddings",),
    )
    monkeypatch.setenv("GEMINI_API_KEY", "gm-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert (
                url
                == "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
            )
            assert json == {
                "model": "models/gemini-embedding-001",
                "content": {"parts": [{"text": "alpha beta"}]},
                "embedContentConfig": {"outputDimensionality": 3},
            }
            assert headers["x-goog-api-key"] == "gm-test"
            return httpx.Response(
                200,
                json={
                    "embedding": {"values": [0.1, 0.2, 0.3]},
                    "usageMetadata": {"promptTokenCount": 3},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    generated, total_tokens = await llm_provider_service.provider_embeddings(
        config=config,
        inputs=["alpha beta"],
        dimensions=3,
    )

    assert total_tokens == 3
    assert generated[0].embedding == [0.1, 0.2, 0.3]
    assert generated[0].token_count == 3
    assert generated[0].provider is not None
    assert generated[0].provider.provider_backend == "google_genai"
    assert generated[0].provider.provider_model_id == "provider.gemini-embedding"


@pytest.mark.anyio
async def test_provider_embeddings_maps_mistral_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.mistral-embed",
        backend="mistral",
        base_url="https://api.mistral.ai/v1",
        upstream_model="mistral-embed",
        api_key_env="MISTRAL_API_KEY",
        description="Provider-backed Mistral embeddings.",
        capabilities=("embeddings",),
    )
    monkeypatch.setenv("MISTRAL_API_KEY", "ms-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "https://api.mistral.ai/v1/embeddings"
            assert json == {
                "model": "mistral-embed",
                "input": ["alpha beta", "gamma delta"],
                "output_dimension": 3,
            }
            assert headers["Authorization"] == "Bearer ms-test"
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"embedding": [0.1, 0.2, 0.3]},
                        {"embedding": [0.4, 0.5, 0.6]},
                    ],
                    "usage": {"prompt_tokens": 7},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    generated, total_tokens = await llm_provider_service.provider_embeddings(
        config=config,
        inputs=["alpha beta", "gamma delta"],
        dimensions=3,
    )

    assert total_tokens == 7
    assert generated[0].embedding == [0.1, 0.2, 0.3]
    assert generated[0].provider is not None
    assert generated[0].provider.provider_backend == "mistral"
    assert generated[0].provider.provider_model_id == "provider.mistral-embed"
    assert generated[1].embedding == [0.4, 0.5, 0.6]


@pytest.mark.anyio
async def test_provider_embeddings_maps_xai_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.xai-grok",
        backend="xai",
        base_url="https://api.x.ai/v1",
        upstream_model="grok-4.3",
        api_key_env="XAI_API_KEY",
        description="Provider-backed xAI embeddings.",
        capabilities=("chat_completions", "embeddings"),
    )
    monkeypatch.setenv("XAI_API_KEY", "xai-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "https://api.x.ai/v1/embeddings"
            assert json == {
                "model": "grok-4.3",
                "input": "hello",
                "dimensions": 3,
            }
            assert headers["Authorization"] == "Bearer xai-test"
            return httpx.Response(
                200,
                json={
                    "data": [{"embedding": [0.1, 0.2, 0.3], "token_count": 2}],
                    "usage": {"prompt_tokens": 2},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    generated, total_tokens = await llm_provider_service.provider_embeddings(
        config=config,
        inputs=["hello"],
        dimensions=3,
    )

    assert total_tokens == 2
    assert generated[0].embedding == [0.1, 0.2, 0.3]
    assert generated[0].provider is not None
    assert generated[0].provider.provider_backend == "xai"
    assert generated[0].provider.provider_model_id == "provider.xai-grok"


def test_provider_embeddings_payload_uses_backend_specific_dimension_keys() -> None:
    mistral_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.mistral-embed",
        backend="mistral",
        base_url="https://api.mistral.ai/v1",
        upstream_model="mistral-embed",
        api_key_env="MISTRAL_API_KEY",
        description="Provider-backed Mistral embeddings.",
        capabilities=("embeddings",),
    )
    openai_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.text-embedding-3-small",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="text-embedding-3-small",
        api_key_env="OPENAI_API_KEY",
        description="Provider-backed OpenAI embeddings.",
        capabilities=("embeddings",),
    )

    mistral_payload = llm_provider_service._provider_embeddings_payload(
        config=mistral_config,
        inputs=["alpha beta"],
        dimensions=3,
    )
    openai_payload = llm_provider_service._provider_embeddings_payload(
        config=openai_config,
        inputs=["alpha beta"],
        dimensions=3,
    )

    assert mistral_payload == {
        "model": "mistral-embed",
        "input": "alpha beta",
        "output_dimension": 3,
    }
    assert openai_payload == {
        "model": "text-embedding-3-small",
        "input": "alpha beta",
        "dimensions": 3,
    }


@pytest.mark.anyio
async def test_provider_embeddings_maps_cohere_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-v4",
        backend="cohere",
        base_url="https://api.cohere.com",
        upstream_model="embed-v4.0",
        api_key_env="COHERE_API_KEY",
        description="Provider-backed Cohere embeddings.",
        capabilities=("embeddings",),
        embedding_input_type="classification",
    )
    monkeypatch.setenv("COHERE_API_KEY", "co-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "https://api.cohere.com/v2/embed"
            assert json == {
                "model": "embed-v4.0",
                "texts": ["alpha beta", "gamma delta"],
                "input_type": "classification",
                "embedding_types": ["float"],
                "output_dimension": 3,
            }
            assert headers["Authorization"] == "Bearer co-test"
            return httpx.Response(
                200,
                json={
                    "embeddings": {
                        "float": [
                            [0.1, 0.2, 0.3],
                            [0.4, 0.5, 0.6],
                        ]
                    },
                    "meta": {"billed_units": {"input_tokens": 9}},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    generated, total_tokens = await llm_provider_service.provider_embeddings(
        config=config,
        inputs=["alpha beta", "gamma delta"],
        dimensions=3,
    )

    assert total_tokens == 9
    assert generated[0].embedding == [0.1, 0.2, 0.3]
    assert generated[0].provider is not None
    assert generated[0].provider.provider_backend == "cohere"
    assert generated[0].provider.provider_model_id == "provider.embed-v4"
    assert generated[1].embedding == [0.4, 0.5, 0.6]
