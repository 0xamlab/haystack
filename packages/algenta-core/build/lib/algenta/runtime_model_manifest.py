from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel

from algenta.runtime_model_common import jsonable


class RuntimeMaturity(str, Enum):
    experimental = "experimental"
    benchmarked = "benchmarked"
    parity_tested = "parity_tested"
    channel_covered = "channel_covered"
    enterprise_ready = "enterprise_ready"
    deprecated = "deprecated"


class RuntimeSideEffectClass(str, Enum):
    read_only = "read_only"
    write_scoped = "write_scoped"
    write_external = "write_external"
    exec_external = "exec_external"
    network_external = "network_external"


class RuntimeRiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RuntimeReplayability(str, Enum):
    deterministic = "deterministic"
    artifact_backed = "artifact_backed"
    non_replayable = "non_replayable"


class RuntimeSupportedChannel(str, Enum):
    python_sdk = "python_sdk"
    typescript_sdk = "typescript_sdk"
    cli = "cli"
    mcp = "mcp"


class RuntimeAuxiliaryChannel(str, Enum):
    daemon_client = "daemon_client"
    runtime_local = "runtime_local"


class RuntimeFeatureFlagChannel(str, Enum):
    http_api_feature_flag = "http_api_feature_flag"


class RuntimeDeploymentMode(str, Enum):
    saas = "saas"
    vpc = "vpc"
    self_hosted = "self_hosted"
    air_gapped = "air_gapped"
    hybrid_provider = "hybrid_provider"
    local_dev_daemon = "local_dev_daemon"


class RuntimeLayer(str, Enum):
    mojo_llm_runtime_core = "mojo_llm_runtime_core"
    python_compatibility_ring = "python_compatibility_ring"
    llm_api_provider_layer = "llm_api_provider_layer"
    agent_runtime = "agent_runtime"
    decision_runtime = "decision_runtime"
    enterprise_control_plane = "enterprise_control_plane"


class RuntimeModuleId(str, Enum):
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


class RuntimeCompiledEngine(str, Enum):
    mojo = "mojo"
    python_fallback = "python_fallback"


class RuntimeKernelPromotionStatus(str, Enum):
    candidate = "candidate"
    shipping = "shipping"


class RuntimeBenchmarkDiscoveryRule(str, Enum):
    shipping_llm_rollout_only = (
        "Only the 22-module, 209-function LLM rollout is treated as the shipping runtime contract."
    )


class RuntimeNonShippingRule(str, Enum):
    broader_mojo_inventory_not_advertised = (
        "The broader Mojo inventory remains a benchmark and discovery lane only; "
        "modules are not advertised on the runtime surface unless listed in this manifest."
    )


class RuntimePublicEndpoint(str, Enum):
    meta_contract = "/v1/meta/contract"
    runtime_manifest = "/v1/runtime/manifest"


class RuntimeAdminEndpoint(str, Enum):
    runtime_modules = "/v1/admin/runtime/modules"
    runtime_benchmarks = "/v1/admin/runtime/benchmarks"
    runtime_validation = "/v1/admin/runtime/validation"


class RuntimeFeatureFlagEndpoint(str, Enum):
    libraries = "/v1/libraries"
    libraries_health = "/v1/libraries/health"
    libraries_execute = "/v1/libraries/execute"


class RuntimeExecutionTransition(str, Enum):
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


class RuntimeReleaseCondition(str, Enum):
    manifest_listed = "manifest-listed"
    proof_backed = "proof-backed"
    policy_covered = "policy-covered"
    replay_tested = "replay-tested"
    deployment_mode_validated = "deployment-mode validated"


class RuntimeFailureCode(str, Enum):
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


class RuntimeBenchmarkClassCode(str, Enum):
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


class RuntimeSchedulerPolicy(str, Enum):
    fifo = "FIFO"
    priority_queue = "priority_queue"
    deadline_aware = "deadline_aware"
    cost_aware = "cost_aware"
    tenant_fair = "tenant_fair"
    kv_cache_aware = "kv_cache_aware"
    batching_aware = "batching_aware"
    speculative_decoding_aware = "speculative_decoding_aware"
    policy_constrained = "policy_constrained"


class RuntimeSchedulerMinimizeObjective(str, Enum):
    tail_latency = "tail latency"
    memory_waste = "memory waste"
    context_switch_overhead = "context-switch overhead"
    provider_cost = "provider cost"
    starvation = "starvation"


class RuntimeSchedulerMaximizeObjective(str, Enum):
    gpu_or_cpu_utilization = "GPU or CPU utilization"
    kv_cache_reuse = "KV cache reuse"
    batching_efficiency = "batching efficiency"
    token_throughput = "token throughput"
    fairness = "fairness"


class RuntimeSchedulerInvariant(str, Enum):
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


class RuntimeReleaseGateId(str, Enum):
    gate_a = "A"
    gate_b = "B"
    gate_c = "C"
    gate_d = "D"
    gate_e = "E"
    gate_f = "F"
    gate_g = "G"


class RuntimeInvariantName(str, Enum):
    manifest_truth = "Manifest Truth"
    replay_determinism = "Replay Determinism"
    policy_monotonicity = "Policy Monotonicity"
    no_silent_fallback = "No Silent Fallback"
    audit_completeness = "Audit Completeness"
    tenant_non_interference = "Tenant Non-Interference"


class RuntimeExecutionStateField(str, Enum):
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


class RuntimeExecutionValidityRule(str, Enum):
    schema_valid = "schema-valid"
    policy_valid = "policy-valid"
    ordered = "ordered"
    replayable = "replayable"
    audit_visible = "audit-visible"


class RuntimeLineageNodeField(str, Enum):
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


class RuntimeExternalNondeterminismSource(str, Enum):
    provider_responses = "provider responses"
    mcp_tool_responses = "MCP tool responses"
    database_snapshots = "database snapshots"
    clock_time = "clock time"
    random_seeds = "random seeds"
    external_api_outputs = "external API outputs"


class RuntimeNondeterminismArtifact(str, Enum):
    provider_response_record = "provider response record"
    tool_or_mcp_response_record = "tool or MCP response record"
    data_snapshot_reference_or_query_result_hash = (
        "data snapshot reference or query result hash"
    )
    clock_snapshot = "clock snapshot"
    seed_record = "seed record"
    backend_or_version_identifier = "backend or version identifier"


class RuntimeArtifactLineageStep(str, Enum):
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


class RuntimeCapabilityField(str, Enum):
    tool_name = "tool_name"
    input_schema = "input_schema"
    output_schema = "output_schema"
    side_effect_class = "side_effect_class"
    risk_level = "risk_level"
    required_policy = "required_policy"
    replayability = "replayability"
    approval_required = "approval_required"


class RuntimeCapabilityRule(str, Enum):
    mcp_tools_are_untrusted_by_default = "MCP tools are untrusted by default."
    no_tool_may_execute_without_a_capability_record = (
        "No tool may execute without a capability record."
    )
    approvals_and_fallbacks_derive_from_capability_algebra_not_ad_hoc_code_paths = (
        "Approvals and fallbacks derive from capability algebra, not ad hoc code paths."
    )


class RuntimeSLOBudgetName(str, Enum):
    runtime_manifest_load = "runtime_manifest_load"
    ttft = "ttft"
    end_to_end_turn = "end_to_end_turn"
    agent_checkpoint_commit = "agent_checkpoint_commit"
    mcp_call_first_party = "mcp_call_first_party"
    decision_plan_creation = "decision_plan_creation"
    replay = "replay"


class RuntimeSLOBudgetAppliesTo(str, Enum):
    first_party_runtime_manifest_route = "first-party runtime manifest route"
    first_party_native_llm_serving_path = "first-party native LLM serving path"
    agent_runtime_checkpoint_persistence = "agent runtime checkpoint persistence"
    first_party_or_internal_mcp_tools = "first-party or internal MCP tools"
    decision_runtime_plan_generation = "decision runtime plan generation"
    runs_up_to_1000_events = "runs up to 1000 events"


class RuntimeMemoryRegion(str, Enum):
    model_weights = "model weights"
    kv_cache_pages = "KV cache pages"
    prompt_token_buffer = "prompt token buffer"
    generation_buffer = "generation buffer"
    retrieval_context_buffer = "retrieval context buffer"
    checkpoint_state = "checkpoint state"
    tool_call_state = "tool-call state"
    tenant_local_cache = "tenant-local cache"


class RuntimeMemoryRule(str, Enum):
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


class RuntimeProofObligation(str, Enum):
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


class RuntimeBenchmarkMetric(str, Enum):
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


class RuntimeBenchmarkBaseline(str, Enum):
    python_reference = "Python reference"
    pytorch_or_transformers_path = "PyTorch or Transformers path"
    vllm_openai_compatible_backend = "vLLM OpenAI-compatible backend"
    llama_cpp_gguf_backend = "llama.cpp GGUF backend"
    onnx_runtime_backend = "ONNX Runtime backend"
    ctranslate2_backend = "CTranslate2 backend"
    algenta_mojo_native_path = "Algenta Mojo-native path"


class RuntimeEvaluationMethod(str, Enum):
    bootstrap_confidence_intervals = "bootstrap confidence intervals"
    paired_model_comparisons = "paired model comparisons"
    regression_tests = "regression tests"
    drift_detection = "drift detection"
    ab_experiments = "A/B experiments"
    counterfactual_replay = "counterfactual replay"
    monte_carlo_simulation = "Monte Carlo simulation"
    sensitivity_analysis = "sensitivity analysis"


class RuntimeReleaseBlocker(str, Enum):
    replay_success_regression = "replay success regression"
    policy_violation_increase = "policy violation increase"
    p95_budget_violation = "p95 budget violation"
    rag_precision_drop = "RAG precision drop"
    tool_call_error_rate_increase = "tool-call error-rate increase"
    decision_plan_validity_drop = "decision-plan validity drop"


class RuntimeEvaluationDimension(str, Enum):
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


class RuntimeThreatClass(str, Enum):
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


class RuntimeThreatControl(str, Enum):
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


class RuntimeThreatRule(str, Enum):
    mcp_tools_are_untrusted_by_default = "MCP tools are untrusted by default."


class RuntimeReleaseArtifact(str, Enum):
    signed_runtime_manifest = "signed runtime manifest"
    module_maturity_table = "module maturity table"
    benchmark_report = "benchmark report"
    parity_report = "parity report"
    replay_report = "replay report"
    security_report = "security report"
    compatibility_report = "compatibility report"
    migration_notes = "migration notes"
    known_limitations = "known limitations"


class RuntimeArtifactKind(str, Enum):
    proof_bundle = "proof_bundle"
    parity_benchmark = "parity_benchmark"
    compiled_runtime_benchmark = "compiled_runtime_benchmark"
    compiled_mojo_binary = "compiled_mojo_binary"


class RuntimeSignatureAlgorithm(str, Enum):
    hmac_sha256 = "hmac-sha256"


class RuntimeSignatureScope(str, Enum):
    control_plane_hmac_v1 = "control_plane_hmac_v1"


EnumT = TypeVar("EnumT", bound=Enum)


def _normalize_manifest_payload_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return {
            key: _normalize_manifest_payload_value(item)
            for key, item in value.__dict__.items()
            if not key.startswith("_")
        }
    if isinstance(value, Mapping):
        return {
            jsonable(key): _normalize_manifest_payload_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_manifest_payload_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_normalize_manifest_payload_value(item) for item in value)
    return value


def coerce_payload_mapping(payload: Any) -> dict[str, Any]:
    if isinstance(payload, BaseModel):
        normalized = _normalize_manifest_payload_value(payload)
        if isinstance(normalized, Mapping):
            return dict(normalized)
    model_dump = getattr(payload, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, Mapping):
            return {
                jsonable(key): _normalize_manifest_payload_value(item)
                for key, item in dumped.items()
            }
    if isinstance(payload, Mapping):
        return {
            jsonable(key): _normalize_manifest_payload_value(item)
            for key, item in payload.items()
        }
    payload_dict = getattr(payload, "__dict__", None)
    if isinstance(payload_dict, dict):
        return {
            jsonable(key): _normalize_manifest_payload_value(item)
            for key, item in payload_dict.items()
        }
    return dict(_normalize_manifest_payload_value(payload))


def _coerce_enum(value: Any, enum_cls: type[EnumT], field_name: str | None = None) -> EnumT:
    if isinstance(value, enum_cls):
        return value
    candidate = value.value if isinstance(value, Enum) else str(value)
    try:
        return enum_cls(candidate)
    except ValueError as exc:
        if field_name:
            raise ValueError(
                f"{field_name}: {value!r} is not a valid {enum_cls.__name__}"
            ) from exc
        raise


def _coerce_optional_enum(
    value: Any,
    enum_cls: type[EnumT],
    field_name: str | None = None,
) -> EnumT | None:
    if value is None:
        return None
    return _coerce_enum(value, enum_cls, field_name)


def _coerce_enum_list(
    values: Any,
    enum_cls: type[EnumT],
    field_name: str | None = None,
) -> list[EnumT]:
    if values is None:
        return []
    if not isinstance(values, list):
        if field_name:
            raise ValueError(f"{field_name} must be a list.")
        raise ValueError(f"{enum_cls.__name__} values must be a list.")
    coerced: list[EnumT] = []
    for index, item in enumerate(values):
        item_field = None if field_name is None else f"{field_name}.{index}"
        coerced.append(_coerce_enum(item, enum_cls, item_field))
    return coerced


def _coerce_enum_mapping(
    values: Any,
    key_enum_cls: type[EnumT],
    value_coercer: Any,
    field_name: str,
) -> dict[EnumT, Any]:
    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    coerced: dict[EnumT, Any] = {}
    for raw_key, raw_value in values.items():
        key = _coerce_enum(raw_key, key_enum_cls, f"{field_name}.{raw_key}.[key]")
        coerced[key] = value_coercer(raw_value, key)
    return coerced


def _normalized_manifest_runtime_value(value: object) -> str:
    if isinstance(value, Enum):
        return value.value
    return str(value)


def _ensure_unique_manifest_values(
    values: list[Any],
    field_name: str,
    *,
    value_selector: Any | None = None,
) -> list[Any]:
    selector = value_selector or (lambda item: item)
    seen: set[str] = set()
    duplicates: list[str] = []
    for entry in values:
        normalized = _normalized_manifest_runtime_value(selector(entry))
        if normalized in seen and normalized not in duplicates:
            duplicates.append(normalized)
        seen.add(normalized)
    if duplicates:
        duplicate_text = ", ".join(duplicates)
        raise ValueError(f"{field_name} must be unique; duplicate entries: {duplicate_text}")
    return values


def _count_manifest_values(values: list[Any]) -> dict[Any, int]:
    counts: dict[Any, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _require_manifest_field(data: dict[str, Any], key: str, context: str) -> Any:
    if key not in data:
        raise ValueError(f"{context}.{key} is required.")
    return data[key]


def _require_manifest_string_value(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")
    return value


def _require_manifest_integer_value(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")
    return value


def _require_manifest_float_value(value: Any, field_name: str) -> float:
    if not isinstance(value, float):
        raise ValueError(f"{field_name} must be a float.")
    return value


def _require_manifest_boolean_value(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")
    return value


def _require_manifest_string(data: dict[str, Any], key: str, context: str) -> str:
    return _require_manifest_string_value(
        _require_manifest_field(data, key, context),
        f"{context}.{key}",
    )


def _require_manifest_integer(data: dict[str, Any], key: str, context: str) -> int:
    return _require_manifest_integer_value(
        _require_manifest_field(data, key, context),
        f"{context}.{key}",
    )


def _require_manifest_float(data: dict[str, Any], key: str, context: str) -> float:
    return _require_manifest_float_value(
        _require_manifest_field(data, key, context),
        f"{context}.{key}",
    )


def _require_manifest_boolean(data: dict[str, Any], key: str, context: str) -> bool:
    return _require_manifest_boolean_value(
        _require_manifest_field(data, key, context),
        f"{context}.{key}",
    )


def _optional_manifest_float(data: dict[str, Any], key: str, context: str) -> float | None:
    if data.get(key) is None:
        return None
    return _require_manifest_float(data, key, context)


def _optional_manifest_string(data: dict[str, Any], key: str, context: str) -> str | None:
    if data.get(key) is None:
        return None
    return _require_manifest_string(data, key, context)


def _optional_manifest_string_list(
    data: dict[str, Any],
    key: str,
    context: str,
) -> list[str]:
    values = data.get(key)
    if values is None:
        return []
    field_name = f"{context}.{key}"
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list.")
    return [
        _require_manifest_string_value(item, f"{field_name}.{index}")
        for index, item in enumerate(values)
    ]


@dataclass(frozen=True)
class RuntimeArtifactReference:
    kind: RuntimeArtifactKind
    path: str
    sha256: str
    size_bytes: int

    @classmethod
    def from_api(cls, payload: Any, context: str = "compiled_artifacts") -> RuntimeArtifactReference:
        data = coerce_payload_mapping(payload)
        return cls(
            kind=_coerce_enum(data["kind"], RuntimeArtifactKind, f"{context}.kind"),
            path=_require_manifest_string(data, "path", context),
            sha256=_require_manifest_string(data, "sha256", context),
            size_bytes=_require_manifest_integer(data, "size_bytes", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeManifestSignature:
    algorithm: RuntimeSignatureAlgorithm
    key_id: str
    digest_hex: str
    signature_hex: str
    scope: RuntimeSignatureScope

    @classmethod
    def from_api(cls, payload: Any, context: str = "signature") -> RuntimeManifestSignature:
        data = coerce_payload_mapping(payload)
        return cls(
            algorithm=_coerce_enum(
                data["algorithm"],
                RuntimeSignatureAlgorithm,
                f"{context}.algorithm",
            ),
            key_id=_require_manifest_string(data, "key_id", context),
            digest_hex=_require_manifest_string(data, "digest_hex", context),
            signature_hex=_require_manifest_string(data, "signature_hex", context),
            scope=_coerce_enum(data["scope"], RuntimeSignatureScope, f"{context}.scope"),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeSnapshotReference:
    snapshot_id: str
    sha256: str
    source: str
    description: str

    @classmethod
    def from_api(cls, payload: Any, context: str = "snapshot") -> RuntimeSnapshotReference:
        data = coerce_payload_mapping(payload)
        return cls(
            snapshot_id=_require_manifest_string(data, "snapshot_id", context),
            sha256=_require_manifest_string(data, "sha256", context),
            source=_require_manifest_string(data, "source", context),
            description=_require_manifest_string(data, "description", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeKernelPromotionCriteria:
    required_manifest_fields: list[str] = field(default_factory=list)
    required_proof_reference_fields: list[str] = field(default_factory=list)
    deterministic_test_corpus_rule: str = ""
    python_parity_rule: str = ""
    schema_compatibility_rule: str = ""
    minimum_primary_metric_improvement_pct: float = 0.0
    maximum_adjacent_metric_regression_pct: float = 0.0
    benchmark_exception_rule: str = ""
    rollback_scope_rule: str = ""
    tenant_isolation_rule: str = ""
    replay_compatibility_rule: str = ""

    @classmethod
    def from_api(
        cls,
        payload: Any,
        context: str = "kernel_promotion_criteria",
    ) -> RuntimeKernelPromotionCriteria:
        data = coerce_payload_mapping(payload)
        return cls(
            required_manifest_fields=_ensure_unique_manifest_values(
                _optional_manifest_string_list(data, "required_manifest_fields", context),
                f"{context}.required_manifest_fields",
            ),
            required_proof_reference_fields=_ensure_unique_manifest_values(
                _optional_manifest_string_list(
                    data,
                    "required_proof_reference_fields",
                    context,
                ),
                f"{context}.required_proof_reference_fields",
            ),
            deterministic_test_corpus_rule=_require_manifest_string(
                data,
                "deterministic_test_corpus_rule",
                context,
            ),
            python_parity_rule=_require_manifest_string(data, "python_parity_rule", context),
            schema_compatibility_rule=_require_manifest_string(
                data,
                "schema_compatibility_rule",
                context,
            ),
            minimum_primary_metric_improvement_pct=_require_manifest_float(
                data,
                "minimum_primary_metric_improvement_pct",
                context,
            ),
            maximum_adjacent_metric_regression_pct=_require_manifest_float(
                data,
                "maximum_adjacent_metric_regression_pct",
                context,
            ),
            benchmark_exception_rule=_require_manifest_string(
                data,
                "benchmark_exception_rule",
                context,
            ),
            rollback_scope_rule=_require_manifest_string(data, "rollback_scope_rule", context),
            tenant_isolation_rule=_require_manifest_string(
                data,
                "tenant_isolation_rule",
                context,
            ),
            replay_compatibility_rule=_require_manifest_string(
                data,
                "replay_compatibility_rule",
                context,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeModuleManifestEntry:
    name: RuntimeModuleId
    function_count: int
    capability_id: str = ""
    owner: str = ""
    contract_boundary: str = ""
    functions: list[str] = field(default_factory=list)
    layer: RuntimeLayer = RuntimeLayer.mojo_llm_runtime_core
    maturity: RuntimeMaturity = RuntimeMaturity.experimental
    public_supported_channels: list[RuntimeSupportedChannel] = field(default_factory=list)
    validated_auxiliary_channels: list[RuntimeAuxiliaryChannel] = field(default_factory=list)
    feature_flag_channels: list[RuntimeFeatureFlagChannel] = field(default_factory=list)
    proof_obligations: list[RuntimeProofObligation] = field(default_factory=list)
    proof_artifacts: list[str] = field(default_factory=list)
    promotion_status: RuntimeKernelPromotionStatus | None = None
    rollback_flag: str | None = None
    benchmark_report_ref: str | None = None
    parity_report_ref: str | None = None
    schema_compat_report_ref: str | None = None
    isolation_proof_ref: str | None = None
    replay_proof_ref: str | None = None
    benchmark_artifact: str = ""
    benchmark_speedup_x: float = 0.0
    compiled_artifact: str = ""
    compiled_engine: RuntimeCompiledEngine = RuntimeCompiledEngine.mojo
    max_cold_ms: float = 0.0
    max_warm_ms: float = 0.0
    max_hot_ms: float = 0.0

    @classmethod
    def from_api(cls, payload: Any, context: str = "modules") -> RuntimeModuleManifestEntry:
        data = coerce_payload_mapping(payload)
        function_count = _require_manifest_integer(data, "function_count", context)
        functions = _ensure_unique_manifest_values(
            _optional_manifest_string_list(data, "functions", context),
            f"{context}.functions",
        )
        if function_count != len(functions):
            raise ValueError(
                f"{context}.functions must contain exactly {function_count} entries to match "
                "function_count."
            )
        promotion_status = (
            _coerce_enum(
                data["promotion_status"],
                RuntimeKernelPromotionStatus,
                f"{context}.promotion_status",
            )
            if data.get("promotion_status") is not None
            else None
        )
        record = cls(
            name=_coerce_enum(data["name"], RuntimeModuleId, f"{context}.name"),
            function_count=function_count,
            capability_id=_optional_manifest_string(data, "capability_id", context),
            owner=_optional_manifest_string(data, "owner", context),
            contract_boundary=_optional_manifest_string(data, "contract_boundary", context),
            functions=functions,
            layer=_coerce_enum(data["layer"], RuntimeLayer, f"{context}.layer"),
            maturity=_coerce_enum(data["maturity"], RuntimeMaturity, f"{context}.maturity"),
            public_supported_channels=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("public_supported_channels"),
                    RuntimeSupportedChannel,
                    f"{context}.public_supported_channels",
                ),
                f"{context}.public_supported_channels",
            ),
            validated_auxiliary_channels=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("validated_auxiliary_channels"),
                    RuntimeAuxiliaryChannel,
                    f"{context}.validated_auxiliary_channels",
                ),
                f"{context}.validated_auxiliary_channels",
            ),
            feature_flag_channels=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("feature_flag_channels"),
                    RuntimeFeatureFlagChannel,
                    f"{context}.feature_flag_channels",
                ),
                f"{context}.feature_flag_channels",
            ),
            proof_obligations=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("proof_obligations"),
                    RuntimeProofObligation,
                    f"{context}.proof_obligations",
                ),
                f"{context}.proof_obligations",
            ),
            proof_artifacts=_ensure_unique_manifest_values(
                _optional_manifest_string_list(data, "proof_artifacts", context),
                f"{context}.proof_artifacts",
            ),
            promotion_status=promotion_status,
            rollback_flag=_optional_manifest_string(data, "rollback_flag", context),
            benchmark_report_ref=_optional_manifest_string(
                data,
                "benchmark_report_ref",
                context,
            ),
            parity_report_ref=_optional_manifest_string(data, "parity_report_ref", context),
            schema_compat_report_ref=_optional_manifest_string(
                data,
                "schema_compat_report_ref",
                context,
            ),
            isolation_proof_ref=_optional_manifest_string(
                data,
                "isolation_proof_ref",
                context,
            ),
            replay_proof_ref=_optional_manifest_string(data, "replay_proof_ref", context),
            benchmark_artifact=_require_manifest_string(data, "benchmark_artifact", context),
            benchmark_speedup_x=_require_manifest_float(data, "benchmark_speedup_x", context),
            compiled_artifact=_require_manifest_string(data, "compiled_artifact", context),
            compiled_engine=_coerce_enum(
                data["compiled_engine"],
                RuntimeCompiledEngine,
                f"{context}.compiled_engine",
            ),
            max_cold_ms=_require_manifest_float(data, "max_cold_ms", context),
            max_warm_ms=_require_manifest_float(data, "max_warm_ms", context),
            max_hot_ms=_require_manifest_float(data, "max_hot_ms", context),
        )
        if record.promotion_status is RuntimeKernelPromotionStatus.shipping:
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
                value = getattr(record, field_name)
                if value is None or not str(value).strip():
                    raise ValueError(
                        f"{context}.{field_name} must be provided for shipping runtime modules."
                    )
        return record

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeDeploymentModes:
    current: RuntimeDeploymentMode = RuntimeDeploymentMode.local_dev_daemon
    supported_modes: list[RuntimeDeploymentMode] = field(default_factory=list)
    rule: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeDeploymentModes:
        data = coerce_payload_mapping(payload)
        return cls(
            current=_coerce_enum(
                data["current"],
                RuntimeDeploymentMode,
                "deployment_modes.current",
            ),
            supported_modes=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("supported_modes"),
                    RuntimeDeploymentMode,
                    "deployment_modes.supported_modes",
                ),
                "deployment_modes.supported_modes",
            ),
            rule=_require_manifest_string(data, "rule", "deployment_modes"),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeShippingContractSummary:
    module_count: int
    function_count: int
    runtime_core_layer: RuntimeLayer
    benchmark_discovery_rule: RuntimeBenchmarkDiscoveryRule

    @classmethod
    def from_api(
        cls,
        payload: Any,
        context: str = "shipping_contract",
    ) -> RuntimeShippingContractSummary:
        data = coerce_payload_mapping(payload)
        return cls(
            module_count=_require_manifest_integer(data, "module_count", context),
            function_count=_require_manifest_integer(data, "function_count", context),
            runtime_core_layer=_coerce_enum(
                data["runtime_core_layer"],
                RuntimeLayer,
                f"{context}.runtime_core_layer",
            ),
            benchmark_discovery_rule=_coerce_enum(
                data["benchmark_discovery_rule"],
                RuntimeBenchmarkDiscoveryRule,
                f"{context}.benchmark_discovery_rule",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeBenchmarkDiscoverySourceModuleEntry:
    import_path: str
    public_function_count: int

    @classmethod
    def from_api(
        cls,
        payload: Any,
        context: str = "benchmark_discovery_lane.discovered_source_inventory",
    ) -> RuntimeBenchmarkDiscoverySourceModuleEntry:
        data = coerce_payload_mapping(payload)
        public_function_count = _require_manifest_integer(data, "public_function_count", context)
        if public_function_count <= 0:
            raise ValueError(f"{context}.public_function_count must be greater than 0.")
        return cls(
            import_path=_require_manifest_string(data, "import_path", context),
            public_function_count=public_function_count,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeBenchmarkDiscoveryLane:
    discovered_source_modules: int
    discovered_public_functions: int
    discovered_source_inventory: list["RuntimeBenchmarkDiscoverySourceModuleEntry"]
    shipping_manifest_modules: int
    shipping_manifest_functions: int
    non_shipping_rule: RuntimeNonShippingRule

    @classmethod
    def from_api(
        cls,
        payload: Any,
        context: str = "benchmark_discovery_lane",
    ) -> RuntimeBenchmarkDiscoveryLane:
        data = coerce_payload_mapping(payload)
        raw_discovered_source_inventory = data.get("discovered_source_inventory")
        if not isinstance(raw_discovered_source_inventory, list):
            raise ValueError("benchmark_discovery_lane.discovered_source_inventory must be a list.")
        discovered_source_inventory = [
            RuntimeBenchmarkDiscoverySourceModuleEntry.from_api(
                item,
                f"{context}.discovered_source_inventory.{index}",
            )
            for index, item in enumerate(raw_discovered_source_inventory)
        ]
        _ensure_unique_manifest_values(
            discovered_source_inventory,
            f"{context}.discovered_source_inventory",
            value_selector=lambda entry: entry.import_path,
        )
        discovered_import_paths = [entry.import_path for entry in discovered_source_inventory]
        if discovered_import_paths != sorted(discovered_import_paths):
            raise ValueError(
                f"{context}.discovered_source_inventory must be sorted by import_path."
            )
        discovered_public_functions = _require_manifest_integer(
            data,
            "discovered_public_functions",
            context,
        )
        if len(discovered_source_inventory) != _require_manifest_integer(
            data,
            "discovered_source_modules",
            context,
        ):
            raise ValueError(
                f"{context}.discovered_source_modules must equal the number of discovered_source_inventory entries."
            )
        total_public_functions = sum(
            entry.public_function_count for entry in discovered_source_inventory
        )
        if total_public_functions != discovered_public_functions:
            raise ValueError(
                f"{context}.discovered_public_functions must equal the total discovered_source_inventory public_function_count."
            )
        shipping_manifest_modules = _require_manifest_integer(
            data,
            "shipping_manifest_modules",
            context,
        )
        if shipping_manifest_modules > len(discovered_source_inventory):
            raise ValueError(
                f"{context}.shipping_manifest_modules cannot exceed {context}.discovered_source_modules."
            )
        shipping_manifest_functions = _require_manifest_integer(
            data,
            "shipping_manifest_functions",
            context,
        )
        if shipping_manifest_functions > discovered_public_functions:
            raise ValueError(
                f"{context}.shipping_manifest_functions cannot exceed {context}.discovered_public_functions."
            )
        return cls(
            discovered_source_modules=len(discovered_source_inventory),
            discovered_public_functions=discovered_public_functions,
            discovered_source_inventory=discovered_source_inventory,
            shipping_manifest_modules=shipping_manifest_modules,
            shipping_manifest_functions=shipping_manifest_functions,
            non_shipping_rule=_coerce_enum(
                data["non_shipping_rule"],
                RuntimeNonShippingRule,
                f"{context}.non_shipping_rule",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeAdvertisedCapabilities:
    runtime_modules: list[RuntimeModuleId] = field(default_factory=list)
    public_endpoints: list[RuntimePublicEndpoint] = field(default_factory=list)
    admin_endpoints: list[RuntimeAdminEndpoint] = field(default_factory=list)
    feature_flag_endpoints: list[RuntimeFeatureFlagEndpoint] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeAdvertisedCapabilities:
        data = coerce_payload_mapping(payload)
        return cls(
            runtime_modules=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("runtime_modules"),
                    RuntimeModuleId,
                    "advertised_capabilities.runtime_modules",
                ),
                "advertised_capabilities.runtime_modules",
            ),
            public_endpoints=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("public_endpoints"),
                    RuntimePublicEndpoint,
                    "advertised_capabilities.public_endpoints",
                ),
                "advertised_capabilities.public_endpoints",
            ),
            admin_endpoints=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("admin_endpoints"),
                    RuntimeAdminEndpoint,
                    "advertised_capabilities.admin_endpoints",
                ),
                "advertised_capabilities.admin_endpoints",
            ),
            feature_flag_endpoints=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("feature_flag_endpoints"),
                    RuntimeFeatureFlagEndpoint,
                    "advertised_capabilities.feature_flag_endpoints",
                ),
                "advertised_capabilities.feature_flag_endpoints",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeNamedRule:
    name: RuntimeInvariantName
    statement: str

    @classmethod
    def from_api(cls, payload: Any, context: str = "system_invariants") -> RuntimeNamedRule:
        data = coerce_payload_mapping(payload)
        return cls(
            name=_coerce_enum(data["name"], RuntimeInvariantName, f"{context}.name"),
            statement=_require_manifest_string(data, "statement", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeExecutionModel:
    state_fields: list[RuntimeExecutionStateField] = field(default_factory=list)
    allowed_transitions: list[RuntimeExecutionTransition] = field(default_factory=list)
    validity_rules: list[RuntimeExecutionValidityRule] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeExecutionModel:
        data = coerce_payload_mapping(payload)
        return cls(
            state_fields=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("state_fields"),
                    RuntimeExecutionStateField,
                    "execution_model.state_fields",
                ),
                "execution_model.state_fields",
            ),
            allowed_transitions=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("allowed_transitions"),
                    RuntimeExecutionTransition,
                    "execution_model.allowed_transitions",
                ),
                "execution_model.allowed_transitions",
            ),
            validity_rules=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("validity_rules"),
                    RuntimeExecutionValidityRule,
                    "execution_model.validity_rules",
                ),
                "execution_model.validity_rules",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeExternalNondeterminismPolicy:
    sources: list[RuntimeExternalNondeterminismSource] = field(default_factory=list)
    rule: str = ""
    required_artifacts: list[RuntimeNondeterminismArtifact] = field(default_factory=list)
    failure_codes: list[RuntimeFailureCode] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeExternalNondeterminismPolicy:
        data = coerce_payload_mapping(payload)
        return cls(
            sources=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("sources"),
                    RuntimeExternalNondeterminismSource,
                    "external_nondeterminism.sources",
                ),
                "external_nondeterminism.sources",
            ),
            rule=_require_manifest_string(data, "rule", "external_nondeterminism"),
            required_artifacts=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("required_artifacts"),
                    RuntimeNondeterminismArtifact,
                    "external_nondeterminism.required_artifacts",
                ),
                "external_nondeterminism.required_artifacts",
            ),
            failure_codes=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("failure_codes"),
                    RuntimeFailureCode,
                    "external_nondeterminism.failure_codes",
                ),
                "external_nondeterminism.failure_codes",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeArtifactLineageSchema:
    artifact_flow: list[RuntimeArtifactLineageStep] = field(default_factory=list)
    required_node_fields: list[RuntimeLineageNodeField] = field(default_factory=list)
    immutability_rule: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeArtifactLineageSchema:
        data = coerce_payload_mapping(payload)
        return cls(
            artifact_flow=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("artifact_flow"),
                    RuntimeArtifactLineageStep,
                    "artifact_lineage.artifact_flow",
                ),
                "artifact_lineage.artifact_flow",
            ),
            required_node_fields=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("required_node_fields"),
                    RuntimeLineageNodeField,
                    "artifact_lineage.required_node_fields",
                ),
                "artifact_lineage.required_node_fields",
            ),
            immutability_rule=_require_manifest_string(
                data,
                "immutability_rule",
                "artifact_lineage",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeCapabilityEnums:
    side_effect_class: list[RuntimeSideEffectClass] = field(default_factory=list)
    risk_level: list[RuntimeRiskLevel] = field(default_factory=list)
    replayability: list[RuntimeReplayability] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeCapabilityEnums:
        data = coerce_payload_mapping(payload)
        return cls(
            side_effect_class=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("side_effect_class"),
                    RuntimeSideEffectClass,
                    "capability_algebra.enums.side_effect_class",
                ),
                "capability_algebra.enums.side_effect_class",
            ),
            risk_level=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("risk_level"),
                    RuntimeRiskLevel,
                    "capability_algebra.enums.risk_level",
                ),
                "capability_algebra.enums.risk_level",
            ),
            replayability=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("replayability"),
                    RuntimeReplayability,
                    "capability_algebra.enums.replayability",
                ),
                "capability_algebra.enums.replayability",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeCapabilityAlgebraSchema:
    required_fields: list[RuntimeCapabilityField] = field(default_factory=list)
    enums: RuntimeCapabilityEnums = field(default_factory=RuntimeCapabilityEnums)
    rules: list[RuntimeCapabilityRule] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeCapabilityAlgebraSchema:
        data = coerce_payload_mapping(payload)
        return cls(
            required_fields=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("required_fields"),
                    RuntimeCapabilityField,
                    "capability_algebra.required_fields",
                ),
                "capability_algebra.required_fields",
            ),
            enums=RuntimeCapabilityEnums.from_api(data.get("enums") or {}),
            rules=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("rules"),
                    RuntimeCapabilityRule,
                    "capability_algebra.rules",
                ),
                "capability_algebra.rules",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeLayerProofMatrixEntry:
    layer: RuntimeLayer
    status: RuntimeMaturity
    obligations: list[RuntimeProofObligation] = field(default_factory=list)
    evidence_paths: list[str] = field(default_factory=list)

    @classmethod
    def from_api(
        cls,
        payload: Any,
        context: str = "proof_matrix",
    ) -> RuntimeLayerProofMatrixEntry:
        data = coerce_payload_mapping(payload)
        return cls(
            layer=_coerce_enum(data["layer"], RuntimeLayer, f"{context}.layer"),
            status=_coerce_enum(data["status"], RuntimeMaturity, f"{context}.status"),
            obligations=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("obligations"),
                    RuntimeProofObligation,
                    f"{context}.obligations",
                ),
                f"{context}.obligations",
            ),
            evidence_paths=_ensure_unique_manifest_values(
                _optional_manifest_string_list(data, "evidence_paths", context),
                f"{context}.evidence_paths",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeBenchmarkClassEntry:
    code: RuntimeBenchmarkClassCode
    description: str
    evidence_paths: list[str] = field(default_factory=list)

    @classmethod
    def from_api(
        cls,
        payload: Any,
        context: str = "benchmarking.classes",
    ) -> RuntimeBenchmarkClassEntry:
        data = coerce_payload_mapping(payload)
        return cls(
            code=_coerce_enum(data["code"], RuntimeBenchmarkClassCode, f"{context}.code"),
            description=_require_manifest_string(data, "description", context),
            evidence_paths=_ensure_unique_manifest_values(
                _optional_manifest_string_list(data, "evidence_paths", context),
                f"{context}.evidence_paths",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeBenchmarkFramework:
    classes: list[RuntimeBenchmarkClassEntry] = field(default_factory=list)
    required_metrics: list[RuntimeBenchmarkMetric] = field(default_factory=list)
    baselines: list[RuntimeBenchmarkBaseline] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeBenchmarkFramework:
        data = coerce_payload_mapping(payload)
        classes = [
            RuntimeBenchmarkClassEntry.from_api(item, f"benchmarking.classes.{index}")
            for index, item in enumerate(data.get("classes") or [])
        ]
        _ensure_unique_manifest_values(
            classes,
            "benchmarking.classes",
            value_selector=lambda entry: entry.code,
        )
        return cls(
            classes=classes,
            required_metrics=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("required_metrics"),
                    RuntimeBenchmarkMetric,
                    "benchmarking.required_metrics",
                ),
                "benchmarking.required_metrics",
            ),
            baselines=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("baselines"),
                    RuntimeBenchmarkBaseline,
                    "benchmarking.baselines",
                ),
                "benchmarking.baselines",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeSLOBudget:
    name: RuntimeSLOBudgetName
    applies_to: RuntimeSLOBudgetAppliesTo
    p95_objective_ms: float
    hard_ceiling_ms: float | None = None
    notes: str | None = None

    @classmethod
    def from_api(cls, payload: Any, context: str = "slo_budgets") -> RuntimeSLOBudget:
        data = coerce_payload_mapping(payload)
        return cls(
            name=_coerce_enum(data["name"], RuntimeSLOBudgetName, f"{context}.name"),
            applies_to=_coerce_enum(
                _require_manifest_string(data, "applies_to", context),
                RuntimeSLOBudgetAppliesTo,
                f"{context}.applies_to",
            ),
            p95_objective_ms=_require_manifest_float(data, "p95_objective_ms", context),
            hard_ceiling_ms=_optional_manifest_float(data, "hard_ceiling_ms", context),
            notes=_optional_manifest_string(data, "notes", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeSchedulerModel:
    policies: list[RuntimeSchedulerPolicy] = field(default_factory=list)
    minimize: list[RuntimeSchedulerMinimizeObjective] = field(default_factory=list)
    maximize: list[RuntimeSchedulerMaximizeObjective] = field(default_factory=list)
    invariants: list[RuntimeSchedulerInvariant] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeSchedulerModel:
        data = coerce_payload_mapping(payload)
        return cls(
            policies=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("policies"),
                    RuntimeSchedulerPolicy,
                    "scheduler_model.policies",
                ),
                "scheduler_model.policies",
            ),
            minimize=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("minimize"),
                    RuntimeSchedulerMinimizeObjective,
                    "scheduler_model.minimize",
                ),
                "scheduler_model.minimize",
            ),
            maximize=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("maximize"),
                    RuntimeSchedulerMaximizeObjective,
                    "scheduler_model.maximize",
                ),
                "scheduler_model.maximize",
            ),
            invariants=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("invariants"),
                    RuntimeSchedulerInvariant,
                    "scheduler_model.invariants",
                ),
                "scheduler_model.invariants",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeMemoryModel:
    regions: list[RuntimeMemoryRegion] = field(default_factory=list)
    rules: list[RuntimeMemoryRule] = field(default_factory=list)
    failure_codes: list[RuntimeFailureCode] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeMemoryModel:
        data = coerce_payload_mapping(payload)
        return cls(
            regions=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("regions"),
                    RuntimeMemoryRegion,
                    "memory_model.regions",
                ),
                "memory_model.regions",
            ),
            rules=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("rules"),
                    RuntimeMemoryRule,
                    "memory_model.rules",
                ),
                "memory_model.rules",
            ),
            failure_codes=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("failure_codes"),
                    RuntimeFailureCode,
                    "memory_model.failure_codes",
                ),
                "memory_model.failure_codes",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeEvaluationScience:
    dimensions: list[RuntimeEvaluationDimension] = field(default_factory=list)
    methods: list[RuntimeEvaluationMethod] = field(default_factory=list)
    release_blockers: list[RuntimeReleaseBlocker] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeEvaluationScience:
        data = coerce_payload_mapping(payload)
        return cls(
            dimensions=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("dimensions"),
                    RuntimeEvaluationDimension,
                    "evaluation_science.dimensions",
                ),
                "evaluation_science.dimensions",
            ),
            methods=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("methods"),
                    RuntimeEvaluationMethod,
                    "evaluation_science.methods",
                ),
                "evaluation_science.methods",
            ),
            release_blockers=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("release_blockers"),
                    RuntimeReleaseBlocker,
                    "evaluation_science.release_blockers",
                ),
                "evaluation_science.release_blockers",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeThreatModel:
    threat_classes: list[RuntimeThreatClass] = field(default_factory=list)
    controls: list[RuntimeThreatControl] = field(default_factory=list)
    non_negotiable_rules: list[RuntimeThreatRule] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeThreatModel:
        data = coerce_payload_mapping(payload)
        return cls(
            threat_classes=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("threat_classes"),
                    RuntimeThreatClass,
                    "threat_model.threat_classes",
                ),
                "threat_model.threat_classes",
            ),
            controls=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("controls"),
                    RuntimeThreatControl,
                    "threat_model.controls",
                ),
                "threat_model.controls",
            ),
            non_negotiable_rules=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("non_negotiable_rules"),
                    RuntimeThreatRule,
                    "threat_model.non_negotiable_rules",
                ),
                "threat_model.non_negotiable_rules",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeTypedFailure:
    code: RuntimeFailureCode
    description: str

    @classmethod
    def from_api(cls, payload: Any, context: str = "typed_failures") -> RuntimeTypedFailure:
        data = coerce_payload_mapping(payload)
        return cls(
            code=_coerce_enum(data["code"], RuntimeFailureCode, f"{context}.code"),
            description=_require_manifest_string(data, "description", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeFormalReleaseTheorem:
    statement: str
    required_conditions: list[RuntimeReleaseCondition] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeFormalReleaseTheorem:
        data = coerce_payload_mapping(payload)
        required_conditions = _ensure_unique_manifest_values(
            _coerce_enum_list(
                data.get("required_conditions"),
                RuntimeReleaseCondition,
                "formal_release_theorem.required_conditions",
            ),
            "formal_release_theorem.required_conditions",
        )
        return cls(
            statement=_require_manifest_string(data, "statement", "formal_release_theorem"),
            required_conditions=required_conditions,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeReleaseArtifactBundle:
    required_artifacts: list[RuntimeReleaseArtifact] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeReleaseArtifactBundle:
        data = coerce_payload_mapping(payload)
        return cls(
            required_artifacts=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("required_artifacts"),
                    RuntimeReleaseArtifact,
                    "release_artifact_bundle.required_artifacts",
                ),
                "release_artifact_bundle.required_artifacts",
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeReleaseGate:
    gate: RuntimeReleaseGateId
    description: str

    @classmethod
    def from_api(cls, payload: Any, context: str = "release_gates") -> RuntimeReleaseGate:
        data = coerce_payload_mapping(payload)
        return cls(
            gate=_coerce_enum(data["gate"], RuntimeReleaseGateId, f"{context}.gate"),
            description=_require_manifest_string(data, "description", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeImmediateImplementationPR:
    pr: str
    focus: str
    deliverables: list[str] = field(default_factory=list)

    @classmethod
    def from_api(
        cls,
        payload: Any,
        context: str = "immediate_implementation_sequence",
    ) -> RuntimeImmediateImplementationPR:
        data = coerce_payload_mapping(payload)
        return cls(
            pr=_require_manifest_string(data, "pr", context),
            focus=_require_manifest_string(data, "focus", context),
            deliverables=_optional_manifest_string_list(data, "deliverables", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeAdminModuleSummary:
    module_count: int
    function_count: int
    maturity_counts: dict[RuntimeMaturity, int] = field(default_factory=dict)
    layer_counts: dict[RuntimeLayer, int] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeAdminModuleSummary:
        data = coerce_payload_mapping(payload)
        return cls(
            module_count=_require_manifest_integer(data, "module_count", "summary"),
            function_count=_require_manifest_integer(data, "function_count", "summary"),
            maturity_counts=_coerce_enum_mapping(
                data.get("maturity_counts"),
                RuntimeMaturity,
                lambda raw_value, key: _require_manifest_integer_value(
                    raw_value,
                    f"summary.maturity_counts.{key.value}",
                ),
                "summary.maturity_counts",
            ),
            layer_counts=_coerce_enum_mapping(
                data.get("layer_counts"),
                RuntimeLayer,
                lambda raw_value, key: _require_manifest_integer_value(
                    raw_value,
                    f"summary.layer_counts.{key.value}",
                ),
                "summary.layer_counts",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeAdminEvaluationSummary:
    dimension_count: int
    method_count: int
    release_blocker_count: int
    benchmark_class_count: int
    slo_budget_count: int
    replay_gate_enabled: bool
    tool_call_quality_gate_enabled: bool
    rag_quality_gate_enabled: bool
    decision_quality_gate_enabled: bool

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeAdminEvaluationSummary:
        data = coerce_payload_mapping(payload)
        return cls(
            dimension_count=_require_manifest_integer(data, "dimension_count", "evaluation_summary"),
            method_count=_require_manifest_integer(data, "method_count", "evaluation_summary"),
            release_blocker_count=_require_manifest_integer(
                data,
                "release_blocker_count",
                "evaluation_summary",
            ),
            benchmark_class_count=_require_manifest_integer(
                data,
                "benchmark_class_count",
                "evaluation_summary",
            ),
            slo_budget_count=_require_manifest_integer(data, "slo_budget_count", "evaluation_summary"),
            replay_gate_enabled=_require_manifest_boolean(
                data,
                "replay_gate_enabled",
                "evaluation_summary",
            ),
            tool_call_quality_gate_enabled=_require_manifest_boolean(
                data,
                "tool_call_quality_gate_enabled",
                "evaluation_summary",
            ),
            rag_quality_gate_enabled=_require_manifest_boolean(
                data,
                "rag_quality_gate_enabled",
                "evaluation_summary",
            ),
            decision_quality_gate_enabled=_require_manifest_boolean(
                data,
                "decision_quality_gate_enabled",
                "evaluation_summary",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeAdminModulesOutput:
    runtime_version: str
    llm_core_manifest: str
    module_manifest_version: str
    shipping_contract: RuntimeShippingContractSummary = field(
        default_factory=lambda: RuntimeShippingContractSummary(0, 0, "", "")
    )
    summary: RuntimeAdminModuleSummary = field(
        default_factory=lambda: RuntimeAdminModuleSummary(0, 0, {}, {})
    )
    proof_matrix: list[RuntimeLayerProofMatrixEntry] = field(default_factory=list)
    modules: list[RuntimeModuleManifestEntry] = field(default_factory=list)
    manifest_digest: str = ""
    signature: RuntimeManifestSignature = field(
        default_factory=lambda: RuntimeManifestSignature(
            RuntimeSignatureAlgorithm.hmac_sha256,
            "",
            "",
            "",
            RuntimeSignatureScope.control_plane_hmac_v1,
        )
    )

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeAdminModulesOutput:
        data = coerce_payload_mapping(payload)
        proof_matrix = [
            RuntimeLayerProofMatrixEntry.from_api(item, f"proof_matrix.{index}")
            for index, item in enumerate(data.get("proof_matrix") or [])
        ]
        modules = [
            RuntimeModuleManifestEntry.from_api(item, f"modules.{index}")
            for index, item in enumerate(data.get("modules") or [])
        ]
        _ensure_unique_manifest_values(
            proof_matrix,
            "proof_matrix",
            value_selector=lambda entry: entry.layer,
        )
        _ensure_unique_manifest_values(
            modules,
            "modules",
            value_selector=lambda entry: entry.name,
        )
        shipping_contract = RuntimeShippingContractSummary.from_api(
            data["shipping_contract"],
            "shipping_contract",
        )
        summary = RuntimeAdminModuleSummary.from_api(data["summary"])
        total_functions = sum(module.function_count for module in modules)
        if shipping_contract.module_count != len(modules):
            raise ValueError(
                "shipping_contract.module_count must equal the number of manifest modules."
            )
        if shipping_contract.function_count != total_functions:
            raise ValueError(
                "shipping_contract.function_count must equal the total module function_count."
            )
        if summary.module_count != len(modules):
            raise ValueError("summary.module_count must equal the number of manifest modules.")
        if summary.function_count != total_functions:
            raise ValueError("summary.function_count must equal the total module function_count.")
        expected_maturity_counts = _count_manifest_values([module.maturity for module in modules])
        if summary.maturity_counts != expected_maturity_counts:
            raise ValueError(
                "summary.maturity_counts must equal the module maturity distribution."
            )
        expected_layer_counts = _count_manifest_values([module.layer for module in modules])
        if summary.layer_counts != expected_layer_counts:
            raise ValueError("summary.layer_counts must equal the module layer distribution.")
        return cls(
            runtime_version=_require_manifest_string(data, "runtime_version", "runtime_admin_modules"),
            llm_core_manifest=_require_manifest_string(data, "llm_core_manifest", "runtime_admin_modules"),
            module_manifest_version=_require_manifest_string(
                data,
                "module_manifest_version",
                "runtime_admin_modules",
            ),
            shipping_contract=shipping_contract,
            summary=summary,
            proof_matrix=proof_matrix,
            modules=modules,
            manifest_digest=_require_manifest_string(
                data,
                "manifest_digest",
                "runtime_admin_modules",
            ),
            signature=RuntimeManifestSignature.from_api(data["signature"], "signature"),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeBenchmarkModuleEntry:
    name: RuntimeModuleId
    function_count: int
    benchmark_artifact: str
    benchmark_speedup_x: float
    compiled_artifact: str
    compiled_engine: RuntimeCompiledEngine
    max_cold_ms: float
    max_warm_ms: float
    max_hot_ms: float

    @classmethod
    def from_api(
        cls,
        payload: Any,
        context: str = "module_benchmarks",
    ) -> RuntimeBenchmarkModuleEntry:
        data = coerce_payload_mapping(payload)
        return cls(
            name=_coerce_enum(data["name"], RuntimeModuleId, f"{context}.name"),
            function_count=_require_manifest_integer(data, "function_count", context),
            benchmark_artifact=_require_manifest_string(data, "benchmark_artifact", context),
            benchmark_speedup_x=_require_manifest_float(data, "benchmark_speedup_x", context),
            compiled_artifact=_require_manifest_string(data, "compiled_artifact", context),
            compiled_engine=_coerce_enum(
                data["compiled_engine"],
                RuntimeCompiledEngine,
                f"{context}.compiled_engine",
            ),
            max_cold_ms=_require_manifest_float(data, "max_cold_ms", context),
            max_warm_ms=_require_manifest_float(data, "max_warm_ms", context),
            max_hot_ms=_require_manifest_float(data, "max_hot_ms", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeAdminBenchmarksOutput:
    runtime_version: str
    llm_core_manifest: str
    module_manifest_version: str
    benchmark_discovery_lane: RuntimeBenchmarkDiscoveryLane = field(
        default_factory=lambda: RuntimeBenchmarkDiscoveryLane(
            0,
            0,
            [],
            0,
            0,
            RuntimeNonShippingRule.broader_mojo_inventory_not_advertised,
        )
    )
    benchmarking: RuntimeBenchmarkFramework = field(default_factory=RuntimeBenchmarkFramework)
    slo_budgets: list[RuntimeSLOBudget] = field(default_factory=list)
    quality_gate_benchmark_classes: list[RuntimeBenchmarkClassEntry] = field(default_factory=list)
    quality_gate_slo_budgets: list[RuntimeSLOBudget] = field(default_factory=list)
    evaluation_science: RuntimeEvaluationScience = field(default_factory=RuntimeEvaluationScience)
    evaluation_summary: RuntimeAdminEvaluationSummary = field(
        default_factory=lambda: RuntimeAdminEvaluationSummary(0, 0, 0, 0, 0, False, False, False, False)
    )
    compiled_artifacts: list[RuntimeArtifactReference] = field(default_factory=list)
    shipping_runtime_modules: list[RuntimeModuleId] = field(default_factory=list)
    shipping_runtime_function_counts: list[int] = field(default_factory=list)
    shipping_runtime_benchmark_speedups_x: list[float] = field(default_factory=list)
    shipping_runtime_benchmark_artifacts: list[str] = field(default_factory=list)
    shipping_runtime_compiled_artifacts: list[str] = field(default_factory=list)
    shipping_runtime_compiled_engines: list[RuntimeCompiledEngine] = field(default_factory=list)
    shipping_runtime_max_cold_ms: list[float] = field(default_factory=list)
    shipping_runtime_max_warm_ms: list[float] = field(default_factory=list)
    shipping_runtime_max_hot_ms: list[float] = field(default_factory=list)
    module_benchmarks: list[RuntimeBenchmarkModuleEntry] = field(default_factory=list)
    manifest_digest: str = ""
    signature: RuntimeManifestSignature = field(
        default_factory=lambda: RuntimeManifestSignature(
            RuntimeSignatureAlgorithm.hmac_sha256,
            "",
            "",
            "",
            RuntimeSignatureScope.control_plane_hmac_v1,
        )
    )

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeAdminBenchmarksOutput:
        data = coerce_payload_mapping(payload)
        benchmarking = RuntimeBenchmarkFramework.from_api(data.get("benchmarking") or {})
        slo_budgets = [
            RuntimeSLOBudget.from_api(item, f"slo_budgets.{index}")
            for index, item in enumerate(data.get("slo_budgets") or [])
        ]
        module_benchmarks = [
            RuntimeBenchmarkModuleEntry.from_api(item, f"module_benchmarks.{index}")
            for index, item in enumerate(data.get("module_benchmarks") or [])
        ]
        _ensure_unique_manifest_values(
            module_benchmarks,
            "module_benchmarks",
            value_selector=lambda entry: entry.name,
        )
        benchmark_discovery_lane = RuntimeBenchmarkDiscoveryLane.from_api(
            data["benchmark_discovery_lane"],
            "benchmark_discovery_lane",
        )
        quality_gate_benchmark_classes = _ensure_unique_manifest_values(
            [
                RuntimeBenchmarkClassEntry.from_api(
                    item,
                    f"quality_gate_benchmark_classes.{index}",
                )
                for index, item in enumerate(data.get("quality_gate_benchmark_classes") or [])
            ],
            "quality_gate_benchmark_classes",
            value_selector=lambda entry: entry.code,
        )
        quality_gate_slo_budgets = _ensure_unique_manifest_values(
            [
                RuntimeSLOBudget.from_api(item, f"quality_gate_slo_budgets.{index}")
                for index, item in enumerate(data.get("quality_gate_slo_budgets") or [])
            ],
            "quality_gate_slo_budgets",
            value_selector=lambda entry: entry.name,
        )
        evaluation_science = RuntimeEvaluationScience.from_api(
            data.get("evaluation_science") or {}
        )
        evaluation_summary = RuntimeAdminEvaluationSummary.from_api(
            data.get("evaluation_summary") or {}
        )
        compiled_artifacts = _ensure_unique_manifest_values(
            [
                RuntimeArtifactReference.from_api(item, f"compiled_artifacts.{index}")
                for index, item in enumerate(data.get("compiled_artifacts") or [])
            ],
            "compiled_artifacts",
            value_selector=lambda entry: entry.path,
        )
        raw_shipping_runtime_modules = data.get("shipping_runtime_modules")
        if not isinstance(raw_shipping_runtime_modules, list):
            raise ValueError("shipping_runtime_modules must be a list.")
        shipping_runtime_modules = _ensure_unique_manifest_values(
            [
                _coerce_enum(item, RuntimeModuleId, f"shipping_runtime_modules.{index}")
                for index, item in enumerate(raw_shipping_runtime_modules)
            ],
            "shipping_runtime_modules",
        )
        raw_shipping_runtime_function_counts = data.get("shipping_runtime_function_counts")
        if not isinstance(raw_shipping_runtime_function_counts, list):
            raise ValueError("shipping_runtime_function_counts must be a list.")
        shipping_runtime_function_counts = [
            _require_manifest_integer(
                {"value": item},
                "value",
                f"shipping_runtime_function_counts.{index}",
            )
            for index, item in enumerate(raw_shipping_runtime_function_counts)
        ]
        raw_shipping_runtime_benchmark_speedups_x = data.get(
            "shipping_runtime_benchmark_speedups_x"
        )
        if not isinstance(raw_shipping_runtime_benchmark_speedups_x, list):
            raise ValueError("shipping_runtime_benchmark_speedups_x must be a list.")
        shipping_runtime_benchmark_speedups_x = [
            _require_manifest_float(
                {"value": item},
                "value",
                f"shipping_runtime_benchmark_speedups_x.{index}",
            )
            for index, item in enumerate(raw_shipping_runtime_benchmark_speedups_x)
        ]
        raw_shipping_runtime_benchmark_artifacts = data.get("shipping_runtime_benchmark_artifacts")
        if not isinstance(raw_shipping_runtime_benchmark_artifacts, list):
            raise ValueError("shipping_runtime_benchmark_artifacts must be a list.")
        shipping_runtime_benchmark_artifacts = [
            _require_manifest_string(
                {"value": item},
                "value",
                f"shipping_runtime_benchmark_artifacts.{index}",
            )
            for index, item in enumerate(raw_shipping_runtime_benchmark_artifacts)
        ]
        raw_shipping_runtime_compiled_artifacts = data.get("shipping_runtime_compiled_artifacts")
        if not isinstance(raw_shipping_runtime_compiled_artifacts, list):
            raise ValueError("shipping_runtime_compiled_artifacts must be a list.")
        shipping_runtime_compiled_artifacts = [
            _require_manifest_string(
                {"value": item},
                "value",
                f"shipping_runtime_compiled_artifacts.{index}",
            )
            for index, item in enumerate(raw_shipping_runtime_compiled_artifacts)
        ]
        raw_shipping_runtime_compiled_engines = data.get("shipping_runtime_compiled_engines")
        if not isinstance(raw_shipping_runtime_compiled_engines, list):
            raise ValueError("shipping_runtime_compiled_engines must be a list.")
        shipping_runtime_compiled_engines = [
            _coerce_enum(
                item,
                RuntimeCompiledEngine,
                f"shipping_runtime_compiled_engines.{index}",
            )
            for index, item in enumerate(raw_shipping_runtime_compiled_engines)
        ]
        raw_shipping_runtime_max_cold_ms = data.get("shipping_runtime_max_cold_ms")
        if not isinstance(raw_shipping_runtime_max_cold_ms, list):
            raise ValueError("shipping_runtime_max_cold_ms must be a list.")
        shipping_runtime_max_cold_ms = [
            _require_manifest_float(
                {"value": item},
                "value",
                f"shipping_runtime_max_cold_ms.{index}",
            )
            for index, item in enumerate(raw_shipping_runtime_max_cold_ms)
        ]
        raw_shipping_runtime_max_warm_ms = data.get("shipping_runtime_max_warm_ms")
        if not isinstance(raw_shipping_runtime_max_warm_ms, list):
            raise ValueError("shipping_runtime_max_warm_ms must be a list.")
        shipping_runtime_max_warm_ms = [
            _require_manifest_float(
                {"value": item},
                "value",
                f"shipping_runtime_max_warm_ms.{index}",
            )
            for index, item in enumerate(raw_shipping_runtime_max_warm_ms)
        ]
        raw_shipping_runtime_max_hot_ms = data.get("shipping_runtime_max_hot_ms")
        if not isinstance(raw_shipping_runtime_max_hot_ms, list):
            raise ValueError("shipping_runtime_max_hot_ms must be a list.")
        shipping_runtime_max_hot_ms = [
            _require_manifest_float(
                {"value": item},
                "value",
                f"shipping_runtime_max_hot_ms.{index}",
            )
            for index, item in enumerate(raw_shipping_runtime_max_hot_ms)
        ]
        if benchmark_discovery_lane.shipping_manifest_modules != len(module_benchmarks):
            raise ValueError(
                "benchmark_discovery_lane.shipping_manifest_modules must equal the number "
                "of benchmark modules."
            )
        if benchmark_discovery_lane.shipping_manifest_modules != len(shipping_runtime_modules):
            raise ValueError(
                "shipping_runtime_modules must contain one entry per shipping benchmark module."
            )
        if benchmark_discovery_lane.shipping_manifest_modules != len(
            shipping_runtime_function_counts
        ):
            raise ValueError(
                "shipping_runtime_function_counts must contain one entry per shipping "
                "benchmark module."
            )
        if benchmark_discovery_lane.shipping_manifest_modules != len(
            shipping_runtime_benchmark_speedups_x
        ):
            raise ValueError(
                "shipping_runtime_benchmark_speedups_x must contain one entry per shipping "
                "benchmark module."
            )
        if benchmark_discovery_lane.shipping_manifest_modules != len(
            shipping_runtime_benchmark_artifacts
        ):
            raise ValueError(
                "shipping_runtime_benchmark_artifacts must contain one entry per shipping "
                "benchmark module."
            )
        if benchmark_discovery_lane.shipping_manifest_modules != len(
            shipping_runtime_compiled_artifacts
        ):
            raise ValueError(
                "shipping_runtime_compiled_artifacts must contain one entry per shipping "
                "benchmark module."
            )
        if benchmark_discovery_lane.shipping_manifest_modules != len(
            shipping_runtime_compiled_engines
        ):
            raise ValueError(
                "shipping_runtime_compiled_engines must contain one entry per shipping "
                "benchmark module."
            )
        if benchmark_discovery_lane.shipping_manifest_modules != len(
            shipping_runtime_max_cold_ms
        ):
            raise ValueError(
                "shipping_runtime_max_cold_ms must contain one entry per shipping "
                "benchmark module."
            )
        if benchmark_discovery_lane.shipping_manifest_modules != len(
            shipping_runtime_max_warm_ms
        ):
            raise ValueError(
                "shipping_runtime_max_warm_ms must contain one entry per shipping "
                "benchmark module."
            )
        if benchmark_discovery_lane.shipping_manifest_modules != len(
            shipping_runtime_max_hot_ms
        ):
            raise ValueError(
                "shipping_runtime_max_hot_ms must contain one entry per shipping "
                "benchmark module."
            )
        total_functions = sum(benchmark.function_count for benchmark in module_benchmarks)
        if benchmark_discovery_lane.shipping_manifest_functions != total_functions:
            raise ValueError(
                "benchmark_discovery_lane.shipping_manifest_functions must equal the total "
                "benchmark module function_count."
            )
        benchmark_class_codes = {entry.code for entry in benchmarking.classes}
        quality_gate_class_codes = {entry.code for entry in quality_gate_benchmark_classes}
        if not quality_gate_class_codes.issubset(benchmark_class_codes):
            raise ValueError(
                "quality_gate_benchmark_classes must be declared in benchmarking.classes."
            )
        budget_names = {entry.name for entry in slo_budgets}
        quality_gate_budget_names = {entry.name for entry in quality_gate_slo_budgets}
        if not quality_gate_budget_names.issubset(budget_names):
            raise ValueError("quality_gate_slo_budgets must be declared in slo_budgets.")
        dimensions = set(evaluation_science.dimensions)
        release_blockers = set(evaluation_science.release_blockers)
        expected_replay_gate = (
            RuntimeBenchmarkClassCode.checkpoint_replay_overhead in quality_gate_class_codes
            and RuntimeSLOBudgetName.replay in quality_gate_budget_names
            and RuntimeEvaluationDimension.replay_success_rate in dimensions
            and RuntimeReleaseBlocker.replay_success_regression in release_blockers
        )
        expected_tool_call_quality_gate = (
            RuntimeBenchmarkClassCode.mcp_tool_latency in quality_gate_class_codes
            and RuntimeSLOBudgetName.mcp_call_first_party in quality_gate_budget_names
            and RuntimeEvaluationDimension.tool_call_correctness in dimensions
            and RuntimeReleaseBlocker.tool_call_error_rate_increase in release_blockers
        )
        expected_rag_quality_gate = (
            RuntimeBenchmarkClassCode.rag_retrieval_quality_latency in quality_gate_class_codes
            and RuntimeEvaluationDimension.retrieval_precision_and_recall in dimensions
            and RuntimeReleaseBlocker.rag_precision_drop in release_blockers
        )
        expected_decision_quality_gate = (
            RuntimeBenchmarkClassCode.decision_workflow_completion_latency in quality_gate_class_codes
            and RuntimeSLOBudgetName.decision_plan_creation in quality_gate_budget_names
            and RuntimeEvaluationDimension.decision_outcome_delta in dimensions
            and RuntimeReleaseBlocker.decision_plan_validity_drop in release_blockers
        )
        if evaluation_summary.dimension_count != len(evaluation_science.dimensions):
            raise ValueError(
                "evaluation_summary.dimension_count must equal the number of evaluation dimensions."
            )
        if evaluation_summary.method_count != len(evaluation_science.methods):
            raise ValueError(
                "evaluation_summary.method_count must equal the number of evaluation methods."
            )
        if evaluation_summary.release_blocker_count != len(evaluation_science.release_blockers):
            raise ValueError(
                "evaluation_summary.release_blocker_count must equal the number of release blockers."
            )
        if evaluation_summary.benchmark_class_count != len(quality_gate_benchmark_classes):
            raise ValueError(
                "evaluation_summary.benchmark_class_count must equal the number of quality gate benchmark classes."
            )
        if evaluation_summary.slo_budget_count != len(quality_gate_slo_budgets):
            raise ValueError(
                "evaluation_summary.slo_budget_count must equal the number of quality gate SLO budgets."
            )
        if evaluation_summary.replay_gate_enabled != expected_replay_gate:
            raise ValueError(
                "evaluation_summary.replay_gate_enabled must match the replay benchmark, budget, and release blocker coverage."
            )
        if (
            evaluation_summary.tool_call_quality_gate_enabled
            != expected_tool_call_quality_gate
        ):
            raise ValueError(
                "evaluation_summary.tool_call_quality_gate_enabled must match the tool-call benchmark, budget, and release blocker coverage."
            )
        if evaluation_summary.rag_quality_gate_enabled != expected_rag_quality_gate:
            raise ValueError(
                "evaluation_summary.rag_quality_gate_enabled must match the RAG benchmark and release blocker coverage."
            )
        if (
            evaluation_summary.decision_quality_gate_enabled
            != expected_decision_quality_gate
        ):
            raise ValueError(
                "evaluation_summary.decision_quality_gate_enabled must match the decision benchmark, budget, and release blocker coverage."
            )
        discovered_import_path_set = {
            entry.import_path for entry in benchmark_discovery_lane.discovered_source_inventory
        }
        for index, benchmark in enumerate(module_benchmarks):
            if benchmark.name.value not in discovered_import_path_set:
                raise ValueError(
                    "benchmark_discovery_lane.discovered_source_inventory must include "
                    f"module_benchmarks.{index}.name ({benchmark.name.value})."
                )
            if shipping_runtime_modules[index] != benchmark.name:
                raise ValueError(
                    f"shipping_runtime_modules.{index} must equal "
                    f"module_benchmarks.{index}.name."
                )
            if shipping_runtime_function_counts[index] != benchmark.function_count:
                raise ValueError(
                    f"shipping_runtime_function_counts.{index} must equal "
                    f"module_benchmarks.{index}.function_count."
                )
            if shipping_runtime_benchmark_speedups_x[index] != benchmark.benchmark_speedup_x:
                raise ValueError(
                    f"shipping_runtime_benchmark_speedups_x.{index} must equal "
                    f"module_benchmarks.{index}.benchmark_speedup_x."
                )
            if shipping_runtime_benchmark_artifacts[index] != benchmark.benchmark_artifact:
                raise ValueError(
                    f"shipping_runtime_benchmark_artifacts.{index} must equal "
                    f"module_benchmarks.{index}.benchmark_artifact."
                )
            if shipping_runtime_compiled_artifacts[index] != benchmark.compiled_artifact:
                raise ValueError(
                    f"shipping_runtime_compiled_artifacts.{index} must equal "
                    f"module_benchmarks.{index}.compiled_artifact."
                )
            if shipping_runtime_compiled_engines[index] != benchmark.compiled_engine:
                raise ValueError(
                    f"shipping_runtime_compiled_engines.{index} must equal "
                    f"module_benchmarks.{index}.compiled_engine."
                )
            if shipping_runtime_max_cold_ms[index] != benchmark.max_cold_ms:
                raise ValueError(
                    f"shipping_runtime_max_cold_ms.{index} must equal "
                    f"module_benchmarks.{index}.max_cold_ms."
                )
            if shipping_runtime_max_warm_ms[index] != benchmark.max_warm_ms:
                raise ValueError(
                    f"shipping_runtime_max_warm_ms.{index} must equal "
                    f"module_benchmarks.{index}.max_warm_ms."
                )
            if shipping_runtime_max_hot_ms[index] != benchmark.max_hot_ms:
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
        compiled_artifact_paths = {artifact.path for artifact in compiled_artifacts}
        benchmark_artifact_indexes: dict[str, int] = {}
        for index, benchmark in enumerate(module_benchmarks):
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
        return cls(
            runtime_version=_require_manifest_string(
                data,
                "runtime_version",
                "runtime_admin_benchmarks",
            ),
            llm_core_manifest=_require_manifest_string(
                data,
                "llm_core_manifest",
                "runtime_admin_benchmarks",
            ),
            module_manifest_version=_require_manifest_string(
                data,
                "module_manifest_version",
                "runtime_admin_benchmarks",
            ),
            benchmark_discovery_lane=benchmark_discovery_lane,
            benchmarking=benchmarking,
            slo_budgets=slo_budgets,
            quality_gate_benchmark_classes=quality_gate_benchmark_classes,
            quality_gate_slo_budgets=quality_gate_slo_budgets,
            evaluation_science=evaluation_science,
            evaluation_summary=evaluation_summary,
            compiled_artifacts=compiled_artifacts,
            shipping_runtime_modules=shipping_runtime_modules,
            shipping_runtime_function_counts=shipping_runtime_function_counts,
            shipping_runtime_benchmark_speedups_x=shipping_runtime_benchmark_speedups_x,
            shipping_runtime_benchmark_artifacts=shipping_runtime_benchmark_artifacts,
            shipping_runtime_compiled_artifacts=shipping_runtime_compiled_artifacts,
            shipping_runtime_compiled_engines=shipping_runtime_compiled_engines,
            shipping_runtime_max_cold_ms=shipping_runtime_max_cold_ms,
            shipping_runtime_max_warm_ms=shipping_runtime_max_warm_ms,
            shipping_runtime_max_hot_ms=shipping_runtime_max_hot_ms,
            module_benchmarks=module_benchmarks,
            manifest_digest=_require_manifest_string(
                data,
                "manifest_digest",
                "runtime_admin_benchmarks",
            ),
            signature=RuntimeManifestSignature.from_api(data["signature"], "signature"),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ReleaseConditionEvaluation:
    condition: RuntimeReleaseCondition
    satisfied: bool
    detail: str
    evidence_paths: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any, context: str = "conditions") -> ReleaseConditionEvaluation:
        data = coerce_payload_mapping(payload)
        return cls(
            condition=_coerce_enum(
                data["condition"],
                RuntimeReleaseCondition,
                f"{context}.condition",
            ),
            satisfied=_require_manifest_boolean(data, "satisfied", context),
            detail=_require_manifest_string(data, "detail", context),
            evidence_paths=_ensure_unique_manifest_values(
                _optional_manifest_string_list(data, "evidence_paths", context),
                f"{context}.evidence_paths",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeReleaseValidationOutput:
    runtime_version: str
    llm_core_manifest: str
    module_manifest_version: str
    theorem_statement: str
    valid_release: bool
    conditions: list[ReleaseConditionEvaluation] = field(default_factory=list)
    deployment_mode: RuntimeDeploymentMode | None = RuntimeDeploymentMode.local_dev_daemon
    deployment_mode_raw: str = RuntimeDeploymentMode.local_dev_daemon.value
    manifest_digest: str = ""
    signature: RuntimeManifestSignature = field(
        default_factory=lambda: RuntimeManifestSignature(
            RuntimeSignatureAlgorithm.hmac_sha256,
            "",
            "",
            "",
            RuntimeSignatureScope.control_plane_hmac_v1,
        )
    )

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeReleaseValidationOutput:
        data = coerce_payload_mapping(payload)
        conditions = [
            ReleaseConditionEvaluation.from_api(item, f"conditions.{index}")
            for index, item in enumerate(data.get("conditions") or [])
        ]
        _ensure_unique_manifest_values(
            conditions,
            "conditions",
            value_selector=lambda entry: entry.condition,
        )
        return cls(
            runtime_version=_require_manifest_string(
                data,
                "runtime_version",
                "release_validation",
            ),
            llm_core_manifest=_require_manifest_string(
                data,
                "llm_core_manifest",
                "release_validation",
            ),
            module_manifest_version=_require_manifest_string(
                data,
                "module_manifest_version",
                "release_validation",
            ),
            theorem_statement=_require_manifest_string(
                data,
                "theorem_statement",
                "release_validation",
            ),
            valid_release=_require_manifest_boolean(data, "valid_release", "release_validation"),
            conditions=conditions,
            deployment_mode=_coerce_optional_enum(
                data.get("deployment_mode"),
                RuntimeDeploymentMode,
                "release_validation.deployment_mode",
            ),
            deployment_mode_raw=_require_manifest_string(
                data,
                "deployment_mode_raw",
                "release_validation",
            ),
            manifest_digest=_require_manifest_string(
                data,
                "manifest_digest",
                "release_validation",
            ),
            signature=RuntimeManifestSignature.from_api(data["signature"], "signature"),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeManifestOutput:
    runtime_version: str
    mojo_version: str
    llm_core_manifest: str
    module_manifest_version: str
    generated_at: str
    modules: list[RuntimeModuleManifestEntry] = field(default_factory=list)
    compiled_artifacts: list[RuntimeArtifactReference] = field(default_factory=list)
    supported_channels: list[RuntimeSupportedChannel] = field(default_factory=list)
    validated_auxiliary_channels: list[RuntimeAuxiliaryChannel] = field(default_factory=list)
    feature_flag_channels: list[RuntimeFeatureFlagChannel] = field(default_factory=list)
    maturity: dict[RuntimeModuleId, RuntimeMaturity] = field(default_factory=dict)
    policy_snapshot: RuntimeSnapshotReference = field(
        default_factory=lambda: RuntimeSnapshotReference("", "", "", "")
    )
    schema_snapshot: RuntimeSnapshotReference = field(
        default_factory=lambda: RuntimeSnapshotReference("", "", "", "")
    )
    deployment_mode: RuntimeDeploymentMode = RuntimeDeploymentMode.local_dev_daemon
    deployment_modes: RuntimeDeploymentModes = field(
        default_factory=lambda: RuntimeDeploymentModes(
            RuntimeDeploymentMode.local_dev_daemon,
            [],
            "",
        )
    )
    shipping_contract: RuntimeShippingContractSummary = field(
        default_factory=lambda: RuntimeShippingContractSummary(
            0,
            0,
            RuntimeLayer.mojo_llm_runtime_core,
            "",
        )
    )
    benchmark_discovery_lane: RuntimeBenchmarkDiscoveryLane = field(
        default_factory=lambda: RuntimeBenchmarkDiscoveryLane(
            0,
            0,
            [],
            0,
            0,
            RuntimeNonShippingRule.broader_mojo_inventory_not_advertised,
        )
    )
    advertised_capabilities: RuntimeAdvertisedCapabilities = field(
        default_factory=RuntimeAdvertisedCapabilities
    )
    system_invariants: list[RuntimeNamedRule] = field(default_factory=list)
    execution_model: RuntimeExecutionModel = field(default_factory=RuntimeExecutionModel)
    external_nondeterminism: RuntimeExternalNondeterminismPolicy = field(
        default_factory=RuntimeExternalNondeterminismPolicy
    )
    artifact_lineage: RuntimeArtifactLineageSchema = field(
        default_factory=RuntimeArtifactLineageSchema
    )
    capability_algebra: RuntimeCapabilityAlgebraSchema = field(
        default_factory=RuntimeCapabilityAlgebraSchema
    )
    kernel_promotion_criteria: RuntimeKernelPromotionCriteria | None = None
    proof_matrix: list[RuntimeLayerProofMatrixEntry] = field(default_factory=list)
    benchmarking: RuntimeBenchmarkFramework = field(default_factory=RuntimeBenchmarkFramework)
    slo_budgets: list[RuntimeSLOBudget] = field(default_factory=list)
    scheduler_model: RuntimeSchedulerModel = field(default_factory=RuntimeSchedulerModel)
    memory_model: RuntimeMemoryModel = field(default_factory=RuntimeMemoryModel)
    evaluation_science: RuntimeEvaluationScience = field(default_factory=RuntimeEvaluationScience)
    typed_failures: list[RuntimeTypedFailure] = field(default_factory=list)
    threat_model: RuntimeThreatModel = field(default_factory=RuntimeThreatModel)
    formal_release_theorem: RuntimeFormalReleaseTheorem = field(
        default_factory=lambda: RuntimeFormalReleaseTheorem("")
    )
    release_artifact_bundle: RuntimeReleaseArtifactBundle = field(
        default_factory=RuntimeReleaseArtifactBundle
    )
    release_gates: list[RuntimeReleaseGate] = field(default_factory=list)
    immediate_implementation_sequence: list[RuntimeImmediateImplementationPR] = field(
        default_factory=list
    )
    manifest_digest: str = ""
    signature: RuntimeManifestSignature = field(
        default_factory=lambda: RuntimeManifestSignature(
            RuntimeSignatureAlgorithm.hmac_sha256,
            "",
            "",
            "",
            RuntimeSignatureScope.control_plane_hmac_v1,
        )
    )

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeManifestOutput:
        data = coerce_payload_mapping(payload)
        modules = [
            RuntimeModuleManifestEntry.from_api(item, f"modules.{index}")
            for index, item in enumerate(data.get("modules") or [])
        ]
        supported_channels = _ensure_unique_manifest_values(
            _coerce_enum_list(
                data.get("supported_channels"),
                RuntimeSupportedChannel,
                "supported_channels",
            ),
            "supported_channels",
        )
        validated_auxiliary_channels = _ensure_unique_manifest_values(
            _coerce_enum_list(
                data.get("validated_auxiliary_channels"),
                RuntimeAuxiliaryChannel,
                "validated_auxiliary_channels",
            ),
            "validated_auxiliary_channels",
        )
        feature_flag_channels = _ensure_unique_manifest_values(
            _coerce_enum_list(
                data.get("feature_flag_channels"),
                RuntimeFeatureFlagChannel,
                "feature_flag_channels",
            ),
            "feature_flag_channels",
        )
        system_invariants = [
            RuntimeNamedRule.from_api(item, f"system_invariants.{index}")
            for index, item in enumerate(data.get("system_invariants") or [])
        ]
        proof_matrix = [
            RuntimeLayerProofMatrixEntry.from_api(item, f"proof_matrix.{index}")
            for index, item in enumerate(data.get("proof_matrix") or [])
        ]
        typed_failures = [
            RuntimeTypedFailure.from_api(item, f"typed_failures.{index}")
            for index, item in enumerate(data.get("typed_failures") or [])
        ]
        release_gates = [
            RuntimeReleaseGate.from_api(item, f"release_gates.{index}")
            for index, item in enumerate(data.get("release_gates") or [])
        ]
        immediate_implementation_sequence = [
            RuntimeImmediateImplementationPR.from_api(
                item,
                f"immediate_implementation_sequence.{index}",
            )
            for index, item in enumerate(data.get("immediate_implementation_sequence") or [])
        ]
        _ensure_unique_manifest_values(
            modules,
            "modules",
            value_selector=lambda entry: entry.name,
        )
        _ensure_unique_manifest_values(
            system_invariants,
            "system_invariants",
            value_selector=lambda entry: entry.name,
        )
        _ensure_unique_manifest_values(
            proof_matrix,
            "proof_matrix",
            value_selector=lambda entry: entry.layer,
        )
        _ensure_unique_manifest_values(
            typed_failures,
            "typed_failures",
            value_selector=lambda entry: entry.code,
        )
        _ensure_unique_manifest_values(
            release_gates,
            "release_gates",
            value_selector=lambda entry: entry.gate,
        )
        _ensure_unique_manifest_values(
            immediate_implementation_sequence,
            "immediate_implementation_sequence",
            value_selector=lambda entry: entry.pr,
        )
        shipping_contract = RuntimeShippingContractSummary.from_api(
            data["shipping_contract"],
            "shipping_contract",
        )
        benchmark_discovery_lane = RuntimeBenchmarkDiscoveryLane.from_api(
            data["benchmark_discovery_lane"],
            "benchmark_discovery_lane",
        )
        total_functions = sum(module.function_count for module in modules)
        if shipping_contract.module_count != len(modules):
            raise ValueError(
                "shipping_contract.module_count must equal the number of manifest modules."
            )
        if shipping_contract.function_count != total_functions:
            raise ValueError(
                "shipping_contract.function_count must equal the total module function_count."
            )
        if benchmark_discovery_lane.shipping_manifest_modules != len(modules):
            raise ValueError(
                "benchmark_discovery_lane.shipping_manifest_modules must equal the number "
                "of manifest modules."
            )
        if benchmark_discovery_lane.shipping_manifest_functions != total_functions:
            raise ValueError(
                "benchmark_discovery_lane.shipping_manifest_functions must equal the total "
                "module function_count."
            )
        discovered_import_path_set = {
            entry.import_path for entry in benchmark_discovery_lane.discovered_source_inventory
        }
        for module in modules:
            if module.name.value not in discovered_import_path_set:
                raise ValueError(
                    "benchmark_discovery_lane.discovered_source_inventory must include "
                    f"manifest module {module.name.value}."
                )
        return cls(
            runtime_version=_require_manifest_string(data, "runtime_version", "runtime_manifest"),
            mojo_version=_require_manifest_string(data, "mojo_version", "runtime_manifest"),
            llm_core_manifest=_require_manifest_string(
                data,
                "llm_core_manifest",
                "runtime_manifest",
            ),
            module_manifest_version=_require_manifest_string(
                data,
                "module_manifest_version",
                "runtime_manifest",
            ),
            generated_at=_require_manifest_string(data, "generated_at", "runtime_manifest"),
            modules=modules,
            compiled_artifacts=_ensure_unique_manifest_values(
                [
                    RuntimeArtifactReference.from_api(item, f"compiled_artifacts.{index}")
                    for index, item in enumerate(data.get("compiled_artifacts") or [])
                ],
                "compiled_artifacts",
                value_selector=lambda entry: entry.path,
            ),
            supported_channels=supported_channels,
            validated_auxiliary_channels=validated_auxiliary_channels,
            feature_flag_channels=feature_flag_channels,
            maturity=_coerce_enum_mapping(
                data.get("maturity"),
                RuntimeModuleId,
                lambda raw_value, key: _coerce_enum(
                    raw_value,
                    RuntimeMaturity,
                    f"maturity.{key.value}",
                ),
                "maturity",
            ),
            policy_snapshot=RuntimeSnapshotReference.from_api(
                data["policy_snapshot"],
                "policy_snapshot",
            ),
            schema_snapshot=RuntimeSnapshotReference.from_api(
                data["schema_snapshot"],
                "schema_snapshot",
            ),
            deployment_mode=_coerce_enum(
                data["deployment_mode"],
                RuntimeDeploymentMode,
                "deployment_mode",
            ),
            deployment_modes=RuntimeDeploymentModes.from_api(data["deployment_modes"]),
            shipping_contract=shipping_contract,
            benchmark_discovery_lane=benchmark_discovery_lane,
            advertised_capabilities=RuntimeAdvertisedCapabilities.from_api(
                data["advertised_capabilities"]
            ),
            system_invariants=system_invariants,
            execution_model=RuntimeExecutionModel.from_api(data.get("execution_model") or {}),
            external_nondeterminism=RuntimeExternalNondeterminismPolicy.from_api(
                data.get("external_nondeterminism") or {}
            ),
            artifact_lineage=RuntimeArtifactLineageSchema.from_api(
                data.get("artifact_lineage") or {}
            ),
            capability_algebra=RuntimeCapabilityAlgebraSchema.from_api(
                data.get("capability_algebra") or {}
            ),
            kernel_promotion_criteria=(
                RuntimeKernelPromotionCriteria.from_api(data["kernel_promotion_criteria"])
                if data.get("kernel_promotion_criteria") is not None
                else None
            ),
            proof_matrix=proof_matrix,
            benchmarking=RuntimeBenchmarkFramework.from_api(data.get("benchmarking") or {}),
            slo_budgets=[
                RuntimeSLOBudget.from_api(item, f"slo_budgets.{index}")
                for index, item in enumerate(data.get("slo_budgets") or [])
            ],
            scheduler_model=RuntimeSchedulerModel.from_api(data.get("scheduler_model") or {}),
            memory_model=RuntimeMemoryModel.from_api(data.get("memory_model") or {}),
            evaluation_science=RuntimeEvaluationScience.from_api(
                data.get("evaluation_science") or {}
            ),
            typed_failures=typed_failures,
            threat_model=RuntimeThreatModel.from_api(data.get("threat_model") or {}),
            formal_release_theorem=RuntimeFormalReleaseTheorem.from_api(
                data.get("formal_release_theorem") or {}
            ),
            release_artifact_bundle=RuntimeReleaseArtifactBundle.from_api(
                data.get("release_artifact_bundle") or {}
            ),
            release_gates=release_gates,
            immediate_implementation_sequence=immediate_implementation_sequence,
            manifest_digest=_require_manifest_string(data, "manifest_digest", "runtime_manifest"),
            signature=RuntimeManifestSignature.from_api(data["signature"], "signature"),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))
