"""_AgentRunsMixin for the Runtime class.

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


class _AgentRunsMixin:
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
    ) -> AgentRunOutput:
        return _runtime_execution_surface_module().create_agent_run_runtime_request(
            self,
            task=task,
            context=context,
            tools=tools,
            max_steps=max_steps,
            output_format=output_format,
            approval_mode=approval_mode,
            start_paused=start_paused,
        )

    def get_agent_run(self, run_id: str) -> AgentRunOutput:
        return _runtime_execution_surface_module().get_agent_run_runtime_request(self, run_id)

    def list_agent_runs(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        status: str | None = None,
        request_hash: str | None = None,
        policy_snapshot_id: str | None = None,
        schema_snapshot_id: str | None = None,
    ) -> AgentRunListOutput:
        return _runtime_execution_surface_module().list_agent_runs_runtime_request(
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
    ) -> AgentRunEventsOutput:
        return _runtime_execution_surface_module().get_agent_run_events_runtime_request(
            self,
            run_id,
            limit=limit,
        )

    def list_agent_run_mission_events(
        self,
        run_id: str,
        *,
        limit: int = 1000,
    ) -> AgentRunMissionEventsOutput:
        return _runtime_execution_surface_module().list_agent_run_mission_events_runtime_request(
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
    ) -> AgentRunMissionEventListResponseOutput:
        return _runtime_execution_surface_module().query_agent_run_mission_events_runtime_request(
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

    def stream_agent_run_events(
        self,
        run_id: str,
        *,
        limit: int = 1000,
    ) -> Iterator[AgentRunStreamEventOutput]:
        return _runtime_execution_surface_module().stream_agent_run_events_runtime_request(
            self,
            run_id,
            limit=limit,
        )

    def resume_agent_run(self, run_id: str) -> AgentRunOutput:
        return _runtime_execution_surface_module().resume_agent_run_runtime_request(self, run_id)

    def cancel_agent_run(self, run_id: str) -> AgentRunOutput:
        return _runtime_execution_surface_module().cancel_agent_run_runtime_request(self, run_id)

    def approve_agent_run(self, run_id: str) -> AgentRunOutput:
        return _runtime_execution_surface_module().approve_agent_run_runtime_request(self, run_id)

    def list_agent_run_checkpoints(self, run_id: str) -> AgentRunCheckpointsOutput:
        return _runtime_execution_surface_module().list_agent_run_checkpoints_runtime_request(
            self,
            run_id,
        )

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
    ) -> AgentRunCheckpointListResponseOutput:
        return _runtime_execution_surface_module().query_agent_run_checkpoints_runtime_request(
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

    def list_agent_run_telemetry(
        self,
        run_id: str,
        *,
        limit: int = 1000,
    ) -> AgentRunTelemetryOutput:
        return _runtime_execution_surface_module().list_agent_run_telemetry_runtime_request(
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
    ) -> AgentRunTelemetryListOutput:
        return _runtime_execution_surface_module().query_agent_run_telemetry_runtime_request(
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
    ) -> AgentRunReplayOutput:
        return _runtime_execution_surface_module().replay_agent_run_runtime_request(
            self,
            run_id,
            checkpoint_id=checkpoint_id,
        )

    def fork_agent_run(
        self,
        run_id: str,
        *,
        checkpoint_id: str | None = None,
    ) -> AgentRunOutput:
        return _runtime_execution_surface_module().fork_agent_run_runtime_request(
            self,
            run_id,
            checkpoint_id=checkpoint_id,
        )
