// Tests for Runtime: supports.
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

describe("Runtime — supports", () => {
    it("supports local resolve and query happy path", async () => {
      const runtime = new Runtime();
      await runtime.connect(
        [
          { product_line: "Electronics", revenue: 42_193_221 },
          { product_line: "Apparel", revenue: 28_114_992 },
        ],
        { name: "orders" },
      );

      const plan = await runtime.resolve({
        source_name: "orders",
        metric: "revenue",
        group_by: "product_line",
      });

      expect(plan.resolved_plan?.metric_column).toBe("revenue");
      expect(plan.resolved_plan?.group_column).toBe("product_line");

      const result = await runtime.query(plan);
      expect(result.result_type).toBe("table");
      expect(result.row_count).toBe(2);
      expect(result.plan_hash).toBeTruthy();
    });

    it("supports local file-backed CSV import preview and query for real corpus files", async () => {
      const runtime = new Runtime();
      const imported = await runtime.importPreview(REAL_MARCH_ORDERS, {
        name: "orders_detail",
        sourceRef: "orders_detail.csv",
        color: false,
      });

      const plan = await runtime.resolve({
        source_name: "orders_detail",
        metric: "Sales (incl. tax)",
        group_by: "Order Channel",
      });
      const result = await runtime.query(plan);

      expect(imported.registration.row_count).toBe(6097);
      expect(imported.preview).toContain("Origin: orders_detail.csv");
      expect(plan.resolved_plan?.metric_column).toBe("Sales (incl. tax)");
      expect(plan.resolved_plan?.group_column).toBe("Order Channel");
      expect(result.result_type).toBe("table");
      expect(result.row_count).toBeGreaterThan(0);
    });

    it("supports branded bundle previews across real csv and local sqlite sources", async () => {
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
      const bundle = await runtime.importBundlePreview(
        [
          REAL_MARCH_ORDERS,
          {
            provider: "sqlite",
            path: dbPath,
            table: "orders",
          },
          REAL_MARCH_EMPTY,
        ],
        {
          sourceRefs: ["orders_detail.csv", "orders.db#orders", REAL_MARCH_EMPTY.split(/[\\/]/).pop()],
          color: false,
        },
      );

      expect(bundle.registrations).toHaveLength(2);
      expect(bundle.failures).toHaveLength(1);
      expect(bundle.preview).toContain("Algenta Source Bundle");
      expect(bundle.preview).toContain("Imported: 2 | Failures: 1");
      expect(bundle.preview).toContain("orders_orders");
      expect(bundle.failures[0].code).toBe("empty_source");
    });

    it("supports api-mode bundle previews across mixed connector descriptors", async () => {
      const seen: Array<Record<string, unknown>> = [];
      const fakeClient = {
        registerSource: async (
          source: Record<string, unknown>,
          options: Record<string, unknown>,
        ) => {
          seen.push(source);
          const connection = source.connection;
          if (connection && typeof connection === "object" && (connection as Record<string, unknown>).type === "rest_api") {
            throw new RuntimeValidationError(
              "upstream_validation_failed",
              "REST source rejected by hosted connector validation.",
              { source: (connection as Record<string, unknown>).url },
            );
          }
          return {
            source_id: `src_${seen.length}`,
            dataset_id: `src_${seen.length}`,
            name: String(source.name ?? "source"),
            status: "ready",
            row_count: 120,
            planner_schema_revision: `schema_${seen.length}`,
            latency_ms: 3.4,
            source_schema: { fields: ["order_id", "revenue", "store_name"] },
          };
        },
      };

      const runtime = new Runtime({
        mode: "api",
        client: fakeClient as never,
      });

      const bundle = await runtime.importBundlePreview(
        [
          {
            type: "postgres",
            location: {
              host: "localhost",
              port: 5432,
              database: "orders",
              schema: "public",
              table: "orders",
            },
            auth: {
              credentials: {
                user: "analytics",
                password: "secret",
              },
            },
          },
          {
            type: "s3",
            bucket: "algenta-public",
            key: "orders/orders.csv",
            format: "csv",
          },
          {
            type: "rest",
            base_url: "https://example.com/api",
            path: "/orders",
            method: "GET",
          },
        ],
        {
          names: ["orders_pg", "orders_s3", "orders_rest"],
          sourceRefs: [
            "postgres://orders",
            "s3://algenta-public/orders/orders.csv",
            "https://example.com/api/orders",
          ],
          color: false,
        },
      );

      expect(bundle.registrations).toHaveLength(2);
      expect(bundle.failures).toHaveLength(1);
      expect(bundle.failures[0]?.code).toBe("upstream_validation_failed");
      expect(bundle.preview).toContain("Algenta Source Bundle");
      expect(bundle.preview).toContain("Imported: 2 | Failures: 1");
      expect(bundle.preview).toContain("orders_pg");
      expect(bundle.preview).toContain("orders_s3");
      expect(bundle.preview).toContain("orders_rest: upstream_validation_failed");
      expect(seen.map(source => String(source.name))).toEqual(["orders_pg", "orders_s3", "orders_rest"]);
      expect(
        seen.map(source => String((source.connection as Record<string, unknown>).type)),
      ).toEqual(["sql", "s3", "rest_api"]);
    });

    it("supports connectMany across related real csv sources with explicit names", async () => {
      const runtime = new Runtime();
      const registrations = await runtime.connectMany(
        [REAL_MARCH_ORDERS, REAL_MARCH_FINANCIAL],
        { names: ["orders_detail", "orders_financial"] },
      );

      expect(registrations).toHaveLength(2);
      expect(registrations[0]?.name).toBe("orders_detail");
      expect(registrations[0]?.row_count).toBe(6097);
      expect(registrations[1]?.name).toBe("orders_financial");
      expect(registrations[1]?.row_count).toBe(2026);
    });

    it("supports local sqlite descriptors when node:sqlite is available", async () => {
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
      const registration = await runtime.connect({
        provider: "sqlite",
        path: dbPath,
        table: "orders",
      });
      const plan = await runtime.resolve({
        source_name: registration.name,
        metric: "revenue",
        group_by: "product_line",
      });
      const result = await runtime.query(plan);

      expect(registration.name).toBe("orders_orders");
      expect(registration.row_count).toBe(2);
      expect(result.row_count).toBe(2);
    });
});
