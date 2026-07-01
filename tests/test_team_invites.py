"""Team membership: seat limits + real invite/accept flow (replaces the old invite stub).

Pure seat-logic tests + DB-backed tests that exercise the invite -> accept lifecycle and the
per-plan seat enforcement (solo plans can't add members; Team is capped at its seats).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from apps.api_server.routers.team import (
    AcceptRequest,
    InviteRequest,
    accept_invite,
    invite_member,
)
from apps.api_server.services import resend_email
from apps.api_server.services.team_seats import can_add_member, is_multi_seat, seat_limit


# ── pure seat logic (no DB) ───────────────────────────────────────────────────
def test_seat_limits():
    assert seat_limit("free") == 1
    assert seat_limit("pro") == 1
    assert seat_limit("ultra") == 1
    assert seat_limit("team") == 5
    assert seat_limit("team", purchased_seats=12) == 12
    assert seat_limit("enterprise") == 0  # unlimited
    assert is_multi_seat("team") and is_multi_seat("enterprise")
    assert not is_multi_seat("pro")
    assert can_add_member("enterprise", 9999)
    assert can_add_member("team", 4)
    assert not can_add_member("team", 5)
    assert not can_add_member("pro", 1)


# ── helpers ───────────────────────────────────────────────────────────────────
async def _seed_org(plan: str, seats: int = 1):
    from apps.api_server.db.session import AsyncSessionLocal
    from apps.api_server.models.organization import Organization, OrgPlan, OrgStatus
    from apps.api_server.models.user import User, UserRole, UserStatus

    s8 = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as s:
        org = Organization(name="Team Test", slug=f"team-{s8}", plan=OrgPlan(plan), status=OrgStatus.ACTIVE, seats=seats)
        s.add(org)
        await s.flush()
        owner = User(
            org_id=org.id, email=f"owner-{s8}@ex.com", password_hash="x", name="Owner",
            role=UserRole.OWNER, status=UserStatus.ACTIVE, email_verified=True,
        )
        s.add(owner)
        await s.commit()
        return org.id, owner.id, s8


def _auth(org_id, user_id, plan):
    return {
        "org_id": org_id, "user_id": str(user_id), "plan": plan, "role": "admin",
        "key_id": "k", "key_prefix": "de_live", "email": "owner", "is_platform": False,
        "workspace_id": None, "org_status": "active", "user_status": "active",
    }


@pytest.fixture(autouse=True)
def _no_email(monkeypatch):
    async def _noop(**kwargs):
        return True

    monkeypatch.setattr(resend_email, "send_team_invite_email", _noop)


# ── DB-backed lifecycle ────────────────────────────────────────────────────────
async def test_solo_plan_cannot_invite():
    from apps.api_server.db.session import AsyncSessionLocal

    org_id, user_id, s8 = await _seed_org("pro")
    async with AsyncSessionLocal() as s:
        with pytest.raises(HTTPException) as ei:
            await invite_member(InviteRequest(email=f"a-{s8}@ex.com", role="member"), s, _auth(org_id, user_id, "pro"))
    assert ei.value.status_code == 403
    assert ei.value.detail["error"]["code"] == "seats_not_available"


async def test_team_invite_then_accept_adds_member():
    from apps.api_server.db.session import AsyncSessionLocal
    from apps.api_server.models.team_invite import TeamInvite
    from apps.api_server.models.user import User

    org_id, user_id, s8 = await _seed_org("team", seats=5)
    invitee = f"invitee-{s8}@ex.com"
    async with AsyncSessionLocal() as s:
        res = await invite_member(InviteRequest(email=invitee, role="member"), s, _auth(org_id, user_id, "team"))
    assert res["status"] == "pending" and res["seat_limit"] == 5 and res["seats_used"] == 2

    async with AsyncSessionLocal() as s:
        token = (await s.scalar(select(TeamInvite).where(TeamInvite.org_id == org_id))).token
    async with AsyncSessionLocal() as s:
        acc = await accept_invite(AcceptRequest(token=token), s)
    assert acc["email"] == invitee and acc["role"] == "member"

    async with AsyncSessionLocal() as s:
        n = await s.scalar(select(func.count()).select_from(User).where(User.org_id == org_id))
    assert n == 2  # owner + accepted member share the org/plan


async def test_team_seat_cap_blocks_over_limit():
    from apps.api_server.db.session import AsyncSessionLocal

    org_id, user_id, s8 = await _seed_org("team", seats=5)
    # owner already uses 1 of 5 seats → 4 more invites fit; the 5th is blocked.
    async with AsyncSessionLocal() as s:
        for i in range(4):
            await invite_member(InviteRequest(email=f"m{i}-{s8}@ex.com", role="member"), s, _auth(org_id, user_id, "team"))
        with pytest.raises(HTTPException) as ei:
            await invite_member(InviteRequest(email=f"over-{s8}@ex.com", role="member"), s, _auth(org_id, user_id, "team"))
    assert ei.value.status_code == 403
    assert ei.value.detail["error"]["code"] == "seat_limit_reached"


async def test_purchased_seats_drive_the_cap():
    """Per-seat billing: an org that bought 2 seats caps at 2 (owner + 1 invite),
    not the default team bundle of 5."""
    from apps.api_server.db.session import AsyncSessionLocal

    org_id, owner_id, s8 = await _seed_org("team", seats=2)
    async with AsyncSessionLocal() as s:
        # owner uses seat 1; 1 invite fills seat 2
        res = await invite_member(InviteRequest(email=f"a-{s8}@ex.com", role="member"), s, _auth(org_id, owner_id, "team"))
        assert res["seat_limit"] == 2
        # seat 3 is over the purchased 2 → blocked
        with pytest.raises(HTTPException) as ei:
            await invite_member(InviteRequest(email=f"b-{s8}@ex.com", role="member"), s, _auth(org_id, owner_id, "team"))
    assert ei.value.status_code == 403
    assert ei.value.detail["error"]["code"] == "seat_limit_reached"


async def test_accept_invalid_token_404():
    from apps.api_server.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as s:
        with pytest.raises(HTTPException) as ei:
            await accept_invite(AcceptRequest(token="does-not-exist"), s)
    assert ei.value.status_code == 404


async def test_same_email_can_belong_to_two_orgs():
    """Cross-org membership: one email is an active member of TWO different orgs
    (previously blocked by the global users.email unique — now per-org)."""
    from apps.api_server.db.session import AsyncSessionLocal
    from apps.api_server.models.team_invite import TeamInvite
    from apps.api_server.models.user import User

    shared = f"shared-{uuid.uuid4().hex[:8]}@ex.com"
    org_ids = []
    for _ in range(2):
        org_id, owner_id, _s8 = await _seed_org("team", seats=2)
        org_ids.append(org_id)
        async with AsyncSessionLocal() as s:
            await invite_member(InviteRequest(email=shared, role="member"), s, _auth(org_id, owner_id, "team"))
        async with AsyncSessionLocal() as s:
            token = (await s.scalar(select(TeamInvite).where(TeamInvite.org_id == org_id))).token
        async with AsyncSessionLocal() as s:
            await accept_invite(AcceptRequest(token=token), s)

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(User).where(func.lower(User.email) == shared))).scalars().all()
    assert len(rows) == 2
    assert {r.org_id for r in rows} == set(org_ids)


async def test_downgrade_suspends_excess_members_keeps_owner():
    """Team (owner + 3 members) downgraded to a solo plan → the 3 members are
    suspended, the owner is kept (the seat-cap enforcement on downgrade)."""
    from apps.api_server.db.session import AsyncSessionLocal
    from apps.api_server.models.user import User, UserRole, UserStatus
    from apps.api_server.routers.billing import _suspend_excess_members

    org_id, owner_id, s8 = await _seed_org("team")
    async with AsyncSessionLocal() as s:
        for i in range(3):
            s.add(User(
                org_id=org_id, email=f"mem{i}-{s8}@ex.com", password_hash="", name=f"M{i}",
                role=UserRole.MEMBER, status=UserStatus.ACTIVE, email_verified=True,
            ))
        await s.commit()
    # downgrade to a solo plan → seat cap 1 → keep owner, suspend the 3 members
    async with AsyncSessionLocal() as s:
        n = await _suspend_excess_members(s, org_id, seat_limit("pro"))
        await s.commit()
    assert n == 3
    async with AsyncSessionLocal() as s:
        active = await s.scalar(
            select(func.count()).select_from(User).where(
                User.org_id == org_id, User.status == UserStatus.ACTIVE
            )
        )
        owner = await s.scalar(select(User).where(User.id == owner_id))
    assert active == 1
    assert owner.status == UserStatus.ACTIVE
