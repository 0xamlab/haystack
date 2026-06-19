// Tests for DecisionEngineClient: reuses.
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

describe("DecisionEngineClient — reuses", () => {

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

    it("reuses a hosted binding token on later requests from the same client", async () => {
      const runtimeDir = fs.mkdtempSync(path.join(os.tmpdir(), "algenta-ts-binding-"));
      process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
      process.env.ALGENTA_DEVICE_ID = "ts-device-00000001";
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeQueryResponse()), {
            status: 200,
            headers: {
              "Content-Type": "application/json",
              "X-Algenta-Device-Binding-Token": "binding-token-000000000000000001",
            },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeQueryResponse()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      vi.stubGlobal("fetch", fetchMock);

      try {
        const client = new DecisionEngineClient({
          apiKey: "de_test_123",
          baseUrl: "https://example.test",
          maxRetries: 0,
          timeout: 1_000,
        });

        await client.query({
          source_name: "orders",
          metric_column: "revenue",
          aggregation: "sum",
        });
        await client.query({
          source_name: "orders",
          metric_column: "revenue",
          aggregation: "sum",
        });

        expect(fetchMock.mock.calls[1]?.[1]).toEqual(
          expect.objectContaining({
            headers: expect.objectContaining({
              "X-Algenta-Device-Binding-Token": "binding-token-000000000000000001",
            }),
          }),
        );
      } finally {
        fs.rmSync(runtimeDir, { recursive: true, force: true });
      }
    });

    it("reuses a hosted binding token across new clients when disk persistence is unavailable", async () => {
      process.env.ALGENTA_DEVICE_ID = "ts-device-00000001";
      const fsStub = {
        readFileSync: vi.fn(() => {
          throw new Error("binding token file unavailable");
        }),
        existsSync: vi.fn(() => false),
        mkdirSync: vi.fn(() => {
          throw new Error("runtime dir is read only");
        }),
        writeFileSync: vi.fn(() => {
          throw new Error("runtime dir is read only");
        }),
        renameSync: vi.fn(() => {
          throw new Error("runtime dir is read only");
        }),
      };
      const osStub = {
        homedir: vi.fn(() => "/read-only-home"),
      };
      const pathStub = {
        join: (...parts: string[]) => parts.join("/"),
      };
      vi.spyOn(process, "getBuiltinModule").mockImplementation(
        ((name: string): unknown => {
          if (name === "node:fs" || name === "fs") {
            return fsStub;
          }
          if (name === "node:os" || name === "os") {
            return osStub;
          }
          if (name === "node:path" || name === "path") {
            return pathStub;
          }
          return undefined;
        }) as typeof process.getBuiltinModule,
      );
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeQueryResponse()), {
            status: 200,
            headers: {
              "Content-Type": "application/json",
              "X-Algenta-Device-Binding-Token": "binding-token-000000000000000001",
            },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeQueryResponse()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      vi.stubGlobal("fetch", fetchMock);

      const firstClient = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });
      await firstClient.query({
        source_name: "orders",
        metric_column: "revenue",
        aggregation: "sum",
      });

      const secondClient = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });
      await secondClient.query({
        source_name: "orders",
        metric_column: "revenue",
        aggregation: "sum",
      });

      expect(fetchMock.mock.calls[1]?.[1]).toEqual(
        expect.objectContaining({
          headers: expect.objectContaining({
            "X-Algenta-Device-Binding-Token": "binding-token-000000000000000001",
          }),
        }),
      );
    });
});
