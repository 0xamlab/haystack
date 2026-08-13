"""Email transport routing (apps/api_server/services/email_service._send_template).

The SMTP default of localhost:1025 silently dropped every verification and
welcome email. Platform emails now go out as published Resend Templates
whenever Resend is configured — from async request handlers (fire-and-forget
task) and sync scripts alike — and only fall back to a plain-text SMTP message
for self-hosted operators with their own relay. No email HTML lives in the
repo; the templates are managed in the Resend dashboard.
"""
from __future__ import annotations

import asyncio

import pytest

from apps.api_server.services import email_service, resend_email


@pytest.fixture()
def captured(monkeypatch):
    box: list[dict] = []

    async def fake_send(*, to: str, template: str, variables: dict, brand: str = "algenta") -> bool:
        box.append({"to": to, "template": template, "variables": variables, "brand": brand})
        return True

    monkeypatch.setattr(resend_email, "is_configured", lambda: True)
    monkeypatch.setattr(resend_email, "send_template_email", fake_send)
    return box


def test_sync_caller_routes_via_resend(captured) -> None:
    email_service._send_template(
        "dev@example.com",
        "engine-verify",
        {"link": "https://x.example/verify"},
        fallback_subject="Subject",
        fallback_text="hi",
    )
    assert captured == [
        {
            "to": "dev@example.com",
            "template": "engine-verify",
            "variables": {"link": "https://x.example/verify"},
            "brand": "algenta",
        }
    ]


@pytest.mark.anyio
async def test_async_caller_schedules_via_resend(captured) -> None:
    email_service._send_template(
        "dev@example.com",
        "engine-verify",
        {"link": "https://x.example/verify"},
        fallback_subject="Subject",
        fallback_text="hi",
    )
    await asyncio.sleep(0)  # let the fire-and-forget task run
    assert captured and captured[0]["to"] == "dev@example.com"


@pytest.mark.anyio
async def test_verification_email_reaches_resend(captured) -> None:
    await email_service.send_verification_email("dev@example.com", "tok-123")
    await asyncio.sleep(0)
    assert captured and captured[0]["template"] == "engine-verify"
    assert "tok-123" in captured[0]["variables"]["link"]


@pytest.mark.anyio
async def test_template_senders_carry_brand_context() -> None:
    """send_template_email merges brand/site/linkedin into every payload —
    Resend requires every declared template variable at send time."""
    sent: list[dict] = []

    async def fake_post(payload: dict) -> bool:
        sent.append(payload)
        return True

    orig = resend_email._post_email
    resend_email._post_email = fake_post  # type: ignore[assignment]
    try:
        await resend_email.send_team_invite_email(
            to="dev@example.com", org_name="Acme", role="admin", accept_url="https://x.example/a"
        )
    finally:
        resend_email._post_email = orig  # type: ignore[assignment]

    assert sent, "no payload posted"
    tpl = sent[0]["template"]
    assert tpl["id"] == "engine-invite"
    for required in ("brand", "site", "linkedin", "org", "role", "link"):
        assert required in tpl["variables"], f"missing template variable {required}"
    assert tpl["variables"]["brand"] == "Codna"
    assert sent[0]["from"].startswith("Codna <")
