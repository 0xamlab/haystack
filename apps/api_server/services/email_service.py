"""
Email notification service.

Provides:
- send_quota_alert()          — 80% and 100% usage threshold emails
- send_welcome_email()        — Welcome email after signup
- send_verification_email()   — Email verification link
- send_password_reset_email() — Password reset link

Every email BODY lives as a published Resend Template (engine-* aliases) —
design and copy are managed in the Resend dashboard, never in this repo. When
Resend is unconfigured (self-hosted operators pointing SMTP at their own
relay), a minimal plain-text rendering of the same variables goes out instead;
there is deliberately no HTML in this file.
"""

import smtplib
from datetime import datetime
from email.mime.text import MIMEText

import structlog

from apps.api_server.config import SettingsProxy
from apps.api_server.services import plan_limits
from apps.api_server.services.egress_guard import (
    EgressAuditContext,
    EgressPolicyDeniedError,
    smtp_connection,
)
from apps.api_server.services.public_url_policy import (
    resolve_billing_dashboard_url,
    resolve_dashboard_url,
    resolve_email_verification_url,
    resolve_password_reset_url,
    resolve_simulate_endpoint_url,
)

logger = structlog.get_logger(__name__)
settings = SettingsProxy()


def _plan_display_name(plan: str) -> str:
    """Customer-facing plan name — internal lookup keys (sqai_developer, …) must
    never render in an email."""
    return plan_limits.get(plan).display_name.title()


def _billing_period_display(billing_period: str) -> str:
    """'2026-08' → 'August 2026'; unknown formats pass through unchanged."""
    try:
        return datetime.strptime(billing_period, "%Y-%m").strftime("%B %Y")
    except ValueError:
        return billing_period


# In-flight fire-and-forget sends (the loop holds only weak task references).
_background_sends: set = set()


def _send_template(
    to: str,
    template: str,
    variables: dict[str, str],
    *,
    fallback_subject: str,
    fallback_text: str,
    audit_context: EgressAuditContext | None = None,
) -> None:
    """Send one platform email. Routes through a published Resend Template when
    Resend is configured (the platform's transactional channel); falls back to a
    plain-text SMTP message only for self-hosted operators running their own
    relay — the fallback carries the same links, but no styled body."""
    from apps.api_server.services import resend_email

    if resend_email.is_configured():
        import asyncio

        async def _via_resend() -> None:
            await resend_email.send_template_email(to=to, template=template, variables=variables)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(_via_resend())  # sync caller (scripts)
        else:
            # Called from request handlers — schedule and return; email is a
            # best-effort side effect and must never block or fail the request.
            # Hold a reference until done: the event loop only keeps weak refs,
            # so an unreferenced task can be garbage-collected mid-send.
            task = loop.create_task(_via_resend())
            _background_sends.add(task)
            task.add_done_callback(_background_sends.discard)
        return
    try:
        msg = MIMEText(fallback_text, "plain")
        msg["Subject"] = fallback_subject
        msg["From"] = settings.email_from
        msg["To"] = to

        with smtp_connection(
            host=settings.smtp_host,
            port=settings.smtp_port,
            surface="smtp_email_delivery",
            explicit_configured=True,
            egress_class="operator_service",
            audit_context=audit_context,
            smtp_factory=smtplib.SMTP,
        ) as smtp:
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.sendmail(settings.email_from, [to], msg.as_string())

        logger.info("email_sent", to=to, subject=fallback_subject)
    except EgressPolicyDeniedError as exc:
        logger.error(
            "email_send_blocked",
            to=to,
            subject=fallback_subject,
            reason=exc.decision.reason,
        )
    except Exception as exc:
        logger.error("email_send_failed", to=to, subject=fallback_subject, error=str(exc))


def send_quota_alert(
    email: str,
    org_name: str,
    plan: str,
    used: int,
    limit: int,
    billing_period: str,
    pct: float,
    audit_context: EgressAuditContext | None = None,
) -> None:
    """
    Send a quota alert email at 80% or 100% usage.
    Called from simulate router after usage is recorded.
    """
    is_exhausted = pct >= 100
    billing_url = resolve_billing_dashboard_url(settings_obj=settings)
    period = _billing_period_display(billing_period)
    plan_name = _plan_display_name(plan)

    variables = {
        "org": org_name,
        "used": f"{used:,}",
        "limit": f"{limit:,}",
        "billing_period": period,
        "plan": plan_name,
        "billing_url": billing_url,
    }
    if is_exhausted:
        template = "engine-quota-100"
        fallback_subject = f"Quota exhausted — Algenta ({period})"
        fallback_text = (
            f"{org_name} has used all {limit:,} simulations for {period}. "
            f"New simulations are paused until the period resets or you upgrade: {billing_url}"
        )
    else:
        template = "engine-quota-80"
        variables["pct"] = f"{pct:.0f}"
        fallback_subject = f"{pct:.0f}% of your monthly quota used — Algenta ({period})"
        fallback_text = (
            f"{org_name} has used {used:,} of {limit:,} simulations in {period}. "
            f"Manage billing: {billing_url}"
        )
    _send_template(
        email,
        template,
        variables,
        fallback_subject=fallback_subject,
        fallback_text=fallback_text,
        audit_context=audit_context,
    )


def send_welcome_email(
    email: str,
    name: str,
    api_key_prefix: str,
    *,
    audit_context: EgressAuditContext | None = None,
) -> None:
    """Send a welcome email after signup with quickstart instructions."""
    simulate_url = resolve_simulate_endpoint_url(settings_obj=settings)
    dashboard_url = resolve_dashboard_url(settings_obj=settings)
    billing_url = resolve_billing_dashboard_url(settings_obj=settings)
    _send_template(
        email,
        "engine-welcome",
        {
            "name": name,
            "api_key_prefix": api_key_prefix,
            "simulate_url": simulate_url,
            "dashboard_url": dashboard_url,
            "billing_url": billing_url,
        },
        fallback_subject="Welcome to Algenta — your API key is ready",
        fallback_text=(
            f"Hi {name}, your account is ready. Your API key starts with {api_key_prefix}. "
            f"Dashboard: {dashboard_url}"
        ),
        audit_context=audit_context,
    )


async def send_verification_email(email: str, token: str) -> None:
    """Send an email verification link after signup."""
    verify_url = resolve_email_verification_url(token, settings_obj=settings)
    _send_template(
        email,
        "engine-verify",
        {"link": verify_url},
        fallback_subject="Verify your email — Algenta",
        fallback_text=f"Verify your email address (link expires in 24 hours): {verify_url}",
    )


async def send_password_reset_email(email: str, token: str) -> None:
    """Send a password reset link."""
    reset_url = resolve_password_reset_url(token, settings_obj=settings)
    _send_template(
        email,
        "engine-password-reset",
        {"link": reset_url},
        fallback_subject="Reset your Algenta password",
        fallback_text=f"Reset your password (link expires in 15 minutes): {reset_url}",
    )
