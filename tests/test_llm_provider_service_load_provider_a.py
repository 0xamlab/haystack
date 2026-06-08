"""Tests for test_llm_provider_service: load_provider_a.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-2/tests/test_llm_provider_service.py during modularization.
"""
from __future__ import annotations

from tests._test_llm_provider_service_helpers import *  # noqa: F401,F403


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


