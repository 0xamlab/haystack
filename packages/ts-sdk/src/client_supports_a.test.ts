// SPDX-License-Identifier: Apache-2.0
// Tests for DecisionEngineClient: supports_a.
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

describe("DecisionEngineClient — supports_a", () => {

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

    it("supports connector onboarding endpoints through the public API", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              id: "conn_1",
              name: "Warehouse Postgres",
              connector_type: "postgres",
              status: "untested",
              visibility: "private",
            }),
            { status: 201, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              connectors: [
                {
                  id: "conn_1",
                  name: "Warehouse Postgres",
                  connector_type: "postgres",
                  status: "live",
                  visibility: "private",
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
              success: true,
              message: "ok",
              latency_ms: 12,
              status: "live",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              connector_type: "postgres",
              items: [{ id: "public.orders", label: "orders", kind: "table" }],
              total: 1,
              message: "1 table available.",
              labels: { entity_noun: "table" },
              discovery: { scope_noun: "schema" },
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

      const created = await client.createConnector({
        name: "Warehouse Postgres",
        connector_type: "postgres",
        config: { host: "db.internal", database: "analytics" },
      });
      const listed = await client.listConnectors({ page: 1, limit: 50 });
      const tested = await client.testConnector("conn_1");
      const browsed = await client.browseConnector("conn_1");

      expect(created.id).toBe("conn_1");
      expect(listed.connectors[0]?.id).toBe("conn_1");
      expect(tested.success).toBe(true);
      expect(browsed.items).toHaveLength(1);
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        "https://example.test/v1/connectors",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            name: "Warehouse Postgres",
            connector_type: "postgres",
            config: { host: "db.internal", database: "analytics" },
          }),
        }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        2,
        "https://example.test/v1/connectors?page=1&limit=50",
        expect.objectContaining({ method: "GET" }),
      );
    });

    it("supports repository intelligence lifecycle endpoints", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              supported_languages: ["python", "typescript", "coq"],
              support_progress: {
                supported_real_language_count: 3,
                ranked_target_language_count: 180,
                progress_fraction: 3 / 180,
                progress_label: "3 / 180",
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              repository_id: "repo_1",
              snapshot_id: "snap_1",
              connector_type: "github_repo",
              ref: "main",
              resolved_revision: "abc123",
              content_hash: "hash_repo",
              status: "created",
              created_at: "2026-05-29T12:00:00Z",
              file_count: 42,
              language_counts: { python: 20, typescript: 10 },
              raw_repo_token_estimate: 3200,
              repository_snapshot_artifact: {
                artifact_id: "artifact_snapshot",
                artifact_kind: "RepositorySnapshot",
                content_hash: "hash_snapshot",
                storage_path: "/tmp/repository_snapshot.parquet",
                schema_revision: "v1",
                created_at: "2026-05-29T12:00:00Z",
              },
              repository_graph_artifact: {
                artifact_id: "artifact_graph",
                artifact_kind: "RepositoryGraph",
                content_hash: "hash_graph",
                storage_path: "/tmp/repository_graph.parquet",
                schema_revision: "v1",
                created_at: "2026-05-29T12:00:00Z",
              },
              symbol_graph_artifact: {
                artifact_id: "artifact_symbols",
                artifact_kind: "SymbolGraph",
                content_hash: "hash_symbols",
                storage_path: "/tmp/symbol_graph.parquet",
                schema_revision: "v1",
                created_at: "2026-05-29T12:00:00Z",
              },
              dependency_graph_artifact: {
                artifact_id: "artifact_dependencies",
                artifact_kind: "DependencyGraph",
                content_hash: "hash_dependencies",
                storage_path: "/tmp/dependency_graph.parquet",
                schema_revision: "v1",
                created_at: "2026-05-29T12:00:00Z",
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              repository_id: "repo_1",
              snapshot_id: "snap_1",
              connector_type: "github_repo",
              ref: "main",
              resolved_revision: "abc123",
              content_hash: "hash_repo",
              status: "existing",
              created_at: "2026-05-29T12:00:00Z",
              file_count: 42,
              language_counts: { python: 20, typescript: 10 },
              raw_repo_token_estimate: 3200,
              repository_snapshot_artifact: {
                artifact_id: "artifact_snapshot",
                artifact_kind: "RepositorySnapshot",
                content_hash: "hash_snapshot",
                storage_path: "/tmp/repository_snapshot.parquet",
                schema_revision: "v1",
                created_at: "2026-05-29T12:00:00Z",
              },
              repository_graph_artifact: {
                artifact_id: "artifact_graph",
                artifact_kind: "RepositoryGraph",
                content_hash: "hash_graph",
                storage_path: "/tmp/repository_graph.parquet",
                schema_revision: "v1",
                created_at: "2026-05-29T12:00:00Z",
              },
              symbol_graph_artifact: {
                artifact_id: "artifact_symbols",
                artifact_kind: "SymbolGraph",
                content_hash: "hash_symbols",
                storage_path: "/tmp/symbol_graph.parquet",
                schema_revision: "v1",
                created_at: "2026-05-29T12:00:00Z",
              },
              dependency_graph_artifact: {
                artifact_id: "artifact_dependencies",
                artifact_kind: "DependencyGraph",
                content_hash: "hash_dependencies",
                storage_path: "/tmp/dependency_graph.parquet",
                schema_revision: "v1",
                created_at: "2026-05-29T12:00:00Z",
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              repository_id: "repo_1",
              snapshot_id: "snap_1",
              workspace_evidence_bundle_ref: "bundle_1",
              created_at: "2026-05-29T12:05:00Z",
              suspect_files: ["src/service.py"],
              suspect_symbols: ["handle_issue"],
              raw_repo_token_estimate: 3200,
              evidence_bundle_token_count: 240,
              reduction_ratio: 13.333,
              evidence_items: [
                {
                  evidence_id: "evidence_1",
                  rank: 1,
                  source_type: "repository_file",
                  source_ref: "src/service.py",
                  file_path: "src/service.py",
                  symbol_name: "handle_issue",
                  summary: "Likely source file",
                  snippet: "def handle_issue():\n    pass\n",
                  token_count: 18,
                  score: 0.94,
                },
              ],
              workspace_evidence_bundle_artifact: {
                artifact_id: "artifact_bundle",
                artifact_kind: "WorkspaceEvidenceBundle",
                content_hash: "hash_bundle",
                storage_path: "/tmp/workspace_evidence_bundle.parquet",
                schema_revision: "v1",
                created_at: "2026-05-29T12:05:00Z",
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              repository_id: "repo_1",
              snapshot_id: "snap_1",
              decision_plan_id: "plan_1",
              created_at: "2026-05-29T12:10:00Z",
              decision_plan: {
                recommended_action: "Apply repository patch",
                confidence: 0.82,
                expected_value: 67.5,
                risk: {
                  p5: -12.5,
                  p95: 84.0,
                  probability_of_loss: 0.12,
                  var_95: 11.0,
                },
                options: [
                  {
                    name: "Apply repository patch",
                    rank: 1,
                    expected_value: 67.5,
                    risk: {
                      p5: -12.5,
                      p95: 84.0,
                      probability_of_loss: 0.12,
                      var_95: 11.0,
                    },
                    score: 0.82,
                  },
                ],
                rationale: "Bounded evidence localized the fault.",
                integrity: {
                  request_hash: "request_hash",
                  result_hash: "result_hash",
                },
                repository_analysis: {
                  root_cause: "Incorrect branch condition in service handler.",
                  planner_model_id: "repo-fix-model",
                  planner_execution_mode: "provider_backed_chat",
                  planner_provider_backend: "openai",
                  candidate_fixes: ["Adjust branch condition"],
                  impacted_services: ["api"],
                  impacted_symbols: ["handle_issue"],
                  likely_failing_tests: ["tests/test_service.py::test_issue"],
                  rollback_complexity: "low",
                  blast_radius: "low",
                  workspace_evidence_refs: ["bundle_1"],
                  generated_patch_ref: "patch_1",
                  patch_impact_report_ref: "impact_1",
                  token_reduction_metrics: {
                    raw_repo_token_estimate: 3200,
                    evidence_bundle_token_count: 240,
                    reduction_ratio: 13.333,
                  },
                },
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              repository_id: "repo_1",
              snapshot_id: "snap_1",
              created_at: "2026-05-29T12:09:30Z",
              seed_file_paths: ["src/service.py"],
              seed_symbols: ["handle_issue"],
              direct_dependencies: ["src/helpers.py"],
              direct_dependents: ["tests/test_service.py"],
              impacted_files: ["src/service.py", "tests/test_service.py"],
              impacted_symbols: ["handle_issue"],
              graph_nodes: [
                {
                  file_path: "src/service.py",
                  depth: 0,
                  is_seed: true,
                  inbound_count: 1,
                  outbound_count: 2,
                  risk_score: 72.5,
                  contained_symbols: ["handle_issue"],
                  parent_child_symbols: ["handle_issue -> guard_user"],
                },
              ],
              graph_edges: [
                {
                  source_file: "tests/test_service.py",
                  target_file: "src/service.py",
                  edge_type: "imports",
                },
              ],
              top_change_risk_files: [
                {
                  file_path: "src/service.py",
                  depth: 0,
                  relationship: "seed",
                  risk_score: 72.5,
                  top_symbol: "handle_issue",
                },
              ],
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              run_id: "feedface-feed-face-feed-facefeed0001",
              status: "completed",
              engine_version: "mojo-1.0.0",
              recommended_action: "apply_patch",
              confidence: 0.91,
              rationale: "Patch simulation satisfied policy thresholds.",
              metrics: {
                expected_value: 88.5,
                median: 90.0,
                std_deviation: 5.2,
                variance: 27.04,
                probability_of_loss: 0.08,
                var_95: 7.0,
                cvar_95: 8.5,
              },
              percentiles: {
                p5: 72.0,
                p25: 84.0,
                p50: 90.0,
                p75: 94.0,
                p95: 98.0,
              },
              scenarios_run: 5000,
              execution_ms: 84,
              metadata: {
                mode: "expert",
                seed: 42,
                billing_units: 3,
                engine_version: "mojo-1.0.0",
              },
              validated_inputs: {
                repository_id: "repo_1",
                snapshot_id: "snap_1",
                decision_plan_id: "plan_1",
                simulation_id: "simulation_1",
              },
              score_breakdown: {
                repository_risk_score: 0.21,
                apply_gate: {
                  passed: true,
                  policy_snapshot_id: "policy_1",
                  min_confidence: 0.7,
                  risk_floor: 12,
                  var_95: 7,
                },
                patch_impact: {
                  changed_files: ["src/service.py"],
                  blast_radius: "low",
                  rollback_complexity: "low",
                  dependency_fanout: 1,
                  api_break_candidates: [],
                },
              },
              decision_plan: {
                recommended_action: "Apply repository patch",
                confidence: 0.91,
                expected_value: 88.5,
                risk: {
                  p5: 72.0,
                  p95: 98.0,
                  probability_of_loss: 0.08,
                  var_95: 7.0,
                },
                options: [],
                rationale: "Patch simulation satisfied policy thresholds.",
                repository_analysis: {
                  root_cause: "Incorrect branch condition in service handler.",
                  planner_model_id: "repo-fix-model",
                  planner_execution_mode: "provider_backed_chat",
                  planner_provider_backend: "openai",
                  candidate_fixes: ["Adjust branch condition"],
                  impacted_services: ["api"],
                  impacted_symbols: ["handle_issue"],
                  likely_failing_tests: ["tests/test_service.py::test_issue"],
                  rollback_complexity: "low",
                  blast_radius: "low",
                  workspace_evidence_refs: ["bundle_1"],
                  generated_patch_ref: "patch_1",
                  patch_impact_report_ref: "impact_1",
                  token_reduction_metrics: {
                    raw_repo_token_estimate: 3200,
                    evidence_bundle_token_count: 240,
                    reduction_ratio: 13.333,
                  },
                },
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              repository_id: "repo_1",
              snapshot_id: "snap_1",
              decision_plan_id: "plan_1",
              simulation_id: "simulation_1",
              mode: "patch_only",
              applied: false,
              created_at: "2026-05-29T12:11:00Z",
              patch: "diff --git a/src/service.py b/src/service.py\n",
              apply_gate: {
                passed: true,
                policy_snapshot_id: "policy_1",
              },
              validation_summary: {
                patch_files: ["src/service.py"],
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

      const capabilities = await client.getRepositoryIntelligenceCapabilities();
      const snapshot = await client.createRepositorySnapshot("repo_1", {
        ref: "main",
        include_patterns: ["src/**/*.py"],
        max_files: 500,
      });
      const snapshotDetail = await client.getRepositorySnapshot("repo_1", "snap_1");
      const triage = await client.triageRepository("repo_1", {
        snapshot_id: "snap_1",
        signals: {
          issue_text: "Regression in service handler",
          diagnostics: [{ path: "src/service.py", line: 12, message: "condition is inverted" }],
          failing_tests: ["tests/test_service.py::test_issue"],
        },
        max_evidence_items: 8,
        token_budget: 1200,
      });
      const decisionPlan = await client.createRepositoryDecisionPlan("repo_1", {
        snapshot_id: "snap_1",
        workspace_evidence_bundle_ref: "bundle_1",
        model: "gpt-5.1",
      });
      const graph = await client.queryRepositoryGraph("repo_1", {
        snapshot_id: "snap_1",
        file_path: "src/service.py",
        direction: "both",
      });
      const simulation = await client.simulateRepository("repo_1", {
        snapshot_id: "snap_1",
        decision_plan_id: "plan_1",
        runs: 5000,
        seed: 42,
      });
      const applied = await client.applyRepository("repo_1", {
        snapshot_id: "snap_1",
        decision_plan_id: "plan_1",
        simulation_id: "simulation_1",
        mode: "patch_only",
      });

      expect(capabilities.supported_languages).toEqual(["python", "typescript", "coq"]);
      expect(capabilities.support_progress.progress_label).toBe("3 / 180");
      expect(snapshot.snapshot_id).toBe("snap_1");
      expect(snapshotDetail.status).toBe("existing");
      expect(triage.workspace_evidence_bundle_ref).toBe("bundle_1");
      expect(decisionPlan.decision_plan.repository_analysis?.patch_impact_report_ref).toBe(
        "impact_1",
      );
      expect(decisionPlan.decision_plan.repository_analysis?.planner_model_id).toBe(
        "repo-fix-model",
      );
      expect(graph.top_change_risk_files[0]?.top_symbol).toBe("handle_issue");
      expect(graph.graph_edges[0]?.edge_type).toBe("imports");
      expect(simulation.decision_plan?.repository_analysis?.root_cause).toContain("branch");
      expect(simulation.decision_plan?.repository_analysis?.planner_provider_backend).toBe(
        "openai",
      );
      expect(simulation.score_breakdown).toMatchObject({
        apply_gate: { passed: true },
        patch_impact: { changed_files: ["src/service.py"] },
      });
      expect(applied.applied).toBe(false);
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        "https://example.test/v1/repositories/capabilities",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        2,
        "https://example.test/v1/repositories/repo_1/snapshots",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            ref: "main",
            include_patterns: ["src/**/*.py"],
            max_files: 500,
          }),
        }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        3,
        "https://example.test/v1/repositories/repo_1/snapshots/snap_1",
        expect.objectContaining({ method: "GET" }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        4,
        "https://example.test/v1/repositories/repo_1/triage",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            snapshot_id: "snap_1",
            signals: {
              issue_text: "Regression in service handler",
              diagnostics: [{ path: "src/service.py", line: 12, message: "condition is inverted" }],
              failing_tests: ["tests/test_service.py::test_issue"],
            },
            max_evidence_items: 8,
            token_budget: 1200,
          }),
        }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        5,
        "https://example.test/v1/repositories/repo_1/decision-plans",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            snapshot_id: "snap_1",
            workspace_evidence_bundle_ref: "bundle_1",
            model: "gpt-5.1",
          }),
        }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        6,
        "https://example.test/v1/repositories/repo_1/graph-query",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            snapshot_id: "snap_1",
            file_path: "src/service.py",
            direction: "both",
          }),
        }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        7,
        "https://example.test/v1/repositories/repo_1/simulate",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            snapshot_id: "snap_1",
            decision_plan_id: "plan_1",
            runs: 5000,
            seed: 42,
          }),
        }),
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        8,
        "https://example.test/v1/repositories/repo_1/apply",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            snapshot_id: "snap_1",
            decision_plan_id: "plan_1",
            simulation_id: "simulation_1",
            mode: "patch_only",
          }),
        }),
      );
    });
});
