"""test_causal_inference_sensitivity.mojo — known-value tests for the sensitivity family.

Hand-written. Every number below is a closed form evaluated on paper.

E-VALUES (VanderWeele & Ding)
    E(2.0)  = 2 + sqrt(2 * 1)   = 3.414213562373095
    E(0.5)  = the same, because inverting a protective ratio of the same size takes the same
              confounding to erase — asserted as EXACT equality of the two, not "both about 3.4"
    E(1.0)  = 1.0 exactly: no confounding is needed to explain nothing
    E(1.5)  = 1.5 + sqrt(1.5 * 0.5) = 2.3660254037844384   (used as the CI-limit E-value)

ROBUSTNESS VALUES (Cinelli & Hazlett)
    f = q |t| / sqrt(dof).  At t = 2, dof = 4, q = 1 the intermediate f is exactly 1, and
    RV = (sqrt(1 + 4) - 1) / 2 = (sqrt(5) - 1) / 2 = 0.6180339887498949 — the reciprocal golden
    ratio, which is about as recognisable a fixture as this family offers. `partial_r2` there is
    t^2 / (t^2 + dof) = 4/8 = 0.5 exactly.

THE ROUND TRIP, WHICH IS THE REAL TEST
    `robustness_value` solves a quadratic; `omitted_variable_bias` propagates a bias formula. The
    two are independent derivations of the same statement, so their agreement is evidence. Setting
    a confounder to exactly `RV_q` in both directions must reduce the estimate to exactly
    `(1 - q)` times its size:

        bias = se sqrt(dof) R^2 / sqrt(1 - R^2),  and  q|estimate| = q|t|se
        =>  R^2 / sqrt(1 - R^2) = q|t| / sqrt(dof) = f  =>  R^2 = (sqrt(f^4 + 4f^2) - f^2)/2

    Asserted at q = 1 (the adjusted estimate lands on exactly 0.0), at q = 0.5 (exactly half) and
    at q = 0.25, over three different (t, dof) pairs — so the identity is demonstrated as an
    identity rather than at one lucky point.

ROSENBAUM BOUNDS
    Exact binomial upper tail over the frozen `probability.binomial_pmf`. `n = 4`, `k = 4`,
    gamma = 1 gives p+ = 0.5 and a bound of 0.5^4 = 0.0625 exactly. gamma = 3 gives p+ = 0.75 and
    0.75^4 = 0.31640625 exactly. `k = 0` is a bound of exactly 1.0, and `k = 3` is
    4(0.5^4) + 0.5^4 = 0.3125, cross-checked against the frozen PMF terms summed in the test.

    `rosenbaum_gamma_needed` is checked the only way a bisection answer can be: the bound AT the
    returned gamma must reach the target while the bound just below it must not. That is a
    two-sided bracket assertion computed with a second call to the bound itself, not a comparison
    against a remembered number.
"""
from std.math import abs as fabs, sqrt

from probability import binomial_pmf

from causal_inference.base import (
    CI_ABSENT,
    CI_ERR_INSUFFICIENT_DATA,
    CI_ERR_INVALID_PARAMETER,
    CI_ERR_SHAPE,
    CI_ERR_WORK_BUDGET,
    CI_OK,
    ci_tolerance,
)
from causal_inference.sensitivity import (
    MAX_SIGN_PAIRS,
    e_value_bound,
    e_value_ratio,
    omitted_variable_bias,
    robustness_value,
    rosenbaum_gamma_needed,
    rosenbaum_sign_bound,
    sensitivity_curve,
)


fn _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _close(a: Float64, b: Float64) -> Bool:
    """Judged against the magnitude of THE TWO TERMS BEING COMPARED, and nothing else."""
    return fabs(a - b) <= ci_tolerance(fabs(a) + fabs(b), 0.0)


fn _round_trip_ok(t: Float64, dof: Int, q: Float64) -> Bool:
    """A confounder at exactly RV_q, in both directions, must leave (1 - q) of the estimate.

    Two independent derivations. The tolerance is built from the magnitudes of the estimate and of
    the two quantities being compared — the terms of this one comparison — plus a small absolute
    floor for the q = 1 case, where the expected value is exactly 0 and a purely relative
    allowance would be zero.
    """
    var rv = robustness_value(t, dof, q)
    if rv.status != CI_OK or not rv.has_value:
        return False
    var se = 0.5
    var estimate = t * se
    var ov = omitted_variable_bias(estimate, se, dof, rv.rv, rv.rv)
    if ov.status != CI_OK or not ov.has_result:
        return False
    var expected = (1.0 - q) * estimate
    return fabs(ov.adjusted_estimate - expected) <= ci_tolerance(
        fabs(ov.adjusted_estimate) + fabs(expected) + fabs(estimate), 1.0e-12
    )


fn _lf5() -> List[Float64]:
    return _floats(0.5, 0.6, 0.7, 0.4, 0.3)


fn main() raises:
    var passed = 0
    var failed = 0

    # ── E-values ─────────────────────────────────────────────────────────────
    var e2 = e_value_ratio(2.0)
    var e_half = e_value_ratio(0.5)
    var e1 = e_value_ratio(1.0)
    if (
        e2.status == CI_OK
        and e2.has_value
        and e2.evalue == 2.0 + sqrt(2.0)
        and not e2.inverted
        and e2.rr_oriented == 2.0
        and e_half.status == CI_OK
        and e_half.evalue == e2.evalue
        and e_half.inverted
        and e_half.rr_oriented == 2.0
        and e1.evalue == 1.0
        and e1.has_value
    ):
        passed += 1
        print("  ✅ E(2) = 2 + sqrt(2) exactly; E(0.5) is IDENTICAL; E(1) is exactly 1.0")
    else:
        failed += 1
        print("  ❌ E-value wrong:", e2.evalue, e_half.evalue, e1.evalue)

    var eb = e_value_bound(2.0, 1.5)
    if (
        eb.status == CI_OK
        and eb.evalue == 2.0 + sqrt(2.0)
        and eb.has_ci_limit
        and eb.evalue_ci_limit == 1.5 + sqrt(0.75)
        and not eb.ci_limit_crosses_null
    ):
        passed += 1
        print("  ✅ the CI-limit E-value is 1.5 + sqrt(0.75) = 2.366025403784438")
    else:
        failed += 1
        print("  ❌ CI-limit E-value wrong:", eb.evalue_ci_limit)

    # A limit that crosses the null needs NO confounding, and says so with a flag rather than
    # with a number a caller has to interpret.
    var crosses = e_value_bound(2.0, 0.9)
    var crosses_low = e_value_bound(0.5, 1.2)
    if (
        crosses.status == CI_OK
        and crosses.ci_limit_crosses_null
        and crosses.evalue_ci_limit == 1.0
        and crosses_low.status == CI_OK
        and crosses_low.ci_limit_crosses_null
        and crosses_low.evalue_ci_limit == 1.0
    ):
        passed += 1
        print("  ✅ a null-crossing limit gives an E-value of exactly 1.0, in both orientations")
    else:
        failed += 1
        print("  ❌ null-crossing case wrong:", crosses.evalue_ci_limit)

    # The protective orientation uses the UPPER limit; a limit on the wrong side is refused
    # rather than answered, because such a number has no interpretation.
    var protective = e_value_bound(0.5, 0.8)
    if (
        protective.status == CI_OK
        and protective.has_ci_limit
        and _close(protective.evalue_ci_limit, 1.25 + sqrt(1.25 * 0.25))
        and e_value_bound(2.0, 3.0).status == CI_ERR_INVALID_PARAMETER
        and e_value_bound(0.5, 0.2).status == CI_ERR_INVALID_PARAMETER
        and e_value_ratio(0.0).status == CI_ERR_INVALID_PARAMETER
        and e_value_ratio(-1.0).status == CI_ERR_INVALID_PARAMETER
    ):
        passed += 1
        print("  ✅ protective orientation inverts the upper limit; a wrong-side limit refused")
    else:
        failed += 1
        print("  ❌ orientation handling wrong:", protective.evalue_ci_limit)

    # A risk ratio of 0 is NOT an infinite E-value.
    if e_value_ratio(0.0).evalue == CI_ABSENT and not e_value_ratio(0.0).has_value:
        passed += 1
        print("  ✅ RR = 0 is refused with an ABSENT E-value, never an infinity")
    else:
        failed += 1
        print("  ❌ RR=0 produced a value")

    # ── robustness values ────────────────────────────────────────────────────
    var rv1 = robustness_value(2.0, 4, 1.0)
    if (
        rv1.status == CI_OK
        and rv1.has_value
        and rv1.f_q == 1.0
        and _close(rv1.rv, 0.5 * (sqrt(5.0) - 1.0))
        and rv1.has_partial_r2
        and rv1.partial_r2 == 0.5
        and rv1.t_abs == 2.0
        and rv1.q == 1.0
    ):
        passed += 1
        print("  ✅ RV(t=2, dof=4, q=1) = (sqrt(5)-1)/2 = 0.618033988749895; partial R2 = 0.5")
    else:
        failed += 1
        print("  ❌ robustness value wrong:", rv1.rv, rv1.f_q, rv1.partial_r2)

    # A negative t gives the same RV — only |t| enters.
    if robustness_value(-2.0, 4, 1.0).rv == rv1.rv:
        passed += 1
        print("  ✅ RV depends on |t| only: t = -2 gives the identical value")
    else:
        failed += 1
        print("  ❌ RV is not symmetric in the sign of t")

    # t = 0 needs no confounding at all: RV is exactly 0, a real answer.
    var rv0 = robustness_value(0.0, 10, 1.0)
    if rv0.status == CI_OK and rv0.has_value and rv0.rv == 0.0 and rv0.partial_r2 == 0.0:
        passed += 1
        print("  ✅ t = 0: RV is exactly 0.0 — an estimate at zero needs no explaining away")
    else:
        failed += 1
        print("  ❌ t=0 case wrong:", rv0.rv)

    # RV must fall as q falls: a smaller demanded reduction needs a weaker confounder.
    var rv_half = robustness_value(2.0, 4, 0.5)
    var rv_quarter = robustness_value(2.0, 4, 0.25)
    if rv_quarter.rv < rv_half.rv and rv_half.rv < rv1.rv:
        passed += 1
        print("  ✅ RV is strictly increasing in q, as the definition requires")
    else:
        failed += 1
        print("  ❌ RV is not monotone in q:", rv_quarter.rv, rv_half.rv, rv1.rv)

    # ── THE ROUND TRIP between two independent derivations ────────────────────
    if (
        _round_trip_ok(2.0, 4, 1.0)
        and _round_trip_ok(2.0, 4, 0.5)
        and _round_trip_ok(2.0, 4, 0.25)
        and _round_trip_ok(5.0, 40, 1.0)
        and _round_trip_ok(5.0, 40, 0.5)
        and _round_trip_ok(1.5, 9, 0.75)
    ):
        passed += 1
        print("  ✅ a confounder at RV_q leaves exactly (1-q) of the estimate — 6 (t,dof,q) cases")
    else:
        failed += 1
        print("  ❌ the RV / OVB round trip failed")

    # At q = 1 specifically, the adjusted estimate must land on 0 to within rounding.
    var rt = omitted_variable_bias(1.0, 0.5, 4, rv1.rv, rv1.rv)
    if rt.status == CI_OK and fabs(rt.adjusted_estimate) < 1.0e-15 and not rt.flips_sign:
        passed += 1
        print("  ✅ at q=1 the adjusted estimate is 0 to 1e-15, and does not overshoot the sign")
    else:
        failed += 1
        print("  ❌ q=1 round trip wrong:", rt.adjusted_estimate, rt.flips_sign)

    # ── omitted-variable bias: no confounder means no adjustment ──────────────
    var zero_r2 = omitted_variable_bias(3.0, 0.5, 10, 0.0, 0.0)
    var zero_yz = omitted_variable_bias(3.0, 0.5, 10, 0.4, 0.0)
    if (
        zero_r2.status == CI_OK
        and zero_r2.bias == 0.0
        and zero_r2.adjusted_estimate == 3.0
        and not zero_r2.flips_sign
        and zero_yz.bias == 0.0
        and zero_yz.adjusted_estimate == 3.0
    ):
        passed += 1
        print("  ✅ r2 = 0 in either direction: bias exactly 0 and the estimate untouched")
    else:
        failed += 1
        print("  ❌ zero-strength case wrong:", zero_r2.bias, zero_yz.bias)

    # A negative estimate is adjusted TOWARD zero, i.e. upward.
    var neg = omitted_variable_bias(-1.0, 0.5, 4, rv1.rv, rv1.rv)
    if neg.status == CI_OK and fabs(neg.adjusted_estimate) < 1.0e-15:
        passed += 1
        print("  ✅ a negative estimate is moved toward zero, not further from it")
    else:
        failed += 1
        print("  ❌ sign handling wrong:", neg.adjusted_estimate)

    # A strong confounder flips the sign, and that is reported explicitly.
    var flipped = omitted_variable_bias(1.0, 0.5, 4, 0.9, 0.9)
    if (
        flipped.status == CI_OK
        and flipped.flips_sign
        and flipped.adjusted_estimate < 0.0
        and flipped.bias > 1.0
    ):
        passed += 1
        print("  ✅ a confounder stronger than the estimate sets flips_sign = True")
    else:
        failed += 1
        print("  ❌ sign flip not reported:", flipped.flips_sign, flipped.bias)

    # r2_dz = 1 leaves nothing to identify from: refused, not an infinity.
    if (
        omitted_variable_bias(1.0, 0.5, 4, 1.0, 0.5).status == CI_ERR_INVALID_PARAMETER
        and omitted_variable_bias(1.0, 0.5, 4, 1.1, 0.5).status == CI_ERR_INVALID_PARAMETER
        and omitted_variable_bias(1.0, 0.5, 4, 0.5, 1.5).status == CI_ERR_INVALID_PARAMETER
        and omitted_variable_bias(1.0, 0.5, 1, 0.5, 0.5).status == CI_ERR_INSUFFICIENT_DATA
        and omitted_variable_bias(1.0, -0.5, 4, 0.5, 0.5).status == CI_ERR_INVALID_PARAMETER
        and robustness_value(2.0, 0, 1.0).status == CI_ERR_INSUFFICIENT_DATA
        and robustness_value(2.0, 4, 0.0).status == CI_ERR_INVALID_PARAMETER
        and robustness_value(2.0, 4, 1.5).status == CI_ERR_INVALID_PARAMETER
    ):
        passed += 1
        print("  ✅ r2_dz = 1, out-of-range r2, dof < 2 and q outside (0,1] all refused")
    else:
        failed += 1
        print("  ❌ parameter refusals incomplete")

    # ── the curve agrees with the scalar entry point, point by point ──────────
    var grid = _floats(0.0, 0.2, rv1.rv, 0.9, 1.0, -0.1)
    var curve = sensitivity_curve(1.0, 0.5, 4, grid)
    var curve_ok = curve.status == CI_OK and curve.has_curve and curve.n_points == 6
    if curve_ok:
        for k in range(6):
            var r2 = grid[k]
            if r2 < 0.0 or r2 >= 1.0:
                if curve.has_point[k]:
                    curve_ok = False
                continue
            if not curve.has_point[k]:
                curve_ok = False
                continue
            var scalar = omitted_variable_bias(1.0, 0.5, 4, r2, r2)
            if scalar.status != CI_OK:
                curve_ok = False
                continue
            if curve.bias[k] != scalar.bias:
                curve_ok = False
            if curve.adjusted[k] != scalar.adjusted_estimate:
                curve_ok = False
    if curve_ok and curve.n_absent == 2:
        passed += 1
        print("  ✅ every curve point is BIT-IDENTICAL to omitted_variable_bias at that r2")
    else:
        failed += 1
        print("  ❌ the curve and the scalar entry point disagree:", curve.n_absent)

    # A grid point at or above 1 is absent, never clamped to a nearby value.
    if (
        not curve.has_point[4]
        and curve.bias[4] == 0.0
        and not curve.has_point[5]
        and curve.has_sign_flip
        and curve.first_sign_flip_r2 <= 0.9
    ):
        passed += 1
        print("  ✅ r2 >= 1 and r2 < 0 are ABSENT points; the sign flip is located on the grid")
    else:
        failed += 1
        print("  ❌ absent-point handling wrong:", curve.has_sign_flip, curve.first_sign_flip_r2)

    # A curve with no usable point at all has no curve.
    var no_curve = sensitivity_curve(1.0, 0.5, 4, _floats(1.0, 2.0))
    if not no_curve.has_curve and no_curve.status == CI_ERR_INVALID_PARAMETER:
        passed += 1
        print("  ✅ a grid with no usable point yields no curve, not an empty-but-OK one")
    else:
        failed += 1
        print("  ❌ empty-curve case wrong:", no_curve.status)

    if (
        sensitivity_curve(1.0, 0.5, 4, List[Float64]()).status == CI_ERR_INSUFFICIENT_DATA
        and sensitivity_curve(1.0, 0.5, 1, _floats(0.5)).status == CI_ERR_INSUFFICIENT_DATA
    ):
        passed += 1
        print("  ✅ an empty grid and dof < 2 are refused")
    else:
        failed += 1
        print("  ❌ curve refusals incomplete")

    # ── Rosenbaum bounds: exact binomial tails ───────────────────────────────
    var rb1 = rosenbaum_sign_bound(4, 4, 1.0)
    var rb3 = rosenbaum_sign_bound(4, 4, 3.0)
    var rb0 = rosenbaum_sign_bound(4, 0, 1.0)
    if (
        rb1.status == CI_OK
        and rb1.has_bound
        and rb1.p_plus == 0.5
        and _close(rb1.p_upper_bound, 0.0625)
        and rb3.p_plus == 0.75
        and _close(rb3.p_upper_bound, 0.31640625)
        and _close(rb0.p_upper_bound, 1.0)
        and rb1.n_pairs == 4
        and rb1.n_positive == 4
    ):
        passed += 1
        print("  ✅ Bin(4, 0.5) tail at 4 is 0.0625; Bin(4, 0.75) is 0.31640625; k=0 is 1.0")
    else:
        failed += 1
        print("  ❌ Rosenbaum tails wrong:", rb1.p_upper_bound, rb3.p_upper_bound)

    # Cross-check against the frozen PMF summed here, independently of the module.
    var manual = binomial_pmf(3, 4, 0.5) + binomial_pmf(4, 4, 0.5)
    var rb_three = rosenbaum_sign_bound(4, 3, 1.0)
    if _close(rb_three.p_upper_bound, manual) and _close(manual, 0.3125):
        passed += 1
        print("  ✅ the tail equals the frozen binomial_pmf terms summed in the test: 0.3125")
    else:
        failed += 1
        print("  ❌ tail disagrees with the frozen PMF:", rb_three.p_upper_bound, manual)

    # The bound is monotone increasing in gamma, which the bisection depends on.
    var mono_ok = True
    var prev = 0.0
    for step in range(1, 12):
        var g = Float64(step)
        var probe = rosenbaum_sign_bound(20, 18, g)
        if probe.status != CI_OK or probe.p_upper_bound < prev:
            mono_ok = False
        prev = probe.p_upper_bound
    if mono_ok:
        passed += 1
        print("  ✅ the bound is monotone in gamma over 11 values — the bisection's premise")
    else:
        failed += 1
        print("  ❌ the bound is not monotone in gamma")

    # ── the critical gamma, bracketed from both sides ────────────────────────
    var need = rosenbaum_gamma_needed(20, 18, 0.05, 100.0, 1.0e-9)
    var at_gamma = rosenbaum_sign_bound(20, 18, need.gamma_critical)
    var just_below = rosenbaum_sign_bound(20, 18, need.gamma_critical - 1.0e-6)
    if (
        need.status == CI_OK
        and need.has_gamma
        and need.gamma_critical > 1.0
        and at_gamma.p_upper_bound >= 0.05
        and just_below.p_upper_bound < 0.05
        and need.n_iter > 0
    ):
        passed += 1
        print("  ✅ the critical gamma is bracketed: the bound reaches 0.05 at it, not below it")
    else:
        failed += 1
        print(
            "  ❌ critical gamma wrong:",
            need.gamma_critical,
            at_gamma.p_upper_bound,
            just_below.p_upper_bound,
        )

    # A result that is already non-significant needs gamma = 1 exactly, not a search.
    var already = rosenbaum_gamma_needed(4, 2, 0.5, 100.0, 1.0e-9)
    if already.status == CI_OK and already.has_gamma and already.gamma_critical == 1.0:
        passed += 1
        print("  ✅ an already non-significant result returns gamma exactly 1.0")
    else:
        failed += 1
        print("  ❌ the gamma=1 shortcut wrong:", already.gamma_critical)

    # No gamma inside the range is an ABSENT answer, not the ceiling reported as the answer.
    var unreachable = rosenbaum_gamma_needed(200, 200, 0.05, 1.5, 1.0e-9)
    if (
        unreachable.status == CI_OK
        and not unreachable.has_gamma
        and unreachable.gamma_critical == CI_ABSENT
        and unreachable.has_bound
    ):
        passed += 1
        print("  ✅ no gamma inside the range: ABSENT, and the ceiling is NOT reported as it")
    else:
        failed += 1
        print("  ❌ unreachable gamma wrong:", unreachable.has_gamma, unreachable.gamma_critical)

    # ── Rosenbaum refusals, including the overflow ceiling ───────────────────
    if (
        rosenbaum_sign_bound(0, 0, 1.0).status == CI_ERR_INSUFFICIENT_DATA
        and rosenbaum_sign_bound(4, 5, 1.0).status == CI_ERR_SHAPE
        and rosenbaum_sign_bound(4, -1, 1.0).status == CI_ERR_SHAPE
        and rosenbaum_sign_bound(4, 4, 0.5).status == CI_ERR_INVALID_PARAMETER
        and rosenbaum_sign_bound(MAX_SIGN_PAIRS + 1, 1, 1.0).status == CI_ERR_WORK_BUDGET
        and rosenbaum_gamma_needed(4, 4, 0.0, 10.0, 1.0e-9).status == CI_ERR_INVALID_PARAMETER
        and rosenbaum_gamma_needed(4, 4, 0.05, 1.0, 1.0e-9).status == CI_ERR_INVALID_PARAMETER
        and rosenbaum_gamma_needed(4, 4, 0.05, 10.0, 0.0).status == CI_ERR_INVALID_PARAMETER
    ):
        passed += 1
        print("  ✅ pair count, positive count, gamma < 1 and the overflow ceiling all refused")
    else:
        failed += 1
        print("  ❌ Rosenbaum refusals incomplete")

    # The tail at the ceiling itself must still be a real probability, not a nan.
    var at_ceiling = rosenbaum_sign_bound(MAX_SIGN_PAIRS, MAX_SIGN_PAIRS // 2, 1.0)
    if (
        at_ceiling.status == CI_OK
        and at_ceiling.p_upper_bound >= 0.0
        and at_ceiling.p_upper_bound <= 1.0
        and at_ceiling.p_upper_bound > 0.4
    ):
        passed += 1
        print("  ✅ at 1000 pairs the exact central tail is still a probability, ~0.51")
    else:
        failed += 1
        print("  ❌ the ceiling case overflowed:", at_ceiling.status, at_ceiling.p_upper_bound)

    # ── the A-Z harness pattern ──────────────────────────────────────────────
    if (
        e_value_ratio(0.5).status == CI_OK
        and e_value_bound(0.5, 0.5).status == CI_OK
        and robustness_value(0.5, 5, 0.5).status == CI_OK
        and omitted_variable_bias(0.5, 0.5, 5, 0.5, 0.5).status == CI_OK
        and sensitivity_curve(0.5, 0.5, 5, _lf5()).status == CI_OK
        and rosenbaum_sign_bound(5, 5, 0.5).status == CI_ERR_INVALID_PARAMETER
        and rosenbaum_gamma_needed(5, 5, 0.5, 0.5, 0.5).status == CI_ERR_INVALID_PARAMETER
    ):
        passed += 1
        print("  ✅ the fixed harness arguments are either answered or refused, never indexed")
    else:
        failed += 1
        print("  ❌ the A-Z argument pattern was mishandled")

    print("  [causal_inference.sensitivity] Passed:", passed, "Failed:", failed)
