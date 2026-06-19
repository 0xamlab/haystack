"""
Device registration service — server-side enforcement of effective per-key device limits.

Called by /v1/device/register and /v1/device/heartbeat.

Device limits per plan:
  free        → cloud API only (no local runtime)
  developer   → 5 devices
  pro         → 5 devices
  team        → 25 devices
  enterprise  → unlimited (0) unless narrowed on the key

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
import hmac
import secrets
import time
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TypedDict

import jwt
import structlog
from fastapi import Request
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api_server.models.api_key import APIKey, APIKeyStatus
from apps.api_server.models.device import (
    DEVICE_BINDING_TOKEN_HASH_MAX_LENGTH,
    DEVICE_HOSTNAME_HASH_MAX_LENGTH,
    DEVICE_ID_MAX_LENGTH,
    DEVICE_PLATFORM_MAX_LENGTH,
    DEVICE_PLATFORM_VERSION_MAX_LENGTH,
    DEVICE_SDK_VERSION_MAX_LENGTH,
    DeviceRegistration,
    DeviceStatus,
)
from apps.api_server.services.auth_service import AuthContext, is_api_key_expired
from apps.api_server.services.plan_limits import effective_device_limit as _effective_device_limit
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
_JWT_ISSUER = "algenta-control-plane"
_GRACE_DAYS = 14
_LICENSE_TTL_DAYS = 365  # fallback TTL for keys without an explicit expiry
HOSTED_DEVICE_ID_HEADER = "X-Algenta-Device-Id"
HOSTED_DEVICE_PLATFORM_HEADER = "X-Algenta-Platform"
HOSTED_DEVICE_PLATFORM_VERSION_HEADER = "X-Algenta-Platform-Version"
HOSTED_DEVICE_HOSTNAME_HASH_HEADER = "X-Algenta-Hostname-Hash"
HOSTED_DEVICE_SDK_VERSION_HEADER = "X-Algenta-SDK-Version"
HOSTED_DEVICE_BINDING_TOKEN_HEADER = "X-Algenta-Device-Binding-Token"  # noqa: S105
# Legacy device-header names (the #157 Algenta rebrand). Algenta is the engine/SDK; these are
# still ACCEPTED on read so deployed raw-HTTP callers / older SDK builds keep working. New
# responses + the bundled SDKs send the canonical X-Algenta-* names above.
LEGACY_HOSTED_DEVICE_ID_HEADER = "X-Codna-Device-Id"
LEGACY_HOSTED_DEVICE_PLATFORM_HEADER = "X-Codna-Platform"
LEGACY_HOSTED_DEVICE_PLATFORM_VERSION_HEADER = "X-Codna-Platform-Version"
LEGACY_HOSTED_DEVICE_HOSTNAME_HASH_HEADER = "X-Codna-Hostname-Hash"
LEGACY_HOSTED_DEVICE_SDK_VERSION_HEADER = "X-Codna-SDK-Version"
LEGACY_HOSTED_DEVICE_BINDING_TOKEN_HEADER = "X-Codna-Device-Binding-Token"  # noqa: S105
_HOSTED_DEVICE_MIN_LENGTH = 16
_HOSTED_DEVICE_BINDING_TOKEN_MIN_LENGTH = 24
_HOSTED_DEVICE_BINDING_EXEMPT_PATHS = frozenset(
    {
        "/v1/device/register",
        "/v1/device/heartbeat",
        "/v1/credits/refresh",
        "/v1/metering",
    }
)
_DEVICE_INFO_LENGTH_LIMITS: tuple[tuple[str, int], ...] = (
    ("device_id", DEVICE_ID_MAX_LENGTH),
    ("platform", DEVICE_PLATFORM_MAX_LENGTH),
    ("platform_version", DEVICE_PLATFORM_VERSION_MAX_LENGTH),
    ("hostname_hash", DEVICE_HOSTNAME_HASH_MAX_LENGTH),
    ("sdk_version", DEVICE_SDK_VERSION_MAX_LENGTH),
)
_DEVICE_IDENTITY_CONSISTENCY_FIELDS: tuple[str, ...] = (
    "hostname_hash",
    "platform",
)


class DeviceBindingError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


class HostedDeviceBindingResult(TypedDict):
    device_id: str
    binding_token: str | None


def _plan_name(plan: object) -> str:
    return getattr(plan, "value", str(plan))


def _api_key_effective_device_limit(api_key_row: APIKey, plan: str) -> int:
    return _effective_device_limit(plan, getattr(api_key_row, "device_limit", None))


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
        secret = hashlib.sha256((settings.jwt_secret + ":license-signing").encode()).hexdigest()
    return secret


def _hash_binding_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _generate_binding_token() -> str:
    return secrets.token_urlsafe(32)


def _validate_device_info_lengths(device_info: Mapping[str, object]) -> None:
    for field_name, max_length in _DEVICE_INFO_LENGTH_LIMITS:
        raw_value = device_info.get(field_name, "")
        if not isinstance(raw_value, str):
            raise ValueError(f"Device field '{field_name}' must be a string.")
        if len(raw_value) > max_length:
            raise ValueError(
                f"Device field '{field_name}' exceeds max length of {max_length} characters."
            )


def _normalized_device_identity_value(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _device_info_value(
    device_info: Mapping[str, object],
    field_name: str,
    *,
    default: str = "",
) -> str:
    raw_value = device_info.get(field_name, default)
    return raw_value if isinstance(raw_value, str) else default


def _device_identity_mismatched_fields(
    existing_row: DeviceRegistration,
    device_info: Mapping[str, object],
) -> tuple[str, ...]:
    mismatches: list[str] = []
    for field_name in _DEVICE_IDENTITY_CONSISTENCY_FIELDS:
        existing_value = _normalized_device_identity_value(
            getattr(existing_row, field_name, ""),
        )
        incoming_value = _normalized_device_identity_value(device_info.get(field_name, ""))
        if existing_value and incoming_value and existing_value != incoming_value:
            mismatches.append(field_name)
    return tuple(mismatches)


def hosted_api_device_binding_required(auth: AuthContext) -> bool:
    return bool(auth.get("device_limit_configured")) and int(auth.get("device_limit", 0)) > 0


def _device_limit_error(
    *,
    api_key_row: APIKey,
    plan: str,
    device_limit: int,
    device_count: int,
) -> DeviceBindingError:
    return DeviceBindingError(
        status_code=402,
        code="device_limit_reached",
        message=(
            f"API key '{api_key_row.label}' allows {device_limit} device(s). "
            f"You have {device_count} registered. "
            "Revoke an existing device or create a broader key."
        ),
        details={
            "device_count": device_count,
            "device_limit": device_limit,
            "plan": plan,
            "upgrade_url": "https://algenta.io/pricing",
        },
    )


def _revoked_device_binding_error(
    *,
    device_id: str,
    plan: str,
) -> DeviceBindingError:
    return DeviceBindingError(
        status_code=403,
        code="device_revoked",
        message=(
            f"Device '{device_id}' has been revoked for this API key. "
            "Use a different key or ask an owner to authorize a different device identity."
        ),
        details={
            "device_id": device_id,
            "plan": plan,
        },
    )


def _device_identity_mismatch_error(
    *,
    device_id: str,
    plan: str,
    mismatched_fields: tuple[str, ...],
) -> DeviceBindingError:
    return DeviceBindingError(
        status_code=403,
        code="device_identity_mismatch",
        message=(
            f"Device '{device_id}' is already bound to different identity metadata "
            "for this API key. "
            "Reuse the original device identity or register a different device ID."
        ),
        details={
            "device_id": device_id,
            "plan": plan,
            "mismatched_fields": list(mismatched_fields),
        },
    )


def _device_binding_token_required_error(
    *,
    device_id: str,
    plan: str,
) -> DeviceBindingError:
    return DeviceBindingError(
        status_code=401,
        code="device_binding_token_required",
        message=(
            f"Device '{device_id}' is already bound for this API key. "
            f"Send the {HOSTED_DEVICE_BINDING_TOKEN_HEADER} header or use the Algenta SDK."
        ),
        details={
            "device_id": device_id,
            "plan": plan,
            "required_header": HOSTED_DEVICE_BINDING_TOKEN_HEADER,
        },
    )


def _invalid_device_binding_token_error(
    *,
    device_id: str,
    plan: str,
) -> DeviceBindingError:
    return DeviceBindingError(
        status_code=403,
        code="invalid_device_binding_token",
        message=(
            f"Device '{device_id}' supplied an invalid hosted binding token for this API key."
        ),
        details={
            "device_id": device_id,
            "plan": plan,
            "required_header": HOSTED_DEVICE_BINDING_TOKEN_HEADER,
        },
    )


def _device_header(request: Request, primary: str, legacy: str, default: str = "") -> str:
    """Read a device header, preferring the canonical X-Algenta-* name and falling back to the
    legacy X-Codna-* name (back-compat for deployed raw-HTTP callers / older SDK builds)."""
    primary_val = request.headers.get(primary, "")
    if primary_val.strip():
        return primary_val
    return request.headers.get(legacy, default)


def _hosted_request_device_info(request: Request) -> dict[str, str]:
    device_id = _device_header(
        request, HOSTED_DEVICE_ID_HEADER, LEGACY_HOSTED_DEVICE_ID_HEADER
    ).strip()
    if not device_id:
        raise DeviceBindingError(
            status_code=401,
            code="device_binding_required",
            message=(
                "This API key is bound to a finite number of devices. "
                f"Send the {HOSTED_DEVICE_ID_HEADER} header or use the Algenta SDK."
            ),
            details={"required_header": HOSTED_DEVICE_ID_HEADER},
        )
    if len(device_id) < _HOSTED_DEVICE_MIN_LENGTH:
        raise DeviceBindingError(
            status_code=400,
            code="invalid_device_binding",
            message=(
                f"{HOSTED_DEVICE_ID_HEADER} must be at least "
                f"{_HOSTED_DEVICE_MIN_LENGTH} characters long."
            ),
            details={"required_header": HOSTED_DEVICE_ID_HEADER},
        )

    device_info = {
        "device_id": device_id,
        "platform": _device_header(
            request, HOSTED_DEVICE_PLATFORM_HEADER, LEGACY_HOSTED_DEVICE_PLATFORM_HEADER
        ).strip(),
        "platform_version": _device_header(
            request,
            HOSTED_DEVICE_PLATFORM_VERSION_HEADER,
            LEGACY_HOSTED_DEVICE_PLATFORM_VERSION_HEADER,
        ).strip(),
        "hostname_hash": _device_header(
            request,
            HOSTED_DEVICE_HOSTNAME_HASH_HEADER,
            LEGACY_HOSTED_DEVICE_HOSTNAME_HASH_HEADER,
        ).strip(),
        "sdk_version": _device_header(
            request,
            HOSTED_DEVICE_SDK_VERSION_HEADER,
            LEGACY_HOSTED_DEVICE_SDK_VERSION_HEADER,
            request.headers.get("User-Agent", ""),
        ).strip()[:DEVICE_SDK_VERSION_MAX_LENGTH],
    }
    try:
        _validate_device_info_lengths(device_info)
    except ValueError as exc:
        raise DeviceBindingError(
            status_code=400,
            code="invalid_device_binding",
            message=str(exc),
        ) from exc
    if not device_info["platform"]:
        raise DeviceBindingError(
            status_code=401,
            code="device_platform_required",
            message=(
                "This API key is bound to a finite number of devices. "
                f"Send the {HOSTED_DEVICE_PLATFORM_HEADER} header or use the Algenta SDK."
            ),
            details={"required_header": HOSTED_DEVICE_PLATFORM_HEADER},
        )
    if not device_info["hostname_hash"]:
        raise DeviceBindingError(
            status_code=401,
            code="device_fingerprint_required",
            message=(
                "This API key is bound to a finite number of devices. "
                f"Send the {HOSTED_DEVICE_HOSTNAME_HASH_HEADER} header or use the Algenta SDK."
            ),
            details={"required_header": HOSTED_DEVICE_HOSTNAME_HASH_HEADER},
        )
    return device_info


def _hosted_request_binding_token(request: Request) -> str:
    token = _device_header(
        request, HOSTED_DEVICE_BINDING_TOKEN_HEADER, LEGACY_HOSTED_DEVICE_BINDING_TOKEN_HEADER
    ).strip()
    if not token:
        return ""
    if len(token) < _HOSTED_DEVICE_BINDING_TOKEN_MIN_LENGTH:
        raise DeviceBindingError(
            status_code=400,
            code="invalid_device_binding",
            message=(
                f"{HOSTED_DEVICE_BINDING_TOKEN_HEADER} must be at least "
                f"{_HOSTED_DEVICE_BINDING_TOKEN_MIN_LENGTH} characters long."
            ),
            details={"required_header": HOSTED_DEVICE_BINDING_TOKEN_HEADER},
        )
    if len(token) > DEVICE_BINDING_TOKEN_HASH_MAX_LENGTH:
        raise DeviceBindingError(
            status_code=400,
            code="invalid_device_binding",
            message=(f"{HOSTED_DEVICE_BINDING_TOKEN_HEADER} exceeds the maximum supported length."),
            details={"required_header": HOSTED_DEVICE_BINDING_TOKEN_HEADER},
        )
    return token


async def _load_api_key_with_org(
    api_key_id: uuid.UUID,
    db: AsyncSession,
    *,
    lock: bool = False,
) -> APIKey | None:
    query = select(APIKey).options(selectinload(APIKey.organization)).where(APIKey.id == api_key_id)
    if lock:
        query = query.with_for_update()
    result = await db.execute(query)
    return result.scalar_one_or_none()


# ── TypedDicts ────────────────────────────────────────────────────────────────


class DeviceRegistrationResult(TypedDict):
    license_token: str
    device_id: str
    plan: str
    device_limit: int
    device_count: int  # current count after this registration
    api_key_prefix: str
    message: str


class HeartbeatResult(TypedDict):
    device_id: str
    plan: str
    device_limit: int
    device_count: int
    status: str  # "ok" | "approaching_limit" | "over_limit"
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
    api_key = result.scalar_one_or_none()
    if api_key is None or is_api_key_expired(api_key.expires_at):
        return None
    return api_key


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
    api_key_expires_at: datetime | None = None,
) -> str:
    now = int(time.time())
    effective_expires_at = now + (_LICENSE_TTL_DAYS * 86400)
    key_expires_at = 0
    if api_key_expires_at is not None:
        normalized_expiry = (
            api_key_expires_at
            if api_key_expires_at.tzinfo is not None
            else api_key_expires_at.replace(tzinfo=UTC)
        )
        key_expires_at = int(normalized_expiry.timestamp())
        effective_expires_at = key_expires_at
    payload = {
        "api_key_prefix": api_key_prefix,
        "device_id": device_id,
        "plan": plan,
        "device_limit": device_limit,
        "org_id": org_id,
        "permitted_modules": ["*"],
        "issued_at": now,
        "expires_at": effective_expires_at,
        "key_expires_at": key_expires_at,
        "grace_days": _GRACE_DAYS,
        "iss": _JWT_ISSUER,
        "sub": "device-license",
        "ver": 1,
    }
    return jwt.encode(payload, _get_license_secret(), algorithm=_JWT_ALGORITHM)


# ── Public service functions ──────────────────────────────────────────────────


async def register_device(
    raw_api_key: str,
    device_info: Mapping[str, object],
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

    _validate_device_info_lengths(device_info)
    device_id = _device_info_value(device_info, "device_id")
    # Eager-load org to get plan
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(APIKey).options(selectinload(APIKey.organization)).where(APIKey.id == api_key_row.id)
    )
    api_key_row = result.scalar_one()
    plan = _plan_name(api_key_row.organization.plan)

    # STARTER (free) plan — cloud API only, local runtime not permitted
    if not _plan_local_runtime(plan):
        raise ValueError(
            f"Plan '{plan}' (STARTER) does not include local runtime access. "
            "Upgrade to PRO or higher to register devices and use the local runtime."
        )

    device_limit_val = _api_key_effective_device_limit(api_key_row, plan)

    # Check for existing registration of this exact device_id
    existing = await db.execute(
        select(DeviceRegistration).where(
            DeviceRegistration.api_key_id == api_key_row.id,
            DeviceRegistration.device_id == device_id,
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
            platform=_device_info_value(device_info, "platform"),
            platform_version=_device_info_value(device_info, "platform_version"),
            hostname_hash=_device_info_value(device_info, "hostname_hash"),
            sdk_version=_device_info_value(device_info, "sdk_version"),
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
            raise ValueError(f"Device '{device_id}' has been revoked for this API key.")
        mismatched_fields = _device_identity_mismatched_fields(existing_row, device_info)
        if mismatched_fields:
            mismatch_error = _device_identity_mismatch_error(
                device_id=device_id,
                plan=plan,
                mismatched_fields=mismatched_fields,
            )
            raise ValueError(mismatch_error.message)
        await db.execute(
            update(DeviceRegistration)
            .where(DeviceRegistration.id == existing_row.id)
            .values(
                status=DeviceStatus.ACTIVE,
                platform=_device_info_value(
                    device_info,
                    "platform",
                    default=existing_row.platform,
                ),
                platform_version=_device_info_value(
                    device_info,
                    "platform_version",
                    default=existing_row.platform_version,
                ),
                hostname_hash=_device_info_value(
                    device_info,
                    "hostname_hash",
                    default=existing_row.hostname_hash,
                ),
                sdk_version=_device_info_value(
                    device_info,
                    "sdk_version",
                    default=existing_row.sdk_version,
                ),
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
        api_key_expires_at=api_key_row.expires_at,
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
            f"Device registered. {current_count}/{device_limit_val or '∞'} devices on {plan} plan."
        ),
    )


async def record_heartbeat(
    raw_api_key: str,
    device_id: str,
    usage: Mapping[str, object],
    db: AsyncSession,
) -> HeartbeatResult | None:
    """Update last_heartbeat_at and return device count status."""
    api_key_row = await _resolve_api_key(raw_api_key, db)
    if api_key_row is None:
        return None

    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(APIKey).options(selectinload(APIKey.organization)).where(APIKey.id == api_key_row.id)
    )
    api_key_row = result.scalar_one()
    plan = _plan_name(api_key_row.organization.plan)
    device_limit = _api_key_effective_device_limit(api_key_row, plan)

    await db.execute(
        update(DeviceRegistration)
        .where(
            DeviceRegistration.api_key_id == api_key_row.id,
            DeviceRegistration.device_id == device_id,
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
            f"{device_count}/{device_limit} devices — over limit, please upgrade or revoke devices"
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


async def bind_hosted_api_device(
    request: Request,
    auth: AuthContext,
    db: AsyncSession,
) -> HostedDeviceBindingResult | None:
    """
    Bind normal hosted API traffic to a registered device when a key has an
    explicit finite per-key device cap.

    This is intentionally opt-in on configured per-key caps to avoid turning
    all legacy bearer keys into machine-bound credentials.
    """
    if request.url.path in _HOSTED_DEVICE_BINDING_EXEMPT_PATHS:
        return None
    if not hosted_api_device_binding_required(auth):
        return None

    device_info = _hosted_request_device_info(request)
    binding_token = _hosted_request_binding_token(request)
    api_key_row = await _load_api_key_with_org(auth["key_id"], db, lock=True)
    if (
        api_key_row is None
        or api_key_row.status != APIKeyStatus.ACTIVE
        or is_api_key_expired(api_key_row.expires_at)
    ):
        raise DeviceBindingError(
            status_code=401,
            code="invalid_api_key",
            message="The API key provided is invalid, expired, or has been revoked.",
        )

    plan = _plan_name(api_key_row.organization.plan)
    device_limit = _api_key_effective_device_limit(api_key_row, plan)
    if api_key_row.device_limit is None or device_limit == 0:
        return {
            "device_id": device_info["device_id"],
            "binding_token": None,
        }

    existing = await db.execute(
        select(DeviceRegistration).where(
            DeviceRegistration.api_key_id == api_key_row.id,
            DeviceRegistration.device_id == device_info["device_id"],
        )
    )
    existing_row = existing.scalar_one_or_none()
    now = datetime.now(UTC)
    if existing_row is None:
        current_count = await _active_device_count(api_key_row.id, db)
        if current_count >= device_limit:
            raise _device_limit_error(
                api_key_row=api_key_row,
                plan=plan,
                device_limit=device_limit,
                device_count=current_count,
            )
        fresh_token = _generate_binding_token()
        db.add(
            DeviceRegistration(
                id=uuid.uuid4(),
                org_id=api_key_row.org_id,
                api_key_id=api_key_row.id,
                device_id=device_info["device_id"],
                platform=device_info["platform"],
                platform_version=device_info["platform_version"],
                hostname_hash=device_info["hostname_hash"],
                sdk_version=device_info["sdk_version"],
                binding_token_hash=_hash_binding_token(fresh_token),
                status=DeviceStatus.ACTIVE,
                last_heartbeat_at=now,
                heartbeat_count=1,
            )
        )
        await db.flush()
        return {
            "device_id": device_info["device_id"],
            "binding_token": fresh_token,
        }

    if existing_row.status == DeviceStatus.REVOKED:
        raise _revoked_device_binding_error(
            device_id=device_info["device_id"],
            plan=plan,
        )
    mismatched_fields = _device_identity_mismatched_fields(existing_row, device_info)
    if mismatched_fields:
        raise _device_identity_mismatch_error(
            device_id=device_info["device_id"],
            plan=plan,
            mismatched_fields=mismatched_fields,
        )
    token_to_return: str | None = None
    if existing_row.binding_token_hash:
        if not binding_token:
            raise _device_binding_token_required_error(
                device_id=device_info["device_id"],
                plan=plan,
            )
        if not hmac.compare_digest(
            existing_row.binding_token_hash,
            _hash_binding_token(binding_token),
        ):
            raise _invalid_device_binding_token_error(
                device_id=device_info["device_id"],
                plan=plan,
            )
    else:
        token_to_return = _generate_binding_token()
    await db.execute(
        update(DeviceRegistration)
        .where(DeviceRegistration.id == existing_row.id)
        .values(
            status=DeviceStatus.ACTIVE,
            platform=device_info["platform"] or existing_row.platform,
            platform_version=(device_info["platform_version"] or existing_row.platform_version),
            hostname_hash=device_info["hostname_hash"] or existing_row.hostname_hash,
            sdk_version=device_info["sdk_version"] or existing_row.sdk_version,
            binding_token_hash=(
                _hash_binding_token(token_to_return)
                if token_to_return is not None
                else existing_row.binding_token_hash
            ),
            last_heartbeat_at=now,
            heartbeat_count=DeviceRegistration.heartbeat_count + 1,
        )
    )
    await db.flush()
    return {
        "device_id": device_info["device_id"],
        "binding_token": token_to_return,
    }


async def list_devices(org_id: uuid.UUID, db: AsyncSession) -> list[dict[str, object]]:
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
            "id": str(r.id),
            "device_id": r.device_id[:8] + "...",  # truncated for display
            "platform": r.platform,
            "platform_version": r.platform_version,
            "sdk_version": r.sdk_version,
            "status": r.status,
            "api_key_label": r.api_key.label if r.api_key else "",
            "api_key_prefix": r.api_key.key_prefix if r.api_key else "",
            "registered_at": r.created_at.isoformat() if r.created_at else None,
            "last_heartbeat_at": r.last_heartbeat_at.isoformat() if r.last_heartbeat_at else None,
            "heartbeat_count": r.heartbeat_count,
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
            DeviceRegistration.id == registration_id,
            DeviceRegistration.org_id == org_id,
        )
        .values(status=DeviceStatus.REVOKED)
        .returning(DeviceRegistration.id)
    )
    await db.commit()
    return result.scalar_one_or_none() is not None
