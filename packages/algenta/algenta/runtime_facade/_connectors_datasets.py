"""_ConnectorsDatasetsMixin for the Runtime class.

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


class _ConnectorsDatasetsMixin:
    def connect(
        self,
        source: LocalSourceInput | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        connector_id: str | None = None,
        connector: Mapping[str, Any] | None = None,
        selection: Mapping[str, Any] | None = None,
        dataset_name: str | None = None,
        persist: bool = False,
        visibility: str | None = None,
        connection_name: str | None = None,
    ) -> SourceRegistration:
        return _runtime_registration_surface_module().connect_runtime_source(
            self,
            source,
            name=name,
            description=description,
            connector_id=connector_id,
            connector=connector,
            selection=selection,
            dataset_name=dataset_name,
            persist=persist,
            visibility=visibility,
            connection_name=connection_name,
        )

    register_source = connect

    def connect_many(
        self,
        sources: list[LocalSourceInput],
        *,
        names: list[str | None] | None = None,
        description: str | None = None,
    ) -> list[SourceRegistration]:
        return _runtime_registration_surface_module().connect_many_runtime_sources(
            self,
            sources,
            names=names,
            description=description,
        )

    def create_connector(self, **kwargs: Any):
        return self._connector_surface().create_connector(**kwargs)

    def list_connectors(self, **kwargs: Any):
        return self._connector_surface().list_connectors(**kwargs)

    def get_connector(self, connector_id: str):
        return self._connector_surface().get_connector(connector_id)

    def update_connector(self, connector_id: str, **kwargs: Any):
        return self._connector_surface().update_connector(connector_id, **kwargs)

    def iter_connectors(self, **kwargs: Any):
        return self._connector_surface().iter_connectors(**kwargs)

    def test_connector(self, connector_id: str | None = None, **kwargs: Any):
        return self._connector_surface().test_connector(connector_id, **kwargs)

    def browse_connector(self, connector_id: str | None = None, **kwargs: Any):
        return self._connector_surface().browse_connector(connector_id, **kwargs)

    def list_datasets(self, **kwargs: Any):
        return self._connector_surface().list_datasets(**kwargs)

    def iter_datasets(self, **kwargs: Any):
        return self._connector_surface().iter_datasets(**kwargs)

    def get_dataset(self, dataset_id: str):
        return self._connector_surface().get_dataset(dataset_id)

    def get_dataset_summary(self, dataset_id: str):
        return self._connector_surface().get_dataset_summary(dataset_id)

    def refresh_dataset(self, dataset_id: str):
        return self._connector_surface().refresh_dataset(dataset_id)

    def delete_connector(self, connector_id: str) -> None:
        self._connector_surface().delete_connector(connector_id)

    def delete_dataset(self, dataset_id: str):
        return self._connector_surface().delete_dataset(dataset_id)

    disconnect_dataset = delete_dataset
