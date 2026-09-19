# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CapabilityProviderProfileResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    profile_id: str
    provider_id: str
    name: str
    description: str | None = None
    auth_kind: str
    default_execution_owner: str
    binding_scope_default: str
    supported_binding_scopes: list[str] = Field(default_factory=list)
    profile_metadata: dict[str, Any] | None = None


class CapabilityProviderResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    provider_id: str
    provider_type: str
    name: str
    description: str | None = None
    docs_url: str | None = None
    auth_schema: dict[str, Any] | None = None
    certification_summary: dict[str, Any] | None = None
    policy_summary: dict[str, Any] | None = None
    supported_execution_owners: list[str] = Field(default_factory=list)
    install_metadata: dict[str, Any] | None = None
    customer_metadata: dict[str, Any] | None = None
    active: bool
    profiles: list[CapabilityProviderProfileResult] = Field(default_factory=list)


class CapabilityBindingResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    binding_id: str
    provider_id: str
    profile_id: str
    binding_name: str
    scope: str
    scope_ref: str
    status: str
    execution_owner: str
    config: dict[str, Any] | None = None
    customer_metadata: dict[str, Any] | None = None
    system_managed: bool
    last_tested_at: datetime | None = None
    last_discovered_at: datetime | None = None
    authorized_at: datetime | None = None
    quarantine_reason: str | None = None
    discovery_error_message: str | None = None
    test_error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class CapabilityBindingTestResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    success: bool
    binding_status: str
    message: str
    latency_ms: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class CapabilityCatalogEntryResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    capability_id: str
    provider_id: str
    profile_id: str
    binding_id: str
    kind: str
    name: str
    description: str | None = None
    implementation_kind: str
    execution_owner: str
    input_schema_ref: str
    output_schema_ref: str
    side_effect_class: str
    risk_level: str
    required_policy: str
    replayability: str
    approval_required: bool
    trust_tier: str
    manifest_hash: str
    artifact_affinities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    required_binding_ids: list[str] = Field(default_factory=list)
    selected_tool_name: str | None = None
    instruction_artifact_ref: str | None = None
    binding_status: str
    discovered_at: datetime | None = None
    customer_metadata: dict[str, Any] | None = None
    instruction_text: str | None = None


class CapabilityDiscoverResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    binding_id: str | None = None
    provider_id: str
    profile_id: str
    snapshot_id: str | None = None
    binding_status: str
    manifest_hash: str
    capability_count: int
    discovered_at: datetime
    message: str
    capabilities: list[CapabilityCatalogEntryResult] = Field(default_factory=list)


class CapabilityRouteFallbackResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    capability_id: str
    provider_id: str
    binding_id: str
    kind: str
    execution_owner: str
    confidence: float
    reason: str
    selected_tool_name: str | None = None
    instruction_artifact_ref: str | None = None


class CapabilityRoutePlanResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    selected_capability_id: str
    selected_provider_id: str
    selected_binding_id: str
    kind: str
    execution_owner: str
    requires_approval: bool
    confidence: float
    reason: str
    fallbacks: list[CapabilityRouteFallbackResult] = Field(default_factory=list)
    policy_snapshot_id: str
    selected_tool_name: str | None = None
    instruction_artifact_ref: str | None = None


class CapabilityExecutionResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    execution_session_id: str
    capability_id: str
    provider_id: str
    binding_id: str
    execution_owner: str
    status: str
    output: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    started_at: datetime
    completed_at: datetime | None = None


class CapabilityOutcomeRecordResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    outcome_id: str
    capability_id: str
    provider_id: str
    binding_id: str | None = None
    success: bool | None = None
    result_status: str
    confidence: float | None = None
    latency_ms: int | None = None
    error_code: str | None = None
    details: dict[str, Any] | None = None
    created_at: datetime


class CapabilityAuthorizationStartResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    session_id: str
    binding_id: str
    provider_id: str
    authorize_url: str
    expires_at: datetime
    requested_scopes: list[str] = Field(default_factory=list)


class CapabilityAuthorizationCompleteResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    session_id: str
    binding_id: str
    provider_id: str
    status: str
    authorized_at: datetime | None = None
