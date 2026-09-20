// SPDX-License-Identifier: Apache-2.0
/**
 * Local-mode capability plane. Bindings, discovery, authorization, routing and
 * execution all run in-process against the adapter registry, so every branch is
 * reachable without a network. capability_plane.test.ts covers the adapter happy
 * path; this file covers the rest of the local implementation in
 * _runtime_class_methods_capability.ts and _runtime_class_capability_helpers.ts.
 */
import { describe, expect, it } from "vitest";

import { Runtime, RuntimeValidationError } from "./runtime.js";
import type { CapabilityAdapter, CapabilityAdapterDescriptor } from "./types.js";

const ROUTER_ID = "cap.native.incident_router";
const EXPORTER_ID = "cap.native.billing_exporter";

function makeAdapter(
  descriptor: Partial<CapabilityAdapterDescriptor> = {},
  execute: CapabilityAdapter["execute"] = async request => ({
    routed_to: "incident-command",
    input: request.input ?? null,
  }),
): CapabilityAdapter {
  return {
    descriptor: {
      capability_id: ROUTER_ID,
      provider_id: "provider.native_tool_pack.customer",
      name: "Incident Router",
      kind: "native_tool",
      // Duplicates and padding are deliberate: the catalog entry must dedupe them.
      tags: ["incident", " route ", "incident", ""],
      artifact_affinities: ["incident"],
      ...descriptor,
    },
    execute,
  };
}

function exporterAdapter(): CapabilityAdapter {
  return makeAdapter({
    capability_id: EXPORTER_ID,
    provider_id: "provider.native_tool_pack.finance",
    name: "Billing Exporter",
    description: "Exports invoices",
    tags: ["billing"],
    artifact_affinities: ["invoice"],
  });
}

/** A manifest with one instruction-only skill and one callable tool. */
const MANIFEST_CONFIG = {
  manifest: {
    capabilities: [
      {
        capability_id: "cap.skill.triage",
        name: "Triage",
        kind: "skill",
        implementation_kind: "instruction_only",
        instruction: "Triage the incident by severity.",
        tags: ["triage", "incident"],
        artifact_affinities: ["incident"],
      },
      {
        capability_id: "cap.tool.pager",
        name: "Pager",
        kind: "native_tool",
        description: "Pages the on-call engineer",
      },
    ],
  },
};

async function createManifestBinding(runtime: Runtime) {
  return runtime.createCapabilityBinding({
    provider_id: "provider.manifest.customer",
    profile_id: "profile.manifest.user",
    binding_name: "Manifest binding",
    config: MANIFEST_CONFIG,
  });
}

async function expectRuntimeValidationError(
  promise: Promise<unknown>,
  code: string,
  messageFragment: string,
): Promise<void> {
  await expect(promise).rejects.toBeInstanceOf(RuntimeValidationError);
  await expect(promise).rejects.toMatchObject({
    code,
    message: expect.stringContaining(messageFragment),
  });
}

describe("Runtime local capability bindings", () => {
  it("creates a binding with defaults and reads it back", async () => {
    const runtime = new Runtime({ mode: "local" });
    const binding = await runtime.createCapabilityBinding({
      provider_id: "provider.mcp.generic",
      profile_id: "profile.mcp.default",
      binding_name: "Generic MCP",
    });

    expect(binding.binding_id).toMatch(/^local-binding-[0-9a-f]{24}$/);
    expect(binding).toMatchObject({
      provider_id: "provider.mcp.generic",
      profile_id: "profile.mcp.default",
      binding_name: "Generic MCP",
      scope: "workspace",
      scope_ref: "local",
      status: "unconfigured",
      execution_owner: "client_managed",
      config: null,
      customer_metadata: null,
      system_managed: false,
      last_tested_at: null,
      last_discovered_at: null,
      authorized_at: null,
      quarantine_reason: null,
      discovery_error_message: null,
      test_error_message: null,
    });
    expect(binding.created_at).toBe(binding.updated_at);
    expect(await runtime.getCapabilityBinding(binding.binding_id)).toBe(binding);
  });

  it("honours explicit scope, owner, config and metadata on create", async () => {
    const runtime = new Runtime({ mode: "local" });
    const binding = await runtime.createCapabilityBinding({
      provider_id: "provider.mcp.generic",
      profile_id: "profile.mcp.default",
      binding_name: "Org MCP",
      scope: "organization",
      scope_ref: "org-1",
      execution_owner: "algenta_managed",
      config: { server_url: "https://mcp.example.test" },
      customer_metadata: { team: "platform" },
    });

    expect(binding).toMatchObject({
      scope: "organization",
      scope_ref: "org-1",
      execution_owner: "algenta_managed",
      config: { server_url: "https://mcp.example.test" },
      customer_metadata: { team: "platform" },
    });
  });

  it("rejects lookups of unknown bindings", async () => {
    const runtime = new Runtime({ mode: "local" });
    await expectRuntimeValidationError(
      runtime.getCapabilityBinding("missing"),
      "binding_not_found",
      "'missing' was not found in local mode",
    );
    await expectRuntimeValidationError(
      runtime.updateCapabilityBinding("missing", { binding_name: "x" }),
      "binding_not_found",
      "'missing'",
    );
  });

  it("lists bindings sorted by name and filters by provider and scope", async () => {
    const runtime = new Runtime({ mode: "local", capabilityAdapters: [makeAdapter()] });
    await runtime.createCapabilityBinding({
      provider_id: "provider.mcp.generic",
      profile_id: "profile.mcp.default",
      binding_name: "Zed MCP",
      scope: "user",
    });
    await runtime.createCapabilityBinding({
      provider_id: "provider.mcp.generic",
      profile_id: "profile.mcp.default",
      binding_name: "Alpha MCP",
    });

    const all = await runtime.listCapabilityBindings();
    expect(all.map(binding => binding.binding_name)).toEqual([
      "Alpha MCP",
      "Incident Router",
      "Zed MCP",
    ]);
    expect(
      (await runtime.listCapabilityBindings({ providerId: "provider.mcp.generic" })).map(
        binding => binding.binding_name,
      ),
    ).toEqual(["Alpha MCP", "Zed MCP"]);
    expect(
      (await runtime.listCapabilityBindings({ scope: "user" })).map(binding => binding.binding_name),
    ).toEqual(["Zed MCP"]);
    expect(
      await runtime.listCapabilityBindings({ providerId: "provider.mcp.generic", scope: "workspace" }),
    ).toHaveLength(1);
  });

  it("updates only the supplied fields and stamps updated_at", async () => {
    const runtime = new Runtime({ mode: "local" });
    const binding = await runtime.createCapabilityBinding({
      provider_id: "provider.mcp.generic",
      profile_id: "profile.mcp.default",
      binding_name: "Generic MCP",
      config: { server_url: "https://old.example.test" },
    });

    const renamed = await runtime.updateCapabilityBinding(binding.binding_id, {
      binding_name: "Renamed MCP",
      status: "ready",
    });
    expect(renamed).toMatchObject({
      binding_name: "Renamed MCP",
      status: "ready",
      scope: "workspace",
      scope_ref: "local",
      execution_owner: "client_managed",
      config: { server_url: "https://old.example.test" },
      customer_metadata: null,
    });

    const reconfigured = await runtime.updateCapabilityBinding(binding.binding_id, {
      scope: "organization",
      scope_ref: "org-9",
      execution_owner: "algenta_managed",
      config: { server_url: "https://new.example.test" },
      customer_metadata: { owner: "ops" },
    });
    expect(reconfigured).toMatchObject({
      binding_name: "Renamed MCP",
      scope: "organization",
      scope_ref: "org-9",
      execution_owner: "algenta_managed",
      config: { server_url: "https://new.example.test" },
      customer_metadata: { owner: "ops" },
    });
    expect(await runtime.getCapabilityBinding(binding.binding_id)).toBe(reconfigured);
  });

  it("deletes a binding together with the capabilities it discovered", async () => {
    const runtime = new Runtime({ mode: "local", capabilityAdapters: [makeAdapter()] });
    const binding = await createManifestBinding(runtime);
    await runtime.discoverCapabilityBinding(binding.binding_id);
    expect(await runtime.listCapabilities()).toHaveLength(3);

    await runtime.deleteCapabilityBinding(binding.binding_id);

    expect((await runtime.listCapabilities()).map(entry => entry.capability_id)).toEqual([ROUTER_ID]);
    await expectRuntimeValidationError(
      runtime.getCapabilityBinding(binding.binding_id),
      "binding_not_found",
      "not found",
    );
    // Deleting an unknown binding is a no-op rather than an error.
    await expect(runtime.deleteCapabilityBinding("missing")).resolves.toBeUndefined();
  });
});

describe("Runtime local binding test and discovery", () => {
  it("previews a manifest-backed binding as ready with its capability count", async () => {
    const runtime = new Runtime({ mode: "local" });
    const result = await runtime.previewTestCapabilityBinding({
      provider_id: "provider.manifest.customer",
      profile_id: "profile.manifest.user",
      config: MANIFEST_CONFIG,
    });
    expect(result).toEqual({
      success: true,
      binding_status: "ready",
      message: "Local manifest-backed capability binding is valid.",
      latency_ms: null,
      details: { capability_count: 2 },
    });
  });

  it("previews an adapter-backed binding by provider and profile match", async () => {
    const runtime = new Runtime({ mode: "local", capabilityAdapters: [makeAdapter()] });
    const [adapterBinding] = await runtime.listCapabilityBindings();
    const matched = await runtime.previewTestCapabilityBinding({
      provider_id: adapterBinding.provider_id,
      profile_id: adapterBinding.profile_id,
    });
    expect(matched).toMatchObject({
      success: true,
      binding_status: "ready",
      details: { adapter_backed: true },
    });

    // A manifest without a capabilities array is not manifest-backed either.
    const unmatched = await runtime.previewTestCapabilityBinding({
      provider_id: "provider.unknown",
      profile_id: "profile.unknown",
      config: { manifest: { capabilities: "not-a-list" } },
    });
    expect(unmatched).toEqual({
      success: false,
      binding_status: "unconfigured",
      message:
        "Local capability binding requires config.manifest.capabilities or a matching registered adapter.",
      latency_ms: null,
      details: { required_field: "config.manifest.capabilities" },
    });
  });

  it("testCapabilityBinding records the outcome on the stored binding", async () => {
    const runtime = new Runtime({ mode: "local" });
    const ready = await createManifestBinding(runtime);
    const readyResult = await runtime.testCapabilityBinding(ready.binding_id);
    expect(readyResult.success).toBe(true);
    const storedReady = await runtime.getCapabilityBinding(ready.binding_id);
    expect(storedReady.status).toBe("ready");
    expect(storedReady.last_tested_at).toEqual(expect.any(String));
    expect(storedReady.test_error_message).toBeNull();

    const bare = await runtime.createCapabilityBinding({
      provider_id: "provider.unknown",
      profile_id: "profile.unknown",
      binding_name: "Bare",
    });
    const bareResult = await runtime.testCapabilityBinding(bare.binding_id);
    expect(bareResult.success).toBe(false);
    const storedBare = await runtime.getCapabilityBinding(bare.binding_id);
    expect(storedBare.status).toBe("unconfigured");
    expect(storedBare.test_error_message).toBe(bareResult.message);
  });

  it("previewDiscover synthesizes catalog entries from a manifest without persisting them", async () => {
    const runtime = new Runtime({ mode: "local" });
    const preview = await runtime.previewDiscoverCapabilityBinding({
      provider_id: "provider.manifest.customer",
      profile_id: "profile.manifest.user",
      scope: "user",
      scope_ref: "user-1",
      execution_owner: "algenta_managed",
      config: MANIFEST_CONFIG,
      customer_metadata: { team: "sre" },
    });

    expect(preview).toMatchObject({
      binding_id: null,
      provider_id: "provider.manifest.customer",
      profile_id: "profile.manifest.user",
      snapshot_id: null,
      binding_status: "ready",
      capability_count: 2,
      message: "Discovered 2 local manifest-backed capabilities.",
    });
    expect(preview.manifest_hash).toMatch(/^[0-9a-f]{64}$/);
    const [skill, tool] = preview.capabilities;
    expect(skill).toMatchObject({
      capability_id: "cap.skill.triage",
      kind: "skill",
      implementation_kind: "instruction_only",
      execution_owner: "algenta_managed",
      instruction_text: "Triage the incident by severity.",
      tags: ["triage", "incident"],
      artifact_affinities: ["incident"],
      description: null,
      selected_tool_name: null,
      customer_metadata: null,
      binding_status: "ready",
    });
    expect(skill.binding_id).toMatch(/^preview-[0-9a-f]{12}$/);
    expect(skill.instruction_artifact_ref).toBe(
      `artifact://local-capability/${skill.manifest_hash}/cap.skill.triage`,
    );
    expect(tool).toMatchObject({
      capability_id: "cap.tool.pager",
      implementation_kind: "callable",
      description: "Pages the on-call engineer",
      instruction_text: null,
      instruction_artifact_ref: null,
      input_schema_ref: "capability://cap.tool.pager/input",
      output_schema_ref: "capability://cap.tool.pager/output",
      required_policy: "policy.capability.execute",
      trust_tier: "customer_managed",
      approval_required: false,
    });
    // Preview never touches the catalog.
    expect(await runtime.listCapabilities()).toEqual([]);
  });

  it("previewDiscover honours explicit manifest fields and skips non-object entries", async () => {
    const runtime = new Runtime({ mode: "local" });
    const preview = await runtime.previewDiscoverCapabilityBinding({
      provider_id: "provider.manifest.customer",
      profile_id: "profile.manifest.user",
      config: {
        manifest: {
          capabilities: [
            "not-an-object",
            null,
            {
              capability_id: " cap.tool.explicit ",
              name: "Explicit",
              kind: "mcp_tool",
              implementation_kind: "callable",
              execution_owner: "client_managed",
              input_schema_ref: "schema://in",
              output_schema_ref: "schema://out",
              side_effect_class: "write_scoped",
              risk_level: "high",
              required_policy: "policy.custom",
              replayability: "artifact_backed",
              approval_required: true,
              trust_tier: "algenta_certified",
              selected_tool_name: "explicit_tool",
              instruction_artifact_ref: "artifact://explicit",
              instruction: "   ",
              customer_metadata: { owner: "ops" },
              tags: "not-a-list",
            },
          ],
        },
      },
    });

    expect(preview.capability_count).toBe(1);
    expect(preview.capabilities[0]).toMatchObject({
      capability_id: "cap.tool.explicit",
      kind: "mcp_tool",
      input_schema_ref: "schema://in",
      output_schema_ref: "schema://out",
      side_effect_class: "write_scoped",
      risk_level: "high",
      required_policy: "policy.custom",
      replayability: "artifact_backed",
      approval_required: true,
      trust_tier: "algenta_certified",
      selected_tool_name: "explicit_tool",
      instruction_artifact_ref: "artifact://explicit",
      // Whitespace-only instructions are treated as absent.
      instruction_text: null,
      customer_metadata: { owner: "ops" },
      tags: [],
    });
  });

  it("previewDiscover falls back to adapter-backed discovery when no manifest is configured", async () => {
    const runtime = new Runtime({ mode: "local", capabilityAdapters: [makeAdapter()] });
    const [adapterBinding] = await runtime.listCapabilityBindings();

    const matched = await runtime.previewDiscoverCapabilityBinding({
      provider_id: adapterBinding.provider_id,
      profile_id: adapterBinding.profile_id,
    });
    expect(matched).toMatchObject({
      binding_id: null,
      binding_status: "ready",
      capability_count: 1,
      message: "Discovered 1 local adapter-backed capabilities.",
    });
    expect(matched.capabilities[0].capability_id).toBe(ROUTER_ID);

    const unmatched = await runtime.previewDiscoverCapabilityBinding({
      provider_id: "provider.unknown",
      profile_id: "profile.unknown",
      config: { manifest: [] },
    });
    expect(unmatched).toMatchObject({
      binding_status: "degraded",
      capability_count: 0,
      capabilities: [],
    });
  });

  it("discoverCapabilityBinding persists entries, replaces stale ones and records errors", async () => {
    const runtime = new Runtime({ mode: "local" });
    const binding = await createManifestBinding(runtime);

    const first = await runtime.discoverCapabilityBinding(binding.binding_id);
    expect(first.binding_id).toBe(binding.binding_id);
    expect(first.capabilities.map(entry => entry.capability_id)).toEqual([
      "cap.skill.triage",
      "cap.tool.pager",
    ]);
    const afterFirst = await runtime.getCapabilityBinding(binding.binding_id);
    expect(afterFirst).toMatchObject({
      status: "ready",
      last_discovered_at: first.discovered_at,
      discovery_error_message: null,
    });
    expect((await runtime.listCapabilities()).map(entry => entry.capability_id)).toEqual([
      "cap.tool.pager",
      "cap.skill.triage",
    ]);

    // Shrinking the manifest drops the capabilities that disappeared.
    await runtime.updateCapabilityBinding(binding.binding_id, {
      config: { manifest: { capabilities: [MANIFEST_CONFIG.manifest.capabilities[1]] } },
    });
    const second = await runtime.discoverCapabilityBinding(binding.binding_id);
    expect(second.capability_count).toBe(1);
    expect((await runtime.listCapabilities()).map(entry => entry.capability_id)).toEqual([
      "cap.tool.pager",
    ]);

    // An empty manifest degrades the binding and surfaces the discovery message.
    await runtime.updateCapabilityBinding(binding.binding_id, {
      config: { manifest: { capabilities: [] } },
    });
    const third = await runtime.discoverCapabilityBinding(binding.binding_id);
    expect(third.binding_status).toBe("degraded");
    expect(await runtime.listCapabilities()).toEqual([]);
    expect(await runtime.getCapabilityBinding(binding.binding_id)).toMatchObject({
      status: "degraded",
      discovery_error_message: "Discovered 0 local manifest-backed capabilities.",
    });
  });

  it("previewDiscover degrades a manifest object that lists no capabilities", async () => {
    const runtime = new Runtime({ mode: "local" });
    const preview = await runtime.previewDiscoverCapabilityBinding({
      provider_id: "p",
      profile_id: "q",
      config: { manifest: {} },
    });
    expect(preview).toMatchObject({
      binding_status: "degraded",
      capability_count: 0,
      capabilities: [],
      message: "Discovered 0 local manifest-backed capabilities.",
    });
  });

  it("rejects manifest entries without capability_id or kind", async () => {
    const runtime = new Runtime({ mode: "local" });
    await expectRuntimeValidationError(
      runtime.previewDiscoverCapabilityBinding({
        provider_id: "p",
        profile_id: "q",
        config: { manifest: { capabilities: [{ capability_id: "cap.x", name: "No kind" }] } },
      }),
      "invalid_capability_manifest",
      "require kind",
    );
    await expectRuntimeValidationError(
      runtime.previewDiscoverCapabilityBinding({
        provider_id: "p",
        profile_id: "q",
        config: { manifest: { capabilities: [{ name: "No id", kind: "skill" }] } },
      }),
      "invalid_capability_manifest",
      "require capability_id",
    );
    await expectRuntimeValidationError(
      runtime.previewDiscoverCapabilityBinding({
        provider_id: "p",
        profile_id: "q",
        config: { manifest: { capabilities: [{ capability_id: "cap.x", kind: "  " }] } },
      }),
      "invalid_capability_manifest",
      "require kind",
    );
  });
});

describe("Runtime local capability authorization", () => {
  it("refuses to start authorization when the binding exposes no authorization_url", async () => {
    const runtime = new Runtime({ mode: "local" });
    const binding = await createManifestBinding(runtime);
    await expectRuntimeValidationError(
      runtime.startCapabilityAuthorization(binding.binding_id, {}),
      "authorization_not_supported",
      "does not expose authorization_url",
    );
  });

  it("runs the start/complete session flow and rejects unknown or mismatched sessions", async () => {
    const runtime = new Runtime({ mode: "local" });
    const binding = await runtime.createCapabilityBinding({
      provider_id: "provider.mcp.generic",
      profile_id: "profile.mcp.oauth",
      binding_name: "OAuth MCP",
      config: { authorization_url: "https://auth.example.test/start" },
    });
    const other = await runtime.createCapabilityBinding({
      provider_id: "provider.mcp.generic",
      profile_id: "profile.mcp.oauth",
      binding_name: "Other MCP",
      config: { authorization_url: "https://auth.example.test/other" },
    });

    const started = await runtime.startCapabilityAuthorization(binding.binding_id, {});
    expect(started).toMatchObject({
      binding_id: binding.binding_id,
      provider_id: "provider.mcp.generic",
      authorize_url: "https://auth.example.test/start",
      requested_scopes: [],
    });
    expect(started.session_id).toMatch(/^local-auth-[0-9a-f]{24}$/);
    expect(Date.parse(started.expires_at)).toBeGreaterThan(Date.now());
    expect((await runtime.getCapabilityBinding(binding.binding_id)).status).toBe("authorizing");

    const scoped = await runtime.startCapabilityAuthorization(other.binding_id, {
      requested_scopes: ["read", "write"],
    });
    expect(scoped.requested_scopes).toEqual(["read", "write"]);

    await expectRuntimeValidationError(
      runtime.completeCapabilityAuthorization(binding.binding_id, { session_id: "nope" }),
      "authorization_session_not_found",
      "session was not found",
    );
    // A valid session for a different binding is not accepted either.
    await expectRuntimeValidationError(
      runtime.completeCapabilityAuthorization(binding.binding_id, {
        session_id: scoped.session_id,
      }),
      "authorization_session_not_found",
      "session was not found",
    );

    const completed = await runtime.completeCapabilityAuthorization(binding.binding_id, {
      session_id: started.session_id,
    });
    expect(completed).toEqual({
      session_id: started.session_id,
      binding_id: binding.binding_id,
      provider_id: "provider.mcp.generic",
      status: "completed",
      authorized_at: expect.any(String),
    });
    expect(await runtime.getCapabilityBinding(binding.binding_id)).toMatchObject({
      status: "ready",
      authorized_at: completed.authorized_at,
      updated_at: completed.authorized_at,
    });
  });
});

describe("Runtime local providers and catalog lookups", () => {
  it("synthesizes providers from bindings, merging profiles per provider", async () => {
    const runtime = new Runtime({
      mode: "local",
      capabilityAdapters: [
        makeAdapter(),
        makeAdapter({
          capability_id: "cap.data.orders",
          provider_id: "provider.data.customer",
          name: "Orders dataset",
          kind: "dataset",
          profile_id: "profile.data.primary",
        }),
      ],
    });
    // Two more bindings on the data provider: one new profile, one duplicate profile.
    await runtime.createCapabilityBinding({
      provider_id: "provider.data.customer",
      profile_id: "profile.data.secondary",
      binding_name: "Secondary data",
      execution_owner: "algenta_managed",
    });
    await runtime.createCapabilityBinding({
      provider_id: "provider.data.customer",
      profile_id: "profile.data.primary",
      binding_name: "Primary again",
    });

    const providers = await runtime.listCapabilityProviders();
    expect(providers.map(provider => provider.provider_id)).toEqual([
      "provider.data.customer",
      "provider.native_tool_pack.customer",
    ]);
    const [data, native] = providers;
    expect(data.provider_type).toBe("data_connector");
    expect(data.profiles.map(profile => profile.profile_id)).toEqual([
      "profile.data.primary",
      "profile.data.secondary",
    ]);
    expect(data.profiles[1]).toMatchObject({
      name: "Secondary data",
      auth_kind: "none",
      default_execution_owner: "algenta_managed",
      binding_scope_default: "workspace",
      supported_binding_scopes: ["workspace"],
    });
    expect(native).toMatchObject({
      provider_type: "native_tool_pack",
      description: "Local capability-plane provider",
      auth_schema: { type: "none", fields: [] },
      supported_execution_owners: ["client_managed"],
      install_metadata: { discovery_mode: "local_adapter" },
      active: true,
    });

    // Providers are synthesized on every call, so compare by value.
    expect(await runtime.getCapabilityProvider("provider.data.customer")).toEqual(data);
    await expectRuntimeValidationError(
      runtime.getCapabilityProvider("provider.missing"),
      "provider_not_found",
      "'provider.missing' was not found in local mode",
    );
  });

  it("infers a provider type for every capability kind and defaults bindings without capabilities", async () => {
    const runtime = new Runtime({ mode: "local" });
    expect(runtime.inferLocalProviderType("dataset")).toBe("data_connector");
    expect(runtime.inferLocalProviderType("mcp_tool")).toBe("mcp_provider");
    expect(runtime.inferLocalProviderType("mcp_resource")).toBe("mcp_provider");
    expect(runtime.inferLocalProviderType("mcp_prompt")).toBe("mcp_provider");
    expect(runtime.inferLocalProviderType("skill")).toBe("skill_pack");
    expect(runtime.inferLocalProviderType("native_tool")).toBe("native_tool_pack");
    expect(runtime.inferLocalProviderType("runtime_library")).toBe("runtime_library_pack");

    await runtime.createCapabilityBinding({
      provider_id: "provider.bare",
      profile_id: "profile.bare",
      binding_name: "Bare",
    });
    expect((await runtime.listCapabilityProviders())[0].provider_type).toBe("native_tool_pack");
    expect(await runtime.listMcpProviders()).toEqual([]);
  });

  it("uses explicit binding_id and profile_id from an adapter descriptor", () => {
    const runtime = new Runtime({
      mode: "local",
      capabilityAdapters: [
        makeAdapter({
          binding_id: " binding-explicit ",
          profile_id: " profile.explicit ",
          binding_name: "Explicit binding",
          execution_owner: "algenta_managed",
          customer_metadata: { team: "core" },
          instruction_text: "Use with care.",
          selected_tool_name: "router",
          instruction_artifact_ref: "artifact://router",
        }),
      ],
    });

    const [entry] = runtime.localCapabilitiesArray();
    expect(entry).toMatchObject({
      binding_id: "binding-explicit",
      profile_id: "profile.explicit",
      execution_owner: "algenta_managed",
      customer_metadata: { team: "core" },
      instruction_text: "Use with care.",
      selected_tool_name: "router",
      instruction_artifact_ref: "artifact://router",
      tags: ["incident", "route"],
      required_binding_ids: ["binding-explicit"],
    });
    expect(runtime.localCapabilityBindings.get("binding-explicit")).toMatchObject({
      binding_name: "Explicit binding",
      execution_owner: "algenta_managed",
      customer_metadata: { team: "core" },
    });
    expect(runtime.dedupeCapabilityStrings([" a ", "a", null, undefined, "", "b"])).toEqual([
      "a",
      "b",
    ]);
  });

  it("adapters that name the same binding share one binding record", () => {
    const runtime = new Runtime({
      mode: "local",
      capabilityAdapters: [
        makeAdapter({ binding_id: "shared-binding" }),
        makeAdapter({
          binding_id: "shared-binding",
          capability_id: EXPORTER_ID,
          name: "Billing Exporter",
          binding_name: "ignored: the first adapter created the binding",
        }),
      ],
    });
    expect(runtime.localBindingsArray()).toHaveLength(1);
    expect(runtime.localBindingsArray()[0].binding_name).toBe("Incident Router");
    expect(runtime.localCapabilitiesArray().map(entry => entry.binding_id)).toEqual([
      "shared-binding",
      "shared-binding",
    ]);
  });

  it("filters the catalog by kinds, providers and bindings", async () => {
    const runtime = new Runtime({
      mode: "local",
      capabilityAdapters: [makeAdapter(), exporterAdapter()],
    });
    const binding = await createManifestBinding(runtime);
    await runtime.discoverCapabilityBinding(binding.binding_id);

    expect((await runtime.listCapabilities()).map(entry => entry.name)).toEqual([
      "Billing Exporter",
      "Incident Router",
      "Pager",
      "Triage",
    ]);
    expect(
      (await runtime.listCapabilities({ kinds: ["skill"] })).map(entry => entry.capability_id),
    ).toEqual(["cap.skill.triage"]);
    expect(
      (
        await runtime.listCapabilities({ providerIds: ["provider.native_tool_pack.finance"] })
      ).map(entry => entry.capability_id),
    ).toEqual([EXPORTER_ID]);
    expect(
      (await runtime.listCapabilities({ bindingIds: [binding.binding_id] })).map(
        entry => entry.capability_id,
      ),
    ).toEqual(["cap.tool.pager", "cap.skill.triage"]);
    // Empty filter lists mean "no filter", not "match nothing".
    expect(await runtime.listCapabilities({ kinds: [], providerIds: [], bindingIds: [] })).toHaveLength(4);
    expect(await runtime.listSkills()).toHaveLength(1);
  });

  it("getCapability redacts the instruction unless asked for it", async () => {
    const runtime = new Runtime({ mode: "local" });
    const binding = await createManifestBinding(runtime);
    await runtime.discoverCapabilityBinding(binding.binding_id);

    const redacted = await runtime.getCapability("cap.skill.triage");
    expect(redacted.instruction_text).toBeNull();
    expect(redacted.instruction_artifact_ref).toMatch(/^artifact:\/\/local-capability\//);
    const full = await runtime.getCapability("cap.skill.triage", { includeInstruction: true });
    expect(full.instruction_text).toBe("Triage the incident by severity.");

    await expectRuntimeValidationError(
      runtime.getCapability("cap.missing"),
      "capability_not_found",
      "'cap.missing' was not found in local mode",
    );
  });
});

describe("Runtime local capability routing", () => {
  it("ranks by token overlap, tag and affinity bonuses and reports fallbacks", async () => {
    const runtime = new Runtime({
      mode: "local",
      capabilityAdapters: [makeAdapter(), exporterAdapter()],
    });

    const plan = await runtime.routeCapabilities({
      objective: "Route the active incident",
      artifact_affinities: ["incident"],
      tags: ["route"],
    });

    // overlap {incident, route} = 20, ready = 15, tag = 8, affinity = 8 -> 51 / 100
    expect(plan).toMatchObject({
      selected_capability_id: ROUTER_ID,
      selected_provider_id: "provider.native_tool_pack.customer",
      kind: "native_tool",
      execution_owner: "client_managed",
      requires_approval: false,
      confidence: 0.51,
      reason: "token overlap: incident, route",
      policy_snapshot_id: "capability-plane-policy-v1",
      selected_tool_name: null,
      instruction_artifact_ref: null,
    });
    expect(plan.fallbacks).toEqual([
      {
        capability_id: EXPORTER_ID,
        provider_id: "provider.native_tool_pack.finance",
        binding_id: expect.stringMatching(/^local-binding-/),
        kind: "native_tool",
        execution_owner: "client_managed",
        confidence: 0.15,
        reason: "default local catalog ranking",
        selected_tool_name: null,
        instruction_artifact_ref: null,
      },
    ]);
  });

  it("breaks confidence ties by name and honours max_fallbacks", async () => {
    const runtime = new Runtime({
      mode: "local",
      capabilityAdapters: [makeAdapter(), exporterAdapter()],
    });

    const plan = await runtime.routeCapabilities({ objective: "nothing matches here" });
    expect(plan.selected_capability_id).toBe(EXPORTER_ID);
    expect(plan.reason).toBe("default local catalog ranking");
    expect(plan.fallbacks.map(item => item.capability_id)).toEqual([ROUTER_ID]);

    const noFallbacks = await runtime.routeCapabilities({
      objective: "nothing matches here",
      max_fallbacks: 0,
    });
    expect(noFallbacks.fallbacks).toEqual([]);
  });

  it("excludes quarantined bindings and unrequested execution owners", async () => {
    const runtime = new Runtime({
      mode: "local",
      capabilityAdapters: [
        makeAdapter(),
        makeAdapter({
          capability_id: EXPORTER_ID,
          provider_id: "provider.native_tool_pack.finance",
          name: "Billing Exporter",
          execution_owner: "algenta_managed",
          tags: ["incident"],
        }),
      ],
    });

    const managedOnly = await runtime.routeCapabilities({
      objective: "incident",
      execution_owners: ["algenta_managed"],
    });
    expect(managedOnly.selected_capability_id).toBe(EXPORTER_ID);

    const router = runtime.localCapabilityCatalog.get(ROUTER_ID);
    if (!router) throw new Error("router entry must exist");
    router.binding_status = "quarantined";
    const plan = await runtime.routeCapabilities({ objective: "incident" });
    expect(plan.selected_capability_id).toBe(EXPORTER_ID);
    expect(plan.fallbacks).toEqual([]);

    await expectRuntimeValidationError(
      runtime.routeCapabilities({ objective: "incident", kinds: ["dataset"] }),
      "capability_route_not_found",
      "No capabilities matched",
    );
  });
});

describe("Runtime local capability execution", () => {
  it("rejects binding mismatches, non-client owners and missing adapters", async () => {
    const runtime = new Runtime({
      mode: "local",
      capabilityAdapters: [
        makeAdapter(),
        makeAdapter({
          capability_id: EXPORTER_ID,
          provider_id: "provider.native_tool_pack.finance",
          name: "Billing Exporter",
          execution_owner: "algenta_managed",
        }),
      ],
    });
    const binding = await createManifestBinding(runtime);
    await runtime.discoverCapabilityBinding(binding.binding_id);

    await expectRuntimeValidationError(
      runtime.executeCapability({ capability_id: ROUTER_ID, binding_id: "other-binding" }),
      "binding_mismatch",
      "binding_id does not match",
    );
    const ownerError = runtime.executeCapability({ capability_id: EXPORTER_ID });
    await expectRuntimeValidationError(
      ownerError,
      "capability_execution_owner_unsupported",
      "only supports client_managed",
    );
    await expect(ownerError).rejects.toMatchObject({
      details: { capability_id: EXPORTER_ID, execution_owner: "algenta_managed" },
    });
    const adapterError = runtime.executeCapability({ capability_id: "cap.tool.pager" });
    await expectRuntimeValidationError(
      adapterError,
      "capability_adapter_missing",
      "requires a registered adapter",
    );
    await expect(adapterError).rejects.toMatchObject({
      details: { capability_id: "cap.tool.pager" },
    });
  });

  it("answers instruction-only capabilities from the manifest without an adapter", async () => {
    const runtime = new Runtime({ mode: "local" });
    const binding = await createManifestBinding(runtime);
    await runtime.discoverCapabilityBinding(binding.binding_id);

    const execution = await runtime.executeCapability({
      capability_id: "cap.skill.triage",
      binding_id: binding.binding_id,
    });
    expect(execution).toMatchObject({
      capability_id: "cap.skill.triage",
      provider_id: "provider.manifest.customer",
      binding_id: binding.binding_id,
      execution_owner: "client_managed",
      status: "succeeded",
      error: null,
      output: {
        instruction_text: "Triage the incident by severity.",
        capability_id: "cap.skill.triage",
        instruction_artifact_ref: expect.stringMatching(/^artifact:\/\/local-capability\//),
      },
    });
    expect(execution.execution_session_id).toMatch(/^local-exec-[0-9a-f]{24}$/);
    expect(execution.completed_at).toEqual(expect.any(String));
    expect(Date.parse(String(execution.completed_at))).toBeGreaterThanOrEqual(
      Date.parse(String(execution.started_at)),
    );
  });

  it("normalizes an adapter that returns nothing to a null output", async () => {
    const runtime = new Runtime({
      mode: "local",
      capabilityAdapters: [makeAdapter({}, () => undefined)],
    });
    const execution = await runtime.executeCapability({ capability_id: ROUTER_ID, input: null });
    expect(execution.output).toBeNull();
    expect(execution.status).toBe("succeeded");
  });

  it("records outcomes with defaults and explicit fields", async () => {
    const runtime = new Runtime({ mode: "local" });
    const defaulted = await runtime.recordCapabilityOutcome({
      capability_id: ROUTER_ID,
      provider_id: "provider.native_tool_pack.customer",
    });
    expect(defaulted).toMatchObject({
      capability_id: ROUTER_ID,
      provider_id: "provider.native_tool_pack.customer",
      binding_id: null,
      success: null,
      result_status: "reported",
      confidence: null,
      latency_ms: null,
      error_code: null,
      details: null,
    });
    expect(defaulted.outcome_id).toMatch(/^local-outcome-[0-9a-f]{24}$/);

    const explicit = await runtime.recordCapabilityOutcome({
      capability_id: ROUTER_ID,
      provider_id: "provider.native_tool_pack.customer",
      binding_id: "binding-1",
      success: false,
      result_status: "failed",
      confidence: 0.2,
      latency_ms: 12,
      error_code: "timeout",
      details: { attempt: 2 },
    });
    expect(explicit).toMatchObject({
      binding_id: "binding-1",
      success: false,
      result_status: "failed",
      confidence: 0.2,
      latency_ms: 12,
      error_code: "timeout",
      details: { attempt: 2 },
    });
    expect(runtime.localCapabilityOutcomes).toEqual([defaulted, explicit]);
  });
});

describe("Runtime local skills and MCP providers", () => {
  it("enableSkill creates a user-scoped manifest binding and disableSkill removes it", async () => {
    const runtime = new Runtime({ mode: "local" });
    const discovered = await runtime.enableSkill({
      // Runs of whitespace collapse to one underscore in the capability id.
      skill_name: "Escalation  Playbook",
      instruction: "Escalate to the on-call lead.",
      description: "How to escalate",
      tags: ["escalation"],
      artifact_affinities: ["incident"],
    });

    expect(discovered.capability_count).toBe(1);
    const [skill] = discovered.capabilities;
    expect(skill).toMatchObject({
      capability_id: "cap.skill.escalation_playbook",
      name: "Escalation  Playbook",
      kind: "skill",
      implementation_kind: "instruction_only",
      execution_owner: "client_managed",
      description: "How to escalate",
      tags: ["escalation"],
      artifact_affinities: ["incident"],
      replayability: "deterministic",
      instruction_text: "Escalate to the on-call lead.",
    });
    if (!discovered.binding_id) throw new Error("enableSkill must return the binding id");
    expect(await runtime.getCapabilityBinding(discovered.binding_id)).toMatchObject({
      provider_id: "provider.skill_pack.algenta",
      profile_id: "profile.skill_pack.user",
      binding_name: "Escalation  Playbook",
      scope: "user",
      status: "ready",
    });
    expect((await runtime.listSkills()).map(entry => entry.capability_id)).toEqual([
      "cap.skill.escalation_playbook",
    ]);
    expect((await runtime.listCapabilityProviders())[0].provider_type).toBe("skill_pack");

    // The defaults apply when the optional fields are omitted.
    const minimal = await runtime.enableSkill({
      skill_name: "Minimal",
      instruction: "Do the minimum.",
      execution_owner: "algenta_managed",
    });
    expect(minimal.capabilities[0]).toMatchObject({
      description: null,
      tags: [],
      artifact_affinities: [],
      execution_owner: "algenta_managed",
    });

    await runtime.disableSkill(discovered.binding_id);
    expect((await runtime.listSkills()).map(entry => entry.capability_id)).toEqual([
      "cap.skill.minimal",
    ]);
  });

  it("listMcpProviders returns only MCP-typed providers", async () => {
    const runtime = new Runtime({
      mode: "local",
      capabilityAdapters: [
        makeAdapter(),
        makeAdapter({
          capability_id: "cap.mcp.search",
          provider_id: "provider.mcp.search",
          name: "Search",
          kind: "mcp_tool",
        }),
      ],
    });
    const providers = await runtime.listMcpProviders();
    expect(providers.map(provider => provider.provider_id)).toEqual(["provider.mcp.search"]);
    expect(providers[0].provider_type).toBe("mcp_provider");
  });
});
