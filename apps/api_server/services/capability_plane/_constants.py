"""Module-level cache state + provider/profile constants + DEFAULT_*_SPECS.

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


