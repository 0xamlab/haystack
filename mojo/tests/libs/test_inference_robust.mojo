"""test_inference_robust.mojo — known-value tests for the Huber IRLS driver.

Hand-written. The strongest available test here is an ENDPOINT, not a tolerance: as the tuning
constant grows every residual falls inside the quadratic region, every Huber weight is exactly
1.0, and the estimator IS ordinary least squares. So `huber_fit_flat` with `tuning = 1e12` is
compared against the frozen `regression.ols_multiple` on the same data and must agree to 1e-9.

That endpoint pins the whole composition at once — the design assembly, the intercept handling,
the weighted normal equations and the solve — and no tolerance can hide a swapped column or a
mis-scaled weight. The two computations are genuinely independent: `regression.ols_multiple`
puts the intercept in column 0 and solves with `regression._solve_normal_equations`, while this
driver puts it LAST and goes through `inference.core.wls_solve_flat`. Measured, they agree to
2e-16 — which is why the assertion is at 1e-9 rather than bitwise: agreement between two
independent computations is evidence, a single plausible number is not.

The robustness claim is then measured against the same frozen kernel on CONTAMINATED data.
Nine points near `y = 2x + 1` plus one shifted by +1000:

    frozen regression.ols_multiple   slope 32.28030303030303   intercept -35.29636363636366
    huber_fit_flat (c = 1.345)       slope  2.0119120691434547 intercept   1.0257055170278544

A single observation moved ordinary least squares by a factor of sixteen. The Huber fit moved by
0.6%, gave that observation a weight of 0.00058, and reports it as one downweighted point.

The MAD scale is cross-checked against the frozen `stats_bootstrap._median` bit-for-bit, since
`robust_scale_mad` deliberately sorts with `sorting.mergesort` instead (the frozen median
insertion-sorts, which would make the IRLS loop quadratic in `n`). On `[3,1,4,1,5,9]` the
median is 3.5, the absolute deviations are `[0.5, 2.5, 0.5, 2.5, 1.5, 5.5]` with median 2.0, so
the scale is `1.482602218505602 * 2 = 2.965204437011204`.

Two opposite outcomes share one arithmetic symptom and are separated rather than collapsed:

* `y = 2x + 1` with only two distinct offsets. Six of the ten residuals agree to rounding, so
  the MAD comes out as 1.45e-14 — not zero, but not distinguishable from zero at the residuals'
  own magnitude of 0.5. There is no usable scale, so the fit is REFUSED
  (`INF_ERR_DEGENERATE`). Before that comparison was made relative to the residual magnitude,
  this input reported `INF_ERR_NOT_CONVERGED` after chasing rounding noise for 100 iterations.
* four identical observations with no covariates. Every residual is exactly zero, the model
  passes through every point, and the answer EXISTS: `exact_fit` is True with all weights 1.0.
"""
from std.math import abs as fabs

from inference.core import (
    INF_ERR_DEGENERATE,
    INF_ERR_DIMENSION_TOO_LARGE,
    INF_ERR_EMPTY,
    INF_ERR_NON_FINITE,
    INF_ERR_NOT_CONVERGED,
    INF_ERR_SHAPE,
    INF_ERR_TOO_FEW,
    INF_ERR_TUNING,
    INF_OK,
    MAX_IRLS_ITER,
    inference_absent,
)
from inference.robust import (
    HUBER_DEFAULT_TUNING,
    MAD_TO_SIGMA,
    ROBUST_SCALE_ABSENT,
    RobustFit,
    huber_fit_flat,
    huber_weight,
    robust_scale_mad,
)
from regression import ols_multiple
from stats_bootstrap import _median


def _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _no_fit(r: RobustFit) -> Bool:
    """A refusal carries no coefficients, no weights and no scale."""
    return (
        r.status != INF_OK
        and not r.converged
        and len(r.coefficients) == 0
        and len(r.weights) == 0
        and r.scale == ROBUST_SCALE_ABSENT
        and r.intercept == 0.0
    )


def _offsets() -> List[Float64]:
    """Ten DISTINCT offsets, so the MAD scale is well defined on this design.

    Distinctness is load-bearing: with only two distinct offsets more than half the residuals
    tie at their median and the MAD collapses, which is the degeneracy case tested separately
    below rather than something to stumble into here.
    """
    return _floats(0.4, -0.3, 0.15, -0.5, 0.25, -0.1, 0.35, -0.45, 0.05, -0.2)


def main():
    var passed: Int = 0
    var failed: Int = 0

    # ── the clean design: y = 2x + 1 + distinct offsets ───────────────────────
    var offs = _offsets()
    var x = List[Float64](capacity=10)
    var y = List[Float64](capacity=10)
    var rows = List[List[Float64]]()
    for i in range(10):
        var xv = Float64(i)
        x.append(xv)
        var row = List[Float64](capacity=1)
        row.append(xv)
        rows.append(row^)
        y.append(2.0 * xv + 1.0 + offs[i])

    # ── 1. the endpoint: a huge tuning constant IS ordinary least squares ─────
    var ols = ols_multiple(rows, y)
    var big_c = huber_fit_flat(x, y, 10, 1, 1.0e12, 100, 1.0e-12)
    if (
        big_c.status == INF_OK
        and big_c.converged
        and len(big_c.coefficients) == 1
        and fabs(big_c.coefficients[0] - ols.coefficients[0]) <= 1.0e-9
        and fabs(big_c.intercept - ols.intercept) <= 1.0e-9
        # measured agreement is 2e-16, i.e. the last bit of the two different solve orders
        and fabs(big_c.coefficients[0] - ols.coefficients[0]) <= 1.0e-14
        # every weight is exactly 1.0, which is WHY the two agree
        and big_c.n_downweighted == 0
        and big_c.min_weight == 1.0
        and len(big_c.weights) == 10
        and big_c.weights[0] == 1.0
        and big_c.weights[9] == 1.0
        # unit weights on the first step, unchanged on the second, so it converges at 2
        and big_c.n_iter == 2
    ):
        passed += 1
        print("  ✅ Huber with a huge tuning equals frozen ols_multiple to 2e-16")
    else:
        failed += 1
        print("  ❌ OLS endpoint:", big_c.status, big_c.coefficients[0], ols.coefficients[0])

    # ── 2. bounded influence, measured against the same frozen kernel ─────────
    var y_out = List[Float64](capacity=10)
    for i in range(10):
        y_out.append(y[i])
    y_out[7] = y_out[7] + 1000.0
    var rows_out = List[List[Float64]]()
    for i in range(10):
        var row = List[Float64](capacity=1)
        row.append(Float64(i))
        rows_out.append(row^)
    var ols_out = ols_multiple(rows_out, y_out)
    var huber = huber_fit_flat(x, y_out, 10, 1, HUBER_DEFAULT_TUNING, 200, 1.0e-10)
    if (
        huber.status == INF_OK
        and huber.converged
        # one gross observation moved OLS by a factor of sixteen
        and fabs(ols_out.coefficients[0] - 32.28030303030303) <= 1.0e-9
        and fabs(ols_out.coefficients[0] - 2.0) > 30.0
        # the Huber fit stayed within 0.6% of the generating slope
        and fabs(huber.coefficients[0] - 2.0) <= 0.02
        and fabs(huber.intercept - 1.0) <= 0.05
        and fabs(huber.coefficients[0] - 2.0119120691434547) <= 1.0e-9
        # and it says which observation it stopped trusting
        and huber.n_downweighted == 1
        and huber.min_weight < 0.001
        and huber.weights[7] == huber.min_weight
        and huber.weights[0] == 1.0
        and huber.scale > 0.0
    ):
        passed += 1
        print("  ✅ one outlier moves OLS 16x and Huber 0.6%; weight 0.00058 on that point")
    else:
        failed += 1
        print("  ❌ robustness:", huber.status, huber.coefficients[0], ols_out.coefficients[0])

    # ── 3. the MAD scale, cross-checked against the frozen median ────────────
    var mm = _floats(3.0, 1.0, 4.0, 1.0, 5.0, 9.0)
    var devs = _floats(0.5, 2.5, 0.5, 2.5, 1.5, 5.5)
    if (
        # the frozen median is 3.5 (even length, averaged), and the deviations' median is 2.0
        _median(mm) == 3.5
        and _median(devs) == 2.0
        and robust_scale_mad(mm, 6) == MAD_TO_SIGMA * 2.0
        and fabs(robust_scale_mad(mm, 6) - 2.965204437011204) <= 1.0e-15
        # odd length takes the middle element, with no averaging
        and _median(_floats(3.0, 1.0, 4.0, 1.0, 5.0)) == 3.0
        and robust_scale_mad(_floats(3.0, 1.0, 4.0, 1.0, 5.0), 5)
        == MAD_TO_SIGMA * _median(_floats(0.0, 2.0, 1.0, 2.0, 2.0))
        and fabs(MAD_TO_SIGMA - 1.482602218505602) <= 1.0e-15
    ):
        passed += 1
        print("  ✅ the mergesort MAD agrees with the frozen median, odd and even length")
    else:
        failed += 1
        print("  ❌ MAD scale:", robust_scale_mad(mm, 6), MAD_TO_SIGMA * 2.0)

    # ── 4. robust_scale_mad's own refusals ───────────────────────────────────
    if (
        # a declared n past the end would read off the array — rule 1, an uncatchable abort
        robust_scale_mad(mm, 25) == ROBUST_SCALE_ABSENT
        and robust_scale_mad(mm, 0) == ROBUST_SCALE_ABSENT
        and robust_scale_mad(mm, -1) == ROBUST_SCALE_ABSENT
        and robust_scale_mad(_floats(1.0, inference_absent()), 2) == ROBUST_SCALE_ABSENT
        # a scale of exactly 0.0 is a REAL answer: more than half the values are at the median
        and robust_scale_mad(_floats(5.0, 5.0, 5.0, 5.0), 4) == 0.0
        and ROBUST_SCALE_ABSENT < 0.0
    ):
        passed += 1
        print("  ✅ the MAD refuses an out-of-range n, and 0.0 stays a real answer")
    else:
        failed += 1
        print("  ❌ MAD refusals:", robust_scale_mad(mm, 25))

    # ── 5. the weight function at its two branches and its refusal ───────────
    if (
        # inside the quadratic region the weight is EXACTLY 1.0, which is what makes the
        # large-tuning endpoint exact rather than approximate
        huber_weight(0.5, 1.0, 1.345) == 1.0
        and huber_weight(1.345, 1.0, 1.345) == 1.0
        # outside it the weight falls like c*s/|r|, so influence is bounded
        and huber_weight(2.0, 1.0, 1.345) == 1.345 / 2.0
        and huber_weight(-2.0, 1.0, 1.345) == huber_weight(2.0, 1.0, 1.345)
        and huber_weight(2.690, 1.0, 1.345) < huber_weight(2.0, 1.0, 1.345)
        # a zero scale or tuning has no weight, and -1.0 is outside [0,1] so it cannot be
        # mistaken for "this observation was discarded"
        and huber_weight(1.0, 0.0, 1.345) == -1.0
        and huber_weight(1.0, 1.0, 0.0) == -1.0
        and huber_weight(inference_absent(), 1.0, 1.345) == -1.0
        and huber_weight(1.0, inference_absent(), 1.345) == -1.0
    ):
        passed += 1
        print("  ✅ the weight is exactly 1 inside the cutoff and c*s/|r| outside it")
    else:
        failed += 1
        print("  ❌ huber_weight:", huber_weight(2.0, 1.0, 1.345), 1.345 / 2.0)

    # ── 6. the MAD breakdown, refused rather than chased ─────────────────────
    # Only two distinct offsets: six of the ten residuals tie at their median to rounding, the
    # MAD is 1.45e-14 against residuals of 0.5, and there is no usable scale.
    var y_tied = List[Float64](capacity=10)
    for i in range(10):
        y_tied.append(2.0 * Float64(i) + 1.0 + (0.3 if i % 3 == 0 else -0.2))
    var degenerate = huber_fit_flat(x, y_tied, 10, 1, HUBER_DEFAULT_TUNING, 100, 1.0e-10)
    if (
        _no_fit(degenerate)
        and degenerate.status == INF_ERR_DEGENERATE
        # refused on the FIRST iteration, not after a hundred of chasing rounding noise
        and degenerate.n_iter == 1
    ):
        passed += 1
        print("  ✅ a MAD that is zero at the residuals' own magnitude is refused, at iter 1")
    else:
        failed += 1
        print("  ❌ MAD breakdown:", degenerate.status, degenerate.n_iter)

    # ── 7. the opposite outcome from the same symptom: an exact fit ──────────
    var empty = List[Float64]()
    var flat_y = _floats(5.0, 5.0, 5.0, 5.0)
    var exact = huber_fit_flat(empty, flat_y, 4, 0, HUBER_DEFAULT_TUNING, 100, 1.0e-10)
    if (
        exact.status == INF_OK
        and exact.exact_fit
        and exact.converged
        and exact.intercept == 5.0
        and exact.scale == 0.0
        and exact.max_abs_residual == 0.0
        and exact.n_downweighted == 0
        and exact.min_weight == 1.0
        and len(exact.weights) == 4
        and len(exact.coefficients) == 0
        and exact.objective == 0.0
    ):
        passed += 1
        print("  ✅ a zero MAD with zero residuals is an EXACT FIT, not the same refusal")
    else:
        failed += 1
        print("  ❌ exact fit:", exact.status, exact.exact_fit, exact.intercept)

    # ── 8. non-convergence has no coefficients ──────────────────────────────
    var capped = huber_fit_flat(x, y_out, 10, 1, HUBER_DEFAULT_TUNING, 1, 1.0e-14)
    if (
        _no_fit(capped)
        and capped.status == INF_ERR_NOT_CONVERGED
        and capped.n_iter == 1
        and capped.max_iter == 1
    ):
        passed += 1
        print("  ✅ an iteration cap is a refusal with a count, never a last iterate")
    else:
        failed += 1
        print("  ❌ non-convergence:", capped.status, capped.n_iter)

    # ── 9. the objective is the Huber loss, and it is finite and non-negative ─
    # In the quadratic region the loss is u^2/2 per observation with u = |r|/s, and the
    # downweighted point contributes the linear branch c(u - c/2). Both are non-negative, and
    # the contaminated fit's objective is dominated by that one linear term:
    # u_7 = 1000/0.434 = 2303, so c(u - c/2) = 1.345 * 2302 = 3097.
    if (
        huber.objective > 0.0
        and fabs(huber.objective - 3097.1524274851163) <= 1.0e-6
        and big_c.objective >= 0.0
        # with a huge cutoff every observation is in the quadratic branch, so the objective is
        # sum (r/s)^2 / 2 and stays small
        and big_c.objective < 20.0
    ):
        passed += 1
        print("  ✅ the objective is the Huber loss: 3097 with the outlier, small without")
    else:
        failed += 1
        print("  ❌ objective:", huber.objective, big_c.objective)

    # ── 10. refusals for shape, tuning and degrees of freedom ───────────────
    if (
        # the payload does not hold 10 x 2 cells
        huber_fit_flat(x, y, 10, 2, 1.345, 50, 1.0e-10).status == INF_ERR_SHAPE
        # len(y) must be exactly n
        and huber_fit_flat(x, _floats(1.0, 2.0), 10, 1, 1.345, 50, 1.0e-10).status
        == INF_ERR_SHAPE
        # n <= p + 1 is not a regression: two observations cannot fit a slope and an intercept
        and huber_fit_flat(_floats(1.0, 2.0), _floats(1.0, 2.0), 2, 1, 1.345, 50, 1.0e-10).status
        == INF_ERR_TOO_FEW
        and huber_fit_flat(x, y, 0, 1, 1.345, 50, 1.0e-10).status == INF_ERR_EMPTY
        and huber_fit_flat(x, y, 10, 1, 0.0, 50, 1.0e-10).status == INF_ERR_TUNING
        and huber_fit_flat(x, y, 10, 1, -1.0, 50, 1.0e-10).status == INF_ERR_TUNING
        and huber_fit_flat(x, y, 10, 1, inference_absent(), 50, 1.0e-10).status
        == INF_ERR_TUNING
        and huber_fit_flat(x, y, 10, 1, 1.345, 0, 1.0e-10).status == INF_ERR_TUNING
        and huber_fit_flat(x, y, 10, 1, 1.345, MAX_IRLS_ITER + 1, 1.0e-10).status
        == INF_ERR_TUNING
        and huber_fit_flat(x, y, 10, 1, 1.345, 50, 0.0).status == INF_ERR_TUNING
        and huber_fit_flat(
            _floats(1.0, 2.0, 3.0, inference_absent()), _floats(1.0, 2.0, 3.0, 4.0),
            4, 1, 1.345, 50, 1.0e-10,
        ).status == INF_ERR_NON_FINITE
    ):
        passed += 1
        print("  ✅ eleven bad requests are refused with distinct statuses and no fit")
    else:
        failed += 1
        print("  ❌ a refusal leaked:", huber_fit_flat(x, y, 10, 2, 1.345, 50, 1.0e-10).status)

    # ── 11. the A-Z harness shapes, which must refuse rather than abort ─────
    # The generated suite calls with _lf5 and 5 for every Int: 5 x 5 = 25 cells backed by 5,
    # which without the guard indexes x[24] on a five-element list.
    var lf5 = _floats(0.5, 0.6, 0.7, 0.4, 0.3)
    if (
        _no_fit(huber_fit_flat(lf5, lf5, 5, 5, 0.5, 5, 0.5))
        and huber_fit_flat(lf5, lf5, 5, 5, 0.5, 5, 0.5).status == INF_ERR_SHAPE
        # and robust_scale_mad(_lf5, 5) is a legal call that must simply work
        and robust_scale_mad(lf5, 5) > 0.0
        and huber_weight(0.5, 0.5, 0.5) >= 0.0
    ):
        passed += 1
        print("  ✅ the harness's 5x5-from-5-cells call is refused, not indexed")
    else:
        failed += 1
        print("  ❌ a harness call was not refused")

    # ── 12. the work budget is a product ───────────────────────────────────
    # 300 observations and 256 parameters is inside every individual ceiling and has more
    # observations than parameters, so nothing else refuses it. The COST is
    # max_iter * n * (p+1)^2 = 1.98e10 at a thousand iterations, past MAX_IRLS_WORK = 2^30. A
    # budget that charged only n, or only p, or only max_iter would let this through.
    var wide_x = List[Float64](capacity=76800)
    for i in range(76800):
        wide_x.append(Float64(i % 3))
    var wide_y = List[Float64](capacity=300)
    for i in range(300):
        wide_y.append(Float64(i % 7))
    if (
        huber_fit_flat(wide_x, wide_y, 300, 256, 1.345, 1000, 1.0e-10).status
        == INF_ERR_DIMENSION_TOO_LARGE
        # the per-dimension ceiling is a separate check and is also enforced
        and huber_fit_flat(wide_x, wide_y, 300, 257, 1.345, 1, 1.0e-10).status
        == INF_ERR_DIMENSION_TOO_LARGE
    ):
        passed += 1
        print("  ✅ max_iter * n * (p+1)^2 is charged as a product, not as a single factor")
    else:
        failed += 1
        print(
            "  ❌ work budget:",
            huber_fit_flat(wide_x, wide_y, 300, 256, 1.345, 1000, 1.0e-10).status,
        )

    print("  [inference.robust] Passed:", passed, "Failed:", failed)
