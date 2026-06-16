"""Supabase Auth JWT verification for the codna website BYOK bridge.

The codna marketing site signs users in with Supabase (GitHub OAuth) and forwards the Supabase
``access_token`` (a JWT) to the top-level ``/byok`` endpoint. This module verifies that JWT
**offline** and extracts the caller's GitHub identity (numeric id + login) so the resolver can map
them to their engine org.

What this proves and what it does NOT:
  - PROVES identity — the verified ``user_metadata.provider_id`` is the caller's GitHub numeric id.
  - Does NOT yield a GitHub credential — the GitHub OAuth ``provider_token`` is a separate session
    field, never embedded in the JWT (and not persisted by Supabase). So we can verify *who* the
    user is, but not act as them on GitHub. (Org-membership checks therefore use the App's own
    installation token, not the user's — see ``github_app_auth.installation_membership_role``.)

Verification (config-driven, no hardcoded project ref):
  - issuer   = ``{SUPABASE_URL}/auth/v1``
  - audience = ``SUPABASE_JWT_AUD`` (default ``"authenticated"``)
  - asymmetric (ES256/RS256/EdDSA) via the project JWKS, fetched through the egress guard
    (self-hosted/air-gapped fail-closed + SSRF posture) and cached in-process; OR legacy HS256 via
    ``SUPABASE_JWT_SECRET`` (we branch on the token-header ``alg`` — never mix HS256 with the
    asymmetric algs in one ``algorithms=[...]`` list, which would invite an alg-confusion attack).

Inert until ``SUPABASE_URL`` is configured.
"""
from __future__ import annotations

import time
from typing import Any

import httpx
import jwt
import structlog
from jwt import PyJWKSet

from apps.api_server.config import get_settings
from apps.api_server.services import egress_guard

logger = structlog.get_logger(__name__)

# JWKS-fetch / configuration failure codes (vs token-validity failures). The router maps these to a
# 503 (service/config issue) rather than a 401 (bad token), so a misconfigured engine reads as
# "temporarily unavailable", not "your session is invalid".
SERVICE_ERROR_CODES = frozenset(
    {"not_configured", "jwks_unreachable", "jwks_unavailable", "jwks_invalid"}
)

_hs256_warned = False

# Asymmetric algs we accept from the JWKS. HS256 is handled on a SEPARATE branch (symmetric secret),
# never alongside these — mixing them is the classic JWT alg-confusion footgun.
_ASYMMETRIC_ALGS = ["RS256", "ES256", "EdDSA"]
_JWKS_PATH = "/auth/v1/.well-known/jwks.json"
_JWKS_TTL_S = 600  # JWKS is edge-cached ~10m; mirror that, with a forced refresh on an unknown kid.
_CLOCK_SKEW_S = 30

# In-process JWKS cache: base_url -> (fetched_at_monotonic, PyJWKSet). Dict writes are atomic under
# the GIL and a stale read merely triggers a re-fetch, so no lock is needed.
_jwks_cache: dict[str, tuple[float, PyJWKSet]] = {}


class SupabaseAuthError(Exception):
    """A Supabase-JWT verification/identity failure (mapped to 401 by the router)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def supabase_configured() -> bool:
    """True when SUPABASE_URL is set — the /byok surface is inert otherwise."""
    return bool((get_settings().supabase_url or "").strip())


def _base_url() -> str:
    base = (get_settings().supabase_url or "").strip().rstrip("/")
    if not base:
        raise SupabaseAuthError(
            "not_configured", "Supabase identity is not configured (SUPABASE_URL unset)."
        )
    return base


def _issuer(base: str) -> str:
    return f"{base}/auth/v1"


async def _fetch_jwks(base: str, *, force: bool = False) -> PyJWKSet:
    if not force:
        cached = _jwks_cache.get(base)
        if cached is not None and (time.monotonic() - cached[0]) < _JWKS_TTL_S:
            return cached[1]
    try:
        resp = await egress_guard.async_http_request(
            method="GET",
            url=f"{base}{_JWKS_PATH}",
            surface="supabase_jwks",
            egress_class="customer_connector",
            explicit_configured=True,
            headers={"Accept": "application/json"},
            client_kwargs={"timeout": 15.0},
        )
    except egress_guard.EgressPolicyDeniedError as exc:
        # Supabase host blocked by the egress policy. build_privacy_policy auto-allows the
        # SUPABASE_URL host, so this is a genuine misconfig — surface a clean error, not a 500.
        raise SupabaseAuthError(
            "jwks_unreachable", "The Supabase JWKS endpoint is not reachable (egress policy)."
        ) from exc
    except httpx.HTTPError as exc:
        raise SupabaseAuthError(
            "jwks_unreachable", "The Supabase JWKS endpoint is not reachable."
        ) from exc
    if resp.status_code >= 400:
        raise SupabaseAuthError("jwks_unavailable", f"JWKS fetch failed ({resp.status_code}).")
    try:
        jwk_set = PyJWKSet.from_dict(resp.json())
    except Exception as exc:  # noqa: BLE001 — any malformed JWKS is a hard verification failure
        raise SupabaseAuthError("jwks_invalid", "JWKS document was not parseable.") from exc
    _jwks_cache[base] = (time.monotonic(), jwk_set)
    return jwk_set


async def _signing_key(token: str, base: str) -> Any:
    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except jwt.PyJWTError as exc:
        raise SupabaseAuthError("malformed_token", "Token header was not parseable.") from exc
    if not kid:
        raise SupabaseAuthError("malformed_token", "Token header is missing 'kid'.")
    for forced in (False, True):  # cache hit; then one forced refresh to ride a key rotation
        jwk_set = await _fetch_jwks(base, force=forced)
        for key in jwk_set.keys:
            if key.key_id == kid:
                return key.key
    raise SupabaseAuthError("unknown_kid", "No signing key matches the token's kid.")


async def verify_supabase_jwt(token: str) -> dict[str, Any]:
    """Verify a Supabase access_token and return its claims, or raise :class:`SupabaseAuthError`."""
    settings = get_settings()
    base = _base_url()
    issuer = _issuer(base)
    audience = settings.supabase_jwt_aud or "authenticated"
    token = (token or "").strip()
    if not token:
        raise SupabaseAuthError("missing_token", "No bearer token supplied.")
    try:
        alg = (jwt.get_unverified_header(token).get("alg") or "").upper()
    except jwt.PyJWTError as exc:
        raise SupabaseAuthError("malformed_token", "Token header was not parseable.") from exc

    decode_kwargs: dict[str, Any] = {
        "audience": audience,
        "issuer": issuer,
        "options": {"require": ["exp", "iss", "aud"]},
        "leeway": _CLOCK_SKEW_S,
    }
    try:
        if alg == "HS256":
            secret = (settings.supabase_jwt_secret or "").strip()
            if not secret:
                raise SupabaseAuthError(
                    "hs256_not_configured",
                    "Token is HS256-signed but SUPABASE_JWT_SECRET is not set.",
                )
            # HS256 is the legacy symmetric path: the same secret verifies AND mints, so a leaked
            # SUPABASE_JWT_SECRET lets an attacker forge any identity. Modern Supabase projects use
            # asymmetric (ES256/RS256) JWKS — prefer those. Warn once so an HS256 deployment is
            # visible in the logs and can be migrated off.
            global _hs256_warned  # noqa: PLW0603 — module-level one-shot warning latch
            if not _hs256_warned:
                _hs256_warned = True
                logger.warning(
                    "supabase_hs256_fallback_in_use",
                    detail="verifying Supabase JWTs with the legacy HS256 shared secret; "
                    "migrate the project to asymmetric signing keys (JWKS) and unset "
                    "SUPABASE_JWT_SECRET",
                )
            claims = jwt.decode(token, secret, algorithms=["HS256"], **decode_kwargs)
        elif alg in _ASYMMETRIC_ALGS:
            key = await _signing_key(token, base)
            claims = jwt.decode(token, key, algorithms=_ASYMMETRIC_ALGS, **decode_kwargs)
        else:
            raise SupabaseAuthError("unsupported_alg", f"Unsupported token algorithm '{alg}'.")
    except SupabaseAuthError:
        raise
    except jwt.ExpiredSignatureError as exc:
        raise SupabaseAuthError("token_expired", "The session token has expired.") from exc
    except jwt.PyJWTError as exc:
        raise SupabaseAuthError(
            "invalid_token", "The session token could not be verified."
        ) from exc
    return claims


def extract_github_identity(claims: dict[str, Any]) -> dict[str, Any]:
    """Pull the GitHub identity out of verified Supabase claims.

    Returns ``{"github_user_id": int, "github_login": str, "email": str | None}``. Raises
    :class:`SupabaseAuthError` if the account is not a GitHub identity or carries no numeric id.

    The numeric GitHub user id lives in ``user_metadata.provider_id`` (also ``user_metadata.sub``)
    for a GitHub-OAuth user; both are strings, so we coerce defensively. ``user_metadata.user_name``
    is the GitHub login. (The top-level ``sub`` is the Supabase UUID — NOT the GitHub id.)"""
    app_meta = claims.get("app_metadata") or {}
    providers = {
        str(p).lower() for p in app_meta.get("providers", []) if isinstance(p, str | bytes)
    }
    primary = str(app_meta.get("provider") or "").lower()
    if "github" not in providers and primary != "github":
        raise SupabaseAuthError("not_github", "This account is not linked to GitHub.")

    user_meta = claims.get("user_metadata") or {}
    raw_id = user_meta.get("provider_id")
    if raw_id is None:
        raw_id = user_meta.get("sub")
    try:
        github_user_id = int(str(raw_id).strip())
    except (TypeError, ValueError) as exc:
        raise SupabaseAuthError("no_github_id", "The token carries no numeric GitHub id.") from exc

    login = str(
        user_meta.get("user_name") or user_meta.get("preferred_username") or ""
    ).strip().lower()
    if not login:
        raise SupabaseAuthError("no_github_login", "The token carries no GitHub login.")

    email = claims.get("email") or user_meta.get("email")
    return {
        "github_user_id": github_user_id,
        "github_login": login,
        "email": str(email) if email else None,
    }
