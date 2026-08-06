"""test_optimization_robust.mojo — known-value tests for scenario robustness.

Hand-written. Every expected number below was computed by hand or is closed-form before it
was run, and the assertions target the specific wrong answers this module exists not to
produce:

  * the WAIT-AND-SEE worst case is asserted to come back under `ROBUST_BOUND_ONLY` and never
    under a success code, and its relationship to the here-and-now answer is asserted as an
    INEQUALITY in the direction the theory gives (`R >= W` when minimising) — including one
    program where it is strict by construction (`W = 3`, `R = 6`) and one where the robust
    program is INFEASIBLE while every individual scenario solves, which is that gap taken to
    infinity;
  * the here-and-now answer is cross-checked against an INDEPENDENT oracle: the test builds
    the elementwise-tightest right-hand side itself, over three rows of mixed sense, and
    calls the frozen `lp_solve_default` directly. Agreement of two different constructions is
    evidence; the driver agreeing with itself is not;
  * `S` IDENTICAL scenarios must reproduce the deterministic answer EXACTLY — same objective,
    same vertex, same duals as `lp_solve_default` on the one program — which is the strongest
    cross-check available here and the one a wrong sense convention or a stray averaging step
    cannot pass;
  * the chance-constraint rate is asserted at a rate that is exactly representable, 3 of 4, so
    the comparison against 0.7, 0.75 and 0.8 is exact arithmetic and the boundary case is a
    real boundary. The rate, the count, the per-row verdict, the JOINT rate and the binomial
    standard error are all asserted, because a status that says "met" while hiding a rate of
    0.75 is the exact failure this module is written against;
  * CVaR is asserted at three levels against hand-computed averages of the worst scenarios
    (35 at 0.5, 30 at 0.25, 40 at 1.0 = the worst case), so a plausible-looking risk number
    cannot pass;
  * feasibility is asserted PER ROW at magnitude 1e9, where a violation of exactly 1.0 must
    still be a violation, and beside a 1e7 row that must not buy a small row a pass — a
    tolerance scaled by anything summed over rows fails both halves;
  * determinism is asserted three ways: the same seed and stream give a BIT-IDENTICAL scenario
    block and a bit-identical rate, a different seed gives a different block, and the same
    seed on a different stream name gives a different block. Two exact rate values (0.75 at
    seed 1000, 0.25 at seed 1035) pin the draw coordinates themselves: if either changes, the
    `(seed, scenario, row, stream)` layout moved and every stored robust answer means
    something else;
  * common random numbers are asserted as prefix stability — drawing more scenarios, or more
    rows, leaves the earlier draws bit-identical;
  * every DIRECTION statement is asserted as a direction, not as a number, because an inverted
    one cannot be detected downstream: the true-support bound is asserted UPPER when maximising
    and LOWER when minimising by solving the same program over a WIDER scenario set and checking
    which way the optimum moved (3 -> 1 maximising, 10 -> 18 minimising), and the claim the
    module docstring used to make unconditionally is asserted to be measurably FALSE for the
    maximisation. `cvar_level` is asserted to be a CONFIDENCE and not a tail fraction at six
    levels against hand-computed tail averages (0.05 -> 50, 0.5 -> 65, 1.0 -> 100 = the worst
    case, mean 40), monotone in the level, with `cvar_tail_fraction` reported alongside;
  * the chance driver's coverage is asserted to include `x >= 0`, the other half of the feasible
    set the two solve drivers verify: a point at x = -5 whose row holds in 4 of 4 scenarios
    reports rate 1.00 AND joint 0.00 under `ROBUST_CHANCE_NOT_MET`, with the rate never hidden;
  * evidence is asserted to be evidence: 1000 scenarios with an EMPTY block verify ONE distinct
    right-hand side, not the base row a thousand times, and an input rejection is asserted to
    leave `lp_status` at MODEL_OK rather than copying a robust code into a field whose vocabulary
    belongs to another module;
  * bounding memory is asserted not to bound WORK: a scenario count inside every allocation
    ceiling that would take ~29 s of single-threaded CPU is refused on all four sweeping entry
    points, while an ordinary 1000-scenario sweep is not;
  * self-consistency is asserted as a PROPERTY over every min-max result in the suite — a
    certificate implies an objective, a direction, a clean verification and a full rate; an
    absent answer implies no objective, no x and no direction;
  * an answer that does not exist is asserted ABSENT: an infeasible robust program, an
    unbounded one, an equality row whose right-hand side varies, and a scenario set with one
    infeasible member all return no objective and an EMPTY `x`, with the per-scenario status
    record still populated so the caller can see which scenario failed and why;
  * the whole rejection surface is asserted not to index anything: the generated A-Z suite's
    sample arguments (`rows = cols = 5` against a 5-element matrix), a wrapping scenario count
    (`6148914691236517206`), an allocation bomb (`S = 2^30` with 3 rows, which would be 25 GB),
    a row count of `2^26` with an empty payload, a `nan` scenario cell, a negative dispersion,
    and a level of 0 or 1.5 — each a distinct status, none a crash, none an allocation.

Exact equality (`==`) is used wherever the arithmetic is exact in binary floating point: the
identical-scenario cross-check, the integer vertices, the rates 0.75 / 0.25 / 1.0, the
zero-half-width uniform draws, and every determinism comparison. A tolerance appears only
where a division genuinely rounds — the CVaR averages over three scenarios and the binomial
standard error.
"""
from optimization.linear import (
    LP_INFEASIBLE,
    LP_OPTIMAL,
    lp_solve_default,
)
from optimization.model import (
    MODEL_ERR_DENSE_SHAPE,
    MODEL_ERR_LENGTH_MISMATCH,
    MODEL_ERR_NON_FINITE_RHS,
    MODEL_ERR_POINT_LENGTH,
    MODEL_OK,
    SENSE_EQ,
    SENSE_GE,
    SENSE_LE,
)
from optimization.robust import (
    ChanceResult,
    ROBUST_BOUND_ONLY,
    ROBUST_CHANCE_NOT_MET,
    ROBUST_EQ_CONFLICT,
    ROBUST_ERR_CONFIDENCE,
    ROBUST_ERR_DISPERSION,
    ROBUST_ERR_SCENARIO_SHAPE,
    ROBUST_ERR_WORK_BUDGET,
    ROBUST_INFEASIBLE,
    ROBUST_MAX_SCENARIOS,
    ROBUST_SCENARIO_FAILED,
    ROBUST_UNBOUNDED,
    ROBUST_UNVERIFIED,
    RobustMinMaxResult,
    RobustScenarioResult,
    ScenarioSet,
    _bound_direction_agrees,
    robust_chance_normal,
    robust_chance_rates,
    robust_min_max_rhs,
    robust_min_max_rhs_default,
    robust_scenario_solve,
    robust_scenario_solve_default,
    robust_status_name,
    scenario_rhs_normal,
    scenario_rhs_uniform,
)


def _lf(*values: Float64) -> List[Float64]:
    var out = List[Float64]()
    for v in values:
        out.append(v)
    return out^


def _li(*values: Int) -> List[Int]:
    var out = List[Int]()
    for v in values:
        out.append(v)
    return out^


def _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    var d = a - b
    if d < 0.0:
        d = -d
    return d <= tol


def _blocks_equal(a: List[Float64], b: List[Float64]) -> Bool:
    """Bit-identical, element for element. `==` on Float64, deliberately no tolerance."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


def _blocks_differ(a: List[Float64], b: List[Float64]) -> Bool:
    if len(a) != len(b):
        return True
    for i in range(len(a)):
        if a[i] != b[i]:
            return True
    return False


def _no_numbers(r: RobustScenarioResult) -> Bool:
    """An absent answer: no aggregate, no per-scenario objective, no bound direction."""
    return (
        not r.has_value
        and len(r.objectives) == 0
        and r.bound_direction == 0
        and not r.has_cvar
        and r.worst_scenario == -1
        and r.best_scenario == -1
    )


def _mm_self_consistent(r: RobustMinMaxResult) -> Bool:
    """Every claim a min-max result makes must agree with every other claim it makes.

    Two mutually exclusive fields in one returned value leave a caller able to use neither, so
    this is asserted as a property rather than checked case by case: a certified answer has an
    objective, a direction, a clean verification and a full rate, and an absent answer has no
    objective, no direction and no certificate.
    """
    if r.optimal_for_scenario_set:
        return (
            r.has_objective
            and r.bound_direction != 0
            and r.worst_violation == 0.0
            and r.worst_violation_row == -1
            and r.worst_violation_scenario == -1
            and r.n_violating_scenarios == 0
            and r.n_verified_scenarios == r.n_distinct_scenarios
            and r.feasible_rate == 1.0
        )
    if not r.has_objective:
        return r.bound_direction == 0 and len(r.x) == 0
    return True


def _mm_absent(r: RobustMinMaxResult) -> Bool:
    """An absent min-max answer: no objective, no x, no direction, no certificate."""
    return (
        not r.has_objective
        and len(r.x) == 0
        and r.bound_direction == 0
        and not r.optimal_for_scenario_set
        and _mm_self_consistent(r)
    )


def main() raises:
    var passed = 0
    var failed = 0

    # ── two scenarios, worst case by hand ────────────────────────────────────
    # minimise 2x subject to x >= b, x >= 0. The optimum is 2b, so the two scenarios
    # b = 3 and b = 5 give 6 and 10; the worst case is 10 and scenario 1 is what makes it so.
    var c1 = _lf(2.0)
    var a1 = _lf(1.0)
    var ge1 = _li(SENSE_GE)
    var b1 = _lf(0.0)
    var two = robust_scenario_solve_default(c1, a1, 1, 1, ge1, b1, False, 2, _lf(3.0, 5.0), 0.5)
    if (
        two.status == ROBUST_BOUND_ONLY
        and two.has_value
        and two.n_solved == 2
        and two.n_failed == 0
        and two.objectives[0] == 6.0
        and two.objectives[1] == 10.0
        and two.worst_case == 10.0
        and two.worst_scenario == 1
        and two.best_case == 6.0
        and two.best_scenario == 0
        and two.mean_objective == 8.0
        and two.bound_direction == -1
    ):
        passed += 1
        print("  ✅ two scenarios: worst 10 at scenario 1, best 6, mean 8, reported as a bound")
    else:
        failed += 1
        print(
            "  ❌ two-scenario worst case wrong:",
            two.status, two.worst_case, two.worst_scenario, two.mean_objective,
        )

    # ── the success code is NOT MODEL_OK, and says which side it bounds ──────
    # A perfect-foresight number under a plain success status is the wrong answer this driver
    # is written against, so the code itself is asserted.
    # maximise 2x subject to x <= b: the optima are again 6 and 10, but the WORST case for a
    # maximiser is the SMALLEST of them, so the extreme flips to scenario 0 and the bound
    # becomes an upper one.
    var maxi = robust_scenario_solve_default(
        c1, a1, 1, 1, _li(SENSE_LE), b1, True, 2, _lf(3.0, 5.0), 0.5
    )
    if (
        two.status != MODEL_OK
        and robust_status_name(two.status) == "found_but_only_a_bound_on_the_robust_value"
        and maxi.status == ROBUST_BOUND_ONLY
        and maxi.bound_direction == 1
        and maxi.worst_case == 6.0
        and maxi.worst_scenario == 0
    ):
        passed += 1
        print("  ✅ wait-and-see never reports MODEL_OK; bound_direction flips with the sense")
    else:
        failed += 1
        print("  ❌ bound status wrong:", two.status, maxi.status, maxi.bound_direction)

    # ── CVaR at three levels, hand-computed ─────────────────────────────────
    # Scenarios b = 5, 10, 15, 20 give costs 10, 20, 30, 40.
    #   level 1.00 -> the worst 1 scenario          -> 40
    #   level 0.50 -> the worst 2, averaged         -> (30 + 40) / 2 = 35
    #   level 0.25 -> the worst 3, averaged         -> (20 + 30 + 40) / 3 = 30
    # and the mean of all four is 25, which CVaR must not be confused with.
    var block4 = _lf(5.0, 10.0, 15.0, 20.0)
    var r50 = robust_scenario_solve_default(c1, a1, 1, 1, ge1, b1, False, 4, block4, 0.5)
    var r25 = robust_scenario_solve_default(c1, a1, 1, 1, ge1, b1, False, 4, block4, 0.25)
    var r100 = robust_scenario_solve_default(c1, a1, 1, 1, ge1, b1, False, 4, block4, 1.0)
    if (
        r50.has_cvar
        and _close(r50.cvar, 35.0, 1e-12)
        and _close(r25.cvar, 30.0, 1e-12)
        and r100.cvar == 40.0
        and r100.cvar == r100.worst_case
        and r50.mean_objective == 25.0
        and r50.worst_case == 40.0
        and r50.worst_scenario == 3
        and r50.best_case == 10.0
        and r50.cvar_level == 0.5
    ):
        passed += 1
        print("  ✅ CVaR is 35 at 0.5, 30 at 0.25 and the worst case at 1.0; mean stays 25")
    else:
        failed += 1
        print("  ❌ CVaR wrong:", r50.cvar, r25.cvar, r100.cvar, r50.mean_objective)

    # ── identical scenarios must reproduce the deterministic answer exactly ──
    # maximise 3x + 5y subject to x <= 4, 2y <= 12, 3x + 2y <= 18. The optimum is (2, 6) with
    # value 36, and three copies of that program cannot have any other answer — objective,
    # vertex and duals all compared to the frozen `lp_solve_default` with ==, not a tolerance.
    var c3 = _lf(3.0, 5.0)
    var a3 = _lf(1.0, 0.0, 0.0, 2.0, 3.0, 2.0)
    var s3 = _li(SENSE_LE, SENSE_LE, SENSE_LE)
    var b3 = _lf(4.0, 12.0, 18.0)
    var same3 = _lf(4.0, 12.0, 18.0, 4.0, 12.0, 18.0, 4.0, 12.0, 18.0)
    var det = lp_solve_default(c3, a3, 3, 2, s3, b3, True)
    var ws = robust_scenario_solve_default(c3, a3, 3, 2, s3, b3, True, 3, same3, 0.5)
    var hn = robust_min_max_rhs_default(c3, a3, 3, 2, s3, b3, True, 3, same3)
    if (
        det.status == LP_OPTIMAL
        and det.objective == 36.0
        and ws.status == ROBUST_BOUND_ONLY
        and ws.worst_case == det.objective
        and ws.best_case == det.objective
        and ws.mean_objective == det.objective
        and ws.cvar == det.objective
        and ws.worst_scenario == 0
        and ws.best_scenario == 0
        and hn.status == MODEL_OK
        and hn.has_objective
        and hn.objective == det.objective
        and hn.x[0] == det.x[0]
        and hn.x[1] == det.x[1]
        and hn.x[0] == 2.0
        and hn.x[1] == 6.0
        and hn.duals[0] == det.duals[0]
        and hn.duals[1] == det.duals[1]
        and hn.duals[2] == det.duals[2]
        and hn.optimal_for_scenario_set
        and hn.n_verified_scenarios == 3
        and hn.n_violating_scenarios == 0
        and hn.feasible_rate == 1.0
        and hn.worst_violation == 0.0
    ):
        passed += 1
        print("  ✅ 3 identical scenarios reproduce lp_solve_default exactly, duals included")
    else:
        failed += 1
        print(
            "  ❌ identical-scenario cross-check failed:",
            ws.worst_case, hn.status, hn.objective, len(hn.x), hn.feasible_rate,
        )

    # An EMPTY scenario block means "nothing varies", which must be the same answer again.
    var ws_empty = robust_scenario_solve_default(c3, a3, 3, 2, s3, b3, True, 4, _lf(), 0.5)
    var hn_empty = robust_min_max_rhs_default(c3, a3, 3, 2, s3, b3, True, 4, _lf())
    if (
        ws_empty.status == ROBUST_BOUND_ONLY
        and len(ws_empty.objectives) == 4
        and ws_empty.worst_case == 36.0
        and ws_empty.best_case == 36.0
        and hn_empty.status == MODEL_OK
        and hn_empty.objective == 36.0
        and hn_empty.binding_scenario[0] == -1
        and hn_empty.effective_rhs[0] == 4.0
        and not hn_empty.scenario_data_given
        and hn_empty.n_distinct_scenarios == 1
        and hn_empty.n_verified_scenarios == 1
        and hn_empty.n_scenarios == 4
    ):
        passed += 1
        print("  ✅ an empty scenario block is S copies of the base program, not a rejection")
    else:
        failed += 1
        print("  ❌ empty-block handling wrong:", ws_empty.status, hn_empty.status, hn_empty.objective)

    # ── the robust answer is strictly worse than the wait-and-see bound ──────
    # minimise x0 + x1 subject to x0 >= b0, x1 >= b1. Scenario A = (3, 0), scenario B = (0, 3).
    # Each scenario alone costs 3, so W = 3. A point feasible in BOTH needs x0 >= 3 and
    # x1 >= 3, so R = 6. Any implementation that reports 3 as the robust value is claiming a
    # solution that does not exist.
    var c2 = _lf(1.0, 1.0)
    var a2 = _lf(1.0, 0.0, 0.0, 1.0)
    var s2 = _li(SENSE_GE, SENSE_GE)
    var b2 = _lf(0.0, 0.0)
    var gapblk = _lf(3.0, 0.0, 0.0, 3.0)
    var w_gap = robust_scenario_solve_default(c2, a2, 2, 2, s2, b2, False, 2, gapblk, 1.0)
    var r_gap = robust_min_max_rhs_default(c2, a2, 2, 2, s2, b2, False, 2, gapblk)
    if (
        w_gap.status == ROBUST_BOUND_ONLY
        and w_gap.objectives[0] == 3.0
        and w_gap.objectives[1] == 3.0
        and w_gap.worst_case == 3.0
        and r_gap.status == MODEL_OK
        and r_gap.objective == 6.0
        and r_gap.x[0] == 3.0
        and r_gap.x[1] == 3.0
        and r_gap.objective > w_gap.worst_case
        and r_gap.effective_rhs[0] == 3.0
        and r_gap.effective_rhs[1] == 3.0
        and r_gap.binding_scenario[0] == 0
        and r_gap.binding_scenario[1] == 1
    ):
        passed += 1
        print("  ✅ R = 6 strictly exceeds the wait-and-see bound W = 3, with binding scenarios")
    else:
        failed += 1
        print(
            "  ❌ bound ordering wrong:",
            w_gap.worst_case, r_gap.status, r_gap.objective, len(r_gap.x),
        )

    # ── an independent oracle for the intersection, mixed senses ────────────
    # minimise x0 + x1 subject to x0 + x1 >= b0, x0 <= b1, x1 <= b2, over four scenarios. The
    # test builds the elementwise-tightest right-hand side ITSELF — max for the >= row, min
    # for the two <= rows — and solves that with the frozen simplex directly.
    var cm = _lf(1.0, 1.0)
    var am = _lf(1.0, 1.0, 1.0, 0.0, 0.0, 1.0)
    var sm = _li(SENSE_GE, SENSE_LE, SENSE_LE)
    var bm = _lf(0.0, 0.0, 0.0)
    var mblk = _lf(
        4.0, 3.0, 3.0,
        5.0, 10.0, 10.0,
        3.0, 3.0, 4.0,
        4.5, 5.0, 5.0,
    )
    var oracle_rhs = _lf(5.0, 3.0, 3.0)  # max(4, 5, 3, 4.5) ; min(3, 10, 3, 5) ; min(3, 10, 4, 5)
    var oracle = lp_solve_default(cm, am, 3, 2, sm, oracle_rhs, False)
    var mixed = robust_min_max_rhs_default(cm, am, 3, 2, sm, bm, False, 4, mblk)
    var w_mixed = robust_scenario_solve_default(cm, am, 3, 2, sm, bm, False, 4, mblk, 1.0)
    if (
        oracle.status == LP_OPTIMAL
        and oracle.objective == 5.0
        and mixed.status == MODEL_OK
        and mixed.objective == oracle.objective
        and mixed.effective_rhs[0] == 5.0
        and mixed.effective_rhs[1] == 3.0
        and mixed.effective_rhs[2] == 3.0
        and mixed.binding_scenario[0] == 1
        and mixed.binding_scenario[1] == 0
        and mixed.binding_scenario[2] == 0
        and mixed.n_verified_scenarios == 4
        and w_mixed.worst_case == 5.0
        and mixed.objective >= w_mixed.worst_case
    ):
        passed += 1
        print("  ✅ the mixed-sense intersection matches an independently built oracle LP")
    else:
        failed += 1
        print(
            "  ❌ intersection oracle mismatch:",
            mixed.status, mixed.objective, oracle.objective, len(mixed.effective_rhs),
        )

    # ── robust infeasible while every scenario is individually feasible ─────
    # minimise x subject to x <= b0, x >= b1. Scenario A = (1, 0) costs 0; scenario B = (5, 3)
    # costs 3. The intersection needs x <= 1 and x >= 3, so no point is feasible in both.
    var ci = _lf(1.0)
    var ai = _lf(1.0, 1.0)
    var si = _li(SENSE_LE, SENSE_GE)
    var bi = _lf(0.0, 0.0)
    var iblk = _lf(1.0, 0.0, 5.0, 3.0)
    var w_inf = robust_scenario_solve_default(ci, ai, 2, 1, si, bi, False, 2, iblk, 1.0)
    var r_inf = robust_min_max_rhs_default(ci, ai, 2, 1, si, bi, False, 2, iblk)
    if (
        w_inf.status == ROBUST_BOUND_ONLY
        and w_inf.objectives[0] == 0.0
        and w_inf.objectives[1] == 3.0
        and w_inf.worst_case == 3.0
        and r_inf.status == ROBUST_INFEASIBLE
        and not r_inf.has_objective
        and len(r_inf.x) == 0
        and not r_inf.optimal_for_scenario_set
        and r_inf.lp_status == LP_INFEASIBLE
        and r_inf.effective_rhs[0] == 1.0
        and r_inf.effective_rhs[1] == 3.0
        and robust_status_name(r_inf.status) == "no_point_feasible_in_every_scenario"
    ):
        passed += 1
        print("  ✅ a robust program with no feasible point returns NO x, not the closest one")
    else:
        failed += 1
        print(
            "  ❌ robust infeasibility wrong:",
            r_inf.status, r_inf.has_objective, len(r_inf.x), w_inf.worst_case,
        )

    # ── an unbounded robust program has no optimum ───────────────────────────
    var unb = robust_min_max_rhs_default(ci, _lf(1.0), 1, 1, _li(SENSE_GE), _lf(0.0), True, 2, _lf(1.0, 2.0))
    var unb_ws = robust_scenario_solve_default(
        ci, _lf(1.0), 1, 1, _li(SENSE_GE), _lf(0.0), True, 2, _lf(1.0, 2.0), 0.5
    )
    if (
        unb.status == ROBUST_UNBOUNDED
        and not unb.has_objective
        and len(unb.x) == 0
        and unb_ws.status == ROBUST_SCENARIO_FAILED
        and _no_numbers(unb_ws)
        and unb_ws.n_failed == 2
        and unb_ws.n_solved == 0
    ):
        passed += 1
        print("  ✅ unbounded is its own status on both drivers, with no numbers attached")
    else:
        failed += 1
        print("  ❌ unbounded handling wrong:", unb.status, unb_ws.status, unb_ws.n_failed)

    # ── one infeasible scenario withholds every aggregate ────────────────────
    # Scenario 1 is x <= 1 and x >= 5. The per-scenario record still names it.
    var fblk = _lf(1.0, 0.0, 1.0, 5.0)
    var fr = robust_scenario_solve_default(ci, ai, 2, 1, si, bi, False, 2, fblk, 1.0)
    if (
        fr.status == ROBUST_SCENARIO_FAILED
        and _no_numbers(fr)
        and fr.n_failed == 1
        and fr.n_solved == 1
        and fr.first_failed_scenario == 1
        and fr.first_failed_status == LP_INFEASIBLE
        and len(fr.scenario_status) == 2
        and fr.scenario_status[0] == LP_OPTIMAL
        and fr.scenario_status[1] == LP_INFEASIBLE
        and fr.worst_case == 0.0
    ):
        passed += 1
        print("  ✅ one infeasible scenario: no worst case over the subset, but a full record")
    else:
        failed += 1
        print(
            "  ❌ scenario failure handling wrong:",
            fr.status, fr.n_failed, fr.first_failed_scenario, len(fr.objectives),
        )

    # ── an equality row whose right-hand side varies has an empty intersection ─
    var eq_bad = robust_min_max_rhs_default(
        ci, _lf(1.0), 1, 1, _li(SENSE_EQ), _lf(0.0), False, 2, _lf(3.0, 4.0)
    )
    var eq_ok = robust_min_max_rhs_default(
        ci, _lf(1.0), 1, 1, _li(SENSE_EQ), _lf(0.0), False, 2, _lf(3.0, 3.0)
    )
    if (
        eq_bad.status == ROBUST_EQ_CONFLICT
        and eq_bad.conflict_row == 0
        and not eq_bad.has_objective
        and len(eq_bad.x) == 0
        and eq_ok.status == MODEL_OK
        and eq_ok.objective == 3.0
        and eq_ok.x[0] == 3.0
        and eq_ok.effective_rhs[0] == 3.0
        and eq_ok.binding_scenario[0] == -1
        and eq_ok.n_verified_scenarios == 2
    ):
        passed += 1
        print("  ✅ a varying equality row is a named conflict; a constant one solves")
    else:
        failed += 1
        print("  ❌ equality handling wrong:", eq_bad.status, eq_bad.conflict_row, eq_ok.status)

    # ── the chance constraint that is met in exactly 3 of 4 scenarios ────────
    # x = 10 against x <= b with b = 12, 10, 10.5, 9. The scenario b = 10 holds AT equality and
    # counts; b = 9 is violated by 1.0 and does not. So the rate is exactly 3/4.
    var x1 = _lf(10.0)
    var le1 = _li(SENSE_LE)
    var cblk = _lf(12.0, 10.0, 10.5, 9.0)
    var at70 = robust_chance_rates(x1, a1, 1, 1, le1, cblk, 4, 0.7, 1e-9)
    var at75 = robust_chance_rates(x1, a1, 1, 1, le1, cblk, 4, 0.75, 1e-9)
    var at80 = robust_chance_rates(x1, a1, 1, 1, le1, cblk, 4, 0.8, 1e-9)
    if (
        at70.has_rates
        and at70.rates[0] == 0.75
        and at70.counts[0] == 3
        and at70.n_scenarios == 4
        and at70.status == MODEL_OK
        and at70.met[0]
        and at70.all_rows_met
        and at70.joint_rate == 0.75
        and at70.joint_met
        and at75.status == MODEL_OK
        and at75.met[0]
        and at80.status == ROBUST_CHANCE_NOT_MET
        and not at80.met[0]
        and at80.rates[0] == 0.75
        and at80.n_rows_unmet == 1
        and at80.worst_row == 0
        and at80.worst_rate == 0.75
        and not at80.joint_met
        and _close(at80.rate_stderr[0], 0.21650635094610965, 1e-15)
    ):
        passed += 1
        print("  ✅ a rate of exactly 0.75 is met at 0.70 and 0.75, not met at 0.80, rate always shown")
    else:
        failed += 1
        print(
            "  ❌ chance rate wrong:",
            at70.rates[0], at70.status, at80.status, at80.n_rows_unmet, at80.rate_stderr[0],
        )

    # The rate is REPORTED under the failing status too, which is the whole point: a boolean
    # that hid 0.75 behind "not satisfied" would be indistinguishable from a rate of 0.0.
    var zero_rate = robust_chance_rates(x1, a1, 1, 1, le1, _lf(1.0, 2.0, 3.0, 4.0), 4, 0.8, 1e-9)
    if (
        zero_rate.status == ROBUST_CHANCE_NOT_MET
        and zero_rate.rates[0] == 0.0
        and zero_rate.counts[0] == 0
        and at80.status == zero_rate.status
        and at80.rates[0] != zero_rate.rates[0]
        and zero_rate.rate_stderr[0] == 0.0
    ):
        passed += 1
        print("  ✅ 'not met' at 0.75 and 'not met' at 0.00 share a status and differ in the rate")
    else:
        failed += 1
        print("  ❌ rate reporting under failure wrong:", zero_rate.rates[0], zero_rate.status)

    # ── the joint rate is not determined by the per-row rates ────────────────
    # Two rows: x <= b0 met in 3 of 4, x <= b1 met in all 4. Every row meets 0.7 and the joint
    # rate is 0.75; at 0.8 row 0 fails and so does the joint.
    var xr = _lf(10.0)
    var ar = _lf(1.0, 1.0)
    var sr = _li(SENSE_LE, SENSE_LE)
    var br = _lf(12.0, 100.0, 10.0, 100.0, 10.5, 100.0, 9.0, 100.0)
    var j70 = robust_chance_rates(xr, ar, 2, 1, sr, br, 4, 0.7, 1e-9)
    var j80 = robust_chance_rates(xr, ar, 2, 1, sr, br, 4, 0.8, 1e-9)
    if (
        j70.status == MODEL_OK
        and j70.rates[0] == 0.75
        and j70.rates[1] == 1.0
        and j70.joint_rate == 0.75
        and j70.all_rows_met
        and j70.joint_met
        and j70.worst_row == 0
        and j80.status == ROBUST_CHANCE_NOT_MET
        and not j80.met[0]
        and j80.met[1]
        and j80.n_rows_unmet == 1
        and not j80.joint_met
        and j80.joint_rate == 0.75
    ):
        passed += 1
        print("  ✅ per-row rates 0.75 / 1.00 with a joint rate of 0.75, all four reported")
    else:
        failed += 1
        print(
            "  ❌ joint rate wrong:",
            j70.rates[0], j70.rates[1], j70.joint_rate, j80.status, j80.n_rows_unmet,
        )

    # ── feasibility is per row, at the row's own magnitude ───────────────────
    # activity 1e9 against b = 1e9 - 1 is a violation of exactly 1.0 — 4.5 million ulps at
    # that magnitude — and must count as one; against b = 1e9 it holds. Rate 0.5.
    var big = robust_chance_rates(
        _lf(1.0e9), a1, 1, 1, le1, _lf(1.0e9 - 1.0, 1.0e9), 2, 0.5, 1e-9
    )
    # And a 1e7 row beside a small row must not raise the small row's budget: x = 1 against
    # 0.5 is violated in both scenarios however large the other row's right-hand side is.
    var mixed_mag = robust_chance_rates(
        _lf(1.0, 1.0), _lf(1.0, 0.0, 0.0, 1.0), 2, 2, _li(SENSE_LE, SENSE_LE),
        _lf(0.5, 1.0e7, 0.5, 1.0e7), 2, 1.0, 1e-9,
    )
    if (
        big.rates[0] == 0.5
        and big.counts[0] == 1
        and mixed_mag.rates[0] == 0.0
        and mixed_mag.rates[1] == 1.0
        and mixed_mag.status == ROBUST_CHANCE_NOT_MET
    ):
        passed += 1
        print("  ✅ a violation of 1.0 at magnitude 1e9 counts, and a 1e7 row buys no pass")
    else:
        failed += 1
        print("  ❌ per-row tolerance wrong:", big.rates[0], mixed_mag.rates[0], mixed_mag.rates[1])

    # ── an objective that varies across scenarios ────────────────────────────
    # minimise c x subject to x >= 2, with c = 1 then c = 3: optima 2 and 6, mean 4.
    var objscen = robust_scenario_solve(
        _lf(1.0), 0.0, a1, 1, 1, ge1, _lf(2.0), False, 2,
        _lf(), _lf(1.0, 3.0), 0.5, 1000, 1e-9, 1e-9,
    )
    if (
        objscen.status == ROBUST_BOUND_ONLY
        and objscen.objectives[0] == 2.0
        and objscen.objectives[1] == 6.0
        and objscen.worst_case == 6.0
        and objscen.worst_scenario == 1
        and objscen.mean_objective == 4.0
    ):
        passed += 1
        print("  ✅ objective scenarios: optima 2 and 6, worst 6 at scenario 1")
    else:
        failed += 1
        print("  ❌ objective scenarios wrong:", objscen.status, objscen.worst_case, objscen.mean_objective)

    # ── determinism: the same seed is the same scenario set, bit for bit ─────
    var d1 = scenario_rhs_normal(_lf(1.0, 2.0), _lf(1.0, 1.0), 3, 31337, "robust-test")
    var d2 = scenario_rhs_normal(_lf(1.0, 2.0), _lf(1.0, 1.0), 3, 31337, "robust-test")
    var d3 = scenario_rhs_normal(_lf(1.0, 2.0), _lf(1.0, 1.0), 3, 31338, "robust-test")
    var d4 = scenario_rhs_normal(_lf(1.0, 2.0), _lf(1.0, 1.0), 3, 31337, "other-stream")
    if (
        d1.status == MODEL_OK
        and d1.n_scenarios == 3
        and d1.n_rows == 2
        and len(d1.rhs) == 6
        and d1.rng == "philox4x64-10/v1"
        and d1.seed == 31337
        and _blocks_equal(d1.rhs, d2.rhs)
        and _blocks_differ(d1.rhs, d3.rhs)
        and _blocks_differ(d1.rhs, d4.rhs)
        and d1.stream == d2.stream
        and d1.stream != d4.stream
    ):
        passed += 1
        print("  ✅ same seed and stream reproduce the block; a different seed or stream does not")
    else:
        failed += 1
        print("  ❌ determinism broken:", d1.status, len(d1.rhs), d1.stream, d4.stream)

    # ── common random numbers: the draws are addressed, not sequential ───────
    # Drawing more scenarios, or more rows, must leave every earlier draw untouched.
    var crn2 = scenario_rhs_normal(_lf(10.0), _lf(2.0), 2, 4242, "crn")
    var crn5 = scenario_rhs_normal(_lf(10.0), _lf(2.0), 5, 4242, "crn")
    var crn_1row = scenario_rhs_normal(_lf(10.0), _lf(2.0), 2, 4242, "crn")
    var crn_2row = scenario_rhs_normal(_lf(10.0, 20.0), _lf(2.0, 3.0), 2, 4242, "crn")
    if (
        crn2.rhs[0] == crn5.rhs[0]
        and crn2.rhs[1] == crn5.rhs[1]
        and len(crn5.rhs) == 5
        and crn_1row.rhs[0] == crn_2row.rhs[0]
        and crn_1row.rhs[1] == crn_2row.rhs[2]
    ):
        passed += 1
        print("  ✅ more scenarios or more rows leave the earlier draws bit-identical")
    else:
        failed += 1
        print("  ❌ draw addressing depends on the request size:", crn2.rhs[0], crn5.rhs[0])

    # ── determinism through a driver: the rate is a function of the seed ─────
    # Two seeds, two exact rates. These numbers pin the draw coordinates themselves: if either
    # changes, the (seed, scenario, row, stream) layout moved and every stored answer drawn
    # from it now means something else.
    var seeded_a = robust_chance_normal(
        x1, a1, 1, 1, le1, _lf(10.0), _lf(2.0), 8, 1000, "chance", 0.5, 1e-9
    )
    var seeded_a2 = robust_chance_normal(
        x1, a1, 1, 1, le1, _lf(10.0), _lf(2.0), 8, 1000, "chance", 0.5, 1e-9
    )
    var seeded_b = robust_chance_normal(
        x1, a1, 1, 1, le1, _lf(10.0), _lf(2.0), 8, 1035, "chance", 0.5, 1e-9
    )
    if (
        seeded_a.status == MODEL_OK
        and seeded_a.drawn
        and seeded_a.seed == 1000
        and seeded_a.rates[0] == 0.75
        and seeded_a2.rates[0] == seeded_a.rates[0]
        and seeded_a2.counts[0] == seeded_a.counts[0]
        and seeded_b.rates[0] == 0.25
        and seeded_b.status == ROBUST_CHANCE_NOT_MET
        and seeded_b.rates[0] != seeded_a.rates[0]
        and not at70.drawn
        and at70.seed == 0
    ):
        passed += 1
        print("  ✅ seed 1000 gives rate 0.75 and seed 1035 gives 0.25, reproducibly")
    else:
        failed += 1
        print(
            "  ❌ seeded rate not reproducible:",
            seeded_a.rates[0], seeded_a2.rates[0], seeded_b.rates[0], seeded_a.seed,
        )

    # ── a zero-width uniform draw is the base right-hand side, exactly ───────
    # base + (2u - 1) * 0 is base for every u, so four drawn scenarios are four copies of one
    # program and the robust answer must again be the deterministic one. Generator and solver
    # composed end to end, with == throughout.
    var flat = scenario_rhs_uniform(b3, _lf(0.0, 0.0, 0.0), 4, 99, "flat")
    var flat_ok = flat.status == MODEL_OK and len(flat.rhs) == 12
    for i in range(len(flat.rhs)):
        if flat.rhs[i] != b3[i % 3]:
            flat_ok = False
    var flat_hn = robust_min_max_rhs_default(c3, a3, 3, 2, s3, b3, True, 4, flat.rhs)
    if (
        flat_ok
        and flat_hn.status == MODEL_OK
        and flat_hn.objective == det.objective
        and flat_hn.x[0] == det.x[0]
        and flat_hn.x[1] == det.x[1]
        and flat_hn.n_verified_scenarios == 4
        and flat_hn.worst_violation == 0.0
    ):
        passed += 1
        print("  ✅ a zero-dispersion draw reproduces the base exactly and the deterministic answer")
    else:
        failed += 1
        print("  ❌ zero-dispersion path wrong:", flat.status, flat_hn.status, flat_hn.objective)

    # ── zero rows: every scenario satisfies all of them, vacuously ───────────
    var norows = robust_chance_rates(_lf(1.0), _lf(), 0, 1, _li(), _lf(), 3, 0.9, 1e-9)
    if (
        norows.status == MODEL_OK
        and norows.has_rates
        and norows.n_rows == 0
        and len(norows.rates) == 0
        and norows.worst_row == -1
        and norows.joint_rate == 1.0
        and norows.joint_met
    ):
        passed += 1
        print("  ✅ an unconstrained point satisfies every constraint it has, rates empty")
    else:
        failed += 1
        print("  ❌ zero-row handling wrong:", norows.status, norows.joint_rate, norows.worst_row)

    # ── ties are broken by the lowest index, deterministically ───────────────
    var tie = robust_scenario_solve_default(c1, a1, 1, 1, ge1, b1, False, 3, _lf(4.0, 4.0, 4.0), 0.5)
    if (
        tie.status == ROBUST_BOUND_ONLY
        and tie.worst_case == 8.0
        and tie.worst_scenario == 0
        and tie.best_scenario == 0
        and tie.cvar == 8.0
    ):
        passed += 1
        print("  ✅ equal scenarios report scenario 0 as binding, not the last one scanned")
    else:
        failed += 1
        print("  ❌ tie-break wrong:", tie.worst_scenario, tie.best_scenario, tie.worst_case)

    # ── the generated A-Z sample arguments must be REJECTED, not indexed ─────
    # `tests/generate_mojo_tests.py` calls every contract function with a 5-element list for
    # every List[Float64] and 5 for every Int, so `rows = cols = 5` against a 5-cell matrix is
    # the call the whole suite makes. Reading a[24] there is an uncatchable process crash.
    var lf5 = _lf(0.5, 0.6, 0.7, 0.4, 0.3)
    var li5 = _li(1, 2, 3, 4, 5)
    var az1 = robust_scenario_solve(lf5, 0.5, lf5, 5, 5, li5, lf5, True, 5, lf5, lf5, 0.5, 5, 0.5, 0.5)
    var az2 = robust_scenario_solve_default(lf5, lf5, 5, 5, li5, lf5, True, 5, lf5, 0.5)
    var az3 = robust_min_max_rhs(lf5, 0.5, lf5, 5, 5, li5, lf5, True, 5, lf5, 5, 0.5, 0.5)
    var az4 = robust_min_max_rhs_default(lf5, lf5, 5, 5, li5, lf5, True, 5, lf5)
    var az5 = robust_chance_rates(lf5, lf5, 5, 5, li5, lf5, 5, 0.5, 0.5)
    var az6 = robust_chance_normal(lf5, lf5, 5, 5, li5, lf5, lf5, 5, 42, "test", 0.5, 0.5)
    var az7 = scenario_rhs_normal(lf5, lf5, 5, 42, "test")
    if (
        az1.status == MODEL_ERR_DENSE_SHAPE
        and az2.status == MODEL_ERR_DENSE_SHAPE
        and az3.status == MODEL_ERR_DENSE_SHAPE
        and az4.status == MODEL_ERR_DENSE_SHAPE
        and az5.status == MODEL_ERR_DENSE_SHAPE
        and az6.status == MODEL_ERR_DENSE_SHAPE
        and _no_numbers(az1)
        and len(az3.x) == 0
        and not az5.has_rates
        and az7.status == MODEL_OK
        and len(az7.rhs) == 25
    ):
        passed += 1
        print("  ✅ the A-Z sample arguments are rejected on shape by every driver, no crash")
    else:
        failed += 1
        print(
            "  ❌ A-Z sample args not rejected:",
            az1.status, az3.status, az5.status, az7.status,
        )

    # ── a scenario count is bounded twice, and the product with a DIVISION ───
    # 6148914691236517206 * 3 == 2 as a wrapping multiply, and 2^30 scenarios of 3 rows is
    # 25 GB. Both are structurally consistent requests, so only a declared ceiling stops them.
    var wrap = robust_scenario_solve_default(
        _lf(1.0), _lf(1.0), 1, 1, ge1, _lf(0.0), False, 6148914691236517206, _lf(), 0.5
    )
    var bomb = scenario_rhs_normal(_lf(1.0, 2.0, 3.0), _lf(1.0, 1.0, 1.0), 1 << 30, 1, "bomb")
    var short_block = robust_scenario_solve_default(
        _lf(1.0), _lf(1.0), 1, 1, ge1, _lf(0.0), False, 3, _lf(1.0, 2.0), 0.5
    )
    var zero_s = scenario_rhs_normal(_lf(1.0), _lf(1.0), 0, 1, "zero")
    # rows = 2^26 with an empty payload: the row count is tied to len(senses), so this is a
    # length mismatch rather than an allocation.
    var no_payload = robust_chance_rates(_lf(), _lf(), 1 << 26, 0, _li(), _lf(), 2, 0.5, 1e-9)
    if (
        wrap.status == ROBUST_ERR_SCENARIO_SHAPE
        and bomb.status == ROBUST_ERR_SCENARIO_SHAPE
        and len(bomb.rhs) == 0
        and short_block.status == ROBUST_ERR_SCENARIO_SHAPE
        and zero_s.status == ROBUST_ERR_SCENARIO_SHAPE
        and no_payload.status == MODEL_ERR_LENGTH_MISMATCH
        and robust_status_name(wrap.status) == "scenario_shape_rejected"
    ):
        passed += 1
        print("  ✅ a wrapping count, a 25 GB request, a short block and S = 0 are all rejected")
    else:
        failed += 1
        print(
            "  ❌ scenario bounding wrong:",
            wrap.status, bomb.status, short_block.status, zero_s.status, no_payload.status,
        )

    # ── every other input rejection has its own status ───────────────────────
    var inf_v = 1.0e308 * 10.0
    var nan_v = inf_v - inf_v
    var nan_cell = robust_chance_rates(x1, a1, 1, 1, le1, _lf(nan_v, 1.0), 2, 0.5, 1e-9)
    var inf_cell = robust_scenario_solve_default(_lf(1.0), a1, 1, 1, ge1, _lf(0.0), False, 2, _lf(inf_v, 1.0), 0.5)
    var neg_sigma = scenario_rhs_normal(_lf(1.0), _lf(-1.0), 2, 1, "neg")
    var nan_sigma = scenario_rhs_normal(_lf(1.0), _lf(nan_v), 2, 1, "nan")
    var bad_base = scenario_rhs_normal(_lf(inf_v), _lf(1.0), 2, 1, "inf")
    var sigma_len = scenario_rhs_normal(_lf(1.0), _lf(1.0, 2.0), 2, 1, "len")
    var level_lo = robust_scenario_solve_default(_lf(1.0), a1, 1, 1, ge1, _lf(0.0), False, 1, _lf(), 0.0)
    var level_hi = robust_chance_rates(x1, a1, 1, 1, le1, _lf(1.0), 1, 1.5, 1e-9)
    var level_nan = robust_chance_rates(x1, a1, 1, 1, le1, _lf(1.0), 1, nan_v, 1e-9)
    var short_x = robust_chance_rates(_lf(1.0, 2.0), a1, 1, 1, le1, _lf(1.0), 1, 0.5, 1e-9)
    var rows_mm = robust_chance_normal(
        x1, a1, 1, 1, le1, _lf(1.0, 2.0), _lf(1.0, 1.0), 2, 7, "mm", 0.5, 1e-9
    )
    if (
        nan_cell.status == MODEL_ERR_NON_FINITE_RHS
        and not nan_cell.has_rates
        and inf_cell.status == MODEL_ERR_NON_FINITE_RHS
        and neg_sigma.status == ROBUST_ERR_DISPERSION
        and nan_sigma.status == ROBUST_ERR_DISPERSION
        and bad_base.status == MODEL_ERR_NON_FINITE_RHS
        and sigma_len.status == MODEL_ERR_LENGTH_MISMATCH
        and level_lo.status == ROBUST_ERR_CONFIDENCE
        and level_hi.status == ROBUST_ERR_CONFIDENCE
        and level_nan.status == ROBUST_ERR_CONFIDENCE
        and short_x.status == MODEL_ERR_POINT_LENGTH
        and rows_mm.status == MODEL_ERR_LENGTH_MISMATCH
    ):
        passed += 1
        print("  ✅ nan cells, bad dispersions, out-of-range levels and length mismatches all differ")
    else:
        failed += 1
        print(
            "  ❌ rejection statuses wrong:",
            nan_cell.status, neg_sigma.status, level_lo.status, short_x.status, rows_mm.status,
        )

    # ── an infinite activity is never read as satisfied ──────────────────────
    # 1e308 * 1e308 twice over overflows, and a non-finite activity makes every `> tol`
    # comparison False — the shape in which an audit passes having counted zero violations.
    var inf_act = robust_chance_rates(
        _lf(1.0e308, 1.0e308), _lf(1.0e308, 1.0e308), 1, 2, le1, _lf(1.0), 1, 0.5, 1e-9
    )
    if inf_act.status != MODEL_OK and not inf_act.has_rates and len(inf_act.rates) == 0:
        passed += 1
        print("  ✅ an overflowing activity is a status, not a satisfied constraint")
    else:
        failed += 1
        print("  ❌ non-finite activity accepted:", inf_act.status, inf_act.has_rates)

    # ── negative objectives keep the risk measures the right way round ───────
    # minimise -x subject to x <= b, so the optimum is -b: scenarios b = 2, 5, 3 give -2, -5,
    # -3. The WORST of those is -2 (scenario 0), the best is -5, the mean is -10/3, and CVaR at
    # 0.5 is the average of the worst two, (-2 + -3) / 2 = -2.5. A sign convention applied in
    # the wrong place turns every one of these into its opposite.
    var neg = robust_scenario_solve_default(
        _lf(-1.0), a1, 1, 1, le1, _lf(0.0), False, 3, _lf(2.0, 5.0, 3.0), 0.5
    )
    if (
        neg.status == ROBUST_BOUND_ONLY
        and neg.objectives[0] == -2.0
        and neg.objectives[1] == -5.0
        and neg.objectives[2] == -3.0
        and neg.worst_case == -2.0
        and neg.worst_scenario == 0
        and neg.best_case == -5.0
        and neg.best_scenario == 1
        and _close(neg.mean_objective, -10.0 / 3.0, 1e-12)
        and _close(neg.cvar, -2.5, 1e-12)
        and neg.bound_direction == -1
    ):
        passed += 1
        print("  ✅ negative optima: worst -2, best -5, CVaR -2.5 — signs survive the round trip")
    else:
        failed += 1
        print(
            "  ❌ negative-objective handling wrong:",
            neg.worst_case, neg.best_case, neg.cvar, neg.mean_objective,
        )

    # ── the two generators do not hand out the same draw twice ───────────────
    # Box-Muller consumes a fixed two draws per coordinate, so the uniform generator addresses
    # the third. Sharing index 0 would make a model whose rows came from both generators
    # perfectly rank-correlated with nothing failing anywhere.
    var u_cmp = scenario_rhs_uniform(_lf(0.0), _lf(1.0), 3, 5150, "cmp")
    var n_cmp = scenario_rhs_normal(_lf(0.0), _lf(1.0), 3, 5150, "cmp")
    if (
        u_cmp.status == MODEL_OK
        and n_cmp.status == MODEL_OK
        and u_cmp.stream == n_cmp.stream
        and u_cmp.seed == n_cmp.seed
        and _blocks_differ(u_cmp.rhs, n_cmp.rhs)
        and u_cmp.rhs[0] != n_cmp.rhs[0]
        and u_cmp.rhs[1] != n_cmp.rhs[1]
        and u_cmp.rhs[2] != n_cmp.rhs[2]
    ):
        passed += 1
        print("  ✅ uniform and normal at the same coordinates draw independent values")
    else:
        failed += 1
        print("  ❌ generators share a draw index:", u_cmp.rhs[0], n_cmp.rhs[0])

    # ── degenerate shapes still answer, and answer correctly ─────────────────
    # Zero rows: minimise x with x >= 0 and nothing else, so the optimum is 0 — a real answer,
    # not an absent one. Zero variables: the objective is the constant, and the rows are
    # judged at activity 0. An objective constant must survive to the reported optimum:
    # 2 * 5 + 100 = 110 for the tightest of b = 3, 5 on a >= row.
    var no_rows = robust_min_max_rhs_default(_lf(1.0), _lf(), 0, 1, _li(), _lf(), False, 3, _lf())
    var no_cols = robust_min_max_rhs_default(_lf(), _lf(), 1, 0, le1, _lf(1.0), False, 2, _lf(1.0, 2.0))
    var withconst = robust_min_max_rhs(
        c1, 100.0, a1, 1, 1, ge1, _lf(0.0), False, 2, _lf(3.0, 5.0), 1000, 1e-9, 1e-9
    )
    if (
        no_rows.status == MODEL_OK
        and no_rows.has_objective
        and no_rows.objective == 0.0
        and no_rows.x[0] == 0.0
        # No block was supplied, so there is ONE distinct scenario, not three.
        and not no_rows.scenario_data_given
        and no_rows.n_distinct_scenarios == 1
        and no_rows.n_verified_scenarios == 1
        and no_cols.status == MODEL_OK
        and no_cols.objective == 0.0
        and no_cols.effective_rhs[0] == 1.0
        and withconst.status == MODEL_OK
        and withconst.objective == 110.0
        and withconst.effective_rhs[0] == 5.0
        and withconst.binding_scenario[0] == 1
    ):
        passed += 1
        print("  ✅ zero rows, zero variables and an objective constant all come back correct")
    else:
        failed += 1
        print(
            "  ❌ degenerate shape wrong:",
            no_rows.status, no_rows.objective, no_cols.status, withconst.objective,
        )

    # ── REGRESSION: the min-max bound's DIRECTION against the true support ───
    # The module docstring stated one direction unconditionally — "a LOWER bound on the objective
    # over the true support" — but the driver takes `maximize`, and shrinking a feasible region
    # RAISES a minimum while it LOWERS a maximum. So the written direction was inverted for every
    # maximisation, under MODEL_OK with `optimal_for_scenario_set = True`, and nothing in the
    # result let a caller detect it. Reproduction verbatim, plus the scenario nobody drew that
    # measures which side the sampled answer errs on.
    #
    #   maximise x s.t. x <= b, scenarios b = 3, 5      -> 3  ; add b = 1 -> 1  <= 3  UPPER
    #   minimise 2x s.t. x >= b, scenarios b = 3, 5     -> 10 ; add b = 9 -> 18 >= 10 LOWER
    var up2 = robust_min_max_rhs_default(_lf(1.0), a1, 1, 1, le1, _lf(0.0), True, 2, _lf(3.0, 5.0))
    var up3 = robust_min_max_rhs_default(
        _lf(1.0), a1, 1, 1, le1, _lf(0.0), True, 3, _lf(3.0, 5.0, 1.0)
    )
    var dn2 = robust_min_max_rhs_default(c1, a1, 1, 1, ge1, _lf(0.0), False, 2, _lf(3.0, 5.0))
    var dn3 = robust_min_max_rhs_default(
        c1, a1, 1, 1, ge1, _lf(0.0), False, 3, _lf(3.0, 5.0, 9.0)
    )
    if (
        up2.status == MODEL_OK
        and up2.objective == 3.0
        and up2.optimal_for_scenario_set
        and up3.objective == 1.0
        # The claim is in the RESULT, not only in a docstring: +1 = upper bound when maximising.
        and up2.bound_direction == 1
        and _bound_direction_agrees(up2.objective, up3.objective, up2.bound_direction)
        # ...and the direction the docstring used to claim is measurably FALSE here, which is
        # what makes this an assertion about the direction rather than about the numbers.
        and not _bound_direction_agrees(up2.objective, up3.objective, -1)
        and dn2.objective == 10.0
        and dn3.objective == 18.0
        and dn2.bound_direction == -1
        and _bound_direction_agrees(dn2.objective, dn3.objective, dn2.bound_direction)
        and not _bound_direction_agrees(dn2.objective, dn3.objective, 1)
        # Both drivers take the direction from one helper, so they cannot disagree.
        and maxi.bound_direction == up2.bound_direction
        and two.bound_direction == dn2.bound_direction
    ):
        passed += 1
        print("  ✅ the true-support bound is UPPER when maximising and LOWER when minimising")
    else:
        failed += 1
        print(
            "  ❌ bound direction wrong:",
            up2.objective, up3.objective, up2.bound_direction,
            dn2.objective, dn3.objective, dn2.bound_direction,
        )

    # ── REGRESSION: `cvar_level` is a CONFIDENCE, not a tail fraction ────────
    # The only statement of the orientation anywhere in the module was inverted ("1.0 ... means
    # 'every scenario'"), and a caller following it passed 0.05 for the 5% tail and got 50 where
    # the answer is 100 — a 2x understatement of tail risk under a success status. Reproduction
    # verbatim: minimise 2x s.t. x >= b over b = 5, 10, 15, 50, so the optima are 10, 20, 30, 100
    # and the mean is 40. Every number below is exact in binary.
    var risk4 = _lf(5.0, 10.0, 15.0, 50.0)
    var cv05 = robust_scenario_solve_default(c1, a1, 1, 1, ge1, b1, False, 4, risk4, 0.05)
    var cv25 = robust_scenario_solve_default(c1, a1, 1, 1, ge1, b1, False, 4, risk4, 0.25)
    var cv50 = robust_scenario_solve_default(c1, a1, 1, 1, ge1, b1, False, 4, risk4, 0.5)
    var cv75 = robust_scenario_solve_default(c1, a1, 1, 1, ge1, b1, False, 4, risk4, 0.75)
    var cv95 = robust_scenario_solve_default(c1, a1, 1, 1, ge1, b1, False, 4, risk4, 0.95)
    var cv100 = robust_scenario_solve_default(c1, a1, 1, 1, ge1, b1, False, 4, risk4, 1.0)
    if (
        cv05.cvar == 50.0
        and cv25.cvar == 50.0
        and cv50.cvar == 65.0
        and cv75.cvar == 100.0
        and cv95.cvar == 100.0
        and cv100.cvar == 100.0
        # 1.0 is the single WORST scenario, NOT "every scenario" — the inverted claim's crux.
        and cv100.cvar == cv100.worst_case
        and cv05.mean_objective == 40.0
        # Monotone non-decreasing in the level, which a tail-fraction reading reverses.
        and cv05.cvar <= cv25.cvar
        and cv25.cvar <= cv50.cvar
        and cv50.cvar <= cv75.cvar
        and cv75.cvar <= cv100.cvar
        # The convention travels WITH the number: 0.05 confidence is the 95% tail.
        and _close(cv05.cvar_tail_fraction, 0.95, 1e-15)
        and cv50.cvar_tail_fraction == 0.5
        and cv25.cvar_tail_fraction == 0.75
        and cv100.cvar_tail_fraction == 0.0
        # The orientation the module claims is CHECKED, so the two reports agree: a
        # confidence-level CVaR of the costs sits between the mean and the worst case.
        and cv05.has_cvar
        and cv05.cvar >= cv05.mean_objective
        and cv05.cvar <= cv05.worst_case
        and cv50.cvar >= cv50.mean_objective
        and cv50.cvar <= cv50.worst_case
        and cv100.cvar >= cv100.mean_objective
    ):
        passed += 1
        print("  ✅ cvar_level is a confidence: 0.05 -> 50, 1.0 -> the worst case, tail reported")
    else:
        failed += 1
        print(
            "  ❌ cvar orientation wrong:",
            cv05.cvar, cv25.cvar, cv50.cvar, cv75.cvar, cv100.cvar,
            cv05.cvar_tail_fraction,
        )

    # ── REGRESSION: the chance driver measures `x >= 0` too ──────────────────
    # `robust_chance_rates` measured only the rows, so a point OUTSIDE the non-negative orthant —
    # which `lp_solve` optimises over and which both sibling drivers verify through the same
    # `_negativity` — came back MODEL_OK with a 100% satisfaction rate. One declared invariant
    # enforced at two strengths in one package. Reproduction verbatim.
    var negx = robust_chance_rates(
        _lf(-5.0), a1, 1, 1, le1, _lf(10.0, 10.0, 10.0, 10.0), 4, 0.95, 1e-9
    )
    # The same rows at an ADMISSIBLE point, so the difference is the non-negativity alone.
    var posx = robust_chance_rates(
        _lf(5.0), a1, 1, 1, le1, _lf(10.0, 10.0, 10.0, 10.0), 4, 0.95, 1e-9
    )
    # Zero rows cannot skip it either: the vacuous joint rate of 1.0 is only honest for a point
    # that is actually in the feasible set.
    var negx_norows = robust_chance_rates(_lf(-1.0), _lf(), 0, 1, _li(), _lf(), 3, 0.9, 1e-9)
    if (
        negx.status == ROBUST_CHANCE_NOT_MET
        and negx.has_rates
        # The measured per-row rate is still reported in full — it is a fact about the row.
        and negx.rates[0] == 1.0
        and negx.counts[0] == 4
        and negx.all_rows_met
        # ...and the point is NOT feasible in any scenario, which is what the joint rate means.
        and not negx.nonnegative
        and negx.worst_negative == 5.0
        and negx.joint_rate == 0.0
        and not negx.joint_met
        and posx.status == MODEL_OK
        and posx.nonnegative
        and posx.worst_negative == 0.0
        and posx.joint_rate == 1.0
        and posx.joint_met
        and posx.rates[0] == negx.rates[0]
        and negx_norows.status == ROBUST_CHANCE_NOT_MET
        and not negx_norows.nonnegative
        and negx_norows.joint_rate == 0.0
        and not negx_norows.joint_met
        # The admissible zero-row point from earlier is unchanged.
        and norows.joint_rate == 1.0
        and norows.nonnegative
    ):
        passed += 1
        print("  ✅ a negative x is infeasible in every scenario: rate 1.00, joint 0.00, not met")
    else:
        failed += 1
        print(
            "  ❌ chance coverage gap:",
            negx.status, negx.rates[0], negx.nonnegative, negx.worst_negative,
            negx.joint_rate, negx_norows.joint_rate,
        )

    # ── REGRESSION: an empty block is ONE scenario, not S of them ────────────
    # With no scenario data the driver re-checked the base right-hand side `n_scenarios` times and
    # reported the count as evidence: `n_verified_scenarios = 1000`, `feasible_rate = 1.0` for a
    # caller who supplied zero scenarios — and 1000 verification passes of one row. Reproduction
    # verbatim (minimise 2x s.t. x >= 4, so the optimum is 8).
    var noblock = robust_min_max_rhs_default(c1, a1, 1, 1, ge1, _lf(4.0), False, 1000, _lf())
    if (
        noblock.status == MODEL_OK
        and noblock.objective == 8.0
        and noblock.n_scenarios == 1000
        and not noblock.scenario_data_given
        and noblock.n_distinct_scenarios == 1
        and noblock.n_verified_scenarios == 1
        and noblock.n_violating_scenarios == 0
        and noblock.feasible_rate == 1.0
        and noblock.binding_scenario[0] == -1
        and noblock.optimal_for_scenario_set
        and _mm_self_consistent(noblock)
    ):
        passed += 1
        print("  ✅ 1000 scenarios with no scenario data verify ONE distinct right-hand side")
    else:
        failed += 1
        print(
            "  ❌ empty-block evidence wrong:",
            noblock.n_verified_scenarios, noblock.n_distinct_scenarios,
            noblock.scenario_data_given, noblock.feasible_rate,
        )

    # ── REGRESSION: an input rejection is not an LP status ───────────────────
    # `_no_min_max_result` copied the robust rejection code into `lp_status`, so a request refused
    # before any solve reported `lp_status = 150` — a number `lp_status_name` does not name and
    # which means something else in the chain that field belongs to. Reproduction verbatim.
    var neg_s = robust_min_max_rhs_default(c1, a1, 1, 1, ge1, _lf(4.0), False, -5, _lf())
    if (
        neg_s.status == ROBUST_ERR_SCENARIO_SHAPE
        and neg_s.lp_status == MODEL_OK
        and neg_s.lp_status != neg_s.status
        and neg_s.iterations == 0
        and _mm_absent(neg_s)
        # The sibling already did this right for its per-scenario field; both now agree.
        and level_lo.first_failed_status == MODEL_OK
        and level_lo.first_failed_scenario == -1
    ):
        passed += 1
        print("  ✅ a pre-solve rejection leaves lp_status at MODEL_OK, not the robust code")
    else:
        failed += 1
        print("  ❌ lp_status leaked a robust code:", neg_s.status, neg_s.lp_status)

    # ── REGRESSION: bounding memory is not bounding WORK ─────────────────────
    # `ROBUST_MAX_SCENARIOS` was justified purely as an ALLOCATION bound, and nothing bounded the
    # S full two-phase simplex solves. Measured: S = 200000 on a 1x1 model took 699 ms, so the
    # allocation-legal ceiling below was ~29 s of single-threaded worker time from a ~120-byte
    # payload — which presents to every other client as the same hang an allocation bomb does.
    # Every one of these requests is INSIDE every allocation ceiling.
    var ceiling = ROBUST_MAX_SCENARIOS
    var solve_work = robust_scenario_solve_default(c1, a1, 1, 1, ge1, b1, False, ceiling, _lf(), 0.5)
    var draw_work = scenario_rhs_normal(_lf(1.0), _lf(1.0), ceiling, 1, "work")
    var chance_work = robust_chance_rates(x1, a1, 1, 1, le1, _lf(), ceiling, 0.5, 1e-9)
    var normal_work = robust_chance_normal(
        x1, a1, 1, 1, le1, _lf(10.0), _lf(2.0), ceiling, 1, "work", 0.5, 1e-9
    )
    # An ordinary sweep is NOT refused — the budget is a ceiling, not a discouragement.
    var solve_fine = robust_scenario_solve_default(c1, a1, 1, 1, ge1, b1, False, 1000, _lf(), 0.5)
    # ...and the empty-block collapse means the same ceiling costs one solve here, so the fix to
    # the evidence count is also the fix to its cost.
    var minmax_fine = robust_min_max_rhs_default(c1, a1, 1, 1, ge1, _lf(4.0), False, ceiling, _lf())
    if (
        solve_work.status == ROBUST_ERR_WORK_BUDGET
        and _no_numbers(solve_work)
        and len(solve_work.scenario_status) == 0
        and draw_work.status == ROBUST_ERR_WORK_BUDGET
        and len(draw_work.rhs) == 0
        and chance_work.status == ROBUST_ERR_WORK_BUDGET
        and not chance_work.has_rates
        and normal_work.status == ROBUST_ERR_WORK_BUDGET
        and not normal_work.has_rates
        and solve_fine.status == ROBUST_BOUND_ONLY
        and solve_fine.n_solved == 1000
        and minmax_fine.status == MODEL_OK
        and minmax_fine.objective == 8.0
        and minmax_fine.n_distinct_scenarios == 1
        and robust_status_name(ROBUST_ERR_WORK_BUDGET) == "scenario_sweep_exceeds_work_budget"
    ):
        passed += 1
        print("  ✅ an allocation-legal S that would take ~29 s of CPU is refused, 1000 is not")
    else:
        failed += 1
        print(
            "  ❌ work budget missing:",
            solve_work.status, draw_work.status, chance_work.status,
            normal_work.status, solve_fine.status, minmax_fine.status,
        )

    # ── every returned min-max result agrees with itself ─────────────────────
    # `positive_definite = True` beside an unbounded solve, and `rank = 1` beside
    # `positive_definite = True`, are why this is asserted as a property: two mutually exclusive
    # claims in one value mean a caller can use neither.
    if (
        _mm_self_consistent(hn)
        and hn.bound_direction == 1
        and _mm_self_consistent(r_gap)
        and r_gap.bound_direction == -1
        and _mm_self_consistent(mixed)
        and _mm_self_consistent(eq_ok)
        and _mm_self_consistent(no_cols)
        and _mm_self_consistent(withconst)
        and _mm_self_consistent(flat_hn)
        and _mm_absent(r_inf)
        and _mm_absent(unb)
        and _mm_absent(eq_bad)
        and _mm_absent(az3)
        and _mm_absent(az4)
    ):
        passed += 1
        print("  ✅ every min-max result's certificate, direction and counts agree with each other")
    else:
        failed += 1
        print(
            "  ❌ min-max result contradicts itself:",
            hn.bound_direction, r_gap.bound_direction, r_inf.bound_direction,
            unb.bound_direction,
        )

    # ── the status vocabulary is one integer per meaning ─────────────────────
    # Tier 1 allocated 80-84 twice inside one package, so one integer named two outcomes. All
    # ten codes here must have distinct names, and the fall-through must still reach the
    # shared chain rather than shadowing it.
    var names = List[String]()
    names.append(robust_status_name(ROBUST_ERR_SCENARIO_SHAPE))
    names.append(robust_status_name(ROBUST_ERR_CONFIDENCE))
    names.append(robust_status_name(ROBUST_ERR_DISPERSION))
    names.append(robust_status_name(ROBUST_SCENARIO_FAILED))
    names.append(robust_status_name(ROBUST_BOUND_ONLY))
    names.append(robust_status_name(ROBUST_INFEASIBLE))
    names.append(robust_status_name(ROBUST_UNBOUNDED))
    names.append(robust_status_name(ROBUST_EQ_CONFLICT))
    names.append(robust_status_name(ROBUST_CHANCE_NOT_MET))
    names.append(robust_status_name(ROBUST_UNVERIFIED))
    names.append(robust_status_name(ROBUST_ERR_WORK_BUDGET))
    var distinct = True
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if names[i] == names[j]:
                distinct = False
    var in_range = (
        ROBUST_ERR_SCENARIO_SHAPE == 150
        and ROBUST_ERR_CONFIDENCE == 151
        and ROBUST_ERR_DISPERSION == 152
        and ROBUST_SCENARIO_FAILED == 153
        and ROBUST_BOUND_ONLY == 154
        and ROBUST_INFEASIBLE == 155
        and ROBUST_UNBOUNDED == 156
        and ROBUST_EQ_CONFLICT == 157
        and ROBUST_CHANCE_NOT_MET == 158
        and ROBUST_UNVERIFIED == 159
        # The eleventh code deliberately SKIPS 160-169: that is the block a sibling extending
        # upward from 149 takes first, and those files were being edited in parallel.
        and ROBUST_ERR_WORK_BUDGET == 170
    )
    if (
        distinct
        and in_range
        and len(names) == 11
        and robust_status_name(LP_OPTIMAL) == "optimal"
        and robust_status_name(LP_INFEASIBLE) == "infeasible"
        and robust_status_name(MODEL_ERR_DENSE_SHAPE) != "scenario_shape_rejected"
    ):
        passed += 1
        print("  ✅ 150-159 plus 170 are eleven distinct names; the shared chain shows through")
    else:
        failed += 1
        print("  ❌ status vocabulary collides:", distinct, in_range, len(names))

    print("  [optimization.robust] Passed:", passed, "Failed:", failed)
