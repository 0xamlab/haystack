"""OAuth 2.0 Device Authorization Grant (RFC 8628) — CLI login for `telys login` (and future `<brand> login`).

Three endpoints on the control plane:
  * ``POST /oauth/device/code``    (public)        — mint a (device_code, user_code) pair + verification_uri.
  * ``POST /oauth/device/token``   (public, poll)  — exchange an APPROVED device_code for the Supabase JWT.
  * ``POST /oauth/device/approve`` (Supabase auth) — the accounts.thyn.ai/device page binds the signed-in
    user's Supabase access_token to the user_code.
  * ``GET  /oauth/device/grant``   (Supabase auth) — the /device page looks up a user_code to show what it is
    approving (client + scope) before the user confirms.

The CLI hits ``accounts.thyn.ai/oauth/device/{code,token}`` (a thin proxy to these); the browser hits
``accounts.thyn.ai/device`` which calls approve/grant here. The returned access_token IS a Supabase JWT, so the
CLI then reuses the existing control-plane interface verbatim (POST /v1/api-keys → POST /v1/device/register).

State lives in ``device_grants`` (short TTL, single-use); the plaintext token is cleared the instant it is
redeemed. See models/device_grant.py.
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_redis
from apps.api_server.models.device_grant import (
    STATUS_APPROVED,
    STATUS_DENIED,
    STATUS_PENDING,
    DeviceGrant,
)
from apps.api_server.services.quota_service import check_named_rate_limit
from apps.api_server.services.supabase_auth import SupabaseAuthError, verify_supabase_jwt
from apps.api_server.services.website_identity import bearer_token, error_body

router = APIRouter(tags=["oauth-device"])

DEVICE_CODE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"
_DEVICE_CODE_TTL = timedelta(minutes=10)
_DEFAULT_INTERVAL = 5
# Unambiguous alphabet: no vowels (avoids real words), no 0/O/1/I/L (avoids misreads).
_USER_CODE_ALPHABET = "BCDFGHJKMNPQRSTVWXYZ23456789"
_USER_CODE_LEN = 8  # rendered "XXXX-XXXX"

# client_id → app slug (drives the brand-aware verification_uri ?app=). Extend for `algenta-cli` etc.
_KNOWN_CLIENTS: dict[str, str] = {"telys-cli": "telys"}


# ── request bodies ────────────────────────────────────────────────────────────
class DeviceCodeRequest(BaseModel):
    client_id: str
    scope: str = ""


class DeviceTokenRequest(BaseModel):
    device_code: str
    grant_type: str
    client_id: str = ""


class ApproveRequest(BaseModel):
    user_code: str = Field(min_length=1)


# ── helpers ─────────────────────────────────────────────────────────────────--
def _oauth_error(status: int, error: str, description: str | None = None) -> JSONResponse:
    body: dict[str, str] = {"error": error}
    if description:
        body["error_description"] = description
    return JSONResponse(status_code=status, content=body)


def _new_user_code() -> str:
    raw = "".join(secrets.choice(_USER_CODE_ALPHABET) for _ in range(_USER_CODE_LEN))
    return f"{raw[:4]}-{raw[4:]}"


def _normalize_user_code(value: str) -> str:
    """Accept user input in any case / with or without the dash; store the canonical XXXX-XXXX form."""
    cleaned = "".join(c for c in (value or "").upper() if c in _USER_CODE_ALPHABET)
    if len(cleaned) != _USER_CODE_LEN:
        return (value or "").strip().upper()  # let the lookup miss + 404 for malformed input
    return f"{cleaned[:4]}-{cleaned[4:]}"


def _client_ip(request: Request) -> str:
    fwd = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    return fwd or (request.client.host if request.client else "unknown")


async def _rate_limit(key: str, redis: Any, *, prefix: str, per_minute: int) -> None:
    """Best-effort rate limit — never fail the flow if Redis is down (raises 429 only on a real breach)."""
    try:
        await check_named_rate_limit(
            key, redis, key_prefix=prefix, limit_per_minute=per_minute, error_code="slow_down"
        )
    except Exception as exc:  # noqa: BLE001
        from fastapi import HTTPException

        if isinstance(exc, HTTPException):
            raise
        # Redis unavailable / misconfigured → don't block logins on the limiter.
        return


async def _by_device_code(db: AsyncSession, device_code: str) -> DeviceGrant | None:
    if not device_code:
        return None
    res = await db.execute(select(DeviceGrant).where(DeviceGrant.device_code == device_code))
    return res.scalar_one_or_none()


async def _by_user_code(db: AsyncSession, user_code: str) -> DeviceGrant | None:
    if not user_code:
        return None
    res = await db.execute(select(DeviceGrant).where(DeviceGrant.user_code == user_code))
    return res.scalar_one_or_none()


# ── endpoints ─────────────────────────────────────────────────────────────────
@router.post("/oauth/device/code")
async def device_code(
    payload: DeviceCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> Any:
    app_slug = _KNOWN_CLIENTS.get(payload.client_id)
    if app_slug is None:
        return _oauth_error(400, "invalid_client", f"unknown client_id {payload.client_id!r}")
    await _rate_limit(_client_ip(request), redis, prefix="device_code_req", per_minute=30)

    now = datetime.now(UTC)
    # user_code must be unique among live grants; retry a few times on the (astronomically rare) collision.
    user_code = _new_user_code()
    for _ in range(5):
        if await _by_user_code(db, user_code) is None:
            break
        user_code = _new_user_code()

    grant = DeviceGrant(
        device_code=secrets.token_urlsafe(32),
        user_code=user_code,
        client_id=payload.client_id,
        scope=payload.scope or app_slug,
        status=STATUS_PENDING,
        interval_seconds=_DEFAULT_INTERVAL,
        expires_at=now + _DEVICE_CODE_TTL,
    )
    db.add(grant)
    await db.flush()

    from apps.api_server.config import get_settings

    accounts = get_settings().accounts_base_url.rstrip("/")
    verification_uri = f"{accounts}/device"
    return {
        "device_code": grant.device_code,
        "user_code": grant.user_code,
        "verification_uri": verification_uri,
        "verification_uri_complete": f"{verification_uri}?app={app_slug}&user_code={grant.user_code}",
        "expires_in": int(_DEVICE_CODE_TTL.total_seconds()),
        "interval": _DEFAULT_INTERVAL,
    }


@router.post("/oauth/device/token")
async def device_token(payload: DeviceTokenRequest, db: AsyncSession = Depends(get_db)) -> Any:
    if payload.grant_type != DEVICE_CODE_GRANT_TYPE:
        return _oauth_error(400, "unsupported_grant_type", payload.grant_type)

    grant = await _by_device_code(db, payload.device_code)
    now = datetime.now(UTC)
    if grant is None:
        return _oauth_error(400, "invalid_grant", "unknown device_code")

    expires_at = grant.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now:
        await db.delete(grant)
        return _oauth_error(400, "expired_token")

    # RFC 8628 slow_down: reject polls faster than the advertised interval.
    last = grant.last_polled_at
    if last is not None:
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        if (now - last).total_seconds() < grant.interval_seconds:
            grant.last_polled_at = now
            return _oauth_error(400, "slow_down")
    grant.last_polled_at = now

    if grant.status == STATUS_DENIED:
        await db.delete(grant)
        return _oauth_error(400, "access_denied")
    if grant.status != STATUS_APPROVED:
        return _oauth_error(400, "authorization_pending")

    token = grant.access_token
    scope = grant.scope
    await db.delete(grant)  # single-use: redeem once, then the plaintext token is gone
    if not token:
        return _oauth_error(400, "invalid_grant", "approved grant had no bound token")
    return {"access_token": token, "token_type": "Bearer", "scope": scope}


async def _authed_subject(authorization: str | None) -> dict[str, Any]:
    from fastapi import HTTPException

    token = bearer_token(authorization)  # raises 401 if absent
    try:
        claims = await verify_supabase_jwt(token)
    except SupabaseAuthError as exc:
        raise HTTPException(status_code=401, detail=error_body(exc.code, str(exc))) from exc
    return {"token": token, "claims": claims}


@router.get("/oauth/device/grant")
async def device_grant_lookup(
    user_code: str,
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> Any:
    from fastapi import HTTPException

    await _authed_subject(authorization)  # any signed-in user may inspect a code before approving
    grant = await _by_user_code(db, _normalize_user_code(user_code))
    now = datetime.now(UTC)
    if grant is None or (grant.expires_at.replace(tzinfo=UTC) if grant.expires_at.tzinfo is None else grant.expires_at) <= now:
        raise HTTPException(status_code=404, detail=error_body("invalid_user_code", "unknown or expired code"))
    return {"client_id": grant.client_id, "scope": grant.scope, "status": grant.status}


@router.post("/oauth/device/approve")
async def device_approve(
    payload: ApproveRequest,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> Any:
    from fastapi import HTTPException

    auth = await _authed_subject(authorization)
    claims = auth["claims"]
    subject = claims.get("sub")
    await _rate_limit(str(subject or _client_ip(request)), redis, prefix="device_approve", per_minute=20)

    grant = await _by_user_code(db, _normalize_user_code(payload.user_code))
    now = datetime.now(UTC)
    expires_at = grant.expires_at if grant else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if grant is None or expires_at <= now:
        raise HTTPException(status_code=404, detail=error_body("invalid_user_code", "unknown or expired code"))
    if grant.status != STATUS_PENDING:
        raise HTTPException(
            status_code=409, detail=error_body("already_resolved", f"code already {grant.status}")
        )

    grant.status = STATUS_APPROVED
    grant.access_token = auth["token"]  # the CLI redeems THIS Supabase JWT once, then it's cleared
    grant.subject = str(subject) if subject else None
    grant.email = claims.get("email")
    grant.approved_at = now
    return {"status": "approved", "client_id": grant.client_id, "scope": grant.scope}
