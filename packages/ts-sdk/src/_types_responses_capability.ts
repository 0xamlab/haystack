// SPDX-License-Identifier: Apache-2.0
/** Auto-split sub-module of types.ts — responses_capability types. */

// Auto-split from types.ts. Cross-file type references use `import type`.
import type { CAPABILITY_PLANE_CONTRACT, PRIMARY_DATA_QUERY_CONTRACT } from "./contract.js";

export interface QueryCandidate {
  source: string;
  column: string;
  role: string;
  magnitude?: string | null;
  formula?: string | null;
  confidence: number;
  score_components?: Record<string, number>;
  notes?: string[];
}

export type QueryFilterOperator =
  | "eq"
  | "in"
  | "gt"
  | "gte"
  | "lt"
  | "lte"
  | "is_null"
  | "is_not_null";

export interface QueryFilterCondition {
  column?: string | null;
  dimension_hint?: string | null;
  op: QueryFilterOperator;
  value?: unknown;
  values?: unknown[];
}

export interface QueryFilterSpec {
  time_filter?: string | null;
  conditions?: QueryFilterCondition[];
}

export interface ResolvedPlan {
  source_name: string;
  metric_column: string;
  aggregation: string;
  group_column?: string | null;
  join_path?: Record<string, unknown> | null;
  filter?: QueryFilterSpec | null;
  limit?: number | null;
  order?: string;
  constraints?: Record<string, unknown>;
  schema_revision: string;
}

export interface ResolveResponse {
  resolved_plan?: ResolvedPlan | null;
  confidence: number;
  plan: string[];
  explanation: string[];
  resolved_column: string;
  resolved_role: string;
  resolved_source: string;
  candidates: QueryCandidate[];
  source_scores: Record<string, number>;
  latency_ms: number;
  decision_path: string;
  plan_hash?: string | null;
  schema_revision: string;
  validated: boolean;
  deterministic_scope: string;
  confidence_source: string;
  clarification_required?: boolean;
  rejection_reason?: string | null;
  request_id?: string | null;
  intent_signature: string;
  source_set?: string[];
  join_path?: Array<Record<string, unknown>>;
  planner_mode?: string | null;
}

export interface QueryResponse {
  query_id: string;
  result: unknown;
  result_type: string;
  confidence: number;
  plan: string[];
  resolved_column: string;
  resolved_role: string;
  resolved_source: string;
  row_count: number;
  candidates: QueryCandidate[];
  source_scores: Record<string, number>;
  ambiguous: boolean;
  exact_spec: boolean;
  explanation: string[];
  latency_ms: number;
  decision_path: string;
  plan_hash: string;
  schema_revision?: string | null;
  validated: boolean;
  deterministic_scope: string;
  confidence_source: string;
  clarification_required?: boolean;
  rejection_reason?: string | null;
  request_id?: string | null;
  source_set?: string[];
  join_path?: Array<Record<string, unknown>>;
  planner_mode?: string | null;
}

export interface QueryExecutionMetadata {
  request_id?: string | null;
  latency_ms?: number | null;
  tokens_in?: number | null;
  tokens_out?: number | null;
  cost_usd?: number | null;
  cache_hit?: boolean | null;
}

export interface QueryWithMetadataResponse {
  data: QueryResponse;
  metadata: QueryExecutionMetadata;
  headers?: Record<string, string> | null;
}

export type PrimaryDataQueryContract = typeof PRIMARY_DATA_QUERY_CONTRACT;
export type CapabilityPlaneContract = typeof CAPABILITY_PLANE_CONTRACT;

export interface ApiKeyPrefixes {
  live: string;
  test: string;
}

export interface CompatibilityContract {
  legacy_headers: string[];
  legacy_env_vars: string[];
  legacy_domains: string[];
  deprecation_window_days: number;
}

export interface PrivacyRegistryContract {
  algenta_owned_hosts: string[];
  algenta_owned_suffixes: string[];
  vendor_telemetry_hosts: string[];
  private_host_suffixes: string[];
}

export interface DefaultsContract {
  read_only_default: boolean;
  write_confirmation_required: boolean;
  plan_limits: Record<string, Record<string, number | string>>;
}

export interface IntegrationContract {
  name: string;
  description: string;
  icon: string;
  capabilities: string[];
  auth_scheme: string;
  required_scopes: string[];
  read_only_default: boolean;
  write_actions: string[];
  admin_controls: string[];
  docs_url: string;
  privacy_url: string;
  terms_url: string;
  support_url: string;
  regions: string[];
  status: string;
}

export interface PlatformContractResponse {
  contract_version: string;
  brand: string;
  api_base_url: string;
  mcp_endpoint: string;
  mcp_transport: string;
  mcp_protocol_version: string;
  mcp_legacy_sse_endpoint: string;
  mcp_tools_endpoint: string;
  auth_scheme: string;
  api_key_prefixes: ApiKeyPrefixes;
  compatibility: CompatibilityContract;
  privacy_registry: PrivacyRegistryContract;
  defaults: DefaultsContract;
  primary_data_query_contract: PrimaryDataQueryContract;
  capability_plane?: CapabilityPlaneContract | null;
  integrations: IntegrationContract[];
}

export type CapabilityProviderType =
  | "data_connector"
  | "mcp_provider"
  | "skill_pack"
  | "native_tool_pack"
  | "runtime_library_pack";

export type CapabilityKind =
  | "dataset"
  | "mcp_tool"
  | "mcp_resource"
  | "mcp_prompt"
  | "skill"
  | "native_tool"
  | "runtime_library";

export type ImplementationKind = "callable" | "instruction_only" | "hybrid";

export type ExecutionOwner = "algenta_managed" | "client_managed";

export type BindingScope = "user" | "workspace" | "organization";

export type BindingStatus =
  | "unconfigured"
  | "authorizing"
  | "ready"
  | "degraded"
  | "quarantined";

export type AuthorizationSessionStatus =
  | "pending"
  | "completed"
  | "expired"
  | "failed";

export type ExecutionSessionStatus =
  | "started"
  | "succeeded"
  | "failed";

export interface CapabilityProviderProfileResponse {
  profile_id: string;
  provider_id: string;
  name: string;
  description?: string | null;
  auth_kind: string;
  default_execution_owner: ExecutionOwner;
  binding_scope_default: BindingScope;
  supported_binding_scopes: string[];
  profile_metadata?: Record<string, unknown> | null;
}

export interface CapabilityProviderResponse {
  provider_id: string;
  provider_type: CapabilityProviderType;
  name: string;
  description?: string | null;
  docs_url?: string | null;
  auth_schema?: Record<string, unknown> | null;
  certification_summary?: Record<string, unknown> | null;
  policy_summary?: Record<string, unknown> | null;
  supported_execution_owners: string[];
  install_metadata?: Record<string, unknown> | null;
  customer_metadata?: Record<string, unknown> | null;
  active: boolean;
  profiles: CapabilityProviderProfileResponse[];
}

export interface CapabilityBindingCreateRequest {
  provider_id: string;
  profile_id: string;
  binding_name: string;
  scope?: BindingScope;
  scope_ref?: string | null;
  execution_owner?: ExecutionOwner | null;
  config?: Record<string, unknown> | null;
  customer_metadata?: Record<string, unknown> | null;
}

export interface CapabilityBindingUpdateRequest {
  binding_name?: string | null;
  scope?: BindingScope | null;
  scope_ref?: string | null;
  status?: BindingStatus | null;
  execution_owner?: ExecutionOwner | null;
  config?: Record<string, unknown> | null;
  customer_metadata?: Record<string, unknown> | null;
}

export interface CapabilityBindingPreviewRequest {
  provider_id: string;
  profile_id: string;
  scope?: BindingScope;
  scope_ref?: string | null;
  execution_owner?: ExecutionOwner | null;
  config?: Record<string, unknown> | null;
  customer_metadata?: Record<string, unknown> | null;
}

export interface CapabilityBindingResponse {
  binding_id: string;
  provider_id: string;
  profile_id: string;
  binding_name: string;
  scope: BindingScope;
  scope_ref: string;
  status: BindingStatus;
  execution_owner: ExecutionOwner;
  config?: Record<string, unknown> | null;
  customer_metadata?: Record<string, unknown> | null;
  system_managed: boolean;
  last_tested_at?: string | null;
  last_discovered_at?: string | null;
  authorized_at?: string | null;
  quarantine_reason?: string | null;
  discovery_error_message?: string | null;
  test_error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CapabilityBindingTestResult {
  success: boolean;
  binding_status: BindingStatus;
  message: string;
  latency_ms?: number | null;
  details: Record<string, unknown>;
}

export interface CapabilityCatalogEntry {
  capability_id: string;
  provider_id: string;
  profile_id: string;
  binding_id: string;
  kind: CapabilityKind;
  name: string;
  description?: string | null;
  implementation_kind: ImplementationKind;
  execution_owner: ExecutionOwner;
  input_schema_ref: string;
  output_schema_ref: string;
  side_effect_class: RuntimeSideEffectClass;
  risk_level: RuntimeRiskLevel;
  required_policy: string;
  replayability: RuntimeReplayability;
  approval_required: boolean;
  trust_tier: string;
  manifest_hash: string;
  artifact_affinities: string[];
  tags: string[];
  required_binding_ids: string[];
  selected_tool_name?: string | null;
  instruction_artifact_ref?: string | null;
  binding_status: BindingStatus;
  discovered_at?: string | null;
  customer_metadata?: Record<string, unknown> | null;
  instruction_text?: string | null;
}

export interface CapabilityDiscoverResponse {
  binding_id?: string | null;
  provider_id: string;
  profile_id: string;
  snapshot_id?: string | null;
  binding_status: BindingStatus;
  manifest_hash: string;
  capability_count: number;
  discovered_at: string;
  message: string;
  capabilities: CapabilityCatalogEntry[];
}

export interface CapabilityRouteRequest {
  objective: string;
  binding_ids?: string[];
  provider_ids?: string[];
  kinds?: CapabilityKind[];
  execution_owners?: ExecutionOwner[];
  artifact_affinities?: string[];
  tags?: string[];
  max_fallbacks?: number;
}

export interface CapabilityRouteFallback {
  capability_id: string;
  provider_id: string;
  binding_id: string;
  kind: CapabilityKind;
  execution_owner: ExecutionOwner;
  confidence: number;
  reason: string;
  selected_tool_name?: string | null;
  instruction_artifact_ref?: string | null;
}

export interface CapabilityRoutePlan {
  selected_capability_id: string;
  selected_provider_id: string;
  selected_binding_id: string;
  kind: CapabilityKind;
  execution_owner: ExecutionOwner;
  requires_approval: boolean;
  confidence: number;
  reason: string;
  fallbacks: CapabilityRouteFallback[];
  policy_snapshot_id: string;
  selected_tool_name?: string | null;
  instruction_artifact_ref?: string | null;
}

export interface CapabilityExecutionRequest {
  capability_id: string;
  binding_id?: string | null;
  input?: Record<string, unknown> | null;
  request_id?: string | null;
}

export interface CapabilityExecutionResponse {
  execution_session_id: string;
  capability_id: string;
  provider_id: string;
  binding_id: string;
  execution_owner: ExecutionOwner;
  status: ExecutionSessionStatus;
  output?: Record<string, unknown> | null;
  error?: Record<string, unknown> | null;
  started_at: string;
  completed_at?: string | null;
}

export interface CapabilityOutcomeRecord {
  outcome_id: string;
  capability_id: string;
  provider_id: string;
  binding_id?: string | null;
  success?: boolean | null;
  result_status: string;
  confidence?: number | null;
  latency_ms?: number | null;
  error_code?: string | null;
  details?: Record<string, unknown> | null;
  created_at: string;
}

export interface CapabilityOutcomeRecordRequest {
  capability_id: string;
  provider_id: string;
  binding_id?: string | null;
  success?: boolean | null;
  result_status?: string;
  confidence?: number | null;
  latency_ms?: number | null;
  error_code?: string | null;
  details?: Record<string, unknown> | null;
}

export interface CapabilityAuthorizationStartRequest {
  redirect_uri?: string | null;
  requested_scopes?: string[];
  state_payload?: Record<string, unknown> | null;
}

export interface CapabilityAuthorizationStartResponse {
  session_id: string;
  binding_id: string;
  provider_id: string;
  authorize_url: string;
  expires_at: string;
  requested_scopes: string[];
}

export interface CapabilityAuthorizationCompleteRequest {
  session_id: string;
  callback_payload?: Record<string, unknown> | null;
  authorization_code?: string | null;
  state?: string | null;
}

export interface CapabilityAuthorizationCompleteResponse {
  session_id: string;
  binding_id: string;
  provider_id: string;
  status: AuthorizationSessionStatus;
  authorized_at?: string | null;
}

export interface SkillEnableRequest {
  skill_name: string;
  instruction: string;
  description?: string | null;
  tags?: string[];
  artifact_affinities?: string[];
  execution_owner?: ExecutionOwner;
}

export interface CapabilityAdapterDescriptor {
  capability_id: string;
  provider_id: string;
  profile_id?: string;
  binding_id?: string;
  binding_name?: string;
  name: string;
  description?: string;
  kind: CapabilityKind;
  implementation_kind?: ImplementationKind;
  execution_owner?: ExecutionOwner;
  input_schema_ref?: string;
  output_schema_ref?: string;
  side_effect_class?: RuntimeSideEffectClass;
  risk_level?: RuntimeRiskLevel;
  required_policy?: string;
  replayability?: RuntimeReplayability;
  approval_required?: boolean;
  trust_tier?: string;
  artifact_affinities?: string[];
  tags?: string[];
  selected_tool_name?: string;
  instruction_artifact_ref?: string;
  instruction_text?: string;
  customer_metadata?: Record<string, unknown>;
}

export interface CapabilityAdapter {
  descriptor: CapabilityAdapterDescriptor;
  execute(
    request: CapabilityExecutionRequest,
    capability: CapabilityCatalogEntry,
  ):
    | Promise<Record<string, unknown> | null | undefined>
    | Record<string, unknown>
    | null
    | undefined;
  test?(
    binding: CapabilityBindingPreviewRequest | CapabilityBindingResponse,
  ): Promise<CapabilityBindingTestResult> | CapabilityBindingTestResult;
  discover?(
    binding: CapabilityBindingPreviewRequest | CapabilityBindingResponse,
  ): Promise<CapabilityCatalogEntry[]> | CapabilityCatalogEntry[];
  health?(): Promise<Record<string, unknown> | null | undefined> | Record<string, unknown> | null | undefined;
}

export type RuntimeMaturity =
  | "experimental"
  | "benchmarked"
  | "parity_tested"
  | "channel_covered"
  | "enterprise_ready"
  | "deprecated";

export type RuntimeSideEffectClass =
  | "read_only"
  | "write_scoped"
  | "write_external"
  | "exec_external"
  | "network_external";

export type RuntimeRiskLevel = "low" | "medium" | "high" | "critical";

export type RuntimeReplayability =
  | "deterministic"
  | "artifact_backed"
  | "non_replayable";

export type RuntimeSupportedChannel =
  | "python_sdk"
  | "typescript_sdk"
  | "cli"
  | "mcp";

export type RuntimeAuxiliaryChannel = "bundled_worker" | "runtime_local";

export type RuntimeFeatureFlagChannel = "http_api_feature_flag";

export type RuntimeDeploymentMode =
  | "saas"
  | "vpc"
  | "self_hosted"
  | "air_gapped"
  | "hybrid_provider"
  | "local_dev_daemon";

export type RuntimeLayer =
  | "mojo_llm_runtime_core"
  | "python_compatibility_ring"
  | "llm_api_provider_layer"
  | "agent_runtime"
  | "decision_runtime"
  | "enterprise_control_plane";
export type RuntimeCompiledEngine = "mojo" | "python_fallback";
export type RuntimeKernelPromotionStatus = "candidate" | "shipping";
export type RuntimeModuleId =
  | "bpe_tokenizer"
  | "text.tokenizer"
  | "embeddings"
  | "flash_attention"
  | "sparse_attention"
  | "transformer_attention"
  | "transformer_blocks"
  | "llm_sampling"
  | "vector_similarity"
  | "vector_search"
  | "vector_kernels.ranker"
  | "vector_kernels.table"
  | "sparse_vector"
  | "rlhf_dpo"
  | "rerank_eval"
  | "inference_cost_latency"
  | "kv_cache"
  | "paged_kv_cache"
  | "continuous_batching"
  | "inference_engine"
  | "speculative_decoding"
  | "generation_loop";
export type RuntimePublicEndpoint =
  | "/v1/meta/contract"
  | "/v1/runtime/manifest";
export type RuntimeAdminEndpoint =
  | "/v1/admin/runtime/modules"
  | "/v1/admin/runtime/benchmarks"
  | "/v1/admin/runtime/validation";
export type RuntimeFeatureFlagEndpoint =
  | "/v1/libraries"
  | "/v1/libraries/health"
  | "/v1/libraries/execute";
export type RuntimeExecutionTransition =
  | "model_call_started"
  | "model_token_emitted"
  | "tool_call_requested"
  | "tool_call_approved"
  | "tool_call_denied"
  | "checkpoint_committed"
  | "decision_plan_created"
  | "simulation_started"
  | "execution_started"
  | "replay_started"
  | "failure_emitted";
export type RuntimeReleaseCondition =
  | "manifest-listed"
  | "proof-backed"
  | "policy-covered"
  | "replay-tested"
  | "deployment-mode validated";
export type RuntimeFailureCode =
  | "provider_timeout"
  | "runtime_compile_error"
  | "mcp_tool_denied"
  | "policy_denied"
  | "schema_access_denied"
  | "checkpoint_failed"
  | "replay_mismatch"
  | "external_dependency_unavailable"
  | "backend_unavailable"
  | "quota_exceeded"
  | "approval_required"
  | "kv_cache_exhausted"
  | "artifact_load_failed"
  | "memory_pressure_limit"
  | "tenant_cache_violation"
  | "checkpoint_state_overflow";
export type RuntimeBenchmarkClassCode =
  | "B1"
  | "B2"
  | "B3"
  | "B4"
  | "B5"
  | "B6"
  | "B7"
  | "B8"
  | "B9"
  | "B10";
export type RuntimeSchedulerPolicy =
  | "FIFO"
  | "priority_queue"
  | "deadline_aware"
  | "cost_aware"
  | "tenant_fair"
  | "kv_cache_aware"
  | "batching_aware"
  | "speculative_decoding_aware"
  | "policy_constrained";
export type RuntimeSchedulerMinimizeObjective =
  | "tail latency"
  | "memory waste"
  | "context-switch overhead"
  | "provider cost"
  | "starvation";
export type RuntimeSchedulerMaximizeObjective =
  | "GPU or CPU utilization"
  | "KV cache reuse"
  | "batching efficiency"
  | "token throughput"
  | "fairness";
export type RuntimeSchedulerInvariant =
  | "No request starves indefinitely."
  | "High-priority requests cannot violate tenant quota."
  | "Batching may not cross isolation boundaries when policy forbids it."
  | "Speculative decoding may not emit unverified tokens.";
export type RuntimeReleaseGateId = "A" | "B" | "C" | "D" | "E" | "F" | "G";
export type RuntimeInvariantName =
  | "Manifest Truth"
  | "Replay Determinism"
  | "Policy Monotonicity"
  | "No Silent Fallback"
  | "Audit Completeness"
  | "Tenant Non-Interference";
export type RuntimeExecutionStateField =
  | "request"
  | "tenant"
  | "workspace"
  | "policy_snapshot"
  | "schema_snapshot"
  | "runtime_manifest"
  | "model_backend"
  | "tool_manifest"
  | "checkpoint_log"
  | "event_log"
  | "decision_state";
export type RuntimeExecutionValidityRule =
  | "schema-valid"
  | "policy-valid"
  | "ordered"
  | "replayable"
  | "audit-visible";
