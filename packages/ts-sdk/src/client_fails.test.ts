// SPDX-License-Identifier: Apache-2.0
// Tests for DecisionEngineClient: fails.
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

describe("DecisionEngineClient — fails", () => {

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

    it("fails closed in private profiles without a self-hosted baseUrl", () => {
      process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
      process.env.ALGENTA_DISABLE_CLOUD = "1";

      try {
        new DecisionEngineClient({
          apiKey: "de_test_123",
        });
        throw new Error("expected DecisionEngineClient to fail closed");
      } catch (error) {
        expect(String(error)).toContain("private profiles cannot target Algenta-owned cloud URLs");
        expect(String(error)).toContain("ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL");
      }
    });

    it("fails fast when pollJob reaches a terminal failed status", async () => {
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            job_id: "11111111-1111-1111-1111-111111111111",
            run_id: "22222222-2222-2222-2222-222222222222",
            org_id: "33333333-3333-3333-3333-333333333333",
            status: "failed",
            queue_name: "default",
            retry_count: 0,
            callback_status: "pending",
            created_at: "2026-05-24T12:00:00Z",
            error_message: "worker crashed",
            poll_url: "https://example.test/v1/jobs/11111111-1111-1111-1111-111111111111",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      await expect(
        client.pollJob("11111111-1111-1111-1111-111111111111", {
          timeoutMs: 1_000,
          pollIntervalMs: 50,
        }),
      ).rejects.toThrow("worker crashed");
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it("fails with a typed timeout when pollJob does not complete in time", async () => {
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            job_id: "11111111-1111-1111-1111-111111111111",
            run_id: "22222222-2222-2222-2222-222222222222",
            org_id: "33333333-3333-3333-3333-333333333333",
            status: "running",
            queue_name: "default",
            retry_count: 0,
            callback_status: "pending",
            created_at: "2026-05-24T12:00:00Z",
            poll_url: "https://example.test/v1/jobs/11111111-1111-1111-1111-111111111111",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
      vi.stubGlobal("fetch", fetchMock);
      vi.useFakeTimers();

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const pollPromise = client.pollJob("11111111-1111-1111-1111-111111111111", {
        timeoutMs: 60,
        pollIntervalMs: 25,
      });
      const assertion = expect(pollPromise).rejects.toThrow("timed out after 60ms");
      await vi.advanceTimersByTimeAsync(75);
      await assertion;
      expect(fetchMock).toHaveBeenCalledTimes(3);
      vi.useRealTimers();
    });

    it("fails closed on non-object error payloads without throwing a TypeError", async () => {
      const fetchMock = vi.fn().mockResolvedValueOnce(
        new Response("null", {
          status: 409,
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

      await expect(client.createDeployment()).rejects.toThrow("Unknown error");
    });
});
