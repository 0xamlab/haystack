"""
causal_inference.panel — difference-in-differences and synthetic control over a real panel.
Zero Python imports.

Why this file exists
--------------------
`causal.diff_in_diff(pre_treatment, post_treatment, pre_control, post_control)` takes four
PRE-AGGREGATED vectors and returns
`(mean(post_t) - mean(pre_t)) - (mean(post_c) - mean(pre_c))`. The arithmetic is right. The
problem is what the signature makes impossible: difference-in-differences rests entirely on
PARALLEL TRENDS — the assumption that, absent treatment, the two groups' outcomes would have
moved together — and four collapsed vectors contain no trend. There is no way, at that call
site, to look at whether the assumption is remotely plausible, and no way for the return value
to say anything about it.

So this module takes the panel itself: `y` flat row-major `n_units x n_periods`. That makes the
pre-treatment period-by-period gap between the arms computable, and it is REPORTED:

    pre_trend_diff        the OLS slope of (treated mean - control mean) across pre-periods
    max_abs_pre_gap_change the largest one-period jump in that gap
    treated_mean[t], control_mean[t]   the raw series, so a caller can look

*Those are evidence, not verification.* Parallel trends is an assumption about the
counterfactual and no data can confirm it — a flat pre-trend is consistent with a violated
assumption and a sloped pre-trend does not by itself invalidate the design. There is therefore
NO field in `DidReport` called `parallel_trends_holds`, and there deliberately never will be. The
report hands a caller the quantity a human judges and refuses to pretend it did the judging. What
IS absent rather than zero is the trend itself: with a single pre-period there is no slope to
compute, so `has_pre_trend` is False and `pre_trend_diff` is not to be read.

Synthetic control
-----------------
The other half of the file. A single treated unit, a donor pool of controls, and weights on the
SIMPLEX (`w_j >= 0`, `sum w_j = 1`) chosen to reproduce the treated unit's PRE-treatment path.
The effect is then the post-treatment gap between the treated unit and its synthetic twin.

Solved by Frank-Wolfe with an exact line search:

  * every iterate stays on the simplex by construction (`w <- w + gamma (e_j - w)` is a convex
    combination for `gamma` in [0, 1]), so there is no projection step and no way to leave the
    feasible set;
  * the objective is a quadratic in `w`, so the line search is closed form
    (`gamma* = (r . Xd) / ||Xd||^2`) and no step size is guessed;
  * it is FULLY DETERMINISTIC. No RNG, no `random_float64`, no `seed(`. The classical synthetic
    control literature reaches for a nested optimisation over covariate weights; this is the
    inner problem only, and it is convex, so the answer is a function of the data and nothing
    else. Two runs give bit-identical weights, which is the premise: a set of donor weights that
    moves between runs cannot appear in a decision anybody has to explain.

The Frank-Wolfe GAP is the convergence certificate and it is an upper bound on `f(w) - f(w*)`,
so it is reported whether or not the run converged. Hitting the iteration cap is
`CI_ERR_NOT_CONVERGED` with the weights and the effect ABSENT: an iterate that has not converged
is not the minimiser, and weights that do not minimise the pre-period error are not a synthetic
control — they are an arbitrary convex combination of donors. The measured gap comes back so a
caller can see how far off it was.

What is REUSED, unchanged
-------------------------
* `regression.ols_simple(x, y)` — the pre-trend slope. Length-guarded before the call, because
  it reads `y[i]` for `i` in `range(len(x))` and a short `y` there is an uncatchable abort.
* `math_ext.mean` — the period and window means.
* `causal.diff_in_diff` — the suite's differential oracle. With one pre-period and one
  post-period this module's ATT must equal it exactly.

Status codes: from `base.mojo`'s 340-359 allocation. None are defined here.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_causal_inference_panel.mojo
benchmark: benchmarks/mojo_benchmarks/bench_causal_inference_panel.mojo
docs: none
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs, sqrt

from math_ext import mean as ext_mean
from regression import ols_simple

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
    CI_ERR_WORK_BUDGET,
    CI_OK,
    MAX_CI_ITERATIONS,
    MAX_CI_SYNTH_WORK,
    ci_all_finite,
    ci_finite,
    ci_panel_fits,
    ci_product3_fits,
    ci_tolerance,
    ci_treatment_defect,
)


# ── result structs (declared HERE; rule 2) ───────────────────────────────────


struct DidReport(Copyable, Movable):
    """A difference-in-differences ATT, plus the pre-treatment trend a caller must judge.

    THERE IS NO `parallel_trends_holds` FIELD. Parallel trends is an assumption about a
    counterfactual, so no computation can verify it and a Bool claiming to would be the most
    damaging thing in this struct. What is here instead is the evidence: `pre_trend_diff` (the
    slope of the treated-minus-control gap across pre-periods), `max_abs_pre_gap_change`, and
    the two raw series.

    `has_pre_trend` is False when there is only ONE pre-period, and then `pre_trend_diff` is not
    a small number, it is not a number at all — absent, per rule 4, because a slope through one
    point does not exist.

    `att` is the standard 2x2 contrast computed over the pre and post WINDOWS (all pre-periods
    pooled, all post-periods pooled), which reduces exactly to `causal.diff_in_diff` when each
    window holds one period.
    """

    var status: Int
    var has_att: Bool
    var att: Float64
    var mean_pre_treated: Float64
    var mean_post_treated: Float64
    var mean_pre_control: Float64
    var mean_post_control: Float64
    var n_treated: Int
    var n_control: Int
    var n_pre: Int
    var n_post: Int
    var has_pre_trend: Bool
    var pre_trend_diff: Float64
    var pre_trend_r_squared: Float64
    var max_abs_pre_gap_change: Float64
    var pre_gap_first: Float64
    var pre_gap_last: Float64
    var treated_mean: List[Float64]
    var control_mean: List[Float64]
    var gap: List[Float64]

    def __init__(out self, status: Int):
        self.status = status
        self.has_att = False
        self.att = 0.0
        self.mean_pre_treated = 0.0
        self.mean_post_treated = 0.0
        self.mean_pre_control = 0.0
        self.mean_post_control = 0.0
        self.n_treated = 0
        self.n_control = 0
        self.n_pre = 0
        self.n_post = 0
        self.has_pre_trend = False
        self.pre_trend_diff = 0.0
        self.pre_trend_r_squared = CI_ABSENT
        self.max_abs_pre_gap_change = CI_ABSENT
        self.pre_gap_first = 0.0
        self.pre_gap_last = 0.0
        self.treated_mean = List[Float64]()
        self.control_mean = List[Float64]()
        self.gap = List[Float64]()


struct SynthResult(Copyable, Movable):
    """Donor weights on the simplex, the pre-period fit that justifies them, and the effect.

    `pre_rmse` is the entire warrant for the weights: a synthetic control that does not track
    the treated unit before treatment says nothing about it after. It is reported whether or not
    it is small, and `has_effect` never depends on it — hiding a bad fit behind a refusal would
    remove the caller's ability to see how bad.

    `fw_gap` is the Frank-Wolfe duality gap at exit, an UPPER BOUND on how far the objective is
    from its minimum. It is reported on both paths: on success as evidence, and on
    `CI_ERR_NOT_CONVERGED` as the measurement of the failure. On that path `weights` is empty and
    `has_effect` is False — an unconverged iterate is an arbitrary convex combination of donors,
    not a synthetic control.

    `effect_per_period[t]` is `y_treated[t] - synthetic[t]` for EVERY period, so the pre-period
    entries are the fit residuals and the post-period entries are the estimated effects. One
    array, because the same subtraction is the diagnostic before treatment and the answer after.
    """

    var status: Int
    var has_effect: Bool
    var effect: Float64
    var weights: List[Float64]
    var donor_index: List[Int]
    var sum_weights: Float64
    var n_nonzero_weights: Int
    var pre_rmse: Float64
    var has_pre_rmse: Bool
    var fw_gap: Float64
    var n_iter: Int
    var converged: Bool
    var n_donors: Int
    var n_pre: Int
    var n_post: Int
    var effect_per_period: List[Float64]
    var synthetic: List[Float64]

    def __init__(out self, status: Int):
        self.status = status
        self.has_effect = False
        self.effect = 0.0
        self.weights = List[Float64]()
        self.donor_index = List[Int]()
        self.sum_weights = 0.0
        self.n_nonzero_weights = 0
        self.pre_rmse = CI_ABSENT
        self.has_pre_rmse = False
        self.fw_gap = CI_ABSENT
        self.n_iter = 0
        self.converged = False
        self.n_donors = 0
        self.n_pre = 0
        self.n_post = 0
        self.effect_per_period = List[Float64]()
        self.synthetic = List[Float64]()


# ── did_panel ────────────────────────────────────────────────────────────────


def did_panel(
    y: List[Float64], n_units: Int, n_periods: Int,
    treated_unit: List[Int], first_treated_period: Int,
) -> DidReport:
    """Difference-in-differences over a panel, reporting the pre-treatment trend difference.

    `y[i * n_periods + t]` is unit `i`'s outcome in period `t`. `treated_unit[i]` is 1 for a
    treated unit and 0 for a control — the same binary convention every estimator in this package
    uses, and non-binary values are refused rather than pooled. `first_treated_period` is the
    index of the FIRST post-treatment period, so periods `[0, first)` are pre and
    `[first, n_periods)` are post; it must satisfy `1 <= first <= n_periods - 1`, because a
    design with no pre-period or no post-period is not a difference in differences.

    The ATT pools the windows: `(mean post treated - mean pre treated) - (mean post control -
    mean pre control)`. With one pre-period and one post-period this is exactly
    `causal.diff_in_diff` and the suite asserts the equality.

    The pre-trend is the OLS slope of the treated-minus-control gap over the pre-periods, from
    the frozen `regression.ols_simple`. It is ABSENT with a single pre-period. A caller reads it
    and decides; nothing here decides for them.

    @capability did_panel
    complexity: O(n_units * n_periods)
    counts:
    - n_units * n_periods == len(y) [kernel_validated]
    - n_units == len(treated_unit) [kernel_validated]
    @endcapability
    """
    if n_units <= 0 or n_periods <= 1:
        return DidReport(CI_ERR_SHAPE)
    if not ci_panel_fits(n_units, n_periods, len(y)):
        return DidReport(CI_ERR_SHAPE)
    if len(treated_unit) != n_units:
        return DidReport(CI_ERR_LENGTH_MISMATCH)
    if not ci_all_finite(y):
        return DidReport(CI_ERR_NON_FINITE)
    if first_treated_period < 1 or first_treated_period > n_periods - 1:
        return DidReport(CI_ERR_INVALID_PARAMETER)
    var tdefect = ci_treatment_defect(treated_unit)
    if tdefect != CI_OK:
        return DidReport(tdefect)

    var out = DidReport(CI_OK)
    out.n_pre = first_treated_period
    out.n_post = n_periods - first_treated_period
    for i in range(n_units):
        if treated_unit[i] == 1:
            out.n_treated += 1
        else:
            out.n_control += 1
    if out.n_treated == 0:
        return DidReport(CI_ERR_NO_TREATED)
    if out.n_control == 0:
        return DidReport(CI_ERR_NO_CONTROL)

    # Per-period arm means, and the gap between them.
    var pre_t = List[Float64]()
    var post_t = List[Float64]()
    var pre_c = List[Float64]()
    var post_c = List[Float64]()
    for t in range(n_periods):
        var st = 0.0
        var sc = 0.0
        for i in range(n_units):
            var v = y[i * n_periods + t]
            if treated_unit[i] == 1:
                st += v
            else:
                sc += v
        var mt = st / Float64(out.n_treated)
        var mc = sc / Float64(out.n_control)
        if not ci_finite(mt) or not ci_finite(mc):
            return DidReport(CI_ERR_NON_FINITE)
        out.treated_mean.append(mt)
        out.control_mean.append(mc)
        out.gap.append(mt - mc)
        if t < first_treated_period:
            pre_t.append(mt)
            pre_c.append(mc)
        else:
            post_t.append(mt)
            post_c.append(mc)

    out.mean_pre_treated = ext_mean(pre_t)
    out.mean_post_treated = ext_mean(post_t)
    out.mean_pre_control = ext_mean(pre_c)
    out.mean_post_control = ext_mean(post_c)
    var att = (out.mean_post_treated - out.mean_pre_treated) - (
        out.mean_post_control - out.mean_pre_control
    )
    if not ci_finite(att):
        return DidReport(CI_ERR_NON_FINITE)
    out.att = att
    out.has_att = True

    out.pre_gap_first = out.gap[0]
    out.pre_gap_last = out.gap[first_treated_period - 1]
    if first_treated_period >= 2:
        var periods = List[Float64]()
        var gaps = List[Float64]()
        var worst = 0.0
        for t in range(first_treated_period):
            periods.append(Float64(t))
            gaps.append(out.gap[t])
            if t > 0:
                var jump = fabs(out.gap[t] - out.gap[t - 1])
                if jump > worst:
                    worst = jump
        # `ols_simple` reads `y[i]` for every `i` in `range(len(x))`; the two lists are built in
        # the same loop so they are the same length by construction, which is the condition that
        # keeps the frozen kernel from indexing past its second argument.
        var fit = ols_simple(periods, gaps)
        if len(fit.coefficients) == 1 and ci_finite(fit.coefficients[0]):
            out.pre_trend_diff = fit.coefficients[0]
            out.has_pre_trend = True
            if ci_finite(fit.r_squared):
                out.pre_trend_r_squared = fit.r_squared
        out.max_abs_pre_gap_change = worst
    return out^


# ── synthetic_control ────────────────────────────────────────────────────────


def synthetic_control(
    y: List[Float64], n_units: Int, n_periods: Int, treated_index: Int,
    first_treated_period: Int, max_iter: Int, tol: Float64,
) -> SynthResult:
    """Synthetic control: simplex weights over donors fitted to the pre-treatment path.

    `y` is flat row-major `n_units x n_periods`; `treated_index` is the single treated unit and
    every other unit is a donor. Weights minimise the pre-period sum of squares
    `sum_{t < first} (y_treated[t] - sum_j w_j y_donor_j[t])^2` subject to `w >= 0`,
    `sum w = 1`.

    Frank-Wolfe with an exact line search. Each step moves toward the vertex `e_j` with the most
    negative gradient component, by the closed-form optimal `gamma` in [0, 1], so every iterate
    is a convex combination of the donors and the feasible set is never left. Deterministic:
    the vertex choice breaks ties toward the LOWEST donor index and the step is a formula, so the
    weights are a pure function of the data.

    CONVERGENCE. The Frank-Wolfe gap `2 sum_t r_t (Xd)_t` upper-bounds `f(w) - f(w*)`, so it is
    the certificate. It is judged RELATIVE to the gap's OWN terms — `2 sum_t |r_t (Xd)_t|`, the
    magnitudes of the very products being summed — and not against the objective, not against the
    outcome scale, and not against a maximum over periods. That distinction is rule 4b: a
    tolerance derived from any aggregate over other quantities lets one period's units pay for
    another period's error.

    `tol` IS THEREFORE A RELATIVE TOLERANCE ON THE GAP, not an absolute one, and that is forced
    rather than chosen. The gap is in SQUARED-OUTCOME units, so an absolute threshold makes the
    verdict a property of the caller's units instead of of the problem: with `tol` used
    absolutely, one problem measured in dollars refused to converge and the identical problem
    measured in ten-thousandths of a dollar converged, the gap scaling exactly as `c^2` (mantissa
    3.55369 across five orders of magnitude) while the threshold stood still. The suite asserts
    the same problem in two unit systems now gets the same verdict, the same `n_iter` and the same
    weights. A caller who wants a tighter certificate lowers `tol`; there is no unit in which
    `tol = 1e-3` means something different.

    Hitting `max_iter` is `CI_ERR_NOT_CONVERGED`: `weights` empty, `has_effect` False, and
    `fw_gap` reported so the caller can see the distance. `n_donors < 1`, no pre-period or no
    post-period are refusals, not degenerate answers.

    @capability synthetic_control
    complexity: O(max_iter * n_pre * n_donors)
    counts:
    - n_units * n_periods == len(y) [kernel_validated]
    - dim max_iter [kernel_validated]
    @endcapability
    """
    if n_units <= 1 or n_periods <= 1:
        return SynthResult(CI_ERR_SHAPE)
    if not ci_panel_fits(n_units, n_periods, len(y)):
        return SynthResult(CI_ERR_SHAPE)
    if not ci_all_finite(y):
        return SynthResult(CI_ERR_NON_FINITE)
    if treated_index < 0 or treated_index >= n_units:
        return SynthResult(CI_ERR_INVALID_PARAMETER)
    if first_treated_period < 1 or first_treated_period > n_periods - 1:
        return SynthResult(CI_ERR_INVALID_PARAMETER)
    # An explicit cap on top of the O(max_iter x n_pre x n_donors) budget below, which admits
    # 2^28 iterations when the inner dimensions are 1 — and every Frank-Wolfe step allocates its
    # own direction vector, so a cheap step is not a free one.
    if max_iter < 1 or max_iter > MAX_CI_ITERATIONS:
        return SynthResult(CI_ERR_INVALID_PARAMETER)
    if not ci_finite(tol) or tol < 0.0:
        return SynthResult(CI_ERR_INVALID_PARAMETER)

    var n_pre = first_treated_period
    var n_post = n_periods - first_treated_period
    var donors = List[Int]()
    for i in range(n_units):
        if i != treated_index:
            donors.append(i)
    var m = len(donors)
    if m < 1:
        return SynthResult(CI_ERR_INSUFFICIENT_DATA)
    # Bounding memory is not bounding work: each iteration costs O(n_pre * m), so all three
    # factors are charged. `ci_panel_fits` bounded the payload; this bounds the loop.
    if not ci_product3_fits(max_iter, n_pre, m, MAX_CI_SYNTH_WORK):
        return SynthResult(CI_ERR_WORK_BUDGET)

    var out = SynthResult(CI_OK)
    out.n_donors = m
    out.n_pre = n_pre
    out.n_post = n_post

    # Uniform start: the barycentre of the simplex, which is the only starting point that does
    # not privilege a donor. Frank-Wolfe's answer does not depend on it (the problem is convex)
    # but the ITERATES do, and a deterministic start makes the whole trajectory reproducible.
    var w = List[Float64](capacity=m)
    for _ in range(m):
        w.append(1.0 / Float64(m))
    # Residual over the pre-period only: r[t] = y_treated[t] - sum_j w_j y_donor_j[t].
    var r = List[Float64](capacity=n_pre)
    for t in range(n_pre):
        var s = 0.0
        for j in range(m):
            s += w[j] * y[donors[j] * n_periods + t]
        r.append(y[treated_index * n_periods + t] - s)
    if not ci_all_finite(r):
        return SynthResult(CI_ERR_NON_FINITE)

    var gap = 0.0
    var converged = False
    var iters = 0
    for _ in range(max_iter):
        iters += 1
        # c_j = sum_t X[t][j] r[t]; the gradient is -2c, so the best vertex maximises c_j.
        var best = 0
        var best_c = 0.0
        for j in range(m):
            var c = 0.0
            for t in range(n_pre):
                c += y[donors[j] * n_periods + t] * r[t]
            if j == 0 or c > best_c:
                best = j
                best_c = c
        # d = e_best - w, so (Xd)[t] = X[t][best] - (y_treated[t] - r[t]).
        var xd = List[Float64](capacity=n_pre)
        var num = 0.0
        var den = 0.0
        var gap_mag = 0.0
        for t in range(n_pre):
            var v = y[donors[best] * n_periods + t] - (
                y[treated_index * n_periods + t] - r[t]
            )
            xd.append(v)
            num += r[t] * v
            den += v * v
            gap_mag += fabs(r[t] * v)
        gap = 2.0 * num
        if not ci_finite(gap) or not ci_finite(den) or not ci_finite(gap_mag):
            return SynthResult(CI_ERR_NON_FINITE)
        # The judged quantity is the GAP, and both halves of what it is judged against are built
        # from the magnitudes of its OWN summands: `2 * sum_t |r_t (Xd)_t|` is the scale, and
        # nothing else enters — not the objective, not the outcome scale, not a maximum over
        # periods. `tol` multiplies that scale rather than standing beside it, because the gap
        # carries SQUARED-OUTCOME units and a fixed absolute number does not.
        #
        # Measured before this was relative: one problem, one `tol = 1e-3`, one `max_iter`, and
        # only the units of `y` changed — x1e-4 converged (fw_gap 3.55e-06), x1e-2 and above
        # refused with CI_ERR_NOT_CONVERGED (fw_gap 0.0355, 355.4, 3.55e6). The mantissa 3.55369
        # was identical across five orders of magnitude, i.e. the gap scaled exactly as c^2 while
        # the threshold stood still, so the SAME problem measured in dollars and in thousands of
        # dollars got opposite verdicts. Now the ratio is what is judged and the verdict is a
        # property of the problem.
        var scale = 2.0 * gap_mag
        var thresh = ci_tolerance(scale, tol * scale)
        if not ci_finite(thresh):
            # `ci_tolerance` already collapses a non-finite `abs_tol` to 0.0, so an absurd `tol`
            # overflowing `tol * scale` lands on the STRICT side by itself; this catches the one
            # remaining case, an overflow in its addition. A non-finite threshold would accept
            # every gap, which is the single direction that must never happen silently.
            return SynthResult(CI_ERR_NON_FINITE)
        if gap <= thresh:
            converged = True
            break
        if den <= 0.0:
            # The chosen direction changes nothing, so no step exists and the gap cannot shrink.
            converged = True
            break
        var step = num / den
        if step > 1.0:
            step = 1.0
        if step < 0.0:
            step = 0.0
        if step == 0.0:
            converged = True
            break
        for j in range(m):
            w[j] = (1.0 - step) * w[j]
        w[best] += step
        for t in range(n_pre):
            r[t] -= step * xd[t]
        if not ci_all_finite(w) or not ci_all_finite(r):
            return SynthResult(CI_ERR_NON_FINITE)

    out.n_iter = iters
    out.converged = converged
    out.fw_gap = gap if ci_finite(gap) else CI_ABSENT
    if not converged:
        out.status = CI_ERR_NOT_CONVERGED
        return out^

    var ss = 0.0
    for t in range(n_pre):
        ss += r[t] * r[t]
    var rmse = sqrt(ss / Float64(n_pre))
    if not ci_finite(rmse):
        return SynthResult(CI_ERR_NON_FINITE)

    var synth = List[Float64](capacity=n_periods)
    var eff = List[Float64](capacity=n_periods)
    var post_sum = 0.0
    for t in range(n_periods):
        var s = 0.0
        for j in range(m):
            s += w[j] * y[donors[j] * n_periods + t]
        synth.append(s)
        var e = y[treated_index * n_periods + t] - s
        eff.append(e)
        if t >= first_treated_period:
            post_sum += e
    if not ci_all_finite(synth) or not ci_all_finite(eff):
        return SynthResult(CI_ERR_NON_FINITE)
    var effect = post_sum / Float64(n_post)
    if not ci_finite(effect):
        return SynthResult(CI_ERR_NON_FINITE)

    var sw = 0.0
    for j in range(m):
        sw += w[j]
        if w[j] > 0.0:
            out.n_nonzero_weights += 1
    out.sum_weights = sw
    out.weights = w^
    out.donor_index = donors^
    out.pre_rmse = rmse
    out.has_pre_rmse = True
    out.synthetic = synth^
    out.effect_per_period = eff^
    out.effect = effect
    out.has_effect = True
    return out^
