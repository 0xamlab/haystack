"""Resolve a verified generic-OIDC principal to its engine org/workspace AuthContext.

The chain is: bearer → :func:`oidc_auth.verify_oidc_token` (audience/issuer/client validated)
→ THIS resolver (mapping lookup + org status) → AuthContext. The workspace is **derived**
from the provisioned mapping — an OIDC caller can never select a workspace via
``X-Workspace-Id`` (``is_platform=False`` makes the middleware reject that header).

Fail-closed: unmapped or revoked principals are rejected (403 ``principal_not_mapped``);
a missing/suspended org fails exactly like any other credential.
"""

from __future__ import annotations

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.config import get_settings
from apps.api_server.models.oidc_principal import OidcPrincipalMapping
from apps.api_server.models.organization import Organization, OrgPlan, OrgStatus
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.oidc_auth import OidcAuthError, OidcPrincipal

logger = structlog.get_logger(__name__)

__all__ = ["resolve_oidc_principal"]

# Multi-seat / shared subscriptions: a new principal joins one of these (up to its seat count)
# instead of getting a personal org. Individual plans (free/pro) are always per-user. Mirrors
# entra_org_resolver.py's identical policy.
_SHARED_PLANS = (OrgPlan.ALGENTA_TEAM, OrgPlan.TEAM, OrgPlan.ENTERPRISE)


async def _issuer_shared_org(principal: OidcPrincipal, db: AsyncSession) -> Organization | None:
    """The issuer's shared (Team/Enterprise) org, if one exists and has a free seat."""
    org = (
        await db.execute(
            select(Organization)
            .join(OidcPrincipalMapping, OidcPrincipalMapping.org_id == Organization.id)
            .where(
                OidcPrincipalMapping.issuer == principal.issuer,
                OidcPrincipalMapping.status == "active",
                Organization.plan.in_(_SHARED_PLANS),
                Organization.status == OrgStatus.ACTIVE,
            )
            .limit(1)
        )
    ).scalars().first()
    if org is None:
        return None
    seats = int(getattr(org, "seats", 1) or 1)
    if seats <= 0:  # 0 = unlimited (enterprise)
        return org
    used = (
        await db.execute(
            select(func.count(OidcPrincipalMapping.id)).where(
                OidcPrincipalMapping.org_id == org.id,
                OidcPrincipalMapping.status == "active",
            )
        )
    ).scalar_one()
    return org if used < seats else None


async def _find_or_create_user_org(principal: OidcPrincipal, db: AsyncSession) -> Organization:
    """This principal's own individual org (Community/free). One per (issuer, subject), race-safe."""
    slug = f"oidc-user-{abs(hash((principal.issuer, principal.subject)))}"[:100]
    org = (
        await db.execute(select(Organization).where(Organization.slug == slug))
    ).scalar_one_or_none()
    if org is not None:
        return org
    label = principal.preferred_username or principal.name or principal.subject[:8]
    org = Organization(
        name=f"{label} (OIDC)"[:255],
        slug=slug,
        plan=OrgPlan.ALGENTA_FREE,  # individual Community tier; metering is off regardless
        status=OrgStatus.ACTIVE,
    )
    db.add(org)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        org = (
            await db.execute(select(Organization).where(Organization.slug == slug))
        ).scalar_one()
    return org


async def _auto_provision(principal: OidcPrincipal, db: AsyncSession) -> OidcPrincipalMapping:
    """Link a verified-but-unmapped OIDC identity to a subscription. Joins the issuer's shared
    Team/Enterprise org when one has a free seat; otherwise gives the principal their own
    individual Community org. The token is already validated for issuer + audience before
    reaching here."""
    org = await _issuer_shared_org(principal, db) or await _find_or_create_user_org(principal, db)
    mapping = OidcPrincipalMapping(
        issuer=principal.issuer,
        subject=principal.subject,
        principal_type=principal.principal_type,
        org_id=org.id,
        role="member",
        status="active",
        display_name=principal.name,
        email=principal.preferred_username,
    )
    db.add(mapping)
    try:
        await db.flush()
        await db.commit()
    except IntegrityError:
        # Concurrent sign-in mapped the same principal — adopt the existing mapping.
        await db.rollback()
        mapping = (
            await db.execute(
                select(OidcPrincipalMapping).where(
                    OidcPrincipalMapping.issuer == principal.issuer,
                    OidcPrincipalMapping.subject == principal.subject,
                )
            )
        ).scalar_one()
    logger.info(
        "oidc_principal_auto_provisioned",
        principal=principal.principal_ref,
        org_id=str(mapping.org_id),
    )
    return mapping


async def resolve_oidc_principal(principal: OidcPrincipal, db: AsyncSession) -> AuthContext:
    """Map a verified principal to an AuthContext, or raise :class:`OidcAuthError`."""

    row = (
        await db.execute(
            select(OidcPrincipalMapping).where(
                OidcPrincipalMapping.issuer == principal.issuer,
                OidcPrincipalMapping.subject == principal.subject,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        # Unknown identity: auto-link it when enabled, else reject.
        if get_settings().oidc_auto_provision:
            row = await _auto_provision(principal, db)
        else:
            raise OidcAuthError(
                "principal_not_mapped",
                "This identity is not provisioned on this gateway. Ask an administrator to map it.",
            )
    if row.status != "active":
        # A revoked mapping is never auto-revived — do not leak which principals exist.
        raise OidcAuthError(
            "principal_not_mapped",
            "This identity is not provisioned on this gateway. Ask an administrator to map it.",
        )

    org = (
        await db.execute(select(Organization).where(Organization.id == row.org_id))
    ).scalar_one_or_none()
    if org is None:
        raise OidcAuthError("principal_not_mapped", "The mapped organization no longer exists.")

    plan = getattr(getattr(org, "plan", None), "value", None) or str(getattr(org, "plan", "free"))
    org_status = getattr(getattr(org, "status", None), "value", None) or str(
        getattr(org, "status", "active")
    )

    logger.debug(
        "oidc_principal_resolved",
        principal=principal.principal_ref,
        org_id=str(row.org_id),
        workspace_id=str(row.workspace_id) if row.workspace_id else None,
    )
    return AuthContext(
        org_id=row.org_id,
        # No api_keys row backs an OIDC identity. key_id stays None so writers stamp NULL into
        # the nullable api_key_id FK columns (never a dangling FK), and key-anchored endpoints
        # can detect a keyless identity instead of 500-ing on a missing lookup.
        key_id=None,
        key_prefix="oidc",
        user_id=None,
        plan=plan,
        device_limit=0,
        device_limit_configured=False,
        role=row.role,
        email=principal.preferred_username or row.email or principal.principal_ref,
        is_platform=False,  # an OIDC caller may NEVER assume X-Workspace-Id
        # NOT a service credential: is_service carries a repo-specific allowance meant for
        # engine-internal callers. An OIDC principal's permissions come from its provisioned
        # mapping role, never from is_service.
        is_service=False,
        workspace_id=row.workspace_id,  # derived from the mapping, not the request
        org_status=org_status,
        user_status="active",
        email_verified=True,  # OIDC identities are IdP-managed and pre-verified
    )
