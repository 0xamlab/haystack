"""SQLAlchemy-backed DecisionRepository over the versioned decision aggregate.

Maps the persistence-agnostic records to the ORM rows (apps/api_server/models/
decision_aggregate.py). Scoping mirrors ``workspace_scope_clauses``: always filter by
``org_id``; when the caller carries a ``workspace_id``, require the row to match.

The repository does NOT commit — the request-scoped session (``get_db``) owns the
transaction; the router commits once per request.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.models.decision_aggregate import (
    AnalysisRun,
    Approval,
    DecisionCase,
    DecisionRevision,
    EvidenceSnapshot,
    ExecutionPlan,
    Outcome,
    Recommendation,
)

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

__all__ = ["SqlDecisionRepository"]


def _scope(model: Any, org_id: uuid.UUID, workspace_id: uuid.UUID | None) -> list[Any]:
    clauses = [model.org_id == org_id]
    if workspace_id is not None:
        clauses.append(model.workspace_id == workspace_id)
    return clauses


def _apply(row: Any, rec: Any, fields: tuple[str, ...]) -> None:
    for f in fields:
        setattr(row, f, getattr(rec, f))


_CASE_FIELDS = (
    "org_id", "workspace_id", "pack_id", "title", "owner", "status",
    "current_revision_id", "current_revision_number",
)
_REVISION_FIELDS = (
    "org_id", "workspace_id", "case_id", "revision_number", "pack_id", "pack_input",
    "objective", "horizon_days", "levers", "constraints", "assumptions", "uncertainties",
    "candidate_options", "change_class", "inputs_hash", "created_by",
)
_EVIDENCE_FIELDS = (
    "org_id", "workspace_id", "case_id", "revision_id", "retention_mode", "sources",
    "snapshot_ref", "data_quality_score", "evidence_notes", "content_hash",
)
_RUN_FIELDS = (
    "org_id", "workspace_id", "case_id", "revision_id", "evidence_snapshot_id",
    "model_version_ref", "status", "inputs_hash", "result", "result_hash",
    "reproducibility_id", "started_at", "finished_at", "error",
)
_REC_FIELDS = (
    "org_id", "workspace_id", "case_id", "run_id", "recommended_scenario_id", "summary",
    "ranked_options", "explanation", "confidence", "content_hash",
)
_PLAN_FIELDS = (
    "org_id", "workspace_id", "case_id", "run_id", "revision_id", "approval_id", "actions",
    "lifecycle_state", "plan_hash", "nonce", "nonce_consumed", "receipt",
)
_APPROVAL_FIELDS = (
    "org_id", "workspace_id", "case_id", "revision_id", "run_id", "recommendation_id",
    "plan_id", "plan_hash", "nonce", "idempotency_key", "approver_principal",
    "approver_tenant", "required_role", "step_up_required", "status", "expires_at",
    "decided_at",
)
_OUTCOME_FIELDS = (
    "org_id", "workspace_id", "case_id", "run_id", "actual_metrics", "delta", "notes",
    "recorded_by", "recorded_at",
)


def _to_record(row: Any, record_cls: type, fields: tuple[str, ...]) -> Any:
    data = {f: getattr(row, f) for f in fields}
    data.update(id=row.id, created_at=row.created_at, updated_at=row.updated_at)
    return record_cls(**data)


class SqlDecisionRepository:
    """DecisionRepository implementation over the request-scoped AsyncSession."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _add(self, orm_cls: type, rec: Any, fields: tuple[str, ...]) -> Any:
        row = orm_cls(id=rec.id)
        _apply(row, rec, fields)
        self._db.add(row)
        await self._db.flush()
        return rec

    async def _get(
        self,
        orm_cls: type,
        record_cls: type,
        fields: tuple[str, ...],
        row_id: uuid.UUID,
        org_id: uuid.UUID,
        workspace_id: uuid.UUID | None,
    ) -> Any | None:
        stmt = select(orm_cls).where(orm_cls.id == row_id, *_scope(orm_cls, org_id, workspace_id))
        row = (await self._db.execute(stmt)).scalar_one_or_none()
        return _to_record(row, record_cls, fields) if row is not None else None

    async def _update(self, orm_cls: type, rec: Any, fields: tuple[str, ...]) -> Any:
        stmt = select(orm_cls).where(
            orm_cls.id == rec.id, *_scope(orm_cls, rec.org_id, rec.workspace_id)
        )
        row = (await self._db.execute(stmt)).scalar_one()
        _apply(row, rec, fields)
        await self._db.flush()
        return rec

    # ── cases ──
    async def add_case(self, case: DecisionCaseRecord) -> DecisionCaseRecord:
        return await self._add(DecisionCase, case, _CASE_FIELDS)

    async def get_case(self, case_id, org_id, workspace_id):  # type: ignore[no-untyped-def]
        return await self._get(
            DecisionCase, DecisionCaseRecord, _CASE_FIELDS, case_id, org_id, workspace_id
        )

    async def update_case(self, case: DecisionCaseRecord) -> DecisionCaseRecord:
        return await self._update(DecisionCase, case, _CASE_FIELDS)

    async def set_case_status(self, case_id, org_id, workspace_id, status):  # type: ignore[no-untyped-def]
        stmt = (
            update(DecisionCase)
            .where(DecisionCase.id == case_id, *_scope(DecisionCase, org_id, workspace_id))
            .values(status=status)
        )
        await self._db.execute(stmt)
        await self._db.flush()

    async def update_case_meta(self, case_id, org_id, workspace_id, *, title, owner=None):  # type: ignore[no-untyped-def]
        values: dict[str, Any] = {"title": title}
        if owner is not None:
            values["owner"] = owner
        stmt = (
            update(DecisionCase)
            .where(DecisionCase.id == case_id, *_scope(DecisionCase, org_id, workspace_id))
            .values(**values)
        )
        await self._db.execute(stmt)
        await self._db.flush()

    # ── revisions ──
    async def add_revision(self, rev: RevisionRecord) -> RevisionRecord:
        return await self._add(DecisionRevision, rev, _REVISION_FIELDS)

    async def get_revision(self, revision_id, org_id, workspace_id):  # type: ignore[no-untyped-def]
        return await self._get(
            DecisionRevision, RevisionRecord, _REVISION_FIELDS, revision_id, org_id, workspace_id
        )

    # ── evidence ──
    async def add_evidence(self, ev: EvidenceRecord) -> EvidenceRecord:
        return await self._add(EvidenceSnapshot, ev, _EVIDENCE_FIELDS)

    async def get_evidence(self, evidence_id, org_id, workspace_id):  # type: ignore[no-untyped-def]
        return await self._get(
            EvidenceSnapshot, EvidenceRecord, _EVIDENCE_FIELDS, evidence_id, org_id, workspace_id
        )

    # ── runs ──
    async def add_run(self, run: RunRecord) -> RunRecord:
        return await self._add(AnalysisRun, run, _RUN_FIELDS)

    async def get_run(self, run_id, org_id, workspace_id):  # type: ignore[no-untyped-def]
        return await self._get(AnalysisRun, RunRecord, _RUN_FIELDS, run_id, org_id, workspace_id)

    async def update_run(self, run: RunRecord) -> RunRecord:
        return await self._update(AnalysisRun, run, _RUN_FIELDS)

    # ── recommendations ──
    async def add_recommendation(self, rec: RecommendationRecord) -> RecommendationRecord:
        return await self._add(Recommendation, rec, _REC_FIELDS)

    async def get_recommendation_for_run(self, run_id, org_id, workspace_id):  # type: ignore[no-untyped-def]
        stmt = select(Recommendation).where(
            Recommendation.run_id == run_id, *_scope(Recommendation, org_id, workspace_id)
        )
        row = (await self._db.execute(stmt)).scalars().first()
        return _to_record(row, RecommendationRecord, _REC_FIELDS) if row is not None else None

    # ── plans ──
    async def add_plan(self, plan: ExecutionPlanRecord) -> ExecutionPlanRecord:
        return await self._add(ExecutionPlan, plan, _PLAN_FIELDS)

    async def get_plan(self, plan_id, org_id, workspace_id):  # type: ignore[no-untyped-def]
        return await self._get(
            ExecutionPlan, ExecutionPlanRecord, _PLAN_FIELDS, plan_id, org_id, workspace_id
        )

    async def update_plan(self, plan: ExecutionPlanRecord) -> ExecutionPlanRecord:
        return await self._update(ExecutionPlan, plan, _PLAN_FIELDS)

    async def transition_plan_state(self, plan: ExecutionPlanRecord, from_state: str) -> bool:
        # Conditional UPDATE — the WHERE on lifecycle_state makes the transition win-once
        # under READ COMMITTED (the loser's UPDATE matches 0 rows after the winner commits).
        values = {f: getattr(plan, f) for f in _PLAN_FIELDS}
        stmt = (
            update(ExecutionPlan)
            .where(
                ExecutionPlan.id == plan.id,
                ExecutionPlan.lifecycle_state == from_state,
                *_scope(ExecutionPlan, plan.org_id, plan.workspace_id),
            )
            .values(**values)
        )
        result = await self._db.execute(stmt)
        await self._db.flush()
        return bool(getattr(result, "rowcount", 0))

    # ── approvals ──
    async def add_approval(self, ap: ApprovalRecord) -> ApprovalRecord:
        try:
            return await self._add(Approval, ap, _APPROVAL_FIELDS)
        except IntegrityError as exc:
            # uq_decision_approvals_org_idempotency — a concurrent first-use of the same key
            # beat us to the insert. Map the designed backstop to the workflow error instead
            # of surfacing a 500. (Lazy import: service imports this module's sibling, not us.)
            from .service import DecisionServiceError

            raise DecisionServiceError(
                "idempotency_key_conflict",
                "idempotency_key was concurrently used by another approval request",
            ) from exc

    async def update_approval(self, ap: ApprovalRecord) -> ApprovalRecord:
        return await self._update(Approval, ap, _APPROVAL_FIELDS)

    async def get_approvals_for_case(self, case_id, org_id, workspace_id):  # type: ignore[no-untyped-def]
        stmt = select(Approval).where(
            Approval.case_id == case_id, *_scope(Approval, org_id, workspace_id)
        )
        rows = (await self._db.execute(stmt)).scalars().all()
        return [_to_record(r, ApprovalRecord, _APPROVAL_FIELDS) for r in rows]

    async def find_approval_by_idempotency(self, idempotency_key, org_id):  # type: ignore[no-untyped-def]
        # Org-wide — matches uq_decision_approvals_org_idempotency exactly, so the pre-check
        # and the unique constraint can never disagree about what counts as a duplicate.
        stmt = select(Approval).where(
            Approval.idempotency_key == idempotency_key,
            Approval.org_id == org_id,
        )
        row = (await self._db.execute(stmt)).scalars().first()
        return _to_record(row, ApprovalRecord, _APPROVAL_FIELDS) if row is not None else None

    # ── outcomes ──
    async def add_outcome(self, outcome: OutcomeRecord) -> OutcomeRecord:
        return await self._add(Outcome, outcome, _OUTCOME_FIELDS)
