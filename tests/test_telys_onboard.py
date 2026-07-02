"""POST /v1/telys/onboard — self-service Telys onboarding (Supabase-authed).

This is the fix for the new-user gap: a brand-new GitHub/Google user (Supabase JWT) had no route to a
telys-entitled API key (POST /v1/api-keys rejects Supabase JWTs; the org resolver is lookup-only). This endpoint
resolves-or-creates the caller's org on the free telys_developer tier (so the device license carries
products.telys) and mints the first key. The Supabase verifier has its own tests; here it's stubbed.
"""
from __future__ import annotations

from sqlalchemy import select

from apps.api_server.db.session import AsyncSessionLocal
from apps.api_server.models import (
    OrgPlan,
    Organization,
    OrgStatus,
    User,
    UserRole,
    UserStatus,
)
from apps.api_server.routers import account as account_router


def _stub_supabase(monkeypatch, *, email="newdev@example.com", name="New Dev"):
    async def _verify(_token):
        return {"email": email, "user_metadata": {"full_name": name}}

    monkeypatch.setattr(account_router, "verify_supabase_jwt", _verify)


async def _org_for_email(email: str) -> Organization | None:
    async with AsyncSessionLocal() as s:
        u = (await s.execute(select(User).where(User.email == email.lower()).order_by(User.created_at))).scalars().first()
        if u is None:
            return None
        return (await s.execute(select(Organization).where(Organization.id == u.org_id))).scalar_one()


async def test_onboard_creates_telys_developer_org_and_key(client, app, monkeypatch):
    _stub_supabase(monkeypatch, email="newdev@example.com")
    r = await client.post(
        "/v1/telys/onboard",
        headers={"authorization": "Bearer JWT"},
        json={"name": "telys-cli", "product": "telys", "plan": "telys_developer"},
    )
    assert r.status_code == 201, r.text
    assert r.json().get("raw_key")

    org = await _org_for_email("newdev@example.com")
    assert org is not None and org.plan == OrgPlan.TELYS_DEVELOPER
    # the license issued for this plan will carry products.telys (the whole point)
    from apps.api_server.services.entitlement_service import resolve_entitlement

    assert "telys" in resolve_entitlement(org.plan.value).products


async def test_onboard_is_idempotent_per_email(client, app, monkeypatch):
    _stub_supabase(monkeypatch, email="dupe@example.com")
    r1 = await client.post("/v1/telys/onboard", headers={"authorization": "Bearer JWT"}, json={})
    r2 = await client.post("/v1/telys/onboard", headers={"authorization": "Bearer JWT"}, json={})
    assert r1.status_code == 201 and r2.status_code == 201
    # both keys are usable, but only ONE org exists for this email (no duplicate orgs)
    async with AsyncSessionLocal() as s:
        users = (await s.execute(select(User).where(User.email == "dupe@example.com"))).scalars().all()
    assert users and len({u.org_id for u in users}) == 1


async def test_onboard_requires_bearer(client, app):
    r = await client.post("/v1/telys/onboard", json={})
    assert r.status_code == 401


async def test_onboard_rejects_identity_without_email(client, app, monkeypatch):
    async def _verify(_token):
        return {"user_metadata": {}}  # no email anywhere

    monkeypatch.setattr(account_router, "verify_supabase_jwt", _verify)
    r = await client.post("/v1/telys/onboard", headers={"authorization": "Bearer JWT"}, json={})
    assert r.status_code == 400


async def test_onboard_does_not_downgrade_a_paid_org(client, app, monkeypatch):
    # An existing PAID (codna) org that does the telys onboard keeps its plan (no downgrade to telys_developer).
    email = "paid@example.com"
    async with AsyncSessionLocal() as s:
        org = Organization(name="Paid Co", slug="paid-co-telys-test", plan=OrgPlan.PRO, status=OrgStatus.ACTIVE)
        s.add(org)
        await s.flush()
        s.add(User(org_id=org.id, email=email, password_hash="x", name="Paid",
                   role=UserRole.OWNER, status=UserStatus.ACTIVE, email_verified=True))
        await s.commit()
    _stub_supabase(monkeypatch, email=email)
    r = await client.post("/v1/telys/onboard", headers={"authorization": "Bearer JWT"}, json={})
    assert r.status_code == 201
    org2 = await _org_for_email(email)
    assert org2.plan == OrgPlan.PRO  # unchanged — never downgraded
