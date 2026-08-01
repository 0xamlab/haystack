"""
inference.robust — Huber regression by iteratively reweighted least squares. Zero Python.

Why this module exists
----------------------
Nothing in the tree fits a robust regression. `regression` has `ols_simple`,
`ols_multiple`, `ridge_regression` and `polynomial_features`; `linear_models` has
elastic net and logistic; `pls` has partial least squares. Every one of them minimises a
SQUARED residual, so one gross observation moves the fit by an amount proportional to its
own size. There is no M-estimator, no Huber loss, no MAD scale and no bounded influence
function anywhere.

`robustness.mojo` is not it either: its functions score robustness (perturbation stability,
adversarial margins) rather than estimate a model.

What is reused rather than rebuilt
----------------------------------
* `inference.core.wls_solve_flat` — every IRLS step, which is in turn the frozen
  `linear_models._solve_linear_system` behind the frozen
  `linalg_ext.mat_is_positive_definite` rank test plus a per-row backward-error check.
* `sorting.mergesort` — the two sorts the MAD scale needs.
* `inference.core` for the status vocabulary, the finiteness predicate, the rule-4b
  tolerance builder and the wrapping-safe budgets.

`stats_bootstrap._median` is the tree's median and is NOT called from the IRLS loop, for a
WORK reason rather than a correctness one: it insertion-sorts, so it is O(n^2), and calling
it twice per iteration would make this driver O(max_iter * n^2) with the quadratic term
dominating everything else. `robust_scale_mad` below computes the same quantity through
`sorting.mergesort` in O(n log n); the suite asserts the two agree BIT-FOR-BIT on several
inputs, including the even-length average case, so the substitution is measured and not
assumed.

Rule 4 in this module
---------------------
* An IRLS fit that did not converge has no coefficients. `INF_ERR_NOT_CONVERGED` carries
  `n_iter` and `max_iter` and an EMPTY coefficient list.
* **A MAD scale of zero is not a scale.** When more than half the residuals sit exactly at
  their median, the MAD is 0, every Huber cutoff `c * s` collapses to 0, and every
  observation with a nonzero residual would receive weight 0 — the fit would be determined by
  the tied half alone. That is `INF_ERR_DEGENERATE`, not a fit. The ONE exception is an exact
  fit: if the MAD is 0 *and* the largest absolute residual is 0, every residual is zero, the
  model passes through every point, and the answer exists. Those two cases are distinguished
  rather than collapsed, because they are opposite outcomes.
* **No standard errors, on purpose.** A Huber estimator's asymptotic variance needs a
  sandwich estimator built from the influence function's first two moments. This driver does
  not compute one, and the weighted-least-squares standard errors from the final weights are
  NOT it — they are the standard errors of a WLS fit with those weights treated as known,
  which understates the uncertainty. Reporting them under a name like `std_errors` would be a
  confident wrong answer, so the struct has no such field and this paragraph says why.
* A non-positive tuning constant is `INF_ERR_TUNING`. `c = 0` would give every nonzero
  residual weight 0.

The strongest available test, and it is an endpoint not a tolerance
-------------------------------------------------------------------
As the tuning constant grows, every residual falls inside the quadratic region, every weight
is exactly 1.0, and the estimator IS ordinary least squares. So `huber_fit_flat` with a huge
`tuning` must equal `regression.ols_multiple` to 1e-9, and the suite asserts exactly that
against the frozen kernel. It is the strongest check available here because it pins the whole
composition — the design assembly, the intercept handling, the normal equations and the solve
— against an independent frozen implementation, and no tolerance can hide a swapped column
or a mis-scaled weight.

The two implementations are not the same code: `regression.ols_multiple` puts the intercept
in column 0 and solves with `regression._solve_normal_equations`, while this driver puts it
LAST and solves through `inference.core.wls_solve_flat`. They therefore round differently,
which is why the endpoint is asserted at 1e-9 rather than bitwise — agreement between two
independent computations is evidence, and a single plausible number is not.

Status codes 320-339 belong to the `inference` package; this module allocates none of its own
(rule 4e).

Bounds, per rule 1c and "bounding memory is not bounding work"
-------------------------------------------------------------
Shape: `n * p == len(x)` by division (a wrapping multiply is not a bound), `len(y) == n`
exactly, `n <= MAX_INFERENCE_OBS`, `p <= MAX_INFERENCE_PARAMS`. Memory is eight
`n`-length arrays plus a `(p+1)^2` matrix.

Two work products are charged, because a budget that counts one factor of a product is not a
budget:

    max_iter * n * (p+1)^2    the normal-equations accumulation
    max_iter * n * ceil(log2 n) <= max_iter * n * 64    the two MAD sorts per iteration

both through `inference_product3_fits`, which decides by division.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_inference_robust.mojo
benchmark: benchmarks/mojo_benchmarks/bench_inference.mojo
docs: none
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs

from inference.core import (
    INF_ERR_DEGENERATE,
    INF_ERR_DIMENSION_TOO_LARGE,
    INF_ERR_DIVERGED,
    INF_ERR_EMPTY,
    INF_ERR_NON_FINITE,
    INF_ERR_NOT_CONVERGED,
    INF_ERR_SHAPE,
    INF_ERR_TOO_FEW,
    INF_ERR_TUNING,
    INF_OK,
    MAX_INFERENCE_OBS,
    MAX_INFERENCE_PARAMS,
    MAX_IRLS_ITER,
    MAX_IRLS_WORK,
    inference_dims_fit,
    inference_finite,
    inference_product3_fits,
    inference_scaled_tol,
    wls_solve_flat,
)
from sorting import mergesort

# 1 / 0.6744897501960817 — the 75th percentile of the standard normal. Multiplying the MAD
# by this makes the scale estimate CONSISTENT for the standard deviation of a normal sample,
# which is the only reason a MAD is comparable to a residual on the same axis.
comptime MAD_TO_SIGMA: Float64 = 1.482602218505602

# Huber's constant. 1.345 * sigma gives 95% asymptotic efficiency at the normal while
# bounding the influence of a single observation. Exposed as the DEFAULT a caller should pass
# rather than defaulted in the signature: an unstated tuning constant is an unstated
# efficiency/robustness trade, and the arity of a public function is load-bearing here (the
# dispatch generator emits an exact-count check).
comptime HUBER_DEFAULT_TUNING: Float64 = 1.345

# A scale is non-negative, so -1.0 is outside the range and says "never computed".
comptime ROBUST_SCALE_ABSENT: Float64 = -1.0


fn robust_scale_mad(residuals: List[Float64], n: Int) -> Float64:
    """`1.4826 * median(|r_i - median(r)|)` — the MAD scale, or `ROBUST_SCALE_ABSENT`.

    The scale every Huber weight is measured against, exported because it is the number a
    caller most needs to see beside a robust fit: it says how large a residual has to be
    before the estimator stops trusting it.

    Two `sorting.mergesort` passes, O(n log n). `stats_bootstrap._median` computes the same
    median and is deliberately not called — it insertion-sorts, so using it here would make
    the IRLS loop quadratic in `n` (see the module docstring). The suite asserts the two
    agree bit-for-bit, odd and even length, so this is a measured substitution.

    Returns `ROBUST_SCALE_ABSENT` (-1.0) for `n <= 0`, `n > len(residuals)` (which would
    otherwise read past the end — rule 1, an uncatchable abort) or any non-finite residual.
    A return of exactly 0.0 is a real answer and means "more than half the residuals are at
    their median"; the caller decides whether that is an exact fit or a degeneracy, and
    `huber_fit_flat` does exactly that.

    @capability robust_scale_mad
    complexity: O(n log n)
    counts:
    - n <= len(residuals) [kernel_validated]
    @endcapability
    """
    if n <= 0 or n > len(residuals):
        return ROBUST_SCALE_ABSENT
    var values = List[Float64](capacity=n)
    for i in range(n):
        if not inference_finite(residuals[i]):
            return ROBUST_SCALE_ABSENT
        values.append(residuals[i])
    var centre = _median_of(values)
    var deviations = List[Float64](capacity=n)
    for i in range(n):
        deviations.append(fabs(values[i] - centre))
    return MAD_TO_SIGMA * _median_of(deviations)


fn _median_of(values: List[Float64]) -> Float64:
    """The median of `values`, via `sorting.mergesort`. Even length averages the two middles.

    Byte-for-byte the same definition as `stats_bootstrap._median`, including the even-length
    average and its order of operations `(a + b) / 2.0`, so the two cannot disagree; the only
    difference is the sort underneath. Assumes a non-empty, all-finite input, which
    `robust_scale_mad` establishes.
    """
    var n = len(values)
    if n == 0:
        return 0.0
    var sorted_v = mergesort(values)
    if len(sorted_v) != n:
        return 0.0
    if n % 2 == 1:
        return sorted_v[n // 2]
    return (sorted_v[n // 2 - 1] + sorted_v[n // 2]) / 2.0


fn huber_weight(residual: Float64, scale: Float64, tuning: Float64) -> Float64:
    """Huber's weight `min(1, c*s/|r|)`, the IRLS form of his loss. Or -1.0 if undefined.

    Inside the quadratic region (`|r| <= c*s`) the weight is exactly 1.0, which is why a
    large `tuning` reduces the estimator to ordinary least squares EXACTLY rather than
    approximately. Outside it the weight falls like `1/|r|`, so the observation's
    contribution to the score is bounded: this is where the bounded influence comes from.

    A non-positive `scale` or `tuning`, or a non-finite argument, returns -1.0. A weight is
    in `[0, 1]`, so -1.0 cannot be read as "this observation was discarded" — which is what
    returning 0.0 there would say, and 0.0 is a legitimate limit of the real formula.
    """
    if not inference_finite(residual) or not inference_finite(scale):
        return -1.0
    if not inference_finite(tuning) or tuning <= 0.0 or scale <= 0.0:
        return -1.0
    var cutoff = tuning * scale
    var magnitude = fabs(residual)
    if magnitude <= cutoff:
        return 1.0
    return cutoff / magnitude


@fieldwise_init
struct RobustFit(Copyable, Movable):
    """A Huber M-estimate, or a refusal that says which outcome occurred.

    `coefficients` and `weights` are EMPTY unless `status == INF_OK`.

    `coefficients` holds the `p` covariate coefficients and `intercept` is separate; X must
    NOT contain a column of ones, matching `inference.glm`'s contract and the frozen
    `linear_models.logistic_fit`.

    `scale` is the final MAD scale (`robust_scale_mad`) and `ROBUST_SCALE_ABSENT` on refusal.
    `weights[i]` is the final Huber weight of observation `i`, so which observations the
    estimator stopped trusting is answerable from the result alone rather than inferred.

    `n_downweighted` counts the weights strictly below 1.0 and `min_weight` is the smallest.
    `objective` is the Huber loss at the returned coefficients, in units of the scale.

    There is deliberately NO standard-error field — see the module docstring. `exact_fit` is
    True when every residual is exactly zero, which is the one case a zero MAD scale is an
    answer rather than a degeneracy.
    """

    var status: Int
    var n_obs: Int
    var n_params: Int
    var tuning: Float64
    var converged: Bool
    var exact_fit: Bool
    var n_iter: Int
    var max_iter: Int
    var intercept: Float64
    var coefficients: List[Float64]
    var weights: List[Float64]
    var scale: Float64
    var n_downweighted: Int
    var min_weight: Float64
    var max_abs_residual: Float64
    var objective: Float64


fn _robust_failure(
    code: Int, n: Int, p: Int, tuning: Float64, iters: Int, max_iter: Int
) -> RobustFit:
    return RobustFit(
        code, n, p, tuning, False, False, iters, max_iter, 0.0,
        List[Float64](), List[Float64](), ROBUST_SCALE_ABSENT, 0, -1.0, -1.0, -1.0,
    )


fn huber_fit_flat(
    x: List[Float64], y: List[Float64], n: Int, p: Int,
    tuning: Float64, max_iter: Int, tol: Float64,
) -> RobustFit:
    """Huber regression by IRLS, with the MAD scale re-estimated at every iteration.

    `X` is flat row-major `n x p` WITHOUT an intercept column; the intercept is fitted
    internally and returned separately.

    The first step carries unit weights, so it is exactly ordinary least squares and the
    iteration starts from the OLS fit rather than from zero. Each subsequent step re-estimates
    the scale from the current residuals (`robust_scale_mad`), forms Huber weights
    (`huber_weight`), and solves the weighted normal equations through
    `inference.core.wls_solve_flat`, which refuses a rank-deficient system instead of
    returning zeros for it.

    Convergence is decided PER COEFFICIENT against that coefficient's own magnitude:
    `|delta_j| <= inference_scaled_tol(|beta_j|, tol)` — the caller's absolute tolerance plus
    DBL_EPSILON times the size of the thing being judged (rule 4b). Not a vector norm, which
    would let a large coefficient's units pay for a small one's movement, and with no `1+|x|`
    floor to make a "relative" test secretly absolute.

    Refuses: a payload that does not match `n` and `p`; a non-finite input; `n <= p + 1`
    (fewer observations than parameters is not a regression); a non-positive or non-finite
    `tuning` or `tol`; a `max_iter` outside `[1, MAX_IRLS_ITER]`; a work product above
    `MAX_IRLS_WORK`; a degenerate MAD scale that is not an exact fit; a rank-deficient
    weighted system; and an iteration cap reached without convergence.

    @capability huber_fit_flat
    complexity: O(max_iter * (n * (p+1)^2 + n log n))
    counts:
    - n * p == len(x) [kernel_validated]
    - n == len(y) [kernel_validated]
    @endcapability
    """
    if n <= 0:
        return _robust_failure(INF_ERR_EMPTY, n, p, tuning, 0, max_iter)
    if n > MAX_INFERENCE_OBS or p > MAX_INFERENCE_PARAMS or p < 0:
        return _robust_failure(INF_ERR_DIMENSION_TOO_LARGE, n, p, tuning, 0, max_iter)
    if not inference_dims_fit(n, p, len(x)) or len(y) != n:
        return _robust_failure(INF_ERR_SHAPE, n, p, tuning, 0, max_iter)
    if n <= p + 1:
        return _robust_failure(INF_ERR_TOO_FEW, n, p, tuning, 0, max_iter)
    if not inference_finite(tuning) or tuning <= 0.0:
        return _robust_failure(INF_ERR_TUNING, n, p, tuning, 0, max_iter)
    if not inference_finite(tol) or tol <= 0.0:
        return _robust_failure(INF_ERR_TUNING, n, p, tuning, 0, max_iter)
    if max_iter < 1 or max_iter > MAX_IRLS_ITER:
        return _robust_failure(INF_ERR_TUNING, n, p, tuning, 0, max_iter)
    var q = p + 1
    if not inference_product3_fits(max_iter, n, q * q, MAX_IRLS_WORK):
        return _robust_failure(INF_ERR_DIMENSION_TOO_LARGE, n, p, tuning, 0, max_iter)
    # The two MAD sorts per iteration cost n log2(n) comparisons each; 64 dominates
    # log2(MAX_INFERENCE_OBS) = 20 with room, and charging it as a product is the point.
    if not inference_product3_fits(max_iter, n, 64, MAX_IRLS_WORK):
        return _robust_failure(INF_ERR_DIMENSION_TOO_LARGE, n, p, tuning, 0, max_iter)
    for i in range(len(x)):
        if not inference_finite(x[i]):
            return _robust_failure(INF_ERR_NON_FINITE, n, p, tuning, 0, max_iter)
    for i in range(n):
        if not inference_finite(y[i]):
            return _robust_failure(INF_ERR_NON_FINITE, n, p, tuning, 0, max_iter)

    var beta = List[Float64](capacity=q)
    for _ in range(q):
        beta.append(0.0)
    var weights = List[Float64](capacity=n)
    for _ in range(n):
        weights.append(1.0)
    var scale = ROBUST_SCALE_ABSENT
    var converged = False
    var exact = False
    var iters = 0

    for _ in range(max_iter):
        iters += 1
        var a = List[Float64](capacity=q * q)
        for _ in range(q * q):
            a.append(0.0)
        var rhs = List[Float64](capacity=q)
        for _ in range(q):
            rhs.append(0.0)
        # Upper triangle only, then mirrored, so the matrix handed to `wls_solve_flat` is
        # EXACTLY symmetric and its symmetry test is checking the solve's input rather than
        # this loop's summation order.
        for i in range(n):
            var w = weights[i]
            for r in range(q):
                var xr = x[i * p + r] if r < p else 1.0
                rhs[r] += w * xr * y[i]
                for c in range(r, q):
                    var xc = x[i * p + c] if c < p else 1.0
                    a[r * q + c] += w * xr * xc
        for r in range(q):
            for c in range(r + 1, q):
                a[c * q + r] = a[r * q + c]

        var step = wls_solve_flat(a, rhs, q)
        if step.status != INF_OK:
            return _robust_failure(step.status, n, p, tuning, iters, max_iter)
        var all_small = True
        for j in range(q):
            if not inference_finite(step.beta[j]):
                return _robust_failure(INF_ERR_DIVERGED, n, p, tuning, iters, max_iter)
            var delta = step.beta[j] - beta[j]
            # Judged quantity: this coefficient's movement. Scale: its own magnitude.
            if fabs(delta) > inference_scaled_tol(step.beta[j], tol):
                all_small = False
            beta[j] = step.beta[j]

        var residuals = List[Float64](capacity=n)
        var max_abs: Float64 = 0.0
        for i in range(n):
            var fitted = beta[p]
            for j in range(p):
                fitted += x[i * p + j] * beta[j]
            var r = y[i] - fitted
            if not inference_finite(r):
                return _robust_failure(INF_ERR_DIVERGED, n, p, tuning, iters, max_iter)
            residuals.append(r)
            if fabs(r) > max_abs:
                max_abs = fabs(r)

        scale = robust_scale_mad(residuals, n)
        if scale < 0.0:
            return _robust_failure(INF_ERR_DEGENERATE, n, p, tuning, iters, max_iter)
        # A scale that is not distinguishable from zero AT THE RESIDUALS' OWN MAGNITUDE is
        # zero for every purpose it has. `scale == 0.0` alone is not enough: measured on
        # `y = 2x + 1` with only two distinct offsets, six of the ten residuals agree to
        # rounding, the MAD comes out as 1.45e-14 rather than 0.0, and every weight becomes
        # ~0.05 — the estimator then chases rounding noise for `max_iter` iterations and
        # reports `INF_ERR_NOT_CONVERGED` for what is really the MAD's breakdown point.
        #
        # This is NOT rule 4b's spelling 2. The scale is a single property of the WHOLE
        # residual vector, so the magnitude it is judged against is that vector's own
        # magnitude; spelling 2 is a PER-ITEM comparison scaled by an aggregate over other
        # items, which transfers one item's units onto another's test. Nothing is transferred
        # here because there is only one quantity.
        var scale_floor = inference_scaled_tol(max_abs, 0.0)
        if scale <= scale_floor:
            # Two opposite outcomes share one arithmetic symptom, so they are separated
            # rather than collapsed: every residual zero is an EXACT fit and an answer; a
            # tied half with the rest nonzero has no usable scale and is a refusal.
            if max_abs == 0.0:
                for i in range(n):
                    weights[i] = 1.0
                exact = True
                converged = True
                break
            return _robust_failure(INF_ERR_DEGENERATE, n, p, tuning, iters, max_iter)

        for i in range(n):
            var w = huber_weight(residuals[i], scale, tuning)
            if w < 0.0:
                return _robust_failure(INF_ERR_DEGENERATE, n, p, tuning, iters, max_iter)
            weights[i] = w
        if all_small:
            converged = True
            break

    if not converged:
        return _robust_failure(INF_ERR_NOT_CONVERGED, n, p, tuning, iters, max_iter)

    var n_down = 0
    var min_w: Float64 = 1.0
    for i in range(n):
        if weights[i] < 1.0:
            n_down += 1
        if weights[i] < min_w:
            min_w = weights[i]

    var max_abs_final: Float64 = 0.0
    var objective: Float64 = 0.0
    for i in range(n):
        var fitted = beta[p]
        for j in range(p):
            fitted += x[i * p + j] * beta[j]
        var r = y[i] - fitted
        var magnitude = fabs(r)
        if magnitude > max_abs_final:
            max_abs_final = magnitude
        if scale > 0.0:
            var u = magnitude / scale
            if u <= tuning:
                objective += 0.5 * u * u
            else:
                objective += tuning * (u - 0.5 * tuning)
    var coefficients = List[Float64](capacity=p)
    for j in range(p):
        coefficients.append(beta[j])
    return RobustFit(
        INF_OK, n, p, tuning, True, exact, iters, max_iter, beta[p],
        coefficients^, weights.copy(), scale, n_down, min_w, max_abs_final, objective,
    )
