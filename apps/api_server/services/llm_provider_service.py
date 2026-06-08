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


@dataclass(frozen=True)
class ProviderModelConfig:
    model_id: str
    backend: str
    base_url: str
    upstream_model: str
    api_key_env: str | None
    description: str
    capabilities: tuple[str, ...]
    embedding_input_type: str | None = None
    routing_targets: tuple[str, ...] = ()
    chat_routing_targets: tuple[str, ...] = ()
    embedding_routing_targets: tuple[str, ...] = ()
    routing_fallback_policy: str | None = None
    chat_routing_fallback_policy: str | None = None
    embedding_routing_fallback_policy: str | None = None
    routing_fallback_on: tuple[str, ...] = ()
    chat_routing_fallback_on: tuple[str, ...] = ()
    embedding_routing_fallback_on: tuple[str, ...] = ()
    routing_max_attempts: int | None = None
    chat_routing_max_attempts: int | None = None
    embedding_routing_max_attempts: int | None = None
    timeout_seconds: float | None = None
    chat_timeout_seconds: float | None = None
    embedding_timeout_seconds: float | None = None
    header_envs: tuple[tuple[str, str], ...] = ()


def _require_non_empty_string(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}.{key} must be a non-empty string.")
    return value.strip()


def _parse_capabilities(
    data: dict[str, Any],
    *,
    backend: str,
    context: str,
) -> tuple[str, ...]:
    raw = data.get("capabilities")
    if raw is None:
        supported = _BACKEND_CAPABILITIES.get(backend)
        if supported is None:
            raise ValueError(
                f"{context}.backend must be one of {sorted(_SUPPORTED_PROVIDER_BACKENDS)}."
            )
        return tuple(
            capability
            for capability in _SUPPORTED_PROVIDER_CAPABILITY_ORDER
            if capability in supported
        )
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{context}.capabilities must be a non-empty list when provided.")
    capabilities: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, str) or item not in _SUPPORTED_PROVIDER_CAPABILITIES:
            raise ValueError(
                f"{context}.capabilities.{index} must be one of "
                f"{sorted(_SUPPORTED_PROVIDER_CAPABILITIES)}."
            )
        if item not in capabilities:
            capabilities.append(item)
    return tuple(capabilities)


def _validate_backend_capabilities(
    *,
    backend: str,
    capabilities: tuple[str, ...],
    context: str,
) -> tuple[str, ...]:
    supported = _BACKEND_CAPABILITIES.get(backend)
    if supported is None:
        raise ValueError(
            f"{context}.backend must be one of {sorted(_SUPPORTED_PROVIDER_BACKENDS)}."
        )
    invalid = [capability for capability in capabilities if capability not in supported]
    if invalid:
        raise ValueError(
            f"{context}.capabilities contains unsupported entries for backend '{backend}': {invalid}."
        )
    return capabilities


def _resolve_upstream_model(data: dict[str, Any], context: str, model_id: str) -> str:
    raw_model_name = data.get("model_name")
    raw_upstream_model = data.get("upstream_model")

    model_name = str(raw_model_name).strip() if raw_model_name is not None else ""
    upstream_model = str(raw_upstream_model).strip() if raw_upstream_model is not None else ""

    if model_name and upstream_model and model_name != upstream_model:
        raise ValueError(
            f"{context}.model_name and {context}.upstream_model must match when both are provided."
        )

    resolved = model_name or upstream_model or model_id
    if not resolved:
        raise ValueError(
            f"{context}.model_name must be a non-empty string when provided."
        )
    return resolved


def _validate_embedding_input_type(
    *,
    backend: str,
    raw_value: Any,
    context: str,
) -> str | None:
    if raw_value is None:
        return None
    if backend != "cohere":
        raise ValueError(
            f"{context}.embedding_input_type is only supported for backend 'cohere'."
        )
    if not isinstance(raw_value, str) or raw_value.strip() not in _COHERE_EMBED_INPUT_TYPES:
        raise ValueError(
            f"{context}.embedding_input_type must be one of {sorted(_COHERE_EMBED_INPUT_TYPES)}."
        )
    return raw_value.strip()


def _parse_provider_header_envs(
    data: dict[str, Any],
    *,
    backend: str,
    context: str,
) -> tuple[tuple[str, str], ...]:
    raw = data.get("header_envs")
    if backend == "router":
        if raw is not None:
            raise ValueError(
                f"{context}.header_envs is only supported for non-router backends."
            )
        return ()
    if raw is None:
        return ()
    if not isinstance(raw, dict) or not raw:
        raise ValueError(f"{context}.header_envs must be a non-empty object when provided.")
    header_envs: list[tuple[str, str]] = []
    seen_header_names: set[str] = set()
    for header_name, env_name in raw.items():
        if not isinstance(header_name, str) or not _PROVIDER_HEADER_NAME_PATTERN.fullmatch(
            header_name
        ):
            raise ValueError(
                f"{context}.header_envs keys must be valid HTTP header names."
            )
        normalized_header_name = header_name.strip()
        lower_header_name = normalized_header_name.lower()
        if lower_header_name in seen_header_names:
            raise ValueError(
                f"{context}.header_envs contains duplicate header '{normalized_header_name}'."
            )
        if lower_header_name in _RESERVED_PROVIDER_HEADER_NAMES:
            raise ValueError(
                f"{context}.header_envs cannot override reserved header '{normalized_header_name}'."
            )
        if not isinstance(env_name, str) or not env_name.strip():
            raise ValueError(
                f"{context}.header_envs['{normalized_header_name}'] must be a non-empty environment variable name."
            )
        seen_header_names.add(lower_header_name)
        header_envs.append((normalized_header_name, env_name.strip()))
    return tuple(header_envs)


def _parse_router_targets(
    data: dict[str, Any],
    *,
    backend: str,
    context: str,
) -> tuple[str, ...]:
    raw = data.get("targets")
    if raw is None:
        return ()
    return _parse_router_target_list(
        raw,
        backend=backend,
        context=f"{context}.targets",
        field_name="targets",
    )


def _parse_router_target_list(
    raw: Any,
    *,
    backend: str,
    context: str,
    field_name: str,
) -> tuple[str, ...]:
    if backend != "router":
        if raw is not None:
            raise ValueError(
                f"{context} is only supported for backend 'router'."
            )
        return ()
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{context} must be a non-empty list for backend 'router'.")
    targets: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{context}.{index} must be a non-empty string.")
        target = item.strip()
        if target not in targets:
            targets.append(target)
    return tuple(targets)


def _parse_capability_router_targets(
    data: dict[str, Any],
    *,
    backend: str,
    context: str,
    key: str,
) -> tuple[str, ...]:
    raw = data.get(key)
    if raw is None:
        return ()
    return _parse_router_target_list(
        raw,
        backend=backend,
        context=f"{context}.{key}",
        field_name=key,
    )


def _parse_router_fallback_policy(
    data: dict[str, Any],
    *,
    backend: str,
    context: str,
    key: str = "fallback_policy",
    default: str | None = None,
) -> str | None:
    raw = data.get(key)
    if backend != "router":
        if raw is not None:
            raise ValueError(
                f"{context}.{key} is only supported for backend 'router'."
            )
        return None
    if raw is None:
        return default
    if not isinstance(raw, str) or raw.strip() not in _SUPPORTED_ROUTER_FALLBACK_POLICIES:
        raise ValueError(
            f"{context}.{key} must be one of {sorted(_SUPPORTED_ROUTER_FALLBACK_POLICIES)}."
        )
    return raw.strip()


def _validate_capability_router_fallback_policies(
    *,
    capabilities: tuple[str, ...],
    chat_policy: str | None,
    embedding_policy: str | None,
    context: str,
) -> None:
    if chat_policy is not None and "chat_completions" not in capabilities:
        raise ValueError(
            f"{context}.chat_fallback_policy requires capability 'chat_completions'."
        )
    if embedding_policy is not None and "embeddings" not in capabilities:
        raise ValueError(
            f"{context}.embedding_fallback_policy requires capability 'embeddings'."
        )


def _parse_router_fallback_on(
    data: dict[str, Any],
    *,
    backend: str,
    context: str,
    key: str = "fallback_on",
) -> tuple[str, ...]:
    raw = data.get(key)
    if backend != "router":
        if raw is not None:
            raise ValueError(f"{context}.{key} is only supported for backend 'router'.")
        return ()
    if raw is None:
        return ()
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{context}.{key} must be a non-empty list when provided.")
    error_codes: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, str) or item not in _RETRYABLE_PROVIDER_ERROR_CODES:
            raise ValueError(
                f"{context}.{key}.{index} must be one of "
                f"{list(_RETRYABLE_PROVIDER_ERROR_CODE_ORDER)}."
            )
        if item not in error_codes:
            error_codes.append(item)
    return tuple(error_codes)


def _effective_router_fallback_policy(
    *,
    shared_policy: str | None,
    capability_policy: str | None,
) -> str:
    if capability_policy is not None:
        return capability_policy
    return shared_policy or _DEFAULT_ROUTER_FALLBACK_POLICY


def _validate_capability_router_fallback_on(
    *,
    capabilities: tuple[str, ...],
    shared_policy: str | None,
    chat_policy: str | None,
    embedding_policy: str | None,
    shared_codes: tuple[str, ...],
    chat_codes: tuple[str, ...],
    embedding_codes: tuple[str, ...],
    context: str,
) -> None:
    if chat_codes and "chat_completions" not in capabilities:
        raise ValueError(
            f"{context}.chat_fallback_on requires capability 'chat_completions'."
        )
    if embedding_codes and "embeddings" not in capabilities:
        raise ValueError(
            f"{context}.embedding_fallback_on requires capability 'embeddings'."
        )
    if shared_codes and (
        _effective_router_fallback_policy(
            shared_policy=shared_policy,
            capability_policy=chat_policy,
        )
        != "retryable_only"
        and _effective_router_fallback_policy(
            shared_policy=shared_policy,
            capability_policy=embedding_policy,
        )
        != "retryable_only"
    ):
        raise ValueError(
            f"{context}.fallback_on requires at least one retryable_only fallback policy."
        )
    if chat_codes and (
        _effective_router_fallback_policy(
            shared_policy=shared_policy,
            capability_policy=chat_policy,
        )
        != "retryable_only"
    ):
        raise ValueError(
            f"{context}.chat_fallback_on requires retryable_only chat fallback policy."
        )
    if embedding_codes and (
        _effective_router_fallback_policy(
            shared_policy=shared_policy,
            capability_policy=embedding_policy,
        )
        != "retryable_only"
    ):
        raise ValueError(
            f"{context}.embedding_fallback_on requires retryable_only embeddings fallback policy."
        )


def _parse_router_max_attempts(
    data: dict[str, Any],
    *,
    backend: str,
    context: str,
    key: str = "max_attempts",
) -> int | None:
    raw = data.get(key)
    if backend != "router":
        if raw is not None:
            raise ValueError(f"{context}.{key} is only supported for backend 'router'.")
        return None
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
        raise ValueError(f"{context}.{key} must be a positive integer.")
    return raw


def _validate_capability_router_max_attempts(
    *,
    capabilities: tuple[str, ...],
    chat_max_attempts: int | None,
    embedding_max_attempts: int | None,
    context: str,
) -> None:
    if chat_max_attempts is not None and "chat_completions" not in capabilities:
        raise ValueError(
            f"{context}.chat_max_attempts requires capability 'chat_completions'."
        )
    if embedding_max_attempts is not None and "embeddings" not in capabilities:
        raise ValueError(
            f"{context}.embedding_max_attempts requires capability 'embeddings'."
        )


def _parse_provider_timeout_seconds(
    data: dict[str, Any],
    *,
    context: str,
    key: str = "timeout_seconds",
) -> float | None:
    raw = data.get(key)
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or float(raw) <= 0.0:
        raise ValueError(f"{context}.{key} must be a positive number.")
    return float(raw)


def _validate_capability_timeout_seconds(
    *,
    capabilities: tuple[str, ...],
    chat_timeout_seconds: float | None,
    embedding_timeout_seconds: float | None,
    context: str,
) -> None:
    if chat_timeout_seconds is not None and "chat_completions" not in capabilities:
        raise ValueError(
            f"{context}.chat_timeout_seconds requires capability 'chat_completions'."
        )
    if embedding_timeout_seconds is not None and "embeddings" not in capabilities:
        raise ValueError(
            f"{context}.embedding_timeout_seconds requires capability 'embeddings'."
        )


def _validate_router_fields(
    data: dict[str, Any],
    *,
    backend: str,
    context: str,
) -> None:
    if backend != "router":
        return
    for key in (
        "base_url",
        "api_key_env",
        "model_name",
        "upstream_model",
        "embedding_input_type",
    ):
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        raise ValueError(
            f"{context}.{key} is not supported for backend 'router'."
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
            "max_tokens": 512,
        }
        if system_messages:
            payload["system"] = "\n".join(system_messages)
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


def _provider_config_map(
    configs: tuple[ProviderModelConfig, ...],
) -> dict[str, ProviderModelConfig]:
    return {config.model_id: config for config in configs}


def _router_targets_for_capability(
    *,
    config: ProviderModelConfig,
    capability: str,
) -> tuple[str, ...]:
    if capability == "chat_completions" and config.chat_routing_targets:
        return config.chat_routing_targets
    if capability == "embeddings" and config.embedding_routing_targets:
        return config.embedding_routing_targets
    return config.routing_targets


def _router_fallback_policy_for_capability(
    *,
    config: ProviderModelConfig,
    capability: str,
) -> str:
    if capability == "chat_completions" and config.chat_routing_fallback_policy is not None:
        return config.chat_routing_fallback_policy
    if capability == "embeddings" and config.embedding_routing_fallback_policy is not None:
        return config.embedding_routing_fallback_policy
    return config.routing_fallback_policy or _DEFAULT_ROUTER_FALLBACK_POLICY


def _router_fallback_on_for_capability(
    *,
    config: ProviderModelConfig,
    capability: str,
) -> tuple[str, ...]:
    if capability == "chat_completions" and config.chat_routing_fallback_on:
        return config.chat_routing_fallback_on
    if capability == "embeddings" and config.embedding_routing_fallback_on:
        return config.embedding_routing_fallback_on
    if config.routing_fallback_on:
        return config.routing_fallback_on
    return _RETRYABLE_PROVIDER_ERROR_CODE_ORDER


def _router_max_attempts_for_capability(
    *,
    config: ProviderModelConfig,
    capability: str,
) -> int | None:
    if capability == "chat_completions" and config.chat_routing_max_attempts is not None:
        return config.chat_routing_max_attempts
    if capability == "embeddings" and config.embedding_routing_max_attempts is not None:
        return config.embedding_routing_max_attempts
    return config.routing_max_attempts


def _provider_timeout_seconds_for_capability(
    *,
    config: ProviderModelConfig,
    capability: str,
) -> float:
    if capability == "chat_completions" and config.chat_timeout_seconds is not None:
        return config.chat_timeout_seconds
    if capability == "embeddings" and config.embedding_timeout_seconds is not None:
        return config.embedding_timeout_seconds
    if config.timeout_seconds is not None:
        return config.timeout_seconds
    return _DEFAULT_PROVIDER_TIMEOUT_SECONDS


def _provider_timeout_override_for_route(
    *,
    config: ProviderModelConfig,
    capability: str,
) -> float | None:
    if (
        config.timeout_seconds is None
        and config.chat_timeout_seconds is None
        and config.embedding_timeout_seconds is None
    ):
        return None
    return _provider_timeout_seconds_for_capability(config=config, capability=capability)


def provider_required_header_names(config: ProviderModelConfig) -> tuple[str, ...]:
    return tuple(header_name for header_name, _ in config.header_envs)


def _provider_capabilities_for_query(
    *,
    config: ProviderModelConfig,
    capability: str | None,
) -> tuple[str, ...]:
    if capability is not None:
        if capability not in _SUPPORTED_PROVIDER_CAPABILITY_ORDER:
            return ()
        if capability not in config.capabilities:
            return ()
        return (capability,)
    return tuple(
        supported_capability
        for supported_capability in _SUPPORTED_PROVIDER_CAPABILITY_ORDER
        if supported_capability in config.capabilities
    )


def get_provider_required_header_names_for_capability(
    *,
    model_id: str,
    capability: str,
) -> tuple[str, ...]:
    return _get_provider_required_header_names(
        model_id=model_id,
        capability=capability,
    )


def _get_provider_required_header_names(
    *,
    model_id: str,
    capability: str | None,
) -> tuple[str, ...]:
    config = get_configured_provider_model(model_id)
    if config is None:
        return ()

    ordered_header_names: list[str] = []
    seen_header_names: set[str] = set()

    def _append_headers(header_names: tuple[str, ...]) -> None:
        for header_name in header_names:
            normalized = header_name.lower()
            if normalized in seen_header_names:
                continue
            seen_header_names.add(normalized)
            ordered_header_names.append(header_name)

    if config.backend != "router":
        if capability is not None and capability not in config.capabilities:
            return ()
        _append_headers(provider_required_header_names(config))
        return tuple(ordered_header_names)

    for supported_capability in _provider_capabilities_for_query(
        config=config,
        capability=capability,
    ):
        for target in get_provider_route_targets(
            model_id=model_id,
            capability=supported_capability,
        ):
            _append_headers(provider_required_header_names(target))
    return tuple(ordered_header_names)


def get_provider_required_header_names(
    *,
    model_id: str,
) -> tuple[str, ...]:
    return _get_provider_required_header_names(model_id=model_id, capability=None)


def provider_required_auth_env_vars(config: ProviderModelConfig) -> tuple[str, ...]:
    env_vars: list[str] = []
    seen: set[str] = set()
    if config.api_key_env is not None:
        seen.add(config.api_key_env)
        env_vars.append(config.api_key_env)
    for _, env_name in config.header_envs:
        if env_name in seen:
            continue
        seen.add(env_name)
        env_vars.append(env_name)
    return tuple(env_vars)


def get_provider_required_auth_env_vars_for_capability(
    *,
    model_id: str,
    capability: str,
) -> tuple[str, ...]:
    return _get_provider_required_auth_env_vars(
        model_id=model_id,
        capability=capability,
    )


def _get_provider_required_auth_env_vars(
    *,
    model_id: str,
    capability: str | None,
) -> tuple[str, ...]:
    config = get_configured_provider_model(model_id)
    if config is None:
        return ()

    ordered_env_vars: list[str] = []
    seen_env_vars: set[str] = set()

    def _append_env_vars(env_vars: tuple[str, ...]) -> None:
        for env_var in env_vars:
            if env_var in seen_env_vars:
                continue
            seen_env_vars.add(env_var)
            ordered_env_vars.append(env_var)

    if config.backend != "router":
        if capability is not None and capability not in config.capabilities:
            return ()
        _append_env_vars(provider_required_auth_env_vars(config))
        return tuple(ordered_env_vars)

    for supported_capability in _provider_capabilities_for_query(
        config=config,
        capability=capability,
    ):
        for target in get_provider_route_targets(
            model_id=model_id,
            capability=supported_capability,
        ):
            _append_env_vars(provider_required_auth_env_vars(target))
    return tuple(ordered_env_vars)


def get_provider_required_auth_env_vars(
    *,
    model_id: str,
) -> tuple[str, ...]:
    return _get_provider_required_auth_env_vars(model_id=model_id, capability=None)


def provider_auth_configured_for_capability(
    *,
    model_id: str,
    capability: str,
) -> bool:
    env_vars = get_provider_required_auth_env_vars_for_capability(
        model_id=model_id,
        capability=capability,
    )
    return all(os.environ.get(env_var, "").strip() for env_var in env_vars)


def provider_auth_configured(
    *,
    model_id: str,
) -> bool:
    env_vars = get_provider_required_auth_env_vars(model_id=model_id)
    return all(os.environ.get(env_var, "").strip() for env_var in env_vars)


def get_provider_resolved_route_targets(
    *,
    model_id: str,
) -> tuple[str, ...]:
    config = get_configured_provider_model(model_id)
    if config is None or config.backend != "router":
        return ()
    resolved: list[str] = []
    for capability in _SUPPORTED_PROVIDER_CAPABILITY_ORDER:
        if capability not in config.capabilities:
            continue
        for target in get_provider_route_targets(model_id=model_id, capability=capability):
            if target.model_id in resolved:
                continue
            resolved.append(target.model_id)
    return tuple(resolved)


def get_provider_resolved_chat_route_targets(
    *,
    model_id: str,
) -> tuple[str, ...]:
    config = get_configured_provider_model(model_id)
    if config is None or config.backend != "router":
        return ()
    return tuple(
        target.model_id
        for target in get_provider_route_targets(
            model_id=model_id,
            capability="chat_completions",
        )
    )


def get_provider_resolved_embedding_route_targets(
    *,
    model_id: str,
) -> tuple[str, ...]:
    config = get_configured_provider_model(model_id)
    if config is None or config.backend != "router":
        return ()
    return tuple(
        target.model_id
        for target in get_provider_route_targets(
            model_id=model_id,
            capability="embeddings",
        )
    )


def _set_provider_attempts(result: Any, attempts: tuple[Any, ...]) -> Any:
    try:
        return replace(result, provider_attempts=attempts)
    except TypeError:
        try:
            setattr(result, "provider_attempts", attempts)
        except Exception:
            return result
        return result


def _provider_attempt_records_from_error(error: Exception) -> tuple[Any, ...]:
    from apps.api_server.services.llm_api_service import ProviderAttemptRecord

    details = getattr(error, "details", None)
    if not isinstance(details, dict):
        return ()
    raw_attempts = details.get("attempts")
    if not isinstance(raw_attempts, list):
        return ()

    records: list[ProviderAttemptRecord] = []
    for item in raw_attempts:
        if not isinstance(item, dict):
            continue
        backend = item.get("backend")
        model_id = item.get("target_model")
        error_code = item.get("code")
        if not isinstance(backend, str) or not isinstance(model_id, str):
            continue
        if error_code is not None and not isinstance(error_code, str):
            continue
        records.append(
            ProviderAttemptRecord(
                provider_backend=backend,
                provider_model_id=model_id,
                outcome="failed",
                error_code=error_code,
            )
        )
    return tuple(records)


def _provider_failure_details_from_error(
    *,
    error: Exception,
    target_model_id: str,
    target_backend: str,
) -> tuple[dict[str, Any], ...]:
    details = getattr(error, "details", None)
    raw_attempts = details.get("attempts") if isinstance(details, dict) else None
    if isinstance(raw_attempts, list):
        failures: list[dict[str, Any]] = []
        for item in raw_attempts:
            if not isinstance(item, dict):
                continue
            backend = item.get("backend")
            model_id = item.get("target_model")
            error_code = item.get("code")
            if not isinstance(backend, str) or not isinstance(model_id, str):
                continue
            if error_code is not None and not isinstance(error_code, str):
                continue
            failures.append(
                {
                    "target_model": model_id,
                    "backend": backend,
                    "code": error_code,
                }
            )
        if failures:
            return tuple(failures)
    return (
        {
            "target_model": target_model_id,
            "backend": target_backend,
            "code": getattr(error, "code", None),
        },
    )


def _merged_provider_attempts(
    *,
    result: Any,
    failed_attempts: tuple[Any, ...],
    selected_backend: str,
    selected_model_id: str,
) -> tuple[Any, ...]:
    from apps.api_server.services.llm_api_service import ProviderAttemptRecord

    existing_attempts = tuple(getattr(result, "provider_attempts", ()))
    if not existing_attempts:
        existing_attempts = (
            ProviderAttemptRecord(
                provider_backend=selected_backend,
                provider_model_id=selected_model_id,
                outcome="selected",
            ),
        )
    return (*failed_attempts, *existing_attempts)


def _resolve_provider_route_targets_from_map(
    *,
    config_by_id: dict[str, ProviderModelConfig],
    model_id: str,
    capability: str,
    seen: tuple[str, ...] = (),
) -> tuple[ProviderModelConfig, ...]:
    if model_id in seen:
        cycle = " -> ".join((*seen, model_id))
        raise ValueError(f"Provider router cycle detected: {cycle}.")
    config = config_by_id.get(model_id)
    if config is None:
        raise ValueError(f"Configured router target '{model_id}' was not found.")
    if capability not in config.capabilities:
        return ()
    if config.backend != "router":
        return (config,)

    resolved: list[ProviderModelConfig] = []
    emitted_model_ids: set[str] = set()
    for target_model_id in _router_targets_for_capability(config=config, capability=capability):
        for target in _resolve_provider_route_targets_from_map(
            config_by_id=config_by_id,
            model_id=target_model_id,
            capability=capability,
            seen=(*seen, model_id),
        ):
            if target.model_id in emitted_model_ids:
                continue
            emitted_model_ids.add(target.model_id)
            resolved.append(target)
    return tuple(resolved)


def _resolve_provider_reachable_route_targets_via_resolver(
    *,
    resolve_config: Callable[[str], ProviderModelConfig | None],
    model_id: str,
    capability: str,
    seen: tuple[str, ...] = (),
) -> tuple[ProviderModelConfig, ...]:
    if model_id in seen:
        cycle = " -> ".join((*seen, model_id))
        raise ValueError(f"Provider router cycle detected: {cycle}.")
    config = resolve_config(model_id)
    if config is None:
        raise ValueError(f"Configured router target '{model_id}' was not found.")
    if capability not in config.capabilities:
        return ()
    if config.backend != "router":
        return (config,)

    resolved: list[ProviderModelConfig] = []
    emitted_model_ids: set[str] = set()
    for target_model_id in _router_reachable_target_model_ids_for_capability(
        config=config,
        capability=capability,
        resolve_config=resolve_config,
        seen=seen,
    ):
        for target in _resolve_provider_reachable_route_targets_via_resolver(
            resolve_config=resolve_config,
            model_id=target_model_id,
            capability=capability,
            seen=(*seen, model_id),
        ):
            if target.model_id in emitted_model_ids:
                continue
            emitted_model_ids.add(target.model_id)
            resolved.append(target)
    return tuple(resolved)


def _resolve_provider_reachable_route_targets_from_map(
    *,
    config_by_id: dict[str, ProviderModelConfig],
    model_id: str,
    capability: str,
    seen: tuple[str, ...] = (),
) -> tuple[ProviderModelConfig, ...]:
    return _resolve_provider_reachable_route_targets_via_resolver(
        resolve_config=config_by_id.get,
        model_id=model_id,
        capability=capability,
        seen=seen,
    )


def _router_all_declared_target_model_ids(
    config: ProviderModelConfig,
) -> tuple[str, ...]:
    ordered_target_model_ids: list[str] = []
    for target_model_id in (
        *config.routing_targets,
        *config.chat_routing_targets,
        *config.embedding_routing_targets,
    ):
        if target_model_id in ordered_target_model_ids:
            continue
        ordered_target_model_ids.append(target_model_id)
    return tuple(ordered_target_model_ids)


def _resolve_provider_leaf_targets_from_map(
    *,
    config_by_id: dict[str, ProviderModelConfig],
    target_model_ids: tuple[str, ...],
    seen: tuple[str, ...] = (),
) -> tuple[ProviderModelConfig, ...]:
    resolved: list[ProviderModelConfig] = []
    emitted_model_ids: set[str] = set()
    for target_model_id in target_model_ids:
        if target_model_id in seen:
            cycle = " -> ".join((*seen, target_model_id))
            raise ValueError(f"Provider router cycle detected: {cycle}.")
        config = config_by_id.get(target_model_id)
        if config is None:
            raise ValueError(f"Configured router target '{target_model_id}' was not found.")
        if config.backend != "router":
            if config.model_id in emitted_model_ids:
                continue
            emitted_model_ids.add(config.model_id)
            resolved.append(config)
            continue
        nested_target_model_ids: list[str] = list(config.routing_targets)
        for target_model_id in (*config.chat_routing_targets, *config.embedding_routing_targets):
            if target_model_id in nested_target_model_ids:
                continue
            nested_target_model_ids.append(target_model_id)
        for target in _resolve_provider_leaf_targets_from_map(
            config_by_id=config_by_id,
            target_model_ids=tuple(nested_target_model_ids),
            seen=(*seen, target_model_id),
        ):
            if target.model_id in emitted_model_ids:
                continue
            emitted_model_ids.add(target.model_id)
            resolved.append(target)
    return tuple(resolved)


@lru_cache(maxsize=1)
def load_provider_model_configs() -> tuple[ProviderModelConfig, ...]:
    raw = os.environ.get(_PROVIDER_MODELS_ENV, "").strip()
    if not raw:
        return ()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{_PROVIDER_MODELS_ENV} must be valid JSON.") from exc
    if not isinstance(payload, list):
        raise ValueError(f"{_PROVIDER_MODELS_ENV} must decode to a list.")

    configs: list[ProviderModelConfig] = []
    seen_model_ids: set[str] = set()
    for index, item in enumerate(payload):
        context = f"{_PROVIDER_MODELS_ENV}[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{context} must be an object.")
        model_id = _require_non_empty_string(item, "id", context)
        if model_id in seen_model_ids:
            raise ValueError(f"{context}.id duplicates configured provider model '{model_id}'.")
        seen_model_ids.add(model_id)
        backend = _require_non_empty_string(item, "backend", context)
        capabilities = _validate_backend_capabilities(
            backend=backend,
            capabilities=_parse_capabilities(item, backend=backend, context=context),
            context=context,
        )
        routing_targets = _parse_router_targets(item, backend=backend, context=context)
        chat_routing_targets = _parse_capability_router_targets(
            item,
            backend=backend,
            context=context,
            key="chat_targets",
        )
        embedding_routing_targets = _parse_capability_router_targets(
            item,
            backend=backend,
            context=context,
            key="embedding_targets",
        )
        routing_fallback_policy = _parse_router_fallback_policy(
            item,
            backend=backend,
            context=context,
            default=_DEFAULT_ROUTER_FALLBACK_POLICY,
        )
        chat_routing_fallback_policy = _parse_router_fallback_policy(
            item,
            backend=backend,
            context=context,
            key="chat_fallback_policy",
        )
        embedding_routing_fallback_policy = _parse_router_fallback_policy(
            item,
            backend=backend,
            context=context,
            key="embedding_fallback_policy",
        )
        routing_fallback_on = _parse_router_fallback_on(
            item,
            backend=backend,
            context=context,
        )
        chat_routing_fallback_on = _parse_router_fallback_on(
            item,
            backend=backend,
            context=context,
            key="chat_fallback_on",
        )
        embedding_routing_fallback_on = _parse_router_fallback_on(
            item,
            backend=backend,
            context=context,
            key="embedding_fallback_on",
        )
        timeout_seconds = _parse_provider_timeout_seconds(
            item,
            context=context,
        )
        chat_timeout_seconds = _parse_provider_timeout_seconds(
            item,
            context=context,
            key="chat_timeout_seconds",
        )
        embedding_timeout_seconds = _parse_provider_timeout_seconds(
            item,
            context=context,
            key="embedding_timeout_seconds",
        )
        header_envs = _parse_provider_header_envs(
            item,
            backend=backend,
            context=context,
        )
        routing_max_attempts = _parse_router_max_attempts(
            item,
            backend=backend,
            context=context,
        )
        chat_routing_max_attempts = _parse_router_max_attempts(
            item,
            backend=backend,
            context=context,
            key="chat_max_attempts",
        )
        embedding_routing_max_attempts = _parse_router_max_attempts(
            item,
            backend=backend,
            context=context,
            key="embedding_max_attempts",
        )
        _validate_router_fields(item, backend=backend, context=context)
        _validate_capability_router_fallback_policies(
            capabilities=capabilities,
            chat_policy=chat_routing_fallback_policy,
            embedding_policy=embedding_routing_fallback_policy,
            context=context,
        )
        _validate_capability_router_fallback_on(
            capabilities=capabilities,
            shared_policy=routing_fallback_policy,
            chat_policy=chat_routing_fallback_policy,
            embedding_policy=embedding_routing_fallback_policy,
            shared_codes=routing_fallback_on,
            chat_codes=chat_routing_fallback_on,
            embedding_codes=embedding_routing_fallback_on,
            context=context,
        )
        _validate_capability_router_max_attempts(
            capabilities=capabilities,
            chat_max_attempts=chat_routing_max_attempts,
            embedding_max_attempts=embedding_routing_max_attempts,
            context=context,
        )
        _validate_capability_timeout_seconds(
            capabilities=capabilities,
            chat_timeout_seconds=chat_timeout_seconds,
            embedding_timeout_seconds=embedding_timeout_seconds,
            context=context,
        )
        if backend == "router":
            description = str(item.get("description") or "").strip()
            if not description:
                description = (
                    f"Deterministic ordered provider router alias for model '{model_id}'."
                )
            configs.append(
                ProviderModelConfig(
                    model_id=model_id,
                    backend=backend,
                    base_url="",
                    upstream_model=model_id,
                    api_key_env=None,
                    description=description,
                    capabilities=capabilities,
                    routing_targets=routing_targets,
                    chat_routing_targets=chat_routing_targets,
                    embedding_routing_targets=embedding_routing_targets,
                    routing_fallback_policy=routing_fallback_policy,
                    chat_routing_fallback_policy=chat_routing_fallback_policy,
                    embedding_routing_fallback_policy=embedding_routing_fallback_policy,
                    routing_fallback_on=routing_fallback_on,
                    chat_routing_fallback_on=chat_routing_fallback_on,
                    embedding_routing_fallback_on=embedding_routing_fallback_on,
                    routing_max_attempts=routing_max_attempts,
                    chat_routing_max_attempts=chat_routing_max_attempts,
                    embedding_routing_max_attempts=embedding_routing_max_attempts,
                    timeout_seconds=timeout_seconds,
                    chat_timeout_seconds=chat_timeout_seconds,
                    embedding_timeout_seconds=embedding_timeout_seconds,
                    header_envs=header_envs,
                )
            )
            continue

        base_url = _require_non_empty_string(item, "base_url", context).rstrip("/")
        raw_api_key_env = item.get("api_key_env")
        api_key_env: str | None
        if raw_api_key_env is None or str(raw_api_key_env).strip() == "":
            if backend in _OPTIONAL_PROVIDER_API_KEY_BACKENDS:
                api_key_env = None
            else:
                raise ValueError(f"{context}.api_key_env must be a non-empty string.")
        else:
            api_key_env = _require_non_empty_string(item, "api_key_env", context)
        upstream_model = _resolve_upstream_model(item, context, model_id)
        description = str(item.get("description") or "").strip()
        if not description:
            description = (
                f"Provider-backed OpenAI-compatible model routed through configured backend "
                f"'{backend}'."
            )
        configs.append(
            ProviderModelConfig(
                model_id=model_id,
                backend=backend,
                base_url=base_url,
                upstream_model=upstream_model,
                api_key_env=api_key_env,
                description=description,
                capabilities=capabilities,
                embedding_input_type=_validate_embedding_input_type(
                    backend=backend,
                    raw_value=item.get("embedding_input_type"),
                    context=context,
                ),
                routing_targets=routing_targets,
                chat_routing_targets=chat_routing_targets,
                embedding_routing_targets=embedding_routing_targets,
                routing_fallback_policy=routing_fallback_policy,
                chat_routing_fallback_policy=chat_routing_fallback_policy,
                embedding_routing_fallback_policy=embedding_routing_fallback_policy,
                routing_fallback_on=routing_fallback_on,
                chat_routing_fallback_on=chat_routing_fallback_on,
                embedding_routing_fallback_on=embedding_routing_fallback_on,
                routing_max_attempts=routing_max_attempts,
                chat_routing_max_attempts=chat_routing_max_attempts,
                embedding_routing_max_attempts=embedding_routing_max_attempts,
                timeout_seconds=timeout_seconds,
                chat_timeout_seconds=chat_timeout_seconds,
                embedding_timeout_seconds=embedding_timeout_seconds,
                header_envs=header_envs,
            )
        )
    config_by_id = _provider_config_map(tuple(configs))
    for config in configs:
        if config.backend != "router":
            continue
        if not config.routing_targets:
            if not config.chat_routing_targets and not config.embedding_routing_targets:
                raise ValueError(
                    f"Configured router model '{config.model_id}' must declare at least one target."
                )
        for capability in config.capabilities:
            resolved_targets = _resolve_provider_reachable_route_targets_from_map(
                config_by_id=config_by_id,
                model_id=config.model_id,
                capability=capability,
            )
            if not resolved_targets:
                raise ValueError(
                    f"Configured router model '{config.model_id}' has no targets for capability '{capability}'."
                )
    return tuple(configs)


def _provider_auth_headers(config: ProviderModelConfig) -> dict[str, str]:
    from apps.api_server.services.llm_api_service import LLMAPIError

    def _require_env_value(env_name: str, *, header_name: str | None = None) -> str:
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
        details: dict[str, Any] = {"model": config.model_id, "env_name": env_name}
        if header_name is None:
            details["api_key_env"] = env_name
            message = (
                f"Provider-backed model '{config.model_id}' is configured, but "
                f"environment variable '{env_name}' is not set."
            )
        else:
            details["header_name"] = header_name
            message = (
                f"Provider-backed model '{config.model_id}' requires header '{header_name}', "
                f"but environment variable '{env_name}' is not set."
            )
        raise LLMAPIError("backend_unavailable", message, details)

    headers: dict[str, str]
    if config.api_key_env is None:
        headers = {"Content-Type": "application/json"}
    else:
        api_key = _require_env_value(config.api_key_env)
        if config.backend == "anthropic":
            headers = {
                "x-api-key": api_key,
                "anthropic-version": _ANTHROPIC_API_VERSION,
                "Content-Type": "application/json",
            }
        elif config.backend == "google_genai":
            headers = {
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            }
        elif config.backend == "ollama":
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        else:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

    for header_name, env_name in config.header_envs:
        headers[header_name] = _require_env_value(env_name, header_name=header_name)
    return headers


async def _provider_post_json(
    *,
    config: ProviderModelConfig,
    path: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    from apps.api_server.services.llm_api_service import LLMAPIError

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                f"{config.base_url}{path}",
                json=payload,
                headers=_provider_auth_headers(config),
            )
    except httpx.TimeoutException as exc:
        raise LLMAPIError(
            "provider_timeout",
            f"Provider backend timed out for model '{config.model_id}'.",
            {"model": config.model_id, "backend": config.backend},
        ) from exc
    except httpx.HTTPError as exc:
        raise LLMAPIError(
            "backend_unavailable",
            f"Provider backend is unavailable for model '{config.model_id}'.",
            {"model": config.model_id, "backend": config.backend},
        ) from exc

    if response.status_code >= 400:
        detail: Any
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        if response.status_code == 429:
            raise LLMAPIError(
                "provider_rate_limited",
                f"Provider backend rate limited model '{config.model_id}'.",
                {"model": config.model_id, "status_code": response.status_code, "response": detail},
            )
        if response.status_code in {401, 403}:
            raise LLMAPIError(
                "provider_authentication_failed",
                f"Provider backend rejected credentials for model '{config.model_id}'.",
                {"model": config.model_id, "status_code": response.status_code, "response": detail},
            )
        if 400 <= response.status_code < 500:
            raise LLMAPIError(
                "invalid_provider_request",
                f"Provider backend rejected the request for model '{config.model_id}'.",
                {"model": config.model_id, "status_code": response.status_code, "response": detail},
            )
        raise LLMAPIError(
            "provider_backend_error",
            f"Provider backend returned HTTP {response.status_code} for model '{config.model_id}'.",
            {"model": config.model_id, "status_code": response.status_code, "response": detail},
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise LLMAPIError(
            "invalid_provider_response",
            f"Provider backend returned invalid JSON for model '{config.model_id}'.",
            {"model": config.model_id, "backend": config.backend},
        ) from exc
    if not isinstance(data, dict):
        raise LLMAPIError(
            "invalid_provider_response",
            f"Provider backend returned an invalid payload for model '{config.model_id}'.",
            {"model": config.model_id, "backend": config.backend},
        )
    return data


def get_configured_provider_model(model_id: str) -> ProviderModelConfig | None:
    for config in load_provider_model_configs():
        if config.model_id == model_id:
            return config
    return None


def get_provider_route_targets(
    *,
    model_id: str,
    capability: str,
) -> tuple[ProviderModelConfig, ...]:
    config_by_id = _provider_config_map(load_provider_model_configs())
    config = config_by_id.get(model_id)
    if config is None:
        return ()
    return _resolve_provider_reachable_route_targets_from_map(
        config_by_id=config_by_id,
        model_id=model_id,
        capability=capability,
    )


def _router_declared_target_model_ids_for_capability(
    *,
    config: ProviderModelConfig,
    capability: str,
) -> tuple[str, ...]:
    return _router_targets_for_capability(config=config, capability=capability)


def _router_attempt_target_model_ids_for_capability(
    *,
    config: ProviderModelConfig,
    capability: str,
    resolve_config: Callable[[str], ProviderModelConfig | None],
    seen: tuple[str, ...] = (),
) -> tuple[str, ...]:
    target_model_ids = _router_declared_target_model_ids_for_capability(
        config=config,
        capability=capability,
    )
    max_attempts = _router_max_attempts_for_capability(config=config, capability=capability)
    effective_target_model_ids: list[str] = []
    for target_model_id in target_model_ids:
        target_config = resolve_config(target_model_id)
        if target_config is None:
            effective_target_model_ids.append(target_model_id)
        else:
            reachable_targets = _resolve_provider_reachable_route_targets_via_resolver(
                resolve_config=resolve_config,
                model_id=target_model_id,
                capability=capability,
                seen=(*seen, config.model_id),
            )
            if not reachable_targets:
                continue
            effective_target_model_ids.append(target_model_id)
        if max_attempts is not None and len(effective_target_model_ids) >= max_attempts:
            break
    return tuple(effective_target_model_ids)


def _router_reachable_target_model_ids_for_capability(
    *,
    config: ProviderModelConfig,
    capability: str,
    resolve_config: Callable[[str], ProviderModelConfig | None],
    seen: tuple[str, ...] = (),
) -> tuple[str, ...]:
    target_model_ids = _router_attempt_target_model_ids_for_capability(
        config=config,
        capability=capability,
        resolve_config=resolve_config,
        seen=seen,
    )
    if not target_model_ids:
        return ()
    if _router_fallback_policy_for_capability(config=config, capability=capability) == "retryable_only":
        return target_model_ids
    return target_model_ids[:1]


def _router_uses_nested_router_targets(
    *,
    config: ProviderModelConfig,
    capability: str,
) -> bool:
    for target_model_id in _router_reachable_target_model_ids_for_capability(
        config=config,
        capability=capability,
        resolve_config=get_configured_provider_model,
    ):
        target_config = get_configured_provider_model(target_model_id)
        if target_config is not None and target_config.backend == "router":
            return True
    return False


async def _execute_router_chat_completion(
    *,
    model_id: str,
    messages: list[dict[str, str]],
    timeout_seconds: float | None = None,
    seen: tuple[str, ...] = (),
) -> Any:
    from apps.api_server.services.llm_api_service import LLMAPIError, ProviderAttemptRecord

    if model_id in seen:
        cycle = " -> ".join((*seen, model_id))
        raise LLMAPIError(
            "backend_unavailable",
            f"Provider router cycle detected: {cycle}.",
            {"model": model_id, "cycle": cycle},
        )

    config = get_configured_provider_model(model_id)
    if config is None or "chat_completions" not in config.capabilities:
        raise LLMAPIError(
            "model_not_supported",
            f"Model '{model_id}' is not configured for provider-backed chat completions.",
            {"model": model_id, "required_capability": "chat_completions"},
        )
    if config.backend != "router":
        return await provider_chat_completion(
            config=config,
            messages=messages,
            timeout_seconds=timeout_seconds,
        )

    route_timeout_seconds = _provider_timeout_override_for_route(
        config=config,
        capability="chat_completions",
    )
    effective_timeout_seconds = (
        route_timeout_seconds if route_timeout_seconds is not None else timeout_seconds
    )
    target_model_ids = _router_reachable_target_model_ids_for_capability(
        config=config,
        capability="chat_completions",
        resolve_config=get_configured_provider_model,
        seen=seen,
    )
    if not target_model_ids:
        raise LLMAPIError(
            "model_not_supported",
            f"Model '{model_id}' is not configured for provider-backed chat completions.",
            {"model": model_id, "required_capability": "chat_completions"},
        )

    failures: list[dict[str, Any]] = []
    attempt_records: list[ProviderAttemptRecord] = []
    last_error: LLMAPIError | None = None
    for target_model_id in target_model_ids:
        target_config = get_configured_provider_model(target_model_id)
        target_backend = target_config.backend if target_config is not None else "router"
        try:
            result = await _execute_router_chat_completion(
                model_id=target_model_id,
                messages=messages,
                timeout_seconds=effective_timeout_seconds,
                seen=(*seen, model_id),
            )
            if attempt_records:
                provider = getattr(result, "provider", None)
                return _set_provider_attempts(
                    result,
                    _merged_provider_attempts(
                        result=result,
                        failed_attempts=tuple(attempt_records),
                        selected_backend=getattr(provider, "provider_backend", target_backend),
                        selected_model_id=getattr(provider, "provider_model_id", target_model_id),
                    ),
                )
            return result
        except LLMAPIError as exc:
            last_error = exc
            failures.extend(
                _provider_failure_details_from_error(
                    error=exc,
                    target_model_id=target_model_id,
                    target_backend=target_backend,
                )
            )
            nested_attempts = _provider_attempt_records_from_error(exc)
            if nested_attempts:
                attempt_records.extend(nested_attempts)
            else:
                attempt_records.append(
                    ProviderAttemptRecord(
                        provider_backend=target_backend,
                        provider_model_id=target_model_id,
                        outcome="failed",
                        error_code=exc.code,
                    )
                )
            if exc.code not in _RETRYABLE_PROVIDER_ERROR_CODES:
                raise
            if (
                _router_fallback_policy_for_capability(
                    config=config,
                    capability="chat_completions",
                )
                != "retryable_only"
                or exc.code
                not in _router_fallback_on_for_capability(
                    config=config,
                    capability="chat_completions",
                )
            ):
                raise

    assert last_error is not None
    raise LLMAPIError(
        last_error.code,
        f"All configured provider targets failed for model '{model_id}'.",
        {
            "model": model_id,
            "required_capability": "chat_completions",
            "attempts": failures,
        },
    ) from last_error


async def _execute_router_embeddings(
    *,
    model_id: str,
    inputs: list[str],
    dimensions: int,
    timeout_seconds: float | None = None,
    seen: tuple[str, ...] = (),
) -> tuple[list[Any], int]:
    from apps.api_server.services.llm_api_service import LLMAPIError, ProviderAttemptRecord

    if model_id in seen:
        cycle = " -> ".join((*seen, model_id))
        raise LLMAPIError(
            "backend_unavailable",
            f"Provider router cycle detected: {cycle}.",
            {"model": model_id, "cycle": cycle},
        )

    config = get_configured_provider_model(model_id)
    if config is None or "embeddings" not in config.capabilities:
        raise LLMAPIError(
            "model_not_supported",
            f"Model '{model_id}' is not configured for provider-backed embeddings.",
            {"model": model_id, "required_capability": "embeddings"},
        )
    if config.backend != "router":
        return await provider_embeddings(
            config=config,
            inputs=inputs,
            dimensions=dimensions,
            timeout_seconds=timeout_seconds,
        )

    route_timeout_seconds = _provider_timeout_override_for_route(
        config=config,
        capability="embeddings",
    )
    effective_timeout_seconds = (
        route_timeout_seconds if route_timeout_seconds is not None else timeout_seconds
    )
    target_model_ids = _router_reachable_target_model_ids_for_capability(
        config=config,
        capability="embeddings",
        resolve_config=get_configured_provider_model,
        seen=seen,
    )
    if not target_model_ids:
        raise LLMAPIError(
            "model_not_supported",
            f"Model '{model_id}' is not configured for provider-backed embeddings.",
            {"model": model_id, "required_capability": "embeddings"},
        )

    failures: list[dict[str, Any]] = []
    attempt_records: list[ProviderAttemptRecord] = []
    last_error: LLMAPIError | None = None
    for target_model_id in target_model_ids:
        target_config = get_configured_provider_model(target_model_id)
        target_backend = target_config.backend if target_config is not None else "router"
        try:
            generated, total_tokens = await _execute_router_embeddings(
                model_id=target_model_id,
                inputs=inputs,
                dimensions=dimensions,
                timeout_seconds=effective_timeout_seconds,
                seen=(*seen, model_id),
            )
            if not attempt_records:
                return generated, total_tokens
            return (
                [
                    _set_provider_attempts(
                        item,
                        _merged_provider_attempts(
                            result=item,
                            failed_attempts=tuple(attempt_records),
                            selected_backend=getattr(
                                getattr(item, "provider", None),
                                "provider_backend",
                                target_backend,
                            ),
                            selected_model_id=getattr(
                                getattr(item, "provider", None),
                                "provider_model_id",
                                target_model_id,
                            ),
                        ),
                    )
                    for item in generated
                ],
                total_tokens,
            )
        except LLMAPIError as exc:
            last_error = exc
            failures.extend(
                _provider_failure_details_from_error(
                    error=exc,
                    target_model_id=target_model_id,
                    target_backend=target_backend,
                )
            )
            nested_attempts = _provider_attempt_records_from_error(exc)
            if nested_attempts:
                attempt_records.extend(nested_attempts)
            else:
                attempt_records.append(
                    ProviderAttemptRecord(
                        provider_backend=target_backend,
                        provider_model_id=target_model_id,
                        outcome="failed",
                        error_code=exc.code,
                    )
                )
            if exc.code not in _RETRYABLE_PROVIDER_ERROR_CODES:
                raise
            if (
                _router_fallback_policy_for_capability(
                    config=config,
                    capability="embeddings",
                )
                != "retryable_only"
                or exc.code
                not in _router_fallback_on_for_capability(
                    config=config,
                    capability="embeddings",
                )
            ):
                raise

    assert last_error is not None
    raise LLMAPIError(
        last_error.code,
        f"All configured provider targets failed for model '{model_id}'.",
        {
            "model": model_id,
            "required_capability": "embeddings",
            "attempts": failures,
        },
    ) from last_error


async def provider_chat_completion(
    *,
    config: ProviderModelConfig,
    messages: list[dict[str, str]],
    timeout_seconds: float | None = None,
) -> Any:
    data = await _provider_post_json(
        config=config,
        path=_provider_chat_path(config),
        payload=_provider_chat_payload(config=config, messages=messages),
        timeout_seconds=(
            timeout_seconds
            if timeout_seconds is not None
            else _provider_timeout_seconds_for_capability(
                config=config,
                capability="chat_completions",
            )
        ),
    )
    return _parse_provider_chat_completion(config=config, data=data)


async def routed_provider_chat_completion(
    *,
    model_id: str,
    messages: list[dict[str, str]],
) -> Any:
    from apps.api_server.services.llm_api_service import LLMAPIError, ProviderAttemptRecord

    router_config = get_configured_provider_model(model_id)
    if (
        router_config is not None
        and router_config.backend == "router"
        and _router_uses_nested_router_targets(
            config=router_config,
            capability="chat_completions",
        )
    ):
        return await _execute_router_chat_completion(
            model_id=model_id,
            messages=messages,
        )
    targets = get_provider_route_targets(
        model_id=model_id,
        capability="chat_completions",
    )
    if router_config is not None and router_config.backend == "router":
        max_attempts = _router_max_attempts_for_capability(
            config=router_config,
            capability="chat_completions",
        )
        if max_attempts is not None:
            targets = targets[:max_attempts]
    route_timeout_seconds = (
        _provider_timeout_override_for_route(
            config=router_config,
            capability="chat_completions",
        )
        if router_config is not None and router_config.backend == "router"
        else None
    )
    if not targets:
        raise LLMAPIError(
            "model_not_supported",
            f"Model '{model_id}' is not configured for provider-backed chat completions.",
            {"model": model_id, "required_capability": "chat_completions"},
        )

    failures: list[dict[str, Any]] = []
    attempt_records: list[ProviderAttemptRecord] = []
    last_error: LLMAPIError | None = None
    for target in targets:
        try:
            result = await provider_chat_completion(
                config=target,
                messages=messages,
                timeout_seconds=route_timeout_seconds,
            )
            if attempt_records:
                return _set_provider_attempts(
                    result,
                    _merged_provider_attempts(
                        result=result,
                        failed_attempts=tuple(attempt_records),
                        selected_backend=target.backend,
                        selected_model_id=target.model_id,
                    ),
                )
            return result
        except LLMAPIError as exc:
            last_error = exc
            failures.append(
                {
                    "target_model": target.model_id,
                    "backend": target.backend,
                    "code": exc.code,
                }
            )
            attempt_records.append(
                ProviderAttemptRecord(
                    provider_backend=target.backend,
                    provider_model_id=target.model_id,
                    outcome="failed",
                    error_code=exc.code,
                )
            )
            if exc.code not in _RETRYABLE_PROVIDER_ERROR_CODES:
                raise
            if (
                router_config is None
                or router_config.backend != "router"
                or _router_fallback_policy_for_capability(
                    config=router_config,
                    capability="chat_completions",
                )
                != "retryable_only"
                or exc.code
                not in _router_fallback_on_for_capability(
                    config=router_config,
                    capability="chat_completions",
                )
            ):
                raise

    assert last_error is not None
    raise LLMAPIError(
        last_error.code,
        f"All configured provider targets failed for model '{model_id}'.",
        {
            "model": model_id,
            "required_capability": "chat_completions",
            "attempts": failures,
        },
    ) from last_error


async def provider_embeddings(
    *,
    config: ProviderModelConfig,
    inputs: list[str],
    dimensions: int,
    timeout_seconds: float | None = None,
) -> tuple[list[Any], int]:
    from apps.api_server.services.llm_api_service import (
        GeneratedEmbedding,
        LLMAPIError,
        ProviderAttemptRecord,
        ProviderExecutionMetadata,
    )

    provider = ProviderExecutionMetadata(
        provider_backend=config.backend,
        provider_model_id=config.model_id,
    )
    selected_attempt = (
        ProviderAttemptRecord(
            provider_backend=config.backend,
            provider_model_id=config.model_id,
            outcome="selected",
        ),
    )

    if config.backend == "google_genai":
        model_resource = _provider_model_resource(config)
        if len(inputs) > 1:
            data = await _provider_post_json(
                config=config,
                path=f"/{model_resource}:batchEmbedContents",
                payload={
                    "requests": [
                        {
                            "model": model_resource,
                            "content": {"parts": [{"text": text}]},
                            "embedContentConfig": {"outputDimensionality": dimensions},
                        }
                        for text in inputs
                    ],
                },
                timeout_seconds=(
                    timeout_seconds
                    if timeout_seconds is not None
                    else _provider_timeout_seconds_for_capability(
                        config=config,
                        capability="embeddings",
                    )
                ),
            )
            try:
                raw_embeddings = data["embeddings"]
                usage = data["usageMetadata"]
                total_tokens = int(usage.get("promptTokenCount") or usage.get("totalTokenCount") or 0)
            except (KeyError, TypeError, ValueError) as exc:
                raise LLMAPIError(
                    "invalid_provider_response",
                    (
                        f"Provider backend returned an invalid embeddings payload for "
                        f"model '{config.model_id}'."
                    ),
                    {"model": config.model_id, "backend": config.backend},
                ) from exc
            if not isinstance(raw_embeddings, list) or len(raw_embeddings) != len(inputs):
                raise LLMAPIError(
                    "invalid_provider_response",
                    (
                        f"Provider backend returned an invalid embeddings payload for "
                        f"model '{config.model_id}'."
                    ),
                    {"model": config.model_id, "backend": config.backend},
                )
            generated = []
            for index, item in enumerate(raw_embeddings):
                values = item.get("values") if isinstance(item, dict) else None
                if not isinstance(values, list) or any(
                    isinstance(value, bool) or not isinstance(value, (int, float)) for value in values
                ):
                    raise LLMAPIError(
                        "invalid_provider_response",
                        (
                            f"Provider backend returned an invalid embeddings payload for "
                            f"model '{config.model_id}'."
                        ),
                        {"model": config.model_id, "backend": config.backend},
                    )
                generated.append(
                    GeneratedEmbedding(
                        index=index,
                        embedding=[float(value) for value in values],
                        token_count=0,
                        provider=provider,
                        provider_attempts=selected_attempt,
                    )
                )
            return generated, total_tokens

        generated: list[GeneratedEmbedding] = []
        total_tokens = 0
        for index, text in enumerate(inputs):
            data = await _provider_post_json(
                config=config,
                path=_provider_embeddings_path(config),
                payload={
                    "model": model_resource,
                    "content": {"parts": [{"text": text}]},
                    "embedContentConfig": {"outputDimensionality": dimensions},
                },
                timeout_seconds=(
                    timeout_seconds
                    if timeout_seconds is not None
                    else _provider_timeout_seconds_for_capability(
                        config=config,
                        capability="embeddings",
                    )
                ),
            )
            try:
                embedding = data["embedding"]["values"]
                usage = data["usageMetadata"]
                token_count = int(usage["promptTokenCount"])
            except (KeyError, TypeError, ValueError) as exc:
                raise LLMAPIError(
                    "invalid_provider_response",
                    (
                        f"Provider backend returned an invalid embeddings payload for "
                        f"model '{config.model_id}'."
                    ),
                    {"model": config.model_id, "backend": config.backend},
                ) from exc
            if not isinstance(embedding, list) or any(
                isinstance(value, bool) or not isinstance(value, (int, float)) for value in embedding
            ):
                raise LLMAPIError(
                    "invalid_provider_response",
                    (
                        f"Provider backend returned an invalid embeddings payload for "
                        f"model '{config.model_id}'."
                    ),
                    {"model": config.model_id, "backend": config.backend},
                )
            total_tokens += token_count
            generated.append(
                GeneratedEmbedding(
                    index=index,
                    embedding=[float(value) for value in embedding],
                    token_count=token_count,
                    provider=provider,
                    provider_attempts=selected_attempt,
                )
            )
        return generated, total_tokens

    if config.backend == "cohere":
        data = await _provider_post_json(
            config=config,
            path=_provider_embeddings_path(config),
            payload=_provider_embeddings_payload(
                config=config,
                inputs=inputs,
                dimensions=dimensions,
            ),
            timeout_seconds=(
                timeout_seconds
                if timeout_seconds is not None
                else _provider_timeout_seconds_for_capability(
                    config=config,
                    capability="embeddings",
                )
            ),
        )
        try:
            embeddings = data["embeddings"]
            raw_vectors = embeddings["float"]
            meta = data.get("meta") or {}
            billed_units = meta.get("billed_units") or meta.get("tokens") or {}
            total_tokens = int(billed_units.get("input_tokens") or 0)
        except (KeyError, TypeError, ValueError) as exc:
            raise LLMAPIError(
                "invalid_provider_response",
                f"Provider backend returned an invalid embeddings payload for model '{config.model_id}'.",
                {"model": config.model_id, "backend": config.backend},
            ) from exc
        if not isinstance(raw_vectors, list) or len(raw_vectors) != len(inputs):
            raise LLMAPIError(
                "invalid_provider_response",
                f"Provider backend returned an invalid embeddings payload for model '{config.model_id}'.",
                {"model": config.model_id, "backend": config.backend},
            )
        generated = []
        for index, embedding in enumerate(raw_vectors):
            if not isinstance(embedding, list) or any(
                isinstance(value, bool) or not isinstance(value, (int, float)) for value in embedding
            ):
                raise LLMAPIError(
                    "invalid_provider_response",
                    f"Provider backend returned an invalid embeddings payload for model '{config.model_id}'.",
                    {"model": config.model_id, "backend": config.backend},
                )
            generated.append(
                GeneratedEmbedding(
                    index=index,
                    embedding=[float(value) for value in embedding],
                    token_count=0,
                    provider=provider,
                    provider_attempts=selected_attempt,
                )
            )
        return generated, total_tokens

    data = await _provider_post_json(
        config=config,
        path=_provider_embeddings_path(config),
        payload=_provider_embeddings_payload(
            config=config,
            inputs=inputs,
            dimensions=dimensions,
        ),
        timeout_seconds=(
            timeout_seconds
            if timeout_seconds is not None
            else _provider_timeout_seconds_for_capability(
                config=config,
                capability="embeddings",
            )
        ),
    )
    try:
        if config.backend == "ollama":
            raw_vectors = data["embeddings"]
            total_tokens = int(data["prompt_eval_count"])
        else:
            raw_vectors = data["data"]
            usage = data["usage"]
            total_tokens = int(usage["prompt_tokens"])
    except (KeyError, TypeError, ValueError) as exc:
        raise LLMAPIError(
            "invalid_provider_response",
            f"Provider backend returned an invalid embeddings payload for model '{config.model_id}'.",
            {"model": config.model_id, "backend": config.backend},
        ) from exc
    if not isinstance(raw_vectors, list) or len(raw_vectors) != len(inputs):
        raise LLMAPIError(
            "invalid_provider_response",
            f"Provider backend returned an invalid embeddings payload for model '{config.model_id}'.",
            {"model": config.model_id, "backend": config.backend},
        )

    generated: list[GeneratedEmbedding] = []
    for index, item in enumerate(raw_vectors):
        token_count: int | object
        if config.backend == "ollama":
            embedding = item
            token_count = total_tokens if len(inputs) == 1 else 0
        else:
            if not isinstance(item, dict):
                raise LLMAPIError(
                    "invalid_provider_response",
                    f"Provider backend returned an invalid embeddings payload for model '{config.model_id}'.",
                    {"model": config.model_id, "backend": config.backend},
                )
            embedding = item.get("embedding")
            token_count = item.get("token_count")
        if not isinstance(embedding, list) or any(
            isinstance(value, bool) or not isinstance(value, (int, float)) for value in embedding
        ):
            raise LLMAPIError(
                "invalid_provider_response",
                f"Provider backend returned an invalid embeddings payload for model '{config.model_id}'.",
                {"model": config.model_id, "backend": config.backend},
            )
        if isinstance(token_count, bool) or not isinstance(token_count, int):
            token_count = 0
        generated.append(
            GeneratedEmbedding(
                index=index,
                embedding=[float(value) for value in embedding],
                token_count=token_count,
                provider=provider,
                provider_attempts=selected_attempt,
            )
        )
    return generated, total_tokens


async def routed_provider_embeddings(
    *,
    model_id: str,
    inputs: list[str],
    dimensions: int,
) -> tuple[list[Any], int]:
    from apps.api_server.services.llm_api_service import LLMAPIError, ProviderAttemptRecord

    router_config = get_configured_provider_model(model_id)
    if (
        router_config is not None
        and router_config.backend == "router"
        and _router_uses_nested_router_targets(
            config=router_config,
            capability="embeddings",
        )
    ):
        return await _execute_router_embeddings(
            model_id=model_id,
            inputs=inputs,
            dimensions=dimensions,
        )
    targets = get_provider_route_targets(
        model_id=model_id,
        capability="embeddings",
    )
    if router_config is not None and router_config.backend == "router":
        max_attempts = _router_max_attempts_for_capability(
            config=router_config,
            capability="embeddings",
        )
        if max_attempts is not None:
            targets = targets[:max_attempts]
    route_timeout_seconds = (
        _provider_timeout_override_for_route(
            config=router_config,
            capability="embeddings",
        )
        if router_config is not None and router_config.backend == "router"
        else None
    )
    if not targets:
        raise LLMAPIError(
            "model_not_supported",
            f"Model '{model_id}' is not configured for provider-backed embeddings.",
            {"model": model_id, "required_capability": "embeddings"},
        )

    failures: list[dict[str, Any]] = []
    attempt_records: list[ProviderAttemptRecord] = []
    last_error: LLMAPIError | None = None
    for target in targets:
        try:
            generated, total_tokens = await provider_embeddings(
                config=target,
                inputs=inputs,
                dimensions=dimensions,
                timeout_seconds=route_timeout_seconds,
            )
            if not attempt_records:
                return generated, total_tokens
            return (
                [
                    _set_provider_attempts(
                        item,
                        _merged_provider_attempts(
                            result=item,
                            failed_attempts=tuple(attempt_records),
                            selected_backend=target.backend,
                            selected_model_id=target.model_id,
                        ),
                    )
                    for item in generated
                ],
                total_tokens,
            )
        except LLMAPIError as exc:
            last_error = exc
            failures.append(
                {
                    "target_model": target.model_id,
                    "backend": target.backend,
                    "code": exc.code,
                }
            )
            attempt_records.append(
                ProviderAttemptRecord(
                    provider_backend=target.backend,
                    provider_model_id=target.model_id,
                    outcome="failed",
                    error_code=exc.code,
                )
            )
            if exc.code not in _RETRYABLE_PROVIDER_ERROR_CODES:
                raise
            if (
                router_config is None
                or router_config.backend != "router"
                or _router_fallback_policy_for_capability(
                    config=router_config,
                    capability="embeddings",
                )
                != "retryable_only"
                or exc.code
                not in _router_fallback_on_for_capability(
                    config=router_config,
                    capability="embeddings",
                )
            ):
                raise

    assert last_error is not None
    raise LLMAPIError(
        last_error.code,
        f"All configured provider targets failed for model '{model_id}'.",
        {
            "model": model_id,
            "required_capability": "embeddings",
            "attempts": failures,
        },
    ) from last_error
