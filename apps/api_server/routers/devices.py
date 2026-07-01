"""
/v1/device — device registration and heartbeat endpoints.

Called by the Algenta SDK (apps/runtime/license.py) during:
  - algenta login       → POST /v1/device/register
  - daemon heartbeat    → POST /v1/device/heartbeat
  - de license status   → GET  /v1/device/list
  - de runtime revoke   → DELETE /v1/device/{id}
"""

from __future__ import annotations

import uuid
from datetime import UTC
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.models.device import (
    DEVICE_HOSTNAME_HASH_MAX_LENGTH,
    DEVICE_ID_MAX_LENGTH,
    DEVICE_PLATFORM_MAX_LENGTH,
    DEVICE_PLATFORM_VERSION_MAX_LENGTH,
    DEVICE_PUBKEY_THUMBPRINT_MAX_LENGTH,
    DEVICE_SDK_VERSION_MAX_LENGTH,
    DeviceRegistration,
    DeviceStatus,
)
from apps.api_server.pagination import paginate_sequence
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.device_service import (
    _api_key_effective_device_limit,
    _check_device_key_binding,
    _device_identity_mismatch_error,
    _device_identity_mismatched_fields,
    _plan_name,
    active_node_cap_enforced,
    effective_node_count,
    installs_per_hour,
    list_devices,
    node_admission_block_count,
    recent_new_registration_count,
    revoke_device,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["devices"])


# ── Request / response models ─────────────────────────────────────────────────


class DeviceInfo(BaseModel):
    device_id: str = Field(..., min_length=16, max_length=DEVICE_ID_MAX_LENGTH)
    platform: str = Field(default="", max_length=DEVICE_PLATFORM_MAX_LENGTH)
    platform_version: str = Field(default="", max_length=DEVICE_PLATFORM_VERSION_MAX_LENGTH)
    hostname_hash: str = Field(default="", max_length=DEVICE_HOSTNAME_HASH_MAX_LENGTH)
    sdk_version: str = Field(default="", max_length=DEVICE_SDK_VERSION_MAX_LENGTH)
    # Ed25519 public-key thumbprint ("ed25519:<b64url(sha256(pub))>"). Optional/back-compat:
    # bound on first keypair-aware register; a later mismatch is rejected as a clone.
    device_pubkey_thumbprint: str = Field(
        default="", max_length=DEVICE_PUBKEY_THUMBPRINT_MAX_LENGTH
    )


class RegisterRequest(BaseModel):
    device: DeviceInfo


class RegisterResponse(BaseModel):
    license_token: str
    device_id: str
    plan: str
    device_limit: int  # 0 = unlimited
    device_count: int
    api_key_prefix: str
    message: str
    device_pubkey_thumbprint: str = ""  # echo of the bound device key (if any)
    # Credit bucket — initial grant at registration
    credits_granted: int = 0
    credits_expires_at: float = 0.0
    credits_billing_period: str = ""
    server_time: float = 0.0


class HeartbeatRequest(BaseModel):
    device_id: str = Field(..., min_length=16, max_length=64)
    usage: dict[str, object] = Field(default_factory=dict)


class HeartbeatResponse(BaseModel):
    device_id: str
    plan: str
    device_limit: int
    device_count: int
    status: str  # "ok" | "approaching_limit" | "over_limit"
    message: str
    server_time: float = 0.0


class DeviceListResponse(BaseModel):
    devices: list[dict[str, object]]
    device_count: int
    total: int
    page: int
    limit: int
    pages: int
    device_limit: int
    plan: str


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/v1/device/register",
    response_model=RegisterResponse,
    summary="Register a device and receive a signed license token",
    description=(
        "Called by `algenta login`. Registers the calling machine under the "
        "API key, checks the plan's device limit, and returns a signed JWT "
        "device license stored locally by the SDK. "
        "Re-registering the same device (same device_id) refreshes the license."
    ),
)
async def device_register(
    body: RegisterRequest,
    request: Request,
    ctx: Annotated[AuthContext, Depends(get_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    # Pass raw API key through request state (set by auth middleware)
    # We need the raw key to look up the APIKey row by hash.
    # The auth middleware already validated it — we just re-use it here.
) -> RegisterResponse:
    from datetime import datetime

    from apps.api_server.services.device_service import (
        _issue_license_jwt,
        _load_api_key_with_org,
        _plan_name,
    )

    api_key_row = await _load_api_key_with_org(ctx["key_id"], db, lock=True)
    if api_key_row is None:
        raise HTTPException(status_code=401, detail="API key not found")
    plan = _plan_name(api_key_row.organization.plan)

    from apps.api_server.services.plan_limits import (
        credit_batch_size as _get_credit_batch,
    )
    from apps.api_server.services.plan_limits import (
        local_runtime_allowed,
    )

    if not local_runtime_allowed(plan):
        raise HTTPException(
            status_code=402,
            detail={
                "error": "local_runtime_not_included",
                "message": (
                    "The STARTER plan includes cloud API access only. "
                    "Upgrade to PRO ($99/dev/mo) to unlock the local runtime and register devices."
                ),
                "plan": plan,
                "upgrade_url": "https://algenta.io/pricing",
            },
        )

    device_limit = _api_key_effective_device_limit(api_key_row, plan)
    device_id = body.device.device_id
    device_info = body.device.model_dump()
    if device_limit > 0 and not body.device.platform.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "device_platform_required",
                    "message": (
                        "This API key is bound to a finite number of devices. "
                        "Provide device.platform when registering a device."
                    ),
                    "required_field": "platform",
                }
            },
        )
    if device_limit > 0 and not body.device.hostname_hash.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "device_fingerprint_required",
                    "message": (
                        "This API key is bound to a finite number of devices. "
                        "Provide device.hostname_hash when registering a device."
                    ),
                    "required_field": "hostname_hash",
                }
            },
        )

    existing = await db.execute(
        select(DeviceRegistration).where(
            DeviceRegistration.api_key_id == api_key_row.id,
            DeviceRegistration.device_id == device_id,
        )
    )
    existing_row = existing.scalar_one_or_none()

    if existing_row is None:
        # Install/registration abuse protection: rate-limit brand-NEW device installs (not usage,
        # not license refreshes). Dynamic per plan; generous so legit fleet scale-up never trips it.
        install_budget = installs_per_hour(plan)
        if install_budget > 0:
            recent = await recent_new_registration_count(api_key_row.id, db)
            if recent >= install_budget:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "device_registration_rate_limited",
                        "message": (
                            f"Too many new device registrations for API key '{api_key_row.label}' "
                            f"(limit {install_budget}/hour). Re-registering an existing device is "
                            "unaffected; wait and retry to add a brand-new device."
                        ),
                        "limit": install_budget,
                        "window_seconds": 3600,
                        "plan": plan,
                    },
                    headers={"Retry-After": "3600"},
                )
        # Enforce the cap against recently-ACTIVE nodes when active-node-cap enforcement is on
        # (a scaled-down node frees its slot automatically); else against all non-revoked devices.
        current_count = await effective_node_count(api_key_row.id, db)
        if device_limit > 0 and current_count >= device_limit:
            _enforced = active_node_cap_enforced()
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "device_limit_reached",
                    "message": (
                        f"API key '{api_key_row.label}' allows {device_limit} device(s). "
                        f"You have {current_count} "
                        f"{'currently active' if _enforced else 'registered'}. "
                        "Revoke an existing device or create a broader key."
                    ),
                    "device_count": current_count,
                    "device_limit": device_limit,
                    "plan": plan,
                    "upgrade_url": "https://algenta.io/pricing",
                },
            )
        row = DeviceRegistration(
            id=uuid.uuid4(),
            org_id=api_key_row.org_id,
            api_key_id=api_key_row.id,
            device_id=device_id,
            platform=body.device.platform,
            platform_version=body.device.platform_version,
            hostname_hash=body.device.hostname_hash,
            sdk_version=body.device.sdk_version,
            device_pubkey_thumbprint=body.device.device_pubkey_thumbprint,
            status=DeviceStatus.ACTIVE,
            last_heartbeat_at=datetime.now(UTC),
            heartbeat_count=1,
        )
        db.add(row)
        await db.flush()
        current_count += 1
        bound_thumbprint = body.device.device_pubkey_thumbprint
    else:
        if existing_row.status == DeviceStatus.REVOKED:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": "device_revoked",
                        "message": (
                            f"Device '{device_id}' has been revoked for this API key. "
                            "Use a different key or ask an owner to authorize "
                            "a different device identity."
                        ),
                        "device_id": device_id,
                        "plan": plan,
                    }
                },
            )
        mismatched_fields = _device_identity_mismatched_fields(existing_row, device_info)
        if mismatched_fields:
            mismatch_error = _device_identity_mismatch_error(
                device_id=device_id,
                plan=plan,
                mismatched_fields=mismatched_fields,
            )
            raise HTTPException(
                status_code=mismatch_error.status_code,
                detail={
                    "error": {
                        "code": mismatch_error.code,
                        "message": mismatch_error.message,
                        **mismatch_error.details,
                    }
                },
            )
        # Cryptographic device binding: reject a re-register that presents a DIFFERENT
        # device key than the one this device is bound to (clone attempt). Empty incoming
        # (legacy fingerprint-only client) is allowed and never re-binds.
        try:
            _check_device_key_binding(existing_row, body.device.device_pubkey_thumbprint)
        except ValueError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "device_key_mismatch",
                        "message": str(exc),
                        "device_id": device_id,
                        "plan": plan,
                    }
                },
            ) from exc

        # Concurrent-cap gate (active-node enforcement only): re-registering an already-active
        # device is admitted (excluded from the count), but a STALE device whose slot was reclaimed
        # cannot come back while other live nodes already fill the cap — reject instead of reviving
        # it. No-op when enforcement is off, so a plain re-register/refresh is unchanged.
        revival_block = await node_admission_block_count(
            api_key_row.id, db, device_id=device_id, device_limit=device_limit
        )
        if revival_block is not None:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "device_limit_reached",
                    "message": (
                        f"API key '{api_key_row.label}' allows {device_limit} device(s) and "
                        f"{revival_block} are currently active. This device's slot was reassigned "
                        "while it was offline — revoke an active device to bring it back."
                    ),
                    "device_count": revival_block,
                    "device_limit": device_limit,
                    "plan": plan,
                    "upgrade_url": "https://algenta.io/pricing",
                },
            )

        from sqlalchemy import update as sa_update

        await db.execute(
            sa_update(DeviceRegistration)
            .where(DeviceRegistration.id == existing_row.id)
            .values(
                status=DeviceStatus.ACTIVE,
                platform=body.device.platform or existing_row.platform,
                platform_version=body.device.platform_version or existing_row.platform_version,
                hostname_hash=body.device.hostname_hash or existing_row.hostname_hash,
                sdk_version=body.device.sdk_version or existing_row.sdk_version,
                device_pubkey_thumbprint=(
                    body.device.device_pubkey_thumbprint
                    or existing_row.device_pubkey_thumbprint
                ),
                last_heartbeat_at=datetime.now(UTC),
                heartbeat_count=DeviceRegistration.heartbeat_count + 1,
            )
        )
        current_count = await effective_node_count(api_key_row.id, db)
        bound_thumbprint = (
            body.device.device_pubkey_thumbprint or existing_row.device_pubkey_thumbprint
        )

    await db.commit()
    logger.info(
        "device_registered",
        device_id=device_id[:8],
        plan=plan,
        device_count=current_count,
        org_id=str(api_key_row.org_id),
    )

    token = _issue_license_jwt(
        device_id=device_id,
        api_key_prefix=api_key_row.key_prefix,
        plan=plan,
        device_limit=device_limit,
        org_id=str(api_key_row.org_id),
        api_key_expires_at=api_key_row.expires_at,
        device_pubkey_thumbprint=bound_thumbprint,
    )

    # ── Issue initial credit batch ─────────────────────────────────────────
    import time as _time
    from datetime import datetime

    credit_batch = _get_credit_batch(plan)
    credit_expires = _time.time() + 86_400  # 24h
    billing_period = datetime.now(UTC).strftime("%Y-%m")

    # Record credit grant in Redis (best-effort)
    try:
        redis_client = getattr(request.app.state, "redis", None)
        if redis_client is not None:
            _key = f"credits_issued:{api_key_row.org_id}:{billing_period}"
            await redis_client.incrby(_key, credit_batch)
            await redis_client.expire(_key, 35 * 86_400)
    except Exception as exc:
        logger.debug(
            "device_registration_credit_cache_write_failed",
            org_id=str(api_key_row.org_id),
            billing_period=billing_period,
            error=str(exc),
        )

    server_time = _time.time()

    return RegisterResponse(
        license_token=token,
        device_id=device_id,
        plan=plan,
        device_limit=device_limit,
        device_count=current_count,
        api_key_prefix=api_key_row.key_prefix,
        message=f"Device registered. {current_count}/{device_limit or '∞'} devices on {plan} plan.",
        device_pubkey_thumbprint=body.device.device_pubkey_thumbprint,
        credits_granted=credit_batch,
        credits_expires_at=credit_expires,
        credits_billing_period=billing_period,
        server_time=server_time,
    )


@router.post(
    "/v1/device/heartbeat",
    response_model=HeartbeatResponse,
    summary="24-hour device heartbeat — updates last_seen and returns device count",
)
async def device_heartbeat(
    body: HeartbeatRequest,
    ctx: Annotated[AuthContext, Depends(get_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HeartbeatResponse:
    from datetime import datetime

    from sqlalchemy import select
    from sqlalchemy import update as sa_update
    from sqlalchemy.orm import selectinload

    from apps.api_server.models.api_key import APIKey
    from apps.api_server.services.device_service import (
        effective_node_count,
        node_admission_block_count,
    )

    result = await db.execute(
        select(APIKey).options(selectinload(APIKey.organization)).where(APIKey.id == ctx["key_id"])
    )
    api_key_row = result.scalar_one()
    plan = _plan_name(api_key_row.organization.plan)
    device_limit = _api_key_effective_device_limit(api_key_row, plan)

    # Concurrent-cap gate: if this is a STALE device returning while other live nodes already fill
    # the cap, withhold the active SLOT (don't refresh it to ACTIVE) — a heartbeat must not silently
    # push the active set past the cap. A currently-active node is never withheld (see
    # node_admission_block_count: it admits a device that already holds a live slot). Usage is
    # reconciled either way below — work already performed is billed regardless of cap status. No-op
    # when enforcement is off: the refresh then always proceeds exactly as before.
    revival_block = await node_admission_block_count(
        api_key_row.id, db, device_id=body.device_id, device_limit=device_limit
    )

    if revival_block is None:
        await db.execute(
            sa_update(DeviceRegistration)
            .where(
                DeviceRegistration.api_key_id == api_key_row.id,
                DeviceRegistration.device_id == body.device_id,
            )
            .values(
                last_heartbeat_at=datetime.now(UTC),
                heartbeat_count=DeviceRegistration.heartbeat_count + 1,
                status=DeviceStatus.ACTIVE,
            )
        )

    # ── Reconcile local execution count into usage_records — ALWAYS, even when the slot is
    # withheld: an over-cap node's already-performed executions must still be billed, never dropped.
    raw_executions_since = body.usage.get("executions_since_last_heartbeat", 0)
    if isinstance(raw_executions_since, bool):
        executions_since = 0
    elif isinstance(raw_executions_since, int | str | bytes | bytearray):
        executions_since = int(raw_executions_since)
    else:
        executions_since = 0
    if executions_since > 0:
        from apps.api_server.models.usage_record import UsageEndpoint, UsageRecord

        billing_period = datetime.now(UTC).strftime("%Y-%m")
        db.add(
            UsageRecord(
                org_id=api_key_row.org_id,
                api_key_id=api_key_row.id,
                billing_period=billing_period,
                endpoint=UsageEndpoint.SIMULATE,
                billing_units=executions_since,
                scenarios_run=executions_since,
            )
        )

    await db.commit()

    if revival_block is not None:
        # Slot withheld — the device stays stale; report it is over the concurrent cap.
        return HeartbeatResponse(
            device_id=body.device_id,
            plan=plan,
            device_limit=device_limit,
            device_count=revival_block,
            status="over_limit",
            message=(
                f"{revival_block}/{device_limit} active — this device's slot was reassigned while "
                "it was offline; revoke an active device to bring it back."
            ),
            server_time=datetime.now(UTC).timestamp(),
        )

    device_count = await effective_node_count(api_key_row.id, db)

    if device_limit == 0:
        status, message = "ok", f"{device_count} active — unlimited plan"
    elif device_count > device_limit:
        status = "over_limit"
        message = f"{device_count}/{device_limit} — over limit, upgrade or revoke a device"
    elif device_count >= max(1, int(device_limit * 0.8)):
        status = "approaching_limit"
        message = f"{device_count}/{device_limit} devices — approaching limit"
    else:
        status = "ok"
        message = f"{device_count}/{device_limit} devices active"

    return HeartbeatResponse(
        device_id=body.device_id,
        plan=plan,
        device_limit=device_limit,
        device_count=device_count,
        status=status,
        message=message,
        server_time=datetime.now(UTC).timestamp(),
    )


@router.get(
    "/v1/device/list",
    response_model=DeviceListResponse,
    summary="List all registered devices for this org",
)
async def device_list(
    ctx: Annotated[AuthContext, Depends(get_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=200),
) -> DeviceListResponse:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from apps.api_server.models.api_key import APIKey

    result = await db.execute(
        select(APIKey).options(selectinload(APIKey.organization)).where(APIKey.id == ctx["key_id"])
    )
    api_key_row = result.scalar_one()
    plan = _plan_name(api_key_row.organization.plan)
    device_limit = _api_key_effective_device_limit(api_key_row, plan)

    devices = await list_devices(ctx["org_id"], db)
    envelope = paginate_sequence(devices, page=page, limit=limit)
    return DeviceListResponse(
        devices=envelope.items,
        device_count=len(envelope.items),
        total=envelope.total,
        page=envelope.page,
        limit=envelope.limit,
        pages=envelope.pages,
        device_limit=device_limit,
        plan=plan,
    )


@router.delete(
    "/v1/device/{registration_id}",
    summary="Revoke a registered device",
    description="Frees up one device slot. The device will lose access on next license refresh.",
)
async def device_revoke(
    registration_id: uuid.UUID,
    ctx: Annotated[AuthContext, Depends(get_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    found = await revoke_device(ctx["org_id"], registration_id, db)
    if not found:
        raise HTTPException(status_code=404, detail="Device registration not found")
    logger.info("device_revoked", registration_id=str(registration_id), org_id=str(ctx["org_id"]))
    return {"revoked": True, "registration_id": str(registration_id)}


@router.get(
    "/v1/runtime/authorize",
    summary="Authorize a runtime bundle download for the calling API key",
    description=(
        "Called server-to-server by the packages.telys.ai runtime host to gate a self-service download: a "
        "valid API key whose plan grants the Telys runtime (products.telys) gets 200 + the entitlement; "
        "otherwise 401 (bad key) / 403 (no runtime entitlement). Mints nothing — a pure authorization check."
    ),
)
async def runtime_authorize(
    ctx: Annotated[AuthContext, Depends(get_current_org)],
) -> dict[str, object]:
    from apps.api_server.services.entitlement_service import resolve_entitlement

    plan = str(ctx.get("plan") or "")
    grant = resolve_entitlement(plan).products.get("telys")
    if grant is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "no_runtime_entitlement", "message": "plan does not grant the Telys runtime"},
        )
    return {
        "authorized": True,
        "product": "telys",
        "tier": grant.tier,
        "features": sorted(grant.features),
        "plan": plan,
    }
