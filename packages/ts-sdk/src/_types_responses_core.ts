/** Auto-split sub-module of types.ts — responses_core types. */

// Auto-split from types.ts. Cross-file type references use `import type`.
import type { CAPABILITY_PLANE_CONTRACT, PRIMARY_DATA_QUERY_CONTRACT } from "./contract.js";
import type {
  AgentRunAction,
  AgentRunPendingAction,
  AgentRunStatus,
  ChatCompletionToolCall,
  SimulateRequest,
} from "./_types_requests.js";

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
  content: string | null;
  tool_calls?: ChatCompletionToolCall[] | null;
}

export interface ChatCompletionChoice {
  index: number;
  finish_reason: "stop" | "tool_calls" | "length" | "content_filter";
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
  text: string | null;
  tokens?: string[] | null;
  token_count: number;
  embedding?: number[] | null;
  tool_calls?: ChatCompletionToolCall[] | null;
  finish_reason?: "stop" | "tool_calls" | "length" | "content_filter" | null;
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

