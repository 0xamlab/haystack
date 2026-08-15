// Tests for Runtime: delegates_c.
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

describe("Runtime — delegates_c", () => {
    it("delegates repository intelligence helpers in self_hosted mode", async () => {
      const fakeClient = {
        getRepositoryIntelligenceCapabilities: async () => ({
          supported_languages: ["python", "typescript", "coq"],
          support_progress: {
            supported_real_language_count: 3,
            ranked_target_language_count: 180,
            progress_fraction: 3 / 180,
            progress_label: "3 / 180",
          },
        }),
        createRepositorySnapshot: async (repositoryId: string, request: Record<string, unknown>) => ({
          repository_id: repositoryId,
          snapshot_id: "snap_1",
          connector_type: "github_repo",
          ref: request.ref ?? null,
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
        getRepositorySnapshot: async (repositoryId: string, snapshotId: string) => ({
          repository_id: repositoryId,
          snapshot_id: snapshotId,
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
        triageRepository: async (repositoryId: string, request: Record<string, unknown>) => ({
          repository_id: repositoryId,
          snapshot_id: request.snapshot_id,
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
        createRepositoryDecisionPlan: async (repositoryId: string, request: Record<string, unknown>) => ({
          repository_id: repositoryId,
          snapshot_id: request.snapshot_id,
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
            options: [],
            rationale: "Bounded evidence localized the fault.",
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
              workspace_evidence_refs: [String(request.workspace_evidence_bundle_ref)],
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
        queryRepositoryGraph: async (repositoryId: string, request: Record<string, unknown>) => ({
          repository_id: repositoryId,
          snapshot_id: request.snapshot_id,
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
        simulateRepository: async (repositoryId: string, request: Record<string, unknown>) => ({
          run_id: "feedface-feed-face-feed-facefeed0001",
          status: "completed",
          engine_version: "mojo-1.0.0",
          recommended_action: "apply_patch",
          confidence: 0.91,
          rationale: `Patch simulation satisfied policy thresholds for ${repositoryId}.`,
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
          scenarios_run: request.runs ?? 5000,
          execution_ms: 84,
          metadata: {
            mode: "expert",
            seed: request.seed ?? 42,
            billing_units: 3,
            engine_version: "mojo-1.0.0",
          },
          score_breakdown: {
            apply_gate: {
              passed: true,
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
        applyRepository: async (repositoryId: string, request: Record<string, unknown>) => ({
          repository_id: repositoryId,
          snapshot_id: request.snapshot_id,
          decision_plan_id: request.decision_plan_id,
          simulation_id: request.simulation_id,
          mode: request.mode,
          applied: false,
          created_at: "2026-05-29T12:11:00Z",
          patch: "diff --git a/src/service.py b/src/service.py\n",
          apply_gate: {
            passed: true,
          },
          validation_summary: {
            patch_files: ["src/service.py"],
          },
        }),
      };

      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: fakeClient as never,
      });

      const capabilities = await runtime.getRepositoryIntelligenceCapabilities();
      const snapshot = await runtime.createRepositorySnapshot("repo_1", {
        ref: "main",
        include_patterns: ["src/**/*.py"],
        max_files: 500,
      });
      const snapshotDetail = await runtime.getRepositorySnapshot("repo_1", "snap_1");
      const triage = await runtime.triageRepository("repo_1", {
        snapshot_id: "snap_1",
        signals: {
          issue_text: "Regression in service handler",
          diagnostics: [{ path: "src/service.py", line: 12, message: "condition is inverted" }],
        },
        max_evidence_items: 8,
      });
      const decisionPlan = await runtime.createRepositoryDecisionPlan("repo_1", {
        snapshot_id: "snap_1",
        workspace_evidence_bundle_ref: "bundle_1",
        model: "gpt-5.1",
      });
      const graph = await runtime.queryRepositoryGraph("repo_1", {
        snapshot_id: "snap_1",
        file_path: "src/service.py",
        direction: "both",
      });
      const simulation = await runtime.simulateRepository("repo_1", {
        snapshot_id: "snap_1",
        decision_plan_id: "plan_1",
        runs: 5000,
        seed: 42,
      });
      const apply = await runtime.applyRepository("repo_1", {
        snapshot_id: "snap_1",
        decision_plan_id: "plan_1",
        simulation_id: "simulation_1",
        mode: "patch_only",
      });

      expect(capabilities.supported_languages).toEqual(["python", "typescript", "coq"]);
      expect(capabilities.support_progress.progress_label).toBe("3 / 180");
      expect(snapshot.snapshot_id).toBe("snap_1");
      expect(snapshotDetail.status).toBe("existing");
      expect(triage.suspect_files).toEqual(["src/service.py"]);
      expect(decisionPlan.decision_plan.repository_analysis?.patch_impact_report_ref).toBe(
        "impact_1",
      );
      expect(decisionPlan.decision_plan.repository_analysis?.planner_execution_mode).toBe(
        "provider_backed_chat",
      );
      expect(graph.top_change_risk_files[0]?.relationship).toBe("seed");
      expect(graph.graph_nodes[0]?.parent_child_symbols).toEqual(["handle_issue -> guard_user"]);
      expect(simulation.decision_plan?.repository_analysis?.generated_patch_ref).toBe("patch_1");
      expect(simulation.decision_plan?.repository_analysis?.planner_provider_backend).toBe(
        "openai",
      );
      expect(simulation.score_breakdown).toMatchObject({ apply_gate: { passed: true } });
      expect(apply.validation_summary).toMatchObject({ patch_files: ["src/service.py"] });
    });

    it("delegates the full trigger lifecycle surface through the api runtime client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
      });
      vi.spyOn(runtime as object as { requireApiTransport(name: string): void }, "requireApiTransport");
      vi.spyOn(runtime as object as { client(): unknown }, "client").mockReturnValue({
        registerTrigger: async () => ({
          trigger_id: "trigger_123",
          org_id: "org_123",
          name: "Revenue alert",
          status: "active",
          condition: {
            source_id: "src_orders",
            metric_hint: "revenue",
            threshold: 200000,
            direction: "above",
            aggregation: "sum",
          },
          auto_execute: true,
          created_at: "2026-05-24T12:00:00Z",
        }),
        listTriggers: async () => ({
          triggers: [
            {
              trigger_id: "trigger_123",
              org_id: "org_123",
              name: "Revenue alert",
              status: "paused",
              condition: {
                source_id: "src_orders",
                metric_hint: "revenue",
                threshold: 200000,
                direction: "above",
                aggregation: "sum",
              },
              auto_execute: true,
              created_at: "2026-05-24T12:00:00Z",
            },
          ],
          count: 1,
          total: 1,
          page: 2,
          limit: 10,
          pages: 1,
        }),
        fireTrigger: async () => ({
          trigger_id: "trigger_123",
          condition_met: true,
          fired: true,
          simulation_run_id: "run_123",
          recommended_action: "proceed",
          expected_value: 123000,
          confidence: 0.82,
          fired_at: "2026-05-24T12:05:00Z",
          execution_status: "queued",
          message: "Trigger fired.",
        }),
        pauseTrigger: async () => ({ trigger_id: "trigger_123", status: "paused" }),
        deleteTrigger: async () => ({ trigger_id: "trigger_123", deleted: true }),
      } as never);

      const created = await runtime.registerTrigger({
        name: "Revenue alert",
        condition: {
          source_id: "src_orders",
          metric_hint: "revenue",
          threshold: 200000,
          direction: "above",
          aggregation: "sum",
        },
        simulation_template: { mode: "auto" },
        webhook_url: "https://example.test/hook",
        execution_webhook_url: "https://example.test/execute",
        auto_execute: true,
        description: "Watch for monthly revenue spikes.",
      });
      const listed = await runtime.listTriggers({ status: "paused", page: 2, limit: 10 });
      const fired = await runtime.fireTrigger("trigger_123", { force: true });
      const paused = await runtime.pauseTrigger("trigger_123", { paused: true });
      const deleted = await runtime.deleteTrigger("trigger_123");

      expect(created.trigger_id).toBe("trigger_123");
      expect(listed.total).toBe(1);
      expect(listed.triggers[0]?.status).toBe("paused");
      expect(fired.simulation_run_id).toBe("run_123");
      expect(paused.status).toBe("paused");
      expect(deleted.deleted).toBe(true);
    });

    it("delegates structured database descriptors to the injected api client", async () => {
      const cases: Array<{ source: Record<string, unknown>; expectedName: string }> = [
        {
          source: {
            type: "postgres",
            connection_string: "postgresql://analytics:secret@localhost:5432/orders",
            schema: "public",
            table: "orders",
          },
          expectedName: "orders_pg",
        },
        {
          source: {
            type: "mysql",
            connection_string: "mysql://analytics:secret@localhost:3306/orders",
            database: "orders",
            table: "orders",
          },
          expectedName: "orders_mysql",
        },
        {
          source: {
            type: "s3",
            bucket: "algenta-public",
            key: "orders/orders.csv",
            format: "csv",
          },
          expectedName: "orders_s3",
        },
        {
          source: {
            type: "rest",
            base_url: "https://example.com/api",
            path: "/orders",
            method: "GET",
          },
          expectedName: "orders_rest",
        },
      ];
      const captured: Array<{ source: Record<string, unknown>; options: Record<string, unknown> }> = [];
      const fakeClient = {
        registerSource: async (
          source: Record<string, unknown>,
          options: Record<string, unknown>,
        ) => {
          captured.push({ source, options });
          return {
            status: "ready",
            source_id: "src_pg_1",
            dataset_id: "src_pg_1",
            name: String(source.name ?? "source"),
            source_schema: { fields: ["order_id", "revenue"] },
            planner_schema_revision: "schema_pg_1",
            latency_ms: 3.4,
            row_count: 120,
          };
        },
      };

      const runtime = new Runtime({
        mode: "api",
        client: fakeClient as never,
      });

      for (const { source, expectedName } of cases) {
        const registration = await runtime.connect(
          source,
          { name: expectedName, description: `Primary ${expectedName} source` },
        );

        expect(registration.name).toBe(expectedName);
      }

      expect(captured).toEqual(
        cases.map(({ source, expectedName }) => ({
          source:
            source.type === "postgres"
              ? {
                  name: expectedName,
                  connection: {
                    type: "sql",
                    provider: "postgres",
                    connection_string: "postgresql://analytics:secret@localhost:5432/orders",
                    schema: "public",
                    table: "orders",
                    query: "SELECT * FROM public.orders",
                  },
                }
              : source.type === "mysql"
                ? {
                    name: expectedName,
                    connection: {
                      type: "sql",
                      provider: "mysql",
                      connection_string: "mysql://analytics:secret@localhost:3306/orders",
                      table: "orders",
                      query: "SELECT * FROM orders",
                    },
                  }
                : source.type === "s3"
                  ? {
                      name: expectedName,
                      connection: {
                        type: "s3",
                        bucket: "algenta-public",
                        key: "orders/orders.csv",
                        file_type: "csv",
                      },
                    }
                  : {
                      name: expectedName,
                      connection: {
                        type: "rest_api",
                        url: "https://example.com/api/orders",
                        path: "/orders",
                        method: "GET",
                      },
                    },
          options: {
            description: `Primary ${expectedName} source`,
          },
        })),
      );
    });
});
