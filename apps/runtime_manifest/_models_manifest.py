"""RuntimeManifestResponse — the top-level manifest model with cross-field validators.

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

# Pure helper used by validators below. Duplicated here (instead of
# imported from _internal_helpers) because _internal_helpers depends
# on RuntimeManifestResponse defined in this module — a circular
# import. The 4-line helper has no side effects so duplication is safe.
def _enum_values(values: list[object]) -> list[str]:
    return [item.value if isinstance(item, Enum) else str(item) for item in values]


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


