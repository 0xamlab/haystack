// SPDX-License-Identifier: Apache-2.0
// Tests for Runtime: rejects_a.
// Extracted from runtime.test.ts during modularization.
import { createHash, createHmac, createSign, generateKeyPairSync } from "node:crypto";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve as resolvePath } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DecisionEngineError } from "./client.js";
import { expectManifestBackedIntegrationsEqual } from "./test_contract_helpers.js";
import {
  Runtime,
  RuntimeConfigurationError,
  RuntimeValidationError,
  renderSourceBundlePreview,
  renderSourceImportPreview,
} from "./runtime.js";
import {
  ALGENTA_OWNED_HOSTS,
  ALGENTA_OWNED_SUFFIXES,
  API_KEY_PREFIX_LIVE,
  API_KEY_PREFIX_TEST,
  AUTH_SCHEME,
  BRAND,
  CONTRACT_VERSION,
  DEFAULT_BASE_URL,
  DEPRECATION_WINDOW_DAYS,
  INTEGRATIONS,
  LEGACY_DOMAINS,
  LEGACY_ENV_VARS,
  LEGACY_HEADERS,
  MCP_ENDPOINT,
  MCP_TOOLS_ENDPOINT,
  PLAN_LIMITS,
  PRIVATE_HOST_SUFFIXES,
  PRIMARY_DATA_QUERY_CONTRACT,
  READ_ONLY_DEFAULT,
  VENDOR_TELEMETRY_HOSTS,
  WRITE_CONFIRMATION_REQUIRED,
} from "./contract.js";
import type {
  RuntimeBenchmarkBaseline,
  RuntimeBenchmarkClassCode,
  RuntimeBenchmarkDiscoveryRule,
  RuntimeBenchmarkMetric,
  RuntimeEvaluationDimension,
  RuntimeEvaluationMethod,
  RuntimeExecutionStateField,
  RuntimeExecutionValidityRule,
  RuntimeExternalNondeterminismSource,
  RuntimeFailureCode,
  RuntimeInvariantName,
  RuntimeArtifactLineageStep,
  RuntimeAdminEndpoint,
  RuntimeCapabilityField,
  RuntimeCapabilityRule,
  RuntimeLineageNodeField,
  RuntimeNondeterminismArtifact,
  RuntimeMemoryRegion,
  RuntimeMemoryRule,
  RuntimeModuleId,
  RuntimeNonShippingRule,
  RuntimeProofObligation,
  RuntimePublicEndpoint,
  RuntimeReleaseArtifact,
  RuntimeReleaseBlocker,
  RuntimeReleaseGateId,
  RuntimeSLOBudgetAppliesTo,
  RuntimeSchedulerInvariant,
  RuntimeSchedulerMaximizeObjective,
  RuntimeSchedulerMinimizeObjective,
  RuntimeSLOBudgetName,
  RuntimeSchedulerPolicy,
  RuntimeFeatureFlagEndpoint,
  RuntimeThreatClass,
  RuntimeThreatControl,
  RuntimeThreatRule,
} from "./types.js";
import {
  SHIPPING_BENCHMARK_DISCOVERY_RULE,
  NON_SHIPPING_RULE,
  DECISION_WORKFLOW_BENCHMARK_EVIDENCE,
  makeDiscoveredSourceInventory,
  makeBenchmarkDiscoveryLanePayload,
  makeKernelPromotionCriteriaPayload,
  REAL_MARCH_ORDERS,
  REAL_MARCH_FINANCIAL,
  REAL_MARCH_EMPTY,
  ORIGINAL_ENV,
  cloneJsonValue,
  makeContractPayload,
  makeRuntimeManifestPayload,
  makeRuntimeAdminModulesPayload,
  makeRuntimeAdminBenchmarksPayload,
  makeRuntimeReleaseValidationPayload,
  runtimeTempDir,
  base64UrlJson,
  issueControlPlaneLicense,
  issueOfflineLocalLicense,
  seedStoredLicense,
  seedTrustedTime,
  readLedgerEvents,
  hasNodeSqlite,
  writeSqliteFixture,
} from "./_runtime_test_helpers.js";

beforeEach(() => {
  delete process.env.ALGENTA_RUNTIME_DIR;
  delete process.env.ALGENTA_JWT_SECRET;
  delete process.env.ALGENTA_CONTROL_PLANE_URL;
  delete process.env.ALGENTA_DISABLE_CLOUD;
  delete process.env.ALGENTA_ALLOW_OUTBOUND_NETWORK;
  delete process.env.ALGENTA_EGRESS_ALLOWLIST;
  delete process.env.ALGENTA_DEPLOYMENT_MODE;
  delete process.env.ALGENTA_API_KEY;
  delete process.env.DE_API_KEY;
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

afterEach(() => {
  const runtimeDir = process.env.ALGENTA_RUNTIME_DIR;
  for (const key of Object.keys(process.env)) {
    if (!(key in ORIGINAL_ENV)) {
      delete process.env[key];
    }
  }
  Object.assign(process.env, ORIGINAL_ENV);
  if (runtimeDir && runtimeDir.includes("algenta-ts-runtime-")) {
    rmSync(runtimeDir, { force: true, recursive: true });
  }
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Runtime — rejects_a", () => {
    it("rejects unsupported filter operators during local query", async () => {
      const runtime = new Runtime();
      await runtime.connect([{ product_line: "Electronics", revenue: 10, region: "US" }], { name: "orders" });
      const plan = await runtime.resolve({
        source_name: "orders",
        metric: "revenue",
      });

      await expect(
        runtime.query({
          ...(plan.resolved_plan ?? {}),
          filter: {
            conditions: [{ dimension_hint: "region", op: "contains", value: "US" }],
          },
        }),
      ).rejects.toMatchObject({
        code: "invalid_filter_condition",
        message: "Unsupported filter operator 'contains'.",
      });
    });

    it("rejects invalid scalar and list filter payload shapes during local query", async () => {
      const runtime = new Runtime();
      await runtime.connect([{ product_line: "Electronics", revenue: 10, region: "US" }], { name: "orders" });
      const plan = await runtime.resolve({
        source_name: "orders",
        metric: "revenue",
      });

      await expect(
        runtime.query({
          ...(plan.resolved_plan ?? {}),
          filter: {
            conditions: [{ dimension_hint: "region", op: "in", value: "US" }],
          },
        }),
      ).rejects.toMatchObject({
        code: "invalid_filter_condition",
        message: "filter condition op='in' does not accept value",
      });
    });

    it("rejects schema revision mismatch in local query", async () => {
      const runtime = new Runtime();
      await runtime.connect([{ product_line: "Electronics", revenue: 10 }], { name: "orders" });
      const plan = await runtime.resolve({
        source_name: "orders",
        metric: "revenue",
        group_by: "product_line",
      });

      await expect(
        runtime.query({
          ...(plan.resolved_plan ?? {}),
          schema_revision: "stale-schema",
        }),
      ).rejects.toBeInstanceOf(RuntimeValidationError);
    });

    it("rejects duplicate runtime manifest release conditions returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeManifest: async () => {
            const manifest = makeRuntimeManifestPayload();
            (manifest.formal_release_theorem.required_conditions as Array<string>).push(
              "manifest-listed",
            );
            return manifest;
          },
        } as never,
      });

      const manifestPromise = runtime.getRuntimeManifest();

      await expect(manifestPromise).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: expect.stringContaining("formal_release_theorem.required_conditions"),
          },
        },
      });
      await expect(manifestPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "formal_release_theorem.required_conditions" &&
          error.fieldErrors[0]?.path === "formal_release_theorem.required_conditions",
      );
    });

    it("rejects runtime manifest artifact kind drift returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeManifest: async () => {
            const manifest = makeRuntimeManifestPayload();
            (manifest.compiled_artifacts as Array<Record<string, unknown>>)[0]!.kind =
              "ghost_bundle";
            return manifest;
          },
        } as never,
      });

      const manifestPromise = runtime.getRuntimeManifest();

      await expect(manifestPromise).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: "compiled_artifacts.0.kind",
          },
        },
      });
      await expect(manifestPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "compiled_artifacts.0.kind" &&
          error.fieldErrors[0]?.path === "compiled_artifacts.0.kind",
      );
    });

    it("rejects duplicate runtime manifest module public channels returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeManifest: async () => {
            const manifest = makeRuntimeManifestPayload();
            (
              (manifest.modules as Array<Record<string, unknown>>)[0]!
                .public_supported_channels as Array<string>
            ).push("python_sdk");
            return manifest;
          },
        } as never,
      });

      const manifestPromise = runtime.getRuntimeManifest();

      await expect(manifestPromise).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: "modules.0.public_supported_channels",
          },
        },
      });
      await expect(manifestPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "modules.0.public_supported_channels" &&
          error.fieldErrors[0]?.path === "modules.0.public_supported_channels",
      );
    });

    it("rejects duplicate runtime manifest module functions returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeManifest: async () => {
            const manifest = makeRuntimeManifestPayload();
            (
              (manifest.modules as Array<Record<string, unknown>>)[0]!.functions as Array<string>
            ).push(
              ((manifest.modules as Array<Record<string, unknown>>)[0]!
                .functions as Array<string>)[0]!,
            );
            return manifest;
          },
        } as never,
      });

      const manifestPromise = runtime.getRuntimeManifest();

      await expect(manifestPromise).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: "modules.0.functions",
          },
        },
      });
      await expect(manifestPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "modules.0.functions" &&
          error.fieldErrors[0]?.path === "modules.0.functions",
      );
    });

    it("rejects invalid runtime manifest kernel promotion status returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeManifest: async () => {
            const manifest = makeRuntimeManifestPayload();
            (manifest.modules as Array<Record<string, unknown>>)[0]!.promotion_status = "graduated";
            return manifest;
          },
        } as never,
      });

      const manifestPromise = runtime.getRuntimeManifest();

      await expect(manifestPromise).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: "modules.0.promotion_status",
          },
        },
      });
      await expect(manifestPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "modules.0.promotion_status" &&
          error.fieldErrors[0]?.path === "modules.0.promotion_status",
      );
    });

    it("rejects missing runtime manifest replay proof refs for shipping kernels returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeManifest: async () => {
            const manifest = makeRuntimeManifestPayload();
            delete (manifest.modules as Array<Record<string, unknown>>)[0]!.replay_proof_ref;
            return manifest;
          },
        } as never,
      });

      const manifestPromise = runtime.getRuntimeManifest();

      await expect(manifestPromise).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: "modules.0.replay_proof_ref",
          },
        },
      });
      await expect(manifestPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "modules.0.replay_proof_ref" &&
          error.fieldErrors[0]?.path === "modules.0.replay_proof_ref",
      );
    });

    it("rejects runtime manifest benchmark shipping function count drift returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeManifest: async () => {
            const manifest = makeRuntimeManifestPayload();
            (manifest.benchmark_discovery_lane as Record<string, unknown>).shipping_manifest_functions =
              999;
            return manifest;
          },
        } as never,
      });

      const manifestPromise = runtime.getRuntimeManifest();

      await expect(manifestPromise).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: "benchmark_discovery_lane.shipping_manifest_functions",
          },
        },
      });
      await expect(manifestPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path ===
            "benchmark_discovery_lane.shipping_manifest_functions" &&
          error.fieldErrors[0]?.path ===
            "benchmark_discovery_lane.shipping_manifest_functions",
      );
    });

    it("rejects invalid runtime benchmark discovery rules returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeManifest: async () => {
            const manifest = makeRuntimeManifestPayload();
            (manifest.shipping_contract as Record<string, unknown>).benchmark_discovery_rule =
              "shadow_runtime_contract";
            return manifest;
          },
        } as never,
      });

      const manifestPromise = runtime.getRuntimeManifest();

      await expect(manifestPromise).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: "shipping_contract.benchmark_discovery_rule",
          },
        },
      });
      await expect(manifestPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "shipping_contract.benchmark_discovery_rule" &&
          error.fieldErrors[0]?.path === "shipping_contract.benchmark_discovery_rule",
      );
    });

    it("rejects runtime admin summary function count drift returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeModules: async () => {
            const payload = makeRuntimeAdminModulesPayload();
            (payload.summary as Record<string, unknown>).function_count = 999;
            return payload;
          },
        } as never,
      });

      const modulesPromise = runtime.getRuntimeModules();

      await expect(modulesPromise).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: "summary.function_count",
          },
        },
      });
      await expect(modulesPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "summary.function_count" &&
          error.fieldErrors[0]?.path === "summary.function_count",
      );
    });

    it("rejects invalid runtime benchmark discovery rules in admin modules returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeModules: async () => {
            const payload = makeRuntimeAdminModulesPayload();
            (payload.shipping_contract as Record<string, unknown>).benchmark_discovery_rule =
              "shadow_runtime_contract";
            return payload;
          },
        } as never,
      });

      const modulesPromise = runtime.getRuntimeModules();

      await expect(modulesPromise).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: "shipping_contract.benchmark_discovery_rule",
          },
        },
      });
      await expect(modulesPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "shipping_contract.benchmark_discovery_rule" &&
          error.fieldErrors[0]?.path === "shipping_contract.benchmark_discovery_rule",
      );
    });

    it("rejects duplicate runtime benchmark compiled artifacts returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeBenchmarks: async () => {
            const payload = makeRuntimeAdminBenchmarksPayload();
            (payload.compiled_artifacts as Array<Record<string, unknown>>).push({
              ...(payload.compiled_artifacts as Array<Record<string, unknown>>)[0]!,
            });
            return payload;
          },
        } as never,
      });

      const benchmarksPromise = runtime.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: "compiled_artifacts",
          },
        },
      });
      await expect(benchmarksPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "compiled_artifacts" &&
          error.fieldErrors[0]?.path === "compiled_artifacts",
      );
    });

    it("rejects invalid runtime non-shipping rules in admin benchmarks returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeBenchmarks: async () => {
            const payload = makeRuntimeAdminBenchmarksPayload();
            (payload.benchmark_discovery_lane as Record<string, unknown>).non_shipping_rule =
              "shadow_inventory_lane";
            return payload;
          },
        } as never,
      });

      const benchmarksPromise = runtime.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: "benchmark_discovery_lane.non_shipping_rule",
          },
        },
      });
      await expect(benchmarksPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "benchmark_discovery_lane.non_shipping_rule" &&
          error.fieldErrors[0]?.path === "benchmark_discovery_lane.non_shipping_rule",
      );
    });

    it("rejects runtime benchmark compiled artifact reference drift returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeBenchmarks: async () => {
            const payload = makeRuntimeAdminBenchmarksPayload();
            (payload.module_benchmarks as Array<Record<string, unknown>>)[0]!.compiled_artifact =
              "build/missing-runtime-benchmark.json";
            (payload.shipping_runtime_compiled_artifacts as Array<string>)[0] =
              "build/missing-runtime-benchmark.json";
            return payload;
          },
        } as never,
      });

      const benchmarksPromise = runtime.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: "module_benchmarks.0.compiled_artifact",
          },
        },
      });
      await expect(benchmarksPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "module_benchmarks.0.compiled_artifact" &&
          error.fieldErrors[0]?.path === "module_benchmarks.0.compiled_artifact",
      );
    });

    it("rejects runtime benchmark shipping function count drift returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeBenchmarks: async () => {
            const payload = makeRuntimeAdminBenchmarksPayload();
            (payload.shipping_runtime_function_counts as Array<number>)[0] = 3;
            return payload;
          },
        } as never,
      });

      const benchmarksPromise = runtime.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: "shipping_runtime_function_counts.0",
          },
        },
      });
      await expect(benchmarksPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "shipping_runtime_function_counts.0" &&
          error.fieldErrors[0]?.path === "shipping_runtime_function_counts.0",
      );
    });

    it("rejects runtime benchmark shipping speedup drift returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeBenchmarks: async () => {
            const payload = makeRuntimeAdminBenchmarksPayload();
            (payload.shipping_runtime_benchmark_speedups_x as Array<number>)[0] = 999;
            return payload;
          },
        } as never,
      });

      const benchmarksPromise = runtime.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: "shipping_runtime_benchmark_speedups_x.0",
          },
        },
      });
      await expect(benchmarksPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "shipping_runtime_benchmark_speedups_x.0" &&
          error.fieldErrors[0]?.path === "shipping_runtime_benchmark_speedups_x.0",
      );
    });

    it("rejects non-positive runtime benchmark speedup metrics returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeBenchmarks: async () => {
            const payload = makeRuntimeAdminBenchmarksPayload();
            (payload.shipping_runtime_benchmark_speedups_x as Array<number>)[0] = 0;
            (payload.module_benchmarks as Array<Record<string, unknown>>)[0]!.benchmark_speedup_x =
              0;
            return payload;
          },
        } as never,
      });

      const benchmarksPromise = runtime.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: "module_benchmarks.0.benchmark_speedup_x",
          },
        },
      });
      await expect(benchmarksPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "module_benchmarks.0.benchmark_speedup_x" &&
          error.fieldErrors[0]?.path === "module_benchmarks.0.benchmark_speedup_x",
      );
    });
});
