// Shared helpers (part a) for runtime.test.ts sub-modules.
// Extracted from runtime.test.ts during modularization.
import { createSign, generateKeyPairSync } from "node:crypto";
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
  MCP_LEGACY_SSE_ENDPOINT,
  MCP_PROTOCOL_VERSION,
  MCP_TRANSPORT,
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
  writeSqliteFixture,
} from "./_runtime_test_helpers.js";

export const SHIPPING_BENCHMARK_DISCOVERY_RULE: RuntimeBenchmarkDiscoveryRule =
  "Only the 22-module, 209-function LLM rollout is treated as the shipping runtime contract.";

export const NON_SHIPPING_RULE: RuntimeNonShippingRule =
  "The broader Mojo inventory remains a benchmark and discovery lane only; modules are not advertised on the runtime surface unless listed in this manifest.";

export const DECISION_WORKFLOW_BENCHMARK_EVIDENCE = [
  "build/repository_intelligence_benchmark.json",
  "benchmarks/repository_intelligence_benchmark.py",
  "tests/test_repository_intelligence_benchmark.py",
];

export function makeDiscoveredSourceInventory(): Record<string, unknown>[] {
  return [
    {
      import_path: "bpe_tokenizer",
      public_function_count: 2,
    },
    {
      import_path: "embeddings",
      public_function_count: 2,
    },
  ];
}

export function makeBenchmarkDiscoveryLanePayload(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    discovered_source_modules: 2,
    discovered_public_functions: 4,
    discovered_source_inventory: makeDiscoveredSourceInventory(),
    shipping_manifest_modules: 1,
    shipping_manifest_functions: 2,
    non_shipping_rule: NON_SHIPPING_RULE,
    ...overrides,
  };
}

export function makeKernelPromotionCriteriaPayload(): Record<string, unknown> {
  return {
    required_manifest_fields: [
      "capability_id",
      "owner",
      "contract_boundary",
      "promotion_status",
      "rollback_flag",
    ],
    required_proof_reference_fields: [
      "benchmark_report_ref",
      "parity_report_ref",
      "schema_compat_report_ref",
      "isolation_proof_ref",
      "replay_proof_ref",
    ],
    deterministic_test_corpus_rule:
      "Shipping kernels must pass a fixed-seed deterministic corpus with stable outputs across repeated runs.",
    python_parity_rule:
      "Shipping kernels must publish Python or reference parity evidence on the same corpus with exact-match outputs or declared tolerances.",
    schema_compatibility_rule:
      "Shipping kernels must prove Arrow and Parquet schema compatibility for declared input, output, checkpoint, and telemetry artifacts.",
    minimum_primary_metric_improvement_pct: 15,
    maximum_adjacent_metric_regression_pct: 5,
    benchmark_exception_rule:
      "A shipping exception is allowed only when the kernel unblocks a declared hard budget and the exception is documented in the benchmark report.",
    rollback_scope_rule:
      "Every shipping kernel must expose an independently switchable rollback flag at tenant, org, or deployment scope.",
    tenant_isolation_rule:
      "Shipping kernels must prove tenant-scoped ownership for caches, checkpoints, artifacts, and buffers before reuse.",
    replay_compatibility_rule:
      "Shipping kernels must reproduce the same result for the same request hash, manifest version, policy snapshot, schema snapshot, seed, and artifact refs or emit replay_mismatch.",
  };
}

// Synthetic CSV fixtures committed under packages/ts-sdk/test-fixtures/ (the suite runs
// with that package as cwd). Regenerate them with scripts/generate_test_fixtures.py —
// deterministic, obviously-synthetic data; see packages/ts-sdk/test-fixtures/README.md.
// The suite asserts exact row counts, so never hand-edit the CSVs.
export const REAL_MARCH_ORDERS = resolvePath(
  process.cwd(),
  "test-fixtures",
  "synthetic_orders_march_2026.csv",
);

export const REAL_MARCH_FINANCIAL = resolvePath(
  process.cwd(),
  "test-fixtures",
  "synthetic_financial_march_2026.csv",
);

export const REAL_MARCH_EMPTY = resolvePath(
  process.cwd(),
  "test-fixtures",
  "synthetic_store_pause_empty.csv",
);

export const ORIGINAL_ENV = { ...process.env };

export function cloneJsonValue<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

export function makeContractPayload(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    contract_version: CONTRACT_VERSION,
    brand: BRAND,
    api_base_url: DEFAULT_BASE_URL,
    mcp_endpoint: MCP_ENDPOINT,
    mcp_transport: MCP_TRANSPORT,
    mcp_protocol_version: MCP_PROTOCOL_VERSION,
    mcp_legacy_sse_endpoint: MCP_LEGACY_SSE_ENDPOINT,
    mcp_tools_endpoint: MCP_TOOLS_ENDPOINT,
    auth_scheme: AUTH_SCHEME,
    api_key_prefixes: {
      live: API_KEY_PREFIX_LIVE,
      test: API_KEY_PREFIX_TEST,
    },
    compatibility: {
      legacy_headers: [...LEGACY_HEADERS],
      legacy_env_vars: [...LEGACY_ENV_VARS],
      legacy_domains: [...LEGACY_DOMAINS],
      deprecation_window_days: DEPRECATION_WINDOW_DAYS,
    },
    privacy_registry: {
      algenta_owned_hosts: [...ALGENTA_OWNED_HOSTS],
      algenta_owned_suffixes: [...ALGENTA_OWNED_SUFFIXES],
      vendor_telemetry_hosts: [...VENDOR_TELEMETRY_HOSTS],
      private_host_suffixes: [...PRIVATE_HOST_SUFFIXES],
    },
    defaults: {
      read_only_default: READ_ONLY_DEFAULT,
      write_confirmation_required: WRITE_CONFIRMATION_REQUIRED,
      plan_limits: cloneJsonValue(PLAN_LIMITS),
    },
    primary_data_query_contract: cloneJsonValue(PRIMARY_DATA_QUERY_CONTRACT),
    integrations: cloneJsonValue(INTEGRATIONS),
    ...overrides,
  };
}

export function makeRuntimeManifestPayload(): Record<string, unknown> {
  return {
    runtime_version: "2026.05.0",
    mojo_version: "25.4.0",
    llm_core_manifest: "llm-core-v1",
    module_manifest_version: "runtime-manifest-v1",
    generated_at: "2026-05-22T12:00:00Z",
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
    compiled_artifacts: [
      {
        kind: "compiled_mojo_binary",
        path: "mojo_build/bpe_tokenizer",
        sha256: "e".repeat(64),
        size_bytes: 4096,
      },
    ],
    supported_channels: ["python_sdk", "typescript_sdk", "cli", "mcp"],
    validated_auxiliary_channels: ["bundled_worker", "runtime_local"],
    feature_flag_channels: ["http_api_feature_flag"],
    maturity: { bpe_tokenizer: "channel_covered" },
    policy_snapshot: {
      snapshot_id: "policy-v1",
      sha256: "a".repeat(64),
      source: "governance/policies/current.json",
      description: "Signed policy snapshot",
    },
    schema_snapshot: {
      snapshot_id: "schema-v1",
      sha256: "b".repeat(64),
      source: "schemas/runtime/current.json",
      description: "Signed schema snapshot",
    },
    deployment_mode: "local_dev_daemon",
    deployment_modes: {
      current: "local_dev_daemon",
      supported_modes: [
        "saas",
        "vpc",
        "self_hosted",
        "air_gapped",
        "hybrid_provider",
        "local_dev_daemon",
      ],
      rule: "Deployment mode availability is defined by the signed runtime manifest only.",
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
    system_invariants: [
      {
        name: "Manifest Truth",
        statement: "No capability is advertised unless it appears in the signed runtime manifest.",
      },
    ],
    execution_model: {
      state_fields: ["request"],
      allowed_transitions: ["model_call_started"],
      validity_rules: ["schema-valid"],
    },
    external_nondeterminism: {
      sources: ["provider responses"],
      rule: "Every nondeterministic dependency must be captured as a replay artifact reference.",
      required_artifacts: ["provider response record"],
      failure_codes: ["replay_mismatch"],
    },
    artifact_lineage: {
      artifact_flow: ["input"],
      required_node_fields: ["node_id"],
      immutability_rule: "Every lineage node must be hash-addressed.",
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
    typed_failures: [{ code: "provider_timeout", description: "timed out" }],
    threat_model: {
      threat_classes: ["prompt injection"],
      controls: ["tool allowlists"],
      non_negotiable_rules: ["MCP tools are untrusted by default."],
    },
    formal_release_theorem: {
      statement:
        "A release is valid iff every advertised capability is manifest-listed, proof-backed, policy-covered, replay-tested, and deployment-mode validated.",
      required_conditions: [
        "manifest-listed",
        "proof-backed",
        "policy-covered",
        "replay-tested",
        "deployment-mode validated",
      ],
    },
    release_artifact_bundle: { required_artifacts: ["signed runtime manifest"] },
    release_gates: [{ gate: "A", description: "all public APIs contract-tested" }],
    immediate_implementation_sequence: [
      {
        pr: "PR 0",
        focus: "Runtime truth manifest",
        deliverables: ["public runtime manifest route"],
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
  };
}

export function makeRuntimeAdminModulesPayload(): Record<string, unknown> {
  return {
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
  };
}

export function makeRuntimeAdminBenchmarksPayload(): Record<string, unknown> {
  return {
    runtime_version: "2026.05.0",
    llm_core_manifest: "llm-core-v1",
    module_manifest_version: "runtime-manifest-v1",
    benchmark_discovery_lane: makeBenchmarkDiscoveryLanePayload(),
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
    shipping_runtime_function_counts: [2],
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
        function_count: 2,
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
  };
}

export function makeRuntimeReleaseValidationPayload(): Record<string, unknown> {
  return {
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
  };
}

export function runtimeTempDir(): string {
  return mkdtempSync(join(tmpdir(), "algenta-ts-runtime-"));
}

export function base64UrlJson(value: Record<string, unknown>): string {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

/**
 * Simulate a control-plane `/v1/device/register` response: an RS256-signed license, using
 * a fresh ephemeral RSA keypair per call (mirrors {@link issueOfflineLocalLicense}'s approach).
 *
 * Legacy license tokens used a retired symmetric scheme; verification of that scheme lives in
 * the private engine repo and is intentionally not reproduced here. The scheme has been retired
 * everywhere — `parseStoredLicenseToken` now hard-rejects any `alg !== "RS256"` unconditionally —
 * so this helper mints RS256 like the hardened control plane does. Callers must register the
 * returned public key (e.g. via `process.env.ALGENTA_LOCAL_LICENSE_PUBLIC_KEY`) before the SDK
 * will accept the token; {@link seedStoredLicense} does this for the common "write license.jwt
 * to disk" case.
 */
export function issueControlPlaneLicense(
  fixtureKey: string,
  expiresAt = 0,
): { token: string; publicKey: string } {
  const { privateKey, publicKey } = generateKeyPairSync("rsa", {
    modulusLength: 2048,
    privateKeyEncoding: { format: "pem", type: "pkcs8" },
    publicKeyEncoding: { format: "pem", type: "spki" },
  });
  const header = base64UrlJson({ alg: "RS256", typ: "JWT" });
  const issuedAt = Math.floor(Date.now() / 1000);
  const payload = base64UrlJson({
    // Deliberately not named like a credential: callers pass a fixture string (e.g.
    // "de_live_ts_runtime_key"), and only its public 12-char prefix -- the `api_key_prefix`
    // claim the control plane mints and parseStoredLicenseToken reads back -- enters the
    // signed payload. Nothing secret is hashed or signed here.
    api_key_prefix: fixtureKey.slice(0, 12),
    device_id: "ts-device-1",
    plan: "pro",
    device_limit: 5,
    permitted_modules: ["*"],
    issued_at: issuedAt,
    expires_at: expiresAt,
    key_expires_at: expiresAt,
    grace_days: 14,
    iss: "algenta-control-plane",
    sub: "device-license",
  });
  const signer = createSign("RSA-SHA256");
  signer.update(`${header}.${payload}`);
  signer.end();
  const signature = signer.sign(privateKey).toString("base64url");
  return { token: `${header}.${payload}.${signature}`, publicKey };
}

export function issueOfflineLocalLicense(expiresAt = 0): { token: string; publicKey: string } {
  const { privateKey, publicKey } = generateKeyPairSync("rsa", {
    modulusLength: 2048,
    privateKeyEncoding: { format: "pem", type: "pkcs8" },
    publicKeyEncoding: { format: "pem", type: "spki" },
  });
  const header = base64UrlJson({ alg: "RS256", typ: "JWT" });
  const issuedAt = Math.floor(Date.now() / 1000);
  const payload = base64UrlJson({
    api_key_prefix: "offline",
    device_id: "ts-device-offline",
    plan: "enterprise",
    device_limit: 0,
    permitted_modules: ["*"],
    issued_at: issuedAt,
    expires_at: expiresAt,
    key_expires_at: expiresAt,
    grace_days: 14,
    iss: "algenta-offline-license",
    sub: "device-license",
  });
  const signer = createSign("RSA-SHA256");
  signer.update(`${header}.${payload}`);
  signer.end();
  const signature = signer.sign(privateKey).toString("base64url");
  return { token: `${header}.${payload}.${signature}`, publicKey };
}

/**
 * Write an RS256 control-plane license to `<runtimeDir>/license.jwt` AND register its public key
 * (via `ALGENTA_LOCAL_LICENSE_PUBLIC_KEY`) so `parseStoredLicenseToken`/`loadLocalLicense` can
 * verify it. Returns the public key PEM in case a caller wants to assert on it directly.
 */
export function seedStoredLicense(runtimeDir: string, fixtureKey: string, expiresAt = 0): string {
  const { token, publicKey } = issueControlPlaneLicense(fixtureKey, expiresAt);
  writeFileSync(join(runtimeDir, "license.jwt"), token, {
    mode: 0o600,
  });
  process.env.ALGENTA_LOCAL_LICENSE_PUBLIC_KEY = publicKey;
  return publicKey;
}

export function seedTrustedTime(runtimeDir: string, trustedEpoch: number, source = "control-plane-register"): void {
  writeFileSync(
    join(runtimeDir, "trusted_time.json"),
    `${JSON.stringify(
      {
        version: 1,
        trusted_epoch: trustedEpoch,
        source,
      },
      null,
      2,
    )}\n`,
  );
}

export function readLedgerEvents(runtimeDir: string): Array<Record<string, unknown>> {
  return readFileSync(join(runtimeDir, "history.jsonl"), "utf8")
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line) as Record<string, unknown>);
}

export async function hasNodeSqlite(): Promise<boolean> {
  try {
    await import("node:sqlite");
    return true;
  } catch {
    return false;
  }
}
