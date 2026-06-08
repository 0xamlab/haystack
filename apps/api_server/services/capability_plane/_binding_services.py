"""Catalog/routing outcome helpers + list/get/create/update/delete/test/discover binding services.

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
from apps.api_server.services.capability_plane._seeding import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._seeding import (
    _ensure_system_binding,
    _ensure_system_bindings,
    _require_provider,
    _require_profile,
    _require_binding,
)
from apps.api_server.services.capability_plane._discovery import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._discovery import (
    _binding_context_from_model,
    _binding_context_from_preview,
    _connector_config_for_binding,
    _discover_data_connector_binding,
    _discover_runtime_library_binding,
    _discover_manifest_binding,
    _discover_binding_capabilities,
    _persist_snapshot,
    _latest_snapshot_map,
    _capabilities_from_snapshot,
    _refresh_system_binding_snapshot_if_needed,
)


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


