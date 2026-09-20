// SPDX-License-Identifier: Apache-2.0
// Wire-shape tests for every DecisionEngineClient method in
// _client_class_methods_agent_capability.ts, plus the connector, dataset,
// simulate and decision methods that had no request-shape coverage. Each case
// asserts the exact URL (path and query), the HTTP method, the JSON body sent to
// fetch, and that the parsed response is handed back unchanged.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DecisionEngineClient } from "./client.js";
import type { CapabilityProviderResponse, SimulateRequest } from "./types.js";

const ORIGINAL_ENV = { ...process.env };
const HERMETIC_ENV_KEYS = [
  "ALGENTA_API_KEY",
  "DE_API_KEY",
  "ALGENTA_BASE_URL",
  "DE_BASE_URL",
  "ALGENTA_API_URL",
  "ALGENTA_DEPLOYMENT_MODE",
  "ALGENTA_DISABLE_CLOUD",
  "ALGENTA_DEVICE_ID",
  "DE_DEVICE_ID",
];
const BASE_URL = "https://example.test";

interface MethodCase {
  name: string;
  invoke: (client: DecisionEngineClient) => Promise<unknown>;
  method: "GET" | "POST" | "PATCH" | "DELETE";
  path: string;
  /** Omitted when the method sends no body at all. */
  body?: unknown;
  /** Methods declared `Promise<void>` swallow the parsed body. */
  returnsVoid?: boolean;
}

function restoreEnv(): void {
  for (const key of Object.keys(process.env)) {
    if (!(key in ORIGINAL_ENV)) {
      delete process.env[key];
    }
  }
  Object.assign(process.env, ORIGINAL_ENV);
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

function sseResponse(events: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const event of events) {
        controller.enqueue(encoder.encode(event));
      }
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { "content-type": "text/event-stream" },
  });
}

function newClient(): DecisionEngineClient {
  return new DecisionEngineClient({
    apiKey: "de_test_methods",
    baseUrl: BASE_URL,
    maxRetries: 0,
    timeout: 1_000,
  });
}

function fetchCall(fetchMock: ReturnType<typeof vi.fn>, index: number): [string, RequestInit] {
  return fetchMock.mock.calls[index] as [string, RequestInit];
}

function expectRequest(
  fetchMock: ReturnType<typeof vi.fn>,
  index: number,
  expected: { method: string; path: string; body?: unknown },
): void {
  const [url, init] = fetchCall(fetchMock, index);
  expect(url).toBe(`${BASE_URL}${expected.path}`);
  expect(init.method).toBe(expected.method);
  if (expected.body === undefined) {
    expect(init.body).toBeUndefined();
  } else {
    expect(JSON.parse(String(init.body))).toEqual(expected.body);
  }
}

const AGENT_QUERY_OPTIONS = {
  page: 3,
  limit: 7,
  status: "running",
  request_hash: "hash-1",
  policy_snapshot_id: "policy-1",
  schema_snapshot_id: "schema-1",
};
const AGENT_QUERY_SUFFIX =
  "page=3&limit=7&status=running&request_hash=hash-1&policy_snapshot_id=policy-1" +
  "&schema_snapshot_id=schema-1";

const BINDING_CREATE_REQUEST = {
  provider_id: "provider.mcp.generic",
  profile_id: "profile.mcp.default",
  binding_name: "Ops MCP",
  scope: "workspace" as const,
  execution_owner: "client_managed" as const,
  config: { server_url: "https://mcp.example.test" },
};
const BINDING_PREVIEW_REQUEST = {
  provider_id: "provider.mcp.generic",
  profile_id: "profile.mcp.default",
  config: { server_url: "https://mcp.example.test" },
};

const AGENT_RUN_CASES: MethodCase[] = [
  {
    name: "createAgentRun",
    invoke: client => client.createAgentRun({ task: "Summarize incidents", max_steps: 3 }),
    method: "POST",
    path: "/v1/agent/runs",
    body: { task: "Summarize incidents", max_steps: 3 },
  },
  {
    name: "getAgentRun",
    invoke: client => client.getAgentRun("run-1"),
    method: "GET",
    path: "/v1/agent/runs/run-1",
  },
  {
    name: "listAgentRuns (defaults)",
    invoke: client => client.listAgentRuns(),
    method: "GET",
    path: "/v1/agent/runs?page=1&limit=25",
  },
  {
    name: "listAgentRuns (explicit options)",
    invoke: client => client.listAgentRuns(AGENT_QUERY_OPTIONS),
    method: "GET",
    path: `/v1/agent/runs?${AGENT_QUERY_SUFFIX}`,
  },
  {
    name: "getAgentRunEvents (default limit)",
    invoke: client => client.getAgentRunEvents("run-1"),
    method: "GET",
    path: "/v1/agent/runs/run-1/events?limit=1000",
  },
  {
    name: "getAgentRunEvents (explicit limit)",
    invoke: client => client.getAgentRunEvents("run-1", { limit: 5 }),
    method: "GET",
    path: "/v1/agent/runs/run-1/events?limit=5",
  },
  {
    name: "listAgentRunCheckpoints",
    invoke: client => client.listAgentRunCheckpoints("run-1"),
    method: "GET",
    path: "/v1/agent/runs/run-1/checkpoints",
  },
  {
    name: "queryAgentRunCheckpoints (defaults)",
    invoke: client => client.queryAgentRunCheckpoints(),
    method: "GET",
    path: "/v1/agent/runs/checkpoints?page=1&limit=25",
  },
  {
    name: "queryAgentRunCheckpoints (explicit options)",
    invoke: client =>
      client.queryAgentRunCheckpoints({
        ...AGENT_QUERY_OPTIONS,
        run_id: "run-1",
        checkpoint_id: "cp-1",
      }),
    method: "GET",
    path: `/v1/agent/runs/checkpoints?${AGENT_QUERY_SUFFIX}&run_id=run-1&checkpoint_id=cp-1`,
  },
  {
    name: "listAgentRunMissionEvents (default limit)",
    invoke: client => client.listAgentRunMissionEvents("run-1"),
    method: "GET",
    path: "/v1/agent/runs/run-1/mission-events?limit=1000",
  },
  {
    name: "listAgentRunMissionEvents (explicit limit)",
    invoke: client => client.listAgentRunMissionEvents("run-1", { limit: 2 }),
    method: "GET",
    path: "/v1/agent/runs/run-1/mission-events?limit=2",
  },
  {
    name: "queryAgentRunMissionEvents (defaults)",
    invoke: client => client.queryAgentRunMissionEvents(),
    method: "GET",
    path: "/v1/agent/runs/mission-events?page=1&limit=25",
  },
  {
    name: "queryAgentRunMissionEvents (explicit options)",
    invoke: client =>
      client.queryAgentRunMissionEvents({
        ...AGENT_QUERY_OPTIONS,
        run_id: "run-1",
        event_type: "tool_call",
      }),
    method: "GET",
    path: `/v1/agent/runs/mission-events?${AGENT_QUERY_SUFFIX}&run_id=run-1&event_type=tool_call`,
  },
  {
    name: "replayAgentRun (no checkpoint)",
    invoke: client => client.replayAgentRun("run-1"),
    method: "POST",
    path: "/v1/agent/runs/run-1/replay",
    body: { checkpoint_id: null },
  },
  {
    name: "replayAgentRun (from checkpoint)",
    invoke: client => client.replayAgentRun("run-1", { checkpoint_id: "cp-1" }),
    method: "POST",
    path: "/v1/agent/runs/run-1/replay",
    body: { checkpoint_id: "cp-1" },
  },
  {
    name: "forkAgentRun (no checkpoint)",
    invoke: client => client.forkAgentRun("run-1"),
    method: "POST",
    path: "/v1/agent/runs/run-1/fork",
    body: { checkpoint_id: null },
  },
  {
    name: "forkAgentRun (from checkpoint)",
    invoke: client => client.forkAgentRun("run-1", { checkpoint_id: "cp-2" }),
    method: "POST",
    path: "/v1/agent/runs/run-1/fork",
    body: { checkpoint_id: "cp-2" },
  },
  {
    name: "resumeAgentRun",
    invoke: client => client.resumeAgentRun("run-1"),
    method: "POST",
    path: "/v1/agent/runs/run-1/resume",
    body: {},
  },
  {
    name: "cancelAgentRun",
    invoke: client => client.cancelAgentRun("run-1"),
    method: "POST",
    path: "/v1/agent/runs/run-1/cancel",
    body: {},
  },
  {
    name: "approveAgentRun",
    invoke: client => client.approveAgentRun("run-1"),
    method: "POST",
    path: "/v1/agent/runs/run-1/approve",
    body: {},
  },
  {
    name: "listAgentRunTelemetry (default limit)",
    invoke: client => client.listAgentRunTelemetry("run-1"),
    method: "GET",
    path: "/v1/agent/runs/run-1/telemetry?limit=1000",
  },
  {
    name: "listAgentRunTelemetry (explicit limit)",
    invoke: client => client.listAgentRunTelemetry("run-1", { limit: 50 }),
    method: "GET",
    path: "/v1/agent/runs/run-1/telemetry?limit=50",
  },
  {
    name: "queryAgentRunTelemetry (defaults)",
    invoke: client => client.queryAgentRunTelemetry(),
    method: "GET",
    path: "/v1/agent/runs/telemetry?page=1&limit=25",
  },
  {
    name: "queryAgentRunTelemetry (explicit options)",
    invoke: client =>
      client.queryAgentRunTelemetry({
        ...AGENT_QUERY_OPTIONS,
        run_id: "run-1",
        telemetry_kind: "kernel",
        module_name: "monte_carlo",
      }),
    method: "GET",
    path:
      `/v1/agent/runs/telemetry?${AGENT_QUERY_SUFFIX}&run_id=run-1` +
      "&telemetry_kind=kernel&module_name=monte_carlo",
  },
];

const CAPABILITY_CASES: MethodCase[] = [
  {
    name: "listCapabilityProviders",
    invoke: client => client.listCapabilityProviders(),
    method: "GET",
    path: "/v1/capability-providers",
  },
  {
    name: "getCapabilityProvider",
    invoke: client => client.getCapabilityProvider("provider.mcp.generic"),
    method: "GET",
    path: "/v1/capability-providers/provider.mcp.generic",
  },
  {
    name: "listCapabilityBindings (no filters)",
    invoke: client => client.listCapabilityBindings(),
    method: "GET",
    path: "/v1/capability-bindings",
  },
  {
    name: "listCapabilityBindings (filters)",
    invoke: client =>
      client.listCapabilityBindings({ providerId: "provider.mcp.generic", scope: "user" }),
    method: "GET",
    path: "/v1/capability-bindings?provider_id=provider.mcp.generic&scope=user",
  },
  {
    name: "createCapabilityBinding",
    invoke: client => client.createCapabilityBinding(BINDING_CREATE_REQUEST),
    method: "POST",
    path: "/v1/capability-bindings",
    body: BINDING_CREATE_REQUEST,
  },
  {
    name: "getCapabilityBinding",
    invoke: client => client.getCapabilityBinding("binding-1"),
    method: "GET",
    path: "/v1/capability-bindings/binding-1",
  },
  {
    name: "updateCapabilityBinding",
    invoke: client => client.updateCapabilityBinding("binding-1", { status: "ready" }),
    method: "PATCH",
    path: "/v1/capability-bindings/binding-1",
    body: { status: "ready" },
  },
  {
    name: "deleteCapabilityBinding",
    invoke: client => client.deleteCapabilityBinding("binding-1"),
    method: "DELETE",
    path: "/v1/capability-bindings/binding-1",
    returnsVoid: true,
  },
  {
    name: "previewTestCapabilityBinding",
    invoke: client => client.previewTestCapabilityBinding(BINDING_PREVIEW_REQUEST),
    method: "POST",
    path: "/v1/capability-bindings/test",
    body: BINDING_PREVIEW_REQUEST,
  },
  {
    name: "testCapabilityBinding",
    invoke: client => client.testCapabilityBinding("binding-1"),
    method: "POST",
    path: "/v1/capability-bindings/binding-1/test",
  },
  {
    name: "previewDiscoverCapabilityBinding",
    invoke: client => client.previewDiscoverCapabilityBinding(BINDING_PREVIEW_REQUEST),
    method: "POST",
    path: "/v1/capability-bindings/discover",
    body: BINDING_PREVIEW_REQUEST,
  },
  {
    name: "discoverCapabilityBinding",
    invoke: client => client.discoverCapabilityBinding("binding-1"),
    method: "POST",
    path: "/v1/capability-bindings/binding-1/discover",
  },
  {
    name: "startCapabilityAuthorization",
    invoke: client =>
      client.startCapabilityAuthorization("binding-1", {
        redirect_uri: "https://app.example.test/callback",
        requested_scopes: ["read"],
      }),
    method: "POST",
    path: "/v1/capability-bindings/binding-1/authorize/start",
    body: { redirect_uri: "https://app.example.test/callback", requested_scopes: ["read"] },
  },
  {
    name: "completeCapabilityAuthorization",
    invoke: client =>
      client.completeCapabilityAuthorization("binding-1", {
        session_id: "session-1",
        authorization_code: "code-1",
      }),
    method: "POST",
    path: "/v1/capability-bindings/binding-1/authorize/complete",
    body: { session_id: "session-1", authorization_code: "code-1" },
  },
  {
    name: "listCapabilities (no filters)",
    invoke: client => client.listCapabilities(),
    method: "GET",
    path: "/v1/capabilities",
  },
  {
    // Repeated keys, not comma-joined lists: that is what the server parses.
    name: "listCapabilities (repeated filter keys)",
    invoke: client =>
      client.listCapabilities({
        kinds: ["skill", "mcp_tool"],
        providerIds: ["provider.a"],
        bindingIds: ["binding-1", "binding-2"],
      }),
    method: "GET",
    path:
      "/v1/capabilities?kinds=skill&kinds=mcp_tool&provider_ids=provider.a" +
      "&binding_ids=binding-1&binding_ids=binding-2",
  },
  {
    name: "getCapability (default)",
    invoke: client => client.getCapability("cap.skill.escalation"),
    method: "GET",
    path: "/v1/capabilities/cap.skill.escalation",
  },
  {
    name: "getCapability (includeInstruction: false)",
    invoke: client => client.getCapability("cap.skill.escalation", { includeInstruction: false }),
    method: "GET",
    path: "/v1/capabilities/cap.skill.escalation",
  },
  {
    name: "getCapability (includeInstruction: true)",
    invoke: client => client.getCapability("cap.skill.escalation", { includeInstruction: true }),
    method: "GET",
    path: "/v1/capabilities/cap.skill.escalation?include_instruction=1",
  },
  {
    name: "routeCapabilities",
    invoke: client => client.routeCapabilities({ objective: "Escalate", kinds: ["skill"] }),
    method: "POST",
    path: "/v1/capabilities/route",
    body: { objective: "Escalate", kinds: ["skill"] },
  },
  {
    name: "executeCapability",
    invoke: client =>
      client.executeCapability({ capability_id: "cap.tool.echo", input: { text: "hi" } }),
    method: "POST",
    path: "/v1/capabilities/execute",
    body: { capability_id: "cap.tool.echo", input: { text: "hi" } },
  },
  {
    name: "recordCapabilityOutcome",
    invoke: client =>
      client.recordCapabilityOutcome({
        capability_id: "cap.tool.echo",
        provider_id: "provider.native",
        success: true,
        latency_ms: 12,
      }),
    method: "POST",
    path: "/v1/capabilities/outcomes",
    body: {
      capability_id: "cap.tool.echo",
      provider_id: "provider.native",
      success: true,
      latency_ms: 12,
    },
  },
  {
    name: "listSkills",
    invoke: client => client.listSkills(),
    method: "GET",
    path: "/v1/capabilities?kinds=skill",
  },
  {
    name: "disableSkill",
    invoke: client => client.disableSkill("binding-skill-1"),
    method: "DELETE",
    path: "/v1/capability-bindings/binding-skill-1",
    returnsVoid: true,
  },
];

const SOURCE_SPEC = { type: "csv", url: "https://files.example.test/orders.csv" };
const QUERY_LIKE_REQUEST = { source_name: "orders", metric_column: "revenue", aggregation: "sum" };
const SIMULATE_REQUEST: SimulateRequest = {
  mode: "auto",
  scenario: {
    variables: { revenue: { low: 80_000, high: 200_000 } },
    objective: "maximize_net_value",
  },
};

const DATA_AND_DECISION_CASES: MethodCase[] = [
  {
    name: "registerSource (bare source)",
    invoke: client => client.registerSource(SOURCE_SPEC),
    method: "POST",
    path: "/v1/sources/register",
    body: { source: SOURCE_SPEC },
  },
  {
    // `name` is folded into the source spec; `description` stays top-level.
    name: "registerSource (name and description)",
    invoke: client =>
      client.registerSource(SOURCE_SPEC, { name: "orders", description: "Orders feed" }),
    method: "POST",
    path: "/v1/sources/register",
    body: { source: { ...SOURCE_SPEC, name: "orders" }, description: "Orders feed" },
  },
  {
    name: "refreshSource",
    invoke: client => client.refreshSource("ds-1"),
    method: "POST",
    path: "/v1/data/ds-1/refresh",
  },
  {
    name: "getConnector",
    invoke: client => client.getConnector("conn-1"),
    method: "GET",
    path: "/v1/connectors/conn-1",
  },
  {
    name: "updateConnector",
    invoke: client => client.updateConnector("conn-1", { name: "Renamed", visibility: "team" }),
    method: "PATCH",
    path: "/v1/connectors/conn-1",
    body: { name: "Renamed", visibility: "team" },
  },
  {
    name: "testConnector",
    invoke: client => client.testConnector("conn-1"),
    method: "POST",
    path: "/v1/connectors/conn-1/test",
  },
  {
    name: "previewTestConnector",
    invoke: client =>
      client.previewTestConnector({ connector_type: "postgres", config: { host: "db.internal" } }),
    method: "POST",
    path: "/v1/connectors/test",
    body: { connector_type: "postgres", config: { host: "db.internal" } },
  },
  {
    name: "browseConnector",
    invoke: client => client.browseConnector("conn-1"),
    method: "GET",
    path: "/v1/connectors/conn-1/browse",
  },
  {
    name: "previewBrowseConnector",
    invoke: client => client.previewBrowseConnector({ connector_type: "s3", config: null }),
    method: "POST",
    path: "/v1/connectors/browse",
    body: { connector_type: "s3", config: null },
  },
  {
    name: "deleteConnector",
    invoke: client => client.deleteConnector("conn-1"),
    method: "DELETE",
    path: "/v1/connectors/conn-1",
    returnsVoid: true,
  },
  {
    name: "deleteDataset",
    invoke: client => client.deleteDataset("ds-1"),
    method: "DELETE",
    path: "/v1/data/ds-1",
  },
  {
    name: "simulate",
    invoke: client => client.simulate(SIMULATE_REQUEST),
    method: "POST",
    path: "/v1/simulate",
    body: SIMULATE_REQUEST,
  },
  {
    name: "listDecisions (no options)",
    invoke: client => client.listDecisions(),
    method: "GET",
    path: "/v1/decisions",
  },
  {
    name: "listDecisions (every option)",
    invoke: client =>
      client.listDecisions({ page: 2, limit: 10, page_size: 10, with_outcome_only: true }),
    method: "GET",
    path: "/v1/decisions?page=2&limit=10&page_size=10&with_outcome_only=true",
  },
  {
    name: "listDecisions (with_outcome_only: false is still sent)",
    invoke: client => client.listDecisions({ with_outcome_only: false }),
    method: "GET",
    path: "/v1/decisions?with_outcome_only=false",
  },
  {
    name: "resolve",
    invoke: client => client.resolve(QUERY_LIKE_REQUEST),
    method: "POST",
    path: "/v1/resolve",
    body: QUERY_LIKE_REQUEST,
  },
  {
    name: "verify",
    invoke: client => client.verify(QUERY_LIKE_REQUEST),
    method: "POST",
    path: "/v1/verify",
    body: QUERY_LIKE_REQUEST,
  },
];

function runMethodTable(cases: MethodCase[]): void {
  it.each(cases.map(testCase => [testCase.name, testCase] as const))(
    "%s sends the documented request and returns the parsed body",
    async (_name, testCase) => {
      const payload = { echo: testCase.name, items: [1, 2, 3] };
      const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse(payload));
      vi.stubGlobal("fetch", fetchMock);

      const result = await testCase.invoke(newClient());

      expect(fetchMock).toHaveBeenCalledTimes(1);
      expectRequest(fetchMock, 0, testCase);
      if (testCase.returnsVoid) {
        expect(result).toBeUndefined();
      } else {
        expect(result).toEqual(payload);
      }
    },
  );
}

describe("DecisionEngineClient method wire shapes", () => {
  beforeEach(() => {
    for (const key of HERMETIC_ENV_KEYS) {
      delete process.env[key];
    }
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    restoreEnv();
  });

  describe("agent runs", () => {
    runMethodTable(AGENT_RUN_CASES);

    it.each([
      ["default limit", undefined, "limit=1000&stream=true"],
      ["explicit limit", { limit: 10 }, "limit=10&stream=true"],
    ])("streamAgentRunEvents (%s) streams SSE events from the events endpoint", async (
      _label,
      options,
      query,
    ) => {
      const fetchMock = vi.fn().mockResolvedValueOnce(
        sseResponse([
          'data: {"event_type":"step","seq":1}\n\n',
          'data: {"event_type":"done","seq":2}\n\n',
          "data: [DONE]\n\n",
        ]),
      );
      vi.stubGlobal("fetch", fetchMock);

      const events = [];
      for await (const event of newClient().streamAgentRunEvents("run-1", options)) {
        events.push(event);
      }

      expect(events).toEqual([
        { event_type: "step", seq: 1 },
        { event_type: "done", seq: 2 },
      ]);
      expectRequest(fetchMock, 0, { method: "GET", path: `/v1/agent/runs/run-1/events?${query}` });
      const headers = fetchCall(fetchMock, 0)[1].headers as Record<string, string>;
      expect(headers.Accept).toBe("text/event-stream");
    });
  });

  describe("capability plane", () => {
    runMethodTable(CAPABILITY_CASES);

    it("enableSkill creates a skill-pack binding, then discovers it", async () => {
      const discovered = { binding_id: "binding-skill-1", capabilities: [] };
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(jsonResponse({ binding_id: "binding-skill-1" }))
        .mockResolvedValueOnce(jsonResponse(discovered));
      vi.stubGlobal("fetch", fetchMock);

      const result = await newClient().enableSkill({
        skill_name: "Incident  Escalation",
        instruction: "Page the on-call engineer.",
      });

      expect(result).toEqual(discovered);
      expect(fetchMock).toHaveBeenCalledTimes(2);
      expectRequest(fetchMock, 0, {
        method: "POST",
        path: "/v1/capability-bindings",
        body: {
          provider_id: "provider.skill_pack.algenta",
          profile_id: "profile.skill_pack.user",
          binding_name: "Incident  Escalation",
          scope: "user",
          execution_owner: "client_managed",
          config: {
            manifest: {
              capabilities: [
                {
                  // Lower-cased, with every whitespace run collapsed to one underscore.
                  capability_id: "cap.skill.incident_escalation",
                  name: "Incident  Escalation",
                  kind: "skill",
                  implementation_kind: "instruction_only",
                  execution_owner: "client_managed",
                  instruction: "Page the on-call engineer.",
                  artifact_affinities: [],
                  tags: [],
                  replayability: "deterministic",
                },
              ],
            },
          },
        },
      });
      expectRequest(fetchMock, 1, {
        method: "POST",
        path: "/v1/capability-bindings/binding-skill-1/discover",
      });
    });

    it("enableSkill forwards description, tags, affinities and an explicit execution owner", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(jsonResponse({ binding_id: "binding-skill-2" }))
        .mockResolvedValueOnce(jsonResponse({ binding_id: "binding-skill-2" }));
      vi.stubGlobal("fetch", fetchMock);

      await newClient().enableSkill({
        skill_name: "Triage",
        instruction: "Classify the ticket.",
        description: "Ticket triage",
        tags: ["support"],
        artifact_affinities: ["ticket"],
        execution_owner: "algenta_managed",
      });

      const body = JSON.parse(String(fetchCall(fetchMock, 0)[1].body)) as {
        execution_owner: string;
        config: { manifest: { capabilities: Array<Record<string, unknown>> } };
      };
      expect(body.execution_owner).toBe("algenta_managed");
      expect(body.config.manifest.capabilities[0]).toMatchObject({
        capability_id: "cap.skill.triage",
        description: "Ticket triage",
        tags: ["support"],
        artifact_affinities: ["ticket"],
        execution_owner: "algenta_managed",
      });
      expectRequest(fetchMock, 1, {
        method: "POST",
        path: "/v1/capability-bindings/binding-skill-2/discover",
      });
    });

    it("listMcpProviders keeps only mcp_provider entries", async () => {
      const providers = [
        { provider_id: "provider.mcp.generic", provider_type: "mcp_provider" },
        { provider_id: "provider.skill_pack.algenta", provider_type: "skill_pack" },
        { provider_id: "provider.mcp.github", provider_type: "mcp_provider" },
      ] as CapabilityProviderResponse[];
      const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse(providers));
      vi.stubGlobal("fetch", fetchMock);

      const result = await newClient().listMcpProviders();

      expect(result.map(provider => provider.provider_id)).toEqual([
        "provider.mcp.generic",
        "provider.mcp.github",
      ]);
      expectRequest(fetchMock, 0, { method: "GET", path: "/v1/capability-providers" });
    });
  });

  describe("data connectors, datasets, simulate and decisions", () => {
    runMethodTable(DATA_AND_DECISION_CASES);
  });
});
