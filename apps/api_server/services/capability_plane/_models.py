"""Request/response Pydantic models + _ScoredCapability.

Extracted from apps/api_server/services/capability_plane.py during modularization.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable, Sequence
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.models.capability_plane import (
    AuthorizationSessionStatus,
    BindingScope,
    BindingStatus,
    CapabilityBinding,
    CapabilityExecutionSession,
    CapabilityKind,
    CapabilityProvider,
    CapabilityProviderProfile,
    CapabilityRoutingOutcome,
    CapabilitySnapshot,
    ExecutionOwner,
    ExecutionSessionStatus,
    ImplementationKind,
    ProviderType,
)
from apps.api_server.models.data_connector import DataConnector
from apps.api_server.models.organization import Organization
from apps.api_server.services import source_registry as sreg
from apps.api_server.services.config_crypto import (
    decrypt_config_dict,
    decrypt_config_json,
    encrypt_config_dict,
)
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.workspace_scope import (
    workspace_id_for_write,
    workspace_scope_clauses,
)
from apps.api_server.services.connectors import test_connector_real_detailed
from apps.api_server.services.data_connection_browse import browse_connector_real_detailed
from apps.api_server.services.data_visibility import (
    filter_visible_datasets,
    get_visible_connector,
    get_visible_dataset_entry,
)
from apps.api_server.services.runtime_library_service import (
    execute_public_runtime_library,
    get_public_runtime_library_health,
    list_public_runtime_library_descriptors,
)
from apps.runtime_manifest import Replayability, RiskLevel, SideEffectClass

POLICY_SNAPSHOT_ID = "capability-plane-policy-v1"
SYSTEM_BINDING_REFRESH_TTL = timedelta(minutes=5)
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_.-]+")


from apps.api_server.services.capability_plane._constants import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._constants import (
    _CATALOG_CACHE_TTL,
    _catalog_cache,
    _invalidate_catalog_cache,
)
from apps.api_server.services.capability_plane._errors import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._errors import (
    _raise_error,
)
from apps.api_server.services.capability_plane._utils import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._utils import (
    _utc_now,
    _stable_hash,
    _dedupe_strings,
    _tokenize,
    _auth_org_id,
    _scope_ref_from_auth,
    _redact_binding_config,
    _system_binding_name,
)


class CapabilityProviderProfileResponse(CapabilityPlaneModel):
    profile_id: str
    provider_id: str
    name: str
    description: str | None = None
    auth_kind: str
    default_execution_owner: ExecutionOwner
    binding_scope_default: BindingScope
    supported_binding_scopes: list[str] = Field(default_factory=list)
    profile_metadata: dict[str, Any] | None = None


class CapabilityProviderResponse(CapabilityPlaneModel):
    provider_id: str
    provider_type: ProviderType
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
    profiles: list[CapabilityProviderProfileResponse] = Field(default_factory=list)


class CapabilityBindingCreateRequest(CapabilityPlaneModel):
    provider_id: str
    profile_id: str
    binding_name: str
    scope: BindingScope = BindingScope.WORKSPACE
    scope_ref: str | None = None
    execution_owner: ExecutionOwner | None = None
    config: dict[str, Any] | None = None
    customer_metadata: dict[str, Any] | None = None


class CapabilityBindingUpdateRequest(CapabilityPlaneModel):
    binding_name: str | None = None
    scope: BindingScope | None = None
    scope_ref: str | None = None
    status: BindingStatus | None = None
    execution_owner: ExecutionOwner | None = None
    config: dict[str, Any] | None = None
    customer_metadata: dict[str, Any] | None = None


class CapabilityBindingPreviewRequest(CapabilityPlaneModel):
    provider_id: str
    profile_id: str
    scope: BindingScope = BindingScope.WORKSPACE
    scope_ref: str | None = None
    execution_owner: ExecutionOwner | None = None
    config: dict[str, Any] | None = None
    customer_metadata: dict[str, Any] | None = None


class CapabilityBindingResponse(CapabilityPlaneModel):
    binding_id: str
    provider_id: str
    profile_id: str
    binding_name: str
    scope: BindingScope
    scope_ref: str
    status: BindingStatus
    execution_owner: ExecutionOwner
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


class CapabilityBindingTestResult(CapabilityPlaneModel):
    success: bool
    binding_status: BindingStatus
    message: str
    latency_ms: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class CapabilityCatalogEntry(CapabilityPlaneModel):
    capability_id: str
    provider_id: str
    profile_id: str
    binding_id: str
    kind: CapabilityKind
    name: str
    description: str | None = None
    implementation_kind: ImplementationKind
    execution_owner: ExecutionOwner
    input_schema_ref: str
    output_schema_ref: str
    side_effect_class: SideEffectClass
    risk_level: RiskLevel
    required_policy: str
    replayability: Replayability
    approval_required: bool
    trust_tier: str
    manifest_hash: str
    artifact_affinities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    required_binding_ids: list[str] = Field(default_factory=list)
    selected_tool_name: str | None = None
    instruction_artifact_ref: str | None = None
    binding_status: BindingStatus
    discovered_at: datetime | None = None
    customer_metadata: dict[str, Any] | None = None
    instruction_text: str | None = None

    @field_validator("artifact_affinities", "tags", "required_binding_ids")
    @classmethod
    def _validate_string_lists(cls, value: list[str]) -> list[str]:
        return _dedupe_strings(value)


class CapabilityDiscoverResponse(CapabilityPlaneModel):
    binding_id: str | None = None
    provider_id: str
    profile_id: str
    snapshot_id: str | None = None
    binding_status: BindingStatus
    manifest_hash: str
    capability_count: int
    discovered_at: datetime
    message: str
    capabilities: list[CapabilityCatalogEntry] = Field(default_factory=list)


class CapabilityRouteRequest(CapabilityPlaneModel):
    objective: str
    binding_ids: list[str] = Field(default_factory=list)
    provider_ids: list[str] = Field(default_factory=list)
    kinds: list[CapabilityKind] = Field(default_factory=list)
    execution_owners: list[ExecutionOwner] = Field(default_factory=list)
    artifact_affinities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    max_fallbacks: int = Field(default=3, ge=0, le=10)


class CapabilityRouteFallback(CapabilityPlaneModel):
    capability_id: str
    provider_id: str
    binding_id: str
    kind: CapabilityKind
    execution_owner: ExecutionOwner
    confidence: float
    reason: str
    selected_tool_name: str | None = None
    instruction_artifact_ref: str | None = None


class CapabilityRoutePlan(CapabilityPlaneModel):
    selected_capability_id: str
    selected_provider_id: str
    selected_binding_id: str
    kind: CapabilityKind
    execution_owner: ExecutionOwner
    requires_approval: bool
    confidence: float
    reason: str
    fallbacks: list[CapabilityRouteFallback] = Field(default_factory=list)
    policy_snapshot_id: str
    selected_tool_name: str | None = None
    instruction_artifact_ref: str | None = None


class CapabilityExecutionRequest(CapabilityPlaneModel):
    capability_id: str
    binding_id: str | None = None
    input: dict[str, Any] | None = None
    request_id: str | None = None


class CapabilityExecutionResponse(CapabilityPlaneModel):
    execution_session_id: str
    capability_id: str
    provider_id: str
    binding_id: str
    execution_owner: ExecutionOwner
    status: ExecutionSessionStatus
    output: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    started_at: datetime
    completed_at: datetime | None = None


class CapabilityOutcomeRecord(CapabilityPlaneModel):
    outcome_id: str
    capability_id: str
    provider_id: str
    binding_id: str | None = None
    success: bool | None = None
    result_status: str
    confidence: float | None = None
    latency_ms: float | None = None
    error_code: str | None = None
    details: dict[str, Any] | None = None
    created_at: datetime


class CapabilityOutcomeRecordRequest(CapabilityPlaneModel):
    capability_id: str
    provider_id: str
    binding_id: str | None = None
    success: bool | None = None
    result_status: str = Field(default="reported")
    confidence: float | None = None
    latency_ms: float | None = None
    error_code: str | None = None
    details: dict[str, Any] | None = None


class CapabilityAuthorizationStartRequest(CapabilityPlaneModel):
    redirect_uri: str | None = None
    requested_scopes: list[str] = Field(default_factory=list)
    state_payload: dict[str, Any] | None = None


class CapabilityAuthorizationStartResponse(CapabilityPlaneModel):
    session_id: str
    binding_id: str
    provider_id: str
    authorize_url: str
    expires_at: datetime
    requested_scopes: list[str] = Field(default_factory=list)


class CapabilityAuthorizationCompleteRequest(CapabilityPlaneModel):
    session_id: str
    callback_payload: dict[str, Any] | None = None
    authorization_code: str | None = None
    state: str | None = None


class CapabilityAuthorizationCompleteResponse(CapabilityPlaneModel):
    session_id: str
    binding_id: str
    provider_id: str
    status: AuthorizationSessionStatus
    authorized_at: datetime | None = None


class SkillEnableRequest(CapabilityPlaneModel):
    skill_name: str
    instruction: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    artifact_affinities: list[str] = Field(default_factory=list)
    execution_owner: ExecutionOwner = ExecutionOwner.CLIENT_MANAGED


@dataclass(frozen=True)
class _ScoredCapability:
    capability: CapabilityCatalogEntry
    score: float
    reason: str

