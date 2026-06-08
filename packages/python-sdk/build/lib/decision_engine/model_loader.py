from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from importlib import import_module
from typing import Any

from pydantic import BaseModel

_MODEL_EXPORTS = {
    "APIKeyInfo": ("decision_engine.models_account", "APIKeyInfo"),
    "DeploymentCostResult": ("decision_engine.models_deployments", "DeploymentCostResult"),
    "DeploymentDeleteResult": ("decision_engine.models_deployments", "DeploymentDeleteResult"),
    "DeploymentProviderResult": ("decision_engine.models_deployments", "DeploymentProviderResult"),
    "DeploymentRegionResult": ("decision_engine.models_deployments", "DeploymentRegionResult"),
    "DeploymentRegionsResult": ("decision_engine.models_deployments", "DeploymentRegionsResult"),
    "DeploymentResult": ("decision_engine.models_deployments", "DeploymentResult"),
    "ConnectorBrowseResult": ("decision_engine.models_connector_preview", "ConnectorBrowseResult"),
    "ConnectorInfo": ("decision_engine.models_connector_info", "ConnectorInfo"),
    "ConnectorListResult": (
        "decision_engine.models_connector_list_result",
        "ConnectorListResult",
    ),
    "ConnectorTestInfo": ("decision_engine.models_connector_preview", "ConnectorTestInfo"),
    "RepositorySnapshotResult": (
        "decision_engine.models_repository_intelligence",
        "RepositorySnapshotResult",
    ),
    "RepositoryIntelligenceCapabilitiesResult": (
        "decision_engine.models_repository_intelligence",
        "RepositoryIntelligenceCapabilitiesResult",
    ),
    "RepositoryTriageResult": (
        "decision_engine.models_repository_intelligence",
        "RepositoryTriageResult",
    ),
    "RepositoryGraphQueryResult": (
        "decision_engine.models_repository_intelligence",
        "RepositoryGraphQueryResult",
    ),
    "RepositoryDecisionPlanRevisionResult": (
        "decision_engine.models_repository_intelligence",
        "RepositoryDecisionPlanRevisionResult",
    ),
    "RepositoryApplyResult": (
        "decision_engine.models_repository_intelligence",
        "RepositoryApplyResult",
    ),
    "DatasetConnectResult": ("decision_engine.models_dataset", "DatasetConnectResult"),
    "DatasetDeleteResult": ("decision_engine.models_dataset", "DatasetDeleteResult"),
    "DatasetDetailResult": ("decision_engine.models_dataset", "DatasetDetailResult"),
    "DatasetListResult": ("decision_engine.models_dataset", "DatasetListResult"),
    "DatasetSummaryResult": ("decision_engine.models_dataset", "DatasetSummaryResult"),
    "DecisionPlanResult": ("decision_engine.models_decision_plan", "DecisionPlanResult"),
    "DecisionLogResult": ("decision_engine.models_decision_memory", "DecisionLogResult"),
    "DecisionListResult": ("decision_engine.models_decision_memory", "DecisionListResult"),
    "ExecutionReceiptResult": (
        "decision_engine.models_decision_memory",
        "ExecutionReceiptResult",
    ),
    "TriggerConditionResult": ("decision_engine.models_triggers", "TriggerConditionResult"),
    "TriggerSummaryResult": ("decision_engine.models_triggers", "TriggerSummaryResult"),
    "TriggerListResult": ("decision_engine.models_triggers", "TriggerListResult"),
    "TriggerFireResult": ("decision_engine.models_triggers", "TriggerFireResult"),
    "TriggerPauseResult": ("decision_engine.models_triggers", "TriggerPauseResult"),
    "TriggerDeleteResult": ("decision_engine.models_triggers", "TriggerDeleteResult"),
    "ProductDecisionResult": ("decision_engine.models_products", "ProductDecisionResult"),
    "ProductAgentStepResult": ("decision_engine.models_products", "ProductAgentStepResult"),
    "ProductAgentRunResult": ("decision_engine.models_products", "ProductAgentRunResult"),
    "ProductOptimizeResult": ("decision_engine.models_products", "ProductOptimizeResult"),
    "ProductRetrieveHitResult": ("decision_engine.models_products", "ProductRetrieveHitResult"),
    "ProductRetrieveResult": ("decision_engine.models_products", "ProductRetrieveResult"),
    "ProductForecastPeriodResult": (
        "decision_engine.models_products",
        "ProductForecastPeriodResult",
    ),
    "ProductForecastResult": ("decision_engine.models_products", "ProductForecastResult"),
    "DecisionEnvelope": ("decision_engine.models_decision_envelope", "DecisionEnvelope"),
    "ExplainResult": ("decision_engine.models_explain_result", "ExplainResult"),
    "AgentRunResult": ("decision_engine.models_agent_runs", "AgentRunResult"),
    "AgentRunListResult": ("decision_engine.models_agent_runs", "AgentRunListResult"),
    "AgentRunCheckpointResult": ("decision_engine.models_agent_runs", "AgentRunCheckpointResult"),
    "AgentRunCheckpointListResult": (
        "decision_engine.models_agent_runs",
        "AgentRunCheckpointListResult",
    ),
    "AgentRunCheckpointsResult": ("decision_engine.models_agent_runs", "AgentRunCheckpointsResult"),
    "AgentRunCheckpointListResponseResult": (
        "decision_engine.models_agent_runs",
        "AgentRunCheckpointListResponseResult",
    ),
    "AgentRunEventsResult": ("decision_engine.models_agent_runs", "AgentRunEventsResult"),
    "AgentRunMissionEventResult": (
        "decision_engine.models_agent_runs",
        "AgentRunMissionEventResult",
    ),
    "AgentRunMissionEventListResult": (
        "decision_engine.models_agent_runs",
        "AgentRunMissionEventListResult",
    ),
    "AgentRunMissionEventListResponseResult": (
        "decision_engine.models_agent_runs",
        "AgentRunMissionEventListResponseResult",
    ),
    "AgentRunMissionEventsResult": (
        "decision_engine.models_agent_runs",
        "AgentRunMissionEventsResult",
    ),
    "AgentRunReplayResult": ("decision_engine.models_agent_runs", "AgentRunReplayResult"),
    "AgentRunStreamEventResult": (
        "decision_engine.models_agent_runs",
        "AgentRunStreamEventResult",
    ),
    "AgentRunTelemetryBatchResult": (
        "decision_engine.models_agent_runs",
        "AgentRunTelemetryBatchResult",
    ),
    "AgentRunTelemetryResult": ("decision_engine.models_agent_runs", "AgentRunTelemetryResult"),
    "AgentRunTelemetryBatchListResult": (
        "decision_engine.models_agent_runs",
        "AgentRunTelemetryBatchListResult",
    ),
    "AgentRunTelemetryListResult": (
        "decision_engine.models_agent_runs",
        "AgentRunTelemetryListResult",
    ),
    "LLMModelListResult": ("decision_engine.models_llm", "LLMModelListResult"),
    "ArtifactBridgeResolveResult": ("decision_engine.models_llm", "ArtifactBridgeResolveResult"),
    "TokenizeResult": ("decision_engine.models_llm", "TokenizeResult"),
    "CountTokensResult": ("decision_engine.models_llm", "CountTokensResult"),
    "ChatCompletionsResult": ("decision_engine.models_llm", "ChatCompletionsResult"),
    "ChatCompletionsStreamChunkResult": (
        "decision_engine.models_llm",
        "ChatCompletionsStreamChunkResult",
    ),
    "TeamMemberResult": ("decision_engine.models_control_plane", "TeamMemberResult"),
    "MeResult": ("decision_engine.models_control_plane", "MeResult"),
    "MeUserResult": ("decision_engine.models_control_plane", "MeUserResult"),
    "MeOrgResult": ("decision_engine.models_control_plane", "MeOrgResult"),
    "TeamListResult": ("decision_engine.models_control_plane", "TeamListResult"),
    "TeamInviteResult": ("decision_engine.models_control_plane", "TeamInviteResult"),
    "TeamRoleUpdateResult": ("decision_engine.models_control_plane", "TeamRoleUpdateResult"),
    "TeamRemoveResult": ("decision_engine.models_control_plane", "TeamRemoveResult"),
    "AuditLogEntryResult": ("decision_engine.models_control_plane", "AuditLogEntryResult"),
    "AuditLogResult": ("decision_engine.models_control_plane", "AuditLogResult"),
    "BillingInfoResult": ("decision_engine.models_control_plane", "BillingInfoResult"),
    "BillingSessionResult": ("decision_engine.models_control_plane", "BillingSessionResult"),
    "CreditRefreshResult": ("decision_engine.models_control_plane", "CreditRefreshResult"),
    "MeteringBatchResult": ("decision_engine.models_control_plane", "MeteringBatchResult"),
    "DeviceRegistrationResult": ("decision_engine.models_control_plane", "DeviceRegistrationResult"),
    "DeviceListEntryResult": ("decision_engine.models_control_plane", "DeviceListEntryResult"),
    "DeviceListResult": ("decision_engine.models_control_plane", "DeviceListResult"),
    "DeviceRevokeResult": ("decision_engine.models_control_plane", "DeviceRevokeResult"),
    "ExecutionPolicyResult": ("decision_engine.models_control_plane", "ExecutionPolicyResult"),
    "ExecutionPolicySnapshotListResult": (
        "decision_engine.models_control_plane",
        "ExecutionPolicySnapshotListResult",
    ),
    "JobListResponse": ("decision_engine.models_account", "JobListResponse"),
    "DistributionInfoResult": ("decision_engine.models_control_plane", "DistributionInfoResult"),
    "DistributionListResult": ("decision_engine.models_control_plane", "DistributionListResult"),
    "TemplateInfoResult": ("decision_engine.models_control_plane", "TemplateInfoResult"),
    "TemplateListResult": ("decision_engine.models_control_plane", "TemplateListResult"),
    "ResponsesResult": ("decision_engine.models_llm", "ResponsesResult"),
    "ResponseStreamEventResult": ("decision_engine.models_llm", "ResponseStreamEventResult"),
    "EmbeddingsResult": ("decision_engine.models_llm", "EmbeddingsResult"),
    "EmbeddingSimilarityResult": ("decision_engine.models_llm", "EmbeddingSimilarityResult"),
    "RerankResponseResult": ("decision_engine.models_llm", "RerankResponseResult"),
    "PlatformContractResult": ("decision_engine.models_contract", "PlatformContractResult"),
    "CapabilityProviderProfileResult": (
        "decision_engine.models_capability_plane",
        "CapabilityProviderProfileResult",
    ),
    "CapabilityProviderResult": (
        "decision_engine.models_capability_plane",
        "CapabilityProviderResult",
    ),
    "CapabilityBindingResult": (
        "decision_engine.models_capability_plane",
        "CapabilityBindingResult",
    ),
    "CapabilityBindingTestResult": (
        "decision_engine.models_capability_plane",
        "CapabilityBindingTestResult",
    ),
    "CapabilityCatalogEntryResult": (
        "decision_engine.models_capability_plane",
        "CapabilityCatalogEntryResult",
    ),
    "CapabilityDiscoverResult": (
        "decision_engine.models_capability_plane",
        "CapabilityDiscoverResult",
    ),
    "CapabilityRouteFallbackResult": (
        "decision_engine.models_capability_plane",
        "CapabilityRouteFallbackResult",
    ),
    "CapabilityRoutePlanResult": (
        "decision_engine.models_capability_plane",
        "CapabilityRoutePlanResult",
    ),
    "CapabilityExecutionResult": (
        "decision_engine.models_capability_plane",
        "CapabilityExecutionResult",
    ),
    "CapabilityOutcomeRecordResult": (
        "decision_engine.models_capability_plane",
        "CapabilityOutcomeRecordResult",
    ),
    "CapabilityAuthorizationStartResult": (
        "decision_engine.models_capability_plane",
        "CapabilityAuthorizationStartResult",
    ),
    "CapabilityAuthorizationCompleteResult": (
        "decision_engine.models_capability_plane",
        "CapabilityAuthorizationCompleteResult",
    ),
    "RuntimeAdminBenchmarksResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeAdminBenchmarksResult",
    ),
    "RuntimeAdminModulesResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeAdminModulesResult",
    ),
    "RuntimeManifestResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeManifestResult",
    ),
    "RuntimeReleaseValidationResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeReleaseValidationResult",
    ),
    "QueryBatchResult": ("decision_engine.models_query_metadata", "QueryBatchResult"),
    "QueryExecutionMetadata": (
        "decision_engine.models_query_metadata",
        "QueryExecutionMetadata",
    ),
    "QueryResult": ("decision_engine.models_query_result", "QueryResult"),
    "QuerySqlReportResult": ("decision_engine.models_query_metadata", "QuerySqlReportResult"),
    "QueryWithMetadataResult": (
        "decision_engine.models_query_metadata",
        "QueryWithMetadataResult",
    ),
    "ResolveResult": ("decision_engine.models_resolve_result", "ResolveResult"),
    "SourceRegistrationResult": (
        "decision_engine.models_registration_result",
        "SourceRegistrationResult",
    ),
    "UsageInfo": ("decision_engine.models_account", "UsageInfo"),
    "VerifyResult": ("decision_engine.models_verify_result", "VerifyResult"),
}


@cache
def _load_model(model_name: str) -> type[Any]:
    try:
        module_name, attribute_name = _MODEL_EXPORTS[model_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported model name: {model_name}") from exc
    module = import_module(module_name)
    return getattr(module, attribute_name)


def _normalize_validation_payload(payload: Any) -> Any:
    if isinstance(payload, BaseModel):
        return {
            key: _normalize_validation_payload(value)
            for key, value in payload.__dict__.items()
            if not key.startswith("_")
        }
    if isinstance(payload, Mapping):
        return {
            str(key): _normalize_validation_payload(value)
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [_normalize_validation_payload(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(_normalize_validation_payload(item) for item in payload)
    return payload


def validate_model(model_name: str, payload: Any) -> Any:
    model = _load_model(model_name)
    return model.model_validate(_normalize_validation_payload(payload))


def validate_model_list(model_name: str, payloads: list[Any]) -> list[Any]:
    model = _load_model(model_name)
    return [model.model_validate(_normalize_validation_payload(payload)) for payload in payloads]
