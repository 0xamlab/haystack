"""Proof matrix + benchmark framework + SLOs + scheduler + memory + evaluation + threat model.

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


@dataclass(frozen=True)
class RuntimeLayerProofMatrixEntry:
    layer: RuntimeLayer
    status: RuntimeMaturity
    obligations: list[RuntimeProofObligation] = field(default_factory=list)
    evidence_paths: list[str] = field(default_factory=list)

    @classmethod
    def from_api(
        cls,
        payload: Any,
        context: str = "proof_matrix",
    ) -> RuntimeLayerProofMatrixEntry:
        data = coerce_payload_mapping(payload)
        return cls(
            layer=_coerce_enum(data["layer"], RuntimeLayer, f"{context}.layer"),
            status=_coerce_enum(data["status"], RuntimeMaturity, f"{context}.status"),
            obligations=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("obligations"),
                    RuntimeProofObligation,
                    f"{context}.obligations",
                ),
                f"{context}.obligations",
            ),
            evidence_paths=_ensure_unique_manifest_values(
                _optional_manifest_string_list(data, "evidence_paths", context),
                f"{context}.evidence_paths",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeBenchmarkClassEntry:
    code: RuntimeBenchmarkClassCode
    description: str
    evidence_paths: list[str] = field(default_factory=list)

    @classmethod
    def from_api(
        cls,
        payload: Any,
        context: str = "benchmarking.classes",
    ) -> RuntimeBenchmarkClassEntry:
        data = coerce_payload_mapping(payload)
        return cls(
            code=_coerce_enum(data["code"], RuntimeBenchmarkClassCode, f"{context}.code"),
            description=_require_manifest_string(data, "description", context),
            evidence_paths=_ensure_unique_manifest_values(
                _optional_manifest_string_list(data, "evidence_paths", context),
                f"{context}.evidence_paths",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeBenchmarkFramework:
    classes: list[RuntimeBenchmarkClassEntry] = field(default_factory=list)
    required_metrics: list[RuntimeBenchmarkMetric] = field(default_factory=list)
    baselines: list[RuntimeBenchmarkBaseline] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeBenchmarkFramework:
        data = coerce_payload_mapping(payload)
        classes = [
            RuntimeBenchmarkClassEntry.from_api(item, f"benchmarking.classes.{index}")
            for index, item in enumerate(data.get("classes") or [])
        ]
        _ensure_unique_manifest_values(
            classes,
            "benchmarking.classes",
            value_selector=lambda entry: entry.code,
        )
        return cls(
            classes=classes,
            required_metrics=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("required_metrics"),
                    RuntimeBenchmarkMetric,
                    "benchmarking.required_metrics",
                ),
                "benchmarking.required_metrics",
            ),
            baselines=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("baselines"),
                    RuntimeBenchmarkBaseline,
                    "benchmarking.baselines",
                ),
                "benchmarking.baselines",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeSLOBudget:
    name: RuntimeSLOBudgetName
    applies_to: RuntimeSLOBudgetAppliesTo
    p95_objective_ms: float
    hard_ceiling_ms: float | None = None
    notes: str | None = None

    @classmethod
    def from_api(cls, payload: Any, context: str = "slo_budgets") -> RuntimeSLOBudget:
        data = coerce_payload_mapping(payload)
        return cls(
            name=_coerce_enum(data["name"], RuntimeSLOBudgetName, f"{context}.name"),
            applies_to=_coerce_enum(
                _require_manifest_string(data, "applies_to", context),
                RuntimeSLOBudgetAppliesTo,
                f"{context}.applies_to",
            ),
            p95_objective_ms=_require_manifest_float(data, "p95_objective_ms", context),
            hard_ceiling_ms=_optional_manifest_float(data, "hard_ceiling_ms", context),
            notes=_optional_manifest_string(data, "notes", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeSchedulerModel:
    policies: list[RuntimeSchedulerPolicy] = field(default_factory=list)
    minimize: list[RuntimeSchedulerMinimizeObjective] = field(default_factory=list)
    maximize: list[RuntimeSchedulerMaximizeObjective] = field(default_factory=list)
    invariants: list[RuntimeSchedulerInvariant] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeSchedulerModel:
        data = coerce_payload_mapping(payload)
        return cls(
            policies=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("policies"),
                    RuntimeSchedulerPolicy,
                    "scheduler_model.policies",
                ),
                "scheduler_model.policies",
            ),
            minimize=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("minimize"),
                    RuntimeSchedulerMinimizeObjective,
                    "scheduler_model.minimize",
                ),
                "scheduler_model.minimize",
            ),
            maximize=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("maximize"),
                    RuntimeSchedulerMaximizeObjective,
                    "scheduler_model.maximize",
                ),
                "scheduler_model.maximize",
            ),
            invariants=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("invariants"),
                    RuntimeSchedulerInvariant,
                    "scheduler_model.invariants",
                ),
                "scheduler_model.invariants",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeMemoryModel:
    regions: list[RuntimeMemoryRegion] = field(default_factory=list)
    rules: list[RuntimeMemoryRule] = field(default_factory=list)
    failure_codes: list[RuntimeFailureCode] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeMemoryModel:
        data = coerce_payload_mapping(payload)
        return cls(
            regions=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("regions"),
                    RuntimeMemoryRegion,
                    "memory_model.regions",
                ),
                "memory_model.regions",
            ),
            rules=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("rules"),
                    RuntimeMemoryRule,
                    "memory_model.rules",
                ),
                "memory_model.rules",
            ),
            failure_codes=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("failure_codes"),
                    RuntimeFailureCode,
                    "memory_model.failure_codes",
                ),
                "memory_model.failure_codes",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeEvaluationScience:
    dimensions: list[RuntimeEvaluationDimension] = field(default_factory=list)
    methods: list[RuntimeEvaluationMethod] = field(default_factory=list)
    release_blockers: list[RuntimeReleaseBlocker] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeEvaluationScience:
        data = coerce_payload_mapping(payload)
        return cls(
            dimensions=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("dimensions"),
                    RuntimeEvaluationDimension,
                    "evaluation_science.dimensions",
                ),
                "evaluation_science.dimensions",
            ),
            methods=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("methods"),
                    RuntimeEvaluationMethod,
                    "evaluation_science.methods",
                ),
                "evaluation_science.methods",
            ),
            release_blockers=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("release_blockers"),
                    RuntimeReleaseBlocker,
                    "evaluation_science.release_blockers",
                ),
                "evaluation_science.release_blockers",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeThreatModel:
    threat_classes: list[RuntimeThreatClass] = field(default_factory=list)
    controls: list[RuntimeThreatControl] = field(default_factory=list)
    non_negotiable_rules: list[RuntimeThreatRule] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeThreatModel:
        data = coerce_payload_mapping(payload)
        return cls(
            threat_classes=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("threat_classes"),
                    RuntimeThreatClass,
                    "threat_model.threat_classes",
                ),
                "threat_model.threat_classes",
            ),
            controls=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("controls"),
                    RuntimeThreatControl,
                    "threat_model.controls",
                ),
                "threat_model.controls",
            ),
            non_negotiable_rules=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("non_negotiable_rules"),
                    RuntimeThreatRule,
                    "threat_model.non_negotiable_rules",
                ),
                "threat_model.non_negotiable_rules",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


