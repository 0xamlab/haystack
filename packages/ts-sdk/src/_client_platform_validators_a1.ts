/** Auto-sub-split of _client_platform_validators_a.ts — first half. */
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
import { assertBoolean, assertJsonObject, assertNonEmptyString } from "./_client_platform_validators_b2.js";

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

