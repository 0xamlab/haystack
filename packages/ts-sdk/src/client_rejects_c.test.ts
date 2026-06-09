// Tests for DecisionEngineClient: rejects_c.
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

describe("DecisionEngineClient — rejects_c", () => {

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

    it("rejects invalid signed runtime release validation payloads", async () => {
      const payload = makeRuntimeReleaseValidationPayload();
      (payload.conditions as Array<Record<string, unknown>>)[0]!.condition = "teleport-validated";

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

      const validationPromise = client.getRuntimeReleaseValidation();

      await expect(validationPromise).rejects.toThrow("invalid signed payload");
      await validationPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("conditions.0.condition");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "conditions.0.condition",
        });
      });
    });

    it("rejects duplicate runtime release validation evidence paths", async () => {
      const payload = makeRuntimeReleaseValidationPayload();
      (
        (payload.conditions as Array<Record<string, unknown>>)[0]!.evidence_paths as Array<string>
      ).push(
        (
          (payload.conditions as Array<Record<string, unknown>>)[0]!
            .evidence_paths as Array<string>
        )[0]!,
      );

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

      const validationPromise = client.getRuntimeReleaseValidation();

      await expect(validationPromise).rejects.toThrow("invalid signed payload");
      await validationPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("conditions.0.evidence_paths");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "conditions.0.evidence_paths",
        });
      });
    });

    it("rejects invalid execution policy update input before sending the request", async () => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      await expect(client.updateExecutionPolicy({})).rejects.toThrow("at least one field");
      await expect(
        client.updateExecutionPolicy({ min_confidence: 1.2 }),
      ).rejects.toThrow("min_confidence");
      await expect(client.updateExecutionPolicy({ risk_floor: -1 })).rejects.toThrow("risk_floor");
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("rejects invalid team mutation input before sending the request", async () => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      await expect(client.inviteTeamMember({ email: "invalid-email" })).rejects.toThrow("valid email");
      await expect(client.updateTeamMemberRole("user_123", "superadmin" as never)).rejects.toThrow(
        "updateTeamMemberRole.role",
      );
      await expect(client.removeTeamMember("")).rejects.toThrow("non-empty userId");
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("rejects invalid device revoke input before sending the request", async () => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      await expect(client.revokeDevice("")).rejects.toThrow("registrationId");
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("rejects invalid metering input before sending the request", async () => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      await expect(
        client.ingestMeteringEvents({ device_id: "", events: [{ event_type: "query" }] }),
      ).rejects.toThrow("device_id");
      await expect(
        client.ingestMeteringEvents({ device_id: "device_123", events: [] }),
      ).rejects.toThrow("events array");
      await expect(
        client.ingestMeteringEvents({
          device_id: "device_123",
          events: [{ event_type: "query", unexpected: true } as never],
        }),
      ).rejects.toThrow("unsupported field");
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("rejects invalid credit refresh input before sending the request", async () => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      await expect(
        client.refreshCredits({ device_id: "", billing_period: "2026-05" }),
      ).rejects.toThrow("device_id");
      await expect(
        client.refreshCredits({ device_id: "device_123", billing_period: "202605" }),
      ).rejects.toThrow("billing_period");
      await expect(
        client.refreshCredits({ device_id: "device_123", billing_period: "2026-13" }),
      ).rejects.toThrow("billing_period month");
      await expect(
        client.refreshCredits({ device_id: "device_123", billing_period: "2026-05", credits_used: -1 }),
      ).rejects.toThrow("credits_used");
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("rejects invalid API key create input before sending the request", async () => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      await expect(
        client.createApiKey({
          label: "Mission Enterprise Key",
          device_limit: -1,
        }),
      ).rejects.toThrow("device_limit");
      await expect(
        client.createApiKey({
          label: "Mission Enterprise Key",
          expires_at: new Date("not-a-date"),
        }),
      ).rejects.toThrow("expires_at");
      await expect(
        client.createApiKey({
          label: "   ",
        }),
      ).rejects.toThrow("label");
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("rejects leaked raw_key fields in API key list responses", async () => {
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify([
            {
              id: "key_1",
              label: "Leaked Key",
              key_prefix: "de_live_abcd",
              raw_key: "de_live_abcd_secret_value",
              status: "active",
              created_at: "2026-05-19T00:00:00Z",
            },
          ]),
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

      await expect(client.listApiKeys()).rejects.toThrow("one-time secret material");
    });
});
