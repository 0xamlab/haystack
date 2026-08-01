"""
survival_analysis.parametric — Weibull and lognormal MLE with right censoring.

What already exists, and what is missing
---------------------------------------
The frozen `reliability.mojo` EVALUATES a Weibull: `weibull_reliability(t, beta, eta)` and
`weibull_failure_rate(t, beta, eta)` both take the parameters as arguments. Nothing anywhere
FITS them. The gap is the estimator, and specifically the estimator with censoring: a
Weibull fitted by dropping the censored rows is biased toward short lives, and one that
treats censored rows as failures is biased the same way twice. Both are the standard
mistake in reliability practice.

`distribution_fit.mojo` fits distributions to COMPLETE samples and has no notion of a
censoring indicator, so it cannot be pointed at this problem either.

The frozen evaluators are called: the goodness-of-fit diagnostic compares the fitted
survival curve, computed by `reliability.weibull_reliability`, against the nonparametric
Kaplan-Meier curve, computed by `survival.kaplan_meier` through `base.sa_risk_table`. So
the number that judges the fit is produced by kernels that know nothing about the fitting
code.

Weibull: profile likelihood plus bisection, not Newton
------------------------------------------------------
With shape `k` and scale `eta`, the scale has a closed form given the shape:

    eta(k) = ( sum_i t_i^k / r )^(1/k)        r = number of EVENTS, sum over ALL observations

Substituting it leaves one equation in one unknown:

    g(k) = 1/k + (sum_events log t_i)/r - (sum_all t_i^k log t_i)/(sum_all t_i^k) = 0

`g` is strictly decreasing, `g(0+) = +inf` and `g(inf) < 0` unless every observation shares
one time. So BISECTION on a bracket is used rather than Newton: it cannot diverge, it needs
no second derivative, its iteration count is a pure function of the bracket and the
tolerance (so the result is reproducible to the bit for a given input), and a bracket that
fails to change sign is a DIAGNOSIS -- the likelihood has no interior maximum -- rather than
a silent wander. Newton on the same equation is faster and can leave the bracket.

Overflow is handled by shifting, not by hoping. `t_i^k` at `k = 1e4` overflows for any
`t > 1`, so every power is computed as `exp(k * (log t_i - max_j log t_j))`, which lies in
(0, 1], and the two sums that form the ratio are accumulated with the frozen
`numerical_stability.kahan_sum`. `log(sum t^k)` is recovered as `log(sum w) + k * max_log`.

Two identities are returned rather than trusted. `shape_equation_residual` is `g(k_hat)`,
which must be zero at the root, and `scale_identity_residual` is `sum (t_i/eta_hat)^k - r`,
which is zero for the profile scale by construction. Both are computed from the RETURNED
parameters, so a reader can check the fit without re-deriving it, and a defect in the
bisection shows up as a residual rather than as a plausible pair of numbers.

Lognormal: does the MLE EXIST? Asked FIRST, because often it does not
---------------------------------------------------------------------
A censored lognormal log-likelihood is UNBOUNDED ABOVE on ordinary industrial data, and an
iterative fit that does not test for this returns whatever its stopping rule happened to
reach. Measured, before this was fixed: `lognormal_mle([3, 3, 1], [1, 1, 0], 200, 1e-13)`
returned `status = ok`, `converged = true`, `sigma = 2.2e-08`, `loglik = +31.21` and
`AIC = -58.42`. The same data at `tol = 1e-4` returned `sigma = 8.1e-05`, `loglik = +14.81`,
`AIC = -25.63`. A 33-unit AIC swing produced by the tolerance alone, on a sample where the
supremum of the likelihood is `+infinity`: with `mu = log 3` and `sigma -> 0` the two density
terms at `t = 3` diverge while the censored term at `t = 1` tends to `log 1 = 0`. Verified
independently: `sigma = 1e-10` gives `+42.02`, `sigma = 1e-200` gives `+916.99`.

The condition is exact, and it is checked before the first EM step:

    every observed failure shares ONE recorded time y*, and no censored row is above y*

Then `mu = y*`, `sigma -> 0` sends `r * (-log sigma)` to `+infinity` with nothing opposing
it, so no maximiser exists and the answer is `SA_ERR_LIKELIHOOD_UNBOUNDED`, not a number.
Conversely, with two distinct failure times `y1 != y2` the sum of squared deviations is at
least `(y1 - y2)^2 / 2` for EVERY `mu`, so the failure part is bounded by
`-r log sigma - (y1 - y2)^2 / (4 sigma^2) -> -infinity`; the censored terms are `<= 0`;
`sigma -> infinity` and `|mu| -> infinity` both send the likelihood to `-infinity`. The
supremum is therefore attained and the MLE exists. And with all failures at `y*` but a
censored row ABOVE it, that row contributes `log(1 - Phi(z))` with `z -> +infinity`, which
falls like `-(delta^2)/(2 sigma^2)` and again dominates. So the refusal fires on exactly the
degenerate family and on nothing else. Its trigger is common: every observed failure sharing
one recorded time is what inspection-interval logging produces.

The sibling asymmetry this closes: `weibull_mle` on `[3, 3, 1], [1, 1, 0]` already refused,
through its no-sign-change bracket test. A caller comparing families saw Weibull refuse and
lognormal win with `AIC = -58`.

Lognormal: EM, because censoring has no closed form
---------------------------------------------------
For log-times `y_i = log t_i`, an uncensored sample gives `mu` and `sigma` in closed form.
With right censoring it does not, and the log-likelihood in `(mu, sigma)` is not concave, so
a raw Newton step can leave the parameter space (`sigma <= 0`). The EM algorithm for a
censored normal is used instead: the E-step replaces a censored `y_i` with its conditional
mean `E[Y | Y > y_i]` and conditional VARIANCE, the M-step is the closed-form normal update.
EM cannot decrease the observed-data log-likelihood, which gives a check with teeth --
`loglik_monotone` is computed, not assumed, and a decrease is a REFUSAL
(`SA_ERR_EM_NOT_MONOTONE`), not a flag on a returned fit.

The M-step is CENTERED, and that is not a style choice
------------------------------------------------------
The textbook M-step is `sigma^2 = m2 - mu^2` with `m2` the mean of `E[Y_i^2]`. That is the
canonical catastrophic cancellation, and it is what produced the numbers above: on
`[3, 3, 1]` the two terms are both 1.2069489608 and their true difference is ~1.6e-16, below
`DBL_EPSILON * mu^2 = 2.68e-16`. The returned `sigma^2 = 4.93e-16` was 1.84 ULP of `mu^2` --
quantisation residue -- and whether it landed positive (accepted) or `<= 0` (refused by the
guard on the next line) was a coin flip. In a package whose base module imports the frozen
`numerical_stability` kernels specifically to avoid this.

So the second moment is accumulated about `mu_new` instead, one observation at a time:

    E[(Y_i - mu_new)^2] = Var(Y_i | data) + (E[Y_i | data] - mu_new)^2

For a failure that is `(y_i - mu_new)^2`, one subtraction of comparable numbers. For a
censored row it is `sigma^2 * (1 + z*lambda - lambda^2) + (mu + sigma*lambda - mu_new)^2`,
where the first factor is the variance of a standard normal truncated below at `z`. No large
quantity is ever subtracted from another large quantity, the sum is non-negative term by
term, and it goes through the frozen `kahan_sum`. On a well-posed sample the two forms agree
to 6e-16, which is the point: this changes the degenerate answer and not the good one.

`1 + z*lambda - lambda^2` is itself a cancellation at large `z` (both middle terms are
`~z^2`), so above `SA_MILLS_ASYMPTOTIC_Z` its asymptotic series `w^2(1 - 6w^2 + 50w^4)`,
`w = 1/z`, is used instead. That series is 0.97% relative at the `z = 6` switch, measured
against a 60-digit evaluation, and improves as `z^-2` (0.18% at 8, 0.017% at 12). It is
tolerated at that width because at `z = 6` the term it multiplies is 0.024 `sigma^2` against
that same row's `(E[Y] - mu_new)^2` of ~38 `sigma^2`: a 1% error on 0.06% of one row's
contribution. Below the switch the direct form is exact to ~3e-13 relative and is used.

The inverse Mills ratio is where this goes wrong quietly. `lambda(z) = phi(z)/(1 - Phi(z))`
is `0/0` in floating point for `z` beyond about 8, and the frozen `math_ext.norm_cdf` is
built on `erf`, so `1 - Phi(z)` loses every significant digit well before that. For `z > 6`
the asymptotic expansion `lambda(z) ~ z + 1/z - 2/z^3 + 10/z^5` is used instead, which is
accurate to about 4e-5 relative at `z = 6` and improves rapidly. The switch is a documented
approximation at a stated accuracy; the alternative was a division by a number that had
already been rounded to zero.

Refusals
--------
* `SA_ERR_NONPOSITIVE_TIME` -- both families are supported on `t > 0` and both estimators
  take `log t`. A time of exactly 0 is legal for a Kaplan-Meier curve and is not legal here,
  which is why `base.sa_validate_observations` accepts it and these two functions do not.
* `SA_ERR_NO_EVENTS` -- with every observation censored there is no likelihood to maximise
  in the shape at all.
* `SA_ERR_NOT_CONVERGED` -- the bracket did not change sign (every observation at one time,
  so the Weibull shape MLE is at infinity), or the iteration limit was reached, or the EM
  update produced `sigma <= 0`. In every case the current iterate is not the MLE and is not
  returned as one.
* `SA_ERR_LIKELIHOOD_UNBOUNDED` -- lognormal only: the sample is in the degenerate family
  above and the supremum of the likelihood is `+infinity`. There is no estimate to return at
  any tolerance, so the refusal does not depend on one.
* `SA_ERR_EM_NOT_MONOTONE` -- the observed-data log-likelihood decreased across an EM step by
  more than that log-likelihood's own error budget. EM cannot do that, so it is a defect in
  this code and it is surfaced as a refusal rather than as a `false` on a returned fit.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_survival_analysis_parametric.mojo
benchmark: benchmarks/mojo_benchmarks/bench_survival_analysis.mojo
docs: gitbook/engine/survival-analysis.md
version_introduced: 0.7.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs
from std.math import exp, log, sqrt

from math_ext import norm_cdf, norm_pdf
from numerical_stability import kahan_sum
from reliability import weibull_reliability

from survival_analysis.base import (
    SA_DBL_EPSILON,
    SA_ERR_BAD_ITER,
    SA_ERR_BAD_TOL,
    SA_ERR_EM_NOT_MONOTONE,
    SA_ERR_LIKELIHOOD_UNBOUNDED,
    SA_ERR_NONPOSITIVE_TIME,
    SA_ERR_NOT_CONVERGED,
    SA_ERR_NO_EVENTS,
    SA_ERR_WORK_BUDGET,
    SA_MAX_WORK,
    SA_OK,
    sa_is_finite,
    sa_risk_table,
    sa_validate_observations,
    sa_work_fits,
)

# The iteration ceiling for both estimators in this file (Weibull bisection steps, lognormal
# EM steps). Declared HERE, as a literal, rather than imported from `base`: the capability
# gate resolves a `dim max_iter <= NAME` ceiling only against a
# `comptime NAME: Int = <literal>` in the same file, so the imported name left both
# declarations unresolvable and the stated ceiling unchecked. `COX_MAX_ITER` is the same
# number in `cox.mojo`, and `test_survival_analysis_cox.mojo` asserts the two are equal --
# without that assertion two literals in two files are a drift waiting to happen.
comptime PAR_MAX_ITER: Int = 500
# The bisection bracket for the Weibull shape. A shape below 1e-4 means a hazard that falls
# faster than any physical wear-in model, and above 1e4 the distribution is a point mass; a
# root outside this range is reported as "no interior maximum" rather than chased.
comptime SA_WEIBULL_SHAPE_MIN: Float64 = 1e-4
comptime SA_WEIBULL_SHAPE_MAX: Float64 = 1e4
# Above this z the inverse Mills ratio switches to its asymptotic expansion, because
# `1 - norm_cdf(z)` has by then lost most of its significant digits to cancellation.
comptime SA_MILLS_ASYMPTOTIC_Z: Float64 = 6.0
comptime SA_LOG_TWO_PI: Float64 = 1.8378770664093456
# The relative accuracy floor of the transcendental kernels this log-likelihood is built from.
# `std.math.log` in this tree is ~1e-10 off correctly-rounded and `erf` ~2e-8, so a sum of
# terms containing them cannot be judged against DBL_EPSILON: it does not have DBL_EPSILON
# accuracy to begin with. Measured over 4000 deterministic cases (six time generators, n in
# [1, 9]), the largest log-likelihood DECREASE across an EM step -- which EM theory forbids and
# floating point produces anyway -- was 7.18e-13, roughly 100x the IEEE rounding of the sum
# itself. Against `abs_scale` values of 3 to 20 this floor puts the line at 3e-10 to 2e-9:
# two to three orders above the measured noise, and six orders below the 1e-3-and-larger
# decrease a genuine M-step defect produces. Both ends of that gap are stated because a
# threshold with only one end measured is a tuning knob.
comptime SA_TRANSCENDENTAL_REL_FLOOR: Float64 = 1e-10


fn _mills_ratio(z: Float64) -> Float64:
    """`phi(z) / (1 - Phi(z))`, the inverse Mills ratio, without dividing by a rounded zero.

    Below `SA_MILLS_ASYMPTOTIC_Z` the frozen `math_ext.norm_pdf` / `norm_cdf` pair is used
    directly. Above it, `1 - Phi(z)` is the difference of two nearly equal numbers and the
    asymptotic series is both faster and more accurate. Returns 0.0 for a non-finite input,
    which the callers check for separately.
    """
    if not sa_is_finite(z):
        return 0.0
    if z > SA_MILLS_ASYMPTOTIC_Z:
        var zi = 1.0 / z
        var z2 = zi * zi
        return z * (1.0 + z2 * (1.0 - 2.0 * z2 + 10.0 * z2 * z2))
    var tail = 1.0 - norm_cdf(z)
    if tail <= 0.0 or not sa_is_finite(tail):
        var zi2 = 1.0 / z if z > 0.0 else 0.0
        return z + zi2
    var value = norm_pdf(z) / tail
    if not sa_is_finite(value) or value < 0.0:
        return 0.0
    return value


fn _truncated_variance_factor(z: Float64, lam: Float64) -> Float64:
    """`Var(Z | Z > z) = 1 + z*lambda - lambda^2` for a standard normal, without cancellation.

    The direct form subtracts two quantities that are both `~z^2` for large `z` to produce a
    result that is `~1/z^2`, so it loses all significance well before the numbers get large:
    at `z = 1e7` the two terms are `1e14` and the true answer is `1e-14`, which the
    subtraction cannot represent and can return NEGATIVE -- a negative variance, which would
    then either refuse a valid fit or corrupt one. Above `SA_MILLS_ASYMPTOTIC_Z` the
    asymptotic series `w^2 (1 - 6 w^2 + 50 w^4)` with `w = 1/z` is used instead; see the
    module docstring for its measured accuracy at the switch and why that width is tolerable.

    The result is a variance of a distribution supported on a half-line inside a unit-variance
    parent, so it lies in (0, 1]; a value outside is clamped, because the alternative is
    propagating a negative variance into `sqrt`.
    """
    if not sa_is_finite(z) or not sa_is_finite(lam):
        return 0.0
    var value: Float64
    if z > SA_MILLS_ASYMPTOTIC_Z:
        var w2 = 1.0 / (z * z)
        value = w2 * (1.0 - 6.0 * w2 + 50.0 * w2 * w2)
    else:
        value = 1.0 + z * lam - lam * lam
    if not sa_is_finite(value) or value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


fn _log_upper_tail(z: Float64) -> Float64:
    """`log(1 - Phi(z))`, via `log phi(z) - log lambda(z)` above the cancellation threshold."""
    if z > SA_MILLS_ASYMPTOTIC_Z:
        var lam = _mills_ratio(z)
        if lam <= 0.0:
            return -1e300
        return -0.5 * z * z - 0.5 * SA_LOG_TWO_PI - log(lam)
    var tail = 1.0 - norm_cdf(z)
    if tail <= 0.0:
        return -1e300
    return log(tail)


struct WeibullFit(Copyable, Movable):
    """A right-censored Weibull MLE, or a refusal.

    `shape` is the Weibull `beta` and `scale` the Weibull `eta` in the frozen
    `reliability.weibull_reliability(t, beta, eta)` parameterisation, so the fitted curve can
    be evaluated with that kernel directly.

    `shape_equation_residual` and `scale_identity_residual` are the two defining equations
    evaluated at the RETURNED parameters; both are zero at the MLE. `ks_distance_vs_km` is
    the largest absolute gap between the fitted survival curve and the nonparametric
    Kaplan-Meier curve over the event times -- a goodness-of-fit distance, not a p-value, and
    `has_ks` is False when there were no event times to compare on.
    """

    var status: Int
    var n_obs: Int
    var n_events: Int
    var n_censored: Int
    var iterations: Int
    var converged: Bool
    var shape: Float64
    var scale: Float64
    var loglik: Float64
    var aic: Float64
    var shape_equation_residual: Float64
    var scale_identity_residual: Float64
    var bracket_width: Float64
    var ks_distance_vs_km: Float64
    var has_ks: Bool

    fn __init__(out self, status: Int):
        self.status = status
        self.n_obs = 0
        self.n_events = 0
        self.n_censored = 0
        self.iterations = 0
        self.converged = False
        self.shape = 0.0
        self.scale = 0.0
        self.loglik = 0.0
        self.aic = 0.0
        self.shape_equation_residual = 0.0
        self.scale_identity_residual = 0.0
        self.bracket_width = 0.0
        self.ks_distance_vs_km = 0.0
        self.has_ks = False


fn _weibull_g(logt: List[Float64], max_log: Float64, mean_event_log: Float64, k: Float64) -> Float64:
    """`g(k) = 1/k + mean_event_log - (sum w_i l_i)/(sum w_i)` with `w_i = exp(k(l_i - max))`.

    The shift keeps every weight in (0, 1], so no power overflows for any `k` in the bracket,
    and the ratio is unchanged by it. Both sums go through the frozen `kahan_sum`.
    """
    var w = List[Float64]()
    var wl = List[Float64]()
    for i in range(len(logt)):
        var wi = exp(k * (logt[i] - max_log))
        w.append(wi)
        wl.append(wi * logt[i])
    var sw = kahan_sum(w)
    var swl = kahan_sum(wl)
    if sw <= 0.0 or not sa_is_finite(sw) or not sa_is_finite(swl):
        return 0.0
    return 1.0 / k + mean_event_log - swl / sw


fn weibull_mle(
    times: List[Float64], event: List[Int], max_iter: Int, tol: Float64
) -> WeibullFit:
    """Weibull shape and scale by maximum likelihood with right-censored observations.

    `event[i]` is 1 for an observed failure and 0 for a right-censored observation;
    `len(event) == len(times)` is required exactly (`SA_ERR_CENSOR_LENGTH`). Every time must
    be strictly positive.

    `max_iter` bisection steps are performed at most, each costing O(n); the product is
    charged against `SA_MAX_WORK`, because `max_iter` and `n` are independent and bounding
    both individually does not bound the loop.

    @capability weibull_mle
    complexity: O(n log n + max_iter * n)
    counts:
    - dim max_iter <= PAR_MAX_ITER [kernel_validated]
    @endcapability
    """
    var status = sa_validate_observations(times, event)
    if status != SA_OK:
        return WeibullFit(status)
    if max_iter < 1 or max_iter > PAR_MAX_ITER:
        return WeibullFit(SA_ERR_BAD_ITER)
    if not sa_is_finite(tol) or tol <= 0.0 or tol > 1.0:
        return WeibullFit(SA_ERR_BAD_TOL)

    var n = len(times)
    var factors = List[Int]()
    factors.append(max_iter)
    factors.append(n)
    if not sa_work_fits(factors, SA_MAX_WORK):
        return WeibullFit(SA_ERR_WORK_BUDGET)

    for i in range(n):
        if times[i] <= 0.0:
            return WeibullFit(SA_ERR_NONPOSITIVE_TIME)

    var logt = List[Float64]()
    var event_logs = List[Float64]()
    var max_log: Float64 = -1e300
    for i in range(n):
        var l = log(times[i])
        if not sa_is_finite(l):
            return WeibullFit(SA_ERR_NONPOSITIVE_TIME)
        logt.append(l)
        if l > max_log:
            max_log = l
        if event[i] == 1:
            event_logs.append(l)
    var r = len(event_logs)
    if r == 0:
        return WeibullFit(SA_ERR_NO_EVENTS)
    var mean_event_log = kahan_sum(event_logs) / Float64(r)

    var lo = SA_WEIBULL_SHAPE_MIN
    var hi = SA_WEIBULL_SHAPE_MAX
    var g_lo = _weibull_g(logt, max_log, mean_event_log, lo)
    var g_hi = _weibull_g(logt, max_log, mean_event_log, hi)
    if not sa_is_finite(g_lo) or not sa_is_finite(g_hi) or g_lo <= 0.0 or g_hi >= 0.0:
        # No sign change: the profile score never crosses zero inside the bracket, which is
        # what a degenerate sample (all observations at one time) looks like. The shape MLE
        # is at a boundary, so there is no interior estimate to return.
        return WeibullFit(SA_ERR_NOT_CONVERGED)

    var iterations = 0
    var converged = False
    for _it in range(max_iter):
        iterations += 1
        var mid = 0.5 * (lo + hi)
        var g_mid = _weibull_g(logt, max_log, mean_event_log, mid)
        if not sa_is_finite(g_mid):
            return WeibullFit(SA_ERR_NOT_CONVERGED)
        if g_mid > 0.0:
            lo = mid
        else:
            hi = mid
        # The quantity judged is the bracket width around a shape of magnitude `lo`, so the
        # tolerance is the caller's ABSOLUTE tol plus machine epsilon scaled by that shape.
        if hi - lo <= tol + SA_DBL_EPSILON * lo:
            converged = True
            break
    if not converged:
        return WeibullFit(SA_ERR_NOT_CONVERGED)

    var k = 0.5 * (lo + hi)
    var w = List[Float64]()
    for i in range(n):
        w.append(exp(k * (logt[i] - max_log)))
    var sw = kahan_sum(w)
    if sw <= 0.0 or not sa_is_finite(sw):
        return WeibullFit(SA_ERR_NOT_CONVERGED)
    var log_eta = (log(sw) + k * max_log - log(Float64(r))) / k
    if not sa_is_finite(log_eta):
        return WeibullFit(SA_ERR_NOT_CONVERGED)
    var eta = exp(log_eta)
    if not sa_is_finite(eta) or eta <= 0.0:
        return WeibullFit(SA_ERR_NOT_CONVERGED)

    var out = WeibullFit(SA_OK)
    out.n_obs = n
    out.n_events = r
    out.n_censored = n - r
    out.iterations = iterations
    out.converged = True
    out.shape = k
    out.scale = eta
    out.bracket_width = hi - lo
    out.shape_equation_residual = _weibull_g(logt, max_log, mean_event_log, k)

    var powers = List[Float64]()
    var terms = List[Float64]()
    for i in range(n):
        var p = exp(k * (logt[i] - log_eta))
        powers.append(p)
        if event[i] == 1:
            terms.append(log(k) - log_eta + (k - 1.0) * (logt[i] - log_eta))
    var sum_pow = kahan_sum(powers)
    out.scale_identity_residual = sum_pow - Float64(r)
    var ll = kahan_sum(terms) - sum_pow
    if sa_is_finite(ll):
        out.loglik = ll
        out.aic = 4.0 - 2.0 * ll

    var table = sa_risk_table(times, event)
    if table.status == SA_OK and table.n_event_times > 0:
        var worst: Float64 = 0.0
        for j in range(table.n_event_times):
            var fitted = weibull_reliability(table.time[j], k, eta)
            if not sa_is_finite(fitted):
                continue
            var gap = fabs(table.survival[j] - fitted)
            if gap > worst:
                worst = gap
        if sa_is_finite(worst):
            out.ks_distance_vs_km = worst
            out.has_ks = True
    return out^


struct LognormalFit(Copyable, Movable):
    """A right-censored lognormal MLE, or a refusal.

    `mu` and `sigma` are the mean and standard deviation of `log(t)`, so the fitted survival
    is `1 - Phi((log t - mu)/sigma)`.

    `loglik_monotone` records that the observed-data log-likelihood never decreased across
    EM iterations. That is a theorem about EM, so a False is a defect report, not a tuning
    knob -- and it is therefore a REFUSAL (`SA_ERR_EM_NOT_MONOTONE`) rather than a flag on a
    returned fit. On an `SA_OK` fit this field is always True; a caller may assert it.

    `status != SA_OK` means every numeric field is at its default and none of them is an
    estimate. In particular `sigma = 0.0` on a refusal is the default, never a fitted scale.
    """

    var status: Int
    var n_obs: Int
    var n_events: Int
    var n_censored: Int
    var iterations: Int
    var converged: Bool
    var loglik_monotone: Bool
    var mu: Float64
    var sigma: Float64
    var loglik: Float64
    var aic: Float64
    var loglik_worst_decrease: Float64
    var loglik_decrease_budget: Float64
    var ks_distance_vs_km: Float64
    var has_ks: Bool

    fn __init__(out self, status: Int):
        self.status = status
        self.n_obs = 0
        self.n_events = 0
        self.n_censored = 0
        self.iterations = 0
        self.converged = False
        self.loglik_monotone = False
        self.mu = 0.0
        self.sigma = 0.0
        self.loglik = 0.0
        self.aic = 0.0
        self.loglik_worst_decrease = 0.0
        self.loglik_decrease_budget = 0.0
        self.ks_distance_vs_km = 0.0
        self.has_ks = False


fn _lognormal_loglik(
    logt: List[Float64], event: List[Int], mu: Float64, sigma: Float64
) -> List[Float64]:
    """Observed-data log-likelihood of the censored lognormal. Returns [value, ok, abs_scale].

    `abs_scale` is `sum |term_i|`, and it is returned because the VALUE's magnitude is not its
    own error scale. The terms have mixed signs -- a density term at a well-fitted point is
    positive, a tail term is negative -- so the sum can be an order of magnitude smaller than
    the terms that built it. Judging a change in this quantity against `DBL_EPSILON * |value|`
    then under-budgets it by exactly that ratio, which is measurably what happened: on a
    4-observation sample the log-likelihood was 0.0699 while the terms summed to ~8 in absolute
    value, and the observed rounding wobble near the EM fixed point was 6.4e-16 -- ten times
    `n * DBL_EPSILON * |value|` and a thousandth of `n * DBL_EPSILON * abs_scale`.
    """
    var out = List[Float64]()
    if sigma <= 0.0 or not sa_is_finite(sigma) or not sa_is_finite(mu):
        out.append(0.0)
        out.append(0.0)
        out.append(0.0)
        return out^
    var terms = List[Float64]()
    var scale: Float64 = 0.0
    for i in range(len(logt)):
        var z = (logt[i] - mu) / sigma
        if not sa_is_finite(z):
            out.append(0.0)
            out.append(0.0)
            out.append(0.0)
            return out^
        var term: Float64
        if event[i] == 1:
            term = -logt[i] - log(sigma) - 0.5 * SA_LOG_TWO_PI - 0.5 * z * z
        else:
            term = _log_upper_tail(z)
        terms.append(term)
        scale += fabs(term)
    var value = kahan_sum(terms)
    if not sa_is_finite(value) or not sa_is_finite(scale):
        out.append(0.0)
        out.append(0.0)
        out.append(0.0)
        return out^
    out.append(value)
    out.append(1.0)
    out.append(scale)
    return out^


fn lognormal_mle(
    times: List[Float64], event: List[Int], max_iter: Int, tol: Float64
) -> LognormalFit:
    """Lognormal `mu`, `sigma` by EM with right-censored observations.

    `event[i]` is 1 for an observed failure and 0 for a right-censored observation; every
    time must be strictly positive. With no censored rows the first EM step already lands on
    the exact closed-form estimates `mean(log t)` and `sqrt(mean((log t - mu)^2))`, so the
    uncensored case is not a special path -- it is the general one with an empty E-step.

    EXISTENCE IS CHECKED FIRST. If every observed failure shares one recorded time and no
    censored row lies above it, the likelihood has no maximum -- its supremum is `+infinity`
    at `sigma -> 0` -- and the answer is `SA_ERR_LIKELIHOOD_UNBOUNDED` at every tolerance.
    Returning the iterate a stopping rule happened to reach there is not an estimate; it is
    the stopping rule. See the module docstring for the measured 33-unit AIC swing that came
    of doing so, and for the proof that the test fires on exactly this family.

    @capability lognormal_mle
    complexity: O(n log n + max_iter * n)
    counts:
    - dim max_iter <= PAR_MAX_ITER [kernel_validated]
    @endcapability
    """
    var status = sa_validate_observations(times, event)
    if status != SA_OK:
        return LognormalFit(status)
    if max_iter < 1 or max_iter > PAR_MAX_ITER:
        return LognormalFit(SA_ERR_BAD_ITER)
    if not sa_is_finite(tol) or tol <= 0.0 or tol > 1.0:
        return LognormalFit(SA_ERR_BAD_TOL)

    var n = len(times)
    var factors = List[Int]()
    factors.append(max_iter)
    factors.append(n)
    if not sa_work_fits(factors, SA_MAX_WORK):
        return LognormalFit(SA_ERR_WORK_BUDGET)

    for i in range(n):
        if times[i] <= 0.0:
            return LognormalFit(SA_ERR_NONPOSITIVE_TIME)

    var logt = List[Float64]()
    var n_events = 0
    for i in range(n):
        var l = log(times[i])
        if not sa_is_finite(l):
            return LognormalFit(SA_ERR_NONPOSITIVE_TIME)
        logt.append(l)
        if event[i] == 1:
            n_events += 1
    if n_events == 0:
        return LognormalFit(SA_ERR_NO_EVENTS)

    # Existence, before any iteration. Exact equality is the right test and not a tolerance:
    # two failures at 3.0 and 3.0000000001 have a finite MLE with a small sigma, and that IS
    # the answer for that sample. It is the exactly-tied family whose supremum is infinite.
    var min_event_log = logt[0]
    var max_event_log = logt[0]
    var seen_event = False
    for i in range(n):
        if event[i] != 1:
            continue
        if not seen_event:
            min_event_log = logt[i]
            max_event_log = logt[i]
            seen_event = True
            continue
        if logt[i] < min_event_log:
            min_event_log = logt[i]
        if logt[i] > max_event_log:
            max_event_log = logt[i]
    if seen_event and min_event_log == max_event_log:
        var censored_above = False
        for i in range(n):
            if event[i] != 1 and logt[i] > max_event_log:
                censored_above = True
                break
        if not censored_above:
            return LognormalFit(SA_ERR_LIKELIHOOD_UNBOUNDED)

    var mu = kahan_sum(logt) / Float64(n)
    var sq = List[Float64]()
    for i in range(n):
        var d = logt[i] - mu
        sq.append(d * d)
    var var0 = kahan_sum(sq) / Float64(n)
    if var0 <= 0.0:
        # Every log-time identical: the scale is zero and the density is a point mass.
        return LognormalFit(SA_ERR_NOT_CONVERGED)
    var sigma = sqrt(var0)

    var prev = _lognormal_loglik(logt, event, mu, sigma)
    if prev[1] != 1.0:
        return LognormalFit(SA_ERR_NOT_CONVERGED)
    var current_ll = prev[0]
    var monotone = True
    var worst_decrease: Float64 = 0.0
    var last_budget: Float64 = 0.0
    var converged = False
    var iterations = 0

    for _it in range(max_iter):
        iterations += 1
        # E-step. `expected[i]` is E[Y_i | data] and `within[i]` is Var(Y_i | data), which is
        # zero for an observed failure. Storing the conditional VARIANCE rather than the
        # conditional second moment is what keeps the M-step free of cancellation: the second
        # moment is `~mu^2` and so is `mu_new^2`, and their difference is the answer.
        var expected = List[Float64]()
        var within = List[Float64]()
        for i in range(n):
            if event[i] == 1:
                expected.append(logt[i])
                within.append(0.0)
                continue
            var z = (logt[i] - mu) / sigma
            var lam = _mills_ratio(z)
            if not sa_is_finite(lam) or lam < 0.0:
                return LognormalFit(SA_ERR_NOT_CONVERGED)
            var e1 = mu + sigma * lam
            var v1 = sigma * sigma * _truncated_variance_factor(z, lam)
            if not sa_is_finite(e1) or not sa_is_finite(v1) or v1 < 0.0:
                return LognormalFit(SA_ERR_NOT_CONVERGED)
            expected.append(e1)
            within.append(v1)
        var mu_new = kahan_sum(expected) / Float64(n)
        if not sa_is_finite(mu_new):
            return LognormalFit(SA_ERR_NOT_CONVERGED)
        # M-step, centered on mu_new: sum of Var(Y_i) + (E[Y_i] - mu_new)^2, every term
        # non-negative, no large-minus-large anywhere.
        var centered = List[Float64]()
        for i in range(n):
            var dm = expected[i] - mu_new
            var term = within[i] + dm * dm
            if not sa_is_finite(term) or term < 0.0:
                return LognormalFit(SA_ERR_NOT_CONVERGED)
            centered.append(term)
        var var_new = kahan_sum(centered) / Float64(n)
        if not sa_is_finite(var_new) or var_new <= 0.0:
            return LognormalFit(SA_ERR_NOT_CONVERGED)
        var sigma_new = sqrt(var_new)

        var evaluated = _lognormal_loglik(logt, event, mu_new, sigma_new)
        if evaluated[1] != 1.0:
            return LognormalFit(SA_ERR_NOT_CONVERGED)
        # The judged quantity is a sum of log-density terms of MIXED SIGN, so its own error
        # budget is set by the magnitudes that BUILT it -- `sum |term_i|`, returned as
        # `evaluated[2]` -- and not by `|sum|`, which cancellation can make arbitrarily
        # smaller. Measured: a 4-observation sample whose log-likelihood was 0.0699 had terms
        # summing to ~8 in absolute value, so `|sum|` under-budgeted its own error 100-fold.
        # And the per-unit floor is the TRANSCENDENTAL one, not DBL_EPSILON, because every
        # term passes through `log` or `erf`; see SA_TRANSCENDENTAL_REL_FLOOR for the measured
        # noise this covers and the defect size it still catches.
        #
        # NOT the caller's `tol`, which is a statement about the PARAMETERS: with `tol = 1e-6`
        # in the slop, a 1e-6 drop in the log-likelihood -- an EM failure by a wide margin --
        # passed as rounding. The budget here does not mention `tol` at all, which is why the
        # accept/refuse verdict no longer moves when the caller changes it.
        var ll_tol = SA_TRANSCENDENTAL_REL_FLOOR * evaluated[2] + SA_DBL_EPSILON
        last_budget = ll_tol
        var decrease = current_ll - evaluated[0]
        if sa_is_finite(decrease) and decrease > worst_decrease:
            worst_decrease = decrease
        if evaluated[0] < current_ll - ll_tol:
            monotone = False

        # Per-PARAMETER: the caller's absolute tolerance plus machine epsilon scaled by that
        # parameter's own magnitude. Not by the other parameter, and not by the sample size.
        var moved_mu = fabs(mu_new - mu) > tol + SA_DBL_EPSILON * fabs(mu_new)
        var moved_sigma = fabs(sigma_new - sigma) > tol + SA_DBL_EPSILON * fabs(sigma_new)
        mu = mu_new
        sigma = sigma_new
        current_ll = evaluated[0]
        if not moved_mu and not moved_sigma:
            converged = True
            break

    if not converged:
        return LognormalFit(SA_ERR_NOT_CONVERGED)
    if not monotone:
        # EM cannot decrease the observed-data log-likelihood. A decrease past that
        # log-likelihood's own error budget is a defect, so no parameter is returned that
        # could be read as an estimate -- but the two DIAGNOSTIC fields are filled, because a
        # refusal a caller cannot size up is a refusal they will work around by guessing.
        var bad = LognormalFit(SA_ERR_EM_NOT_MONOTONE)
        bad.n_obs = n
        bad.n_events = n_events
        bad.n_censored = n - n_events
        bad.iterations = iterations
        bad.loglik_worst_decrease = worst_decrease
        bad.loglik_decrease_budget = last_budget
        return bad^

    var out = LognormalFit(SA_OK)
    out.n_obs = n
    out.n_events = n_events
    out.n_censored = n - n_events
    out.iterations = iterations
    out.converged = True
    out.loglik_monotone = monotone
    out.mu = mu
    out.sigma = sigma
    out.loglik = current_ll
    out.aic = 4.0 - 2.0 * current_ll
    out.loglik_worst_decrease = worst_decrease
    out.loglik_decrease_budget = last_budget

    var table = sa_risk_table(times, event)
    if table.status == SA_OK and table.n_event_times > 0:
        var worst: Float64 = 0.0
        for j in range(table.n_event_times):
            var t = table.time[j]
            if t <= 0.0:
                continue
            var z = (log(t) - mu) / sigma
            var fitted = 1.0 - norm_cdf(z)
            if not sa_is_finite(fitted):
                continue
            var gap = fabs(table.survival[j] - fitted)
            if gap > worst:
                worst = gap
        if sa_is_finite(worst):
            out.ks_distance_vs_km = worst
            out.has_ks = True
    return out^
