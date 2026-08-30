"""Public provider_chat_completion + routed_provider_chat_completion.

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
from apps.api_server.services.llm_provider_service._http_layer import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._http_layer import (
    _provider_auth_headers,
    _provider_post_json,
    _provider_post_json_stream,
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
    max_output_tokens: int | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any | None = None,
    parallel_tool_calls: bool | None = None,
) -> Any:
    # D3 managed-LLM (no-op unless this call resolves to the platform's pooled key): fail closed
    # before the call if the org is over its monthly managed spend cap, then meter the cost after.
    from apps.api_server.services import llm_spend_service

    await llm_spend_service.gate_managed_llm_call(
        backend=config.backend, api_key_env=config.api_key_env
    )
    data = await _provider_post_json(
        config=config,
        path=_provider_chat_path(config),
        payload=_provider_chat_payload(
            config=config,
            messages=messages,
            max_output_tokens=max_output_tokens,
            tools=tools,
            tool_choice=tool_choice,
            parallel_tool_calls=parallel_tool_calls,
        ),
        timeout_seconds=(
            timeout_seconds
            if timeout_seconds is not None
            else _provider_timeout_seconds_for_capability(
                config=config,
                capability="chat_completions",
            )
        ),
    )
    result = _parse_provider_chat_completion(config=config, data=data)
    await llm_spend_service.meter_managed_llm_call(
        backend=config.backend,
        api_key_env=config.api_key_env,
        model=config.model_id,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        cache_read_tokens=result.cache_read_tokens,
        cache_write_tokens=result.cache_write_tokens,
    )
    return result


# Track C2 (real per-backend streaming, 2026-08): openai-shaped backends additionally get
# `stream_options: {"include_usage": true}` on the request so the provider sends one extra
# terminal chunk (empty `choices`, populated `usage`) we can meter from -- anthropic always
# includes usage on message_start/message_delta with no extra request flag needed.
_OPENAI_SHAPED_STREAM_BACKENDS = frozenset(
    {"openai", "openai_compatible", "groq", "xai", "mistral"}
)


async def provider_chat_completion_stream(
    *,
    config: ProviderModelConfig,
    messages: list[dict[str, str]],
    timeout_seconds: float | None = None,
    max_output_tokens: int | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Real per-backend streaming counterpart to provider_chat_completion, for backends in
    _STREAM_NORMALIZED_BACKENDS only (the caller is responsible for that check). Yields
    normalized internal stream-event dicts (see _streaming.py) as the upstream generates them --
    never buffers the full body.

    Tool calling is intentionally not threaded through this path yet (the router only calls this
    when the request carries no `tools`); the normalizers already parse tool-call deltas
    correctly (unit-tested in test_llm_provider_service_streaming_normalizers.py), so wiring that
    in later is a router-level change, not a normalizer one.

    Usage metering fires from a `finally` block using whatever usage the terminal upstream event
    carried (0s if the provider never sent one) -- reusing the SAME llm_spend_service calls the
    non-streaming path uses, just relocated to fire at stream end. A `finally` block on a
    generator also runs on early client disconnect (Starlette closes the generator, raising
    GeneratorExit at the suspended `yield`), so a dropped connection still meters the real tokens
    generated so far instead of silently losing them.
    """
    from apps.api_server.services import llm_spend_service

    await llm_spend_service.gate_managed_llm_call(
        backend=config.backend, api_key_env=config.api_key_env
    )
    payload = _provider_chat_payload(
        config=config,
        messages=messages,
        max_output_tokens=max_output_tokens,
    )
    payload["stream"] = True
    if config.backend in _OPENAI_SHAPED_STREAM_BACKENDS:
        payload["stream_options"] = {"include_usage": True}

    usage_totals = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
    }
    try:
        async for event in _provider_post_json_stream(
            config=config,
            path=_provider_chat_path(config),
            payload=payload,
            timeout_seconds=(
                timeout_seconds
                if timeout_seconds is not None
                else _provider_timeout_seconds_for_capability(
                    config=config,
                    capability="chat_completions",
                )
            ),
        ):
            usage = event.get("usage")
            if usage:
                usage_totals.update(usage)
            yield event
    finally:
        await llm_spend_service.meter_managed_llm_call(
            backend=config.backend,
            api_key_env=config.api_key_env,
            model=config.model_id,
            prompt_tokens=usage_totals["prompt_tokens"],
            completion_tokens=usage_totals["completion_tokens"],
            cache_read_tokens=usage_totals["cache_read_tokens"],
            cache_write_tokens=usage_totals["cache_write_tokens"],
        )


async def routed_provider_chat_completion_stream(
    *,
    model_id: str,
    messages: list[dict[str, str]],
    max_output_tokens: int | None = None,
) -> tuple[ProviderModelConfig, AsyncIterator[dict[str, Any]]]:
    """Streaming counterpart to routed_provider_chat_completion, for a passthrough-capable target
    only (the caller checks llm_provider_service._features.resolved_streaming_mode_for_model
    first). Resolves the SAME ordered, fully-flattened (including through a nested router)
    reachable-target list the non-streaming router would, via get_provider_route_targets -- but
    only ever ATTEMPTS the first one.

    This is a deliberate v1 simplification, not an oversight: a buffered non-streaming call can
    retry a failed target with no visible side effect, but a real streaming call may already have
    written several chunks to the client before a later failure -- silently falling back to a
    second target at that point would either resend already-streamed content or splice two
    providers' output together inside one SSE response, which is worse than surfacing the
    failure. A failure that happens BEFORE any network I/O (bad config, missing auth) still
    raises here, before the caller ever opens the SSE response, so it still surfaces as a normal
    JSON error with the right HTTP status -- only a genuine mid-stream network failure ends the
    SSE response early instead of retrying.

    Returns the concrete target config (for the caller to report provider_backend/
    provider_model_id/provider_attempts) alongside the event stream.
    """
    from apps.api_server.services import llm_provider_service as _facade_module
    from apps.api_server.services.llm_api_service import LLMAPIError

    targets = _facade_module.get_provider_route_targets(
        model_id=model_id, capability="chat_completions"
    )
    if not targets:
        raise LLMAPIError(
            "model_not_supported",
            f"Model '{model_id}' is not configured for provider-backed chat completions.",
            {"model": model_id, "required_capability": "chat_completions"},
        )
    target = targets[0]

    route_timeout_seconds = None
    router_config = _facade_module.get_configured_provider_model(model_id)
    if router_config is not None and router_config.backend == "router":
        route_timeout_seconds = _provider_timeout_override_for_route(
            config=router_config,
            capability="chat_completions",
        )

    _output_budget = (
        {} if max_output_tokens is None else {"max_output_tokens": max_output_tokens}
    )
    stream = _facade_module.provider_chat_completion_stream(
        config=target,
        messages=messages,
        timeout_seconds=route_timeout_seconds,
        **_output_budget,
    )
    return target, stream


async def routed_provider_chat_completion(
    *,
    model_id: str,
    messages: list[dict[str, str]],
    max_output_tokens: int | None = None,
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
            **_tool_kwargs,
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
            # Forward the output budget only when the caller set one, so existing
            # callers/stubs that don't expect the kwarg are unaffected (None == 512).
            _output_budget = (
                {} if max_output_tokens is None else {"max_output_tokens": max_output_tokens}
            )
            result = await _facade_module.provider_chat_completion(
                config=target,
                messages=messages,
                timeout_seconds=route_timeout_seconds,
                **_output_budget,
                **_tool_kwargs,
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


