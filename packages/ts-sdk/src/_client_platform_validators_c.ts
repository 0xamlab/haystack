// SPDX-License-Identifier: Apache-2.0
/** Auto-split sub-module of client.ts — platform contract validators (part C). */

/**
 * Algenta TypeScript SDK — fetch-based client.
 * Works in Node.js 18+ and modern browsers.
 *
 * @example
 * import { AlgentaClient } from 'algenta-sdk';
 *
 * const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;
 * if (!apiKey) {
 *   throw new Error('Set ALGENTA_API_KEY or DE_API_KEY before running this example.');
 * }
 * const client = new AlgentaClient({ apiKey });
 * const result = await client.simulate({
 *   mode: 'auto',
 *   scenario: {
 *     variables: { revenue: { low: 80000, high: 200000 } },
 *     objective: 'maximize_net_value',
 *   },
 * });
 * console.log(result.recommended_action, result.confidence);
 *
 * This example is the Cloud Managed path. In `self_hosted` and `air_gapped`,
 * pass an explicit self-hosted `baseUrl` and use the API key provisioned by
 * your self-hosted operator deployment instead. Private profiles fail closed
 * and do not silently fall back to Algenta cloud.
 */

import type {
  APIKeyCreated,
  APIKeyInfo,
  AgentRunCheckpointListResponse,
  AgentRunCheckpointsResponse,
  AgentRunCreateRequest,
  AgentRunEventsResponse,
  AgentRunListResponse,
  AgentRunMissionEventListResponse,
  AgentRunMissionEventsResponse,
  AgentRunReplayResponse,
  AgentRunResponse,
  AgentRunStreamEventResponse,
  AgentRunTelemetryListResponse,
  AgentRunTelemetryResponse,
  AuditLogEntry,
  AuditLogResponse,
  BillingInfoResponse,
  BillingSessionResponse,
  BatchResult,
  ChatCompletionsRequest,
  ChatCompletionsResponse,
  ChatCompletionsStreamChunkResponse,
  ArtifactBridgeResolveRequest,
  ArtifactBridgeResolveResponse,
  CapabilityAuthorizationCompleteRequest,
  CapabilityAuthorizationCompleteResponse,
  CapabilityAuthorizationStartRequest,
  CapabilityAuthorizationStartResponse,
  CapabilityBindingCreateRequest,
  CapabilityBindingPreviewRequest,
  CapabilityBindingResponse,
  CapabilityBindingTestResult,
  CapabilityBindingUpdateRequest,
  CapabilityCatalogEntry,
  CapabilityDiscoverResponse,
  CapabilityExecutionRequest,
  CapabilityExecutionResponse,
  CapabilityOutcomeRecord,
  CapabilityOutcomeRecordRequest,
  CapabilityPlaneContract,
  CapabilityProviderResponse,
  CapabilityRoutePlan,
  CapabilityRouteRequest,
  CompatibilityContract,
  CompareResponse,
  ConnectDataRequest,
  ConnectorBrowseResult,
  ConnectorInfo,
  ConnectorListResult,
  ConnectorTestInfo,
  CountTokensRequest,
  CountTokensResponse,
  CreditRefreshRequest,
  CreditRefreshResponse,
  CreateAPIKeyRequest,
  CreateDeploymentRequest,
  CreateConnectorRequest,
  DecisionListResponse,
  DecisionLogResponse,
  DistributionInfoResponse,
  DistributionListResponse,
  DeviceListEntryResponse,
  DeviceListResponse,
  DeviceRegistrationResponse,
  DeviceRevokeResponse,
  DefaultsContract,
  DecisionEnvelope,
  DecisionEngineClientConfig,
  DecisionPlanResponse,
  ProductAgentRunRequest,
  ProductAgentRunResponse,
  ProductDecisionRequest,
  ProductDecisionResponse,
  ProductForecastRequest,
  ProductForecastResponse,
  ProductOptimizeRequest,
  ProductOptimizeResponse,
  ProductRetrieveRequest,
  ProductRetrieveResponse,
  DeploymentCostResponse,
  DeploymentDeleteResponse,
  DeploymentProviderResponse,
  DeploymentRegionResponse,
  DeploymentRegionsResponse,
  DeploymentResponse,
  DatasetConnectResult,
  DatasetDeleteResult,
  DatasetDetailResult,
  DatasetInfo,
  DatasetListResult,
  DatasetSummaryResult,
  EmbeddingsRequest,
  EmbeddingsResponse,
  EmbeddingSimilarityRequest,
  EmbeddingSimilarityResponse,
  ExecuteDecisionRequest,
  ExecutionReceiptResponse,
  ExecutionPolicyResponse,
  ExecutionPolicySnapshotListResponse,
  ExplainResponse,
  JobListResponse,
  JobStatusResponse,
  JobSubmitResponse,
  WebhookTestResponse,
  LLMModelListResponse,
  LogDecisionRequest,
  MeteringBatchRequest,
  MeteringBatchResponse,
  MeResponse,
  PlatformContractResponse,
  PrivacyRegistryContract,
  PrimaryDataQueryContract,
  PreviewConnectorRequest,
  RepositoryApplyRequest,
  RepositoryApplyResponse,
  RepositoryIntelligenceCapabilitiesResponse,
  RepositoryDecisionPlanCreateRequest,
  RepositoryDecisionPlanRevisionResponse,
  RepositoryGraphQueryRequest,
  RepositoryGraphQueryResponse,
  RepositorySimulationRequest,
  RepositorySnapshotCreateRequest,
  RepositorySnapshotResponse,
  RepositoryTriageRequest,
  RepositoryTriageResponse,
  QueryBatchResponse,
  QueryExecutionMetadata,
  QueryFilterSpec,
  QueryResponse,
  QuerySqlReportRequest,
  QuerySqlReportResponse,
  QueryWithMetadataResponse,
  RecordOutcomeRequest,
  ResponseStreamEventResponse,
  RecommendResponse,
  ResolveResponse,
  RuntimeAdminBenchmarksResponse,
  RuntimeAdminModulesResponse,
  RuntimeBenchmarkClassCode,
  RuntimeCompiledEngine,
  RuntimeLayer,
  RuntimeManifestResponse,
  RuntimeMaturity,
  RuntimeModuleId,
  RuntimeReleaseValidationResponse,
  ScoreResponse,
  SimulateRequest,
  SourceRegistrationRequest,
  SourceRegistrationResponse,
  ResponsesRequest,
  ResponsesResponse,
  RerankRequest,
  RerankResponse,
  TokenizeRequest,
  TokenizeResponse,
  TeamListResponse,
  TeamInviteRequest,
  TeamInviteResponse,
  TeamMemberInfo,
  TemplateInfoResponse,
  TemplateListResponse,
  TriggerDeleteResponse,
  TriggerFireResponse,
  TriggerListResponse,
  TriggerPauseResponse,
  TriggerResponse,
  RegisterTriggerRequest,
  TeamRemoveResponse,
  TeamRoleUpdateResponse,
  UpdateMeRequest,
  UpdateConnectorRequest,
  UpdateExecutionPolicyRequest,
  UsageInfo,
  VerifyResponse,
  LimitsInfo,
} from './types.js';
import {
  ALGENTA_OWNED_HOSTS,
  ALGENTA_OWNED_SUFFIXES,
  API_KEY_PREFIX_LIVE,
  API_KEY_PREFIX_TEST,
  AUTH_SCHEME,
  BRAND,
  CONTRACT_VERSION,
  DEFAULT_BASE_URL,
  DEPRECATION_WINDOW_DAYS,
  INTEGRATIONS,
  LEGACY_DOMAINS,
  LEGACY_ENV_VARS,
  LEGACY_HEADERS,
  MCP_ENDPOINT,
  MCP_TOOLS_ENDPOINT,
  PLAN_LIMITS,
  PRIVATE_HOST_SUFFIXES,
  CAPABILITY_PLANE_CONTRACT,
  PRIMARY_DATA_QUERY_CONTRACT,
  READ_ONLY_DEFAULT,
  VENDOR_TELEMETRY_HOSTS,
  WRITE_CONFIRMATION_REQUIRED,
} from './contract.js';
import { DEVICE_ID_HEADER, resolveClientDeviceHeaders } from './client_device_headers.js';
import {
  DEVICE_BINDING_TOKEN_HEADER,
  loadHostedDeviceBindingToken,
  persistHostedDeviceBindingToken,
} from './client_device_binding.js';
import { apiKeyHelpText, resolveClientBaseUrl } from './privacy_profile.js';


import {
  RUNTIME_ADMIN_ENDPOINT_VALUES,
  RUNTIME_ARTIFACT_LINEAGE_STEP_VALUES,
  RUNTIME_AUXILIARY_CHANNEL_VALUES,
  RUNTIME_BENCHMARK_BASELINE_VALUES,
  RUNTIME_BENCHMARK_CLASS_VALUES,
  RUNTIME_BENCHMARK_METRIC_VALUES,
  RUNTIME_CAPABILITY_FIELD_VALUES,
  RUNTIME_CAPABILITY_RULE_VALUES,
  RUNTIME_COMPILED_ENGINE_VALUES,
  RUNTIME_DEPLOYMENT_MODE_VALUES,
  RUNTIME_EVALUATION_DIMENSION_VALUES,
  RUNTIME_EVALUATION_METHOD_VALUES,
  RUNTIME_EXECUTION_STATE_FIELD_VALUES,
  RUNTIME_EXECUTION_TRANSITION_VALUES,
  RUNTIME_EXECUTION_VALIDITY_RULE_VALUES,
  RUNTIME_EXTERNAL_NONDETERMINISM_SOURCE_VALUES,
  RUNTIME_FAILURE_CODE_VALUES,
  RUNTIME_FEATURE_FLAG_CHANNEL_VALUES,
  RUNTIME_FEATURE_FLAG_ENDPOINT_VALUES,
  RUNTIME_KERNEL_PROMOTION_STATUS_VALUES,
  RUNTIME_LAYER_VALUES,
  RUNTIME_LINEAGE_NODE_FIELD_VALUES,
  RUNTIME_MATURITY_VALUES,
  RUNTIME_MEMORY_REGION_VALUES,
  RUNTIME_MEMORY_RULE_VALUES,
  RUNTIME_MODULE_ID_VALUES,
  RUNTIME_NONDETERMINISM_ARTIFACT_VALUES,
  RUNTIME_PROOF_OBLIGATION_VALUES,
  RUNTIME_PUBLIC_ENDPOINT_VALUES,
  RUNTIME_RELEASE_ARTIFACT_VALUES,
  RUNTIME_RELEASE_BLOCKER_VALUES,
  RUNTIME_RELEASE_CONDITION_VALUES,
  RUNTIME_RELEASE_GATE_VALUES,
  RUNTIME_REPLAYABILITY_VALUES,
  RUNTIME_RISK_LEVEL_VALUES,
  RUNTIME_SCHEDULER_INVARIANT_VALUES,
  RUNTIME_SCHEDULER_MAXIMIZE_VALUES,
  RUNTIME_SCHEDULER_MINIMIZE_VALUES,
  RUNTIME_SCHEDULER_POLICY_VALUES,
  RUNTIME_SIDE_EFFECT_CLASS_VALUES,
  RUNTIME_SLO_BUDGET_APPLIES_TO_VALUES,
  RUNTIME_SLO_BUDGET_NAME_VALUES,
  RUNTIME_SUPPORTED_CHANNEL_VALUES,
  RUNTIME_THREAT_CLASS_VALUES,
  RUNTIME_THREAT_CONTROL_VALUES,
  RUNTIME_THREAT_RULE_VALUES,
} from "./_client_constants.js";
import { DecisionEngineError } from "./_client_errors.js";
import { assertStringArray } from "./_client_platform_validators_a1.js";
import { assertArray, assertBoolean, assertEnumArray, assertEnumKeyedCountRecord, assertEnumValue, assertFiniteNumber, assertInteger, assertJsonObject, assertNonEmptyString, assertUniqueRuntimeObjectField, assertUniqueRuntimeValues, buildStructuredValidationError } from "./_client_platform_validators_b2.js";

export function assertRuntimeModuleManifestEntry(
  payload: unknown,
  context: string,
): {
  name: RuntimeModuleId;
  functionCount: number;
  functions: string[];
  layer: RuntimeLayer;
  maturity: RuntimeMaturity;
  benchmarkSpeedupX: number;
  promotionStatus: "candidate" | "shipping";
} {
  const obj = assertJsonObject(payload, context);
  const name = assertEnumValue(obj.name, RUNTIME_MODULE_ID_VALUES, `${context}.name`);
  assertNonEmptyString(obj.capability_id, `${context}.capability_id`);
  assertNonEmptyString(obj.owner, `${context}.owner`);
  assertNonEmptyString(obj.contract_boundary, `${context}.contract_boundary`);
  const functionCount = assertInteger(obj.function_count, `${context}.function_count`);
  const functions = assertStringArray(obj.functions, `${context}.functions`);
  assertUniqueRuntimeValues(functions, `${context}.functions`);
  if (functions.length !== functionCount) {
    throw buildStructuredValidationError(
      `${context}.functions`,
      `${context}.functions must contain exactly ${functionCount} entries to match function_count.`,
      "value_error",
    );
  }
  const layer = assertEnumValue(obj.layer, RUNTIME_LAYER_VALUES, `${context}.layer`);
  const maturity = assertEnumValue(obj.maturity, RUNTIME_MATURITY_VALUES, `${context}.maturity`);
  const publicSupportedChannels = assertEnumArray(
    obj.public_supported_channels,
    RUNTIME_SUPPORTED_CHANNEL_VALUES,
    `${context}.public_supported_channels`,
  );
  assertUniqueRuntimeValues(publicSupportedChannels, `${context}.public_supported_channels`);
  const validatedAuxiliaryChannels = assertEnumArray(
    obj.validated_auxiliary_channels,
    RUNTIME_AUXILIARY_CHANNEL_VALUES,
    `${context}.validated_auxiliary_channels`,
  );
  assertUniqueRuntimeValues(
    validatedAuxiliaryChannels,
    `${context}.validated_auxiliary_channels`,
  );
  const featureFlagChannels = assertEnumArray(
    obj.feature_flag_channels,
    RUNTIME_FEATURE_FLAG_CHANNEL_VALUES,
    `${context}.feature_flag_channels`,
  );
  assertUniqueRuntimeValues(featureFlagChannels, `${context}.feature_flag_channels`);
  const proofObligations = assertEnumArray(
    obj.proof_obligations,
    RUNTIME_PROOF_OBLIGATION_VALUES,
    `${context}.proof_obligations`,
  );
  assertUniqueRuntimeValues(proofObligations, `${context}.proof_obligations`);
  const proofArtifacts = assertStringArray(obj.proof_artifacts, `${context}.proof_artifacts`);
  assertUniqueRuntimeValues(proofArtifacts, `${context}.proof_artifacts`);
  const promotionStatus = assertEnumValue(
    obj.promotion_status,
    RUNTIME_KERNEL_PROMOTION_STATUS_VALUES,
    `${context}.promotion_status`,
  );
  assertNonEmptyString(obj.rollback_flag, `${context}.rollback_flag`);
  assertNonEmptyString(obj.benchmark_report_ref, `${context}.benchmark_report_ref`);
  assertNonEmptyString(obj.parity_report_ref, `${context}.parity_report_ref`);
  assertNonEmptyString(obj.schema_compat_report_ref, `${context}.schema_compat_report_ref`);
  assertNonEmptyString(obj.isolation_proof_ref, `${context}.isolation_proof_ref`);
  assertNonEmptyString(obj.replay_proof_ref, `${context}.replay_proof_ref`);
  assertNonEmptyString(obj.benchmark_artifact, `${context}.benchmark_artifact`);
  const benchmarkSpeedupX = assertFiniteNumber(
    obj.benchmark_speedup_x,
    `${context}.benchmark_speedup_x`,
  );
  assertNonEmptyString(obj.compiled_artifact, `${context}.compiled_artifact`);
  assertEnumValue(obj.compiled_engine, RUNTIME_COMPILED_ENGINE_VALUES, `${context}.compiled_engine`);
  assertFiniteNumber(obj.max_cold_ms, `${context}.max_cold_ms`);
  assertFiniteNumber(obj.max_warm_ms, `${context}.max_warm_ms`);
  assertFiniteNumber(obj.max_hot_ms, `${context}.max_hot_ms`);
  return { name, functionCount, functions, layer, maturity, benchmarkSpeedupX, promotionStatus };
}

export function assertRuntimeAdvertisedCapabilities(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const runtimeModules = assertEnumArray(
    obj.runtime_modules,
    RUNTIME_MODULE_ID_VALUES,
    `${context}.runtime_modules`,
  );
  assertUniqueRuntimeValues(runtimeModules, `${context}.runtime_modules`);
  const publicEndpoints = assertEnumArray(
    obj.public_endpoints,
    RUNTIME_PUBLIC_ENDPOINT_VALUES,
    `${context}.public_endpoints`,
  );
  assertUniqueRuntimeValues(publicEndpoints, `${context}.public_endpoints`);
  const adminEndpoints = assertEnumArray(
    obj.admin_endpoints,
    RUNTIME_ADMIN_ENDPOINT_VALUES,
    `${context}.admin_endpoints`,
  );
  assertUniqueRuntimeValues(adminEndpoints, `${context}.admin_endpoints`);
  const featureFlagEndpoints = assertEnumArray(
    obj.feature_flag_endpoints,
    RUNTIME_FEATURE_FLAG_ENDPOINT_VALUES,
    `${context}.feature_flag_endpoints`,
  );
  assertUniqueRuntimeValues(featureFlagEndpoints, `${context}.feature_flag_endpoints`);
}

export function assertRuntimeNamedRule(
  payload: unknown,
  context: string,
  allowedNames: readonly string[],
  nameField: string,
): void {
  const obj = assertJsonObject(payload, context);
  assertEnumValue(obj[nameField], allowedNames, `${context}.${nameField}`);
  assertNonEmptyString(obj.statement, `${context}.statement`);
}

export function assertRuntimeExecutionModel(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const stateFields = assertEnumArray(
    obj.state_fields,
    RUNTIME_EXECUTION_STATE_FIELD_VALUES,
    `${context}.state_fields`,
  );
  assertUniqueRuntimeValues(stateFields, `${context}.state_fields`);
  const allowedTransitions = assertEnumArray(
    obj.allowed_transitions,
    RUNTIME_EXECUTION_TRANSITION_VALUES,
    `${context}.allowed_transitions`,
  );
  assertUniqueRuntimeValues(allowedTransitions, `${context}.allowed_transitions`);
  const validityRules = assertEnumArray(
    obj.validity_rules,
    RUNTIME_EXECUTION_VALIDITY_RULE_VALUES,
    `${context}.validity_rules`,
  );
  assertUniqueRuntimeValues(validityRules, `${context}.validity_rules`);
}

export function assertRuntimeExternalNondeterminismPolicy(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const sources = assertEnumArray(
    obj.sources,
    RUNTIME_EXTERNAL_NONDETERMINISM_SOURCE_VALUES,
    `${context}.sources`,
  );
  assertUniqueRuntimeValues(sources, `${context}.sources`);
  assertNonEmptyString(obj.rule, `${context}.rule`);
  const requiredArtifacts = assertEnumArray(
    obj.required_artifacts,
    RUNTIME_NONDETERMINISM_ARTIFACT_VALUES,
    `${context}.required_artifacts`,
  );
  assertUniqueRuntimeValues(requiredArtifacts, `${context}.required_artifacts`);
  const failureCodes = assertEnumArray(
    obj.failure_codes,
    RUNTIME_FAILURE_CODE_VALUES,
    `${context}.failure_codes`,
  );
  assertUniqueRuntimeValues(failureCodes, `${context}.failure_codes`);
}

export function assertRuntimeArtifactLineageSchema(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const artifactFlow = assertEnumArray(
    obj.artifact_flow,
    RUNTIME_ARTIFACT_LINEAGE_STEP_VALUES,
    `${context}.artifact_flow`,
  );
  assertUniqueRuntimeValues(artifactFlow, `${context}.artifact_flow`);
  const requiredNodeFields = assertEnumArray(
    obj.required_node_fields,
    RUNTIME_LINEAGE_NODE_FIELD_VALUES,
    `${context}.required_node_fields`,
  );
  assertUniqueRuntimeValues(requiredNodeFields, `${context}.required_node_fields`);
  assertNonEmptyString(obj.immutability_rule, `${context}.immutability_rule`);
}

export function assertRuntimeCapabilityAlgebra(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const requiredFields = assertEnumArray(
    obj.required_fields,
    RUNTIME_CAPABILITY_FIELD_VALUES,
    `${context}.required_fields`,
  );
  assertUniqueRuntimeValues(requiredFields, `${context}.required_fields`);
  const enums = assertJsonObject(obj.enums, `${context}.enums`);
  const sideEffectClass = assertEnumArray(
    enums.side_effect_class,
    RUNTIME_SIDE_EFFECT_CLASS_VALUES,
    `${context}.enums.side_effect_class`,
  );
  assertUniqueRuntimeValues(sideEffectClass, `${context}.enums.side_effect_class`);
  const riskLevels = assertEnumArray(
    enums.risk_level,
    RUNTIME_RISK_LEVEL_VALUES,
    `${context}.enums.risk_level`,
  );
  assertUniqueRuntimeValues(riskLevels, `${context}.enums.risk_level`);
  const replayability = assertEnumArray(
    enums.replayability,
    RUNTIME_REPLAYABILITY_VALUES,
    `${context}.enums.replayability`,
  );
  assertUniqueRuntimeValues(replayability, `${context}.enums.replayability`);
  const rules = assertEnumArray(obj.rules, RUNTIME_CAPABILITY_RULE_VALUES, `${context}.rules`);
  assertUniqueRuntimeValues(rules, `${context}.rules`);
}

export function assertRuntimeKernelPromotionCriteria(payload: unknown, context: string): {
  minimumPrimaryMetricImprovementPct: number;
} {
  const obj = assertJsonObject(payload, context);
  const requiredManifestFields = assertStringArray(
    obj.required_manifest_fields,
    `${context}.required_manifest_fields`,
  );
  assertUniqueRuntimeValues(requiredManifestFields, `${context}.required_manifest_fields`);
  const requiredProofReferenceFields = assertStringArray(
    obj.required_proof_reference_fields,
    `${context}.required_proof_reference_fields`,
  );
  assertUniqueRuntimeValues(
    requiredProofReferenceFields,
    `${context}.required_proof_reference_fields`,
  );
  assertNonEmptyString(
    obj.deterministic_test_corpus_rule,
    `${context}.deterministic_test_corpus_rule`,
  );
  assertNonEmptyString(obj.python_parity_rule, `${context}.python_parity_rule`);
  assertNonEmptyString(
    obj.schema_compatibility_rule,
    `${context}.schema_compatibility_rule`,
  );
  const minimumPrimaryMetricImprovementPct = assertFiniteNumber(
    obj.minimum_primary_metric_improvement_pct,
    `${context}.minimum_primary_metric_improvement_pct`,
  );
  const maximumAdjacentMetricRegressionPct = assertFiniteNumber(
    obj.maximum_adjacent_metric_regression_pct,
    `${context}.maximum_adjacent_metric_regression_pct`,
  );
  if (minimumPrimaryMetricImprovementPct <= 0) {
    throw buildStructuredValidationError(
      `${context}.minimum_primary_metric_improvement_pct`,
      `${context}.minimum_primary_metric_improvement_pct must be greater than 0.`,
      "value_error",
    );
  }
  if (maximumAdjacentMetricRegressionPct < 0) {
    throw buildStructuredValidationError(
      `${context}.maximum_adjacent_metric_regression_pct`,
      `${context}.maximum_adjacent_metric_regression_pct must be greater than or equal to 0.`,
      "value_error",
    );
  }
  assertNonEmptyString(obj.benchmark_exception_rule, `${context}.benchmark_exception_rule`);
  assertNonEmptyString(obj.rollback_scope_rule, `${context}.rollback_scope_rule`);
  assertNonEmptyString(obj.tenant_isolation_rule, `${context}.tenant_isolation_rule`);
  assertNonEmptyString(
    obj.replay_compatibility_rule,
    `${context}.replay_compatibility_rule`,
  );
  return { minimumPrimaryMetricImprovementPct };
}

export function assertRuntimeLayerProofMatrixEntry(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertEnumValue(obj.layer, RUNTIME_LAYER_VALUES, `${context}.layer`);
  assertEnumValue(obj.status, RUNTIME_MATURITY_VALUES, `${context}.status`);
  const obligations = assertEnumArray(
    obj.obligations,
    RUNTIME_PROOF_OBLIGATION_VALUES,
    `${context}.obligations`,
  );
  assertUniqueRuntimeValues(obligations, `${context}.obligations`);
  const evidencePaths = assertStringArray(obj.evidence_paths, `${context}.evidence_paths`);
  assertUniqueRuntimeValues(evidencePaths, `${context}.evidence_paths`);
}

export function assertRuntimeBenchmarkFramework(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const classes = assertArray(obj.classes, `${context}.classes`);
  classes.forEach((entry, index) => {
    const benchmarkClass = assertJsonObject(entry, `${context}.classes[${index}]`);
    assertEnumValue(benchmarkClass.code, RUNTIME_BENCHMARK_CLASS_VALUES, `${context}.classes[${index}].code`);
    assertNonEmptyString(benchmarkClass.description, `${context}.classes[${index}].description`);
  });
  assertUniqueRuntimeObjectField(classes, "code", `${context}.classes`);
  const requiredMetrics = assertEnumArray(
    obj.required_metrics,
    RUNTIME_BENCHMARK_METRIC_VALUES,
    `${context}.required_metrics`,
  );
  assertUniqueRuntimeValues(requiredMetrics, `${context}.required_metrics`);
  const baselines = assertEnumArray(
    obj.baselines,
    RUNTIME_BENCHMARK_BASELINE_VALUES,
    `${context}.baselines`,
  );
  assertUniqueRuntimeValues(baselines, `${context}.baselines`);
}

export function assertRuntimeSLOBudget(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertEnumValue(obj.name, RUNTIME_SLO_BUDGET_NAME_VALUES, `${context}.name`);
  assertEnumValue(obj.applies_to, RUNTIME_SLO_BUDGET_APPLIES_TO_VALUES, `${context}.applies_to`);
  assertFiniteNumber(obj.p95_objective_ms, `${context}.p95_objective_ms`);
  if (obj.hard_ceiling_ms !== undefined && obj.hard_ceiling_ms !== null) {
    assertFiniteNumber(obj.hard_ceiling_ms, `${context}.hard_ceiling_ms`);
  }
  if (obj.notes !== undefined && obj.notes !== null) {
    assertNonEmptyString(obj.notes, `${context}.notes`);
  }
}

export function assertRuntimeSchedulerModel(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const policies = assertEnumArray(
    obj.policies,
    RUNTIME_SCHEDULER_POLICY_VALUES,
    `${context}.policies`,
  );
  assertUniqueRuntimeValues(policies, `${context}.policies`);
  const minimize = assertEnumArray(
    obj.minimize,
    RUNTIME_SCHEDULER_MINIMIZE_VALUES,
    `${context}.minimize`,
  );
  assertUniqueRuntimeValues(minimize, `${context}.minimize`);
  const maximize = assertEnumArray(
    obj.maximize,
    RUNTIME_SCHEDULER_MAXIMIZE_VALUES,
    `${context}.maximize`,
  );
  assertUniqueRuntimeValues(maximize, `${context}.maximize`);
  const invariants = assertEnumArray(
    obj.invariants,
    RUNTIME_SCHEDULER_INVARIANT_VALUES,
    `${context}.invariants`,
  );
  assertUniqueRuntimeValues(invariants, `${context}.invariants`);
}

export function assertRuntimeMemoryModel(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const regions = assertEnumArray(obj.regions, RUNTIME_MEMORY_REGION_VALUES, `${context}.regions`);
  assertUniqueRuntimeValues(regions, `${context}.regions`);
  const rules = assertEnumArray(obj.rules, RUNTIME_MEMORY_RULE_VALUES, `${context}.rules`);
  assertUniqueRuntimeValues(rules, `${context}.rules`);
  const failureCodes = assertEnumArray(
    obj.failure_codes,
    RUNTIME_FAILURE_CODE_VALUES,
    `${context}.failure_codes`,
  );
  assertUniqueRuntimeValues(failureCodes, `${context}.failure_codes`);
}

export function assertRuntimeEvaluationScience(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const dimensions = assertEnumArray(
    obj.dimensions,
    RUNTIME_EVALUATION_DIMENSION_VALUES,
    `${context}.dimensions`,
  );
  assertUniqueRuntimeValues(dimensions, `${context}.dimensions`);
  const methods = assertEnumArray(
    obj.methods,
    RUNTIME_EVALUATION_METHOD_VALUES,
    `${context}.methods`,
  );
  assertUniqueRuntimeValues(methods, `${context}.methods`);
  const releaseBlockers = assertEnumArray(
    obj.release_blockers,
    RUNTIME_RELEASE_BLOCKER_VALUES,
    `${context}.release_blockers`,
  );
  assertUniqueRuntimeValues(releaseBlockers, `${context}.release_blockers`);
}

export function assertRuntimeAdminEvaluationSummary(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertInteger(obj.dimension_count, `${context}.dimension_count`);
  assertInteger(obj.method_count, `${context}.method_count`);
  assertInteger(obj.release_blocker_count, `${context}.release_blocker_count`);
  assertInteger(obj.benchmark_class_count, `${context}.benchmark_class_count`);
  assertInteger(obj.slo_budget_count, `${context}.slo_budget_count`);
  assertBoolean(obj.replay_gate_enabled, `${context}.replay_gate_enabled`);
  assertBoolean(
    obj.tool_call_quality_gate_enabled,
    `${context}.tool_call_quality_gate_enabled`,
  );
  assertBoolean(obj.rag_quality_gate_enabled, `${context}.rag_quality_gate_enabled`);
  assertBoolean(
    obj.decision_quality_gate_enabled,
    `${context}.decision_quality_gate_enabled`,
  );
}

export function assertRuntimeTypedFailure(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertEnumValue(obj.code, RUNTIME_FAILURE_CODE_VALUES, `${context}.code`);
  assertNonEmptyString(obj.description, `${context}.description`);
}

export function assertRuntimeThreatModel(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const threatClasses = assertEnumArray(
    obj.threat_classes,
    RUNTIME_THREAT_CLASS_VALUES,
    `${context}.threat_classes`,
  );
  assertUniqueRuntimeValues(threatClasses, `${context}.threat_classes`);
  const controls = assertEnumArray(
    obj.controls,
    RUNTIME_THREAT_CONTROL_VALUES,
    `${context}.controls`,
  );
  assertUniqueRuntimeValues(controls, `${context}.controls`);
  const nonNegotiableRules = assertEnumArray(
    obj.non_negotiable_rules,
    RUNTIME_THREAT_RULE_VALUES,
    `${context}.non_negotiable_rules`,
  );
  assertUniqueRuntimeValues(nonNegotiableRules, `${context}.non_negotiable_rules`);
}

export function assertRuntimeFormalReleaseTheorem(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.statement, `${context}.statement`);
  const requiredConditions = assertEnumArray(
    obj.required_conditions,
    RUNTIME_RELEASE_CONDITION_VALUES,
    `${context}.required_conditions`,
  );
  assertUniqueRuntimeValues(requiredConditions, `${context}.required_conditions`);
}

export function assertRuntimeReleaseArtifactBundle(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const requiredArtifacts = assertEnumArray(
    obj.required_artifacts,
    RUNTIME_RELEASE_ARTIFACT_VALUES,
    `${context}.required_artifacts`,
  );
  assertUniqueRuntimeValues(requiredArtifacts, `${context}.required_artifacts`);
}

export function assertRuntimeReleaseGate(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertEnumValue(obj.gate, RUNTIME_RELEASE_GATE_VALUES, `${context}.gate`);
  assertNonEmptyString(obj.description, `${context}.description`);
}

export function assertRuntimeImplementationStep(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.pr, `${context}.pr`);
  assertNonEmptyString(obj.focus, `${context}.focus`);
  assertStringArray(obj.deliverables, `${context}.deliverables`);
}

export function assertRuntimeDeploymentModes(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertEnumValue(obj.current, RUNTIME_DEPLOYMENT_MODE_VALUES, `${context}.current`);
  const supportedModes = assertEnumArray(
    obj.supported_modes,
    RUNTIME_DEPLOYMENT_MODE_VALUES,
    `${context}.supported_modes`,
  );
  assertUniqueRuntimeValues(supportedModes, `${context}.supported_modes`);
  assertNonEmptyString(obj.rule, `${context}.rule`);
}

export function assertRuntimeAdminModuleSummary(
  payload: unknown,
  context: string,
): {
  moduleCount: number;
  functionCount: number;
  maturityCounts: Partial<Record<RuntimeMaturity, number>>;
  layerCounts: Partial<Record<RuntimeLayer, number>>;
} {
  const obj = assertJsonObject(payload, context);
  const moduleCount = assertInteger(obj.module_count, `${context}.module_count`);
  const functionCount = assertInteger(obj.function_count, `${context}.function_count`);
  const maturityCounts = assertEnumKeyedCountRecord(
    obj.maturity_counts,
    RUNTIME_MATURITY_VALUES,
    `${context}.maturity_counts`,
  );
  const layerCounts = assertEnumKeyedCountRecord(
    obj.layer_counts,
    RUNTIME_LAYER_VALUES,
    `${context}.layer_counts`,
  );
  return { moduleCount, functionCount, maturityCounts, layerCounts };
}

export function countRuntimeValues(values: readonly string[]): Record<string, number> {
  return values.reduce<Record<string, number>>((counts, value) => {
    counts[value] = (counts[value] ?? 0) + 1;
    return counts;
  }, {});
}

export function assertCountRecordMatches(
  actual: Partial<Record<string, number>>,
  expected: Record<string, number>,
  context: string,
  label: string,
): void {
  const actualKeys = Object.keys(actual).sort();
  const expectedKeys = Object.keys(expected).sort();
  if (
    actualKeys.length !== expectedKeys.length ||
    actualKeys.some((key, index) => key !== expectedKeys[index]) ||
    expectedKeys.some(key => actual[key] !== expected[key])
  ) {
    throw buildStructuredValidationError(
      context,
      `${context} must equal the module ${label} distribution.`,
      "value_error",
    );
  }
}

export function assertRuntimeBenchmarkModuleEntry(
  payload: unknown,
  context: string,
): {
  name: RuntimeModuleId;
  functionCount: number;
  benchmarkArtifact: string;
  benchmarkSpeedupX: number;
  compiledArtifact: string;
  compiledEngine: RuntimeCompiledEngine;
  maxColdMs: number;
  maxWarmMs: number;
  maxHotMs: number;
} {
  const obj = assertJsonObject(payload, context);
  const name = assertEnumValue(obj.name, RUNTIME_MODULE_ID_VALUES, `${context}.name`);
  const functionCount = assertInteger(obj.function_count, `${context}.function_count`);
  const benchmarkArtifact = assertNonEmptyString(
    obj.benchmark_artifact,
    `${context}.benchmark_artifact`,
  );
  const benchmarkSpeedupX = assertFiniteNumber(obj.benchmark_speedup_x, `${context}.benchmark_speedup_x`);
  const compiledArtifact = assertNonEmptyString(
    obj.compiled_artifact,
    `${context}.compiled_artifact`,
  );
  const compiledEngine = assertEnumValue(
    obj.compiled_engine,
    RUNTIME_COMPILED_ENGINE_VALUES,
    `${context}.compiled_engine`,
  );
  const maxColdMs = assertFiniteNumber(obj.max_cold_ms, `${context}.max_cold_ms`);
  const maxWarmMs = assertFiniteNumber(obj.max_warm_ms, `${context}.max_warm_ms`);
  const maxHotMs = assertFiniteNumber(obj.max_hot_ms, `${context}.max_hot_ms`);
  return {
    name,
    functionCount,
    benchmarkArtifact,
    benchmarkSpeedupX,
    compiledArtifact,
    compiledEngine,
    maxColdMs,
    maxWarmMs,
    maxHotMs,
  };
}

export function assertRuntimeBenchmarkClassEntry(
  payload: unknown,
  context: string,
): {
  code: RuntimeBenchmarkClassCode;
  description: string;
  evidence_paths: string[];
} {
  const obj = assertJsonObject(payload, context);
  const code = assertEnumValue(obj.code, RUNTIME_BENCHMARK_CLASS_VALUES, `${context}.code`);
  const description = assertNonEmptyString(obj.description, `${context}.description`);
  const evidencePaths =
    obj.evidence_paths === undefined
      ? []
      : assertStringArray(obj.evidence_paths, `${context}.evidence_paths`);
  assertUniqueRuntimeValues(evidencePaths, `${context}.evidence_paths`);
  return { code, description, evidence_paths: evidencePaths };
}

export function assertRuntimeReleaseConditionEvaluation(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertEnumValue(obj.condition, RUNTIME_RELEASE_CONDITION_VALUES, `${context}.condition`);
  assertBoolean(obj.satisfied, `${context}.satisfied`);
  assertNonEmptyString(obj.detail, `${context}.detail`);
  const evidencePaths = assertStringArray(obj.evidence_paths, `${context}.evidence_paths`);
  assertUniqueRuntimeValues(evidencePaths, `${context}.evidence_paths`);
}

export function wrapRuntimeValidation<T>(
  context: string,
  payload: unknown,
  validator: (value: unknown) => T,
): T {
  try {
    return validator(payload);
  } catch (error) {
    if (error instanceof DecisionEngineError) {
      const details =
        error.details && typeof error.details === "object" && !Array.isArray(error.details)
          ? error.details
          : { cause: error.message };
      throw new DecisionEngineError(
        `${context} returned an invalid signed payload: ${error.message}`,
        0,
        "invalid_runtime_contract_payload",
        {
          error: {
            code: "invalid_runtime_contract_payload",
            details,
          },
        },
      );
    }
    throw error;
  }
}

