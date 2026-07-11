"""
Simulation persistence helpers.

Used by:
  - apps/worker/tasks/simulation_task.py  (Celery, after HTTP response sent)
  - apps/api_server/routers/simulate.py   (in-process fallback when Celery unavailable)

Writes SimulationRun, AuditEvent, UsageRecord, increments Redis quota counter,
and optionally stores the full result in object storage.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.config import SettingsProxy
from apps.api_server.services.egress_guard import EgressAuditContext

logger = structlog.get_logger(__name__)
settings = SettingsProxy()


async def persist_simulation_run(
    db: AsyncSession,
    persist_meta: dict[str, Any],
    plan: str,
    actor_email: str,
    client_ip: str,
    redis_client: object | None = None,
) -> None:
    """
    Write all accounting records for a completed simulation.

    persist_meta keys (produced by run_simulation_fast):
      run_id, org_id, api_key_id, mode, request_hash, execution_ms,
      engine_version, scenarios_run, result_hash, recommended_action,
      confidence, expected_value, probability_of_loss, std_deviation,
      rationale, simulation_model, envelope_json
    """
    from apps.api_server.models.simulation_run import (
        ExecutionType,
        RunStatus,
        SimulationMode,
        SimulationRun,
    )
    from apps.api_server.models.usage_record import UsageEndpoint, UsageRecord
    from apps.api_server.services.audit_service import write_audit_event

    run_id = uuid.UUID(persist_meta["run_id"])
    org_id = uuid.UUID(persist_meta["org_id"])
    workspace_id = (
        uuid.UUID(persist_meta["workspace_id"]) if persist_meta.get("workspace_id") else None
    )
    api_key_id = uuid.UUID(persist_meta["api_key_id"]) if persist_meta.get("api_key_id") else None
    now = datetime.now(UTC)

    # ── 1. Insert SimulationRun ────────────────────────────────────────────
    run = SimulationRun(
        id=run_id,
        org_id=org_id,
        workspace_id=workspace_id,
        api_key_id=api_key_id,
        mode=SimulationMode(persist_meta["mode"]),
        request_hash=persist_meta["request_hash"],
        status=RunStatus.COMPLETED,
        execution_type=ExecutionType.SYNC,
        started_at=now,
        completed_at=now,
        duration_ms=persist_meta["execution_ms"],
        engine_version=persist_meta["engine_version"],
        scenarios_run=persist_meta["scenarios_run"],
        billing_units=1,
        result_hash=persist_meta["result_hash"],
        recommended_action=persist_meta["recommended_action"],
        confidence=persist_meta["confidence"],
        expected_value=persist_meta["expected_value"],
        probability_of_loss=persist_meta["probability_of_loss"],
        std_deviation=persist_meta["std_deviation"],
        rationale=persist_meta["rationale"],
    )
    # Wave-C exactly-once billing: idempotent on the SimulationRun PK. On a Celery retry (acks_late)
    # the run may already be committed — a bare re-insert would raise IntegrityError and abort the
    # whole transaction BEFORE the UsageRecord, so the run would never be billed (UNDER-count). Get-
    # or-create avoids that; on a retry we reuse the existing run and skip the result-reference write.
    existing_run = await db.get(SimulationRun, run_id)
    if existing_run is None:
        try:
            run.simulation_model = persist_meta["simulation_model"]
        except Exception as exc:
            logger.debug("simulation_model_persist_failed", run_id=str(run_id), error=str(exc))
        db.add(run)
        await db.flush()
        await _persist_result_reference(run=run, persist_meta=persist_meta)
    else:
        run = existing_run

    # ── 2. Audit event ────────────────────────────────────────────────────
    await write_audit_event(
        db=db,
        org_id=org_id,
        workspace_id=workspace_id,
        action="simulate",
        actor_email=actor_email,
        resource_type="simulation_run",
        resource_id=persist_meta["run_id"],
        ip_address=client_ip,
        metadata={
            "recommended_action": persist_meta["recommended_action"],
            "confidence": persist_meta["confidence"],
        },
    )

    # ── 3. Usage record ───────────────────────────────────────────────────
    from apps.api_server.services.quota_service import _current_billing_period

    period = _current_billing_period()
    # Wave-C exactly-once billing: the UsageRecord is keyed by a logical-run usage_key and guarded by
    # a PARTIAL-unique index (migration 0034). Insert inside a SAVEPOINT so a duplicate (a retry or a
    # cross-replica race) raises IntegrityError that rolls back ONLY this insert — never the whole
    # transaction — and leaves usage_inserted=False. The quota counter AND the (real-money) Stripe
    # push then fire ONLY on a genuine first insert, so a retry neither under-bills nor double-bills.
    from sqlalchemy.exc import IntegrityError

    usage_inserted = False
    try:
        async with db.begin_nested():
            record = UsageRecord(
                org_id=org_id,
                workspace_id=workspace_id,
                api_key_id=api_key_id,
                simulation_run_id=run_id,
                billing_period=period,
                endpoint=UsageEndpoint.SIMULATE,
                billing_units=1,
                scenarios_run=persist_meta["scenarios_run"],
                usage_key=f"sim:{run_id}",
            )
            db.add(record)
            await db.flush()
        usage_inserted = True
    except IntegrityError:
        # already billed for this logical run (Celery retry / cross-replica race) — not an error.
        usage_inserted = False
        logger.info("usage_record_already_billed", run_id=str(run_id), org_id=str(org_id))

    from apps.api_server.services.plan_limits import is_unmetered_execution_plan

    metered_execution = not is_unmetered_execution_plan(plan)

    # ── 4. Increment Redis quota counter (only for quota-governed plans) ───
    if usage_inserted and metered_execution and redis_client is not None:
        try:
            from apps.api_server.services.quota_service import incr_quota_counter

            await incr_quota_counter(org_id, period, redis_client)
        except Exception as exc:
            logger.warning("quota_counter_incr_failed", org_id=str(org_id), error=str(exc))

    # Algenta licenses are flat per device. Its local usage record supports customer-owned audit,
    # but execution counts must never leave the deployment as Stripe meter events.
    if usage_inserted and metered_execution:
        import asyncio

        asyncio.create_task(_push_stripe_usage(org_id=org_id, billing_units=1, db=db))

    # ── 6. Object storage (enterprise — off hot path) ─────────────────────
    logger.info(
        "simulation_persisted",
        run_id=persist_meta["run_id"],
        org_id=str(org_id),
        execution_ms=persist_meta["execution_ms"],
    )


async def _push_stripe_usage(org_id: uuid.UUID, billing_units: int, db: AsyncSession) -> None:
    try:
        from sqlalchemy import select

        from apps.api_server.models.organization import Organization
        from apps.api_server.services.stripe_service import (
            stripe_api_request,
            stripe_metering_enabled,
        )

        if not settings.stripe_secret_key or settings.stripe_secret_key.startswith("sk_test"):
            return
        if not stripe_metering_enabled():
            return
        org_result = await db.execute(select(Organization).where(Organization.id == org_id))
        org = org_result.scalar_one_or_none()
        if not org or not org.stripe_customer_id:
            return
        import time as _time

        await stripe_api_request(
            method="POST",
            path="/v1/billing/meter_events",
            surface="persist_metering_flush",
            audit_context=EgressAuditContext(org_id=org_id),
            timeout=8,
            headers={"Authorization": f"Bearer {settings.stripe_secret_key}"},
            data={
                "event_name": "simulation_run",
                "payload[stripe_customer_id]": org.stripe_customer_id,
                "payload[value]": str(billing_units),
                "timestamp": str(int(_time.time())),
            },
        )
    except Exception as exc:
        logger.warning("stripe_usage_push_failed", org_id=str(org_id), error=str(exc))


async def _persist_result_reference(run: Any, persist_meta: dict[str, Any]) -> None:
    """Persist the full result envelope and attach the storage reference to the run."""
    if not settings.result_storage_enabled:
        return

    from apps.api_server.services.storage_service import (
        ResultStorageUnavailableError,
        store_result,
    )

    run_id = uuid.UUID(persist_meta["run_id"])
    org_id = uuid.UUID(persist_meta["org_id"])
    try:
        stored = await store_result(
            org_id=org_id,
            run_id=run_id,
            result_data=persist_meta.get("envelope_json", {}),
        )
    except ResultStorageUnavailableError as exc:
        logger.warning(
            "result_storage_unavailable",
            run_id=str(run_id),
            org_id=str(org_id),
            error=str(exc),
            fallback_allowed=settings.allow_runtime_fallbacks,
        )
        if settings.allow_runtime_fallbacks:
            return
        raise RuntimeError("Result storage backend unavailable.") from exc

    run.output_blob_ref = stored.blob_ref
    run.result_url = stored.result_url
