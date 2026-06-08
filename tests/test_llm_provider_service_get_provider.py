"""Tests for test_llm_provider_service: get_provider.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-2/tests/test_llm_provider_service.py during modularization.
"""
from __future__ import annotations

from tests._test_llm_provider_service_helpers import *  # noqa: F401,F403


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


