// SPDX-License-Identifier: Apache-2.0
/** Auto-split sub-module of client.ts — constants + setup imports. */

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


import { DecisionEngineError } from "./_client_errors.js";

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


export { DecisionEngineClientConfig };

export const DEFAULT_TIMEOUT = 120_000;
export const DEFAULT_MAX_RETRIES = 3;
export const DEFAULT_JOIN_PATH_HOPS = 4;
export const MAX_JOIN_PATH_HOPS = 6;
export const SDK_USER_AGENT = "algenta-ts/1.0.4";

export const RUNTIME_MATURITY_VALUES = [
  "experimental",
  "benchmarked",
  "parity_tested",
  "channel_covered",
  "enterprise_ready",
  "deprecated",
] as const;
export const RUNTIME_SIDE_EFFECT_CLASS_VALUES = [
  "read_only",
  "write_scoped",
  "write_external",
  "exec_external",
  "network_external",
] as const;
export const RUNTIME_RISK_LEVEL_VALUES = ["low", "medium", "high", "critical"] as const;
export const RUNTIME_REPLAYABILITY_VALUES = [
  "deterministic",
  "artifact_backed",
  "non_replayable",
] as const;
export const RUNTIME_SUPPORTED_CHANNEL_VALUES = [
  "python_sdk",
  "typescript_sdk",
  "cli",
  "mcp",
] as const;
export const RUNTIME_AUXILIARY_CHANNEL_VALUES = ["bundled_worker", "runtime_local"] as const;
export const RUNTIME_FEATURE_FLAG_CHANNEL_VALUES = ["http_api_feature_flag"] as const;
export const RUNTIME_DEPLOYMENT_MODE_VALUES = [
  "saas",
  "vpc",
  "self_hosted",
  "air_gapped",
  "hybrid_provider",
  "local_dev_daemon",
] as const;
export const RUNTIME_LAYER_VALUES = [
  "mojo_llm_runtime_core",
  "python_compatibility_ring",
  "llm_api_provider_layer",
  "agent_runtime",
  "decision_runtime",
  "enterprise_control_plane",
] as const;
export const RUNTIME_COMPILED_ENGINE_VALUES = ["mojo", "python_fallback"] as const;
export const RUNTIME_KERNEL_PROMOTION_STATUS_VALUES = ["candidate", "shipping"] as const;
export const RUNTIME_BENCHMARK_DISCOVERY_RULE_VALUES = [
  "Only the 22-module, 209-function LLM rollout is treated as the shipping runtime contract.",
] as const;
export const RUNTIME_NON_SHIPPING_RULE_VALUES = [
  "The broader Mojo inventory remains a benchmark and discovery lane only; modules are not advertised on the runtime surface unless listed in this manifest.",
] as const;
export const RUNTIME_MODULE_ID_VALUES = [
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
export const RUNTIME_PUBLIC_ENDPOINT_VALUES = [
  "/v1/meta/contract",
  "/v1/runtime/manifest",
] as const;
export const RUNTIME_ADMIN_ENDPOINT_VALUES = [
  "/v1/admin/runtime/modules",
  "/v1/admin/runtime/benchmarks",
  "/v1/admin/runtime/validation",
] as const;
export const RUNTIME_FEATURE_FLAG_ENDPOINT_VALUES = [
  "/v1/libraries",
  "/v1/libraries/health",
  "/v1/libraries/execute",
] as const;
export const RUNTIME_EXECUTION_TRANSITION_VALUES = [
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
export const RUNTIME_RELEASE_CONDITION_VALUES = [
  "manifest-listed",
  "proof-backed",
  "policy-covered",
  "replay-tested",
  "deployment-mode validated",
] as const;
export const RUNTIME_FAILURE_CODE_VALUES = [
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
export const RUNTIME_BENCHMARK_CLASS_VALUES = [
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
export const RUNTIME_SCHEDULER_POLICY_VALUES = [
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
export const RUNTIME_SCHEDULER_MINIMIZE_VALUES = [
  "tail latency",
  "memory waste",
  "context-switch overhead",
  "provider cost",
  "starvation",
] as const;
export const RUNTIME_SCHEDULER_MAXIMIZE_VALUES = [
  "GPU or CPU utilization",
  "KV cache reuse",
  "batching efficiency",
  "token throughput",
  "fairness",
] as const;
export const RUNTIME_SCHEDULER_INVARIANT_VALUES = [
  "No request starves indefinitely.",
  "High-priority requests cannot violate tenant quota.",
  "Batching may not cross isolation boundaries when policy forbids it.",
  "Speculative decoding may not emit unverified tokens.",
] as const;
export const RUNTIME_RELEASE_GATE_VALUES = ["A", "B", "C", "D", "E", "F", "G"] as const;
export const RUNTIME_INVARIANT_NAME_VALUES = [
  "Manifest Truth",
  "Replay Determinism",
  "Policy Monotonicity",
  "No Silent Fallback",
  "Audit Completeness",
  "Tenant Non-Interference",
] as const;
export const RUNTIME_EXECUTION_STATE_FIELD_VALUES = [
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
export const RUNTIME_EXECUTION_VALIDITY_RULE_VALUES = [
  "schema-valid",
  "policy-valid",
  "ordered",
  "replayable",
  "audit-visible",
] as const;
export const RUNTIME_LINEAGE_NODE_FIELD_VALUES = [
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
export const RUNTIME_EXTERNAL_NONDETERMINISM_SOURCE_VALUES = [
  "provider responses",
  "MCP tool responses",
  "database snapshots",
  "clock time",
  "random seeds",
  "external API outputs",
] as const;
export const RUNTIME_NONDETERMINISM_ARTIFACT_VALUES = [
  "provider response record",
  "tool or MCP response record",
  "data snapshot reference or query result hash",
  "clock snapshot",
  "seed record",
  "backend or version identifier",
] as const;
export const RUNTIME_ARTIFACT_LINEAGE_STEP_VALUES = [
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
export const RUNTIME_CAPABILITY_FIELD_VALUES = [
  "tool_name",
  "input_schema",
  "output_schema",
  "side_effect_class",
  "risk_level",
  "required_policy",
  "replayability",
  "approval_required",
] as const;
export const RUNTIME_CAPABILITY_RULE_VALUES = [
  "MCP tools are untrusted by default.",
  "No tool may execute without a capability record.",
  "Approvals and fallbacks derive from capability algebra, not ad hoc code paths.",
] as const;
export const RUNTIME_SLO_BUDGET_NAME_VALUES = [
  "runtime_manifest_load",
  "ttft",
  "end_to_end_turn",
  "agent_checkpoint_commit",
  "mcp_call_first_party",
  "decision_plan_creation",
  "replay",
] as const;
export const RUNTIME_SLO_BUDGET_APPLIES_TO_VALUES = [
  "first-party runtime manifest route",
  "first-party native LLM serving path",
  "agent runtime checkpoint persistence",
  "first-party or internal MCP tools",
  "decision runtime plan generation",
  "runs up to 1000 events",
] as const;
export const RUNTIME_MEMORY_REGION_VALUES = [
  "model weights",
  "KV cache pages",
  "prompt token buffer",
  "generation buffer",
  "retrieval context buffer",
  "checkpoint state",
  "tool-call state",
  "tenant-local cache",
] as const;
export const RUNTIME_MEMORY_RULE_VALUES = [
  "KV pages are tenant-scoped.",
  "Evicted cache pages must be zeroed or isolation-proven before reuse.",
  "Checkpoint state must reference immutable artifact hashes.",
  "Model weights must be version-pinned.",
  "Memory pressure must emit typed failure and never degrade silently.",
] as const;
export const RUNTIME_PROOF_OBLIGATION_VALUES = [
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
export const RUNTIME_BENCHMARK_METRIC_VALUES = [
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
export const RUNTIME_BENCHMARK_BASELINE_VALUES = [
  "Python reference",
  "PyTorch or Transformers path",
  "vLLM OpenAI-compatible backend",
  "llama.cpp GGUF backend",
  "ONNX Runtime backend",
  "CTranslate2 backend",
  "Algenta Mojo-native path",
] as const;
export const RUNTIME_EVALUATION_METHOD_VALUES = [
  "bootstrap confidence intervals",
  "paired model comparisons",
  "regression tests",
  "drift detection",
  "A/B experiments",
  "counterfactual replay",
  "Monte Carlo simulation",
  "sensitivity analysis",
] as const;
export const RUNTIME_RELEASE_BLOCKER_VALUES = [
  "replay success regression",
  "policy violation increase",
  "p95 budget violation",
  "RAG precision drop",
  "tool-call error-rate increase",
  "decision-plan validity drop",
] as const;
export const RUNTIME_EVALUATION_DIMENSION_VALUES = [
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
export const RUNTIME_THREAT_CLASS_VALUES = [
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
export const RUNTIME_THREAT_CONTROL_VALUES = [
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
export const RUNTIME_THREAT_RULE_VALUES = ["MCP tools are untrusted by default."] as const;
export const RUNTIME_RELEASE_ARTIFACT_VALUES = [
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
export const RUNTIME_ARTIFACT_KIND_VALUES = [
  "proof_bundle",
  "parity_benchmark",
  "compiled_runtime_benchmark",
  "compiled_mojo_binary",
] as const;
export const RUNTIME_SIGNATURE_ALGORITHM_VALUES = ["hmac-sha256"] as const;
export const RUNTIME_SIGNATURE_SCOPE_VALUES = ["control_plane_hmac_v1"] as const;

export function normalizeMaxJoinHops(value: unknown, fieldPath: string): number {
  if (!Number.isInteger(value)) {
    throw new Error(`${fieldPath} must be an integer between 1 and ${MAX_JOIN_PATH_HOPS}.`);
  }
  const normalized = Number(value);
  if (normalized < 1 || normalized > MAX_JOIN_PATH_HOPS) {
    throw new Error(`${fieldPath} must be between 1 and ${MAX_JOIN_PATH_HOPS}.`);
  }
  return normalized;
}

export function requireNonNegativeInteger(value: unknown, errorMessage: string): number {
  if (!Number.isInteger(value)) {
    throw new DecisionEngineError(errorMessage);
  }
  const normalized = Number(value);
  if (normalized < 0) {
    throw new DecisionEngineError(errorMessage);
  }
  return normalized;
}

export function requirePositiveInteger(value: unknown, errorMessage: string): number {
  const normalized = requireNonNegativeInteger(value, errorMessage);
  if (normalized < 1) {
    throw new DecisionEngineError(errorMessage);
  }
  return normalized;
}

export function normalizeJoinPathSpec(joinPath: Record<string, unknown>): Record<string, unknown> {
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

export function normalizeQueryLikeRequest(request: Record<string, unknown>): Record<string, unknown> {
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

export function mergeRequestPayload(
  request: Record<string, unknown> | undefined,
  extra: Record<string, unknown> = {},
): Record<string, unknown> {
  return normalizeQueryLikeRequest({ ...(request ?? {}), ...extra });
}

export function cloneJsonValue<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

export function mergeContractSections<T>(base: T, override: unknown): T {
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

export function appendQueryParameters(
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

export function invalidStreamError(
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

export function parseSseEvent(rawEvent: string): unknown | "[DONE]" | null {
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

export async function* iterateSsePayloads(body: ReadableStream<Uint8Array>): AsyncGenerator<unknown> {
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

export function normalizeSourceRegistrationRequest(
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

export function endpointSuffix(endpoint: string): string {
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

export function rebaseEndpoint(baseUrl: string, endpoint: string): string {
  return `${baseUrl.replace(/\/$/, "")}${endpointSuffix(endpoint)}`;
}
