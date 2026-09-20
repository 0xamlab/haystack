// SPDX-License-Identifier: Apache-2.0
/**
 * Local-mode planning and execution branches in
 * _runtime_class_methods_local_query.ts: source selection, the three resolve
 * outcomes (rejected / clarify / resolved), plan coercion, query filtering and
 * verification. In-memory records only, so every branch is deterministic.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  Runtime,
  RuntimeConfigurationError,
  RuntimeValidationError,
} from "./runtime.js";
import type { ResolvedPlan } from "./types.js";

const ORIGINAL_ENV = { ...process.env };

const ORDERS = [
  { revenue: 100, region: "north", order_date: "2026-01-05", flag: "yes" },
  { revenue: 50, region: "south", order_date: "2026-02-10", flag: "no" },
  { revenue: 25, region: "north", order_date: "2025-12-31", flag: "yes" },
];

async function connectedRuntime(records: Array<Record<string, unknown>> = ORDERS): Promise<Runtime> {
  const runtime = new Runtime({ mode: "local" });
  await runtime.connect(records, { name: "orders" });
  return runtime;
}

beforeEach(() => {
  delete process.env.ALGENTA_API_KEY;
  delete process.env.DE_API_KEY;
  delete process.env.ALGENTA_DEPLOYMENT_MODE;
  delete process.env.ALGENTA_DISABLE_CLOUD;
  delete process.env.ALGENTA_REQUIRE_LOCAL_LICENSE;
});

afterEach(() => {
  vi.useRealTimers();
  for (const key of Object.keys(process.env)) {
    if (!(key in ORIGINAL_ENV)) delete process.env[key];
  }
  Object.assign(process.env, ORIGINAL_ENV);
});

describe("Runtime local source selection", () => {
  it("requires a connected source before resolving", async () => {
    const runtime = new Runtime({ mode: "local" });
    const failure = runtime.resolve({ metric: "revenue" });
    await expect(failure).rejects.toBeInstanceOf(RuntimeConfigurationError);
    await expect(failure).rejects.toMatchObject({
      code: "source_required",
      message: expect.stringContaining("Call Runtime.connect(...)"),
    });
  });

  it("requires source_name or dataset_id once several sources are connected", async () => {
    const runtime = await connectedRuntime();
    await runtime.connect([{ cost: 3 }], { name: "costs" });

    const failure = runtime.resolve({ metric: "revenue" });
    await expect(failure).rejects.toBeInstanceOf(RuntimeValidationError);
    await expect(failure).rejects.toMatchObject({
      code: "source_required",
      message: expect.stringContaining("Multiple local sources"),
      details: { available: ["costs", "orders"] },
    });
  });

  it("selects by dataset_id and rejects unknown sources with the available list", async () => {
    const runtime = await connectedRuntime();
    const registration = await runtime.connect([{ cost: 3 }], { name: "costs" });

    const resolved = await runtime.resolve({ dataset_id: registration.dataset_id, metric: "cost" });
    expect(resolved.resolved_source).toBe("costs");

    await expect(runtime.resolve({ source_name: "nope", metric: "revenue" })).rejects.toMatchObject({
      code: "unknown_source",
      details: { requested: "nope", available: ["costs", "orders"] },
    });
  });
});

describe("Runtime local resolve outcomes", () => {
  it("requires a structured metric", async () => {
    const runtime = await connectedRuntime();
    await expect(runtime.resolve({ source_name: "orders" })).rejects.toMatchObject({
      code: "metric_required",
      message: expect.stringContaining("structured metric"),
      details: { request: { source_name: "orders" } },
    });
  });

  it("rejects when no numeric field exists or the best match is too weak", async () => {
    const textOnly = await connectedRuntime([{ region: "north", note: "x" }]);
    const noNumeric = await textOnly.resolve({ metric: "revenue" });
    expect(noNumeric).toMatchObject({
      resolved_plan: null,
      confidence: 0,
      validated: false,
      clarification_required: false,
      rejection_reason: "schema_unresolved",
      explanation: ["No numeric field matched metric 'revenue'."],
      candidates: [],
      decision_path: "planner_hint",
      plan_hash: null,
    });
    expect(noNumeric.request_id).toBe(`local_${noNumeric.intent_signature.slice(0, 12)}`);

    const runtime = await connectedRuntime();
    const weak = await runtime.resolve({ source_name: "orders", metric: "headcount" });
    expect(weak.rejection_reason).toBe("schema_unresolved");
    expect(weak.explanation[0]).toMatch(/scored below the 0\.70 threshold/);
    expect(weak.candidates.map(candidate => candidate.column)).toEqual(["revenue"]);
    expect(weak.candidates[0]).toMatchObject({
      source: "orders",
      role: "measure",
      notes: ["schema similarity"],
    });
  });

  it("asks for clarification when two metric columns tie", async () => {
    const runtime = await connectedRuntime([
      { revenue_net: 1, revenue_gross: 2, region: "north" },
    ]);
    const response = await runtime.resolve({ source_name: "orders", metric: "revenue" });
    expect(response).toMatchObject({
      resolved_plan: null,
      confidence: 0.75,
      validated: false,
      clarification_required: true,
      rejection_reason: null,
      explanation: ["Metric mapping for 'revenue' is not decisive enough for execution."],
    });
    expect(response.candidates.map(candidate => candidate.column)).toEqual([
      "revenue_gross",
      "revenue_net",
    ]);
  });

  it("resolves canonical metric synonyms with a planner_hint decision path", async () => {
    const runtime = await connectedRuntime();
    const response = await runtime.resolve({
      source_name: "orders",
      metric: "sales",
      aggregation: "average",
      limit: 2,
      order: "asc",
      filter: { time_filter: "this_year" },
      constraints: { note: "kept" },
    });
    expect(response).toMatchObject({
      decision_path: "planner_hint",
      confidence: 1,
      validated: true,
      resolved_plan: {
        source_name: "orders",
        metric_column: "revenue",
        aggregation: "avg",
        group_column: null,
        join_path: null,
        filter: { time_filter: "this_year" },
        limit: 2,
        order: "asc",
        constraints: { note: "kept" },
      },
      plan: ["Use source 'orders'.", "Aggregate 'revenue' with 'avg'."],
      explanation: ["Resolved metric 'sales' to 'revenue'."],
    });
    expect(response.candidates[0].notes).toContain("canonical synonym match");
  });

  it("covers every group_by outcome", async () => {
    const runtime = await connectedRuntime([
      { revenue: 10, region_name: "north", region_code: "N", zone: "a" },
    ]);

    const missing = await runtime.resolve({ source_name: "orders", metric: "revenue", group_by: "warehouse" });
    // Nothing matches, so the alphabetical first field is reported as the (weak) top match.
    expect(missing).toMatchObject({
      rejection_reason: "schema_unresolved",
      explanation: ["Top group_by match 'region_code' scored below the 0.70 threshold."],
    });
    expect(missing.candidates.filter(candidate => candidate.role === "dimension")).toHaveLength(4);

    const ambiguous = await runtime.resolve({ source_name: "orders", metric: "revenue", group_by: "region" });
    // region_name and region_code both substring-match at 0.9, so the gap is zero.
    expect(ambiguous).toMatchObject({
      clarification_required: true,
      explanation: ["Group_by mapping for 'region' is not decisive enough for execution."],
    });

    const exact = await runtime.resolve({ source_name: "orders", metric: "revenue", group_by: "zone" });
    expect(exact).toMatchObject({
      decision_path: "exact_spec",
      resolved_plan: { group_column: "zone" },
      plan: ["Use source 'orders'.", "Aggregate 'revenue' with 'sum'.", "Group by 'zone'."],
      explanation: ["Resolved metric 'revenue' to 'revenue'.", "Resolved group_by 'zone' to 'zone'."],
    });
    // Whitespace-only group_by is treated as absent.
    const blank = await runtime.resolve({ source_name: "orders", metric: "revenue", group_by: "   " });
    expect(blank.resolved_plan?.group_column).toBeNull();
  });

  it("rejects a group_by that matches no field at all", async () => {
    const runtime = new Runtime({ mode: "local" });
    await runtime.connect([{ revenue: 1 }], { name: "solo" });
    const response = await runtime.resolve({ metric: "revenue", group_by: "region" });
    // The only field is numeric-and-metric, so nothing scores above the floor.
    expect(response.rejection_reason).toBe("schema_unresolved");
    expect(response.explanation[0]).toMatch(/group_by/);
  });
});

describe("Runtime local plan coercion and execution", () => {
  it("query requires an executable plan and a connected, unchanged source", async () => {
    const runtime = await connectedRuntime();
    const rejected = await runtime.resolve({ source_name: "orders", metric: "headcount" });

    await expect(runtime.query(rejected)).rejects.toMatchObject({
      code: "query_requires_executable_plan",
    });

    const plan = await runtime.resolve({ source_name: "orders", metric: "revenue" });
    const detached = { ...(plan.resolved_plan as ResolvedPlan), source_name: "elsewhere" };
    await expect(runtime.query(detached)).rejects.toMatchObject({
      code: "unknown_source",
      details: { source_name: "elsewhere" },
    });

    const stale = { ...(plan.resolved_plan as ResolvedPlan), schema_revision: "old" };
    await expect(runtime.query(stale)).rejects.toMatchObject({
      code: "schema_revision_mismatch",
      details: { expected: plan.schema_revision, received: "old" },
    });

    // Overrides replace the request entirely.
    const overridden = await runtime.query(
      { resolved_plan: null },
      plan.resolved_plan as unknown as Record<string, unknown>,
    );
    expect(overridden.result).toBe(175);
  });

  it("applies time and condition filters and reports each step in the plan", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-02-20T12:00:00Z"));
    const runtime = await connectedRuntime();
    const plan = (await runtime.resolve({ source_name: "orders", metric: "revenue", group_by: "region" }))
      .resolved_plan as ResolvedPlan;

    const response = await runtime.query({
      ...plan,
      filter: {
        time_filter: " this_year ",
        conditions: [{ column: "flag", op: "eq", value: "yes" }],
      },
      limit: null,
    });

    expect(response).toMatchObject({
      result_type: "table",
      result: [{ region: "north", revenue: 100, count: 1 }],
      row_count: 1,
      plan: [
        "Use source 'orders'.",
        "Aggregate 'revenue' with 'sum'.",
        "Group by 'region'.",
        "Time filter 'this_year' on 'order_date': 3->2 rows.",
        "Filter 'flag eq \"yes\"': 2->1 rows.",
      ],
      exact_spec: true,
      decision_path: "exact_spec",
      confidence_source: "local_exact_execution",
    });
    expect(response.query_id).toBe(response.request_id);
  });

  it("skips the time filter when no time-like field exists and returns null scalars for empty sets", async () => {
    // V8 parses most plain digit strings as dates ("5" is May 2001), so a metric value
    // in exponent notation is the one numeric spelling that leaves no time-like column.
    const runtime = await connectedRuntime([{ revenue: 1e21, region: "north" }]);
    const plan = (
      await runtime.resolve({ source_name: "orders", metric: "revenue", aggregation: "avg" })
    ).resolved_plan as ResolvedPlan;

    // The condition filters every row out: the average of nothing is null, not 0.
    const response = await runtime.query({
      ...plan,
      filter: {
        time_filter: "last_year",
        conditions: [{ column: "region", op: "eq", value: "nowhere" }],
      },
    });

    expect(response.result).toBeNull();
    expect(response.result_type).toBe("scalar");
    expect(response.row_count).toBe(0);
    expect(response.plan).toContain("No time-like field found. time_filter skipped.");
  });

  it("hosted local limits require an explicit API key", async () => {
    const runtime = new Runtime({ mode: "local", enforceLimits: true });
    await runtime.connect(ORDERS, { name: "orders" });
    const plan = await runtime.resolve({ source_name: "orders", metric: "revenue" });

    const failure = runtime.query(plan);
    await expect(failure).rejects.toBeInstanceOf(RuntimeConfigurationError);
    await expect(failure).rejects.toMatchObject({
      code: "api_key_required",
      message: expect.stringContaining("Hosted local mode requires an API key"),
    });
    expect(runtime.usesHostedLocalLimits()).toBe(true);
  });

  it("private profiles never apply hosted local limits", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    const runtime = new Runtime({ mode: "local", enforceLimits: true, apiKey: "de_test_key" });
    expect(runtime.usesHostedLocalLimits()).toBe(false);
  });
});

describe("Runtime local verify", () => {
  it("verifies an executable plan and lists every mismatch otherwise", async () => {
    const runtime = await connectedRuntime();
    const plan = (await runtime.resolve({ source_name: "orders", metric: "revenue", group_by: "region" }))
      .resolved_plan as ResolvedPlan;

    const valid = await runtime.verify(plan);
    expect(valid).toMatchObject({
      valid: true,
      verified: true,
      errors: [],
      suggestions: [],
      resolved: { source_name: "orders", metric_column: "revenue", group_column: "region" },
      valid_dimensions: ["region"],
      valid_measures: ["revenue"],
      source_behavior: "local_registered_source",
      verification_mode: "local",
      rejection_reason: null,
      schema_revision: plan.schema_revision,
    });
    expect(valid.request_id).toBe(`local_verify_${String(valid.plan_hash).slice(0, 12)}`);

    const broken = await runtime.verify({
      ...plan,
      schema_revision: "old",
      metric_column: "margin",
      group_column: "warehouse",
      filter: { conditions: [{ column: "missing", op: "eq", value: 1 }] },
    });
    expect(broken).toMatchObject({
      valid: false,
      verified: false,
      errors: [
        "schema_revision mismatch",
        "Metric column 'margin' is missing.",
        "Group column 'warehouse' is missing.",
        "Filter column 'missing' is not present on source 'orders'.",
      ],
      suggestions: ["Reconnect the source or rerun resolve against the current schema."],
      rejection_reason: "plan_verification_failed",
      valid_dimensions: ["warehouse"],
    });

    const disconnected = await runtime.verify({ ...plan, source_name: "elsewhere", group_column: null });
    expect(disconnected.errors).toEqual(["Source 'elsewhere' is not connected."]);
    expect(disconnected.resolved).toEqual({
      source_name: "elsewhere",
      metric_column: "revenue",
      group_column: "",
    });
    expect(disconnected.valid_dimensions).toEqual([]);
  });

  it("lets non-runtime errors escape verify", async () => {
    const runtime = await connectedRuntime();
    // `null` is not a plan shape at all; the resulting TypeError is not swallowed.
    await expect(runtime.verify(null as never)).rejects.toBeInstanceOf(TypeError);
  });

  it("turns a non-executable plan into a failed verification instead of throwing", async () => {
    const runtime = await connectedRuntime();
    const rejected = await runtime.resolve({ source_name: "orders", metric: "headcount" });

    const response = await runtime.verify(rejected);

    expect(response).toEqual({
      valid: false,
      errors: ["Runtime.query() requires an executable plan."],
      suggestions: ["Run Runtime.resolve(...) again with a more explicit metric or source."],
      resolved: {},
      latency_ms: expect.any(Number),
      verified: false,
      verification_mode: "local",
      rejection_reason: "query_requires_executable_plan",
    });
  });
});
