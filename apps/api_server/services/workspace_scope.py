"""Workspace sub-tenancy scope helpers.

A PLATFORM key (e.g. Mission's company key) may set ``auth["workspace_id"]`` via the
X-Workspace-Id header to act on a specific workspace within its org. When set,
queries/creates are partitioned by ``(org_id, workspace_id)``; when ``None`` (org-wide
platform calls, or pre-migration rows), only ``org_id`` applies — preserving existing
behavior. Tenant keys can never set workspace_id (rejected at the auth layer), so this
is safe to apply uniformly across every org-scoped resource.
"""

from __future__ import annotations

import uuid
from typing import Any

from apps.api_server.services.auth_service import AuthContext


def workspace_id_for_write(auth: AuthContext) -> uuid.UUID | None:
    """The workspace_id to stamp on a newly-created row (None = org-wide)."""
    return auth.get("workspace_id")


def workspace_scope_clauses(model: Any, auth: AuthContext) -> list:
    """SQLAlchemy filter clauses scoping a query to the caller's org + workspace.

    Always filters by org_id; adds workspace_id only when the request carries one.
    """
    clauses = [model.org_id == auth["org_id"]]
    workspace_id = auth.get("workspace_id")
    if workspace_id is not None:
        clauses.append(model.workspace_id == workspace_id)
    return clauses
