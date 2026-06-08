/** Auto-split sub-module of client.ts — the DecisionEngineClient class. */

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
  DEFAULT_MAX_RETRIES,
  DEFAULT_TIMEOUT,
  SDK_USER_AGENT,
  appendQueryParameters,
  invalidStreamError,
  iterateSsePayloads,
  mergeRequestPayload,
  normalizeQueryLikeRequest,
  normalizeSourceRegistrationRequest,
} from "./_client_constants.js";
import { buildPlatformContractFromOpenApi } from "./_client_contract_validators.js";
import {
  AuthenticationError,
  DecisionEngineError,
  NotFoundError,
  RateLimitError,
  ServerError,
  ValidationError,
  normalizedErrorCode,
  normalizedErrorMessage,
} from "./_client_errors.js";
import {
  assertApiKeyCreateResponse,
  assertApiKeyListResponse,
  assertBillingInfoResponse,
  assertBillingSessionResponse,
  assertCreditRefreshResponse,
  assertDeviceListResponse,
  assertDeviceRevokeResponse,
  assertDistributionListResponse,
  assertLimitsInfoResponse,
  assertMeResponse,
  assertMeteringBatchResponse,
  assertPlatformContractResponse,
  assertTeamInviteResponse,
  assertTeamListResponse,
  assertTeamRemoveResponse,
  assertTeamRoleUpdateResponse,
  assertTemplateListResponse,
  assertUsageInfoResponse,
  buildExplainResponse,
  normalizeUpdateMeRequest,
} from "./_client_platform_validators_a.js";
import {
  assertAuditLogResponse,
  assertConnectorListResponse,
  assertDatasetListResponse,
  assertDatasetSummaryResponse,
  assertDeploymentCostResponse,
  assertDeploymentDeleteResponse,
  assertDeploymentRegionsResponse,
  assertDeploymentResponse,
  assertExecutionPolicyResponse,
  assertExecutionPolicySnapshotListResponse,
  normalizeApiKeyCreateRequest,
  normalizeCreateDeploymentRequest,
  normalizeCreditRefreshRequest,
  normalizeMeteringBatchRequest,
  normalizeTeamInviteRequest,
  normalizeTeamRole,
  normalizeUpdateExecutionPolicyRequest,
} from "./_client_platform_validators_b.js";
import { assertRuntimeAdminBenchmarksResponse, assertRuntimeAdminModulesResponse } from "./_client_runtime_admin.js";
import { assertRuntimeManifestResponse } from "./_client_runtime_manifest.js";
import { assertRuntimeReleaseValidationResponse, buildQueryExecutionMetadata } from "./_client_runtime_release.js";

export class DecisionEngineClient {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly timeout: number;
  private readonly maxRetries: number;
  private readonly defaultHeaders: Record<string, string>;
  private readonly deviceId: string | null;

  constructor(config: DecisionEngineClientConfig = {}) {
    const resolvedBaseUrl = resolveClientBaseUrl(config.baseUrl, "DecisionEngineClient");
    // Safe env var access — works in Node.js; undefined in browsers (use config.apiKey instead)
    const envKey: string | undefined = (typeof globalThis !== 'undefined' &&
      'process' in globalThis &&
      ((globalThis as { process?: { env?: { ALGENTA_API_KEY?: string; DE_API_KEY?: string } } }).process?.env?.[
        'ALGENTA_API_KEY'
      ] ||
        (globalThis as { process?: { env?: { ALGENTA_API_KEY?: string; DE_API_KEY?: string } } }).process?.env?.[
          'DE_API_KEY'
        ])) || undefined;
    const key = config.apiKey ?? envKey ?? '';
    if (!key) {
      throw new Error(
        'API key required. Pass apiKey or set ALGENTA_API_KEY / DE_API_KEY environment variables.\n' +
          apiKeyHelpText("DecisionEngineClient", resolvedBaseUrl),
      );
    }
    this.apiKey = key;
    this.baseUrl = resolvedBaseUrl;
    this.timeout = config.timeout ?? DEFAULT_TIMEOUT;
    this.maxRetries = config.maxRetries ?? DEFAULT_MAX_RETRIES;
    const deviceHeaders = resolveClientDeviceHeaders(SDK_USER_AGENT, config.defaultHeaders);
    this.defaultHeaders = {
      'Authorization': `Bearer ${this.apiKey}`,
      'Content-Type': 'application/json',
      'User-Agent': SDK_USER_AGENT,
      ...deviceHeaders,
      ...config.defaultHeaders,
    };
    this.deviceId =
      typeof this.defaultHeaders[DEVICE_ID_HEADER] === "string" &&
      this.defaultHeaders[DEVICE_ID_HEADER].trim().length > 0
        ? this.defaultHeaders[DEVICE_ID_HEADER].trim()
        : null;
  }

  private currentRequestHeaders(): Record<string, string> {
    const headers = { ...this.defaultHeaders };
    if (this.deviceId) {
      const bindingToken = loadHostedDeviceBindingToken(this.baseUrl, this.apiKey, this.deviceId);
      if (bindingToken) {
        headers[DEVICE_BINDING_TOKEN_HEADER] = bindingToken;
      }
    }
    return headers;
  }

  private captureBindingToken(response: Response, requestHeaders: Record<string, string>): void {
    const deviceId = requestHeaders[DEVICE_ID_HEADER]?.trim();
    const bindingToken = response.headers.get(DEVICE_BINDING_TOKEN_HEADER)?.trim();
    if (!deviceId || !bindingToken) {
      return;
    }
    persistHostedDeviceBindingToken(this.baseUrl, this.apiKey, deviceId, bindingToken);
    this.defaultHeaders[DEVICE_BINDING_TOKEN_HEADER] = bindingToken;
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      if (attempt > 0) {
        const delay = Math.pow(2, attempt - 1) * 1000;
        await new Promise(resolve => setTimeout(resolve, delay));
      }

      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.timeout);

        try {
          const requestHeaders = this.currentRequestHeaders();
          const response = await fetch(`${this.baseUrl}${path}`, {
            method,
            headers: requestHeaders,
            body: body !== undefined ? JSON.stringify(body) : undefined,
            signal: controller.signal,
          });
          clearTimeout(timer);
          this.captureBindingToken(response, requestHeaders);
          return await this.handleResponse<T>(response);
        } finally {
          clearTimeout(timer);
        }
      } catch (err) {
        if (err instanceof AuthenticationError || err instanceof ValidationError || err instanceof NotFoundError) {
          throw err;
        }
        if (err instanceof RateLimitError) {
          if (attempt >= this.maxRetries) throw err;
          await new Promise(resolve => setTimeout(resolve, err.retryAfter * 1000));
          lastError = err;
          continue;
        }
        lastError = err as Error;
        if (attempt >= this.maxRetries) throw err;
      }
    }

    throw lastError ?? new DecisionEngineError('Request failed after retries');
  }

  private async requestWithMetadata<T>(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<{ data: T; headers: Record<string, string> }> {
    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      if (attempt > 0) {
        const delay = Math.pow(2, attempt - 1) * 1000;
        await new Promise(resolve => setTimeout(resolve, delay));
      }

      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.timeout);

        try {
          const requestHeaders = this.currentRequestHeaders();
          const response = await fetch(`${this.baseUrl}${path}`, {
            method,
            headers: requestHeaders,
            body: body !== undefined ? JSON.stringify(body) : undefined,
            signal: controller.signal,
          });
          clearTimeout(timer);
          this.captureBindingToken(response, requestHeaders);
          const data = await this.handleResponse<T>(response);
          const headers: Record<string, string> = {};
          response.headers.forEach((value, key) => {
            headers[key] = value;
          });
          return { data, headers };
        } finally {
          clearTimeout(timer);
        }
      } catch (err) {
        if (err instanceof AuthenticationError || err instanceof ValidationError || err instanceof NotFoundError) {
          throw err;
        }
        if (err instanceof RateLimitError) {
          if (attempt >= this.maxRetries) throw err;
          await new Promise(resolve => setTimeout(resolve, err.retryAfter * 1000));
          lastError = err;
          continue;
        }
        lastError = err as Error;
        if (attempt >= this.maxRetries) throw err;
      }
    }

    throw lastError ?? new DecisionEngineError('Request failed after retries');
  }

  private async *requestStream<T>(
    method: string,
    path: string,
    body?: unknown,
  ): AsyncGenerator<T> {
    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      if (attempt > 0) {
        const delay = Math.pow(2, attempt - 1) * 1000;
        await new Promise(resolve => setTimeout(resolve, delay));
      }

      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.timeout);

        try {
          const requestHeaders = this.currentRequestHeaders();
          requestHeaders.Accept = "text/event-stream";
          const response = await fetch(`${this.baseUrl}${path}`, {
            method,
            headers: requestHeaders,
            body: body !== undefined ? JSON.stringify(body) : undefined,
            signal: controller.signal,
          });
          clearTimeout(timer);
          this.captureBindingToken(response, requestHeaders);
          if (!(response.status >= 200 && response.status < 300)) {
            await this.handleResponse<unknown>(response);
            throw invalidStreamError(
              "stream_request_failed",
              "Streaming request failed without a structured API error.",
              { status_code: response.status },
            );
          }
          const contentType = response.headers.get("content-type") ?? "";
          if (!contentType.includes("text/event-stream")) {
            throw invalidStreamError(
              "invalid_stream_content_type",
              "Expected text/event-stream response for streaming request.",
              { content_type: contentType },
            );
          }
          if (!response.body) {
            throw invalidStreamError(
              "stream_body_missing",
              "Streaming response body is unavailable.",
              {},
            );
          }
          for await (const payload of iterateSsePayloads(response.body)) {
            yield payload as T;
          }
          return;
        } finally {
          clearTimeout(timer);
        }
      } catch (err) {
        if (
          err instanceof AuthenticationError ||
          err instanceof ValidationError ||
          err instanceof NotFoundError
        ) {
          throw err;
        }
        if (err instanceof RateLimitError) {
          if (attempt >= this.maxRetries) throw err;
          await new Promise(resolve => setTimeout(resolve, err.retryAfter * 1000));
          lastError = err;
          continue;
        }
        lastError = err as Error;
        if (attempt >= this.maxRetries) throw err;
      }
    }

    throw lastError ?? new DecisionEngineError('Streaming request failed after retries');
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    let body: unknown = {};
    try {
      body = await response.json();
    } catch { /* empty body */ }

    const msg = normalizedErrorMessage(body);
    const errorCode = normalizedErrorCode(body, "unknown_error");

    if (response.status >= 200 && response.status < 300) return body as T;
    if (response.status === 401) throw new AuthenticationError(msg, body, errorCode);
    if (response.status === 404) throw new NotFoundError(msg, body, errorCode);
    if (response.status === 422) throw new ValidationError(msg, body, errorCode);
    if (response.status === 429) {
      const retryAfter = parseInt(response.headers.get('Retry-After') ?? '60', 10);
      throw new RateLimitError(msg, retryAfter, body, errorCode);
    }
    if (response.status >= 500) throw new ServerError(msg, response.status, body, errorCode);
    throw new DecisionEngineError(msg, response.status, errorCode, body);
  }

  // ─── Simulation ───────────────────────────────────────────────────────────

  async simulate(request: SimulateRequest): Promise<DecisionEnvelope> {
    return this.request<DecisionEnvelope>('POST', '/v1/simulate', request);
  }

  async planDecision(request: SimulateRequest): Promise<DecisionPlanResponse> {
    return this.request<DecisionPlanResponse>('POST', '/v1/decisions/plan', request);
  }

  async productDecision(request: ProductDecisionRequest): Promise<ProductDecisionResponse> {
    return this.request<ProductDecisionResponse>('POST', '/v1/decision', request);
  }

  async productAgentRun(request: ProductAgentRunRequest): Promise<ProductAgentRunResponse> {
    return this.request<ProductAgentRunResponse>('POST', '/v1/agent/run', request);
  }

  async productOptimize(request: ProductOptimizeRequest): Promise<ProductOptimizeResponse> {
    return this.request<ProductOptimizeResponse>('POST', '/v1/optimize', request);
  }

  async productRetrieve(request: ProductRetrieveRequest): Promise<ProductRetrieveResponse> {
    return this.request<ProductRetrieveResponse>('POST', '/v1/retrieve', request);
  }

  async productForecast(request: ProductForecastRequest): Promise<ProductForecastResponse> {
    return this.request<ProductForecastResponse>('POST', '/v1/forecast', request);
  }

  async logDecision(request: LogDecisionRequest): Promise<DecisionLogResponse> {
    return this.request<DecisionLogResponse>('POST', '/v1/decisions', request);
  }

  async listDecisions(options: {
    page?: number;
    limit?: number;
    page_size?: number;
    with_outcome_only?: boolean;
  } = {}): Promise<DecisionListResponse> {
    const params = new URLSearchParams();
    if (options.page !== undefined) params.set('page', String(options.page));
    if (options.limit !== undefined) params.set('limit', String(options.limit));
    if (options.page_size !== undefined) params.set('page_size', String(options.page_size));
    if (options.with_outcome_only !== undefined) {
      params.set('with_outcome_only', String(options.with_outcome_only));
    }
    const suffix = params.size > 0 ? `?${params.toString()}` : '';
    return this.request<DecisionListResponse>('GET', `/v1/decisions${suffix}`);
  }

  async getDecision(decisionId: string): Promise<DecisionLogResponse> {
    return this.request<DecisionLogResponse>('GET', `/v1/decisions/${decisionId}`);
  }

  async recordOutcome(
    decisionId: string,
    request: RecordOutcomeRequest,
  ): Promise<DecisionLogResponse> {
    return this.request<DecisionLogResponse>(
      'PATCH',
      `/v1/decisions/${decisionId}/outcome`,
      request,
    );
  }

  async executeDecision(
    decisionId: string,
    request: ExecuteDecisionRequest,
  ): Promise<ExecutionReceiptResponse> {
    return this.request<ExecutionReceiptResponse>(
      'POST',
      `/v1/decisions/${decisionId}/execute`,
      request,
    );
  }

  async deleteDecision(decisionId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('DELETE', `/v1/decisions/${decisionId}`);
  }

  async resolve(request: Record<string, unknown>): Promise<ResolveResponse> {
    return this.request<ResolveResponse>('POST', '/v1/resolve', normalizeQueryLikeRequest(request));
  }

  async query(request: Record<string, unknown>): Promise<QueryResponse> {
    return this.request<QueryResponse>('POST', '/v1/query', normalizeQueryLikeRequest(request));
  }

  async queryWithMetadata(
    request: Record<string, unknown>,
  ): Promise<QueryWithMetadataResponse> {
    const { data, headers } = await this.requestWithMetadata<QueryResponse>(
      'POST',
      '/v1/query',
      normalizeQueryLikeRequest(request),
    );
    return {
      data,
      metadata: buildQueryExecutionMetadata(data, headers),
      headers,
    };
  }

  async verify(request: Record<string, unknown>): Promise<VerifyResponse> {
    return this.request<VerifyResponse>('POST', '/v1/verify', normalizeQueryLikeRequest(request));
  }

  async queryBatch(request: {
    defaults?: {
      dataset_id?: string | null;
      filter?: QueryFilterSpec | null;
      limit?: number | null;
      order?: "asc" | "desc" | null;
    } | null;
    queries: Array<{ key: string; request: Record<string, unknown> }>;
  }): Promise<QueryBatchResponse> {
    return this.request<QueryBatchResponse>('POST', '/v1/query/batch', request);
  }

  async querySqlReport(request: QuerySqlReportRequest): Promise<QuerySqlReportResponse> {
    return this.request<QuerySqlReportResponse>('POST', '/v1/query/sql-report', request);
  }

  async listModels(): Promise<LLMModelListResponse> {
    return this.request<LLMModelListResponse>('GET', '/v1/models');
  }

  async resolveArtifactBridge(
    request: ArtifactBridgeResolveRequest,
  ): Promise<ArtifactBridgeResolveResponse> {
    return this.request<ArtifactBridgeResolveResponse>('POST', '/v1/artifacts/resolve', {
      local_files_only: true,
      ...request,
    });
  }

  async chatCompletions(request: ChatCompletionsRequest): Promise<ChatCompletionsResponse> {
    return this.request<ChatCompletionsResponse>('POST', '/v1/chat/completions', {
      ...request,
      stream: false,
    });
  }

  async *streamChatCompletions(
    request: ChatCompletionsRequest,
  ): AsyncGenerator<ChatCompletionsStreamChunkResponse> {
    for await (const chunk of this.requestStream<ChatCompletionsStreamChunkResponse>(
      'POST',
      '/v1/chat/completions',
      { ...request, stream: true },
    )) {
      yield chunk;
    }
  }

  async tokenize(request: TokenizeRequest): Promise<TokenizeResponse> {
    return this.request<TokenizeResponse>('POST', '/v1/tokenize', request);
  }

  async countTokens(request: CountTokensRequest): Promise<CountTokensResponse> {
    return this.request<CountTokensResponse>('POST', '/v1/count_tokens', request);
  }

  async responses(request: ResponsesRequest): Promise<ResponsesResponse> {
    return this.request<ResponsesResponse>('POST', '/v1/responses', { ...request, stream: false });
  }

  async *streamResponses(request: ResponsesRequest): AsyncGenerator<ResponseStreamEventResponse> {
    for await (const event of this.requestStream<ResponseStreamEventResponse>(
      'POST',
      '/v1/responses',
      { ...request, stream: true },
    )) {
      yield event;
    }
  }

  async embeddings(request: EmbeddingsRequest): Promise<EmbeddingsResponse> {
    return this.request<EmbeddingsResponse>('POST', '/v1/embeddings', request);
  }

  async embeddingSimilarity(
    request: EmbeddingSimilarityRequest,
  ): Promise<EmbeddingSimilarityResponse> {
    return this.request<EmbeddingSimilarityResponse>('POST', '/v1/embeddings/similarity', request);
  }

  async rerank(request: RerankRequest): Promise<RerankResponse> {
    return this.request<RerankResponse>('POST', '/v1/rerank', request);
  }

  async getContract(): Promise<PlatformContractResponse> {
    try {
      return assertPlatformContractResponse(
        await this.request<unknown>('GET', '/v1/meta/contract'),
      );
    } catch (error) {
      if (!(error instanceof NotFoundError)) {
        throw error;
      }
      const openapiSchema = await this.request<Record<string, unknown>>('GET', '/openapi.json');
      return assertPlatformContractResponse(
        buildPlatformContractFromOpenApi(this.baseUrl, openapiSchema),
      );
    }
  }

  async getRuntimeManifest(): Promise<RuntimeManifestResponse> {
    return assertRuntimeManifestResponse(
      await this.request<unknown>('GET', '/v1/runtime/manifest'),
    );
  }

  async getRuntimeModules(): Promise<RuntimeAdminModulesResponse> {
    return assertRuntimeAdminModulesResponse(
      await this.request<unknown>('GET', '/v1/admin/runtime/modules'),
    );
  }

  async getRuntimeBenchmarks(): Promise<RuntimeAdminBenchmarksResponse> {
    return assertRuntimeAdminBenchmarksResponse(
      await this.request<unknown>('GET', '/v1/admin/runtime/benchmarks'),
    );
  }

  async getRuntimeReleaseValidation(): Promise<RuntimeReleaseValidationResponse> {
    return assertRuntimeReleaseValidationResponse(
      await this.request<unknown>('GET', '/v1/admin/runtime/validation'),
    );
  }

  async listCapabilityProviders(): Promise<CapabilityProviderResponse[]> {
    return this.request<CapabilityProviderResponse[]>('GET', '/v1/capability-providers');
  }

  async getCapabilityProvider(providerId: string): Promise<CapabilityProviderResponse> {
    return this.request<CapabilityProviderResponse>(
      'GET',
      `/v1/capability-providers/${providerId}`,
    );
  }

  async listCapabilityBindings(
    options: {
      providerId?: string;
      scope?: string;
    } = {},
  ): Promise<CapabilityBindingResponse[]> {
    const path = appendQueryParameters('/v1/capability-bindings', {
      provider_id: options.providerId,
      scope: options.scope,
    });
    return this.request<CapabilityBindingResponse[]>('GET', path);
  }

  async createCapabilityBinding(
    request: CapabilityBindingCreateRequest,
  ): Promise<CapabilityBindingResponse> {
    return this.request<CapabilityBindingResponse>('POST', '/v1/capability-bindings', request);
  }

  async getCapabilityBinding(bindingId: string): Promise<CapabilityBindingResponse> {
    return this.request<CapabilityBindingResponse>('GET', `/v1/capability-bindings/${bindingId}`);
  }

  async updateCapabilityBinding(
    bindingId: string,
    request: CapabilityBindingUpdateRequest,
  ): Promise<CapabilityBindingResponse> {
    return this.request<CapabilityBindingResponse>(
      'PATCH',
      `/v1/capability-bindings/${bindingId}`,
      request,
    );
  }

  async deleteCapabilityBinding(bindingId: string): Promise<void> {
    await this.request('DELETE', `/v1/capability-bindings/${bindingId}`);
  }

  async previewTestCapabilityBinding(
    request: CapabilityBindingPreviewRequest,
  ): Promise<CapabilityBindingTestResult> {
    return this.request<CapabilityBindingTestResult>(
      'POST',
      '/v1/capability-bindings/test',
      request,
    );
  }

  async testCapabilityBinding(bindingId: string): Promise<CapabilityBindingTestResult> {
    return this.request<CapabilityBindingTestResult>(
      'POST',
      `/v1/capability-bindings/${bindingId}/test`,
    );
  }

  async previewDiscoverCapabilityBinding(
    request: CapabilityBindingPreviewRequest,
  ): Promise<CapabilityDiscoverResponse> {
    return this.request<CapabilityDiscoverResponse>(
      'POST',
      '/v1/capability-bindings/discover',
      request,
    );
  }

  async discoverCapabilityBinding(bindingId: string): Promise<CapabilityDiscoverResponse> {
    return this.request<CapabilityDiscoverResponse>(
      'POST',
      `/v1/capability-bindings/${bindingId}/discover`,
    );
  }

  async startCapabilityAuthorization(
    bindingId: string,
    request: CapabilityAuthorizationStartRequest,
  ): Promise<CapabilityAuthorizationStartResponse> {
    return this.request<CapabilityAuthorizationStartResponse>(
      'POST',
      `/v1/capability-bindings/${bindingId}/authorize/start`,
      request,
    );
  }

  async completeCapabilityAuthorization(
    bindingId: string,
    request: CapabilityAuthorizationCompleteRequest,
  ): Promise<CapabilityAuthorizationCompleteResponse> {
    return this.request<CapabilityAuthorizationCompleteResponse>(
      'POST',
      `/v1/capability-bindings/${bindingId}/authorize/complete`,
      request,
    );
  }

  async listCapabilities(
    options: {
      kinds?: string[];
      providerIds?: string[];
      bindingIds?: string[];
    } = {},
  ): Promise<CapabilityCatalogEntry[]> {
    const params = new URLSearchParams();
    (options.kinds ?? []).forEach(kind => params.append('kinds', kind));
    (options.providerIds ?? []).forEach(providerId => params.append('provider_ids', providerId));
    (options.bindingIds ?? []).forEach(bindingId => params.append('binding_ids', bindingId));
    const suffix = params.size > 0 ? `?${params.toString()}` : '';
    return this.request<CapabilityCatalogEntry[]>('GET', `/v1/capabilities${suffix}`);
  }

  async getCapability(
    capabilityId: string,
    options: { includeInstruction?: boolean } = {},
  ): Promise<CapabilityCatalogEntry> {
    const path = appendQueryParameters(`/v1/capabilities/${capabilityId}`, {
      include_instruction: options.includeInstruction ? 1 : undefined,
    });
    return this.request<CapabilityCatalogEntry>('GET', path);
  }

  async routeCapabilities(request: CapabilityRouteRequest): Promise<CapabilityRoutePlan> {
    return this.request<CapabilityRoutePlan>('POST', '/v1/capabilities/route', request);
  }

  async executeCapability(
    request: CapabilityExecutionRequest,
  ): Promise<CapabilityExecutionResponse> {
    return this.request<CapabilityExecutionResponse>('POST', '/v1/capabilities/execute', request);
  }

  async recordCapabilityOutcome(
    request: CapabilityOutcomeRecordRequest,
  ): Promise<CapabilityOutcomeRecord> {
    return this.request<CapabilityOutcomeRecord>('POST', '/v1/capabilities/outcomes', request);
  }

  async listSkills(): Promise<CapabilityCatalogEntry[]> {
    return this.listCapabilities({ kinds: ['skill'] });
  }

  async enableSkill(
    request: {
      skill_name: string;
      instruction: string;
      description?: string;
      tags?: string[];
      artifact_affinities?: string[];
      execution_owner?: "algenta_managed" | "client_managed";
    },
  ): Promise<CapabilityDiscoverResponse> {
    const binding = await this.createCapabilityBinding({
      provider_id: 'provider.skill_pack.algenta',
      profile_id: 'profile.skill_pack.user',
      binding_name: request.skill_name,
      scope: 'user',
      execution_owner: request.execution_owner ?? 'client_managed',
      config: {
        manifest: {
          capabilities: [
            {
              capability_id: `cap.skill.${request.skill_name.toLowerCase().replace(/\s+/g, "_")}`,
              name: request.skill_name,
              description: request.description,
              kind: 'skill',
              implementation_kind: 'instruction_only',
              execution_owner: request.execution_owner ?? 'client_managed',
              instruction: request.instruction,
              artifact_affinities: request.artifact_affinities ?? [],
              tags: request.tags ?? [],
              replayability: 'deterministic',
            },
          ],
        },
      },
    });
    return this.discoverCapabilityBinding(binding.binding_id);
  }

  async disableSkill(bindingId: string): Promise<void> {
    await this.deleteCapabilityBinding(bindingId);
  }

  async listMcpProviders(): Promise<CapabilityProviderResponse[]> {
    const providers = await this.listCapabilityProviders();
    return providers.filter(provider => provider.provider_type === 'mcp_provider');
  }

  async registerSource(
    source: SourceRegistrationRequest | Record<string, unknown>,
    options: { description?: string; name?: string } = {},
  ): Promise<SourceRegistrationResponse> {
    return this.request<SourceRegistrationResponse>(
      'POST',
      '/v1/sources/register',
      normalizeSourceRegistrationRequest(
        source,
        options.description,
        options.name ? { name: options.name } : {},
      ),
    );
  }

  async refreshSource(datasetId: string): Promise<SourceRegistrationResponse> {
    return this.request<SourceRegistrationResponse>('POST', `/v1/data/${datasetId}/refresh`);
  }

  async createAgentRun(request: AgentRunCreateRequest): Promise<AgentRunResponse> {
    return this.request<AgentRunResponse>('POST', '/v1/agent/runs', request);
  }

  async getAgentRun(runId: string): Promise<AgentRunResponse> {
    return this.request<AgentRunResponse>('GET', `/v1/agent/runs/${runId}`);
  }

  async listAgentRuns(
    options: {
      page?: number;
      limit?: number;
      status?: string;
      request_hash?: string;
      policy_snapshot_id?: string;
      schema_snapshot_id?: string;
    } = {},
  ): Promise<AgentRunListResponse> {
    const path = appendQueryParameters('/v1/agent/runs', {
      page: options.page ?? 1,
      limit: options.limit ?? 25,
      status: options.status,
      request_hash: options.request_hash,
      policy_snapshot_id: options.policy_snapshot_id,
      schema_snapshot_id: options.schema_snapshot_id,
    });
    return this.request<AgentRunListResponse>('GET', path);
  }

  async getAgentRunEvents(
    runId: string,
    options: { limit?: number } = {},
  ): Promise<AgentRunEventsResponse> {
    const path = appendQueryParameters(`/v1/agent/runs/${runId}/events`, {
      limit: options.limit ?? 1000,
    });
    return this.request<AgentRunEventsResponse>('GET', path);
  }

  async *streamAgentRunEvents(
    runId: string,
    options: { limit?: number } = {},
  ): AsyncGenerator<AgentRunStreamEventResponse> {
    const path = appendQueryParameters(`/v1/agent/runs/${runId}/events`, {
      limit: options.limit ?? 1000,
      stream: "true",
    });
    for await (const event of this.requestStream<AgentRunStreamEventResponse>('GET', path)) {
      yield event;
    }
  }

  async listAgentRunCheckpoints(runId: string): Promise<AgentRunCheckpointsResponse> {
    return this.request<AgentRunCheckpointsResponse>('GET', `/v1/agent/runs/${runId}/checkpoints`);
  }

  async queryAgentRunCheckpoints(
    options: {
      page?: number;
      limit?: number;
      status?: string;
      request_hash?: string;
      policy_snapshot_id?: string;
      schema_snapshot_id?: string;
      run_id?: string;
      checkpoint_id?: string;
    } = {},
  ): Promise<AgentRunCheckpointListResponse> {
    const path = appendQueryParameters('/v1/agent/runs/checkpoints', {
      page: options.page ?? 1,
      limit: options.limit ?? 25,
      status: options.status,
      request_hash: options.request_hash,
      policy_snapshot_id: options.policy_snapshot_id,
      schema_snapshot_id: options.schema_snapshot_id,
      run_id: options.run_id,
      checkpoint_id: options.checkpoint_id,
    });
    return this.request<AgentRunCheckpointListResponse>('GET', path);
  }

  async listAgentRunMissionEvents(
    runId: string,
    options: { limit?: number } = {},
  ): Promise<AgentRunMissionEventsResponse> {
    const path = appendQueryParameters(`/v1/agent/runs/${runId}/mission-events`, {
      limit: options.limit ?? 1000,
    });
    return this.request<AgentRunMissionEventsResponse>('GET', path);
  }

  async queryAgentRunMissionEvents(
    options: {
      page?: number;
      limit?: number;
      status?: string;
      request_hash?: string;
      policy_snapshot_id?: string;
      schema_snapshot_id?: string;
      run_id?: string;
      event_type?: string;
    } = {},
  ): Promise<AgentRunMissionEventListResponse> {
    const path = appendQueryParameters('/v1/agent/runs/mission-events', {
      page: options.page ?? 1,
      limit: options.limit ?? 25,
      status: options.status,
      request_hash: options.request_hash,
      policy_snapshot_id: options.policy_snapshot_id,
      schema_snapshot_id: options.schema_snapshot_id,
      run_id: options.run_id,
      event_type: options.event_type,
    });
    return this.request<AgentRunMissionEventListResponse>('GET', path);
  }

  async replayAgentRun(
    runId: string,
    options: { checkpoint_id?: string | null } = {},
  ): Promise<AgentRunReplayResponse> {
    return this.request<AgentRunReplayResponse>('POST', `/v1/agent/runs/${runId}/replay`, {
      checkpoint_id: options.checkpoint_id ?? null,
    });
  }

  async forkAgentRun(
    runId: string,
    options: { checkpoint_id?: string | null } = {},
  ): Promise<AgentRunResponse> {
    return this.request<AgentRunResponse>('POST', `/v1/agent/runs/${runId}/fork`, {
      checkpoint_id: options.checkpoint_id ?? null,
    });
  }

  async resumeAgentRun(runId: string): Promise<AgentRunResponse> {
    return this.request<AgentRunResponse>('POST', `/v1/agent/runs/${runId}/resume`, {});
  }

  async cancelAgentRun(runId: string): Promise<AgentRunResponse> {
    return this.request<AgentRunResponse>('POST', `/v1/agent/runs/${runId}/cancel`, {});
  }

  async approveAgentRun(runId: string): Promise<AgentRunResponse> {
    return this.request<AgentRunResponse>('POST', `/v1/agent/runs/${runId}/approve`, {});
  }

  async listAgentRunTelemetry(
    runId: string,
    options: { limit?: number } = {},
  ): Promise<AgentRunTelemetryResponse> {
    const path = appendQueryParameters(`/v1/agent/runs/${runId}/telemetry`, {
      limit: options.limit ?? 1000,
    });
    return this.request<AgentRunTelemetryResponse>('GET', path);
  }

  async queryAgentRunTelemetry(
    options: {
      page?: number;
      limit?: number;
      status?: string;
      request_hash?: string;
      policy_snapshot_id?: string;
      schema_snapshot_id?: string;
      run_id?: string;
      telemetry_kind?: string;
      module_name?: string;
    } = {},
  ): Promise<AgentRunTelemetryListResponse> {
    const path = appendQueryParameters('/v1/agent/runs/telemetry', {
      page: options.page ?? 1,
      limit: options.limit ?? 25,
      status: options.status,
      request_hash: options.request_hash,
      policy_snapshot_id: options.policy_snapshot_id,
      schema_snapshot_id: options.schema_snapshot_id,
      run_id: options.run_id,
      telemetry_kind: options.telemetry_kind,
      module_name: options.module_name,
    });
    return this.request<AgentRunTelemetryListResponse>('GET', path);
  }

  async createConnector(request: CreateConnectorRequest): Promise<ConnectorInfo> {
    return this.request<ConnectorInfo>('POST', '/v1/connectors', request);
  }

  async listConnectors(
    options: { page?: number; limit?: number } = {},
  ): Promise<ConnectorListResult> {
    const page = options.page ?? 1;
    const limit = options.limit ?? 200;
    const path = appendQueryParameters('/v1/connectors', {
      page,
      limit,
    });
    return assertConnectorListResponse(
      await this.request<unknown>('GET', path),
      page,
    );
  }

  async getConnector(connectorId: string): Promise<ConnectorInfo> {
    return this.request<ConnectorInfo>('GET', `/v1/connectors/${connectorId}`);
  }

  async updateConnector(
    connectorId: string,
    request: UpdateConnectorRequest,
  ): Promise<ConnectorInfo> {
    return this.request<ConnectorInfo>('PATCH', `/v1/connectors/${connectorId}`, request);
  }

  async testConnector(connectorId: string): Promise<ConnectorTestInfo> {
    return this.request<ConnectorTestInfo>('POST', `/v1/connectors/${connectorId}/test`);
  }

  async previewTestConnector(request: PreviewConnectorRequest): Promise<ConnectorTestInfo> {
    return this.request<ConnectorTestInfo>('POST', '/v1/connectors/test', request);
  }

  async browseConnector(connectorId: string): Promise<ConnectorBrowseResult> {
    return this.request<ConnectorBrowseResult>('GET', `/v1/connectors/${connectorId}/browse`);
  }

  async previewBrowseConnector(request: PreviewConnectorRequest): Promise<ConnectorBrowseResult> {
    return this.request<ConnectorBrowseResult>('POST', '/v1/connectors/browse', request);
  }

  async createRepositorySnapshot(
    repositoryId: string,
    request: RepositorySnapshotCreateRequest,
  ): Promise<RepositorySnapshotResponse> {
    return this.request<RepositorySnapshotResponse>(
      'POST',
      `/v1/repositories/${repositoryId}/snapshots`,
      request,
    );
  }

  async getRepositoryIntelligenceCapabilities(): Promise<RepositoryIntelligenceCapabilitiesResponse> {
    return this.request<RepositoryIntelligenceCapabilitiesResponse>(
      'GET',
      '/v1/repositories/capabilities',
    );
  }

  async getRepositorySnapshot(
    repositoryId: string,
    snapshotId: string,
  ): Promise<RepositorySnapshotResponse> {
    return this.request<RepositorySnapshotResponse>(
      'GET',
      `/v1/repositories/${repositoryId}/snapshots/${snapshotId}`,
    );
  }

  async triageRepository(
    repositoryId: string,
    request: RepositoryTriageRequest,
  ): Promise<RepositoryTriageResponse> {
    return this.request<RepositoryTriageResponse>(
      'POST',
      `/v1/repositories/${repositoryId}/triage`,
      request,
    );
  }

  async createRepositoryDecisionPlan(
    repositoryId: string,
    request: RepositoryDecisionPlanCreateRequest,
  ): Promise<RepositoryDecisionPlanRevisionResponse> {
    return this.request<RepositoryDecisionPlanRevisionResponse>(
      'POST',
      `/v1/repositories/${repositoryId}/decision-plans`,
      request,
    );
  }

  async queryRepositoryGraph(
    repositoryId: string,
    request: RepositoryGraphQueryRequest,
  ): Promise<RepositoryGraphQueryResponse> {
    return this.request<RepositoryGraphQueryResponse>(
      'POST',
      `/v1/repositories/${repositoryId}/graph-query`,
      request,
    );
  }

  async simulateRepository(
    repositoryId: string,
    request: RepositorySimulationRequest,
  ): Promise<DecisionEnvelope> {
    return this.request<DecisionEnvelope>(
      'POST',
      `/v1/repositories/${repositoryId}/simulate`,
      request,
    );
  }

  async applyRepository(
    repositoryId: string,
    request: RepositoryApplyRequest,
  ): Promise<RepositoryApplyResponse> {
    return this.request<RepositoryApplyResponse>(
      'POST',
      `/v1/repositories/${repositoryId}/apply`,
      request,
    );
  }

  async deleteConnector(connectorId: string): Promise<void> {
    await this.request('DELETE', `/v1/connectors/${connectorId}`);
  }

  async connectData(request: ConnectDataRequest): Promise<DatasetConnectResult> {
    return this.request<DatasetConnectResult>('POST', '/v1/data/connect', request);
  }

  async listDatasets(
    options: {
      page?: number;
      limit?: number;
      search?: string;
      status?: string;
      sourceName?: string;
      compact?: boolean;
    } = {},
  ): Promise<DatasetListResult> {
    const page = options.page ?? 1;
    const limit = options.limit ?? 200;
    const path = appendQueryParameters('/v1/data', {
      page,
      limit,
      search: options.search,
      status: options.status,
      source_name: options.sourceName,
      compact: options.compact ? 1 : undefined,
    });
    return assertDatasetListResponse(
      await this.request<unknown>('GET', path),
      page,
    );
  }

  async getDataset(datasetId: string): Promise<DatasetDetailResult> {
    return this.request<DatasetDetailResult>('GET', `/v1/data/${datasetId}`);
  }

  async getDatasetSummary(datasetId: string): Promise<DatasetSummaryResult> {
    return assertDatasetSummaryResponse(
      await this.request<unknown>('GET', `/v1/data/${datasetId}/summary`),
    );
  }

  async refreshDataset(datasetId: string): Promise<DatasetConnectResult> {
    return this.request<DatasetConnectResult>('POST', `/v1/data/${datasetId}/refresh`);
  }

  async deleteDataset(datasetId: string): Promise<DatasetDeleteResult> {
    return this.request<DatasetDeleteResult>('DELETE', `/v1/data/${datasetId}`);
  }

  async explain(request: Record<string, unknown>): Promise<ExplainResponse> {
    const result = await this.query(mergeRequestPayload(request));
    return buildExplainResponse(request, result);
  }

  async recommend(
    actions: Array<{ name: string; request: SimulateRequest }>,
    options?: { runs?: number; seed?: number },
  ): Promise<RecommendResponse> {
    return this.request<RecommendResponse>('POST', '/v1/recommend', { actions, ...options });
  }

  async score(
    request: SimulateRequest,
    scoringWeights?: Record<string, number>,
  ): Promise<ScoreResponse> {
    return this.request<ScoreResponse>('POST', '/v1/score', {
      request,
      scoring_weights: scoringWeights,
    });
  }

  async batch(items: SimulateRequest[]): Promise<BatchResult> {
    return this.request<BatchResult>('POST', '/v1/batch', { items });
  }

  async compare(
    scenarios: Array<{ name: string; request: SimulateRequest }>,
    options?: { runs?: number; seed?: number },
  ): Promise<CompareResponse> {
    return this.request<CompareResponse>('POST', '/v1/compare', {
      scenarios,
      ...options,
    });
  }

  // ─── Async Jobs ───────────────────────────────────────────────────────────

  async submitJob(request: SimulateRequest, callbackUrl?: string): Promise<JobSubmitResponse> {
    return this.request<JobSubmitResponse>('POST', '/v1/jobs', { request, callback_url: callbackUrl });
  }

  async getJob(jobId: string): Promise<JobStatusResponse> {
    return this.request<JobStatusResponse>('GET', `/v1/jobs/${jobId}`);
  }

  async getJobResult(jobId: string): Promise<Record<string, unknown>> {
    return this.request('GET', `/v1/jobs/${jobId}/result`);
  }

  async listJobs(options: { page?: number; limit?: number; status?: string } = {}): Promise<JobListResponse> {
    const query = new URLSearchParams();
    query.set("page", String(options.page ?? 1));
    query.set("limit", String(options.limit ?? 25));
    if (options.status) {
      query.set("status", options.status);
    }
    return this.request<JobListResponse>('GET', `/v1/jobs/list?${query.toString()}`);
  }

  async cancelJob(jobId: string): Promise<JobStatusResponse> {
    return this.request<JobStatusResponse>('POST', `/v1/jobs/${jobId}/cancel`);
  }

  async testWebhookDelivery(callbackUrl: string): Promise<WebhookTestResponse> {
    return this.request<WebhookTestResponse>('POST', '/v1/webhooks/test', {
      callback_url: callbackUrl,
    });
  }

  async registerTrigger(request: RegisterTriggerRequest): Promise<TriggerResponse> {
    return this.request<TriggerResponse>('POST', '/v1/triggers', request);
  }

  async listTriggers(options: { status?: "active" | "paused" | "all"; page?: number; limit?: number } = {}): Promise<TriggerListResponse> {
    const query = new URLSearchParams();
    if (options.status && options.status !== 'all') {
      query.set("status", options.status);
    }
    if (options.page !== undefined) {
      query.set("page", String(options.page));
    }
    if (options.limit !== undefined) {
      query.set("limit", String(options.limit));
    }
    const suffix = query.toString();
    return this.request<TriggerListResponse>('GET', suffix ? `/v1/triggers?${suffix}` : '/v1/triggers');
  }

  async fireTrigger(triggerId: string, options: { force?: boolean } = {}): Promise<TriggerFireResponse> {
    return this.request<TriggerFireResponse>('POST', `/v1/triggers/${triggerId}/fire`, {
      force: options.force ?? false,
    });
  }

  async pauseTrigger(triggerId: string, options: { paused?: boolean } = {}): Promise<TriggerPauseResponse> {
    const paused = options.paused ?? true;
    return this.request<TriggerPauseResponse>('PATCH', `/v1/triggers/${triggerId}/pause?paused=${paused ? 'true' : 'false'}`);
  }

  async deleteTrigger(triggerId: string): Promise<TriggerDeleteResponse> {
    await this.request('DELETE', `/v1/triggers/${triggerId}`);
    return { trigger_id: triggerId, deleted: true };
  }

  async pollJob(jobId: string, options: { timeoutMs?: number; pollIntervalMs?: number } = {}): Promise<Record<string, unknown>> {
    const { timeoutMs = 300_000, pollIntervalMs = 2_000 } = options;
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const status = await this.getJob(jobId);
      if (status.status === 'completed') return this.getJobResult(jobId);
      if (status.status === 'failed' || status.status === 'cancelled') {
        throw new DecisionEngineError(`Job ${jobId} ended with status '${status.status}': ${status.error_message}`);
      }
      await new Promise(resolve => setTimeout(resolve, pollIntervalMs));
    }
    throw new DecisionEngineError(`Job ${jobId} timed out after ${timeoutMs}ms`);
  }

  // ─── Account ──────────────────────────────────────────────────────────────

  async me(): Promise<MeResponse> {
    return assertMeResponse(await this.request<unknown>('GET', '/v1/me'));
  }

  async updateMe(request: UpdateMeRequest): Promise<MeResponse> {
    return assertMeResponse(
      await this.request<unknown>('PATCH', '/v1/me', normalizeUpdateMeRequest(request)),
    );
  }

  async usage(): Promise<UsageInfo> {
    return assertUsageInfoResponse(await this.request<unknown>('GET', '/v1/usage'));
  }

  async limits(): Promise<LimitsInfo> {
    return assertLimitsInfoResponse(await this.request<unknown>('GET', '/v1/limits'));
  }

  async distributions(): Promise<DistributionListResponse> {
    return assertDistributionListResponse(await this.request<unknown>('GET', '/v1/distributions'));
  }

  async templates(): Promise<TemplateListResponse> {
    return assertTemplateListResponse(await this.request<unknown>('GET', '/v1/templates'));
  }

  async getBillingInfo(): Promise<BillingInfoResponse> {
    return assertBillingInfoResponse(await this.request<unknown>('GET', '/v1/billing/info'));
  }

  async createBillingCheckout(
    options: { plan?: "developer" | "pro" } = {},
  ): Promise<BillingSessionResponse> {
    return assertBillingSessionResponse(
      await this.request<unknown>('POST', '/v1/billing/checkout', options),
    );
  }

  async createBillingPortal(): Promise<BillingSessionResponse> {
    return assertBillingSessionResponse(
      await this.request<unknown>('POST', '/v1/billing/portal', {}),
    );
  }

  async refreshCredits(request: CreditRefreshRequest): Promise<CreditRefreshResponse> {
    return assertCreditRefreshResponse(
      await this.request<unknown>('POST', '/v1/credits/refresh', normalizeCreditRefreshRequest(request)),
    );
  }

  async ingestMeteringEvents(request: MeteringBatchRequest): Promise<MeteringBatchResponse> {
    return assertMeteringBatchResponse(
      await this.request<unknown>('POST', '/v1/metering', normalizeMeteringBatchRequest(request)),
    );
  }

  async listApiKeys(): Promise<APIKeyInfo[]> {
    return assertApiKeyListResponse(await this.request<unknown>('GET', '/v1/api-keys'));
  }

  async createApiKey(request: CreateAPIKeyRequest): Promise<APIKeyCreated> {
    return assertApiKeyCreateResponse(
      await this.request<unknown>('POST', '/v1/api-keys', normalizeApiKeyCreateRequest(request)),
    );
  }

  async revokeApiKey(keyId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('DELETE', `/v1/api-keys/${keyId}`);
  }

  async listTeamMembers(options: { page?: number; limit?: number } = {}): Promise<TeamListResponse> {
    const params = new URLSearchParams();
    if (options.page !== undefined) params.set('page', String(options.page));
    if (options.limit !== undefined) params.set('limit', String(options.limit));
    const suffix = params.size > 0 ? `?${params.toString()}` : '';
    return assertTeamListResponse(await this.request<unknown>('GET', `/v1/team${suffix}`));
  }

  async inviteTeamMember(request: TeamInviteRequest): Promise<TeamInviteResponse> {
    return assertTeamInviteResponse(
      await this.request<unknown>('POST', '/v1/team/invite', normalizeTeamInviteRequest(request)),
    );
  }

  async updateTeamMemberRole(
    userId: string,
    role: "owner" | "admin" | "member" | "viewer",
  ): Promise<TeamRoleUpdateResponse> {
    if (typeof userId !== "string" || userId.length === 0) {
      throw new DecisionEngineError("updateTeamMemberRole requires a non-empty userId.");
    }
    return assertTeamRoleUpdateResponse(
      await this.request<unknown>(
        'PATCH',
        `/v1/team/${userId}/role`,
        { role: normalizeTeamRole(role, "updateTeamMemberRole") },
      ),
    );
  }

  async removeTeamMember(userId: string): Promise<TeamRemoveResponse> {
    if (typeof userId !== "string" || userId.length === 0) {
      throw new DecisionEngineError("removeTeamMember requires a non-empty userId.");
    }
    return assertTeamRemoveResponse(
      await this.request<unknown>('DELETE', `/v1/team/${userId}`),
      userId,
    );
  }

  async listDevices(options: { page?: number; limit?: number } = {}): Promise<DeviceListResponse> {
    const params = new URLSearchParams();
    if (options.page !== undefined) params.set('page', String(options.page));
    if (options.limit !== undefined) params.set('limit', String(options.limit));
    const suffix = params.size > 0 ? `?${params.toString()}` : '';
    return assertDeviceListResponse(await this.request<unknown>('GET', `/v1/device/list${suffix}`));
  }

  async revokeDevice(registrationId: string): Promise<DeviceRevokeResponse> {
    if (typeof registrationId !== "string" || registrationId.length === 0) {
      throw new DecisionEngineError("revokeDevice requires a non-empty registrationId.");
    }
    return assertDeviceRevokeResponse(
      await this.request<unknown>('DELETE', `/v1/device/${registrationId}`),
    );
  }

  async getAuditLogs(
    options: {
      page?: number;
      limit?: number;
      actor_email?: string;
      action?: string;
      resource_type?: string;
      result?: string;
      policy_snapshot_id?: string;
      schema_snapshot_id?: string;
      manifest_version?: string;
      request_hash?: string;
    } = {},
  ): Promise<AuditLogResponse> {
    const params = new URLSearchParams();
    if (options.page !== undefined) params.set('page', String(options.page));
    if (options.limit !== undefined) params.set('limit', String(options.limit));
    if (options.actor_email !== undefined) params.set('actor_email', options.actor_email);
    if (options.action !== undefined) params.set('action', options.action);
    if (options.resource_type !== undefined) params.set('resource_type', options.resource_type);
    if (options.result !== undefined) params.set('result', options.result);
    if (options.policy_snapshot_id !== undefined) {
      params.set('policy_snapshot_id', options.policy_snapshot_id);
    }
    if (options.schema_snapshot_id !== undefined) {
      params.set('schema_snapshot_id', options.schema_snapshot_id);
    }
    if (options.manifest_version !== undefined) {
      params.set('manifest_version', options.manifest_version);
    }
    if (options.request_hash !== undefined) params.set('request_hash', options.request_hash);
    const suffix = params.size > 0 ? `?${params.toString()}` : '';
    return assertAuditLogResponse(await this.request<unknown>('GET', `/v1/audit-logs${suffix}`));
  }

  async getAuditLogArtifacts(
    options: {
      page?: number;
      limit?: number;
      actor_email?: string;
      action?: string;
      resource_type?: string;
      result?: string;
      policy_snapshot_id?: string;
      schema_snapshot_id?: string;
      manifest_version?: string;
      request_hash?: string;
      content_hash?: string;
    } = {},
  ): Promise<AuditLogResponse> {
    const params = new URLSearchParams();
    if (options.page !== undefined) params.set('page', String(options.page));
    if (options.limit !== undefined) params.set('limit', String(options.limit));
    if (options.actor_email !== undefined) params.set('actor_email', options.actor_email);
    if (options.action !== undefined) params.set('action', options.action);
    if (options.resource_type !== undefined) params.set('resource_type', options.resource_type);
    if (options.result !== undefined) params.set('result', options.result);
    if (options.policy_snapshot_id !== undefined) {
      params.set('policy_snapshot_id', options.policy_snapshot_id);
    }
    if (options.schema_snapshot_id !== undefined) {
      params.set('schema_snapshot_id', options.schema_snapshot_id);
    }
    if (options.manifest_version !== undefined) {
      params.set('manifest_version', options.manifest_version);
    }
    if (options.request_hash !== undefined) params.set('request_hash', options.request_hash);
    if (options.content_hash !== undefined) params.set('content_hash', options.content_hash);
    const suffix = params.size > 0 ? `?${params.toString()}` : '';
    return assertAuditLogResponse(
      await this.request<unknown>('GET', `/v1/audit-logs/artifacts${suffix}`),
    );
  }

  async getExecutionPolicy(): Promise<ExecutionPolicyResponse> {
    return assertExecutionPolicyResponse(await this.request<unknown>('GET', '/v1/execution/policy'));
  }

  async listExecutionPolicySnapshots(): Promise<ExecutionPolicySnapshotListResponse> {
    return assertExecutionPolicySnapshotListResponse(
      await this.request<unknown>('GET', '/v1/execution/policy/snapshots'),
    );
  }

  async updateExecutionPolicy(
    request: UpdateExecutionPolicyRequest,
  ): Promise<ExecutionPolicyResponse> {
    return assertExecutionPolicyResponse(
      await this.request<unknown>(
        'PATCH',
        '/v1/execution/policy',
        normalizeUpdateExecutionPolicyRequest(request),
      ),
    );
  }

  async listDeploymentRegions(): Promise<DeploymentRegionsResponse> {
    return assertDeploymentRegionsResponse(await this.request<unknown>('GET', '/v1/deployments/regions'));
  }

  async getDeployment(): Promise<DeploymentResponse | null> {
    const payload = await this.request<unknown>('GET', '/v1/deployments');
    if (payload === null) return null;
    return assertDeploymentResponse(payload, "Deployment response");
  }

  async createDeployment(request: CreateDeploymentRequest = {}): Promise<DeploymentResponse> {
    return assertDeploymentResponse(
      await this.request<unknown>('POST', '/v1/deployments', normalizeCreateDeploymentRequest(request)),
      "Deployment create response",
    );
  }

  async deleteDeployment(deploymentId: string): Promise<DeploymentDeleteResponse> {
    return assertDeploymentDeleteResponse(
      await this.request<unknown>('DELETE', `/v1/deployments/${deploymentId}`),
    );
  }

  async getDeploymentCost(deploymentId: string): Promise<DeploymentCostResponse> {
    return assertDeploymentCostResponse(
      await this.request<unknown>('GET', `/v1/deployments/${deploymentId}/cost`),
    );
  }

  async health(): Promise<{ status: string; timestamp: string }> {
    return this.request('GET', '/v1/health');
  }

  async version(): Promise<{ api_version: string; engine_version: string; environment: string }> {
    return this.request('GET', '/v1/version');
  }

}

export { DecisionEngineClient as AlgentaClient };
export type { DecisionEngineClientConfig as AlgentaClientConfig };

export default DecisionEngineClient;
