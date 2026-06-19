import { afterEach, describe, expect, it, vi } from "vitest";

import { DecisionEngineClient } from "./client.js";
import { Runtime, RuntimeValidationError } from "./runtime.js";

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

describe("capability plane SDK surface", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("DecisionEngineClient calls the canonical capability-plane endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse([
          {
            provider_id: "provider.mcp.generic",
            provider_type: "mcp_provider",
            name: "Generic MCP Provider",
            description: null,
            docs_url: null,
            auth_schema: { type: "oauth_or_api_key", fields: ["server_url"] },
            certification_summary: { owner: "customer", certified: false },
            policy_summary: { route_authority: "capability_plane" },
            supported_execution_owners: ["client_managed"],
            install_metadata: { discovery_mode: "binding_manifest" },
            customer_metadata: null,
            active: true,
            profiles: [],
          },
        ]),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          selected_capability_id: "cap.skill.escalation",
          selected_provider_id: "provider.skill_pack.algenta",
          selected_binding_id: "binding-skill-1",
          kind: "skill",
          execution_owner: "algenta_managed",
          requires_approval: false,
          confidence: 0.91,
          reason: "token overlap: incident",
          fallbacks: [],
          policy_snapshot_id: "capability-plane-policy-v1",
          selected_tool_name: null,
          instruction_artifact_ref: "artifact://capability-snapshot/abc/cap.skill.escalation",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const client = new DecisionEngineClient({
      apiKey: "de_test_capability_plane",
      baseUrl: "https://example.test",
    });

    const providers = await client.listCapabilityProviders();
    const routePlan = await client.routeCapabilities({
      objective: "Escalate the production incident",
      kinds: ["skill"],
      max_fallbacks: 0,
    });

    expect(providers[0]?.provider_id).toBe("provider.mcp.generic");
    expect(routePlan.selected_capability_id).toBe("cap.skill.escalation");
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/v1/capability-providers");
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain("/v1/capabilities/route");
  });

  it("Runtime local mode registers adapters, routes, and executes client-managed capabilities", async () => {
    const runtime = new Runtime({
      mode: "local",
      capabilityAdapters: [
        {
          descriptor: {
            capability_id: "cap.native.incident_router",
            provider_id: "provider.native_tool_pack.customer",
            name: "Incident Router",
            kind: "native_tool",
            execution_owner: "client_managed",
            tags: ["incident", "route"],
            artifact_affinities: ["incident"],
          },
          execute: async request => ({
            routed_to: "incident-command",
            input: request.input ?? null,
          }),
        },
      ],
    });

    const providers = await runtime.listCapabilityProviders();
    const capabilities = await runtime.listCapabilities({
      kinds: ["native_tool"],
    });
    const routePlan = await runtime.routeCapabilities({
      objective: "Route the active incident",
      kinds: ["native_tool"],
      artifact_affinities: ["incident"],
      max_fallbacks: 0,
    });
    const execution = await runtime.executeCapability({
      capability_id: "cap.native.incident_router",
      input: { severity: "critical" },
    });

    expect(providers[0]?.provider_id).toBe("provider.native_tool_pack.customer");
    expect(capabilities[0]?.capability_id).toBe("cap.native.incident_router");
    expect(routePlan.selected_capability_id).toBe("cap.native.incident_router");
    expect(execution.status).toBe("succeeded");
    expect(execution.output).toEqual({
      routed_to: "incident-command",
      input: { severity: "critical" },
    });
  });

  it("Runtime local mode rejects algenta-managed capability execution", async () => {
    const runtime = new Runtime({ mode: "local" });

    await runtime.enableSkill({
      skill_name: "Governed Skill",
      instruction: "Run through Algenta-managed execution.",
      execution_owner: "algenta_managed",
    });

    await expect(
      runtime.executeCapability({
        capability_id: "cap.skill.governed_skill",
      }),
    ).rejects.toMatchObject<Partial<RuntimeValidationError>>({
      code: "capability_execution_owner_unsupported",
      details: {
        capability_id: "cap.skill.governed_skill",
        execution_owner: "algenta_managed",
      },
    });
  });

  it("Runtime local mode rejects a client-managed capability when the adapter is missing", async () => {
    const runtime = new Runtime({ mode: "local" });

    const binding = await runtime.createCapabilityBinding({
      provider_id: "provider.native_tool_pack.customer",
      profile_id: "profile.native_tool_pack.workspace",
      binding_name: "Dispatch Stub",
      scope: "workspace",
      execution_owner: "client_managed",
      config: {
        manifest: {
          capabilities: [
            {
              capability_id: "cap.native.dispatch_stub",
              name: "Dispatch Stub",
              kind: "native_tool",
              implementation_kind: "callable",
              execution_owner: "client_managed",
              tags: ["incident"],
              artifact_affinities: ["incident"],
            },
          ],
        },
      },
    });
    await runtime.discoverCapabilityBinding(binding.binding_id);

    await expect(
      runtime.executeCapability({
        capability_id: "cap.native.dispatch_stub",
        input: { severity: "critical" },
      }),
    ).rejects.toMatchObject<Partial<RuntimeValidationError>>({
      code: "capability_adapter_missing",
      details: {
        capability_id: "cap.native.dispatch_stub",
      },
    });
  });
});
