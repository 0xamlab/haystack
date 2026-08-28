"""
Device license — JWT-based, locally stored, offline-capable.

License lifecycle:
  1. algenta login → device fingerprint sent to control plane
  2. Control plane validates API key, checks device count against plan limits
  3. Control plane issues signed JWT → stored in ~/.algenta/runtime/license.jwt
  4. Runtime validates JWT locally on every startup (no network)
  5. A persisted trusted clock keeps offline expiry checks non-decreasing
  6. Self-hosted/private profiles keep audit records local; managed profiles may explicitly sync
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
    "sub": "device-license",
    "ver": 2,                              # license schema version; v2 is required
    "products": {"codna": {"tier": "pro", "features": ["triage", "fix"]}}
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

_LICENSE_VERSION = 2

# Secret used for self-signed dev licenses (never used for cloud validation). It lives ONLY in the
# dev-only stub module so the production wheel can physically strip it (scripts/strip_dev_stub.py);
# when the stub is absent, _DEV_SECRET is None and the HS256 dev-stub verify/issue paths become
# unreachable — the runtime is RS256-only by construction, not just by flag.
try:
    from apps.runtime._dev_license_stub import DEV_SECRET as _DEV_SECRET
except ImportError:  # production wheel — dev stub stripped
    _DEV_SECRET = None  # type: ignore[assignment]

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


def _rs256_only_enforced() -> bool:
    """Production RS256-only mode: reject EVERY HS256 token (the forgeable dev-stub AND the
    control-plane HS256 secrets), leaving asymmetric RS256 the only accepted signature.

    True when ``ALGENTA_LICENSE_RS256_ONLY`` is set OR the deployment already requires a local
    signed license (``require_local_license``). Production wheels set the flag so the HS256 path
    is unreachable regardless of profile — the runtime half of the artifact split (the packaging
    half physically strips the dev secret from the wheel; this guarantees safety even if it's
    present). Default OFF preserves the shipped HS256-verifying internal consumers."""
    value = os.environ.get("ALGENTA_LICENSE_RS256_ONLY", "").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    return _local_license_required()


def _runtime_product() -> str:
    """The product edition this runtime is licensed for (algenta | codna | telys | sqai | cohenta).

    Used by the strict verifier to reject a license minted for a different product (cross-product
    replay). Defaults to ``algenta`` (the engine) and is overridable per edition deployment."""
    return (os.environ.get("ALGENTA_RUNTIME_PRODUCT", "") or "algenta").strip() or "algenta"


# Products whose SHIPPED runtime still verifies the legacy HS256 control-plane / dev-stub license
# by explicit, already-reviewed design (mirrors apps/api_server/services/product_registry.py's
# ``rs256_license=False`` set — codna today; see also device_service._RS256_LICENSE_PRODUCTS,
# the mirror-image allowlist on the SIGNER side). Inlined here (rather than importing
# product_registry, which lives in the api_server app) so apps/runtime stays a leaf module with no
# dependency on the api_server layer — this small frozenset is the one place the two must be kept
# in sync. Every product NOT in this set is RS256-only, unconditionally, regardless of
# ALGENTA_LICENSE_RS256_ONLY / require_local_license — those remain available as additional,
# stricter opt-ins, not as what makes RS256-only the default.
_HS256_LEGACY_PERMITTED_PRODUCTS: frozenset[str] = frozenset({"codna"})


def _hs256_legacy_permitted_for_current_product() -> bool:
    """Whether the CURRENT runtime's product is still allowed to verify legacy HS256 tokens.

    This is the structural fix for the historical footgun: HS256 acceptance used to be an
    opt-in "strict mode" (``ALGENTA_LICENSE_RS256_ONLY`` / ``require_local_license``) that was
    OFF by default, so every product silently accepted a forgeable HS256 token unless an
    operator explicitly hardened it. Now HS256 is hard-rejected by default for every product
    except the one still shipping it by deliberate design (``_HS256_LEGACY_PERMITTED_PRODUCTS``)
    — hardening is no longer something an operator has to remember to turn on."""
    return _runtime_product() in _HS256_LEGACY_PERMITTED_PRODUCTS


def _runtime_deployment_id() -> str:
    """Explicit organization-deployment activation signal. Its PRESENCE (with a deployment-scope
    license) is one of the ways a runtime opts into deployment scope — detection never does."""
    return (os.environ.get("ALGENTA_DEPLOYMENT_ID", "") or "").strip()


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
    # ── v2 commercial-capacity claims (v2 is the only supported format) ──
    license_version: int = 2
    org_id: str = ""
    license_id: str = ""
    activation_id: str = ""
    entitlement_version: int = 0
    deployment_class: str = ""  # desktop | server | ci | airgapped | oem
    # ── server/enterprise scope + Compute-Unit claims (additive; default = personal device) ──
    # license_scope is the top-level context switch: "device" (default — personal, local,
    # never sees Compute Units/pools/Relay) vs "deployment" (org server deployment). A token
    # without the claim is "device" (back-compat + fail-safe). Detection NEVER sets this — only
    # an explicitly-minted deployment license / Relay lease carries scope="deployment".
    license_scope: str = "device"  # device | deployment
    deployment_id: str = ""  # set only for deployment-scoped licenses
    max_concurrent_units: int = 0  # Compute-Unit pool ceiling (0 = unspecified / device scope)
    max_effective_vcpu: int = 0  # per-node workstation vCPU ceiling (0 = unspecified)
    vcpu_per_unit: int = 0  # measurement policy: effective vCPU per Compute Unit (0 = default 4)
    measurement_policy_version: str = ""  # names the vCPU→unit measurement rules in force
    grace_policy_id: str = ""  # names the lapse/grace/Community-floor policy in force
    device_pubkey_thumbprint: str = ""
    products: dict[str, ProductEntitlement] = field(default_factory=dict)
    named_seat_limit: int = 0  # 0 = unspecified (control-plane enforced)
    active_node_limit: int = 0
    concurrent_worker_limit: int = 0  # 0 = unspecified; local broker enforces when > 0
    device_allowance_per_seat: int = 0
    commercial_use: bool = False
    redistribution_allowed: bool = False
    offline_grace_days: int = 0
    # Vendor-signed mint time (epoch seconds), covered by the token's RS256 signature. When the
    # local lapse floor is unverifiable (missing/tampered), a license carrying this claim re-seeds
    # the floor from the vendor signature instead of trusting the host's wall clock — closing
    # the delete-floor + roll-back-clock re-validation attack (trusted_time.floor_integrity).
    signed_epoch: int = 0

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

    def has_product(self, product: str) -> bool:
        if not self.valid:
            return False
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

    def node_limit(self) -> int:
        """Active-node cap (0 = unspecified; node_broker does not cap). Enforced offline by the runtime
        node_broker (device-binding + peer census), symmetric to ``worker_limit`` — see
        ``apps/runtime/node_broker.py``."""
        return self.active_node_limit

    def is_deployment_scope(self) -> bool:
        """True only for an explicitly-minted organization-deployment license. Personal-device
        licenses (the default, and any legacy token without the claim) return False — so the
        server enforcement path (Compute Units / pools / Relay) is opt-in per signed claim,
        never inferred from the host environment."""
        return self.valid and self.license_scope == "deployment"

    def unit_size(self) -> int:
        """Effective vCPU per Compute Unit for this license (falls back to the measurement
        default when the claim is unset)."""
        from apps.runtime.capacity import DEFAULT_VCPU_PER_UNIT

        return self.vcpu_per_unit if self.vcpu_per_unit > 0 else DEFAULT_VCPU_PER_UNIT


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
) -> DeviceLicense | None:
    """Build a DeviceLicense from a decoded JWT payload. v2 is the only supported
    format: a token without a v2 (``ver`` >= 2) claim is rejected (returns None)."""
    if _coerce_int(payload.get("ver"), 0) < 2:
        return None
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
        license_version=_coerce_int(payload.get("ver"), 2),
        org_id=_coerce_str(payload.get("org_id")),
        license_id=_coerce_str(payload.get("license_id")),
        activation_id=_coerce_str(payload.get("activation_id")),
        entitlement_version=_coerce_int(payload.get("entitlement_version"), 0),
        deployment_class=_coerce_str(payload.get("deployment_class")),
        # Scope defaults to "device": a token without the claim (legacy or personal) is
        # personal-device scope, never accidentally a server deployment.
        license_scope=(_coerce_str(payload.get("license_scope"), "device") or "device"),
        deployment_id=_coerce_str(payload.get("deployment_id")),
        max_concurrent_units=_coerce_int(payload.get("max_concurrent_units"), 0),
        max_effective_vcpu=_coerce_int(payload.get("max_effective_vcpu"), 0),
        vcpu_per_unit=_coerce_int(payload.get("vcpu_per_unit"), 0),
        measurement_policy_version=_coerce_str(payload.get("measurement_policy_version")),
        grace_policy_id=_coerce_str(payload.get("grace_policy_id")),
        device_pubkey_thumbprint=_coerce_str(payload.get("device_pubkey_thumbprint")),
        products=_coerce_products(payload.get("products")),
        named_seat_limit=_coerce_int(payload.get("named_seat_limit"), 0),
        active_node_limit=_coerce_int(payload.get("active_node_limit"), 0),
        concurrent_worker_limit=_coerce_int(payload.get("concurrent_worker_limit"), 0),
        device_allowance_per_seat=_coerce_int(payload.get("device_allowance_per_seat"), 0),
        commercial_use=bool(payload.get("commercial_use", False)),
        redistribution_allowed=bool(payload.get("redistribution_allowed", False)),
        offline_grace_days=_coerce_int(payload.get("offline_grace_days"), 0),
        signed_epoch=_coerce_int(payload.get("signed_epoch"), 0),
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


def _make_community_license(
    api_key: str = "", *, reason: str = "", deployment_id: str = ""
) -> DeviceLicense:
    """Free-forever Community fallback for a lapsed/expired PAID license.

    A deployment whose paid license hard-expires and cannot renew downgrades to Community rather
    than hard-blocking: the engine keeps running on the user's
    hardware at Community limits (1 device, 1 worker, non-commercial); paid caps/features and
    updates/support resume only when the license renews. The fallback is local and works for a
    previously valid connected or air-gapped license; an installation with no valid signed license
    remains blocked when the deployment profile requires one.

    For a lapsed SERVER/DEPLOYMENT license, ``deployment_id`` is carried through so the recovery
    floor is scoped ONCE per deployment (an elected recovery runtime — coordinated by the node
    broker), never one free Community allowance per node/pod/replica. The floor itself stays
    1 unit / 1 worker regardless of scope.
    """
    from apps.runtime.device import get_device_id

    prefix = api_key[:12] if api_key else ""
    return DeviceLicense(
        valid=True,
        plan="algenta_free",
        device_id=get_device_id(),
        device_limit=1,
        permitted_modules=["*"],
        expires_at=0,  # free-forever — never expires
        key_expires_at=0,
        grace_days=_DEFAULT_GRACE_DAYS,
        api_key_prefix=prefix,
        issued_at=int(time.time()),
        message=(reason or "Paid license expired — running on Community (free-forever). Renew to restore your plan."),
        source="community-fallback",
        deployment_class="desktop",
        # Stays device-scope: a lapsed deployment recovers to the personal-device Community
        # floor. deployment_id is retained so the once-per-deployment recovery election (node
        # broker) can key on it; it does NOT re-grant deployment-scope capacity.
        license_scope="device",
        deployment_id=deployment_id,
        named_seat_limit=1,
        active_node_limit=1,
        concurrent_worker_limit=1,  # Community per-device worker cap
        device_allowance_per_seat=1,
        commercial_use=False,  # Community is non-commercial
        offline_grace_days=30,
    )


def _issue_dev_jwt(device_id: str, api_key: str = "") -> str:
    """Issue a self-signed dev JWT for local storage. Unavailable in a production wheel (the dev
    stub is stripped → _DEV_SECRET is None), where dev-mode issuance must not exist."""
    if _DEV_SECRET is None:
        raise RuntimeError("dev-stub license issuance is unavailable in a production build")
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


# ── RS256 device-token signer (control-plane / operator mint side) ──────────────
# The DEVICE only ever VERIFIES — it holds the PUBLIC key (ALGENTA_LOCAL_LICENSE_PUBLIC_KEY).
# This signer runs where the PRIVATE key lives: the control plane (Fly) or an operator mint tool,
# NEVER shipped to a device. It supersedes the HS256 dev stub for any real (commercial / go-dark)
# token — HS256 is forgeable by anyone holding the shared secret; RS256 is not.


def _signing_private_key(private_key_pem: str | None = None) -> str:
    """The RS256 private key, from (in order) an explicit PEM arg, ALGENTA_LICENSE_SIGNING_PRIVATE_KEY,
    or ALGENTA_LICENSE_SIGNING_PRIVATE_KEY_FILE. Mirrors the public-key env convention."""
    if private_key_pem and private_key_pem.strip():
        return private_key_pem.strip()
    value = (os.environ.get("ALGENTA_LICENSE_SIGNING_PRIVATE_KEY") or "").strip()
    if value:
        return value
    path_value = (os.environ.get("ALGENTA_LICENSE_SIGNING_PRIVATE_KEY_FILE") or "").strip()
    if path_value:
        return Path(path_value).expanduser().read_text().strip()
    raise ValueError(
        "RS256 device-token signing requires ALGENTA_LICENSE_SIGNING_PRIVATE_KEY (or _FILE) — the "
        "control-plane private key. It must never be present on a device."
    )


def mint_device_token(
    *,
    org_id: str,
    plan: str = "pro",
    ttl_days: int = 14,
    grace_days: int = _DEFAULT_GRACE_DAYS,
    device_id: str = "",
    api_key_prefix: str = "",
    permitted_modules: list[str] | None = None,
    products: dict[str, object] | None = None,
    license_version: int = 2,
    license_id: str = "",
    activation_id: str = "",
    deployment_class: str = "desktop",
    license_scope: str = "device",
    deployment_id: str = "",
    max_concurrent_units: int = 0,
    max_effective_vcpu: int = 0,
    vcpu_per_unit: int = 0,
    measurement_policy_version: str = "",
    grace_policy_id: str = "",
    issued_at: int | None = None,
    private_key_pem: str | None = None,
    extra_claims: dict[str, object] | None = None,
) -> str:
    """Mint an RS256-signed offline device token the runtime verifies with its public key.

    TTL + grace (go-dark): the token's working life is ``ttl_days``; past ``expires_at`` the device
    keeps operating through ``grace_days`` before hard denial. Enforcement is via the ``expires_at`` +
    ``grace_days`` claims (the RS256 decode path runs ``verify_exp=False`` — the runtime owns expiry,
    see ``DeviceLicense.is_hard_expired`` / ``offline_token``); the JWT ``exp`` is set to the hard-deny
    boundary so external tooling agrees with the runtime.
    """
    if not org_id:
        raise ValueError("org_id is required for a device token")
    now = int(issued_at if issued_at is not None else time.time())
    grace = max(0, int(grace_days))
    expires_at = 0 if ttl_days <= 0 else now + int(ttl_days) * 86400
    payload: dict[str, object] = {
        "org_id": org_id,
        "plan": plan,
        "device_id": device_id,
        "device_limit": 0,
        "permitted_modules": permitted_modules or ["*"],
        "issued_at": now,
        "iat": now,
        "expires_at": expires_at,
        "grace_days": grace,
        "ver": int(license_version),
        "license_id": license_id,
        "activation_id": activation_id,
        "deployment_class": deployment_class,
        "iss": "algenta-control-plane",
        "sub": "device-license",
    }
    if api_key_prefix:
        payload["api_key_prefix"] = api_key_prefix
    if products:
        payload["products"] = products
    # Server/deployment claims — emitted ONLY when set, so personal-device tokens (and existing
    # golden shapes) are unchanged. scope="deployment" is the sole switch that activates the
    # server enforcement path at runtime.
    if license_scope and license_scope != "device":
        payload["license_scope"] = license_scope
    if deployment_id:
        payload["deployment_id"] = deployment_id
    if max_concurrent_units > 0:
        payload["max_concurrent_units"] = int(max_concurrent_units)
    if max_effective_vcpu > 0:
        payload["max_effective_vcpu"] = int(max_effective_vcpu)
    if vcpu_per_unit > 0:
        payload["vcpu_per_unit"] = int(vcpu_per_unit)
    if measurement_policy_version:
        payload["measurement_policy_version"] = measurement_policy_version
    if grace_policy_id:
        payload["grace_policy_id"] = grace_policy_id
    if expires_at:
        # JWT exp = the HARD-deny boundary (expiry + grace), so a verifier that DOES check exp agrees
        # with the runtime's is_hard_expired(); the runtime itself decodes with verify_exp=False.
        payload["exp"] = expires_at + grace * 86400
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, _signing_private_key(private_key_pem), algorithm="RS256")


def mint_deployment_token(
    *,
    org_id: str,
    product: str,
    edition: str,
    deployment_id: str,
    license_claims: dict[str, object],
    device_pubkey_thumbprint: str = "",
    ttl_days: int = 365,
    grace_days: int = _DEFAULT_GRACE_DAYS,
    jti: str = "",
    kid: str = "",
    issued_at: int | None = None,
    private_key_pem: str | None = None,
    audience: str = "algenta-runtime",
    issuer: str = "https://license.algenta.ai",
) -> str:
    """Mint a STRICT-PROFILE (``typ=algenta-license+jwt``) RS256 deployment license.

    This is the server/enterprise counterpart to ``mint_device_token``: it emits the full strict
    JOSE profile the hardened verifier (``license_verify``) requires — exact ``typ``/``kid``/
    ``iss``/``aud``/``product``/``edition`` + all required claims — merging the resolved
    ``license_claims`` (from an ``EntitlementSnapshot``, incl. ``max_concurrent_units`` etc.).
    ``license_scope`` is forced to ``deployment``. The private key must live only where signing
    happens (control plane / operator), never on a device.
    """
    if not org_id or not product or not deployment_id:
        raise ValueError("org_id, product, and deployment_id are required for a deployment token")
    now = int(issued_at if issued_at is not None else time.time())
    grace = max(0, int(grace_days))
    expires_at = now + max(1, int(ttl_days)) * 86400
    license_id = jti or _new_jti()
    payload: dict[str, object] = {
        # strict-profile required claims
        "iss": issuer,
        "aud": audience,
        "sub": "device-license",
        "jti": license_id,
        "license_id": license_id,
        # Stable per (org, deployment) — the CRL revokes by activation_id (same convention as
        # device licenses), so a deployment license is revocable even across re-issues.
        "activation_id": _deployment_activation_id(org_id, deployment_id),
        "iat": now,
        "nbf": now,
        "issued_at": now,
        # Vendor-signed mint time — covered by the RS256 signature. Lets the runtime re-seed its
        # lapse floor from the vendor signature when the local floor is unverifiable (GAP-1),
        # keeping first-boot air-gapped activation working.
        "signed_epoch": now,
        "exp": expires_at + grace * 86400,  # hard-deny boundary; runtime owns grace within
        "expires_at": expires_at,
        "grace_days": grace,
        "schema_version": 2,
        "ver": 2,
        "product": product,
        "edition": edition,
        "license_scope": "deployment",
        "deployment_id": deployment_id,
        "device_pubkey_thumbprint": device_pubkey_thumbprint,
        "permitted_modules": ["*"],
    }
    # Merge the resolved entitlement claims (products, max_concurrent_units, vcpu_per_unit,
    # measurement/grace policy, commercial_use, ...). Never let them override the identity/scope.
    for key, value in (license_claims or {}).items():
        payload.setdefault(key, value)
    payload["license_scope"] = "deployment"  # authoritative regardless of claims
    if "deployment_class" not in payload:
        payload["deployment_class"] = "server"

    headers = {"typ": "algenta-license+jwt", "kid": kid or _signing_kid()}
    return jwt.encode(
        payload, _signing_private_key(private_key_pem), algorithm="RS256", headers=headers
    )


def _new_jti() -> str:
    import uuid

    return str(uuid.uuid4())


def _deployment_activation_id(org_id: str, deployment_id: str) -> str:
    """Deterministic, stable, opaque activation id for an (org, deployment) — the CRL revokes by
    it. Stable across re-issues so a deployment can be named once for revocation."""
    import uuid

    try:
        namespace = uuid.UUID(str(org_id))
    except (ValueError, AttributeError, TypeError):
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{org_id}:{deployment_id}"))
    return str(uuid.uuid5(namespace, f"deployment:{deployment_id}"))


def _signing_kid() -> str:
    return (os.environ.get("ALGENTA_LICENSE_SIGNING_KID", "") or "algenta-license-default").strip()


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
    # Durable env fallback so a hosted/air-gapped engine keeps a valid offline license across
    # redeploys WITHOUT a persistent volume — the license JWT lives in a platform secret
    # (e.g. a Fly secret), which survives machine/image redeploys where the local file does not.
    # The file still takes precedence; env is only used when no file is present. Mirrors the
    # public-key env/_FILE resolution. Verification is unchanged (RS256, fully offline).
    for env_name in ("ALGENTA_LICENSE_JWT", "ALGENTA_LOCAL_LICENSE"):
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
    for env_name in ("ALGENTA_LICENSE_JWT_FILE", "ALGENTA_LOCAL_LICENSE_FILE"):
        path = os.environ.get(env_name, "").strip()
        if not path:
            continue
        try:
            candidate = Path(path)
            if candidate.exists():
                return candidate.read_text().strip()
        except Exception as exc:
            logger.debug("license_env_file_read_failed", error=str(exc))
    return None


# ── Token parsing ─────────────────────────────────────────────────────────────


def _parse_token(token: str, api_key: str = "") -> DeviceLicense | None:
    """
    Decode and validate a JWT license token. v2 is the only supported format
    (tokens without ``ver`` >= 2 are rejected).

    Dev tokens use HMAC-SHA256 with the dev secret; cloud/offline tokens use
    RS256 with the Algenta public key.
    """
    # Strict-profile (new server/deployment) tokens carry typ=algenta-license+jwt and are
    # verified by the hardened RS256-only JOSE profile (no HS256, exact iss/aud/product match).
    # They NEVER fall through to the legacy path — a strict token that fails strict verification
    # is invalid, full stop. Legacy tokens (no such typ) are untouched below.
    try:
        from apps.runtime import license_verify

        if license_verify.is_strict_profile_token(token):
            verified, reason = license_verify.try_verify_license_token(
                token, expected_product=_runtime_product()
            )
            if verified is None:
                logger.warning("strict_license_rejected", reason=reason)
                return None
            return _device_license_from_payload(
                verified.payload, source="strict", api_key=api_key, default_plan="enterprise"
            )
    except Exception:  # noqa: BLE001 — strict verifier problems must not crash license load
        logger.debug("strict_license_verify_error", exc_info=True)
        return None

    rs256_only = _rs256_only_enforced()
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
                    options={"verify_exp": False, "verify_aud": False},
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

    if rs256_only or not _hs256_legacy_permitted_for_current_product():
        # Hard reject: no HS256 token (dev-stub or control-plane secret) is accepted. This is now
        # the UNCONDITIONAL default for every product except the one still shipping HS256 by
        # deliberate design (see _HS256_LEGACY_PERMITTED_PRODUCTS) — ALGENTA_LICENSE_RS256_ONLY /
        # require_local_license remain available as an operator's additional, stricter opt-in on
        # top of that, not as what makes RS256-only the default.
        return None

    # The dev-stub secret is only in the loop when the dev stub is present (dev/test builds); a
    # production wheel with the stub stripped has _DEV_SECRET=None and never accepts a dev-stub token.
    hs256_secrets: list[tuple[str, str]] = list(_control_plane_verification_secrets())
    if _DEV_SECRET is not None:
        hs256_secrets.insert(0, (_DEV_SECRET, "dev-stub"))
    for secret, source in hs256_secrets:
        try:
            decoded = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_exp": False, "verify_aud": False},  # we handle expiry ourselves
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


# ── Revocation list (CRL) enforcement (P3b-D2) ─────────────────────────────────
#
# DARK + fail-open-on-uncertainty: a license is revoked ONLY when a positively-VERIFIED CRL
# explicitly lists its activation_id. Any uncertainty — offline, fetch/parse/verify failure,
# expired CRL — KEEPS the
# license valid. This is the only path that can falsely break a paying customer, so it errs
# entirely toward NOT revoking.

_CRL_CACHE_TTL_SECONDS = 600
_crl_cache: dict[str, object] = {}


def _verify_control_plane_jwt(token: str) -> dict[str, object] | None:
    """Verify a control-plane-signed JWT (e.g. the CRL) with the SAME key material as licenses.

    Mirrors ``_parse_token``'s verification (RS256 via offline public keys; else HS256 via the
    dev + control-plane secrets). Returns the payload, or None if no trusted key verifies it.
    """
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError:
        return None
    if _coerce_str(header.get("alg")) == "RS256":
        for key_text, _ in _offline_license_public_keys():
            try:
                return _decoded_payload(
                    jwt.decode(token, key_text, algorithms=["RS256"], options={"verify_exp": False, "verify_aud": False})
                )
            except jwt.InvalidTokenError:
                continue
        return None
    if _local_license_required() or not _hs256_legacy_permitted_for_current_product():
        return None  # strict deployments / every non-legacy product accept RS256 only
    # NOTE: the CRL is NEVER signed with the public dev stub secret — only with the control-plane
    # secret (or RS256 above). Excluding _DEV_SECRET here prevents an attacker from forging a CRL
    # with the hardcoded, source-visible dev secret to revoke a victim's activation.
    for secret, _ in _control_plane_verification_secrets():
        try:
            return _decoded_payload(
                jwt.decode(token, secret, algorithms=["HS256"], options={"verify_exp": False, "verify_aud": False})
            )
        except jwt.InvalidTokenError:
            continue
    return None


def _crl_get_request(
    url: str,
) -> urllib.request.Request:
    return urllib.request.Request(  # noqa: S310
        url,
        headers={"Accept": "application/json"},
        method="GET",
    )


def _fetch_revocation_list() -> dict[str, object] | None:
    """Fetch + verify the signed CRL. Returns the VERIFIED payload, or None on any uncertainty.

    Cached in-process with a monotonic TTL. None means "do not trust / do not revoke" — every
    failure mode (offline, bad/missing signature, expired valid_until) returns None.
    """
    cached = _crl_cache.get("payload")
    fetched = _crl_cache.get("fetched_monotonic", 0.0)
    if cached is not None and (time.monotonic() - float(fetched)) < _CRL_CACHE_TTL_SECONDS:
        cached_valid_until = _coerce_int(cached.get("valid_until"), 0)  # type: ignore[union-attr]
        if not cached_valid_until or cached_valid_until >= int(time.time()):
            return cached  # type: ignore[return-value]
        _crl_cache.clear()  # cached CRL passed its valid_until → re-fetch (fail-open if that fails)
    try:
        control_plane_url = _validated_control_plane_url(surface="crl_fetch", record=False)
        req = _crl_get_request(f"{control_plane_url}/v1/license/revocations")
        with runtime_urlopen(
            req, surface="crl_fetch", timeout=_CONTROL_PLANE_TIMEOUT_SECONDS
        ) as resp:
            body = _decoded_payload(json.loads(resp.read()))
        crl_jwt = _coerce_str(body.get("crl")) if body else ""
        if not crl_jwt:
            return None
        payload = _verify_control_plane_jwt(crl_jwt)
        if payload is None:
            logger.warning("crl_signature_unverified")  # fail-open: do not revoke on bad sig
            return None
        valid_until = _coerce_int(payload.get("valid_until"), 0)
        if valid_until and valid_until < int(time.time()):
            logger.warning("crl_expired")  # stale CRL → do not trust (fail-open)
            return None
        _crl_cache["payload"] = payload
        _crl_cache["fetched_monotonic"] = time.monotonic()
        return payload
    except Exception:  # noqa: BLE001 — any failure → do not revoke (fail-open)
        logger.debug("crl_fetch_failed", exc_info=True)
        return None


def _deny_if_revoked(parsed: DeviceLicense) -> DeviceLicense | None:
    """If the license is revoked, mark it invalid and return it; else None. Centralizes the
    revocation verdict so every load path (stored / auto-renewed / freshly-issued) enforces it."""
    if _is_license_revoked(parsed):
        logger.warning("license_revoked", device_id=parsed.device_id)
        parsed.valid = False
        parsed.message = "License revoked by the control plane."
        return parsed
    return None


def _is_license_revoked(parsed: DeviceLicense) -> bool:
    """True ONLY when a positively-verified CRL explicitly lists this license's activation_id.

    OEM licenses are deliberately non-phone-home and therefore never fetch a control-plane CRL.
    DARK: no activation_id → never revoked. Every uncertainty → False (keep the license).
    """
    if parsed.deployment_class == "oem":
        return False
    if not parsed.activation_id:
        return False
    crl = _fetch_revocation_list()
    if not crl:
        return False  # offline / unverifiable / expired → keep the license
    revoked = crl.get("revoked")
    if not isinstance(revoked, list):
        return False
    revoked_ids = {
        _coerce_str(entry.get("activation_id"))
        for entry in revoked
        if isinstance(entry, dict)
    }
    return parsed.activation_id in revoked_ids


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
    if _is_license_revoked(parsed):
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


def _settle_lapse_floor(parsed: DeviceLicense) -> None:
    """Durably settle the lapse floor past a lapsed token's hard-deny boundary.

    Called when a lapse verdict had to be made WITHOUT a verifiable floor (missing/tampered):
    the floor is advanced to ``expires_at + grace_days + 1`` — vendor-signed claims, never the
    host clock — so a later boot cannot re-validate the lapsed token by rolling the wall clock
    back under a wall-clock-seeded floor. ``max`` with the current trusted time keeps an honest
    (already-later) clock from ever moving backward. The floor is monotonic and signed from here
    on; deleting it again just re-runs the same fail-closed gate."""
    from apps.runtime.trusted_time import observe_time, trusted_now_epoch

    if parsed.expires_at <= 0:
        return
    hard_deny_boundary = float(parsed.expires_at + parsed.grace_days * 86400 + 1)
    observe_time(max(hard_deny_boundary, trusted_now_epoch()), source="lapse-floor")


def load_license(api_key: str = "") -> DeviceLicense:
    """
    Load the local license. Precedence:
      1. Valid stored JWT (cloud or dev, not hard-expired)
      2. Exchange API key for new license (if key present + no valid stored)
      3. Allow explicit dev stub only when ALGENTA_RUNTIME_DEV_MODE is enabled
    """
    from apps.runtime.device import get_device_info
    from apps.runtime.trusted_time import floor_integrity, observe_time, trusted_now_epoch

    # GAP-1 (time-floor hardening): capture the lapse-floor integrity verdict BEFORE
    # trusted_now_epoch() runs — that first read recreates a MISSING floor from the wall clock,
    # which must not launder a deleted floor back into "ok" before the lapse decision below.
    floor_status = floor_integrity()

    trusted_now_epoch()

    # 1. Try stored license
    raw = _load_raw_token()
    if raw:
        parsed = _parse_token(raw, api_key)
        if parsed:
            # GAP-1 (time-floor hardening): for a license that CAN lapse (finite expiry), the
            # expiry verdict is only as trustworthy as the lapse floor under it. When the floor
            # is unverifiable (missing or tampered), the host's wall clock may NOT decide lapse —
            # that is exactly the delete-the-floor + roll-back-the-clock re-validation attack.
            # Never-expiring licenses (expires_at=0) and the Community floor itself don't consult
            # the floor for any expiry decision, so they are exempt.
            floor_unverifiable = (
                parsed.expires_at > 0
                and parsed.plan != "algenta_free"
                and floor_status != "ok"
            )
            if floor_unverifiable:
                if parsed.signed_epoch > 0:
                    # The token carries a vendor-signed mint time (signed_epoch is part of the
                    # RS256 payload, so the signature already covers it): re-seed the floor from
                    # the vendor signature and proceed normally. This is also what keeps the
                    # first-boot air-gapped activation ceremony working (no floor exists yet).
                    observe_time(float(parsed.signed_epoch), source="signed-epoch")
                    logger.info(
                        "time_floor_reseeded_from_signed_epoch",
                        device_id=parsed.device_id[:8],
                        signed_epoch=parsed.signed_epoch,
                    )
                    floor_unverifiable = False
                else:
                    logger.warning(
                        "time_floor_unverifiable",
                        floor_status=floor_status,
                        device_id=parsed.device_id[:8],
                    )
            if parsed.is_hard_expired() or floor_unverifiable:
                if floor_unverifiable:
                    logger.warning("license_lapse_unverifiable", device_id=parsed.device_id)
                else:
                    logger.warning("license_hard_expired", device_id=parsed.device_id)
                # Preferred refresh: prove possession of the bound device key → a fresh license
                # WITHOUT a full re-login. Dark: any failure (old server, unbound device, egress
                # denial) falls through to the Community settle below. A successful renewal also
                # re-anchors the lapse floor from the control plane's server_time.
                if api_key and not _local_license_required():
                    renewed = renew_license(api_key)
                    if renewed:
                        _save_license(renewed)
                        fresh = _parse_token(renewed, api_key)
                        if fresh and not fresh.is_hard_expired():
                            logger.info("license_auto_renewed", device_id=fresh.device_id[:8])
                            return _deny_if_revoked(fresh) or fresh
                # Renewal unavailable (offline / unbound / server unreachable). A previously valid
                # paid license settles at Community (free-forever), including in an air-gapped
                # deployment. Missing or invalid local licenses still fail closed below.
                if floor_unverifiable:
                    # Durable lapse: settle the floor PAST this token's hard-deny boundary so the
                    # verdict survives reboots — a wall-clock-seeded floor must never let a later
                    # boot re-validate the lapsed token as paid. The anchor is vendor-signed data
                    # (expires_at + grace_days are RS256 claims), never the host clock; deleting
                    # the floor again simply re-runs this same gate.
                    _settle_lapse_floor(parsed)
                    logger.info(
                        "license_downgraded_to_community",
                        reason="time-floor-unverifiable",
                        prev_plan=parsed.plan,
                        device_id=parsed.device_id[:8],
                    )
                    return _make_community_license(
                        api_key,
                        reason="time-floor-unverifiable",
                        deployment_id=parsed.deployment_id,
                    )
                logger.info(
                    "license_downgraded_to_community",
                    prev_plan=parsed.plan,
                    device_id=parsed.device_id[:8],
                )
                return _make_community_license(
                    api_key,
                    reason=(
                        f"Your {parsed.plan} license expired — running on Community (free-forever). "
                        f"Renew to restore {parsed.plan}."
                    ),
                    deployment_id=parsed.deployment_id,
                )
            # Revocation (P3b-D2): dormant for v1 (current); v2 → CRL-checked, fail-open.
            denied = _deny_if_revoked(parsed)
            if denied:
                return denied
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
                return _deny_if_revoked(parsed) or parsed
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
