"""_provider_auth_headers + _provider_post_json + getters + target-ID helpers.

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
    from apps.api_server.services import egress_guard
    from apps.api_server.services.egress_guard import EgressPolicyDeniedError
    from apps.api_server.services.llm_api_service import LLMAPIError

    # B10: every LLM provider call is the SOLE outbound for chat + embeddings; route it through the
    # egress guard so the self_hosted/air_gapped fail-closed policy + SSRF check apply to the
    # (customer-configured) provider base_url. Deny raises before any socket opens. Transport only —
    # the auth header still reads the global env key here; per-tenant key resolution is a follow-up.
    try:
        response = await egress_guard.async_http_request(
            method="POST",
            url=f"{config.base_url}{path}",
            surface="llm_provider_post",
            egress_class="customer_connector",
            explicit_configured=True,
            headers=_provider_auth_headers(config),
            json=payload,
            client_kwargs={"timeout": timeout_seconds},
        )
    except EgressPolicyDeniedError as exc:
        # Caught before the broad httpx.HTTPError below (it is a RuntimeError, not an httpx error):
        # a policy denial must surface as a typed failure, never a silent retry to an alternate host.
        raise LLMAPIError(
            "egress_denied",
            f"Provider egress denied by privacy policy for model '{config.model_id}'.",
            {"model": config.model_id, "backend": config.backend},
        ) from exc
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
    from apps.api_server.services import llm_provider_service as _facade_module
    for config in _facade_module.load_provider_model_configs():
        if config.model_id == model_id:
            return config
    return None


def get_provider_route_targets(
    *,
    model_id: str,
    capability: str,
) -> tuple[ProviderModelConfig, ...]:
    from apps.api_server.services import llm_provider_service as _facade_module
    config_by_id = _provider_config_map(_facade_module.load_provider_model_configs())
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


