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


def contract_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("get_contract")
    runtime_model_contract = import_module("algenta.runtime_model_contract")
    payload = _request_runtime_contract_payload(
        runtime,
        client_method_name="get_contract",
        runtime_error_code="invalid_contract_payload",
        message="get_contract() returned an invalid payload.",
        upstream_error_codes=("invalid_contract_payload", "contract_extension_missing"),
    )
    return _validate_contract_payload(
        "get_contract",
        payload,
        runtime_model_contract.PlatformContractOutput,
    )


def _validate_contract_payload(
    method_name: str,
    payload: Any,
    parser: Any,
) -> Any:
    try:
        return parser.from_api(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeValidationError(
            "invalid_contract_payload",
            f"{method_name}() returned an invalid payload.",
            _build_runtime_validation_error_details(exc),
        ) from exc


_RUNTIME_VALIDATION_ERROR_PREFIX = re.compile(
    r"^(?P<path>[A-Za-z0-9_.\[\]-]+)(?::|\s)(?P<message>.+)$"
)


def _build_runtime_validation_error_details(exc: Exception) -> dict[str, Any]:
    message = str(exc)
    match = _RUNTIME_VALIDATION_ERROR_PREFIX.match(message)
    if not match:
        return {"cause": message}
    path = match.group("path")
    detail = match.group("message").strip()
    if not path or not detail:
        return {"cause": message}
    return {
        "cause": path,
        "validation_errors": [
            {
                "path": path,
                "message": detail,
                "type": "value_error",
            }
        ],
    }


def _validate_runtime_proof_payload(
    method_name: str,
    payload: Any,
    parser: Any,
) -> Any:
    try:
        return parser.from_api(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeValidationError(
            "invalid_runtime_contract_payload",
            f"{method_name}() returned an invalid signed payload.",
            _build_runtime_validation_error_details(exc),
        ) from exc


def _validate_runtime_api_payload(
    method_name: str,
    payload: Any,
    parser: Any,
) -> Any:
    try:
        return parser.from_api(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeValidationError(
            "invalid_runtime_api_payload",
            f"{method_name}() returned an invalid payload.",
            _build_runtime_validation_error_details(exc),
        ) from exc


def _validate_runtime_api_mapping_payload(method_name: str, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise RuntimeValidationError(
            "invalid_runtime_api_payload",
            f"{method_name}() returned an invalid payload.",
            {"cause": "payload", "expected_type": "mapping", "actual_type": type(payload).__name__},
        )
    return dict(payload)


def _validate_runtime_api_structured_mapping_payload(
    method_name: str,
    payload: Any,
    parser: Any,
) -> dict[str, Any]:
    validated = _validate_runtime_api_payload(method_name, payload, parser)
    to_dict = getattr(validated, "to_dict", None)
    if callable(to_dict):
        normalized = to_dict()
        if isinstance(normalized, Mapping):
            return dict(normalized)
    if isinstance(validated, Mapping):
        return dict(validated)
    raise RuntimeValidationError(
        "invalid_runtime_api_payload",
        f"{method_name}() returned an invalid payload.",
        {"cause": "payload", "expected_type": "mapping", "actual_type": type(validated).__name__},
    )


def _validate_runtime_api_mapping_list_payload(
    method_name: str,
    payload: Any,
) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise RuntimeValidationError(
            "invalid_runtime_api_payload",
            f"{method_name}() returned an invalid payload.",
            {"cause": "payload", "expected_type": "list", "actual_type": type(payload).__name__},
        )
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise RuntimeValidationError(
                "invalid_runtime_api_payload",
                f"{method_name}() returned an invalid payload.",
                {
                    "cause": f"payload[{index}]",
                    "expected_type": "mapping",
                    "actual_type": type(item).__name__,
                },
            )
        normalized.append(dict(item))
    return normalized


def _validate_runtime_api_stream(
    method_name: str,
    payloads: Any,
    parser: Any,
) -> Any:
    for payload in payloads:
        yield _validate_runtime_api_payload(method_name, payload, parser)


def _validate_runtime_api_payload_list(
    method_name: str,
    payload: Any,
    parser: Any,
) -> list[Any]:
    raw_items = payload
    if isinstance(payload, Mapping):
        raw_items = payload.get("api_keys", payload)
    if not isinstance(raw_items, list):
        raise RuntimeValidationError(
            "invalid_runtime_api_payload",
            f"{method_name}() returned an invalid payload.",
            {"cause": "payload", "expected_type": "list", "actual_type": type(raw_items).__name__},
        )
    return [_validate_runtime_api_payload(method_name, item, parser) for item in raw_items]


def _request_runtime_contract_payload(
    runtime: Any,
    *,
    client_method_name: str,
    runtime_error_code: str,
    message: str,
    upstream_error_codes: tuple[str, ...],
) -> Any:
    try:
        return getattr(runtime._client(), client_method_name)()
    except Exception as exc:
        upstream_error_code = getattr(exc, "error_code", None)
        if upstream_error_code not in upstream_error_codes:
            raise
        details = {
            "cause": str(exc),
            "source_error_code": upstream_error_code,
        }
        upstream_status_code = getattr(exc, "status_code", None)
        if isinstance(upstream_status_code, int):
            details["source_status_code"] = upstream_status_code
        source_error_details = getattr(exc, "details", None)
        if isinstance(source_error_details, dict):
            details["source_error_details"] = source_error_details
        else:
            response_body = getattr(exc, "response_body", None)
            if isinstance(response_body, dict):
                error_payload = response_body.get("error")
                if isinstance(error_payload, dict) and "details" in error_payload:
                    details["source_error_details"] = error_payload["details"]
        raise RuntimeValidationError(
            runtime_error_code,
            message,
            details,
        ) from exc


def runtime_manifest_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("get_runtime_manifest")
    runtime_model_manifest = import_module("algenta.runtime_model_manifest")
    payload = _request_runtime_contract_payload(
        runtime,
        client_method_name="get_runtime_manifest",
        runtime_error_code="invalid_runtime_contract_payload",
        message="get_runtime_manifest() returned an invalid signed payload.",
        upstream_error_codes=("invalid_runtime_contract_payload",),
    )
    return _validate_runtime_proof_payload(
        "get_runtime_manifest",
        payload,
        runtime_model_manifest.RuntimeManifestOutput,
    )


def runtime_modules_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("get_runtime_modules")
    runtime_model_manifest = import_module("algenta.runtime_model_manifest")
    payload = _request_runtime_contract_payload(
        runtime,
        client_method_name="get_runtime_modules",
        runtime_error_code="invalid_runtime_contract_payload",
        message="get_runtime_modules() returned an invalid signed payload.",
        upstream_error_codes=("invalid_runtime_contract_payload",),
    )
    return _validate_runtime_proof_payload(
        "get_runtime_modules",
        payload,
        runtime_model_manifest.RuntimeAdminModulesOutput,
    )


def runtime_benchmarks_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("get_runtime_benchmarks")
    runtime_model_manifest = import_module("algenta.runtime_model_manifest")
    payload = _request_runtime_contract_payload(
        runtime,
        client_method_name="get_runtime_benchmarks",
        runtime_error_code="invalid_runtime_contract_payload",
        message="get_runtime_benchmarks() returned an invalid signed payload.",
        upstream_error_codes=("invalid_runtime_contract_payload",),
    )
    return _validate_runtime_proof_payload(
        "get_runtime_benchmarks",
        payload,
        runtime_model_manifest.RuntimeAdminBenchmarksOutput,
    )


def runtime_release_validation_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("get_runtime_release_validation")
    runtime_model_manifest = import_module("algenta.runtime_model_manifest")
    payload = _request_runtime_contract_payload(
        runtime,
        client_method_name="get_runtime_release_validation",
        runtime_error_code="invalid_runtime_contract_payload",
        message="get_runtime_release_validation() returned an invalid signed payload.",
        upstream_error_codes=("invalid_runtime_contract_payload",),
    )
    return _validate_runtime_proof_payload(
        "get_runtime_release_validation",
        payload,
        runtime_model_manifest.RuntimeReleaseValidationOutput,
    )


def verify_runtime_request(runtime: Any, request: Any = None, **kwargs: Any) -> Any:
    if runtime._uses_api_transport():
        payload = coerce_api_query_payload(request, kwargs)
        return _runtime_model_verify_output_module().VerifyOutput.from_api(
            runtime._client().verify(payload)
        )
    return verify_local_request(runtime, request, kwargs)


def decision_plan_runtime_request(runtime: Any, request: Mapping[str, Any]) -> Any:
    runtime._require_api_transport("plan_decision")
    return _validate_runtime_api_payload(
        "plan_decision",
        runtime._client().plan_decision(dict(request)),
        _runtime_model_decision_plan_module().DecisionPlanOutput,
    )


def create_repository_snapshot_runtime_request(
    runtime: Any,
    repository_id: str,
    request: Mapping[str, Any],
) -> Any:
    runtime._require_api_transport("create_repository_snapshot")
    return _validate_runtime_api_payload(
        "create_repository_snapshot",
        runtime._client().create_repository_snapshot(repository_id, dict(request)),
        _runtime_model_repository_intelligence_module().RepositorySnapshotOutput,
    )


def get_repository_intelligence_capabilities_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("get_repository_intelligence_capabilities")
    return _validate_runtime_api_payload(
        "get_repository_intelligence_capabilities",
        runtime._client().get_repository_intelligence_capabilities(),
        _runtime_model_repository_intelligence_module().RepositoryIntelligenceCapabilitiesOutput,
    )


def get_repository_snapshot_runtime_request(
    runtime: Any,
    repository_id: str,
    snapshot_id: str,
) -> Any:
    runtime._require_api_transport("get_repository_snapshot")
    return _validate_runtime_api_payload(
        "get_repository_snapshot",
        runtime._client().get_repository_snapshot(repository_id, snapshot_id),
        _runtime_model_repository_intelligence_module().RepositorySnapshotOutput,
    )


def triage_repository_runtime_request(
    runtime: Any,
    repository_id: str,
    request: Mapping[str, Any],
) -> Any:
    runtime._require_api_transport("triage_repository")
    return _validate_runtime_api_payload(
        "triage_repository",
        runtime._client().triage_repository(repository_id, dict(request)),
        _runtime_model_repository_intelligence_module().RepositoryTriageOutput,
    )


def create_repository_decision_plan_runtime_request(
    runtime: Any,
    repository_id: str,
    request: Mapping[str, Any],
) -> Any:
    runtime._require_api_transport("create_repository_decision_plan")
    return _validate_runtime_api_payload(
        "create_repository_decision_plan",
        runtime._client().create_repository_decision_plan(repository_id, dict(request)),
        _runtime_model_repository_intelligence_module().RepositoryDecisionPlanRevisionOutput,
    )


def query_repository_graph_runtime_request(
    runtime: Any,
    repository_id: str,
    request: Mapping[str, Any],
) -> Any:
    runtime._require_api_transport("query_repository_graph")
    return _validate_runtime_api_payload(
        "query_repository_graph",
        runtime._client().query_repository_graph(repository_id, dict(request)),
        _runtime_model_repository_intelligence_module().RepositoryGraphQueryOutput,
    )


def simulate_repository_runtime_request(
    runtime: Any,
    repository_id: str,
    request: Mapping[str, Any],
) -> Any:
    runtime._require_api_transport("simulate_repository")
    return _validate_runtime_api_payload(
        "simulate_repository",
        runtime._client().simulate_repository(repository_id, dict(request)),
        _runtime_model_decision_envelope_module().DecisionEnvelopeOutput,
    )


def apply_repository_runtime_request(
    runtime: Any,
    repository_id: str,
    request: Mapping[str, Any],
) -> Any:
    runtime._require_api_transport("apply_repository")
    return _validate_runtime_api_payload(
        "apply_repository",
        runtime._client().apply_repository(repository_id, dict(request)),
        _runtime_model_repository_intelligence_module().RepositoryApplyOutput,
    )


def product_decision_runtime_request(runtime: Any, request: Mapping[str, Any]) -> Any:
    runtime._require_api_transport("product_decision")
    return _validate_runtime_api_payload(
        "product_decision",
        runtime._client().product_decision(dict(request)),
        _runtime_model_products_module().ProductDecisionOutput,
    )


def product_agent_run_runtime_request(runtime: Any, request: Mapping[str, Any]) -> Any:
    runtime._require_api_transport("product_agent_run")
    return _validate_runtime_api_payload(
        "product_agent_run",
        runtime._client().product_agent_run(dict(request)),
        _runtime_model_products_module().ProductAgentRunOutput,
    )


def product_optimize_runtime_request(runtime: Any, request: Mapping[str, Any]) -> Any:
    runtime._require_api_transport("product_optimize")
    return _validate_runtime_api_payload(
        "product_optimize",
        runtime._client().product_optimize(dict(request)),
        _runtime_model_products_module().ProductOptimizeOutput,
    )


def product_retrieve_runtime_request(runtime: Any, request: Mapping[str, Any]) -> Any:
    runtime._require_api_transport("product_retrieve")
    return _validate_runtime_api_payload(
        "product_retrieve",
        runtime._client().product_retrieve(dict(request)),
        _runtime_model_products_module().ProductRetrieveOutput,
    )


def product_forecast_runtime_request(runtime: Any, request: Mapping[str, Any]) -> Any:
    runtime._require_api_transport("product_forecast")
    return _validate_runtime_api_payload(
        "product_forecast",
        runtime._client().product_forecast(dict(request)),
        _runtime_model_products_module().ProductForecastOutput,
    )


def log_decision_runtime_request(runtime: Any, request: Mapping[str, Any]) -> Any:
    runtime._require_api_transport("log_decision")
    return _validate_runtime_api_payload(
        "log_decision",
        runtime._client().log_decision(dict(request)),
        _runtime_model_decision_memory_module().DecisionLogOutput,
    )


def list_decisions_runtime_request(
    runtime: Any,
    *,
    page: int | None = None,
    limit: int | None = None,
    page_size: int | None = None,
    with_outcome_only: bool | None = None,
) -> Any:
    runtime._require_api_transport("list_decisions")
    return _validate_runtime_api_payload(
        "list_decisions",
        runtime._client().list_decisions(
            page=page,
            limit=limit,
            page_size=page_size,
            with_outcome_only=with_outcome_only,
        ),
        _runtime_model_decision_memory_module().DecisionListOutput,
    )


def get_decision_runtime_request(runtime: Any, decision_id: str) -> Any:
    runtime._require_api_transport("get_decision")
    return _validate_runtime_api_payload(
        "get_decision",
        runtime._client().get_decision(decision_id),
        _runtime_model_decision_memory_module().DecisionLogOutput,
    )


def record_outcome_runtime_request(
    runtime: Any,
    decision_id: str,
    *,
    actual_outcome: float,
    outcome_notes: str | None = None,
) -> Any:
    runtime._require_api_transport("record_outcome")
    return _validate_runtime_api_payload(
        "record_outcome",
        runtime._client().record_outcome(
            decision_id,
            actual_outcome=actual_outcome,
            outcome_notes=outcome_notes,
        ),
        _runtime_model_decision_memory_module().DecisionLogOutput,
    )


def execute_decision_runtime_request(
    runtime: Any,
    decision_id: str,
    *,
    webhook_url: str,
    timeout_seconds: float = 10.0,
    force: bool = False,
    override_safety: bool = False,
    metadata: dict[str, Any] | None = None,
) -> Any:
    runtime._require_api_transport("execute_decision")
    return _validate_runtime_api_payload(
        "execute_decision",
        runtime._client().execute_decision(
            decision_id,
            webhook_url=webhook_url,
            timeout_seconds=timeout_seconds,
            force=force,
            override_safety=override_safety,
            metadata=metadata,
        ),
        _runtime_model_decision_memory_module().ExecutionReceiptOutput,
    )


def delete_decision_runtime_request(runtime: Any, decision_id: str) -> dict[str, Any]:
    runtime._require_api_transport("delete_decision")
    return _validate_runtime_api_mapping_payload(
        "delete_decision",
        runtime._client().delete_decision(decision_id),
    )


def recommend_runtime_request(runtime: Any, actions: Any, **kwargs: Any) -> dict[str, Any]:
    runtime._require_api_transport("recommend")
    return _validate_runtime_api_mapping_payload(
        "recommend",
        runtime._client().recommend(actions, **kwargs),
    )


def score_runtime_request(
    runtime: Any,
    request: Mapping[str, Any],
    scoring_weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    runtime._require_api_transport("score")
    return _validate_runtime_api_mapping_payload(
        "score",
        runtime._client().score(dict(request), scoring_weights=scoring_weights),
    )


def batch_runtime_request(runtime: Any, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    runtime._require_api_transport("batch")
    return _validate_runtime_api_mapping_list_payload(
        "batch",
        runtime._client().batch(items),
    )


def compare_runtime_request(runtime: Any, scenarios: Any, **kwargs: Any) -> dict[str, Any]:
    runtime._require_api_transport("compare")
    return _validate_runtime_api_mapping_payload(
        "compare",
        runtime._client().compare(scenarios, **kwargs),
    )


def deployment_regions_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("list_deployment_regions")
    return _validate_runtime_api_payload(
        "list_deployment_regions",
        runtime._client().list_deployment_regions(),
        _runtime_model_deployments_module().DeploymentRegionsOutput,
    )


def get_deployment_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("get_deployment")
    payload = runtime._client().get_deployment()
    if payload is None:
        return None
    return _validate_runtime_api_payload(
        "get_deployment",
        payload,
        _runtime_model_deployments_module().DeploymentOutput,
    )


def create_deployment_runtime_request(
    runtime: Any,
    *,
    provider: str,
    region: str,
    config: dict[str, Any] | None,
    billing_markup_pct: float,
) -> Any:
    runtime._require_api_transport("create_deployment")
    return _validate_runtime_api_payload(
        "create_deployment",
        runtime._client().create_deployment(
            provider=provider,
            region=region,
            config=config,
            billing_markup_pct=billing_markup_pct,
        ),
        _runtime_model_deployments_module().DeploymentOutput,
    )


def delete_deployment_runtime_request(runtime: Any, deployment_id: str) -> Any:
    runtime._require_api_transport("delete_deployment")
    return _validate_runtime_api_payload(
        "delete_deployment",
        runtime._client().delete_deployment(deployment_id),
        _runtime_model_deployments_module().DeploymentDeleteOutput,
    )


def deployment_cost_runtime_request(runtime: Any, deployment_id: str) -> Any:
    runtime._require_api_transport("get_deployment_cost")
    return _validate_runtime_api_payload(
        "get_deployment_cost",
        runtime._client().get_deployment_cost(deployment_id),
        _runtime_model_deployments_module().DeploymentCostOutput,
    )


def me_runtime_request(runtime: Any) -> dict[str, Any]:
    runtime._require_api_transport("me")
    return _validate_runtime_api_structured_mapping_payload(
        "me",
        runtime._client().me(),
        _runtime_model_control_plane_module().MeOutput,
    )


def update_me_runtime_request(
    runtime: Any,
    *,
    name: str | None = None,
    org_name: str | None = None,
) -> Any:
    runtime._require_api_transport("update_me")
    return _validate_runtime_api_structured_mapping_payload(
        "update_me",
        runtime._client().update_me(name=name, org_name=org_name),
        _runtime_model_control_plane_module().MeOutput,
    )


def usage_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("usage")
    return _validate_runtime_api_payload(
        "usage",
        runtime._client().usage(),
        _runtime_model_account_module().UsageOutput,
    )


def limits_runtime_request(runtime: Any) -> dict[str, Any]:
    runtime._require_api_transport("limits")
    return _validate_runtime_api_mapping_payload("limits", runtime._client().limits())


def get_billing_info_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("get_billing_info")
    return _validate_runtime_api_payload(
        "get_billing_info",
        runtime._client().get_billing_info(),
        _runtime_model_control_plane_module().BillingInfoOutput,
    )


def create_billing_checkout_runtime_request(
    runtime: Any,
    *,
    plan: str | None = None,
) -> Any:
    runtime._require_api_transport("create_billing_checkout")
    return _validate_runtime_api_payload(
        "create_billing_checkout",
        runtime._client().create_billing_checkout(plan=plan),
        _runtime_model_control_plane_module().BillingSessionOutput,
    )


def create_billing_portal_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("create_billing_portal")
    return _validate_runtime_api_payload(
        "create_billing_portal",
        runtime._client().create_billing_portal(),
        _runtime_model_control_plane_module().BillingSessionOutput,
    )


def refresh_credits_runtime_request(
    runtime: Any,
    *,
    device_id: str,
    billing_period: str,
    credits_used: int = 0,
) -> Any:
    runtime._require_api_transport("refresh_credits")
    return _validate_runtime_api_payload(
        "refresh_credits",
        runtime._client().refresh_credits(
            device_id=device_id,
            billing_period=billing_period,
            credits_used=credits_used,
        ),
        _runtime_model_control_plane_module().CreditRefreshOutput,
    )


def ingest_metering_events_runtime_request(
    runtime: Any,
    *,
    device_id: str,
    events: list[dict[str, Any]],
) -> Any:
    runtime._require_api_transport("ingest_metering_events")
    return _validate_runtime_api_payload(
        "ingest_metering_events",
        runtime._client().ingest_metering_events(device_id=device_id, events=events),
        _runtime_model_control_plane_module().MeteringBatchOutput,
    )


def list_api_keys_runtime_request(runtime: Any) -> list[Any]:
    runtime._require_api_transport("list_api_keys")
    return _validate_runtime_api_payload_list(
        "list_api_keys",
        runtime._client().list_api_keys(),
        _runtime_model_account_module().APIKeyInfoOutput,
    )


def create_api_key_runtime_request(
    runtime: Any,
    *,
    label: str | None = None,
    name: str | None = None,
    expires_at: Any = None,
    device_limit: int | None = None,
) -> Any:
    runtime._require_api_transport("create_api_key")
    return _validate_runtime_api_payload(
        "create_api_key",
        runtime._client().create_api_key(
            label=label,
            name=name,
            expires_at=expires_at,
            device_limit=device_limit,
        ),
        _runtime_model_account_module().APIKeyCreatedOutput,
    )


def revoke_api_key_runtime_request(runtime: Any, key_id: str) -> dict[str, Any]:
    runtime._require_api_transport("revoke_api_key")
    return _validate_runtime_api_mapping_payload(
        "revoke_api_key",
        runtime._client().revoke_api_key(key_id),
    )


def distributions_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("distributions")
    return _validate_runtime_api_payload(
        "distributions",
        runtime._client().distributions(),
        _runtime_model_control_plane_module().DistributionListOutput,
    )


def templates_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("templates")
    return _validate_runtime_api_payload(
        "templates",
        runtime._client().templates(),
        _runtime_model_control_plane_module().TemplateListOutput,
    )


def list_team_members_runtime_request(
    runtime: Any,
    *,
    page: int | None = None,
    limit: int | None = None,
) -> Any:
    runtime._require_api_transport("list_team_members")
    return _validate_runtime_api_payload(
        "list_team_members",
        runtime._client().list_team_members(page=page, limit=limit),
        _runtime_model_control_plane_module().TeamListOutput,
    )


def invite_team_member_runtime_request(
    runtime: Any,
    *,
    email: str,
    role: str = "member",
) -> Any:
    runtime._require_api_transport("invite_team_member")
    return _validate_runtime_api_payload(
        "invite_team_member",
        runtime._client().invite_team_member(email=email, role=role),
        _runtime_model_control_plane_module().TeamInviteOutput,
    )


def update_team_member_role_runtime_request(
    runtime: Any,
    user_id: str,
    *,
    role: str,
) -> Any:
    runtime._require_api_transport("update_team_member_role")
    return _validate_runtime_api_payload(
        "update_team_member_role",
        runtime._client().update_team_member_role(user_id, role=role),
        _runtime_model_control_plane_module().TeamRoleUpdateOutput,
    )


def remove_team_member_runtime_request(runtime: Any, user_id: str) -> Any:
    runtime._require_api_transport("remove_team_member")
    payload = runtime._client().remove_team_member(user_id)
    if not isinstance(payload, dict):
        raise TypeError(
            f"remove_team_member returned {type(payload).__name__}, expected a JSON object."
        )
    return _validate_runtime_api_payload(
        "remove_team_member",
        {"removed": True, "user_id": user_id, **payload},
        _runtime_model_control_plane_module().TeamRemoveOutput,
    )


def get_audit_logs_runtime_request(
    runtime: Any,
    *,
    page: int = 1,
    limit: int = 25,
    actor_email: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    result: str | None = None,
    policy_snapshot_id: str | None = None,
    schema_snapshot_id: str | None = None,
    manifest_version: str | None = None,
    request_hash: str | None = None,
) -> Any:
    runtime._require_api_transport("get_audit_logs")
    return _validate_runtime_api_payload(
        "get_audit_logs",
        runtime._client().get_audit_logs(
            page=page,
            limit=limit,
            actor_email=actor_email,
            action=action,
            resource_type=resource_type,
            result=result,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            manifest_version=manifest_version,
            request_hash=request_hash,
        ),
        _runtime_model_control_plane_module().AuditLogOutput,
    )


def get_audit_log_artifacts_runtime_request(
    runtime: Any,
    *,
    page: int = 1,
    limit: int = 25,
    actor_email: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    result: str | None = None,
    policy_snapshot_id: str | None = None,
    schema_snapshot_id: str | None = None,
    manifest_version: str | None = None,
    request_hash: str | None = None,
    content_hash: str | None = None,
) -> Any:
    runtime._require_api_transport("get_audit_log_artifacts")
    return _validate_runtime_api_payload(
        "get_audit_log_artifacts",
        runtime._client().get_audit_log_artifacts(
            page=page,
            limit=limit,
            actor_email=actor_email,
            action=action,
            resource_type=resource_type,
            result=result,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            manifest_version=manifest_version,
            request_hash=request_hash,
            content_hash=content_hash,
        ),
        _runtime_model_control_plane_module().AuditLogOutput,
    )


def get_execution_policy_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("get_execution_policy")
    return _validate_runtime_api_payload(
        "get_execution_policy",
        runtime._client().get_execution_policy(),
        _runtime_model_control_plane_module().ExecutionPolicyOutput,
    )


def list_execution_policy_snapshots_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("list_execution_policy_snapshots")
    return _validate_runtime_api_payload(
        "list_execution_policy_snapshots",
        runtime._client().list_execution_policy_snapshots(),
        _runtime_model_control_plane_module().ExecutionPolicySnapshotListOutput,
    )


def list_devices_runtime_request(
    runtime: Any,
    *,
    page: int | None = None,
    limit: int | None = None,
) -> Any:
    runtime._require_api_transport("list_devices")
    return _validate_runtime_api_payload(
        "list_devices",
        runtime._client().list_devices(page=page, limit=limit),
        _runtime_model_control_plane_module().DeviceListOutput,
    )


def revoke_device_runtime_request(runtime: Any, registration_id: str) -> Any:
    runtime._require_api_transport("revoke_device")
    return _validate_runtime_api_payload(
        "revoke_device",
        runtime._client().revoke_device(registration_id),
        _runtime_model_control_plane_module().DeviceRevokeOutput,
    )


def update_execution_policy_runtime_request(
    runtime: Any,
    *,
    min_confidence: float | None = None,
    risk_floor: float | None = None,
    require_calibration: bool | None = None,
    allow_reexecution: bool | None = None,
) -> Any:
    runtime._require_api_transport("update_execution_policy")
    return _validate_runtime_api_payload(
        "update_execution_policy",
        runtime._client().update_execution_policy(
            min_confidence=min_confidence,
            risk_floor=risk_floor,
            require_calibration=require_calibration,
            allow_reexecution=allow_reexecution,
        ),
        _runtime_model_control_plane_module().ExecutionPolicyOutput,
    )


def llm_models_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("list_models")
    return _validate_runtime_api_payload(
        "list_models",
        runtime._client().list_models(),
        _runtime_model_llm_module().LLMModelListOutput,
    )


def resolve_artifact_bridge_runtime_request(
    runtime: Any,
    *,
    repo_id: str,
    filename: str,
    revision: str | None,
    local_files_only: bool,
) -> Any:
    runtime._require_api_transport("resolve_artifact_bridge")
    return _validate_runtime_api_payload(
        "resolve_artifact_bridge",
        runtime._client().resolve_artifact_bridge(
            repo_id=repo_id,
            filename=filename,
            revision=revision,
            local_files_only=local_files_only,
        ),
        _runtime_model_llm_module().ArtifactBridgeResolveOutput,
    )


def tokenize_runtime_request(runtime: Any, text: str, *, model: str) -> Any:
    runtime._require_api_transport("tokenize")
    return _validate_runtime_api_payload(
        "tokenize",
        runtime._client().tokenize(text, model=model),
        _runtime_model_llm_module().TokenizeOutput,
    )


def count_tokens_runtime_request(runtime: Any, text: str, *, model: str) -> Any:
    runtime._require_api_transport("count_tokens")
    return _validate_runtime_api_payload(
        "count_tokens",
        runtime._client().count_tokens(text, model=model),
        _runtime_model_llm_module().CountTokensOutput,
    )


def chat_completions_runtime_request(
    runtime: Any,
    messages: list[dict[str, str]],
    *,
    model: str,
) -> Any:
    runtime._require_api_transport("chat_completions")
    return _validate_runtime_api_payload(
        "chat_completions",
        runtime._client().chat_completions(messages, model=model),
        _runtime_model_llm_module().ChatCompletionsOutput,
    )


def stream_chat_completions_runtime_request(
    runtime: Any,
    messages: list[dict[str, str]],
    *,
    model: str,
) -> Any:
    runtime._require_api_transport("stream_chat_completions")
    return _validate_runtime_api_stream(
        "stream_chat_completions",
        runtime._client().stream_chat_completions(messages, model=model),
        _runtime_model_llm_module().ChatCompletionsStreamChunkOutput,
    )


def responses_runtime_request(
    runtime: Any,
    input_value: str | list[str],
    *,
    model: str,
    dimensions: int,
) -> Any:
    runtime._require_api_transport("responses")
    return _validate_runtime_api_payload(
        "responses",
        runtime._client().responses(input_value, model=model, dimensions=dimensions),
        _runtime_model_llm_module().ResponsesOutput,
    )


def stream_responses_runtime_request(
    runtime: Any,
    input_value: str | list[str],
    *,
    model: str,
    dimensions: int,
) -> Any:
    runtime._require_api_transport("stream_responses")
    return _validate_runtime_api_stream(
        "stream_responses",
        runtime._client().stream_responses(input_value, model=model, dimensions=dimensions),
        _runtime_model_llm_module().ResponseStreamEventOutput,
    )


def embeddings_runtime_request(
    runtime: Any,
    input_value: str | list[str],
    *,
    model: str,
    dimensions: int,
) -> Any:
    runtime._require_api_transport("embeddings")
    return _validate_runtime_api_payload(
        "embeddings",
        runtime._client().embeddings(input_value, model=model, dimensions=dimensions),
        _runtime_model_llm_module().EmbeddingsOutput,
    )


def embedding_similarity_runtime_request(
    runtime: Any,
    left: list[float],
    right: list[float],
    *,
    model: str,
) -> Any:
    runtime._require_api_transport("embedding_similarity")
    return _validate_runtime_api_payload(
        "embedding_similarity",
        runtime._client().embedding_similarity(left, right, model=model),
        _runtime_model_llm_module().EmbeddingSimilarityOutput,
    )


def rerank_runtime_request(
    runtime: Any,
    query_embedding: list[float],
    documents: list[dict[str, Any]],
    *,
    model: str,
    top_n: int | None,
) -> Any:
    runtime._require_api_transport("rerank")
    return _validate_runtime_api_payload(
        "rerank",
        runtime._client().rerank(
            query_embedding,
            documents,
            model=model,
            top_n=top_n,
        ),
        _runtime_model_llm_module().RerankResponseOutput,
    )


def create_agent_run_runtime_request(
    runtime: Any,
    *,
    task: str,
    context: dict[str, Any] | None,
    tools: list[str] | None,
    max_steps: int,
    output_format: str,
    approval_mode: str,
    start_paused: bool,
) -> Any:
    runtime._require_api_transport("create_agent_run")
    return _validate_runtime_api_payload(
        "create_agent_run",
        runtime._client().create_agent_run(
            task=task,
            context=context,
            tools=tools,
            max_steps=max_steps,
            output_format=output_format,
            approval_mode=approval_mode,
            start_paused=start_paused,
        ),
        _runtime_model_agent_runs_module().AgentRunOutput,
    )


def get_agent_run_runtime_request(runtime: Any, run_id: str) -> Any:
    runtime._require_api_transport("get_agent_run")
    return _validate_runtime_api_payload(
        "get_agent_run",
        runtime._client().get_agent_run(run_id),
        _runtime_model_agent_runs_module().AgentRunOutput,
    )


def list_agent_runs_runtime_request(
    runtime: Any,
    *,
    page: int,
    limit: int,
    status: str | None,
    request_hash: str | None,
    policy_snapshot_id: str | None,
    schema_snapshot_id: str | None,
) -> Any:
    runtime._require_api_transport("list_agent_runs")
    return _validate_runtime_api_payload(
        "list_agent_runs",
        runtime._client().list_agent_runs(
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
        ),
        _runtime_model_agent_runs_module().AgentRunListOutput,
    )


def get_agent_run_events_runtime_request(
    runtime: Any,
    run_id: str,
    *,
    limit: int,
) -> Any:
    runtime._require_api_transport("get_agent_run_events")
    return _validate_runtime_api_payload(
        "get_agent_run_events",
        runtime._client().get_agent_run_events(run_id, limit=limit),
        _runtime_model_agent_runs_module().AgentRunEventsOutput,
    )


def list_agent_run_mission_events_runtime_request(
    runtime: Any,
    run_id: str,
    *,
    limit: int,
) -> Any:
    runtime._require_api_transport("list_agent_run_mission_events")
    return _validate_runtime_api_payload(
        "list_agent_run_mission_events",
        runtime._client().list_agent_run_mission_events(run_id, limit=limit),
        _runtime_model_agent_runs_module().AgentRunMissionEventsOutput,
    )


def query_agent_run_mission_events_runtime_request(
    runtime: Any,
    *,
    page: int,
    limit: int,
    status: str | None,
    request_hash: str | None,
    policy_snapshot_id: str | None,
    schema_snapshot_id: str | None,
    run_id: str | None,
    event_type: str | None,
) -> Any:
    runtime._require_api_transport("query_agent_run_mission_events")
    return _validate_runtime_api_payload(
        "query_agent_run_mission_events",
        runtime._client().query_agent_run_mission_events(
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            run_id=run_id,
            event_type=event_type,
        ),
        _runtime_model_agent_runs_module().AgentRunMissionEventListResponseOutput,
    )


def stream_agent_run_events_runtime_request(
    runtime: Any,
    run_id: str,
    *,
    limit: int,
) -> Any:
    runtime._require_api_transport("stream_agent_run_events")
    return _validate_runtime_api_stream(
        "stream_agent_run_events",
        runtime._client().stream_agent_run_events(run_id, limit=limit),
        _runtime_model_agent_runs_module().AgentRunStreamEventOutput,
    )


def list_agent_run_checkpoints_runtime_request(runtime: Any, run_id: str) -> Any:
    runtime._require_api_transport("list_agent_run_checkpoints")
    return _validate_runtime_api_payload(
        "list_agent_run_checkpoints",
        runtime._client().list_agent_run_checkpoints(run_id),
        _runtime_model_agent_runs_module().AgentRunCheckpointsOutput,
    )


def query_agent_run_checkpoints_runtime_request(
    runtime: Any,
    *,
    page: int,
    limit: int,
    status: str | None,
    request_hash: str | None,
    policy_snapshot_id: str | None,
    schema_snapshot_id: str | None,
    run_id: str | None,
    checkpoint_id: str | None,
) -> Any:
    runtime._require_api_transport("query_agent_run_checkpoints")
    return _validate_runtime_api_payload(
        "query_agent_run_checkpoints",
        runtime._client().query_agent_run_checkpoints(
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            run_id=run_id,
            checkpoint_id=checkpoint_id,
        ),
        _runtime_model_agent_runs_module().AgentRunCheckpointListResponseOutput,
    )


def list_agent_run_telemetry_runtime_request(
    runtime: Any,
    run_id: str,
    *,
    limit: int,
) -> Any:
    runtime._require_api_transport("list_agent_run_telemetry")
    return _validate_runtime_api_payload(
        "list_agent_run_telemetry",
        runtime._client().list_agent_run_telemetry(run_id, limit=limit),
        _runtime_model_agent_runs_module().AgentRunTelemetryOutput,
    )


def query_agent_run_telemetry_runtime_request(
    runtime: Any,
    *,
    page: int,
    limit: int,
    status: str | None,
    request_hash: str | None,
    policy_snapshot_id: str | None,
    schema_snapshot_id: str | None,
    run_id: str | None,
    telemetry_kind: str | None,
    module_name: str | None,
) -> Any:
    runtime._require_api_transport("query_agent_run_telemetry")
    return _validate_runtime_api_payload(
        "query_agent_run_telemetry",
        runtime._client().query_agent_run_telemetry(
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            run_id=run_id,
            telemetry_kind=telemetry_kind,
            module_name=module_name,
        ),
        _runtime_model_agent_runs_module().AgentRunTelemetryListOutput,
    )


def replay_agent_run_runtime_request(
    runtime: Any,
    run_id: str,
    *,
    checkpoint_id: str | None,
) -> Any:
    runtime._require_api_transport("replay_agent_run")
    return _validate_runtime_api_payload(
        "replay_agent_run",
        runtime._client().replay_agent_run(run_id, checkpoint_id=checkpoint_id),
        _runtime_model_agent_runs_module().AgentRunReplayOutput,
    )


def fork_agent_run_runtime_request(
    runtime: Any,
    run_id: str,
    *,
    checkpoint_id: str | None,
) -> Any:
    runtime._require_api_transport("fork_agent_run")
    return _validate_runtime_api_payload(
        "fork_agent_run",
        runtime._client().fork_agent_run(run_id, checkpoint_id=checkpoint_id),
        _runtime_model_agent_runs_module().AgentRunOutput,
    )


def resume_agent_run_runtime_request(runtime: Any, run_id: str) -> Any:
    runtime._require_api_transport("resume_agent_run")
    return _validate_runtime_api_payload(
        "resume_agent_run",
        runtime._client().resume_agent_run(run_id),
        _runtime_model_agent_runs_module().AgentRunOutput,
    )


def cancel_agent_run_runtime_request(runtime: Any, run_id: str) -> Any:
    runtime._require_api_transport("cancel_agent_run")
    return _validate_runtime_api_payload(
        "cancel_agent_run",
        runtime._client().cancel_agent_run(run_id),
        _runtime_model_agent_runs_module().AgentRunOutput,
    )


def approve_agent_run_runtime_request(runtime: Any, run_id: str) -> Any:
    runtime._require_api_transport("approve_agent_run")
    return _validate_runtime_api_payload(
        "approve_agent_run",
        runtime._client().approve_agent_run(run_id),
        _runtime_model_agent_runs_module().AgentRunOutput,
    )


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
                "Install algenta-sdk or algenta-core[cloud]."
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


__all__ = [
    "cancel_job_runtime_request",
    "create_api_key_runtime_request",
    "coerce_api_query_payload",
    "coerce_api_resolve_payload",
    "coerce_plan",
    "contract_runtime_request",
    "consume_local_credit",
    "ensure_local_execution_entitlement",
    "forget_api_registration",
    "get_job_result_runtime_request",
    "get_job_runtime_request",
    "ingest_metering_events_runtime_request",
    "invite_team_member_runtime_request",
    "limits_runtime_request",
    "list_api_keys_runtime_request",
    "list_devices_runtime_request",
    "list_jobs_runtime_request",
    "me_runtime_request",
    "query_batch_runtime_request",
    "query_local_request",
    "query_sql_report_runtime_request",
    "query_runtime_request",
    "remove_team_member_runtime_request",
    "revoke_device_runtime_request",
    "revoke_api_key_runtime_request",
    "remember_api_registration",
    "resolve_local_request",
    "resolve_runtime_request",
    "runtime_api_client",
    "runtime_benchmarks_runtime_request",
    "runtime_manifest_runtime_request",
    "runtime_modules_runtime_request",
    "runtime_release_validation_runtime_request",
    "stream_agent_run_events_runtime_request",
    "stream_chat_completions_runtime_request",
    "stream_responses_runtime_request",
    "submit_job_runtime_request",
    "test_webhook_delivery_runtime_request",
    "try_exact_api_resolve",
    "usage_runtime_request",
    "update_team_member_role_runtime_request",
    "verify_local_request",
    "verify_runtime_request",
    "poll_job_runtime_request",
]
