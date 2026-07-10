"""Tests for the decision evaluators (Build order 9).

A real pack run must pass the whole suite; deliberately-tampered results must fail the exact
evaluator that guards that property (numerical grounding, constraint compliance, fabricated
recommendation, unit bounds, deterministic replay, prompt-injection isolation).
"""

from __future__ import annotations

import copy

from apps.api_server.decision_packs import renewal_capacity_allocation as rca
from apps.api_server.services.decision_service.evaluators import (
    EvalContext,
    build_rerun_for_pack,
    eval_instruction_isolation,
    evaluate_decision,
)

PACK = "renewal_capacity_allocation"


def _input(*, total_hours: float = 40, strategic_min: float = 4) -> dict:
    return {
        "accounts": [
            {"account_id": "A1", "name": "BigCo", "arr": 500000, "renewal_date": "2026-08-01", "health_score": 40, "segment": "standard"},
            {"account_id": "A2", "name": "MidCo", "arr": 300000, "renewal_date": "2026-08-01", "health_score": 55, "segment": "standard"},
            {"account_id": "A3", "name": "SmallStrategic", "arr": 60000, "renewal_date": "2026-08-01", "health_score": 35, "segment": "strategic"},
            {"account_id": "A5", "name": "KeyStrategic", "arr": 90000, "renewal_date": "2026-08-01", "health_score": 50, "segment": "strategic"},
        ],
        "capacity": {"total_hours": total_hours},
        "constraints": {"strategic_min_hours": strategic_min, "allocation_step_hours": 1},
        "horizon_days": 90,
    }


def _result(**kw) -> dict:
    return rca.run(rca.RenewalAllocationInput(**_input(**kw))).model_dump(mode="json")


def _recommendation(result: dict) -> dict:
    rid = result.get("recommended_scenario_id")
    scn = next((s for s in result["scenarios"] if s["id"] == rid), {})
    return {
        "summary": (
            f"{scn.get('label')}: expected retained ARR ${scn.get('expected_retained_arr', 0):,.0f} "
            f"(+${scn.get('uplift_arr', 0):,.0f} vs baseline)"
        ),
        "explanation": {
            "disclaimer": result.get("disclaimer"),
            "sensitivity": result.get("sensitivity"),
        },
    }


def _ctx(result: dict, *, with_rerun: bool = True, pack_input: dict | None = None, rec: dict | None = None) -> EvalContext:
    return EvalContext(
        result=result,
        recommendation=rec if rec is not None else _recommendation(result),
        pack_input=pack_input if pack_input is not None else _input(),
        rerun=build_rerun_for_pack(PACK) if with_rerun else None,
    )


def test_real_result_passes_every_evaluator() -> None:
    report = evaluate_decision(_ctx(_result()))
    assert report.passed, list(report.failed)
    # no evaluator should be skipped when full context is supplied
    assert all(o.status == "passed" for o in report.outcomes), report.counts()


def test_numerical_grounding_catches_invented_figure() -> None:
    result = _result()
    rec = _recommendation(result)
    rec["summary"] += " Projected windfall: $999,999,999."  # not in engine output
    report = evaluate_decision(_ctx(result, rec=rec))
    failed = {o.name for o in report.failed}
    assert "numerical_grounding" in failed


def test_constraint_compliance_catches_unsatisfied_hard_constraint() -> None:
    result = _result()
    # tamper: mark a hard constraint unsatisfied
    for c in result["constraints"]:
        if c["kind"] == "hard":
            c["satisfied"] = False
            break
    report = evaluate_decision(_ctx(result))
    assert "constraint_compliance" in {o.name for o in report.failed}


def test_no_feasible_solution_catches_fabricated_recommendation() -> None:
    result = _result(strategic_min=20)  # infeasible
    assert result["feasible"] is False
    result["recommended_scenario_id"] = "baseline"  # fabricate
    report = evaluate_decision(_ctx(result, pack_input=_input(strategic_min=20)))
    assert "no_feasible_solution" in {o.name for o in report.failed}


def test_genuinely_infeasible_result_passes_no_feasible_evaluator() -> None:
    result = _result(strategic_min=20)
    report = evaluate_decision(_ctx(result, pack_input=_input(strategic_min=20)))
    nf = next(o for o in report.outcomes if o.name == "no_feasible_solution")
    assert nf.status == "passed"


def test_unit_consistency_catches_out_of_range_probability() -> None:
    result = _result()
    result["scenarios"][0]["allocations"][0]["estimated_renewal_probability"] = 1.7
    report = evaluate_decision(_ctx(result))
    assert "unit_consistency" in {o.name for o in report.failed}


def test_deterministic_replay_catches_nondeterminism() -> None:
    result = _result()
    tampered = copy.deepcopy(result)
    # simulate a stored result that doesn't match a fresh run
    tampered["scenarios"][0]["expected_retained_arr"] += 12345.0
    report = evaluate_decision(_ctx(tampered))
    assert "deterministic_replay" in {o.name for o in report.failed}


def test_instruction_isolation_passes_for_the_real_pack() -> None:
    # The pack ignores free-text names, so injection into names must not move the numbers.
    result = _result()
    out = eval_instruction_isolation(_ctx(result))
    assert out.status == "passed"


def test_evaluators_skip_cleanly_without_optional_context() -> None:
    result = _result()
    ctx = EvalContext(result=result)  # no recommendation, no rerun, no input
    report = evaluate_decision(ctx)
    statuses = {o.name: o.status for o in report.outcomes}
    assert statuses["numerical_grounding"] == "skipped"
    assert statuses["deterministic_replay"] == "skipped"
    assert statuses["instruction_isolation"] == "skipped"
    # the input-free evaluators still run
    assert statuses["constraint_compliance"] == "passed"
    assert statuses["unit_consistency"] == "passed"
    assert report.passed  # skips are not failures
