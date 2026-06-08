"""Release condition evaluation + RuntimeManifestResult top-level container.

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


from decision_engine.models_runtime_manifest._enums import *  # noqa: F401, F403
from decision_engine.models_runtime_manifest._enums import (
    _normalized_runtime_value,
    _ensure_unique_runtime_values,
    _count_runtime_values,
)
from decision_engine.models_runtime_manifest._models_basic import *  # noqa: F401, F403
from decision_engine.models_runtime_manifest._models_admin import *  # noqa: F401, F403


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
