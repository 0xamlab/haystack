"""A4: the governed execution receipt — a versioned, typed contract.

WHAT THIS REPLACES. The receipt was `dict[str, Any]`, built inline as three keys:

    plan.receipt = {"executed_at": ..., "prepared_artifacts": [...], "action_count": N}

Untyped and unversioned. A consumer could not tell an old receipt from a new one, could not detect a
field being renamed, and had nothing to validate against. A receipt is the artifact an operator (or
an auditor, or a partner's compliance review) relies on to say *this execution happened, under this
plan, with this approval* -- so its shape is an interface, and an interface without a version cannot
be changed safely.

WHY A VERSION FIELD AND NOT JUST MORE KEYS. Adding keys is backwards-compatible; renaming or
re-meaning one is not. `receipt_version` lets a consumer branch instead of guess, and lets us
tighten the contract later without silently breaking a partner's parser. It is a string, not an int,
so a future "2.1" needs no schema change.

HONESTY ABOUT WHAT IS NOT HERE. `policy_snapshot_hash` is part of the envelope shape but is `None`
on the decision-plan path, because that path genuinely has no policy snapshot -- grep for
policy_snapshot across apps/api_server/services/decision_service/ returns nothing. It is declared
so the field is stable for the surfaces that DO carry policy evidence (decision_logs records
policy_snapshot_id / schema_snapshot_id / manifest_version), and so a consumer's parser does not
change shape when those surfaces adopt it. Populating it with a plan hash, or a digest of the
actions, would put something in a field named "policy snapshot" that is not one -- which on an
evidence artifact is worse than a null, because a null is legible and a mislabel is trusted.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# Bump ONLY for a breaking change (a field removed, renamed, or given a new meaning). Adding an
# optional field is backwards-compatible and does not need a bump.
RECEIPT_VERSION = "1"


class ExecutionReceipt(BaseModel):
    """Evidence that one approved plan executed exactly once, and under what authority."""

    receipt_version: str = Field(
        default=RECEIPT_VERSION,
        description="Receipt schema version. Bumped only on a breaking change.",
    )

    # ── what happened ──────────────────────────────────────────────────────────────────────────
    status: Literal["executed", "denied", "approval_required", "failed"] = Field(
        description="Terminal state of the governed operation this receipt describes."
    )
    code: str | None = Field(
        default=None,
        description=(
            "Machine-readable reason when status is not 'executed' -- the same DecisionServiceError "
            "code the HTTP layer maps (e.g. plan_hash_mismatch, invalid_nonce, approval_expired)."
        ),
    )
    retryable: bool = Field(
        default=False,
        description=(
            "Whether re-issuing the identical request could succeed. A policy denial is NOT "
            "retryable; an upstream timeout is. Stated explicitly so a caller does not have to "
            "infer intent from an HTTP status."
        ),
    )

    # ── correlation ────────────────────────────────────────────────────────────────────────────
    request_id: str | None = Field(
        default=None, description="Identifies the single HTTP call that produced this receipt."
    )
    trace_id: str | None = Field(
        default=None,
        description=(
            "W3C trace-id of the wider operation. One agent turn may produce several receipts; "
            "this is what lets them be reassembled afterwards."
        ),
    )
    idempotency_key: str | None = Field(
        default=None,
        description=(
            "The Idempotency-Key the caller supplied, echoed so a retry can be matched to its "
            "original outcome. None when the caller sent none."
        ),
    )

    # ── authority ──────────────────────────────────────────────────────────────────────────────
    execution_id: uuid.UUID = Field(
        description=(
            "Unique id for this execution attempt, minted at execute time and persisted with the "
            "receipt. Distinct from plan_id: the plan is what was authorised, this is the act."
        )
    )
    plan_hash: str | None = Field(
        default=None,
        description="Hash of the approved plan. An approval is bound to this exact value.",
    )
    approval_state: Literal["approved", "not_required", "pending", "rejected", "expired"] | None = (
        Field(
            default=None,
            description="Approval status at the moment of execution.",
        )
    )
    policy_snapshot_hash: str | None = Field(
        default=None,
        description=(
            "Content hash of the policy snapshot in force. None on the decision-plan path, which "
            "carries no policy snapshot -- deliberately null rather than filled with a value that "
            "is not a policy hash."
        ),
    )

    # ── payload ────────────────────────────────────────────────────────────────────────────────
    executed_at: datetime | None = Field(default=None, description="When execution completed.")
    result: dict[str, Any] | None = Field(
        default=None,
        description="Operation-specific result. Everything above is stable across operations.",
    )

    def to_stored(self) -> dict[str, Any]:
        """JSON-safe mapping for the receipt JSONB column.

        mode="json" so uuid/datetime become strings -- asyncpg cannot adapt them inside a JSONB
        payload, and a receipt that fails to persist is a receipt that does not exist.
        """
        return self.model_dump(mode="json")
