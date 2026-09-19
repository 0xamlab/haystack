// SPDX-License-Identifier: Apache-2.0
/** Auto-split sub-module of runtime.ts — capability plane wrapper and
 * local-mode capability plane implementations for the Runtime class.
 *
 * This module augments the {@link Runtime} class via TypeScript declaration
 * merging and prototype assignment. Importing this file (for its side
 * effects) is required so the prototype assignments execute and the
 * augmented methods are available on `Runtime` instances.
 */

import type {
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
  PlatformContractResponse,
} from "./types.js";
import { assertPlatformContractResponse } from "./client.js";
import { Runtime } from "./_runtime_class.js";
import { RuntimeValidationError } from "./_runtime_errors.js";
import { sha256Hex } from "./_runtime_helpers_a.js";

declare module "./_runtime_class.js" {
  interface Runtime {
    getContract(): Promise<PlatformContractResponse>;
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

Runtime.prototype.getContract = async function (
  this: Runtime,
): Promise<PlatformContractResponse> {
  this.requireApiTransport("getContract");
  return this.requestValidatedContractPayload(
    "getContract",
    () => this.client().getContract(),
    assertPlatformContractResponse,
  );
};

Runtime.prototype.listCapabilityProviders = async function (
  this: Runtime,
): Promise<CapabilityProviderResponse[]> {
  if (this.usesApiTransport()) {
    return this.client().listCapabilityProviders();
  }
  return this.localProviderResponses();
};

Runtime.prototype.getCapabilityProvider = async function (
  this: Runtime,
  providerId: string,
): Promise<CapabilityProviderResponse> {
  if (this.usesApiTransport()) {
    return this.client().getCapabilityProvider(providerId);
  }
  const provider = this.localProviderResponses().find(item => item.provider_id === providerId);
  if (!provider) {
    throw new RuntimeValidationError(
      "provider_not_found",
      `Capability provider '${providerId}' was not found in local mode.`,
    );
  }
  return provider;
};

Runtime.prototype.listCapabilityBindings = async function (
  this: Runtime,
  options: { providerId?: string; scope?: string } = {},
): Promise<CapabilityBindingResponse[]> {
  if (this.usesApiTransport()) {
    return this.client().listCapabilityBindings(options);
  }
  return this.localBindingsArray().filter(binding => {
    if (options.providerId && binding.provider_id !== options.providerId) return false;
    if (options.scope && binding.scope !== options.scope) return false;
    return true;
  });
};

Runtime.prototype.createCapabilityBinding = async function (
  this: Runtime,
  request: CapabilityBindingCreateRequest,
): Promise<CapabilityBindingResponse> {
  if (this.usesApiTransport()) {
    return this.client().createCapabilityBinding(request);
  }
  const now = this.nowIso();
  const bindingId = `local-binding-${sha256Hex(
    JSON.stringify({ request, now }).slice(0, 2048),
  ).slice(0, 24)}`;
  const binding: CapabilityBindingResponse = {
    binding_id: bindingId,
    provider_id: request.provider_id,
    profile_id: request.profile_id,
    binding_name: request.binding_name,
    scope: request.scope ?? "workspace",
    scope_ref: request.scope_ref ?? "local",
    status: "unconfigured",
    execution_owner: request.execution_owner ?? "client_managed",
    config: request.config ?? null,
    customer_metadata: request.customer_metadata ?? null,
    system_managed: false,
    last_tested_at: null,
    last_discovered_at: null,
    authorized_at: null,
    quarantine_reason: null,
    discovery_error_message: null,
    test_error_message: null,
    created_at: now,
    updated_at: now,
  };
  this.localCapabilityBindings.set(bindingId, binding);
  return binding;
};

Runtime.prototype.getCapabilityBinding = async function (
  this: Runtime,
  bindingId: string,
): Promise<CapabilityBindingResponse> {
  if (this.usesApiTransport()) {
    return this.client().getCapabilityBinding(bindingId);
  }
  const binding = this.localCapabilityBindings.get(bindingId);
  if (!binding) {
    throw new RuntimeValidationError(
      "binding_not_found",
      `Capability binding '${bindingId}' was not found in local mode.`,
    );
  }
  return binding;
};

Runtime.prototype.updateCapabilityBinding = async function (
  this: Runtime,
  bindingId: string,
  request: CapabilityBindingUpdateRequest,
): Promise<CapabilityBindingResponse> {
  if (this.usesApiTransport()) {
    return this.client().updateCapabilityBinding(bindingId, request);
  }
  const binding = await this.getCapabilityBinding(bindingId);
  const updated: CapabilityBindingResponse = {
    ...binding,
    binding_name: request.binding_name ?? binding.binding_name,
    scope: request.scope ?? binding.scope,
    scope_ref: request.scope_ref ?? binding.scope_ref,
    status: request.status ?? binding.status,
    execution_owner: request.execution_owner ?? binding.execution_owner,
    config: request.config ?? binding.config,
    customer_metadata: request.customer_metadata ?? binding.customer_metadata,
    updated_at: this.nowIso(),
  };
  this.localCapabilityBindings.set(bindingId, updated);
  return updated;
};

Runtime.prototype.deleteCapabilityBinding = async function (
  this: Runtime,
  bindingId: string,
): Promise<void> {
  if (this.usesApiTransport()) {
    await this.client().deleteCapabilityBinding(bindingId);
    return;
  }
  this.localCapabilityBindings.delete(bindingId);
  Array.from(this.localCapabilityCatalog.values())
    .filter(entry => entry.binding_id === bindingId)
    .forEach(entry => this.localCapabilityCatalog.delete(entry.capability_id));
};

Runtime.prototype.previewTestCapabilityBinding = async function (
  this: Runtime,
  request: CapabilityBindingPreviewRequest,
): Promise<CapabilityBindingTestResult> {
  if (this.usesApiTransport()) {
    return this.client().previewTestCapabilityBinding(request);
  }
  const manifest =
    request.config && typeof request.config === "object" && !Array.isArray(request.config)
      ? (request.config as Record<string, unknown>).manifest
      : null;
  if (
    manifest &&
    typeof manifest === "object" &&
    !Array.isArray(manifest) &&
    Array.isArray((manifest as { capabilities?: unknown }).capabilities)
  ) {
    return {
      success: true,
      binding_status: "ready",
      message: "Local manifest-backed capability binding is valid.",
      latency_ms: null,
      details: {
        capability_count: ((manifest as { capabilities: unknown[] }).capabilities ?? []).length,
      },
    };
  }
  const adapterMatch = this.localCapabilitiesArray().some(
    entry => entry.provider_id === request.provider_id && entry.profile_id === request.profile_id,
  );
  return adapterMatch
    ? {
        success: true,
        binding_status: "ready",
        message: "Local adapter-backed capability binding is available.",
        latency_ms: null,
        details: { adapter_backed: true },
      }
    : {
        success: false,
        binding_status: "unconfigured",
        message:
          "Local capability binding requires config.manifest.capabilities or a matching registered adapter.",
        latency_ms: null,
        details: { required_field: "config.manifest.capabilities" },
      };
};

Runtime.prototype.testCapabilityBinding = async function (
  this: Runtime,
  bindingId: string,
): Promise<CapabilityBindingTestResult> {
  if (this.usesApiTransport()) {
    return this.client().testCapabilityBinding(bindingId);
  }
  const binding = await this.getCapabilityBinding(bindingId);
  const result = await this.previewTestCapabilityBinding({
    provider_id: binding.provider_id,
    profile_id: binding.profile_id,
    scope: binding.scope,
    scope_ref: binding.scope_ref,
    execution_owner: binding.execution_owner,
    config: binding.config ?? undefined,
    customer_metadata: binding.customer_metadata ?? undefined,
  });
  this.localCapabilityBindings.set(bindingId, {
    ...binding,
    status: result.binding_status,
    last_tested_at: this.nowIso(),
    test_error_message: result.success ? null : result.message,
    updated_at: this.nowIso(),
  });
  return result;
};

Runtime.prototype.previewDiscoverCapabilityBinding = async function (
  this: Runtime,
  request: CapabilityBindingPreviewRequest,
): Promise<CapabilityDiscoverResponse> {
  if (this.usesApiTransport()) {
    return this.client().previewDiscoverCapabilityBinding(request);
  }
  return this.discoverLocalBinding(request);
};

Runtime.prototype.discoverCapabilityBinding = async function (
  this: Runtime,
  bindingId: string,
): Promise<CapabilityDiscoverResponse> {
  if (this.usesApiTransport()) {
    return this.client().discoverCapabilityBinding(bindingId);
  }
  const binding = await this.getCapabilityBinding(bindingId);
  const response = this.discoverLocalBinding(binding);
  Array.from(this.localCapabilityCatalog.values())
    .filter(entry => entry.binding_id === bindingId)
    .forEach(entry => this.localCapabilityCatalog.delete(entry.capability_id));
  response.capabilities.forEach(entry =>
    this.localCapabilityCatalog.set(entry.capability_id, entry),
  );
  this.localCapabilityBindings.set(bindingId, {
    ...binding,
    status: response.binding_status,
    last_discovered_at: response.discovered_at,
    discovery_error_message: response.capabilities.length > 0 ? null : response.message,
    updated_at: this.nowIso(),
  });
  return response;
};

Runtime.prototype.startCapabilityAuthorization = async function (
  this: Runtime,
  bindingId: string,
  request: CapabilityAuthorizationStartRequest,
): Promise<CapabilityAuthorizationStartResponse> {
  if (this.usesApiTransport()) {
    return this.client().startCapabilityAuthorization(bindingId, request);
  }
  const binding = await this.getCapabilityBinding(bindingId);
  const authorizeUrl =
    binding.config &&
    typeof binding.config === "object" &&
    !Array.isArray(binding.config) &&
    typeof (binding.config as { authorization_url?: unknown }).authorization_url === "string"
      ? String((binding.config as { authorization_url?: unknown }).authorization_url)
      : null;
  if (!authorizeUrl) {
    throw new RuntimeValidationError(
      "authorization_not_supported",
      "This local capability binding does not expose authorization_url.",
    );
  }
  const sessionId = `local-auth-${sha256Hex(
    JSON.stringify({ bindingId, request, now: this.nowIso() }),
  ).slice(0, 24)}`;
  const expiresAt = new Date(Date.now() + 15 * 60 * 1000).toISOString();
  const requestedScopes = request.requested_scopes ?? [];
  const response: CapabilityAuthorizationStartResponse = {
    session_id: sessionId,
    binding_id: bindingId,
    provider_id: binding.provider_id,
    authorize_url: authorizeUrl,
    expires_at: expiresAt,
    requested_scopes: requestedScopes,
  };
  this.localCapabilityAuthSessions.set(sessionId, response);
  this.localCapabilityBindings.set(bindingId, {
    ...binding,
    status: "authorizing",
    updated_at: this.nowIso(),
  });
  return response;
};

Runtime.prototype.completeCapabilityAuthorization = async function (
  this: Runtime,
  bindingId: string,
  request: CapabilityAuthorizationCompleteRequest,
): Promise<CapabilityAuthorizationCompleteResponse> {
  if (this.usesApiTransport()) {
    return this.client().completeCapabilityAuthorization(bindingId, request);
  }
  const session = this.localCapabilityAuthSessions.get(request.session_id);
  if (!session || session.binding_id !== bindingId) {
    throw new RuntimeValidationError(
      "authorization_session_not_found",
      "Local capability authorization session was not found.",
    );
  }
  const binding = await this.getCapabilityBinding(bindingId);
  const authorizedAt = this.nowIso();
  this.localCapabilityBindings.set(bindingId, {
    ...binding,
    status: "ready",
    authorized_at: authorizedAt,
    updated_at: authorizedAt,
  });
  return {
    session_id: session.session_id,
    binding_id: bindingId,
    provider_id: binding.provider_id,
    status: "completed",
    authorized_at: authorizedAt,
  };
};

Runtime.prototype.listCapabilities = async function (
  this: Runtime,
  options: {
    kinds?: string[];
    providerIds?: string[];
    bindingIds?: string[];
  } = {},
): Promise<CapabilityCatalogEntry[]> {
  if (this.usesApiTransport()) {
    return this.client().listCapabilities(options);
  }
  return this.localCapabilitiesArray().filter(entry => {
    if (options.kinds?.length && !options.kinds.includes(entry.kind)) return false;
    if (options.providerIds?.length && !options.providerIds.includes(entry.provider_id)) return false;
    if (options.bindingIds?.length && !options.bindingIds.includes(entry.binding_id)) return false;
    return true;
  });
};

Runtime.prototype.getCapability = async function (
  this: Runtime,
  capabilityId: string,
  options: { includeInstruction?: boolean } = {},
): Promise<CapabilityCatalogEntry> {
  if (this.usesApiTransport()) {
    return this.client().getCapability(capabilityId, options);
  }
  const capability = this.localCapabilityCatalog.get(capabilityId);
  if (!capability) {
    throw new RuntimeValidationError(
      "capability_not_found",
      `Capability '${capabilityId}' was not found in local mode.`,
    );
  }
  if (options.includeInstruction) return capability;
  const { instruction_text: _instruction, ...rest } = capability;
  void _instruction;
  return { ...rest, instruction_text: null };
};

Runtime.prototype.routeCapabilities = async function (
  this: Runtime,
  request: CapabilityRouteRequest,
): Promise<CapabilityRoutePlan> {
  if (this.usesApiTransport()) {
    return this.client().routeCapabilities(request);
  }
  const tokenize = (value: string): string[] =>
    value
      .toLowerCase()
      .split(/[^a-z0-9_.-]+/g)
      .filter(Boolean);
  const objectiveTokens = new Set(tokenize(request.objective));
  const entries = await this.listCapabilities({
    kinds: request.kinds,
    providerIds: request.provider_ids,
    bindingIds: request.binding_ids,
  });
  const filtered = entries.filter(entry => {
    if (
      request.execution_owners?.length &&
      !request.execution_owners.includes(entry.execution_owner)
    ) {
      return false;
    }
    return entry.binding_status !== "quarantined";
  });
  if (filtered.length === 0) {
    throw new RuntimeValidationError(
      "capability_route_not_found",
      "No capabilities matched the requested local route filters.",
    );
  }
  const scored = filtered
    .map(entry => {
      const overlap = new Set(
        [
          ...tokenize(entry.name),
          ...tokenize(entry.description ?? ""),
          ...(entry.tags ?? []).flatMap(tokenize),
          ...(entry.artifact_affinities ?? []).flatMap(tokenize),
        ].filter(token => objectiveTokens.has(token)),
      );
      let score = overlap.size * 10 + (entry.binding_status === "ready" ? 15 : 0);
      if ((request.tags ?? []).some(tag => entry.tags.includes(tag))) score += 8;
      if (
        (request.artifact_affinities ?? []).some(tag =>
          entry.artifact_affinities.includes(tag),
        )
      ) {
        score += 8;
      }
      const confidence = Math.max(0.05, Math.min(0.99, score / 100));
      return {
        entry,
        confidence,
        reason:
          overlap.size > 0
            ? `token overlap: ${Array.from(overlap).sort().join(", ")}`
            : "default local catalog ranking",
      };
    })
    .sort((left, right) => {
      if (right.confidence !== left.confidence) return right.confidence - left.confidence;
      return left.entry.name.localeCompare(right.entry.name);
    });
  const selected = scored[0];
  return {
    selected_capability_id: selected.entry.capability_id,
    selected_provider_id: selected.entry.provider_id,
    selected_binding_id: selected.entry.binding_id,
    kind: selected.entry.kind,
    execution_owner: selected.entry.execution_owner,
    requires_approval: selected.entry.approval_required,
    confidence: Number(selected.confidence.toFixed(4)),
    reason: selected.reason,
    fallbacks: scored.slice(1, 1 + (request.max_fallbacks ?? 3)).map(item => ({
      capability_id: item.entry.capability_id,
      provider_id: item.entry.provider_id,
      binding_id: item.entry.binding_id,
      kind: item.entry.kind,
      execution_owner: item.entry.execution_owner,
      confidence: Number(item.confidence.toFixed(4)),
      reason: item.reason,
      selected_tool_name: item.entry.selected_tool_name ?? null,
      instruction_artifact_ref: item.entry.instruction_artifact_ref ?? null,
    })),
    policy_snapshot_id: "capability-plane-policy-v1",
    selected_tool_name: selected.entry.selected_tool_name ?? null,
    instruction_artifact_ref: selected.entry.instruction_artifact_ref ?? null,
  };
};

Runtime.prototype.executeCapability = async function (
  this: Runtime,
  request: CapabilityExecutionRequest,
): Promise<CapabilityExecutionResponse> {
  if (this.usesApiTransport()) {
    return this.client().executeCapability(request);
  }
  const capability = await this.getCapability(request.capability_id, {
    includeInstruction: true,
  });
  if (request.binding_id && request.binding_id !== capability.binding_id) {
    throw new RuntimeValidationError(
      "binding_mismatch",
      "binding_id does not match the selected capability binding.",
    );
  }
  if (capability.execution_owner !== "client_managed") {
    throw new RuntimeValidationError(
      "capability_execution_owner_unsupported",
      "Local runtime execution only supports client_managed capabilities.",
      {
        capability_id: capability.capability_id,
        execution_owner: capability.execution_owner,
      },
    );
  }
  const executionSessionId = `local-exec-${sha256Hex(
    JSON.stringify({ request, ts: this.nowIso() }),
  ).slice(0, 24)}`;
  const startedAt = this.nowIso();
  if (capability.implementation_kind === "instruction_only") {
    return {
      execution_session_id: executionSessionId,
      capability_id: capability.capability_id,
      provider_id: capability.provider_id,
      binding_id: capability.binding_id,
      execution_owner: capability.execution_owner,
      status: "succeeded",
      output: {
        instruction_artifact_ref: capability.instruction_artifact_ref ?? null,
        instruction_text: capability.instruction_text ?? null,
        capability_id: capability.capability_id,
      },
      error: null,
      started_at: startedAt,
      completed_at: this.nowIso(),
    };
  }
  const adapter = this.capabilityAdapters.get(capability.capability_id);
  if (!adapter) {
    throw new RuntimeValidationError(
      "capability_adapter_missing",
      "Local capability execution requires a registered adapter.",
      { capability_id: capability.capability_id },
    );
  }
  const output = (await adapter.execute(request, capability)) ?? null;
  return {
    execution_session_id: executionSessionId,
    capability_id: capability.capability_id,
    provider_id: capability.provider_id,
    binding_id: capability.binding_id,
    execution_owner: capability.execution_owner,
    status: "succeeded",
    output,
    error: null,
    started_at: startedAt,
    completed_at: this.nowIso(),
  };
};

Runtime.prototype.recordCapabilityOutcome = async function (
  this: Runtime,
  request: CapabilityOutcomeRecordRequest,
): Promise<CapabilityOutcomeRecord> {
  if (this.usesApiTransport()) {
    return this.client().recordCapabilityOutcome(request);
  }
  const outcome: CapabilityOutcomeRecord = {
    outcome_id: `local-outcome-${sha256Hex(
      JSON.stringify({ request, ts: this.nowIso() }),
    ).slice(0, 24)}`,
    capability_id: request.capability_id,
    provider_id: request.provider_id,
    binding_id: request.binding_id ?? null,
    success: request.success ?? null,
    result_status: request.result_status ?? "reported",
    confidence: request.confidence ?? null,
    latency_ms: request.latency_ms ?? null,
    error_code: request.error_code ?? null,
    details: request.details ?? null,
    created_at: this.nowIso(),
  };
  this.localCapabilityOutcomes.push(outcome);
  return outcome;
};

Runtime.prototype.listSkills = async function (
  this: Runtime,
): Promise<CapabilityCatalogEntry[]> {
  if (this.usesApiTransport()) {
    return this.client().listSkills();
  }
  return this.listCapabilities({ kinds: ["skill"] });
};

Runtime.prototype.enableSkill = async function (
  this: Runtime,
  request: {
    skill_name: string;
    instruction: string;
    description?: string;
    tags?: string[];
    artifact_affinities?: string[];
    execution_owner?: "algenta_managed" | "client_managed";
  },
): Promise<CapabilityDiscoverResponse> {
  if (this.usesApiTransport()) {
    return this.client().enableSkill(request);
  }
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

Runtime.prototype.disableSkill = async function (
  this: Runtime,
  bindingId: string,
): Promise<void> {
  if (this.usesApiTransport()) {
    await this.client().disableSkill(bindingId);
    return;
  }
  await this.deleteCapabilityBinding(bindingId);
};

Runtime.prototype.listMcpProviders = async function (
  this: Runtime,
): Promise<CapabilityProviderResponse[]> {
  if (this.usesApiTransport()) {
    return this.client().listMcpProviders();
  }
  return (await this.listCapabilityProviders()).filter(
    provider => provider.provider_type === "mcp_provider",
  );
};
