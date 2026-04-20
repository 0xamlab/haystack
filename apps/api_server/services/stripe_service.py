"""
Stripe billing service.

Provides:
- create_checkout_session()   — Start Stripe Checkout for a plan upgrade
- create_billing_portal()    — Open Stripe Customer Portal
- handle_webhook()           — Process Stripe webhook events
- get_billing_info()         — Get current subscription status

Plans map to Stripe Price IDs configured in environment variables.
"""
import hashlib
import hmac
import json
from typing import Any

import httpx
import structlog
from fastapi import HTTPException

from apps.api_server.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# ─── Plan → Stripe Price ID mapping ──────────────────────────────────────────

PLAN_PRICE_IDS: dict[str, str | None] = {
    "free": None,
    "developer": (
        settings.stripe_price_developer
        if hasattr(settings, "stripe_price_developer")
        else None
    ),
    "pro": (
        settings.stripe_price_pro
        if hasattr(settings, "stripe_price_pro")
        else None
    ),
    "enterprise": None,  # sales-assisted only
}


def _stripe_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.stripe_secret_key}",
        "Content-Type": "application/x-www-form-urlencoded",
    }


async def create_checkout_session(
    org_id: str,
    org_email: str,
    plan: str,
    success_url: str = "http://localhost:3000/dashboard/billing?success=1",
    cancel_url: str = "http://localhost:3000/dashboard/billing?cancelled=1",
) -> dict[str, str]:
    """
    Create a Stripe Checkout Session for upgrading to the given plan.
    Returns {"url": "https://checkout.stripe.com/..."}
    """
    price_id = PLAN_PRICE_IDS.get(plan)
    if not price_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "invalid_plan",
                    "message": f"No Stripe price configured for plan '{plan}'",
                }
            },
        )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.stripe.com/v1/checkout/sessions",
            headers=_stripe_headers(),
            data={
                "mode": "subscription",
                "line_items[0][price]": price_id,
                "line_items[0][quantity]": "1",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "customer_email": org_email,
                "metadata[org_id]": org_id,
                "metadata[plan]": plan,
            },
        )

    if resp.status_code != 200:
        logger.error("stripe_checkout_failed", status=resp.status_code, body=resp.text)
        raise HTTPException(
            status_code=502,
            detail={
                "error": {
                    "code": "stripe_error",
                    "message": "Failed to create checkout session",
                }
            },
        )

    data = resp.json()
    return {"url": data["url"]}


async def create_billing_portal_session(
    customer_id: str,
    return_url: str = "http://localhost:3000/dashboard/billing",
) -> dict[str, str]:
    """
    Create a Stripe Customer Portal session for managing billing.
    Returns {"url": "https://billing.stripe.com/..."}
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.stripe.com/v1/billing_portal/sessions",
            headers=_stripe_headers(),
            data={
                "customer": customer_id,
                "return_url": return_url,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail={
                "error": {
                    "code": "stripe_error",
                    "message": "Failed to create billing portal session",
                }
            },
        )

    data = resp.json()
    return {"url": data["url"]}


def verify_stripe_webhook(payload: bytes, sig_header: str) -> dict[str, Any]:
    """
    Verify Stripe webhook signature (HMAC-SHA256).
    Returns parsed event dict or raises 400.
    """
    secret = settings.stripe_webhook_secret
    try:
        # Extract timestamp and signature
        parts = dict(item.split("=", 1) for item in sig_header.split(","))
        timestamp = parts.get("t", "")
        signature = parts.get("v1", "")

        signed_payload = f"{timestamp}.{payload.decode()}"
        expected = hmac.new(
            secret.encode(), signed_payload.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise ValueError("Invalid signature")

        return json.loads(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "webhook_signature_invalid", "message": str(exc)}},
        ) from exc


async def handle_checkout_completed(event: dict[str, Any]) -> None:
    """
    Process checkout.session.completed event.
    Updates org plan in the database.
    Called from the webhook router.
    """
    session_data = event.get("data", {}).get("object", {})
    org_id = session_data.get("metadata", {}).get("org_id")
    plan = session_data.get("metadata", {}).get("plan")
    customer_id = session_data.get("customer")

    if not org_id or not plan:
        logger.warning("checkout_completed_missing_metadata", event_id=event.get("id"))
        return

    logger.info(
        "checkout_completed",
        org_id=org_id,
        plan=plan,
        customer_id=customer_id,
    )
    # Actual DB update is done in the billing router (has access to AsyncSession)
