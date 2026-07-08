"""Execution model + capabilities + invariants + lineage + capability algebra.

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


@dataclass(frozen=True)
class RuntimeAdvertisedCapabilities:
    runtime_modules: list[RuntimeModuleId] = field(default_factory=list)
    public_endpoints: list[RuntimePublicEndpoint] = field(default_factory=list)
    admin_endpoints: list[RuntimeAdminEndpoint] = field(default_factory=list)
    feature_flag_endpoints: list[RuntimeFeatureFlagEndpoint] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeAdvertisedCapabilities:
        data = coerce_payload_mapping(payload)
        return cls(
            runtime_modules=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("runtime_modules"),
                    RuntimeModuleId,
                    "advertised_capabilities.runtime_modules",
                ),
                "advertised_capabilities.runtime_modules",
            ),
            public_endpoints=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("public_endpoints"),
                    RuntimePublicEndpoint,
                    "advertised_capabilities.public_endpoints",
                ),
                "advertised_capabilities.public_endpoints",
            ),
            admin_endpoints=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("admin_endpoints"),
                    RuntimeAdminEndpoint,
                    "advertised_capabilities.admin_endpoints",
                ),
                "advertised_capabilities.admin_endpoints",
            ),
            feature_flag_endpoints=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("feature_flag_endpoints"),
                    RuntimeFeatureFlagEndpoint,
                    "advertised_capabilities.feature_flag_endpoints",
                ),
                "advertised_capabilities.feature_flag_endpoints",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeNamedRule:
    name: RuntimeInvariantName
    statement: str

    @classmethod
    def from_api(cls, payload: Any, context: str = "system_invariants") -> RuntimeNamedRule:
        data = coerce_payload_mapping(payload)
        return cls(
            name=_coerce_enum(data["name"], RuntimeInvariantName, f"{context}.name"),
            statement=_require_manifest_string(data, "statement", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeExecutionModel:
    state_fields: list[RuntimeExecutionStateField] = field(default_factory=list)
    allowed_transitions: list[RuntimeExecutionTransition] = field(default_factory=list)
    validity_rules: list[RuntimeExecutionValidityRule] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeExecutionModel:
        data = coerce_payload_mapping(payload)
        return cls(
            state_fields=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("state_fields"),
                    RuntimeExecutionStateField,
                    "execution_model.state_fields",
                ),
                "execution_model.state_fields",
            ),
            allowed_transitions=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("allowed_transitions"),
                    RuntimeExecutionTransition,
                    "execution_model.allowed_transitions",
                ),
                "execution_model.allowed_transitions",
            ),
            validity_rules=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("validity_rules"),
                    RuntimeExecutionValidityRule,
                    "execution_model.validity_rules",
                ),
                "execution_model.validity_rules",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeExternalNondeterminismPolicy:
    sources: list[RuntimeExternalNondeterminismSource] = field(default_factory=list)
    rule: str = ""
    required_artifacts: list[RuntimeNondeterminismArtifact] = field(default_factory=list)
    failure_codes: list[RuntimeFailureCode] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeExternalNondeterminismPolicy:
        data = coerce_payload_mapping(payload)
        return cls(
            sources=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("sources"),
                    RuntimeExternalNondeterminismSource,
                    "external_nondeterminism.sources",
                ),
                "external_nondeterminism.sources",
            ),
            rule=_require_manifest_string(data, "rule", "external_nondeterminism"),
            required_artifacts=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("required_artifacts"),
                    RuntimeNondeterminismArtifact,
                    "external_nondeterminism.required_artifacts",
                ),
                "external_nondeterminism.required_artifacts",
            ),
            failure_codes=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("failure_codes"),
                    RuntimeFailureCode,
                    "external_nondeterminism.failure_codes",
                ),
                "external_nondeterminism.failure_codes",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeArtifactLineageSchema:
    artifact_flow: list[RuntimeArtifactLineageStep] = field(default_factory=list)
    required_node_fields: list[RuntimeLineageNodeField] = field(default_factory=list)
    immutability_rule: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeArtifactLineageSchema:
        data = coerce_payload_mapping(payload)
        return cls(
            artifact_flow=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("artifact_flow"),
                    RuntimeArtifactLineageStep,
                    "artifact_lineage.artifact_flow",
                ),
                "artifact_lineage.artifact_flow",
            ),
            required_node_fields=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("required_node_fields"),
                    RuntimeLineageNodeField,
                    "artifact_lineage.required_node_fields",
                ),
                "artifact_lineage.required_node_fields",
            ),
            immutability_rule=_require_manifest_string(
                data,
                "immutability_rule",
                "artifact_lineage",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeCapabilityEnums:
    side_effect_class: list[RuntimeSideEffectClass] = field(default_factory=list)
    risk_level: list[RuntimeRiskLevel] = field(default_factory=list)
    replayability: list[RuntimeReplayability] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeCapabilityEnums:
        data = coerce_payload_mapping(payload)
        return cls(
            side_effect_class=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("side_effect_class"),
                    RuntimeSideEffectClass,
                    "capability_algebra.enums.side_effect_class",
                ),
                "capability_algebra.enums.side_effect_class",
            ),
            risk_level=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("risk_level"),
                    RuntimeRiskLevel,
                    "capability_algebra.enums.risk_level",
                ),
                "capability_algebra.enums.risk_level",
            ),
            replayability=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("replayability"),
                    RuntimeReplayability,
                    "capability_algebra.enums.replayability",
                ),
                "capability_algebra.enums.replayability",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeCapabilityAlgebraSchema:
    required_fields: list[RuntimeCapabilityField] = field(default_factory=list)
    enums: RuntimeCapabilityEnums = field(default_factory=RuntimeCapabilityEnums)
    rules: list[RuntimeCapabilityRule] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeCapabilityAlgebraSchema:
        data = coerce_payload_mapping(payload)
        return cls(
            required_fields=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("required_fields"),
                    RuntimeCapabilityField,
                    "capability_algebra.required_fields",
                ),
                "capability_algebra.required_fields",
            ),
            enums=RuntimeCapabilityEnums.from_api(data.get("enums") or {}),
            rules=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("rules"),
                    RuntimeCapabilityRule,
                    "capability_algebra.rules",
                ),
                "capability_algebra.rules",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


