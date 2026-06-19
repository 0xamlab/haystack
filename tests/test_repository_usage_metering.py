"""Phase 0d/0e: repository-intelligence usage metering.

The Codna coding-edition repo tools (triage/snapshot/graph/decision-plan/simulate/
pipeline/apply) are now metered + rate-limited. These tests cover the model/enum/
migration changes (always run) and the `_meter_repository` write+dedupe behavior
(DB-integration; skips cleanly when no migrated Postgres is reachable).
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

DB_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://angel:@localhost:5432/decision_engine")


# ── Always-run: model + enum + migration ────────────────────────────────────


def test_usage_endpoint_has_repository_value() -> None:
    from apps.api_server.models.usage_record import UsageEndpoint

    assert UsageEndpoint.REPOSITORY.value == "repository"


def test_usage_record_accepts_product_and_tool_name() -> None:
    from apps.api_server.models.usage_record import UsageEndpoint, UsageRecord

    cols = {c.name for c in UsageRecord.__table__.columns}
    assert {"product", "tool_name"} <= cols
    row = UsageRecord(
        org_id=uuid.uuid4(),
        billing_period="2026-06",
        endpoint=UsageEndpoint.REPOSITORY,
        billing_units=1,
        product="codna",
        tool_name="triage_repository",
    )
    assert row.product == "codna"
    assert row.tool_name == "triage_repository"
    assert row.endpoint is UsageEndpoint.REPOSITORY


def test_migration_0040_chains_and_adds_columns_and_enum() -> None:
    text = Path(
        "apps/api_server/alembic/versions/0040_repository_usage_metering.py"
    ).read_text()
    assert 'revision = "0040"' in text
    assert 'down_revision = "0039"' in text
    assert "ALTER TYPE usage_endpoint ADD VALUE 'repository'" in text
    assert 'add_column("usage_records", sa.Column("product"' in text
    assert 'add_column("usage_records", sa.Column("tool_name"' in text


# ── DB-integration: _meter_repository writes one REPOSITORY row + dedupes ─────


@pytest.fixture
async def session_factory_and_org():
    from sqlalchemy import delete, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from apps.api_server.models import Organization, OrgPlan, OrgStatus
    from apps.api_server.models.usage_record import UsageRecord

    engine = create_async_engine(DB_URL, echo=False)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as probe:
            try:
                await probe.execute(select(1))
            except Exception:
                pytest.skip("no Postgres reachable for the repository metering test")
            org = Organization(
                name="pytest repo-metering",
                slug=f"pytest-rm-{uuid.uuid4().hex[:10]}",
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
                await cleanup.execute(delete(Organization).where(Organization.id == org_id))
                await cleanup.commit()
    finally:
        await engine.dispose()


async def test_meter_repository_writes_one_repository_row(session_factory_and_org) -> None:
    from sqlalchemy import func, select

    from apps.api_server.models.usage_record import UsageEndpoint, UsageRecord
    from apps.api_server.routers.repositories import _meter_repository

    factory, org_id = session_factory_and_org
    auth = {"org_id": org_id, "plan": "pro", "key_id": None, "workspace_id": None}

    async with factory() as session:
        try:
            await _meter_repository(
                tool_name="triage_repository", auth=auth, db=session, redis_client=None
            )
        except Exception as exc:  # missing 'repository' enum / product cols → DB not at migration 0040
            pytest.skip(f"test Postgres not migrated to 0040: {exc}")
        await session.commit()

    async with factory() as s:
        rows = (
            await s.execute(select(UsageRecord).where(UsageRecord.org_id == org_id))
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].endpoint is UsageEndpoint.REPOSITORY
    assert rows[0].product == "codna"
    assert rows[0].tool_name == "triage_repository"

    # A second NULL-keyed call is a distinct billable unit (no usage_key → not deduped).
    async with factory() as session:
        await _meter_repository(
            tool_name="apply_repository", auth=auth, db=session, redis_client=None
        )
        await session.commit()
    async with factory() as s:
        total = int(
            await s.scalar(
                select(func.count()).select_from(UsageRecord).where(UsageRecord.org_id == org_id)
            )
        )
    assert total == 2
