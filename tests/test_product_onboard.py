"""POST /v1/products/{product}/onboard — product-generic self-service onboarding (Supabase-authed).

The generic form of /v1/telys/onboard, used by `algenta login` (and any future brand). The product comes
from the URL PATH, validated against the product registry — never the request body — so a caller can't
onboard themselves into another brand's entitlement. Resolves-or-creates the caller's org on that product's
free tier (so the device license carries products.<product>) and mints the first key. The Supabase verifier
has its own tests; here it's stubbed (mirrors test_telys_onboard.py).
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


def _stub_supabase(monkeypatch, *, email, name="New Dev"):
    async def _verify(_token):
        return {"email": email, "user_metadata": {"full_name": name}}

    monkeypatch.setattr(account_router, "verify_supabase_jwt", _verify)


async def _org_for_email(email: str) -> Organization | None:
    async with AsyncSessionLocal() as s:
        u = (
            await s.execute(select(User).where(User.email == email.lower()).order_by(User.created_at))
        ).scalars().first()
        if u is None:
            return None
        return (await s.execute(select(Organization).where(Organization.id == u.org_id))).scalar_one()


async def test_algenta_onboard_creates_algenta_free_org_and_key(client, app, monkeypatch):
    _stub_supabase(monkeypatch, email="algdev@example.com")
    r = await client.post(
        "/v1/products/algenta/onboard",
        headers={"authorization": "Bearer JWT"},
        json={"name": "algenta-cli"},
    )
    assert r.status_code == 201, r.text
    assert r.json().get("raw_key")

    org = await _org_for_email("algdev@example.com")
    assert org is not None and org.plan == OrgPlan.ALGENTA_FREE
    # the device license for this plan carries products.algenta with a non-empty feature set (the whole point)
    from apps.api_server.services.entitlement_service import resolve_entitlement, to_license_claims

    rec = resolve_entitlement(org.plan.value)
    assert "algenta" in rec.products
    assert to_license_claims(rec)["products"]["algenta"]["features"]


async def test_onboard_product_comes_from_path_not_body(client, app, monkeypatch):
    # A body `product` is IGNORED — onboarding to /v1/products/algenta/onboard with product="telys" in the
    # body must still land the caller on ALGENTA, never telys (no cross-brand entitlement via a body field).
    _stub_supabase(monkeypatch, email="pathwins@example.com")
    r = await client.post(
        "/v1/products/algenta/onboard",
        headers={"authorization": "Bearer JWT"},
        json={"product": "telys", "plan": "telys_team"},  # both must be ignored
    )
    assert r.status_code == 201, r.text
    org = await _org_for_email("pathwins@example.com")
    assert org.plan == OrgPlan.ALGENTA_FREE  # path won; body's telys_team ignored


async def test_generic_route_also_serves_telys(client, app, monkeypatch):
    _stub_supabase(monkeypatch, email="genericteltys@example.com")
    r = await client.post(
        "/v1/products/telys/onboard", headers={"authorization": "Bearer JWT"}, json={}
    )
    assert r.status_code == 201, r.text
    org = await _org_for_email("genericteltys@example.com")
    assert org.plan == OrgPlan.TELYS_DEVELOPER


async def test_onboard_unknown_product_404(client, app, monkeypatch):
    _stub_supabase(monkeypatch, email="ghost@example.com")
    r = await client.post(
        "/v1/products/nosuchbrand/onboard", headers={"authorization": "Bearer JWT"}, json={}
    )
    assert r.status_code == 404, r.text
    # no org was created for the caller
    assert await _org_for_email("ghost@example.com") is None


async def test_onboard_is_idempotent_per_email(client, app, monkeypatch):
    _stub_supabase(monkeypatch, email="algdupe@example.com")
    r1 = await client.post("/v1/products/algenta/onboard", headers={"authorization": "Bearer JWT"}, json={})
    r2 = await client.post("/v1/products/algenta/onboard", headers={"authorization": "Bearer JWT"}, json={})
    assert r1.status_code == 201 and r2.status_code == 201
    async with AsyncSessionLocal() as s:
        users = (await s.execute(select(User).where(User.email == "algdupe@example.com"))).scalars().all()
    assert users and len({u.org_id for u in users}) == 1  # exactly one org, no junk


async def test_onboard_requires_bearer(client, app):
    r = await client.post("/v1/products/algenta/onboard", json={})
    assert r.status_code == 401


async def test_onboard_rejects_reserved_off_product(client, app, monkeypatch):
    # codna is a registered product but device_login=False (GitHub-App auth) → NOT self-serve onboardable
    # here → 404 (matches the reserved-off intent; no ungated signup for a not-yet-live-for-CLI brand).
    _stub_supabase(monkeypatch, email="codnauser@example.com")
    r = await client.post("/v1/products/codna/onboard", headers={"authorization": "Bearer JWT"}, json={})
    assert r.status_code == 404, r.text
    assert await _org_for_email("codnauser@example.com") is None


async def test_onboard_does_not_downgrade_a_paid_org(client, app, monkeypatch):
    # An existing PAID (codna) org that runs `algenta login` keeps its plan (no downgrade to algenta_free).
    email = "algpaid@example.com"
    async with AsyncSessionLocal() as s:
        org = Organization(name="Paid Co", slug="paid-co-algenta-test", plan=OrgPlan.PRO, status=OrgStatus.ACTIVE)
        s.add(org)
        await s.flush()
        s.add(User(org_id=org.id, email=email, password_hash="x", name="Paid",
                   role=UserRole.OWNER, status=UserStatus.ACTIVE, email_verified=True))
        await s.commit()
    _stub_supabase(monkeypatch, email=email)
    r = await client.post("/v1/products/algenta/onboard", headers={"authorization": "Bearer JWT"}, json={})
    assert r.status_code == 201
    org2 = await _org_for_email(email)
    assert org2.plan == OrgPlan.PRO  # unchanged — never downgraded
