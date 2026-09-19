// SPDX-License-Identifier: Apache-2.0
/** Auto-split sub-module of runtime.ts — the Runtime class. */

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
  AuditLogResponse,
  BillingInfoResponse,
  BillingSessionResponse,
  BatchResult,
  ChatCompletionsRequest,
  ChatCompletionsResponse,
  ChatCompletionsStreamChunkResponse,
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
  DecisionEnvelope,
  DecisionListResponse,
  DecisionLogResponse,
  DeviceListResponse,
  DeviceRevokeResponse,
  DistributionListResponse,
  DecisionPlanResponse,
  DecisionEngineClientConfig,
  DeploymentCostResponse,
  DeploymentDeleteResponse,
  DeploymentRegionsResponse,
  DeploymentResponse,
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
  DatasetConnectResult,
  DatasetDeleteResult,
  DatasetDetailResult,
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
  ArtifactBridgeResolveRequest,
  ArtifactBridgeResolveResponse,
  BindingScope,
  BindingStatus,
  CapabilityAdapter,
  CapabilityAdapterDescriptor,
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
  CapabilityProviderResponse,
  CapabilityRoutePlan,
  CapabilityRouteRequest,
  ExecutionOwner,
  ExecutionSessionStatus,
  JobStatusResponse,
  JobSubmitResponse,
  JobListResponse,
  WebhookTestResponse,
  LLMModelListResponse,
  LogDecisionRequest,
  MeteringBatchRequest,
  MeteringBatchResponse,
  MeResponse,
  PlatformContractResponse,
  QueryCandidate,
  QueryBatchResponse,
  QuerySqlReportRequest,
  QuerySqlReportResponse,
  QueryResponse,
  QueryWithMetadataResponse,
  RecordOutcomeRequest,
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
  RecommendResponse,
  ResolveResponse,
  ResolvedPlan,
  ResponseStreamEventResponse,
  ResponsesRequest,
  ResponsesResponse,
  RerankRequest,
  RerankResponse,
  RuntimeAdminBenchmarksResponse,
  RuntimeAdminModulesResponse,
  RuntimeManifestResponse,
  RuntimeReleaseValidationResponse,
  ScoreResponse,
  SimulateRequest,
  SourceRegistrationResponse,
  TokenizeRequest,
  TokenizeResponse,
  TeamListResponse,
  TeamInviteRequest,
  TeamInviteResponse,
  TeamRemoveResponse,
  TeamRoleUpdateResponse,
  TemplateListResponse,
  TriggerDeleteResponse,
  TriggerFireResponse,
  TriggerListResponse,
  TriggerPauseResponse,
  TriggerResponse,
  RegisterTriggerRequest,
  UpdateMeRequest,
  UpdateExecutionPolicyRequest,
  UsageInfo,
  LimitsInfo,
  VerifyResponse,
} from "./types.js";
import {
  DecisionEngineClient,
  DecisionEngineError,
  assertPlatformContractResponse,
  assertRuntimeAdminBenchmarksResponse,
  assertRuntimeAdminModulesResponse,
  assertRuntimeManifestResponse,
  assertRuntimeReleaseValidationResponse,
} from "./client.js";
import { resolveClientBaseUrl } from "./privacy_profile.js";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import { createHash, createHmac, createVerify, timingSafeEqual } from "node:crypto";
import { homedir, hostname, platform, release } from "node:os";
import { extname, join, resolve as resolvePath } from "node:path";
import {
  RuntimeEgressPolicyDeniedError,
  deploymentMode,
  meteringMode,
  privateProfile,
  requireLocalLicense,
  resolveControlPlaneBaseUrl,
  telemetryMode,
  validatedControlPlaneBaseUrl,
} from "./runtime_privacy.js";


import {
  ImportBundlePreviewOptions,
  ImportBundlePreviewResult,
  ImportFailureResult,
  ImportPreviewOptions,
  ImportPreviewResult,
  LocalRecord,
  LocalRuntimeLicense,
  LocalSource,
  RUNTIME_DATASET_SCOPE_KEY,
  RankedField,
  RuntimeConfig,
  RuntimeConnectOptions,
  RuntimeMode,
} from "./_runtime_constants.js";
import { RuntimeConfigurationError, RuntimeError, RuntimeValidationError } from "./_runtime_errors.js";
import {
  deviceInfo,
  loadLocalLicense,
  normalizeText,
  observeTrustedTime,
  runtimeEnv,
  sha256Hex,
  stableHash,
  trustedNowEpoch,
} from "./_runtime_helpers_a.js";
import {
  applyLocalFilterConditions,
  findLocalTimeField,
  isExactFieldMatch,
  isNumericField,
  mergeRequest,
  metricSynonymSet,
  orderedFields,
  parseDateValue,
  registrationDatasetId,
  registrationFields,
  registrationResolvedSourceName,
  resolveAggregation,
  resolveLocalFilterConditions,
  roundLatency,
  semanticScore,
  timeRange,
} from "./_runtime_helpers_b.js";
import {
  flattenConnectorEnvelope,
  isCanonicalConnectorEnvelope,
  normalizeApiSourcePayload,
  sourceReference,
  stripUndefined,
} from "./_runtime_helpers_c.js";
import {
  coerceRecords,
  exactPlanHash,
  executePlan,
  intentSignature,
  localSourceName,
  looksLikeResolvedPlan,
  renderSourceBundlePreview,
  renderSourceImportPreview,
} from "./_runtime_helpers_d.js";

export class Runtime {
  readonly mode: RuntimeMode;
  readonly apiKey?: string;
  readonly enforceLimits: boolean;
  readonly baseUrl?: string;
  readonly clientInstance?: DecisionEngineClient;
  readonly clientConfig: DecisionEngineClientConfig;
  readonly localSources = new Map<string, LocalSource>();
  readonly apiRegistrationsByName = new Map<string, SourceRegistrationResponse>();
  readonly apiRegistrationsByDataset = new Map<string, SourceRegistrationResponse>();
  readonly capabilityAdapters = new Map<string, CapabilityAdapter>();
  readonly localCapabilityBindings = new Map<string, CapabilityBindingResponse>();
  readonly localCapabilityCatalog = new Map<string, CapabilityCatalogEntry>();
  readonly localCapabilityAuthSessions = new Map<
    string,
    {
      session_id: string;
      binding_id: string;
      provider_id: string;
      authorize_url: string;
      expires_at: string;
      requested_scopes: string[];
    }
  >();
  readonly localCapabilityOutcomes: CapabilityOutcomeRecord[] = [];
  lazyClient?: DecisionEngineClient;
  localLicense?: LocalRuntimeLicense;
  licensePromise?: Promise<LocalRuntimeLicense>;

  constructor(config: RuntimeConfig = {}) {
    this.mode = config.mode ?? "local";
    if (!["local", "api", "self_hosted"].includes(this.mode)) {
      throw new RuntimeValidationError("invalid_mode", "Invalid mode. Expected 'local', 'api', or 'self_hosted'.", {
        mode: config.mode,
      });
    }
    if (deploymentMode() === "air_gapped" && (telemetryMode() === "control_plane_sync" || meteringMode() === "control_plane_sync")) {
      throw new RuntimeConfigurationError(
        "air_gapped_control_plane_sync_forbidden",
        "air_gapped deployments cannot use control_plane_sync telemetry or metering.",
      );
    }
    const controlPlaneSyncEnabled =
      telemetryMode() === "control_plane_sync" || meteringMode() === "control_plane_sync";
    const explicitControlPlaneUrl = (runtimeEnv().ALGENTA_CONTROL_PLANE_URL ?? "").trim();
    const resolvedControlPlaneUrl = resolveControlPlaneBaseUrl(config.baseUrl);
    if (controlPlaneSyncEnabled && !resolvedControlPlaneUrl) {
      throw new RuntimeConfigurationError(
        "control_plane_url_required",
        "control_plane_sync requires a non-empty ALGENTA_CONTROL_PLANE_URL or explicit baseUrl.",
      );
    }
    if ((controlPlaneSyncEnabled || explicitControlPlaneUrl) && resolvedControlPlaneUrl) {
      try {
        validatedControlPlaneBaseUrl(config.baseUrl, {
          surface: "runtime_control_plane_config",
          record: false,
        });
      } catch (error) {
        if (error instanceof RuntimeEgressPolicyDeniedError) {
          throw new RuntimeConfigurationError(
            "egress_policy_denied",
            `Control-plane egress is blocked by the active privacy policy. Reason: ${error.decision.reason}.`,
            {
              reason: error.decision.reason,
              surface: error.decision.surface,
              egress_class: error.decision.egressClass,
            },
          );
        }
        if (error instanceof Error) {
          throw new RuntimeConfigurationError("control_plane_url_invalid", error.message);
        }
        throw error;
      }
    }
    const envApiKey =
      typeof globalThis !== "undefined" &&
      "process" in globalThis &&
      (globalThis as { process?: { env?: { ALGENTA_API_KEY?: string; DE_API_KEY?: string } } }).process?.env
        ? (globalThis as { process?: { env?: { ALGENTA_API_KEY?: string; DE_API_KEY?: string } } }).process?.env
            ?.ALGENTA_API_KEY ??
          (globalThis as { process?: { env?: { ALGENTA_API_KEY?: string; DE_API_KEY?: string } } }).process?.env
            ?.DE_API_KEY
        : undefined;
    const explicitApiKey = Object.prototype.hasOwnProperty.call(config, "apiKey");
    this.apiKey = config.apiKey ?? envApiKey;
    this.enforceLimits = config.enforceLimits ?? (this.mode === "local" && explicitApiKey);
    if (this.mode === "self_hosted") {
      if (typeof config.baseUrl !== "string" || !config.baseUrl.trim()) {
        throw new RuntimeConfigurationError(
          "self_hosted_base_url_required",
          "Runtime({ mode: 'self_hosted' }) requires an explicit baseUrl.",
        );
      }
      this.baseUrl = resolveClientBaseUrl(
        config.baseUrl.trim(),
        "Runtime({ mode: 'self_hosted' })",
      );
    } else if (this.mode === "api") {
      this.baseUrl = resolveClientBaseUrl(
        config.baseUrl,
        "Runtime({ mode: 'api' })",
      );
    } else {
      this.baseUrl = config.baseUrl;
    }
    this.clientInstance = config.client;
    this.clientConfig = {
      apiKey: this.apiKey,
      baseUrl: this.baseUrl,
      timeout: config.timeout,
      maxRetries: config.maxRetries,
      defaultHeaders: config.defaultHeaders,
    };
    for (const adapter of config.capabilityAdapters ?? []) {
      this.registerCapabilityAdapter(adapter);
    }
  }

  toString(): string {
    return `Runtime(mode=${JSON.stringify(this.mode)}, apiKey=${this.apiKey ? "set" : "not set"})`;
  }

  usesApiTransport(): boolean {
    return this.mode === "api" || this.mode === "self_hosted";
  }

  requireApiTransport(methodName: string): void {
    if (this.usesApiTransport()) {
      return;
    }
    throw new RuntimeConfigurationError(
      "local_mode_not_supported",
      `${methodName}() is not supported for Runtime({ mode: 'local' }). Use Runtime({ mode: 'api', apiKey: '...' }) or Runtime({ mode: 'self_hosted', baseUrl: '...' }).`,
    );
  }

  buildNormalizedContractErrorDetails(error: DecisionEngineError): Record<string, unknown> {
    const details: Record<string, unknown> = {
      cause: error.message,
      source_error_code: error.errorCode,
      source_status_code: error.statusCode,
    };
    if (error.details && typeof error.details === "object" && !Array.isArray(error.details)) {
      details.source_error_details = error.details;
    }
    return details;
  }

  rethrowNormalizedContractError(
    error: unknown,
    runtimeCode: string,
    message: string,
    upstreamErrorCodes: ReadonlyArray<string>,
  ): never {
    if (
      error instanceof DecisionEngineError &&
      upstreamErrorCodes.includes(error.errorCode)
    ) {
      throw new RuntimeValidationError(
        runtimeCode,
        message,
        this.buildNormalizedContractErrorDetails(error),
      );
    }
    throw error;
  }

  async requestValidatedContractPayload<T>(
    methodName: string,
    requester: () => Promise<unknown>,
    validator: (value: unknown) => T,
  ): Promise<T> {
    let payload: unknown;
    try {
      payload = await requester();
    } catch (error) {
      this.rethrowNormalizedContractError(
        error,
        "invalid_contract_payload",
        `${methodName}() returned an invalid payload.`,
        ["invalid_contract_payload", "contract_extension_missing"],
      );
    }
    return this.validateContractPayload(methodName, payload, validator);
  }

  validateContractPayload<T>(
    methodName: string,
    payload: unknown,
    validator: (value: unknown) => T,
  ): T {
    try {
      return validator(payload);
    } catch (error) {
      if (error instanceof DecisionEngineError) {
        throw new RuntimeValidationError(
          "invalid_contract_payload",
          `${methodName}() returned an invalid payload.`,
          this.buildNormalizedContractErrorDetails(error),
        );
      }
      throw error;
    }
  }

  validateRuntimeProofPayload<T>(
    methodName: string,
    payload: unknown,
    validator: (value: unknown) => T,
  ): T {
    try {
      return validator(payload);
    } catch (error) {
      if (error instanceof DecisionEngineError) {
        throw new RuntimeValidationError(
          "invalid_runtime_contract_payload",
          `${methodName}() returned an invalid signed payload.`,
          this.buildNormalizedContractErrorDetails(error),
        );
      }
      throw error;
    }
  }

  async requestValidatedRuntimeProofPayload<T>(
    methodName: string,
    requester: () => Promise<unknown>,
    validator: (value: unknown) => T,
  ): Promise<T> {
    let payload: unknown;
    try {
      payload = await requester();
    } catch (error) {
      this.rethrowNormalizedContractError(
        error,
        "invalid_runtime_contract_payload",
        `${methodName}() returned an invalid signed payload.`,
        ["invalid_runtime_contract_payload"],
      );
    }
    return this.validateRuntimeProofPayload(methodName, payload, validator);
  }

  async getRuntimeManifest(): Promise<RuntimeManifestResponse> {
    this.requireApiTransport("getRuntimeManifest");
    return this.requestValidatedRuntimeProofPayload(
      "getRuntimeManifest",
      () => this.client().getRuntimeManifest(),
      assertRuntimeManifestResponse,
    );
  }

  async getRuntimeModules(): Promise<RuntimeAdminModulesResponse> {
    this.requireApiTransport("getRuntimeModules");
    return this.requestValidatedRuntimeProofPayload(
      "getRuntimeModules",
      () => this.client().getRuntimeModules(),
      assertRuntimeAdminModulesResponse,
    );
  }

  async getRuntimeBenchmarks(): Promise<RuntimeAdminBenchmarksResponse> {
    this.requireApiTransport("getRuntimeBenchmarks");
    return this.requestValidatedRuntimeProofPayload(
      "getRuntimeBenchmarks",
      () => this.client().getRuntimeBenchmarks(),
      assertRuntimeAdminBenchmarksResponse,
    );
  }

  async getRuntimeReleaseValidation(): Promise<RuntimeReleaseValidationResponse> {
    this.requireApiTransport("getRuntimeReleaseValidation");
    return this.requestValidatedRuntimeProofPayload(
      "getRuntimeReleaseValidation",
      () => this.client().getRuntimeReleaseValidation(),
      assertRuntimeReleaseValidationResponse,
    );
  }

  client(): DecisionEngineClient {
    if (this.clientInstance) {
      return this.clientInstance;
    }
    if (this.lazyClient) {
      return this.lazyClient;
    }
    if (!this.apiKey) {
      throw new RuntimeConfigurationError(
        "api_key_required",
        "API and self_hosted mode require an API key. Set ALGENTA_API_KEY / DE_API_KEY or pass apiKey.",
      );
    }
    this.lazyClient = new DecisionEngineClient(this.clientConfig);
    return this.lazyClient;
  }

}
