# SPDX-License-Identifier: Apache-2.0

"""Release gate + admin modules/evaluations + admin benchmarks.

Extracted from packages/python-sdk/decision_engine/models_runtime_manifest.py during modularization.
"""
from __future__ import annotations

from pydantic import (
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from decision_engine.models_runtime_manifest._enums import (
    RuntimeBenchmarkClassCodeResult,
    RuntimeCompiledEngineResult,
    RuntimeEvaluationDimensionResult,
    RuntimeLayerResult,
    RuntimeMaturityResult,
    RuntimeModuleIdResult,
    RuntimeReleaseBlockerResult,
    RuntimeReleaseGateIdResult,
    RuntimeSLOBudgetNameResult,
    _count_runtime_values,
    _ensure_unique_runtime_values,
)
from decision_engine.models_runtime_manifest._models_basic import (
    RuntimeArtifactReferenceResult,
    RuntimeBenchmarkClassEntryResult,
    RuntimeBenchmarkDiscoveryLaneResult,
    RuntimeBenchmarkFrameworkResult,
    RuntimeEvaluationScienceResult,
    RuntimeLayerProofMatrixEntryResult,
    RuntimeManifestResultBaseModel,
    RuntimeManifestSignatureResult,
    RuntimeModuleManifestEntryResult,
    RuntimeShippingContractSummaryResult,
    RuntimeSLOBudgetResult,
)

__all__ = [
    "RuntimeReleaseGateResult",
    "RuntimeImmediateImplementationPRResult",
    "RuntimeAdminModuleSummaryResult",
    "RuntimeAdminEvaluationSummaryResult",
    "RuntimeAdminModulesResult",
    "RuntimeBenchmarkModuleEntryResult",
    "RuntimeAdminBenchmarksResult",
]


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
            RuntimeBenchmarkClassCodeResult.rag_retrieval_quality_latency
            in quality_gate_class_codes
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
                "evaluation_summary.release_blocker_count must equal the number of release "
                "blockers."
            )
        if self.evaluation_summary.benchmark_class_count != len(
            self.quality_gate_benchmark_classes
        ):
            raise ValueError(
                "evaluation_summary.benchmark_class_count must equal the number of quality gate "
                "benchmark classes."
            )
        if self.evaluation_summary.slo_budget_count != len(self.quality_gate_slo_budgets):
            raise ValueError(
                "evaluation_summary.slo_budget_count must equal the number of quality gate SLO "
                "budgets."
            )
        if self.evaluation_summary.replay_gate_enabled != expected_replay_gate:
            raise ValueError(
                "evaluation_summary.replay_gate_enabled must match the replay benchmark, budget, "
                "and release blocker coverage."
            )
        if (
            self.evaluation_summary.tool_call_quality_gate_enabled
            != expected_tool_call_quality_gate
        ):
            raise ValueError(
                "evaluation_summary.tool_call_quality_gate_enabled must match the tool-call "
                "benchmark, budget, and release blocker coverage."
            )
        if self.evaluation_summary.rag_quality_gate_enabled != expected_rag_quality_gate:
            raise ValueError(
                "evaluation_summary.rag_quality_gate_enabled must match the RAG benchmark and "
                "release blocker coverage."
            )
        if (
            self.evaluation_summary.decision_quality_gate_enabled
            != expected_decision_quality_gate
        ):
            raise ValueError(
                "evaluation_summary.decision_quality_gate_enabled must match the decision "
                "benchmark, budget, and release blocker coverage."
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


