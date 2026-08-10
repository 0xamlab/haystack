"""load_provider_model_configs — the @lru_cache config loader.

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

        if backend == "algenta_local":
            # The local GPU engine is not an HTTP provider: no base_url, no api_key. The entry's
            # model_name is the key into ALGENTA_LOCAL_LLM_MODELS_JSON (model name -> checkpoint
            # directory); routing/failover fields do not apply and stay at their defaults.
            description = str(item.get("description") or "").strip()
            if not description:
                description = (
                    "Local Apple-Silicon GPU inference through the Algenta engine "
                    "(Qwen3-family checkpoints, greedy or seeded sampling)."
                )
            configs.append(
                ProviderModelConfig(
                    model_id=model_id,
                    backend=backend,
                    base_url="",
                    upstream_model=_resolve_upstream_model(item, context, model_id),
                    api_key_env=None,
                    description=description,
                    capabilities=capabilities,
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


