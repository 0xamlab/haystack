from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Mapping
from typing import Any

from pydantic import BaseModel

from algenta.runtime_model_common import coerce_payload_mapping, jsonable


@dataclass(frozen=True)
class ApiKeyPrefixes:
    live: str
    test: str

    @classmethod
    def from_api(cls, payload: Any) -> ApiKeyPrefixes:
        context = "api_key_prefixes"
        data = _coerce_contract_mapping(payload, context)
        return cls(
            live=_require_contract_string(data, "live", context),
            test=_require_contract_string(data, "test", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class CompatibilityContract:
    legacy_headers: list[str] = field(default_factory=list)
    legacy_env_vars: list[str] = field(default_factory=list)
    legacy_domains: list[str] = field(default_factory=list)
    deprecation_window_days: int = 0

    @classmethod
    def from_api(cls, payload: Any) -> CompatibilityContract:
        context = "compatibility"
        data = _coerce_contract_mapping(payload, context)
        return cls(
            legacy_headers=_optional_contract_string_list(data, "legacy_headers", context),
            legacy_env_vars=_optional_contract_string_list(data, "legacy_env_vars", context),
            legacy_domains=_optional_contract_string_list(data, "legacy_domains", context),
            deprecation_window_days=_require_contract_integer(
                data,
                "deprecation_window_days",
                context,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class DefaultsContract:
    read_only_default: bool
    write_confirmation_required: bool
    plan_limits: dict[str, dict[str, int | str]] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: Any) -> DefaultsContract:
        context = "defaults"
        data = _coerce_contract_mapping(payload, context)
        return cls(
            read_only_default=_require_contract_boolean(
                data,
                "read_only_default",
                context,
            ),
            write_confirmation_required=_require_contract_boolean(
                data,
                "write_confirmation_required",
                context,
            ),
            plan_limits=_parse_contract_plan_limits(
                data.get("plan_limits"),
                f"{context}.plan_limits",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class IntegrationContract:
    name: str
    description: str
    icon: str
    capabilities: list[str] = field(default_factory=list)
    auth_scheme: str = ""
    required_scopes: list[str] = field(default_factory=list)
    read_only_default: bool = True
    write_actions: list[str] = field(default_factory=list)
    admin_controls: list[str] = field(default_factory=list)
    docs_url: str = ""
    privacy_url: str = ""
    terms_url: str = ""
    support_url: str = ""
    regions: list[str] = field(default_factory=list)
    status: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> IntegrationContract:
        context = "integrations.item"
        data = _coerce_contract_mapping(payload, context)
        return cls(
            name=_require_contract_string(data, "name", context),
            description=_require_contract_string(data, "description", context),
            icon=_require_contract_string(data, "icon", context),
            capabilities=_optional_contract_string_list(data, "capabilities", context),
            auth_scheme=_require_contract_string(data, "auth_scheme", context),
            required_scopes=_optional_contract_string_list(data, "required_scopes", context),
            read_only_default=_optional_contract_boolean(
                data,
                "read_only_default",
                context,
                default=True,
            ),
            write_actions=_optional_contract_string_list(data, "write_actions", context),
            admin_controls=_optional_contract_string_list(data, "admin_controls", context),
            docs_url=_require_contract_string(data, "docs_url", context),
            privacy_url=_require_contract_string(data, "privacy_url", context),
            terms_url=_require_contract_string(data, "terms_url", context),
            support_url=_require_contract_string(data, "support_url", context),
            regions=_optional_contract_string_list(data, "regions", context),
            status=_require_contract_string(data, "status", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


def _coerce_contract_mapping(payload: Any, context: str) -> dict[str, Any]:
    try:
        if isinstance(payload, BaseModel):
            return {
                str(key): _normalize_contract_payload_value(value)
                for key, value in payload.__dict__.items()
                if not str(key).startswith("_")
            }
        if isinstance(payload, Mapping):
            return {
                str(key): _normalize_contract_payload_value(value)
                for key, value in payload.items()
            }
        model_dump = getattr(payload, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump()
            if isinstance(dumped, Mapping):
                return {
                    str(key): _normalize_contract_payload_value(value)
                    for key, value in dumped.items()
                }
        if hasattr(payload, "__dict__") and isinstance(payload.__dict__, dict):
            return {
                str(key): _normalize_contract_payload_value(value)
                for key, value in payload.__dict__.items()
                if not str(key).startswith("_")
            }
        return coerce_payload_mapping(payload)
    except Exception as exc:
        raise TypeError(f"{context} must be a mapping.") from exc


def _normalize_contract_payload_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_contract_payload_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_contract_payload_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_normalize_contract_payload_value(item) for item in value)
    return value


def _require_contract_string(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _require_contract_boolean(data: dict[str, Any], key: str, context: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise TypeError(f"{context}.{key} must be a boolean.")
    return value


def _optional_contract_boolean(
    data: dict[str, Any],
    key: str,
    context: str,
    *,
    default: bool,
) -> bool:
    if key not in data:
        return default
    return _require_contract_boolean(data, key, context)


def _require_contract_integer(data: dict[str, Any], key: str, context: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{context}.{key} must be an integer.")
    return value


def _require_contract_string_list(data: dict[str, Any], key: str, context: str) -> list[str]:
    raw = data.get(key)
    if not isinstance(raw, list) or not all(isinstance(item, str) and item for item in raw):
        raise TypeError(f"{context}.{key} must be a list of non-empty strings.")
    return [str(item) for item in raw]


def _optional_contract_string_list(
    data: dict[str, Any],
    key: str,
    context: str,
) -> list[str]:
    if key not in data:
        return []
    return _require_contract_string_list(data, key, context)


def _parse_contract_plan_limits(payload: Any, context: str) -> dict[str, dict[str, int | str]]:
    data = _coerce_contract_mapping(payload, context)
    plan_limits: dict[str, dict[str, int | str]] = {}
    for plan_name, limit_payload in data.items():
        if not isinstance(plan_name, str) or not plan_name:
            raise TypeError(f"{context} keys must be non-empty strings.")
        limit_context = f"{context}.{plan_name}"
        limits = _coerce_contract_mapping(limit_payload, limit_context)
        normalized_limits: dict[str, int | str] = {}
        for limit_name, limit_value in limits.items():
            if not isinstance(limit_name, str) or not limit_name:
                raise TypeError(f"{limit_context} keys must be non-empty strings.")
            if isinstance(limit_value, bool) or not isinstance(limit_value, (int, str)):
                raise TypeError(
                    f"{limit_context}.{limit_name} must be an integer or non-empty string."
                )
            if isinstance(limit_value, str) and not limit_value:
                raise TypeError(
                    f"{limit_context}.{limit_name} must be an integer or non-empty string."
                )
            normalized_limits[limit_name] = limit_value
        plan_limits[plan_name] = normalized_limits
    return plan_limits


def _parse_contract_api(payload: Any, context: str) -> dict[str, Any]:
    data = _coerce_contract_mapping(payload, context)
    return {
        "contract_endpoint": _require_contract_string(data, "contract_endpoint", context),
        "discovery_endpoint": _require_contract_string(data, "discovery_endpoint", context),
        "summary_endpoint": _require_contract_string(data, "summary_endpoint", context),
        "resolve_endpoint": _require_contract_string(data, "resolve_endpoint", context),
        "verify_endpoint": _require_contract_string(data, "verify_endpoint", context),
        "query_endpoint": _require_contract_string(data, "query_endpoint", context),
        "query_batch_endpoint": _require_contract_string(data, "query_batch_endpoint", context),
        "query_sql_report_endpoint": _require_contract_string(
            data,
            "query_sql_report_endpoint",
            context,
        ),
    }


def _parse_governed_filter_operators(payload: Any, context: str) -> dict[str, Any]:
    data = _coerce_contract_mapping(payload, context)
    return {
        "scalar": _require_contract_string_list(data, "scalar", context),
        "list": _require_contract_string_list(data, "list", context),
        "nullary": _require_contract_string_list(data, "nullary", context),
    }


def _parse_governed_filter_type_behavior(payload: Any, context: str) -> dict[str, Any]:
    data = _coerce_contract_mapping(payload, context)
    return {
        "boolean": _require_contract_string_list(data, "boolean", context),
        "string": _require_contract_string_list(data, "string", context),
        "numeric": _require_contract_string_list(data, "numeric", context),
        "null_checks": _require_contract_string_list(data, "null_checks", context),
    }


def _parse_governed_filter_validation(payload: Any, context: str) -> dict[str, Any]:
    data = _coerce_contract_mapping(payload, context)
    return {
        "requires_selector": _require_contract_boolean(data, "requires_selector", context),
        "scalar_ops_require_value": _require_contract_string_list(
            data,
            "scalar_ops_require_value",
            context,
        ),
        "list_ops_require_non_empty_values": _require_contract_string_list(
            data,
            "list_ops_require_non_empty_values",
            context,
        ),
        "nullary_ops_forbid_value_and_values": _require_contract_string_list(
            data,
            "nullary_ops_forbid_value_and_values",
            context,
        ),
    }


def _parse_governed_filter_contract(payload: Any, context: str) -> dict[str, Any]:
    data = _coerce_contract_mapping(payload, context)
    return {
        "kind": _require_contract_string(data, "kind", context),
        "time_filter_field": _require_contract_string(data, "time_filter_field", context),
        "conditions_field": _require_contract_string(data, "conditions_field", context),
        "selector_fields": _require_contract_string_list(data, "selector_fields", context),
        "operators": _parse_governed_filter_operators(data.get("operators"), f"{context}.operators"),
        "type_behavior": _parse_governed_filter_type_behavior(
            data.get("type_behavior"),
            f"{context}.type_behavior",
        ),
        "validation": _parse_governed_filter_validation(
            data.get("validation"),
            f"{context}.validation",
        ),
        "applies_before_aggregation": _require_contract_boolean(
            data,
            "applies_before_aggregation",
            context,
        ),
        "supports_non_sql_backends": _require_contract_boolean(
            data,
            "supports_non_sql_backends",
            context,
        ),
        "notes": _require_contract_string_list(data, "notes", context),
    }


def _parse_direct_python_sdk_contract(payload: Any, context: str) -> dict[str, Any]:
    data = _coerce_contract_mapping(payload, context)
    return {
        "import_root": _require_contract_string(data, "import_root", context),
        "preferred_client_class": _require_contract_string(
            data,
            "preferred_client_class",
            context,
        ),
        "preferred_async_client_class": _require_contract_string(
            data,
            "preferred_async_client_class",
            context,
        ),
        "compatibility_client_class": _require_contract_string(
            data,
            "compatibility_client_class",
            context,
        ),
        "compatibility_async_client_class": _require_contract_string(
            data,
            "compatibility_async_client_class",
            context,
        ),
        "contract_method": _require_contract_string(data, "contract_method", context),
        "discovery_method": _require_contract_string(data, "discovery_method", context),
        "summary_method": _require_contract_string(data, "summary_method", context),
        "query_with_metadata_method": _require_contract_string(
            data,
            "query_with_metadata_method",
            context,
        ),
        "query_batch_method": _require_contract_string(data, "query_batch_method", context),
        "query_sql_report_method": _require_contract_string(
            data,
            "query_sql_report_method",
            context,
        ),
    }


def _parse_direct_typescript_sdk_contract(payload: Any, context: str) -> dict[str, Any]:
    data = _coerce_contract_mapping(payload, context)
    return {
        "import_package": _require_contract_string(data, "import_package", context),
        "preferred_client_class": _require_contract_string(
            data,
            "preferred_client_class",
            context,
        ),
        "compatibility_client_class": _require_contract_string(
            data,
            "compatibility_client_class",
            context,
        ),
        "contract_method": _require_contract_string(data, "contract_method", context),
        "discovery_method": _require_contract_string(data, "discovery_method", context),
        "summary_method": _require_contract_string(data, "summary_method", context),
        "query_with_metadata_method": _require_contract_string(
            data,
            "query_with_metadata_method",
            context,
        ),
        "query_batch_method": _require_contract_string(data, "query_batch_method", context),
        "query_sql_report_method": _require_contract_string(
            data,
            "query_sql_report_method",
            context,
        ),
    }


def _parse_runtime_python_sdk_contract(payload: Any, context: str) -> dict[str, Any]:
    data = _coerce_contract_mapping(payload, context)
    return {
        "import_root": _require_contract_string(data, "import_root", context),
        "runtime_class": _require_contract_string(data, "runtime_class", context),
        "libraries_entrypoint": _require_contract_string(data, "libraries_entrypoint", context),
        "contract_method": _require_contract_string(data, "contract_method", context),
        "discovery_method": _require_contract_string(data, "discovery_method", context),
        "summary_method": _require_contract_string(data, "summary_method", context),
        "query_with_metadata_method": _require_contract_string(
            data,
            "query_with_metadata_method",
            context,
        ),
        "query_batch_method": _require_contract_string(data, "query_batch_method", context),
        "query_sql_report_method": _require_contract_string(
            data,
            "query_sql_report_method",
            context,
        ),
    }


def _parse_runtime_typescript_sdk_contract(payload: Any, context: str) -> dict[str, Any]:
    data = _coerce_contract_mapping(payload, context)
    return {
        "import_package": _require_contract_string(data, "import_package", context),
        "runtime_class": _require_contract_string(data, "runtime_class", context),
        "libraries_entrypoint": _require_contract_string(data, "libraries_entrypoint", context),
        "contract_method": _require_contract_string(data, "contract_method", context),
        "discovery_method": _require_contract_string(data, "discovery_method", context),
        "summary_method": _require_contract_string(data, "summary_method", context),
        "query_with_metadata_method": _require_contract_string(
            data,
            "query_with_metadata_method",
            context,
        ),
        "query_batch_method": _require_contract_string(data, "query_batch_method", context),
        "query_sql_report_method": _require_contract_string(
            data,
            "query_sql_report_method",
            context,
        ),
    }


def _parse_cli_contract(payload: Any, context: str) -> dict[str, Any]:
    data = _coerce_contract_mapping(payload, context)
    return {
        "contract_command": _require_contract_string(data, "contract_command", context),
        "discovery_command": _require_contract_string(data, "discovery_command", context),
        "summary_command": _require_contract_string(data, "summary_command", context),
        "query_batch_command": _require_contract_string(data, "query_batch_command", context),
        "query_sql_report_command": _require_contract_string(
            data,
            "query_sql_report_command",
            context,
        ),
        "runtime_modules_command": _require_contract_string(
            data,
            "runtime_modules_command",
            context,
        ),
        "runtime_functions_command": _require_contract_string(
            data,
            "runtime_functions_command",
            context,
        ),
        "runtime_execute_command": _require_contract_string(
            data,
            "runtime_execute_command",
            context,
        ),
    }


def _parse_mcp_contract(payload: Any, context: str) -> dict[str, Any]:
    data = _coerce_contract_mapping(payload, context)
    return {
        "contract_tool": _require_contract_string(data, "contract_tool", context),
        "discovery_tool": _require_contract_string(data, "discovery_tool", context),
        "summary_tool": _require_contract_string(data, "summary_tool", context),
        "query_tool": _require_contract_string(data, "query_tool", context),
        "query_batch_tool": _require_contract_string(data, "query_batch_tool", context),
        "query_sql_report_tool": _require_contract_string(
            data,
            "query_sql_report_tool",
            context,
        ),
        "runtime_library_list_tool": _require_contract_string(
            data,
            "runtime_library_list_tool",
            context,
        ),
        "runtime_library_execute_tool": _require_contract_string(
            data,
            "runtime_library_execute_tool",
            context,
        ),
    }


def _parse_recommended_flows_contract(payload: Any, context: str) -> dict[str, Any]:
    data = _coerce_contract_mapping(payload, context)
    return {
        "machine_readable_contract": _require_contract_string_list(
            data,
            "machine_readable_contract",
            context,
        ),
        "governed_query": _require_contract_string_list(data, "governed_query", context),
        "multi_metric_query": _require_contract_string_list(data, "multi_metric_query", context),
        "wide_sql_report": _require_contract_string_list(data, "wide_sql_report", context),
    }


def _parse_primary_data_query_contract(payload: Any) -> dict[str, Any]:
    context = "primary_data_query_contract"
    data = _coerce_contract_mapping(payload, context)
    return {
        "api": _parse_contract_api(data.get("api"), f"{context}.api"),
        "governed_filter_contract": _parse_governed_filter_contract(
            data.get("governed_filter_contract"),
            f"{context}.governed_filter_contract",
        ),
        "direct_sdk": {
            "python": _parse_direct_python_sdk_contract(
                _coerce_contract_mapping(data.get("direct_sdk"), f"{context}.direct_sdk").get(
                    "python"
                ),
                f"{context}.direct_sdk.python",
            ),
            "typescript": _parse_direct_typescript_sdk_contract(
                _coerce_contract_mapping(data.get("direct_sdk"), f"{context}.direct_sdk").get(
                    "typescript"
                ),
                f"{context}.direct_sdk.typescript",
            ),
        },
        "runtime_sdk": {
            "python": _parse_runtime_python_sdk_contract(
                _coerce_contract_mapping(data.get("runtime_sdk"), f"{context}.runtime_sdk").get(
                    "python"
                ),
                f"{context}.runtime_sdk.python",
            ),
            "typescript": _parse_runtime_typescript_sdk_contract(
                _coerce_contract_mapping(data.get("runtime_sdk"), f"{context}.runtime_sdk").get(
                    "typescript"
                ),
                f"{context}.runtime_sdk.typescript",
            ),
        },
        "cli": _parse_cli_contract(data.get("cli"), f"{context}.cli"),
        "mcp": _parse_mcp_contract(data.get("mcp"), f"{context}.mcp"),
        "recommended_flows": _parse_recommended_flows_contract(
            data.get("recommended_flows"),
            f"{context}.recommended_flows",
        ),
    }


@dataclass(frozen=True)
class PlatformContractOutput:
    contract_version: str
    brand: str
    api_base_url: str
    mcp_endpoint: str
    mcp_tools_endpoint: str
    auth_scheme: str
    api_key_prefixes: ApiKeyPrefixes
    compatibility: CompatibilityContract
    defaults: DefaultsContract
    primary_data_query_contract: dict[str, Any] = field(default_factory=dict)
    capability_plane: dict[str, Any] | None = None
    integrations: list[IntegrationContract] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> PlatformContractOutput:
        context = "platform_contract"
        data = _coerce_contract_mapping(payload, context)
        raw_integrations = data.get("integrations", [])
        if not isinstance(raw_integrations, list):
            raise TypeError(f"{context}.integrations must be a list.")
        return cls(
            contract_version=_require_contract_string(data, "contract_version", context),
            brand=_require_contract_string(data, "brand", context),
            api_base_url=_require_contract_string(data, "api_base_url", context),
            mcp_endpoint=_require_contract_string(data, "mcp_endpoint", context),
            mcp_tools_endpoint=_require_contract_string(data, "mcp_tools_endpoint", context),
            auth_scheme=_require_contract_string(data, "auth_scheme", context),
            api_key_prefixes=ApiKeyPrefixes.from_api(data["api_key_prefixes"]),
            compatibility=CompatibilityContract.from_api(data["compatibility"]),
            defaults=DefaultsContract.from_api(data["defaults"]),
            primary_data_query_contract=_parse_primary_data_query_contract(
                data["primary_data_query_contract"]
            ),
            capability_plane=(
                _coerce_contract_mapping(data.get("capability_plane"), f"{context}.capability_plane")
                if data.get("capability_plane") is not None
                else None
            ),
            integrations=[
                IntegrationContract.from_api(item) for item in raw_integrations
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))
