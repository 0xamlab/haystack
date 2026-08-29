"""OidcPrincipalMapping — validated generic-OIDC identities → engine org/workspace.

The workspace an OIDC caller acts in is DERIVED from this mapping (provisioned by an org
admin), never taken from a header or the request body. Fail-closed: an unmapped principal
is rejected (403), and ``status='revoked'`` cuts access without deleting the audit trail.

Keyed by (issuer, subject) rather than Entra's (tenant_id, principal_oid): a generic OIDC
deployment's issuer URL already encodes the full tenant/realm identity (Keycloak's issuer is
literally ``{server}/realms/{realm}``), so there is no separate tenant dimension to key on —
the issuer itself is that dimension, and it is real column here (not assumed constant the way
a single-tenant table might) so one engine could, in principle, accept mappings from more than
one configured issuer over its lifetime without a schema change.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin
from apps.api_server.models._mixins import OrgWorkspaceScopedMixin


class OidcPrincipalMapping(UUIDMixin, TimestampMixin, OrgWorkspaceScopedMixin, Base):
    """One validated generic-OIDC principal (user or app) allowed into an org/workspace."""

    __tablename__ = "oidc_principal_mappings"
    __table_args__ = (
        # One mapping per principal per issuer — the resolver's O(1) lookup key.
        Index(
            "uq_oidc_principal_issuer_subject",
            "issuer",
            "subject",
            unique=True,
        ),
    )

    issuer: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    principal_type: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        default="user",
        server_default="user",
        doc="user | app (client-credentials / service token)",
    )
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="member",
        server_default="member",
        doc="owner | admin | member | viewer",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        server_default="active",
        index=True,
        doc="active | revoked",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, doc="Admin user who provisioned the mapping"
    )

    def __repr__(self) -> str:
        return (
            f"<OidcPrincipalMapping {self.issuer}:{self.subject} "
            f"org={self.org_id} status={self.status}>"
        )
