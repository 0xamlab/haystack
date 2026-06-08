"""start/complete capability authorization services.

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
from apps.api_server.services.capability_plane._binding_services import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._binding_services import (
    _catalog_for_org,
    _record_routing_outcome,
    _test_binding,
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

