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
    daemon_client = "daemon_client"
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


class RuntimeManifestResultBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    @model_validator(mode="before")
    @classmethod
    def _validate_list_fields_use_json_arrays(
        cls,
        value: Any,
    ) -> Any:
        if not isinstance(value, dict):
            return value
        for field_name, field_info in cls.model_fields.items():
            if field_name not in value:
                continue
            if get_origin(field_info.annotation) is not list:
                continue
            field_value = value[field_name]
            if field_value is None or isinstance(field_value, list):
                continue
            raise ValueError(f"{field_name} must be provided as a list.")
        return value


class RuntimeArtifactReferenceResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    kind: RuntimeArtifactKindResult
    path: str
    sha256: str
    size_bytes: StrictInt


class RuntimeManifestSignatureResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    algorithm: RuntimeSignatureAlgorithmResult
    key_id: str
    digest_hex: str
    signature_hex: str
    scope: RuntimeSignatureScopeResult


class RuntimeSnapshotReferenceResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    snapshot_id: str
    sha256: str
    source: str
    description: str


class RuntimeKernelPromotionCriteriaResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    required_manifest_fields: list[str] = Field(default_factory=list)
    required_proof_reference_fields: list[str] = Field(default_factory=list)
    deterministic_test_corpus_rule: str
    python_parity_rule: str
    schema_compatibility_rule: str
    minimum_primary_metric_improvement_pct: StrictFloat
    maximum_adjacent_metric_regression_pct: StrictFloat
    benchmark_exception_rule: str
    rollback_scope_rule: str
    tenant_isolation_rule: str
    replay_compatibility_rule: str

    @field_validator("required_manifest_fields", "required_proof_reference_fields")
    @classmethod
    def _validate_unique_required_fields(
        cls,
        value: list[str],
        info,
    ) -> list[str]:
        return _ensure_unique_runtime_values(value, str(info.field_name))


class RuntimeModuleManifestEntryResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    name: RuntimeModuleIdResult
    capability_id: StrictStr | None = None
    owner: StrictStr | None = None
    contract_boundary: StrictStr | None = None
    function_count: StrictInt
    functions: list[str] = Field(default_factory=list)
    layer: RuntimeLayerResult
    maturity: RuntimeMaturityResult
    public_supported_channels: list[RuntimeSupportedChannelResult] = Field(
        default_factory=list,
    )
    validated_auxiliary_channels: list[RuntimeAuxiliaryChannelResult] = Field(
        default_factory=list,
    )
    feature_flag_channels: list[RuntimeFeatureFlagChannelResult] = Field(
        default_factory=list,
    )
    proof_obligations: list[RuntimeProofObligationResult] = Field(
        default_factory=list,
    )
    proof_artifacts: list[str] = Field(default_factory=list)
    promotion_status: RuntimeKernelPromotionStatusResult | None = None
    rollback_flag: StrictStr | None = None
    benchmark_report_ref: StrictStr | None = None
    parity_report_ref: StrictStr | None = None
    schema_compat_report_ref: StrictStr | None = None
    isolation_proof_ref: StrictStr | None = None
    replay_proof_ref: StrictStr | None = None
    benchmark_artifact: str
    benchmark_speedup_x: StrictFloat
    compiled_artifact: str
    compiled_engine: RuntimeCompiledEngineResult
    max_cold_ms: StrictFloat
    max_warm_ms: StrictFloat
    max_hot_ms: StrictFloat

    @field_validator(
        "functions",
        "proof_artifacts",
        "public_supported_channels",
        "validated_auxiliary_channels",
        "feature_flag_channels",
        "proof_obligations",
    )
    @classmethod
    def _validate_unique_module_identifier_lists(
        cls,
        value: list[Any],
        info,
    ) -> list[Any]:
        return _ensure_unique_runtime_values(value, str(info.field_name))

    @model_validator(mode="after")
    def _validate_shipping_kernel_metadata(self) -> RuntimeModuleManifestEntryResult:
        if self.promotion_status is not RuntimeKernelPromotionStatusResult.shipping:
            return self
        required_fields = (
            "capability_id",
            "owner",
            "contract_boundary",
            "rollback_flag",
            "benchmark_report_ref",
            "parity_report_ref",
            "schema_compat_report_ref",
            "isolation_proof_ref",
            "replay_proof_ref",
        )
        for field_name in required_fields:
            value = getattr(self, field_name)
            if value is None or not str(value).strip():
                raise ValueError(
                    f"{field_name} must be provided for shipping runtime modules."
                )
        return self


class RuntimeDeploymentModesResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    current: RuntimeDeploymentModeResult
    supported_modes: list[RuntimeDeploymentModeResult] = Field(default_factory=list)
    rule: str

    @field_validator("supported_modes")
    @classmethod
    def _validate_unique_supported_modes(
        cls,
        value: list[RuntimeDeploymentModeResult],
    ) -> list[RuntimeDeploymentModeResult]:
        return _ensure_unique_runtime_values(value, "supported_modes")


class RuntimeShippingContractSummaryResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    module_count: StrictInt
    function_count: StrictInt
    runtime_core_layer: RuntimeLayerResult
    benchmark_discovery_rule: RuntimeBenchmarkDiscoveryRuleResult


class RuntimeBenchmarkDiscoverySourceModuleEntryResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    import_path: StrictStr
    public_function_count: StrictInt


class RuntimeBenchmarkDiscoveryLaneResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    discovered_source_modules: StrictInt
    discovered_public_functions: StrictInt
    discovered_source_inventory: list[RuntimeBenchmarkDiscoverySourceModuleEntryResult] = Field(
        default_factory=list
    )
    shipping_manifest_modules: StrictInt
    shipping_manifest_functions: StrictInt
    non_shipping_rule: RuntimeNonShippingRuleResult

    @field_validator("discovered_source_inventory")
    @classmethod
    def _validate_unique_discovered_source_inventory(
        cls,
        value: list[RuntimeBenchmarkDiscoverySourceModuleEntryResult],
    ) -> list[RuntimeBenchmarkDiscoverySourceModuleEntryResult]:
        return _ensure_unique_runtime_values(
            value,
            "benchmark_discovery_lane.discovered_source_inventory",
            value_selector=lambda entry: entry.import_path,
        )

    @model_validator(mode="after")
    def _validate_discovery_inventory(self) -> RuntimeBenchmarkDiscoveryLaneResult:
        if self.discovered_source_modules != len(self.discovered_source_inventory):
            raise ValueError(
                "benchmark_discovery_lane.discovered_source_modules must equal the number "
                "of discovered_source_inventory entries."
            )
        total_public_functions = 0
        discovered_import_paths: list[str] = []
        for index, entry in enumerate(self.discovered_source_inventory):
            if entry.public_function_count <= 0:
                raise ValueError(
                    f"benchmark_discovery_lane.discovered_source_inventory.{index}.public_function_count must be greater than 0."
                )
            total_public_functions += entry.public_function_count
            discovered_import_paths.append(entry.import_path)
        if self.discovered_public_functions != total_public_functions:
            raise ValueError(
                "benchmark_discovery_lane.discovered_public_functions must equal the total "
                "discovered_source_inventory public_function_count."
            )
        if discovered_import_paths != sorted(discovered_import_paths):
            raise ValueError(
                "benchmark_discovery_lane.discovered_source_inventory must be sorted by import_path."
            )
        if self.shipping_manifest_modules > self.discovered_source_modules:
            raise ValueError(
                "benchmark_discovery_lane.shipping_manifest_modules cannot exceed "
                "benchmark_discovery_lane.discovered_source_modules."
            )
        if self.shipping_manifest_functions > self.discovered_public_functions:
            raise ValueError(
                "benchmark_discovery_lane.shipping_manifest_functions cannot exceed "
                "benchmark_discovery_lane.discovered_public_functions."
            )
        return self


class RuntimeAdvertisedCapabilitiesResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    runtime_modules: list[RuntimeModuleIdResult] = Field(default_factory=list)
    public_endpoints: list[RuntimePublicEndpointResult] = Field(
        default_factory=list,
    )
    admin_endpoints: list[RuntimeAdminEndpointResult] = Field(default_factory=list)
    feature_flag_endpoints: list[RuntimeFeatureFlagEndpointResult] = Field(
        default_factory=list,
    )

    @field_validator(
        "runtime_modules",
        "public_endpoints",
        "admin_endpoints",
        "feature_flag_endpoints",
    )
    @classmethod
    def _validate_unique_advertised_capabilities(
        cls,
        value: list[Any],
        info,
    ) -> list[Any]:
        return _ensure_unique_runtime_values(value, str(info.field_name))


class RuntimeNamedRuleResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    name: RuntimeInvariantNameResult
    statement: str


class RuntimeExecutionModelResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    state_fields: list[RuntimeExecutionStateFieldResult] = Field(default_factory=list)
    allowed_transitions: list[RuntimeExecutionTransitionResult] = Field(
        default_factory=list,
    )
    validity_rules: list[RuntimeExecutionValidityRuleResult] = Field(
        default_factory=list,
    )

    @field_validator("state_fields", "allowed_transitions", "validity_rules")
    @classmethod
    def _validate_unique_execution_lists(
        cls,
        value: list[Any],
        info,
    ) -> list[Any]:
        return _ensure_unique_runtime_values(value, str(info.field_name))


class RuntimeExternalNondeterminismPolicyResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    sources: list[RuntimeExternalNondeterminismSourceResult] = Field(
        default_factory=list,
    )
    rule: str
    required_artifacts: list[RuntimeNondeterminismArtifactResult] = Field(
        default_factory=list,
    )
    failure_codes: list[RuntimeFailureCodeResult] = Field(default_factory=list)

    @field_validator("sources", "required_artifacts", "failure_codes")
    @classmethod
    def _validate_unique_nondeterminism_lists(
        cls,
        value: list[Any],
        info,
    ) -> list[Any]:
        return _ensure_unique_runtime_values(value, str(info.field_name))


class RuntimeArtifactLineageSchemaResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    artifact_flow: list[RuntimeArtifactLineageStepResult] = Field(
        default_factory=list,
    )
    required_node_fields: list[RuntimeLineageNodeFieldResult] = Field(
        default_factory=list,
    )
    immutability_rule: str

    @field_validator("artifact_flow", "required_node_fields")
    @classmethod
    def _validate_unique_lineage_lists(
        cls,
        value: list[Any],
        info,
    ) -> list[Any]:
        return _ensure_unique_runtime_values(value, str(info.field_name))


class RuntimeCapabilityEnumsResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    side_effect_class: list[RuntimeSideEffectClassResult] = Field(
        default_factory=list,
    )
    risk_level: list[RuntimeRiskLevelResult] = Field(default_factory=list)
    replayability: list[RuntimeReplayabilityResult] = Field(default_factory=list)

    @field_validator("side_effect_class", "risk_level", "replayability")
    @classmethod
    def _validate_unique_capability_enums(
        cls,
        value: list[Any],
        info,
    ) -> list[Any]:
        return _ensure_unique_runtime_values(value, str(info.field_name))


class RuntimeCapabilityAlgebraSchemaResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    required_fields: list[RuntimeCapabilityFieldResult] = Field(default_factory=list)
    enums: RuntimeCapabilityEnumsResult
    rules: list[RuntimeCapabilityRuleResult] = Field(default_factory=list)

    @field_validator("required_fields", "rules")
    @classmethod
    def _validate_unique_capability_lists(
        cls,
        value: list[Any],
        info,
    ) -> list[Any]:
        return _ensure_unique_runtime_values(value, str(info.field_name))


class RuntimeLayerProofMatrixEntryResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    layer: RuntimeLayerResult
    status: RuntimeMaturityResult
    obligations: list[RuntimeProofObligationResult] = Field(default_factory=list)
    evidence_paths: list[str] = Field(default_factory=list)

    @field_validator("obligations", "evidence_paths")
    @classmethod
    def _validate_unique_layer_artifacts(
        cls,
        value: list[Any],
        info,
    ) -> list[Any]:
        return _ensure_unique_runtime_values(value, str(info.field_name))


class RuntimeBenchmarkClassEntryResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    code: RuntimeBenchmarkClassCodeResult
    description: str
    evidence_paths: list[StrictStr] = Field(default_factory=list)

    @field_validator("evidence_paths")
    @classmethod
    def _validate_unique_evidence_paths(cls, value: list[StrictStr]) -> list[StrictStr]:
        return _ensure_unique_runtime_values(value, "evidence_paths")


class RuntimeBenchmarkFrameworkResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    classes: list[RuntimeBenchmarkClassEntryResult] = Field(default_factory=list)
    required_metrics: list[RuntimeBenchmarkMetricResult] = Field(
        default_factory=list,
    )
    baselines: list[RuntimeBenchmarkBaselineResult] = Field(default_factory=list)

    @field_validator("classes")
    @classmethod
    def _validate_unique_benchmark_classes(
        cls,
        value: list[RuntimeBenchmarkClassEntryResult],
    ) -> list[RuntimeBenchmarkClassEntryResult]:
        return _ensure_unique_runtime_values(
            value,
            "classes",
            value_selector=lambda entry: entry.code,
        )

    @field_validator("required_metrics", "baselines")
    @classmethod
    def _validate_unique_benchmark_enum_lists(
        cls,
        value: list[Any],
        info,
    ) -> list[Any]:
        return _ensure_unique_runtime_values(value, str(info.field_name))


class RuntimeSLOBudgetResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    name: RuntimeSLOBudgetNameResult
    applies_to: RuntimeSLOBudgetAppliesToResult
    p95_objective_ms: StrictFloat
    hard_ceiling_ms: StrictFloat | None = None
    notes: str | None = None


class RuntimeSchedulerModelResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    policies: list[RuntimeSchedulerPolicyResult] = Field(default_factory=list)
    minimize: list[RuntimeSchedulerMinimizeObjectiveResult] = Field(
        default_factory=list,
    )
    maximize: list[RuntimeSchedulerMaximizeObjectiveResult] = Field(
        default_factory=list,
    )
    invariants: list[RuntimeSchedulerInvariantResult] = Field(default_factory=list)

    @field_validator("policies", "minimize", "maximize", "invariants")
    @classmethod
    def _validate_unique_scheduler_lists(
        cls,
        value: list[Any],
        info,
    ) -> list[Any]:
        return _ensure_unique_runtime_values(value, str(info.field_name))


class RuntimeMemoryModelResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    regions: list[RuntimeMemoryRegionResult] = Field(default_factory=list)
    rules: list[RuntimeMemoryRuleResult] = Field(default_factory=list)
    failure_codes: list[RuntimeFailureCodeResult] = Field(default_factory=list)

    @field_validator("regions", "rules", "failure_codes")
    @classmethod
    def _validate_unique_memory_lists(
        cls,
        value: list[Any],
        info,
    ) -> list[Any]:
        return _ensure_unique_runtime_values(value, str(info.field_name))


class RuntimeEvaluationScienceResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    dimensions: list[RuntimeEvaluationDimensionResult] = Field(default_factory=list)
    methods: list[RuntimeEvaluationMethodResult] = Field(default_factory=list)
    release_blockers: list[RuntimeReleaseBlockerResult] = Field(
        default_factory=list,
    )

    @field_validator("dimensions", "methods", "release_blockers")
    @classmethod
    def _validate_unique_evaluation_lists(
        cls,
        value: list[Any],
        info,
    ) -> list[Any]:
        return _ensure_unique_runtime_values(value, str(info.field_name))


class RuntimeThreatModelResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    threat_classes: list[RuntimeThreatClassResult] = Field(default_factory=list)
    controls: list[RuntimeThreatControlResult] = Field(default_factory=list)
    non_negotiable_rules: list[RuntimeThreatRuleResult] = Field(
        default_factory=list,
    )

    @field_validator("threat_classes", "controls", "non_negotiable_rules")
    @classmethod
    def _validate_unique_threat_lists(
        cls,
        value: list[Any],
        info,
    ) -> list[Any]:
        return _ensure_unique_runtime_values(value, str(info.field_name))


class RuntimeTypedFailureResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    code: RuntimeFailureCodeResult
    description: str


class RuntimeFormalReleaseTheoremResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    statement: str
    required_conditions: list[RuntimeReleaseConditionResult] = Field(
        default_factory=list,
    )

    @field_validator("required_conditions")
    @classmethod
    def _validate_unique_required_conditions(
        cls,
        value: list[RuntimeReleaseConditionResult],
    ) -> list[RuntimeReleaseConditionResult]:
        return _ensure_unique_runtime_values(
            value,
            "required_conditions",
        )


class RuntimeReleaseArtifactBundleResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    required_artifacts: list[RuntimeReleaseArtifactResult] = Field(
        default_factory=list,
    )

    @field_validator("required_artifacts")
    @classmethod
    def _validate_unique_required_artifacts(
        cls,
        value: list[RuntimeReleaseArtifactResult],
    ) -> list[RuntimeReleaseArtifactResult]:
        return _ensure_unique_runtime_values(
            value,
            "required_artifacts",
        )


class RuntimeReleaseGateResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    gate: RuntimeReleaseGateIdResult
    description: str


class RuntimeImmediateImplementationPRResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    pr: str
    focus: str
    deliverables: list[str] = Field(default_factory=list)


class RuntimeAdminModuleSummaryResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    module_count: StrictInt
    function_count: StrictInt
    maturity_counts: dict[RuntimeMaturityResult, StrictInt] = Field(default_factory=dict)
    layer_counts: dict[RuntimeLayerResult, StrictInt] = Field(default_factory=dict)


class RuntimeAdminEvaluationSummaryResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    dimension_count: StrictInt
    method_count: StrictInt
    release_blocker_count: StrictInt
    benchmark_class_count: StrictInt
    slo_budget_count: StrictInt
    replay_gate_enabled: StrictBool
    tool_call_quality_gate_enabled: StrictBool
    rag_quality_gate_enabled: StrictBool
    decision_quality_gate_enabled: StrictBool


class RuntimeAdminModulesResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    runtime_version: str
    llm_core_manifest: str
    module_manifest_version: str
    shipping_contract: RuntimeShippingContractSummaryResult
    summary: RuntimeAdminModuleSummaryResult
    proof_matrix: list[RuntimeLayerProofMatrixEntryResult] = Field(
        default_factory=list,
    )
    modules: list[RuntimeModuleManifestEntryResult] = Field(default_factory=list)
    manifest_digest: str
    signature: RuntimeManifestSignatureResult

    @field_validator("proof_matrix")
    @classmethod
    def _validate_unique_proof_matrix_layers(
        cls,
        value: list[RuntimeLayerProofMatrixEntryResult],
    ) -> list[RuntimeLayerProofMatrixEntryResult]:
        return _ensure_unique_runtime_values(
            value,
            "proof_matrix",
            value_selector=lambda entry: entry.layer,
        )

    @field_validator("modules")
    @classmethod
    def _validate_unique_module_names(
        cls,
        value: list[RuntimeModuleManifestEntryResult],
    ) -> list[RuntimeModuleManifestEntryResult]:
        return _ensure_unique_runtime_values(
            value,
            "modules",
            value_selector=lambda entry: entry.name,
        )

    @model_validator(mode="after")
    def _validate_count_integrity(self) -> RuntimeAdminModulesResult:
        total_functions = 0
        for index, module in enumerate(self.modules):
            if module.function_count != len(module.functions):
                raise ValueError(
                    f"modules.{index}.functions must contain exactly "
                    f"{module.function_count} entries to match function_count."
                )
            total_functions += module.function_count
        if self.shipping_contract.module_count != len(self.modules):
            raise ValueError(
                "shipping_contract.module_count must equal the number of manifest modules."
            )
        if self.shipping_contract.function_count != total_functions:
            raise ValueError(
                "shipping_contract.function_count must equal the total module function_count."
            )
        if self.summary.module_count != len(self.modules):
            raise ValueError("summary.module_count must equal the number of manifest modules.")
        if self.summary.function_count != total_functions:
            raise ValueError(
                "summary.function_count must equal the total module function_count."
            )
        expected_maturity_counts = _count_runtime_values(
            [module.maturity for module in self.modules]
        )
        if self.summary.maturity_counts != expected_maturity_counts:
            raise ValueError(
                "summary.maturity_counts must equal the module maturity distribution."
            )
        expected_layer_counts = _count_runtime_values([module.layer for module in self.modules])
        if self.summary.layer_counts != expected_layer_counts:
            raise ValueError("summary.layer_counts must equal the module layer distribution.")
        return self


class RuntimeBenchmarkModuleEntryResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    name: RuntimeModuleIdResult
    function_count: StrictInt
    benchmark_artifact: str
    benchmark_speedup_x: StrictFloat
    compiled_artifact: str
    compiled_engine: RuntimeCompiledEngineResult
    max_cold_ms: StrictFloat
    max_warm_ms: StrictFloat
    max_hot_ms: StrictFloat


class RuntimeAdminBenchmarksResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    runtime_version: str
    llm_core_manifest: str
    module_manifest_version: str
    benchmark_discovery_lane: RuntimeBenchmarkDiscoveryLaneResult
    benchmarking: RuntimeBenchmarkFrameworkResult
    slo_budgets: list[RuntimeSLOBudgetResult] = Field(default_factory=list)
    quality_gate_benchmark_classes: list[RuntimeBenchmarkClassEntryResult] = Field(
        default_factory=list,
    )
    quality_gate_slo_budgets: list[RuntimeSLOBudgetResult] = Field(default_factory=list)
    evaluation_science: RuntimeEvaluationScienceResult
    evaluation_summary: RuntimeAdminEvaluationSummaryResult
    compiled_artifacts: list[RuntimeArtifactReferenceResult] = Field(
        default_factory=list,
    )
    shipping_runtime_modules: list[RuntimeModuleIdResult] = Field(
        default_factory=list,
    )
    shipping_runtime_function_counts: list[StrictInt] = Field(default_factory=list)
    shipping_runtime_benchmark_speedups_x: list[StrictFloat] = Field(
        default_factory=list,
    )
    shipping_runtime_benchmark_artifacts: list[StrictStr] = Field(
        default_factory=list,
    )
    shipping_runtime_compiled_artifacts: list[StrictStr] = Field(
        default_factory=list,
    )
    shipping_runtime_compiled_engines: list[RuntimeCompiledEngineResult] = Field(
        default_factory=list,
    )
    shipping_runtime_max_cold_ms: list[StrictFloat] = Field(
        default_factory=list,
    )
    shipping_runtime_max_warm_ms: list[StrictFloat] = Field(
        default_factory=list,
    )
    shipping_runtime_max_hot_ms: list[StrictFloat] = Field(
        default_factory=list,
    )
    module_benchmarks: list[RuntimeBenchmarkModuleEntryResult] = Field(
        default_factory=list,
    )
    manifest_digest: str
    signature: RuntimeManifestSignatureResult

    @field_validator("compiled_artifacts")
    @classmethod
    def _validate_unique_compiled_artifacts(
        cls,
        value: list[RuntimeArtifactReferenceResult],
    ) -> list[RuntimeArtifactReferenceResult]:
        return _ensure_unique_runtime_values(
            value,
            "compiled_artifacts",
            value_selector=lambda entry: entry.path,
        )

    @field_validator("quality_gate_benchmark_classes")
    @classmethod
    def _validate_unique_quality_gate_benchmark_classes(
        cls,
        value: list[RuntimeBenchmarkClassEntryResult],
    ) -> list[RuntimeBenchmarkClassEntryResult]:
        return _ensure_unique_runtime_values(
            value,
            "quality_gate_benchmark_classes",
            value_selector=lambda entry: entry.code,
        )

    @field_validator("module_benchmarks")
    @classmethod
    def _validate_unique_benchmark_modules(
        cls,
        value: list[RuntimeBenchmarkModuleEntryResult],
    ) -> list[RuntimeBenchmarkModuleEntryResult]:
        return _ensure_unique_runtime_values(
            value,
            "module_benchmarks",
            value_selector=lambda entry: entry.name,
        )

    @field_validator("shipping_runtime_modules")
    @classmethod
    def _validate_unique_shipping_runtime_modules(
        cls,
        value: list[RuntimeModuleIdResult],
    ) -> list[RuntimeModuleIdResult]:
        return _ensure_unique_runtime_values(value, "shipping_runtime_modules")

    @field_validator("quality_gate_slo_budgets")
    @classmethod
    def _validate_unique_quality_gate_slo_budgets(
        cls,
        value: list[RuntimeSLOBudgetResult],
    ) -> list[RuntimeSLOBudgetResult]:
        return _ensure_unique_runtime_values(
            value,
            "quality_gate_slo_budgets",
            value_selector=lambda entry: entry.name,
        )

    @model_validator(mode="after")
    def _validate_benchmark_integrity(self) -> RuntimeAdminBenchmarksResult:
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(self.module_benchmarks):
            raise ValueError(
                "benchmark_discovery_lane.shipping_manifest_modules must equal the number "
                "of benchmark modules."
            )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(
            self.shipping_runtime_modules
        ):
            raise ValueError(
                "shipping_runtime_modules must contain one entry per shipping benchmark module."
            )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(
            self.shipping_runtime_function_counts
        ):
            raise ValueError(
                "shipping_runtime_function_counts must contain one entry per shipping "
                "benchmark module."
            )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(
            self.shipping_runtime_benchmark_speedups_x
        ):
            raise ValueError(
                "shipping_runtime_benchmark_speedups_x must contain one entry per shipping "
                "benchmark module."
            )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(
            self.shipping_runtime_benchmark_artifacts
        ):
            raise ValueError(
                "shipping_runtime_benchmark_artifacts must contain one entry per shipping "
                "benchmark module."
            )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(
            self.shipping_runtime_compiled_artifacts
        ):
            raise ValueError(
                "shipping_runtime_compiled_artifacts must contain one entry per shipping "
                "benchmark module."
            )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(
            self.shipping_runtime_compiled_engines
        ):
            raise ValueError(
                "shipping_runtime_compiled_engines must contain one entry per shipping "
                "benchmark module."
            )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(
            self.shipping_runtime_max_cold_ms
        ):
            raise ValueError(
                "shipping_runtime_max_cold_ms must contain one entry per shipping "
                "benchmark module."
            )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(
            self.shipping_runtime_max_warm_ms
        ):
            raise ValueError(
                "shipping_runtime_max_warm_ms must contain one entry per shipping "
                "benchmark module."
            )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(
            self.shipping_runtime_max_hot_ms
        ):
            raise ValueError(
                "shipping_runtime_max_hot_ms must contain one entry per shipping "
                "benchmark module."
            )
        total_functions = sum(benchmark.function_count for benchmark in self.module_benchmarks)
        if self.benchmark_discovery_lane.shipping_manifest_functions != total_functions:
            raise ValueError(
                "benchmark_discovery_lane.shipping_manifest_functions must equal the total "
                "benchmark module function_count."
            )
        benchmark_class_codes = {entry.code for entry in self.benchmarking.classes}
        quality_gate_class_codes = {entry.code for entry in self.quality_gate_benchmark_classes}
        if not quality_gate_class_codes.issubset(benchmark_class_codes):
            raise ValueError(
                "quality_gate_benchmark_classes must be declared in benchmarking.classes."
            )
        budget_names = {entry.name for entry in self.slo_budgets}
        quality_gate_budget_names = {entry.name for entry in self.quality_gate_slo_budgets}
        if not quality_gate_budget_names.issubset(budget_names):
            raise ValueError("quality_gate_slo_budgets must be declared in slo_budgets.")
        dimensions = set(self.evaluation_science.dimensions)
        release_blockers = set(self.evaluation_science.release_blockers)
        expected_replay_gate = (
            RuntimeBenchmarkClassCodeResult.checkpoint_replay_overhead in quality_gate_class_codes
            and RuntimeSLOBudgetNameResult.replay in quality_gate_budget_names
            and RuntimeEvaluationDimensionResult.replay_success_rate in dimensions
            and RuntimeReleaseBlockerResult.replay_success_regression in release_blockers
        )
        expected_tool_call_quality_gate = (
            RuntimeBenchmarkClassCodeResult.mcp_tool_latency in quality_gate_class_codes
            and RuntimeSLOBudgetNameResult.mcp_call_first_party in quality_gate_budget_names
            and RuntimeEvaluationDimensionResult.tool_call_correctness in dimensions
            and RuntimeReleaseBlockerResult.tool_call_error_rate_increase in release_blockers
        )
        expected_rag_quality_gate = (
            RuntimeBenchmarkClassCodeResult.rag_retrieval_quality_latency in quality_gate_class_codes
            and RuntimeEvaluationDimensionResult.retrieval_precision_and_recall in dimensions
            and RuntimeReleaseBlockerResult.rag_precision_drop in release_blockers
        )
        expected_decision_quality_gate = (
            RuntimeBenchmarkClassCodeResult.decision_workflow_completion_latency
            in quality_gate_class_codes
            and RuntimeSLOBudgetNameResult.decision_plan_creation in quality_gate_budget_names
            and RuntimeEvaluationDimensionResult.decision_outcome_delta in dimensions
            and RuntimeReleaseBlockerResult.decision_plan_validity_drop in release_blockers
        )
        if self.evaluation_summary.dimension_count != len(self.evaluation_science.dimensions):
            raise ValueError(
                "evaluation_summary.dimension_count must equal the number of evaluation dimensions."
            )
        if self.evaluation_summary.method_count != len(self.evaluation_science.methods):
            raise ValueError(
                "evaluation_summary.method_count must equal the number of evaluation methods."
            )
        if self.evaluation_summary.release_blocker_count != len(
            self.evaluation_science.release_blockers
        ):
            raise ValueError(
                "evaluation_summary.release_blocker_count must equal the number of release blockers."
            )
        if self.evaluation_summary.benchmark_class_count != len(
            self.quality_gate_benchmark_classes
        ):
            raise ValueError(
                "evaluation_summary.benchmark_class_count must equal the number of quality gate benchmark classes."
            )
        if self.evaluation_summary.slo_budget_count != len(self.quality_gate_slo_budgets):
            raise ValueError(
                "evaluation_summary.slo_budget_count must equal the number of quality gate SLO budgets."
            )
        if self.evaluation_summary.replay_gate_enabled != expected_replay_gate:
            raise ValueError(
                "evaluation_summary.replay_gate_enabled must match the replay benchmark, budget, and release blocker coverage."
            )
        if (
            self.evaluation_summary.tool_call_quality_gate_enabled
            != expected_tool_call_quality_gate
        ):
            raise ValueError(
                "evaluation_summary.tool_call_quality_gate_enabled must match the tool-call benchmark, budget, and release blocker coverage."
            )
        if self.evaluation_summary.rag_quality_gate_enabled != expected_rag_quality_gate:
            raise ValueError(
                "evaluation_summary.rag_quality_gate_enabled must match the RAG benchmark and release blocker coverage."
            )
        if (
            self.evaluation_summary.decision_quality_gate_enabled
            != expected_decision_quality_gate
        ):
            raise ValueError(
                "evaluation_summary.decision_quality_gate_enabled must match the decision benchmark, budget, and release blocker coverage."
            )
        discovered_import_path_set = {
            entry.import_path for entry in self.benchmark_discovery_lane.discovered_source_inventory
        }
        for index, benchmark in enumerate(self.module_benchmarks):
            if benchmark.name.value not in discovered_import_path_set:
                raise ValueError(
                    "benchmark_discovery_lane.discovered_source_inventory must include "
                    f"module_benchmarks.{index}.name ({benchmark.name.value})."
                )
            if self.shipping_runtime_modules[index] != benchmark.name:
                raise ValueError(
                    f"shipping_runtime_modules.{index} must equal "
                    f"module_benchmarks.{index}.name."
                )
            if self.shipping_runtime_function_counts[index] != benchmark.function_count:
                raise ValueError(
                    f"shipping_runtime_function_counts.{index} must equal "
                    f"module_benchmarks.{index}.function_count."
                )
            if self.shipping_runtime_benchmark_speedups_x[index] != benchmark.benchmark_speedup_x:
                raise ValueError(
                    f"shipping_runtime_benchmark_speedups_x.{index} must equal "
                    f"module_benchmarks.{index}.benchmark_speedup_x."
                )
            if self.shipping_runtime_benchmark_artifacts[index] != benchmark.benchmark_artifact:
                raise ValueError(
                    f"shipping_runtime_benchmark_artifacts.{index} must equal "
                    f"module_benchmarks.{index}.benchmark_artifact."
                )
            if self.shipping_runtime_compiled_artifacts[index] != benchmark.compiled_artifact:
                raise ValueError(
                    f"shipping_runtime_compiled_artifacts.{index} must equal "
                    f"module_benchmarks.{index}.compiled_artifact."
                )
            if self.shipping_runtime_compiled_engines[index] != benchmark.compiled_engine:
                raise ValueError(
                    f"shipping_runtime_compiled_engines.{index} must equal "
                    f"module_benchmarks.{index}.compiled_engine."
                )
            if self.shipping_runtime_max_cold_ms[index] != benchmark.max_cold_ms:
                raise ValueError(
                    f"shipping_runtime_max_cold_ms.{index} must equal "
                    f"module_benchmarks.{index}.max_cold_ms."
                )
            if self.shipping_runtime_max_warm_ms[index] != benchmark.max_warm_ms:
                raise ValueError(
                    f"shipping_runtime_max_warm_ms.{index} must equal "
                    f"module_benchmarks.{index}.max_warm_ms."
                )
            if self.shipping_runtime_max_hot_ms[index] != benchmark.max_hot_ms:
                raise ValueError(
                    f"shipping_runtime_max_hot_ms.{index} must equal "
                    f"module_benchmarks.{index}.max_hot_ms."
                )
            if benchmark.benchmark_speedup_x <= 0:
                raise ValueError(
                    f"module_benchmarks.{index}.benchmark_speedup_x must be greater than 0."
                )
            if benchmark.max_cold_ms <= 0:
                raise ValueError(
                    f"module_benchmarks.{index}.max_cold_ms must be greater than 0."
                )
            if benchmark.max_warm_ms <= 0:
                raise ValueError(
                    f"module_benchmarks.{index}.max_warm_ms must be greater than 0."
                )
            if benchmark.max_hot_ms <= 0:
                raise ValueError(
                    f"module_benchmarks.{index}.max_hot_ms must be greater than 0."
                )
        compiled_artifact_paths = {artifact.path for artifact in self.compiled_artifacts}
        benchmark_artifact_indexes: dict[str, int] = {}
        for index, benchmark in enumerate(self.module_benchmarks):
            previous_index = benchmark_artifact_indexes.get(benchmark.benchmark_artifact)
            if previous_index is not None:
                raise ValueError(
                    f"module_benchmarks.{index}.benchmark_artifact duplicates "
                    f"module_benchmarks.{previous_index}.benchmark_artifact."
                )
            benchmark_artifact_indexes[benchmark.benchmark_artifact] = index
            if benchmark.compiled_artifact not in compiled_artifact_paths:
                raise ValueError(
                    f"module_benchmarks.{index}.compiled_artifact must reference a path "
                    "present in compiled_artifacts."
                )
        return self


class ReleaseConditionEvaluationResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    condition: RuntimeReleaseConditionResult
    satisfied: StrictBool
    detail: str
    evidence_paths: list[str] = Field(default_factory=list)

    @field_validator("evidence_paths")
    @classmethod
    def _validate_unique_evidence_paths(
        cls,
        value: list[str],
    ) -> list[str]:
        return _ensure_unique_runtime_values(value, "evidence_paths")


class RuntimeReleaseValidationResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    runtime_version: str
    llm_core_manifest: str
    module_manifest_version: str
    theorem_statement: str
    valid_release: StrictBool
    conditions: list[ReleaseConditionEvaluationResult] = Field(default_factory=list)
    deployment_mode: RuntimeDeploymentModeResult | None = None
    deployment_mode_raw: str
    manifest_digest: str
    signature: RuntimeManifestSignatureResult

    @field_validator("conditions")
    @classmethod
    def _validate_unique_conditions(
        cls,
        value: list[ReleaseConditionEvaluationResult],
    ) -> list[ReleaseConditionEvaluationResult]:
        return _ensure_unique_runtime_values(
            value,
            "conditions",
            value_selector=lambda entry: entry.condition,
        )


class RuntimeManifestResult(RuntimeManifestResultBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    runtime_version: str
    mojo_version: str
    llm_core_manifest: str
    module_manifest_version: str
    generated_at: str
    modules: list[RuntimeModuleManifestEntryResult] = Field(default_factory=list)
    compiled_artifacts: list[RuntimeArtifactReferenceResult] = Field(
        default_factory=list,
    )
    supported_channels: list[RuntimeSupportedChannelResult] = Field(
        default_factory=list,
    )
    validated_auxiliary_channels: list[RuntimeAuxiliaryChannelResult] = Field(
        default_factory=list,
    )
    feature_flag_channels: list[RuntimeFeatureFlagChannelResult] = Field(
        default_factory=list,
    )
    maturity: dict[RuntimeModuleIdResult, RuntimeMaturityResult] = Field(default_factory=dict)
    policy_snapshot: RuntimeSnapshotReferenceResult
    schema_snapshot: RuntimeSnapshotReferenceResult
    deployment_mode: RuntimeDeploymentModeResult
    deployment_modes: RuntimeDeploymentModesResult
    shipping_contract: RuntimeShippingContractSummaryResult
    benchmark_discovery_lane: RuntimeBenchmarkDiscoveryLaneResult
    advertised_capabilities: RuntimeAdvertisedCapabilitiesResult
    system_invariants: list[RuntimeNamedRuleResult] = Field(default_factory=list)
    execution_model: RuntimeExecutionModelResult
    external_nondeterminism: RuntimeExternalNondeterminismPolicyResult
    artifact_lineage: RuntimeArtifactLineageSchemaResult
    capability_algebra: RuntimeCapabilityAlgebraSchemaResult
    kernel_promotion_criteria: RuntimeKernelPromotionCriteriaResult | None = None
    proof_matrix: list[RuntimeLayerProofMatrixEntryResult] = Field(
        default_factory=list,
    )
    benchmarking: RuntimeBenchmarkFrameworkResult
    slo_budgets: list[RuntimeSLOBudgetResult] = Field(default_factory=list)
    scheduler_model: RuntimeSchedulerModelResult
    memory_model: RuntimeMemoryModelResult
    evaluation_science: RuntimeEvaluationScienceResult
    typed_failures: list[RuntimeTypedFailureResult] = Field(default_factory=list)
    threat_model: RuntimeThreatModelResult
    formal_release_theorem: RuntimeFormalReleaseTheoremResult
    release_artifact_bundle: RuntimeReleaseArtifactBundleResult
    release_gates: list[RuntimeReleaseGateResult] = Field(default_factory=list)
    immediate_implementation_sequence: list[RuntimeImmediateImplementationPRResult] = Field(
        default_factory=list,
    )
    manifest_digest: str
    signature: RuntimeManifestSignatureResult

    @field_validator(
        "compiled_artifacts",
        "supported_channels",
        "validated_auxiliary_channels",
        "feature_flag_channels",
    )
    @classmethod
    def _validate_unique_top_level_channels(
        cls,
        value: list[Any],
        info,
    ) -> list[Any]:
        if info.field_name == "compiled_artifacts":
            return _ensure_unique_runtime_values(
                value,
                str(info.field_name),
                value_selector=lambda entry: entry.path,
            )
        return _ensure_unique_runtime_values(value, str(info.field_name))

    @field_validator("system_invariants")
    @classmethod
    def _validate_unique_system_invariants(
        cls,
        value: list[RuntimeNamedRuleResult],
    ) -> list[RuntimeNamedRuleResult]:
        return _ensure_unique_runtime_values(
            value,
            "system_invariants",
            value_selector=lambda entry: entry.name,
        )

    @field_validator("proof_matrix")
    @classmethod
    def _validate_unique_manifest_proof_matrix_layers(
        cls,
        value: list[RuntimeLayerProofMatrixEntryResult],
    ) -> list[RuntimeLayerProofMatrixEntryResult]:
        return _ensure_unique_runtime_values(
            value,
            "proof_matrix",
            value_selector=lambda entry: entry.layer,
        )

    @field_validator("modules")
    @classmethod
    def _validate_unique_manifest_modules(
        cls,
        value: list[RuntimeModuleManifestEntryResult],
    ) -> list[RuntimeModuleManifestEntryResult]:
        return _ensure_unique_runtime_values(
            value,
            "modules",
            value_selector=lambda entry: entry.name,
        )

    @field_validator("typed_failures")
    @classmethod
    def _validate_unique_typed_failures(
        cls,
        value: list[RuntimeTypedFailureResult],
    ) -> list[RuntimeTypedFailureResult]:
        return _ensure_unique_runtime_values(
            value,
            "typed_failures",
            value_selector=lambda entry: entry.code,
        )

    @field_validator("release_gates")
    @classmethod
    def _validate_unique_release_gates(
        cls,
        value: list[RuntimeReleaseGateResult],
    ) -> list[RuntimeReleaseGateResult]:
        return _ensure_unique_runtime_values(
            value,
            "release_gates",
            value_selector=lambda entry: entry.gate,
        )

    @field_validator("immediate_implementation_sequence")
    @classmethod
    def _validate_unique_implementation_prs(
        cls,
        value: list[RuntimeImmediateImplementationPRResult],
    ) -> list[RuntimeImmediateImplementationPRResult]:
        return _ensure_unique_runtime_values(
            value,
            "immediate_implementation_sequence",
            value_selector=lambda entry: entry.pr,
        )

    @model_validator(mode="after")
    def _validate_count_integrity(self) -> RuntimeManifestResult:
        total_functions = 0
        for index, module in enumerate(self.modules):
            if module.function_count != len(module.functions):
                raise ValueError(
                    f"modules.{index}.functions must contain exactly "
                    f"{module.function_count} entries to match function_count."
                )
            total_functions += module.function_count
        if self.shipping_contract.module_count != len(self.modules):
            raise ValueError(
                "shipping_contract.module_count must equal the number of manifest modules."
            )
        if self.shipping_contract.function_count != total_functions:
            raise ValueError(
                "shipping_contract.function_count must equal the total module function_count."
            )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(self.modules):
            raise ValueError(
                "benchmark_discovery_lane.shipping_manifest_modules must equal the number "
                "of manifest modules."
            )
        if self.benchmark_discovery_lane.shipping_manifest_functions != total_functions:
            raise ValueError(
                "benchmark_discovery_lane.shipping_manifest_functions must equal the total "
                "module function_count."
            )
        discovered_import_path_set = {
            entry.import_path for entry in self.benchmark_discovery_lane.discovered_source_inventory
        }
        for module in self.modules:
            if module.name.value not in discovered_import_path_set:
                raise ValueError(
                    "benchmark_discovery_lane.discovered_source_inventory must include "
                    f"manifest module {module.name.value}."
                )
        return self
