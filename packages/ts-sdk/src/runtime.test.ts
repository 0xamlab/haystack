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

const SHIPPING_BENCHMARK_DISCOVERY_RULE: RuntimeBenchmarkDiscoveryRule =
  "Only the 22-module, 209-function LLM rollout is treated as the shipping runtime contract.";
const NON_SHIPPING_RULE: RuntimeNonShippingRule =
  "The broader Mojo inventory remains a benchmark and discovery lane only; modules are not advertised on the runtime surface unless listed in this manifest.";
const DECISION_WORKFLOW_BENCHMARK_EVIDENCE = [
  "build/repository_intelligence_benchmark.json",
  "benchmarks/repository_intelligence_benchmark.py",
  "tests/test_repository_intelligence_benchmark.py",
];

function makeDiscoveredSourceInventory(): Record<string, unknown>[] {
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

function makeBenchmarkDiscoveryLanePayload(
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

function makeKernelPromotionCriteriaPayload(): Record<string, unknown> {
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

const REAL_MARCH_ORDERS = resolvePath(
  process.cwd(),
  "..",
  "..",
  "test_files",
  "850a28da-a6f7-4ecc-9e7a-51a9cf7f501b-united_states.csv",
);
const REAL_MARCH_FINANCIAL = resolvePath(
  process.cwd(),
  "..",
  "..",
  "test_files",
  "aaeff3ab-19ac-494e-9e58-e507bd7e3893-united_states.csv",
);
const REAL_MARCH_EMPTY = resolvePath(
  process.cwd(),
  "..",
  "..",
  "test_files",
  "549c63c8-3300-416c-8b45-55fec4c6529a_store_pause_2026-03-01_2026-03-31.csv",
);

const ORIGINAL_ENV = { ...process.env };

function cloneJsonValue<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function makeContractPayload(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    contract_version: CONTRACT_VERSION,
    brand: BRAND,
    api_base_url: DEFAULT_BASE_URL,
    mcp_endpoint: MCP_ENDPOINT,
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

function makeRuntimeManifestPayload(): Record<string, unknown> {
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
        validated_auxiliary_channels: ["daemon_client", "runtime_local"],
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
    validated_auxiliary_channels: ["daemon_client", "runtime_local"],
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

function makeRuntimeAdminModulesPayload(): Record<string, unknown> {
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
        validated_auxiliary_channels: ["daemon_client", "runtime_local"],
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

function makeRuntimeAdminBenchmarksPayload(): Record<string, unknown> {
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

function makeRuntimeReleaseValidationPayload(): Record<string, unknown> {
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

function runtimeTempDir(): string {
  return mkdtempSync(join(tmpdir(), "algenta-ts-runtime-"));
}

function base64UrlJson(value: Record<string, unknown>): string {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

function issueControlPlaneLicense(apiKey: string, expiresAt = 0): string {
  const header = base64UrlJson({ alg: "HS256", typ: "JWT" });
  const issuedAt = Math.floor(Date.now() / 1000);
  const payload = base64UrlJson({
    api_key_prefix: apiKey.slice(0, 12),
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
  const jwtSeed = process.env.ALGENTA_JWT_SECRET ?? "change-me-in-production-use-256-bit-random-value";
  const secret = createHash("sha256")
    .update(`${jwtSeed}:license-signing`)
    .digest("hex");
  const signature = createHmac("sha256", secret).update(`${header}.${payload}`).digest("base64url");
  return `${header}.${payload}.${signature}`;
}

function issueOfflineLocalLicense(expiresAt = 0): { token: string; publicKey: string } {
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

function seedStoredLicense(runtimeDir: string, apiKey: string, expiresAt = 0): void {
  writeFileSync(join(runtimeDir, "license.jwt"), issueControlPlaneLicense(apiKey, expiresAt), {
    mode: 0o600,
  });
}

function seedTrustedTime(runtimeDir: string, trustedEpoch: number, source = "control-plane-register"): void {
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

function seedCredits(runtimeDir: string, remaining: number, total = remaining): void {
  const now = Date.now() / 1000;
  writeFileSync(
    join(runtimeDir, "credits.json"),
    `${JSON.stringify(
      {
        credits_remaining: remaining,
        credits_total: total,
        issued_at: now,
        expires_at: now + 3600,
        billing_period: "2026-04",
        refresh_after: now + 1800,
      },
      null,
      2,
    )}\n`,
  );
}

function readLedgerEvents(runtimeDir: string): Array<Record<string, unknown>> {
  return readFileSync(join(runtimeDir, "history.jsonl"), "utf8")
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line) as Record<string, unknown>);
}

async function hasNodeSqlite(): Promise<boolean> {
  try {
    await import("node:sqlite");
    return true;
  } catch {
    return false;
  }
}

async function writeSqliteFixture(
  path: string,
  rows: Array<Record<string, string | number>>,
  table = "orders",
): Promise<void> {
  const { DatabaseSync } = await import("node:sqlite");
  const database = new DatabaseSync(path);
  try {
    database.exec(`DROP TABLE IF EXISTS "${table}"`);
    database.exec(
      `CREATE TABLE "${table}" ("product_line" TEXT, "revenue" REAL, "region" TEXT)`,
    );
    const statement = database.prepare(
      `INSERT INTO "${table}" ("product_line", "revenue", "region") VALUES (?, ?, ?)`,
    );
    for (const row of rows) {
      statement.run(row.product_line, row.revenue, row.region);
    }
  } finally {
    database.close();
  }
}

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

describe("Runtime", () => {
  it("supports local resolve and query happy path", async () => {
    const runtime = new Runtime();
    await runtime.connect(
      [
        { product_line: "Electronics", revenue: 42_193_221 },
        { product_line: "Apparel", revenue: 28_114_992 },
      ],
      { name: "orders" },
    );

    const plan = await runtime.resolve({
      source_name: "orders",
      metric: "revenue",
      group_by: "product_line",
    });

    expect(plan.resolved_plan?.metric_column).toBe("revenue");
    expect(plan.resolved_plan?.group_column).toBe("product_line");

    const result = await runtime.query(plan);
    expect(result.result_type).toBe("table");
    expect(result.row_count).toBe(2);
    expect(result.plan_hash).toBeTruthy();
  });

  it("applies time and generic filter conditions in local exact execution", async () => {
    const runtime = new Runtime();
    const currentYear = new Date().getUTCFullYear();
    await runtime.connect(
      [
        {
          product_line: "Electronics",
          revenue: 10,
          status: "closed",
          booked_on: `${currentYear}-01-15`,
        },
        {
          product_line: "Electronics",
          revenue: 20,
          status: "open",
          booked_on: `${currentYear}-02-15`,
        },
        {
          product_line: "Apparel",
          revenue: 30,
          status: "closed",
          booked_on: `${currentYear - 1}-03-10`,
        },
      ],
      { name: "orders" },
    );

    const result = await runtime.query({
      source_name: "orders",
      metric_column: "revenue",
      aggregation: "sum",
      schema_revision: (await runtime.resolve({
        source_name: "orders",
        metric: "revenue",
      })).resolved_plan?.schema_revision ?? "missing",
      filter: {
        time_filter: "this_year",
        conditions: [{ dimension_hint: "status", op: "eq", value: "closed" }],
      },
    });

    expect(result.result).toBe(10);
    expect(result.plan.some(step => step.includes("Time filter 'this_year'"))).toBe(true);
    expect(result.plan.some(step => step.includes("Filter 'status eq"))).toBe(true);
  });

  it("verifies local plans", async () => {
    const runtime = new Runtime();
    await runtime.connect([{ product_line: "Electronics", revenue: 10 }], { name: "orders" });
    const plan = await runtime.resolve({
      source_name: "orders",
      metric: "revenue",
      group_by: "product_line",
    });

    const verified = await runtime.verify(plan);
    expect(verified.valid).toBe(true);
    expect(verified.verification_mode).toBe("local");
  });

  it("reports invalid generic filter conditions during local verify", async () => {
    const runtime = new Runtime();
    await runtime.connect([{ product_line: "Electronics", revenue: 10 }], { name: "orders" });
    const plan = await runtime.resolve({
      source_name: "orders",
      metric: "revenue",
    });

    const verified = await runtime.verify({
      ...(plan.resolved_plan ?? {}),
      filter: {
        conditions: [{ dimension_hint: "priority", op: "eq", value: "high" }],
      },
    });

    expect(verified.valid).toBe(false);
    expect(verified.errors).toEqual([
      "Filter dimension_hint 'priority' did not resolve on source 'orders'.",
    ]);
  });

  it("rejects unsupported filter operators during local query", async () => {
    const runtime = new Runtime();
    await runtime.connect([{ product_line: "Electronics", revenue: 10, region: "US" }], { name: "orders" });
    const plan = await runtime.resolve({
      source_name: "orders",
      metric: "revenue",
    });

    await expect(
      runtime.query({
        ...(plan.resolved_plan ?? {}),
        filter: {
          conditions: [{ dimension_hint: "region", op: "contains", value: "US" }],
        },
      }),
    ).rejects.toMatchObject({
      code: "invalid_filter_condition",
      message: "Unsupported filter operator 'contains'.",
    });
  });

  it("rejects invalid scalar and list filter payload shapes during local query", async () => {
    const runtime = new Runtime();
    await runtime.connect([{ product_line: "Electronics", revenue: 10, region: "US" }], { name: "orders" });
    const plan = await runtime.resolve({
      source_name: "orders",
      metric: "revenue",
    });

    await expect(
      runtime.query({
        ...(plan.resolved_plan ?? {}),
        filter: {
          conditions: [{ dimension_hint: "region", op: "in", value: "US" }],
        },
      }),
    ).rejects.toMatchObject({
      code: "invalid_filter_condition",
      message: "filter condition op='in' does not accept value",
    });
  });

  it("rejects schema revision mismatch in local query", async () => {
    const runtime = new Runtime();
    await runtime.connect([{ product_line: "Electronics", revenue: 10 }], { name: "orders" });
    const plan = await runtime.resolve({
      source_name: "orders",
      metric: "revenue",
      group_by: "product_line",
    });

    await expect(
      runtime.query({
        ...(plan.resolved_plan ?? {}),
        schema_revision: "stale-schema",
      }),
    ).rejects.toBeInstanceOf(RuntimeValidationError);
  });

  it("requires API configuration when api mode has no key or client", async () => {
    const runtime = new Runtime({ mode: "api" });
    await expect(runtime.resolve({ source_name: "orders", metric: "revenue" })).rejects.toMatchObject({
      code: "api_key_required",
    });
    await expect(runtime.resolve({ source_name: "orders", metric: "revenue" })).rejects.toThrow(
      "ALGENTA_API_KEY / DE_API_KEY",
    );
  });

  it("requires an explicit baseUrl for self_hosted mode", () => {
    expect(() => new Runtime({ mode: "self_hosted", apiKey: "de_test_123" })).toThrow(
      RuntimeConfigurationError,
    );
  });

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

  it("accepts ALGENTA_API_URL for api mode in private profiles", async () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    process.env.ALGENTA_DISABLE_CLOUD = "1";
    delete process.env.ALGENTA_BASE_URL;
    delete process.env.DE_BASE_URL;
    process.env.ALGENTA_API_URL = "http://localhost:8000";

    const runtime = new Runtime({ mode: "api", apiKey: "de_test_123" });

    expect((runtime as unknown as { baseUrl?: string }).baseUrl).toBe("http://localhost:8000");
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

  it("delegates resolve, verify, query, and connect to the injected api client", async () => {
    let capturedResolve: Record<string, unknown> | null = null;
    let capturedVerify: Record<string, unknown> | null = null;
    let capturedQuery: Record<string, unknown> | null = null;
    const fakeClient = {
      registerSource: async () => ({ status: "ready", source_id: "src_1" }),
      resolve: async (request: Record<string, unknown>) => {
        capturedResolve = request;
        return {
        resolved_plan: {
          source_name: "orders",
          metric_column: "revenue",
          aggregation: "sum",
          schema_revision: "schema-1",
        },
        confidence: 1,
        plan: ["Use orders"],
        explanation: ["Resolved exactly"],
        resolved_column: "revenue",
        resolved_role: "measure",
        resolved_source: "orders",
        candidates: [],
        source_scores: { orders: 1 },
        latency_ms: 1,
        decision_path: "exact_spec",
        plan_hash: "plan-1",
        schema_revision: "schema-1",
        validated: true,
        deterministic_scope: "api",
        confidence_source: "schema_truth",
        clarification_required: false,
        rejection_reason: null,
        request_id: "req_1",
        intent_signature: "intent-1",
        source_set: ["orders"],
        join_path: [],
        planner_mode: "exact_spec",
      };
      },
      verify: async (request: Record<string, unknown>) => {
        capturedVerify = request;
        return {
        valid: true,
        errors: [],
        suggestions: [],
        resolved: { source_name: "orders" },
        latency_ms: 1,
      };
      },
      query: async (request: Record<string, unknown>) => {
        capturedQuery = request;
        return {
        query_id: "query-1",
        result: 42,
        result_type: "scalar",
        confidence: 1,
        plan: ["Use orders"],
        resolved_column: "revenue",
        resolved_role: "measure",
        resolved_source: "orders",
        row_count: 1,
        candidates: [],
        source_scores: { orders: 1 },
        ambiguous: false,
        exact_spec: true,
        explanation: ["Executed exactly"],
        latency_ms: 1,
        decision_path: "exact_spec",
        plan_hash: "plan-1",
        schema_revision: "schema-1",
        validated: true,
        deterministic_scope: "api",
        confidence_source: "schema_truth",
        clarification_required: false,
        rejection_reason: null,
        request_id: "req_2",
        source_set: ["orders"],
        join_path: [],
        planner_mode: "exact_spec",
      };
      },
    };

    const runtime = new Runtime({
      mode: "api",
      client: fakeClient as never,
    });

    const registered = await runtime.connect({ records: [{ revenue: 42, product_line: "Electronics" }] });
    const plan = await runtime.resolve({ source_name: "orders", metric: "revenue" });
    const verified = await runtime.verify(plan);
    const result = await runtime.query(plan);

    expect(registered.source_id).toBe("src_1");
    expect(plan.resolved_plan?.metric_column).toBe("revenue");
    expect(verified.valid).toBe(true);
    expect(result.result).toBe(42);
    expect(capturedResolve).toEqual({
      preferred_source: "orders",
      allow_org_scope: true,
      metric: {
        role: "metric",
        hint: "revenue",
      },
    });
    expect(capturedVerify).toMatchObject({
      resolved_plan: {
        source_name: "orders",
        metric_column: "revenue",
        schema_revision: "schema-1",
      },
    });
    expect(capturedQuery).toMatchObject({
      resolved_plan: {
        source_name: "orders",
        metric_column: "revenue",
        schema_revision: "schema-1",
      },
    });
  });

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
            validated_auxiliary_channels: ["daemon_client", "runtime_local"],
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
        validated_auxiliary_channels: ["daemon_client", "runtime_local"],
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
            validated_auxiliary_channels: ["daemon_client", "runtime_local"],
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

  it("exposes the plan-aligned api helper surface through Runtime(mode='api')", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        listModels: async () => ({
          object: "list",
          data: [
            {
              id: "text.tokenizer",
              object: "model",
              owned_by: "algenta",
              runtime_module: "text.tokenizer",
              description: "Deterministic tokenizer utility model",
              capabilities: ["tokenize", "count_tokens", "chat_completions"],
              supported_endpoints: ["/v1/models", "/v1/tokenize", "/v1/count_tokens"],
              runtime_functions: ["tokenize_text", "count_text_tokens"],
              tokenizer_kind: "wordpiece",
              provider_backend: null,
              routing_targets: [],
              resolved_routing_targets: [],
              chat_routing_targets: [],
              resolved_chat_routing_targets: [],
              embedding_routing_targets: [],
              resolved_embedding_routing_targets: [],
              routing_fallback_policy: null,
              chat_routing_fallback_policy: null,
              embedding_routing_fallback_policy: null,
              routing_fallback_on: [],
              chat_routing_fallback_on: [],
              embedding_routing_fallback_on: [],
              routing_max_attempts: null,
              chat_routing_max_attempts: null,
              embedding_routing_max_attempts: null,
              timeout_seconds: null,
              chat_timeout_seconds: null,
              embedding_timeout_seconds: null,
              required_provider_headers: [],
              chat_required_provider_headers: [],
              embedding_required_provider_headers: [],
              provider_auth_env_vars: [],
              chat_provider_auth_env_vars: [],
              embedding_provider_auth_env_vars: [],
              provider_auth_configured: false,
              chat_provider_auth_configured: false,
              embedding_provider_auth_configured: false,
              bridge_cache_root: "/tmp/algenta-hf-cache",
              bridge_auth_env_vars: ["HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"],
              bridge_auth_configured: true,
              bridge_tokenizer_backends: ["tiktoken", "sentencepiece"],
              bridge_artifact_backends: ["safetensors", "huggingface_hub"],
              available: true,
            },
          ],
        }),
        resolveArtifactBridge: async () => ({
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
        tokenize: async () => ({
          object: "tokenization",
          model: "text.tokenizer",
          input: "alpha beta",
          tokens: ["alpha", "beta"],
          token_count: 2,
        }),
        countTokens: async () => ({
          object: "token_count",
          model: "text.tokenizer",
          input: "alpha beta",
          token_count: 2,
        }),
        chatCompletions: async () => ({
          id: "chatcmpl_123",
          object: "chat.completion",
          created: 1,
          model: "text.tokenizer",
          provider_backend: null,
          provider_model_id: null,
          provider_attempts: [],
          choices: [
            {
              index: 0,
              message: { role: "assistant", content: "Deterministic utility response." },
              finish_reason: "stop",
            },
          ],
          usage: { prompt_tokens: 2, completion_tokens: 3, total_tokens: 5 },
        }),
        streamChatCompletions: async function* () {
          yield {
            id: "chatcmpl_stream_123",
            object: "chat.completion.chunk",
            model: "text.tokenizer",
            provider_backend: null,
            provider_model_id: null,
            provider_attempts: [],
            choices: [{ index: 0, delta: { role: "assistant" }, finish_reason: null }],
          };
          yield {
            id: "chatcmpl_stream_123",
            object: "chat.completion.chunk",
            model: "text.tokenizer",
            provider_backend: null,
            provider_model_id: null,
            provider_attempts: [],
            choices: [{ index: 0, delta: { content: "Deterministic utility response." }, finish_reason: "stop" }],
          };
        },
        responses: async () => ({
          id: "resp_123",
          object: "response",
          created_at: 1,
          status: "completed",
          model: "text.tokenizer",
          provider_backend: null,
          provider_model_id: null,
          provider_attempts: [],
          output: [
            {
              id: "resp_123_item_0",
              object: "response.output",
              index: 0,
              provider_backend: null,
              provider_model_id: null,
              provider_attempts: [],
              content: [
                {
                  type: "tokenization",
                  text: "alpha beta",
                  tokens: ["alpha", "beta"],
                  token_count: 2,
                  embedding: null,
                },
              ],
            },
          ],
          usage: { prompt_tokens: 2, total_tokens: 2 },
        }),
        streamResponses: async function* () {
          yield {
            type: "response.created",
            response: {
              id: "resp_123",
              object: "response",
              status: "in_progress",
              model: "text.tokenizer",
              provider_backend: null,
              provider_model_id: null,
              provider_attempts: [],
            },
          };
          yield {
            type: "response.completed",
            response: {
              id: "resp_123",
              object: "response",
              status: "completed",
              model: "text.tokenizer",
              provider_backend: null,
              provider_model_id: null,
              provider_attempts: [],
              usage: { prompt_tokens: 2, total_tokens: 2 },
            },
          };
        },
        embeddings: async () => ({
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
        embeddingSimilarity: async () => ({
          object: "embedding_similarity",
          model: "embeddings.cosine_similarity",
          similarity_metric: "cosine",
          score: 0.94,
          dimension: 3,
        }),
        rerank: async () => ({
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
        planDecision: async () => ({
          recommended_action: "Expand sales coverage",
          confidence: 0.82,
          expected_value: 128000,
          risk: {
            p5: -15000,
            p95: 240000,
            probability_of_loss: 0.18,
            var_95: -15000,
          },
          options: [
            {
              name: "Expand sales coverage",
              rank: 1,
              expected_value: 128000,
              risk: {
                p5: -15000,
                p95: 240000,
                probability_of_loss: 0.18,
                var_95: -15000,
              },
              score: 0.82,
            },
          ],
          rationale: "Projected revenue upside outweighs downside risk.",
          integrity: {
            request_hash: "a".repeat(64),
            result_hash: "b".repeat(64),
          },
          calibration: "6 outcomes | bias=-2.0% | hit_rate=83%",
        }),
        productDecision: async () => ({
          decision_id: "decision_product_123",
          action: "proceed",
          confidence: 0.82,
          reasoning: "Expected value remains attractive within risk tolerance.",
          why: ["Positive expected value", "Downside bounded", "Risk acceptable"],
          expected_outcome: 125000,
          downside_risk: 81000,
          upside_potential: 189000,
          probability_of_loss: 0.14,
          scenarios_evaluated: 10000,
          latency_ms: 41.2,
        }),
        productAgentRun: async () => ({
          run_id: "agent_product_123",
          status: "completed",
          result: { summary: "done" },
          steps: [
            {
              step: 1,
              action: "search",
              tool: "search",
              result: "Found 3 documents",
              status: "completed",
            },
          ],
          tools_used: ["search", "simulate"],
          latency_ms: 88.4,
        }),
        productOptimize: async () => ({
          optimization_id: "opt_123",
          status: "completed",
          optimal_values: { price: 119 },
          objective_value: 183000,
          improvement_vs_midpoint: 14.6,
          constraints_satisfied: true,
          iterations_run: 1200,
          latency_ms: 63,
        }),
        productRetrieve: async () => ({
          retrieval_id: "ret_123",
          query: "launch checklist",
          results: [
            {
              rank: 1,
              document_id: "doc_1",
              content: "Launch checklist for product release.",
              relevance_score: 0.93,
              snippet: "Launch checklist",
            },
          ],
          total_searched: 4,
          latency_ms: 27.5,
        }),
        productForecast: async () => ({
          forecast_id: "forecast_123",
          metric: "monthly_revenue",
          baseline: 125000,
          forecast_mean: 149000,
          total_change_pct: 19.2,
          periods: [
            {
              period: 1,
              forecast: 129000,
              lower_bound: 118000,
              upper_bound: 141000,
              trend: "up",
            },
          ],
          scenarios_evaluated: 5000,
          latency_ms: 35.8,
        }),
        logDecision: async () => ({
          id: "decision_123",
          org_id: "org_123",
          run_id: "run_123",
          context: "Launch planning",
          chosen_action: "expand",
          options_considered: ["expand", "hold"],
          expected_value: 128000,
          confidence: 0.82,
          rationale: "Projected upside outweighs downside.",
          risk_p5: -15000,
          risk_p95: 240000,
          risk_pol: 0.18,
          request_hash: "a".repeat(64),
          result_hash: "b".repeat(64),
          policy_snapshot_id: "policy-v1",
          schema_snapshot_id: "schema-v1",
          manifest_version: "runtime-manifest-v1",
          actual_outcome: null,
          outcome_delta: null,
          outcome_notes: null,
          outcome_recorded_at: null,
          executed_at: null,
          execution_status: null,
          execution_webhook_url: null,
          execution_response_code: null,
          created_at: "2026-05-24T12:00:00Z",
          updated_at: "2026-05-24T12:00:00Z",
        }),
        listDecisions: async () => ({
          decisions: [
            {
              id: "decision_123",
              org_id: "org_123",
              run_id: "run_123",
              context: "Launch planning",
              chosen_action: "expand",
              options_considered: ["expand", "hold"],
              expected_value: 128000,
              confidence: 0.82,
              rationale: "Projected upside outweighs downside.",
              risk_p5: -15000,
              risk_p95: 240000,
              risk_pol: 0.18,
              request_hash: "a".repeat(64),
              result_hash: "b".repeat(64),
              policy_snapshot_id: "policy-v1",
              schema_snapshot_id: "schema-v1",
              manifest_version: "runtime-manifest-v1",
              actual_outcome: null,
              outcome_delta: null,
              outcome_notes: null,
              outcome_recorded_at: null,
              executed_at: null,
              execution_status: null,
              execution_webhook_url: null,
              execution_response_code: null,
              created_at: "2026-05-24T12:00:00Z",
              updated_at: "2026-05-24T12:00:00Z",
            },
          ],
          total: 1,
          page: 1,
          limit: 20,
          pages: 1,
          page_size: 20,
        }),
        getDecision: async () => ({
          id: "decision_123",
          org_id: "org_123",
          run_id: "run_123",
          context: "Launch planning",
          chosen_action: "expand",
          options_considered: ["expand", "hold"],
          expected_value: 128000,
          confidence: 0.82,
          rationale: "Projected upside outweighs downside.",
          risk_p5: -15000,
          risk_p95: 240000,
          risk_pol: 0.18,
          request_hash: "a".repeat(64),
          result_hash: "b".repeat(64),
          policy_snapshot_id: "policy-v1",
          schema_snapshot_id: "schema-v1",
          manifest_version: "runtime-manifest-v1",
          actual_outcome: null,
          outcome_delta: null,
          outcome_notes: null,
          outcome_recorded_at: null,
          executed_at: null,
          execution_status: null,
          execution_webhook_url: null,
          execution_response_code: null,
          created_at: "2026-05-24T12:00:00Z",
          updated_at: "2026-05-24T12:00:00Z",
        }),
        recordOutcome: async () => ({
          id: "decision_123",
          org_id: "org_123",
          run_id: "run_123",
          context: "Launch planning",
          chosen_action: "expand",
          options_considered: ["expand", "hold"],
          expected_value: 128000,
          confidence: 0.82,
          rationale: "Projected upside outweighs downside.",
          risk_p5: -15000,
          risk_p95: 240000,
          risk_pol: 0.18,
          request_hash: "a".repeat(64),
          result_hash: "b".repeat(64),
          policy_snapshot_id: "policy-v1",
          schema_snapshot_id: "schema-v1",
          manifest_version: "runtime-manifest-v1",
          actual_outcome: 141000,
          outcome_delta: 13000,
          outcome_notes: "Launch outperformed baseline",
          outcome_recorded_at: "2026-05-24T12:30:00Z",
          executed_at: null,
          execution_status: null,
          execution_webhook_url: null,
          execution_response_code: null,
          created_at: "2026-05-24T12:00:00Z",
          updated_at: "2026-05-24T12:30:00Z",
        }),
        executeDecision: async () => ({
          decision_id: "decision_123",
          webhook_url: "https://hooks.example.test/decision",
          execution_status: "delivered",
          response_code: 202,
          executed_at: "2026-05-24T12:05:00Z",
          policy_snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
          schema_snapshot_id: "schema-v1",
          manifest_version: "runtime-manifest-v1",
          payload_summary: {
            chosen_action: "expand",
            expected_value: 128000,
            confidence: 0.82,
          },
          safety_overridden: false,
        }),
        deleteDecision: async () => ({}),
        createAgentRun: async () => ({
          run_id: "run_agent_123",
          status: "requires_approval",
          task: "Search the knowledge base",
          output_format: "markdown",
          approval_mode: "manual",
          pending_action: "approve",
          selected_tool: "search",
          result: { summary: "Found 3 relevant documents" },
          tools_available: ["search", "summarize"],
          tools_used: ["search"],
          steps: [
            { action: "Planning execution", status: "completed", step: 1 },
            { action: "Routing to search", tool: "search", result: "Found 3 relevant documents", status: "completed", step: 2 },
          ],
          request_hash: "a".repeat(64),
          decision_hash: "b".repeat(64),
          policy_snapshot_id: "policy-v1",
          schema_snapshot_id: "schema-v1",
          manifest_version: "runtime-manifest-v1",
          replayable: true,
          artifact_refs: ["art_1"],
          latest_checkpoint_id: "cp_2",
          checkpoint_count: 2,
          created_at: "2026-05-24T12:00:00Z",
          updated_at: "2026-05-24T12:00:03Z",
          latency_ms: 21.5,
        }),
        getAgentRun: async () => ({
          run_id: "run_agent_123",
          status: "requires_approval",
          task: "Search the knowledge base",
          output_format: "markdown",
          approval_mode: "manual",
          pending_action: "approve",
          selected_tool: "search",
          result: { summary: "Found 3 relevant documents" },
          tools_available: ["search", "summarize"],
          tools_used: ["search"],
          steps: [
            { action: "Planning execution", status: "completed", step: 1 },
            { action: "Routing to search", tool: "search", result: "Found 3 relevant documents", status: "completed", step: 2 },
          ],
          request_hash: "a".repeat(64),
          decision_hash: "b".repeat(64),
          policy_snapshot_id: "policy-v1",
          schema_snapshot_id: "schema-v1",
          manifest_version: "runtime-manifest-v1",
          replayable: true,
          artifact_refs: ["art_1"],
          latest_checkpoint_id: "cp_2",
          checkpoint_count: 2,
          created_at: "2026-05-24T12:00:00Z",
          updated_at: "2026-05-24T12:00:03Z",
          latency_ms: 21.5,
        }),
        listAgentRuns: async () => ({
          object: "list",
          data: [
            {
              run_id: "run_agent_123",
              status: "requires_approval",
              task: "Search the knowledge base",
              output_format: "markdown",
              approval_mode: "manual",
              pending_action: "approve",
              selected_tool: "search",
              result: { summary: "Found 3 relevant documents" },
              tools_available: ["search", "summarize"],
              tools_used: ["search"],
              steps: [
                { action: "Planning execution", status: "completed", step: 1 },
                { action: "Routing to search", tool: "search", result: "Found 3 relevant documents", status: "completed", step: 2 },
              ],
              request_hash: "a".repeat(64),
              decision_hash: "b".repeat(64),
              policy_snapshot_id: "policy-v1",
              schema_snapshot_id: "schema-v1",
              manifest_version: "runtime-manifest-v1",
              replayable: true,
              artifact_refs: ["art_1"],
              latest_checkpoint_id: "cp_2",
              checkpoint_count: 2,
              created_at: "2026-05-24T12:00:00Z",
              updated_at: "2026-05-24T12:00:03Z",
              latency_ms: 21.5,
            },
          ],
          total: 1,
          page: 1,
          limit: 25,
          pages: 1,
        }),
        getAgentRunEvents: async () => ({
          object: "list",
          run_id: "run_agent_123",
          data: [
            {
              event_id: "evt_1",
              event_type: "run_created",
              status: "paused",
              message: "Run created and awaiting approval.",
              created_at: "2026-05-24T12:00:00Z",
              details: { pending_action: "approve" },
            },
          ],
          total_events: 1,
        }),
        streamAgentRunEvents: async function* () {
          yield {
            type: "agent.run.event",
            event: {
              event_id: "evt_1",
              event_type: "run_created",
              status: "paused",
              message: "Run created and awaiting approval.",
              created_at: "2026-05-24T12:00:00Z",
              details: { pending_action: "approve" },
            },
          };
          yield { type: "agent.run.completed", status: "completed", run_id: "run_agent_123" };
        },
        listAgentRunCheckpoints: async () => ({
          object: "list",
          run_id: "run_agent_123",
          data: [
            {
              checkpoint_id: "cp_1",
              checkpoint_index: 1,
              run_id: "run_agent_123",
              parent_checkpoint_id: null,
              status: "requires_approval",
              event_start_index: 0,
              event_end_index: 2,
              request_hash: "a".repeat(64),
              decision_hash: "b".repeat(64),
              content_hash: "c".repeat(64),
              policy_snapshot_id: "policy-v1",
              schema_snapshot_id: "schema-v1",
              manifest_version: "runtime-manifest-v1",
              artifact_refs: ["art_1"],
              created_at: "2026-05-24T12:00:02Z",
            },
            {
              checkpoint_id: "cp_2",
              checkpoint_index: 2,
              run_id: "run_agent_123",
              parent_checkpoint_id: "cp_1",
              status: "completed",
              event_start_index: 3,
              event_end_index: 5,
              request_hash: "a".repeat(64),
              decision_hash: "b".repeat(64),
              content_hash: "d".repeat(64),
              policy_snapshot_id: "policy-v1",
              schema_snapshot_id: "schema-v1",
              manifest_version: "runtime-manifest-v1",
              artifact_refs: ["art_1", "art_2"],
              created_at: "2026-05-24T12:00:03Z",
            },
          ],
          total_checkpoints: 2,
        }),
        queryAgentRunCheckpoints: async () => ({
          object: "list",
          data: [
            {
              checkpoint_id: "cp_2",
              checkpoint_index: 2,
              run_id: "run_agent_123",
              parent_checkpoint_id: "cp_1",
              status: "completed",
              event_start_index: 3,
              event_end_index: 5,
              request_hash: "a".repeat(64),
              decision_hash: "b".repeat(64),
              content_hash: "d".repeat(64),
              policy_snapshot_id: "policy-v1",
              schema_snapshot_id: "schema-v1",
              manifest_version: "runtime-manifest-v1",
              artifact_refs: ["art_1", "art_2"],
              created_at: "2026-05-24T12:00:03Z",
              run_status: "completed",
            },
          ],
          total: 1,
          page: 1,
          limit: 25,
          pages: 1,
        }),
        listAgentRunMissionEvents: async () => ({
          object: "list",
          run_id: "run_agent_123",
          data: [
            {
              mission_id: "run_agent_123",
              thread_id: "run_agent_123",
              tenant_scope: "org_test",
              workspace_scope: "run_agent_123",
              event_index: 0,
              superstep: 1,
              node_name: "agent_run_service",
              event_type: "run_created",
              event_message: "Agent run created.",
              details_json: '{"approval_mode":"manual","start_paused":false}',
              event_ts: "2026-05-24T12:00:00Z",
              request_hash: "a".repeat(64),
              policy_snapshot_id: "policy-v1",
              schema_snapshot_id: "schema-v1",
              manifest_version: "runtime-manifest-v1",
              checkpoint_id: null,
              artifact_refs: ["evt_1"],
              failure_code: null,
              latency_ms: null,
              cost_usd_micros: null,
            },
          ],
          total_events: 1,
        }),
        queryAgentRunMissionEvents: async () => ({
          object: "list",
          data: [
            {
              mission_id: "run_agent_123",
              thread_id: "run_agent_123",
              tenant_scope: "org_test",
              workspace_scope: "run_agent_123",
              event_index: 0,
              superstep: 1,
              node_name: "agent_run_service",
              event_type: "run_created",
              event_message: "Agent run created.",
              details_json: '{"approval_mode":"manual","start_paused":false}',
              event_ts: "2026-05-24T12:00:00Z",
              request_hash: "a".repeat(64),
              policy_snapshot_id: "policy-v1",
              schema_snapshot_id: "schema-v1",
              manifest_version: "runtime-manifest-v1",
              checkpoint_id: null,
              artifact_refs: ["evt_1"],
              failure_code: null,
              latency_ms: null,
              cost_usd_micros: null,
              run_id: "run_agent_123",
              run_status: "completed",
            },
          ],
          total: 1,
          page: 1,
          limit: 25,
          pages: 1,
        }),
        listAgentRunTelemetry: async () => ({
          object: "list",
          run_id: "run_agent_123",
          data: [
            {
              batch_id: "telemetry_1",
              telemetry_kind: "agent_run_completion",
              module_name: "agent_run_service",
              tenant_scope: "org_test",
              request_hash: "a".repeat(64),
              started_at: "2026-05-24T12:00:00Z",
              ended_at: "2026-05-24T12:00:03Z",
              success_count: 1,
              failure_count: 0,
              latency_ms_p95: 21.5,
              cost_usd_micros: 0,
            },
          ],
          total_batches: 1,
        }),
        queryAgentRunTelemetry: async () => ({
          object: "list",
          data: [
            {
              batch_id: "telemetry_1",
              telemetry_kind: "agent_run_completion",
              module_name: "agent_run_service",
              tenant_scope: "org_test",
              request_hash: "a".repeat(64),
              started_at: "2026-05-24T12:00:00Z",
              ended_at: "2026-05-24T12:00:03Z",
              success_count: 1,
              failure_count: 0,
              latency_ms_p95: 21.5,
              cost_usd_micros: 0,
              run_id: "run_agent_123",
              run_status: "completed",
            },
          ],
          total: 1,
          page: 1,
          limit: 25,
          pages: 1,
        }),
        replayAgentRun: async () => ({
          object: "agent_run_replay",
          run_id: "run_agent_123",
          checkpoint_id: "cp_2",
          replay_status: "matched",
          compared_event_count: 3,
          checkpoint_count: 2,
          request_hash: "a".repeat(64),
          decision_hash: "b".repeat(64),
          content_hash: "d".repeat(64),
          policy_snapshot_id: "policy-v1",
          schema_snapshot_id: "schema-v1",
          manifest_version: "runtime-manifest-v1",
          failure_code: null,
          created_at: "2026-05-24T12:00:04Z",
        }),
        forkAgentRun: async () => ({
          run_id: "run_agent_124",
          status: "paused",
          task: "Search the knowledge base",
          output_format: "markdown",
          approval_mode: "manual",
          pending_action: "resume",
          selected_tool: "search",
          result: null,
          tools_available: ["search", "summarize"],
          tools_used: [],
          steps: [],
          request_hash: "a".repeat(64),
          decision_hash: null,
          policy_snapshot_id: "policy-v1",
          schema_snapshot_id: "schema-v1",
          manifest_version: "runtime-manifest-v1",
          replayable: true,
          artifact_refs: ["art_3"],
          latest_checkpoint_id: "cp_3",
          checkpoint_count: 1,
          source_run_id: "run_agent_123",
          source_checkpoint_id: "cp_1",
          created_at: "2026-05-24T12:00:05Z",
          updated_at: "2026-05-24T12:00:05Z",
          latency_ms: null,
        }),
        resumeAgentRun: async () => ({
          run_id: "run_agent_123",
          status: "requires_approval",
          task: "Search the knowledge base",
          output_format: "markdown",
          approval_mode: "manual",
          pending_action: "approve",
          selected_tool: "search",
          result: { summary: "Found 3 relevant documents" },
          tools_available: ["search", "summarize"],
          tools_used: ["search"],
          steps: [],
          created_at: "2026-05-24T12:00:00Z",
          updated_at: "2026-05-24T12:00:03Z",
          latency_ms: 21.5,
        }),
        cancelAgentRun: async () => ({
          run_id: "run_agent_123",
          status: "cancelled",
          task: "Search the knowledge base",
          output_format: "markdown",
          approval_mode: "manual",
          pending_action: null,
          selected_tool: "search",
          result: { summary: "Cancelled" },
          tools_available: ["search", "summarize"],
          tools_used: ["search"],
          steps: [],
          created_at: "2026-05-24T12:00:00Z",
          updated_at: "2026-05-24T12:00:03Z",
          latency_ms: 21.5,
        }),
        approveAgentRun: async () => ({
          run_id: "run_agent_123",
          status: "completed",
          task: "Search the knowledge base",
          output_format: "markdown",
          approval_mode: "manual",
          pending_action: null,
          selected_tool: "search",
          result: { summary: "Found 3 relevant documents" },
          tools_available: ["search", "summarize"],
          tools_used: ["search"],
          steps: [],
          created_at: "2026-05-24T12:00:00Z",
          updated_at: "2026-05-24T12:00:03Z",
          latency_ms: 21.5,
        }),
        recommend: async () => ({
          recommended_action: "expand",
          confidence: 0.76,
          rationale: "Expand has the strongest expected value after risk adjustment.",
          action_results: [
            {
              name: "expand",
              rank: 1,
              envelope: {
                run_id: "run_decision_123",
                status: "completed",
                engine_version: "2026.05.0",
                recommended_action: "expand",
                confidence: 0.82,
                rationale: "Projected revenue upside outweighs downside risk.",
                metrics: {
                  expected_value: 128000,
                  median: 121000,
                  std_deviation: 18000,
                  variance: 324000000,
                  probability_of_loss: 0.18,
                  var_95: -15000,
                  cvar_95: -28000,
                },
                percentiles: {
                  p5: -15000,
                  p25: 64000,
                  p50: 121000,
                  p75: 176000,
                  p95: 240000,
                },
                scenarios_run: 250,
                execution_ms: 18.4,
                metadata: {
                  mode: "expert",
                  seed: 42,
                  billing_units: 1,
                  engine_version: "2026.05.0",
                },
              },
              expected_value: 140000,
              probability_of_loss: 0.15,
              score: 0.76,
            },
          ],
          total_actions: 1,
          decision_plan: {
            recommended_action: "expand",
            confidence: 0.76,
            expected_value: 140000,
            risk: {
              p5: -12000,
              p95: 240000,
              probability_of_loss: 0.15,
              var_95: -12000,
            },
            options: [],
            rationale: "Expand has the strongest expected value after risk adjustment.",
          },
        }),
        score: async () => ({
          envelope: {
            run_id: "run_decision_123",
            status: "completed",
            engine_version: "2026.05.0",
            recommended_action: "expand",
            confidence: 0.82,
            rationale: "Projected revenue upside outweighs downside risk.",
            metrics: {
              expected_value: 128000,
              median: 121000,
              std_deviation: 18000,
              variance: 324000000,
              probability_of_loss: 0.18,
              var_95: -15000,
              cvar_95: -28000,
            },
            percentiles: {
              p5: -15000,
              p25: 64000,
              p50: 121000,
              p75: 176000,
              p95: 240000,
            },
            scenarios_run: 250,
            execution_ms: 18.4,
            metadata: {
              mode: "expert",
              seed: 42,
              billing_units: 1,
              engine_version: "2026.05.0",
            },
          },
          score: 0.73,
          score_breakdown: { expected_value: 0.61, downside_risk: 0.12 },
        }),
        batch: async () => ({
          total: 2,
          succeeded: 2,
          failed: 0,
          results: [
            {
              index: 0,
              success: true,
              envelope: {
                run_id: "run_batch_1",
                status: "completed",
                engine_version: "2026.05.0",
                recommended_action: "base",
                confidence: 0.71,
                rationale: "Base scenario is stable.",
                metrics: {
                  expected_value: 100,
                  median: 100,
                  std_deviation: 0,
                  variance: 0,
                  probability_of_loss: 0,
                },
                percentiles: { p5: 100, p25: 100, p50: 100, p75: 100, p95: 100 },
                scenarios_run: 100,
                execution_ms: 5,
                metadata: { mode: "expert", seed: 1, billing_units: 1, engine_version: "2026.05.0" },
              },
            },
            {
              index: 1,
              success: true,
              envelope: {
                run_id: "run_batch_2",
                status: "completed",
                engine_version: "2026.05.0",
                recommended_action: "stretch",
                confidence: 0.74,
                rationale: "Stretch scenario has higher upside.",
                metrics: {
                  expected_value: 120,
                  median: 120,
                  std_deviation: 0,
                  variance: 0,
                  probability_of_loss: 0,
                },
                percentiles: { p5: 120, p25: 120, p50: 120, p75: 120, p95: 120 },
                scenarios_run: 100,
                execution_ms: 5,
                metadata: { mode: "expert", seed: 1, billing_units: 1, engine_version: "2026.05.0" },
              },
            },
          ],
        }),
        compare: async () => ({
          winner: "stretch",
          margin: {
            expected_value_delta: 20,
            probability_of_loss_delta: -0.04,
            score_delta: 0.09,
          },
          scenarios: [
            {
              name: "base",
              envelope: {
                run_id: "run_compare_base",
                status: "completed",
                engine_version: "2026.05.0",
                recommended_action: "base",
                confidence: 0.7,
                rationale: "Base scenario.",
                metrics: {
                  expected_value: 100,
                  median: 100,
                  std_deviation: 0,
                  variance: 0,
                  probability_of_loss: 0,
                },
                percentiles: { p5: 100, p25: 100, p50: 100, p75: 100, p95: 100 },
                scenarios_run: 150,
                execution_ms: 6,
                metadata: { mode: "expert", seed: 1, billing_units: 1, engine_version: "2026.05.0" },
              },
              delta_vs_best: {
                expected_value_delta: -20,
                probability_of_loss_delta: 0.04,
                score_delta: -0.09,
              },
            },
            {
              name: "stretch",
              envelope: {
                run_id: "run_compare_stretch",
                status: "completed",
                engine_version: "2026.05.0",
                recommended_action: "stretch",
                confidence: 0.79,
                rationale: "Stretch scenario.",
                metrics: {
                  expected_value: 120,
                  median: 120,
                  std_deviation: 0,
                  variance: 0,
                  probability_of_loss: 0,
                },
                percentiles: { p5: 120, p25: 120, p50: 120, p75: 120, p95: 120 },
                scenarios_run: 150,
                execution_ms: 6,
                metadata: { mode: "expert", seed: 1, billing_units: 1, engine_version: "2026.05.0" },
              },
              delta_vs_best: {
                expected_value_delta: 0,
                probability_of_loss_delta: 0,
                score_delta: 0,
              },
            },
          ],
        }),
        listDeploymentRegions: async () => ({
          providers: [
            {
              id: "algenta_shared",
              name: "Algenta Managed",
              description: "Multi-tenant shared pool.",
              icon: "🌐",
              regions: [
                {
                  id: "algenta-shared",
                  name: "Algenta Shared",
                  label: "Algenta Shared",
                  location: "Global",
                },
              ],
            },
          ],
        }),
        getDeployment: async () => ({
          deployment_id: "dep_123",
          org_id: "org_123",
          provider: "algenta_shared",
          region: "algenta-shared",
          status: "requested",
          endpoint_url: "https://example.test/runtime",
          cost_usd_month: 12.5,
          billable_cost_usd_month: 15.0,
          billing_markup_pct: 20.0,
          created_at: "2026-05-24T12:00:00Z",
          provisioned_at: null,
          error_message: null,
        }),
        createDeployment: async () => ({
          deployment_id: "dep_123",
          org_id: "org_123",
          provider: "algenta_shared",
          region: "algenta-shared",
          status: "requested",
          endpoint_url: "https://example.test/runtime",
          cost_usd_month: 12.5,
          billable_cost_usd_month: 15.0,
          billing_markup_pct: 20.0,
          created_at: "2026-05-24T12:00:00Z",
          provisioned_at: null,
          error_message: null,
        }),
        getDeploymentCost: async () => ({
          deployment_id: "dep_123",
          provider: "algenta_shared",
          region: "algenta-shared",
          year: 2026,
          month: 5,
          cost_usd_month: 12.5,
          billable_cost_usd_month: 15.0,
          billing_markup_pct: 20.0,
          last_updated: "2026-05-24T12:30:00Z",
        }),
        deleteDeployment: async () => ({
          status: "deprovisioning",
          deployment_id: "dep_123",
        }),
        me: async () => ({
          org_id: "org_123",
          email: "owner@example.com",
          organization: "Algenta Labs",
          plan: "enterprise",
        }),
        usage: async () => ({
          org_id: "org_123",
          billing_period: "2026-05",
          simulations_run: 120,
          api_calls: 340,
          quota_limit: 1000,
          quota_used_pct: 12,
        }),
        limits: async () => ({
          plan: "enterprise",
          simulations_per_month: "unlimited",
          rate_limit_per_minute: 10000,
          connectors: 64,
          jobs_enabled: true,
        }),
        distributions: async () => ({
          page: 1,
          limit: 50,
          total: 1,
          pages: 1,
          distributions: [
            {
              name: "normal",
              description: "Normal distribution.",
              required_params: ["mean", "std"],
              optional_params: [],
              example: { mean: 100, std: 12 },
            },
          ],
        }),
        templates: async () => ({
          page: 1,
          limit: 50,
          total: 1,
          pages: 1,
          templates: [
            {
              id: "product-launch",
              name: "Product Launch Decision",
              category: "business",
              description: "Compare launch scenarios.",
              example_request: { mode: "auto" },
            },
          ],
        }),
        getBillingInfo: async () => ({
          plan: "enterprise",
          stripe_customer_id: "cus_123",
          subscription_status: "active",
          current_period_end: "2026-06-30T00:00:00Z",
        }),
        createBillingCheckout: async () => ({
          url: "https://billing.example/checkout/session_123",
        }),
        createBillingPortal: async () => ({
          url: "https://billing.example/portal/session_123",
        }),
        refreshCredits: async () => ({
          credits_granted: 10000,
          credits_issued_this_month: 25000,
          monthly_limit: 500000,
          monthly_remaining: 475000,
          billing_period: "2026-05",
          expires_at: 1716547200,
          refresh_after: 1716545040,
          server_time: 1716460800,
        }),
        listApiKeys: async () => ([
          {
            id: "key_1",
            label: "Mission Runtime Key",
            key_prefix: "de_live_abcd",
            device_limit: 2,
            status: "active",
            created_at: "2026-05-24T12:00:00Z",
            expires_at: null,
          },
        ]),
        createApiKey: async () => ({
          id: "key_2",
          label: "Mission Rotation Key",
          key_prefix: "de_live_wxyz",
          device_limit: 3,
          raw_key: "de_live_wxyz_secret_value",
          created_at: "2026-05-24T12:00:00Z",
          expires_at: null,
        }),
        revokeApiKey: async () => ({}),
      } as never,
    });

    const models = await runtime.listModels();
    const artifact = await runtime.resolveArtifactBridge({
      repo_id: "org/model",
      filename: "model.safetensors",
      revision: "main",
    });
    const tokenized = await runtime.tokenize({ input: "alpha beta" });
    const counted = await runtime.countTokens({ input: "alpha beta" });
    const chat = await runtime.chatCompletions({
      messages: [{ role: "user", content: "Summarize" }],
    });
    const chatStream = [];
    for await (const chunk of runtime.streamChatCompletions({
      messages: [{ role: "user", content: "Summarize" }],
    })) {
      chatStream.push(chunk);
    }
    const response = await runtime.responses({ input: ["alpha beta"], model: "text.hash_embedding_v1", dimensions: 3 });
    const responseStream = [];
    for await (const item of runtime.streamResponses({ input: "alpha beta" })) {
      responseStream.push(item);
    }
    const embeddings = await runtime.embeddings({ input: "alpha beta", dimensions: 3 });
    const similarity = await runtime.embeddingSimilarity({ left: [0.1, 0.2, 0.3], right: [0.1, 0.2, 0.3] });
    const reranked = await runtime.rerank({
      query_embedding: [0.1, 0.2, 0.3],
      documents: [{ id: "doc-1", embedding: [0.1, 0.2, 0.3], text: "Top document" }],
      top_n: 1,
    });
    const plan = await runtime.planDecision({
      mode: "auto",
      scenario: {
        variables: { revenue: { low: 1, high: 2 } },
        objective: "maximize_score",
      },
    });
    const productDecision = await runtime.productDecision({
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
    const productAgentRun = await runtime.productAgentRun({
      task: "Search launch preparation docs",
      context: { area: "operations" },
      tools: ["search", "simulate"],
      max_steps: 4,
      output_format: "markdown",
    });
    const productOptimize = await runtime.productOptimize({
      objective: "maximize_margin",
      variables: [{ name: "price", min: 95, max: 140, step: 1 }],
      constraints: [{ expression: "price >= 100", required: true }],
      iterations: 1200,
      engine: "product",
    });
    const productRetrieve = await runtime.productRetrieve({
      query: "launch checklist",
      documents: [
        { id: "doc_1", content: "Launch checklist for product release." },
        { id: "doc_2", content: "Retention analysis for pilot customers." },
      ],
      top_k: 2,
      rerank: true,
    });
    const productForecast = await runtime.productForecast({
      metric: "monthly_revenue",
      history: [118000, 121000, 125000, 128500],
      horizon: 3,
      seasonality: true,
      confidence_level: 0.9,
    });
    const loggedDecision = await runtime.logDecision({
      chosen_action: "expand",
      context: "Launch planning",
      expected_value: 128000,
    });
    const listedDecisions = await runtime.listDecisions({
      page: 1,
      limit: 20,
      with_outcome_only: true,
    });
    const fetchedDecision = await runtime.getDecision("decision_123");
    const recordedOutcome = await runtime.recordOutcome("decision_123", {
      actual_outcome: 141000,
      outcome_notes: "Launch outperformed baseline",
    });
    const executionReceipt = await runtime.executeDecision("decision_123", {
      webhook_url: "https://hooks.example.test/decision",
    });
    const deletedDecision = await runtime.deleteDecision("decision_123");
    const created = await runtime.createAgentRun({
      task: "Search the knowledge base",
      approval_mode: "manual",
      output_format: "markdown",
    });
    const listed = await runtime.listAgentRuns({ status: "requires_approval" });
    const fetched = await runtime.getAgentRun("run_agent_123");
    const events = await runtime.getAgentRunEvents("run_agent_123", { limit: 25 });
    const eventStream = [];
    for await (const item of runtime.streamAgentRunEvents("run_agent_123", { limit: 25 })) {
      eventStream.push(item);
    }
    const resumed = await runtime.resumeAgentRun("run_agent_123");
    const cancelled = await runtime.cancelAgentRun("run_agent_123");
    const approved = await runtime.approveAgentRun("run_agent_123");
    const checkpoints = await runtime.listAgentRunCheckpoints("run_agent_123");
    const checkpointQuery = await runtime.queryAgentRunCheckpoints({
      status: "completed",
      request_hash: "a".repeat(64),
      policy_snapshot_id: "policy-v1",
      schema_snapshot_id: "schema-v1",
      run_id: "run_agent_123",
      checkpoint_id: "cp_2",
    });
    const missionEvents = await runtime.listAgentRunMissionEvents("run_agent_123", { limit: 25 });
    const missionEventQuery = await runtime.queryAgentRunMissionEvents({
      status: "completed",
      request_hash: "a".repeat(64),
      policy_snapshot_id: "policy-v1",
      schema_snapshot_id: "schema-v1",
      run_id: "run_agent_123",
      event_type: "run_created",
    });
    const telemetry = await runtime.listAgentRunTelemetry("run_agent_123", { limit: 25 });
    const telemetryQuery = await runtime.queryAgentRunTelemetry({
      status: "completed",
      request_hash: "a".repeat(64),
      policy_snapshot_id: "policy-v1",
      schema_snapshot_id: "schema-v1",
      run_id: "run_agent_123",
      telemetry_kind: "agent_run_completion",
      module_name: "agent_run_service",
    });
    const replay = await runtime.replayAgentRun("run_agent_123", { checkpoint_id: "cp_2" });
    const forked = await runtime.forkAgentRun("run_agent_123", { checkpoint_id: "cp_1" });
    const recommendation = await runtime.recommend([
      {
        name: "expand",
        request: {
          mode: "expert",
          runs: 250,
          simulation: {
            variables: [{ name: "outcome", distribution: "fixed", params: { value: 140000 } }],
            objective_function: "outcome",
          },
        },
      },
    ]);
    const score = await runtime.score(
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
    const batch = await runtime.batch([
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
    const compare = await runtime.compare([
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
    const deploymentRegions = await runtime.listDeploymentRegions();
    const deployment = await runtime.getDeployment();
    const createdDeployment = await runtime.createDeployment();
    const deploymentCost = await runtime.getDeploymentCost("dep_123");
    const deletedDeployment = await runtime.deleteDeployment("dep_123");
    const me = await runtime.me();
    const usage = await runtime.usage();
    const limits = await runtime.limits();
    const distributions = await runtime.distributions();
    const templates = await runtime.templates();
    const billingInfo = await runtime.getBillingInfo();
    const checkout = await runtime.createBillingCheckout({ plan: "developer" });
    const portal = await runtime.createBillingPortal();
    const refreshed = await runtime.refreshCredits({
      device_id: "device_runtime_123",
      billing_period: "2026-05",
      credits_used: 17,
    });
    const listedApiKeys = await runtime.listApiKeys();
    const createdApiKey = await runtime.createApiKey({
      label: "Mission Rotation Key",
      device_limit: 3,
    });
    const revokedApiKey = await runtime.revokeApiKey("key_2");

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
    expect(tokenized.token_count).toBe(2);
    expect(counted.token_count).toBe(2);
    expect(chat.choices[0]?.message.content).toBe("Deterministic utility response.");
    expect(chat.provider_backend).toBeNull();
    expect(chat.provider_model_id).toBeNull();
    expect(chat.provider_attempts).toEqual([]);
    expect(chatStream).toHaveLength(2);
    expect(chatStream[0]?.provider_backend).toBeNull();
    expect(chatStream[0]?.provider_model_id).toBeNull();
    expect(chatStream[0]?.provider_attempts).toEqual([]);
    expect(response.output[0]?.content[0]?.type).toBe("tokenization");
    expect(response.provider_backend).toBeNull();
    expect(response.provider_model_id).toBeNull();
    expect(response.provider_attempts).toEqual([]);
    expect(response.output[0]?.provider_backend).toBeNull();
    expect(response.output[0]?.provider_model_id).toBeNull();
    expect(response.output[0]?.provider_attempts).toEqual([]);
    expect(responseStream[0]).toMatchObject({ type: "response.created" });
    expect(responseStream[0]?.response?.provider_backend).toBeNull();
    expect(responseStream[0]?.response?.provider_model_id).toBeNull();
    expect(responseStream[0]?.response?.provider_attempts).toEqual([]);
    expect(embeddings.dimensions).toBe(3);
    expect(embeddings.provider_backend).toBeNull();
    expect(embeddings.provider_model_id).toBeNull();
    expect(embeddings.provider_attempts).toEqual([]);
    expect(similarity.score).toBe(0.94);
    expect(reranked.data[0]?.rank).toBe(1);
    expect(plan.recommended_action).toBe("Expand sales coverage");
    expect(productDecision.action).toBe("proceed");
    expect(productAgentRun.steps[0]?.tool).toBe("search");
    expect(productOptimize.optimal_values.price).toBe(119);
    expect(productRetrieve.results[0]?.document_id).toBe("doc_1");
    expect(productForecast.periods[0]?.trend).toBe("up");
    expect(loggedDecision.chosen_action).toBe("expand");
    expect(loggedDecision.policy_snapshot_id).toBe("policy-v1");
    expect(listedDecisions.decisions[0]?.id).toBe("decision_123");
    expect(listedDecisions.decisions[0]?.schema_snapshot_id).toBe("schema-v1");
    expect(fetchedDecision.context).toBe("Launch planning");
    expect(fetchedDecision.manifest_version).toBe("runtime-manifest-v1");
    expect(recordedOutcome.outcome_delta).toBe(13000);
    expect(executionReceipt.execution_status).toBe("delivered");
    expect(executionReceipt.policy_snapshot_id).toBe("execution-policy-v1-r2:abcd1234abcd1234");
    expect(executionReceipt.schema_snapshot_id).toBe("schema-v1");
    expect(executionReceipt.manifest_version).toBe("runtime-manifest-v1");
    expect(deletedDecision).toEqual({});
    expect(created.pending_action).toBe("approve");
    expect(listed.total).toBe(1);
    expect(listed.data[0]?.run_id).toBe("run_agent_123");
    expect(created.latest_checkpoint_id).toBe("cp_2");
    expect(fetched.run_id).toBe("run_agent_123");
    expect(events.total_events).toBe(1);
    expect(eventStream.at(-1)).toMatchObject({ type: "agent.run.completed" });
    expect(resumed.status).toBe("requires_approval");
    expect(cancelled.status).toBe("cancelled");
    expect(approved.status).toBe("completed");
    expect(checkpoints.total_checkpoints).toBe(2);
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
    expect(forked.source_checkpoint_id).toBe("cp_1");
    expect(recommendation.recommended_action).toBe("expand");
    expect(score.score).toBe(0.73);
    expect(batch.total).toBe(2);
    expect(compare.winner).toBe("stretch");
    expect(deploymentRegions.providers[0]?.regions[0]?.id).toBe("algenta-shared");
    expect(deploymentRegions.providers[0]?.regions[0]?.name).toBe("Algenta Shared");
    expect(deployment?.deployment_id).toBe("dep_123");
    expect(createdDeployment.status).toBe("requested");
    expect(deploymentCost.month).toBe(5);
    expect(deletedDeployment.status).toBe("deprovisioning");
    expect(me.organization).toBe("Algenta Labs");
    expect(usage.billing_period).toBe("2026-05");
    expect(usage.simulations_run).toBe(120);
    expect(limits.plan).toBe("enterprise");
    expect(distributions.distributions[0]?.name).toBe("normal");
    expect(templates.templates[0]?.id).toBe("product-launch");
    expect(limits.connectors).toBe(64);
    expect(billingInfo.stripe_customer_id).toBe("cus_123");
    expect(checkout.url).toContain("/checkout/");
    expect(portal.url).toContain("/portal/");
    expect(refreshed.credits_granted).toBe(10000);
    expect(refreshed.monthly_remaining).toBe(475000);
    expect(listedApiKeys[0]?.label).toBe("Mission Runtime Key");
    expect(createdApiKey.raw_key).toBe("de_live_wxyz_secret_value");
    expect(revokedApiKey).toEqual({});
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

  it("exposes typed control-plane helpers through Runtime(mode='api')", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        listTeamMembers: async () => ({
          members: [
            {
              user_id: "user_123",
              name: "Owner",
              email: "owner@example.com",
              role: "owner",
              status: "active",
              last_active: "2026-05-24T12:00:00Z",
            },
          ],
          total: 1,
          page: 1,
          limit: 50,
          pages: 1,
        }),
        inviteTeamMember: async () => ({
          message: "Invitation sent.",
          invite_id: "invite_123",
        }),
        updateTeamMemberRole: async () => ({
          message: "Role updated.",
          user_id: "user_123",
        }),
        removeTeamMember: async () => ({
          removed: true,
          user_id: "user_123",
        }),
        listDevices: async () => ({
          devices: [
            {
              id: "reg_123",
              device_id: "device_12...",
              platform: "macos",
              platform_version: "15.5",
              sdk_version: "1.0.0",
              status: "active",
              api_key_label: "Primary SDK Key",
              api_key_prefix: "de_live_",
              registered_at: "2026-05-24T11:00:00Z",
              last_heartbeat_at: "2026-05-24T12:00:00Z",
              heartbeat_count: 2,
            },
          ],
          device_count: 1,
          total: 1,
          page: 1,
          limit: 25,
          pages: 1,
          device_limit: 2,
          plan: "enterprise",
        }),
        revokeDevice: async () => ({
          revoked: true,
          registration_id: "reg_123",
        }),
        getAuditLogs: async (options?: {
          actor_email?: string;
          action?: string;
          resource_type?: string;
          result?: string;
          policy_snapshot_id?: string;
          schema_snapshot_id?: string;
          manifest_version?: string;
          request_hash?: string;
        }) => ({
          entries: [
            {
              id: options?.manifest_version ? "audit_456" : "audit_123",
              timestamp: "2026-05-24T12:00:00Z",
              actor_email: "owner@example.com",
              action: "policy_update",
              resource_type: "execution_policy",
              resource_id: "org_123",
              ip_address: "203.0.113.10",
              result: "success",
              metadata: options?.manifest_version
                ? {
                    policy_snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
                    schema_snapshot_id: "schema-v1",
                    manifest_version: options.manifest_version,
                    request_hash: options.request_hash,
                  }
                : {
                    policy_snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
                    schema_revision: "execution-policy-v1",
                  },
            },
          ],
          total: 1,
          page: options?.manifest_version ? 2 : 1,
          limit: options?.manifest_version ? 10 : 25,
          pages: 1,
        }),
        getAuditLogArtifacts: async () => ({
          entries: [
            {
              id: "audit_artifact_1",
              timestamp: "2026-05-24T12:02:00Z",
              actor_email: "owner@example.com",
              action: "policy_update",
              resource_type: "execution_policy",
              resource_id: "org_123",
              ip_address: "203.0.113.10",
              result: "success",
              content_hash: "content_hash_1",
              metadata: {
                policy_snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
                schema_snapshot_id: "schema-v1",
                manifest_version: "runtime-manifest-v1",
                request_hash: "hash_123",
              },
            },
          ],
          total: 1,
          page: 1,
          limit: 5,
          pages: 1,
        }),
        getExecutionPolicy: async () => ({
          org_id: "org_123",
          min_confidence: 0.7,
          risk_floor: 10000,
          require_calibration: true,
          allow_reexecution: false,
          snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
          content_hash: "abcd1234".repeat(8),
          schema_revision: "execution-policy-v1",
          revision: 2,
          previous_snapshot_id: "execution-policy-v1-r1:1111222233334444",
          created_at: "2026-05-24T12:00:00Z",
          updated_at: "2026-05-24T12:00:00Z",
        }),
        listExecutionPolicySnapshots: async () => ({
          org_id: "org_123",
          data: [
            {
              org_id: "org_123",
              min_confidence: 0.7,
              risk_floor: 10000,
              require_calibration: true,
              allow_reexecution: false,
              snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
              content_hash: "abcd1234".repeat(8),
              schema_revision: "execution-policy-v1",
              revision: 2,
              previous_snapshot_id: "execution-policy-v1-r1:1111222233334444",
              created_at: "2026-05-24T12:00:00Z",
              updated_at: "2026-05-24T12:00:00Z",
            },
          ],
          total_snapshots: 1,
        }),
        updateMe: async () => ({
          user: {
            id: "user_123",
            email: "owner@example.com",
            name: "Mission Ops",
            role: "owner",
            email_verified: true,
            created_at: "2026-05-24T12:00:00Z",
          },
          org: {
            id: "org_123",
            name: "Mission Control",
            slug: "mission-control",
            plan: "enterprise",
            status: "active",
            created_at: "2026-05-24T11:00:00Z",
          },
        }),
        getBillingInfo: async () => ({
          plan: "enterprise",
          stripe_customer_id: "cus_123",
          subscription_status: "active",
          current_period_end: "2026-06-30T00:00:00Z",
        }),
        createBillingCheckout: async () => ({
          url: "https://billing.example/checkout/session_123",
        }),
        createBillingPortal: async () => ({
          url: "https://billing.example/portal/session_123",
        }),
        refreshCredits: async () => ({
          credits_granted: 10000,
          credits_issued_this_month: 25000,
          monthly_limit: 500000,
          monthly_remaining: 475000,
          billing_period: "2026-05",
          expires_at: 1716547200,
          refresh_after: 1716545040,
          server_time: 1716460800,
        }),
        ingestMeteringEvents: async () => ({
          accepted: 1,
          billing_period: "2026-05",
        }),
        updateExecutionPolicy: async () => ({
          org_id: "org_123",
          min_confidence: 0.85,
          risk_floor: 10000,
          require_calibration: true,
          allow_reexecution: true,
          snapshot_id: "execution-policy-v1-r3:fedcfedcfedcfedc",
          content_hash: "fedc".repeat(16),
          schema_revision: "execution-policy-v1",
          revision: 3,
          previous_snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
          created_at: "2026-05-24T12:05:00Z",
          updated_at: "2026-05-24T12:05:00Z",
        }),
      } as never,
    });

    const team = await runtime.listTeamMembers({ page: 1, limit: 50 });
    const invited = await runtime.inviteTeamMember({ email: "new@example.com", role: "admin" });
    const roleUpdated = await runtime.updateTeamMemberRole("user_123", "viewer");
    const removed = await runtime.removeTeamMember("user_123");
    const devices = await runtime.listDevices({ page: 1, limit: 25 });
    const revoked = await runtime.revokeDevice("reg_123");
    const logs = await runtime.getAuditLogs();
    const filteredLogs = await runtime.getAuditLogs({
      actor_email: "owner@example.com",
      action: "policy_update",
      resource_type: "execution_policy",
      result: "success",
      policy_snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
      schema_snapshot_id: "schema-v1",
      manifest_version: "runtime-manifest-v1",
      request_hash: "hash_123",
    });
    const artifacts = await runtime.getAuditLogArtifacts({
      actor_email: "owner@example.com",
      action: "policy_update",
      resource_type: "execution_policy",
      result: "success",
      policy_snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
      schema_snapshot_id: "schema-v1",
      manifest_version: "runtime-manifest-v1",
      request_hash: "hash_123",
      content_hash: "content_hash_1",
    });
    const policy = await runtime.getExecutionPolicy();
    const snapshots = await runtime.listExecutionPolicySnapshots();
    const me = await runtime.updateMe({ org_name: "Mission Control" });
    const billingInfo = await runtime.getBillingInfo();
    const checkout = await runtime.createBillingCheckout({ plan: "pro" });
    const portal = await runtime.createBillingPortal();
    const refreshed = await runtime.refreshCredits({
      device_id: "device_runtime_123",
      billing_period: "2026-05",
      credits_used: 17,
    });
    const metering = await runtime.ingestMeteringEvents({
      device_id: "device_runtime_123",
      events: [{ event_type: "query", latency_ms: 8.0, success: true }],
    });
    const updated = await runtime.updateExecutionPolicy({
      min_confidence: 0.85,
      allow_reexecution: true,
    });

    expect(team.members[0]?.email).toBe("owner@example.com");
    expect(team.total).toBe(1);
    expect(invited.invite_id).toBe("invite_123");
    expect(roleUpdated.user_id).toBe("user_123");
    expect(removed).toEqual({ removed: true, user_id: "user_123" });
    expect(devices.device_count).toBe(1);
    expect(devices.devices[0]?.device_id).toBe("device_12...");
    expect(devices.devices[0]?.api_key_prefix).toBe("de_live_");
    expect(revoked).toEqual({ revoked: true, registration_id: "reg_123" });
    expect(logs.entries[0]?.resource_type).toBe("execution_policy");
    expect(logs.entries[0]?.metadata?.["policy_snapshot_id"]).toBe(
      "execution-policy-v1-r2:abcd1234abcd1234",
    );
    expect(filteredLogs.entries[0]?.metadata?.["manifest_version"]).toBe("runtime-manifest-v1");
    expect(artifacts.entries[0]?.content_hash).toBe("content_hash_1");
    expect(policy.min_confidence).toBe(0.7);
    expect(snapshots.total_snapshots).toBe(1);
    expect(me.org.name).toBe("Mission Control");
    expect(billingInfo.plan).toBe("enterprise");
    expect(checkout.url).toContain("/checkout/");
    expect(portal.url).toContain("/portal/");
    expect(refreshed.credits_granted).toBe(10000);
    expect(metering.billing_period).toBe("2026-05");
    expect(updated.allow_reexecution).toBe(true);
  });

  it("exposes typed async job helpers through Runtime(mode='api')", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        submitJob: async () => ({
          job_id: "11111111-1111-1111-1111-111111111111",
          poll_url: "http://localhost:8000/v1/jobs/11111111-1111-1111-1111-111111111111",
          status: "queued",
        }),
        getJob: async () => ({
          job_id: "11111111-1111-1111-1111-111111111111",
          run_id: "22222222-2222-2222-2222-222222222222",
          org_id: "33333333-3333-3333-3333-333333333333",
          status: "queued",
          queue_name: "default",
          retry_count: 0,
          callback_status: "pending",
          created_at: "2026-05-24T12:00:00Z",
          poll_url: "http://localhost:8000/v1/jobs/11111111-1111-1111-1111-111111111111",
        }),
        getJobResult: async () => ({
          summary: "ok",
        }),
        listJobs: async () => ({
          jobs: [
            {
              job_id: "11111111-1111-1111-1111-111111111111",
              run_id: "22222222-2222-2222-2222-222222222222",
              org_id: "33333333-3333-3333-3333-333333333333",
              status: "queued",
              queue_name: "default",
              retry_count: 0,
              callback_status: "pending",
              created_at: "2026-05-24T12:00:00Z",
              poll_url: "http://localhost:8000/v1/jobs/11111111-1111-1111-1111-111111111111",
            },
          ],
          total: 1,
          page: 2,
          limit: 10,
          pages: 1,
        }),
        cancelJob: async () => ({
          job_id: "11111111-1111-1111-1111-111111111111",
          run_id: "22222222-2222-2222-2222-222222222222",
          org_id: "33333333-3333-3333-3333-333333333333",
          status: "cancelled",
          queue_name: "default",
          retry_count: 0,
          callback_status: "pending",
          created_at: "2026-05-24T12:00:00Z",
          completed_at: "2026-05-24T12:01:00Z",
          poll_url: "http://localhost:8000/v1/jobs/11111111-1111-1111-1111-111111111111",
        }),
        testWebhookDelivery: async () => ({
          success: true,
          status_code: 200,
          message: "delivered",
        }),
        pollJob: async () => ({
          summary: "ok",
        }),
      } as never,
    });

    const submitted = await runtime.submitJob({
      mode: "expert",
      runs: 100,
      simulation: {
        variables: [{ name: "outcome", distribution: "fixed", params: { value: 100 } }],
        objective_function: "outcome",
      },
    });
    const status = await runtime.getJob("11111111-1111-1111-1111-111111111111");
    const result = await runtime.getJobResult("11111111-1111-1111-1111-111111111111");
    const listed = await runtime.listJobs({ page: 2, limit: 10, status: "queued" });
    const cancelled = await runtime.cancelJob("11111111-1111-1111-1111-111111111111");
    const webhook = await runtime.testWebhookDelivery("https://example.test/webhook");
    const polled = await runtime.pollJob("11111111-1111-1111-1111-111111111111", {
      timeoutMs: 100,
      pollIntervalMs: 1,
    });

    expect(submitted.job_id).toBe("11111111-1111-1111-1111-111111111111");
    expect(status.status).toBe("queued");
    expect(result.summary).toBe("ok");
    expect(listed.total).toBe(1);
    expect(listed.page).toBe(2);
    expect(listed.jobs[0]?.status).toBe("queued");
    expect(cancelled.status).toBe("cancelled");
    expect(webhook.status_code).toBe(200);
    expect(polled.summary).toBe("ok");
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

  it("normalizes an upstream contract error from the api client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getContract: async () => {
          throw new DecisionEngineError(
            "OpenAPI contract fallback returned an invalid payload: primary_data_query_contract.runtime_sdk.typescript.runtime_class",
            0,
            "invalid_contract_payload",
            {
              error: {
                code: "invalid_contract_payload",
                details: {
                  cause:
                    "primary_data_query_contract.runtime_sdk.typescript.runtime_class",
                },
              },
            },
          );
        },
      } as never,
    });

    const contractPromise = runtime.getContract();

    await expect(contractPromise).rejects.toMatchObject({
      code: "invalid_contract_payload",
      details: {
        source_error_code: "invalid_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "primary_data_query_contract.runtime_sdk.typescript.runtime_class",
        },
      },
    });
    await expect(contractPromise).rejects.toThrow("getContract() returned an invalid payload.");
  });

  it("exposes field-level validation aliases on direct runtime validation errors", () => {
    const error = new RuntimeValidationError(
      "invalid_runtime_contract_payload",
      "invalid signed payload",
      {
        cause: "proof_matrix.0.status",
        validation_errors: [
          {
            path: "proof_matrix.0.status",
            message: "Input should be a valid enum value",
            type: "enum",
          },
        ],
      },
    );

    expect(error.validationErrors).toEqual([
      {
        path: "proof_matrix.0.status",
        message: "Input should be a valid enum value",
        type: "enum",
      },
    ]);
    expect(error.fieldErrors).toEqual(error.validationErrors);
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
          validated_auxiliary_channels: ["daemon_client", "runtime_local"],
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

  it("rejects duplicate runtime manifest release conditions returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeManifest: async () => {
          const manifest = makeRuntimeManifestPayload();
          (manifest.formal_release_theorem.required_conditions as Array<string>).push(
            "manifest-listed",
          );
          return manifest;
        },
      } as never,
    });

    const manifestPromise = runtime.getRuntimeManifest();

    await expect(manifestPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: expect.stringContaining("formal_release_theorem.required_conditions"),
        },
      },
    });
    await expect(manifestPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "formal_release_theorem.required_conditions" &&
        error.fieldErrors[0]?.path === "formal_release_theorem.required_conditions",
    );
  });

  it("rejects runtime manifest artifact kind drift returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeManifest: async () => {
          const manifest = makeRuntimeManifestPayload();
          (manifest.compiled_artifacts as Array<Record<string, unknown>>)[0]!.kind =
            "ghost_bundle";
          return manifest;
        },
      } as never,
    });

    const manifestPromise = runtime.getRuntimeManifest();

    await expect(manifestPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "compiled_artifacts.0.kind",
        },
      },
    });
    await expect(manifestPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "compiled_artifacts.0.kind" &&
        error.fieldErrors[0]?.path === "compiled_artifacts.0.kind",
    );
  });

  it("rejects duplicate runtime manifest module public channels returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeManifest: async () => {
          const manifest = makeRuntimeManifestPayload();
          (
            (manifest.modules as Array<Record<string, unknown>>)[0]!
              .public_supported_channels as Array<string>
          ).push("python_sdk");
          return manifest;
        },
      } as never,
    });

    const manifestPromise = runtime.getRuntimeManifest();

    await expect(manifestPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "modules.0.public_supported_channels",
        },
      },
    });
    await expect(manifestPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "modules.0.public_supported_channels" &&
        error.fieldErrors[0]?.path === "modules.0.public_supported_channels",
    );
  });

  it("rejects duplicate runtime manifest module functions returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeManifest: async () => {
          const manifest = makeRuntimeManifestPayload();
          (
            (manifest.modules as Array<Record<string, unknown>>)[0]!.functions as Array<string>
          ).push(
            ((manifest.modules as Array<Record<string, unknown>>)[0]!
              .functions as Array<string>)[0]!,
          );
          return manifest;
        },
      } as never,
    });

    const manifestPromise = runtime.getRuntimeManifest();

    await expect(manifestPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "modules.0.functions",
        },
      },
    });
    await expect(manifestPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "modules.0.functions" &&
        error.fieldErrors[0]?.path === "modules.0.functions",
    );
  });

  it("rejects invalid runtime manifest kernel promotion status returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeManifest: async () => {
          const manifest = makeRuntimeManifestPayload();
          (manifest.modules as Array<Record<string, unknown>>)[0]!.promotion_status = "graduated";
          return manifest;
        },
      } as never,
    });

    const manifestPromise = runtime.getRuntimeManifest();

    await expect(manifestPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "modules.0.promotion_status",
        },
      },
    });
    await expect(manifestPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "modules.0.promotion_status" &&
        error.fieldErrors[0]?.path === "modules.0.promotion_status",
    );
  });

  it("rejects missing runtime manifest replay proof refs for shipping kernels returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeManifest: async () => {
          const manifest = makeRuntimeManifestPayload();
          delete (manifest.modules as Array<Record<string, unknown>>)[0]!.replay_proof_ref;
          return manifest;
        },
      } as never,
    });

    const manifestPromise = runtime.getRuntimeManifest();

    await expect(manifestPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "modules.0.replay_proof_ref",
        },
      },
    });
    await expect(manifestPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "modules.0.replay_proof_ref" &&
        error.fieldErrors[0]?.path === "modules.0.replay_proof_ref",
    );
  });

  it("rejects runtime manifest benchmark shipping function count drift returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeManifest: async () => {
          const manifest = makeRuntimeManifestPayload();
          (manifest.benchmark_discovery_lane as Record<string, unknown>).shipping_manifest_functions =
            999;
          return manifest;
        },
      } as never,
    });

    const manifestPromise = runtime.getRuntimeManifest();

    await expect(manifestPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "benchmark_discovery_lane.shipping_manifest_functions",
        },
      },
    });
    await expect(manifestPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path ===
          "benchmark_discovery_lane.shipping_manifest_functions" &&
        error.fieldErrors[0]?.path ===
          "benchmark_discovery_lane.shipping_manifest_functions",
    );
  });

  it("rejects invalid runtime benchmark discovery rules returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeManifest: async () => {
          const manifest = makeRuntimeManifestPayload();
          (manifest.shipping_contract as Record<string, unknown>).benchmark_discovery_rule =
            "shadow_runtime_contract";
          return manifest;
        },
      } as never,
    });

    const manifestPromise = runtime.getRuntimeManifest();

    await expect(manifestPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "shipping_contract.benchmark_discovery_rule",
        },
      },
    });
    await expect(manifestPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "shipping_contract.benchmark_discovery_rule" &&
        error.fieldErrors[0]?.path === "shipping_contract.benchmark_discovery_rule",
    );
  });

  it("rejects runtime admin summary function count drift returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeModules: async () => {
          const payload = makeRuntimeAdminModulesPayload();
          (payload.summary as Record<string, unknown>).function_count = 999;
          return payload;
        },
      } as never,
    });

    const modulesPromise = runtime.getRuntimeModules();

    await expect(modulesPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "summary.function_count",
        },
      },
    });
    await expect(modulesPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "summary.function_count" &&
        error.fieldErrors[0]?.path === "summary.function_count",
    );
  });

  it("rejects invalid runtime benchmark discovery rules in admin modules returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeModules: async () => {
          const payload = makeRuntimeAdminModulesPayload();
          (payload.shipping_contract as Record<string, unknown>).benchmark_discovery_rule =
            "shadow_runtime_contract";
          return payload;
        },
      } as never,
    });

    const modulesPromise = runtime.getRuntimeModules();

    await expect(modulesPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "shipping_contract.benchmark_discovery_rule",
        },
      },
    });
    await expect(modulesPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "shipping_contract.benchmark_discovery_rule" &&
        error.fieldErrors[0]?.path === "shipping_contract.benchmark_discovery_rule",
    );
  });

  it("rejects duplicate runtime benchmark compiled artifacts returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeBenchmarks: async () => {
          const payload = makeRuntimeAdminBenchmarksPayload();
          (payload.compiled_artifacts as Array<Record<string, unknown>>).push({
            ...(payload.compiled_artifacts as Array<Record<string, unknown>>)[0]!,
          });
          return payload;
        },
      } as never,
    });

    const benchmarksPromise = runtime.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "compiled_artifacts",
        },
      },
    });
    await expect(benchmarksPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "compiled_artifacts" &&
        error.fieldErrors[0]?.path === "compiled_artifacts",
    );
  });

  it("rejects invalid runtime non-shipping rules in admin benchmarks returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeBenchmarks: async () => {
          const payload = makeRuntimeAdminBenchmarksPayload();
          (payload.benchmark_discovery_lane as Record<string, unknown>).non_shipping_rule =
            "shadow_inventory_lane";
          return payload;
        },
      } as never,
    });

    const benchmarksPromise = runtime.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "benchmark_discovery_lane.non_shipping_rule",
        },
      },
    });
    await expect(benchmarksPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "benchmark_discovery_lane.non_shipping_rule" &&
        error.fieldErrors[0]?.path === "benchmark_discovery_lane.non_shipping_rule",
    );
  });

  it("rejects runtime benchmark compiled artifact reference drift returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeBenchmarks: async () => {
          const payload = makeRuntimeAdminBenchmarksPayload();
          (payload.module_benchmarks as Array<Record<string, unknown>>)[0]!.compiled_artifact =
            "build/missing-runtime-benchmark.json";
          (payload.shipping_runtime_compiled_artifacts as Array<string>)[0] =
            "build/missing-runtime-benchmark.json";
          return payload;
        },
      } as never,
    });

    const benchmarksPromise = runtime.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "module_benchmarks.0.compiled_artifact",
        },
      },
    });
    await expect(benchmarksPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "module_benchmarks.0.compiled_artifact" &&
        error.fieldErrors[0]?.path === "module_benchmarks.0.compiled_artifact",
    );
  });

  it("rejects runtime benchmark shipping function count drift returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeBenchmarks: async () => {
          const payload = makeRuntimeAdminBenchmarksPayload();
          (payload.shipping_runtime_function_counts as Array<number>)[0] = 3;
          return payload;
        },
      } as never,
    });

    const benchmarksPromise = runtime.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "shipping_runtime_function_counts.0",
        },
      },
    });
    await expect(benchmarksPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "shipping_runtime_function_counts.0" &&
        error.fieldErrors[0]?.path === "shipping_runtime_function_counts.0",
    );
  });

  it("rejects runtime benchmark shipping speedup drift returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeBenchmarks: async () => {
          const payload = makeRuntimeAdminBenchmarksPayload();
          (payload.shipping_runtime_benchmark_speedups_x as Array<number>)[0] = 999;
          return payload;
        },
      } as never,
    });

    const benchmarksPromise = runtime.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "shipping_runtime_benchmark_speedups_x.0",
        },
      },
    });
    await expect(benchmarksPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "shipping_runtime_benchmark_speedups_x.0" &&
        error.fieldErrors[0]?.path === "shipping_runtime_benchmark_speedups_x.0",
    );
  });

  it("rejects non-positive runtime benchmark speedup metrics returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeBenchmarks: async () => {
          const payload = makeRuntimeAdminBenchmarksPayload();
          (payload.shipping_runtime_benchmark_speedups_x as Array<number>)[0] = 0;
          (payload.module_benchmarks as Array<Record<string, unknown>>)[0]!.benchmark_speedup_x =
            0;
          return payload;
        },
      } as never,
    });

    const benchmarksPromise = runtime.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "module_benchmarks.0.benchmark_speedup_x",
        },
      },
    });
    await expect(benchmarksPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "module_benchmarks.0.benchmark_speedup_x" &&
        error.fieldErrors[0]?.path === "module_benchmarks.0.benchmark_speedup_x",
    );
  });

  it("rejects runtime benchmark shipping module identity drift returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeBenchmarks: async () => {
          const payload = makeRuntimeAdminBenchmarksPayload();
          (payload.shipping_runtime_modules as Array<string>)[0] = "embeddings";
          return payload;
        },
      } as never,
    });

    const benchmarksPromise = runtime.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "shipping_runtime_modules.0",
        },
      },
    });
    await expect(benchmarksPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "shipping_runtime_modules.0" &&
        error.fieldErrors[0]?.path === "shipping_runtime_modules.0",
    );
  });

  it("rejects runtime benchmark shipping artifact drift returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeBenchmarks: async () => {
          const payload = makeRuntimeAdminBenchmarksPayload();
          (payload.shipping_runtime_benchmark_artifacts as Array<string>)[0] =
            "benchmarks/results/embeddings.json";
          return payload;
        },
      } as never,
    });

    const benchmarksPromise = runtime.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "shipping_runtime_benchmark_artifacts.0",
        },
      },
    });
    await expect(benchmarksPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "shipping_runtime_benchmark_artifacts.0" &&
        error.fieldErrors[0]?.path === "shipping_runtime_benchmark_artifacts.0",
    );
  });

  it("rejects runtime benchmark shipping compiled artifact drift returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeBenchmarks: async () => {
          const payload = makeRuntimeAdminBenchmarksPayload();
          (payload.shipping_runtime_compiled_artifacts as Array<string>)[0] =
            "mojo_build/embeddings";
          return payload;
        },
      } as never,
    });

    const benchmarksPromise = runtime.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "shipping_runtime_compiled_artifacts.0",
        },
      },
    });
    await expect(benchmarksPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "shipping_runtime_compiled_artifacts.0" &&
        error.fieldErrors[0]?.path === "shipping_runtime_compiled_artifacts.0",
    );
  });

  it("rejects runtime benchmark shipping compiled engine drift returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeBenchmarks: async () => {
          const payload = makeRuntimeAdminBenchmarksPayload();
          (payload.shipping_runtime_compiled_engines as Array<string>)[0] =
            "python_fallback";
          return payload;
        },
      } as never,
    });

    const benchmarksPromise = runtime.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "shipping_runtime_compiled_engines.0",
        },
      },
    });
    await expect(benchmarksPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "shipping_runtime_compiled_engines.0" &&
        error.fieldErrors[0]?.path === "shipping_runtime_compiled_engines.0",
    );
  });

  it("rejects runtime benchmark SLO budget applies_to drift returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeBenchmarks: async () => {
          const payload = makeRuntimeAdminBenchmarksPayload();
          (payload.slo_budgets as Array<Record<string, unknown>>)[0]!.applies_to =
            "shadow_realm_lane";
          return payload;
        },
      } as never,
    });

    const benchmarksPromise = runtime.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "slo_budgets.0.applies_to",
        },
      },
    });
    await expect(benchmarksPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "slo_budgets.0.applies_to" &&
        error.fieldErrors[0]?.path === "slo_budgets.0.applies_to",
    );
  });

  it.each([
    ["shipping_runtime_max_cold_ms", "max_cold_ms", 999],
    ["shipping_runtime_max_warm_ms", "max_warm_ms", 999],
    ["shipping_runtime_max_hot_ms", "max_hot_ms", 999],
  ])(
    "rejects runtime benchmark %s drift returned by the injected client",
    async (shippingField, _benchmarkField, badValue) => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          getRuntimeBenchmarks: async () => {
            const payload = makeRuntimeAdminBenchmarksPayload();
            (payload[shippingField] as Array<number>)[0] = badValue;
            return payload;
          },
        } as never,
      });

      const benchmarksPromise = runtime.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: `${shippingField}.0`,
          },
        },
      });
      await expect(benchmarksPromise).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof RuntimeValidationError &&
          error.validationErrors[0]?.path === `${shippingField}.0` &&
          error.fieldErrors[0]?.path === `${shippingField}.0`,
      );
    },
  );

  it("rejects duplicate runtime benchmark artifact paths returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeBenchmarks: async () => {
          const payload = makeRuntimeAdminBenchmarksPayload();
          (payload.benchmark_discovery_lane as Record<string, unknown>).shipping_manifest_modules = 2;
          (payload.benchmark_discovery_lane as Record<string, unknown>).shipping_manifest_functions =
            4;
          (payload.shipping_runtime_modules as Array<string>).push("embeddings");
          (payload.shipping_runtime_function_counts as Array<number>).push(2);
          (payload.shipping_runtime_benchmark_speedups_x as Array<number>).push(101.0);
          (payload.shipping_runtime_benchmark_artifacts as Array<string>).push(
            "build/bench.json",
          );
          (payload.shipping_runtime_compiled_artifacts as Array<string>).push(
            "mojo_build/bpe_tokenizer",
          );
          (payload.shipping_runtime_compiled_engines as Array<string>).push("mojo");
          (payload.shipping_runtime_max_cold_ms as Array<number>).push(12.0);
          (payload.shipping_runtime_max_warm_ms as Array<number>).push(4.0);
          (payload.shipping_runtime_max_hot_ms as Array<number>).push(2.0);
          (payload.module_benchmarks as Array<Record<string, unknown>>).push({
            ...(payload.module_benchmarks as Array<Record<string, unknown>>)[0]!,
            name: "embeddings",
          });
          return payload;
        },
      } as never,
    });

    const benchmarksPromise = runtime.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "module_benchmarks.1.benchmark_artifact",
        },
      },
    });
    await expect(benchmarksPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "module_benchmarks.1.benchmark_artifact" &&
        error.fieldErrors[0]?.path === "module_benchmarks.1.benchmark_artifact",
    );
  });

  it("rejects duplicate runtime release validation evidence paths returned by the injected client", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        getRuntimeReleaseValidation: async () => {
          const payload = makeRuntimeReleaseValidationPayload();
          (
            (payload.conditions as Array<Record<string, unknown>>)[0]!
              .evidence_paths as Array<string>
          ).push(
            (
              (payload.conditions as Array<Record<string, unknown>>)[0]!
                .evidence_paths as Array<string>
            )[0]!,
          );
          return payload;
        },
      } as never,
    });

    const validationPromise = runtime.getRuntimeReleaseValidation();

    await expect(validationPromise).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: {
        source_error_code: "invalid_runtime_contract_payload",
        source_status_code: 0,
        source_error_details: {
          cause: "conditions.0.evidence_paths",
        },
      },
    });
    await expect(validationPromise).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof RuntimeValidationError &&
        error.validationErrors[0]?.path === "conditions.0.evidence_paths" &&
        error.fieldErrors[0]?.path === "conditions.0.evidence_paths",
    );
  });

  it.each([
    ["getRuntimeManifest", "getRuntimeManifest"],
    ["getRuntimeModules", "getRuntimeModules"],
    ["getRuntimeBenchmarks", "getRuntimeBenchmarks"],
    ["getRuntimeReleaseValidation", "getRuntimeReleaseValidation"],
  ] as const)(
    "normalizes an upstream invalid signed payload error from the api client for %s",
    async (methodName, clientMethodName) => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          [clientMethodName]: async () => {
            throw new DecisionEngineError(
              `${methodName} upstream signed payload invalid`,
              0,
              "invalid_runtime_contract_payload",
              {
                error: {
                  code: "invalid_runtime_contract_payload",
                  details: { cause: `${methodName}.proof_matrix[0].status` },
                },
              },
            );
          },
        } as never,
      });

      const proofPromise = runtime[methodName]();

      await expect(proofPromise).rejects.toMatchObject({
        code: "invalid_runtime_contract_payload",
        details: {
          source_error_code: "invalid_runtime_contract_payload",
          source_status_code: 0,
          source_error_details: {
            cause: `${methodName}.proof_matrix[0].status`,
          },
        },
      });
      await expect(proofPromise).rejects.toThrow(
        `${methodName}() returned an invalid signed payload.`,
      );
    },
  );

  it("requires persist when connecting from an inline connector preview", async () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_123",
      baseUrl: "http://localhost:8000",
      client: {
        connectData: async () => {
          throw new Error("should not be called");
        },
      } as never,
    });

    await expect(
      runtime.connect(null, {
        name: "preview_orders",
        connector: { type: "redis", url: "redis://localhost:6379" },
      }),
    ).rejects.toMatchObject({
      code: "connector_persistence_required",
    });
  });

  it("uses an exact api resolve for registered source fields when schema metadata is known", async () => {
    let resolveCalls = 0;
    const fakeClient = {
      registerSource: async () => ({
        status: "ready",
        source_id: "src_1",
        dataset_id: "src_1",
        name: "orders",
        source_schema: { fields: ["product_line", "revenue", "region"] },
        planner_schema_revision: "planner_schema_1",
      }),
      request: async () => ({
        entry: {
          source_schema_revision: "registry_schema_1",
        },
      }),
      resolve: async () => {
        resolveCalls += 1;
        throw new Error("exact api resolve should not call client.resolve");
      },
      verify: async () => ({
        valid: true,
        errors: [],
        suggestions: [],
        resolved: { source_name: "orders" },
        latency_ms: 1,
      }),
      query: async (request: Record<string, unknown>) => ({
        query_id: "query-1",
        result: 2,
        result_type: "scalar",
        confidence: 1,
        plan: ["Execute exact plan."],
        resolved_column: String(
          (request.resolved_plan as Record<string, unknown> | undefined)?.metric_column,
        ),
        resolved_role: "measure",
        resolved_source: String(
          (request.resolved_plan as Record<string, unknown> | undefined)?.source_name,
        ),
        row_count: 1,
        candidates: [],
        source_scores: { orders: 1 },
        ambiguous: false,
        exact_spec: true,
        explanation: ["Executed exactly."],
        latency_ms: 1,
        decision_path: "exact_spec",
        plan_hash: "plan-1",
        schema_revision: "registry_schema_1",
        validated: true,
        deterministic_scope: "api",
        confidence_source: "schema_truth",
        clarification_required: false,
        rejection_reason: null,
        request_id: "req_2",
        source_set: ["orders"],
        join_path: [],
        planner_mode: "exact_spec",
      }),
    };

    const runtime = new Runtime({
      mode: "api",
      client: fakeClient as never,
    });

    await runtime.connect({ records: [{ revenue: 42, product_line: "Electronics" }] }, { name: "orders" });
    const plan = await runtime.resolve({
      source_name: "orders",
      metric: "revenue",
      group_by: "product_line",
      aggregation: "count",
    });
    const verified = await runtime.verify(plan);
    const result = await runtime.query(plan);

    expect(resolveCalls).toBe(0);
    expect(plan.resolved_plan?.source_name).toBe("orders");
    expect(plan.resolved_plan?.metric_column).toBe("revenue");
    expect(plan.resolved_plan?.group_column).toBe("product_line");
    expect(plan.schema_revision).toBe("registry_schema_1");
    expect(verified.valid).toBe(true);
    expect(result.result).toBe(2);
  });

  it("lifts runtime dataset scope for exact api verify and query payloads", async () => {
    let capturedVerify: Record<string, unknown> | null = null;
    let capturedQuery: Record<string, unknown> | null = null;
    const fakeClient = {
      registerSource: async () => ({
        status: "ready",
        source_id: "src_alias_1",
        dataset_id: "src_alias_1",
        name: "orders_alias",
        source_schema: {
          source: "orders",
          fields: ["product_line", "revenue", "region"],
        },
        planner_schema_revision: "planner_schema_1",
      }),
      request: async () => ({
        entry: {
          source_schema_revision: "registry_schema_1",
        },
      }),
      verify: async (request: Record<string, unknown>) => {
        capturedVerify = request;
        return {
          valid: true,
          errors: [],
          suggestions: [],
          resolved: { source_name: "orders" },
          latency_ms: 1,
        };
      },
      query: async (request: Record<string, unknown>) => {
        capturedQuery = request;
        return {
          query_id: "query-1",
          result: 2,
          result_type: "scalar",
          confidence: 1,
          plan: ["Execute exact plan."],
          resolved_column: "revenue",
          resolved_role: "measure",
          resolved_source: "orders",
          row_count: 1,
          candidates: [],
          source_scores: { orders: 1 },
          ambiguous: false,
          exact_spec: true,
          explanation: ["Executed exactly."],
          latency_ms: 1,
          decision_path: "exact_spec",
          plan_hash: "plan-1",
          schema_revision: "registry_schema_1",
          validated: true,
          deterministic_scope: "api",
          confidence_source: "schema_truth",
          clarification_required: false,
          rejection_reason: null,
          request_id: "req_2",
          source_set: ["orders"],
          join_path: [],
          planner_mode: "exact_spec",
        };
      },
    };

    const runtime = new Runtime({
      mode: "api",
      client: fakeClient as never,
    });

    await runtime.connect(
      { records: [{ revenue: 42, product_line: "Electronics" }] },
      { name: "orders_alias" },
    );
    const plan = await runtime.resolve({
      source_name: "orders_alias",
      metric: "revenue",
      group_by: "product_line",
      aggregation: "count",
    });
    await runtime.verify(plan);
    await runtime.query(plan);

    expect(plan.resolved_plan?.source_name).toBe("orders");
    expect(plan.resolved_plan?.constraints).toMatchObject({
      __runtime_dataset_id__: "src_alias_1",
    });
    expect(capturedVerify).toMatchObject({
      dataset_id: "src_alias_1",
      resolved_plan: {
        source_name: "orders",
        metric_column: "revenue",
        schema_revision: "registry_schema_1",
        constraints: {},
      },
    });
    expect(capturedQuery).toMatchObject({
      dataset_id: "src_alias_1",
      resolved_plan: {
        source_name: "orders",
        metric_column: "revenue",
        schema_revision: "registry_schema_1",
        constraints: {},
      },
    });
  });

  it("hydrates missing api registration row counts from dataset detail", async () => {
    const fakeClient = {
      registerSource: async () => ({
        status: "already_registered",
        source_id: "src_s3_1",
        dataset_id: "src_s3_1",
        name: "orders_s3",
        source_schema: { source: "orders", fields: ["product_line", "revenue"] },
        planner_schema_revision: "schema_s3_1",
      }),
      getDataset: async () => ({
        dataset: {
          dataset_id: "src_s3_1",
          name: "orders_s3",
          status: "ready",
          source_names: ["orders"],
          row_count: 29,
          column_count: 2,
        },
        schema: {
          source: "orders",
          fields: ["product_line", "revenue"],
        },
      }),
    };

    const runtime = new Runtime({
      mode: "api",
      client: fakeClient as never,
    });

    const registration = await runtime.connect(
      {
        type: "s3",
        bucket: "algenta-public",
        key: "orders/orders.csv",
        format: "csv",
      },
      { name: "orders_s3" },
    );

    expect(registration.status).toBe("already_registered");
    expect(registration.row_count).toBe(29);
    expect(registration.source_schema).toMatchObject({
      source: "orders",
      fields: ["product_line", "revenue"],
    });
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

  it("accepts canonical connector envelopes in api mode", async () => {
    const cases: Array<{
      source: Record<string, unknown>;
      expectedName: string;
      expectedConnection: Record<string, unknown>;
    }> = [
      {
        source: {
          type: "postgres",
          location: {
            host: "localhost",
            port: 5432,
            database: "orders",
            schema: "public",
            table: "orders",
          },
          auth: {
            credentials: {
              user: "analytics",
              password: "secret",
            },
          },
        },
        expectedName: "orders_pg",
        expectedConnection: {
          type: "sql",
          provider: "postgres",
          connection_string: "postgresql://analytics:secret@localhost:5432/orders",
          schema: "public",
          table: "orders",
          query: "SELECT * FROM public.orders",
        },
      },
      {
        source: {
          type: "s3",
          location: { bucket: "algenta-public", key: "orders/orders.csv" },
          options: { format: "csv" },
        },
        expectedName: "orders_s3",
        expectedConnection: {
          type: "s3",
          bucket: "algenta-public",
          key: "orders/orders.csv",
          file_type: "csv",
        },
      },
      {
        source: {
          type: "rest",
          location: { base_url: "https://example.com/api", path: "/orders" },
          auth: { mode: "token", credentials: { token: "secret-token" } },
          options: { method: "GET" },
        },
        expectedName: "orders_rest",
        expectedConnection: {
          type: "rest_api",
          url: "https://example.com/api/orders",
          path: "/orders",
          method: "GET",
          headers: { Authorization: "Bearer secret-token" },
        },
      },
      {
        source: {
          type: "csv",
          location: { path: REAL_MARCH_ORDERS },
          options: { delimiter: "," },
        },
        expectedName: "orders_csv",
        expectedConnection: {
          type: "file",
          file_type: "csv",
          file_path: REAL_MARCH_ORDERS,
          delimiter: ",",
        },
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
      cases.map(({ expectedName, expectedConnection }) => ({
        source: {
          name: expectedName,
          connection: expectedConnection,
        },
        options: {
          description: `Primary ${expectedName} source`,
        },
      })),
    );
  });

  it("accepts canonical csv connectors in local mode", async () => {
    const runtimeDir = runtimeTempDir();
    try {
      const csvPath = join(runtimeDir, "orders.csv");
      writeFileSync(csvPath, "product_line,revenue\nElectronics,10\nApparel,20\n");

      const runtime = new Runtime();
      const registration = await runtime.connect(
        {
          type: "csv",
          location: { path: csvPath },
          options: { delimiter: "," },
        },
        { name: "orders" },
      );
      const plan = await runtime.resolve({
        source_name: "orders",
        metric: "revenue",
        aggregation: "count",
      });
      const result = await runtime.query(plan);

      expect(registration.row_count).toBe(2);
      expect(plan.resolved_plan?.source_name).toBe("orders");
      expect(result.result).toBe(2);
    } finally {
      rmSync(runtimeDir, { recursive: true, force: true });
    }
  });

  it("rejects remote canonical connectors in local mode", async () => {
    const runtime = new Runtime();

    await expect(
      runtime.connect({
        type: "postgres",
        location: {
          host: "localhost",
          port: 5432,
          database: "orders",
          schema: "public",
          table: "orders",
        },
        auth: {
          credentials: {
            user: "analytics",
            password: "secret",
          },
        },
      }),
    ).rejects.toMatchObject({ code: "unsupported_local_connector" });
  });

  it("returns a branded import preview for local sources", async () => {
    const runtime = new Runtime();
    const imported = await runtime.importPreview(
      [{ product_line: "Electronics", revenue: 42_193_221, region: "US" }],
      { name: "orders", sourceRef: "orders.csv", color: false },
    );

    expect(imported.registration.name).toBe("orders");
    expect(imported.registration.row_count).toBe(1);
    expect(imported.preview).toContain("Algenta Source Import");
    expect(imported.preview).toContain("Source: orders");
    expect(imported.preview).toContain("Origin: orders.csv");
    expect(imported.preview).toContain("Rows: 1 | Fields: 3");
  });

  it("renders a pure import preview from registration metadata", () => {
    const preview = renderSourceImportPreview(
      {
        name: "orders",
        status: "ready",
        row_count: 2,
        planner_schema_revision: "schema_revision_123456",
        latency_ms: 4.2,
        source_schema: { fields: ["product_line", "revenue", "region", "country"] },
      },
      { sourceRef: "orders.csv", mode: "local", color: false },
    );

    expect(preview).toContain("Algenta Source Import");
    expect(preview).toContain("Mode: local | Status: ready");
    expect(preview).toContain("Preview: product_line, revenue, region, +1 more");
    expect(preview).toContain("Schema: schema_revis | Latency: 4.200ms");
  });

  it("renders a pure bundle preview from registration and failure metadata", () => {
    const preview = renderSourceBundlePreview(
      [
        {
          source_id: "src_1",
          dataset_id: "src_1",
          name: "orders_detail",
          status: "ready",
          row_count: 6097,
          planner_schema_revision: "schema_orders_123456",
          latency_ms: 12.5,
          source_schema: { fields: ["Order ID", "Store Name", "Sales (incl. tax)"] },
        },
        {
          source_id: "src_2",
          dataset_id: "src_2",
          name: "orders_financial",
          status: "ready",
          row_count: 2026,
          planner_schema_revision: "schema_financial_123456",
          latency_ms: 8.3,
          source_schema: {
            fields: [
              "Order ID as per Uber Eats manager",
              "Store name as per Uber Eats manager",
            ],
          },
        },
      ],
      [
        {
          sourceRef: "store_pause.csv",
          code: "empty_source",
          message: "Connected source is empty and cannot be queried.",
          name: "store_pause",
        },
      ],
      { color: false },
    );

    expect(preview).toContain("Algenta Source Bundle");
    expect(preview).toContain("Imported: 2 | Failures: 1");
    expect(preview).toContain("orders_detail");
    expect(preview).toContain("orders_financial");
    expect(preview).toContain("store_pause: empty_source");
  });

  it("supports local file-backed CSV import preview and query for real corpus files", async () => {
    const runtime = new Runtime();
    const imported = await runtime.importPreview(REAL_MARCH_ORDERS, {
      name: "orders_detail",
      sourceRef: "orders_detail.csv",
      color: false,
    });

    const plan = await runtime.resolve({
      source_name: "orders_detail",
      metric: "Sales (incl. tax)",
      group_by: "Order Channel",
    });
    const result = await runtime.query(plan);

    expect(imported.registration.row_count).toBe(6097);
    expect(imported.preview).toContain("Origin: orders_detail.csv");
    expect(plan.resolved_plan?.metric_column).toBe("Sales (incl. tax)");
    expect(plan.resolved_plan?.group_column).toBe("Order Channel");
    expect(result.result_type).toBe("table");
    expect(result.row_count).toBeGreaterThan(0);
  });

  it("supports branded bundle previews across real csv and local sqlite sources", async () => {
    if (!(await hasNodeSqlite())) {
      return;
    }
    const runtimeDir = runtimeTempDir();
    const dbPath = join(runtimeDir, "orders.db");
    await writeSqliteFixture(dbPath, [
      { product_line: "Electronics", revenue: 42_193_221, region: "US" },
      { product_line: "Apparel", revenue: 28_114_992, region: "US" },
    ]);

    const runtime = new Runtime();
    const bundle = await runtime.importBundlePreview(
      [
        REAL_MARCH_ORDERS,
        {
          provider: "sqlite",
          path: dbPath,
          table: "orders",
        },
        REAL_MARCH_EMPTY,
      ],
      {
        sourceRefs: ["orders_detail.csv", "orders.db#orders", REAL_MARCH_EMPTY.split(/[\\/]/).pop()],
        color: false,
      },
    );

    expect(bundle.registrations).toHaveLength(2);
    expect(bundle.failures).toHaveLength(1);
    expect(bundle.preview).toContain("Algenta Source Bundle");
    expect(bundle.preview).toContain("Imported: 2 | Failures: 1");
    expect(bundle.preview).toContain("orders_orders");
    expect(bundle.preview).toContain("empty_source");
  });

  it("supports api-mode bundle previews across mixed connector descriptors", async () => {
    const seen: Array<Record<string, unknown>> = [];
    const fakeClient = {
      registerSource: async (
        source: Record<string, unknown>,
        options: Record<string, unknown>,
      ) => {
        seen.push(source);
        const connection = source.connection;
        if (connection && typeof connection === "object" && (connection as Record<string, unknown>).type === "rest_api") {
          throw new RuntimeValidationError(
            "upstream_validation_failed",
            "REST source rejected by hosted connector validation.",
            { source: (connection as Record<string, unknown>).url },
          );
        }
        return {
          source_id: `src_${seen.length}`,
          dataset_id: `src_${seen.length}`,
          name: String(source.name ?? "source"),
          status: "ready",
          row_count: 120,
          planner_schema_revision: `schema_${seen.length}`,
          latency_ms: 3.4,
          source_schema: { fields: ["order_id", "revenue", "store_name"] },
        };
      },
    };

    const runtime = new Runtime({
      mode: "api",
      client: fakeClient as never,
    });

    const bundle = await runtime.importBundlePreview(
      [
        {
          type: "postgres",
          location: {
            host: "localhost",
            port: 5432,
            database: "orders",
            schema: "public",
            table: "orders",
          },
          auth: {
            credentials: {
              user: "analytics",
              password: "secret",
            },
          },
        },
        {
          type: "s3",
          bucket: "algenta-public",
          key: "orders/orders.csv",
          format: "csv",
        },
        {
          type: "rest",
          base_url: "https://example.com/api",
          path: "/orders",
          method: "GET",
        },
      ],
      {
        names: ["orders_pg", "orders_s3", "orders_rest"],
        sourceRefs: [
          "postgres://orders",
          "s3://algenta-public/orders/orders.csv",
          "https://example.com/api/orders",
        ],
        color: false,
      },
    );

    expect(bundle.registrations).toHaveLength(2);
    expect(bundle.failures).toHaveLength(1);
    expect(bundle.failures[0]?.code).toBe("upstream_validation_failed");
    expect(bundle.preview).toContain("Algenta Source Bundle");
    expect(bundle.preview).toContain("Imported: 2 | Failures: 1");
    expect(bundle.preview).toContain("orders_pg");
    expect(bundle.preview).toContain("orders_s3");
    expect(bundle.preview).toContain("orders_rest: upstream_validation_failed");
    expect(seen.map(source => String(source.name))).toEqual(["orders_pg", "orders_s3", "orders_rest"]);
    expect(
      seen.map(source => String((source.connection as Record<string, unknown>).type)),
    ).toEqual(["sql", "s3", "rest_api"]);
  });

  it("supports connectMany across related real csv sources with explicit names", async () => {
    const runtime = new Runtime();
    const registrations = await runtime.connectMany(
      [REAL_MARCH_ORDERS, REAL_MARCH_FINANCIAL],
      { names: ["orders_detail", "orders_financial"] },
    );

    expect(registrations).toHaveLength(2);
    expect(registrations[0]?.name).toBe("orders_detail");
    expect(registrations[0]?.row_count).toBe(6097);
    expect(registrations[1]?.name).toBe("orders_financial");
    expect(registrations[1]?.row_count).toBe(2026);
  });

  it("skips alias header rows in real financial csv files", async () => {
    const runtime = new Runtime();
    const registration = await runtime.connect(REAL_MARCH_FINANCIAL, { name: "orders_financial" });

    expect(registration.row_count).toBe(2026);
  });

  it("supports local sqlite descriptors when node:sqlite is available", async () => {
    if (!(await hasNodeSqlite())) {
      return;
    }
    const runtimeDir = runtimeTempDir();
    const dbPath = join(runtimeDir, "orders.db");
    await writeSqliteFixture(dbPath, [
      { product_line: "Electronics", revenue: 42_193_221, region: "US" },
      { product_line: "Apparel", revenue: 28_114_992, region: "US" },
    ]);

    const runtime = new Runtime();
    const registration = await runtime.connect({
      provider: "sqlite",
      path: dbPath,
      table: "orders",
    });
    const plan = await runtime.resolve({
      source_name: registration.name,
      metric: "revenue",
      group_by: "product_line",
    });
    const result = await runtime.query(plan);

    expect(registration.name).toBe("orders_orders");
    expect(registration.row_count).toBe(2);
    expect(result.row_count).toBe(2);
  });

  it("renders sqlite descriptor origins cleanly in import previews", async () => {
    if (!(await hasNodeSqlite())) {
      return;
    }
    const runtimeDir = runtimeTempDir();
    const dbPath = join(runtimeDir, "orders.db");
    await writeSqliteFixture(dbPath, [
      { product_line: "Electronics", revenue: 42_193_221, region: "US" },
      { product_line: "Apparel", revenue: 28_114_992, region: "US" },
    ]);

    const runtime = new Runtime();
    const imported = await runtime.importPreview({
      provider: "sqlite",
      path: dbPath,
      table: "orders",
    });

    expect(imported.registration.name).toBe("orders_orders");
    expect(imported.preview).toContain(`Origin: orders.db#orders`);
  });

  it("rejects empty real csv exports", async () => {
    const runtime = new Runtime();

    await expect(runtime.connect(REAL_MARCH_EMPTY, { name: "store_pause" })).rejects.toBeInstanceOf(
      RuntimeValidationError,
    );
  });

  it("enforces hosted local limits offline with a stored license on real csv files", async () => {
    const runtimeDir = runtimeTempDir();
    process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
    process.env.ALGENTA_JWT_SECRET = "ts-runtime-test-secret";
    seedStoredLicense(runtimeDir, "de_live_ts_runtime_key");
    seedCredits(runtimeDir, 2, 2);
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new Error("offline");
    }));

    const runtime = new Runtime({ apiKey: "de_live_ts_runtime_key" });
    await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
    const plan = await runtime.resolve({
      source_name: "orders_detail",
      metric: "Sales (incl. tax)",
      group_by: "Order Channel",
    });

    const first = await runtime.query(plan);
    const second = await runtime.query(plan);

    expect(first.row_count).toBeGreaterThan(0);
    expect(second.row_count).toBeGreaterThan(0);
    await expect(runtime.query(plan)).rejects.toMatchObject({ code: "quota_exhausted" });
    expect(JSON.parse(readFileSync(join(runtimeDir, "credits.json"), "utf8")).credits_remaining).toBe(0);
  });

  it("allows key-bound offline execution without a local credit batch", async () => {
    const runtimeDir = runtimeTempDir();
    process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
    process.env.ALGENTA_JWT_SECRET = "ts-runtime-test-secret";
    const now = Math.floor(Date.now() / 1000);
    seedStoredLicense(runtimeDir, "de_live_ts_runtime_key", now + 86_400);
    const fetchSpy = vi.fn(async () => {
      throw new Error("offline");
    });
    vi.stubGlobal("fetch", fetchSpy);

    const runtime = new Runtime({ apiKey: "de_live_ts_runtime_key" });
    await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
    const plan = await runtime.resolve({
      source_name: "orders_detail",
      metric: "Sales (incl. tax)",
      group_by: "Order Channel",
    });

    const first = await runtime.query(plan);
    const second = await runtime.query(plan);

    expect(first.row_count).toBeGreaterThan(0);
    expect(second.row_count).toBeGreaterThan(0);
    expect(existsSync(join(runtimeDir, "credits.json"))).toBe(false);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("blocks first-time offline hosted local execution without a stored license", async () => {
    const runtimeDir = runtimeTempDir();
    process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
    process.env.ALGENTA_JWT_SECRET = "ts-runtime-test-secret";
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new Error("offline");
    }));

    const runtime = new Runtime({ apiKey: "de_live_ts_runtime_key" });
    await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
    const plan = await runtime.resolve({
      source_name: "orders_detail",
      metric: "Sales (incl. tax)",
      group_by: "Order Channel",
    });

    await expect(runtime.query(plan)).rejects.toMatchObject({
      code: "license_required",
      message: expect.stringContaining("reachable control plane"),
    });
  });

  it("keeps plain local runtime outside hosted local enforcement", async () => {
    const runtimeDir = runtimeTempDir();
    process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
    const fetchSpy = vi.fn(async () => {
      throw new Error("hosted path should not run");
    });
    vi.stubGlobal("fetch", fetchSpy);

    const runtime = new Runtime();
    await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
    const plan = await runtime.resolve({
      source_name: "orders_detail",
      metric: "Sales (incl. tax)",
      group_by: "Order Channel",
    });
    const result = await runtime.query(plan);

    expect(result.row_count).toBeGreaterThan(0);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("keeps self_hosted private local runtime outside hosted local enforcement", async () => {
    const runtimeDir = runtimeTempDir();
    process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    process.env.ALGENTA_DISABLE_CLOUD = "1";
    const fetchSpy = vi.fn(async () => {
      throw new Error("hosted path should not run");
    });
    vi.stubGlobal("fetch", fetchSpy);

    const runtime = new Runtime({ apiKey: "de_live_ts_runtime_key" });
    await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
    const plan = await runtime.resolve({
      source_name: "orders_detail",
      metric: "Sales (incl. tax)",
      group_by: "Order Channel",
    });
    const result = await runtime.query(plan);

    expect(result.row_count).toBeGreaterThan(0);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("requires a local signed license in air_gapped local mode", async () => {
    const runtimeDir = runtimeTempDir();
    process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
    process.env.ALGENTA_DEPLOYMENT_MODE = "air_gapped";
    const fetchSpy = vi.fn(async () => {
      throw new Error("hosted path should not run");
    });
    vi.stubGlobal("fetch", fetchSpy);

    const runtime = new Runtime();
    await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
    const plan = await runtime.resolve({
      source_name: "orders_detail",
      metric: "Sales (incl. tax)",
      group_by: "Order Channel",
    });

    await expect(runtime.query(plan)).rejects.toMatchObject({
      code: "license_required",
      message: expect.stringContaining("local signed license"),
    });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("accepts an RS256 offline local license in air_gapped local mode", async () => {
    const runtimeDir = runtimeTempDir();
    process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
    process.env.ALGENTA_DEPLOYMENT_MODE = "air_gapped";
    const offlineLicense = issueOfflineLocalLicense(Math.floor(Date.now() / 1000) + 86_400);
    process.env.ALGENTA_LOCAL_LICENSE_PUBLIC_KEY = offlineLicense.publicKey;
    writeFileSync(join(runtimeDir, "license.jwt"), offlineLicense.token, { mode: 0o600 });
    const fetchSpy = vi.fn(async () => {
      throw new Error("hosted path should not run");
    });
    vi.stubGlobal("fetch", fetchSpy);

    const runtime = new Runtime();
    await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
    const plan = await runtime.resolve({
      source_name: "orders_detail",
      metric: "Sales (incl. tax)",
      group_by: "Order Channel",
    });
    const result = await runtime.query(plan);

    expect(result.row_count).toBeGreaterThan(0);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("seeds stored license and local credits from control-plane registration", async () => {
    const runtimeDir = runtimeTempDir();
    process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
    process.env.ALGENTA_JWT_SECRET = "ts-runtime-test-secret";
    const serverTime = 2_200_000_000;
    const fetchSpy = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/v1/device/register")) {
        return new Response(
          JSON.stringify({
            license_token: issueControlPlaneLicense("de_live_ts_runtime_key", serverTime + 86_400),
            credits_granted: 2,
            credits_billing_period: "2026-04",
            credits_expires_at: serverTime + 3600,
            server_time: serverTime,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(JSON.stringify({ credits_granted: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchSpy);

    const runtime = new Runtime({ apiKey: "de_live_ts_runtime_key" });
    await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
    const plan = await runtime.resolve({
      source_name: "orders_detail",
      metric: "Sales (incl. tax)",
      group_by: "Order Channel",
    });
    const result = await runtime.query(plan);

    expect(result.row_count).toBeGreaterThan(0);
    expect(existsSync(join(runtimeDir, "license.jwt"))).toBe(true);
    expect(JSON.parse(readFileSync(join(runtimeDir, "credits.json"), "utf8")).credits_remaining).toBe(2);
    expect(JSON.parse(readFileSync(join(runtimeDir, "trusted_time.json"), "utf8"))).toMatchObject({
      trusted_epoch: serverTime,
      source: "control-plane-register",
    });
    expect(fetchSpy).toHaveBeenCalled();
  });

  it("records sanitized control-plane egress when hosted local registration succeeds", async () => {
    const runtimeDir = runtimeTempDir();
    process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
    process.env.ALGENTA_JWT_SECRET = "ts-runtime-test-secret";
    process.env.ALGENTA_ALLOW_OUTBOUND_NETWORK = "0";
    process.env.ALGENTA_CONTROL_PLANE_URL = "https://control.customer.internal";
    process.env.ALGENTA_EGRESS_ALLOWLIST = "control.customer.internal";
    const serverTime = 2_200_000_000;
    const fetchSpy = vi.fn(async () =>
      new Response(
        JSON.stringify({
          license_token: issueControlPlaneLicense("de_live_ts_runtime_key", serverTime + 86_400),
          credits_granted: 1,
          credits_billing_period: "2026-04",
          credits_expires_at: serverTime + 3600,
          server_time: serverTime,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchSpy);

    const runtime = new Runtime({ apiKey: "de_live_ts_runtime_key" });
    await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
    const plan = await runtime.resolve({
      source_name: "orders_detail",
      metric: "Sales (incl. tax)",
      group_by: "Order Channel",
    });
    await runtime.query(plan);

    const [event] = readLedgerEvents(runtimeDir);
    expect(event.action).toBe("privacy_egress");
    expect(event.status).toBe("allow");
    expect(event.target).toBe("internal-host");
    expect(event.success).toBe(true);
    expect(event.error).toBeNull();
    expect(event.details).toMatchObject({
      surface: "device_register",
      egress_class: "operator_service",
      decision: "allow",
      reason: "destination_allowlisted",
      deployment_mode: "saas",
      service_name: "runtime",
      destination_host_redacted: "internal-host",
    });
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("rejects a stored license when the trusted floor passed hard expiry despite a rolled-back wall clock", async () => {
    const runtimeDir = runtimeTempDir();
    process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
    process.env.ALGENTA_JWT_SECRET = "ts-runtime-test-secret";
    const expiresAt = 1_900_000_000;
    seedStoredLicense(runtimeDir, "de_live_ts_runtime_key", expiresAt);
    seedTrustedTime(runtimeDir, expiresAt + 14 * 86_400 + 5);
    seedCredits(runtimeDir, 2, 2);
    vi.spyOn(Date, "now").mockReturnValue((expiresAt - 86_400) * 1000);
    vi.spyOn(performance, "now").mockReturnValue(0);
    const fetchSpy = vi.fn(async () => {
      throw new Error("offline");
    });
    vi.stubGlobal("fetch", fetchSpy);

    const runtime = new Runtime({ apiKey: "de_live_ts_runtime_key" });
    await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
    const plan = await runtime.resolve({
      source_name: "orders_detail",
      metric: "Sales (incl. tax)",
      group_by: "Order Channel",
    });

    await expect(runtime.query(plan)).rejects.toMatchObject({
      code: "license_required",
      message: expect.stringContaining("renew"),
    });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("advances the trusted offline clock with monotonic time when the wall clock stalls", async () => {
    const runtimeDir = runtimeTempDir();
    process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
    process.env.ALGENTA_JWT_SECRET = "ts-runtime-test-secret";
    const issuedAt = 1_950_000_000;
    const expiresAt = issuedAt + 1;
    seedStoredLicense(runtimeDir, "de_live_ts_runtime_key", expiresAt);
    seedTrustedTime(runtimeDir, issuedAt);
    seedCredits(runtimeDir, 2, 2);
    vi.spyOn(Date, "now").mockReturnValue(issuedAt * 1000);
    let monotonicMillis = 0;
    vi.spyOn(performance, "now").mockImplementation(() => monotonicMillis);
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new Error("offline");
    }));

    const runtime = new Runtime({ apiKey: "de_live_ts_runtime_key" });
    await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
    const plan = await runtime.resolve({
      source_name: "orders_detail",
      metric: "Sales (incl. tax)",
      group_by: "Order Channel",
    });

    monotonicMillis = 0;
    const first = await runtime.query(plan);
    expect(first.row_count).toBeGreaterThan(0);

    monotonicMillis = (14 * 86_400 + 5) * 1000;
    await expect(runtime.query(plan)).rejects.toMatchObject({
      code: "license_required",
      message: expect.stringContaining("renew"),
    });
  });
});
