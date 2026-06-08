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

export { DecisionEngineClientConfig };

const DEFAULT_TIMEOUT = 120_000;
const DEFAULT_MAX_RETRIES = 3;
const DEFAULT_JOIN_PATH_HOPS = 4;
const MAX_JOIN_PATH_HOPS = 6;
const SDK_USER_AGENT = "algenta-ts/1.0.0";

const RUNTIME_MATURITY_VALUES = [
  "experimental",
  "benchmarked",
  "parity_tested",
  "channel_covered",
  "enterprise_ready",
  "deprecated",
] as const;
const RUNTIME_SIDE_EFFECT_CLASS_VALUES = [
  "read_only",
  "write_scoped",
  "write_external",
  "exec_external",
  "network_external",
] as const;
const RUNTIME_RISK_LEVEL_VALUES = ["low", "medium", "high", "critical"] as const;
const RUNTIME_REPLAYABILITY_VALUES = [
  "deterministic",
  "artifact_backed",
  "non_replayable",
] as const;
const RUNTIME_SUPPORTED_CHANNEL_VALUES = [
  "python_sdk",
  "typescript_sdk",
  "cli",
  "mcp",
] as const;
const RUNTIME_AUXILIARY_CHANNEL_VALUES = ["daemon_client", "runtime_local"] as const;
const RUNTIME_FEATURE_FLAG_CHANNEL_VALUES = ["http_api_feature_flag"] as const;
const RUNTIME_DEPLOYMENT_MODE_VALUES = [
  "saas",
  "vpc",
  "self_hosted",
  "air_gapped",
  "hybrid_provider",
  "local_dev_daemon",
] as const;
const RUNTIME_LAYER_VALUES = [
  "mojo_llm_runtime_core",
  "python_compatibility_ring",
  "llm_api_provider_layer",
  "agent_runtime",
  "decision_runtime",
  "enterprise_control_plane",
] as const;
const RUNTIME_COMPILED_ENGINE_VALUES = ["mojo", "python_fallback"] as const;
const RUNTIME_KERNEL_PROMOTION_STATUS_VALUES = ["candidate", "shipping"] as const;
const RUNTIME_BENCHMARK_DISCOVERY_RULE_VALUES = [
  "Only the 22-module, 209-function LLM rollout is treated as the shipping runtime contract.",
] as const;
const RUNTIME_NON_SHIPPING_RULE_VALUES = [
  "The broader Mojo inventory remains a benchmark and discovery lane only; modules are not advertised on the runtime surface unless listed in this manifest.",
] as const;
const RUNTIME_MODULE_ID_VALUES = [
  "bpe_tokenizer",
  "text.tokenizer",
  "embeddings",
  "flash_attention",
  "sparse_attention",
  "transformer_attention",
  "transformer_blocks",
  "llm_sampling",
  "vector_similarity",
  "vector_search",
  "vector_kernels.ranker",
  "vector_kernels.table",
  "sparse_vector",
  "rlhf_dpo",
  "rerank_eval",
  "inference_cost_latency",
  "kv_cache",
  "paged_kv_cache",
  "continuous_batching",
  "inference_engine",
  "speculative_decoding",
  "generation_loop",
] as const;
const RUNTIME_PUBLIC_ENDPOINT_VALUES = [
  "/v1/meta/contract",
  "/v1/runtime/manifest",
] as const;
const RUNTIME_ADMIN_ENDPOINT_VALUES = [
  "/v1/admin/runtime/modules",
  "/v1/admin/runtime/benchmarks",
  "/v1/admin/runtime/validation",
] as const;
const RUNTIME_FEATURE_FLAG_ENDPOINT_VALUES = [
  "/v1/libraries",
  "/v1/libraries/health",
  "/v1/libraries/execute",
] as const;
const RUNTIME_EXECUTION_TRANSITION_VALUES = [
  "model_call_started",
  "model_token_emitted",
  "tool_call_requested",
  "tool_call_approved",
  "tool_call_denied",
  "checkpoint_committed",
  "decision_plan_created",
  "simulation_started",
  "execution_started",
  "replay_started",
  "failure_emitted",
] as const;
const RUNTIME_RELEASE_CONDITION_VALUES = [
  "manifest-listed",
  "proof-backed",
  "policy-covered",
  "replay-tested",
  "deployment-mode validated",
] as const;
const RUNTIME_FAILURE_CODE_VALUES = [
  "provider_timeout",
  "runtime_compile_error",
  "mcp_tool_denied",
  "policy_denied",
  "schema_access_denied",
  "checkpoint_failed",
  "replay_mismatch",
  "external_dependency_unavailable",
  "backend_unavailable",
  "quota_exceeded",
  "approval_required",
  "kv_cache_exhausted",
  "artifact_load_failed",
  "memory_pressure_limit",
  "tenant_cache_violation",
  "checkpoint_state_overflow",
] as const;
const RUNTIME_BENCHMARK_CLASS_VALUES = [
  "B1",
  "B2",
  "B3",
  "B4",
  "B5",
  "B6",
  "B7",
  "B8",
  "B9",
  "B10",
] as const;
const RUNTIME_SCHEDULER_POLICY_VALUES = [
  "FIFO",
  "priority_queue",
  "deadline_aware",
  "cost_aware",
  "tenant_fair",
  "kv_cache_aware",
  "batching_aware",
  "speculative_decoding_aware",
  "policy_constrained",
] as const;
const RUNTIME_SCHEDULER_MINIMIZE_VALUES = [
  "tail latency",
  "memory waste",
  "context-switch overhead",
  "provider cost",
  "starvation",
] as const;
const RUNTIME_SCHEDULER_MAXIMIZE_VALUES = [
  "GPU or CPU utilization",
  "KV cache reuse",
  "batching efficiency",
  "token throughput",
  "fairness",
] as const;
const RUNTIME_SCHEDULER_INVARIANT_VALUES = [
  "No request starves indefinitely.",
  "High-priority requests cannot violate tenant quota.",
  "Batching may not cross isolation boundaries when policy forbids it.",
  "Speculative decoding may not emit unverified tokens.",
] as const;
const RUNTIME_RELEASE_GATE_VALUES = ["A", "B", "C", "D", "E", "F", "G"] as const;
const RUNTIME_INVARIANT_NAME_VALUES = [
  "Manifest Truth",
  "Replay Determinism",
  "Policy Monotonicity",
  "No Silent Fallback",
  "Audit Completeness",
  "Tenant Non-Interference",
] as const;
const RUNTIME_EXECUTION_STATE_FIELD_VALUES = [
  "request",
  "tenant",
  "workspace",
  "policy_snapshot",
  "schema_snapshot",
  "runtime_manifest",
  "model_backend",
  "tool_manifest",
  "checkpoint_log",
  "event_log",
  "decision_state",
] as const;
const RUNTIME_EXECUTION_VALIDITY_RULE_VALUES = [
  "schema-valid",
  "policy-valid",
  "ordered",
  "replayable",
  "audit-visible",
] as const;
const RUNTIME_LINEAGE_NODE_FIELD_VALUES = [
  "node_id",
  "artifact_type",
  "content_hash",
  "parent_hashes",
  "tenant_scope",
  "workspace_scope",
  "timestamp",
  "manifest_version",
  "policy_snapshot_id",
  "schema_snapshot_id",
] as const;
const RUNTIME_EXTERNAL_NONDETERMINISM_SOURCE_VALUES = [
  "provider responses",
  "MCP tool responses",
  "database snapshots",
  "clock time",
  "random seeds",
  "external API outputs",
] as const;
const RUNTIME_NONDETERMINISM_ARTIFACT_VALUES = [
  "provider response record",
  "tool or MCP response record",
  "data snapshot reference or query result hash",
  "clock snapshot",
  "seed record",
  "backend or version identifier",
] as const;
const RUNTIME_ARTIFACT_LINEAGE_STEP_VALUES = [
  "input",
  "policy snapshot",
  "schema snapshot",
  "runtime manifest",
  "backend or model",
  "tool or MCP calls",
  "checkpoints",
  "decision plan",
  "execution record",
  "outcome",
  "evaluation result",
] as const;
const RUNTIME_CAPABILITY_FIELD_VALUES = [
  "tool_name",
  "input_schema",
  "output_schema",
  "side_effect_class",
  "risk_level",
  "required_policy",
  "replayability",
  "approval_required",
] as const;
const RUNTIME_CAPABILITY_RULE_VALUES = [
  "MCP tools are untrusted by default.",
  "No tool may execute without a capability record.",
  "Approvals and fallbacks derive from capability algebra, not ad hoc code paths.",
] as const;
const RUNTIME_SLO_BUDGET_NAME_VALUES = [
  "runtime_manifest_load",
  "ttft",
  "end_to_end_turn",
  "agent_checkpoint_commit",
  "mcp_call_first_party",
  "decision_plan_creation",
  "replay",
] as const;
const RUNTIME_SLO_BUDGET_APPLIES_TO_VALUES = [
  "first-party runtime manifest route",
  "first-party native LLM serving path",
  "agent runtime checkpoint persistence",
  "first-party or internal MCP tools",
  "decision runtime plan generation",
  "runs up to 1000 events",
] as const;
const RUNTIME_MEMORY_REGION_VALUES = [
  "model weights",
  "KV cache pages",
  "prompt token buffer",
  "generation buffer",
  "retrieval context buffer",
  "checkpoint state",
  "tool-call state",
  "tenant-local cache",
] as const;
const RUNTIME_MEMORY_RULE_VALUES = [
  "KV pages are tenant-scoped.",
  "Evicted cache pages must be zeroed or isolation-proven before reuse.",
  "Checkpoint state must reference immutable artifact hashes.",
  "Model weights must be version-pinned.",
  "Memory pressure must emit typed failure and never degrade silently.",
] as const;
const RUNTIME_PROOF_OBLIGATION_VALUES = [
  "numerical parity",
  "deterministic kernels",
  "latency and memory bounds",
  "channel proof",
  "manifest listing",
  "API equivalence",
  "behavioral equivalence against Python reference",
  "OpenAI-compatible schema parity",
  "streaming semantics parity",
  "typed failure parity",
  "event ordering",
  "checkpoint correctness",
  "cancellation safety",
  "replay safety",
  "evidence completeness",
  "simulation traceability",
  "approval correctness",
  "tenant isolation",
  "policy enforcement",
  "metering correctness",
] as const;
const RUNTIME_BENCHMARK_METRIC_VALUES = [
  "p50",
  "p90",
  "p95",
  "p99",
  "tokens_per_second",
  "ttft",
  "requests_per_second",
  "memory_peak",
  "cache_hit_rate",
  "checkpoint_commit_latency",
  "replay_latency",
  "tool_call_latency",
  "decision_plan_latency",
  "simulation_latency",
  "cost_per_successful_run",
] as const;
const RUNTIME_BENCHMARK_BASELINE_VALUES = [
  "Python reference",
  "PyTorch or Transformers path",
  "vLLM OpenAI-compatible backend",
  "llama.cpp GGUF backend",
  "ONNX Runtime backend",
  "CTranslate2 backend",
  "Algenta Mojo-native path",
] as const;
const RUNTIME_EVALUATION_METHOD_VALUES = [
  "bootstrap confidence intervals",
  "paired model comparisons",
  "regression tests",
  "drift detection",
  "A/B experiments",
  "counterfactual replay",
  "Monte Carlo simulation",
  "sensitivity analysis",
] as const;
const RUNTIME_RELEASE_BLOCKER_VALUES = [
  "replay success regression",
  "policy violation increase",
  "p95 budget violation",
  "RAG precision drop",
  "tool-call error-rate increase",
  "decision-plan validity drop",
] as const;
const RUNTIME_EVALUATION_DIMENSION_VALUES = [
  "answer correctness",
  "tool-call correctness",
  "schema correctness",
  "retrieval precision and recall",
  "hallucination rate",
  "policy violation rate",
  "replay success rate",
  "decision outcome delta",
  "cost-quality frontier",
  "latency-quality frontier",
] as const;
const RUNTIME_THREAT_CLASS_VALUES = [
  "prompt injection",
  "tool injection",
  "MCP abuse",
  "data exfiltration",
  "cross-tenant leakage",
  "provider fallback leakage",
  "secret exposure",
  "replay tampering",
  "audit log mutation",
  "model artifact poisoning",
  "dependency supply-chain attack",
  "billing abuse",
  "quota bypass",
] as const;
const RUNTIME_THREAT_CONTROL_VALUES = [
  "tool allowlists",
  "argument validation",
  "result sanitization",
  "egress policy",
  "signed manifests",
  "signed artifacts",
  "immutable audit logs",
  "policy snapshots",
  "secret scoping",
  "tenant-scoped cache",
  "SBOM",
  "dependency pinning",
  "runtime attestation",
] as const;
const RUNTIME_THREAT_RULE_VALUES = ["MCP tools are untrusted by default."] as const;
const RUNTIME_RELEASE_ARTIFACT_VALUES = [
  "signed runtime manifest",
  "module maturity table",
  "benchmark report",
  "parity report",
  "replay report",
  "security report",
  "compatibility report",
  "migration notes",
  "known limitations",
] as const;
const RUNTIME_ARTIFACT_KIND_VALUES = [
  "proof_bundle",
  "parity_benchmark",
  "compiled_runtime_benchmark",
  "compiled_mojo_binary",
] as const;
const RUNTIME_SIGNATURE_ALGORITHM_VALUES = ["hmac-sha256"] as const;
const RUNTIME_SIGNATURE_SCOPE_VALUES = ["control_plane_hmac_v1"] as const;

function normalizeMaxJoinHops(value: unknown, fieldPath: string): number {
  if (!Number.isInteger(value)) {
    throw new Error(`${fieldPath} must be an integer between 1 and ${MAX_JOIN_PATH_HOPS}.`);
  }
  const normalized = Number(value);
  if (normalized < 1 || normalized > MAX_JOIN_PATH_HOPS) {
    throw new Error(`${fieldPath} must be between 1 and ${MAX_JOIN_PATH_HOPS}.`);
  }
  return normalized;
}

function requireNonNegativeInteger(value: unknown, errorMessage: string): number {
  if (!Number.isInteger(value)) {
    throw new DecisionEngineError(errorMessage);
  }
  const normalized = Number(value);
  if (normalized < 0) {
    throw new DecisionEngineError(errorMessage);
  }
  return normalized;
}

function requirePositiveInteger(value: unknown, errorMessage: string): number {
  const normalized = requireNonNegativeInteger(value, errorMessage);
  if (normalized < 1) {
    throw new DecisionEngineError(errorMessage);
  }
  return normalized;
}

function normalizeJoinPathSpec(joinPath: Record<string, unknown>): Record<string, unknown> {
  const normalized: Record<string, unknown> = { ...joinPath };
  const maxHops =
    normalized.max_hops === undefined
      ? DEFAULT_JOIN_PATH_HOPS
      : normalizeMaxJoinHops(normalized.max_hops, "join_path.max_hops");
  normalized.max_hops = maxHops;
  const edges = normalized.edges;
  if (Array.isArray(edges) && edges.length > maxHops) {
    throw new Error(
      `join_path.edges has ${edges.length} entries but join_path.max_hops=${maxHops}.`,
    );
  }
  return normalized;
}

function normalizeQueryLikeRequest(request: Record<string, unknown>): Record<string, unknown> {
  const normalized: Record<string, unknown> = { ...request };
  if (normalized.join_path && typeof normalized.join_path === "object") {
    normalized.join_path = normalizeJoinPathSpec(
      normalized.join_path as Record<string, unknown>,
    );
  }
  if (normalized.constraints && typeof normalized.constraints === "object") {
    const constraints = { ...(normalized.constraints as Record<string, unknown>) };
    if (constraints.max_join_hops !== undefined) {
      constraints.max_join_hops = normalizeMaxJoinHops(
        constraints.max_join_hops,
        "constraints.max_join_hops",
      );
    }
    normalized.constraints = constraints;
  }
  return normalized;
}

function mergeRequestPayload(
  request: Record<string, unknown> | undefined,
  extra: Record<string, unknown> = {},
): Record<string, unknown> {
  return normalizeQueryLikeRequest({ ...(request ?? {}), ...extra });
}

function cloneJsonValue<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function mergeContractSections<T>(base: T, override: unknown): T {
  if (
    base &&
    typeof base === "object" &&
    !Array.isArray(base) &&
    override &&
    typeof override === "object" &&
    !Array.isArray(override)
  ) {
    const merged: Record<string, unknown> = cloneJsonValue(base as Record<string, unknown>);
    for (const [key, value] of Object.entries(override as Record<string, unknown>)) {
      merged[key] = mergeContractSections(merged[key], value);
    }
    return merged as T;
  }
  return cloneJsonValue(override as T);
}

function appendQueryParameters(
  path: string,
  params: Record<string, string | number | undefined>,
): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined) continue;
    query.set(key, String(value));
  }
  const serialized = query.toString();
  return serialized ? `${path}?${serialized}` : path;
}

function invalidStreamError(
  code: string,
  message: string,
  details: Record<string, unknown>,
): DecisionEngineError {
  return new DecisionEngineError(message, 0, code, {
    error: {
      code,
      message,
      details,
    },
  });
}

function parseSseEvent(rawEvent: string): unknown | "[DONE]" | null {
  const dataLines: string[] = [];
  for (const rawLine of rawEvent.split(/\r?\n/)) {
    const line = rawLine.trimEnd();
    if (!line || line.startsWith(":")) {
      continue;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (dataLines.length === 0) {
    return null;
  }
  const payloadText = dataLines.join("\n");
  if (payloadText === "[DONE]") {
    return "[DONE]";
  }
  try {
    return JSON.parse(payloadText) as unknown;
  } catch {
    throw invalidStreamError(
      "invalid_sse_event",
      "Received invalid JSON in Server-Sent Events payload.",
      { payload: payloadText },
    );
  }
}

async function* iterateSsePayloads(body: ReadableStream<Uint8Array>): AsyncGenerator<unknown> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    while (true) {
      const separatorIndex = buffer.indexOf("\n\n");
      if (separatorIndex === -1) {
        break;
      }
      const rawEvent = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);
      const payload = parseSseEvent(rawEvent);
      if (payload === null) {
        continue;
      }
      if (payload === "[DONE]") {
        return;
      }
      yield payload;
    }
    if (done) {
      break;
    }
  }
  const trailing = buffer.trim();
  if (!trailing) {
    return;
  }
  const payload = parseSseEvent(trailing);
  if (payload === null || payload === "[DONE]") {
    return;
  }
  yield payload;
}

function normalizeSourceRegistrationRequest(
  source?: SourceRegistrationRequest | Record<string, unknown>,
  description?: string,
  extra: Record<string, unknown> = {},
): Record<string, unknown> {
  let payload: Record<string, unknown>;
  if (source && typeof source === 'object' && 'source' in source) {
    payload = { ...(source as Record<string, unknown>) };
  } else {
    payload = { source: { ...(source ?? {}), ...extra } };
    extra = {};
  }

  if (Object.keys(extra).length > 0) {
    payload = { ...payload, ...extra };
  }
  if (description !== undefined) {
    payload.description = description;
  }
  return payload;
}

function endpointSuffix(endpoint: string): string {
  const normalizedDefault = DEFAULT_BASE_URL.replace(/\/$/, "");
  if (endpoint.startsWith(normalizedDefault)) {
    const suffix = endpoint.slice(normalizedDefault.length);
    return suffix.length > 0 ? suffix : "/";
  }
  try {
    const url = new URL(endpoint);
    return `${url.pathname || "/"}${url.search}`;
  } catch {
    return endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  }
}

function rebaseEndpoint(baseUrl: string, endpoint: string): string {
  return `${baseUrl.replace(/\/$/, "")}${endpointSuffix(endpoint)}`;
}

function assertPrimaryDataQueryContractExtension(
  payload: unknown,
): PrimaryDataQueryContract {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError(
      "OpenAPI contract fallback payload must be a JSON object.",
      0,
      "invalid_contract_payload",
    );
  }
  const extension = (payload as { ["x-primary-data-query-contract"]?: unknown })[
    "x-primary-data-query-contract"
  ];
  if (!extension || typeof extension !== "object" || Array.isArray(extension)) {
    throw new DecisionEngineError(
      "OpenAPI contract fallback is missing x-primary-data-query-contract.",
      0,
      "contract_extension_missing",
    );
  }
  const apiContract = (extension as { api?: unknown }).api;
  if (!apiContract || typeof apiContract !== "object" || Array.isArray(apiContract)) {
    throw new DecisionEngineError(
      "OpenAPI contract fallback is missing the api contract section.",
      0,
      "invalid_contract_payload",
    );
  }
  if (typeof (apiContract as { contract_endpoint?: unknown }).contract_endpoint !== "string") {
    throw new DecisionEngineError(
      "OpenAPI contract fallback is missing api.contract_endpoint.",
      0,
      "invalid_contract_payload",
    );
  }
  const merged = mergeContractSections(PRIMARY_DATA_QUERY_CONTRACT, extension);
  return merged;
}

function buildPlatformContractFromOpenApi(
  baseUrl: string,
  payload: unknown,
): PlatformContractResponse {
  const apiBaseUrl = baseUrl.replace(/\/$/, "");
  const schema =
    payload && typeof payload === "object" && !Array.isArray(payload)
      ? (payload as { ["x-capability-plane-contract"]?: unknown })
      : {};
  let capabilityPlane: CapabilityPlaneContract | null = null;
  const capabilityPlaneExtension = schema["x-capability-plane-contract"];
  if (capabilityPlaneExtension !== undefined) {
    if (
      !capabilityPlaneExtension ||
      typeof capabilityPlaneExtension !== "object" ||
      Array.isArray(capabilityPlaneExtension)
    ) {
      throw new DecisionEngineError(
        "OpenAPI contract fallback returned an invalid x-capability-plane-contract payload.",
        0,
        "invalid_contract_payload",
      );
    }
    capabilityPlane = mergeContractSections(
      CAPABILITY_PLANE_CONTRACT,
      capabilityPlaneExtension,
    ) as CapabilityPlaneContract;
  }
  return {
    contract_version: CONTRACT_VERSION,
    brand: BRAND,
    api_base_url: apiBaseUrl,
    mcp_endpoint: rebaseEndpoint(apiBaseUrl, MCP_ENDPOINT),
    mcp_tools_endpoint: rebaseEndpoint(apiBaseUrl, MCP_TOOLS_ENDPOINT),
    auth_scheme: AUTH_SCHEME,
    api_key_prefixes: {
      live: API_KEY_PREFIX_LIVE,
      test: API_KEY_PREFIX_TEST,
    },
    compatibility: {
      legacy_headers: [...LEGACY_HEADERS],
      legacy_env_vars: [...LEGACY_ENV_VARS],
      legacy_domains: [...LEGACY_DOMAINS],
      deprecation_window_days: DEPRECATION_WINDOW_DAYS,
    } satisfies CompatibilityContract,
    privacy_registry: {
      algenta_owned_hosts: [...ALGENTA_OWNED_HOSTS],
      algenta_owned_suffixes: [...ALGENTA_OWNED_SUFFIXES],
      vendor_telemetry_hosts: [...VENDOR_TELEMETRY_HOSTS],
      private_host_suffixes: [...PRIVATE_HOST_SUFFIXES],
    } satisfies PrivacyRegistryContract,
    defaults: {
      read_only_default: READ_ONLY_DEFAULT,
      write_confirmation_required: WRITE_CONFIRMATION_REQUIRED,
      plan_limits: cloneJsonValue(PLAN_LIMITS),
    } satisfies DefaultsContract,
    primary_data_query_contract: cloneJsonValue(assertPrimaryDataQueryContractExtension(payload)),
    capability_plane: capabilityPlane,
    integrations: cloneJsonValue(INTEGRATIONS),
  };
}

function assertApiKeyPrefixes(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.live, `${context}.live`);
  assertNonEmptyString(obj.test, `${context}.test`);
}

function assertCompatibilityContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertStringArray(obj.legacy_headers, `${context}.legacy_headers`);
  assertStringArray(obj.legacy_env_vars, `${context}.legacy_env_vars`);
  assertStringArray(obj.legacy_domains, `${context}.legacy_domains`);
  assertInteger(obj.deprecation_window_days, `${context}.deprecation_window_days`);
}

function assertPrivacyRegistryContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertStringArray(obj.algenta_owned_hosts, `${context}.algenta_owned_hosts`);
  assertStringArray(obj.algenta_owned_suffixes, `${context}.algenta_owned_suffixes`);
  assertStringArray(obj.vendor_telemetry_hosts, `${context}.vendor_telemetry_hosts`);
  assertStringArray(obj.private_host_suffixes, `${context}.private_host_suffixes`);
}

function assertDefaultsContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertBoolean(obj.read_only_default, `${context}.read_only_default`);
  assertBoolean(obj.write_confirmation_required, `${context}.write_confirmation_required`);
  const planLimits = assertJsonObject(obj.plan_limits, `${context}.plan_limits`);
  for (const [planName, limitPayload] of Object.entries(planLimits)) {
    const limits = assertJsonObject(limitPayload, `${context}.plan_limits.${planName}`);
    for (const [limitName, limitValue] of Object.entries(limits)) {
      if (typeof limitValue === "string") {
        if (!limitValue.trim()) {
          throw new DecisionEngineError(
            `${context}.plan_limits.${planName}.${limitName} must be a non-empty string.`,
          );
        }
        continue;
      }
      assertFiniteNumber(limitValue, `${context}.plan_limits.${planName}.${limitName}`);
    }
  }
}

function assertIntegrationContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.name, `${context}.name`);
  assertNonEmptyString(obj.description, `${context}.description`);
  assertNonEmptyString(obj.icon, `${context}.icon`);
  assertStringArray(obj.capabilities, `${context}.capabilities`);
  assertNonEmptyString(obj.auth_scheme, `${context}.auth_scheme`);
  assertStringArray(obj.required_scopes, `${context}.required_scopes`);
  assertBoolean(obj.read_only_default, `${context}.read_only_default`);
  assertStringArray(obj.write_actions, `${context}.write_actions`);
  assertStringArray(obj.admin_controls, `${context}.admin_controls`);
  assertNonEmptyString(obj.docs_url, `${context}.docs_url`);
  assertNonEmptyString(obj.privacy_url, `${context}.privacy_url`);
  assertNonEmptyString(obj.terms_url, `${context}.terms_url`);
  assertNonEmptyString(obj.support_url, `${context}.support_url`);
  assertStringArray(obj.regions, `${context}.regions`);
  assertNonEmptyString(obj.status, `${context}.status`);
}

function assertPrimaryDataQueryApiPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.contract_endpoint, `${context}.contract_endpoint`);
  assertNonEmptyString(obj.discovery_endpoint, `${context}.discovery_endpoint`);
  assertNonEmptyString(obj.summary_endpoint, `${context}.summary_endpoint`);
  assertNonEmptyString(obj.resolve_endpoint, `${context}.resolve_endpoint`);
  assertNonEmptyString(obj.verify_endpoint, `${context}.verify_endpoint`);
  assertNonEmptyString(obj.query_endpoint, `${context}.query_endpoint`);
  assertNonEmptyString(obj.query_batch_endpoint, `${context}.query_batch_endpoint`);
  assertNonEmptyString(obj.query_sql_report_endpoint, `${context}.query_sql_report_endpoint`);
}

function assertGovernedFilterOperatorsPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertStringArray(obj.scalar, `${context}.scalar`);
  assertStringArray(obj.list, `${context}.list`);
  assertStringArray(obj.nullary, `${context}.nullary`);
}

function assertGovernedFilterTypeBehaviorPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertStringArray(obj.boolean, `${context}.boolean`);
  assertStringArray(obj.string, `${context}.string`);
  assertStringArray(obj.numeric, `${context}.numeric`);
  assertStringArray(obj.null_checks, `${context}.null_checks`);
}

function assertGovernedFilterValidationPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertBoolean(obj.requires_selector, `${context}.requires_selector`);
  assertStringArray(obj.scalar_ops_require_value, `${context}.scalar_ops_require_value`);
  assertStringArray(
    obj.list_ops_require_non_empty_values,
    `${context}.list_ops_require_non_empty_values`,
  );
  assertStringArray(
    obj.nullary_ops_forbid_value_and_values,
    `${context}.nullary_ops_forbid_value_and_values`,
  );
}

function assertGovernedFilterContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.kind, `${context}.kind`);
  assertNonEmptyString(obj.time_filter_field, `${context}.time_filter_field`);
  assertNonEmptyString(obj.conditions_field, `${context}.conditions_field`);
  assertStringArray(obj.selector_fields, `${context}.selector_fields`);
  assertGovernedFilterOperatorsPayload(obj.operators, `${context}.operators`);
  assertGovernedFilterTypeBehaviorPayload(obj.type_behavior, `${context}.type_behavior`);
  assertGovernedFilterValidationPayload(obj.validation, `${context}.validation`);
  assertBoolean(obj.applies_before_aggregation, `${context}.applies_before_aggregation`);
  assertBoolean(obj.supports_non_sql_backends, `${context}.supports_non_sql_backends`);
  assertStringArray(obj.notes, `${context}.notes`);
}

function assertDirectPythonSdkContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.import_root, `${context}.import_root`);
  assertNonEmptyString(obj.preferred_client_class, `${context}.preferred_client_class`);
  assertNonEmptyString(
    obj.preferred_async_client_class,
    `${context}.preferred_async_client_class`,
  );
  assertNonEmptyString(obj.compatibility_client_class, `${context}.compatibility_client_class`);
  assertNonEmptyString(
    obj.compatibility_async_client_class,
    `${context}.compatibility_async_client_class`,
  );
  assertNonEmptyString(obj.contract_method, `${context}.contract_method`);
  assertNonEmptyString(obj.discovery_method, `${context}.discovery_method`);
  assertNonEmptyString(obj.summary_method, `${context}.summary_method`);
  assertNonEmptyString(obj.query_with_metadata_method, `${context}.query_with_metadata_method`);
  assertNonEmptyString(obj.query_batch_method, `${context}.query_batch_method`);
  assertNonEmptyString(obj.query_sql_report_method, `${context}.query_sql_report_method`);
}

function assertDirectTypeScriptSdkContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.import_package, `${context}.import_package`);
  assertNonEmptyString(obj.preferred_client_class, `${context}.preferred_client_class`);
  assertNonEmptyString(obj.compatibility_client_class, `${context}.compatibility_client_class`);
  assertNonEmptyString(obj.contract_method, `${context}.contract_method`);
  assertNonEmptyString(obj.discovery_method, `${context}.discovery_method`);
  assertNonEmptyString(obj.summary_method, `${context}.summary_method`);
  assertNonEmptyString(obj.query_with_metadata_method, `${context}.query_with_metadata_method`);
  assertNonEmptyString(obj.query_batch_method, `${context}.query_batch_method`);
  assertNonEmptyString(obj.query_sql_report_method, `${context}.query_sql_report_method`);
}

function assertRuntimePythonSdkContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.import_root, `${context}.import_root`);
  assertNonEmptyString(obj.runtime_class, `${context}.runtime_class`);
  assertNonEmptyString(obj.libraries_entrypoint, `${context}.libraries_entrypoint`);
  assertNonEmptyString(obj.contract_method, `${context}.contract_method`);
  assertNonEmptyString(obj.discovery_method, `${context}.discovery_method`);
  assertNonEmptyString(obj.summary_method, `${context}.summary_method`);
  assertNonEmptyString(obj.query_with_metadata_method, `${context}.query_with_metadata_method`);
  assertNonEmptyString(obj.query_batch_method, `${context}.query_batch_method`);
  assertNonEmptyString(obj.query_sql_report_method, `${context}.query_sql_report_method`);
}

function assertRuntimeTypeScriptSdkContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.import_package, `${context}.import_package`);
  assertNonEmptyString(obj.runtime_class, `${context}.runtime_class`);
  assertNonEmptyString(obj.libraries_entrypoint, `${context}.libraries_entrypoint`);
  assertNonEmptyString(obj.contract_method, `${context}.contract_method`);
  assertNonEmptyString(obj.discovery_method, `${context}.discovery_method`);
  assertNonEmptyString(obj.summary_method, `${context}.summary_method`);
  assertNonEmptyString(obj.query_with_metadata_method, `${context}.query_with_metadata_method`);
  assertNonEmptyString(obj.query_batch_method, `${context}.query_batch_method`);
  assertNonEmptyString(obj.query_sql_report_method, `${context}.query_sql_report_method`);
}

function assertDirectSdkContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertDirectPythonSdkContractPayload(obj.python, `${context}.python`);
  assertDirectTypeScriptSdkContractPayload(obj.typescript, `${context}.typescript`);
}

function assertRuntimeSdkContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertRuntimePythonSdkContractPayload(obj.python, `${context}.python`);
  assertRuntimeTypeScriptSdkContractPayload(obj.typescript, `${context}.typescript`);
}

function assertCliContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.contract_command, `${context}.contract_command`);
  assertNonEmptyString(obj.discovery_command, `${context}.discovery_command`);
  assertNonEmptyString(obj.summary_command, `${context}.summary_command`);
  assertNonEmptyString(obj.query_batch_command, `${context}.query_batch_command`);
  assertNonEmptyString(obj.query_sql_report_command, `${context}.query_sql_report_command`);
  assertNonEmptyString(obj.runtime_modules_command, `${context}.runtime_modules_command`);
  assertNonEmptyString(obj.runtime_functions_command, `${context}.runtime_functions_command`);
  assertNonEmptyString(obj.runtime_execute_command, `${context}.runtime_execute_command`);
}

function assertMcpContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.contract_tool, `${context}.contract_tool`);
  assertNonEmptyString(obj.discovery_tool, `${context}.discovery_tool`);
  assertNonEmptyString(obj.summary_tool, `${context}.summary_tool`);
  assertNonEmptyString(obj.query_tool, `${context}.query_tool`);
  assertNonEmptyString(obj.query_batch_tool, `${context}.query_batch_tool`);
  assertNonEmptyString(obj.query_sql_report_tool, `${context}.query_sql_report_tool`);
  assertNonEmptyString(obj.runtime_library_list_tool, `${context}.runtime_library_list_tool`);
  assertNonEmptyString(
    obj.runtime_library_execute_tool,
    `${context}.runtime_library_execute_tool`,
  );
}

function assertRecommendedFlowsPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertStringArray(obj.machine_readable_contract, `${context}.machine_readable_contract`);
  assertStringArray(obj.governed_query, `${context}.governed_query`);
  assertStringArray(obj.multi_metric_query, `${context}.multi_metric_query`);
  assertStringArray(obj.wide_sql_report, `${context}.wide_sql_report`);
}

function assertPrimaryDataQueryContractPayload(
  payload: unknown,
  context: string,
): PrimaryDataQueryContract {
  const obj = assertJsonObject(payload, context);
  assertPrimaryDataQueryApiPayload(obj.api, `${context}.api`);
  assertGovernedFilterContractPayload(
    obj.governed_filter_contract,
    `${context}.governed_filter_contract`,
  );
  assertDirectSdkContractPayload(obj.direct_sdk, `${context}.direct_sdk`);
  assertRuntimeSdkContractPayload(obj.runtime_sdk, `${context}.runtime_sdk`);
  assertCliContractPayload(obj.cli, `${context}.cli`);
  assertMcpContractPayload(obj.mcp, `${context}.mcp`);
  assertRecommendedFlowsPayload(obj.recommended_flows, `${context}.recommended_flows`);
  return cloneJsonValue(obj) as unknown as PrimaryDataQueryContract;
}

function assertCapabilityPlaneApiContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  [
    "list_providers_endpoint",
    "get_provider_endpoint",
    "list_bindings_endpoint",
    "create_binding_endpoint",
    "get_binding_endpoint",
    "update_binding_endpoint",
    "delete_binding_endpoint",
    "preview_test_binding_endpoint",
    "test_binding_endpoint",
    "preview_discover_binding_endpoint",
    "discover_binding_endpoint",
    "start_authorization_endpoint",
    "complete_authorization_endpoint",
    "list_capabilities_endpoint",
    "get_capability_endpoint",
    "route_capabilities_endpoint",
    "execute_capability_endpoint",
    "record_outcome_endpoint",
  ].forEach(fieldName => assertNonEmptyString(obj[fieldName], `${context}.${fieldName}`));
}

function assertCapabilityPlaneEnumsContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertStringArray(obj.provider_types, `${context}.provider_types`);
  assertStringArray(obj.capability_kinds, `${context}.capability_kinds`);
  assertStringArray(obj.implementation_kinds, `${context}.implementation_kinds`);
  assertStringArray(obj.execution_owners, `${context}.execution_owners`);
  assertStringArray(obj.binding_scopes, `${context}.binding_scopes`);
  assertStringArray(obj.binding_statuses, `${context}.binding_statuses`);
}

function assertCapabilityPlaneTypeScriptSdkContractPayload(
  payload: unknown,
  context: string,
): void {
  const obj = assertJsonObject(payload, context);
  [
    "import_package",
    "preferred_client_class",
    "compatibility_client_class",
    "list_providers_method",
    "get_provider_method",
    "list_bindings_method",
    "create_binding_method",
    "get_binding_method",
    "update_binding_method",
    "delete_binding_method",
    "preview_test_binding_method",
    "test_binding_method",
    "preview_discover_binding_method",
    "discover_binding_method",
    "start_authorization_method",
    "complete_authorization_method",
    "list_capabilities_method",
    "get_capability_method",
    "route_capabilities_method",
    "execute_capability_method",
    "record_outcome_method",
    "list_skills_method",
    "enable_skill_method",
    "disable_skill_method",
    "list_mcp_providers_method",
  ].forEach(fieldName => assertNonEmptyString(obj[fieldName], `${context}.${fieldName}`));
}

function assertCapabilityPlaneRuntimeTypeScriptSdkContractPayload(
  payload: unknown,
  context: string,
): void {
  const obj = assertJsonObject(payload, context);
  [
    "import_package",
    "runtime_class",
    "list_providers_method",
    "list_bindings_method",
    "list_capabilities_method",
    "route_capabilities_method",
    "execute_capability_method",
    "register_adapter_method",
  ].forEach(fieldName => assertNonEmptyString(obj[fieldName], `${context}.${fieldName}`));
}

function assertCapabilityPlaneDirectSdkContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertCapabilityPlaneTypeScriptSdkContractPayload(obj.typescript, `${context}.typescript`);
}

function assertCapabilityPlaneRuntimeSdkContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertCapabilityPlaneRuntimeTypeScriptSdkContractPayload(
    obj.typescript,
    `${context}.typescript`,
  );
}

function assertCapabilityPlaneMcpContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  [
    "list_providers_tool",
    "list_bindings_tool",
    "create_binding_tool",
    "test_binding_tool",
    "discover_binding_tool",
    "list_capabilities_tool",
    "get_capability_tool",
    "route_capabilities_tool",
    "execute_capability_tool",
    "list_skills_tool",
    "enable_skill_tool",
    "disable_skill_tool",
  ].forEach(fieldName => assertNonEmptyString(obj[fieldName], `${context}.${fieldName}`));
  assertStringArray(obj.compatibility_aliases, `${context}.compatibility_aliases`);
}

function assertCapabilityPlaneContractPayload(
  payload: unknown,
  context: string,
): CapabilityPlaneContract {
  const obj = assertJsonObject(payload, context);
  assertCapabilityPlaneApiContractPayload(obj.api, `${context}.api`);
  assertCapabilityPlaneEnumsContractPayload(obj.enums, `${context}.enums`);
  assertCapabilityPlaneDirectSdkContractPayload(obj.direct_sdk, `${context}.direct_sdk`);
  assertCapabilityPlaneRuntimeSdkContractPayload(obj.runtime_sdk, `${context}.runtime_sdk`);
  assertCapabilityPlaneMcpContractPayload(obj.mcp, `${context}.mcp`);
  return cloneJsonValue(obj) as unknown as CapabilityPlaneContract;
}

function assertPlatformContractPayload(
  payload: unknown,
  context: string,
): PlatformContractResponse {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.contract_version, `${context}.contract_version`);
  assertNonEmptyString(obj.brand, `${context}.brand`);
  assertNonEmptyString(obj.api_base_url, `${context}.api_base_url`);
  assertNonEmptyString(obj.mcp_endpoint, `${context}.mcp_endpoint`);
  assertNonEmptyString(obj.mcp_tools_endpoint, `${context}.mcp_tools_endpoint`);
  assertNonEmptyString(obj.auth_scheme, `${context}.auth_scheme`);
  assertApiKeyPrefixes(obj.api_key_prefixes, `${context}.api_key_prefixes`);
  assertCompatibilityContractPayload(obj.compatibility, `${context}.compatibility`);
  assertPrivacyRegistryContractPayload(obj.privacy_registry, `${context}.privacy_registry`);
  assertDefaultsContractPayload(obj.defaults, `${context}.defaults`);
  assertPrimaryDataQueryContractPayload(
    obj.primary_data_query_contract,
    `${context}.primary_data_query_contract`,
  );
  if (obj.capability_plane !== undefined && obj.capability_plane !== null) {
    assertCapabilityPlaneContractPayload(obj.capability_plane, `${context}.capability_plane`);
  }
  assertArray(obj.integrations, `${context}.integrations`).forEach((entry, index) =>
    assertIntegrationContractPayload(entry, `${context}.integrations[${index}]`),
  );
  return cloneJsonValue(obj) as unknown as PlatformContractResponse;
}

function wrapContractValidation<T>(
  context: string,
  payload: unknown,
  validator: (value: unknown) => T,
): T {
  try {
    return validator(payload);
  } catch (error) {
    if (error instanceof DecisionEngineError) {
      const details =
        error.details && typeof error.details === "object" && !Array.isArray(error.details)
          ? error.details
          : { cause: error.message };
      throw new DecisionEngineError(
        `${context} returned an invalid payload: ${error.message}`,
        0,
        "invalid_contract_payload",
        {
          error: {
            code: "invalid_contract_payload",
            details,
          },
        },
      );
    }
    throw error;
  }
}

export function assertPlatformContractResponse(payload: unknown): PlatformContractResponse {
  return wrapContractValidation("Algenta contract endpoint", payload, value =>
    assertPlatformContractPayload(value, "Algenta contract response"),
  );
}

function dedupeStrings(values: string[]): string[] {
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

function sourceSetFromRequest(request: Record<string, unknown>): string[] {
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

function splitResolvedSources(resolvedSource: string | undefined): string[] {
  if (!resolvedSource) return [];
  return dedupeStrings(resolvedSource.split('⋈').map(part => part.trim()));
}

function buildExplainResponse(
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

function assertApiKeyPrefix(payload: unknown, context: string): string {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError(`${context} must be a JSON object.`);
  }
  const keyPrefix = (payload as { key_prefix?: unknown }).key_prefix;
  if (typeof keyPrefix !== "string" || keyPrefix.length === 0) {
    throw new DecisionEngineError(`${context} missing key_prefix.`);
  }
  return keyPrefix;
}

function assertOptionalApiKeyDeviceLimit(payload: unknown, context: string): void {
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

function assertApiKeyListResponse(payload: unknown): APIKeyInfo[] {
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

function assertApiKeyCreateResponse(payload: unknown): APIKeyCreated {
  const keyPrefix = assertApiKeyPrefix(payload, "API key create response");
  assertOptionalApiKeyDeviceLimit(payload, "API key create response");
  const rawKey = (payload as { raw_key?: unknown }).raw_key;
  if (typeof rawKey !== "string" || rawKey.length === 0 || !rawKey.startsWith(keyPrefix)) {
    throw new DecisionEngineError("API key create response missing raw_key.");
  }
  return payload as APIKeyCreated;
}

function assertUsageInfoResponse(payload: unknown): UsageInfo {
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

function assertMeResponse(payload: unknown): MeResponse {
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

function normalizeUpdateMeRequest(request: UpdateMeRequest): Record<string, unknown> {
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

function assertStringArray(value: unknown, context: string): string[] {
  if (!Array.isArray(value) || value.some(item => typeof item !== "string" || item.length === 0)) {
    throw new DecisionEngineError(`${context} must be a list of non-empty strings.`);
  }
  return [...value];
}

function assertJsonRecord(value: unknown, context: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new DecisionEngineError(`${context} must be a JSON object.`);
  }
  return value as Record<string, unknown>;
}

function assertDistributionInfoResponse(payload: unknown): DistributionInfoResponse {
  const data = assertJsonRecord(payload, "Distribution entry");
  return {
    name: assertNonEmptyString(data.name, "Distribution entry.name"),
    description: assertNonEmptyString(data.description, "Distribution entry.description"),
    required_params: assertStringArray(data.required_params, "Distribution entry.required_params"),
    optional_params: assertStringArray(data.optional_params, "Distribution entry.optional_params"),
    example: assertJsonRecord(data.example, "Distribution entry.example"),
  };
}

function assertDistributionListResponse(payload: unknown): DistributionListResponse {
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

function assertTemplateInfoResponse(payload: unknown): TemplateInfoResponse {
  const data = assertJsonRecord(payload, "Template entry");
  return {
    id: assertNonEmptyString(data.id, "Template entry.id"),
    name: assertNonEmptyString(data.name, "Template entry.name"),
    category: assertNonEmptyString(data.category, "Template entry.category"),
    description: assertNonEmptyString(data.description, "Template entry.description"),
    example_request: assertJsonRecord(data.example_request, "Template entry.example_request"),
  };
}

function assertTemplateListResponse(payload: unknown): TemplateListResponse {
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

function assertLimitsInfoResponse(payload: unknown): LimitsInfo {
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

function assertBillingInfoResponse(payload: unknown): BillingInfoResponse {
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

function assertBillingSessionResponse(payload: unknown): BillingSessionResponse {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Billing session response must be a JSON object.");
  }
  const url = (payload as { url?: unknown }).url;
  if (typeof url !== "string" || url.length === 0) {
    throw new DecisionEngineError("Billing session response missing url.");
  }
  return { url };
}

function assertMeteringBatchResponse(payload: unknown): MeteringBatchResponse {
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

function assertCreditRefreshResponse(payload: unknown): CreditRefreshResponse {
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

function assertTeamMemberInfo(payload: unknown): TeamMemberInfo {
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

function assertTeamListResponse(payload: unknown): TeamListResponse {
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

function assertTeamInviteResponse(payload: unknown): TeamInviteResponse {
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

function assertTeamRoleUpdateResponse(payload: unknown): TeamRoleUpdateResponse {
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

function assertTeamRemoveResponse(payload: unknown, userId: string): TeamRemoveResponse {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError("Team remove response must be a JSON object.");
  }
  const data = payload as Record<string, unknown>;
  return {
    removed: typeof data.removed === "boolean" ? data.removed : true,
    user_id: typeof data.user_id === "string" && data.user_id.length > 0 ? data.user_id : userId,
  };
}

function assertDeviceRegistrationResponse(
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

function assertDeviceListEntryResponse(payload: unknown): DeviceListEntryResponse {
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

function assertDeviceListResponse(payload: unknown): DeviceListResponse {
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

function assertDeviceRevokeResponse(payload: unknown): DeviceRevokeResponse {
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

function assertAuditLogEntry(payload: unknown): AuditLogEntry {
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

function assertAuditLogResponse(payload: unknown): AuditLogResponse {
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

function assertExecutionPolicyResponse(payload: unknown): ExecutionPolicyResponse {
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

function assertExecutionPolicySnapshotListResponse(payload: unknown): ExecutionPolicySnapshotListResponse {
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

function normalizeUpdateExecutionPolicyRequest(
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

function normalizeMeteringBatchRequest(request: MeteringBatchRequest): Record<string, unknown> {
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

function normalizeCreditRefreshRequest(request: CreditRefreshRequest): Record<string, unknown> {
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

function normalizeTeamInviteRequest(request: TeamInviteRequest): Record<string, unknown> {
  if (!request || typeof request !== "object" || Array.isArray(request)) {
    throw new DecisionEngineError("Team invite request must be a JSON object.");
  }
  if (typeof request.email !== "string" || request.email.trim().length === 0 || !request.email.includes("@")) {
    throw new DecisionEngineError("Team invite request requires a valid email.");
  }
  const role = normalizeTeamRole(request.role ?? "member", "inviteTeamMember");
  return { email: request.email.trim(), role };
}

function normalizeTeamRole(role: unknown, methodName: string): "owner" | "admin" | "member" | "viewer" {
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

function normalizeApiKeyCreateRequest(request: CreateAPIKeyRequest): Record<string, unknown> {
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

function assertDeploymentRegionsResponse(payload: unknown): DeploymentRegionsResponse {
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

function assertDeploymentResponse(payload: unknown, context: string): DeploymentResponse {
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

function normalizeCreateDeploymentRequest(request: CreateDeploymentRequest = {}): Record<string, unknown> {
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

function assertDeploymentDeleteResponse(payload: unknown): DeploymentDeleteResponse {
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

function assertDeploymentCostResponse(payload: unknown): DeploymentCostResponse {
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

function assertConnectorListResponse(
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

function assertDatasetListResponse(
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

function assertDatasetSummaryResponse(payload: unknown): DatasetSummaryResult {
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

function normalizeValidationPath(context: string): string {
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

function buildStructuredValidationError(
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

function assertJsonObject(payload: unknown, context: string): Record<string, unknown> {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw buildStructuredValidationError(
      context,
      `${context} must be a JSON object.`,
      "model_type",
    );
  }
  return payload as Record<string, unknown>;
}

function assertNonEmptyString(value: unknown, context: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw buildStructuredValidationError(
      context,
      `${context} must be a non-empty string.`,
      "string_type",
    );
  }
  return value;
}

function assertFiniteNumber(value: unknown, context: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw buildStructuredValidationError(
      context,
      `${context} must be a finite number.`,
      "finite_number",
    );
  }
  return value;
}

function assertInteger(value: unknown, context: string): number {
  if (!Number.isInteger(value)) {
    throw buildStructuredValidationError(
      context,
      `${context} must be an integer.`,
      "integer_type",
    );
  }
  return Number(value);
}

function assertBoolean(value: unknown, context: string): boolean {
  if (typeof value !== "boolean") {
    throw buildStructuredValidationError(
      context,
      `${context} must be a boolean.`,
      "bool_type",
    );
  }
  return value;
}

function assertArray(value: unknown, context: string): unknown[] {
  if (!Array.isArray(value)) {
    throw buildStructuredValidationError(
      context,
      `${context} must be a JSON array.`,
      "array_type",
    );
  }
  return value;
}

function assertEnumValue<T extends string>(
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

function assertEnumArray<T extends string>(
  value: unknown,
  allowedValues: readonly T[],
  context: string,
): T[] {
  return assertArray(value, context).map((entry, index) =>
    assertEnumValue(entry, allowedValues, `${context}[${index}]`),
  );
}

function assertUniqueRuntimeValues(values: readonly string[], context: string): void {
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

function assertUniqueRuntimeObjectField(
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

function assertEnumKeyedCountRecord<T extends string>(
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

function assertEnumKeyedEnumRecord<TKey extends string, TValue extends string>(
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

function assertRuntimeSignature(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertEnumValue(obj.algorithm, RUNTIME_SIGNATURE_ALGORITHM_VALUES, `${context}.algorithm`);
  assertNonEmptyString(obj.key_id, `${context}.key_id`);
  assertNonEmptyString(obj.digest_hex, `${context}.digest_hex`);
  assertNonEmptyString(obj.signature_hex, `${context}.signature_hex`);
  assertEnumValue(obj.scope, RUNTIME_SIGNATURE_SCOPE_VALUES, `${context}.scope`);
}

function assertRuntimeSnapshotReference(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.snapshot_id, `${context}.snapshot_id`);
  assertNonEmptyString(obj.sha256, `${context}.sha256`);
  assertNonEmptyString(obj.source, `${context}.source`);
  assertNonEmptyString(obj.description, `${context}.description`);
}

function assertRuntimeArtifactReference(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertEnumValue(obj.kind, RUNTIME_ARTIFACT_KIND_VALUES, `${context}.kind`);
  assertNonEmptyString(obj.path, `${context}.path`);
  assertNonEmptyString(obj.sha256, `${context}.sha256`);
  assertInteger(obj.size_bytes, `${context}.size_bytes`);
}

function assertRuntimeShippingContractSummary(
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

function assertRuntimeBenchmarkDiscoveryLane(
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

function assertRuntimeModuleManifestEntry(
  payload: unknown,
  context: string,
): {
  name: RuntimeModuleId;
  functionCount: number;
  functions: string[];
  layer: RuntimeLayer;
  maturity: RuntimeMaturity;
  benchmarkSpeedupX: number;
  promotionStatus: "candidate" | "shipping";
} {
  const obj = assertJsonObject(payload, context);
  const name = assertEnumValue(obj.name, RUNTIME_MODULE_ID_VALUES, `${context}.name`);
  assertNonEmptyString(obj.capability_id, `${context}.capability_id`);
  assertNonEmptyString(obj.owner, `${context}.owner`);
  assertNonEmptyString(obj.contract_boundary, `${context}.contract_boundary`);
  const functionCount = assertInteger(obj.function_count, `${context}.function_count`);
  const functions = assertStringArray(obj.functions, `${context}.functions`);
  assertUniqueRuntimeValues(functions, `${context}.functions`);
  if (functions.length !== functionCount) {
    throw buildStructuredValidationError(
      `${context}.functions`,
      `${context}.functions must contain exactly ${functionCount} entries to match function_count.`,
      "value_error",
    );
  }
  const layer = assertEnumValue(obj.layer, RUNTIME_LAYER_VALUES, `${context}.layer`);
  const maturity = assertEnumValue(obj.maturity, RUNTIME_MATURITY_VALUES, `${context}.maturity`);
  const publicSupportedChannels = assertEnumArray(
    obj.public_supported_channels,
    RUNTIME_SUPPORTED_CHANNEL_VALUES,
    `${context}.public_supported_channels`,
  );
  assertUniqueRuntimeValues(publicSupportedChannels, `${context}.public_supported_channels`);
  const validatedAuxiliaryChannels = assertEnumArray(
    obj.validated_auxiliary_channels,
    RUNTIME_AUXILIARY_CHANNEL_VALUES,
    `${context}.validated_auxiliary_channels`,
  );
  assertUniqueRuntimeValues(
    validatedAuxiliaryChannels,
    `${context}.validated_auxiliary_channels`,
  );
  const featureFlagChannels = assertEnumArray(
    obj.feature_flag_channels,
    RUNTIME_FEATURE_FLAG_CHANNEL_VALUES,
    `${context}.feature_flag_channels`,
  );
  assertUniqueRuntimeValues(featureFlagChannels, `${context}.feature_flag_channels`);
  const proofObligations = assertEnumArray(
    obj.proof_obligations,
    RUNTIME_PROOF_OBLIGATION_VALUES,
    `${context}.proof_obligations`,
  );
  assertUniqueRuntimeValues(proofObligations, `${context}.proof_obligations`);
  const proofArtifacts = assertStringArray(obj.proof_artifacts, `${context}.proof_artifacts`);
  assertUniqueRuntimeValues(proofArtifacts, `${context}.proof_artifacts`);
  const promotionStatus = assertEnumValue(
    obj.promotion_status,
    RUNTIME_KERNEL_PROMOTION_STATUS_VALUES,
    `${context}.promotion_status`,
  );
  assertNonEmptyString(obj.rollback_flag, `${context}.rollback_flag`);
  assertNonEmptyString(obj.benchmark_report_ref, `${context}.benchmark_report_ref`);
  assertNonEmptyString(obj.parity_report_ref, `${context}.parity_report_ref`);
  assertNonEmptyString(obj.schema_compat_report_ref, `${context}.schema_compat_report_ref`);
  assertNonEmptyString(obj.isolation_proof_ref, `${context}.isolation_proof_ref`);
  assertNonEmptyString(obj.replay_proof_ref, `${context}.replay_proof_ref`);
  assertNonEmptyString(obj.benchmark_artifact, `${context}.benchmark_artifact`);
  const benchmarkSpeedupX = assertFiniteNumber(
    obj.benchmark_speedup_x,
    `${context}.benchmark_speedup_x`,
  );
  assertNonEmptyString(obj.compiled_artifact, `${context}.compiled_artifact`);
  assertEnumValue(obj.compiled_engine, RUNTIME_COMPILED_ENGINE_VALUES, `${context}.compiled_engine`);
  assertFiniteNumber(obj.max_cold_ms, `${context}.max_cold_ms`);
  assertFiniteNumber(obj.max_warm_ms, `${context}.max_warm_ms`);
  assertFiniteNumber(obj.max_hot_ms, `${context}.max_hot_ms`);
  return { name, functionCount, functions, layer, maturity, benchmarkSpeedupX, promotionStatus };
}

function assertRuntimeAdvertisedCapabilities(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const runtimeModules = assertEnumArray(
    obj.runtime_modules,
    RUNTIME_MODULE_ID_VALUES,
    `${context}.runtime_modules`,
  );
  assertUniqueRuntimeValues(runtimeModules, `${context}.runtime_modules`);
  const publicEndpoints = assertEnumArray(
    obj.public_endpoints,
    RUNTIME_PUBLIC_ENDPOINT_VALUES,
    `${context}.public_endpoints`,
  );
  assertUniqueRuntimeValues(publicEndpoints, `${context}.public_endpoints`);
  const adminEndpoints = assertEnumArray(
    obj.admin_endpoints,
    RUNTIME_ADMIN_ENDPOINT_VALUES,
    `${context}.admin_endpoints`,
  );
  assertUniqueRuntimeValues(adminEndpoints, `${context}.admin_endpoints`);
  const featureFlagEndpoints = assertEnumArray(
    obj.feature_flag_endpoints,
    RUNTIME_FEATURE_FLAG_ENDPOINT_VALUES,
    `${context}.feature_flag_endpoints`,
  );
  assertUniqueRuntimeValues(featureFlagEndpoints, `${context}.feature_flag_endpoints`);
}

function assertRuntimeNamedRule(
  payload: unknown,
  context: string,
  allowedNames: readonly string[],
  nameField: string,
): void {
  const obj = assertJsonObject(payload, context);
  assertEnumValue(obj[nameField], allowedNames, `${context}.${nameField}`);
  assertNonEmptyString(obj.statement, `${context}.statement`);
}

function assertRuntimeExecutionModel(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const stateFields = assertEnumArray(
    obj.state_fields,
    RUNTIME_EXECUTION_STATE_FIELD_VALUES,
    `${context}.state_fields`,
  );
  assertUniqueRuntimeValues(stateFields, `${context}.state_fields`);
  const allowedTransitions = assertEnumArray(
    obj.allowed_transitions,
    RUNTIME_EXECUTION_TRANSITION_VALUES,
    `${context}.allowed_transitions`,
  );
  assertUniqueRuntimeValues(allowedTransitions, `${context}.allowed_transitions`);
  const validityRules = assertEnumArray(
    obj.validity_rules,
    RUNTIME_EXECUTION_VALIDITY_RULE_VALUES,
    `${context}.validity_rules`,
  );
  assertUniqueRuntimeValues(validityRules, `${context}.validity_rules`);
}

function assertRuntimeExternalNondeterminismPolicy(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const sources = assertEnumArray(
    obj.sources,
    RUNTIME_EXTERNAL_NONDETERMINISM_SOURCE_VALUES,
    `${context}.sources`,
  );
  assertUniqueRuntimeValues(sources, `${context}.sources`);
  assertNonEmptyString(obj.rule, `${context}.rule`);
  const requiredArtifacts = assertEnumArray(
    obj.required_artifacts,
    RUNTIME_NONDETERMINISM_ARTIFACT_VALUES,
    `${context}.required_artifacts`,
  );
  assertUniqueRuntimeValues(requiredArtifacts, `${context}.required_artifacts`);
  const failureCodes = assertEnumArray(
    obj.failure_codes,
    RUNTIME_FAILURE_CODE_VALUES,
    `${context}.failure_codes`,
  );
  assertUniqueRuntimeValues(failureCodes, `${context}.failure_codes`);
}

function assertRuntimeArtifactLineageSchema(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const artifactFlow = assertEnumArray(
    obj.artifact_flow,
    RUNTIME_ARTIFACT_LINEAGE_STEP_VALUES,
    `${context}.artifact_flow`,
  );
  assertUniqueRuntimeValues(artifactFlow, `${context}.artifact_flow`);
  const requiredNodeFields = assertEnumArray(
    obj.required_node_fields,
    RUNTIME_LINEAGE_NODE_FIELD_VALUES,
    `${context}.required_node_fields`,
  );
  assertUniqueRuntimeValues(requiredNodeFields, `${context}.required_node_fields`);
  assertNonEmptyString(obj.immutability_rule, `${context}.immutability_rule`);
}

function assertRuntimeCapabilityAlgebra(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const requiredFields = assertEnumArray(
    obj.required_fields,
    RUNTIME_CAPABILITY_FIELD_VALUES,
    `${context}.required_fields`,
  );
  assertUniqueRuntimeValues(requiredFields, `${context}.required_fields`);
  const enums = assertJsonObject(obj.enums, `${context}.enums`);
  const sideEffectClass = assertEnumArray(
    enums.side_effect_class,
    RUNTIME_SIDE_EFFECT_CLASS_VALUES,
    `${context}.enums.side_effect_class`,
  );
  assertUniqueRuntimeValues(sideEffectClass, `${context}.enums.side_effect_class`);
  const riskLevels = assertEnumArray(
    enums.risk_level,
    RUNTIME_RISK_LEVEL_VALUES,
    `${context}.enums.risk_level`,
  );
  assertUniqueRuntimeValues(riskLevels, `${context}.enums.risk_level`);
  const replayability = assertEnumArray(
    enums.replayability,
    RUNTIME_REPLAYABILITY_VALUES,
    `${context}.enums.replayability`,
  );
  assertUniqueRuntimeValues(replayability, `${context}.enums.replayability`);
  const rules = assertEnumArray(obj.rules, RUNTIME_CAPABILITY_RULE_VALUES, `${context}.rules`);
  assertUniqueRuntimeValues(rules, `${context}.rules`);
}

function assertRuntimeKernelPromotionCriteria(payload: unknown, context: string): {
  minimumPrimaryMetricImprovementPct: number;
} {
  const obj = assertJsonObject(payload, context);
  const requiredManifestFields = assertStringArray(
    obj.required_manifest_fields,
    `${context}.required_manifest_fields`,
  );
  assertUniqueRuntimeValues(requiredManifestFields, `${context}.required_manifest_fields`);
  const requiredProofReferenceFields = assertStringArray(
    obj.required_proof_reference_fields,
    `${context}.required_proof_reference_fields`,
  );
  assertUniqueRuntimeValues(
    requiredProofReferenceFields,
    `${context}.required_proof_reference_fields`,
  );
  assertNonEmptyString(
    obj.deterministic_test_corpus_rule,
    `${context}.deterministic_test_corpus_rule`,
  );
  assertNonEmptyString(obj.python_parity_rule, `${context}.python_parity_rule`);
  assertNonEmptyString(
    obj.schema_compatibility_rule,
    `${context}.schema_compatibility_rule`,
  );
  const minimumPrimaryMetricImprovementPct = assertFiniteNumber(
    obj.minimum_primary_metric_improvement_pct,
    `${context}.minimum_primary_metric_improvement_pct`,
  );
  const maximumAdjacentMetricRegressionPct = assertFiniteNumber(
    obj.maximum_adjacent_metric_regression_pct,
    `${context}.maximum_adjacent_metric_regression_pct`,
  );
  if (minimumPrimaryMetricImprovementPct <= 0) {
    throw buildStructuredValidationError(
      `${context}.minimum_primary_metric_improvement_pct`,
      `${context}.minimum_primary_metric_improvement_pct must be greater than 0.`,
      "value_error",
    );
  }
  if (maximumAdjacentMetricRegressionPct < 0) {
    throw buildStructuredValidationError(
      `${context}.maximum_adjacent_metric_regression_pct`,
      `${context}.maximum_adjacent_metric_regression_pct must be greater than or equal to 0.`,
      "value_error",
    );
  }
  assertNonEmptyString(obj.benchmark_exception_rule, `${context}.benchmark_exception_rule`);
  assertNonEmptyString(obj.rollback_scope_rule, `${context}.rollback_scope_rule`);
  assertNonEmptyString(obj.tenant_isolation_rule, `${context}.tenant_isolation_rule`);
  assertNonEmptyString(
    obj.replay_compatibility_rule,
    `${context}.replay_compatibility_rule`,
  );
  return { minimumPrimaryMetricImprovementPct };
}

function assertRuntimeLayerProofMatrixEntry(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertEnumValue(obj.layer, RUNTIME_LAYER_VALUES, `${context}.layer`);
  assertEnumValue(obj.status, RUNTIME_MATURITY_VALUES, `${context}.status`);
  const obligations = assertEnumArray(
    obj.obligations,
    RUNTIME_PROOF_OBLIGATION_VALUES,
    `${context}.obligations`,
  );
  assertUniqueRuntimeValues(obligations, `${context}.obligations`);
  const evidencePaths = assertStringArray(obj.evidence_paths, `${context}.evidence_paths`);
  assertUniqueRuntimeValues(evidencePaths, `${context}.evidence_paths`);
}

function assertRuntimeBenchmarkFramework(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const classes = assertArray(obj.classes, `${context}.classes`);
  classes.forEach((entry, index) => {
    const benchmarkClass = assertJsonObject(entry, `${context}.classes[${index}]`);
    assertEnumValue(benchmarkClass.code, RUNTIME_BENCHMARK_CLASS_VALUES, `${context}.classes[${index}].code`);
    assertNonEmptyString(benchmarkClass.description, `${context}.classes[${index}].description`);
  });
  assertUniqueRuntimeObjectField(classes, "code", `${context}.classes`);
  const requiredMetrics = assertEnumArray(
    obj.required_metrics,
    RUNTIME_BENCHMARK_METRIC_VALUES,
    `${context}.required_metrics`,
  );
  assertUniqueRuntimeValues(requiredMetrics, `${context}.required_metrics`);
  const baselines = assertEnumArray(
    obj.baselines,
    RUNTIME_BENCHMARK_BASELINE_VALUES,
    `${context}.baselines`,
  );
  assertUniqueRuntimeValues(baselines, `${context}.baselines`);
}

function assertRuntimeSLOBudget(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertEnumValue(obj.name, RUNTIME_SLO_BUDGET_NAME_VALUES, `${context}.name`);
  assertEnumValue(obj.applies_to, RUNTIME_SLO_BUDGET_APPLIES_TO_VALUES, `${context}.applies_to`);
  assertFiniteNumber(obj.p95_objective_ms, `${context}.p95_objective_ms`);
  if (obj.hard_ceiling_ms !== undefined && obj.hard_ceiling_ms !== null) {
    assertFiniteNumber(obj.hard_ceiling_ms, `${context}.hard_ceiling_ms`);
  }
  if (obj.notes !== undefined && obj.notes !== null) {
    assertNonEmptyString(obj.notes, `${context}.notes`);
  }
}

function assertRuntimeSchedulerModel(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const policies = assertEnumArray(
    obj.policies,
    RUNTIME_SCHEDULER_POLICY_VALUES,
    `${context}.policies`,
  );
  assertUniqueRuntimeValues(policies, `${context}.policies`);
  const minimize = assertEnumArray(
    obj.minimize,
    RUNTIME_SCHEDULER_MINIMIZE_VALUES,
    `${context}.minimize`,
  );
  assertUniqueRuntimeValues(minimize, `${context}.minimize`);
  const maximize = assertEnumArray(
    obj.maximize,
    RUNTIME_SCHEDULER_MAXIMIZE_VALUES,
    `${context}.maximize`,
  );
  assertUniqueRuntimeValues(maximize, `${context}.maximize`);
  const invariants = assertEnumArray(
    obj.invariants,
    RUNTIME_SCHEDULER_INVARIANT_VALUES,
    `${context}.invariants`,
  );
  assertUniqueRuntimeValues(invariants, `${context}.invariants`);
}

function assertRuntimeMemoryModel(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const regions = assertEnumArray(obj.regions, RUNTIME_MEMORY_REGION_VALUES, `${context}.regions`);
  assertUniqueRuntimeValues(regions, `${context}.regions`);
  const rules = assertEnumArray(obj.rules, RUNTIME_MEMORY_RULE_VALUES, `${context}.rules`);
  assertUniqueRuntimeValues(rules, `${context}.rules`);
  const failureCodes = assertEnumArray(
    obj.failure_codes,
    RUNTIME_FAILURE_CODE_VALUES,
    `${context}.failure_codes`,
  );
  assertUniqueRuntimeValues(failureCodes, `${context}.failure_codes`);
}

function assertRuntimeEvaluationScience(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const dimensions = assertEnumArray(
    obj.dimensions,
    RUNTIME_EVALUATION_DIMENSION_VALUES,
    `${context}.dimensions`,
  );
  assertUniqueRuntimeValues(dimensions, `${context}.dimensions`);
  const methods = assertEnumArray(
    obj.methods,
    RUNTIME_EVALUATION_METHOD_VALUES,
    `${context}.methods`,
  );
  assertUniqueRuntimeValues(methods, `${context}.methods`);
  const releaseBlockers = assertEnumArray(
    obj.release_blockers,
    RUNTIME_RELEASE_BLOCKER_VALUES,
    `${context}.release_blockers`,
  );
  assertUniqueRuntimeValues(releaseBlockers, `${context}.release_blockers`);
}

function assertRuntimeAdminEvaluationSummary(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertInteger(obj.dimension_count, `${context}.dimension_count`);
  assertInteger(obj.method_count, `${context}.method_count`);
  assertInteger(obj.release_blocker_count, `${context}.release_blocker_count`);
  assertInteger(obj.benchmark_class_count, `${context}.benchmark_class_count`);
  assertInteger(obj.slo_budget_count, `${context}.slo_budget_count`);
  assertBoolean(obj.replay_gate_enabled, `${context}.replay_gate_enabled`);
  assertBoolean(
    obj.tool_call_quality_gate_enabled,
    `${context}.tool_call_quality_gate_enabled`,
  );
  assertBoolean(obj.rag_quality_gate_enabled, `${context}.rag_quality_gate_enabled`);
  assertBoolean(
    obj.decision_quality_gate_enabled,
    `${context}.decision_quality_gate_enabled`,
  );
}

function assertRuntimeTypedFailure(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertEnumValue(obj.code, RUNTIME_FAILURE_CODE_VALUES, `${context}.code`);
  assertNonEmptyString(obj.description, `${context}.description`);
}

function assertRuntimeThreatModel(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const threatClasses = assertEnumArray(
    obj.threat_classes,
    RUNTIME_THREAT_CLASS_VALUES,
    `${context}.threat_classes`,
  );
  assertUniqueRuntimeValues(threatClasses, `${context}.threat_classes`);
  const controls = assertEnumArray(
    obj.controls,
    RUNTIME_THREAT_CONTROL_VALUES,
    `${context}.controls`,
  );
  assertUniqueRuntimeValues(controls, `${context}.controls`);
  const nonNegotiableRules = assertEnumArray(
    obj.non_negotiable_rules,
    RUNTIME_THREAT_RULE_VALUES,
    `${context}.non_negotiable_rules`,
  );
  assertUniqueRuntimeValues(nonNegotiableRules, `${context}.non_negotiable_rules`);
}

function assertRuntimeFormalReleaseTheorem(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.statement, `${context}.statement`);
  const requiredConditions = assertEnumArray(
    obj.required_conditions,
    RUNTIME_RELEASE_CONDITION_VALUES,
    `${context}.required_conditions`,
  );
  assertUniqueRuntimeValues(requiredConditions, `${context}.required_conditions`);
}

function assertRuntimeReleaseArtifactBundle(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  const requiredArtifacts = assertEnumArray(
    obj.required_artifacts,
    RUNTIME_RELEASE_ARTIFACT_VALUES,
    `${context}.required_artifacts`,
  );
  assertUniqueRuntimeValues(requiredArtifacts, `${context}.required_artifacts`);
}

function assertRuntimeReleaseGate(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertEnumValue(obj.gate, RUNTIME_RELEASE_GATE_VALUES, `${context}.gate`);
  assertNonEmptyString(obj.description, `${context}.description`);
}

function assertRuntimeImplementationStep(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.pr, `${context}.pr`);
  assertNonEmptyString(obj.focus, `${context}.focus`);
  assertStringArray(obj.deliverables, `${context}.deliverables`);
}

function assertRuntimeDeploymentModes(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertEnumValue(obj.current, RUNTIME_DEPLOYMENT_MODE_VALUES, `${context}.current`);
  const supportedModes = assertEnumArray(
    obj.supported_modes,
    RUNTIME_DEPLOYMENT_MODE_VALUES,
    `${context}.supported_modes`,
  );
  assertUniqueRuntimeValues(supportedModes, `${context}.supported_modes`);
  assertNonEmptyString(obj.rule, `${context}.rule`);
}

function assertRuntimeAdminModuleSummary(
  payload: unknown,
  context: string,
): {
  moduleCount: number;
  functionCount: number;
  maturityCounts: Partial<Record<RuntimeMaturity, number>>;
  layerCounts: Partial<Record<RuntimeLayer, number>>;
} {
  const obj = assertJsonObject(payload, context);
  const moduleCount = assertInteger(obj.module_count, `${context}.module_count`);
  const functionCount = assertInteger(obj.function_count, `${context}.function_count`);
  const maturityCounts = assertEnumKeyedCountRecord(
    obj.maturity_counts,
    RUNTIME_MATURITY_VALUES,
    `${context}.maturity_counts`,
  );
  const layerCounts = assertEnumKeyedCountRecord(
    obj.layer_counts,
    RUNTIME_LAYER_VALUES,
    `${context}.layer_counts`,
  );
  return { moduleCount, functionCount, maturityCounts, layerCounts };
}

function countRuntimeValues(values: readonly string[]): Record<string, number> {
  return values.reduce<Record<string, number>>((counts, value) => {
    counts[value] = (counts[value] ?? 0) + 1;
    return counts;
  }, {});
}

function assertCountRecordMatches(
  actual: Partial<Record<string, number>>,
  expected: Record<string, number>,
  context: string,
  label: string,
): void {
  const actualKeys = Object.keys(actual).sort();
  const expectedKeys = Object.keys(expected).sort();
  if (
    actualKeys.length !== expectedKeys.length ||
    actualKeys.some((key, index) => key !== expectedKeys[index]) ||
    expectedKeys.some(key => actual[key] !== expected[key])
  ) {
    throw buildStructuredValidationError(
      context,
      `${context} must equal the module ${label} distribution.`,
      "value_error",
    );
  }
}

function assertRuntimeBenchmarkModuleEntry(
  payload: unknown,
  context: string,
): {
  name: RuntimeModuleId;
  functionCount: number;
  benchmarkArtifact: string;
  benchmarkSpeedupX: number;
  compiledArtifact: string;
  compiledEngine: RuntimeCompiledEngine;
  maxColdMs: number;
  maxWarmMs: number;
  maxHotMs: number;
} {
  const obj = assertJsonObject(payload, context);
  const name = assertEnumValue(obj.name, RUNTIME_MODULE_ID_VALUES, `${context}.name`);
  const functionCount = assertInteger(obj.function_count, `${context}.function_count`);
  const benchmarkArtifact = assertNonEmptyString(
    obj.benchmark_artifact,
    `${context}.benchmark_artifact`,
  );
  const benchmarkSpeedupX = assertFiniteNumber(obj.benchmark_speedup_x, `${context}.benchmark_speedup_x`);
  const compiledArtifact = assertNonEmptyString(
    obj.compiled_artifact,
    `${context}.compiled_artifact`,
  );
  const compiledEngine = assertEnumValue(
    obj.compiled_engine,
    RUNTIME_COMPILED_ENGINE_VALUES,
    `${context}.compiled_engine`,
  );
  const maxColdMs = assertFiniteNumber(obj.max_cold_ms, `${context}.max_cold_ms`);
  const maxWarmMs = assertFiniteNumber(obj.max_warm_ms, `${context}.max_warm_ms`);
  const maxHotMs = assertFiniteNumber(obj.max_hot_ms, `${context}.max_hot_ms`);
  return {
    name,
    functionCount,
    benchmarkArtifact,
    benchmarkSpeedupX,
    compiledArtifact,
    compiledEngine,
    maxColdMs,
    maxWarmMs,
    maxHotMs,
  };
}

function assertRuntimeBenchmarkClassEntry(
  payload: unknown,
  context: string,
): {
  code: RuntimeBenchmarkClassCode;
  description: string;
  evidence_paths: string[];
} {
  const obj = assertJsonObject(payload, context);
  const code = assertEnumValue(obj.code, RUNTIME_BENCHMARK_CLASS_VALUES, `${context}.code`);
  const description = assertNonEmptyString(obj.description, `${context}.description`);
  const evidencePaths =
    obj.evidence_paths === undefined
      ? []
      : assertStringArray(obj.evidence_paths, `${context}.evidence_paths`);
  assertUniqueRuntimeValues(evidencePaths, `${context}.evidence_paths`);
  return { code, description, evidence_paths: evidencePaths };
}

function assertRuntimeReleaseConditionEvaluation(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertEnumValue(obj.condition, RUNTIME_RELEASE_CONDITION_VALUES, `${context}.condition`);
  assertBoolean(obj.satisfied, `${context}.satisfied`);
  assertNonEmptyString(obj.detail, `${context}.detail`);
  const evidencePaths = assertStringArray(obj.evidence_paths, `${context}.evidence_paths`);
  assertUniqueRuntimeValues(evidencePaths, `${context}.evidence_paths`);
}

function wrapRuntimeValidation<T>(
  context: string,
  payload: unknown,
  validator: (value: unknown) => T,
): T {
  try {
    return validator(payload);
  } catch (error) {
    if (error instanceof DecisionEngineError) {
      const details =
        error.details && typeof error.details === "object" && !Array.isArray(error.details)
          ? error.details
          : { cause: error.message };
      throw new DecisionEngineError(
        `${context} returned an invalid signed payload: ${error.message}`,
        0,
        "invalid_runtime_contract_payload",
        {
          error: {
            code: "invalid_runtime_contract_payload",
            details,
          },
        },
      );
    }
    throw error;
  }
}

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

export function assertRuntimeAdminModulesResponse(payload: unknown): RuntimeAdminModulesResponse {
  return wrapRuntimeValidation("Algenta runtime admin modules endpoint", payload, value => {
    const obj = assertJsonObject(value, "Algenta runtime admin modules response");
    assertNonEmptyString(obj.runtime_version, "Algenta runtime admin modules response.runtime_version");
    assertNonEmptyString(obj.llm_core_manifest, "Algenta runtime admin modules response.llm_core_manifest");
    assertNonEmptyString(
      obj.module_manifest_version,
      "Algenta runtime admin modules response.module_manifest_version",
    );
    const shippingContract = assertRuntimeShippingContractSummary(
      obj.shipping_contract,
      "Algenta runtime admin modules response.shipping_contract",
    );
    const summary = assertRuntimeAdminModuleSummary(
      obj.summary,
      "Algenta runtime admin modules response.summary",
    );
    const proofMatrix = assertArray(
      obj.proof_matrix,
      "Algenta runtime admin modules response.proof_matrix",
    );
    proofMatrix.forEach((entry, index) =>
        assertRuntimeLayerProofMatrixEntry(
          entry,
          `Algenta runtime admin modules response.proof_matrix[${index}]`,
        ),
    );
    assertUniqueRuntimeObjectField(
      proofMatrix,
      "layer",
      "Algenta runtime admin modules response.proof_matrix",
    );
    const modules = assertArray(obj.modules, "Algenta runtime admin modules response.modules");
    const validatedModules = modules.map((entry, index) =>
      assertRuntimeModuleManifestEntry(
        entry,
        `Algenta runtime admin modules response.modules[${index}]`,
      ),
    );
    assertUniqueRuntimeValues(
      validatedModules.map(entry => entry.name),
      "Algenta runtime admin modules response.modules",
    );
    assertNonEmptyString(obj.manifest_digest, "Algenta runtime admin modules response.manifest_digest");
    assertRuntimeSignature(obj.signature, "Algenta runtime admin modules response.signature");
    const totalFunctions = validatedModules.reduce((sum, entry) => sum + entry.functionCount, 0);
    if (shippingContract.moduleCount !== validatedModules.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin modules response.shipping_contract.module_count",
        "Algenta runtime admin modules response.shipping_contract.module_count must equal the number of manifest modules.",
        "value_error",
      );
    }
    if (shippingContract.functionCount !== totalFunctions) {
      throw buildStructuredValidationError(
        "Algenta runtime admin modules response.shipping_contract.function_count",
        "Algenta runtime admin modules response.shipping_contract.function_count must equal the total module function_count.",
        "value_error",
      );
    }
    if (summary.moduleCount !== validatedModules.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin modules response.summary.module_count",
        "Algenta runtime admin modules response.summary.module_count must equal the number of manifest modules.",
        "value_error",
      );
    }
    if (summary.functionCount !== totalFunctions) {
      throw buildStructuredValidationError(
        "Algenta runtime admin modules response.summary.function_count",
        "Algenta runtime admin modules response.summary.function_count must equal the total module function_count.",
        "value_error",
      );
    }
    assertCountRecordMatches(
      summary.maturityCounts,
      countRuntimeValues(validatedModules.map(entry => entry.maturity)),
      "Algenta runtime admin modules response.summary.maturity_counts",
      "maturity",
    );
    assertCountRecordMatches(
      summary.layerCounts,
      countRuntimeValues(validatedModules.map(entry => entry.layer)),
      "Algenta runtime admin modules response.summary.layer_counts",
      "layer",
    );
    return value as RuntimeAdminModulesResponse;
  });
}

export function assertRuntimeAdminBenchmarksResponse(payload: unknown): RuntimeAdminBenchmarksResponse {
  return wrapRuntimeValidation("Algenta runtime admin benchmarks endpoint", payload, value => {
    const obj = assertJsonObject(value, "Algenta runtime admin benchmarks response");
    assertNonEmptyString(
      obj.runtime_version,
      "Algenta runtime admin benchmarks response.runtime_version",
    );
    assertNonEmptyString(
      obj.llm_core_manifest,
      "Algenta runtime admin benchmarks response.llm_core_manifest",
    );
    assertNonEmptyString(
      obj.module_manifest_version,
      "Algenta runtime admin benchmarks response.module_manifest_version",
    );
    const benchmarkDiscoveryLane = assertRuntimeBenchmarkDiscoveryLane(
      obj.benchmark_discovery_lane,
      "Algenta runtime admin benchmarks response.benchmark_discovery_lane",
    );
    assertRuntimeBenchmarkFramework(
      obj.benchmarking,
      "Algenta runtime admin benchmarks response.benchmarking",
    );
    assertArray(obj.slo_budgets, "Algenta runtime admin benchmarks response.slo_budgets").forEach(
      (entry, index) =>
        assertRuntimeSLOBudget(entry, `Algenta runtime admin benchmarks response.slo_budgets[${index}]`),
    );
    const qualityGateBenchmarkClasses = assertArray(
      obj.quality_gate_benchmark_classes,
      "Algenta runtime admin benchmarks response.quality_gate_benchmark_classes",
    );
    qualityGateBenchmarkClasses.forEach((entry, index) =>
      assertRuntimeBenchmarkClassEntry(
        entry,
        `Algenta runtime admin benchmarks response.quality_gate_benchmark_classes[${index}]`,
      ),
    );
    assertUniqueRuntimeObjectField(
      qualityGateBenchmarkClasses,
      "code",
      "Algenta runtime admin benchmarks response.quality_gate_benchmark_classes",
    );
    const qualityGateSLOBudgets = assertArray(
      obj.quality_gate_slo_budgets,
      "Algenta runtime admin benchmarks response.quality_gate_slo_budgets",
    );
    qualityGateSLOBudgets.forEach((entry, index) =>
      assertRuntimeSLOBudget(
        entry,
        `Algenta runtime admin benchmarks response.quality_gate_slo_budgets[${index}]`,
      ),
    );
    assertUniqueRuntimeObjectField(
      qualityGateSLOBudgets,
      "name",
      "Algenta runtime admin benchmarks response.quality_gate_slo_budgets",
    );
    assertRuntimeEvaluationScience(
      obj.evaluation_science,
      "Algenta runtime admin benchmarks response.evaluation_science",
    );
    assertRuntimeAdminEvaluationSummary(
      obj.evaluation_summary,
      "Algenta runtime admin benchmarks response.evaluation_summary",
    );
    const compiledArtifacts = assertArray(
      obj.compiled_artifacts,
      "Algenta runtime admin benchmarks response.compiled_artifacts",
    );
    compiledArtifacts.forEach((entry, index) =>
      assertRuntimeArtifactReference(
        entry,
        `Algenta runtime admin benchmarks response.compiled_artifacts[${index}]`,
      ),
    );
    assertUniqueRuntimeObjectField(
      compiledArtifacts,
      "path",
      "Algenta runtime admin benchmarks response.compiled_artifacts",
    );
    const shippingRuntimeModules = assertEnumArray(
      obj.shipping_runtime_modules,
      RUNTIME_MODULE_ID_VALUES,
      "Algenta runtime admin benchmarks response.shipping_runtime_modules",
    );
    assertUniqueRuntimeValues(
      shippingRuntimeModules,
      "Algenta runtime admin benchmarks response.shipping_runtime_modules",
    );
    const shippingRuntimeFunctionCounts = assertArray(
      obj.shipping_runtime_function_counts,
      "Algenta runtime admin benchmarks response.shipping_runtime_function_counts",
    ).map((value, index) =>
      assertInteger(
        value,
        `Algenta runtime admin benchmarks response.shipping_runtime_function_counts[${index}]`,
      ),
    );
    const shippingRuntimeBenchmarkSpeedupsX = assertArray(
      obj.shipping_runtime_benchmark_speedups_x,
      "Algenta runtime admin benchmarks response.shipping_runtime_benchmark_speedups_x",
    ).map((value, index) =>
      assertFiniteNumber(
        value,
        `Algenta runtime admin benchmarks response.shipping_runtime_benchmark_speedups_x[${index}]`,
      ),
    );
    const shippingRuntimeBenchmarkArtifacts = assertArray(
      obj.shipping_runtime_benchmark_artifacts,
      "Algenta runtime admin benchmarks response.shipping_runtime_benchmark_artifacts",
    ).map((value, index) =>
      assertNonEmptyString(
        value,
        `Algenta runtime admin benchmarks response.shipping_runtime_benchmark_artifacts[${index}]`,
      ),
    );
    const shippingRuntimeCompiledArtifacts = assertArray(
      obj.shipping_runtime_compiled_artifacts,
      "Algenta runtime admin benchmarks response.shipping_runtime_compiled_artifacts",
    ).map((value, index) =>
      assertNonEmptyString(
        value,
        `Algenta runtime admin benchmarks response.shipping_runtime_compiled_artifacts[${index}]`,
      ),
    );
    const shippingRuntimeCompiledEngines = assertArray(
      obj.shipping_runtime_compiled_engines,
      "Algenta runtime admin benchmarks response.shipping_runtime_compiled_engines",
    ).map((value, index) =>
      assertEnumValue(
        value,
        RUNTIME_COMPILED_ENGINE_VALUES,
        `Algenta runtime admin benchmarks response.shipping_runtime_compiled_engines[${index}]`,
      ),
    );
    const shippingRuntimeMaxColdMs = assertArray(
      obj.shipping_runtime_max_cold_ms,
      "Algenta runtime admin benchmarks response.shipping_runtime_max_cold_ms",
    ).map((value, index) =>
      assertFiniteNumber(
        value,
        `Algenta runtime admin benchmarks response.shipping_runtime_max_cold_ms[${index}]`,
      ),
    );
    const shippingRuntimeMaxWarmMs = assertArray(
      obj.shipping_runtime_max_warm_ms,
      "Algenta runtime admin benchmarks response.shipping_runtime_max_warm_ms",
    ).map((value, index) =>
      assertFiniteNumber(
        value,
        `Algenta runtime admin benchmarks response.shipping_runtime_max_warm_ms[${index}]`,
      ),
    );
    const shippingRuntimeMaxHotMs = assertArray(
      obj.shipping_runtime_max_hot_ms,
      "Algenta runtime admin benchmarks response.shipping_runtime_max_hot_ms",
    ).map((value, index) =>
      assertFiniteNumber(
        value,
        `Algenta runtime admin benchmarks response.shipping_runtime_max_hot_ms[${index}]`,
      ),
    );
    const compiledArtifactPaths = new Set(
      compiledArtifacts.map((entry, index) => {
        const artifact = assertJsonObject(
          entry,
          `Algenta runtime admin benchmarks response.compiled_artifacts[${index}]`,
        );
        return assertNonEmptyString(
          artifact.path,
          `Algenta runtime admin benchmarks response.compiled_artifacts[${index}].path`,
        );
      }),
    );
    const moduleBenchmarks = assertArray(
      obj.module_benchmarks,
      "Algenta runtime admin benchmarks response.module_benchmarks",
    );
    const validatedModuleBenchmarks = moduleBenchmarks.map((entry, index) =>
      assertRuntimeBenchmarkModuleEntry(
        entry,
        `Algenta runtime admin benchmarks response.module_benchmarks[${index}]`,
      ),
    );
    assertUniqueRuntimeObjectField(
      moduleBenchmarks,
      "name",
      "Algenta runtime admin benchmarks response.module_benchmarks",
    );
    if (benchmarkDiscoveryLane.shippingManifestModules !== validatedModuleBenchmarks.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.benchmark_discovery_lane.shipping_manifest_modules",
        "Algenta runtime admin benchmarks response.benchmark_discovery_lane.shipping_manifest_modules must equal the number of benchmark modules.",
        "value_error",
      );
    }
    if (benchmarkDiscoveryLane.shippingManifestModules !== shippingRuntimeModules.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.shipping_runtime_modules",
        "Algenta runtime admin benchmarks response.shipping_runtime_modules must contain one entry per shipping benchmark module.",
        "value_error",
      );
    }
    if (benchmarkDiscoveryLane.shippingManifestModules !== shippingRuntimeFunctionCounts.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.shipping_runtime_function_counts",
        "Algenta runtime admin benchmarks response.shipping_runtime_function_counts must contain one entry per shipping benchmark module.",
        "value_error",
      );
    }
    if (benchmarkDiscoveryLane.shippingManifestModules !== shippingRuntimeBenchmarkSpeedupsX.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.shipping_runtime_benchmark_speedups_x",
        "Algenta runtime admin benchmarks response.shipping_runtime_benchmark_speedups_x must contain one entry per shipping benchmark module.",
        "value_error",
      );
    }
    if (benchmarkDiscoveryLane.shippingManifestModules !== shippingRuntimeBenchmarkArtifacts.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.shipping_runtime_benchmark_artifacts",
        "Algenta runtime admin benchmarks response.shipping_runtime_benchmark_artifacts must contain one entry per shipping benchmark module.",
        "value_error",
      );
    }
    if (benchmarkDiscoveryLane.shippingManifestModules !== shippingRuntimeCompiledArtifacts.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.shipping_runtime_compiled_artifacts",
        "Algenta runtime admin benchmarks response.shipping_runtime_compiled_artifacts must contain one entry per shipping benchmark module.",
        "value_error",
      );
    }
    if (benchmarkDiscoveryLane.shippingManifestModules !== shippingRuntimeCompiledEngines.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.shipping_runtime_compiled_engines",
        "Algenta runtime admin benchmarks response.shipping_runtime_compiled_engines must contain one entry per shipping benchmark module.",
        "value_error",
      );
    }
    if (benchmarkDiscoveryLane.shippingManifestModules !== shippingRuntimeMaxColdMs.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.shipping_runtime_max_cold_ms",
        "Algenta runtime admin benchmarks response.shipping_runtime_max_cold_ms must contain one entry per shipping benchmark module.",
        "value_error",
      );
    }
    if (benchmarkDiscoveryLane.shippingManifestModules !== shippingRuntimeMaxWarmMs.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.shipping_runtime_max_warm_ms",
        "Algenta runtime admin benchmarks response.shipping_runtime_max_warm_ms must contain one entry per shipping benchmark module.",
        "value_error",
      );
    }
    if (benchmarkDiscoveryLane.shippingManifestModules !== shippingRuntimeMaxHotMs.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.shipping_runtime_max_hot_ms",
        "Algenta runtime admin benchmarks response.shipping_runtime_max_hot_ms must contain one entry per shipping benchmark module.",
        "value_error",
      );
    }
    const totalFunctions = validatedModuleBenchmarks.reduce(
      (sum, entry) => sum + entry.functionCount,
      0,
    );
    if (benchmarkDiscoveryLane.shippingManifestFunctions !== totalFunctions) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.benchmark_discovery_lane.shipping_manifest_functions",
        "Algenta runtime admin benchmarks response.benchmark_discovery_lane.shipping_manifest_functions must equal the total benchmark module function_count.",
        "value_error",
      );
    }
    validatedModuleBenchmarks.forEach((entry, index) => {
      if (!benchmarkDiscoveryLane.discoveredSourceImportPaths.includes(entry.name)) {
        throw buildStructuredValidationError(
          "Algenta runtime admin benchmarks response.benchmark_discovery_lane.discovered_source_inventory",
          `Algenta runtime admin benchmarks response.benchmark_discovery_lane.discovered_source_inventory must include module_benchmarks[${index}].name (${entry.name}).`,
          "value_error",
        );
      }
      if (shippingRuntimeModules[index] !== entry.name) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.shipping_runtime_modules[${index}]`,
          `Algenta runtime admin benchmarks response.shipping_runtime_modules[${index}] must equal module_benchmarks[${index}].name.`,
          "value_error",
        );
      }
      if (shippingRuntimeFunctionCounts[index] !== entry.functionCount) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.shipping_runtime_function_counts[${index}]`,
          `Algenta runtime admin benchmarks response.shipping_runtime_function_counts[${index}] must equal module_benchmarks[${index}].function_count.`,
          "value_error",
        );
      }
      if (shippingRuntimeBenchmarkSpeedupsX[index] !== entry.benchmarkSpeedupX) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.shipping_runtime_benchmark_speedups_x[${index}]`,
          `Algenta runtime admin benchmarks response.shipping_runtime_benchmark_speedups_x[${index}] must equal module_benchmarks[${index}].benchmark_speedup_x.`,
          "value_error",
        );
      }
      if (shippingRuntimeBenchmarkArtifacts[index] !== entry.benchmarkArtifact) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.shipping_runtime_benchmark_artifacts[${index}]`,
          `Algenta runtime admin benchmarks response.shipping_runtime_benchmark_artifacts[${index}] must equal module_benchmarks[${index}].benchmark_artifact.`,
          "value_error",
        );
      }
      if (shippingRuntimeCompiledArtifacts[index] !== entry.compiledArtifact) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.shipping_runtime_compiled_artifacts[${index}]`,
          `Algenta runtime admin benchmarks response.shipping_runtime_compiled_artifacts[${index}] must equal module_benchmarks[${index}].compiled_artifact.`,
          "value_error",
        );
      }
      if (shippingRuntimeCompiledEngines[index] !== entry.compiledEngine) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.shipping_runtime_compiled_engines[${index}]`,
          `Algenta runtime admin benchmarks response.shipping_runtime_compiled_engines[${index}] must equal module_benchmarks[${index}].compiled_engine.`,
          "value_error",
        );
      }
      if (shippingRuntimeMaxColdMs[index] !== entry.maxColdMs) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.shipping_runtime_max_cold_ms[${index}]`,
          `Algenta runtime admin benchmarks response.shipping_runtime_max_cold_ms[${index}] must equal module_benchmarks[${index}].max_cold_ms.`,
          "value_error",
        );
      }
      if (shippingRuntimeMaxWarmMs[index] !== entry.maxWarmMs) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.shipping_runtime_max_warm_ms[${index}]`,
          `Algenta runtime admin benchmarks response.shipping_runtime_max_warm_ms[${index}] must equal module_benchmarks[${index}].max_warm_ms.`,
          "value_error",
        );
      }
      if (shippingRuntimeMaxHotMs[index] !== entry.maxHotMs) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.shipping_runtime_max_hot_ms[${index}]`,
          `Algenta runtime admin benchmarks response.shipping_runtime_max_hot_ms[${index}] must equal module_benchmarks[${index}].max_hot_ms.`,
          "value_error",
        );
      }
      if (entry.benchmarkSpeedupX <= 0) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.module_benchmarks[${index}].benchmark_speedup_x`,
          "Algenta runtime admin benchmarks response.module_benchmarks entries must have positive benchmark_speedup_x values.",
          "value_error",
        );
      }
      if (entry.maxColdMs <= 0) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.module_benchmarks[${index}].max_cold_ms`,
          "Algenta runtime admin benchmarks response.module_benchmarks entries must have positive max_cold_ms values.",
          "value_error",
        );
      }
      if (entry.maxWarmMs <= 0) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.module_benchmarks[${index}].max_warm_ms`,
          "Algenta runtime admin benchmarks response.module_benchmarks entries must have positive max_warm_ms values.",
          "value_error",
        );
      }
      if (entry.maxHotMs <= 0) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.module_benchmarks[${index}].max_hot_ms`,
          "Algenta runtime admin benchmarks response.module_benchmarks entries must have positive max_hot_ms values.",
          "value_error",
        );
      }
    });
    const benchmarkArtifactIndexes = new Map<string, number>();
    validatedModuleBenchmarks.forEach((entry, index) => {
      const previousIndex = benchmarkArtifactIndexes.get(entry.benchmarkArtifact);
      if (previousIndex !== undefined) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.module_benchmarks[${index}].benchmark_artifact`,
          `Algenta runtime admin benchmarks response.module_benchmarks[${index}].benchmark_artifact duplicates module_benchmarks[${previousIndex}].benchmark_artifact.`,
          "value_error",
        );
      }
      benchmarkArtifactIndexes.set(entry.benchmarkArtifact, index);
      if (!compiledArtifactPaths.has(entry.compiledArtifact)) {
        throw buildStructuredValidationError(
          `Algenta runtime admin benchmarks response.module_benchmarks[${index}].compiled_artifact`,
          `Algenta runtime admin benchmarks response.module_benchmarks[${index}].compiled_artifact must reference a path present in compiled_artifacts.`,
          "value_error",
        );
      }
    });
    const declaredBenchmarkClassCodes = new Set(
      assertArray(
        assertJsonObject(obj.benchmarking, "Algenta runtime admin benchmarks response.benchmarking").classes,
        "Algenta runtime admin benchmarks response.benchmarking.classes",
      ).map((entry, index) =>
          assertEnumValue(
          assertJsonObject(
            entry,
            `Algenta runtime admin benchmarks response.benchmarking.classes[${index}]`,
          ).code,
          RUNTIME_BENCHMARK_CLASS_VALUES,
          `Algenta runtime admin benchmarks response.benchmarking.classes[${index}].code`,
        ),
      ),
    );
    const qualityGateClassCodes = new Set(
      qualityGateBenchmarkClasses.map((entry, index) =>
          assertEnumValue(
          assertJsonObject(
            entry,
            `Algenta runtime admin benchmarks response.quality_gate_benchmark_classes[${index}]`,
          ).code,
          RUNTIME_BENCHMARK_CLASS_VALUES,
          `Algenta runtime admin benchmarks response.quality_gate_benchmark_classes[${index}].code`,
        ),
      ),
    );
    qualityGateClassCodes.forEach(code => {
      if (!declaredBenchmarkClassCodes.has(code)) {
        throw buildStructuredValidationError(
          "Algenta runtime admin benchmarks response.quality_gate_benchmark_classes",
          "Algenta runtime admin benchmarks response.quality_gate_benchmark_classes must be declared in benchmarking.classes.",
          "value_error",
        );
      }
    });
    const declaredSLOBudgetNames = new Set(
      assertArray(
        obj.slo_budgets,
        "Algenta runtime admin benchmarks response.slo_budgets",
      ).map((entry, index) =>
        assertEnumValue(
          assertJsonObject(
            entry,
            `Algenta runtime admin benchmarks response.slo_budgets[${index}]`,
          ).name,
          RUNTIME_SLO_BUDGET_NAME_VALUES,
          `Algenta runtime admin benchmarks response.slo_budgets[${index}].name`,
        ),
      ),
    );
    const qualityGateBudgetNames = new Set(
      qualityGateSLOBudgets.map((entry, index) =>
        assertEnumValue(
          assertJsonObject(
            entry,
            `Algenta runtime admin benchmarks response.quality_gate_slo_budgets[${index}]`,
          ).name,
          RUNTIME_SLO_BUDGET_NAME_VALUES,
          `Algenta runtime admin benchmarks response.quality_gate_slo_budgets[${index}].name`,
        ),
      ),
    );
    qualityGateBudgetNames.forEach(name => {
      if (!declaredSLOBudgetNames.has(name)) {
        throw buildStructuredValidationError(
          "Algenta runtime admin benchmarks response.quality_gate_slo_budgets",
          "Algenta runtime admin benchmarks response.quality_gate_slo_budgets must be declared in slo_budgets.",
          "value_error",
        );
      }
    });
    const evaluationScience = assertJsonObject(
      obj.evaluation_science,
      "Algenta runtime admin benchmarks response.evaluation_science",
    );
    const evaluationDimensions = new Set(
      assertEnumArray(
        evaluationScience.dimensions,
        RUNTIME_EVALUATION_DIMENSION_VALUES,
        "Algenta runtime admin benchmarks response.evaluation_science.dimensions",
      ),
    );
    const evaluationReleaseBlockers = new Set(
      assertEnumArray(
        evaluationScience.release_blockers,
        RUNTIME_RELEASE_BLOCKER_VALUES,
        "Algenta runtime admin benchmarks response.evaluation_science.release_blockers",
      ),
    );
    const evaluationMethods = assertEnumArray(
      evaluationScience.methods,
      RUNTIME_EVALUATION_METHOD_VALUES,
      "Algenta runtime admin benchmarks response.evaluation_science.methods",
    );
    const evaluationSummary = assertJsonObject(
      obj.evaluation_summary,
      "Algenta runtime admin benchmarks response.evaluation_summary",
    );
    const expectedReplayGate =
      qualityGateClassCodes.has("B6") &&
      qualityGateBudgetNames.has("replay") &&
      evaluationDimensions.has("replay success rate") &&
      evaluationReleaseBlockers.has("replay success regression");
    const expectedToolCallGate =
      qualityGateClassCodes.has("B7") &&
      qualityGateBudgetNames.has("mcp_call_first_party") &&
      evaluationDimensions.has("tool-call correctness") &&
      evaluationReleaseBlockers.has("tool-call error-rate increase");
    const expectedRagGate =
      qualityGateClassCodes.has("B9") &&
      evaluationDimensions.has("retrieval precision and recall") &&
      evaluationReleaseBlockers.has("RAG precision drop");
    const expectedDecisionGate =
      qualityGateClassCodes.has("B10") &&
      qualityGateBudgetNames.has("decision_plan_creation") &&
      evaluationDimensions.has("decision outcome delta") &&
      evaluationReleaseBlockers.has("decision-plan validity drop");
    if (assertInteger(evaluationSummary.dimension_count, "Algenta runtime admin benchmarks response.evaluation_summary.dimension_count") !== evaluationDimensions.size) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.evaluation_summary.dimension_count",
        "Algenta runtime admin benchmarks response.evaluation_summary.dimension_count must equal the number of evaluation dimensions.",
        "value_error",
      );
    }
    if (assertInteger(evaluationSummary.method_count, "Algenta runtime admin benchmarks response.evaluation_summary.method_count") !== evaluationMethods.length) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.evaluation_summary.method_count",
        "Algenta runtime admin benchmarks response.evaluation_summary.method_count must equal the number of evaluation methods.",
        "value_error",
      );
    }
    if (assertInteger(evaluationSummary.release_blocker_count, "Algenta runtime admin benchmarks response.evaluation_summary.release_blocker_count") !== evaluationReleaseBlockers.size) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.evaluation_summary.release_blocker_count",
        "Algenta runtime admin benchmarks response.evaluation_summary.release_blocker_count must equal the number of release blockers.",
        "value_error",
      );
    }
    if (assertInteger(evaluationSummary.benchmark_class_count, "Algenta runtime admin benchmarks response.evaluation_summary.benchmark_class_count") !== qualityGateClassCodes.size) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.evaluation_summary.benchmark_class_count",
        "Algenta runtime admin benchmarks response.evaluation_summary.benchmark_class_count must equal the number of quality gate benchmark classes.",
        "value_error",
      );
    }
    if (assertInteger(evaluationSummary.slo_budget_count, "Algenta runtime admin benchmarks response.evaluation_summary.slo_budget_count") !== qualityGateBudgetNames.size) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.evaluation_summary.slo_budget_count",
        "Algenta runtime admin benchmarks response.evaluation_summary.slo_budget_count must equal the number of quality gate SLO budgets.",
        "value_error",
      );
    }
    if (
      assertBoolean(
        evaluationSummary.replay_gate_enabled,
        "Algenta runtime admin benchmarks response.evaluation_summary.replay_gate_enabled",
      ) !== expectedReplayGate
    ) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.evaluation_summary.replay_gate_enabled",
        "Algenta runtime admin benchmarks response.evaluation_summary.replay_gate_enabled must match the replay benchmark, budget, and release blocker coverage.",
        "value_error",
      );
    }
    if (
      assertBoolean(
        evaluationSummary.tool_call_quality_gate_enabled,
        "Algenta runtime admin benchmarks response.evaluation_summary.tool_call_quality_gate_enabled",
      ) !== expectedToolCallGate
    ) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.evaluation_summary.tool_call_quality_gate_enabled",
        "Algenta runtime admin benchmarks response.evaluation_summary.tool_call_quality_gate_enabled must match the tool-call benchmark, budget, and release blocker coverage.",
        "value_error",
      );
    }
    if (
      assertBoolean(
        evaluationSummary.rag_quality_gate_enabled,
        "Algenta runtime admin benchmarks response.evaluation_summary.rag_quality_gate_enabled",
      ) !== expectedRagGate
    ) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.evaluation_summary.rag_quality_gate_enabled",
        "Algenta runtime admin benchmarks response.evaluation_summary.rag_quality_gate_enabled must match the RAG benchmark and release blocker coverage.",
        "value_error",
      );
    }
    if (
      assertBoolean(
        evaluationSummary.decision_quality_gate_enabled,
        "Algenta runtime admin benchmarks response.evaluation_summary.decision_quality_gate_enabled",
      ) !== expectedDecisionGate
    ) {
      throw buildStructuredValidationError(
        "Algenta runtime admin benchmarks response.evaluation_summary.decision_quality_gate_enabled",
        "Algenta runtime admin benchmarks response.evaluation_summary.decision_quality_gate_enabled must match the decision benchmark, budget, and release blocker coverage.",
        "value_error",
      );
    }
    assertNonEmptyString(
      obj.manifest_digest,
      "Algenta runtime admin benchmarks response.manifest_digest",
    );
    assertRuntimeSignature(obj.signature, "Algenta runtime admin benchmarks response.signature");
    return value as RuntimeAdminBenchmarksResponse;
  });
}

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

function parseHeaderNumber(headers: Record<string, string>, ...keys: string[]): number | undefined {
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

function parseHeaderBoolean(headers: Record<string, string>, ...keys: string[]): boolean | undefined {
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

function buildQueryExecutionMetadata(
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

interface ResponseErrorEnvelope {
  code?: unknown;
  message?: unknown;
  details?: unknown;
}

function extractResponseError(body: unknown): ResponseErrorEnvelope | null {
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

function normalizedErrorCode(
  body: unknown,
  fallback: string,
): string {
  const code = extractResponseError(body)?.code;
  return typeof code === "string" && code.length > 0 ? code : fallback;
}

function normalizedErrorMessage(body: unknown): string {
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
