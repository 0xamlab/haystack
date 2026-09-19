// SPDX-License-Identifier: Apache-2.0
/** Auto-split sub-module of runtime.ts — recommend/score/batch/compare,
 * jobs, triggers, deployments, account, billing, team, devices, audit, and
 * execution policy wrappers for the Runtime class.
 *
 * This module augments the {@link Runtime} class via TypeScript declaration
 * merging and prototype assignment. Importing this file (for its side
 * effects) is required so the prototype assignments execute and the
 * augmented methods are available on `Runtime` instances.
 */

import type {
  APIKeyCreated,
  APIKeyInfo,
  AuditLogResponse,
  BatchResult,
  BillingInfoResponse,
  BillingSessionResponse,
  CompareResponse,
  CreateAPIKeyRequest,
  CreditRefreshRequest,
  CreditRefreshResponse,
  DeploymentCostResponse,
  DeploymentDeleteResponse,
  DeploymentRegionsResponse,
  DeploymentResponse,
  DeviceListResponse,
  DeviceRevokeResponse,
  DistributionListResponse,
  ExecutionPolicyResponse,
  ExecutionPolicySnapshotListResponse,
  JobListResponse,
  JobStatusResponse,
  JobSubmitResponse,
  LimitsInfo,
  MeResponse,
  MeteringBatchRequest,
  MeteringBatchResponse,
  QueryBatchResponse,
  QuerySqlReportRequest,
  QuerySqlReportResponse,
  RecommendResponse,
  RegisterTriggerRequest,
  ScoreResponse,
  SimulateRequest,
  TeamInviteRequest,
  TeamInviteResponse,
  TeamListResponse,
  TeamRemoveResponse,
  TeamRoleUpdateResponse,
  TemplateListResponse,
  TriggerDeleteResponse,
  TriggerFireResponse,
  TriggerListResponse,
  TriggerPauseResponse,
  TriggerResponse,
  UpdateExecutionPolicyRequest,
  UpdateMeRequest,
  UsageInfo,
  WebhookTestResponse,
} from "./types.js";
import { Runtime } from "./_runtime_class.js";

declare module "./_runtime_class.js" {
  interface Runtime {
    recommend(
      actions: Array<{ name: string; request: SimulateRequest }>,
      options?: { runs?: number; seed?: number },
    ): Promise<RecommendResponse>;
    score(
      request: SimulateRequest,
      scoringWeights?: Record<string, number>,
    ): Promise<ScoreResponse>;
    batch(items: SimulateRequest[]): Promise<BatchResult>;
    compare(
      scenarios: Array<{ name: string; request: SimulateRequest }>,
      options?: { runs?: number; seed?: number },
    ): Promise<CompareResponse>;
    listJobs(options?: {
      page?: number;
      limit?: number;
      status?: string;
    }): Promise<JobListResponse>;
    submitJob(request: SimulateRequest, callbackUrl?: string): Promise<JobSubmitResponse>;
    getJob(jobId: string): Promise<JobStatusResponse>;
    getJobResult(jobId: string): Promise<Record<string, unknown>>;
    cancelJob(jobId: string): Promise<JobStatusResponse>;
    testWebhookDelivery(callbackUrl: string): Promise<WebhookTestResponse>;
    registerTrigger(request: RegisterTriggerRequest): Promise<TriggerResponse>;
    listTriggers(options?: {
      status?: "active" | "paused" | "all";
      page?: number;
      limit?: number;
    }): Promise<TriggerListResponse>;
    fireTrigger(triggerId: string, options?: { force?: boolean }): Promise<TriggerFireResponse>;
    pauseTrigger(triggerId: string, options?: { paused?: boolean }): Promise<TriggerPauseResponse>;
    deleteTrigger(triggerId: string): Promise<TriggerDeleteResponse>;
    pollJob(
      jobId: string,
      options?: { timeoutMs?: number; pollIntervalMs?: number },
    ): Promise<Record<string, unknown>>;
    listDeploymentRegions(): Promise<DeploymentRegionsResponse>;
    getDeployment(): Promise<DeploymentResponse | null>;
    createDeployment(request?: {
      provider?: string;
      region?: string;
      config?: Record<string, unknown> | null;
      billing_markup_pct?: number;
    }): Promise<DeploymentResponse>;
    deleteDeployment(deploymentId: string): Promise<DeploymentDeleteResponse>;
    getDeploymentCost(deploymentId: string): Promise<DeploymentCostResponse>;
    me(): Promise<MeResponse>;
    updateMe(request: UpdateMeRequest): Promise<MeResponse>;
    usage(): Promise<UsageInfo>;
    limits(): Promise<LimitsInfo>;
    distributions(): Promise<DistributionListResponse>;
    templates(): Promise<TemplateListResponse>;
    getBillingInfo(): Promise<BillingInfoResponse>;
    createBillingCheckout(options?: { plan?: "developer" | "pro" }): Promise<BillingSessionResponse>;
    createBillingPortal(): Promise<BillingSessionResponse>;
    refreshCredits(request: CreditRefreshRequest): Promise<CreditRefreshResponse>;
    ingestMeteringEvents(request: MeteringBatchRequest): Promise<MeteringBatchResponse>;
    listApiKeys(): Promise<APIKeyInfo[]>;
    createApiKey(request: CreateAPIKeyRequest): Promise<APIKeyCreated>;
    revokeApiKey(keyId: string): Promise<Record<string, unknown>>;
    listTeamMembers(options?: { page?: number; limit?: number }): Promise<TeamListResponse>;
    inviteTeamMember(request: TeamInviteRequest): Promise<TeamInviteResponse>;
    updateTeamMemberRole(
      userId: string,
      role: "owner" | "admin" | "member" | "viewer",
    ): Promise<TeamRoleUpdateResponse>;
    removeTeamMember(userId: string): Promise<TeamRemoveResponse>;
    listDevices(options?: { page?: number; limit?: number }): Promise<DeviceListResponse>;
    revokeDevice(registrationId: string): Promise<DeviceRevokeResponse>;
    getAuditLogs(options?: {
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
    }): Promise<AuditLogResponse>;
    getAuditLogArtifacts(options?: {
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
    }): Promise<AuditLogResponse>;
    getExecutionPolicy(): Promise<ExecutionPolicyResponse>;
    listExecutionPolicySnapshots(): Promise<ExecutionPolicySnapshotListResponse>;
    updateExecutionPolicy(
      request: UpdateExecutionPolicyRequest,
    ): Promise<ExecutionPolicyResponse>;
    queryBatch(request: {
      defaults?: {
        dataset_id?: string | null;
        filter?: Record<string, unknown> | null;
        limit?: number | null;
        order?: "asc" | "desc" | null;
      } | null;
      queries: Array<{ key: string; request: Record<string, unknown> }>;
    }): Promise<QueryBatchResponse>;
    querySqlReport(request: QuerySqlReportRequest): Promise<QuerySqlReportResponse>;
  }
}

Runtime.prototype.recommend = async function (
  this: Runtime,
  actions: Array<{ name: string; request: SimulateRequest }>,
  options?: { runs?: number; seed?: number },
): Promise<RecommendResponse> {
  this.requireApiTransport("recommend");
  return this.client().recommend(actions, options);
};

Runtime.prototype.score = async function (
  this: Runtime,
  request: SimulateRequest,
  scoringWeights?: Record<string, number>,
): Promise<ScoreResponse> {
  this.requireApiTransport("score");
  return this.client().score(request, scoringWeights);
};

Runtime.prototype.batch = async function (
  this: Runtime,
  items: SimulateRequest[],
): Promise<BatchResult> {
  this.requireApiTransport("batch");
  return this.client().batch(items);
};

Runtime.prototype.compare = async function (
  this: Runtime,
  scenarios: Array<{ name: string; request: SimulateRequest }>,
  options?: { runs?: number; seed?: number },
): Promise<CompareResponse> {
  this.requireApiTransport("compare");
  return this.client().compare(scenarios, options);
};

Runtime.prototype.listJobs = async function (
  this: Runtime,
  options: { page?: number; limit?: number; status?: string } = {},
): Promise<JobListResponse> {
  this.requireApiTransport("listJobs");
  return this.client().listJobs(options);
};

Runtime.prototype.submitJob = async function (
  this: Runtime,
  request: SimulateRequest,
  callbackUrl?: string,
): Promise<JobSubmitResponse> {
  this.requireApiTransport("submitJob");
  return this.client().submitJob(request, callbackUrl);
};

Runtime.prototype.getJob = async function (
  this: Runtime,
  jobId: string,
): Promise<JobStatusResponse> {
  this.requireApiTransport("getJob");
  return this.client().getJob(jobId);
};

Runtime.prototype.getJobResult = async function (
  this: Runtime,
  jobId: string,
): Promise<Record<string, unknown>> {
  this.requireApiTransport("getJobResult");
  return this.client().getJobResult(jobId);
};

Runtime.prototype.cancelJob = async function (
  this: Runtime,
  jobId: string,
): Promise<JobStatusResponse> {
  this.requireApiTransport("cancelJob");
  return this.client().cancelJob(jobId);
};

Runtime.prototype.testWebhookDelivery = async function (
  this: Runtime,
  callbackUrl: string,
): Promise<WebhookTestResponse> {
  this.requireApiTransport("testWebhookDelivery");
  return this.client().testWebhookDelivery(callbackUrl);
};

Runtime.prototype.registerTrigger = async function (
  this: Runtime,
  request: RegisterTriggerRequest,
): Promise<TriggerResponse> {
  this.requireApiTransport("registerTrigger");
  return this.client().registerTrigger(request);
};

Runtime.prototype.listTriggers = async function (
  this: Runtime,
  options: { status?: "active" | "paused" | "all"; page?: number; limit?: number } = {},
): Promise<TriggerListResponse> {
  this.requireApiTransport("listTriggers");
  return this.client().listTriggers(options);
};

Runtime.prototype.fireTrigger = async function (
  this: Runtime,
  triggerId: string,
  options: { force?: boolean } = {},
): Promise<TriggerFireResponse> {
  this.requireApiTransport("fireTrigger");
  return this.client().fireTrigger(triggerId, options);
};

Runtime.prototype.pauseTrigger = async function (
  this: Runtime,
  triggerId: string,
  options: { paused?: boolean } = {},
): Promise<TriggerPauseResponse> {
  this.requireApiTransport("pauseTrigger");
  return this.client().pauseTrigger(triggerId, options);
};

Runtime.prototype.deleteTrigger = async function (
  this: Runtime,
  triggerId: string,
): Promise<TriggerDeleteResponse> {
  this.requireApiTransport("deleteTrigger");
  return this.client().deleteTrigger(triggerId);
};

Runtime.prototype.pollJob = async function (
  this: Runtime,
  jobId: string,
  options: { timeoutMs?: number; pollIntervalMs?: number } = {},
): Promise<Record<string, unknown>> {
  this.requireApiTransport("pollJob");
  return this.client().pollJob(jobId, options);
};

Runtime.prototype.listDeploymentRegions = async function (
  this: Runtime,
): Promise<DeploymentRegionsResponse> {
  this.requireApiTransport("listDeploymentRegions");
  return this.client().listDeploymentRegions();
};

Runtime.prototype.getDeployment = async function (
  this: Runtime,
): Promise<DeploymentResponse | null> {
  this.requireApiTransport("getDeployment");
  return this.client().getDeployment();
};

Runtime.prototype.createDeployment = async function (
  this: Runtime,
  request: {
    provider?: string;
    region?: string;
    config?: Record<string, unknown> | null;
    billing_markup_pct?: number;
  } = {},
): Promise<DeploymentResponse> {
  this.requireApiTransport("createDeployment");
  return this.client().createDeployment(request);
};

Runtime.prototype.deleteDeployment = async function (
  this: Runtime,
  deploymentId: string,
): Promise<DeploymentDeleteResponse> {
  this.requireApiTransport("deleteDeployment");
  return this.client().deleteDeployment(deploymentId);
};

Runtime.prototype.getDeploymentCost = async function (
  this: Runtime,
  deploymentId: string,
): Promise<DeploymentCostResponse> {
  this.requireApiTransport("getDeploymentCost");
  return this.client().getDeploymentCost(deploymentId);
};

Runtime.prototype.me = async function (this: Runtime): Promise<MeResponse> {
  this.requireApiTransport("me");
  return this.client().me();
};

Runtime.prototype.updateMe = async function (
  this: Runtime,
  request: UpdateMeRequest,
): Promise<MeResponse> {
  this.requireApiTransport("updateMe");
  return this.client().updateMe(request);
};

Runtime.prototype.usage = async function (this: Runtime): Promise<UsageInfo> {
  this.requireApiTransport("usage");
  return this.client().usage();
};

Runtime.prototype.limits = async function (this: Runtime): Promise<LimitsInfo> {
  this.requireApiTransport("limits");
  return this.client().limits();
};

Runtime.prototype.distributions = async function (
  this: Runtime,
): Promise<DistributionListResponse> {
  this.requireApiTransport("distributions");
  return this.client().distributions();
};

Runtime.prototype.templates = async function (this: Runtime): Promise<TemplateListResponse> {
  this.requireApiTransport("templates");
  return this.client().templates();
};

Runtime.prototype.getBillingInfo = async function (
  this: Runtime,
): Promise<BillingInfoResponse> {
  this.requireApiTransport("getBillingInfo");
  return this.client().getBillingInfo();
};

Runtime.prototype.createBillingCheckout = async function (
  this: Runtime,
  options: { plan?: "developer" | "pro" } = {},
): Promise<BillingSessionResponse> {
  this.requireApiTransport("createBillingCheckout");
  return this.client().createBillingCheckout(options);
};

Runtime.prototype.createBillingPortal = async function (
  this: Runtime,
): Promise<BillingSessionResponse> {
  this.requireApiTransport("createBillingPortal");
  return this.client().createBillingPortal();
};

Runtime.prototype.refreshCredits = async function (
  this: Runtime,
  request: CreditRefreshRequest,
): Promise<CreditRefreshResponse> {
  this.requireApiTransport("refreshCredits");
  return this.client().refreshCredits(request);
};

Runtime.prototype.ingestMeteringEvents = async function (
  this: Runtime,
  request: MeteringBatchRequest,
): Promise<MeteringBatchResponse> {
  this.requireApiTransport("ingestMeteringEvents");
  return this.client().ingestMeteringEvents(request);
};

Runtime.prototype.listApiKeys = async function (this: Runtime): Promise<APIKeyInfo[]> {
  this.requireApiTransport("listApiKeys");
  return this.client().listApiKeys();
};

Runtime.prototype.createApiKey = async function (
  this: Runtime,
  request: CreateAPIKeyRequest,
): Promise<APIKeyCreated> {
  this.requireApiTransport("createApiKey");
  return this.client().createApiKey(request);
};

Runtime.prototype.revokeApiKey = async function (
  this: Runtime,
  keyId: string,
): Promise<Record<string, unknown>> {
  this.requireApiTransport("revokeApiKey");
  return this.client().revokeApiKey(keyId);
};

Runtime.prototype.listTeamMembers = async function (
  this: Runtime,
  options: { page?: number; limit?: number } = {},
): Promise<TeamListResponse> {
  this.requireApiTransport("listTeamMembers");
  return this.client().listTeamMembers(options);
};

Runtime.prototype.inviteTeamMember = async function (
  this: Runtime,
  request: TeamInviteRequest,
): Promise<TeamInviteResponse> {
  this.requireApiTransport("inviteTeamMember");
  return this.client().inviteTeamMember(request);
};

Runtime.prototype.updateTeamMemberRole = async function (
  this: Runtime,
  userId: string,
  role: "owner" | "admin" | "member" | "viewer",
): Promise<TeamRoleUpdateResponse> {
  this.requireApiTransport("updateTeamMemberRole");
  return this.client().updateTeamMemberRole(userId, role);
};

Runtime.prototype.removeTeamMember = async function (
  this: Runtime,
  userId: string,
): Promise<TeamRemoveResponse> {
  this.requireApiTransport("removeTeamMember");
  return this.client().removeTeamMember(userId);
};

Runtime.prototype.listDevices = async function (
  this: Runtime,
  options: { page?: number; limit?: number } = {},
): Promise<DeviceListResponse> {
  this.requireApiTransport("listDevices");
  return this.client().listDevices(options);
};

Runtime.prototype.revokeDevice = async function (
  this: Runtime,
  registrationId: string,
): Promise<DeviceRevokeResponse> {
  this.requireApiTransport("revokeDevice");
  return this.client().revokeDevice(registrationId);
};

Runtime.prototype.getAuditLogs = async function (
  this: Runtime,
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
};

Runtime.prototype.getAuditLogArtifacts = async function (
  this: Runtime,
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
};

Runtime.prototype.getExecutionPolicy = async function (
  this: Runtime,
): Promise<ExecutionPolicyResponse> {
  this.requireApiTransport("getExecutionPolicy");
  return this.client().getExecutionPolicy();
};

Runtime.prototype.listExecutionPolicySnapshots = async function (
  this: Runtime,
): Promise<ExecutionPolicySnapshotListResponse> {
  this.requireApiTransport("listExecutionPolicySnapshots");
  return this.client().listExecutionPolicySnapshots();
};

Runtime.prototype.updateExecutionPolicy = async function (
  this: Runtime,
  request: UpdateExecutionPolicyRequest,
): Promise<ExecutionPolicyResponse> {
  this.requireApiTransport("updateExecutionPolicy");
  return this.client().updateExecutionPolicy(request);
};

Runtime.prototype.queryBatch = async function (
  this: Runtime,
  request: {
    defaults?: {
      dataset_id?: string | null;
      filter?: Record<string, unknown> | null;
      limit?: number | null;
      order?: "asc" | "desc" | null;
    } | null;
    queries: Array<{ key: string; request: Record<string, unknown> }>;
  },
): Promise<QueryBatchResponse> {
  this.requireApiTransport("queryBatch");
  return this.client().queryBatch(request);
};

Runtime.prototype.querySqlReport = async function (
  this: Runtime,
  request: QuerySqlReportRequest,
): Promise<QuerySqlReportResponse> {
  this.requireApiTransport("querySqlReport");
  return this.client().querySqlReport(request);
};
