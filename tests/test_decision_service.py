"""DB-free unit tests for the DecisionService workflow (Build order 4).

Drives the service over the in-memory repository, asserting the full happy path plus the
governance invariants: reproducibility, material-change invalidation, separately-authenticated
approval (plan-hash + single-use nonce + role), approve != execute, tenancy isolation, and
first-class no-feasible-solution. Async is driven via asyncio.run so no pytest-asyncio needed.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest

from apps.api_server.services.decision_service import (
    DecisionService,
    DecisionServiceError,
    InMemoryDecisionRepository,
)
from apps.api_server.services.decision_service.service import RequestScope

_FIXED_NOW = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)


def _svc() -> DecisionService:
    return DecisionService(InMemoryDecisionRepository(), clock=lambda: _FIXED_NOW)


def _scope(role: str | None = "approver") -> RequestScope:
    return RequestScope(org_id=uuid.uuid4(), workspace_id=None, principal="user@example.com", role=role)


def _renewal_input(*, total_hours: float = 40, strategic_min: float = 4) -> dict:
    return {
        "accounts": [
            {"account_id": "A1", "name": "BigCo", "arr": 500000, "renewal_date": "2026-08-01", "health_score": 40, "segment": "standard"},
            {"account_id": "A2", "name": "MidCo", "arr": 300000, "renewal_date": "2026-08-01", "health_score": 55, "segment": "standard"},
            {"account_id": "A3", "name": "SmallStrategic", "arr": 60000, "renewal_date": "2026-08-01", "health_score": 35, "segment": "strategic"},
            {"account_id": "A5", "name": "KeyStrategic", "arr": 90000, "renewal_date": "2026-08-01", "health_score": 50, "segment": "strategic"},
        ],
        "capacity": {"total_hours": total_hours},
        "assumptions": {"effectiveness": 0.35, "saturation_hours": 8, "max_useful_hours_per_account": 16},
        "constraints": {"strategic_min_hours": strategic_min, "allocation_step_hours": 1},
        "horizon_days": 90,
    }


async def _framed(svc: DecisionService, scope: RequestScope, **kw):
    return await svc.create_or_update_decision(
        scope, pack_id="renewal_capacity_allocation", title="Q3 renewals", pack_input=_renewal_input(**kw)
    )


def test_happy_path_frame_run_propose_approve_execute_outcome() -> None:
    async def run() -> None:
        svc, scope = _svc(), _scope()
        case, rev = await _framed(svc, scope)
        assert rev.revision_number == 1 and rev.inputs_hash

        run_rec = await svc.run_decision_analysis(scope, case_id=case.id)
        assert run_rec.status == "completed"
        assert run_rec.result and run_rec.result["feasible"] is True
        assert run_rec.reproducibility_id and run_rec.model_version_ref

        result = await svc.get_result(scope, run_rec.id)
        assert result["status"] == "completed"

        ev = await svc.inspect_evidence(scope, run_rec.id)
        assert ev["evidence"]["retention_mode"] == "exploratory"
        assert ev["provenance"]  # observed facts / assumptions / simulated separated

        plan = await svc.propose_action_plan(scope, run_rec.id)
        assert plan.lifecycle_state == "proposed" and plan.plan_hash and plan.nonce

        approval = await svc.approve(scope, plan_id=plan.id, plan_hash=plan.plan_hash, nonce=plan.nonce)
        assert approval.status == "approved"

        executed = await svc.execute_approved_plan(scope, plan_id=plan.id)
        assert executed.lifecycle_state == "executed" and executed.receipt

        outcome = await svc.record_outcome(
            scope, case_id=case.id, run_id=run_rec.id, actual_metrics={"retained_arr": 400000}
        )
        assert outcome.actual_metrics["retained_arr"] == 400000

    asyncio.run(run())


def test_runs_are_reproducible() -> None:
    async def run() -> None:
        svc, scope = _svc(), _scope()
        case, _ = await _framed(svc, scope)
        r1 = await svc.run_decision_analysis(scope, case_id=case.id)
        r2 = await svc.refresh_decision(scope, case_id=case.id)
        assert r1.result_hash == r2.result_hash
        assert r1.reproducibility_id == r2.reproducibility_id

    asyncio.run(run())


def test_identical_reframing_is_a_noop_revision() -> None:
    async def run() -> None:
        svc, scope = _svc(), _scope()
        case, rev1 = await _framed(svc, scope)
        case2, rev2 = await svc.create_or_update_decision(
            scope, pack_id="renewal_capacity_allocation", title="Q3 renewals",
            pack_input=_renewal_input(), case_id=case.id,
        )
        assert rev2.id == rev1.id and case2.current_revision_number == 1

    asyncio.run(run())


def test_material_reframing_creates_new_revision_and_invalidates_prior_approval() -> None:
    async def run() -> None:
        svc, scope = _svc(), _scope()
        case, rev1 = await _framed(svc, scope)
        r = await svc.run_decision_analysis(scope, case_id=case.id)
        plan = await svc.propose_action_plan(scope, r.id)
        approval = await svc.approve(scope, plan_id=plan.id, plan_hash=plan.plan_hash, nonce=plan.nonce)
        assert approval.status == "approved"

        # material change -> new revision, prior approval expired, prior plan compensated
        case2, rev2 = await svc.create_or_update_decision(
            scope, pack_id="renewal_capacity_allocation", title="Q3 renewals (more capacity)",
            pack_input=_renewal_input(total_hours=80), case_id=case.id,
        )
        assert rev2.revision_number == 2 and case2.current_revision_id == rev2.id
        approvals = await svc._repo.get_approvals_for_case(case.id, scope.org_id, scope.workspace_id)
        assert all(a.status == "expired" for a in approvals)
        stale_plan = await svc._repo.get_plan(plan.id, scope.org_id, scope.workspace_id)
        assert stale_plan.lifecycle_state == "failed_compensated"

    asyncio.run(run())


def test_approve_requires_matching_plan_hash_and_nonce() -> None:
    async def run() -> None:
        svc, scope = _svc(), _scope()
        case, _ = await _framed(svc, scope)
        r = await svc.run_decision_analysis(scope, case_id=case.id)
        plan = await svc.propose_action_plan(scope, r.id)
        with pytest.raises(DecisionServiceError) as e1:
            await svc.approve(scope, plan_id=plan.id, plan_hash="deadbeef", nonce=plan.nonce)
        assert e1.value.code == "plan_hash_mismatch"
        with pytest.raises(DecisionServiceError) as e2:
            await svc.approve(scope, plan_id=plan.id, plan_hash=plan.plan_hash, nonce="wrong")
        assert e2.value.code == "invalid_nonce"

    asyncio.run(run())


def test_approval_nonce_is_single_use() -> None:
    async def run() -> None:
        svc, scope = _svc(), _scope()
        case, _ = await _framed(svc, scope)
        r = await svc.run_decision_analysis(scope, case_id=case.id)
        plan = await svc.propose_action_plan(scope, r.id)
        await svc.approve(scope, plan_id=plan.id, plan_hash=plan.plan_hash, nonce=plan.nonce)
        with pytest.raises(DecisionServiceError) as e:
            await svc.approve(scope, plan_id=plan.id, plan_hash=plan.plan_hash, nonce=plan.nonce)
        assert e.value.code == "plan_not_approvable"  # already approved; nonce consumed

    asyncio.run(run())


def test_idempotent_approval() -> None:
    async def run() -> None:
        svc, scope = _svc(), _scope()
        case, _ = await _framed(svc, scope)
        r = await svc.run_decision_analysis(scope, case_id=case.id)
        plan = await svc.propose_action_plan(scope, r.id)
        a1 = await svc.approve(scope, plan_id=plan.id, plan_hash=plan.plan_hash, nonce=plan.nonce, idempotency_key="k1")
        a2 = await svc.approve(scope, plan_id=plan.id, plan_hash=plan.plan_hash, nonce=plan.nonce, idempotency_key="k1")
        assert a1.id == a2.id

    asyncio.run(run())


def test_required_role_is_enforced() -> None:
    async def run() -> None:
        svc = _svc()
        scope = _scope(role="viewer")
        case, _ = await _framed(svc, scope)
        r = await svc.run_decision_analysis(scope, case_id=case.id)
        plan = await svc.propose_action_plan(scope, r.id)
        with pytest.raises(DecisionServiceError) as e:
            await svc.approve(
                scope, plan_id=plan.id, plan_hash=plan.plan_hash, nonce=plan.nonce, required_role="approver"
            )
        assert e.value.code == "insufficient_role"

    asyncio.run(run())


def test_approve_is_not_execute() -> None:
    async def run() -> None:
        svc, scope = _svc(), _scope()
        case, _ = await _framed(svc, scope)
        r = await svc.run_decision_analysis(scope, case_id=case.id)
        plan = await svc.propose_action_plan(scope, r.id)
        # execute before approve -> refused
        with pytest.raises(DecisionServiceError) as e:
            await svc.execute_approved_plan(scope, plan_id=plan.id)
        assert e.value.code == "plan_not_approved"
        await svc.approve(scope, plan_id=plan.id, plan_hash=plan.plan_hash, nonce=plan.nonce)
        executed = await svc.execute_approved_plan(scope, plan_id=plan.id)
        assert executed.lifecycle_state == "executed"

    asyncio.run(run())


def test_stale_plan_cannot_be_approved_after_revision() -> None:
    async def run() -> None:
        svc, scope = _svc(), _scope()
        case, _ = await _framed(svc, scope)
        r = await svc.run_decision_analysis(scope, case_id=case.id)
        plan = await svc.propose_action_plan(scope, r.id)
        # revise the decision (new revision) before approving the old plan
        await svc.create_or_update_decision(
            scope, pack_id="renewal_capacity_allocation", title="revised",
            pack_input=_renewal_input(total_hours=60), case_id=case.id,
        )
        with pytest.raises(DecisionServiceError) as e:
            await svc.approve(scope, plan_id=plan.id, plan_hash=plan.plan_hash, nonce=plan.nonce)
        # the reframe compensates the plan (failed_compensated) before the stale check fires
        assert e.value.code in ("stale_plan", "plan_not_approvable")

    asyncio.run(run())


def test_no_feasible_solution_blocks_plan_proposal() -> None:
    async def run() -> None:
        svc, scope = _svc(), _scope()
        # strategic_min 20h > per-account cap 16h -> infeasible
        case, _ = await svc.create_or_update_decision(
            scope, pack_id="renewal_capacity_allocation", title="infeasible",
            pack_input=_renewal_input(strategic_min=20),
        )
        r = await svc.run_decision_analysis(scope, case_id=case.id)
        assert r.status == "completed" and r.result["feasible"] is False
        with pytest.raises(DecisionServiceError) as e:
            await svc.propose_action_plan(scope, r.id)
        assert e.value.code == "no_feasible_solution"

    asyncio.run(run())


def test_invalid_framing_is_rejected() -> None:
    async def run() -> None:
        svc, scope = _svc(), _scope()
        with pytest.raises(DecisionServiceError) as e:
            await svc.create_or_update_decision(
                scope, pack_id="renewal_capacity_allocation", title="bad",
                pack_input={"accounts": [], "capacity": {"total_hours": 10}},  # empty accounts -> invalid
            )
        assert e.value.code == "invalid_framing"

    asyncio.run(run())


def test_unknown_pack_is_rejected() -> None:
    async def run() -> None:
        svc, scope = _svc(), _scope()
        with pytest.raises(DecisionServiceError) as e:
            await svc.create_or_update_decision(scope, pack_id="nope", title="x", pack_input={})
        assert e.value.code == "unknown_pack"

    asyncio.run(run())


def test_idempotency_key_reuse_for_a_different_plan_is_rejected() -> None:
    # Review finding (#319): a reused idempotency_key must NOT return a different plan's
    # approval — the request fingerprint (plan_id/plan_hash/nonce) must match exactly.
    async def run() -> None:
        svc, scope = _svc(), _scope()
        case, _ = await _framed(svc, scope)
        r1 = await svc.run_decision_analysis(scope, case_id=case.id)
        p1 = await svc.propose_action_plan(scope, r1.id)
        await svc.approve(scope, plan_id=p1.id, plan_hash=p1.plan_hash, nonce=p1.nonce, idempotency_key="K")

        r2 = await svc.refresh_decision(scope, case_id=case.id)
        p2 = await svc.propose_action_plan(scope, r2.id)
        with pytest.raises(DecisionServiceError) as e:
            await svc.approve(
                scope, plan_id=p2.id, plan_hash=p2.plan_hash, nonce=p2.nonce, idempotency_key="K"
            )
        assert e.value.code == "idempotency_key_conflict"
        # p2 remains unapproved (the key replay did not silently mask it)
        with pytest.raises(DecisionServiceError) as e2:
            await svc.execute_approved_plan(scope, plan_id=p2.id)
        assert e2.value.code == "plan_not_approved"

    asyncio.run(run())


def test_children_inherit_case_workspace_from_org_wide_caller() -> None:
    # Review finding (#319): an org-wide platform caller (workspace_id=None) acting on a
    # workspace-owned case must not strand children in a different workspace scope.
    async def run() -> None:
        svc = _svc()
        org = uuid.uuid4()
        ws = uuid.uuid4()
        ws_scope = RequestScope(org_id=org, workspace_id=ws, principal="ws-user")
        org_scope = RequestScope(org_id=org, workspace_id=None, principal="platform")

        case, _ = await svc.create_or_update_decision(
            ws_scope, pack_id="renewal_capacity_allocation", title="ws case",
            pack_input=_renewal_input(),
        )
        # org-wide caller re-frames the workspace-owned case
        case2, rev2 = await svc.create_or_update_decision(
            org_scope, pack_id="renewal_capacity_allocation", title="ws case v2",
            pack_input=_renewal_input(total_hours=80), case_id=case.id,
        )
        assert rev2.workspace_id == ws  # inherited from the case, not the caller

        # the owning workspace can still run its own current revision
        run_rec = await svc.run_decision_analysis(ws_scope, case_id=case.id)
        assert run_rec.status == "completed"
        assert run_rec.workspace_id == ws
        plan = await svc.propose_action_plan(ws_scope, run_rec.id)
        assert plan.workspace_id == ws
        approval = await svc.approve(
            ws_scope, plan_id=plan.id, plan_hash=plan.plan_hash, nonce=plan.nonce
        )
        assert approval.workspace_id == ws

    asyncio.run(run())


def test_concurrent_double_approve_single_winner() -> None:
    # #320 review: two parallel approves with the same nonce -> exactly one wins (CAS).
    async def run() -> None:
        svc, scope = _svc(), _scope()
        case, _ = await _framed(svc, scope)
        r = await svc.run_decision_analysis(scope, case_id=case.id)
        plan = await svc.propose_action_plan(scope, r.id)

        async def try_approve():
            try:
                await svc.approve(scope, plan_id=plan.id, plan_hash=plan.plan_hash, nonce=plan.nonce)
                return "ok"
            except DecisionServiceError as e:
                return e.code

        results = await asyncio.gather(try_approve(), try_approve())
        assert sorted(results) == ["ok", "plan_not_approvable"]
        approvals = await svc._repo.get_approvals_for_case(case.id, scope.org_id, scope.workspace_id)
        assert len([a for a in approvals if a.status == "approved"]) == 1

    asyncio.run(run())


def test_concurrent_double_execute_single_winner() -> None:
    async def run() -> None:
        svc, scope = _svc(), _scope()
        case, _ = await _framed(svc, scope)
        r = await svc.run_decision_analysis(scope, case_id=case.id)
        plan = await svc.propose_action_plan(scope, r.id)
        await svc.approve(scope, plan_id=plan.id, plan_hash=plan.plan_hash, nonce=plan.nonce)

        async def try_execute():
            try:
                await svc.execute_approved_plan(scope, plan_id=plan.id)
                return "ok"
            except DecisionServiceError as e:
                return e.code

        results = await asyncio.gather(try_execute(), try_execute())
        assert sorted(results) == ["ok", "plan_not_approved"]

    asyncio.run(run())


def test_approval_nonce_ttl_expires() -> None:
    # #320 review: a leaked propose response must not be approvable after the nonce TTL.
    async def run() -> None:
        from datetime import timedelta

        now = {"t": _FIXED_NOW}
        svc = DecisionService(InMemoryDecisionRepository(), clock=lambda: now["t"])
        scope = _scope()
        case, _ = await _framed(svc, scope)
        r = await svc.run_decision_analysis(scope, case_id=case.id)
        plan = await svc.propose_action_plan(scope, r.id)
        now["t"] = _FIXED_NOW + timedelta(hours=25)  # past the 24h nonce TTL
        with pytest.raises(DecisionServiceError) as e:
            await svc.approve(scope, plan_id=plan.id, plan_hash=plan.plan_hash, nonce=plan.nonce)
        assert e.value.code == "approval_expired"

    asyncio.run(run())


def test_outcome_run_must_belong_to_the_case() -> None:
    # #320 review: an outcome must not compute its delta from another case's run.
    async def run() -> None:
        svc, scope = _svc(), _scope()
        case_a, _ = await _framed(svc, scope)
        case_b, _ = await svc.create_or_update_decision(
            scope, pack_id="renewal_capacity_allocation", title="other case",
            pack_input=_renewal_input(total_hours=60),
        )
        run_b = await svc.run_decision_analysis(scope, case_id=case_b.id)
        with pytest.raises(DecisionServiceError) as e:
            await svc.record_outcome(
                scope, case_id=case_a.id, run_id=run_b.id, actual_metrics={"retained_arr": 1}
            )
        assert e.value.code == "run_not_found"

    asyncio.run(run())


def test_title_only_reframe_applies_without_new_revision() -> None:
    # #320 review: identical framing + new title must update the case, not silently no-op.
    async def run() -> None:
        svc, scope = _svc(), _scope()
        case, rev1 = await _framed(svc, scope)
        case2, rev2 = await svc.create_or_update_decision(
            scope, pack_id="renewal_capacity_allocation", title="Renamed decision",
            pack_input=_renewal_input(), case_id=case.id,
        )
        assert rev2.id == rev1.id  # same immutable revision
        assert case2.title == "Renamed decision"
        stored = await svc._repo.get_case(case.id, scope.org_id, scope.workspace_id)
        assert stored.title == "Renamed decision"

    asyncio.run(run())


def test_pack_id_cannot_change_on_an_existing_case() -> None:
    async def run() -> None:
        svc, scope = _svc(), _scope()
        case, _ = await _framed(svc, scope)
        with pytest.raises(DecisionServiceError) as e:
            await svc.create_or_update_decision(
                scope, pack_id="some_other_pack", title="x",
                pack_input=_renewal_input(), case_id=case.id,
            )
        assert e.value.code in ("invalid_framing", "unknown_pack")

    asyncio.run(run())


def test_tenancy_isolation_across_orgs() -> None:
    async def run() -> None:
        svc = _svc()
        scope_a, scope_b = _scope(), _scope()
        case, _ = await _framed(svc, scope_a)
        r = await svc.run_decision_analysis(scope_a, case_id=case.id)
        # org B cannot see org A's case or run
        with pytest.raises(DecisionServiceError) as e:
            await svc.get_run(scope_b, r.id)
        assert e.value.code == "run_not_found"
        with pytest.raises(DecisionServiceError):
            await svc.run_decision_analysis(scope_b, case_id=case.id)

    asyncio.run(run())
