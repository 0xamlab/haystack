// SPDX-License-Identifier: Apache-2.0
// Tests for Runtime: renders.
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

describe("Runtime — renders", () => {
    it("renders a pure import preview from registration metadata", () => {
      const preview = renderSourceImportPreview(
        {
          name: "orders",
          status: "ready",
          row_count: 2,
          planner_schema_revision: "schema_revision_123456",
          latency_ms: 4.2,
          source_schema: { fields: ["product_line", "revenue", "region", "country"] },
        },
        { sourceRef: "orders.csv", mode: "local", color: false },
      );

      expect(preview).toContain("Algenta Source Import");
      expect(preview).toContain("Mode: local | Status: ready");
      expect(preview).toContain("Preview: product_line, revenue, region, +1 more");
      expect(preview).toContain("Schema: schema_revis | Latency: 4.200ms");
    });

    it("renders a pure bundle preview from registration and failure metadata", () => {
      const preview = renderSourceBundlePreview(
        [
          {
            source_id: "src_1",
            dataset_id: "src_1",
            name: "orders_detail",
            status: "ready",
            row_count: 6097,
            planner_schema_revision: "schema_orders_123456",
            latency_ms: 12.5,
            source_schema: { fields: ["Order ID", "Store Name", "Sales (incl. tax)"] },
          },
          {
            source_id: "src_2",
            dataset_id: "src_2",
            name: "orders_financial",
            status: "ready",
            row_count: 2026,
            planner_schema_revision: "schema_financial_123456",
            latency_ms: 8.3,
            source_schema: {
              fields: [
                "Order ID as per Uber Eats manager",
                "Store name as per Uber Eats manager",
              ],
            },
          },
        ],
        [
          {
            sourceRef: "store_pause.csv",
            code: "empty_source",
            message: "Connected source is empty and cannot be queried.",
            name: "store_pause",
          },
        ],
        { color: false },
      );

      expect(preview).toContain("Algenta Source Bundle");
      expect(preview).toContain("Imported: 2 | Failures: 1");
      expect(preview).toContain("orders_detail");
      expect(preview).toContain("orders_financial");
      expect(preview).toContain("store_pause: empty_source");
    });

    it("renders sqlite descriptor origins cleanly in import previews", async () => {
      if (!(await hasNodeSqlite())) {
        return;
      }
      const runtimeDir = runtimeTempDir();
      const dbPath = join(runtimeDir, "orders.db");
      await writeSqliteFixture(dbPath, [
        { product_line: "Electronics", revenue: 42_193_221, region: "US" },
        { product_line: "Apparel", revenue: 28_114_992, region: "US" },
      ]);

      const runtime = new Runtime();
      const imported = await runtime.importPreview({
        provider: "sqlite",
        path: dbPath,
        table: "orders",
      });

      expect(imported.registration.name).toBe("orders_orders");
      expect(imported.preview).toContain(`Origin: orders.db#orders`);
    });
});
