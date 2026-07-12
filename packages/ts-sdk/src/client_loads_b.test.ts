// Tests for DecisionEngineClient: loads_b.
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

describe("DecisionEngineClient — loads_b", () => {

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

    it("loads typed runtime admin proof surfaces without fallback", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              runtime_version: "2026.05.0",
              llm_core_manifest: "llm-core-v1",
              module_manifest_version: "runtime-manifest-v1",
              shipping_contract: {
                module_count: 1,
                function_count: 2,
                runtime_core_layer: "mojo_llm_runtime_core",
                benchmark_discovery_rule: SHIPPING_BENCHMARK_DISCOVERY_RULE,
              },
              summary: {
                module_count: 1,
                function_count: 2,
                maturity_counts: { channel_covered: 1 },
                layer_counts: { mojo_llm_runtime_core: 1 },
              },
              proof_matrix: [
                {
                  layer: "mojo_llm_runtime_core",
                  status: "channel_covered",
                  obligations: ["numerical parity"],
                  evidence_paths: ["build/proof.json"],
                },
              ],
              modules: [
                {
                  name: "bpe_tokenizer",
                  capability_id: "mojo_llm_runtime_core.bpe_tokenizer",
                  owner: "algenta-runtime-core",
                  contract_boundary:
                    "Deterministic Mojo kernel with a bounded manifest-listed surface.",
                  function_count: 2,
                  functions: ["encode", "decode"],
                  layer: "mojo_llm_runtime_core",
                  maturity: "channel_covered",
                  public_supported_channels: ["python_sdk", "typescript_sdk", "cli", "mcp"],
                  validated_auxiliary_channels: ["bundled_worker", "runtime_local"],
                  feature_flag_channels: ["http_api_feature_flag"],
                  proof_obligations: ["numerical parity"],
                  proof_artifacts: ["build/proof.json"],
                  promotion_status: "shipping",
                  rollback_flag: "runtime.manifest.module.bpe_tokenizer.rollback_to_python",
                  benchmark_report_ref: "build/bench.json",
                  parity_report_ref: "build/llm_rollout_parity_benchmark.json",
                  schema_compat_report_ref: "tests/test_runtime_schema_surface.py",
                  isolation_proof_ref: "tests/test_runtime_manifest.py",
                  replay_proof_ref: "tests/test_runtime_release_validation.py",
                  benchmark_artifact: "build/bench.json",
                  benchmark_speedup_x: 101.0,
                  compiled_artifact: "mojo_build/bpe_tokenizer",
                  compiled_engine: "mojo",
                  max_cold_ms: 12.0,
                  max_warm_ms: 4.0,
                  max_hot_ms: 2.0,
                },
              ],
              manifest_digest: "c".repeat(64),
              signature: {
                algorithm: "hmac-sha256",
                key_id: "runtime-manifest-signing-v1",
                digest_hex: "c".repeat(64),
                signature_hex: "d".repeat(64),
                scope: "control_plane_hmac_v1",
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              runtime_version: "2026.05.0",
              llm_core_manifest: "llm-core-v1",
              module_manifest_version: "runtime-manifest-v1",
              benchmark_discovery_lane: makeBenchmarkDiscoveryLanePayload({
                shipping_manifest_functions: 1,
              }),
              benchmarking: {
                classes: [
                  {
                    code: "B8",
                    description: "provider routing overhead",
                    evidence_paths: [
                      "build/provider_routing_overhead_benchmark.json",
                      "benchmarks/provider_routing_overhead_benchmark.py",
                      "tests/test_provider_routing_overhead_benchmark.py",
                    ],
                  },
                  {
                    code: "B6",
                    description: "checkpoint and replay overhead",
                    evidence_paths: [],
                  },
                  {
                    code: "B7",
                    description: "MCP tool latency",
                    evidence_paths: [],
                  },
                  {
                    code: "B9",
                    description: "RAG retrieval quality and latency",
                    evidence_paths: [],
                  },
                  {
                    code: "B10",
                    description: "decision workflow completion latency",
                    evidence_paths: DECISION_WORKFLOW_BENCHMARK_EVIDENCE,
                  },
                ],
                required_metrics: ["p50"],
                baselines: ["Algenta Mojo-native path"],
              },
              slo_budgets: [
                {
                  name: "runtime_manifest_load",
                  applies_to: "first-party runtime manifest route",
                  p95_objective_ms: 25,
                  hard_ceiling_ms: 100,
                },
                {
                  name: "mcp_call_first_party",
                  applies_to: "first-party or internal MCP tools",
                  p95_objective_ms: 400,
                  hard_ceiling_ms: 1200,
                },
                {
                  name: "decision_plan_creation",
                  applies_to: "decision runtime plan generation",
                  p95_objective_ms: 750,
                  hard_ceiling_ms: 2000,
                },
                {
                  name: "replay",
                  applies_to: "runs up to 1000 events",
                  p95_objective_ms: 750,
                  hard_ceiling_ms: 2000,
                },
              ],
              quality_gate_benchmark_classes: [
                {
                  code: "B6",
                  description: "checkpoint and replay overhead",
                  evidence_paths: [],
                },
                {
                  code: "B7",
                  description: "MCP tool latency",
                  evidence_paths: [],
                },
                {
                  code: "B9",
                  description: "RAG retrieval quality and latency",
                  evidence_paths: [],
                },
                {
                  code: "B10",
                  description: "decision workflow completion latency",
                  evidence_paths: DECISION_WORKFLOW_BENCHMARK_EVIDENCE,
                },
              ],
              quality_gate_slo_budgets: [
                {
                  name: "mcp_call_first_party",
                  applies_to: "first-party or internal MCP tools",
                  p95_objective_ms: 400,
                  hard_ceiling_ms: 1200,
                },
                {
                  name: "decision_plan_creation",
                  applies_to: "decision runtime plan generation",
                  p95_objective_ms: 750,
                  hard_ceiling_ms: 2000,
                },
                {
                  name: "replay",
                  applies_to: "runs up to 1000 events",
                  p95_objective_ms: 750,
                  hard_ceiling_ms: 2000,
                },
              ],
              evaluation_science: {
                dimensions: [
                  "replay success rate",
                  "tool-call correctness",
                  "retrieval precision and recall",
                  "decision outcome delta",
                ],
                methods: ["bootstrap confidence intervals"],
                release_blockers: [
                  "replay success regression",
                  "tool-call error-rate increase",
                  "RAG precision drop",
                  "decision-plan validity drop",
                ],
              },
              evaluation_summary: {
                dimension_count: 4,
                method_count: 1,
                release_blocker_count: 4,
                benchmark_class_count: 4,
                slo_budget_count: 3,
                replay_gate_enabled: true,
                tool_call_quality_gate_enabled: true,
                rag_quality_gate_enabled: true,
                decision_quality_gate_enabled: true,
              },
              compiled_artifacts: [
                {
                  kind: "compiled_mojo_binary",
                  path: "mojo_build/bpe_tokenizer",
                  sha256: "e".repeat(64),
                  size_bytes: 4096,
                },
              ],
              shipping_runtime_modules: ["bpe_tokenizer"],
              shipping_runtime_function_counts: [1],
              shipping_runtime_benchmark_speedups_x: [101.0],
              shipping_runtime_benchmark_artifacts: ["build/bench.json"],
              shipping_runtime_compiled_artifacts: ["mojo_build/bpe_tokenizer"],
              shipping_runtime_compiled_engines: ["mojo"],
              shipping_runtime_max_cold_ms: [12.0],
              shipping_runtime_max_warm_ms: [4.0],
              shipping_runtime_max_hot_ms: [2.0],
              module_benchmarks: [
                {
                  name: "bpe_tokenizer",
                  function_count: 1,
                  benchmark_artifact: "build/bench.json",
                  benchmark_speedup_x: 101.0,
                  compiled_artifact: "mojo_build/bpe_tokenizer",
                  compiled_engine: "mojo",
                  max_cold_ms: 12.0,
                  max_warm_ms: 4.0,
                  max_hot_ms: 2.0,
                },
              ],
              manifest_digest: "c".repeat(64),
              signature: {
                algorithm: "hmac-sha256",
                key_id: "runtime-manifest-signing-v1",
                digest_hex: "c".repeat(64),
                signature_hex: "d".repeat(64),
                scope: "control_plane_hmac_v1",
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              runtime_version: "2026.05.0",
              llm_core_manifest: "llm-core-v1",
              module_manifest_version: "runtime-manifest-v1",
              theorem_statement:
                "A release is valid iff every advertised capability is manifest-listed, proof-backed, policy-covered, replay-tested, and deployment-mode validated.",
              valid_release: true,
              conditions: [
                {
                  condition: "manifest-listed",
                  satisfied: true,
                  detail: "all advertised capabilities are signed manifest entries",
                  evidence_paths: ["runtime_manifest.modules"],
                },
              ],
              deployment_mode: "saas",
              deployment_mode_raw: "saas",
              manifest_digest: "c".repeat(64),
              signature: {
                algorithm: "hmac-sha256",
                key_id: "runtime-manifest-signing-v1",
                digest_hex: "c".repeat(64),
                signature_hex: "d".repeat(64),
                scope: "control_plane_hmac_v1",
              },
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

      const modules = await client.getRuntimeModules();
      const benchmarks = await client.getRuntimeBenchmarks();
      const validation = await client.getRuntimeReleaseValidation();
      const benchmarkClass: RuntimeBenchmarkClassCode = "B8";
      const qualityGateBenchmarkClass: RuntimeBenchmarkClassCode = "B6";
      const budgetAppliesTo: RuntimeSLOBudgetAppliesTo = "first-party runtime manifest route";
      const benchmarkDiscoveryRule: RuntimeBenchmarkDiscoveryRule =
        SHIPPING_BENCHMARK_DISCOVERY_RULE;
      const nonShippingRule: RuntimeNonShippingRule = NON_SHIPPING_RULE;

      expect(modules.summary.module_count).toBe(1);
      expect(modules.shipping_contract.benchmark_discovery_rule).toBe(benchmarkDiscoveryRule);
      expect(modules.modules[0]?.name).toBe("bpe_tokenizer");
      expect(modules.modules[0]?.layer).toBe("mojo_llm_runtime_core");
      expect(modules.modules[0]?.proof_obligations[0]).toBe("numerical parity");
      expect(modules.proof_matrix[0]?.obligations[0]).toBe("numerical parity");
      expect(benchmarks.compiled_artifacts[0]?.kind).toBe("compiled_mojo_binary");
      expect(benchmarks.benchmark_discovery_lane.non_shipping_rule).toBe(nonShippingRule);
      expect(benchmarks.module_benchmarks[0]?.compiled_engine).toBe("mojo");
      expect(benchmarks.module_benchmarks[0]?.function_count).toBe(1);
      expect(benchmarks.shipping_runtime_modules[0]).toBe("bpe_tokenizer");
      expect(benchmarks.shipping_runtime_function_counts[0]).toBe(
        benchmarks.module_benchmarks[0]?.function_count,
      );
      expect(benchmarks.shipping_runtime_benchmark_speedups_x[0]).toBe(
        benchmarks.module_benchmarks[0]?.benchmark_speedup_x,
      );
      expect(benchmarks.shipping_runtime_benchmark_artifacts[0]).toBe(
        benchmarks.module_benchmarks[0]?.benchmark_artifact,
      );
      expect(benchmarks.shipping_runtime_compiled_artifacts[0]).toBe(
        benchmarks.module_benchmarks[0]?.compiled_artifact,
      );
      expect(benchmarks.shipping_runtime_compiled_engines[0]).toBe(
        benchmarks.module_benchmarks[0]?.compiled_engine,
      );
      expect(benchmarks.shipping_runtime_max_cold_ms[0]).toBe(
        benchmarks.module_benchmarks[0]?.max_cold_ms,
      );
      expect(benchmarks.shipping_runtime_max_warm_ms[0]).toBe(
        benchmarks.module_benchmarks[0]?.max_warm_ms,
      );
      expect(benchmarks.shipping_runtime_max_hot_ms[0]).toBe(
        benchmarks.module_benchmarks[0]?.max_hot_ms,
      );
      const providerRoutingOverhead = benchmarks.benchmarking.classes.find(
        (entry) => entry.code === benchmarkClass,
      );
      const checkpointReplayOverhead = benchmarks.quality_gate_benchmark_classes.find(
        (entry) => entry.code === qualityGateBenchmarkClass,
      );
      const mcpToolLatency = benchmarks.quality_gate_benchmark_classes.find(
        (entry) => entry.code === "B7",
      );
      const ragRetrievalQualityLatency = benchmarks.quality_gate_benchmark_classes.find(
        (entry) => entry.code === "B9",
      );
      const decisionWorkflowCompletionLatency = benchmarks.quality_gate_benchmark_classes.find(
        (entry) => entry.code === "B10",
      );
      expect(providerRoutingOverhead?.evidence_paths).toEqual([
        "build/provider_routing_overhead_benchmark.json",
        "benchmarks/provider_routing_overhead_benchmark.py",
        "tests/test_provider_routing_overhead_benchmark.py",
      ]);
      expect(benchmarks.benchmarking.required_metrics[0]).toBe("p50");
      expect(benchmarks.benchmarking.baselines.at(-1)).toBe("Algenta Mojo-native path");
      expect(benchmarks.slo_budgets[0]?.applies_to).toBe(budgetAppliesTo);
      expect(benchmarks.slo_budgets[0]?.hard_ceiling_ms).toBe(100);
      expect(checkpointReplayOverhead?.description).toBe("checkpoint and replay overhead");
      expect(checkpointReplayOverhead?.evidence_paths).toEqual([]);
      expect(mcpToolLatency?.description).toBe("MCP tool latency");
      expect(mcpToolLatency?.evidence_paths).toEqual([]);
      expect(ragRetrievalQualityLatency?.description).toBe("RAG retrieval quality and latency");
      expect(ragRetrievalQualityLatency?.evidence_paths).toEqual([]);
      expect(decisionWorkflowCompletionLatency?.description).toBe(
        "decision workflow completion latency",
      );
      expect(decisionWorkflowCompletionLatency?.evidence_paths).toEqual(
        DECISION_WORKFLOW_BENCHMARK_EVIDENCE,
      );
      expect(benchmarks.quality_gate_slo_budgets.map((entry) => entry.name)).toEqual([
        "mcp_call_first_party",
        "decision_plan_creation",
        "replay",
      ]);
      expect(benchmarks.evaluation_summary.replay_gate_enabled).toBe(true);
      expect(benchmarks.evaluation_summary.tool_call_quality_gate_enabled).toBe(true);
      expect(benchmarks.evaluation_summary.rag_quality_gate_enabled).toBe(true);
      expect(benchmarks.evaluation_summary.decision_quality_gate_enabled).toBe(true);
      expect(benchmarks.evaluation_summary.benchmark_class_count).toBe(4);
      expect(benchmarks.evaluation_summary.slo_budget_count).toBe(3);
      expect(validation.valid_release).toBe(true);
      expect(validation.conditions[0]?.condition).toBe("manifest-listed");
      expect(validation.deployment_mode_raw).toBe("saas");
      expect(validation.signature.scope).toBe("control_plane_hmac_v1");
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        "https://example.test/v1/admin/runtime/modules",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        2,
        "https://example.test/v1/admin/runtime/benchmarks",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        3,
        "https://example.test/v1/admin/runtime/validation",
        expect.objectContaining({ method: "GET" }),
      );
    });
});
