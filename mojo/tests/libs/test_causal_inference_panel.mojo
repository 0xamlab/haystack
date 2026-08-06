"""test_causal_inference_panel.mojo — known-value tests for DiD and synthetic control.

Hand-written. Two families, both with answers arrived at on paper.

DIFFERENCE-IN-DIFFERENCES
------------------------
The 2x2 case is checked against the FROZEN `causal.diff_in_diff` for exact equality — a panel with
one pre-period and one post-period reduces to it, so the two must agree bit for bit. What this
module adds is what the frozen signature cannot carry:

  * with a SINGLE pre-period there is no trend to compute, so `has_pre_trend` is False and
    `pre_trend_diff` is not to be read. Absent, per rule 4, rather than reported as 0.0 — which
    would be indistinguishable from "the trends were perfectly parallel", the single most
    misleading thing this struct could say;
  * with three pre-periods the gap series is `[1, 2, 4]`, whose OLS slope is exactly 1.5 and whose
    largest one-period jump is exactly 2.0. Both are asserted against hand arithmetic
    (slope = sum((t - 1)(g - 7/3)) / sum((t - 1)^2) = 3/2), so the reported trend is a real
    regression and not a first difference in disguise.

There is deliberately no assertion that the design is valid, because there is no field that claims
it. Parallel trends is an assumption; the report hands over the evidence and stops.

SYNTHETIC CONTROL
-----------------
The pre-period problem is a quadratic on the simplex, so the answer is a closed form and the
weights are checkable by hand. Panel: the treated unit's pre-period path is `[1, 2, 3]`, donor A
is `[0, 0, 0]` and donor B is `[2, 4, 6]`. On the simplex `w_A + w_B = 1`, so the objective is
`||[1,2,3] - w_B [2,4,6]||^2` and its minimiser is

    w_B = ([1,2,3] . [2,4,6]) / ||[2,4,6]||^2 = 28 / 56 = 0.5

exactly, with a pre-period residual of exactly zero. The post-period donor values are 0 and 8, so
the synthetic value is 4 and the effect on a treated post value of 10 is exactly 6. Every one of
those five numbers is asserted.

A second panel gives a non-degenerate fit whose exact minimiser is also computable, and an
iteration cap of 1 is asserted to come back `CI_ERR_NOT_CONVERGED` with the weights and the effect
ABSENT and the measured Frank-Wolfe gap present — an unconverged iterate is an arbitrary convex
combination of donors, not a synthetic control.
"""
from std.math import abs as fabs, sqrt

from causal import diff_in_diff as frozen_did

from causal_inference.base import (
    CI_ABSENT,
    CI_ERR_INSUFFICIENT_DATA,
    CI_ERR_INVALID_PARAMETER,
    CI_ERR_LENGTH_MISMATCH,
    CI_ERR_NON_FINITE,
    CI_ERR_NOT_CONVERGED,
    CI_ERR_NO_CONTROL,
    CI_ERR_NO_TREATED,
    CI_ERR_SHAPE,
    CI_ERR_TREATMENT_NOT_BINARY,
    CI_OK,
    MAX_CI_ITERATIONS,
    ci_tolerance,
)
from causal_inference.panel import did_panel, synthetic_control


def _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _ints(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _close(a: Float64, b: Float64) -> Bool:
    return fabs(a - b) <= ci_tolerance(fabs(a) + fabs(b), 0.0)


def _unit_system(c: Float64) -> List[Float64]:
    """ONE synthetic-control problem, expressed in a unit `c` times larger.

    4 units x 6 periods, row-major, treated unit first, `first_treated_period = 4`. Multiplying
    every outcome by a constant is a change of UNITS and nothing else: the optimal simplex
    weights, the number of Frank-Wolfe steps needed and the convergence verdict are all
    invariant, while the objective and its duality gap scale as `c^2`.
    """
    var base = _floats(
        10.0, 11.0, 12.5, 13.0, 14.0, 15.0,
        9.0, 10.5, 11.0, 12.0, 13.0, 13.5,
        12.0, 12.5, 14.0, 14.5, 15.0, 16.0,
        8.0, 9.0, 9.5, 11.0, 11.5, 12.0,
    )
    var out = List[Float64](capacity=len(base))
    for i in range(len(base)):
        out.append(base[i] * c)
    return out^


def _lf5() -> List[Float64]:
    return _floats(0.5, 0.6, 0.7, 0.4, 0.3)


def _li5() -> List[Int]:
    return _ints(1, 2, 3, 4, 5)


def main() raises:
    var passed = 0
    var failed = 0

    # ── the 2x2 case IS the frozen kernel ────────────────────────────────────
    # Unit 0 treated: 10 -> 15.  Unit 1 control: 8 -> 9.  ATT = 5 - 1 = 4.
    var y22 = _floats(10.0, 15.0, 8.0, 9.0)
    var d22 = did_panel(y22, 2, 2, _ints(1, 0), 1)
    var oracle = frozen_did(_floats(10.0), _floats(15.0), _floats(8.0), _floats(9.0))
    if (
        d22.status == CI_OK
        and d22.has_att
        and d22.att == 4.0
        and d22.att == oracle
        and d22.n_pre == 1
        and d22.n_post == 1
        and d22.n_treated == 1
        and d22.n_control == 1
        and d22.mean_pre_treated == 10.0
        and d22.mean_post_treated == 15.0
        and d22.mean_pre_control == 8.0
        and d22.mean_post_control == 9.0
    ):
        passed += 1
        print("  ✅ 2x2 panel: ATT is exactly 4.0 and equals frozen causal.diff_in_diff")
    else:
        failed += 1
        print("  ❌ 2x2 case wrong:", d22.att, oracle)

    # ── one pre-period: the trend is ABSENT, not zero ─────────────────────────
    if (
        not d22.has_pre_trend
        and d22.max_abs_pre_gap_change == CI_ABSENT
        and d22.pre_trend_r_squared == CI_ABSENT
        and d22.pre_gap_first == 2.0
        and d22.pre_gap_last == 2.0
        and len(d22.gap) == 2
    ):
        passed += 1
        print("  ✅ one pre-period: has_pre_trend=False and the jump statistic is ABSENT")
    else:
        failed += 1
        print("  ❌ absent trend mishandled:", d22.has_pre_trend, d22.max_abs_pre_gap_change)

    # ── three pre-periods: the trend is a real OLS slope ─────────────────────
    # Treated 11, 12, 14, then 30.  Control 10, 10, 10, 10.  Gaps 1, 2, 4 pre.
    # slope = sum((t - 1)(g - 7/3)) / sum((t - 1)^2) = ((-1)(1 - 7/3) + 0 + (1)(4 - 7/3)) / 2
    #       = (4/3 + 5/3) / 2 = 3 / 2 = 1.5.  Largest one-period jump = |4 - 2| = 2.
    # ATT = (30 - 37/3) - (10 - 10) = 30 - 12.3333... = 17.6666...
    var y34 = _floats(11.0, 12.0, 14.0, 30.0, 10.0, 10.0, 10.0, 10.0)
    var d34 = did_panel(y34, 2, 4, _ints(1, 0), 3)
    var att_expected = 30.0 - 37.0 / 3.0
    if (
        d34.status == CI_OK
        and d34.has_pre_trend
        and _close(d34.pre_trend_diff, 1.5)
        and d34.max_abs_pre_gap_change == 2.0
        and d34.pre_gap_first == 1.0
        and d34.pre_gap_last == 4.0
        and _close(d34.att, att_expected)
        and d34.n_pre == 3
        and d34.n_post == 1
        and d34.pre_trend_r_squared >= 0.0
    ):
        passed += 1
        print("  ✅ three pre-periods: OLS trend slope exactly 1.5, largest jump exactly 2.0")
    else:
        failed += 1
        print("  ❌ pre-trend wrong:", d34.pre_trend_diff, d34.max_abs_pre_gap_change, d34.att)

    # A perfectly parallel pre-period gives a slope of exactly 0 — a REAL zero, and it is
    # distinguishable from the absent case above only by `has_pre_trend`.
    # Treated 11, 12, 13 | 25.  Control 10, 11, 12 | 13.  Gaps are 1, 1, 1 pre.
    # ATT = (25 - 12) - (13 - 11) = 13 - 2 = 11.
    var y_par = _floats(11.0, 12.0, 13.0, 25.0, 10.0, 11.0, 12.0, 13.0)
    var d_par = did_panel(y_par, 2, 4, _ints(1, 0), 3)
    if (
        d_par.status == CI_OK
        and d_par.has_pre_trend
        and d_par.pre_trend_diff == 0.0
        and d_par.max_abs_pre_gap_change == 0.0
        and d_par.att == 11.0
    ):
        passed += 1
        print("  ✅ parallel pre-periods: slope exactly 0.0 WITH has_pre_trend=True")
    else:
        failed += 1
        print("  ❌ parallel case wrong:", d_par.pre_trend_diff, d_par.att)

    # ── per-period arm means come back, so a caller can look ─────────────────
    var means_ok = len(d34.treated_mean) == 4 and len(d34.control_mean) == 4
    if means_ok:
        for t in range(4):
            if d34.gap[t] != d34.treated_mean[t] - d34.control_mean[t]:
                means_ok = False
        if d34.treated_mean[0] != 11.0 or d34.control_mean[3] != 10.0:
            means_ok = False
    if means_ok:
        passed += 1
        print("  ✅ the per-period series are returned and gap == treated - control everywhere")
    else:
        failed += 1
        print("  ❌ the reported series are inconsistent with the gap")

    # ── DiD refusals ─────────────────────────────────────────────────────────
    if (
        did_panel(y22, 2, 2, _ints(1, 0), 0).status == CI_ERR_INVALID_PARAMETER
        and did_panel(y22, 2, 2, _ints(1, 0), 2).status == CI_ERR_INVALID_PARAMETER
        and did_panel(y22, 2, 2, _ints(1, 1), 1).status == CI_ERR_NO_CONTROL
        and did_panel(y22, 2, 2, _ints(0, 0), 1).status == CI_ERR_NO_TREATED
        and did_panel(y22, 2, 2, _ints(1, 2), 1).status == CI_ERR_TREATMENT_NOT_BINARY
        and did_panel(y22, 2, 2, _ints(1), 1).status == CI_ERR_LENGTH_MISMATCH
        and did_panel(y22, 2, 3, _ints(1, 0), 1).status == CI_ERR_SHAPE
        and did_panel(y22, 2, 1, _ints(1, 0), 1).status == CI_ERR_SHAPE
    ):
        passed += 1
        print("  ✅ DiD refuses a zero-length pre or post window, one-armed panels and bad shape")
    else:
        failed += 1
        print("  ❌ DiD refusals incomplete")

    # ── synthetic control: the closed-form minimiser, exactly ────────────────
    # unit 0 (treated): 1, 2, 3 | 10.   donor A: 0, 0, 0 | 0.   donor B: 2, 4, 6 | 8.
    # w_B = 28/56 = 0.5 exactly; pre-period residual 0; synthetic post = 4; effect = 6.
    var y_sc = _floats(
        1.0, 2.0, 3.0, 10.0,
        0.0, 0.0, 0.0, 0.0,
        2.0, 4.0, 6.0, 8.0,
    )
    var sc = synthetic_control(y_sc, 3, 4, 0, 3, 500, 1.0e-14)
    if (
        sc.status == CI_OK
        and sc.converged
        and sc.has_effect
        and sc.n_donors == 2
        and sc.n_pre == 3
        and sc.n_post == 1
        and len(sc.weights) == 2
        and _close(sc.weights[0], 0.5)
        and _close(sc.weights[1], 0.5)
        and _close(sc.sum_weights, 1.0)
        and sc.has_pre_rmse
        and _close(sc.pre_rmse, 0.0)
        and _close(sc.effect, 6.0)
        and _close(sc.synthetic[3], 4.0)
    ):
        passed += 1
        print("  ✅ synthetic control: w = (0.5, 0.5) exactly, pre-RMSE 0, effect exactly 6.0")
    else:
        failed += 1
        print(
            "  ❌ synthetic control wrong:",
            sc.status,
            sc.weights[0] if len(sc.weights) > 0 else -99.0,
            sc.pre_rmse,
            sc.effect,
        )

    # The pre-period entries of `effect_per_period` ARE the fit residuals, by construction.
    var eff_ok = sc.has_effect and len(sc.effect_per_period) == 4
    if eff_ok:
        for t in range(4):
            if not _close(
                sc.effect_per_period[t], y_sc[t] - sc.synthetic[t]
            ):
                eff_ok = False
        for t in range(3):
            if fabs(sc.effect_per_period[t]) > 1.0e-12:
                eff_ok = False
    if eff_ok:
        passed += 1
        print("  ✅ effect_per_period is treated - synthetic everywhere; pre-period entries ~0")
    else:
        failed += 1
        print("  ❌ effect_per_period inconsistent")

    # A donor that reproduces the treated unit exactly gets all the weight.
    var y_one = _floats(
        1.0, 2.0, 3.0, 99.0,
        5.0, 5.0, 5.0, 5.0,
        1.0, 2.0, 3.0, 4.0,
    )
    var one = synthetic_control(y_one, 3, 4, 0, 3, 500, 1.0e-14)
    if (
        one.status == CI_OK
        and one.converged
        and _close(one.weights[0], 0.0)
        and _close(one.weights[1], 1.0)
        and _close(one.pre_rmse, 0.0)
        and _close(one.effect, 95.0)
        and one.n_nonzero_weights == 1
    ):
        passed += 1
        print("  ✅ an exactly matching donor takes weight 1.0; effect 99 - 4 = 95")
    else:
        failed += 1
        print("  ❌ single-donor case wrong:", one.weights[1], one.effect)

    # The weights stay on the simplex: non-negative and summing to 1.
    var simplex_ok = True
    for j in range(len(sc.weights)):
        if sc.weights[j] < 0.0:
            simplex_ok = False
    for j in range(len(one.weights)):
        if one.weights[j] < 0.0:
            simplex_ok = False
    if simplex_ok and _close(sc.sum_weights, 1.0) and _close(one.sum_weights, 1.0):
        passed += 1
        print("  ✅ every weight is >= 0 and each set sums to 1 — the iterate never left the simplex")
    else:
        failed += 1
        print("  ❌ the weights left the simplex")

    # A donor pool that cannot reproduce the path still returns the best fit AND its RMSE, which
    # is the only warrant the weights have.
    var y_bad = _floats(
        1.0, 5.0, 2.0, 50.0,
        0.0, 0.0, 0.0, 0.0,
        1.0, 1.0, 1.0, 1.0,
    )
    var bad = synthetic_control(y_bad, 3, 4, 0, 3, 2000, 1.0e-14)
    if (
        bad.status == CI_OK
        and bad.converged
        and bad.has_pre_rmse
        and bad.pre_rmse > 0.5
        and bad.has_effect
    ):
        passed += 1
        print("  ✅ a poor donor pool still reports its pre-RMSE rather than hiding the misfit")
    else:
        failed += 1
        print("  ❌ poor-fit case wrong:", bad.status, bad.pre_rmse)

    # ── the iteration cap is a REFUSAL with the gap measured ─────────────────
    var capped = synthetic_control(y_one, 3, 4, 0, 3, 1, 1.0e-14)
    if (
        capped.status == CI_ERR_NOT_CONVERGED
        and not capped.converged
        and not capped.has_effect
        and len(capped.weights) == 0
        and len(capped.effect_per_period) == 0
        and capped.n_iter == 1
        and capped.fw_gap != CI_ABSENT
        and capped.fw_gap > 0.0
    ):
        passed += 1
        print("  ✅ max_iter=1: refused, weights absent, and the Frank-Wolfe gap MEASURED")
    else:
        failed += 1
        print("  ❌ non-convergence handling wrong:", capped.status, capped.fw_gap)

    # ── the verdict belongs to the PROBLEM, not to the caller's units ─────────
    # The Frank-Wolfe gap `2 sum_t r_t (Xd)_t` is in SQUARED-OUTCOME units, so judging it against
    # an absolute `tol` made convergence a property of how the outcome happened to be scaled.
    # MEASURED before this was fixed, on one problem with one `tol = 1e-3` and one `max_iter`,
    # changing nothing but the units of `y`: x1e-4 CONVERGED with an effect (fw_gap 3.55e-06)
    # while x1e-2, x1, x100 all REFUSED with CI_ERR_NOT_CONVERGED (fw_gap 0.0355, 355.4, 3.55e6).
    # The mantissa 3.55369 was identical across five orders of magnitude — the gap scaled exactly
    # as c^2 while the threshold stood still. The same problem in dollars and in ten-thousandths
    # of a dollar got opposite answers.
    #
    # THIS IS THE DELIVERABLE. One problem, three unit systems spanning a factor of a million:
    # same status, same converged flag, same n_iter, same weights, and an effect and pre-RMSE
    # that scale by exactly `c` because they are in outcome units.
    var conv_small = synthetic_control(_unit_system(1.0e-3), 4, 6, 0, 4, 200, 0.1)
    var conv_one = synthetic_control(_unit_system(1.0), 4, 6, 0, 4, 200, 0.1)
    var conv_big = synthetic_control(_unit_system(1.0e3), 4, 6, 0, 4, 200, 0.1)
    var same_weights = (
        len(conv_small.weights) == 3
        and len(conv_one.weights) == 3
        and len(conv_big.weights) == 3
    )
    if same_weights:
        for j in range(3):
            if not _close(conv_small.weights[j], conv_one.weights[j]):
                same_weights = False
            if not _close(conv_big.weights[j], conv_one.weights[j]):
                same_weights = False
    if (
        conv_one.status == CI_OK
        and conv_one.converged
        and conv_one.has_effect
        and conv_small.status == conv_one.status
        and conv_big.status == conv_one.status
        and conv_small.converged == conv_one.converged
        and conv_big.converged == conv_one.converged
        and conv_small.n_iter == conv_one.n_iter
        and conv_big.n_iter == conv_one.n_iter
        and same_weights
        and _close(conv_small.effect * 1.0e3, conv_one.effect)
        and _close(conv_big.effect, conv_one.effect * 1.0e3)
        and _close(conv_small.pre_rmse * 1.0e3, conv_one.pre_rmse)
        and _close(conv_big.pre_rmse, conv_one.pre_rmse * 1.0e3)
    ):
        passed += 1
        print("  ✅ one problem, three unit systems: same verdict, same n_iter, same weights")
    else:
        failed += 1
        print(
            "  ❌ the convergence verdict moved with the units:",
            conv_small.status, conv_small.converged, conv_small.n_iter,
            "|", conv_one.status, conv_one.converged, conv_one.n_iter,
            "|", conv_big.status, conv_big.converged, conv_big.n_iter,
        )

    # And the REFUSAL side has to be unit-invariant too, or the fix would just have moved the
    # asymmetry: at a tolerance this problem cannot reach in 500 steps, all three unit systems
    # refuse identically — and the reported gap divided by c^2 is the same number, which is what
    # "the gap carries squared-outcome units" means as an assertion rather than a claim.
    var ref_small = synthetic_control(_unit_system(1.0e-3), 4, 6, 0, 4, 500, 1.0e-3)
    var ref_one = synthetic_control(_unit_system(1.0), 4, 6, 0, 4, 500, 1.0e-3)
    var ref_big = synthetic_control(_unit_system(1.0e3), 4, 6, 0, 4, 500, 1.0e-3)
    if (
        ref_one.status == CI_ERR_NOT_CONVERGED
        and ref_small.status == ref_one.status
        and ref_big.status == ref_one.status
        and not ref_small.converged
        and not ref_one.converged
        and not ref_big.converged
        and ref_small.n_iter == ref_one.n_iter
        and ref_big.n_iter == ref_one.n_iter
        and len(ref_one.weights) == 0
        and _close(ref_small.fw_gap * 1.0e6, ref_one.fw_gap)
        and _close(ref_big.fw_gap, ref_one.fw_gap * 1.0e6)
    ):
        passed += 1
        print("  ✅ the refusal is unit-invariant too, and the gap scales as exactly c^2")
    else:
        failed += 1
        print(
            "  ❌ the refusal moved with the units:",
            ref_small.status, ref_small.fw_gap,
            "|", ref_one.status, ref_one.fw_gap,
            "|", ref_big.status, ref_big.fw_gap,
        )

    # ── synthetic-control refusals ───────────────────────────────────────────
    if (
        synthetic_control(y_sc, 3, 4, 3, 3, 100, 1.0e-12).status == CI_ERR_INVALID_PARAMETER
        and synthetic_control(y_sc, 3, 4, 0, 0, 100, 1.0e-12).status
        == CI_ERR_INVALID_PARAMETER
        and synthetic_control(y_sc, 3, 4, 0, 4, 100, 1.0e-12).status
        == CI_ERR_INVALID_PARAMETER
        and synthetic_control(y_sc, 3, 4, 0, 3, 0, 1.0e-12).status == CI_ERR_INVALID_PARAMETER
        # An iteration ceiling on top of the O(max_iter x n_pre x n_donors) budget, which admits
        # 2^28 iterations when the inner dimensions are small — each allocating its own direction.
        and synthetic_control(
            y_sc, 3, 4, 0, 3, MAX_CI_ITERATIONS + 1, 1.0e-12
        ).status
        == CI_ERR_INVALID_PARAMETER
        and synthetic_control(y_sc, 3, 4, 0, 3, 100, -1.0).status == CI_ERR_INVALID_PARAMETER
        and synthetic_control(y_sc, 3, 5, 0, 3, 100, 1.0e-12).status == CI_ERR_SHAPE
        and synthetic_control(_floats(1.0, 2.0), 1, 2, 0, 1, 10, 1.0e-12).status
        == CI_ERR_SHAPE
    ):
        passed += 1
        print("  ✅ bad treated index, window, iteration cap, tolerance and shape all refused")
    else:
        failed += 1
        print("  ❌ synthetic-control refusals incomplete")

    # ── the A-Z harness pattern ──────────────────────────────────────────────
    if (
        did_panel(_lf5(), 5, 5, _li5(), 5).status == CI_ERR_SHAPE
        and synthetic_control(_lf5(), 5, 5, 5, 5, 5, 0.5).status == CI_ERR_SHAPE
    ):
        passed += 1
        print("  ✅ the fixed 5-element / 5-integer harness pattern is refused, not indexed")
    else:
        failed += 1
        print("  ❌ the A-Z argument pattern was mishandled")

    print("  [causal_inference.panel] Passed:", passed, "Failed:", failed)
