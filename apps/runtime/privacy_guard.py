"""Shared runtime privacy-policy enforcement with local append-only audit entries."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from apps.privacy_policy import EgressClass, EgressDecision, evaluate_egress, policy_from_environment
from apps.runtime.ledger import append_event

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
