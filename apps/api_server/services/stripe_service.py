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
from collections.abc import Iterator, Mapping
from typing import Any

import httpx
import structlog
from fastapi import HTTPException

from apps.api_server.config import SettingsProxy, get_settings
from apps.api_server.services.egress_guard import (
    EgressAuditContext,
    EgressPolicyDeniedError,
    async_http_request,
)
from apps.api_server.services.public_url_policy import resolve_billing_redirect_urls

logger = structlog.get_logger(__name__)
settings = SettingsProxy()
_STRIPE_BASE_URL = "https://api.stripe.com"

# ─── Plan → Stripe Price ID mapping ──────────────────────────────────────────

class _PlanPriceIdMapping(Mapping[str, str | None]):
    def _current_mapping(self) -> dict[str, str | None]:
        current_settings = get_settings()
        return {
            "free": None,
            "developer": (
                current_settings.stripe_price_developer
                if hasattr(current_settings, "stripe_price_developer")
                else None
            ),
            "pro": (
                current_settings.stripe_price_pro
                if hasattr(current_settings, "stripe_price_pro")
                else None
            ),
            "proplus": (
                current_settings.stripe_price_proplus
                if hasattr(current_settings, "stripe_price_proplus")
                and not _is_placeholder(current_settings.stripe_price_proplus)
                else None
            ),
            "ultra": (
                current_settings.stripe_price_ultra
                if hasattr(current_settings, "stripe_price_ultra")
                and not _is_placeholder(current_settings.stripe_price_ultra)
                else None
            ),
            "team": (
                current_settings.stripe_price_team
                if hasattr(current_settings, "stripe_price_team")
                and not _is_placeholder(current_settings.stripe_price_team)
                else None
            ),
            "enterprise": None,  # sales-assisted only
            # Telys runtime plans: telys_developer is free (no Stripe SKU); pro/team are paid.
            "telys_developer": None,
            "telys_pro": (
                current_settings.stripe_price_telys_pro
                if hasattr(current_settings, "stripe_price_telys_pro")
                and not _is_placeholder(current_settings.stripe_price_telys_pro)
                else None
            ),
            "telys_team": (
                current_settings.stripe_price_telys_team
                if hasattr(current_settings, "stripe_price_telys_team")
                and not _is_placeholder(current_settings.stripe_price_telys_team)
                else None
            ),
            # Algenta engine plans: algenta_free is free (no SKU); pro/team are hosted per-seat; selfhost is
            # per-node ($199/node, self-serve provisions one node — see create_checkout_session).
            "algenta_free": None,
            "algenta_pro": (
                current_settings.stripe_price_algenta_pro
                if hasattr(current_settings, "stripe_price_algenta_pro")
                and not _is_placeholder(current_settings.stripe_price_algenta_pro)
                else None
            ),
            "algenta_team": (
                current_settings.stripe_price_algenta_team
                if hasattr(current_settings, "stripe_price_algenta_team")
                and not _is_placeholder(current_settings.stripe_price_algenta_team)
                else None
            ),
            "algenta_selfhost": (
                current_settings.stripe_price_algenta_selfhost
                if hasattr(current_settings, "stripe_price_algenta_selfhost")
                and not _is_placeholder(current_settings.stripe_price_algenta_selfhost)
                else None
            ),
        }

    def __getitem__(self, key: str) -> str | None:
        return self._current_mapping()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._current_mapping())

    def __len__(self) -> int:
        return len(self._current_mapping())

    def __repr__(self) -> str:
        return repr(self._current_mapping())


PLAN_PRICE_IDS: Mapping[str, str | None] = _PlanPriceIdMapping()

def _is_placeholder(value: str | None) -> bool:
    """A Stripe config value is a placeholder (= unconfigured) if it is empty or contains the words
    used in the shipped config defaults and CI fixtures ('replace', 'placeholder') — e.g.
    stripe_secret_key_replace_me, stripe_webhook_secret_replace_me, sk_test_placeholder, whsec_placeholder. A real test- or
    live-mode key/secret (sk_test_<id> / sk_live_<id> / whsec_<id>) contains neither."""
    if not value:
        return True
    low = value.lower()
    return "replace" in low or "placeholder" in low


def billing_configured(current_settings: object | None = None) -> bool:
    """True when a real Stripe secret key is set (the operator intends to run paid billing)."""
    s = current_settings or get_settings()
    return not _is_placeholder(getattr(s, "stripe_secret_key", ""))


def validate_billing_configuration(current_settings: object | None = None) -> None:
    """Fail-closed startup check: if billing is configured (a real STRIPE_SECRET_KEY), the webhook
    secret and price IDs must ALSO be real, not placeholders. A half-configured billing setup (real
    key, placeholder webhook/prices) silently mis-handles checkout + webhooks — refuse to start.

    A placeholder secret key means billing is off (free-tier-only deploy) → no validation.
    """
    s = current_settings or get_settings()
    if not billing_configured(s):
        return
    # Require the webhook secret + the live entry price (Pro). STRIPE_PRICE_DEVELOPER is intentionally
    # NOT required: the legacy Algenta "Developer" tier was archived from the Stripe catalog during the
    # Codna consolidation, so demanding it here fails-closed on a price that no longer exists (it broke
    # billing startup on codna-api). The higher Codna tiers (proplus/ultra/team) degrade gracefully —
    # a placeholder there just makes that one upgrade unavailable, not a silent mis-handle — so they
    # aren't hard-required either.
    missing = [
        env
        for attr, env in (
            ("stripe_webhook_secret", "STRIPE_WEBHOOK_SECRET"),
            ("stripe_price_pro", "STRIPE_PRICE_PRO"),
        )
        if _is_placeholder(getattr(s, attr, ""))
    ]
    if missing:
        raise RuntimeError(
            "Stripe billing is partially configured (STRIPE_SECRET_KEY is set) but these are still "
            "placeholders: " + ", ".join(missing) + ". Set them, or unset STRIPE_SECRET_KEY to run "
            "free-tier-only."
        )


def _stripe_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.stripe_secret_key}",
        "Content-Type": "application/x-www-form-urlencoded",
    }


def stripe_metering_enabled() -> bool:
    return get_settings().privacy_policy.metering_mode == "control_plane_sync"


def _stripe_url(path: str) -> str:
    return f"{_STRIPE_BASE_URL}{path}"


async def stripe_api_request(
    *,
    method: str,
    path: str,
    surface: str,
    audit_context: EgressAuditContext | None = None,
    timeout: float | httpx.Timeout | None = None,
    **request_kwargs: Any,
) -> httpx.Response:
    client_kwargs: dict[str, Any] | None = None
    if timeout is not None:
        client_kwargs = {"timeout": timeout}
    return await async_http_request(
        method=method,
        url=_stripe_url(path),
        surface=surface,
        explicit_configured=True,
        egress_class="operator_service",
        audit_context=audit_context,
        client_kwargs=client_kwargs,
        **request_kwargs,
    )


async def create_checkout_session(
    org_id: str,
    org_email: str,
    plan: str,
    success_url: str | None = None,
    cancel_url: str | None = None,
    audit_context: EgressAuditContext | None = None,
    quantity: int = 1,
) -> dict[str, str]:
    """
    Create a Stripe Checkout Session for upgrading to the given plan.
    Returns {"url": "https://checkout.stripe.com/..."}
    """
    price_id = PLAN_PRICE_IDS.get(plan)
    if not price_id or _is_placeholder(price_id):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "invalid_plan",
                    "message": f"No Stripe price configured for plan '{plan}'",
                }
            },
        )

    redirect_urls = resolve_billing_redirect_urls(settings_obj=settings)
    resolved_success_url = success_url or redirect_urls.success_url
    resolved_cancel_url = cancel_url or redirect_urls.cancel_url

    try:
        resp = await stripe_api_request(
            method="POST",
            path="/v1/checkout/sessions",
            surface="billing_checkout",
            audit_context=audit_context,
            headers=_stripe_headers(),
            data={
                "mode": "subscription",
                "line_items[0][price]": price_id,
                # per-seat plans (team) bill by quantity; solo plans stay at 1
                "line_items[0][quantity]": str(max(1, quantity)),
                "success_url": resolved_success_url,
                "cancel_url": resolved_cancel_url,
                "customer_email": org_email,
                "metadata[org_id]": org_id,
                "metadata[plan]": plan,
                **(
                    {
                        "line_items[0][adjustable_quantity][enabled]": "true",
                        "line_items[0][adjustable_quantity][minimum]": "1",
                    }
                    if plan in ("team", "telys_team", "algenta_team")
                    else {}
                ),
            },
        )
    except EgressPolicyDeniedError as exc:
        raise HTTPException(
            status_code=503,
            detail=exc.error_payload(
                message="Stripe checkout egress is blocked by the active privacy policy."
            ),
        ) from exc

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
    return_url: str | None = None,
    audit_context: EgressAuditContext | None = None,
) -> dict[str, str]:
    """
    Create a Stripe Customer Portal session for managing billing.
    Returns {"url": "https://billing.stripe.com/..."}
    """
    resolved_return_url = return_url or resolve_billing_redirect_urls(
        settings_obj=settings
    ).return_url
    try:
        resp = await stripe_api_request(
            method="POST",
            path="/v1/billing_portal/sessions",
            surface="billing_portal",
            audit_context=audit_context,
            headers=_stripe_headers(),
            data={
                "customer": customer_id,
                "return_url": resolved_return_url,
            },
        )
    except EgressPolicyDeniedError as exc:
        raise HTTPException(
            status_code=503,
            detail=exc.error_payload(
                message="Stripe billing portal egress is blocked by the active privacy policy."
            ),
        ) from exc

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
        expected = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise ValueError("Invalid signature")

        event = json.loads(payload)
        if not isinstance(event, dict):
            raise ValueError("Stripe webhook payload must decode to a JSON object")
        return dict(event)
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
