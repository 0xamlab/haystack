// Tests for Runtime: rejects_b.
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

describe("Runtime — rejects_b", () => {
    it("rejects runtime benchmark shipping module identity drift returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeBenchmarks: async () => {
            const payload = makeRuntimeAdminBenchmarksPayload();
            (payload.shipping_runtime_modules as Array<string>)[0] = "embeddings";
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
            cause: "shipping_runtime_modules.0",
          },
        },
      });
      await expect(benchmarksPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "shipping_runtime_modules.0" &&
          error.fieldErrors[0]?.path === "shipping_runtime_modules.0",
      );
    });

    it("rejects runtime benchmark shipping artifact drift returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeBenchmarks: async () => {
            const payload = makeRuntimeAdminBenchmarksPayload();
            (payload.shipping_runtime_benchmark_artifacts as Array<string>)[0] =
              "benchmarks/results/embeddings.json";
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
            cause: "shipping_runtime_benchmark_artifacts.0",
          },
        },
      });
      await expect(benchmarksPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "shipping_runtime_benchmark_artifacts.0" &&
          error.fieldErrors[0]?.path === "shipping_runtime_benchmark_artifacts.0",
      );
    });

    it("rejects runtime benchmark shipping compiled artifact drift returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeBenchmarks: async () => {
            const payload = makeRuntimeAdminBenchmarksPayload();
            (payload.shipping_runtime_compiled_artifacts as Array<string>)[0] =
              "mojo_build/embeddings";
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
            cause: "shipping_runtime_compiled_artifacts.0",
          },
        },
      });
      await expect(benchmarksPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "shipping_runtime_compiled_artifacts.0" &&
          error.fieldErrors[0]?.path === "shipping_runtime_compiled_artifacts.0",
      );
    });

    it("rejects runtime benchmark shipping compiled engine drift returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeBenchmarks: async () => {
            const payload = makeRuntimeAdminBenchmarksPayload();
            (payload.shipping_runtime_compiled_engines as Array<string>)[0] =
              "python_fallback";
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
            cause: "shipping_runtime_compiled_engines.0",
          },
        },
      });
      await expect(benchmarksPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "shipping_runtime_compiled_engines.0" &&
          error.fieldErrors[0]?.path === "shipping_runtime_compiled_engines.0",
      );
    });

    it("rejects runtime benchmark SLO budget applies_to drift returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeBenchmarks: async () => {
            const payload = makeRuntimeAdminBenchmarksPayload();
            (payload.slo_budgets as Array<Record<string, unknown>>)[0]!.applies_to =
              "shadow_realm_lane";
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
            cause: "slo_budgets.0.applies_to",
          },
        },
      });
      await expect(benchmarksPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "slo_budgets.0.applies_to" &&
          error.fieldErrors[0]?.path === "slo_budgets.0.applies_to",
      );
    });

    it.each([
      ["shipping_runtime_max_cold_ms", "max_cold_ms", 999],
      ["shipping_runtime_max_warm_ms", "max_warm_ms", 999],
      ["shipping_runtime_max_hot_ms", "max_hot_ms", 999],
    ])(
      "rejects runtime benchmark %s drift returned by the injected client",
      async (shippingField, _benchmarkField, badValue) => {
        const runtime = new Runtime({
          mode: "self_hosted",
          apiKey: "de_test_123",
          baseUrl: "http://localhost:8000",
          client: {
            getRuntimeBenchmarks: async () => {
              const payload = makeRuntimeAdminBenchmarksPayload();
              (payload[shippingField] as Array<number>)[0] = badValue;
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
              cause: `${shippingField}.0`,
            },
          },
        });
        await expect(benchmarksPromise).rejects.toSatisfy(
          (error: unknown) =>
            error instanceof RuntimeValidationError &&
            error.validationErrors[0]?.path === `${shippingField}.0` &&
            error.fieldErrors[0]?.path === `${shippingField}.0`,
        );
      },
    );

    it("rejects duplicate runtime benchmark artifact paths returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeBenchmarks: async () => {
            const payload = makeRuntimeAdminBenchmarksPayload();
            (payload.benchmark_discovery_lane as Record<string, unknown>).shipping_manifest_modules = 2;
            (payload.benchmark_discovery_lane as Record<string, unknown>).shipping_manifest_functions =
              4;
            (payload.shipping_runtime_modules as Array<string>).push("embeddings");
            (payload.shipping_runtime_function_counts as Array<number>).push(2);
            (payload.shipping_runtime_benchmark_speedups_x as Array<number>).push(101.0);
            (payload.shipping_runtime_benchmark_artifacts as Array<string>).push(
              "build/bench.json",
            );
            (payload.shipping_runtime_compiled_artifacts as Array<string>).push(
              "mojo_build/bpe_tokenizer",
            );
            (payload.shipping_runtime_compiled_engines as Array<string>).push("mojo");
            (payload.shipping_runtime_max_cold_ms as Array<number>).push(12.0);
            (payload.shipping_runtime_max_warm_ms as Array<number>).push(4.0);
            (payload.shipping_runtime_max_hot_ms as Array<number>).push(2.0);
            (payload.module_benchmarks as Array<Record<string, unknown>>).push({
              ...(payload.module_benchmarks as Array<Record<string, unknown>>)[0]!,
              name: "embeddings",
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
            cause: "module_benchmarks.1.benchmark_artifact",
          },
        },
      });
      await expect(benchmarksPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "module_benchmarks.1.benchmark_artifact" &&
          error.fieldErrors[0]?.path === "module_benchmarks.1.benchmark_artifact",
      );
    });

    it("rejects duplicate runtime release validation evidence paths returned by the injected client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeReleaseValidation: async () => {
            const payload = makeRuntimeReleaseValidationPayload();
            (
              (payload.conditions as Array<Record<string, unknown>>)[0]!
                .evidence_paths as Array<string>
            ).push(
              (
                (payload.conditions as Array<Record<string, unknown>>)[0]!
                  .evidence_paths as Array<string>
              )[0]!,
            );
            return payload;
          },
        } as never,
      });

      const validationPromise = runtime.getRuntimeReleaseValidation();

      await expect(validationPromise).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: "conditions.0.evidence_paths",
          },
        },
      });
      await expect(validationPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "conditions.0.evidence_paths" &&
          error.fieldErrors[0]?.path === "conditions.0.evidence_paths",
      );
    });

    it("rejects remote canonical connectors in local mode", async () => {
      const runtime = new Runtime();

      await expect(
        runtime.connect({
          type: "postgres",
          location: {
            host: "localhost",
            port: 5432,
            database: "orders",
            schema: "public",
            table: "orders",
          },
          auth: {
            credentials: {
              user: "analytics",
              password: "secret",
            },
          },
        }),
      ).rejects.toMatchObject({ code: "unsupported_local_connector" });
    });

    it("rejects empty real csv exports", async () => {
      const runtime = new Runtime();

      await expect(runtime.connect(REAL_MARCH_EMPTY, { name: "store_pause" })).rejects.toBeInstanceOf(
        RuntimeValidationError,
      );
    });

    it("rejects a stored license when the trusted floor passed hard expiry despite a rolled-back wall clock", async () => {
      const runtimeDir = runtimeTempDir();
      process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
      process.env.ALGENTA_JWT_SECRET = "ts-runtime-test-secret";
      const expiresAt = 1_900_000_000;
      seedStoredLicense(runtimeDir, "de_live_ts_runtime_key", expiresAt);
      seedTrustedTime(runtimeDir, expiresAt + 14 * 86_400 + 5);
      vi.spyOn(Date, "now").mockReturnValue((expiresAt - 86_400) * 1000);
      vi.spyOn(performance, "now").mockReturnValue(0);
      const fetchSpy = vi.fn(async () => {
        throw new Error("offline");
      });
      vi.stubGlobal("fetch", fetchSpy);

      const runtime = new Runtime({ apiKey: "de_live_ts_runtime_key" });
      await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
      const plan = await runtime.resolve({
        source_name: "orders_detail",
        metric: "Sales (incl. tax)",
        group_by: "Order Channel",
      });

      await expect(runtime.query(plan)).rejects.toMatchObject({
        code: "license_required",
        message: expect.stringContaining("renew"),
      });
      expect(fetchSpy).not.toHaveBeenCalled();
    });
});
