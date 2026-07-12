"""Wave-C PR-3: exactly-once billing.

A retried persist_simulation_run (same run_id) must produce exactly ONE SimulationRun and ONE
UsageRecord, and fire the quota counter + the (real-money) Stripe push exactly once — never under-
bill (the SimulationRun PK collision no longer aborts the txn before the UsageRecord) nor double-
bill (the partial-unique usage_key + the rowcount gate). NULL-keyed rows (heartbeat / credits) are
exempt from the constraint. Runs against the dev Postgres; skips cleanly when none is reachable."""

from __future__ import annotations

import asyncio
import os
import uuid
from unittest.mock import AsyncMock

import pytest

DB_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://angel:@localhost:5432/decision_engine")


def _persist_meta(org_id: uuid.UUID, run_id: uuid.UUID) -> dict:
    return {
        "run_id": str(run_id),
        "org_id": str(org_id),
        "api_key_id": None,
        "mode": "expert",
        "request_hash": "req-" + run_id.hex[:12],
        "execution_ms": 42,
        "engine_version": "test-1",
        "scenarios_run": 1000,
        "result_hash": "res-" + run_id.hex[:12],
        "recommended_action": "proceed",
        "confidence": 0.9,
        "expected_value": 1.5,
        "probability_of_loss": 0.1,
        "std_deviation": 0.2,
        "rationale": "ok",
        "simulation_model": "monte_carlo",
        "envelope_json": {"status": "completed"},
    }


@pytest.fixture
async def session_factory_and_org():
    from sqlalchemy import delete, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    engine = create_async_engine(DB_URL, echo=False)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    from apps.api_server.models import Organization, OrgPlan, OrgStatus
    from apps.api_server.models.simulation_run import SimulationRun
    from apps.api_server.models.usage_record import UsageRecord

    try:
        async with factory() as probe:
            try:
                await probe.execute(select(1))
            except Exception:
                pytest.skip("no Postgres reachable for the exactly-once billing test")
            org = Organization(
                name="pytest exactly-once",
                slug=f"pytest-eo-{uuid.uuid4().hex[:10]}",
                plan=OrgPlan.PRO,
                status=OrgStatus.ACTIVE,
            )
            probe.add(org)
            await probe.commit()
            org_id = org.id
        try:
            yield factory, org_id
        finally:
            async with factory() as cleanup:
                await cleanup.execute(delete(UsageRecord).where(UsageRecord.org_id == org_id))
                await cleanup.execute(delete(SimulationRun).where(SimulationRun.org_id == org_id))
                await cleanup.execute(delete(Organization).where(Organization.id == org_id))
                await cleanup.commit()
    finally:
        await engine.dispose()


async def _count(factory, model, org_id) -> int:
    from sqlalchemy import func, select

    async with factory() as s:
        return int(await s.scalar(select(func.count()).select_from(model).where(model.org_id == org_id)))


async def test_retried_persist_bills_exactly_once(session_factory_and_org, monkeypatch):
    import apps.api_server.services._persist_helpers as ph
    from apps.api_server.models.simulation_run import SimulationRun
    from apps.api_server.models.usage_record import UsageRecord

    factory, org_id = session_factory_and_org
    run_id = uuid.uuid4()
    meta = _persist_meta(org_id, run_id)

    stripe_calls = {"n": 0}

    async def _fake_stripe(**kwargs):
        stripe_calls["n"] += 1

    monkeypatch.setattr(ph, "_push_stripe_usage", _fake_stripe)
    # This test asserts the metered billing path (UsageRecord + Stripe). Metering is OFF by
    # default now (self-host, per-device), so opt in to exercise the exactly-once machinery.
    monkeypatch.setattr("apps.api_server.services.quota_service._metering_disabled", lambda: False)

    # two independent transactions with the SAME run_id (the Celery-retry scenario)
    for _ in range(2):
        async with factory() as session:
            await ph.persist_simulation_run(
                db=session, persist_meta=meta, plan="pro", actor_email="t@example.com",
                client_ip="127.0.0.1", redis_client=None,
            )
            await session.commit()
        await asyncio.sleep(0.05)  # let the fire-and-forget Stripe task run

    assert await _count(factory, SimulationRun, org_id) == 1  # idempotent run insert
    assert await _count(factory, UsageRecord, org_id) == 1  # billed exactly once
    assert stripe_calls["n"] == 1  # real-money push fired once, not twice


async def test_algenta_persist_never_pushes_usage_to_stripe_or_quota_redis(
    session_factory_and_org, monkeypatch
):
    import apps.api_server.services._persist_helpers as ph
    from apps.api_server.models.usage_record import UsageRecord

    factory, org_id = session_factory_and_org
    push = AsyncMock()
    redis = AsyncMock()
    monkeypatch.setattr(ph, "_push_stripe_usage", push)
    # Metering is OFF by default now; opt in so the UsageRecord is written (this test asserts
    # that even with metering on, an Algenta per-device plan writes the local row but never
    # pushes to Stripe / the quota counter).
    monkeypatch.setattr("apps.api_server.services.quota_service._metering_disabled", lambda: False)

    async with factory() as session:
        await ph.persist_simulation_run(
            db=session,
            persist_meta=_persist_meta(org_id, uuid.uuid4()),
            plan="algenta_pro",
            actor_email="owner@example.com",
            client_ip="127.0.0.1",
            redis_client=redis,
        )
        await session.commit()
    await asyncio.sleep(0)

    assert await _count(factory, UsageRecord, org_id) == 1
    redis.incr.assert_not_awaited()
    push.assert_not_awaited()


async def test_null_usage_key_rows_are_exempt(session_factory_and_org):
    from apps.api_server.models.usage_record import UsageEndpoint, UsageRecord

    factory, org_id = session_factory_and_org
    # two NULL-keyed usage rows (e.g. heartbeat writers) coexist — the partial-unique index ignores NULL
    async with factory() as s:
        for _ in range(2):
            s.add(
                UsageRecord(
                    org_id=org_id, billing_period="2026-06", endpoint=UsageEndpoint.SIMULATE,
                    billing_units=1, scenarios_run=0, usage_key=None,
                )
            )
        await s.commit()
    assert await _count(factory, UsageRecord, org_id) == 2
