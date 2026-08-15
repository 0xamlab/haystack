// Tests for Runtime: accepts.
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

describe("Runtime — accepts", () => {
    it("accepts ALGENTA_API_URL for api mode in private profiles", async () => {
      process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
      process.env.ALGENTA_DISABLE_CLOUD = "1";
      delete process.env.ALGENTA_BASE_URL;
      delete process.env.DE_BASE_URL;
      process.env.ALGENTA_API_URL = "http://localhost:8000";

      const runtime = new Runtime({ mode: "api", apiKey: "de_test_123" });

      expect((runtime as unknown as { baseUrl?: string }).baseUrl).toBe("http://localhost:8000");
    });

    it("accepts canonical connector envelopes in api mode", async () => {
      const cases: Array<{
        source: Record<string, unknown>;
        expectedName: string;
        expectedConnection: Record<string, unknown>;
      }> = [
        {
          source: {
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
          expectedName: "orders_pg",
          expectedConnection: {
            type: "sql",
            provider: "postgres",
            connection_string: "postgresql://analytics:secret@localhost:5432/orders",
            schema: "public",
            table: "orders",
            query: "SELECT * FROM public.orders",
          },
        },
        {
          source: {
            type: "s3",
            location: { bucket: "algenta-public", key: "orders/orders.csv" },
            options: { format: "csv" },
          },
          expectedName: "orders_s3",
          expectedConnection: {
            type: "s3",
            bucket: "algenta-public",
            key: "orders/orders.csv",
            file_type: "csv",
          },
        },
        {
          source: {
            type: "rest",
            location: { base_url: "https://example.com/api", path: "/orders" },
            auth: { mode: "token", credentials: { token: "secret-token" } },
            options: { method: "GET" },
          },
          expectedName: "orders_rest",
          expectedConnection: {
            type: "rest_api",
            url: "https://example.com/api/orders",
            path: "/orders",
            method: "GET",
            headers: { Authorization: "Bearer secret-token" },
          },
        },
        {
          source: {
            type: "csv",
            location: { path: REAL_MARCH_ORDERS },
            options: { delimiter: "," },
          },
          expectedName: "orders_csv",
          expectedConnection: {
            type: "file",
            file_type: "csv",
            file_path: REAL_MARCH_ORDERS,
            delimiter: ",",
          },
        },
      ];
      const captured: Array<{ source: Record<string, unknown>; options: Record<string, unknown> }> = [];
      const fakeClient = {
        registerSource: async (
          source: Record<string, unknown>,
          options: Record<string, unknown>,
        ) => {
          captured.push({ source, options });
          return {
            status: "ready",
            source_id: "src_pg_1",
            dataset_id: "src_pg_1",
            name: String(source.name ?? "source"),
            source_schema: { fields: ["order_id", "revenue"] },
            planner_schema_revision: "schema_pg_1",
            latency_ms: 3.4,
            row_count: 120,
          };
        },
      };

      const runtime = new Runtime({
        mode: "api",
        client: fakeClient as never,
      });

      for (const { source, expectedName } of cases) {
        const registration = await runtime.connect(
          source,
          { name: expectedName, description: `Primary ${expectedName} source` },
        );

        expect(registration.name).toBe(expectedName);
      }

      expect(captured).toEqual(
        cases.map(({ expectedName, expectedConnection }) => ({
          source: {
            name: expectedName,
            connection: expectedConnection,
          },
          options: {
            description: `Primary ${expectedName} source`,
          },
        })),
      );
    });

    it("accepts canonical csv connectors in local mode", async () => {
      const runtimeDir = runtimeTempDir();
      try {
        const csvPath = join(runtimeDir, "orders.csv");
        writeFileSync(csvPath, "product_line,revenue\nElectronics,10\nApparel,20\n");

        const runtime = new Runtime();
        const registration = await runtime.connect(
          {
            type: "csv",
            location: { path: csvPath },
            options: { delimiter: "," },
          },
          { name: "orders" },
        );
        const plan = await runtime.resolve({
          source_name: "orders",
          metric: "revenue",
          aggregation: "count",
        });
        const result = await runtime.query(plan);

        expect(registration.row_count).toBe(2);
        expect(plan.resolved_plan?.source_name).toBe("orders");
        expect(result.result).toBe(2);
      } finally {
        rmSync(runtimeDir, { recursive: true, force: true });
      }
    });

    it("accepts an RS256 offline local license in air_gapped local mode", async () => {
      const runtimeDir = runtimeTempDir();
      process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
      process.env.ALGENTA_DEPLOYMENT_MODE = "air_gapped";
      const offlineLicense = issueOfflineLocalLicense(Math.floor(Date.now() / 1000) + 86_400);
      process.env.ALGENTA_LOCAL_LICENSE_PUBLIC_KEY = offlineLicense.publicKey;
      writeFileSync(join(runtimeDir, "license.jwt"), offlineLicense.token, { mode: 0o600 });
      const fetchSpy = vi.fn(async () => {
        throw new Error("hosted path should not run");
      });
      vi.stubGlobal("fetch", fetchSpy);

      const runtime = new Runtime();
      await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
      const plan = await runtime.resolve({
        source_name: "orders_detail",
        metric: "Sales (incl. tax)",
        group_by: "Order Channel",
      });
      const result = await runtime.query(plan);

      expect(result.row_count).toBeGreaterThan(0);
      expect(fetchSpy).not.toHaveBeenCalled();
    });
});
