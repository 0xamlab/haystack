"""runtime_api_client + remember/forget/try_exact_api_resolve + local execution paths.

Extracted from packages/algenta/algenta/runtime_execution_surface.py during modularization.
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from importlib import import_module
from typing import TYPE_CHECKING, Any

from algenta.runtime_errors import RuntimeConfigurationError, RuntimeValidationError
from algenta.runtime_model_common import coerce_payload_mapping

if TYPE_CHECKING:
    from types import ModuleType


@cache
def _runtime_api_exact_module() -> ModuleType:
    return import_module("algenta.runtime_api_exact")


@cache
def _runtime_api_payloads_module() -> ModuleType:
    return import_module("algenta.runtime_api_payloads")


@cache
def _runtime_intent_module() -> ModuleType:
    return import_module("algenta.runtime_intent")


@cache
def _runtime_local_limits_module() -> ModuleType:
    return import_module("algenta.runtime_local_limits")


@cache
def _runtime_local_query_module() -> ModuleType:
    return import_module("algenta.runtime_local_query")


@cache
def _runtime_local_resolve_module() -> ModuleType:
    return import_module("algenta.runtime_local_resolve")


@cache
def _runtime_model_query_output_module() -> ModuleType:
    return import_module("algenta.runtime_model_query_output")


@cache
def _runtime_model_query_metadata_module() -> ModuleType:
    return import_module("algenta.runtime_model_query_metadata")


@cache
def _runtime_model_resolve_output_module() -> ModuleType:
    return import_module("algenta.runtime_model_resolve_output")


@cache
def _runtime_model_verify_output_module() -> ModuleType:
    return import_module("algenta.runtime_model_verify_output")


@cache
def _runtime_model_decision_plan_module() -> ModuleType:
    return import_module("algenta.runtime_model_decision_plan")


@cache
def _runtime_model_decision_envelope_module() -> ModuleType:
    return import_module("algenta.runtime_model_decision_envelope")


@cache
def _runtime_model_decision_memory_module() -> ModuleType:
    return import_module("algenta.runtime_model_decision_memory")


@cache
def _runtime_model_repository_intelligence_module() -> ModuleType:
    return import_module("algenta.runtime_model_repository_intelligence")


@cache
def _runtime_model_products_module() -> ModuleType:
    return import_module("algenta.runtime_model_products")


@cache
def _runtime_model_llm_module() -> ModuleType:
    return import_module("algenta.runtime_model_llm")


@cache
def _runtime_model_agent_runs_module() -> ModuleType:
    return import_module("algenta.runtime_model_agent_runs")


@cache
def _runtime_model_account_module() -> ModuleType:
    return import_module("algenta.runtime_model_account")


@cache
def _runtime_model_deployments_module() -> ModuleType:
    return import_module("algenta.runtime_model_deployments")


@cache
def _runtime_model_control_plane_module() -> ModuleType:
    return import_module("algenta.runtime_model_control_plane")




def runtime_api_client(runtime: Any) -> Any:
    if runtime._api_client is not None:
        return runtime._api_client
    if not runtime._api_key:
        raise RuntimeConfigurationError(
            "api_key_required",
            (
                "API-backed runtime modes require an API key. "
                "Set ALGENTA_API_KEY / DE_API_KEY or pass api_key=..."
            ),
        )
    try:
        from decision_engine import DecisionEngineClient
    except ImportError as exc:  # pragma: no cover - exercised via tests
        raise RuntimeConfigurationError(
            "api_sdk_missing",
            (
                "API-backed runtime modes require the algenta-sdk package. "
                "Install algenta-sdk or algenta[cloud]."
            ),
        ) from exc
    runtime._api_client = DecisionEngineClient(
        api_key=runtime._api_key,
        base_url=runtime._base_url,
        max_retries=0,
    )
    return runtime._api_client


def remember_api_registration(runtime: Any, registration: Any) -> None:
    source_key = registration.dataset_id or registration.source_id
    if isinstance(source_key, str) and source_key.strip():
        runtime._api_source_schema_revision_cache.pop(source_key, None)
    _runtime_api_exact_module().remember_api_registration(
        runtime._api_registrations_by_name,
        runtime._api_registrations_by_dataset,
        registration,
    )


def forget_api_registration(runtime: Any, dataset_id: str) -> None:
    _runtime_api_exact_module().forget_api_registration(
        runtime._api_registrations_by_name,
        runtime._api_registrations_by_dataset,
        runtime._api_source_schema_revision_cache,
        dataset_id,
    )


def try_exact_api_resolve(runtime: Any, request: Mapping[str, Any], start: float) -> Any | None:
    intent = _runtime_intent_module()
    return _runtime_api_exact_module().try_exact_api_resolve(
        request,
        registrations_by_name=runtime._api_registrations_by_name,
        registrations_by_dataset=runtime._api_registrations_by_dataset,
        source_schema_revision_cache=runtime._api_source_schema_revision_cache,
        client_factory=runtime._client,
        resolve_aggregation=intent.resolve_aggregation,
        intent_signature=intent.intent_signature,
        plan_hash=intent.plan_hash,
        started_at=start,
    )


def coerce_api_resolve_payload(request: Mapping[str, Any]) -> dict[str, Any]:
    return _runtime_api_payloads_module().coerce_api_resolve_payload(request)


def ensure_local_execution_entitlement(runtime: Any) -> None:
    runtime._local_license = _runtime_local_limits_module().ensure_local_execution_entitlement(
        enabled=runtime._uses_hosted_local_limits(),
        api_key=runtime._api_key,
        current_license=runtime._local_license,
    )


def consume_local_credit(runtime: Any) -> None:
    _runtime_local_limits_module().consume_local_credit(
        enabled=runtime._uses_hosted_local_limits(),
        run_sync=_run_sync,
    )


def resolve_local_request(runtime: Any, request: Mapping[str, Any]) -> Any:
    intent = _runtime_intent_module()
    return _runtime_local_resolve_module().resolve_local_request(
        runtime._local_sources,
        request,
        started_at=runtime._perf_counter(),
        resolve_aggregation=intent.resolve_aggregation,
        intent_signature=intent.intent_signature,
        plan_hash=intent.plan_hash,
    )


def coerce_plan(request: Any, kwargs: Mapping[str, Any]) -> Any:
    return _runtime_api_payloads_module().coerce_plan(request, kwargs)


def query_local_request(runtime: Any, request: Any, kwargs: Mapping[str, Any]) -> Any:
    return _runtime_local_query_module().query_local_request(
        runtime._local_sources,
        request,
        kwargs,
        coerce_plan=coerce_plan,
        ensure_local_execution_entitlement=lambda: ensure_local_execution_entitlement(runtime),
        consume_local_credit=lambda: consume_local_credit(runtime),
        plan_hash=_runtime_intent_module().plan_hash,
    )


def verify_local_request(runtime: Any, request: Any, kwargs: Mapping[str, Any]) -> Any:
    return _runtime_local_query_module().verify_local_request(
        runtime._local_sources,
        request,
        kwargs,
        coerce_plan=coerce_plan,
        plan_hash=_runtime_intent_module().plan_hash,
    )


def coerce_api_query_payload(request: Any, kwargs: Mapping[str, Any]) -> dict[str, Any]:
    return _runtime_api_payloads_module().coerce_api_query_payload(request, kwargs)


def _run_sync(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def _run_in_thread() -> Any:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run_in_thread).result()
