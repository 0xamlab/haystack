"""Supabase JWT verification + GitHub-identity extraction for the website BYOK bridge.

Covers the HS256 path (asymmetric/JWKS is exercised via the live Supabase project, not unit-mocked
here): happy verify, expired/aud/issuer/signature rejections, the unconfigured-secret guard, and the
identity-extraction rules (GitHub-only, numeric id required, sub fallback, login normalization)."""
from __future__ import annotations

import time

import jwt
import pytest

from apps.api_server.config import get_settings
from apps.api_server.services import supabase_auth
from apps.api_server.services.supabase_auth import SupabaseAuthError, extract_github_identity

_SECRET = "test-supabase-hs256-secret-value-at-least-32-bytes-long"
_BASE = "http://127.0.0.1:54421"
_ISS = f"{_BASE}/auth/v1"


@pytest.fixture
def supabase_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", _BASE)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", _SECRET)
    monkeypatch.delenv("SUPABASE_JWT_AUD", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _token(
    *,
    secret=_SECRET,
    iss=_ISS,
    aud="authenticated",
    exp_delta=3600,
    user_metadata=None,
    app_metadata=None,
    **extra,
):
    now = int(time.time())
    payload = {
        "iss": iss,
        "sub": "8a9f1c2e-3b4d-5e6f-7a8b-9c0d1e2f3a4b",  # Supabase UUID (NOT the GitHub id)
        "aud": aud,
        "role": "authenticated",
        "iat": now,
        "exp": now + exp_delta,
        "email": "octocat@example.com",
        "app_metadata": app_metadata
        if app_metadata is not None
        else {"provider": "github", "providers": ["github"]},
        "user_metadata": user_metadata
        if user_metadata is not None
        else {
            "provider_id": "583231",
            "sub": "583231",
            "user_name": "Octocat",
            "name": "The Octocat",
        },
    }
    payload.update(extra)
    return jwt.encode(payload, secret, algorithm="HS256")


async def test_verify_hs256_happy_path(supabase_env):
    claims = await supabase_auth.verify_supabase_jwt(_token())
    assert claims["user_metadata"]["provider_id"] == "583231"
    ident = extract_github_identity(claims)
    assert ident == {
        "github_user_id": 583231,
        "github_login": "octocat",  # normalized lowercase
        "email": "octocat@example.com",
    }


async def test_verify_rejects_expired(supabase_env):
    with pytest.raises(SupabaseAuthError) as exc:
        await supabase_auth.verify_supabase_jwt(_token(exp_delta=-3600))
    assert exc.value.code == "token_expired"


async def test_verify_rejects_wrong_audience(supabase_env):
    with pytest.raises(SupabaseAuthError) as exc:
        await supabase_auth.verify_supabase_jwt(_token(aud="anon"))
    assert exc.value.code == "invalid_token"


async def test_verify_rejects_wrong_issuer(supabase_env):
    with pytest.raises(SupabaseAuthError) as exc:
        await supabase_auth.verify_supabase_jwt(_token(iss="https://evil.example/auth/v1"))
    assert exc.value.code == "invalid_token"


async def test_verify_rejects_bad_signature(supabase_env):
    with pytest.raises(SupabaseAuthError) as exc:
        await supabase_auth.verify_supabase_jwt(
            _token(secret="a-totally-different-secret-also-at-least-32-bytes-long")
        )
    assert exc.value.code == "invalid_token"


async def test_verify_rejects_empty_token(supabase_env):
    with pytest.raises(SupabaseAuthError) as exc:
        await supabase_auth.verify_supabase_jwt("   ")
    assert exc.value.code == "missing_token"


async def test_verify_hs256_without_secret_is_rejected(monkeypatch):
    # Engine has SUPABASE_URL but no HS256 secret; an HS256 token must not be accepted.
    monkeypatch.setenv("SUPABASE_URL", _BASE)
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(SupabaseAuthError) as exc:
            await supabase_auth.verify_supabase_jwt(_token())
        assert exc.value.code == "hs256_not_configured"
    finally:
        get_settings.cache_clear()


async def test_verify_unconfigured_base_raises(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(SupabaseAuthError) as exc:
            await supabase_auth.verify_supabase_jwt(_token())
        assert exc.value.code == "not_configured"
    finally:
        get_settings.cache_clear()


def test_supabase_configured_toggles(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    get_settings.cache_clear()
    assert supabase_auth.supabase_configured() is False
    monkeypatch.setenv("SUPABASE_URL", _BASE)
    get_settings.cache_clear()
    assert supabase_auth.supabase_configured() is True
    get_settings.cache_clear()


# ── extract_github_identity ─────────────────────────────────────────────────────────────────────


def test_extract_requires_github_provider():
    with pytest.raises(SupabaseAuthError) as exc:
        extract_github_identity(
            {"app_metadata": {"provider": "email", "providers": ["email"]}, "user_metadata": {}}
        )
    assert exc.value.code == "not_github"


def test_extract_requires_numeric_id():
    with pytest.raises(SupabaseAuthError) as exc:
        extract_github_identity(
            {"app_metadata": {"provider": "github"}, "user_metadata": {"user_name": "x"}}
        )
    assert exc.value.code == "no_github_id"


def test_extract_requires_login():
    with pytest.raises(SupabaseAuthError) as exc:
        extract_github_identity(
            {"app_metadata": {"provider": "github"}, "user_metadata": {"provider_id": "5"}}
        )
    assert exc.value.code == "no_github_login"


def test_extract_falls_back_to_sub_for_id_and_handles_null_email():
    ident = extract_github_identity(
        {
            "app_metadata": {"providers": ["github"]},  # provider via the providers[] array
            "user_metadata": {"sub": "999", "user_name": "Foo"},
            "email": None,
        }
    )
    assert ident == {"github_user_id": 999, "github_login": "foo", "email": None}
