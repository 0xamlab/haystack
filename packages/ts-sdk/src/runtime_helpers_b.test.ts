// SPDX-License-Identifier: Apache-2.0
// Unit tests for runtime helper module B: natural-language request parsing,
// aggregation canonicalization, typed-field inference, local filter resolution,
// named time ranges and source-registration schema helpers.
import { afterEach, describe, expect, it, vi } from "vitest";

import type { LocalRecord, LocalResolvedFilterCondition, LocalSource } from "./_runtime_constants.js";
import { RuntimeValidationError } from "./_runtime_errors.js";
import {
  applyLocalFilterConditions,
  booleanValue,
  buildExplainJoinPath,
  bundleFieldTokens,
  canonicalizeAggregation,
  dedupeStrings,
  fieldMatchScore,
  fieldOverlapScore,
  findLocalTimeField,
  inferTypedFields,
  isExactFieldMatch,
  isNullishFilterValue,
  isNumericField,
  mergeRequest,
  metricSynonymSet,
  numericValue,
  orderedFields,
  parseDateValue,
  parseRawText,
  preferredFilterValueType,
  registrationDatasetId,
  registrationFields,
  registrationResolvedSourceName,
  resolveAggregation,
  resolveLocalFilterColumn,
  resolveLocalFilterConditions,
  roundLatency,
  rowMatchesFilterCondition,
  sampleBooleanField,
  semanticScore,
  sourceSetFromRequest,
  timeRange,
  valuesEqual,
} from "./_runtime_helpers_b.js";
import type { SourceRegistrationResponse, TypedFieldType } from "./types.js";

const REGION_RECORDS: LocalRecord[] = [
  { region: "North", revenue: 120, order_date: "2026-03-01", is_active: true },
  { region: "South", revenue: 80, order_date: "2026-03-02", is_active: false },
  { region: "North", revenue: 40, order_date: "2026-03-03", is_active: "yes" },
];

afterEach(() => {
  vi.useRealTimers();
});

function makeSource(records: LocalRecord[], fields: string[] = orderedFields(records)): LocalSource {
  return { name: "orders", records, fields, schemaRevision: "rev-1", datasetId: "ds-1" };
}

function registration(fields: Record<string, unknown>): SourceRegistrationResponse {
  return fields as SourceRegistrationResponse;
}

function utcDay(year: number, month: number, day: number): Date {
  return new Date(Date.UTC(year, month - 1, day));
}

function expectValidationError(run: () => unknown, code: string, messageFragment: string): RuntimeValidationError {
  let caught: unknown;
  try {
    run();
  } catch (error) {
    caught = error;
  }
  expect(caught).toBeInstanceOf(RuntimeValidationError);
  const error = caught as RuntimeValidationError;
  expect(error.code).toBe(code);
  expect(error.message).toContain(messageFragment);
  return error;
}

describe("isExactFieldMatch and metricSynonymSet", () => {
  it("compares normalized text", () => {
    expect(isExactFieldMatch("Order_Date", "order date")).toBe(true);
    expect(isExactFieldMatch("order", "orders")).toBe(false);
  });

  it.each<[string, string[]]>([
    ["Revenue", ["revenue", "sales", "net sales", "income", "gmv"]],
    ["GMV", ["gmv", "revenue", "sales", "net sales", "income"]],
    ["count", ["count", "quantity", "qty", "units"]],
    ["headcount", ["headcount"]],
  ])("expands %j to its synonym family", (hint, expected) => {
    expect(metricSynonymSet(hint)).toEqual(new Set(expected));
  });
});

describe("parseRawText", () => {
  it.each<[string, Record<string, unknown>]>([
    ["average revenue by region", { aggregation: "avg", metric: "revenue", group_by: "region" }],
    // Keyword table order decides, not position in the sentence: "count" precedes "total",
    // and "count" is also a quantity synonym.
    ["the total count of orders", { aggregation: "count", metric: "quantity" }],
    ["maximum margin per store", { aggregation: "max", metric: "profit", group_by: "store" }],
    ["minimum spend grouped by channel", { aggregation: "min", metric: "cost", group_by: "channel" }],
    ["sum of units group by day", { aggregation: "sum", metric: "quantity", group_by: "day" }],
    ["mean income for each customer", { aggregation: "avg", metric: "revenue", group_by: "customer" }],
    ["  Show Sales  ", { metric: "revenue" }],
    ["show me everything", {}],
  ])("parses %j", (text, expected) => {
    expect(parseRawText(text)).toEqual(expected);
  });
});

describe("mergeRequest", () => {
  it("returns an empty request when nothing is provided", () => {
    expect(mergeRequest(undefined)).toEqual({});
  });

  it("fills only the keys raw_text implies that are still missing", () => {
    expect(mergeRequest({ raw_text: "total revenue by region", aggregation: "avg" })).toEqual({
      raw_text: "total revenue by region",
      aggregation: "avg",
      metric: "revenue",
      group_by: "region",
    });
  });

  it("lets overrides win over the base request", () => {
    expect(mergeRequest({ metric: "cost", limit: 1 }, { metric: "revenue" })).toEqual({ metric: "revenue", limit: 1 });
  });

  it("ignores a non-string raw_text", () => {
    expect(mergeRequest({ raw_text: 42 })).toEqual({ raw_text: 42 });
  });
});

describe("canonicalizeAggregation", () => {
  it.each<[string, string]>([
    ["sum", "sum"],
    ["total", "sum"],
    ["avg", "avg"],
    ["average", "avg"],
    ["mean", "avg"],
    ["count", "count"],
    ["min", "min"],
    ["minimum", "min"],
    ["max", "max"],
    ["maximum", "max"],
    ["  Mean ", "avg"],
  ])("maps %j to %j", (alias, canonical) => {
    expect(canonicalizeAggregation(alias)).toBe(canonical);
  });

  // Object.prototype names must not resolve through inherited properties.
  it.each([["median"], ["constructor"], ["toString"], ["__proto__"], ["hasOwnProperty"], [""]])(
    "rejects %j",
    value => {
      const error = expectValidationError(
        () => canonicalizeAggregation(value),
        "invalid_aggregation",
        `Unknown aggregation '${value}'. Supported: avg, count, max, min, sum.`,
      );
      expect(error.details).toEqual({ aggregation: value, supported: ["avg", "count", "max", "min", "sum"] });
    },
  );
});

describe("resolveAggregation", () => {
  it.each<[string, Record<string, unknown>, string]>([
    ["an explicit alias", { aggregation: "Total" }, "sum"],
    ["raw_text when the explicit value is blank", { aggregation: "  ", raw_text: "average revenue" }, "avg"],
    ["raw_text without an aggregation keyword", { raw_text: "revenue by region" }, "sum"],
    ["a non-string raw_text", { raw_text: 5 }, "sum"],
    ["an empty request", {}, "sum"],
  ])("resolves %s", (_label, request, expected) => {
    expect(resolveAggregation(request)).toBe(expected);
  });

  it("rejects an unknown explicit aggregation", () => {
    expectValidationError(() => resolveAggregation({ aggregation: "median" }), "invalid_aggregation", "median");
  });
});

describe("orderedFields and numericValue", () => {
  it("lists fields in first-seen order without duplicates", () => {
    expect(orderedFields([{ b: 1, a: 2 }, { a: 3, c: 4 }])).toEqual(["b", "a", "c"]);
    expect(orderedFields([])).toEqual([]);
  });

  it.each<[unknown, number | null]>([
    [5, 5],
    [-2.5, -2.5],
    [Number.NaN, null],
    [Number.POSITIVE_INFINITY, null],
    ["12.5", 12.5],
    [" 7 ", 7],
    ["1e3", 1000],
    ["  ", null],
    ["abc", null],
    [true, null],
    [null, null],
    [undefined, null],
  ])("numericValue(%j) is %j", (value, expected) => {
    expect(numericValue(value)).toBe(expected);
  });
});

describe("inferTypedFields", () => {
  it("takes the majority vote per field and ignores nulls", () => {
    const records: LocalRecord[] = [
      { n: 1, s: "a", d: "2026-01-05", b: true, mixed: 1, empty: null },
      { n: "2", s: "b", d: "2026-01-06T10:00:00Z", b: false, mixed: "x", empty: null },
      { n: null, s: null, d: null, b: null, mixed: "y", empty: undefined },
    ];
    expect(inferTypedFields(records, ["n", "s", "d", "b", "mixed", "empty", "missing"])).toEqual([
      { name: "n", type: "number" },
      { name: "s", type: "string" },
      { name: "d", type: "date" },
      { name: "b", type: "boolean" },
      { name: "mixed", type: "string" },
      { name: "empty", type: "unknown" },
      { name: "missing", type: "unknown" },
    ]);
  });

  it.each<[string, unknown[], TypedFieldType]>([
    ["number beats date", [1, "2026-01-01"], "number"],
    ["date beats string", ["2026-01-01", "abc"], "date"],
    ["string beats boolean", ["abc", true], "string"],
    ["boolean beats unknown", [true, {}], "boolean"],
  ])("breaks ties by precedence: %s", (_label, values, expected) => {
    expect(inferTypedFields(values.map(value => ({ f: value })), ["f"])).toEqual([{ name: "f", type: expected }]);
  });

  it("is unknown for an empty record set", () => {
    expect(inferTypedFields([], ["f"])).toEqual([{ name: "f", type: "unknown" }]);
  });

  it("samples only the first fifty records", () => {
    const records: LocalRecord[] = [
      ...Array.from({ length: 50 }, () => ({ f: "text" })),
      ...Array.from({ length: 60 }, () => ({ f: 1 })),
    ];
    expect(inferTypedFields(records, ["f"])).toEqual([{ name: "f", type: "string" }]);
  });
});

describe("booleanValue, isNullishFilterValue and valuesEqual", () => {
  it.each<[unknown, boolean | null]>([
    [true, true],
    [false, false],
    [1, true],
    [0, false],
    [2, null],
    ["yes", true],
    [" N ", false],
    ["maybe", null],
    ["", null],
    [null, null],
  ])("booleanValue(%j) is %j", (value, expected) => {
    expect(booleanValue(value)).toBe(expected);
  });

  it.each<[unknown, boolean]>([
    [null, true],
    [undefined, true],
    ["", true],
    ["  None ", true],
    ["null", true],
    ["NaN", true],
    ["x", false],
    [Number.NaN, true],
    [5, false],
    [true, false],
  ])("isNullishFilterValue(%j) is %j", (value, expected) => {
    expect(isNullishFilterValue(value)).toBe(expected);
  });

  it.each<[unknown, unknown, boolean]>([
    [true, "yes", true],
    ["1", true, true],
    [true, "no", false],
    [5, "5", true],
    ["2", 2, true],
    [5, "6", false],
    [null, "x", false],
    ["x", null, false],
    ["Apple ", "apple", true],
    ["a", "b", false],
  ])("valuesEqual(%j, %j) is %j", (rowValue, expected, result) => {
    expect(valuesEqual(rowValue, expected)).toBe(result);
  });
});

describe("parseDateValue", () => {
  it.each<[string, unknown, Date | null]>([
    ["a full timestamp truncated to its UTC day", "2026-03-15T10:20:30Z", utcDay(2026, 3, 15)],
    ["an offset timestamp resolved on the UTC calendar", "2026-03-15T23:30:00-05:00", utcDay(2026, 3, 16)],
    ["a plain date", "2026-03-15", utcDay(2026, 3, 15)],
    ["a year-month string", "2026-03", utcDay(2026, 3, 1)],
    // V8 parses "YYYY-MM" directly; only an out-of-range month reaches the manual fallback,
    // which lets Date.UTC roll the month over.
    ["a year-month string with an overflowing month", "2026-13", utcDay(2027, 1, 1)],
    ["garbage", "not a date", null],
    ["null", null, null],
    ["undefined", undefined, null],
    ["whitespace", "   ", null],
  ])("parses %s", (_label, value, expected) => {
    expect(parseDateValue(value)).toEqual(expected);
  });
});

describe("timeRange", () => {
  it("resolves named ranges relative to the current UTC day", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-15T12:00:00Z"));
    expect(timeRange("this_month")).toEqual({ start: utcDay(2026, 5, 1), end: utcDay(2026, 5, 15) });
    expect(timeRange("last_month")).toEqual({ start: utcDay(2026, 4, 1), end: utcDay(2026, 4, 30) });
    expect(timeRange("this_year")).toEqual({ start: utcDay(2026, 1, 1), end: utcDay(2026, 5, 15) });
    expect(timeRange("last_year")).toEqual({ start: utcDay(2025, 1, 1), end: utcDay(2025, 12, 31) });
    expect(timeRange("this_quarter")).toEqual({ start: utcDay(2026, 4, 1), end: utcDay(2026, 5, 15) });
    expect(timeRange("last_quarter")).toEqual({ start: utcDay(2026, 1, 1), end: utcDay(2026, 3, 31) });
    expect(timeRange("yesterday")).toBeNull();
  });

  it("wraps last_quarter and last_month into the previous year during January", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-20T00:30:00Z"));
    expect(timeRange("last_quarter")).toEqual({ start: utcDay(2025, 10, 1), end: utcDay(2025, 12, 31) });
    expect(timeRange("last_month")).toEqual({ start: utcDay(2025, 12, 1), end: utcDay(2025, 12, 31) });
  });
});

describe("sampleBooleanField", () => {
  it("accepts a field whose observed values are all boolean-like", () => {
    expect(sampleBooleanField(REGION_RECORDS, "is_active")).toBe(true);
  });

  it("rejects a field with any non-boolean value", () => {
    expect(sampleBooleanField(REGION_RECORDS, "region")).toBe(false);
  });

  it("rejects fields that are absent or only nullish", () => {
    expect(sampleBooleanField(REGION_RECORDS, "missing")).toBe(false);
    expect(sampleBooleanField([{ f: null }, { f: "" }], "f")).toBe(false);
  });

  it("samples only the first fifty records", () => {
    const records: LocalRecord[] = [...Array.from({ length: 50 }, () => ({ f: true })), { f: "nope" }];
    expect(sampleBooleanField(records, "f")).toBe(true);
  });
});

describe("fieldMatchScore", () => {
  it.each<[string, string, number, boolean]>([
    ["Order_Date", "order date", 1, true],
    ["order date", "order", 0.95, false],
    ["order", "order date", 0.95, false],
    ["net sales total", "sales", 0.9, false],
    ["sales", "net sales total", 0.9, false],
    ["store region", "region code", 0.5, false],
    ["abc", "xyz", 0, false],
    ["", "x", 0, false],
    ["x", "", 0, false],
  ])("scores (%j, %j) as %j", (field, hint, score, exact) => {
    expect(fieldMatchScore(field, hint)).toEqual({ score, exact });
  });
});

describe("preferredFilterValueType", () => {
  it.each<[Record<string, unknown>, "numeric" | "boolean" | null]>([
    [{ op: "gt" }, "numeric"],
    [{ op: "lte", value: "x" }, "numeric"],
    [{ op: "is_null" }, null],
    [{ op: "is_not_null", value: 1 }, null],
    [{ op: "in", values: [true, "no"] }, "boolean"],
    [{ op: "in", values: [5, "7"] }, "numeric"],
    [{ op: "in", values: ["a", 1] }, null],
    [{ op: "in", values: [] }, null],
    [{ op: "in" }, null],
    [{ op: "eq", value: "yes" }, "boolean"],
    [{ value: 5 }, "numeric"],
    [{ op: 7, value: true }, "boolean"],
    [{ op: "eq", value: "north" }, null],
  ])("classifies %j as %j", (condition, expected) => {
    expect(preferredFilterValueType(condition)).toBe(expected);
  });
});

describe("resolveLocalFilterColumn", () => {
  const source = makeSource(REGION_RECORDS);

  it("resolves an explicit column by normalized name", () => {
    expect(resolveLocalFilterColumn(source, { column: "Region", op: "eq", value: "North" })).toBe("region");
  });

  it("rejects an explicit column that is not on the source", () => {
    expectValidationError(
      () => resolveLocalFilterColumn(source, { column: "missing", op: "eq", value: 1 }),
      "invalid_filter_condition",
      "Filter column 'missing' is not present on source 'orders'.",
    );
  });

  it.each<[Record<string, unknown>]>([[{ op: "eq", value: 1 }], [{ column: "  ", dimension_hint: "  ", op: "eq" }]])(
    "requires a column or dimension_hint for %j",
    condition => {
      expectValidationError(
        () => resolveLocalFilterColumn(source, condition),
        "invalid_filter_condition",
        "Filter condition requires column or dimension_hint.",
      );
    },
  );

  it.each<[string, Record<string, unknown>, string]>([
    ["an exact string hint", { dimension_hint: "region", op: "eq", value: "North" }, "region"],
    ["a numeric comparison", { dimension_hint: "revenue", op: "gt", value: 100 }, "revenue"],
    ["a boolean equality", { dimension_hint: "is_active", op: "eq", value: true }, "is_active"],
    ["an in-list with mixed values", { dimension_hint: "region", op: "in", values: ["North", 1] }, "region"],
    ["a null check", { dimension_hint: "region", op: "is_null" }, "region"],
  ])("resolves %s through the dimension_hint", (_label, condition, expected) => {
    expect(resolveLocalFilterColumn(source, condition)).toBe(expected);
  });

  it("resolves a lexical match on a source without records", () => {
    expect(resolveLocalFilterColumn(makeSource([], ["region"]), { dimension_hint: "region", op: "eq", value: "x" })).toBe(
      "region",
    );
  });

  it("prefers the clearly better non-exact candidate", () => {
    const codes = makeSource([{ region_code_id: "a", store_code: "b" }]);
    expect(resolveLocalFilterColumn(codes, { dimension_hint: "region code", op: "eq", value: "a" })).toBe("region_code_id");
  });

  it("prefers the exact candidate when scores tie, whichever field is declared first", () => {
    // "flag" is exact but numeric (penalised for a boolean value); "is_flag_set" is a
    // substring match with no penalty. Both land on 0.9 and exactness decides.
    const records: LocalRecord[] = [
      { flag: 1, is_flag_set: "yes" },
      { flag: 2, is_flag_set: "maybe" },
    ];
    for (const fields of [["flag", "is_flag_set"], ["is_flag_set", "flag"]]) {
      const flags = makeSource(records, fields);
      expect(resolveLocalFilterColumn(flags, { dimension_hint: "flag", op: "eq", value: true })).toBe("flag");
    }
  });

  it("rejects a hint that resolves to nothing", () => {
    expectValidationError(
      () => resolveLocalFilterColumn(source, { dimension_hint: "zzz", op: "eq", value: 1 }),
      "invalid_filter_condition",
      "Filter dimension_hint 'zzz' did not resolve on source 'orders'.",
    );
  });

  it("rejects an ambiguous hint and lists the contenders", () => {
    const ambiguous = makeSource([{ sales_region: "N", store_region: "S", revenue: 1 }]);
    expectValidationError(
      () => resolveLocalFilterColumn(ambiguous, { dimension_hint: "region", op: "eq", value: "North" }),
      "invalid_filter_condition",
      "Filter dimension_hint 'region' is ambiguous on source 'orders': store_region, sales_region.",
    );
  });

  it("rejects a numeric comparison against a non-numeric column", () => {
    expectValidationError(
      () => resolveLocalFilterColumn(source, { dimension_hint: "region", op: "gt", value: 100 }),
      "invalid_filter_condition",
      "Filter column 'region' on source 'orders' is not numeric.",
    );
  });
});

describe("resolveLocalFilterConditions", () => {
  const source = makeSource(REGION_RECORDS);

  it.each<[string, unknown]>([
    ["null", null],
    ["a string", "region = North"],
    ["an object without conditions", {}],
    ["conditions that are not an array", { conditions: "x" }],
  ])("returns no conditions for %s", (_label, filter) => {
    expect(resolveLocalFilterConditions(source, filter)).toEqual([]);
  });

  it.each<[string, unknown, string]>([
    ["a scalar condition", 5, "Filter conditions must be objects."],
    ["a null condition", null, "Filter conditions must be objects."],
    ["a missing op", { column: "region" }, "Filter condition op is required."],
    ["an unsupported op", { column: "region", op: "between" }, "Unsupported filter operator 'between'."],
    ["in with value", { column: "region", op: "in", value: "x", values: ["x"] }, "filter condition op='in' does not accept value"],
    ["in without values", { column: "region", op: "in" }, "filter condition op='in' requires non-empty values"],
    ["in with empty values", { column: "region", op: "in", values: [] }, "filter condition op='in' requires non-empty values"],
    ["is_null with value", { column: "region", op: "is_null", value: 1 }, "filter condition null checks do not accept value or values"],
    ["is_not_null with values", { column: "region", op: "is_not_null", values: [] }, "filter condition null checks do not accept value or values"],
    ["eq with values", { column: "region", op: "eq", values: ["x"] }, "filter condition op='eq' does not accept values"],
    ["gt without value", { column: "revenue", op: "gt" }, "filter condition op='gt' requires value"],
    ["eq with null value", { column: "region", op: "eq", value: null }, "filter condition op='eq' requires value"],
  ])("rejects %s", (_label, condition, message) => {
    expectValidationError(
      () => resolveLocalFilterConditions(source, { conditions: [condition] }),
      "invalid_filter_condition",
      message,
    );
  });

  it("resolves well-formed conditions to their columns", () => {
    expect(
      resolveLocalFilterConditions(source, {
        conditions: [
          { op: "eq", column: "Region", value: "North" },
          { op: "in", dimension_hint: "region", values: ["North"] },
          { op: "is_null", column: "revenue" },
        ],
      }),
    ).toEqual([
      { column: "region", op: "eq", value: "North", values: undefined },
      { column: "region", op: "in", value: undefined, values: ["North"] },
      { column: "revenue", op: "is_null", value: undefined, values: undefined },
    ]);
  });
});

describe("rowMatchesFilterCondition", () => {
  const record: LocalRecord = { region: "North", revenue: 120, note: null };

  it.each<[string, LocalResolvedFilterCondition, boolean]>([
    ["eq matches case-insensitively", { column: "region", op: "eq", value: "north" }, true],
    ["eq rejects a different value", { column: "region", op: "eq", value: "south" }, false],
    ["in matches any listed value", { column: "region", op: "in", values: ["south", "NORTH"] }, true],
    ["in without values never matches", { column: "region", op: "in" }, false],
    ["gt above the bound", { column: "revenue", op: "gt", value: 100 }, true],
    ["gt with a non-numeric bound", { column: "revenue", op: "gt", value: "abc" }, false],
    ["gt on a non-numeric row value", { column: "region", op: "gt", value: 1 }, false],
    ["gte at the bound", { column: "revenue", op: "gte", value: "120" }, true],
    ["lt at the bound", { column: "revenue", op: "lt", value: 120 }, false],
    ["lte at the bound", { column: "revenue", op: "lte", value: 120 }, true],
    ["is_null on a null value", { column: "note", op: "is_null" }, true],
    ["is_null on a present value", { column: "revenue", op: "is_null" }, false],
    ["is_not_null on a null value", { column: "note", op: "is_not_null" }, false],
    ["is_not_null on a missing column", { column: "missing", op: "is_not_null" }, false],
  ])("%s", (_label, condition, expected) => {
    expect(rowMatchesFilterCondition(record, condition)).toBe(expected);
  });

  it("rejects an operator the resolver never produces", () => {
    expectValidationError(
      () => rowMatchesFilterCondition(record, { column: "revenue", op: "between", value: 1 }),
      "invalid_filter_condition",
      "Unsupported filter operator 'between'.",
    );
  });
});

describe("applyLocalFilterConditions", () => {
  it("applies conditions in order and narrates each step", () => {
    const { records, planSteps } = applyLocalFilterConditions(REGION_RECORDS, [
      { column: "region", op: "eq", value: "North" },
      { column: "revenue", op: "gt", value: 50 },
      { column: "is_active", op: "is_not_null" },
      { column: "region", op: "in", values: ["North"] },
      { column: "region", op: "in" },
    ]);
    expect(records).toEqual([]);
    expect(planSteps).toEqual([
      "Filter 'region eq \"North\"': 3->2 rows.",
      "Filter 'revenue gt 50': 2->1 rows.",
      "Filter 'is_active is_not_null': 1->1 rows.",
      "Filter 'region in [\"North\"]': 1->1 rows.",
      "Filter 'region in []': 1->0 rows.",
    ]);
  });

  it("returns the surviving records", () => {
    const { records } = applyLocalFilterConditions(REGION_RECORDS, [
      { column: "region", op: "eq", value: "North" },
      { column: "revenue", op: "gt", value: 50 },
    ]);
    expect(records).toEqual([REGION_RECORDS[0]]);
  });

  it("is a no-op without conditions", () => {
    const result = applyLocalFilterConditions(REGION_RECORDS, []);
    expect(result.records).toBe(REGION_RECORDS);
    expect(result.planSteps).toEqual([]);
  });
});

describe("findLocalTimeField", () => {
  it("breaks a parse-count tie with the field-name cue", () => {
    const records: LocalRecord[] = [
      { created: "2026-03-01", order_date: "2026-03-01", region: "North" },
      { created: "2026-03-02", order_date: "2026-03-02", region: "South" },
    ];
    expect(findLocalTimeField(makeSource(records))).toBe("order_date");
  });

  it("prefers the field with more parseable values over a cue", () => {
    const records: LocalRecord[] = [
      { when: "2026-03-01", order_date: "2026-03-01" },
      { when: "2026-03-02", order_date: "garbage" },
      { when: "2026-03-03", order_date: "garbage" },
    ];
    expect(findLocalTimeField(makeSource(records))).toBe("when");
  });

  it("returns null when no field parses as a date", () => {
    expect(findLocalTimeField(makeSource(REGION_RECORDS, ["region"]))).toBeNull();
  });
});

describe("isNumericField", () => {
  it.each<[string, LocalRecord[], string, boolean]>([
    ["all numeric", REGION_RECORDS, "revenue", true],
    ["a non-numeric value", REGION_RECORDS, "region", false],
    ["an absent field", REGION_RECORDS, "missing", false],
    ["a field present on some records", [{ a: 1 }, { b: 2 }], "a", true],
  ])("%s", (_label, records, field, expected) => {
    expect(isNumericField(field, records)).toBe(expected);
  });
});

describe("semanticScore", () => {
  it.each<[string, string, number, string[]]>([
    ["Revenue", "revenue", 1, ["exact field match"]],
    ["store region", "region", 0.9, ["token overlap", "substring match"]],
    ["region of store", "store region", 0.6667, ["token overlap"]],
    ["subregion", "region", 0.9, ["schema similarity", "substring match"]],
    ["abc", "xyz", 0, ["schema similarity"]],
    ["", "x", 0, []],
    ["x", "", 0, []],
  ])("scores (%j, %j)", (field, hint, score, reasons) => {
    expect(semanticScore(field, hint)).toEqual({ score, reasons });
  });
});

describe("dedupeStrings, sourceSetFromRequest and buildExplainJoinPath", () => {
  it("dedupes trimmed non-empty strings in order", () => {
    expect(dedupeStrings([" a ", "a", "", "b", "  "])).toEqual(["a", "b"]);
  });

  it.each<[Record<string, unknown>, string[]]>([
    [{ source_name: "a", join_source_name: "b" }, ["a", "b"]],
    [{ source_name: "a", join_source_name: "a" }, ["a"]],
    [{ join_source_name: "b" }, ["b"]],
    [{ source_name: 5 }, []],
    [{}, []],
  ])("collects the source set from %j", (request, expected) => {
    expect(sourceSetFromRequest(request)).toEqual(expected);
  });

  it("chains adjacent sources into join steps", () => {
    expect(buildExplainJoinPath([])).toEqual([]);
    expect(buildExplainJoinPath(["a"])).toEqual([]);
    expect(buildExplainJoinPath(["a", "b", "c"])).toEqual([
      { left_source: "a", right_source: "b" },
      { left_source: "b", right_source: "c" },
    ]);
  });
});

describe("roundLatency", () => {
  it("measures elapsed milliseconds from a start timestamp", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-15T12:00:00Z"));
    expect(roundLatency(Date.now() - 12)).toBe(12);
    expect(roundLatency(Date.now())).toBe(0);
  });
});

describe("registrationFields", () => {
  it.each<[string, Record<string, unknown>, string[]]>([
    ["source_schema.fields keeps non-blank strings", { source_schema: { fields: ["a", "", 3, " b"] } }, ["a", " b"]],
    ["schema.columns[].name keeps non-blank names", { schema: { columns: [{ name: "a" }, { name: "  " }, { name: 4 }, null, "x", { other: 1 }] } }, ["a"]],
    ["source_schema wins over schema", { source_schema: { fields: ["a"] }, schema: { fields: ["b"] } }, ["a"]],
    ["a null source_schema falls back to schema", { source_schema: null, schema: { fields: ["b"] } }, ["b"]],
    ["non-array fields and missing columns", { schema: { fields: "nope" } }, []],
    ["non-array columns", { schema: { columns: "nope" } }, []],
    ["no schema at all", {}, []],
  ])("%s", (_label, fields, expected) => {
    expect(registrationFields(registration(fields))).toEqual(expected);
  });
});

describe("registrationResolvedSourceName and registrationDatasetId", () => {
  it.each<[Record<string, unknown>, string | null]>([
    [{ source_schema: { source: " canonical " }, name: "ignored" }, "canonical"],
    [{ schema: { source: "  " }, name: " nm " }, "nm"],
    [{ dataset_name: " ds " }, "ds"],
    [{ name: "  ", dataset_name: null }, null],
    [{}, null],
  ])("resolves the source name of %j", (fields, expected) => {
    expect(registrationResolvedSourceName(registration(fields))).toBe(expected);
  });

  it.each<[Record<string, unknown>, string | null]>([
    [{ dataset_id: " d ", source_id: "s" }, "d"],
    [{ dataset_id: "  ", source_id: " s " }, "s"],
    [{ source_id: 5 }, null],
    [{}, null],
  ])("resolves the dataset id of %j", (fields, expected) => {
    expect(registrationDatasetId(registration(fields))).toBe(expected);
  });
});

describe("bundleFieldTokens and fieldOverlapScore", () => {
  it("tokenizes the base header name", () => {
    expect(bundleFieldTokens("Order_ID__2")).toEqual(new Set(["order", "id"]));
    expect(bundleFieldTokens("   ")).toEqual(new Set());
  });

  it.each<[string, string, number]>([
    ["order id", "Order_ID__2", 1],
    ["order id", "customer id", 0.5],
    ["a b c", "a", 1],
    ["alpha", "beta", 0],
    ["", "x", 0],
    ["x", "", 0],
  ])("scores (%j, %j) as %j", (left, right, expected) => {
    expect(fieldOverlapScore(left, right)).toBe(expected);
  });
});
