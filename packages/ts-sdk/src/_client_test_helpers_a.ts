// Shared helpers (part a) for client.test.ts sub-modules.
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
  makeRuntimeManifestPayload,
  makeRuntimeAdminModulesPayload,
  makeRuntimeAdminBenchmarksPayload,
  makeRuntimeReleaseValidationPayload,
} from "./_client_test_helpers.js";

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

export function makeQueryResponse(overrides: Record<string, unknown> = {}) {
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

export function makeLLMModelsPayload(): Record<string, unknown> {
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

export function makeDecisionPlanPayload(): Record<string, unknown> {
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

export function makeProductDecisionPayload(): Record<string, unknown> {
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

export function makeProductAgentRunPayload(): Record<string, unknown> {
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

export function makeProductOptimizePayload(): Record<string, unknown> {
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

export function makeProductRetrievePayload(): Record<string, unknown> {
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

export function makeProductForecastPayload(): Record<string, unknown> {
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

export function makeDecisionLogPayload(
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

export function makeDecisionListPayload(): Record<string, unknown> {
  return {
    decisions: [makeDecisionLogPayload()],
    total: 1,
    page: 1,
    limit: 20,
    pages: 1,
    page_size: 20,
  };
}

export function makeExecutionReceiptPayload(): Record<string, unknown> {
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

export function makeDecisionEnvelopePayload(
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

export function makeRecommendPayload(): Record<string, unknown> {
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

export function makeScorePayload(): Record<string, unknown> {
  return {
    envelope: makeDecisionEnvelopePayload(),
    score: 0.73,
    score_breakdown: {
      expected_value: 0.61,
      downside_risk: 0.12,
    },
  };
}

export function makeComparePayload(): Record<string, unknown> {
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

export function makeAgentRunPayload(
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

export function makeAgentRunEventsPayload(): Record<string, unknown> {
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

export function makeAgentRunListPayload(): Record<string, unknown> {
  return {
    object: "list",
    data: [makeAgentRunPayload("requires_approval", "approve")],
    total: 1,
    page: 1,
    limit: 25,
    pages: 1,
  };
}

export function makeAgentRunCheckpointsPayload(): Record<string, unknown> {
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

export function makeAgentRunMissionEventsPayload(): Record<string, unknown> {
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

export function makeAgentRunMissionEventQueryPayload(): Record<string, unknown> {
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

export function makeAgentRunCheckpointQueryPayload(): Record<string, unknown> {
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

export function makeAgentRunReplayPayload(): Record<string, unknown> {
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

export function makeAgentRunTelemetryPayload(): Record<string, unknown> {
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

export function makeAgentRunTelemetryQueryPayload(): Record<string, unknown> {
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
