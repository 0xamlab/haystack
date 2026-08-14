"""Website/dashboard self-service billing — Supabase-authenticated.

Companion to ``/byok`` and ``/account/devices``: a signed-in user sees their current plan + managed-
LLM usage and can upgrade (Stripe Checkout) or manage billing (Stripe Customer Portal) WITHOUT an
engine API key. Authenticated by the user's Supabase access_token (the site's OAuth session),
resolved to the caller's engine org via the shared website-identity path; everything is org-scoped.

Distinct from the API-key ``/v1/billing/*`` (``require_role('owner')``, for the SDK/CLI) — this
surface is account management for the website and delegates to the SAME Stripe service. Inert until
``SUPABASE_URL`` (+ the GitHub App) is configured → 503; and 503 when Stripe billing is not
configured (placeholder key) so the dashboard card degrades to a "billing not enabled yet" state,
exactly like ``/account/devices``.
"""

from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.config import get_settings as _get_settings
from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_redis
from apps.api_server.models.llm_usage_record import USD_MICROS
from apps.api_server.models.user import User
from apps.api_server.services import llm_spend_service, plan_limits, website_identity
from apps.api_server.services.public_url_policy import (
    request_origin_base_url,
    resolve_billing_redirect_urls,
)
from apps.api_server.services.stripe_service import (
    StripeCustomerMissingError,
    billing_configured,
    create_billing_portal_session,
    create_checkout_session,
    customer_exists,
    portal_configuration_for_app,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["account"])


async def _heal_dead_customer(db: AsyncSession, org: Any, *, reason: str) -> None:
    """The org's stored Stripe customer no longer exists in the ACTIVE Stripe mode.

    Happens after a test→live key flip (test-mode customers are invisible to a live key and can
    never be migrated — Stripe forbids moving customers/subscriptions/cards across modes) or when a
    customer is deleted in the dashboard. There is no live billing to manage, so drop the org to its
    product Community tier, close any stale subscriptions row, and clear the dead reference. The
    billing card then shows the honest Free state and 'Manage' stops erroring. Commits.
    """
    # Imported lazily to avoid a router→router import cycle at module load.
    from apps.api_server.routers.billing import _downgrade_to_community

    dead = org.stripe_customer_id
    await _downgrade_to_community(
        db, org, reason=reason, event_id=None, subscription_resource_id=None
    )
    org.stripe_customer_id = None
    await db.execute(
        text("UPDATE subscriptions SET status='canceled' WHERE org_id = :org_id"),
        {"org_id": str(org.id)},
    )
    await db.commit()
    logger.info("billing_dead_customer_healed", org_id=str(org.id), customer_id=dead, reason=reason)

# Plans purchasable from the website Upgrade buttons, across every brand's public ladder: codna
# pro/proplus/ultra/team, telys_pro, algenta pro/team (per-device), cohenta pro_runner/team. Free
# tiers are $0 and Enterprise is sales-assisted, so neither goes through Checkout here. Telys's
# public ladder is Developer (free) / Pro / Enterprise (contact-sales) — telys_team is retained for
# existing orgs + enforcement but is NOT publicly sellable, so it's excluded from self-serve checkout.
# Keep in sync with the Stripe catalog (product.metadata.source=<brand>) + stripe_service.PLAN_PRICE_IDS.
_CHECKOUT_PLANS = frozenset(
    {
        "pro",
        "team",
        "proplus",
        "ultra",
        "telys_pro",
        "algenta_pro",
        "algenta_team",
        "cohenta_pro_runner",
        "cohenta_team",
        "sqai_pro",
        "sqai_team",
        # Server (Compute-Unit) tiers are self-serve + scalable: checkout starts at the SKU's
        # qty_min Compute Units and Stripe's adjustable_quantity lets the buyer scale up on the
        # checkout page (bounded by the SKU's qty_max). cohenta_server is omitted — cohenta isn't live.
        "algenta_server",
        "telys_server",
        "sqai_server",
        "codna_server",
    }
)

# Compute-Unit (server) plans: bill per CU, priced dynamically from Stripe, purchased at >= qty_min
# units with adjustable scaling on the Stripe checkout page.
_COMPUTE_UNIT_PLANS = frozenset(
    {"algenta_server", "telys_server", "sqai_server", "codna_server", "cohenta_server"}
)


def _is_free_plan(plan: str) -> bool:
    """True for every $0 entry tier across the family — the two naming schemes: the community tiers
    (``free``, ``algenta_free``, …) AND the ``developer`` entry tier (``developer``,
    ``telys_developer``, ``sqai_developer``). A free plan has no billing cycle and never cancels, so
    its subscription/renewal state must not be surfaced. Mirrors the accounts BillingCard ``isFree``."""
    p = (plan or "").strip().lower()
    return p in ("free", "") or p == "developer" or p.endswith("_free") or p.endswith("_developer")


def _require_billing() -> None:
    """503 when Stripe isn't configured (placeholder key) so the dashboard card shows
    "billing not enabled yet", exactly like /account/devices when SUPABASE_URL is unset."""
    if not billing_configured():
        raise HTTPException(
            status_code=503,
            detail=website_identity.error_body(
                "billing_not_configured", "Billing is not enabled yet."
            ),
        )


class CheckoutRequest(BaseModel):
    plan: str = Field(min_length=1, max_length=32)
    # Units to purchase: per-DEVICE for algenta_pro/algenta_team (Stripe quantity = licensed devices),
    # per-SEAT for team/cohenta_team. Defaults to 1; the webhook syncs this quantity into
    # licensed_devices / seats.
    quantity: int = Field(default=1, ge=1, le=10000)
    # Post-checkout redirect back to the CALLER (the accounts portal). Validated against the trusted
    # accounts host (open-redirect protection); ignored if it points anywhere else. Omit → derived default.
    success_url: str | None = Field(default=None, max_length=2048)
    cancel_url: str | None = Field(default=None, max_length=2048)


def _validated_return_url(url: str | None) -> str | None:
    """Accept a caller-supplied post-checkout redirect ONLY when its host matches a TRUSTED host —
    the accounts portal (`accounts_base_url`) or localhost (dev). Anything else (an attacker-supplied
    URL) is dropped so Checkout can't be turned into an open redirect. Returns the URL or None."""
    if not url:
        return None
    from urllib.parse import urlparse

    parsed = urlparse(url.strip())
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        return None
    trusted: set[str] = set()
    accounts_host = urlparse(str(_get_settings().accounts_base_url)).hostname
    if accounts_host:
        trusted.add(accounts_host.lower())
    trusted.update({"localhost", "127.0.0.1"})
    return url if parsed.hostname.lower() in trusted else None



async def _require_billing_owner(db, org, identity: dict) -> None:
    """Checkout / Customer-Portal require an OWNER. verify_and_resolve_org proves
    org MEMBERSHIP, not role — and identity links + email memberships now let any
    member (viewer included) resolve the org — so without this gate a viewer could
    open the Stripe portal and cancel the subscription, swap the card, or read
    invoices. A row-less caller is a GitHub-install admin (owner-equivalent) → passes."""
    from sqlalchemy import func as _func

    from apps.api_server.models.user import User, UserRole

    email = (identity.get("email") or "").strip().lower()
    if not email:
        return
    member = await db.scalar(
        select(User).where(User.org_id == org.id, _func.lower(User.email) == email)
    )
    if member is not None and member.role != UserRole.OWNER:
        raise HTTPException(
            status_code=403,
            detail=website_identity.error_body(
                "owner_only", "Only the organization owner can manage billing."
            ),
        )

@router.get(
    "/account/billing",
    summary="Current plan + managed-LLM usage for the signed-in user (website / Supabase auth)",
    description=(
        "Returns the caller's current plan, subscription status + renewal, and managed-LLM spend "
        "vs the plan's monthly cap. Powers the subscription dashboard's billing card."
    ),
)
async def account_billing_info(
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
    x_org_id: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"  # private billing data — never cache
    org, _identity = await website_identity.verify_and_resolve_org(
        authorization, db, redis, selected_org_id=website_identity.parse_org_id(x_org_id)
    )
    _require_billing()

    # Self-heal a stale paid plan whose Stripe customer no longer exists in the active mode (a
    # test-mode leftover after the live flip). Only when there's a customer id AND a paid plan — free
    # orgs and orgs with no customer never pay the extra Stripe call. `customer_exists` returns None
    # on any transient/indeterminate outcome, so a Stripe blip can never wrongly downgrade a payer.
    if org.stripe_customer_id and org.plan.value not in ("free", "algenta_free"):
        if await customer_exists(org.stripe_customer_id) is False:
            await _heal_dead_customer(db, org, reason="billing_info_customer_missing")

    plan = org.plan.value
    cap_usd = plan_limits.get(plan).llm_spend_cap_usd_month
    spend_micros = await llm_spend_service.get_monthly_llm_spend_micros(org.id, db)

    # Subscription status + renewal come from the subscriptions row (the engine's mirror of the
    # Stripe subscription), most-recent first. Free orgs have no row → active / no renewal. Wrapped
    # defensively: a missing/empty subscriptions table must not break the plan read.
    status = "active"
    renews_at: str | None = None
    cancel_at_period_end = False
    # A free/Community plan is ALWAYS free and NEVER cancels — it has no billing cycle. A prior paid
    # subscription that was cancelled/downgraded can leave a stale subscriptions row with
    # cancel_at_period_end=true + a period end; reading it here made the card show
    # "Community · canceled · Cancels <date>", which is wrong. Skip the row entirely for free plans.
    if not _is_free_plan(plan):
        try:
            row = (
                await db.execute(
                    text(
                        "SELECT status, current_period_end, cancel_at_period_end FROM subscriptions "
                        "WHERE org_id = :org_id ORDER BY updated_at DESC LIMIT 1"
                    ),
                    {"org_id": str(org.id)},
                )
            ).first()
            if row is not None:
                status = row[0] or status
                renews_at = row[1].isoformat() if row[1] else None
                cancel_at_period_end = bool(row[2])
        except Exception as exc:  # noqa: BLE001 — billing info must degrade, not 500
            logger.warning("account_billing_subscription_read_failed", error=str(exc))

    return {
        "plan": plan,
        "status": status,
        "renews_at": renews_at,
        # True while a cancellation is pending — the portal shows "Cancels on <renews_at>".
        "cancel_at_period_end": cancel_at_period_end,
        "usage_usd": round(spend_micros / USD_MICROS, 2),
        "cap_usd": cap_usd if cap_usd and cap_usd > 0 else None,
    }


@router.post(
    "/account/billing/checkout",
    summary="Start Stripe Checkout for a plan upgrade (website / Supabase auth)",
)
async def account_billing_checkout(
    payload: CheckoutRequest,
    request: Request,
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
    x_org_id: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    org, identity = await website_identity.verify_and_resolve_org(
        authorization, db, redis, selected_org_id=website_identity.parse_org_id(x_org_id)
    )
    _require_billing()
    await _require_billing_owner(db, org, identity)

    plan = payload.plan.strip().lower()
    if plan not in _CHECKOUT_PLANS:
        raise HTTPException(
            status_code=400,
            detail=website_identity.error_body(
                "invalid_plan", "This plan cannot be purchased here."
            ),
        )
    # Product-scoped billing gate (mirrors POST /v1/billing/checkout): a brand's checkout is live only when
    # its `billing` flag is on. Algenta ships billing DARK until the owner flips product_registry
    # algenta.billing; codna/telys are on, so this is a no-op for them.
    from apps.api_server.services.product_registry import product_flag, product_for_plan

    _plan_product = product_for_plan(plan)
    if not product_flag(_plan_product, "billing", default=True):
        raise HTTPException(
            status_code=403,
            detail=website_identity.error_body(
                "billing_not_enabled", f"Billing is not yet enabled for {_plan_product}."
            ),
        )

    # Billing email: the resolved identity's email, else the org's first user, else a placeholder.
    email = identity.get("email")
    if not email:
        user = (
            await db.execute(
                select(User).where(User.org_id == org.id).order_by(User.created_at).limit(1)
            )
        ).scalar_one_or_none()
        email = user.email if user else "unknown@example.com"

    # Redirect back to the caller (the accounts portal) when it supplies a trusted-host URL; otherwise
    # fall back to the engine-derived dashboard URL. Validation blocks an open redirect via Checkout.
    redirect_urls = resolve_billing_redirect_urls(request_origin=request_origin_base_url(request))
    success_url = _validated_return_url(payload.success_url) or redirect_urls.success_url
    cancel_url = _validated_return_url(payload.cancel_url) or redirect_urls.cancel_url

    # Resolve the Stripe price from the SAME catalogue that /billing/plans renders — exactly like the
    # v1 checkout (routers/billing.py) already does. WITHOUT this, create_checkout_session falls back to
    # PLAN_PRICE_IDS, the hand-maintained env map that only carries codna's legacy plans, so every
    # catalogue-only plan (algenta_pro/algenta_team, telys_pro, sqai_pro, cohenta_*) failed with
    # invalid_plan → "Couldn't start checkout". The accounts portal upgrades monthly; annual follows
    # once the UI exposes the cadence toggle. None → create_checkout_session still tries the env map,
    # so codna's env-configured plans keep working unchanged.
    from apps.api_server.services.stripe_catalog import resolve_price

    catalogue_price = await resolve_price(_plan_product, plan, "month")
    price_id = catalogue_price.get("id") if catalogue_price else None

    # Compute-Unit (server) plans are sold at >= the SKU's qty_min units; start checkout at that
    # minimum and let Stripe's adjustable_quantity scale the buyer up. Other plans keep min 1.
    is_compute_unit = plan in _COMPUTE_UNIT_PLANS
    qty_min = int((catalogue_price or {}).get("qty_min") or 1) if is_compute_unit else 1
    quantity = max(payload.quantity, qty_min)

    return await create_checkout_session(
        str(org.id),
        email,
        plan,
        price_id=price_id,
        quantity=quantity,
        min_quantity=qty_min,
        success_url=success_url,
        cancel_url=cancel_url,
    )


class PortalRequest(BaseModel):
    # Brand context — selects the per-brand Customer Portal configuration so the
    # "Update subscription" picker only offers this brand's plans (metadata.brand match).
    app: str | None = Field(default=None, max_length=32)
    # Where "Return to …" goes — validated against the trusted accounts host, like checkout.
    return_url: str | None = Field(default=None, max_length=2048)


@router.post(
    "/account/billing/portal",
    summary="Open the Stripe Customer Portal (website / Supabase auth)",
)
async def account_billing_portal(
    request: Request,
    response: Response,
    payload: PortalRequest | None = None,
    authorization: Annotated[str | None, Header()] = None,
    x_org_id: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    org, identity = await website_identity.verify_and_resolve_org(
        authorization, db, redis, selected_org_id=website_identity.parse_org_id(x_org_id)
    )
    _require_billing()
    await _require_billing_owner(db, org, identity)

    if not org.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail=website_identity.error_body(
                "no_billing_account", "No billing account yet — upgrade first."
            ),
        )
    body = payload or PortalRequest()
    return_url = _validated_return_url(body.return_url)
    if return_url is None:
        redirect_urls = resolve_billing_redirect_urls(
            request_origin=request_origin_base_url(request)
        )
        return_url = redirect_urls.return_url
    try:
        return await create_billing_portal_session(
            org.stripe_customer_id,
            return_url=return_url,
            configuration=await portal_configuration_for_app(body.app),
        )
    except StripeCustomerMissingError:
        # The stored customer is gone in the active (live) Stripe mode — a test-mode leftover after
        # the live flip, or a deleted customer. Self-heal to the honest Free state and tell the
        # caller to subscribe, instead of surfacing an opaque "please try again".
        await _heal_dead_customer(db, org, reason="portal_customer_missing")
        raise HTTPException(
            status_code=400,
            detail=website_identity.error_body(
                "no_billing_account",
                "No live billing account yet — subscribe to a plan to activate billing.",
            ),
        ) from None
