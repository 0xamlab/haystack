"""Resend transactional email (team invites, dormant-account notices).

Every email body lives as a PUBLISHED Resend Template (engine-* aliases) —
design and copy are managed in the Resend dashboard, not in this repo. This
module only supplies the transport and the per-send variables.

Isolated + guarded: if RESEND_API_KEY is unset the send helpers no-op and log a
warning instead of raising, so the invite/accept flow still works end-to-end in
dev/CI without email delivery (mirrors the BYOK/Supabase "graceful when
unconfigured" pattern). Uses the Resend HTTP API directly via httpx.
"""

from __future__ import annotations

import re
from datetime import datetime

import httpx
import structlog

from apps.api_server.config import get_settings

log = structlog.get_logger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"

# Sender-facing brand context. The footer's site/linkedin links ride along with
# every template send — Resend requires every declared template variable at
# send time (declared fallbacks do NOT make them optional).
BRANDS: dict[str, dict[str, str]] = {
    "algenta": {
        "brand": "Algenta",
        "site": "https://algenta.ai",
        "linkedin": "https://www.linkedin.com/showcase/algenta-ai/",
    },
    "codna": {
        "brand": "Codna",
        "site": "https://codna.ai",
        "linkedin": "https://www.linkedin.com/showcase/codna-ai/",
    },
}


def is_configured() -> bool:
    return bool(get_settings().resend_api_key)


def _from_address(brand_name: str) -> str:
    """Display the brand as the sender name over the configured mailbox."""
    configured = get_settings().resend_from_email
    m = re.search(r"<([^>]+)>", configured)
    mailbox = m.group(1) if m else configured
    return f"{brand_name} <{mailbox}>"


async def _post_email(payload: dict) -> bool:
    settings = get_settings()
    if not settings.resend_api_key:
        log.warning("resend_unconfigured_email_skipped", to=payload.get("to"))
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                RESEND_ENDPOINT,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json=payload,
            )
        if resp.status_code >= 400:
            log.error(
                "resend_send_failed",
                to=payload.get("to"),
                status=resp.status_code,
                body=resp.text[:300],
            )
            return False
        return True
    except Exception as exc:  # noqa: BLE001 — email must never break the request
        log.error("resend_send_error", to=payload.get("to"), error=str(exc))
        return False


async def send_email(to: str, subject: str, html_body: str) -> bool:
    """Low-level raw send (self-hosted escape hatch; platform emails use
    send_template_email so all bodies stay dashboard-managed)."""
    settings = get_settings()
    return await _post_email(
        {
            "from": settings.resend_from_email,
            "to": [to],
            "subject": subject,
            "html": html_body,
        }
    )


async def send_template_email(
    *,
    to: str,
    template: str,
    variables: dict[str, str],
    brand: str = "algenta",
) -> bool:
    """Send via a published Resend Template alias. The subject is baked into the
    template; brand/site/linkedin are merged in for the shared header + footer."""
    ctx = BRANDS.get(brand, BRANDS["algenta"])
    return await _post_email(
        {
            "from": _from_address(ctx["brand"]),
            "to": [to],
            "template": {"id": template, "variables": {**ctx, **variables}},
        }
    )


def _plain(value: str) -> str:
    """Template variables render unescaped (triple-brace) into HTML bodies AND
    plain-text subjects, so user-controlled values must carry no markup."""
    return re.sub(r"[<>]", "", value)


def _human_date(iso_date: str) -> str:
    """'2026-09-12' → 'September 12, 2026'; unknown formats pass through."""
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d")
    except ValueError:
        return iso_date
    return f"{d.strftime('%B')} {d.day}, {d.year}"


async def send_dormant_warning_email(*, to: str, days_left: int, delete_on: str, keep_url: str) -> bool:
    when = "today" if days_left <= 1 else f"in {days_left} days"
    return await send_template_email(
        to=to,
        template="engine-dormant-warning",
        variables={"when": when, "delete_on": _human_date(delete_on), "link": keep_url},
        brand="codna",
    )


async def send_dormant_deleted_email(*, to: str) -> bool:
    return await send_template_email(
        to=to,
        template="engine-dormant-deleted",
        variables={},
        brand="codna",
    )


async def send_team_invite_email(*, to: str, org_name: str, role: str, accept_url: str) -> bool:
    return await send_template_email(
        to=to,
        template="engine-invite",
        variables={
            "org": _plain(org_name or "your team"),
            "role": _plain(role or "member"),
            "link": accept_url,
        },
        brand="codna",
    )
