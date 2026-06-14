"""Cloudflare Turnstile verification for signup bot protection (Wave 2).

Feature-flagged: if no secret is configured (``settings.turnstile_secret_key == ""``) verification is
a no-op that ALLOWS the request, so self-host / dev / non-hosted deployments are unaffected and the
hosted control plane only enforces it once the secret is provisioned. When a secret is set, a missing
or invalid token is rejected. On a transient transport/parse/egress error talking to Cloudflare we
FAIL OPEN (allow) so a Cloudflare outage cannot take signups down — the per-IP and per-email rate
limits remain the backstop against abuse.

Outbound HTTP goes through the egress-guarded ``async_http_request`` (operator-service class), never
raw httpx, so the call is allowlist-enforced + audited like the Stripe integration.
"""

from __future__ import annotations

import structlog

from apps.api_server.config import get_settings
from apps.api_server.services.egress_guard import async_http_request

logger = structlog.get_logger(__name__)

_SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
_TIMEOUT_SECONDS = 5.0


def turnstile_enabled() -> bool:
    """True when a Turnstile secret is configured (the captcha feature flag)."""
    return bool(get_settings().turnstile_secret_key)


async def verify_turnstile(token: str | None, remote_ip: str | None = None) -> bool:
    """Verify a Cloudflare Turnstile token. Returns True if the request may proceed."""
    secret = get_settings().turnstile_secret_key
    if not secret:
        return True  # feature flag off — no captcha required
    if not token:
        return False  # captcha required but the client supplied no token
    data = {"secret": secret, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    try:
        response = await async_http_request(
            method="POST",
            url=_SITEVERIFY_URL,
            surface="turnstile_siteverify",
            egress_class="operator_service",
            explicit_configured=True,
            data=data,
            client_kwargs={"timeout": _TIMEOUT_SECONDS},
        )
        payload = response.json()
    except Exception as exc:
        # Fail open: a Cloudflare/egress outage must not block all signups; the rate limits cap abuse.
        logger.warning("turnstile_verification_unavailable", error=str(exc))
        return True
    success = bool(payload.get("success"))
    if not success:
        logger.warning("turnstile_verification_failed", error_codes=payload.get("error-codes"))
    return success
