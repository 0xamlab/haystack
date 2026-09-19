// SPDX-License-Identifier: Apache-2.0
// Tests for Runtime: delegates_a.
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

describe("Runtime — delegates_a", () => {
    it("delegates resolve, verify, query, and connect to the injected api client", async () => {
      let capturedResolve: Record<string, unknown> | null = null;
      let capturedVerify: Record<string, unknown> | null = null;
      let capturedQuery: Record<string, unknown> | null = null;
      const fakeClient = {
        registerSource: async () => ({ status: "ready", source_id: "src_1" }),
        resolve: async (request: Record<string, unknown>) => {
          capturedResolve = request;
          return {
          resolved_plan: {
            source_name: "orders",
            metric_column: "revenue",
            aggregation: "sum",
            schema_revision: "schema-1",
          },
          confidence: 1,
          plan: ["Use orders"],
          explanation: ["Resolved exactly"],
          resolved_column: "revenue",
          resolved_role: "measure",
          resolved_source: "orders",
          candidates: [],
          source_scores: { orders: 1 },
          latency_ms: 1,
          decision_path: "exact_spec",
          plan_hash: "plan-1",
          schema_revision: "schema-1",
          validated: true,
          deterministic_scope: "api",
          confidence_source: "schema_truth",
          clarification_required: false,
          rejection_reason: null,
          request_id: "req_1",
          intent_signature: "intent-1",
          source_set: ["orders"],
          join_path: [],
          planner_mode: "exact_spec",
        };
        },
        verify: async (request: Record<string, unknown>) => {
          capturedVerify = request;
          return {
          valid: true,
          errors: [],
          suggestions: [],
          resolved: { source_name: "orders" },
          latency_ms: 1,
        };
        },
        query: async (request: Record<string, unknown>) => {
          capturedQuery = request;
          return {
          query_id: "query-1",
          result: 42,
          result_type: "scalar",
          confidence: 1,
          plan: ["Use orders"],
          resolved_column: "revenue",
          resolved_role: "measure",
          resolved_source: "orders",
          row_count: 1,
          candidates: [],
          source_scores: { orders: 1 },
          ambiguous: false,
          exact_spec: true,
          explanation: ["Executed exactly"],
          latency_ms: 1,
          decision_path: "exact_spec",
          plan_hash: "plan-1",
          schema_revision: "schema-1",
          validated: true,
          deterministic_scope: "api",
          confidence_source: "schema_truth",
          clarification_required: false,
          rejection_reason: null,
          request_id: "req_2",
          source_set: ["orders"],
          join_path: [],
          planner_mode: "exact_spec",
        };
        },
      };

      const runtime = new Runtime({
        mode: "api",
        client: fakeClient as never,
      });

      const registered = await runtime.connect({ records: [{ revenue: 42, product_line: "Electronics" }] });
      const plan = await runtime.resolve({ source_name: "orders", metric: "revenue" });
      const verified = await runtime.verify(plan);
      const result = await runtime.query(plan);

      expect(registered.source_id).toBe("src_1");
      expect(plan.resolved_plan?.metric_column).toBe("revenue");
      expect(verified.valid).toBe(true);
      expect(result.result).toBe(42);
      expect(capturedResolve).toEqual({
        preferred_source: "orders",
        allow_org_scope: true,
        metric: {
          role: "metric",
          hint: "revenue",
        },
      });
      expect(capturedVerify).toMatchObject({
        resolved_plan: {
          source_name: "orders",
          metric_column: "revenue",
          schema_revision: "schema-1",
        },
      });
      expect(capturedQuery).toMatchObject({
        resolved_plan: {
          source_name: "orders",
          metric_column: "revenue",
          schema_revision: "schema-1",
        },
      });
    });
});
