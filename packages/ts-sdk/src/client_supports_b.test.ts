// Tests for DecisionEngineClient: supports_b.
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

describe("DecisionEngineClient — supports_b", () => {

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

    it("supports dataset connect and refresh endpoints through the public API", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              status: "ready",
              dataset_id: "ds_1",
              source_id: "ds_1",
              dataset_name: "warehouse_orders",
              connection_id: "conn_1",
              connection_type: "database",
              provider: "postgres",
              selection: { schema: "public", table: "orders" },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              datasets: [
                {
                  dataset_id: "ds_1",
                  dataset_name: "warehouse_orders",
                  connection_id: "conn_1",
                  provider: "postgres",
                },
              ],
              count: 1,
              total: 1,
              page: 1,
              limit: 25,
              pages: 1,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              dataset: {
                dataset_id: "ds_1",
                dataset_name: "warehouse_orders",
                connection_id: "conn_1",
              },
              schema: { fields: ["order_id", "revenue"] },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              status: "ready",
              dataset_id: "ds_1",
              source_id: "ds_1",
              dataset_name: "warehouse_orders",
              schema: { fields: ["order_id", "revenue"] },
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

      const connected = await client.connectData({
        dataset_name: "warehouse_orders",
        connection_id: "conn_1",
        selection: { schema: "public", table: "orders" },
      });
      const datasets = await client.listDatasets({ page: 1, limit: 25 });
      const dataset = await client.getDataset("ds_1");
      const refreshed = await client.refreshDataset("ds_1");

      expect(connected.dataset_id).toBe("ds_1");
      expect(datasets.datasets[0]?.dataset_id).toBe("ds_1");
      expect(dataset.schema.fields).toEqual(["order_id", "revenue"]);
      expect(refreshed.status).toBe("ready");
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        "https://example.test/v1/data/connect",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            dataset_name: "warehouse_orders",
            connection_id: "conn_1",
            selection: { schema: "public", table: "orders" },
          }),
        }),
      );
    });

    it("supports filtered dataset discovery and dataset summaries", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              datasets: [
                {
                  dataset_id: "ds_otp",
                  dataset_name: "OTP Monthly",
                  name: "OTP Monthly",
                  status: "ready",
                  source_names: ["ops_postgres"],
                  column_count: 12,
                  registered_at: "2026-05-20T10:00:00Z",
                },
              ],
              count: 1,
              total: 15,
              matched_total: 1,
              page: 2,
              limit: 50,
              pages: 1,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              dataset_id: "ds_otp",
              name: "OTP Monthly",
              status: "ready",
              source_names: ["ops_postgres"],
              row_count: 5000,
              column_count: 12,
              registered_at: "2026-05-20T10:00:00Z",
              query_hints: [{ hint: "otp_rate" }],
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

      const datasets = await client.listDatasets({
        page: 2,
        limit: 50,
        search: "otp",
        status: "ready",
        sourceName: "ops_postgres",
        compact: true,
      });
      const summary = await client.getDatasetSummary("ds_otp");

      expect(datasets.matched_total).toBe(1);
      expect(datasets.datasets[0]?.status).toBe("ready");
      expect(summary.query_hints).toEqual([{ hint: "otp_rate" }]);
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        "https://example.test/v1/data?page=2&limit=50&search=otp&status=ready&source_name=ops_postgres&compact=1",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        2,
        "https://example.test/v1/data/ds_otp/summary",
        expect.objectContaining({ method: "GET" }),
      );
    });

    it("supports governed batch query execution", async () => {
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            request_id: "req_batch",
            results: [
              {
                key: "overall_otp",
                data: makeQueryResponse({ request_id: "req_1" }),
                metadata: { request_id: "req_1", latency_ms: 12.5 },
              },
              {
                key: "avg_delay",
                error: {
                  code: "metric_not_found",
                  message: "Metric average_delay_minutes was not found.",
                },
              },
            ],
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

      const response = await client.queryBatch({
        defaults: {
          dataset_id: "otp_events",
          filter: {
            time_filter: "last_year",
            conditions: [{ dimension_hint: "status", op: "eq", value: "closed" }],
          },
          limit: 12,
          order: "desc",
        },
        queries: [
          { key: "overall_otp", request: { metric: { role: "derived_measure", hint: "otp_rate" } } },
          { key: "avg_delay", request: { metric: { role: "base_measure", hint: "average_delay_minutes" } } },
        ],
      });

      expect(response.request_id).toBe("req_batch");
      expect(response.results[0]?.key).toBe("overall_otp");
      expect(response.results[1]?.error?.code).toBe("metric_not_found");
      expect(fetchMock).toHaveBeenCalledWith(
        "https://example.test/v1/query/batch",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            defaults: {
              dataset_id: "otp_events",
              filter: {
                time_filter: "last_year",
                conditions: [{ dimension_hint: "status", op: "eq", value: "closed" }],
              },
              limit: 12,
              order: "desc",
            },
            queries: [
              { key: "overall_otp", request: { metric: { role: "derived_measure", hint: "otp_rate" } } },
              { key: "avg_delay", request: { metric: { role: "base_measure", hint: "average_delay_minutes" } } },
            ],
          }),
        }),
      );
    });

    it("supports read-only SQL reports", async () => {
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            columns: ["flight_month", "otp_rate_pct"],
            rows: [{ flight_month: "2026-04-01", otp_rate_pct: 92.4 }],
            row_count: 1,
            truncated: false,
            request_id: "req_sql",
            latency_ms: 24.1,
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

      const response = await client.querySqlReport({
        sources: [{ dataset_id: "ds_otp", alias: "otp" }],
        sql: "select flight_month, otp_rate_pct from otp",
        max_rows: 100,
      });

      expect(response.row_count).toBe(1);
      expect(response.columns).toEqual(["flight_month", "otp_rate_pct"]);
      expect(fetchMock).toHaveBeenCalledWith(
        "https://example.test/v1/query/sql-report",
        expect.objectContaining({ method: "POST" }),
      );
    });

    it("supports the plan-aligned llm utility routes", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeLLMModelsPayload()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              object: "artifact_bridge_resolution",
              backend: "huggingface_hub",
              artifact_backend: "safetensors",
              repo_id: "org/model",
              filename: "model.safetensors",
              revision: "main",
              local_files_only: true,
              status: "not_cached",
              cache_root: "/tmp/algenta-hf-cache",
              auth_env_vars: ["HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"],
              auth_configured: true,
              auth_env_var_used: "HF_TOKEN",
              resolved_path: null,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              object: "tokenization",
              model: "text.tokenizer",
              tokenizer_kind: "wordpiece",
              tokens: ["expand", "sales", "coverage"],
              token_count: 3,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              object: "token_count",
              model: "text.tokenizer",
              tokenizer_kind: "wordpiece",
              token_count: 3,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              id: "chatcmpl_123",
              object: "chat.completion",
              model: "text.tokenizer",
              provider_backend: null,
              provider_model_id: null,
              provider_attempts: [],
              choices: [
                {
                  index: 0,
                  finish_reason: "stop",
                  message: { role: "assistant", content: "Deterministic utility response." },
                },
              ],
              usage: { prompt_tokens: 4, completion_tokens: 3, total_tokens: 7 },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              id: "resp_123",
              object: "response",
              status: "completed",
              model: "provider.gpt-4o-mini",
              provider_backend: "openai_compatible",
              provider_model_id: "provider.gpt-4o-mini",
              provider_attempts: [
                {
                  provider_backend: "groq",
                  provider_model_id: "provider.fast",
                  outcome: "failed",
                  error_code: "provider_backend_error",
                },
                {
                  provider_backend: "openai_compatible",
                  provider_model_id: "provider.gpt-4o-mini",
                  outcome: "selected",
                  error_code: null,
                },
              ],
              output: [
                {
                  id: "out_1",
                  object: "response.output",
                  index: 0,
                  provider_backend: "openai_compatible",
                  provider_model_id: "provider.gpt-4o-mini",
                  provider_attempts: [
                    {
                      provider_backend: "groq",
                      provider_model_id: "provider.fast",
                      outcome: "failed",
                      error_code: "provider_backend_error",
                    },
                    {
                      provider_backend: "openai_compatible",
                      provider_model_id: "provider.gpt-4o-mini",
                      outcome: "selected",
                      error_code: null,
                    },
                  ],
                  content: [
                    {
                      type: "text",
                      text: "Provider response.",
                      token_count: 3,
                      embedding: null,
                    },
                  ],
                },
              ],
              usage: { prompt_tokens: 7, total_tokens: 7 },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              object: "list",
              model: "text.hash_embedding_v1",
              dimensions: 3,
              provider_backend: null,
              provider_model_id: null,
              provider_attempts: [],
              data: [
                {
                  object: "embedding",
                  index: 0,
                  embedding: [0.1, 0.2, 0.3],
                  token_count: 3,
                },
              ],
              usage: { prompt_tokens: 3, total_tokens: 3 },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              object: "embedding_similarity",
              model: "embeddings.cosine_similarity",
              similarity_metric: "cosine",
              score: 0.94,
              dimension: 3,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              object: "list",
              model: "embeddings.cosine_similarity",
              similarity_metric: "cosine",
              total_documents: 2,
              returned_documents: 1,
              data: [
                {
                  object: "rerank_result",
                  id: "doc-1",
                  index: 0,
                  rank: 1,
                  score: 0.94,
                  text: "Top document",
                  metadata: { source: "kb" },
                },
              ],
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeDecisionPlanPayload()), {
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

      const models = await client.listModels();
      const artifact = await client.resolveArtifactBridge({
        repo_id: "org/model",
        filename: "model.safetensors",
        revision: "main",
      });
      const tokenized = await client.tokenize({ input: "expand sales coverage" });
      const counted = await client.countTokens({ input: "expand sales coverage" });
      const chat = await client.chatCompletions({
        messages: [{ role: "user", content: "Summarize" }],
      });
      const response = await client.responses({
        model: "provider.gpt-4o-mini",
        input: ["expand sales coverage"],
        dimensions: 3,
      });
      const embeddings = await client.embeddings({
        input: "expand sales coverage",
        dimensions: 3,
      });
      const similarity = await client.embeddingSimilarity({
        left: [0.1, 0.2, 0.3],
        right: [0.1, 0.2, 0.3],
      });
      const reranked = await client.rerank({
        query_embedding: [0.1, 0.2, 0.3],
        documents: [{ id: "doc-1", embedding: [0.1, 0.2, 0.3], text: "Top document" }],
        top_n: 1,
      });
      const plan = await client.planDecision({
        mode: "auto",
        scenario: {
          variables: { revenue: { low: 1, high: 2 } },
          objective: "maximize_score",
        },
      });

      expect(models.data[0]?.id).toBe("text.tokenizer");
      expect(models.data[0]?.routing_targets).toEqual([]);
      expect(models.data[0]?.resolved_routing_targets).toEqual([]);
      expect(models.data[0]?.chat_routing_targets).toEqual([]);
      expect(models.data[0]?.resolved_chat_routing_targets).toEqual([]);
      expect(models.data[0]?.embedding_routing_targets).toEqual([]);
      expect(models.data[0]?.resolved_embedding_routing_targets).toEqual([]);
      expect(models.data[0]?.required_provider_headers).toEqual([]);
      expect(models.data[0]?.provider_auth_env_vars).toEqual([]);
      expect(models.data[0]?.provider_auth_configured).toBe(false);
      expect(models.data[0]?.routing_fallback_policy).toBeNull();
      expect(models.data[0]?.chat_routing_fallback_policy).toBeNull();
      expect(models.data[0]?.embedding_routing_fallback_policy).toBeNull();
      expect(models.data[0]?.routing_fallback_on).toEqual([]);
      expect(models.data[0]?.chat_routing_fallback_on).toEqual([]);
      expect(models.data[0]?.embedding_routing_fallback_on).toEqual([]);
      expect(models.data[0]?.routing_max_attempts).toBeNull();
      expect(models.data[0]?.chat_routing_max_attempts).toBeNull();
      expect(models.data[0]?.embedding_routing_max_attempts).toBeNull();
      expect(models.data[0]?.timeout_seconds).toBeNull();
      expect(models.data[0]?.chat_timeout_seconds).toBeNull();
      expect(models.data[0]?.embedding_timeout_seconds).toBeNull();
      expect(models.data[0]?.bridge_tokenizer_backends).toEqual(["tiktoken", "sentencepiece"]);
      expect(models.data[0]?.bridge_artifact_backends).toEqual([
        "safetensors",
        "huggingface_hub",
      ]);
      expect(models.data[0]?.bridge_cache_root).toBe("/tmp/algenta-hf-cache");
      expect(models.data[0]?.bridge_auth_env_vars).toEqual(["HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"]);
      expect(models.data[0]?.bridge_auth_configured).toBe(true);
      expect(artifact.status).toBe("not_cached");
      expect(artifact.auth_env_var_used).toBe("HF_TOKEN");
      expect(artifact.resolved_path).toBeNull();
      expect(tokenized.token_count).toBe(3);
      expect(counted.token_count).toBe(3);
      expect(chat.choices[0]?.message.content).toBe("Deterministic utility response.");
      expect(chat.provider_backend).toBeNull();
      expect(chat.provider_model_id).toBeNull();
      expect(chat.provider_attempts).toEqual([]);
      expect(response.provider_backend).toBe("openai_compatible");
      expect(response.provider_model_id).toBe("provider.gpt-4o-mini");
      expect(response.provider_attempts[0]?.provider_backend).toBe("groq");
      expect(response.provider_attempts[1]?.outcome).toBe("selected");
      expect(response.output[0]?.provider_backend).toBe("openai_compatible");
      expect(response.output[0]?.provider_model_id).toBe("provider.gpt-4o-mini");
      expect(response.output[0]?.provider_attempts).toHaveLength(2);
      expect(response.output[0]?.provider_attempts[1]?.provider_model_id).toBe("provider.gpt-4o-mini");
      expect(response.output[0]?.content[0]?.type).toBe("text");
      expect(response.output[0]?.content[0]?.embedding).toBeNull();
      expect(embeddings.dimensions).toBe(3);
      expect(embeddings.provider_backend).toBeNull();
      expect(embeddings.provider_model_id).toBeNull();
      expect(embeddings.provider_attempts).toEqual([]);
      expect(similarity.score).toBe(0.94);
      expect(reranked.data[0]?.rank).toBe(1);
      expect(plan.options[0]?.rank).toBe(1);
      expect(fetchMock.mock.calls[0]?.[0]).toBe("https://example.test/v1/models");
      expect(fetchMock.mock.calls[1]?.[0]).toBe("https://example.test/v1/artifacts/resolve");
      expect(fetchMock.mock.calls[9]?.[0]).toBe("https://example.test/v1/decisions/plan");
    });
});
