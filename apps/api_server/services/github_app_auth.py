"""GitHub App auth — mint short-lived per-installation access tokens.

App JWT (RS256, signed with the App private key) -> installation access token via the
GitHub API, routed through the egress guard so the self-hosted / air-gapped fail-closed
+ SSRF policy holds (same posture as ``_create_pull_request``). Tokens are cached ~55m
in Redis and persisted encrypted on the installation row as a cold-cache backstop.

The whole surface is inert until ``GITHUB_APP_*`` is configured.
"""
from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from apps.api_server.config import get_settings
from apps.api_server.services import egress_guard
from apps.api_server.services.config_crypto import decrypt_config_json, encrypt_config_json

_GITHUB_API = "https://api.github.com"
_GITHUB_OAUTH_TOKEN = "https://github.com/login/oauth/access_token"
_REFRESH_SAFETY_S = 300  # refresh 5 min before GitHub's ~1h expiry
_REDIS_PREFIX = "github_app:inst_token:"


class GithubAppNotConfiguredError(RuntimeError):
    """Raised when GITHUB_APP_ID / GITHUB_APP_PRIVATE_KEY are not set."""


def app_configured() -> bool:
    s = get_settings()
    return bool(s.github_app_id and s.github_app_private_key)


def _app_jwt() -> str:
    s = get_settings()
    if not s.github_app_id or not s.github_app_private_key:
        raise GithubAppNotConfiguredError("GITHUB_APP_ID / GITHUB_APP_PRIVATE_KEY not set.")
    pem = s.github_app_private_key.replace("\\n", "\n")  # allow single-line env var
    now = int(time.time())
    # GitHub requires exp <= 10 minutes; back-date iat 60s for clock skew.
    return jwt.encode({"iat": now - 60, "exp": now + 540, "iss": str(s.github_app_id)},
                      pem, algorithm="RS256")


async def _mint_installation_token(installation_id: int) -> tuple[str, datetime]:
    resp = await egress_guard.async_http_request(
        method="POST",
        url=f"{_GITHUB_API}/app/installations/{installation_id}/access_tokens",
        surface="github_app_token",
        egress_class="customer_connector",
        explicit_configured=True,
        headers={
            "Authorization": f"Bearer {_app_jwt()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        client_kwargs={"timeout": 30.0},
    )
    if resp.status_code >= 400:
        raise RuntimeError(
            f"github installation-token mint failed ({resp.status_code}): {resp.text[:200]}"
        )
    data = resp.json()
    expires_at = datetime.fromisoformat(str(data["expires_at"]).replace("Z", "+00:00"))
    return data["token"], expires_at


async def _gh_get(url: str, token: str, audit: Any) -> Any | None:
    """Egress-guarded GET with a Bearer token; None on any >=400."""
    resp = await egress_guard.async_http_request(
        method="GET",
        url=url,
        surface="github_app_oauth",
        egress_class="customer_connector",
        explicit_configured=True,
        audit_context=audit,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        client_kwargs={"timeout": 30.0},
    )
    if resp.status_code >= 400:
        return None
    return resp.json() or {}


async def verify_user_administers_installation(
    installation_id: int,
    code: str,
    *,
    org_id: uuid.UUID | str,
) -> dict[str, Any] | None:
    """Bind-time ownership check: confirm the GitHub user who completed the install is an
    ADMIN of the account that owns ``installation_id`` — not merely someone with access.

    On success returns the App-JWT-resolved installing account
    ``{"id": int, "login": str(lower), "type": "user"|"organization"}`` (the trusted source
    for install-first org provisioning); on ANY failure returns ``None`` (still falsy, so the
    one caller's truthiness check is preserved).

    WITHOUT this, the callback would trust an attacker-supplied ``installation_id`` query
    param and let them bind a victim's installation to their own org. A bare
    ``/user/installations`` membership check is NOT enough: that endpoint returns every
    installation the user can *access* (incl. org installs where they are only a repo
    collaborator), so we instead resolve the installation's owning account (App JWT) and
    require the user to be the account owner (user installs) or an org *admin* (org installs).

    Requires the App's OAuth client credentials + "Request user authorization during
    installation" enabled. All egress is guarded (self-hosted/air-gapped fail-closed)."""
    s = get_settings()
    if not (s.github_app_client_id and s.github_app_client_secret and code):
        return None
    audit = egress_guard.EgressAuditContext(
        org_id=org_id if isinstance(org_id, uuid.UUID) else None
    )
    # 1) exchange the install-flow OAuth code for a user token
    token_resp = await egress_guard.async_http_request(
        method="POST",
        url=_GITHUB_OAUTH_TOKEN,
        surface="github_app_oauth",
        egress_class="customer_connector",
        explicit_configured=True,
        audit_context=audit,
        headers={"Accept": "application/json"},
        json={
            "client_id": s.github_app_client_id,
            "client_secret": s.github_app_client_secret,
            "code": code,
        },
        client_kwargs={"timeout": 30.0},
    )
    if token_resp.status_code >= 400:
        return None
    user_token = str((token_resp.json() or {}).get("access_token") or "").strip()
    if not user_token:
        return None
    # 2) who is the user?
    user = await _gh_get(f"{_GITHUB_API}/user", user_token, audit)
    user_login = str((user or {}).get("login") or "").strip().lower()
    if not user_login:
        return None
    # 3) which account owns this installation? (resolved via the App JWT, not the user)
    inst = await _gh_get_app(f"{_GITHUB_API}/app/installations/{installation_id}", audit)
    account = (inst or {}).get("account") or {}
    acct_id = account.get("id")
    acct_login = str(account.get("login") or "").strip().lower()
    acct_type = str(account.get("type") or "").strip().lower()
    if not acct_login or acct_id is None:
        return None
    resolved = {"id": int(acct_id), "login": acct_login, "type": acct_type}
    # 4) require ADMIN of that account
    if acct_type == "user":
        return resolved if user_login == acct_login else None
    if acct_type == "organization":
        membership = await _gh_get(
            f"{_GITHUB_API}/user/memberships/orgs/{acct_login}", user_token, audit
        )
        return (
            resolved
            if (
                str((membership or {}).get("state")) == "active"
                and str((membership or {}).get("role")) == "admin"
            )
            else None
        )
    return None


async def resolve_installation_account(
    installation_id: int,
    *,
    org_id: uuid.UUID | str | None = None,
) -> dict[str, Any] | None:
    """Resolve the account that owns ``installation_id`` via the App JWT (no OAuth user code).

    The trusted account source for the WEBHOOK install-first path, where there is no OAuth
    code to verify a human admin — GitHub already authenticated the delivery via the HMAC
    signature, and the App JWT (not attacker-supplied payload) names the installing account.
    Returns ``{"id": int, "login": str(lower), "type": "user"|"organization"}`` or ``None``.
    All egress is guarded (self-hosted/air-gapped fail-closed), same posture as the verify path."""
    audit = egress_guard.EgressAuditContext(
        org_id=org_id if isinstance(org_id, uuid.UUID) else None
    )
    inst = await _gh_get_app(f"{_GITHUB_API}/app/installations/{installation_id}", audit)
    account = (inst or {}).get("account") or {}
    acct_id = account.get("id")
    acct_login = str(account.get("login") or "").strip().lower()
    acct_type = str(account.get("type") or "").strip().lower()
    if acct_id is None or not acct_login or not acct_type:
        return None
    return {"id": int(acct_id), "login": acct_login, "type": acct_type}


async def _gh_get_app(url: str, audit: Any) -> Any | None:
    """Egress-guarded GET authenticated with the App JWT; None on any >=400."""
    resp = await egress_guard.async_http_request(
        method="GET",
        url=url,
        surface="github_app_oauth",
        egress_class="customer_connector",
        explicit_configured=True,
        audit_context=audit,
        headers={
            "Authorization": f"Bearer {_app_jwt()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        client_kwargs={"timeout": 30.0},
    )
    if resp.status_code >= 400:
        return None
    return resp.json() or {}


async def installation_membership_role(
    installation_id: int,
    org_login: str,
    username: str,
    *,
    org_id: uuid.UUID | str,
    redis: Any | None = None,
    installation_row: Any | None = None,
) -> dict[str, Any] | None:
    """Check a user's org membership using the App's INSTALLATION token (not a user token).

    For the website BYOK bridge we know *who* the caller is (verified Supabase JWT → GitHub login)
    but hold no GitHub credential for them. So instead of the user-token ``/user/memberships`` path
    (see :func:`verify_user_administers_installation`), we mint the App's installation token for the
    org's installation and ask GitHub directly: ``GET /orgs/{org}/memberships/{username}``.

    Returns the membership dict ``{"state": "active"|"pending", "role": "admin"|"member"|...}`` or
    ``None`` when the user is not a member (404) / the call failed (>=400). The caller decides what
    counts (BYOK requires ``state == "active"`` and ``role == "admin"``).

    Requires the App's "Organization → Members: read" permission on the installed org. The
    installation token sees PRIVATE membership of that org, so private members resolve correctly.
    All egress is guarded (self-hosted/air-gapped fail-closed). Raises
    :class:`GithubAppNotConfiguredError` if the App is unconfigured and propagates
    ``EgressPolicyDeniedError`` if egress is denied — both caller-level (not per-org) failures."""
    org_login = (org_login or "").strip().lower()
    username = (username or "").strip().lower()
    if not org_login or not username:
        return None
    audit = egress_guard.EgressAuditContext(
        org_id=org_id if isinstance(org_id, uuid.UUID) else None
    )
    token = await get_installation_token(
        installation_id, org_id=org_id, redis=redis, installation_row=installation_row
    )
    return await _gh_get(f"{_GITHUB_API}/orgs/{org_login}/memberships/{username}", token, audit)


async def get_installation_token(
    installation_id: int,
    *,
    org_id: uuid.UUID | str,
    redis: Any | None = None,
    installation_row: Any | None = None,
) -> str:
    """Return a valid installation access token, minting + caching if needed.

    If ``installation_row`` is given, a freshly-minted token is persisted encrypted on
    it (caller commits). Redis caching is best-effort.
    """
    key = f"{_REDIS_PREFIX}{installation_id}"
    if redis is not None:
        try:
            cached = await redis.get(key)
            if cached:
                return cached.decode() if isinstance(cached, bytes) else cached
        except Exception:  # noqa: BLE001 — cache is best-effort
            pass
    # cold backstop: a still-valid encrypted token on the row. Require the SAME pre-expiry
    # safety margin as the Redis path (line below) so a near-expiry token isn't handed to the
    # multi-minute fix pipeline only to 401 mid-clone/push.
    row = installation_row
    if row is not None and row.encrypted_access_token and row.token_expires_at:
        if row.token_expires_at > datetime.now(UTC) + timedelta(seconds=_REFRESH_SAFETY_S):
            tok = decrypt_config_json(row.encrypted_access_token, org_id=org_id)
            if tok:
                return tok
    token, expires_at = await _mint_installation_token(installation_id)
    if redis is not None:
        ttl = max(60, int((expires_at - datetime.now(UTC)).total_seconds()) - _REFRESH_SAFETY_S)
        try:
            await redis.set(key, token, ex=ttl)
        except Exception:  # noqa: BLE001
            pass
    if row is not None:
        row.encrypted_access_token = encrypt_config_json(token, org_id=org_id)
        row.token_expires_at = expires_at
    return token
