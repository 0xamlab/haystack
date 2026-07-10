"""EntraPrincipalMapping — validated Entra identities → engine org/workspace.

The workspace an Entra caller acts in is DERIVED from this mapping (provisioned by an org
admin), never taken from a header or the request body. Fail-closed: an unmapped principal
is rejected (403), and ``status='revoked'`` cuts access without deleting the audit trail.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin
from apps.api_server.models._mixins import OrgWorkspaceScopedMixin


class EntraPrincipalMapping(UUIDMixin, TimestampMixin, OrgWorkspaceScopedMixin, Base):
    """One validated Entra principal (user or app) allowed into an org/workspace."""

    __tablename__ = "entra_principal_mappings"
    __table_args__ = (
        # One mapping per principal per tenant — the resolver's O(1) lookup key.
        Index(
            "uq_entra_principal_tenant_oid",
            "tenant_id",
            "principal_oid",
            unique=True,
        ),
    )

    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    principal_oid: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    principal_type: Mapped[str] = mapped_column(
        String(8), nullable=False, default="user", doc="user | app (service/managed identity)"
    )
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="member", doc="owner | admin | member | viewer"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", index=True, doc="active | revoked"
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, doc="Admin user who provisioned the mapping"
    )

    def __repr__(self) -> str:
        return (
            f"<EntraPrincipalMapping {self.tenant_id}:{self.principal_oid} "
            f"org={self.org_id} status={self.status}>"
        )
