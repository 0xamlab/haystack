"""Repository interface for the Decision Service + an in-memory implementation.

The service depends only on :class:`DecisionRepository`, so the workflow logic is testable
without a database. The SQLAlchemy-backed implementation (used by the app) maps these records
to the ORM aggregate; the in-memory one stores them in dicts and is used by unit tests.

All reads are org/workspace scoped, mirroring ``workspace_scope_clauses``: always filter by
``org_id``; when the caller carries a ``workspace_id`` (platform key + X-Workspace-Id), also
require the row's ``workspace_id`` to match. A tenant key never carries a workspace_id.
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from .records import (
    ApprovalRecord,
    DecisionCaseRecord,
    EvidenceRecord,
    ExecutionPlanRecord,
    OutcomeRecord,
    RecommendationRecord,
    RevisionRecord,
    RunRecord,
)

__all__ = ["DecisionRepository", "InMemoryDecisionRepository"]


class DecisionRepository(Protocol):
    """Persistence boundary for the decision aggregate (async to match the app)."""

    async def add_case(self, case: DecisionCaseRecord) -> DecisionCaseRecord: ...
    async def get_case(
        self, case_id: uuid.UUID, org_id: uuid.UUID, workspace_id: uuid.UUID | None
    ) -> DecisionCaseRecord | None: ...
    async def update_case(self, case: DecisionCaseRecord) -> DecisionCaseRecord: ...
    async def set_case_status(
        self, case_id: uuid.UUID, org_id: uuid.UUID, workspace_id: uuid.UUID | None, status: str
    ) -> None:
        """Narrow, status-only update — never blind-applies a stale case snapshot."""
        ...

    async def add_revision(self, rev: RevisionRecord) -> RevisionRecord: ...
    async def get_revision(
        self, revision_id: uuid.UUID, org_id: uuid.UUID, workspace_id: uuid.UUID | None
    ) -> RevisionRecord | None: ...

    async def add_evidence(self, ev: EvidenceRecord) -> EvidenceRecord: ...
    async def get_evidence(
        self, evidence_id: uuid.UUID, org_id: uuid.UUID, workspace_id: uuid.UUID | None
    ) -> EvidenceRecord | None: ...

    async def add_run(self, run: RunRecord) -> RunRecord: ...
    async def get_run(
        self, run_id: uuid.UUID, org_id: uuid.UUID, workspace_id: uuid.UUID | None
    ) -> RunRecord | None: ...
    async def update_run(self, run: RunRecord) -> RunRecord: ...

    async def add_recommendation(self, rec: RecommendationRecord) -> RecommendationRecord: ...
    async def get_recommendation_for_run(
        self, run_id: uuid.UUID, org_id: uuid.UUID, workspace_id: uuid.UUID | None
    ) -> RecommendationRecord | None: ...

    async def add_plan(self, plan: ExecutionPlanRecord) -> ExecutionPlanRecord: ...
    async def get_plan(
        self, plan_id: uuid.UUID, org_id: uuid.UUID, workspace_id: uuid.UUID | None
    ) -> ExecutionPlanRecord | None: ...
    async def update_plan(self, plan: ExecutionPlanRecord) -> ExecutionPlanRecord: ...
    async def transition_plan_state(
        self, plan: ExecutionPlanRecord, from_state: str
    ) -> bool:
        """Compare-and-set: apply ``plan`` only if the stored row is still in ``from_state``.

        Returns True when the transition won; False when another request already moved the
        plan out of ``from_state`` (the caller must treat that as a lost race, not retry).
        """
        ...

    async def add_approval(self, ap: ApprovalRecord) -> ApprovalRecord: ...
    async def update_approval(self, ap: ApprovalRecord) -> ApprovalRecord: ...
    async def get_approvals_for_case(
        self, case_id: uuid.UUID, org_id: uuid.UUID, workspace_id: uuid.UUID | None
    ) -> list[ApprovalRecord]: ...
    async def find_approval_by_idempotency(
        self, idempotency_key: str, org_id: uuid.UUID
    ) -> ApprovalRecord | None:
        """ORG-wide lookup — must match the scope of the DB unique index
        ``uq_decision_approvals_org_idempotency`` exactly, or a same-key insert from another
        workspace bypasses the pre-check and dies as an IntegrityError."""
        ...

    async def add_outcome(self, outcome: OutcomeRecord) -> OutcomeRecord: ...


def _visible(rec: Any, org_id: uuid.UUID, workspace_id: uuid.UUID | None) -> bool:
    if rec.org_id != org_id:
        return False
    if workspace_id is not None and rec.workspace_id != workspace_id:
        return False
    return True


class InMemoryDecisionRepository:
    """Dict-backed repository for DB-free unit tests. Stores copies to mimic persistence."""

    def __init__(self) -> None:
        self._cases: dict[uuid.UUID, DecisionCaseRecord] = {}
        self._revisions: dict[uuid.UUID, RevisionRecord] = {}
        self._evidence: dict[uuid.UUID, EvidenceRecord] = {}
        self._runs: dict[uuid.UUID, RunRecord] = {}
        self._recs: dict[uuid.UUID, RecommendationRecord] = {}
        self._plans: dict[uuid.UUID, ExecutionPlanRecord] = {}
        self._approvals: dict[uuid.UUID, ApprovalRecord] = {}
        self._outcomes: dict[uuid.UUID, OutcomeRecord] = {}

    # ── cases ──
    async def add_case(self, case: DecisionCaseRecord) -> DecisionCaseRecord:
        self._cases[case.id] = case.model_copy(deep=True)
        return case

    async def get_case(self, case_id, org_id, workspace_id):  # type: ignore[no-untyped-def]
        c = self._cases.get(case_id)
        return c.model_copy(deep=True) if c and _visible(c, org_id, workspace_id) else None

    async def update_case(self, case: DecisionCaseRecord) -> DecisionCaseRecord:
        self._cases[case.id] = case.model_copy(deep=True)
        return case

    async def set_case_status(self, case_id, org_id, workspace_id, status):  # type: ignore[no-untyped-def]
        c = self._cases.get(case_id)
        if c is not None and _visible(c, org_id, workspace_id):
            c.status = status  # narrow: mutate only status on the STORED copy

    # ── revisions ──
    async def add_revision(self, rev: RevisionRecord) -> RevisionRecord:
        self._revisions[rev.id] = rev.model_copy(deep=True)
        return rev

    async def get_revision(self, revision_id, org_id, workspace_id):  # type: ignore[no-untyped-def]
        r = self._revisions.get(revision_id)
        return r.model_copy(deep=True) if r and _visible(r, org_id, workspace_id) else None

    # ── evidence ──
    async def add_evidence(self, ev: EvidenceRecord) -> EvidenceRecord:
        self._evidence[ev.id] = ev.model_copy(deep=True)
        return ev

    async def get_evidence(self, evidence_id, org_id, workspace_id):  # type: ignore[no-untyped-def]
        e = self._evidence.get(evidence_id)
        return e.model_copy(deep=True) if e and _visible(e, org_id, workspace_id) else None

    # ── runs ──
    async def add_run(self, run: RunRecord) -> RunRecord:
        self._runs[run.id] = run.model_copy(deep=True)
        return run

    async def get_run(self, run_id, org_id, workspace_id):  # type: ignore[no-untyped-def]
        r = self._runs.get(run_id)
        return r.model_copy(deep=True) if r and _visible(r, org_id, workspace_id) else None

    async def update_run(self, run: RunRecord) -> RunRecord:
        self._runs[run.id] = run.model_copy(deep=True)
        return run

    # ── recommendations ──
    async def add_recommendation(self, rec: RecommendationRecord) -> RecommendationRecord:
        self._recs[rec.id] = rec.model_copy(deep=True)
        return rec

    async def get_recommendation_for_run(self, run_id, org_id, workspace_id):  # type: ignore[no-untyped-def]
        for r in self._recs.values():
            if r.run_id == run_id and _visible(r, org_id, workspace_id):
                return r.model_copy(deep=True)
        return None

    # ── plans ──
    async def add_plan(self, plan: ExecutionPlanRecord) -> ExecutionPlanRecord:
        self._plans[plan.id] = plan.model_copy(deep=True)
        return plan

    async def get_plan(self, plan_id, org_id, workspace_id):  # type: ignore[no-untyped-def]
        p = self._plans.get(plan_id)
        return p.model_copy(deep=True) if p and _visible(p, org_id, workspace_id) else None

    async def update_plan(self, plan: ExecutionPlanRecord) -> ExecutionPlanRecord:
        self._plans[plan.id] = plan.model_copy(deep=True)
        return plan

    async def transition_plan_state(self, plan: ExecutionPlanRecord, from_state: str) -> bool:
        stored = self._plans.get(plan.id)
        if stored is None or not _visible(stored, plan.org_id, plan.workspace_id):
            return False
        # No awaits between check and set — atomic under the single-threaded event loop.
        if stored.lifecycle_state != from_state:
            return False
        self._plans[plan.id] = plan.model_copy(deep=True)
        return True

    # ── approvals ──
    async def add_approval(self, ap: ApprovalRecord) -> ApprovalRecord:
        self._approvals[ap.id] = ap.model_copy(deep=True)
        return ap

    async def update_approval(self, ap: ApprovalRecord) -> ApprovalRecord:
        self._approvals[ap.id] = ap.model_copy(deep=True)
        return ap

    async def get_approvals_for_case(self, case_id, org_id, workspace_id):  # type: ignore[no-untyped-def]
        return [
            a.model_copy(deep=True)
            for a in self._approvals.values()
            if a.case_id == case_id and _visible(a, org_id, workspace_id)
        ]

    async def find_approval_by_idempotency(self, idempotency_key, org_id):  # type: ignore[no-untyped-def]
        # Org-wide by design — mirrors uq_decision_approvals_org_idempotency.
        for a in self._approvals.values():
            if a.idempotency_key == idempotency_key and a.org_id == org_id:
                return a.model_copy(deep=True)
        return None

    # ── outcomes ──
    async def add_outcome(self, outcome: OutcomeRecord) -> OutcomeRecord:
        self._outcomes[outcome.id] = outcome.model_copy(deep=True)
        return outcome
