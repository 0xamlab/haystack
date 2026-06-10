"""Provider path + payload builders for chat and embeddings.

Extracted from apps/api_server/services/llm_provider_service.py during modularization.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Any, Callable

import httpx

_PROVIDER_MODELS_ENV = "ALGENTA_LLM_PROVIDER_MODELS_JSON"
_SUPPORTED_PROVIDER_CAPABILITY_ORDER = ("chat_completions", "embeddings")
_SUPPORTED_PROVIDER_CAPABILITIES = frozenset(_SUPPORTED_PROVIDER_CAPABILITY_ORDER)
_SUPPORTED_PROVIDER_BACKENDS = frozenset(
    {
        "openai_compatible",
        "openai",
        "anthropic",
        "ollama",
        "google_genai",
        "mistral",
        "cohere",
        "groq",
        "xai",
        "router",
    }
)
_BACKEND_CAPABILITIES = {
    "openai_compatible": frozenset({"chat_completions", "embeddings"}),
    "openai": frozenset({"chat_completions", "embeddings"}),
    "anthropic": frozenset({"chat_completions"}),
    "ollama": frozenset({"chat_completions", "embeddings"}),
    "google_genai": frozenset({"chat_completions", "embeddings"}),
    "mistral": frozenset({"chat_completions", "embeddings"}),
    "cohere": frozenset({"chat_completions", "embeddings"}),
    "groq": frozenset({"chat_completions"}),
    "xai": frozenset({"chat_completions", "embeddings"}),
    "router": frozenset({"chat_completions", "embeddings"}),
}
_ANTHROPIC_API_VERSION = "2023-06-01"
_OPTIONAL_PROVIDER_API_KEY_BACKENDS = frozenset({"ollama"})
_RETRYABLE_PROVIDER_ERROR_CODE_ORDER = (
    "backend_unavailable",
    "provider_timeout",
    "provider_rate_limited",
    "provider_backend_error",
)
_RETRYABLE_PROVIDER_ERROR_CODES = frozenset(_RETRYABLE_PROVIDER_ERROR_CODE_ORDER)
_COHERE_EMBED_INPUT_TYPES = frozenset(
    {"search_document", "search_query", "classification", "clustering", "image"}
)
_SUPPORTED_ROUTER_FALLBACK_POLICIES = frozenset({"disabled", "retryable_only"})
_DEFAULT_ROUTER_FALLBACK_POLICY = "disabled"
_DEFAULT_PROVIDER_TIMEOUT_SECONDS = 30.0
_PROVIDER_HEADER_NAME_PATTERN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_RESERVED_PROVIDER_HEADER_NAMES = frozenset(
    {
        "authorization",
        "content-type",
        "x-api-key",
        "x-goog-api-key",
        "anthropic-version",
    }
)



from apps.api_server.services.llm_provider_service._config import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._parsers import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._parsers import (
    _require_non_empty_string,
    _parse_capabilities,
    _validate_backend_capabilities,
    _resolve_upstream_model,
    _validate_embedding_input_type,
    _parse_provider_header_envs,
    _parse_router_targets,
    _parse_router_target_list,
    _parse_capability_router_targets,
    _parse_router_fallback_policy,
    _validate_capability_router_fallback_policies,
    _parse_router_fallback_on,
    _effective_router_fallback_policy,
    _validate_capability_router_fallback_on,
    _parse_router_max_attempts,
    _validate_capability_router_max_attempts,
    _parse_provider_timeout_seconds,
    _validate_capability_timeout_seconds,
    _validate_router_fields,
)


def _provider_chat_path(config: ProviderModelConfig) -> str:
    if config.backend == "anthropic":
        return "/messages"
    if config.backend == "ollama":
        return "/api/chat"
    if config.backend == "google_genai":
        return f"/{_provider_model_resource(config)}:generateContent"
    if config.backend == "cohere":
        return "/v2/chat"
    return "/chat/completions"


def _provider_embeddings_path(config: ProviderModelConfig) -> str:
    from apps.api_server.services.llm_api_service import LLMAPIError

    if config.backend == "anthropic":
        raise LLMAPIError(
            "model_capability_unsupported",
            f"Provider backend '{config.backend}' does not support embeddings for model '{config.model_id}'.",
            {
                "model": config.model_id,
                "backend": config.backend,
                "required_capability": "embeddings",
            },
        )
    if config.backend == "ollama":
        return "/api/embed"
    if config.backend == "google_genai":
        return f"/{_provider_model_resource(config)}:embedContent"
    if config.backend == "cohere":
        return "/v2/embed"
    return "/embeddings"


def _provider_embeddings_payload(
    *,
    config: ProviderModelConfig,
    inputs: list[str],
    dimensions: int,
) -> dict[str, Any]:
    if config.backend == "cohere":
        return {
            "model": config.upstream_model,
            "texts": inputs,
            "input_type": config.embedding_input_type or "search_document",
            "embedding_types": ["float"],
            "output_dimension": dimensions,
        }
    if config.backend == "mistral":
        return {
            "model": config.upstream_model,
            "input": inputs if len(inputs) != 1 else inputs[0],
            "output_dimension": dimensions,
        }
    return {
        "model": config.upstream_model,
        "input": inputs if len(inputs) != 1 else inputs[0],
        "dimensions": dimensions,
    }


def _provider_model_resource(config: ProviderModelConfig) -> str:
    if config.backend != "google_genai":
        return config.upstream_model
    if config.upstream_model.startswith("models/"):
        return config.upstream_model
    return f"models/{config.upstream_model}"


def _provider_chat_payload(
    *,
    config: ProviderModelConfig,
    messages: list[dict[str, str]],
    max_output_tokens: int | None = None,
) -> dict[str, Any]:
    from apps.api_server.services.llm_api_service import LLMAPIError

    if config.backend == "anthropic":
        system_messages = [
            str(message["content"])
            for message in messages
            if message.get("role") == "system"
        ]
        anthropic_messages = [
            {"role": message["role"], "content": message["content"]}
            for message in messages
            if message.get("role") in {"user", "assistant"}
        ]
        if not anthropic_messages:
            raise LLMAPIError(
                "invalid_provider_request",
                f"Provider-backed model '{config.model_id}' requires at least one non-system message.",
                {"model": config.model_id, "backend": config.backend},
            )
        payload: dict[str, Any] = {
            "model": config.upstream_model,
            "messages": anthropic_messages,
            # AR-OPT-5: dynamic output budget when the caller estimates one; the fixed
            # 512 default truncated larger patch diffs.
            "max_tokens": max_output_tokens or 512,
        }
        if system_messages:
            # AR-OPT-1: emit the system prompt as a cacheable content block so Anthropic
            # prompt-caching reuses a large, stable prefix (e.g. the evidence bundle)
            # across repeated calls. Harmless if the block is below the cache minimum.
            payload["system"] = [
                {
                    "type": "text",
                    "text": "\n".join(system_messages),
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        return payload
    if config.backend == "ollama":
        return {
            "model": config.upstream_model,
            "messages": messages,
            "stream": False,
        }
    if config.backend == "google_genai":
        system_messages = [
            str(message["content"])
            for message in messages
            if message.get("role") == "system"
        ]
        content_items = []
        for message in messages:
            role = message.get("role")
            if role == "system":
                continue
            if role == "assistant":
                gemini_role = "model"
            elif role == "user":
                gemini_role = "user"
            else:
                raise LLMAPIError(
                    "invalid_provider_request",
                    f"Provider-backed model '{config.model_id}' does not support role '{role}'.",
                    {"model": config.model_id, "backend": config.backend, "role": role},
                )
            content_items.append(
                {
                    "role": gemini_role,
                    "parts": [{"text": message["content"]}],
                }
            )
        if not content_items:
            raise LLMAPIError(
                "invalid_provider_request",
                f"Provider-backed model '{config.model_id}' requires at least one non-system message.",
                {"model": config.model_id, "backend": config.backend},
            )
        payload: dict[str, Any] = {"contents": content_items}
        if system_messages:
            payload["systemInstruction"] = {
                "parts": [{"text": "\n".join(system_messages)}],
            }
        return payload
    if config.backend == "cohere":
        return {
            "model": config.upstream_model,
            "messages": messages,
            "stream": False,
        }
    return {
        "model": config.upstream_model,
        "messages": messages,
        "stream": False,
    }

