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
    billing_configured,
    create_billing_portal_session,
    create_checkout_session,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["account"])

# Plans purchasable from the website Upgrade buttons (mirrors codna plans.ts checkout tiers).
# Free is $0 and Enterprise is sales-assisted, so neither goes through Checkout here. Telys's public
# ladder is Developer (free) / Pro / Enterprise (contact-sales) — telys_team is retained for existing
# orgs + enforcement but is NOT publicly sellable, so it's excluded from self-serve checkout.
# Keep in sync with the Stripe catalog (product.metadata.source=telys) + stripe_service.PLAN_PRICE_IDS.
_CHECKOUT_PLANS = frozenset({"pro", "team", "telys_pro", "algenta_pro", "algenta_team"})


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
    # per-SEAT for team. Defaults to 1; the webhook syncs this quantity into licensed_devices / seats.
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

    plan = org.plan.value
    cap_usd = plan_limits.get(plan).llm_spend_cap_usd_month
    spend_micros = await llm_spend_service.get_monthly_llm_spend_micros(org.id, db)

    # Subscription status + renewal come from the subscriptions row (the engine's mirror of the
    # Stripe subscription), most-recent first. Free orgs have no row → active / no renewal. Wrapped
    # defensively: a missing/empty subscriptions table must not break the plan read.
    status = "active"
    renews_at: str | None = None
    try:
        row = (
            await db.execute(
                text(
                    "SELECT status, current_period_end FROM subscriptions "
                    "WHERE org_id = :org_id ORDER BY updated_at DESC LIMIT 1"
                ),
                {"org_id": str(org.id)},
            )
        ).first()
        if row is not None:
            status = row[0] or status
            renews_at = row[1].isoformat() if row[1] else None
    except Exception as exc:  # noqa: BLE001 — billing info must degrade, not 500
        logger.debug("account_billing_subscription_read_failed", error=str(exc))

    return {
        "plan": plan,
        "status": status,
        "renews_at": renews_at,
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
    return await create_checkout_session(
        str(org.id),
        email,
        plan,
        quantity=payload.quantity,
        success_url=success_url,
        cancel_url=cancel_url,
    )


@router.post(
    "/account/billing/portal",
    summary="Open the Stripe Customer Portal (website / Supabase auth)",
)
async def account_billing_portal(
    request: Request,
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
    x_org_id: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    org, _identity = await website_identity.verify_and_resolve_org(
        authorization, db, redis, selected_org_id=website_identity.parse_org_id(x_org_id)
    )
    _require_billing()

    if not org.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail=website_identity.error_body(
                "no_billing_account", "No billing account yet — upgrade first."
            ),
        )
    redirect_urls = resolve_billing_redirect_urls(request_origin=request_origin_base_url(request))
    return await create_billing_portal_session(
        org.stripe_customer_id, return_url=redirect_urls.return_url
    )
