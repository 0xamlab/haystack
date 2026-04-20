/**
 * TypeScript type definitions for the Decision Engine API.
 */

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
  score_breakdown?: Record<string, number> | null;
  scenario_ranking?: Array<Record<string, unknown>> | null;
  sensitivity_ranking?: Array<Record<string, unknown>> | null;
  request_hash?: string | null;
  result_hash?: string | null;
  created_at?: string | null;
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

export interface ResolvedPlan {
  source_name: string;
  metric_column: string;
  aggregation: string;
  group_column?: string | null;
  join_path?: Record<string, unknown> | null;
  filter?: Record<string, unknown> | null;
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
  planner_cache_hit?: boolean | null;
  planner_schema_revision?: string | null;
  planner_prewarm_ms?: number | null;
  latency_ms?: number | null;
  [key: string]: unknown;
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
