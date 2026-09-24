# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import builtins
from typing import Any, get_origin

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_list_factory = list


class _ContractBaseModel(BaseModel):
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


class _PrimaryDataQueryApiContractResult(_ContractBaseModel):
    contract_endpoint: str
    discovery_endpoint: str
    summary_endpoint: str
    resolve_endpoint: str
    verify_endpoint: str
    query_endpoint: str
    query_batch_endpoint: str
    query_sql_report_endpoint: str


class _GovernedFilterOperatorsContractResult(_ContractBaseModel):
    scalar: builtins.list[str] = Field(default_factory=_list_factory)
    list: builtins.list[str] = Field(default_factory=_list_factory)
    nullary: builtins.list[str] = Field(default_factory=_list_factory)


class _GovernedFilterTypeBehaviorContractResult(_ContractBaseModel):
    boolean: list[str] = Field(default_factory=list)
    string: list[str] = Field(default_factory=list)
    numeric: list[str] = Field(default_factory=list)
    null_checks: list[str] = Field(default_factory=list)


class _GovernedFilterValidationContractResult(_ContractBaseModel):
    requires_selector: bool
    scalar_ops_require_value: list[str] = Field(default_factory=list)
    list_ops_require_non_empty_values: list[str] = Field(default_factory=list)
    nullary_ops_forbid_value_and_values: list[str] = Field(default_factory=list)


class _GovernedFilterContractResult(_ContractBaseModel):
    kind: str
    time_filter_field: str
    conditions_field: str
    selector_fields: list[str] = Field(default_factory=list)
    operators: _GovernedFilterOperatorsContractResult
    type_behavior: _GovernedFilterTypeBehaviorContractResult
    validation: _GovernedFilterValidationContractResult
    applies_before_aggregation: bool
    supports_non_sql_backends: bool
    notes: list[str] = Field(default_factory=list)


class _DirectPythonSdkContractResult(_ContractBaseModel):
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


class _DirectTypeScriptSdkContractResult(_ContractBaseModel):
    import_package: str
    preferred_client_class: str
    compatibility_client_class: str
    contract_method: str
    discovery_method: str
    summary_method: str
    query_with_metadata_method: str
    query_batch_method: str
    query_sql_report_method: str


class _DirectSdkContractResult(_ContractBaseModel):
    python: _DirectPythonSdkContractResult
    typescript: _DirectTypeScriptSdkContractResult


class _RuntimePythonSdkContractResult(_ContractBaseModel):
    import_root: str
    runtime_class: str
    libraries_entrypoint: str
    contract_method: str
    discovery_method: str
    summary_method: str
    query_with_metadata_method: str
    query_batch_method: str
    query_sql_report_method: str


class _RuntimeTypeScriptSdkContractResult(_ContractBaseModel):
    import_package: str
    runtime_class: str
    libraries_entrypoint: str
    contract_method: str
    discovery_method: str
    summary_method: str
    query_with_metadata_method: str
    query_batch_method: str
    query_sql_report_method: str


class _RuntimeSdkContractResult(_ContractBaseModel):
    python: _RuntimePythonSdkContractResult
    typescript: _RuntimeTypeScriptSdkContractResult


class _CliContractResult(_ContractBaseModel):
    contract_command: str
    discovery_command: str
    summary_command: str
    query_batch_command: str
    query_sql_report_command: str
    runtime_modules_command: str
    runtime_functions_command: str
    runtime_execute_command: str


class _McpContractResult(_ContractBaseModel):
    contract_tool: str
    discovery_tool: str
    summary_tool: str
    query_tool: str
    query_batch_tool: str
    query_sql_report_tool: str
    runtime_library_list_tool: str
    runtime_library_execute_tool: str


class _RecommendedFlowsContractResult(_ContractBaseModel):
    machine_readable_contract: list[str] = Field(default_factory=list)
    governed_query: list[str] = Field(default_factory=list)
    multi_metric_query: list[str] = Field(default_factory=list)
    wide_sql_report: list[str] = Field(default_factory=list)
    decision_simulation_tools: list[str] = Field(default_factory=list)
    dataset_onboarding_tools: list[str] = Field(default_factory=list)


class _PrimaryDataQueryContractValidationResult(_ContractBaseModel):
    api: _PrimaryDataQueryApiContractResult
    governed_filter_contract: _GovernedFilterContractResult
    direct_sdk: _DirectSdkContractResult
    runtime_sdk: _RuntimeSdkContractResult
    cli: _CliContractResult
    mcp: _McpContractResult
    recommended_flows: _RecommendedFlowsContractResult


class ApiKeyPrefixesResult(_ContractBaseModel):
    live: str
    test: str


class CompatibilityContractResult(_ContractBaseModel):
    legacy_headers: list[str] = Field(default_factory=list)
    legacy_env_vars: list[str] = Field(default_factory=list)
    legacy_domains: list[str] = Field(default_factory=list)
    deprecation_window_days: int


class PrivacyRegistryContractResult(_ContractBaseModel):
    algenta_owned_hosts: list[str] = Field(default_factory=list)
    algenta_owned_suffixes: list[str] = Field(default_factory=list)
    vendor_telemetry_hosts: list[str] = Field(default_factory=list)
    private_host_suffixes: list[str] = Field(default_factory=list)


class DefaultsContractResult(_ContractBaseModel):
    read_only_default: bool
    write_confirmation_required: bool
    plan_limits: dict[str, dict[str, int | str]]


class IntegrationContractResult(_ContractBaseModel):
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


class PlatformContractResult(_ContractBaseModel):
    contract_version: str
    brand: str
    api_base_url: str
    mcp_endpoint: str
    mcp_transport: str
    mcp_protocol_version: str
    mcp_legacy_sse_endpoint: str
    mcp_tools_endpoint: str
    auth_scheme: str
    api_key_prefixes: ApiKeyPrefixesResult
    compatibility: CompatibilityContractResult
    privacy_registry: PrivacyRegistryContractResult
    defaults: DefaultsContractResult
    primary_data_query_contract: dict[str, Any]
    capability_plane: dict[str, Any] | None = None
    integrations: list[IntegrationContractResult] = Field(default_factory=list)

    @field_validator("primary_data_query_contract")
    @classmethod
    def _validate_primary_data_query_contract(cls, value: Any) -> dict[str, Any]:
        payload = _PrimaryDataQueryContractValidationResult.model_validate(value)
        return payload.model_dump(mode="python")

    @field_validator("capability_plane")
    @classmethod
    def _validate_capability_plane(cls, value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("capability_plane must be a JSON object when provided.")
        return value
