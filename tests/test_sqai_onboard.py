"""POST /v1/products/sqai/onboard — self-service SQAI onboarding (Supabase-authed).

SQAI is a registry-row product (product_registry "sqai") on the shared engine, so onboarding rides the
generic /v1/products/{product}/onboard route with NO sqai-specific code. These tests pin that the row is
wired end-to-end: onboarding resolves-or-creates the caller's org on the free sqai_developer tier and the
license claims for that plan carry products.sqai (mirrors test_telys_onboard.py; the Supabase verifier has
its own tests — here it's stubbed).
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


def _stub_supabase(monkeypatch, *, email="sqaidev@example.com", name="New Dev"):
    async def _verify(_token):
        return {"email": email, "user_metadata": {"full_name": name}}

    monkeypatch.setattr(account_router, "verify_supabase_jwt", _verify)


async def _org_for_email(email: str) -> Organization | None:
    async with AsyncSessionLocal() as s:
        u = (await s.execute(select(User).where(User.email == email.lower()).order_by(User.created_at))).scalars().first()
        if u is None:
            return None
        return (await s.execute(select(Organization).where(Organization.id == u.org_id))).scalar_one()


async def test_onboard_creates_sqai_developer_org_and_key(client, app, monkeypatch):
    _stub_supabase(monkeypatch, email="sqaidev@example.com")
    r = await client.post(
        "/v1/products/sqai/onboard",
        headers={"authorization": "Bearer JWT"},
        json={"name": "sqai-cli", "product": "sqai", "plan": "sqai_developer"},
    )
    assert r.status_code == 201, r.text
    assert r.json().get("raw_key")

    org = await _org_for_email("sqaidev@example.com")
    assert org is not None and org.plan == OrgPlan.SQAI_DEVELOPER
    # the license issued for this plan carries products.sqai with a non-empty feature set (the whole point)
    from apps.api_server.services.entitlement_service import resolve_entitlement, to_license_claims

    rec = resolve_entitlement(org.plan.value)
    assert "sqai" in rec.products
    claims = to_license_claims(rec)
    assert claims["products"]["sqai"]["features"]
    assert "local_runtime" in claims["products"]["sqai"]["features"]
    assert "structured_query" in claims["products"]["sqai"]["features"]


async def test_onboard_is_idempotent_per_email(client, app, monkeypatch):
    _stub_supabase(monkeypatch, email="sqaidupe@example.com")
    r1 = await client.post("/v1/products/sqai/onboard", headers={"authorization": "Bearer JWT"}, json={})
    r2 = await client.post("/v1/products/sqai/onboard", headers={"authorization": "Bearer JWT"}, json={})
    assert r1.status_code == 201 and r2.status_code == 201
    # both keys are usable, but only ONE org exists for this email (no duplicate orgs)
    async with AsyncSessionLocal() as s:
        users = (await s.execute(select(User).where(User.email == "sqaidupe@example.com"))).scalars().all()
    assert users and len({u.org_id for u in users}) == 1


async def test_onboard_requires_bearer(client, app):
    r = await client.post("/v1/products/sqai/onboard", json={})
    assert r.status_code == 401


async def test_onboard_rejects_identity_without_email(client, app, monkeypatch):
    async def _verify(_token):
        return {"user_metadata": {}}  # no email anywhere

    monkeypatch.setattr(account_router, "verify_supabase_jwt", _verify)
    r = await client.post("/v1/products/sqai/onboard", headers={"authorization": "Bearer JWT"}, json={})
    assert r.status_code == 400


async def test_onboard_does_not_downgrade_a_paid_org(client, app, monkeypatch):
    # An existing PAID (codna) org that runs `sqai login` keeps its plan (no downgrade to sqai_developer).
    email = "sqaipaid@example.com"
    async with AsyncSessionLocal() as s:
        org = Organization(name="Paid Co", slug="paid-co-sqai-test", plan=OrgPlan.PRO, status=OrgStatus.ACTIVE)
        s.add(org)
        await s.flush()
        s.add(User(org_id=org.id, email=email, password_hash="x", name="Paid",
                   role=UserRole.OWNER, status=UserStatus.ACTIVE, email_verified=True))
        await s.commit()
    _stub_supabase(monkeypatch, email=email)
    r = await client.post("/v1/products/sqai/onboard", headers={"authorization": "Bearer JWT"}, json={})
    assert r.status_code == 201
    org2 = await _org_for_email(email)
    assert org2.plan == OrgPlan.PRO  # unchanged — never downgraded
