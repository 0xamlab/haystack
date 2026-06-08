from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, List, get_origin

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = _ROOT / "apps" / "docs" / "integration_manifest.v1.json"
_list_factory = list


class _StrictContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

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


class ApiKeyPrefixesResponse(_StrictContractModel):
    live: str
    test: str


class CompatibilityResponse(_StrictContractModel):
    legacy_headers: list[str] = Field(default_factory=list)
    legacy_env_vars: list[str] = Field(default_factory=list)
    legacy_domains: list[str] = Field(default_factory=list)
    deprecation_window_days: int


class PrivacyRegistryResponse(_StrictContractModel):
    algenta_owned_hosts: list[str] = Field(default_factory=list)
    algenta_owned_suffixes: list[str] = Field(default_factory=list)
    vendor_telemetry_hosts: list[str] = Field(default_factory=list)
    private_host_suffixes: list[str] = Field(default_factory=list)


class DefaultsResponse(_StrictContractModel):
    read_only_default: bool
    write_confirmation_required: bool
    plan_limits: dict[str, dict[str, int | str]]


class IntegrationResponse(_StrictContractModel):
    name: str
    description: str
    icon: str
    capabilities: list[str] = Field(default_factory=list)
    auth_scheme: str
    required_scopes: list[str] = Field(default_factory=list)
    read_only_default: bool
    write_actions: list[str] = Field(default_factory=list)
    admin_controls: list[str] = Field(default_factory=list)
    docs_url: str
    privacy_url: str
    terms_url: str
    support_url: str
    regions: list[str] = Field(default_factory=list)
    status: str


class PrimaryDataQueryApiResponse(_StrictContractModel):
    contract_endpoint: str
    discovery_endpoint: str
    summary_endpoint: str
    resolve_endpoint: str
    verify_endpoint: str
    query_endpoint: str
    query_batch_endpoint: str
    query_sql_report_endpoint: str


class GovernedFilterOperatorsResponse(_StrictContractModel):
    scalar: List[str] = Field(default_factory=_list_factory)
    list: List[str] = Field(default_factory=_list_factory)
    nullary: List[str] = Field(default_factory=_list_factory)


class GovernedFilterTypeBehaviorResponse(_StrictContractModel):
    boolean: list[str] = Field(default_factory=list)
    string: list[str] = Field(default_factory=list)
    numeric: list[str] = Field(default_factory=list)
    null_checks: list[str] = Field(default_factory=list)


class GovernedFilterValidationResponse(_StrictContractModel):
    requires_selector: bool
    scalar_ops_require_value: list[str] = Field(default_factory=list)
    list_ops_require_non_empty_values: list[str] = Field(default_factory=list)
    nullary_ops_forbid_value_and_values: list[str] = Field(default_factory=list)


class GovernedFilterContractResponse(_StrictContractModel):
    kind: str
    time_filter_field: str
    conditions_field: str
    selector_fields: list[str] = Field(default_factory=list)
    operators: GovernedFilterOperatorsResponse
    type_behavior: GovernedFilterTypeBehaviorResponse
    validation: GovernedFilterValidationResponse
    applies_before_aggregation: bool
    supports_non_sql_backends: bool
    notes: list[str] = Field(default_factory=list)


class DirectPythonSdkContractResponse(_StrictContractModel):
    import_root: str
    preferred_client_class: str
    preferred_async_client_class: str
    compatibility_client_class: str
    compatibility_async_client_class: str
    contract_method: str
    discovery_method: str
    summary_method: str
    query_with_metadata_method: str
    query_batch_method: str
    query_sql_report_method: str


class DirectTypeScriptSdkContractResponse(_StrictContractModel):
    import_package: str
    preferred_client_class: str
    compatibility_client_class: str
    contract_method: str
    discovery_method: str
    summary_method: str
    query_with_metadata_method: str
    query_batch_method: str
    query_sql_report_method: str


class DirectSdkContractResponse(_StrictContractModel):
    python: DirectPythonSdkContractResponse
    typescript: DirectTypeScriptSdkContractResponse


class RuntimePythonSdkContractResponse(_StrictContractModel):
    import_root: str
    runtime_class: str
    libraries_entrypoint: str
    contract_method: str
    discovery_method: str
    summary_method: str
    query_with_metadata_method: str
    query_batch_method: str
    query_sql_report_method: str


class RuntimeTypeScriptSdkContractResponse(_StrictContractModel):
    import_package: str
    runtime_class: str
    libraries_entrypoint: str
    contract_method: str
    discovery_method: str
    summary_method: str
    query_with_metadata_method: str
    query_batch_method: str
    query_sql_report_method: str


class RuntimeSdkContractResponse(_StrictContractModel):
    python: RuntimePythonSdkContractResponse
    typescript: RuntimeTypeScriptSdkContractResponse


class CliContractResponse(_StrictContractModel):
    contract_command: str
    discovery_command: str
    summary_command: str
    query_batch_command: str
    query_sql_report_command: str
    runtime_modules_command: str
    runtime_functions_command: str
    runtime_execute_command: str


class McpContractResponse(_StrictContractModel):
    contract_tool: str
    discovery_tool: str
    summary_tool: str
    query_tool: str
    query_batch_tool: str
    query_sql_report_tool: str
    runtime_library_list_tool: str
    runtime_library_execute_tool: str


class RecommendedFlowsResponse(_StrictContractModel):
    machine_readable_contract: list[str] = Field(default_factory=list)
    governed_query: list[str] = Field(default_factory=list)
    multi_metric_query: list[str] = Field(default_factory=list)
    wide_sql_report: list[str] = Field(default_factory=list)


class PrimaryDataQueryContractResponse(_StrictContractModel):
    api: PrimaryDataQueryApiResponse
    governed_filter_contract: GovernedFilterContractResponse
    direct_sdk: DirectSdkContractResponse
    runtime_sdk: RuntimeSdkContractResponse
    cli: CliContractResponse
    mcp: McpContractResponse
    recommended_flows: RecommendedFlowsResponse


class CapabilityPlaneApiResponse(_StrictContractModel):
    list_providers_endpoint: str
    get_provider_endpoint: str
    list_bindings_endpoint: str
    create_binding_endpoint: str
    get_binding_endpoint: str
    update_binding_endpoint: str
    delete_binding_endpoint: str
    preview_test_binding_endpoint: str
    test_binding_endpoint: str
    preview_discover_binding_endpoint: str
    discover_binding_endpoint: str
    start_authorization_endpoint: str
    complete_authorization_endpoint: str
    list_capabilities_endpoint: str
    get_capability_endpoint: str
    route_capabilities_endpoint: str
    execute_capability_endpoint: str
    record_outcome_endpoint: str


class CapabilityPlaneEnumsResponse(_StrictContractModel):
    provider_types: list[str] = Field(default_factory=list)
    capability_kinds: list[str] = Field(default_factory=list)
    implementation_kinds: list[str] = Field(default_factory=list)
    execution_owners: list[str] = Field(default_factory=list)
    binding_scopes: list[str] = Field(default_factory=list)
    binding_statuses: list[str] = Field(default_factory=list)


class CapabilityPlaneTypeScriptSdkContractResponse(_StrictContractModel):
    import_package: str
    preferred_client_class: str
    compatibility_client_class: str
    list_providers_method: str
    get_provider_method: str
    list_bindings_method: str
    create_binding_method: str
    get_binding_method: str
    update_binding_method: str
    delete_binding_method: str
    preview_test_binding_method: str
    test_binding_method: str
    preview_discover_binding_method: str
    discover_binding_method: str
    start_authorization_method: str
    complete_authorization_method: str
    list_capabilities_method: str
    get_capability_method: str
    route_capabilities_method: str
    execute_capability_method: str
    record_outcome_method: str
    list_skills_method: str
    enable_skill_method: str
    disable_skill_method: str
    list_mcp_providers_method: str


class CapabilityPlaneRuntimeTypeScriptSdkContractResponse(_StrictContractModel):
    import_package: str
    runtime_class: str
    list_providers_method: str
    list_bindings_method: str
    list_capabilities_method: str
    route_capabilities_method: str
    execute_capability_method: str
    register_adapter_method: str


class CapabilityPlaneDirectSdkContractResponse(_StrictContractModel):
    typescript: CapabilityPlaneTypeScriptSdkContractResponse


class CapabilityPlaneRuntimeSdkContractResponse(_StrictContractModel):
    typescript: CapabilityPlaneRuntimeTypeScriptSdkContractResponse


class CapabilityPlaneMcpContractResponse(_StrictContractModel):
    list_providers_tool: str
    list_bindings_tool: str
    create_binding_tool: str
    test_binding_tool: str
    discover_binding_tool: str
    list_capabilities_tool: str
    get_capability_tool: str
    route_capabilities_tool: str
    execute_capability_tool: str
    list_skills_tool: str
    enable_skill_tool: str
    disable_skill_tool: str
    compatibility_aliases: list[str] = Field(default_factory=list)


class CapabilityPlaneContractResponse(_StrictContractModel):
    api: CapabilityPlaneApiResponse
    enums: CapabilityPlaneEnumsResponse
    direct_sdk: CapabilityPlaneDirectSdkContractResponse
    runtime_sdk: CapabilityPlaneRuntimeSdkContractResponse
    mcp: CapabilityPlaneMcpContractResponse


class PlatformContractResponse(_StrictContractModel):
    contract_version: str
    brand: str
    api_base_url: str
    mcp_endpoint: str
    mcp_tools_endpoint: str
    auth_scheme: str
    api_key_prefixes: ApiKeyPrefixesResponse
    compatibility: CompatibilityResponse
    privacy_registry: PrivacyRegistryResponse
    defaults: DefaultsResponse
    primary_data_query_contract: PrimaryDataQueryContractResponse
    capability_plane: CapabilityPlaneContractResponse | None = None
    integrations: list[IntegrationResponse] = Field(default_factory=list)


class PlatformContractManifestError(ValueError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _normalize_platform_contract_payload(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return {
            key: _normalize_platform_contract_payload(item)
            for key, item in value.__dict__.items()
            if not key.startswith("_")
        }
    if isinstance(value, dict):
        return {
            str(key): _normalize_platform_contract_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_platform_contract_payload(item) for item in value]
    return value


def _build_platform_contract_error_details(exc: ValidationError) -> dict[str, Any]:
    try:
        errors = exc.errors(include_url=False, include_context=True, include_input=False)
    except TypeError:  # pragma: no cover - compatibility guard
        errors = exc.errors()

    validation_errors: list[dict[str, str]] = []
    for error in errors:
        path = ".".join(str(item) for item in tuple(error.get("loc") or ()) if str(item))
        validation_errors.append(
            {
                "path": path,
                "message": str(error.get("msg", "Invalid value")),
                "type": str(error.get("type", "validation_error")),
            }
        )

    cause = next(
        (item["path"] for item in validation_errors if item.get("path")),
        str(exc),
    )
    details: dict[str, Any] = {"cause": cause}
    if validation_errors:
        details["validation_errors"] = validation_errors
    return details


def validate_platform_contract_payload(payload: Any) -> PlatformContractResponse:
    try:
        return PlatformContractResponse.model_validate(
            _normalize_platform_contract_payload(payload)
        )
    except ValidationError as exc:
        details = _build_platform_contract_error_details(exc)
        cause = details.get("cause")
        suffix = f": {cause}" if isinstance(cause, str) and cause else ""
        raise PlatformContractManifestError(
            "invalid_platform_contract_manifest",
            "Integration manifest does not match the canonical Algenta contract schema."
            f"{suffix}",
            details,
        ) from exc


@dataclass(frozen=True)
class PlatformContract:
    contract_version: str
    brand: str
    api_base_url: str
    mcp_endpoint: str
    mcp_tools_endpoint: str
    auth_scheme: str
    api_key_prefix_live: str
    api_key_prefix_test: str
    legacy_headers: tuple[str, ...]
    legacy_env_vars: tuple[str, ...]
    legacy_domains: tuple[str, ...]
    algenta_owned_hosts: tuple[str, ...]
    algenta_owned_suffixes: tuple[str, ...]
    vendor_telemetry_hosts: tuple[str, ...]
    private_host_suffixes: tuple[str, ...]
    deprecation_window_days: int
    plan_limits: dict[str, dict[str, Any]]
    primary_data_query_contract: dict[str, Any]
    capability_plane: dict[str, Any] | None
    integrations: tuple[dict[str, Any], ...]


def _load_platform_contract_raw_manifest() -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text())
    if not isinstance(manifest, dict):
        raise PlatformContractManifestError(
            "invalid_platform_contract_manifest",
            "Integration manifest must be a JSON object.",
        )
    return manifest


@lru_cache(maxsize=1)
def load_platform_contract_manifest_model() -> PlatformContractResponse:
    return validate_platform_contract_payload(_load_platform_contract_raw_manifest())


def load_platform_contract_manifest() -> dict[str, Any]:
    return load_platform_contract_manifest_model().model_dump(mode="json")


@lru_cache(maxsize=1)
def load_platform_contract() -> PlatformContract:
    manifest = load_platform_contract_manifest_model()
    compatibility = manifest.compatibility
    privacy_registry = manifest.privacy_registry
    defaults = manifest.defaults
    return PlatformContract(
        contract_version=manifest.contract_version,
        brand=manifest.brand,
        api_base_url=manifest.api_base_url,
        mcp_endpoint=manifest.mcp_endpoint,
        mcp_tools_endpoint=manifest.mcp_tools_endpoint,
        auth_scheme=manifest.auth_scheme,
        api_key_prefix_live=manifest.api_key_prefixes.live,
        api_key_prefix_test=manifest.api_key_prefixes.test,
        legacy_headers=tuple(compatibility.legacy_headers),
        legacy_env_vars=tuple(compatibility.legacy_env_vars),
        legacy_domains=tuple(compatibility.legacy_domains),
        algenta_owned_hosts=tuple(privacy_registry.algenta_owned_hosts),
        algenta_owned_suffixes=tuple(privacy_registry.algenta_owned_suffixes),
        vendor_telemetry_hosts=tuple(privacy_registry.vendor_telemetry_hosts),
        private_host_suffixes=tuple(privacy_registry.private_host_suffixes),
        deprecation_window_days=int(compatibility.deprecation_window_days),
        plan_limits=defaults.model_dump(mode="python")["plan_limits"],
        primary_data_query_contract=manifest.primary_data_query_contract.model_dump(mode="python"),
        capability_plane=(
            manifest.capability_plane.model_dump(mode="python")
            if manifest.capability_plane is not None
            else None
        ),
        integrations=tuple(item.model_dump(mode="python") for item in manifest.integrations),
    )


def clear_platform_contract_caches() -> None:
    load_platform_contract_manifest_model.cache_clear()
    load_platform_contract.cache_clear()
