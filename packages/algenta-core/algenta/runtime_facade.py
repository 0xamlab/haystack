"""Runtime-first Algenta implementation for deterministic resolve and query workflows."""

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


@cache
def _runtime_execution_surface_module() -> ModuleType:
    return import_module("algenta.runtime_execution_surface")


@cache
def _runtime_registration_surface_module() -> ModuleType:
    return import_module("algenta.runtime_registration_surface")


@cache
def _runtime_model_source_registration_module() -> ModuleType:
    return import_module("algenta.runtime_model_source_registration")


@cache
def _runtime_local_limits_module() -> ModuleType:
    return import_module("algenta.runtime_local_limits")


@cache
def _runtime_connectors_module() -> ModuleType:
    return import_module("algenta.runtime_connectors")


@cache
def _runtime_capability_plane_module() -> ModuleType:
    return import_module("algenta.runtime_capability_plane")


class Runtime:
    """
    Runtime-first Algenta facade.

    Local mode executes against connected in-memory or file-backed sources.
    API mode delegates to the lower-level `decision_engine.AlgentaClient`.
    """

    def __init__(
        self,
        *,
        mode: str = "local",
        api_key: str | None = None,
        base_url: str | None = None,
        enforce_limits: bool | None = None,
    ) -> None:
        if mode not in {"local", "api", "self_hosted"}:
            raise ValueError("Invalid mode. Expected 'local', 'api', or 'self_hosted'.")
        api_key_from_env = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
        explicit_api_key = api_key is not None
        self._mode = mode
        self._api_key = api_key or api_key_from_env
        if mode == "self_hosted":
            if not isinstance(base_url, str) or not base_url.strip():
                raise RuntimeConfigurationError(
                    "self_hosted_base_url_required",
                    "Runtime(mode='self_hosted') requires an explicit base_url.",
                )
            self._base_url = resolve_cloud_base_url(
                explicit_base_url=base_url,
                component="Runtime(mode='self_hosted')",
            )
        elif mode == "api":
            self._base_url = resolve_cloud_base_url(
                explicit_base_url=base_url,
                component="Runtime(mode='api')",
            )
        else:
            self._base_url = (
                base_url.strip()
                if isinstance(base_url, str) and base_url.strip()
                else ""
            )
        self._local_sources: dict[str, Any] = {}
        self._api_registrations_by_name: dict[str, SourceRegistration] = {}
        self._api_registrations_by_dataset: dict[str, SourceRegistration] = {}
        self._api_source_schema_revision_cache: dict[str, str] = {}
        self._api_client: Any | None = None
        self._connector_surface_helper: Any | None = None
        self._local_license: Any | None = None
        self._api_surface_cache: dict[str, tuple[float, Any]] = {}
        self._inline_preview_events: list[float] = []
        self._inline_preview_pending_cleanup: dict[str, float] = {}
        self._inline_preview_cache: dict[str, tuple[float, Any]] = {}
        self._inline_preview_capabilities: dict[str, tuple[float, bool]] = {}
        self._capability_adapters: dict[str, dict[str, Any]] = {}
        self._local_capability_bindings: dict[str, dict[str, Any]] = {}
        self._local_capability_catalog: dict[str, dict[str, Any]] = {}
        self._local_capability_auth_sessions: dict[str, dict[str, Any]] = {}
        self._local_capability_outcomes: list[dict[str, Any]] = []
        self._local_capability_executions: dict[str, dict[str, Any]] = {}
        if enforce_limits is None:
            self._enforce_limits = mode == "local" and explicit_api_key
        else:
            self._enforce_limits = enforce_limits

    def __repr__(self) -> str:
        key_state = "set" if self._api_key else "not set"
        return f"Runtime(mode={self._mode!r}, api_key={key_state})"

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            return getattr(self._connector_surface(), name)
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    def _connector_surface(self) -> Any:
        helper = self._connector_surface_helper
        if helper is None:
            helper = _runtime_connectors_module().RuntimeConnectorSurface(self)
            self._connector_surface_helper = helper
        return helper

    @staticmethod
    def _perf_counter() -> float:
        return time.perf_counter()

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

    def resolve(self, request: Mapping[str, Any] | None = None, **kwargs: Any) -> ResolveOutput:
        return _runtime_execution_surface_module().resolve_runtime_request(
            self,
            request,
            **kwargs,
        )

    def query(self, request: Any = None, **kwargs: Any) -> QueryOutput:
        return _runtime_execution_surface_module().query_runtime_request(
            self,
            request,
            **kwargs,
        )

    def query_with_metadata(
        self,
        request: Any = None,
        **kwargs: Any,
    ) -> QueryWithMetadataOutput:
        return _runtime_execution_surface_module().query_with_metadata_runtime_request(
            self,
            request,
            **kwargs,
        )

    def query_batch(self, request: Mapping[str, Any]) -> QueryBatchOutput:
        return _runtime_execution_surface_module().query_batch_runtime_request(
            self,
            request,
        )

    def query_sql_report(self, request: Mapping[str, Any]) -> QuerySqlReportOutput:
        return _runtime_execution_surface_module().query_sql_report_runtime_request(
            self,
            request,
        )

    def recommend(self, actions: Any, **kwargs: Any) -> dict[str, Any]:
        return _runtime_execution_surface_module().recommend_runtime_request(
            self,
            actions,
            **kwargs,
        )

    def score(
        self,
        request: Mapping[str, Any],
        scoring_weights: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        return _runtime_execution_surface_module().score_runtime_request(
            self,
            request,
            scoring_weights=scoring_weights,
        )

    def batch(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return _runtime_execution_surface_module().batch_runtime_request(
            self,
            items,
        )

    def compare(self, scenarios: Any, **kwargs: Any) -> dict[str, Any]:
        return _runtime_execution_surface_module().compare_runtime_request(
            self,
            scenarios,
            **kwargs,
        )

    def submit_job(
        self,
        request: Mapping[str, Any] | None = None,
        *,
        callback_url: str | None = None,
        **kwargs: Any,
    ) -> JobSubmitOutput:
        return _runtime_execution_surface_module().submit_job_runtime_request(
            self,
            request,
            callback_url=callback_url,
            **kwargs,
        )

    def get_job(self, job_id: str) -> JobStatusOutput:
        return _runtime_execution_surface_module().get_job_runtime_request(self, job_id)

    def get_job_result(self, job_id: str) -> dict[str, Any]:
        return _runtime_execution_surface_module().get_job_result_runtime_request(self, job_id)

    def list_jobs(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        status: str | None = None,
    ) -> JobListOutput:
        return _runtime_execution_surface_module().list_jobs_runtime_request(
            self,
            page=page,
            limit=limit,
            status=status,
        )

    def cancel_job(self, job_id: str) -> JobStatusOutput:
        return _runtime_execution_surface_module().cancel_job_runtime_request(self, job_id)

    def test_webhook_delivery(self, callback_url: str) -> WebhookTestOutput:
        return _runtime_execution_surface_module().test_webhook_delivery_runtime_request(
            self,
            callback_url,
        )

    def register_trigger(
        self,
        *,
        name: str,
        condition: Mapping[str, Any],
        simulation_template: Mapping[str, Any],
        webhook_url: str | None = None,
        execution_webhook_url: str | None = None,
        auto_execute: bool = False,
        description: str | None = None,
    ) -> TriggerSummaryOutput:
        return _runtime_execution_surface_module().register_trigger_runtime_request(
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
    ) -> TriggerListOutput:
        return _runtime_execution_surface_module().list_triggers_runtime_request(
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
    ) -> TriggerFireOutput:
        return _runtime_execution_surface_module().fire_trigger_runtime_request(
            self,
            trigger_id,
            force=force,
        )

    def pause_trigger(
        self,
        trigger_id: str,
        *,
        paused: bool = True,
    ) -> TriggerPauseOutput:
        return _runtime_execution_surface_module().pause_trigger_runtime_request(
            self,
            trigger_id,
            paused=paused,
        )

    def delete_trigger(self, trigger_id: str) -> TriggerDeleteOutput:
        return _runtime_execution_surface_module().delete_trigger_runtime_request(
            self,
            trigger_id,
        )

    def poll_job(
        self,
        job_id: str,
        *,
        timeout: float = 300.0,
        poll_interval: float = 2.0,
    ) -> dict[str, Any]:
        return _runtime_execution_surface_module().poll_job_runtime_request(
            self,
            job_id,
            timeout=timeout,
            poll_interval=poll_interval,
        )

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
