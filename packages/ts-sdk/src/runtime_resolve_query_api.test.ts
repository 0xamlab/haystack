// SPDX-License-Identifier: Apache-2.0
/**
 * API-transport resolve/query paths in _runtime_class_methods_resolve_query.ts:
 * registration bookkeeping, schema-revision discovery, the exact-spec resolve
 * short-circuit, and the payload coercions applied before a request reaches the
 * DecisionEngineClient. Everything runs against an in-memory fake client.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RUNTIME_DATASET_SCOPE_KEY, Runtime, RuntimeValidationError } from "./runtime.js";
import type { ResolvedPlan, SourceRegistrationResponse } from "./types.js";

const ORIGINAL_ENV = { ...process.env };

/** A registration as the API returns it after Runtime.connect() in api mode. */
function makeRegistration(
  overrides: Partial<SourceRegistrationResponse> = {},
): SourceRegistrationResponse {
  return {
    status: "ready",
    source_id: "src_orders",
    dataset_id: "ds_orders",
    name: "orders",
    dataset_name: "orders",
    source_schema: { fields: ["revenue", "region", "order_date"] },
    schema: { fields: ["revenue", "region", "order_date"] },
    planner_schema_revision: "rev_planner",
    row_count: 12,
    ...overrides,
  };
}

function makePlan(overrides: Partial<ResolvedPlan> = {}): ResolvedPlan {
  return {
    source_name: "orders",
    metric_column: "revenue",
    aggregation: "sum",
    schema_revision: "rev_planner",
    ...overrides,
  } as ResolvedPlan;
}

type FakeClient = {
  registerSource: ReturnType<typeof vi.fn>;
  resolve: ReturnType<typeof vi.fn>;
  query: ReturnType<typeof vi.fn>;
  queryWithMetadata: ReturnType<typeof vi.fn>;
  verify: ReturnType<typeof vi.fn>;
  request?: ReturnType<typeof vi.fn>;
  getDataset?: ReturnType<typeof vi.fn>;
};

function makeClient(overrides: Partial<FakeClient> = {}): FakeClient {
  return {
    registerSource: vi.fn(async () => makeRegistration()),
    resolve: vi.fn(async (payload: unknown) => ({ planner: "api", payload })),
    query: vi.fn(async (payload: unknown) => ({ result: 1, payload })),
    queryWithMetadata: vi.fn(async (payload: unknown) => ({ data: { payload }, metadata: {} })),
    verify: vi.fn(async (payload: unknown) => ({ valid: true, payload })),
    ...overrides,
  };
}

function apiRuntime(client: FakeClient): Runtime {
  return new Runtime({ mode: "api", apiKey: "de_test_key", client: client as never });
}

beforeEach(() => {
  delete process.env.ALGENTA_API_KEY;
  delete process.env.DE_API_KEY;
  delete process.env.ALGENTA_DEPLOYMENT_MODE;
  delete process.env.ALGENTA_DISABLE_CLOUD;
});

afterEach(() => {
  for (const key of Object.keys(process.env)) {
    if (!(key in ORIGINAL_ENV)) delete process.env[key];
  }
  Object.assign(process.env, ORIGINAL_ENV);
});

describe("Runtime API registration bookkeeping", () => {
  it("remembers registrations by trimmed name and by dataset or source id", () => {
    const runtime = apiRuntime(makeClient());
    const byDataset = makeRegistration({ name: "  orders  ", dataset_id: " ds_1 ", source_id: null });
    const bySource = makeRegistration({ name: "", dataset_id: null, source_id: "src_2" });
    const anonymous = makeRegistration({ name: null, dataset_id: "", source_id: "  " });

    runtime.rememberApiRegistration(byDataset);
    runtime.rememberApiRegistration(bySource);
    runtime.rememberApiRegistration(anonymous);

    expect(runtime.apiRegistrationsByName.get("orders")).toBe(byDataset);
    expect(runtime.apiRegistrationsByDataset.get("ds_1")).toBe(byDataset);
    expect(runtime.apiRegistrationsByDataset.get("src_2")).toBe(bySource);
    expect(runtime.apiRegistrationsByName.size).toBe(1);
    expect(runtime.apiRegistrationsByDataset.size).toBe(2);

    expect(runtime.lookupApiRegistration({ dataset_id: " ds_1 " })).toBe(byDataset);
    // An unknown dataset id falls back to the source name.
    expect(runtime.lookupApiRegistration({ dataset_id: "nope", source_name: " orders " })).toBe(byDataset);
    expect(runtime.lookupApiRegistration({ source_name: "missing" })).toBeNull();
    expect(runtime.lookupApiRegistration({})).toBeNull();
  });

  it("hydrates an incomplete registration from getDataset and tolerates failures", async () => {
    const detail = {
      dataset: { name: "Orders (detail)", row_count: 400 },
      schema: { fields: ["revenue"] },
    };
    const getDataset = vi.fn<(datasetId: string) => Promise<unknown>>(async () => detail);
    const runtime = apiRuntime(makeClient({ getDataset }));

    const complete = makeRegistration();
    expect(await runtime.hydrateApiRegistration(complete)).toBe(complete);
    expect(getDataset).not.toHaveBeenCalled();

    const noId = makeRegistration({ dataset_id: null, source_id: null, row_count: null });
    expect(await runtime.hydrateApiRegistration(noId)).toBe(noId);

    const sparse: SourceRegistrationResponse = { status: "ready", dataset_id: "ds_orders" };
    expect(await runtime.hydrateApiRegistration(sparse)).toEqual({
      status: "ready",
      dataset_id: "ds_orders",
      name: "Orders (detail)",
      dataset_name: "Orders (detail)",
      row_count: 400,
      schema: { fields: ["revenue"] },
      source_schema: { fields: ["revenue"] },
    });
    expect(getDataset).toHaveBeenCalledWith("ds_orders");

    // Fields the registration already carries win over the dataset detail.
    const partial = makeRegistration({ row_count: null, schema: null });
    expect(await runtime.hydrateApiRegistration(partial)).toMatchObject({
      name: "orders",
      dataset_name: "orders",
      row_count: 400,
      schema: { fields: ["revenue"] },
      source_schema: { fields: ["revenue", "region", "order_date"] },
    });

    getDataset.mockResolvedValueOnce({ dataset: { name: "   " }, schema: "not-an-object" });
    expect(await runtime.hydrateApiRegistration(sparse)).toEqual({
      status: "ready",
      dataset_id: "ds_orders",
      name: null,
      dataset_name: null,
      row_count: null,
      schema: null,
      source_schema: null,
    });

    getDataset.mockRejectedValueOnce(new Error("boom"));
    expect(await runtime.hydrateApiRegistration(sparse)).toBe(sparse);
  });

  it("skips hydration when the client has no getDataset method", async () => {
    const runtime = apiRuntime(makeClient());
    const sparse: SourceRegistrationResponse = { status: "ready", dataset_id: "ds_orders" };
    expect(await runtime.hydrateApiRegistration(sparse)).toBe(sparse);
  });

  it("reads the schema revision from /v1/sources/<id> in preference order", async () => {
    const request = vi.fn();
    const runtime = apiRuntime(makeClient({ request }));
    const registration = makeRegistration();

    expect(await runtime.fetchApiSourceSchemaRevision(makeRegistration({ dataset_id: null, source_id: null }))).toBeNull();
    expect(request).not.toHaveBeenCalled();

    request.mockResolvedValueOnce({ entry: { source_schema_revision: " rev_entry " } });
    expect(await runtime.fetchApiSourceSchemaRevision(registration)).toBe("rev_entry");
    expect(request).toHaveBeenCalledWith("GET", "/v1/sources/ds_orders");

    request.mockResolvedValueOnce({ entry: { schema_revision: "rev_legacy" } });
    expect(await runtime.fetchApiSourceSchemaRevision(registration)).toBe("rev_legacy");

    request.mockResolvedValueOnce({ entry: { schema_revision: "" }, schema: { schema_revision: "rev_schema" } });
    expect(await runtime.fetchApiSourceSchemaRevision(registration)).toBe("rev_schema");

    request.mockResolvedValueOnce({ schema: { schema_revision: "rev_schema_only" } });
    expect(await runtime.fetchApiSourceSchemaRevision(registration)).toBe("rev_schema_only");

    request.mockResolvedValueOnce({ entry: {} });
    expect(await runtime.fetchApiSourceSchemaRevision(registration)).toBeNull();

    request.mockResolvedValueOnce({ entry: {}, schema: { schema_revision: 3 } });
    expect(await runtime.fetchApiSourceSchemaRevision(registration)).toBeNull();

    request.mockResolvedValueOnce("not-an-object");
    expect(await runtime.fetchApiSourceSchemaRevision(registration)).toBeNull();

    request.mockRejectedValueOnce(new Error("offline"));
    expect(await runtime.fetchApiSourceSchemaRevision(registration)).toBeNull();

    const noRequest = apiRuntime(makeClient());
    expect(await noRequest.fetchApiSourceSchemaRevision(registration)).toBeNull();
  });
});

describe("Runtime exact-spec resolve over the API transport", () => {
  it("answers locally when the registered schema names every requested column", async () => {
    const client = makeClient({
      request: vi.fn(async () => ({ entry: { source_schema_revision: "rev_live" } })),
    });
    const runtime = apiRuntime(client);
    await runtime.connect({ records: [{ revenue: 1 }] }, { name: "orders" });

    const response = await runtime.resolve({
      source_name: "orders",
      metric: "revenue",
      group_by: "region",
      aggregation: "avg",
      constraints: { max_join_hops: 2 },
      join_path: { edges: [] },
      filter: { time_filter: "this_month" },
      limit: 5,
      order: "asc",
    });

    expect(client.resolve).not.toHaveBeenCalled();
    expect(response).toMatchObject({
      resolved_plan: {
        source_name: "orders",
        metric_column: "revenue",
        aggregation: "avg",
        group_column: "region",
        join_path: { edges: [] },
        filter: { time_filter: "this_month" },
        limit: 5,
        order: "asc",
        constraints: { max_join_hops: 2, [RUNTIME_DATASET_SCOPE_KEY]: "ds_orders" },
        schema_revision: "rev_live",
      },
      confidence: 1,
      plan: [
        "Use exact source 'orders'.",
        "Use exact metric column 'revenue'.",
        "Group by exact column 'region'.",
      ],
      explanation: [
        "Using registered source 'orders' as an exact source.",
        "Using exact metric column 'revenue'.",
        "Using exact group column 'region'.",
      ],
      resolved_column: "revenue",
      resolved_role: "measure",
      resolved_source: "orders",
      candidates: [],
      source_scores: { orders: 1 },
      decision_path: "exact_spec",
      schema_revision: "rev_live",
      validated: true,
      deterministic_scope: "api_registered_source",
      confidence_source: "runtime_exact_spec",
      clarification_required: false,
      rejection_reason: null,
      source_set: ["orders"],
      join_path: [],
      planner_mode: "runtime_exact_spec",
    });
    expect(response.plan_hash).toMatch(/^[0-9a-f]{64}$/);
    expect(response.request_id).toBe(`runtime_exact_${response.intent_signature.slice(0, 12)}`);
  });

  it("falls back to the registration's own schema revision and keeps an explicit dataset scope", async () => {
    const client = makeClient({
      registerSource: vi.fn(async () =>
        makeRegistration({ planner_schema_revision: null, schema_revision: " rev_fallback " }),
      ),
    });
    const runtime = apiRuntime(client);
    await runtime.connect({ records: [{ revenue: 1 }] }, { name: "orders" });

    const response = await runtime.resolve({
      dataset_id: "ds_orders",
      metric_column: "revenue",
      group_column: "region",
      constraints: { [RUNTIME_DATASET_SCOPE_KEY]: "ds_explicit" },
    });

    expect(response.resolved_plan).toMatchObject({
      metric_column: "revenue",
      group_column: "region",
      aggregation: "sum",
      order: "desc",
      constraints: { [RUNTIME_DATASET_SCOPE_KEY]: "ds_explicit" },
      schema_revision: "rev_fallback",
    });
    expect(response.resolved_plan).not.toHaveProperty("limit");
    expect(response.resolved_plan).not.toHaveProperty("join_path");
    expect(response.resolved_plan).not.toHaveProperty("filter");
    expect(client.resolve).not.toHaveBeenCalled();
  });

  it("accepts a single-element group_by list and omits the group when none is requested", async () => {
    const runtime = apiRuntime(makeClient({
      registerSource: vi.fn(async () => makeRegistration({ planner_schema_revision: "rev_p" })),
    }));
    await runtime.connect({ records: [{ revenue: 1 }] }, { name: "orders" });

    const grouped = await runtime.resolve({ source_name: "orders", metric: "revenue", group_by: ["  ", "region"] });
    expect(grouped.resolved_plan?.group_column).toBe("region");

    const ungrouped = await runtime.resolve({ source_name: "orders", metric: "revenue", group_by: [] });
    expect(ungrouped.resolved_plan).not.toHaveProperty("group_column");
    expect(ungrouped.plan).toEqual([
      "Use exact source 'orders'.",
      "Use exact metric column 'revenue'.",
    ]);
  });

  it.each([
    ["no registration matches", { source_name: "unknown", metric: "revenue" }, {}],
    ["the registration has no resolvable source name", { dataset_id: "ds_orders", metric: "revenue" }, {
      name: null,
      dataset_name: null,
    }],
    ["the registration has no schema revision", { source_name: "orders", metric: "revenue" }, {
      planner_schema_revision: null,
      schema_revision: "   ",
    }],
    ["the registration exposes no fields", { source_name: "orders", metric: "revenue" }, {
      source_schema: { fields: [] },
      schema: null,
    }],
    ["the metric is not a registered column", { source_name: "orders", metric: "margin" }, {}],
    ["group_by names an unknown column", { source_name: "orders", metric: "revenue", group_by: "channel" }, {}],
    ["group_column names an unknown column", { source_name: "orders", metric: "revenue", group_column: "channel" }, {}],
    ["group_by lists several columns", { source_name: "orders", metric: "revenue", group_by: ["region", "order_date"] }, {}],
    ["group_by lists one unknown column", { source_name: "orders", metric: "revenue", group_by: ["channel"] }, {}],
  ] as Array<[string, Record<string, unknown>, Partial<SourceRegistrationResponse>]>)(
    "defers to the API planner when %s",
    async (_label, request, registrationOverrides) => {
      const client = makeClient({
        registerSource: vi.fn(async () => makeRegistration(registrationOverrides)),
      });
      const runtime = apiRuntime(client);
      await runtime.connect({ records: [{ revenue: 1 }] }, { name: "orders" });

      const response = await runtime.resolve(request);

      expect(client.resolve).toHaveBeenCalledTimes(1);
      expect(response).toMatchObject({ planner: "api" });
    },
  );

  it("resolves the registered source by its canonical schema source name", async () => {
    const runtime = apiRuntime(makeClient({
      registerSource: vi.fn(async () =>
        makeRegistration({
          name: "orders",
          source_schema: { source: " canonical_orders ", fields: ["revenue"] },
        }),
      ),
    }));
    await runtime.connect({ records: [{ revenue: 1 }] }, { name: "orders" });
    const response = await runtime.resolve({ source_name: "orders", metric: "revenue" });
    expect(response.resolved_source).toBe("canonical_orders");
    expect(response.source_scores).toEqual({ canonical_orders: 1 });
  });

  it("exposes the exact-field helpers", () => {
    const runtime = apiRuntime(makeClient());
    const fields = new Set(["revenue", "region"]);
    expect(runtime.exactResolveMetricField({ metric_column: "revenue" }, fields)).toBe("revenue");
    expect(runtime.exactResolveMetricField({ metric: "revenue" }, fields)).toBe("revenue");
    expect(runtime.exactResolveMetricField({ metric: { hint: "revenue" } }, fields)).toBeNull();
    expect(runtime.exactResolveGroupField({}, fields)).toBeNull();
    expect(runtime.exactResolveGroupField({ group_by: 42 }, fields)).toBeNull();
    expect(runtime.exactResolveGroupField({ group_by: "region" }, fields)).toBe("region");
    expect(runtime.exactResolveGroupField({ group_by: "channel" }, fields)).toBeUndefined();
  });
});

describe("Runtime API payload coercion", () => {
  it("coerceApiResolvePayload maps the structured request onto the planner contract", () => {
    const runtime = apiRuntime(makeClient());

    expect(
      runtime.coerceApiResolvePayload({
        source_name: " orders ",
        metric: " revenue ",
        group_by: "region",
        metric_column: "revenue",
        resolved_plan: { stale: true },
      }),
    ).toEqual({
      preferred_source: "orders",
      allow_org_scope: true,
      metric: { role: "metric", hint: "revenue" },
      group_by: ["region"],
    });

    // Explicit planner fields are never overridden; group_column feeds group_by only when absent.
    expect(
      runtime.coerceApiResolvePayload({
        source_name: "orders",
        preferred_source: "warehouse",
        allow_org_scope: false,
        metric: { role: "metric", hint: "gmv" },
        group_column: " region ",
      }),
    ).toEqual({
      preferred_source: "warehouse",
      allow_org_scope: false,
      metric: { role: "metric", hint: "gmv" },
      group_by: ["region"],
    });

    expect(
      runtime.coerceApiResolvePayload({ metric: "revenue", group_by: ["a", "b"], group_column: "ignored" }),
    ).toEqual({ metric: { role: "metric", hint: "revenue" }, group_by: ["a", "b"] });
    expect(runtime.coerceApiResolvePayload({ metric: "revenue", group_column: "  " })).toEqual({
      metric: { role: "metric", hint: "revenue" },
    });
  });

  it("coerceApiQueryPayload prefers overrides, then resolved plans, then bare plans", () => {
    const runtime = apiRuntime(makeClient());
    const plan = makePlan({
      constraints: { [RUNTIME_DATASET_SCOPE_KEY]: " ds_scope ", max_join_hops: 2 },
    });

    expect(runtime.coerceApiQueryPayload({ resolved_plan: plan }, { raw: "override" })).toEqual({
      raw: "override",
    });

    const fromResponse = runtime.coerceApiQueryPayload({ resolved_plan: plan, confidence: 1 }, {});
    expect(fromResponse).toEqual({
      dataset_id: "ds_scope",
      resolved_plan: { ...plan, constraints: { max_join_hops: 2 } },
    });
    // The caller's plan object is not mutated.
    expect(plan.constraints).toEqual({ [RUNTIME_DATASET_SCOPE_KEY]: " ds_scope ", max_join_hops: 2 });

    expect(runtime.coerceApiQueryPayload(plan, {})).toEqual({
      dataset_id: "ds_scope",
      resolved_plan: { ...plan, constraints: { max_join_hops: 2 } },
    });

    expect(runtime.coerceApiQueryPayload({ metric: "revenue" }, {})).toEqual({ metric: "revenue" });

    expect(() => runtime.coerceApiQueryPayload({ resolved_plan: null }, {})).toThrow(
      RuntimeValidationError,
    );
    expect(() => runtime.coerceApiQueryPayload({ resolved_plan: null }, {})).toThrow(
      "requires an executable plan",
    );
  });

  it("extractRuntimeDatasetScope leaves unrelated shapes alone and keeps an explicit dataset_id", () => {
    const runtime = apiRuntime(makeClient());

    const noPlan = { dataset_id: "ds_1" };
    expect(runtime.extractRuntimeDatasetScope(noPlan)).toBe(noPlan);
    expect(runtime.extractRuntimeDatasetScope({ resolved_plan: [1] })).toEqual({ resolved_plan: [1] });

    const noConstraints = runtime.extractRuntimeDatasetScope({
      resolved_plan: { source_name: "orders", constraints: "invalid" },
    });
    expect(noConstraints).toEqual({ resolved_plan: { source_name: "orders", constraints: "invalid" } });

    const explicit = runtime.extractRuntimeDatasetScope({
      dataset_id: "ds_explicit",
      resolved_plan: { constraints: { [RUNTIME_DATASET_SCOPE_KEY]: "ds_scope" } },
    });
    expect(explicit).toEqual({ dataset_id: "ds_explicit", resolved_plan: { constraints: {} } });

    const blank = runtime.extractRuntimeDatasetScope({
      resolved_plan: { constraints: { [RUNTIME_DATASET_SCOPE_KEY]: "   " } },
    });
    expect(blank).toEqual({ resolved_plan: { constraints: {} } });
  });

  it("query, queryWithMetadata and verify forward the coerced payload to the client", async () => {
    const client = makeClient();
    const runtime = apiRuntime(client);
    const plan = makePlan({ constraints: { [RUNTIME_DATASET_SCOPE_KEY]: "ds_orders" } });
    const expected = { dataset_id: "ds_orders", resolved_plan: { ...plan, constraints: {} } };

    await runtime.query(plan);
    await runtime.queryWithMetadata({ resolved_plan: plan });
    await runtime.verify(plan, { override: true });

    expect(client.query).toHaveBeenCalledWith(expected);
    expect(client.queryWithMetadata).toHaveBeenCalledWith(expected);
    expect(client.verify).toHaveBeenCalledWith({ override: true });
  });
});

describe("Runtime.queryWithMetadata in local mode", () => {
  it("wraps the local query result with request id and latency metadata", async () => {
    const runtime = new Runtime({ mode: "local" });
    await runtime.connect([{ revenue: 10 }, { revenue: 5 }], { name: "orders" });
    const plan = await runtime.resolve({ source_name: "orders", metric: "revenue" });

    const response = await runtime.queryWithMetadata(plan);

    expect(response.data.result).toBe(15);
    expect(response.metadata).toEqual({
      request_id: response.data.request_id,
      latency_ms: response.data.latency_ms,
    });
  });
});
