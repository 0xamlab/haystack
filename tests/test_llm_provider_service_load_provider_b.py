"""Tests for test_llm_provider_service: load_provider_b.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-2/tests/test_llm_provider_service.py during modularization.
"""
from __future__ import annotations

from tests._test_llm_provider_service_helpers import *  # noqa: F401,F403


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


