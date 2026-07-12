"""All RuntimeManifest * Result enum classes.

Extracted from packages/python-sdk/decision_engine/models_runtime_manifest.py during modularization.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, get_origin

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)




class RuntimeMaturityResult(str, Enum):
    experimental = "experimental"
    benchmarked = "benchmarked"
    parity_tested = "parity_tested"
    channel_covered = "channel_covered"
    enterprise_ready = "enterprise_ready"
    deprecated = "deprecated"


class RuntimeSideEffectClassResult(str, Enum):
    read_only = "read_only"
    write_scoped = "write_scoped"
    write_external = "write_external"
    exec_external = "exec_external"
    network_external = "network_external"


class RuntimeRiskLevelResult(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RuntimeReplayabilityResult(str, Enum):
    deterministic = "deterministic"
    artifact_backed = "artifact_backed"
    non_replayable = "non_replayable"


class RuntimeSupportedChannelResult(str, Enum):
    python_sdk = "python_sdk"
    typescript_sdk = "typescript_sdk"
    cli = "cli"
    mcp = "mcp"


class RuntimeAuxiliaryChannelResult(str, Enum):
    bundled_worker = "bundled_worker"
    runtime_local = "runtime_local"


class RuntimeFeatureFlagChannelResult(str, Enum):
    http_api_feature_flag = "http_api_feature_flag"


class RuntimeDeploymentModeResult(str, Enum):
    saas = "saas"
    vpc = "vpc"
    self_hosted = "self_hosted"
    air_gapped = "air_gapped"
    hybrid_provider = "hybrid_provider"
    local_dev_daemon = "local_dev_daemon"


class RuntimeLayerResult(str, Enum):
    mojo_llm_runtime_core = "mojo_llm_runtime_core"
    python_compatibility_ring = "python_compatibility_ring"
    llm_api_provider_layer = "llm_api_provider_layer"
    agent_runtime = "agent_runtime"
    decision_runtime = "decision_runtime"
    enterprise_control_plane = "enterprise_control_plane"


class RuntimeModuleIdResult(str, Enum):
    bpe_tokenizer = "bpe_tokenizer"
    text_tokenizer = "text.tokenizer"
    embeddings = "embeddings"
    flash_attention = "flash_attention"
    sparse_attention = "sparse_attention"
    transformer_attention = "transformer_attention"
    transformer_blocks = "transformer_blocks"
    llm_sampling = "llm_sampling"
    vector_similarity = "vector_similarity"
    vector_search = "vector_search"
    vector_kernels_ranker = "vector_kernels.ranker"
    vector_kernels_table = "vector_kernels.table"
    sparse_vector = "sparse_vector"
    rlhf_dpo = "rlhf_dpo"
    rerank_eval = "rerank_eval"
    inference_cost_latency = "inference_cost_latency"
    kv_cache = "kv_cache"
    paged_kv_cache = "paged_kv_cache"
    continuous_batching = "continuous_batching"
    inference_engine = "inference_engine"
    speculative_decoding = "speculative_decoding"
    generation_loop = "generation_loop"


class RuntimeCompiledEngineResult(str, Enum):
    mojo = "mojo"
    python_fallback = "python_fallback"


class RuntimeKernelPromotionStatusResult(str, Enum):
    candidate = "candidate"
    shipping = "shipping"


class RuntimeBenchmarkDiscoveryRuleResult(str, Enum):
    shipping_llm_rollout_only = (
        "Only the 22-module, 209-function LLM rollout is treated as the shipping runtime contract."
    )


class RuntimeNonShippingRuleResult(str, Enum):
    broader_mojo_inventory_not_advertised = (
        "The broader Mojo inventory remains a benchmark and discovery lane only; "
        "modules are not advertised on the runtime surface unless listed in this manifest."
    )


class RuntimePublicEndpointResult(str, Enum):
    meta_contract = "/v1/meta/contract"
    runtime_manifest = "/v1/runtime/manifest"


class RuntimeAdminEndpointResult(str, Enum):
    runtime_modules = "/v1/admin/runtime/modules"
    runtime_benchmarks = "/v1/admin/runtime/benchmarks"
    runtime_validation = "/v1/admin/runtime/validation"


class RuntimeFeatureFlagEndpointResult(str, Enum):
    libraries = "/v1/libraries"
    libraries_health = "/v1/libraries/health"
    libraries_execute = "/v1/libraries/execute"


class RuntimeExecutionTransitionResult(str, Enum):
    model_call_started = "model_call_started"
    model_token_emitted = "model_token_emitted"
    tool_call_requested = "tool_call_requested"
    tool_call_approved = "tool_call_approved"
    tool_call_denied = "tool_call_denied"
    checkpoint_committed = "checkpoint_committed"
    decision_plan_created = "decision_plan_created"
    simulation_started = "simulation_started"
    execution_started = "execution_started"
    replay_started = "replay_started"
    failure_emitted = "failure_emitted"


class RuntimeReleaseConditionResult(str, Enum):
    manifest_listed = "manifest-listed"
    proof_backed = "proof-backed"
    policy_covered = "policy-covered"
    replay_tested = "replay-tested"
    deployment_mode_validated = "deployment-mode validated"


class RuntimeFailureCodeResult(str, Enum):
    provider_timeout = "provider_timeout"
    runtime_compile_error = "runtime_compile_error"
    mcp_tool_denied = "mcp_tool_denied"
    policy_denied = "policy_denied"
    schema_access_denied = "schema_access_denied"
    checkpoint_failed = "checkpoint_failed"
    replay_mismatch = "replay_mismatch"
    external_dependency_unavailable = "external_dependency_unavailable"
    backend_unavailable = "backend_unavailable"
    quota_exceeded = "quota_exceeded"
    approval_required = "approval_required"
    kv_cache_exhausted = "kv_cache_exhausted"
    artifact_load_failed = "artifact_load_failed"
    memory_pressure_limit = "memory_pressure_limit"
    tenant_cache_violation = "tenant_cache_violation"
    checkpoint_state_overflow = "checkpoint_state_overflow"


class RuntimeBenchmarkClassCodeResult(str, Enum):
    microkernel_latency = "B1"
    end_to_end_llm_serving_latency = "B2"
    streaming_ttft = "B3"
    throughput_under_concurrency = "B4"
    memory_pressure_fragmentation = "B5"
    checkpoint_replay_overhead = "B6"
    mcp_tool_latency = "B7"
    provider_routing_overhead = "B8"
    rag_retrieval_quality_latency = "B9"
    decision_workflow_completion_latency = "B10"


class RuntimeSchedulerPolicyResult(str, Enum):
    fifo = "FIFO"
    priority_queue = "priority_queue"
    deadline_aware = "deadline_aware"
    cost_aware = "cost_aware"
    tenant_fair = "tenant_fair"
    kv_cache_aware = "kv_cache_aware"
    batching_aware = "batching_aware"
    speculative_decoding_aware = "speculative_decoding_aware"
    policy_constrained = "policy_constrained"


class RuntimeSchedulerMinimizeObjectiveResult(str, Enum):
    tail_latency = "tail latency"
    memory_waste = "memory waste"
    context_switch_overhead = "context-switch overhead"
    provider_cost = "provider cost"
    starvation = "starvation"


class RuntimeSchedulerMaximizeObjectiveResult(str, Enum):
    gpu_or_cpu_utilization = "GPU or CPU utilization"
    kv_cache_reuse = "KV cache reuse"
    batching_efficiency = "batching efficiency"
    token_throughput = "token throughput"
    fairness = "fairness"


class RuntimeSchedulerInvariantResult(str, Enum):
    no_request_starves_indefinitely = "No request starves indefinitely."
    high_priority_requests_cannot_violate_tenant_quota = (
        "High-priority requests cannot violate tenant quota."
    )
    batching_may_not_cross_isolation_boundaries_when_policy_forbids_it = (
        "Batching may not cross isolation boundaries when policy forbids it."
    )
    speculative_decoding_may_not_emit_unverified_tokens = (
        "Speculative decoding may not emit unverified tokens."
    )


class RuntimeReleaseGateIdResult(str, Enum):
    gate_a = "A"
    gate_b = "B"
    gate_c = "C"
    gate_d = "D"
    gate_e = "E"
    gate_f = "F"
    gate_g = "G"


class RuntimeInvariantNameResult(str, Enum):
    manifest_truth = "Manifest Truth"
    replay_determinism = "Replay Determinism"
    policy_monotonicity = "Policy Monotonicity"
    no_silent_fallback = "No Silent Fallback"
    audit_completeness = "Audit Completeness"
    tenant_non_interference = "Tenant Non-Interference"


class RuntimeExecutionStateFieldResult(str, Enum):
    request = "request"
    tenant = "tenant"
    workspace = "workspace"
    policy_snapshot = "policy_snapshot"
    schema_snapshot = "schema_snapshot"
    runtime_manifest = "runtime_manifest"
    model_backend = "model_backend"
    tool_manifest = "tool_manifest"
    checkpoint_log = "checkpoint_log"
    event_log = "event_log"
    decision_state = "decision_state"


class RuntimeExecutionValidityRuleResult(str, Enum):
    schema_valid = "schema-valid"
    policy_valid = "policy-valid"
    ordered = "ordered"
    replayable = "replayable"
    audit_visible = "audit-visible"


class RuntimeLineageNodeFieldResult(str, Enum):
    node_id = "node_id"
    artifact_type = "artifact_type"
    content_hash = "content_hash"
    parent_hashes = "parent_hashes"
    tenant_scope = "tenant_scope"
    workspace_scope = "workspace_scope"
    timestamp = "timestamp"
    manifest_version = "manifest_version"
    policy_snapshot_id = "policy_snapshot_id"
    schema_snapshot_id = "schema_snapshot_id"


class RuntimeExternalNondeterminismSourceResult(str, Enum):
    provider_responses = "provider responses"
    mcp_tool_responses = "MCP tool responses"
    database_snapshots = "database snapshots"
    clock_time = "clock time"
    random_seeds = "random seeds"
    external_api_outputs = "external API outputs"


class RuntimeNondeterminismArtifactResult(str, Enum):
    provider_response_record = "provider response record"
    tool_or_mcp_response_record = "tool or MCP response record"
    data_snapshot_reference_or_query_result_hash = (
        "data snapshot reference or query result hash"
    )
    clock_snapshot = "clock snapshot"
    seed_record = "seed record"
    backend_or_version_identifier = "backend or version identifier"


class RuntimeArtifactLineageStepResult(str, Enum):
    input = "input"
    policy_snapshot = "policy snapshot"
    schema_snapshot = "schema snapshot"
    runtime_manifest = "runtime manifest"
    backend_or_model = "backend or model"
    tool_or_mcp_calls = "tool or MCP calls"
    checkpoints = "checkpoints"
    decision_plan = "decision plan"
    execution_record = "execution record"
    outcome = "outcome"
    evaluation_result = "evaluation result"


class RuntimeCapabilityFieldResult(str, Enum):
    tool_name = "tool_name"
    input_schema = "input_schema"
    output_schema = "output_schema"
    side_effect_class = "side_effect_class"
    risk_level = "risk_level"
    required_policy = "required_policy"
    replayability = "replayability"
    approval_required = "approval_required"


class RuntimeCapabilityRuleResult(str, Enum):
    mcp_tools_are_untrusted_by_default = "MCP tools are untrusted by default."
    no_tool_may_execute_without_a_capability_record = (
        "No tool may execute without a capability record."
    )
    approvals_and_fallbacks_derive_from_capability_algebra_not_ad_hoc_code_paths = (
        "Approvals and fallbacks derive from capability algebra, not ad hoc code paths."
    )


class RuntimeSLOBudgetNameResult(str, Enum):
    runtime_manifest_load = "runtime_manifest_load"
    ttft = "ttft"
    end_to_end_turn = "end_to_end_turn"
    agent_checkpoint_commit = "agent_checkpoint_commit"
    mcp_call_first_party = "mcp_call_first_party"
    decision_plan_creation = "decision_plan_creation"
    replay = "replay"


class RuntimeSLOBudgetAppliesToResult(str, Enum):
    first_party_runtime_manifest_route = "first-party runtime manifest route"
    first_party_native_llm_serving_path = "first-party native LLM serving path"
    agent_runtime_checkpoint_persistence = "agent runtime checkpoint persistence"
    first_party_or_internal_mcp_tools = "first-party or internal MCP tools"
    decision_runtime_plan_generation = "decision runtime plan generation"
    runs_up_to_1000_events = "runs up to 1000 events"


class RuntimeMemoryRegionResult(str, Enum):
    model_weights = "model weights"
    kv_cache_pages = "KV cache pages"
    prompt_token_buffer = "prompt token buffer"
    generation_buffer = "generation buffer"
    retrieval_context_buffer = "retrieval context buffer"
    checkpoint_state = "checkpoint state"
    tool_call_state = "tool-call state"
    tenant_local_cache = "tenant-local cache"


class RuntimeMemoryRuleResult(str, Enum):
    kv_pages_are_tenant_scoped = "KV pages are tenant-scoped."
    evicted_cache_pages_must_be_zeroed_or_isolation_proven_before_reuse = (
        "Evicted cache pages must be zeroed or isolation-proven before reuse."
    )
    checkpoint_state_must_reference_immutable_artifact_hashes = (
        "Checkpoint state must reference immutable artifact hashes."
    )
    model_weights_must_be_version_pinned = "Model weights must be version-pinned."
    memory_pressure_must_emit_typed_failure_and_never_degrade_silently = (
        "Memory pressure must emit typed failure and never degrade silently."
    )


class RuntimeProofObligationResult(str, Enum):
    numerical_parity = "numerical parity"
    deterministic_kernels = "deterministic kernels"
    latency_memory_bounds = "latency and memory bounds"
    channel_proof = "channel proof"
    manifest_listing = "manifest listing"
    api_equivalence = "API equivalence"
    behavioral_equivalence_against_python_reference = (
        "behavioral equivalence against Python reference"
    )
    openai_compatible_schema_parity = "OpenAI-compatible schema parity"
    streaming_semantics_parity = "streaming semantics parity"
    typed_failure_parity = "typed failure parity"
    event_ordering = "event ordering"
    checkpoint_correctness = "checkpoint correctness"
    cancellation_safety = "cancellation safety"
    replay_safety = "replay safety"
    evidence_completeness = "evidence completeness"
    simulation_traceability = "simulation traceability"
    approval_correctness = "approval correctness"
    tenant_isolation = "tenant isolation"
    policy_enforcement = "policy enforcement"
    metering_correctness = "metering correctness"


class RuntimeBenchmarkMetricResult(str, Enum):
    p50 = "p50"
    p90 = "p90"
    p95 = "p95"
    p99 = "p99"
    tokens_per_second = "tokens_per_second"
    ttft = "ttft"
    requests_per_second = "requests_per_second"
    memory_peak = "memory_peak"
    cache_hit_rate = "cache_hit_rate"
    checkpoint_commit_latency = "checkpoint_commit_latency"
    replay_latency = "replay_latency"
    tool_call_latency = "tool_call_latency"
    decision_plan_latency = "decision_plan_latency"
    simulation_latency = "simulation_latency"
    cost_per_successful_run = "cost_per_successful_run"


class RuntimeBenchmarkBaselineResult(str, Enum):
    python_reference = "Python reference"
    pytorch_or_transformers_path = "PyTorch or Transformers path"
    vllm_openai_compatible_backend = "vLLM OpenAI-compatible backend"
    llama_cpp_gguf_backend = "llama.cpp GGUF backend"
    onnx_runtime_backend = "ONNX Runtime backend"
    ctranslate2_backend = "CTranslate2 backend"
    algenta_mojo_native_path = "Algenta Mojo-native path"


class RuntimeEvaluationMethodResult(str, Enum):
    bootstrap_confidence_intervals = "bootstrap confidence intervals"
    paired_model_comparisons = "paired model comparisons"
    regression_tests = "regression tests"
    drift_detection = "drift detection"
    ab_experiments = "A/B experiments"
    counterfactual_replay = "counterfactual replay"
    monte_carlo_simulation = "Monte Carlo simulation"
    sensitivity_analysis = "sensitivity analysis"


class RuntimeReleaseBlockerResult(str, Enum):
    replay_success_regression = "replay success regression"
    policy_violation_increase = "policy violation increase"
    p95_budget_violation = "p95 budget violation"
    rag_precision_drop = "RAG precision drop"
    tool_call_error_rate_increase = "tool-call error-rate increase"
    decision_plan_validity_drop = "decision-plan validity drop"


class RuntimeEvaluationDimensionResult(str, Enum):
    answer_correctness = "answer correctness"
    tool_call_correctness = "tool-call correctness"
    schema_correctness = "schema correctness"
    retrieval_precision_and_recall = "retrieval precision and recall"
    hallucination_rate = "hallucination rate"
    policy_violation_rate = "policy violation rate"
    replay_success_rate = "replay success rate"
    decision_outcome_delta = "decision outcome delta"
    cost_quality_frontier = "cost-quality frontier"
    latency_quality_frontier = "latency-quality frontier"


class RuntimeThreatClassResult(str, Enum):
    prompt_injection = "prompt injection"
    tool_injection = "tool injection"
    mcp_abuse = "MCP abuse"
    data_exfiltration = "data exfiltration"
    cross_tenant_leakage = "cross-tenant leakage"
    provider_fallback_leakage = "provider fallback leakage"
    secret_exposure = "secret exposure"
    replay_tampering = "replay tampering"
    audit_log_mutation = "audit log mutation"
    model_artifact_poisoning = "model artifact poisoning"
    dependency_supply_chain_attack = "dependency supply-chain attack"
    billing_abuse = "billing abuse"
    quota_bypass = "quota bypass"


class RuntimeThreatControlResult(str, Enum):
    tool_allowlists = "tool allowlists"
    argument_validation = "argument validation"
    result_sanitization = "result sanitization"
    egress_policy = "egress policy"
    signed_manifests = "signed manifests"
    signed_artifacts = "signed artifacts"
    immutable_audit_logs = "immutable audit logs"
    policy_snapshots = "policy snapshots"
    secret_scoping = "secret scoping"
    tenant_scoped_cache = "tenant-scoped cache"
    sbom = "SBOM"
    dependency_pinning = "dependency pinning"
    runtime_attestation = "runtime attestation"


class RuntimeThreatRuleResult(str, Enum):
    mcp_tools_are_untrusted_by_default = "MCP tools are untrusted by default."


class RuntimeReleaseArtifactResult(str, Enum):
    signed_runtime_manifest = "signed runtime manifest"
    module_maturity_table = "module maturity table"
    benchmark_report = "benchmark report"
    parity_report = "parity report"
    replay_report = "replay report"
    security_report = "security report"
    compatibility_report = "compatibility report"
    migration_notes = "migration notes"
    known_limitations = "known limitations"


class RuntimeArtifactKindResult(str, Enum):
    proof_bundle = "proof_bundle"
    parity_benchmark = "parity_benchmark"
    compiled_runtime_benchmark = "compiled_runtime_benchmark"
    compiled_mojo_binary = "compiled_mojo_binary"


class RuntimeSignatureAlgorithmResult(str, Enum):
    hmac_sha256 = "hmac-sha256"


class RuntimeSignatureScopeResult(str, Enum):
    control_plane_hmac_v1 = "control_plane_hmac_v1"


def _normalized_runtime_value(value: object) -> str:
    if isinstance(value, Enum):
        return value.value
    return str(value)


def _ensure_unique_runtime_values(
    values: list[Any],
    field_name: str,
    *,
    value_selector: Any | None = None,
) -> list[Any]:
    selector = value_selector or (lambda item: item)
    seen: set[str] = set()
    duplicates: list[str] = []
    for entry in values:
        normalized = _normalized_runtime_value(selector(entry))
        if normalized in seen and normalized not in duplicates:
            duplicates.append(normalized)
        seen.add(normalized)
    if duplicates:
        duplicate_text = ", ".join(duplicates)
        raise ValueError(f"{field_name} must be unique; duplicate entries: {duplicate_text}")
    return values


def _count_runtime_values(values: list[Any]) -> dict[Any, int]:
    counts: dict[Any, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts

