"""Wave 2 PR-2b: operator suspend/unsuspend/delete tooling (scripts/admin_account_control.py).

Pure-logic tests (arg parsing, identifier resolution, action validation) + DB tests that the action
flips the enforced UserStatus/OrgStatus and reports the busted-cache count.
"""

from __future__ import annotations

import uuid

import pytest

from apps.api_server.models.organization import OrgStatus
from apps.api_server.models.user import UserStatus
from scripts.admin_account_control import _maybe_uuid, _parse_args, apply_account_action


class _FakeRedis:
    def __init__(self):
        self.deleted: list[str] = []

    async def delete(self, key):
        self.deleted.append(key)
        return 1


async def _seed_org_user_keys(n_keys: int = 2):
    from apps.api_server.db.session import AsyncSessionLocal
    from apps.api_server.models.api_key import APIKey
    from apps.api_server.models.organization import Organization, OrgPlan
    from apps.api_server.models.user import User, UserRole

    s8 = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        org = Organization(name="Admin Test", slug=f"admin-test-{s8}", plan=OrgPlan.FREE, status=OrgStatus.ACTIVE)
        session.add(org)
        await session.flush()
        user = User(
            org_id=org.id, email=f"admin-{s8}@example.com", password_hash="x", name="T",
            role=UserRole.OWNER, status=UserStatus.ACTIVE, email_verified=True,
        )
        session.add(user)
        await session.flush()
        for i in range(n_keys):
            session.add(APIKey(org_id=org.id, user_id=user.id, label=f"k{i}",
                               key_prefix=f"de_live_{s8[:4]}{i}", hashed_key=f"hash_{s8}_{i}"))
        await session.commit()
        return str(org.id), str(user.id), org.slug, user.email


# ── pure logic (no DB) ────────────────────────────────────────────────────────


def test_maybe_uuid():
    assert _maybe_uuid("not-a-uuid") is None
    u = uuid.uuid4()
    assert _maybe_uuid(str(u)) == u


def test_parse_args_enforces_choices():
    a = _parse_args(["--target", "org", "--id", "x", "--action", "suspend"])
    assert (a.target, a.action) == ("org", "suspend")
    with pytest.raises(SystemExit):
        _parse_args(["--target", "bad", "--id", "x", "--action", "suspend"])


async def test_user_delete_is_rejected():
    # users have no DELETED status; the check fires before any DB access.
    with pytest.raises(ValueError):
        await apply_account_action(None, None, target="user", identifier="x", action="delete")


async def test_unknown_target_is_rejected():
    with pytest.raises(ValueError):
        await apply_account_action(None, None, target="nope", identifier="x", action="suspend")


# ── DB-backed ───────────────────────────────────────────────────────────────


async def test_org_suspend_then_delete_flips_status_and_busts_cache():
    from apps.api_server.db.session import AsyncSessionLocal

    org_id, _user_id, slug, _email = await _seed_org_user_keys(n_keys=2)
    async with AsyncSessionLocal() as session:
        r = await apply_account_action(session, _FakeRedis(), target="org", identifier=slug, action="suspend")
    assert r["status"] == OrgStatus.SUSPENDED.value
    assert r["keys_invalidated"] == 2  # both org keys' caches busted
    # delete by uuid (soft → DELETED)
    async with AsyncSessionLocal() as session:
        r2 = await apply_account_action(session, _FakeRedis(), target="org", identifier=org_id, action="delete")
    assert r2["status"] == OrgStatus.DELETED.value


async def test_user_suspend_then_unsuspend():
    from apps.api_server.db.session import AsyncSessionLocal

    _org_id, user_id, _slug, email = await _seed_org_user_keys(n_keys=1)
    async with AsyncSessionLocal() as session:
        r = await apply_account_action(session, _FakeRedis(), target="user", identifier=email, action="suspend")
    assert r["status"] == UserStatus.SUSPENDED.value
    async with AsyncSessionLocal() as session:
        r2 = await apply_account_action(session, _FakeRedis(), target="user", identifier=user_id, action="unsuspend")
    assert r2["status"] == UserStatus.ACTIVE.value


async def test_not_found_raises():
    from apps.api_server.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        with pytest.raises(ValueError):
            await apply_account_action(session, _FakeRedis(), target="org", identifier="no-such-slug", action="suspend")
