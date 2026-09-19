// SPDX-License-Identifier: Apache-2.0
// Tests for Runtime: exposes_b.
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

describe("Runtime — exposes_b", () => {
    it("exposes typed control-plane helpers through Runtime(mode='api')", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          listTeamMembers: async () => ({
            members: [
              {
                user_id: "user_123",
                name: "Owner",
                email: "owner@example.com",
                role: "owner",
                status: "active",
                last_active: "2026-05-24T12:00:00Z",
              },
            ],
            total: 1,
            page: 1,
            limit: 50,
            pages: 1,
          }),
          inviteTeamMember: async () => ({
            message: "Invitation sent.",
            invite_id: "invite_123",
          }),
          updateTeamMemberRole: async () => ({
            message: "Role updated.",
            user_id: "user_123",
          }),
          removeTeamMember: async () => ({
            removed: true,
            user_id: "user_123",
          }),
          listDevices: async () => ({
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
                heartbeat_count: 2,
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
          revokeDevice: async () => ({
            revoked: true,
            registration_id: "reg_123",
          }),
          getAuditLogs: async (options?: {
            actor_email?: string;
            action?: string;
            resource_type?: string;
            result?: string;
            policy_snapshot_id?: string;
            schema_snapshot_id?: string;
            manifest_version?: string;
            request_hash?: string;
          }) => ({
            entries: [
              {
                id: options?.manifest_version ? "audit_456" : "audit_123",
                timestamp: "2026-05-24T12:00:00Z",
                actor_email: "owner@example.com",
                action: "policy_update",
                resource_type: "execution_policy",
                resource_id: "org_123",
                ip_address: "203.0.113.10",
                result: "success",
                metadata: options?.manifest_version
                  ? {
                      policy_snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
                      schema_snapshot_id: "schema-v1",
                      manifest_version: options.manifest_version,
                      request_hash: options.request_hash,
                    }
                  : {
                      policy_snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
                      schema_revision: "execution-policy-v1",
                    },
              },
            ],
            total: 1,
            page: options?.manifest_version ? 2 : 1,
            limit: options?.manifest_version ? 10 : 25,
            pages: 1,
          }),
          getAuditLogArtifacts: async () => ({
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
          getExecutionPolicy: async () => ({
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
          listExecutionPolicySnapshots: async () => ({
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
          updateMe: async () => ({
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
          getBillingInfo: async () => ({
            plan: "enterprise",
            stripe_customer_id: "cus_123",
            subscription_status: "active",
            current_period_end: "2026-06-30T00:00:00Z",
          }),
          createBillingCheckout: async () => ({
            url: "https://billing.example/checkout/session_123",
          }),
          createBillingPortal: async () => ({
            url: "https://billing.example/portal/session_123",
          }),
          refreshCredits: async () => ({
            credits_granted: 10000,
            credits_issued_this_month: 25000,
            monthly_limit: 500000,
            monthly_remaining: 475000,
            billing_period: "2026-05",
            expires_at: 1716547200,
            refresh_after: 1716545040,
            server_time: 1716460800,
          }),
          ingestMeteringEvents: async () => ({
            accepted: 1,
            billing_period: "2026-05",
          }),
          updateExecutionPolicy: async () => ({
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
        } as never,
      });

      const team = await runtime.listTeamMembers({ page: 1, limit: 50 });
      const invited = await runtime.inviteTeamMember({ email: "new@example.com", role: "admin" });
      const roleUpdated = await runtime.updateTeamMemberRole("user_123", "viewer");
      const removed = await runtime.removeTeamMember("user_123");
      const devices = await runtime.listDevices({ page: 1, limit: 25 });
      const revoked = await runtime.revokeDevice("reg_123");
      const logs = await runtime.getAuditLogs();
      const filteredLogs = await runtime.getAuditLogs({
        actor_email: "owner@example.com",
        action: "policy_update",
        resource_type: "execution_policy",
        result: "success",
        policy_snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
        schema_snapshot_id: "schema-v1",
        manifest_version: "runtime-manifest-v1",
        request_hash: "hash_123",
      });
      const artifacts = await runtime.getAuditLogArtifacts({
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
      const policy = await runtime.getExecutionPolicy();
      const snapshots = await runtime.listExecutionPolicySnapshots();
      const me = await runtime.updateMe({ org_name: "Mission Control" });
      const billingInfo = await runtime.getBillingInfo();
      const checkout = await runtime.createBillingCheckout({ plan: "pro" });
      const portal = await runtime.createBillingPortal();
      const refreshed = await runtime.refreshCredits({
        device_id: "device_runtime_123",
        billing_period: "2026-05",
        credits_used: 17,
      });
      const metering = await runtime.ingestMeteringEvents({
        device_id: "device_runtime_123",
        events: [{ event_type: "query", latency_ms: 8.0, success: true }],
      });
      const updated = await runtime.updateExecutionPolicy({
        min_confidence: 0.85,
        allow_reexecution: true,
      });

      expect(team.members[0]?.email).toBe("owner@example.com");
      expect(team.total).toBe(1);
      expect(invited.invite_id).toBe("invite_123");
      expect(roleUpdated.user_id).toBe("user_123");
      expect(removed).toEqual({ removed: true, user_id: "user_123" });
      expect(devices.device_count).toBe(1);
      expect(devices.devices[0]?.device_id).toBe("device_12...");
      expect(devices.devices[0]?.api_key_prefix).toBe("de_live_");
      expect(revoked).toEqual({ revoked: true, registration_id: "reg_123" });
      expect(logs.entries[0]?.resource_type).toBe("execution_policy");
      expect(logs.entries[0]?.metadata?.["policy_snapshot_id"]).toBe(
        "execution-policy-v1-r2:abcd1234abcd1234",
      );
      expect(filteredLogs.entries[0]?.metadata?.["manifest_version"]).toBe("runtime-manifest-v1");
      expect(artifacts.entries[0]?.content_hash).toBe("content_hash_1");
      expect(policy.min_confidence).toBe(0.7);
      expect(snapshots.total_snapshots).toBe(1);
      expect(me.org.name).toBe("Mission Control");
      expect(billingInfo.plan).toBe("enterprise");
      expect(checkout.url).toContain("/checkout/");
      expect(portal.url).toContain("/portal/");
      expect(refreshed.credits_granted).toBe(10000);
      expect(metering.billing_period).toBe("2026-05");
      expect(updated.allow_reexecution).toBe(true);
    });

    it("exposes typed async job helpers through Runtime(mode='api')", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          submitJob: async () => ({
            job_id: "11111111-1111-1111-1111-111111111111",
            poll_url: "http://localhost:8000/v1/jobs/11111111-1111-1111-1111-111111111111",
            status: "queued",
          }),
          getJob: async () => ({
            job_id: "11111111-1111-1111-1111-111111111111",
            run_id: "22222222-2222-2222-2222-222222222222",
            org_id: "33333333-3333-3333-3333-333333333333",
            status: "queued",
            queue_name: "default",
            retry_count: 0,
            callback_status: "pending",
            created_at: "2026-05-24T12:00:00Z",
            poll_url: "http://localhost:8000/v1/jobs/11111111-1111-1111-1111-111111111111",
          }),
          getJobResult: async () => ({
            summary: "ok",
          }),
          listJobs: async () => ({
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
                poll_url: "http://localhost:8000/v1/jobs/11111111-1111-1111-1111-111111111111",
              },
            ],
            total: 1,
            page: 2,
            limit: 10,
            pages: 1,
          }),
          cancelJob: async () => ({
            job_id: "11111111-1111-1111-1111-111111111111",
            run_id: "22222222-2222-2222-2222-222222222222",
            org_id: "33333333-3333-3333-3333-333333333333",
            status: "cancelled",
            queue_name: "default",
            retry_count: 0,
            callback_status: "pending",
            created_at: "2026-05-24T12:00:00Z",
            completed_at: "2026-05-24T12:01:00Z",
            poll_url: "http://localhost:8000/v1/jobs/11111111-1111-1111-1111-111111111111",
          }),
          testWebhookDelivery: async () => ({
            success: true,
            status_code: 200,
            message: "delivered",
          }),
          pollJob: async () => ({
            summary: "ok",
          }),
        } as never,
      });

      const submitted = await runtime.submitJob({
        mode: "expert",
        runs: 100,
        simulation: {
          variables: [{ name: "outcome", distribution: "fixed", params: { value: 100 } }],
          objective_function: "outcome",
        },
      });
      const status = await runtime.getJob("11111111-1111-1111-1111-111111111111");
      const result = await runtime.getJobResult("11111111-1111-1111-1111-111111111111");
      const listed = await runtime.listJobs({ page: 2, limit: 10, status: "queued" });
      const cancelled = await runtime.cancelJob("11111111-1111-1111-1111-111111111111");
      const webhook = await runtime.testWebhookDelivery("https://example.test/webhook");
      const polled = await runtime.pollJob("11111111-1111-1111-1111-111111111111", {
        timeoutMs: 100,
        pollIntervalMs: 1,
      });

      expect(submitted.job_id).toBe("11111111-1111-1111-1111-111111111111");
      expect(status.status).toBe("queued");
      expect(result.summary).toBe("ok");
      expect(listed.total).toBe(1);
      expect(listed.page).toBe(2);
      expect(listed.jobs[0]?.status).toBe("queued");
      expect(cancelled.status).toBe("cancelled");
      expect(webhook.status_code).toBe(200);
      expect(polled.summary).toBe("ok");
    });

    it("exposes field-level validation aliases on direct runtime validation errors", () => {
      const error = new RuntimeValidationError(
        "invalid_runtime_contract_payload",
        "invalid signed payload",
        {
          cause: "proof_matrix.0.status",
          validation_errors: [
            {
              path: "proof_matrix.0.status",
              message: "Input should be a valid enum value",
              type: "enum",
            },
          ],
        },
      );

      expect(error.validationErrors).toEqual([
        {
          path: "proof_matrix.0.status",
          message: "Input should be a valid enum value",
          type: "enum",
        },
      ]);
      expect(error.fieldErrors).toEqual(error.validationErrors);
    });
});
