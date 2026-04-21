"""
Device registration service — server-side enforcement of per-plan device limits.

Called by /v1/device/register and /v1/device/heartbeat.

Device limits per plan:
  free        → 1 device
  developer   → 3 devices
  pro         → 10 devices
  enterprise  → unlimited (0)

On registration:
  1. Hash API key → look up org + plan
  2. Count non-revoked devices for this api_key_id
  3. If at limit → return 402 with upgrade prompt
  4. Upsert device row (handles re-registration of same machine gracefully)
  5. Issue signed JWT containing device_id, plan, device_limit, expires_at

On heartbeat:
  1. Verify JWT signature
  2. Update last_heartbeat_at + heartbeat_count
  3. Return current device count + limit (so client can warn on approaching limit)

On list:
  Return all non-revoked devices for the org, grouped by API key label.

On revoke:
  Set status=revoked (does NOT delete — preserved for audit log).
"""
from __future__ import annotations

import hashlib
import time
import uuid
from datetime import UTC, datetime
from typing import TypedDict

import jwt
import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.models.api_key import APIKey, APIKeyStatus
from apps.api_server.models.device import DeviceRegistration, DeviceStatus
from apps.api_server.services.plan_limits import device_limit as _plan_device_limit
from apps.api_server.services.plan_limits import local_runtime_allowed as _plan_local_runtime

logger = structlog.get_logger(__name__)

# ── Plan limits (derived from plan_limits.py — do not duplicate here) ────────

def _device_limits_compat() -> dict[str, int]:
    """Compatibility shim — prefer plan_limits.device_limit(plan) directly."""
    from apps.api_server.services.plan_limits import _PLANS

    return {name: cfg.devices for name, cfg in _PLANS.items()}

_DEVICE_LIMITS = _device_limits_compat()

# License JWT config
_JWT_ALGORITHM = "HS256"
_JWT_ISSUER    = "algenta-control-plane"
_GRACE_DAYS    = 14
_LICENSE_TTL_DAYS = 365   # 1-year license; refreshed on re-registration


def _plan_name(plan: object) -> str:
    return getattr(plan, "value", str(plan))


def _get_license_secret() -> str:
    """
    In production: use an RSA private key (RS256) stored in a secret manager.
    v1: HMAC secret from settings — good enough for a single-node control plane.
    """
    from apps.api_server.config import get_settings
    settings = get_settings()
    secret = getattr(settings, "license_signing_secret", None)
    if not secret:
        # Fallback: derive from the app secret key (not ideal for prod, fine for v1)
        secret = hashlib.sha256(
            (settings.jwt_secret + ":license-signing").encode()
        ).hexdigest()
    return secret


# ── TypedDicts ────────────────────────────────────────────────────────────────

class DeviceRegistrationResult(TypedDict):
    license_token: str
    device_id: str
    plan: str
    device_limit: int
    device_count: int          # current count after this registration
    api_key_prefix: str
    message: str


class HeartbeatResult(TypedDict):
    device_id: str
    plan: str
    device_limit: int
    device_count: int
    status: str                # "ok" | "approaching_limit" | "over_limit"
    message: str


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _resolve_api_key(raw_key: str, db: AsyncSession) -> APIKey | None:
    """Look up APIKey row by hashed value."""
    hashed = hashlib.sha256(raw_key.encode()).hexdigest()
    result = await db.execute(
        select(APIKey).where(
            APIKey.hashed_key == hashed,
            APIKey.status == APIKeyStatus.ACTIVE,
        )
    )
    return result.scalar_one_or_none()


async def _active_device_count(api_key_id: uuid.UUID, db: AsyncSession) -> int:
    """Count non-revoked devices for this API key."""
    result = await db.execute(
        select(func.count()).where(
            DeviceRegistration.api_key_id == api_key_id,
            DeviceRegistration.status != DeviceStatus.REVOKED,
        )
    )
    return result.scalar_one() or 0


def _issue_license_jwt(
    device_id: str,
    api_key_prefix: str,
    plan: str,
    device_limit: int,
    org_id: str,
) -> str:
    now = int(time.time())
    payload = {
        "api_key_prefix": api_key_prefix,
        "device_id":      device_id,
        "plan":           plan,
        "device_limit":   device_limit,
        "org_id":         org_id,
        "permitted_modules": ["*"],
        "issued_at":      now,
        "expires_at":     now + (_LICENSE_TTL_DAYS * 86400),
        "grace_days":     _GRACE_DAYS,
        "iss":            _JWT_ISSUER,
        "sub":            "device-license",
        "ver":            1,
    }
    return jwt.encode(payload, _get_license_secret(), algorithm=_JWT_ALGORITHM)


# ── Public service functions ──────────────────────────────────────────────────

async def register_device(
    raw_api_key: str,
    device_info: dict,
    db: AsyncSession,
) -> DeviceRegistrationResult | None:
    """
    Register or re-register a device under an API key.

    Returns None if the API key is invalid.
    Raises ValueError if the device limit is reached.
    """
    api_key_row = await _resolve_api_key(raw_api_key, db)
    if api_key_row is None:
        return None

    device_id  = device_info.get("device_id", "")
    # Eager-load org to get plan
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(APIKey)
        .options(selectinload(APIKey.organization))
        .where(APIKey.id == api_key_row.id)
    )
    api_key_row = result.scalar_one()
    plan = _plan_name(api_key_row.organization.plan)

    # STARTER (free) plan — cloud API only, local runtime not permitted
    if not _plan_local_runtime(plan):
        raise ValueError(
            f"Plan '{plan}' (STARTER) does not include local runtime access. "
            "Upgrade to PRO or higher to register devices and use the local runtime."
        )

    device_limit_val = _plan_device_limit(plan)

    # Check for existing registration of this exact device_id
    existing = await db.execute(
        select(DeviceRegistration).where(
            DeviceRegistration.api_key_id == api_key_row.id,
            DeviceRegistration.device_id  == device_id,
        )
    )
    existing_row = existing.scalar_one_or_none()

    if existing_row is None:
        # New device — check limit
        current_count = await _active_device_count(api_key_row.id, db)
        if device_limit_val > 0 and current_count >= device_limit_val:
            raise ValueError(
                f"Device limit reached: plan '{plan}' allows {device_limit_val} device(s). "
                f"You have {current_count} registered. "
                f"Revoke an existing device or upgrade your plan."
            )
        row = DeviceRegistration(
            id=uuid.uuid4(),
            org_id=api_key_row.org_id,
            api_key_id=api_key_row.id,
            device_id=device_id,
            platform=device_info.get("platform", ""),
            platform_version=device_info.get("platform_version", ""),
            hostname_hash=device_info.get("hostname_hash", ""),
            sdk_version=device_info.get("sdk_version", ""),
            status=DeviceStatus.ACTIVE,
            last_heartbeat_at=datetime.now(UTC),
            heartbeat_count=1,
        )
        db.add(row)
        await db.flush()
        current_count += 1
    else:
        # Re-registration of same device
        if existing_row.status == DeviceStatus.REVOKED:
            current_count = await _active_device_count(api_key_row.id, db)
            if device_limit_val > 0 and current_count >= device_limit_val:
                raise ValueError(
                    f"Cannot re-activate: device limit of {device_limit_val} reached."
                )
        await db.execute(
            update(DeviceRegistration)
            .where(DeviceRegistration.id == existing_row.id)
            .values(
                status=DeviceStatus.ACTIVE,
                platform=device_info.get("platform", existing_row.platform),
                sdk_version=device_info.get("sdk_version", existing_row.sdk_version),
                last_heartbeat_at=datetime.now(UTC),
                heartbeat_count=DeviceRegistration.heartbeat_count + 1,
            )
        )
        current_count = await _active_device_count(api_key_row.id, db)

    await db.commit()

    license_token = _issue_license_jwt(
        device_id=device_id,
        api_key_prefix=api_key_row.key_prefix,
        plan=plan,
        device_limit=device_limit_val,
        org_id=str(api_key_row.org_id),
    )
    logger.info(
        "device_registered",
        device_id=device_id[:8],
        plan=plan,
        device_count=current_count,
        device_limit=device_limit_val,
        org_id=str(api_key_row.org_id),
    )
    return DeviceRegistrationResult(
        license_token=license_token,
        device_id=device_id,
        plan=plan,
        device_limit=device_limit_val,
        device_count=current_count,
        api_key_prefix=api_key_row.key_prefix,
        message=(
            f"Device registered. {current_count}/{device_limit_val or '∞'} "
            f"devices on {plan} plan."
        ),
    )


async def record_heartbeat(
    raw_api_key: str,
    device_id: str,
    usage: dict,
    db: AsyncSession,
) -> HeartbeatResult | None:
    """Update last_heartbeat_at and return device count status."""
    api_key_row = await _resolve_api_key(raw_api_key, db)
    if api_key_row is None:
        return None

    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(APIKey)
        .options(selectinload(APIKey.organization))
        .where(APIKey.id == api_key_row.id)
    )
    api_key_row = result.scalar_one()
    plan = _plan_name(api_key_row.organization.plan)
    device_limit = _plan_device_limit(plan)

    await db.execute(
        update(DeviceRegistration)
        .where(
            DeviceRegistration.api_key_id == api_key_row.id,
            DeviceRegistration.device_id  == device_id,
        )
        .values(
            last_heartbeat_at=datetime.now(UTC),
            heartbeat_count=DeviceRegistration.heartbeat_count + 1,
            status=DeviceStatus.ACTIVE,
        )
    )
    await db.commit()

    device_count = await _active_device_count(api_key_row.id, db)

    if device_limit == 0:
        status, message = "ok", f"{device_count} device(s) active — unlimited plan"
    elif device_count > device_limit:
        status = "over_limit"
        message = (
            f"{device_count}/{device_limit} devices — over limit, "
            "please upgrade or revoke devices"
        )
    elif device_count >= device_limit * 0.8:
        status = "approaching_limit"
        message = f"{device_count}/{device_limit} devices — approaching limit"
    else:
        status = "ok"
        message = f"{device_count}/{device_limit} devices active"

    return HeartbeatResult(
        device_id=device_id,
        plan=plan,
        device_limit=device_limit,
        device_count=device_count,
        status=status,
        message=message,
    )


async def list_devices(org_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    """List all non-revoked devices for an org with their API key labels."""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(DeviceRegistration)
        .options(selectinload(DeviceRegistration.api_key))
        .where(
            DeviceRegistration.org_id == org_id,
            DeviceRegistration.status != DeviceStatus.REVOKED,
        )
        .order_by(DeviceRegistration.last_heartbeat_at.desc().nullslast())
    )
    rows = result.scalars().all()
    return [
        {
            "id":               str(r.id),
            "device_id":        r.device_id[:8] + "...",    # truncated for display
            "platform":         r.platform,
            "platform_version": r.platform_version,
            "sdk_version":      r.sdk_version,
            "status":           r.status,
            "api_key_label":    r.api_key.label if r.api_key else "",
            "api_key_prefix":   r.api_key.key_prefix if r.api_key else "",
            "registered_at":    r.created_at.isoformat() if r.created_at else None,
            "last_heartbeat_at": r.last_heartbeat_at.isoformat() if r.last_heartbeat_at else None,
            "heartbeat_count":  r.heartbeat_count,
        }
        for r in rows
    ]


async def revoke_device(
    org_id: uuid.UUID,
    registration_id: uuid.UUID,
    db: AsyncSession,
) -> bool:
    """Revoke a device by its registration UUID. Returns True if found."""
    result = await db.execute(
        update(DeviceRegistration)
        .where(
            DeviceRegistration.id     == registration_id,
            DeviceRegistration.org_id == org_id,
        )
        .values(status=DeviceStatus.REVOKED)
        .returning(DeviceRegistration.id)
    )
    await db.commit()
    return result.scalar_one_or_none() is not None
