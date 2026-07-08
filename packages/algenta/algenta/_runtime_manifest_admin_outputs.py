"""RuntimeAdminModulesOutput + RuntimeBenchmarkModuleEntry + RuntimeAdminBenchmarksOutput.

Auto-extracted from runtime_model_manifest.py.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel

from algenta.runtime_model_common import jsonable

from algenta._runtime_manifest_enums import *  # noqa: F401, F403
from algenta._runtime_manifest_coercion import *  # noqa: F401, F403
from algenta._runtime_manifest_coercion import (
    _coerce_enum,
    _coerce_enum_list,
    _coerce_enum_mapping,
    _coerce_optional_enum,
    _count_manifest_values,
    _ensure_unique_manifest_values,
    _normalize_manifest_payload_value,
    _normalized_manifest_runtime_value,
    _optional_manifest_float,
    _optional_manifest_string,
    _optional_manifest_string_list,
    _require_manifest_boolean,
    _require_manifest_boolean_value,
    _require_manifest_field,
    _require_manifest_float,
    _require_manifest_float_value,
    _require_manifest_integer,
    _require_manifest_integer_value,
    _require_manifest_string,
    _require_manifest_string_value,
)
from algenta._runtime_manifest_references import *  # noqa: F401, F403
from algenta._runtime_manifest_modules import *  # noqa: F401, F403
from algenta._runtime_manifest_topology import *  # noqa: F401, F403
from algenta._runtime_manifest_operations import *  # noqa: F401, F403
from algenta._runtime_manifest_release import *  # noqa: F401, F403


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


