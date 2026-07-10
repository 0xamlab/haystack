"""Resolve a verified Entra principal to its engine org/workspace AuthContext.

The chain is: bearer → :func:`entra_auth.verify_entra_token` (audience/issuer/tenant/client
validated) → THIS resolver (mapping lookup + org status) → AuthContext. The workspace is
**derived** from the provisioned mapping — an Entra caller can never select a workspace via
``X-Workspace-Id`` (``is_platform=False`` makes the middleware reject that header).

Fail-closed: unmapped or revoked principals are rejected (403 ``principal_not_mapped``);
a missing/suspended org fails exactly like any other credential.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.models.entra_principal import EntraPrincipalMapping
from apps.api_server.models.organization import Organization
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.entra_auth import EntraAuthError, EntraPrincipal

logger = structlog.get_logger(__name__)

__all__ = ["resolve_entra_principal"]


async def resolve_entra_principal(principal: EntraPrincipal, db: AsyncSession) -> AuthContext:
    """Map a verified principal to an AuthContext, or raise :class:`EntraAuthError`."""

    row = (
        await db.execute(
            select(EntraPrincipalMapping).where(
                EntraPrincipalMapping.tenant_id == principal.tenant_id,
                EntraPrincipalMapping.principal_oid == principal.oid,
            )
        )
    ).scalar_one_or_none()
    if row is None or row.status != "active":
        # Same error for "unknown" and "revoked" — do not leak which principals exist.
        raise EntraAuthError(
            "principal_not_mapped",
            "This identity is not provisioned on this gateway. Ask an administrator to map it.",
        )

    org = (
        await db.execute(select(Organization).where(Organization.id == row.org_id))
    ).scalar_one_or_none()
    if org is None:
        raise EntraAuthError("principal_not_mapped", "The mapped organization no longer exists.")

    plan = getattr(getattr(org, "plan", None), "value", None) or str(getattr(org, "plan", "free"))
    org_status = getattr(getattr(org, "status", None), "value", None) or str(
        getattr(org, "status", "active")
    )

    logger.debug(
        "entra_principal_resolved",
        principal=principal.principal_ref,
        org_id=str(row.org_id),
        workspace_id=str(row.workspace_id) if row.workspace_id else None,
    )
    return AuthContext(
        org_id=row.org_id,
        # No api_keys row backs an Entra identity. key_id stays None so writers stamp NULL into
        # the nullable api_key_id FK columns (never a dangling FK), and key-anchored endpoints
        # can detect a keyless identity instead of 500-ing on a missing lookup.
        key_id=None,
        key_prefix="entra",
        user_id=None,
        plan=plan,
        device_limit=0,
        device_limit_configured=False,
        role=row.role,
        email=principal.preferred_username or row.email or principal.principal_ref,
        is_platform=False,  # an Entra caller may NEVER assume X-Workspace-Id
        # NOT a service credential: is_service carries a repo-specific allowance (org-wide
        # connector READ) meant for the agent's engine-callback key. An Entra principal's
        # permissions come from its provisioned mapping role, never from is_service.
        is_service=False,
        workspace_id=row.workspace_id,  # derived from the mapping, not the request
        org_status=org_status,
        user_status="active",
        email_verified=True,  # Entra identities are org-managed and pre-verified
    )
