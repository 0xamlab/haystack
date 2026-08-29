"""Nested-router check + _execute_router_chat_completion.

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
from apps.api_server.services.llm_provider_service._route_resolution import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._route_resolution import (
    _set_provider_attempts,
    _provider_attempt_records_from_error,
    _provider_failure_details_from_error,
    _merged_provider_attempts,
    _resolve_provider_route_targets_from_map,
    _resolve_provider_reachable_route_targets_via_resolver,
    _resolve_provider_reachable_route_targets_from_map,
    _router_all_declared_target_model_ids,
    _resolve_provider_leaf_targets_from_map,
)
from apps.api_server.services.llm_provider_service._loader import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._http_layer import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._http_layer import (
    _provider_auth_headers,
    _provider_post_json,
    _router_declared_target_model_ids_for_capability,
    _router_attempt_target_model_ids_for_capability,
    _router_reachable_target_model_ids_for_capability,
)


def _router_uses_nested_router_targets(
    *,
    config: ProviderModelConfig,
    capability: str,
) -> bool:
    from apps.api_server.services import llm_provider_service as _facade_module
    for target_model_id in _router_reachable_target_model_ids_for_capability(
        config=config,
        capability=capability,
        resolve_config=_facade_module.get_configured_provider_model,
    ):
        target_config = _facade_module.get_configured_provider_model(target_model_id)
        if target_config is not None and target_config.backend == "router":
            return True
    return False


async def _execute_router_chat_completion(
    *,
    model_id: str,
    messages: list[dict[str, str]],
    timeout_seconds: float | None = None,
    seen: tuple[str, ...] = (),
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any | None = None,
    parallel_tool_calls: bool | None = None,
) -> Any:
    from apps.api_server.services import llm_provider_service as _facade_module
    from apps.api_server.services.llm_api_service import LLMAPIError, ProviderAttemptRecord

    # Forward tool-calling params only when the caller actually set them, so existing
    # callers/stubs (including test doubles with a fixed signature) that never mention tools
    # are unaffected.
    _tool_kwargs: dict[str, Any] = {}
    if tools:
        _tool_kwargs["tools"] = tools
    if tool_choice is not None:
        _tool_kwargs["tool_choice"] = tool_choice
    if parallel_tool_calls is not None:
        _tool_kwargs["parallel_tool_calls"] = parallel_tool_calls

    if model_id in seen:
        cycle = " -> ".join((*seen, model_id))
        raise LLMAPIError(
            "backend_unavailable",
            f"Provider router cycle detected: {cycle}.",
            {"model": model_id, "cycle": cycle},
        )

    config = _facade_module.get_configured_provider_model(model_id)
    if config is None or "chat_completions" not in config.capabilities:
        raise LLMAPIError(
            "model_not_supported",
            f"Model '{model_id}' is not configured for provider-backed chat completions.",
            {"model": model_id, "required_capability": "chat_completions"},
        )
    if config.backend != "router":
        return await _facade_module.provider_chat_completion(
            config=config,
            messages=messages,
            timeout_seconds=timeout_seconds,
            **_tool_kwargs,
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
        resolve_config=_facade_module.get_configured_provider_model,
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
        target_config = _facade_module.get_configured_provider_model(target_model_id)
        target_backend = target_config.backend if target_config is not None else "router"
        try:
            result = await _execute_router_chat_completion(
                model_id=target_model_id,
                messages=messages,
                timeout_seconds=effective_timeout_seconds,
                seen=(*seen, model_id),
                **_tool_kwargs,
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


