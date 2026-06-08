"""Reference dataclasses: artifacts, signatures, snapshots, promotion criteria.

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


@dataclass(frozen=True)
class RuntimeArtifactReference:
    kind: RuntimeArtifactKind
    path: str
    sha256: str
    size_bytes: int

    @classmethod
    def from_api(cls, payload: Any, context: str = "compiled_artifacts") -> RuntimeArtifactReference:
        data = coerce_payload_mapping(payload)
        return cls(
            kind=_coerce_enum(data["kind"], RuntimeArtifactKind, f"{context}.kind"),
            path=_require_manifest_string(data, "path", context),
            sha256=_require_manifest_string(data, "sha256", context),
            size_bytes=_require_manifest_integer(data, "size_bytes", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeManifestSignature:
    algorithm: RuntimeSignatureAlgorithm
    key_id: str
    digest_hex: str
    signature_hex: str
    scope: RuntimeSignatureScope

    @classmethod
    def from_api(cls, payload: Any, context: str = "signature") -> RuntimeManifestSignature:
        data = coerce_payload_mapping(payload)
        return cls(
            algorithm=_coerce_enum(
                data["algorithm"],
                RuntimeSignatureAlgorithm,
                f"{context}.algorithm",
            ),
            key_id=_require_manifest_string(data, "key_id", context),
            digest_hex=_require_manifest_string(data, "digest_hex", context),
            signature_hex=_require_manifest_string(data, "signature_hex", context),
            scope=_coerce_enum(data["scope"], RuntimeSignatureScope, f"{context}.scope"),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeSnapshotReference:
    snapshot_id: str
    sha256: str
    source: str
    description: str

    @classmethod
    def from_api(cls, payload: Any, context: str = "snapshot") -> RuntimeSnapshotReference:
        data = coerce_payload_mapping(payload)
        return cls(
            snapshot_id=_require_manifest_string(data, "snapshot_id", context),
            sha256=_require_manifest_string(data, "sha256", context),
            source=_require_manifest_string(data, "source", context),
            description=_require_manifest_string(data, "description", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeKernelPromotionCriteria:
    required_manifest_fields: list[str] = field(default_factory=list)
    required_proof_reference_fields: list[str] = field(default_factory=list)
    deterministic_test_corpus_rule: str = ""
    python_parity_rule: str = ""
    schema_compatibility_rule: str = ""
    minimum_primary_metric_improvement_pct: float = 0.0
    maximum_adjacent_metric_regression_pct: float = 0.0
    benchmark_exception_rule: str = ""
    rollback_scope_rule: str = ""
    tenant_isolation_rule: str = ""
    replay_compatibility_rule: str = ""

    @classmethod
    def from_api(
        cls,
        payload: Any,
        context: str = "kernel_promotion_criteria",
    ) -> RuntimeKernelPromotionCriteria:
        data = coerce_payload_mapping(payload)
        return cls(
            required_manifest_fields=_ensure_unique_manifest_values(
                _optional_manifest_string_list(data, "required_manifest_fields", context),
                f"{context}.required_manifest_fields",
            ),
            required_proof_reference_fields=_ensure_unique_manifest_values(
                _optional_manifest_string_list(
                    data,
                    "required_proof_reference_fields",
                    context,
                ),
                f"{context}.required_proof_reference_fields",
            ),
            deterministic_test_corpus_rule=_require_manifest_string(
                data,
                "deterministic_test_corpus_rule",
                context,
            ),
            python_parity_rule=_require_manifest_string(data, "python_parity_rule", context),
            schema_compatibility_rule=_require_manifest_string(
                data,
                "schema_compatibility_rule",
                context,
            ),
            minimum_primary_metric_improvement_pct=_require_manifest_float(
                data,
                "minimum_primary_metric_improvement_pct",
                context,
            ),
            maximum_adjacent_metric_regression_pct=_require_manifest_float(
                data,
                "maximum_adjacent_metric_regression_pct",
                context,
            ),
            benchmark_exception_rule=_require_manifest_string(
                data,
                "benchmark_exception_rule",
                context,
            ),
            rollback_scope_rule=_require_manifest_string(data, "rollback_scope_rule", context),
            tenant_isolation_rule=_require_manifest_string(
                data,
                "tenant_isolation_rule",
                context,
            ),
            replay_compatibility_rule=_require_manifest_string(
                data,
                "replay_compatibility_rule",
                context,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


