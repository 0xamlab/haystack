"""Unit tests for Phase 5B — Stripe service, email service, billing."""

import hashlib
import hmac
import json
import time
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from apps.api_server.services.email_service import send_quota_alert, send_welcome_email
from apps.api_server.services.stripe_service import verify_stripe_webhook

# ─── verify_stripe_webhook ────────────────────────────────────────────────────


class TestVerifyStripeWebhook:
    def _make_sig_header(self, payload: bytes, secret: str = "whsec_test") -> str:
        timestamp = str(int(time.time()))
        signed = f"{timestamp}.{payload.decode()}"
        sig = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
        return f"t={timestamp},v1={sig}"

    def test_valid_signature_returns_event(self):
        payload = json.dumps({"type": "checkout.session.completed", "id": "evt_123"}).encode()
        with patch("apps.api_server.services.stripe_service.settings") as mock_settings:
            mock_settings.stripe_webhook_secret = "whsec_test"
            sig = self._make_sig_header(payload, "whsec_test")
            event = verify_stripe_webhook(payload, sig)
            assert event["type"] == "checkout.session.completed"

    def test_invalid_signature_raises_400(self):
        payload = json.dumps({"type": "test"}).encode()
        with patch("apps.api_server.services.stripe_service.settings") as mock_settings:
            mock_settings.stripe_webhook_secret = "whsec_test"
            with pytest.raises(HTTPException) as exc_info:
                verify_stripe_webhook(payload, "t=123,v1=badsignature")
            assert exc_info.value.status_code == 400

    def test_empty_sig_header_raises_400(self):
        payload = b'{"type": "test"}'
        with patch("apps.api_server.services.stripe_service.settings") as mock_settings:
            mock_settings.stripe_webhook_secret = "whsec_test"
            with pytest.raises(HTTPException) as exc_info:
                verify_stripe_webhook(payload, "")
            assert exc_info.value.status_code == 400

    def test_tampered_payload_raises_400(self):
        original = json.dumps({"type": "checkout.session.completed"}).encode()
        with patch("apps.api_server.services.stripe_service.settings") as mock_settings:
            mock_settings.stripe_webhook_secret = "whsec_test"
            sig = self._make_sig_header(original, "whsec_test")
            tampered = json.dumps({"type": "evil_event"}).encode()
            with pytest.raises(HTTPException):
                verify_stripe_webhook(tampered, sig)


# ─── send_quota_alert ─────────────────────────────────────────────────────────


class TestSendQuotaAlert:
    def test_80pct_alert_sends_email(self):
        with patch("apps.api_server.services.email_service._send_template") as mock_send:
            send_quota_alert(
                email="dev@example.com",
                org_name="Acme Corp",
                plan="free",
                used=400,
                limit=500,
                billing_period="2026-03",
                pct=80.0,
            )
            mock_send.assert_called_once()
            args = mock_send.call_args[0]
            assert args[0] == "dev@example.com"
            assert args[1] == "engine-quota-80"
            assert args[2]["pct"] == "80"

    def test_100pct_alert_sends_exhausted_email(self):
        with patch("apps.api_server.services.email_service._send_template") as mock_send:
            send_quota_alert(
                email="dev@example.com",
                org_name="Acme Corp",
                plan="free",
                used=500,
                limit=500,
                billing_period="2026-03",
                pct=100.0,
            )
            mock_send.assert_called_once()
            args = mock_send.call_args[0]
            assert args[1] == "engine-quota-100"
            assert "exhausted" in mock_send.call_args[1]["fallback_subject"].lower()

    def test_alert_variables_contain_usage_numbers(self):
        with patch("apps.api_server.services.email_service._send_template") as mock_send:
            send_quota_alert(
                email="test@test.com",
                org_name="Test Org",
                plan="developer",
                used=8000,
                limit=10000,
                billing_period="2026-03",
                pct=80.0,
            )
            variables = mock_send.call_args[0][2]
            assert variables["used"] == "8,000"
            assert variables["limit"] == "10,000"

    def test_smtp_failure_does_not_raise(self):
        """Email send failure should log and not propagate."""
        with patch("apps.api_server.services.email_service.smtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = Exception("SMTP connection refused")
            # Should NOT raise — fails silently
            send_quota_alert(
                email="test@test.com",
                org_name="Test",
                plan="free",
                used=500,
                limit=500,
                billing_period="2026-03",
                pct=100.0,
            )


# ─── send_welcome_email ────────────────────────────────────────────────────────


class TestSendWelcomeEmail:
    def test_welcome_email_sent(self):
        with patch("apps.api_server.services.email_service._send_template") as mock_send:
            send_welcome_email("user@example.com", "Alice", "de_live_abc123")
            mock_send.assert_called_once()
            args = mock_send.call_args[0]
            assert args[0] == "user@example.com"
            assert args[1] == "engine-welcome"

    def test_welcome_email_contains_key_prefix(self):
        with patch("apps.api_server.services.email_service._send_template") as mock_send:
            send_welcome_email("user@example.com", "Bob", "de_live_xyz789")
            variables = mock_send.call_args[0][2]
            assert variables["api_key_prefix"] == "de_live_xyz789"

    def test_welcome_email_smtp_failure_does_not_raise(self):
        with patch("apps.api_server.services.email_service.smtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = ConnectionRefusedError("SMTP down")
            send_welcome_email("user@example.com", "Charlie", "de_live_test")


# ─── PLAN_PRICE_IDS ──────────────────────────────────────────────────────────


class TestStripePlanConfig:
    def test_developer_plan_has_price_id(self):
        from apps.api_server.services.stripe_service import PLAN_PRICE_IDS

        assert "developer" in PLAN_PRICE_IDS

    def test_pro_plan_has_price_id(self):
        from apps.api_server.services.stripe_service import PLAN_PRICE_IDS

        assert "pro" in PLAN_PRICE_IDS

    def test_enterprise_plan_is_none(self):
        from apps.api_server.services.stripe_service import PLAN_PRICE_IDS

        assert PLAN_PRICE_IDS["enterprise"] is None

    def test_free_plan_is_none(self):
        from apps.api_server.services.stripe_service import PLAN_PRICE_IDS

        assert PLAN_PRICE_IDS["free"] is None
