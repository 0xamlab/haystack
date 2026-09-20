// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import { DecisionEngineError } from "./_client_errors.js";
import {
  assertRuntimeAdminBenchmarksResponse,
  assertRuntimeAdminModulesResponse,
} from "./_client_runtime_admin.js";
import { assertRuntimeManifestResponse } from "./_client_runtime_manifest.js";
import {
  assertRuntimeReleaseValidationResponse,
  buildQueryExecutionMetadata,
  parseHeaderBoolean,
  parseHeaderNumber,
} from "./_client_runtime_release.js";
import {
  cloneJsonValue,
  makeQueryResponse,
  makeRuntimeAdminBenchmarksPayload,
  makeRuntimeAdminModulesPayload,
  makeRuntimeManifestPayload,
  makeRuntimeReleaseValidationPayload,
} from "./_client_test_helpers.js";
import type { QueryResponse } from "./types.js";

type JsonObject = Record<string, unknown>;

interface CrossCheckCase {
  name: string;
  mutate: (payload: JsonObject) => void;
  path: string;
  message: string;
}

function section(root: JsonObject, ...keys: string[]): JsonObject {
  return keys.reduce<JsonObject>((current, key) => current[key] as JsonObject, root);
}

function firstEntry(root: JsonObject, key: string): JsonObject {
  return (root[key] as JsonObject[])[0];
}

function pushEntry(root: JsonObject, key: string, entry: unknown): void {
  (root[key] as unknown[]).push(entry);
}

function expectRuntimeRejection(
  run: () => unknown,
  endpoint: string,
  path: string,
  message: string,
): void {
  let caught: unknown;
  try {
    run();
  } catch (error) {
    caught = error;
  }
  expect(caught).toBeInstanceOf(DecisionEngineError);
  const error = caught as DecisionEngineError;
  expect(error.errorCode).toBe("invalid_runtime_contract_payload");
  expect(error.message.startsWith(`${endpoint} returned an invalid signed payload: `)).toBe(true);
  expect(error.message).toContain(message);
  // buildStructuredValidationError strips the response prefix and dots array indexes.
  expect(error.validationErrors[0]?.path).toBe(path);
}

function describeCrossChecks(
  endpoint: string,
  factory: () => JsonObject,
  validator: (payload: unknown) => unknown,
  cases: CrossCheckCase[],
): void {
  it.each(cases)("rejects when $name", ({ mutate, path, message }) => {
    const payload = cloneJsonValue(factory());
    mutate(payload);
    expectRuntimeRejection(() => validator(payload), endpoint, path, message);
  });
}

// Shrinks the discovery inventory to a module that is not the shipping one, keeping the lane's
// own count invariants satisfied so only the manifest cross-check can fail.
function dropShippingModuleFromInventory(payload: JsonObject): void {
  const lane = section(payload, "benchmark_discovery_lane");
  lane.discovered_source_inventory = [{ import_path: "embeddings", public_function_count: 2 }];
  lane.discovered_source_modules = 1;
  lane.discovered_public_functions = 2;
}

describe("assertRuntimeManifestResponse", () => {
  const ENDPOINT = "Algenta runtime manifest endpoint";

  it("returns the validated payload by reference", () => {
    const payload = makeRuntimeManifestPayload();
    expect(assertRuntimeManifestResponse(payload)).toBe(payload);
  });

  it("rejects a non-object payload at the response root", () => {
    expectRuntimeRejection(
      () => assertRuntimeManifestResponse(null),
      ENDPOINT,
      "Algenta runtime manifest response",
      "Algenta runtime manifest response must be a JSON object.",
    );
  });

  describeCrossChecks(ENDPOINT, makeRuntimeManifestPayload, assertRuntimeManifestResponse, [
    {
      name: "shipping_contract.module_count disagrees with the module list",
      mutate: (payload) => {
        section(payload, "shipping_contract").module_count = 2;
      },
      path: "shipping_contract.module_count",
      message: "shipping_contract.module_count must equal the number of manifest modules.",
    },
    {
      name: "shipping_contract.function_count disagrees with the summed function_count",
      mutate: (payload) => {
        section(payload, "shipping_contract").function_count = 3;
      },
      path: "shipping_contract.function_count",
      message: "shipping_contract.function_count must equal the total module function_count.",
    },
    {
      name: "benchmark_discovery_lane.shipping_manifest_modules disagrees with the module list",
      mutate: (payload) => {
        section(payload, "benchmark_discovery_lane").shipping_manifest_modules = 2;
      },
      path: "benchmark_discovery_lane.shipping_manifest_modules",
      message: "shipping_manifest_modules must equal the number of manifest modules.",
    },
    {
      name: "benchmark_discovery_lane.shipping_manifest_functions disagrees with the summed function_count",
      mutate: (payload) => {
        section(payload, "benchmark_discovery_lane").shipping_manifest_functions = 3;
      },
      path: "benchmark_discovery_lane.shipping_manifest_functions",
      message: "shipping_manifest_functions must equal the total module function_count.",
    },
    {
      name: "the discovery inventory omits a manifest module",
      mutate: dropShippingModuleFromInventory,
      path: "benchmark_discovery_lane.discovered_source_inventory",
      message: "discovered_source_inventory must include manifest module bpe_tokenizer.",
    },
    {
      name: "a manifest module is still a candidate",
      mutate: (payload) => {
        firstEntry(payload, "modules").promotion_status = "candidate";
      },
      path: "modules",
      message: "modules must mark bpe_tokenizer as shipping to appear in the signed manifest.",
    },
    {
      name: "a manifest module speedup sits below the promotion threshold",
      mutate: (payload) => {
        // Threshold is 1 + minimum_primary_metric_improvement_pct / 100 = 1.15.
        firstEntry(payload, "modules").benchmark_speedup_x = 1.1;
      },
      path: "modules",
      message:
        "modules must keep bpe_tokenizer above the kernel promotion minimum speedup threshold.",
    },
  ]);
});

describe("assertRuntimeAdminModulesResponse", () => {
  const ENDPOINT = "Algenta runtime admin modules endpoint";

  it("returns the validated payload by reference", () => {
    const payload = makeRuntimeAdminModulesPayload();
    expect(assertRuntimeAdminModulesResponse(payload)).toBe(payload);
  });

  describeCrossChecks(
    ENDPOINT,
    makeRuntimeAdminModulesPayload,
    assertRuntimeAdminModulesResponse,
    [
      {
        name: "shipping_contract.module_count disagrees with the module list",
        mutate: (payload) => {
          section(payload, "shipping_contract").module_count = 0;
        },
        path: "shipping_contract.module_count",
        message: "shipping_contract.module_count must equal the number of manifest modules.",
      },
      {
        name: "shipping_contract.function_count disagrees with the summed function_count",
        mutate: (payload) => {
          section(payload, "shipping_contract").function_count = 1;
        },
        path: "shipping_contract.function_count",
        message: "shipping_contract.function_count must equal the total module function_count.",
      },
      {
        name: "summary.module_count disagrees with the module list",
        mutate: (payload) => {
          section(payload, "summary").module_count = 2;
        },
        path: "summary.module_count",
        message: "summary.module_count must equal the number of manifest modules.",
      },
      {
        name: "summary.function_count disagrees with the summed function_count",
        mutate: (payload) => {
          section(payload, "summary").function_count = 4;
        },
        path: "summary.function_count",
        message: "summary.function_count must equal the total module function_count.",
      },
      {
        name: "summary.maturity_counts disagrees with the module maturities",
        mutate: (payload) => {
          section(payload, "summary").maturity_counts = { channel_covered: 2 };
        },
        path: "summary.maturity_counts",
        message: "summary.maturity_counts must equal the module maturity distribution.",
      },
      {
        name: "summary.layer_counts disagrees with the module layers",
        mutate: (payload) => {
          section(payload, "summary").layer_counts = {};
        },
        path: "summary.layer_counts",
        message: "summary.layer_counts must equal the module layer distribution.",
      },
    ],
  );
});

describe("assertRuntimeAdminBenchmarksResponse", () => {
  const ENDPOINT = "Algenta runtime admin benchmarks endpoint";

  // Every shipping_runtime_* array must line up index-for-index with module_benchmarks.
  const SHIPPING_ARRAYS = [
    { key: "shipping_runtime_modules", field: "name", extra: "embeddings", mismatch: "embeddings" },
    { key: "shipping_runtime_function_counts", field: "function_count", extra: 2, mismatch: 3 },
    {
      key: "shipping_runtime_benchmark_speedups_x",
      field: "benchmark_speedup_x",
      extra: 50,
      mismatch: 55,
    },
    {
      key: "shipping_runtime_benchmark_artifacts",
      field: "benchmark_artifact",
      extra: "build/other.json",
      mismatch: "build/other.json",
    },
    {
      key: "shipping_runtime_compiled_artifacts",
      field: "compiled_artifact",
      extra: "mojo_build/other",
      mismatch: "mojo_build/other",
    },
    {
      key: "shipping_runtime_compiled_engines",
      field: "compiled_engine",
      extra: "mojo",
      mismatch: "python_fallback",
    },
    { key: "shipping_runtime_max_cold_ms", field: "max_cold_ms", extra: 12, mismatch: 13 },
    { key: "shipping_runtime_max_warm_ms", field: "max_warm_ms", extra: 4, mismatch: 5 },
    { key: "shipping_runtime_max_hot_ms", field: "max_hot_ms", extra: 2, mismatch: 3 },
  ];

  const POSITIVE_FIELDS = [
    { field: "benchmark_speedup_x", key: "shipping_runtime_benchmark_speedups_x" },
    { field: "max_cold_ms", key: "shipping_runtime_max_cold_ms" },
    { field: "max_warm_ms", key: "shipping_runtime_max_warm_ms" },
    { field: "max_hot_ms", key: "shipping_runtime_max_hot_ms" },
  ];

  const EVALUATION_COUNTS = [
    { field: "dimension_count", suffix: "the number of evaluation dimensions." },
    { field: "method_count", suffix: "the number of evaluation methods." },
    { field: "release_blocker_count", suffix: "the number of release blockers." },
    { field: "benchmark_class_count", suffix: "the number of quality gate benchmark classes." },
    { field: "slo_budget_count", suffix: "the number of quality gate SLO budgets." },
  ];

  const GATE_FLAGS = [
    {
      flag: "replay_gate_enabled",
      suffix: "the replay benchmark, budget, and release blocker coverage.",
    },
    {
      flag: "tool_call_quality_gate_enabled",
      suffix: "the tool-call benchmark, budget, and release blocker coverage.",
    },
    {
      flag: "rag_quality_gate_enabled",
      suffix: "the RAG benchmark and release blocker coverage.",
    },
    {
      flag: "decision_quality_gate_enabled",
      suffix: "the decision benchmark, budget, and release blocker coverage.",
    },
  ];

  // The shared factory lists the replay budget under quality_gate_slo_budgets but not under
  // slo_budgets, which the validator rejects; declare it so the base payload is valid.
  function makeBenchmarksPayload(): JsonObject {
    const payload = makeRuntimeAdminBenchmarksPayload();
    pushEntry(payload, "slo_budgets", {
      name: "replay",
      applies_to: "runs up to 1000 events",
      p95_objective_ms: 750,
      hard_ceiling_ms: 2000,
    });
    return payload;
  }

  function withSecondBenchmarkModule(payload: JsonObject, overrides: JsonObject = {}): void {
    const second: JsonObject = {
      name: "embeddings",
      function_count: 2,
      benchmark_artifact: "build/embeddings_bench.json",
      benchmark_speedup_x: 50,
      compiled_artifact: "mojo_build/embeddings",
      compiled_engine: "mojo",
      max_cold_ms: 20,
      max_warm_ms: 8,
      max_hot_ms: 3,
      ...overrides,
    };
    pushEntry(payload, "module_benchmarks", second);
    pushEntry(payload, "compiled_artifacts", {
      kind: "compiled_mojo_binary",
      path: second.compiled_artifact,
      sha256: "f".repeat(64),
      size_bytes: 2048,
    });
    for (const { key, field } of SHIPPING_ARRAYS) {
      pushEntry(payload, key, second[field]);
    }
    const lane = section(payload, "benchmark_discovery_lane");
    lane.shipping_manifest_modules = 2;
    lane.shipping_manifest_functions = 4;
  }

  function removeQualityGateBudget(payload: JsonObject, name: string): void {
    payload.quality_gate_slo_budgets = (payload.quality_gate_slo_budgets as JsonObject[]).filter(
      (entry) => entry.name !== name,
    );
    section(payload, "evaluation_summary").slo_budget_count = 2;
  }

  it("returns the validated payload by reference", () => {
    const payload = makeBenchmarksPayload();
    expect(assertRuntimeAdminBenchmarksResponse(payload)).toBe(payload);
  });

  it("accepts a consistent multi-module payload", () => {
    const payload = makeBenchmarksPayload();
    withSecondBenchmarkModule(payload);
    expect(assertRuntimeAdminBenchmarksResponse(payload)).toBe(payload);
    expect((payload.shipping_runtime_modules as string[]).length).toBe(2);
  });

  it.each([
    {
      gate: "replay",
      flag: "replay_gate_enabled",
      disable: (payload: JsonObject) => removeQualityGateBudget(payload, "replay"),
    },
    {
      gate: "tool-call",
      flag: "tool_call_quality_gate_enabled",
      disable: (payload: JsonObject) => removeQualityGateBudget(payload, "mcp_call_first_party"),
    },
    {
      gate: "decision",
      flag: "decision_quality_gate_enabled",
      disable: (payload: JsonObject) => removeQualityGateBudget(payload, "decision_plan_creation"),
    },
    {
      gate: "RAG",
      flag: "rag_quality_gate_enabled",
      disable: (payload: JsonObject) => {
        payload.quality_gate_benchmark_classes = (
          payload.quality_gate_benchmark_classes as JsonObject[]
        ).filter((entry) => entry.code !== "B9");
        section(payload, "evaluation_summary").benchmark_class_count = 3;
      },
    },
  ])("accepts a payload whose $gate gate is legitimately disabled", ({ flag, disable }) => {
    const payload = makeBenchmarksPayload();
    disable(payload);
    section(payload, "evaluation_summary")[flag] = false;
    expect(assertRuntimeAdminBenchmarksResponse(payload)).toBe(payload);
  });

  describeCrossChecks(
    ENDPOINT,
    makeBenchmarksPayload,
    assertRuntimeAdminBenchmarksResponse,
    [
      {
        name: "benchmark_discovery_lane.shipping_manifest_modules disagrees with module_benchmarks",
        mutate: (payload) => {
          section(payload, "benchmark_discovery_lane").shipping_manifest_modules = 2;
        },
        path: "benchmark_discovery_lane.shipping_manifest_modules",
        message: "shipping_manifest_modules must equal the number of benchmark modules.",
      },
      ...SHIPPING_ARRAYS.map(({ key, extra }) => ({
        name: `${key} has more entries than module_benchmarks`,
        mutate: (payload: JsonObject) => {
          pushEntry(payload, key, extra);
        },
        path: key,
        message: `${key} must contain one entry per shipping benchmark module.`,
      })),
      {
        name: "benchmark_discovery_lane.shipping_manifest_functions disagrees with the summed function_count",
        mutate: (payload) => {
          section(payload, "benchmark_discovery_lane").shipping_manifest_functions = 3;
        },
        path: "benchmark_discovery_lane.shipping_manifest_functions",
        message:
          "shipping_manifest_functions must equal the total benchmark module function_count.",
      },
      {
        name: "the discovery inventory omits a benchmark module",
        mutate: dropShippingModuleFromInventory,
        path: "benchmark_discovery_lane.discovered_source_inventory",
        message:
          "discovered_source_inventory must include module_benchmarks[0].name (bpe_tokenizer).",
      },
      ...SHIPPING_ARRAYS.map(({ key, field, mismatch }) => ({
        name: `${key}[0] disagrees with module_benchmarks[0].${field}`,
        mutate: (payload: JsonObject) => {
          (payload[key] as unknown[])[0] = mismatch;
        },
        path: `${key}.0`,
        message: `${key}[0] must equal module_benchmarks[0].${field}.`,
      })),
      ...POSITIVE_FIELDS.map(({ field, key }) => ({
        name: `module_benchmarks[0].${field} is not positive`,
        mutate: (payload: JsonObject) => {
          // Keep the mirrored array in sync so the positivity check is the first to fail.
          firstEntry(payload, "module_benchmarks")[field] = 0;
          (payload[key] as unknown[])[0] = 0;
        },
        path: `module_benchmarks.0.${field}`,
        message: `module_benchmarks entries must have positive ${field} values.`,
      })),
      {
        name: "module_benchmarks[1].benchmark_artifact duplicates an earlier module",
        mutate: (payload) => {
          withSecondBenchmarkModule(payload, { benchmark_artifact: "build/bench.json" });
        },
        path: "module_benchmarks.1.benchmark_artifact",
        message:
          "module_benchmarks[1].benchmark_artifact duplicates module_benchmarks[0].benchmark_artifact.",
      },
      {
        name: "module_benchmarks[0].compiled_artifact is not in compiled_artifacts",
        mutate: (payload) => {
          firstEntry(payload, "module_benchmarks").compiled_artifact = "mojo_build/missing";
          payload.shipping_runtime_compiled_artifacts = ["mojo_build/missing"];
        },
        path: "module_benchmarks.0.compiled_artifact",
        message:
          "module_benchmarks[0].compiled_artifact must reference a path present in compiled_artifacts.",
      },
      {
        name: "a quality gate benchmark class is not declared in benchmarking.classes",
        mutate: (payload) => {
          pushEntry(payload, "quality_gate_benchmark_classes", {
            code: "B1",
            description: "microkernel latency",
            evidence_paths: ["benchmarks/summary.json"],
          });
        },
        path: "quality_gate_benchmark_classes",
        message: "quality_gate_benchmark_classes must be declared in benchmarking.classes.",
      },
      {
        name: "a quality gate SLO budget is not declared in slo_budgets",
        mutate: (payload) => {
          pushEntry(payload, "quality_gate_slo_budgets", {
            name: "ttft",
            applies_to: "first-party native LLM serving path",
            p95_objective_ms: 300,
            hard_ceiling_ms: 900,
          });
        },
        path: "quality_gate_slo_budgets",
        message: "quality_gate_slo_budgets must be declared in slo_budgets.",
      },
      ...EVALUATION_COUNTS.map(({ field, suffix }) => ({
        name: `evaluation_summary.${field} is off by one`,
        mutate: (payload: JsonObject) => {
          const summary = section(payload, "evaluation_summary");
          summary[field] = (summary[field] as number) + 1;
        },
        path: `evaluation_summary.${field}`,
        message: `evaluation_summary.${field} must equal ${suffix}`,
      })),
      ...GATE_FLAGS.map(({ flag, suffix }) => ({
        name: `evaluation_summary.${flag} contradicts the declared coverage`,
        mutate: (payload: JsonObject) => {
          section(payload, "evaluation_summary")[flag] = false;
        },
        path: `evaluation_summary.${flag}`,
        message: `evaluation_summary.${flag} must match ${suffix}`,
      })),
    ],
  );
});

describe("assertRuntimeReleaseValidationResponse", () => {
  const ENDPOINT = "Algenta runtime release validation endpoint";

  it.each(["saas", "local_dev_daemon", null])(
    "accepts deployment_mode %j and returns the payload by reference",
    (deploymentMode) => {
      const payload = makeRuntimeReleaseValidationPayload();
      payload.deployment_mode = deploymentMode;
      expect(assertRuntimeReleaseValidationResponse(payload)).toBe(payload);
    },
  );

  it("rejects an unsupported deployment_mode", () => {
    const payload = makeRuntimeReleaseValidationPayload();
    payload.deployment_mode = "orbital";
    expectRuntimeRejection(
      () => assertRuntimeReleaseValidationResponse(payload),
      ENDPOINT,
      "deployment_mode",
      "deployment_mode has unsupported value 'orbital'.",
    );
  });

  it("rejects a missing deployment_mode because only null opts out", () => {
    const payload = makeRuntimeReleaseValidationPayload();
    delete payload.deployment_mode;
    expectRuntimeRejection(
      () => assertRuntimeReleaseValidationResponse(payload),
      ENDPOINT,
      "deployment_mode",
      "deployment_mode must be a non-empty string.",
    );
  });

  it("rejects duplicate condition names", () => {
    const payload = makeRuntimeReleaseValidationPayload();
    pushEntry(payload, "conditions", cloneJsonValue(firstEntry(payload, "conditions")));
    expectRuntimeRejection(
      () => assertRuntimeReleaseValidationResponse(payload),
      ENDPOINT,
      "conditions",
      "conditions must be unique; duplicate entries: manifest-listed",
    );
  });
});

describe("parseHeaderNumber", () => {
  it("returns the first finite numeric header, skipping missing and non-numeric keys", () => {
    expect(parseHeaderNumber({ "x-b": "2.5" }, "x-a", "x-b")).toBe(2.5);
    expect(parseHeaderNumber({ "x-a": "n/a", "x-b": "0" }, "x-a", "x-b")).toBe(0);
    expect(parseHeaderNumber({ "x-a": "-7" }, "x-a")).toBe(-7);
  });

  it("returns undefined when no key yields a finite number", () => {
    expect(parseHeaderNumber({}, "x-a")).toBeUndefined();
    expect(parseHeaderNumber({ "x-a": "NaN", "x-b": "Infinity" }, "x-a", "x-b")).toBeUndefined();
  });
});

describe("parseHeaderBoolean", () => {
  it.each(["1", "true", "HIT", " yes "])("reads %j as true", (value) => {
    expect(parseHeaderBoolean({ "x-cache": value }, "x-cache")).toBe(true);
  });

  it.each(["0", "false", "Miss", "no"])("reads %j as false", (value) => {
    expect(parseHeaderBoolean({ "x-cache": value }, "x-cache")).toBe(false);
  });

  it("falls through unknown values to later keys and otherwise returns undefined", () => {
    expect(parseHeaderBoolean({ "x-a": "maybe", "x-b": "miss" }, "x-a", "x-b")).toBe(false);
    expect(parseHeaderBoolean({ "x-a": "maybe" }, "x-a", "x-b")).toBeUndefined();
    expect(parseHeaderBoolean({}, "x-a")).toBeUndefined();
  });
});

describe("buildQueryExecutionMetadata", () => {
  const queryData = (overrides: Record<string, unknown> = {}): QueryResponse =>
    makeQueryResponse(overrides) as unknown as QueryResponse;

  it("prefers body fields and reads the remaining metrics from headers", () => {
    const metadata = buildQueryExecutionMetadata(
      queryData({ request_id: "req-body", latency_ms: 12 }),
      {
        "x-request-id": "req-header",
        "x-latency-ms": "99",
        "x-prompt-tokens": "120",
        "x-tokens-out": "40",
        "x-usage-cost-usd": "0.0025",
        "x-cache": "hit",
      },
    );
    expect(metadata).toEqual({
      request_id: "req-body",
      latency_ms: 12,
      tokens_in: 120,
      tokens_out: 40,
      cost_usd: 0.0025,
      cache_hit: true,
    });
  });

  it("falls back to headers when the body omits request_id and latency_ms", () => {
    const metadata = buildQueryExecutionMetadata(
      queryData({ request_id: "", latency_ms: "fast" }),
      {
        "x-algenta-request-id": "req-algenta",
        "x-latency-ms": "n/a",
        "x-response-time-ms": "31",
        "x-algenta-cache-hit": "miss",
      },
    );
    expect(metadata).toEqual({
      request_id: "req-algenta",
      latency_ms: 31,
      tokens_in: undefined,
      tokens_out: undefined,
      cost_usd: undefined,
      cache_hit: false,
    });
  });

  it("walks the full request-id header chain", () => {
    expect(
      buildQueryExecutionMetadata(queryData({ request_id: null }), { "request-id": "req-last" })
        .request_id,
    ).toBe("req-last");
    expect(
      buildQueryExecutionMetadata(queryData({ request_id: undefined, latency_ms: null }), {}),
    ).toEqual({
      request_id: undefined,
      latency_ms: undefined,
      tokens_in: undefined,
      tokens_out: undefined,
      cost_usd: undefined,
      cache_hit: undefined,
    });
  });
});
