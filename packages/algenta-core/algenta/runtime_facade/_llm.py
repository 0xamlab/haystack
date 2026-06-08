"""_LLMMixin for the Runtime class.

Extracted from packages/algenta-core/algenta/runtime_facade.py during modularization.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator, Mapping
from functools import cache
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any

from algenta.privacy_profile import resolve_cloud_base_url
from algenta.runtime_errors import RuntimeConfigurationError

if TYPE_CHECKING:
    from types import ModuleType

    from algenta.runtime_model_account import (
        APIKeyCreatedOutput,
        APIKeyInfoOutput,
        UsageOutput,
    )
    from algenta.runtime_model_agent_runs import (
        AgentRunCheckpointListResponseOutput,
        AgentRunCheckpointsOutput,
        AgentRunEventsOutput,
        AgentRunListOutput,
        AgentRunMissionEventListResponseOutput,
        AgentRunMissionEventsOutput,
        AgentRunOutput,
        AgentRunReplayOutput,
        AgentRunStreamEventOutput,
        AgentRunTelemetryListOutput,
        AgentRunTelemetryOutput,
    )
    from algenta.runtime_model_contract import PlatformContractOutput
    from algenta.runtime_model_capability_plane import (
        CapabilityAuthorizationCompleteOutput,
        CapabilityAuthorizationStartOutput,
        CapabilityBindingOutput,
        CapabilityBindingTestOutput,
        CapabilityCatalogEntryOutput,
        CapabilityDiscoverOutput,
        CapabilityExecutionOutput,
        CapabilityOutcomeRecordOutput,
        CapabilityProviderOutput,
        CapabilityRoutePlanOutput,
    )
    from algenta.runtime_model_control_plane import (
        AuditLogOutput,
        BillingInfoOutput,
        BillingSessionOutput,
        CreditRefreshOutput,
        DeviceListOutput,
        DeviceRevokeOutput,
        DistributionListOutput,
        ExecutionPolicyOutput,
        ExecutionPolicySnapshotListOutput,
        MeteringBatchOutput,
        TeamListOutput,
        TemplateListOutput,
    )
    from algenta.runtime_model_decision_envelope import DecisionEnvelopeOutput
    from algenta.runtime_model_decision_memory import (
        DecisionListOutput,
        DecisionLogOutput,
        ExecutionReceiptOutput,
    )
    from algenta.runtime_model_decision_plan import DecisionPlanOutput
    from algenta.runtime_model_deployments import (
        DeploymentCostOutput,
        DeploymentDeleteOutput,
        DeploymentOutput,
        DeploymentRegionsOutput,
    )
    from algenta.runtime_model_import_preview import (
        ImportBundlePreview,
        ImportPreview,
    )
    from algenta.runtime_model_jobs import (
        JobListOutput,
        JobStatusOutput,
        JobSubmitOutput,
        WebhookTestOutput,
    )
    from algenta.runtime_model_llm import (
        ArtifactBridgeResolveOutput,
        ChatCompletionsOutput,
        ChatCompletionsStreamChunkOutput,
        CountTokensOutput,
        EmbeddingSimilarityOutput,
        EmbeddingsOutput,
        LLMModelListOutput,
        RerankResponseOutput,
        ResponsesOutput,
        ResponseStreamEventOutput,
        TokenizeOutput,
    )
    from algenta.runtime_model_manifest import (
        RuntimeAdminBenchmarksOutput,
        RuntimeAdminModulesOutput,
        RuntimeManifestOutput,
        RuntimeReleaseValidationOutput,
    )
    from algenta.runtime_model_products import (
        ProductAgentRunOutput,
        ProductDecisionOutput,
        ProductForecastOutput,
        ProductOptimizeOutput,
        ProductRetrieveOutput,
    )
    from algenta.runtime_model_query_metadata import (
        QueryBatchOutput,
        QuerySqlReportOutput,
        QueryWithMetadataOutput,
    )
    from algenta.runtime_model_query_output import QueryOutput
    from algenta.runtime_model_repository_intelligence import (
        RepositoryApplyOutput,
        RepositoryGraphQueryOutput,
        RepositoryDecisionPlanRevisionOutput,
        RepositorySnapshotOutput,
        RepositoryTriageOutput,
    )
    from algenta.runtime_model_resolve_output import ResolveOutput
    from algenta.runtime_model_resolved_plan import ResolvedPlan
    from algenta.runtime_model_source_registration import SourceRegistration
    from algenta.runtime_model_triggers import (
        TriggerDeleteOutput,
        TriggerFireOutput,
        TriggerListOutput,
        TriggerPauseOutput,
        TriggerSummaryOutput,
    )
    from algenta.runtime_model_verify_output import VerifyOutput

LocalSourceInput = str | Path | list[dict[str, Any]] | Mapping[str, Any]

# Lazy facade-routed wrappers — test monkey-patches on
# `algenta.runtime_facade._runtime_X_module` propagate into mixin method
# bodies because each call re-reads the attribute from the facade.
def _runtime_execution_surface_module():
    from algenta import runtime_facade as _facade
    return _facade._runtime_execution_surface_module()


def _runtime_registration_surface_module():
    from algenta import runtime_facade as _facade
    return _facade._runtime_registration_surface_module()


def _runtime_model_source_registration_module():
    from algenta import runtime_facade as _facade
    return _facade._runtime_model_source_registration_module()


def _runtime_local_limits_module():
    from algenta import runtime_facade as _facade
    return _facade._runtime_local_limits_module()


def _runtime_connectors_module():
    from algenta import runtime_facade as _facade
    return _facade._runtime_connectors_module()


def _runtime_capability_plane_module():
    from algenta import runtime_facade as _facade
    return _facade._runtime_capability_plane_module()


class _LLMMixin:
    def list_models(self) -> LLMModelListOutput:
        return _runtime_execution_surface_module().llm_models_runtime_request(self)

    def resolve_artifact_bridge(
        self,
        *,
        repo_id: str,
        filename: str,
        revision: str | None = None,
        local_files_only: bool = True,
    ) -> ArtifactBridgeResolveOutput:
        return _runtime_execution_surface_module().resolve_artifact_bridge_runtime_request(
            self,
            repo_id=repo_id,
            filename=filename,
            revision=revision,
            local_files_only=local_files_only,
        )

    def tokenize(self, text: str, *, model: str = "text.tokenizer") -> TokenizeOutput:
        return _runtime_execution_surface_module().tokenize_runtime_request(
            self,
            text,
            model=model,
        )

    def count_tokens(
        self,
        text: str,
        *,
        model: str = "text.tokenizer",
    ) -> CountTokensOutput:
        return _runtime_execution_surface_module().count_tokens_runtime_request(
            self,
            text,
            model=model,
        )

    def chat_completions(
        self,
        messages: list[dict[str, str]],
        *,
        model: str = "text.tokenizer",
    ) -> ChatCompletionsOutput:
        return _runtime_execution_surface_module().chat_completions_runtime_request(
            self,
            messages,
            model=model,
        )

    def stream_chat_completions(
        self,
        messages: list[dict[str, str]],
        *,
        model: str = "text.tokenizer",
    ) -> Iterator[ChatCompletionsStreamChunkOutput]:
        return _runtime_execution_surface_module().stream_chat_completions_runtime_request(
            self,
            messages,
            model=model,
        )

    def responses(
        self,
        input_value: str | list[str],
        *,
        model: str = "text.tokenizer",
        dimensions: int = 64,
    ) -> ResponsesOutput:
        return _runtime_execution_surface_module().responses_runtime_request(
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
    ) -> Iterator[ResponseStreamEventOutput]:
        return _runtime_execution_surface_module().stream_responses_runtime_request(
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
    ) -> EmbeddingsOutput:
        return _runtime_execution_surface_module().embeddings_runtime_request(
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
    ) -> EmbeddingSimilarityOutput:
        return _runtime_execution_surface_module().embedding_similarity_runtime_request(
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
    ) -> RerankResponseOutput:
        return _runtime_execution_surface_module().rerank_runtime_request(
            self,
            query_embedding,
            documents,
            model=model,
            top_n=top_n,
        )
