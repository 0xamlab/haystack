"""
Email notification service.

Provides:
- send_quota_alert()   — Send 80% and 100% usage threshold emails
- send_welcome_email() — Welcome email after signup

Uses SMTP (defaults to dev mailhog on port 1025, configure for SendGrid/SES in prod).
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

from apps.api_server.config import SettingsProxy
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


def _send(
    to: str,
    subject: str,
    html: str,
    *,
    audit_context: EgressAuditContext | None = None,
) -> None:
    """Send an email via SMTP. Logs errors but does not raise."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.email_from
        msg["To"] = to
        msg.attach(MIMEText(html, "html"))

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

        logger.info("email_sent", to=to, subject=subject)
    except EgressPolicyDeniedError as exc:
        logger.error(
            "email_send_blocked",
            to=to,
            subject=subject,
            reason=exc.decision.reason,
        )
    except Exception as exc:
        logger.error("email_send_failed", to=to, subject=subject, error=str(exc))


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

    if is_exhausted:
        subject = f"⚠️ Quota exhausted — Codna ({billing_period})"
        headline = "You've used 100% of your monthly quota"
        body = (
            f"Your organization <strong>{org_name}</strong> has exhausted its "
            f"{limit:,} simulation quota for {billing_period}. "
            f"New simulations will be blocked until the period resets or you upgrade your plan."
        )
        cta = "Upgrade now"
        cta_color = "#ef4444"
    else:
        subject = f"⚡ 80% quota used — Codna ({billing_period})"
        headline = f"You've used {pct:.0f}% of your monthly quota"
        body = (
            f"Your organization <strong>{org_name}</strong> has used "
            f"{used:,} of {limit:,} simulations in {billing_period}. "
            f"Consider upgrading your plan before you hit the limit."
        )
        cta = "View usage"
        cta_color = "#eab308"

    html = f"""
<!DOCTYPE html>
<html>
<body
  style="font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; padding: 40px;"
>
  <div
    style="
      max-width: 560px;
      margin: 0 auto;
      background: #1e293b;
      border-radius: 12px;
      padding: 32px;
    "
  >
    <div style="font-size: 24px; font-weight: 700; color: #fff; margin-bottom: 8px;">
      Codna
    </div>
    <div style="height: 1px; background: #334155; margin-bottom: 24px;"></div>
    <h1 style="font-size: 20px; color: #fff; margin: 0 0 12px;">{headline}</h1>
    <p style="color: #94a3b8; line-height: 1.6; margin: 0 0 24px;">{body}</p>
    <div style="background: #0f172a; border-radius: 8px; padding: 16px; margin-bottom: 24px;">
      <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
        <span style="color: #64748b; font-size: 14px;">Used</span>
        <span style="color: #fff; font-size: 14px; font-weight: 600;">{used:,} / {limit:,}</span>
      </div>
      <div style="background: #1e293b; border-radius: 99px; height: 8px; overflow: hidden;">
        <div
          style="
            background: {cta_color};
            height: 8px;
            width: {min(pct, 100):.0f}%;
            border-radius: 99px;
          "
        ></div>
      </div>
    </div>
    <a href="{billing_url}" style="
      display: inline-block;
      background: {cta_color};
      color: #fff;
      text-decoration: none;
      padding: 12px 24px;
      border-radius: 8px;
      font-weight: 600;
      font-size: 14px;
    ">{cta} →</a>
    <p style="color: #475569; font-size: 12px; margin-top: 24px;">
      You're on the <strong>{plan}</strong> plan.
      <a href="{billing_url}" style="color: #818cf8;">Manage billing</a>
    </p>
  </div>
</body>
</html>
"""
    _send(email, subject, html, audit_context=audit_context)


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
    html = f"""
<!DOCTYPE html>
<html>
<body
  style="font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; padding: 40px;"
>
  <div
    style="
      max-width: 560px;
      margin: 0 auto;
      background: #1e293b;
      border-radius: 12px;
      padding: 32px;
    "
  >
    <div style="font-size: 24px; font-weight: 700; color: #fff; margin-bottom: 24px;">
      Welcome to Codna
    </div>
    <p style="color: #94a3b8; line-height: 1.6;">Hi {name},</p>
    <p style="color: #94a3b8; line-height: 1.6;">
      Your account is ready. Here's your first API call:
    </p>
    <pre
      style="
        background: #0f172a;
        border-radius: 8px;
        padding: 16px;
        font-size: 13px;
        color: #a5b4fc;
        overflow-x: auto;
      "
    >
curl -X POST {simulate_url} \\
  -H "Authorization: Bearer {api_key_prefix}..." \\
  -d '{{"mode":"auto","scenario":{{"variables":{{"revenue":{{"low":80000,"high":200000}}}}}}}}'
    </pre>
    <a href="{dashboard_url}" style="
      display: inline-block;
      background: #4f63ff;
      color: #fff;
      text-decoration: none;
      padding: 12px 24px;
      border-radius: 8px;
      font-weight: 600;
      font-size: 14px;
      margin-top: 16px;
    ">Open Dashboard →</a>
    <p style="color: #475569; font-size: 12px; margin-top: 24px;">
      You're on the free plan — 500 simulations/month.
      <a href="{billing_url}" style="color: #818cf8;">
        Upgrade anytime.
      </a>
    </p>
  </div>
</body>
</html>
"""
    _send(
        email,
        "Welcome to Codna — your API key is ready",
        html,
        audit_context=audit_context,
    )


async def send_verification_email(email: str, token: str) -> None:
    """Send an email verification link after signup."""
    verify_url = resolve_email_verification_url(token, settings_obj=settings)

    html = f"""
<!DOCTYPE html>
<html>
<body
  style="font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; padding: 40px;"
>
  <div
    style="
      max-width: 520px;
      margin: 0 auto;
      background: #1e293b;
      border-radius: 12px;
      padding: 32px;
    "
  >
    <div style="font-size: 22px; font-weight: 700; color: #fff; margin-bottom: 20px;">
      Verify your email
    </div>
    <p style="color: #94a3b8; line-height: 1.6; margin-bottom: 24px;">
      Click the button below to verify your email address and activate your Codna account.
      This link expires in 24 hours.
    </p>
    <a href="{verify_url}" style="
      display:inline-block;
      background:#6b42fc;
      color:#fff;
      text-decoration:none;
      padding:12px 24px;
      border-radius:8px;
      font-weight:600;
      font-size:14px;
    ">
      Verify Email →
    </a>
    <p style="color:#475569;font-size:12px;margin-top:24px;">
      If you didn't create an Codna account, ignore this email.
    </p>
  </div>
</body>
</html>
"""
    _send(email, "Verify your email — Codna", html)


async def send_password_reset_email(email: str, token: str) -> None:
    """Send a password reset link."""
    reset_url = resolve_password_reset_url(token, settings_obj=settings)

    html = f"""
<!DOCTYPE html>
<html>
<body
  style="font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; padding: 40px;"
>
  <div
    style="
      max-width: 520px;
      margin: 0 auto;
      background: #1e293b;
      border-radius: 12px;
      padding: 32px;
    "
  >
    <div style="font-size: 22px; font-weight: 700; color: #fff; margin-bottom: 20px;">
      Reset your password
    </div>
    <p style="color: #94a3b8; line-height: 1.6; margin-bottom: 24px;">
      Click the button below to reset your password. This link expires in 15 minutes.
    </p>
    <a href="{reset_url}" style="
      display:inline-block;
      background:#ef4444;
      color:#fff;
      text-decoration:none;
      padding:12px 24px;
      border-radius:8px;
      font-weight:600;
      font-size:14px;
    ">
      Reset Password →
    </a>
    <p style="color:#475569;font-size:12px;margin-top:24px;">
      If you didn't request this, ignore this email — your password won't change.
    </p>
  </div>
</body>
</html>
"""
    _send(email, "Reset your Codna password", html)
