"""Constrained allocation solver + scenario/sensitivity builder.

Greedy marginal allocation is provably optimal here because each account's
expected-retained-ARR value function is concave in hours (the uplift curve saturates),
and there is a single shared hours budget (plus per-account and per-CSM ceilings). We
allocate hard strategic minimums first, then repeatedly give the next step of hours to
the account with the highest marginal expected-ARR gain.

Hard constraints are *genuinely enforced*: if the strategic minimums cannot fit within
capacity (globally or for a CSM), the solver returns a **no-feasible-solution** result
with the binding constraint and suggested relaxations — it never fabricates an answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .contract import (
    AccountAllocation,
    ConfidenceLevel,
    ConstraintStatus,
    InterventionAssumptions,
    NoFeasibleSolution,
    RenewalAccount,
    RenewalAllocationInput,
    RenewalAllocationResult,
    RenewalConstraints,
    ScenarioResult,
    Segment,
    SensitivityResult,
)
from .evidence_contract import assess_evidence
from .outcome_model import (
    MODEL_VERSION,
    baseline_probability_from_health,
    estimated_probability,
    marginal_uplift_arr,
)

__all__ = ["solve"]


@dataclass
class _Acct:
    """Validated, model-ready view of an account."""

    account_id: str
    name: str
    arr: float
    segment: Segment
    csm_id: str | None
    baseline: float
    health_fallback: bool = False


@dataclass
class _Prepared:
    accounts: list[_Acct]
    excluded: list[str] = field(default_factory=list)
    health_fallbacks: int = 0


def _segment_median_health(accounts: list[RenewalAccount]) -> float:
    vals = sorted(a.health_score for a in accounts if a.health_score is not None)
    if not vals:
        return 50.0
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2.0


def _prepare(inp: RenewalAllocationInput) -> _Prepared:
    """Validate accounts against the contract; derive baselines; record exclusions."""

    median_health = _segment_median_health(inp.accounts)
    out: list[_Acct] = []
    excluded: list[str] = []
    fallbacks = 0
    for a in inp.accounts:
        # ARR/renewal_date are required per the Evidence Contract; exclude if unusable.
        if a.arr <= 0 or a.renewal_date is None:
            excluded.append(a.account_id)
            continue
        if a.baseline_renewal_probability is not None:
            baseline = a.baseline_renewal_probability
            fb = False
        else:
            health = a.health_score
            fb = health is None
            if fb:
                fallbacks += 1
                health = median_health
            baseline = baseline_probability_from_health(float(health))
        out.append(
            _Acct(
                account_id=a.account_id,
                name=a.name,
                arr=a.arr,
                segment=a.segment,
                csm_id=a.csm_id,
                baseline=baseline,
                health_fallback=fb,
            )
        )
    return _Prepared(accounts=out, excluded=excluded, health_fallbacks=fallbacks)


def _per_account_cap(
    constraints: RenewalConstraints, assumptions: InterventionAssumptions
) -> float:
    if constraints.max_hours_per_account is not None:
        return constraints.max_hours_per_account
    return assumptions.max_useful_hours_per_account


def _greedy_allocate(
    accounts: list[_Acct],
    *,
    total_hours: float,
    per_csm_hours: dict[str, float],
    per_account_cap: float,
    strategic_min: float,
    assumptions: InterventionAssumptions,
    step_hours: float = 1.0,
    seed_minimums: bool = True,
) -> dict[str, float]:
    """Allocate hours by highest marginal expected-ARR gain, respecting all ceilings.

    ``seed_minimums`` pre-allocates strategic minimums (the hard guarantee) before the
    greedy pass. Set it False to model a strategy that *ignores* the guarantee.
    """

    hours: dict[str, float] = {a.account_id: 0.0 for a in accounts}
    remaining = total_hours
    csm_left = dict(per_csm_hours)

    def csm_budget(a: _Acct) -> float:
        if a.csm_id is None or a.csm_id not in csm_left:
            return float("inf")
        return csm_left[a.csm_id]

    def spend(a: _Acct, amount: float) -> None:
        nonlocal remaining
        hours[a.account_id] += amount
        remaining -= amount
        if a.csm_id is not None and a.csm_id in csm_left:
            csm_left[a.csm_id] -= amount

    if seed_minimums and strategic_min > 0:
        for a in accounts:
            if a.segment is Segment.strategic:
                give = min(strategic_min, per_account_cap, csm_budget(a), max(0.0, remaining))
                if give > 0:
                    spend(a, give)

    # Marginal-greedy pass.
    while remaining > 1e-9:
        best: _Acct | None = None
        best_gain = 0.0
        this_step = min(step_hours, remaining)
        for a in accounts:
            headroom = min(per_account_cap - hours[a.account_id], csm_budget(a))
            if headroom < this_step - 1e-9:
                continue
            gain = marginal_uplift_arr(
                arr=a.arr,
                baseline=a.baseline,
                current_hours=hours[a.account_id],
                step_hours=this_step,
                segment=a.segment,
                assumptions=assumptions,
            )
            if gain > best_gain + 1e-12:
                best_gain = gain
                best = a
        if best is None or best_gain <= 1e-9:
            break
        spend(best, this_step)
    return hours


def _score_allocation(
    accounts: list[_Acct],
    hours: dict[str, float],
    *,
    assumptions: InterventionAssumptions,
) -> tuple[float, float, list[AccountAllocation]]:
    """Return (baseline_retained_arr, expected_retained_arr, per-account allocations)."""

    baseline_total = 0.0
    expected_total = 0.0
    allocs: list[AccountAllocation] = []
    for a in accounts:
        h = hours.get(a.account_id, 0.0)
        p_est = estimated_probability(
            baseline=a.baseline, hours=h, segment=a.segment, assumptions=assumptions
        )
        base_arr = a.arr * a.baseline
        est_arr = a.arr * p_est
        baseline_total += base_arr
        expected_total += est_arr
        if h > 0 and est_arr - base_arr > 1e-6:
            reason = f"{h:g}h → +${est_arr - base_arr:,.0f} expected retained ARR"
        elif a.segment is Segment.strategic and h > 0:
            reason = f"{h:g}h strategic-minimum guarantee"
        else:
            reason = "Not prioritized — lower marginal retained-ARR gain than funded accounts"
        allocs.append(
            AccountAllocation(
                account_id=a.account_id,
                name=a.name,
                segment=a.segment,
                arr=a.arr,
                hours=h,
                baseline_renewal_probability=round(a.baseline, 6),
                estimated_renewal_probability=round(p_est, 6),
                baseline_expected_retained_arr=round(base_arr, 2),
                estimated_expected_retained_arr=round(est_arr, 2),
                uplift_arr=round(est_arr - base_arr, 2),
                selected=h > 0,
                reason=reason,
            )
        )
    return baseline_total, expected_total, allocs


def _scenario(
    scenario_id: str,
    label: str,
    accounts: list[_Acct],
    hours: dict[str, float],
    *,
    total_hours: float,
    assumptions: InterventionAssumptions,
    strategic_min: float,
) -> ScenarioResult:
    baseline_total, expected_total, allocs = _score_allocation(
        accounts, hours, assumptions=assumptions
    )
    used = sum(hours.values())
    # Feasibility: strategic minimums honored + capacity not exceeded.
    feasible = True
    reason: str | None = None
    if used > total_hours + 1e-6:
        feasible = False
        reason = f"Uses {used:g}h > {total_hours:g}h available capacity"
    else:
        for a in accounts:
            if (
                a.segment is Segment.strategic
                and hours.get(a.account_id, 0.0) + 1e-9 < strategic_min
            ):
                feasible = False
                reason = (
                    f"Strategic account '{a.name}' receives "
                    f"{hours.get(a.account_id, 0.0):g}h < {strategic_min:g}h minimum guarantee"
                )
                break
    return ScenarioResult(
        id=scenario_id,
        label=label,
        feasible=feasible,
        rejected_reason=None if feasible else reason,
        total_hours_used=round(used, 4),
        capacity_utilization=round(used / total_hours, 4) if total_hours > 0 else 0.0,
        baseline_retained_arr=round(baseline_total, 2),
        expected_retained_arr=round(expected_total, 2),
        uplift_arr=round(expected_total - baseline_total, 2),
        allocations=allocs,
    )


def _alloc_signature(scenario: ScenarioResult) -> tuple[tuple[str, float], ...]:
    """Stable signature of *where* hours went — used to detect allocation changes."""

    return tuple(
        sorted((a.account_id, round(a.hours, 3)) for a in scenario.allocations if a.hours > 0)
    )


def _sensitivity(
    accounts: list[_Acct],
    inp: RenewalAllocationInput,
    base_recommended: ScenarioResult,
) -> list[SensitivityResult]:
    """Report how the recommendation responds to intervention-effectiveness.

    A *uniform* effectiveness change scales every account's marginal gain by the same factor,
    so it generally does not reorder the greedy allocation — it scales the *magnitude* of
    retained ARR, not *where* hours go. We report that honestly, plus the threshold (if any,
    down to a small floor) at which the allocation actually flips, and the magnitude at half
    the assumed effectiveness so the reader sees the real dependency.
    """

    base_sig = _alloc_signature(base_recommended)
    base_eff = inp.assumptions.effectiveness
    per_account_cap = _per_account_cap(inp.constraints, inp.assumptions)
    floor = 0.05

    def run_at(eff: float) -> ScenarioResult:
        trial_assumptions = inp.assumptions.model_copy(update={"effectiveness": max(0.0, eff)})
        hours = _greedy_allocate(
            accounts,
            total_hours=inp.capacity.total_hours,
            per_csm_hours=inp.capacity.per_csm_hours,
            per_account_cap=per_account_cap,
            strategic_min=inp.constraints.strategic_min_hours,
            assumptions=trial_assumptions,
            step_hours=inp.constraints.allocation_step_hours,
        )
        return _scenario(
            "trial",
            "trial",
            accounts,
            hours,
            total_hours=inp.capacity.total_hours,
            assumptions=trial_assumptions,
            strategic_min=inp.constraints.strategic_min_hours,
        )

    threshold: float | None = None
    steps = 20
    for i in range(1, steps + 1):
        eff = base_eff - (base_eff - floor) * (i / steps)
        if eff < floor - 1e-9:
            break
        if _alloc_signature(run_at(eff)) != base_sig:
            threshold = round(eff, 4)
            break

    half_eff = base_eff / 2.0
    half_uplift = run_at(half_eff).uplift_arr
    base_uplift = base_recommended.uplift_arr

    if threshold is None:
        desc = (
            f"The allocation is stable to intervention-effectiveness down to {floor:.2f} — "
            "a uniform change scales retained-ARR magnitude, not where hours go. "
            f"At half the assumed effectiveness ({half_eff:.2f}), estimated uplift falls to "
            f"~${half_uplift:,.0f} (from ~${base_uplift:,.0f})."
        )
    else:
        desc = (
            f"The recommended allocation changes if intervention effectiveness falls below "
            f"{threshold:.2f} (base assumption {base_eff:.2f}). At half effectiveness "
            f"({half_eff:.2f}), estimated uplift ~${half_uplift:,.0f} (from ~${base_uplift:,.0f})."
        )
    return [
        SensitivityResult(
            parameter="intervention_effectiveness",
            base_value=base_eff,
            threshold_value=threshold,
            direction="below",
            description=desc,
        )
    ]


def solve(inp: RenewalAllocationInput) -> RenewalAllocationResult:
    """Run the full renewal-capacity-allocation analysis. Deterministic and reproducible."""

    prepared = _prepare(inp)
    accounts = prepared.accounts

    quality = assess_evidence(
        account_count=len(accounts),
        excluded_account_count=len(prepared.excluded),
        health_fallback_count=prepared.health_fallbacks,
        max_health_age_days=None,
        max_arr_age_days=None,
        available_hours=inp.capacity.total_hours,
    )

    strategic_min = inp.constraints.strategic_min_hours
    per_account_cap = _per_account_cap(inp.constraints, inp.assumptions)
    strategic = [a for a in accounts if a.segment is Segment.strategic]
    required_strategic_hours = len(strategic) * strategic_min

    # ── feasibility (hard constraints genuinely enforced) ──────────────────────────
    if not quality.ok:
        block = quality.blocking[0]
        return RenewalAllocationResult(
            model_version=MODEL_VERSION,
            feasible=False,
            no_feasible_solution=NoFeasibleSolution(
                binding_constraint=block.concept,
                detail=block.detail,
                suggested_relaxations=[
                    "Provide the missing required evidence (ARR, renewal date, or capacity)."
                ],
            ),
            data_quality_score=quality.data_quality_score,
            evidence_notes=[i.detail for i in quality.issues],
        )

    # A strategic minimum larger than the per-account cap (which defaults to the model's
    # max useful hours when max_hours_per_account is unset) is unachievable for any single
    # account — the guarantee can never be met, so this is a no-feasible-solution, not a
    # silently-broken constraint.
    if strategic and strategic_min > per_account_cap + 1e-9:
        return RenewalAllocationResult(
            model_version=MODEL_VERSION,
            feasible=False,
            no_feasible_solution=NoFeasibleSolution(
                binding_constraint="strategic_min_hours",
                detail=(
                    f"strategic_min_hours ({strategic_min:g}h) exceeds the per-account ceiling "
                    f"({per_account_cap:g}h), so no strategic account can receive its guaranteed "
                    "minimum."
                ),
                suggested_relaxations=[
                    f"Lower strategic_min_hours to at most {per_account_cap:g}h.",
                    "Raise max_hours_per_account (or the model's max useful hours) above "
                    f"{strategic_min:g}h.",
                ],
            ),
            data_quality_score=quality.data_quality_score,
            evidence_notes=[i.detail for i in quality.issues],
        )

    if required_strategic_hours > inp.capacity.total_hours + 1e-6:
        return RenewalAllocationResult(
            model_version=MODEL_VERSION,
            feasible=False,
            no_feasible_solution=NoFeasibleSolution(
                binding_constraint="strategic_min_hours",
                detail=(
                    f"{len(strategic)} strategic accounts require {required_strategic_hours:g}h of "
                    f"guaranteed minimums but only {inp.capacity.total_hours:g}h are available."
                ),
                suggested_relaxations=[
                    f"Lower strategic_min_hours (currently {strategic_min:g}h).",
                    f"Increase available capacity above {required_strategic_hours:g}h.",
                    "Reduce the number of strategic accounts in scope.",
                ],
            ),
            data_quality_score=quality.data_quality_score,
            evidence_notes=[i.detail for i in quality.issues],
        )

    # per-CSM feasibility for strategic minimums
    if inp.capacity.per_csm_hours:
        csm_required: dict[str, float] = {}
        for a in strategic:
            if a.csm_id is not None:
                csm_required[a.csm_id] = csm_required.get(a.csm_id, 0.0) + strategic_min
        for csm_id, need in csm_required.items():
            have = inp.capacity.per_csm_hours.get(csm_id, float("inf"))
            if need > have + 1e-6:
                return RenewalAllocationResult(
                    model_version=MODEL_VERSION,
                    feasible=False,
                    no_feasible_solution=NoFeasibleSolution(
                        binding_constraint="per_csm_capacity",
                        detail=(
                            f"CSM '{csm_id}' owns strategic accounts needing {need:g}h of minimums "
                            f"but has only {have:g}h."
                        ),
                        suggested_relaxations=[
                            f"Rebalance strategic accounts off CSM '{csm_id}'.",
                            f"Raise CSM '{csm_id}' capacity to at least {need:g}h.",
                            "Lower strategic_min_hours.",
                        ],
                    ),
                    data_quality_score=quality.data_quality_score,
                    evidence_notes=[i.detail for i in quality.issues],
                )

    # ── scenarios ──────────────────────────────────────────────────────────────────
    zero_hours = {a.account_id: 0.0 for a in accounts}
    baseline_scn = _scenario(
        "baseline",
        "Baseline — no additional intervention",
        accounts,
        zero_hours,
        total_hours=inp.capacity.total_hours,
        assumptions=inp.assumptions,
        strategic_min=0.0,  # baseline = do-nothing reference; guarantee not claimed here
    )
    baseline_scn.feasible = True
    baseline_scn.rejected_reason = None

    recommended_hours = _greedy_allocate(
        accounts,
        total_hours=inp.capacity.total_hours,
        per_csm_hours=inp.capacity.per_csm_hours,
        per_account_cap=per_account_cap,
        strategic_min=strategic_min,
        assumptions=inp.assumptions,
        step_hours=inp.constraints.allocation_step_hours,
    )
    recommended_scn = _scenario(
        "recommended",
        "Recommended — marginal-optimal allocation",
        accounts,
        recommended_hours,
        total_hours=inp.capacity.total_hours,
        assumptions=inp.assumptions,
        strategic_min=strategic_min,
    )

    # A tempting-but-infeasible alternative: concentrate on the highest-ARR accounts,
    # ignoring the strategic-minimum guarantee. Demonstrates real constraint enforcement.
    concentrate_hours = {a.account_id: 0.0 for a in accounts}
    remaining = inp.capacity.total_hours
    csm_left = dict(inp.capacity.per_csm_hours)
    for a in sorted(accounts, key=lambda x: x.arr, reverse=True):
        if remaining <= 0:
            break
        budget = csm_left.get(a.csm_id, float("inf")) if a.csm_id else float("inf")
        give = min(per_account_cap, budget, remaining)
        if give > 0:
            concentrate_hours[a.account_id] = give
            remaining -= give
            if a.csm_id in csm_left:
                csm_left[a.csm_id] -= give
    concentrate_scn = _scenario(
        "concentrate_top_arr",
        "Concentrate on highest-ARR accounts",
        accounts,
        concentrate_hours,
        total_hours=inp.capacity.total_hours,
        assumptions=inp.assumptions,
        strategic_min=strategic_min,
    )

    scenarios = [baseline_scn, recommended_scn, concentrate_scn]

    # Rank feasible scenarios by expected retained ARR; on a tie prefer the guarantee-honoring
    # "recommended" scenario over the baseline/concentrate alternatives.
    feasible = [s for s in scenarios if s.feasible]
    feasible.sort(key=lambda s: (s.expected_retained_arr, s.id == "recommended"), reverse=True)
    for rank, s in enumerate(feasible, start=1):
        s.rank = rank
    # The do-nothing baseline is a reference only — it does not honor the strategic-minimum
    # guarantee, so it is never the recommendation. Recommend the best feasible non-baseline one.
    candidates = [s for s in feasible if s.id != "baseline"]
    recommended_id = candidates[0].id if candidates else None

    # ── constraint statuses ──────────────────────────────────────────────────────────
    used = recommended_scn.total_hours_used
    constraints = [
        ConstraintStatus(
            name="total_capacity",
            kind="hard",
            satisfied=used <= inp.capacity.total_hours + 1e-6,
            detail=f"{used:g}h used of {inp.capacity.total_hours:g}h available",
            slack=round(inp.capacity.total_hours - used, 4),
        ),
        ConstraintStatus(
            name="strategic_min_hours",
            kind="hard",
            satisfied=all(
                recommended_hours.get(a.account_id, 0.0) + 1e-9 >= strategic_min for a in strategic
            ),
            detail=f"{len(strategic)} strategic account(s) each guaranteed ≥ {strategic_min:g}h",
        ),
    ]

    sensitivity = _sensitivity(accounts, inp, recommended_scn)

    # ── provenance separation + honesty ────────────────────────────────────────────
    provenance = _provenance(inp, prepared, recommended_scn)
    confidence = inp.assumptions.confidence
    if quality.confidence_downgraded and confidence is not ConfidenceLevel.low:
        confidence = (
            ConfidenceLevel.low
            if confidence is ConfidenceLevel.medium
            else ConfidenceLevel.medium
        )

    return RenewalAllocationResult(
        model_version=MODEL_VERSION,
        feasible=True,
        recommended_scenario_id=recommended_id,
        scenarios=scenarios,
        constraints=constraints,
        sensitivity=sensitivity,
        provenance=provenance,
        data_quality_score=quality.data_quality_score,
        confidence=confidence,
        confidence_downgraded=quality.confidence_downgraded,
        evidence_notes=[i.detail for i in quality.issues],
    )


def _provenance(inp, prepared, recommended):  # type: ignore[no-untyped-def]
    from .contract import ProvenanceSeparation

    facts = [
        f"{len(prepared.accounts)} renewal accounts in scope with validated ARR and renewal date.",
        f"{inp.capacity.total_hours:g}h of customer-success capacity available.",
    ]
    if prepared.excluded:
        facts.append(f"{len(prepared.excluded)} account(s) excluded for missing required evidence.")
    assumptions = [
        f"Intervention effectiveness = {inp.assumptions.effectiveness:.2f} "
        f"({inp.assumptions.source_of_estimate}, {inp.assumptions.calibration_status}).",
        f"Saturation at {inp.assumptions.saturation_hours:g}h; max useful "
        f"{inp.assumptions.max_useful_hours_per_account:g}h/account.",
        f"Strategic minimum = {inp.constraints.strategic_min_hours:g}h (hard).",
    ]
    estimated = [
        "Baseline renewal probabilities derived from account health via the outcome-model curve.",
    ]
    if prepared.health_fallbacks:
        estimated.append(
            f"{prepared.health_fallbacks} account(s) used the segment-median health fallback."
        )
    simulated = [
        f"Expected retained ARR under the recommendation: "
        f"${recommended.expected_retained_arr:,.0f} "
        f"(+${recommended.uplift_arr:,.0f} vs baseline).",
    ]
    return ProvenanceSeparation(
        observed_facts=facts,
        customer_assumptions=assumptions,
        estimated_parameters=estimated,
        simulated_outcomes=simulated,
    )
