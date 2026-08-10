"""All _parse_* / _validate_* functions for provider config + router targets.

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
        "algenta_local",
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
    "algenta_local": frozenset({"chat_completions"}),
}
_ANTHROPIC_API_VERSION = "2023-06-01"
_OPTIONAL_PROVIDER_API_KEY_BACKENDS = frozenset({"ollama", "algenta_local"})
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

