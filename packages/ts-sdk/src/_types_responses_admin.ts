// SPDX-License-Identifier: Apache-2.0
/** Auto-split sub-module of types.ts — responses_admin types. */

// Auto-split from types.ts. Cross-file type references use `import type`.
import type { CAPABILITY_PLANE_CONTRACT, PRIMARY_DATA_QUERY_CONTRACT } from "./contract.js";
import type { DecisionEnvelope, DecisionPlanResponse } from "./_types_responses_core.js";

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

