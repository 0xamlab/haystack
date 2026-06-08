from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import subprocess
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar, get_origin

from pydantic import (
    BaseModel,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
)

from apps.api_server.config import get_settings
from apps.api_server.services.execution_policy_service import default_policy_payload
from apps.platform_contract import load_platform_contract_manifest
from apps.runtime.mojo_inventory import build_inventory_report
from benchmarks.llm_compiled_runtime_benchmark import TARGET_MODULES as LLM_ROLLOUT_MODULE_ORDER

_ROOT = Path(__file__).resolve().parents[1]
_PROOF_BUNDLE_PATH = _ROOT / "build" / "llm_rollout_proof_bundle.json"
_PARITY_ARTIFACT_PATH = _ROOT / "build" / "llm_rollout_parity_benchmark.json"
_COMPILED_ARTIFACT_PATH = _ROOT / "build" / "llm_compiled_runtime_benchmark.json"
_MOJO_BINARY_PATH = _ROOT / "mojo_build" / "simulate"

_RUNTIME_VERSION = "2026.05.0"
_LLM_CORE_MANIFEST = "llm-core-v1"
_MODULE_MANIFEST_VERSION = "runtime-manifest-v1"
_CONTROL_PLANE_SIGNATURE_KEY_ID = "runtime-manifest-signing-v1"
_PUBLIC_ENDPOINTS = (
    "/v1/meta/contract",
    "/v1/runtime/manifest",
)
_ADMIN_ENDPOINTS = (
    "/v1/admin/runtime/modules",
    "/v1/admin/runtime/benchmarks",
    "/v1/admin/runtime/validation",
)
_FEATURE_FLAG_ENDPOINTS = (
    "/v1/libraries",
    "/v1/libraries/health",
    "/v1/libraries/execute",
)
_KERNEL_SCHEMA_COMPAT_REPORT_REF = "tests/test_runtime_schema_surface.py"
_KERNEL_ISOLATION_PROOF_REF = "tests/test_runtime_manifest.py"
_KERNEL_REPLAY_PROOF_REF = "tests/test_runtime_release_validation.py"
_KERNEL_OWNER = "algenta-runtime-core"
_MODULE_BENCHMARK_NAME_MAP = {
    "text.tokenizer": "text_tokenizer",
    "vector_kernels.ranker": "vector_kernels_ranker",
    "vector_kernels.table": "vector_kernels_table",
}


class RuntimeManifestBaseModel(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def validate_list_fields_use_json_arrays(
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


class RuntimeMaturity(str, Enum):
    experimental = "experimental"
    benchmarked = "benchmarked"
    parity_tested = "parity_tested"
    channel_covered = "channel_covered"
    enterprise_ready = "enterprise_ready"
    deprecated = "deprecated"


class SideEffectClass(str, Enum):
    read_only = "read_only"
    write_scoped = "write_scoped"
    write_external = "write_external"
    exec_external = "exec_external"
    network_external = "network_external"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Replayability(str, Enum):
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


class ExecutionTransition(str, Enum):
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


class ReleaseCondition(str, Enum):
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


class ArtifactReference(RuntimeManifestBaseModel):
    kind: RuntimeArtifactKind
    path: str
    sha256: str
    size_bytes: StrictInt


class ManifestSignature(RuntimeManifestBaseModel):
    algorithm: RuntimeSignatureAlgorithm
    key_id: str
    digest_hex: str
    signature_hex: str
    scope: RuntimeSignatureScope


class ShippingContractSummary(RuntimeManifestBaseModel):
    module_count: StrictInt
    function_count: StrictInt
    runtime_core_layer: RuntimeLayer
    benchmark_discovery_rule: RuntimeBenchmarkDiscoveryRule


class BenchmarkDiscoverySourceModuleEntry(RuntimeManifestBaseModel):
    import_path: StrictStr
    public_function_count: StrictInt


class BenchmarkDiscoveryLane(RuntimeManifestBaseModel):
    discovered_source_modules: StrictInt
    discovered_public_functions: StrictInt
    discovered_source_inventory: list[BenchmarkDiscoverySourceModuleEntry] = Field(default_factory=list)
    shipping_manifest_modules: StrictInt
    shipping_manifest_functions: StrictInt
    non_shipping_rule: RuntimeNonShippingRule

    @model_validator(mode="after")
    def validate_discovery_inventory(self) -> BenchmarkDiscoveryLane:
        _raise_on_duplicate_values(
            self.discovered_source_inventory,
            "discovered_source_inventory",
            lambda entry: entry.import_path,
            "runtime benchmark discovery source modules",
        )
        if self.discovered_source_modules != len(self.discovered_source_inventory):
            _raise_manifest_integrity_error(
                "discovered_source_modules",
                "runtime benchmark discovery source module count does not match discovered source inventory",
            )
        discovered_public_function_count = 0
        discovered_import_paths: list[str] = []
        for index, entry in enumerate(self.discovered_source_inventory):
            if entry.public_function_count <= 0:
                _raise_manifest_integrity_error(
                    f"discovered_source_inventory.{index}.public_function_count",
                    "runtime benchmark discovery public_function_count must be positive",
                )
            discovered_public_function_count += entry.public_function_count
            discovered_import_paths.append(entry.import_path)
        if self.discovered_public_functions != discovered_public_function_count:
            _raise_manifest_integrity_error(
                "discovered_public_functions",
                "runtime benchmark discovery public function count does not match discovered source inventory",
            )
        if discovered_import_paths != sorted(discovered_import_paths):
            _raise_manifest_integrity_error(
                "discovered_source_inventory",
                "runtime benchmark discovery source inventory must be sorted by import_path",
            )
        if self.shipping_manifest_modules > self.discovered_source_modules:
            _raise_manifest_integrity_error(
                "shipping_manifest_modules",
                "runtime benchmark discovery shipping module count cannot exceed discovered source module count",
            )
        if self.shipping_manifest_functions > self.discovered_public_functions:
            _raise_manifest_integrity_error(
                "shipping_manifest_functions",
                "runtime benchmark discovery shipping function count cannot exceed discovered public function count",
            )
        return self


class SnapshotReference(RuntimeManifestBaseModel):
    snapshot_id: str
    sha256: str
    source: str
    description: str


class KernelPromotionCriteria(RuntimeManifestBaseModel):
    required_manifest_fields: list[StrictStr] = Field(default_factory=list)
    required_proof_reference_fields: list[StrictStr] = Field(default_factory=list)
    deterministic_test_corpus_rule: str
    python_parity_rule: str
    schema_compatibility_rule: str
    minimum_primary_metric_improvement_pct: StrictFloat
    maximum_adjacent_metric_regression_pct: StrictFloat
    benchmark_exception_rule: str
    rollback_scope_rule: str
    tenant_isolation_rule: str
    replay_compatibility_rule: str

    @model_validator(mode="after")
    def validate_thresholds(self) -> KernelPromotionCriteria:
        if self.minimum_primary_metric_improvement_pct <= 0:
            _raise_manifest_integrity_error(
                "kernel_promotion_criteria.minimum_primary_metric_improvement_pct",
                "kernel promotion minimum_primary_metric_improvement_pct must be positive",
            )
        if self.maximum_adjacent_metric_regression_pct < 0:
            _raise_manifest_integrity_error(
                "kernel_promotion_criteria.maximum_adjacent_metric_regression_pct",
                "kernel promotion maximum_adjacent_metric_regression_pct must be non-negative",
            )
        return self


class RuntimeModuleManifestEntry(RuntimeManifestBaseModel):
    name: RuntimeModuleId
    capability_id: StrictStr
    owner: StrictStr
    contract_boundary: StrictStr
    function_count: StrictInt
    functions: list[str] = Field(default_factory=list)
    layer: RuntimeLayer
    maturity: RuntimeMaturity
    public_supported_channels: list[RuntimeSupportedChannel] = Field(
        default_factory=list,
    )
    validated_auxiliary_channels: list[RuntimeAuxiliaryChannel] = Field(
        default_factory=list,
    )
    feature_flag_channels: list[RuntimeFeatureFlagChannel] = Field(
        default_factory=list,
    )
    proof_obligations: list[RuntimeProofObligation] = Field(default_factory=list)
    proof_artifacts: list[str] = Field(default_factory=list)
    promotion_status: RuntimeKernelPromotionStatus
    rollback_flag: StrictStr
    benchmark_report_ref: StrictStr
    parity_report_ref: StrictStr
    schema_compat_report_ref: StrictStr
    isolation_proof_ref: StrictStr
    replay_proof_ref: StrictStr
    benchmark_artifact: str
    benchmark_speedup_x: StrictFloat
    compiled_artifact: str
    compiled_engine: RuntimeCompiledEngine
    max_cold_ms: StrictFloat
    max_warm_ms: StrictFloat
    max_hot_ms: StrictFloat


class NamedRule(RuntimeManifestBaseModel):
    name: RuntimeInvariantName
    statement: str


class ExecutionModel(RuntimeManifestBaseModel):
    state_fields: list[RuntimeExecutionStateField] = Field(default_factory=list)
    allowed_transitions: list[ExecutionTransition] = Field(default_factory=list)
    validity_rules: list[RuntimeExecutionValidityRule] = Field(default_factory=list)


class ExternalNondeterminismPolicy(RuntimeManifestBaseModel):
    sources: list[RuntimeExternalNondeterminismSource] = Field(default_factory=list)
    rule: str
    required_artifacts: list[RuntimeNondeterminismArtifact] = Field(
        default_factory=list,
    )
    failure_codes: list[RuntimeFailureCode] = Field(default_factory=list)


class ArtifactLineageSchema(RuntimeManifestBaseModel):
    artifact_flow: list[RuntimeArtifactLineageStep] = Field(default_factory=list)
    required_node_fields: list[RuntimeLineageNodeField] = Field(
        default_factory=list,
    )
    immutability_rule: str


class CapabilityEnums(RuntimeManifestBaseModel):
    side_effect_class: list[SideEffectClass] = Field(default_factory=list)
    risk_level: list[RiskLevel] = Field(default_factory=list)
    replayability: list[Replayability] = Field(default_factory=list)


class CapabilityAlgebraSchema(RuntimeManifestBaseModel):
    required_fields: list[RuntimeCapabilityField] = Field(default_factory=list)
    enums: CapabilityEnums
    rules: list[RuntimeCapabilityRule] = Field(default_factory=list)


class LayerProofMatrixEntry(RuntimeManifestBaseModel):
    layer: RuntimeLayer
    status: RuntimeMaturity
    obligations: list[RuntimeProofObligation] = Field(default_factory=list)
    evidence_paths: list[str] = Field(default_factory=list)


class BenchmarkClassEntry(RuntimeManifestBaseModel):
    code: RuntimeBenchmarkClassCode
    description: str
    evidence_paths: list[str] = Field(default_factory=list)

    @field_validator("evidence_paths")
    @classmethod
    def validate_unique_evidence_paths(cls, value: list[str]) -> list[str]:
        _raise_on_duplicate_values(
            value,
            "evidence_paths",
            lambda item: item,
            "runtime benchmark class evidence paths",
        )
        return value


class BenchmarkFramework(RuntimeManifestBaseModel):
    classes: list[BenchmarkClassEntry] = Field(default_factory=list)
    required_metrics: list[RuntimeBenchmarkMetric] = Field(default_factory=list)
    baselines: list[RuntimeBenchmarkBaseline] = Field(default_factory=list)


class SLOBudget(RuntimeManifestBaseModel):
    name: RuntimeSLOBudgetName
    applies_to: RuntimeSLOBudgetAppliesTo
    p95_objective_ms: StrictFloat
    hard_ceiling_ms: StrictFloat | None = None
    notes: str | None = None


class SchedulerModel(RuntimeManifestBaseModel):
    policies: list[RuntimeSchedulerPolicy] = Field(default_factory=list)
    minimize: list[RuntimeSchedulerMinimizeObjective] = Field(default_factory=list)
    maximize: list[RuntimeSchedulerMaximizeObjective] = Field(default_factory=list)
    invariants: list[RuntimeSchedulerInvariant] = Field(default_factory=list)


class MemoryModel(RuntimeManifestBaseModel):
    regions: list[RuntimeMemoryRegion] = Field(default_factory=list)
    rules: list[RuntimeMemoryRule] = Field(default_factory=list)
    failure_codes: list[RuntimeFailureCode] = Field(default_factory=list)


class EvaluationScience(RuntimeManifestBaseModel):
    dimensions: list[RuntimeEvaluationDimension] = Field(default_factory=list)
    methods: list[RuntimeEvaluationMethod] = Field(default_factory=list)
    release_blockers: list[RuntimeReleaseBlocker] = Field(default_factory=list)


class ThreatModel(RuntimeManifestBaseModel):
    threat_classes: list[RuntimeThreatClass] = Field(default_factory=list)
    controls: list[RuntimeThreatControl] = Field(default_factory=list)
    non_negotiable_rules: list[RuntimeThreatRule] = Field(default_factory=list)


class TypedFailure(RuntimeManifestBaseModel):
    code: RuntimeFailureCode
    description: str


class FormalReleaseTheorem(RuntimeManifestBaseModel):
    statement: str
    required_conditions: list[ReleaseCondition] = Field(default_factory=list)


class ReleaseArtifactBundle(RuntimeManifestBaseModel):
    required_artifacts: list[RuntimeReleaseArtifact] = Field(default_factory=list)


class ReleaseGate(RuntimeManifestBaseModel):
    gate: RuntimeReleaseGateId
    description: str


class ImmediateImplementationPR(RuntimeManifestBaseModel):
    pr: str
    focus: str
    deliverables: list[str] = Field(default_factory=list)


class DeploymentModes(RuntimeManifestBaseModel):
    current: RuntimeDeploymentMode
    supported_modes: list[RuntimeDeploymentMode] = Field(default_factory=list)
    rule: str


class AdvertisedCapabilities(RuntimeManifestBaseModel):
    runtime_modules: list[RuntimeModuleId] = Field(default_factory=list)
    public_endpoints: list[RuntimePublicEndpoint] = Field(default_factory=list)
    admin_endpoints: list[RuntimeAdminEndpoint] = Field(default_factory=list)
    feature_flag_endpoints: list[RuntimeFeatureFlagEndpoint] = Field(
        default_factory=list,
    )


class RuntimeAdminModuleSummary(RuntimeManifestBaseModel):
    module_count: StrictInt
    function_count: StrictInt
    maturity_counts: dict[RuntimeMaturity, StrictInt] = Field(default_factory=dict)
    layer_counts: dict[RuntimeLayer, StrictInt] = Field(default_factory=dict)


class RuntimeAdminEvaluationSummary(RuntimeManifestBaseModel):
    dimension_count: StrictInt
    method_count: StrictInt
    release_blocker_count: StrictInt
    benchmark_class_count: StrictInt
    slo_budget_count: StrictInt
    replay_gate_enabled: StrictBool
    tool_call_quality_gate_enabled: StrictBool
    rag_quality_gate_enabled: StrictBool
    decision_quality_gate_enabled: StrictBool


class RuntimeAdminModulesResponse(RuntimeManifestBaseModel):
    runtime_version: str
    llm_core_manifest: str
    module_manifest_version: str
    shipping_contract: ShippingContractSummary
    summary: RuntimeAdminModuleSummary
    proof_matrix: list[LayerProofMatrixEntry] = Field(default_factory=list)
    modules: list[RuntimeModuleManifestEntry] = Field(default_factory=list)
    manifest_digest: str
    signature: ManifestSignature

    @model_validator(mode="after")
    def validate_unique_identifiers(self) -> RuntimeAdminModulesResponse:
        _raise_on_duplicate_values(
            self.proof_matrix,
            "proof_matrix",
            lambda entry: entry.layer,
            "runtime admin proof matrix layers",
        )
        for index, entry in enumerate(self.proof_matrix):
            _raise_on_duplicate_values(
                entry.obligations,
                f"proof_matrix.{index}.obligations",
                lambda obligation: obligation,
                "runtime layer proof obligations",
            )
            _raise_on_duplicate_values(
                entry.evidence_paths,
                f"proof_matrix.{index}.evidence_paths",
                lambda path: path,
                "runtime layer proof evidence paths",
            )
        _raise_on_duplicate_values(
            self.modules,
            "modules",
            lambda entry: entry.name,
            "runtime admin modules",
        )
        for index, module in enumerate(self.modules):
            _raise_on_duplicate_values(
                module.public_supported_channels,
                f"modules.{index}.public_supported_channels",
                lambda channel: channel,
                "runtime module public supported channels",
            )
            _raise_on_duplicate_values(
                module.validated_auxiliary_channels,
                f"modules.{index}.validated_auxiliary_channels",
                lambda channel: channel,
                "runtime module validated auxiliary channels",
            )
            _raise_on_duplicate_values(
                module.feature_flag_channels,
                f"modules.{index}.feature_flag_channels",
                lambda channel: channel,
                "runtime module feature-flag channels",
            )
            _raise_on_duplicate_values(
                module.proof_obligations,
                f"modules.{index}.proof_obligations",
                lambda obligation: obligation,
                "runtime module proof obligations",
            )
            _raise_on_duplicate_values(
                module.functions,
                f"modules.{index}.functions",
                lambda function_name: function_name,
                "runtime module functions",
            )
            _raise_on_duplicate_values(
                module.proof_artifacts,
                f"modules.{index}.proof_artifacts",
                lambda artifact_path: artifact_path,
                "runtime module proof artifacts",
            )
            if module.function_count != len(module.functions):
                _raise_manifest_integrity_error(
                    f"modules.{index}.functions",
                    f"runtime module '{module.name.value}' function_count must equal the number "
                    f"of listed functions",
                )
        total_functions = sum(module.function_count for module in self.modules)
        if self.shipping_contract.module_count != len(self.modules):
            _raise_manifest_integrity_error(
                "shipping_contract.module_count",
                "shipping contract module count does not match admin modules inventory",
            )
        if self.shipping_contract.function_count != total_functions:
            _raise_manifest_integrity_error(
                "shipping_contract.function_count",
                "shipping contract function count does not match admin modules inventory",
            )
        if self.summary.module_count != len(self.modules):
            _raise_manifest_integrity_error(
                "summary.module_count",
                "runtime admin module count does not match admin modules inventory",
            )
        if self.summary.function_count != total_functions:
            _raise_manifest_integrity_error(
                "summary.function_count",
                "runtime admin function count does not match admin modules inventory",
            )
        expected_maturity_counts = _count_values([module.maturity for module in self.modules])
        if self.summary.maturity_counts != expected_maturity_counts:
            _raise_manifest_integrity_error(
                "summary.maturity_counts",
                "runtime admin maturity counts do not match admin modules inventory",
            )
        expected_layer_counts = _count_values([module.layer for module in self.modules])
        if self.summary.layer_counts != expected_layer_counts:
            _raise_manifest_integrity_error(
                "summary.layer_counts",
                "runtime admin layer counts do not match admin modules inventory",
            )
        return self


class RuntimeBenchmarkModuleEntry(RuntimeManifestBaseModel):
    name: RuntimeModuleId
    function_count: StrictInt
    benchmark_artifact: str
    benchmark_speedup_x: StrictFloat
    compiled_artifact: str
    compiled_engine: RuntimeCompiledEngine
    max_cold_ms: StrictFloat
    max_warm_ms: StrictFloat
    max_hot_ms: StrictFloat


class RuntimeAdminBenchmarksResponse(RuntimeManifestBaseModel):
    runtime_version: str
    llm_core_manifest: str
    module_manifest_version: str
    benchmark_discovery_lane: BenchmarkDiscoveryLane
    benchmarking: BenchmarkFramework
    slo_budgets: list[SLOBudget] = Field(default_factory=list)
    quality_gate_benchmark_classes: list[BenchmarkClassEntry] = Field(default_factory=list)
    quality_gate_slo_budgets: list[SLOBudget] = Field(default_factory=list)
    evaluation_science: EvaluationScience
    evaluation_summary: RuntimeAdminEvaluationSummary
    compiled_artifacts: list[ArtifactReference] = Field(default_factory=list)
    shipping_runtime_modules: list[RuntimeModuleId] = Field(default_factory=list)
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
    shipping_runtime_compiled_engines: list[RuntimeCompiledEngine] = Field(
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
    module_benchmarks: list[RuntimeBenchmarkModuleEntry] = Field(
        default_factory=list,
    )
    manifest_digest: str
    signature: ManifestSignature

    @model_validator(mode="after")
    def validate_unique_identifiers(self) -> RuntimeAdminBenchmarksResponse:
        _raise_on_duplicate_values(
            self.benchmarking.classes,
            "benchmarking.classes",
            lambda entry: entry.code,
            "runtime benchmark classes",
        )
        _raise_on_duplicate_values(
            self.quality_gate_benchmark_classes,
            "quality_gate_benchmark_classes",
            lambda entry: entry.code,
            "runtime evaluation benchmark classes",
        )
        _raise_on_duplicate_values(
            self.benchmarking.required_metrics,
            "benchmarking.required_metrics",
            lambda metric: metric,
            "runtime benchmark required metrics",
        )
        _raise_on_duplicate_values(
            self.benchmarking.baselines,
            "benchmarking.baselines",
            lambda baseline: baseline,
            "runtime benchmark baselines",
        )
        _raise_on_duplicate_values(
            self.module_benchmarks,
            "module_benchmarks",
            lambda entry: entry.name,
            "runtime benchmark modules",
        )
        _raise_on_duplicate_values(
            self.quality_gate_slo_budgets,
            "quality_gate_slo_budgets",
            lambda entry: entry.name,
            "runtime evaluation SLO budgets",
        )
        _raise_on_duplicate_values(
            self.compiled_artifacts,
            "compiled_artifacts",
            lambda entry: entry.path,
            "runtime compiled artifacts",
        )
        _raise_on_duplicate_values(
            self.shipping_runtime_modules,
            "shipping_runtime_modules",
            lambda entry: entry,
            "runtime benchmark shipping modules",
        )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(self.module_benchmarks):
            _raise_manifest_integrity_error(
                "benchmark_discovery_lane.shipping_manifest_modules",
                "runtime benchmark discovery shipping module count does not match benchmark module inventory",
            )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(
            self.shipping_runtime_modules
        ):
            _raise_manifest_integrity_error(
                "shipping_runtime_modules",
                "runtime benchmark shipping module list count does not match benchmark discovery shipping module count",
            )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(
            self.shipping_runtime_function_counts
        ):
            _raise_manifest_integrity_error(
                "shipping_runtime_function_counts",
                "runtime benchmark shipping function inventory count does not match benchmark discovery shipping module count",
            )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(
            self.shipping_runtime_benchmark_speedups_x
        ):
            _raise_manifest_integrity_error(
                "shipping_runtime_benchmark_speedups_x",
                "runtime benchmark shipping speedup inventory count does not match benchmark discovery shipping module count",
            )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(
            self.shipping_runtime_benchmark_artifacts
        ):
            _raise_manifest_integrity_error(
                "shipping_runtime_benchmark_artifacts",
                "runtime benchmark shipping artifact inventory count does not match benchmark discovery shipping module count",
            )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(
            self.shipping_runtime_compiled_artifacts
        ):
            _raise_manifest_integrity_error(
                "shipping_runtime_compiled_artifacts",
                "runtime benchmark shipping compiled artifact inventory count does not match benchmark discovery shipping module count",
            )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(
            self.shipping_runtime_compiled_engines
        ):
            _raise_manifest_integrity_error(
                "shipping_runtime_compiled_engines",
                "runtime benchmark shipping compiled engine inventory count does not match benchmark discovery shipping module count",
            )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(
            self.shipping_runtime_max_cold_ms
        ):
            _raise_manifest_integrity_error(
                "shipping_runtime_max_cold_ms",
                "runtime benchmark shipping max_cold_ms inventory count does not match benchmark discovery shipping module count",
            )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(
            self.shipping_runtime_max_warm_ms
        ):
            _raise_manifest_integrity_error(
                "shipping_runtime_max_warm_ms",
                "runtime benchmark shipping max_warm_ms inventory count does not match benchmark discovery shipping module count",
            )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(
            self.shipping_runtime_max_hot_ms
        ):
            _raise_manifest_integrity_error(
                "shipping_runtime_max_hot_ms",
                "runtime benchmark shipping max_hot_ms inventory count does not match benchmark discovery shipping module count",
            )
        total_functions = sum(entry.function_count for entry in self.module_benchmarks)
        if self.benchmark_discovery_lane.shipping_manifest_functions != total_functions:
            _raise_manifest_integrity_error(
                "benchmark_discovery_lane.shipping_manifest_functions",
                "runtime benchmark discovery shipping function count does not match benchmark module inventory",
            )
        benchmark_class_codes = {entry.code for entry in self.benchmarking.classes}
        quality_gate_class_codes = {entry.code for entry in self.quality_gate_benchmark_classes}
        if not quality_gate_class_codes.issubset(benchmark_class_codes):
            _raise_manifest_integrity_error(
                "quality_gate_benchmark_classes",
                "runtime evaluation benchmark classes must be declared in benchmarking.classes",
            )
        budget_names = {entry.name for entry in self.slo_budgets}
        quality_gate_budget_names = {entry.name for entry in self.quality_gate_slo_budgets}
        if not quality_gate_budget_names.issubset(budget_names):
            _raise_manifest_integrity_error(
                "quality_gate_slo_budgets",
                "runtime evaluation SLO budgets must be declared in slo_budgets",
            )
        dimensions = set(self.evaluation_science.dimensions)
        release_blockers = set(self.evaluation_science.release_blockers)
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
        if self.evaluation_summary.dimension_count != len(self.evaluation_science.dimensions):
            _raise_manifest_integrity_error(
                "evaluation_summary.dimension_count",
                "runtime evaluation dimension count does not match evaluation_science.dimensions",
            )
        if self.evaluation_summary.method_count != len(self.evaluation_science.methods):
            _raise_manifest_integrity_error(
                "evaluation_summary.method_count",
                "runtime evaluation method count does not match evaluation_science.methods",
            )
        if self.evaluation_summary.release_blocker_count != len(
            self.evaluation_science.release_blockers
        ):
            _raise_manifest_integrity_error(
                "evaluation_summary.release_blocker_count",
                "runtime evaluation blocker count does not match evaluation_science.release_blockers",
            )
        if self.evaluation_summary.benchmark_class_count != len(self.quality_gate_benchmark_classes):
            _raise_manifest_integrity_error(
                "evaluation_summary.benchmark_class_count",
                "runtime evaluation benchmark class count does not match quality_gate_benchmark_classes",
            )
        if self.evaluation_summary.slo_budget_count != len(self.quality_gate_slo_budgets):
            _raise_manifest_integrity_error(
                "evaluation_summary.slo_budget_count",
                "runtime evaluation SLO budget count does not match quality_gate_slo_budgets",
            )
        if self.evaluation_summary.replay_gate_enabled != expected_replay_gate:
            _raise_manifest_integrity_error(
                "evaluation_summary.replay_gate_enabled",
                "runtime replay quality gate flag does not match benchmark, budget, and evaluation science coverage",
            )
        if (
            self.evaluation_summary.tool_call_quality_gate_enabled
            != expected_tool_call_quality_gate
        ):
            _raise_manifest_integrity_error(
                "evaluation_summary.tool_call_quality_gate_enabled",
                "runtime tool-call quality gate flag does not match benchmark, budget, and evaluation science coverage",
            )
        if self.evaluation_summary.rag_quality_gate_enabled != expected_rag_quality_gate:
            _raise_manifest_integrity_error(
                "evaluation_summary.rag_quality_gate_enabled",
                "runtime RAG quality gate flag does not match benchmark and evaluation science coverage",
            )
        if (
            self.evaluation_summary.decision_quality_gate_enabled
            != expected_decision_quality_gate
        ):
            _raise_manifest_integrity_error(
                "evaluation_summary.decision_quality_gate_enabled",
                "runtime decision quality gate flag does not match benchmark, budget, and evaluation science coverage",
            )
        discovered_import_path_set = {
            entry.import_path for entry in self.benchmark_discovery_lane.discovered_source_inventory
        }
        for index, entry in enumerate(self.module_benchmarks):
            if entry.name.value not in discovered_import_path_set:
                _raise_manifest_integrity_error(
                    "benchmark_discovery_lane.discovered_source_inventory",
                    f"runtime benchmark discovery source inventory must include module_benchmarks.{index}.name ('{entry.name.value}')",
                )
            if self.shipping_runtime_modules[index] != entry.name:
                _raise_manifest_integrity_error(
                    f"shipping_runtime_modules.{index}",
                    f"runtime benchmark shipping module does not match module_benchmarks.{index}.name",
                )
            if self.shipping_runtime_function_counts[index] != entry.function_count:
                _raise_manifest_integrity_error(
                    f"shipping_runtime_function_counts.{index}",
                    f"runtime benchmark shipping function inventory does not match module_benchmarks.{index}.function_count",
                )
            if self.shipping_runtime_benchmark_speedups_x[index] != entry.benchmark_speedup_x:
                _raise_manifest_integrity_error(
                    f"shipping_runtime_benchmark_speedups_x.{index}",
                    f"runtime benchmark shipping speedup inventory does not match module_benchmarks.{index}.benchmark_speedup_x",
                )
            if self.shipping_runtime_benchmark_artifacts[index] != entry.benchmark_artifact:
                _raise_manifest_integrity_error(
                    f"shipping_runtime_benchmark_artifacts.{index}",
                    f"runtime benchmark shipping artifact inventory does not match module_benchmarks.{index}.benchmark_artifact",
                )
            if self.shipping_runtime_compiled_artifacts[index] != entry.compiled_artifact:
                _raise_manifest_integrity_error(
                    f"shipping_runtime_compiled_artifacts.{index}",
                    f"runtime benchmark shipping compiled artifact inventory does not match module_benchmarks.{index}.compiled_artifact",
                )
            if self.shipping_runtime_compiled_engines[index] != entry.compiled_engine:
                _raise_manifest_integrity_error(
                    f"shipping_runtime_compiled_engines.{index}",
                    f"runtime benchmark shipping compiled engine inventory does not match module_benchmarks.{index}.compiled_engine",
                )
            if self.shipping_runtime_max_cold_ms[index] != entry.max_cold_ms:
                _raise_manifest_integrity_error(
                    f"shipping_runtime_max_cold_ms.{index}",
                    f"runtime benchmark shipping max_cold_ms inventory does not match module_benchmarks.{index}.max_cold_ms",
                )
            if self.shipping_runtime_max_warm_ms[index] != entry.max_warm_ms:
                _raise_manifest_integrity_error(
                    f"shipping_runtime_max_warm_ms.{index}",
                    f"runtime benchmark shipping max_warm_ms inventory does not match module_benchmarks.{index}.max_warm_ms",
                )
            if self.shipping_runtime_max_hot_ms[index] != entry.max_hot_ms:
                _raise_manifest_integrity_error(
                    f"shipping_runtime_max_hot_ms.{index}",
                    f"runtime benchmark shipping max_hot_ms inventory does not match module_benchmarks.{index}.max_hot_ms",
                )
            if entry.benchmark_speedup_x <= 0:
                _raise_manifest_integrity_error(
                    f"module_benchmarks.{index}.benchmark_speedup_x",
                    "runtime benchmark module benchmark_speedup_x must be positive",
                )
            if entry.max_cold_ms <= 0:
                _raise_manifest_integrity_error(
                    f"module_benchmarks.{index}.max_cold_ms",
                    "runtime benchmark module max_cold_ms must be positive",
                )
            if entry.max_warm_ms <= 0:
                _raise_manifest_integrity_error(
                    f"module_benchmarks.{index}.max_warm_ms",
                    "runtime benchmark module max_warm_ms must be positive",
                )
            if entry.max_hot_ms <= 0:
                _raise_manifest_integrity_error(
                    f"module_benchmarks.{index}.max_hot_ms",
                    "runtime benchmark module max_hot_ms must be positive",
                )
        compiled_artifact_paths = {artifact.path for artifact in self.compiled_artifacts}
        benchmark_artifact_indexes: dict[str, int] = {}
        for index, entry in enumerate(self.module_benchmarks):
            previous_index = benchmark_artifact_indexes.get(entry.benchmark_artifact)
            if previous_index is not None:
                _raise_manifest_integrity_error(
                    f"module_benchmarks.{index}.benchmark_artifact",
                    f"runtime benchmark artifact path duplicates module_benchmarks.{previous_index}.benchmark_artifact",
                )
            benchmark_artifact_indexes[entry.benchmark_artifact] = index
            if entry.compiled_artifact not in compiled_artifact_paths:
                _raise_manifest_integrity_error(
                    f"module_benchmarks.{index}.compiled_artifact",
                    "runtime benchmark module compiled_artifact must reference a compiled_artifacts path",
                )
        return self


class ReleaseConditionEvaluation(RuntimeManifestBaseModel):
    condition: ReleaseCondition
    satisfied: StrictBool
    detail: str
    evidence_paths: list[str] = Field(default_factory=list)


class RuntimeReleaseValidationResponse(RuntimeManifestBaseModel):
    runtime_version: str
    llm_core_manifest: str
    module_manifest_version: str
    theorem_statement: str
    valid_release: StrictBool
    conditions: list[ReleaseConditionEvaluation] = Field(default_factory=list)
    deployment_mode: RuntimeDeploymentMode | None = None
    deployment_mode_raw: str
    manifest_digest: str
    signature: ManifestSignature

    @model_validator(mode="after")
    def validate_unique_identifiers(self) -> RuntimeReleaseValidationResponse:
        _raise_on_duplicate_values(
            self.conditions,
            "conditions",
            lambda entry: entry.condition,
            "runtime release validation conditions",
        )
        for index, condition in enumerate(self.conditions):
            _raise_on_duplicate_values(
                condition.evidence_paths,
                f"conditions.{index}.evidence_paths",
                lambda path: path,
                "runtime release validation evidence paths",
            )
        return self


class RuntimeManifestBuildError(ValueError):
    def __init__(
        self, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _manifest_error_details(path: str, message: str) -> dict[str, Any]:
    return {
        "cause": path,
        "validation_errors": [
            {
                "path": path,
                "message": message,
                "type": "value_error",
            }
        ],
    }


def _raise_manifest_integrity_error(path: str, message: str) -> None:
    raise RuntimeManifestBuildError(
        "invalid_runtime_manifest_payload",
        message,
        _manifest_error_details(path, message),
    )


def _raise_on_duplicate_values(
    values: list[Any],
    path: str,
    value_selector: Any,
    label: str,
) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for entry in values:
        raw_value = value_selector(entry)
        normalized = raw_value.value if isinstance(raw_value, Enum) else str(raw_value)
        if normalized in seen and normalized not in duplicates:
            duplicates.append(normalized)
        seen.add(normalized)
    if duplicates:
        duplicate_text = ", ".join(duplicates)
        _raise_manifest_integrity_error(
            path,
            f"{label} must be unique; duplicate entries: {duplicate_text}",
        )


class RuntimeManifestResponse(RuntimeManifestBaseModel):
    runtime_version: str
    mojo_version: str
    llm_core_manifest: str
    module_manifest_version: str
    generated_at: str
    modules: list[RuntimeModuleManifestEntry] = Field(default_factory=list)
    compiled_artifacts: list[ArtifactReference] = Field(default_factory=list)
    supported_channels: list[RuntimeSupportedChannel] = Field(default_factory=list)
    validated_auxiliary_channels: list[RuntimeAuxiliaryChannel] = Field(
        default_factory=list,
    )
    feature_flag_channels: list[RuntimeFeatureFlagChannel] = Field(
        default_factory=list,
    )
    maturity: dict[RuntimeModuleId, RuntimeMaturity] = Field(default_factory=dict)
    policy_snapshot: SnapshotReference
    schema_snapshot: SnapshotReference
    deployment_mode: RuntimeDeploymentMode
    deployment_modes: DeploymentModes
    shipping_contract: ShippingContractSummary
    benchmark_discovery_lane: BenchmarkDiscoveryLane
    advertised_capabilities: AdvertisedCapabilities
    system_invariants: list[NamedRule] = Field(default_factory=list)
    execution_model: ExecutionModel
    external_nondeterminism: ExternalNondeterminismPolicy
    artifact_lineage: ArtifactLineageSchema
    capability_algebra: CapabilityAlgebraSchema
    kernel_promotion_criteria: KernelPromotionCriteria
    proof_matrix: list[LayerProofMatrixEntry] = Field(default_factory=list)
    benchmarking: BenchmarkFramework
    slo_budgets: list[SLOBudget] = Field(default_factory=list)
    scheduler_model: SchedulerModel
    memory_model: MemoryModel
    evaluation_science: EvaluationScience
    typed_failures: list[TypedFailure] = Field(default_factory=list)
    threat_model: ThreatModel
    formal_release_theorem: FormalReleaseTheorem
    release_artifact_bundle: ReleaseArtifactBundle
    release_gates: list[ReleaseGate] = Field(default_factory=list)
    immediate_implementation_sequence: list[ImmediateImplementationPR] = Field(
        default_factory=list,
    )
    manifest_digest: str
    signature: ManifestSignature

    @model_validator(mode="after")
    def validate_manifest(self) -> RuntimeManifestResponse:
        _raise_on_duplicate_values(
            self.supported_channels,
            "supported_channels",
            lambda entry: entry,
            "runtime supported channels",
        )
        _raise_on_duplicate_values(
            self.validated_auxiliary_channels,
            "validated_auxiliary_channels",
            lambda entry: entry,
            "runtime validated auxiliary channels",
        )
        _raise_on_duplicate_values(
            self.feature_flag_channels,
            "feature_flag_channels",
            lambda entry: entry,
            "runtime feature-flag channels",
        )
        _raise_on_duplicate_values(
            self.deployment_modes.supported_modes,
            "deployment_modes.supported_modes",
            lambda entry: entry,
            "runtime deployment modes",
        )
        _raise_on_duplicate_values(
            self.advertised_capabilities.runtime_modules,
            "advertised_capabilities.runtime_modules",
            lambda entry: entry,
            "advertised runtime modules",
        )
        _raise_on_duplicate_values(
            self.advertised_capabilities.public_endpoints,
            "advertised_capabilities.public_endpoints",
            lambda entry: entry,
            "advertised public endpoints",
        )
        _raise_on_duplicate_values(
            self.advertised_capabilities.admin_endpoints,
            "advertised_capabilities.admin_endpoints",
            lambda entry: entry,
            "advertised admin endpoints",
        )
        _raise_on_duplicate_values(
            self.advertised_capabilities.feature_flag_endpoints,
            "advertised_capabilities.feature_flag_endpoints",
            lambda entry: entry,
            "advertised feature-flag endpoints",
        )
        _raise_on_duplicate_values(
            self.system_invariants,
            "system_invariants",
            lambda entry: entry.name,
            "runtime system invariants",
        )
        _raise_on_duplicate_values(
            self.execution_model.state_fields,
            "execution_model.state_fields",
            lambda entry: entry,
            "runtime execution state fields",
        )
        _raise_on_duplicate_values(
            self.execution_model.allowed_transitions,
            "execution_model.allowed_transitions",
            lambda entry: entry,
            "runtime execution transitions",
        )
        _raise_on_duplicate_values(
            self.execution_model.validity_rules,
            "execution_model.validity_rules",
            lambda entry: entry,
            "runtime execution validity rules",
        )
        _raise_on_duplicate_values(
            self.external_nondeterminism.sources,
            "external_nondeterminism.sources",
            lambda entry: entry,
            "runtime nondeterminism sources",
        )
        _raise_on_duplicate_values(
            self.external_nondeterminism.required_artifacts,
            "external_nondeterminism.required_artifacts",
            lambda entry: entry,
            "runtime nondeterminism artifacts",
        )
        _raise_on_duplicate_values(
            self.external_nondeterminism.failure_codes,
            "external_nondeterminism.failure_codes",
            lambda entry: entry,
            "runtime nondeterminism failure codes",
        )
        _raise_on_duplicate_values(
            self.artifact_lineage.artifact_flow,
            "artifact_lineage.artifact_flow",
            lambda entry: entry,
            "runtime artifact lineage steps",
        )
        _raise_on_duplicate_values(
            self.artifact_lineage.required_node_fields,
            "artifact_lineage.required_node_fields",
            lambda entry: entry,
            "runtime artifact lineage node fields",
        )
        _raise_on_duplicate_values(
            self.capability_algebra.required_fields,
            "capability_algebra.required_fields",
            lambda entry: entry,
            "runtime capability fields",
        )
        _raise_on_duplicate_values(
            self.capability_algebra.enums.side_effect_class,
            "capability_algebra.enums.side_effect_class",
            lambda entry: entry,
            "runtime capability side-effect classes",
        )
        _raise_on_duplicate_values(
            self.capability_algebra.enums.risk_level,
            "capability_algebra.enums.risk_level",
            lambda entry: entry,
            "runtime capability risk levels",
        )
        _raise_on_duplicate_values(
            self.capability_algebra.enums.replayability,
            "capability_algebra.enums.replayability",
            lambda entry: entry,
            "runtime capability replayability modes",
        )
        _raise_on_duplicate_values(
            self.capability_algebra.rules,
            "capability_algebra.rules",
            lambda entry: entry,
            "runtime capability rules",
        )
        _raise_on_duplicate_values(
            self.kernel_promotion_criteria.required_manifest_fields,
            "kernel_promotion_criteria.required_manifest_fields",
            lambda entry: entry,
            "kernel promotion required manifest fields",
        )
        _raise_on_duplicate_values(
            self.kernel_promotion_criteria.required_proof_reference_fields,
            "kernel_promotion_criteria.required_proof_reference_fields",
            lambda entry: entry,
            "kernel promotion required proof reference fields",
        )
        _raise_on_duplicate_values(
            self.proof_matrix,
            "proof_matrix",
            lambda entry: entry.layer,
            "runtime proof matrix layers",
        )
        for index, entry in enumerate(self.proof_matrix):
            _raise_on_duplicate_values(
                entry.obligations,
                f"proof_matrix.{index}.obligations",
                lambda obligation: obligation,
                "runtime layer proof obligations",
            )
            _raise_on_duplicate_values(
                entry.evidence_paths,
                f"proof_matrix.{index}.evidence_paths",
                lambda path: path,
                "runtime layer proof evidence paths",
            )
        _raise_on_duplicate_values(
            self.benchmarking.classes,
            "benchmarking.classes",
            lambda entry: entry.code,
            "runtime benchmark classes",
        )
        _raise_on_duplicate_values(
            self.benchmarking.required_metrics,
            "benchmarking.required_metrics",
            lambda entry: entry,
            "runtime benchmark required metrics",
        )
        _raise_on_duplicate_values(
            self.benchmarking.baselines,
            "benchmarking.baselines",
            lambda entry: entry,
            "runtime benchmark baselines",
        )
        _raise_on_duplicate_values(
            self.scheduler_model.policies,
            "scheduler_model.policies",
            lambda entry: entry,
            "runtime scheduler policies",
        )
        _raise_on_duplicate_values(
            self.scheduler_model.minimize,
            "scheduler_model.minimize",
            lambda entry: entry,
            "runtime scheduler minimize objectives",
        )
        _raise_on_duplicate_values(
            self.scheduler_model.maximize,
            "scheduler_model.maximize",
            lambda entry: entry,
            "runtime scheduler maximize objectives",
        )
        _raise_on_duplicate_values(
            self.scheduler_model.invariants,
            "scheduler_model.invariants",
            lambda entry: entry,
            "runtime scheduler invariants",
        )
        _raise_on_duplicate_values(
            self.memory_model.regions,
            "memory_model.regions",
            lambda entry: entry,
            "runtime memory regions",
        )
        _raise_on_duplicate_values(
            self.memory_model.rules,
            "memory_model.rules",
            lambda entry: entry,
            "runtime memory rules",
        )
        _raise_on_duplicate_values(
            self.memory_model.failure_codes,
            "memory_model.failure_codes",
            lambda entry: entry,
            "runtime memory failure codes",
        )
        _raise_on_duplicate_values(
            self.evaluation_science.dimensions,
            "evaluation_science.dimensions",
            lambda entry: entry,
            "runtime evaluation dimensions",
        )
        _raise_on_duplicate_values(
            self.evaluation_science.methods,
            "evaluation_science.methods",
            lambda entry: entry,
            "runtime evaluation methods",
        )
        _raise_on_duplicate_values(
            self.evaluation_science.release_blockers,
            "evaluation_science.release_blockers",
            lambda entry: entry,
            "runtime evaluation release blockers",
        )
        _raise_on_duplicate_values(
            self.typed_failures,
            "typed_failures",
            lambda entry: entry.code,
            "runtime typed failures",
        )
        _raise_on_duplicate_values(
            self.threat_model.threat_classes,
            "threat_model.threat_classes",
            lambda entry: entry,
            "runtime threat classes",
        )
        _raise_on_duplicate_values(
            self.threat_model.controls,
            "threat_model.controls",
            lambda entry: entry,
            "runtime threat controls",
        )
        _raise_on_duplicate_values(
            self.threat_model.non_negotiable_rules,
            "threat_model.non_negotiable_rules",
            lambda entry: entry,
            "runtime threat non-negotiable rules",
        )
        _raise_on_duplicate_values(
            self.release_gates,
            "release_gates",
            lambda entry: entry.gate,
            "runtime release gates",
        )
        _raise_on_duplicate_values(
            self.immediate_implementation_sequence,
            "immediate_implementation_sequence",
            lambda entry: entry.pr,
            "runtime implementation sequence PRs",
        )
        _raise_on_duplicate_values(
            self.formal_release_theorem.required_conditions,
            "formal_release_theorem.required_conditions",
            lambda entry: entry,
            "formal release theorem conditions",
        )
        _raise_on_duplicate_values(
            self.release_artifact_bundle.required_artifacts,
            "release_artifact_bundle.required_artifacts",
            lambda entry: entry,
            "release artifact bundle entries",
        )
        _raise_on_duplicate_values(
            self.compiled_artifacts,
            "compiled_artifacts",
            lambda entry: entry.path,
            "runtime compiled artifacts",
        )
        module_names = _enum_values([module.name for module in self.modules])
        if len(module_names) != len(set(module_names)):
            _raise_manifest_integrity_error(
                "modules",
                "runtime manifest contains duplicate module entries",
            )
        _raise_on_duplicate_values(
            self.modules,
            "modules",
            lambda module: module.capability_id,
            "runtime module capability ids",
        )
        if self.shipping_contract.module_count != len(self.modules):
            _raise_manifest_integrity_error(
                "shipping_contract.module_count",
                "shipping contract module count does not match manifest modules",
            )
        total_functions = sum(module.function_count for module in self.modules)
        if self.shipping_contract.function_count != total_functions:
            _raise_manifest_integrity_error(
                "shipping_contract.function_count",
                "shipping contract function count does not match manifest modules",
            )
        if self.benchmark_discovery_lane.shipping_manifest_modules != len(self.modules):
            _raise_manifest_integrity_error(
                "benchmark_discovery_lane.shipping_manifest_modules",
                "benchmark discovery shipping module count does not match manifest modules",
            )
        if self.benchmark_discovery_lane.shipping_manifest_functions != total_functions:
            _raise_manifest_integrity_error(
                "benchmark_discovery_lane.shipping_manifest_functions",
                "benchmark discovery shipping function count does not match manifest modules",
            )
        discovered_import_path_set = {
            entry.import_path for entry in self.benchmark_discovery_lane.discovered_source_inventory
        }
        for module_name in module_names:
            if module_name not in discovered_import_path_set:
                _raise_manifest_integrity_error(
                    "benchmark_discovery_lane.discovered_source_inventory",
                    f"benchmark discovery source inventory must include shipping manifest module '{module_name}'",
                )
        if module_names != _enum_values(self.advertised_capabilities.runtime_modules):
            _raise_manifest_integrity_error(
                "advertised_capabilities.runtime_modules",
                "advertised runtime modules must exactly match manifest module order",
            )
        if _enum_values(self.advertised_capabilities.public_endpoints) != list(_PUBLIC_ENDPOINTS):
            _raise_manifest_integrity_error(
                "advertised_capabilities.public_endpoints",
                "public endpoint boundary drifted from the signed runtime manifest",
            )
        if _enum_values(self.advertised_capabilities.admin_endpoints) != list(_ADMIN_ENDPOINTS):
            _raise_manifest_integrity_error(
                "advertised_capabilities.admin_endpoints",
                "admin endpoint boundary drifted from the signed runtime manifest",
            )
        if _enum_values(self.advertised_capabilities.feature_flag_endpoints) != list(
            _FEATURE_FLAG_ENDPOINTS
        ):
            _raise_manifest_integrity_error(
                "advertised_capabilities.feature_flag_endpoints",
                "feature-flag endpoint boundary drifted from the signed runtime manifest"
            )
        for index, module in enumerate(self.modules):
            _raise_on_duplicate_values(
                module.public_supported_channels,
                f"modules.{index}.public_supported_channels",
                lambda channel: channel,
                "runtime module public supported channels",
            )
            _raise_on_duplicate_values(
                module.validated_auxiliary_channels,
                f"modules.{index}.validated_auxiliary_channels",
                lambda channel: channel,
                "runtime module validated auxiliary channels",
            )
            _raise_on_duplicate_values(
                module.feature_flag_channels,
                f"modules.{index}.feature_flag_channels",
                lambda channel: channel,
                "runtime module feature-flag channels",
            )
            _raise_on_duplicate_values(
                module.proof_obligations,
                f"modules.{index}.proof_obligations",
                lambda obligation: obligation,
                "runtime module proof obligations",
            )
            _raise_on_duplicate_values(
                module.functions,
                f"modules.{index}.functions",
                lambda function_name: function_name,
                "runtime module functions",
            )
            _raise_on_duplicate_values(
                module.proof_artifacts,
                f"modules.{index}.proof_artifacts",
                lambda artifact_path: artifact_path,
                "runtime module proof artifacts",
            )
            if self.maturity.get(module.name) != module.maturity:
                _raise_manifest_integrity_error(
                    f"maturity.{module.name.value}",
                    f"maturity map mismatch for module '{module.name.value}'",
                )
            if not module.proof_artifacts:
                _raise_manifest_integrity_error(
                    f"modules.{index}.proof_artifacts",
                    f"module '{module.name.value}' is missing proof artifacts",
                )
            if module.function_count != len(module.functions):
                _raise_manifest_integrity_error(
                    f"modules.{index}.functions",
                    f"module '{module.name.value}' function_count must equal the number "
                    f"of listed functions",
                )
            if not set(self.supported_channels).issubset(module.public_supported_channels):
                _raise_manifest_integrity_error(
                    f"modules.{index}.public_supported_channels",
                    f"module '{module.name.value}' does not cover all public supported channels"
                )
            if not module.capability_id:
                _raise_manifest_integrity_error(
                    f"modules.{index}.capability_id",
                    f"module '{module.name.value}' is missing a stable capability_id",
                )
            if not module.owner:
                _raise_manifest_integrity_error(
                    f"modules.{index}.owner",
                    f"module '{module.name.value}' is missing an owner",
                )
            if not module.contract_boundary:
                _raise_manifest_integrity_error(
                    f"modules.{index}.contract_boundary",
                    f"module '{module.name.value}' is missing a bounded contract description",
                )
            if module.promotion_status is not RuntimeKernelPromotionStatus.shipping:
                _raise_manifest_integrity_error(
                    f"modules.{index}.promotion_status",
                    f"module '{module.name.value}' must be marked shipping to appear in the signed runtime manifest",
                )
            for field_name in self.kernel_promotion_criteria.required_manifest_fields:
                field_value = getattr(module, field_name, None)
                if isinstance(field_value, str):
                    field_value = field_value.strip()
                if field_value in (None, ""):
                    _raise_manifest_integrity_error(
                        f"modules.{index}.{field_name}",
                        f"shipping module '{module.name.value}' is missing required kernel promotion field '{field_name}'",
                    )
            for field_name in self.kernel_promotion_criteria.required_proof_reference_fields:
                field_value = getattr(module, field_name, None)
                if isinstance(field_value, str):
                    field_value = field_value.strip()
                if field_value in (None, ""):
                    _raise_manifest_integrity_error(
                        f"modules.{index}.{field_name}",
                        f"shipping module '{module.name.value}' is missing required kernel promotion proof '{field_name}'",
                    )
            minimum_speedup = 1.0 + (
                self.kernel_promotion_criteria.minimum_primary_metric_improvement_pct / 100.0
            )
            if module.benchmark_speedup_x < minimum_speedup:
                _raise_manifest_integrity_error(
                    f"modules.{index}.benchmark_speedup_x",
                    f"shipping module '{module.name.value}' must meet the kernel promotion minimum speedup threshold",
                )
        release_conditions = set(self.formal_release_theorem.required_conditions)
        expected_conditions = {
            ReleaseCondition.manifest_listed,
            ReleaseCondition.proof_backed,
            ReleaseCondition.policy_covered,
            ReleaseCondition.replay_tested,
            ReleaseCondition.deployment_mode_validated,
        }
        if release_conditions != expected_conditions:
            _raise_manifest_integrity_error(
                "formal_release_theorem.required_conditions",
                "formal release theorem conditions drifted from the expected set",
            )
        if not self.manifest_digest:
            _raise_manifest_integrity_error(
                "manifest_digest",
                "runtime manifest signature is incomplete",
            )
        if not self.signature.signature_hex:
            _raise_manifest_integrity_error(
                "signature.signature_hex",
                "runtime manifest signature is incomplete",
            )
        return self


def _format_runtime_manifest_validation_path(location: tuple[Any, ...]) -> str:
    return ".".join(str(item) for item in location if str(item))


def _build_runtime_manifest_error_details(exc: ValidationError) -> dict[str, Any]:
    try:
        errors = exc.errors(include_url=False, include_context=True, include_input=False)
    except TypeError:  # pragma: no cover - compatibility guard
        errors = exc.errors()

    normalized_errors: list[dict[str, str]] = []
    cause: str | None = None
    for error in errors:
        ctx = error.get("ctx")
        nested_error = ctx.get("error") if isinstance(ctx, dict) else None
        if isinstance(nested_error, RuntimeManifestBuildError):
            nested_details = nested_error.details if isinstance(nested_error.details, dict) else {}
            nested_validation_errors = nested_details.get("validation_errors")
            if isinstance(nested_validation_errors, list):
                normalized_errors.extend(
                    item for item in nested_validation_errors if isinstance(item, dict)
                )
            nested_cause = nested_details.get("cause")
            if cause is None and isinstance(nested_cause, str) and nested_cause:
                cause = nested_cause
            if normalized_errors:
                continue
        path = _format_runtime_manifest_validation_path(tuple(error.get("loc") or ()))
        normalized_errors.append(
            {
                "path": path,
                "message": str(error.get("msg", "Invalid value")),
                "type": str(error.get("type", "validation_error")),
            }
        )

    if cause is None:
        cause = next(
            (str(item.get("path")) for item in normalized_errors if item.get("path")),
            str(exc),
        )
    details: dict[str, Any] = {"cause": cause}
    if normalized_errors:
        details["validation_errors"] = normalized_errors
    return details


def _format_runtime_manifest_build_error_message(details: dict[str, Any]) -> str:
    return _format_runtime_payload_build_error_message(
        "Signed runtime manifest build produced an invalid payload.",
        details,
    )


def _format_runtime_payload_build_error_message(prefix: str, details: dict[str, Any]) -> str:
    cause = details.get("cause")
    if isinstance(cause, str) and cause:
        return f"{prefix}: {cause}"
    return prefix


def _raise_runtime_payload_build_error(
    code: str,
    prefix: str,
    exc: ValidationError,
) -> None:
    details = _build_runtime_manifest_error_details(exc)
    raise RuntimeManifestBuildError(
        code,
        _format_runtime_payload_build_error_message(prefix, details),
        details,
    ) from exc


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _build_artifact_reference(path: Path, *, kind: RuntimeArtifactKind) -> ArtifactReference:
    return ArtifactReference(
        kind=kind,
        path=str(path.relative_to(_ROOT)),
        sha256=_sha256_file(path),
        size_bytes=path.stat().st_size,
    )


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def _manifest_signing_secret() -> str:
    settings = get_settings()
    seed = settings.license_signing_secret or settings.jwt_secret
    return hashlib.sha256(f"{seed}:runtime-manifest-signing".encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def _detect_mojo_version() -> str:
    candidate = os.getenv("MOJO_VERSION")
    if candidate:
        return candidate.strip()
    executable = shutil.which("mojo")
    if executable is None:
        return "unknown"
    try:
        proc = subprocess.run(  # noqa: S603
            [executable, "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    output = (proc.stdout or proc.stderr).strip()
    return output or "unknown"


def _deployment_mode() -> str:
    raw_mode = os.getenv("ALGENTA_DEPLOYMENT_MODE", "").strip().lower()
    if raw_mode in {
        "saas",
        "vpc",
        "self_hosted",
        "air_gapped",
        "hybrid_provider",
        "local_dev_daemon",
    }:
        return raw_mode
    settings = get_settings()
    return "local_dev_daemon" if settings.is_development else "saas"


def _runtime_deployment_mode_value(value: object) -> str:
    if isinstance(value, RuntimeDeploymentMode):
        return value.value
    return str(value)


def _enum_values(values: list[object]) -> list[str]:
    return [item.value if isinstance(item, Enum) else str(item) for item in values]


def _raw_runtime_dict_key(value: object) -> str:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, str):
        return value
    return str(value)


def _raw_runtime_payload(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return {
            field_name: _raw_runtime_payload(getattr(value, field_name))
            for field_name in value.__class__.model_fields
        }
    if isinstance(value, list):
        return [_raw_runtime_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_raw_runtime_payload(item) for item in value]
    if isinstance(value, dict):
        return {
            _raw_runtime_dict_key(key): _raw_runtime_payload(item)
            for key, item in value.items()
        }
    return value


def normalize_runtime_validation_payload(value: Any) -> Any:
    return _raw_runtime_payload(value)


RuntimePayloadModelT = TypeVar("RuntimePayloadModelT", bound=BaseModel)


def validate_runtime_payload(
    payload: Any,
    *,
    model: type[RuntimePayloadModelT],
    code: str,
    prefix: str,
) -> RuntimePayloadModelT:
    try:
        return model.model_validate(normalize_runtime_validation_payload(payload))
    except ValidationError as exc:
        _raise_runtime_payload_build_error(code, prefix, exc)


def validate_runtime_manifest_payload(payload: Any) -> RuntimeManifestResponse:
    return validate_runtime_payload(
        payload,
        model=RuntimeManifestResponse,
        code="invalid_runtime_manifest_payload",
        prefix="Signed runtime manifest build produced an invalid payload.",
    )


def validate_runtime_admin_modules_payload(payload: Any) -> RuntimeAdminModulesResponse:
    return validate_runtime_payload(
        payload,
        model=RuntimeAdminModulesResponse,
        code="invalid_runtime_admin_modules_payload",
        prefix="Signed runtime admin modules payload is invalid.",
    )


def validate_runtime_admin_benchmarks_payload(payload: Any) -> RuntimeAdminBenchmarksResponse:
    return validate_runtime_payload(
        payload,
        model=RuntimeAdminBenchmarksResponse,
        code="invalid_runtime_admin_benchmarks_payload",
        prefix="Signed runtime admin benchmarks payload is invalid.",
    )


def validate_runtime_release_validation_payload(
    payload: Any,
) -> RuntimeReleaseValidationResponse:
    return validate_runtime_payload(
        payload,
        model=RuntimeReleaseValidationResponse,
        code="invalid_runtime_release_validation_payload",
        prefix="Signed runtime release validation payload is invalid.",
    )


def _validated_runtime_manifest_for_surface(
    manifest: RuntimeManifestResponse,
    *,
    code: str,
    prefix: str,
) -> RuntimeManifestResponse:
    try:
        return validate_runtime_manifest_payload(_raw_runtime_payload(manifest))
    except RuntimeManifestBuildError as exc:
        raise RuntimeManifestBuildError(
            code,
            _format_runtime_payload_build_error_message(prefix, exc.details),
            dict(exc.details),
        ) from exc


def _try_runtime_deployment_mode(value: object) -> RuntimeDeploymentMode | None:
    try:
        return RuntimeDeploymentMode(_runtime_deployment_mode_value(value))
    except ValueError:
        return None


def _build_policy_snapshot() -> SnapshotReference:
    payload = default_policy_payload()
    raw = _canonical_json(payload)
    return SnapshotReference(
        snapshot_id=f"execution-policy-default-v1:{_sha256_bytes(raw)[:16]}",
        sha256=_sha256_bytes(raw),
        source="apps/api_server/services/execution_policy_service.py",
        description="Default execution policy baseline for manifest-scoped policy coverage.",
    )


def _build_schema_snapshot() -> SnapshotReference:
    payload = load_platform_contract_manifest()
    raw = _canonical_json(payload)
    return SnapshotReference(
        snapshot_id=f"platform-contract-v1:{_sha256_bytes(raw)[:16]}",
        sha256=_sha256_bytes(raw),
        source="apps/docs/integration_manifest.v1.json",
        description="Canonical public contract schema baseline referenced by the runtime manifest.",
    )


def _build_module_entries(
    proof_bundle: dict[str, Any],
    parity_artifact: dict[str, Any],
    compiled_artifact: dict[str, Any],
) -> list[RuntimeModuleManifestEntry]:
    parity_by_name: dict[str, dict[str, Any]] = {}
    reverse_name_map = {value: key for key, value in _MODULE_BENCHMARK_NAME_MAP.items()}
    for entry in parity_artifact["libraries"]:
        lib_name = str(entry["lib"])
        parity_by_name[lib_name] = entry
        mapped_name = reverse_name_map.get(lib_name)
        if mapped_name is not None:
            parity_by_name[mapped_name] = entry
    compiled_modules = compiled_artifact["modules"]
    public_channels = list(proof_bundle["public_supported_channels"])
    auxiliary_channels = list(proof_bundle["underlying_validated_lanes"])
    feature_flag_channels = ["http_api_feature_flag"]
    proof_paths = [
        "build/llm_rollout_proof_bundle.json",
        "build/llm_rollout_parity_benchmark.json",
        "build/llm_compiled_runtime_benchmark.json",
        "tests/test_llm_rollout_matrix.py",
    ]
    module_entries: list[RuntimeModuleManifestEntry] = []
    for module_name in LLM_ROLLOUT_MODULE_ORDER:
        compiled_payload = compiled_modules[module_name]
        benchmark_name = _MODULE_BENCHMARK_NAME_MAP.get(module_name, module_name)
        benchmark_path = f"benchmarks/results/{benchmark_name}.json"
        function_payloads = compiled_payload["functions"]
        cold_samples = [float(entry["cold_ms"]) for entry in function_payloads.values()]
        warm_samples = [float(entry["warm_ms"]) for entry in function_payloads.values()]
        hot_samples = [float(entry["hot_ms"]) for entry in function_payloads.values()]
        parity_payload = parity_by_name[module_name]
        rollback_slug = benchmark_name.replace(".", "_")
        module_entries.append(
            RuntimeModuleManifestEntry(
                name=RuntimeModuleId(module_name),
                capability_id=f"mojo_llm_runtime_core.{module_name}",
                owner=_KERNEL_OWNER,
                contract_boundary=(
                    "Deterministic Mojo kernel with a manifest-listed function surface only; "
                    "public access remains mediated by the signed runtime manifest and parity-backed "
                    "SDK or API adapters."
                ),
                function_count=int(compiled_payload["function_count"]),
                functions=list(function_payloads.keys()),
                layer=RuntimeLayer.mojo_llm_runtime_core,
                maturity=RuntimeMaturity.channel_covered,
                public_supported_channels=public_channels,
                validated_auxiliary_channels=auxiliary_channels,
                feature_flag_channels=feature_flag_channels,
                proof_obligations=[
                    RuntimeProofObligation.numerical_parity,
                    RuntimeProofObligation.deterministic_kernels,
                    RuntimeProofObligation.latency_memory_bounds,
                    RuntimeProofObligation.channel_proof,
                    RuntimeProofObligation.manifest_listing,
                    RuntimeProofObligation.tenant_isolation,
                    RuntimeProofObligation.replay_safety,
                ],
                proof_artifacts=proof_paths,
                promotion_status=RuntimeKernelPromotionStatus.shipping,
                rollback_flag=f"runtime.manifest.module.{rollback_slug}.rollback_to_python",
                benchmark_report_ref=benchmark_path,
                parity_report_ref="build/llm_rollout_parity_benchmark.json",
                schema_compat_report_ref=_KERNEL_SCHEMA_COMPAT_REPORT_REF,
                isolation_proof_ref=_KERNEL_ISOLATION_PROOF_REF,
                replay_proof_ref=_KERNEL_REPLAY_PROOF_REF,
                benchmark_artifact=benchmark_path,
                benchmark_speedup_x=float(parity_payload["speedup_x"]),
                compiled_artifact="build/llm_compiled_runtime_benchmark.json",
                compiled_engine="mojo",
                max_cold_ms=max(cold_samples),
                max_warm_ms=max(warm_samples),
                max_hot_ms=max(hot_samples),
            )
        )
    return module_entries


def _build_compiled_artifacts() -> list[ArtifactReference]:
    artifacts = [
        _build_artifact_reference(_PROOF_BUNDLE_PATH, kind=RuntimeArtifactKind.proof_bundle),
        _build_artifact_reference(
            _PARITY_ARTIFACT_PATH,
            kind=RuntimeArtifactKind.parity_benchmark,
        ),
        _build_artifact_reference(
            _COMPILED_ARTIFACT_PATH,
            kind=RuntimeArtifactKind.compiled_runtime_benchmark,
        ),
    ]
    if _MOJO_BINARY_PATH.exists():
        artifacts.append(
            _build_artifact_reference(
                _MOJO_BINARY_PATH,
                kind=RuntimeArtifactKind.compiled_mojo_binary,
            )
        )
    return artifacts


def _build_kernel_promotion_criteria() -> KernelPromotionCriteria:
    return KernelPromotionCriteria(
        required_manifest_fields=[
            "capability_id",
            "owner",
            "contract_boundary",
            "promotion_status",
            "rollback_flag",
        ],
        required_proof_reference_fields=[
            "benchmark_report_ref",
            "parity_report_ref",
            "schema_compat_report_ref",
            "isolation_proof_ref",
            "replay_proof_ref",
        ],
        deterministic_test_corpus_rule=(
            "Shipping kernels must pass a fixed-seed deterministic corpus with stable outputs "
            "across repeated runs."
        ),
        python_parity_rule=(
            "Shipping kernels must publish Python or reference parity evidence on the same corpus "
            "with exact-match outputs or declared tolerances."
        ),
        schema_compatibility_rule=(
            "Shipping kernels must prove Arrow and Parquet schema compatibility for declared "
            "input, output, checkpoint, and telemetry artifacts."
        ),
        minimum_primary_metric_improvement_pct=15.0,
        maximum_adjacent_metric_regression_pct=5.0,
        benchmark_exception_rule=(
            "A shipping exception is allowed only when the kernel unblocks a declared hard budget "
            "and the exception is documented in the benchmark report."
        ),
        rollback_scope_rule=(
            "Every shipping kernel must expose an independently switchable rollback flag at "
            "tenant, org, or deployment scope."
        ),
        tenant_isolation_rule=(
            "Shipping kernels must prove tenant-scoped ownership for caches, checkpoints, "
            "artifacts, and buffers before reuse."
        ),
        replay_compatibility_rule=(
            "Shipping kernels must reproduce the same result for the same request hash, manifest "
            "version, policy snapshot, schema snapshot, seed, and artifact refs or emit "
            "replay_mismatch."
        ),
    )


def _build_system_invariants() -> list[NamedRule]:
    return [
        NamedRule(
            name=RuntimeInvariantName.manifest_truth,
            statement="No capability may be advertised unless it is present in the signed runtime manifest.",
        ),
        NamedRule(
            name=RuntimeInvariantName.replay_determinism,
            statement=(
                "Given the same input hash, runtime manifest, policy snapshot, schema snapshot, "
                "tool manifest, backend seed, and captured external artifacts, replay must "
                "reproduce the same decision trace or emit replay_mismatch."
            ),
        ),
        NamedRule(
            name=RuntimeInvariantName.policy_monotonicity,
            statement=(
                "A lower-privilege policy may not enable an action denied by its higher-privilege baseline."
            ),
        ),
        NamedRule(
            name=RuntimeInvariantName.no_silent_fallback,
            statement=(
                "No backend, provider, or tool fallback may occur unless the active policy explicitly permits it."
            ),
        ),
        NamedRule(
            name=RuntimeInvariantName.audit_completeness,
            statement=(
                "Every externally visible output must be traceable to inputs, data, tools, backend or model, "
                "policy, schema, and runtime artifact versions."
            ),
        ),
        NamedRule(
            name=RuntimeInvariantName.tenant_non_interference,
            statement=(
                "No tenant execution path may observe, infer, or reuse another tenant's secrets, data, "
                "cache, checkpoints, or tool outputs."
            ),
        ),
    ]


def _build_execution_model() -> ExecutionModel:
    return ExecutionModel(
        state_fields=[
            RuntimeExecutionStateField.request,
            RuntimeExecutionStateField.tenant,
            RuntimeExecutionStateField.workspace,
            RuntimeExecutionStateField.policy_snapshot,
            RuntimeExecutionStateField.schema_snapshot,
            RuntimeExecutionStateField.runtime_manifest,
            RuntimeExecutionStateField.model_backend,
            RuntimeExecutionStateField.tool_manifest,
            RuntimeExecutionStateField.checkpoint_log,
            RuntimeExecutionStateField.event_log,
            RuntimeExecutionStateField.decision_state,
        ],
        allowed_transitions=[
            ExecutionTransition.model_call_started,
            ExecutionTransition.model_token_emitted,
            ExecutionTransition.tool_call_requested,
            ExecutionTransition.tool_call_approved,
            ExecutionTransition.tool_call_denied,
            ExecutionTransition.checkpoint_committed,
            ExecutionTransition.decision_plan_created,
            ExecutionTransition.simulation_started,
            ExecutionTransition.execution_started,
            ExecutionTransition.replay_started,
            ExecutionTransition.failure_emitted,
        ],
        validity_rules=[
            RuntimeExecutionValidityRule.schema_valid,
            RuntimeExecutionValidityRule.policy_valid,
            RuntimeExecutionValidityRule.ordered,
            RuntimeExecutionValidityRule.replayable,
            RuntimeExecutionValidityRule.audit_visible,
        ],
    )


def _build_external_nondeterminism_policy() -> ExternalNondeterminismPolicy:
    return ExternalNondeterminismPolicy(
        sources=[
            RuntimeExternalNondeterminismSource.provider_responses,
            RuntimeExternalNondeterminismSource.mcp_tool_responses,
            RuntimeExternalNondeterminismSource.database_snapshots,
            RuntimeExternalNondeterminismSource.clock_time,
            RuntimeExternalNondeterminismSource.random_seeds,
            RuntimeExternalNondeterminismSource.external_api_outputs,
        ],
        rule=(
            "Every nondeterministic dependency must be captured as a replay artifact reference "
            "in the lineage graph, or replay must emit replay_mismatch or external_dependency_unavailable."
        ),
        required_artifacts=[
            RuntimeNondeterminismArtifact.provider_response_record,
            RuntimeNondeterminismArtifact.tool_or_mcp_response_record,
            RuntimeNondeterminismArtifact.data_snapshot_reference_or_query_result_hash,
            RuntimeNondeterminismArtifact.clock_snapshot,
            RuntimeNondeterminismArtifact.seed_record,
            RuntimeNondeterminismArtifact.backend_or_version_identifier,
        ],
        failure_codes=[
            RuntimeFailureCode.replay_mismatch,
            RuntimeFailureCode.external_dependency_unavailable,
        ],
    )


def _build_artifact_lineage_schema() -> ArtifactLineageSchema:
    return ArtifactLineageSchema(
        artifact_flow=[
            RuntimeArtifactLineageStep.input,
            RuntimeArtifactLineageStep.policy_snapshot,
            RuntimeArtifactLineageStep.schema_snapshot,
            RuntimeArtifactLineageStep.runtime_manifest,
            RuntimeArtifactLineageStep.backend_or_model,
            RuntimeArtifactLineageStep.tool_or_mcp_calls,
            RuntimeArtifactLineageStep.checkpoints,
            RuntimeArtifactLineageStep.decision_plan,
            RuntimeArtifactLineageStep.execution_record,
            RuntimeArtifactLineageStep.outcome,
            RuntimeArtifactLineageStep.evaluation_result,
        ],
        required_node_fields=[
            RuntimeLineageNodeField.node_id,
            RuntimeLineageNodeField.artifact_type,
            RuntimeLineageNodeField.content_hash,
            RuntimeLineageNodeField.parent_hashes,
            RuntimeLineageNodeField.tenant_scope,
            RuntimeLineageNodeField.workspace_scope,
            RuntimeLineageNodeField.timestamp,
            RuntimeLineageNodeField.manifest_version,
            RuntimeLineageNodeField.policy_snapshot_id,
            RuntimeLineageNodeField.schema_snapshot_id,
        ],
        immutability_rule="Lineage nodes are immutable and linked by content hashes in a DAG.",
    )


def _build_capability_algebra() -> CapabilityAlgebraSchema:
    return CapabilityAlgebraSchema(
        required_fields=[
            RuntimeCapabilityField.tool_name,
            RuntimeCapabilityField.input_schema,
            RuntimeCapabilityField.output_schema,
            RuntimeCapabilityField.side_effect_class,
            RuntimeCapabilityField.risk_level,
            RuntimeCapabilityField.required_policy,
            RuntimeCapabilityField.replayability,
            RuntimeCapabilityField.approval_required,
        ],
        enums=CapabilityEnums(
            side_effect_class=list(SideEffectClass),
            risk_level=list(RiskLevel),
            replayability=list(Replayability),
        ),
        rules=[
            RuntimeCapabilityRule.mcp_tools_are_untrusted_by_default,
            RuntimeCapabilityRule.no_tool_may_execute_without_a_capability_record,
            RuntimeCapabilityRule.approvals_and_fallbacks_derive_from_capability_algebra_not_ad_hoc_code_paths,
        ],
    )


def _build_proof_matrix() -> list[LayerProofMatrixEntry]:
    return [
        LayerProofMatrixEntry(
            layer=RuntimeLayer.mojo_llm_runtime_core,
            status=RuntimeMaturity.channel_covered,
            obligations=[
                RuntimeProofObligation.numerical_parity,
                RuntimeProofObligation.deterministic_kernels,
                RuntimeProofObligation.latency_memory_bounds,
                RuntimeProofObligation.channel_proof,
                RuntimeProofObligation.manifest_listing,
            ],
            evidence_paths=[
                "build/llm_rollout_proof_bundle.json",
                "build/llm_rollout_parity_benchmark.json",
                "build/llm_compiled_runtime_benchmark.json",
                "tests/test_llm_rollout_matrix.py",
            ],
        ),
        LayerProofMatrixEntry(
            layer=RuntimeLayer.python_compatibility_ring,
            status=RuntimeMaturity.experimental,
            obligations=[
                RuntimeProofObligation.api_equivalence,
                RuntimeProofObligation.behavioral_equivalence_against_python_reference,
            ],
            evidence_paths=[],
        ),
        LayerProofMatrixEntry(
            layer=RuntimeLayer.llm_api_provider_layer,
            status=RuntimeMaturity.experimental,
            obligations=[
                RuntimeProofObligation.openai_compatible_schema_parity,
                RuntimeProofObligation.streaming_semantics_parity,
                RuntimeProofObligation.typed_failure_parity,
            ],
            evidence_paths=[],
        ),
        LayerProofMatrixEntry(
            layer=RuntimeLayer.agent_runtime,
            status=RuntimeMaturity.experimental,
            obligations=[
                RuntimeProofObligation.event_ordering,
                RuntimeProofObligation.checkpoint_correctness,
                RuntimeProofObligation.cancellation_safety,
                RuntimeProofObligation.replay_safety,
            ],
            evidence_paths=[],
        ),
        LayerProofMatrixEntry(
            layer=RuntimeLayer.decision_runtime,
            status=RuntimeMaturity.experimental,
            obligations=[
                RuntimeProofObligation.evidence_completeness,
                RuntimeProofObligation.simulation_traceability,
                RuntimeProofObligation.approval_correctness,
            ],
            evidence_paths=[],
        ),
        LayerProofMatrixEntry(
            layer=RuntimeLayer.enterprise_control_plane,
            status=RuntimeMaturity.experimental,
            obligations=[
                RuntimeProofObligation.tenant_isolation,
                RuntimeProofObligation.policy_enforcement,
                RuntimeProofObligation.metering_correctness,
            ],
            evidence_paths=[],
        ),
    ]


def _build_benchmark_framework() -> BenchmarkFramework:
    return BenchmarkFramework(
        classes=[
            BenchmarkClassEntry(
                code=RuntimeBenchmarkClassCode.microkernel_latency,
                description="microkernel latency",
                evidence_paths=[
                    "benchmarks/summary.json",
                    "tests/benchmark_mojo_vs_python.py",
                ],
            ),
            BenchmarkClassEntry(
                code=RuntimeBenchmarkClassCode.end_to_end_llm_serving_latency,
                description="end-to-end LLM serving latency",
            ),
            BenchmarkClassEntry(
                code=RuntimeBenchmarkClassCode.streaming_ttft,
                description="streaming TTFT",
            ),
            BenchmarkClassEntry(
                code=RuntimeBenchmarkClassCode.throughput_under_concurrency,
                description="throughput under concurrency",
            ),
            BenchmarkClassEntry(
                code=RuntimeBenchmarkClassCode.memory_pressure_fragmentation,
                description="memory pressure and fragmentation",
            ),
            BenchmarkClassEntry(
                code=RuntimeBenchmarkClassCode.checkpoint_replay_overhead,
                description="checkpoint and replay overhead",
            ),
            BenchmarkClassEntry(
                code=RuntimeBenchmarkClassCode.mcp_tool_latency,
                description="MCP tool latency",
            ),
            BenchmarkClassEntry(
                code=RuntimeBenchmarkClassCode.provider_routing_overhead,
                description="provider routing overhead",
                evidence_paths=[
                    "build/provider_routing_overhead_benchmark.json",
                    "benchmarks/provider_routing_overhead_benchmark.py",
                    "tests/test_provider_routing_overhead_benchmark.py",
                ],
            ),
            BenchmarkClassEntry(
                code=RuntimeBenchmarkClassCode.rag_retrieval_quality_latency,
                description="RAG retrieval quality and latency",
            ),
            BenchmarkClassEntry(
                code=RuntimeBenchmarkClassCode.decision_workflow_completion_latency,
                description="decision workflow completion latency",
                evidence_paths=[
                    "build/repository_intelligence_benchmark.json",
                    "benchmarks/repository_intelligence_benchmark.py",
                    "tests/test_repository_intelligence_benchmark.py",
                ],
            ),
        ],
        required_metrics=[
            RuntimeBenchmarkMetric.p50,
            RuntimeBenchmarkMetric.p90,
            RuntimeBenchmarkMetric.p95,
            RuntimeBenchmarkMetric.p99,
            RuntimeBenchmarkMetric.tokens_per_second,
            RuntimeBenchmarkMetric.ttft,
            RuntimeBenchmarkMetric.requests_per_second,
            RuntimeBenchmarkMetric.memory_peak,
            RuntimeBenchmarkMetric.cache_hit_rate,
            RuntimeBenchmarkMetric.checkpoint_commit_latency,
            RuntimeBenchmarkMetric.replay_latency,
            RuntimeBenchmarkMetric.tool_call_latency,
            RuntimeBenchmarkMetric.decision_plan_latency,
            RuntimeBenchmarkMetric.simulation_latency,
            RuntimeBenchmarkMetric.cost_per_successful_run,
        ],
        baselines=[
            RuntimeBenchmarkBaseline.python_reference,
            RuntimeBenchmarkBaseline.pytorch_or_transformers_path,
            RuntimeBenchmarkBaseline.vllm_openai_compatible_backend,
            RuntimeBenchmarkBaseline.llama_cpp_gguf_backend,
            RuntimeBenchmarkBaseline.onnx_runtime_backend,
            RuntimeBenchmarkBaseline.ctranslate2_backend,
            RuntimeBenchmarkBaseline.algenta_mojo_native_path,
        ],
    )


def _build_slo_budgets() -> list[SLOBudget]:
    return [
        SLOBudget(
            name=RuntimeSLOBudgetName.runtime_manifest_load,
            applies_to=RuntimeSLOBudgetAppliesTo.first_party_runtime_manifest_route,
            p95_objective_ms=25.0,
            hard_ceiling_ms=100.0,
        ),
        SLOBudget(
            name=RuntimeSLOBudgetName.ttft,
            applies_to=RuntimeSLOBudgetAppliesTo.first_party_native_llm_serving_path,
            p95_objective_ms=800.0,
            hard_ceiling_ms=1500.0,
        ),
        SLOBudget(
            name=RuntimeSLOBudgetName.end_to_end_turn,
            applies_to=RuntimeSLOBudgetAppliesTo.first_party_native_llm_serving_path,
            p95_objective_ms=4000.0,
            hard_ceiling_ms=8000.0,
        ),
        SLOBudget(
            name=RuntimeSLOBudgetName.agent_checkpoint_commit,
            applies_to=RuntimeSLOBudgetAppliesTo.agent_runtime_checkpoint_persistence,
            p95_objective_ms=50.0,
            hard_ceiling_ms=150.0,
        ),
        SLOBudget(
            name=RuntimeSLOBudgetName.mcp_call_first_party,
            applies_to=RuntimeSLOBudgetAppliesTo.first_party_or_internal_mcp_tools,
            p95_objective_ms=500.0,
            hard_ceiling_ms=1000.0,
        ),
        SLOBudget(
            name=RuntimeSLOBudgetName.decision_plan_creation,
            applies_to=RuntimeSLOBudgetAppliesTo.decision_runtime_plan_generation,
            p95_objective_ms=2000.0,
            hard_ceiling_ms=5000.0,
        ),
        SLOBudget(
            name=RuntimeSLOBudgetName.replay,
            applies_to=RuntimeSLOBudgetAppliesTo.runs_up_to_1000_events,
            p95_objective_ms=750.0,
            hard_ceiling_ms=2000.0,
        ),
    ]


def _build_scheduler_model() -> SchedulerModel:
    return SchedulerModel(
        policies=[
            RuntimeSchedulerPolicy.fifo,
            RuntimeSchedulerPolicy.priority_queue,
            RuntimeSchedulerPolicy.deadline_aware,
            RuntimeSchedulerPolicy.cost_aware,
            RuntimeSchedulerPolicy.tenant_fair,
            RuntimeSchedulerPolicy.kv_cache_aware,
            RuntimeSchedulerPolicy.batching_aware,
            RuntimeSchedulerPolicy.speculative_decoding_aware,
            RuntimeSchedulerPolicy.policy_constrained,
        ],
        minimize=[
            RuntimeSchedulerMinimizeObjective.tail_latency,
            RuntimeSchedulerMinimizeObjective.memory_waste,
            RuntimeSchedulerMinimizeObjective.context_switch_overhead,
            RuntimeSchedulerMinimizeObjective.provider_cost,
            RuntimeSchedulerMinimizeObjective.starvation,
        ],
        maximize=[
            RuntimeSchedulerMaximizeObjective.gpu_or_cpu_utilization,
            RuntimeSchedulerMaximizeObjective.kv_cache_reuse,
            RuntimeSchedulerMaximizeObjective.batching_efficiency,
            RuntimeSchedulerMaximizeObjective.token_throughput,
            RuntimeSchedulerMaximizeObjective.fairness,
        ],
        invariants=[
            RuntimeSchedulerInvariant.no_request_starves_indefinitely,
            RuntimeSchedulerInvariant.high_priority_requests_cannot_violate_tenant_quota,
            RuntimeSchedulerInvariant.batching_may_not_cross_isolation_boundaries_when_policy_forbids_it,
            RuntimeSchedulerInvariant.speculative_decoding_may_not_emit_unverified_tokens,
        ],
    )


def _build_memory_model() -> MemoryModel:
    return MemoryModel(
        regions=[
            RuntimeMemoryRegion.model_weights,
            RuntimeMemoryRegion.kv_cache_pages,
            RuntimeMemoryRegion.prompt_token_buffer,
            RuntimeMemoryRegion.generation_buffer,
            RuntimeMemoryRegion.retrieval_context_buffer,
            RuntimeMemoryRegion.checkpoint_state,
            RuntimeMemoryRegion.tool_call_state,
            RuntimeMemoryRegion.tenant_local_cache,
        ],
        rules=[
            RuntimeMemoryRule.kv_pages_are_tenant_scoped,
            RuntimeMemoryRule.evicted_cache_pages_must_be_zeroed_or_isolation_proven_before_reuse,
            RuntimeMemoryRule.checkpoint_state_must_reference_immutable_artifact_hashes,
            RuntimeMemoryRule.model_weights_must_be_version_pinned,
            RuntimeMemoryRule.memory_pressure_must_emit_typed_failure_and_never_degrade_silently,
        ],
        failure_codes=[
            RuntimeFailureCode.kv_cache_exhausted,
            RuntimeFailureCode.artifact_load_failed,
            RuntimeFailureCode.memory_pressure_limit,
            RuntimeFailureCode.tenant_cache_violation,
            RuntimeFailureCode.checkpoint_state_overflow,
        ],
    )


def _build_evaluation_science() -> EvaluationScience:
    return EvaluationScience(
        dimensions=[
            RuntimeEvaluationDimension.answer_correctness,
            RuntimeEvaluationDimension.tool_call_correctness,
            RuntimeEvaluationDimension.schema_correctness,
            RuntimeEvaluationDimension.retrieval_precision_and_recall,
            RuntimeEvaluationDimension.hallucination_rate,
            RuntimeEvaluationDimension.policy_violation_rate,
            RuntimeEvaluationDimension.replay_success_rate,
            RuntimeEvaluationDimension.decision_outcome_delta,
            RuntimeEvaluationDimension.cost_quality_frontier,
            RuntimeEvaluationDimension.latency_quality_frontier,
        ],
        methods=[
            RuntimeEvaluationMethod.bootstrap_confidence_intervals,
            RuntimeEvaluationMethod.paired_model_comparisons,
            RuntimeEvaluationMethod.regression_tests,
            RuntimeEvaluationMethod.drift_detection,
            RuntimeEvaluationMethod.ab_experiments,
            RuntimeEvaluationMethod.counterfactual_replay,
            RuntimeEvaluationMethod.monte_carlo_simulation,
            RuntimeEvaluationMethod.sensitivity_analysis,
        ],
        release_blockers=[
            RuntimeReleaseBlocker.replay_success_regression,
            RuntimeReleaseBlocker.policy_violation_increase,
            RuntimeReleaseBlocker.p95_budget_violation,
            RuntimeReleaseBlocker.rag_precision_drop,
            RuntimeReleaseBlocker.tool_call_error_rate_increase,
            RuntimeReleaseBlocker.decision_plan_validity_drop,
        ],
    )


def _build_typed_failures() -> list[TypedFailure]:
    return [
        TypedFailure(
            code=RuntimeFailureCode.provider_timeout,
            description="Provider timed out before returning a result.",
        ),
        TypedFailure(
            code=RuntimeFailureCode.runtime_compile_error,
            description="Runtime compilation failed before execution.",
        ),
        TypedFailure(
            code=RuntimeFailureCode.mcp_tool_denied,
            description="MCP tool execution was denied by policy or approval rules.",
        ),
        TypedFailure(
            code=RuntimeFailureCode.policy_denied,
            description="Execution was denied by the active policy snapshot.",
        ),
        TypedFailure(
            code=RuntimeFailureCode.schema_access_denied,
            description="Schema or data access was denied by governance rules.",
        ),
        TypedFailure(
            code=RuntimeFailureCode.checkpoint_failed,
            description="Checkpoint persistence or recovery failed.",
        ),
        TypedFailure(
            code=RuntimeFailureCode.replay_mismatch,
            description="Replay diverged from the captured decision trace.",
        ),
        TypedFailure(
            code=RuntimeFailureCode.external_dependency_unavailable,
            description="Replay could not load a required external dependency artifact.",
        ),
        TypedFailure(
            code=RuntimeFailureCode.backend_unavailable,
            description="The selected execution backend was unavailable.",
        ),
        TypedFailure(
            code=RuntimeFailureCode.quota_exceeded,
            description="Execution exceeded configured quota or credit limits.",
        ),
        TypedFailure(
            code=RuntimeFailureCode.approval_required,
            description="Execution requires explicit approval before continuing.",
        ),
    ]


def _build_threat_model() -> ThreatModel:
    return ThreatModel(
        threat_classes=[
            RuntimeThreatClass.prompt_injection,
            RuntimeThreatClass.tool_injection,
            RuntimeThreatClass.mcp_abuse,
            RuntimeThreatClass.data_exfiltration,
            RuntimeThreatClass.cross_tenant_leakage,
            RuntimeThreatClass.provider_fallback_leakage,
            RuntimeThreatClass.secret_exposure,
            RuntimeThreatClass.replay_tampering,
            RuntimeThreatClass.audit_log_mutation,
            RuntimeThreatClass.model_artifact_poisoning,
            RuntimeThreatClass.dependency_supply_chain_attack,
            RuntimeThreatClass.billing_abuse,
            RuntimeThreatClass.quota_bypass,
        ],
        controls=[
            RuntimeThreatControl.tool_allowlists,
            RuntimeThreatControl.argument_validation,
            RuntimeThreatControl.result_sanitization,
            RuntimeThreatControl.egress_policy,
            RuntimeThreatControl.signed_manifests,
            RuntimeThreatControl.signed_artifacts,
            RuntimeThreatControl.immutable_audit_logs,
            RuntimeThreatControl.policy_snapshots,
            RuntimeThreatControl.secret_scoping,
            RuntimeThreatControl.tenant_scoped_cache,
            RuntimeThreatControl.sbom,
            RuntimeThreatControl.dependency_pinning,
            RuntimeThreatControl.runtime_attestation,
        ],
        non_negotiable_rules=[RuntimeThreatRule.mcp_tools_are_untrusted_by_default],
    )


def _build_formal_release_theorem() -> FormalReleaseTheorem:
    return FormalReleaseTheorem(
        statement=(
            "A release is valid iff every advertised capability is manifest-listed, proof-backed, "
            "policy-covered, replay-tested, and deployment-mode validated."
        ),
        required_conditions=[
            ReleaseCondition.manifest_listed,
            ReleaseCondition.proof_backed,
            ReleaseCondition.policy_covered,
            ReleaseCondition.replay_tested,
            ReleaseCondition.deployment_mode_validated,
        ],
    )


def _build_release_artifact_bundle() -> ReleaseArtifactBundle:
    return ReleaseArtifactBundle(
        required_artifacts=[
            RuntimeReleaseArtifact.signed_runtime_manifest,
            RuntimeReleaseArtifact.module_maturity_table,
            RuntimeReleaseArtifact.benchmark_report,
            RuntimeReleaseArtifact.parity_report,
            RuntimeReleaseArtifact.replay_report,
            RuntimeReleaseArtifact.security_report,
            RuntimeReleaseArtifact.compatibility_report,
            RuntimeReleaseArtifact.migration_notes,
            RuntimeReleaseArtifact.known_limitations,
        ]
    )


def _build_release_gates() -> list[ReleaseGate]:
    return [
        ReleaseGate(
            gate=RuntimeReleaseGateId.gate_a,
            description="all public APIs contract-tested",
        ),
        ReleaseGate(
            gate=RuntimeReleaseGateId.gate_b,
            description="all enterprise_ready capabilities have proof artifacts",
        ),
        ReleaseGate(gate=RuntimeReleaseGateId.gate_c, description="replay corpus passes"),
        ReleaseGate(gate=RuntimeReleaseGateId.gate_d, description="policy corpus passes"),
        ReleaseGate(
            gate=RuntimeReleaseGateId.gate_e,
            description="benchmark regressions are within threshold",
        ),
        ReleaseGate(gate=RuntimeReleaseGateId.gate_f, description="threat model updated"),
        ReleaseGate(
            gate=RuntimeReleaseGateId.gate_g,
            description="deployment modes validated",
        ),
    ]


def _build_immediate_pr_sequence() -> list[ImmediateImplementationPR]:
    return [
        ImmediateImplementationPR(
            pr="PR 0",
            focus="Runtime truth manifest",
            deliverables=[
                "public runtime manifest route",
                "signed manifest artifact",
                "current 22-module and 209-function inventory",
                "channel inventory",
                "lineage node schema",
            ],
        ),
        ImmediateImplementationPR(
            pr="PR 1",
            focus="Maturity model and proof matrix",
            deliverables=[
                "maturity enum",
                "per-layer proof obligation mapping",
                "CI gates for promotion",
                "release theorem enforcement",
            ],
        ),
        ImmediateImplementationPR(pr="PR 2", focus="Python compatibility foundation"),
        ImmediateImplementationPR(pr="PR 3", focus="OpenAI-compatible schemas and streaming"),
        ImmediateImplementationPR(pr="PR 4", focus="MCP core stabilization"),
        ImmediateImplementationPR(pr="PR 5", focus="Provider clients and LiteLLM-style routing"),
        ImmediateImplementationPR(pr="PR 6", focus="Tokenizer and artifact bridge"),
        ImmediateImplementationPR(pr="PR 7", focus="Rust agent runtime"),
        ImmediateImplementationPR(pr="PR 8", focus="Decision runtime convergence"),
        ImmediateImplementationPR(pr="PR 9", focus="Evaluation and RAG quality gates"),
        ImmediateImplementationPR(pr="PR 10", focus="Enterprise control plane"),
        ImmediateImplementationPR(pr="PR 11", focus="Billing and quotas"),
        ImmediateImplementationPR(pr="PR 12", focus="Deployment modes"),
    ]


def _build_benchmark_discovery_lane(module_count: int, function_count: int) -> BenchmarkDiscoveryLane:
    inventory_report = build_inventory_report()
    discovered_source_inventory = [
        BenchmarkDiscoverySourceModuleEntry(
            import_path=module.import_path,
            public_function_count=len(module.public_functions),
        )
        for module in sorted(inventory_report.source_modules, key=lambda entry: entry.import_path)
        if module.public_functions
    ]
    return BenchmarkDiscoveryLane(
        discovered_source_modules=inventory_report.source_modules_with_public_functions_count,
        discovered_public_functions=inventory_report.source_public_function_count,
        discovered_source_inventory=discovered_source_inventory,
        shipping_manifest_modules=module_count,
        shipping_manifest_functions=function_count,
        non_shipping_rule=RuntimeNonShippingRule.broader_mojo_inventory_not_advertised,
    )


def _build_signature(payload: dict[str, Any]) -> tuple[str, ManifestSignature]:
    canonical = _canonical_json(payload)
    digest_hex = _sha256_bytes(canonical)
    signature_hex = hmac.new(
        _manifest_signing_secret().encode("utf-8"),
        canonical,
        hashlib.sha256,
    ).hexdigest()
    return digest_hex, ManifestSignature(
        algorithm=RuntimeSignatureAlgorithm.hmac_sha256,
        key_id=_CONTROL_PLANE_SIGNATURE_KEY_ID,
        digest_hex=digest_hex,
        signature_hex=signature_hex,
        scope=RuntimeSignatureScope.control_plane_hmac_v1,
    )


@lru_cache(maxsize=8)
def load_runtime_manifest(
    api_env: str,
    runtime_library_http_api_enabled: bool,
    deployment_mode: str,
) -> RuntimeManifestResponse:
    del api_env
    del runtime_library_http_api_enabled

    proof_bundle = _read_json(_PROOF_BUNDLE_PATH)
    parity_artifact = _read_json(_PARITY_ARTIFACT_PATH)
    compiled_artifact = _read_json(_COMPILED_ARTIFACT_PATH)

    modules = _build_module_entries(proof_bundle, parity_artifact, compiled_artifact)
    maturity = {module.name: module.maturity for module in modules}
    public_supported_channels = list(proof_bundle["public_supported_channels"])
    validated_auxiliary_channels = list(proof_bundle["underlying_validated_lanes"])
    feature_flag_channels = ["http_api_feature_flag"]
    module_count = len(modules)
    function_count = sum(module.function_count for module in modules)

    payload: dict[str, Any] = {
        "runtime_version": _RUNTIME_VERSION,
        "mojo_version": _detect_mojo_version(),
        "llm_core_manifest": _LLM_CORE_MANIFEST,
        "module_manifest_version": _MODULE_MANIFEST_VERSION,
        "generated_at": proof_bundle["generated_at"],
        "modules": _raw_runtime_payload(modules),
        "compiled_artifacts": _raw_runtime_payload(_build_compiled_artifacts()),
        "supported_channels": public_supported_channels,
        "validated_auxiliary_channels": validated_auxiliary_channels,
        "feature_flag_channels": feature_flag_channels,
        "maturity": _raw_runtime_payload(maturity),
        "policy_snapshot": _raw_runtime_payload(_build_policy_snapshot()),
        "schema_snapshot": _raw_runtime_payload(_build_schema_snapshot()),
        "deployment_mode": deployment_mode,
        "deployment_modes": {
            "current": deployment_mode,
            "supported_modes": [
                "saas",
                "vpc",
                "self_hosted",
                "air_gapped",
                "hybrid_provider",
                "local_dev_daemon",
            ],
            "rule": (
                "Current deployment mode is environment-derived or explicitly supplied "
                "through ALGENTA_DEPLOYMENT_MODE."
            ),
        },
        "shipping_contract": {
            "module_count": module_count,
            "function_count": function_count,
            "runtime_core_layer": RuntimeLayer.mojo_llm_runtime_core.value,
            "benchmark_discovery_rule": RuntimeBenchmarkDiscoveryRule.shipping_llm_rollout_only.value,
        },
        "benchmark_discovery_lane": _raw_runtime_payload(
            _build_benchmark_discovery_lane(
                module_count,
                function_count,
            )
        ),
        "advertised_capabilities": {
            "runtime_modules": _enum_values([module.name for module in modules]),
            "public_endpoints": list(_PUBLIC_ENDPOINTS),
            "admin_endpoints": list(_ADMIN_ENDPOINTS),
            "feature_flag_endpoints": list(_FEATURE_FLAG_ENDPOINTS),
        },
        "system_invariants": _raw_runtime_payload(_build_system_invariants()),
        "execution_model": _raw_runtime_payload(_build_execution_model()),
        "external_nondeterminism": _raw_runtime_payload(
            _build_external_nondeterminism_policy()
        ),
        "artifact_lineage": _raw_runtime_payload(_build_artifact_lineage_schema()),
        "capability_algebra": _raw_runtime_payload(_build_capability_algebra()),
        "kernel_promotion_criteria": _raw_runtime_payload(_build_kernel_promotion_criteria()),
        "proof_matrix": _raw_runtime_payload(_build_proof_matrix()),
        "benchmarking": _raw_runtime_payload(_build_benchmark_framework()),
        "slo_budgets": _raw_runtime_payload(_build_slo_budgets()),
        "scheduler_model": _raw_runtime_payload(_build_scheduler_model()),
        "memory_model": _raw_runtime_payload(_build_memory_model()),
        "evaluation_science": _raw_runtime_payload(_build_evaluation_science()),
        "typed_failures": _raw_runtime_payload(_build_typed_failures()),
        "threat_model": _raw_runtime_payload(_build_threat_model()),
        "formal_release_theorem": _raw_runtime_payload(_build_formal_release_theorem()),
        "release_artifact_bundle": _raw_runtime_payload(_build_release_artifact_bundle()),
        "release_gates": _raw_runtime_payload(_build_release_gates()),
        "immediate_implementation_sequence": _raw_runtime_payload(
            _build_immediate_pr_sequence()
        ),
    }
    digest_hex, signature = _build_signature(payload)
    payload["manifest_digest"] = digest_hex
    payload["signature"] = _raw_runtime_payload(signature)
    return validate_runtime_manifest_payload(payload)


def get_runtime_manifest() -> RuntimeManifestResponse:
    settings = get_settings()
    return load_runtime_manifest(
        settings.api_env,
        settings.runtime_library_http_api_enabled,
        _deployment_mode(),
    )


def _count_values(values: list[Any]) -> dict[Any, int]:
    counts: dict[Any, int] = {}
    for value in values:
        key = value if isinstance(value, Enum) else str(value)
        counts[key] = counts.get(key, 0) + 1
    return counts


def get_runtime_admin_modules() -> RuntimeAdminModulesResponse:
    manifest = _validated_runtime_manifest_for_surface(
        get_runtime_manifest(),
        code="invalid_runtime_admin_modules_payload",
        prefix="Signed runtime admin modules payload is invalid.",
    )
    payload = {
        "runtime_version": manifest.runtime_version,
        "llm_core_manifest": manifest.llm_core_manifest,
        "module_manifest_version": manifest.module_manifest_version,
        "shipping_contract": _raw_runtime_payload(manifest.shipping_contract),
        "summary": _raw_runtime_payload(
            RuntimeAdminModuleSummary(
                module_count=len(manifest.modules),
                function_count=sum(module.function_count for module in manifest.modules),
                maturity_counts=_count_values([module.maturity for module in manifest.modules]),
                layer_counts=_count_values([module.layer for module in manifest.modules]),
            )
        ),
        "proof_matrix": _raw_runtime_payload(manifest.proof_matrix),
        "modules": _raw_runtime_payload(manifest.modules),
        "manifest_digest": manifest.manifest_digest,
        "signature": _raw_runtime_payload(manifest.signature),
    }
    return validate_runtime_admin_modules_payload(payload)


def get_runtime_admin_benchmarks() -> RuntimeAdminBenchmarksResponse:
    manifest = get_runtime_manifest()
    quality_gate_benchmark_classes = [
        entry
        for entry in manifest.benchmarking.classes
        if entry.code
        in {
            RuntimeBenchmarkClassCode.checkpoint_replay_overhead,
            RuntimeBenchmarkClassCode.mcp_tool_latency,
            RuntimeBenchmarkClassCode.rag_retrieval_quality_latency,
            RuntimeBenchmarkClassCode.decision_workflow_completion_latency,
        }
    ]
    quality_gate_slo_budgets = [
        budget
        for budget in manifest.slo_budgets
        if budget.name
        in {
            RuntimeSLOBudgetName.mcp_call_first_party,
            RuntimeSLOBudgetName.decision_plan_creation,
            RuntimeSLOBudgetName.replay,
        }
    ]
    evaluation_dimensions = set(manifest.evaluation_science.dimensions)
    evaluation_release_blockers = set(manifest.evaluation_science.release_blockers)
    quality_gate_class_codes = {entry.code for entry in quality_gate_benchmark_classes}
    quality_gate_budget_names = {entry.name for entry in quality_gate_slo_budgets}
    payload = {
        "runtime_version": manifest.runtime_version,
        "llm_core_manifest": manifest.llm_core_manifest,
        "module_manifest_version": manifest.module_manifest_version,
        "benchmark_discovery_lane": _raw_runtime_payload(manifest.benchmark_discovery_lane),
        "benchmarking": _raw_runtime_payload(manifest.benchmarking),
        "slo_budgets": _raw_runtime_payload(manifest.slo_budgets),
        "quality_gate_benchmark_classes": _raw_runtime_payload(quality_gate_benchmark_classes),
        "quality_gate_slo_budgets": _raw_runtime_payload(quality_gate_slo_budgets),
        "evaluation_science": _raw_runtime_payload(manifest.evaluation_science),
        "evaluation_summary": _raw_runtime_payload(
            RuntimeAdminEvaluationSummary(
                dimension_count=len(manifest.evaluation_science.dimensions),
                method_count=len(manifest.evaluation_science.methods),
                release_blocker_count=len(manifest.evaluation_science.release_blockers),
                benchmark_class_count=len(quality_gate_benchmark_classes),
                slo_budget_count=len(quality_gate_slo_budgets),
                replay_gate_enabled=(
                    RuntimeBenchmarkClassCode.checkpoint_replay_overhead
                    in quality_gate_class_codes
                    and RuntimeSLOBudgetName.replay in quality_gate_budget_names
                    and RuntimeEvaluationDimension.replay_success_rate in evaluation_dimensions
                    and RuntimeReleaseBlocker.replay_success_regression
                    in evaluation_release_blockers
                ),
                tool_call_quality_gate_enabled=(
                    RuntimeBenchmarkClassCode.mcp_tool_latency in quality_gate_class_codes
                    and RuntimeSLOBudgetName.mcp_call_first_party in quality_gate_budget_names
                    and RuntimeEvaluationDimension.tool_call_correctness
                    in evaluation_dimensions
                    and RuntimeReleaseBlocker.tool_call_error_rate_increase
                    in evaluation_release_blockers
                ),
                rag_quality_gate_enabled=(
                    RuntimeBenchmarkClassCode.rag_retrieval_quality_latency
                    in quality_gate_class_codes
                    and RuntimeEvaluationDimension.retrieval_precision_and_recall
                    in evaluation_dimensions
                    and RuntimeReleaseBlocker.rag_precision_drop
                    in evaluation_release_blockers
                ),
                decision_quality_gate_enabled=(
                    RuntimeBenchmarkClassCode.decision_workflow_completion_latency
                    in quality_gate_class_codes
                    and RuntimeSLOBudgetName.decision_plan_creation in quality_gate_budget_names
                    and RuntimeEvaluationDimension.decision_outcome_delta
                    in evaluation_dimensions
                    and RuntimeReleaseBlocker.decision_plan_validity_drop
                    in evaluation_release_blockers
                ),
            )
        ),
        "compiled_artifacts": _raw_runtime_payload(manifest.compiled_artifacts),
        "shipping_runtime_modules": [module.name for module in manifest.modules],
        "shipping_runtime_function_counts": [module.function_count for module in manifest.modules],
        "shipping_runtime_benchmark_speedups_x": [
            module.benchmark_speedup_x for module in manifest.modules
        ],
        "shipping_runtime_benchmark_artifacts": [
            module.benchmark_artifact for module in manifest.modules
        ],
        "shipping_runtime_compiled_artifacts": [
            module.compiled_artifact for module in manifest.modules
        ],
        "shipping_runtime_compiled_engines": [
            module.compiled_engine for module in manifest.modules
        ],
        "shipping_runtime_max_cold_ms": [module.max_cold_ms for module in manifest.modules],
        "shipping_runtime_max_warm_ms": [module.max_warm_ms for module in manifest.modules],
        "shipping_runtime_max_hot_ms": [module.max_hot_ms for module in manifest.modules],
        "module_benchmarks": [
            {
                "name": module.name,
                "function_count": module.function_count,
                "benchmark_artifact": module.benchmark_artifact,
                "benchmark_speedup_x": module.benchmark_speedup_x,
                "compiled_artifact": module.compiled_artifact,
                "compiled_engine": module.compiled_engine,
                "max_cold_ms": module.max_cold_ms,
                "max_warm_ms": module.max_warm_ms,
                "max_hot_ms": module.max_hot_ms,
            }
            for module in manifest.modules
        ],
        "manifest_digest": manifest.manifest_digest,
        "signature": _raw_runtime_payload(manifest.signature),
    }
    return validate_runtime_admin_benchmarks_payload(payload)


def build_runtime_release_validation(
    manifest: RuntimeManifestResponse | None = None,
) -> RuntimeReleaseValidationResponse:
    effective_manifest = manifest or get_runtime_manifest()
    deployment_mode = _try_runtime_deployment_mode(effective_manifest.deployment_mode)
    deployment_mode_raw = _runtime_deployment_mode_value(effective_manifest.deployment_mode)
    module_names = _enum_values([module.name for module in effective_manifest.modules])
    invariant_names = {entry.name for entry in effective_manifest.system_invariants}
    typed_failure_codes = {entry.code for entry in effective_manifest.typed_failures}
    proof_matrix = {entry.layer: entry for entry in effective_manifest.proof_matrix}
    conditions = [
        ReleaseConditionEvaluation(
            condition=ReleaseCondition.manifest_listed,
            satisfied=(
                module_names
                == _enum_values(effective_manifest.advertised_capabilities.runtime_modules)
                and _enum_values(effective_manifest.advertised_capabilities.public_endpoints)
                == list(_PUBLIC_ENDPOINTS)
                and _enum_values(effective_manifest.advertised_capabilities.admin_endpoints)
                == list(_ADMIN_ENDPOINTS)
                and _enum_values(effective_manifest.advertised_capabilities.feature_flag_endpoints)
                == list(_FEATURE_FLAG_ENDPOINTS)
            ),
            detail=(
                "Advertised runtime modules and public, admin, and feature-flag endpoint "
                "boundaries must be declared by the signed runtime manifest."
            ),
            evidence_paths=[
                "/v1/runtime/manifest",
                *[artifact.path for artifact in effective_manifest.compiled_artifacts],
            ],
        ),
        ReleaseConditionEvaluation(
            condition=ReleaseCondition.proof_backed,
            satisfied=(
                all(
                    module.proof_artifacts
                    and module.benchmark_artifact
                    and module.compiled_artifact
                    for module in effective_manifest.modules
                )
                and bool(effective_manifest.compiled_artifacts)
                and RuntimeLayer.mojo_llm_runtime_core in proof_matrix
                and bool(proof_matrix[RuntimeLayer.mojo_llm_runtime_core].evidence_paths)
            ),
            detail=(
                "Every advertised runtime module must carry proof artifacts, benchmark linkage, "
                "compiled artifact linkage, and proof-matrix evidence."
            ),
            evidence_paths=[
                "build/llm_rollout_proof_bundle.json",
                "build/llm_rollout_parity_benchmark.json",
                "build/llm_compiled_runtime_benchmark.json",
                "tests/test_llm_rollout_matrix.py",
            ],
        ),
        ReleaseConditionEvaluation(
            condition=ReleaseCondition.policy_covered,
            satisfied=(
                bool(effective_manifest.policy_snapshot.snapshot_id)
                and RuntimeInvariantName.policy_monotonicity in invariant_names
                and "required_policy" in effective_manifest.capability_algebra.required_fields
                and RuntimeFailureCode.policy_denied in typed_failure_codes
            ),
            detail=(
                "Policy coverage requires a policy snapshot, explicit monotonicity invariant, "
                "capability-level policy binding, and typed denial failures."
            ),
            evidence_paths=[
                effective_manifest.policy_snapshot.source,
                "/v1/runtime/manifest",
            ],
        ),
        ReleaseConditionEvaluation(
            condition=ReleaseCondition.replay_tested,
            satisfied=(
                bool(effective_manifest.artifact_lineage.artifact_flow)
                and RuntimeInvariantName.replay_determinism in invariant_names
                and RuntimeFailureCode.replay_mismatch in typed_failure_codes
                and RuntimeFailureCode.external_dependency_unavailable in typed_failure_codes
                and RuntimeFailureCode.replay_mismatch
                in effective_manifest.external_nondeterminism.failure_codes
                and RuntimeFailureCode.external_dependency_unavailable
                in effective_manifest.external_nondeterminism.failure_codes
            ),
            detail=(
                "Replay coverage requires deterministic lineage, explicit nondeterminism capture, "
                "and typed mismatch or unavailable-dependency failures."
            ),
            evidence_paths=[
                "/v1/runtime/manifest",
                effective_manifest.schema_snapshot.source,
            ],
        ),
        ReleaseConditionEvaluation(
            condition=ReleaseCondition.deployment_mode_validated,
            satisfied=(
                deployment_mode is not None
                and deployment_mode in effective_manifest.deployment_modes.supported_modes
            ),
            detail=(
                "The active deployment mode must be listed in the manifest-supported deployment "
                "modes before release claims are considered valid."
            ),
            evidence_paths=["/v1/runtime/manifest"],
        ),
    ]
    payload = {
        "runtime_version": effective_manifest.runtime_version,
        "llm_core_manifest": effective_manifest.llm_core_manifest,
        "module_manifest_version": effective_manifest.module_manifest_version,
        "theorem_statement": effective_manifest.formal_release_theorem.statement,
        "valid_release": all(condition.satisfied for condition in conditions),
        "conditions": _raw_runtime_payload(conditions),
        "deployment_mode": deployment_mode.value if deployment_mode is not None else None,
        "deployment_mode_raw": deployment_mode_raw,
        "manifest_digest": effective_manifest.manifest_digest,
        "signature": _raw_runtime_payload(effective_manifest.signature),
    }
    return validate_runtime_release_validation_payload(payload)


def get_runtime_release_validation() -> RuntimeReleaseValidationResponse:
    return build_runtime_release_validation()
