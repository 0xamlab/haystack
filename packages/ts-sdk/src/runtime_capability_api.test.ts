// SPDX-License-Identifier: Apache-2.0
/**
 * API / self_hosted transport for the Runtime capability plane. Every method is a
 * thin delegation to the matching DecisionEngineClient method, so one table proves
 * the whole surface forwards its arguments unchanged and returns the client's
 * answer untouched. getContract additionally validates the payload it receives.
 */
import { describe, expect, it, vi } from "vitest";

import { DecisionEngineError } from "./client.js";
import {
  Runtime,
  RuntimeConfigurationError,
  RuntimeValidationError,
} from "./runtime.js";
import { makeContractPayload } from "./_runtime_test_helpers.js";

type Delegation = {
  /** Runtime method under test, as the label. */
  method: string;
  /** Invokes the Runtime method with representative arguments. */
  call: (runtime: Runtime) => Promise<unknown>;
  /** Client method the call must land on. */
  clientMethod: string;
  /** Exactly the arguments the client must receive. */
  expectedArgs: unknown[];
};

const BINDING_REQUEST = {
  provider_id: "provider.mcp.generic",
  profile_id: "profile.mcp.default",
  binding_name: "Generic",
};

const DELEGATIONS: Delegation[] = [
  {
    method: "listCapabilityProviders",
    call: runtime => runtime.listCapabilityProviders(),
    clientMethod: "listCapabilityProviders",
    expectedArgs: [],
  },
  {
    method: "getCapabilityProvider",
    call: runtime => runtime.getCapabilityProvider("provider.mcp.generic"),
    clientMethod: "getCapabilityProvider",
    expectedArgs: ["provider.mcp.generic"],
  },
  {
    method: "listCapabilityBindings",
    call: runtime => runtime.listCapabilityBindings({ providerId: "p", scope: "user" }),
    clientMethod: "listCapabilityBindings",
    expectedArgs: [{ providerId: "p", scope: "user" }],
  },
  {
    method: "listCapabilityBindings (no options)",
    call: runtime => runtime.listCapabilityBindings(),
    clientMethod: "listCapabilityBindings",
    expectedArgs: [{}],
  },
  {
    method: "createCapabilityBinding",
    call: runtime => runtime.createCapabilityBinding(BINDING_REQUEST),
    clientMethod: "createCapabilityBinding",
    expectedArgs: [BINDING_REQUEST],
  },
  {
    method: "getCapabilityBinding",
    call: runtime => runtime.getCapabilityBinding("binding-1"),
    clientMethod: "getCapabilityBinding",
    expectedArgs: ["binding-1"],
  },
  {
    method: "updateCapabilityBinding",
    call: runtime => runtime.updateCapabilityBinding("binding-1", { binding_name: "Renamed" }),
    clientMethod: "updateCapabilityBinding",
    expectedArgs: ["binding-1", { binding_name: "Renamed" }],
  },
  {
    method: "deleteCapabilityBinding",
    call: runtime => runtime.deleteCapabilityBinding("binding-1"),
    clientMethod: "deleteCapabilityBinding",
    expectedArgs: ["binding-1"],
  },
  {
    method: "previewTestCapabilityBinding",
    call: runtime => runtime.previewTestCapabilityBinding(BINDING_REQUEST),
    clientMethod: "previewTestCapabilityBinding",
    expectedArgs: [BINDING_REQUEST],
  },
  {
    method: "testCapabilityBinding",
    call: runtime => runtime.testCapabilityBinding("binding-1"),
    clientMethod: "testCapabilityBinding",
    expectedArgs: ["binding-1"],
  },
  {
    method: "previewDiscoverCapabilityBinding",
    call: runtime => runtime.previewDiscoverCapabilityBinding(BINDING_REQUEST),
    clientMethod: "previewDiscoverCapabilityBinding",
    expectedArgs: [BINDING_REQUEST],
  },
  {
    method: "discoverCapabilityBinding",
    call: runtime => runtime.discoverCapabilityBinding("binding-1"),
    clientMethod: "discoverCapabilityBinding",
    expectedArgs: ["binding-1"],
  },
  {
    method: "startCapabilityAuthorization",
    call: runtime =>
      runtime.startCapabilityAuthorization("binding-1", { requested_scopes: ["read"] }),
    clientMethod: "startCapabilityAuthorization",
    expectedArgs: ["binding-1", { requested_scopes: ["read"] }],
  },
  {
    method: "completeCapabilityAuthorization",
    call: runtime => runtime.completeCapabilityAuthorization("binding-1", { session_id: "s-1" }),
    clientMethod: "completeCapabilityAuthorization",
    expectedArgs: ["binding-1", { session_id: "s-1" }],
  },
  {
    method: "listCapabilities",
    call: runtime => runtime.listCapabilities({ kinds: ["skill"] }),
    clientMethod: "listCapabilities",
    expectedArgs: [{ kinds: ["skill"] }],
  },
  {
    method: "getCapability",
    call: runtime => runtime.getCapability("cap.skill.x", { includeInstruction: true }),
    clientMethod: "getCapability",
    expectedArgs: ["cap.skill.x", { includeInstruction: true }],
  },
  {
    method: "getCapability (no options)",
    call: runtime => runtime.getCapability("cap.skill.x"),
    clientMethod: "getCapability",
    expectedArgs: ["cap.skill.x", {}],
  },
  {
    method: "routeCapabilities",
    call: runtime => runtime.routeCapabilities({ objective: "route it" }),
    clientMethod: "routeCapabilities",
    expectedArgs: [{ objective: "route it" }],
  },
  {
    method: "executeCapability",
    call: runtime => runtime.executeCapability({ capability_id: "cap.skill.x" }),
    clientMethod: "executeCapability",
    expectedArgs: [{ capability_id: "cap.skill.x" }],
  },
  {
    method: "recordCapabilityOutcome",
    call: runtime =>
      runtime.recordCapabilityOutcome({ capability_id: "cap.skill.x", provider_id: "p" }),
    clientMethod: "recordCapabilityOutcome",
    expectedArgs: [{ capability_id: "cap.skill.x", provider_id: "p" }],
  },
  {
    method: "listSkills",
    call: runtime => runtime.listSkills(),
    clientMethod: "listSkills",
    expectedArgs: [],
  },
  {
    method: "enableSkill",
    call: runtime => runtime.enableSkill({ skill_name: "Triage", instruction: "Do it." }),
    clientMethod: "enableSkill",
    expectedArgs: [{ skill_name: "Triage", instruction: "Do it." }],
  },
  {
    method: "disableSkill",
    call: runtime => runtime.disableSkill("binding-1"),
    clientMethod: "disableSkill",
    expectedArgs: ["binding-1"],
  },
  {
    method: "listMcpProviders",
    call: runtime => runtime.listMcpProviders(),
    clientMethod: "listMcpProviders",
    expectedArgs: [],
  },
];

function makeFakeClient(sentinel: unknown): Record<string, ReturnType<typeof vi.fn>> {
  const client: Record<string, ReturnType<typeof vi.fn>> = {};
  for (const { clientMethod } of DELEGATIONS) {
    client[clientMethod] = vi.fn(async () => sentinel);
  }
  return client;
}

describe("Runtime capability plane over the API transport", () => {
  it.each(DELEGATIONS)("$method delegates to the client", async ({ call, clientMethod, expectedArgs }) => {
    const sentinel = { from: clientMethod };
    const client = makeFakeClient(sentinel);
    const runtime = new Runtime({ mode: "api", apiKey: "de_test_key", client: client as never });

    const result = await call(runtime);

    expect(client[clientMethod]).toHaveBeenCalledTimes(1);
    expect(client[clientMethod].mock.calls[0]).toEqual(expectedArgs);
    // deleteCapabilityBinding / disableSkill resolve to void by contract.
    if (clientMethod === "deleteCapabilityBinding" || clientMethod === "disableSkill") {
      expect(result).toBeUndefined();
    } else {
      expect(result).toBe(sentinel);
    }
    // Nothing leaks into the local registries when the API transport is in use.
    expect(runtime.localCapabilityBindings.size).toBe(0);
    expect(runtime.localCapabilityCatalog.size).toBe(0);
  });

  it("self_hosted mode uses the same delegation path", async () => {
    const client = { listCapabilityProviders: vi.fn(async () => []) };
    const runtime = new Runtime({
      mode: "self_hosted",
      baseUrl: "https://engine.customer.internal",
      apiKey: "de_test_key",
      client: client as never,
    });
    expect(await runtime.listCapabilityProviders()).toEqual([]);
    expect(client.listCapabilityProviders).toHaveBeenCalledTimes(1);
  });
});

describe("Runtime.getContract", () => {
  it("returns the validated platform contract from the API", async () => {
    const payload = makeContractPayload();
    const client = { getContract: vi.fn(async () => payload) };
    const runtime = new Runtime({ mode: "api", apiKey: "de_test_key", client: client as never });

    const contract = await runtime.getContract();

    expect(contract.api_base_url).toBe(payload.api_base_url);
    expect(contract.integrations).toEqual(payload.integrations);
    expect(client.getContract).toHaveBeenCalledTimes(1);
  });

  it("is unavailable in local mode", async () => {
    const runtime = new Runtime({ mode: "local" });
    await expect(runtime.getContract()).rejects.toBeInstanceOf(RuntimeConfigurationError);
    await expect(runtime.getContract()).rejects.toMatchObject({
      code: "local_mode_not_supported",
      message: expect.stringContaining("getContract() is not supported"),
    });
  });

  it("normalizes an invalid payload into a RuntimeValidationError with the upstream cause", async () => {
    const client = { getContract: vi.fn(async () => ({ contract_version: "" })) };
    const runtime = new Runtime({ mode: "api", apiKey: "de_test_key", client: client as never });

    const failure = runtime.getContract();
    await expect(failure).rejects.toBeInstanceOf(RuntimeValidationError);
    await expect(failure).rejects.toMatchObject({
      code: "invalid_contract_payload",
      message: "getContract() returned an invalid payload.",
      details: {
        source_error_code: "invalid_contract_payload",
        source_status_code: 0,
        cause: expect.stringContaining("contract_version"),
      },
    });
  });

  it("normalizes an upstream contract error and passes other client errors through", async () => {
    const upstream = new DecisionEngineError(
      "OpenAPI contract fallback is missing x-primary-data-query-contract.",
      0,
      "contract_extension_missing",
      { error: { code: "contract_extension_missing", details: { path: "/openapi.json" } } },
    );
    const runtime = new Runtime({
      mode: "api",
      apiKey: "de_test_key",
      client: { getContract: vi.fn(async () => { throw upstream; }) } as never,
    });
    await expect(runtime.getContract()).rejects.toMatchObject({
      code: "invalid_contract_payload",
      details: {
        cause: upstream.message,
        source_error_code: "contract_extension_missing",
        source_error_details: { path: "/openapi.json" },
      },
    });

    const unrelated = new DecisionEngineError("Unauthorized", 401, "authentication_error");
    const unauthorized = new Runtime({
      mode: "api",
      apiKey: "de_test_key",
      client: { getContract: vi.fn(async () => { throw unrelated; }) } as never,
    });
    await expect(unauthorized.getContract()).rejects.toBe(unrelated);
  });
});
