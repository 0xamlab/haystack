/**
 * TypeScript type definitions for the Algenta API.
 */

import type { CAPABILITY_PLANE_CONTRACT, PRIMARY_DATA_QUERY_CONTRACT } from "./contract.js";

// ─── Request Types ─────────────────────────────────────────────────────────

export interface AutoVariable {
  low: number;
  high: number;
  description?: string;
}

export type ObjectiveType =
  | "maximize_net_value"
  | "maximize_revenue"
  | "minimize_cost"
  | "minimize_risk"
  | "maximize_score";

export interface AutoScenario {
  name?: string;
  variables: Record<string, AutoVariable>;
  objective: ObjectiveType;
}

export interface AutoSimulateRequest {
  mode: "auto";
  scenario: AutoScenario;
  runs?: number;
  seed?: number;
}

export type DistributionType =
  | "normal"
  | "lognormal"
  | "uniform"
  | "triangular"
  | "beta"
  | "gamma"
  | "exponential"
  | "poisson"
  | "binomial"
  | "negative_binomial"
  | "geometric"
  | "hypergeometric"
  | "weibull"
  | "pareto"
  | "cauchy"
  | "laplace"
  | "logistic"
  | "chi_squared"
  | "student_t"
  | "f_distribution"
  | "dirichlet"
  | "multivariate_normal"
  | "halfnormal"
  | "truncated_normal"
  | "pert"
  | "lomax"
  | "fixed"
  | string;  // Forward-compatible — new distributions added without breaking changes

export interface DistributionParams {
  mean?: number;
  std?: number;
  low?: number;
  high?: number;
  mode?: number;
  value?: number;
  [key: string]: number | undefined;
}

export interface VariableSpec {
  name: string;
  distribution: DistributionType;
  params: DistributionParams;
  unit?: string;
}

export interface ScoringWeights {
  expected_value?: number;
  downside_risk?: number;
}

export interface ExpertSimulation {
  variables: VariableSpec[];
  correlations?: Array<{ variables: [string, string]; coefficient: number }>;
  objective_function?: string;
  scoring?: ScoringWeights;
}

export interface ExpertSimulateRequest {
  mode: "expert";
  simulation: ExpertSimulation;
  runs?: number;
  seed?: number;
}

export type SimulateRequest = AutoSimulateRequest | ExpertSimulateRequest;

export interface ChatCompletionInputMessage {
  role: "system" | "user" | "assistant" | "developer";
  content: string;
}

export interface ChatCompletionsRequest {
  model?: string;
  messages: ChatCompletionInputMessage[];
  stream?: boolean;
}

export interface TokenizeRequest {
  model?: string;
  input: string;
}

export interface CountTokensRequest {
  model?: string;
  input: string;
}

export interface ArtifactBridgeResolveRequest {
  repo_id: string;
  filename: string;
  revision?: string | null;
  local_files_only?: boolean;
}

export interface ArtifactBridgeResolveResponse {
  object: "artifact_bridge_resolution";
  backend: string;
  artifact_backend?: string | null;
  repo_id: string;
  filename: string;
  revision?: string | null;
  local_files_only: boolean;
  status: "resolved" | "not_cached";
  cache_root?: string | null;
  auth_env_vars: string[];
  auth_configured: boolean;
  auth_env_var_used?: string | null;
  resolved_path?: string | null;
}

export interface ResponsesRequest {
  model?: string;
  input: string | string[];
  dimensions?: number;
  stream?: boolean;
}

export interface EmbeddingsRequest {
  model?: string;
  input: string | string[];
  dimensions?: number;
}

export interface EmbeddingSimilarityRequest {
  model?: string;
  left: number[];
  right: number[];
}

export interface RerankDocumentInput {
  id: string;
  embedding: number[];
  text?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface RerankRequest {
  model?: string;
  query_embedding: number[];
  documents: RerankDocumentInput[];
  top_n?: number | null;
}

export type AgentRunAction = "auto" | "manual";
export type AgentRunStatus = "running" | "paused" | "requires_approval" | "completed" | "cancelled";
export type AgentRunPendingAction = "resume" | "approve" | null;

export interface AgentRunCreateRequest {
  task: string;
  context?: Record<string, unknown> | null;
  tools?: string[] | null;
  max_steps?: number;
  output_format?: string;
  approval_mode?: AgentRunAction;
  start_paused?: boolean;
}

export interface ProductDecisionInput {
  name: string;
  value: number;
  low?: number | null;
  high?: number | null;
  unit?: string | null;
}

export interface ProductDecisionRequest {
  inputs: ProductDecisionInput[];
  objective?: string;
  risk_tolerance?: string;
  scenarios?: number;
  engine?: string;
  label?: string | null;
}

export interface ProductAgentRunRequest {
  task: string;
  context?: Record<string, unknown> | null;
  tools?: string[] | null;
  max_steps?: number;
  output_format?: string;
}

export interface ProductOptimizeVariable {
  name: string;
  min: number;
  max: number;
  step?: number | null;
  unit?: string | null;
}

export interface ProductOptimizeConstraint {
  expression: string;
  required?: boolean;
}

export interface ProductOptimizeRequest {
  objective: string;
  variables: ProductOptimizeVariable[];
  constraints?: ProductOptimizeConstraint[];
  iterations?: number;
  engine?: string;
}

export interface ProductRetrieveDocumentInput {
  id?: string | null;
  content: string;
  metadata?: Record<string, unknown> | null;
}

export interface ProductRetrieveRequest {
  query: string;
  documents?: ProductRetrieveDocumentInput[] | null;
  collection_id?: string | null;
  top_k?: number;
  rerank?: boolean;
}

export interface ProductForecastRequest {
  metric: string;
  history: number[];
  horizon?: number;
  seasonality?: boolean;
  confidence_level?: number;
}

// ─── Response Types ────────────────────────────────────────────────────────

export interface MetricsSummary {
  expected_value: number;
  median: number;
  std_deviation: number;
  variance: number;
  probability_of_loss: number;
  var_95?: number | null;
  cvar_95?: number | null;
}

export interface PercentileSummary {
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
}

export interface RunMetadata {
  mode: string;
  seed?: number | null;
  billing_units: number;
  engine_version: string;
}

export interface DecisionEnvelope {
  run_id: string;
  status: string;
  engine_version: string;
  recommended_action: string;
  confidence: number;
  rationale: string;
  metrics: MetricsSummary;
  percentiles: PercentileSummary;
  scenarios_run: number;
  execution_ms: number;
  metadata: RunMetadata;
  simulation_model?: string | null;
  engine_type?: string | null;
  simulation_class?: string | null;
  model_revision?: string | null;
  assumptions_hash?: string | null;
  validated_inputs?: Record<string, unknown> | null;
  confidence_interval?: Record<string, unknown> | null;
  request_id?: string | null;
  score?: number | null;
  score_breakdown?: Record<string, unknown> | null;
  scenario_ranking?: Array<Record<string, unknown>> | null;
  sensitivity_ranking?: Array<Record<string, unknown>> | null;
  request_hash?: string | null;
  result_hash?: string | null;
  created_at?: string | null;
  decision_plan?: DecisionPlanResponse | null;
}

export interface RiskProfileResponse {
  p5: number;
  p95: number;
  probability_of_loss: number;
  var_95?: number | null;
}

export interface DecisionOptionResponse {
  name: string;
  rank: number;
  expected_value: number;
  risk: RiskProfileResponse;
  score?: number | null;
}

export interface TokenReductionMetricsResponse {
  raw_repo_token_estimate: number;
  evidence_bundle_token_count: number;
  reduction_ratio: number;
}

export interface RepositoryAnalysisResponse {
  root_cause: string;
  planner_model_id: string;
  planner_execution_mode: string;
  planner_provider_backend?: string | null;
  candidate_fixes: string[];
  impacted_services: string[];
  impacted_symbols: string[];
  likely_failing_tests: string[];
  rollback_complexity: string;
  blast_radius: string;
  workspace_evidence_refs: string[];
  generated_patch_ref?: string | null;
  patch_impact_report_ref?: string | null;
  token_reduction_metrics: TokenReductionMetricsResponse;
}

export interface DecisionPlanResponse {
  recommended_action: string;
  confidence: number;
  expected_value: number;
  risk: RiskProfileResponse;
  options: DecisionOptionResponse[];
  rationale: string;
  integrity?: Record<string, unknown> | null;
  calibration?: string | null;
  repository_analysis?: RepositoryAnalysisResponse | null;
}

export interface ProductDecisionResponse {
  decision_id: string;
  action: string;
  confidence: number;
  reasoning: string;
  why: string[];
  expected_outcome: number;
  downside_risk: number;
  upside_potential: number;
  probability_of_loss: number;
  scenarios_evaluated: number;
  latency_ms: number;
}

export interface ProductAgentStepResponse {
  step: number;
  action: string;
  tool?: string | null;
  result?: string | null;
  status: string;
}

export interface ProductAgentRunResponse {
  run_id: string;
  status: string;
  result: string | Record<string, unknown>;
  steps: ProductAgentStepResponse[];
  tools_used: string[];
  latency_ms: number;
}

export interface ProductOptimizeResponse {
  optimization_id: string;
  status: string;
  optimal_values: Record<string, number>;
  objective_value: number;
  improvement_vs_midpoint: number;
  constraints_satisfied: boolean;
  iterations_run: number;
  latency_ms: number;
}

export interface ProductRetrieveHitResponse {
  rank: number;
  document_id?: string | null;
  content: string;
  relevance_score: number;
  snippet: string;
}

export interface ProductRetrieveResponse {
  retrieval_id: string;
  query: string;
  results: ProductRetrieveHitResponse[];
  total_searched: number;
  latency_ms: number;
}

export interface ProductForecastPeriodResponse {
  period: number;
  forecast: number;
  lower_bound: number;
  upper_bound: number;
  trend: string;
}

export interface ProductForecastResponse {
  forecast_id: string;
  metric: string;
  baseline: number;
  forecast_mean: number;
  total_change_pct: number;
  periods: ProductForecastPeriodResponse[];
  scenarios_evaluated: number;
  latency_ms: number;
}

export interface LogDecisionRequest {
  run_id?: string | null;
  context?: string | null;
  chosen_action: string;
  options_considered?: string[] | null;
  expected_value?: number | null;
  confidence?: number | null;
  rationale?: string | null;
  risk_p5?: number | null;
  risk_p95?: number | null;
  risk_pol?: number | null;
  request_hash?: string | null;
  result_hash?: string | null;
}

export interface RecordOutcomeRequest {
  actual_outcome: number;
  outcome_notes?: string | null;
}

export interface ExecuteDecisionRequest {
  webhook_url: string;
  timeout_seconds?: number;
  force?: boolean;
  override_safety?: boolean;
  metadata?: Record<string, unknown> | null;
}

export interface DecisionLogResponse {
  id: string;
  org_id: string;
  run_id?: string | null;
  context?: string | null;
  chosen_action: string;
  options_considered?: string[] | null;
  expected_value?: number | null;
  confidence?: number | null;
  rationale?: string | null;
  risk_p5?: number | null;
  risk_p95?: number | null;
  risk_pol?: number | null;
  request_hash?: string | null;
  result_hash?: string | null;
  policy_snapshot_id?: string | null;
  schema_snapshot_id?: string | null;
  manifest_version?: string | null;
  actual_outcome?: number | null;
  outcome_delta?: number | null;
  outcome_notes?: string | null;
  outcome_recorded_at?: string | null;
  executed_at?: string | null;
  execution_status?: string | null;
  execution_webhook_url?: string | null;
  execution_response_code?: number | null;
  created_at: string;
  updated_at: string;
}

export interface DecisionListResponse {
  decisions: DecisionLogResponse[];
  total: number;
  page: number;
  limit: number;
  pages: number;
  page_size: number;
}

export interface ExecutionReceiptResponse {
  decision_id: string;
  webhook_url: string;
  execution_status: string;
  response_code?: number | null;
  executed_at: string;
  policy_snapshot_id: string;
  schema_snapshot_id: string;
  manifest_version: string;
  payload_summary: Record<string, unknown>;
  safety_overridden: boolean;
}

export interface NamedSimulationAction {
  name: string;
  request: SimulateRequest;
}

export interface RecommendActionResult {
  name: string;
  rank: number;
  envelope: DecisionEnvelope;
  expected_value: number;
  probability_of_loss: number;
  score: number;
}

export interface RecommendResponse {
  recommended_action: string;
  confidence: number;
  rationale: string;
  action_results: RecommendActionResult[];
  total_actions: number;
  decision_plan?: DecisionPlanResponse | null;
}

export interface ScoreResponse {
  envelope: DecisionEnvelope;
  score: number;
  score_breakdown: Record<string, number>;
}

export interface ComparisonDelta {
  expected_value_delta: number;
  probability_of_loss_delta: number;
  score_delta: number;
}

export interface ScenarioComparison {
  name: string;
  envelope: DecisionEnvelope;
  delta_vs_best: ComparisonDelta;
}

export interface CompareResponse {
  winner: string;
  margin: ComparisonDelta;
  scenarios: ScenarioComparison[];
}

export interface LLMModelResponse {
  id: string;
  object: "model";
  owned_by: string;
  runtime_module: string;
  description: string;
  capabilities: string[];
  supported_endpoints: string[];
  runtime_functions: string[];
  tokenizer_kind: string | null;
  similarity_metric: string | null;
  provider_backend: string | null;
  routing_targets: string[];
  resolved_routing_targets: string[];
  chat_routing_targets: string[];
  resolved_chat_routing_targets: string[];
  embedding_routing_targets: string[];
  resolved_embedding_routing_targets: string[];
  routing_fallback_policy: string | null;
  chat_routing_fallback_policy: string | null;
  embedding_routing_fallback_policy: string | null;
  routing_fallback_on: string[];
  chat_routing_fallback_on: string[];
  embedding_routing_fallback_on: string[];
  routing_max_attempts: number | null;
  chat_routing_max_attempts: number | null;
  embedding_routing_max_attempts: number | null;
  timeout_seconds: number | null;
  chat_timeout_seconds: number | null;
  embedding_timeout_seconds: number | null;
  required_provider_headers: string[];
  chat_required_provider_headers: string[];
  embedding_required_provider_headers: string[];
  provider_auth_env_vars: string[];
  chat_provider_auth_env_vars: string[];
  embedding_provider_auth_env_vars: string[];
  provider_auth_configured: boolean;
  chat_provider_auth_configured: boolean;
  embedding_provider_auth_configured: boolean;
  bridge_cache_root: string | null;
  bridge_auth_env_vars: string[];
  bridge_auth_configured: boolean;
  bridge_tokenizer_backends: string[];
  bridge_artifact_backends: string[];
  available: boolean;
}

export interface LLMModelListResponse {
  object: "list";
  data: LLMModelResponse[];
}

export interface TokenizeResponse {
  object: "tokenization";
  model: string;
  tokenizer_kind: string;
  tokens: string[];
  token_count: number;
}

export interface CountTokensResponse {
  object: "token_count";
  model: string;
  tokenizer_kind: string;
  token_count: number;
}

export interface ChatCompletionOutputMessage {
  role: "assistant";
  content: string;
}

export interface ChatCompletionChoice {
  index: number;
  finish_reason: "stop";
  message: ChatCompletionOutputMessage;
}

export interface ChatCompletionUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface ProviderAttemptResponse {
  provider_backend: string;
  provider_model_id: string;
  outcome: "selected" | "failed";
  error_code?: string | null;
}

export interface ChatCompletionsResponse {
  id: string;
  object: "chat.completion";
  model: string;
  provider_backend: string | null;
  provider_model_id: string | null;
  provider_attempts: ProviderAttemptResponse[];
  choices: ChatCompletionChoice[];
  usage: ChatCompletionUsage;
}

export interface ChatCompletionChunkDelta {
  role?: "assistant" | null;
  content?: string | null;
}

export interface ChatCompletionChunkChoice {
  index: number;
  delta: ChatCompletionChunkDelta;
  finish_reason?: "stop" | null;
}

export interface ChatCompletionsStreamChunkResponse {
  id: string;
  object: "chat.completion.chunk";
  model: string;
  provider_backend: string | null;
  provider_model_id: string | null;
  provider_attempts: ProviderAttemptResponse[];
  choices: ChatCompletionChunkChoice[];
}

export interface EmbeddingVectorResponse {
  object: "embedding";
  index: number;
  embedding: number[];
  token_count: number;
}

export interface EmbeddingUsageResponse {
  prompt_tokens: number;
  total_tokens: number;
}

export interface EmbeddingsResponse {
  object: "list";
  model: string;
  dimensions: number;
  provider_backend: string | null;
  provider_model_id: string | null;
  provider_attempts: ProviderAttemptResponse[];
  data: EmbeddingVectorResponse[];
  usage: EmbeddingUsageResponse;
}

export interface ResponseOutputContent {
  type: "tokenization" | "embedding" | "text";
  text: string;
  tokens?: string[] | null;
  token_count: number;
  embedding?: number[] | null;
}

export interface ResponseOutputItem {
  id: string;
  object: "response.output";
  index: number;
  provider_backend: string | null;
  provider_model_id: string | null;
  provider_attempts: ProviderAttemptResponse[];
  content: ResponseOutputContent[];
}

export interface ResponsesResponse {
  id: string;
  object: "response";
  status: "completed";
  model: string;
  provider_backend: string | null;
  provider_model_id: string | null;
  provider_attempts: ProviderAttemptResponse[];
  output: ResponseOutputItem[];
  usage: EmbeddingUsageResponse;
}

export interface ResponseLifecycleResponse {
  id: string;
  object: "response";
  status: "in_progress" | "completed";
  model: string;
  provider_backend: string | null;
  provider_model_id: string | null;
  provider_attempts: ProviderAttemptResponse[];
  usage?: EmbeddingUsageResponse | null;
}

export interface ResponseStreamEventResponse {
  type: "response.created" | "response.output_item.done" | "response.completed";
  response?: ResponseLifecycleResponse | null;
  output_index?: number | null;
  item?: ResponseOutputItem | null;
}

export interface EmbeddingSimilarityResponse {
  object: "embedding_similarity";
  model: string;
  similarity_metric: string;
  score: number;
  dimension: number;
}

export interface RerankResult {
  object: "rerank_result";
  id: string;
  index: number;
  rank: number;
  score: number;
  text?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface RerankResponse {
  object: "list";
  model: string;
  similarity_metric: string;
  total_documents: number;
  returned_documents: number;
  data: RerankResult[];
}

export interface AgentStepResponse {
  step_number: number;
  tool_name?: string | null;
  action?: string | null;
  result?: string | null;
  status?: string | null;
  input?: Record<string, unknown> | null;
  output?: Record<string, unknown> | null;
  rationale?: string | null;
}

export interface AgentRunResponse {
  run_id: string;
  status: AgentRunStatus;
  task: string;
  output_format: string;
  approval_mode: AgentRunAction;
  pending_action: AgentRunPendingAction;
  selected_tool?: string | null;
  result?: string | Record<string, unknown> | null;
  tools_available: string[];
  tools_used: string[];
  steps: AgentStepResponse[];
  request_hash?: string | null;
  decision_hash?: string | null;
  policy_snapshot_id?: string | null;
  schema_snapshot_id?: string | null;
  manifest_version?: string | null;
  replayable?: boolean;
  artifact_refs?: string[];
  latest_checkpoint_id?: string | null;
  checkpoint_count?: number;
  source_run_id?: string | null;
  source_checkpoint_id?: string | null;
  created_at: string;
  updated_at: string;
  latency_ms?: number | null;
}

export interface AgentRunListResponse {
  object: string;
  data: AgentRunResponse[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface AgentRunEventResponse {
  event_id: string;
  event_type: string;
  status: string;
  message: string;
  created_at: string;
  details: Record<string, unknown>;
}

export interface AgentRunEventsResponse {
  object: string;
  run_id: string;
  data: AgentRunEventResponse[];
  total_events: number;
}

export interface AgentRunMissionEventResponse {
  mission_id: string;
  thread_id: string;
  tenant_scope: string;
  workspace_scope: string;
  event_index: number;
  superstep: number;
  node_name: string;
  event_type: string;
  event_message?: string | null;
  details_json?: string | null;
  event_ts: string;
  request_hash: string;
  policy_snapshot_id: string;
  schema_snapshot_id: string;
  manifest_version: string;
  checkpoint_id?: string | null;
  artifact_refs: string[];
  failure_code?: string | null;
  latency_ms?: number | null;
  cost_usd_micros?: number | null;
}

export interface AgentRunMissionEventsResponse {
  object: string;
  run_id: string;
  data: AgentRunMissionEventResponse[];
  total_events: number;
}

export interface AgentRunMissionEventListEntry extends AgentRunMissionEventResponse {
  run_id: string;
  run_status: AgentRunStatus;
}

export interface AgentRunMissionEventListResponse {
  object: string;
  data: AgentRunMissionEventListEntry[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface AgentRunStreamEventResponse {
  type: "agent.run.event" | "agent.run.completed";
  run_id: string;
  event?: AgentRunEventResponse | null;
  status?: AgentRunStatus | null;
  total_events?: number | null;
}

export interface AgentRunCheckpointResponse {
  checkpoint_id: string;
  checkpoint_index: number;
  run_id: string;
  parent_checkpoint_id?: string | null;
  status: AgentRunStatus;
  event_start_index: number;
  event_end_index: number;
  request_hash: string;
  decision_hash: string;
  content_hash: string;
  policy_snapshot_id: string;
  schema_snapshot_id: string;
  manifest_version: string;
  artifact_refs: string[];
  created_at: string;
}

export interface AgentRunCheckpointListEntry extends AgentRunCheckpointResponse {
  run_status: AgentRunStatus;
}

export interface AgentRunCheckpointsResponse {
  object: string;
  run_id: string;
  data: AgentRunCheckpointResponse[];
  total_checkpoints: number;
}

export interface AgentRunCheckpointListResponse {
  object: string;
  data: AgentRunCheckpointListEntry[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export type AgentRunReplayStatus = "matched" | "mismatch";

export interface AgentRunReplayResponse {
  object: "agent_run_replay";
  run_id: string;
  checkpoint_id: string;
  replay_status: AgentRunReplayStatus;
  compared_event_count: number;
  checkpoint_count: number;
  request_hash: string;
  decision_hash: string;
  content_hash: string;
  policy_snapshot_id: string;
  schema_snapshot_id: string;
  manifest_version: string;
  failure_code?: string | null;
  created_at: string;
}

export interface AgentRunTelemetryBatchResponse {
  batch_id: string;
  telemetry_kind: string;
  module_name: string;
  tenant_scope: string;
  request_hash: string;
  started_at: string;
  ended_at: string;
  success_count: number;
  failure_count: number;
  latency_ms_p95: number;
  cost_usd_micros: number;
}

export interface AgentRunTelemetryResponse {
  object: string;
  run_id: string;
  data: AgentRunTelemetryBatchResponse[];
  total_batches: number;
}

export interface AgentRunTelemetryBatchListEntry extends AgentRunTelemetryBatchResponse {
  run_id: string;
  run_status: AgentRunStatus;
}

export interface AgentRunTelemetryListResponse {
  object: string;
  data: AgentRunTelemetryBatchListEntry[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

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

export type RuntimeAuxiliaryChannel = "daemon_client" | "runtime_local";

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
  [key: string]: unknown;
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

export interface RepositorySimulationRequest {
  snapshot_id?: string | null;
  decision_plan_id: string;
  runs?: number;
  seed?: number | null;
}

export type RepositoryApplyMode = "patch_only" | "local_branch" | "remote_pr";

export interface RepositoryApplyRequest {
  snapshot_id?: string | null;
  decision_plan_id: string;
  simulation_id: string;
  mode: RepositoryApplyMode;
  write_permission?: boolean;
  branch_name?: string | null;
  commit_message?: string | null;
  base_branch?: string | null;
  pull_request_title?: string | null;
  pull_request_body?: string | null;
}

export interface ConnectorInfo {
  id: string;
  name: string;
  description?: string | null;
  connector_type: string;
  status: string;
  visibility: string;
  last_tested_at?: string | null;
  error_message?: string | null;
  created_at?: string | null;
  [key: string]: unknown;
}

export interface ConnectorListResult {
  connectors: ConnectorInfo[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface ConnectorTestInfo {
  success: boolean;
  message: string;
  latency_ms?: number | null;
  status?: string | null;
  error_type?: string | null;
  recoverable?: boolean | null;
  [key: string]: unknown;
}

export interface ConnectorBrowseResult {
  connector_type: string;
  items: Array<Record<string, unknown>>;
  total: number;
  message: string;
  labels: Record<string, unknown>;
  discovery: Record<string, unknown>;
  connection_id?: string | null;
  [key: string]: unknown;
}

export interface RepositoryArtifactRefResponse {
  artifact_id: string;
  artifact_kind: string;
  content_hash: string;
  storage_path: string;
  schema_revision?: string | null;
  created_at: string;
}

export interface RepositorySnapshotResponse {
  repository_id: string;
  snapshot_id: string;
  connector_type: string;
  ref?: string | null;
  resolved_revision: string;
  content_hash: string;
  status: "created" | "existing";
  created_at: string;
  file_count: number;
  language_counts: Record<string, number>;
  raw_repo_token_estimate: number;
  repository_snapshot_artifact: RepositoryArtifactRefResponse;
  repository_graph_artifact: RepositoryArtifactRefResponse;
  symbol_graph_artifact: RepositoryArtifactRefResponse;
  dependency_graph_artifact: RepositoryArtifactRefResponse;
}

export interface RepositoryEvidenceItemResponse {
  evidence_id: string;
  rank: number;
  source_type:
    | "diagnostic"
    | "failing_test"
    | "changed_file"
    | "workspace_context"
    | "repository_file";
  source_ref: string;
  file_path?: string | null;
  symbol_name?: string | null;
  summary: string;
  snippet: string;
  token_count: number;
  score: number;
}

export interface RepositoryTriageResponse {
  repository_id: string;
  snapshot_id: string;
  workspace_evidence_bundle_ref: string;
  created_at: string;
  suspect_files: string[];
  suspect_symbols: string[];
  raw_repo_token_estimate: number;
  evidence_bundle_token_count: number;
  reduction_ratio: number;
  evidence_items: RepositoryEvidenceItemResponse[];
  workspace_evidence_bundle_artifact: RepositoryArtifactRefResponse;
}

export interface RepositoryDecisionPlanRevisionResponse {
  repository_id: string;
  snapshot_id: string;
  decision_plan_id: string;
  created_at: string;
  decision_plan: DecisionPlanResponse;
}

export interface RepositoryGraphEdgeResponse {
  source_file: string;
  target_file: string;
  edge_type: string;
}

export interface RepositoryGraphNodeResponse {
  file_path: string;
  depth: number;
  is_seed: boolean;
  inbound_count: number;
  outbound_count: number;
  risk_score: number;
  contained_symbols: string[];
  parent_child_symbols: string[];
}

export interface RepositoryGraphImpactItemResponse {
  file_path: string;
  depth: number;
  relationship: "seed" | "dependent" | "dependency" | "connected";
  risk_score: number;
  top_symbol?: string | null;
}

export interface RepositoryGraphQueryResponse {
  repository_id: string;
  snapshot_id: string;
  created_at: string;
  seed_file_paths: string[];
  seed_symbols: string[];
  direct_dependencies: string[];
  direct_dependents: string[];
  impacted_files: string[];
  impacted_symbols: string[];
  graph_nodes: RepositoryGraphNodeResponse[];
  graph_edges: RepositoryGraphEdgeResponse[];
  top_change_risk_files: RepositoryGraphImpactItemResponse[];
}

export interface RepositoryApplyResponse {
  repository_id: string;
  snapshot_id: string;
  decision_plan_id: string;
  simulation_id: string;
  mode: RepositoryApplyMode;
  applied: boolean;
  created_at: string;
  patch: string;
  branch_name?: string | null;
  commit_sha?: string | null;
  local_checkout_path?: string | null;
  pull_request_url?: string | null;
  apply_gate: Record<string, unknown>;
  validation_summary: Record<string, unknown>;
}

export interface ConnectDataRequest {
  connection_type?: string | null;
  dataset_name: string;
  provider?: string | null;
  connector?: Record<string, unknown> | null;
  connection_id?: string | null;
  connection_name?: string | null;
  connection_config?: Record<string, unknown> | null;
  selection?: Record<string, unknown> | null;
  description?: string | null;
  visibility?: string | null;
  records?: Array<Record<string, unknown>> | null;
  csv?: string | null;
  json_str?: string | null;
  url?: string | null;
  excel_b64?: string | null;
  parquet_b64?: string | null;
  [key: string]: unknown;
}

export interface DatasetInfo {
  dataset_id: string;
  name?: string | null;
  source_id?: string | null;
  dataset_name: string;
  status?: string | null;
  source_names?: string[];
  source_name?: string | null;
  description?: string | null;
  connection_id?: string | null;
  connection_type?: string | null;
  provider?: string | null;
  visibility?: string | null;
  owner_user_id?: string | null;
  owner_key_id?: string | null;
  refreshable?: boolean | null;
  row_count?: number | null;
  column_count?: number | null;
  columns?: number | null;
  roles_summary?: Record<string, unknown>;
  discovery_labels?: Record<string, unknown> | null;
  discovery_metadata?: Record<string, unknown> | null;
  registered_at?: string | null;
  selection?: Record<string, unknown> | null;
  [key: string]: unknown;
}

export interface DatasetListResult {
  datasets: DatasetInfo[];
  count: number;
  total: number;
  matched_total?: number | null;
  page: number;
  limit: number;
  pages: number;
}

export interface DatasetSummaryResult {
  dataset_id: string;
  name: string;
  status: string;
  source_names: string[];
  row_count?: number | null;
  column_count: number;
  registered_at?: string | null;
  query_hints: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

export interface DatasetDetailResult {
  dataset: DatasetInfo;
  schema: Record<string, unknown>;
  [key: string]: unknown;
}

export interface DatasetDeleteResult {
  dataset_id: string;
  status: string;
  connection_deleted: boolean;
  [key: string]: unknown;
}

export interface DatasetConnectResult {
  status: string;
  dataset_id?: string | null;
  source_id?: string | null;
  dataset_name?: string | null;
  schema?: Record<string, unknown> | null;
  schema_summary?: Record<string, unknown> | null;
  connection_id?: string | null;
  connection_type?: string | null;
  provider?: string | null;
  labels?: Record<string, unknown> | null;
  discovery?: Record<string, unknown> | null;
  visibility?: string | null;
  selection?: Record<string, unknown> | null;
  refreshable?: boolean | null;
  latency_ms?: number | null;
  message?: string | null;
  choices?: Array<Record<string, unknown>> | null;
  [key: string]: unknown;
}

export interface QuerySqlReportSource {
  dataset_id: string;
  alias?: string | null;
}

export interface QuerySqlReportRequest {
  sources: QuerySqlReportSource[];
  sql: string;
  max_rows?: number | null;
}

export interface QuerySqlReportResponse {
  columns: string[];
  rows: Array<Record<string, unknown>>;
  row_count: number;
  truncated: boolean;
  request_id?: string | null;
  latency_ms: number;
}

export interface ExplainResponse {
  source_set: string[];
  join_path: Array<Record<string, unknown>>;
  planner_mode: string;
  decision_path: string;
  plan_hash?: string | null;
  schema_revision?: string | null;
  validated: boolean;
  clarification_required?: boolean;
  rejection_reason?: string | null;
  resolved_source: string;
  resolved_column: string;
  resolved_role: string;
  confidence: number;
  confidence_source?: string | null;
  deterministic_scope?: string | null;
  plan: string[];
  explanation: string[];
  request_id?: string | null;
}

export interface JobStatusResponse {
  job_id: string;
  run_id: string;
  org_id: string;
  status: string;
  queue_name: string;
  retry_count: number;
  callback_url?: string | null;
  callback_status: string;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  ttl_expires_at?: string | null;
  poll_url: string;
}

export interface JobSubmitResponse {
  job_id: string;
  run_id: string;
  status: string;
  poll_url: string;
  message: string;
}

export interface JobListResponse {
  jobs: JobStatusResponse[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface WebhookTestResponse {
  success: boolean;
  status_code: number;
  message: string;
}

export type TriggerDirection = "above" | "below" | "change";
export type TriggerAggregation = "sum" | "avg" | "max" | "min" | "count";

export interface TriggerConditionRequest {
  source_id: string;
  metric_hint: string;
  threshold: number;
  direction: TriggerDirection;
  aggregation?: TriggerAggregation;
}

export interface RegisterTriggerRequest {
  name: string;
  condition: TriggerConditionRequest;
  simulation_template: Record<string, unknown>;
  webhook_url?: string | null;
  execution_webhook_url?: string | null;
  auto_execute?: boolean;
  description?: string | null;
}

export interface TriggerConditionResponse {
  source_id: string;
  metric_hint: string;
  threshold: number;
  direction: TriggerDirection;
  aggregation: TriggerAggregation;
}

export interface TriggerResponse {
  trigger_id: string;
  org_id: string;
  name: string;
  status: "active" | "paused";
  condition: TriggerConditionResponse;
  description?: string | null;
  webhook_url?: string | null;
  execution_webhook_url?: string | null;
  auto_execute: boolean;
  created_at: string;
  last_checked_at?: string | null;
  last_fired_at?: string | null;
  last_result_summary?: string | null;
}

export interface TriggerListResponse {
  triggers: TriggerResponse[];
  count: number;
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface TriggerFireResponse {
  trigger_id: string;
  condition_met: boolean;
  fired: boolean;
  simulation_run_id?: string | null;
  recommended_action?: string | null;
  expected_value?: number | null;
  confidence?: number | null;
  fired_at?: string | null;
  execution_status?: string | null;
  message: string;
}

export interface TriggerPauseResponse {
  trigger_id: string;
  status: "active" | "paused";
}

export interface TriggerDeleteResponse {
  trigger_id: string;
  deleted: boolean;
}

export interface APIKeyInfo {
  id: string;
  label: string;
  key_prefix: string;
  device_limit?: number | null;
  status: string;
  created_at: string;
  last_used_at?: string | null;
  expires_at?: string | null;
}

export interface APIKeyCreated {
  id: string;
  label: string;
  key_prefix: string;
  device_limit?: number | null;
  raw_key: string;
  created_at: string;
  expires_at?: string | null;
}

export interface CreateAPIKeyRequest {
  label: string;
  expires_at?: string | Date | null;
  device_limit?: number | null;
}

export interface UsageInfo {
  org_id: string;
  billing_period: string;
  simulations_run: number;
  api_calls: number;
  quota_limit: number;
  quota_used_pct: number;
}

export interface MeUserInfo {
  id: string;
  email: string;
  name: string;
  role: string;
  email_verified: boolean;
  created_at: string;
}

export interface MeOrgInfo {
  id: string;
  name: string;
  slug: string;
  plan: string;
  status: string;
  created_at: string;
}

export interface MeResponse {
  user: MeUserInfo;
  org: MeOrgInfo;
  email?: string | null;
  org_id?: string | null;
  org_name?: string | null;
  plan?: string | null;
  organization?: string | null;
}

export interface UpdateMeRequest {
  name?: string;
  org_name?: string;
}

export interface DistributionInfoResponse {
  name: string;
  description: string;
  required_params: string[];
  optional_params: string[];
  example: Record<string, unknown>;
}

export interface DistributionListResponse {
  distributions: DistributionInfoResponse[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface TemplateInfoResponse {
  id: string;
  name: string;
  category: string;
  description: string;
  example_request: Record<string, unknown>;
}

export interface TemplateListResponse {
  templates: TemplateInfoResponse[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface LimitsInfo {
  plan: string;
  simulations_per_month: number | string;
  max_simulations_per_month?: number;
  max_runs_per_simulation?: number;
  max_batch_items?: number;
  rate_limit_per_minute: number;
  connectors?: number | null;
  jobs_enabled?: boolean | null;
  async_jobs_enabled?: boolean | null;
  webhooks_enabled?: boolean | null;
}

export interface BillingInfoResponse {
  plan: string;
  stripe_customer_id?: string | null;
  subscription_status?: string | null;
  current_period_end?: string | null;
}

export interface BillingSessionResponse {
  url: string;
}

export interface MeteringEventRequest {
  event_type?: string;
  module?: string;
  function?: string;
  engine_used?: string;
  latency_ms?: number;
  success?: boolean;
  timestamp?: number;
  request_id?: string;
}

export interface MeteringBatchRequest {
  device_id: string;
  events: MeteringEventRequest[];
}

export interface MeteringBatchResponse {
  accepted: number;
  billing_period: string;
}

export interface CreditRefreshRequest {
  device_id: string;
  billing_period: string;
  credits_used?: number;
}

export interface CreditRefreshResponse {
  credits_granted: number;
  credits_issued_this_month: number;
  monthly_limit: number;
  monthly_remaining: number;
  billing_period: string;
  expires_at: number;
  refresh_after: number;
  server_time: number;
}

export interface TeamInviteRequest {
  email: string;
  role?: "owner" | "admin" | "member" | "viewer";
}

export interface TeamMemberInfo {
  user_id: string;
  name: string;
  email: string;
  role: string;
  status: string;
  last_active?: string | null;
}

export interface TeamListResponse {
  members: TeamMemberInfo[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface TeamInviteResponse {
  message: string;
  invite_id: string;
}

export interface TeamRoleUpdateResponse {
  message: string;
  user_id: string;
}

export interface TeamRemoveResponse {
  removed: boolean;
  user_id: string;
}

export interface DeviceRegistrationResponse {
  id: string;
  org_id: string;
  api_key_id: string;
  device_id: string;
  platform?: string | null;
  platform_version?: string | null;
  hostname_hash?: string | null;
  sdk_version?: string | null;
  status: string;
  last_heartbeat_at?: string | null;
  heartbeat_count: number;
  created_at: string;
  updated_at: string;
}

export interface DeviceListEntryResponse {
  id: string;
  device_id: string;
  platform?: string | null;
  platform_version?: string | null;
  sdk_version?: string | null;
  status: string;
  api_key_label?: string | null;
  api_key_prefix?: string | null;
  registered_at?: string | null;
  last_heartbeat_at?: string | null;
  heartbeat_count: number;
}

export interface DeviceListResponse {
  devices: DeviceListEntryResponse[];
  device_count: number;
  total: number;
  page: number;
  limit: number;
  pages: number;
  device_limit: number;
  plan: string;
}

export interface DeviceRevokeResponse {
  revoked: boolean;
  registration_id: string;
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  actor_email: string;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  ip_address?: string | null;
  result: string;
  content_hash?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface AuditLogResponse {
  entries: AuditLogEntry[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface ExecutionPolicyResponse {
  org_id: string;
  min_confidence: number;
  risk_floor?: number | null;
  require_calibration: boolean;
  allow_reexecution: boolean;
  snapshot_id?: string | null;
  content_hash?: string | null;
  schema_revision?: string | null;
  revision?: number | null;
  previous_snapshot_id?: string | null;
  created_at?: string | null;
  updated_at: string;
}

export interface ExecutionPolicySnapshotListResponse {
  org_id: string;
  data: ExecutionPolicyResponse[];
  total_snapshots: number;
}

export interface UpdateExecutionPolicyRequest {
  min_confidence?: number;
  risk_floor?: number | null;
  require_calibration?: boolean;
  allow_reexecution?: boolean;
}

export interface DeploymentRegionResponse {
  id: string;
  name: string;
  label?: string | null;
  location?: string | null;
}

export interface DeploymentProviderResponse {
  id: string;
  name: string;
  description: string;
  icon: string;
  regions: DeploymentRegionResponse[];
}

export interface DeploymentRegionsResponse {
  providers: DeploymentProviderResponse[];
}

export interface DeploymentResponse {
  deployment_id: string;
  org_id: string;
  provider: string;
  region: string;
  status: string;
  endpoint_url?: string | null;
  cost_usd_month: number;
  billable_cost_usd_month: number;
  billing_markup_pct: number;
  created_at: string;
  provisioned_at?: string | null;
  error_message?: string | null;
}

export interface CreateDeploymentRequest {
  provider?: string;
  region?: string;
  config?: Record<string, unknown> | null;
  billing_markup_pct?: number;
}

export interface DeploymentDeleteResponse {
  status: string;
  deployment_id: string;
}

export interface DeploymentCostResponse {
  deployment_id: string;
  provider: string;
  region: string;
  year: number;
  month: number;
  cost_usd_month: number;
  billable_cost_usd_month: number;
  billing_markup_pct: number;
  last_updated?: string | null;
}

export interface BatchItemResult {
  index: number;
  success: boolean;
  envelope?: DecisionEnvelope | null;
  error?: string | null;
}

export interface BatchResult {
  total: number;
  succeeded: number;
  failed: number;
  results: BatchItemResult[];
}

// ─── Runtime Libraries ─────────────────────────────────────────────────────

export interface LibraryModuleDescriptor {
  name: string;
  engine: string;
  functions: string[];
}

export interface LibraryListResponse {
  modules: LibraryModuleDescriptor[];
  count: number;
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface LibraryHealthResponse {
  status: string;
  engine: string;
  module_count: number;
  runtime_available: boolean;
}

export interface LibraryExecutionRequest {
  module: string;
  function: string;
  args?: unknown;
  request_id?: string;
}

export interface LibraryExecutionResponse {
  module: string;
  function: string;
  result: unknown;
  latency_ms: number;
  engine_used: string;
  request_id?: string | null;
}

// ─── Error Types ───────────────────────────────────────────────────────────

export interface APIErrorDetail {
  field?: string;
  issue: string;
}

export interface APIError {
  code: string;
  message: string;
  details?: APIErrorDetail[];
  request_id?: string;
  docs_url?: string;
}

export interface APIErrorResponse {
  error: APIError;
}

// ─── Client Config ─────────────────────────────────────────────────────────

export interface DecisionEngineClientConfig {
  apiKey?: string;
  baseUrl?: string;
  timeout?: number;
  maxRetries?: number;
  defaultHeaders?: Record<string, string>;
}
