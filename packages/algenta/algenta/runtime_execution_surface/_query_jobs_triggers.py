"""resolve/query/job/webhook/trigger runtime requests.

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


from algenta.runtime_execution_surface._api_client_local import *  # noqa: F401, F403
from algenta.runtime_execution_surface._api_client_local import (
    _run_sync,
)
from algenta.runtime_execution_surface._validation import *  # noqa: F401, F403
from algenta.runtime_execution_surface._validation import (
    _validate_contract_payload,
    _build_runtime_validation_error_details,
    _validate_runtime_proof_payload,
    _validate_runtime_api_payload,
    _validate_runtime_api_mapping_payload,
    _validate_runtime_api_structured_mapping_payload,
    _validate_runtime_api_mapping_list_payload,
    _validate_runtime_api_stream,
    _validate_runtime_api_payload_list,
    _request_runtime_contract_payload,
)


def resolve_runtime_request(
    runtime: Any,
    request: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    start = runtime._perf_counter()
    merged = _runtime_intent_module().merge_runtime_request(request, kwargs)
    if runtime._uses_api_transport():
        exact = try_exact_api_resolve(runtime, merged, start)
        if exact is not None:
            return exact
        return _runtime_model_resolve_output_module().ResolveOutput.from_api(
            runtime._client().resolve(coerce_api_resolve_payload(merged))
        )
    return resolve_local_request(runtime, merged)


def query_runtime_request(runtime: Any, request: Any = None, **kwargs: Any) -> Any:
    if runtime._uses_api_transport():
        payload = coerce_api_query_payload(request, kwargs)
        return _runtime_model_query_output_module().QueryOutput.from_api(
            runtime._client().query(payload)
        )
    return query_local_request(runtime, request, kwargs)


def query_with_metadata_runtime_request(runtime: Any, request: Any = None, **kwargs: Any) -> Any:
    metadata_models = _runtime_model_query_metadata_module()
    if runtime._uses_api_transport():
        payload = coerce_api_query_payload(request, kwargs)
        return metadata_models.QueryWithMetadataOutput.from_api(
            runtime._client().query_with_metadata(payload)
        )
    query_result = query_local_request(runtime, request, kwargs)
    return metadata_models.QueryWithMetadataOutput(
        data=query_result,
        metadata=metadata_models.QueryExecutionMetadata(
            request_id=query_result.request_id,
            latency_ms=query_result.latency_ms,
        ),
        headers={},
    )


def query_batch_runtime_request(runtime: Any, request: Mapping[str, Any]) -> Any:
    runtime._require_api_transport("query_batch")
    return _runtime_model_query_metadata_module().QueryBatchOutput.from_api(
        runtime._client().query_batch(dict(request))
    )


def query_sql_report_runtime_request(runtime: Any, request: Mapping[str, Any]) -> Any:
    runtime._require_api_transport("query_sql_report")
    return _runtime_model_query_metadata_module().QuerySqlReportOutput.from_api(
        runtime._client().query_sql_report(dict(request))
    )


def submit_job_runtime_request(
    runtime: Any,
    request: Mapping[str, Any] | None = None,
    *,
    callback_url: str | None = None,
    **kwargs: Any,
) -> Any:
    runtime._require_api_transport("submit_job")
    normalized_request = dict(request) if isinstance(request, Mapping) else request
    return _validate_runtime_api_payload(
        "submit_job",
        runtime._client().submit_job(normalized_request, callback_url=callback_url, **kwargs),
        import_module("algenta.runtime_model_jobs").JobSubmitOutput,
    )


def get_job_runtime_request(runtime: Any, job_id: str) -> Any:
    runtime._require_api_transport("get_job")
    return _validate_runtime_api_payload(
        "get_job",
        runtime._client().get_job(job_id),
        import_module("algenta.runtime_model_jobs").JobStatusOutput,
    )


def get_job_result_runtime_request(runtime: Any, job_id: str) -> dict[str, Any]:
    runtime._require_api_transport("get_job_result")
    return _validate_runtime_api_mapping_payload(
        "get_job_result",
        runtime._client().get_job_result(job_id),
    )


def list_jobs_runtime_request(
    runtime: Any,
    *,
    page: int = 1,
    limit: int = 25,
    status: str | None = None,
) -> Any:
    runtime._require_api_transport("list_jobs")
    return _validate_runtime_api_payload(
        "list_jobs",
        runtime._client().list_jobs(page=page, limit=limit, status=status),
        import_module("algenta.runtime_model_jobs").JobListOutput,
    )


def cancel_job_runtime_request(runtime: Any, job_id: str) -> Any:
    runtime._require_api_transport("cancel_job")
    return _validate_runtime_api_payload(
        "cancel_job",
        runtime._client().cancel_job(job_id),
        import_module("algenta.runtime_model_jobs").JobStatusOutput,
    )


def test_webhook_delivery_runtime_request(runtime: Any, callback_url: str) -> Any:
    runtime._require_api_transport("test_webhook_delivery")
    return _validate_runtime_api_payload(
        "test_webhook_delivery",
        runtime._client().test_webhook_delivery(callback_url),
        import_module("algenta.runtime_model_jobs").WebhookTestOutput,
    )


def poll_job_runtime_request(
    runtime: Any,
    job_id: str,
    *,
    timeout: float = 300.0,
    poll_interval: float = 2.0,
) -> dict[str, Any]:
    runtime._require_api_transport("poll_job")
    return _validate_runtime_api_mapping_payload(
        "poll_job",
        runtime._client().poll_job(job_id, timeout=timeout, poll_interval=poll_interval),
    )


def register_trigger_runtime_request(
    runtime: Any,
    *,
    name: str,
    condition: Mapping[str, Any],
    simulation_template: Mapping[str, Any],
    webhook_url: str | None = None,
    execution_webhook_url: str | None = None,
    auto_execute: bool = False,
    description: str | None = None,
) -> Any:
    runtime._require_api_transport("register_trigger")
    return _validate_runtime_api_payload(
        "register_trigger",
        runtime._client().register_trigger(
            name=name,
            condition=dict(condition),
            simulation_template=dict(simulation_template),
            webhook_url=webhook_url,
            execution_webhook_url=execution_webhook_url,
            auto_execute=auto_execute,
            description=description,
        ),
        import_module("algenta.runtime_model_triggers").TriggerSummaryOutput,
    )


def list_triggers_runtime_request(
    runtime: Any,
    *,
    status: str = "all",
    page: int | None = None,
    limit: int | None = None,
) -> Any:
    runtime._require_api_transport("list_triggers")
    return _validate_runtime_api_payload(
        "list_triggers",
        runtime._client().list_triggers(status=status, page=page, limit=limit),
        import_module("algenta.runtime_model_triggers").TriggerListOutput,
    )


def fire_trigger_runtime_request(
    runtime: Any,
    trigger_id: str,
    *,
    force: bool = False,
) -> Any:
    runtime._require_api_transport("fire_trigger")
    return _validate_runtime_api_payload(
        "fire_trigger",
        runtime._client().fire_trigger(trigger_id, force=force),
        import_module("algenta.runtime_model_triggers").TriggerFireOutput,
    )


def pause_trigger_runtime_request(
    runtime: Any,
    trigger_id: str,
    *,
    paused: bool = True,
) -> Any:
    runtime._require_api_transport("pause_trigger")
    return _validate_runtime_api_payload(
        "pause_trigger",
        runtime._client().pause_trigger(trigger_id, paused=paused),
        import_module("algenta.runtime_model_triggers").TriggerPauseOutput,
    )


def delete_trigger_runtime_request(runtime: Any, trigger_id: str) -> Any:
    runtime._require_api_transport("delete_trigger")
    payload = runtime._client().delete_trigger(trigger_id)
    normalized_payload = coerce_payload_mapping(payload)
    return _validate_runtime_api_payload(
        "delete_trigger",
        {"trigger_id": trigger_id, "deleted": True, **normalized_payload},
        import_module("algenta.runtime_model_triggers").TriggerDeleteOutput,
    )


