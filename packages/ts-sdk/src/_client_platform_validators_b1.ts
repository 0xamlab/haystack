/** Auto-sub-split of _client_platform_validators_b.ts — first half. */
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

export function assertAuditLogResponse(payload: unknown): AuditLogResponse {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Audit logs response must be a JSON object.");
  }
  const data = payload as Record<string, unknown>;
  if (!Array.isArray(data.entries)) {
    throw new DecisionEngineError("Audit logs response is missing entries.");
  }
  const total = data.total;
  const page = data.page;
  const limit = data.limit;
  const pages = data.pages;
  if (!Number.isInteger(total) || Number(total) < 0) {
    throw new DecisionEngineError("Audit logs response has an invalid total.");
  }
  if (!Number.isInteger(page) || Number(page) < 1) {
    throw new DecisionEngineError("Audit logs response has an invalid page.");
  }
  if (!Number.isInteger(limit) || Number(limit) < 1) {
    throw new DecisionEngineError("Audit logs response has an invalid limit.");
  }
  if (!Number.isInteger(pages) || Number(pages) < 1) {
    throw new DecisionEngineError("Audit logs response has an invalid pages value.");
  }
  return {
    entries: data.entries.map(assertAuditLogEntry),
    total: Number(total),
    page: Number(page),
    limit: Number(limit),
    pages: Number(pages),
  };
}

export function assertExecutionPolicyResponse(payload: unknown): ExecutionPolicyResponse {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Execution policy response must be a JSON object.");
  }
  const data = payload as Record<string, unknown>;
  const orgId = data.org_id;
  const minConfidence = data.min_confidence;
  const riskFloor = data.risk_floor;
  const requireCalibration = data.require_calibration;
  const allowReexecution = data.allow_reexecution;
  const snapshotId = data.snapshot_id;
  const contentHash = data.content_hash;
  const schemaRevision = data.schema_revision;
  const revision = data.revision;
  const previousSnapshotId = data.previous_snapshot_id;
  const createdAt = data.created_at;
  const updatedAt = data.updated_at;
  if (typeof orgId !== "string" || orgId.length === 0) {
    throw new DecisionEngineError("Execution policy response is missing org_id.");
  }
  if (typeof minConfidence !== "number" || Number.isNaN(minConfidence)) {
    throw new DecisionEngineError("Execution policy response has an invalid min_confidence.");
  }
  if (riskFloor !== undefined && riskFloor !== null && (typeof riskFloor !== "number" || Number.isNaN(riskFloor))) {
    throw new DecisionEngineError("Execution policy response has an invalid risk_floor.");
  }
  if (typeof requireCalibration !== "boolean") {
    throw new DecisionEngineError("Execution policy response has an invalid require_calibration.");
  }
  if (typeof allowReexecution !== "boolean") {
    throw new DecisionEngineError("Execution policy response has an invalid allow_reexecution.");
  }
  if (snapshotId !== undefined && snapshotId !== null && (typeof snapshotId !== "string" || snapshotId.length === 0)) {
    throw new DecisionEngineError("Execution policy response has an invalid snapshot_id.");
  }
  if (contentHash !== undefined && contentHash !== null && (typeof contentHash !== "string" || contentHash.length === 0)) {
    throw new DecisionEngineError("Execution policy response has an invalid content_hash.");
  }
  if (schemaRevision !== undefined && schemaRevision !== null && (typeof schemaRevision !== "string" || schemaRevision.length === 0)) {
    throw new DecisionEngineError("Execution policy response has an invalid schema_revision.");
  }
  if (revision !== undefined && revision !== null && (!Number.isInteger(revision) || Number(revision) < 1)) {
    throw new DecisionEngineError("Execution policy response has an invalid revision.");
  }
  if (previousSnapshotId !== undefined && previousSnapshotId !== null && (typeof previousSnapshotId !== "string" || previousSnapshotId.length === 0)) {
    throw new DecisionEngineError("Execution policy response has an invalid previous_snapshot_id.");
  }
  if (createdAt !== undefined && createdAt !== null && (typeof createdAt !== "string" || createdAt.length === 0)) {
    throw new DecisionEngineError("Execution policy response has an invalid created_at.");
  }
  if (typeof updatedAt !== "string" || updatedAt.length === 0) {
    throw new DecisionEngineError("Execution policy response is missing updated_at.");
  }
  return {
    org_id: orgId,
    min_confidence: minConfidence,
    risk_floor: (riskFloor as number | null | undefined) ?? null,
    require_calibration: requireCalibration,
    allow_reexecution: allowReexecution,
    snapshot_id: (snapshotId as string | null | undefined) ?? null,
    content_hash: (contentHash as string | null | undefined) ?? null,
    schema_revision: (schemaRevision as string | null | undefined) ?? null,
    revision: (revision as number | null | undefined) ?? null,
    previous_snapshot_id: (previousSnapshotId as string | null | undefined) ?? null,
    created_at: (createdAt as string | null | undefined) ?? null,
    updated_at: updatedAt,
  };
}

export function assertExecutionPolicySnapshotListResponse(payload: unknown): ExecutionPolicySnapshotListResponse {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Execution policy snapshot list response must be a JSON object.");
  }
  const data = payload as Record<string, unknown>;
  if (typeof data.org_id !== "string" || data.org_id.length === 0) {
    throw new DecisionEngineError("Execution policy snapshot list response is missing org_id.");
  }
  if (!Array.isArray(data.data)) {
    throw new DecisionEngineError("Execution policy snapshot list response is missing data.");
  }
  if (!Number.isInteger(data.total_snapshots) || Number(data.total_snapshots) < 0) {
    throw new DecisionEngineError("Execution policy snapshot list response has an invalid total_snapshots.");
  }
  return {
    org_id: data.org_id,
    data: data.data.map(assertExecutionPolicyResponse),
    total_snapshots: Number(data.total_snapshots),
  };
}

export function normalizeUpdateExecutionPolicyRequest(
  request: UpdateExecutionPolicyRequest,
): Record<string, unknown> {
  if (!request || typeof request !== "object" || Array.isArray(request)) {
    throw new DecisionEngineError("Execution policy update request must be a JSON object.");
  }
  const payload: Record<string, unknown> = {};
  if (request.min_confidence !== undefined) {
    if (typeof request.min_confidence !== "number" || Number.isNaN(request.min_confidence) || request.min_confidence < 0 || request.min_confidence > 1) {
      throw new DecisionEngineError("Execution policy update min_confidence must be a number between 0 and 1.");
    }
    payload.min_confidence = request.min_confidence;
  }
  if (request.risk_floor !== undefined) {
    if (request.risk_floor !== null && (typeof request.risk_floor !== "number" || Number.isNaN(request.risk_floor) || request.risk_floor < 0)) {
      throw new DecisionEngineError("Execution policy update risk_floor must be a non-negative number or null.");
    }
    payload.risk_floor = request.risk_floor;
  }
  if (request.require_calibration !== undefined) {
    if (typeof request.require_calibration !== "boolean") {
      throw new DecisionEngineError("Execution policy update require_calibration must be a boolean.");
    }
    payload.require_calibration = request.require_calibration;
  }
  if (request.allow_reexecution !== undefined) {
    if (typeof request.allow_reexecution !== "boolean") {
      throw new DecisionEngineError("Execution policy update allow_reexecution must be a boolean.");
    }
    payload.allow_reexecution = request.allow_reexecution;
  }
  if (Object.keys(payload).length === 0) {
    throw new DecisionEngineError("Execution policy update request must include at least one field.");
  }
  return payload;
}

export function normalizeMeteringBatchRequest(request: MeteringBatchRequest): Record<string, unknown> {
  if (!request || typeof request !== "object" || Array.isArray(request)) {
    throw new DecisionEngineError("Metering ingest request must be a JSON object.");
  }
  if (typeof request.device_id !== "string" || request.device_id.trim().length === 0) {
    throw new DecisionEngineError("Metering ingest request requires a non-empty device_id.");
  }
  if (!Array.isArray(request.events) || request.events.length === 0) {
    throw new DecisionEngineError("Metering ingest request requires a non-empty events array.");
  }
  const allowedKeys = new Set([
    "event_type",
    "module",
    "function",
    "engine_used",
    "latency_ms",
    "success",
    "timestamp",
    "request_id",
  ]);
  const events = request.events.map((event, index) => {
    if (!event || typeof event !== "object" || Array.isArray(event)) {
      throw new DecisionEngineError(`Metering event ${index} must be a JSON object.`);
    }
    const normalized: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(event)) {
      if (!allowedKeys.has(key)) {
        throw new DecisionEngineError(`Metering event ${index} contains unsupported field '${key}'.`);
      }
      if (["event_type", "module", "function", "engine_used", "request_id"].includes(key)) {
        if (typeof value !== "string") {
          throw new DecisionEngineError(`Metering event ${index}.${key} must be a string.`);
        }
        normalized[key] = value.trim();
        continue;
      }
      if (key === "latency_ms" || key === "timestamp") {
        if (typeof value !== "number" || Number.isNaN(value)) {
          throw new DecisionEngineError(`Metering event ${index}.${key} must be a finite number.`);
        }
        normalized[key] = value;
        continue;
      }
      if (key === "success") {
        if (typeof value !== "boolean") {
          throw new DecisionEngineError(`Metering event ${index}.success must be a boolean.`);
        }
        normalized[key] = value;
      }
    }
    return normalized;
  });
  return {
    device_id: request.device_id.trim(),
    events,
  };
}

export function normalizeCreditRefreshRequest(request: CreditRefreshRequest): Record<string, unknown> {
  if (!request || typeof request !== "object" || Array.isArray(request)) {
    throw new DecisionEngineError("Credit refresh request must be a JSON object.");
  }
  if (typeof request.device_id !== "string" || request.device_id.trim().length === 0) {
    throw new DecisionEngineError("Credit refresh request requires a non-empty device_id.");
  }
  if (
    typeof request.billing_period !== "string" ||
    !/^\d{4}-\d{2}$/.test(request.billing_period)
  ) {
    throw new DecisionEngineError("Credit refresh request requires a YYYY-MM billing_period.");
  }
  const month = Number(request.billing_period.slice(5, 7));
  if (!Number.isInteger(month) || month < 1 || month > 12) {
    throw new DecisionEngineError("Credit refresh request requires a valid billing_period month.");
  }
  const creditsUsed = request.credits_used ?? 0;
  if (!Number.isInteger(creditsUsed) || creditsUsed < 0) {
    throw new DecisionEngineError("Credit refresh request credits_used must be a non-negative integer.");
  }
  return {
    device_id: request.device_id.trim(),
    billing_period: request.billing_period,
    credits_used: creditsUsed,
  };
}

export function normalizeTeamInviteRequest(request: TeamInviteRequest): Record<string, unknown> {
  if (!request || typeof request !== "object" || Array.isArray(request)) {
    throw new DecisionEngineError("Team invite request must be a JSON object.");
  }
  if (typeof request.email !== "string" || request.email.trim().length === 0 || !request.email.includes("@")) {
    throw new DecisionEngineError("Team invite request requires a valid email.");
  }
  const role = normalizeTeamRole(request.role ?? "member", "inviteTeamMember");
  return { email: request.email.trim(), role };
}

export function normalizeTeamRole(role: unknown, methodName: string): "owner" | "admin" | "member" | "viewer" {
  if (typeof role !== "string" || role.trim().length === 0) {
    throw new DecisionEngineError(`${methodName} requires a non-empty role.`);
  }
  const normalized = role.trim();
  if (!["owner", "admin", "member", "viewer"].includes(normalized)) {
    throw new DecisionEngineError(
      `${methodName}.role must be one of: owner, admin, member, viewer.`,
    );
  }
  return normalized as "owner" | "admin" | "member" | "viewer";
}

export function normalizeApiKeyCreateRequest(request: CreateAPIKeyRequest): Record<string, unknown> {
  if (!request || typeof request !== "object" || Array.isArray(request)) {
    throw new DecisionEngineError("API key create request must be a JSON object.");
  }

  const label = request.label;
  if (typeof label !== "string" || label.trim().length === 0) {
    throw new DecisionEngineError("API key create request label must be a non-empty string.");
  }

  const payload: Record<string, unknown> = { label };
  const expiresAt = request.expires_at;
  if (expiresAt !== undefined) {
    if (expiresAt === null) {
      payload.expires_at = null;
    } else if (expiresAt instanceof Date) {
      if (Number.isNaN(expiresAt.getTime())) {
        throw new DecisionEngineError(
          "API key create request expires_at must be a valid Date, ISO-8601 string, or null.",
        );
      }
      payload.expires_at = expiresAt.toISOString();
    } else if (typeof expiresAt === "string") {
      payload.expires_at = expiresAt;
    } else {
      throw new DecisionEngineError(
        "API key create request expires_at must be a Date, ISO-8601 string, or null.",
      );
    }
  }

  const deviceLimit = request.device_limit;
  if (deviceLimit !== undefined) {
    if (deviceLimit === null) {
      payload.device_limit = null;
    } else if (!Number.isInteger(deviceLimit) || Number(deviceLimit) < 0) {
      throw new DecisionEngineError(
        "API key create request device_limit must be an integer greater than or equal to 0, or null.",
      );
    } else {
      payload.device_limit = deviceLimit;
    }
  }

  return payload;
}

export function assertDeploymentRegionsResponse(payload: unknown): DeploymentRegionsResponse {
  if (
    !payload ||
    typeof payload !== "object" ||
    Array.isArray(payload) ||
    !Array.isArray((payload as { providers?: unknown }).providers)
  ) {
    throw new DecisionEngineError("Deployment regions response must be a JSON object with providers.");
  }
  const normalizedProviders: DeploymentProviderResponse[] = [];
  for (const provider of (payload as { providers: unknown[] }).providers) {
    if (!provider || typeof provider !== "object" || Array.isArray(provider)) {
      throw new DecisionEngineError("Deployment provider entry must be a JSON object.");
    }
    const id = (provider as { id?: unknown }).id;
    const name = (provider as { name?: unknown }).name;
    const description = (provider as { description?: unknown }).description;
    const icon = (provider as { icon?: unknown }).icon;
    const regions = (provider as { regions?: unknown }).regions;
    if (typeof id !== "string" || id.length === 0) {
      throw new DecisionEngineError("Deployment provider entry missing id.");
    }
    if (typeof name !== "string" || name.length === 0) {
      throw new DecisionEngineError("Deployment provider entry missing name.");
    }
    if (typeof description !== "string" || description.length === 0) {
      throw new DecisionEngineError("Deployment provider entry missing description.");
    }
    if (typeof icon !== "string" || icon.length === 0) {
      throw new DecisionEngineError("Deployment provider entry missing icon.");
    }
    if (!Array.isArray(regions)) {
      throw new DecisionEngineError("Deployment provider entry missing regions.");
    }
    const normalizedRegions: DeploymentRegionResponse[] = [];
    for (const region of regions) {
      if (!region || typeof region !== "object" || Array.isArray(region)) {
        throw new DecisionEngineError("Deployment region entry must be a JSON object.");
      }
      const regionId = (region as { id?: unknown }).id;
      const regionName =
        typeof (region as { name?: unknown }).name === "string" &&
        (region as { name: string }).name.length > 0
          ? (region as { name: string }).name
          : (region as { label?: unknown }).label;
      if (typeof regionId !== "string" || regionId.length === 0) {
        throw new DecisionEngineError("Deployment region entry missing id.");
      }
      if (typeof regionName !== "string" || regionName.length === 0) {
        throw new DecisionEngineError("Deployment region entry missing name or label.");
      }
      normalizedRegions.push({
        ...(region as DeploymentRegionResponse),
        id: regionId,
        name: regionName,
        label:
          typeof (region as { label?: unknown }).label === "string"
            ? ((region as { label: string }).label)
            : regionName,
      });
    }
    normalizedProviders.push({
      ...(provider as DeploymentProviderResponse),
      id,
      name,
      description,
      icon,
      regions: normalizedRegions,
    });
  }
  return { providers: normalizedProviders };
}

export function assertDeploymentResponse(payload: unknown, context: string): DeploymentResponse {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError(`${context} must be a JSON object.`);
  }
  const deploymentId = (payload as { deployment_id?: unknown }).deployment_id;
  const orgId = (payload as { org_id?: unknown }).org_id;
  const provider = (payload as { provider?: unknown }).provider;
  const region = (payload as { region?: unknown }).region;
  const status = (payload as { status?: unknown }).status;
  const createdAt = (payload as { created_at?: unknown }).created_at;
  if (typeof deploymentId !== "string" || deploymentId.length === 0) {
    throw new DecisionEngineError(`${context} missing deployment_id.`);
  }
  if (typeof orgId !== "string" || orgId.length === 0) {
    throw new DecisionEngineError(`${context} missing org_id.`);
  }
  if (typeof provider !== "string" || provider.length === 0) {
    throw new DecisionEngineError(`${context} missing provider.`);
  }
  if (typeof region !== "string" || region.length === 0) {
    throw new DecisionEngineError(`${context} missing region.`);
  }
  if (typeof status !== "string" || status.length === 0) {
    throw new DecisionEngineError(`${context} missing status.`);
  }
  if (typeof createdAt !== "string" || createdAt.length === 0) {
    throw new DecisionEngineError(`${context} missing created_at.`);
  }
  for (const key of ["cost_usd_month", "billable_cost_usd_month", "billing_markup_pct"] as const) {
    const value = (payload as Record<string, unknown>)[key];
    if (typeof value !== "number" || !Number.isFinite(value)) {
      throw new DecisionEngineError(`${context} missing ${key}.`);
    }
  }
  return payload as DeploymentResponse;
}

export function normalizeCreateDeploymentRequest(request: CreateDeploymentRequest = {}): Record<string, unknown> {
  if (request === null || typeof request !== "object" || Array.isArray(request)) {
    throw new DecisionEngineError("Deployment create request must be a JSON object.");
  }
  const provider = request.provider ?? "algenta_shared";
  const region = request.region ?? "algenta-shared";
  if (typeof provider !== "string" || provider.trim().length === 0) {
    throw new DecisionEngineError("Deployment create request provider must be a non-empty string.");
  }
  if (typeof region !== "string" || region.trim().length === 0) {
    throw new DecisionEngineError("Deployment create request region must be a non-empty string.");
  }
  const payload: Record<string, unknown> = {
    provider,
    region,
    config: request.config ?? null,
  };
  const markup = request.billing_markup_pct ?? 20;
  if (typeof markup !== "number" || !Number.isFinite(markup)) {
    throw new DecisionEngineError("Deployment create request billing_markup_pct must be a finite number.");
  }
  payload.billing_markup_pct = markup;
  return payload;
}

export function assertDeploymentDeleteResponse(payload: unknown): DeploymentDeleteResponse {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Deployment delete response must be a JSON object.");
  }
  const status = (payload as { status?: unknown }).status;
  const deploymentId = (payload as { deployment_id?: unknown }).deployment_id;
  if (typeof status !== "string" || status.length === 0) {
    throw new DecisionEngineError("Deployment delete response missing status.");
  }
  if (typeof deploymentId !== "string" || deploymentId.length === 0) {
    throw new DecisionEngineError("Deployment delete response missing deployment_id.");
  }
  return payload as DeploymentDeleteResponse;
}

