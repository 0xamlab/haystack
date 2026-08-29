"""Public API: load_runtime_manifest, get_runtime_manifest, get_runtime_admin_*, get_runtime_release_validation.

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
from apps.runtime_manifest._module_order import LLM_ROLLOUT_MODULE_ORDER

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
from apps.runtime_manifest._internal_helpers import *  # noqa: F401, F403
from apps.runtime_manifest._internal_helpers import (
    _build_artifact_reference,
    _build_runtime_manifest_error_details,
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
    _sha256_bytes,
    _sha256_file,
    _validated_runtime_manifest_for_surface,
)
from apps.runtime_manifest._builders import *  # noqa: F401, F403
from apps.runtime_manifest._builders import (
    _build_artifact_lineage_schema,
    _build_benchmark_discovery_lane,
    _build_benchmark_framework,
    _build_capability_algebra,
    _build_compiled_artifacts,
    _build_evaluation_science,
    _build_execution_model,
    _build_external_nondeterminism_policy,
    _build_formal_release_theorem,
    _build_immediate_pr_sequence,
    _build_kernel_promotion_criteria,
    _build_memory_model,
    _build_module_entries,
    _build_policy_snapshot,
    _build_proof_matrix,
    _build_release_artifact_bundle,
    _build_release_gates,
    _build_scheduler_model,
    _build_schema_snapshot,
    _build_signature,
    _build_slo_budgets,
    _build_system_invariants,
    _build_threat_model,
    _build_typed_failures,
)


def runtime_version() -> str:
    """The engine build version, for surfaces that need the version WITHOUT building the manifest.

    Building the manifest reads proof bundles off disk and hashes artifacts; a public ``/v1/version``
    that a load balancer hits on every probe must not pay that. Exposing the constant as a function is
    what lets other surfaces stop keeping their own literal copy of the version and silently drift.
    """
    return _RUNTIME_VERSION


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
        "deployment_mode": publicize_runtime_deployment_mode(deployment_mode),
        "deployment_mode_raw": deployment_mode,
        "deployment_modes": {
            "current": publicize_runtime_deployment_mode(deployment_mode),
            "supported_modes": [
                "saas",
                "vpc",
                "self_hosted",
                "air_gapped",
                "hybrid_provider",
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
                proof_bundle,
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
    deployment_mode_raw = effective_manifest.deployment_mode_raw
    try:
        deployment_mode: RuntimeDeploymentModePublic | None = publicize_runtime_deployment_mode(
            deployment_mode_raw
        )
    except ValueError:
        # An unsupported/foreign mode (e.g. injected via direct attribute assignment, which
        # Pydantic does not re-validate) — deployment_mode_validated correctly fails closed below.
        deployment_mode = None
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
