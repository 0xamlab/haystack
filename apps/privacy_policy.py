from __future__ import annotations

import hashlib
import ipaddress
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from apps.platform_contract_constants import (
    ALGENTA_OWNED_HOSTS,
    ALGENTA_OWNED_SUFFIXES,
    API_BASE_URL,
    PRIVATE_HOST_SUFFIXES,
    VENDOR_TELEMETRY_HOSTS,
)

DeploymentMode = Literal[
    "saas",
    "vpc",
    "self_hosted",
    "air_gapped",
    "hybrid_provider",
    "local_dev_daemon",
]
TelemetryMode = Literal["disabled", "local_audit", "control_plane_sync"]
MeteringMode = Literal["disabled", "local_audit", "control_plane_sync"]
EgressClass = Literal[
    "algenta_cloud",
    "vendor_telemetry",
    "customer_connector",
    "operator_service",
    "undeclared_public",
]
EgressDecisionValue = Literal["allow", "deny"]

_VALID_DEPLOYMENT_MODES = {
    "saas",
    "vpc",
    "self_hosted",
    "air_gapped",
    "hybrid_provider",
    "local_dev_daemon",
}
_VALID_TELEMETRY_MODES = {"disabled", "local_audit", "control_plane_sync"}
_VALID_METERING_MODES = {"disabled", "local_audit", "control_plane_sync"}
_ALGENTA_OWNED_HOSTS = frozenset(ALGENTA_OWNED_HOSTS)
_ALGENTA_OWNED_SUFFIXES = tuple(ALGENTA_OWNED_SUFFIXES)
_VENDOR_TELEMETRY_HOSTS = frozenset(VENDOR_TELEMETRY_HOSTS)
PRIVATE_HOST_SUFFIXES = tuple(PRIVATE_HOST_SUFFIXES)


class PrivacyConfigurationError(ValueError):
    def __init__(self, code: str, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class PrivacyPolicy:
    deployment_mode: DeploymentMode
    disable_cloud: bool
    disable_telemetry: bool
    telemetry_mode: TelemetryMode
    metering_mode: MeteringMode
    require_local_license: bool
    control_plane_url: str
    allow_outbound_network: bool
    egress_allowlist: tuple[str, ...]
    algenta_owned_hosts: tuple[str, ...]
    algenta_owned_suffixes: tuple[str, ...]
    vendor_telemetry_hosts: tuple[str, ...]
    private_host_suffixes: tuple[str, ...]

    @property
    def private_profile(self) -> bool:
        return self.deployment_mode in {"self_hosted", "air_gapped"}

    @property
    def algenta_cloud_enabled(self) -> bool:
        return not self.disable_cloud and self.allow_outbound_network

    @property
    def vendor_telemetry_enabled(self) -> bool:
        return (
            not self.disable_telemetry
            and self.telemetry_mode == "control_plane_sync"
            and self.allow_outbound_network
        )

    @property
    def customer_connector_egress_enabled(self) -> bool:
        return self.allow_outbound_network or bool(self.egress_allowlist)

    @property
    def undeclared_public_egress_allowed(self) -> bool:
        return self.allow_outbound_network

    @property
    def mandatory_heartbeat_enabled(self) -> bool:
        return self.metering_mode == "control_plane_sync" and self.allow_outbound_network

    @property
    def metering_flush_enabled(self) -> bool:
        return self.metering_mode == "control_plane_sync" and self.allow_outbound_network

    def as_report_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["egress_allowlist"] = list(self.egress_allowlist)
        payload["algenta_owned_hosts"] = list(self.algenta_owned_hosts)
        payload["algenta_owned_suffixes"] = list(self.algenta_owned_suffixes)
        payload["vendor_telemetry_hosts"] = list(self.vendor_telemetry_hosts)
        payload["private_host_suffixes"] = list(self.private_host_suffixes)
        payload["privacy_registry"] = {
            "algenta_owned_hosts": list(self.algenta_owned_hosts),
            "algenta_owned_suffixes": list(self.algenta_owned_suffixes),
            "vendor_telemetry_hosts": list(self.vendor_telemetry_hosts),
            "private_host_suffixes": list(self.private_host_suffixes),
        }
        payload.update(
            {
                "algenta_cloud_enabled": self.algenta_cloud_enabled,
                "vendor_telemetry_enabled": self.vendor_telemetry_enabled,
                "customer_connector_egress_enabled": self.customer_connector_egress_enabled,
                "undeclared_public_egress_allowed": self.undeclared_public_egress_allowed,
                "mandatory_heartbeat_enabled": self.mandatory_heartbeat_enabled,
                "metering_flush_enabled": self.metering_flush_enabled,
            }
        )
        return payload


@dataclass(frozen=True)
class EgressDestination:
    original: str
    host: str
    port: int | None
    normalized: str


@dataclass(frozen=True)
class EgressDecision:
    surface: str
    egress_class: EgressClass
    decision: EgressDecisionValue
    reason: str
    destination_host_hash: str
    destination_host_redacted: str
    deployment_mode: DeploymentMode
    service_name: str
    request_id: str | None = None

    def to_audit_metadata(self) -> dict[str, object]:
        return {
            "surface": self.surface,
            "egress_class": self.egress_class,
            "destination_host_hash": self.destination_host_hash,
            "destination_host_redacted": self.destination_host_redacted,
            "decision": self.decision,
            "reason": self.reason,
            "deployment_mode": self.deployment_mode,
            "service_name": self.service_name,
            "request_id": self.request_id,
        }


def _env(mapping: Mapping[str, str], key: str) -> str | None:
    raw = mapping.get(key)
    if raw is None:
        return None
    value = raw.strip()
    return value if value else None


def _parse_optional_bool(value: object | None) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    raise PrivacyConfigurationError(
        "invalid_boolean_value",
        "Privacy boolean settings must be true/false style values.",
        details={"value": value},
    )


def _normalized_mode(raw: object | None) -> DeploymentMode:
    value = "saas" if raw is None else str(raw).strip().lower()
    if value not in _VALID_DEPLOYMENT_MODES:
        raise PrivacyConfigurationError(
            "invalid_deployment_mode",
            "ALGENTA_DEPLOYMENT_MODE must be one of saas, vpc, self_hosted, air_gapped, hybrid_provider, local_dev_daemon.",
            details={"value": value},
        )
    return value  # type: ignore[return-value]


def _normalized_mode_value(
    value: object | None,
    *,
    default: TelemetryMode | MeteringMode,
    valid_values: set[str],
    field_name: str,
) -> TelemetryMode | MeteringMode:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized not in valid_values:
        raise PrivacyConfigurationError(
            "invalid_mode_value",
            f"{field_name} must be one of {', '.join(sorted(valid_values))}.",
            details={"field": field_name, "value": normalized},
        )
    return normalized  # type: ignore[return-value]


def _normalized_allowlist(raw: object | None) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        items = [item.strip().lower() for item in raw.split(",") if item.strip()]
        return tuple(dict.fromkeys(items))
    raise PrivacyConfigurationError(
        "invalid_allowlist",
        "ALGENTA_EGRESS_ALLOWLIST must be a comma-separated string.",
        details={"value": raw},
    )


def _base_host_patterns() -> tuple[str, ...]:
    parsed = urlparse(API_BASE_URL)
    base_host = parsed.hostname.strip().lower() if parsed.hostname else ""
    hosts = list(_ALGENTA_OWNED_HOSTS)
    if base_host and base_host not in hosts:
        hosts.append(base_host)
    return tuple(sorted(set(hosts)))


def _base_owned_suffixes() -> tuple[str, ...]:
    return tuple(ALGENTA_OWNED_SUFFIXES)


def _base_vendor_telemetry_hosts() -> tuple[str, ...]:
    return tuple(VENDOR_TELEMETRY_HOSTS)


def _base_private_host_suffixes() -> tuple[str, ...]:
    return tuple(PRIVATE_HOST_SUFFIXES)


def build_privacy_policy(
    *,
    deployment_mode: object | None = None,
    disable_cloud: object | None = None,
    disable_telemetry: object | None = None,
    telemetry_mode: object | None = None,
    metering_mode: object | None = None,
    require_local_license: object | None = None,
    control_plane_url: object | None = None,
    allow_outbound_network: object | None = None,
    egress_allowlist: object | None = None,
    agent_core_url: object | None = None,
    supabase_url: object | None = None,
    base_url_fallback: str | None = None,
) -> PrivacyPolicy:
    mode = _normalized_mode(deployment_mode)
    private_profile = mode in {"self_hosted", "air_gapped"}
    effective_disable_cloud = (
        _parse_optional_bool(disable_cloud)
        if disable_cloud is not None
        else private_profile
    )
    assert effective_disable_cloud is not None
    effective_disable_telemetry = (
        _parse_optional_bool(disable_telemetry)
        if disable_telemetry is not None
        else private_profile
    )
    assert effective_disable_telemetry is not None
    effective_allow_outbound = (
        _parse_optional_bool(allow_outbound_network)
        if allow_outbound_network is not None
        else (not private_profile)
    )
    assert effective_allow_outbound is not None
    effective_require_local_license = (
        _parse_optional_bool(require_local_license)
        if require_local_license is not None
        else mode == "air_gapped"
    )
    assert effective_require_local_license is not None

    if effective_disable_telemetry:
        default_telemetry_mode: TelemetryMode = "local_audit" if private_profile else "disabled"
    else:
        default_telemetry_mode = "control_plane_sync"
    if private_profile:
        default_metering_mode: MeteringMode = "local_audit"
    else:
        default_metering_mode = "control_plane_sync"
    effective_telemetry_mode = _normalized_mode_value(
        telemetry_mode,
        default=default_telemetry_mode,
        valid_values=_VALID_TELEMETRY_MODES,
        field_name="ALGENTA_TELEMETRY_MODE",
    )
    effective_metering_mode = _normalized_mode_value(
        metering_mode,
        default=default_metering_mode,
        valid_values=_VALID_METERING_MODES,
        field_name="ALGENTA_METERING_MODE",
    )

    explicit_control_plane = None
    if control_plane_url is not None:
        explicit_control_plane = str(control_plane_url).strip()
    if not explicit_control_plane and base_url_fallback:
        explicit_control_plane = base_url_fallback.strip()
    if not explicit_control_plane and not effective_disable_cloud:
        explicit_control_plane = API_BASE_URL
    effective_control_plane_url = (explicit_control_plane or "").rstrip("/")

    # Self-host trust: an operator who explicitly configures the agent-core sidecar
    # URL has opted into reaching it, so trust that exact host for egress. Without
    # this, a sidecar on a private/loopback address (the self-hosted default) is
    # unreachable behind the SSRF guard and agentic planning fails closed with an
    # opaque EgressPolicyDeniedError. Only the configured host is allowlisted — this
    # never enables general outbound egress.
    effective_allowlist = list(_normalized_allowlist(egress_allowlist))
    if agent_core_url:
        try:
            agent_core_host = parse_egress_destination(str(agent_core_url)).host
        except PrivacyConfigurationError:
            agent_core_host = ""
        if agent_core_host and agent_core_host not in effective_allowlist:
            effective_allowlist.append(agent_core_host)
    # Same self-host trust for the Supabase identity provider: an operator who configures
    # SUPABASE_URL has opted into reaching it for the offline JWKS fetch that powers /byok. Trust
    # exactly that host so the fetch isn't blocked by the SSRF/fail-closed guard (which would
    # otherwise surface as an opaque egress denial). Only the configured host is allowlisted.
    if supabase_url:
        try:
            supabase_host = parse_egress_destination(str(supabase_url)).host
        except PrivacyConfigurationError:
            supabase_host = ""
        if supabase_host and supabase_host not in effective_allowlist:
            effective_allowlist.append(supabase_host)

    policy = PrivacyPolicy(
        deployment_mode=mode,
        disable_cloud=effective_disable_cloud,
        disable_telemetry=effective_disable_telemetry,
        telemetry_mode=effective_telemetry_mode,
        metering_mode=effective_metering_mode,
        require_local_license=effective_require_local_license,
        control_plane_url=effective_control_plane_url,
        allow_outbound_network=effective_allow_outbound,
        egress_allowlist=tuple(effective_allowlist),
        algenta_owned_hosts=_base_host_patterns(),
        algenta_owned_suffixes=_base_owned_suffixes(),
        vendor_telemetry_hosts=_base_vendor_telemetry_hosts(),
        private_host_suffixes=_base_private_host_suffixes(),
    )
    validate_privacy_policy(policy)
    return policy


def policy_from_environment(
    env: Mapping[str, str] | None = None,
    *,
    base_url_fallback: str | None = None,
) -> PrivacyPolicy:
    mapping = os.environ if env is None else env
    control_plane_url = (
        _env(mapping, "ALGENTA_CONTROL_PLANE_URL")
        or _env(mapping, "ALGENTA_BASE_URL")
        or _env(mapping, "DE_BASE_URL")
        or _env(mapping, "ALGENTA_API_URL")
    )
    return build_privacy_policy(
        deployment_mode=_env(mapping, "ALGENTA_DEPLOYMENT_MODE"),
        disable_cloud=_env(mapping, "ALGENTA_DISABLE_CLOUD"),
        disable_telemetry=_env(mapping, "ALGENTA_DISABLE_TELEMETRY"),
        telemetry_mode=_env(mapping, "ALGENTA_TELEMETRY_MODE"),
        metering_mode=_env(mapping, "ALGENTA_METERING_MODE"),
        require_local_license=_env(mapping, "ALGENTA_REQUIRE_LOCAL_LICENSE"),
        control_plane_url=control_plane_url,
        allow_outbound_network=_env(mapping, "ALGENTA_ALLOW_OUTBOUND_NETWORK"),
        egress_allowlist=_env(mapping, "ALGENTA_EGRESS_ALLOWLIST"),
        agent_core_url=_env(mapping, "ALGENTA_AGENT_CORE_URL"),
        supabase_url=_env(mapping, "SUPABASE_URL") or _env(mapping, "NEXT_PUBLIC_SUPABASE_URL"),
        base_url_fallback=base_url_fallback,
    )


def validate_privacy_policy(policy: PrivacyPolicy) -> None:
    if policy.disable_cloud and policy.control_plane_url:
        destination = parse_egress_destination(policy.control_plane_url)
        if is_algenta_owned_destination(destination.host):
            raise PrivacyConfigurationError(
                "algenta_cloud_disabled_with_algenta_control_plane",
                "ALGENTA_DISABLE_CLOUD=1 cannot be combined with an Codna-owned ALGENTA_CONTROL_PLANE_URL.",
                details={"control_plane_url": policy.control_plane_url},
            )

    if policy.telemetry_mode == "control_plane_sync" or policy.metering_mode == "control_plane_sync":
        if not policy.control_plane_url:
            raise PrivacyConfigurationError(
                "control_plane_url_required",
                "control_plane_sync requires a non-empty ALGENTA_CONTROL_PLANE_URL.",
            )
        decision = evaluate_egress(
            policy,
            policy.control_plane_url,
            surface="privacy-validation",
            service_name="privacy-policy",
            explicit_configured=True,
            egress_class=(
                "algenta_cloud"
                if is_algenta_owned_destination(parse_egress_destination(policy.control_plane_url).host)
                else "operator_service"
            ),
        )
        if decision.decision == "deny":
            raise PrivacyConfigurationError(
                "control_plane_url_denied",
                "control_plane_sync requires a permitted ALGENTA_CONTROL_PLANE_URL under the active egress policy.",
                details={"reason": decision.reason},
            )

    if policy.deployment_mode == "air_gapped" and (
        policy.telemetry_mode == "control_plane_sync" or policy.metering_mode == "control_plane_sync"
    ):
        raise PrivacyConfigurationError(
            "air_gapped_control_plane_sync_forbidden",
            "air_gapped deployments cannot use control_plane_sync telemetry or metering.",
        )


def resolve_runtime_license_path() -> Path:
    return Path(os.environ.get("ALGENTA_RUNTIME_DIR", Path.home() / ".algenta" / "runtime")) / "license.jwt"


def local_license_required_for_runtime(env: dict[str, str] | os._Environ[str] | None = None) -> bool:
    return policy_from_environment(env).require_local_license


def self_hosted_private_runtime_without_commercial_plane(
    env: Mapping[str, str] | None = None,
) -> bool:
    policy = policy_from_environment(env)
    return policy.deployment_mode == "self_hosted" and not policy.require_local_license


def parse_egress_destination(value: str) -> EgressDestination:
    raw = value.strip()
    if not raw:
        raise PrivacyConfigurationError(
            "invalid_egress_destination",
            "Egress destination must be a non-empty host or URL.",
        )
    candidate = raw if "://" in raw else f"https://{raw}"
    parsed = urlparse(candidate)
    if not parsed.hostname:
        raise PrivacyConfigurationError(
            "invalid_egress_destination",
            "Egress destination must include a valid host.",
            details={"value": value},
        )
    host = parsed.hostname.strip().lower()
    port = parsed.port
    normalized = f"{host}:{port}" if port else host
    return EgressDestination(original=value, host=host, port=port, normalized=normalized)


def is_algenta_owned_destination(host: str) -> bool:
    normalized = host.strip().lower()
    if normalized in _ALGENTA_OWNED_HOSTS:
        return True
    return any(normalized.endswith(suffix) for suffix in _ALGENTA_OWNED_SUFFIXES)


def is_vendor_telemetry_destination(host: str) -> bool:
    normalized = host.strip().lower()
    if normalized in _VENDOR_TELEMETRY_HOSTS:
        return True
    return normalized.endswith(".sentry.io")


def _destination_hash(normalized_host: str) -> str:
    return hashlib.sha256(normalized_host.encode("utf-8")).hexdigest()


def _private_host(host: str) -> bool:
    normalized = host.strip().lower()
    if normalized in {"localhost", "127.0.0.1", "::1"}:
        return True
    if any(normalized.endswith(suffix) for suffix in PRIVATE_HOST_SUFFIXES):
        return True
    try:
        ip = ipaddress.ip_address(normalized)
    except ValueError:
        return normalized.endswith(".internal")
    return bool(
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
    )


def redact_destination_host(host: str) -> str:
    normalized = host.strip().lower()
    if is_algenta_owned_destination(normalized) or is_vendor_telemetry_destination(normalized):
        return normalized
    if _private_host(normalized):
        return "internal-host"
    parts = normalized.split(".")
    if len(parts) >= 2:
        return f"*.{parts[-2]}.{parts[-1]}"
    return "public-host"


def destination_matches_allowlist(
    destination: EgressDestination,
    allowlist: tuple[str, ...],
) -> bool:
    for item in allowlist:
        pattern = item.strip().lower()
        if not pattern:
            continue
        if pattern.startswith("*."):
            suffix = pattern[1:]
            if destination.host.endswith(suffix):
                return True
            continue
        if ":" in pattern:
            if destination.normalized == pattern:
                return True
            continue
        if destination.host == pattern:
            return True
    return False


def classify_egress_destination(
    destination: EgressDestination,
    *,
    explicit_egress_class: EgressClass | None = None,
    explicit_configured: bool,
) -> EgressClass:
    if explicit_egress_class is not None:
        return explicit_egress_class
    if is_algenta_owned_destination(destination.host):
        return "algenta_cloud"
    if is_vendor_telemetry_destination(destination.host):
        return "vendor_telemetry"
    if explicit_configured:
        return "customer_connector"
    return "undeclared_public"


def evaluate_egress(
    policy: PrivacyPolicy,
    destination: str,
    *,
    surface: str,
    service_name: str,
    explicit_configured: bool = False,
    egress_class: EgressClass | None = None,
    request_id: str | None = None,
) -> EgressDecision:
    target = parse_egress_destination(destination)
    classified = classify_egress_destination(
        target,
        explicit_egress_class=egress_class,
        explicit_configured=explicit_configured,
    )
    host_hash = _destination_hash(target.normalized)
    redacted = redact_destination_host(target.host)

    if classified == "algenta_cloud":
        if policy.disable_cloud or not policy.allow_outbound_network:
            return EgressDecision(
                surface=surface,
                egress_class=classified,
                decision="deny",
                reason="algenta_cloud_disabled",
                destination_host_hash=host_hash,
                destination_host_redacted=redacted,
                deployment_mode=policy.deployment_mode,
                service_name=service_name,
                request_id=request_id,
            )
        return EgressDecision(
            surface=surface,
            egress_class=classified,
            decision="allow",
            reason="algenta_cloud_enabled",
            destination_host_hash=host_hash,
            destination_host_redacted=redacted,
            deployment_mode=policy.deployment_mode,
            service_name=service_name,
            request_id=request_id,
        )

    if classified == "vendor_telemetry":
        if (
            policy.disable_telemetry
            or policy.telemetry_mode != "control_plane_sync"
            or not policy.allow_outbound_network
        ):
            reason = "vendor_telemetry_disabled"
            return EgressDecision(
                surface=surface,
                egress_class=classified,
                decision="deny",
                reason=reason,
                destination_host_hash=host_hash,
                destination_host_redacted=redacted,
                deployment_mode=policy.deployment_mode,
                service_name=service_name,
                request_id=request_id,
            )
        return EgressDecision(
            surface=surface,
            egress_class=classified,
            decision="allow",
            reason="vendor_telemetry_enabled",
            destination_host_hash=host_hash,
            destination_host_redacted=redacted,
            deployment_mode=policy.deployment_mode,
            service_name=service_name,
            request_id=request_id,
        )

    if classified in {"customer_connector", "operator_service"}:
        if explicit_configured and destination_matches_allowlist(target, policy.egress_allowlist):
            return EgressDecision(
                surface=surface,
                egress_class=classified,
                decision="allow",
                reason="destination_allowlisted",
                destination_host_hash=host_hash,
                destination_host_redacted=redacted,
                deployment_mode=policy.deployment_mode,
                service_name=service_name,
                request_id=request_id,
            )
        if policy.allow_outbound_network:
            return EgressDecision(
                surface=surface,
                egress_class=classified,
                decision="allow",
                reason="outbound_network_enabled",
                destination_host_hash=host_hash,
                destination_host_redacted=redacted,
                deployment_mode=policy.deployment_mode,
                service_name=service_name,
                request_id=request_id,
            )
        return EgressDecision(
            surface=surface,
            egress_class=classified,
            decision="deny",
            reason="destination_not_allowlisted",
            destination_host_hash=host_hash,
            destination_host_redacted=redacted,
            deployment_mode=policy.deployment_mode,
            service_name=service_name,
            request_id=request_id,
        )

    if policy.allow_outbound_network:
        return EgressDecision(
            surface=surface,
            egress_class=classified,
            decision="allow",
            reason="undeclared_public_egress_enabled",
            destination_host_hash=host_hash,
            destination_host_redacted=redacted,
            deployment_mode=policy.deployment_mode,
            service_name=service_name,
            request_id=request_id,
        )

    return EgressDecision(
        surface=surface,
        egress_class=classified,
        decision="deny",
        reason="undeclared_public_egress_disabled",
        destination_host_hash=host_hash,
        destination_host_redacted=redacted,
        deployment_mode=policy.deployment_mode,
        service_name=service_name,
        request_id=request_id,
    )
