"""Module manifest + deployment + shipping contract + benchmark discovery lane.

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


@dataclass(frozen=True)
class RuntimeModuleManifestEntry:
    name: RuntimeModuleId
    function_count: int
    capability_id: str = ""
    owner: str = ""
    contract_boundary: str = ""
    functions: list[str] = field(default_factory=list)
    layer: RuntimeLayer = RuntimeLayer.mojo_llm_runtime_core
    maturity: RuntimeMaturity = RuntimeMaturity.experimental
    public_supported_channels: list[RuntimeSupportedChannel] = field(default_factory=list)
    validated_auxiliary_channels: list[RuntimeAuxiliaryChannel] = field(default_factory=list)
    feature_flag_channels: list[RuntimeFeatureFlagChannel] = field(default_factory=list)
    proof_obligations: list[RuntimeProofObligation] = field(default_factory=list)
    proof_artifacts: list[str] = field(default_factory=list)
    promotion_status: RuntimeKernelPromotionStatus | None = None
    rollback_flag: str | None = None
    benchmark_report_ref: str | None = None
    parity_report_ref: str | None = None
    schema_compat_report_ref: str | None = None
    isolation_proof_ref: str | None = None
    replay_proof_ref: str | None = None
    benchmark_artifact: str = ""
    benchmark_speedup_x: float = 0.0
    compiled_artifact: str = ""
    compiled_engine: RuntimeCompiledEngine = RuntimeCompiledEngine.mojo
    max_cold_ms: float = 0.0
    max_warm_ms: float = 0.0
    max_hot_ms: float = 0.0

    @classmethod
    def from_api(cls, payload: Any, context: str = "modules") -> RuntimeModuleManifestEntry:
        data = coerce_payload_mapping(payload)
        function_count = _require_manifest_integer(data, "function_count", context)
        functions = _ensure_unique_manifest_values(
            _optional_manifest_string_list(data, "functions", context),
            f"{context}.functions",
        )
        if function_count != len(functions):
            raise ValueError(
                f"{context}.functions must contain exactly {function_count} entries to match "
                "function_count."
            )
        promotion_status = (
            _coerce_enum(
                data["promotion_status"],
                RuntimeKernelPromotionStatus,
                f"{context}.promotion_status",
            )
            if data.get("promotion_status") is not None
            else None
        )
        record = cls(
            name=_coerce_enum(data["name"], RuntimeModuleId, f"{context}.name"),
            function_count=function_count,
            capability_id=_optional_manifest_string(data, "capability_id", context),
            owner=_optional_manifest_string(data, "owner", context),
            contract_boundary=_optional_manifest_string(data, "contract_boundary", context),
            functions=functions,
            layer=_coerce_enum(data["layer"], RuntimeLayer, f"{context}.layer"),
            maturity=_coerce_enum(data["maturity"], RuntimeMaturity, f"{context}.maturity"),
            public_supported_channels=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("public_supported_channels"),
                    RuntimeSupportedChannel,
                    f"{context}.public_supported_channels",
                ),
                f"{context}.public_supported_channels",
            ),
            validated_auxiliary_channels=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("validated_auxiliary_channels"),
                    RuntimeAuxiliaryChannel,
                    f"{context}.validated_auxiliary_channels",
                ),
                f"{context}.validated_auxiliary_channels",
            ),
            feature_flag_channels=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("feature_flag_channels"),
                    RuntimeFeatureFlagChannel,
                    f"{context}.feature_flag_channels",
                ),
                f"{context}.feature_flag_channels",
            ),
            proof_obligations=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("proof_obligations"),
                    RuntimeProofObligation,
                    f"{context}.proof_obligations",
                ),
                f"{context}.proof_obligations",
            ),
            proof_artifacts=_ensure_unique_manifest_values(
                _optional_manifest_string_list(data, "proof_artifacts", context),
                f"{context}.proof_artifacts",
            ),
            promotion_status=promotion_status,
            rollback_flag=_optional_manifest_string(data, "rollback_flag", context),
            benchmark_report_ref=_optional_manifest_string(
                data,
                "benchmark_report_ref",
                context,
            ),
            parity_report_ref=_optional_manifest_string(data, "parity_report_ref", context),
            schema_compat_report_ref=_optional_manifest_string(
                data,
                "schema_compat_report_ref",
                context,
            ),
            isolation_proof_ref=_optional_manifest_string(
                data,
                "isolation_proof_ref",
                context,
            ),
            replay_proof_ref=_optional_manifest_string(data, "replay_proof_ref", context),
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
        if record.promotion_status is RuntimeKernelPromotionStatus.shipping:
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
                value = getattr(record, field_name)
                if value is None or not str(value).strip():
                    raise ValueError(
                        f"{context}.{field_name} must be provided for shipping runtime modules."
                    )
        return record

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeDeploymentModes:
    current: RuntimeDeploymentMode = RuntimeDeploymentMode.local_dev_daemon
    supported_modes: list[RuntimeDeploymentMode] = field(default_factory=list)
    rule: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> RuntimeDeploymentModes:
        data = coerce_payload_mapping(payload)
        return cls(
            current=_coerce_enum(
                data["current"],
                RuntimeDeploymentMode,
                "deployment_modes.current",
            ),
            supported_modes=_ensure_unique_manifest_values(
                _coerce_enum_list(
                    data.get("supported_modes"),
                    RuntimeDeploymentMode,
                    "deployment_modes.supported_modes",
                ),
                "deployment_modes.supported_modes",
            ),
            rule=_require_manifest_string(data, "rule", "deployment_modes"),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeShippingContractSummary:
    module_count: int
    function_count: int
    runtime_core_layer: RuntimeLayer
    benchmark_discovery_rule: RuntimeBenchmarkDiscoveryRule

    @classmethod
    def from_api(
        cls,
        payload: Any,
        context: str = "shipping_contract",
    ) -> RuntimeShippingContractSummary:
        data = coerce_payload_mapping(payload)
        return cls(
            module_count=_require_manifest_integer(data, "module_count", context),
            function_count=_require_manifest_integer(data, "function_count", context),
            runtime_core_layer=_coerce_enum(
                data["runtime_core_layer"],
                RuntimeLayer,
                f"{context}.runtime_core_layer",
            ),
            benchmark_discovery_rule=_coerce_enum(
                data["benchmark_discovery_rule"],
                RuntimeBenchmarkDiscoveryRule,
                f"{context}.benchmark_discovery_rule",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeBenchmarkDiscoverySourceModuleEntry:
    import_path: str
    public_function_count: int

    @classmethod
    def from_api(
        cls,
        payload: Any,
        context: str = "benchmark_discovery_lane.discovered_source_inventory",
    ) -> RuntimeBenchmarkDiscoverySourceModuleEntry:
        data = coerce_payload_mapping(payload)
        public_function_count = _require_manifest_integer(data, "public_function_count", context)
        if public_function_count <= 0:
            raise ValueError(f"{context}.public_function_count must be greater than 0.")
        return cls(
            import_path=_require_manifest_string(data, "import_path", context),
            public_function_count=public_function_count,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RuntimeBenchmarkDiscoveryLane:
    discovered_source_modules: int
    discovered_public_functions: int
    discovered_source_inventory: list["RuntimeBenchmarkDiscoverySourceModuleEntry"]
    shipping_manifest_modules: int
    shipping_manifest_functions: int
    non_shipping_rule: RuntimeNonShippingRule

    @classmethod
    def from_api(
        cls,
        payload: Any,
        context: str = "benchmark_discovery_lane",
    ) -> RuntimeBenchmarkDiscoveryLane:
        data = coerce_payload_mapping(payload)
        raw_discovered_source_inventory = data.get("discovered_source_inventory")
        if not isinstance(raw_discovered_source_inventory, list):
            raise ValueError("benchmark_discovery_lane.discovered_source_inventory must be a list.")
        discovered_source_inventory = [
            RuntimeBenchmarkDiscoverySourceModuleEntry.from_api(
                item,
                f"{context}.discovered_source_inventory.{index}",
            )
            for index, item in enumerate(raw_discovered_source_inventory)
        ]
        _ensure_unique_manifest_values(
            discovered_source_inventory,
            f"{context}.discovered_source_inventory",
            value_selector=lambda entry: entry.import_path,
        )
        discovered_import_paths = [entry.import_path for entry in discovered_source_inventory]
        if discovered_import_paths != sorted(discovered_import_paths):
            raise ValueError(
                f"{context}.discovered_source_inventory must be sorted by import_path."
            )
        discovered_public_functions = _require_manifest_integer(
            data,
            "discovered_public_functions",
            context,
        )
        if len(discovered_source_inventory) != _require_manifest_integer(
            data,
            "discovered_source_modules",
            context,
        ):
            raise ValueError(
                f"{context}.discovered_source_modules must equal the number of discovered_source_inventory entries."
            )
        total_public_functions = sum(
            entry.public_function_count for entry in discovered_source_inventory
        )
        if total_public_functions != discovered_public_functions:
            raise ValueError(
                f"{context}.discovered_public_functions must equal the total discovered_source_inventory public_function_count."
            )
        shipping_manifest_modules = _require_manifest_integer(
            data,
            "shipping_manifest_modules",
            context,
        )
        if shipping_manifest_modules > len(discovered_source_inventory):
            raise ValueError(
                f"{context}.shipping_manifest_modules cannot exceed {context}.discovered_source_modules."
            )
        shipping_manifest_functions = _require_manifest_integer(
            data,
            "shipping_manifest_functions",
            context,
        )
        if shipping_manifest_functions > discovered_public_functions:
            raise ValueError(
                f"{context}.shipping_manifest_functions cannot exceed {context}.discovered_public_functions."
            )
        return cls(
            discovered_source_modules=len(discovered_source_inventory),
            discovered_public_functions=discovered_public_functions,
            discovered_source_inventory=discovered_source_inventory,
            shipping_manifest_modules=shipping_manifest_modules,
            shipping_manifest_functions=shipping_manifest_functions,
            non_shipping_rule=_coerce_enum(
                data["non_shipping_rule"],
                RuntimeNonShippingRule,
                f"{context}.non_shipping_rule",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


