"""CapabilityPlaneModel + small helpers + ResolvedBindingContext.

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

