"""_RepositoryImportsMixin for the Runtime class.

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


def _runtime_repository_intelligence_module():
    from algenta import runtime_facade as _facade
    return _facade._runtime_repository_intelligence_module()


class _RepositoryImportsMixin:
    def register_repository_intelligence_backend(self, backend: Any) -> None:
        _runtime_repository_intelligence_module().register_repository_intelligence_backend(
            self,
            backend,
        )

    def create_repository_snapshot(
        self,
        repository_id: str,
        request: Mapping[str, Any],
    ) -> RepositorySnapshotOutput:
        return _runtime_execution_surface_module().create_repository_snapshot_runtime_request(
            self,
            repository_id,
            request,
        )

    def get_repository_intelligence_capabilities(
        self,
    ) -> "RepositoryIntelligenceCapabilitiesOutput":
        return _runtime_execution_surface_module().get_repository_intelligence_capabilities_runtime_request(
            self
        )

    def get_repository_snapshot(
        self,
        repository_id: str,
        snapshot_id: str,
    ) -> RepositorySnapshotOutput:
        return _runtime_execution_surface_module().get_repository_snapshot_runtime_request(
            self,
            repository_id,
            snapshot_id,
        )

    def triage_repository(
        self,
        repository_id: str,
        request: Mapping[str, Any],
    ) -> RepositoryTriageOutput:
        return _runtime_execution_surface_module().triage_repository_runtime_request(
            self,
            repository_id,
            request,
        )

    def create_repository_decision_plan(
        self,
        repository_id: str,
        request: Mapping[str, Any],
    ) -> RepositoryDecisionPlanRevisionOutput:
        return _runtime_execution_surface_module().create_repository_decision_plan_runtime_request(
            self,
            repository_id,
            request,
        )

    def query_repository_graph(
        self,
        repository_id: str,
        request: Mapping[str, Any],
    ) -> RepositoryGraphQueryOutput:
        return _runtime_execution_surface_module().query_repository_graph_runtime_request(
            self,
            repository_id,
            request,
        )

    def simulate_repository(
        self,
        repository_id: str,
        request: Mapping[str, Any],
    ) -> DecisionEnvelopeOutput:
        return _runtime_execution_surface_module().simulate_repository_runtime_request(
            self,
            repository_id,
            request,
        )

    def apply_repository(
        self,
        repository_id: str,
        request: Mapping[str, Any],
    ) -> RepositoryApplyOutput:
        return _runtime_execution_surface_module().apply_repository_runtime_request(
            self,
            repository_id,
            request,
        )

    def _source_registration_from_api(self, payload: Any) -> SourceRegistration:
        return _runtime_model_source_registration_module().SourceRegistration.from_api(payload)

    def import_preview(
        self,
        source: LocalSourceInput,
        *,
        name: str | None = None,
        description: str | None = None,
        source_ref: str | None = None,
    ) -> ImportPreview:
        return _runtime_registration_surface_module().build_runtime_import_preview(
            self,
            source,
            name=name,
            description=description,
            source_ref=source_ref,
        )

    def import_bundle_preview(
        self,
        sources: list[LocalSourceInput],
        *,
        names: list[str | None] | None = None,
        source_refs: list[str | None] | None = None,
        description: str | None = None,
    ) -> ImportBundlePreview:
        return _runtime_registration_surface_module().build_runtime_import_bundle_preview(
            self,
            sources,
            names=names,
            source_refs=source_refs,
            description=description,
        )
