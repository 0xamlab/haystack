"""_provider_auth_headers + _provider_post_json + getters + target-ID helpers.

Extracted from apps/api_server/services/llm_provider_service.py during modularization.
"""
from __future__ import annotations

import json
import os
import re
from collections.abc import AsyncIterator
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
        # B10: resolve the LLM provider key through the per-tenant seam — a per-request org override
        # wins; single-tenant (default) uses the env key (unchanged). When a per-tenant key is
        # REQUIRED (multi-tenant) and none is configured for this request, FAIL CLOSED here — never
        # fall back to the shared env key. Single-tenant + env-unset delegates to the existing
        # env-required error (preserving its message/contract).
        from apps.api_server.services.tenant_keys import (
            require_per_tenant_keys,
            resolve_provider_api_key,
        )

        api_key = resolve_provider_api_key(config.api_key_env, config.backend)
        if not api_key:
            if require_per_tenant_keys():
                raise LLMAPIError(
                    "backend_unavailable",
                    (
                        f"Provider-backed model '{config.model_id}' requires a per-tenant API key, "
                        "which is not configured for this request."
                    ),
                    {"model": config.model_id, "api_key_env": config.api_key_env},
                )
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


def _raise_for_provider_error_status(
    *,
    config: ProviderModelConfig,
    status_code: int,
    detail: Any,
) -> None:
    """Shared HTTP-status -> typed LLMAPIError mapping for both the buffered (_provider_post_json)
    and streaming (_provider_post_json_stream) provider call paths -- kept as one function so the
    two paths can never silently drift apart on what counts as retryable vs terminal."""
    from apps.api_server.services.llm_api_service import LLMAPIError

    if status_code == 429:
        raise LLMAPIError(
            "provider_rate_limited",
            f"Provider backend rate limited model '{config.model_id}'.",
            {"model": config.model_id, "status_code": status_code, "response": detail},
        )
    if status_code in {401, 403}:
        raise LLMAPIError(
            "provider_authentication_failed",
            f"Provider backend rejected credentials for model '{config.model_id}'.",
            {"model": config.model_id, "status_code": status_code, "response": detail},
        )
    if 400 <= status_code < 500:
        raise LLMAPIError(
            "invalid_provider_request",
            f"Provider backend rejected the request for model '{config.model_id}'.",
            {"model": config.model_id, "status_code": status_code, "response": detail},
        )
    raise LLMAPIError(
        "provider_backend_error",
        f"Provider backend returned HTTP {status_code} for model '{config.model_id}'.",
        {"model": config.model_id, "status_code": status_code, "response": detail},
    )


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
        _raise_for_provider_error_status(
            config=config, status_code=response.status_code, detail=detail
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


# Track C2 (real per-backend streaming, 2026-08): backends with a real SSE normalizer in
# _streaming.py -- re-exported here from the single source of truth (llm_provider_service._features)
# so _provider_post_json_stream's normalizer choice can never silently drift from what
# GET /v1/models (and the router's streaming-mode gate) advertise as "passthrough".
from apps.api_server.services.llm_provider_service._features import (
    PASSTHROUGH_STREAMING_BACKENDS as _STREAM_NORMALIZED_BACKENDS,
)


async def _provider_post_json_stream(
    *,
    config: ProviderModelConfig,
    path: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> AsyncIterator[dict[str, Any]]:
    """Streaming counterpart to _provider_post_json: the SAME egress gate + typed HTTP-status
    error mapping, but opens the connection via egress_guard.async_http_stream and yields
    normalized per-backend stream-event dicts (see _streaming.py) as the upstream produces them --
    never buffers the full response body. Only meaningful for config.backend in
    _STREAM_NORMALIZED_BACKENDS; the caller (provider_chat_completion_stream) is responsible for
    only invoking this for a passthrough-capable backend -- enforced defensively below too, so a
    future caller mistake fails loudly instead of silently parsing a non-openai-shaped,
    non-anthropic body with the wrong normalizer."""
    from apps.api_server.services import egress_guard
    from apps.api_server.services.egress_guard import EgressPolicyDeniedError
    from apps.api_server.services.llm_api_service import LLMAPIError
    from apps.api_server.services.llm_provider_service._streaming import (
        parse_anthropic_stream,
        parse_openai_shaped_stream,
    )

    assert config.backend in _STREAM_NORMALIZED_BACKENDS, (
        f"_provider_post_json_stream called for non-passthrough backend '{config.backend}'"
    )
    try:
        async with egress_guard.async_http_stream(
            method="POST",
            url=f"{config.base_url}{path}",
            surface="llm_provider_post_stream",
            egress_class="customer_connector",
            explicit_configured=True,
            headers=_provider_auth_headers(config),
            json=payload,
            client_kwargs={"timeout": timeout_seconds},
        ) as response:
            if response.status_code >= 400:
                body = await response.aread()
                detail: Any
                try:
                    detail = json.loads(body.decode("utf-8", errors="replace"))
                except (TypeError, ValueError):
                    detail = body.decode("utf-8", errors="replace")
                _raise_for_provider_error_status(
                    config=config, status_code=response.status_code, detail=detail
                )
            normalizer = (
                parse_anthropic_stream
                if config.backend == "anthropic"
                else parse_openai_shaped_stream
            )
            async for event in normalizer(response.aiter_lines()):
                yield event
    except EgressPolicyDeniedError as exc:
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


async def _provider_get_json(
    *,
    config: ProviderModelConfig,
    path: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    """GET a provider endpoint through the egress guard (used by model discovery). Mirrors
    _provider_post_json's egress routing + typed error handling; no request body. The (customer-configured)
    provider base_url still goes through the fail-closed/SSRF policy — deny raises before any socket opens."""
    from apps.api_server.services import egress_guard
    from apps.api_server.services.egress_guard import EgressPolicyDeniedError
    from apps.api_server.services.llm_api_service import LLMAPIError

    try:
        response = await egress_guard.async_http_request(
            method="GET",
            url=f"{config.base_url}{path}",
            surface="llm_provider_discover",
            egress_class="customer_connector",
            explicit_configured=True,
            headers=_provider_auth_headers(config),
            client_kwargs={"timeout": timeout_seconds},
        )
    except EgressPolicyDeniedError as exc:
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
            raise LLMAPIError("provider_rate_limited",
                              f"Provider backend rate limited discovery for '{config.model_id}'.",
                              {"model": config.model_id, "status_code": response.status_code, "response": detail})
        if response.status_code in {401, 403}:
            raise LLMAPIError("provider_authentication_failed",
                              f"Provider backend rejected credentials for '{config.model_id}'.",
                              {"model": config.model_id, "status_code": response.status_code, "response": detail})
        if 400 <= response.status_code < 500:
            raise LLMAPIError("invalid_provider_request",
                              f"Provider backend rejected the discovery request for '{config.model_id}'.",
                              {"model": config.model_id, "status_code": response.status_code, "response": detail})
        raise LLMAPIError("provider_backend_error",
                          f"Provider backend returned HTTP {response.status_code} for '{config.model_id}'.",
                          {"model": config.model_id, "status_code": response.status_code, "response": detail})

    try:
        data = response.json()
    except ValueError as exc:
        raise LLMAPIError("invalid_provider_response",
                          f"Provider backend returned invalid JSON for '{config.model_id}'.",
                          {"model": config.model_id, "backend": config.backend}) from exc
    if not isinstance(data, dict):
        raise LLMAPIError("invalid_provider_response",
                          f"Provider backend returned an invalid discovery payload for '{config.model_id}'.",
                          {"model": config.model_id, "backend": config.backend})
    return data


def get_configured_provider_model(model_id: str) -> ProviderModelConfig | None:
    from apps.api_server.services import llm_provider_service as _facade_module
    from apps.api_server.services.llm_provider_service._discovery import (
        is_discovery_entry,
        resolve_discovered_model,
    )

    for config in _facade_module.load_provider_model_configs():
        if config.model_id == model_id:
            # A discovery entry (model_name "*") is not itself a callable model — only its discovered
            # <entry-id>:<model> children are — so fall through to discovery resolution below.
            if is_discovery_entry(config):
                break
            return config
    # Dynamic discovery: a `<entry-id>:<model>` id routes to the entry's backend with that upstream model.
    return resolve_discovered_model(model_id)


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


