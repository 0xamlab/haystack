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
  CREDIT_TTL_SECONDS,
  ImportBundlePreviewOptions,
  ImportBundlePreviewResult,
  ImportFailureResult,
  ImportPreviewOptions,
  ImportPreviewResult,
  LicenseExchangeResponse,
  LocalCreditState,
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
  decrementCredit,
  deviceInfo,
  hasOfflineExecutionEntitlement,
  loadLocalLicense,
  normalizeText,
  observeTrustedTime,
  readCreditState,
  runtimeEnv,
  sha256Hex,
  stableHash,
  stateNeedsRefresh,
  trustedNowEpoch,
  writeCreditState,
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
  private readonly mode: RuntimeMode;
  private readonly apiKey?: string;
  private readonly enforceLimits: boolean;
  private readonly baseUrl?: string;
  private readonly clientInstance?: DecisionEngineClient;
  private readonly clientConfig: DecisionEngineClientConfig;
  private readonly localSources = new Map<string, LocalSource>();
  private readonly apiRegistrationsByName = new Map<string, SourceRegistrationResponse>();
  private readonly apiRegistrationsByDataset = new Map<string, SourceRegistrationResponse>();
  private readonly capabilityAdapters = new Map<string, CapabilityAdapter>();
  private readonly localCapabilityBindings = new Map<string, CapabilityBindingResponse>();
  private readonly localCapabilityCatalog = new Map<string, CapabilityCatalogEntry>();
  private readonly localCapabilityAuthSessions = new Map<
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
  private readonly localCapabilityOutcomes: CapabilityOutcomeRecord[] = [];
  private lazyClient?: DecisionEngineClient;
  private localLicense?: LocalRuntimeLicense;
  private licensePromise?: Promise<LocalRuntimeLicense>;
  private creditRefreshPromise?: Promise<void>;

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

  private usesApiTransport(): boolean {
    return this.mode === "api" || this.mode === "self_hosted";
  }

  private requireApiTransport(methodName: string): void {
    if (this.usesApiTransport()) {
      return;
    }
    throw new RuntimeConfigurationError(
      "local_mode_not_supported",
      `${methodName}() is not supported for Runtime({ mode: 'local' }). Use Runtime({ mode: 'api', apiKey: '...' }) or Runtime({ mode: 'self_hosted', baseUrl: '...' }).`,
    );
  }

  private nowIso(): string {
    return new Date().toISOString();
  }

  private dedupeCapabilityStrings(values: Array<string | undefined | null>): string[] {
    const ordered: string[] = [];
    const seen = new Set<string>();
    for (const value of values) {
      if (typeof value !== "string") continue;
      const normalized = value.trim();
      if (!normalized || seen.has(normalized)) continue;
      seen.add(normalized);
      ordered.push(normalized);
    }
    return ordered;
  }

  private inferLocalProviderType(
    kind: CapabilityCatalogEntry["kind"],
  ): CapabilityProviderResponse["provider_type"] {
    switch (kind) {
      case "dataset":
        return "data_connector";
      case "mcp_tool":
      case "mcp_resource":
      case "mcp_prompt":
        return "mcp_provider";
      case "skill":
        return "skill_pack";
      case "native_tool":
        return "native_tool_pack";
      case "runtime_library":
      default:
        return "runtime_library_pack";
    }
  }

  private localBindingIdForDescriptor(descriptor: CapabilityAdapterDescriptor): string {
    if (descriptor.binding_id?.trim()) return descriptor.binding_id.trim();
    const seed = JSON.stringify({
      capability_id: descriptor.capability_id,
      provider_id: descriptor.provider_id,
      name: descriptor.name,
      kind: descriptor.kind,
    });
    return `local-binding-${sha256Hex(seed).slice(0, 24)}`;
  }

  private localProfileIdForDescriptor(descriptor: CapabilityAdapterDescriptor): string {
    if (descriptor.profile_id?.trim()) return descriptor.profile_id.trim();
    const providerType = this.inferLocalProviderType(descriptor.kind);
    return `profile.${providerType}.local`;
  }

  private ensureLocalBindingFromAdapter(adapter: CapabilityAdapter): CapabilityBindingResponse {
    const descriptor = adapter.descriptor;
    const bindingId = this.localBindingIdForDescriptor(descriptor);
    const existing = this.localCapabilityBindings.get(bindingId);
    if (existing) {
      return existing;
    }
    const now = this.nowIso();
    const binding: CapabilityBindingResponse = {
      binding_id: bindingId,
      provider_id: descriptor.provider_id,
      profile_id: this.localProfileIdForDescriptor(descriptor),
      binding_name: descriptor.binding_name ?? descriptor.name,
      scope: "workspace",
      scope_ref: "local",
      status: "ready",
      execution_owner: descriptor.execution_owner ?? "client_managed",
      config: null,
      customer_metadata: descriptor.customer_metadata ?? null,
      system_managed: false,
      last_tested_at: now,
      last_discovered_at: now,
      authorized_at: null,
      quarantine_reason: null,
      discovery_error_message: null,
      test_error_message: null,
      created_at: now,
      updated_at: now,
    };
    this.localCapabilityBindings.set(binding.binding_id, binding);
    return binding;
  }

  private capabilityEntryFromAdapter(adapter: CapabilityAdapter): CapabilityCatalogEntry {
    const descriptor = adapter.descriptor;
    const binding = this.ensureLocalBindingFromAdapter(adapter);
    const manifestHash = sha256Hex(JSON.stringify(descriptor));
    return {
      capability_id: descriptor.capability_id,
      provider_id: descriptor.provider_id,
      profile_id: binding.profile_id,
      binding_id: binding.binding_id,
      kind: descriptor.kind,
      name: descriptor.name,
      description: descriptor.description ?? null,
      implementation_kind: descriptor.implementation_kind ?? "callable",
      execution_owner: descriptor.execution_owner ?? "client_managed",
      input_schema_ref:
        descriptor.input_schema_ref ?? `capability://${descriptor.capability_id}/input`,
      output_schema_ref:
        descriptor.output_schema_ref ?? `capability://${descriptor.capability_id}/output`,
      side_effect_class: descriptor.side_effect_class ?? "read_only",
      risk_level: descriptor.risk_level ?? "low",
      required_policy: descriptor.required_policy ?? "policy.capability.execute",
      replayability: descriptor.replayability ?? "deterministic",
      approval_required: descriptor.approval_required ?? false,
      trust_tier: descriptor.trust_tier ?? "customer_managed",
      manifest_hash: manifestHash,
      artifact_affinities: this.dedupeCapabilityStrings(descriptor.artifact_affinities ?? []),
      tags: this.dedupeCapabilityStrings(descriptor.tags ?? []),
      required_binding_ids: [binding.binding_id],
      selected_tool_name: descriptor.selected_tool_name ?? null,
      instruction_artifact_ref: descriptor.instruction_artifact_ref ?? null,
      binding_status: binding.status,
      discovered_at: binding.last_discovered_at ?? binding.created_at,
      customer_metadata: descriptor.customer_metadata ?? null,
      instruction_text: descriptor.instruction_text ?? null,
    };
  }

  registerCapabilityAdapter(adapter: CapabilityAdapter): void {
    const entry = this.capabilityEntryFromAdapter(adapter);
    this.capabilityAdapters.set(entry.capability_id, adapter);
    this.localCapabilityCatalog.set(entry.capability_id, entry);
  }

  private localBindingsArray(): CapabilityBindingResponse[] {
    return Array.from(this.localCapabilityBindings.values()).sort((left, right) =>
      left.binding_name.localeCompare(right.binding_name),
    );
  }

  private localCapabilitiesArray(): CapabilityCatalogEntry[] {
    return Array.from(this.localCapabilityCatalog.values()).sort((left, right) =>
      left.name.localeCompare(right.name),
    );
  }

  private localCapabilityEntryFromManifest(
    payload: Record<string, unknown>,
    binding: CapabilityBindingResponse,
  ): CapabilityCatalogEntry {
    const capabilityId = String(payload.capability_id ?? "").trim();
    if (!capabilityId) {
      throw new RuntimeValidationError(
        "invalid_capability_manifest",
        "Local capability manifests require capability_id.",
      );
    }
    const kind = String(payload.kind ?? "").trim() as CapabilityCatalogEntry["kind"];
    if (!kind) {
      throw new RuntimeValidationError(
        "invalid_capability_manifest",
        "Local capability manifests require kind.",
      );
    }
    const manifestHash = sha256Hex(JSON.stringify(payload));
    const instructionText =
      typeof payload.instruction === "string" && payload.instruction.trim()
        ? payload.instruction
        : null;
    return {
      capability_id: capabilityId,
      provider_id: binding.provider_id,
      profile_id: binding.profile_id,
      binding_id: binding.binding_id,
      kind,
      name: String(payload.name ?? capabilityId),
      description: typeof payload.description === "string" ? payload.description : null,
      implementation_kind:
        (String(payload.implementation_kind ?? "callable") as CapabilityCatalogEntry["implementation_kind"]),
      execution_owner:
        (String(payload.execution_owner ?? binding.execution_owner) as CapabilityCatalogEntry["execution_owner"]),
      input_schema_ref: String(
        payload.input_schema_ref ?? `capability://${capabilityId}/input`,
      ),
      output_schema_ref: String(
        payload.output_schema_ref ?? `capability://${capabilityId}/output`,
      ),
      side_effect_class:
        (String(payload.side_effect_class ?? "read_only") as CapabilityCatalogEntry["side_effect_class"]),
      risk_level: (String(payload.risk_level ?? "low") as CapabilityCatalogEntry["risk_level"]),
      required_policy: String(payload.required_policy ?? "policy.capability.execute"),
      replayability:
        (String(payload.replayability ?? "deterministic") as CapabilityCatalogEntry["replayability"]),
      approval_required: Boolean(payload.approval_required ?? false),
      trust_tier: String(payload.trust_tier ?? "customer_managed"),
      manifest_hash: manifestHash,
      artifact_affinities: this.dedupeCapabilityStrings(
        Array.isArray(payload.artifact_affinities)
          ? (payload.artifact_affinities as Array<string | undefined | null>)
          : [],
      ),
      tags: this.dedupeCapabilityStrings(
        Array.isArray(payload.tags) ? (payload.tags as Array<string | undefined | null>) : [],
      ),
      required_binding_ids: [binding.binding_id],
      selected_tool_name:
        typeof payload.selected_tool_name === "string" ? payload.selected_tool_name : null,
      instruction_artifact_ref:
        typeof payload.instruction_artifact_ref === "string"
          ? payload.instruction_artifact_ref
          : instructionText
            ? `artifact://local-capability/${manifestHash}/${capabilityId}`
            : null,
      binding_status: binding.status,
      discovered_at: this.nowIso(),
      customer_metadata:
        payload.customer_metadata && typeof payload.customer_metadata === "object" && !Array.isArray(payload.customer_metadata)
          ? (payload.customer_metadata as Record<string, unknown>)
          : null,
      instruction_text: instructionText,
    };
  }

  private discoverLocalBinding(
    binding:
      | CapabilityBindingResponse
      | (CapabilityBindingPreviewRequest & {
          binding_id?: string;
          binding_name?: string;
          status?: BindingStatus;
        }),
  ): CapabilityDiscoverResponse {
    const manifest =
      binding.config && typeof binding.config === "object" && !Array.isArray(binding.config)
        ? (binding.config as Record<string, unknown>).manifest
        : null;
    const bindingId =
      "binding_id" in binding && typeof binding.binding_id === "string"
        ? binding.binding_id
        : null;
    const bindingName =
      "binding_name" in binding && typeof binding.binding_name === "string"
        ? binding.binding_name
        : "preview";
    const bindingStatus =
      "status" in binding && binding.status ? binding.status : ("ready" as BindingStatus);
    const discoveredAt = this.nowIso();

    if (manifest && typeof manifest === "object" && !Array.isArray(manifest)) {
      const rawCapabilities = Array.isArray((manifest as { capabilities?: unknown }).capabilities)
        ? ((manifest as { capabilities: unknown[] }).capabilities as unknown[])
        : [];
      const normalizedBinding: CapabilityBindingResponse = {
        binding_id: bindingId ?? `preview-${sha256Hex(JSON.stringify(binding)).slice(0, 12)}`,
        provider_id: binding.provider_id,
        profile_id: binding.profile_id,
        binding_name: bindingName,
        scope: ("scope" in binding && binding.scope ? binding.scope : "workspace") as BindingScope,
        scope_ref:
          ("scope_ref" in binding && typeof binding.scope_ref === "string"
            ? binding.scope_ref
            : "local"),
        status: bindingStatus,
        execution_owner:
          ("execution_owner" in binding && binding.execution_owner
            ? binding.execution_owner
            : "client_managed") as ExecutionOwner,
        config: binding.config ?? null,
        customer_metadata:
          ("customer_metadata" in binding ? binding.customer_metadata ?? null : null) as
            | Record<string, unknown>
            | null,
        system_managed: false,
        last_tested_at: discoveredAt,
        last_discovered_at: discoveredAt,
        authorized_at: null,
        quarantine_reason: null,
        discovery_error_message: null,
        test_error_message: null,
        created_at: discoveredAt,
        updated_at: discoveredAt,
      };
      const capabilities = rawCapabilities
        .filter(item => item && typeof item === "object" && !Array.isArray(item))
        .map(item =>
          this.localCapabilityEntryFromManifest(item as Record<string, unknown>, normalizedBinding),
        );
      const manifestHash = sha256Hex(JSON.stringify(rawCapabilities));
      return {
        binding_id: bindingId,
        provider_id: binding.provider_id,
        profile_id: binding.profile_id,
        snapshot_id: null,
        binding_status: capabilities.length > 0 ? "ready" : "degraded",
        manifest_hash: manifestHash,
        capability_count: capabilities.length,
        discovered_at: discoveredAt,
        message: `Discovered ${capabilities.length} local manifest-backed capabilities.`,
        capabilities,
      };
    }

    const capabilities = this.localCapabilitiesArray().filter(
      entry =>
        entry.binding_id === bindingId ||
        (!bindingId &&
          entry.provider_id === binding.provider_id &&
          entry.profile_id === binding.profile_id),
    );
    const manifestHash = sha256Hex(
      JSON.stringify(capabilities.map(item => item.capability_id)),
    );
    return {
      binding_id: bindingId,
      provider_id: binding.provider_id,
      profile_id: binding.profile_id,
      snapshot_id: null,
      binding_status: capabilities.length > 0 ? "ready" : "degraded",
      manifest_hash: manifestHash,
      capability_count: capabilities.length,
      discovered_at: discoveredAt,
      message: `Discovered ${capabilities.length} local adapter-backed capabilities.`,
      capabilities,
    };
  }

  private localProviderResponses(): CapabilityProviderResponse[] {
    const providers = new Map<string, CapabilityProviderResponse>();
    for (const binding of this.localBindingsArray()) {
      const sampleCapability = this.localCapabilitiesArray().find(
        entry => entry.binding_id === binding.binding_id,
      );
      const providerType = sampleCapability
        ? this.inferLocalProviderType(sampleCapability.kind)
        : "native_tool_pack";
      const existing = providers.get(binding.provider_id);
      const profile = {
        profile_id: binding.profile_id,
        provider_id: binding.provider_id,
        name: binding.binding_name,
        description: null,
        auth_kind: "none",
        default_execution_owner: binding.execution_owner,
        binding_scope_default: binding.scope,
        supported_binding_scopes: [binding.scope],
        profile_metadata: null,
      };
      if (existing) {
        if (!existing.profiles.some(item => item.profile_id === profile.profile_id)) {
          existing.profiles.push(profile);
        }
        continue;
      }
      providers.set(binding.provider_id, {
        provider_id: binding.provider_id,
        provider_type: providerType,
        name: binding.provider_id,
        description: "Local capability-plane provider",
        docs_url: null,
        auth_schema: { type: "none", fields: [] },
        certification_summary: { owner: "customer", certified: false },
        policy_summary: { route_authority: "capability_plane", execution_owner: "client_managed" },
        supported_execution_owners: [binding.execution_owner],
        install_metadata: { discovery_mode: "local_adapter" },
        customer_metadata: null,
        active: true,
        profiles: [profile],
      });
    }
    return Array.from(providers.values()).sort((left, right) =>
      left.provider_id.localeCompare(right.provider_id),
    );
  }

  private sourceRegistrationFromDatasetConnect(
    registration: DatasetConnectResult,
    datasetName: string,
  ): SourceRegistrationResponse {
    return {
      status: registration.status,
      source_id:
        typeof registration.source_id === "string" && registration.source_id.trim()
          ? registration.source_id.trim()
          : typeof registration.dataset_id === "string" && registration.dataset_id.trim()
            ? registration.dataset_id.trim()
            : null,
      dataset_id:
        typeof registration.dataset_id === "string" && registration.dataset_id.trim()
          ? registration.dataset_id.trim()
          : typeof registration.source_id === "string" && registration.source_id.trim()
            ? registration.source_id.trim()
            : null,
      name:
        typeof registration.dataset_name === "string" && registration.dataset_name.trim()
          ? registration.dataset_name.trim()
          : datasetName,
      dataset_name:
        typeof registration.dataset_name === "string" && registration.dataset_name.trim()
          ? registration.dataset_name.trim()
          : datasetName,
      schema: registration.schema ?? null,
      source_schema: registration.schema ?? null,
      latency_ms: registration.latency_ms ?? null,
      connection_id: registration.connection_id ?? null,
      connection_type: registration.connection_type ?? null,
      provider: registration.provider ?? null,
      selection: registration.selection ?? null,
      visibility: registration.visibility ?? null,
      row_count: null,
    };
  }

  private async connectWithManagedConnector(
    options: RuntimeConnectOptions,
  ): Promise<SourceRegistrationResponse> {
    this.requireApiTransport("connect");
    const hasInlineConnector = Boolean(options.connector);
    if (hasInlineConnector && !options.persist) {
      throw new RuntimeValidationError(
        "connector_persistence_required",
        "connect(connector=...) requires persist=true. Use testConnector() or browseConnector() for inline preview flows.",
      );
    }
    const datasetName = (options.datasetName ?? options.name ?? "").trim();
    if (!datasetName) {
      throw new RuntimeValidationError(
        "missing_dataset_name",
        "connect() requires datasetName or name when onboarding a connector-backed dataset.",
      );
    }
    const result = await this.client().connectData({
      dataset_name: datasetName,
      description: options.description,
      selection: options.selection,
      visibility: options.visibility,
      connection_name: options.connectionName,
      ...(options.connectorId ? { connection_id: options.connectorId } : {}),
      ...(options.connector ? { connector: options.connector } : {}),
    });
    if (result.status !== "ready") {
      const errorCode = result.status === "needs_selection" ? "selection_required" : `connect_${result.status}`;
      throw new RuntimeValidationError(
        errorCode,
        result.message ?? "Connector-backed dataset connection did not complete.",
        {
          status: result.status,
          choices: result.choices ?? [],
          labels: result.labels ?? {},
          discovery: result.discovery ?? {},
          connection_id: result.connection_id ?? null,
        },
      );
    }
    const registration = this.sourceRegistrationFromDatasetConnect(result, datasetName);
    const hydrated = await this.hydrateApiRegistration(registration);
    this.rememberApiRegistration(hydrated);
    return hydrated;
  }

  private normalizePreviewConnectorPayload(
    connector: Record<string, unknown>,
  ): { connector_type: string; config?: Record<string, unknown> } {
    const normalized = isCanonicalConnectorEnvelope(connector)
      ? flattenConnectorEnvelope(connector)
      : stripUndefined({ ...connector });
    const connectorType = String(
      normalized.type ?? normalized.connector_type ?? normalized.provider ?? "",
    )
      .trim()
      .toLowerCase()
      .replace(/-/g, "_");
    if (!connectorType) {
      throw new RuntimeValidationError(
        "invalid_connector",
        "Connector previews require an explicit connector type.",
        { field: "type" },
      );
    }
    const config = stripUndefined(
      Object.fromEntries(
        Object.entries(normalized).filter(([key]) => !["type", "connector_type", "provider"].includes(key)),
      ),
    );
    return Object.keys(config).length > 0
      ? { connector_type: connectorType, config }
      : { connector_type: connectorType };
  }

  async connect(
    source?: string | LocalRecord[] | LocalRecord | Record<string, unknown> | null,
    options: RuntimeConnectOptions = {},
  ): Promise<SourceRegistrationResponse> {
    const startMs = Date.now();
    if (options.connectorId || options.connector) {
      return this.connectWithManagedConnector(options);
    }
    if (this.usesApiTransport()) {
      if (!source || typeof source !== "object" || Array.isArray(source)) {
        throw new RuntimeValidationError(
          "api_connect_requires_source_descriptor",
          "API and self_hosted mode connect() expect a structured source descriptor.",
          { expected: "object", received: source === null ? "null" : Array.isArray(source) ? "array" : typeof source },
        );
      }
      const registration = await this.client().registerSource(normalizeApiSourcePayload(source, options.name), {
        description: options.description,
      });
      const hydrated = await this.hydrateApiRegistration(registration);
      this.rememberApiRegistration(hydrated);
      return hydrated;
    }

    if (source === null || source === undefined) {
      throw new RuntimeValidationError(
        "source_required",
        "Local Runtime.connect() requires a local source path, records array, or structured local descriptor.",
      );
    }

    const records = await coerceRecords(source);
    if (records.length === 0) {
      throw new RuntimeValidationError("empty_source", "Connected source is empty and cannot be queried.", {
        name: options.name ?? localSourceName(source, this.localSources.size),
      });
    }

    const name = options.name ?? localSourceName(source, this.localSources.size);
    const fields = orderedFields(records);
    const datasetId = stableHash({ name, fields }).slice(0, 24);
    const schemaRevision = stableHash({ datasetId, fields });
    this.localSources.set(name, {
      name,
      records,
      fields,
      schemaRevision,
      datasetId,
    });

    return {
      source_id: datasetId,
      dataset_id: datasetId,
      name,
      status: "ready",
      ingest_mode: "local",
      schema: { fields },
      source_schema: { fields },
      planner_cache_hit: false,
      planner_schema_revision: schemaRevision,
      planner_prewarm_ms: 0,
      latency_ms: roundLatency(startMs),
      row_count: records.length,
    };
  }

  registerSource(
    source: string | LocalRecord[] | LocalRecord | Record<string, unknown>,
    options: { name?: string; description?: string } = {},
  ): Promise<SourceRegistrationResponse> {
    return this.connect(source, options);
  }

  async connectMany(
    sources: Array<string | LocalRecord[] | LocalRecord | Record<string, unknown>>,
    options: { names?: Array<string | undefined>; description?: string } = {},
  ): Promise<SourceRegistrationResponse[]> {
    if (options.names && options.names.length !== sources.length) {
      throw new RuntimeValidationError(
        "invalid_names_length",
        "connectMany() names must match the number of sources.",
        { sources: sources.length, names: options.names.length },
      );
    }
    const registrations: SourceRegistrationResponse[] = [];
    for (const [index, source] of sources.entries()) {
      registrations.push(
        await this.connect(source, {
          name: options.names?.[index],
          description: options.description,
        }),
      );
    }
    return registrations;
  }

  async createConnector(request: {
    name: string;
    connectorType: string;
    config?: Record<string, unknown>;
    description?: string;
    visibility?: string;
  }): Promise<ConnectorInfo> {
    this.requireApiTransport("createConnector");
    return this.client().createConnector({
      name: request.name,
      connector_type: request.connectorType,
      config: request.config,
      description: request.description,
      visibility: request.visibility,
    });
  }

  async listConnectors(options: { page?: number; limit?: number } = {}): Promise<ConnectorListResult> {
    this.requireApiTransport("listConnectors");
    return this.client().listConnectors(options);
  }

  async getConnector(connectorId: string): Promise<ConnectorInfo> {
    this.requireApiTransport("getConnector");
    return this.client().getConnector(connectorId);
  }

  async updateConnector(
    connectorId: string,
    request: {
      name?: string;
      description?: string;
      visibility?: string;
      config?: Record<string, unknown>;
    },
  ): Promise<ConnectorInfo> {
    this.requireApiTransport("updateConnector");
    return this.client().updateConnector(connectorId, {
      name: request.name,
      description: request.description,
      visibility: request.visibility,
      config: request.config,
    });
  }

  async testConnector(connectorIdOrConnector: string | Record<string, unknown>): Promise<ConnectorTestInfo> {
    this.requireApiTransport("testConnector");
    if (typeof connectorIdOrConnector === "string") {
      return this.client().testConnector(connectorIdOrConnector);
    }
    return this.client().previewTestConnector(this.normalizePreviewConnectorPayload(connectorIdOrConnector));
  }

  async browseConnector(connectorIdOrConnector: string | Record<string, unknown>): Promise<ConnectorBrowseResult> {
    this.requireApiTransport("browseConnector");
    if (typeof connectorIdOrConnector === "string") {
      return this.client().browseConnector(connectorIdOrConnector);
    }
    return this.client().previewBrowseConnector(this.normalizePreviewConnectorPayload(connectorIdOrConnector));
  }

  async deleteConnector(connectorId: string): Promise<void> {
    this.requireApiTransport("deleteConnector");
    await this.client().deleteConnector(connectorId);
  }

  async createRepositorySnapshot(
    repositoryId: string,
    request: RepositorySnapshotCreateRequest,
  ): Promise<RepositorySnapshotResponse> {
    this.requireApiTransport("createRepositorySnapshot");
    return this.client().createRepositorySnapshot(repositoryId, request);
  }

  async getRepositoryIntelligenceCapabilities(): Promise<RepositoryIntelligenceCapabilitiesResponse> {
    this.requireApiTransport("getRepositoryIntelligenceCapabilities");
    return this.client().getRepositoryIntelligenceCapabilities();
  }

  async getRepositorySnapshot(
    repositoryId: string,
    snapshotId: string,
  ): Promise<RepositorySnapshotResponse> {
    this.requireApiTransport("getRepositorySnapshot");
    return this.client().getRepositorySnapshot(repositoryId, snapshotId);
  }

  async triageRepository(
    repositoryId: string,
    request: RepositoryTriageRequest,
  ): Promise<RepositoryTriageResponse> {
    this.requireApiTransport("triageRepository");
    return this.client().triageRepository(repositoryId, request);
  }

  async createRepositoryDecisionPlan(
    repositoryId: string,
    request: RepositoryDecisionPlanCreateRequest,
  ): Promise<RepositoryDecisionPlanRevisionResponse> {
    this.requireApiTransport("createRepositoryDecisionPlan");
    return this.client().createRepositoryDecisionPlan(repositoryId, request);
  }

  async queryRepositoryGraph(
    repositoryId: string,
    request: RepositoryGraphQueryRequest,
  ): Promise<RepositoryGraphQueryResponse> {
    this.requireApiTransport("queryRepositoryGraph");
    return this.client().queryRepositoryGraph(repositoryId, request);
  }

  async simulateRepository(
    repositoryId: string,
    request: RepositorySimulationRequest,
  ): Promise<DecisionEnvelope> {
    this.requireApiTransport("simulateRepository");
    return this.client().simulateRepository(repositoryId, request);
  }

  async applyRepository(
    repositoryId: string,
    request: RepositoryApplyRequest,
  ): Promise<RepositoryApplyResponse> {
    this.requireApiTransport("applyRepository");
    return this.client().applyRepository(repositoryId, request);
  }

  async listDatasets(options: {
    page?: number;
    limit?: number;
    search?: string;
    status?: string;
    sourceName?: string;
    compact?: boolean;
  } = {}): Promise<DatasetListResult> {
    this.requireApiTransport("listDatasets");
    return this.client().listDatasets(options);
  }

  async getDataset(datasetId: string): Promise<DatasetDetailResult> {
    this.requireApiTransport("getDataset");
    return this.client().getDataset(datasetId);
  }

  async getDatasetSummary(datasetId: string): Promise<DatasetSummaryResult> {
    this.requireApiTransport("getDatasetSummary");
    return this.client().getDatasetSummary(datasetId);
  }

  async getContract(): Promise<PlatformContractResponse> {
    this.requireApiTransport("getContract");
    return this.requestValidatedContractPayload(
      "getContract",
      () => this.client().getContract(),
      assertPlatformContractResponse,
    );
  }

  async listCapabilityProviders(): Promise<CapabilityProviderResponse[]> {
    if (this.usesApiTransport()) {
      return this.client().listCapabilityProviders();
    }
    return this.localProviderResponses();
  }

  async getCapabilityProvider(providerId: string): Promise<CapabilityProviderResponse> {
    if (this.usesApiTransport()) {
      return this.client().getCapabilityProvider(providerId);
    }
    const provider = this.localProviderResponses().find(item => item.provider_id === providerId);
    if (!provider) {
      throw new RuntimeValidationError(
        "provider_not_found",
        `Capability provider '${providerId}' was not found in local mode.`,
      );
    }
    return provider;
  }

  async listCapabilityBindings(
    options: { providerId?: string; scope?: string } = {},
  ): Promise<CapabilityBindingResponse[]> {
    if (this.usesApiTransport()) {
      return this.client().listCapabilityBindings(options);
    }
    return this.localBindingsArray().filter(binding => {
      if (options.providerId && binding.provider_id !== options.providerId) return false;
      if (options.scope && binding.scope !== options.scope) return false;
      return true;
    });
  }

  async createCapabilityBinding(
    request: CapabilityBindingCreateRequest,
  ): Promise<CapabilityBindingResponse> {
    if (this.usesApiTransport()) {
      return this.client().createCapabilityBinding(request);
    }
    const now = this.nowIso();
    const bindingId = `local-binding-${sha256Hex(
      JSON.stringify({ request, now }).slice(0, 2048),
    ).slice(0, 24)}`;
    const binding: CapabilityBindingResponse = {
      binding_id: bindingId,
      provider_id: request.provider_id,
      profile_id: request.profile_id,
      binding_name: request.binding_name,
      scope: request.scope ?? "workspace",
      scope_ref: request.scope_ref ?? "local",
      status: "unconfigured",
      execution_owner: request.execution_owner ?? "client_managed",
      config: request.config ?? null,
      customer_metadata: request.customer_metadata ?? null,
      system_managed: false,
      last_tested_at: null,
      last_discovered_at: null,
      authorized_at: null,
      quarantine_reason: null,
      discovery_error_message: null,
      test_error_message: null,
      created_at: now,
      updated_at: now,
    };
    this.localCapabilityBindings.set(bindingId, binding);
    return binding;
  }

  async getCapabilityBinding(bindingId: string): Promise<CapabilityBindingResponse> {
    if (this.usesApiTransport()) {
      return this.client().getCapabilityBinding(bindingId);
    }
    const binding = this.localCapabilityBindings.get(bindingId);
    if (!binding) {
      throw new RuntimeValidationError(
        "binding_not_found",
        `Capability binding '${bindingId}' was not found in local mode.`,
      );
    }
    return binding;
  }

  async updateCapabilityBinding(
    bindingId: string,
    request: CapabilityBindingUpdateRequest,
  ): Promise<CapabilityBindingResponse> {
    if (this.usesApiTransport()) {
      return this.client().updateCapabilityBinding(bindingId, request);
    }
    const binding = await this.getCapabilityBinding(bindingId);
    const updated: CapabilityBindingResponse = {
      ...binding,
      binding_name: request.binding_name ?? binding.binding_name,
      scope: request.scope ?? binding.scope,
      scope_ref: request.scope_ref ?? binding.scope_ref,
      status: request.status ?? binding.status,
      execution_owner: request.execution_owner ?? binding.execution_owner,
      config: request.config ?? binding.config,
      customer_metadata: request.customer_metadata ?? binding.customer_metadata,
      updated_at: this.nowIso(),
    };
    this.localCapabilityBindings.set(bindingId, updated);
    return updated;
  }

  async deleteCapabilityBinding(bindingId: string): Promise<void> {
    if (this.usesApiTransport()) {
      await this.client().deleteCapabilityBinding(bindingId);
      return;
    }
    this.localCapabilityBindings.delete(bindingId);
    Array.from(this.localCapabilityCatalog.values())
      .filter(entry => entry.binding_id === bindingId)
      .forEach(entry => this.localCapabilityCatalog.delete(entry.capability_id));
  }

  async previewTestCapabilityBinding(
    request: CapabilityBindingPreviewRequest,
  ): Promise<CapabilityBindingTestResult> {
    if (this.usesApiTransport()) {
      return this.client().previewTestCapabilityBinding(request);
    }
    const manifest =
      request.config && typeof request.config === "object" && !Array.isArray(request.config)
        ? (request.config as Record<string, unknown>).manifest
        : null;
    if (
      manifest &&
      typeof manifest === "object" &&
      !Array.isArray(manifest) &&
      Array.isArray((manifest as { capabilities?: unknown }).capabilities)
    ) {
      return {
        success: true,
        binding_status: "ready",
        message: "Local manifest-backed capability binding is valid.",
        latency_ms: null,
        details: {
          capability_count: ((manifest as { capabilities: unknown[] }).capabilities ?? []).length,
        },
      };
    }
    const adapterMatch = this.localCapabilitiesArray().some(
      entry => entry.provider_id === request.provider_id && entry.profile_id === request.profile_id,
    );
    return adapterMatch
      ? {
          success: true,
          binding_status: "ready",
          message: "Local adapter-backed capability binding is available.",
          latency_ms: null,
          details: { adapter_backed: true },
        }
      : {
          success: false,
          binding_status: "unconfigured",
          message: "Local capability binding requires config.manifest.capabilities or a matching registered adapter.",
          latency_ms: null,
          details: { required_field: "config.manifest.capabilities" },
        };
  }

  async testCapabilityBinding(bindingId: string): Promise<CapabilityBindingTestResult> {
    if (this.usesApiTransport()) {
      return this.client().testCapabilityBinding(bindingId);
    }
    const binding = await this.getCapabilityBinding(bindingId);
    const result = await this.previewTestCapabilityBinding({
      provider_id: binding.provider_id,
      profile_id: binding.profile_id,
      scope: binding.scope,
      scope_ref: binding.scope_ref,
      execution_owner: binding.execution_owner,
      config: binding.config ?? undefined,
      customer_metadata: binding.customer_metadata ?? undefined,
    });
    this.localCapabilityBindings.set(bindingId, {
      ...binding,
      status: result.binding_status,
      last_tested_at: this.nowIso(),
      test_error_message: result.success ? null : result.message,
      updated_at: this.nowIso(),
    });
    return result;
  }

  async previewDiscoverCapabilityBinding(
    request: CapabilityBindingPreviewRequest,
  ): Promise<CapabilityDiscoverResponse> {
    if (this.usesApiTransport()) {
      return this.client().previewDiscoverCapabilityBinding(request);
    }
    return this.discoverLocalBinding(request);
  }

  async discoverCapabilityBinding(bindingId: string): Promise<CapabilityDiscoverResponse> {
    if (this.usesApiTransport()) {
      return this.client().discoverCapabilityBinding(bindingId);
    }
    const binding = await this.getCapabilityBinding(bindingId);
    const response = this.discoverLocalBinding(binding);
    Array.from(this.localCapabilityCatalog.values())
      .filter(entry => entry.binding_id === bindingId)
      .forEach(entry => this.localCapabilityCatalog.delete(entry.capability_id));
    response.capabilities.forEach(entry => this.localCapabilityCatalog.set(entry.capability_id, entry));
    this.localCapabilityBindings.set(bindingId, {
      ...binding,
      status: response.binding_status,
      last_discovered_at: response.discovered_at,
      discovery_error_message: response.capabilities.length > 0 ? null : response.message,
      updated_at: this.nowIso(),
    });
    return response;
  }

  async startCapabilityAuthorization(
    bindingId: string,
    request: CapabilityAuthorizationStartRequest,
  ): Promise<CapabilityAuthorizationStartResponse> {
    if (this.usesApiTransport()) {
      return this.client().startCapabilityAuthorization(bindingId, request);
    }
    const binding = await this.getCapabilityBinding(bindingId);
    const authorizeUrl =
      binding.config &&
      typeof binding.config === "object" &&
      !Array.isArray(binding.config) &&
      typeof (binding.config as { authorization_url?: unknown }).authorization_url === "string"
        ? String((binding.config as { authorization_url?: unknown }).authorization_url)
        : null;
    if (!authorizeUrl) {
      throw new RuntimeValidationError(
        "authorization_not_supported",
        "This local capability binding does not expose authorization_url.",
      );
    }
    const sessionId = `local-auth-${sha256Hex(
      JSON.stringify({ bindingId, request, now: this.nowIso() }),
    ).slice(0, 24)}`;
    const expiresAt = new Date(Date.now() + 15 * 60 * 1000).toISOString();
    const requestedScopes = request.requested_scopes ?? [];
    const response: CapabilityAuthorizationStartResponse = {
      session_id: sessionId,
      binding_id: bindingId,
      provider_id: binding.provider_id,
      authorize_url: authorizeUrl,
      expires_at: expiresAt,
      requested_scopes: requestedScopes,
    };
    this.localCapabilityAuthSessions.set(sessionId, response);
    this.localCapabilityBindings.set(bindingId, {
      ...binding,
      status: "authorizing",
      updated_at: this.nowIso(),
    });
    return response;
  }

  async completeCapabilityAuthorization(
    bindingId: string,
    request: CapabilityAuthorizationCompleteRequest,
  ): Promise<CapabilityAuthorizationCompleteResponse> {
    if (this.usesApiTransport()) {
      return this.client().completeCapabilityAuthorization(bindingId, request);
    }
    const session = this.localCapabilityAuthSessions.get(request.session_id);
    if (!session || session.binding_id !== bindingId) {
      throw new RuntimeValidationError(
        "authorization_session_not_found",
        "Local capability authorization session was not found.",
      );
    }
    const binding = await this.getCapabilityBinding(bindingId);
    const authorizedAt = this.nowIso();
    this.localCapabilityBindings.set(bindingId, {
      ...binding,
      status: "ready",
      authorized_at: authorizedAt,
      updated_at: authorizedAt,
    });
    return {
      session_id: session.session_id,
      binding_id: bindingId,
      provider_id: binding.provider_id,
      status: "completed",
      authorized_at: authorizedAt,
    };
  }

  async listCapabilities(
    options: {
      kinds?: string[];
      providerIds?: string[];
      bindingIds?: string[];
    } = {},
  ): Promise<CapabilityCatalogEntry[]> {
    if (this.usesApiTransport()) {
      return this.client().listCapabilities(options);
    }
    return this.localCapabilitiesArray().filter(entry => {
      if (options.kinds?.length && !options.kinds.includes(entry.kind)) return false;
      if (options.providerIds?.length && !options.providerIds.includes(entry.provider_id)) return false;
      if (options.bindingIds?.length && !options.bindingIds.includes(entry.binding_id)) return false;
      return true;
    });
  }

  async getCapability(
    capabilityId: string,
    options: { includeInstruction?: boolean } = {},
  ): Promise<CapabilityCatalogEntry> {
    if (this.usesApiTransport()) {
      return this.client().getCapability(capabilityId, options);
    }
    const capability = this.localCapabilityCatalog.get(capabilityId);
    if (!capability) {
      throw new RuntimeValidationError(
        "capability_not_found",
        `Capability '${capabilityId}' was not found in local mode.`,
      );
    }
    if (options.includeInstruction) return capability;
    const { instruction_text, ...rest } = capability;
    return { ...rest, instruction_text: null };
  }

  async routeCapabilities(request: CapabilityRouteRequest): Promise<CapabilityRoutePlan> {
    if (this.usesApiTransport()) {
      return this.client().routeCapabilities(request);
    }
    const tokenize = (value: string): string[] =>
      value
        .toLowerCase()
        .split(/[^a-z0-9_.-]+/g)
        .filter(Boolean);
    const objectiveTokens = new Set(tokenize(request.objective));
    const entries = await this.listCapabilities({
      kinds: request.kinds,
      providerIds: request.provider_ids,
      bindingIds: request.binding_ids,
    });
    const filtered = entries.filter(entry => {
      if (request.execution_owners?.length && !request.execution_owners.includes(entry.execution_owner)) {
        return false;
      }
      return entry.binding_status !== "quarantined";
    });
    if (filtered.length === 0) {
      throw new RuntimeValidationError(
        "capability_route_not_found",
        "No capabilities matched the requested local route filters.",
      );
    }
    const scored = filtered
      .map(entry => {
        const overlap = new Set(
          [
            ...tokenize(entry.name),
            ...tokenize(entry.description ?? ""),
            ...(entry.tags ?? []).flatMap(tokenize),
            ...(entry.artifact_affinities ?? []).flatMap(tokenize),
          ].filter(token => objectiveTokens.has(token)),
        );
        let score = overlap.size * 10 + (entry.binding_status === "ready" ? 15 : 0);
        if ((request.tags ?? []).some(tag => entry.tags.includes(tag))) score += 8;
        if ((request.artifact_affinities ?? []).some(tag => entry.artifact_affinities.includes(tag))) {
          score += 8;
        }
        const confidence = Math.max(0.05, Math.min(0.99, score / 100));
        return {
          entry,
          confidence,
          reason:
            overlap.size > 0
              ? `token overlap: ${Array.from(overlap).sort().join(", ")}`
              : "default local catalog ranking",
        };
      })
      .sort((left, right) => {
        if (right.confidence !== left.confidence) return right.confidence - left.confidence;
        return left.entry.name.localeCompare(right.entry.name);
      });
    const selected = scored[0];
    return {
      selected_capability_id: selected.entry.capability_id,
      selected_provider_id: selected.entry.provider_id,
      selected_binding_id: selected.entry.binding_id,
      kind: selected.entry.kind,
      execution_owner: selected.entry.execution_owner,
      requires_approval: selected.entry.approval_required,
      confidence: Number(selected.confidence.toFixed(4)),
      reason: selected.reason,
      fallbacks: scored.slice(1, 1 + (request.max_fallbacks ?? 3)).map(item => ({
        capability_id: item.entry.capability_id,
        provider_id: item.entry.provider_id,
        binding_id: item.entry.binding_id,
        kind: item.entry.kind,
        execution_owner: item.entry.execution_owner,
        confidence: Number(item.confidence.toFixed(4)),
        reason: item.reason,
        selected_tool_name: item.entry.selected_tool_name ?? null,
        instruction_artifact_ref: item.entry.instruction_artifact_ref ?? null,
      })),
      policy_snapshot_id: "capability-plane-policy-v1",
      selected_tool_name: selected.entry.selected_tool_name ?? null,
      instruction_artifact_ref: selected.entry.instruction_artifact_ref ?? null,
    };
  }

  async executeCapability(
    request: CapabilityExecutionRequest,
  ): Promise<CapabilityExecutionResponse> {
    if (this.usesApiTransport()) {
      return this.client().executeCapability(request);
    }
    const capability = await this.getCapability(request.capability_id, {
      includeInstruction: true,
    });
    if (request.binding_id && request.binding_id !== capability.binding_id) {
      throw new RuntimeValidationError(
        "binding_mismatch",
        "binding_id does not match the selected capability binding.",
      );
    }
    if (capability.execution_owner !== "client_managed") {
      throw new RuntimeValidationError(
        "capability_execution_owner_unsupported",
        "Local runtime execution only supports client_managed capabilities.",
        {
          capability_id: capability.capability_id,
          execution_owner: capability.execution_owner,
        },
      );
    }
    const executionSessionId = `local-exec-${sha256Hex(
      JSON.stringify({ request, ts: this.nowIso() }),
    ).slice(0, 24)}`;
    const startedAt = this.nowIso();
    if (capability.implementation_kind === "instruction_only") {
      return {
        execution_session_id: executionSessionId,
        capability_id: capability.capability_id,
        provider_id: capability.provider_id,
        binding_id: capability.binding_id,
        execution_owner: capability.execution_owner,
        status: "succeeded",
        output: {
          instruction_artifact_ref: capability.instruction_artifact_ref ?? null,
          instruction_text: capability.instruction_text ?? null,
          capability_id: capability.capability_id,
        },
        error: null,
        started_at: startedAt,
        completed_at: this.nowIso(),
      };
    }
    const adapter = this.capabilityAdapters.get(capability.capability_id);
    if (!adapter) {
      throw new RuntimeValidationError(
        "capability_adapter_missing",
        "Local capability execution requires a registered adapter.",
        { capability_id: capability.capability_id },
      );
    }
    const output = (await adapter.execute(request, capability)) ?? null;
    return {
      execution_session_id: executionSessionId,
      capability_id: capability.capability_id,
      provider_id: capability.provider_id,
      binding_id: capability.binding_id,
      execution_owner: capability.execution_owner,
      status: "succeeded",
      output,
      error: null,
      started_at: startedAt,
      completed_at: this.nowIso(),
    };
  }

  async recordCapabilityOutcome(
    request: CapabilityOutcomeRecordRequest,
  ): Promise<CapabilityOutcomeRecord> {
    if (this.usesApiTransport()) {
      return this.client().recordCapabilityOutcome(request);
    }
    const outcome: CapabilityOutcomeRecord = {
      outcome_id: `local-outcome-${sha256Hex(
        JSON.stringify({ request, ts: this.nowIso() }),
      ).slice(0, 24)}`,
      capability_id: request.capability_id,
      provider_id: request.provider_id,
      binding_id: request.binding_id ?? null,
      success: request.success ?? null,
      result_status: request.result_status ?? "reported",
      confidence: request.confidence ?? null,
      latency_ms: request.latency_ms ?? null,
      error_code: request.error_code ?? null,
      details: request.details ?? null,
      created_at: this.nowIso(),
    };
    this.localCapabilityOutcomes.push(outcome);
    return outcome;
  }

  async listSkills(): Promise<CapabilityCatalogEntry[]> {
    if (this.usesApiTransport()) {
      return this.client().listSkills();
    }
    return this.listCapabilities({ kinds: ["skill"] });
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
    if (this.usesApiTransport()) {
      return this.client().enableSkill(request);
    }
    const binding = await this.createCapabilityBinding({
      provider_id: "provider.skill_pack.algenta",
      profile_id: "profile.skill_pack.user",
      binding_name: request.skill_name,
      scope: "user",
      execution_owner: request.execution_owner ?? "client_managed",
      config: {
        manifest: {
          capabilities: [
            {
              capability_id: `cap.skill.${request.skill_name.toLowerCase().replace(/\s+/g, "_")}`,
              name: request.skill_name,
              description: request.description,
              kind: "skill",
              implementation_kind: "instruction_only",
              execution_owner: request.execution_owner ?? "client_managed",
              instruction: request.instruction,
              artifact_affinities: request.artifact_affinities ?? [],
              tags: request.tags ?? [],
              replayability: "deterministic",
            },
          ],
        },
      },
    });
    return this.discoverCapabilityBinding(binding.binding_id);
  }

  async disableSkill(bindingId: string): Promise<void> {
    if (this.usesApiTransport()) {
      await this.client().disableSkill(bindingId);
      return;
    }
    await this.deleteCapabilityBinding(bindingId);
  }

  async listMcpProviders(): Promise<CapabilityProviderResponse[]> {
    if (this.usesApiTransport()) {
      return this.client().listMcpProviders();
    }
    return (await this.listCapabilityProviders()).filter(
      provider => provider.provider_type === "mcp_provider",
    );
  }

  private buildNormalizedContractErrorDetails(error: DecisionEngineError): Record<string, unknown> {
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

  private rethrowNormalizedContractError(
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

  private async requestValidatedContractPayload<T>(
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

  private validateContractPayload<T>(
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

  private validateRuntimeProofPayload<T>(
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

  private async requestValidatedRuntimeProofPayload<T>(
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

  async listModels(): Promise<LLMModelListResponse> {
    this.requireApiTransport("listModels");
    return this.client().listModels();
  }

  async resolveArtifactBridge(
    request: ArtifactBridgeResolveRequest,
  ): Promise<ArtifactBridgeResolveResponse> {
    this.requireApiTransport("resolveArtifactBridge");
    return this.client().resolveArtifactBridge(request);
  }

  async tokenize(request: TokenizeRequest): Promise<TokenizeResponse> {
    this.requireApiTransport("tokenize");
    return this.client().tokenize(request);
  }

  async countTokens(request: CountTokensRequest): Promise<CountTokensResponse> {
    this.requireApiTransport("countTokens");
    return this.client().countTokens(request);
  }

  async chatCompletions(request: ChatCompletionsRequest): Promise<ChatCompletionsResponse> {
    this.requireApiTransport("chatCompletions");
    return this.client().chatCompletions(request);
  }

  async *streamChatCompletions(
    request: ChatCompletionsRequest,
  ): AsyncGenerator<ChatCompletionsStreamChunkResponse> {
    this.requireApiTransport("streamChatCompletions");
    yield* this.client().streamChatCompletions(request);
  }

  async responses(request: ResponsesRequest): Promise<ResponsesResponse> {
    this.requireApiTransport("responses");
    return this.client().responses(request);
  }

  async *streamResponses(
    request: ResponsesRequest,
  ): AsyncGenerator<ResponseStreamEventResponse> {
    this.requireApiTransport("streamResponses");
    yield* this.client().streamResponses(request);
  }

  async embeddings(request: EmbeddingsRequest): Promise<EmbeddingsResponse> {
    this.requireApiTransport("embeddings");
    return this.client().embeddings(request);
  }

  async embeddingSimilarity(
    request: EmbeddingSimilarityRequest,
  ): Promise<EmbeddingSimilarityResponse> {
    this.requireApiTransport("embeddingSimilarity");
    return this.client().embeddingSimilarity(request);
  }

  async rerank(request: RerankRequest): Promise<RerankResponse> {
    this.requireApiTransport("rerank");
    return this.client().rerank(request);
  }

  async planDecision(request: SimulateRequest): Promise<DecisionPlanResponse> {
    this.requireApiTransport("planDecision");
    return this.client().planDecision(request);
  }

  async productDecision(request: ProductDecisionRequest): Promise<ProductDecisionResponse> {
    this.requireApiTransport("productDecision");
    return this.client().productDecision(request);
  }

  async productAgentRun(request: ProductAgentRunRequest): Promise<ProductAgentRunResponse> {
    this.requireApiTransport("productAgentRun");
    return this.client().productAgentRun(request);
  }

  async productOptimize(request: ProductOptimizeRequest): Promise<ProductOptimizeResponse> {
    this.requireApiTransport("productOptimize");
    return this.client().productOptimize(request);
  }

  async productRetrieve(request: ProductRetrieveRequest): Promise<ProductRetrieveResponse> {
    this.requireApiTransport("productRetrieve");
    return this.client().productRetrieve(request);
  }

  async productForecast(request: ProductForecastRequest): Promise<ProductForecastResponse> {
    this.requireApiTransport("productForecast");
    return this.client().productForecast(request);
  }

  async logDecision(request: LogDecisionRequest): Promise<DecisionLogResponse> {
    this.requireApiTransport("logDecision");
    return this.client().logDecision(request);
  }

  async listDecisions(options: {
    page?: number;
    limit?: number;
    page_size?: number;
    with_outcome_only?: boolean;
  } = {}): Promise<DecisionListResponse> {
    this.requireApiTransport("listDecisions");
    return this.client().listDecisions(options);
  }

  async getDecision(decisionId: string): Promise<DecisionLogResponse> {
    this.requireApiTransport("getDecision");
    return this.client().getDecision(decisionId);
  }

  async recordOutcome(
    decisionId: string,
    request: RecordOutcomeRequest,
  ): Promise<DecisionLogResponse> {
    this.requireApiTransport("recordOutcome");
    return this.client().recordOutcome(decisionId, request);
  }

  async executeDecision(
    decisionId: string,
    request: ExecuteDecisionRequest,
  ): Promise<ExecutionReceiptResponse> {
    this.requireApiTransport("executeDecision");
    return this.client().executeDecision(decisionId, request);
  }

  async deleteDecision(decisionId: string): Promise<Record<string, unknown>> {
    this.requireApiTransport("deleteDecision");
    return this.client().deleteDecision(decisionId);
  }

  async createAgentRun(request: AgentRunCreateRequest): Promise<AgentRunResponse> {
    this.requireApiTransport("createAgentRun");
    return this.client().createAgentRun(request);
  }

  async getAgentRun(runId: string): Promise<AgentRunResponse> {
    this.requireApiTransport("getAgentRun");
    return this.client().getAgentRun(runId);
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
    this.requireApiTransport("listAgentRuns");
    return this.client().listAgentRuns(options);
  }

  async getAgentRunEvents(
    runId: string,
    options: { limit?: number } = {},
  ): Promise<AgentRunEventsResponse> {
    this.requireApiTransport("getAgentRunEvents");
    return this.client().getAgentRunEvents(runId, options);
  }

  async *streamAgentRunEvents(
    runId: string,
    options: { limit?: number } = {},
  ): AsyncGenerator<AgentRunStreamEventResponse> {
    this.requireApiTransport("streamAgentRunEvents");
    yield* this.client().streamAgentRunEvents(runId, options);
  }

  async listAgentRunCheckpoints(runId: string): Promise<AgentRunCheckpointsResponse> {
    this.requireApiTransport("listAgentRunCheckpoints");
    return this.client().listAgentRunCheckpoints(runId);
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
    this.requireApiTransport("queryAgentRunCheckpoints");
    return this.client().queryAgentRunCheckpoints(options);
  }

  async listAgentRunMissionEvents(
    runId: string,
    options: { limit?: number } = {},
  ): Promise<AgentRunMissionEventsResponse> {
    this.requireApiTransport("listAgentRunMissionEvents");
    return this.client().listAgentRunMissionEvents(runId, options);
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
    this.requireApiTransport("queryAgentRunMissionEvents");
    return this.client().queryAgentRunMissionEvents(options);
  }

  async replayAgentRun(
    runId: string,
    options: { checkpoint_id?: string | null } = {},
  ): Promise<AgentRunReplayResponse> {
    this.requireApiTransport("replayAgentRun");
    return this.client().replayAgentRun(runId, options);
  }

  async forkAgentRun(
    runId: string,
    options: { checkpoint_id?: string | null } = {},
  ): Promise<AgentRunResponse> {
    this.requireApiTransport("forkAgentRun");
    return this.client().forkAgentRun(runId, options);
  }

  async resumeAgentRun(runId: string): Promise<AgentRunResponse> {
    this.requireApiTransport("resumeAgentRun");
    return this.client().resumeAgentRun(runId);
  }

  async cancelAgentRun(runId: string): Promise<AgentRunResponse> {
    this.requireApiTransport("cancelAgentRun");
    return this.client().cancelAgentRun(runId);
  }

  async approveAgentRun(runId: string): Promise<AgentRunResponse> {
    this.requireApiTransport("approveAgentRun");
    return this.client().approveAgentRun(runId);
  }

  async listAgentRunTelemetry(
    runId: string,
    options: { limit?: number } = {},
  ): Promise<AgentRunTelemetryResponse> {
    this.requireApiTransport("listAgentRunTelemetry");
    return this.client().listAgentRunTelemetry(runId, options);
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
    this.requireApiTransport("queryAgentRunTelemetry");
    return this.client().queryAgentRunTelemetry(options);
  }

  async recommend(
    actions: Array<{ name: string; request: SimulateRequest }>,
    options?: { runs?: number; seed?: number },
  ): Promise<RecommendResponse> {
    this.requireApiTransport("recommend");
    return this.client().recommend(actions, options);
  }

  async score(
    request: SimulateRequest,
    scoringWeights?: Record<string, number>,
  ): Promise<ScoreResponse> {
    this.requireApiTransport("score");
    return this.client().score(request, scoringWeights);
  }

  async batch(items: SimulateRequest[]): Promise<BatchResult> {
    this.requireApiTransport("batch");
    return this.client().batch(items);
  }

  async compare(
    scenarios: Array<{ name: string; request: SimulateRequest }>,
    options?: { runs?: number; seed?: number },
  ): Promise<CompareResponse> {
    this.requireApiTransport("compare");
    return this.client().compare(scenarios, options);
  }

  async listJobs(options: { page?: number; limit?: number; status?: string } = {}): Promise<JobListResponse> {
    this.requireApiTransport("listJobs");
    return this.client().listJobs(options);
  }

  async submitJob(request: SimulateRequest, callbackUrl?: string): Promise<JobSubmitResponse> {
    this.requireApiTransport("submitJob");
    return this.client().submitJob(request, callbackUrl);
  }

  async getJob(jobId: string): Promise<JobStatusResponse> {
    this.requireApiTransport("getJob");
    return this.client().getJob(jobId);
  }

  async getJobResult(jobId: string): Promise<Record<string, unknown>> {
    this.requireApiTransport("getJobResult");
    return this.client().getJobResult(jobId);
  }

  async cancelJob(jobId: string): Promise<JobStatusResponse> {
    this.requireApiTransport("cancelJob");
    return this.client().cancelJob(jobId);
  }

  async testWebhookDelivery(callbackUrl: string): Promise<WebhookTestResponse> {
    this.requireApiTransport("testWebhookDelivery");
    return this.client().testWebhookDelivery(callbackUrl);
  }

  async registerTrigger(request: RegisterTriggerRequest): Promise<TriggerResponse> {
    this.requireApiTransport("registerTrigger");
    return this.client().registerTrigger(request);
  }

  async listTriggers(options: { status?: "active" | "paused" | "all"; page?: number; limit?: number } = {}): Promise<TriggerListResponse> {
    this.requireApiTransport("listTriggers");
    return this.client().listTriggers(options);
  }

  async fireTrigger(triggerId: string, options: { force?: boolean } = {}): Promise<TriggerFireResponse> {
    this.requireApiTransport("fireTrigger");
    return this.client().fireTrigger(triggerId, options);
  }

  async pauseTrigger(triggerId: string, options: { paused?: boolean } = {}): Promise<TriggerPauseResponse> {
    this.requireApiTransport("pauseTrigger");
    return this.client().pauseTrigger(triggerId, options);
  }

  async deleteTrigger(triggerId: string): Promise<TriggerDeleteResponse> {
    this.requireApiTransport("deleteTrigger");
    return this.client().deleteTrigger(triggerId);
  }

  async pollJob(
    jobId: string,
    options: { timeoutMs?: number; pollIntervalMs?: number } = {},
  ): Promise<Record<string, unknown>> {
    this.requireApiTransport("pollJob");
    return this.client().pollJob(jobId, options);
  }

  async listDeploymentRegions(): Promise<DeploymentRegionsResponse> {
    this.requireApiTransport("listDeploymentRegions");
    return this.client().listDeploymentRegions();
  }

  async getDeployment(): Promise<DeploymentResponse | null> {
    this.requireApiTransport("getDeployment");
    return this.client().getDeployment();
  }

  async createDeployment(request: {
    provider?: string;
    region?: string;
    config?: Record<string, unknown> | null;
    billing_markup_pct?: number;
  } = {}): Promise<DeploymentResponse> {
    this.requireApiTransport("createDeployment");
    return this.client().createDeployment(request);
  }

  async deleteDeployment(deploymentId: string): Promise<DeploymentDeleteResponse> {
    this.requireApiTransport("deleteDeployment");
    return this.client().deleteDeployment(deploymentId);
  }

  async getDeploymentCost(deploymentId: string): Promise<DeploymentCostResponse> {
    this.requireApiTransport("getDeploymentCost");
    return this.client().getDeploymentCost(deploymentId);
  }

  async me(): Promise<MeResponse> {
    this.requireApiTransport("me");
    return this.client().me();
  }

  async updateMe(request: UpdateMeRequest): Promise<MeResponse> {
    this.requireApiTransport("updateMe");
    return this.client().updateMe(request);
  }

  async usage(): Promise<UsageInfo> {
    this.requireApiTransport("usage");
    return this.client().usage();
  }

  async limits(): Promise<LimitsInfo> {
    this.requireApiTransport("limits");
    return this.client().limits();
  }

  async distributions(): Promise<DistributionListResponse> {
    this.requireApiTransport("distributions");
    return this.client().distributions();
  }

  async templates(): Promise<TemplateListResponse> {
    this.requireApiTransport("templates");
    return this.client().templates();
  }

  async getBillingInfo(): Promise<BillingInfoResponse> {
    this.requireApiTransport("getBillingInfo");
    return this.client().getBillingInfo();
  }

  async createBillingCheckout(
    options: { plan?: "developer" | "pro" } = {},
  ): Promise<BillingSessionResponse> {
    this.requireApiTransport("createBillingCheckout");
    return this.client().createBillingCheckout(options);
  }

  async createBillingPortal(): Promise<BillingSessionResponse> {
    this.requireApiTransport("createBillingPortal");
    return this.client().createBillingPortal();
  }

  async refreshCredits(request: CreditRefreshRequest): Promise<CreditRefreshResponse> {
    this.requireApiTransport("refreshCredits");
    return this.client().refreshCredits(request);
  }

  async ingestMeteringEvents(request: MeteringBatchRequest): Promise<MeteringBatchResponse> {
    this.requireApiTransport("ingestMeteringEvents");
    return this.client().ingestMeteringEvents(request);
  }

  async listApiKeys(): Promise<APIKeyInfo[]> {
    this.requireApiTransport("listApiKeys");
    return this.client().listApiKeys();
  }

  async createApiKey(request: CreateAPIKeyRequest): Promise<APIKeyCreated> {
    this.requireApiTransport("createApiKey");
    return this.client().createApiKey(request);
  }

  async revokeApiKey(keyId: string): Promise<Record<string, unknown>> {
    this.requireApiTransport("revokeApiKey");
    return this.client().revokeApiKey(keyId);
  }

  async listTeamMembers(options: { page?: number; limit?: number } = {}): Promise<TeamListResponse> {
    this.requireApiTransport("listTeamMembers");
    return this.client().listTeamMembers(options);
  }

  async inviteTeamMember(request: TeamInviteRequest): Promise<TeamInviteResponse> {
    this.requireApiTransport("inviteTeamMember");
    return this.client().inviteTeamMember(request);
  }

  async updateTeamMemberRole(
    userId: string,
    role: "owner" | "admin" | "member" | "viewer",
  ): Promise<TeamRoleUpdateResponse> {
    this.requireApiTransport("updateTeamMemberRole");
    return this.client().updateTeamMemberRole(userId, role);
  }

  async removeTeamMember(userId: string): Promise<TeamRemoveResponse> {
    this.requireApiTransport("removeTeamMember");
    return this.client().removeTeamMember(userId);
  }

  async listDevices(options: { page?: number; limit?: number } = {}): Promise<DeviceListResponse> {
    this.requireApiTransport("listDevices");
    return this.client().listDevices(options);
  }

  async revokeDevice(registrationId: string): Promise<DeviceRevokeResponse> {
    this.requireApiTransport("revokeDevice");
    return this.client().revokeDevice(registrationId);
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
    this.requireApiTransport("getAuditLogs");
    return this.client().getAuditLogs(options);
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
    this.requireApiTransport("getAuditLogArtifacts");
    return this.client().getAuditLogArtifacts(options);
  }

  async getExecutionPolicy(): Promise<ExecutionPolicyResponse> {
    this.requireApiTransport("getExecutionPolicy");
    return this.client().getExecutionPolicy();
  }

  async listExecutionPolicySnapshots(): Promise<ExecutionPolicySnapshotListResponse> {
    this.requireApiTransport("listExecutionPolicySnapshots");
    return this.client().listExecutionPolicySnapshots();
  }

  async updateExecutionPolicy(
    request: UpdateExecutionPolicyRequest,
  ): Promise<ExecutionPolicyResponse> {
    this.requireApiTransport("updateExecutionPolicy");
    return this.client().updateExecutionPolicy(request);
  }

  async refreshDataset(datasetId: string): Promise<DatasetConnectResult> {
    this.requireApiTransport("refreshDataset");
    return this.client().refreshDataset(datasetId);
  }

  async deleteDataset(datasetId: string): Promise<DatasetDeleteResult> {
    this.requireApiTransport("deleteDataset");
    return this.client().deleteDataset(datasetId);
  }

  async importPreview(
    source: string | LocalRecord[] | LocalRecord | Record<string, unknown>,
    options: ImportPreviewOptions = {},
  ): Promise<ImportPreviewResult> {
    const registration = await this.connect(source, options);
    return {
      registration,
      preview: renderSourceImportPreview(registration, {
        sourceRef: sourceReference(source, options.sourceRef),
        mode: this.mode,
        color: options.color,
      }),
    };
  }

  async importBundlePreview(
    sources: Array<string | LocalRecord[] | LocalRecord | Record<string, unknown>>,
    options: ImportBundlePreviewOptions = {},
  ): Promise<ImportBundlePreviewResult> {
    if (options.names && options.names.length !== sources.length) {
      throw new RuntimeValidationError(
        "invalid_names_length",
        "importBundlePreview() names must match the number of sources.",
        { sources: sources.length, names: options.names.length },
      );
    }
    if (options.sourceRefs && options.sourceRefs.length !== sources.length) {
      throw new RuntimeValidationError(
        "invalid_source_refs_length",
        "importBundlePreview() sourceRefs must match the number of sources.",
        { sources: sources.length, sourceRefs: options.sourceRefs.length },
      );
    }

    const registrations: SourceRegistrationResponse[] = [];
    const failures: ImportFailureResult[] = [];
    for (const [index, source] of sources.entries()) {
      try {
        registrations.push(
          await this.connect(source, {
            name: options.names?.[index],
            description: options.description,
          }),
        );
      } catch (error) {
        if (!(error instanceof RuntimeError)) {
          throw error;
        }
        failures.push({
          sourceRef: options.sourceRefs?.[index] ?? sourceReference(source),
          code: error.code,
          message: error.message,
          name: options.names?.[index],
        });
      }
    }

    return {
      registrations,
      failures,
      preview: renderSourceBundlePreview(registrations, failures, {
        mode: this.mode,
        color: options.color,
      }),
    };
  }

  async resolve(
    request: Record<string, unknown> = {},
    overrides: Record<string, unknown> = {},
  ): Promise<ResolveResponse> {
    const merged = mergeRequest(request, overrides);
    if (this.usesApiTransport()) {
      const exact = await this.tryExactApiResolve(merged);
      if (exact) {
        return exact;
      }
      return this.client().resolve(this.coerceApiResolvePayload(merged));
    }
    return this.resolveLocal(merged);
  }

  async query(
    request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
    overrides: Record<string, unknown> = {},
  ): Promise<QueryResponse> {
    if (this.usesApiTransport()) {
      return this.client().query(this.coerceApiQueryPayload(request, overrides));
    }
    return this.queryLocal(request, overrides);
  }

  async queryWithMetadata(
    request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
    overrides: Record<string, unknown> = {},
  ): Promise<QueryWithMetadataResponse> {
    if (this.usesApiTransport()) {
      return this.client().queryWithMetadata(this.coerceApiQueryPayload(request, overrides));
    }
    const data = await this.queryLocal(request, overrides);
    return {
      data,
      metadata: {
        request_id: data.request_id ?? undefined,
        latency_ms: data.latency_ms,
      },
    };
  }

  async verify(
    request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
    overrides: Record<string, unknown> = {},
  ): Promise<VerifyResponse> {
    if (this.usesApiTransport()) {
      return this.client().verify(this.coerceApiQueryPayload(request, overrides));
    }
    return this.verifyLocal(request, overrides);
  }

  async queryBatch(request: {
    defaults?: {
      dataset_id?: string | null;
      filter?: Record<string, unknown> | null;
      limit?: number | null;
      order?: "asc" | "desc" | null;
    } | null;
    queries: Array<{ key: string; request: Record<string, unknown> }>;
  }): Promise<QueryBatchResponse> {
    this.requireApiTransport("queryBatch");
    return this.client().queryBatch(request);
  }

  async querySqlReport(request: QuerySqlReportRequest): Promise<QuerySqlReportResponse> {
    this.requireApiTransport("querySqlReport");
    return this.client().querySqlReport(request);
  }

  private client(): DecisionEngineClient {
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

  private rememberApiRegistration(registration: SourceRegistrationResponse): void {
    if (typeof registration.name === "string" && registration.name.trim()) {
      this.apiRegistrationsByName.set(registration.name.trim(), registration);
    }
    const datasetId = registrationDatasetId(registration);
    if (datasetId) {
      this.apiRegistrationsByDataset.set(datasetId, registration);
    }
  }

  private async hydrateApiRegistration(
    registration: SourceRegistrationResponse,
  ): Promise<SourceRegistrationResponse> {
    const datasetId = registrationDatasetId(registration);
    if (!datasetId) {
      return registration;
    }
    const needsHydration =
      registration.row_count == null ||
      typeof registration.name !== "string" ||
      !registration.name.trim() ||
      typeof registration.dataset_name !== "string" ||
      !registration.dataset_name.trim() ||
      registration.schema == null ||
      registration.source_schema == null;
    if (!needsHydration) {
      return registration;
    }
    const clientWithGetDataset = this.client() as unknown as {
      getDataset?: (datasetId: string) => Promise<DatasetDetailResult>;
    };
    if (typeof clientWithGetDataset.getDataset !== "function") {
      return registration;
    }
    try {
      const detail = await clientWithGetDataset.getDataset(datasetId);
      const dataset = detail?.dataset;
      const schema =
        detail?.schema && typeof detail.schema === "object"
          ? detail.schema
          : null;
      return {
        ...registration,
        name:
          typeof registration.name === "string" && registration.name.trim()
            ? registration.name
            : typeof dataset?.name === "string" && dataset.name.trim()
              ? dataset.name
              : registration.name ?? null,
        dataset_name:
          typeof registration.dataset_name === "string" && registration.dataset_name.trim()
            ? registration.dataset_name
            : typeof dataset?.name === "string" && dataset.name.trim()
              ? dataset.name
              : registration.dataset_name ?? null,
        row_count:
          typeof registration.row_count === "number"
            ? registration.row_count
            : typeof dataset?.row_count === "number"
              ? dataset.row_count
              : registration.row_count ?? null,
        schema: registration.schema ?? schema,
        source_schema: registration.source_schema ?? schema,
      };
    } catch {
      return registration;
    }
  }

  private lookupApiRegistration(request: Record<string, unknown>): SourceRegistrationResponse | null {
    const datasetId = request.dataset_id;
    if (typeof datasetId === "string" && datasetId.trim()) {
      const registration = this.apiRegistrationsByDataset.get(datasetId.trim());
      if (registration) {
        return registration;
      }
    }
    const sourceName = request.source_name;
    if (typeof sourceName === "string" && sourceName.trim()) {
      return this.apiRegistrationsByName.get(sourceName.trim()) ?? null;
    }
    return null;
  }

  private async fetchApiSourceSchemaRevision(
    registration: SourceRegistrationResponse,
  ): Promise<string | null> {
    const sourceId = registrationDatasetId(registration);
    if (!sourceId) {
      return null;
    }
    const clientWithRequest = this.client() as unknown as {
      request?: (method: string, path: string, body?: unknown) => Promise<unknown>;
    };
    if (typeof clientWithRequest.request !== "function") {
      return null;
    }
    try {
      const payload = await clientWithRequest.request("GET", `/v1/sources/${sourceId}`);
      if (!payload || typeof payload !== "object") {
        return null;
      }
      const body = payload as Record<string, unknown>;
      const entry = body.entry;
      if (entry && typeof entry === "object") {
        const entryRecord = entry as Record<string, unknown>;
        const entryRevision = entryRecord.source_schema_revision ?? entryRecord.schema_revision;
        if (typeof entryRevision === "string" && entryRevision.trim()) {
          return entryRevision.trim();
        }
      }
      const schema = body.schema;
      if (schema && typeof schema === "object") {
        const schemaRevision = (schema as Record<string, unknown>).schema_revision;
        if (typeof schemaRevision === "string" && schemaRevision.trim()) {
          return schemaRevision.trim();
        }
      }
      return null;
    } catch {
      return null;
    }
  }

  private async tryExactApiResolve(request: Record<string, unknown>): Promise<ResolveResponse | null> {
    const registration = this.lookupApiRegistration(request);
    if (!registration) {
      return null;
    }
    const resolvedSourceName = registrationResolvedSourceName(registration);
    if (!resolvedSourceName) {
      return null;
    }
    const schemaRevision =
      (await this.fetchApiSourceSchemaRevision(registration)) ??
      (typeof registration.planner_schema_revision === "string" &&
      registration.planner_schema_revision.trim()
        ? registration.planner_schema_revision.trim()
        : typeof registration.schema_revision === "string" && registration.schema_revision.trim()
          ? registration.schema_revision.trim()
          : null);
    if (!schemaRevision) {
      return null;
    }
    const fields = new Set(registrationFields(registration));
    if (fields.size === 0) {
      return null;
    }

    const metricColumn = this.exactResolveMetricField(request, fields);
    if (!metricColumn) {
      return null;
    }
    const groupColumn = this.exactResolveGroupField(request, fields);
    if (groupColumn === undefined) {
      return null;
    }

    const startMs = Date.now();
    const constraints =
      request.constraints && typeof request.constraints === "object"
        ? { ...(request.constraints as Record<string, unknown>) }
        : {};
    const datasetScope = registrationDatasetId(registration);
    if (datasetScope && constraints[RUNTIME_DATASET_SCOPE_KEY] === undefined) {
      constraints[RUNTIME_DATASET_SCOPE_KEY] = datasetScope;
    }
    const resolvedPlan: ResolvedPlan = {
      source_name: resolvedSourceName,
      metric_column: metricColumn,
      aggregation: resolveAggregation(request),
      ...(groupColumn ? { group_column: groupColumn } : {}),
      ...(request.join_path && typeof request.join_path === "object" ? { join_path: request.join_path as Record<string, unknown> } : {}),
      ...(request.filter && typeof request.filter === "object" ? { filter: request.filter as Record<string, unknown> } : {}),
      ...(typeof request.limit === "number" ? { limit: request.limit } : {}),
      order: typeof request.order === "string" ? request.order : "desc",
      constraints,
      schema_revision: schemaRevision,
    };
    const planHash = exactPlanHash(resolvedPlan);
    const signature = intentSignature(resolvedSourceName, request, schemaRevision);

    return {
      resolved_plan: resolvedPlan,
      confidence: 1,
      plan: [
        `Use exact source '${resolvedSourceName}'.`,
        `Use exact metric column '${metricColumn}'.`,
        ...(groupColumn ? [`Group by exact column '${groupColumn}'.`] : []),
      ],
      explanation: [
        `Using registered source '${resolvedSourceName}' as an exact source.`,
        `Using exact metric column '${metricColumn}'.`,
        ...(groupColumn ? [`Using exact group column '${groupColumn}'.`] : []),
      ],
      resolved_column: metricColumn,
      resolved_role: "measure",
      resolved_source: resolvedSourceName,
      candidates: [],
      source_scores: { [resolvedSourceName]: 1 },
      latency_ms: roundLatency(startMs),
      decision_path: "exact_spec",
      plan_hash: planHash,
      schema_revision: schemaRevision,
      validated: true,
      deterministic_scope: "api_registered_source",
      confidence_source: "runtime_exact_spec",
      clarification_required: false,
      rejection_reason: null,
      request_id: `runtime_exact_${signature.slice(0, 12)}`,
      intent_signature: signature,
      source_set: [resolvedSourceName],
      join_path: [],
      planner_mode: "runtime_exact_spec",
    };
  }

  private exactResolveMetricField(
    request: Record<string, unknown>,
    fields: Set<string>,
  ): string | null {
    const metricColumn = request.metric_column;
    if (typeof metricColumn === "string" && fields.has(metricColumn)) {
      return metricColumn;
    }
    const metric = request.metric;
    if (typeof metric === "string" && fields.has(metric)) {
      return metric;
    }
    return null;
  }

  private exactResolveGroupField(
    request: Record<string, unknown>,
    fields: Set<string>,
  ): string | null | undefined {
    const groupColumn = request.group_column;
    if (typeof groupColumn === "string") {
      return fields.has(groupColumn) ? groupColumn : undefined;
    }
    const groupBy = request.group_by;
    if (typeof groupBy === "string") {
      return fields.has(groupBy) ? groupBy : undefined;
    }
    if (Array.isArray(groupBy)) {
      const candidates = groupBy.filter(
        (value): value is string => typeof value === "string" && value.trim().length > 0,
      );
      if (candidates.length > 1) {
        return undefined;
      }
      if (candidates.length === 1) {
        return fields.has(candidates[0]) ? candidates[0] : undefined;
      }
    }
    return null;
  }

  private usesHostedLocalLimits(): boolean {
    return this.mode === "local" && this.enforceLimits && !privateProfile();
  }

  private async ensureLocalExecutionEntitlement(): Promise<void> {
    if (!this.usesHostedLocalLimits() && !requireLocalLicense()) {
      return;
    }
    if (this.usesHostedLocalLimits() && !this.apiKey) {
      throw new RuntimeConfigurationError(
        "api_key_required",
        "Hosted local mode requires an API key. Pass apiKey explicitly when constructing Runtime.",
      );
    }
    if (!this.licensePromise) {
      this.licensePromise = loadLocalLicense(this.apiKey ?? "", this.baseUrl)
        .finally(() => {
          this.licensePromise = undefined;
        });
    }
    this.localLicense = await this.licensePromise;
    if (!this.localLicense.valid) {
      throw new RuntimeConfigurationError(
        "license_required",
        this.localLicense.message || "A valid local device license is required.",
        {
          plan: this.localLicense.plan,
          source: this.localLicense.source,
        },
      );
    }
  }

  private consumeLocalCredit(): void {
    if (!this.usesHostedLocalLimits()) {
      return;
    }
    if (hasOfflineExecutionEntitlement(this.localLicense)) {
      return;
    }
    const outcome = decrementCredit();
    if (!outcome.permitted) {
      throw new RuntimeConfigurationError(
        "quota_exhausted",
        "Local execution credits are exhausted. Refresh credits or renew the device license before continuing.",
      );
    }
    if (outcome.state && stateNeedsRefresh(outcome.state) && !this.creditRefreshPromise) {
      this.creditRefreshPromise = this.refreshLocalCredits(outcome.state)
        .finally(() => {
          this.creditRefreshPromise = undefined;
        });
    }
  }

  private async refreshLocalCredits(state: LocalCreditState): Promise<void> {
    if (!this.apiKey) {
      return;
    }
    let controlPlaneUrl = "";
    try {
      controlPlaneUrl = validatedControlPlaneBaseUrl(this.baseUrl, {
        surface: "credits_refresh",
      });
    } catch {
      return;
    }
    try {
      const response = await fetch(`${controlPlaneUrl}/v1/credits/refresh`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${this.apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          device_id: deviceInfo().device_id,
          billing_period: state.billing_period,
          credits_used: state.credits_total - state.credits_remaining,
        }),
      });
      if (!response.ok) {
        return;
      }
      const data = (await response.json()) as LicenseExchangeResponse;
      observeTrustedTime(
        data.server_time ?? Math.floor(Date.now() / 1000),
        "control-plane-credit-refresh",
      );
      const granted = data.credits_granted ?? 0;
      if (granted <= 0) {
        return;
      }
      const now = trustedNowEpoch();
      const expiresAt = data.credits_expires_at ?? now + CREDIT_TTL_SECONDS;
      const ttlSeconds = Math.max(1, expiresAt - now);
      const existing = readCreditState();
      const carry = existing?.credits_remaining ?? 0;
      writeCreditState({
        credits_remaining: carry + granted,
        credits_total: granted,
        issued_at: now,
        expires_at: now + ttlSeconds,
        billing_period: data.credits_billing_period ?? state.billing_period,
        refresh_after: now + ttlSeconds * 0.9,
      });
    } catch {
      return;
    }
  }

  private selectLocalSource(request: Record<string, unknown>): LocalSource {
    const requested = typeof request.source_name === "string"
      ? request.source_name
      : typeof request.dataset_id === "string"
        ? request.dataset_id
        : null;

    if (requested) {
      if (this.localSources.has(requested)) {
        return this.localSources.get(requested)!;
      }
      for (const source of this.localSources.values()) {
        if (source.datasetId === requested) return source;
      }
      throw new RuntimeValidationError("unknown_source", "Requested source is not connected to this runtime.", {
        requested,
        available: [...this.localSources.keys()].sort(),
      });
    }

    if (this.localSources.size === 1) {
      return [...this.localSources.values()][0];
    }
    if (this.localSources.size === 0) {
      throw new RuntimeConfigurationError(
        "source_required",
        "No local sources are connected. Call Runtime.connect(...) before resolve/query.",
      );
    }
    throw new RuntimeValidationError("source_required", "Multiple local sources are connected. Provide source_name or dataset_id.", {
      available: [...this.localSources.keys()].sort(),
    });
  }

  private rankFields(source: LocalSource, hint: string, numericOnly: boolean): RankedField[] {
    const hintTerms = metricSynonymSet(hint);
    return source.fields
      .filter(field => !numericOnly || isNumericField(field, source.records))
      .map(field => {
        const base = semanticScore(field, hint);
        let score = base.score;
        const reasons = [...base.reasons];
        const normalizedField = normalizeText(field);
        if (hintTerms.has(normalizedField)) {
          score = Math.max(score, 1);
          reasons.push("canonical synonym match");
        }
        if (isExactFieldMatch(field, hint)) {
          score = 1;
        }
        return {
          field,
          score: Number(score.toFixed(4)),
          reasons: reasons.length > 0 ? reasons : ["schema similarity"],
        };
      })
      .sort((left, right) => {
        if (right.score !== left.score) return right.score - left.score;
        return left.field.localeCompare(right.field);
      });
  }

  private buildCandidates(source: LocalSource, ranked: RankedField[], role: string): QueryCandidate[] {
    return ranked.slice(0, 5).map(item => ({
      source: source.name,
      column: item.field,
      role,
      confidence: item.score,
      notes: item.reasons,
      score_components: { schema_similarity: item.score },
    }));
  }

  private resolveLocal(request: Record<string, unknown>): ResolveResponse {
    const startMs = Date.now();
    const source = this.selectLocalSource(request);
    const metricHint = typeof request.metric === "string" ? request.metric : null;
    if (!metricHint) {
      throw new RuntimeValidationError(
        "metric_required",
        "Local Runtime.resolve() requires a structured metric field.",
        { request },
      );
    }

    const aggregation = resolveAggregation(request);
    const metricRanked = this.rankFields(source, metricHint, true);
    if (metricRanked.length === 0) {
      return this.rejectedResolve(source, request, "schema_unresolved", [`No numeric field matched metric '${metricHint}'.`], startMs);
    }

    const metricChoice = metricRanked[0];
    const metricCandidates = this.buildCandidates(source, metricRanked, "measure");
    const metricSecond = metricRanked[1]?.score ?? 0;
    const metricGap = Number((metricChoice.score - metricSecond).toFixed(4));

    if (metricChoice.score < 0.7) {
      return this.rejectedResolve(
        source,
        request,
        "schema_unresolved",
        [`Top metric match '${metricChoice.field}' scored below the 0.70 threshold.`],
        startMs,
        metricCandidates,
      );
    }
    if (metricChoice.score < 0.85 || metricGap < 0.1) {
      return this.clarifyResolve(
        source,
        request,
        [`Metric mapping for '${metricHint}' is not decisive enough for execution.`],
        startMs,
        metricCandidates,
      );
    }

    let resolvedGroup: string | null = null;
    let groupCandidates: QueryCandidate[] = [];
    if (typeof request.group_by === "string" && request.group_by.trim()) {
      const groupRanked = this.rankFields(source, request.group_by, false);
      groupCandidates = this.buildCandidates(source, groupRanked, "dimension");
      if (groupRanked.length === 0) {
        return this.rejectedResolve(
          source,
          request,
          "schema_unresolved",
          [`No field matched group_by '${request.group_by}'.`],
          startMs,
          metricCandidates,
        );
      }
      const groupChoice = groupRanked[0];
      const groupSecond = groupRanked[1]?.score ?? 0;
      const groupGap = Number((groupChoice.score - groupSecond).toFixed(4));
      if (groupChoice.score < 0.7) {
        return this.rejectedResolve(
          source,
          request,
          "schema_unresolved",
          [`Top group_by match '${groupChoice.field}' scored below the 0.70 threshold.`],
          startMs,
          [...metricCandidates, ...groupCandidates],
        );
      }
      if (groupChoice.score < 0.85 || groupGap < 0.1) {
        return this.clarifyResolve(
          source,
          request,
          [`Group_by mapping for '${request.group_by}' is not decisive enough for execution.`],
          startMs,
          [...metricCandidates, ...groupCandidates],
        );
      }
      resolvedGroup = groupChoice.field;
    }

    const resolvedPlan: ResolvedPlan = {
      source_name: source.name,
      metric_column: metricChoice.field,
      aggregation,
      group_column: resolvedGroup,
      join_path: null,
      filter: (request.filter as Record<string, unknown> | undefined) ?? null,
      limit: typeof request.limit === "number" ? request.limit : null,
      order: typeof request.order === "string" ? request.order : "desc",
      constraints: (request.constraints as Record<string, unknown> | undefined) ?? {},
      schema_revision: source.schemaRevision,
    };
    const planHash = exactPlanHash(resolvedPlan);
    const signature = intentSignature(source.name, request, source.schemaRevision);
    const decisionPath =
      isExactFieldMatch(metricChoice.field, metricHint) &&
      (!resolvedGroup || isExactFieldMatch(resolvedGroup, String(request.group_by ?? "")))
        ? "exact_spec"
        : "planner_hint";

    return {
      resolved_plan: resolvedPlan,
      confidence: 1,
      plan: [
        `Use source '${source.name}'.`,
        `Aggregate '${metricChoice.field}' with '${aggregation}'.`,
        ...(resolvedGroup ? [`Group by '${resolvedGroup}'.`] : []),
      ],
      explanation: [
        `Resolved metric '${metricHint}' to '${metricChoice.field}'.`,
        ...(resolvedGroup ? [`Resolved group_by '${request.group_by}' to '${resolvedGroup}'.`] : []),
      ],
      resolved_column: metricChoice.field,
      resolved_role: "measure",
      resolved_source: source.name,
      candidates: [...metricCandidates, ...groupCandidates],
      source_scores: { [source.name]: 1 },
      latency_ms: roundLatency(startMs),
      decision_path: decisionPath,
      plan_hash: planHash,
      schema_revision: source.schemaRevision,
      validated: true,
      deterministic_scope: "local_registered_source",
      confidence_source: "local_schema_match",
      clarification_required: false,
      rejection_reason: null,
      request_id: `local_${signature.slice(0, 12)}`,
      intent_signature: signature,
      source_set: [source.name],
      join_path: [],
      planner_mode: "local_structured_intent",
    };
  }

  private rejectedResolve(
    source: LocalSource,
    request: Record<string, unknown>,
    reason: string,
    explanation: string[],
    startMs: number,
    candidates: QueryCandidate[] = [],
  ): ResolveResponse {
    const signature = intentSignature(source.name, request, source.schemaRevision);
    return {
      resolved_plan: null,
      confidence: 0,
      plan: [],
      explanation,
      resolved_column: "",
      resolved_role: "",
      resolved_source: source.name,
      candidates,
      source_scores: { [source.name]: 1 },
      latency_ms: roundLatency(startMs),
      decision_path: "planner_hint",
      plan_hash: null,
      schema_revision: source.schemaRevision,
      validated: false,
      deterministic_scope: "local_registered_source",
      confidence_source: "local_schema_match",
      clarification_required: false,
      rejection_reason: reason,
      request_id: `local_${signature.slice(0, 12)}`,
      intent_signature: signature,
      source_set: [source.name],
      join_path: [],
      planner_mode: "local_structured_intent",
    };
  }

  private clarifyResolve(
    source: LocalSource,
    request: Record<string, unknown>,
    explanation: string[],
    startMs: number,
    candidates: QueryCandidate[],
  ): ResolveResponse {
    const signature = intentSignature(source.name, request, source.schemaRevision);
    return {
      resolved_plan: null,
      confidence: 0.75,
      plan: [],
      explanation,
      resolved_column: "",
      resolved_role: "",
      resolved_source: source.name,
      candidates,
      source_scores: { [source.name]: 1 },
      latency_ms: roundLatency(startMs),
      decision_path: "planner_hint",
      plan_hash: null,
      schema_revision: source.schemaRevision,
      validated: false,
      deterministic_scope: "local_registered_source",
      confidence_source: "local_schema_match",
      clarification_required: true,
      rejection_reason: null,
      request_id: `local_${signature.slice(0, 12)}`,
      intent_signature: signature,
      source_set: [source.name],
      join_path: [],
      planner_mode: "local_structured_intent",
    };
  }

  private coercePlan(
    request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
    overrides: Record<string, unknown>,
  ): ResolvedPlan {
    const payload =
      Object.keys(overrides).length > 0
        ? overrides
        : "resolved_plan" in request
          ? (request.resolved_plan as ResolvedPlan | null)
          : request;
    if (!payload) {
      throw new RuntimeValidationError(
        "query_requires_executable_plan",
        "Runtime.query() requires an executable plan.",
      );
    }
    return payload as ResolvedPlan;
  }

  private async queryLocal(
    request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
    overrides: Record<string, unknown>,
  ): Promise<QueryResponse> {
    const startMs = Date.now();
    const plan = this.coercePlan(request, overrides);
    const source = this.localSources.get(plan.source_name);
    if (!source) {
      throw new RuntimeValidationError(
        "unknown_source",
        "Query plan references a source that is not connected to this runtime.",
        { source_name: plan.source_name },
      );
    }
    if (plan.schema_revision !== source.schemaRevision) {
      throw new RuntimeValidationError(
        "schema_revision_mismatch",
        "Query plan schema_revision does not match the connected source.",
        { expected: source.schemaRevision, received: plan.schema_revision },
      );
    }

    await this.ensureLocalExecutionEntitlement();
    this.consumeLocalCredit();

    let executionRecords = source.records;
    const localPlanSteps: string[] = [];
    const filterValue =
      plan.filter && typeof plan.filter === "object" ? (plan.filter as Record<string, unknown>) : {};
    const timeFilter = typeof filterValue.time_filter === "string" ? filterValue.time_filter.trim() : "";
    if (timeFilter) {
      const localTimeField = findLocalTimeField(source);
      const localTimeRange = timeRange(timeFilter);
      if (localTimeField && localTimeRange) {
        const before = executionRecords.length;
        executionRecords = executionRecords.filter(record => {
          const parsed = parseDateValue(record[localTimeField]);
          return (
            parsed !== null &&
            parsed.getTime() >= localTimeRange.start.getTime() &&
            parsed.getTime() <= localTimeRange.end.getTime()
          );
        });
        localPlanSteps.push(
          `Time filter '${timeFilter}' on '${localTimeField}': ${before}->${executionRecords.length} rows.`,
        );
      } else {
        localPlanSteps.push("No time-like field found. time_filter skipped.");
      }
    }

    const resolvedFilterConditions = resolveLocalFilterConditions(source, filterValue);
    const filteredLocalRecords = applyLocalFilterConditions(executionRecords, resolvedFilterConditions);
    executionRecords = filteredLocalRecords.records;
    localPlanSteps.push(...filteredLocalRecords.planSteps);

    const rows = executePlan(
      executionRecords,
      plan.metric_column,
      plan.group_column,
      plan.aggregation,
      plan.limit ?? 100,
    );
    const result = plan.group_column ? rows : rows[0]?.[plan.metric_column] ?? null;

    return {
      query_id: `local_query_${exactPlanHash(plan).slice(0, 12)}`,
      result,
      result_type: plan.group_column ? "table" : "scalar",
      confidence: 1,
      plan: [
        `Use source '${source.name}'.`,
        `Aggregate '${plan.metric_column}' with '${plan.aggregation}'.`,
        ...(plan.group_column ? [`Group by '${plan.group_column}'.`] : []),
        ...localPlanSteps,
      ],
      resolved_column: plan.metric_column,
      resolved_role: "measure",
      resolved_source: source.name,
      row_count: plan.group_column ? rows.length : result === null ? 0 : 1,
      candidates: [],
      source_scores: { [source.name]: 1 },
      ambiguous: false,
      exact_spec: true,
      explanation: ["Executed deterministic local plan."],
      latency_ms: roundLatency(startMs),
      decision_path: "exact_spec",
      plan_hash: exactPlanHash(plan),
      schema_revision: source.schemaRevision,
      validated: true,
      deterministic_scope: "local_registered_source",
      confidence_source: "local_exact_execution",
      clarification_required: false,
      rejection_reason: null,
      request_id: `local_query_${exactPlanHash(plan).slice(0, 12)}`,
      source_set: [source.name],
      join_path: [],
      planner_mode: "local_structured_intent",
    };
  }

  private verifyLocal(
    request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
    overrides: Record<string, unknown>,
  ): VerifyResponse {
    const startMs = Date.now();
    try {
      const plan = this.coercePlan(request, overrides);
      const source = this.localSources.get(plan.source_name);
      const errors: string[] = [];
      if (!source) {
        errors.push(`Source '${plan.source_name}' is not connected.`);
      } else {
        if (plan.schema_revision !== source.schemaRevision) {
          errors.push("schema_revision mismatch");
        }
        if (!source.fields.includes(plan.metric_column)) {
          errors.push(`Metric column '${plan.metric_column}' is missing.`);
        }
        if (plan.group_column && !source.fields.includes(plan.group_column)) {
          errors.push(`Group column '${plan.group_column}' is missing.`);
        }
        try {
          resolveLocalFilterConditions(
            source,
            plan.filter && typeof plan.filter === "object" ? (plan.filter as Record<string, unknown>) : {},
          );
        } catch (error) {
          if (error instanceof RuntimeValidationError) {
            errors.push(error.message);
          } else {
            throw error;
          }
        }
      }
      const valid = errors.length === 0;
      return {
        valid,
        errors,
        suggestions: valid ? [] : ["Reconnect the source or rerun resolve against the current schema."],
        resolved: {
          source_name: plan.source_name,
          metric_column: plan.metric_column,
          group_column: plan.group_column ?? "",
        },
        valid_dimensions: plan.group_column ? [plan.group_column] : [],
        valid_measures: [plan.metric_column],
        source_behavior: "local_registered_source",
        latency_ms: roundLatency(startMs),
        verified: valid,
        request_id: `local_verify_${exactPlanHash(plan).slice(0, 12)}`,
        schema_revision: plan.schema_revision,
        plan_hash: exactPlanHash(plan),
        verification_mode: "local",
        rejection_reason: valid ? null : "plan_verification_failed",
      };
    } catch (error) {
      if (error instanceof RuntimeError) {
        return {
          valid: false,
          errors: [error.message],
          suggestions: ["Run Runtime.resolve(...) again with a more explicit metric or source."],
          resolved: {},
          latency_ms: roundLatency(startMs),
          verified: false,
          verification_mode: "local",
          rejection_reason: error.code,
        };
      }
      throw error;
    }
  }

  private coerceApiQueryPayload(
    request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
    overrides: Record<string, unknown>,
  ): Record<string, unknown> {
    if (Object.keys(overrides).length > 0) {
      return this.extractRuntimeDatasetScope({ ...overrides });
    }
    if ("resolved_plan" in request) {
      if (!request.resolved_plan) {
        throw new RuntimeValidationError(
          "query_requires_executable_plan",
          "Runtime.query() requires an executable plan.",
        );
      }
      return this.extractRuntimeDatasetScope({
        resolved_plan: { ...(request.resolved_plan as Record<string, unknown>) },
      });
    }
    if (looksLikeResolvedPlan(request)) {
      return this.extractRuntimeDatasetScope({
        resolved_plan: { ...(request as unknown as Record<string, unknown>) },
      });
    }
    return this.extractRuntimeDatasetScope({ ...(request as Record<string, unknown>) });
  }

  private extractRuntimeDatasetScope(payload: Record<string, unknown>): Record<string, unknown> {
    const resolvedPlan = payload.resolved_plan;
    if (!resolvedPlan || typeof resolvedPlan !== "object" || Array.isArray(resolvedPlan)) {
      return payload;
    }
    const resolvedPlanPayload = { ...(resolvedPlan as Record<string, unknown>) };
    const rawConstraints = resolvedPlanPayload.constraints;
    if (!rawConstraints || typeof rawConstraints !== "object" || Array.isArray(rawConstraints)) {
      payload.resolved_plan = resolvedPlanPayload;
      return payload;
    }
    const constraints = { ...(rawConstraints as Record<string, unknown>) };
    const datasetId = constraints[RUNTIME_DATASET_SCOPE_KEY];
    delete constraints[RUNTIME_DATASET_SCOPE_KEY];
    if (
      payload.dataset_id === undefined &&
      typeof datasetId === "string" &&
      datasetId.trim()
    ) {
      payload.dataset_id = datasetId.trim();
    }
    resolvedPlanPayload.constraints = constraints;
    payload.resolved_plan = resolvedPlanPayload;
    return payload;
  }

  private coerceApiResolvePayload(request: Record<string, unknown>): Record<string, unknown> {
    const payload: Record<string, unknown> = { ...request };
    const sourceName = payload.source_name;
    if (typeof sourceName === "string" && sourceName.trim()) {
      if (payload.preferred_source === undefined) {
        payload.preferred_source = sourceName.trim();
      }
      if (payload.allow_org_scope === undefined) {
        payload.allow_org_scope = true;
      }
    }
    delete payload.source_name;

    const metric = payload.metric;
    if (typeof metric === "string") {
      payload.metric = {
        role: "metric",
        hint: metric.trim(),
      };
    }

    const groupBy = payload.group_by;
    if (typeof groupBy === "string") {
      payload.group_by = [groupBy];
    } else if (groupBy == null) {
      const groupColumn = payload.group_column;
      if (typeof groupColumn === "string" && groupColumn.trim()) {
        payload.group_by = [groupColumn.trim()];
      }
    }
    delete payload.group_column;
    delete payload.metric_column;
    delete payload.resolved_plan;
    return payload;
  }
}
