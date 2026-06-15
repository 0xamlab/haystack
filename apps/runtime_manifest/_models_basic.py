"""Small Pydantic models: ArtifactReference, ManifestSignature, ShippingContractSummary, ...

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


