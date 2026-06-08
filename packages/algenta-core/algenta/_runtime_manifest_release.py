"""Typed failures + release theorem + gates + admin summaries.

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


@dataclass(frozen=True)
class RuntimeTypedFailure:
    code: RuntimeFailureCode
    description: str

    @classmethod
    def from_api(cls, payload: Any, context: str = "typed_failures") -> RuntimeTypedFailure:
        data = coerce_payload_mapping(payload)
        return cls(
            code=_coerce_enum(data["code"], RuntimeFailureCode, f"{context}.code"),
            description=_require_manifest_string(data, "description", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeFormalReleaseTheorem:
    statement: str
    required_conditions: list[RuntimeReleaseCondition] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeFormalReleaseTheorem:
        data = coerce_payload_mapping(payload)
        required_conditions = _ensure_unique_manifest_values(
            _coerce_enum_list(
                data.get("required_conditions"),
                RuntimeReleaseCondition,
                "formal_release_theorem.required_conditions",
            ),
            "formal_release_theorem.required_conditions",
        )
        return cls(
            statement=_require_manifest_string(data, "statement", "formal_release_theorem"),
            required_conditions=required_conditions,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeReleaseArtifactBundle:
    required_artifacts: list[RuntimeReleaseArtifact] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeReleaseArtifactBundle:
        data = coerce_payload_mapping(payload)
        return cls(
            required_artifacts=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("required_artifacts"),
                    RuntimeReleaseArtifact,
                    "release_artifact_bundle.required_artifacts",
                ),
                "release_artifact_bundle.required_artifacts",
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeReleaseGate:
    gate: RuntimeReleaseGateId
    description: str

    @classmethod
    def from_api(cls, payload: Any, context: str = "release_gates") -> RuntimeReleaseGate:
        data = coerce_payload_mapping(payload)
        return cls(
            gate=_coerce_enum(data["gate"], RuntimeReleaseGateId, f"{context}.gate"),
            description=_require_manifest_string(data, "description", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeImmediateImplementationPR:
    pr: str
    focus: str
    deliverables: list[str] = field(default_factory=list)

    @classmethod
    def from_api(
        cls,
        payload: Any,
        context: str = "immediate_implementation_sequence",
    ) -> RuntimeImmediateImplementationPR:
        data = coerce_payload_mapping(payload)
        return cls(
            pr=_require_manifest_string(data, "pr", context),
            focus=_require_manifest_string(data, "focus", context),
            deliverables=_optional_manifest_string_list(data, "deliverables", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeAdminModuleSummary:
    module_count: int
    function_count: int
    maturity_counts: dict[RuntimeMaturity, int] = field(default_factory=dict)
    layer_counts: dict[RuntimeLayer, int] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeAdminModuleSummary:
        data = coerce_payload_mapping(payload)
        return cls(
            module_count=_require_manifest_integer(data, "module_count", "summary"),
            function_count=_require_manifest_integer(data, "function_count", "summary"),
            maturity_counts=_coerce_enum_mapping(
                data.get("maturity_counts"),
                RuntimeMaturity,
                lambda raw_value, key: _require_manifest_integer_value(
                    raw_value,
                    f"summary.maturity_counts.{key.value}",
                ),
                "summary.maturity_counts",
            ),
            layer_counts=_coerce_enum_mapping(
                data.get("layer_counts"),
                RuntimeLayer,
                lambda raw_value, key: _require_manifest_integer_value(
                    raw_value,
                    f"summary.layer_counts.{key.value}",
                ),
                "summary.layer_counts",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeAdminEvaluationSummary:
    dimension_count: int
    method_count: int
    release_blocker_count: int
    benchmark_class_count: int
    slo_budget_count: int
    replay_gate_enabled: bool
    tool_call_quality_gate_enabled: bool
    rag_quality_gate_enabled: bool
    decision_quality_gate_enabled: bool

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeAdminEvaluationSummary:
        data = coerce_payload_mapping(payload)
        return cls(
            dimension_count=_require_manifest_integer(data, "dimension_count", "evaluation_summary"),
            method_count=_require_manifest_integer(data, "method_count", "evaluation_summary"),
            release_blocker_count=_require_manifest_integer(
                data,
                "release_blocker_count",
                "evaluation_summary",
            ),
            benchmark_class_count=_require_manifest_integer(
                data,
                "benchmark_class_count",
                "evaluation_summary",
            ),
            slo_budget_count=_require_manifest_integer(data, "slo_budget_count", "evaluation_summary"),
            replay_gate_enabled=_require_manifest_boolean(
                data,
                "replay_gate_enabled",
                "evaluation_summary",
            ),
            tool_call_quality_gate_enabled=_require_manifest_boolean(
                data,
                "tool_call_quality_gate_enabled",
                "evaluation_summary",
            ),
            rag_quality_gate_enabled=_require_manifest_boolean(
                data,
                "rag_quality_gate_enabled",
                "evaluation_summary",
            ),
            decision_quality_gate_enabled=_require_manifest_boolean(
                data,
                "decision_quality_gate_enabled",
                "evaluation_summary",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


