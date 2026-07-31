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
from apps.api_server.models.audit_event import AuditAction
from apps.api_server.models.organization import Organization, OrgPlan
from apps.api_server.models.stripe_webhook_event import StripeWebhookEvent
from apps.api_server.models.user import User, UserRole, UserStatus
from apps.api_server.services.audit_service import write_audit_event
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.device_service import (
    revoke_excess_org_devices,
    revoke_org_devices,
)
from apps.api_server.services.egress_guard import audit_context_from_auth
from apps.api_server.services.entitlement_service import entitlement_for_org
from apps.api_server.services.plan_limits import device_limit as _plan_device_limit
from apps.api_server.services.plan_limits import is_per_device_plan
from apps.api_server.services.plan_limits import local_runtime_allowed as _plan_local_runtime
from apps.api_server.services.product_registry import (
    all_products,
    get_product,
    legacy_default_product,
    product_for_plan,
    product_for_public_api_host,
)
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
from apps.api_server.services.team_seats import seat_limit as _seat_limit

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Billing"])

# Stripe subscription statuses that mean dunning is EXHAUSTED — the customer stopped paying and
# Stripe has given up retrying. These downgrade to Community (anti-pay-once-leave). We deliberately
# do NOT include "past_due": that is still inside Stripe's retry window (a transient/declined card
# that may recover), so cutting the customer off then would be over-enforcement. Letting Stripe's
# own dunning ladder run first gives the ~one-renewal-cycle grace the short license TTL expects.
_DELINQUENT_TERMINAL_STATUSES = frozenset({"unpaid", "canceled", "incomplete_expired"})


async def _suspend_excess_members(db: AsyncSession, org_id: Any, seat_cap: int) -> int:
    """On downgrade, suspend active NON-OWNER members beyond the new plan's seat cap.
    Owners are always kept; the oldest members fill the remaining seats. Mirrors the
    conservative device-revocation policy. seat_cap <= 0 means unlimited → no-op."""
    if seat_cap <= 0:
        return 0
    result = await db.execute(
        select(User)
        .where(User.org_id == org_id, User.status == UserStatus.ACTIVE)
        .order_by(User.created_at)
    )
    members = list(result.scalars().all())
    owners = [u for u in members if u.role == UserRole.OWNER]
    non_owners = [u for u in members if u.role != UserRole.OWNER]
    keep = {u.id for u in non_owners[: max(0, seat_cap - len(owners))]}
    suspended = 0
    for u in non_owners:
        if u.id not in keep:
            u.status = UserStatus.SUSPENDED
            suspended += 1
    return suspended


def _registered_product_ids() -> str:
    """The registered brands, for an error message that lets a caller fix the request."""
    return ", ".join(sorted(cfg.id for cfg in all_products()))


def _invalid_product_error(product: str) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={
            "error": {
                "code": "invalid_product",
                "message": (
                    f"Unknown product '{product}'. Registered products: "
                    f"{_registered_product_ids()}."
                ),
            }
        },
    )


def _brand_pin(request: Request) -> str | None:
    """The ONE brand this endpoint may price, or ``None`` when this host speaks for no single brand.

    Resolved from authoritative signals only, most explicit first:
      1. ``ALGENTA_PRODUCT`` — the deployment declaring its own edition (also used by the MCP edition).
      2. the request's ``Host`` matched against the registry's ``public_api_base`` — so a brand host is
         pinned to its brand with zero configuration.
    A non-brand host (internal Fly name, IP, ``localhost``) on an unconfigured deployment yields
    ``None``: that is the shared multi-brand engine, where cross-brand pricing is the point.

    ``X-Forwarded-Host`` is consulted only when ``Host`` names no brand, because an edge that rewrites
    ``Host`` to an internal origin name would otherwise un-pin the deployment and quietly restore the
    old wrong answer. Neither header is a trust boundary (see ``product_for_public_api_host``); a caller
    who forges one gains nothing it could not get by naming the brand outright on an unpinned host.
    """
    configured = (_get_settings().deployment_product or "").strip().lower()
    if configured:
        return configured
    from_host = product_for_public_api_host(request.headers.get("host"))
    if from_host is not None:
        return from_host
    forwarded = (request.headers.get("x-forwarded-host") or "").split(",")[0]
    return product_for_public_api_host(forwarded)


@router.get("/billing/plans", summary="Public — active plans for an app, dynamic from Stripe")
async def public_plans(request: Request, app: str | None = None) -> dict[str, Any]:
    """Plan titles/prices/descriptions/features straight from Stripe (no hardcoding). Public —
    pricing is public (a pricing page renders before sign-in). Free + Enterprise (no Stripe price)
    are added by the frontend as bookends.

    A BRANDED host prices exactly one brand: its own. `api.algenta.ai` used to answer
    `{"app":"codna",...}` because the signature default was the literal `"codna"`, so an
    Algenta-branded host publicly advertised another product's catalogue — and `?app=<brand>` let any
    host price any brand, including unlaunched SKUs. The brand is now taken from an authoritative
    signal (`ALGENTA_PRODUCT`, else the request's own `Host` via the registry's `public_api_base`),
    and a request for a DIFFERENT brand on a branded host is refused rather than served: cross-brand
    pricing stays possible only on the shared engine's own non-brand host, which is where a
    multi-brand portal belongs. `?app=<own brand>` remains valid so existing callers keep working.

    An unregistered `app` is rejected rather than answered with an empty plan list under a 200, which
    read as "this brand has no paid tiers" instead of "no such brand" — and, because the brand string
    was passed straight into the Stripe catalogue cache, an unbounded number of distinct values each
    bought a permanent cache entry and a live Stripe call from an unauthenticated endpoint.
    """
    from apps.api_server.services.stripe_catalog import list_plans

    pinned = _brand_pin(request)
    if pinned is not None and get_product(pinned) is None:
        # Only reachable from a typo in ALGENTA_PRODUCT (the host signal is registry-derived). Surface
        # it instead of falling back to another brand's catalogue — a silent fallback would reintroduce
        # exactly this defect while making the operator believe the host was configured.
        raise _invalid_product_error(pinned)

    requested = (app or "").strip().lower()
    if not requested:
        # Nothing named and no brand host: the registry's unprefixed namespace is what a nameless brand
        # means, so an unconfigured deployment keeps answering instead of failing closed on a public page.
        resolved = pinned or legacy_default_product()
    elif get_product(requested) is None:
        raise _invalid_product_error(requested)
    elif pinned is not None and requested != pinned:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "product_not_served",
                    "message": (
                        f"This deployment serves '{pinned}' plans only; it will not price "
                        f"'{requested}'. Ask '{requested}' on its own API host."
                    ),
                }
            },
        )
    else:
        resolved = requested
    return {"app": resolved, "plans": await list_plans(resolved)}


@router.post("/v1/billing/checkout", summary="Create Stripe Checkout session")
async def checkout(
    request: Request,
    auth: AuthContext = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    body = await request.json()
    plan = body.get("plan", "developer")
    try:
        seats = max(1, int(body.get("seats", 1)))
    except (TypeError, ValueError):
        seats = 1
    try:
        devices = max(1, int(body.get("devices", 1)))
    except (TypeError, ValueError):
        devices = 1
    if plan not in (
        "developer", "pro", "proplus", "ultra", "team",
        "telys_pro", "telys_team",
        "sqai_pro", "sqai_team",
        "algenta_pro", "algenta_team",
    ):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "invalid_plan",
                    "message": "Invalid plan",
                }
            },
        )

    # Product-scoped billing gate: a brand's checkout is live only when its `billing` flag is on. Algenta
    # ships billing DARK (Stripe test-mode first) — its plans are in the allow-list above (machinery
    # deployed) but checkout is refused until the owner flips product_registry algenta.billing on.
    # codna/telys are on, so this is a no-op for them.
    from apps.api_server.services.product_registry import product_flag, product_for_plan

    _plan_product = product_for_plan(plan)
    if not product_flag(_plan_product, "billing", default=True):
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "billing_not_enabled",
                    "message": f"Billing is not yet enabled for {_plan_product}.",
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
        quantity=(
            devices
            if is_per_device_plan(plan)
            else seats
            if plan in ("team", "telys_team", "sqai_team")
            else 1
        ),
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
        affected_org_id = await _process_stripe_event(db, event)
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

    # Bust the org's cached AuthContexts AFTER commit so a plan / device-cap change (worker caps,
    # licensed_devices) takes effect immediately instead of lagging the per-key cache TTL (~5 min).
    # Best-effort: invalidate_org_api_key_caches never raises (a Redis hiccup falls back to TTL).
    if affected_org_id:
        from apps.api_server.services.auth_service import invalidate_org_api_key_caches

        redis_client = getattr(request.app.state, "redis", None)
        await invalidate_org_api_key_caches(db, affected_org_id, redis_client)
    return JSONResponse(content={"received": True})


async def _process_stripe_event(db: AsyncSession, event: dict[str, Any]) -> str | None:
    """Apply the billing state change for a verified Stripe event.

    Raises on DB failure (the caller rolls back + returns 5xx so Stripe retries). Does NOT commit —
    the caller commits atomically with the exactly-once event-id ledger row. Returns the id of the
    org whose plan/caps changed (or ``None``) so the caller can bust its cached AuthContexts AFTER
    commit — otherwise a plan/device-cap change lags up to the per-key cache TTL.
    """
    event_type = event.get("type", "")
    obj = event.get("data", {}).get("object", {})
    affected_org_id: str | None = None

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
                affected_org_id = str(org.id)
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
                # Entitlement expands (upgrade) — recompute + audit, no revocation.
                await _audit_entitlement_recompute(db, org, event_type, event.get("id"))

    # ── Subscription updated / created ────────────────────────────────────────
    elif event_type in ("customer.subscription.created", "customer.subscription.updated"):
        customer_id = obj.get("customer")
        subscription_id = obj.get("id")
        status = obj.get("status", "active")
        period_end = obj.get("current_period_end")  # Unix timestamp
        cancel_at_end = obj.get("cancel_at_period_end", False)

        # Get plan from subscription metadata or items
        plan_name = _plan_from_subscription(obj)

        # Find org by customer_id, falling back to the subscription's stamped org_id metadata — the
        # fallback survives the ordering race where this event precedes checkout.session.completed
        # persisting stripe_customer_id (Stripe gives no ordering guarantee), which would otherwise
        # drop the per-device quantity sync and cap a customer who paid for N>plan-default at the default.
        org_result = await db.execute(
            select(Organization).where(Organization.stripe_customer_id == customer_id)
        )
        org = org_result.scalar_one_or_none()
        if org is None:
            meta_org_id = (obj.get("metadata") or {}).get("org_id")
            if meta_org_id:
                org = (
                    await db.execute(
                        select(Organization).where(Organization.id == meta_org_id)
                    )
                ).scalar_one_or_none()
        if org is not None and customer_id and not org.stripe_customer_id:
            org.stripe_customer_id = customer_id  # backfill so later customer-id lookups match
        if org:
            affected_org_id = str(org.id)
            # Dunning exhausted (unpaid / canceled / incomplete_expired) → the customer stopped
            # paying and Stripe gave up retrying. Downgrade to Community NOW, before the eventual
            # delete, so a delinquent monthly subscriber loses paid entitlement within ~one cycle
            # rather than weeks later. `past_due` is deliberately NOT terminal — it's still inside
            # Stripe's retry window (a transient decline that may recover), so it keeps the plan.
            if status in _DELINQUENT_TERMINAL_STATUSES:
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
                await _downgrade_to_community(
                    db,
                    org,
                    reason=f"subscription_{status}",
                    event_id=event.get("id"),
                    subscription_resource_id=subscription_id,
                )
                return affected_org_id
            # An ACTIVE subscription should map to a KNOWN paid price. plan_name=='free' here means
            # an unknown/misconfigured price_id (see _plan_from_subscription's fallback) — do NOT
            # downgrade-and-de-entitle a paying customer on a parse failure. A genuine cancellation
            # always arrives as customer.subscription.deleted (handled below). Keep the current plan
            # and surface the misconfiguration loudly.
            if plan_name == "free":
                logger.warning(
                    "subscription_updated_unknown_price_id_plan_kept",
                    org_id=str(org.id),
                    customer_id=customer_id,
                    current_plan=_org_plan_name(org),
                    status=status,
                    event_id=event.get("id"),
                )
            else:
                try:
                    org.plan = OrgPlan(plan_name)
                except ValueError:
                    pass
            # Per-seat Team billing: sync purchased seats from the subscription item quantity.
            org.seats = _seats_from_subscription(obj)
            # Per-DEVICE billing (algenta_pro/algenta_team): the subscription-item quantity IS the
            # licensed device count — store it so enforcement uses the paid count, not the static
            # plan constant. Update ONLY on a real, positive quantity: a quantity-less/malformed
            # event must NOT collapse the count (which would then revoke paid devices). None for
            # per-seat plans (their device cap stays the static one).
            _dev_qty = _subscription_quantity(obj) if is_per_device_plan(plan_name) else None
            if _dev_qty is not None:
                org.licensed_devices = _dev_qty
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
            await _audit_entitlement_recompute(db, org, event_type, event.get("id"))
            # Conservative downgrade enforcement: revoke devices BEYOND the new finite cap of a
            # still-runtime paid plan. We never full-revoke here — a misconfigured price_id falls
            # back to 'free' (see _plan_from_subscription), and a genuine cancellation arrives as
            # `customer.subscription.deleted` (below). Per-seat/other plans re-cap to the static plan
            # cap (idempotent). Per-device plans re-cap to the licensed count ONLY when THIS event
            # carried a real quantity (_dev_qty) — never on a quantity-less/metadata update, so a
            # malformed payload can't collapse the cap and revoke paid devices. (New over-cap devices
            # are always blocked by the org-wide registration gate regardless.)
            if is_per_device_plan(plan_name):
                _keep_cap = _dev_qty or 0  # None/absent → 0 → skip revoke, don't touch devices
            else:
                _keep_cap = _plan_device_limit(plan_name)
            if _plan_local_runtime(plan_name) and _keep_cap > 0:
                revoked = await revoke_excess_org_devices(org.id, _keep_cap, db)
                if revoked:
                    logger.info(
                        "subscription_downgrade_excess_revoked",
                        org_id=str(org.id),
                        plan=plan_name,
                        count=revoked,
                    )
                    await write_audit_event(
                        db,
                        org.id,
                        AuditAction.DEVICE_REVOKED,
                        actor_email="stripe-webhook",
                        resource_type="device",
                        resource_id=str(org.id),
                        metadata={
                            "count": revoked,
                            "reason": "plan_downgrade",
                            "new_plan": plan_name,
                            "event_id": event.get("id"),
                        },
                    )

            # Suspend members beyond the new plan's seat cap (owners always kept). Runs for
            # ANY downgrade — including to a non-runtime/solo plan — mirroring the device policy.
            seat_cap = _seat_limit(plan_name)
            suspended_members = await _suspend_excess_members(db, org.id, seat_cap)
            if suspended_members:
                logger.info(
                    "subscription_downgrade_excess_members_suspended",
                    org_id=str(org.id),
                    plan=plan_name,
                    count=suspended_members,
                )
                await write_audit_event(
                    db,
                    org.id,
                    AuditAction.PLAN_DOWNGRADE,
                    actor_email="stripe-webhook",
                    resource_type="team_member",
                    resource_id=str(org.id),
                    metadata={
                        "suspended_members": suspended_members,
                        "new_plan": plan_name,
                        "seat_cap": seat_cap,
                        "event_id": event.get("id"),
                    },
                )

    # ── Subscription deleted / cancelled ─────────────────────────────────────
    elif event_type == "customer.subscription.deleted":
        customer_id = obj.get("customer")
        org_result = await db.execute(
            select(Organization).where(Organization.stripe_customer_id == customer_id)
        )
        org = org_result.scalar_one_or_none()
        if org:
            affected_org_id = str(org.id)
            # Cancellation is unambiguous → drop to the product's Community tier (algenta_free keeps
            # the free-forever device re-capped to 1; cloud-only free revokes all devices).
            await _downgrade_to_community(
                db,
                org,
                reason="subscription.deleted",
                event_id=event.get("id"),
                subscription_resource_id=obj.get("id"),
            )

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

    return affected_org_id


def _org_plan_name(org: Organization) -> str:
    return getattr(org.plan, "value", str(org.plan))


def _community_downgrade_plan(prev_plan: str) -> OrgPlan:
    """The Community / free-forever tier to drop to when a paid subscription ends, in the SAME
    product namespace as the prior plan.

    ``algenta_pro/algenta_team`` → ``algenta_free`` (Community — free-forever, self-hosted, 1 device);
    ``telys_*`` → ``telys_developer``; unprefixed codna/core plans → generic ``free``. This is what makes
    a lapsed Algenta customer land on the intended limited Community grant instead of the generic
    cloud-only ``free`` tier (whose entitlement has an EMPTY products dict and would strip the engine
    license entirely). If the product's default tier isn't a valid enum value, fail safe to ``free``.
    """
    cfg = get_product(product_for_plan(prev_plan))
    tier = cfg.default_free_tier if cfg else "free"
    try:
        return OrgPlan(tier)
    except ValueError:
        return OrgPlan.FREE


async def _downgrade_to_community(
    db: AsyncSession,
    org: Organization,
    *,
    reason: str,
    event_id: str | None,
    subscription_resource_id: str | None,
) -> None:
    """Drop a paid org to its product's Community tier and re-cap devices/seats accordingly.

    Used by both a clean cancellation (``customer.subscription.deleted``) and dunning-exhausted
    delinquency (``customer.subscription.updated`` with a terminal status). Device handling depends on
    the landing tier: a local-runtime Community tier (``algenta_free`` — 1 device) is RE-CAPPED so the
    free-forever device survives; a cloud-only ``free`` tier (no local runtime) has ALL devices revoked
    since none can hold a valid license. Does NOT commit — the caller commits with the event-id ledger.
    """
    prev_plan = _org_plan_name(org)
    new_plan_enum = _community_downgrade_plan(prev_plan)
    org.plan = new_plan_enum
    await db.flush()
    new_plan = new_plan_enum.value

    if _plan_local_runtime(new_plan) and _plan_device_limit(new_plan) > 0:
        # Keep the Community device(s); revoke only devices beyond the free-forever cap.
        revoked = await revoke_excess_org_devices(org.id, _plan_device_limit(new_plan), db)
    else:
        # Cloud-only free: no device can hold a license → revoke all (rows land in the signed CRL).
        revoked = await revoke_org_devices(org.id, db)

    logger.info(
        "subscription_downgraded_to_community",
        org_id=str(org.id),
        prev_plan=prev_plan,
        new_plan=new_plan,
        reason=reason,
        devices_revoked=revoked,
    )
    await write_audit_event(
        db,
        org.id,
        AuditAction.ENTITLEMENT_REVOKED,
        actor_email="stripe-webhook",
        resource_type="subscription",
        resource_id=subscription_resource_id or str(org.id),
        metadata={"old_plan": prev_plan, "new_plan": new_plan, "reason": reason, "event_id": event_id},
    )
    if revoked:
        await write_audit_event(
            db,
            org.id,
            AuditAction.DEVICE_REVOKED,
            actor_email="stripe-webhook",
            resource_type="device",
            resource_id=str(org.id),
            metadata={"count": revoked, "reason": reason, "event_id": event_id},
        )

    # Suspend members beyond the Community seat cap (owners always kept).
    seat_cap = _seat_limit(new_plan)
    suspended = await _suspend_excess_members(db, org.id, seat_cap)
    if suspended:
        logger.info(
            "subscription_downgrade_excess_members_suspended",
            org_id=str(org.id),
            plan=new_plan,
            count=suspended,
        )
        await write_audit_event(
            db,
            org.id,
            AuditAction.PLAN_DOWNGRADE,
            actor_email="stripe-webhook",
            resource_type="team_member",
            resource_id=str(org.id),
            metadata={
                "suspended_members": suspended,
                "new_plan": new_plan,
                "seat_cap": seat_cap,
                "reason": reason,
                "event_id": event_id,
            },
        )
    await _audit_entitlement_recompute(db, org, reason, event_id)


async def _audit_entitlement_recompute(
    db: AsyncSession, org: Organization, event_type: str, event_id: str | None
) -> None:
    """Audit that the org's entitlement was re-resolved from its (now-current) plan.

    The entitlement is derived live from org.plan (entitlement_service); license issuance +
    renewal read it at issue time, so no license rows need touching — this records the change.
    """
    plan_name = _org_plan_name(org)
    record = entitlement_for_org(org)
    await write_audit_event(
        db,
        org.id,
        AuditAction.ENTITLEMENT_RECOMPUTE,
        actor_email="stripe-webhook",
        resource_type="organization",
        resource_id=str(org.id),
        metadata={
            "plan": plan_name,
            "event_type": event_type,
            "event_id": event_id,
            "deployment_class": record.deployment_class,
            "device_limit": _plan_device_limit(plan_name),
        },
    )


def _seats_from_subscription(sub_obj: dict[str, Any]) -> int:
    """Purchased seats = the subscription item quantity (per-seat Team billing). Defaults to 1."""
    try:
        items = sub_obj.get("items", {}).get("data", [])
        qty = items[0].get("quantity") if items else None
        return max(1, int(qty)) if qty else 1
    except (KeyError, IndexError, TypeError, ValueError):
        return 1


def _subscription_quantity(sub_obj: dict[str, Any]) -> int | None:
    """The subscription item quantity as a POSITIVE int, or None when it is absent / zero / not
    parseable. Unlike ``_seats_from_subscription`` (which floors to 1), per-device licensing must NOT
    treat a missing quantity as 1 — a quantity-less or malformed event would otherwise collapse
    ``licensed_devices`` to 1 and revoke devices the customer still pays for. Callers update the
    licensed count / re-cap ONLY when this returns a real quantity."""
    try:
        items = sub_obj.get("items", {}).get("data", [])
        qty = items[0].get("quantity") if items else None
        if qty is None:
            return None
        qty = int(qty)
        return qty if qty > 0 else None
    except (KeyError, IndexError, TypeError, ValueError):
        return None


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
            if (
                hasattr(_settings, "stripe_price_team")
                and price_id == _settings.stripe_price_team
            ):
                return "team"
            # Codna solo power tiers (Pro+/Ultra) — sellable from the website checkout, so their
            # price_ids must reverse-map or a renewal/update logs "unknown price" forever.
            if (
                hasattr(_settings, "stripe_price_proplus")
                and price_id == _settings.stripe_price_proplus
            ):
                return "proplus"
            if (
                hasattr(_settings, "stripe_price_ultra")
                and price_id == _settings.stripe_price_ultra
            ):
                return "ultra"
            # Telys runtime paid tiers (telys_developer is free → no Stripe price). Without these a
            # paid Telys subscription's price_id falls through to "free", and the handler's
            # unknown-price branch keeps the org on its current (free) plan — silently de-entitling
            # a paying customer. Keep this map in lockstep with stripe_service.PLAN_PRICE_IDS.
            if (
                hasattr(_settings, "stripe_price_telys_pro")
                and price_id == _settings.stripe_price_telys_pro
            ):
                return "telys_pro"
            if (
                hasattr(_settings, "stripe_price_telys_team")
                and price_id == _settings.stripe_price_telys_team
            ):
                return "telys_team"
            # SQAI runtime paid tiers (sqai_developer is free → no Stripe price). Same rationale as telys:
            # without these an sqai subscription's price_id falls through to "free" and silently
            # de-entitles a paying customer. Keep in lockstep with stripe_service.PLAN_PRICE_IDS.
            if (
                hasattr(_settings, "stripe_price_sqai_pro")
                and price_id == _settings.stripe_price_sqai_pro
            ):
                return "sqai_pro"
            if (
                hasattr(_settings, "stripe_price_sqai_team")
                and price_id == _settings.stripe_price_sqai_team
            ):
                return "sqai_team"
            # Algenta engine paid tiers (algenta_free is free → no Stripe price). Same rationale as telys:
            # without these an algenta subscription's price_id falls through to "free" and silently
            # de-entitles a paying customer. Keep in lockstep with stripe_service.PLAN_PRICE_IDS.
            if (
                hasattr(_settings, "stripe_price_algenta_pro")
                and price_id == _settings.stripe_price_algenta_pro
            ):
                return "algenta_pro"
            if (
                hasattr(_settings, "stripe_price_algenta_team")
                and price_id == _settings.stripe_price_algenta_team
            ):
                return "algenta_team"
            # Cohenta paid tiers (cohenta_free is free → no Stripe price). Same rationale as telys/
            # algenta: without these a cohenta subscription's price_id falls through to "free" and
            # silently de-entitles a paying customer. Keep in lockstep with stripe_service.PLAN_PRICE_IDS.
            if (
                hasattr(_settings, "stripe_price_cohenta_pro_runner")
                and price_id == _settings.stripe_price_cohenta_pro_runner
            ):
                return "cohenta_pro_runner"
            if (
                hasattr(_settings, "stripe_price_cohenta_team")
                and price_id == _settings.stripe_price_cohenta_team
            ):
                return "cohenta_team"
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
