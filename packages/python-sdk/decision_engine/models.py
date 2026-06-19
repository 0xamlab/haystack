"""Pydantic response models for the Algenta Python SDK."""

from __future__ import annotations

from importlib import import_module

_LAZY_EXPORTS = {
    "MetricsSummary": ("decision_engine.models_simulation_common", "MetricsSummary"),
    "PercentileSummary": ("decision_engine.models_simulation_common", "PercentileSummary"),
    "RunMetadata": ("decision_engine.models_simulation_common", "RunMetadata"),
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
    "BatchItemResult": ("decision_engine.models_batch_result", "BatchItemResult"),
    "BatchResult": ("decision_engine.models_batch_result", "BatchResult"),
    "QueryBatchResult": ("decision_engine.models_query_metadata", "QueryBatchResult"),
    "QueryExecutionMetadata": ("decision_engine.models_query_metadata", "QueryExecutionMetadata"),
    "QueryCandidate": ("decision_engine.models_query_result", "QueryCandidate"),
    "ResolvedPlan": ("decision_engine.models_resolve_result", "ResolvedPlan"),
    "QueryResult": ("decision_engine.models_query_result", "QueryResult"),
    "QuerySqlReportResult": ("decision_engine.models_query_metadata", "QuerySqlReportResult"),
    "QueryWithMetadataResult": ("decision_engine.models_query_metadata", "QueryWithMetadataResult"),
    "ResolveResult": ("decision_engine.models_resolve_result", "ResolveResult"),
    "VerifyResult": ("decision_engine.models_verify_result", "VerifyResult"),
    "SourceRegistrationResult": (
        "decision_engine.models_registration_result",
        "SourceRegistrationResult",
    ),
    "ExplainResult": ("decision_engine.models_explain_result", "ExplainResult"),
    "AgentRunResult": ("decision_engine.models_agent_runs", "AgentRunResult"),
    "AgentRunListResult": ("decision_engine.models_agent_runs", "AgentRunListResult"),
    "AgentRunEventResult": ("decision_engine.models_agent_runs", "AgentRunEventResult"),
    "AgentRunEventsResult": ("decision_engine.models_agent_runs", "AgentRunEventsResult"),
    "AgentRunMissionEventResult": ("decision_engine.models_agent_runs", "AgentRunMissionEventResult"),
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
    "ConnectorInfo": ("decision_engine.models_connector_info", "ConnectorInfo"),
    "ConnectorListResult": (
        "decision_engine.models_connector_list_result",
        "ConnectorListResult",
    ),
    "ConnectorTestInfo": ("decision_engine.models_connector_preview", "ConnectorTestInfo"),
    "ConnectorBrowseResult": (
        "decision_engine.models_connector_preview",
        "ConnectorBrowseResult",
    ),
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
    "PlatformContractResult": ("decision_engine.models_contract", "PlatformContractResult"),
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
    "DatasetInfo": ("decision_engine.models_dataset", "DatasetInfo"),
    "DatasetListResult": ("decision_engine.models_dataset", "DatasetListResult"),
    "DatasetDetailResult": ("decision_engine.models_dataset", "DatasetDetailResult"),
    "DatasetSummaryResult": ("decision_engine.models_dataset", "DatasetSummaryResult"),
    "DatasetDeleteResult": ("decision_engine.models_dataset", "DatasetDeleteResult"),
    "DatasetConnectResult": ("decision_engine.models_dataset", "DatasetConnectResult"),
    "JobStatus": ("decision_engine.models_account", "JobStatus"),
    "JobListResponse": ("decision_engine.models_account", "JobListResponse"),
    "JobSubmitResponse": ("decision_engine.models_account", "JobSubmitResponse"),
    "APIKeyInfo": ("decision_engine.models_account", "APIKeyInfo"),
    "UsageInfo": ("decision_engine.models_account", "UsageInfo"),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    export = _LAZY_EXPORTS.get(name)
    if export is None:
        raise AttributeError(f"module 'decision_engine.models' has no attribute '{name}'")
    module_name, attribute_name = export
    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
