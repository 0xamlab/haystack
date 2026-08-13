"""Email transport routing (apps/api_server/services/email_service._send).

The SMTP default of localhost:1025 silently dropped every verification and
welcome email. _send now routes through Resend whenever it is configured —
from async request handlers (fire-and-forget task) and sync scripts alike —
and only falls back to SMTP for self-hosted operators with their own relay.
"""
from __future__ import annotations

import asyncio

import pytest

from apps.api_server.services import email_service, resend_email


@pytest.fixture()
def captured(monkeypatch):
    box: list[dict] = []

    async def fake_send(*, to: str, subject: str, html_body: str) -> bool:
        box.append({"to": to, "subject": subject, "html": html_body})
        return True

    monkeypatch.setattr(resend_email, "is_configured", lambda: True)
    monkeypatch.setattr(resend_email, "send_email", fake_send)
    return box


def test_sync_caller_routes_via_resend(captured) -> None:
    email_service._send("dev@example.com", "Subject", "<b>hi</b>")
    assert captured == [{"to": "dev@example.com", "subject": "Subject", "html": "<b>hi</b>"}]


@pytest.mark.anyio
async def test_async_caller_schedules_via_resend(captured) -> None:
    email_service._send("dev@example.com", "Subject", "<b>hi</b>")
    await asyncio.sleep(0)  # let the fire-and-forget task run
    assert captured and captured[0]["to"] == "dev@example.com"


@pytest.mark.anyio
async def test_verification_email_reaches_resend(captured) -> None:
    await email_service.send_verification_email("dev@example.com", "tok-123")
    await asyncio.sleep(0)
    assert captured and "tok-123" in captured[0]["html"]
