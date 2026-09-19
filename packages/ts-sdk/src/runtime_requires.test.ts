// SPDX-License-Identifier: Apache-2.0
// Tests for Runtime: requires.
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

describe("Runtime — requires", () => {
    it("requires API configuration when api mode has no key or client", async () => {
      const runtime = new Runtime({ mode: "api" });
      await expect(runtime.resolve({ source_name: "orders", metric: "revenue" })).rejects.toMatchObject({
        code: "api_key_required",
      });
      await expect(runtime.resolve({ source_name: "orders", metric: "revenue" })).rejects.toThrow(
        "ALGENTA_API_KEY / DE_API_KEY",
      );
    });

    it("requires an explicit baseUrl for self_hosted mode", () => {
      expect(() => new Runtime({ mode: "self_hosted", apiKey: "de_test_123" })).toThrow(
        RuntimeConfigurationError,
      );
    });

    it("requires persist when connecting from an inline connector preview", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          connectData: async () => {
            throw new Error("should not be called");
          },
        } as never,
      });

      await expect(
        runtime.connect(null, {
          name: "preview_orders",
          connector: { type: "redis", url: "redis://localhost:6379" },
        }),
      ).rejects.toMatchObject({
        code: "connector_persistence_required",
      });
    });

    it("requires a local signed license in air_gapped local mode", async () => {
      const runtimeDir = runtimeTempDir();
      process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
      process.env.ALGENTA_DEPLOYMENT_MODE = "air_gapped";
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

      await expect(runtime.query(plan)).rejects.toMatchObject({
        code: "license_required",
        message: expect.stringContaining("local signed license"),
      });
      expect(fetchSpy).not.toHaveBeenCalled();
    });
});
