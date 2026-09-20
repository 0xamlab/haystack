// SPDX-License-Identifier: Apache-2.0
// Unit tests for the remaining uncovered branches of
// _client_platform_validators_c.ts. Payloads come from the shared signed
// manifest factories; each rejection case mutates exactly one field so the
// failing branch is unambiguous.
import { describe, expect, it } from "vitest";
import { DecisionEngineError } from "./_client_errors.js";
import { buildStructuredValidationError } from "./_client_platform_validators_b2.js";
import {
  assertCountRecordMatches,
  assertRuntimeBenchmarkClassEntry,
  assertRuntimeKernelPromotionCriteria,
  assertRuntimeModuleManifestEntry,
  assertRuntimeSLOBudget,
  wrapRuntimeValidation,
} from "./_client_platform_validators_c.js";
import {
  cloneJsonValue,
  makeKernelPromotionCriteriaPayload,
  makeRuntimeManifestPayload,
} from "./_client_test_helpers.js";

type RejectionCase = [label: string, payload: unknown, fragment: RegExp];

function expectRejection(run: () => unknown, fragment: RegExp): void {
  expect(run).toThrow(DecisionEngineError);
  expect(run).toThrow(fragment);
}

function captureError(run: () => unknown): DecisionEngineError {
  try {
    run();
  } catch (error) {
    expect(error).toBeInstanceOf(DecisionEngineError);
    return error as DecisionEngineError;
  }
  throw new Error("expected the validator to throw");
}

// Fresh deep copies of the first entry of each manifest section, so that a
// mutation in one case can never leak into another.
function manifestModule(): Record<string, unknown> {
  const modules = makeRuntimeManifestPayload().modules as Record<string, unknown>[];
  return cloneJsonValue(modules[0]);
}

function manifestSloBudget(): Record<string, unknown> {
  const budgets = makeRuntimeManifestPayload().slo_budgets as Record<string, unknown>[];
  return cloneJsonValue(budgets[0]);
}

function manifestBenchmarkClass(): Record<string, unknown> {
  const benchmarking = makeRuntimeManifestPayload().benchmarking as {
    classes: Record<string, unknown>[];
  };
  return cloneJsonValue(benchmarking.classes[0]);
}

describe("assertRuntimeModuleManifestEntry", () => {
  const context = "Algenta runtime manifest response.modules[0]";

  it("returns the module summary for a well-formed entry", () => {
    expect(assertRuntimeModuleManifestEntry(manifestModule(), context)).toEqual({
      name: "bpe_tokenizer",
      functionCount: 2,
      functions: ["encode", "decode"],
      layer: "mojo_llm_runtime_core",
      maturity: "channel_covered",
      benchmarkSpeedupX: 101,
      promotionStatus: "shipping",
    });
  });

  it("rejects a functions list whose length disagrees with function_count", () => {
    const error = captureError(() =>
      assertRuntimeModuleManifestEntry({ ...manifestModule(), function_count: 3 }, context),
    );
    expect(error.message).toBe(
      `${context}.functions must contain exactly 3 entries to match function_count.`,
    );
    expect(error.errorCode).toBe("invalid_payload_fragment");
    // The manifest prefix is stripped and the index is normalized in the path.
    expect(error.validationErrors).toEqual([
      { path: "modules.0.functions", message: error.message, type: "value_error" },
    ]);
  });
});

describe("assertRuntimeKernelPromotionCriteria", () => {
  const context = "Algenta runtime manifest response.kernel_promotion_criteria";

  it("returns the minimum primary-metric improvement", () => {
    expect(
      assertRuntimeKernelPromotionCriteria(makeKernelPromotionCriteriaPayload(), context),
    ).toEqual({
      minimumPrimaryMetricImprovementPct: 15,
    });
  });

  it.each<RejectionCase>([
    [
      "a zero minimum improvement",
      { ...makeKernelPromotionCriteriaPayload(), minimum_primary_metric_improvement_pct: 0 },
      /minimum_primary_metric_improvement_pct must be greater than 0/,
    ],
    [
      "a negative minimum improvement",
      { ...makeKernelPromotionCriteriaPayload(), minimum_primary_metric_improvement_pct: -1 },
      /minimum_primary_metric_improvement_pct must be greater than 0/,
    ],
    [
      "a negative maximum regression",
      { ...makeKernelPromotionCriteriaPayload(), maximum_adjacent_metric_regression_pct: -0.5 },
      /maximum_adjacent_metric_regression_pct must be greater than or equal to 0/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertRuntimeKernelPromotionCriteria(payload, context), fragment);
  });

  it("reports the offending threshold in the validation path", () => {
    const error = captureError(() =>
      assertRuntimeKernelPromotionCriteria(
        { ...makeKernelPromotionCriteriaPayload(), maximum_adjacent_metric_regression_pct: -0.5 },
        context,
      ),
    );
    expect(error.validationErrors[0]).toEqual({
      path: "kernel_promotion_criteria.maximum_adjacent_metric_regression_pct",
      message: error.message,
      type: "value_error",
    });
  });
});

describe("assertRuntimeSLOBudget", () => {
  const context = "Algenta runtime manifest response.slo_budgets[0]";

  it.each<[label: string, overrides: Record<string, unknown>]>([
    ["a numeric hard_ceiling_ms", { hard_ceiling_ms: 100 }],
    ["a null hard_ceiling_ms", { hard_ceiling_ms: null }],
    ["an undefined hard_ceiling_ms", { hard_ceiling_ms: undefined }],
    ["a string notes", { notes: "Measured on the shared fleet." }],
    ["a null notes", { notes: null }],
    ["an undefined notes", { notes: undefined }],
  ])("accepts %s", (_label, overrides) => {
    expect(
      assertRuntimeSLOBudget({ ...manifestSloBudget(), ...overrides }, context),
    ).toBeUndefined();
  });

  it.each<RejectionCase>([
    [
      "a string hard_ceiling_ms",
      { hard_ceiling_ms: "fast" },
      /slo_budgets\[0\]\.hard_ceiling_ms must be a finite number/,
    ],
    [
      "a NaN hard_ceiling_ms",
      { hard_ceiling_ms: Number.NaN },
      /slo_budgets\[0\]\.hard_ceiling_ms must be a finite number/,
    ],
    ["an empty notes", { notes: "" }, /slo_budgets\[0\]\.notes must be a non-empty string/],
    ["a numeric notes", { notes: 5 }, /slo_budgets\[0\]\.notes must be a non-empty string/],
  ])("rejects %s", (_label, overrides, fragment) => {
    expectRejection(
      () =>
        assertRuntimeSLOBudget(
          { ...manifestSloBudget(), ...(overrides as Record<string, unknown>) },
          context,
        ),
      fragment,
    );
  });
});

describe("assertCountRecordMatches", () => {
  const context = "Algenta runtime admin modules response.summary.maturity_counts";

  it("accepts identical distributions regardless of key order", () => {
    expect(
      assertCountRecordMatches(
        { channel_covered: 1, experimental: 2 },
        { experimental: 2, channel_covered: 1 },
        context,
        "maturity",
      ),
    ).toBeUndefined();
  });

  it.each<[label: string, actual: Record<string, number>, expected: Record<string, number>]>([
    ["an extra key", { channel_covered: 1, experimental: 0 }, { channel_covered: 1 }],
    ["a different key with the same size", { experimental: 1 }, { channel_covered: 1 }],
    ["a different count", { channel_covered: 2 }, { channel_covered: 1 }],
  ])("rejects %s", (_label, actual, expected) => {
    const error = captureError(() =>
      assertCountRecordMatches(actual, expected, context, "maturity"),
    );
    expect(error.message).toBe(`${context} must equal the module maturity distribution.`);
    expect(error.validationErrors).toEqual([
      { path: "summary.maturity_counts", message: error.message, type: "value_error" },
    ]);
  });
});

describe("assertRuntimeBenchmarkClassEntry", () => {
  const context = "Algenta runtime manifest response.benchmarking.classes[0]";

  it("keeps the declared evidence paths", () => {
    expect(assertRuntimeBenchmarkClassEntry(manifestBenchmarkClass(), context)).toEqual({
      code: "B1",
      description: "microkernel latency",
      evidence_paths: ["benchmarks/summary.json"],
    });
  });

  it("defaults evidence_paths to an empty list when the field is absent", () => {
    expect(
      assertRuntimeBenchmarkClassEntry(
        { ...manifestBenchmarkClass(), evidence_paths: undefined },
        context,
      ),
    ).toEqual({ code: "B1", description: "microkernel latency", evidence_paths: [] });
  });

  it.each<RejectionCase>([
    [
      "a string evidence_paths",
      { evidence_paths: "benchmarks/summary.json" },
      /classes\[0\]\.evidence_paths must be a list of non-empty strings/,
    ],
    [
      "a null evidence_paths",
      { evidence_paths: null },
      /classes\[0\]\.evidence_paths must be a list of non-empty strings/,
    ],
    [
      "duplicate evidence paths",
      { evidence_paths: ["benchmarks/summary.json", "benchmarks/summary.json"] },
      /classes\[0\]\.evidence_paths must be unique; duplicate entries: benchmarks\/summary\.json/,
    ],
  ])("rejects %s", (_label, overrides, fragment) => {
    expectRejection(
      () =>
        assertRuntimeBenchmarkClassEntry(
          { ...manifestBenchmarkClass(), ...(overrides as Record<string, unknown>) },
          context,
        ),
      fragment,
    );
  });
});

describe("wrapRuntimeValidation", () => {
  const context = "getRuntimeManifest()";

  it("returns the validator result untouched", () => {
    expect(
      wrapRuntimeValidation(context, { count: 3 }, (value) => (value as { count: number }).count),
    ).toBe(3);
  });

  it("wraps a structured validation error and preserves its details object", () => {
    const inner = buildStructuredValidationError(
      "Algenta runtime manifest response.modules[0].name",
      "modules[0].name has unsupported value 'x'.",
      "enum",
    );
    const error = captureError(() =>
      wrapRuntimeValidation(context, {}, () => {
        throw inner;
      }),
    );
    expect(error).not.toBe(inner);
    expect(error.message).toBe(
      "getRuntimeManifest() returned an invalid signed payload: modules[0].name has unsupported value 'x'.",
    );
    expect(error.statusCode).toBe(0);
    expect(error.errorCode).toBe("invalid_runtime_contract_payload");
    expect(error.responseBody).toEqual({
      error: { code: "invalid_runtime_contract_payload", details: inner.details },
    });
    expect(error.validationErrors).toEqual(inner.validationErrors);
  });

  it.each<[label: string, inner: DecisionEngineError]>([
    ["no response body", new DecisionEngineError("plain failure")],
    // Array-shaped details are not a details object, so they are replaced by the cause.
    [
      "array-shaped details",
      new DecisionEngineError("plain failure", 0, "unknown_error", {
        error: { details: [{ path: "modules" }] },
      }),
    ],
  ])("wraps a DecisionEngineError with %s into a cause-only details object", (_label, inner) => {
    const error = captureError(() =>
      wrapRuntimeValidation(context, {}, () => {
        throw inner;
      }),
    );
    expect(error.message).toBe(
      "getRuntimeManifest() returned an invalid signed payload: plain failure",
    );
    expect(error.errorCode).toBe("invalid_runtime_contract_payload");
    expect(error.details).toEqual({ cause: "plain failure" });
    expect(error.validationErrors).toEqual([]);
  });

  it("rethrows non-DecisionEngineError failures unchanged", () => {
    const boom = new TypeError("boom");
    let caught: unknown;
    try {
      wrapRuntimeValidation(context, {}, () => {
        throw boom;
      });
    } catch (error) {
      caught = error;
    }
    expect(caught).toBe(boom);
  });
});
