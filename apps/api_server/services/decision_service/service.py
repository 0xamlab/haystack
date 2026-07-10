"""DecisionService — governed decision workflow orchestration.

Drives the versioned aggregate through the coarse workflow using a
:class:`DecisionRepository` and a governed Decision Pack. Key guarantees, enforced here
(not by the LLM): immutable revisions (a material framing change creates a new revision and
invalidates prior approvals); reproducible runs (inputs/result hashes + reproducibility id);
retention-aware evidence; a **separately-authenticated** approval bound to an exact plan hash
+ single-use nonce; and **approve ≠ execute** (execution is a distinct, post-approval step).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from apps.api_server.decision_packs import renewal_capacity_allocation as _rca
from apps.api_server.decision_packs.renewal_capacity_allocation.contract import (
    RenewalAllocationInput,
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
from .repository import DecisionRepository

__all__ = ["DecisionService", "DecisionServiceError", "RequestScope", "PACK_REGISTRY"]


class DecisionServiceError(Exception):
    """Workflow error with a stable ``code`` for the API layer to map to HTTP."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class RequestScope:
    """Caller identity/scope derived from the auth layer (never from request body)."""

    org_id: uuid.UUID
    workspace_id: uuid.UUID | None = None
    principal: str | None = None
    tenant: str | None = None
    role: str | None = None


@dataclass(frozen=True)
class _Pack:
    run: Callable[[Any], Any]
    input_model: type
    model_version: str
    descriptor: Any


PACK_REGISTRY: dict[str, _Pack] = {
    _rca.PACK_ID: _Pack(
        run=_rca.run,
        input_model=RenewalAllocationInput,
        model_version=_rca.MODEL_VERSION,
        descriptor=_rca.DESCRIPTOR,
    ),
}


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str)


def _hash(obj: Any) -> str:
    return hashlib.sha256(_canonical(obj).encode("utf-8")).hexdigest()


class DecisionService:
    def __init__(
        self, repo: DecisionRepository, clock: Callable[[], datetime] | None = None
    ) -> None:
        self._repo = repo
        self._clock = clock or (lambda: datetime.now(UTC))

    # ── helpers ──────────────────────────────────────────────────────────────────────
    def _now(self) -> datetime:
        return self._clock()

    def _stamp(self) -> dict[str, Any]:
        now = self._now()
        return {"id": uuid.uuid4(), "created_at": now, "updated_at": now}

    def _pack(self, pack_id: str) -> _Pack:
        pack = PACK_REGISTRY.get(pack_id)
        if pack is None:
            raise DecisionServiceError(
                "unknown_pack", f"Decision Pack '{pack_id}' is not registered"
            )
        return pack

    # ── 1. frame / re-frame ─────────────────────────────────────────────────────────
    async def create_or_update_decision(
        self,
        scope: RequestScope,
        *,
        pack_id: str,
        title: str,
        pack_input: dict[str, Any],
        case_id: uuid.UUID | None = None,
        owner: str | None = None,
        objective: str | None = None,
        horizon_days: int | None = None,
    ) -> tuple[DecisionCaseRecord, RevisionRecord]:
        pack = self._pack(pack_id)
        # Validate the framing against the pack contract (raises on invalid input).
        try:
            validated = pack.input_model(**pack_input)
        except Exception as exc:  # pydantic ValidationError etc.
            raise DecisionServiceError("invalid_framing", f"Invalid pack input: {exc}") from exc
        normalized = validated.model_dump(mode="json")
        inputs_hash = _hash({"pack_id": pack_id, "input": normalized, "model": pack.model_version})

        desc = pack.descriptor
        rev_common = {
            "pack_id": pack_id,
            "pack_input": normalized,
            "objective": objective or getattr(desc, "objective", None),
            "horizon_days": horizon_days or normalized.get("horizon_days"),
            "levers": {"levers": list(getattr(desc, "levers", []))},
            "constraints": normalized.get("constraints"),
            "assumptions": normalized.get("assumptions"),
            "uncertainties": {"uncertainties": list(getattr(desc, "uncertainties", []))},
            "candidate_options": None,
            "inputs_hash": inputs_hash,
            "created_by": scope.principal,
        }

        if case_id is None:
            case = DecisionCaseRecord(
                **self._stamp(),
                org_id=scope.org_id,
                workspace_id=scope.workspace_id,
                pack_id=pack_id,
                title=title,
                owner=owner,
                status="analyzing",
                current_revision_number=1,
            )
            rev = RevisionRecord(
                **self._stamp(),
                org_id=scope.org_id,
                workspace_id=scope.workspace_id,
                case_id=case.id,
                revision_number=1,
                change_class="material",
                **rev_common,
            )
            case.current_revision_id = rev.id
            await self._repo.add_case(case)
            await self._repo.add_revision(rev)
            return case, rev

        case = await self._repo.get_case(case_id, scope.org_id, scope.workspace_id)
        if case is None:
            raise DecisionServiceError("case_not_found", f"Decision case {case_id} not found")
        current = (
            await self._repo.get_revision(
                case.current_revision_id, scope.org_id, scope.workspace_id
            )
            if case.current_revision_id
            else None
        )
        if current is not None and current.inputs_hash == inputs_hash:
            return case, current  # no-op: identical framing

        # Material change → new immutable revision + invalidate prior approvals/plans.
        # Children inherit the CASE's workspace (not the caller's): an org-wide platform
        # caller re-framing a workspace-owned case must not strand its children in a
        # different workspace scope.
        new_number = case.current_revision_number + 1
        rev = RevisionRecord(
            **self._stamp(),
            org_id=scope.org_id,
            workspace_id=case.workspace_id,
            case_id=case.id,
            revision_number=new_number,
            change_class="material",
            **rev_common,
        )
        await self._repo.add_revision(rev)
        await self._invalidate_open_approvals(scope, case.id)
        case.current_revision_id = rev.id
        case.current_revision_number = new_number
        case.title = title
        if owner is not None:
            case.owner = owner
        case.status = "analyzing"
        case.updated_at = self._now()
        await self._repo.update_case(case)
        return case, rev

    async def _invalidate_open_approvals(self, scope: RequestScope, case_id: uuid.UUID) -> None:
        approvals = await self._repo.get_approvals_for_case(
            case_id, scope.org_id, scope.workspace_id
        )
        for ap in approvals:
            if ap.status in ("pending", "approved"):
                ap.status = "expired"
                ap.updated_at = self._now()
                await self._repo.update_approval(ap)
                if ap.plan_id:
                    plan = await self._repo.get_plan(ap.plan_id, scope.org_id, scope.workspace_id)
                    if plan and plan.lifecycle_state not in ("executed", "reconciled"):
                        plan.lifecycle_state = "failed_compensated"
                        plan.updated_at = self._now()
                        await self._repo.update_plan(plan)

    # ── 2. analyze (the async run executes the pack) ─────────────────────────────────
    async def run_decision_analysis(
        self, scope: RequestScope, *, case_id: uuid.UUID, retention_mode: str = "exploratory"
    ) -> RunRecord:
        if retention_mode not in ("exploratory", "governed"):
            raise DecisionServiceError("invalid_retention_mode", retention_mode)
        case = await self._repo.get_case(case_id, scope.org_id, scope.workspace_id)
        if case is None:
            raise DecisionServiceError("case_not_found", f"Decision case {case_id} not found")
        rev = await self._repo.get_revision(
            case.current_revision_id, scope.org_id, scope.workspace_id
        )
        if rev is None:
            raise DecisionServiceError("revision_not_found", "Case has no current revision")
        pack = self._pack(rev.pack_id)

        run = RunRecord(
            **self._stamp(),
            org_id=scope.org_id,
            workspace_id=case.workspace_id,  # children inherit the case's workspace
            case_id=case.id,
            revision_id=rev.id,
            model_version_ref=pack.model_version,
            status="running",
            inputs_hash=rev.inputs_hash,
            started_at=self._now(),
        )
        await self._repo.add_run(run)

        try:
            result = pack.run(pack.input_model(**rev.pack_input))
            result_dict = result.model_dump(mode="json")
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)
            run.finished_at = self._now()
            run.updated_at = self._now()
            await self._repo.update_run(run)
            return run

        result_hash = _hash(result_dict)
        run.result = result_dict
        run.result_hash = result_hash
        run.reproducibility_id = f"{(rev.inputs_hash or '')[:8]}-{result_hash[:8]}"

        evidence = EvidenceRecord(
            **self._stamp(),
            org_id=scope.org_id,
            workspace_id=case.workspace_id,
            case_id=case.id,
            revision_id=rev.id,
            retention_mode=retention_mode,
            sources=self._evidence_sources(rev, retention_mode),
            snapshot_ref=(f"revision:{rev.id}" if retention_mode == "governed" else None),
            data_quality_score=result_dict.get("data_quality_score"),
            evidence_notes=result_dict.get("evidence_notes"),
            content_hash=rev.inputs_hash,
        )
        await self._repo.add_evidence(evidence)

        run.evidence_snapshot_id = evidence.id
        run.status = "completed"
        run.finished_at = self._now()
        run.updated_at = self._now()
        await self._repo.update_run(run)

        await self._build_recommendation(scope, case, run, result_dict)

        case.status = "recommended" if result_dict.get("feasible") else "analyzing"
        case.updated_at = self._now()
        await self._repo.update_case(case)
        return run

    def _evidence_sources(self, rev: RevisionRecord, retention_mode: str) -> dict[str, Any]:
        pin = rev.pack_input
        summary: dict[str, Any] = {
            "pack_id": rev.pack_id,
            "account_count": len(pin.get("accounts", [])),
            "inputs_hash": rev.inputs_hash,
            "retention_mode": retention_mode,
        }
        # Exploratory: refs + hashes only. Governed: retain the exact inputs for reproduction.
        if retention_mode == "governed":
            summary["retained_input"] = pin
        return summary

    async def _build_recommendation(
        self, scope: RequestScope, case: DecisionCaseRecord, run: RunRecord, result: dict[str, Any]
    ) -> RecommendationRecord:
        rec_id = result.get("recommended_scenario_id")
        scenarios = result.get("scenarios", [])
        chosen = next((s for s in scenarios if s.get("id") == rec_id), None)
        summary = None
        if chosen:
            summary = (
                f"{chosen.get('label')}: expected retained ARR "
                f"${chosen.get('expected_retained_arr', 0):,.0f} "
                f"(+${chosen.get('uplift_arr', 0):,.0f} vs baseline)"
            )
        rec = RecommendationRecord(
            **self._stamp(),
            org_id=scope.org_id,
            workspace_id=case.workspace_id,
            case_id=case.id,
            run_id=run.id,
            recommended_scenario_id=rec_id,
            summary=summary,
            ranked_options={"scenarios": scenarios},
            explanation={
                "sensitivity": result.get("sensitivity"),
                "constraints": result.get("constraints"),
                "provenance": result.get("provenance"),
                "disclaimer": result.get("disclaimer"),
            },
            confidence=result.get("confidence"),
            content_hash=run.result_hash,
        )
        await self._repo.add_recommendation(rec)
        return rec

    # ── 3. read ──────────────────────────────────────────────────────────────────────
    async def get_run(self, scope: RequestScope, run_id: uuid.UUID) -> RunRecord:
        run = await self._repo.get_run(run_id, scope.org_id, scope.workspace_id)
        if run is None:
            raise DecisionServiceError("run_not_found", f"Analysis run {run_id} not found")
        return run

    async def get_result(self, scope: RequestScope, run_id: uuid.UUID) -> dict[str, Any]:
        run = await self.get_run(scope, run_id)
        if run.status != "completed":
            return {"status": run.status, "error": run.error}
        return {
            "status": "completed",
            "reproducibility_id": run.reproducibility_id,
            "model_version": run.model_version_ref,
            "result": run.result,
        }

    async def inspect_evidence(self, scope: RequestScope, run_id: uuid.UUID) -> dict[str, Any]:
        run = await self.get_run(scope, run_id)
        ev = (
            await self._repo.get_evidence(
                run.evidence_snapshot_id, scope.org_id, scope.workspace_id
            )
            if run.evidence_snapshot_id
            else None
        )
        provenance = (run.result or {}).get("provenance")
        return {
            "evidence": ev.model_dump(mode="json") if ev else None,
            "provenance": provenance,
            "reproducibility_id": run.reproducibility_id,
        }

    # ── 4. propose an execution plan (safe MVP actions only) ─────────────────────────
    async def propose_action_plan(
        self, scope: RequestScope, run_id: uuid.UUID
    ) -> ExecutionPlanRecord:
        run = await self.get_run(scope, run_id)
        if run.status != "completed":
            raise DecisionServiceError("run_not_completed", "Analysis run is not completed")
        result = run.result or {}
        if not result.get("feasible"):
            raise DecisionServiceError(
                "no_feasible_solution",
                "Cannot propose a plan: the analysis found no feasible solution",
            )
        actions = self._safe_actions(result)
        plan_hash = _hash(
            {"run_id": str(run.id), "revision_id": str(run.revision_id), "actions": actions}
        )
        plan = ExecutionPlanRecord(
            **self._stamp(),
            org_id=scope.org_id,
            workspace_id=run.workspace_id,  # inherit the case's workspace via the run
            case_id=run.case_id,
            run_id=run.id,
            revision_id=run.revision_id,
            actions={"actions": actions},
            lifecycle_state="proposed",
            plan_hash=plan_hash,
            nonce=uuid.uuid4().hex,
        )
        await self._repo.add_plan(plan)
        return plan

    def _safe_actions(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        rec_id = result.get("recommended_scenario_id")
        chosen = next(
            (s for s in result.get("scenarios", []) if s.get("id") == rec_id), None
        )
        funded = [a for a in (chosen or {}).get("allocations", []) if a.get("hours", 0) > 0]
        funded.sort(key=lambda a: a.get("hours", 0), reverse=True)
        top = funded[:50]
        return [
            {
                "type": "export_allocation_table",
                "title": "Recommended allocation",
                "rows": [
                    {
                        "account": a.get("name"),
                        "hours": a.get("hours"),
                        "expected_retained_arr": a.get("estimated_expected_retained_arr"),
                    }
                    for a in top
                ],
            },
            {
                "type": "create_task_list",
                "title": "Customer-success intervention tasks",
                "tasks": [f"Allocate {a.get('hours'):g}h to {a.get('name')}" for a in top],
            },
            {
                "type": "draft_approval_memo",
                "title": "Decision memo",
                "body": (
                    (chosen or {}).get("label", "Recommended allocation")
                    + f" — expected ARR ${(chosen or {}).get('expected_retained_arr', 0):,.0f}"
                ),
            },
        ]

    # ── 5. approve (separately authenticated; NOT an LLM tool) ───────────────────────
    async def approve(
        self,
        scope: RequestScope,
        *,
        plan_id: uuid.UUID,
        plan_hash: str,
        nonce: str,
        idempotency_key: str | None = None,
        required_role: str | None = None,
        expires_at: datetime | None = None,
    ) -> ApprovalRecord:
        if idempotency_key:
            existing = await self._repo.find_approval_by_idempotency(
                idempotency_key, scope.org_id, scope.workspace_id
            )
            if existing is not None:
                # An idempotency key is only a safe replay if the request fingerprint matches
                # the stored approval EXACTLY — otherwise a reused key would silently return a
                # different plan's approval (misrouting + approval-material disclosure).
                if (
                    existing.plan_id != plan_id
                    or existing.plan_hash != plan_hash
                    or existing.nonce != nonce
                ):
                    raise DecisionServiceError(
                        "idempotency_key_conflict",
                        "idempotency_key was already used for a different approval request",
                    )
                return existing

        plan = await self._repo.get_plan(plan_id, scope.org_id, scope.workspace_id)
        if plan is None:
            raise DecisionServiceError("plan_not_found", f"Execution plan {plan_id} not found")
        if plan.lifecycle_state != "proposed":
            raise DecisionServiceError(
                "plan_not_approvable", f"Plan is '{plan.lifecycle_state}', not 'proposed'"
            )
        if plan.plan_hash != plan_hash:
            raise DecisionServiceError(
                "plan_hash_mismatch", "plan_hash does not match the current plan"
            )
        if plan.nonce != nonce or plan.nonce_consumed:
            raise DecisionServiceError("invalid_nonce", "approval nonce is invalid or already used")
        if expires_at is not None and self._now() > expires_at:
            raise DecisionServiceError("approval_expired", "approval challenge has expired")
        if required_role is not None and scope.role != required_role:
            raise DecisionServiceError(
                "insufficient_role", f"approval requires role '{required_role}'"
            )
        # Material-change guard: the plan's revision must still be the case's current revision.
        case = await self._repo.get_case(plan.case_id, scope.org_id, scope.workspace_id)
        if case is None:
            raise DecisionServiceError("case_not_found", "Decision case not found")
        if case.current_revision_id != plan.revision_id:
            raise DecisionServiceError(
                "stale_plan", "the decision was revised since this plan was proposed; re-propose"
            )

        approval = ApprovalRecord(
            **self._stamp(),
            org_id=scope.org_id,
            workspace_id=plan.workspace_id,  # inherit the case's workspace via the plan
            case_id=plan.case_id,
            revision_id=plan.revision_id,
            run_id=plan.run_id,
            plan_id=plan.id,
            plan_hash=plan_hash,
            nonce=nonce,
            idempotency_key=idempotency_key,
            approver_principal=scope.principal,
            approver_tenant=scope.tenant,
            required_role=required_role,
            status="approved",
            expires_at=expires_at,
            decided_at=self._now(),
        )
        await self._repo.add_approval(approval)

        plan.nonce_consumed = True
        plan.lifecycle_state = "approved"
        plan.approval_id = approval.id
        plan.updated_at = self._now()
        await self._repo.update_plan(plan)

        case.status = "approved"
        case.updated_at = self._now()
        await self._repo.update_case(case)
        return approval

    # ── 6. execute (approve != execute; requires a prior approval) ───────────────────
    async def execute_approved_plan(
        self, scope: RequestScope, *, plan_id: uuid.UUID
    ) -> ExecutionPlanRecord:
        plan = await self._repo.get_plan(plan_id, scope.org_id, scope.workspace_id)
        if plan is None:
            raise DecisionServiceError("plan_not_found", f"Execution plan {plan_id} not found")
        if plan.lifecycle_state != "approved":
            raise DecisionServiceError(
                "plan_not_approved", f"Plan is '{plan.lifecycle_state}', not 'approved'"
            )
        case = await self._repo.get_case(plan.case_id, scope.org_id, scope.workspace_id)
        if case is None:
            raise DecisionServiceError("case_not_found", "Decision case not found")
        if case.current_revision_id != plan.revision_id:
            raise DecisionServiceError(
                "stale_plan", "the decision was revised after approval; re-propose and re-approve"
            )
        # Safe MVP execution: produce artifacts/receipt only — no external side effects.
        actions = (plan.actions or {}).get("actions", [])
        plan.receipt = {
            "executed_at": self._now().isoformat(),
            "prepared_artifacts": [a.get("type") for a in actions],
            "action_count": len(actions),
        }
        plan.lifecycle_state = "executed"
        plan.updated_at = self._now()
        await self._repo.update_plan(plan)

        case.status = "monitoring"
        case.updated_at = self._now()
        await self._repo.update_case(case)
        return plan

    # ── 7. learn ─────────────────────────────────────────────────────────────────────
    async def record_outcome(
        self,
        scope: RequestScope,
        *,
        case_id: uuid.UUID,
        run_id: uuid.UUID | None,
        actual_metrics: dict[str, Any],
        notes: str | None = None,
    ) -> OutcomeRecord:
        case = await self._repo.get_case(case_id, scope.org_id, scope.workspace_id)
        if case is None:
            raise DecisionServiceError("case_not_found", f"Decision case {case_id} not found")
        delta: dict[str, Any] = {}
        if run_id is not None:
            run = await self._repo.get_run(run_id, scope.org_id, scope.workspace_id)
            if run and run.result:
                rec_id = run.result.get("recommended_scenario_id")
                chosen = next(
                    (s for s in run.result.get("scenarios", []) if s.get("id") == rec_id), None
                )
                expected = (chosen or {}).get("expected_retained_arr")
                actual = actual_metrics.get("retained_arr")
                if expected is not None and actual is not None:
                    delta["retained_arr"] = actual - expected
        outcome = OutcomeRecord(
            **self._stamp(),
            org_id=scope.org_id,
            workspace_id=case.workspace_id,
            case_id=case.id,
            run_id=run_id,
            actual_metrics=actual_metrics,
            delta=delta or None,
            notes=notes,
            recorded_by=scope.principal,
            recorded_at=self._now(),
        )
        await self._repo.add_outcome(outcome)
        case.status = "monitoring"
        case.updated_at = self._now()
        await self._repo.update_case(case)
        return outcome

    async def refresh_decision(
        self, scope: RequestScope, *, case_id: uuid.UUID, retention_mode: str = "exploratory"
    ) -> RunRecord:
        # Re-run the current revision with fresh evidence (manual refresh; scheduled = Phase 2).
        return await self.run_decision_analysis(
            scope, case_id=case_id, retention_mode=retention_mode
        )
