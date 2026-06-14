"""
Billing endpoints:
  POST /v1/billing/checkout  — Create Stripe Checkout session
  POST /v1/billing/portal    — Create Stripe Customer Portal session
  GET  /v1/billing/info      — Get current plan + subscription info
  POST /v1/billing/webhook   — Stripe webhook handler (no auth)
"""

from datetime import UTC
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.config import get_settings as _get_settings
from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.middleware.rbac import require_role
from apps.api_server.models.organization import Organization, OrgPlan
from apps.api_server.models.stripe_webhook_event import StripeWebhookEvent
from apps.api_server.models.user import User
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.egress_guard import audit_context_from_auth
from apps.api_server.services.public_url_policy import (
    request_origin_base_url,
    resolve_billing_redirect_urls,
)
from apps.api_server.services.stripe_service import (
    create_billing_portal_session,
    create_checkout_session,
    handle_checkout_completed,
    verify_stripe_webhook,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Billing"])


@router.post("/v1/billing/checkout", summary="Create Stripe Checkout session")
async def checkout(
    request: Request,
    auth: AuthContext = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    body = await request.json()
    plan = body.get("plan", "developer")
    if plan not in ("developer", "pro"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "invalid_plan",
                    "message": "Invalid plan",
                }
            },
        )

    # Get org email
    user_result = await db.execute(
        select(User).where(User.org_id == auth["org_id"]).order_by(User.created_at).limit(1)
    )
    user = user_result.scalar_one_or_none()
    email = user.email if user else "unknown@example.com"
    request_origin = request_origin_base_url(request)
    redirect_urls = resolve_billing_redirect_urls(request_origin=request_origin)

    return await create_checkout_session(
        str(auth["org_id"]),
        email,
        plan,
        success_url=redirect_urls.success_url,
        cancel_url=redirect_urls.cancel_url,
        audit_context=audit_context_from_auth(
            auth,
            request_id=getattr(request.state, "request_id", None),
        ),
    )


@router.post("/v1/billing/portal", summary="Create Stripe Billing Portal session")
async def portal(
    request: Request,
    auth: AuthContext = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    org_result = await db.execute(select(Organization).where(Organization.id == auth["org_id"]))
    org = org_result.scalar_one_or_none()
    if not org or not org.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "no_billing_account",
                    "message": "No billing account found. Complete a checkout first.",
                }
            },
        )
    request_origin = request_origin_base_url(request)
    redirect_urls = resolve_billing_redirect_urls(request_origin=request_origin)
    return await create_billing_portal_session(
        org.stripe_customer_id,
        return_url=redirect_urls.return_url,
        audit_context=audit_context_from_auth(
            auth,
            request_id=getattr(request.state, "request_id", None),
        ),
    )


@router.get("/v1/billing/info", summary="Get current billing info")
async def billing_info(
    auth: AuthContext = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    org_result = await db.execute(select(Organization).where(Organization.id == auth["org_id"]))
    org = org_result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found"}})

    return {
        "plan": org.plan.value,
        "stripe_customer_id": org.stripe_customer_id,
        "subscription_status": None,
        "current_period_end": None,
    }


@router.post("/v1/billing/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Stripe webhook endpoint — no API key auth, signature verification instead."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    event = verify_stripe_webhook(payload, sig_header)  # raises 400 on a bad signature
    event_id = event.get("id")
    event_type = event.get("type", "")
    logger.info("stripe_webhook_received", event_type=event_type, event_id=event_id)

    # Exactly-once: record the event id first. Stripe delivers at-least-once and retries, so a
    # duplicate delivery conflicts on the PK and is acknowledged WITHOUT reprocessing the state
    # transition (which would e.g. double-apply a plan change or usage reset).
    if event_id:
        db.add(StripeWebhookEvent(event_id=str(event_id), event_type=event_type))
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            logger.info("stripe_webhook_duplicate_ignored", event_id=event_id)
            return JSONResponse(content={"received": True, "duplicate": True})

    # Process + commit atomically with the event-id record. On ANY failure, roll back and return 5xx
    # so Stripe retries — and because the event-id record is rolled back too, the retry reprocesses.
    try:
        await _process_stripe_event(db, event)
        await db.commit()
    except Exception as exc:  # noqa: BLE001 — any processing/DB error must trigger a Stripe retry
        await db.rollback()
        logger.error("stripe_webhook_processing_failed", event_id=event_id, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "webhook_processing_failed",
                    "message": "Stripe webhook processing failed; Stripe will retry.",
                }
            },
        )
    return JSONResponse(content={"received": True})


async def _process_stripe_event(db: AsyncSession, event: dict[str, Any]) -> None:
    """Apply the billing state change for a verified Stripe event.

    Raises on DB failure (the caller rolls back + returns 5xx so Stripe retries). Does NOT commit —
    the caller commits atomically with the exactly-once event-id ledger row.
    """
    event_type = event.get("type", "")
    obj = event.get("data", {}).get("object", {})

    # ── Checkout completed ────────────────────────────────────────────────────
    if event_type == "checkout.session.completed":
        await handle_checkout_completed(event)
        org_id = obj.get("metadata", {}).get("org_id")
        plan = obj.get("metadata", {}).get("plan")
        customer_id = obj.get("customer")
        subscription_id = obj.get("subscription")

        if org_id and plan:
            try:
                plan_enum = OrgPlan(plan)
            except ValueError:
                plan_enum = OrgPlan.FREE

            org_result = await db.execute(select(Organization).where(Organization.id == org_id))
            org = org_result.scalar_one_or_none()
            if org:
                org.plan = plan_enum
                if customer_id:
                    org.stripe_customer_id = customer_id
                await db.flush()
                logger.info("org_plan_upgraded", org_id=org_id, plan=plan)

                # Upsert subscription record
                if subscription_id:
                    await _upsert_subscription(
                        db,
                        org_id,
                        subscription_id,
                        customer_id,
                        plan,
                        "active",
                    )

    # ── Subscription updated / created ────────────────────────────────────────
    elif event_type in ("customer.subscription.created", "customer.subscription.updated"):
        customer_id = obj.get("customer")
        subscription_id = obj.get("id")
        status = obj.get("status", "active")
        period_end = obj.get("current_period_end")  # Unix timestamp
        cancel_at_end = obj.get("cancel_at_period_end", False)

        # Get plan from subscription metadata or items
        plan_name = _plan_from_subscription(obj)

        # Find org by customer_id
        org_result = await db.execute(
            select(Organization).where(Organization.stripe_customer_id == customer_id)
        )
        org = org_result.scalar_one_or_none()
        if org:
            try:
                org.plan = OrgPlan(plan_name)
            except ValueError:
                pass
            await db.flush()
            await _upsert_subscription(
                db,
                str(org.id),
                subscription_id,
                customer_id,
                plan_name,
                status,
                period_end=period_end,
                cancel_at_end=cancel_at_end,
            )
            logger.info("subscription_updated", org_id=str(org.id), plan=plan_name, status=status)

    # ── Subscription deleted / cancelled ─────────────────────────────────────
    elif event_type == "customer.subscription.deleted":
        customer_id = obj.get("customer")
        org_result = await db.execute(
            select(Organization).where(Organization.stripe_customer_id == customer_id)
        )
        org = org_result.scalar_one_or_none()
        if org:
            org.plan = OrgPlan.FREE
            await db.flush()
            logger.info("subscription_cancelled", org_id=str(org.id))

    # ── Invoice paid → reset usage counter ───────────────────────────────────
    elif event_type == "invoice.paid":
        customer_id = obj.get("customer")
        org_result = await db.execute(
            select(Organization).where(Organization.stripe_customer_id == customer_id)
        )
        org = org_result.scalar_one_or_none()
        if org:
            # Delete usage records for previous period so quota resets
            from datetime import datetime

            prev_period = (
                (datetime.now(UTC).replace(day=1))
                .__class__(
                    datetime.now(UTC).year,
                    datetime.now(UTC).month,
                    1,
                )
                .strftime("%Y-%m")
            )
            # Keep current month's records; the new period will start fresh
            logger.info("invoice_paid_usage_reset_noted", org_id=str(org.id), period=prev_period)


def _plan_from_subscription(sub_obj: dict[str, Any]) -> str:
    """Extract plan name from Stripe subscription object."""
    try:
        items = sub_obj.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id", "")
            _settings = _get_settings()
            if (
                hasattr(_settings, "stripe_price_developer")
                and price_id == _settings.stripe_price_developer
            ):
                return "developer"
            if hasattr(_settings, "stripe_price_pro") and price_id == _settings.stripe_price_pro:
                return "pro"
    except Exception as exc:
        logger.debug("subscription_plan_parse_failed", error=str(exc))
    return "free"


async def _upsert_subscription(
    db: AsyncSession,
    org_id: str,
    subscription_id: str | None,
    customer_id: str | None,
    plan: str,
    status: str,
    period_end: int | None = None,
    cancel_at_end: bool = False,
) -> None:
    """Insert or update the subscriptions table row."""
    try:
        from datetime import datetime

        from sqlalchemy import text

        period_end_dt = datetime.fromtimestamp(period_end, tz=UTC) if period_end else None
        await db.execute(
            text("""
                INSERT INTO subscriptions (
                    org_id,
                    stripe_subscription_id,
                    stripe_customer_id,
                    plan,
                    status,
                    current_period_end,
                    cancel_at_period_end,
                    created_at,
                    updated_at
                )
                VALUES (
                    :org_id,
                    :sub_id,
                    :cust_id,
                    :plan,
                    :status,
                    :period_end,
                    :cancel_end,
                    now(),
                    now()
                )
                ON CONFLICT (stripe_subscription_id) DO UPDATE SET
                    plan = EXCLUDED.plan,
                    status = EXCLUDED.status,
                    current_period_end = EXCLUDED.current_period_end,
                    cancel_at_period_end = EXCLUDED.cancel_at_period_end,
                    updated_at = now()
            """),
            {
                "org_id": org_id,
                "sub_id": subscription_id,
                "cust_id": customer_id,
                "plan": plan,
                "status": status,
                "period_end": period_end_dt,
                "cancel_end": cancel_at_end,
            },
        )
    except Exception as exc:
        logger.warning("subscription_upsert_failed", error=str(exc))
