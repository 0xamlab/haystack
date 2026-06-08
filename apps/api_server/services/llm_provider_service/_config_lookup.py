"""Provider config map + per-capability lookups + header/auth helpers.

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
from apps.api_server.services.llm_provider_service._response_parsing import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._response_parsing import (
    _parse_provider_chat_completion,
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
    from apps.api_server.services import llm_provider_service as _facade_module
    config = _facade_module.get_configured_provider_model(model_id)
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
        for target in _facade_module.get_provider_route_targets(
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
    from apps.api_server.services import llm_provider_service as _facade_module
    config = _facade_module.get_configured_provider_model(model_id)
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
        for target in _facade_module.get_provider_route_targets(
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

