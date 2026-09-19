// SPDX-License-Identifier: Apache-2.0
// Tests for DecisionEngineClient: misc.
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

describe("DecisionEngineClient — misc", () => {

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

    it("sends deterministic query requests with auth headers", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(makeQueryResponse()), {
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

      const request = {
        source_name: "orders",
        metric_column: "revenue",
        aggregation: "sum",
      };

      const result = await client.query(request);

      expect(result.plan_hash).toBe("plan-1");
      expect(fetchMock).toHaveBeenCalledTimes(1);
      expect(fetchMock).toHaveBeenCalledWith(
        "https://example.test/v1/query",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify(request),
          headers: expect.objectContaining({
            Authorization: "Bearer de_test_123",
            "Content-Type": "application/json",
          }),
        }),
      );
    });

    it("emits hosted device headers when ALGENTA_DEVICE_ID is set", async () => {
      process.env.ALGENTA_DEVICE_ID = "ts-device-00000001";
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(makeQueryResponse()), {
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

      await client.query({
        source_name: "orders",
        metric_column: "revenue",
        aggregation: "sum",
      });

      expect(fetchMock).toHaveBeenCalledWith(
        "https://example.test/v1/query",
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: "Bearer de_test_123",
            "X-Algenta-Device-Id": "ts-device-00000001",
            [HOSTNAME_HASH_HEADER]: expect.any(String),
            "X-Algenta-SDK-Version": "algenta-ts/1.0.4",
          }),
        }),
      );
    });

    it("lets explicit defaultHeaders override the auto device id", async () => {
      process.env.ALGENTA_DEVICE_ID = "ts-device-00000001";
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(makeQueryResponse()), {
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
        defaultHeaders: {
          "X-Algenta-Device-Id": "ts-device-explicit-0001",
        },
      });

      await client.query({
        source_name: "orders",
        metric_column: "revenue",
        aggregation: "sum",
      });

      expect(fetchMock).toHaveBeenCalledWith(
        "https://example.test/v1/query",
        expect.objectContaining({
          headers: expect.objectContaining({
            "X-Algenta-Device-Id": "ts-device-explicit-0001",
            [HOSTNAME_HASH_HEADER]: expect.any(String),
          }),
        }),
      );
    });

    it("derives explain output from query responses when source graph metadata is absent", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify(
              makeQueryResponse({
                exact_spec: false,
                decision_path: "planner_hint",
                resolved_source: "orders ⋈ stores",
                source_scores: { orders: 0.92, stores: 0.88 },
              }),
            ),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            },
          ),
        );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const response = await client.explain({
        metric_column: "revenue",
        aggregation: "sum",
      });

      expect(response.source_set).toEqual(["orders", "stores"]);
      expect(response.join_path).toEqual([
        { left_source: "orders", right_source: "stores" },
      ]);
      expect(response.planner_mode).toBe("planner_hint");
    });

    it("applies the safe default join-path budget and preserves explicit opt-in", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(makeQueryResponse()), {
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

      await client.query({
        source_name: "S0",
        metric_column: "value",
        group_column: "region",
        join_path: {
          base_source: "S0",
          group_source: "S1",
          edges: [{ left_source: "S0", right_source: "S1", left_key: "id", right_key: "id" }],
        },
      });

      expect(fetchMock).toHaveBeenLastCalledWith(
        "https://example.test/v1/query",
        expect.objectContaining({
          body: JSON.stringify({
            source_name: "S0",
            metric_column: "value",
            group_column: "region",
            join_path: {
              base_source: "S0",
              group_source: "S1",
              edges: [{ left_source: "S0", right_source: "S1", left_key: "id", right_key: "id" }],
              max_hops: 4,
            },
          }),
        }),
      );

      await client.query({
        source_name: "S0",
        metric_column: "value",
        group_column: "region",
        join_path: {
          base_source: "S0",
          group_source: "S6",
          max_hops: 6,
          edges: Array.from({ length: 6 }, (_unused, index) => ({
            left_source: `S${index}`,
            right_source: `S${index + 1}`,
            left_key: `k${index}`,
            right_key: `k${index}`,
          })),
        },
      });

      expect(fetchMock).toHaveBeenLastCalledWith(
        "https://example.test/v1/query",
        expect.objectContaining({
          body: JSON.stringify({
            source_name: "S0",
            metric_column: "value",
            group_column: "region",
            join_path: {
              base_source: "S0",
              group_source: "S6",
              max_hops: 6,
              edges: Array.from({ length: 6 }, (_unused, index) => ({
                left_source: `S${index}`,
                right_source: `S${index + 1}`,
                left_key: `k${index}`,
                right_key: `k${index}`,
              })),
            },
          }),
        }),
      );
    });

    it("returns query metadata without changing query()", async () => {
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(makeQueryResponse({ request_id: "req_123", latency_ms: 18.5 })), {
          status: 200,
          headers: {
            "Content-Type": "application/json",
            "X-Input-Tokens": "120",
            "X-Output-Tokens": "45",
            "X-Cost-Usd": "0.0025",
            "X-Cache-Hit": "true",
          },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const response = await client.queryWithMetadata({
        source_name: "orders",
        metric_column: "revenue",
        aggregation: "sum",
      });

      expect(response.data.plan_hash).toBe("plan-1");
      expect(response.metadata).toEqual({
        request_id: "req_123",
        latency_ms: 18.5,
        tokens_in: 120,
        tokens_out: 45,
        cost_usd: 0.0025,
        cache_hit: true,
      });
      expect(response.headers?.["x-cache-hit"]).toBe("true");
    });

    it("streams chat, responses, and agent-run events as typed SSE payloads", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            [
              'data: {"id":"chatcmpl_stream_123","object":"chat.completion.chunk","model":"text.tokenizer","provider_backend":null,"provider_model_id":null,"provider_attempts":[],"choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}',
              "",
              'data: {"id":"chatcmpl_stream_123","object":"chat.completion.chunk","model":"text.tokenizer","provider_backend":null,"provider_model_id":null,"provider_attempts":[],"choices":[{"index":0,"delta":{"content":"Deterministic utility response."},"finish_reason":null}]}',
              "",
              'data: {"id":"chatcmpl_stream_123","object":"chat.completion.chunk","model":"text.tokenizer","provider_backend":null,"provider_model_id":null,"provider_attempts":[],"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}',
              "",
              "data: [DONE]",
              "",
            ].join("\n"),
            { status: 200, headers: { "Content-Type": "text/event-stream" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            [
              'data: {"type":"response.created","response":{"id":"resp_stream_123","object":"response","status":"in_progress","model":"text.tokenizer","provider_backend":null,"provider_model_id":null,"provider_attempts":[]}}',
              "",
              'data: {"type":"response.output_item.done","output_index":0,"item":{"id":"resp_stream_123_item_0","object":"response.output","index":0,"provider_backend":null,"provider_model_id":null,"provider_attempts":[],"content":[{"type":"tokenization","text":"alpha beta","tokens":["alpha","beta"],"token_count":2,"embedding":null}]}}',
              "",
              'data: {"type":"response.completed","response":{"id":"resp_stream_123","object":"response","status":"completed","model":"text.tokenizer","provider_backend":null,"provider_model_id":null,"provider_attempts":[],"usage":{"prompt_tokens":2,"total_tokens":2}}}',
              "",
              "data: [DONE]",
              "",
            ].join("\n"),
            { status: 200, headers: { "Content-Type": "text/event-stream" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            [
              'data: {"type":"agent.run.event","run_id":"8e3c9e2c-b67d-42da-b456-1de39d7289fb","event":{"event_id":"evt_1","event_type":"run_created","status":"paused","message":"Run created and awaiting approval.","created_at":"2026-05-24T12:00:00Z","details":{"pending_action":"approve"}}}',
              "",
              'data: {"type":"agent.run.completed","run_id":"8e3c9e2c-b67d-42da-b456-1de39d7289fb","status":"completed","total_events":1}',
              "",
              "data: [DONE]",
              "",
            ].join("\n"),
            { status: 200, headers: { "Content-Type": "text/event-stream" } },
          ),
        );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const chatChunks = [];
      for await (const chunk of client.streamChatCompletions({
        messages: [{ role: "user", content: "Summarize" }],
      })) {
        chatChunks.push(chunk);
      }

      const responseEvents = [];
      for await (const event of client.streamResponses({
        model: "text.tokenizer",
        input: "alpha beta",
      })) {
        responseEvents.push(event);
      }

      const runEvents = [];
      for await (const event of client.streamAgentRunEvents(
        "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        { limit: 25 },
      )) {
        runEvents.push(event);
      }

      expect(chatChunks[0]?.choices[0]?.delta.role).toBe("assistant");
      expect(chatChunks[1]?.choices[0]?.delta.content).toBe("Deterministic utility response.");
      expect(chatChunks[2]?.choices[0]?.finish_reason).toBe("stop");
      expect(chatChunks[0]?.provider_backend).toBeNull();
      expect(chatChunks[0]?.provider_model_id).toBeNull();
      expect(responseEvents[0]?.type).toBe("response.created");
      expect(responseEvents[0]?.response?.provider_backend).toBeNull();
      expect(responseEvents[0]?.response?.provider_model_id).toBeNull();
      expect(responseEvents[1]?.item?.provider_backend).toBeNull();
      expect(responseEvents[1]?.item?.provider_model_id).toBeNull();
      expect(responseEvents[1]?.item?.content[0]?.tokens).toEqual(["alpha", "beta"]);
      expect(responseEvents[2]?.response?.status).toBe("completed");
      expect(runEvents[0]?.event?.event_type).toBe("run_created");
      expect(runEvents[1]?.status).toBe("completed");

      expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body)).stream).toBe(true);
      expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body)).stream).toBe(true);
      expect(fetchMock.mock.calls[2]?.[0]).toBe(
        "https://example.test/v1/agent/runs/8e3c9e2c-b67d-42da-b456-1de39d7289fb/events?limit=25&stream=true",
      );
    });

    it("falls back to the OpenAPI contract extension when /v1/meta/contract is missing", async () => {
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
                api: {
                  contract_endpoint: "/v1/meta/contract",
                  query_batch_endpoint: "/v1/query/batch",
                },
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

      const contract = await client.getContract();

      expect(contract.api_base_url).toBe("https://example.test/self-host");
      expect(contract.mcp_endpoint).toBe("https://example.test/self-host/mcp");
      expect(contract.defaults.read_only_default).toBe(true);
      expectManifestBackedIntegrationsEqual(contract.integrations, INTEGRATIONS);
      expect(contract.primary_data_query_contract.api.query_batch_endpoint).toBe(
        "/v1/query/batch",
      );
      expect(fetchMock.mock.calls.map(call => call[0])).toEqual([
        "https://example.test/self-host/v1/meta/contract",
        "https://example.test/self-host/openapi.json",
      ]);
    });

    it("polls typed async jobs until completion", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              job_id: "11111111-1111-1111-1111-111111111111",
              run_id: "22222222-2222-2222-2222-222222222222",
              org_id: "33333333-3333-3333-3333-333333333333",
              status: "running",
              queue_name: "default",
              retry_count: 0,
              callback_status: "pending",
              created_at: "2026-05-24T12:00:00Z",
              poll_url: "https://example.test/v1/jobs/11111111-1111-1111-1111-111111111111",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              job_id: "11111111-1111-1111-1111-111111111111",
              run_id: "22222222-2222-2222-2222-222222222222",
              org_id: "33333333-3333-3333-3333-333333333333",
              status: "completed",
              queue_name: "default",
              retry_count: 0,
              callback_status: "pending",
              created_at: "2026-05-24T12:00:00Z",
              completed_at: "2026-05-24T12:01:00Z",
              poll_url: "https://example.test/v1/jobs/11111111-1111-1111-1111-111111111111",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              job_id: "11111111-1111-1111-1111-111111111111",
              result: { score: 0.99 },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      vi.stubGlobal("fetch", fetchMock);
      vi.useFakeTimers();

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const pollPromise = client.pollJob("11111111-1111-1111-1111-111111111111", {
        timeoutMs: 1_000,
        pollIntervalMs: 50,
      });
      await vi.advanceTimersByTimeAsync(50);
      const result = await pollPromise;

      expect(result).toEqual({
        job_id: "11111111-1111-1111-1111-111111111111",
        result: { score: 0.99 },
      });
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        "https://example.test/v1/jobs/11111111-1111-1111-1111-111111111111",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        2,
        "https://example.test/v1/jobs/11111111-1111-1111-1111-111111111111",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        3,
        "https://example.test/v1/jobs/11111111-1111-1111-1111-111111111111/result",
        expect.objectContaining({ method: "GET" }),
      );
      vi.useRealTimers();
    });
});
