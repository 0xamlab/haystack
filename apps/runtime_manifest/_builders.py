"""All _build_* functions: module entries, artifacts, kernel promotion, invariants, execution model, ...

Extracted from apps/runtime_manifest.py during modularization.
"""
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

from apps.runtime_manifest._constants import *  # noqa: F401, F403
from apps.runtime_manifest._constants import (
    _ADMIN_ENDPOINTS,
    _COMPILED_ARTIFACT_PATH,
    _CONTROL_PLANE_SIGNATURE_KEY_ID,
    _FEATURE_FLAG_ENDPOINTS,
    _KERNEL_ISOLATION_PROOF_REF,
    _KERNEL_OWNER,
    _KERNEL_REPLAY_PROOF_REF,
    _KERNEL_SCHEMA_COMPAT_REPORT_REF,
    _LLM_CORE_MANIFEST,
    _MODULE_BENCHMARK_NAME_MAP,
    _MODULE_MANIFEST_VERSION,
    _MOJO_BINARY_PATH,
    _PARITY_ARTIFACT_PATH,
    _PROOF_BUNDLE_PATH,
    _PUBLIC_ENDPOINTS,
    _ROOT,
    _RUNTIME_VERSION,
)
from apps.runtime_manifest._base import *  # noqa: F401, F403
from apps.runtime_manifest._enums import *  # noqa: F401, F403
from apps.runtime_manifest._models_basic import *  # noqa: F401, F403
from apps.runtime_manifest._models_admin import *  # noqa: F401, F403
from apps.runtime_manifest._errors import (
    RuntimeManifestBuildError,
    _manifest_error_details,
    _raise_manifest_integrity_error,
    _raise_on_duplicate_values,
)
from apps.runtime_manifest._models_manifest import *  # noqa: F401, F403
from apps.runtime_manifest._internal_helpers import (
    _build_runtime_manifest_error_details,
    _build_artifact_reference,
    _canonical_json,
    _detect_mojo_version,
    _deployment_mode,
    _enum_values,
    _format_runtime_manifest_build_error_message,
    _format_runtime_manifest_validation_path,
    _format_runtime_payload_build_error_message,
    _manifest_signing_secret,
    _raise_runtime_payload_build_error,
    _raw_runtime_dict_key,
    _raw_runtime_payload,
    _read_json,
    _runtime_deployment_mode_value,
    _sha256_bytes,
    _sha256_file,
    _try_runtime_deployment_mode,
    _validated_runtime_manifest_for_surface,
    normalize_runtime_validation_payload,
    validate_runtime_admin_benchmarks_payload,
    validate_runtime_admin_modules_payload,
    validate_runtime_manifest_payload,
    validate_runtime_payload,
    validate_runtime_release_validation_payload,
)



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


def _build_benchmark_discovery_lane(
    module_count: int,
    function_count: int,
    proof_bundle: dict[str, Any] | None = None,
) -> BenchmarkDiscoveryLane:
    # Prefer the lane committed in the proof bundle so CI doesn't need to
    # re-scan mojo/engine on disk (which may diverge from what the bundle
    # was generated against). Fall back to a live disk scan only if the
    # bundle pre-dates the lane field.
    if proof_bundle is not None:
        committed_lane = proof_bundle.get("benchmark_discovery_lane")
        if committed_lane:
            return BenchmarkDiscoveryLane.model_validate(committed_lane)

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


