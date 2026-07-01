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
import os
import secrets
import time
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict

import structlog
from fastapi import Request
from sqlalchemy import func, nulls_last, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api_server.models.api_key import APIKey, APIKeyStatus
from apps.api_server.models.device import (
    DEVICE_BINDING_TOKEN_HASH_MAX_LENGTH,
    DEVICE_HOSTNAME_HASH_MAX_LENGTH,
    DEVICE_ID_MAX_LENGTH,
    DEVICE_PLATFORM_MAX_LENGTH,
    DEVICE_PLATFORM_VERSION_MAX_LENGTH,
    DEVICE_PUBKEY_THUMBPRINT_MAX_LENGTH,
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
        # License renewal carries its OWN device proof (keypair proof-of-possession), so it
        # is exempt from the hosted binding-token mechanism — same as register/heartbeat.
        "/v1/license/challenge",
        "/v1/license/renew",
    }
)
_DEVICE_INFO_LENGTH_LIMITS: tuple[tuple[str, int], ...] = (
    ("device_id", DEVICE_ID_MAX_LENGTH),
    ("platform", DEVICE_PLATFORM_MAX_LENGTH),
    ("platform_version", DEVICE_PLATFORM_VERSION_MAX_LENGTH),
    ("hostname_hash", DEVICE_HOSTNAME_HASH_MAX_LENGTH),
    ("sdk_version", DEVICE_SDK_VERSION_MAX_LENGTH),
    ("device_pubkey_thumbprint", DEVICE_PUBKEY_THUMBPRINT_MAX_LENGTH),
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


def _check_device_key_binding(existing_row: DeviceRegistration, incoming_thumbprint: str) -> None:
    """Enforce cryptographic device binding on re-registration.

    Bound on first keypair-aware registration; thereafter the same device_id presenting a
    DIFFERENT non-empty thumbprint is a clone attempt and is rejected. Empty incoming (legacy
    fingerprint-only client) is allowed and never re-binds.
    """
    bound = (existing_row.device_pubkey_thumbprint or "").strip()
    incoming = (incoming_thumbprint or "").strip()
    if bound and incoming and bound != incoming:
        raise ValueError(
            "Device key mismatch: this device id is already activated on a different device "
            "key. Re-binding requires revoking the existing activation first."
        )


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


# ── Install/registration rate-limit (abuse protection on NEW device installs, not usage) ──────────
# Dynamic per plan; 0 = unlimited. Generous so a legitimate fleet scale-up + normal hardware swaps
# never trip it — this only stops scripted hammering of the register endpoint. Tune globally with
# ALGENTA_DEVICE_INSTALLS_PER_HOUR. Re-registering an EXISTING device (license refresh) updates the
# row in place and is NOT counted; only brand-new device registrations count toward the budget.
_DEFAULT_INSTALLS_PER_HOUR: dict[str, int] = {
    "free": 20,        # free is cloud-only (cannot register a local device) — a safety net only
    "pro": 100,
    "team": 200,
    "enterprise": 0,   # unlimited — large fleets / big autoscaling events
}
_INSTALL_RATE_WINDOW_SECONDS = 3600


def installs_per_hour(plan: str) -> int:
    """Dynamic per-plan new-device install budget (0 = unlimited). A global env override wins."""
    override = os.environ.get("ALGENTA_DEVICE_INSTALLS_PER_HOUR")
    if override is not None:
        try:
            return max(0, int(override.strip()))
        except ValueError:
            pass
    return _DEFAULT_INSTALLS_PER_HOUR.get(plan, 100)


async def recent_new_registration_count(
    api_key_id: uuid.UUID,
    db: AsyncSession,
    *,
    window_seconds: int = _INSTALL_RATE_WINDOW_SECONDS,
) -> int:
    """Count NEW device registrations created for this key within the rolling window. Refreshes of an
    existing device update the row in place (created_at unchanged) and are therefore excluded."""
    cutoff = datetime.now(UTC) - timedelta(seconds=window_seconds)
    result = await db.execute(
        select(func.count()).where(
            DeviceRegistration.api_key_id == api_key_id,
            DeviceRegistration.created_at >= cutoff,
        )
    )
    return result.scalar_one() or 0


# ── Active-node-cap enforcement (heartbeat-based; the cap counts only RECENTLY-ACTIVE nodes) ──
# The device cap (device_limit) is normally counted against EVERY non-revoked device ever
# registered. With this enforcement on, the cap is counted against only nodes that have
# heartbeated within the active window — so a decommissioned / scaled-down node (its heartbeat
# stops) automatically frees its slot after the window, while running MORE than the cap
# CONCURRENTLY is still blocked. This is what makes "I have 3 devices and want to drop 1" work
# without a manual revoke (and without cheating the cap), and what stops fleet abuse on
# cloud/server (AWS) deployments. The client heartbeats every 24h (apps/runtime/metering.py) and
# the offline grace is 14 days, so the window sits between the two: > one heartbeat interval (a
# node that missed a single beat still counts) and < the offline grace. Fully dynamic;
# default-DARK (env opt-in) so today's all-non-revoked semantics are unchanged until the flip.
# Free tier cannot register a device at all, so this never touches the always-free path.
_ACTIVE_NODE_WINDOW_SECONDS = 3 * 86_400  # 3 days


def _env_truthy(name: str) -> bool:
    """A flag env var is on when set to a recognized truthy token (1/true/yes/on)."""
    val = os.environ.get(name)
    return val is not None and val.strip().lower() in {"1", "true", "yes", "on"}


def active_node_cap_enforced() -> bool:
    """Whether the device cap is counted against only recently-active (heartbeating) nodes.

    Default OFF — when off, the cap counts every non-revoked device (today's behavior).
    """
    return _env_truthy("ALGENTA_ENFORCE_ACTIVE_NODE_CAP")


def active_node_window_seconds() -> int:
    """Rolling window within which a node must have heartbeated to still count against the cap.

    Override with ALGENTA_ACTIVE_NODE_WINDOW_SECONDS (floored at 60s so it can never be 0/negative).
    """
    override = os.environ.get("ALGENTA_ACTIVE_NODE_WINDOW_SECONDS")
    if override is not None:
        try:
            return max(60, int(override.strip()))
        except ValueError:
            pass
    return _ACTIVE_NODE_WINDOW_SECONDS


async def active_node_count(
    api_key_id: uuid.UUID,
    db: AsyncSession,
    *,
    window_seconds: int | None = None,
    exclude_device_id: str | None = None,
) -> int:
    """Count non-revoked devices that have heartbeated within the active window.

    A node whose heartbeat has lapsed (decommissioned / scaled down) no longer counts, freeing its
    slot. A device that has never heartbeated (NULL last_heartbeat_at) does not count — but every
    register and heartbeat stamps last_heartbeat_at, so a healthy node always has a recent value.

    ``exclude_device_id`` omits one device from the count — used by the admission gate so a device's
    own idempotent refresh never blocks itself (it asks "are the OTHER active nodes already full?").
    """
    window = window_seconds if window_seconds is not None else active_node_window_seconds()
    cutoff = datetime.now(UTC) - timedelta(seconds=window)
    conditions = [
        DeviceRegistration.api_key_id == api_key_id,
        DeviceRegistration.status != DeviceStatus.REVOKED,
        DeviceRegistration.last_heartbeat_at.is_not(None),
        DeviceRegistration.last_heartbeat_at >= cutoff,
    ]
    if exclude_device_id is not None:
        conditions.append(DeviceRegistration.device_id != exclude_device_id)
    result = await db.execute(select(func.count()).where(*conditions))
    return result.scalar_one() or 0


async def _device_is_active(
    api_key_id: uuid.UUID,
    db: AsyncSession,
    device_id: str,
    *,
    window_seconds: int | None = None,
) -> bool:
    """Whether this device currently holds a live slot (non-revoked + heartbeated in the window).

    Used by the admission gate to never evict a node that is already running — only NEW or
    returning-stale devices are blocked when the cap is full.
    """
    window = window_seconds if window_seconds is not None else active_node_window_seconds()
    cutoff = datetime.now(UTC) - timedelta(seconds=window)
    result = await db.execute(
        select(func.count()).where(
            DeviceRegistration.api_key_id == api_key_id,
            DeviceRegistration.device_id == device_id,
            DeviceRegistration.status != DeviceStatus.REVOKED,
            DeviceRegistration.last_heartbeat_at.is_not(None),
            DeviceRegistration.last_heartbeat_at >= cutoff,
        )
    )
    return (result.scalar_one() or 0) > 0


async def effective_node_count(api_key_id: uuid.UUID, db: AsyncSession) -> int:
    """The count the device cap is enforced/reported against.

    Active-node count when active-node-cap enforcement is on, else the legacy all-non-revoked count.
    The single chokepoint every cap counter + count report goes through (the register cap, the
    re-register and heartbeat status reports, the hosted-API binding cap, and the license-renew
    report) so they never disagree on the semantics in force.
    """
    if active_node_cap_enforced():
        return await active_node_count(api_key_id, db)
    return await _active_device_count(api_key_id, db)


async def node_admission_block_count(
    api_key_id: uuid.UUID,
    db: AsyncSession,
    *,
    device_id: str,
    device_limit: int,
) -> int | None:
    """Gate for any path that would (re)mark a device ACTIVE — register, re-register, heartbeat,
    hosted-API bind, license renew.

    Returns the count of OTHER currently-active nodes when admitting/refreshing ``device_id`` would
    push the concurrent active set past ``device_limit`` (so the caller rejects with 402
    ``device_limit_reached`` or withholds the slot); otherwise None.

    This is what turns the cap into a true CONCURRENT ceiling rather than a registration-only gate:
    a node that lapsed and "freed its slot" cannot silently reclaim it once another node has taken
    it. Returns None when enforcement is OFF or the cap is unlimited — the revival paths then behave
    exactly as before (no concurrency gate), preserving default-dark.

    A device that ALREADY holds a live slot is never blocked (we never evict a running node — only
    NEW or returning-stale devices are gated). So when the active set already sits at/over the cap
    (e.g. the moment enforcement is flipped on for a fleet that exceeds it), the running nodes keep
    refreshing and the set drains naturally as nodes go stale, rather than all being shed at once.
    """
    if not active_node_cap_enforced() or device_limit <= 0:
        return None
    others_active = await active_node_count(api_key_id, db, exclude_device_id=device_id)
    if others_active < device_limit:
        return None
    # Cap is full of OTHER live nodes. Admit only if THIS device already holds a live slot; block a
    # brand-new or returning-stale device from joining over the cap.
    if await _device_is_active(api_key_id, db, device_id):
        return None
    return others_active


def _activation_id(org_id: str, device_id: str) -> str:
    """Deterministic, stable, opaque activation id for an (org, device).

    ``uuid5(org_id, device_id)`` — stable across license renewals (so the CRL can name a
    device once), org-scoped, and reversible to nothing about the machine. FROZEN: changing
    this derivation orphans every issued activation_id. Falls back to a NIL-namespace form
    only if org_id is not a UUID (shouldn't happen — it's always ``str(org.id)``).
    """
    try:
        namespace = uuid.UUID(str(org_id))
    except (ValueError, AttributeError, TypeError):
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{org_id}:{device_id}"))
    return str(uuid.uuid5(namespace, device_id))


# Products whose on-device runtime verifies the platform RS256 (ver:2) license OFFLINE and therefore MUST be
# signed by the shared cf_worker (license.algenta.ai), NOT the legacy dev_hmac HS256. Telys is the first such
# externally-consumed product; **Algenta external users follow the SAME onboarding model next** (pip/login →
# API key → device → offline RS256 license) — so this is deliberately product-generic, not telys-only. Enable a
# product by adding it here or via settings.rs256_license_products (env-overridable, no code change). Codna and
# Algenta's *internal* consumers still verify HS256, so they keep the global default until their runtime verifies
# RS256 — flipping them before then would break live installs. This is why selection is per-product, not global.
_RS256_LICENSE_PRODUCTS: frozenset[str] = frozenset({"telys"})

# The cf_worker (license.algenta.ai) signs claims VERBATIM and enforces its own policy: iss must be the platform
# issuer, aud must be the platform-runtime audience, and a standard `exp` is REQUIRED and capped (worker.js
# MAX_TTL_SECONDS = 90d). Telys.verify independently requires the same iss + an accepted aud + a finite exp. So a
# license routed to cf_worker MUST carry these exact claims (the legacy dev_hmac/Codna path keeps
# iss=_JWT_ISSUER + expires_at and is never reshaped). Keep in sync with infra/cloudflare/license-signer/worker.js
# and telys-sdk telys/verify.py (DEFAULT_LICENSE_ISSUER / DEFAULT_LICENSE_AUDIENCES).
_PLATFORM_LICENSE_ISSUER = "https://license.algenta.ai"
_PLATFORM_LICENSE_AUDIENCE = "algenta-runtime"
_CF_WORKER_MAX_TTL_SECONDS = 89 * 86400  # stay safely under the worker's 90-day ceiling (clock-skew margin)


def _rs256_products(settings: Any) -> set[str]:
    """The set of products whose license is signed by the cf_worker (RS256). Config-extensible via
    settings.rs256_license_products (comma-separated env string or an iterable); default = Telys only."""
    configured = getattr(settings, "rs256_license_products", None)
    if isinstance(configured, str):
        return {p.strip() for p in configured.split(",") if p.strip()}
    if configured:  # an explicit iterable (e.g. a set from a caller/test)
        return set(configured)
    return set(_RS256_LICENSE_PRODUCTS)


def _use_cf_worker_signer(plan: str, settings: Any) -> bool:
    """True when this plan's product(s) must be signed by the shared cf_worker (RS256, license.algenta.ai).

    An externally-consumed product whose on-device runtime verifies the platform license OFFLINE (Telys now;
    Algenta external next) routes here; everyone else stays on dev_hmac/HS256 so Codna/Algenta internal consumers
    are untouched. Requires cf_worker to actually be configured (``license_signer_url``), else we fall back to
    HS256 so dev/test never break. This is the SINGLE source of truth for RS256 routing — the global
    ``license_signer_backend`` deliberately does NOT widen it (that would silently flip Codna/Algenta to RS256)."""
    if not (getattr(settings, "license_signer_url", "") or ""):
        return False
    try:
        from apps.api_server.services.entitlement_service import resolve_entitlement

        products = set(getattr(resolve_entitlement(plan), "products", {}) or {})
    except Exception:  # unknown/legacy plan: fall back to the plan-name signal, never crash issuance
        products = {"telys"} if str(plan or "").startswith("telys") else set()
    return bool(products & _rs256_products(settings))


def _issue_license_jwt(
    device_id: str,
    api_key_prefix: str,
    plan: str,
    device_limit: int,
    org_id: str,
    api_key_expires_at: datetime | None = None,
    device_pubkey_thumbprint: str = "",
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
    license_id = str(uuid.uuid4())
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
        "ver": 2,
        # Identity claims (additive, back-compat): the runtime already parses these.
        # activation_id is stable per (org, device) — the CRL revokes by it; license_id/jti
        # are per-issuance (audit / future per-token revocation). device_pubkey_thumbprint
        # echoes the bound device key into the license.
        "license_id": license_id,
        "jti": license_id,
        "activation_id": _activation_id(org_id, device_id),
        "device_pubkey_thumbprint": device_pubkey_thumbprint,
    }
    # Enrich with the ver:2 ENTITLEMENT claim shape (products{name:{tier,features}} + capacity caps) from the
    # resolved tier — required by the Telys verifier (products.telys) and for product feature gating. Additive
    # merge — never drops the identity claims.
    #
    # Gating is product-aware so Telys works WITHOUT a global flip:
    #   * Telys plans (telys_developer/pro/team) ALWAYS emit the products map — a paid Telys customer's local
    #     runtime fails closed (no products.telys → no features) without it, and the Telys verifier is the only
    #     consumer of a telys_* license, so this cannot affect Codna/Algenta.
    #   * All other plans stay gated on license_v2_issuance (default OFF): off = legacy claim set with NO products
    #     map, so existing Codna/Algenta consumers are unaffected; flip ON only after confirming every consumer
    #     handles a products map (see telys docs/SHARED-PLATFORM-INTEGRATION.md).
    from apps.api_server.config import get_settings

    settings = get_settings()
    _is_telys_plan = str(plan or "").startswith("telys")
    if _is_telys_plan or settings.license_v2_issuance:
        from apps.api_server.services.entitlement_service import resolve_entitlement, to_license_claims

        payload.update(to_license_claims(resolve_entitlement(plan)))

    # PER-PRODUCT signing. Externally-consumed products whose runtime verifies RS256 OFFLINE (Telys now, Algenta
    # external next) are signed by the shared cf_worker (license.algenta.ai); everyone else is signed with an
    # EXPLICIT dev_hmac (HS256) — never the ambient global backend — so setting LICENSE_SIGNER_BACKEND=cf_worker
    # can't silently flip Codna/Algenta to RS256 (which their HS256 runtimes would reject). See _use_cf_worker_signer.
    from apps.api_server.services.license_signer import get_license_signer

    if _use_cf_worker_signer(plan, settings):
        # The cf_worker signs verbatim + enforces policy, and telys.verify enforces the same: platform iss, an
        # accepted aud, and a finite `exp` capped at the worker's TTL ceiling. Shape ONLY this RS256 path — the
        # Codna/Algenta dev_hmac path above keeps iss=_JWT_ISSUER + expires_at exactly as before.
        capped_exp = min(effective_expires_at, now + _CF_WORKER_MAX_TTL_SECONDS)
        payload["iss"] = _PLATFORM_LICENSE_ISSUER
        payload["aud"] = _PLATFORM_LICENSE_AUDIENCE
        payload["exp"] = capped_exp
        payload["expires_at"] = capped_exp  # keep the token internally consistent (verify prefers exp)
        return get_license_signer(backend="cf_worker").sign(payload)
    return get_license_signer(backend="dev_hmac").sign(payload)


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
            device_pubkey_thumbprint=_device_info_value(device_info, "device_pubkey_thumbprint"),
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
        incoming_thumbprint = _device_info_value(device_info, "device_pubkey_thumbprint")
        _check_device_key_binding(existing_row, incoming_thumbprint)
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
                device_pubkey_thumbprint=(
                    incoming_thumbprint or existing_row.device_pubkey_thumbprint
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
        device_pubkey_thumbprint=_device_info_value(device_info, "device_pubkey_thumbprint"),
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
        # New device binding on the live hosted-API path. Count via the shared chokepoint so this
        # plane honors the same active-node semantics as register/heartbeat (a freed slot is freed
        # here too when enforcement is on; all-non-revoked when off).
        current_count = await effective_node_count(api_key_row.id, db)
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
    # Concurrent-cap gate: an already-active device re-binding is admitted (it is excluded from the
    # count), but a STALE device returning to do work while other live nodes already fill the cap is
    # rejected here — this is the true concurrent ceiling on the path that actually serves requests.
    # No-op when enforcement is off (returns None), so legacy bind behavior is unchanged.
    blocked_count = await node_admission_block_count(
        api_key_row.id, db, device_id=device_info["device_id"], device_limit=device_limit
    )
    if blocked_count is not None:
        raise _device_limit_error(
            api_key_row=api_key_row,
            plan=plan,
            device_limit=device_limit,
            device_count=blocked_count,
        )
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


async def list_devices_with_activity(
    org_id: uuid.UUID,
    db: AsyncSession,
    *,
    window_seconds: int | None = None,
) -> dict[str, object]:
    """Dashboard view of an org's devices for self-service subscription management.

    Returns the same per-device rows as :func:`list_devices`, each annotated with ``active`` (it has
    heartbeated within the active window — i.e. holds a seat now vs. is idle/decommissioned), plus a
    seat summary (``total`` registered, ``active`` live) so a dashboard can show how many seats are
    live and which idle device to revoke. Read-only; the active window mirrors the cap window.
    """
    window = window_seconds if window_seconds is not None else active_node_window_seconds()
    cutoff = datetime.now(UTC) - timedelta(seconds=window)
    devices = await list_devices(org_id, db)
    active = 0
    for d in devices:
        hb = d.get("last_heartbeat_at")
        is_active = False
        if isinstance(hb, str) and hb:
            try:
                is_active = datetime.fromisoformat(hb) >= cutoff
            except ValueError:
                is_active = False
        d["active"] = is_active
        active += 1 if is_active else 0
    return {
        "devices": devices,
        "total": len(devices),
        "active": active,
        "active_window_seconds": window,
    }


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
        # Explicit updated_at bump so the CRL version (max updated_at over REVOKED rows)
        # advances deterministically on every revoke.
        .values(status=DeviceStatus.REVOKED, updated_at=datetime.now(UTC))
        .returning(DeviceRegistration.id)
    )
    await db.commit()
    return result.scalar_one_or_none() is not None


async def build_revocation_payload(db: AsyncSession) -> dict[str, object]:
    """Build the (unsigned) CRL payload from REVOKED device rows.

    Each revoked device maps to its stable ``activation_id`` (uuid5(org, device) — matches the
    license claim). ``version`` is the max revoke time (epoch) so a runtime can detect changes;
    ``valid_until`` bounds how long a fetched CRL may be trusted offline. The caller signs this
    via the license signer so the runtime can verify it with the same kid/secret as licenses.
    """
    rows = (
        await db.execute(
            select(
                DeviceRegistration.org_id,
                DeviceRegistration.device_id,
                DeviceRegistration.updated_at,
            ).where(DeviceRegistration.status == DeviceStatus.REVOKED)
        )
    ).all()
    revoked: list[dict[str, object]] = []
    version = 0
    for org_id, device_id, updated_at in rows:
        revoked_at = int(updated_at.timestamp()) if updated_at else 0
        version = max(version, revoked_at)
        revoked.append(
            {"activation_id": _activation_id(str(org_id), device_id), "revoked_at": revoked_at}
        )
    now = int(time.time())
    return {
        "revoked": revoked,
        "version": version,
        "issued_at": now,
        "valid_until": now + 86400,
        "iss": _JWT_ISSUER,
        "sub": "device-license-revocation-list",
    }


async def revoke_org_devices(org_id: uuid.UUID, db: AsyncSession) -> int:
    """Revoke ALL non-revoked devices for an org (e.g. on subscription cancellation).

    Org-scoped bulk UPDATE; bumps updated_at so the CRL version advances once for the batch.
    FLUSH-ONLY (no commit) — the caller commits atomically (e.g. with the Stripe event ledger
    row). Idempotent: already-revoked rows are excluded, so a replay revokes 0.
    """
    result = await db.execute(
        update(DeviceRegistration)
        .where(
            DeviceRegistration.org_id == org_id,
            DeviceRegistration.status != DeviceStatus.REVOKED,
        )
        .values(status=DeviceStatus.REVOKED, updated_at=datetime.now(UTC))
        .returning(DeviceRegistration.id)
    )
    return len(result.all())


async def revoke_excess_org_devices(org_id: uuid.UUID, keep_limit: int, db: AsyncSession) -> int:
    """Revoke an org's non-revoked devices beyond ``keep_limit``, keeping the most-recently-active.

    For a paid→paid downgrade where the device cap shrank. ``keep_limit <= 0`` is a no-op (0 =
    unlimited / enterprise — never revoke). Keeps the ``keep_limit`` devices with the most recent
    ``last_heartbeat_at`` (NULLs — never-heartbeated — revoked first). Org-scoped, FLUSH-ONLY.
    """
    if keep_limit <= 0:
        return 0
    ids = (
        (
            await db.execute(
                select(DeviceRegistration.id)
                .where(
                    DeviceRegistration.org_id == org_id,
                    DeviceRegistration.status != DeviceStatus.REVOKED,
                )
                .order_by(nulls_last(DeviceRegistration.last_heartbeat_at.desc()))
            )
        )
        .scalars()
        .all()
    )
    excess = list(ids[keep_limit:])
    if not excess:
        return 0
    await db.execute(
        update(DeviceRegistration)
        .where(DeviceRegistration.id.in_(excess))
        .values(status=DeviceStatus.REVOKED, updated_at=datetime.now(UTC))
    )
    return len(excess)
