// SPDX-License-Identifier: Apache-2.0
// Tests for DecisionEngineClient: supports_c.
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

describe("DecisionEngineClient — supports_c", () => {

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

    it("supports the plan-aligned agent run lifecycle routes", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeAgentRunPayload("requires_approval", "approve")), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeAgentRunListPayload()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeAgentRunPayload("requires_approval", "approve")), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeAgentRunEventsPayload()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeAgentRunPayload("requires_approval", "approve")), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeAgentRunPayload("cancelled")), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeAgentRunPayload("completed")), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeAgentRunCheckpointsPayload()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeAgentRunCheckpointQueryPayload()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeAgentRunMissionEventsPayload()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeAgentRunMissionEventQueryPayload()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeAgentRunTelemetryPayload()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeAgentRunTelemetryQueryPayload()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeAgentRunReplayPayload()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeAgentRunPayload("paused", "resume")), {
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

      const created = await client.createAgentRun({
        task: "Search the knowledge base",
        approval_mode: "manual",
        output_format: "markdown",
      });
      const listed = await client.listAgentRuns({ status: "requires_approval" });
      const fetched = await client.getAgentRun("8e3c9e2c-b67d-42da-b456-1de39d7289fb");
      const events = await client.getAgentRunEvents("8e3c9e2c-b67d-42da-b456-1de39d7289fb", {
        limit: 25,
      });
      const resumed = await client.resumeAgentRun("8e3c9e2c-b67d-42da-b456-1de39d7289fb");
      const cancelled = await client.cancelAgentRun("8e3c9e2c-b67d-42da-b456-1de39d7289fb");
      const approved = await client.approveAgentRun("8e3c9e2c-b67d-42da-b456-1de39d7289fb");
      const checkpoints = await client.listAgentRunCheckpoints(
        "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
      );
      const checkpointQuery = await client.queryAgentRunCheckpoints({
        status: "completed",
        request_hash: "a".repeat(64),
        policy_snapshot_id: "policy-v1",
        schema_snapshot_id: "schema-v1",
        run_id: "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        checkpoint_id: "cp_2",
      });
      const missionEvents = await client.listAgentRunMissionEvents(
        "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        { limit: 25 },
      );
      const missionEventQuery = await client.queryAgentRunMissionEvents({
        status: "completed",
        request_hash: "a".repeat(64),
        policy_snapshot_id: "policy-v1",
        schema_snapshot_id: "schema-v1",
        run_id: "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        event_type: "run_created",
      });
      const telemetry = await client.listAgentRunTelemetry(
        "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        { limit: 25 },
      );
      const telemetryQuery = await client.queryAgentRunTelemetry({
        status: "completed",
        request_hash: "a".repeat(64),
        policy_snapshot_id: "policy-v1",
        schema_snapshot_id: "schema-v1",
        run_id: "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        telemetry_kind: "agent_run_completion",
        module_name: "agent_run_service",
      });
      const replay = await client.replayAgentRun("8e3c9e2c-b67d-42da-b456-1de39d7289fb", {
        checkpoint_id: "cp_2",
      });
      const forked = await client.forkAgentRun("8e3c9e2c-b67d-42da-b456-1de39d7289fb", {
        checkpoint_id: "cp_1",
      });

      expect(created.pending_action).toBe("approve");
      expect(listed.total).toBe(1);
      expect(listed.data[0]?.status).toBe("requires_approval");
      expect(created.latest_checkpoint_id).toBe("cp_2");
      expect(fetched.steps[0]?.action).toBe("Planning execution for: Search the knowledge base");
      expect(fetched.steps[1]?.tool_name).toBe("search");
      expect(events.total_events).toBe(1);
      expect(resumed.status).toBe("requires_approval");
      expect(cancelled.status).toBe("cancelled");
      expect(approved.status).toBe("completed");
      expect(checkpoints.total_checkpoints).toBe(2);
      expect(checkpoints.data[1]?.checkpoint_id).toBe("cp_2");
      expect(checkpointQuery.total).toBe(1);
      expect(checkpointQuery.data[0]?.run_status).toBe("completed");
      expect(checkpointQuery.data[0]?.checkpoint_id).toBe("cp_2");
      expect(missionEvents.total_events).toBe(1);
      expect(missionEvents.data[0]?.event_message).toBe("Agent run created.");
      expect(missionEventQuery.total).toBe(1);
      expect(missionEventQuery.data[0]?.run_status).toBe("completed");
      expect(telemetry.total_batches).toBe(1);
      expect(telemetry.data[0]?.telemetry_kind).toBe("agent_run_completion");
      expect(telemetryQuery.total).toBe(1);
      expect(telemetryQuery.data[0]?.module_name).toBe("agent_run_service");
      expect(replay.replay_status).toBe("matched");
      expect(forked.pending_action).toBe("resume");
      expect(fetchMock.mock.calls[1]?.[0]).toBe(
        "https://example.test/v1/agent/runs?page=1&limit=25&status=requires_approval",
      );
      expect(fetchMock.mock.calls[3]?.[0]).toBe(
        "https://example.test/v1/agent/runs/8e3c9e2c-b67d-42da-b456-1de39d7289fb/events?limit=25",
      );
      expect(fetchMock.mock.calls[7]?.[0]).toBe(
        "https://example.test/v1/agent/runs/8e3c9e2c-b67d-42da-b456-1de39d7289fb/checkpoints",
      );
      expect(fetchMock.mock.calls[8]?.[0]).toBe(
        "https://example.test/v1/agent/runs/checkpoints?page=1&limit=25&status=completed&request_hash="
        + "a".repeat(64)
        + "&policy_snapshot_id=policy-v1&schema_snapshot_id=schema-v1&run_id=8e3c9e2c-b67d-42da-b456-1de39d7289fb&checkpoint_id=cp_2",
      );
      expect(fetchMock.mock.calls[9]?.[0]).toBe(
        "https://example.test/v1/agent/runs/8e3c9e2c-b67d-42da-b456-1de39d7289fb/mission-events?limit=25",
      );
      expect(fetchMock.mock.calls[10]?.[0]).toBe(
        "https://example.test/v1/agent/runs/mission-events?page=1&limit=25&status=completed&request_hash="
        + "a".repeat(64)
        + "&policy_snapshot_id=policy-v1&schema_snapshot_id=schema-v1&run_id=8e3c9e2c-b67d-42da-b456-1de39d7289fb&event_type=run_created",
      );
      expect(fetchMock.mock.calls[11]?.[0]).toBe(
        "https://example.test/v1/agent/runs/8e3c9e2c-b67d-42da-b456-1de39d7289fb/telemetry?limit=25",
      );
      expect(fetchMock.mock.calls[12]?.[0]).toBe(
        "https://example.test/v1/agent/runs/telemetry?page=1&limit=25&status=completed&request_hash="
        + "a".repeat(64)
        + "&policy_snapshot_id=policy-v1&schema_snapshot_id=schema-v1&run_id=8e3c9e2c-b67d-42da-b456-1de39d7289fb&telemetry_kind=agent_run_completion&module_name=agent_run_service",
      );
      expect(fetchMock.mock.calls[13]?.[0]).toBe(
        "https://example.test/v1/agent/runs/8e3c9e2c-b67d-42da-b456-1de39d7289fb/replay",
      );
    });

    it("supports the simplified product api helpers", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeProductDecisionPayload()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeProductAgentRunPayload()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeProductOptimizePayload()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeProductRetrievePayload()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeProductForecastPayload()), {
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

      const decision = await client.productDecision({
        inputs: [
          { name: "revenue", value: 125000, low: 100000, high: 160000 },
          { name: "cost", value: 72000, low: 65000, high: 90000 },
        ],
        objective: "maximize_expected_value",
        risk_tolerance: "balanced",
        scenarios: 10000,
        engine: "product",
        label: "launch-eval",
      });
      const agentRun = await client.productAgentRun({
        task: "Search launch preparation docs",
        context: { area: "operations" },
        tools: ["search", "simulate"],
        max_steps: 4,
        output_format: "markdown",
      });
      const optimization = await client.productOptimize({
        objective: "maximize_margin",
        variables: [{ name: "price", min: 95, max: 140, step: 1 }],
        constraints: [{ expression: "price >= 100", required: true }],
        iterations: 1200,
        engine: "product",
      });
      const retrieval = await client.productRetrieve({
        query: "launch checklist",
        documents: [
          { id: "doc_1", content: "Launch checklist for product release." },
          { id: "doc_2", content: "Retention analysis for pilot customers." },
        ],
        top_k: 2,
        rerank: true,
      });
      const forecast = await client.productForecast({
        metric: "monthly_revenue",
        history: [118000, 121000, 125000, 128500],
        horizon: 3,
        seasonality: true,
        confidence_level: 0.9,
      });

      expect(decision.action).toBe("proceed");
      expect(agentRun.steps[0]?.tool).toBe("search");
      expect(optimization.optimal_values.price).toBe(119);
      expect(retrieval.results[0]?.document_id).toBe("doc_1");
      expect(forecast.periods[0]?.trend).toBe("up");
      expect(fetchMock.mock.calls[0]?.[0]).toBe("https://example.test/v1/decision");
      expect(fetchMock.mock.calls[1]?.[0]).toBe("https://example.test/v1/agent/run");
      expect(fetchMock.mock.calls[2]?.[0]).toBe("https://example.test/v1/optimize");
      expect(fetchMock.mock.calls[3]?.[0]).toBe("https://example.test/v1/retrieve");
      expect(fetchMock.mock.calls[4]?.[0]).toBe("https://example.test/v1/forecast");
    });

    it("supports the decision-memory lifecycle routes", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeDecisionLogPayload()), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeDecisionListPayload()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeDecisionLogPayload()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeDecisionLogPayload({
            actual_outcome: 141000,
            outcome_delta: 13000,
            outcome_recorded_at: "2026-05-24T12:30:00Z",
          })), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeExecutionReceiptPayload()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(new Response(null, { status: 204 }));
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const logged = await client.logDecision({
        chosen_action: "expand",
        context: "Launch planning",
        expected_value: 128000,
      });
      const listed = await client.listDecisions({ page: 1, limit: 20, with_outcome_only: true });
      const fetched = await client.getDecision("decision_123");
      const outcome = await client.recordOutcome("decision_123", {
        actual_outcome: 141000,
        outcome_notes: "Launch outperformed baseline",
      });
      const executed = await client.executeDecision("decision_123", {
        webhook_url: "https://hooks.example.test/decision",
      });
      const deleted = await client.deleteDecision("decision_123");

      expect(logged.chosen_action).toBe("expand");
      expect(logged.policy_snapshot_id).toBe("policy-v1");
      expect(listed.decisions[0]?.id).toBe("decision_123");
      expect(listed.decisions[0]?.schema_snapshot_id).toBe("schema-v1");
      expect(fetched.context).toBe("Launch planning");
      expect(fetched.manifest_version).toBe("runtime-manifest-v1");
      expect(outcome.outcome_delta).toBe(13000);
      expect(executed.execution_status).toBe("delivered");
      expect(executed.policy_snapshot_id).toBe("execution-policy-v1-r2:abcd1234abcd1234");
      expect(executed.schema_snapshot_id).toBe("schema-v1");
      expect(executed.manifest_version).toBe("runtime-manifest-v1");
      expect(deleted).toEqual({});
    });

    it("supports the decision-runtime helper routes", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeRecommendPayload()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeScorePayload()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              total: 2,
              succeeded: 2,
              failed: 0,
              results: [
                { index: 0, success: true, envelope: makeDecisionEnvelopePayload() },
                {
                  index: 1,
                  success: true,
                  envelope: makeDecisionEnvelopePayload({ recommended_action: "stretch" }),
                },
              ],
            }),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            },
          ),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeComparePayload()), {
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

      const recommend = await client.recommend(
        [
          {
            name: "expand",
            request: {
              mode: "expert",
              runs: 250,
              simulation: {
                variables: [
                  { name: "outcome", distribution: "fixed", params: { value: 140000 } },
                ],
                objective_function: "outcome",
              },
            },
          },
          {
            name: "hold",
            request: {
              mode: "expert",
              runs: 250,
              simulation: {
                variables: [
                  { name: "outcome", distribution: "fixed", params: { value: 90000 } },
                ],
                objective_function: "outcome",
              },
            },
          },
        ],
        { runs: 250, seed: 42 },
      );
      const score = await client.score(
        {
          mode: "expert",
          runs: 250,
          simulation: {
            variables: [{ name: "outcome", distribution: "fixed", params: { value: 120000 } }],
            objective_function: "outcome",
          },
        },
        { expected_value: 0.7, downside_risk: 0.3 },
      );
      const batch = await client.batch([
        {
          mode: "expert",
          runs: 100,
          simulation: {
            variables: [{ name: "outcome", distribution: "fixed", params: { value: 100 } }],
            objective_function: "outcome",
          },
        },
        {
          mode: "expert",
          runs: 100,
          simulation: {
            variables: [{ name: "outcome", distribution: "fixed", params: { value: 120 } }],
            objective_function: "outcome",
          },
        },
      ]);
      const compare = await client.compare([
        {
          name: "base",
          request: {
            mode: "expert",
            runs: 150,
            simulation: {
              variables: [{ name: "outcome", distribution: "fixed", params: { value: 100 } }],
              objective_function: "outcome",
            },
          },
        },
        {
          name: "stretch",
          request: {
            mode: "expert",
            runs: 150,
            simulation: {
              variables: [{ name: "outcome", distribution: "fixed", params: { value: 120 } }],
              objective_function: "outcome",
            },
          },
        },
      ]);

      expect(recommend.recommended_action).toBe("expand");
      expect(recommend.action_results[0]?.rank).toBe(1);
      expect(score.score).toBe(0.73);
      expect(score.score_breakdown.expected_value).toBe(0.61);
      expect(batch.total).toBe(2);
      expect(batch.results[1]?.envelope?.recommended_action).toBe("stretch");
      expect(compare.winner).toBe("stretch");
      expect(compare.scenarios[0]?.name).toBe("base");
      expect(fetchMock.mock.calls[0]?.[0]).toBe("https://example.test/v1/recommend");
      expect(fetchMock.mock.calls[1]?.[0]).toBe("https://example.test/v1/score");
      expect(fetchMock.mock.calls[2]?.[0]).toBe("https://example.test/v1/batch");
      expect(fetchMock.mock.calls[3]?.[0]).toBe("https://example.test/v1/compare");
    });

    it("supports API key lifecycle endpoints with optional expiry metadata", async () => {
      const expiresAt = new Date("2028-05-19T00:00:00.000Z");
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              api_keys: [
                {
                  id: "key_1",
                  label: "Mission Runtime Key",
                  key_prefix: "de_live_abcd",
                  device_limit: 3,
                  status: "active",
                  created_at: "2026-05-19T00:00:00Z",
                  expires_at: "2028-05-19T00:00:00Z",
                },
              ],
              total: 1,
              page: 1,
              limit: 50,
              pages: 1,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              id: "key_2",
              label: "Mission Rotation Key",
              key_prefix: "de_live_efgh",
              device_limit: 2,
              raw_key: "de_live_efgh_secret_value",
              created_at: "2026-05-19T00:00:00Z",
              expires_at: "2028-05-19T00:00:00Z",
            }),
            { status: 201, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(null, {
            status: 204,
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

      const listed = await client.listApiKeys();
      const created = await client.createApiKey({
        label: "Mission Rotation Key",
        expires_at: expiresAt,
        device_limit: 2,
      });
      const revoked = await client.revokeApiKey("key_2");

      expect(listed[0]?.expires_at).toBe("2028-05-19T00:00:00Z");
      expect(listed[0]?.key_prefix).toBe("de_live_abcd");
      expect(listed[0]?.device_limit).toBe(3);
      expect("raw_key" in (listed[0] ?? {})).toBe(false);
      expect(created.id).toBe("key_2");
      expect(created.key_prefix).toBe("de_live_efgh");
      expect(created.device_limit).toBe(2);
      expect(created.raw_key.startsWith(created.key_prefix)).toBe(true);
      expect(revoked).toEqual({});
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        "https://example.test/v1/api-keys",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        2,
        "https://example.test/v1/api-keys",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            label: "Mission Rotation Key",
            expires_at: "2028-05-19T00:00:00.000Z",
            device_limit: 2,
          }),
        }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        3,
        "https://example.test/v1/api-keys/key_2",
        expect.objectContaining({ method: "DELETE" }),
      );
    });
});
