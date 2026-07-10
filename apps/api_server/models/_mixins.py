"""Shared column mixins for decision-engine models."""

from __future__ import annotations

import uuid

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class OrgWorkspaceScopedMixin:
    """org_id + optional workspace_id — the sub-tenancy scoping used across the platform.

    No FK to ``organizations`` (the auth layer enforces org isolation; avoids requiring an
    org row in tests). ``workspace_id`` is the platform-key ``X-Workspace-Id`` sub-tenant
    scope; NULL means org-wide. Both are indexed for scoped queries.
    """

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
