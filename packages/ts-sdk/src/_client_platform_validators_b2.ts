/** Auto-sub-split of _client_platform_validators_b.ts — second half. */
/** Auto-split sub-module of client.ts — platform contract validators (part B). */

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
  RUNTIME_ARTIFACT_KIND_VALUES,
  RUNTIME_BENCHMARK_DISCOVERY_RULE_VALUES,
  RUNTIME_LAYER_VALUES,
  RUNTIME_NON_SHIPPING_RULE_VALUES,
  RUNTIME_SIGNATURE_ALGORITHM_VALUES,
  RUNTIME_SIGNATURE_SCOPE_VALUES,
} from "./_client_constants.js";
import { DecisionEngineError } from "./_client_errors.js";
import { assertAuditLogEntry } from "./_client_platform_validators_a2.js";

export function assertDeploymentCostResponse(payload: unknown): DeploymentCostResponse {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Deployment cost response must be a JSON object.");
  }
  const deploymentId = (payload as { deployment_id?: unknown }).deployment_id;
  const provider = (payload as { provider?: unknown }).provider;
  const region = (payload as { region?: unknown }).region;
  if (typeof deploymentId !== "string" || deploymentId.length === 0) {
    throw new DecisionEngineError("Deployment cost response missing deployment_id.");
  }
  if (typeof provider !== "string" || provider.length === 0) {
    throw new DecisionEngineError("Deployment cost response missing provider.");
  }
  if (typeof region !== "string" || region.length === 0) {
    throw new DecisionEngineError("Deployment cost response missing region.");
  }
  for (const key of ["year", "month"] as const) {
    const value = (payload as Record<string, unknown>)[key];
    if (!Number.isInteger(value)) {
      throw new DecisionEngineError(`Deployment cost response missing ${key}.`);
    }
  }
  for (const key of ["cost_usd_month", "billable_cost_usd_month", "billing_markup_pct"] as const) {
    const value = (payload as Record<string, unknown>)[key];
    if (typeof value !== "number" || !Number.isFinite(value)) {
      throw new DecisionEngineError(`Deployment cost response missing ${key}.`);
    }
  }
  return payload as DeploymentCostResponse;
}

export function assertConnectorListResponse(
  payload: unknown,
  requestedPage: number,
): ConnectorListResult {
  if (Array.isArray(payload)) {
    if (requestedPage !== 1) {
      throw new DecisionEngineError(
        `Connector list response returned a raw array for page=${requestedPage}; paginated responses are required beyond the first page.`,
      );
    }
    return {
      connectors: payload as ConnectorInfo[],
      total: payload.length,
      page: 1,
      limit: Math.max(payload.length, 1),
      pages: 1,
    };
  }
  if (
    !payload ||
    typeof payload !== "object" ||
    Array.isArray(payload) ||
    !Array.isArray((payload as { connectors?: unknown }).connectors)
  ) {
    throw new DecisionEngineError(
      "Connector list response must be a JSON array or paginated object.",
    );
  }
  return payload as ConnectorListResult;
}

export function assertDatasetListResponse(
  payload: unknown,
  requestedPage: number,
): DatasetListResult {
  if (Array.isArray(payload)) {
    if (requestedPage !== 1) {
      throw new DecisionEngineError(
        `Dataset list response returned a raw array for page=${requestedPage}; paginated responses are required beyond the first page.`,
      );
    }
    return {
      datasets: payload as DatasetInfo[],
      count: payload.length,
      total: payload.length,
      page: 1,
      limit: Math.max(payload.length, 1),
      pages: 1,
    };
  }
  if (
    !payload ||
    typeof payload !== "object" ||
    Array.isArray(payload) ||
    !Array.isArray((payload as { datasets?: unknown }).datasets)
  ) {
    throw new DecisionEngineError(
      "Dataset list response must be a JSON array or paginated object.",
    );
  }
  return payload as DatasetListResult;
}

export function assertDatasetSummaryResponse(payload: unknown): DatasetSummaryResult {
  if (
    !payload ||
    typeof payload !== "object" ||
    Array.isArray(payload) ||
    typeof (payload as { dataset_id?: unknown }).dataset_id !== "string" ||
    typeof (payload as { name?: unknown }).name !== "string" ||
    typeof (payload as { status?: unknown }).status !== "string" ||
    !Array.isArray((payload as { source_names?: unknown }).source_names) ||
    !Number.isInteger((payload as { column_count?: unknown }).column_count) ||
    !Array.isArray((payload as { query_hints?: unknown }).query_hints)
  ) {
    throw new DecisionEngineError(
      "Dataset summary response must be a JSON object with the required discovery fields.",
    );
  }
  return payload as DatasetSummaryResult;
}

export function normalizeValidationPath(context: string): string {
  const prefixes = [
    "Algenta contract response.",
    "Algenta runtime manifest response.",
    "Algenta runtime admin modules response.",
    "Algenta runtime admin benchmarks response.",
    "Algenta runtime release validation response.",
  ];
  let normalized = context;
  for (const prefix of prefixes) {
    if (normalized.startsWith(prefix)) {
      normalized = normalized.slice(prefix.length);
      break;
    }
  }
  return normalized.replace(/\[(\d+)\]/g, ".$1");
}

export function buildStructuredValidationError(
  context: string,
  message: string,
  type: string,
): DecisionEngineError {
  const path = normalizeValidationPath(context);
  return new DecisionEngineError(message, 0, "invalid_payload_fragment", {
    error: {
      code: "invalid_payload_fragment",
      details: {
        cause: path,
        validation_errors: [
          {
            path,
            message,
            type,
          },
        ],
      },
    },
  });
}

export function assertJsonObject(payload: unknown, context: string): Record<string, unknown> {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw buildStructuredValidationError(
      context,
      `${context} must be a JSON object.`,
      "model_type",
    );
  }
  return payload as Record<string, unknown>;
}

export function assertNonEmptyString(value: unknown, context: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw buildStructuredValidationError(
      context,
      `${context} must be a non-empty string.`,
      "string_type",
    );
  }
  return value;
}

export function assertFiniteNumber(value: unknown, context: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw buildStructuredValidationError(
      context,
      `${context} must be a finite number.`,
      "finite_number",
    );
  }
  return value;
}

export function assertInteger(value: unknown, context: string): number {
  if (!Number.isInteger(value)) {
    throw buildStructuredValidationError(
      context,
      `${context} must be an integer.`,
      "integer_type",
    );
  }
  return Number(value);
}

export function assertBoolean(value: unknown, context: string): boolean {
  if (typeof value !== "boolean") {
    throw buildStructuredValidationError(
      context,
      `${context} must be a boolean.`,
      "bool_type",
    );
  }
  return value;
}

export function assertArray(value: unknown, context: string): unknown[] {
  if (!Array.isArray(value)) {
    throw buildStructuredValidationError(
      context,
      `${context} must be a JSON array.`,
      "array_type",
    );
  }
  return value;
}

export function assertEnumValue<T extends string>(
  value: unknown,
  allowedValues: readonly T[],
  context: string,
): T {
  const normalized = assertNonEmptyString(value, context);
  if (!(allowedValues as readonly string[]).includes(normalized)) {
    throw buildStructuredValidationError(
      context,
      `${context} has unsupported value '${normalized}'.`,
      "enum",
    );
  }
  return normalized as T;
}

export function assertEnumArray<T extends string>(
  value: unknown,
  allowedValues: readonly T[],
  context: string,
): T[] {
  return assertArray(value, context).map((entry, index) =>
    assertEnumValue(entry, allowedValues, `${context}[${index}]`),
  );
}

export function assertUniqueRuntimeValues(values: readonly string[], context: string): void {
  const seen = new Set<string>();
  const duplicates: string[] = [];
  values.forEach(value => {
    if (seen.has(value) && !duplicates.includes(value)) {
      duplicates.push(value);
      return;
    }
    seen.add(value);
  });
  if (duplicates.length > 0) {
    throw buildStructuredValidationError(
      context,
      `${context} must be unique; duplicate entries: ${duplicates.join(", ")}`,
      "value_error",
    );
  }
}

export function assertUniqueRuntimeObjectField(
  values: unknown[],
  fieldName: string,
  context: string,
): void {
  const normalizedValues = values.map((entry, index) => {
    const obj = assertJsonObject(entry, `${context}[${index}]`);
    return String(obj[fieldName]);
  });
  assertUniqueRuntimeValues(normalizedValues, context);
}

export function assertEnumKeyedCountRecord<T extends string>(
  value: unknown,
  allowedKeys: readonly T[],
  context: string,
): Partial<Record<T, number>> {
  const record = assertJsonObject(value, context);
  for (const [key, count] of Object.entries(record)) {
    if (!(allowedKeys as readonly string[]).includes(key)) {
      throw buildStructuredValidationError(
        `${context}.${key}`,
        `${context} has unsupported key '${key}'.`,
        "extra_forbidden",
      );
    }
    assertInteger(count, `${context}.${key}`);
  }
  return record as Partial<Record<T, number>>;
}

export function assertEnumKeyedEnumRecord<TKey extends string, TValue extends string>(
  value: unknown,
  allowedKeys: readonly TKey[],
  allowedValues: readonly TValue[],
  context: string,
): void {
  const record = assertJsonObject(value, context);
  for (const [key, entryValue] of Object.entries(record)) {
    if (!(allowedKeys as readonly string[]).includes(key)) {
      throw buildStructuredValidationError(
        `${context}.${key}`,
        `${context} has unsupported key '${key}'.`,
        "extra_forbidden",
      );
    }
    assertEnumValue(entryValue, allowedValues, `${context}.${key}`);
  }
}

export function assertRuntimeSignature(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertEnumValue(obj.algorithm, RUNTIME_SIGNATURE_ALGORITHM_VALUES, `${context}.algorithm`);
  assertNonEmptyString(obj.key_id, `${context}.key_id`);
  assertNonEmptyString(obj.digest_hex, `${context}.digest_hex`);
  assertNonEmptyString(obj.signature_hex, `${context}.signature_hex`);
  assertEnumValue(obj.scope, RUNTIME_SIGNATURE_SCOPE_VALUES, `${context}.scope`);
}

export function assertRuntimeSnapshotReference(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.snapshot_id, `${context}.snapshot_id`);
  assertNonEmptyString(obj.sha256, `${context}.sha256`);
  assertNonEmptyString(obj.source, `${context}.source`);
  assertNonEmptyString(obj.description, `${context}.description`);
}

export function assertRuntimeArtifactReference(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertEnumValue(obj.kind, RUNTIME_ARTIFACT_KIND_VALUES, `${context}.kind`);
  assertNonEmptyString(obj.path, `${context}.path`);
  assertNonEmptyString(obj.sha256, `${context}.sha256`);
  assertInteger(obj.size_bytes, `${context}.size_bytes`);
}

export function assertRuntimeShippingContractSummary(
  payload: unknown,
  context: string,
): { moduleCount: number; functionCount: number } {
  const obj = assertJsonObject(payload, context);
  const moduleCount = assertInteger(obj.module_count, `${context}.module_count`);
  const functionCount = assertInteger(obj.function_count, `${context}.function_count`);
  assertEnumValue(obj.runtime_core_layer, RUNTIME_LAYER_VALUES, `${context}.runtime_core_layer`);
  assertEnumValue(
    obj.benchmark_discovery_rule,
    RUNTIME_BENCHMARK_DISCOVERY_RULE_VALUES,
    `${context}.benchmark_discovery_rule`,
  );
  return { moduleCount, functionCount };
}

export function assertRuntimeBenchmarkDiscoveryLane(
  payload: unknown,
  context: string,
): {
  shippingManifestModules: number;
  shippingManifestFunctions: number;
  discoveredSourceImportPaths: string[];
} {
  const obj = assertJsonObject(payload, context);
  const discoveredSourceModules = assertInteger(
    obj.discovered_source_modules,
    `${context}.discovered_source_modules`,
  );
  const discoveredPublicFunctions = assertInteger(
    obj.discovered_public_functions,
    `${context}.discovered_public_functions`,
  );
  if (!Array.isArray(obj.discovered_source_inventory)) {
    throw buildStructuredValidationError(
      `${context}.discovered_source_inventory`,
      `${context}.discovered_source_inventory must be a JSON array.`,
      "type_error.list",
    );
  }
  const discoveredSourceInventory = obj.discovered_source_inventory.map((entry, index) => {
    const entryContext = `${context}.discovered_source_inventory[${index}]`;
    const sourceModule = assertJsonObject(entry, entryContext);
    const importPath = assertNonEmptyString(sourceModule.import_path, `${entryContext}.import_path`);
    const publicFunctionCount = assertInteger(
      sourceModule.public_function_count,
      `${entryContext}.public_function_count`,
    );
    if (publicFunctionCount <= 0) {
      throw buildStructuredValidationError(
        `${entryContext}.public_function_count`,
        `${entryContext}.public_function_count must be greater than 0.`,
        "value_error",
      );
    }
    return {
      import_path: importPath,
      public_function_count: publicFunctionCount,
    };
  });
  assertUniqueRuntimeObjectField(
    discoveredSourceInventory,
    "import_path",
    `${context}.discovered_source_inventory`,
  );
  const discoveredSourceImportPaths = discoveredSourceInventory.map(entry => entry.import_path);
  const sortedImportPaths = [...discoveredSourceImportPaths].sort();
  if (discoveredSourceImportPaths.some((value, index) => value !== sortedImportPaths[index])) {
    throw buildStructuredValidationError(
      `${context}.discovered_source_inventory`,
      `${context}.discovered_source_inventory must be sorted by import_path.`,
      "value_error",
    );
  }
  if (discoveredSourceModules !== discoveredSourceInventory.length) {
    throw buildStructuredValidationError(
      `${context}.discovered_source_modules`,
      `${context}.discovered_source_modules must equal the number of discovered_source_inventory entries.`,
      "value_error",
    );
  }
  const totalDiscoveredPublicFunctions = discoveredSourceInventory.reduce(
    (sum, entry) => sum + entry.public_function_count,
    0,
  );
  if (discoveredPublicFunctions !== totalDiscoveredPublicFunctions) {
    throw buildStructuredValidationError(
      `${context}.discovered_public_functions`,
      `${context}.discovered_public_functions must equal the total discovered_source_inventory public_function_count.`,
      "value_error",
    );
  }
  const shippingManifestModules = assertInteger(
    obj.shipping_manifest_modules,
    `${context}.shipping_manifest_modules`,
  );
  const shippingManifestFunctions = assertInteger(
    obj.shipping_manifest_functions,
    `${context}.shipping_manifest_functions`,
  );
  assertEnumValue(
    obj.non_shipping_rule,
    RUNTIME_NON_SHIPPING_RULE_VALUES,
    `${context}.non_shipping_rule`,
  );
  if (shippingManifestModules > discoveredSourceModules) {
    throw buildStructuredValidationError(
      `${context}.shipping_manifest_modules`,
      `${context}.shipping_manifest_modules cannot exceed ${context}.discovered_source_modules.`,
      "value_error",
    );
  }
  if (shippingManifestFunctions > discoveredPublicFunctions) {
    throw buildStructuredValidationError(
      `${context}.shipping_manifest_functions`,
      `${context}.shipping_manifest_functions cannot exceed ${context}.discovered_public_functions.`,
      "value_error",
    );
  }
  return {
    shippingManifestModules,
    shippingManifestFunctions,
    discoveredSourceImportPaths,
  };
}

