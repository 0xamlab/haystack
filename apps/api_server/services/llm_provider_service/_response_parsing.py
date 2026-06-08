"""_parse_provider_chat_completion.

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
from apps.api_server.services.llm_provider_service._payload_builders import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._payload_builders import (
    _provider_chat_path,
    _provider_embeddings_path,
    _provider_embeddings_payload,
    _provider_model_resource,
    _provider_chat_payload,
)


def _parse_provider_chat_completion(
    *,
    config: ProviderModelConfig,
    data: dict[str, Any],
) -> Any:
    from apps.api_server.services.llm_api_service import (
        ChatCompletionResult,
        LLMAPIError,
        ProviderAttemptRecord,
        ProviderExecutionMetadata,
    )

    try:
        if config.backend == "anthropic":
            completion_id = str(data["id"])
            raw_content = data["content"]
            usage = data["usage"]
            if not isinstance(raw_content, list) or not raw_content:
                raise TypeError("content")
            text_parts: list[str] = []
            for item in raw_content:
                if not isinstance(item, dict):
                    raise TypeError("content_item")
                if item.get("type") != "text":
                    continue
                text_value = item.get("text")
                if not isinstance(text_value, str):
                    raise TypeError("content_text")
                text_parts.append(text_value)
            if not text_parts:
                raise TypeError("content_text_missing")
            content = "".join(text_parts)
            prompt_tokens = int(usage["input_tokens"])
            completion_tokens = int(usage["output_tokens"])
        elif config.backend == "ollama":
            completion_id = str(data["id"])
            message = data["message"]
            content = str(message["content"])
            prompt_tokens = int(data["prompt_eval_count"])
            completion_tokens = int(data["eval_count"])
        elif config.backend == "google_genai":
            completion_id = str(data["responseId"])
            candidates = data["candidates"]
            usage = data["usageMetadata"]
            content_parts = candidates[0]["content"]["parts"]
            text_parts = [str(item["text"]) for item in content_parts if "text" in item]
            if not text_parts:
                raise TypeError("content_text_missing")
            content = "".join(text_parts)
            prompt_tokens = int(usage["promptTokenCount"])
            completion_tokens = int(usage["candidatesTokenCount"])
        elif config.backend == "cohere":
            completion_id = str(data["id"])
            message = data["message"]
            meta = data["meta"]
            content_items = message["content"]
            if not isinstance(content_items, list) or not content_items:
                raise TypeError("content")
            text_parts = [
                str(item["text"])
                for item in content_items
                if isinstance(item, dict) and item.get("type") == "text" and "text" in item
            ]
            if not text_parts:
                raise TypeError("content_text_missing")
            content = "".join(text_parts)
            tokens = meta.get("tokens") or meta.get("billed_units") or {}
            prompt_tokens = int(tokens["input_tokens"])
            completion_tokens = int(tokens["output_tokens"])
        else:
            completion_id = str(data["id"])
            choices = data["choices"]
            usage = data["usage"]
            content = str(choices[0]["message"]["content"])
            prompt_tokens = int(usage["prompt_tokens"])
            completion_tokens = int(usage["completion_tokens"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise LLMAPIError(
            "invalid_provider_response",
            f"Provider backend returned an invalid chat completion payload for model '{config.model_id}'.",
            {"model": config.model_id, "backend": config.backend},
        ) from exc
    return ChatCompletionResult(
        completion_id=completion_id,
        content=content,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        provider=ProviderExecutionMetadata(
            provider_backend=config.backend,
            provider_model_id=config.model_id,
        ),
        provider_attempts=(
            ProviderAttemptRecord(
                provider_backend=config.backend,
                provider_model_id=config.model_id,
                outcome="selected",
            ),
        ),
    )


