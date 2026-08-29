"""The OIDC principal provisioner (scripts/provision_oidc_principal.py) — the write-side the
gateway was missing. Without it, every verified OIDC caller 403s (principal_not_mapped) forever
(unless auto-provision is on), so no Okta/Auth0/Keycloak identity can be onboarded. These prove:
provisioning writes a mapping the resolver reads (→ AuthContext with the org+role), it is
idempotent on (issuer,subject), and a revoked mapping is refused — the full write→read path an
OIDC caller depends on. Mirrors test_provision_entra_principal.py exactly."""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from apps.api_server.db.session import AsyncSessionLocal
from apps.api_server.models.oidc_principal import OidcPrincipalMapping
from apps.api_server.models.organization import Organization
from apps.api_server.services.oidc_auth import OidcAuthError, OidcPrincipal
from apps.api_server.services.oidc_org_resolver import resolve_oidc_principal
from scripts.provision_oidc_principal import provision

ISSUER = "https://idp.example.com/realms/acme"


def _args(subject: str, slug: str, role: str = "admin", ptype: str = "app", status: str = "active"):
    return SimpleNamespace(issuer=ISSUER, subject=subject, org_slug=slug, role=role, ptype=ptype,
                            status=status, display_name="CI service account", email=None)


def _principal(subject: str, ptype: str = "app") -> OidcPrincipal:
    return OidcPrincipal(issuer=ISSUER, subject=subject, principal_type=ptype, client_id=None,
                          scopes=(), roles=("decisions.service",))


@pytest.mark.anyio
async def test_provision_then_resolve_yields_authcontext_with_org_and_role() -> None:
    subject = uuid.uuid4().hex
    slug = f"oidc-prov-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as s:
        m = await provision(s, _args(subject, slug, role="admin"))
        await s.commit()
        org_id = m.org_id
    # the org was get-or-created
    async with AsyncSessionLocal() as s:
        org = (await s.execute(select(Organization).where(Organization.slug == slug))).scalar_one()
        assert org.id == org_id
    # the resolver reads the mapping -> AuthContext bound to that org + role (the path an OIDC call takes)
    async with AsyncSessionLocal() as s:
        ctx = await resolve_oidc_principal(_principal(subject), s)
    assert ctx["org_id"] == org_id and ctx["role"] == "admin" and ctx["is_service"] is False


@pytest.mark.anyio
async def test_provision_is_idempotent_and_updates_role() -> None:
    subject = uuid.uuid4().hex
    slug = f"oidc-idem-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as s:
        await provision(s, _args(subject, slug, role="member"))
        await s.commit()
    async with AsyncSessionLocal() as s:
        await provision(s, _args(subject, slug, role="admin"))  # same (issuer,subject) -> update, no dupe
        await s.commit()
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(OidcPrincipalMapping).where(
            OidcPrincipalMapping.issuer == ISSUER, OidcPrincipalMapping.subject == subject
        ))).scalars().all()
    assert len(rows) == 1 and rows[0].role == "admin"


@pytest.mark.anyio
async def test_revoked_mapping_is_refused() -> None:
    subject = uuid.uuid4().hex
    slug = f"oidc-rev-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as s:
        await provision(s, _args(subject, slug, status="revoked"))
        await s.commit()
    with pytest.raises(OidcAuthError) as e:
        async with AsyncSessionLocal() as s:
            await resolve_oidc_principal(_principal(subject), s)
    assert "not_mapped" in e.value.code or e.value.code == "principal_not_mapped"
