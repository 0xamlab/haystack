"""_DecisionsProductsMixin for the Runtime class.

Extracted from packages/algenta/algenta/runtime_facade.py during modularization.
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


class _DecisionsProductsMixin:
    def plan_decision(self, request: Mapping[str, Any]) -> DecisionPlanOutput:
        return _runtime_execution_surface_module().decision_plan_runtime_request(self, request)

    def product_decision(self, request: Mapping[str, Any]) -> ProductDecisionOutput:
        return _runtime_execution_surface_module().product_decision_runtime_request(self, request)

    def product_agent_run(self, request: Mapping[str, Any]) -> ProductAgentRunOutput:
        return _runtime_execution_surface_module().product_agent_run_runtime_request(self, request)

    def product_optimize(self, request: Mapping[str, Any]) -> ProductOptimizeOutput:
        return _runtime_execution_surface_module().product_optimize_runtime_request(self, request)

    def product_retrieve(self, request: Mapping[str, Any]) -> ProductRetrieveOutput:
        return _runtime_execution_surface_module().product_retrieve_runtime_request(self, request)

    def product_forecast(self, request: Mapping[str, Any]) -> ProductForecastOutput:
        return _runtime_execution_surface_module().product_forecast_runtime_request(self, request)

    def log_decision(self, request: Mapping[str, Any]) -> DecisionLogOutput:
        return _runtime_execution_surface_module().log_decision_runtime_request(self, request)

    def list_decisions(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
        page_size: int | None = None,
        with_outcome_only: bool | None = None,
    ) -> DecisionListOutput:
        return _runtime_execution_surface_module().list_decisions_runtime_request(
            self,
            page=page,
            limit=limit,
            page_size=page_size,
            with_outcome_only=with_outcome_only,
        )

    def get_decision(self, decision_id: str) -> DecisionLogOutput:
        return _runtime_execution_surface_module().get_decision_runtime_request(self, decision_id)

    def record_outcome(
        self,
        decision_id: str,
        *,
        actual_outcome: float,
        outcome_notes: str | None = None,
    ) -> DecisionLogOutput:
        return _runtime_execution_surface_module().record_outcome_runtime_request(
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
    ) -> ExecutionReceiptOutput:
        return _runtime_execution_surface_module().execute_decision_runtime_request(
            self,
            decision_id,
            webhook_url=webhook_url,
            timeout_seconds=timeout_seconds,
            force=force,
            override_safety=override_safety,
            metadata=metadata,
        )

    def delete_decision(self, decision_id: str) -> dict[str, Any]:
        return _runtime_execution_surface_module().delete_decision_runtime_request(
            self,
            decision_id,
        )
