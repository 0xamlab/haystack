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

function makeQueryResponse(overrides: Record<string, unknown> = {}) {
  return {
    query_id: "query-1",
    result: { rows: [] },
    result_type: "table",
    confidence: 0.98,
    plan: ["resolve metric", "execute query"],
    resolved_column: "revenue",
    resolved_role: "metric",
    resolved_source: "orders",
    row_count: 1,
    candidates: [],
    source_scores: { orders: 0.98 },
    ambiguous: false,
    exact_spec: true,
    explanation: ["used exact spec"],
    latency_ms: 12,
    decision_path: "exact_spec",
    plan_hash: "plan-1",
    validated: true,
    deterministic_scope: "exact",
    confidence_source: "schema_truth",
    ...overrides,
  };
}

function makeLLMModelsPayload(): Record<string, unknown> {
  return {
    object: "list",
    data: [
      {
        id: "text.tokenizer",
        object: "model",
        owned_by: "algenta",
        runtime_module: "text.tokenizer",
        description: "Deterministic tokenizer utility model",
        capabilities: ["tokenize", "count_tokens", "chat_completions"],
        supported_endpoints: [
          "/v1/models",
          "/v1/tokenize",
          "/v1/count_tokens",
          "/v1/chat/completions",
          "/v1/responses",
        ],
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
  };
}

function makeDecisionPlanPayload(): Record<string, unknown> {
  return {
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
  };
}

function makeProductDecisionPayload(): Record<string, unknown> {
  return {
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
  };
}

function makeProductAgentRunPayload(): Record<string, unknown> {
  return {
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
  };
}

function makeProductOptimizePayload(): Record<string, unknown> {
  return {
    optimization_id: "opt_123",
    status: "completed",
    optimal_values: { price: 119.0 },
    objective_value: 183000,
    improvement_vs_midpoint: 14.6,
    constraints_satisfied: true,
    iterations_run: 1200,
    latency_ms: 63.0,
  };
}

function makeProductRetrievePayload(): Record<string, unknown> {
  return {
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
  };
}

function makeProductForecastPayload(): Record<string, unknown> {
  return {
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
  };
}

function makeDecisionLogPayload(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
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
    ...overrides,
  };
}

function makeDecisionListPayload(): Record<string, unknown> {
  return {
    decisions: [makeDecisionLogPayload()],
    total: 1,
    page: 1,
    limit: 20,
    pages: 1,
    page_size: 20,
  };
}

function makeExecutionReceiptPayload(): Record<string, unknown> {
  return {
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
  };
}

function makeDecisionEnvelopePayload(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    run_id: "run_decision_123",
    status: "completed",
    engine_version: "2026.05.0",
    recommended_action: "Expand sales coverage",
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
    ...overrides,
  };
}

function makeRecommendPayload(): Record<string, unknown> {
  return {
    recommended_action: "expand",
    confidence: 0.76,
    rationale: "Expand has the strongest expected value after risk adjustment.",
    action_results: [
      {
        name: "expand",
        rank: 1,
        envelope: makeDecisionEnvelopePayload({ recommended_action: "expand" }),
        expected_value: 140000,
        probability_of_loss: 0.15,
        score: 0.76,
      },
      {
        name: "hold",
        rank: 2,
        envelope: makeDecisionEnvelopePayload({ recommended_action: "hold" }),
        expected_value: 90000,
        probability_of_loss: 0.08,
        score: 0.58,
      },
    ],
    total_actions: 2,
    decision_plan: makeDecisionPlanPayload(),
  };
}

function makeScorePayload(): Record<string, unknown> {
  return {
    envelope: makeDecisionEnvelopePayload(),
    score: 0.73,
    score_breakdown: {
      expected_value: 0.61,
      downside_risk: 0.12,
    },
  };
}

function makeComparePayload(): Record<string, unknown> {
  return {
    winner: "stretch",
    margin: {
      expected_value_delta: 20000,
      probability_of_loss_delta: -0.04,
      score_delta: 0.09,
    },
    scenarios: [
      {
        name: "base",
        envelope: makeDecisionEnvelopePayload({ recommended_action: "base" }),
        delta_vs_best: {
          expected_value_delta: -20000,
          probability_of_loss_delta: 0.04,
          score_delta: -0.09,
        },
      },
      {
        name: "stretch",
        envelope: makeDecisionEnvelopePayload({ recommended_action: "stretch" }),
        delta_vs_best: {
          expected_value_delta: 0,
          probability_of_loss_delta: 0,
          score_delta: 0,
        },
      },
    ],
  };
}

function makeAgentRunPayload(
  status: string,
  pendingAction: string | null = null,
): Record<string, unknown> {
  return {
    run_id: "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
    status,
    task: "Search the knowledge base",
    output_format: "markdown",
    approval_mode: "manual",
    pending_action: pendingAction,
    selected_tool: "search",
    result: { summary: "Found 3 relevant documents" },
    tools_available: ["search", "summarize"],
    tools_used: ["search"],
    steps: [
      {
        step_number: 1,
        action: "Planning execution for: Search the knowledge base",
        status: "completed",
      },
      {
        step_number: 2,
        action: "Routing to search tool",
        tool_name: "search",
        result: "Found 3 relevant documents",
        status: "completed",
      },
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
    source_run_id: null,
    source_checkpoint_id: null,
    created_at: "2026-05-24T12:00:00Z",
    updated_at: "2026-05-24T12:00:03Z",
    latency_ms: 21.5,
  };
}

function makeAgentRunEventsPayload(): Record<string, unknown> {
  return {
    object: "list",
    run_id: "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
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
  };
}

function makeAgentRunListPayload(): Record<string, unknown> {
  return {
    object: "list",
    data: [makeAgentRunPayload("requires_approval", "approve")],
    total: 1,
    page: 1,
    limit: 25,
    pages: 1,
  };
}

function makeAgentRunCheckpointsPayload(): Record<string, unknown> {
  return {
    object: "list",
    run_id: "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
    data: [
      {
        checkpoint_id: "cp_1",
        checkpoint_index: 1,
        run_id: "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
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
        run_id: "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
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
  };
}

function makeAgentRunMissionEventsPayload(): Record<string, unknown> {
  return {
    object: "list",
    run_id: "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
    data: [
      {
        mission_id: "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        thread_id: "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        tenant_scope: "org_test",
        workspace_scope: "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
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
  };
}

function makeAgentRunMissionEventQueryPayload(): Record<string, unknown> {
  const base = makeAgentRunMissionEventsPayload().data as Array<Record<string, unknown>>;
  return {
    object: "list",
    data: [{ ...base[0], run_id: "8e3c9e2c-b67d-42da-b456-1de39d7289fb", run_status: "completed" }],
    total: 1,
    page: 1,
    limit: 25,
    pages: 1,
  };
}

function makeAgentRunCheckpointQueryPayload(): Record<string, unknown> {
  const base = makeAgentRunCheckpointsPayload().data as Array<Record<string, unknown>>;
  return {
    object: "list",
    data: [{ ...base[1], run_status: "completed" }],
    total: 1,
    page: 1,
    limit: 25,
    pages: 1,
  };
}

function makeAgentRunReplayPayload(): Record<string, unknown> {
  return {
    object: "agent_run_replay",
    run_id: "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
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
  };
}

function makeAgentRunTelemetryPayload(): Record<string, unknown> {
  return {
    object: "list",
    run_id: "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
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
  };
}

function makeAgentRunTelemetryQueryPayload(): Record<string, unknown> {
  const base = makeAgentRunTelemetryPayload().data as Array<Record<string, unknown>>;
  return {
    object: "list",
    data: [{ ...base[0], run_id: "8e3c9e2c-b67d-42da-b456-1de39d7289fb", run_status: "completed" }],
    total: 1,
    page: 1,
    limit: 25,
    pages: 1,
  };
}

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
      { name: "Manifest Truth", statement: "No capability is advertised unless it appears in the signed runtime manifest." },
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
      immutability_rule: "Every lineage node is immutable and content-addressed.",
    },
    capability_algebra: {
      required_fields: ["tool_name"],
      enums: {
        side_effect_class: ["read_only", "write_scoped", "write_external", "exec_external", "network_external"],
        risk_level: ["low", "medium", "high", "critical"],
        replayability: ["deterministic", "artifact_backed", "non_replayable"],
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
    typed_failures: [{ code: "replay_mismatch", description: "Replay diverged." }],
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

describe("DecisionEngineClient", () => {
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

  it("fails closed in private profiles without a self-hosted baseUrl", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    process.env.ALGENTA_DISABLE_CLOUD = "1";

    try {
      new DecisionEngineClient({
        apiKey: "de_test_123",
      });
      throw new Error("expected DecisionEngineClient to fail closed");
    } catch (error) {
      expect(String(error)).toContain("private profiles cannot target Algenta-owned cloud URLs");
      expect(String(error)).toContain("ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL");
    }
  });

  it("uses ALGENTA_BASE_URL in private profiles when provided", async () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    process.env.ALGENTA_DISABLE_CLOUD = "1";
    process.env.ALGENTA_BASE_URL = "http://localhost:8000";
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
    });

    await client.query({
      source_name: "orders",
      metric_column: "revenue",
      aggregation: "sum",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/v1/query",
      expect.objectContaining({
        method: "POST",
      }),
    );
  });

  it("uses ALGENTA_API_URL in private profiles when baseUrl env vars are otherwise unset", async () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    process.env.ALGENTA_DISABLE_CLOUD = "1";
    delete process.env.ALGENTA_BASE_URL;
    delete process.env.DE_BASE_URL;
    process.env.ALGENTA_API_URL = "http://localhost:8000";
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
    });

    await client.query({
      source_name: "orders",
      metric_column: "revenue",
      aggregation: "sum",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/v1/query",
      expect.objectContaining({
        method: "POST",
      }),
    );
  });

  it("rejects Algenta-owned baseUrl in private profiles even when passed explicitly", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "air_gapped";
    process.env.ALGENTA_DISABLE_CLOUD = "1";

    expect(
      () =>
        new DecisionEngineClient({
          apiKey: "de_test_123",
          baseUrl: DEFAULT_BASE_URL,
        }),
    ).toThrow("private profiles cannot target Algenta-owned cloud URLs");
  });

  it("uses cloud-managed API key guidance when apiKey is missing", () => {
    expect(
      () =>
        new DecisionEngineClient({
          baseUrl: "https://api.algenta.ai",
        }),
    ).toThrow("https://app.algenta.ai/dashboard/api-keys");
  });

  it("uses self-hosted API key guidance in private profiles when apiKey is missing", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    process.env.ALGENTA_DISABLE_CLOUD = "1";
    process.env.ALGENTA_BASE_URL = "http://localhost:8000";

    try {
      new DecisionEngineClient({
        baseUrl: "http://localhost:8000",
      });
      throw new Error("expected DecisionEngineClient to require an API key");
    } catch (error) {
      expect(String(error)).toContain("ALGENTA_API_KEY / DE_API_KEY environment variables");
      expect(String(error)).toContain(
        "Create a key from your self-hosted admin surface or API base URL: http://localhost:8000",
      );
    }
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
          "X-Algenta-SDK-Version": "algenta-ts/1.0.0",
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

  it("rejects invalid env device ids before sending requests", async () => {
    process.env.ALGENTA_DEVICE_ID = "short";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    expect(
      () =>
        new DecisionEngineClient({
          apiKey: "de_test_123",
          baseUrl: "https://example.test",
          maxRetries: 0,
          timeout: 1_000,
        }),
    ).toThrow("ALGENTA_DEVICE_ID");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("reuses a hosted binding token on later requests from the same client", async () => {
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
      await client.query({
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

  it("reuses a hosted binding token across new clients when disk persistence is unavailable", async () => {
    process.env.ALGENTA_DEVICE_ID = "ts-device-00000001";
    const fsStub = {
      readFileSync: vi.fn(() => {
        throw new Error("binding token file unavailable");
      }),
      existsSync: vi.fn(() => false),
      mkdirSync: vi.fn(() => {
        throw new Error("runtime dir is read only");
      }),
      writeFileSync: vi.fn(() => {
        throw new Error("runtime dir is read only");
      }),
      renameSync: vi.fn(() => {
        throw new Error("runtime dir is read only");
      }),
    };
    const osStub = {
      homedir: vi.fn(() => "/read-only-home"),
    };
    const pathStub = {
      join: (...parts: string[]) => parts.join("/"),
    };
    vi.spyOn(process, "getBuiltinModule").mockImplementation(
      ((name: string): unknown => {
        if (name === "node:fs" || name === "fs") {
          return fsStub;
        }
        if (name === "node:os" || name === "os") {
          return osStub;
        }
        if (name === "node:path" || name === "path") {
          return pathStub;
        }
        return undefined;
      }) as typeof process.getBuiltinModule,
    );
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
              ranked_target_language_count: 250,
              progress_fraction: 3 / 250,
              progress_label: "3 / 250",
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
    expect(capabilities.support_progress.progress_label).toBe("3 / 250");
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

  it("canonicalizes legacy raw connector arrays into paginated results", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "conn_1",
            name: "Warehouse Postgres",
            connector_type: "postgres",
            status: "live",
            visibility: "private",
          },
        ]),
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

    const listed = await client.listConnectors();

    expect(listed.connectors[0]?.id).toBe("conn_1");
    expect(listed.total).toBe(1);
    expect(listed.page).toBe(1);
    expect(listed.limit).toBe(1);
    expect(listed.pages).toBe(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.test/v1/connectors?page=1&limit=200",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("rejects raw connector arrays beyond the first page", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "conn_1",
            name: "Warehouse Postgres",
            connector_type: "postgres",
            status: "live",
            visibility: "private",
          },
        ]),
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

    await expect(client.listConnectors({ page: 2, limit: 50 })).rejects.toThrow(
      "page=2",
    );
  });

  it("supports dataset connect and refresh endpoints through the public API", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            status: "ready",
            dataset_id: "ds_1",
            source_id: "ds_1",
            dataset_name: "warehouse_orders",
            connection_id: "conn_1",
            connection_type: "database",
            provider: "postgres",
            selection: { schema: "public", table: "orders" },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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
            limit: 25,
            pages: 1,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            dataset: {
              dataset_id: "ds_1",
              dataset_name: "warehouse_orders",
              connection_id: "conn_1",
            },
            schema: { fields: ["order_id", "revenue"] },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            status: "ready",
            dataset_id: "ds_1",
            source_id: "ds_1",
            dataset_name: "warehouse_orders",
            schema: { fields: ["order_id", "revenue"] },
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

    const connected = await client.connectData({
      dataset_name: "warehouse_orders",
      connection_id: "conn_1",
      selection: { schema: "public", table: "orders" },
    });
    const datasets = await client.listDatasets({ page: 1, limit: 25 });
    const dataset = await client.getDataset("ds_1");
    const refreshed = await client.refreshDataset("ds_1");

    expect(connected.dataset_id).toBe("ds_1");
    expect(datasets.datasets[0]?.dataset_id).toBe("ds_1");
    expect(dataset.schema.fields).toEqual(["order_id", "revenue"]);
    expect(refreshed.status).toBe("ready");
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://example.test/v1/data/connect",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          dataset_name: "warehouse_orders",
          connection_id: "conn_1",
          selection: { schema: "public", table: "orders" },
        }),
      }),
    );
  });

  it("canonicalizes legacy raw dataset arrays into paginated results", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            dataset_id: "ds_1",
            dataset_name: "warehouse_orders",
            connection_id: "conn_1",
            provider: "postgres",
          },
        ]),
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

    const datasets = await client.listDatasets();

    expect(datasets.datasets[0]?.dataset_id).toBe("ds_1");
    expect(datasets.count).toBe(1);
    expect(datasets.total).toBe(1);
    expect(datasets.page).toBe(1);
    expect(datasets.limit).toBe(1);
    expect(datasets.pages).toBe(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.test/v1/data?page=1&limit=200",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("rejects raw dataset arrays beyond the first page", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            dataset_id: "ds_1",
            dataset_name: "warehouse_orders",
            connection_id: "conn_1",
            provider: "postgres",
          },
        ]),
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

    await expect(client.listDatasets({ page: 2, limit: 50 })).rejects.toThrow(
      "page=2",
    );
  });

  it("supports filtered dataset discovery and dataset summaries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            datasets: [
              {
                dataset_id: "ds_otp",
                dataset_name: "OTP Monthly",
                name: "OTP Monthly",
                status: "ready",
                source_names: ["ops_postgres"],
                column_count: 12,
                registered_at: "2026-05-20T10:00:00Z",
              },
            ],
            count: 1,
            total: 15,
            matched_total: 1,
            page: 2,
            limit: 50,
            pages: 1,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            dataset_id: "ds_otp",
            name: "OTP Monthly",
            status: "ready",
            source_names: ["ops_postgres"],
            row_count: 5000,
            column_count: 12,
            registered_at: "2026-05-20T10:00:00Z",
            query_hints: [{ hint: "otp_rate" }],
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

    const datasets = await client.listDatasets({
      page: 2,
      limit: 50,
      search: "otp",
      status: "ready",
      sourceName: "ops_postgres",
      compact: true,
    });
    const summary = await client.getDatasetSummary("ds_otp");

    expect(datasets.matched_total).toBe(1);
    expect(datasets.datasets[0]?.status).toBe("ready");
    expect(summary.query_hints).toEqual([{ hint: "otp_rate" }]);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://example.test/v1/data?page=2&limit=50&search=otp&status=ready&source_name=ops_postgres&compact=1",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://example.test/v1/data/ds_otp/summary",
      expect.objectContaining({ method: "GET" }),
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

  it("supports governed batch query execution", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          request_id: "req_batch",
          results: [
            {
              key: "overall_otp",
              data: makeQueryResponse({ request_id: "req_1" }),
              metadata: { request_id: "req_1", latency_ms: 12.5 },
            },
            {
              key: "avg_delay",
              error: {
                code: "metric_not_found",
                message: "Metric average_delay_minutes was not found.",
              },
            },
          ],
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

    const response = await client.queryBatch({
      defaults: {
        dataset_id: "otp_events",
        filter: {
          time_filter: "last_year",
          conditions: [{ dimension_hint: "status", op: "eq", value: "closed" }],
        },
        limit: 12,
        order: "desc",
      },
      queries: [
        { key: "overall_otp", request: { metric: { role: "derived_measure", hint: "otp_rate" } } },
        { key: "avg_delay", request: { metric: { role: "base_measure", hint: "average_delay_minutes" } } },
      ],
    });

    expect(response.request_id).toBe("req_batch");
    expect(response.results[0]?.key).toBe("overall_otp");
    expect(response.results[1]?.error?.code).toBe("metric_not_found");
    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.test/v1/query/batch",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          defaults: {
            dataset_id: "otp_events",
            filter: {
              time_filter: "last_year",
              conditions: [{ dimension_hint: "status", op: "eq", value: "closed" }],
            },
            limit: 12,
            order: "desc",
          },
          queries: [
            { key: "overall_otp", request: { metric: { role: "derived_measure", hint: "otp_rate" } } },
            { key: "avg_delay", request: { metric: { role: "base_measure", hint: "average_delay_minutes" } } },
          ],
        }),
      }),
    );
  });

  it("supports read-only SQL reports", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          columns: ["flight_month", "otp_rate_pct"],
          rows: [{ flight_month: "2026-04-01", otp_rate_pct: 92.4 }],
          row_count: 1,
          truncated: false,
          request_id: "req_sql",
          latency_ms: 24.1,
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

    const response = await client.querySqlReport({
      sources: [{ dataset_id: "ds_otp", alias: "otp" }],
      sql: "select flight_month, otp_rate_pct from otp",
      max_rows: 100,
    });

    expect(response.row_count).toBe(1);
    expect(response.columns).toEqual(["flight_month", "otp_rate_pct"]);
    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.test/v1/query/sql-report",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("supports the plan-aligned llm utility routes", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(makeLLMModelsPayload()), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            object: "tokenization",
            model: "text.tokenizer",
            tokenizer_kind: "wordpiece",
            tokens: ["expand", "sales", "coverage"],
            token_count: 3,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            object: "token_count",
            model: "text.tokenizer",
            tokenizer_kind: "wordpiece",
            token_count: 3,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "chatcmpl_123",
            object: "chat.completion",
            model: "text.tokenizer",
            provider_backend: null,
            provider_model_id: null,
            provider_attempts: [],
            choices: [
              {
                index: 0,
                finish_reason: "stop",
                message: { role: "assistant", content: "Deterministic utility response." },
              },
            ],
            usage: { prompt_tokens: 4, completion_tokens: 3, total_tokens: 7 },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "resp_123",
            object: "response",
            status: "completed",
            model: "provider.gpt-4o-mini",
            provider_backend: "openai_compatible",
            provider_model_id: "provider.gpt-4o-mini",
            provider_attempts: [
              {
                provider_backend: "groq",
                provider_model_id: "provider.fast",
                outcome: "failed",
                error_code: "provider_backend_error",
              },
              {
                provider_backend: "openai_compatible",
                provider_model_id: "provider.gpt-4o-mini",
                outcome: "selected",
                error_code: null,
              },
            ],
            output: [
              {
                id: "out_1",
                object: "response.output",
                index: 0,
                provider_backend: "openai_compatible",
                provider_model_id: "provider.gpt-4o-mini",
                provider_attempts: [
                  {
                    provider_backend: "groq",
                    provider_model_id: "provider.fast",
                    outcome: "failed",
                    error_code: "provider_backend_error",
                  },
                  {
                    provider_backend: "openai_compatible",
                    provider_model_id: "provider.gpt-4o-mini",
                    outcome: "selected",
                    error_code: null,
                  },
                ],
                content: [
                  {
                    type: "text",
                    text: "Provider response.",
                    token_count: 3,
                    embedding: null,
                  },
                ],
              },
            ],
            usage: { prompt_tokens: 7, total_tokens: 7 },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            object: "embedding_similarity",
            model: "embeddings.cosine_similarity",
            similarity_metric: "cosine",
            score: 0.94,
            dimension: 3,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(makeDecisionPlanPayload()), {
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

    const models = await client.listModels();
    const artifact = await client.resolveArtifactBridge({
      repo_id: "org/model",
      filename: "model.safetensors",
      revision: "main",
    });
    const tokenized = await client.tokenize({ input: "expand sales coverage" });
    const counted = await client.countTokens({ input: "expand sales coverage" });
    const chat = await client.chatCompletions({
      messages: [{ role: "user", content: "Summarize" }],
    });
    const response = await client.responses({
      model: "provider.gpt-4o-mini",
      input: ["expand sales coverage"],
      dimensions: 3,
    });
    const embeddings = await client.embeddings({
      input: "expand sales coverage",
      dimensions: 3,
    });
    const similarity = await client.embeddingSimilarity({
      left: [0.1, 0.2, 0.3],
      right: [0.1, 0.2, 0.3],
    });
    const reranked = await client.rerank({
      query_embedding: [0.1, 0.2, 0.3],
      documents: [{ id: "doc-1", embedding: [0.1, 0.2, 0.3], text: "Top document" }],
      top_n: 1,
    });
    const plan = await client.planDecision({
      mode: "auto",
      scenario: {
        variables: { revenue: { low: 1, high: 2 } },
        objective: "maximize_score",
      },
    });

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
    expect(tokenized.token_count).toBe(3);
    expect(counted.token_count).toBe(3);
    expect(chat.choices[0]?.message.content).toBe("Deterministic utility response.");
    expect(chat.provider_backend).toBeNull();
    expect(chat.provider_model_id).toBeNull();
    expect(chat.provider_attempts).toEqual([]);
    expect(response.provider_backend).toBe("openai_compatible");
    expect(response.provider_model_id).toBe("provider.gpt-4o-mini");
    expect(response.provider_attempts[0]?.provider_backend).toBe("groq");
    expect(response.provider_attempts[1]?.outcome).toBe("selected");
    expect(response.output[0]?.provider_backend).toBe("openai_compatible");
    expect(response.output[0]?.provider_model_id).toBe("provider.gpt-4o-mini");
    expect(response.output[0]?.provider_attempts).toHaveLength(2);
    expect(response.output[0]?.provider_attempts[1]?.provider_model_id).toBe("provider.gpt-4o-mini");
    expect(response.output[0]?.content[0]?.type).toBe("text");
    expect(response.output[0]?.content[0]?.embedding).toBeNull();
    expect(embeddings.dimensions).toBe(3);
    expect(embeddings.provider_backend).toBeNull();
    expect(embeddings.provider_model_id).toBeNull();
    expect(embeddings.provider_attempts).toEqual([]);
    expect(similarity.score).toBe(0.94);
    expect(reranked.data[0]?.rank).toBe(1);
    expect(plan.options[0]?.rank).toBe(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("https://example.test/v1/models");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("https://example.test/v1/artifacts/resolve");
    expect(fetchMock.mock.calls[9]?.[0]).toBe("https://example.test/v1/decisions/plan");
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
    expect(contract.mcp_endpoint).toBe("https://example.test/self-host/mcp/sse");
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

  it("rejects an invalid OpenAPI contract fallback payload", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ error: { code: "not_found", message: "missing" } }),
          { status: 404, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ openapi: "3.1.0" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const client = new DecisionEngineClient({
      apiKey: "de_test_123",
      baseUrl: "https://example.test/self-host",
      maxRetries: 0,
      timeout: 1_000,
    });

    const contractPromise = client.getContract();

    await expect(contractPromise).rejects.toMatchObject({
      errorCode: "contract_extension_missing",
    });
    await expect(contractPromise).rejects.toThrow("x-primary-data-query-contract");
  });

  it("rejects an OpenAPI contract fallback payload with no api section", async () => {
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

    const contractPromise = client.getContract();

    await expect(contractPromise).rejects.toMatchObject({
      errorCode: "invalid_contract_payload",
    });
    await expect(contractPromise).rejects.toThrow("api contract section");
  });

  it("rejects an OpenAPI contract fallback payload with no api.contract_endpoint", async () => {
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
              api: { query_batch_endpoint: "/v1/query/batch" },
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

    const contractPromise = client.getContract();

    await expect(contractPromise).rejects.toMatchObject({
      errorCode: "invalid_contract_payload",
    });
    await expect(contractPromise).rejects.toThrow("api.contract_endpoint");
  });

  it("rejects an OpenAPI contract fallback payload with an invalid nested primary-data contract section", async () => {
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
              api: { contract_endpoint: "/v1/meta/contract" },
              mcp: { contract_tool: "get_contract" },
              runtime_sdk: {
                typescript: { runtime_class: null },
              },
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

    const contractPromise = client.getContract();

    await expect(contractPromise).rejects.toMatchObject({
      errorCode: "invalid_contract_payload",
    });
    await expect(contractPromise).rejects.toThrow("runtime_sdk.typescript.runtime_class");
  });

  it("rejects an invalid contract payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify(
          makeContractPayload({
            primary_data_query_contract: {
              api: { contract_endpoint: "/v1/meta/contract" },
            },
          }),
        ),
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

    const contractPromise = client.getContract();

    await expect(contractPromise).rejects.toMatchObject({
      errorCode: "invalid_contract_payload",
    });
    await expect(contractPromise).rejects.toThrow("invalid payload");
  });

  it("rejects a contract payload with an invalid nested primary-data contract section", async () => {
    const payload = makeContractPayload();
    (payload.primary_data_query_contract as Record<string, unknown>).runtime_sdk = {
      python: cloneJsonValue(PRIMARY_DATA_QUERY_CONTRACT.runtime_sdk.python),
      typescript: {
        ...cloneJsonValue(PRIMARY_DATA_QUERY_CONTRACT.runtime_sdk.typescript),
        runtime_class: null,
      },
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const contractPromise = client.getContract();

    await expect(contractPromise).rejects.toMatchObject({
      errorCode: "invalid_contract_payload",
    });
    await expect(contractPromise).rejects.toThrow("runtime_sdk.typescript.runtime_class");

    await contractPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain(
        "primary_data_query_contract.runtime_sdk.typescript.runtime_class",
      );
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "primary_data_query_contract.runtime_sdk.typescript.runtime_class",
      });
      expect((error as DecisionEngineError).fieldErrors[0]).toMatchObject({
        path: "primary_data_query_contract.runtime_sdk.typescript.runtime_class",
      });
    });
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
              compiled_artifact: "mojo_build/simulate",
              compiled_engine: "mojo",
              max_cold_ms: 12.0,
              max_warm_ms: 4.0,
              max_hot_ms: 2.0,
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

  it("rejects a runtime manifest payload with an invalid kernel promotion status", async () => {
    const payload = makeRuntimeManifestPayload();
    ((payload.modules as Array<Record<string, unknown>>)[0] as Record<string, unknown>).promotion_status =
      "graduated";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const manifestPromise = client.getRuntimeManifest();

    await expect(manifestPromise).rejects.toMatchObject({
      errorCode: "invalid_runtime_contract_payload",
    });
    await expect(manifestPromise).rejects.toThrow("response.modules[0].promotion_status");
  });

  it("rejects a runtime manifest payload with a missing shipping replay proof ref", async () => {
    const payload = makeRuntimeManifestPayload();
    delete ((payload.modules as Array<Record<string, unknown>>)[0] as Record<string, unknown>)
      .replay_proof_ref;
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const manifestPromise = client.getRuntimeManifest();

    await expect(manifestPromise).rejects.toMatchObject({
      errorCode: "invalid_runtime_contract_payload",
    });
    await expect(manifestPromise).rejects.toThrow("response.modules[0].replay_proof_ref");
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

  it("rejects invalid signed runtime manifest payloads", async () => {
    const manifest = makeRuntimeManifestPayload();
    (manifest.maturity as Record<string, unknown>).bpe_tokenizer = "legendary";

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(manifest), {
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

    const manifestPromise = client.getRuntimeManifest();

    await expect(manifestPromise).rejects.toThrow("invalid signed payload");
    await manifestPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("maturity.bpe_tokenizer");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "maturity.bpe_tokenizer",
      });
      expect((error as DecisionEngineError).fieldErrors[0]).toMatchObject({
        path: "maturity.bpe_tokenizer",
      });
    });
  });

  it("rejects runtime manifest artifact kind drift", async () => {
    const manifest = makeRuntimeManifestPayload();
    (manifest.compiled_artifacts as Array<Record<string, unknown>>)[0]!.kind =
      "ghost_bundle";

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(manifest), {
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

    const manifestPromise = client.getRuntimeManifest();

    await expect(manifestPromise).rejects.toThrow("invalid signed payload");
    await manifestPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("compiled_artifacts.0.kind");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "compiled_artifacts.0.kind",
      });
      expect((error as DecisionEngineError).fieldErrors[0]).toMatchObject({
        path: "compiled_artifacts.0.kind",
      });
    });
  });

  it("rejects duplicate runtime manifest release conditions", async () => {
    const manifest = makeRuntimeManifestPayload();
    (manifest.formal_release_theorem.required_conditions as Array<string>).push(
      "manifest-listed",
    );

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(manifest), {
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

    const manifestPromise = client.getRuntimeManifest();

    await expect(manifestPromise).rejects.toThrow("invalid signed payload");
    await manifestPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("formal_release_theorem.required_conditions");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "formal_release_theorem.required_conditions",
      });
    });
  });

  it("rejects duplicate runtime manifest module public channels", async () => {
    const manifest = makeRuntimeManifestPayload();
    (
      (manifest.modules as Array<Record<string, unknown>>)[0]!
        .public_supported_channels as Array<string>
    ).push("python_sdk");

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(manifest), {
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

    const manifestPromise = client.getRuntimeManifest();

    await expect(manifestPromise).rejects.toThrow("invalid signed payload");
    await manifestPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("modules.0.public_supported_channels");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "modules.0.public_supported_channels",
      });
    });
  });

  it("rejects duplicate runtime manifest module functions", async () => {
    const manifest = makeRuntimeManifestPayload();
    (
      (manifest.modules as Array<Record<string, unknown>>)[0]!.functions as Array<string>
    ).push(
      ((manifest.modules as Array<Record<string, unknown>>)[0]!.functions as Array<string>)[0]!,
    );

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(manifest), {
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

    const manifestPromise = client.getRuntimeManifest();

    await expect(manifestPromise).rejects.toThrow("invalid signed payload");
    await manifestPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("modules.0.functions");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "modules.0.functions",
      });
    });
  });

  it("rejects runtime manifest benchmark shipping function count drift", async () => {
    const manifest = makeRuntimeManifestPayload();
    (manifest.benchmark_discovery_lane as Record<string, unknown>).shipping_manifest_functions =
      999;

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(manifest), {
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

    const manifestPromise = client.getRuntimeManifest();

    await expect(manifestPromise).rejects.toThrow("invalid signed payload");
    await manifestPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("benchmark_discovery_lane.shipping_manifest_functions");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "benchmark_discovery_lane.shipping_manifest_functions",
      });
    });
  });

  it("rejects invalid runtime benchmark discovery rules in the manifest", async () => {
    const manifest = makeRuntimeManifestPayload();
    (manifest.shipping_contract as Record<string, unknown>).benchmark_discovery_rule =
      "shadow_runtime_contract";

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(manifest), {
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

    const manifestPromise = client.getRuntimeManifest();

    await expect(manifestPromise).rejects.toThrow("invalid signed payload");
    await manifestPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("shipping_contract.benchmark_discovery_rule");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "shipping_contract.benchmark_discovery_rule",
      });
    });
  });

  it("rejects invalid signed runtime admin module payloads", async () => {
    const payload = makeRuntimeAdminModulesPayload();
    (payload.proof_matrix as Array<Record<string, unknown>>)[0]!.status = "unknown_status";

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const modulesPromise = client.getRuntimeModules();

    await expect(modulesPromise).rejects.toThrow("invalid signed payload");
    await modulesPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("proof_matrix.0.status");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "proof_matrix.0.status",
      });
    });
  });

  it("rejects invalid runtime benchmark discovery rules in admin modules", async () => {
    const payload = makeRuntimeAdminModulesPayload();
    (payload.shipping_contract as Record<string, unknown>).benchmark_discovery_rule =
      "shadow_runtime_contract";

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const modulesPromise = client.getRuntimeModules();

    await expect(modulesPromise).rejects.toThrow("invalid signed payload");
    await modulesPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("shipping_contract.benchmark_discovery_rule");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "shipping_contract.benchmark_discovery_rule",
      });
    });
  });

  it("rejects duplicate runtime admin proof matrix layers", async () => {
    const payload = makeRuntimeAdminModulesPayload();
    (payload.proof_matrix as Array<Record<string, unknown>>).push({
      ...(payload.proof_matrix as Array<Record<string, unknown>>)[0]!,
    });

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const modulesPromise = client.getRuntimeModules();

    await expect(modulesPromise).rejects.toThrow("invalid signed payload");
    await modulesPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("proof_matrix");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "proof_matrix",
      });
    });
  });

  it("rejects runtime admin summary function count drift", async () => {
    const payload = makeRuntimeAdminModulesPayload();
    (payload.summary as Record<string, unknown>).function_count = 999;

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const modulesPromise = client.getRuntimeModules();

    await expect(modulesPromise).rejects.toThrow("invalid signed payload");
    await modulesPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("summary.function_count");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "summary.function_count",
      });
    });
  });

  it("rejects invalid signed runtime benchmark payloads", async () => {
    const payload = makeRuntimeAdminBenchmarksPayload();
    (payload.module_benchmarks as Array<Record<string, unknown>>)[0]!.compiled_engine =
      "warp_core";

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const benchmarksPromise = client.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
    await benchmarksPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("module_benchmarks.0.compiled_engine");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "module_benchmarks.0.compiled_engine",
      });
    });
  });

  it("rejects invalid runtime SLO budget applies_to values", async () => {
    const payload = makeRuntimeAdminBenchmarksPayload();
    (payload.slo_budgets as Array<Record<string, unknown>>)[0]!.applies_to = "shadow_realm_lane";

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const benchmarksPromise = client.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
    await benchmarksPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("slo_budgets.0.applies_to");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "slo_budgets.0.applies_to",
      });
    });
  });

  it("rejects invalid runtime non-shipping rules in admin benchmarks", async () => {
    const payload = makeRuntimeAdminBenchmarksPayload();
    (payload.benchmark_discovery_lane as Record<string, unknown>).non_shipping_rule =
      "shadow_inventory_lane";

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const benchmarksPromise = client.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
    await benchmarksPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("benchmark_discovery_lane.non_shipping_rule");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "benchmark_discovery_lane.non_shipping_rule",
      });
    });
  });

  it("rejects duplicate runtime benchmark classes", async () => {
    const payload = makeRuntimeAdminBenchmarksPayload();
    (payload.benchmarking.classes as Array<Record<string, unknown>>).push({
      ...(payload.benchmarking.classes as Array<Record<string, unknown>>)[0]!,
    });

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const benchmarksPromise = client.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
    await benchmarksPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("benchmarking.classes");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "benchmarking.classes",
      });
    });
  });

  it("rejects duplicate runtime benchmark compiled artifacts", async () => {
    const payload = makeRuntimeAdminBenchmarksPayload();
    (payload.compiled_artifacts as Array<Record<string, unknown>>).push({
      ...(payload.compiled_artifacts as Array<Record<string, unknown>>)[0]!,
    });

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const benchmarksPromise = client.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
    await benchmarksPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("compiled_artifacts");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "compiled_artifacts",
      });
    });
  });

  it("rejects runtime benchmark shipping module count drift", async () => {
    const payload = makeRuntimeAdminBenchmarksPayload();
    (payload.benchmark_discovery_lane as Record<string, unknown>).shipping_manifest_modules = 2;

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const benchmarksPromise = client.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
    await benchmarksPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("benchmark_discovery_lane.shipping_manifest_modules");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "benchmark_discovery_lane.shipping_manifest_modules",
      });
    });
  });

  it("rejects runtime benchmark shipping function count drift", async () => {
    const payload = makeRuntimeAdminBenchmarksPayload();
    (payload.shipping_runtime_function_counts as Array<number>)[0] = 3;

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const benchmarksPromise = client.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
    await benchmarksPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("shipping_runtime_function_counts.0");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "shipping_runtime_function_counts.0",
      });
    });
  });

  it("rejects runtime benchmark shipping speedup drift", async () => {
    const payload = makeRuntimeAdminBenchmarksPayload();
    (payload.shipping_runtime_benchmark_speedups_x as Array<number>)[0] = 999;

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const benchmarksPromise = client.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
    await benchmarksPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("shipping_runtime_benchmark_speedups_x.0");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "shipping_runtime_benchmark_speedups_x.0",
      });
    });
  });

  it("rejects non-positive runtime benchmark speedup metrics", async () => {
    const payload = makeRuntimeAdminBenchmarksPayload();
    (payload.shipping_runtime_benchmark_speedups_x as Array<number>)[0] = 0;
    (payload.module_benchmarks as Array<Record<string, unknown>>)[0]!.benchmark_speedup_x = 0;

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const benchmarksPromise = client.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
    await benchmarksPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("module_benchmarks.0.benchmark_speedup_x");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "module_benchmarks.0.benchmark_speedup_x",
      });
    });
  });

  it("rejects runtime benchmark shipping module identity drift", async () => {
    const payload = makeRuntimeAdminBenchmarksPayload();
    (payload.shipping_runtime_modules as Array<string>)[0] = "embeddings";

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const benchmarksPromise = client.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
    await benchmarksPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("shipping_runtime_modules.0");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "shipping_runtime_modules.0",
      });
    });
  });

  it("rejects runtime benchmark shipping artifact drift", async () => {
    const payload = makeRuntimeAdminBenchmarksPayload();
    (payload.shipping_runtime_benchmark_artifacts as Array<string>)[0] =
      "benchmarks/results/embeddings.json";

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const benchmarksPromise = client.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
    await benchmarksPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("shipping_runtime_benchmark_artifacts.0");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "shipping_runtime_benchmark_artifacts.0",
      });
    });
  });

  it("rejects runtime benchmark shipping compiled artifact drift", async () => {
    const payload = makeRuntimeAdminBenchmarksPayload();
    (payload.shipping_runtime_compiled_artifacts as Array<string>)[0] =
      "mojo_build/embeddings";

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const benchmarksPromise = client.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
    await benchmarksPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("shipping_runtime_compiled_artifacts.0");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "shipping_runtime_compiled_artifacts.0",
      });
    });
  });

  it("rejects runtime benchmark shipping compiled engine drift", async () => {
    const payload = makeRuntimeAdminBenchmarksPayload();
    (payload.shipping_runtime_compiled_engines as Array<string>)[0] = "python_fallback";

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const benchmarksPromise = client.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
    await benchmarksPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("shipping_runtime_compiled_engines.0");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "shipping_runtime_compiled_engines.0",
      });
    });
  });

  it.each([
    ["shipping_runtime_max_cold_ms", "max_cold_ms", 999],
    ["shipping_runtime_max_warm_ms", "max_warm_ms", 999],
    ["shipping_runtime_max_hot_ms", "max_hot_ms", 999],
  ])(
    "rejects runtime benchmark %s drift",
    async (shippingField, _benchmarkField, badValue) => {
      const payload = makeRuntimeAdminBenchmarksPayload();
      (payload[shippingField] as Array<number>)[0] = badValue;

      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
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

      const benchmarksPromise = client.getRuntimeBenchmarks();

      await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
      await benchmarksPromise.catch(error => {
        expect(error).toBeInstanceOf(DecisionEngineError);
        const details = (error as DecisionEngineError).details as Record<string, unknown>;
        expect(String(details.cause)).toContain(`${shippingField}.0`);
        expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
          path: `${shippingField}.0`,
        });
      });
    },
  );

  it("rejects runtime benchmark compiled artifact reference drift", async () => {
    const payload = makeRuntimeAdminBenchmarksPayload();
    (payload.module_benchmarks as Array<Record<string, unknown>>)[0]!.compiled_artifact =
      "build/missing-runtime-benchmark.json";
    (payload.shipping_runtime_compiled_artifacts as Array<string>)[0] =
      "build/missing-runtime-benchmark.json";

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const benchmarksPromise = client.getRuntimeBenchmarks();

    await expect(benchmarksPromise).rejects.toThrow("invalid signed payload");
    await benchmarksPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("module_benchmarks.0.compiled_artifact");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "module_benchmarks.0.compiled_artifact",
      });
    });
  });

  it("rejects invalid signed runtime release validation payloads", async () => {
    const payload = makeRuntimeReleaseValidationPayload();
    (payload.conditions as Array<Record<string, unknown>>)[0]!.condition = "teleport-validated";

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const validationPromise = client.getRuntimeReleaseValidation();

    await expect(validationPromise).rejects.toThrow("invalid signed payload");
    await validationPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("conditions.0.condition");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "conditions.0.condition",
      });
    });
  });

  it("rejects duplicate runtime release validation evidence paths", async () => {
    const payload = makeRuntimeReleaseValidationPayload();
    (
      (payload.conditions as Array<Record<string, unknown>>)[0]!.evidence_paths as Array<string>
    ).push(
      (
        (payload.conditions as Array<Record<string, unknown>>)[0]!
          .evidence_paths as Array<string>
      )[0]!,
    );

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
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

    const validationPromise = client.getRuntimeReleaseValidation();

    await expect(validationPromise).rejects.toThrow("invalid signed payload");
    await validationPromise.catch(error => {
      expect(error).toBeInstanceOf(DecisionEngineError);
      const details = (error as DecisionEngineError).details as Record<string, unknown>;
      expect(String(details.cause)).toContain("conditions.0.evidence_paths");
      expect((error as DecisionEngineError).validationErrors[0]).toMatchObject({
        path: "conditions.0.evidence_paths",
      });
    });
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

  it("supports typed account usage and limits helpers", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            org_id: "org_123",
            email: "owner@example.com",
            organization: "Algenta Labs",
            plan: "enterprise",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            org_id: "org_123",
            billing_period: "2026-05",
            simulations_run: 120,
            api_calls: 340,
            quota_limit: 1000,
            quota_used_pct: 12,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            plan: "enterprise",
            stripe_customer_id: "cus_123",
            subscription_status: "active",
            current_period_end: "2026-06-30T00:00:00Z",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            url: "https://billing.example/checkout/session_123",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            url: "https://billing.example/portal/session_123",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            plan: "enterprise",
            max_simulations_per_month: 100000,
            max_runs_per_simulation: 1000000,
            max_batch_items: 100,
            rate_limit_per_minute: 10000,
            async_jobs_enabled: true,
            webhooks_enabled: true,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              name: "normal",
              description: "Normal distribution.",
              required_params: ["mean", "std"],
              optional_params: [],
              example: { mean: 100, std: 12 },
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "product-launch",
              name: "Product Launch Decision",
              category: "business",
              description: "Compare launch scenarios.",
              example_request: { mode: "auto" },
            },
          ]),
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

    const me = await client.me();
    const usage = await client.usage();
    const billingInfo = await client.getBillingInfo();
    const checkout = await client.createBillingCheckout({ plan: "pro" });
    const portal = await client.createBillingPortal();
    const limits = await client.limits();
    const distributions = await client.distributions();
    const templates = await client.templates();

    expect(me.organization).toBe("Algenta Labs");
    expect(usage.billing_period).toBe("2026-05");
    expect(usage.simulations_run).toBe(120);
    expect(billingInfo.plan).toBe("enterprise");
    expect(billingInfo.stripe_customer_id).toBe("cus_123");
    expect(checkout.url).toContain("/checkout/");
    expect(portal.url).toContain("/portal/");
    expect(limits.plan).toBe("enterprise");
    expect(limits.simulations_per_month).toBe(100000);
    expect(limits.max_simulations_per_month).toBe(100000);
    expect(limits.max_runs_per_simulation).toBe(1000000);
    expect(limits.max_batch_items).toBe(100);
    expect(limits.jobs_enabled).toBe(true);
    expect(limits.async_jobs_enabled).toBe(true);
    expect(limits.webhooks_enabled).toBe(true);
    expect(distributions.distributions[0]?.name).toBe("normal");
    expect(templates.templates[0]?.id).toBe("product-launch");
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://example.test/v1/me",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://example.test/v1/usage",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "https://example.test/v1/billing/info",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "https://example.test/v1/billing/checkout",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ plan: "pro" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "https://example.test/v1/billing/portal",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({}),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      "https://example.test/v1/limits",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      7,
      "https://example.test/v1/distributions",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      8,
      "https://example.test/v1/templates",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("supports typed team, audit log, and execution policy helpers", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              user_id: "user_123",
              name: "Owner",
              email: "owner@example.com",
              role: "owner",
              status: "active",
              last_active: "2026-05-24T12:00:00Z",
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            message: "Invitation sent.",
            invite_id: "invite_123",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            message: "Role updated.",
            user_id: "user_123",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({}), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            entries: [
              {
                id: "audit_123",
                timestamp: "2026-05-24T12:00:00Z",
                actor_email: "owner@example.com",
                action: "policy_update",
                resource_type: "execution_policy",
                resource_id: "org_123",
                ip_address: "203.0.113.10",
                result: "success",
                metadata: {
                  policy_snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
                  schema_revision: "execution-policy-v1",
                },
              },
            ],
            total: 1,
            page: 1,
            limit: 20,
            pages: 1,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            entries: [
              {
                id: "audit_456",
                timestamp: "2026-05-24T12:01:00Z",
                actor_email: "owner@example.com",
                action: "policy_update",
                resource_type: "execution_policy",
                resource_id: "org_123",
                ip_address: "203.0.113.10",
                result: "success",
                metadata: {
                  policy_snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
                  schema_snapshot_id: "schema-v1",
                  manifest_version: "runtime-manifest-v1",
                  request_hash: "hash_123",
                },
              },
            ],
            total: 1,
            page: 2,
            limit: 10,
            pages: 1,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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

    const team = await client.listTeamMembers({ page: 1, limit: 50 });
    const invited = await client.inviteTeamMember({ email: "new@example.com", role: "admin" });
    const roleUpdated = await client.updateTeamMemberRole("user_123", "viewer");
    const removed = await client.removeTeamMember("user_123");
    const logs = await client.getAuditLogs({ page: 1, limit: 20 });
    const filteredLogs = await client.getAuditLogs({
      page: 2,
      limit: 10,
      actor_email: "owner@example.com",
      action: "policy_update",
      resource_type: "execution_policy",
      result: "success",
      policy_snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
      schema_snapshot_id: "schema-v1",
      manifest_version: "runtime-manifest-v1",
      request_hash: "hash_123",
    });
    const artifacts = await client.getAuditLogArtifacts({
      page: 1,
      limit: 5,
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
    const policy = await client.getExecutionPolicy();
    const snapshots = await client.listExecutionPolicySnapshots();
    const updated = await client.updateExecutionPolicy({
      min_confidence: 0.85,
      allow_reexecution: true,
    });

    expect(team.members[0]?.email).toBe("owner@example.com");
    expect(team.total).toBe(1);
    expect(invited.invite_id).toBe("invite_123");
    expect(roleUpdated.user_id).toBe("user_123");
    expect(removed).toEqual({ removed: true, user_id: "user_123" });
    expect(logs.entries[0]?.action).toBe("policy_update");
    expect(logs.entries[0]?.metadata?.["policy_snapshot_id"]).toBe(
      "execution-policy-v1-r2:abcd1234abcd1234",
    );
    expect(filteredLogs.entries[0]?.metadata?.["manifest_version"]).toBe("runtime-manifest-v1");
    expect(artifacts.entries[0]?.content_hash).toBe("content_hash_1");
    expect(policy.min_confidence).toBe(0.7);
    expect(policy.snapshot_id).toBe("execution-policy-v1-r2:abcd1234abcd1234");
    expect(snapshots.total_snapshots).toBe(1);
    expect(updated.allow_reexecution).toBe(true);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://example.test/v1/team?page=1&limit=50",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://example.test/v1/team/invite",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ email: "new@example.com", role: "admin" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "https://example.test/v1/team/user_123/role",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ role: "viewer" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "https://example.test/v1/team/user_123",
      expect.objectContaining({ method: "DELETE" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "https://example.test/v1/audit-logs?page=1&limit=20",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      "https://example.test/v1/audit-logs?page=2&limit=10&actor_email=owner%40example.com&action=policy_update&resource_type=execution_policy&result=success&policy_snapshot_id=execution-policy-v1-r2%3Aabcd1234abcd1234&schema_snapshot_id=schema-v1&manifest_version=runtime-manifest-v1&request_hash=hash_123",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      7,
      "https://example.test/v1/audit-logs/artifacts?page=1&limit=5&actor_email=owner%40example.com&action=policy_update&resource_type=execution_policy&result=success&policy_snapshot_id=execution-policy-v1-r2%3Aabcd1234abcd1234&schema_snapshot_id=schema-v1&manifest_version=runtime-manifest-v1&request_hash=hash_123&content_hash=content_hash_1",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      8,
      "https://example.test/v1/execution/policy",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      9,
      "https://example.test/v1/execution/policy/snapshots",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      10,
      "https://example.test/v1/execution/policy",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ min_confidence: 0.85, allow_reexecution: true }),
      }),
    );
  });

  it("supports typed account update helpers", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
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

    const me = await client.updateMe({ name: " Mission Ops ", org_name: "Mission Control" });

    expect(me.user.name).toBe("Mission Ops");
    expect(me.org.slug).toBe("mission-control");
    expect(me.organization).toBe("Mission Control");
    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.test/v1/me",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ name: "Mission Ops", org_name: "Mission Control" }),
      }),
    );
  });

  it("supports typed device list and revoke helpers", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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
              heartbeat_count: 3,
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
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ revoked: true, registration_id: "reg_123" }),
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

    const listed = await client.listDevices({ page: 1, limit: 25 });
    const revoked = await client.revokeDevice("reg_123");

    expect(listed.page).toBe(1);
    expect(listed.limit).toBe(25);
    expect(listed.device_limit).toBe(2);
    expect(listed.devices[0]?.device_id).toBe("device_12...");
    expect(listed.devices[0]?.api_key_label).toBe("Primary SDK Key");
    expect(revoked).toEqual({ revoked: true, registration_id: "reg_123" });
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://example.test/v1/device/list?page=1&limit=25",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://example.test/v1/device/reg_123",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("supports typed metering ingest helpers", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          accepted: 2,
          billing_period: "2026-05",
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

    const metering = await client.ingestMeteringEvents({
      device_id: "device_sdk_123",
      events: [
        { event_type: "query", latency_ms: 9.5, success: true },
        { module: "pricing", timestamp: 1716547200 },
      ],
    });

    expect(metering.accepted).toBe(2);
    expect(metering.billing_period).toBe("2026-05");
    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.test/v1/metering",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          device_id: "device_sdk_123",
          events: [
            { event_type: "query", latency_ms: 9.5, success: true },
            { module: "pricing", timestamp: 1716547200 },
          ],
        }),
      }),
    );
  });

  it("supports typed credit refresh helpers", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          credits_granted: 10000,
          credits_issued_this_month: 25000,
          monthly_limit: 500000,
          monthly_remaining: 475000,
          billing_period: "2026-05",
          expires_at: 1716547200,
          refresh_after: 1716545040,
          server_time: 1716460800,
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

    const refreshed = await client.refreshCredits({
      device_id: "device_sdk_123",
      billing_period: "2026-05",
      credits_used: 42,
    });

    expect(refreshed.credits_granted).toBe(10000);
    expect(refreshed.monthly_remaining).toBe(475000);
    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.test/v1/credits/refresh",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          device_id: "device_sdk_123",
          billing_period: "2026-05",
          credits_used: 42,
        }),
      }),
    );
  });

  it("supports typed async job helpers", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            job_id: "11111111-1111-1111-1111-111111111111",
            poll_url: "https://example.test/v1/jobs/11111111-1111-1111-1111-111111111111",
            status: "queued",
          }),
          { status: 202, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            job_id: "11111111-1111-1111-1111-111111111111",
            run_id: "22222222-2222-2222-2222-222222222222",
            org_id: "33333333-3333-3333-3333-333333333333",
            status: "queued",
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
            result: { score: 0.98 },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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
                poll_url: "https://example.test/v1/jobs/11111111-1111-1111-1111-111111111111",
              },
            ],
            total: 1,
            page: 2,
            limit: 10,
            pages: 1,
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
            status: "cancelled",
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
            success: true,
            status_code: 200,
            message: "delivered",
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

    const submitted = await client.submitJob(
      {
        mode: "expert",
        runs: 100,
        simulation: {
          variables: [{ name: "outcome", distribution: "fixed", params: { value: 100 } }],
          objective_function: "outcome",
        },
      },
      "https://example.test/webhook",
    );
    const status = await client.getJob("11111111-1111-1111-1111-111111111111");
    const result = await client.getJobResult("11111111-1111-1111-1111-111111111111");
    const listed = await client.listJobs({ page: 2, limit: 10, status: "queued" });
    const cancelled = await client.cancelJob("11111111-1111-1111-1111-111111111111");
    const webhook = await client.testWebhookDelivery("https://example.test/webhook");

    expect(submitted.job_id).toBe("11111111-1111-1111-1111-111111111111");
    expect(submitted.status).toBe("queued");
    expect(status.status).toBe("queued");
    expect(result.result).toEqual({ score: 0.98 });
    expect(listed.total).toBe(1);
    expect(listed.page).toBe(2);
    expect(listed.jobs[0]?.queue_name).toBe("default");
    expect(cancelled.status).toBe("cancelled");
    expect(webhook.status_code).toBe(200);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://example.test/v1/jobs",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          request: {
            mode: "expert",
            runs: 100,
            simulation: {
              variables: [{ name: "outcome", distribution: "fixed", params: { value: 100 } }],
              objective_function: "outcome",
            },
          },
          callback_url: "https://example.test/webhook",
        }),
      }),
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
    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.test/v1/jobs/list?page=2&limit=10&status=queued",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "https://example.test/v1/jobs/11111111-1111-1111-1111-111111111111/cancel",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      "https://example.test/v1/webhooks/test",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ callback_url: "https://example.test/webhook" }),
      }),
    );
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

  it("fails fast when pollJob reaches a terminal failed status", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          job_id: "11111111-1111-1111-1111-111111111111",
          run_id: "22222222-2222-2222-2222-222222222222",
          org_id: "33333333-3333-3333-3333-333333333333",
          status: "failed",
          queue_name: "default",
          retry_count: 0,
          callback_status: "pending",
          created_at: "2026-05-24T12:00:00Z",
          error_message: "worker crashed",
          poll_url: "https://example.test/v1/jobs/11111111-1111-1111-1111-111111111111",
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

    await expect(
      client.pollJob("11111111-1111-1111-1111-111111111111", {
        timeoutMs: 1_000,
        pollIntervalMs: 50,
      }),
    ).rejects.toThrow("worker crashed");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("fails with a typed timeout when pollJob does not complete in time", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
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
      timeoutMs: 60,
      pollIntervalMs: 25,
    });
    const assertion = expect(pollPromise).rejects.toThrow("timed out after 60ms");
    await vi.advanceTimersByTimeAsync(75);
    await assertion;
    expect(fetchMock).toHaveBeenCalledTimes(3);
    vi.useRealTimers();
  });

  it("supports the full trigger lifecycle surface", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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
            description: "Watch for monthly revenue spikes.",
            webhook_url: "https://example.test/hook",
            execution_webhook_url: "https://example.test/execute",
            auto_execute: true,
            created_at: "2026-05-24T12:00:00Z",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ trigger_id: "trigger_123", status: "paused" }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    const client = new DecisionEngineClient({
      apiKey: "de_test_123",
      baseUrl: "https://example.test",
      maxRetries: 0,
      timeout: 1_000,
    });

    const created = await client.registerTrigger({
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
    const listed = await client.listTriggers({ status: "paused", page: 2, limit: 10 });
    const fired = await client.fireTrigger("trigger_123", { force: true });
    const paused = await client.pauseTrigger("trigger_123", { paused: true });
    const deleted = await client.deleteTrigger("trigger_123");

    expect(created.trigger_id).toBe("trigger_123");
    expect(listed.total).toBe(1);
    expect(listed.triggers[0]?.status).toBe("paused");
    expect(fired.simulation_run_id).toBe("run_123");
    expect(paused.status).toBe("paused");
    expect(deleted).toEqual({ trigger_id: "trigger_123", deleted: true });
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://example.test/v1/triggers",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://example.test/v1/triggers?status=paused&page=2&limit=10",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "https://example.test/v1/triggers/trigger_123/fire",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "https://example.test/v1/triggers/trigger_123/pause?paused=true",
      expect.objectContaining({ method: "PATCH" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "https://example.test/v1/triggers/trigger_123",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("rejects invalid execution policy update input before sending the request", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const client = new DecisionEngineClient({
      apiKey: "de_test_123",
      baseUrl: "https://example.test",
      maxRetries: 0,
      timeout: 1_000,
    });

    await expect(client.updateExecutionPolicy({})).rejects.toThrow("at least one field");
    await expect(
      client.updateExecutionPolicy({ min_confidence: 1.2 }),
    ).rejects.toThrow("min_confidence");
    await expect(client.updateExecutionPolicy({ risk_floor: -1 })).rejects.toThrow("risk_floor");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects invalid team mutation input before sending the request", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const client = new DecisionEngineClient({
      apiKey: "de_test_123",
      baseUrl: "https://example.test",
      maxRetries: 0,
      timeout: 1_000,
    });

    await expect(client.inviteTeamMember({ email: "invalid-email" })).rejects.toThrow("valid email");
    await expect(client.updateTeamMemberRole("user_123", "superadmin" as never)).rejects.toThrow(
      "updateTeamMemberRole.role",
    );
    await expect(client.removeTeamMember("")).rejects.toThrow("non-empty userId");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects invalid device revoke input before sending the request", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const client = new DecisionEngineClient({
      apiKey: "de_test_123",
      baseUrl: "https://example.test",
      maxRetries: 0,
      timeout: 1_000,
    });

    await expect(client.revokeDevice("")).rejects.toThrow("registrationId");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects invalid metering input before sending the request", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const client = new DecisionEngineClient({
      apiKey: "de_test_123",
      baseUrl: "https://example.test",
      maxRetries: 0,
      timeout: 1_000,
    });

    await expect(
      client.ingestMeteringEvents({ device_id: "", events: [{ event_type: "query" }] }),
    ).rejects.toThrow("device_id");
    await expect(
      client.ingestMeteringEvents({ device_id: "device_123", events: [] }),
    ).rejects.toThrow("events array");
    await expect(
      client.ingestMeteringEvents({
        device_id: "device_123",
        events: [{ event_type: "query", unexpected: true } as never],
      }),
    ).rejects.toThrow("unsupported field");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects invalid credit refresh input before sending the request", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const client = new DecisionEngineClient({
      apiKey: "de_test_123",
      baseUrl: "https://example.test",
      maxRetries: 0,
      timeout: 1_000,
    });

    await expect(
      client.refreshCredits({ device_id: "", billing_period: "2026-05" }),
    ).rejects.toThrow("device_id");
    await expect(
      client.refreshCredits({ device_id: "device_123", billing_period: "202605" }),
    ).rejects.toThrow("billing_period");
    await expect(
      client.refreshCredits({ device_id: "device_123", billing_period: "2026-13" }),
    ).rejects.toThrow("billing_period month");
    await expect(
      client.refreshCredits({ device_id: "device_123", billing_period: "2026-05", credits_used: -1 }),
    ).rejects.toThrow("credits_used");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("supports explicit zero device_limit on API key list and create responses", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "key_1",
              label: "Mission Enterprise Key",
              key_prefix: "de_live_abcd",
              device_limit: 0,
              status: "active",
              created_at: "2026-05-19T00:00:00Z",
              expires_at: "2028-05-19T00:00:00Z",
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "key_2",
            label: "Mission Enterprise Key",
            key_prefix: "de_live_efgh",
            device_limit: 0,
            raw_key: "de_live_efgh_secret_value",
            created_at: "2026-05-19T00:00:00Z",
            expires_at: "2028-05-19T00:00:00Z",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
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
      label: "Mission Enterprise Key",
      device_limit: 0,
    });

    expect(listed[0]?.device_limit).toBe(0);
    expect(created.device_limit).toBe(0);
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://example.test/v1/api-keys",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          label: "Mission Enterprise Key",
          device_limit: 0,
        }),
      }),
    );
  });

  it("rejects invalid API key create input before sending the request", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const client = new DecisionEngineClient({
      apiKey: "de_test_123",
      baseUrl: "https://example.test",
      maxRetries: 0,
      timeout: 1_000,
    });

    await expect(
      client.createApiKey({
        label: "Mission Enterprise Key",
        device_limit: -1,
      }),
    ).rejects.toThrow("device_limit");
    await expect(
      client.createApiKey({
        label: "Mission Enterprise Key",
        expires_at: new Date("not-a-date"),
      }),
    ).rejects.toThrow("expires_at");
    await expect(
      client.createApiKey({
        label: "   ",
      }),
    ).rejects.toThrow("label");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects leaked raw_key fields in API key list responses", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "key_1",
            label: "Leaked Key",
            key_prefix: "de_live_abcd",
            raw_key: "de_live_abcd_secret_value",
            status: "active",
            created_at: "2026-05-19T00:00:00Z",
          },
        ]),
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

    await expect(client.listApiKeys()).rejects.toThrow("one-time secret material");
  });

  it("supports typed deployment control-plane helpers", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            providers: [
              {
                id: "algenta_shared",
                name: "Algenta Managed",
                description: "Multi-tenant shared pool.",
                icon: "🌐",
                regions: [{ id: "algenta-shared", label: "Algenta Shared", location: "Global" }],
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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
          { status: 202, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ status: "deprovisioning", deployment_id: "dep_123" }),
          { status: 202, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    const client = new DecisionEngineClient({
      apiKey: "de_test_123",
      baseUrl: "https://example.test",
      maxRetries: 0,
      timeout: 1_000,
    });

    const regions = await client.listDeploymentRegions();
    const deployment = await client.getDeployment();
    const created = await client.createDeployment();
    const cost = await client.getDeploymentCost("dep_123");
    const deleted = await client.deleteDeployment("dep_123");

    expect(regions.providers[0]?.regions[0]?.id).toBe("algenta-shared");
    expect(regions.providers[0]?.regions[0]?.name).toBe("Algenta Shared");
    expect(deployment?.deployment_id).toBe("dep_123");
    expect(created.status).toBe("requested");
    expect(cost.month).toBe(5);
    expect(deleted.status).toBe("deprovisioning");
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "https://example.test/v1/deployments",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          provider: "algenta_shared",
          region: "algenta-shared",
          config: null,
          billing_markup_pct: 20,
        }),
      }),
    );
  });

  it("fails closed on non-object error payloads without throwing a TypeError", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      new Response("null", {
        status: 409,
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

    await expect(client.createDeployment()).rejects.toThrow("Unknown error");
  });

  it("preserves structured upstream error codes on 5xx responses", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: {
            code: "repository_model_unavailable",
            message:
              "Repository decision planning requires a configured provider-backed chat model.",
            details: {},
          },
        }),
        {
          status: 503,
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

    const planPromise = client.createRepositoryDecisionPlan("repo_123", {
      snapshot_id: "snapshot_123",
      workspace_evidence_bundle_ref: "bundle_123",
    });

    await expect(planPromise).rejects.toMatchObject({
      statusCode: 503,
      errorCode: "repository_model_unavailable",
      message:
        "Repository decision planning requires a configured provider-backed chat model.",
    });

    await planPromise.catch(error => {
      expect(error).toBeInstanceOf(ServerError);
      expect((error as ServerError).responseBody).toEqual({
        error: {
          code: "repository_model_unavailable",
          message:
            "Repository decision planning requires a configured provider-backed chat model.",
          details: {},
        },
      });
    });
  });

  it("preserves structured upstream error codes on authentication failures", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: {
            code: "invalid_api_key",
            message: "The API key provided is invalid, expired, or has been revoked.",
          },
        }),
        {
          status: 401,
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

    await expect(client.me()).rejects.toMatchObject({
      statusCode: 401,
      errorCode: "invalid_api_key",
      message: "The API key provided is invalid, expired, or has been revoked.",
    });
  });

});
