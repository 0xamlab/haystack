/** Auto-split sub-module of client.ts — agent runs and capability plane
 * methods for DecisionEngineClient.
 *
 * This module augments the {@link DecisionEngineClient} class via TypeScript
 * declaration merging and prototype assignment. Importing this file (for its
 * side effects) is required so the prototype assignments execute and the
 * augmented methods are available on `DecisionEngineClient` instances.
 */

import type {
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
  CapabilityProviderResponse,
  CapabilityRoutePlan,
  CapabilityRouteRequest,
} from "./types.js";
import { DecisionEngineClient } from "./_client_class.js";
import { appendQueryParameters } from "./_client_constants.js";

declare module "./_client_class.js" {
  interface DecisionEngineClient {
    createAgentRun(request: AgentRunCreateRequest): Promise<AgentRunResponse>;
    getAgentRun(runId: string): Promise<AgentRunResponse>;
    listAgentRuns(options?: {
      page?: number;
      limit?: number;
      status?: string;
      request_hash?: string;
      policy_snapshot_id?: string;
      schema_snapshot_id?: string;
    }): Promise<AgentRunListResponse>;
    getAgentRunEvents(
      runId: string,
      options?: { limit?: number },
    ): Promise<AgentRunEventsResponse>;
    streamAgentRunEvents(
      runId: string,
      options?: { limit?: number },
    ): AsyncGenerator<AgentRunStreamEventResponse>;
    listAgentRunCheckpoints(runId: string): Promise<AgentRunCheckpointsResponse>;
    queryAgentRunCheckpoints(options?: {
      page?: number;
      limit?: number;
      status?: string;
      request_hash?: string;
      policy_snapshot_id?: string;
      schema_snapshot_id?: string;
      run_id?: string;
      checkpoint_id?: string;
    }): Promise<AgentRunCheckpointListResponse>;
    listAgentRunMissionEvents(
      runId: string,
      options?: { limit?: number },
    ): Promise<AgentRunMissionEventsResponse>;
    queryAgentRunMissionEvents(options?: {
      page?: number;
      limit?: number;
      status?: string;
      request_hash?: string;
      policy_snapshot_id?: string;
      schema_snapshot_id?: string;
      run_id?: string;
      event_type?: string;
    }): Promise<AgentRunMissionEventListResponse>;
    replayAgentRun(
      runId: string,
      options?: { checkpoint_id?: string | null },
    ): Promise<AgentRunReplayResponse>;
    forkAgentRun(
      runId: string,
      options?: { checkpoint_id?: string | null },
    ): Promise<AgentRunResponse>;
    resumeAgentRun(runId: string): Promise<AgentRunResponse>;
    cancelAgentRun(runId: string): Promise<AgentRunResponse>;
    approveAgentRun(runId: string): Promise<AgentRunResponse>;
    listAgentRunTelemetry(
      runId: string,
      options?: { limit?: number },
    ): Promise<AgentRunTelemetryResponse>;
    queryAgentRunTelemetry(options?: {
      page?: number;
      limit?: number;
      status?: string;
      request_hash?: string;
      policy_snapshot_id?: string;
      schema_snapshot_id?: string;
      run_id?: string;
      telemetry_kind?: string;
      module_name?: string;
    }): Promise<AgentRunTelemetryListResponse>;
    listCapabilityProviders(): Promise<CapabilityProviderResponse[]>;
    getCapabilityProvider(providerId: string): Promise<CapabilityProviderResponse>;
    listCapabilityBindings(options?: {
      providerId?: string;
      scope?: string;
    }): Promise<CapabilityBindingResponse[]>;
    createCapabilityBinding(
      request: CapabilityBindingCreateRequest,
    ): Promise<CapabilityBindingResponse>;
    getCapabilityBinding(bindingId: string): Promise<CapabilityBindingResponse>;
    updateCapabilityBinding(
      bindingId: string,
      request: CapabilityBindingUpdateRequest,
    ): Promise<CapabilityBindingResponse>;
    deleteCapabilityBinding(bindingId: string): Promise<void>;
    previewTestCapabilityBinding(
      request: CapabilityBindingPreviewRequest,
    ): Promise<CapabilityBindingTestResult>;
    testCapabilityBinding(bindingId: string): Promise<CapabilityBindingTestResult>;
    previewDiscoverCapabilityBinding(
      request: CapabilityBindingPreviewRequest,
    ): Promise<CapabilityDiscoverResponse>;
    discoverCapabilityBinding(bindingId: string): Promise<CapabilityDiscoverResponse>;
    startCapabilityAuthorization(
      bindingId: string,
      request: CapabilityAuthorizationStartRequest,
    ): Promise<CapabilityAuthorizationStartResponse>;
    completeCapabilityAuthorization(
      bindingId: string,
      request: CapabilityAuthorizationCompleteRequest,
    ): Promise<CapabilityAuthorizationCompleteResponse>;
    listCapabilities(options?: {
      kinds?: string[];
      providerIds?: string[];
      bindingIds?: string[];
    }): Promise<CapabilityCatalogEntry[]>;
    getCapability(
      capabilityId: string,
      options?: { includeInstruction?: boolean },
    ): Promise<CapabilityCatalogEntry>;
    routeCapabilities(request: CapabilityRouteRequest): Promise<CapabilityRoutePlan>;
    executeCapability(request: CapabilityExecutionRequest): Promise<CapabilityExecutionResponse>;
    recordCapabilityOutcome(
      request: CapabilityOutcomeRecordRequest,
    ): Promise<CapabilityOutcomeRecord>;
    listSkills(): Promise<CapabilityCatalogEntry[]>;
    enableSkill(request: {
      skill_name: string;
      instruction: string;
      description?: string;
      tags?: string[];
      artifact_affinities?: string[];
      execution_owner?: "algenta_managed" | "client_managed";
    }): Promise<CapabilityDiscoverResponse>;
    disableSkill(bindingId: string): Promise<void>;
    listMcpProviders(): Promise<CapabilityProviderResponse[]>;
  }
}

DecisionEngineClient.prototype.createAgentRun = async function (
  this: DecisionEngineClient,
  request: AgentRunCreateRequest,
): Promise<AgentRunResponse> {
  return this.request<AgentRunResponse>("POST", "/v1/agent/runs", request);
};

DecisionEngineClient.prototype.getAgentRun = async function (
  this: DecisionEngineClient,
  runId: string,
): Promise<AgentRunResponse> {
  return this.request<AgentRunResponse>("GET", `/v1/agent/runs/${runId}`);
};

DecisionEngineClient.prototype.listAgentRuns = async function (
  this: DecisionEngineClient,
  options: {
    page?: number;
    limit?: number;
    status?: string;
    request_hash?: string;
    policy_snapshot_id?: string;
    schema_snapshot_id?: string;
  } = {},
): Promise<AgentRunListResponse> {
  const path = appendQueryParameters("/v1/agent/runs", {
    page: options.page ?? 1,
    limit: options.limit ?? 25,
    status: options.status,
    request_hash: options.request_hash,
    policy_snapshot_id: options.policy_snapshot_id,
    schema_snapshot_id: options.schema_snapshot_id,
  });
  return this.request<AgentRunListResponse>("GET", path);
};

DecisionEngineClient.prototype.getAgentRunEvents = async function (
  this: DecisionEngineClient,
  runId: string,
  options: { limit?: number } = {},
): Promise<AgentRunEventsResponse> {
  const path = appendQueryParameters(`/v1/agent/runs/${runId}/events`, {
    limit: options.limit ?? 1000,
  });
  return this.request<AgentRunEventsResponse>("GET", path);
};

DecisionEngineClient.prototype.streamAgentRunEvents = async function* (
  this: DecisionEngineClient,
  runId: string,
  options: { limit?: number } = {},
): AsyncGenerator<AgentRunStreamEventResponse> {
  const path = appendQueryParameters(`/v1/agent/runs/${runId}/events`, {
    limit: options.limit ?? 1000,
    stream: "true",
  });
  for await (const event of this.requestStream<AgentRunStreamEventResponse>("GET", path)) {
    yield event;
  }
};

DecisionEngineClient.prototype.listAgentRunCheckpoints = async function (
  this: DecisionEngineClient,
  runId: string,
): Promise<AgentRunCheckpointsResponse> {
  return this.request<AgentRunCheckpointsResponse>("GET", `/v1/agent/runs/${runId}/checkpoints`);
};

DecisionEngineClient.prototype.queryAgentRunCheckpoints = async function (
  this: DecisionEngineClient,
  options: {
    page?: number;
    limit?: number;
    status?: string;
    request_hash?: string;
    policy_snapshot_id?: string;
    schema_snapshot_id?: string;
    run_id?: string;
    checkpoint_id?: string;
  } = {},
): Promise<AgentRunCheckpointListResponse> {
  const path = appendQueryParameters("/v1/agent/runs/checkpoints", {
    page: options.page ?? 1,
    limit: options.limit ?? 25,
    status: options.status,
    request_hash: options.request_hash,
    policy_snapshot_id: options.policy_snapshot_id,
    schema_snapshot_id: options.schema_snapshot_id,
    run_id: options.run_id,
    checkpoint_id: options.checkpoint_id,
  });
  return this.request<AgentRunCheckpointListResponse>("GET", path);
};

DecisionEngineClient.prototype.listAgentRunMissionEvents = async function (
  this: DecisionEngineClient,
  runId: string,
  options: { limit?: number } = {},
): Promise<AgentRunMissionEventsResponse> {
  const path = appendQueryParameters(`/v1/agent/runs/${runId}/mission-events`, {
    limit: options.limit ?? 1000,
  });
  return this.request<AgentRunMissionEventsResponse>("GET", path);
};

DecisionEngineClient.prototype.queryAgentRunMissionEvents = async function (
  this: DecisionEngineClient,
  options: {
    page?: number;
    limit?: number;
    status?: string;
    request_hash?: string;
    policy_snapshot_id?: string;
    schema_snapshot_id?: string;
    run_id?: string;
    event_type?: string;
  } = {},
): Promise<AgentRunMissionEventListResponse> {
  const path = appendQueryParameters("/v1/agent/runs/mission-events", {
    page: options.page ?? 1,
    limit: options.limit ?? 25,
    status: options.status,
    request_hash: options.request_hash,
    policy_snapshot_id: options.policy_snapshot_id,
    schema_snapshot_id: options.schema_snapshot_id,
    run_id: options.run_id,
    event_type: options.event_type,
  });
  return this.request<AgentRunMissionEventListResponse>("GET", path);
};

DecisionEngineClient.prototype.replayAgentRun = async function (
  this: DecisionEngineClient,
  runId: string,
  options: { checkpoint_id?: string | null } = {},
): Promise<AgentRunReplayResponse> {
  return this.request<AgentRunReplayResponse>("POST", `/v1/agent/runs/${runId}/replay`, {
    checkpoint_id: options.checkpoint_id ?? null,
  });
};

DecisionEngineClient.prototype.forkAgentRun = async function (
  this: DecisionEngineClient,
  runId: string,
  options: { checkpoint_id?: string | null } = {},
): Promise<AgentRunResponse> {
  return this.request<AgentRunResponse>("POST", `/v1/agent/runs/${runId}/fork`, {
    checkpoint_id: options.checkpoint_id ?? null,
  });
};

DecisionEngineClient.prototype.resumeAgentRun = async function (
  this: DecisionEngineClient,
  runId: string,
): Promise<AgentRunResponse> {
  return this.request<AgentRunResponse>("POST", `/v1/agent/runs/${runId}/resume`, {});
};

DecisionEngineClient.prototype.cancelAgentRun = async function (
  this: DecisionEngineClient,
  runId: string,
): Promise<AgentRunResponse> {
  return this.request<AgentRunResponse>("POST", `/v1/agent/runs/${runId}/cancel`, {});
};

DecisionEngineClient.prototype.approveAgentRun = async function (
  this: DecisionEngineClient,
  runId: string,
): Promise<AgentRunResponse> {
  return this.request<AgentRunResponse>("POST", `/v1/agent/runs/${runId}/approve`, {});
};

DecisionEngineClient.prototype.listAgentRunTelemetry = async function (
  this: DecisionEngineClient,
  runId: string,
  options: { limit?: number } = {},
): Promise<AgentRunTelemetryResponse> {
  const path = appendQueryParameters(`/v1/agent/runs/${runId}/telemetry`, {
    limit: options.limit ?? 1000,
  });
  return this.request<AgentRunTelemetryResponse>("GET", path);
};

DecisionEngineClient.prototype.queryAgentRunTelemetry = async function (
  this: DecisionEngineClient,
  options: {
    page?: number;
    limit?: number;
    status?: string;
    request_hash?: string;
    policy_snapshot_id?: string;
    schema_snapshot_id?: string;
    run_id?: string;
    telemetry_kind?: string;
    module_name?: string;
  } = {},
): Promise<AgentRunTelemetryListResponse> {
  const path = appendQueryParameters("/v1/agent/runs/telemetry", {
    page: options.page ?? 1,
    limit: options.limit ?? 25,
    status: options.status,
    request_hash: options.request_hash,
    policy_snapshot_id: options.policy_snapshot_id,
    schema_snapshot_id: options.schema_snapshot_id,
    run_id: options.run_id,
    telemetry_kind: options.telemetry_kind,
    module_name: options.module_name,
  });
  return this.request<AgentRunTelemetryListResponse>("GET", path);
};

DecisionEngineClient.prototype.listCapabilityProviders = async function (
  this: DecisionEngineClient,
): Promise<CapabilityProviderResponse[]> {
  return this.request<CapabilityProviderResponse[]>("GET", "/v1/capability-providers");
};

DecisionEngineClient.prototype.getCapabilityProvider = async function (
  this: DecisionEngineClient,
  providerId: string,
): Promise<CapabilityProviderResponse> {
  return this.request<CapabilityProviderResponse>(
    "GET",
    `/v1/capability-providers/${providerId}`,
  );
};

DecisionEngineClient.prototype.listCapabilityBindings = async function (
  this: DecisionEngineClient,
  options: { providerId?: string; scope?: string } = {},
): Promise<CapabilityBindingResponse[]> {
  const path = appendQueryParameters("/v1/capability-bindings", {
    provider_id: options.providerId,
    scope: options.scope,
  });
  return this.request<CapabilityBindingResponse[]>("GET", path);
};

DecisionEngineClient.prototype.createCapabilityBinding = async function (
  this: DecisionEngineClient,
  request: CapabilityBindingCreateRequest,
): Promise<CapabilityBindingResponse> {
  return this.request<CapabilityBindingResponse>("POST", "/v1/capability-bindings", request);
};

DecisionEngineClient.prototype.getCapabilityBinding = async function (
  this: DecisionEngineClient,
  bindingId: string,
): Promise<CapabilityBindingResponse> {
  return this.request<CapabilityBindingResponse>("GET", `/v1/capability-bindings/${bindingId}`);
};

DecisionEngineClient.prototype.updateCapabilityBinding = async function (
  this: DecisionEngineClient,
  bindingId: string,
  request: CapabilityBindingUpdateRequest,
): Promise<CapabilityBindingResponse> {
  return this.request<CapabilityBindingResponse>(
    "PATCH",
    `/v1/capability-bindings/${bindingId}`,
    request,
  );
};

DecisionEngineClient.prototype.deleteCapabilityBinding = async function (
  this: DecisionEngineClient,
  bindingId: string,
): Promise<void> {
  await this.request("DELETE", `/v1/capability-bindings/${bindingId}`);
};

DecisionEngineClient.prototype.previewTestCapabilityBinding = async function (
  this: DecisionEngineClient,
  request: CapabilityBindingPreviewRequest,
): Promise<CapabilityBindingTestResult> {
  return this.request<CapabilityBindingTestResult>(
    "POST",
    "/v1/capability-bindings/test",
    request,
  );
};

DecisionEngineClient.prototype.testCapabilityBinding = async function (
  this: DecisionEngineClient,
  bindingId: string,
): Promise<CapabilityBindingTestResult> {
  return this.request<CapabilityBindingTestResult>(
    "POST",
    `/v1/capability-bindings/${bindingId}/test`,
  );
};

DecisionEngineClient.prototype.previewDiscoverCapabilityBinding = async function (
  this: DecisionEngineClient,
  request: CapabilityBindingPreviewRequest,
): Promise<CapabilityDiscoverResponse> {
  return this.request<CapabilityDiscoverResponse>(
    "POST",
    "/v1/capability-bindings/discover",
    request,
  );
};

DecisionEngineClient.prototype.discoverCapabilityBinding = async function (
  this: DecisionEngineClient,
  bindingId: string,
): Promise<CapabilityDiscoverResponse> {
  return this.request<CapabilityDiscoverResponse>(
    "POST",
    `/v1/capability-bindings/${bindingId}/discover`,
  );
};

DecisionEngineClient.prototype.startCapabilityAuthorization = async function (
  this: DecisionEngineClient,
  bindingId: string,
  request: CapabilityAuthorizationStartRequest,
): Promise<CapabilityAuthorizationStartResponse> {
  return this.request<CapabilityAuthorizationStartResponse>(
    "POST",
    `/v1/capability-bindings/${bindingId}/authorize/start`,
    request,
  );
};

DecisionEngineClient.prototype.completeCapabilityAuthorization = async function (
  this: DecisionEngineClient,
  bindingId: string,
  request: CapabilityAuthorizationCompleteRequest,
): Promise<CapabilityAuthorizationCompleteResponse> {
  return this.request<CapabilityAuthorizationCompleteResponse>(
    "POST",
    `/v1/capability-bindings/${bindingId}/authorize/complete`,
    request,
  );
};

DecisionEngineClient.prototype.listCapabilities = async function (
  this: DecisionEngineClient,
  options: {
    kinds?: string[];
    providerIds?: string[];
    bindingIds?: string[];
  } = {},
): Promise<CapabilityCatalogEntry[]> {
  const params = new URLSearchParams();
  (options.kinds ?? []).forEach(kind => params.append("kinds", kind));
  (options.providerIds ?? []).forEach(providerId => params.append("provider_ids", providerId));
  (options.bindingIds ?? []).forEach(bindingId => params.append("binding_ids", bindingId));
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return this.request<CapabilityCatalogEntry[]>("GET", `/v1/capabilities${suffix}`);
};

DecisionEngineClient.prototype.getCapability = async function (
  this: DecisionEngineClient,
  capabilityId: string,
  options: { includeInstruction?: boolean } = {},
): Promise<CapabilityCatalogEntry> {
  const path = appendQueryParameters(`/v1/capabilities/${capabilityId}`, {
    include_instruction: options.includeInstruction ? 1 : undefined,
  });
  return this.request<CapabilityCatalogEntry>("GET", path);
};

DecisionEngineClient.prototype.routeCapabilities = async function (
  this: DecisionEngineClient,
  request: CapabilityRouteRequest,
): Promise<CapabilityRoutePlan> {
  return this.request<CapabilityRoutePlan>("POST", "/v1/capabilities/route", request);
};

DecisionEngineClient.prototype.executeCapability = async function (
  this: DecisionEngineClient,
  request: CapabilityExecutionRequest,
): Promise<CapabilityExecutionResponse> {
  return this.request<CapabilityExecutionResponse>("POST", "/v1/capabilities/execute", request);
};

DecisionEngineClient.prototype.recordCapabilityOutcome = async function (
  this: DecisionEngineClient,
  request: CapabilityOutcomeRecordRequest,
): Promise<CapabilityOutcomeRecord> {
  return this.request<CapabilityOutcomeRecord>("POST", "/v1/capabilities/outcomes", request);
};

DecisionEngineClient.prototype.listSkills = async function (
  this: DecisionEngineClient,
): Promise<CapabilityCatalogEntry[]> {
  return this.listCapabilities({ kinds: ["skill"] });
};

DecisionEngineClient.prototype.enableSkill = async function (
  this: DecisionEngineClient,
  request: {
    skill_name: string;
    instruction: string;
    description?: string;
    tags?: string[];
    artifact_affinities?: string[];
    execution_owner?: "algenta_managed" | "client_managed";
  },
): Promise<CapabilityDiscoverResponse> {
  const binding = await this.createCapabilityBinding({
    provider_id: "provider.skill_pack.algenta",
    profile_id: "profile.skill_pack.user",
    binding_name: request.skill_name,
    scope: "user",
    execution_owner: request.execution_owner ?? "client_managed",
    config: {
      manifest: {
        capabilities: [
          {
            capability_id: `cap.skill.${request.skill_name.toLowerCase().replace(/\s+/g, "_")}`,
            name: request.skill_name,
            description: request.description,
            kind: "skill",
            implementation_kind: "instruction_only",
            execution_owner: request.execution_owner ?? "client_managed",
            instruction: request.instruction,
            artifact_affinities: request.artifact_affinities ?? [],
            tags: request.tags ?? [],
            replayability: "deterministic",
          },
        ],
      },
    },
  });
  return this.discoverCapabilityBinding(binding.binding_id);
};

DecisionEngineClient.prototype.disableSkill = async function (
  this: DecisionEngineClient,
  bindingId: string,
): Promise<void> {
  await this.deleteCapabilityBinding(bindingId);
};

DecisionEngineClient.prototype.listMcpProviders = async function (
  this: DecisionEngineClient,
): Promise<CapabilityProviderResponse[]> {
  const providers = await this.listCapabilityProviders();
  return providers.filter(provider => provider.provider_type === "mcp_provider");
};
