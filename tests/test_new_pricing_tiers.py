"""proplus + ultra tiers: enum, price mapping, seat classification, and DB enum (0045)."""

from __future__ import annotations

import uuid


def test_proplus_ultra_in_orgplan_enum():
    from apps.api_server.models.organization import OrgPlan

    assert OrgPlan("proplus") is OrgPlan.PROPLUS
    assert OrgPlan("ultra") is OrgPlan.ULTRA


def test_proplus_ultra_price_mapping_resolves():
    from apps.api_server.services.stripe_service import PLAN_PRICE_IDS

    # keys exist (no KeyError); value is the env price or None if the env is a placeholder
    _ = PLAN_PRICE_IDS["proplus"]
    _ = PLAN_PRICE_IDS["ultra"]


def test_proplus_ultra_are_single_seat():
    from apps.api_server.services.team_seats import is_multi_seat, seat_limit

    assert seat_limit("proplus") == 1
    assert seat_limit("ultra") == 1
    assert not is_multi_seat("proplus")
    assert not is_multi_seat("ultra")


def test_proplus_ultra_have_plan_limits():
    from apps.api_server.services.plan_limits import device_limit

    # bigger than pro (5) — ultra allows more devices; both are defined (no KeyError/default)
    assert device_limit("proplus") >= 5
    assert device_limit("ultra") >= device_limit("proplus")


async def test_org_plan_proplus_persists_in_db():
    """Proves migration 0045 added 'proplus'/'ultra' to the org_plan Postgres enum —
    without it this INSERT fails with 'invalid input value for enum org_plan'."""
    from apps.api_server.db.session import AsyncSessionLocal
    from apps.api_server.models.organization import Organization, OrgPlan, OrgStatus

    s8 = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as s:
        org = Organization(name="PP", slug=f"pp-{s8}", plan=OrgPlan.PROPLUS, status=OrgStatus.ACTIVE)
        s.add(org)
        await s.commit()
        assert org.plan is OrgPlan.PROPLUS
        org.plan = OrgPlan.ULTRA
        await s.commit()
        assert org.plan is OrgPlan.ULTRA
