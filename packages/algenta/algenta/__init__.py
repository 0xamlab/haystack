"""
algenta — runtime-first package for deterministic structured-data execution.

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
Private profiles fail closed and do not silently fall back to Algenta cloud.
"""

from __future__ import annotations

from importlib import import_module

__version__ = "1.0.27"

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
    "AlgentaRuntimeError": ("algenta.runtime_errors", "AlgentaRuntimeError"),
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
    "MemoryEpisodeOutput": ("algenta.runtime_model_memory", "MemoryEpisodeOutput"),
    "MemoryFactOutput": ("algenta.runtime_model_memory", "MemoryFactOutput"),
    "MemoryRecallHit": ("algenta.runtime_model_memory", "MemoryRecallHit"),
    "MemoryRecallOutput": ("algenta.runtime_model_memory", "MemoryRecallOutput"),
    "MemoryCompactionOutput": ("algenta.runtime_model_memory", "MemoryCompactionOutput"),
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
    "AlgentaClient": ("algenta.client", "AlgentaClient"),
    # Backward-compatible alias for integrations that used the former client name.
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
    "MCP_TRANSPORT": ("algenta._contract", "MCP_TRANSPORT"),
    "MCP_PROTOCOL_VERSION": ("algenta._contract", "MCP_PROTOCOL_VERSION"),
    "MCP_LEGACY_SSE_ENDPOINT": ("algenta._contract", "MCP_LEGACY_SSE_ENDPOINT"),
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
    # ── coarse local execution: batch, pipeline, resident datasets, queries ────
    # All local-only surfaces over the bundled Mojo worker. Lazy like everything
    # else here, so importing `algenta` still does not touch the runtime.
    "BatchItem": ("algenta.batch", "BatchItem"),
    "Pipeline": ("algenta.pipeline", "Pipeline"),
    "PipelineShardError": ("algenta.pipeline", "PipelineShardError"),
    "PREV": ("algenta.pipeline", "PREV"),
    "Ref": ("algenta.pipeline", "Ref"),
    "DatasetError": ("algenta.session", "DatasetError"),
    "Expr": ("algenta.query", "Expr"),
    "Query": ("algenta.query", "Query"),
    "QueryError": ("algenta.query", "QueryError"),
    "QueryResult": ("algenta.query", "QueryResult"),
    "col": ("algenta.query", "col"),
    "lit": ("algenta.query", "lit"),
    # ── retrieval: six typed verbs over one explicit backend ───────────────────
    # Appended, never reordered, so no existing export moves. Lazy like the rest:
    # importing `algenta` still probes no engine and touches no runtime, and a
    # backend's availability is only ever resolved when a verb is actually called.
    "BackendStatus": ("algenta.retrieval", "BackendStatus"),
    "CompactionReport": ("algenta.retrieval", "CompactionReport"),
    "RETRIEVAL_BACKENDS": ("algenta.retrieval", "BACKENDS"),
    "RETRIEVAL_FUSIONS": ("algenta.retrieval", "FUSIONS"),
    "RETRIEVAL_LANES": ("algenta.retrieval", "LANES"),
    "RETRIEVAL_METRICS": ("algenta.retrieval", "METRICS"),
    "RETRIEVAL_RERANK_METHODS": ("algenta.retrieval", "RERANK_METHODS"),
    "RETRIEVAL_VERBS": ("algenta.retrieval", "VERBS"),
    "RememberReceipt": ("algenta.retrieval", "RememberReceipt"),
    "Retrieval": ("algenta.retrieval", "Retrieval"),
    "RetrievalCandidate": ("algenta.retrieval", "RetrievalCandidate"),
    "RetrievalDocument": ("algenta.retrieval", "RetrievalDocument"),
    "RetrievalError": ("algenta.retrieval", "RetrievalError"),
    "RetrievalFilter": ("algenta.retrieval", "RetrievalFilter"),
    "RetrievalHit": ("algenta.retrieval", "RetrievalHit"),
    "RetrievalLaneContribution": ("algenta.retrieval", "RetrievalLaneContribution"),
    "RetrievalProvenance": ("algenta.retrieval", "RetrievalProvenance"),
    "RetrievalProvenanceItem": ("algenta.retrieval", "RetrievalProvenanceItem"),
    "RetrievalRequest": ("algenta.retrieval", "RetrievalRequest"),
    "RetrievalResult": ("algenta.retrieval", "RetrievalResult"),
    "backend_status": ("algenta.retrieval", "backend_status"),
    "compact": ("algenta.retrieval", "compact"),
    "filtered_search": ("algenta.retrieval", "filtered_search"),
    "hybrid_search": ("algenta.retrieval", "hybrid_search"),
    "provenance": ("algenta.retrieval", "provenance"),
    "recall": ("algenta.retrieval", "recall"),
    "remember": ("algenta.retrieval", "remember"),
    "rerank": ("algenta.retrieval", "rerank"),
    "sparse_search": ("algenta.retrieval", "sparse_search"),
    "vector_search": ("algenta.retrieval", "vector_search"),
    # Declared kernel capabilities. Additive: nothing above changes shape.
    "UNDECLARED": ("algenta.capabilities", "UNDECLARED"),
    "Undeclared": ("algenta.capabilities", "Undeclared"),
    "CapabilityCatalog": ("algenta.capabilities", "CapabilityCatalog"),
    "CapabilityError": ("algenta.capabilities", "CapabilityError"),
    "CapabilityRecord": ("algenta.capabilities", "CapabilityRecord"),
    "CapabilitySearchResult": ("algenta.capabilities", "CapabilitySearchResult"),
    "CountRelation": ("algenta.capabilities", "CountRelation"),
    "UndeclaredCapability": ("algenta.capabilities", "UndeclaredCapability"),
    "capabilities": ("algenta.capabilities", "capabilities"),
    # ── Qwen3-0.6B-Base decode: one model shape, one hardware family (Apple Silicon/Metal) ──────
    # Appended, never reordered, so no existing export moves. Lazy like the rest: importing
    # `algenta` still probes no engine, and no GPU/checkpoint work happens until
    # `qwen3_i8_allsimd7_decode()` or `prepare_checkpoint()` is actually called.
    "Qwen3DecodeError": ("algenta.qwen3_decode", "Qwen3DecodeError"),
    "Qwen3DecodeResult": ("algenta.qwen3_decode", "Qwen3DecodeResult"),
    "UnsupportedCheckpointArchitectureError": (
        "algenta.qwen3_decode",
        "UnsupportedCheckpointArchitectureError",
    ),
    "prepare_qwen3_checkpoint": ("algenta.qwen3_decode", "prepare_checkpoint"),
    "qwen3_i8_allsimd7_decode": ("algenta.qwen3_decode", "qwen3_i8_allsimd7_decode"),
    # ── Model-agnostic inference: any supported-family model, one hardware family (Apple Silicon/
    # Metal). Generic-named (not model-specific) door onto the same Metal kernel path. Lazy like the
    # rest: no GPU/checkpoint work until decode()/prepare_model_checkpoint() is actually called.
    "InferenceError": ("algenta.inference", "InferenceError"),
    "InferenceResult": ("algenta.inference", "InferenceResult"),
    "UnsupportedArchitectureError": ("algenta.inference", "UnsupportedArchitectureError"),
    "prepare_model_checkpoint": ("algenta.inference", "prepare_model_checkpoint"),
    "prepare_model_checkpoint_from_gguf": (
        "algenta.inference",
        "prepare_model_checkpoint_from_gguf",
    ),
    "decode": ("algenta.inference", "decode"),
    # ── Qwen3-family tokenizer: the checkpoint's own tokenizer.json, implemented here (parity
    # gap 1). Lazy like the rest: no file read until load_tokenizer() is actually called.
    "Tokenizer": ("algenta.tokenizer", "Tokenizer"),
    "TokenizerFormatError": ("algenta.tokenizer", "TokenizerFormatError"),
    "load_tokenizer": ("algenta.tokenizer", "load_tokenizer"),
    # ── Public engine-kernel inventory: the CUDA/Metal kernels the engine races, declared as
    # capability (they are pointer-based and not JSON-callable, so they are not in
    # `runtime_modules()`). Lazy like the rest: no contract read until actually queried.
    "EngineKernelInventory": ("algenta.runtime_library_contract", "EngineKernelInventory"),
    "EngineKernelModule": ("algenta.runtime_library_contract", "EngineKernelModule"),
    "EngineKernelSpec": ("algenta.runtime_library_contract", "EngineKernelSpec"),
    "engine_kernel_backends": ("algenta.runtime_library_contract", "engine_kernel_backends"),
    "engine_kernel_inventory": ("algenta.runtime_library_contract", "engine_kernel_inventory"),
    "engine_kernels": ("algenta.runtime_library_contract", "engine_kernels"),
    # ── `algenta serve`: one gated entry point onto the engine, on either published backend.
    # Appended, never reordered. Lazy like the rest — importing `algenta` probes no accelerator,
    # shells out to no nvidia-smi and reads no checkpoint until plan_serve()/serve() is called.
    # NOTE: there is deliberately NO top-level "serve" export. `algenta.serve` is the SUBPACKAGE,
    # and a lazy attribute of the same name would be cached over the submodule attribute the
    # import machinery sets, so `import algenta.serve.gating` would resolve `algenta.serve` to a
    # function and fail. Call it as `from algenta.serve import serve` — the same shape as
    # `from algenta.inference import decode`.
    "ServeError": ("algenta.serve", "ServeError"),
    "ServeOutcome": ("algenta.serve", "ServeOutcome"),
    "ServePlan": ("algenta.serve", "ServePlan"),
    "ServeRequest": ("algenta.serve", "ServeRequest"),
    "plan_serve": ("algenta.serve", "plan_serve"),
    "serve_backends": ("algenta.serve", "serve_backends"),
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


def check_migration() -> str | None:
    """Detect a stale, file-owning ``algenta-core`` install.

    Return a one-line migration warning for pre-graduation installations,
    or None.

    The ``algenta`` distribution owns the ``algenta`` import + the ``algenta`` command. A legacy,
    file-owning ``algenta-core`` installation can still shadow those files,
    so warn with an explicit uninstall/migration command. Never raises; kept
    OUT of import time (the CLI calls it once at startup).
    """
    try:
        from importlib import metadata

        reqs = metadata.requires("algenta-core") or []
    except Exception:  # noqa: BLE001 — algenta-core not installed (fine) / metadata unavailable
        return None
    depends_on_algenta = any(
        r.split(";")[0].split()[0].strip().lower() == "algenta" for r in reqs if r.split()
    )
    if not depends_on_algenta:
        return (
            "algenta: a legacy `algenta-core` package is installed and may "
            "shadow the supported `algenta` "
            "distribution. Run `pip uninstall algenta-core && pip install --upgrade algenta`."
        )
    return None
