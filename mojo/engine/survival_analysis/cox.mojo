"""
survival_analysis.cox — Cox proportional-hazards fit, with the refusals it needs.

Nothing in the tree fitted a Cox model. `survival.mojo` estimates curves and a two-group
log-rank statistic; neither answers "what does one unit of this covariate do to the
hazard, holding the others fixed". That is the whole reason a proportional-hazards model
exists, so this is a genuinely absent capability rather than an unreached one.

Efron, and why not Breslow
--------------------------
Ties in the event times are not a rounding nuisance -- they change the estimator. Two
approximations to the exact partial likelihood are in circulation:

* Breslow uses the FULL risk-set denominator once per tied event. With `d` events tied at
  one time, all `d` contributions share the same denominator, which over-counts the
  subjects who have already failed within the group.
* Efron replaces the denominator for the `l`-th of `d` tied events with
  `S0 - (l/d) * s0`, where `s0` is the sum over the tied events themselves -- the expected
  denominator if the `d` failures had occurred in some unknown order.

Efron is used here for the partial likelihood. It is materially closer to the exact
conditional likelihood when ties are heavy, it costs the same asymptotic work, and it is
what R's `coxph` uses by default -- so a coefficient from this kernel is comparable to the
number a user already has. Breslow is what the BASELINE cumulative hazard uses
(`cox_baseline_cumhaz`), where it is the standard estimator and the Efron correction
changes the result by O(d^2 / n) per tie group; the choice is named in the field docs
rather than left to be inferred.

One honest limitation of Efron, stated because it looks like a bug: a tie group containing
EVERY remaining subject still contributes curvature to the information matrix, so a
dataset where all subjects fail at one time returns `beta ~ 0` with a finite standard
error rather than a refusal. There is no ordering information in such a sample. This
matches `coxph`, which is why it is documented rather than special-cased -- a kernel that
silently disagreed with the reference implementation on a degenerate input would be worse.

Cost is O(n * p^2) per iteration, not O(n_events * n * p^2)
----------------------------------------------------------
The textbook form re-sums the risk set at every event time, which is O(n_events * n) and
turns a 200k-row fit into minutes. Here the observations are walked ONCE in descending
time order and `S0`, `S1` and `S2` accumulate as the risk set grows, so one Newton
iteration is a single pass. That is what makes the benchmark's per-row cost flat in `n`
instead of linear in it, and bounding memory would not have caught the difference:
`max_iter * n_rows * n_cols^2` is charged against `SA_MAX_WORK` explicitly.

Refusing instead of returning a coefficient
-------------------------------------------
A Cox fit has several ways to have no answer, and every one of them yields a
plausible-looking number if it is not checked:

* `SA_ERR_NO_EVENTS` -- the partial likelihood is a constant. Every beta is equally good,
  so any returned beta is arbitrary.
* `SA_ERR_NO_COVARIATE_VARIATION` -- a constant column contributes the same factor to
  numerator and denominator at every risk set, so its coefficient is not identified. The
  likelihood is exactly flat in that direction and the information matrix is exactly
  singular. Detected with the frozen `numerical_stability.welford_mean_var` before any
  iteration runs, so the message names the cause rather than the symptom.
* `SA_ERR_SINGULAR_INFORMATION` -- the observed information is not positive definite, so
  there is no Newton step and no standard error. Checked with the frozen
  `linalg_ext.mat_is_positive_definite`, which attempts a Cholesky, BEFORE calling the
  frozen `linalg.mat_solve` -- because `mat_solve` returns an all-zeros vector for a
  singular system, and a zero Newton step is indistinguishable from convergence.
* `SA_ERR_SEPARATION` -- a covariate that perfectly orders the failures drives the MLE to
  +/- infinity. The iterates diverge, and the log-likelihood keeps improving, so a naive
  loop "converges" at whatever iterate the tolerance happened to accept.
  `|beta_k| > SA_COX_BETA_LIMIT` (30, a hazard ratio of 1e13) is treated as divergence.
* `SA_ERR_NOT_CONVERGED` -- the iteration limit was reached. The current iterate is not
  the MLE and is not returned as one.

Centering is exact, not a convenience
-------------------------------------
Every column is centered on its own mean before any exponential is formed. The Cox partial
likelihood is invariant to a constant shift of a covariate -- the shift contributes
`exp(beta * c)` to the numerator and to every risk-set term, and cancels exactly -- so
`beta` is unchanged, while `exp(eta)` stops overflowing on covariates whose natural units
are large. The means are returned so a caller can reconstruct the raw linear predictor.
Overflow is still checked rather than assumed away: `|eta| > 300` and any non-finite
accumulator are refused as divergence.

Tolerance
---------
Convergence is judged on the log-likelihood change against
`tol + DBL_EPSILON * |loglik|` -- the caller's ABSOLUTE tolerance plus machine epsilon
scaled by the magnitude of THAT quantity. Not by a sum over rows, not by the largest
covariate, and not `caller_tol * |loglik|`, which would silently loosen the test by
fourteen orders of magnitude on a large sample.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_survival_analysis_cox.mojo
benchmark: benchmarks/mojo_benchmarks/bench_survival_analysis.mojo
docs: gitbook/engine/survival-analysis.md
version_introduced: 0.7.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs
from std.math import exp, log, sqrt

from linalg import Matrix, mat_inv, mat_solve
from linalg_ext import mat_is_positive_definite
from numerical_stability import welford_mean_var
from sparse_numerics.csr import dims_fit

from survival_analysis.base import (
    SA_DBL_EPSILON,
    SA_ERR_BAD_ITER,
    SA_ERR_BAD_TOL,
    SA_ERR_NON_FINITE_COVARIATE,
    SA_ERR_NO_COVARIATE_VARIATION,
    SA_ERR_NO_EVENTS,
    SA_ERR_NOT_CONVERGED,
    SA_ERR_SEPARATION,
    SA_ERR_SHAPE,
    SA_ERR_SINGULAR_INFORMATION,
    SA_ERR_TOO_MANY_COVARIATES,
    SA_ERR_WORK_BUDGET,
    SA_MAX_COVARIATES,
    SA_MAX_WORK,
    SA_OK,
    sa_is_finite,
    sa_sort_observations,
    sa_work_fits,
)

# The Newton iteration ceiling. Declared HERE, as a literal, rather than imported from
# `base`: the capability gate resolves a `dim max_iter <= NAME` ceiling only against a
# `comptime NAME: Int = <literal>` in the same file, so the imported name left the
# declaration in `cox_fit` unresolvable and the stated ceiling unchecked. The package still
# presents ONE iteration ceiling to callers -- `test_survival_analysis_cox.mojo` asserts
# `COX_MAX_ITER == PAR_MAX_ITER`, and that assertion is the only thing standing between two
# literals and a drift.
comptime COX_MAX_ITER: Int = 500
# The largest |beta| treated as an estimate rather than divergence. exp(30) is 1.07e13:
# a hazard ratio no finite sample supports, and the scale at which the information matrix
# underflows toward singular. Beyond it the answer is "the MLE is at infinity", which is a
# refusal, not a number.
comptime SA_COX_BETA_LIMIT: Float64 = 30.0
# The largest |eta| for which exp(eta) can be summed over SA_MAX_OBS rows and stay finite
# with room for the second-moment accumulator. exp(300) is 1.9e130.
comptime SA_COX_ETA_LIMIT: Float64 = 300.0
# Step halvings per Newton iteration before the step is abandoned. Each halving costs one
# O(n * p) log-likelihood evaluation, so this factor is charged against the work budget.
comptime SA_COX_MAX_HALVINGS: Int = 12
# "The likelihood is flat" made measurable: the trace of the observed information at the
# current iterate, divided by its value at beta = 0. A finite MLE leaves the curvature the
# same order of magnitude as the null model's (0.65 vs 0.72 on the closed-form case in the
# suite). A separating covariate drives it to zero exponentially -- 8e-11 against a null of
# 0.25 by |beta| = 23 -- so a millionth is far outside anything a finite optimum produces
# and far inside where a diverging one has already gone. It is a ratio of the SAME quantity
# at two points, so it carries no units and no other item's scale.
#
# Measured, and the reason this test exists rather than only the |beta| ceiling: with a
# log-likelihood-only convergence test and `tol = 1e-10`, the separating case
# `x = [0, 1], t = [1, 2], event = [1, 1]` reached an improvement of 5.3e-11 at
# `beta = -24.2` and would have been reported CONVERGED with a hazard ratio of 3e-11 --
# a coefficient where none exists.
comptime SA_COX_FLATNESS_RATIO: Float64 = 1e-6


struct CoxFit(Copyable, Movable):
    """A fitted Cox proportional-hazards model, or a refusal.

    `beta[k]` is the log hazard ratio for covariate `k`. `has_std_error[k]` False means the
    inverse information had no usable diagonal entry there and `std_error[k]` / `z_score[k]`
    are 0.0 placeholders rather than measurements.

    `loglik_null` is the Efron partial log-likelihood at `beta = 0` and
    `lr_statistic = 2 * (loglik - loglik_null)` is the likelihood-ratio test against the
    null model, on `n_covariates` degrees of freedom.

    `loglik_monotone` records that every accepted iterate did not decrease the
    log-likelihood. It is a property of the run, checked rather than assumed, and a False
    there with `status == SA_OK` would be a real defect in the line search.
    """

    var status: Int
    var n_obs: Int
    var n_events: Int
    var n_covariates: Int
    var iterations: Int
    var converged: Bool
    var loglik_monotone: Bool
    var beta: List[Float64]
    var std_error: List[Float64]
    var has_std_error: List[Bool]
    var z_score: List[Float64]
    var covariate_mean: List[Float64]
    var score: List[Float64]
    var loglik: Float64
    var loglik_null: Float64
    var lr_statistic: Float64
    var has_loglik: Bool
    var max_abs_score: Float64
    var last_step_max: Float64

    def __init__(out self, status: Int):
        self.status = status
        self.n_obs = 0
        self.n_events = 0
        self.n_covariates = 0
        self.iterations = 0
        self.converged = False
        self.loglik_monotone = False
        self.beta = List[Float64]()
        self.std_error = List[Float64]()
        self.has_std_error = List[Bool]()
        self.z_score = List[Float64]()
        self.covariate_mean = List[Float64]()
        self.score = List[Float64]()
        self.loglik = 0.0
        self.loglik_null = 0.0
        self.lr_statistic = 0.0
        self.has_loglik = False
        self.max_abs_score = 0.0
        self.last_step_max = 0.0


struct _Design(Copyable, Movable):
    """Validated, centered, time-ordered design. Internal: never crosses the wire."""

    var status: Int
    var n: Int
    var p: Int
    var x: List[Float64]
    var stime: List[Float64]
    var is_event: List[Bool]
    var mean: List[Float64]
    var n_events: Int

    def __init__(out self, status: Int):
        self.status = status
        self.n = 0
        self.p = 0
        self.x = List[Float64]()
        self.stime = List[Float64]()
        self.is_event = List[Bool]()
        self.mean = List[Float64]()
        self.n_events = 0


def _build_design(
    x_flat: List[Float64], n_rows: Int, n_cols: Int, times: List[Float64], event: List[Int]
) -> _Design:
    """Validate shapes, reject constant columns, center, and gather into time order.

    Shape validation goes through the frozen `sparse_numerics.csr.dims_fit`, which decides
    `n_rows * n_cols == len(x_flat)` by DIVISION. A formed product would wrap:
    `3 * 6148914691236517206 == 2`, so `n_rows = 3, n_cols = 6148914691236517206` against a
    two-element payload passes a multiply-then-compare guard and then reads far past the
    end -- the uncatchable abort, reachable from the SDK.
    """
    if n_cols <= 0 or n_rows <= 0:
        return _Design(SA_ERR_SHAPE)
    if n_cols > SA_MAX_COVARIATES:
        return _Design(SA_ERR_TOO_MANY_COVARIATES)
    if not dims_fit(n_rows, n_cols, len(x_flat)):
        return _Design(SA_ERR_SHAPE)
    if len(times) != n_rows or len(event) != n_rows:
        return _Design(SA_ERR_SHAPE)

    var sorted = sa_sort_observations(times, event)
    if sorted.status != SA_OK:
        return _Design(sorted.status)
    if sorted.n_events == 0:
        return _Design(SA_ERR_NO_EVENTS)

    for i in range(len(x_flat)):
        if not sa_is_finite(x_flat[i]):
            return _Design(SA_ERR_NON_FINITE_COVARIATE)

    var out = _Design(SA_OK)
    out.n = n_rows
    out.p = n_cols
    out.n_events = sorted.n_events
    out.stime = sorted.time.copy()
    out.is_event = sorted.is_event.copy()

    for k in range(n_cols):
        var col = List[Float64]()
        for i in range(n_rows):
            col.append(x_flat[i * n_cols + k])
        var mv = welford_mean_var(col)
        if len(mv) < 2:
            return _Design(SA_ERR_SHAPE)
        if not sa_is_finite(mv[0]) or not sa_is_finite(mv[1]):
            return _Design(SA_ERR_NON_FINITE_COVARIATE)
        if mv[1] <= 0.0:
            return _Design(SA_ERR_NO_COVARIATE_VARIATION)
        out.mean.append(mv[0])

    for r in range(n_rows):
        var src = sorted.order[r]
        for k in range(n_cols):
            out.x.append(x_flat[src * n_cols + k] - out.mean[k])
    return out^


def _eta(design: _Design, beta: List[Float64], row: Int) -> Float64:
    var total: Float64 = 0.0
    for k in range(design.p):
        total += beta[k] * design.x[row * design.p + k]
    return total


def _cox_loglik(design: _Design, beta: List[Float64]) -> List[Float64]:
    """Efron partial log-likelihood at `beta`. Returns [value, ok] with ok in {0.0, 1.0}.

    O(n) exponentials and O(n * p) products: the cheap evaluation the line search needs.
    `ok = 0.0` means an accumulator left the representable range, which is divergence, not
    a log-likelihood of zero.
    """
    var out = List[Float64]()
    var n = design.n
    var s0: Float64 = 0.0
    var loglik: Float64 = 0.0

    var eta = List[Float64]()
    for i in range(n):
        var e = _eta(design, beta, i)
        if not sa_is_finite(e) or fabs(e) > SA_COX_ETA_LIMIT:
            out.append(0.0)
            out.append(0.0)
            return out^
        eta.append(e)

    var r = n - 1
    while r >= 0:
        var t = design.stime[r]
        var lo = r
        while lo >= 0 and design.stime[lo] == t:
            lo -= 1
        var s0_tie: Float64 = 0.0
        var d = 0
        var eta_sum: Float64 = 0.0
        for s in range(lo + 1, r + 1):
            var w = exp(eta[s])
            s0 += w
            if design.is_event[s]:
                s0_tie += w
                eta_sum += eta[s]
                d += 1
        if not sa_is_finite(s0):
            out.append(0.0)
            out.append(0.0)
            return out^
        if d > 0:
            loglik += eta_sum
            for l in range(d):
                var f = Float64(l) / Float64(d)
                var a0 = s0 - f * s0_tie
                if not sa_is_finite(a0) or a0 <= 0.0:
                    out.append(0.0)
                    out.append(0.0)
                    return out^
                loglik -= log(a0)
        r = lo

    if not sa_is_finite(loglik):
        out.append(0.0)
        out.append(0.0)
        return out^
    out.append(loglik)
    out.append(1.0)
    return out^


struct _Newton(Copyable, Movable):
    """One accepted-point evaluation: log-likelihood, score and observed information."""

    var ok: Bool
    var loglik: Float64
    var score: List[Float64]
    var info: List[Float64]

    def __init__(out self, ok: Bool):
        self.ok = ok
        self.loglik = 0.0
        self.score = List[Float64]()
        self.info = List[Float64]()


def _cox_newton(design: _Design, beta: List[Float64]) -> _Newton:
    """Efron log-likelihood, score vector and observed information at `beta`.

    One descending pass. `S2` and `info` are filled on the upper triangle and mirrored, so
    both matrices are EXACTLY symmetric -- which matters because the frozen
    `linalg_ext.mat_is_positive_definite` rejects an asymmetric matrix outright, and a
    Cholesky on a matrix that is symmetric only to 1e-16 would be a coin flip.
    """
    var n = design.n
    var p = design.p
    var out = _Newton(False)

    var eta = List[Float64]()
    for i in range(n):
        var e = _eta(design, beta, i)
        if not sa_is_finite(e) or fabs(e) > SA_COX_ETA_LIMIT:
            return out^
        eta.append(e)

    var s0: Float64 = 0.0
    var s1 = List[Float64]()
    var s2 = List[Float64]()
    var score = List[Float64]()
    var info = List[Float64]()
    for _k in range(p):
        s1.append(0.0)
        score.append(0.0)
    for _k in range(p * p):
        s2.append(0.0)
        info.append(0.0)

    var loglik: Float64 = 0.0
    var s1_tie = List[Float64]()
    var s2_tie = List[Float64]()
    for _k in range(p):
        s1_tie.append(0.0)
    for _k in range(p * p):
        s2_tie.append(0.0)

    var r = n - 1
    while r >= 0:
        var t = design.stime[r]
        var lo = r
        while lo >= 0 and design.stime[lo] == t:
            lo -= 1

        var s0_tie: Float64 = 0.0
        for k in range(p):
            s1_tie[k] = 0.0
        for k in range(p * p):
            s2_tie[k] = 0.0
        var d = 0
        var eta_sum: Float64 = 0.0

        for s in range(lo + 1, r + 1):
            var w = exp(eta[s])
            s0 += w
            var base = s * p
            for k in range(p):
                var xk = design.x[base + k]
                s1[k] += w * xk
                for m in range(k, p):
                    var v = w * xk * design.x[base + m]
                    s2[k * p + m] += v
                    if m != k:
                        s2[m * p + k] += v
            if design.is_event[s]:
                s0_tie += w
                eta_sum += eta[s]
                d += 1
                for k in range(p):
                    var xk2 = design.x[base + k]
                    s1_tie[k] += w * xk2
                    for m in range(k, p):
                        var v2 = w * xk2 * design.x[base + m]
                        s2_tie[k * p + m] += v2
                        if m != k:
                            s2_tie[m * p + k] += v2

        if not sa_is_finite(s0):
            return out^

        if d > 0:
            loglik += eta_sum
            for s in range(lo + 1, r + 1):
                if design.is_event[s]:
                    for k in range(p):
                        score[k] += design.x[s * p + k]
            for l in range(d):
                var f = Float64(l) / Float64(d)
                var a0 = s0 - f * s0_tie
                if not sa_is_finite(a0) or a0 <= 0.0:
                    return out^
                loglik -= log(a0)
                for k in range(p):
                    var a1k = s1[k] - f * s1_tie[k]
                    score[k] -= a1k / a0
                    for m in range(k, p):
                        var a1m = s1[m] - f * s1_tie[m]
                        var a2 = s2[k * p + m] - f * s2_tie[k * p + m]
                        var term = a2 / a0 - (a1k * a1m) / (a0 * a0)
                        info[k * p + m] += term
                        if m != k:
                            info[m * p + k] += term
        r = lo

    if not sa_is_finite(loglik):
        return out^
    for k in range(p):
        if not sa_is_finite(score[k]):
            return out^
    for k in range(p * p):
        if not sa_is_finite(info[k]):
            return out^

    out.ok = True
    out.loglik = loglik
    out.score = score^
    out.info = info^
    return out^


def cox_fit(
    x_flat: List[Float64], n_rows: Int, n_cols: Int,
    times: List[Float64], event: List[Int],
    max_iter: Int, tol: Float64,
) -> CoxFit:
    """Cox proportional-hazards fit by Newton-Raphson on the Efron partial likelihood.

    `x_flat` is the row-major `n_rows x n_cols` covariate matrix. `event[i]` is 1 for an
    observed event and 0 for a right-censored observation; `len(event) == len(times) ==
    n_rows` is required exactly, and a mismatch is `SA_ERR_SHAPE` rather than a fit on
    whichever rows happened to line up. `max_iter` is in [1, COX_MAX_ITER] and `tol` in
    (0, 1].

    Returns a refusal, never a coefficient, when the likelihood carries no information:
    see the module docstring for the five cases and how each is detected.

    @capability cox_fit
    complexity: O(max_iter * n * p^2)
    counts:
    - n_rows * n_cols == len(x_flat) [kernel_validated]
    - n_rows == len(times, event) [kernel_validated]
    - dim max_iter <= COX_MAX_ITER [kernel_validated]
    @endcapability
    """
    if max_iter < 1 or max_iter > COX_MAX_ITER:
        return CoxFit(SA_ERR_BAD_ITER)
    if not sa_is_finite(tol) or tol <= 0.0 or tol > 1.0:
        return CoxFit(SA_ERR_BAD_TOL)

    var design = _build_design(x_flat, n_rows, n_cols, times, event)
    if design.status != SA_OK:
        return CoxFit(design.status)

    var n = design.n
    var p = design.p
    var factors = List[Int]()
    factors.append(max_iter)
    factors.append(n)
    factors.append(p)
    factors.append(p + SA_COX_MAX_HALVINGS)
    if not sa_work_fits(factors, SA_MAX_WORK):
        return CoxFit(SA_ERR_WORK_BUDGET)

    var beta = List[Float64]()
    for _k in range(p):
        beta.append(0.0)

    var start = _cox_newton(design, beta)
    if not start.ok:
        return CoxFit(SA_ERR_SEPARATION)
    var loglik_null = start.loglik
    var current = start.loglik
    var score = start.score.copy()
    var info = start.info.copy()

    var trace_null: Float64 = 0.0
    for k in range(p):
        trace_null += info[k * p + k]

    var monotone = True
    var converged = False
    var iterations = 0
    var last_step: Float64 = 0.0

    for _it in range(max_iter):
        iterations += 1
        var trace_now: Float64 = 0.0
        for k in range(p):
            trace_now += info[k * p + k]
        if trace_now <= SA_COX_FLATNESS_RATIO * trace_null:
            return CoxFit(SA_ERR_SEPARATION)

        var hessian = Matrix(p, p)
        for k in range(p):
            for m in range(p):
                hessian.set(k, m, info[k * p + m])
        if not mat_is_positive_definite(hessian):
            return CoxFit(SA_ERR_SINGULAR_INFORMATION)
        var delta = mat_solve(hessian, score)
        if len(delta) != p:
            return CoxFit(SA_ERR_SINGULAR_INFORMATION)
        # An ALL-ZEROS Newton direction is `mat_solve`'s sentinel for a system its pivoting
        # judged singular -- and it is indistinguishable from the direction at a stationary
        # point. Left unchecked it is worse than an error return, because a zero step passes
        # BOTH convergence tests trivially (`improvement = 0`, `step_max = 0`) and the current
        # iterate is published as the estimate. Measured: 2 rows x 2 covariates, both events,
        # makes the observed information exactly `x x^T` for one centred row -- rank 1, yet
        # positive definite by a 2e-10 pivot, so `mat_is_positive_definite` admits it and
        # `mat_solve` then returns zeros. `cox_fit` reported `status = ok`,
        # `converged = true`, `beta = [0, 0]`, `loglik == loglik_null`, `lr = 0` with
        # `score = [-0.534, -0.057]`: a coefficient of zero on a sample whose MLE is at
        # infinity, which is absence published as no effect.
        #
        # So a zero direction has to be justified by the SCORE. The per-coefficient scale is
        # that coefficient's own diagonal Newton step `|score_k| / info_kk`, which is in the
        # units of `beta_k` and therefore comparable against the same per-coefficient
        # tolerance the step test uses; it borrows nothing from the other coefficients.
        var delta_zero = True
        for k in range(p):
            if delta[k] != 0.0:
                delta_zero = False
        if delta_zero:
            var stationary = True
            for k in range(p):
                var diag = info[k * p + k]
                if not sa_is_finite(diag) or diag <= 0.0:
                    stationary = False
                    continue
                if fabs(score[k]) / diag > tol + SA_DBL_EPSILON * fabs(beta[k]):
                    stationary = False
            if not stationary:
                return CoxFit(SA_ERR_SINGULAR_INFORMATION)
        for k in range(p):
            if not sa_is_finite(delta[k]):
                return CoxFit(SA_ERR_SEPARATION)
            if fabs(beta[k] + delta[k]) > SA_COX_BETA_LIMIT:
                return CoxFit(SA_ERR_SEPARATION)

        var scale: Float64 = 1.0
        var accepted = False
        var trial = List[Float64]()
        var trial_ll: Float64 = 0.0
        for _h in range(SA_COX_MAX_HALVINGS):
            trial = List[Float64]()
            for k in range(p):
                trial.append(beta[k] + scale * delta[k])
            var ll = _cox_loglik(design, trial)
            if ll[1] == 1.0 and ll[0] >= current:
                trial_ll = ll[0]
                accepted = True
                break
            scale *= 0.5
        if not accepted:
            # No downhill-free step exists at this iterate. Either the score is already
            # zero to machine precision (converged) or the direction is not usable.
            #
            # A ZERO STEP IS NOT EVIDENCE OF A ZERO SCORE. `mat_solve` returns an all-zeros
            # vector for a system its pivoting judges singular, which is indistinguishable
            # from "the step is zero because the gradient is". Measured: 2 rows x 2
            # covariates, both events, makes the observed information EXACTLY rank 1 (it is
            # `x x^T` for a single centred row) but numerically positive definite by a 2e-10
            # pivot, so `mat_is_positive_definite` admits it and `mat_solve` then returns
            # zeros. This branch read those zeros as convergence and published
            # `beta = [0, 0]`, `status = ok`, `converged = true` with `score = [-0.534,
            # -0.057]` and `loglik == loglik_null` -- a coefficient of zero on a sample whose
            # MLE is at infinity. Absence reported as no effect.
            #
            # So stationarity is judged on the SCORE. The scale is that coefficient's own
            # diagonal Newton step, `|score_k| / info_kk`: it is in the units of `beta_k`, so
            # it is comparable against the same per-coefficient tolerance the accepted-step
            # path uses, and it borrows nothing from the other coefficients.
            var stationary = True
            for k in range(p):
                var own = tol + SA_DBL_EPSILON * fabs(beta[k])
                var diag = info[k * p + k]
                if not sa_is_finite(diag) or diag <= 0.0:
                    stationary = False
                    continue
                if fabs(score[k]) / diag > own:
                    stationary = False
            if stationary:
                converged = True
                break
            return CoxFit(SA_ERR_NOT_CONVERGED)

        var step_max: Float64 = 0.0
        var step_small = True
        for k in range(p):
            var s = fabs(trial[k] - beta[k])
            if s > step_max:
                step_max = s
            # Per-COEFFICIENT: the caller's absolute tolerance plus machine epsilon scaled
            # by the magnitude of THAT coefficient. Not by the largest coefficient, not by
            # a norm over all of them.
            if s > tol + SA_DBL_EPSILON * fabs(trial[k]):
                step_small = False
        last_step = step_max
        _ = trial_ll

        for k in range(p):
            if fabs(trial[k]) > SA_COX_BETA_LIMIT:
                return CoxFit(SA_ERR_SEPARATION)

        beta = trial.copy()
        var refreshed = _cox_newton(design, beta)
        if not refreshed.ok:
            return CoxFit(SA_ERR_SEPARATION)

        # The quantity judged is the log-likelihood CHANGE, so the tolerance is the
        # caller's absolute `tol` plus DBL_EPSILON times the magnitude of THAT
        # log-likelihood -- not of the sample size, the covariates, or a sum over rows.
        var own_tol = tol + SA_DBL_EPSILON * fabs(refreshed.loglik)
        var improvement = refreshed.loglik - current
        if improvement < -own_tol:
            monotone = False
        score = refreshed.score.copy()
        info = refreshed.info.copy()
        current = refreshed.loglik
        # BOTH criteria, not either. A separating covariate makes the log-likelihood gain
        # vanish while the Newton step stays at a constant ~1 per iteration forever, so a
        # gain-only test declares convergence at an arbitrary large |beta|. Requiring the
        # STEP to be small as well is what lets the iteration run on until the flatness
        # ratio or the |beta| ceiling names the real answer.
        if improvement <= own_tol and step_small:
            converged = True
            break

    if not converged:
        return CoxFit(SA_ERR_NOT_CONVERGED)

    var hess = Matrix(p, p)
    for k in range(p):
        for m in range(p):
            hess.set(k, m, info[k * p + m])
    if not mat_is_positive_definite(hess):
        return CoxFit(SA_ERR_SINGULAR_INFORMATION)
    var cov = mat_inv(hess)

    var out = CoxFit(SA_OK)
    out.n_obs = n
    out.n_events = design.n_events
    out.n_covariates = p
    out.iterations = iterations
    out.converged = True
    out.loglik_monotone = monotone
    out.beta = beta.copy()
    out.covariate_mean = design.mean.copy()
    out.score = score.copy()
    out.loglik = current
    out.loglik_null = loglik_null
    out.lr_statistic = 2.0 * (current - loglik_null)
    out.has_loglik = True
    out.last_step_max = last_step

    var max_score: Float64 = 0.0
    for k in range(p):
        if fabs(score[k]) > max_score:
            max_score = fabs(score[k])
    out.max_abs_score = max_score

    for k in range(p):
        var v = cov.get(k, k)
        if sa_is_finite(v) and v > 0.0:
            var se = sqrt(v)
            out.std_error.append(se)
            out.has_std_error.append(True)
            out.z_score.append(beta[k] / se)
        else:
            out.std_error.append(0.0)
            out.has_std_error.append(False)
            out.z_score.append(0.0)
    return out^


struct CoxRisk(Copyable, Movable):
    """Per-row linear predictor and relative risk under a given coefficient vector."""

    var status: Int
    var n_rows: Int
    var mean_linear_predictor: Float64
    var has_mean: Bool
    var linear_predictor: List[Float64]
    var relative_risk: List[Float64]
    var has_value: List[Bool]

    def __init__(out self, status: Int):
        self.status = status
        self.n_rows = 0
        self.mean_linear_predictor = 0.0
        self.has_mean = False
        self.linear_predictor = List[Float64]()
        self.relative_risk = List[Float64]()
        self.has_value = List[Bool]()


def cox_linear_predictor(
    x_flat: List[Float64], n_rows: Int, n_cols: Int, beta: List[Float64]
) -> CoxRisk:
    """`eta_i = sum_k beta_k * x_ik`, and `exp(eta_i - mean(eta))` as a relative risk.

    The relative risk is expressed against the SAMPLE MEAN linear predictor, and that
    reference is returned in `mean_linear_predictor`. A bare `exp(eta_i)` would be
    meaningless on its own -- the Cox model identifies hazard RATIOS, and the baseline is
    unspecified -- so publishing a number without its reference would invite it to be read
    as an absolute hazard.

    A row whose linear predictor is not representable is reported absent rather than
    clamped, because a clamped relative risk sorts as if it were the largest real one.

    @capability cox_linear_predictor
    complexity: O(n * p)
    counts:
    - n_rows * n_cols == len(x_flat) [kernel_validated]
    - n_cols == len(beta) [kernel_validated]
    @endcapability
    """
    if n_rows <= 0 or n_cols <= 0:
        return CoxRisk(SA_ERR_SHAPE)
    if n_cols > SA_MAX_COVARIATES:
        return CoxRisk(SA_ERR_TOO_MANY_COVARIATES)
    if not dims_fit(n_rows, n_cols, len(x_flat)):
        return CoxRisk(SA_ERR_SHAPE)
    if len(beta) != n_cols:
        return CoxRisk(SA_ERR_SHAPE)
    for k in range(n_cols):
        if not sa_is_finite(beta[k]):
            return CoxRisk(SA_ERR_NON_FINITE_COVARIATE)
    for i in range(len(x_flat)):
        if not sa_is_finite(x_flat[i]):
            return CoxRisk(SA_ERR_NON_FINITE_COVARIATE)

    var out = CoxRisk(SA_OK)
    out.n_rows = n_rows
    var total: Float64 = 0.0
    var n_ok = 0
    for i in range(n_rows):
        var e: Float64 = 0.0
        for k in range(n_cols):
            e += beta[k] * x_flat[i * n_cols + k]
        if sa_is_finite(e):
            total += e
            n_ok += 1
        out.linear_predictor.append(e if sa_is_finite(e) else 0.0)
    var reference: Float64 = 0.0
    var has_mean = False
    if n_ok == n_rows and sa_is_finite(total):
        reference = total / Float64(n_rows)
        has_mean = sa_is_finite(reference)
    out.mean_linear_predictor = reference if has_mean else 0.0
    out.has_mean = has_mean

    for i in range(n_rows):
        var e = out.linear_predictor[i]
        if not has_mean:
            out.relative_risk.append(0.0)
            out.has_value.append(False)
            continue
        var shifted = e - reference
        if not sa_is_finite(shifted) or fabs(shifted) > SA_COX_ETA_LIMIT:
            out.relative_risk.append(0.0)
            out.has_value.append(False)
            continue
        var rr = exp(shifted)
        if not sa_is_finite(rr):
            out.relative_risk.append(0.0)
            out.has_value.append(False)
            continue
        out.relative_risk.append(rr)
        out.has_value.append(True)
    return out^


struct CoxBaseline(Copyable, Movable):
    """Breslow baseline cumulative hazard at each distinct event time."""

    var status: Int
    var n_obs: Int
    var n_event_times: Int
    var time: List[Float64]
    var cum_hazard: List[Float64]
    var baseline_survival: List[Float64]
    var has_value: List[Bool]
    var monotone: Bool

    def __init__(out self, status: Int):
        self.status = status
        self.n_obs = 0
        self.n_event_times = 0
        self.time = List[Float64]()
        self.cum_hazard = List[Float64]()
        self.baseline_survival = List[Float64]()
        self.has_value = List[Bool]()
        self.monotone = False


def cox_baseline_cumhaz(
    x_flat: List[Float64], n_rows: Int, n_cols: Int,
    times: List[Float64], event: List[Int], beta: List[Float64],
) -> CoxBaseline:
    """Breslow baseline cumulative hazard `H0(t) = sum d_j / sum_{i in R(t_j)} exp(eta_i)`.

    The covariates are centered on their own means, exactly as in `cox_fit`, so `H0` is the
    cumulative hazard for a subject AT THE MEAN covariate vector rather than at the
    all-zeros vector -- the same convention `survfit.coxph` uses, and the reason
    `baseline_survival = exp(-H0)` is a curve a reader can compare against a Kaplan-Meier
    estimate of the same sample.

    Breslow rather than Efron here: it is the standard baseline estimator, it is defined
    without reference to a tie ordering, and the Efron correction changes each tie group's
    increment by O(d^2 / n). The pairing (Efron likelihood, Breslow baseline) is stated in
    the module docstring rather than left to be discovered.

    `monotone` is checked: a cumulative hazard must be non-decreasing, since every
    increment is a positive count over a positive sum.

    @capability cox_baseline_cumhaz
    complexity: O(n log n + n * p)
    counts:
    - n_rows * n_cols == len(x_flat) [kernel_validated]
    - n_rows == len(times, event) [kernel_validated]
    - n_cols == len(beta) [kernel_validated]
    @endcapability
    """
    if len(beta) != n_cols:
        return CoxBaseline(SA_ERR_SHAPE)
    for k in range(len(beta)):
        if not sa_is_finite(beta[k]):
            return CoxBaseline(SA_ERR_NON_FINITE_COVARIATE)
    var design = _build_design(x_flat, n_rows, n_cols, times, event)
    if design.status != SA_OK:
        return CoxBaseline(design.status)

    var n = design.n
    var eta = List[Float64]()
    for i in range(n):
        var e = _eta(design, beta, i)
        if not sa_is_finite(e) or fabs(e) > SA_COX_ETA_LIMIT:
            return CoxBaseline(SA_ERR_SEPARATION)
        eta.append(e)

    # The risk-set sum only accumulates when time DESCENDS, but the cumulative hazard only
    # accumulates when time ASCENDS. Those are two different directions, so the descending
    # pass collects per-event-time INCREMENTS `d_j / S0(t_j)` and the cumulative sum is
    # formed afterwards, walking the increments back up. Accumulating in the descending
    # pass produces a REVERSE cumulative hazard: correct increments, wrong prefix, and a
    # curve that decreases with time. That was the first version of this function, and the
    # `monotone` check below is what caught it -- which is the argument for asserting a
    # property that "obviously" holds.
    var rev_time = List[Float64]()
    var rev_inc = List[Float64]()
    var s0: Float64 = 0.0
    var r = n - 1
    while r >= 0:
        var t = design.stime[r]
        var lo = r
        while lo >= 0 and design.stime[lo] == t:
            lo -= 1
        var d = 0
        for s in range(lo + 1, r + 1):
            s0 += exp(eta[s])
            if design.is_event[s]:
                d += 1
        if not sa_is_finite(s0) or s0 <= 0.0:
            return CoxBaseline(SA_ERR_SEPARATION)
        if d > 0:
            var inc = Float64(d) / s0
            if not sa_is_finite(inc) or inc < 0.0:
                return CoxBaseline(SA_ERR_SEPARATION)
            rev_time.append(t)
            rev_inc.append(inc)
        r = lo

    var out = CoxBaseline(SA_OK)
    out.n_obs = n
    var k_rows = len(rev_time)
    out.n_event_times = k_rows
    var previous: Float64 = 0.0
    var cum: Float64 = 0.0
    var monotone = True
    for j in range(k_rows):
        var idx = k_rows - 1 - j
        cum += rev_inc[idx]
        if not sa_is_finite(cum):
            return CoxBaseline(SA_ERR_SEPARATION)
        var slop = SA_DBL_EPSILON * (fabs(previous) if fabs(previous) > 1.0 else 1.0)
        if cum + slop < previous:
            monotone = False
        out.time.append(rev_time[idx])
        out.cum_hazard.append(cum)
        var s = exp(-cum)
        if sa_is_finite(s) and s >= 0.0 and s <= 1.0:
            out.baseline_survival.append(s)
            out.has_value.append(True)
        else:
            out.baseline_survival.append(0.0)
            out.has_value.append(False)
        previous = cum
    out.monotone = monotone
    return out^
