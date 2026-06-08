/** Auto-split sub-module of client.ts — platform contract validators (part A). */

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


import { requireNonNegativeInteger, requirePositiveInteger } from "./_client_constants.js";
import { assertPlatformContractPayload, wrapContractValidation } from "./_client_contract_validators.js";
import { DecisionEngineError } from "./_client_errors.js";
import { assertBoolean, assertJsonObject, assertNonEmptyString } from "./_client_platform_validators_b.js";

export function assertPlatformContractResponse(payload: unknown): PlatformContractResponse {
  return wrapContractValidation("Algenta contract endpoint", payload, value =>
    assertPlatformContractPayload(value, "Algenta contract response"),
  );
}

export function dedupeStrings(values: string[]): string[] {
  const seen = new Set<string>();
  const ordered: string[] = [];
  for (const value of values) {
    const normalized = value.trim();
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    ordered.push(normalized);
  }
  return ordered;
}

export function sourceSetFromRequest(request: Record<string, unknown>): string[] {
  const values: string[] = [];
  if (typeof request.source_name === 'string') values.push(request.source_name);
  if (typeof request.join_source_name === 'string') values.push(request.join_source_name);

  if (Array.isArray(request.sources)) {
    for (const source of request.sources) {
      if (source && typeof source === 'object' && typeof (source as { name?: unknown }).name === 'string') {
        values.push((source as { name: string }).name);
      }
    }
  }

  if (request.join_path && typeof request.join_path === 'object') {
    const joinPath = request.join_path as Record<string, unknown>;
    for (const key of ['base_source', 'group_source']) {
      const value = joinPath[key];
      if (typeof value === 'string') values.push(value);
    }
    if (Array.isArray(joinPath.edges)) {
      for (const edge of joinPath.edges) {
        if (!edge || typeof edge !== 'object') continue;
        const edgeRecord = edge as Record<string, unknown>;
        for (const key of ['left_source', 'right_source']) {
          const value = edgeRecord[key];
          if (typeof value === 'string') values.push(value);
        }
      }
    }
  }

  return dedupeStrings(values);
}

export function splitResolvedSources(resolvedSource: string | undefined): string[] {
  if (!resolvedSource) return [];
  return dedupeStrings(resolvedSource.split('⋈').map(part => part.trim()));
}

export function buildExplainResponse(
  request: Record<string, unknown>,
  result: QueryResponse,
): ExplainResponse {
  let joinPath: Array<Record<string, unknown>> = [...(result.join_path ?? [])];
  if (request.join_path && typeof request.join_path === 'object') {
    const edges = (request.join_path as { edges?: unknown }).edges;
    if (joinPath.length === 0 && Array.isArray(edges)) {
      joinPath = edges.filter(
        (edge): edge is Record<string, unknown> => Boolean(edge) && typeof edge === 'object',
      );
    }
  }

  const sourceSet = (() => {
    const resolved = result.source_set ?? splitResolvedSources(result.resolved_source);
    return resolved.length > 0 ? resolved : sourceSetFromRequest(request);
  })();
  if (joinPath.length === 0 && sourceSet.length > 1) {
    joinPath = sourceSet.slice(0, -1).map((source, index) => ({
      left_source: source,
      right_source: sourceSet[index + 1],
    }));
  }

  return {
    source_set: sourceSet,
    join_path: joinPath,
    planner_mode: result.planner_mode ?? (result.exact_spec ? 'exact_spec' : result.decision_path),
    decision_path: result.decision_path,
    plan_hash: result.plan_hash,
    schema_revision: result.schema_revision,
    validated: result.validated,
    clarification_required: result.clarification_required,
    rejection_reason: result.rejection_reason,
    resolved_source: result.resolved_source,
    resolved_column: result.resolved_column,
    resolved_role: result.resolved_role,
    confidence: result.confidence,
    confidence_source: result.confidence_source,
    deterministic_scope: result.deterministic_scope,
    plan: result.plan,
    explanation: result.explanation,
    request_id: result.request_id,
  };
}

export function assertApiKeyPrefix(payload: unknown, context: string): string {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError(`${context} must be a JSON object.`);
  }
  const keyPrefix = (payload as { key_prefix?: unknown }).key_prefix;
  if (typeof keyPrefix !== "string" || keyPrefix.length === 0) {
    throw new DecisionEngineError(`${context} missing key_prefix.`);
  }
  return keyPrefix;
}

export function assertOptionalApiKeyDeviceLimit(payload: unknown, context: string): void {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return;
  }
  const deviceLimit = (payload as { device_limit?: unknown }).device_limit;
  if (deviceLimit === undefined || deviceLimit === null) {
    return;
  }
  if (!Number.isInteger(deviceLimit) || Number(deviceLimit) < 0) {
    throw new DecisionEngineError(`${context} has an invalid device_limit.`);
  }
}

export function assertApiKeyListResponse(payload: unknown): APIKeyInfo[] {
  const items = Array.isArray(payload)
    ? payload
    : payload && typeof payload === "object" && Array.isArray((payload as { api_keys?: unknown }).api_keys)
      ? (payload as { api_keys: unknown[] }).api_keys
      : null;
  if (!items) {
    throw new DecisionEngineError("API key list response must be a JSON array or paginated object.");
  }
  for (const item of items) {
    assertApiKeyPrefix(item, "API key list item");
    assertOptionalApiKeyDeviceLimit(item, "API key list item");
    if (item && typeof item === "object" && ("raw_key" in item || "key" in item)) {
      throw new DecisionEngineError("API key list response leaked one-time secret material.");
    }
  }
  return items as APIKeyInfo[];
}

export function assertApiKeyCreateResponse(payload: unknown): APIKeyCreated {
  const keyPrefix = assertApiKeyPrefix(payload, "API key create response");
  assertOptionalApiKeyDeviceLimit(payload, "API key create response");
  const rawKey = (payload as { raw_key?: unknown }).raw_key;
  if (typeof rawKey !== "string" || rawKey.length === 0 || !rawKey.startsWith(keyPrefix)) {
    throw new DecisionEngineError("API key create response missing raw_key.");
  }
  return payload as APIKeyCreated;
}

export function assertUsageInfoResponse(payload: unknown): UsageInfo {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Usage response must be a JSON object.");
  }
  const usage = payload as Partial<UsageInfo>;
  const orgId = usage.org_id;
  if (typeof orgId !== "string" || orgId.length === 0) {
    throw new DecisionEngineError("Usage response missing org_id.");
  }
  const billingPeriod = usage.billing_period;
  if (typeof billingPeriod !== "string" || billingPeriod.length === 0) {
    throw new DecisionEngineError("Usage response missing billing_period.");
  }
  const simulationsRun = requireNonNegativeInteger(
    usage.simulations_run,
    "Usage response has an invalid simulations_run.",
  );
  const apiCalls = requireNonNegativeInteger(
    usage.api_calls,
    "Usage response has an invalid api_calls.",
  );
  const quotaLimit = requireNonNegativeInteger(
    usage.quota_limit,
    "Usage response has an invalid quota_limit.",
  );
  const quotaUsedPct = usage.quota_used_pct;
  if (typeof quotaUsedPct !== "number" || Number.isNaN(quotaUsedPct) || quotaUsedPct < 0) {
    throw new DecisionEngineError("Usage response has an invalid quota_used_pct.");
  }
  return {
    org_id: orgId,
    billing_period: billingPeriod,
    simulations_run: simulationsRun,
    api_calls: apiCalls,
    quota_limit: quotaLimit,
    quota_used_pct: quotaUsedPct,
  };
}

export function assertMeResponse(payload: unknown): MeResponse {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Me response must be a JSON object.");
  }
  const data = payload as Record<string, unknown>;
  const user =
    data.user && typeof data.user === "object" && !Array.isArray(data.user)
      ? assertJsonObject(data.user, "Me response.user")
      : {
          id: data.user_id ?? data.id ?? "current_user",
          email: data.email,
          name: data.name ?? data.user_name ?? "current_user",
          role: data.role ?? "member",
          email_verified: data.email_verified ?? true,
          created_at: data.created_at ?? "1970-01-01T00:00:00Z",
        };
  const org =
    data.org && typeof data.org === "object" && !Array.isArray(data.org)
      ? assertJsonObject(data.org, "Me response.org")
      : {
          id: data.org_id ?? "current_org",
          name: data.org_name ?? data.organization,
          slug: data.org_slug ?? data.slug ?? "current-org",
          plan: data.plan,
          status: data.org_status ?? "active",
          created_at: data.org_created_at ?? data.created_at ?? "1970-01-01T00:00:00Z",
        };
  const normalizedUser = {
    id: assertNonEmptyString(user.id, "Me response.user.id"),
    email: assertNonEmptyString(user.email, "Me response.user.email"),
    name: assertNonEmptyString(user.name, "Me response.user.name"),
    role: assertNonEmptyString(user.role, "Me response.user.role"),
    email_verified: assertBoolean(user.email_verified, "Me response.user.email_verified"),
    created_at: assertNonEmptyString(user.created_at, "Me response.user.created_at"),
  };
  const normalizedOrg = {
    id: assertNonEmptyString(org.id, "Me response.org.id"),
    name: assertNonEmptyString(org.name, "Me response.org.name"),
    slug: assertNonEmptyString(org.slug, "Me response.org.slug"),
    plan: assertNonEmptyString(org.plan, "Me response.org.plan"),
    status: assertNonEmptyString(org.status, "Me response.org.status"),
    created_at: assertNonEmptyString(org.created_at, "Me response.org.created_at"),
  };
  return {
    user: normalizedUser,
    org: normalizedOrg,
    email: normalizedUser.email,
    org_id: normalizedOrg.id,
    org_name: normalizedOrg.name,
    plan: normalizedOrg.plan,
    organization: normalizedOrg.name,
  };
}

export function normalizeUpdateMeRequest(request: UpdateMeRequest): Record<string, unknown> {
  if (!request || typeof request !== "object" || Array.isArray(request)) {
    throw new DecisionEngineError("Account update request must be a JSON object.");
  }
  const payload: Record<string, unknown> = {};
  if (request.name !== undefined) {
    if (typeof request.name !== "string" || request.name.trim().length === 0) {
      throw new DecisionEngineError("Account update name must be a non-empty string.");
    }
    payload.name = request.name.trim();
  }
  if (request.org_name !== undefined) {
    if (typeof request.org_name !== "string" || request.org_name.trim().length === 0) {
      throw new DecisionEngineError("Account update org_name must be a non-empty string.");
    }
    payload.org_name = request.org_name.trim();
  }
  if (Object.keys(payload).length === 0) {
    throw new DecisionEngineError("Account update request must include name and/or org_name.");
  }
  return payload;
}

export function assertStringArray(value: unknown, context: string): string[] {
  if (!Array.isArray(value) || value.some(item => typeof item !== "string" || item.length === 0)) {
    throw new DecisionEngineError(`${context} must be a list of non-empty strings.`);
  }
  return [...value];
}

export function assertJsonRecord(value: unknown, context: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new DecisionEngineError(`${context} must be a JSON object.`);
  }
  return value as Record<string, unknown>;
}

export function assertDistributionInfoResponse(payload: unknown): DistributionInfoResponse {
  const data = assertJsonRecord(payload, "Distribution entry");
  return {
    name: assertNonEmptyString(data.name, "Distribution entry.name"),
    description: assertNonEmptyString(data.description, "Distribution entry.description"),
    required_params: assertStringArray(data.required_params, "Distribution entry.required_params"),
    optional_params: assertStringArray(data.optional_params, "Distribution entry.optional_params"),
    example: assertJsonRecord(data.example, "Distribution entry.example"),
  };
}

export function assertDistributionListResponse(payload: unknown): DistributionListResponse {
  if (Array.isArray(payload)) {
    const items = payload.map(assertDistributionInfoResponse);
    return {
      distributions: items,
      total: items.length,
      page: 1,
      limit: items.length || 1,
      pages: 1,
    };
  }
  const data = assertJsonRecord(payload, "Distribution list response");
  if (!Array.isArray(data.distributions)) {
    throw new DecisionEngineError("Distribution list response is missing distributions.");
  }
  return {
    distributions: data.distributions.map(assertDistributionInfoResponse),
    total: requireNonNegativeInteger(data.total, "Distribution list response has an invalid total."),
    page: requirePositiveInteger(data.page, "Distribution list response has an invalid page."),
    limit: requirePositiveInteger(data.limit, "Distribution list response has an invalid limit."),
    pages: requirePositiveInteger(data.pages, "Distribution list response has an invalid pages."),
  };
}

export function assertTemplateInfoResponse(payload: unknown): TemplateInfoResponse {
  const data = assertJsonRecord(payload, "Template entry");
  return {
    id: assertNonEmptyString(data.id, "Template entry.id"),
    name: assertNonEmptyString(data.name, "Template entry.name"),
    category: assertNonEmptyString(data.category, "Template entry.category"),
    description: assertNonEmptyString(data.description, "Template entry.description"),
    example_request: assertJsonRecord(data.example_request, "Template entry.example_request"),
  };
}

export function assertTemplateListResponse(payload: unknown): TemplateListResponse {
  if (Array.isArray(payload)) {
    const items = payload.map(assertTemplateInfoResponse);
    return {
      templates: items,
      total: items.length,
      page: 1,
      limit: items.length || 1,
      pages: 1,
    };
  }
  const data = assertJsonRecord(payload, "Template list response");
  if (!Array.isArray(data.templates)) {
    throw new DecisionEngineError("Template list response is missing templates.");
  }
  return {
    templates: data.templates.map(assertTemplateInfoResponse),
    total: requireNonNegativeInteger(data.total, "Template list response has an invalid total."),
    page: requirePositiveInteger(data.page, "Template list response has an invalid page."),
    limit: requirePositiveInteger(data.limit, "Template list response has an invalid limit."),
    pages: requirePositiveInteger(data.pages, "Template list response has an invalid pages."),
  };
}

export function assertLimitsInfoResponse(payload: unknown): LimitsInfo {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Limits response must be a JSON object.");
  }
  const limits = payload as Partial<LimitsInfo>;
  const plan = limits.plan;
  if (typeof plan !== "string" || plan.length === 0) {
    throw new DecisionEngineError("Limits response missing plan.");
  }
  const maxSimulationsPerMonth = limits.max_simulations_per_month;
  if (
    maxSimulationsPerMonth !== undefined &&
    (!Number.isInteger(maxSimulationsPerMonth) || maxSimulationsPerMonth < 0)
  ) {
    throw new DecisionEngineError("Limits response has an invalid max_simulations_per_month.");
  }
  const simulationsPerMonth = limits.simulations_per_month ?? maxSimulationsPerMonth;
  if (typeof simulationsPerMonth !== "number" && typeof simulationsPerMonth !== "string") {
    throw new DecisionEngineError("Limits response has an invalid simulations_per_month.");
  }
  const maxRunsPerSimulation = limits.max_runs_per_simulation;
  if (
    maxRunsPerSimulation !== undefined &&
    (!Number.isInteger(maxRunsPerSimulation) || maxRunsPerSimulation < 0)
  ) {
    throw new DecisionEngineError("Limits response has an invalid max_runs_per_simulation.");
  }
  const maxBatchItems = limits.max_batch_items;
  if (maxBatchItems !== undefined && (!Number.isInteger(maxBatchItems) || maxBatchItems < 0)) {
    throw new DecisionEngineError("Limits response has an invalid max_batch_items.");
  }
  const rateLimitPerMinute = requireNonNegativeInteger(
    limits.rate_limit_per_minute,
    "Limits response has an invalid rate_limit_per_minute.",
  );
  const connectors = limits.connectors;
  if (connectors !== undefined && connectors !== null && (!Number.isInteger(connectors) || connectors < 0)) {
    throw new DecisionEngineError("Limits response has an invalid connectors count.");
  }
  const jobsEnabled = limits.jobs_enabled;
  if (jobsEnabled !== undefined && jobsEnabled !== null && typeof jobsEnabled !== "boolean") {
    throw new DecisionEngineError("Limits response has an invalid jobs_enabled flag.");
  }
  const asyncJobsEnabled = limits.async_jobs_enabled;
  if (
    asyncJobsEnabled !== undefined &&
    asyncJobsEnabled !== null &&
    typeof asyncJobsEnabled !== "boolean"
  ) {
    throw new DecisionEngineError("Limits response has an invalid async_jobs_enabled flag.");
  }
  const webhooksEnabled = limits.webhooks_enabled;
  if (
    webhooksEnabled !== undefined &&
    webhooksEnabled !== null &&
    typeof webhooksEnabled !== "boolean"
  ) {
    throw new DecisionEngineError("Limits response has an invalid webhooks_enabled flag.");
  }
  return {
    plan,
    simulations_per_month: simulationsPerMonth,
    max_simulations_per_month: maxSimulationsPerMonth,
    max_runs_per_simulation: maxRunsPerSimulation,
    max_batch_items: maxBatchItems,
    rate_limit_per_minute: rateLimitPerMinute,
    connectors,
    jobs_enabled: jobsEnabled ?? asyncJobsEnabled,
    async_jobs_enabled: asyncJobsEnabled,
    webhooks_enabled: webhooksEnabled,
  };
}

export function assertBillingInfoResponse(payload: unknown): BillingInfoResponse {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Billing info response must be a JSON object.");
  }
  const info = payload as Partial<BillingInfoResponse>;
  const plan = info.plan;
  if (typeof plan !== "string" || plan.length === 0) {
    throw new DecisionEngineError("Billing info response missing plan.");
  }
  const stripeCustomerId = info.stripe_customer_id;
  if (
    stripeCustomerId !== undefined &&
    stripeCustomerId !== null &&
    typeof stripeCustomerId !== "string"
  ) {
    throw new DecisionEngineError("Billing info response has an invalid stripe_customer_id.");
  }
  const subscriptionStatus = info.subscription_status;
  if (
    subscriptionStatus !== undefined &&
    subscriptionStatus !== null &&
    typeof subscriptionStatus !== "string"
  ) {
    throw new DecisionEngineError("Billing info response has an invalid subscription_status.");
  }
  const currentPeriodEnd = info.current_period_end;
  if (
    currentPeriodEnd !== undefined &&
    currentPeriodEnd !== null &&
    typeof currentPeriodEnd !== "string"
  ) {
    throw new DecisionEngineError("Billing info response has an invalid current_period_end.");
  }
  return {
    plan,
    stripe_customer_id: stripeCustomerId ?? null,
    subscription_status: subscriptionStatus ?? null,
    current_period_end: currentPeriodEnd ?? null,
  };
}

export function assertBillingSessionResponse(payload: unknown): BillingSessionResponse {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Billing session response must be a JSON object.");
  }
  const url = (payload as { url?: unknown }).url;
  if (typeof url !== "string" || url.length === 0) {
    throw new DecisionEngineError("Billing session response missing url.");
  }
  return { url };
}

export function assertMeteringBatchResponse(payload: unknown): MeteringBatchResponse {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Metering response must be a JSON object.");
  }
  const data = payload as { accepted?: unknown; billing_period?: unknown };
  if (!Number.isInteger(data.accepted) || Number(data.accepted) < 0) {
    throw new DecisionEngineError("Metering response has an invalid accepted count.");
  }
  if (typeof data.billing_period !== "string" || data.billing_period.length === 0) {
    throw new DecisionEngineError("Metering response is missing billing_period.");
  }
  return {
    accepted: Number(data.accepted),
    billing_period: data.billing_period,
  };
}

export function assertCreditRefreshResponse(payload: unknown): CreditRefreshResponse {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Credit refresh response must be a JSON object.");
  }
  const data = payload as Record<string, unknown>;
  const requireNonNegativeInteger = (key: string): number => {
    const value = data[key];
    if (!Number.isInteger(value) || Number(value) < 0) {
      throw new DecisionEngineError(`Credit refresh response has an invalid ${key}.`);
    }
    return Number(value);
  };
  const requireFiniteNumber = (key: string): number => {
    const value = data[key];
    if (typeof value !== "number" || !Number.isFinite(value)) {
      throw new DecisionEngineError(`Credit refresh response has an invalid ${key}.`);
    }
    return value;
  };
  const billingPeriod = data.billing_period;
  if (typeof billingPeriod !== "string" || billingPeriod.length === 0) {
    throw new DecisionEngineError("Credit refresh response is missing billing_period.");
  }
  return {
    credits_granted: requireNonNegativeInteger("credits_granted"),
    credits_issued_this_month: requireNonNegativeInteger("credits_issued_this_month"),
    monthly_limit: requireNonNegativeInteger("monthly_limit"),
    monthly_remaining: requireNonNegativeInteger("monthly_remaining"),
    billing_period: billingPeriod,
    expires_at: requireFiniteNumber("expires_at"),
    refresh_after: requireFiniteNumber("refresh_after"),
    server_time: requireFiniteNumber("server_time"),
  };
}

export function assertTeamMemberInfo(payload: unknown): TeamMemberInfo {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Team member entry must be a JSON object.");
  }
  const member = payload as Record<string, unknown>;
  const userId = member.user_id;
  const name = member.name;
  const email = member.email;
  const role = member.role;
  const status = member.status;
  const lastActive = member.last_active;
  if (typeof userId !== "string" || userId.length === 0) {
    throw new DecisionEngineError("Team member entry is missing user_id.");
  }
  if (typeof name !== "string" || name.length === 0) {
    throw new DecisionEngineError("Team member entry is missing name.");
  }
  if (typeof email !== "string" || email.length === 0) {
    throw new DecisionEngineError("Team member entry is missing email.");
  }
  if (typeof role !== "string" || role.length === 0) {
    throw new DecisionEngineError("Team member entry is missing role.");
  }
  if (typeof status !== "string" || status.length === 0) {
    throw new DecisionEngineError("Team member entry is missing status.");
  }
  if (lastActive !== undefined && lastActive !== null && typeof lastActive !== "string") {
    throw new DecisionEngineError("Team member entry has an invalid last_active value.");
  }
  return {
    user_id: userId,
    name,
    email,
    role,
    status,
    last_active: (lastActive as string | null | undefined) ?? null,
  };
}

export function assertTeamListResponse(payload: unknown): TeamListResponse {
  if (Array.isArray(payload)) {
    const members = payload.map(assertTeamMemberInfo);
    return {
      members,
      total: members.length,
      page: 1,
      limit: members.length || 1,
      pages: 1,
    };
  }
  if (!payload || typeof payload !== "object") {
    throw new DecisionEngineError("Team response must be a JSON object or list.");
  }
  const data = payload as Record<string, unknown>;
  if (!Array.isArray(data.members)) {
    throw new DecisionEngineError("Team response is missing members.");
  }
  const total = data.total;
  const page = data.page;
  const limit = data.limit;
  const pages = data.pages;
  if (!Number.isInteger(total) || Number(total) < 0) {
    throw new DecisionEngineError("Team response has an invalid total.");
  }
  if (!Number.isInteger(page) || Number(page) < 1) {
    throw new DecisionEngineError("Team response has an invalid page.");
  }
  if (!Number.isInteger(limit) || Number(limit) < 1) {
    throw new DecisionEngineError("Team response has an invalid limit.");
  }
  if (!Number.isInteger(pages) || Number(pages) < 1) {
    throw new DecisionEngineError("Team response has an invalid pages value.");
  }
  return {
    members: data.members.map(assertTeamMemberInfo),
    total: Number(total),
    page: Number(page),
    limit: Number(limit),
    pages: Number(pages),
  };
}

export function assertTeamInviteResponse(payload: unknown): TeamInviteResponse {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Team invite response must be a JSON object.");
  }
  const data = payload as Record<string, unknown>;
  if (typeof data.message !== "string" || data.message.length === 0) {
    throw new DecisionEngineError("Team invite response is missing message.");
  }
  if (typeof data.invite_id !== "string" || data.invite_id.length === 0) {
    throw new DecisionEngineError("Team invite response is missing invite_id.");
  }
  return { message: data.message, invite_id: data.invite_id };
}

export function assertTeamRoleUpdateResponse(payload: unknown): TeamRoleUpdateResponse {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Team role update response must be a JSON object.");
  }
  const data = payload as Record<string, unknown>;
  if (typeof data.message !== "string" || data.message.length === 0) {
    throw new DecisionEngineError("Team role update response is missing message.");
  }
  if (typeof data.user_id !== "string" || data.user_id.length === 0) {
    throw new DecisionEngineError("Team role update response is missing user_id.");
  }
  return { message: data.message, user_id: data.user_id };
}

export function assertTeamRemoveResponse(payload: unknown, userId: string): TeamRemoveResponse {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Team remove response must be a JSON object.");
  }
  const data = payload as Record<string, unknown>;
  return {
    removed: typeof data.removed === "boolean" ? data.removed : true,
    user_id: typeof data.user_id === "string" && data.user_id.length > 0 ? data.user_id : userId,
  };
}

export function assertDeviceRegistrationResponse(
  payload: unknown,
  context = "Device registration entry",
): DeviceRegistrationResponse {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError(`${context} must be a JSON object.`);
  }
  const entry = payload as Record<string, unknown>;
  const id = entry.id;
  const orgId = entry.org_id;
  const apiKeyId = entry.api_key_id;
  const deviceId = entry.device_id;
  const status = entry.status;
  const heartbeatCount = entry.heartbeat_count;
  const createdAt = entry.created_at;
  const updatedAt = entry.updated_at;
  const platform = entry.platform;
  const platformVersion = entry.platform_version;
  const hostnameHash = entry.hostname_hash;
  const sdkVersion = entry.sdk_version;
  const lastHeartbeatAt = entry.last_heartbeat_at;
  if (typeof id !== "string" || id.length === 0) {
    throw new DecisionEngineError(`${context} is missing id.`);
  }
  if (typeof orgId !== "string" || orgId.length === 0) {
    throw new DecisionEngineError(`${context} is missing org_id.`);
  }
  if (typeof apiKeyId !== "string" || apiKeyId.length === 0) {
    throw new DecisionEngineError(`${context} is missing api_key_id.`);
  }
  if (typeof deviceId !== "string" || deviceId.length === 0) {
    throw new DecisionEngineError(`${context} is missing device_id.`);
  }
  if (typeof status !== "string" || status.length === 0) {
    throw new DecisionEngineError(`${context} is missing status.`);
  }
  if (!Number.isInteger(heartbeatCount) || Number(heartbeatCount) < 0) {
    throw new DecisionEngineError(`${context} has an invalid heartbeat_count.`);
  }
  if (typeof createdAt !== "string" || createdAt.length === 0) {
    throw new DecisionEngineError(`${context} is missing created_at.`);
  }
  if (typeof updatedAt !== "string" || updatedAt.length === 0) {
    throw new DecisionEngineError(`${context} is missing updated_at.`);
  }
  if (platform !== undefined && platform !== null && typeof platform !== "string") {
    throw new DecisionEngineError(`${context} has an invalid platform.`);
  }
  if (
    platformVersion !== undefined &&
    platformVersion !== null &&
    typeof platformVersion !== "string"
  ) {
    throw new DecisionEngineError(`${context} has an invalid platform_version.`);
  }
  if (
    hostnameHash !== undefined &&
    hostnameHash !== null &&
    typeof hostnameHash !== "string"
  ) {
    throw new DecisionEngineError(`${context} has an invalid hostname_hash.`);
  }
  if (sdkVersion !== undefined && sdkVersion !== null && typeof sdkVersion !== "string") {
    throw new DecisionEngineError(`${context} has an invalid sdk_version.`);
  }
  if (
    lastHeartbeatAt !== undefined &&
    lastHeartbeatAt !== null &&
    typeof lastHeartbeatAt !== "string"
  ) {
    throw new DecisionEngineError(`${context} has an invalid last_heartbeat_at.`);
  }
  return {
    id,
    org_id: orgId,
    api_key_id: apiKeyId,
    device_id: deviceId,
    platform: (platform as string | null | undefined) ?? null,
    platform_version: (platformVersion as string | null | undefined) ?? null,
    hostname_hash: (hostnameHash as string | null | undefined) ?? null,
    sdk_version: (sdkVersion as string | null | undefined) ?? null,
    status,
    last_heartbeat_at: (lastHeartbeatAt as string | null | undefined) ?? null,
    heartbeat_count: Number(heartbeatCount),
    created_at: createdAt,
    updated_at: updatedAt,
  };
}

export function assertDeviceListEntryResponse(payload: unknown): DeviceListEntryResponse {
  const context = "Device list item";
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError(`${context} must be a JSON object.`);
  }
  const entry = payload as Record<string, unknown>;
  const id = entry.id;
  const deviceId = entry.device_id;
  const status = entry.status;
  const heartbeatCount = entry.heartbeat_count;
  const platform = entry.platform;
  const platformVersion = entry.platform_version;
  const sdkVersion = entry.sdk_version;
  const apiKeyLabel = entry.api_key_label;
  const apiKeyPrefix = entry.api_key_prefix;
  const registeredAt = entry.registered_at;
  const lastHeartbeatAt = entry.last_heartbeat_at;
  if (typeof id !== "string" || id.length === 0) {
    throw new DecisionEngineError(`${context} is missing id.`);
  }
  if (typeof deviceId !== "string" || deviceId.length === 0) {
    throw new DecisionEngineError(`${context} is missing device_id.`);
  }
  if (typeof status !== "string" || status.length === 0) {
    throw new DecisionEngineError(`${context} is missing status.`);
  }
  if (!Number.isInteger(heartbeatCount) || Number(heartbeatCount) < 0) {
    throw new DecisionEngineError(`${context} has an invalid heartbeat_count.`);
  }
  for (const [field, value] of [
    ["platform", platform],
    ["platform_version", platformVersion],
    ["sdk_version", sdkVersion],
    ["api_key_label", apiKeyLabel],
    ["api_key_prefix", apiKeyPrefix],
    ["registered_at", registeredAt],
    ["last_heartbeat_at", lastHeartbeatAt],
  ] as const) {
    if (value !== undefined && value !== null && typeof value !== "string") {
      throw new DecisionEngineError(`${context} has an invalid ${field}.`);
    }
  }
  return {
    id,
    device_id: deviceId,
    platform: (platform as string | null | undefined) ?? null,
    platform_version: (platformVersion as string | null | undefined) ?? null,
    sdk_version: (sdkVersion as string | null | undefined) ?? null,
    status,
    api_key_label: (apiKeyLabel as string | null | undefined) ?? null,
    api_key_prefix: (apiKeyPrefix as string | null | undefined) ?? null,
    registered_at: (registeredAt as string | null | undefined) ?? null,
    last_heartbeat_at: (lastHeartbeatAt as string | null | undefined) ?? null,
    heartbeat_count: Number(heartbeatCount),
  };
}

export function assertDeviceListResponse(payload: unknown): DeviceListResponse {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Device list response must be a JSON object.");
  }
  const data = payload as Record<string, unknown>;
  if (!Array.isArray(data.devices)) {
    throw new DecisionEngineError("Device list response is missing devices.");
  }
  const deviceCount = data.device_count;
  const total = data.total;
  const page = data.page;
  const limit = data.limit;
  const pages = data.pages;
  const deviceLimit = data.device_limit;
  const plan = data.plan;
  if (!Number.isInteger(deviceCount) || Number(deviceCount) < 0) {
    throw new DecisionEngineError("Device list response has an invalid device_count.");
  }
  if (!Number.isInteger(total) || Number(total) < 0) {
    throw new DecisionEngineError("Device list response has an invalid total.");
  }
  if (!Number.isInteger(page) || Number(page) < 1) {
    throw new DecisionEngineError("Device list response has an invalid page.");
  }
  if (!Number.isInteger(limit) || Number(limit) < 1) {
    throw new DecisionEngineError("Device list response has an invalid limit.");
  }
  if (!Number.isInteger(pages) || Number(pages) < 1) {
    throw new DecisionEngineError("Device list response has an invalid pages value.");
  }
  if (!Number.isInteger(deviceLimit) || Number(deviceLimit) < 0) {
    throw new DecisionEngineError("Device list response has an invalid device_limit.");
  }
  if (typeof plan !== "string" || plan.length === 0) {
    throw new DecisionEngineError("Device list response is missing plan.");
  }
  return {
    devices: data.devices.map((item) => assertDeviceListEntryResponse(item)),
    device_count: Number(deviceCount),
    total: Number(total),
    page: Number(page),
    limit: Number(limit),
    pages: Number(pages),
    device_limit: Number(deviceLimit),
    plan,
  };
}

export function assertDeviceRevokeResponse(payload: unknown): DeviceRevokeResponse {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Device revoke response must be a JSON object.");
  }
  const data = payload as Record<string, unknown>;
  if (typeof data.revoked !== "boolean") {
    throw new DecisionEngineError("Device revoke response is missing revoked.");
  }
  if (typeof data.registration_id !== "string" || data.registration_id.length === 0) {
    throw new DecisionEngineError("Device revoke response is missing registration_id.");
  }
  return {
    revoked: data.revoked,
    registration_id: data.registration_id,
  };
}

export function assertAuditLogEntry(payload: unknown): AuditLogEntry {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Audit log entry must be a JSON object.");
  }
  const entry = payload as Record<string, unknown>;
  const id = entry.id;
  const timestamp = entry.timestamp;
  const actorEmail = entry.actor_email;
  const action = entry.action;
  const resourceType = entry.resource_type;
  const result = entry.result;
  const resourceId = entry.resource_id;
  const ipAddress = entry.ip_address;
  const contentHash = entry.content_hash;
  const metadata = entry.metadata;
  if (typeof id !== "string" || id.length === 0) {
    throw new DecisionEngineError("Audit log entry is missing id.");
  }
  if (typeof timestamp !== "string" || timestamp.length === 0) {
    throw new DecisionEngineError("Audit log entry is missing timestamp.");
  }
  if (typeof actorEmail !== "string" || actorEmail.length === 0) {
    throw new DecisionEngineError("Audit log entry is missing actor_email.");
  }
  if (typeof action !== "string" || action.length === 0) {
    throw new DecisionEngineError("Audit log entry is missing action.");
  }
  if (typeof resourceType !== "string" || resourceType.length === 0) {
    throw new DecisionEngineError("Audit log entry is missing resource_type.");
  }
  if (typeof result !== "string" || result.length === 0) {
    throw new DecisionEngineError("Audit log entry is missing result.");
  }
  if (resourceId !== undefined && resourceId !== null && typeof resourceId !== "string") {
    throw new DecisionEngineError("Audit log entry has an invalid resource_id.");
  }
  if (ipAddress !== undefined && ipAddress !== null && typeof ipAddress !== "string") {
    throw new DecisionEngineError("Audit log entry has an invalid ip_address.");
  }
  if (contentHash !== undefined && contentHash !== null && typeof contentHash !== "string") {
    throw new DecisionEngineError("Audit log entry has an invalid content_hash.");
  }
  if (
    metadata !== undefined &&
    metadata !== null &&
    (typeof metadata !== "object" || Array.isArray(metadata))
  ) {
    throw new DecisionEngineError("Audit log entry has invalid metadata.");
  }
  return {
    id,
    timestamp,
    actor_email: actorEmail,
    action,
    resource_type: resourceType,
    resource_id: (resourceId as string | null | undefined) ?? null,
    ip_address: (ipAddress as string | null | undefined) ?? null,
    result,
    content_hash: (contentHash as string | null | undefined) ?? null,
    metadata: (metadata as Record<string, unknown> | null | undefined) ?? null,
  };
}

