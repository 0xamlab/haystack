"""Customer-agnostic capability-plane services."""

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

# Process-level catalog cache. `_catalog_for_org` reloads all bindings and
# re-probes every system binding (data-connector tests, runtime-library
# discovery) on EVERY call. Capability routing/listing is on the agent hot path
# (it blocks the first model token), and the org catalog changes rarely, so we
# cache the built catalog briefly per (org, include_instruction) and invalidate
# it on any binding mutation. This turns the local /v1/capabilities/route call
# from ~1-2s into sub-millisecond after the first build.
# Invalidate-on-write cache. Freshness comes from explicit
# _invalidate_catalog_cache() calls on every catalog-changing mutation (binding
# create/update/delete, skill enable/disable) — NOT from this timer. The TTL is
# only a self-healing backstop for any mutation path we might miss, so it's
# deliberately long: a short timer just makes spaced-out chat requests re-pay
# the full ~1-2s catalog rebuild every time. The cache is per-process and clears
# on restart, so a long backstop is safe.
_CATALOG_CACHE_TTL = timedelta(hours=24)
_catalog_cache: dict[
    tuple[str, bool], tuple[datetime, list["CapabilityCatalogEntry"]]
] = {}


def _invalidate_catalog_cache() -> None:
    _catalog_cache.clear()

DATA_CONNECTOR_PROVIDER_ID = "provider.data_connector.algenta"
DATA_CONNECTOR_PROFILE_ID = "profile.data_connector.workspace"
MCP_PROVIDER_ID = "provider.mcp.generic"
MCP_PROFILE_ID = "profile.mcp.workspace"
SKILL_PACK_PROVIDER_ID = "provider.skill_pack.algenta"
SKILL_PACK_PROFILE_ID = "profile.skill_pack.user"
NATIVE_TOOL_PROVIDER_ID = "provider.native_tool_pack.customer"
NATIVE_TOOL_PROFILE_ID = "profile.native_tool_pack.workspace"
RUNTIME_LIBRARY_PROVIDER_ID = "provider.runtime_library_pack.algenta"
RUNTIME_LIBRARY_PROFILE_ID = "profile.runtime_library_pack.workspace"

DEFAULT_PROVIDER_SPECS: tuple[dict[str, Any], ...] = (
    {
        "provider_id": DATA_CONNECTOR_PROVIDER_ID,
        "provider_type": ProviderType.DATA_CONNECTOR,
        "name": "Algenta Governed Data",
        "description": (
            "Algenta-managed governed dataset inventory derived from registered datasets "
            "and connector-backed sources."
        ),
        "docs_url": "/v1/data",
        "auth_schema_json": {"type": "managed", "fields": []},
        "certification_summary_json": {"owner": "algenta", "certified": True},
        "policy_summary_json": {
            "route_authority": "capability_plane",
            "execution_path": "governed_data",
        },
        "supported_execution_owners_json": [ExecutionOwner.ALGENTA_MANAGED.value],
        "install_metadata_json": {"discovery_mode": "system_managed"},
    },
    {
        "provider_id": MCP_PROVIDER_ID,
        "provider_type": ProviderType.MCP_PROVIDER,
        "name": "Generic MCP Provider",
        "description": (
            "Customer-registered MCP provider profile. Discovery persists MCP tools, "
            "resources, and prompts into the unified capability catalog."
        ),
        "docs_url": "/mcp/sse",
        "auth_schema_json": {
            "type": "oauth_or_api_key",
            "fields": ["server_url", "authorization_url"],
        },
        "certification_summary_json": {"owner": "customer", "certified": False},
        "policy_summary_json": {"route_authority": "capability_plane"},
        "supported_execution_owners_json": [
            ExecutionOwner.ALGENTA_MANAGED.value,
            ExecutionOwner.CLIENT_MANAGED.value,
        ],
        "install_metadata_json": {"discovery_mode": "binding_manifest"},
    },
    {
        "provider_id": SKILL_PACK_PROVIDER_ID,
        "provider_type": ProviderType.SKILL_PACK,
        "name": "Skill Pack",
        "description": (
            "Prompt-only and hybrid skills stored as customer-agnostic capability records."
        ),
        "docs_url": "/v1/capabilities",
        "auth_schema_json": {"type": "none", "fields": []},
        "certification_summary_json": {"owner": "customer", "certified": False},
        "policy_summary_json": {"route_authority": "capability_plane"},
        "supported_execution_owners_json": [
            ExecutionOwner.ALGENTA_MANAGED.value,
            ExecutionOwner.CLIENT_MANAGED.value,
        ],
        "install_metadata_json": {"discovery_mode": "binding_manifest"},
    },
    {
        "provider_id": NATIVE_TOOL_PROVIDER_ID,
        "provider_type": ProviderType.NATIVE_TOOL_PACK,
        "name": "Native Tool Pack",
        "description": "Customer-managed native tool definitions exposed through the capability plane.",
        "docs_url": "/v1/capabilities",
        "auth_schema_json": {"type": "none", "fields": []},
        "certification_summary_json": {"owner": "customer", "certified": False},
        "policy_summary_json": {"route_authority": "capability_plane"},
        "supported_execution_owners_json": [
            ExecutionOwner.ALGENTA_MANAGED.value,
            ExecutionOwner.CLIENT_MANAGED.value,
        ],
        "install_metadata_json": {"discovery_mode": "binding_manifest"},
    },
    {
        "provider_id": RUNTIME_LIBRARY_PROVIDER_ID,
        "provider_type": ProviderType.RUNTIME_LIBRARY_PACK,
        "name": "Algenta Runtime Libraries",
        "description": "Algenta-managed executable runtime-library inventory.",
        "docs_url": "/v1/libraries",
        "auth_schema_json": {"type": "managed", "fields": []},
        "certification_summary_json": {"owner": "algenta", "certified": True},
        "policy_summary_json": {"route_authority": "capability_plane"},
        "supported_execution_owners_json": [ExecutionOwner.ALGENTA_MANAGED.value],
        "install_metadata_json": {"discovery_mode": "system_managed"},
    },
)

DEFAULT_PROFILE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "profile_id": DATA_CONNECTOR_PROFILE_ID,
        "provider_id": DATA_CONNECTOR_PROVIDER_ID,
        "name": "Workspace governed datasets",
        "description": "System-managed governed data binding for one workspace-equivalent scope.",
        "auth_kind": "managed",
        "default_execution_owner": ExecutionOwner.ALGENTA_MANAGED,
        "binding_scope_default": BindingScope.WORKSPACE,
        "supported_binding_scopes_json": [BindingScope.WORKSPACE.value],
    },
    {
        "profile_id": MCP_PROFILE_ID,
        "provider_id": MCP_PROVIDER_ID,
        "name": "Workspace MCP profile",
        "description": "Customer-provided MCP capability manifest and auth state.",
        "auth_kind": "oauth_or_api_key",
        "default_execution_owner": ExecutionOwner.CLIENT_MANAGED,
        "binding_scope_default": BindingScope.WORKSPACE,
        "supported_binding_scopes_json": [
            BindingScope.WORKSPACE.value,
            BindingScope.ORGANIZATION.value,
        ],
    },
    {
        "profile_id": SKILL_PACK_PROFILE_ID,
        "provider_id": SKILL_PACK_PROVIDER_ID,
        "name": "User skills",
        "description": "User-scoped prompt-only or hybrid skill pack.",
        "auth_kind": "none",
        "default_execution_owner": ExecutionOwner.CLIENT_MANAGED,
        "binding_scope_default": BindingScope.USER,
        "supported_binding_scopes_json": [BindingScope.USER.value],
    },
    {
        "profile_id": NATIVE_TOOL_PROFILE_ID,
        "provider_id": NATIVE_TOOL_PROVIDER_ID,
        "name": "Workspace native tools",
        "description": "Workspace-scoped native-tool pack provided by the customer.",
        "auth_kind": "none",
        "default_execution_owner": ExecutionOwner.CLIENT_MANAGED,
        "binding_scope_default": BindingScope.WORKSPACE,
        "supported_binding_scopes_json": [
            BindingScope.WORKSPACE.value,
            BindingScope.ORGANIZATION.value,
        ],
    },
    {
        "profile_id": RUNTIME_LIBRARY_PROFILE_ID,
        "provider_id": RUNTIME_LIBRARY_PROVIDER_ID,
        "name": "Workspace runtime libraries",
        "description": "System-managed Algenta runtime-library binding.",
        "auth_kind": "managed",
        "default_execution_owner": ExecutionOwner.ALGENTA_MANAGED,
        "binding_scope_default": BindingScope.WORKSPACE,
        "supported_binding_scopes_json": [BindingScope.WORKSPACE.value],
    },
)

SECRET_FIELD_NAMES = {
    "access_token",
    "api_key",
    "authorization",
    "bearer_token",
    "client_secret",
    "password",
    "refresh_token",
    "secret",
    "token",
}


class CapabilityPlaneError(ValueError):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def capability_plane_error_payload(exc: CapabilityPlaneError) -> dict[str, Any]:
    return {
        "error": {
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        }
    }


def _raise_error(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    raise CapabilityPlaneError(
        status_code=status_code,
        code=code,
        message=message,
        details=details,
    )


class CapabilityPlaneModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _dedupe_strings(values: Iterable[str | None]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]


def _auth_org_id(auth: AuthContext) -> uuid.UUID:
    org_id = auth["org_id"]
    if isinstance(org_id, uuid.UUID):
        return org_id
    return uuid.UUID(str(org_id))


def _scope_ref_from_auth(
    auth: AuthContext,
    *,
    scope: BindingScope,
    scope_ref: str | None,
) -> str:
    if scope_ref:
        return scope_ref.strip()
    if scope is BindingScope.USER:
        user_id = auth.get("user_id")
        return str(user_id) if user_id is not None else str(auth["key_id"])
    return str(auth["org_id"])


def _redact_binding_config(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = key.lower()
            if lowered in SECRET_FIELD_NAMES:
                redacted[key] = "***redacted***"
                continue
            if lowered == "manifest" and isinstance(item, dict):
                capabilities = item.get("capabilities")
                count = len(capabilities) if isinstance(capabilities, list) else 0
                redacted[key] = {"capability_count": count}
                continue
            redacted[key] = _redact_binding_config(item)
        return redacted
    if isinstance(value, list):
        return [_redact_binding_config(item) for item in value]
    return value


def _system_binding_name(provider_id: str) -> str:
    if provider_id == DATA_CONNECTOR_PROVIDER_ID:
        return "System governed data plane"
    if provider_id == RUNTIME_LIBRARY_PROVIDER_ID:
        return "System runtime libraries"
    return f"System binding for {provider_id}"


@dataclass(frozen=True)
class ResolvedBindingContext:
    binding_id: str | None
    provider_id: str
    profile_id: str
    binding_name: str
    scope: BindingScope
    scope_ref: str
    status: BindingStatus
    execution_owner: ExecutionOwner
    config: dict[str, Any]
    customer_metadata: dict[str, Any]
    system_managed: bool
    last_discovered_at: datetime | None = None


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


def _binding_response(binding: CapabilityBinding) -> CapabilityBindingResponse:
    return CapabilityBindingResponse(
        binding_id=str(binding.id),
        provider_id=binding.provider_id,
        profile_id=binding.profile_id,
        binding_name=binding.binding_name,
        scope=binding.scope,
        scope_ref=str(binding.scope_ref or ""),
        status=binding.status,
        execution_owner=binding.execution_owner,
        config=_redact_binding_config(
            decrypt_config_dict(binding.config_json, org_id=getattr(binding, "org_id", ""))
        ),
        customer_metadata=binding.customer_metadata_json,
        system_managed=bool(binding.system_managed),
        last_tested_at=binding.last_tested_at,
        last_discovered_at=binding.last_discovered_at,
        authorized_at=binding.authorized_at,
        quarantine_reason=binding.quarantine_reason,
        discovery_error_message=binding.discovery_error_message,
        test_error_message=binding.test_error_message,
        created_at=binding.created_at,
        updated_at=binding.updated_at,
    )


def _provider_profile_response(profile: CapabilityProviderProfile) -> CapabilityProviderProfileResponse:
    return CapabilityProviderProfileResponse(
        profile_id=profile.profile_id,
        provider_id=profile.provider_id,
        name=profile.name,
        description=profile.description,
        auth_kind=profile.auth_kind,
        default_execution_owner=profile.default_execution_owner,
        binding_scope_default=profile.binding_scope_default,
        supported_binding_scopes=list(profile.supported_binding_scopes_json or []),
        profile_metadata=profile.profile_metadata_json,
    )


def _provider_response(
    provider: CapabilityProvider,
    *,
    profiles: Sequence[CapabilityProviderProfile],
) -> CapabilityProviderResponse:
    return CapabilityProviderResponse(
        provider_id=provider.provider_id,
        provider_type=provider.provider_type,
        name=provider.name,
        description=provider.description,
        docs_url=provider.docs_url,
        auth_schema=provider.auth_schema_json,
        certification_summary=provider.certification_summary_json,
        policy_summary=provider.policy_summary_json,
        supported_execution_owners=list(provider.supported_execution_owners_json or []),
        install_metadata=provider.install_metadata_json,
        customer_metadata=provider.customer_metadata_json,
        active=bool(provider.active),
        profiles=[_provider_profile_response(profile) for profile in profiles],
    )


def _dataset_tags(entry: dict[str, Any], schema_meta: dict[str, Any] | None) -> list[str]:
    values = [
        str(entry.get("id") or ""),
        str(entry.get("dataset_name") or entry.get("name") or ""),
        *[str(item) for item in (entry.get("source_names") or []) if isinstance(item, str)],
    ]
    if isinstance(schema_meta, dict):
        values.extend(
            str(item)
            for item in (schema_meta.get("query_hints") or [])
            if isinstance(item, str)
        )
    return _dedupe_strings(values)


def _dataset_artifact_affinities(entry: dict[str, Any]) -> list[str]:
    return _dedupe_strings(
        [
            str(entry.get("dataset_name") or entry.get("name") or ""),
            *[str(item) for item in (entry.get("source_names") or []) if isinstance(item, str)],
        ]
    )


def _build_dataset_capability(
    *,
    binding: ResolvedBindingContext,
    entry: dict[str, Any],
    schema_meta: dict[str, Any] | None,
    manifest_hash: str,
    discovered_at: datetime,
) -> CapabilityCatalogEntry:
    dataset_id = str(entry.get("id") or entry.get("dataset_id") or "")
    dataset_name = str(entry.get("dataset_name") or entry.get("name") or dataset_id)
    source_names = [str(item) for item in (entry.get("source_names") or []) if isinstance(item, str)]
    description_parts = [f"dataset_id={dataset_id}"]
    if source_names:
        description_parts.append(f"sources={', '.join(source_names[:5])}")
    if isinstance(schema_meta, dict) and schema_meta.get("row_count") is not None:
        description_parts.append(f"rows={schema_meta.get('row_count')}")
    return CapabilityCatalogEntry(
        capability_id=f"cap.dataset.{dataset_id}",
        provider_id=binding.provider_id,
        profile_id=binding.profile_id,
        binding_id=str(binding.binding_id),
        kind=CapabilityKind.DATASET,
        name=dataset_name,
        description="; ".join(description_parts),
        implementation_kind=ImplementationKind.CALLABLE,
        execution_owner=binding.execution_owner,
        input_schema_ref="schemas/capability-plane/dataset.summary-or-governed-query.json",
        output_schema_ref="schemas/capability-plane/dataset.summary.json",
        side_effect_class=SideEffectClass.read_only,
        risk_level=RiskLevel.low,
        required_policy="policy.governed_data.query",
        replayability=Replayability.artifact_backed,
        approval_required=False,
        trust_tier="algenta_governed",
        manifest_hash=manifest_hash,
        artifact_affinities=_dataset_artifact_affinities(entry),
        tags=_dataset_tags(entry, schema_meta),
        required_binding_ids=[str(binding.binding_id)],
        binding_status=binding.status,
        discovered_at=discovered_at,
        customer_metadata={"dataset_id": dataset_id, "source_names": source_names},
    )


def _build_runtime_library_capability(
    *,
    binding: ResolvedBindingContext,
    module_name: str,
    function_name: str,
    engine: str,
    manifest_hash: str,
    discovered_at: datetime,
) -> CapabilityCatalogEntry:
    dotted_name = f"{module_name}.{function_name}"
    return CapabilityCatalogEntry(
        capability_id=f"cap.runtime_library.{module_name}.{function_name}",
        provider_id=binding.provider_id,
        profile_id=binding.profile_id,
        binding_id=str(binding.binding_id),
        kind=CapabilityKind.RUNTIME_LIBRARY,
        name=dotted_name,
        description=f"Runtime library function `{dotted_name}` backed by engine `{engine}`.",
        implementation_kind=ImplementationKind.CALLABLE,
        execution_owner=binding.execution_owner,
        input_schema_ref=f"runtime-library://{module_name}/{function_name}/input",
        output_schema_ref=f"runtime-library://{module_name}/{function_name}/output",
        side_effect_class=SideEffectClass.read_only,
        risk_level=RiskLevel.low,
        required_policy="policy.runtime_library.execute",
        replayability=Replayability.deterministic,
        approval_required=False,
        trust_tier="algenta_runtime",
        manifest_hash=manifest_hash,
        artifact_affinities=[module_name],
        tags=_dedupe_strings([module_name, function_name, dotted_name]),
        required_binding_ids=[str(binding.binding_id)],
        selected_tool_name=function_name,
        binding_status=binding.status,
        discovered_at=discovered_at,
        customer_metadata={"module": module_name, "function": function_name},
    )


def _provider_type_from_capability_kind(kind: CapabilityKind) -> ProviderType:
    if kind is CapabilityKind.DATASET:
        return ProviderType.DATA_CONNECTOR
    if kind in {CapabilityKind.MCP_TOOL, CapabilityKind.MCP_PROMPT, CapabilityKind.MCP_RESOURCE}:
        return ProviderType.MCP_PROVIDER
    if kind is CapabilityKind.SKILL:
        return ProviderType.SKILL_PACK
    if kind is CapabilityKind.NATIVE_TOOL:
        return ProviderType.NATIVE_TOOL_PACK
    return ProviderType.RUNTIME_LIBRARY_PACK


def _manifest_capability_kind_allowed(
    *,
    provider_id: str,
    kind: CapabilityKind,
) -> bool:
    if provider_id == MCP_PROVIDER_ID:
        return kind in {CapabilityKind.MCP_TOOL, CapabilityKind.MCP_PROMPT, CapabilityKind.MCP_RESOURCE}
    if provider_id == SKILL_PACK_PROVIDER_ID:
        return kind is CapabilityKind.SKILL
    if provider_id == NATIVE_TOOL_PROVIDER_ID:
        return kind is CapabilityKind.NATIVE_TOOL
    return True


def _manifest_capability_entry_to_catalog(
    *,
    binding: ResolvedBindingContext,
    manifest_hash: str,
    discovered_at: datetime,
    payload: dict[str, Any],
) -> CapabilityCatalogEntry:
    capability_id = str(payload.get("capability_id") or "").strip()
    if not capability_id:
        _raise_error(422, "invalid_capability_manifest", "Capability manifest entries require capability_id.")
    try:
        kind = CapabilityKind(str(payload.get("kind") or "").strip())
    except ValueError as exc:
        _raise_error(
            422,
            "invalid_capability_manifest",
            "Capability manifest entries require a valid kind.",
            {"capability_id": capability_id, "field": "kind"},
        )
    if not _manifest_capability_kind_allowed(provider_id=binding.provider_id, kind=kind):
        _raise_error(
            422,
            "invalid_capability_manifest",
            f"Capability kind '{kind.value}' is not allowed for provider '{binding.provider_id}'.",
        )
    try:
        implementation_kind = ImplementationKind(
            str(payload.get("implementation_kind") or ImplementationKind.CALLABLE.value)
        )
        execution_owner = ExecutionOwner(
            str(payload.get("execution_owner") or binding.execution_owner.value)
        )
        side_effect_class = SideEffectClass(
            str(payload.get("side_effect_class") or SideEffectClass.read_only.value)
        )
        risk_level = RiskLevel(str(payload.get("risk_level") or RiskLevel.low.value))
        replayability = Replayability(
            str(payload.get("replayability") or Replayability.deterministic.value)
        )
    except ValueError as exc:
        _raise_error(
            422,
            "invalid_capability_manifest",
            "Capability manifest contains an invalid enum value.",
            {"capability_id": capability_id},
        )
    instruction_text = payload.get("instruction")
    instruction_artifact_ref = payload.get("instruction_artifact_ref")
    if isinstance(instruction_text, str) and instruction_text.strip() and not instruction_artifact_ref:
        instruction_artifact_ref = f"artifact://capability-snapshot/{manifest_hash}/{capability_id}"
    selected_tool_name = payload.get("selected_tool_name")
    return CapabilityCatalogEntry(
        capability_id=capability_id,
        provider_id=binding.provider_id,
        profile_id=binding.profile_id,
        binding_id=str(binding.binding_id),
        kind=kind,
        name=str(payload.get("name") or capability_id),
        description=(
            str(payload.get("description")).strip()
            if isinstance(payload.get("description"), str)
            else None
        ),
        implementation_kind=implementation_kind,
        execution_owner=execution_owner,
        input_schema_ref=str(
            payload.get("input_schema_ref") or f"capability://{capability_id}/input"
        ),
        output_schema_ref=str(
            payload.get("output_schema_ref") or f"capability://{capability_id}/output"
        ),
        side_effect_class=side_effect_class,
        risk_level=risk_level,
        required_policy=str(payload.get("required_policy") or "policy.capability.execute"),
        replayability=replayability,
        approval_required=bool(payload.get("approval_required") or False),
        trust_tier=str(payload.get("trust_tier") or "customer_managed"),
        manifest_hash=manifest_hash,
        artifact_affinities=_dedupe_strings(payload.get("artifact_affinities") or []),
        tags=_dedupe_strings(payload.get("tags") or []),
        required_binding_ids=_dedupe_strings(
            payload.get("required_binding_ids") or [str(binding.binding_id)]
        ),
        selected_tool_name=selected_tool_name if isinstance(selected_tool_name, str) else None,
        instruction_artifact_ref=(
            str(instruction_artifact_ref).strip()
            if isinstance(instruction_artifact_ref, str) and str(instruction_artifact_ref).strip()
            else None
        ),
        binding_status=binding.status,
        discovered_at=discovered_at,
        customer_metadata=payload.get("customer_metadata") if isinstance(payload.get("customer_metadata"), dict) else None,
        instruction_text=instruction_text if isinstance(instruction_text, str) else None,
    )


async def _ensure_org_exists(db: AsyncSession, org_id: uuid.UUID) -> None:
    org = await db.get(Organization, org_id)
    if org is None:
        _raise_error(404, "organization_not_found", "Organization not found.")


async def ensure_capability_plane_seeded(db: AsyncSession) -> None:
    for spec in DEFAULT_PROVIDER_SPECS:
        provider = await db.get(CapabilityProvider, spec["provider_id"])
        if provider is None:
            provider = CapabilityProvider(**spec)
            db.add(provider)
        else:
            provider.provider_type = spec["provider_type"]
            provider.name = spec["name"]
            provider.description = spec["description"]
            provider.docs_url = spec["docs_url"]
            provider.auth_schema_json = spec["auth_schema_json"]
            provider.certification_summary_json = spec["certification_summary_json"]
            provider.policy_summary_json = spec["policy_summary_json"]
            provider.supported_execution_owners_json = spec["supported_execution_owners_json"]
            provider.install_metadata_json = spec["install_metadata_json"]
            provider.active = True
    for spec in DEFAULT_PROFILE_SPECS:
        profile = await db.get(CapabilityProviderProfile, spec["profile_id"])
        if profile is None:
            profile = CapabilityProviderProfile(**spec)
            db.add(profile)
        else:
            profile.provider_id = spec["provider_id"]
            profile.name = spec["name"]
            profile.description = spec["description"]
            profile.auth_kind = spec["auth_kind"]
            profile.default_execution_owner = spec["default_execution_owner"]
            profile.binding_scope_default = spec["binding_scope_default"]
            profile.supported_binding_scopes_json = spec["supported_binding_scopes_json"]
    await db.flush()


async def _ensure_system_binding(
    db: AsyncSession,
    *,
    auth: AuthContext,
    provider_id: str,
    profile_id: str,
    execution_owner: ExecutionOwner,
) -> CapabilityBinding:
    org_id = _auth_org_id(auth)
    scope_ref = _scope_ref_from_auth(auth, scope=BindingScope.WORKSPACE, scope_ref=None)
    result = await db.execute(
        select(CapabilityBinding)
        .where(*workspace_scope_clauses(CapabilityBinding, auth))
        .where(CapabilityBinding.provider_id == provider_id)
        .where(CapabilityBinding.profile_id == profile_id)
        .where(CapabilityBinding.system_managed.is_(True))
        .order_by(CapabilityBinding.created_at.asc())
    )
    binding = result.scalars().first()
    if binding is None:
        binding = CapabilityBinding(
            org_id=org_id,
            workspace_id=workspace_id_for_write(auth),
            provider_id=provider_id,
            profile_id=profile_id,
            binding_name=_system_binding_name(provider_id),
            scope=BindingScope.WORKSPACE,
            scope_ref=scope_ref,
            status=BindingStatus.READY,
            execution_owner=execution_owner,
            config_json={},
            customer_metadata_json={},
            system_managed=True,
        )
        db.add(binding)
        await db.flush()
    return binding


async def _ensure_system_bindings(db: AsyncSession, auth: AuthContext) -> None:
    org_id = _auth_org_id(auth)
    await _ensure_org_exists(db, org_id)
    await ensure_capability_plane_seeded(db)
    await _ensure_system_binding(
        db,
        auth=auth,
        provider_id=DATA_CONNECTOR_PROVIDER_ID,
        profile_id=DATA_CONNECTOR_PROFILE_ID,
        execution_owner=ExecutionOwner.ALGENTA_MANAGED,
    )
    await _ensure_system_binding(
        db,
        auth=auth,
        provider_id=RUNTIME_LIBRARY_PROVIDER_ID,
        profile_id=RUNTIME_LIBRARY_PROFILE_ID,
        execution_owner=ExecutionOwner.ALGENTA_MANAGED,
    )
    await db.flush()


async def _require_provider(
    db: AsyncSession,
    provider_id: str,
) -> CapabilityProvider:
    provider = await db.get(CapabilityProvider, provider_id)
    if provider is None or not provider.active:
        _raise_error(404, "provider_not_found", f"Capability provider '{provider_id}' not found.")
    return provider


async def _require_profile(
    db: AsyncSession,
    profile_id: str,
) -> CapabilityProviderProfile:
    profile = await db.get(CapabilityProviderProfile, profile_id)
    if profile is None:
        _raise_error(404, "profile_not_found", f"Capability provider profile '{profile_id}' not found.")
    return profile


async def _require_binding(
    db: AsyncSession,
    auth: AuthContext,
    binding_id: str,
) -> CapabilityBinding:
    try:
        parsed = uuid.UUID(binding_id)
    except ValueError:
        _raise_error(422, "invalid_binding_id", "binding_id must be a valid UUID.")
    binding = await db.get(CapabilityBinding, parsed)
    _auth_ws = auth.get("workspace_id")
    if (
        binding is None
        or binding.org_id != _auth_org_id(auth)
        or (_auth_ws is not None and binding.workspace_id != _auth_ws)
    ):
        _raise_error(404, "binding_not_found", f"Capability binding '{binding_id}' not found.")
    return binding


def _binding_context_from_model(binding: CapabilityBinding) -> ResolvedBindingContext:
    return ResolvedBindingContext(
        binding_id=str(binding.id),
        provider_id=binding.provider_id,
        profile_id=binding.profile_id,
        binding_name=binding.binding_name,
        scope=binding.scope,
        scope_ref=str(binding.scope_ref or ""),
        status=binding.status,
        execution_owner=binding.execution_owner,
        config=dict(
            decrypt_config_dict(binding.config_json, org_id=getattr(binding, "org_id", "")) or {}
        ),
        customer_metadata=dict(binding.customer_metadata_json or {}),
        system_managed=bool(binding.system_managed),
        last_discovered_at=binding.last_discovered_at,
    )


def _binding_context_from_preview(
    *,
    auth: AuthContext,
    payload: CapabilityBindingPreviewRequest,
    default_execution_owner: ExecutionOwner,
) -> ResolvedBindingContext:
    scope = payload.scope
    return ResolvedBindingContext(
        binding_id=None,
        provider_id=payload.provider_id,
        profile_id=payload.profile_id,
        binding_name="preview",
        scope=scope,
        scope_ref=_scope_ref_from_auth(auth, scope=scope, scope_ref=payload.scope_ref),
        status=BindingStatus.READY,
        execution_owner=payload.execution_owner or default_execution_owner,
        config=dict(payload.config or {}),
        customer_metadata=dict(payload.customer_metadata or {}),
        system_managed=False,
    )


async def _connector_config_for_binding(
    db: AsyncSession,
    auth: AuthContext,
    binding: ResolvedBindingContext,
) -> tuple[str, dict[str, Any]] | None:
    config = dict(binding.config)
    connector_id_raw = config.get("connector_id")
    connector_type_raw = config.get("connector_type")
    connector_config_raw = config.get("config")
    if isinstance(connector_id_raw, str) and connector_id_raw.strip():
        try:
            connector_id = uuid.UUID(connector_id_raw)
        except ValueError:
            _raise_error(422, "invalid_connector_id", "connector_id must be a valid UUID.")
        # SECURITY: scope the saved-connector lookup to the caller's org + workspace.
        # The binding preview endpoints (POST /v1/capability-bindings/test|/discover) accept
        # a caller-controlled config.connector_id; a bare db.get(DataConnector, id) here was a
        # cross-tenant / cross-org IDOR (it would decrypt + live-connect a victim's connector).
        # get_visible_connector applies workspace_scope_clauses + connector_visible and 404s
        # out-of-scope ids, making a foreign connector indistinguishable from a missing one.
        connector = await get_visible_connector(db, connector_id, auth)
        try:
            stored_config = json.loads(
                decrypt_config_json(connector.config_json, org_id=connector.org_id) or "{}"
            )
        except json.JSONDecodeError:
            _raise_error(
                409,
                "invalid_connector_config",
                "Saved connector config is not valid JSON.",
            )
        return connector.connector_type.value, stored_config if isinstance(stored_config, dict) else {}
    if isinstance(connector_type_raw, str) and connector_type_raw.strip():
        normalized_config = connector_config_raw if isinstance(connector_config_raw, dict) else {}
        return connector_type_raw.strip(), normalized_config
    return None


async def _discover_data_connector_binding(
    db: AsyncSession,
    auth: AuthContext,
    binding: ResolvedBindingContext,
) -> tuple[list[CapabilityCatalogEntry], dict[str, Any], str]:
    connector = await _connector_config_for_binding(db, auth, binding)
    discovered_at = _utc_now()
    if connector is not None:
        connector_type, connector_config = connector
        items, message, discovery = await browse_connector_real_detailed(
            connector_type,
            connector_config,
        )
        manifest_payload = {
            "binding_kind": "data_connector_preview",
            "preview": True,
            "items": items,
            "discovery": discovery,
        }
        manifest_hash = _stable_hash(manifest_payload)
        capabilities = []
        for item in items:
            label = str(item.get("label") or item.get("name") or item.get("selection") or "preview")
            selection = item.get("selection") if isinstance(item.get("selection"), dict) else {}
            capability = CapabilityCatalogEntry(
                capability_id=f"cap.dataset.preview.{manifest_hash[:12]}.{_stable_hash(item)[:12]}",
                provider_id=binding.provider_id,
                profile_id=binding.profile_id,
                binding_id=str(binding.binding_id or ""),
                kind=CapabilityKind.DATASET,
                name=label,
                description=message,
                implementation_kind=ImplementationKind.CALLABLE,
                execution_owner=binding.execution_owner,
                input_schema_ref="schemas/capability-plane/dataset.preview-selection.json",
                output_schema_ref="schemas/capability-plane/dataset.preview.json",
                side_effect_class=SideEffectClass.read_only,
                risk_level=RiskLevel.low,
                required_policy="policy.governed_data.preview",
                replayability=Replayability.non_replayable,
                approval_required=False,
                trust_tier="customer_preview",
                manifest_hash=manifest_hash,
                artifact_affinities=_dedupe_strings([label]),
                tags=_dedupe_strings(
                    [
                        label,
                        connector_type,
                        *[str(item) for item in selection.values() if item is not None],
                    ]
                ),
                required_binding_ids=[str(binding.binding_id)] if binding.binding_id else [],
                binding_status=binding.status,
                discovered_at=discovered_at,
                customer_metadata={
                    "preview": True,
                    "selection": selection,
                    "connector_type": connector_type,
                },
            )
            capabilities.append(capability)
        return capabilities, {"message": message, "discovery": discovery}, message

    org_id = str(auth["org_id"])
    visible_entries = filter_visible_datasets(sreg.list_sources(org_id), auth)
    manifest_hash = _stable_hash(visible_entries)
    capabilities = [
        _build_dataset_capability(
            binding=binding,
            entry=entry,
            schema_meta=sreg.get_source_meta(org_id, str(entry.get("id") or entry.get("dataset_id") or "")),
            manifest_hash=manifest_hash,
            discovered_at=discovered_at,
        )
        for entry in visible_entries
    ]
    message = f"Discovered {len(capabilities)} governed dataset capabilities."
    return capabilities, {"visible_dataset_count": len(capabilities)}, message


async def _discover_runtime_library_binding(
    binding: ResolvedBindingContext,
) -> tuple[list[CapabilityCatalogEntry], dict[str, Any], str]:
    descriptors = list_public_runtime_library_descriptors()
    health = get_public_runtime_library_health()
    discovered_at = _utc_now()
    manifest_hash = _stable_hash(
        [{"name": descriptor.name, "functions": list(descriptor.functions)} for descriptor in descriptors]
    )
    capabilities: list[CapabilityCatalogEntry] = []
    for descriptor in descriptors:
        for function_name in descriptor.functions:
            capabilities.append(
                _build_runtime_library_capability(
                    binding=binding,
                    module_name=descriptor.name,
                    function_name=function_name,
                    engine=descriptor.engine,
                    manifest_hash=manifest_hash,
                    discovered_at=discovered_at,
                )
            )
    message = f"Discovered {len(capabilities)} runtime-library capabilities."
    return (
        capabilities,
        {
            "runtime_available": health.runtime_available,
            "engine": health.engine,
            "module_count": health.module_count,
        },
        message,
    )


def _discover_manifest_binding(
    binding: ResolvedBindingContext,
) -> tuple[list[CapabilityCatalogEntry], dict[str, Any], str]:
    manifest = binding.config.get("manifest")
    if not isinstance(manifest, dict):
        _raise_error(
            422,
            "manifest_required",
            "Manifest-backed bindings require config.manifest.",
        )
    raw_capabilities = manifest.get("capabilities")
    if not isinstance(raw_capabilities, list):
        _raise_error(
            422,
            "manifest_required",
            "config.manifest.capabilities must be an array.",
        )
    discovered_at = _utc_now()
    manifest_hash = _stable_hash(manifest)
    capabilities = [
        _manifest_capability_entry_to_catalog(
            binding=binding,
            manifest_hash=manifest_hash,
            discovered_at=discovered_at,
            payload=item,
        )
        for item in raw_capabilities
        if isinstance(item, dict)
    ]
    message = f"Discovered {len(capabilities)} manifest-backed capabilities."
    metadata = {
        "capability_count": len(capabilities),
        "provider_type": _provider_type_from_capability_kind(capabilities[0].kind).value
        if capabilities
        else None,
    }
    return capabilities, metadata, message


async def _discover_binding_capabilities(
    db: AsyncSession,
    auth: AuthContext,
    binding: ResolvedBindingContext,
) -> tuple[list[CapabilityCatalogEntry], dict[str, Any], str]:
    if binding.provider_id == DATA_CONNECTOR_PROVIDER_ID:
        return await _discover_data_connector_binding(db, auth, binding)
    if binding.provider_id == RUNTIME_LIBRARY_PROVIDER_ID:
        return await _discover_runtime_library_binding(binding)
    return _discover_manifest_binding(binding)


async def _persist_snapshot(
    db: AsyncSession,
    auth: AuthContext,
    binding: CapabilityBinding,
    *,
    capabilities: list[CapabilityCatalogEntry],
    metadata: dict[str, Any],
) -> CapabilitySnapshot:
    discovered_at = _utc_now()
    manifest = {
        "binding_id": str(binding.id),
        "provider_id": binding.provider_id,
        "profile_id": binding.profile_id,
        "capabilities": [capability.model_dump(mode="json") for capability in capabilities],
    }
    snapshot = CapabilitySnapshot(
        binding_id=binding.id,
        org_id=_auth_org_id(auth),
        manifest_hash=_stable_hash(manifest),
        content_hash=_stable_hash({"manifest": manifest, "metadata": metadata}),
        manifest_json=manifest,
        discovery_metadata_json=metadata,
        discovered_at=discovered_at,
    )
    db.add(snapshot)
    binding.last_discovered_at = discovered_at
    binding.status = BindingStatus.READY if capabilities else BindingStatus.DEGRADED
    binding.discovery_error_message = None if capabilities else "No capabilities discovered."
    await db.flush()
    return snapshot


async def _latest_snapshot_map(
    db: AsyncSession,
    *,
    binding_ids: Sequence[uuid.UUID],
) -> dict[uuid.UUID, CapabilitySnapshot]:
    if not binding_ids:
        return {}
    result = await db.execute(
        select(CapabilitySnapshot)
        .where(CapabilitySnapshot.binding_id.in_(list(binding_ids)))
        .order_by(CapabilitySnapshot.binding_id.asc(), CapabilitySnapshot.discovered_at.desc())
    )
    snapshots: dict[uuid.UUID, CapabilitySnapshot] = {}
    for snapshot in result.scalars():
        snapshots.setdefault(snapshot.binding_id, snapshot)
    return snapshots


def _capabilities_from_snapshot(
    binding: CapabilityBinding,
    snapshot: CapabilitySnapshot,
    *,
    include_instruction: bool = False,
) -> list[CapabilityCatalogEntry]:
    raw_capabilities = snapshot.manifest_json.get("capabilities")
    if not isinstance(raw_capabilities, list):
        return []
    entries: list[CapabilityCatalogEntry] = []
    for item in raw_capabilities:
        if not isinstance(item, dict):
            continue
        payload = dict(item)
        payload["binding_id"] = str(binding.id)
        payload["binding_status"] = binding.status.value
        payload["provider_id"] = binding.provider_id
        payload["profile_id"] = binding.profile_id
        payload["manifest_hash"] = snapshot.manifest_hash
        if not include_instruction:
            payload.pop("instruction_text", None)
        entries.append(CapabilityCatalogEntry.model_validate(payload))
    return entries


async def _refresh_system_binding_snapshot_if_needed(
    db: AsyncSession,
    auth: AuthContext,
    binding: CapabilityBinding,
    snapshot_map: dict[uuid.UUID, CapabilitySnapshot],
) -> None:
    if not binding.system_managed:
        return
    current_snapshot = snapshot_map.get(binding.id)
    if current_snapshot is not None and current_snapshot.discovered_at >= _utc_now() - SYSTEM_BINDING_REFRESH_TTL:
        return
    binding_context = _binding_context_from_model(binding)
    capabilities, metadata, _message = await _discover_binding_capabilities(db, auth, binding_context)
    snapshot = await _persist_snapshot(db, auth, binding, capabilities=capabilities, metadata=metadata)
    snapshot_map[binding.id] = snapshot


async def _catalog_for_org(
    db: AsyncSession,
    auth: AuthContext,
    *,
    include_instruction: bool = False,
) -> list[CapabilityCatalogEntry]:
    org_id = _auth_org_id(auth)
    # Key the catalog cache by workspace too, or workspace A's catalog would leak to B.
    cache_key = (str(org_id), str(auth.get("workspace_id")), include_instruction)
    cached = _catalog_cache.get(cache_key)
    if cached is not None and cached[0] >= _utc_now():
        return list(cached[1])
    await _ensure_system_bindings(db, auth)
    result = await db.execute(
        select(CapabilityBinding)
        .where(*workspace_scope_clauses(CapabilityBinding, auth))
        .order_by(CapabilityBinding.created_at.asc())
    )
    bindings = list(result.scalars())
    snapshot_map = await _latest_snapshot_map(
        db,
        binding_ids=[binding.id for binding in bindings],
    )
    for binding in bindings:
        await _refresh_system_binding_snapshot_if_needed(db, auth, binding, snapshot_map)
    entries: list[CapabilityCatalogEntry] = []
    for binding in bindings:
        snapshot = snapshot_map.get(binding.id)
        if snapshot is None:
            continue
        entries.extend(
            _capabilities_from_snapshot(
                binding,
                snapshot,
                include_instruction=include_instruction,
            )
        )
    _catalog_cache[cache_key] = (_utc_now() + _CATALOG_CACHE_TTL, list(entries))
    return entries


async def _record_routing_outcome(
    db: AsyncSession,
    auth: AuthContext,
    *,
    capability_id: str,
    provider_id: str,
    binding_id: str | None,
    route_request: dict[str, Any] | None,
    route_plan: dict[str, Any] | None,
    result_status: str,
    success: bool | None,
    score: float | None,
    confidence: float | None,
    latency_ms: float | None = None,
    error_code: str | None = None,
    details: dict[str, Any] | None = None,
) -> CapabilityRoutingOutcome:
    outcome = CapabilityRoutingOutcome(
        org_id=_auth_org_id(auth),
        provider_id=provider_id,
        binding_id=uuid.UUID(binding_id) if binding_id else None,
        capability_id=capability_id,
        route_request_json=route_request,
        route_plan_json=route_plan,
        result_status=result_status,
        success=success,
        score=score,
        confidence=confidence,
        latency_ms=latency_ms,
        error_code=error_code,
        outcome_details_json=details,
    )
    db.add(outcome)
    await db.flush()
    return outcome


async def list_capability_providers_service(
    db: AsyncSession,
    auth: AuthContext,
) -> list[CapabilityProviderResponse]:
    await _ensure_system_bindings(db, auth)
    providers_result = await db.execute(
        select(CapabilityProvider).where(CapabilityProvider.active.is_(True)).order_by(CapabilityProvider.name.asc())
    )
    providers = list(providers_result.scalars())
    profiles_result = await db.execute(
        select(CapabilityProviderProfile).order_by(CapabilityProviderProfile.name.asc())
    )
    profiles = list(profiles_result.scalars())
    profiles_by_provider: dict[str, list[CapabilityProviderProfile]] = {}
    for profile in profiles:
        profiles_by_provider.setdefault(profile.provider_id, []).append(profile)
    return [
        _provider_response(provider, profiles=profiles_by_provider.get(provider.provider_id, []))
        for provider in providers
    ]


async def get_capability_provider_service(
    db: AsyncSession,
    auth: AuthContext,
    provider_id: str,
) -> CapabilityProviderResponse:
    await _ensure_system_bindings(db, auth)
    provider = await _require_provider(db, provider_id)
    result = await db.execute(
        select(CapabilityProviderProfile)
        .where(CapabilityProviderProfile.provider_id == provider_id)
        .order_by(CapabilityProviderProfile.name.asc())
    )
    profiles = list(result.scalars())
    return _provider_response(provider, profiles=profiles)


async def list_capability_bindings_service(
    db: AsyncSession,
    auth: AuthContext,
    *,
    provider_id: str | None = None,
    scope: BindingScope | None = None,
) -> list[CapabilityBindingResponse]:
    await _ensure_system_bindings(db, auth)
    stmt = (
        select(CapabilityBinding)
        .where(*workspace_scope_clauses(CapabilityBinding, auth))
        .order_by(CapabilityBinding.created_at.asc())
    )
    if provider_id:
        stmt = stmt.where(CapabilityBinding.provider_id == provider_id)
    if scope is not None:
        stmt = stmt.where(CapabilityBinding.scope == scope)
    result = await db.execute(stmt)
    return [_binding_response(binding) for binding in result.scalars()]


async def create_capability_binding_service(
    db: AsyncSession,
    auth: AuthContext,
    payload: CapabilityBindingCreateRequest,
) -> CapabilityBindingResponse:
    await _ensure_system_bindings(db, auth)
    provider = await _require_provider(db, payload.provider_id)
    profile = await _require_profile(db, payload.profile_id)
    if profile.provider_id != provider.provider_id:
        _raise_error(422, "profile_provider_mismatch", "profile_id does not belong to provider_id.")
    scope_ref = _scope_ref_from_auth(auth, scope=payload.scope, scope_ref=payload.scope_ref)
    binding = CapabilityBinding(
        org_id=_auth_org_id(auth),
        workspace_id=workspace_id_for_write(auth),
        provider_id=provider.provider_id,
        profile_id=profile.profile_id,
        binding_name=payload.binding_name.strip(),
        scope=payload.scope,
        scope_ref=scope_ref,
        status=BindingStatus.UNCONFIGURED,
        execution_owner=payload.execution_owner or profile.default_execution_owner,
        config_json=encrypt_config_dict(
            dict(payload.config or {}), org_id=_auth_org_id(auth)
        ),
        customer_metadata_json=dict(payload.customer_metadata or {}),
        system_managed=False,
    )
    db.add(binding)
    await db.flush()
    _invalidate_catalog_cache()
    return _binding_response(binding)


async def get_capability_binding_service(
    db: AsyncSession,
    auth: AuthContext,
    binding_id: str,
) -> CapabilityBindingResponse:
    binding = await _require_binding(db, auth, binding_id)
    return _binding_response(binding)


async def update_capability_binding_service(
    db: AsyncSession,
    auth: AuthContext,
    binding_id: str,
    payload: CapabilityBindingUpdateRequest,
) -> CapabilityBindingResponse:
    binding = await _require_binding(db, auth, binding_id)
    if binding.system_managed and payload.status is not None:
        _raise_error(
            409,
            "system_binding_read_only",
            "System-managed capability bindings do not allow manual status changes.",
        )
    if payload.binding_name is not None:
        binding.binding_name = payload.binding_name.strip()
    if payload.scope is not None:
        binding.scope = payload.scope
        binding.scope_ref = _scope_ref_from_auth(auth, scope=payload.scope, scope_ref=payload.scope_ref)
    elif payload.scope_ref is not None:
        binding.scope_ref = payload.scope_ref.strip()
    if payload.status is not None:
        binding.status = payload.status
    if payload.execution_owner is not None:
        binding.execution_owner = payload.execution_owner
    if payload.config is not None:
        binding.config_json = encrypt_config_dict(
            dict(payload.config), org_id=getattr(binding, "org_id", "")
        )
    if payload.customer_metadata is not None:
        binding.customer_metadata_json = dict(payload.customer_metadata)
    await db.flush()
    _invalidate_catalog_cache()
    return _binding_response(binding)


async def delete_capability_binding_service(
    db: AsyncSession,
    auth: AuthContext,
    binding_id: str,
) -> None:
    binding = await _require_binding(db, auth, binding_id)
    if binding.system_managed:
        _raise_error(
            409,
            "system_binding_read_only",
            "System-managed capability bindings cannot be deleted.",
        )
    await db.delete(binding)
    await db.flush()
    _invalidate_catalog_cache()


async def _test_binding(
    db: AsyncSession,
    auth: AuthContext,
    binding: ResolvedBindingContext,
) -> CapabilityBindingTestResult:
    if binding.provider_id == DATA_CONNECTOR_PROVIDER_ID:
        connector = await _connector_config_for_binding(db, auth, binding)
        if connector is None:
            return CapabilityBindingTestResult(
                success=True,
                binding_status=BindingStatus.READY,
                message="Using governed dataset inventory bound to the current organization.",
                details={"binding_mode": "governed_inventory"},
            )
        connector_type, connector_config = connector
        outcome = await test_connector_real_detailed(connector_type, connector_config)
        return CapabilityBindingTestResult(
            success=outcome.success,
            binding_status=BindingStatus.READY if outcome.success else BindingStatus.DEGRADED,
            message=outcome.message,
            latency_ms=float(outcome.latency_ms),
            details={
                "status": outcome.status,
                "error_type": outcome.error_type,
                "recoverable": outcome.recoverable,
            },
        )
    if binding.provider_id == RUNTIME_LIBRARY_PROVIDER_ID:
        health = get_public_runtime_library_health()
        success = bool(health.runtime_available)
        return CapabilityBindingTestResult(
            success=success,
            binding_status=BindingStatus.READY if success else BindingStatus.DEGRADED,
            message=(
                "Runtime libraries are available."
                if success
                else "Runtime libraries are currently unavailable."
            ),
            details={
                "engine": health.engine,
                "module_count": health.module_count,
                "runtime_available": health.runtime_available,
            },
        )
    manifest = binding.config.get("manifest")
    if isinstance(manifest, dict) and isinstance(manifest.get("capabilities"), list):
        return CapabilityBindingTestResult(
            success=True,
            binding_status=BindingStatus.READY,
            message="Manifest-backed binding payload is valid.",
            details={"capability_count": len(manifest.get("capabilities") or [])},
        )
    return CapabilityBindingTestResult(
        success=False,
        binding_status=BindingStatus.UNCONFIGURED,
        message="Manifest-backed bindings require config.manifest.capabilities.",
        details={"required_field": "config.manifest.capabilities"},
    )


async def test_capability_binding_preview_service(
    db: AsyncSession,
    auth: AuthContext,
    payload: CapabilityBindingPreviewRequest,
) -> CapabilityBindingTestResult:
    await _ensure_system_bindings(db, auth)
    profile = await _require_profile(db, payload.profile_id)
    if profile.provider_id != payload.provider_id:
        _raise_error(422, "profile_provider_mismatch", "profile_id does not belong to provider_id.")
    preview = _binding_context_from_preview(
        auth=auth,
        payload=payload,
        default_execution_owner=profile.default_execution_owner,
    )
    return await _test_binding(db, auth, preview)


async def test_capability_binding_service(
    db: AsyncSession,
    auth: AuthContext,
    binding_id: str,
) -> CapabilityBindingTestResult:
    binding = await _require_binding(db, auth, binding_id)
    result = await _test_binding(db, auth, _binding_context_from_model(binding))
    binding.last_tested_at = _utc_now()
    binding.status = result.binding_status
    binding.test_error_message = None if result.success else result.message
    await db.flush()
    return result


async def discover_capability_binding_preview_service(
    db: AsyncSession,
    auth: AuthContext,
    payload: CapabilityBindingPreviewRequest,
) -> CapabilityDiscoverResponse:
    await _ensure_system_bindings(db, auth)
    profile = await _require_profile(db, payload.profile_id)
    if profile.provider_id != payload.provider_id:
        _raise_error(422, "profile_provider_mismatch", "profile_id does not belong to provider_id.")
    preview = _binding_context_from_preview(
        auth=auth,
        payload=payload,
        default_execution_owner=profile.default_execution_owner,
    )
    capabilities, metadata, message = await _discover_binding_capabilities(db, auth, preview)
    manifest_hash = _stable_hash([item.model_dump(mode="json") for item in capabilities])
    discovered_at = _utc_now()
    return CapabilityDiscoverResponse(
        provider_id=preview.provider_id,
        profile_id=preview.profile_id,
        binding_status=BindingStatus.READY if capabilities else BindingStatus.DEGRADED,
        manifest_hash=manifest_hash,
        capability_count=len(capabilities),
        discovered_at=discovered_at,
        message=message,
        capabilities=capabilities,
    )


async def discover_capability_binding_service(
    db: AsyncSession,
    auth: AuthContext,
    binding_id: str,
) -> CapabilityDiscoverResponse:
    binding = await _require_binding(db, auth, binding_id)
    binding_context = _binding_context_from_model(binding)
    capabilities, metadata, message = await _discover_binding_capabilities(db, auth, binding_context)
    snapshot = await _persist_snapshot(db, auth, binding, capabilities=capabilities, metadata=metadata)
    return CapabilityDiscoverResponse(
        binding_id=str(binding.id),
        provider_id=binding.provider_id,
        profile_id=binding.profile_id,
        snapshot_id=str(snapshot.id),
        binding_status=binding.status,
        manifest_hash=snapshot.manifest_hash,
        capability_count=len(capabilities),
        discovered_at=snapshot.discovered_at,
        message=message,
        capabilities=capabilities,
    )


async def start_capability_authorization_service(
    db: AsyncSession,
    auth: AuthContext,
    binding_id: str,
    payload: CapabilityAuthorizationStartRequest,
) -> CapabilityAuthorizationStartResponse:
    from apps.api_server.models.capability_plane import CapabilityAuthorizationSession

    binding = await _require_binding(db, auth, binding_id)
    provider = await _require_provider(db, binding.provider_id)
    authorize_url = None
    _binding_config = decrypt_config_dict(
        binding.config_json, org_id=getattr(binding, "org_id", "")
    )
    if isinstance(_binding_config, dict):
        authorize_url = _binding_config.get("authorization_url")
    if not isinstance(authorize_url, str) or not authorize_url.strip():
        install_metadata = provider.install_metadata_json or {}
        authorize_url = install_metadata.get("authorization_url")
    if not isinstance(authorize_url, str) or not authorize_url.strip():
        _raise_error(
            409,
            "authorization_not_supported",
            "This capability binding does not expose an authorization_url.",
        )
    requested_scopes = _dedupe_strings(payload.requested_scopes)
    state_seed = _stable_hash(
        {
            "binding_id": binding_id,
            "redirect_uri": payload.redirect_uri,
            "scopes": requested_scopes,
            "state_payload": payload.state_payload,
            "ts": _utc_now().isoformat(),
        }
    )
    query: dict[str, str] = {"algenta_session_id": state_seed[:24]}
    if payload.redirect_uri:
        query["redirect_uri"] = payload.redirect_uri
    if requested_scopes:
        query["scopes"] = " ".join(requested_scopes)
    auth_url = f"{authorize_url.rstrip('?')}{'&' if '?' in authorize_url else '?'}{urlencode(query)}"
    session = CapabilityAuthorizationSession(
        org_id=_auth_org_id(auth),
        workspace_id=workspace_id_for_write(auth),
        provider_id=binding.provider_id,
        binding_id=binding.id,
        session_state_hash=state_seed,
        authorize_url=auth_url,
        status=AuthorizationSessionStatus.PENDING,
        request_payload_json=payload.model_dump(mode="json"),
        expires_at=_utc_now() + timedelta(minutes=15),
    )
    db.add(session)
    binding.status = BindingStatus.AUTHORIZING
    await db.flush()
    return CapabilityAuthorizationStartResponse(
        session_id=str(session.id),
        binding_id=str(binding.id),
        provider_id=binding.provider_id,
        authorize_url=auth_url,
        expires_at=session.expires_at,
        requested_scopes=requested_scopes,
    )


async def complete_capability_authorization_service(
    db: AsyncSession,
    auth: AuthContext,
    payload: CapabilityAuthorizationCompleteRequest,
) -> CapabilityAuthorizationCompleteResponse:
    from apps.api_server.models.capability_plane import CapabilityAuthorizationSession

    try:
        session_id = uuid.UUID(payload.session_id)
    except ValueError:
        _raise_error(422, "invalid_session_id", "session_id must be a valid UUID.")
    session = await db.get(CapabilityAuthorizationSession, session_id)
    _auth_ws = auth.get("workspace_id")
    if (
        session is None
        or session.org_id != _auth_org_id(auth)
        or (_auth_ws is not None and session.workspace_id != _auth_ws)
    ):
        # Independent workspace gate on the session itself (durable #4): a scoped caller
        # cannot complete a sibling workspace's session even before the binding gate runs.
        _raise_error(404, "authorization_session_not_found", "Authorization session not found.")
    if session.expires_at <= _utc_now():
        # Resolve the binding through the workspace-scoped guard FIRST, so an out-of-scope
        # caller (sibling workspace, same org) gets 404 and cannot DEGRADE another
        # workspace's binding via an expired-session race.
        binding = await _require_binding(db, auth, str(session.binding_id))
        session.status = AuthorizationSessionStatus.EXPIRED
        binding.status = BindingStatus.DEGRADED
        _raise_error(409, "authorization_session_expired", "Authorization session has expired.")
    # SECURITY: _require_binding enforces org_id AND workspace_id (CapabilityAuthorizationSession
    # itself carries no workspace_id, so the binding's workspace gate is the tenancy boundary here).
    binding = await _require_binding(db, auth, str(session.binding_id))
    session.callback_payload_json = payload.model_dump(mode="json")
    session.completed_at = _utc_now()
    session.status = AuthorizationSessionStatus.COMPLETED
    binding.authorized_at = session.completed_at
    binding.status = BindingStatus.READY
    auth_state = dict(
        decrypt_config_dict(binding.auth_state_json, org_id=getattr(binding, "org_id", "")) or {}
    )
    auth_state["authorization_code_present"] = bool(payload.authorization_code)
    auth_state["last_completed_session_id"] = str(session.id)
    binding.auth_state_json = encrypt_config_dict(
        auth_state, org_id=getattr(binding, "org_id", "")
    )
    await db.flush()
    return CapabilityAuthorizationCompleteResponse(
        session_id=str(session.id),
        binding_id=str(binding.id),
        provider_id=binding.provider_id,
        status=session.status,
        authorized_at=binding.authorized_at,
    )


async def list_capabilities_service(
    db: AsyncSession,
    auth: AuthContext,
    *,
    kinds: Sequence[CapabilityKind] | None = None,
    provider_ids: Sequence[str] | None = None,
    binding_ids: Sequence[str] | None = None,
) -> list[CapabilityCatalogEntry]:
    entries = await _catalog_for_org(db, auth, include_instruction=False)
    normalized_binding_ids = set(binding_ids or [])
    normalized_provider_ids = set(provider_ids or [])
    normalized_kinds = set(kinds or [])
    filtered = []
    for entry in entries:
        if normalized_kinds and entry.kind not in normalized_kinds:
            continue
        if normalized_provider_ids and entry.provider_id not in normalized_provider_ids:
            continue
        if normalized_binding_ids and entry.binding_id not in normalized_binding_ids:
            continue
        filtered.append(entry)
    return filtered


async def get_capability_service(
    db: AsyncSession,
    auth: AuthContext,
    capability_id: str,
    *,
    include_instruction: bool = False,
) -> CapabilityCatalogEntry:
    entries = await _catalog_for_org(db, auth, include_instruction=include_instruction)
    for entry in entries:
        if entry.capability_id == capability_id:
            return entry
    _raise_error(404, "capability_not_found", f"Capability '{capability_id}' not found.")


async def _historical_outcome_adjustments(
    db: AsyncSession,
    auth: AuthContext,
) -> dict[str, tuple[int, int]]:
    result = await db.execute(
        select(CapabilityRoutingOutcome)
        .where(CapabilityRoutingOutcome.org_id == _auth_org_id(auth))
        .where(CapabilityRoutingOutcome.success.is_not(None))
    )
    counts: dict[str, tuple[int, int]] = {}
    for outcome in result.scalars():
        success_count, failure_count = counts.get(outcome.capability_id, (0, 0))
        if outcome.success:
            success_count += 1
        else:
            failure_count += 1
        counts[outcome.capability_id] = (success_count, failure_count)
    return counts


def _score_capability(
    capability: CapabilityCatalogEntry,
    *,
    objective: str,
    artifact_affinities: Sequence[str],
    requested_tags: Sequence[str],
    historical_counts: tuple[int, int],
) -> _ScoredCapability:
    objective_tokens = set(_tokenize(objective))
    tag_tokens = set(_tokenize(" ".join(capability.tags)))
    name_tokens = set(_tokenize(capability.name))
    description_tokens = set(_tokenize(capability.description or ""))
    affinity_tokens = set(_tokenize(" ".join(capability.artifact_affinities)))
    overlap = objective_tokens & (tag_tokens | name_tokens | description_tokens | affinity_tokens)
    score = float(len(overlap) * 10)
    reasons: list[str] = []
    if overlap:
        reasons.append(f"token overlap: {', '.join(sorted(overlap)[:6])}")
    if capability.binding_status is BindingStatus.READY:
        score += 15
        reasons.append("binding ready")
    elif capability.binding_status is BindingStatus.DEGRADED:
        score -= 10
        reasons.append("binding degraded")
    elif capability.binding_status is BindingStatus.QUARANTINED:
        score -= 50
        reasons.append("binding quarantined")
    if any(tag in capability.tags for tag in requested_tags):
        score += 8
        reasons.append("requested tag match")
    if any(affinity in capability.artifact_affinities for affinity in artifact_affinities):
        score += 8
        reasons.append("artifact affinity match")
    success_count, failure_count = historical_counts
    score += float(success_count * 2)
    score -= float(failure_count * 3)
    if success_count or failure_count:
        reasons.append(f"historical outcomes: +{success_count}/-{failure_count}")
    if capability.approval_required:
        score -= 2
        reasons.append("approval required")
    confidence = max(0.05, min(0.99, score / 100.0))
    return _ScoredCapability(
        capability=capability,
        score=confidence,
        reason="; ".join(reasons) if reasons else "default catalog ranking",
    )


async def route_capabilities_service(
    db: AsyncSession,
    auth: AuthContext,
    payload: CapabilityRouteRequest,
) -> CapabilityRoutePlan:
    entries = await _catalog_for_org(db, auth, include_instruction=False)
    filtered = []
    binding_ids = set(payload.binding_ids)
    provider_ids = set(payload.provider_ids)
    kinds = set(payload.kinds)
    execution_owners = set(payload.execution_owners)
    for entry in entries:
        if binding_ids and entry.binding_id not in binding_ids:
            continue
        if provider_ids and entry.provider_id not in provider_ids:
            continue
        if kinds and entry.kind not in kinds:
            continue
        if execution_owners and entry.execution_owner not in execution_owners:
            continue
        if entry.binding_status is BindingStatus.QUARANTINED:
            continue
        filtered.append(entry)
    if not filtered:
        _raise_error(
            404,
            "capability_route_not_found",
            "No capabilities matched the requested route filters.",
        )
    historical = await _historical_outcome_adjustments(db, auth)
    scored = sorted(
        (
            _score_capability(
                entry,
                objective=payload.objective,
                artifact_affinities=payload.artifact_affinities,
                requested_tags=payload.tags,
                historical_counts=historical.get(entry.capability_id, (0, 0)),
            )
            for entry in filtered
        ),
        key=lambda item: (item.score, item.capability.name),
        reverse=True,
    )
    selected = scored[0]
    fallbacks = [
        CapabilityRouteFallback(
            capability_id=item.capability.capability_id,
            provider_id=item.capability.provider_id,
            binding_id=item.capability.binding_id,
            kind=item.capability.kind,
            execution_owner=item.capability.execution_owner,
            confidence=round(item.score, 4),
            reason=item.reason,
            selected_tool_name=item.capability.selected_tool_name,
            instruction_artifact_ref=item.capability.instruction_artifact_ref,
        )
        for item in scored[1 : 1 + payload.max_fallbacks]
    ]
    route_plan = CapabilityRoutePlan(
        selected_capability_id=selected.capability.capability_id,
        selected_provider_id=selected.capability.provider_id,
        selected_binding_id=selected.capability.binding_id,
        kind=selected.capability.kind,
        execution_owner=selected.capability.execution_owner,
        requires_approval=selected.capability.approval_required,
        confidence=round(selected.score, 4),
        reason=selected.reason,
        fallbacks=fallbacks,
        policy_snapshot_id=POLICY_SNAPSHOT_ID,
        selected_tool_name=selected.capability.selected_tool_name,
        instruction_artifact_ref=selected.capability.instruction_artifact_ref,
    )
    await _record_routing_outcome(
        db,
        auth,
        capability_id=selected.capability.capability_id,
        provider_id=selected.capability.provider_id,
        binding_id=selected.capability.binding_id,
        route_request=payload.model_dump(mode="json"),
        route_plan=route_plan.model_dump(mode="json"),
        result_status="routed",
        success=None,
        score=selected.score,
        confidence=selected.score,
    )
    return route_plan


async def _create_execution_session(
    db: AsyncSession,
    auth: AuthContext,
    capability: CapabilityCatalogEntry,
    request: CapabilityExecutionRequest,
) -> CapabilityExecutionSession:
    session = CapabilityExecutionSession(
        org_id=_auth_org_id(auth),
        provider_id=capability.provider_id,
        binding_id=uuid.UUID(capability.binding_id),
        capability_id=capability.capability_id,
        execution_owner=capability.execution_owner,
        status=ExecutionSessionStatus.STARTED,
        request_id=request.request_id,
        request_payload_json=request.model_dump(mode="json"),
        started_at=_utc_now(),
    )
    db.add(session)
    await db.flush()
    return session


async def _complete_execution_session(
    db: AsyncSession,
    auth: AuthContext,
    *,
    session: CapabilityExecutionSession,
    capability: CapabilityCatalogEntry,
    status: ExecutionSessionStatus,
    output: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> CapabilityExecutionResponse:
    session.status = status
    session.success = status is ExecutionSessionStatus.SUCCEEDED
    session.error_code = error.get("code") if isinstance(error, dict) else None
    session.response_payload_json = {"output": output, "error": error}
    session.completed_at = _utc_now()
    await db.flush()
    await _record_routing_outcome(
        db,
        auth,
        capability_id=capability.capability_id,
        provider_id=capability.provider_id,
        binding_id=capability.binding_id,
        route_request=None,
        route_plan=None,
        result_status="succeeded" if session.success else "failed",
        success=session.success,
        score=None,
        confidence=None,
        error_code=session.error_code,
        details=error or output,
    )
    return CapabilityExecutionResponse(
        execution_session_id=str(session.id),
        capability_id=capability.capability_id,
        provider_id=capability.provider_id,
        binding_id=capability.binding_id,
        execution_owner=capability.execution_owner,
        status=status,
        output=output,
        error=error,
        started_at=session.started_at,
        completed_at=session.completed_at,
    )


async def execute_capability_service(
    db: AsyncSession,
    auth: AuthContext,
    payload: CapabilityExecutionRequest,
) -> CapabilityExecutionResponse:
    capability = await get_capability_service(
        db,
        auth,
        payload.capability_id,
        include_instruction=True,
    )
    if payload.binding_id and payload.binding_id != capability.binding_id:
        _raise_error(
            409,
            "binding_mismatch",
            "binding_id does not match the selected capability binding.",
        )
    session = await _create_execution_session(db, auth, capability, payload)
    request_input = dict(payload.input or {})
    if capability.execution_owner is ExecutionOwner.CLIENT_MANAGED:
        return await _complete_execution_session(
            db,
            auth,
            session=session,
            capability=capability,
            status=ExecutionSessionStatus.FAILED,
            error={
                "code": "client_managed_capability_requires_adapter",
                "message": (
                    "This capability is marked client_managed and must execute through "
                    "a customer-provided adapter."
                ),
            },
        )
    if capability.kind is CapabilityKind.DATASET:
        dataset_id = (
            capability.customer_metadata.get("dataset_id")
            if isinstance(capability.customer_metadata, dict)
            else None
        )
        if not isinstance(dataset_id, str) or not dataset_id:
            return await _complete_execution_session(
                db,
                auth,
                session=session,
                capability=capability,
                status=ExecutionSessionStatus.FAILED,
                error={
                    "code": "preview_capability_not_executable",
                    "message": "Preview dataset capabilities cannot execute directly.",
                },
            )
        operation = str(request_input.get("operation") or "summary").strip().lower()
        if operation not in {"summary", "schema"}:
            return await _complete_execution_session(
                db,
                auth,
                session=session,
                capability=capability,
                status=ExecutionSessionStatus.FAILED,
                error={
                    "code": "dataset_execution_requires_governed_query_path",
                    "message": (
                        "Dataset capabilities currently execute via summary/schema only. "
                        "Use the governed query path for query execution."
                    ),
                },
            )
        org_id = str(auth["org_id"])
        entry = get_visible_dataset_entry(org_id, dataset_id, auth)
        if entry is None:
            return await _complete_execution_session(
                db,
                auth,
                session=session,
                capability=capability,
                status=ExecutionSessionStatus.FAILED,
                error={
                    "code": "dataset_not_found",
                    "message": f"Dataset '{dataset_id}' is no longer visible.",
                },
            )
        schema_meta = sreg.get_source_meta(org_id, dataset_id)
        output = {"dataset": entry, "schema": schema_meta} if operation == "schema" else {
            "dataset_id": dataset_id,
            "summary": {
                "dataset_id": dataset_id,
                "name": capability.name,
                "source_names": entry.get("source_names") or [],
                "row_count": schema_meta.get("row_count") if isinstance(schema_meta, dict) else None,
                "column_count": len(schema_meta.get("columns") or [])
                if isinstance(schema_meta, dict)
                else None,
                "query_hints": (schema_meta.get("query_hints") or [])[:10]
                if isinstance(schema_meta, dict)
                else [],
            },
        }
        return await _complete_execution_session(
            db,
            auth,
            session=session,
            capability=capability,
            status=ExecutionSessionStatus.SUCCEEDED,
            output=output,
        )
    if capability.kind is CapabilityKind.RUNTIME_LIBRARY:
        metadata = capability.customer_metadata or {}
        module = metadata.get("module")
        function = metadata.get("function")
        if not isinstance(module, str) or not isinstance(function, str):
            return await _complete_execution_session(
                db,
                auth,
                session=session,
                capability=capability,
                status=ExecutionSessionStatus.FAILED,
                error={
                    "code": "runtime_library_metadata_missing",
                    "message": "Runtime-library capability metadata is incomplete.",
                },
            )
        execution = await execute_public_runtime_library(
            module=module,
            function=function,
            args=request_input.get("args"),
            request_id=payload.request_id,
        )
        return await _complete_execution_session(
            db,
            auth,
            session=session,
            capability=capability,
            status=ExecutionSessionStatus.SUCCEEDED,
            output={
                "module": execution.module,
                "function": execution.function,
                "result": execution.result,
                "latency_ms": execution.latency_ms,
                "engine_used": execution.engine_used,
                "request_id": execution.request_id,
            },
        )
    if capability.kind in {CapabilityKind.SKILL, CapabilityKind.MCP_PROMPT, CapabilityKind.MCP_RESOURCE}:
        payload_output: dict[str, Any] = {
            "instruction_artifact_ref": capability.instruction_artifact_ref,
            "instruction_text": capability.instruction_text,
            "capability_id": capability.capability_id,
        }
        return await _complete_execution_session(
            db,
            auth,
            session=session,
            capability=capability,
            status=ExecutionSessionStatus.SUCCEEDED,
            output=payload_output,
        )
    return await _complete_execution_session(
        db,
        auth,
        session=session,
        capability=capability,
        status=ExecutionSessionStatus.FAILED,
        error={
            "code": "algenta_managed_capability_not_executable",
            "message": (
                "This capability type does not yet have an Algenta-managed execution path. "
                "Use routeCapabilities() plus the customer execution node."
            ),
        },
    )


async def record_capability_outcome_service(
    db: AsyncSession,
    auth: AuthContext,
    payload: CapabilityOutcomeRecordRequest,
) -> CapabilityOutcomeRecord:
    outcome = await _record_routing_outcome(
        db,
        auth,
        capability_id=payload.capability_id,
        provider_id=payload.provider_id,
        binding_id=payload.binding_id,
        route_request=None,
        route_plan=None,
        result_status=payload.result_status,
        success=payload.success,
        score=payload.confidence,
        confidence=payload.confidence,
        latency_ms=payload.latency_ms,
        error_code=payload.error_code,
        details=payload.details,
    )
    return CapabilityOutcomeRecord(
        outcome_id=str(outcome.id),
        capability_id=payload.capability_id,
        provider_id=payload.provider_id,
        binding_id=payload.binding_id,
        success=payload.success,
        result_status=payload.result_status,
        confidence=payload.confidence,
        latency_ms=payload.latency_ms,
        error_code=payload.error_code,
        details=payload.details,
        created_at=outcome.created_at,
    )


async def enable_skill_service(
    db: AsyncSession,
    auth: AuthContext,
    payload: SkillEnableRequest,
) -> CapabilityDiscoverResponse:
    binding = await create_capability_binding_service(
        db,
        auth,
        CapabilityBindingCreateRequest(
            provider_id=SKILL_PACK_PROVIDER_ID,
            profile_id=SKILL_PACK_PROFILE_ID,
            binding_name=payload.skill_name,
            scope=BindingScope.USER,
            execution_owner=payload.execution_owner,
            config={
                "manifest": {
                    "capabilities": [
                        {
                            "capability_id": f"cap.skill.{payload.skill_name.lower().replace(' ', '_')}",
                            "name": payload.skill_name,
                            "description": payload.description,
                            "kind": CapabilityKind.SKILL.value,
                            "implementation_kind": ImplementationKind.INSTRUCTION_ONLY.value,
                            "execution_owner": payload.execution_owner.value,
                            "instruction": payload.instruction,
                            "artifact_affinities": payload.artifact_affinities,
                            "tags": payload.tags,
                            "replayability": Replayability.deterministic.value,
                        }
                    ]
                }
            },
        ),
    )
    return await discover_capability_binding_service(db, auth, binding.binding_id)
