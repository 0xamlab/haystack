"""
Synchronous Algenta API client.

Usage:
    import os

    from decision_engine import AlgentaClient

    api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
    if not api_key:
        raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

    client = AlgentaClient(api_key=api_key)
    result = client.simulate(
        mode="auto",
        scenario={
            "variables": {"revenue": {"low": 80000, "high": 200000}},
            "objective": "maximize_net_value",
        },
    )
    print(result.recommended_action, result.confidence)

This example is the Cloud Managed path. In `self_hosted` and `air_gapped`,
pass an explicit self-hosted `base_url` and use the API key provisioned by
your self-hosted operator deployment instead. Private profiles fail closed and
do not silently fall back to Algenta cloud.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Iterator
from datetime import datetime
from functools import cache
from typing import TYPE_CHECKING, Any

from .device_binding import (
    DEVICE_BINDING_TOKEN_HEADER,
    load_device_binding_token,
    store_device_binding_token,
)
from .device_headers import DEVICE_ID_HEADER, build_device_headers
from .lazy_http_client import LazySyncHttpClient
from .privacy_profile import api_key_help_text, resolve_client_base_url
from .sdk_defaults import DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT

if TYPE_CHECKING:
    from types import ModuleType

    import httpx

    from .models_account import APIKeyInfo, UsageInfo
    from .models_agent_runs import (
        AgentRunCheckpointsResult,
        AgentRunCheckpointListResponseResult,
        AgentRunEventsResult,
        AgentRunListResult,
        AgentRunMissionEventListResponseResult,
        AgentRunMissionEventsResult,
        AgentRunReplayResult,
        AgentRunResult,
        AgentRunStreamEventResult,
        AgentRunTelemetryListResult,
        AgentRunTelemetryResult,
    )
    from .models_control_plane import (
        AuditLogResult,
        BillingInfoResult,
        BillingSessionResult,
        CreditRefreshResult,
        MeteringBatchResult,
        DeviceListResult,
        DeviceRevokeResult,
        DistributionListResult,
        ExecutionPolicyResult,
        ExecutionPolicySnapshotListResult,
        MeResult,
        TemplateListResult,
        TeamInviteResult,
        TeamListResult,
        TeamRemoveResult,
        TeamRoleUpdateResult,
    )
    from .models_decision_memory import (
        DecisionListResult,
        DecisionLogResult,
        ExecutionReceiptResult,
    )
    from .models_triggers import (
        TriggerDeleteResult,
        TriggerFireResult,
        TriggerListResult,
        TriggerPauseResult,
        TriggerSummaryResult,
    )
    from .models_connectors import (
        ConnectorBrowseResult,
        ConnectorInfo,
        ConnectorListResult,
        ConnectorTestInfo,
        DatasetConnectResult,
        DatasetDeleteResult,
        DatasetDetailResult,
        DatasetListResult,
        DatasetSummaryResult,
    )
    from .models_repository_intelligence import (
        RepositoryApplyResult,
        RepositoryGraphQueryResult,
        RepositoryDecisionPlanRevisionResult,
        RepositorySnapshotResult,
        RepositoryTriageResult,
    )
    from .models_contract import PlatformContractResult
    from .models_capability_plane import (
        CapabilityAuthorizationCompleteResult,
        CapabilityAuthorizationStartResult,
        CapabilityBindingResult,
        CapabilityBindingTestResult,
        CapabilityCatalogEntryResult,
        CapabilityDiscoverResult,
        CapabilityExecutionResult,
        CapabilityOutcomeRecordResult,
        CapabilityProviderResult,
        CapabilityRoutePlanResult,
    )
    from .models_decision_plan import DecisionPlanResult
    from .models_products import (
        ProductAgentRunResult,
        ProductDecisionResult,
        ProductForecastResult,
        ProductOptimizeResult,
        ProductRetrieveResult,
    )
    from .models_deployments import (
        DeploymentCostResult,
        DeploymentDeleteResult,
        DeploymentRegionsResult,
        DeploymentResult,
    )
    from .models_llm import (
        ArtifactBridgeResolveResult,
        ChatCompletionsResult,
        ChatCompletionsStreamChunkResult,
        CountTokensResult,
        EmbeddingSimilarityResult,
        EmbeddingsResult,
        LLMModelListResult,
        ResponseStreamEventResult,
        ResponsesResult,
        RerankResponseResult,
        TokenizeResult,
    )
    from .models_runtime_manifest import (
        RuntimeAdminBenchmarksResult,
        RuntimeAdminModulesResult,
        RuntimeManifestResult,
        RuntimeReleaseValidationResult,
    )
    from .models_decision_envelope import DecisionEnvelope
    from .models_query import (
        ExplainResult,
        QueryBatchResult,
        QueryResult,
        QuerySqlReportResult,
        QueryWithMetadataResult,
        ResolveResult,
        SourceRegistrationResult,
        VerifyResult,
    )

_httpx: Any | None = None
_SDK_USER_AGENT = "algenta-python/1.0.0"
_SDK_VERSION = "algenta-python/1.0.0"


def _get_httpx() -> Any:
    global _httpx
    if _httpx is None:
        _httpx = importlib.import_module("httpx")
    return _httpx


@cache
def _connector_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_connector_surface")


@cache
def _repository_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_repository_surface")


@cache
def _transport_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_transport")


@cache
def _response_module() -> ModuleType:
    return importlib.import_module("decision_engine.transport_response")


@cache
def _query_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_query_surface")


@cache
def _contract_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_contract_surface")


@cache
def _simulation_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_simulation_surface")


@cache
def _source_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_source_surface")


@cache
def _job_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_job_surface")


@cache
def _product_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_product_surface")


@cache
def _deployment_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_deployment_surface")


@cache
def _account_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_account_surface")


@cache
def _control_plane_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_control_plane_surface")


@cache
def _llm_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_llm_surface")


@cache
def _agent_run_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_agent_run_surface")


@cache
def _decision_plan_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_decision_plan_surface")


@cache
def _decision_memory_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_decision_memory_surface")


@cache
def _trigger_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_trigger_surface")


@cache
def _capability_plane_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_capability_plane_surface")


class DecisionEngineClient:
    """
    Synchronous HTTP client for the Algenta API.

    `AlgentaClient` is the preferred public alias.
    `DecisionEngineClient` remains available for backward compatibility.

    Args:
        api_key: Your API key. Prefer `ALGENTA_API_KEY`; legacy `DE_API_KEY`
            remains accepted for compatibility.
                 Falls back to ALGENTA_API_KEY or DE_API_KEY environment variable.
        base_url: API base URL. Override for self-hosted deployments.
        timeout: Request timeout in seconds.
        max_retries: Maximum retries on 429 and 5xx responses.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        resolved_base_url = resolve_client_base_url(
            explicit_base_url=base_url,
            component="DecisionEngineClient",
        )
        resolved_key = (
            api_key or os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "")
        )
        if not resolved_key:
            raise ValueError(
                "API key required. Pass api_key= or set ALGENTA_API_KEY / DE_API_KEY environment variables.\n"
                + api_key_help_text(
                    component="DecisionEngineClient",
                    fallback_base_url=resolved_base_url,
                )
            )
        self._api_key = resolved_key
        self._base_url = resolved_base_url
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = LazySyncHttpClient(self._build_http_client)

    def _build_http_client(self) -> Any:
        httpx = _get_httpx()
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": _SDK_USER_AGENT,
        }
        headers.update(
            build_device_headers(
                sdk_version=_SDK_VERSION,
                user_agent=_SDK_USER_AGENT,
            )
        )
        device_id = headers.get(DEVICE_ID_HEADER, "").strip()
        if device_id:
            binding_token = load_device_binding_token(
                base_url=self._base_url,
                api_key=self._api_key,
                device_id=device_id,
            )
            if binding_token:
                headers[DEVICE_BINDING_TOKEN_HEADER] = binding_token
        return httpx.Client(
            base_url=self._base_url,
            headers=headers,
            timeout=self._timeout,
        )

    def _get_httpx_module(self) -> Any:
        return _get_httpx()

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        return _transport_module().request_with_retries(self, method, path, **kwargs)

    def _request_response(self, method: str, path: str, **kwargs: Any) -> tuple[Any, Any]:
        return _transport_module().request_with_retries_and_response(self, method, path, **kwargs)

    def _handle_response(self, response: httpx.Response) -> Any:
        return _response_module().handle_response(
            response,
            auth_message="Authentication failed",
        )

    def _store_device_binding_token(self, response: Any) -> None:
        binding_token = str(response.headers.get(DEVICE_BINDING_TOKEN_HEADER, "")).strip()
        if not binding_token:
            return
        device_id = str(self._client.headers.get(DEVICE_ID_HEADER, "")).strip()
        if not device_id:
            return
        store_device_binding_token(
            base_url=self._base_url,
            api_key=self._api_key,
            device_id=device_id,
            binding_token=binding_token,
        )
        self._client.headers[DEVICE_BINDING_TOKEN_HEADER] = binding_token

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> DecisionEngineClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ─── Simulation Endpoints ─────────────────────────────────────────────────

    def simulate(self, **kwargs: Any) -> DecisionEnvelope:
        return _simulation_surface_module().simulate(self, **kwargs)

    def resolve(self, request: dict[str, Any] | None = None, **kwargs: Any) -> ResolveResult:
        return _query_surface_module().resolve(self, request, **kwargs)

    def query(self, request: dict[str, Any] | None = None, **kwargs: Any) -> QueryResult:
        return _query_surface_module().query(self, request, **kwargs)

    def query_with_metadata(
        self,
        request: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> QueryWithMetadataResult:
        return _query_surface_module().query_with_metadata(self, request, **kwargs)

    def query_batch(self, request: dict[str, Any]) -> QueryBatchResult:
        return _query_surface_module().query_batch(self, request)

    def query_sql_report(self, request: dict[str, Any]) -> QuerySqlReportResult:
        return _query_surface_module().query_sql_report(self, request)

    def plan_decision(self, request: dict[str, Any]) -> DecisionPlanResult:
        return _decision_plan_surface_module().plan_decision(self, request)

    def product_decision(self, request: dict[str, Any]) -> ProductDecisionResult:
        return _product_surface_module().product_decision(self, request)

    def product_agent_run(self, request: dict[str, Any]) -> ProductAgentRunResult:
        return _product_surface_module().product_agent_run(self, request)

    def product_optimize(self, request: dict[str, Any]) -> ProductOptimizeResult:
        return _product_surface_module().product_optimize(self, request)

    def product_retrieve(self, request: dict[str, Any]) -> ProductRetrieveResult:
        return _product_surface_module().product_retrieve(self, request)

    def product_forecast(self, request: dict[str, Any]) -> ProductForecastResult:
        return _product_surface_module().product_forecast(self, request)

    def log_decision(self, request: dict[str, Any]) -> DecisionLogResult:
        return _decision_memory_surface_module().log_decision(self, request)

    def list_decisions(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
        page_size: int | None = None,
        with_outcome_only: bool | None = None,
    ) -> DecisionListResult:
        return _decision_memory_surface_module().list_decisions(
            self,
            page=page,
            limit=limit,
            page_size=page_size,
            with_outcome_only=with_outcome_only,
        )

    def get_decision(self, decision_id: str) -> DecisionLogResult:
        return _decision_memory_surface_module().get_decision(self, decision_id)

    def record_outcome(
        self,
        decision_id: str,
        *,
        actual_outcome: float,
        outcome_notes: str | None = None,
    ) -> DecisionLogResult:
        return _decision_memory_surface_module().record_outcome(
            self,
            decision_id,
            actual_outcome=actual_outcome,
            outcome_notes=outcome_notes,
        )

    def execute_decision(
        self,
        decision_id: str,
        *,
        webhook_url: str,
        timeout_seconds: float = 10.0,
        force: bool = False,
        override_safety: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionReceiptResult:
        return _decision_memory_surface_module().execute_decision(
            self,
            decision_id,
            webhook_url=webhook_url,
            timeout_seconds=timeout_seconds,
            force=force,
            override_safety=override_safety,
            metadata=metadata,
        )

    def delete_decision(self, decision_id: str) -> dict[str, Any]:
        return _decision_memory_surface_module().delete_decision(self, decision_id)

    def register_trigger(
        self,
        *,
        name: str,
        condition: dict[str, Any],
        simulation_template: dict[str, Any],
        webhook_url: str | None = None,
        execution_webhook_url: str | None = None,
        auto_execute: bool = False,
        description: str | None = None,
    ) -> TriggerSummaryResult:
        return _trigger_surface_module().register_trigger(
            self,
            name=name,
            condition=condition,
            simulation_template=simulation_template,
            webhook_url=webhook_url,
            execution_webhook_url=execution_webhook_url,
            auto_execute=auto_execute,
            description=description,
        )

    def list_triggers(
        self,
        *,
        status: str = "all",
        page: int | None = None,
        limit: int | None = None,
    ) -> TriggerListResult:
        return _trigger_surface_module().list_triggers(
            self,
            status=status,
            page=page,
            limit=limit,
        )

    def fire_trigger(
        self,
        trigger_id: str,
        *,
        force: bool = False,
    ) -> TriggerFireResult:
        return _trigger_surface_module().fire_trigger(self, trigger_id, force=force)

    def pause_trigger(
        self,
        trigger_id: str,
        *,
        paused: bool = True,
    ) -> TriggerPauseResult:
        return _trigger_surface_module().pause_trigger(self, trigger_id, paused=paused)

    def delete_trigger(self, trigger_id: str) -> TriggerDeleteResult:
        return _trigger_surface_module().delete_trigger(self, trigger_id)

    def list_models(self) -> LLMModelListResult:
        return _llm_surface_module().list_models(self)

    def tokenize(self, text: str, *, model: str = "text.tokenizer") -> TokenizeResult:
        return _llm_surface_module().tokenize(self, text, model=model)

    def count_tokens(
        self,
        text: str,
        *,
        model: str = "text.tokenizer",
    ) -> CountTokensResult:
        return _llm_surface_module().count_tokens(self, text, model=model)

    def resolve_artifact_bridge(
        self,
        *,
        repo_id: str,
        filename: str,
        revision: str | None = None,
        local_files_only: bool = True,
    ) -> ArtifactBridgeResolveResult:
        return _llm_surface_module().resolve_artifact_bridge(
            self,
            repo_id=repo_id,
            filename=filename,
            revision=revision,
            local_files_only=local_files_only,
        )

    def chat_completions(
        self,
        messages: list[dict[str, str]],
        *,
        model: str = "text.tokenizer",
    ) -> ChatCompletionsResult:
        return _llm_surface_module().chat_completions(self, messages, model=model)

    def stream_chat_completions(
        self,
        messages: list[dict[str, str]],
        *,
        model: str = "text.tokenizer",
    ) -> Iterator[ChatCompletionsStreamChunkResult]:
        return _llm_surface_module().stream_chat_completions(self, messages, model=model)

    def responses(
        self,
        input_value: str | list[str],
        *,
        model: str = "text.tokenizer",
        dimensions: int = 64,
    ) -> ResponsesResult:
        return _llm_surface_module().responses(
            self,
            input_value,
            model=model,
            dimensions=dimensions,
        )

    def stream_responses(
        self,
        input_value: str | list[str],
        *,
        model: str = "text.tokenizer",
        dimensions: int = 64,
    ) -> Iterator[ResponseStreamEventResult]:
        return _llm_surface_module().stream_responses(
            self,
            input_value,
            model=model,
            dimensions=dimensions,
        )

    def embeddings(
        self,
        input_value: str | list[str],
        *,
        model: str = "text.hash_embedding_v1",
        dimensions: int = 64,
    ) -> EmbeddingsResult:
        return _llm_surface_module().embeddings(
            self,
            input_value,
            model=model,
            dimensions=dimensions,
        )

    def embedding_similarity(
        self,
        left: list[float],
        right: list[float],
        *,
        model: str = "embeddings.cosine_similarity",
    ) -> EmbeddingSimilarityResult:
        return _llm_surface_module().embedding_similarity(
            self,
            left,
            right,
            model=model,
        )

    def rerank(
        self,
        query_embedding: list[float],
        documents: list[dict[str, Any]],
        *,
        model: str = "embeddings.cosine_similarity",
        top_n: int | None = None,
    ) -> RerankResponseResult:
        return _llm_surface_module().rerank(
            self,
            query_embedding,
            documents,
            model=model,
            top_n=top_n,
        )

    def get_contract(self) -> PlatformContractResult:
        return _contract_surface_module().get_contract(self)

    def list_capability_providers(self) -> list[CapabilityProviderResult]:
        return _capability_plane_surface_module().list_capability_providers(self)

    def get_capability_provider(self, provider_id: str) -> CapabilityProviderResult:
        return _capability_plane_surface_module().get_capability_provider(self, provider_id)

    def list_capability_bindings(
        self,
        *,
        provider_id: str | None = None,
        scope: str | None = None,
    ) -> list[CapabilityBindingResult]:
        return _capability_plane_surface_module().list_capability_bindings(
            self,
            provider_id=provider_id,
            scope=scope,
        )

    def create_capability_binding(self, request: dict[str, Any]) -> CapabilityBindingResult:
        return _capability_plane_surface_module().create_capability_binding(self, request)

    def get_capability_binding(self, binding_id: str) -> CapabilityBindingResult:
        return _capability_plane_surface_module().get_capability_binding(self, binding_id)

    def update_capability_binding(
        self,
        binding_id: str,
        request: dict[str, Any],
    ) -> CapabilityBindingResult:
        return _capability_plane_surface_module().update_capability_binding(
            self,
            binding_id,
            request,
        )

    def delete_capability_binding(self, binding_id: str) -> None:
        _capability_plane_surface_module().delete_capability_binding(self, binding_id)

    def preview_test_capability_binding(
        self,
        request: dict[str, Any],
    ) -> CapabilityBindingTestResult:
        return _capability_plane_surface_module().preview_test_capability_binding(self, request)

    def test_capability_binding(self, binding_id: str) -> CapabilityBindingTestResult:
        return _capability_plane_surface_module().test_capability_binding(self, binding_id)

    def preview_discover_capability_binding(
        self,
        request: dict[str, Any],
    ) -> CapabilityDiscoverResult:
        return _capability_plane_surface_module().preview_discover_capability_binding(
            self,
            request,
        )

    def discover_capability_binding(self, binding_id: str) -> CapabilityDiscoverResult:
        return _capability_plane_surface_module().discover_capability_binding(self, binding_id)

    def start_capability_authorization(
        self,
        binding_id: str,
        request: dict[str, Any],
    ) -> CapabilityAuthorizationStartResult:
        return _capability_plane_surface_module().start_capability_authorization(
            self,
            binding_id,
            request,
        )

    def complete_capability_authorization(
        self,
        binding_id: str,
        request: dict[str, Any],
    ) -> CapabilityAuthorizationCompleteResult:
        return _capability_plane_surface_module().complete_capability_authorization(
            self,
            binding_id,
            request,
        )

    def list_capabilities(
        self,
        *,
        kinds: list[str] | tuple[str, ...] | None = None,
        provider_ids: list[str] | tuple[str, ...] | None = None,
        binding_ids: list[str] | tuple[str, ...] | None = None,
    ) -> list[CapabilityCatalogEntryResult]:
        return _capability_plane_surface_module().list_capabilities(
            self,
            kinds=kinds,
            provider_ids=provider_ids,
            binding_ids=binding_ids,
        )

    def get_capability(
        self,
        capability_id: str,
        *,
        include_instruction: bool = False,
    ) -> CapabilityCatalogEntryResult:
        return _capability_plane_surface_module().get_capability(
            self,
            capability_id,
            include_instruction=include_instruction,
        )

    def route_capabilities(self, request: dict[str, Any]) -> CapabilityRoutePlanResult:
        return _capability_plane_surface_module().route_capabilities(self, request)

    def execute_capability(self, request: dict[str, Any]) -> CapabilityExecutionResult:
        return _capability_plane_surface_module().execute_capability(self, request)

    def record_capability_outcome(
        self,
        request: dict[str, Any],
    ) -> CapabilityOutcomeRecordResult:
        return _capability_plane_surface_module().record_capability_outcome(self, request)

    def list_skills(self) -> list[CapabilityCatalogEntryResult]:
        return _capability_plane_surface_module().list_skills(self)

    def enable_skill(
        self,
        *,
        skill_name: str,
        instruction: str,
        description: str | None = None,
        tags: list[str] | None = None,
        artifact_affinities: list[str] | None = None,
        execution_owner: str = "client_managed",
    ) -> CapabilityDiscoverResult:
        return _capability_plane_surface_module().enable_skill(
            self,
            skill_name=skill_name,
            instruction=instruction,
            description=description,
            tags=tags,
            artifact_affinities=artifact_affinities,
            execution_owner=execution_owner,
        )

    def disable_skill(self, binding_id: str) -> None:
        _capability_plane_surface_module().disable_skill(self, binding_id)

    def list_mcp_providers(self) -> list[CapabilityProviderResult]:
        return _capability_plane_surface_module().list_mcp_providers(self)

    def get_runtime_manifest(self) -> RuntimeManifestResult:
        return _contract_surface_module().get_runtime_manifest(self)

    def get_runtime_modules(self) -> RuntimeAdminModulesResult:
        return _contract_surface_module().get_runtime_modules(self)

    def get_runtime_benchmarks(self) -> RuntimeAdminBenchmarksResult:
        return _contract_surface_module().get_runtime_benchmarks(self)

    def get_runtime_release_validation(self) -> RuntimeReleaseValidationResult:
        return _contract_surface_module().get_runtime_release_validation(self)

    def verify(self, request: dict[str, Any] | None = None, **kwargs: Any) -> VerifyResult:
        return _query_surface_module().verify(self, request, **kwargs)

    def register_source(
        self,
        source: dict[str, Any] | None = None,
        *,
        description: str | None = None,
        **kwargs: Any,
    ) -> SourceRegistrationResult:
        return _source_surface_module().register_source(
            self,
            source,
            description=description,
            **kwargs,
        )

    def refresh_source(self, dataset_id: str) -> SourceRegistrationResult:
        return _source_surface_module().refresh_source(self, dataset_id)

    def create_agent_run(
        self,
        *,
        task: str,
        context: dict[str, Any] | None = None,
        tools: list[str] | None = None,
        max_steps: int = 10,
        output_format: str = "text",
        approval_mode: str = "auto",
        start_paused: bool = False,
    ) -> AgentRunResult:
        return _agent_run_surface_module().create_agent_run(
            self,
            task=task,
            context=context,
            tools=tools,
            max_steps=max_steps,
            output_format=output_format,
            approval_mode=approval_mode,
            start_paused=start_paused,
        )

    def get_agent_run(self, run_id: str) -> AgentRunResult:
        return _agent_run_surface_module().get_agent_run(self, run_id)

    def list_agent_runs(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        status: str | None = None,
        request_hash: str | None = None,
        policy_snapshot_id: str | None = None,
        schema_snapshot_id: str | None = None,
    ) -> AgentRunListResult:
        return _agent_run_surface_module().list_agent_runs(
            self,
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
        )

    def get_agent_run_events(
        self,
        run_id: str,
        *,
        limit: int = 1000,
    ) -> AgentRunEventsResult:
        return _agent_run_surface_module().get_agent_run_events(self, run_id, limit=limit)

    def stream_agent_run_events(
        self,
        run_id: str,
        *,
        limit: int = 1000,
    ) -> Iterator[AgentRunStreamEventResult]:
        return _agent_run_surface_module().stream_agent_run_events(self, run_id, limit=limit)

    def resume_agent_run(self, run_id: str) -> AgentRunResult:
        return _agent_run_surface_module().resume_agent_run(self, run_id)

    def cancel_agent_run(self, run_id: str) -> AgentRunResult:
        return _agent_run_surface_module().cancel_agent_run(self, run_id)

    def approve_agent_run(self, run_id: str) -> AgentRunResult:
        return _agent_run_surface_module().approve_agent_run(self, run_id)

    def list_agent_run_checkpoints(self, run_id: str) -> AgentRunCheckpointsResult:
        return _agent_run_surface_module().list_agent_run_checkpoints(self, run_id)

    def query_agent_run_checkpoints(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        status: str | None = None,
        request_hash: str | None = None,
        policy_snapshot_id: str | None = None,
        schema_snapshot_id: str | None = None,
        run_id: str | None = None,
        checkpoint_id: str | None = None,
    ) -> AgentRunCheckpointListResponseResult:
        return _agent_run_surface_module().query_agent_run_checkpoints(
            self,
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            run_id=run_id,
            checkpoint_id=checkpoint_id,
        )

    def list_agent_run_mission_events(
        self,
        run_id: str,
        *,
        limit: int = 1000,
    ) -> AgentRunMissionEventsResult:
        return _agent_run_surface_module().list_agent_run_mission_events(
            self,
            run_id,
            limit=limit,
        )

    def query_agent_run_mission_events(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        status: str | None = None,
        request_hash: str | None = None,
        policy_snapshot_id: str | None = None,
        schema_snapshot_id: str | None = None,
        run_id: str | None = None,
        event_type: str | None = None,
    ) -> AgentRunMissionEventListResponseResult:
        return _agent_run_surface_module().query_agent_run_mission_events(
            self,
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            run_id=run_id,
            event_type=event_type,
        )

    def list_agent_run_telemetry(
        self,
        run_id: str,
        *,
        limit: int = 1000,
    ) -> AgentRunTelemetryResult:
        return _agent_run_surface_module().list_agent_run_telemetry(
            self,
            run_id,
            limit=limit,
        )

    def query_agent_run_telemetry(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        status: str | None = None,
        request_hash: str | None = None,
        policy_snapshot_id: str | None = None,
        schema_snapshot_id: str | None = None,
        run_id: str | None = None,
        telemetry_kind: str | None = None,
        module_name: str | None = None,
    ) -> AgentRunTelemetryListResult:
        return _agent_run_surface_module().query_agent_run_telemetry(
            self,
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            run_id=run_id,
            telemetry_kind=telemetry_kind,
            module_name=module_name,
        )

    def replay_agent_run(
        self,
        run_id: str,
        *,
        checkpoint_id: str | None = None,
    ) -> AgentRunReplayResult:
        return _agent_run_surface_module().replay_agent_run(
            self,
            run_id,
            checkpoint_id=checkpoint_id,
        )

    def fork_agent_run(
        self,
        run_id: str,
        *,
        checkpoint_id: str | None = None,
    ) -> AgentRunResult:
        return _agent_run_surface_module().fork_agent_run(
            self,
            run_id,
            checkpoint_id=checkpoint_id,
        )

    def create_connector(
        self,
        *,
        name: str,
        connector_type: str,
        config: dict[str, Any] | None = None,
        description: str | None = None,
        visibility: str | None = None,
    ) -> ConnectorInfo:
        return _connector_surface_module().create_connector(
            self,
            name=name,
            connector_type=connector_type,
            config=config,
            description=description,
            visibility=visibility,
        )

    def list_connectors(
        self,
        *,
        page: int = 1,
        limit: int = 200,
    ) -> ConnectorListResult:
        return _connector_surface_module().list_connectors(self, page=page, limit=limit)

    def get_connector(self, connector_id: str) -> ConnectorInfo:
        return _connector_surface_module().get_connector(self, connector_id)

    def update_connector(
        self,
        connector_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        visibility: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> ConnectorInfo:
        return _connector_surface_module().update_connector(
            self,
            connector_id,
            name=name,
            description=description,
            visibility=visibility,
            config=config,
        )

    def iter_connectors(
        self,
        *,
        page: int = 1,
        limit: int = 200,
        max_items: int | None = None,
    ):
        yield from _connector_surface_module().iter_connectors(
            self,
            page=page,
            limit=limit,
            max_items=max_items,
        )

    def test_connector(self, connector_id: str) -> ConnectorTestInfo:
        return _connector_surface_module().test_connector(self, connector_id)

    def preview_test_connector(
        self,
        *,
        connector_type: str,
        config: dict[str, Any] | None = None,
    ) -> ConnectorTestInfo:
        return _connector_surface_module().preview_test_connector(
            self,
            connector_type=connector_type,
            config=config,
        )

    def browse_connector(self, connector_id: str) -> ConnectorBrowseResult:
        return _connector_surface_module().browse_connector(self, connector_id)

    def preview_browse_connector(
        self,
        *,
        connector_type: str,
        config: dict[str, Any] | None = None,
    ) -> ConnectorBrowseResult:
        return _connector_surface_module().preview_browse_connector(
            self,
            connector_type=connector_type,
            config=config,
        )

    def delete_connector(self, connector_id: str) -> None:
        _connector_surface_module().delete_connector(self, connector_id)

    def create_repository_snapshot(
        self,
        repository_id: str,
        request: dict[str, Any],
    ) -> RepositorySnapshotResult:
        return _repository_surface_module().create_repository_snapshot(self, repository_id, request)

    def get_repository_intelligence_capabilities(
        self,
    ) -> "RepositoryIntelligenceCapabilitiesResult":
        return _repository_surface_module().get_repository_intelligence_capabilities(self)

    def get_repository_snapshot(
        self,
        repository_id: str,
        snapshot_id: str,
    ) -> RepositorySnapshotResult:
        return _repository_surface_module().get_repository_snapshot(
            self,
            repository_id,
            snapshot_id,
        )

    def triage_repository(
        self,
        repository_id: str,
        request: dict[str, Any],
    ) -> RepositoryTriageResult:
        return _repository_surface_module().triage_repository(self, repository_id, request)

    def create_repository_decision_plan(
        self,
        repository_id: str,
        request: dict[str, Any],
    ) -> RepositoryDecisionPlanRevisionResult:
        return _repository_surface_module().create_repository_decision_plan(
            self,
            repository_id,
            request,
        )

    def query_repository_graph(
        self,
        repository_id: str,
        request: dict[str, Any],
    ) -> RepositoryGraphQueryResult:
        return _repository_surface_module().query_repository_graph(self, repository_id, request)

    def simulate_repository(
        self,
        repository_id: str,
        request: dict[str, Any],
    ) -> DecisionEnvelope:
        return _repository_surface_module().simulate_repository(self, repository_id, request)

    def apply_repository(
        self,
        repository_id: str,
        request: dict[str, Any],
    ) -> RepositoryApplyResult:
        return _repository_surface_module().apply_repository(self, repository_id, request)

    def connect_data(
        self,
        request: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> DatasetConnectResult:
        return _connector_surface_module().connect_data(self, request, **kwargs)

    def list_datasets(
        self,
        *,
        page: int = 1,
        limit: int = 200,
        search: str | None = None,
        status: str | None = None,
        source_name: str | None = None,
        compact: bool = False,
    ) -> DatasetListResult:
        return _connector_surface_module().list_datasets(
            self,
            page=page,
            limit=limit,
            search=search,
            status=status,
            source_name=source_name,
            compact=compact,
        )

    def iter_datasets(
        self,
        *,
        page: int = 1,
        limit: int = 200,
        max_items: int | None = None,
        search: str | None = None,
        status: str | None = None,
        source_name: str | None = None,
        compact: bool = False,
    ):
        yield from _connector_surface_module().iter_datasets(
            self,
            page=page,
            limit=limit,
            max_items=max_items,
            search=search,
            status=status,
            source_name=source_name,
            compact=compact,
        )

    def get_dataset(self, dataset_id: str) -> DatasetDetailResult:
        return _connector_surface_module().get_dataset(self, dataset_id)

    def get_dataset_summary(self, dataset_id: str) -> DatasetSummaryResult:
        return _connector_surface_module().get_dataset_summary(self, dataset_id)

    def refresh_dataset(self, dataset_id: str) -> DatasetConnectResult:
        return _connector_surface_module().refresh_dataset(self, dataset_id)

    def delete_dataset(self, dataset_id: str) -> DatasetDeleteResult:
        return _connector_surface_module().delete_dataset(self, dataset_id)

    def explain(self, request: dict[str, Any] | None = None, **kwargs: Any) -> ExplainResult:
        return _query_surface_module().explain(self, request, **kwargs)

    def recommend(self, actions: Any, **kwargs: Any) -> dict[str, Any]:
        return _simulation_surface_module().recommend(self, actions, **kwargs)

    def score(
        self, request: dict[str, Any], scoring_weights: dict[str, float] | None = None
    ) -> dict[str, Any]:
        return _simulation_surface_module().score(self, request, scoring_weights)

    def batch(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return _simulation_surface_module().batch(self, items)

    def compare(self, scenarios: Any, **kwargs: Any) -> dict[str, Any]:
        return _simulation_surface_module().compare(self, scenarios, **kwargs)

    # ─── Async Jobs ───────────────────────────────────────────────────────────

    def submit_job(
        self,
        request: dict[str, Any] | None = None,
        callback_url: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return _job_surface_module().submit_job(self, request, callback_url, **kwargs)

    def get_job(self, job_id: str) -> dict[str, Any]:
        return _job_surface_module().get_job(self, job_id)

    def get_job_result(self, job_id: str) -> dict[str, Any]:
        return _job_surface_module().get_job_result(self, job_id)

    def list_jobs(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        status: str | None = None,
    ) -> dict[str, Any]:
        return _job_surface_module().list_jobs(self, page=page, limit=limit, status=status)

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        return _job_surface_module().cancel_job(self, job_id)

    def test_webhook_delivery(self, callback_url: str) -> dict[str, Any]:
        return _job_surface_module().test_webhook_delivery(self, callback_url)

    def poll_job(
        self, job_id: str, timeout: float = 300.0, poll_interval: float = 2.0
    ) -> dict[str, Any]:
        return _job_surface_module().poll_job(self, job_id, timeout, poll_interval)

    # ─── Deployment Control Plane ────────────────────────────────────────────

    def list_deployment_regions(self) -> DeploymentRegionsResult:
        return _deployment_surface_module().list_deployment_regions(self)

    def get_deployment(self) -> DeploymentResult | None:
        return _deployment_surface_module().get_deployment(self)

    def create_deployment(
        self,
        *,
        provider: str = "algenta_shared",
        region: str = "algenta-shared",
        config: dict[str, Any] | None = None,
        billing_markup_pct: float = 20.0,
    ) -> DeploymentResult:
        return _deployment_surface_module().create_deployment(
            self,
            provider=provider,
            region=region,
            config=config,
            billing_markup_pct=billing_markup_pct,
        )

    def delete_deployment(self, deployment_id: str) -> DeploymentDeleteResult:
        return _deployment_surface_module().delete_deployment(self, deployment_id)

    def get_deployment_cost(self, deployment_id: str) -> DeploymentCostResult:
        return _deployment_surface_module().get_deployment_cost(self, deployment_id)

    # ─── Account Endpoints ────────────────────────────────────────────────────

    def me(self) -> MeResult:
        return _account_surface_module().me(self)

    def update_me(
        self,
        *,
        name: str | None = None,
        org_name: str | None = None,
    ) -> Any:
        return _account_surface_module().update_me(self, name=name, org_name=org_name)

    def usage(self) -> UsageInfo:
        return _account_surface_module().usage(self)

    def limits(self) -> dict[str, Any]:
        return _account_surface_module().limits(self)

    def list_api_keys(self) -> list[APIKeyInfo]:
        return _account_surface_module().list_api_keys(self)

    def create_api_key(
        self,
        label: str | None = None,
        *,
        name: str | None = None,
        expires_at: datetime | str | None = None,
        device_limit: int | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"name": name, "expires_at": expires_at}
        if device_limit is not None:
            kwargs["device_limit"] = device_limit
        return _account_surface_module().create_api_key(self, label, **kwargs)

    def revoke_api_key(self, key_id: str) -> dict[str, Any]:
        return _account_surface_module().revoke_api_key(self, key_id)

    def get_billing_info(self) -> BillingInfoResult:
        return _control_plane_surface_module().get_billing_info(self)

    def create_billing_checkout(
        self,
        *,
        plan: str | None = None,
    ) -> BillingSessionResult:
        return _control_plane_surface_module().create_billing_checkout(self, plan=plan)

    def create_billing_portal(self) -> BillingSessionResult:
        return _control_plane_surface_module().create_billing_portal(self)

    def refresh_credits(
        self,
        *,
        device_id: str,
        billing_period: str,
        credits_used: int = 0,
    ) -> CreditRefreshResult:
        return _control_plane_surface_module().refresh_credits(
            self,
            device_id=device_id,
            billing_period=billing_period,
            credits_used=credits_used,
        )

    def ingest_metering_events(
        self,
        *,
        device_id: str,
        events: list[dict[str, Any]],
    ) -> MeteringBatchResult:
        return _control_plane_surface_module().ingest_metering_events(
            self,
            device_id=device_id,
            events=events,
        )

    def list_team_members(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
    ) -> TeamListResult:
        return _control_plane_surface_module().list_team_members(
            self,
            page=page,
            limit=limit,
        )

    def invite_team_member(
        self,
        *,
        email: str,
        role: str = "member",
    ) -> TeamInviteResult:
        return _control_plane_surface_module().invite_team_member(self, email=email, role=role)

    def update_team_member_role(
        self,
        user_id: str,
        *,
        role: str,
    ) -> TeamRoleUpdateResult:
        return _control_plane_surface_module().update_team_member_role(
            self,
            user_id,
            role=role,
        )

    def remove_team_member(self, user_id: str) -> TeamRemoveResult:
        return _control_plane_surface_module().remove_team_member(self, user_id)

    def get_audit_logs(
        self,
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
    ) -> AuditLogResult:
        return _control_plane_surface_module().get_audit_logs(
            self,
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
        )

    def get_audit_log_artifacts(
        self,
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
        return _control_plane_surface_module().get_audit_log_artifacts(
            self,
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
        )

    def get_execution_policy(self) -> ExecutionPolicyResult:
        return _control_plane_surface_module().get_execution_policy(self)

    def list_execution_policy_snapshots(self) -> ExecutionPolicySnapshotListResult:
        return _control_plane_surface_module().list_execution_policy_snapshots(self)

    def list_devices(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
    ) -> DeviceListResult:
        return _control_plane_surface_module().list_devices(
            self,
            page=page,
            limit=limit,
        )

    def revoke_device(self, registration_id: str) -> DeviceRevokeResult:
        return _control_plane_surface_module().revoke_device(self, registration_id)

    def update_execution_policy(
        self,
        *,
        min_confidence: float | None = None,
        risk_floor: float | None = None,
        require_calibration: bool | None = None,
        allow_reexecution: bool | None = None,
    ) -> ExecutionPolicyResult:
        return _control_plane_surface_module().update_execution_policy(
            self,
            min_confidence=min_confidence,
            risk_floor=risk_floor,
            require_calibration=require_calibration,
            allow_reexecution=allow_reexecution,
        )

    def distributions(self) -> DistributionListResult:
        return _account_surface_module().distributions(self)

    def templates(self) -> TemplateListResult:
        return _account_surface_module().templates(self)

    def health(self) -> dict[str, Any]:
        return _account_surface_module().health(self)

    def version(self) -> dict[str, Any]:
        return _account_surface_module().version(self)


class AlgentaClient(DecisionEngineClient):
    """Preferred public sync client name for the Algenta API."""
