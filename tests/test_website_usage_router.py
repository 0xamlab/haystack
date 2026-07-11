"""Website/dashboard usage read — GET /account/usage (Supabase auth).

Pins the dashboard contract against the REAL usage store: the endpoint counts
GITHUB FIXES (fix-completing tool_names only — internal steps like simulations
never count) for the CURRENT billing period and caller's org only, plus the
plan's fix allowance (free env / Stripe cloud_fix_prs metadata). Inert (503)
until Supabase is configured / 401 without a bearer.
"""

from __future__ import annotations

import uuid

import pytest

from apps.api_server.middleware.auth import get_redis
from apps.api_server.models.api_key import APIKey
from apps.api_server.models.usage_record import UsageEndpoint, UsageRecord
from apps.api_server.services import byok_org_resolver, supabase_auth
from apps.api_server.services.auth_service import hash_api_key
from apps.api_server.services.quota_service import _current_billing_period
from tests._test_api_key_expiry_contract_helpers import *  # noqa: F401,F403


@pytest.fixture
def redis_override(app):  # noqa: ANN001
    """Same pattern as the devices-router tests: stub app-state redis."""
    stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return stub

    app.dependency_overrides[get_redis] = _fake_redis
    yield stub
    app.dependency_overrides.pop(get_redis, None)

_IDENT = {"supabase_uid": "sb-uuid-octocat", "github_user_id": 583231, "github_login": "octocat", "email": "octocat@example.com", "provider": "github"}
_BEARER = {"Authorization": "Bearer JWT"}


class _Org:
    def __init__(self, org_id: uuid.UUID, plan: str = "free") -> None:
        self.id = org_id
        self.plan = plan  # str form — the router handles enum-or-str


async def _org_id_for(raw_key: str) -> uuid.UUID:
    async with AsyncSessionLocal() as session:  # noqa: F405
        return (
            await session.execute(select(APIKey.org_id).where(APIKey.hashed_key == hash_api_key(raw_key)))  # noqa: F405
        ).scalar_one()


def _stub_supabase(monkeypatch: pytest.MonkeyPatch, *, configured: bool = True, org: _Org | None = None) -> None:
    monkeypatch.setattr(supabase_auth, "supabase_configured", lambda: configured)

    async def _verify(_token: str) -> dict:
        return {"verified": True}

    monkeypatch.setattr(supabase_auth, "verify_supabase_jwt", _verify)
    monkeypatch.setattr(supabase_auth, "extract_identity", lambda _claims: _IDENT)
    monkeypatch.setattr(supabase_auth, "extract_github_identity", lambda _claims: _IDENT)

    async def _resolve(_db, *, supabase_uid=None, email=None, github_user_id=None, github_login=None, redis=None, selected_org_id=None, auto_provision=False):  # noqa: ANN001
        return org

    monkeypatch.setattr(byok_org_resolver, "resolve_org_for_supabase_user", _resolve)


async def _seed_usage(
    org_id: uuid.UUID, period: str, n: int, tool_name: str = "apply_repository"
) -> None:
    async with AsyncSessionLocal() as session:  # noqa: F405
        for _ in range(n):
            session.add(
                UsageRecord(
                    org_id=org_id,
                    billing_period=period,
                    endpoint=UsageEndpoint.REPOSITORY,
                    billing_units=1,
                    product="codna",
                    tool_name=tool_name,
                )
            )
        await session.commit()


@pytest.mark.anyio
async def test_account_usage_requires_bearer(client, redis_override, monkeypatch):  # noqa: ANN001
    _stub_supabase(monkeypatch, configured=True, org=None)
    r = await client.get("/account/usage")
    assert r.status_code == 401


@pytest.mark.anyio
async def test_account_usage_counts_current_period_own_org_only(client, redis_override, monkeypatch):  # noqa: ANN001
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="Usage Owner",
        expires_at=datetime.now(UTC) + timedelta(days=30),  # noqa: F405
        plan=OrgPlan.FREE,  # noqa: F405
    )
    org_id = await _org_id_for(owner_key)
    period = _current_billing_period()

    # FIX events this period: 2 applies + 1 pipeline = 3 fixes. Internal steps
    # (simulate/triage) and stale-period fixes must NOT count.
    await _seed_usage(org_id, period, 2, tool_name="apply_repository")
    await _seed_usage(org_id, period, 1, tool_name="run_repository_pipeline")
    await _seed_usage(org_id, period, 4, tool_name="simulate_repository_patch")
    await _seed_usage(org_id, period, 2, tool_name="triage_repository")
    await _seed_usage(org_id, "2020-01", 2, tool_name="apply_repository")

    _stub_supabase(monkeypatch, org=_Org(org_id, plan="free"))
    r = await client.get("/account/usage", headers=_BEARER)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["billing_period"] == period
    assert body["plan"] == "free"
    assert body["unit"] == "fixes"
    assert body["used"] == 3  # fixes only — simulations/triage are components, never charged
    assert body["quota"] == 20  # free allowance (CODNA_FREE_FIXES_PER_MONTH default)
    assert body["remaining"] == 17
    assert body["unlimited"] is False
    assert r.headers.get("cache-control") == "no-store"


@pytest.mark.anyio
async def test_account_usage_never_leaks_other_orgs(client, redis_override, monkeypatch):  # noqa: ANN001
    ours_key, _ = await _seed_api_key(  # noqa: F405
        label="Usage Ours",
        expires_at=datetime.now(UTC) + timedelta(days=30),  # noqa: F405
        plan=OrgPlan.FREE,  # noqa: F405
    )
    theirs_key, _ = await _seed_api_key(  # noqa: F405
        label="Usage Theirs",
        expires_at=datetime.now(UTC) + timedelta(days=30),  # noqa: F405
        plan=OrgPlan.FREE,  # noqa: F405
    )
    ours = await _org_id_for(ours_key)
    theirs = await _org_id_for(theirs_key)
    period = _current_billing_period()
    await _seed_usage(theirs, period, 5)

    _stub_supabase(monkeypatch, org=_Org(ours))
    r = await client.get("/account/usage", headers=_BEARER)
    assert r.status_code == 200, r.text
    assert r.json()["used"] == 0
