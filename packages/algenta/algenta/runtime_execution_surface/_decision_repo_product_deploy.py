"""verify/decision/repository/product/recommend/deployment runtime requests.

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


@cache
def _runtime_repository_intelligence_module_runtime() -> ModuleType:
    return import_module("algenta.runtime_repository_intelligence")


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
from algenta.runtime_execution_surface._query_jobs_triggers import *  # noqa: F401, F403


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
    if runtime._uses_api_transport():
        return _validate_runtime_api_payload(
            "create_repository_snapshot",
            runtime._client().create_repository_snapshot(repository_id, dict(request)),
            _runtime_model_repository_intelligence_module().RepositorySnapshotOutput,
        )
    payload = _call_local_repository_intelligence_backend(
        runtime,
        "create_repository_snapshot",
        repository_id,
        dict(request),
    )
    return _coerce_repository_backend_result(
        "create_repository_snapshot",
        payload,
        _runtime_model_repository_intelligence_module().RepositorySnapshotOutput,
    )


def get_repository_intelligence_capabilities_runtime_request(runtime: Any) -> Any:
    if runtime._uses_api_transport():
        return _validate_runtime_api_payload(
            "get_repository_intelligence_capabilities",
            runtime._client().get_repository_intelligence_capabilities(),
            _runtime_model_repository_intelligence_module().RepositoryIntelligenceCapabilitiesOutput,
        )
    payload = _call_local_repository_intelligence_backend(
        runtime,
        "get_repository_intelligence_capabilities",
    )
    return _coerce_repository_backend_result(
        "get_repository_intelligence_capabilities",
        payload,
        _runtime_model_repository_intelligence_module().RepositoryIntelligenceCapabilitiesOutput,
    )


def get_repository_snapshot_runtime_request(
    runtime: Any,
    repository_id: str,
    snapshot_id: str,
) -> Any:
    if runtime._uses_api_transport():
        return _validate_runtime_api_payload(
            "get_repository_snapshot",
            runtime._client().get_repository_snapshot(repository_id, snapshot_id),
            _runtime_model_repository_intelligence_module().RepositorySnapshotOutput,
        )
    payload = _call_local_repository_intelligence_backend(
        runtime,
        "get_repository_snapshot",
        repository_id,
        snapshot_id,
    )
    return _coerce_repository_backend_result(
        "get_repository_snapshot",
        payload,
        _runtime_model_repository_intelligence_module().RepositorySnapshotOutput,
    )


def triage_repository_runtime_request(
    runtime: Any,
    repository_id: str,
    request: Mapping[str, Any],
) -> Any:
    if runtime._uses_api_transport():
        return _validate_runtime_api_payload(
            "triage_repository",
            runtime._client().triage_repository(repository_id, dict(request)),
            _runtime_model_repository_intelligence_module().RepositoryTriageOutput,
        )
    payload = _call_local_repository_intelligence_backend(
        runtime,
        "triage_repository",
        repository_id,
        dict(request),
    )
    return _coerce_repository_backend_result(
        "triage_repository",
        payload,
        _runtime_model_repository_intelligence_module().RepositoryTriageOutput,
    )


def create_repository_decision_plan_runtime_request(
    runtime: Any,
    repository_id: str,
    request: Mapping[str, Any],
) -> Any:
    if runtime._uses_api_transport():
        return _validate_runtime_api_payload(
            "create_repository_decision_plan",
            runtime._client().create_repository_decision_plan(repository_id, dict(request)),
            _runtime_model_repository_intelligence_module().RepositoryDecisionPlanRevisionOutput,
        )
    payload = _call_local_repository_intelligence_backend(
        runtime,
        "create_repository_decision_plan",
        repository_id,
        dict(request),
    )
    return _coerce_repository_backend_result(
        "create_repository_decision_plan",
        payload,
        _runtime_model_repository_intelligence_module().RepositoryDecisionPlanRevisionOutput,
    )


def query_repository_graph_runtime_request(
    runtime: Any,
    repository_id: str,
    request: Mapping[str, Any],
) -> Any:
    if runtime._uses_api_transport():
        return _validate_runtime_api_payload(
            "query_repository_graph",
            runtime._client().query_repository_graph(repository_id, dict(request)),
            _runtime_model_repository_intelligence_module().RepositoryGraphQueryOutput,
        )
    payload = _call_local_repository_intelligence_backend(
        runtime,
        "query_repository_graph",
        repository_id,
        dict(request),
    )
    return _coerce_repository_backend_result(
        "query_repository_graph",
        payload,
        _runtime_model_repository_intelligence_module().RepositoryGraphQueryOutput,
    )


def simulate_repository_runtime_request(
    runtime: Any,
    repository_id: str,
    request: Mapping[str, Any],
) -> Any:
    if runtime._uses_api_transport():
        return _validate_runtime_api_payload(
            "simulate_repository",
            runtime._client().simulate_repository(repository_id, dict(request)),
            _runtime_model_decision_envelope_module().DecisionEnvelopeOutput,
        )
    payload = _call_local_repository_intelligence_backend(
        runtime,
        "simulate_repository",
        repository_id,
        dict(request),
    )
    return _coerce_repository_backend_result(
        "simulate_repository",
        payload,
        _runtime_model_decision_envelope_module().DecisionEnvelopeOutput,
    )


def apply_repository_runtime_request(
    runtime: Any,
    repository_id: str,
    request: Mapping[str, Any],
) -> Any:
    if runtime._uses_api_transport():
        return _validate_runtime_api_payload(
            "apply_repository",
            runtime._client().apply_repository(repository_id, dict(request)),
            _runtime_model_repository_intelligence_module().RepositoryApplyOutput,
        )
    payload = _call_local_repository_intelligence_backend(
        runtime,
        "apply_repository",
        repository_id,
        dict(request),
    )
    return _coerce_repository_backend_result(
        "apply_repository",
        payload,
        _runtime_model_repository_intelligence_module().RepositoryApplyOutput,
    )


def _call_local_repository_intelligence_backend(
    runtime: Any,
    method_name: str,
    *args: Any,
) -> Any:
    backend = _runtime_repository_intelligence_module_runtime().require_repository_intelligence_backend(
        runtime,
        method_name,
    )
    return getattr(backend, method_name)(*args)


def _coerce_repository_backend_result(
    method_name: str,
    payload: Any,
    parser: Any,
) -> Any:
    if isinstance(payload, parser):
        return payload
    return _validate_runtime_api_payload(method_name, payload, parser)


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
