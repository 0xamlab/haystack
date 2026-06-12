"""Shared runtime privacy-policy enforcement with local append-only audit entries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from apps.privacy_policy import (
    EgressClass,
    EgressDecision,
    evaluate_egress,
    is_algenta_owned_destination,
    policy_from_environment,
)
from apps.runtime.ledger import append_event

if TYPE_CHECKING:
    import urllib.request

_RUNTIME_EGRESS_ACTION = "privacy_egress"


class RuntimeEgressPolicyDeniedError(RuntimeError):
    """Raised when runtime outbound egress is blocked by the active privacy policy."""

    def __init__(self, decision: EgressDecision) -> None:
        self.decision = decision
        super().__init__(
            f"Egress blocked by privacy policy for surface '{decision.surface}' "
            f"({decision.reason})."
        )


def evaluate_runtime_egress_policy(
    destination: str,
    *,
    surface: str,
    explicit_configured: bool = False,
    egress_class: EgressClass | None = None,
    request_id: str | None = None,
) -> EgressDecision:
    return evaluate_egress(
        policy_from_environment(),
        destination,
        surface=surface,
        service_name="runtime",
        explicit_configured=explicit_configured,
        egress_class=egress_class,
        request_id=request_id,
    )


def record_runtime_egress_event(decision: EgressDecision) -> dict[str, Any]:
    task_id = decision.request_id or f"privacy_{decision.surface}_{decision.destination_host_hash[:16]}"
    return append_event(
        task_id=task_id,
        surface="runtime",
        action=_RUNTIME_EGRESS_ACTION,
        status=decision.decision,
        target=decision.destination_host_redacted,
        request_id=decision.request_id or "",
        success=decision.decision == "allow",
        error="" if decision.decision == "allow" else decision.reason,
        sync_state="local_only",
        details=decision.to_audit_metadata(),
    )


def enforce_runtime_egress(
    destination: str,
    *,
    surface: str,
    explicit_configured: bool = False,
    egress_class: EgressClass | None = None,
    request_id: str | None = None,
) -> EgressDecision:
    decision = evaluate_runtime_egress_policy(
        destination,
        surface=surface,
        explicit_configured=explicit_configured,
        egress_class=egress_class,
        request_id=request_id,
    )
    record_runtime_egress_event(decision)
    if decision.decision == "deny":
        raise RuntimeEgressPolicyDeniedError(decision)
    return decision


def validated_runtime_egress_url(
    destination: str,
    *,
    surface: str,
    field_name: str,
    explicit_configured: bool = False,
    egress_class: EgressClass | None = None,
    request_id: str | None = None,
    record: bool = True,
) -> str:
    normalized = destination.rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field_name} must use an absolute http(s) URL.")
    if record:
        enforce_runtime_egress(
            normalized,
            surface=surface,
            explicit_configured=explicit_configured,
            egress_class=egress_class,
            request_id=request_id,
        )
    else:
        decision = evaluate_runtime_egress_policy(
            normalized,
            surface=surface,
            explicit_configured=explicit_configured,
            egress_class=egress_class,
            request_id=request_id,
        )
        if decision.decision == "deny":
            raise RuntimeEgressPolicyDeniedError(decision)
    return normalized


def _classify_runtime_destination(url: str) -> EgressClass:
    """Match the egress_class derivation the validated_*_url helpers use, so a transport-time
    enforce agrees with any prior base-URL enforce on the same host (no class-mismatch regression)."""
    host = urlparse(url).hostname
    return "algenta_cloud" if host and is_algenta_owned_destination(host) else "operator_service"


def runtime_urlopen(
    request: "urllib.request.Request",
    *,
    surface: str,
    explicit_configured: bool = True,
    egress_class: EgressClass | None = None,
    request_id: str | None = None,
    timeout: float | None = None,
    urlopen_fn: Any = None,
):
    """Enforce the runtime egress policy on the request URL BEFORE dispatch, then urlopen.

    The runtime plane's approved outbound transport — fails closed (a policy deny raises
    RuntimeEgressPolicyDeniedError before any socket opens). Only the redacted host/hash reaches the
    audit ledger; request headers (which carry the bearer token) never do. The api_server
    egress_guard is intentionally NOT imported here — the runtime/SDK transport boundary stays
    self-contained. egress_class defaults to the same host-based classification the validated_*_url
    helpers use, so routing a site that already validated its base URL does not change the verdict."""
    import urllib.request

    url = request.full_url
    enforce_runtime_egress(
        url,
        surface=surface,
        explicit_configured=explicit_configured,
        egress_class=egress_class or _classify_runtime_destination(url),
        request_id=request_id,
    )
    opener = urlopen_fn or urllib.request.urlopen
    if timeout is not None:
        return opener(request, timeout=timeout)  # noqa: S310
    return opener(request)  # noqa: S310


async def runtime_http_request(
    *,
    method: str,
    url: str,
    surface: str,
    explicit_configured: bool = True,
    egress_class: EgressClass | None = None,
    request_id: str | None = None,
    client: Any = None,
    client_kwargs: dict[str, Any] | None = None,
    **request_kwargs: Any,
):
    """Async counterpart of runtime_urlopen for httpx-based runtime transport (e.g. the SDK cloud
    fallback). Enforces the runtime egress policy on `url` BEFORE dispatch (deny raises before any
    socket); headers never enter the ledger; the api_server egress_guard is NOT imported."""
    import httpx

    enforce_runtime_egress(
        url,
        surface=surface,
        explicit_configured=explicit_configured,
        egress_class=egress_class or _classify_runtime_destination(url),
        request_id=request_id,
    )

    async def _dispatch(async_client: "httpx.AsyncClient") -> "httpx.Response":
        method_name = method.strip().lower()
        specialized = getattr(async_client, method_name, None)
        if callable(specialized):
            return await specialized(url, **request_kwargs)
        return await async_client.request(method=method, url=url, **request_kwargs)

    if client is not None:
        return await _dispatch(client)
    async with httpx.AsyncClient(**(client_kwargs or {})) as managed_client:
        return await _dispatch(managed_client)
