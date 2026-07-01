"""Resend transactional email (team invites, dormant-account notices).

Isolated + guarded: if RESEND_API_KEY is unset the send helpers no-op and log a
warning instead of raising, so the invite/accept flow still works end-to-end in
dev/CI without email delivery (mirrors the BYOK/Supabase "graceful when
unconfigured" pattern). Uses the Resend HTTP API directly via httpx.
"""

from __future__ import annotations

import html as _html

import httpx
import structlog

from apps.api_server.config import get_settings

log = structlog.get_logger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"


def is_configured() -> bool:
    return bool(get_settings().resend_api_key)


async def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send one transactional email via Resend. Returns True if accepted, False if
    unconfigured or on error (never raises — email is a best-effort side effect)."""
    settings = get_settings()
    if not settings.resend_api_key:
        log.warning("resend_unconfigured_email_skipped", to=to, subject=subject)
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                RESEND_ENDPOINT,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.resend_from_email,
                    "to": [to],
                    "subject": subject,
                    "html": html_body,
                },
            )
        if resp.status_code >= 400:
            log.error("resend_send_failed", to=to, status=resp.status_code, body=resp.text[:300])
            return False
        return True
    except Exception as exc:  # noqa: BLE001 — email must never break the request
        log.error("resend_send_error", to=to, error=str(exc))
        return False


async def send_dormant_warning_email(*, to: str, days_left: int, delete_on: str, keep_url: str) -> bool:
    when = "today" if days_left <= 1 else f"in {days_left} days"
    subject = f"Your Codna account will be deleted {when}"
    body = f"""
    <div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:520px;margin:0 auto;color:#0b1020">
      <h2 style="font-weight:820;letter-spacing:-.03em">We miss you at Codna</h2>
      <p style="color:#3a4252;font-size:16px;line-height:1.5">
        Your account has been inactive for a while. To respect your data, we delete accounts after
        12 months of inactivity. Unless you sign in, <strong>your account and its data will be
        permanently deleted on {_html.escape(delete_on)}</strong> ({when}).
      </p>
      <p style="margin:28px 0">
        <a href="{_html.escape(keep_url)}"
           style="background:#2563ff;color:#fff;padding:12px 22px;border-radius:12px;text-decoration:none;font-weight:700">
          Keep my account — sign in
        </a>
      </p>
      <p style="color:#8a94a6;font-size:13px">Just signing in keeps your account active. Paid subscribers are never affected.</p>
    </div>
    """
    return await send_email(to=to, subject=subject, html_body=body)


async def send_dormant_deleted_email(*, to: str) -> bool:
    subject = "Your Codna account has been deleted"
    body = """
    <div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:520px;margin:0 auto;color:#0b1020">
      <h2 style="font-weight:820;letter-spacing:-.03em">Account deleted</h2>
      <p style="color:#3a4252;font-size:16px;line-height:1.5">
        As we warned, your inactive Codna account and its data have now been deleted under our
        12-month data-retention policy. You're welcome back anytime — just sign up again.
      </p>
    </div>
    """
    return await send_email(to=to, subject=subject, html_body=body)


async def send_team_invite_email(*, to: str, org_name: str, role: str, accept_url: str) -> bool:
    org = _html.escape(org_name or "your team")
    role_s = _html.escape(role or "member")
    subject = f"You're invited to join {org} on Codna"
    body = f"""
    <div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:520px;margin:0 auto;color:#0b1020">
      <h2 style="font-weight:820;letter-spacing:-.03em">Join {org} on Codna</h2>
      <p style="color:#3a4252;font-size:16px;line-height:1.5">
        You've been invited to join <strong>{org}</strong> as a <strong>{role_s}</strong>.
        Codna gives your team deterministic repo understanding and test-verified fixes.
      </p>
      <p style="margin:28px 0">
        <a href="{_html.escape(accept_url)}"
           style="background:#2563ff;color:#fff;padding:12px 22px;border-radius:12px;text-decoration:none;font-weight:700">
          Accept invitation
        </a>
      </p>
      <p style="color:#8a94a6;font-size:13px">This invitation expires in 7 days. If you weren't expecting it, you can ignore this email.</p>
    </div>
    """
    return await send_email(to=to, subject=subject, html_body=body)
