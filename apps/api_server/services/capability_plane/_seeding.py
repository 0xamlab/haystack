"""ensure_capability_plane_seeded + _ensure_system_binding(s) + _require_*.

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
from apps.api_server.services.capability_plane._models import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._models import (
    _ScoredCapability,
)
from apps.api_server.services.capability_plane._response_builders import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._response_builders import (
    _binding_response,
    _provider_profile_response,
    _provider_response,
)
from apps.api_server.services.capability_plane._capability_builders import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._capability_builders import (
    _dataset_tags,
    _dataset_artifact_affinities,
    _build_dataset_capability,
    _build_runtime_library_capability,
    _provider_type_from_capability_kind,
    _manifest_capability_kind_allowed,
    _manifest_capability_entry_to_catalog,
    _ensure_org_exists,
)


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

