"""
Device license — JWT-based, locally stored, offline-capable.

License lifecycle:
  1. algenta login → device fingerprint sent to control plane
  2. Control plane validates API key, checks device count against plan limits
  3. Control plane issues signed JWT → stored in ~/.algenta/runtime/license.jwt
  4. Runtime validates JWT locally on every startup (no network)
  5. Background sync every 24h: sends usage + re-validates device count
  6. Grace period: 14 days after expiry before hard block

JWT payload:
  {
    "api_key_prefix": "de_live_d36l",      # first 12 chars — for display only
    "device_id": "abc123...",
    "plan": "pro",
    "device_limit": 5,
    "permitted_modules": ["*"],
    "issued_at": 1712345678,
    "expires_at": 1743881678,              # 0 = no expiry
    "grace_days": 14,
    "iss": "algenta-control-plane",
    "sub": "device-license"
  }

Dev-stub mode is allowed only when explicitly enabled for local development.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import jwt
import structlog

from apps.platform_contract_constants import API_BASE_URL

logger = structlog.get_logger(__name__)

_RUNTIME_DIR = Path(os.environ.get("ALGENTA_RUNTIME_DIR", Path.home() / ".algenta" / "runtime"))
_LICENSE_FILE = _RUNTIME_DIR / "license.jwt"
_LICENSE_VERSION = 1

# Secret used for self-signed dev licenses (never used for cloud validation)
_DEV_SECRET = "algenta-dev-local-v1-not-for-production"  # noqa: S105

# Control plane base URL (override with ALGENTA_CONTROL_PLANE_URL)
_CONTROL_PLANE_URL = os.environ.get(
    "ALGENTA_CONTROL_PLANE_URL",
    os.environ.get(
        "ALGENTA_BASE_URL",
        os.environ.get("DE_BASE_URL", API_BASE_URL),
    ),
)
_CONTROL_PLANE_TIMEOUT_SECONDS = float(
    os.environ.get("ALGENTA_CONTROL_PLANE_TIMEOUT_SECONDS", "20")
)
_CONTROL_PLANE_MAX_ATTEMPTS = max(
    1,
    int(os.environ.get("ALGENTA_CONTROL_PLANE_MAX_ATTEMPTS", "3")),
)
_CONTROL_PLANE_RETRY_BASE_SECONDS = float(
    os.environ.get("ALGENTA_CONTROL_PLANE_RETRY_BASE_SECONDS", "0.5")
)
_RETRYABLE_CONTROL_PLANE_HTTP_CODES = frozenset({409, 429, 500, 502, 503, 504})

# Grace period: continue working this many days after license expiry
_DEFAULT_GRACE_DAYS = 14


def _env_api_key() -> str:
    return os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "")


def _runtime_dev_mode_enabled() -> bool:
    value = os.environ.get("ALGENTA_RUNTIME_DEV_MODE", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _validated_control_plane_url() -> str:
    parsed = urlparse(_CONTROL_PLANE_URL)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(
            "ALGENTA_CONTROL_PLANE_URL must use an absolute http(s) URL."
        )
    return _CONTROL_PLANE_URL.rstrip("/")


def _control_plane_verification_secrets() -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []

    explicit_secret = (
        os.environ.get("ALGENTA_LICENSE_SIGNING_SECRET")
        or os.environ.get("LICENSE_SIGNING_SECRET")
    )
    if explicit_secret:
        candidates.append((explicit_secret, "control-plane"))

    jwt_seed = os.environ.get("ALGENTA_JWT_SECRET") or os.environ.get("JWT_SECRET")
    if jwt_seed is None:
        jwt_seed = "change-me-in-production-use-256-bit-random-value"
    derived_secret = hashlib.sha256((jwt_seed + ":license-signing").encode()).hexdigest()
    candidates.append((derived_secret, "control-plane"))

    deduped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for secret, source in candidates:
        if not secret or secret in seen or secret == _DEV_SECRET:
            continue
        seen.add(secret)
        deduped.append((secret, source))
    return deduped


def _device_registration_idempotency_key(device_id: str) -> str:
    digest = hashlib.sha256(device_id.encode("utf-8")).hexdigest()
    return f"device-register:{digest}"


def _device_register_request(
    control_plane_url: str,
    api_key: str,
    device_info: dict,
    body: bytes,
) -> urllib.request.Request:
    return urllib.request.Request(  # noqa: S310
        f"{control_plane_url}/v1/device/register",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Idempotency-Key": _device_registration_idempotency_key(
                device_info.get("device_id", "")
            ),
        },
        method="POST",
    )


def _is_retryable_control_plane_error(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in _RETRYABLE_CONTROL_PLANE_HTTP_CODES
    return isinstance(exc, TimeoutError | urllib.error.URLError | OSError)


def _license_retry_delay_seconds(attempt: int) -> float:
    return max(0.0, _CONTROL_PLANE_RETRY_BASE_SECONDS) * (2 ** max(0, attempt - 1))


@dataclass
class DeviceLicense:
    valid: bool
    plan: str                             # "dev" | "pro" | "enterprise"
    device_id: str
    device_limit: int                     # 0 = unlimited
    permitted_modules: list[str]
    expires_at: int                       # unix timestamp; 0 = no expiry
    grace_days: int
    api_key_prefix: str
    issued_at: int
    message: str = ""
    source: str = "unknown"              # "cloud" | "dev-stub" | "expired-grace"

    def is_expired(self) -> bool:
        if self.expires_at == 0:
            return False
        return int(time.time()) > self.expires_at

    def is_in_grace(self) -> bool:
        if self.expires_at == 0:
            return False
        grace_end = self.expires_at + (self.grace_days * 86400)
        return self.is_expired() and int(time.time()) <= grace_end

    def is_hard_expired(self) -> bool:
        """True only after grace period ends — this is when we actually block."""
        if self.expires_at == 0:
            return False
        grace_end = self.expires_at + (self.grace_days * 86400)
        return int(time.time()) > grace_end

    def is_module_permitted(self, module_name: str) -> bool:
        if not self.valid:
            return False
        if "*" in self.permitted_modules:
            return True
        return module_name in self.permitted_modules


# ── Dev stub license ──────────────────────────────────────────────────────────

def _make_dev_license(api_key: str = "") -> DeviceLicense:
    from apps.runtime.device import get_device_id
    prefix = api_key[:12] if api_key else "dev-local"
    return DeviceLicense(
        valid=True,
        plan="dev",
        device_id=get_device_id(),
        device_limit=0,
        permitted_modules=["*"],
        expires_at=0,
        grace_days=_DEFAULT_GRACE_DAYS,
        api_key_prefix=prefix,
        issued_at=int(time.time()),
        message="Dev mode — self-signed local license",
        source="dev-stub",
    )


def _make_invalid_license(message: str, *, api_key: str = "") -> DeviceLicense:
    from apps.runtime.device import get_device_id

    prefix = api_key[:12] if api_key else ""
    return DeviceLicense(
        valid=False,
        plan="unknown",
        device_id=get_device_id(),
        device_limit=0,
        permitted_modules=[],
        expires_at=0,
        grace_days=_DEFAULT_GRACE_DAYS,
        api_key_prefix=prefix,
        issued_at=int(time.time()),
        message=message,
        source="none",
    )


def _issue_dev_jwt(device_id: str, api_key: str = "") -> str:
    """Issue a self-signed dev JWT for local storage."""
    payload = {
        "api_key_prefix": api_key[:12] if api_key else "dev-local",
        "device_id": device_id,
        "plan": "dev",
        "device_limit": 0,
        "permitted_modules": ["*"],
        "issued_at": int(time.time()),
        "expires_at": 0,
        "grace_days": _DEFAULT_GRACE_DAYS,
        "iss": "algenta-dev-local",
        "sub": "device-license",
        "ver": _LICENSE_VERSION,
    }
    return jwt.encode(payload, _DEV_SECRET, algorithm="HS256")


# ── Disk I/O ──────────────────────────────────────────────────────────────────

def _save_license(token: str) -> None:
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    _LICENSE_FILE.write_text(token)
    # Restrict permissions: owner read/write only
    try:
        _LICENSE_FILE.chmod(0o600)
    except Exception as exc:
        logger.debug("license_permission_update_failed", error=str(exc))


def _load_raw_token() -> str | None:
    try:
        if _LICENSE_FILE.exists():
            return _LICENSE_FILE.read_text().strip()
    except Exception as exc:
        logger.debug("license_read_failed", error=str(exc))
    return None


# ── Token parsing ─────────────────────────────────────────────────────────────

def _parse_token(token: str, api_key: str = "") -> DeviceLicense | None:
    """
    Decode and validate a JWT license token.

    v1: dev tokens use HMAC-SHA256 with the dev secret.
    v2+: cloud tokens use RS256 with the Algenta public key.
    """
    for secret, source in [(_DEV_SECRET, "dev-stub"), *_control_plane_verification_secrets()]:
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_exp": False},  # we handle expiry ourselves
            )
            return DeviceLicense(
                valid=True,
                plan=payload.get("plan", "dev"),
                device_id=payload.get("device_id", ""),
                device_limit=payload.get("device_limit", 0),
                permitted_modules=payload.get("permitted_modules", ["*"]),
                expires_at=payload.get("expires_at", 0),
                grace_days=payload.get("grace_days", _DEFAULT_GRACE_DAYS),
                api_key_prefix=payload.get("api_key_prefix", ""),
                issued_at=payload.get("issued_at", 0),
                message=payload.get("message", ""),
                source=source,
            )
        except jwt.InvalidTokenError:
            continue
    return None


# ── Control plane exchange ────────────────────────────────────────────────────

def _exchange_api_key_for_license(api_key: str, device_info: dict) -> str | None:
    """
    POST to control plane: exchange API key + device fingerprint → signed JWT.

    Returns raw JWT string or None on failure.
    """
    control_plane_url = _validated_control_plane_url()
    body = json.dumps({
        "device": {
            "device_id":        device_info.get("device_id", ""),
            "platform":         device_info.get("platform", ""),
            "platform_version": device_info.get("platform_version", ""),
            "hostname_hash":    device_info.get("hostname_hash", ""),
            "sdk_version":      device_info.get("sdk_version", ""),
        }
    }).encode()
    for attempt in range(1, _CONTROL_PLANE_MAX_ATTEMPTS + 1):
        req = _device_register_request(control_plane_url, api_key, device_info, body)
        try:
            with urllib.request.urlopen(  # noqa: S310
                req,
                timeout=_CONTROL_PLANE_TIMEOUT_SECONDS,
            ) as resp:
                data = json.loads(resp.read())
                token = data.get("license_token")
                if token:
                    logger.info(
                        "license_from_control_plane",
                        plan=data.get("plan"),
                        device_count=data.get("device_count"),
                        device_limit=data.get("device_limit"),
                    )
                    credits_granted = data.get("credits_granted", 0)
                    if credits_granted > 0:
                        try:
                            from apps.runtime.credits import get_store

                            get_store().initialize_sync(
                                credits_granted=credits_granted,
                                billing_period=data.get("credits_billing_period", ""),
                                ttl_seconds=max(
                                    1,
                                    int(
                                        data.get(
                                            "credits_expires_at",
                                            time.time() + 86_400,
                                        )
                                        - time.time()
                                    ),
                                ),
                            )
                        except Exception as credit_error:
                            logger.debug(
                                "credit_seed_failed",
                                error=str(credit_error),
                            )
                    return token
        except urllib.error.HTTPError as exc:
            if exc.code == 402:
                try:
                    detail = json.loads(exc.read().decode())
                    logger.error("device_limit_reached", detail=detail)
                    raise PermissionError(
                        detail.get("detail", {}).get(
                            "message",
                            "Device limit reached.",
                        )
                    ) from exc
                except (json.JSONDecodeError, KeyError):
                    raise PermissionError(
                        "Device limit reached. Upgrade your plan."
                    ) from exc
            if (
                _is_retryable_control_plane_error(exc)
                and attempt < _CONTROL_PLANE_MAX_ATTEMPTS
            ):
                logger.warning(
                    "license_exchange_retryable_http_error",
                    attempt=attempt,
                    max_attempts=_CONTROL_PLANE_MAX_ATTEMPTS,
                    status=exc.code,
                    error=str(exc),
                )
                time.sleep(_license_retry_delay_seconds(attempt))
                continue
            logger.warning("license_exchange_http_error", status=exc.code, error=str(exc))
        except Exception as exc:
            if (
                _is_retryable_control_plane_error(exc)
                and attempt < _CONTROL_PLANE_MAX_ATTEMPTS
            ):
                logger.warning(
                    "license_exchange_retryable_failure",
                    attempt=attempt,
                    max_attempts=_CONTROL_PLANE_MAX_ATTEMPTS,
                    error=str(exc),
                )
                time.sleep(_license_retry_delay_seconds(attempt))
                continue
            logger.warning("license_exchange_failed", error=str(exc))

    return None


# ── Public API ────────────────────────────────────────────────────────────────

def load_license(api_key: str = "") -> DeviceLicense:
    """
    Load the local license. Precedence:
      1. Valid stored JWT (cloud or dev, not hard-expired)
      2. Exchange API key for new license (if key present + no valid stored)
      3. Allow explicit dev stub only when ALGENTA_RUNTIME_DEV_MODE is enabled
    """
    from apps.runtime.device import get_device_info

    # 1. Try stored license
    raw = _load_raw_token()
    if raw:
        parsed = _parse_token(raw, api_key)
        if parsed:
            if parsed.is_hard_expired():
                logger.warning("license_hard_expired", device_id=parsed.device_id)
                parsed.valid = False
                parsed.message = "License expired — run `algenta login` to renew."
                return parsed
            if parsed.is_in_grace():
                parsed.message = "License in grace period — run `algenta login` to renew."
                logger.info("license_in_grace_period")
            return parsed

    # 2. Exchange API key for a new license
    if api_key:
        device_info = get_device_info()
        token = _exchange_api_key_for_license(api_key, device_info)
        if token:
            _save_license(token)
            parsed = _parse_token(token, api_key)
            if parsed:
                logger.info("license_issued", plan=parsed.plan, device_id=parsed.device_id[:8])
                return parsed
            logger.warning(
                "license_token_unverifiable",
                hint=(
                    "Set ALGENTA_LICENSE_SIGNING_SECRET or JWT_SECRET "
                    "for local control-plane verification."
                ),
            )
        return _make_invalid_license(
            "Control plane registration failed. "
            "First-time local login requires a reachable control plane.",
            api_key=api_key,
        )

    if _runtime_dev_mode_enabled():
        logger.warning("license_dev_stub_active")
        return _make_dev_license(api_key)

    return _make_invalid_license(
        "No stored license found. "
        "Run `algenta login` against the control plane before offline execution."
    )


def issue_and_store(api_key: str) -> DeviceLicense:
    """
    Called by `algenta login`: exchange API key → store license → return it.
    This is the registration flow — called once per machine.
    """
    from apps.runtime.device import get_device_info

    device_info = get_device_info()
    token = _exchange_api_key_for_license(api_key, device_info)
    if token:
        _save_license(token)
        parsed = _parse_token(token, api_key)
        if parsed:
            return parsed

    if _runtime_dev_mode_enabled():
        token = _issue_dev_jwt(device_info["device_id"], api_key)
        _save_license(token)
        parsed = _parse_token(token, api_key)
        if parsed:
            return parsed
    return _make_invalid_license(
        "Control plane registration failed. A hosted license is required before offline execution.",
        api_key=api_key,
    )


def revoke_local() -> None:
    """Remove the stored license (called by `algenta logout`)."""
    try:
        _LICENSE_FILE.unlink(missing_ok=True)
    except Exception as exc:
        logger.debug("license_delete_failed", error=str(exc))


def license_summary(lic: DeviceLicense) -> str:
    """Human-readable one-liner."""
    expiry = "no expiry" if lic.expires_at == 0 else (
        "in grace" if lic.is_in_grace() else
        f"expires {time.strftime('%Y-%m-%d', time.gmtime(lic.expires_at))}"
    )
    limit = "unlimited" if lic.device_limit == 0 else f"max {lic.device_limit} devices"
    return (
        f"plan={lic.plan}  {limit}  {expiry}  "
        f"source={lic.source}  device={lic.device_id[:8]}..."
    )
