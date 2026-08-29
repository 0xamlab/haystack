"""Generic OIDC access-token verification for the Decision API.

Entra ID (services/entra_auth.py) covers Microsoft Cloud clients specifically — this module
covers everything else: Okta, Auth0, Keycloak, or any other standards-compliant OIDC provider a
self-hosted customer already runs. It verifies a bearer token **offline** (JWKS via the egress
guard) under the same strict shape entra_auth.py established:

  * audience  — the token must be minted FOR the Algenta Decision API
    (``ALGENTA_OIDC_AUDIENCE``). A token minted for any other resource is **rejected**.
  * issuer    — must exactly match ``ALGENTA_OIDC_ISSUER``. Unlike Entra (one fixed host,
    many tenants), a generic OIDC issuer URL already IS the tenant/realm identity — Keycloak's
    issuer is literally ``{server}/realms/{realm}`` — so there is no separate tenant allowlist
    to maintain; the configured issuer is the whole trust boundary.
  * client app — optional ``azp``/``client_id`` allowlist (``ALGENTA_OIDC_ALLOWED_CLIENT_APPS``).
  * signature — RS256 via ``ALGENTA_OIDC_JWKS_URL`` (fetched through the egress guard, cached,
    one forced refresh on an unknown ``kid`` to ride key rotation) — a direct, configured URL
    rather than a discovery document fetch, matching how Entra's JWKS location is also a fixed,
    configured shape rather than resolved at request time.

What comes OUT is an :class:`OidcPrincipal` — the validated ``(issuer, subject)`` pair plus
scopes/roles. The workspace/org is **derived** from that principal by the resolver
(services/oidc_org_resolver.py), never taken from a header or the request body.

Generic OIDC has no ``idtyp``-style claim distinguishing a user token from a service-principal
token the way Entra does, and no single standard claim for roles across providers (Keycloak uses
``realm_access.roles``; others vary or omit it). This module reads ``scope`` (OAuth2/OIDC
standard, space-separated) as the primary access-token signal, and falls back to Keycloac's own
``realm_access.roles`` shape when present — see :func:`_extract_roles`. ``principal_type`` is
``"app"`` when ``sub == azp`` (or ``sub == client_id`` — the Auth0/Okta client-credentials shape),
OR when ``preferred_username`` starts with ``service-account-`` (Keycloak's own client-credentials
shape: its dedicated service-account user's ``sub`` is its own UUID, never equal to the client id —
confirmed against a live Keycloak instance, not assumed); everything else is ``"user"``.

Inert until ``ALGENTA_OIDC_ISSUER`` + ``ALGENTA_OIDC_AUDIENCE`` + ``ALGENTA_OIDC_JWKS_URL`` are all
configured.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx
import jwt
import structlog
from jwt import PyJWKSet

from apps.api_server.config import get_settings
from apps.api_server.services import egress_guard

logger = structlog.get_logger(__name__)

SERVICE_ERROR_CODES = frozenset({"not_configured", "jwks_unreachable", "jwks_unavailable", "jwks_invalid"})

_JWKS_TTL_S = 600
_CLOCK_SKEW_S = 30
_FORCED_JWKS_REFETCH_COOLDOWN_S = 60

# Single-issuer deployment: one cached JWKS set, one forced-refetch cooldown timestamp — there is
# no per-tenant dimension the way entra_auth.py's dicts are keyed by tenant_id, because a generic
# OIDC gateway is configured for exactly one issuer at a time.
_jwks_cache: tuple[float, PyJWKSet] | None = None
_last_forced_jwks_refetch: float = 0.0


class OidcAuthError(Exception):
    """A generic-OIDC token verification failure (mapped to 401/403/503 by the caller)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class OidcPrincipal:
    """The validated identity a verified generic-OIDC token proves."""

    issuer: str
    subject: str
    principal_type: str  # "user" | "app"
    client_id: str | None
    scopes: tuple[str, ...] = ()
    roles: tuple[str, ...] = ()
    preferred_username: str | None = None
    name: str | None = None

    @property
    def principal_ref(self) -> str:
        return f"oidc:{self.issuer}:{self.subject}"


def oidc_configured() -> bool:
    s = get_settings()
    return bool(
        (getattr(s, "oidc_issuer", None) or "").strip()
        and (getattr(s, "oidc_audience", None) or "").strip()
        and (getattr(s, "oidc_jwks_url", None) or "").strip()
    )


def oidc_authorization_server_issuer() -> str | None:
    """The single issuer URL ``verify_oidc_token`` actually trusts, for RFC 9728 protected-resource
    metadata (``routers/oauth_protected_resource.py``). ``None`` when generic OIDC is not
    configured; discovery must never advertise an authorization server this gateway would not
    actually trust."""
    if not oidc_configured():
        return None
    settings = get_settings()
    return (getattr(settings, "oidc_issuer", None) or "").strip() or None


def looks_like_oidc_token(token: str) -> bool:
    """Cheap, unverified pre-routing check — carries zero trust on its own. Compares the token's
    unverified ``iss`` against the exact configured issuer, not a substring/host match: a
    generic OIDC issuer string (e.g. ``https://idp.example.com/realms/acme``) has no fixed host
    set to check against the way Entra's does, so exact-string comparison is the only check that
    can't be spoofed by a similarly-hosted-but-different-path issuer."""
    token = (token or "").strip()
    if token.count(".") != 2:
        return False
    settings = get_settings()
    configured_issuer = (getattr(settings, "oidc_issuer", None) or "").strip()
    if not configured_issuer:
        return False
    try:
        iss = str(jwt.decode(token, options={"verify_signature": False}).get("iss") or "").strip()
    except jwt.PyJWTError:
        return False
    return bool(iss) and iss.rstrip("/") == configured_issuer.rstrip("/")


def _allowed_client_apps(settings: Any) -> frozenset[str]:
    raw = (getattr(settings, "oidc_allowed_client_apps", None) or "").strip()
    return frozenset(a.strip().lower() for a in raw.split(",") if a.strip())


def _accepted_audiences(settings: Any) -> list[str]:
    raw = (getattr(settings, "oidc_audience", None) or "").strip()
    return [a.strip() for a in raw.split(",") if a.strip()]


async def _fetch_jwks(*, force: bool = False) -> PyJWKSet:
    global _jwks_cache
    if not force and _jwks_cache is not None and (time.monotonic() - _jwks_cache[0]) < _JWKS_TTL_S:
        return _jwks_cache[1]
    settings = get_settings()
    url = (getattr(settings, "oidc_jwks_url", None) or "").strip()
    if not url:
        raise OidcAuthError("not_configured", "OIDC identity is not configured on this gateway.")
    try:
        resp = await egress_guard.async_http_request(
            method="GET",
            url=url,
            surface="oidc_jwks",
            egress_class="customer_connector",
            explicit_configured=True,
            headers={"Accept": "application/json"},
            client_kwargs={"timeout": 15.0},
        )
    except egress_guard.EgressPolicyDeniedError as exc:
        raise OidcAuthError("jwks_unreachable", "The OIDC JWKS endpoint is not reachable (egress policy).") from exc
    except httpx.HTTPError as exc:
        raise OidcAuthError("jwks_unreachable", "The OIDC JWKS endpoint is not reachable.") from exc
    if resp.status_code >= 400:
        raise OidcAuthError("jwks_unavailable", f"OIDC JWKS fetch failed ({resp.status_code}).")
    try:
        jwk_set = PyJWKSet.from_dict(resp.json())
    except Exception as exc:  # noqa: BLE001
        raise OidcAuthError("jwks_invalid", "OIDC JWKS document was not parseable.") from exc
    _jwks_cache = (time.monotonic(), jwk_set)
    return jwk_set


async def _signing_key(token: str) -> Any:
    global _last_forced_jwks_refetch
    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except jwt.PyJWTError as exc:
        raise OidcAuthError("malformed_token", "Token header was not parseable.") from exc
    if not kid:
        raise OidcAuthError("malformed_token", "Token header is missing 'kid'.")
    jwk_set = await _fetch_jwks(force=False)
    for key in jwk_set.keys:
        if key.key_id == kid:
            return key.key
    now = time.monotonic()
    if now - _last_forced_jwks_refetch >= _FORCED_JWKS_REFETCH_COOLDOWN_S:
        _last_forced_jwks_refetch = now
        jwk_set = await _fetch_jwks(force=True)
        for key in jwk_set.keys:
            if key.key_id == kid:
                return key.key
    raise OidcAuthError("unknown_kid", "No signing key matches the token's kid.")


def _extract_roles(claims: dict[str, Any]) -> tuple[str, ...]:
    """Best-effort roles extraction across generic OIDC providers. There is no cross-provider
    standard claim for roles (unlike ``scope``, which OAuth2/OIDC both define), so this checks,
    in order: a plain top-level ``roles`` array (several providers' custom-claim convention), then
    Keycloak's own ``realm_access.roles`` shape (the provider this module is verified against
    end-to-end). Absence of either is not an error — plenty of valid access tokens carry no role
    claim at all and are authorized purely by scope."""
    top_level = claims.get("roles")
    if isinstance(top_level, list) and top_level:
        return tuple(str(r) for r in top_level if r)
    realm_access = claims.get("realm_access")
    if isinstance(realm_access, dict):
        roles = realm_access.get("roles")
        if isinstance(roles, list):
            return tuple(str(r) for r in roles if r)
    return ()


async def verify_oidc_token(token: str) -> OidcPrincipal:
    settings = get_settings()
    issuer = (getattr(settings, "oidc_issuer", None) or "").strip()
    audiences = _accepted_audiences(settings)
    jwks_url = (getattr(settings, "oidc_jwks_url", None) or "").strip()
    if not issuer or not audiences or not jwks_url:
        raise OidcAuthError("not_configured", "OIDC identity is not configured on this gateway.")

    token = (token or "").strip()
    if not token:
        raise OidcAuthError("missing_token", "No bearer token supplied.")

    key = await _signing_key(token)
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=audiences,
            issuer=issuer,
            options={"require": ["exp", "iss", "aud", "sub"]},
            leeway=_CLOCK_SKEW_S,
        )
    except jwt.ExpiredSignatureError as exc:
        raise OidcAuthError("token_expired", "The access token has expired.") from exc
    except jwt.InvalidAudienceError as exc:
        raise OidcAuthError(
            "wrong_audience", "The access token was not minted for this gateway's configured audience."
        ) from exc
    except jwt.InvalidIssuerError as exc:
        raise OidcAuthError("wrong_issuer", "The access token's issuer does not match the configured issuer.") from exc
    except jwt.PyJWTError as exc:
        raise OidcAuthError("invalid_token", "The access token could not be verified.") from exc

    subject = str(claims.get("sub") or "").strip()
    if not subject:
        raise OidcAuthError("missing_subject", "Token carries no subject (sub).")

    client_id = str(claims.get("azp") or claims.get("client_id") or "").strip() or None
    allowed_apps = _allowed_client_apps(settings)
    if allowed_apps and (client_id or "").lower() not in allowed_apps:
        raise OidcAuthError("client_app_not_allowed", "The calling application is not allowed.")

    scopes = tuple(s for s in str(claims.get("scope") or "").split() if s)
    roles = _extract_roles(claims)

    if claims.get("nonce"):
        raise OidcAuthError(
            "not_api_access_token", "This looks like an ID token (carries a nonce), not an API access token."
        )
    if not scopes and not roles and (client_id is None or subject != client_id):
        raise OidcAuthError(
            "not_api_access_token", "Token carries no scope, no role, and is not a client-credentials token."
        )

    preferred_username = str(claims.get("preferred_username") or "")
    principal_type = "user"
    if client_id is not None and subject == client_id:
        # Auth0/Okta-style client-credentials shape: the subject IS the client.
        principal_type = "app"
    elif preferred_username.startswith("service-account-"):
        # Keycloak's client-credentials grant mints a dedicated service-account USER whose sub is
        # its own UUID (never equal to the client id) — but that user is always, unconditionally,
        # named "service-account-<client-id>". Verified against a live Keycloak instance: a real
        # client-credentials token's `sub` did NOT equal `azp`/`client_id`, which the sub==client_id
        # check alone misses. This is Keycloak's stable, documented convention, not a heuristic
        # guess, so it can't misclassify a genuine end-user token from Keycloak or any other
        # provider (a human's preferred_username won't collide with this exact prefix).
        principal_type = "app"

    return OidcPrincipal(
        issuer=issuer,
        subject=subject,
        principal_type=principal_type,
        client_id=client_id,
        scopes=scopes,
        roles=roles,
        preferred_username=preferred_username or None,
        name=(str(claims.get("name")) if claims.get("name") else None),
    )
