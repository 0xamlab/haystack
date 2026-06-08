from __future__ import annotations

from importlib import import_module

_LAZY_EXPORTS = {
    "UsageOutput": ("algenta.runtime_model_account", "UsageOutput"),
    "APIKeyInfoOutput": ("algenta.runtime_model_account", "APIKeyInfoOutput"),
    "APIKeyCreatedOutput": ("algenta.runtime_model_account", "APIKeyCreatedOutput"),
    "MeUserOutput": ("algenta.runtime_model_control_plane", "MeUserOutput"),
    "MeOrgOutput": ("algenta.runtime_model_control_plane", "MeOrgOutput"),
    "MeOutput": ("algenta.runtime_model_control_plane", "MeOutput"),
    "TeamMemberOutput": ("algenta.runtime_model_control_plane", "TeamMemberOutput"),
    "TeamListOutput": ("algenta.runtime_model_control_plane", "TeamListOutput"),
    "TeamInviteOutput": ("algenta.runtime_model_control_plane", "TeamInviteOutput"),
    "TeamRoleUpdateOutput": ("algenta.runtime_model_control_plane", "TeamRoleUpdateOutput"),
    "TeamRemoveOutput": ("algenta.runtime_model_control_plane", "TeamRemoveOutput"),
    "DeviceRegistrationOutput": (
        "algenta.runtime_model_control_plane",
        "DeviceRegistrationOutput",
    ),
    "DeviceListEntryOutput": ("algenta.runtime_model_control_plane", "DeviceListEntryOutput"),
    "DeviceListOutput": ("algenta.runtime_model_control_plane", "DeviceListOutput"),
    "DeviceRevokeOutput": ("algenta.runtime_model_control_plane", "DeviceRevokeOutput"),
    "AuditLogEntryOutput": (
        "algenta.runtime_model_control_plane",
        "AuditLogEntryOutput",
    ),
    "AuditLogOutput": ("algenta.runtime_model_control_plane", "AuditLogOutput"),
    "BillingInfoOutput": ("algenta.runtime_model_control_plane", "BillingInfoOutput"),
    "BillingSessionOutput": ("algenta.runtime_model_control_plane", "BillingSessionOutput"),
    "CreditRefreshOutput": ("algenta.runtime_model_control_plane", "CreditRefreshOutput"),
    "MeteringBatchOutput": ("algenta.runtime_model_control_plane", "MeteringBatchOutput"),
    "ExecutionPolicyOutput": (
        "algenta.runtime_model_control_plane",
        "ExecutionPolicyOutput",
    ),
    "ExecutionPolicySnapshotListOutput": (
        "algenta.runtime_model_control_plane",
        "ExecutionPolicySnapshotListOutput",
    ),
    "DistributionInfoOutput": ("algenta.runtime_model_control_plane", "DistributionInfoOutput"),
    "DistributionListOutput": ("algenta.runtime_model_control_plane", "DistributionListOutput"),
    "TemplateInfoOutput": ("algenta.runtime_model_control_plane", "TemplateInfoOutput"),
    "TemplateListOutput": ("algenta.runtime_model_control_plane", "TemplateListOutput"),
    "SourceRegistration": (
        "algenta.runtime_model_source_registration",
        "SourceRegistration",
    ),
    "RiskProfileOutput": ("algenta.runtime_model_decision_plan", "RiskProfileOutput"),
    "DecisionOptionOutput": (
        "algenta.runtime_model_decision_plan",
        "DecisionOptionOutput",
    ),
    "TokenReductionMetricsOutput": (
        "algenta.runtime_model_decision_plan",
        "TokenReductionMetricsOutput",
    ),
    "RepositoryAnalysisOutput": (
        "algenta.runtime_model_decision_plan",
        "RepositoryAnalysisOutput",
    ),
    "DecisionPlanOutput": ("algenta.runtime_model_decision_plan", "DecisionPlanOutput"),
    "MetricsSummaryOutput": (
        "algenta.runtime_model_decision_envelope",
        "MetricsSummaryOutput",
    ),
    "PercentileSummaryOutput": (
        "algenta.runtime_model_decision_envelope",
        "PercentileSummaryOutput",
    ),
    "RunMetadataOutput": (
        "algenta.runtime_model_decision_envelope",
        "RunMetadataOutput",
    ),
    "DecisionEnvelopeOutput": (
        "algenta.runtime_model_decision_envelope",
        "DecisionEnvelopeOutput",
    ),
    "RepositoryArtifactRefOutput": (
        "algenta.runtime_model_repository_intelligence",
        "RepositoryArtifactRefOutput",
    ),
    "RepositoryLanguageSupportProgressOutput": (
        "algenta.runtime_model_repository_intelligence",
        "RepositoryLanguageSupportProgressOutput",
    ),
    "RepositoryIntelligenceCapabilitiesOutput": (
        "algenta.runtime_model_repository_intelligence",
        "RepositoryIntelligenceCapabilitiesOutput",
    ),
    "RepositoryEvidenceItemOutput": (
        "algenta.runtime_model_repository_intelligence",
        "RepositoryEvidenceItemOutput",
    ),
    "RepositorySnapshotOutput": (
        "algenta.runtime_model_repository_intelligence",
        "RepositorySnapshotOutput",
    ),
    "RepositoryTriageOutput": (
        "algenta.runtime_model_repository_intelligence",
        "RepositoryTriageOutput",
    ),
    "RepositoryGraphEdgeOutput": (
        "algenta.runtime_model_repository_intelligence",
        "RepositoryGraphEdgeOutput",
    ),
    "RepositoryGraphNodeOutput": (
        "algenta.runtime_model_repository_intelligence",
        "RepositoryGraphNodeOutput",
    ),
    "RepositoryGraphImpactItemOutput": (
        "algenta.runtime_model_repository_intelligence",
        "RepositoryGraphImpactItemOutput",
    ),
    "RepositoryGraphQueryOutput": (
        "algenta.runtime_model_repository_intelligence",
        "RepositoryGraphQueryOutput",
    ),
    "RepositoryDecisionPlanRevisionOutput": (
        "algenta.runtime_model_repository_intelligence",
        "RepositoryDecisionPlanRevisionOutput",
    ),
    "RepositoryApplyOutput": (
        "algenta.runtime_model_repository_intelligence",
        "RepositoryApplyOutput",
    ),
    "DecisionLogOutput": ("algenta.runtime_model_decision_memory", "DecisionLogOutput"),
    "DecisionListOutput": ("algenta.runtime_model_decision_memory", "DecisionListOutput"),
    "ExecutionReceiptOutput": (
        "algenta.runtime_model_decision_memory",
        "ExecutionReceiptOutput",
    ),
    "JobSubmitOutput": ("algenta.runtime_model_jobs", "JobSubmitOutput"),
    "JobStatusOutput": ("algenta.runtime_model_jobs", "JobStatusOutput"),
    "JobListOutput": ("algenta.runtime_model_jobs", "JobListOutput"),
    "WebhookTestOutput": ("algenta.runtime_model_jobs", "WebhookTestOutput"),
    "TriggerConditionOutput": ("algenta.runtime_model_triggers", "TriggerConditionOutput"),
    "TriggerSummaryOutput": ("algenta.runtime_model_triggers", "TriggerSummaryOutput"),
    "TriggerListOutput": ("algenta.runtime_model_triggers", "TriggerListOutput"),
    "TriggerFireOutput": ("algenta.runtime_model_triggers", "TriggerFireOutput"),
    "TriggerPauseOutput": ("algenta.runtime_model_triggers", "TriggerPauseOutput"),
    "TriggerDeleteOutput": ("algenta.runtime_model_triggers", "TriggerDeleteOutput"),
    "ProductDecisionOutput": ("algenta.runtime_model_products", "ProductDecisionOutput"),
    "ProductAgentStepOutput": ("algenta.runtime_model_products", "ProductAgentStepOutput"),
    "ProductAgentRunOutput": ("algenta.runtime_model_products", "ProductAgentRunOutput"),
    "ProductOptimizeOutput": ("algenta.runtime_model_products", "ProductOptimizeOutput"),
    "ProductRetrieveHitOutput": ("algenta.runtime_model_products", "ProductRetrieveHitOutput"),
    "ProductRetrieveOutput": ("algenta.runtime_model_products", "ProductRetrieveOutput"),
    "ProductForecastPeriodOutput": (
        "algenta.runtime_model_products",
        "ProductForecastPeriodOutput",
    ),
    "ProductForecastOutput": ("algenta.runtime_model_products", "ProductForecastOutput"),
    "DeploymentCostOutput": ("algenta.runtime_model_deployments", "DeploymentCostOutput"),
    "DeploymentDeleteOutput": ("algenta.runtime_model_deployments", "DeploymentDeleteOutput"),
    "DeploymentOutput": ("algenta.runtime_model_deployments", "DeploymentOutput"),
    "DeploymentProviderOutput": ("algenta.runtime_model_deployments", "DeploymentProviderOutput"),
    "DeploymentRegionOutput": ("algenta.runtime_model_deployments", "DeploymentRegionOutput"),
    "DeploymentRegionsOutput": ("algenta.runtime_model_deployments", "DeploymentRegionsOutput"),
    "ImportPreview": ("algenta.runtime_model_import_preview", "ImportPreview"),
    "ImportFailure": ("algenta.runtime_model_import_preview", "ImportFailure"),
    "ImportBundlePreview": ("algenta.runtime_model_import_preview", "ImportBundlePreview"),
    "LLMModelOutput": ("algenta.runtime_model_llm", "LLMModelOutput"),
    "LLMModelListOutput": ("algenta.runtime_model_llm", "LLMModelListOutput"),
    "TokenizeOutput": ("algenta.runtime_model_llm", "TokenizeOutput"),
    "CountTokensOutput": ("algenta.runtime_model_llm", "CountTokensOutput"),
    "ChatCompletionMessageOutput": (
        "algenta.runtime_model_llm",
        "ChatCompletionMessageOutput",
    ),
    "ChatCompletionChoiceOutput": (
        "algenta.runtime_model_llm",
        "ChatCompletionChoiceOutput",
    ),
    "ChatCompletionChunkDeltaOutput": (
        "algenta.runtime_model_llm",
        "ChatCompletionChunkDeltaOutput",
    ),
    "ChatCompletionChunkChoiceOutput": (
        "algenta.runtime_model_llm",
        "ChatCompletionChunkChoiceOutput",
    ),
    "ChatCompletionUsageOutput": (
        "algenta.runtime_model_llm",
        "ChatCompletionUsageOutput",
    ),
    "ChatCompletionsOutput": ("algenta.runtime_model_llm", "ChatCompletionsOutput"),
    "ChatCompletionsStreamChunkOutput": (
        "algenta.runtime_model_llm",
        "ChatCompletionsStreamChunkOutput",
    ),
    "EmbeddingVectorOutput": ("algenta.runtime_model_llm", "EmbeddingVectorOutput"),
    "EmbeddingUsageOutput": ("algenta.runtime_model_llm", "EmbeddingUsageOutput"),
    "EmbeddingsOutput": ("algenta.runtime_model_llm", "EmbeddingsOutput"),
    "ResponseOutputContentOutput": (
        "algenta.runtime_model_llm",
        "ResponseOutputContentOutput",
    ),
    "ResponseOutputItemOutput": ("algenta.runtime_model_llm", "ResponseOutputItemOutput"),
    "ResponsesOutput": ("algenta.runtime_model_llm", "ResponsesOutput"),
    "ResponseLifecycleOutput": ("algenta.runtime_model_llm", "ResponseLifecycleOutput"),
    "ResponseStreamEventOutput": (
        "algenta.runtime_model_llm",
        "ResponseStreamEventOutput",
    ),
    "EmbeddingSimilarityOutput": (
        "algenta.runtime_model_llm",
        "EmbeddingSimilarityOutput",
    ),
    "RerankDocumentOutput": ("algenta.runtime_model_llm", "RerankDocumentOutput"),
    "RerankResponseOutput": ("algenta.runtime_model_llm", "RerankResponseOutput"),
    "AgentStepOutput": ("algenta.runtime_model_agent_runs", "AgentStepOutput"),
    "AgentRunListOutput": ("algenta.runtime_model_agent_runs", "AgentRunListOutput"),
    "AgentRunOutput": ("algenta.runtime_model_agent_runs", "AgentRunOutput"),
    "AgentRunCheckpointListOutput": (
        "algenta.runtime_model_agent_runs",
        "AgentRunCheckpointListOutput",
    ),
    "AgentRunCheckpointListResponseOutput": (
        "algenta.runtime_model_agent_runs",
        "AgentRunCheckpointListResponseOutput",
    ),
    "AgentRunCheckpointOutput": ("algenta.runtime_model_agent_runs", "AgentRunCheckpointOutput"),
    "AgentRunCheckpointsOutput": (
        "algenta.runtime_model_agent_runs",
        "AgentRunCheckpointsOutput",
    ),
    "AgentRunEventOutput": ("algenta.runtime_model_agent_runs", "AgentRunEventOutput"),
    "AgentRunEventsOutput": ("algenta.runtime_model_agent_runs", "AgentRunEventsOutput"),
    "AgentRunMissionEventOutput": (
        "algenta.runtime_model_agent_runs",
        "AgentRunMissionEventOutput",
    ),
    "AgentRunMissionEventListOutput": (
        "algenta.runtime_model_agent_runs",
        "AgentRunMissionEventListOutput",
    ),
    "AgentRunMissionEventListResponseOutput": (
        "algenta.runtime_model_agent_runs",
        "AgentRunMissionEventListResponseOutput",
    ),
    "AgentRunMissionEventsOutput": (
        "algenta.runtime_model_agent_runs",
        "AgentRunMissionEventsOutput",
    ),
    "AgentRunReplayOutput": ("algenta.runtime_model_agent_runs", "AgentRunReplayOutput"),
    "AgentRunTelemetryBatchOutput": (
        "algenta.runtime_model_agent_runs",
        "AgentRunTelemetryBatchOutput",
    ),
    "AgentRunTelemetryBatchListOutput": (
        "algenta.runtime_model_agent_runs",
        "AgentRunTelemetryBatchListOutput",
    ),
    "AgentRunTelemetryOutput": ("algenta.runtime_model_agent_runs", "AgentRunTelemetryOutput"),
    "AgentRunTelemetryListOutput": (
        "algenta.runtime_model_agent_runs",
        "AgentRunTelemetryListOutput",
    ),
    "AgentRunStreamEventOutput": (
        "algenta.runtime_model_agent_runs",
        "AgentRunStreamEventOutput",
    ),
    "ResolvedPlan": ("algenta.runtime_model_resolved_plan", "ResolvedPlan"),
    "ResolveOutput": ("algenta.runtime_model_resolve_output", "ResolveOutput"),
    "QueryOutput": ("algenta.runtime_model_query_output", "QueryOutput"),
    "VerifyOutput": ("algenta.runtime_model_verify_output", "VerifyOutput"),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    export = _LAZY_EXPORTS.get(name)
    if export is None:
        raise AttributeError(f"module 'algenta.runtime_models' has no attribute '{name}'")
    module_name, attribute_name = export
    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
