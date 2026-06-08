/** Auto-split sub-module of client.ts — async jobs, triggers, account,
 * billing, team, devices, audit, execution policy, deployment, health and
 * version methods for DecisionEngineClient.
 *
 * This module augments the {@link DecisionEngineClient} class via TypeScript
 * declaration merging and prototype assignment. Importing this file (for its
 * side effects) is required so the prototype assignments execute and the
 * augmented methods are available on `DecisionEngineClient` instances.
 */

import type {
  APIKeyCreated,
  APIKeyInfo,
  AuditLogResponse,
  BillingInfoResponse,
  BillingSessionResponse,
  CreateAPIKeyRequest,
  CreateDeploymentRequest,
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
  RegisterTriggerRequest,
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
import { DecisionEngineClient } from "./_client_class.js";
import { DecisionEngineError } from "./_client_errors.js";
import {
  assertApiKeyCreateResponse,
  assertApiKeyListResponse,
  assertBillingInfoResponse,
  assertDistributionListResponse,
  assertLimitsInfoResponse,
  assertMeResponse,
  assertTemplateListResponse,
  assertUsageInfoResponse,
  normalizeUpdateMeRequest,
} from "./_client_platform_validators_a1.js";
import {
  assertBillingSessionResponse,
  assertCreditRefreshResponse,
  assertDeviceListResponse,
  assertDeviceRevokeResponse,
  assertMeteringBatchResponse,
  assertTeamInviteResponse,
  assertTeamListResponse,
  assertTeamRemoveResponse,
  assertTeamRoleUpdateResponse,
} from "./_client_platform_validators_a2.js";
import {
  assertAuditLogResponse,
  assertDeploymentDeleteResponse,
  assertDeploymentRegionsResponse,
  assertDeploymentResponse,
  assertExecutionPolicyResponse,
  assertExecutionPolicySnapshotListResponse,
  normalizeApiKeyCreateRequest,
  normalizeCreateDeploymentRequest,
  normalizeCreditRefreshRequest,
  normalizeMeteringBatchRequest,
  normalizeTeamInviteRequest,
  normalizeTeamRole,
  normalizeUpdateExecutionPolicyRequest,
} from "./_client_platform_validators_b1.js";
import { assertDeploymentCostResponse } from "./_client_platform_validators_b2.js";

declare module "./_client_class.js" {
  interface DecisionEngineClient {
    submitJob(request: SimulateRequest, callbackUrl?: string): Promise<JobSubmitResponse>;
    getJob(jobId: string): Promise<JobStatusResponse>;
    getJobResult(jobId: string): Promise<Record<string, unknown>>;
    listJobs(options?: { page?: number; limit?: number; status?: string }): Promise<JobListResponse>;
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
    listDeploymentRegions(): Promise<DeploymentRegionsResponse>;
    getDeployment(): Promise<DeploymentResponse | null>;
    createDeployment(request?: CreateDeploymentRequest): Promise<DeploymentResponse>;
    deleteDeployment(deploymentId: string): Promise<DeploymentDeleteResponse>;
    getDeploymentCost(deploymentId: string): Promise<DeploymentCostResponse>;
    health(): Promise<{ status: string; timestamp: string }>;
    version(): Promise<{ api_version: string; engine_version: string; environment: string }>;
  }
}

DecisionEngineClient.prototype.submitJob = async function (
  this: DecisionEngineClient,
  request: SimulateRequest,
  callbackUrl?: string,
): Promise<JobSubmitResponse> {
  return this.request<JobSubmitResponse>("POST", "/v1/jobs", {
    request,
    callback_url: callbackUrl,
  });
};

DecisionEngineClient.prototype.getJob = async function (
  this: DecisionEngineClient,
  jobId: string,
): Promise<JobStatusResponse> {
  return this.request<JobStatusResponse>("GET", `/v1/jobs/${jobId}`);
};

DecisionEngineClient.prototype.getJobResult = async function (
  this: DecisionEngineClient,
  jobId: string,
): Promise<Record<string, unknown>> {
  return this.request("GET", `/v1/jobs/${jobId}/result`);
};

DecisionEngineClient.prototype.listJobs = async function (
  this: DecisionEngineClient,
  options: { page?: number; limit?: number; status?: string } = {},
): Promise<JobListResponse> {
  const query = new URLSearchParams();
  query.set("page", String(options.page ?? 1));
  query.set("limit", String(options.limit ?? 25));
  if (options.status) {
    query.set("status", options.status);
  }
  return this.request<JobListResponse>("GET", `/v1/jobs/list?${query.toString()}`);
};

DecisionEngineClient.prototype.cancelJob = async function (
  this: DecisionEngineClient,
  jobId: string,
): Promise<JobStatusResponse> {
  return this.request<JobStatusResponse>("POST", `/v1/jobs/${jobId}/cancel`);
};

DecisionEngineClient.prototype.testWebhookDelivery = async function (
  this: DecisionEngineClient,
  callbackUrl: string,
): Promise<WebhookTestResponse> {
  return this.request<WebhookTestResponse>("POST", "/v1/webhooks/test", {
    callback_url: callbackUrl,
  });
};

DecisionEngineClient.prototype.registerTrigger = async function (
  this: DecisionEngineClient,
  request: RegisterTriggerRequest,
): Promise<TriggerResponse> {
  return this.request<TriggerResponse>("POST", "/v1/triggers", request);
};

DecisionEngineClient.prototype.listTriggers = async function (
  this: DecisionEngineClient,
  options: { status?: "active" | "paused" | "all"; page?: number; limit?: number } = {},
): Promise<TriggerListResponse> {
  const query = new URLSearchParams();
  if (options.status && options.status !== "all") {
    query.set("status", options.status);
  }
  if (options.page !== undefined) {
    query.set("page", String(options.page));
  }
  if (options.limit !== undefined) {
    query.set("limit", String(options.limit));
  }
  const suffix = query.toString();
  return this.request<TriggerListResponse>(
    "GET",
    suffix ? `/v1/triggers?${suffix}` : "/v1/triggers",
  );
};

DecisionEngineClient.prototype.fireTrigger = async function (
  this: DecisionEngineClient,
  triggerId: string,
  options: { force?: boolean } = {},
): Promise<TriggerFireResponse> {
  return this.request<TriggerFireResponse>("POST", `/v1/triggers/${triggerId}/fire`, {
    force: options.force ?? false,
  });
};

DecisionEngineClient.prototype.pauseTrigger = async function (
  this: DecisionEngineClient,
  triggerId: string,
  options: { paused?: boolean } = {},
): Promise<TriggerPauseResponse> {
  const paused = options.paused ?? true;
  return this.request<TriggerPauseResponse>(
    "PATCH",
    `/v1/triggers/${triggerId}/pause?paused=${paused ? "true" : "false"}`,
  );
};

DecisionEngineClient.prototype.deleteTrigger = async function (
  this: DecisionEngineClient,
  triggerId: string,
): Promise<TriggerDeleteResponse> {
  await this.request("DELETE", `/v1/triggers/${triggerId}`);
  return { trigger_id: triggerId, deleted: true };
};

DecisionEngineClient.prototype.pollJob = async function (
  this: DecisionEngineClient,
  jobId: string,
  options: { timeoutMs?: number; pollIntervalMs?: number } = {},
): Promise<Record<string, unknown>> {
  const { timeoutMs = 300_000, pollIntervalMs = 2_000 } = options;
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const status = await this.getJob(jobId);
    if (status.status === "completed") return this.getJobResult(jobId);
    if (status.status === "failed" || status.status === "cancelled") {
      throw new DecisionEngineError(
        `Job ${jobId} ended with status '${status.status}': ${status.error_message}`,
      );
    }
    await new Promise(resolve => setTimeout(resolve, pollIntervalMs));
  }
  throw new DecisionEngineError(`Job ${jobId} timed out after ${timeoutMs}ms`);
};

DecisionEngineClient.prototype.me = async function (
  this: DecisionEngineClient,
): Promise<MeResponse> {
  return assertMeResponse(await this.request<unknown>("GET", "/v1/me"));
};

DecisionEngineClient.prototype.updateMe = async function (
  this: DecisionEngineClient,
  request: UpdateMeRequest,
): Promise<MeResponse> {
  return assertMeResponse(
    await this.request<unknown>("PATCH", "/v1/me", normalizeUpdateMeRequest(request)),
  );
};

DecisionEngineClient.prototype.usage = async function (
  this: DecisionEngineClient,
): Promise<UsageInfo> {
  return assertUsageInfoResponse(await this.request<unknown>("GET", "/v1/usage"));
};

DecisionEngineClient.prototype.limits = async function (
  this: DecisionEngineClient,
): Promise<LimitsInfo> {
  return assertLimitsInfoResponse(await this.request<unknown>("GET", "/v1/limits"));
};

DecisionEngineClient.prototype.distributions = async function (
  this: DecisionEngineClient,
): Promise<DistributionListResponse> {
  return assertDistributionListResponse(await this.request<unknown>("GET", "/v1/distributions"));
};

DecisionEngineClient.prototype.templates = async function (
  this: DecisionEngineClient,
): Promise<TemplateListResponse> {
  return assertTemplateListResponse(await this.request<unknown>("GET", "/v1/templates"));
};

DecisionEngineClient.prototype.getBillingInfo = async function (
  this: DecisionEngineClient,
): Promise<BillingInfoResponse> {
  return assertBillingInfoResponse(await this.request<unknown>("GET", "/v1/billing/info"));
};

DecisionEngineClient.prototype.createBillingCheckout = async function (
  this: DecisionEngineClient,
  options: { plan?: "developer" | "pro" } = {},
): Promise<BillingSessionResponse> {
  return assertBillingSessionResponse(
    await this.request<unknown>("POST", "/v1/billing/checkout", options),
  );
};

DecisionEngineClient.prototype.createBillingPortal = async function (
  this: DecisionEngineClient,
): Promise<BillingSessionResponse> {
  return assertBillingSessionResponse(
    await this.request<unknown>("POST", "/v1/billing/portal", {}),
  );
};

DecisionEngineClient.prototype.refreshCredits = async function (
  this: DecisionEngineClient,
  request: CreditRefreshRequest,
): Promise<CreditRefreshResponse> {
  return assertCreditRefreshResponse(
    await this.request<unknown>(
      "POST",
      "/v1/credits/refresh",
      normalizeCreditRefreshRequest(request),
    ),
  );
};

DecisionEngineClient.prototype.ingestMeteringEvents = async function (
  this: DecisionEngineClient,
  request: MeteringBatchRequest,
): Promise<MeteringBatchResponse> {
  return assertMeteringBatchResponse(
    await this.request<unknown>(
      "POST",
      "/v1/metering",
      normalizeMeteringBatchRequest(request),
    ),
  );
};

DecisionEngineClient.prototype.listApiKeys = async function (
  this: DecisionEngineClient,
): Promise<APIKeyInfo[]> {
  return assertApiKeyListResponse(await this.request<unknown>("GET", "/v1/api-keys"));
};

DecisionEngineClient.prototype.createApiKey = async function (
  this: DecisionEngineClient,
  request: CreateAPIKeyRequest,
): Promise<APIKeyCreated> {
  return assertApiKeyCreateResponse(
    await this.request<unknown>(
      "POST",
      "/v1/api-keys",
      normalizeApiKeyCreateRequest(request),
    ),
  );
};

DecisionEngineClient.prototype.revokeApiKey = async function (
  this: DecisionEngineClient,
  keyId: string,
): Promise<Record<string, unknown>> {
  return this.request<Record<string, unknown>>("DELETE", `/v1/api-keys/${keyId}`);
};

DecisionEngineClient.prototype.listTeamMembers = async function (
  this: DecisionEngineClient,
  options: { page?: number; limit?: number } = {},
): Promise<TeamListResponse> {
  const params = new URLSearchParams();
  if (options.page !== undefined) params.set("page", String(options.page));
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return assertTeamListResponse(await this.request<unknown>("GET", `/v1/team${suffix}`));
};

DecisionEngineClient.prototype.inviteTeamMember = async function (
  this: DecisionEngineClient,
  request: TeamInviteRequest,
): Promise<TeamInviteResponse> {
  return assertTeamInviteResponse(
    await this.request<unknown>(
      "POST",
      "/v1/team/invite",
      normalizeTeamInviteRequest(request),
    ),
  );
};

DecisionEngineClient.prototype.updateTeamMemberRole = async function (
  this: DecisionEngineClient,
  userId: string,
  role: "owner" | "admin" | "member" | "viewer",
): Promise<TeamRoleUpdateResponse> {
  if (typeof userId !== "string" || userId.length === 0) {
    throw new DecisionEngineError("updateTeamMemberRole requires a non-empty userId.");
  }
  return assertTeamRoleUpdateResponse(
    await this.request<unknown>("PATCH", `/v1/team/${userId}/role`, {
      role: normalizeTeamRole(role, "updateTeamMemberRole"),
    }),
  );
};

DecisionEngineClient.prototype.removeTeamMember = async function (
  this: DecisionEngineClient,
  userId: string,
): Promise<TeamRemoveResponse> {
  if (typeof userId !== "string" || userId.length === 0) {
    throw new DecisionEngineError("removeTeamMember requires a non-empty userId.");
  }
  return assertTeamRemoveResponse(
    await this.request<unknown>("DELETE", `/v1/team/${userId}`),
    userId,
  );
};

DecisionEngineClient.prototype.listDevices = async function (
  this: DecisionEngineClient,
  options: { page?: number; limit?: number } = {},
): Promise<DeviceListResponse> {
  const params = new URLSearchParams();
  if (options.page !== undefined) params.set("page", String(options.page));
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return assertDeviceListResponse(await this.request<unknown>("GET", `/v1/device/list${suffix}`));
};

DecisionEngineClient.prototype.revokeDevice = async function (
  this: DecisionEngineClient,
  registrationId: string,
): Promise<DeviceRevokeResponse> {
  if (typeof registrationId !== "string" || registrationId.length === 0) {
    throw new DecisionEngineError("revokeDevice requires a non-empty registrationId.");
  }
  return assertDeviceRevokeResponse(
    await this.request<unknown>("DELETE", `/v1/device/${registrationId}`),
  );
};

DecisionEngineClient.prototype.getAuditLogs = async function (
  this: DecisionEngineClient,
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
  if (options.page !== undefined) params.set("page", String(options.page));
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.actor_email !== undefined) params.set("actor_email", options.actor_email);
  if (options.action !== undefined) params.set("action", options.action);
  if (options.resource_type !== undefined) params.set("resource_type", options.resource_type);
  if (options.result !== undefined) params.set("result", options.result);
  if (options.policy_snapshot_id !== undefined) {
    params.set("policy_snapshot_id", options.policy_snapshot_id);
  }
  if (options.schema_snapshot_id !== undefined) {
    params.set("schema_snapshot_id", options.schema_snapshot_id);
  }
  if (options.manifest_version !== undefined) {
    params.set("manifest_version", options.manifest_version);
  }
  if (options.request_hash !== undefined) params.set("request_hash", options.request_hash);
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return assertAuditLogResponse(await this.request<unknown>("GET", `/v1/audit-logs${suffix}`));
};

DecisionEngineClient.prototype.getAuditLogArtifacts = async function (
  this: DecisionEngineClient,
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
  if (options.page !== undefined) params.set("page", String(options.page));
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.actor_email !== undefined) params.set("actor_email", options.actor_email);
  if (options.action !== undefined) params.set("action", options.action);
  if (options.resource_type !== undefined) params.set("resource_type", options.resource_type);
  if (options.result !== undefined) params.set("result", options.result);
  if (options.policy_snapshot_id !== undefined) {
    params.set("policy_snapshot_id", options.policy_snapshot_id);
  }
  if (options.schema_snapshot_id !== undefined) {
    params.set("schema_snapshot_id", options.schema_snapshot_id);
  }
  if (options.manifest_version !== undefined) {
    params.set("manifest_version", options.manifest_version);
  }
  if (options.request_hash !== undefined) params.set("request_hash", options.request_hash);
  if (options.content_hash !== undefined) params.set("content_hash", options.content_hash);
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return assertAuditLogResponse(
    await this.request<unknown>("GET", `/v1/audit-logs/artifacts${suffix}`),
  );
};

DecisionEngineClient.prototype.getExecutionPolicy = async function (
  this: DecisionEngineClient,
): Promise<ExecutionPolicyResponse> {
  return assertExecutionPolicyResponse(
    await this.request<unknown>("GET", "/v1/execution/policy"),
  );
};

DecisionEngineClient.prototype.listExecutionPolicySnapshots = async function (
  this: DecisionEngineClient,
): Promise<ExecutionPolicySnapshotListResponse> {
  return assertExecutionPolicySnapshotListResponse(
    await this.request<unknown>("GET", "/v1/execution/policy/snapshots"),
  );
};

DecisionEngineClient.prototype.updateExecutionPolicy = async function (
  this: DecisionEngineClient,
  request: UpdateExecutionPolicyRequest,
): Promise<ExecutionPolicyResponse> {
  return assertExecutionPolicyResponse(
    await this.request<unknown>(
      "PATCH",
      "/v1/execution/policy",
      normalizeUpdateExecutionPolicyRequest(request),
    ),
  );
};

DecisionEngineClient.prototype.listDeploymentRegions = async function (
  this: DecisionEngineClient,
): Promise<DeploymentRegionsResponse> {
  return assertDeploymentRegionsResponse(
    await this.request<unknown>("GET", "/v1/deployments/regions"),
  );
};

DecisionEngineClient.prototype.getDeployment = async function (
  this: DecisionEngineClient,
): Promise<DeploymentResponse | null> {
  const payload = await this.request<unknown>("GET", "/v1/deployments");
  if (payload === null) return null;
  return assertDeploymentResponse(payload, "Deployment response");
};

DecisionEngineClient.prototype.createDeployment = async function (
  this: DecisionEngineClient,
  request: CreateDeploymentRequest = {},
): Promise<DeploymentResponse> {
  return assertDeploymentResponse(
    await this.request<unknown>(
      "POST",
      "/v1/deployments",
      normalizeCreateDeploymentRequest(request),
    ),
    "Deployment create response",
  );
};

DecisionEngineClient.prototype.deleteDeployment = async function (
  this: DecisionEngineClient,
  deploymentId: string,
): Promise<DeploymentDeleteResponse> {
  return assertDeploymentDeleteResponse(
    await this.request<unknown>("DELETE", `/v1/deployments/${deploymentId}`),
  );
};

DecisionEngineClient.prototype.getDeploymentCost = async function (
  this: DecisionEngineClient,
  deploymentId: string,
): Promise<DeploymentCostResponse> {
  return assertDeploymentCostResponse(
    await this.request<unknown>("GET", `/v1/deployments/${deploymentId}/cost`),
  );
};

DecisionEngineClient.prototype.health = async function (
  this: DecisionEngineClient,
): Promise<{ status: string; timestamp: string }> {
  return this.request("GET", "/v1/health");
};

DecisionEngineClient.prototype.version = async function (
  this: DecisionEngineClient,
): Promise<{ api_version: string; engine_version: string; environment: string }> {
  return this.request("GET", "/v1/version");
};
