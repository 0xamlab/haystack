"""
Execution Policy Service

Per-org configurable safety gates that govern when autonomous execution is allowed.
All checks apply to POST /v1/decisions/{id}/execute and trigger auto_execute.

Policy is stored in-memory (per-process) with sensible safe defaults.
A future migration can persist this to a DB table for multi-instance deployments.

Gates (evaluated in order):
  1. Idempotency    — already executed → block unless force=True
  2. Confidence     — confidence < min_confidence → block unless override_safety=True
  3. Risk floor     — p5 < -risk_floor → block unless override_safety=True
  4. Calibration    — auto_execute requires is_reliable (when require_calibration=True)

Design principle: default to SAFE
  - min_confidence defaults to 0.5 (reject majority-uncertain decisions)
  - require_calibration defaults to True (no blind autonomous execution)
  - allow_reexecution defaults to False (idempotent by default)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

# ─── Policy definition ────────────────────────────────────────────────────────

@dataclass
class ExecutionPolicy:
    """
    Configurable safety policy for an org's autonomous execution.

    All thresholds can be loosened via the PATCH /v1/execution/policy endpoint.
    Set ``override_safety=True`` in an execute request to bypass confidence/risk gates
    for a single call (requires explicit intent signal from caller).
    """
    min_confidence: float = 0.5
    """
    Minimum confidence required to allow execution.
    Decisions below this are blocked. Use override_safety=True to bypass.
    """

    risk_floor: float | None = None
    """
    Maximum acceptable downside loss (absolute value). If p5 < -risk_floor, block.
    Example: risk_floor=10000 blocks any decision whose worst-case (p5) is worse than -10000.
    None = no floor check.
    """

    require_calibration: bool = True
    """
    When True, trigger auto_execute is disabled until the org has ≥5 recorded outcomes
    (calibration.is_reliable). Manual execution (POST /execute) is unaffected.
    """

    allow_reexecution: bool = False
    """
    When False (default), a decision that already has execution_status='delivered'
    cannot be re-executed unless force=True is passed. Prevents double-actions.
    """

    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        return {
            "min_confidence":        self.min_confidence,
            "risk_floor":            self.risk_floor,
            "require_calibration":   self.require_calibration,
            "allow_reexecution":     self.allow_reexecution,
            "updated_at":            self.updated_at.isoformat(),
        }


# ── In-process policy cache (per org) ─────────────────────────────────────────
_POLICY_STORE: dict[str, ExecutionPolicy] = {}


def get_policy(org_id: str) -> ExecutionPolicy:
    """Return the org's execution policy. Returns safe defaults if not configured."""
    return _POLICY_STORE.get(org_id, ExecutionPolicy())


def set_policy(org_id: str, **kwargs) -> ExecutionPolicy:
    """Update policy fields. Unknown fields are silently ignored."""
    policy = _POLICY_STORE.get(org_id, ExecutionPolicy())
    allowed = {"min_confidence", "risk_floor", "require_calibration", "allow_reexecution"}
    for k, v in kwargs.items():
        if k in allowed:
            setattr(policy, k, v)
    policy.updated_at = datetime.now(UTC)
    _POLICY_STORE[org_id] = policy
    return policy


# ── Gate evaluation ────────────────────────────────────────────────────────────

@dataclass
class PolicyViolation:
    gate: Literal["idempotency", "confidence", "risk_floor"]
    detail: str
    override_hint: str


def check_execution_gates(
    policy: ExecutionPolicy,
    confidence: float | None,
    risk_p5: float | None,
    already_executed: bool,
    force: bool = False,
    override_safety: bool = False,
) -> PolicyViolation | None:
    """
    Evaluate all safety gates in order.

    Returns the first violation, or None if execution is allowed.

    Args:
        force:           bypass the idempotency gate only
        override_safety: bypass confidence + risk_floor gates
    """
    # Gate 1 — Idempotency
    if already_executed and not policy.allow_reexecution and not force:
        return PolicyViolation(
            gate="idempotency",
            detail="This decision was already executed. Pass force=true to re-execute.",
            override_hint="Add force=true to the request body.",
        )

    # Gate 2 — Confidence
    if not override_safety and confidence is not None:
        if confidence < policy.min_confidence:
            return PolicyViolation(
                gate="confidence",
                detail=(
                    f"confidence {confidence:.2%} is below policy minimum "
                    f"{policy.min_confidence:.2%}."
                ),
                override_hint="Add override_safety=true to bypass this gate.",
            )

    # Gate 3 — Risk floor
    if not override_safety and policy.risk_floor is not None and risk_p5 is not None:
        if risk_p5 < -policy.risk_floor:
            return PolicyViolation(
                gate="risk_floor",
                detail=(
                    f"worst-case outcome p5={risk_p5:,.0f} exceeds risk floor "
                    f"-{policy.risk_floor:,.0f}."
                ),
                override_hint="Add override_safety=true to bypass this gate.",
            )

    return None


def check_auto_execute_allowed(
    policy: ExecutionPolicy,
    calibration_is_reliable: bool,
) -> tuple[bool, str | None]:
    """
    Check whether a trigger's auto_execute should proceed.

    Returns (allowed, reason_if_blocked).
    """
    if policy.require_calibration and not calibration_is_reliable:
        return False, (
            "auto_execute skipped: calibration not yet reliable "
            "(record outcomes via PATCH /v1/decisions/{id}/outcome to enable)"
        )
    return True, None
