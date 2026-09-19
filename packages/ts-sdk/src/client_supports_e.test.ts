// SPDX-License-Identifier: Apache-2.0
// Tests for DecisionEngineClient: supports_e.
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

describe("DecisionEngineClient — supports_e", () => {

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

    it("supports typed metering ingest helpers", async () => {
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            accepted: 2,
            billing_period: "2026-05",
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

      const metering = await client.ingestMeteringEvents({
        device_id: "device_sdk_123",
        events: [
          { event_type: "query", latency_ms: 9.5, success: true },
          { module: "pricing", timestamp: 1716547200 },
        ],
      });

      expect(metering.accepted).toBe(2);
      expect(metering.billing_period).toBe("2026-05");
      expect(fetchMock).toHaveBeenCalledWith(
        "https://example.test/v1/metering",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            device_id: "device_sdk_123",
            events: [
              { event_type: "query", latency_ms: 9.5, success: true },
              { module: "pricing", timestamp: 1716547200 },
            ],
          }),
        }),
      );
    });

    it("supports typed credit refresh helpers", async () => {
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            credits_granted: 10000,
            credits_issued_this_month: 25000,
            monthly_limit: 500000,
            monthly_remaining: 475000,
            billing_period: "2026-05",
            expires_at: 1716547200,
            refresh_after: 1716545040,
            server_time: 1716460800,
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

      const refreshed = await client.refreshCredits({
        device_id: "device_sdk_123",
        billing_period: "2026-05",
        credits_used: 42,
      });

      expect(refreshed.credits_granted).toBe(10000);
      expect(refreshed.monthly_remaining).toBe(475000);
      expect(fetchMock).toHaveBeenCalledWith(
        "https://example.test/v1/credits/refresh",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            device_id: "device_sdk_123",
            billing_period: "2026-05",
            credits_used: 42,
          }),
        }),
      );
    });

    it("supports typed async job helpers", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              job_id: "11111111-1111-1111-1111-111111111111",
              poll_url: "https://example.test/v1/jobs/11111111-1111-1111-1111-111111111111",
              status: "queued",
            }),
            { status: 202, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              job_id: "11111111-1111-1111-1111-111111111111",
              run_id: "22222222-2222-2222-2222-222222222222",
              org_id: "33333333-3333-3333-3333-333333333333",
              status: "queued",
              queue_name: "default",
              retry_count: 0,
              callback_status: "pending",
              created_at: "2026-05-24T12:00:00Z",
              poll_url: "https://example.test/v1/jobs/11111111-1111-1111-1111-111111111111",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              job_id: "11111111-1111-1111-1111-111111111111",
              result: { score: 0.98 },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              jobs: [
                {
                  job_id: "11111111-1111-1111-1111-111111111111",
                  run_id: "22222222-2222-2222-2222-222222222222",
                  org_id: "33333333-3333-3333-3333-333333333333",
                  status: "queued",
                  queue_name: "default",
                  retry_count: 0,
                  callback_status: "pending",
                  created_at: "2026-05-24T12:00:00Z",
                  poll_url: "https://example.test/v1/jobs/11111111-1111-1111-1111-111111111111",
                },
              ],
              total: 1,
              page: 2,
              limit: 10,
              pages: 1,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              job_id: "11111111-1111-1111-1111-111111111111",
              run_id: "22222222-2222-2222-2222-222222222222",
              org_id: "33333333-3333-3333-3333-333333333333",
              status: "cancelled",
              queue_name: "default",
              retry_count: 0,
              callback_status: "pending",
              created_at: "2026-05-24T12:00:00Z",
              completed_at: "2026-05-24T12:01:00Z",
              poll_url: "https://example.test/v1/jobs/11111111-1111-1111-1111-111111111111",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              success: true,
              status_code: 200,
              message: "delivered",
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

      const submitted = await client.submitJob(
        {
          mode: "expert",
          runs: 100,
          simulation: {
            variables: [{ name: "outcome", distribution: "fixed", params: { value: 100 } }],
            objective_function: "outcome",
          },
        },
        "https://example.test/webhook",
      );
      const status = await client.getJob("11111111-1111-1111-1111-111111111111");
      const result = await client.getJobResult("11111111-1111-1111-1111-111111111111");
      const listed = await client.listJobs({ page: 2, limit: 10, status: "queued" });
      const cancelled = await client.cancelJob("11111111-1111-1111-1111-111111111111");
      const webhook = await client.testWebhookDelivery("https://example.test/webhook");

      expect(submitted.job_id).toBe("11111111-1111-1111-1111-111111111111");
      expect(submitted.status).toBe("queued");
      expect(status.status).toBe("queued");
      expect(result.result).toEqual({ score: 0.98 });
      expect(listed.total).toBe(1);
      expect(listed.page).toBe(2);
      expect(listed.jobs[0]?.queue_name).toBe("default");
      expect(cancelled.status).toBe("cancelled");
      expect(webhook.status_code).toBe(200);
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        "https://example.test/v1/jobs",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            request: {
              mode: "expert",
              runs: 100,
              simulation: {
                variables: [{ name: "outcome", distribution: "fixed", params: { value: 100 } }],
                objective_function: "outcome",
              },
            },
            callback_url: "https://example.test/webhook",
          }),
        }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        2,
        "https://example.test/v1/jobs/11111111-1111-1111-1111-111111111111",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        3,
        "https://example.test/v1/jobs/11111111-1111-1111-1111-111111111111/result",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenCalledWith(
        "https://example.test/v1/jobs/list?page=2&limit=10&status=queued",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        5,
        "https://example.test/v1/jobs/11111111-1111-1111-1111-111111111111/cancel",
        expect.objectContaining({ method: "POST" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        6,
        "https://example.test/v1/webhooks/test",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ callback_url: "https://example.test/webhook" }),
        }),
      );
    });

    it("supports the full trigger lifecycle surface", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              trigger_id: "trigger_123",
              org_id: "org_123",
              name: "Revenue alert",
              status: "active",
              condition: {
                source_id: "src_orders",
                metric_hint: "revenue",
                threshold: 200000,
                direction: "above",
                aggregation: "sum",
              },
              description: "Watch for monthly revenue spikes.",
              webhook_url: "https://example.test/hook",
              execution_webhook_url: "https://example.test/execute",
              auto_execute: true,
              created_at: "2026-05-24T12:00:00Z",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              triggers: [
                {
                  trigger_id: "trigger_123",
                  org_id: "org_123",
                  name: "Revenue alert",
                  status: "paused",
                  condition: {
                    source_id: "src_orders",
                    metric_hint: "revenue",
                    threshold: 200000,
                    direction: "above",
                    aggregation: "sum",
                  },
                  auto_execute: true,
                  created_at: "2026-05-24T12:00:00Z",
                },
              ],
              count: 1,
              total: 1,
              page: 2,
              limit: 10,
              pages: 1,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              trigger_id: "trigger_123",
              condition_met: true,
              fired: true,
              simulation_run_id: "run_123",
              recommended_action: "proceed",
              expected_value: 123000,
              confidence: 0.82,
              fired_at: "2026-05-24T12:05:00Z",
              execution_status: "queued",
              message: "Trigger fired.",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({ trigger_id: "trigger_123", status: "paused" }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(new Response(null, { status: 204 }));
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const created = await client.registerTrigger({
        name: "Revenue alert",
        condition: {
          source_id: "src_orders",
          metric_hint: "revenue",
          threshold: 200000,
          direction: "above",
          aggregation: "sum",
        },
        simulation_template: { mode: "auto" },
        webhook_url: "https://example.test/hook",
        execution_webhook_url: "https://example.test/execute",
        auto_execute: true,
        description: "Watch for monthly revenue spikes.",
      });
      const listed = await client.listTriggers({ status: "paused", page: 2, limit: 10 });
      const fired = await client.fireTrigger("trigger_123", { force: true });
      const paused = await client.pauseTrigger("trigger_123", { paused: true });
      const deleted = await client.deleteTrigger("trigger_123");

      expect(created.trigger_id).toBe("trigger_123");
      expect(listed.total).toBe(1);
      expect(listed.triggers[0]?.status).toBe("paused");
      expect(fired.simulation_run_id).toBe("run_123");
      expect(paused.status).toBe("paused");
      expect(deleted).toEqual({ trigger_id: "trigger_123", deleted: true });
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        "https://example.test/v1/triggers",
        expect.objectContaining({ method: "POST" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        2,
        "https://example.test/v1/triggers?status=paused&page=2&limit=10",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        3,
        "https://example.test/v1/triggers/trigger_123/fire",
        expect.objectContaining({ method: "POST" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        4,
        "https://example.test/v1/triggers/trigger_123/pause?paused=true",
        expect.objectContaining({ method: "PATCH" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        5,
        "https://example.test/v1/triggers/trigger_123",
        expect.objectContaining({ method: "DELETE" }),
      );
    });

    it("supports explicit zero device_limit on API key list and create responses", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify([
              {
                id: "key_1",
                label: "Mission Enterprise Key",
                key_prefix: "de_live_abcd",
                device_limit: 0,
                status: "active",
                created_at: "2026-05-19T00:00:00Z",
                expires_at: "2028-05-19T00:00:00Z",
              },
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              id: "key_2",
              label: "Mission Enterprise Key",
              key_prefix: "de_live_efgh",
              device_limit: 0,
              raw_key: "de_live_efgh_secret_value",
              created_at: "2026-05-19T00:00:00Z",
              expires_at: "2028-05-19T00:00:00Z",
            }),
            { status: 201, headers: { "Content-Type": "application/json" } },
          ),
        );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const listed = await client.listApiKeys();
      const created = await client.createApiKey({
        label: "Mission Enterprise Key",
        device_limit: 0,
      });

      expect(listed[0]?.device_limit).toBe(0);
      expect(created.device_limit).toBe(0);
      expect(fetchMock).toHaveBeenNthCalledWith(
        2,
        "https://example.test/v1/api-keys",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            label: "Mission Enterprise Key",
            device_limit: 0,
          }),
        }),
      );
    });

    it("supports typed deployment control-plane helpers", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              providers: [
                {
                  id: "algenta_shared",
                  name: "Algenta Managed",
                  description: "Multi-tenant shared pool.",
                  icon: "🌐",
                  regions: [{ id: "algenta-shared", label: "Algenta Shared", location: "Global" }],
                },
              ],
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              deployment_id: "dep_123",
              org_id: "org_123",
              provider: "algenta_shared",
              region: "algenta-shared",
              status: "requested",
              endpoint_url: "https://example.test/runtime",
              cost_usd_month: 12.5,
              billable_cost_usd_month: 15.0,
              billing_markup_pct: 20.0,
              created_at: "2026-05-24T12:00:00Z",
              provisioned_at: null,
              error_message: null,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              deployment_id: "dep_123",
              org_id: "org_123",
              provider: "algenta_shared",
              region: "algenta-shared",
              status: "requested",
              endpoint_url: "https://example.test/runtime",
              cost_usd_month: 12.5,
              billable_cost_usd_month: 15.0,
              billing_markup_pct: 20.0,
              created_at: "2026-05-24T12:00:00Z",
              provisioned_at: null,
              error_message: null,
            }),
            { status: 202, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              deployment_id: "dep_123",
              provider: "algenta_shared",
              region: "algenta-shared",
              year: 2026,
              month: 5,
              cost_usd_month: 12.5,
              billable_cost_usd_month: 15.0,
              billing_markup_pct: 20.0,
              last_updated: "2026-05-24T12:30:00Z",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({ status: "deprovisioning", deployment_id: "dep_123" }),
            { status: 202, headers: { "Content-Type": "application/json" } },
          ),
        );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const regions = await client.listDeploymentRegions();
      const deployment = await client.getDeployment();
      const created = await client.createDeployment();
      const cost = await client.getDeploymentCost("dep_123");
      const deleted = await client.deleteDeployment("dep_123");

      expect(regions.providers[0]?.regions[0]?.id).toBe("algenta-shared");
      expect(regions.providers[0]?.regions[0]?.name).toBe("Algenta Shared");
      expect(deployment?.deployment_id).toBe("dep_123");
      expect(created.status).toBe("requested");
      expect(cost.month).toBe(5);
      expect(deleted.status).toBe("deprovisioning");
      expect(fetchMock).toHaveBeenNthCalledWith(
        3,
        "https://example.test/v1/deployments",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            provider: "algenta_shared",
            region: "algenta-shared",
            config: null,
            billing_markup_pct: 20,
          }),
        }),
      );
    });
});
