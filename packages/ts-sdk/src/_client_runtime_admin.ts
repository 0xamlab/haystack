/** Auto-split sub-module of client.ts — runtime admin modules + benchmarks validators. */

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
  RUNTIME_BENCHMARK_CLASS_VALUES,
  RUNTIME_COMPILED_ENGINE_VALUES,
  RUNTIME_EVALUATION_DIMENSION_VALUES,
  RUNTIME_EVALUATION_METHOD_VALUES,
  RUNTIME_MODULE_ID_VALUES,
  RUNTIME_RELEASE_BLOCKER_VALUES,
  RUNTIME_SLO_BUDGET_NAME_VALUES,
} from "./_client_constants.js";
import { assertArray, assertBoolean, assertEnumArray, assertEnumValue, assertFiniteNumber, assertInteger, assertJsonObject, assertNonEmptyString, assertRuntimeArtifactReference, assertRuntimeBenchmarkDiscoveryLane, assertRuntimeShippingContractSummary, assertRuntimeSignature, assertUniqueRuntimeObjectField, assertUniqueRuntimeValues, buildStructuredValidationError } from "./_client_platform_validators_b2.js";
import {
  assertCountRecordMatches,
  assertRuntimeAdminEvaluationSummary,
  assertRuntimeAdminModuleSummary,
  assertRuntimeBenchmarkClassEntry,
  assertRuntimeBenchmarkFramework,
  assertRuntimeBenchmarkModuleEntry,
  assertRuntimeEvaluationScience,
  assertRuntimeLayerProofMatrixEntry,
  assertRuntimeModuleManifestEntry,
  assertRuntimeSLOBudget,
  countRuntimeValues,
  wrapRuntimeValidation,
} from "./_client_platform_validators_c.js";

export function assertRuntimeAdminModulesResponse(payload: unknown): RuntimeAdminModulesResponse {
  return wrapRuntimeValidation("Algenta runtime admin modules endpoint", payload, value => {
    const obj = assertJsonObject(value, "Algenta runtime admin modules response");
    assertNonEmptyString(obj.runtime_version, "Algenta runtime admin modules response.runtime_version");
    assertNonEmptyString(obj.llm_core_manifest, "Algenta runtime admin modules response.llm_core_manifest");
    assertNonEmptyString(
      obj.module_manifest_version,
      "Algenta runtime admin modules response.module_manifest_version",
    );
    const shippingContract = assertRuntimeShippingContractSummary(
      obj.shipping_contract,
      "Algenta runtime admin modules response.shipping_contract",
    );
    const summary = assertRuntimeAdminModuleSummary(
      obj.summary,
      "Algenta runtime admin modules response.summary",
    );
    const proofMatrix = assertArray(
      obj.proof_matrix,
      "Algenta runtime admin modules response.proof_matrix",
    );
    proofMatrix.forEach((entry, index) =>
        assertRuntimeLayerProofMatrixEntry(
          entry,
          `Algenta runtime admin modules response.proof_matrix[${index}]`,
        ),
    );
    assertUniqueRuntimeObjectField(
      proofMatrix,
      "layer",
      "Algenta runtime admin modules response.proof_matrix",
    );
    const modules = assertArray(obj.modules, "Algenta runtime admin modules response.modules");
    const validatedModules = modules.map((entry, index) =>
      assertRuntimeModuleManifestEntry(
        entry,
        `Algenta runtime admin modules response.modules[${index}]`,
      ),
    );
    assertUniqueRuntimeValues(
      validatedModules.map(entry => entry.name),
      "Algenta runtime admin modules response.modules",
    );
    assertNonEmptyString(obj.manifest_digest, "Algenta runtime admin modules response.manifest_digest");
    assertRuntimeSignature(obj.signature, "Algenta runtime admin modules response.signature");
    const totalFunctions = validatedModules.reduce((sum, entry) => sum + entry.functionCount, 0);
    if (shippingContract.moduleCount !== validatedModules.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin modules response.shipping_contract.module_count",
        "Algenta runtime admin modules response.shipping_contract.module_count must equal the number of manifest modules.",
        "value_error",
      );
    }
    if (shippingContract.functionCount !== totalFunctions) {
      throw buildStructuredValidationError(
        "Algenta runtime admin modules response.shipping_contract.function_count",
        "Algenta runtime admin modules response.shipping_contract.function_count must equal the total module function_count.",
        "value_error",
      );
    }
    if (summary.moduleCount !== validatedModules.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin modules response.summary.module_count",
        "Algenta runtime admin modules response.summary.module_count must equal the number of manifest modules.",
        "value_error",
      );
    }
    if (summary.functionCount !== totalFunctions) {
      throw buildStructuredValidationError(
        "Algenta runtime admin modules response.summary.function_count",
        "Algenta runtime admin modules response.summary.function_count must equal the total module function_count.",
        "value_error",
      );
    }
    assertCountRecordMatches(
      summary.maturityCounts,
      countRuntimeValues(validatedModules.map(entry => entry.maturity)),
      "Algenta runtime admin modules response.summary.maturity_counts",
      "maturity",
    );
    assertCountRecordMatches(
      summary.layerCounts,
      countRuntimeValues(validatedModules.map(entry => entry.layer)),
      "Algenta runtime admin modules response.summary.layer_counts",
      "layer",
    );
    return value as RuntimeAdminModulesResponse;
  });
}

export function assertRuntimeAdminBenchmarksResponse(payload: unknown): RuntimeAdminBenchmarksResponse {
  return wrapRuntimeValidation("Algenta runtime admin benchmarks endpoint", payload, value => {
    const obj = assertJsonObject(value, "Algenta runtime admin benchmarks response");
    assertNonEmptyString(
      obj.runtime_version,
      "Algenta runtime admin benchmarks response.runtime_version",
    );
    assertNonEmptyString(
      obj.llm_core_manifest,
      "Algenta runtime admin benchmarks response.llm_core_manifest",
    );
    assertNonEmptyString(
      obj.module_manifest_version,
      "Algenta runtime admin benchmarks response.module_manifest_version",
    );
    const benchmarkDiscoveryLane = assertRuntimeBenchmarkDiscoveryLane(
      obj.benchmark_discovery_lane,
      "Algenta runtime admin benchmarks response.benchmark_discovery_lane",
    );
    assertRuntimeBenchmarkFramework(
      obj.benchmarking,
      "Algenta runtime admin benchmarks response.benchmarking",
    );
    assertArray(obj.slo_budgets, "Algenta runtime admin benchmarks response.slo_budgets").forEach(
      (entry, index) =>
        assertRuntimeSLOBudget(entry, `Algenta runtime admin benchmarks response.slo_budgets[${index}]`),
    );
    const qualityGateBenchmarkClasses = assertArray(
      obj.quality_gate_benchmark_classes,
      "Algenta runtime admin benchmarks response.quality_gate_benchmark_classes",
    );
    qualityGateBenchmarkClasses.forEach((entry, index) =>
      assertRuntimeBenchmarkClassEntry(
        entry,
        `Algenta runtime admin benchmarks response.quality_gate_benchmark_classes[${index}]`,
      ),
    );
    assertUniqueRuntimeObjectField(
      qualityGateBenchmarkClasses,
      "code",
      "Algenta runtime admin benchmarks response.quality_gate_benchmark_classes",
    );
    const qualityGateSLOBudgets = assertArray(
      obj.quality_gate_slo_budgets,
      "Algenta runtime admin benchmarks response.quality_gate_slo_budgets",
    );
    qualityGateSLOBudgets.forEach((entry, index) =>
      assertRuntimeSLOBudget(
        entry,
        `Algenta runtime admin benchmarks response.quality_gate_slo_budgets[${index}]`,
      ),
    );
    assertUniqueRuntimeObjectField(
      qualityGateSLOBudgets,
      "name",
      "Algenta runtime admin benchmarks response.quality_gate_slo_budgets",
    );
    assertRuntimeEvaluationScience(
      obj.evaluation_science,
      "Algenta runtime admin benchmarks response.evaluation_science",
    );
    assertRuntimeAdminEvaluationSummary(
      obj.evaluation_summary,
      "Algenta runtime admin benchmarks response.evaluation_summary",
    );
    const compiledArtifacts = assertArray(
      obj.compiled_artifacts,
      "Algenta runtime admin benchmarks response.compiled_artifacts",
    );
    compiledArtifacts.forEach((entry, index) =>
      assertRuntimeArtifactReference(
        entry,
        `Algenta runtime admin benchmarks response.compiled_artifacts[${index}]`,
      ),
    );
    assertUniqueRuntimeObjectField(
      compiledArtifacts,
      "path",
      "Algenta runtime admin benchmarks response.compiled_artifacts",
    );
    const shippingRuntimeModules = assertEnumArray(
      obj.shipping_runtime_modules,
      RUNTIME_MODULE_ID_VALUES,
      "Algenta runtime admin benchmarks response.shipping_runtime_modules",
    );
    assertUniqueRuntimeValues(
      shippingRuntimeModules,
      "Algenta runtime admin benchmarks response.shipping_runtime_modules",
    );
    const shippingRuntimeFunctionCounts = assertArray(
      obj.shipping_runtime_function_counts,
      "Algenta runtime admin benchmarks response.shipping_runtime_function_counts",
    ).map((value, index) =>
      assertInteger(
        value,
        `Algenta runtime admin benchmarks response.shipping_runtime_function_counts[${index}]`,
      ),
    );
    const shippingRuntimeBenchmarkSpeedupsX = assertArray(
      obj.shipping_runtime_benchmark_speedups_x,
      "Algenta runtime admin benchmarks response.shipping_runtime_benchmark_speedups_x",
    ).map((value, index) =>
      assertFiniteNumber(
        value,
        `Algenta runtime admin benchmarks response.shipping_runtime_benchmark_speedups_x[${index}]`,
      ),
    );
    const shippingRuntimeBenchmarkArtifacts = assertArray(
      obj.shipping_runtime_benchmark_artifacts,
      "Algenta runtime admin benchmarks response.shipping_runtime_benchmark_artifacts",
    ).map((value, index) =>
      assertNonEmptyString(
        value,
        `Algenta runtime admin benchmarks response.shipping_runtime_benchmark_artifacts[${index}]`,
      ),
    );
    const shippingRuntimeCompiledArtifacts = assertArray(
      obj.shipping_runtime_compiled_artifacts,
      "Algenta runtime admin benchmarks response.shipping_runtime_compiled_artifacts",
    ).map((value, index) =>
      assertNonEmptyString(
        value,
        `Algenta runtime admin benchmarks response.shipping_runtime_compiled_artifacts[${index}]`,
      ),
    );
    const shippingRuntimeCompiledEngines = assertArray(
      obj.shipping_runtime_compiled_engines,
      "Algenta runtime admin benchmarks response.shipping_runtime_compiled_engines",
    ).map((value, index) =>
      assertEnumValue(
        value,
        RUNTIME_COMPILED_ENGINE_VALUES,
        `Algenta runtime admin benchmarks response.shipping_runtime_compiled_engines[${index}]`,
      ),
    );
    const shippingRuntimeMaxColdMs = assertArray(
      obj.shipping_runtime_max_cold_ms,
      "Algenta runtime admin benchmarks response.shipping_runtime_max_cold_ms",
    ).map((value, index) =>
      assertFiniteNumber(
        value,
        `Algenta runtime admin benchmarks response.shipping_runtime_max_cold_ms[${index}]`,
      ),
    );
    const shippingRuntimeMaxWarmMs = assertArray(
      obj.shipping_runtime_max_warm_ms,
      "Algenta runtime admin benchmarks response.shipping_runtime_max_warm_ms",
    ).map((value, index) =>
      assertFiniteNumber(
        value,
        `Algenta runtime admin benchmarks response.shipping_runtime_max_warm_ms[${index}]`,
      ),
    );
    const shippingRuntimeMaxHotMs = assertArray(
      obj.shipping_runtime_max_hot_ms,
      "Algenta runtime admin benchmarks response.shipping_runtime_max_hot_ms",
    ).map((value, index) =>
      assertFiniteNumber(
        value,
        `Algenta runtime admin benchmarks response.shipping_runtime_max_hot_ms[${index}]`,
      ),
    );
    const compiledArtifactPaths = new Set(
      compiledArtifacts.map((entry, index) => {
        const artifact = assertJsonObject(
          entry,
          `Algenta runtime admin benchmarks response.compiled_artifacts[${index}]`,
        );
        return assertNonEmptyString(
          artifact.path,
          `Algenta runtime admin benchmarks response.compiled_artifacts[${index}].path`,
        );
      }),
    );
    const moduleBenchmarks = assertArray(
      obj.module_benchmarks,
      "Algenta runtime admin benchmarks response.module_benchmarks",
    );
    const validatedModuleBenchmarks = moduleBenchmarks.map((entry, index) =>
      assertRuntimeBenchmarkModuleEntry(
        entry,
        `Algenta runtime admin benchmarks response.module_benchmarks[${index}]`,
      ),
    );
    assertUniqueRuntimeObjectField(
      moduleBenchmarks,
      "name",
      "Algenta runtime admin benchmarks response.module_benchmarks",
    );
    if (benchmarkDiscoveryLane.shippingManifestModules !== validatedModuleBenchmarks.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.benchmark_discovery_lane.shipping_manifest_modules",
        "Algenta runtime admin benchmarks response.benchmark_discovery_lane.shipping_manifest_modules must equal the number of benchmark modules.",
        "value_error",
      );
    }
    if (benchmarkDiscoveryLane.shippingManifestModules !== shippingRuntimeModules.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.shipping_runtime_modules",
        "Algenta runtime admin benchmarks response.shipping_runtime_modules must contain one entry per shipping benchmark module.",
        "value_error",
      );
    }
    if (benchmarkDiscoveryLane.shippingManifestModules !== shippingRuntimeFunctionCounts.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.shipping_runtime_function_counts",
        "Algenta runtime admin benchmarks response.shipping_runtime_function_counts must contain one entry per shipping benchmark module.",
        "value_error",
      );
    }
    if (benchmarkDiscoveryLane.shippingManifestModules !== shippingRuntimeBenchmarkSpeedupsX.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.shipping_runtime_benchmark_speedups_x",
        "Algenta runtime admin benchmarks response.shipping_runtime_benchmark_speedups_x must contain one entry per shipping benchmark module.",
        "value_error",
      );
    }
    if (benchmarkDiscoveryLane.shippingManifestModules !== shippingRuntimeBenchmarkArtifacts.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.shipping_runtime_benchmark_artifacts",
        "Algenta runtime admin benchmarks response.shipping_runtime_benchmark_artifacts must contain one entry per shipping benchmark module.",
        "value_error",
      );
    }
    if (benchmarkDiscoveryLane.shippingManifestModules !== shippingRuntimeCompiledArtifacts.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.shipping_runtime_compiled_artifacts",
        "Algenta runtime admin benchmarks response.shipping_runtime_compiled_artifacts must contain one entry per shipping benchmark module.",
        "value_error",
      );
    }
    if (benchmarkDiscoveryLane.shippingManifestModules !== shippingRuntimeCompiledEngines.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.shipping_runtime_compiled_engines",
        "Algenta runtime admin benchmarks response.shipping_runtime_compiled_engines must contain one entry per shipping benchmark module.",
        "value_error",
      );
    }
    if (benchmarkDiscoveryLane.shippingManifestModules !== shippingRuntimeMaxColdMs.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.shipping_runtime_max_cold_ms",
        "Algenta runtime admin benchmarks response.shipping_runtime_max_cold_ms must contain one entry per shipping benchmark module.",
        "value_error",
      );
    }
    if (benchmarkDiscoveryLane.shippingManifestModules !== shippingRuntimeMaxWarmMs.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.shipping_runtime_max_warm_ms",
        "Algenta runtime admin benchmarks response.shipping_runtime_max_warm_ms must contain one entry per shipping benchmark module.",
        "value_error",
      );
    }
    if (benchmarkDiscoveryLane.shippingManifestModules !== shippingRuntimeMaxHotMs.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.shipping_runtime_max_hot_ms",
        "Algenta runtime admin benchmarks response.shipping_runtime_max_hot_ms must contain one entry per shipping benchmark module.",
        "value_error",
      );
    }
    const totalFunctions = validatedModuleBenchmarks.reduce(
      (sum, entry) => sum + entry.functionCount,
      0,
    );
    if (benchmarkDiscoveryLane.shippingManifestFunctions !== totalFunctions) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.benchmark_discovery_lane.shipping_manifest_functions",
        "Algenta runtime admin benchmarks response.benchmark_discovery_lane.shipping_manifest_functions must equal the total benchmark module function_count.",
        "value_error",
      );
    }
    validatedModuleBenchmarks.forEach((entry, index) => {
      if (!benchmarkDiscoveryLane.discoveredSourceImportPaths.includes(entry.name)) {
        throw buildStructuredValidationError(
          "Algenta runtime admin benchmarks response.benchmark_discovery_lane.discovered_source_inventory",
          `Algenta runtime admin benchmarks response.benchmark_discovery_lane.discovered_source_inventory must include module_benchmarks[${index}].name (${entry.name}).`,
          "value_error",
        );
      }
      if (shippingRuntimeModules[index] !== entry.name) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.shipping_runtime_modules[${index}]`,
          `Algenta runtime admin benchmarks response.shipping_runtime_modules[${index}] must equal module_benchmarks[${index}].name.`,
          "value_error",
        );
      }
      if (shippingRuntimeFunctionCounts[index] !== entry.functionCount) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.shipping_runtime_function_counts[${index}]`,
          `Algenta runtime admin benchmarks response.shipping_runtime_function_counts[${index}] must equal module_benchmarks[${index}].function_count.`,
          "value_error",
        );
      }
      if (shippingRuntimeBenchmarkSpeedupsX[index] !== entry.benchmarkSpeedupX) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.shipping_runtime_benchmark_speedups_x[${index}]`,
          `Algenta runtime admin benchmarks response.shipping_runtime_benchmark_speedups_x[${index}] must equal module_benchmarks[${index}].benchmark_speedup_x.`,
          "value_error",
        );
      }
      if (shippingRuntimeBenchmarkArtifacts[index] !== entry.benchmarkArtifact) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.shipping_runtime_benchmark_artifacts[${index}]`,
          `Algenta runtime admin benchmarks response.shipping_runtime_benchmark_artifacts[${index}] must equal module_benchmarks[${index}].benchmark_artifact.`,
          "value_error",
        );
      }
      if (shippingRuntimeCompiledArtifacts[index] !== entry.compiledArtifact) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.shipping_runtime_compiled_artifacts[${index}]`,
          `Algenta runtime admin benchmarks response.shipping_runtime_compiled_artifacts[${index}] must equal module_benchmarks[${index}].compiled_artifact.`,
          "value_error",
        );
      }
      if (shippingRuntimeCompiledEngines[index] !== entry.compiledEngine) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.shipping_runtime_compiled_engines[${index}]`,
          `Algenta runtime admin benchmarks response.shipping_runtime_compiled_engines[${index}] must equal module_benchmarks[${index}].compiled_engine.`,
          "value_error",
        );
      }
      if (shippingRuntimeMaxColdMs[index] !== entry.maxColdMs) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.shipping_runtime_max_cold_ms[${index}]`,
          `Algenta runtime admin benchmarks response.shipping_runtime_max_cold_ms[${index}] must equal module_benchmarks[${index}].max_cold_ms.`,
          "value_error",
        );
      }
      if (shippingRuntimeMaxWarmMs[index] !== entry.maxWarmMs) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.shipping_runtime_max_warm_ms[${index}]`,
          `Algenta runtime admin benchmarks response.shipping_runtime_max_warm_ms[${index}] must equal module_benchmarks[${index}].max_warm_ms.`,
          "value_error",
        );
      }
      if (shippingRuntimeMaxHotMs[index] !== entry.maxHotMs) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.shipping_runtime_max_hot_ms[${index}]`,
          `Algenta runtime admin benchmarks response.shipping_runtime_max_hot_ms[${index}] must equal module_benchmarks[${index}].max_hot_ms.`,
          "value_error",
        );
      }
      if (entry.benchmarkSpeedupX <= 0) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.module_benchmarks[${index}].benchmark_speedup_x`,
          "Algenta runtime admin benchmarks response.module_benchmarks entries must have positive benchmark_speedup_x values.",
          "value_error",
        );
      }
      if (entry.maxColdMs <= 0) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.module_benchmarks[${index}].max_cold_ms`,
          "Algenta runtime admin benchmarks response.module_benchmarks entries must have positive max_cold_ms values.",
          "value_error",
        );
      }
      if (entry.maxWarmMs <= 0) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.module_benchmarks[${index}].max_warm_ms`,
          "Algenta runtime admin benchmarks response.module_benchmarks entries must have positive max_warm_ms values.",
          "value_error",
        );
      }
      if (entry.maxHotMs <= 0) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.module_benchmarks[${index}].max_hot_ms`,
          "Algenta runtime admin benchmarks response.module_benchmarks entries must have positive max_hot_ms values.",
          "value_error",
        );
      }
    });
    const benchmarkArtifactIndexes = new Map<string, number>();
    validatedModuleBenchmarks.forEach((entry, index) => {
      const previousIndex = benchmarkArtifactIndexes.get(entry.benchmarkArtifact);
      if (previousIndex !== undefined) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.module_benchmarks[${index}].benchmark_artifact`,
          `Algenta runtime admin benchmarks response.module_benchmarks[${index}].benchmark_artifact duplicates module_benchmarks[${previousIndex}].benchmark_artifact.`,
          "value_error",
        );
      }
      benchmarkArtifactIndexes.set(entry.benchmarkArtifact, index);
      if (!compiledArtifactPaths.has(entry.compiledArtifact)) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.module_benchmarks[${index}].compiled_artifact`,
          `Algenta runtime admin benchmarks response.module_benchmarks[${index}].compiled_artifact must reference a path present in compiled_artifacts.`,
          "value_error",
        );
      }
    });
    const declaredBenchmarkClassCodes = new Set(
      assertArray(
        assertJsonObject(obj.benchmarking, "Algenta runtime admin benchmarks response.benchmarking").classes,
        "Algenta runtime admin benchmarks response.benchmarking.classes",
      ).map((entry, index) =>
          assertEnumValue(
          assertJsonObject(
            entry,
            `Algenta runtime admin benchmarks response.benchmarking.classes[${index}]`,
          ).code,
          RUNTIME_BENCHMARK_CLASS_VALUES,
          `Algenta runtime admin benchmarks response.benchmarking.classes[${index}].code`,
        ),
      ),
    );
    const qualityGateClassCodes = new Set(
      qualityGateBenchmarkClasses.map((entry, index) =>
          assertEnumValue(
          assertJsonObject(
            entry,
            `Algenta runtime admin benchmarks response.quality_gate_benchmark_classes[${index}]`,
          ).code,
          RUNTIME_BENCHMARK_CLASS_VALUES,
          `Algenta runtime admin benchmarks response.quality_gate_benchmark_classes[${index}].code`,
        ),
      ),
    );
    qualityGateClassCodes.forEach(code => {
      if (!declaredBenchmarkClassCodes.has(code)) {
        throw buildStructuredValidationError(
          "Algenta runtime admin benchmarks response.quality_gate_benchmark_classes",
          "Algenta runtime admin benchmarks response.quality_gate_benchmark_classes must be declared in benchmarking.classes.",
          "value_error",
        );
      }
    });
    const declaredSLOBudgetNames = new Set(
      assertArray(
        obj.slo_budgets,
        "Algenta runtime admin benchmarks response.slo_budgets",
      ).map((entry, index) =>
        assertEnumValue(
          assertJsonObject(
            entry,
            `Algenta runtime admin benchmarks response.slo_budgets[${index}]`,
          ).name,
          RUNTIME_SLO_BUDGET_NAME_VALUES,
          `Algenta runtime admin benchmarks response.slo_budgets[${index}].name`,
        ),
      ),
    );
    const qualityGateBudgetNames = new Set(
      qualityGateSLOBudgets.map((entry, index) =>
        assertEnumValue(
          assertJsonObject(
            entry,
            `Algenta runtime admin benchmarks response.quality_gate_slo_budgets[${index}]`,
          ).name,
          RUNTIME_SLO_BUDGET_NAME_VALUES,
          `Algenta runtime admin benchmarks response.quality_gate_slo_budgets[${index}].name`,
        ),
      ),
    );
    qualityGateBudgetNames.forEach(name => {
      if (!declaredSLOBudgetNames.has(name)) {
        throw buildStructuredValidationError(
          "Algenta runtime admin benchmarks response.quality_gate_slo_budgets",
          "Algenta runtime admin benchmarks response.quality_gate_slo_budgets must be declared in slo_budgets.",
          "value_error",
        );
      }
    });
    const evaluationScience = assertJsonObject(
      obj.evaluation_science,
      "Algenta runtime admin benchmarks response.evaluation_science",
    );
    const evaluationDimensions = new Set(
      assertEnumArray(
        evaluationScience.dimensions,
        RUNTIME_EVALUATION_DIMENSION_VALUES,
        "Algenta runtime admin benchmarks response.evaluation_science.dimensions",
      ),
    );
    const evaluationReleaseBlockers = new Set(
      assertEnumArray(
        evaluationScience.release_blockers,
        RUNTIME_RELEASE_BLOCKER_VALUES,
        "Algenta runtime admin benchmarks response.evaluation_science.release_blockers",
      ),
    );
    const evaluationMethods = assertEnumArray(
      evaluationScience.methods,
      RUNTIME_EVALUATION_METHOD_VALUES,
      "Algenta runtime admin benchmarks response.evaluation_science.methods",
    );
    const evaluationSummary = assertJsonObject(
      obj.evaluation_summary,
      "Algenta runtime admin benchmarks response.evaluation_summary",
    );
    const expectedReplayGate =
      qualityGateClassCodes.has("B6") &&
      qualityGateBudgetNames.has("replay") &&
      evaluationDimensions.has("replay success rate") &&
      evaluationReleaseBlockers.has("replay success regression");
    const expectedToolCallGate =
      qualityGateClassCodes.has("B7") &&
      qualityGateBudgetNames.has("mcp_call_first_party") &&
      evaluationDimensions.has("tool-call correctness") &&
      evaluationReleaseBlockers.has("tool-call error-rate increase");
    const expectedRagGate =
      qualityGateClassCodes.has("B9") &&
      evaluationDimensions.has("retrieval precision and recall") &&
      evaluationReleaseBlockers.has("RAG precision drop");
    const expectedDecisionGate =
      qualityGateClassCodes.has("B10") &&
      qualityGateBudgetNames.has("decision_plan_creation") &&
      evaluationDimensions.has("decision outcome delta") &&
      evaluationReleaseBlockers.has("decision-plan validity drop");
    if (assertInteger(evaluationSummary.dimension_count, "Algenta runtime admin benchmarks response.evaluation_summary.dimension_count") !== evaluationDimensions.size) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.evaluation_summary.dimension_count",
        "Algenta runtime admin benchmarks response.evaluation_summary.dimension_count must equal the number of evaluation dimensions.",
        "value_error",
      );
    }
    if (assertInteger(evaluationSummary.method_count, "Algenta runtime admin benchmarks response.evaluation_summary.method_count") !== evaluationMethods.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.evaluation_summary.method_count",
        "Algenta runtime admin benchmarks response.evaluation_summary.method_count must equal the number of evaluation methods.",
        "value_error",
      );
    }
    if (assertInteger(evaluationSummary.release_blocker_count, "Algenta runtime admin benchmarks response.evaluation_summary.release_blocker_count") !== evaluationReleaseBlockers.size) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.evaluation_summary.release_blocker_count",
        "Algenta runtime admin benchmarks response.evaluation_summary.release_blocker_count must equal the number of release blockers.",
        "value_error",
      );
    }
    if (assertInteger(evaluationSummary.benchmark_class_count, "Algenta runtime admin benchmarks response.evaluation_summary.benchmark_class_count") !== qualityGateClassCodes.size) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.evaluation_summary.benchmark_class_count",
        "Algenta runtime admin benchmarks response.evaluation_summary.benchmark_class_count must equal the number of quality gate benchmark classes.",
        "value_error",
      );
    }
    if (assertInteger(evaluationSummary.slo_budget_count, "Algenta runtime admin benchmarks response.evaluation_summary.slo_budget_count") !== qualityGateBudgetNames.size) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.evaluation_summary.slo_budget_count",
        "Algenta runtime admin benchmarks response.evaluation_summary.slo_budget_count must equal the number of quality gate SLO budgets.",
        "value_error",
      );
    }
    if (
      assertBoolean(
        evaluationSummary.replay_gate_enabled,
        "Algenta runtime admin benchmarks response.evaluation_summary.replay_gate_enabled",
      ) !== expectedReplayGate
    ) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.evaluation_summary.replay_gate_enabled",
        "Algenta runtime admin benchmarks response.evaluation_summary.replay_gate_enabled must match the replay benchmark, budget, and release blocker coverage.",
        "value_error",
      );
    }
    if (
      assertBoolean(
        evaluationSummary.tool_call_quality_gate_enabled,
        "Algenta runtime admin benchmarks response.evaluation_summary.tool_call_quality_gate_enabled",
      ) !== expectedToolCallGate
    ) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.evaluation_summary.tool_call_quality_gate_enabled",
        "Algenta runtime admin benchmarks response.evaluation_summary.tool_call_quality_gate_enabled must match the tool-call benchmark, budget, and release blocker coverage.",
        "value_error",
      );
    }
    if (
      assertBoolean(
        evaluationSummary.rag_quality_gate_enabled,
        "Algenta runtime admin benchmarks response.evaluation_summary.rag_quality_gate_enabled",
      ) !== expectedRagGate
    ) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.evaluation_summary.rag_quality_gate_enabled",
        "Algenta runtime admin benchmarks response.evaluation_summary.rag_quality_gate_enabled must match the RAG benchmark and release blocker coverage.",
        "value_error",
      );
    }
    if (
      assertBoolean(
        evaluationSummary.decision_quality_gate_enabled,
        "Algenta runtime admin benchmarks response.evaluation_summary.decision_quality_gate_enabled",
      ) !== expectedDecisionGate
    ) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.evaluation_summary.decision_quality_gate_enabled",
        "Algenta runtime admin benchmarks response.evaluation_summary.decision_quality_gate_enabled must match the decision benchmark, budget, and release blocker coverage.",
        "value_error",
      );
    }
    assertNonEmptyString(
      obj.manifest_digest,
      "Algenta runtime admin benchmarks response.manifest_digest",
    );
    assertRuntimeSignature(obj.signature, "Algenta runtime admin benchmarks response.signature");
    return value as RuntimeAdminBenchmarksResponse;
  });
}

