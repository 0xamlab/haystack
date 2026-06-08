/** Auto-split sub-module of runtime.ts — internal capability-plane helper
 * methods (adapter normalization, manifest discovery, provider response
 * synthesis) used by the Runtime class.
 *
 * This module augments the {@link Runtime} class via TypeScript declaration
 * merging and prototype assignment. Importing this file (for its side
 * effects) is required so the prototype assignments execute and the
 * augmented methods are available on `Runtime` instances.
 */

import type {
  BindingScope,
  BindingStatus,
  CapabilityAdapter,
  CapabilityAdapterDescriptor,
  CapabilityBindingPreviewRequest,
  CapabilityBindingResponse,
  CapabilityCatalogEntry,
  CapabilityDiscoverResponse,
  CapabilityProviderResponse,
  ExecutionOwner,
} from "./types.js";
import { Runtime } from "./_runtime_class.js";
import { RuntimeValidationError } from "./_runtime_errors.js";
import { sha256Hex } from "./_runtime_helpers_a.js";

declare module "./_runtime_class.js" {
  interface Runtime {
    nowIso(): string;
    dedupeCapabilityStrings(values: Array<string | undefined | null>): string[];
    inferLocalProviderType(
      kind: CapabilityCatalogEntry["kind"],
    ): CapabilityProviderResponse["provider_type"];
    localBindingIdForDescriptor(descriptor: CapabilityAdapterDescriptor): string;
    localProfileIdForDescriptor(descriptor: CapabilityAdapterDescriptor): string;
    ensureLocalBindingFromAdapter(adapter: CapabilityAdapter): CapabilityBindingResponse;
    capabilityEntryFromAdapter(adapter: CapabilityAdapter): CapabilityCatalogEntry;
    registerCapabilityAdapter(adapter: CapabilityAdapter): void;
    localBindingsArray(): CapabilityBindingResponse[];
    localCapabilitiesArray(): CapabilityCatalogEntry[];
    localCapabilityEntryFromManifest(
      payload: Record<string, unknown>,
      binding: CapabilityBindingResponse,
    ): CapabilityCatalogEntry;
    discoverLocalBinding(
      binding:
        | CapabilityBindingResponse
        | (CapabilityBindingPreviewRequest & {
            binding_id?: string;
            binding_name?: string;
            status?: BindingStatus;
          }),
    ): CapabilityDiscoverResponse;
    localProviderResponses(): CapabilityProviderResponse[];
  }
}

Runtime.prototype.nowIso = function (this: Runtime): string {
  return new Date().toISOString();
};

Runtime.prototype.dedupeCapabilityStrings = function (
  this: Runtime,
  values: Array<string | undefined | null>,
): string[] {
  const ordered: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    if (typeof value !== "string") continue;
    const normalized = value.trim();
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    ordered.push(normalized);
  }
  return ordered;
};

Runtime.prototype.inferLocalProviderType = function (
  this: Runtime,
  kind: CapabilityCatalogEntry["kind"],
): CapabilityProviderResponse["provider_type"] {
  switch (kind) {
    case "dataset":
      return "data_connector";
    case "mcp_tool":
    case "mcp_resource":
    case "mcp_prompt":
      return "mcp_provider";
    case "skill":
      return "skill_pack";
    case "native_tool":
      return "native_tool_pack";
    case "runtime_library":
    default:
      return "runtime_library_pack";
  }
};

Runtime.prototype.localBindingIdForDescriptor = function (
  this: Runtime,
  descriptor: CapabilityAdapterDescriptor,
): string {
  if (descriptor.binding_id?.trim()) return descriptor.binding_id.trim();
  const seed = JSON.stringify({
    capability_id: descriptor.capability_id,
    provider_id: descriptor.provider_id,
    name: descriptor.name,
    kind: descriptor.kind,
  });
  return `local-binding-${sha256Hex(seed).slice(0, 24)}`;
};

Runtime.prototype.localProfileIdForDescriptor = function (
  this: Runtime,
  descriptor: CapabilityAdapterDescriptor,
): string {
  if (descriptor.profile_id?.trim()) return descriptor.profile_id.trim();
  const providerType = this.inferLocalProviderType(descriptor.kind);
  return `profile.${providerType}.local`;
};

Runtime.prototype.ensureLocalBindingFromAdapter = function (
  this: Runtime,
  adapter: CapabilityAdapter,
): CapabilityBindingResponse {
  const descriptor = adapter.descriptor;
  const bindingId = this.localBindingIdForDescriptor(descriptor);
  const existing = this.localCapabilityBindings.get(bindingId);
  if (existing) {
    return existing;
  }
  const now = this.nowIso();
  const binding: CapabilityBindingResponse = {
    binding_id: bindingId,
    provider_id: descriptor.provider_id,
    profile_id: this.localProfileIdForDescriptor(descriptor),
    binding_name: descriptor.binding_name ?? descriptor.name,
    scope: "workspace",
    scope_ref: "local",
    status: "ready",
    execution_owner: descriptor.execution_owner ?? "client_managed",
    config: null,
    customer_metadata: descriptor.customer_metadata ?? null,
    system_managed: false,
    last_tested_at: now,
    last_discovered_at: now,
    authorized_at: null,
    quarantine_reason: null,
    discovery_error_message: null,
    test_error_message: null,
    created_at: now,
    updated_at: now,
  };
  this.localCapabilityBindings.set(binding.binding_id, binding);
  return binding;
};

Runtime.prototype.capabilityEntryFromAdapter = function (
  this: Runtime,
  adapter: CapabilityAdapter,
): CapabilityCatalogEntry {
  const descriptor = adapter.descriptor;
  const binding = this.ensureLocalBindingFromAdapter(adapter);
  const manifestHash = sha256Hex(JSON.stringify(descriptor));
  return {
    capability_id: descriptor.capability_id,
    provider_id: descriptor.provider_id,
    profile_id: binding.profile_id,
    binding_id: binding.binding_id,
    kind: descriptor.kind,
    name: descriptor.name,
    description: descriptor.description ?? null,
    implementation_kind: descriptor.implementation_kind ?? "callable",
    execution_owner: descriptor.execution_owner ?? "client_managed",
    input_schema_ref:
      descriptor.input_schema_ref ?? `capability://${descriptor.capability_id}/input`,
    output_schema_ref:
      descriptor.output_schema_ref ?? `capability://${descriptor.capability_id}/output`,
    side_effect_class: descriptor.side_effect_class ?? "read_only",
    risk_level: descriptor.risk_level ?? "low",
    required_policy: descriptor.required_policy ?? "policy.capability.execute",
    replayability: descriptor.replayability ?? "deterministic",
    approval_required: descriptor.approval_required ?? false,
    trust_tier: descriptor.trust_tier ?? "customer_managed",
    manifest_hash: manifestHash,
    artifact_affinities: this.dedupeCapabilityStrings(descriptor.artifact_affinities ?? []),
    tags: this.dedupeCapabilityStrings(descriptor.tags ?? []),
    required_binding_ids: [binding.binding_id],
    selected_tool_name: descriptor.selected_tool_name ?? null,
    instruction_artifact_ref: descriptor.instruction_artifact_ref ?? null,
    binding_status: binding.status,
    discovered_at: binding.last_discovered_at ?? binding.created_at,
    customer_metadata: descriptor.customer_metadata ?? null,
    instruction_text: descriptor.instruction_text ?? null,
  };
};

Runtime.prototype.registerCapabilityAdapter = function (
  this: Runtime,
  adapter: CapabilityAdapter,
): void {
  const entry = this.capabilityEntryFromAdapter(adapter);
  this.capabilityAdapters.set(entry.capability_id, adapter);
  this.localCapabilityCatalog.set(entry.capability_id, entry);
};

Runtime.prototype.localBindingsArray = function (this: Runtime): CapabilityBindingResponse[] {
  return Array.from(this.localCapabilityBindings.values()).sort((left, right) =>
    left.binding_name.localeCompare(right.binding_name),
  );
};

Runtime.prototype.localCapabilitiesArray = function (this: Runtime): CapabilityCatalogEntry[] {
  return Array.from(this.localCapabilityCatalog.values()).sort((left, right) =>
    left.name.localeCompare(right.name),
  );
};

Runtime.prototype.localCapabilityEntryFromManifest = function (
  this: Runtime,
  payload: Record<string, unknown>,
  binding: CapabilityBindingResponse,
): CapabilityCatalogEntry {
  const capabilityId = String(payload.capability_id ?? "").trim();
  if (!capabilityId) {
    throw new RuntimeValidationError(
      "invalid_capability_manifest",
      "Local capability manifests require capability_id.",
    );
  }
  const kind = String(payload.kind ?? "").trim() as CapabilityCatalogEntry["kind"];
  if (!kind) {
    throw new RuntimeValidationError(
      "invalid_capability_manifest",
      "Local capability manifests require kind.",
    );
  }
  const manifestHash = sha256Hex(JSON.stringify(payload));
  const instructionText =
    typeof payload.instruction === "string" && payload.instruction.trim()
      ? payload.instruction
      : null;
  return {
    capability_id: capabilityId,
    provider_id: binding.provider_id,
    profile_id: binding.profile_id,
    binding_id: binding.binding_id,
    kind,
    name: String(payload.name ?? capabilityId),
    description: typeof payload.description === "string" ? payload.description : null,
    implementation_kind: String(
      payload.implementation_kind ?? "callable",
    ) as CapabilityCatalogEntry["implementation_kind"],
    execution_owner: String(
      payload.execution_owner ?? binding.execution_owner,
    ) as CapabilityCatalogEntry["execution_owner"],
    input_schema_ref: String(
      payload.input_schema_ref ?? `capability://${capabilityId}/input`,
    ),
    output_schema_ref: String(
      payload.output_schema_ref ?? `capability://${capabilityId}/output`,
    ),
    side_effect_class: String(
      payload.side_effect_class ?? "read_only",
    ) as CapabilityCatalogEntry["side_effect_class"],
    risk_level: String(payload.risk_level ?? "low") as CapabilityCatalogEntry["risk_level"],
    required_policy: String(payload.required_policy ?? "policy.capability.execute"),
    replayability: String(
      payload.replayability ?? "deterministic",
    ) as CapabilityCatalogEntry["replayability"],
    approval_required: Boolean(payload.approval_required ?? false),
    trust_tier: String(payload.trust_tier ?? "customer_managed"),
    manifest_hash: manifestHash,
    artifact_affinities: this.dedupeCapabilityStrings(
      Array.isArray(payload.artifact_affinities)
        ? (payload.artifact_affinities as Array<string | undefined | null>)
        : [],
    ),
    tags: this.dedupeCapabilityStrings(
      Array.isArray(payload.tags) ? (payload.tags as Array<string | undefined | null>) : [],
    ),
    required_binding_ids: [binding.binding_id],
    selected_tool_name:
      typeof payload.selected_tool_name === "string" ? payload.selected_tool_name : null,
    instruction_artifact_ref:
      typeof payload.instruction_artifact_ref === "string"
        ? payload.instruction_artifact_ref
        : instructionText
          ? `artifact://local-capability/${manifestHash}/${capabilityId}`
          : null,
    binding_status: binding.status,
    discovered_at: this.nowIso(),
    customer_metadata:
      payload.customer_metadata &&
      typeof payload.customer_metadata === "object" &&
      !Array.isArray(payload.customer_metadata)
        ? (payload.customer_metadata as Record<string, unknown>)
        : null,
    instruction_text: instructionText,
  };
};

Runtime.prototype.discoverLocalBinding = function (
  this: Runtime,
  binding:
    | CapabilityBindingResponse
    | (CapabilityBindingPreviewRequest & {
        binding_id?: string;
        binding_name?: string;
        status?: BindingStatus;
      }),
): CapabilityDiscoverResponse {
  const manifest =
    binding.config && typeof binding.config === "object" && !Array.isArray(binding.config)
      ? (binding.config as Record<string, unknown>).manifest
      : null;
  const bindingId =
    "binding_id" in binding && typeof binding.binding_id === "string"
      ? binding.binding_id
      : null;
  const bindingName =
    "binding_name" in binding && typeof binding.binding_name === "string"
      ? binding.binding_name
      : "preview";
  const bindingStatus =
    "status" in binding && binding.status ? binding.status : ("ready" as BindingStatus);
  const discoveredAt = this.nowIso();

  if (manifest && typeof manifest === "object" && !Array.isArray(manifest)) {
    const rawCapabilities = Array.isArray((manifest as { capabilities?: unknown }).capabilities)
      ? ((manifest as { capabilities: unknown[] }).capabilities as unknown[])
      : [];
    const normalizedBinding: CapabilityBindingResponse = {
      binding_id: bindingId ?? `preview-${sha256Hex(JSON.stringify(binding)).slice(0, 12)}`,
      provider_id: binding.provider_id,
      profile_id: binding.profile_id,
      binding_name: bindingName,
      scope: ("scope" in binding && binding.scope ? binding.scope : "workspace") as BindingScope,
      scope_ref:
        "scope_ref" in binding && typeof binding.scope_ref === "string"
          ? binding.scope_ref
          : "local",
      status: bindingStatus,
      execution_owner: (
        "execution_owner" in binding && binding.execution_owner
          ? binding.execution_owner
          : "client_managed"
      ) as ExecutionOwner,
      config: binding.config ?? null,
      customer_metadata: ("customer_metadata" in binding
        ? binding.customer_metadata ?? null
        : null) as Record<string, unknown> | null,
      system_managed: false,
      last_tested_at: discoveredAt,
      last_discovered_at: discoveredAt,
      authorized_at: null,
      quarantine_reason: null,
      discovery_error_message: null,
      test_error_message: null,
      created_at: discoveredAt,
      updated_at: discoveredAt,
    };
    const capabilities = rawCapabilities
      .filter(item => item && typeof item === "object" && !Array.isArray(item))
      .map(item =>
        this.localCapabilityEntryFromManifest(item as Record<string, unknown>, normalizedBinding),
      );
    const manifestHash = sha256Hex(JSON.stringify(rawCapabilities));
    return {
      binding_id: bindingId,
      provider_id: binding.provider_id,
      profile_id: binding.profile_id,
      snapshot_id: null,
      binding_status: capabilities.length > 0 ? "ready" : "degraded",
      manifest_hash: manifestHash,
      capability_count: capabilities.length,
      discovered_at: discoveredAt,
      message: `Discovered ${capabilities.length} local manifest-backed capabilities.`,
      capabilities,
    };
  }

  const capabilities = this.localCapabilitiesArray().filter(
    entry =>
      entry.binding_id === bindingId ||
      (!bindingId &&
        entry.provider_id === binding.provider_id &&
        entry.profile_id === binding.profile_id),
  );
  const manifestHash = sha256Hex(
    JSON.stringify(capabilities.map(item => item.capability_id)),
  );
  return {
    binding_id: bindingId,
    provider_id: binding.provider_id,
    profile_id: binding.profile_id,
    snapshot_id: null,
    binding_status: capabilities.length > 0 ? "ready" : "degraded",
    manifest_hash: manifestHash,
    capability_count: capabilities.length,
    discovered_at: discoveredAt,
    message: `Discovered ${capabilities.length} local adapter-backed capabilities.`,
    capabilities,
  };
};

Runtime.prototype.localProviderResponses = function (
  this: Runtime,
): CapabilityProviderResponse[] {
  const providers = new Map<string, CapabilityProviderResponse>();
  for (const binding of this.localBindingsArray()) {
    const sampleCapability = this.localCapabilitiesArray().find(
      entry => entry.binding_id === binding.binding_id,
    );
    const providerType = sampleCapability
      ? this.inferLocalProviderType(sampleCapability.kind)
      : "native_tool_pack";
    const existing = providers.get(binding.provider_id);
    const profile = {
      profile_id: binding.profile_id,
      provider_id: binding.provider_id,
      name: binding.binding_name,
      description: null,
      auth_kind: "none",
      default_execution_owner: binding.execution_owner,
      binding_scope_default: binding.scope,
      supported_binding_scopes: [binding.scope],
      profile_metadata: null,
    };
    if (existing) {
      if (!existing.profiles.some(item => item.profile_id === profile.profile_id)) {
        existing.profiles.push(profile);
      }
      continue;
    }
    providers.set(binding.provider_id, {
      provider_id: binding.provider_id,
      provider_type: providerType,
      name: binding.provider_id,
      description: "Local capability-plane provider",
      docs_url: null,
      auth_schema: { type: "none", fields: [] },
      certification_summary: { owner: "customer", certified: false },
      policy_summary: { route_authority: "capability_plane", execution_owner: "client_managed" },
      supported_execution_owners: [binding.execution_owner],
      install_metadata: { discovery_mode: "local_adapter" },
      customer_metadata: null,
      active: true,
      profiles: [profile],
    });
  }
  return Array.from(providers.values()).sort((left, right) =>
    left.provider_id.localeCompare(right.provider_id),
  );
};
