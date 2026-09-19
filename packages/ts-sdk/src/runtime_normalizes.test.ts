// SPDX-License-Identifier: Apache-2.0
// Tests for Runtime: normalizes.
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

describe("Runtime — normalizes", () => {
    it("normalizes an upstream contract error from the api client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getContract: async () => {
            throw new DecisionEngineError(
              "OpenAPI contract fallback returned an invalid payload: primary_data_query_contract.runtime_sdk.typescript.runtime_class",
              0,
              "invalid_contract_payload",
              {
                error: {
                  code: "invalid_contract_payload",
                  details: {
                    cause:
                      "primary_data_query_contract.runtime_sdk.typescript.runtime_class",
                  },
                },
              },
            );
          },
        } as never,
      });

      const contractPromise = runtime.getContract();

      await expect(contractPromise).rejects.toMatchObject({
        code: "invalid_contract_payload",
        details: {
          source_error_code: "invalid_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: "primary_data_query_contract.runtime_sdk.typescript.runtime_class",
          },
        },
      });
      await expect(contractPromise).rejects.toThrow("getContract() returned an invalid payload.");
    });

    it.each([
      ["getRuntimeManifest", "getRuntimeManifest"],
      ["getRuntimeModules", "getRuntimeModules"],
      ["getRuntimeBenchmarks", "getRuntimeBenchmarks"],
      ["getRuntimeReleaseValidation", "getRuntimeReleaseValidation"],
    ] as const)(
      "normalizes an upstream invalid signed payload error from the api client for %s",
      async (methodName, clientMethodName) => {
        const runtime = new Runtime({
          mode: "self_hosted",
          apiKey: "de_test_123",
          baseUrl: "http://localhost:8000",
          client: {
            [clientMethodName]: async () => {
              throw new DecisionEngineError(
                `${methodName} upstream signed payload invalid`,
                0,
                "invalid_runtime_contract_payload",
                {
                  error: {
                    code: "invalid_runtime_contract_payload",
                    details: { cause: `${methodName}.proof_matrix[0].status` },
                  },
                },
              );
            },
          } as never,
        });

        const proofPromise = runtime[methodName]();

        await expect(proofPromise).rejects.toMatchObject({
          code: "invalid_runtime_contract_payload",
          details: {
            source_error_code: "invalid_runtime_contract_payload",
            source_status_code: 0,
            source_error_details: {
              cause: `${methodName}.proof_matrix[0].status`,
            },
          },
        });
        await expect(proofPromise).rejects.toThrow(
          `${methodName}() returned an invalid signed payload.`,
        );
      },
    );
});
