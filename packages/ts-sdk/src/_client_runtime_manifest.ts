// SPDX-License-Identifier: Apache-2.0
/** Auto-split sub-module of client.ts — runtime manifest response validators. */

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
  RUNTIME_AUXILIARY_CHANNEL_VALUES,
  RUNTIME_DEPLOYMENT_MODE_VALUES,
  RUNTIME_FEATURE_FLAG_CHANNEL_VALUES,
  RUNTIME_INVARIANT_NAME_VALUES,
  RUNTIME_MATURITY_VALUES,
  RUNTIME_MODULE_ID_VALUES,
  RUNTIME_SUPPORTED_CHANNEL_VALUES,
} from "./_client_constants.js";
import { assertArray, assertEnumArray, assertEnumKeyedEnumRecord, assertEnumValue, assertJsonObject, assertNonEmptyString, assertRuntimeArtifactReference, assertRuntimeBenchmarkDiscoveryLane, assertRuntimeShippingContractSummary, assertRuntimeSignature, assertRuntimeSnapshotReference, assertUniqueRuntimeObjectField, assertUniqueRuntimeValues, buildStructuredValidationError } from "./_client_platform_validators_b2.js";
import {
  assertRuntimeAdvertisedCapabilities,
  assertRuntimeArtifactLineageSchema,
  assertRuntimeBenchmarkFramework,
  assertRuntimeCapabilityAlgebra,
  assertRuntimeDeploymentModes,
  assertRuntimeEvaluationScience,
  assertRuntimeExecutionModel,
  assertRuntimeExternalNondeterminismPolicy,
  assertRuntimeFormalReleaseTheorem,
  assertRuntimeImplementationStep,
  assertRuntimeKernelPromotionCriteria,
  assertRuntimeLayerProofMatrixEntry,
  assertRuntimeMemoryModel,
  assertRuntimeModuleManifestEntry,
  assertRuntimeNamedRule,
  assertRuntimeReleaseArtifactBundle,
  assertRuntimeReleaseGate,
  assertRuntimeSLOBudget,
  assertRuntimeSchedulerModel,
  assertRuntimeThreatModel,
  assertRuntimeTypedFailure,
  wrapRuntimeValidation,
} from "./_client_platform_validators_c.js";

export function assertRuntimeManifestResponse(payload: unknown): RuntimeManifestResponse {
  return wrapRuntimeValidation("Algenta runtime manifest endpoint", payload, value => {
    const obj = assertJsonObject(value, "Algenta runtime manifest response");
    assertNonEmptyString(obj.runtime_version, "Algenta runtime manifest response.runtime_version");
    assertNonEmptyString(obj.mojo_version, "Algenta runtime manifest response.mojo_version");
    assertNonEmptyString(obj.llm_core_manifest, "Algenta runtime manifest response.llm_core_manifest");
    assertNonEmptyString(
      obj.module_manifest_version,
      "Algenta runtime manifest response.module_manifest_version",
    );
    assertNonEmptyString(obj.generated_at, "Algenta runtime manifest response.generated_at");
    const modules = assertArray(obj.modules, "Algenta runtime manifest response.modules");
    const validatedModules = modules.map((entry, index) =>
      assertRuntimeModuleManifestEntry(
        entry,
        `Algenta runtime manifest response.modules[${index}]`,
      ),
    );
    assertUniqueRuntimeValues(
      validatedModules.map(entry => entry.name),
      "Algenta runtime manifest response.modules",
    );
    const compiledArtifacts = assertArray(
      obj.compiled_artifacts,
      "Algenta runtime manifest response.compiled_artifacts",
    );
    compiledArtifacts.forEach((entry, index) =>
      assertRuntimeArtifactReference(
        entry,
        `Algenta runtime manifest response.compiled_artifacts[${index}]`,
      ),
    );
    assertUniqueRuntimeObjectField(
      compiledArtifacts,
      "path",
      "Algenta runtime manifest response.compiled_artifacts",
    );
    const supportedChannels = assertEnumArray(
      obj.supported_channels,
      RUNTIME_SUPPORTED_CHANNEL_VALUES,
      "Algenta runtime manifest response.supported_channels",
    );
    assertUniqueRuntimeValues(
      supportedChannels,
      "Algenta runtime manifest response.supported_channels",
    );
    const validatedAuxiliaryChannels = assertEnumArray(
      obj.validated_auxiliary_channels,
      RUNTIME_AUXILIARY_CHANNEL_VALUES,
      "Algenta runtime manifest response.validated_auxiliary_channels",
    );
    assertUniqueRuntimeValues(
      validatedAuxiliaryChannels,
      "Algenta runtime manifest response.validated_auxiliary_channels",
    );
    const featureFlagChannels = assertEnumArray(
      obj.feature_flag_channels,
      RUNTIME_FEATURE_FLAG_CHANNEL_VALUES,
      "Algenta runtime manifest response.feature_flag_channels",
    );
    assertUniqueRuntimeValues(
      featureFlagChannels,
      "Algenta runtime manifest response.feature_flag_channels",
    );
    assertEnumKeyedEnumRecord(
      obj.maturity,
      RUNTIME_MODULE_ID_VALUES,
      RUNTIME_MATURITY_VALUES,
      "Algenta runtime manifest response.maturity",
    );
    assertRuntimeSnapshotReference(
      obj.policy_snapshot,
      "Algenta runtime manifest response.policy_snapshot",
    );
    assertRuntimeSnapshotReference(
      obj.schema_snapshot,
      "Algenta runtime manifest response.schema_snapshot",
    );
    assertEnumValue(
      obj.deployment_mode,
      RUNTIME_DEPLOYMENT_MODE_VALUES,
      "Algenta runtime manifest response.deployment_mode",
    );
    assertRuntimeDeploymentModes(
      obj.deployment_modes,
      "Algenta runtime manifest response.deployment_modes",
    );
    const shippingContract = assertRuntimeShippingContractSummary(
      obj.shipping_contract,
      "Algenta runtime manifest response.shipping_contract",
    );
    const benchmarkDiscoveryLane = assertRuntimeBenchmarkDiscoveryLane(
      obj.benchmark_discovery_lane,
      "Algenta runtime manifest response.benchmark_discovery_lane",
    );
    assertRuntimeAdvertisedCapabilities(
      obj.advertised_capabilities,
      "Algenta runtime manifest response.advertised_capabilities",
    );
    const systemInvariants = assertArray(
      obj.system_invariants,
      "Algenta runtime manifest response.system_invariants",
    );
    systemInvariants.forEach((entry, index) =>
        assertRuntimeNamedRule(
          entry,
          `Algenta runtime manifest response.system_invariants[${index}]`,
          RUNTIME_INVARIANT_NAME_VALUES,
          "name",
        ),
    );
    assertUniqueRuntimeObjectField(
      systemInvariants,
      "name",
      "Algenta runtime manifest response.system_invariants",
    );
    assertRuntimeExecutionModel(
      obj.execution_model,
      "Algenta runtime manifest response.execution_model",
    );
    assertRuntimeExternalNondeterminismPolicy(
      obj.external_nondeterminism,
      "Algenta runtime manifest response.external_nondeterminism",
    );
    assertRuntimeArtifactLineageSchema(
      obj.artifact_lineage,
      "Algenta runtime manifest response.artifact_lineage",
    );
    assertRuntimeCapabilityAlgebra(
      obj.capability_algebra,
      "Algenta runtime manifest response.capability_algebra",
    );
    const kernelPromotionCriteria = assertRuntimeKernelPromotionCriteria(
      obj.kernel_promotion_criteria,
      "Algenta runtime manifest response.kernel_promotion_criteria",
    );
    const proofMatrix = assertArray(
      obj.proof_matrix,
      "Algenta runtime manifest response.proof_matrix",
    );
    proofMatrix.forEach((entry, index) =>
        assertRuntimeLayerProofMatrixEntry(
          entry,
          `Algenta runtime manifest response.proof_matrix[${index}]`,
        ),
    );
    assertUniqueRuntimeObjectField(
      proofMatrix,
      "layer",
      "Algenta runtime manifest response.proof_matrix",
    );
    assertRuntimeBenchmarkFramework(
      obj.benchmarking,
      "Algenta runtime manifest response.benchmarking",
    );
    assertArray(obj.slo_budgets, "Algenta runtime manifest response.slo_budgets").forEach(
      (entry, index) =>
        assertRuntimeSLOBudget(entry, `Algenta runtime manifest response.slo_budgets[${index}]`),
    );
    assertRuntimeSchedulerModel(
      obj.scheduler_model,
      "Algenta runtime manifest response.scheduler_model",
    );
    assertRuntimeMemoryModel(obj.memory_model, "Algenta runtime manifest response.memory_model");
    assertRuntimeEvaluationScience(
      obj.evaluation_science,
      "Algenta runtime manifest response.evaluation_science",
    );
    const typedFailures = assertArray(
      obj.typed_failures,
      "Algenta runtime manifest response.typed_failures",
    );
    typedFailures.forEach((entry, index) =>
        assertRuntimeTypedFailure(entry, `Algenta runtime manifest response.typed_failures[${index}]`),
    );
    assertUniqueRuntimeObjectField(
      typedFailures,
      "code",
      "Algenta runtime manifest response.typed_failures",
    );
    assertRuntimeThreatModel(obj.threat_model, "Algenta runtime manifest response.threat_model");
    assertRuntimeFormalReleaseTheorem(
      obj.formal_release_theorem,
      "Algenta runtime manifest response.formal_release_theorem",
    );
    assertRuntimeReleaseArtifactBundle(
      obj.release_artifact_bundle,
      "Algenta runtime manifest response.release_artifact_bundle",
    );
    const releaseGates = assertArray(
      obj.release_gates,
      "Algenta runtime manifest response.release_gates",
    );
    releaseGates.forEach((entry, index) =>
        assertRuntimeReleaseGate(entry, `Algenta runtime manifest response.release_gates[${index}]`),
    );
    assertUniqueRuntimeObjectField(
      releaseGates,
      "gate",
      "Algenta runtime manifest response.release_gates",
    );
    const implementationSequence = assertArray(
      obj.immediate_implementation_sequence,
      "Algenta runtime manifest response.immediate_implementation_sequence",
    );
    implementationSequence.forEach((entry, index) =>
      assertRuntimeImplementationStep(
        entry,
        `Algenta runtime manifest response.immediate_implementation_sequence[${index}]`,
      ),
    );
    assertUniqueRuntimeObjectField(
      implementationSequence,
      "pr",
      "Algenta runtime manifest response.immediate_implementation_sequence",
    );
    assertNonEmptyString(obj.manifest_digest, "Algenta runtime manifest response.manifest_digest");
    assertRuntimeSignature(obj.signature, "Algenta runtime manifest response.signature");
    const totalFunctions = validatedModules.reduce((sum, entry) => sum + entry.functionCount, 0);
    if (shippingContract.moduleCount !== validatedModules.length) {
      throw buildStructuredValidationError(
        "Algenta runtime manifest response.shipping_contract.module_count",
        "Algenta runtime manifest response.shipping_contract.module_count must equal the number of manifest modules.",
        "value_error",
      );
    }
    if (shippingContract.functionCount !== totalFunctions) {
      throw buildStructuredValidationError(
        "Algenta runtime manifest response.shipping_contract.function_count",
        "Algenta runtime manifest response.shipping_contract.function_count must equal the total module function_count.",
        "value_error",
      );
    }
    if (benchmarkDiscoveryLane.shippingManifestModules !== validatedModules.length) {
      throw buildStructuredValidationError(
        "Algenta runtime manifest response.benchmark_discovery_lane.shipping_manifest_modules",
        "Algenta runtime manifest response.benchmark_discovery_lane.shipping_manifest_modules must equal the number of manifest modules.",
        "value_error",
      );
    }
    if (benchmarkDiscoveryLane.shippingManifestFunctions !== totalFunctions) {
      throw buildStructuredValidationError(
        "Algenta runtime manifest response.benchmark_discovery_lane.shipping_manifest_functions",
        "Algenta runtime manifest response.benchmark_discovery_lane.shipping_manifest_functions must equal the total module function_count.",
        "value_error",
      );
    }
    const discoveredSourceImportPaths = new Set(benchmarkDiscoveryLane.discoveredSourceImportPaths);
    validatedModules.forEach(entry => {
      if (!discoveredSourceImportPaths.has(entry.name)) {
        throw buildStructuredValidationError(
          "Algenta runtime manifest response.benchmark_discovery_lane.discovered_source_inventory",
          `Algenta runtime manifest response.benchmark_discovery_lane.discovered_source_inventory must include manifest module ${entry.name}.`,
          "value_error",
        );
      }
      if (entry.promotionStatus !== "shipping") {
        throw buildStructuredValidationError(
          "Algenta runtime manifest response.modules",
          `Algenta runtime manifest response.modules must mark ${entry.name} as shipping to appear in the signed manifest.`,
          "value_error",
        );
      }
      if (
        entry.benchmarkSpeedupX <
        1 + kernelPromotionCriteria.minimumPrimaryMetricImprovementPct / 100
      ) {
        throw buildStructuredValidationError(
          "Algenta runtime manifest response.modules",
          `Algenta runtime manifest response.modules must keep ${entry.name} above the kernel promotion minimum speedup threshold.`,
          "value_error",
        );
      }
    });
    return value as RuntimeManifestResponse;
  });
}

