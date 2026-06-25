"""/license + /.well-known — control-plane license surfaces.

- GET /.well-known/jwks.json (B1) — the license signer's PUBLIC key(s), so a runtime can
  verify device licenses (and the signed CRL) by ``kid``. Unauthenticated.
- POST /v1/license/challenge + /v1/license/renew (C1) — renewal proof-of-possession: the
  server issues a single-use nonce; the runtime signs it with the device's Ed25519 private
  key; the server verifies the presented public key's thumbprint matches the bound one AND
  the signature, then re-issues a fresh license. The private key never leaves the device.
- GET /v1/license/revocations (D1, later) — signed CRL.
"""

from __future__ import annotations

import base64
import secrets
import time
from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.models.device import (
    DEVICE_ID_MAX_LENGTH,
    DeviceRegistration,
    DeviceStatus,
)
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.device_service import (
    _api_key_effective_device_limit,
    _issue_license_jwt,
    _load_api_key_with_org,
    _plan_name,
    build_revocation_payload,
    effective_node_count,
    node_admission_block_count,
)
from apps.api_server.services.license_jwk import get_active_license_jwks
from apps.api_server.services.license_signer import get_license_signer
from apps.api_server.services.quota_service import check_named_rate_limit
from apps.runtime.device_keypair import thumbprint_for_public_pem, verify_signature

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["license"])


# ── JWKS (B1) ──────────────────────────────────────────────────────────────────


@router.get(
    "/.well-known/jwks.json",
    include_in_schema=False,
    summary="License signer public keys (JWKS)",
)
async def jwks() -> dict[str, list[dict[str, str]]]:
    """Public JWKS for the active license signer (empty under dev_hmac/HS256)."""
    return get_active_license_jwks()


@router.get(
    "/v1/license/revocations",
    include_in_schema=False,
    summary="Signed device-license revocation list (CRL)",
)
async def revocations(db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, str]:
    """Signed CRL of revoked activation_ids.

    Unauthenticated + self-authenticating: a JWT signed by the license signer (same kid/secret
    as device licenses), so a runtime verifies it with the JWKS/secret it already trusts. The
    runtime enforces it fail-open-on-uncertainty (P3b-D2); the authoritative flip is P5.
    """
    payload = await build_revocation_payload(db)
    return {"crl": get_license_signer().sign(payload)}


# ── Renewal proof-of-possession (C1) ───────────────────────────────────────────

_NONCE_TTL_SECONDS = 120
_MAX_LOCAL_NONCES = 10_000  # hard cap so challenge-spam can't grow the dict unbounded
# In-memory single-use nonce store (used when Redis is absent — single-node / tests).
# key -> (nonce, monotonic_expiry). Best-effort single-use across replicas until the shared
# coordination store lands. Monotonic expiry so a wall-clock change can't resurrect a nonce.
_local_nonces: dict[str, tuple[bytes, float]] = {}

# Atomic GET+DEL for redis clients without a native getdel (keeps single-use race-free).
_GETDEL_LUA = "local v = redis.call('GET', KEYS[1]); if v then redis.call('DEL', KEYS[1]) end; return v"


def _nonce_key(org_id: object, device_id: str) -> str:
    return f"renewal_nonce:{org_id}:{device_id}"


def _store_local_nonce(key: str, nonce: bytes, now: float) -> None:
    if len(_local_nonces) >= _MAX_LOCAL_NONCES:
        for stale in [k for k, (_, exp) in list(_local_nonces.items()) if exp <= now]:
            _local_nonces.pop(stale, None)
        while len(_local_nonces) >= _MAX_LOCAL_NONCES:  # still full → evict soonest-expiring
            _local_nonces.pop(min(_local_nonces, key=lambda k: _local_nonces[k][1]), None)
    _local_nonces[key] = (nonce, now + _NONCE_TTL_SECONDS)


async def _store_nonce(redis: object, key: str, nonce: bytes) -> None:
    if redis is not None:
        try:
            await redis.set(key, base64.b64encode(nonce).decode(), ex=_NONCE_TTL_SECONDS)
            return
        except Exception:  # noqa: BLE001 — redis hiccup → in-memory fallback
            logger.warning("renewal_nonce_redis_store_failed", exc_info=True)
    _store_local_nonce(key, nonce, time.monotonic())


async def _consume_nonce(redis: object, key: str) -> bytes | None:
    """Atomically fetch+delete the nonce (single-use). Returns None if missing/expired."""
    if redis is not None:
        try:
            getdel = getattr(redis, "getdel", None)
            val = await getdel(key) if getdel is not None else await redis.eval(_GETDEL_LUA, 1, key)
            if val is None:
                return None
            return base64.b64decode(val.decode() if isinstance(val, bytes) else val)
        except Exception:  # noqa: BLE001 — never fall back to in-memory here (no double-spend)
            logger.warning("renewal_nonce_redis_consume_failed", exc_info=True)
            return None
    entry = _local_nonces.pop(key, None)
    if entry is None:
        return None
    nonce, expiry = entry
    return nonce if time.monotonic() < expiry else None


class ChallengeRequest(BaseModel):
    device_id: str = Field(..., min_length=16, max_length=DEVICE_ID_MAX_LENGTH)


class ChallengeResponse(BaseModel):
    nonce: str  # base64 of the raw bytes to sign
    device_pubkey_thumbprint: str
    expires_in: int = _NONCE_TTL_SECONDS


class RenewRequest(BaseModel):
    device_id: str = Field(..., min_length=16, max_length=DEVICE_ID_MAX_LENGTH)
    public_key_pem: str = Field(..., max_length=4096)
    signature: str = Field(..., max_length=512)  # base64 Ed25519 signature over the nonce


class RenewResponse(BaseModel):
    license_token: str
    device_id: str
    plan: str
    device_limit: int
    device_count: int
    api_key_prefix: str
    device_pubkey_thumbprint: str = ""
    server_time: float = 0.0


def _err(status: int, code: str, message: str, **extra: object) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": {"code": code, "message": message, **extra}})


async def _load_renewable_device(
    api_key_row: object, device_id: str, db: AsyncSession
) -> DeviceRegistration:
    """Load the device row and assert it is ACTIVE + key-bound (PoP prerequisites)."""
    row = (
        await db.execute(
            select(DeviceRegistration).where(
                DeviceRegistration.api_key_id == api_key_row.id,
                DeviceRegistration.device_id == device_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise _err(404, "device_not_registered", "No such device for this API key; register first.")
    if row.status == DeviceStatus.REVOKED:
        raise _err(403, "device_revoked", "This device has been revoked.")
    if row.status != DeviceStatus.ACTIVE:
        raise _err(409, "device_inactive", "This device is not active.")
    if not (row.device_pubkey_thumbprint or "").strip():
        raise _err(
            409,
            "device_not_bound",
            "This device has no bound device key; re-register to bind a key before renewal.",
        )
    return row


@router.post(
    "/v1/license/challenge",
    response_model=ChallengeResponse,
    summary="Begin renewal proof-of-possession — receive a single-use nonce to sign",
)
async def license_challenge(
    body: ChallengeRequest,
    request: Request,
    ctx: Annotated[AuthContext, Depends(get_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChallengeResponse:
    await check_named_rate_limit(
        ctx["org_id"],
        getattr(request.app.state, "redis", None),
        key_prefix="license_challenge",
        limit_per_minute=30,
        request_state=getattr(request, "state", None),
    )
    api_key_row = await _load_api_key_with_org(ctx["key_id"], db)
    if api_key_row is None:
        raise _err(401, "api_key_not_found", "API key not found.")
    row = await _load_renewable_device(api_key_row, body.device_id, db)
    nonce = secrets.token_bytes(32)
    await _store_nonce(
        getattr(request.app.state, "redis", None), _nonce_key(ctx["org_id"], body.device_id), nonce
    )
    return ChallengeResponse(
        nonce=base64.b64encode(nonce).decode(),
        device_pubkey_thumbprint=row.device_pubkey_thumbprint,
    )


@router.post(
    "/v1/license/renew",
    response_model=RenewResponse,
    summary="Renew a device license by proving possession of the bound device key",
)
async def license_renew(
    body: RenewRequest,
    request: Request,
    ctx: Annotated[AuthContext, Depends(get_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RenewResponse:
    await check_named_rate_limit(
        ctx["org_id"],
        getattr(request.app.state, "redis", None),
        key_prefix="license_renew",
        limit_per_minute=30,
        request_state=getattr(request, "state", None),
    )
    api_key_row = await _load_api_key_with_org(ctx["key_id"], db, lock=True)
    if api_key_row is None:
        raise _err(401, "api_key_not_found", "API key not found.")
    row = await _load_renewable_device(api_key_row, body.device_id, db)

    # Consume the nonce FIRST (single-use): a failed attempt still burns it, so one nonce
    # buys at most one verification attempt (no signature-grinding against a live nonce).
    nonce = await _consume_nonce(
        getattr(request.app.state, "redis", None), _nonce_key(ctx["org_id"], body.device_id)
    )
    if nonce is None:
        raise _err(409, "challenge_required", "No valid challenge; request a new nonce and retry.")

    # Binding: the presented public key must be the one bound to this device.
    if thumbprint_for_public_pem(body.public_key_pem) != row.device_pubkey_thumbprint:
        raise _err(409, "device_key_mismatch", "Presented key does not match the bound device key.")

    # Possession: the signature over the server nonce must verify (private key never sent).
    try:
        signature = base64.b64decode(body.signature)
    except (ValueError, TypeError) as exc:
        raise _err(400, "bad_signature_encoding", "signature must be base64.") from exc
    if not verify_signature(body.public_key_pem, nonce, signature):
        raise _err(401, "proof_of_possession_failed", "Signature did not verify.")

    plan = _plan_name(api_key_row.organization.plan)
    device_limit = _api_key_effective_device_limit(api_key_row, plan)
    # Concurrent-cap gate: a renewal refreshes the heartbeat clock, so a STALE device renewing while
    # other live nodes already fill the cap would reclaim a slot it had already freed — reject it
    # instead. A device still inside the active window is excluded from the count, so a live
    # device's normal renewal is unaffected. No-op when active-node enforcement is off.
    renew_block = await node_admission_block_count(
        api_key_row.id, db, device_id=body.device_id, device_limit=device_limit
    )
    if renew_block is not None:
        raise _err(
            402,
            "device_limit_reached",
            f"{renew_block}/{device_limit} devices are currently active; this device's slot was "
            "reassigned while it was offline. Revoke an active device to renew this one.",
        )
    # Guarded update FIRST (TOCTOU): if the device was revoked between load and now, this
    # matches 0 rows → reject WITHOUT issuing a token. Only mint the license once the row is
    # confirmed still ACTIVE under this same transaction.
    upd = await db.execute(
        update(DeviceRegistration)
        .where(
            DeviceRegistration.id == row.id,
            DeviceRegistration.status == DeviceStatus.ACTIVE,
        )
        .values(
            last_heartbeat_at=datetime.now(UTC),
            heartbeat_count=DeviceRegistration.heartbeat_count + 1,
        )
    )
    if upd.rowcount == 0:
        await db.rollback()
        raise _err(403, "device_revoked", "Device was revoked; renewal denied.")
    await db.commit()
    token = _issue_license_jwt(
        device_id=body.device_id,
        api_key_prefix=api_key_row.key_prefix,
        plan=plan,
        device_limit=device_limit,
        org_id=str(api_key_row.org_id),
        api_key_expires_at=api_key_row.expires_at,
        device_pubkey_thumbprint=row.device_pubkey_thumbprint,
    )
    device_count = await effective_node_count(api_key_row.id, db)
    logger.info("license_renewed", device_id=body.device_id[:8], org_id=str(api_key_row.org_id))
    return RenewResponse(
        license_token=token,
        device_id=body.device_id,
        plan=plan,
        device_limit=device_limit,
        device_count=device_count,
        api_key_prefix=api_key_row.key_prefix,
        device_pubkey_thumbprint=row.device_pubkey_thumbprint,
        server_time=time.time(),
    )
