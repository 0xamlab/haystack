// SPDX-License-Identifier: Apache-2.0
// Regression guard for the cross-language query-plane parity semantics
// (restored after the graduation regression): alias canonicalization, strict
// aggregation (no silent sum), count-carrying rows, and sha256 plan hashes.
import { describe, expect, it } from "vitest";

import {
  aggregateValues,
  exactPlanHash,
  executePlan,
} from "./_runtime_helpers_d.js";
import { stripNullEntries } from "./_runtime_helpers_a.js";
import {
  CANONICAL_AGGREGATIONS,
  canonicalizeAggregation,
  resolveAggregation,
} from "./_runtime_helpers_b.js";
import { RuntimeValidationError } from "./_runtime_errors.js";
import type { ResolvedPlan } from "./_runtime_helpers_d.js";

describe("aggregation canonicalization (Python parity)", () => {
  it("maps aliases to the canonical five", () => {
    expect(canonicalizeAggregation("mean")).toBe("avg");
    expect(canonicalizeAggregation("average")).toBe("avg");
    expect(canonicalizeAggregation("AVG")).toBe("avg");
    expect(canonicalizeAggregation("total")).toBe("sum");
    expect(canonicalizeAggregation("minimum")).toBe("min");
    expect(canonicalizeAggregation("maximum")).toBe("max");
    for (const canonical of CANONICAL_AGGREGATIONS) {
      expect(canonicalizeAggregation(canonical)).toBe(canonical);
    }
  });

  it("rejects unknown aggregations instead of silently summing", () => {
    expect(() => canonicalizeAggregation("totl")).toThrow(RuntimeValidationError);
    expect(() => resolveAggregation({ aggregation: "median" })).toThrow(RuntimeValidationError);
  });

  it("resolveAggregation canonicalizes explicit spellings", () => {
    expect(resolveAggregation({ aggregation: "mean" })).toBe("avg");
    expect(resolveAggregation({ aggregation: " sum " })).toBe("sum");
    expect(resolveAggregation({})).toBe("sum");
  });
});

describe("strict aggregation semantics (Python _agg parity)", () => {
  it("avg is the mean at full precision", () => {
    const mean = (100.5 + 430 + 250) / 3;
    expect(aggregateValues([100.5, 430, 250], "avg")).toBe(mean);
    expect(aggregateValues([100.5, 430, 250], "mean")).toBe(mean);
  });

  it("empty avg/min/max is null, empty sum is 0, count counts admitted values", () => {
    expect(aggregateValues([], "avg")).toBeNull();
    expect(aggregateValues([], "min")).toBeNull();
    expect(aggregateValues([], "max")).toBeNull();
    expect(aggregateValues([], "sum")).toBe(0);
    expect(aggregateValues([], "count")).toBe(0);
    expect(aggregateValues([2, 4], "count")).toBe(2);
  });
});

describe("executePlan rows carry counts (Python parity)", () => {
  const records = [
    { region: "east", revenue: 100.5 },
    { region: "east", revenue: 430 },
    { region: "west", revenue: 250 },
  ];

  it("scalar rows include the admitted-value count", () => {
    const rows = executePlan(records, "revenue", undefined, "sum", 100);
    expect(rows).toEqual([{ revenue: 780.5, count: 3 }]);
  });

  it("grouped rows include counts and sort null-metric rows last", () => {
    const rows = executePlan(records, "revenue", "region", "sum", 100);
    expect(rows).toEqual([
      { region: "east", revenue: 530.5, count: 2 },
      { region: "west", revenue: 250, count: 1 },
    ]);
  });
});

describe("plan hash is sha256-shaped and null-stripped (Python parity)", () => {
  const plan: ResolvedPlan = {
    source_name: "orders",
    metric_column: "revenue",
    aggregation: "sum",
    group_column: null,
    join_path: null,
    filter: null,
    limit: null,
    order: "desc",
    constraints: {},
    schema_revision: "rev",
  } as unknown as ResolvedPlan;

  it("is 64 lowercase hex chars (sha256), stable across calls", () => {
    const first = exactPlanHash(plan);
    expect(first).toMatch(/^[0-9a-f]{64}$/);
    expect(exactPlanHash(plan)).toBe(first);
  });

  it("null-stripping makes absent and null keys hash equally", () => {
    expect(stripNullEntries({ a: 1, b: null, c: { d: null, e: 2 } })).toEqual({ a: 1, c: { e: 2 } });
    const withoutNulls: ResolvedPlan = {
      source_name: "orders",
      metric_column: "revenue",
      aggregation: "sum",
      order: "desc",
      constraints: {},
      schema_revision: "rev",
    } as unknown as ResolvedPlan;
    expect(exactPlanHash(withoutNulls)).toBe(exactPlanHash(plan));
  });
});
