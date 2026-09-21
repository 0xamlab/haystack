"""Retention purge for expired short-lived service keys (services/api_key_retention.py).

Real Postgres (the suite's DATABASE_URL): every safety clause of the purge is pinned against
actual rows -- the retention boundary, non-service keys, unexpired and never-expiring keys,
device-registration holders, dry-run, and batching -- plus the CLI's argument contract.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from apps.api_server.db.session import AsyncSessionLocal
from apps.api_server.models import APIKey, APIKeyStatus, Organization, OrgPlan, OrgStatus
from apps.api_server.models.device import DeviceRegistration
from apps.api_server.services import api_key_retention as retention
from apps.api_server.services.auth_service import hash_api_key

RETENTION = timedelta(days=7)


async def _seed_org() -> Organization:
    async with AsyncSessionLocal() as db:
        org = Organization(
            name="Pytest Key Retention",
            slug=f"pytest-key-retention-{uuid4().hex[:12]}",
            plan=OrgPlan.PRO,
            status=OrgStatus.ACTIVE,
        )
        db.add(org)
        await db.commit()
        await db.refresh(org)
        return org


async def _seed_key(
    org: Organization,
    *,
    is_service: bool,
    expires_at: datetime | None,
    label: str,
    status: APIKeyStatus = APIKeyStatus.ACTIVE,
    with_device: bool = False,
) -> APIKey:
    raw = f"de_test_{uuid4().hex}"
    async with AsyncSessionLocal() as db:
        key = APIKey(
            org_id=org.id,
            user_id=None,
            label=label,
            key_prefix=raw[:12],
            hashed_key=hash_api_key(raw),
            status=status,
            is_service=is_service,
            expires_at=expires_at,
        )
        db.add(key)
        await db.flush()
        if with_device:
            db.add(
                DeviceRegistration(
                    org_id=org.id,
                    api_key_id=key.id,
                    device_id=f"dev-{uuid4().hex[:16]}",
                )
            )
        await db.commit()
        await db.refresh(key)
        return key


async def _present(ids) -> set:
    async with AsyncSessionLocal() as db:
        rows = await db.execute(select(APIKey.id).where(APIKey.id.in_(list(ids))))
        return set(rows.scalars().all())


async def _drop_org(org: Organization) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Organization).where(Organization.id == org.id))
        await db.commit()


async def _drain(now: datetime) -> None:
    """Purge whatever the shared test database already holds so batch/count assertions are exact."""
    async with AsyncSessionLocal() as db:
        await retention.purge_expired_service_keys(
            db, execute=True, now=now, retention=RETENTION, batch_size=5000
        )


@pytest.fixture
async def org():
    org = await _seed_org()
    try:
        yield org
    finally:
        await _drop_org(org)


@pytest.fixture
async def org_b():
    org = await _seed_org()
    try:
        yield org
    finally:
        await _drop_org(org)


async def test_dry_run_counts_candidates_but_deletes_nothing(org):
    now = datetime.now(UTC)
    old = now - RETENTION - timedelta(days=3)
    a = await _seed_key(org, is_service=True, expires_at=old, label="svc old a")
    b = await _seed_key(org, is_service=True, expires_at=old, label="svc old b")

    async with AsyncSessionLocal() as db:
        report = await retention.purge_expired_service_keys(db, now=now, retention=RETENTION)

    assert report.execute is False
    assert report.tenants >= 1
    assert report.candidates >= 2
    assert report.deleted == 0
    assert report.batches == 0
    assert report.cutoff == now - RETENTION
    assert await _present({a.id, b.id}) == {a.id, b.id}


async def test_purge_is_tenant_scoped_and_batches_per_tenant(org, org_b):
    now = datetime.now(UTC)
    await _drain(now)
    old = now - RETENTION - timedelta(days=1)
    keys_a = [await _seed_key(org, is_service=True, expires_at=old, label=f"a {i}") for i in range(2)]
    keys_b = [await _seed_key(org_b, is_service=True, expires_at=old, label=f"b {i}") for i in range(2)]
    live_b = await _seed_key(org_b, is_service=True, expires_at=now + timedelta(hours=1), label="b live")

    async with AsyncSessionLocal() as db:
        assert set(await retention.tenants_with_purge_candidates(db, cutoff=now - RETENTION)) == {org.id, org_b.id}
        assert await retention.count_purge_candidates(db, org_id=org.id, cutoff=now - RETENTION) == 2
        report = await retention.purge_expired_service_keys(
            db, execute=True, now=now, retention=RETENTION, batch_size=3
        )

    # 4 candidates across 2 tenants with batch 3: one statement PER TENANT (2 + 2), never one
    # cross-tenant statement of 3 + 1.
    assert (report.tenants, report.candidates, report.deleted, report.batches) == (2, 4, 4, 2)
    assert await _present({k.id for k in keys_a + keys_b} | {live_b.id}) == {live_b.id}


async def test_retention_boundary_is_strict_and_only_past_the_window(org):
    now = datetime.now(UTC)
    cutoff = now - RETENTION
    beyond = await _seed_key(org, is_service=True, expires_at=cutoff - timedelta(seconds=1), label="beyond")
    at_cutoff = await _seed_key(org, is_service=True, expires_at=cutoff, label="at cutoff")
    inside = await _seed_key(org, is_service=True, expires_at=cutoff + timedelta(seconds=1), label="inside")
    just_expired = await _seed_key(org, is_service=True, expires_at=now - timedelta(minutes=1), label="just expired")
    unexpired = await _seed_key(org, is_service=True, expires_at=now + timedelta(hours=1), label="unexpired")
    never = await _seed_key(org, is_service=True, expires_at=None, label="never expires")

    async with AsyncSessionLocal() as db:
        report = await retention.purge_expired_service_keys(db, execute=True, now=now, retention=RETENTION)

    assert report.execute is True
    assert report.deleted >= 1
    kept = {at_cutoff.id, inside.id, just_expired.id, unexpired.id, never.id}
    assert await _present(kept | {beyond.id}) == kept


async def test_non_service_keys_are_never_candidates(org):
    now = datetime.now(UTC)
    long_ago = now - timedelta(days=400)
    human_expired = await _seed_key(org, is_service=False, expires_at=long_ago, label="human expired")
    human_revoked = await _seed_key(
        org, is_service=False, expires_at=long_ago, label="human revoked", status=APIKeyStatus.REVOKED
    )
    human_live = await _seed_key(org, is_service=False, expires_at=None, label="human live")
    service_old = await _seed_key(org, is_service=True, expires_at=long_ago, label="svc old")

    async with AsyncSessionLocal() as db:
        await retention.purge_expired_service_keys(db, execute=True, now=now, retention=RETENTION)

    humans = {human_expired.id, human_revoked.id, human_live.id}
    assert await _present(humans | {service_old.id}) == humans


async def test_service_key_owning_a_device_registration_is_skipped(org):
    now = datetime.now(UTC)
    long_ago = now - timedelta(days=30)
    bound = await _seed_key(org, is_service=True, expires_at=long_ago, label="svc bound", with_device=True)
    free = await _seed_key(org, is_service=True, expires_at=long_ago, label="svc free")

    async with AsyncSessionLocal() as db:
        report = await retention.purge_expired_service_keys(db, execute=True, now=now, retention=RETENTION)

    assert report.deleted >= 1
    assert await _present({bound.id, free.id}) == {bound.id}
    async with AsyncSessionLocal() as db:
        regs = await db.execute(select(DeviceRegistration.id).where(DeviceRegistration.api_key_id == bound.id))
        assert len(regs.scalars().all()) == 1


async def test_execute_deletes_in_batches_of_batch_size(org):
    now = datetime.now(UTC)
    await _drain(now)
    old = now - RETENTION - timedelta(days=1)
    keys = [await _seed_key(org, is_service=True, expires_at=old, label=f"svc {i}") for i in range(7)]

    async with AsyncSessionLocal() as db:
        report = await retention.purge_expired_service_keys(
            db, execute=True, now=now, retention=RETENTION, batch_size=3
        )

    assert report.tenants == 1
    assert report.candidates == 7
    assert report.deleted == 7
    assert report.batches == 3  # 3 + 3 + 1
    assert report.batch_size == 3
    assert await _present({k.id for k in keys}) == set()


async def test_exact_multiple_of_batch_size_issues_no_trailing_empty_delete(org):
    now = datetime.now(UTC)
    await _drain(now)
    old = now - RETENTION - timedelta(days=1)
    keys = [await _seed_key(org, is_service=True, expires_at=old, label=f"svc {i}") for i in range(6)]

    async with AsyncSessionLocal() as db:
        report = await retention.purge_expired_service_keys(
            db, execute=True, now=now, retention=RETENTION, batch_size=3
        )

    assert (report.candidates, report.deleted, report.batches) == (6, 6, 2)  # 3 + 3, no third
    assert await _present({k.id for k in keys}) == set()


async def test_execute_with_large_batch_is_a_single_statement(org):
    now = datetime.now(UTC)
    await _drain(now)
    old = now - RETENTION - timedelta(days=1)
    keys = [await _seed_key(org, is_service=True, expires_at=old, label=f"svc {i}") for i in range(2)]

    async with AsyncSessionLocal() as db:
        report = await retention.purge_expired_service_keys(db, execute=True, now=now, retention=RETENTION)

    assert (report.candidates, report.deleted, report.batches) == (2, 2, 1)
    assert report.batch_size == retention.DEFAULT_BATCH_SIZE == 5000
    assert await _present({k.id for k in keys}) == set()


async def test_invalid_arguments_are_rejected_before_touching_the_database():
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        with pytest.raises(ValueError, match="batch_size"):
            await retention.purge_expired_service_keys(db, now=now, batch_size=0)
        with pytest.raises(ValueError, match="pause_s"):
            await retention.purge_expired_service_keys(db, now=now, pause_s=-1)
        with pytest.raises(ValueError, match="retention"):
            await retention.purge_expired_service_keys(db, now=now, retention=timedelta(days=-1))
        with pytest.raises(ValueError, match="timezone-aware"):
            await retention.purge_expired_service_keys(db, now=datetime(2026, 9, 21))


def test_default_retention_reads_env_and_defaults_to_seven_days(monkeypatch):
    monkeypatch.delenv(retention.RETENTION_DAYS_ENV, raising=False)
    assert retention.default_retention() == timedelta(days=7)
    monkeypatch.setenv(retention.RETENTION_DAYS_ENV, "3")
    assert retention.default_retention() == timedelta(days=3)
    monkeypatch.setenv(retention.RETENTION_DAYS_ENV, "0")
    assert retention.default_retention() == timedelta(0)
    monkeypatch.setenv(retention.RETENTION_DAYS_ENV, "-1")
    with pytest.raises(ValueError):
        retention.default_retention()


def test_cli_defaults_to_dry_run_and_validates_numbers():
    from scripts.purge_expired_service_keys import build_parser

    parser = build_parser()
    args = parser.parse_args([])
    assert (args.execute, args.retention_days, args.batch_size, args.pause_s) == (False, None, 5000, 0.2)

    args = parser.parse_args(["--execute", "--retention-days", "0", "--batch-size", "1", "--pause-s", "0"])
    assert (args.execute, args.retention_days, args.batch_size, args.pause_s) == (True, 0, 1, 0.0)

    for bad in (["--batch-size", "0"], ["--retention-days", "-1"], ["--pause-s", "-0.5"]):
        with pytest.raises(SystemExit):
            parser.parse_args(bad)
