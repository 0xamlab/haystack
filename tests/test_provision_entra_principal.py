"""The Entra principal provisioner (scripts/provision_entra_principal.py) — the write-side the
gateway was missing. Without it, every verified Entra caller 403s (principal_not_mapped) forever, so
no Excel/Teams/Copilot/Foundry identity can be onboarded. These prove: provisioning writes a mapping
the resolver reads (→ AuthContext with the org+role), it is idempotent on (tenant,oid), and a revoked
mapping is refused — the full write→read path an Entra caller depends on."""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from apps.api_server.db.session import AsyncSessionLocal
from apps.api_server.models.entra_principal import EntraPrincipalMapping
from apps.api_server.models.organization import Organization
from apps.api_server.services.entra_auth import EntraAuthError, EntraPrincipal
from apps.api_server.services.entra_org_resolver import resolve_entra_principal
from scripts.provision_entra_principal import provision

TENANT = "7a0cd533-4d98-450c-bc3a-93cee1495e06"


def _args(oid: str, slug: str, role: str = "admin", ptype: str = "app", status: str = "active"):
    return SimpleNamespace(tenant=TENANT, oid=oid, org_slug=slug, role=role, ptype=ptype,
                           status=status, display_name="Foundry agent", email=None)


def _principal(oid: str, ptype: str = "app") -> EntraPrincipal:
    return EntraPrincipal(tenant_id=TENANT, oid=oid, principal_type=ptype, client_app_id=None,
                          scopes=(), roles=("Decisions.Service",))


@pytest.mark.anyio
async def test_provision_then_resolve_yields_authcontext_with_org_and_role() -> None:
    oid = uuid.uuid4().hex
    slug = f"entra-prov-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as s:
        m = await provision(s, _args(oid, slug, role="admin"))
        await s.commit()
        org_id = m.org_id
    # the org was get-or-created
    async with AsyncSessionLocal() as s:
        org = (await s.execute(select(Organization).where(Organization.slug == slug))).scalar_one()
        assert org.id == org_id
    # the resolver reads the mapping -> AuthContext bound to that org + role (the path an Entra call takes)
    async with AsyncSessionLocal() as s:
        ctx = await resolve_entra_principal(_principal(oid), s)
    assert ctx["org_id"] == org_id and ctx["role"] == "admin" and ctx["is_service"] is False


@pytest.mark.anyio
async def test_provision_is_idempotent_and_updates_role() -> None:
    oid = uuid.uuid4().hex
    slug = f"entra-idem-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as s:
        await provision(s, _args(oid, slug, role="member"))
        await s.commit()
    async with AsyncSessionLocal() as s:
        await provision(s, _args(oid, slug, role="admin"))  # same (tenant,oid) -> update, no dupe
        await s.commit()
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(EntraPrincipalMapping).where(
            EntraPrincipalMapping.tenant_id == TENANT, EntraPrincipalMapping.principal_oid == oid
        ))).scalars().all()
    assert len(rows) == 1 and rows[0].role == "admin"


@pytest.mark.anyio
async def test_revoked_mapping_is_refused() -> None:
    oid = uuid.uuid4().hex
    slug = f"entra-rev-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as s:
        await provision(s, _args(oid, slug, status="revoked"))
        await s.commit()
    with pytest.raises(EntraAuthError) as e:
        async with AsyncSessionLocal() as s:
            await resolve_entra_principal(_principal(oid), s)
    assert "not_mapped" in e.value.code or e.value.code == "principal_not_mapped"
