# SPDX-License-Identifier: Apache-2.0

"""
Algenta Python SDK.

Usage:
    import os

    from decision_engine import AlgentaClient

    api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
    if not api_key:
        raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

    client = AlgentaClient(api_key=api_key)
    datasets = client.list_datasets(search="orders", compact=True)
    summary = client.get_dataset_summary(datasets.datasets[0].dataset_id)
    result = client.query_with_metadata(
        {
            "dataset_id": summary.dataset_id,
            "metric": {"hint": "completed_order_count"},
            "aggregation": "sum",
        }
    )
    print(result.metadata.request_id)

This example is the Cloud Managed path. In `self_hosted` and `air_gapped`,
pass an explicit self-hosted `base_url` and use the API key provisioned by
your self-hosted operator deployment instead. Private profiles fail closed and
do not silently fall back to Algenta cloud.
"""

from __future__ import annotations

from importlib import import_module

__version__ = "1.0.28"

_LAZY_EXPORTS = {
    "AlgentaClient": ("decision_engine.client_facade", "AlgentaClient"),
    "AsyncAlgentaClient": (
        "decision_engine.async_client_facade",
        "AsyncAlgentaClient",
    ),
    # Backward-compatible aliases for integrations that used the former name.
    "CodnaClient": ("decision_engine.client_facade", "CodnaClient"),
    "AsyncCodnaClient": (
        "decision_engine.async_client_facade",
        "AsyncCodnaClient",
    ),
    "DecisionEngineClient": ("decision_engine.client_facade", "DecisionEngineClient"),
    "AsyncDecisionEngineClient": (
        "decision_engine.async_client_facade",
        "AsyncDecisionEngineClient",
    ),
    "AuthenticationError": ("decision_engine.exceptions", "AuthenticationError"),
    "DecisionEngineError": ("decision_engine.exceptions", "DecisionEngineError"),
    "NotFoundError": ("decision_engine.exceptions", "NotFoundError"),
    "RateLimitError": ("decision_engine.exceptions", "RateLimitError"),
    "ServerError": ("decision_engine.exceptions", "ServerError"),
    "ValidationError": ("decision_engine.exceptions", "ValidationError"),
    "APIKeyInfo": ("decision_engine.models_account", "APIKeyInfo"),
    "BatchItemResult": ("decision_engine.models_batch_result", "BatchItemResult"),
    "BatchResult": ("decision_engine.models_batch_result", "BatchResult"),
    "ConnectorBrowseResult": (
        "decision_engine.models_connector_preview",
        "ConnectorBrowseResult",
    ),
    "ConnectorInfo": ("decision_engine.models_connector_info", "ConnectorInfo"),
    "ConnectorListResult": (
        "decision_engine.models_connector_list_result",
        "ConnectorListResult",
    ),
    "ConnectorTestInfo": ("decision_engine.models_connector_preview", "ConnectorTestInfo"),
    "RepositoryIntelligenceCapabilitiesResult": (
        "decision_engine.models_repository_intelligence",
        "RepositoryIntelligenceCapabilitiesResult",
    ),
    "RepositorySnapshotResult": (
        "decision_engine.models_repository_intelligence",
        "RepositorySnapshotResult",
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
    "DatasetInfo": ("decision_engine.models_dataset", "DatasetInfo"),
    "DatasetListResult": ("decision_engine.models_dataset", "DatasetListResult"),
    "DatasetSummaryResult": ("decision_engine.models_dataset", "DatasetSummaryResult"),
    "DecisionEnvelope": ("decision_engine.models_decision_envelope", "DecisionEnvelope"),
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
    "DeploymentCostResult": ("decision_engine.models_deployments", "DeploymentCostResult"),
    "DeploymentDeleteResult": ("decision_engine.models_deployments", "DeploymentDeleteResult"),
    "DeploymentProviderResult": ("decision_engine.models_deployments", "DeploymentProviderResult"),
    "DeploymentRegionResult": ("decision_engine.models_deployments", "DeploymentRegionResult"),
    "DeploymentRegionsResult": ("decision_engine.models_deployments", "DeploymentRegionsResult"),
    "DeploymentResult": ("decision_engine.models_deployments", "DeploymentResult"),
    "ExplainResult": ("decision_engine.models_explain_result", "ExplainResult"),
    "AgentRunListResult": ("decision_engine.models_agent_runs", "AgentRunListResult"),
    "AgentRunResult": ("decision_engine.models_agent_runs", "AgentRunResult"),
    "AgentRunEventResult": ("decision_engine.models_agent_runs", "AgentRunEventResult"),
    "AgentRunCheckpointResult": ("decision_engine.models_agent_runs", "AgentRunCheckpointResult"),
    "AgentRunCheckpointListResult": (
        "decision_engine.models_agent_runs",
        "AgentRunCheckpointListResult",
    ),
    "AgentRunCheckpointsResult": (
        "decision_engine.models_agent_runs",
        "AgentRunCheckpointsResult",
    ),
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
    "AgentRunTelemetryBatchListResult": (
        "decision_engine.models_agent_runs",
        "AgentRunTelemetryBatchListResult",
    ),
    "AgentRunTelemetryResult": ("decision_engine.models_agent_runs", "AgentRunTelemetryResult"),
    "AgentRunTelemetryListResult": (
        "decision_engine.models_agent_runs",
        "AgentRunTelemetryListResult",
    ),
    "LLMModelResult": ("decision_engine.models_llm", "LLMModelResult"),
    "LLMModelListResult": ("decision_engine.models_llm", "LLMModelListResult"),
    "ArtifactBridgeResolveResult": ("decision_engine.models_llm", "ArtifactBridgeResolveResult"),
    "TokenizeResult": ("decision_engine.models_llm", "TokenizeResult"),
    "CountTokensResult": ("decision_engine.models_llm", "CountTokensResult"),
    "ChatCompletionMessageResult": (
        "decision_engine.models_llm",
        "ChatCompletionMessageResult",
    ),
    "ChatCompletionChoiceResult": (
        "decision_engine.models_llm",
        "ChatCompletionChoiceResult",
    ),
    "ChatCompletionDeltaResult": ("decision_engine.models_llm", "ChatCompletionDeltaResult"),
    "ChatCompletionChunkChoiceResult": (
        "decision_engine.models_llm",
        "ChatCompletionChunkChoiceResult",
    ),
    "ChatCompletionUsageResult": (
        "decision_engine.models_llm",
        "ChatCompletionUsageResult",
    ),
    "ChatCompletionsResult": ("decision_engine.models_llm", "ChatCompletionsResult"),
    "ChatCompletionsStreamChunkResult": (
        "decision_engine.models_llm",
        "ChatCompletionsStreamChunkResult",
    ),
    "MeResult": ("decision_engine.models_control_plane", "MeResult"),
    "MeUserResult": ("decision_engine.models_control_plane", "MeUserResult"),
    "MeOrgResult": ("decision_engine.models_control_plane", "MeOrgResult"),
    "TeamMemberResult": ("decision_engine.models_control_plane", "TeamMemberResult"),
    "TeamListResult": ("decision_engine.models_control_plane", "TeamListResult"),
    "TeamInviteResult": ("decision_engine.models_control_plane", "TeamInviteResult"),
    "TeamRoleUpdateResult": ("decision_engine.models_control_plane", "TeamRoleUpdateResult"),
    "TeamRemoveResult": ("decision_engine.models_control_plane", "TeamRemoveResult"),
    "AuditLogEntryResult": ("decision_engine.models_control_plane", "AuditLogEntryResult"),
    "AuditLogResult": ("decision_engine.models_control_plane", "AuditLogResult"),
    "BillingInfoResult": ("decision_engine.models_control_plane", "BillingInfoResult"),
    "BillingSessionResult": (
        "decision_engine.models_control_plane",
        "BillingSessionResult",
    ),
    "CreditRefreshResult": ("decision_engine.models_control_plane", "CreditRefreshResult"),
    "MeteringBatchResult": ("decision_engine.models_control_plane", "MeteringBatchResult"),
    "DeviceRegistrationResult": (
        "decision_engine.models_control_plane",
        "DeviceRegistrationResult",
    ),
    "DeviceListEntryResult": ("decision_engine.models_control_plane", "DeviceListEntryResult"),
    "DeviceListResult": ("decision_engine.models_control_plane", "DeviceListResult"),
    "DeviceRevokeResult": ("decision_engine.models_control_plane", "DeviceRevokeResult"),
    "ExecutionPolicyResult": ("decision_engine.models_control_plane", "ExecutionPolicyResult"),
    "ExecutionPolicySnapshotListResult": (
        "decision_engine.models_control_plane",
        "ExecutionPolicySnapshotListResult",
    ),
    "DistributionInfoResult": ("decision_engine.models_control_plane", "DistributionInfoResult"),
    "DistributionListResult": ("decision_engine.models_control_plane", "DistributionListResult"),
    "TemplateInfoResult": ("decision_engine.models_control_plane", "TemplateInfoResult"),
    "TemplateListResult": ("decision_engine.models_control_plane", "TemplateListResult"),
    "EmbeddingVectorResult": ("decision_engine.models_llm", "EmbeddingVectorResult"),
    "EmbeddingUsageResult": ("decision_engine.models_llm", "EmbeddingUsageResult"),
    "EmbeddingsResult": ("decision_engine.models_llm", "EmbeddingsResult"),
    "ResponseOutputContentResult": (
        "decision_engine.models_llm",
        "ResponseOutputContentResult",
    ),
    "ResponseOutputItemResult": ("decision_engine.models_llm", "ResponseOutputItemResult"),
    "ResponsesResult": ("decision_engine.models_llm", "ResponsesResult"),
    "ResponseLifecycleResult": ("decision_engine.models_llm", "ResponseLifecycleResult"),
    "ResponseStreamEventResult": ("decision_engine.models_llm", "ResponseStreamEventResult"),
    "EmbeddingSimilarityResult": (
        "decision_engine.models_llm",
        "EmbeddingSimilarityResult",
    ),
    "RerankDocumentResult": ("decision_engine.models_llm", "RerankDocumentResult"),
    "RerankResponseResult": ("decision_engine.models_llm", "RerankResponseResult"),
    "JobStatus": ("decision_engine.models_account", "JobStatus"),
    "JobListResponse": ("decision_engine.models_account", "JobListResponse"),
    "JobSubmitResponse": ("decision_engine.models_account", "JobSubmitResponse"),
    "MetricsSummary": ("decision_engine.models_simulation_common", "MetricsSummary"),
    "PercentileSummary": ("decision_engine.models_simulation_common", "PercentileSummary"),
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
    "RuntimeSupportedChannelResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeSupportedChannelResult",
    ),
    "RuntimeAuxiliaryChannelResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeAuxiliaryChannelResult",
    ),
    "RuntimeFeatureFlagChannelResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeFeatureFlagChannelResult",
    ),
    "RuntimeDeploymentModeResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeDeploymentModeResult",
    ),
    "RuntimeBenchmarkClassCodeResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeBenchmarkClassCodeResult",
    ),
    "RuntimeBenchmarkMetricResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeBenchmarkMetricResult",
    ),
    "RuntimeBenchmarkBaselineResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeBenchmarkBaselineResult",
    ),
    "RuntimeMemoryRegionResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeMemoryRegionResult",
    ),
    "RuntimeMemoryRuleResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeMemoryRuleResult",
    ),
    "RuntimeExecutionStateFieldResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeExecutionStateFieldResult",
    ),
    "RuntimeExecutionValidityRuleResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeExecutionValidityRuleResult",
    ),
    "RuntimeExternalNondeterminismSourceResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeExternalNondeterminismSourceResult",
    ),
    "RuntimeFailureCodeResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeFailureCodeResult",
    ),
    "RuntimeExecutionTransitionResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeExecutionTransitionResult",
    ),
    "RuntimeArtifactLineageStepResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeArtifactLineageStepResult",
    ),
    "RuntimeCapabilityFieldResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeCapabilityFieldResult",
    ),
    "RuntimeCapabilityRuleResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeCapabilityRuleResult",
    ),
    "RuntimeArtifactKindResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeArtifactKindResult",
    ),
    "RuntimeCompiledEngineResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeCompiledEngineResult",
    ),
    "RuntimeBenchmarkDiscoveryRuleResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeBenchmarkDiscoveryRuleResult",
    ),
    "RuntimeNonShippingRuleResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeNonShippingRuleResult",
    ),
    "RuntimeSignatureAlgorithmResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeSignatureAlgorithmResult",
    ),
    "RuntimeSignatureScopeResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeSignatureScopeResult",
    ),
    "RuntimeLayerResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeLayerResult",
    ),
    "RuntimeModuleIdResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeModuleIdResult",
    ),
    "RuntimePublicEndpointResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimePublicEndpointResult",
    ),
    "RuntimeAdminEndpointResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeAdminEndpointResult",
    ),
    "RuntimeFeatureFlagEndpointResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeFeatureFlagEndpointResult",
    ),
    "RuntimeMaturityResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeMaturityResult",
    ),
    "RuntimeInvariantNameResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeInvariantNameResult",
    ),
    "RuntimeLineageNodeFieldResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeLineageNodeFieldResult",
    ),
    "RuntimeNondeterminismArtifactResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeNondeterminismArtifactResult",
    ),
    "RuntimeEvaluationMethodResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeEvaluationMethodResult",
    ),
    "RuntimeEvaluationDimensionResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeEvaluationDimensionResult",
    ),
    "RuntimeProofObligationResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeProofObligationResult",
    ),
    "RuntimeReplayabilityResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeReplayabilityResult",
    ),
    "RuntimeRiskLevelResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeRiskLevelResult",
    ),
    "RuntimeReleaseValidationResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeReleaseValidationResult",
    ),
    "RuntimeReleaseConditionResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeReleaseConditionResult",
    ),
    "RuntimeReleaseGateIdResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeReleaseGateIdResult",
    ),
    "RuntimeReleaseBlockerResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeReleaseBlockerResult",
    ),
    "RuntimeThreatClassResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeThreatClassResult",
    ),
    "RuntimeThreatControlResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeThreatControlResult",
    ),
    "RuntimeThreatRuleResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeThreatRuleResult",
    ),
    "RuntimeReleaseArtifactResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeReleaseArtifactResult",
    ),
    "RuntimeSchedulerInvariantResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeSchedulerInvariantResult",
    ),
    "RuntimeSchedulerMaximizeObjectiveResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeSchedulerMaximizeObjectiveResult",
    ),
    "RuntimeSchedulerMinimizeObjectiveResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeSchedulerMinimizeObjectiveResult",
    ),
    "RuntimeSchedulerPolicyResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeSchedulerPolicyResult",
    ),
    "RuntimeSideEffectClassResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeSideEffectClassResult",
    ),
    "RuntimeSLOBudgetNameResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeSLOBudgetNameResult",
    ),
    "RuntimeSLOBudgetAppliesToResult": (
        "decision_engine.models_runtime_manifest",
        "RuntimeSLOBudgetAppliesToResult",
    ),
    "QueryBatchResult": ("decision_engine.models_query_metadata", "QueryBatchResult"),
    "QueryExecutionMetadata": ("decision_engine.models_query_metadata", "QueryExecutionMetadata"),
    "QueryCandidate": ("decision_engine.models_query_result", "QueryCandidate"),
    "QueryFilterCondition": (
        "decision_engine.models_resolve_result",
        "QueryFilterCondition",
    ),
    "QueryFilterSpec": ("decision_engine.models_resolve_result", "QueryFilterSpec"),
    "QueryResult": ("decision_engine.models_query_result", "QueryResult"),
    "QuerySqlReportResult": ("decision_engine.models_query_metadata", "QuerySqlReportResult"),
    "QueryWithMetadataResult": ("decision_engine.models_query_metadata", "QueryWithMetadataResult"),
    "ResolvedPlan": ("decision_engine.models_resolve_result", "ResolvedPlan"),
    "ResolveResult": ("decision_engine.models_resolve_result", "ResolveResult"),
    "SourceRegistrationResult": (
        "decision_engine.models_registration_result",
        "SourceRegistrationResult",
    ),
    "RunMetadata": ("decision_engine.models_simulation_common", "RunMetadata"),
    "UsageInfo": ("decision_engine.models_account", "UsageInfo"),
    "VerifyResult": ("decision_engine.models_verify_result", "VerifyResult"),
    "DEFAULT_BASE_URL": ("decision_engine._contract", "DEFAULT_BASE_URL"),
    "CONTRACT_VERSION": ("decision_engine._contract", "CONTRACT_VERSION"),
    "BRAND": ("decision_engine._contract", "BRAND"),
    "MCP_ENDPOINT": ("decision_engine._contract", "MCP_ENDPOINT"),
    "MCP_TRANSPORT": ("decision_engine._contract", "MCP_TRANSPORT"),
    "MCP_PROTOCOL_VERSION": ("decision_engine._contract", "MCP_PROTOCOL_VERSION"),
    "MCP_LEGACY_SSE_ENDPOINT": ("decision_engine._contract", "MCP_LEGACY_SSE_ENDPOINT"),
    "MCP_TOOLS_ENDPOINT": ("decision_engine._contract", "MCP_TOOLS_ENDPOINT"),
    "AUTH_SCHEME": ("decision_engine._contract", "AUTH_SCHEME"),
    "API_KEY_PREFIX_LIVE": ("decision_engine._contract", "API_KEY_PREFIX_LIVE"),
    "API_KEY_PREFIX_TEST": ("decision_engine._contract", "API_KEY_PREFIX_TEST"),
    "LEGACY_HEADERS": ("decision_engine._contract", "LEGACY_HEADERS"),
    "LEGACY_ENV_VARS": ("decision_engine._contract", "LEGACY_ENV_VARS"),
    "LEGACY_DOMAINS": ("decision_engine._contract", "LEGACY_DOMAINS"),
    "VENDOR_TELEMETRY_HOSTS": ("decision_engine._contract", "VENDOR_TELEMETRY_HOSTS"),
    "PRIVATE_HOST_SUFFIXES": ("decision_engine._contract", "PRIVATE_HOST_SUFFIXES"),
    "DEPRECATION_WINDOW_DAYS": ("decision_engine._contract", "DEPRECATION_WINDOW_DAYS"),
    "READ_ONLY_DEFAULT": ("decision_engine._contract", "READ_ONLY_DEFAULT"),
    "WRITE_CONFIRMATION_REQUIRED": (
        "decision_engine._contract",
        "WRITE_CONFIRMATION_REQUIRED",
    ),
    "PLAN_LIMITS": ("decision_engine._contract", "PLAN_LIMITS"),
    "INTEGRATIONS": ("decision_engine._contract", "INTEGRATIONS"),
    "PRIMARY_DATA_QUERY_CONTRACT": (
        "decision_engine._contract",
        "PRIMARY_DATA_QUERY_CONTRACT",
    ),
    "CAPABILITY_PLANE_CONTRACT": (
        "decision_engine._contract",
        "CAPABILITY_PLANE_CONTRACT",
    ),
}

_CONTRACT_EXPORT_NAMES = tuple(
    name for name, export in _LAZY_EXPORTS.items() if export[0] == "decision_engine._contract"
)

__all__ = list(_LAZY_EXPORTS)


def _cache_available_exports(module_name: str, module) -> None:
    for export_name, export in _LAZY_EXPORTS.items():
        if export[0] != module_name:
            continue
        attribute_name = export[1]
        if hasattr(module, attribute_name):
            globals()[export_name] = getattr(module, attribute_name)


def __getattr__(name: str):
    export = _LAZY_EXPORTS.get(name)
    if export is None:
        raise AttributeError(f"module 'decision_engine' has no attribute '{name}'")
    module_name, attribute_name = export
    module = import_module(module_name)
    if module_name == "decision_engine._contract":
        _cache_available_exports(module_name, module)
        value = getattr(module, attribute_name)
        globals()[name] = value
    else:
        _cache_available_exports(module_name, module)
        value = getattr(module, attribute_name)
        globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
