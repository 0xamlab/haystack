"""
Async Algenta API client for use with asyncio.

Usage:
    import asyncio
    import os
    from decision_engine import AsyncAlgentaClient

    async def main():
        api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
        if not api_key:
            raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

        async with AsyncAlgentaClient(api_key=api_key) as client:
            result = await client.simulate(
                mode="auto",
                scenario={
                    "variables": {"revenue": {"low": 80000, "high": 200000}},
                    "objective": "maximize_net_value",
                },
            )
            print(result.recommended_action)

    asyncio.run(main())

This example is the Cloud Managed path. In `self_hosted` and `air_gapped`,
pass an explicit self-hosted `base_url` and use the API key provisioned by
your self-hosted operator deployment instead. Private profiles fail closed and
do not silently fall back to Algenta cloud.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import AsyncIterator
from datetime import datetime
from functools import cache
from typing import TYPE_CHECKING, Any

from .device_binding import (
    DEVICE_BINDING_TOKEN_HEADER,
    load_device_binding_token,
    store_device_binding_token,
)
from .device_headers import DEVICE_ID_HEADER, build_device_headers
from .lazy_http_client import LazyAsyncHttpClient
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
    return importlib.import_module("decision_engine.async_client_connector_surface")


@cache
def _repository_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_repository_surface")


@cache
def _transport_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_transport")


@cache
def _response_module() -> ModuleType:
    return importlib.import_module("decision_engine.transport_response")


@cache
def _query_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_query_surface")


@cache
def _contract_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_contract_surface")


@cache
def _simulation_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_simulation_surface")


@cache
def _source_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_source_surface")


@cache
def _job_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_job_surface")


@cache
def _product_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_product_surface")


@cache
def _deployment_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_deployment_surface")


@cache
def _account_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_account_surface")


@cache
def _control_plane_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_control_plane_surface")


@cache
def _llm_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_llm_surface")


@cache
def _agent_run_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_agent_run_surface")


@cache
def _decision_plan_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_decision_plan_surface")


@cache
def _decision_memory_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_decision_memory_surface")


@cache
def _trigger_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_trigger_surface")


@cache
def _capability_plane_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_capability_plane_surface")


class AsyncDecisionEngineClient:
    """
    Async HTTP client for the Algenta API.

    `AsyncAlgentaClient` is the preferred public alias.
    `AsyncDecisionEngineClient` remains available for backward compatibility.
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
            component="AsyncDecisionEngineClient",
        )
        resolved_key = (
            api_key or os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "")
        )
        if not resolved_key:
            raise ValueError(
                "API key required. Pass api_key= or set ALGENTA_API_KEY / DE_API_KEY environment variables.\n"
                + api_key_help_text(
                    component="AsyncDecisionEngineClient",
                    fallback_base_url=resolved_base_url,
                )
            )
        self._api_key = resolved_key
        self._base_url = resolved_base_url
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = LazyAsyncHttpClient(self._build_http_client)

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
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=self._timeout,
        )

    def _get_httpx_module(self) -> Any:
        return _get_httpx()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        return await _transport_module().request_with_retries(self, method, path, **kwargs)

    async def _request_response(self, method: str, path: str, **kwargs: Any) -> tuple[Any, Any]:
        return await _transport_module().request_with_retries_and_response(
            self,
            method,
            path,
            **kwargs,
        )

    def _handle_response(self, response: httpx.Response) -> Any:
        return _response_module().handle_response(response, auth_message="Auth failed")

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

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> AsyncDecisionEngineClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    async def simulate(self, **kwargs: Any) -> DecisionEnvelope:
        return await _simulation_surface_module().simulate(self, **kwargs)

    async def resolve(self, request: dict[str, Any] | None = None, **kwargs: Any) -> ResolveResult:
        return await _query_surface_module().resolve(self, request, **kwargs)

    async def query(self, request: dict[str, Any] | None = None, **kwargs: Any) -> QueryResult:
        return await _query_surface_module().query(self, request, **kwargs)

    async def query_with_metadata(
        self,
        request: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> QueryWithMetadataResult:
        return await _query_surface_module().query_with_metadata(self, request, **kwargs)

    async def query_batch(self, request: dict[str, Any]) -> QueryBatchResult:
        return await _query_surface_module().query_batch(self, request)

    async def query_sql_report(self, request: dict[str, Any]) -> QuerySqlReportResult:
        return await _query_surface_module().query_sql_report(self, request)

    async def plan_decision(self, request: dict[str, Any]) -> DecisionPlanResult:
        return await _decision_plan_surface_module().plan_decision(self, request)

    async def product_decision(self, request: dict[str, Any]) -> ProductDecisionResult:
        return await _product_surface_module().product_decision(self, request)

    async def product_agent_run(self, request: dict[str, Any]) -> ProductAgentRunResult:
        return await _product_surface_module().product_agent_run(self, request)

    async def product_optimize(self, request: dict[str, Any]) -> ProductOptimizeResult:
        return await _product_surface_module().product_optimize(self, request)

    async def product_retrieve(self, request: dict[str, Any]) -> ProductRetrieveResult:
        return await _product_surface_module().product_retrieve(self, request)

    async def product_forecast(self, request: dict[str, Any]) -> ProductForecastResult:
        return await _product_surface_module().product_forecast(self, request)

    async def log_decision(self, request: dict[str, Any]) -> DecisionLogResult:
        return await _decision_memory_surface_module().log_decision(self, request)

    async def list_decisions(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
        page_size: int | None = None,
        with_outcome_only: bool | None = None,
    ) -> DecisionListResult:
        return await _decision_memory_surface_module().list_decisions(
            self,
            page=page,
            limit=limit,
            page_size=page_size,
            with_outcome_only=with_outcome_only,
        )

    async def get_decision(self, decision_id: str) -> DecisionLogResult:
        return await _decision_memory_surface_module().get_decision(self, decision_id)

    async def record_outcome(
        self,
        decision_id: str,
        *,
        actual_outcome: float,
        outcome_notes: str | None = None,
    ) -> DecisionLogResult:
        return await _decision_memory_surface_module().record_outcome(
            self,
            decision_id,
            actual_outcome=actual_outcome,
            outcome_notes=outcome_notes,
        )

    async def execute_decision(
        self,
        decision_id: str,
        *,
        webhook_url: str,
        timeout_seconds: float = 10.0,
        force: bool = False,
        override_safety: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionReceiptResult:
        return await _decision_memory_surface_module().execute_decision(
            self,
            decision_id,
            webhook_url=webhook_url,
            timeout_seconds=timeout_seconds,
            force=force,
            override_safety=override_safety,
            metadata=metadata,
        )

    async def delete_decision(self, decision_id: str) -> dict[str, Any]:
        return await _decision_memory_surface_module().delete_decision(self, decision_id)

    async def register_trigger(
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
        return await _trigger_surface_module().register_trigger(
            self,
            name=name,
            condition=condition,
            simulation_template=simulation_template,
            webhook_url=webhook_url,
            execution_webhook_url=execution_webhook_url,
            auto_execute=auto_execute,
            description=description,
        )

    async def list_triggers(
        self,
        *,
        status: str = "all",
        page: int | None = None,
        limit: int | None = None,
    ) -> TriggerListResult:
        return await _trigger_surface_module().list_triggers(
            self,
            status=status,
            page=page,
            limit=limit,
        )

    async def fire_trigger(
        self,
        trigger_id: str,
        *,
        force: bool = False,
    ) -> TriggerFireResult:
        return await _trigger_surface_module().fire_trigger(self, trigger_id, force=force)

    async def pause_trigger(
        self,
        trigger_id: str,
        *,
        paused: bool = True,
    ) -> TriggerPauseResult:
        return await _trigger_surface_module().pause_trigger(self, trigger_id, paused=paused)

    async def delete_trigger(self, trigger_id: str) -> TriggerDeleteResult:
        return await _trigger_surface_module().delete_trigger(self, trigger_id)

    async def list_models(self) -> LLMModelListResult:
        return await _llm_surface_module().list_models(self)

    async def tokenize(
        self,
        text: str,
        *,
        model: str = "text.tokenizer",
    ) -> TokenizeResult:
        return await _llm_surface_module().tokenize(self, text, model=model)

    async def count_tokens(
        self,
        text: str,
        *,
        model: str = "text.tokenizer",
    ) -> CountTokensResult:
        return await _llm_surface_module().count_tokens(self, text, model=model)

    async def resolve_artifact_bridge(
        self,
        *,
        repo_id: str,
        filename: str,
        revision: str | None = None,
        local_files_only: bool = True,
    ) -> ArtifactBridgeResolveResult:
        return await _llm_surface_module().resolve_artifact_bridge(
            self,
            repo_id=repo_id,
            filename=filename,
            revision=revision,
            local_files_only=local_files_only,
        )

    async def chat_completions(
        self,
        messages: list[dict[str, str]],
        *,
        model: str = "text.tokenizer",
    ) -> ChatCompletionsResult:
        return await _llm_surface_module().chat_completions(self, messages, model=model)

    def stream_chat_completions(
        self,
        messages: list[dict[str, str]],
        *,
        model: str = "text.tokenizer",
    ) -> AsyncIterator[ChatCompletionsStreamChunkResult]:
        return _llm_surface_module().stream_chat_completions(self, messages, model=model)

    async def responses(
        self,
        input_value: str | list[str],
        *,
        model: str = "text.tokenizer",
        dimensions: int = 64,
    ) -> ResponsesResult:
        return await _llm_surface_module().responses(
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
    ) -> AsyncIterator[ResponseStreamEventResult]:
        return _llm_surface_module().stream_responses(
            self,
            input_value,
            model=model,
            dimensions=dimensions,
        )

    async def embeddings(
        self,
        input_value: str | list[str],
        *,
        model: str = "text.hash_embedding_v1",
        dimensions: int = 64,
    ) -> EmbeddingsResult:
        return await _llm_surface_module().embeddings(
            self,
            input_value,
            model=model,
            dimensions=dimensions,
        )

    async def embedding_similarity(
        self,
        left: list[float],
        right: list[float],
        *,
        model: str = "embeddings.cosine_similarity",
    ) -> EmbeddingSimilarityResult:
        return await _llm_surface_module().embedding_similarity(
            self,
            left,
            right,
            model=model,
        )

    async def rerank(
        self,
        query_embedding: list[float],
        documents: list[dict[str, Any]],
        *,
        model: str = "embeddings.cosine_similarity",
        top_n: int | None = None,
    ) -> RerankResponseResult:
        return await _llm_surface_module().rerank(
            self,
            query_embedding,
            documents,
            model=model,
            top_n=top_n,
        )

    async def get_contract(self) -> PlatformContractResult:
        return await _contract_surface_module().get_contract(self)

    async def list_capability_providers(self) -> list[CapabilityProviderResult]:
        return await _capability_plane_surface_module().list_capability_providers(self)

    async def get_capability_provider(self, provider_id: str) -> CapabilityProviderResult:
        return await _capability_plane_surface_module().get_capability_provider(self, provider_id)

    async def list_capability_bindings(
        self,
        *,
        provider_id: str | None = None,
        scope: str | None = None,
    ) -> list[CapabilityBindingResult]:
        return await _capability_plane_surface_module().list_capability_bindings(
            self,
            provider_id=provider_id,
            scope=scope,
        )

    async def create_capability_binding(self, request: dict[str, Any]) -> CapabilityBindingResult:
        return await _capability_plane_surface_module().create_capability_binding(self, request)

    async def get_capability_binding(self, binding_id: str) -> CapabilityBindingResult:
        return await _capability_plane_surface_module().get_capability_binding(self, binding_id)

    async def update_capability_binding(
        self,
        binding_id: str,
        request: dict[str, Any],
    ) -> CapabilityBindingResult:
        return await _capability_plane_surface_module().update_capability_binding(
            self,
            binding_id,
            request,
        )

    async def delete_capability_binding(self, binding_id: str) -> None:
        await _capability_plane_surface_module().delete_capability_binding(self, binding_id)

    async def preview_test_capability_binding(
        self,
        request: dict[str, Any],
    ) -> CapabilityBindingTestResult:
        return await _capability_plane_surface_module().preview_test_capability_binding(
            self,
            request,
        )

    async def test_capability_binding(self, binding_id: str) -> CapabilityBindingTestResult:
        return await _capability_plane_surface_module().test_capability_binding(self, binding_id)

    async def preview_discover_capability_binding(
        self,
        request: dict[str, Any],
    ) -> CapabilityDiscoverResult:
        return await _capability_plane_surface_module().preview_discover_capability_binding(
            self,
            request,
        )

    async def discover_capability_binding(self, binding_id: str) -> CapabilityDiscoverResult:
        return await _capability_plane_surface_module().discover_capability_binding(
            self,
            binding_id,
        )

    async def start_capability_authorization(
        self,
        binding_id: str,
        request: dict[str, Any],
    ) -> CapabilityAuthorizationStartResult:
        return await _capability_plane_surface_module().start_capability_authorization(
            self,
            binding_id,
            request,
        )

    async def complete_capability_authorization(
        self,
        binding_id: str,
        request: dict[str, Any],
    ) -> CapabilityAuthorizationCompleteResult:
        return await _capability_plane_surface_module().complete_capability_authorization(
            self,
            binding_id,
            request,
        )

    async def list_capabilities(
        self,
        *,
        kinds: list[str] | tuple[str, ...] | None = None,
        provider_ids: list[str] | tuple[str, ...] | None = None,
        binding_ids: list[str] | tuple[str, ...] | None = None,
    ) -> list[CapabilityCatalogEntryResult]:
        return await _capability_plane_surface_module().list_capabilities(
            self,
            kinds=kinds,
            provider_ids=provider_ids,
            binding_ids=binding_ids,
        )

    async def get_capability(
        self,
        capability_id: str,
        *,
        include_instruction: bool = False,
    ) -> CapabilityCatalogEntryResult:
        return await _capability_plane_surface_module().get_capability(
            self,
            capability_id,
            include_instruction=include_instruction,
        )

    async def route_capabilities(self, request: dict[str, Any]) -> CapabilityRoutePlanResult:
        return await _capability_plane_surface_module().route_capabilities(self, request)

    async def execute_capability(self, request: dict[str, Any]) -> CapabilityExecutionResult:
        return await _capability_plane_surface_module().execute_capability(self, request)

    async def record_capability_outcome(
        self,
        request: dict[str, Any],
    ) -> CapabilityOutcomeRecordResult:
        return await _capability_plane_surface_module().record_capability_outcome(self, request)

    async def list_skills(self) -> list[CapabilityCatalogEntryResult]:
        return await _capability_plane_surface_module().list_skills(self)

    async def enable_skill(
        self,
        *,
        skill_name: str,
        instruction: str,
        description: str | None = None,
        tags: list[str] | None = None,
        artifact_affinities: list[str] | None = None,
        execution_owner: str = "client_managed",
    ) -> CapabilityDiscoverResult:
        return await _capability_plane_surface_module().enable_skill(
            self,
            skill_name=skill_name,
            instruction=instruction,
            description=description,
            tags=tags,
            artifact_affinities=artifact_affinities,
            execution_owner=execution_owner,
        )

    async def disable_skill(self, binding_id: str) -> None:
        await _capability_plane_surface_module().disable_skill(self, binding_id)

    async def list_mcp_providers(self) -> list[CapabilityProviderResult]:
        return await _capability_plane_surface_module().list_mcp_providers(self)

    async def get_runtime_manifest(self) -> RuntimeManifestResult:
        return await _contract_surface_module().get_runtime_manifest(self)

    async def get_runtime_modules(self) -> RuntimeAdminModulesResult:
        return await _contract_surface_module().get_runtime_modules(self)

    async def get_runtime_benchmarks(self) -> RuntimeAdminBenchmarksResult:
        return await _contract_surface_module().get_runtime_benchmarks(self)

    async def get_runtime_release_validation(self) -> RuntimeReleaseValidationResult:
        return await _contract_surface_module().get_runtime_release_validation(self)

    async def verify(self, request: dict[str, Any] | None = None, **kwargs: Any) -> VerifyResult:
        return await _query_surface_module().verify(self, request, **kwargs)

    async def register_source(
        self,
        source: dict[str, Any] | None = None,
        *,
        description: str | None = None,
        **kwargs: Any,
    ) -> SourceRegistrationResult:
        return await _source_surface_module().register_source(
            self,
            source,
            description=description,
            **kwargs,
        )

    async def refresh_source(self, dataset_id: str) -> SourceRegistrationResult:
        return await _source_surface_module().refresh_source(self, dataset_id)

    async def create_agent_run(
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
        return await _agent_run_surface_module().create_agent_run(
            self,
            task=task,
            context=context,
            tools=tools,
            max_steps=max_steps,
            output_format=output_format,
            approval_mode=approval_mode,
            start_paused=start_paused,
        )

    async def get_agent_run(self, run_id: str) -> AgentRunResult:
        return await _agent_run_surface_module().get_agent_run(self, run_id)

    async def list_agent_runs(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        status: str | None = None,
        request_hash: str | None = None,
        policy_snapshot_id: str | None = None,
        schema_snapshot_id: str | None = None,
    ) -> AgentRunListResult:
        return await _agent_run_surface_module().list_agent_runs(
            self,
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
        )

    async def get_agent_run_events(
        self,
        run_id: str,
        *,
        limit: int = 1000,
    ) -> AgentRunEventsResult:
        return await _agent_run_surface_module().get_agent_run_events(self, run_id, limit=limit)

    def stream_agent_run_events(
        self,
        run_id: str,
        *,
        limit: int = 1000,
    ) -> AsyncIterator[AgentRunStreamEventResult]:
        return _agent_run_surface_module().stream_agent_run_events(self, run_id, limit=limit)

    async def resume_agent_run(self, run_id: str) -> AgentRunResult:
        return await _agent_run_surface_module().resume_agent_run(self, run_id)

    async def cancel_agent_run(self, run_id: str) -> AgentRunResult:
        return await _agent_run_surface_module().cancel_agent_run(self, run_id)

    async def approve_agent_run(self, run_id: str) -> AgentRunResult:
        return await _agent_run_surface_module().approve_agent_run(self, run_id)

    async def list_agent_run_checkpoints(self, run_id: str) -> AgentRunCheckpointsResult:
        return await _agent_run_surface_module().list_agent_run_checkpoints(self, run_id)

    async def query_agent_run_checkpoints(
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
        return await _agent_run_surface_module().query_agent_run_checkpoints(
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

    async def list_agent_run_mission_events(
        self,
        run_id: str,
        *,
        limit: int = 1000,
    ) -> AgentRunMissionEventsResult:
        return await _agent_run_surface_module().list_agent_run_mission_events(
            self,
            run_id,
            limit=limit,
        )

    async def query_agent_run_mission_events(
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
        return await _agent_run_surface_module().query_agent_run_mission_events(
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

    async def list_agent_run_telemetry(
        self,
        run_id: str,
        *,
        limit: int = 1000,
    ) -> AgentRunTelemetryResult:
        return await _agent_run_surface_module().list_agent_run_telemetry(
            self,
            run_id,
            limit=limit,
        )

    async def query_agent_run_telemetry(
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
        return await _agent_run_surface_module().query_agent_run_telemetry(
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

    async def replay_agent_run(
        self,
        run_id: str,
        *,
        checkpoint_id: str | None = None,
    ) -> AgentRunReplayResult:
        return await _agent_run_surface_module().replay_agent_run(
            self,
            run_id,
            checkpoint_id=checkpoint_id,
        )

    async def fork_agent_run(
        self,
        run_id: str,
        *,
        checkpoint_id: str | None = None,
    ) -> AgentRunResult:
        return await _agent_run_surface_module().fork_agent_run(
            self,
            run_id,
            checkpoint_id=checkpoint_id,
        )

    async def create_connector(
        self,
        *,
        name: str,
        connector_type: str,
        config: dict[str, Any] | None = None,
        description: str | None = None,
        visibility: str | None = None,
    ) -> ConnectorInfo:
        return await _connector_surface_module().create_connector(
            self,
            name=name,
            connector_type=connector_type,
            config=config,
            description=description,
            visibility=visibility,
        )

    async def list_connectors(
        self,
        *,
        page: int = 1,
        limit: int = 200,
    ) -> ConnectorListResult:
        return await _connector_surface_module().list_connectors(self, page=page, limit=limit)

    async def get_connector(self, connector_id: str) -> ConnectorInfo:
        return await _connector_surface_module().get_connector(self, connector_id)

    async def update_connector(
        self,
        connector_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        visibility: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> ConnectorInfo:
        return await _connector_surface_module().update_connector(
            self,
            connector_id,
            name=name,
            description=description,
            visibility=visibility,
            config=config,
        )

    async def iter_connectors(
        self,
        *,
        page: int = 1,
        limit: int = 200,
        max_items: int | None = None,
    ):
        async for connector in _connector_surface_module().iter_connectors(
            self,
            page=page,
            limit=limit,
            max_items=max_items,
        ):
            yield connector

    async def test_connector(self, connector_id: str) -> ConnectorTestInfo:
        return await _connector_surface_module().test_connector(self, connector_id)

    async def preview_test_connector(
        self,
        *,
        connector_type: str,
        config: dict[str, Any] | None = None,
    ) -> ConnectorTestInfo:
        return await _connector_surface_module().preview_test_connector(
            self,
            connector_type=connector_type,
            config=config,
        )

    async def browse_connector(self, connector_id: str) -> ConnectorBrowseResult:
        return await _connector_surface_module().browse_connector(self, connector_id)

    async def preview_browse_connector(
        self,
        *,
        connector_type: str,
        config: dict[str, Any] | None = None,
    ) -> ConnectorBrowseResult:
        return await _connector_surface_module().preview_browse_connector(
            self,
            connector_type=connector_type,
            config=config,
        )

    async def delete_connector(self, connector_id: str) -> None:
        await _connector_surface_module().delete_connector(self, connector_id)

    async def create_repository_snapshot(
        self,
        repository_id: str,
        request: dict[str, Any],
    ) -> RepositorySnapshotResult:
        return await _repository_surface_module().create_repository_snapshot(
            self,
            repository_id,
            request,
        )

    async def get_repository_intelligence_capabilities(
        self,
    ) -> "RepositoryIntelligenceCapabilitiesResult":
        return await _repository_surface_module().get_repository_intelligence_capabilities(self)

    async def get_repository_snapshot(
        self,
        repository_id: str,
        snapshot_id: str,
    ) -> RepositorySnapshotResult:
        return await _repository_surface_module().get_repository_snapshot(
            self,
            repository_id,
            snapshot_id,
        )

    async def triage_repository(
        self,
        repository_id: str,
        request: dict[str, Any],
    ) -> RepositoryTriageResult:
        return await _repository_surface_module().triage_repository(self, repository_id, request)

    async def create_repository_decision_plan(
        self,
        repository_id: str,
        request: dict[str, Any],
    ) -> RepositoryDecisionPlanRevisionResult:
        return await _repository_surface_module().create_repository_decision_plan(
            self,
            repository_id,
            request,
        )

    async def query_repository_graph(
        self,
        repository_id: str,
        request: dict[str, Any],
    ) -> RepositoryGraphQueryResult:
        return await _repository_surface_module().query_repository_graph(
            self,
            repository_id,
            request,
        )

    async def simulate_repository(
        self,
        repository_id: str,
        request: dict[str, Any],
    ) -> DecisionEnvelope:
        return await _repository_surface_module().simulate_repository(self, repository_id, request)

    async def apply_repository(
        self,
        repository_id: str,
        request: dict[str, Any],
    ) -> RepositoryApplyResult:
        return await _repository_surface_module().apply_repository(self, repository_id, request)

    async def connect_data(
        self,
        request: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> DatasetConnectResult:
        return await _connector_surface_module().connect_data(self, request, **kwargs)

    async def list_datasets(
        self,
        *,
        page: int = 1,
        limit: int = 200,
        search: str | None = None,
        status: str | None = None,
        source_name: str | None = None,
        compact: bool = False,
    ) -> DatasetListResult:
        return await _connector_surface_module().list_datasets(
            self,
            page=page,
            limit=limit,
            search=search,
            status=status,
            source_name=source_name,
            compact=compact,
        )

    async def iter_datasets(
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
        async for dataset in _connector_surface_module().iter_datasets(
            self,
            page=page,
            limit=limit,
            max_items=max_items,
            search=search,
            status=status,
            source_name=source_name,
            compact=compact,
        ):
            yield dataset

    async def get_dataset(self, dataset_id: str) -> DatasetDetailResult:
        return await _connector_surface_module().get_dataset(self, dataset_id)

    async def get_dataset_summary(self, dataset_id: str) -> DatasetSummaryResult:
        return await _connector_surface_module().get_dataset_summary(self, dataset_id)

    async def refresh_dataset(self, dataset_id: str) -> DatasetConnectResult:
        return await _connector_surface_module().refresh_dataset(self, dataset_id)

    async def delete_dataset(self, dataset_id: str) -> DatasetDeleteResult:
        return await _connector_surface_module().delete_dataset(self, dataset_id)

    async def explain(self, request: dict[str, Any] | None = None, **kwargs: Any) -> ExplainResult:
        return await _query_surface_module().explain(self, request, **kwargs)

    async def recommend(self, actions: Any, **kwargs: Any) -> dict[str, Any]:
        return await _simulation_surface_module().recommend(self, actions, **kwargs)

    async def score(
        self, request: dict[str, Any], scoring_weights: dict[str, float] | None = None
    ) -> dict[str, Any]:
        return await _simulation_surface_module().score(self, request, scoring_weights)

    async def batch(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return await _simulation_surface_module().batch(self, items)

    async def compare(self, scenarios: Any, **kwargs: Any) -> dict[str, Any]:
        return await _simulation_surface_module().compare(self, scenarios, **kwargs)

    async def submit_job(
        self,
        request: dict[str, Any] | None = None,
        callback_url: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return await _job_surface_module().submit_job(self, request, callback_url, **kwargs)

    async def get_job(self, job_id: str) -> dict[str, Any]:
        return await _job_surface_module().get_job(self, job_id)

    async def get_job_result(self, job_id: str) -> dict[str, Any]:
        return await _job_surface_module().get_job_result(self, job_id)

    async def list_jobs(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        status: str | None = None,
    ) -> dict[str, Any]:
        return await _job_surface_module().list_jobs(
            self,
            page=page,
            limit=limit,
            status=status,
        )

    async def cancel_job(self, job_id: str) -> dict[str, Any]:
        return await _job_surface_module().cancel_job(self, job_id)

    async def test_webhook_delivery(self, callback_url: str) -> dict[str, Any]:
        return await _job_surface_module().test_webhook_delivery(self, callback_url)

    async def poll_job(
        self, job_id: str, timeout: float = 300.0, poll_interval: float = 2.0
    ) -> dict[str, Any]:
        return await _job_surface_module().poll_job(self, job_id, timeout, poll_interval)

    async def list_deployment_regions(self) -> DeploymentRegionsResult:
        return await _deployment_surface_module().list_deployment_regions(self)

    async def get_deployment(self) -> DeploymentResult | None:
        return await _deployment_surface_module().get_deployment(self)

    async def create_deployment(
        self,
        *,
        provider: str = "algenta_shared",
        region: str = "algenta-shared",
        config: dict[str, Any] | None = None,
        billing_markup_pct: float = 20.0,
    ) -> DeploymentResult:
        return await _deployment_surface_module().create_deployment(
            self,
            provider=provider,
            region=region,
            config=config,
            billing_markup_pct=billing_markup_pct,
        )

    async def delete_deployment(self, deployment_id: str) -> DeploymentDeleteResult:
        return await _deployment_surface_module().delete_deployment(self, deployment_id)

    async def get_deployment_cost(self, deployment_id: str) -> DeploymentCostResult:
        return await _deployment_surface_module().get_deployment_cost(self, deployment_id)

    async def me(self) -> MeResult:
        return await _account_surface_module().me(self)

    async def update_me(
        self,
        *,
        name: str | None = None,
        org_name: str | None = None,
    ) -> Any:
        return await _account_surface_module().update_me(self, name=name, org_name=org_name)

    async def usage(self) -> UsageInfo:
        return await _account_surface_module().usage(self)

    async def limits(self) -> dict[str, Any]:
        return await _account_surface_module().limits(self)

    async def list_api_keys(self) -> list[APIKeyInfo]:
        return await _account_surface_module().list_api_keys(self)

    async def create_api_key(
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
        return await _account_surface_module().create_api_key(self, label, **kwargs)

    async def revoke_api_key(self, key_id: str) -> dict[str, Any]:
        return await _account_surface_module().revoke_api_key(self, key_id)

    async def get_billing_info(self) -> BillingInfoResult:
        return await _control_plane_surface_module().get_billing_info(self)

    async def create_billing_checkout(
        self,
        *,
        plan: str | None = None,
    ) -> BillingSessionResult:
        return await _control_plane_surface_module().create_billing_checkout(self, plan=plan)

    async def create_billing_portal(self) -> BillingSessionResult:
        return await _control_plane_surface_module().create_billing_portal(self)

    async def refresh_credits(
        self,
        *,
        device_id: str,
        billing_period: str,
        credits_used: int = 0,
    ) -> CreditRefreshResult:
        return await _control_plane_surface_module().refresh_credits(
            self,
            device_id=device_id,
            billing_period=billing_period,
            credits_used=credits_used,
        )

    async def ingest_metering_events(
        self,
        *,
        device_id: str,
        events: list[dict[str, Any]],
    ) -> MeteringBatchResult:
        return await _control_plane_surface_module().ingest_metering_events(
            self,
            device_id=device_id,
            events=events,
        )

    async def list_team_members(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
    ) -> TeamListResult:
        return await _control_plane_surface_module().list_team_members(
            self,
            page=page,
            limit=limit,
        )

    async def invite_team_member(
        self,
        *,
        email: str,
        role: str = "member",
    ) -> TeamInviteResult:
        return await _control_plane_surface_module().invite_team_member(
            self,
            email=email,
            role=role,
        )

    async def update_team_member_role(
        self,
        user_id: str,
        *,
        role: str,
    ) -> TeamRoleUpdateResult:
        return await _control_plane_surface_module().update_team_member_role(
            self,
            user_id,
            role=role,
        )

    async def remove_team_member(self, user_id: str) -> TeamRemoveResult:
        return await _control_plane_surface_module().remove_team_member(self, user_id)

    async def get_audit_logs(
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
        return await _control_plane_surface_module().get_audit_logs(
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

    async def get_audit_log_artifacts(
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
        return await _control_plane_surface_module().get_audit_log_artifacts(
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

    async def get_execution_policy(self) -> ExecutionPolicyResult:
        return await _control_plane_surface_module().get_execution_policy(self)

    async def list_execution_policy_snapshots(self) -> ExecutionPolicySnapshotListResult:
        return await _control_plane_surface_module().list_execution_policy_snapshots(self)

    async def list_devices(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
    ) -> DeviceListResult:
        return await _control_plane_surface_module().list_devices(
            self,
            page=page,
            limit=limit,
        )

    async def revoke_device(self, registration_id: str) -> DeviceRevokeResult:
        return await _control_plane_surface_module().revoke_device(self, registration_id)

    async def update_execution_policy(
        self,
        *,
        min_confidence: float | None = None,
        risk_floor: float | None = None,
        require_calibration: bool | None = None,
        allow_reexecution: bool | None = None,
    ) -> ExecutionPolicyResult:
        return await _control_plane_surface_module().update_execution_policy(
            self,
            min_confidence=min_confidence,
            risk_floor=risk_floor,
            require_calibration=require_calibration,
            allow_reexecution=allow_reexecution,
        )

    async def distributions(self) -> DistributionListResult:
        return await _account_surface_module().distributions(self)

    async def templates(self) -> TemplateListResult:
        return await _account_surface_module().templates(self)

    async def health(self) -> dict[str, Any]:
        return await _account_surface_module().health(self)

    async def version(self) -> dict[str, Any]:
        return await _account_surface_module().version(self)


class AsyncAlgentaClient(AsyncDecisionEngineClient):
    """Preferred public async client name for the Algenta API."""
