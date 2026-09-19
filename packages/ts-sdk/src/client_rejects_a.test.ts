// SPDX-License-Identifier: Apache-2.0
// Tests for DecisionEngineClient: rejects_a.
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

describe("DecisionEngineClient — rejects_a", () => {

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

    it("rejects Algenta-owned baseUrl in private profiles even when passed explicitly", () => {
      process.env.ALGENTA_DEPLOYMENT_MODE = "air_gapped";
      process.env.ALGENTA_DISABLE_CLOUD = "1";

      expect(
        () =>
          new DecisionEngineClient({
            apiKey: "de_test_123",
            baseUrl: DEFAULT_BASE_URL,
          }),
      ).toThrow("private profiles cannot target Algenta-owned cloud URLs");
    });

    it("rejects invalid env device ids before sending requests", async () => {
      process.env.ALGENTA_DEVICE_ID = "short";
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      expect(
        () =>
          new DecisionEngineClient({
            apiKey: "de_test_123",
            baseUrl: "https://example.test",
            maxRetries: 0,
            timeout: 1_000,
          }),
      ).toThrow("ALGENTA_DEVICE_ID");
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("rejects raw connector arrays beyond the first page", async () => {
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify([
            {
              id: "conn_1",
              name: "Warehouse Postgres",
              connector_type: "postgres",
              status: "live",
              visibility: "private",
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

      await expect(client.listConnectors({ page: 2, limit: 50 })).rejects.toThrow(
        "page=2",
      );
    });

    it("rejects raw dataset arrays beyond the first page", async () => {
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify([
            {
              dataset_id: "ds_1",
              dataset_name: "warehouse_orders",
              connection_id: "conn_1",
              provider: "postgres",
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

      await expect(client.listDatasets({ page: 2, limit: 50 })).rejects.toThrow(
        "page=2",
      );
    });

    it("rejects an invalid OpenAPI contract fallback payload", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({ error: { code: "not_found", message: "missing" } }),
            { status: 404, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ openapi: "3.1.0" }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test/self-host",
        maxRetries: 0,
        timeout: 1_000,
      });

      const contractPromise = client.getContract();

      await expect(contractPromise).rejects.toMatchObject({
        errorCode: "contract_extension_missing",
      });
      await expect(contractPromise).rejects.toThrow("x-primary-data-query-contract");
    });

    it("rejects an OpenAPI contract fallback payload with no api section", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({ error: { code: "not_found", message: "missing" } }),
            { status: 404, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              openapi: "3.1.0",
              "x-primary-data-query-contract": {
                mcp: { contract_tool: "get_contract" },
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test/self-host",
        maxRetries: 0,
        timeout: 1_000,
      });

      const contractPromise = client.getContract();

      await expect(contractPromise).rejects.toMatchObject({
        errorCode: "invalid_contract_payload",
      });
      await expect(contractPromise).rejects.toThrow("api contract section");
    });

    it("rejects an OpenAPI contract fallback payload with no api.contract_endpoint", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({ error: { code: "not_found", message: "missing" } }),
            { status: 404, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              openapi: "3.1.0",
              "x-primary-data-query-contract": {
                api: { query_batch_endpoint: "/v1/query/batch" },
                mcp: { contract_tool: "get_contract" },
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test/self-host",
        maxRetries: 0,
        timeout: 1_000,
      });

      const contractPromise = client.getContract();

      await expect(contractPromise).rejects.toMatchObject({
        errorCode: "invalid_contract_payload",
      });
      await expect(contractPromise).rejects.toThrow("api.contract_endpoint");
    });

    it("rejects an OpenAPI contract fallback payload with an invalid nested primary-data contract section", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({ error: { code: "not_found", message: "missing" } }),
            { status: 404, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              openapi: "3.1.0",
              "x-primary-data-query-contract": {
                api: { contract_endpoint: "/v1/meta/contract" },
                mcp: { contract_tool: "get_contract" },
                runtime_sdk: {
                  typescript: { runtime_class: null },
                },
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test/self-host",
        maxRetries: 0,
        timeout: 1_000,
      });

      const contractPromise = client.getContract();

      await expect(contractPromise).rejects.toMatchObject({
        errorCode: "invalid_contract_payload",
      });
      await expect(contractPromise).rejects.toThrow("runtime_sdk.typescript.runtime_class");
    });

    it("rejects an invalid contract payload", async () => {
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify(
            makeContractPayload({
              primary_data_query_contract: {
                api: { contract_endpoint: "/v1/meta/contract" },
              },
            }),
          ),
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

      const contractPromise = client.getContract();

      await expect(contractPromise).rejects.toMatchObject({
        errorCode: "invalid_contract_payload",
      });
      await expect(contractPromise).rejects.toThrow("invalid payload");
    });

    it("rejects a contract payload with an invalid nested primary-data contract section", async () => {
      const payload = makeContractPayload();
      (payload.primary_data_query_contract as Record<string, unknown>).runtime_sdk = {
        python: cloneJsonValue(PRIMARY_DATA_QUERY_CONTRACT.runtime_sdk.python),
        typescript: {
          ...cloneJsonValue(PRIMARY_DATA_QUERY_CONTRACT.runtime_sdk.typescript),
          runtime_class: null,
        },
      };
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const contractPromise = client.getContract();

      await expect(contractPromise).rejects.toMatchObject({
        errorCode: "invalid_contract_payload",
      });
      await expect(contractPromise).rejects.toThrow("runtime_sdk.typescript.runtime_class");

      await contractPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain(
          "primary_data_query_contract.runtime_sdk.typescript.runtime_class",
        );
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "primary_data_query_contract.runtime_sdk.typescript.runtime_class",
        });
        expect((error as DecisionEngineError).fieldErrors[0]).toMatchObject({
          path: "primary_data_query_contract.runtime_sdk.typescript.runtime_class",
        });
      });
    });

    it("rejects a runtime manifest payload with an invalid kernel promotion status", async () => {
      const payload = makeRuntimeManifestPayload();
      ((payload.modules as Array<Record<string, unknown>>)[0] as Record<string, unknown>).promotion_status =
        "graduated";
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const manifestPromise = client.getRuntimeManifest();

      await expect(manifestPromise).rejects.toMatchObject({
        errorCode: "invalid_runtime_contract_payload",
      });
      await expect(manifestPromise).rejects.toThrow("response.modules[0].promotion_status");
    });

    it("rejects a runtime manifest payload with a missing shipping replay proof ref", async () => {
      const payload = makeRuntimeManifestPayload();
      delete ((payload.modules as Array<Record<string, unknown>>)[0] as Record<string, unknown>)
        .replay_proof_ref;
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const manifestPromise = client.getRuntimeManifest();

      await expect(manifestPromise).rejects.toMatchObject({
        errorCode: "invalid_runtime_contract_payload",
      });
      await expect(manifestPromise).rejects.toThrow("response.modules[0].replay_proof_ref");
    });

    it("rejects invalid signed runtime manifest payloads", async () => {
      const manifest = makeRuntimeManifestPayload();
      (manifest.maturity as Record<string, unknown>).bpe_tokenizer = "legendary";

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(manifest), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const manifestPromise = client.getRuntimeManifest();

      await expect(manifestPromise).rejects.toThrow("invalid signed payload");
      await manifestPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("maturity.bpe_tokenizer");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "maturity.bpe_tokenizer",
        });
        expect((error as DecisionEngineError).fieldErrors[0]).toMatchObject({
          path: "maturity.bpe_tokenizer",
        });
      });
    });

    it("rejects runtime manifest artifact kind drift", async () => {
      const manifest = makeRuntimeManifestPayload();
      (manifest.compiled_artifacts as Array<Record<string, unknown>>)[0]!.kind =
        "ghost_bundle";

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(manifest), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const manifestPromise = client.getRuntimeManifest();

      await expect(manifestPromise).rejects.toThrow("invalid signed payload");
      await manifestPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("compiled_artifacts.0.kind");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "compiled_artifacts.0.kind",
        });
        expect((error as DecisionEngineError).fieldErrors[0]).toMatchObject({
          path: "compiled_artifacts.0.kind",
        });
      });
    });

    it("rejects duplicate runtime manifest release conditions", async () => {
      const manifest = makeRuntimeManifestPayload();
      (manifest.formal_release_theorem.required_conditions as Array<string>).push(
        "manifest-listed",
      );

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(manifest), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const manifestPromise = client.getRuntimeManifest();

      await expect(manifestPromise).rejects.toThrow("invalid signed payload");
      await manifestPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("formal_release_theorem.required_conditions");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "formal_release_theorem.required_conditions",
        });
      });
    });

    it("rejects duplicate runtime manifest module public channels", async () => {
      const manifest = makeRuntimeManifestPayload();
      (
        (manifest.modules as Array<Record<string, unknown>>)[0]!
          .public_supported_channels as Array<string>
      ).push("python_sdk");

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(manifest), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const manifestPromise = client.getRuntimeManifest();

      await expect(manifestPromise).rejects.toThrow("invalid signed payload");
      await manifestPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("modules.0.public_supported_channels");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "modules.0.public_supported_channels",
        });
      });
    });

    it("rejects duplicate runtime manifest module functions", async () => {
      const manifest = makeRuntimeManifestPayload();
      (
        (manifest.modules as Array<Record<string, unknown>>)[0]!.functions as Array<string>
      ).push(
        ((manifest.modules as Array<Record<string, unknown>>)[0]!.functions as Array<string>)[0]!,
      );

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(manifest), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const manifestPromise = client.getRuntimeManifest();

      await expect(manifestPromise).rejects.toThrow("invalid signed payload");
      await manifestPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("modules.0.functions");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "modules.0.functions",
        });
      });
    });

    it("rejects runtime manifest benchmark shipping function count drift", async () => {
      const manifest = makeRuntimeManifestPayload();
      (manifest.benchmark_discovery_lane as Record<string, unknown>).shipping_manifest_functions =
        999;

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(manifest), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const manifestPromise = client.getRuntimeManifest();

      await expect(manifestPromise).rejects.toThrow("invalid signed payload");
      await manifestPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("benchmark_discovery_lane.shipping_manifest_functions");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "benchmark_discovery_lane.shipping_manifest_functions",
        });
      });
    });

    it("rejects invalid runtime benchmark discovery rules in the manifest", async () => {
      const manifest = makeRuntimeManifestPayload();
      (manifest.shipping_contract as Record<string, unknown>).benchmark_discovery_rule =
        "shadow_runtime_contract";

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(manifest), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const manifestPromise = client.getRuntimeManifest();

      await expect(manifestPromise).rejects.toThrow("invalid signed payload");
      await manifestPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain("shipping_contract.benchmark_discovery_rule");
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: "shipping_contract.benchmark_discovery_rule",
        });
      });
    });
});
