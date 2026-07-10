"""Golden + invariant tests for the Renewal Capacity Allocation Decision Pack.

These prove the *contracts-first* deliverable: deterministic/reproducible output, genuine
hard-constraint enforcement, first-class no-feasible-solution, out-of-validity rejection,
and the evidence-quality gate — the walking-skeleton foundation the Decision Service builds on.

Regenerate the golden snapshot intentionally with:
    UPDATE_GOLDEN=1 pytest tests/test_renewal_capacity_allocation_pack.py
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from apps.api_server.decision_packs import renewal_capacity_allocation as pack
from apps.api_server.decision_packs.renewal_capacity_allocation.contract import (
    CapacityInput,
    InterventionAssumptions,
    RenewalAccount,
    RenewalAllocationInput,
    RenewalConstraints,
    Segment,
)
from apps.api_server.decision_packs.renewal_capacity_allocation.outcome_model import (
    DomainValidityError,
    baseline_probability_from_health,
    estimated_probability,
)

GOLDEN = Path(pack.__file__).parent / "golden" / "expected_baseline.json"
_RENEWAL = date(2026, 8, 1)


def _baseline_input() -> RenewalAllocationInput:
    """A small, fully-deterministic scenario: 5 accounts (2 strategic, low ARR), 40h capacity."""

    accounts = [
        RenewalAccount(account_id="A1", name="BigCo", arr=500_000, renewal_date=_RENEWAL, health_score=40, segment=Segment.standard),
        RenewalAccount(account_id="A2", name="MidCo", arr=300_000, renewal_date=_RENEWAL, health_score=55, segment=Segment.standard),
        RenewalAccount(account_id="A3", name="SmallStrategic", arr=60_000, renewal_date=_RENEWAL, health_score=35, segment=Segment.strategic),
        RenewalAccount(account_id="A4", name="GrowthCo", arr=200_000, renewal_date=_RENEWAL, health_score=60, segment=Segment.standard),
        RenewalAccount(account_id="A5", name="KeyStrategic", arr=90_000, renewal_date=_RENEWAL, health_score=50, segment=Segment.strategic),
    ]
    return RenewalAllocationInput(
        accounts=accounts,
        capacity=CapacityInput(total_hours=40),
        assumptions=InterventionAssumptions(effectiveness=0.35, saturation_hours=8, max_useful_hours_per_account=16),
        constraints=RenewalConstraints(strategic_min_hours=4, allocation_step_hours=1),
        horizon_days=90,
    )


def test_baseline_is_feasible_and_recommends_a_scenario() -> None:
    res = pack.run(_baseline_input())
    assert res.feasible is True
    assert res.no_feasible_solution is None
    assert res.recommended_scenario_id is not None
    assert res.model_version.endswith("@v0.1.0")


def test_hard_constraints_are_genuinely_enforced() -> None:
    res = pack.run(_baseline_input())
    rec = next(s for s in res.scenarios if s.id == res.recommended_scenario_id)

    # total capacity respected
    assert rec.total_hours_used <= 40 + 1e-6
    # every strategic account got at least the 4h guarantee
    strat = {a.account_id for a in rec.allocations if a.segment is Segment.strategic}
    assert strat == {"A3", "A5"}
    for a in rec.allocations:
        if a.segment is Segment.strategic:
            assert a.hours >= 4 - 1e-9
    # the constraint statuses agree
    assert all(c.satisfied for c in res.constraints if c.kind == "hard")


def test_recommended_beats_baseline_and_uplift_nonnegative() -> None:
    res = pack.run(_baseline_input())
    rec = next(s for s in res.scenarios if s.id == res.recommended_scenario_id)
    base = next(s for s in res.scenarios if s.id == "baseline")
    assert rec.expected_retained_arr >= base.expected_retained_arr
    assert rec.uplift_arr >= 0
    # recommended is the top-ranked feasible scenario
    feasible_ranked = sorted(
        (s for s in res.scenarios if s.feasible), key=lambda s: s.expected_retained_arr, reverse=True
    )
    assert feasible_ranked[0].id == res.recommended_scenario_id


def test_constraint_violating_alternative_is_rejected_with_reason() -> None:
    # "Concentrate on highest-ARR accounts" starves the low-ARR strategic accounts
    # below their 4h guarantee, so it must be flagged infeasible — not silently accepted.
    res = pack.run(_baseline_input())
    concentrate = next(s for s in res.scenarios if s.id == "concentrate_top_arr")
    assert concentrate.feasible is False
    assert concentrate.rejected_reason and "strategic" in concentrate.rejected_reason.lower()
    assert concentrate.rank is None  # rejected scenarios are not ranked


def test_no_feasible_solution_when_strategic_minimums_exceed_capacity() -> None:
    inp = _baseline_input()
    # 2 strategic accounts × 4h = 8h, but only 6h available → infeasible.
    inp = inp.model_copy(update={"capacity": CapacityInput(total_hours=6)})
    res = pack.run(inp)
    assert res.feasible is False
    assert res.no_feasible_solution is not None
    assert res.no_feasible_solution.binding_constraint == "strategic_min_hours"
    assert res.no_feasible_solution.suggested_relaxations


def test_no_feasible_solution_when_capacity_is_zero() -> None:
    inp = _baseline_input().model_copy(update={"capacity": CapacityInput(total_hours=0)})
    res = pack.run(inp)
    assert res.feasible is False
    assert res.no_feasible_solution is not None
    assert res.no_feasible_solution.binding_constraint == "available_capacity"


def test_accounts_missing_required_evidence_are_excluded_and_downgrade_quality() -> None:
    inp = _baseline_input()
    accounts = list(inp.accounts)
    accounts.append(
        RenewalAccount(account_id="A6", name="NoDate", arr=150_000, renewal_date=None, health_score=70)
    )
    inp = inp.model_copy(update={"accounts": accounts})
    res = pack.run(inp)
    # excluded account never appears in any scenario
    ids = {a.account_id for s in res.scenarios for a in s.allocations}
    assert "A6" not in ids
    assert res.data_quality_score < 100


def test_missing_health_uses_segment_median_fallback_and_downgrades_confidence() -> None:
    inp = _baseline_input()
    accounts = list(inp.accounts)
    accounts[0] = accounts[0].model_copy(update={"health_score": None})
    inp = inp.model_copy(update={"accounts": accounts})
    res = pack.run(inp)
    assert res.confidence_downgraded is True
    assert any("fallback" in note.lower() for note in res.evidence_notes)


def test_out_of_validity_health_is_rejected_not_extrapolated() -> None:
    # direct model call rejects out-of-range
    with pytest.raises(DomainValidityError):
        baseline_probability_from_health(140.0)
    # and the contract edge is guarded by pydantic
    with pytest.raises(ValidationError):
        RenewalAccount(account_id="X", name="X", arr=1.0, renewal_date=_RENEWAL, health_score=140)


def test_sensitivity_threshold_is_reported() -> None:
    res = pack.run(_baseline_input())
    assert res.sensitivity
    s = res.sensitivity[0]
    assert s.parameter == "intervention_effectiveness"
    assert "effectiveness" in s.description.lower()


def test_provenance_separates_facts_from_assumptions_and_simulated() -> None:
    res = pack.run(_baseline_input())
    p = res.provenance
    assert p.observed_facts and p.customer_assumptions and p.simulated_outcomes
    # the confounding / assumption honesty is explicit
    assert any("effectiveness" in a.lower() for a in p.customer_assumptions)
    assert "model-estimated" in res.disclaimer.lower()


def test_deterministic_reproducible_output() -> None:
    a = pack.run(_baseline_input()).model_dump(mode="json")
    b = pack.run(_baseline_input()).model_dump(mode="json")
    assert a == b


def test_matches_golden_snapshot() -> None:
    res = pack.run(_baseline_input()).model_dump(mode="json")
    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.write_text(json.dumps(res, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        pytest.skip("golden snapshot regenerated")
    assert GOLDEN.exists(), "run once with UPDATE_GOLDEN=1 to create the golden snapshot"
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert res == expected


# ── regression tests for adversarial-review findings (PR #318) ─────────────────────────


def test_strategic_min_exceeding_per_account_cap_is_infeasible() -> None:
    # strategic_min (20h) > the default per-account cap (max_useful_hours_per_account=16h) can
    # never be met for any single account -> must be a no-feasible-solution, not a false "feasible".
    inp = _baseline_input().model_copy(
        update={"constraints": RenewalConstraints(strategic_min_hours=20.0, allocation_step_hours=1)}
    )
    res = pack.run(inp)
    assert res.feasible is False
    assert res.no_feasible_solution is not None
    assert res.no_feasible_solution.binding_constraint == "strategic_min_hours"


def test_zero_hours_never_reduces_probability_below_baseline() -> None:
    a = InterventionAssumptions()  # default cap 0.99
    # a baseline above the cap must be preserved, never pulled down by the cap
    assert estimated_probability(baseline=1.0, hours=0, segment=Segment.standard, assumptions=a) == 1.0
    assert estimated_probability(baseline=1.0, hours=8, segment=Segment.standard, assumptions=a) == 1.0
    assert (
        estimated_probability(baseline=0.995, hours=5, segment=Segment.standard, assumptions=a)
        >= 0.995
    )


def test_high_baseline_account_reports_nonnegative_uplift() -> None:
    inp = _baseline_input()
    accounts = list(inp.accounts)
    accounts[0] = accounts[0].model_copy(update={"baseline_renewal_probability": 1.0})
    inp = inp.model_copy(update={"accounts": accounts})
    res = pack.run(inp)
    for s in res.scenarios:
        assert s.uplift_arr >= -1e-6
        for al in s.allocations:
            assert al.uplift_arr >= -1e-6  # zero-hours (or capped) accounts never lose ARR


def test_do_nothing_baseline_is_never_recommended() -> None:
    # effectiveness 0 -> no beneficial allocation; baseline and recommended tie on ARR, but the
    # do-nothing baseline (which gives strategic accounts 0h) must never be the recommendation.
    inp = _baseline_input().model_copy(update={"assumptions": InterventionAssumptions(effectiveness=0.0)})
    res = pack.run(inp)
    assert res.feasible is True
    assert res.recommended_scenario_id not in (None, "baseline")
    rec = next(s for s in res.scenarios if s.id == res.recommended_scenario_id)
    for a in rec.allocations:
        if a.segment is Segment.strategic:
            assert a.hours >= 4 - 1e-9  # the recommendation honors the hard guarantee


def test_allocation_step_hours_is_honored() -> None:
    accts = [
        RenewalAccount(account_id="S1", name="One", arr=500_000, renewal_date=_RENEWAL, health_score=40),
        RenewalAccount(account_id="S2", name="Two", arr=450_000, renewal_date=_RENEWAL, health_score=45),
    ]
    base = RenewalAllocationInput(accounts=accts, capacity=CapacityInput(total_hours=7))
    fine = base.model_copy(update={"constraints": RenewalConstraints(strategic_min_hours=0, allocation_step_hours=1)})
    coarse = base.model_copy(update={"constraints": RenewalConstraints(strategic_min_hours=0, allocation_step_hours=8)})

    def alloc(res):
        rec = next(s for s in res.scenarios if s.id == res.recommended_scenario_id)
        return {a.account_id: a.hours for a in rec.allocations}

    assert alloc(pack.run(fine)) != alloc(pack.run(coarse))


def test_negative_segment_modifier_is_rejected() -> None:
    with pytest.raises(ValidationError):
        InterventionAssumptions(segment_modifiers={Segment.strategic: -0.5})
