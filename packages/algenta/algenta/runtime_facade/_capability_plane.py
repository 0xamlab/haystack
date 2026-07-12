"""_CapabilityPlaneMixin for the Runtime class.

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


class _CapabilityPlaneMixin:
    def get_contract(self) -> PlatformContractOutput:
        return _runtime_execution_surface_module().contract_runtime_request(self)

    def register_capability_adapter(self, adapter: Any) -> None:
        _runtime_capability_plane_module().register_capability_adapter(self, adapter)

    def list_capability_providers(self) -> list[CapabilityProviderOutput]:
        return _runtime_capability_plane_module().list_capability_providers(self)

    def get_capability_provider(self, provider_id: str) -> CapabilityProviderOutput:
        return _runtime_capability_plane_module().get_capability_provider(self, provider_id)

    def list_capability_bindings(
        self,
        *,
        provider_id: str | None = None,
        scope: str | None = None,
    ) -> list[CapabilityBindingOutput]:
        return _runtime_capability_plane_module().list_capability_bindings(
            self,
            provider_id=provider_id,
            scope=scope,
        )

    def create_capability_binding(self, request: Mapping[str, Any]) -> CapabilityBindingOutput:
        return _runtime_capability_plane_module().create_capability_binding(self, request)

    def get_capability_binding(self, binding_id: str) -> CapabilityBindingOutput:
        return _runtime_capability_plane_module().get_capability_binding(self, binding_id)

    def update_capability_binding(
        self,
        binding_id: str,
        request: Mapping[str, Any],
    ) -> CapabilityBindingOutput:
        return _runtime_capability_plane_module().update_capability_binding(
            self,
            binding_id,
            request,
        )

    def delete_capability_binding(self, binding_id: str) -> None:
        _runtime_capability_plane_module().delete_capability_binding(self, binding_id)

    def preview_test_capability_binding(
        self,
        request: Mapping[str, Any],
    ) -> CapabilityBindingTestOutput:
        return _runtime_capability_plane_module().preview_test_capability_binding(self, request)

    def test_capability_binding(self, binding_id: str) -> CapabilityBindingTestOutput:
        return _runtime_capability_plane_module().test_capability_binding(self, binding_id)

    def preview_discover_capability_binding(
        self,
        request: Mapping[str, Any],
    ) -> CapabilityDiscoverOutput:
        return _runtime_capability_plane_module().preview_discover_capability_binding(
            self,
            request,
        )

    def discover_capability_binding(self, binding_id: str) -> CapabilityDiscoverOutput:
        return _runtime_capability_plane_module().discover_capability_binding(self, binding_id)

    def start_capability_authorization(
        self,
        binding_id: str,
        request: Mapping[str, Any],
    ) -> CapabilityAuthorizationStartOutput:
        return _runtime_capability_plane_module().start_capability_authorization(
            self,
            binding_id,
            request,
        )

    def complete_capability_authorization(
        self,
        binding_id: str,
        request: Mapping[str, Any],
    ) -> CapabilityAuthorizationCompleteOutput:
        return _runtime_capability_plane_module().complete_capability_authorization(
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
    ) -> list[CapabilityCatalogEntryOutput]:
        return _runtime_capability_plane_module().list_capabilities(
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
    ) -> CapabilityCatalogEntryOutput:
        return _runtime_capability_plane_module().get_capability(
            self,
            capability_id,
            include_instruction=include_instruction,
        )

    def route_capabilities(self, request: Mapping[str, Any]) -> CapabilityRoutePlanOutput:
        return _runtime_capability_plane_module().route_capabilities(self, request)

    def execute_capability(self, request: Mapping[str, Any]) -> CapabilityExecutionOutput:
        return _runtime_capability_plane_module().execute_capability(self, request)

    def record_capability_outcome(
        self,
        request: Mapping[str, Any],
    ) -> CapabilityOutcomeRecordOutput:
        return _runtime_capability_plane_module().record_capability_outcome(self, request)

    def list_skills(self) -> list[CapabilityCatalogEntryOutput]:
        return _runtime_capability_plane_module().list_skills(self)

    def enable_skill(
        self,
        *,
        skill_name: str,
        instruction: str,
        description: str | None = None,
        tags: list[str] | None = None,
        artifact_affinities: list[str] | None = None,
        execution_owner: str = "client_managed",
    ) -> CapabilityDiscoverOutput:
        return _runtime_capability_plane_module().enable_skill(
            self,
            skill_name=skill_name,
            instruction=instruction,
            description=description,
            tags=tags,
            artifact_affinities=artifact_affinities,
            execution_owner=execution_owner,
        )

    def disable_skill(self, binding_id: str) -> None:
        _runtime_capability_plane_module().disable_skill(self, binding_id)

    def list_mcp_providers(self) -> list[CapabilityProviderOutput]:
        return _runtime_capability_plane_module().list_mcp_providers(self)

    def get_runtime_manifest(self) -> RuntimeManifestOutput:
        return _runtime_execution_surface_module().runtime_manifest_runtime_request(self)

    def get_runtime_modules(self) -> RuntimeAdminModulesOutput:
        return _runtime_execution_surface_module().runtime_modules_runtime_request(self)

    def get_runtime_benchmarks(self) -> RuntimeAdminBenchmarksOutput:
        return _runtime_execution_surface_module().runtime_benchmarks_runtime_request(self)

    def get_runtime_release_validation(self) -> RuntimeReleaseValidationOutput:
        return _runtime_execution_surface_module().runtime_release_validation_runtime_request(self)

    def verify(self, request: Any = None, **kwargs: Any) -> VerifyOutput:
        return _runtime_execution_surface_module().verify_runtime_request(
            self,
            request,
            **kwargs,
        )
