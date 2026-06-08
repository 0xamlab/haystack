"""ReleaseConditionEvaluation + RuntimeReleaseValidationOutput + RuntimeManifestOutput.

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
from algenta._runtime_manifest_admin_outputs import *  # noqa: F401, F403


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
