"""_AccountBillingAdminMixin for the Runtime class.

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


class _AccountBillingAdminMixin:
    def list_deployment_regions(self) -> DeploymentRegionsOutput:
        return _runtime_execution_surface_module().deployment_regions_runtime_request(self)

    def get_deployment(self) -> DeploymentOutput | None:
        return _runtime_execution_surface_module().get_deployment_runtime_request(self)

    def create_deployment(
        self,
        *,
        provider: str = "algenta_shared",
        region: str = "algenta-shared",
        config: dict[str, Any] | None = None,
        billing_markup_pct: float = 20.0,
    ) -> DeploymentOutput:
        return _runtime_execution_surface_module().create_deployment_runtime_request(
            self,
            provider=provider,
            region=region,
            config=config,
            billing_markup_pct=billing_markup_pct,
        )

    def delete_deployment(self, deployment_id: str) -> DeploymentDeleteOutput:
        return _runtime_execution_surface_module().delete_deployment_runtime_request(
            self,
            deployment_id,
        )

    def get_deployment_cost(self, deployment_id: str) -> DeploymentCostOutput:
        return _runtime_execution_surface_module().deployment_cost_runtime_request(
            self,
            deployment_id,
        )

    def me(self) -> dict[str, Any]:
        return _runtime_execution_surface_module().me_runtime_request(self)

    def update_me(
        self,
        *,
        name: str | None = None,
        org_name: str | None = None,
    ) -> Any:
        return _runtime_execution_surface_module().update_me_runtime_request(
            self,
            name=name,
            org_name=org_name,
        )

    def usage(self) -> UsageOutput:
        return _runtime_execution_surface_module().usage_runtime_request(self)

    def limits(self) -> dict[str, Any]:
        return _runtime_execution_surface_module().limits_runtime_request(self)

    def distributions(self) -> DistributionListOutput:
        return _runtime_execution_surface_module().distributions_runtime_request(self)

    def templates(self) -> TemplateListOutput:
        return _runtime_execution_surface_module().templates_runtime_request(self)

    def get_billing_info(self) -> BillingInfoOutput:
        return _runtime_execution_surface_module().get_billing_info_runtime_request(self)

    def create_billing_checkout(
        self,
        *,
        plan: str | None = None,
    ) -> BillingSessionOutput:
        return _runtime_execution_surface_module().create_billing_checkout_runtime_request(
            self,
            plan=plan,
        )

    def create_billing_portal(self) -> BillingSessionOutput:
        return _runtime_execution_surface_module().create_billing_portal_runtime_request(self)

    def refresh_credits(
        self,
        *,
        device_id: str,
        billing_period: str,
        credits_used: int = 0,
    ) -> CreditRefreshOutput:
        return _runtime_execution_surface_module().refresh_credits_runtime_request(
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
    ) -> MeteringBatchOutput:
        return _runtime_execution_surface_module().ingest_metering_events_runtime_request(
            self,
            device_id=device_id,
            events=events,
        )

    def list_api_keys(self) -> list[APIKeyInfoOutput]:
        return _runtime_execution_surface_module().list_api_keys_runtime_request(self)

    def create_api_key(
        self,
        label: str | None = None,
        *,
        name: str | None = None,
        expires_at: Any = None,
        device_limit: int | None = None,
    ) -> APIKeyCreatedOutput:
        return _runtime_execution_surface_module().create_api_key_runtime_request(
            self,
            label=label,
            name=name,
            expires_at=expires_at,
            device_limit=device_limit,
        )

    def revoke_api_key(self, key_id: str) -> dict[str, Any]:
        return _runtime_execution_surface_module().revoke_api_key_runtime_request(self, key_id)

    def list_team_members(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
    ) -> TeamListOutput:
        return _runtime_execution_surface_module().list_team_members_runtime_request(
            self,
            page=page,
            limit=limit,
        )

    def invite_team_member(
        self,
        *,
        email: str,
        role: str = "member",
    ) -> Any:
        return _runtime_execution_surface_module().invite_team_member_runtime_request(
            self,
            email=email,
            role=role,
        )

    def update_team_member_role(
        self,
        user_id: str,
        *,
        role: str,
    ) -> Any:
        return _runtime_execution_surface_module().update_team_member_role_runtime_request(
            self,
            user_id,
            role=role,
        )

    def remove_team_member(self, user_id: str) -> Any:
        return _runtime_execution_surface_module().remove_team_member_runtime_request(
            self,
            user_id,
        )

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
    ) -> AuditLogOutput:
        return _runtime_execution_surface_module().get_audit_logs_runtime_request(
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
    ) -> AuditLogOutput:
        return _runtime_execution_surface_module().get_audit_log_artifacts_runtime_request(
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

    def get_execution_policy(self) -> ExecutionPolicyOutput:
        return _runtime_execution_surface_module().get_execution_policy_runtime_request(self)

    def list_execution_policy_snapshots(self) -> ExecutionPolicySnapshotListOutput:
        return _runtime_execution_surface_module().list_execution_policy_snapshots_runtime_request(
            self
        )

    def list_devices(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
    ) -> DeviceListOutput:
        return _runtime_execution_surface_module().list_devices_runtime_request(
            self,
            page=page,
            limit=limit,
        )

    def revoke_device(self, registration_id: str) -> DeviceRevokeOutput:
        return _runtime_execution_surface_module().revoke_device_runtime_request(
            self,
            registration_id,
        )

    def update_execution_policy(
        self,
        *,
        min_confidence: float | None = None,
        risk_floor: float | None = None,
        require_calibration: bool | None = None,
        allow_reexecution: bool | None = None,
    ) -> ExecutionPolicyOutput:
        return _runtime_execution_surface_module().update_execution_policy_runtime_request(
            self,
            min_confidence=min_confidence,
            risk_floor=risk_floor,
            require_calibration=require_calibration,
            allow_reexecution=allow_reexecution,
        )
