// Tests for Runtime: delegates_b.
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

describe("Runtime — delegates_b", () => {
    it("delegates connector onboarding and dataset operations in self_hosted mode", async () => {
      const connectPayloads: Array<Record<string, unknown>> = [];
      const fakeClient = {
        createConnector: async (request: Record<string, unknown>) => ({
          id: "conn_1",
          name: request.name,
          connector_type: request.connector_type,
          status: "untested",
          visibility: request.visibility ?? "private",
        }),
        listConnectors: async () => ({
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
          limit: 200,
          pages: 1,
        }),
        getConnector: async (connectorId: string) => ({
          id: connectorId,
          name: "Warehouse Postgres",
          connector_type: "postgres",
          status: "live",
          visibility: "private",
        }),
        updateConnector: async (connectorId: string, request: Record<string, unknown>) => ({
          id: connectorId,
          name: "Warehouse Postgres",
          connector_type: "postgres",
          status: "untested",
          visibility: request.visibility ?? "private",
          description: request.description ?? null,
        }),
        testConnector: async (connectorId: string) => ({
          success: true,
          message: `tested:${connectorId}`,
          status: "live",
        }),
        previewTestConnector: async (request: Record<string, unknown>) => ({
          success: true,
          message: `preview:${request.connector_type}`,
          status: "live",
        }),
        browseConnector: async (connectorId: string) => ({
          connector_type: "postgres",
          items: [{ id: "public.orders", label: "orders" }],
          total: 1,
          message: `browse:${connectorId}`,
          labels: { entity_noun: "table" },
          discovery: { scope_noun: "schema" },
        }),
        previewBrowseConnector: async (request: Record<string, unknown>) => ({
          connector_type: String(request.connector_type),
          items: [{ id: "orders:*", label: "orders:*" }],
          total: 1,
          message: "preview browse",
          labels: { entity_noun: "key" },
          discovery: { scope_noun: "pattern" },
        }),
        connectData: async (request: Record<string, unknown>) => {
          connectPayloads.push(request);
          return {
            status: "ready",
            dataset_id: `ds_${connectPayloads.length}`,
            source_id: `ds_${connectPayloads.length}`,
            dataset_name: request.dataset_name,
            connection_id: request.connection_id ?? "inline_conn",
            connection_type: "database",
            provider: "postgres",
            selection: request.selection ?? null,
            latency_ms: 5,
          };
        },
        listDatasets: async () => ({
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
          limit: 200,
          pages: 1,
        }),
        getDataset: async (datasetId: string) => ({
          dataset: {
            dataset_id: datasetId,
            dataset_name: "warehouse_orders",
            connection_id: "conn_1",
          },
          schema: { fields: ["order_id", "revenue"] },
        }),
        getContract: async () => ({
          ...makeContractPayload(),
        }),
        getRuntimeManifest: async () => ({
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
              benchmark_speedup_x: 101,
              compiled_artifact: "mojo_build/simulate",
              compiled_engine: "mojo",
              max_cold_ms: 12,
              max_warm_ms: 4,
              max_hot_ms: 2,
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
        getRuntimeModules: async () => ({
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
              contract_boundary: "Deterministic Mojo kernel with a bounded manifest-listed surface.",
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
        getRuntimeBenchmarks: async () => ({
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
        getRuntimeReleaseValidation: async () => ({
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
        refreshDataset: async (datasetId: string) => ({
          status: "ready",
          dataset_id: datasetId,
          source_id: datasetId,
          dataset_name: "warehouse_orders",
          schema: { fields: ["order_id", "revenue"] },
        }),
        deleteDataset: async (datasetId: string) => ({
          dataset_id: datasetId,
          status: "deleted",
          connection_deleted: true,
        }),
        deleteConnector: async () => undefined,
      };

      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: fakeClient as never,
      });

      const connector = await runtime.createConnector({
        name: "Warehouse Postgres",
        connectorType: "postgres",
        config: { host: "db.internal", database: "analytics" },
      });
      const connectors = await runtime.listConnectors();
      const connectorDetail = await runtime.getConnector("conn_1");
      const updated = await runtime.updateConnector("conn_1", {
        description: "analytics warehouse",
        visibility: "workspace",
      });
      const tested = await runtime.testConnector("conn_1");
      const previewTest = await runtime.testConnector({ type: "redis", url: "redis://localhost:6379" });
      const browsed = await runtime.browseConnector("conn_1");
      const previewBrowse = await runtime.browseConnector({ type: "redis", url: "redis://localhost:6379" });
      const registration = await runtime.connect(null, {
        connectorId: "conn_1",
        name: "warehouse_orders",
        selection: { schema: "public", table: "orders" },
      });
      const datasets = await runtime.listDatasets();
      const dataset = await runtime.getDataset("ds_1");
      const contract = await runtime.getContract();
      const manifest = await runtime.getRuntimeManifest();
      const manifestBenchmarkClass: RuntimeBenchmarkClassCode = "B1";
      const manifestProviderRoutingClass: RuntimeBenchmarkClassCode = "B8";
      const manifestReplayClass: RuntimeBenchmarkClassCode = "B6";
      const benchmarkClass: RuntimeBenchmarkClassCode = "B8";
      const qualityGateBenchmarkClass: RuntimeBenchmarkClassCode = "B6";
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
      const modules = await runtime.getRuntimeModules();
      const benchmarks = await runtime.getRuntimeBenchmarks();
      const validation = await runtime.getRuntimeReleaseValidation();
      const refreshed = await runtime.refreshDataset("ds_1");
      const deleted = await runtime.deleteDataset("ds_1");
      await runtime.deleteConnector("conn_1");

      expect(connector.id).toBe("conn_1");
      expect(connectors.connectors).toHaveLength(1);
      expect(connectorDetail.id).toBe("conn_1");
      expect(updated.visibility).toBe("workspace");
      expect(tested.message).toBe("tested:conn_1");
      expect(previewTest.message).toBe("preview:redis");
      expect(browsed.items).toHaveLength(1);
      expect(previewBrowse.connector_type).toBe("redis");
      expect(registration.dataset_id).toBe("ds_1");
      expect(registration.name).toBe("warehouse_orders");
      expect(datasets.datasets[0]?.dataset_id).toBe("ds_1");
      expect(dataset.schema.fields).toEqual(["order_id", "revenue"]);
      expect(contract.primary_data_query_contract.api.contract_endpoint).toBe("/v1/meta/contract");
      expectManifestBackedIntegrationsEqual(contract.integrations, INTEGRATIONS);
      expect(manifest.shipping_contract.function_count).toBe(1);
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
      expect(manifest.benchmarking.classes[0]?.code).toBe(manifestBenchmarkClass);
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
      expect(manifest.signature.scope).toBe("control_plane_hmac_v1");
      expect(manifest.advertised_capabilities.runtime_modules[0]).toBe(moduleId);
      expect(manifest.advertised_capabilities.public_endpoints[0]).toBe(publicEndpoint);
      expect(manifest.advertised_capabilities.admin_endpoints[0]).toBe(adminEndpoint);
      expect(manifest.advertised_capabilities.feature_flag_endpoints[0]).toBe(featureFlagEndpoint);
      expect(modules.summary.module_count).toBe(1);
      expect(modules.shipping_contract.benchmark_discovery_rule).toBe(benchmarkDiscoveryRule);
      expect(modules.modules[0]?.layer).toBe("mojo_llm_runtime_core");
      expect(modules.proof_matrix[0]?.evidence_paths[0]).toBe("build/proof.json");
      expect(benchmarks.module_benchmarks[0]?.name).toBe(moduleId);
      expect(benchmarks.benchmark_discovery_lane.non_shipping_rule).toBe(nonShippingRule);
      expect(benchmarks.module_benchmarks[0]?.function_count).toBe(1);
      expect(benchmarks.shipping_runtime_modules[0]).toBe(moduleId);
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
      expect(refreshed.dataset_id).toBe("ds_1");
      expect(deleted.connection_deleted).toBe(true);
      expect(connectPayloads[0]).toEqual({
        dataset_name: "warehouse_orders",
        selection: { schema: "public", table: "orders" },
        connection_id: "conn_1",
      });
    });
});
