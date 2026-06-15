"""
algenta-core — runtime-first local package for deterministic structured-data execution.

Primary path:

  from algenta import Runtime

  rt = Runtime()
  rt.connect("orders.csv")
  plan = rt.resolve({"metric": "revenue", "group_by": "product_line"})
  result = rt.query(plan)

Supported secondary modes remain available:

  from algenta import decision, optimize, simulate, forecast, map_data, query_data

Cloud/API examples under this package are the Cloud Managed path by default. In
`self_hosted` and `air_gapped`, pass an explicit self-hosted `base_url` and use
the API key provisioned by your self-hosted operator deployment instead.
Private profiles fail closed and do not silently fall back to Codna cloud.
"""

from __future__ import annotations

from importlib import import_module

__version__ = "1.0.0"

_LAZY_EXPORTS = {
    "Runtime": ("algenta.runtime_facade", "Runtime"),
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
    "QueryFilterCondition": (
        "algenta.runtime_model_resolved_plan",
        "QueryFilterCondition",
    ),
    "QueryFilterSpec": ("algenta.runtime_model_resolved_plan", "QueryFilterSpec"),
    "ResolvedPlan": ("algenta.runtime_model_resolved_plan", "ResolvedPlan"),
    "ResolveOutput": ("algenta.runtime_model_resolve_output", "ResolveOutput"),
    "QueryOutput": ("algenta.runtime_model_query_output", "QueryOutput"),
    "VerifyOutput": ("algenta.runtime_model_verify_output", "VerifyOutput"),
    "SourceRegistration": ("algenta.runtime_model_source_registration", "SourceRegistration"),
    "ImportPreview": ("algenta.runtime_model_import_preview", "ImportPreview"),
    "ImportBundlePreview": ("algenta.runtime_model_import_preview", "ImportBundlePreview"),
    "ImportFailure": ("algenta.runtime_model_import_preview", "ImportFailure"),
    "CodnaRuntimeError": ("algenta.runtime_errors", "CodnaRuntimeError"),
    "RuntimeConfigurationError": ("algenta.runtime_errors", "RuntimeConfigurationError"),
    "RuntimeValidationError": ("algenta.runtime_errors", "RuntimeValidationError"),
    "ConnectorMetadata": ("algenta.runtime_connector_model_metadata", "ConnectorMetadata"),
    "ConnectorTestOutput": ("algenta.runtime_connector_model_preview", "ConnectorTestOutput"),
    "ConnectorBrowseOutput": ("algenta.runtime_connector_model_preview", "ConnectorBrowseOutput"),
    "DatasetDetail": ("algenta.runtime_connector_model_dataset", "DatasetDetail"),
    "DatasetDeleteOutput": ("algenta.runtime_connector_model_dataset", "DatasetDeleteOutput"),
    "DatasetList": ("algenta.runtime_connector_model_dataset", "DatasetList"),
    "DatasetSelectionSummary": (
        "algenta.runtime_connector_model_dataset",
        "DatasetSelectionSummary",
    ),
    "DatasetSummary": ("algenta.runtime_connector_model_dataset", "DatasetSummary"),
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
    "LLMModelOutput": ("algenta.runtime_model_llm", "LLMModelOutput"),
    "LLMModelListOutput": ("algenta.runtime_model_llm", "LLMModelListOutput"),
    "ArtifactBridgeResolveOutput": (
        "algenta.runtime_model_llm",
        "ArtifactBridgeResolveOutput",
    ),
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
    "QueryExecutionMetadata": (
        "algenta.runtime_model_query_metadata",
        "QueryExecutionMetadata",
    ),
    "PlatformContractOutput": ("algenta.runtime_model_contract", "PlatformContractOutput"),
    "CapabilityProviderProfileOutput": (
        "algenta.runtime_model_capability_plane",
        "CapabilityProviderProfileOutput",
    ),
    "CapabilityProviderOutput": (
        "algenta.runtime_model_capability_plane",
        "CapabilityProviderOutput",
    ),
    "CapabilityBindingOutput": (
        "algenta.runtime_model_capability_plane",
        "CapabilityBindingOutput",
    ),
    "CapabilityBindingTestOutput": (
        "algenta.runtime_model_capability_plane",
        "CapabilityBindingTestOutput",
    ),
    "CapabilityCatalogEntryOutput": (
        "algenta.runtime_model_capability_plane",
        "CapabilityCatalogEntryOutput",
    ),
    "CapabilityDiscoverOutput": (
        "algenta.runtime_model_capability_plane",
        "CapabilityDiscoverOutput",
    ),
    "CapabilityRouteFallbackOutput": (
        "algenta.runtime_model_capability_plane",
        "CapabilityRouteFallbackOutput",
    ),
    "CapabilityRoutePlanOutput": (
        "algenta.runtime_model_capability_plane",
        "CapabilityRoutePlanOutput",
    ),
    "CapabilityExecutionOutput": (
        "algenta.runtime_model_capability_plane",
        "CapabilityExecutionOutput",
    ),
    "CapabilityOutcomeRecordOutput": (
        "algenta.runtime_model_capability_plane",
        "CapabilityOutcomeRecordOutput",
    ),
    "CapabilityAuthorizationStartOutput": (
        "algenta.runtime_model_capability_plane",
        "CapabilityAuthorizationStartOutput",
    ),
    "CapabilityAuthorizationCompleteOutput": (
        "algenta.runtime_model_capability_plane",
        "CapabilityAuthorizationCompleteOutput",
    ),
    "RuntimeAdminBenchmarksOutput": (
        "algenta.runtime_model_manifest",
        "RuntimeAdminBenchmarksOutput",
    ),
    "RuntimeAdminModulesOutput": (
        "algenta.runtime_model_manifest",
        "RuntimeAdminModulesOutput",
    ),
    "RuntimeManifestOutput": ("algenta.runtime_model_manifest", "RuntimeManifestOutput"),
    "RuntimeSupportedChannel": ("algenta.runtime_model_manifest", "RuntimeSupportedChannel"),
    "RuntimeAuxiliaryChannel": ("algenta.runtime_model_manifest", "RuntimeAuxiliaryChannel"),
    "RuntimeFeatureFlagChannel": (
        "algenta.runtime_model_manifest",
        "RuntimeFeatureFlagChannel",
    ),
    "RuntimeDeploymentMode": ("algenta.runtime_model_manifest", "RuntimeDeploymentMode"),
    "RuntimeBenchmarkClassCode": (
        "algenta.runtime_model_manifest",
        "RuntimeBenchmarkClassCode",
    ),
    "RuntimeBenchmarkMetric": ("algenta.runtime_model_manifest", "RuntimeBenchmarkMetric"),
    "RuntimeBenchmarkBaseline": ("algenta.runtime_model_manifest", "RuntimeBenchmarkBaseline"),
    "RuntimeMemoryRegion": ("algenta.runtime_model_manifest", "RuntimeMemoryRegion"),
    "RuntimeMemoryRule": ("algenta.runtime_model_manifest", "RuntimeMemoryRule"),
    "RuntimeExecutionStateField": (
        "algenta.runtime_model_manifest",
        "RuntimeExecutionStateField",
    ),
    "RuntimeExecutionValidityRule": (
        "algenta.runtime_model_manifest",
        "RuntimeExecutionValidityRule",
    ),
    "RuntimeExternalNondeterminismSource": (
        "algenta.runtime_model_manifest",
        "RuntimeExternalNondeterminismSource",
    ),
    "RuntimeFailureCode": ("algenta.runtime_model_manifest", "RuntimeFailureCode"),
    "RuntimeExecutionTransition": (
        "algenta.runtime_model_manifest",
        "RuntimeExecutionTransition",
    ),
    "RuntimeArtifactLineageStep": (
        "algenta.runtime_model_manifest",
        "RuntimeArtifactLineageStep",
    ),
    "RuntimeCapabilityField": (
        "algenta.runtime_model_manifest",
        "RuntimeCapabilityField",
    ),
    "RuntimeCapabilityRule": (
        "algenta.runtime_model_manifest",
        "RuntimeCapabilityRule",
    ),
    "RuntimeArtifactKind": ("algenta.runtime_model_manifest", "RuntimeArtifactKind"),
    "RuntimeCompiledEngine": ("algenta.runtime_model_manifest", "RuntimeCompiledEngine"),
    "RuntimeBenchmarkDiscoveryRule": (
        "algenta.runtime_model_manifest",
        "RuntimeBenchmarkDiscoveryRule",
    ),
    "RuntimeNonShippingRule": (
        "algenta.runtime_model_manifest",
        "RuntimeNonShippingRule",
    ),
    "RuntimeSignatureAlgorithm": (
        "algenta.runtime_model_manifest",
        "RuntimeSignatureAlgorithm",
    ),
    "RuntimeSignatureScope": (
        "algenta.runtime_model_manifest",
        "RuntimeSignatureScope",
    ),
    "RuntimeLayer": ("algenta.runtime_model_manifest", "RuntimeLayer"),
    "RuntimeModuleId": ("algenta.runtime_model_manifest", "RuntimeModuleId"),
    "RuntimePublicEndpoint": ("algenta.runtime_model_manifest", "RuntimePublicEndpoint"),
    "RuntimeAdminEndpoint": ("algenta.runtime_model_manifest", "RuntimeAdminEndpoint"),
    "RuntimeFeatureFlagEndpoint": (
        "algenta.runtime_model_manifest",
        "RuntimeFeatureFlagEndpoint",
    ),
    "RuntimeMaturity": ("algenta.runtime_model_manifest", "RuntimeMaturity"),
    "RuntimeInvariantName": ("algenta.runtime_model_manifest", "RuntimeInvariantName"),
    "RuntimeLineageNodeField": (
        "algenta.runtime_model_manifest",
        "RuntimeLineageNodeField",
    ),
    "RuntimeNondeterminismArtifact": (
        "algenta.runtime_model_manifest",
        "RuntimeNondeterminismArtifact",
    ),
    "RuntimeEvaluationMethod": ("algenta.runtime_model_manifest", "RuntimeEvaluationMethod"),
    "RuntimeEvaluationDimension": (
        "algenta.runtime_model_manifest",
        "RuntimeEvaluationDimension",
    ),
    "RuntimeProofObligation": ("algenta.runtime_model_manifest", "RuntimeProofObligation"),
    "RuntimeReplayability": ("algenta.runtime_model_manifest", "RuntimeReplayability"),
    "RuntimeRiskLevel": ("algenta.runtime_model_manifest", "RuntimeRiskLevel"),
    "RuntimeReleaseValidationOutput": (
        "algenta.runtime_model_manifest",
        "RuntimeReleaseValidationOutput",
    ),
    "RuntimeReleaseCondition": (
        "algenta.runtime_model_manifest",
        "RuntimeReleaseCondition",
    ),
    "RuntimeReleaseGateId": ("algenta.runtime_model_manifest", "RuntimeReleaseGateId"),
    "RuntimeReleaseBlocker": ("algenta.runtime_model_manifest", "RuntimeReleaseBlocker"),
    "RuntimeThreatClass": ("algenta.runtime_model_manifest", "RuntimeThreatClass"),
    "RuntimeThreatControl": ("algenta.runtime_model_manifest", "RuntimeThreatControl"),
    "RuntimeThreatRule": ("algenta.runtime_model_manifest", "RuntimeThreatRule"),
    "RuntimeReleaseArtifact": ("algenta.runtime_model_manifest", "RuntimeReleaseArtifact"),
    "RuntimeSchedulerInvariant": (
        "algenta.runtime_model_manifest",
        "RuntimeSchedulerInvariant",
    ),
    "RuntimeSchedulerMaximizeObjective": (
        "algenta.runtime_model_manifest",
        "RuntimeSchedulerMaximizeObjective",
    ),
    "RuntimeSchedulerMinimizeObjective": (
        "algenta.runtime_model_manifest",
        "RuntimeSchedulerMinimizeObjective",
    ),
    "RuntimeSchedulerPolicy": ("algenta.runtime_model_manifest", "RuntimeSchedulerPolicy"),
    "RuntimeSideEffectClass": (
        "algenta.runtime_model_manifest",
        "RuntimeSideEffectClass",
    ),
    "RuntimeSLOBudgetName": ("algenta.runtime_model_manifest", "RuntimeSLOBudgetName"),
    "RuntimeSLOBudgetAppliesTo": (
        "algenta.runtime_model_manifest",
        "RuntimeSLOBudgetAppliesTo",
    ),
    "QueryWithMetadataOutput": (
        "algenta.runtime_model_query_metadata",
        "QueryWithMetadataOutput",
    ),
    "QueryBatchError": ("algenta.runtime_model_query_metadata", "QueryBatchError"),
    "QueryBatchItemOutput": (
        "algenta.runtime_model_query_metadata",
        "QueryBatchItemOutput",
    ),
    "QueryBatchOutput": ("algenta.runtime_model_query_metadata", "QueryBatchOutput"),
    "QuerySqlReportOutput": (
        "algenta.runtime_model_query_metadata",
        "QuerySqlReportOutput",
    ),
    "MojoRuntime": ("algenta.mojo_runtime", "MojoRuntime"),
    "libraries": ("algenta.mojo_entrypoints", "libraries"),
    "MojoRuntimeError": ("algenta.mojo_errors", "MojoRuntimeError"),
    "MojoRuntimeConfigurationError": (
        "algenta.mojo_errors",
        "MojoRuntimeConfigurationError",
    ),
    "MojoModuleNotRegisteredError": ("algenta.mojo_errors", "MojoModuleNotRegisteredError"),
    "MojoFunctionNotRegisteredError": (
        "algenta.mojo_errors",
        "MojoFunctionNotRegisteredError",
    ),
    "MojoExecutionError": ("algenta.mojo_errors", "MojoExecutionError"),
    "CodnaClient": ("algenta.client", "CodnaClient"),
    "Result": ("algenta.simple", "Result"),
    "decision": ("algenta.simple", "decision"),
    "optimize": ("algenta.simple", "optimize"),
    "simulate": ("algenta.simple", "simulate"),
    "forecast": ("algenta.forecast", "forecast"),
    "map_data": ("algenta.map_matching", "map_data"),
    "query_data": ("algenta.map_query", "query_data"),
    "MapResult": ("algenta.map_models", "MapResult"),
    "MappedField": ("algenta.map_models", "FieldMapping"),
    "DEFAULT_BASE_URL": ("algenta._contract", "DEFAULT_BASE_URL"),
    "CONTRACT_VERSION": ("algenta._contract", "CONTRACT_VERSION"),
    "BRAND": ("algenta._contract", "BRAND"),
    "MCP_ENDPOINT": ("algenta._contract", "MCP_ENDPOINT"),
    "MCP_TOOLS_ENDPOINT": ("algenta._contract", "MCP_TOOLS_ENDPOINT"),
    "AUTH_SCHEME": ("algenta._contract", "AUTH_SCHEME"),
    "API_KEY_PREFIX_LIVE": ("algenta._contract", "API_KEY_PREFIX_LIVE"),
    "API_KEY_PREFIX_TEST": ("algenta._contract", "API_KEY_PREFIX_TEST"),
    "LEGACY_HEADERS": ("algenta._contract", "LEGACY_HEADERS"),
    "LEGACY_ENV_VARS": ("algenta._contract", "LEGACY_ENV_VARS"),
    "LEGACY_DOMAINS": ("algenta._contract", "LEGACY_DOMAINS"),
    "DEPRECATION_WINDOW_DAYS": ("algenta._contract", "DEPRECATION_WINDOW_DAYS"),
    "READ_ONLY_DEFAULT": ("algenta._contract", "READ_ONLY_DEFAULT"),
    "WRITE_CONFIRMATION_REQUIRED": (
        "algenta._contract",
        "WRITE_CONFIRMATION_REQUIRED",
    ),
    "PLAN_LIMITS": ("algenta._contract", "PLAN_LIMITS"),
    "INTEGRATIONS": ("algenta._contract", "INTEGRATIONS"),
    "PRIMARY_DATA_QUERY_CONTRACT": ("algenta._contract", "PRIMARY_DATA_QUERY_CONTRACT"),
    "CAPABILITY_PLANE_CONTRACT": ("algenta._contract", "CAPABILITY_PLANE_CONTRACT"),
}

_CONTRACT_EXPORT_NAMES = tuple(
    name for name, export in _LAZY_EXPORTS.items() if export[0] == "algenta._contract"
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
        raise AttributeError(f"module 'algenta' has no attribute '{name}'")
    module_name, attribute_name = export
    module = import_module(module_name)
    if module_name == "algenta._contract":
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
