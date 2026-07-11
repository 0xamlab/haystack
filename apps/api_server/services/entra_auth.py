"""Microsoft Entra ID (Azure AD) access-token verification for the Decision API.

The Microsoft Cloud clients (M365 Copilot/Teams agent, Excel Add-in, Foundry agents,
Copilot Studio / Power Platform connectors) authenticate employees and service identities
with Entra ID and call the customer-hosted gateway with a bearer token. This module
verifies that token **offline** (JWKS via the egress guard) under the strict rules the
trust plan mandates:

  * audience   — the token must be minted FOR the Algenta Decision API
    (``ALGENTA_ENTRA_AUDIENCE``: the app-id URI or client id of the gateway's app
    registration). A Microsoft Graph token, an ARM (Azure management) token, or any
    other resource's token is **rejected** — never "forwarded and accepted".
  * issuer     — ``https://login.microsoftonline.com/{tenant}/v2.0`` (v2 tokens only).
  * tenant     — ``tid`` must be in the allowlist (default: the configured tenant).
  * client app — optional ``azp``/``appid`` allowlist (``ALGENTA_ENTRA_ALLOWED_CLIENT_APPS``).
  * signature  — RS256 via the tenant's JWKS (fetched through the egress guard, cached,
    one forced refresh on an unknown ``kid`` to ride key rotation).

What comes OUT is an :class:`EntraPrincipal` — the validated ``(tenant_id, oid)`` pair plus
scopes/roles. The workspace/org is **derived** from that principal by the resolver
(services/entra_org_resolver.py), never taken from a header or the request body.

Inert until ``ALGENTA_ENTRA_TENANT_ID`` + ``ALGENTA_ENTRA_AUDIENCE`` are configured.
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

__all__ = [
    "EntraAuthError",
    "EntraPrincipal",
    "entra_configured",
    "looks_like_entra_token",
    "verify_entra_token",
    "SERVICE_ERROR_CODES",
]

# Config/JWKS failures (503, "gateway misconfigured/unreachable") vs token failures (401).
SERVICE_ERROR_CODES = frozenset(
    {"not_configured", "jwks_unreachable", "jwks_unavailable", "jwks_invalid"}
)

_LOGIN_HOST = "login.microsoftonline.com"
# Exact issuer hosts we recognize (routing only — trust comes from the pinned-issuer verify).
_ENTRA_ISSUER_HOSTS = frozenset({_LOGIN_HOST, "sts.windows.net"})
_JWKS_TTL_S = 600
_CLOCK_SKEW_S = 30
# Well-known audiences that must NEVER be accepted as Decision-API tokens.
_FORBIDDEN_AUDIENCES = frozenset(
    {
        "https://graph.microsoft.com",
        "00000003-0000-0000-c000-000000000000",  # Microsoft Graph app id
        "https://management.azure.com",
        "https://management.core.windows.net",
    }
)

# tenant_id -> (fetched_at_monotonic, PyJWKSet)
_jwks_cache: dict[str, tuple[float, PyJWKSet]] = {}


class EntraAuthError(Exception):
    """An Entra token verification failure (mapped to 401/403/503 by the caller)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class EntraPrincipal:
    """The validated identity a verified Entra token proves."""

    tenant_id: str
    oid: str  # the stable object id of the user or service principal
    principal_type: str  # "user" | "app"
    client_app_id: str | None
    scopes: tuple[str, ...] = ()
    roles: tuple[str, ...] = ()
    preferred_username: str | None = None
    name: str | None = None

    @property
    def principal_ref(self) -> str:
        return f"entra:{self.tenant_id}:{self.oid}"


def entra_configured() -> bool:
    s = get_settings()
    return bool((getattr(s, "entra_tenant_id", None) or "").strip()) and bool(
        (getattr(s, "entra_audience", None) or "").strip()
    )


def looks_like_entra_token(token: str) -> bool:
    """Cheap pre-check: is this bearer a JWT whose UNVERIFIED issuer is an Entra issuer?

    Used only for routing (which verifier to try) — carries zero trust by itself.
    """

    token = (token or "").strip()
    if token.count(".") != 2:
        return False
    try:
        iss = str(jwt.decode(token, options={"verify_signature": False}).get("iss") or "")
    except jwt.PyJWTError:
        return False
    # Parse and compare the HOST exactly — never a substring match (a substring check would
    # route e.g. "https://evil.example/login.microsoftonline.com" here; harmless because the
    # real verify pins the issuer, but we keep the pre-check honest and CodeQL-clean).
    host = (urlsplit(iss).hostname or "").lower()
    return host in _ENTRA_ISSUER_HOSTS


def _allowed_tenants(settings: Any) -> frozenset[str]:
    raw = (getattr(settings, "entra_allowed_tenants", None) or "").strip()
    tenants = {t.strip().lower() for t in raw.split(",") if t.strip()}
    tenants.add((settings.entra_tenant_id or "").strip().lower())
    return frozenset(t for t in tenants if t)


def _allowed_client_apps(settings: Any) -> frozenset[str]:
    raw = (getattr(settings, "entra_allowed_client_apps", None) or "").strip()
    return frozenset(a.strip().lower() for a in raw.split(",") if a.strip())


def _accepted_audiences(settings: Any) -> list[str]:
    """Every audience string the Decision API accepts, from ``ALGENTA_ENTRA_AUDIENCE`` (comma-sep).

    Entra issues DIFFERENT ``aud`` forms for the two identity shapes this service is built for:
    a **delegated** (employee) token carries the App ID URI ``api://{client_id}``, while an
    **app-only** (service / managed-identity, e.g. a Foundry agent) client-credentials token carries
    the bare ``{client_id}`` GUID. Configuring only one would silently reject the other. So each
    configured value is auto-expanded across that pair — set ``ALGENTA_ENTRA_AUDIENCE="api://{id}"``
    (or the GUID) and BOTH shapes are accepted. Exact-match still holds; nothing else broadens."""
    raw = (getattr(settings, "entra_audience", None) or "").strip()
    out: list[str] = []
    for a in (v.strip() for v in raw.split(",")):
        if not a or a in out:
            continue
        out.append(a)
        if a.lower().startswith("api://"):
            bare = a[len("api://"):]
            if bare and bare not in out:
                out.append(bare)  # app-only client-credentials aud = the bare client id
        else:
            uri = f"api://{a}"
            if uri not in out:
                out.append(uri)  # delegated aud = the App ID URI form
    return out


async def _fetch_jwks(tenant_id: str, *, force: bool = False) -> PyJWKSet:
    if not force:
        cached = _jwks_cache.get(tenant_id)
        if cached is not None and (time.monotonic() - cached[0]) < _JWKS_TTL_S:
            return cached[1]
    url = f"https://{_LOGIN_HOST}/{tenant_id}/discovery/v2.0/keys"
    try:
        resp = await egress_guard.async_http_request(
            method="GET",
            url=url,
            surface="entra_jwks",
            egress_class="customer_connector",
            explicit_configured=True,
            headers={"Accept": "application/json"},
            client_kwargs={"timeout": 15.0},
        )
    except egress_guard.EgressPolicyDeniedError as exc:
        raise EntraAuthError(
            "jwks_unreachable", "The Entra JWKS endpoint is not reachable (egress policy)."
        ) from exc
    except httpx.HTTPError as exc:
        raise EntraAuthError(
            "jwks_unreachable", "The Entra JWKS endpoint is not reachable."
        ) from exc
    if resp.status_code >= 400:
        raise EntraAuthError("jwks_unavailable", f"Entra JWKS fetch failed ({resp.status_code}).")
    try:
        jwk_set = PyJWKSet.from_dict(resp.json())
    except Exception as exc:  # noqa: BLE001 — any malformed JWKS is a hard verification failure
        raise EntraAuthError("jwks_invalid", "Entra JWKS document was not parseable.") from exc
    _jwks_cache[tenant_id] = (time.monotonic(), jwk_set)
    return jwk_set


async def _signing_key(token: str, tenant_id: str) -> Any:
    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except jwt.PyJWTError as exc:
        raise EntraAuthError("malformed_token", "Token header was not parseable.") from exc
    if not kid:
        raise EntraAuthError("malformed_token", "Token header is missing 'kid'.")
    for forced in (False, True):
        jwk_set = await _fetch_jwks(tenant_id, force=forced)
        for key in jwk_set.keys:
            if key.key_id == kid:
                return key.key
    raise EntraAuthError("unknown_kid", "No signing key matches the token's kid.")


def _reject_forbidden_audience(token: str) -> None:
    """Fail fast (and with a precise error) when the token was minted for another resource."""

    try:
        aud = jwt.decode(token, options={"verify_signature": False}).get("aud")
    except jwt.PyJWTError:
        return  # the real decode below will produce the canonical error
    auds = {str(a).lower().rstrip("/") for a in (aud if isinstance(aud, list) else [aud]) if a}
    if auds & {f.lower().rstrip("/") for f in _FORBIDDEN_AUDIENCES}:
        raise EntraAuthError(
            "wrong_resource_token",
            "This token was minted for another Microsoft resource (e.g. Graph or ARM); "
            "request a token whose audience is the Algenta Decision API.",
        )


async def verify_entra_token(token: str) -> EntraPrincipal:
    """Verify an Entra v2 access token for the Decision API; return the validated principal.

    Raises :class:`EntraAuthError` on any failure. Fail-closed everywhere: unconfigured →
    error; wrong audience/issuer/tenant/client → error; v1 (sts.windows.net) tokens → error.
    """

    settings = get_settings()
    tenant = (getattr(settings, "entra_tenant_id", None) or "").strip()
    audiences = _accepted_audiences(settings)  # App ID URI + bare client-id (both aud shapes)
    if not tenant or not audiences:
        raise EntraAuthError("not_configured", "Entra identity is not configured on this gateway.")

    token = (token or "").strip()
    if not token:
        raise EntraAuthError("missing_token", "No bearer token supplied.")

    _reject_forbidden_audience(token)

    # Multi-tenant: the token's own tid determines which tenant JWKS signs it, but the tid
    # must be allowlisted BEFORE we fetch that tenant's keys (no key-fetch for strangers).
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError as exc:
        raise EntraAuthError("malformed_token", "Token was not parseable.") from exc
    tid = str(unverified.get("tid") or "").strip().lower()
    if not tid:
        raise EntraAuthError("missing_tenant", "Token carries no tenant id (tid).")
    if tid not in _allowed_tenants(settings):
        raise EntraAuthError("tenant_not_allowed", "The token's tenant is not allowed here.")

    issuer = f"https://{_LOGIN_HOST}/{tid}/v2.0"
    key = await _signing_key(token, tid)
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],  # Entra signs v2 access tokens with RS256; nothing else accepted
            audience=audiences,  # PyJWT accepts if aud matches ANY (URI or bare client id)
            issuer=issuer,
            options={"require": ["exp", "iss", "aud", "sub"]},
            leeway=_CLOCK_SKEW_S,
        )
    except jwt.ExpiredSignatureError as exc:
        raise EntraAuthError("token_expired", "The access token has expired.") from exc
    except jwt.InvalidAudienceError as exc:
        raise EntraAuthError(
            "wrong_audience", "The token's audience is not the Algenta Decision API."
        ) from exc
    except jwt.InvalidIssuerError as exc:
        # v1 tokens (iss=https://sts.windows.net/{tid}/) land here too — v2 only, by design.
        raise EntraAuthError(
            "wrong_issuer", "The token's issuer is not an Entra v2 issuer."
        ) from exc
    except jwt.PyJWTError as exc:
        raise EntraAuthError("invalid_token", "The access token could not be verified.") from exc

    oid = str(claims.get("oid") or "").strip()
    if not oid:
        raise EntraAuthError("missing_oid", "Token carries no principal object id (oid).")

    client_app = str(claims.get("azp") or claims.get("appid") or "").strip().lower() or None
    allowed_apps = _allowed_client_apps(settings)
    if allowed_apps and (client_app or "") not in allowed_apps:
        raise EntraAuthError("client_app_not_allowed", "The calling application is not allowed.")

    scopes = tuple(s for s in str(claims.get("scp") or "").split() if s)
    roles = tuple(str(r) for r in (claims.get("roles") or []) if r)
    idtyp = str(claims.get("idtyp") or "").strip().lower()

    # Reject ID tokens replayed as API bearers: a genuine Entra access token for a custom API
    # carries delegated scopes (scp), app-role assignments (roles), or the app-only marker
    # (idtyp=app). An ID token carries none of these — refuse it even if its aud happens to be
    # the app's client-id GUID.
    if not scopes and not roles and idtyp != "app":
        raise EntraAuthError(
            "not_api_access_token",
            "Token is not an API access token for the Decision API (no scope, role, or app id).",
        )

    # principal_type is derived ONLY from the trustworthy idtyp claim. Do NOT infer "app" from
    # "roles present but no scp": a delegated USER token under an app-role assignment (no
    # delegated scopes exposed) legitimately carries roles + no scp, and must stay "user".
    principal_type = "app" if idtyp == "app" else "user"

    return EntraPrincipal(
        tenant_id=tid,
        oid=oid,
        principal_type=principal_type,
        client_app_id=client_app,
        scopes=scopes,
        roles=roles,
        preferred_username=(
            str(claims.get("preferred_username")) if claims.get("preferred_username") else None
        ),
        name=(str(claims.get("name")) if claims.get("name") else None),
    )
