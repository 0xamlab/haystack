// SPDX-License-Identifier: Apache-2.0
/** Auto-split sub-module of types.ts — responses_runtime types. */

// Auto-split from types.ts. Cross-file type references use `import type`.
import type { CAPABILITY_PLANE_CONTRACT, PRIMARY_DATA_QUERY_CONTRACT } from "./contract.js";
import type {
  QueryExecutionMetadata,
  QueryFilterSpec,
  QueryResponse,
  RuntimeAdminEndpoint,
  RuntimeAuxiliaryChannel,
  RuntimeBenchmarkClassCode,
  RuntimeCompiledEngine,
  RuntimeDeploymentMode,
  RuntimeExecutionStateField,
  RuntimeExecutionTransition,
  RuntimeExecutionValidityRule,
  RuntimeFailureCode,
  RuntimeFeatureFlagChannel,
  RuntimeFeatureFlagEndpoint,
  RuntimeInvariantName,
  RuntimeKernelPromotionStatus,
  RuntimeLayer,
  RuntimeMaturity,
  RuntimeModuleId,
  RuntimePublicEndpoint,
  RuntimeReleaseCondition,
  RuntimeReleaseGateId,
  RuntimeReplayability,
  RuntimeRiskLevel,
  RuntimeSchedulerInvariant,
  RuntimeSchedulerMaximizeObjective,
  RuntimeSchedulerMinimizeObjective,
  RuntimeSchedulerPolicy,
  RuntimeSideEffectClass,
  RuntimeSupportedChannel,
} from "./_types_responses_capability.js";

export type RuntimeLineageNodeField =
  | "node_id"
  | "artifact_type"
  | "content_hash"
  | "parent_hashes"
  | "tenant_scope"
  | "workspace_scope"
  | "timestamp"
  | "manifest_version"
  | "policy_snapshot_id"
  | "schema_snapshot_id";
export type RuntimeExternalNondeterminismSource =
  | "provider responses"
  | "MCP tool responses"
  | "database snapshots"
  | "clock time"
  | "random seeds"
  | "external API outputs";
export type RuntimeNondeterminismArtifact =
  | "provider response record"
  | "tool or MCP response record"
  | "data snapshot reference or query result hash"
  | "clock snapshot"
  | "seed record"
  | "backend or version identifier";
export type RuntimeArtifactLineageStep =
  | "input"
  | "policy snapshot"
  | "schema snapshot"
  | "runtime manifest"
  | "backend or model"
  | "tool or MCP calls"
  | "checkpoints"
  | "decision plan"
  | "execution record"
  | "outcome"
  | "evaluation result";
export type RuntimeCapabilityField =
  | "tool_name"
  | "input_schema"
  | "output_schema"
  | "side_effect_class"
  | "risk_level"
  | "required_policy"
  | "replayability"
  | "approval_required";
export type RuntimeCapabilityRule =
  | "MCP tools are untrusted by default."
  | "No tool may execute without a capability record."
  | "Approvals and fallbacks derive from capability algebra, not ad hoc code paths.";
export type RuntimeSLOBudgetName =
  | "runtime_manifest_load"
  | "ttft"
  | "end_to_end_turn"
  | "agent_checkpoint_commit"
  | "mcp_call_first_party"
  | "decision_plan_creation"
  | "replay";
export type RuntimeSLOBudgetAppliesTo =
  | "first-party runtime manifest route"
  | "first-party native LLM serving path"
  | "agent runtime checkpoint persistence"
  | "first-party or internal MCP tools"
  | "decision runtime plan generation"
  | "runs up to 1000 events";
export type RuntimeMemoryRegion =
  | "model weights"
  | "KV cache pages"
  | "prompt token buffer"
  | "generation buffer"
  | "retrieval context buffer"
  | "checkpoint state"
  | "tool-call state"
  | "tenant-local cache";
export type RuntimeMemoryRule =
  | "KV pages are tenant-scoped."
  | "Evicted cache pages must be zeroed or isolation-proven before reuse."
  | "Checkpoint state must reference immutable artifact hashes."
  | "Model weights must be version-pinned."
  | "Memory pressure must emit typed failure and never degrade silently.";

export type RuntimeProofObligation =
  | "numerical parity"
  | "deterministic kernels"
  | "latency and memory bounds"
  | "channel proof"
  | "manifest listing"
  | "API equivalence"
  | "behavioral equivalence against Python reference"
  | "OpenAI-compatible schema parity"
  | "streaming semantics parity"
  | "typed failure parity"
  | "event ordering"
  | "checkpoint correctness"
  | "cancellation safety"
  | "replay safety"
  | "evidence completeness"
  | "simulation traceability"
  | "approval correctness"
  | "tenant isolation"
  | "policy enforcement"
  | "metering correctness";

export type RuntimeBenchmarkMetric =
  | "p50"
  | "p90"
  | "p95"
  | "p99"
  | "tokens_per_second"
  | "ttft"
  | "requests_per_second"
  | "memory_peak"
  | "cache_hit_rate"
  | "checkpoint_commit_latency"
  | "replay_latency"
  | "tool_call_latency"
  | "decision_plan_latency"
  | "simulation_latency"
  | "cost_per_successful_run";

export type RuntimeBenchmarkBaseline =
  | "Python reference"
  | "PyTorch or Transformers path"
  | "vLLM OpenAI-compatible backend"
  | "llama.cpp GGUF backend"
  | "ONNX Runtime backend"
  | "CTranslate2 backend"
  | "Algenta Mojo-native path";

export type RuntimeEvaluationMethod =
  | "bootstrap confidence intervals"
  | "paired model comparisons"
  | "regression tests"
  | "drift detection"
  | "A/B experiments"
  | "counterfactual replay"
  | "Monte Carlo simulation"
  | "sensitivity analysis";

export type RuntimeReleaseBlocker =
  | "replay success regression"
  | "policy violation increase"
  | "p95 budget violation"
  | "RAG precision drop"
  | "tool-call error-rate increase"
  | "decision-plan validity drop";

export type RuntimeEvaluationDimension =
  | "answer correctness"
  | "tool-call correctness"
  | "schema correctness"
  | "retrieval precision and recall"
  | "hallucination rate"
  | "policy violation rate"
  | "replay success rate"
  | "decision outcome delta"
  | "cost-quality frontier"
  | "latency-quality frontier";

export type RuntimeThreatClass =
  | "prompt injection"
  | "tool injection"
  | "MCP abuse"
  | "data exfiltration"
  | "cross-tenant leakage"
  | "provider fallback leakage"
  | "secret exposure"
  | "replay tampering"
  | "audit log mutation"
  | "model artifact poisoning"
  | "dependency supply-chain attack"
  | "billing abuse"
  | "quota bypass";

export type RuntimeThreatControl =
  | "tool allowlists"
  | "argument validation"
  | "result sanitization"
  | "egress policy"
  | "signed manifests"
  | "signed artifacts"
  | "immutable audit logs"
  | "policy snapshots"
  | "secret scoping"
  | "tenant-scoped cache"
  | "SBOM"
  | "dependency pinning"
  | "runtime attestation";

export type RuntimeThreatRule = "MCP tools are untrusted by default.";

export type RuntimeReleaseArtifact =
  | "signed runtime manifest"
  | "module maturity table"
  | "benchmark report"
  | "parity report"
  | "replay report"
  | "security report"
  | "compatibility report"
  | "migration notes"
  | "known limitations";
export type RuntimeArtifactKind =
  | "proof_bundle"
  | "parity_benchmark"
  | "compiled_runtime_benchmark"
  | "compiled_mojo_binary";
export type RuntimeSignatureAlgorithm = "hmac-sha256";
export type RuntimeSignatureScope = "control_plane_hmac_v1";
export type RuntimeBenchmarkDiscoveryRule =
  "Only the 22-module, 209-function LLM rollout is treated as the shipping runtime contract.";
export type RuntimeNonShippingRule =
  "The broader Mojo inventory remains a benchmark and discovery lane only; modules are not advertised on the runtime surface unless listed in this manifest.";

export interface RuntimeArtifactReference {
  kind: RuntimeArtifactKind;
  path: string;
  sha256: string;
  size_bytes: number;
}

export interface RuntimeManifestSignature {
  algorithm: RuntimeSignatureAlgorithm;
  key_id: string;
  digest_hex: string;
  signature_hex: string;
  scope: RuntimeSignatureScope;
}

export interface RuntimeSnapshotReference {
  snapshot_id: string;
  sha256: string;
  source: string;
  description: string;
}

export interface RuntimeKernelPromotionCriteria {
  required_manifest_fields: string[];
  required_proof_reference_fields: string[];
  deterministic_test_corpus_rule: string;
  python_parity_rule: string;
  schema_compatibility_rule: string;
  minimum_primary_metric_improvement_pct: number;
  maximum_adjacent_metric_regression_pct: number;
  benchmark_exception_rule: string;
  rollback_scope_rule: string;
  tenant_isolation_rule: string;
  replay_compatibility_rule: string;
}

export interface RuntimeModuleManifestEntry {
  name: RuntimeModuleId;
  capability_id: string;
  owner: string;
  contract_boundary: string;
  function_count: number;
  functions: string[];
  layer: RuntimeLayer;
  maturity: RuntimeMaturity;
  public_supported_channels: RuntimeSupportedChannel[];
  validated_auxiliary_channels: RuntimeAuxiliaryChannel[];
  feature_flag_channels: RuntimeFeatureFlagChannel[];
  proof_obligations: RuntimeProofObligation[];
  proof_artifacts: string[];
  promotion_status: RuntimeKernelPromotionStatus;
  rollback_flag: string;
  benchmark_report_ref: string;
  parity_report_ref: string;
  schema_compat_report_ref: string;
  isolation_proof_ref: string;
  replay_proof_ref: string;
  benchmark_artifact: string;
  benchmark_speedup_x: number;
  compiled_artifact: string;
  compiled_engine: RuntimeCompiledEngine;
  max_cold_ms: number;
  max_warm_ms: number;
  max_hot_ms: number;
}

export interface RuntimeDeploymentModes {
  current: RuntimeDeploymentMode;
  supported_modes: RuntimeDeploymentMode[];
  rule: string;
}

export interface RuntimeShippingContractSummary {
  module_count: number;
  function_count: number;
  runtime_core_layer: RuntimeLayer;
  benchmark_discovery_rule: RuntimeBenchmarkDiscoveryRule;
}

export interface RuntimeBenchmarkDiscoverySourceModuleEntry {
  import_path: string;
  public_function_count: number;
}

export interface RuntimeBenchmarkDiscoveryLane {
  discovered_source_modules: number;
  discovered_public_functions: number;
  discovered_source_inventory: RuntimeBenchmarkDiscoverySourceModuleEntry[];
  shipping_manifest_modules: number;
  shipping_manifest_functions: number;
  non_shipping_rule: RuntimeNonShippingRule;
}

export interface RuntimeAdvertisedCapabilities {
  runtime_modules: RuntimeModuleId[];
  public_endpoints: RuntimePublicEndpoint[];
  admin_endpoints: RuntimeAdminEndpoint[];
  feature_flag_endpoints: RuntimeFeatureFlagEndpoint[];
}

export interface RuntimeNamedRule {
  name: RuntimeInvariantName;
  statement: string;
}

export interface RuntimeExecutionModel {
  state_fields: RuntimeExecutionStateField[];
  allowed_transitions: RuntimeExecutionTransition[];
  validity_rules: RuntimeExecutionValidityRule[];
}

export interface RuntimeExternalNondeterminismPolicy {
  sources: RuntimeExternalNondeterminismSource[];
  rule: string;
  required_artifacts: RuntimeNondeterminismArtifact[];
  failure_codes: RuntimeFailureCode[];
}

export interface RuntimeArtifactLineageSchema {
  artifact_flow: RuntimeArtifactLineageStep[];
  required_node_fields: RuntimeLineageNodeField[];
  immutability_rule: string;
}

export interface RuntimeCapabilityEnums {
  side_effect_class: RuntimeSideEffectClass[];
  risk_level: RuntimeRiskLevel[];
  replayability: RuntimeReplayability[];
}

export interface RuntimeCapabilityAlgebraSchema {
  required_fields: RuntimeCapabilityField[];
  enums: RuntimeCapabilityEnums;
  rules: RuntimeCapabilityRule[];
}

export interface RuntimeLayerProofMatrixEntry {
  layer: RuntimeLayer;
  status: RuntimeMaturity;
  obligations: RuntimeProofObligation[];
  evidence_paths: string[];
}

export interface RuntimeBenchmarkClassEntry {
  code: RuntimeBenchmarkClassCode;
  description: string;
  evidence_paths: string[];
}

export interface RuntimeBenchmarkFramework {
  classes: RuntimeBenchmarkClassEntry[];
  required_metrics: RuntimeBenchmarkMetric[];
  baselines: RuntimeBenchmarkBaseline[];
}

export interface RuntimeSLOBudget {
  name: RuntimeSLOBudgetName;
  applies_to: RuntimeSLOBudgetAppliesTo;
  p95_objective_ms: number;
  hard_ceiling_ms?: number | null;
  notes?: string | null;
}

export interface RuntimeSchedulerModel {
  policies: RuntimeSchedulerPolicy[];
  minimize: RuntimeSchedulerMinimizeObjective[];
  maximize: RuntimeSchedulerMaximizeObjective[];
  invariants: RuntimeSchedulerInvariant[];
}

export interface RuntimeMemoryModel {
  regions: RuntimeMemoryRegion[];
  rules: RuntimeMemoryRule[];
  failure_codes: RuntimeFailureCode[];
}

export interface RuntimeEvaluationScience {
  dimensions: RuntimeEvaluationDimension[];
  methods: RuntimeEvaluationMethod[];
  release_blockers: RuntimeReleaseBlocker[];
}

export interface RuntimeThreatModel {
  threat_classes: RuntimeThreatClass[];
  controls: RuntimeThreatControl[];
  non_negotiable_rules: RuntimeThreatRule[];
}

export interface RuntimeTypedFailure {
  code: RuntimeFailureCode;
  description: string;
}

export interface RuntimeFormalReleaseTheorem {
  statement: string;
  required_conditions: RuntimeReleaseCondition[];
}

export interface RuntimeReleaseArtifactBundle {
  required_artifacts: RuntimeReleaseArtifact[];
}

export interface RuntimeReleaseGate {
  gate: RuntimeReleaseGateId;
  description: string;
}

export interface RuntimeImmediateImplementationPR {
  pr: string;
  focus: string;
  deliverables: string[];
}

export interface RuntimeAdminModuleSummary {
  module_count: number;
  function_count: number;
  maturity_counts: Partial<Record<RuntimeMaturity, number>>;
  layer_counts: Partial<Record<RuntimeLayer, number>>;
}

export interface RuntimeAdminModulesResponse {
  runtime_version: string;
  llm_core_manifest: string;
  module_manifest_version: string;
  shipping_contract: RuntimeShippingContractSummary;
  summary: RuntimeAdminModuleSummary;
  proof_matrix: RuntimeLayerProofMatrixEntry[];
  modules: RuntimeModuleManifestEntry[];
  manifest_digest: string;
  signature: RuntimeManifestSignature;
}

export interface RuntimeBenchmarkModuleEntry {
  name: RuntimeModuleId;
  function_count: number;
  benchmark_artifact: string;
  benchmark_speedup_x: number;
  compiled_artifact: string;
  compiled_engine: RuntimeCompiledEngine;
  max_cold_ms: number;
  max_warm_ms: number;
  max_hot_ms: number;
}

export interface RuntimeAdminBenchmarksResponse {
  runtime_version: string;
  llm_core_manifest: string;
  module_manifest_version: string;
  benchmark_discovery_lane: RuntimeBenchmarkDiscoveryLane;
  benchmarking: RuntimeBenchmarkFramework;
  slo_budgets: RuntimeSLOBudget[];
  quality_gate_benchmark_classes: RuntimeBenchmarkClassEntry[];
  quality_gate_slo_budgets: RuntimeSLOBudget[];
  evaluation_science: RuntimeEvaluationScience;
  evaluation_summary: RuntimeAdminEvaluationSummary;
  compiled_artifacts: RuntimeArtifactReference[];
  shipping_runtime_modules: RuntimeModuleId[];
  shipping_runtime_function_counts: number[];
  shipping_runtime_benchmark_speedups_x: number[];
  shipping_runtime_benchmark_artifacts: string[];
  shipping_runtime_compiled_artifacts: string[];
  shipping_runtime_compiled_engines: RuntimeCompiledEngine[];
  shipping_runtime_max_cold_ms: number[];
  shipping_runtime_max_warm_ms: number[];
  shipping_runtime_max_hot_ms: number[];
  module_benchmarks: RuntimeBenchmarkModuleEntry[];
  manifest_digest: string;
  signature: RuntimeManifestSignature;
}

export interface RuntimeAdminEvaluationSummary {
  dimension_count: number;
  method_count: number;
  release_blocker_count: number;
  benchmark_class_count: number;
  slo_budget_count: number;
  replay_gate_enabled: boolean;
  tool_call_quality_gate_enabled: boolean;
  rag_quality_gate_enabled: boolean;
  decision_quality_gate_enabled: boolean;
}

export interface ReleaseConditionEvaluation {
  condition: RuntimeReleaseCondition;
  satisfied: boolean;
  detail: string;
  evidence_paths: string[];
}

export interface RuntimeReleaseValidationResponse {
  runtime_version: string;
  llm_core_manifest: string;
  module_manifest_version: string;
  theorem_statement: string;
  valid_release: boolean;
  conditions: ReleaseConditionEvaluation[];
  deployment_mode: RuntimeDeploymentMode | null;
  deployment_mode_raw: string;
  manifest_digest: string;
  signature: RuntimeManifestSignature;
}

export interface RuntimeManifestResponse {
  runtime_version: string;
  mojo_version: string;
  llm_core_manifest: string;
  module_manifest_version: string;
  generated_at: string;
  modules: RuntimeModuleManifestEntry[];
  compiled_artifacts: RuntimeArtifactReference[];
  supported_channels: RuntimeSupportedChannel[];
  validated_auxiliary_channels: RuntimeAuxiliaryChannel[];
  feature_flag_channels: RuntimeFeatureFlagChannel[];
  maturity: Partial<Record<RuntimeModuleId, RuntimeMaturity>>;
  policy_snapshot: RuntimeSnapshotReference;
  schema_snapshot: RuntimeSnapshotReference;
  deployment_mode: RuntimeDeploymentMode;
  deployment_modes: RuntimeDeploymentModes;
  shipping_contract: RuntimeShippingContractSummary;
  benchmark_discovery_lane: RuntimeBenchmarkDiscoveryLane;
  advertised_capabilities: RuntimeAdvertisedCapabilities;
  system_invariants: RuntimeNamedRule[];
  execution_model: RuntimeExecutionModel;
  external_nondeterminism: RuntimeExternalNondeterminismPolicy;
  artifact_lineage: RuntimeArtifactLineageSchema;
  capability_algebra: RuntimeCapabilityAlgebraSchema;
  kernel_promotion_criteria: RuntimeKernelPromotionCriteria;
  proof_matrix: RuntimeLayerProofMatrixEntry[];
  benchmarking: RuntimeBenchmarkFramework;
  slo_budgets: RuntimeSLOBudget[];
  scheduler_model: RuntimeSchedulerModel;
  memory_model: RuntimeMemoryModel;
  evaluation_science: RuntimeEvaluationScience;
  typed_failures: RuntimeTypedFailure[];
  threat_model: RuntimeThreatModel;
  formal_release_theorem: RuntimeFormalReleaseTheorem;
  release_artifact_bundle: RuntimeReleaseArtifactBundle;
  release_gates: RuntimeReleaseGate[];
  immediate_implementation_sequence: RuntimeImmediateImplementationPR[];
  manifest_digest: string;
  signature: RuntimeManifestSignature;
}

export interface QueryBatchDefaults {
  dataset_id?: string | null;
  filter?: QueryFilterSpec | null;
  limit?: number | null;
  order?: "asc" | "desc" | null;
}

export interface QueryBatchItemRequest {
  key: string;
  request: Record<string, unknown>;
}

export interface QueryBatchItemError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface QueryBatchItemResponse {
  key: string;
  data?: QueryResponse | null;
  metadata?: QueryExecutionMetadata | null;
  error?: QueryBatchItemError | null;
}

export interface QueryBatchResponse {
  results: QueryBatchItemResponse[];
  request_id?: string | null;
}

export interface VerifyResponse {
  valid: boolean;
  errors: string[];
  suggestions: string[];
  resolved: Record<string, string>;
  valid_dimensions?: string[];
  valid_measures?: string[];
  source_behavior?: string;
  latency_ms: number;
  verified?: boolean;
  request_id?: string | null;
  schema_revision?: string | null;
  plan_hash?: string | null;
  verification_mode?: string;
  rejection_reason?: string | null;
}

export interface SourceRegistrationRequest {
  source: Record<string, unknown>;
  description?: string;
}

/** Coarse per-field type inferred at local connect() time. Inference rules are
 * shared verbatim with the Python SDK (conformance-tested cross-language). */
export type TypedFieldType = "number" | "string" | "boolean" | "date" | "unknown";

export interface TypedField {
  name: string;
  type: TypedFieldType;
}

export interface SourceRegistrationResponse {
  source_id?: string | null;
  dataset_id?: string | null;
  name?: string | null;
  dataset_name?: string | null;
  status: string;
  ingest_mode?: string | null;
  schema?: Record<string, unknown> | null;
  source_schema?: Record<string, unknown> | null;
  planner_cache_hit?: boolean | null;
  planner_schema_revision?: string | null;
  planner_prewarm_ms?: number | null;
  latency_ms?: number | null;
  row_count?: number | null;
  typed_fields?: TypedField[] | null;
  [key: string]: unknown;
}

/** Aligned numeric column extraction result — mirrors the Python SDK's
 * ColumnExtract dataclass exactly (conformance-tested cross-language). */
export interface ColumnExtractResult {
  columns: Record<string, Array<number | null>>;
  row_count: number;
  source_name: string;
  schema_revision: string;
  alignment: "rowwise";
  input_hash: string;
}

export interface CreateConnectorRequest {
  name: string;
  connector_type: string;
  config?: Record<string, unknown> | null;
  description?: string | null;
  visibility?: string | null;
}

export interface UpdateConnectorRequest {
  name?: string | null;
  description?: string | null;
  visibility?: string | null;
  config?: Record<string, unknown> | null;
}

export interface PreviewConnectorRequest {
  connector_type: string;
  config?: Record<string, unknown> | null;
}

export interface RepositoryDiagnostic {
  path?: string | null;
  line?: number | null;
  severity?: "info" | "warning" | "error";
  code?: string | null;
  message: string;
}

export interface RepositorySignals {
  issue_text?: string | null;
  diagnostics?: RepositoryDiagnostic[];
  failing_tests?: string[];
  changed_files?: string[];
  workspace_context?: string[];
}

export interface RepositorySnapshotCreateRequest {
  ref?: string | null;
  include_patterns?: string[];
  exclude_patterns?: string[];
  max_files?: number;
  max_file_size_bytes?: number;
}

export interface RepositoryLanguageSupportProgressResponse {
  supported_real_language_count: number;
  ranked_target_language_count: number;
  progress_fraction: number;
  progress_label: string;
}

export interface RepositoryIntelligenceCapabilitiesResponse {
  supported_languages: string[];
  support_progress: RepositoryLanguageSupportProgressResponse;
}

export interface RepositoryTriageRequest {
  snapshot_id: string;
  signals: RepositorySignals;
  max_evidence_items?: number;
  max_snippet_lines?: number;
  token_budget?: number;
}

export interface RepositoryDecisionPlanCreateRequest {
  snapshot_id?: string | null;
  workspace_evidence_bundle_ref: string;
  model?: string | null;
}

export interface RepositoryGraphQueryRequest {
  snapshot_id?: string | null;
  file_path?: string | null;
  symbol_name?: string | null;
  workspace_evidence_bundle_ref?: string | null;
  direction?: "inbound" | "outbound" | "both";
  max_depth?: number;
  max_nodes?: number;
}

