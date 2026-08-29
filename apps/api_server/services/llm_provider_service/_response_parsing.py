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


_VALID_CHAT_FINISH_REASONS = frozenset({"stop", "tool_calls", "length", "content_filter"})
# Gemini finishReason values that mean the response was cut short vs blocked. Anything else
# (STOP, or an unrecognized/future value) defaults to "stop".
_GEMINI_LENGTH_FINISH_REASONS = frozenset({"MAX_TOKENS"})
_GEMINI_CONTENT_FILTER_FINISH_REASONS = frozenset(
    {"SAFETY", "RECITATION", "PROHIBITED_CONTENT", "SPII", "BLOCKLIST", "IMAGE_SAFETY"}
)


def _normalize_openai_shaped_finish_reason(raw: Any) -> str:
    """openai/openai_compatible/groq/xai/mistral all report finish_reason with the OpenAI enum
    already ("stop", "length", "tool_calls", "content_filter"), plus the deprecated
    "function_call" alias -- normalize that alias forward and default anything unrecognized to
    "stop" rather than propagating a value our own response schema doesn't declare."""
    if raw == "function_call":
        return "tool_calls"
    if raw in _VALID_CHAT_FINISH_REASONS:
        return raw
    return "stop"


def _anthropic_finish_reason(stop_reason: Any) -> str:
    if stop_reason == "max_tokens":
        return "length"
    return "stop"


def _gemini_finish_reason(raw: Any) -> str:
    if raw in _GEMINI_LENGTH_FINISH_REASONS:
        return "length"
    if raw in _GEMINI_CONTENT_FILTER_FINISH_REASONS:
        return "content_filter"
    return "stop"


def _cohere_finish_reason(raw: Any) -> str:
    if raw == "MAX_TOKENS":
        return "length"
    return "stop"


def _tool_calls_from_openai_shaped(raw_tool_calls: Any) -> tuple[Any, ...] | None:
    from apps.api_server.services.llm_api_service import (
        ChatCompletionToolCall,
        ChatCompletionToolCallFunction,
    )

    if not raw_tool_calls:
        return None
    return tuple(
        ChatCompletionToolCall(
            id=str(item["id"]),
            type="function",
            function=ChatCompletionToolCallFunction(
                name=str(item["function"]["name"]),
                arguments=str(item["function"]["arguments"]),
            ),
        )
        for item in raw_tool_calls
    ) or None


def _parse_provider_chat_completion(
    *,
    config: ProviderModelConfig,
    data: dict[str, Any],
) -> Any:
    from apps.api_server.services.llm_api_service import (
        ChatCompletionResult,
        ChatCompletionToolCall,
        ChatCompletionToolCallFunction,
        LLMAPIError,
        ProviderAttemptRecord,
        ProviderExecutionMetadata,
    )

    try:
        cache_read_tokens = 0
        cache_write_tokens = 0
        tool_calls: tuple[Any, ...] | None = None
        finish_reason = "stop"
        if config.backend == "anthropic":
            completion_id = str(data["id"])
            raw_content = data["content"]
            usage = data["usage"]
            if not isinstance(raw_content, list) or not raw_content:
                raise TypeError("content")
            text_parts: list[str] = []
            tool_call_list: list[Any] = []
            for item in raw_content:
                if not isinstance(item, dict):
                    raise TypeError("content_item")
                item_type = item.get("type")
                if item_type == "text":
                    text_value = item.get("text")
                    if not isinstance(text_value, str):
                        raise TypeError("content_text")
                    text_parts.append(text_value)
                elif item_type == "tool_use":
                    tool_call_list.append(
                        ChatCompletionToolCall(
                            id=str(item["id"]),
                            type="function",
                            function=ChatCompletionToolCallFunction(
                                name=str(item["name"]),
                                arguments=json.dumps(
                                    item.get("input") or {},
                                    separators=(",", ":"),
                                    sort_keys=True,
                                ),
                            ),
                        )
                    )
            if not text_parts and not tool_call_list:
                raise TypeError("content_text_missing")
            content = "".join(text_parts) if text_parts else None
            tool_calls = tuple(tool_call_list) or None
            finish_reason = "tool_calls" if tool_calls else _anthropic_finish_reason(data.get("stop_reason"))
            prompt_tokens = int(usage["input_tokens"])
            completion_tokens = int(usage["output_tokens"])
            cache_read_tokens = int(usage.get("cache_read_input_tokens", 0) or 0)
            cache_write_tokens = int(usage.get("cache_creation_input_tokens", 0) or 0)
        elif config.backend == "ollama":
            completion_id = str(data["id"])
            message = data["message"]
            raw_content = message.get("content")
            raw_tool_calls = message.get("tool_calls") or []
            tool_call_list = [
                ChatCompletionToolCall(
                    id=f"call_{completion_id}_{index}",
                    type="function",
                    function=ChatCompletionToolCallFunction(
                        name=str(item["function"]["name"]),
                        arguments=json.dumps(
                            item["function"].get("arguments") or {},
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    ),
                )
                for index, item in enumerate(raw_tool_calls)
            ]
            tool_calls = tuple(tool_call_list) or None
            content = str(raw_content) if raw_content else None
            finish_reason = "tool_calls" if tool_calls else "stop"
            prompt_tokens = int(data["prompt_eval_count"])
            completion_tokens = int(data["eval_count"])
        elif config.backend == "google_genai":
            completion_id = str(data["responseId"])
            candidates = data["candidates"]
            usage = data["usageMetadata"]
            candidate = candidates[0]
            content_parts = candidate["content"]["parts"]
            text_parts = [str(item["text"]) for item in content_parts if "text" in item]
            tool_call_list = []
            for index, item in enumerate(content_parts):
                function_call = item.get("functionCall")
                if function_call is None:
                    continue
                # Gemini's functionCall carries no id -- synthesize one from the response id + the
                # part's position so a follow-up turn's tool-role message can reference it.
                tool_call_list.append(
                    ChatCompletionToolCall(
                        id=f"call_{completion_id}_{index}",
                        type="function",
                        function=ChatCompletionToolCallFunction(
                            name=str(function_call["name"]),
                            arguments=json.dumps(
                                function_call.get("args") or {},
                                separators=(",", ":"),
                                sort_keys=True,
                            ),
                        ),
                    )
                )
            if not text_parts and not tool_call_list:
                raise TypeError("content_text_missing")
            content = "".join(text_parts) if text_parts else None
            tool_calls = tuple(tool_call_list) or None
            finish_reason = (
                "tool_calls" if tool_calls else _gemini_finish_reason(candidate.get("finishReason"))
            )
            prompt_tokens = int(usage["promptTokenCount"])
            completion_tokens = int(usage["candidatesTokenCount"])
        elif config.backend == "cohere":
            completion_id = str(data["id"])
            message = data["message"]
            meta = data["meta"]
            content_items = message.get("content") or []
            raw_tool_calls = message.get("tool_calls") or []
            if not isinstance(content_items, list):
                raise TypeError("content")
            text_parts = [
                str(item["text"])
                for item in content_items
                if isinstance(item, dict) and item.get("type") == "text" and "text" in item
            ]
            tool_calls = _tool_calls_from_openai_shaped(raw_tool_calls)
            if not text_parts and not tool_calls:
                raise TypeError("content_text_missing")
            content = "".join(text_parts) if text_parts else None
            finish_reason = (
                "tool_calls" if tool_calls else _cohere_finish_reason(data.get("finish_reason"))
            )
            tokens = meta.get("tokens") or meta.get("billed_units") or {}
            prompt_tokens = int(tokens["input_tokens"])
            completion_tokens = int(tokens["output_tokens"])
        else:
            completion_id = str(data["id"])
            choices = data["choices"]
            usage = data["usage"]
            message = choices[0]["message"]
            raw_content = message.get("content")
            tool_calls = _tool_calls_from_openai_shaped(message.get("tool_calls"))
            if raw_content is None and not tool_calls:
                raise TypeError("content_text_missing")
            content = str(raw_content) if raw_content is not None else None
            finish_reason = _normalize_openai_shaped_finish_reason(choices[0].get("finish_reason"))
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
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        tool_calls=tool_calls,
        finish_reason=finish_reason,
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


