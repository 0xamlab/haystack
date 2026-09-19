// Tests for Runtime: misc.
// Extracted from runtime.test.ts during modularization.
import { createHmac, createSign, generateKeyPairSync } from "node:crypto";
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
  parseStoredLicenseToken,
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

describe("Runtime — misc", () => {
    it("applies time and generic filter conditions in local exact execution", async () => {
      const runtime = new Runtime();
      const currentYear = new Date().getUTCFullYear();
      await runtime.connect(
        [
          {
            product_line: "Electronics",
            revenue: 10,
            status: "closed",
            booked_on: `${currentYear}-01-15`,
          },
          {
            product_line: "Electronics",
            revenue: 20,
            status: "open",
            booked_on: `${currentYear}-02-15`,
          },
          {
            product_line: "Apparel",
            revenue: 30,
            status: "closed",
            booked_on: `${currentYear - 1}-03-10`,
          },
        ],
        { name: "orders" },
      );

      const result = await runtime.query({
        source_name: "orders",
        metric_column: "revenue",
        aggregation: "sum",
        schema_revision: (await runtime.resolve({
          source_name: "orders",
          metric: "revenue",
        })).resolved_plan?.schema_revision ?? "missing",
        filter: {
          time_filter: "this_year",
          conditions: [{ dimension_hint: "status", op: "eq", value: "closed" }],
        },
      });

      expect(result.result).toBe(10);
      expect(result.plan.some(step => step.includes("Time filter 'this_year'"))).toBe(true);
      expect(result.plan.some(step => step.includes("Filter 'status eq"))).toBe(true);
    });

    it("verifies local plans", async () => {
      const runtime = new Runtime();
      await runtime.connect([{ product_line: "Electronics", revenue: 10 }], { name: "orders" });
      const plan = await runtime.resolve({
        source_name: "orders",
        metric: "revenue",
        group_by: "product_line",
      });

      const verified = await runtime.verify(plan);
      expect(verified.valid).toBe(true);
      expect(verified.verification_mode).toBe("local");
    });

    it("reports invalid generic filter conditions during local verify", async () => {
      const runtime = new Runtime();
      await runtime.connect([{ product_line: "Electronics", revenue: 10 }], { name: "orders" });
      const plan = await runtime.resolve({
        source_name: "orders",
        metric: "revenue",
      });

      const verified = await runtime.verify({
        ...(plan.resolved_plan ?? {}),
        filter: {
          conditions: [{ dimension_hint: "priority", op: "eq", value: "high" }],
        },
      });

      expect(verified.valid).toBe(false);
      expect(verified.errors).toEqual([
        "Filter dimension_hint 'priority' did not resolve on source 'orders'.",
      ]);
    });

    it("uses an exact api resolve for registered source fields when schema metadata is known", async () => {
      let resolveCalls = 0;
      const fakeClient = {
        registerSource: async () => ({
          status: "ready",
          source_id: "src_1",
          dataset_id: "src_1",
          name: "orders",
          source_schema: { fields: ["product_line", "revenue", "region"] },
          planner_schema_revision: "planner_schema_1",
        }),
        request: async () => ({
          entry: {
            source_schema_revision: "registry_schema_1",
          },
        }),
        resolve: async () => {
          resolveCalls += 1;
          throw new Error("exact api resolve should not call client.resolve");
        },
        verify: async () => ({
          valid: true,
          errors: [],
          suggestions: [],
          resolved: { source_name: "orders" },
          latency_ms: 1,
        }),
        query: async (request: Record<string, unknown>) => ({
          query_id: "query-1",
          result: 2,
          result_type: "scalar",
          confidence: 1,
          plan: ["Execute exact plan."],
          resolved_column: String(
            (request.resolved_plan as Record<string, unknown> | undefined)?.metric_column,
          ),
          resolved_role: "measure",
          resolved_source: String(
            (request.resolved_plan as Record<string, unknown> | undefined)?.source_name,
          ),
          row_count: 1,
          candidates: [],
          source_scores: { orders: 1 },
          ambiguous: false,
          exact_spec: true,
          explanation: ["Executed exactly."],
          latency_ms: 1,
          decision_path: "exact_spec",
          plan_hash: "plan-1",
          schema_revision: "registry_schema_1",
          validated: true,
          deterministic_scope: "api",
          confidence_source: "schema_truth",
          clarification_required: false,
          rejection_reason: null,
          request_id: "req_2",
          source_set: ["orders"],
          join_path: [],
          planner_mode: "exact_spec",
        }),
      };

      const runtime = new Runtime({
        mode: "api",
        client: fakeClient as never,
      });

      await runtime.connect({ records: [{ revenue: 42, product_line: "Electronics" }] }, { name: "orders" });
      const plan = await runtime.resolve({
        source_name: "orders",
        metric: "revenue",
        group_by: "product_line",
        aggregation: "count",
      });
      const verified = await runtime.verify(plan);
      const result = await runtime.query(plan);

      expect(resolveCalls).toBe(0);
      expect(plan.resolved_plan?.source_name).toBe("orders");
      expect(plan.resolved_plan?.metric_column).toBe("revenue");
      expect(plan.resolved_plan?.group_column).toBe("product_line");
      expect(plan.schema_revision).toBe("registry_schema_1");
      expect(verified.valid).toBe(true);
      expect(result.result).toBe(2);
    });

    it("lifts runtime dataset scope for exact api verify and query payloads", async () => {
      let capturedVerify: Record<string, unknown> | null = null;
      let capturedQuery: Record<string, unknown> | null = null;
      const fakeClient = {
        registerSource: async () => ({
          status: "ready",
          source_id: "src_alias_1",
          dataset_id: "src_alias_1",
          name: "orders_alias",
          source_schema: {
            source: "orders",
            fields: ["product_line", "revenue", "region"],
          },
          planner_schema_revision: "planner_schema_1",
        }),
        request: async () => ({
          entry: {
            source_schema_revision: "registry_schema_1",
          },
        }),
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
            result: 2,
            result_type: "scalar",
            confidence: 1,
            plan: ["Execute exact plan."],
            resolved_column: "revenue",
            resolved_role: "measure",
            resolved_source: "orders",
            row_count: 1,
            candidates: [],
            source_scores: { orders: 1 },
            ambiguous: false,
            exact_spec: true,
            explanation: ["Executed exactly."],
            latency_ms: 1,
            decision_path: "exact_spec",
            plan_hash: "plan-1",
            schema_revision: "registry_schema_1",
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

      await runtime.connect(
        { records: [{ revenue: 42, product_line: "Electronics" }] },
        { name: "orders_alias" },
      );
      const plan = await runtime.resolve({
        source_name: "orders_alias",
        metric: "revenue",
        group_by: "product_line",
        aggregation: "count",
      });
      await runtime.verify(plan);
      await runtime.query(plan);

      expect(plan.resolved_plan?.source_name).toBe("orders");
      expect(plan.resolved_plan?.constraints).toMatchObject({
        __runtime_dataset_id__: "src_alias_1",
      });
      expect(capturedVerify).toMatchObject({
        dataset_id: "src_alias_1",
        resolved_plan: {
          source_name: "orders",
          metric_column: "revenue",
          schema_revision: "registry_schema_1",
          constraints: {},
        },
      });
      expect(capturedQuery).toMatchObject({
        dataset_id: "src_alias_1",
        resolved_plan: {
          source_name: "orders",
          metric_column: "revenue",
          schema_revision: "registry_schema_1",
          constraints: {},
        },
      });
    });

    it("hydrates missing api registration row counts from dataset detail", async () => {
      const fakeClient = {
        registerSource: async () => ({
          status: "already_registered",
          source_id: "src_s3_1",
          dataset_id: "src_s3_1",
          name: "orders_s3",
          source_schema: { source: "orders", fields: ["product_line", "revenue"] },
          planner_schema_revision: "schema_s3_1",
        }),
        getDataset: async () => ({
          dataset: {
            dataset_id: "src_s3_1",
            name: "orders_s3",
            status: "ready",
            source_names: ["orders"],
            row_count: 29,
            column_count: 2,
          },
          schema: {
            source: "orders",
            fields: ["product_line", "revenue"],
          },
        }),
      };

      const runtime = new Runtime({
        mode: "api",
        client: fakeClient as never,
      });

      const registration = await runtime.connect(
        {
          type: "s3",
          bucket: "algenta-public",
          key: "orders/orders.csv",
          format: "csv",
        },
        { name: "orders_s3" },
      );

      expect(registration.status).toBe("already_registered");
      expect(registration.row_count).toBe(29);
      expect(registration.source_schema).toMatchObject({
        source: "orders",
        fields: ["product_line", "revenue"],
      });
    });

    it("returns a branded import preview for local sources", async () => {
      const runtime = new Runtime();
      const imported = await runtime.importPreview(
        [{ product_line: "Electronics", revenue: 42_193_221, region: "US" }],
        { name: "orders", sourceRef: "orders.csv", color: false },
      );

      expect(imported.registration.name).toBe("orders");
      expect(imported.registration.row_count).toBe(1);
      expect(imported.preview).toContain("Algenta Source Import");
      expect(imported.preview).toContain("Source: orders");
      expect(imported.preview).toContain("Origin: orders.csv");
      expect(imported.preview).toContain("Rows: 1 | Fields: 3");
    });

    it("skips alias header rows in real financial csv files", async () => {
      const runtime = new Runtime();
      const registration = await runtime.connect(REAL_MARCH_FINANCIAL, { name: "orders_financial" });

      expect(registration.row_count).toBe(2026);
    });

    it("allows unlimited repeated offline queries under a valid stored license (no local credit ledger)", async () => {
      // The local credit-ledger subsystem (writeCreditState/readCreditState/decrementCredit/
      // consumeLocalCredit) has been retired entirely: a client-side credit ledger could never be
      // the real entitlement source of truth (see ensureLocalExecutionEntitlement — the license
      // check itself is what remains). This is the regression test for its removal: repeated
      // queries under a validly-stored license never hit a quota_exhausted error, and no
      // credits.json ledger file is ever written.
      const runtimeDir = runtimeTempDir();
      process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
      seedStoredLicense(runtimeDir, "de_live_ts_runtime_key");
      vi.stubGlobal("fetch", vi.fn(async () => {
        throw new Error("offline");
      }));

      const runtime = new Runtime({ apiKey: "de_live_ts_runtime_key" });
      await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
      const plan = await runtime.resolve({
        source_name: "orders_detail",
        metric: "Sales (incl. tax)",
        group_by: "Order Channel",
      });

      const first = await runtime.query(plan);
      const second = await runtime.query(plan);
      const third = await runtime.query(plan);

      expect(first.row_count).toBeGreaterThan(0);
      expect(second.row_count).toBeGreaterThan(0);
      expect(third.row_count).toBeGreaterThan(0);
      expect(existsSync(join(runtimeDir, "credits.json"))).toBe(false);
    });

    it("allows key-bound offline execution under a valid stored license", async () => {
      const runtimeDir = runtimeTempDir();
      process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
      const now = Math.floor(Date.now() / 1000);
      seedStoredLicense(runtimeDir, "de_live_ts_runtime_key", now + 86_400);
      const fetchSpy = vi.fn(async () => {
        throw new Error("offline");
      });
      vi.stubGlobal("fetch", fetchSpy);

      const runtime = new Runtime({ apiKey: "de_live_ts_runtime_key" });
      await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
      const plan = await runtime.resolve({
        source_name: "orders_detail",
        metric: "Sales (incl. tax)",
        group_by: "Order Channel",
      });

      const first = await runtime.query(plan);
      const second = await runtime.query(plan);

      expect(first.row_count).toBeGreaterThan(0);
      expect(second.row_count).toBeGreaterThan(0);
      expect(existsSync(join(runtimeDir, "credits.json"))).toBe(false);
      expect(fetchSpy).not.toHaveBeenCalled();
    });

    it("blocks first-time offline hosted local execution without a stored license", async () => {
      const runtimeDir = runtimeTempDir();
      process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
      process.env.ALGENTA_JWT_SECRET = "ts-runtime-test-secret";
      vi.stubGlobal("fetch", vi.fn(async () => {
        throw new Error("offline");
      }));

      const runtime = new Runtime({ apiKey: "de_live_ts_runtime_key" });
      await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
      const plan = await runtime.resolve({
        source_name: "orders_detail",
        metric: "Sales (incl. tax)",
        group_by: "Order Channel",
      });

      await expect(runtime.query(plan)).rejects.toMatchObject({
        code: "license_required",
        message: expect.stringContaining("reachable control plane"),
      });
    });

    it("seeds a stored RS256 license from control-plane registration", async () => {
      const runtimeDir = runtimeTempDir();
      process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
      const serverTime = 2_200_000_000;
      const issued = issueControlPlaneLicense("de_live_ts_runtime_key", serverTime + 86_400);
      // The client-side check is optional UX preflight (the engine independently re-verifies
      // every entitlement claim); simulating that the deployment has the control plane's public
      // key configured is what lets parseStoredLicenseToken accept the RS256 response at all —
      // an unconfigured deployment would correctly treat this as an unverifiable/invalid license.
      process.env.ALGENTA_LOCAL_LICENSE_PUBLIC_KEY = issued.publicKey;
      const fetchSpy = vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/v1/device/register")) {
          return new Response(
            JSON.stringify({
              license_token: issued.token,
              server_time: serverTime,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(JSON.stringify({}), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      });
      vi.stubGlobal("fetch", fetchSpy);

      const runtime = new Runtime({ apiKey: "de_live_ts_runtime_key" });
      await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
      const plan = await runtime.resolve({
        source_name: "orders_detail",
        metric: "Sales (incl. tax)",
        group_by: "Order Channel",
      });
      const result = await runtime.query(plan);

      expect(result.row_count).toBeGreaterThan(0);
      expect(existsSync(join(runtimeDir, "license.jwt"))).toBe(true);
      expect(existsSync(join(runtimeDir, "credits.json"))).toBe(false);
      expect(JSON.parse(readFileSync(join(runtimeDir, "trusted_time.json"), "utf8"))).toMatchObject({
        trusted_epoch: serverTime,
        source: "control-plane-register",
      });
      expect(fetchSpy).toHaveBeenCalled();
    });

    it("records sanitized control-plane egress when hosted local registration succeeds", async () => {
      const runtimeDir = runtimeTempDir();
      process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
      process.env.ALGENTA_ALLOW_OUTBOUND_NETWORK = "0";
      process.env.ALGENTA_CONTROL_PLANE_URL = "https://control.customer.internal";
      process.env.ALGENTA_EGRESS_ALLOWLIST = "control.customer.internal";
      const serverTime = 2_200_000_000;
      const issued = issueControlPlaneLicense("de_live_ts_runtime_key", serverTime + 86_400);
      process.env.ALGENTA_LOCAL_LICENSE_PUBLIC_KEY = issued.publicKey;
      const fetchSpy = vi.fn(async () =>
        new Response(
          JSON.stringify({
            license_token: issued.token,
            server_time: serverTime,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
      vi.stubGlobal("fetch", fetchSpy);

      const runtime = new Runtime({ apiKey: "de_live_ts_runtime_key" });
      await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
      const plan = await runtime.resolve({
        source_name: "orders_detail",
        metric: "Sales (incl. tax)",
        group_by: "Order Channel",
      });
      await runtime.query(plan);

      const [event] = readLedgerEvents(runtimeDir);
      expect(event.action).toBe("privacy_egress");
      expect(event.status).toBe("allow");
      expect(event.target).toBe("internal-host");
      expect(event.success).toBe(true);
      expect(event.error).toBeNull();
      expect(event.details).toMatchObject({
        surface: "device_register",
        egress_class: "operator_service",
        decision: "allow",
        reason: "destination_allowlisted",
        deployment_mode: "saas",
        service_name: "runtime",
        destination_host_redacted: "internal-host",
      });
      expect(fetchSpy).toHaveBeenCalledTimes(1);
    });

    it("advances the trusted offline clock with monotonic time when the wall clock stalls", async () => {
      const runtimeDir = runtimeTempDir();
      process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
      const issuedAt = 1_950_000_000;
      const expiresAt = issuedAt + 1;
      seedStoredLicense(runtimeDir, "de_live_ts_runtime_key", expiresAt);
      seedTrustedTime(runtimeDir, issuedAt);
      vi.spyOn(Date, "now").mockReturnValue(issuedAt * 1000);
      let monotonicMillis = 0;
      vi.spyOn(performance, "now").mockImplementation(() => monotonicMillis);
      vi.stubGlobal("fetch", vi.fn(async () => {
        throw new Error("offline");
      }));

      const runtime = new Runtime({ apiKey: "de_live_ts_runtime_key" });
      await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
      const plan = await runtime.resolve({
        source_name: "orders_detail",
        metric: "Sales (incl. tax)",
        group_by: "Order Channel",
      });

      monotonicMillis = 0;
      const first = await runtime.query(plan);
      expect(first.row_count).toBeGreaterThan(0);

      monotonicMillis = (14 * 86_400 + 5) * 1000;
      await expect(runtime.query(plan)).rejects.toMatchObject({
        code: "license_required",
        message: expect.stringContaining("renew"),
      });
    });

    it("hard-rejects a token signed with the retired symmetric license scheme (regression)", () => {
      // Uses the precomputed shared secret of the retired symmetric license scheme as a fixed
      // test vector (the derivation itself lives in the private engine repo and is
      // intentionally not reproduced here). Proves the token is rejected outright even with
      // the historically correct secret: alg !== "RS256" is now an unconditional hard reject
      // in parseStoredLicenseToken, never a fallback-eligible condition gated on
      // requireLocalLicense() or any other deployment profile.
      const retiredSecret =
        "57b5c258396eca54eb9c4518b90b7be25b69c909abfae42f12352cc355490963";
      const header = base64UrlJson({ alg: "HS256", typ: "JWT" });
      const payload = base64UrlJson({
        api_key_prefix: "de_live_ts_r",
        device_id: "ts-device-1",
        plan: "enterprise",
        device_limit: 0,
        permitted_modules: ["*"],
        issued_at: Math.floor(Date.now() / 1000),
        expires_at: 0,
        key_expires_at: 0,
        grace_days: 14,
        iss: "algenta-control-plane",
        sub: "device-license",
      });
      const signature = createHmac("sha256", retiredSecret).update(`${header}.${payload}`).digest("base64url");
      const forgedToken = `${header}.${payload}.${signature}`;

      expect(parseStoredLicenseToken(forgedToken, "de_live_ts_runtime_key")).toBeNull();
    });

    it("denies local execution entitlement to a hand-forged HS256 license (malicious/modified-SDK simulation)", async () => {
      // Simulates a hostile actor (or a maliciously modified SDK fork) that hand-forges a
      // self-signed "enterprise" license under the retired symmetric scheme and plants it
      // straight on the on-disk license path a real SDK reads from -- bypassing
      // exchangeApiKeyForLicense (the network/control-plane path) entirely, exactly as a
      // hostile fork calling internals directly could. The forged secret below is a stand-in:
      // any historical real value lives only in the private engine repo, and the scheme is
      // rejected on alg alone, so every value exercises the same rejection path.
      const runtimeDir = runtimeTempDir();
      process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
      const forgedSecret = "synthetic-forged-secret-not-a-real-credential";
      const header = base64UrlJson({ alg: "HS256", typ: "JWT" });
      const payload = base64UrlJson({
        api_key_prefix: "forged",
        device_id: "attacker-device",
        plan: "enterprise",
        device_limit: 0,
        permitted_modules: ["*"],
        issued_at: Math.floor(Date.now() / 1000),
        expires_at: 0,
        key_expires_at: 0,
        grace_days: 14,
        iss: "forged-synthetic-issuer",
        sub: "device-license",
      });
      const signature = createHmac("sha256", forgedSecret).update(`${header}.${payload}`).digest("base64url");
      const forgedToken = `${header}.${payload}.${signature}`;

      // Direct proof: the internal parser alone never accepts it, regardless of any surrounding flow.
      expect(parseStoredLicenseToken(forgedToken, "de_live_ts_runtime_key")).toBeNull();

      // End-to-end proof: even planted directly on disk (bypassing the network entirely), a real
      // Runtime never treats this as a valid license -- it falls through exactly like "no usable
      // license on disk" and correctly refuses local execution rather than granting entitlement.
      writeFileSync(join(runtimeDir, "license.jwt"), forgedToken, { mode: 0o600 });
      vi.stubGlobal("fetch", vi.fn(async () => {
        throw new Error("offline");
      }));

      const runtime = new Runtime({ apiKey: "de_live_ts_runtime_key" });
      await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
      const plan = await runtime.resolve({
        source_name: "orders_detail",
        metric: "Sales (incl. tax)",
        group_by: "Order Channel",
      });

      await expect(runtime.query(plan)).rejects.toMatchObject({ code: "license_required" });
    });
});
