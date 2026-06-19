// Tests for DecisionEngineClient: supports_d.
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

describe("DecisionEngineClient — supports_d", () => {

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

    it("supports typed account usage and limits helpers", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              org_id: "org_123",
              email: "owner@example.com",
              organization: "Algenta Labs",
              plan: "enterprise",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              org_id: "org_123",
              billing_period: "2026-05",
              simulations_run: 120,
              api_calls: 340,
              quota_limit: 1000,
              quota_used_pct: 12,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              plan: "enterprise",
              stripe_customer_id: "cus_123",
              subscription_status: "active",
              current_period_end: "2026-06-30T00:00:00Z",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              url: "https://billing.example/checkout/session_123",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              url: "https://billing.example/portal/session_123",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              plan: "enterprise",
              max_simulations_per_month: 100000,
              max_runs_per_simulation: 1000000,
              max_batch_items: 100,
              rate_limit_per_minute: 10000,
              async_jobs_enabled: true,
              webhooks_enabled: true,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify([
              {
                name: "normal",
                description: "Normal distribution.",
                required_params: ["mean", "std"],
                optional_params: [],
                example: { mean: 100, std: 12 },
              },
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify([
              {
                id: "product-launch",
                name: "Product Launch Decision",
                category: "business",
                description: "Compare launch scenarios.",
                example_request: { mode: "auto" },
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

      const me = await client.me();
      const usage = await client.usage();
      const billingInfo = await client.getBillingInfo();
      const checkout = await client.createBillingCheckout({ plan: "pro" });
      const portal = await client.createBillingPortal();
      const limits = await client.limits();
      const distributions = await client.distributions();
      const templates = await client.templates();

      expect(me.organization).toBe("Algenta Labs");
      expect(usage.billing_period).toBe("2026-05");
      expect(usage.simulations_run).toBe(120);
      expect(billingInfo.plan).toBe("enterprise");
      expect(billingInfo.stripe_customer_id).toBe("cus_123");
      expect(checkout.url).toContain("/checkout/");
      expect(portal.url).toContain("/portal/");
      expect(limits.plan).toBe("enterprise");
      expect(limits.simulations_per_month).toBe(100000);
      expect(limits.max_simulations_per_month).toBe(100000);
      expect(limits.max_runs_per_simulation).toBe(1000000);
      expect(limits.max_batch_items).toBe(100);
      expect(limits.jobs_enabled).toBe(true);
      expect(limits.async_jobs_enabled).toBe(true);
      expect(limits.webhooks_enabled).toBe(true);
      expect(distributions.distributions[0]?.name).toBe("normal");
      expect(templates.templates[0]?.id).toBe("product-launch");
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        "https://example.test/v1/me",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        2,
        "https://example.test/v1/usage",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        3,
        "https://example.test/v1/billing/info",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        4,
        "https://example.test/v1/billing/checkout",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ plan: "pro" }),
        }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        5,
        "https://example.test/v1/billing/portal",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({}),
        }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        6,
        "https://example.test/v1/limits",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        7,
        "https://example.test/v1/distributions",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        8,
        "https://example.test/v1/templates",
        expect.objectContaining({ method: "GET" }),
      );
    });

    it("supports typed team, audit log, and execution policy helpers", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify([
              {
                user_id: "user_123",
                name: "Owner",
                email: "owner@example.com",
                role: "owner",
                status: "active",
                last_active: "2026-05-24T12:00:00Z",
              },
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              message: "Invitation sent.",
              invite_id: "invite_123",
            }),
            { status: 201, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              message: "Role updated.",
              user_id: "user_123",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify({}), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              entries: [
                {
                  id: "audit_123",
                  timestamp: "2026-05-24T12:00:00Z",
                  actor_email: "owner@example.com",
                  action: "policy_update",
                  resource_type: "execution_policy",
                  resource_id: "org_123",
                  ip_address: "203.0.113.10",
                  result: "success",
                  metadata: {
                    policy_snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
                    schema_revision: "execution-policy-v1",
                  },
                },
              ],
              total: 1,
              page: 1,
              limit: 20,
              pages: 1,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              entries: [
                {
                  id: "audit_456",
                  timestamp: "2026-05-24T12:01:00Z",
                  actor_email: "owner@example.com",
                  action: "policy_update",
                  resource_type: "execution_policy",
                  resource_id: "org_123",
                  ip_address: "203.0.113.10",
                  result: "success",
                  metadata: {
                    policy_snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
                    schema_snapshot_id: "schema-v1",
                    manifest_version: "runtime-manifest-v1",
                    request_hash: "hash_123",
                  },
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
              entries: [
                {
                  id: "audit_artifact_1",
                  timestamp: "2026-05-24T12:02:00Z",
                  actor_email: "owner@example.com",
                  action: "policy_update",
                  resource_type: "execution_policy",
                  resource_id: "org_123",
                  ip_address: "203.0.113.10",
                  result: "success",
                  content_hash: "content_hash_1",
                  metadata: {
                    policy_snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
                    schema_snapshot_id: "schema-v1",
                    manifest_version: "runtime-manifest-v1",
                    request_hash: "hash_123",
                  },
                },
              ],
              total: 1,
              page: 1,
              limit: 5,
              pages: 1,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              org_id: "org_123",
              min_confidence: 0.7,
              risk_floor: 10000,
              require_calibration: true,
              allow_reexecution: false,
              snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
              content_hash: "abcd1234".repeat(8),
              schema_revision: "execution-policy-v1",
              revision: 2,
              previous_snapshot_id: "execution-policy-v1-r1:1111222233334444",
              created_at: "2026-05-24T12:00:00Z",
              updated_at: "2026-05-24T12:00:00Z",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              org_id: "org_123",
              data: [
                {
                  org_id: "org_123",
                  min_confidence: 0.7,
                  risk_floor: 10000,
                  require_calibration: true,
                  allow_reexecution: false,
                  snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
                  content_hash: "abcd1234".repeat(8),
                  schema_revision: "execution-policy-v1",
                  revision: 2,
                  previous_snapshot_id: "execution-policy-v1-r1:1111222233334444",
                  created_at: "2026-05-24T12:00:00Z",
                  updated_at: "2026-05-24T12:00:00Z",
                },
              ],
              total_snapshots: 1,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              org_id: "org_123",
              min_confidence: 0.85,
              risk_floor: 10000,
              require_calibration: true,
              allow_reexecution: true,
              snapshot_id: "execution-policy-v1-r3:fedcfedcfedcfedc",
              content_hash: "fedc".repeat(16),
              schema_revision: "execution-policy-v1",
              revision: 3,
              previous_snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
              created_at: "2026-05-24T12:05:00Z",
              updated_at: "2026-05-24T12:05:00Z",
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

      const team = await client.listTeamMembers({ page: 1, limit: 50 });
      const invited = await client.inviteTeamMember({ email: "new@example.com", role: "admin" });
      const roleUpdated = await client.updateTeamMemberRole("user_123", "viewer");
      const removed = await client.removeTeamMember("user_123");
      const logs = await client.getAuditLogs({ page: 1, limit: 20 });
      const filteredLogs = await client.getAuditLogs({
        page: 2,
        limit: 10,
        actor_email: "owner@example.com",
        action: "policy_update",
        resource_type: "execution_policy",
        result: "success",
        policy_snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
        schema_snapshot_id: "schema-v1",
        manifest_version: "runtime-manifest-v1",
        request_hash: "hash_123",
      });
      const artifacts = await client.getAuditLogArtifacts({
        page: 1,
        limit: 5,
        actor_email: "owner@example.com",
        action: "policy_update",
        resource_type: "execution_policy",
        result: "success",
        policy_snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
        schema_snapshot_id: "schema-v1",
        manifest_version: "runtime-manifest-v1",
        request_hash: "hash_123",
        content_hash: "content_hash_1",
      });
      const policy = await client.getExecutionPolicy();
      const snapshots = await client.listExecutionPolicySnapshots();
      const updated = await client.updateExecutionPolicy({
        min_confidence: 0.85,
        allow_reexecution: true,
      });

      expect(team.members[0]?.email).toBe("owner@example.com");
      expect(team.total).toBe(1);
      expect(invited.invite_id).toBe("invite_123");
      expect(roleUpdated.user_id).toBe("user_123");
      expect(removed).toEqual({ removed: true, user_id: "user_123" });
      expect(logs.entries[0]?.action).toBe("policy_update");
      expect(logs.entries[0]?.metadata?.["policy_snapshot_id"]).toBe(
        "execution-policy-v1-r2:abcd1234abcd1234",
      );
      expect(filteredLogs.entries[0]?.metadata?.["manifest_version"]).toBe("runtime-manifest-v1");
      expect(artifacts.entries[0]?.content_hash).toBe("content_hash_1");
      expect(policy.min_confidence).toBe(0.7);
      expect(policy.snapshot_id).toBe("execution-policy-v1-r2:abcd1234abcd1234");
      expect(snapshots.total_snapshots).toBe(1);
      expect(updated.allow_reexecution).toBe(true);
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        "https://example.test/v1/team?page=1&limit=50",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        2,
        "https://example.test/v1/team/invite",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ email: "new@example.com", role: "admin" }),
        }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        3,
        "https://example.test/v1/team/user_123/role",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ role: "viewer" }),
        }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        4,
        "https://example.test/v1/team/user_123",
        expect.objectContaining({ method: "DELETE" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        5,
        "https://example.test/v1/audit-logs?page=1&limit=20",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        6,
        "https://example.test/v1/audit-logs?page=2&limit=10&actor_email=owner%40example.com&action=policy_update&resource_type=execution_policy&result=success&policy_snapshot_id=execution-policy-v1-r2%3Aabcd1234abcd1234&schema_snapshot_id=schema-v1&manifest_version=runtime-manifest-v1&request_hash=hash_123",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        7,
        "https://example.test/v1/audit-logs/artifacts?page=1&limit=5&actor_email=owner%40example.com&action=policy_update&resource_type=execution_policy&result=success&policy_snapshot_id=execution-policy-v1-r2%3Aabcd1234abcd1234&schema_snapshot_id=schema-v1&manifest_version=runtime-manifest-v1&request_hash=hash_123&content_hash=content_hash_1",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        8,
        "https://example.test/v1/execution/policy",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        9,
        "https://example.test/v1/execution/policy/snapshots",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        10,
        "https://example.test/v1/execution/policy",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ min_confidence: 0.85, allow_reexecution: true }),
        }),
      );
    });

    it("supports typed account update helpers", async () => {
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            user: {
              id: "user_123",
              email: "owner@example.com",
              name: "Mission Ops",
              role: "owner",
              email_verified: true,
              created_at: "2026-05-24T12:00:00Z",
            },
            org: {
              id: "org_123",
              name: "Mission Control",
              slug: "mission-control",
              plan: "enterprise",
              status: "active",
              created_at: "2026-05-24T11:00:00Z",
            },
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

      const me = await client.updateMe({ name: " Mission Ops ", org_name: "Mission Control" });

      expect(me.user.name).toBe("Mission Ops");
      expect(me.org.slug).toBe("mission-control");
      expect(me.organization).toBe("Mission Control");
      expect(fetchMock).toHaveBeenCalledWith(
        "https://example.test/v1/me",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ name: "Mission Ops", org_name: "Mission Control" }),
        }),
      );
    });

    it("supports typed device list and revoke helpers", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              devices: [
              {
                id: "reg_123",
                device_id: "device_12...",
                platform: "macos",
                platform_version: "15.5",
                sdk_version: "1.0.0",
                status: "active",
                api_key_label: "Primary SDK Key",
                api_key_prefix: "de_live_",
                registered_at: "2026-05-24T11:00:00Z",
                last_heartbeat_at: "2026-05-24T12:00:00Z",
                heartbeat_count: 3,
              },
              ],
              device_count: 1,
              total: 1,
              page: 1,
              limit: 25,
              pages: 1,
              device_limit: 2,
              plan: "enterprise",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({ revoked: true, registration_id: "reg_123" }),
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

      const listed = await client.listDevices({ page: 1, limit: 25 });
      const revoked = await client.revokeDevice("reg_123");

      expect(listed.page).toBe(1);
      expect(listed.limit).toBe(25);
      expect(listed.device_limit).toBe(2);
      expect(listed.devices[0]?.device_id).toBe("device_12...");
      expect(listed.devices[0]?.api_key_label).toBe("Primary SDK Key");
      expect(revoked).toEqual({ revoked: true, registration_id: "reg_123" });
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        "https://example.test/v1/device/list?page=1&limit=25",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        2,
        "https://example.test/v1/device/reg_123",
        expect.objectContaining({ method: "DELETE" }),
      );
    });
});
