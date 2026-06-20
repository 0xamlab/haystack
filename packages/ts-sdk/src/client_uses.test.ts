// Tests for DecisionEngineClient: uses.
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

describe("DecisionEngineClient — uses", () => {

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

    it("uses ALGENTA_BASE_URL in private profiles when provided", async () => {
      process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
      process.env.ALGENTA_DISABLE_CLOUD = "1";
      process.env.ALGENTA_BASE_URL = "http://localhost:8000";
      const fetchMock = vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(makeQueryResponse()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
      });

      await client.query({
        source_name: "orders",
        metric_column: "revenue",
        aggregation: "sum",
      });

      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/v1/query",
        expect.objectContaining({
          method: "POST",
        }),
      );
    });

    it("uses ALGENTA_API_URL in private profiles when baseUrl env vars are otherwise unset", async () => {
      process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
      process.env.ALGENTA_DISABLE_CLOUD = "1";
      delete process.env.ALGENTA_BASE_URL;
      delete process.env.DE_BASE_URL;
      process.env.ALGENTA_API_URL = "http://localhost:8000";
      const fetchMock = vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(makeQueryResponse()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
      });

      await client.query({
        source_name: "orders",
        metric_column: "revenue",
        aggregation: "sum",
      });

      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/v1/query",
        expect.objectContaining({
          method: "POST",
        }),
      );
    });

    it("uses cloud-managed API key guidance when apiKey is missing", () => {
      expect(
        () =>
          new DecisionEngineClient({
            baseUrl: "https://api.algenta.ai",
          }),
      ).toThrow("https://app.algenta.ai/dashboard/api-keys");
    });

    it("uses self-hosted API key guidance in private profiles when apiKey is missing", () => {
      process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
      process.env.ALGENTA_DISABLE_CLOUD = "1";
      process.env.ALGENTA_BASE_URL = "http://localhost:8000";

      try {
        new DecisionEngineClient({
          baseUrl: "http://localhost:8000",
        });
        throw new Error("expected DecisionEngineClient to require an API key");
      } catch (error) {
        expect(String(error)).toContain("ALGENTA_API_KEY / DE_API_KEY environment variables");
        expect(String(error)).toContain(
          "Create a key from your self-hosted admin surface or API base URL: http://localhost:8000",
        );
      }
    });
});
