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


def _tool_call_arguments_object(function: dict[str, Any]) -> dict[str, Any]:
    """A tool_call's function.arguments is always a JSON string on our own wire shape (matching
    OpenAI); some backends (anthropic input, gemini args, ollama arguments) want it back as a
    parsed object. Malformed/empty arguments degrade to {} rather than failing the whole request --
    the provider surfaces its own error if it truly needed a well-formed payload."""
    raw = function.get("arguments")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _openai_tool_to_anthropic(tool: dict[str, Any]) -> dict[str, Any]:
    function = tool["function"]
    return {
        "name": function["name"],
        "description": function.get("description") or "",
        "input_schema": function.get("parameters") or {"type": "object", "properties": {}},
    }


def _anthropic_tool_choice(
    tool_choice: Any,
    *,
    parallel_tool_calls: bool | None,
) -> dict[str, Any] | None:
    if tool_choice is None or tool_choice == "auto":
        choice: dict[str, Any] = {"type": "auto"}
    elif tool_choice == "required":
        choice = {"type": "any"}
    elif tool_choice == "none":
        choice = {"type": "none"}
    elif isinstance(tool_choice, dict):
        choice = {"type": "tool", "name": tool_choice.get("function", {}).get("name")}
    else:
        return None
    if parallel_tool_calls is False:
        choice["disable_parallel_tool_use"] = True
    return choice


def _anthropic_messages_from_openai(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Translate OpenAI-shaped user/assistant/tool messages into Anthropic's message array.
    Plain text-only user/assistant turns keep their EXACT prior shape (bare string content) so
    non-tool requests stay byte-identical to before this change; only tool-calling turns grow
    Anthropic's content-block-array shape (assistant tool_use blocks, user tool_result blocks,
    with consecutive tool_result messages merged into one user turn, as Anthropic requires)."""
    entries: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        if role == "user":
            entries.append({"role": "user", "content": message.get("content") or ""})
        elif role == "assistant":
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                entries.append({"role": "assistant", "content": message.get("content") or ""})
                continue
            blocks: list[dict[str, Any]] = []
            content = message.get("content")
            if content:
                blocks.append({"type": "text", "text": content})
            for tool_call in tool_calls:
                function = tool_call["function"]
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tool_call["id"],
                        "name": function["name"],
                        "input": _tool_call_arguments_object(function),
                    }
                )
            entries.append({"role": "assistant", "content": blocks})
        elif role == "tool":
            block = {
                "type": "tool_result",
                "tool_use_id": message.get("tool_call_id", ""),
                "content": message.get("content") or "",
            }
            if entries and entries[-1]["role"] == "user" and isinstance(entries[-1]["content"], list):
                entries[-1]["content"].append(block)
            else:
                entries.append({"role": "user", "content": [block]})
        # system/developer/unrecognized roles: dropped here (system is folded into the top-level
        # "system" prompt block by the caller before this helper ever sees the message list).
    return entries


def _gemini_function_declarations(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": tool["function"]["name"],
            "description": tool["function"].get("description") or "",
            "parameters": tool["function"].get("parameters") or {"type": "object", "properties": {}},
        }
        for tool in tools
    ]


def _gemini_tool_config(tool_choice: Any) -> dict[str, Any] | None:
    if tool_choice is None or tool_choice == "auto":
        return None
    if tool_choice == "required":
        return {"functionCallingConfig": {"mode": "ANY"}}
    if tool_choice == "none":
        return {"functionCallingConfig": {"mode": "NONE"}}
    if isinstance(tool_choice, dict):
        name = tool_choice.get("function", {}).get("name")
        return {
            "functionCallingConfig": {
                "mode": "ANY",
                "allowedFunctionNames": [name] if name else [],
            }
        }
    return None


def _gemini_function_name_for_tool_call_id(
    messages: list[dict[str, Any]],
    tool_call_id: str | None,
) -> str:
    if not tool_call_id:
        return ""
    for message in messages:
        if message.get("role") != "assistant":
            continue
        for tool_call in message.get("tool_calls") or []:
            if tool_call.get("id") == tool_call_id:
                return str(tool_call["function"]["name"])
    return ""


def _ollama_messages_with_tools(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ollama's native /api/chat wants tool_calls.function.arguments as a parsed OBJECT (not the
    OpenAI JSON-string convention our own wire shape uses), and has no notion of a tool_call id --
    it correlates a tool-role reply to the preceding call positionally/by name."""
    result: list[dict[str, Any]] = []
    for message in messages:
        entry: dict[str, Any] = {"role": message.get("role"), "content": message.get("content") or ""}
        if message.get("role") == "assistant" and message.get("tool_calls"):
            entry["tool_calls"] = [
                {
                    "function": {
                        "name": tool_call["function"]["name"],
                        "arguments": _tool_call_arguments_object(tool_call["function"]),
                    }
                }
                for tool_call in message["tool_calls"]
            ]
        result.append(entry)
    return result


def _provider_chat_payload(
    *,
    config: ProviderModelConfig,
    messages: list[dict[str, Any]],
    max_output_tokens: int | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any | None = None,
    parallel_tool_calls: bool | None = None,
) -> dict[str, Any]:
    from apps.api_server.services.llm_api_service import LLMAPIError

    if config.backend == "anthropic":
        system_messages = [
            str(message["content"])
            for message in messages
            if message.get("role") == "system"
        ]
        anthropic_messages = _anthropic_messages_from_openai(messages)
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
        if tools:
            payload["tools"] = [_openai_tool_to_anthropic(tool) for tool in tools]
            choice = _anthropic_tool_choice(tool_choice, parallel_tool_calls=parallel_tool_calls)
            if choice is not None:
                payload["tool_choice"] = choice
        return payload
    if config.backend == "ollama":
        if tools and tool_choice not in (None, "auto"):
            # Ollama's native /api/chat has no request-side knob to force/forbid tool use --
            # tools are always offered "auto" and the model decides. Say so rather than silently
            # ignoring the caller's forcing intent.
            raise LLMAPIError(
                "model_capability_unsupported",
                (
                    f"Provider backend 'ollama' does not support tool_choice='{tool_choice}' on "
                    "/api/chat; only the default automatic tool selection is supported."
                ),
                {
                    "model": config.model_id,
                    "backend": config.backend,
                    "required_capability": "tool_choice_forced",
                },
            )
        payload = {
            "model": config.upstream_model,
            "messages": _ollama_messages_with_tools(messages) if tools else messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        return payload
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
                tool_calls = message.get("tool_calls") or []
                parts: list[dict[str, Any]] = []
                content = message.get("content")
                if content:
                    parts.append({"text": content})
                for tool_call in tool_calls:
                    function = tool_call["function"]
                    parts.append(
                        {
                            "functionCall": {
                                "name": function["name"],
                                "args": _tool_call_arguments_object(function),
                            }
                        }
                    )
                if not parts:
                    parts.append({"text": ""})
                content_items.append({"role": "model", "parts": parts})
                continue
            if role == "user":
                content_items.append({"role": "user", "parts": [{"text": message.get("content") or ""}]})
                continue
            if role == "tool":
                name = _gemini_function_name_for_tool_call_id(messages, message.get("tool_call_id"))
                content_items.append(
                    {
                        "role": "function",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": name,
                                    "response": {"result": message.get("content") or ""},
                                }
                            }
                        ],
                    }
                )
                continue
            raise LLMAPIError(
                "invalid_provider_request",
                f"Provider-backed model '{config.model_id}' does not support role '{role}'.",
                {"model": config.model_id, "backend": config.backend, "role": role},
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
        if tools:
            payload["tools"] = [{"functionDeclarations": _gemini_function_declarations(tools)}]
            tool_config = _gemini_tool_config(tool_choice)
            if tool_config is not None:
                payload["toolConfig"] = tool_config
        return payload
    if config.backend == "cohere":
        payload = {
            "model": config.upstream_model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            if tool_choice is not None and tool_choice != "auto":
                if isinstance(tool_choice, dict):
                    # Cohere v2's tool_choice is REQUIRED/NONE only -- it cannot force one named
                    # function the way OpenAI/Anthropic/Gemini can.
                    raise LLMAPIError(
                        "model_capability_unsupported",
                        (
                            "Provider backend 'cohere' does not support forcing a specific named "
                            "tool via tool_choice; only 'auto', 'required', and 'none' are supported."
                        ),
                        {
                            "model": config.model_id,
                            "backend": config.backend,
                            "required_capability": "tool_choice_named_function",
                        },
                    )
                payload["tool_choice"] = "REQUIRED" if tool_choice == "required" else "NONE"
        return payload
    payload = {
        "model": config.upstream_model,
        "messages": messages,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if parallel_tool_calls is not None:
            payload["parallel_tool_calls"] = parallel_tool_calls
    return payload

