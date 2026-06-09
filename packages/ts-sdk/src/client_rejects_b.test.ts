// Tests for DecisionEngineClient: rejects_b.
// Extracted from client.test.ts during modularization.
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DecisionEngineClient, DecisionEngineError, ServerError } from "./client.js";
import { HOSTNAME_HASH_HEADER } from "./client_device_headers.js";
import { clearHostedDeviceBindingTokenCacheForTests } from "./client_device_binding.js";
import { expectManifestBackedIntegrationsEqual } from "./test_contract_helpers.js";
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
  makeQueryResponse,
  makeLLMModelsPayload,
  makeDecisionPlanPayload,
  makeProductDecisionPayload,
  makeProductAgentRunPayload,
  makeProductOptimizePayload,
  makeProductRetrievePayload,
  makeProductForecastPayload,
  makeDecisionLogPayload,
  makeDecisionListPayload,
  makeExecutionReceiptPayload,
  makeDecisionEnvelopePayload,
  makeRecommendPayload,
  makeScorePayload,
  makeComparePayload,
  makeAgentRunPayload,
  makeAgentRunEventsPayload,
  makeAgentRunListPayload,
  makeAgentRunCheckpointsPayload,
  makeAgentRunMissionEventsPayload,
  makeAgentRunMissionEventQueryPayload,
  makeAgentRunCheckpointQueryPayload,
  makeAgentRunReplayPayload,
  makeAgentRunTelemetryPayload,
  makeAgentRunTelemetryQueryPayload,
  cloneJsonValue,
  makeContractPayload,
  makeRuntimeManifestPayload,
  makeRuntimeAdminModulesPayload,
  makeRuntimeAdminBenchmarksPayload,
  makeRuntimeReleaseValidationPayload,
} from "./_client_test_helpers.js";

describe("DecisionEngineClient — rejects_b", () => {

    afterEach(() => {
      vi.restoreAllMocks();
      vi.unstubAllGlobals();
      clearHostedDeviceBindingTokenCacheForTests();
      delete process.env.ALGENTA_DEVICE_ID;
      delete process.env.DE_DEVICE_ID;
      delete process.env.ALGENTA_DEPLOYMENT_MODE;
      delete process.env.ALGENTA_DISABLE_CLOUD;
      delete process.env.ALGENTA_BASE_URL;
      delete process.env.DE_BASE_URL;
      delete process.env.ALGENTA_API_URL;
      delete process.env.ALGENTA_APP_BASE_URL;
      delete process.env.APP_BASE_URL;
      delete process.env.DE_APP_BASE_URL;
      delete process.env.ALGENTA_RUNTIME_DIR;
    });

    it("rejects invalid signed runtime admin module payloads", async () => {
      const payload = makeRuntimeAdminModulesPayload();
      (payload.proof_matrix as Array<Record<string, unknown>>)[0]!.status = "unknown_status";

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const modulesPromise = client.getRuntimeModules();

      await expect(modulesPromise).rejects.toThrow("invalid signed payload");
      await modulesPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("proof_matrix.0.status");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "proof_matrix.0.status",
        });
      });
    });

    it("rejects invalid runtime benchmark discovery rules in admin modules", async () => {
      const payload = makeRuntimeAdminModulesPayload();
      (payload.shipping_contract as Record<string, unknown>).benchmark_discovery_rule =
        "shadow_runtime_contract";

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const modulesPromise = client.getRuntimeModules();

      await expect(modulesPromise).rejects.toThrow("invalid signed payload");
      await modulesPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("shipping_contract.benchmark_discovery_rule");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "shipping_contract.benchmark_discovery_rule",
        });
      });
    });

    it("rejects duplicate runtime admin proof matrix layers", async () => {
      const payload = makeRuntimeAdminModulesPayload();
      (payload.proof_matrix as Array<Record<string, unknown>>).push({
        ...(payload.proof_matrix as Array<Record<string, unknown>>)[0]!,
      });

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const modulesPromise = client.getRuntimeModules();

      await expect(modulesPromise).rejects.toThrow("invalid signed payload");
      await modulesPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("proof_matrix");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "proof_matrix",
        });
      });
    });

    it("rejects runtime admin summary function count drift", async () => {
      const payload = makeRuntimeAdminModulesPayload();
      (payload.summary as Record<string, unknown>).function_count = 999;

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const modulesPromise = client.getRuntimeModules();

      await expect(modulesPromise).rejects.toThrow("invalid signed payload");
      await modulesPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("summary.function_count");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "summary.function_count",
        });
      });
    });

    it("rejects invalid signed runtime benchmark payloads", async () => {
      const payload = makeRuntimeAdminBenchmarksPayload();
      (payload.module_benchmarks as Array<Record<string, unknown>>)[0]!.compiled_engine =
        "warp_core";

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const benchmarksPromise = client.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
      await benchmarksPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("module_benchmarks.0.compiled_engine");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "module_benchmarks.0.compiled_engine",
        });
      });
    });

    it("rejects invalid runtime SLO budget applies_to values", async () => {
      const payload = makeRuntimeAdminBenchmarksPayload();
      (payload.slo_budgets as Array<Record<string, unknown>>)[0]!.applies_to = "shadow_realm_lane";

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const benchmarksPromise = client.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
      await benchmarksPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("slo_budgets.0.applies_to");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "slo_budgets.0.applies_to",
        });
      });
    });

    it("rejects invalid runtime non-shipping rules in admin benchmarks", async () => {
      const payload = makeRuntimeAdminBenchmarksPayload();
      (payload.benchmark_discovery_lane as Record<string, unknown>).non_shipping_rule =
        "shadow_inventory_lane";

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const benchmarksPromise = client.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
      await benchmarksPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("benchmark_discovery_lane.non_shipping_rule");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "benchmark_discovery_lane.non_shipping_rule",
        });
      });
    });

    it("rejects duplicate runtime benchmark classes", async () => {
      const payload = makeRuntimeAdminBenchmarksPayload();
      (payload.benchmarking.classes as Array<Record<string, unknown>>).push({
        ...(payload.benchmarking.classes as Array<Record<string, unknown>>)[0]!,
      });

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const benchmarksPromise = client.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
      await benchmarksPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("benchmarking.classes");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "benchmarking.classes",
        });
      });
    });

    it("rejects duplicate runtime benchmark compiled artifacts", async () => {
      const payload = makeRuntimeAdminBenchmarksPayload();
      (payload.compiled_artifacts as Array<Record<string, unknown>>).push({
        ...(payload.compiled_artifacts as Array<Record<string, unknown>>)[0]!,
      });

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const benchmarksPromise = client.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
      await benchmarksPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("compiled_artifacts");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "compiled_artifacts",
        });
      });
    });

    it("rejects runtime benchmark shipping module count drift", async () => {
      const payload = makeRuntimeAdminBenchmarksPayload();
      (payload.benchmark_discovery_lane as Record<string, unknown>).shipping_manifest_modules = 2;

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const benchmarksPromise = client.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
      await benchmarksPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("benchmark_discovery_lane.shipping_manifest_modules");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "benchmark_discovery_lane.shipping_manifest_modules",
        });
      });
    });

    it("rejects runtime benchmark shipping function count drift", async () => {
      const payload = makeRuntimeAdminBenchmarksPayload();
      (payload.shipping_runtime_function_counts as Array<number>)[0] = 3;

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const benchmarksPromise = client.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
      await benchmarksPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("shipping_runtime_function_counts.0");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "shipping_runtime_function_counts.0",
        });
      });
    });

    it("rejects runtime benchmark shipping speedup drift", async () => {
      const payload = makeRuntimeAdminBenchmarksPayload();
      (payload.shipping_runtime_benchmark_speedups_x as Array<number>)[0] = 999;

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const benchmarksPromise = client.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
      await benchmarksPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("shipping_runtime_benchmark_speedups_x.0");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "shipping_runtime_benchmark_speedups_x.0",
        });
      });
    });

    it("rejects non-positive runtime benchmark speedup metrics", async () => {
      const payload = makeRuntimeAdminBenchmarksPayload();
      (payload.shipping_runtime_benchmark_speedups_x as Array<number>)[0] = 0;
      (payload.module_benchmarks as Array<Record<string, unknown>>)[0]!.benchmark_speedup_x = 0;

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const benchmarksPromise = client.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
      await benchmarksPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("module_benchmarks.0.benchmark_speedup_x");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "module_benchmarks.0.benchmark_speedup_x",
        });
      });
    });

    it("rejects runtime benchmark shipping module identity drift", async () => {
      const payload = makeRuntimeAdminBenchmarksPayload();
      (payload.shipping_runtime_modules as Array<string>)[0] = "embeddings";

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const benchmarksPromise = client.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
      await benchmarksPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("shipping_runtime_modules.0");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "shipping_runtime_modules.0",
        });
      });
    });

    it("rejects runtime benchmark shipping artifact drift", async () => {
      const payload = makeRuntimeAdminBenchmarksPayload();
      (payload.shipping_runtime_benchmark_artifacts as Array<string>)[0] =
        "benchmarks/results/embeddings.json";

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const benchmarksPromise = client.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
      await benchmarksPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("shipping_runtime_benchmark_artifacts.0");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "shipping_runtime_benchmark_artifacts.0",
        });
      });
    });

    it("rejects runtime benchmark shipping compiled artifact drift", async () => {
      const payload = makeRuntimeAdminBenchmarksPayload();
      (payload.shipping_runtime_compiled_artifacts as Array<string>)[0] =
        "mojo_build/embeddings";

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const benchmarksPromise = client.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
      await benchmarksPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("shipping_runtime_compiled_artifacts.0");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "shipping_runtime_compiled_artifacts.0",
        });
      });
    });

    it("rejects runtime benchmark shipping compiled engine drift", async () => {
      const payload = makeRuntimeAdminBenchmarksPayload();
      (payload.shipping_runtime_compiled_engines as Array<string>)[0] = "python_fallback";

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const benchmarksPromise = client.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
      await benchmarksPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("shipping_runtime_compiled_engines.0");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "shipping_runtime_compiled_engines.0",
        });
      });
    });

    it.each([
      ["shipping_runtime_max_cold_ms", "max_cold_ms", 999],
      ["shipping_runtime_max_warm_ms", "max_warm_ms", 999],
      ["shipping_runtime_max_hot_ms", "max_hot_ms", 999],
    ])(
      "rejects runtime benchmark %s drift",
      async (shippingField, _benchmarkField, badValue) => {
        const payload = makeRuntimeAdminBenchmarksPayload();
        (payload[shippingField] as Array<number>)[0] = badValue;

        const fetchMock = vi.fn().mockResolvedValue(
          new Response(JSON.stringify(payload), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
        vi.stubGlobal("fetch", fetchMock);

        const client = new DecisionEngineClient({
          apiKey: "de_test_123",
          baseUrl: "https://example.test",
          maxRetries: 0,
          timeout: 1_000,
        });

        const benchmarksPromise = client.getRuntimeBenchmarks();

        await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
        await benchmarksPromise.catch(error => {
          expect(error).toBeInstanceOf(DecisionEngineError);
          const details = (error as DecisionEngineError).details as Record<string, unknown>;
          expect(String(details.cause)).toContain(`${shippingField}.0`);
          expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
            path: `${shippingField}.0`,
          });
        });
      },
    );

    it("rejects runtime benchmark compiled artifact reference drift", async () => {
      const payload = makeRuntimeAdminBenchmarksPayload();
      (payload.module_benchmarks as Array<Record<string, unknown>>)[0]!.compiled_artifact =
        "build/missing-runtime-benchmark.json";
      (payload.shipping_runtime_compiled_artifacts as Array<string>)[0] =
        "build/missing-runtime-benchmark.json";

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const benchmarksPromise = client.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
      await benchmarksPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("module_benchmarks.0.compiled_artifact");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "module_benchmarks.0.compiled_artifact",
        });
      });
    });
});
