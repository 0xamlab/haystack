"""Retention purge for expired short-lived SERVICE keys (``api_keys.is_service = true``).

WHY THIS EXISTS: ``routers/github_webhooks.py::codna_webhook_engine_key`` mints one
``is_service`` key with a 2 h TTL per bridge call from codna-webhook, and nothing ever deleted
them. Measured read-only on the hosted codna-pg on 2026-09-21: 28,367 ``api_keys`` rows, 28,363
of them service keys, 28,350 already expired, ~1,131 new ones a day, 15 MB (8.9 MB of indexes)
= 83 % of all user data, ``n_tup_del = 0``. An expired key is dead weight: auth rejects it
(``auth_service.is_api_key_expired``), so it can never authenticate again.

SCOPE, deliberately narrow (every clause is a safety property the tests pin):
  * only ``is_service = true``            -- a human's key is never a candidate, expired or not;
  * only ``expires_at IS NOT NULL``       -- a key with no expiry is never a candidate;
  * only ``expires_at < now - retention`` -- unexpired keys, and keys expired for less than the
    retention window (default 7 days, so an incident can still be traced against the key that
    was used), are never candidates;
  * only keys with NO ``device_registrations`` rows -- that FK is ON DELETE CASCADE and a purge
    must never take a registration with it. The other four FKs onto ``api_keys`` (usage_records,
    llm_usage_records, simulation_runs, deployment_license_registrations) are ON DELETE SET NULL:
    their rows survive with ``api_key_id = NULL``, the existing behaviour for a deleted key.
    ``audit_events`` has no reference onto ``api_keys``.

TENANT-SCOPED, like every other query on an org-owned model here (the ``org_scope`` reliability
guard enforces it): the purge first lists the tenants that own candidates, then counts and
deletes per tenant with an explicit ``APIKey.org_id == org_id`` predicate. Each DELETE is
therefore bounded to one org as well as to one batch (``... WHERE id IN (SELECT ... LIMIT n)``,
one commit per batch), so a first run over tens of thousands of rows never holds one long
transaction against the table the API authenticates on. Dry-run (``execute=False``) only counts.

Entry point: ``scripts/purge_expired_service_keys.py`` (dry-run by default), scheduled by
``.github/workflows/db-maintenance.yml`` inside an ephemeral Machine of the deployed codna-api
image (release_command-style ``fly console``), so the database URL never leaves Fly.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.models.api_key import APIKey
from apps.api_server.models.device import DeviceRegistration

RETENTION_DAYS_ENV = "ALGENTA_SERVICE_KEY_RETENTION_DAYS"
DEFAULT_RETENTION_DAYS = 7
DEFAULT_BATCH_SIZE = 5000


def default_retention() -> timedelta:
    """Retention window: ``ALGENTA_SERVICE_KEY_RETENTION_DAYS`` (default 7). Never negative."""
    raw = os.environ.get(RETENTION_DAYS_ENV, "").strip()
    days = int(raw) if raw else DEFAULT_RETENTION_DAYS
    if days < 0:
        raise ValueError(f"{RETENTION_DAYS_ENV} must be >= 0, got {days}")
    return timedelta(days=days)


def purge_cutoff(now: datetime, retention: timedelta) -> datetime:
    """Keys whose ``expires_at`` is strictly before this instant are candidates."""
    if retention < timedelta(0):
        raise ValueError(f"retention must be >= 0, got {retention}")
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now - retention


def _expired_service_key_clauses(cutoff: datetime) -> tuple:
    """The row predicate shared by tenant enumeration and the per-tenant count/delete."""
    return (
        APIKey.is_service.is_(True),
        APIKey.expires_at.is_not(None),
        APIKey.expires_at < cutoff,
        ~exists().where(DeviceRegistration.api_key_id == APIKey.id),
    )


async def tenants_with_purge_candidates(db: AsyncSession, *, cutoff: datetime) -> list[uuid.UUID]:
    """Tenants (``org_id``) that own at least one candidate -- the scope for everything below."""
    result = await db.execute(
        select(APIKey.org_id)
        .where(*_expired_service_key_clauses(cutoff))
        .distinct()
        .order_by(APIKey.org_id)
    )
    return list(result.scalars().all())


def _candidate_ids(org_id: uuid.UUID, cutoff: datetime, *, limit: int | None = None):
    stmt = (
        select(APIKey.id)
        .where(APIKey.org_id == org_id)
        .where(*_expired_service_key_clauses(cutoff))
    )
    if limit is not None:
        stmt = stmt.order_by(APIKey.expires_at, APIKey.id).limit(limit)
    return stmt


async def count_purge_candidates(db: AsyncSession, *, org_id: uuid.UUID, cutoff: datetime) -> int:
    result = await db.execute(
        select(func.count()).select_from(_candidate_ids(org_id, cutoff).subquery())
    )
    return int(result.scalar_one())


@dataclass(frozen=True)
class PurgeReport:
    """``candidates`` is the per-tenant count taken before that tenant's deletes; ``deleted`` is
    what the DELETE statements actually removed (equal unless rows were drained by, or became
    candidates during, the run); ``batches`` is the number of DELETE statements issued."""

    execute: bool
    cutoff: datetime
    tenants: int
    candidates: int
    deleted: int
    batches: int
    batch_size: int

    def as_dict(self) -> dict[str, object]:
        return {
            "execute": self.execute,
            "cutoff": self.cutoff.isoformat(),
            "tenants": self.tenants,
            "candidates": self.candidates,
            "deleted": self.deleted,
            "batches": self.batches,
            "batch_size": self.batch_size,
        }


async def purge_expired_service_keys(
    db: AsyncSession,
    *,
    execute: bool = False,
    now: datetime | None = None,
    retention: timedelta | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    pause_s: float = 0.0,
) -> PurgeReport:
    """Count (and with ``execute=True`` delete, per tenant and in batches) expired short-lived
    service keys.

    ``now`` defaults to the current UTC time; ``retention`` to :func:`default_retention`.
    Each batch is its own committed, tenant-scoped statement; ``pause_s`` sleeps between batches
    so a large first run yields to the API's own traffic.
    """
    if batch_size < 1:
        raise ValueError(f"batch_size must be >= 1, got {batch_size}")
    if pause_s < 0:
        raise ValueError(f"pause_s must be >= 0, got {pause_s}")
    now = now or datetime.now(UTC)
    cutoff = purge_cutoff(now, default_retention() if retention is None else retention)

    tenants = await tenants_with_purge_candidates(db, cutoff=cutoff)
    candidates = 0
    deleted = 0
    batches = 0
    for org_id in tenants:
        n = await count_purge_candidates(db, org_id=org_id, cutoff=cutoff)
        candidates += n
        if not (execute and n):
            continue
        # A partial batch means this tenant is exhausted (or a concurrent run drained it). After a
        # FULL batch, a tenant-scoped re-count decides whether to continue: n being an exact
        # multiple of batch_size ends with a cheap COUNT instead of a trailing empty DELETE, and
        # rows that became candidates meanwhile are still picked up rather than left behind.
        while True:
            result = await db.execute(
                delete(APIKey)
                .where(APIKey.org_id == org_id)
                .where(APIKey.id.in_(_candidate_ids(org_id, cutoff, limit=batch_size)))
                .execution_options(synchronize_session=False)
            )
            await db.commit()
            batches += 1
            deleted += result.rowcount
            if result.rowcount < batch_size:
                break
            if not await count_purge_candidates(db, org_id=org_id, cutoff=cutoff):
                break
            if pause_s:
                await asyncio.sleep(pause_s)
    return PurgeReport(
        execute=execute,
        cutoff=cutoff,
        tenants=len(tenants),
        candidates=candidates,
        deleted=deleted,
        batches=batches,
        batch_size=batch_size,
    )
