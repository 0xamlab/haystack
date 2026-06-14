"""Wave 2 PR-3: free-tier cost caps — PlanConfig values + concurrent-jobs enforcement.

The concurrent_jobs cap is enforced now (job_service.enforce_concurrent_jobs on async submit). The
storage_gb + llm_spend_cap_usd_month caps are DEFINED + surfaced via /v1/limits; their enforcement
lands with their accounting backends (storage accounting; managed-LLM metering / D3 = PR-5).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from apps.api_server.services import plan_limits
from apps.api_server.services.job_service import enforce_concurrent_jobs


def test_free_tier_caps_match_agreed_defaults():
    free = plan_limits.get("free")
    assert (free.concurrent_jobs, free.storage_gb, free.llm_spend_cap_usd_month) == (1, 1, 5)


def test_paid_and_unlimited_caps():
    assert plan_limits.get("developer").concurrent_jobs == 5
    assert plan_limits.get("pro").concurrent_jobs == 20
    assert plan_limits.get("team").concurrent_jobs == 50
    ent = plan_limits.get("enterprise")
    assert (ent.concurrent_jobs, ent.storage_gb, ent.llm_spend_cap_usd_month) == (0, 0, 0)  # unlimited


async def _seed_org():
    from apps.api_server.db.session import AsyncSessionLocal
    from apps.api_server.models.organization import Organization, OrgPlan, OrgStatus

    async with AsyncSessionLocal() as s:
        org = Organization(
            name="Caps Test", slug=f"caps-{uuid.uuid4().hex[:8]}", plan=OrgPlan.FREE, status=OrgStatus.ACTIVE
        )
        s.add(org)
        await s.commit()
        return org.id


async def _add_queued_job(org_id):
    from apps.api_server.db.session import AsyncSessionLocal
    from apps.api_server.services.job_service import create_job

    async with AsyncSessionLocal() as s:
        await create_job(run_id=None, org_id=org_id, db=s)
        await s.commit()


async def test_concurrent_jobs_enforced_at_cap():
    from apps.api_server.db.session import AsyncSessionLocal

    org_id = await _seed_org()
    # 0 in-flight, free cap = 1 → allowed.
    async with AsyncSessionLocal() as s:
        await enforce_concurrent_jobs(org_id, "free", s)
    # 1 in-flight, free cap = 1 → next submission blocked.
    await _add_queued_job(org_id)
    async with AsyncSessionLocal() as s:
        with pytest.raises(HTTPException) as exc:
            await enforce_concurrent_jobs(org_id, "free", s)
    assert exc.value.status_code == 429
    assert exc.value.detail["error"]["code"] == "concurrent_jobs_exceeded"


async def test_unlimited_plan_never_blocks():
    from apps.api_server.db.session import AsyncSessionLocal

    org_id = await _seed_org()
    await _add_queued_job(org_id)
    await _add_queued_job(org_id)
    async with AsyncSessionLocal() as s:
        await enforce_concurrent_jobs(org_id, "enterprise", s)  # cap=0 (unlimited) → no raise
