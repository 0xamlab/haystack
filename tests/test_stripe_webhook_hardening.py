"""Wave 2 PR-4: Stripe webhook hardening — exactly-once idempotency, 5xx-on-failure, fail-closed config.

- validate_billing_configuration: refuse to start a half-configured billing setup (unit).
- the webhook dedups on event id (a duplicate delivery no-ops) and commits the event-id ledger row
  atomically with the state change; a processing failure rolls back and returns 5xx so Stripe retries.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import types
import uuid

import pytest
from sqlalchemy import select

from apps.api_server.models.stripe_webhook_event import StripeWebhookEvent
from apps.api_server.routers import billing
from apps.api_server.services import stripe_service
from apps.api_server.services.stripe_service import (
    billing_configured,
    validate_billing_configuration,
)

_WEBHOOK_SECRET = "whsec_test_hardening"


# ── validate_billing_configuration (fail-closed startup) ──────────────────────


def _settings(**over):
    base = {
        "stripe_secret_key": "sk_test_replace_me",
        "stripe_webhook_secret": "whsec_replace_me",
        "stripe_price_developer": "price_developer_replace_me",
        "stripe_price_pro": "price_pro_replace_me",
    }
    base.update(over)
    return types.SimpleNamespace(**base)


def test_billing_not_configured_skips_validation():
    # Placeholder secret key = billing off (free-tier-only deploy) → no raise.
    validate_billing_configuration(_settings())
    assert billing_configured(_settings()) is False


def test_partial_billing_config_fails_closed():
    # Real secret key but placeholder webhook + entry price → refuse to start.
    s = _settings(stripe_secret_key="sk_live_real")
    assert billing_configured(s) is True
    with pytest.raises(RuntimeError) as exc:
        validate_billing_configuration(s)
    msg = str(exc.value)
    assert "STRIPE_WEBHOOK_SECRET" in msg
    assert "STRIPE_PRICE_PRO" in msg
    # The archived Algenta "Developer" tier is NOT required — demanding it fails-closed on a price
    # that no longer exists in the Stripe catalog (this crashed billing startup on codna-api).
    assert "STRIPE_PRICE_DEVELOPER" not in msg


def test_placeholder_developer_price_does_not_block_startup():
    # Regression (codna-api): real secret + webhook + entry price, but the legacy developer price is
    # still a placeholder → must start cleanly. Enabling billing here previously crashed the app.
    s = _settings(
        stripe_secret_key="sk_live_real",
        stripe_webhook_secret="whsec_real",
        stripe_price_pro="price_pro_real",
        # stripe_price_developer stays "price_developer_replace_me" (archived tier, not set)
    )
    assert billing_configured(s) is True
    validate_billing_configuration(s)  # must not raise


def test_ci_placeholder_values_are_unconfigured():
    # The CI Test job sets STRIPE_SECRET_KEY=sk_test_placeholder / STRIPE_WEBHOOK_SECRET=whsec_placeholder.
    # These must read as "billing off" so the lifespan validation never fails CI startup.
    ci = _settings(stripe_secret_key="sk_test_placeholder", stripe_webhook_secret="whsec_placeholder")
    assert billing_configured(ci) is False
    validate_billing_configuration(ci)  # must not raise


def test_fully_configured_billing_passes():
    s = _settings(
        stripe_secret_key="sk_live_real",
        stripe_webhook_secret="whsec_real",
        stripe_price_developer="price_dev_real",
        stripe_price_pro="price_pro_real",
    )
    validate_billing_configuration(s)  # no raise


# ── webhook idempotency + 5xx (HTTP) ──────────────────────────────────────────


def _signed_event(event_id: str, event_type: str = "ping") -> tuple[bytes, str]:
    payload = json.dumps({"id": event_id, "type": event_type, "data": {"object": {}}}).encode()
    timestamp = str(int(time.time()))
    signed = f"{timestamp}.{payload.decode()}"
    sig = hmac.new(_WEBHOOK_SECRET.encode(), signed.encode(), hashlib.sha256).hexdigest()
    return payload, f"t={timestamp},v1={sig}"


async def _ledger_count(event_id: str) -> int:
    from apps.api_server.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.event_id == event_id)
        )
        return len(result.scalars().all())


async def test_webhook_is_idempotent_on_duplicate_event(client, monkeypatch):
    monkeypatch.setattr(
        stripe_service, "settings", types.SimpleNamespace(stripe_webhook_secret=_WEBHOOK_SECRET)
    )
    event_id = f"evt_{uuid.uuid4().hex}"
    payload, sig = _signed_event(event_id)
    headers = {"stripe-signature": sig, "content-type": "application/json"}

    r1 = await client.post("/v1/billing/webhook", content=payload, headers=headers)
    assert r1.status_code == 200, r1.text
    assert r1.json().get("duplicate") is not True

    r2 = await client.post("/v1/billing/webhook", content=payload, headers=headers)
    assert r2.status_code == 200, r2.text
    assert r2.json().get("duplicate") is True  # second delivery is a no-op

    assert await _ledger_count(event_id) == 1  # recorded exactly once

    # A different event id is processed normally.
    other_id = f"evt_{uuid.uuid4().hex}"
    p2, s2 = _signed_event(other_id)
    r3 = await client.post(
        "/v1/billing/webhook", content=p2, headers={"stripe-signature": s2, "content-type": "application/json"}
    )
    assert r3.status_code == 200
    assert r3.json().get("duplicate") is not True


async def test_webhook_returns_5xx_on_processing_failure(client, monkeypatch):
    monkeypatch.setattr(
        stripe_service, "settings", types.SimpleNamespace(stripe_webhook_secret=_WEBHOOK_SECRET)
    )

    async def _boom(db, event):
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(billing, "_process_stripe_event", _boom)

    event_id = f"evt_{uuid.uuid4().hex}"
    payload, sig = _signed_event(event_id)
    r = await client.post(
        "/v1/billing/webhook",
        content=payload,
        headers={"stripe-signature": sig, "content-type": "application/json"},
    )
    assert r.status_code == 500, r.text
    assert r.json()["error"]["code"] == "webhook_processing_failed"
    # The event-id ledger row was rolled back, so a Stripe retry will reprocess.
    assert await _ledger_count(event_id) == 0
