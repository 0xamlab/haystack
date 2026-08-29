/** Auto-split sub-module of types.ts — requests types. */

// Auto-split from types.ts. Cross-file type references use `import type`.
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

export interface ChatCompletionToolCallFunction {
  name: string;
  arguments: string;
}

export interface ChatCompletionToolCall {
  id: string;
  type: "function";
  function: ChatCompletionToolCallFunction;
}

export interface ChatCompletionInputMessage {
  role: "system" | "user" | "assistant" | "developer" | "tool";
  content?: string | null;
  tool_calls?: ChatCompletionToolCall[];
  tool_call_id?: string;
  name?: string;
}

export interface ChatCompletionToolFunctionDef {
  name: string;
  description?: string;
  parameters?: Record<string, unknown>;
  strict?: boolean;
}

export interface ChatCompletionToolDef {
  type: "function";
  function: ChatCompletionToolFunctionDef;
}

export type ChatCompletionToolChoice =
  | "auto"
  | "none"
  | "required"
  | { type: "function"; function: { name: string } };

export interface ChatCompletionsRequest {
  model?: string;
  messages: ChatCompletionInputMessage[];
  stream?: boolean;
  tools?: ChatCompletionToolDef[];
  tool_choice?: ChatCompletionToolChoice;
  parallel_tool_calls?: boolean;
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

