"""Public provider_chat_completion + routed_provider_chat_completion.

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
from apps.api_server.services.llm_provider_service._executors_chat import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._executors_chat import (
    _router_uses_nested_router_targets,
    _execute_router_chat_completion,
)
from apps.api_server.services.llm_provider_service._executors_embeddings import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._executors_embeddings import (
    _execute_router_embeddings,
)


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
    from apps.api_server.services import llm_provider_service as _facade_module
    from apps.api_server.services.llm_api_service import LLMAPIError, ProviderAttemptRecord

    router_config = _facade_module.get_configured_provider_model(model_id)
    if (
        router_config is not None
        and router_config.backend == "router"
        and _router_uses_nested_router_targets(
            config=router_config,
            capability="chat_completions",
        )
    ):
        return await _facade_module._execute_router_chat_completion(
            model_id=model_id,
            messages=messages,
        )
    targets = _facade_module.get_provider_route_targets(
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
            result = await _facade_module.provider_chat_completion(
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


