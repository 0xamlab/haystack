"""_InternalHelpersMixin for the Runtime class.

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


class _InternalHelpersMixin:
    def _uses_api_transport(self) -> bool:
        return self._mode in {"api", "self_hosted"}

    def _client(self) -> Any:
        return _runtime_execution_surface_module().runtime_api_client(self)

    def _uses_hosted_local_limits(self) -> bool:
        return _runtime_local_limits_module().uses_hosted_local_limits(
            mode=self._mode,
            enforce_limits=self._enforce_limits,
        )

    def _remember_api_registration(self, registration: SourceRegistration) -> None:
        _runtime_execution_surface_module().remember_api_registration(self, registration)

    def _forget_api_registration(self, dataset_id: str) -> None:
        _runtime_execution_surface_module().forget_api_registration(self, dataset_id)

    def _try_exact_api_resolve(
        self,
        request: Mapping[str, Any],
        start: float,
    ) -> ResolveOutput | None:
        return _runtime_execution_surface_module().try_exact_api_resolve(self, request, start)

    def _coerce_api_resolve_payload(self, request: Mapping[str, Any]) -> dict[str, Any]:
        return _runtime_execution_surface_module().coerce_api_resolve_payload(request)

    def _ensure_local_execution_entitlement(self) -> None:
        _runtime_execution_surface_module().ensure_local_execution_entitlement(self)

    def _consume_local_credit(self) -> None:
        _runtime_execution_surface_module().consume_local_credit(self)

    def _resolve_local(self, request: Mapping[str, Any]) -> ResolveOutput:
        return _runtime_execution_surface_module().resolve_local_request(self, request)

    def _coerce_plan(self, request: Any, kwargs: Mapping[str, Any]) -> ResolvedPlan:
        return _runtime_execution_surface_module().coerce_plan(request, kwargs)

    def _query_local(self, request: Any, kwargs: Mapping[str, Any]) -> QueryOutput:
        return _runtime_execution_surface_module().query_local_request(self, request, kwargs)

    def _verify_local(self, request: Any, kwargs: Mapping[str, Any]) -> VerifyOutput:
        return _runtime_execution_surface_module().verify_local_request(self, request, kwargs)

    def _coerce_api_query_payload(self, request: Any, kwargs: Mapping[str, Any]) -> dict[str, Any]:
        return _runtime_execution_surface_module().coerce_api_query_payload(request, kwargs)
