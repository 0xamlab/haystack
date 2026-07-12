// Tests for DecisionEngineClient: loads_a.
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

describe("DecisionEngineClient — loads_a", () => {

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

    it("loads a persisted hosted binding token for new client instances", async () => {
      const runtimeDir = fs.mkdtempSync(path.join(os.tmpdir(), "algenta-ts-binding-"));
      process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
      process.env.ALGENTA_DEVICE_ID = "ts-device-00000001";
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeQueryResponse()), {
            status: 200,
            headers: {
              "Content-Type": "application/json",
              "X-Algenta-Device-Binding-Token": "binding-token-000000000000000001",
            },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(makeQueryResponse()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      vi.stubGlobal("fetch", fetchMock);

      try {
        const firstClient = new DecisionEngineClient({
          apiKey: "de_test_123",
          baseUrl: "https://example.test",
          maxRetries: 0,
          timeout: 1_000,
        });
        await firstClient.query({
          source_name: "orders",
          metric_column: "revenue",
          aggregation: "sum",
        });

        const secondClient = new DecisionEngineClient({
          apiKey: "de_test_123",
          baseUrl: "https://example.test",
          maxRetries: 0,
          timeout: 1_000,
        });
        await secondClient.query({
          source_name: "orders",
          metric_column: "revenue",
          aggregation: "sum",
        });

        expect(fetchMock.mock.calls[1]?.[1]).toEqual(
          expect.objectContaining({
            headers: expect.objectContaining({
              "X-Algenta-Device-Binding-Token": "binding-token-000000000000000001",
            }),
          }),
        );
      } finally {
        fs.rmSync(runtimeDir, { recursive: true, force: true });
      }
    });

    it("loads the machine-readable Algenta contract", async () => {
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify(makeContractPayload()),
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

      const contract = await client.getContract();

      expect(contract.primary_data_query_contract.api.contract_endpoint).toBe("/v1/meta/contract");
      expect(contract.primary_data_query_contract.mcp.contract_tool).toBe("get_contract");
      expect(fetchMock).toHaveBeenCalledWith(
        "https://example.test/v1/meta/contract",
        expect.objectContaining({ method: "GET" }),
      );
    });

    it("loads the signed runtime manifest without fallback", async () => {
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            runtime_version: "2026.05.0",
            mojo_version: "25.6.0",
            llm_core_manifest: "llm-core-v1",
            module_manifest_version: "runtime-manifest-v1",
            generated_at: "2026-05-22T00:00:00Z",
            modules: [
              {
                name: "bpe_tokenizer",
                capability_id: "mojo_llm_runtime_core.bpe_tokenizer",
                owner: "algenta-runtime-core",
                contract_boundary: "Deterministic Mojo kernel with a bounded manifest-listed surface.",
                function_count: 1,
                functions: ["bpe_encode"],
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
                compiled_artifact: "mojo_build/simulate",
                compiled_engine: "mojo",
                max_cold_ms: 12.0,
                max_warm_ms: 4.0,
                max_hot_ms: 2.0,
              },
            ],
            compiled_artifacts: [],
            supported_channels: ["python_sdk", "typescript_sdk", "cli", "mcp"],
            validated_auxiliary_channels: ["bundled_worker", "runtime_local"],
            feature_flag_channels: ["http_api_feature_flag"],
            maturity: { bpe_tokenizer: "channel_covered" },
            policy_snapshot: {
              snapshot_id: "policy",
              sha256: "a".repeat(64),
              source: "policy",
              description: "policy",
            },
            schema_snapshot: {
              snapshot_id: "schema",
              sha256: "b".repeat(64),
              source: "schema",
              description: "schema",
            },
            deployment_mode: "saas",
            deployment_modes: {
              current: "saas",
              supported_modes: [
                "saas",
                "vpc",
                "self_hosted",
                "air_gapped",
                "hybrid_provider",
                "local_dev_daemon",
              ],
              rule: "Current deployment mode is environment-derived or explicitly supplied through ALGENTA_DEPLOYMENT_MODE.",
            },
            shipping_contract: {
              module_count: 1,
              function_count: 1,
              runtime_core_layer: "mojo_llm_runtime_core",
              benchmark_discovery_rule: SHIPPING_BENCHMARK_DISCOVERY_RULE,
            },
            benchmark_discovery_lane: makeBenchmarkDiscoveryLanePayload({
              shipping_manifest_functions: 1,
            }),
            advertised_capabilities: {
              runtime_modules: ["bpe_tokenizer"],
              public_endpoints: ["/v1/meta/contract", "/v1/runtime/manifest"],
              admin_endpoints: [
                "/v1/admin/runtime/modules",
                "/v1/admin/runtime/benchmarks",
                "/v1/admin/runtime/validation",
              ],
              feature_flag_endpoints: [
                "/v1/libraries",
                "/v1/libraries/health",
                "/v1/libraries/execute",
              ],
            },
            system_invariants: [{ name: "Manifest Truth", statement: "manifest-listed only" }],
            execution_model: {
              state_fields: ["request"],
              allowed_transitions: ["model_call_started"],
              validity_rules: ["schema-valid"],
            },
            external_nondeterminism: {
              sources: ["provider responses"],
              rule: "capture artifacts or fail replay",
              required_artifacts: ["provider response record"],
              failure_codes: ["replay_mismatch"],
            },
            artifact_lineage: {
              artifact_flow: ["input", "outcome"],
              required_node_fields: ["node_id"],
              immutability_rule: "hash-addressed lineage only",
            },
            capability_algebra: {
              required_fields: ["tool_name"],
              enums: {
                side_effect_class: ["read_only"],
                risk_level: ["low", "critical"],
                replayability: ["deterministic"],
              },
              rules: ["MCP tools are untrusted by default."],
            },
            kernel_promotion_criteria: makeKernelPromotionCriteriaPayload(),
            proof_matrix: [
              {
                layer: "mojo_llm_runtime_core",
                status: "channel_covered",
                obligations: ["numerical parity"],
                evidence_paths: ["build/proof.json"],
              },
            ],
            benchmarking: {
              classes: [
                {
                  code: "B1",
                  description: "microkernel latency",
                  evidence_paths: ["benchmarks/summary.json"],
                },
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
            ],
            scheduler_model: {
              policies: ["FIFO"],
              minimize: ["tail latency"],
              maximize: ["GPU or CPU utilization"],
              invariants: ["No request starves indefinitely."],
            },
            memory_model: {
              regions: ["model weights"],
              rules: ["KV pages are tenant-scoped."],
              failure_codes: ["kv_cache_exhausted"],
            },
            evaluation_science: {
              dimensions: ["answer correctness"],
              methods: ["bootstrap confidence intervals"],
              release_blockers: ["replay success regression"],
            },
            typed_failures: [{ code: "replay_mismatch", description: "replay drift" }],
            threat_model: {
              threat_classes: ["prompt injection"],
              controls: ["tool allowlists"],
              non_negotiable_rules: ["MCP tools are untrusted by default."],
            },
            formal_release_theorem: {
              statement: "A release is valid iff every advertised capability is manifest-listed, proof-backed, policy-covered, replay-tested, and deployment-mode validated.",
              required_conditions: [
                "manifest-listed",
                "proof-backed",
                "policy-covered",
                "replay-tested",
                "deployment-mode validated",
              ],
            },
            release_artifact_bundle: { required_artifacts: ["signed runtime manifest"] },
            release_gates: [{ gate: "A", description: "contract-tested" }],
            immediate_implementation_sequence: [
              { pr: "PR 0", focus: "Runtime truth manifest", deliverables: ["signed manifest"] },
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
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new DecisionEngineClient({
        apiKey: "de_test_123",
        baseUrl: "https://example.test",
        maxRetries: 0,
        timeout: 1_000,
      });

      const manifest = await client.getRuntimeManifest();
      const benchmarkClass: RuntimeBenchmarkClassCode = "B1";
      const manifestProviderRoutingClass: RuntimeBenchmarkClassCode = "B8";
      const manifestReplayClass: RuntimeBenchmarkClassCode = "B6";
      const invariantName: RuntimeInvariantName = "Manifest Truth";
      const stateField: RuntimeExecutionStateField = "request";
      const validityRule: RuntimeExecutionValidityRule = "schema-valid";
      const nondeterminismSource: RuntimeExternalNondeterminismSource = "provider responses";
      const nondeterminismArtifact: RuntimeNondeterminismArtifact = "provider response record";
      const artifactFlowStep: RuntimeArtifactLineageStep = "input";
      const capabilityField: RuntimeCapabilityField = "tool_name";
      const capabilityRule: RuntimeCapabilityRule = "MCP tools are untrusted by default.";
      const lineageField: RuntimeLineageNodeField = "node_id";
      const moduleId: RuntimeModuleId = "bpe_tokenizer";
      const publicEndpoint: RuntimePublicEndpoint = "/v1/meta/contract";
      const adminEndpoint: RuntimeAdminEndpoint = "/v1/admin/runtime/modules";
      const featureFlagEndpoint: RuntimeFeatureFlagEndpoint = "/v1/libraries";
      const replayFailure: RuntimeFailureCode = "replay_mismatch";
      const memoryFailure: RuntimeFailureCode = "kv_cache_exhausted";
      const proofObligation: RuntimeProofObligation = "numerical parity";
      const benchmarkMetric: RuntimeBenchmarkMetric = "p50";
      const benchmarkBaseline: RuntimeBenchmarkBaseline = "Algenta Mojo-native path";
      const evaluationDimension: RuntimeEvaluationDimension = "answer correctness";
      const evaluationMethod: RuntimeEvaluationMethod = "bootstrap confidence intervals";
      const releaseBlocker: RuntimeReleaseBlocker = "replay success regression";
      const threatClass: RuntimeThreatClass = "prompt injection";
      const threatControl: RuntimeThreatControl = "tool allowlists";
      const threatRule: RuntimeThreatRule = "MCP tools are untrusted by default.";
      const releaseArtifact: RuntimeReleaseArtifact = "signed runtime manifest";
      const schedulerPolicy: RuntimeSchedulerPolicy = "FIFO";
      const schedulerMinimize: RuntimeSchedulerMinimizeObjective = "tail latency";
      const schedulerMaximize: RuntimeSchedulerMaximizeObjective = "GPU or CPU utilization";
      const schedulerInvariant: RuntimeSchedulerInvariant =
        "No request starves indefinitely.";
      const budgetName: RuntimeSLOBudgetName = "runtime_manifest_load";
      const budgetAppliesTo: RuntimeSLOBudgetAppliesTo = "first-party runtime manifest route";
      const benchmarkDiscoveryRule: RuntimeBenchmarkDiscoveryRule =
        SHIPPING_BENCHMARK_DISCOVERY_RULE;
      const nonShippingRule: RuntimeNonShippingRule = NON_SHIPPING_RULE;
      const memoryRegion: RuntimeMemoryRegion = "model weights";
      const memoryRule: RuntimeMemoryRule = "KV pages are tenant-scoped.";
      const releaseGate: RuntimeReleaseGateId = "A";

      expect(manifest.llm_core_manifest).toBe("llm-core-v1");
      expect(manifest.shipping_contract.module_count).toBe(1);
      expect(manifest.shipping_contract.benchmark_discovery_rule).toBe(benchmarkDiscoveryRule);
      expect(manifest.benchmark_discovery_lane.non_shipping_rule).toBe(nonShippingRule);
      expect(manifest.system_invariants[0]?.name).toBe(invariantName);
      expect(manifest.execution_model.state_fields[0]).toBe(stateField);
      expect(manifest.execution_model.validity_rules[0]).toBe(validityRule);
      expect(manifest.execution_model.allowed_transitions[0]).toBe("model_call_started");
      expect(manifest.external_nondeterminism.sources[0]).toBe(nondeterminismSource);
      expect(manifest.external_nondeterminism.required_artifacts[0]).toBe(nondeterminismArtifact);
      expect(manifest.external_nondeterminism.failure_codes[0]).toBe(replayFailure);
      expect(manifest.artifact_lineage.artifact_flow[0]).toBe(artifactFlowStep);
      expect(manifest.artifact_lineage.required_node_fields[0]).toBe(lineageField);
      expect(manifest.capability_algebra.required_fields[0]).toBe(capabilityField);
      expect(manifest.capability_algebra.rules[0]).toBe(capabilityRule);
      expect(manifest.capability_algebra.enums.risk_level.at(-1)).toBe("critical");
      expect(manifest.modules[0]?.name).toBe(moduleId);
      expect(manifest.modules[0]?.proof_obligations[0]).toBe(proofObligation);
      expect(manifest.proof_matrix[0]?.obligations[0]).toBe(proofObligation);
      expect(manifest.proof_matrix[0]?.evidence_paths[0]).toBe("build/proof.json");
      expect(manifest.benchmarking.classes[0]?.code).toBe(benchmarkClass);
      expect(manifest.benchmarking.classes[0]?.evidence_paths[0]).toBe("benchmarks/summary.json");
      const manifestProviderRoutingOverhead = manifest.benchmarking.classes.find(
        (entry) => entry.code === manifestProviderRoutingClass,
      );
      const manifestCheckpointReplayOverhead = manifest.benchmarking.classes.find(
        (entry) => entry.code === manifestReplayClass,
      );
      expect(manifestProviderRoutingOverhead?.description).toBe("provider routing overhead");
      expect(manifestProviderRoutingOverhead?.evidence_paths).toEqual([
        "build/provider_routing_overhead_benchmark.json",
        "benchmarks/provider_routing_overhead_benchmark.py",
        "tests/test_provider_routing_overhead_benchmark.py",
      ]);
      expect(manifestCheckpointReplayOverhead?.description).toBe("checkpoint and replay overhead");
      expect(manifestCheckpointReplayOverhead?.evidence_paths).toEqual([]);
      expect(manifest.benchmarking.required_metrics[0]).toBe(benchmarkMetric);
      expect(manifest.benchmarking.baselines.at(-1)).toBe(benchmarkBaseline);
      expect(manifest.slo_budgets[0]?.name).toBe(budgetName);
      expect(manifest.slo_budgets[0]?.applies_to).toBe(budgetAppliesTo);
      expect(manifest.scheduler_model.policies[0]).toBe(schedulerPolicy);
      expect(manifest.scheduler_model.minimize[0]).toBe(schedulerMinimize);
      expect(manifest.scheduler_model.maximize[0]).toBe(schedulerMaximize);
      expect(manifest.scheduler_model.invariants[0]).toBe(schedulerInvariant);
      expect(manifest.memory_model.regions[0]).toBe(memoryRegion);
      expect(manifest.memory_model.rules[0]).toBe(memoryRule);
      expect(manifest.memory_model.failure_codes[0]).toBe(memoryFailure);
      expect(manifest.evaluation_science.dimensions[0]).toBe(evaluationDimension);
      expect(manifest.evaluation_science.methods[0]).toBe(evaluationMethod);
      expect(manifest.evaluation_science.release_blockers[0]).toBe(releaseBlocker);
      expect(manifest.threat_model.threat_classes[0]).toBe(threatClass);
      expect(manifest.threat_model.controls[0]).toBe(threatControl);
      expect(manifest.threat_model.non_negotiable_rules[0]).toBe(threatRule);
      expect(manifest.release_artifact_bundle.required_artifacts[0]).toBe(releaseArtifact);
      expect(manifest.release_gates[0]?.gate).toBe(releaseGate);
      expect(manifest.immediate_implementation_sequence[0]?.pr).toBe("PR 0");
      expect(manifest.formal_release_theorem.required_conditions).toContain("manifest-listed");
      expect(manifest.signature.scope).toBe("control_plane_hmac_v1");
      expect(manifest.advertised_capabilities.runtime_modules[0]).toBe(moduleId);
      expect(manifest.advertised_capabilities.public_endpoints[0]).toBe(publicEndpoint);
      expect(manifest.advertised_capabilities.admin_endpoints[0]).toBe(adminEndpoint);
      expect(manifest.advertised_capabilities.feature_flag_endpoints[0]).toBe(featureFlagEndpoint);
      expect(fetchMock).toHaveBeenCalledWith(
        "https://example.test/v1/runtime/manifest",
        expect.objectContaining({ method: "GET" }),
      );
    });
});
