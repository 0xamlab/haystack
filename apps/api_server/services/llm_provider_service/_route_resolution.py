"""Auth-configured checks + resolved/reachable route targets + leaf resolver.

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
from apps.api_server.services.llm_provider_service._config_lookup import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._config_lookup import (
    _provider_config_map,
    _router_targets_for_capability,
    _router_fallback_policy_for_capability,
    _router_fallback_on_for_capability,
    _router_max_attempts_for_capability,
    _provider_timeout_seconds_for_capability,
    _provider_timeout_override_for_route,
    _provider_capabilities_for_query,
    _get_provider_required_header_names,
    _get_provider_required_auth_env_vars,
)


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
    from apps.api_server.services import llm_provider_service as _facade_module
    config = _facade_module.get_configured_provider_model(model_id)
    if config is None or config.backend != "router":
        return ()
    resolved: list[str] = []
    for capability in _SUPPORTED_PROVIDER_CAPABILITY_ORDER:
        if capability not in config.capabilities:
            continue
        for target in _facade_module.get_provider_route_targets(model_id=model_id, capability=capability):
            if target.model_id in resolved:
                continue
            resolved.append(target.model_id)
    return tuple(resolved)


def get_provider_resolved_chat_route_targets(
    *,
    model_id: str,
) -> tuple[str, ...]:
    from apps.api_server.services import llm_provider_service as _facade_module
    config = _facade_module.get_configured_provider_model(model_id)
    if config is None or config.backend != "router":
        return ()
    return tuple(
        target.model_id
        for target in _facade_module.get_provider_route_targets(
            model_id=model_id,
            capability="chat_completions",
        )
    )


def get_provider_resolved_embedding_route_targets(
    *,
    model_id: str,
) -> tuple[str, ...]:
    from apps.api_server.services import llm_provider_service as _facade_module
    config = _facade_module.get_configured_provider_model(model_id)
    if config is None or config.backend != "router":
        return ()
    return tuple(
        target.model_id
        for target in _facade_module.get_provider_route_targets(
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

    from apps.api_server.services.llm_provider_service._http_layer import (
        _router_reachable_target_model_ids_for_capability,
    )
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


