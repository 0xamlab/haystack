"""
Device license — JWT-based, locally stored, offline-capable.

License lifecycle:
  1. algenta login → device fingerprint sent to control plane
  2. Control plane validates API key, checks device count against plan limits
  3. Control plane issues signed JWT → stored in ~/.algenta/runtime/license.jwt
  4. Runtime validates JWT locally on every startup (no network)
  5. A persisted trusted clock keeps offline expiry checks non-decreasing
  6. Background sync every 24h: sends usage + re-validates device count
  7. Grace period: 14 days after expiry before hard block

JWT payload:
  {
    "api_key_prefix": "<API_KEY_PREFIX>",  # first 12 chars — for display only
    "device_id": "abc123...",
    "plan": "pro",
    "device_limit": 5,
    "permitted_modules": ["*"],
    "issued_at": 1712345678,
    "expires_at": 1743881678,              # effective local entitlement expiry
    "key_expires_at": 1743881678,          # backing API key expiry; 0 = no expiry
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
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

import jwt
import structlog

from apps.privacy_policy import is_algenta_owned_destination, policy_from_environment
from apps.runtime.privacy_guard import (
    RuntimeEgressPolicyDeniedError,
    runtime_urlopen,
    validated_runtime_egress_url,
)

logger = structlog.get_logger(__name__)

_LICENSE_VERSION = 1

# Secret used for self-signed dev licenses (never used for cloud validation)
_DEV_SECRET = "algenta-dev-local-v1-not-for-production"  # noqa: S105

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


def _runtime_dir() -> Path:
    return Path(os.environ.get("ALGENTA_RUNTIME_DIR", Path.home() / ".algenta" / "runtime"))


def _license_file(runtime_dir: Path | None = None) -> Path:
    base_dir = _runtime_dir() if runtime_dir is None else runtime_dir
    return base_dir / "license.jwt"


def _env_api_key() -> str:
    return os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "")


def _runtime_dev_mode_enabled() -> bool:
    value = os.environ.get("ALGENTA_RUNTIME_DEV_MODE", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _local_license_required() -> bool:
    return policy_from_environment().require_local_license


def _offline_license_public_keys() -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []

    for env_name in ("ALGENTA_LOCAL_LICENSE_PUBLIC_KEY", "ALGENTA_LICENSE_PUBLIC_KEY"):
        value = os.environ.get(env_name, "").strip()
        if value:
            candidates.append((value, "offline-local"))

    for env_name in ("ALGENTA_LOCAL_LICENSE_PUBLIC_KEY_FILE", "ALGENTA_LICENSE_PUBLIC_KEY_FILE"):
        path_value = os.environ.get(env_name, "").strip()
        if not path_value:
            continue
        try:
            key_text = Path(path_value).expanduser().read_text().strip()
        except OSError as exc:
            logger.warning("offline_license_public_key_unreadable", path=path_value, error=str(exc))
            continue
        if key_text:
            candidates.append((key_text, "offline-local"))

    deduped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key_text, source in candidates:
        if key_text in seen:
            continue
        seen.add(key_text)
        deduped.append((key_text, source))
    return deduped


def _validated_control_plane_url(
    *, surface: str = "runtime_control_plane", record: bool = True
) -> str:
    policy = policy_from_environment()
    control_plane_url = policy.control_plane_url.rstrip("/")
    if not control_plane_url:
        raise ValueError(
            "ALGENTA_CONTROL_PLANE_URL must be configured explicitly for control-plane sync in this deployment profile."
        )
    parsed = urlparse(control_plane_url)
    try:
        return validated_runtime_egress_url(
            control_plane_url,
            surface=surface,
            field_name="ALGENTA_CONTROL_PLANE_URL",
            explicit_configured=True,
            egress_class=(
                "algenta_cloud"
                if parsed.hostname and is_algenta_owned_destination(parsed.hostname)
                else "operator_service"
            ),
            record=record,
        )
    except RuntimeEgressPolicyDeniedError as exc:
        raise ValueError(
            "Control-plane egress is blocked by the active privacy policy. "
            f"Reason: {exc.decision.reason}."
        ) from exc


def _control_plane_verification_secrets() -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []

    explicit_secret = os.environ.get("ALGENTA_LICENSE_SIGNING_SECRET") or os.environ.get(
        "LICENSE_SIGNING_SECRET"
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
    device_info: Mapping[str, object],
    body: bytes,
) -> urllib.request.Request:
    return urllib.request.Request(  # noqa: S310
        f"{control_plane_url}/v1/device/register",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Idempotency-Key": _device_registration_idempotency_key(
                _coerce_str(device_info.get("device_id"))
            ),
        },
        method="POST",
    )


def _is_retryable_control_plane_error(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in _RETRYABLE_CONTROL_PLANE_HTTP_CODES
    return isinstance(exc, TimeoutError | urllib.error.URLError | OSError)


def _license_retry_delay_seconds(attempt: int) -> float:
    retry_multiplier = 2 ** max(0, attempt - 1)
    return float(max(0.0, _CONTROL_PLANE_RETRY_BASE_SECONDS) * retry_multiplier)


def _coerce_str(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _coerce_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _coerce_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _coerce_str_list(value: object, default: list[str] | None = None) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return list(default or [])


def _decoded_payload(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    return cast(dict[str, object], value)


@dataclass(frozen=True)
class ProductEntitlement:
    """A single product edition entitlement carried in a v2 license.

    ``tier`` is a coarse plan label for the product (e.g. ``pro``/``team``);
    ``features`` is the set of granted feature identifiers the local engine
    intersects with the product allowlist to compute available tools.
    """

    tier: str
    features: frozenset[str]


@dataclass
class DeviceLicense:
    valid: bool
    plan: str  # "dev" | "pro" | "enterprise"
    device_id: str
    device_limit: int  # 0 = unlimited
    permitted_modules: list[str]
    expires_at: int  # unix timestamp; 0 = no expiry
    key_expires_at: int
    grace_days: int
    api_key_prefix: str
    issued_at: int
    message: str = ""
    source: str = "unknown"  # "cloud" | "dev-stub" | "expired-grace"
    # ── v2 commercial-capacity claims (defaults preserve v1 legacy behavior) ──
    # license_version 1 = legacy-permissive (transition only; rejected after the
    # firm v1 sunset). 2 = authoritative: only granted products/features apply.
    license_version: int = 1
    org_id: str = ""
    license_id: str = ""
    activation_id: str = ""
    entitlement_version: int = 0
    deployment_class: str = ""  # desktop | server | ci | airgapped | oem
    device_pubkey_thumbprint: str = ""
    products: dict[str, ProductEntitlement] = field(default_factory=dict)
    named_seat_limit: int = 0  # 0 = unspecified (control-plane enforced)
    active_node_limit: int = 0
    concurrent_worker_limit: int = 0  # 0 = unspecified; local broker enforces when > 0
    device_allowance_per_seat: int = 0
    commercial_use: bool = False
    redistribution_allowed: bool = False
    offline_grace_days: int = 0

    def is_expired(self) -> bool:
        from apps.runtime.trusted_time import trusted_now_epoch

        if self.expires_at == 0:
            return False
        return int(trusted_now_epoch()) > self.expires_at

    def is_in_grace(self) -> bool:
        from apps.runtime.trusted_time import trusted_now_epoch

        if self.expires_at == 0:
            return False
        grace_end = self.expires_at + (self.grace_days * 86400)
        return self.is_expired() and int(trusted_now_epoch()) <= grace_end

    def is_hard_expired(self) -> bool:
        """True only after grace period ends — this is when we actually block."""
        from apps.runtime.trusted_time import trusted_now_epoch

        if self.expires_at == 0:
            return False
        grace_end = self.expires_at + (self.grace_days * 86400)
        return int(trusted_now_epoch()) > grace_end

    def is_module_permitted(self, module_name: str) -> bool:
        if not self.valid:
            return False
        if "*" in self.permitted_modules:
            return True
        return module_name in self.permitted_modules

    def is_legacy_v1(self) -> bool:
        """True for pre-products (v1) licenses — legacy-permissive during the
        transition window, rejected by production after the firm v1 sunset."""
        return self.license_version < 2

    def has_product(self, product: str) -> bool:
        if not self.valid:
            return False
        # v1 licenses predate product entitlements → legacy-permissive.
        if self.is_legacy_v1():
            return True
        return product in self.products

    def product_features(self, product: str) -> frozenset[str]:
        ent = self.products.get(product)
        return ent.features if ent is not None else frozenset()

    def product_tier(self, product: str) -> str:
        ent = self.products.get(product)
        return ent.tier if ent is not None else ""

    def worker_limit(self) -> int:
        """Local worker-concurrency cap (0 = unspecified; broker does not cap)."""
        return self.concurrent_worker_limit


def _coerce_products(value: object) -> dict[str, ProductEntitlement]:
    """Parse the v2 ``products`` claim, fail-closed: malformed entries are dropped."""
    out: dict[str, ProductEntitlement] = {}
    if not isinstance(value, dict):
        return out
    for name, spec in value.items():
        if not isinstance(name, str) or not name or not isinstance(spec, dict):
            continue
        features = frozenset(_coerce_str_list(spec.get("features"), []))
        out[name] = ProductEntitlement(tier=_coerce_str(spec.get("tier")), features=features)
    return out


def _device_license_from_payload(
    payload: dict[str, object], *, source: str, api_key: str, default_plan: str
) -> DeviceLicense:
    """Build a DeviceLicense from a decoded JWT payload (v1 + v2 claims)."""
    return DeviceLicense(
        valid=True,
        plan=_coerce_str(payload.get("plan"), default_plan),
        device_id=_coerce_str(payload.get("device_id")),
        device_limit=_coerce_int(payload.get("device_limit"), 0),
        permitted_modules=_coerce_str_list(payload.get("permitted_modules"), ["*"]),
        expires_at=_coerce_int(payload.get("expires_at"), 0),
        key_expires_at=_coerce_int(payload.get("key_expires_at"), 0),
        grace_days=_coerce_int(payload.get("grace_days"), _DEFAULT_GRACE_DAYS),
        api_key_prefix=_coerce_str(payload.get("api_key_prefix"), api_key[:12]),
        issued_at=_coerce_int(payload.get("issued_at"), 0),
        message=_coerce_str(payload.get("message")),
        source=source,
        # ── v2 commercial-capacity claims ──
        license_version=_coerce_int(payload.get("ver"), 1),
        org_id=_coerce_str(payload.get("org_id")),
        license_id=_coerce_str(payload.get("license_id")),
        activation_id=_coerce_str(payload.get("activation_id")),
        entitlement_version=_coerce_int(payload.get("entitlement_version"), 0),
        deployment_class=_coerce_str(payload.get("deployment_class")),
        device_pubkey_thumbprint=_coerce_str(payload.get("device_pubkey_thumbprint")),
        products=_coerce_products(payload.get("products")),
        named_seat_limit=_coerce_int(payload.get("named_seat_limit"), 0),
        active_node_limit=_coerce_int(payload.get("active_node_limit"), 0),
        concurrent_worker_limit=_coerce_int(payload.get("concurrent_worker_limit"), 0),
        device_allowance_per_seat=_coerce_int(payload.get("device_allowance_per_seat"), 0),
        commercial_use=bool(payload.get("commercial_use", False)),
        redistribution_allowed=bool(payload.get("redistribution_allowed", False)),
        offline_grace_days=_coerce_int(payload.get("offline_grace_days"), 0),
    )


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
        key_expires_at=0,
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
        key_expires_at=0,
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


def _save_license(token: str, runtime_dir: Path | None = None) -> None:
    target_file = _license_file(runtime_dir)
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(token)
    # Restrict permissions: owner read/write only
    try:
        target_file.chmod(0o600)
    except Exception as exc:
        logger.debug("license_permission_update_failed", error=str(exc))


def _load_raw_token(runtime_dir: Path | None = None) -> str | None:
    target_file = _license_file(runtime_dir)
    try:
        if target_file.exists():
            return target_file.read_text().strip()
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
    strict_local_license = _local_license_required()
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError:
        return None
    algorithm = _coerce_str(header.get("alg"))

    if algorithm == "RS256":
        for key_text, source in _offline_license_public_keys():
            try:
                decoded = jwt.decode(
                    token,
                    key_text,
                    algorithms=["RS256"],
                    options={"verify_exp": False},
                )
                payload = _decoded_payload(decoded)
                if payload is None:
                    continue
                return _device_license_from_payload(
                    payload, source=source, api_key=api_key, default_plan="enterprise"
                )
            except jwt.InvalidTokenError:
                continue
        return None

    if strict_local_license:
        return None

    for secret, source in [(_DEV_SECRET, "dev-stub"), *_control_plane_verification_secrets()]:
        try:
            decoded = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_exp": False},  # we handle expiry ourselves
            )
            payload = _decoded_payload(decoded)
            if payload is None:
                continue
            return _device_license_from_payload(
                payload, source=source, api_key=api_key, default_plan="dev"
            )
        except jwt.InvalidTokenError:
            continue
    return None


def stored_offline_execution_entitlement(
    api_key: str = "",
    *,
    runtime_dir: Path | None = None,
) -> bool:
    token = _load_raw_token(runtime_dir)
    if not token:
        return False
    parsed = _parse_token(token, api_key)
    if parsed is None or not parsed.valid or parsed.key_expires_at <= 0:
        return False
    return not parsed.is_hard_expired()


def local_license_status(api_key: str = "") -> dict[str, object]:
    token = _load_raw_token()
    if not token:
        return {"active": False, "source": "none"}
    parsed = _parse_token(token, api_key)
    if parsed is None:
        return {"active": False, "source": "invalid"}
    if parsed.is_hard_expired():
        return {"active": False, "source": parsed.source, "message": "expired"}
    return {
        "active": parsed.valid,
        "source": parsed.source,
        "plan": parsed.plan,
        "device_id": parsed.device_id,
        "expires_at": parsed.expires_at,
    }


# ── Control plane exchange ────────────────────────────────────────────────────


def _device_pubkey_thumbprint() -> str:
    """This device's Ed25519 public-key thumbprint for activation binding (P3b).

    Generated + persisted on first call (the activation moment). Guarded: any keypair/store
    failure returns "" so registration falls back to a legacy fingerprint-only (unbound)
    activation rather than breaking login.
    """
    try:
        from apps.runtime.device_keypair import public_key_thumbprint

        return public_key_thumbprint()
    except Exception:  # noqa: BLE001 — never let key binding break license exchange
        logger.warning("device_pubkey_thumbprint_unavailable", exc_info=True)
        return ""


def _device_register_body(device_info: Mapping[str, object]) -> bytes:
    """Build the /v1/device/register request body, including the device-key thumbprint."""
    return json.dumps(
        {
            "device": {
                "device_id": device_info.get("device_id", ""),
                "platform": device_info.get("platform", ""),
                "platform_version": device_info.get("platform_version", ""),
                "hostname_hash": device_info.get("hostname_hash", ""),
                "sdk_version": device_info.get("sdk_version", ""),
                "device_pubkey_thumbprint": _device_pubkey_thumbprint(),
            }
        }
    ).encode()


def _exchange_api_key_for_license(
    api_key: str,
    device_info: Mapping[str, object],
) -> str | None:
    """
    POST to control plane: exchange API key + device fingerprint → signed JWT.

    Returns raw JWT string or None on failure.
    """
    # shape-validate only; runtime_urlopen below is the single enforce + audit point
    control_plane_url = _validated_control_plane_url(surface="license_exchange", record=False)
    body = _device_register_body(device_info)
    for attempt in range(1, _CONTROL_PLANE_MAX_ATTEMPTS + 1):
        req = _device_register_request(control_plane_url, api_key, device_info, body)
        try:
            # B10: transport-time fail-closed egress enforcement via the approved wrapper.
            with runtime_urlopen(
                req,
                surface="license_exchange",
                timeout=_CONTROL_PLANE_TIMEOUT_SECONDS,
            ) as resp:
                data = _decoded_payload(json.loads(resp.read()))
                if data is None:
                    logger.warning("license_exchange_invalid_response")
                    return None
                token = _coerce_str(data.get("license_token"))
                if token:
                    from apps.runtime.trusted_time import observe_time

                    logger.info(
                        "license_from_control_plane",
                        plan=data.get("plan"),
                        device_count=data.get("device_count"),
                        device_limit=data.get("device_limit"),
                    )
                    observe_time(
                        _coerce_float(data.get("server_time"), time.time()),
                        source="control-plane-register",
                    )
                    credits_granted = _coerce_int(data.get("credits_granted"), 0)
                    if credits_granted > 0:
                        try:
                            from apps.runtime.credits import get_store
                            from apps.runtime.trusted_time import trusted_now_epoch

                            now = trusted_now_epoch()

                            get_store().initialize_sync(
                                credits_granted=credits_granted,
                                billing_period=_coerce_str(data.get("credits_billing_period")),
                                ttl_seconds=max(
                                    1,
                                    _coerce_int(
                                        _coerce_float(
                                            data.get("credits_expires_at"),
                                            now + 86_400,
                                        )
                                        - now,
                                        1,
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
                    detail = _decoded_payload(json.loads(exc.read().decode()))
                    if detail is None:
                        raise PermissionError("Device limit reached. Upgrade your plan.") from exc
                    detail_payload = _decoded_payload(detail.get("detail", {})) or {}
                    logger.error("device_limit_reached", detail=detail)
                    raise PermissionError(
                        detail_payload.get(
                            "message",
                            "Device limit reached.",
                        )
                    ) from exc
                except (json.JSONDecodeError, KeyError):
                    raise PermissionError("Device limit reached. Upgrade your plan.") from exc
            if _is_retryable_control_plane_error(exc) and attempt < _CONTROL_PLANE_MAX_ATTEMPTS:
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
            if _is_retryable_control_plane_error(exc) and attempt < _CONTROL_PLANE_MAX_ATTEMPTS:
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


def _license_post_request(
    url: str, api_key: str, body: bytes
) -> urllib.request.Request:
    return urllib.request.Request(  # noqa: S310
        url,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )


def renew_license(api_key: str, device_info: Mapping[str, object] | None = None) -> str | None:
    """Renew the device license via proof-of-possession (challenge → sign → renew).

    The preferred refresh for an already-bound device: it proves possession of the device
    private key (signing a server nonce) and returns a fresh license WITHOUT a full
    re-registration. Returns the new token on success, or None on ANY failure (an old server
    that 404s on /v1/license/*, an egress denial, a missing keypair, a bad response) so the
    caller transparently falls back to ``_exchange_api_key_for_license`` (full re-register).
    """
    try:
        import base64 as _b64

        from apps.runtime.device import get_device_info
        from apps.runtime.device_keypair import device_public_key_pem, sign

        if device_info is None:
            device_info = get_device_info()
        device_id = _coerce_str(device_info.get("device_id"))
        if not device_id:
            return None
        control_plane_url = _validated_control_plane_url(surface="license_renew", record=False)

        # 1. Challenge → single-use nonce.
        chal_req = _license_post_request(
            f"{control_plane_url}/v1/license/challenge",
            api_key,
            json.dumps({"device_id": device_id}).encode(),
        )
        with runtime_urlopen(
            chal_req, surface="license_renew", timeout=_CONTROL_PLANE_TIMEOUT_SECONDS
        ) as resp:
            chal = _decoded_payload(json.loads(resp.read()))
        nonce_b64 = _coerce_str(chal.get("nonce")) if chal else ""
        if not nonce_b64:
            return None

        # 2. Sign the server nonce with the device private key (never transmitted).
        signature = _b64.b64encode(sign(_b64.b64decode(nonce_b64))).decode()

        # 3. Renew → fresh license.
        renew_req = _license_post_request(
            f"{control_plane_url}/v1/license/renew",
            api_key,
            json.dumps(
                {
                    "device_id": device_id,
                    "public_key_pem": device_public_key_pem(),
                    "signature": signature,
                }
            ).encode(),
        )
        with runtime_urlopen(
            renew_req, surface="license_renew", timeout=_CONTROL_PLANE_TIMEOUT_SECONDS
        ) as resp:
            data = _decoded_payload(json.loads(resp.read()))
        token = _coerce_str(data.get("license_token")) if data else ""
        if not token:
            return None
        from apps.runtime.trusted_time import observe_time

        observe_time(_coerce_float(data.get("server_time"), time.time()), source="control-plane-renew")
        logger.info("license_renewed_via_pop", device_id=device_id[:8])
        return token
    except Exception:  # noqa: BLE001 — renewal is best-effort; caller falls back to register
        logger.debug("license_renew_failed", exc_info=True)
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
    from apps.runtime.trusted_time import trusted_now_epoch

    trusted_now_epoch()

    # 1. Try stored license
    raw = _load_raw_token()
    if raw:
        parsed = _parse_token(raw, api_key)
        if parsed:
            if parsed.is_hard_expired():
                logger.warning("license_hard_expired", device_id=parsed.device_id)
                # Preferred refresh: prove possession of the bound device key → a fresh license
                # WITHOUT a full re-login. Dark: any failure (old server, unbound device, egress
                # denial) falls through to the existing expired message.
                if api_key and not _local_license_required():
                    renewed = renew_license(api_key)
                    if renewed:
                        _save_license(renewed)
                        fresh = _parse_token(renewed, api_key)
                        if fresh and not fresh.is_hard_expired():
                            logger.info("license_auto_renewed", device_id=fresh.device_id[:8])
                            return fresh
                parsed.valid = False
                parsed.message = "License expired — run `algenta login` to renew."
                return parsed
            if parsed.is_in_grace():
                parsed.message = "License in grace period — run `algenta login` to renew."
                logger.info("license_in_grace_period")
            return parsed

    if _local_license_required():
        return _make_invalid_license(
            "A valid local signed license is required for this deployment profile. "
            "Provision an offline license file before startup.",
            api_key=api_key,
        )

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
    if _local_license_required():
        return _make_invalid_license(
            "ALGENTA_REQUIRE_LOCAL_LICENSE=1 disables hosted registration. "
            "Use scripts/issue_offline_license.py to provision a local signed license.",
            api_key=api_key,
        )
    from apps.runtime.device import get_device_info
    from apps.runtime.trusted_time import trusted_now_epoch

    trusted_now_epoch()
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
        _license_file().unlink(missing_ok=True)
    except Exception as exc:
        logger.debug("license_delete_failed", error=str(exc))


def license_summary(lic: DeviceLicense) -> str:
    """Human-readable one-liner."""
    expiry = (
        "no expiry"
        if lic.expires_at == 0
        else (
            "in grace"
            if lic.is_in_grace()
            else f"expires {time.strftime('%Y-%m-%d', time.gmtime(lic.expires_at))}"
        )
    )
    limit = "unlimited" if lic.device_limit == 0 else f"max {lic.device_limit} devices"
    return f"plan={lic.plan}  {limit}  {expiry}  source={lic.source}  device={lic.device_id[:8]}..."
