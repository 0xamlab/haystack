// SPDX-License-Identifier: Apache-2.0
/** Auto-split sub-module of client.ts — error classes (DecisionEngineError + subclasses). */

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



export class DecisionEngineError extends Error {
  constructor(
    message: string,
    public readonly statusCode: number = 0,
    public readonly errorCode: string = 'unknown_error',
    public readonly responseBody: unknown = null,
  ) {
    super(message);
    this.name = 'DecisionEngineError';
  }

  public get details(): unknown {
    return extractResponseError(this.responseBody)?.details ?? null;
  }

  public get validationErrors(): Array<Record<string, unknown>> {
    const details = this.details;
    if (Array.isArray(details)) {
      return details.filter(
        (item): item is Record<string, unknown> =>
          !!item && typeof item === "object" && !Array.isArray(item),
      );
    }
    if (
      details &&
      typeof details === "object" &&
      !Array.isArray(details) &&
      "validation_errors" in details
    ) {
      const validationErrors = (details as { validation_errors?: unknown }).validation_errors;
      if (Array.isArray(validationErrors)) {
        return validationErrors.filter(
          (item): item is Record<string, unknown> =>
            !!item && typeof item === "object" && !Array.isArray(item),
        );
      }
    }
    return [];
  }

  public get fieldErrors(): Array<Record<string, unknown>> {
    return this.validationErrors;
  }
}

export interface ResponseErrorEnvelope {
  code?: unknown;
  message?: unknown;
  details?: unknown;
}

export function extractResponseError(body: unknown): ResponseErrorEnvelope | null {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return null;
  }
  const bodyRecord = body as Record<string, unknown>;
  const topLevelError = bodyRecord.error;
  if (topLevelError && typeof topLevelError === "object" && !Array.isArray(topLevelError)) {
    return topLevelError as ResponseErrorEnvelope;
  }
  const detail = bodyRecord.detail;
  if (!detail || typeof detail !== "object" || Array.isArray(detail)) {
    return null;
  }
  const detailRecord = detail as Record<string, unknown>;
  const nestedError = detailRecord.error;
  if (nestedError && typeof nestedError === "object" && !Array.isArray(nestedError)) {
    return nestedError as ResponseErrorEnvelope;
  }
  if ("code" in detailRecord || "message" in detailRecord || "details" in detailRecord) {
    return detailRecord as ResponseErrorEnvelope;
  }
  return null;
}

export function normalizedErrorCode(
  body: unknown,
  fallback: string,
): string {
  const code = extractResponseError(body)?.code;
  return typeof code === "string" && code.length > 0 ? code : fallback;
}

export function normalizedErrorMessage(body: unknown): string {
  const message = extractResponseError(body)?.message;
  return typeof message === "string" && message.length > 0 ? message : "Unknown error";
}

export class AuthenticationError extends DecisionEngineError {
  constructor(message: string, body: unknown, errorCode: string = "authentication_error") {
    super(message, 401, errorCode, body);
    this.name = 'AuthenticationError';
  }
}

export class RateLimitError extends DecisionEngineError {
  constructor(
    message: string,
    public readonly retryAfter: number = 60,
    body: unknown,
    errorCode: string = "rate_limit_exceeded",
  ) {
    super(message, 429, errorCode, body);
    this.name = 'RateLimitError';
  }
}

export class ValidationError extends DecisionEngineError {
  constructor(message: string, body: unknown, errorCode: string = "validation_error") {
    super(message, 422, errorCode, body);
    this.name = 'ValidationError';
  }
}

export class NotFoundError extends DecisionEngineError {
  constructor(message: string, body: unknown, errorCode: string = "not_found") {
    super(message, 404, errorCode, body);
    this.name = 'NotFoundError';
  }
}

export class ServerError extends DecisionEngineError {
  constructor(
    message: string,
    statusCode: number,
    body: unknown,
    errorCode: string = "server_error",
  ) {
    super(message, statusCode, errorCode, body);
    this.name = 'ServerError';
  }
}

