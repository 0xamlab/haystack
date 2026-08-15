// Tests for Runtime: fails.
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

describe("Runtime — fails", () => {
    it("fails fast for api mode in private profiles when no self-hosted baseUrl is configured", () => {
      process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
      delete process.env.ALGENTA_BASE_URL;
      delete process.env.DE_BASE_URL;
      delete process.env.ALGENTA_API_URL;

      try {
        new Runtime({ mode: "api", apiKey: "de_test_123" });
        throw new Error("expected Runtime to fail closed");
      } catch (error) {
        expect(String(error)).toContain("private profiles cannot target Algenta-owned cloud URLs");
        expect(String(error)).toContain("ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL");
      }
    });

    it("fails fast when control-plane sync targets a blocked destination", () => {
      process.env.ALGENTA_ALLOW_OUTBOUND_NETWORK = "0";
      process.env.ALGENTA_CONTROL_PLANE_URL = "https://control.customer.com";

      expect(() => new Runtime({ apiKey: "de_live_ts_runtime_key" })).toThrowError(
        RuntimeConfigurationError,
      );
      expect(() => new Runtime({ apiKey: "de_live_ts_runtime_key" })).toThrowError(
        /destination_not_allowlisted/,
      );
    });

    it("fails closed for connector surfaces in local mode", async () => {
      const runtime = new Runtime();

      await expect(runtime.listDatasets()).rejects.toMatchObject({
        code: "local_mode_not_supported",
      });
    });

    it("fails closed on an invalid contract payload from an injected api client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getContract: async () => ({
            ...makeContractPayload({
              primary_data_query_contract: {
                api: { contract_endpoint: "/v1/meta/contract" },
              },
            }),
          }),
        } as never,
      });

      await expect(runtime.getContract()).rejects.toMatchObject({
        code: "invalid_contract_payload",
      });
      await expect(runtime.getContract()).rejects.toThrow("invalid payload");
    });

    it("fails closed on an invalid nested contract payload from an injected api client", async () => {
      const payload = makeContractPayload();
      (payload.primary_data_query_contract as Record<string, unknown>).cli = {
        ...cloneJsonValue(PRIMARY_DATA_QUERY_CONTRACT.cli),
        runtime_modules_command: null,
      };
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getContract: async () => payload,
        } as never,
      });

      const contractPromise = runtime.getContract();

      await expect(contractPromise).rejects.toMatchObject({
        code: "invalid_contract_payload",
        details: {
          source_error_code: "invalid_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: expect.stringContaining(
              "primary_data_query_contract.cli.runtime_modules_command",
            ),
          },
        },
      });
      await expect(contractPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path ===
            "primary_data_query_contract.cli.runtime_modules_command" &&
          error.fieldErrors[0]?.path ===
            "primary_data_query_contract.cli.runtime_modules_command",
      );
      await expect(contractPromise).rejects.toThrow("getContract() returned an invalid payload.");
    });

    it("fails closed on invalid runtime proof payloads from an injected api client", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeManifest: async () => ({
            runtime_version: "2026.05.0",
            mojo_version: "25.6.0",
            llm_core_manifest: "llm-core-v1",
            module_manifest_version: "runtime-manifest-v1",
            generated_at: "2026-05-22T00:00:00Z",
            modules: [],
            compiled_artifacts: [],
            supported_channels: ["python_sdk", "typescript_sdk", "cli", "mcp"],
            validated_auxiliary_channels: ["bundled_worker", "runtime_local"],
            feature_flag_channels: ["http_api_feature_flag"],
            maturity: { bpe_tokenizer: "legendary" },
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
              supported_modes: ["saas"],
              rule: "rule",
            },
            shipping_contract: {
              module_count: 1,
              function_count: 2,
              runtime_core_layer: "mojo_llm_runtime_core",
              benchmark_discovery_rule: SHIPPING_BENCHMARK_DISCOVERY_RULE,
            },
            benchmark_discovery_lane: makeBenchmarkDiscoveryLanePayload(),
            advertised_capabilities: {
              runtime_modules: ["bpe_tokenizer"],
              public_endpoints: ["/v1/meta/contract"],
              admin_endpoints: ["/v1/admin/runtime/modules"],
              feature_flag_endpoints: ["/v1/libraries"],
            },
            system_invariants: [{ name: "Manifest Truth", statement: "manifest-listed only" }],
            execution_model: {
              state_fields: ["request"],
              allowed_transitions: ["model_call_started"],
              validity_rules: ["schema-valid"],
            },
            external_nondeterminism: {
              sources: ["provider responses"],
              rule: "rule",
              required_artifacts: ["provider response record"],
              failure_codes: ["replay_mismatch"],
            },
            artifact_lineage: {
              artifact_flow: ["input"],
              required_node_fields: ["node_id"],
              immutability_rule: "rule",
            },
            capability_algebra: {
              required_fields: ["tool_name"],
              enums: {
                side_effect_class: ["read_only"],
                risk_level: ["low"],
                replayability: ["deterministic"],
              },
              rules: ["MCP tools are untrusted by default."],
            },
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
              statement: "theorem",
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
                status: "unknown_status",
                obligations: ["numerical parity"],
                evidence_paths: ["build/proof.json"],
              },
            ],
            modules: [],
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
                  code: "B1",
                  description: "microkernel latency",
                  evidence_paths: ["benchmarks/summary.json"],
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
            quality_gate_benchmark_classes: [],
            quality_gate_slo_budgets: [],
            evaluation_science: {
              dimensions: [],
              methods: [],
              release_blockers: [],
            },
            evaluation_summary: {
              dimension_count: 0,
              method_count: 0,
              release_blocker_count: 0,
              benchmark_class_count: 0,
              slo_budget_count: 0,
              replay_gate_enabled: false,
              tool_call_quality_gate_enabled: false,
              rag_quality_gate_enabled: false,
              decision_quality_gate_enabled: false,
            },
            compiled_artifacts: [],
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
                compiled_engine: "warp_core",
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
            theorem_statement: "theorem",
            valid_release: true,
            conditions: [
              {
                condition: "teleport-validated",
                satisfied: true,
                detail: "detail",
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
        } as never,
      });

      await expect(runtime.getRuntimeManifest()).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: expect.stringContaining("maturity.bpe_tokenizer"),
          },
        },
      });
      await expect(runtime.getRuntimeManifest()).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "maturity.bpe_tokenizer" &&
          error.fieldErrors[0]?.path === "maturity.bpe_tokenizer",
      );
      await expect(runtime.getRuntimeModules()).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: expect.stringContaining("proof_matrix.0.status"),
          },
        },
      });
      await expect(runtime.getRuntimeModules()).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "proof_matrix.0.status" &&
          error.fieldErrors[0]?.path === "proof_matrix.0.status",
      );
      await expect(runtime.getRuntimeBenchmarks()).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: expect.stringContaining("module_benchmarks.0.compiled_engine"),
          },
        },
      });
      await expect(runtime.getRuntimeBenchmarks()).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "module_benchmarks.0.compiled_engine" &&
          error.fieldErrors[0]?.path === "module_benchmarks.0.compiled_engine",
      );
      await expect(runtime.getRuntimeReleaseValidation()).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: expect.stringContaining("conditions.0.condition"),
          },
        },
      });
      await expect(runtime.getRuntimeReleaseValidation()).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === "conditions.0.condition" &&
          error.fieldErrors[0]?.path === "conditions.0.condition",
      );
    });
});
