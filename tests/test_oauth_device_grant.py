"""OAuth 2.0 Device Authorization Grant (RFC 8628) — the CLI login flow at /oauth/device/*.

Pins the contract the shipped telys client (`telys login`) depends on: mint a (device_code, user_code) pair,
poll → authorization_pending until an authenticated user approves the user_code (binding their Supabase JWT),
then poll → the access_token exactly once. The Supabase verifier has its own tests; here it's stubbed so we
exercise the grant state machine end-to-end against the real device_grants store.
"""
from __future__ import annotations

import pytest

from apps.api_server.middleware.auth import get_redis
from apps.api_server.routers import oauth_device

GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"
_BEARER = {"Authorization": "Bearer JWT"}


async def _fake_redis(*_a, **_k):  # rate limiter is best-effort; a dummy keeps tests deterministic
    return None


def _stub_supabase(monkeypatch, *, sub="user-123", email="dev@example.com"):
    async def _verify(_token):
        return {"sub": sub, "email": email}

    monkeypatch.setattr(oauth_device, "verify_supabase_jwt", _verify)


async def _mint(client, client_id="telys-cli", scope="telys"):
    r = await client.post("/oauth/device/code", json={"client_id": client_id, "scope": scope})
    assert r.status_code == 200, r.text
    return r.json()


def _poll(client, device_code):
    return client.post(
        "/oauth/device/token",
        json={"client_id": "telys-cli", "device_code": device_code, "grant_type": GRANT_TYPE},
    )


async def test_code_endpoint_returns_verification_uri(client, app):
    app.dependency_overrides[get_redis] = _fake_redis
    try:
        body = await _mint(client)
        assert body["device_code"] and body["user_code"]
        assert body["verification_uri"].endswith("/device")
        assert "app=telys" in body["verification_uri_complete"]
        assert body["user_code"] in body["verification_uri_complete"]
        assert body["expires_in"] > 0 and body["interval"] >= 1
    finally:
        app.dependency_overrides.pop(get_redis, None)


async def test_unknown_client_rejected(client, app):
    app.dependency_overrides[get_redis] = _fake_redis
    try:
        r = await client.post("/oauth/device/code", json={"client_id": "evil-cli", "scope": "x"})
        assert r.status_code == 400 and r.json()["error"] == "invalid_client"
    finally:
        app.dependency_overrides.pop(get_redis, None)


async def test_poll_pending_before_approval(client, app):
    app.dependency_overrides[get_redis] = _fake_redis
    try:
        body = await _mint(client)
        r = await _poll(client, body["device_code"])
        assert r.status_code == 400 and r.json()["error"] == "authorization_pending"
    finally:
        app.dependency_overrides.pop(get_redis, None)


async def test_bad_grant_type_rejected(client, app):
    r = await client.post(
        "/oauth/device/token", json={"device_code": "x", "grant_type": "authorization_code"}
    )
    assert r.status_code == 400 and r.json()["error"] == "unsupported_grant_type"


async def test_unknown_device_code_rejected(client, app):
    r = await _poll(client, "does-not-exist")
    assert r.status_code == 400 and r.json()["error"] == "invalid_grant"


async def test_approve_then_redeem_once(client, app, monkeypatch):
    app.dependency_overrides[get_redis] = _fake_redis
    try:
        _stub_supabase(monkeypatch)
        body = await _mint(client)
        # approve as the signed-in user
        r = await client.post("/oauth/device/approve", headers=_BEARER, json={"user_code": body["user_code"]})
        assert r.status_code == 200 and r.json()["status"] == "approved"
        # first poll after approval → the Supabase JWT (last_polled_at is None so no slow_down)
        r = await _poll(client, body["device_code"])
        assert r.status_code == 200, r.text
        assert r.json()["access_token"] == "JWT" and r.json()["token_type"] == "Bearer"
        # single-use: the grant is consumed, a second redemption fails
        r = await _poll(client, body["device_code"])
        assert r.status_code == 400 and r.json()["error"] == "invalid_grant"
    finally:
        app.dependency_overrides.pop(get_redis, None)


async def test_slow_down_on_rapid_polling(client, app):
    app.dependency_overrides[get_redis] = _fake_redis
    try:
        body = await _mint(client)
        first = await _poll(client, body["device_code"])
        assert first.json()["error"] == "authorization_pending"  # first poll allowed
        second = await _poll(client, body["device_code"])  # immediate re-poll < interval
        assert second.status_code == 400 and second.json()["error"] == "slow_down"
    finally:
        app.dependency_overrides.pop(get_redis, None)


async def test_approve_requires_bearer(client, app):
    app.dependency_overrides[get_redis] = _fake_redis
    try:
        body = await _mint(client)
        r = await client.post("/oauth/device/approve", json={"user_code": body["user_code"]})
        assert r.status_code == 401
    finally:
        app.dependency_overrides.pop(get_redis, None)


async def test_approve_unknown_code_404(client, app, monkeypatch):
    app.dependency_overrides[get_redis] = _fake_redis
    try:
        _stub_supabase(monkeypatch)
        r = await client.post("/oauth/device/approve", headers=_BEARER, json={"user_code": "ZZZZ-ZZZZ"})
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(get_redis, None)
