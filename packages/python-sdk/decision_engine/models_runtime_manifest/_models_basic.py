# SPDX-License-Identifier: Apache-2.0

"""RuntimeManifestResultBaseModel + module entries + deployment + benchmark discovery.

Extracted from packages/python-sdk/decision_engine/models_runtime_manifest.py during modularization.
"""
from __future__ import annotations

from typing import Any, get_origin

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from decision_engine.models_runtime_manifest._enums import (
    RuntimeAdminEndpointResult,
    RuntimeArtifactKindResult,
    RuntimeArtifactLineageStepResult,
    RuntimeAuxiliaryChannelResult,
    RuntimeBenchmarkBaselineResult,
    RuntimeBenchmarkClassCodeResult,
    RuntimeBenchmarkDiscoveryRuleResult,
    RuntimeBenchmarkMetricResult,
    RuntimeCapabilityFieldResult,
    RuntimeCapabilityRuleResult,
    RuntimeCompiledEngineResult,
    RuntimeDeploymentModeResult,
    RuntimeEvaluationDimensionResult,
    RuntimeEvaluationMethodResult,
    RuntimeExecutionStateFieldResult,
    RuntimeExecutionTransitionResult,
    RuntimeExecutionValidityRuleResult,
    RuntimeExternalNondeterminismSourceResult,
    RuntimeFailureCodeResult,
    RuntimeFeatureFlagChannelResult,
    RuntimeFeatureFlagEndpointResult,
    RuntimeInvariantNameResult,
    RuntimeKernelPromotionStatusResult,
    RuntimeLayerResult,
    RuntimeLineageNodeFieldResult,
    RuntimeMaturityResult,
    RuntimeMemoryRegionResult,
    RuntimeMemoryRuleResult,
    RuntimeModuleIdResult,
    RuntimeNondeterminismArtifactResult,
    RuntimeNonShippingRuleResult,
    RuntimeProofObligationResult,
    RuntimePublicEndpointResult,
    RuntimeReleaseArtifactResult,
    RuntimeReleaseBlockerResult,
    RuntimeReleaseConditionResult,
    RuntimeReplayabilityResult,
    RuntimeRiskLevelResult,
    RuntimeSchedulerInvariantResult,
    RuntimeSchedulerMaximizeObjectiveResult,
    RuntimeSchedulerMinimizeObjectiveResult,
    RuntimeSchedulerPolicyResult,
    RuntimeSideEffectClassResult,
    RuntimeSignatureAlgorithmResult,
    RuntimeSignatureScopeResult,
    RuntimeSLOBudgetAppliesToResult,
    RuntimeSLOBudgetNameResult,
    RuntimeSupportedChannelResult,
    RuntimeThreatClassResult,
    RuntimeThreatControlResult,
    RuntimeThreatRuleResult,
    _ensure_unique_runtime_values,
)

__all__ = [
    "RuntimeManifestResultBaseModel",
    "RuntimeArtifactReferenceResult",
    "RuntimeManifestSignatureResult",
    "RuntimeSnapshotReferenceResult",
    "RuntimeKernelPromotionCriteriaResult",
    "RuntimeModuleManifestEntryResult",
    "RuntimeDeploymentModesResult",
    "RuntimeShippingContractSummaryResult",
    "RuntimeBenchmarkDiscoverySourceModuleEntryResult",
    "RuntimeBenchmarkDiscoveryLaneResult",
    "RuntimeAdvertisedCapabilitiesResult",
    "RuntimeNamedRuleResult",
    "RuntimeExecutionModelResult",
    "RuntimeExternalNondeterminismPolicyResult",
    "RuntimeArtifactLineageSchemaResult",
    "RuntimeCapabilityEnumsResult",
    "RuntimeCapabilityAlgebraSchemaResult",
    "RuntimeLayerProofMatrixEntryResult",
    "RuntimeBenchmarkClassEntryResult",
    "RuntimeBenchmarkFrameworkResult",
    "RuntimeSLOBudgetResult",
    "RuntimeSchedulerModelResult",
    "RuntimeMemoryModelResult",
    "RuntimeEvaluationScienceResult",
    "RuntimeThreatModelResult",
    "RuntimeTypedFailureResult",
    "RuntimeFormalReleaseTheoremResult",
    "RuntimeReleaseArtifactBundleResult",
]


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
                    f"benchmark_discovery_lane.discovered_source_inventory.{index}."
                    "public_function_count must be greater than 0."
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
                "benchmark_discovery_lane.discovered_source_inventory must be sorted by "
                "import_path."
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


