"""Wave 2 PR-2: signup abuse controls — Turnstile verifier, daily-email cap, config defaults.

Unit-level coverage of the new logic (the per-IP signup limit + per-org key-create limit reuse the
already-tested check_named_rate_limit). No network: httpx + settings are monkeypatched.
"""

from __future__ import annotations

import types

import pytest
from fastapi import HTTPException

from apps.api_server.config import Settings
from apps.api_server.routers.auth import _enforce_daily_email_signup_cap
from apps.api_server.services import captcha


def _settings(secret: str):
    return types.SimpleNamespace(turnstile_secret_key=secret)


class _FakeResp:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def _fake_ahr(payload=None, raise_exc=None):
    """Build a fake async_http_request that returns a JSON payload or raises."""

    async def _ahr(**kwargs):
        if raise_exc:
            raise raise_exc
        return _FakeResp(payload)

    return _ahr


# ── Turnstile verifier ────────────────────────────────────────────────────────


async def test_turnstile_noop_when_secret_unset(monkeypatch):
    monkeypatch.setattr(captcha, "get_settings", lambda: _settings(""))
    assert captcha.turnstile_enabled() is False
    assert await captcha.verify_turnstile(None) is True  # feature flag off → allow


async def test_turnstile_rejects_missing_token_when_enabled(monkeypatch):
    monkeypatch.setattr(captcha, "get_settings", lambda: _settings("sk_secret"))
    assert captcha.turnstile_enabled() is True
    assert await captcha.verify_turnstile(None) is False


async def test_turnstile_accepts_valid_token(monkeypatch):
    monkeypatch.setattr(captcha, "get_settings", lambda: _settings("sk_secret"))
    monkeypatch.setattr(captcha, "async_http_request", _fake_ahr(payload={"success": True}))
    assert await captcha.verify_turnstile("good-token", "1.2.3.4") is True


async def test_turnstile_rejects_invalid_token(monkeypatch):
    monkeypatch.setattr(captcha, "get_settings", lambda: _settings("sk_secret"))
    monkeypatch.setattr(
        captcha, "async_http_request", _fake_ahr(payload={"success": False, "error-codes": ["x"]})
    )
    assert await captcha.verify_turnstile("bad-token") is False


async def test_turnstile_fails_open_on_transport_error(monkeypatch):
    # A Cloudflare/egress outage must not block all signups; the rate limits remain the backstop.
    monkeypatch.setattr(captcha, "get_settings", lambda: _settings("sk_secret"))
    monkeypatch.setattr(captcha, "async_http_request", _fake_ahr(raise_exc=RuntimeError("network down")))
    assert await captcha.verify_turnstile("any") is True


# ── Per-email daily signup cap ─────────────────────────────────────────────────


class _CountingRedis:
    def __init__(self):
        self.counts: dict[str, int] = {}

    async def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key, ttl):
        return True


async def test_daily_email_cap_blocks_after_limit():
    redis = _CountingRedis()
    settings = types.SimpleNamespace(signup_max_per_day_per_email=2)
    # First two attempts for the same email pass; the third is rejected.
    await _enforce_daily_email_signup_cap("a@b.com", redis, settings)
    await _enforce_daily_email_signup_cap("a@b.com", redis, settings)
    with pytest.raises(HTTPException) as exc:
        await _enforce_daily_email_signup_cap("a@b.com", redis, settings)
    assert exc.value.status_code == 429
    assert exc.value.detail["error"]["code"] == "signup_limit_exceeded"


async def test_daily_email_cap_is_per_email():
    redis = _CountingRedis()
    settings = types.SimpleNamespace(signup_max_per_day_per_email=1)
    await _enforce_daily_email_signup_cap("a@b.com", redis, settings)
    await _enforce_daily_email_signup_cap("c@d.com", redis, settings)  # different email → fine


async def test_daily_email_cap_disabled_when_zero():
    redis = _CountingRedis()
    settings = types.SimpleNamespace(signup_max_per_day_per_email=0)
    for _ in range(5):
        await _enforce_daily_email_signup_cap("a@b.com", redis, settings)  # never raises


async def test_daily_email_cap_fails_open_on_redis_error():
    class _BrokenRedis:
        async def incr(self, key):
            raise RuntimeError("redis down")

    settings = types.SimpleNamespace(signup_max_per_day_per_email=1)
    await _enforce_daily_email_signup_cap("a@b.com", _BrokenRedis(), settings)  # no raise


# ── Config defaults ─────────────────────────────────────────────────────────────


def test_signup_abuse_settings_defaults():
    s = Settings()
    assert s.turnstile_secret_key == ""  # captcha off by default (feature flag)
    assert s.signup_rate_limit_per_minute == 3
    assert s.signup_max_per_day_per_email == 2
    assert s.api_key_create_rate_limit_per_minute == 10
