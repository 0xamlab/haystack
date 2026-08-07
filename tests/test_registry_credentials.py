"""POST /v1/registry/credentials — installer distribution credentials (device-login token in,
read-only registry credentials out).

The one-line self-hosted installer authenticates through the same device-login path as the
SDKs and exchanges the Supabase access token for pull credentials here. The Supabase
verifier has its own tests; here it's stubbed (mirrors test_product_onboard.py).
"""
from __future__ import annotations

from apps.api_server.config import get_settings
from apps.api_server.middleware.auth import get_redis
from apps.api_server.routers import registry_credentials as registry_router


async def _fake_redis():  # rate limiter is best-effort; a dummy keeps tests deterministic
    return None


def _stub_supabase(monkeypatch, *, ok: bool = True):
    async def _verify(_token):
        if not ok:
            from apps.api_server.services.supabase_auth import SupabaseAuthError

            raise SupabaseAuthError("invalid_token", "bad or expired token")
        return {"email": "selfhoster@example.com", "user_metadata": {}}

    monkeypatch.setattr(registry_router, "verify_supabase_jwt", _verify)


def _set_registry_env(monkeypatch, *, configured: bool):
    get_settings.cache_clear()
    if configured:
        monkeypatch.setenv("ALGENTA_REGISTRY_URL", "ghcr.io")
        monkeypatch.setenv("ALGENTA_REGISTRY_USERNAME", "algenta-puller")
        monkeypatch.setenv("ALGENTA_REGISTRY_READ_TOKEN", "ghro_readonly_token")
    else:
        monkeypatch.delenv("ALGENTA_REGISTRY_USERNAME", raising=False)
        monkeypatch.delenv("ALGENTA_REGISTRY_READ_TOKEN", raising=False)


async def test_registry_credentials_serves_configured_credentials(client, app, monkeypatch):
    _stub_supabase(monkeypatch)
    _set_registry_env(monkeypatch, configured=True)
    app.dependency_overrides[get_redis] = _fake_redis
    try:
        r = await client.post("/v1/registry/credentials", headers={"authorization": "Bearer JWT"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body == {
            "registry": "ghcr.io",
            "username": "algenta-puller",
            "password": "ghro_readonly_token",
        }
    finally:
        app.dependency_overrides.pop(get_redis, None)
        get_settings.cache_clear()


async def test_registry_credentials_503_when_distribution_not_configured(client, app, monkeypatch):
    _stub_supabase(monkeypatch)
    _set_registry_env(monkeypatch, configured=False)
    app.dependency_overrides[get_redis] = _fake_redis
    try:
        r = await client.post("/v1/registry/credentials", headers={"authorization": "Bearer JWT"})
        assert r.status_code == 503, r.text
        error = r.json()["error"]
        assert error["code"] == "registry_distribution_disabled"
    finally:
        app.dependency_overrides.pop(get_redis, None)
        get_settings.cache_clear()


async def test_registry_credentials_requires_authorization(client, app, monkeypatch):
    _set_registry_env(monkeypatch, configured=True)
    app.dependency_overrides[get_redis] = _fake_redis
    try:
        r = await client.post("/v1/registry/credentials")
        assert r.status_code == 401, r.text
    finally:
        app.dependency_overrides.pop(get_redis, None)
        get_settings.cache_clear()


async def test_registry_credentials_rejects_bad_token(client, app, monkeypatch):
    _stub_supabase(monkeypatch, ok=False)
    _set_registry_env(monkeypatch, configured=True)
    app.dependency_overrides[get_redis] = _fake_redis
    try:
        r = await client.post("/v1/registry/credentials", headers={"authorization": "Bearer BAD"})
        assert r.status_code == 401, r.text
    finally:
        app.dependency_overrides.pop(get_redis, None)
        get_settings.cache_clear()
