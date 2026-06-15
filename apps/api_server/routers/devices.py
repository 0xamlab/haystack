"""
/v1/device — device registration and heartbeat endpoints.

Called by the Codna SDK (apps/runtime/license.py) during:
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
    DEVICE_SDK_VERSION_MAX_LENGTH,
    DeviceRegistration,
    DeviceStatus,
)
from apps.api_server.pagination import paginate_sequence
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.device_service import (
    _api_key_effective_device_limit,
    _device_identity_mismatch_error,
    _device_identity_mismatched_fields,
    _plan_name,
    list_devices,
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
        _active_device_count,
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
        current_count = await _active_device_count(api_key_row.id, db)
        if device_limit > 0 and current_count >= device_limit:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "device_limit_reached",
                    "message": (
                        f"API key '{api_key_row.label}' allows {device_limit} device(s). "
                        f"You have {current_count} registered. "
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
            status=DeviceStatus.ACTIVE,
            last_heartbeat_at=datetime.now(UTC),
            heartbeat_count=1,
        )
        db.add(row)
        await db.flush()
        current_count += 1
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
                last_heartbeat_at=datetime.now(UTC),
                heartbeat_count=DeviceRegistration.heartbeat_count + 1,
            )
        )
        current_count = await _active_device_count(api_key_row.id, db)

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
    from apps.api_server.services.device_service import _active_device_count

    result = await db.execute(
        select(APIKey).options(selectinload(APIKey.organization)).where(APIKey.id == ctx["key_id"])
    )
    api_key_row = result.scalar_one()
    plan = _plan_name(api_key_row.organization.plan)
    device_limit = _api_key_effective_device_limit(api_key_row, plan)

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

    # ── Reconcile local execution count into usage_records ─────────────────
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

    device_count = await _active_device_count(api_key_row.id, db)

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
