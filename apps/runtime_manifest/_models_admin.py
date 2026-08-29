"""Admin response models: AdminModules, BenchmarkModuleEntry, AdminBenchmarks, ReleaseValidation.

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
from apps.runtime_manifest._errors import (
    RuntimeManifestBuildError,
    _manifest_error_details,
    _raise_manifest_integrity_error,
    _raise_on_duplicate_values,
)
from apps.runtime_manifest._models_basic import *  # noqa: F401, F403

# Pure helper used by validators below. Duplicated here (instead of
# imported from _public_api) because _public_api depends transitively
# on this module. The 6-line helper has no side effects.
def _count_values(values: list[Any]) -> dict[Any, int]:
    counts: dict[Any, int] = {}
    for value in values:
        key = value if isinstance(value, Enum) else str(value)
        counts[key] = counts.get(key, 0) + 1
    return counts


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
    deployment_mode: RuntimeDeploymentModePublic | None = None
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


