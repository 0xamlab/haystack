// SPDX-License-Identifier: Apache-2.0
/** Auto-split sub-module of client.ts — runtime release validation response validator. */

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


import { RUNTIME_DEPLOYMENT_MODE_VALUES } from "./_client_constants.js";
import { assertArray, assertBoolean, assertEnumValue, assertJsonObject, assertNonEmptyString, assertRuntimeSignature, assertUniqueRuntimeObjectField } from "./_client_platform_validators_b2.js";
import { assertRuntimeReleaseConditionEvaluation, wrapRuntimeValidation } from "./_client_platform_validators_c.js";

export function assertRuntimeReleaseValidationResponse(payload: unknown): RuntimeReleaseValidationResponse {
  return wrapRuntimeValidation("Algenta runtime release validation endpoint", payload, value => {
    const obj = assertJsonObject(value, "Algenta runtime release validation response");
    assertNonEmptyString(
      obj.runtime_version,
      "Algenta runtime release validation response.runtime_version",
    );
    assertNonEmptyString(
      obj.llm_core_manifest,
      "Algenta runtime release validation response.llm_core_manifest",
    );
    assertNonEmptyString(
      obj.module_manifest_version,
      "Algenta runtime release validation response.module_manifest_version",
    );
    assertNonEmptyString(
      obj.theorem_statement,
      "Algenta runtime release validation response.theorem_statement",
    );
    assertBoolean(obj.valid_release, "Algenta runtime release validation response.valid_release");
    const conditions = assertArray(
      obj.conditions,
      "Algenta runtime release validation response.conditions",
    );
    conditions.forEach((entry, index) =>
        assertRuntimeReleaseConditionEvaluation(
          entry,
          `Algenta runtime release validation response.conditions[${index}]`,
        ),
    );
    assertUniqueRuntimeObjectField(
      conditions,
      "condition",
      "Algenta runtime release validation response.conditions",
    );
    if (obj.deployment_mode !== null) {
      assertEnumValue(
        obj.deployment_mode,
        RUNTIME_DEPLOYMENT_MODE_VALUES,
        "Algenta runtime release validation response.deployment_mode",
      );
    }
    assertNonEmptyString(
      obj.deployment_mode_raw,
      "Algenta runtime release validation response.deployment_mode_raw",
    );
    assertNonEmptyString(
      obj.manifest_digest,
      "Algenta runtime release validation response.manifest_digest",
    );
    assertRuntimeSignature(obj.signature, "Algenta runtime release validation response.signature");
    return value as RuntimeReleaseValidationResponse;
  });
}

export function parseHeaderNumber(headers: Record<string, string>, ...keys: string[]): number | undefined {
  for (const key of keys) {
    const value = headers[key];
    if (value === undefined) {
      continue;
    }
    const numeric = Number(value);
    if (Number.isFinite(numeric)) {
      return numeric;
    }
  }
  return undefined;
}

export function parseHeaderBoolean(headers: Record<string, string>, ...keys: string[]): boolean | undefined {
  for (const key of keys) {
    const value = headers[key];
    if (value === undefined) {
      continue;
    }
    const normalized = value.trim().toLowerCase();
    if (["1", "true", "hit", "yes"].includes(normalized)) {
      return true;
    }
    if (["0", "false", "miss", "no"].includes(normalized)) {
      return false;
    }
  }
  return undefined;
}

export function buildQueryExecutionMetadata(
  data: QueryResponse,
  headers: Record<string, string>,
): QueryExecutionMetadata {
  return {
    request_id:
      typeof data.request_id === "string" && data.request_id.length > 0
        ? data.request_id
        : headers["x-request-id"] ?? headers["x-algenta-request-id"] ?? headers["request-id"],
    latency_ms:
      typeof data.latency_ms === "number"
        ? data.latency_ms
        : parseHeaderNumber(
            headers,
            "x-latency-ms",
            "x-response-time-ms",
            "x-runtime-ms",
            "x-execution-ms",
          ),
    tokens_in: parseHeaderNumber(headers, "x-input-tokens", "x-prompt-tokens", "x-tokens-in"),
    tokens_out: parseHeaderNumber(
      headers,
      "x-output-tokens",
      "x-completion-tokens",
      "x-tokens-out",
    ),
    cost_usd: parseHeaderNumber(headers, "x-cost-usd", "x-usage-cost-usd"),
    cache_hit: parseHeaderBoolean(headers, "x-cache-hit", "x-algenta-cache-hit", "x-cache"),
  };
}

