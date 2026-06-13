"""Visibility and ownership helpers for high-level data connections."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.error_payloads import access_scope_denied_error
from apps.api_server.models.data_connector import ConnectorType, ConnectorVisibility, DataConnector
from apps.api_server.services import source_registry as sreg
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.workspace_scope import workspace_scope_clauses

_ADMIN_ROLES = {"admin", "owner"}

# A service key (the agent's engine-callback key, is_service) gets a narrow visibility allowance
# over REPOSITORY connectors only — never data-source connectors (S3/postgres/… with credentials).
# Strictly org-bounded (see _service_can_read_connector), so a leaked service key can read only its
# own org's repos, the exact thing the agent operates on during a run.
# All repository connector kinds (incl. local_repo / repo_archive — the self-hosted agent path).
# Kept in lockstep with services.repository_intelligence_repository_source.REPOSITORY_CONNECTOR_TYPES
# via a drift-guard test (test_service_key_visibility) rather than importing that heavier module here.
_REPO_CONNECTOR_TYPES = frozenset(
    {
        ConnectorType.GITHUB_REPO.value,
        ConnectorType.GITLAB_REPO.value,
        ConnectorType.BITBUCKET_REPO.value,
        ConnectorType.LOCAL_REPO.value,
        ConnectorType.REPO_ARCHIVE.value,
    }
)


def _service_can_read_connector(connector: DataConnector, auth: AuthContext) -> bool:
    """An is_service key may READ (not manage) a REPOSITORY connector that belongs to its OWN org.

    Defense-in-depth: even though every connector query already filters by org_id
    (workspace_scope_clauses), we re-check org_id == auth.org_id here so the allowance can never
    grant cross-org access regardless of how the caller obtained the connector object."""
    if not auth.get("is_service"):
        return False
    connector_type = str(getattr(connector, "connector_type", "") or "")
    if connector_type not in _REPO_CONNECTOR_TYPES:
        return False
    connector_org = getattr(connector, "org_id", None)
    auth_org = auth.get("org_id")
    return connector_org is not None and auth_org is not None and str(connector_org) == str(auth_org)


def auth_user_id(auth: AuthContext) -> str | None:
    user_id = auth.get("user_id")
    return str(user_id) if user_id else None


def auth_key_id(auth: AuthContext) -> str | None:
    key_id = auth.get("key_id")
    return str(key_id) if key_id else None


def can_share(auth: AuthContext) -> bool:
    return str(auth.get("role", "member")).lower() in _ADMIN_ROLES


def normalize_visibility(requested: str | None, auth: AuthContext) -> str:
    visibility = (requested or ConnectorVisibility.PRIVATE.value).strip().lower()
    if visibility not in {
        ConnectorVisibility.PRIVATE.value,
        ConnectorVisibility.SHARED.value,
    }:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "invalid_visibility",
                    "message": "visibility must be private or shared.",
                }
            },
        )
    if visibility == ConnectorVisibility.SHARED.value and not can_share(auth):
        raise HTTPException(
            status_code=403,
            detail=access_scope_denied_error(
                "Shared connections and datasets require admin or owner role.",
                details=[{"field": "visibility", "issue": "shared_requires_admin"}],
            ),
        )
    return visibility


def private_visible(owner_user_id: str | None, owner_key_id: str | None, auth: AuthContext) -> bool:
    user_id = auth_user_id(auth)
    key_id = auth_key_id(auth)
    if owner_user_id and user_id and owner_user_id == user_id:
        return True
    if owner_key_id and key_id and owner_key_id == key_id:
        return True
    return False


def connector_visible(connector: DataConnector, auth: AuthContext) -> bool:
    visibility = str(
        getattr(connector, "visibility", ConnectorVisibility.PRIVATE.value)
        or ConnectorVisibility.PRIVATE.value
    )
    if visibility == ConnectorVisibility.SHARED.value:
        return True
    # Org-internal service key: may READ its own org's repository connectors without owning them.
    if _service_can_read_connector(connector, auth):
        return True
    owner_user_id = (
        str(connector.owner_user_id) if getattr(connector, "owner_user_id", None) else None
    )
    owner_key_id = str(connector.owner_key_id) if getattr(connector, "owner_key_id", None) else None
    return private_visible(owner_user_id, owner_key_id, auth)


def connector_manageable(connector: DataConnector, auth: AuthContext) -> bool:
    # Service keys are read/simulate-only: the repo-connector allowance grants visibility, never
    # management. (The forced `viewer` role already fails role-gated mutations; this is belt-and-
    # suspenders so a service key can never reach connector_manageable=True via the visibility path.)
    if auth.get("is_service"):
        return False
    visibility = str(
        getattr(connector, "visibility", ConnectorVisibility.PRIVATE.value)
        or ConnectorVisibility.PRIVATE.value
    )
    if visibility == ConnectorVisibility.SHARED.value:
        return can_share(auth)
    return connector_visible(connector, auth)


def dataset_in_workspace_scope(entry: dict[str, Any], auth: AuthContext) -> bool:
    """Workspace gate for on-disk dataset entries — the disk mirror of
    workspace_scope_clauses (the DataConnector query filter). A None auth workspace_id
    (unscoped platform call, or a pre-sub-tenancy key) sees all org entries; a
    workspace-scoped caller sees only entries whose workspace_id matches. Legacy entries
    with no workspace_id are invisible to scoped callers, so pre-migration datasets never
    leak across a platform key's workspaces."""
    ws = auth.get("workspace_id")
    if ws is None:
        return True
    entry_ws = entry.get("workspace_id")
    # str-coerce BOTH sides: auth["workspace_id"] is a uuid.UUID, the entry stores the str
    # form — a raw UUID-vs-str compare is always False and would hide every dataset.
    return entry_ws is not None and str(entry_ws) == str(ws)


def dataset_visible(entry: dict[str, Any], auth: AuthContext) -> bool:
    # Workspace gate runs FIRST — even a SHARED dataset is confined to its workspace for a
    # scoped caller, mirroring how list_visible_connectors filters by workspace before visibility.
    if not dataset_in_workspace_scope(entry, auth):
        return False
    visibility = str(entry.get("visibility") or ConnectorVisibility.PRIVATE.value)
    if visibility == ConnectorVisibility.SHARED.value:
        return True
    return private_visible(entry.get("owner_user_id"), entry.get("owner_key_id"), auth)


def dataset_manageable(entry: dict[str, Any], auth: AuthContext) -> bool:
    if not dataset_in_workspace_scope(entry, auth):
        return False
    visibility = str(entry.get("visibility") or ConnectorVisibility.PRIVATE.value)
    if visibility == ConnectorVisibility.SHARED.value:
        return can_share(auth)
    return dataset_visible(entry, auth)


def filter_visible_datasets(
    entries: list[dict[str, Any]],
    auth: AuthContext,
) -> list[dict[str, Any]]:
    return [entry for entry in entries if dataset_visible(entry, auth)]


def visibility_hash(entries: list[dict[str, Any]]) -> str:
    payload = [
        {
            "id": entry.get("id", ""),
            "registered_at": entry.get("registered_at", ""),
            "visibility": entry.get("visibility", ""),
        }
        for entry in sorted(entries, key=lambda item: item.get("id", ""))
    ]
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def get_visible_dataset_entry(
    org_id: str,
    dataset_id: str,
    auth: AuthContext,
) -> dict[str, Any] | None:
    entry = sreg.get_source_entry(org_id, dataset_id)
    if entry is None:
        return None
    if not dataset_visible(entry, auth):
        return None
    return entry


def get_visible_source_entry_by_name(
    org_id: str,
    source_name: str,
    auth: AuthContext,
) -> dict[str, Any] | None:
    """Visibility/workspace-gated by-name lookup. Several query paths resolve a dataset
    by name via sreg.get_source_entry_by_name WITHOUT a visibility check — a cross-tenant
    leak. Route those through here so an out-of-scope name resolves to None."""
    entry = sreg.get_source_entry_by_name(org_id, source_name)
    if entry is None or not dataset_visible(entry, auth):
        return None
    return entry


async def list_visible_connectors(db: AsyncSession, auth: AuthContext) -> list[DataConnector]:
    result = await db.execute(
        select(DataConnector)
        .where(*workspace_scope_clauses(DataConnector, auth))
        .order_by(desc(DataConnector.created_at))
    )
    return [connector for connector in result.scalars().all() if connector_visible(connector, auth)]


async def get_visible_connector(
    db: AsyncSession,
    connector_id: uuid.UUID,
    auth: AuthContext,
) -> DataConnector:
    result = await db.execute(
        select(DataConnector).where(
            DataConnector.id == connector_id,
            *workspace_scope_clauses(DataConnector, auth),
        )
    )
    connector = result.scalar_one_or_none()
    if connector is None or not connector_visible(connector, auth):
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": "Connection not found."}},
        )
    return connector
