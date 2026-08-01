"""
causal_inference.propensity — propensity scores, the diagnostics that decide whether they can
be used, IPW, and matching. Zero Python imports.

Why this file exists
--------------------
`causal.propensity_score(features, treatment)` is the tree's propensity model and it is not
one. Read it: it takes the mean and standard deviation of `features`, forms
`z = (features[i] - mean) / sd`, returns `sigmoid(z)`, and clamps the result into [0.01, 0.99].
Three separate problems, each fatal on its own:

  1. `treatment` IS NEVER READ. Nothing in the function looks at who was treated, so the
     "propensity" is a monotone rescaling of one covariate that happens to land in (0, 1). Two
     datasets with identical covariates and opposite treatment assignments get identical
     scores. It cannot be a probability of treatment, because it was never shown the treatment.
  2. It takes ONE feature — a flat `List[Float64]`, one value per unit. Confounding by more
     than one variable is the situation propensity scores exist for.
  3. The clamp. A unit with essentially no chance of treatment comes back at exactly 0.01, so
     `1/p` is 100 and the unit carries a hundred units of weight in an estimate the caller
     believes is an average. The clamp is applied AGAIN inside `causal.ipw_estimate`, so even a
     caller supplying honest scores gets them silently rewritten. A lack of overlap is the most
     important thing a propensity analysis can discover and the clamp is precisely what hides
     it.

So this module fits a real model — the frozen `linear_models.logistic_fit`, L2-regularised
Newton/IRLS over a flat row-major design matrix, CALLED UNCHANGED — and then reports what a
caller needs in order to decide whether the fit is usable at all.

What is REUSED, unchanged
-------------------------
* `linear_models.logistic_fit(X, y, l2, max_iter, tol)` — the fit. It already backtracks on the
  penalised log-likelihood, warm-starts the intercept at `logit(mean(y))`, and reports
  `converged` honestly, including the documented case where `l2 = 0` on separable data grows
  weights until `max_iter`. That last case is not papered over here: separable data means the
  arms are perfectly distinguishable, i.e. NO OVERLAP, and a non-converged fit is returned as
  `CI_ERR_NOT_CONVERGED` with the scores ABSENT rather than as scores that are not the MLE.
* `linear_models.logistic_predict_proba(X, weights, bias)` — the scores.
* `linear_models.logistic_std_errors(X, y, weights, bias, l2)` — the coefficient standard
  errors, so a caller can see which covariate the model actually leans on.
* `math_ext.mean` / `math_ext.variance` — the arm summaries and the normalised difference.
* `optimization.assignment.assignment_solve_masked` — OPTIMAL matching. Rectangular Hungarian
  with dual potentials, forbidden pairings as a `Bool` mask rather than a big-M cost, and a
  non-perfect matching reported as such instead of returned as a partial one. Greedy matching
  is also offered because it is a different estimand (it can leave units unmatched), and the
  suite asserts the relationship the two must satisfy: when both match everybody, the optimal
  total gap is <= the greedy total gap.

What this module refuses to do
------------------------------
* It does not clamp. A score of exactly 0 for a treated unit means the model says that unit
  could not have been treated, and `1/0` is not a weight. That is
  `CI_ERR_DEGENERATE_PROPENSITY`, with no estimate.
* It does not trim unless asked. Trimming changes the estimand — the ATE over the trimmed
  region is a different quantity from the ATE over the sample — so `trim_eps` defaults to
  nothing and the number of trimmed units is always reported. Silently discarding the units
  that carry the most weight is how an IPW estimate becomes stable and wrong.
* It does not hide how extreme the weighting got. `ipw_ate` reports the maximum weight, the
  count over the caller's threshold, and Kish's effective sample size per arm. An ATE built on
  three observations with weight 400 has an ESS near 3, and a caller who is told that will not
  quote it.
* It reports BOTH the Horvitz-Thompson and the Hajek (weight-normalised) estimates rather than
  picking one. They differ, they differ most exactly when the weights are worst, and the gap
  between them is itself a diagnostic.

Tolerances
----------
The only comparisons here that need one are the "is this score at the boundary" tests, and they
are exact (`p <= 0.0`, `p >= 1.0`) rather than toleranced, because a boundary score is a
structural statement and not a rounding question. `ci_tolerance` is used where a magnitude
comparison is genuinely needed, always against THAT comparison's own magnitude — never against a
sum or a maximum over units (rule 4b).

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
golden_vectors: mojo/tests/libs/test_causal_inference_propensity.mojo
benchmark: benchmarks/mojo_benchmarks/bench_causal_inference.mojo
docs: none
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs, sqrt

from math_ext import mean as ext_mean, variance as ext_variance
from linear_models import (
    logistic_fit,
    logistic_predict_proba,
    logistic_std_errors,
)
from optimization.assignment import (
    ASSIGN_ERR_FEWER_AGENTS_THAN_TASKS,
    ASSIGN_ERR_NO_PERFECT_MATCHING,
    ASSIGN_NONE,
    ASSIGN_OK,
    assignment_solve_masked,
)

from causal_inference.base import (
    CI_ABSENT,
    CI_ERR_DEGENERATE_PROPENSITY,
    CI_ERR_INSUFFICIENT_DATA,
    CI_ERR_INVALID_PARAMETER,
    CI_ERR_LENGTH_MISMATCH,
    CI_ERR_NON_FINITE,
    CI_ERR_NO_OVERLAP,
    CI_ERR_NOT_CONVERGED,
    CI_ERR_NO_CONTROL,
    CI_ERR_NO_MATCHES,
    CI_ERR_NO_TREATED,
    CI_ERR_SHAPE,
    CI_ERR_WORK_BUDGET,
    CI_LOGISTIC_BACKTRACK_STEPS,
    CI_OK,
    MAX_CI_FIT_WORK,
    MAX_CI_ITERATIONS,
    MAX_CI_MATCH_CELLS,
    MAX_CI_PAIR_CELLS,
    ci_all_finite,
    ci_finite,
    ci_matrix_fits,
    ci_product3_fits,
    ci_product_fits,
    ci_treatment_defect,
)


# ── result structs (declared HERE; see rule 2 — a struct owned elsewhere silently
#    drops the function that returns it out of the runtime contract) ───────────


struct PropensityFit(Copyable, Movable):
    """A fitted propensity model, its scores, and the overlap they imply.

    `has_scores` is False on every refusal and the lists are empty. `n_degenerate` counts
    scores at exactly 0.0 or 1.0 — reported, never clamped, because that count is the strongest
    single signal that the design has no overlap. The four per-arm extremes are the raw material
    for `overlap_report` and are returned here so one fit answers both questions.
    """

    var status: Int
    var has_scores: Bool
    var scores: List[Float64]
    var weights: List[Float64]
    var bias: Float64
    var std_errors: List[Float64]
    var converged: Bool
    var n_iter: Int
    var log_likelihood: Float64
    var n_units: Int
    var n_features: Int
    var n_treated: Int
    var n_control: Int
    var n_degenerate: Int
    var min_score_treated: Float64
    var max_score_treated: Float64
    var min_score_control: Float64
    var max_score_control: Float64

    fn __init__(out self, status: Int):
        self.status = status
        self.has_scores = False
        self.scores = List[Float64]()
        self.weights = List[Float64]()
        self.bias = 0.0
        self.std_errors = List[Float64]()
        self.converged = False
        self.n_iter = 0
        self.log_likelihood = 0.0
        self.n_units = 0
        self.n_features = 0
        self.n_treated = 0
        self.n_control = 0
        self.n_degenerate = 0
        self.min_score_treated = CI_ABSENT
        self.max_score_treated = CI_ABSENT
        self.min_score_control = CI_ABSENT
        self.max_score_control = CI_ABSENT


struct OverlapReport(Copyable, Movable):
    """Common support, measured rather than assumed.

    `support_lo`/`support_hi` are `[max(min over treated, min over control),
    min(max over treated, max over control)]` — the score interval where both arms have units.
    `has_support` is False when that interval is empty, which is the situation where no
    weighting or matching scheme can recover an ATE and every one of them will nonetheless
    return a number.

    `standardized_diff` is `(mean_t - mean_c) / sqrt((var_t + var_c) / 2)` on the scores, the
    conventional balance statistic. `has_standardized_diff` is False in exactly two situations:
    when the pooled denominator is zero, because a ratio with a zero denominator does not exist;
    and when EITHER arm holds fewer than two units, because a ddof=1 sample variance of one
    observation does not exist either. The frozen `math_ext.variance` returns 0.0 for `n <= 1`
    rather than refusing, and that invented zero survives a `pooled > 0` test whenever the OTHER
    arm has spread — shrinking the denominator by sqrt(2) and inflating the reported balance
    statistic by 1.414x. `mean_treated`/`mean_control` are still reported in that case; they are
    means, and a mean of one observation exists.
    """

    var status: Int
    var has_report: Bool
    var support_lo: Float64
    var support_hi: Float64
    var has_support: Bool
    var n_treated: Int
    var n_control: Int
    var n_treated_outside: Int
    var n_control_outside: Int
    var overlap_fraction: Float64
    var n_below_eps: Int
    var n_above_eps: Int
    var n_degenerate: Int
    var mean_treated: Float64
    var mean_control: Float64
    var standardized_diff: Float64
    var has_standardized_diff: Bool

    fn __init__(out self, status: Int):
        self.status = status
        self.has_report = False
        self.support_lo = 0.0
        self.support_hi = 0.0
        self.has_support = False
        self.n_treated = 0
        self.n_control = 0
        self.n_treated_outside = 0
        self.n_control_outside = 0
        self.overlap_fraction = CI_ABSENT
        self.n_below_eps = 0
        self.n_above_eps = 0
        self.n_degenerate = 0
        self.mean_treated = 0.0
        self.mean_control = 0.0
        self.standardized_diff = 0.0
        self.has_standardized_diff = False


struct IpwEstimate(Copyable, Movable):
    """An inverse-propensity-weighted ATE, with everything needed to distrust it.

    TWO estimates, on purpose. `ate_ht` is Horvitz-Thompson,
    `(1/n) Sum [T_i Y_i / e_i - (1 - T_i) Y_i / (1 - e_i)]`. `ate_hajek` normalises by the
    realised weight totals in each arm. They agree when the weights are benign and diverge when
    they are not, so the gap is a diagnostic a single number cannot carry. Hajek also has an
    exact property worth relying on: with a CONSTANT propensity it equals the plain difference
    in means, for any constant, which is asserted in the suite.

    `ess_treated`/`ess_control` are Kish's effective sample size `(Sum w)^2 / Sum w^2` per arm —
    the number of equally-weighted observations the weighted arm is worth. `n_extreme` counts
    weights above the caller's threshold and `max_weight` reports the worst one. An ATE whose
    ESS is 3 out of 10,000 units is not an ATE, and these are the fields that say so.

    `n_trimmed` is 0 unless the caller passed a positive `trim_eps`. Trimming is never applied
    on this module's initiative.
    """

    var status: Int
    var has_estimate: Bool
    var ate_ht: Float64
    var ate_hajek: Float64
    var n_units: Int
    var n_used: Int
    var n_used_treated: Int
    var n_used_control: Int
    var n_trimmed: Int
    var n_extreme: Int
    var max_weight: Float64
    var sum_weight_treated: Float64
    var sum_weight_control: Float64
    var ess_treated: Float64
    var ess_control: Float64

    fn __init__(out self, status: Int):
        self.status = status
        self.has_estimate = False
        self.ate_ht = 0.0
        self.ate_hajek = 0.0
        self.n_units = 0
        self.n_used = 0
        self.n_used_treated = 0
        self.n_used_control = 0
        self.n_trimmed = 0
        self.n_extreme = 0
        self.max_weight = CI_ABSENT
        self.sum_weight_treated = 0.0
        self.sum_weight_control = 0.0
        self.ess_treated = CI_ABSENT
        self.ess_control = CI_ABSENT


struct MatchReport(Copyable, Movable):
    """A matched sample and the ATT over it — plus how much of the sample it actually is.

    `n_unmatched` and `matched_fraction` are the fields that keep this honest. A matched ATT
    over 40% of the treated units is a different estimand from the ATT over all of them — it is
    the ATT among treated units that HAVE a comparable control — and a result that does not say
    so is a result a caller will read as the first thing.

    `matched_treated[k]` is paired with `matched_control[k]`, both unit indices into the
    caller's arrays. `total_gap` is the sum of `|e_i - e_j|` over pairs, which is what the
    optimal matcher minimises and therefore the number to compare the two matchers on.
    """

    var status: Int
    var has_estimate: Bool
    var att: Float64
    var matched_treated: List[Int]
    var matched_control: List[Int]
    var n_treated: Int
    var n_control: Int
    var n_matched: Int
    var n_unmatched: Int
    var matched_fraction: Float64
    var is_full_sample: Bool
    var total_gap: Float64
    var mean_gap: Float64
    var max_gap: Float64
    var with_replacement: Bool
    var n_controls_used: Int

    fn __init__(out self, status: Int):
        self.status = status
        self.has_estimate = False
        self.att = 0.0
        self.matched_treated = List[Int]()
        self.matched_control = List[Int]()
        self.n_treated = 0
        self.n_control = 0
        self.n_matched = 0
        self.n_unmatched = 0
        self.matched_fraction = CI_ABSENT
        self.is_full_sample = False
        self.total_gap = CI_ABSENT
        self.mean_gap = CI_ABSENT
        self.max_gap = CI_ABSENT
        self.with_replacement = False
        self.n_controls_used = 0


# ── propensity_fit ───────────────────────────────────────────────────────────


fn propensity_fit(
    x: List[Float64], n_units: Int, n_features: Int, treatment: List[Int],
    l2: Float64, max_iter: Int, tol: Float64,
) -> PropensityFit:
    """Fit `P(T = 1 | X)` by L2 logistic regression and report the scores plus their overlap.

    `x` is flat row-major `n_units x n_features`; `x[i * n_features + j]` is feature `j` of
    unit `i`. The intercept is implicit and never penalised (the frozen fit's convention).

    A non-converged fit is a REFUSAL, not a result. `linear_models.logistic_fit` documents that
    with `l2 = 0` on separable data the weights grow until `max_iter`, and separable data is
    exactly the no-overlap case: the covariates determine treatment, so no unit in one arm has a
    comparable unit in the other. Returning the last iterate's scores would hand a caller a
    weighting scheme built on probabilities that are artefacts of where the iteration stopped.
    `CI_ERR_NOT_CONVERGED` with `converged = False` and `n_iter` reported is the answer; the
    caller raises `l2` or `max_iter`, or concludes there is no overlap.

    Scores are NOT clamped. `n_degenerate` counts those at exactly 0.0 or 1.0 (reachable by
    underflow in `sigmoid` for a large linear index), and `ipw_ate` refuses on one rather than
    dividing. The frozen `causal.propensity_score` clamps to [0.01, 0.99] and
    `causal.ipw_estimate` clamps again, which turns "this unit could not have been treated" into
    "this unit carries a weight of 100".

    `n_features >= 1` is required. A constant propensity is expressed by passing a constant
    column, not by passing zero features: `logistic_predict_proba` returns an empty list for
    `p == 0`, so a zero-feature model would need a second scoring path, and a second path is
    where two behaviours come from (rule 3).

    @capability propensity_fit
    complexity: O(max_iter * n_units * n_features^2 + max_iter * n_features^3)
    counts:
    - n_units * n_features == len(x) [kernel_validated]
    - n_units == len(treatment) [kernel_validated]
    @endcapability
    """
    if n_units <= 0 or n_features <= 0:
        return PropensityFit(CI_ERR_SHAPE)
    if not ci_matrix_fits(n_units, n_features, len(x)):
        return PropensityFit(CI_ERR_SHAPE)
    if len(treatment) != n_units:
        return PropensityFit(CI_ERR_LENGTH_MISMATCH)
    if not ci_all_finite(x):
        return PropensityFit(CI_ERR_NON_FINITE)
    if not ci_finite(l2) or l2 < 0.0 or not ci_finite(tol) or tol <= 0.0:
        return PropensityFit(CI_ERR_INVALID_PARAMETER)
    # Both bounds are needed. The product budget below admits max_iter = 2^30 when n_units and
    # n_features are 1, and every Newton step allocates regardless of how cheap it is.
    if max_iter < 1 or max_iter > MAX_CI_ITERATIONS:
        return PropensityFit(CI_ERR_INVALID_PARAMETER)
    var tdefect = ci_treatment_defect(treatment)
    if tdefect != CI_OK:
        return PropensityFit(tdefect)
    # Work, charged for ALL FOUR factors: the Newton loop, the per-unit information
    # accumulation, the (p+1)^2 inner square, and — the one this used to omit — the frozen fit's
    # BACKTRACKING LINE SEARCH, up to CI_LOGISTIC_BACKTRACK_STEPS full O(n x (p+1)) penalized
    # log-likelihood passes per Newton step (linear_models.mojo:336, `for _ in range(20)`).
    # Claiming "all three factors" while a 20x inner loop ran unpriced is exactly the shape of
    # undercharge a work budget exists to prevent: MEASURED at p = 1, the regime where the
    # omission is worst, 9.4-11.1 ns per old-charged unit against 0.19-0.24 ns converging, so the
    # old charge bought ~10.1-11.9 s where MAX_CI_FIT_WORK promises order-of-seconds. With the
    # line-search term the same measurement is 0.85-1.01 ns per charged unit, ~1 s at the ceiling.
    # `n_features <= MAX_CI_FEATURES` (2^7) keeps `pp1 * pp1 + 20 * pp1` (max 18,944) well inside
    # Int, so forming it here cannot wrap.
    var pp1 = n_features + 1
    var per_unit = pp1 * pp1 + CI_LOGISTIC_BACKTRACK_STEPS * pp1
    if not ci_product3_fits(max_iter, n_units, per_unit, MAX_CI_FIT_WORK):
        return PropensityFit(CI_ERR_WORK_BUDGET)
    if not ci_product3_fits(max_iter, pp1 * pp1, pp1, MAX_CI_FIT_WORK):
        return PropensityFit(CI_ERR_WORK_BUDGET)

    var fit = logistic_fit(x, treatment, l2, max_iter, tol)
    var out = PropensityFit(CI_OK)
    out.n_units = n_units
    out.n_features = n_features
    out.n_iter = fit.n_iter
    out.converged = fit.converged
    if not fit.converged:
        out.status = CI_ERR_NOT_CONVERGED
        return out^
    if len(fit.weights) != n_features:
        # Unreachable given the validation above; reported rather than assumed away.
        out.status = CI_ERR_SHAPE
        return out^
    if not ci_all_finite(fit.weights) or not ci_finite(fit.bias):
        out.status = CI_ERR_NON_FINITE
        return out^

    var scores = logistic_predict_proba(x, fit.weights, fit.bias)
    if len(scores) != n_units or not ci_all_finite(scores):
        out.status = CI_ERR_NON_FINITE
        return out^
    if not ci_finite(fit.log_likelihood):
        out.status = CI_ERR_NON_FINITE
        return out^

    var min_t = 0.0
    var max_t = 0.0
    var min_c = 0.0
    var max_c = 0.0
    var seen_t = False
    var seen_c = False
    for i in range(n_units):
        var p = scores[i]
        if p <= 0.0 or p >= 1.0:
            out.n_degenerate += 1
        if treatment[i] == 1:
            out.n_treated += 1
            if not seen_t or p < min_t:
                min_t = p
            if not seen_t or p > max_t:
                max_t = p
            seen_t = True
        else:
            out.n_control += 1
            if not seen_c or p < min_c:
                min_c = p
            if not seen_c or p > max_c:
                max_c = p
            seen_c = True
    out.min_score_treated = min_t
    out.max_score_treated = max_t
    out.min_score_control = min_c
    out.max_score_control = max_c

    out.std_errors = logistic_std_errors(x, treatment, fit.weights, fit.bias, l2)
    if not ci_all_finite(out.std_errors):
        # A singular information matrix already comes back as an empty list from the frozen
        # kernel; a non-finite entry would be a serialization hazard, so it is dropped rather
        # than returned. The scores are unaffected and stay.
        out.std_errors = List[Float64]()
    out.scores = scores^
    out.weights = fit.weights.copy()
    out.bias = fit.bias
    out.log_likelihood = fit.log_likelihood
    out.has_scores = True
    return out^


# ── overlap_report ───────────────────────────────────────────────────────────


fn overlap_report(
    scores: List[Float64], treatment: List[Int], eps: Float64
) -> OverlapReport:
    """Common support and balance on the propensity score. Checkable, so checked.

    Overlap is the assumption every weighting and matching estimator rests on, and unlike
    parallel trends it is a property of the data rather than of the world — so it is measured
    here and reported, rather than assumed by the estimators. `has_support = False` means the
    score ranges of the two arms do not intersect at all: no reweighting of these units can
    produce a comparison, and every estimator that ignores this will still return a number.

    `eps` sets what counts as an extreme score for the `n_below_eps` / `n_above_eps` counts and
    must lie in [0, 0.5). It is a REPORTING threshold and changes nothing: no unit is dropped,
    reweighted or clamped here.

    @capability overlap_report
    complexity: O(n)
    counts: none
    @endcapability
    """
    var n = len(scores)
    if n == 0:
        return OverlapReport(CI_ERR_INSUFFICIENT_DATA)
    if len(treatment) != n:
        return OverlapReport(CI_ERR_LENGTH_MISMATCH)
    if not ci_all_finite(scores):
        return OverlapReport(CI_ERR_NON_FINITE)
    if not ci_finite(eps) or eps < 0.0 or eps >= 0.5:
        return OverlapReport(CI_ERR_INVALID_PARAMETER)
    var tdefect = ci_treatment_defect(treatment)
    if tdefect != CI_OK:
        return OverlapReport(tdefect)

    var out = OverlapReport(CI_OK)
    var st = List[Float64]()
    var sc = List[Float64]()
    for i in range(n):
        var p = scores[i]
        if p <= 0.0 or p >= 1.0:
            out.n_degenerate += 1
        if p < eps:
            out.n_below_eps += 1
        if p > 1.0 - eps:
            out.n_above_eps += 1
        if treatment[i] == 1:
            st.append(p)
        else:
            sc.append(p)
    out.n_treated = len(st)
    out.n_control = len(sc)

    var min_t = st[0]
    var max_t = st[0]
    for i in range(len(st)):
        if st[i] < min_t:
            min_t = st[i]
        if st[i] > max_t:
            max_t = st[i]
    var min_c = sc[0]
    var max_c = sc[0]
    for i in range(len(sc)):
        if sc[i] < min_c:
            min_c = sc[i]
        if sc[i] > max_c:
            max_c = sc[i]

    out.support_lo = min_t if min_t > min_c else min_c
    out.support_hi = max_t if max_t < max_c else max_c
    out.has_support = out.support_lo <= out.support_hi

    if out.has_support:
        for i in range(len(st)):
            if st[i] < out.support_lo or st[i] > out.support_hi:
                out.n_treated_outside += 1
        for i in range(len(sc)):
            if sc[i] < out.support_lo or sc[i] > out.support_hi:
                out.n_control_outside += 1
    else:
        out.n_treated_outside = len(st)
        out.n_control_outside = len(sc)
    var inside = n - out.n_treated_outside - out.n_control_outside
    out.overlap_fraction = Float64(inside) / Float64(n)

    out.mean_treated = ext_mean(st)
    out.mean_control = ext_mean(sc)
    # Sample variances of the two arms, from the frozen `math_ext.variance` (ddof = 1). The
    # denominator is the pooled spread of the two arms being compared — the quantity the
    # difference itself is measured in — and not a spread over anything else.
    #
    # BOTH arms need at least two units before that pooled spread EXISTS. The frozen
    # `math_ext.variance` returns 0.0 for `n <= 1` (math_ext.mojo: `if n <= 1: return 0.0`),
    # which is a FABRICATED zero and not a measured one — a ddof=1 variance of one observation
    # has a zero denominator and is not a number. Feeding it in is not caught by `pooled > 0.0`:
    # with one treated unit and a control arm that has real spread, `sqrt(0.5 * (0 + vc))` is
    # `sqrt(vc / 2)`, strictly positive, so the guard passes on the strength of the invented
    # zero and the denominator comes out a factor of sqrt(2) SMALLER than the one arm that
    # actually carries spread. Measured on one treated unit against a spread control arm:
    # `standardized_diff = 0.1195` reported where the honest single-arm SD gives 0.0845, i.e.
    # inflated by 1.414x — enough to move a caller across the conventional 0.1 balance
    # threshold on a quantity that was never observed. So absence is reported instead, which is
    # the same rule the rest of the package follows: a number that does not exist is absent.
    #
    # A genuine zero variance in one arm (two or more units that happen to share a score) is
    # NOT this case and is not excluded: `pooled` is then `sqrt(vc / 2)` built from two
    # variances that both exist, which is the textbook pooled SD.
    if len(st) >= 2 and len(sc) >= 2:
        var vt = ext_variance(st)
        var vc = ext_variance(sc)
        var pooled = sqrt(0.5 * (vt + vc))
        if pooled > 0.0 and ci_finite(pooled):
            var sd = (out.mean_treated - out.mean_control) / pooled
            if ci_finite(sd):
                out.standardized_diff = sd
                out.has_standardized_diff = True
    out.has_report = True
    return out^


# ── ipw_ate ──────────────────────────────────────────────────────────────────


fn ipw_ate(
    outcomes: List[Float64], treatment: List[Int], scores: List[Float64],
    trim_eps: Float64, extreme_weight_threshold: Float64,
) -> IpwEstimate:
    """Inverse-propensity-weighted ATE, both Horvitz-Thompson and Hajek, with weight diagnostics.

    A propensity of exactly 0.0 for a treated unit (or 1.0 for a control) is a statement that
    the unit could not have received the treatment it received. There is no weight for it, so
    the answer is `CI_ERR_DEGENERATE_PROPENSITY` and no estimate — never a clamp, which is what
    `causal.ipw_estimate` does to [0.01, 0.99] and which converts an impossible unit into a
    hundred units of influence.

    `trim_eps` in [0, 0.5) drops units whose score lies outside `[trim_eps, 1 - trim_eps]`
    BEFORE the degeneracy check, so a caller can knowingly exclude the extremes. It is 0 by
    default in every sense that matters: pass 0.0 and nothing is dropped. Trimming changes the
    estimand and `n_trimmed` always says how many units it changed it by.

    `extreme_weight_threshold` (> 0) only counts; it drops nothing.

    THE PROPERTY THE SUITE PINS: with a CONSTANT propensity `e_i = c` for every unit, the Hajek
    estimate equals the plain difference in arm means exactly, for any `c` in (0, 1) — the
    weights cancel arm by arm. Horvitz-Thompson equals it only when the arms are also balanced
    and `c = 0.5`, which is why both are reported.

    @capability ipw_ate
    complexity: O(n)
    counts: none
    @endcapability
    """
    var n = len(outcomes)
    if n == 0:
        return IpwEstimate(CI_ERR_INSUFFICIENT_DATA)
    if len(treatment) != n or len(scores) != n:
        return IpwEstimate(CI_ERR_LENGTH_MISMATCH)
    if not ci_all_finite(outcomes) or not ci_all_finite(scores):
        return IpwEstimate(CI_ERR_NON_FINITE)
    if not ci_finite(trim_eps) or trim_eps < 0.0 or trim_eps >= 0.5:
        return IpwEstimate(CI_ERR_INVALID_PARAMETER)
    if not ci_finite(extreme_weight_threshold) or extreme_weight_threshold <= 0.0:
        return IpwEstimate(CI_ERR_INVALID_PARAMETER)
    var tdefect = ci_treatment_defect(treatment)
    if tdefect != CI_OK:
        return IpwEstimate(tdefect)

    var out = IpwEstimate(CI_OK)
    out.n_units = n

    var sum_signed = 0.0
    var sw_t = 0.0
    var sw2_t = 0.0
    var swy_t = 0.0
    var sw_c = 0.0
    var sw2_c = 0.0
    var swy_c = 0.0
    var max_w = 0.0
    # Per-arm score extremes over the units actually USED, so trimming is reflected. Sentinels sit
    # outside [0, 1] so the first real score replaces them.
    var min_t = 2.0
    var max_t = -1.0
    var min_c = 2.0
    var max_c = -1.0

    for i in range(n):
        var p = scores[i]
        if trim_eps > 0.0 and (p < trim_eps or p > 1.0 - trim_eps):
            out.n_trimmed += 1
            continue
        var w: Float64
        if treatment[i] == 1:
            if p <= 0.0:
                return IpwEstimate(CI_ERR_DEGENERATE_PROPENSITY)
            w = 1.0 / p
        else:
            if p >= 1.0:
                return IpwEstimate(CI_ERR_DEGENERATE_PROPENSITY)
            w = 1.0 / (1.0 - p)
        if not ci_finite(w):
            return IpwEstimate(CI_ERR_DEGENERATE_PROPENSITY)
        if w > max_w:
            max_w = w
        if w > extreme_weight_threshold:
            out.n_extreme += 1
        out.n_used += 1
        if treatment[i] == 1:
            if p < min_t:
                min_t = p
            if p > max_t:
                max_t = p
        else:
            if p < min_c:
                min_c = p
            if p > max_c:
                max_c = p
        var wy = w * outcomes[i]
        if treatment[i] == 1:
            out.n_used_treated += 1
            sw_t += w
            sw2_t += w * w
            swy_t += wy
            sum_signed += wy
        else:
            out.n_used_control += 1
            sw_c += w
            sw2_c += w * w
            swy_c += wy
            sum_signed -= wy

    if out.n_used_treated == 0:
        out.status = CI_ERR_NO_TREATED
        return out^
    if out.n_used_control == 0:
        out.status = CI_ERR_NO_CONTROL
        return out^

    # Common support is the INTERSECTION of the two arms' score ranges. When it is empty, no treated
    # unit has a control at a comparable propensity and no control has a treated one, so a weighted
    # contrast between the arms is extrapolation dressed as an estimate -- there is no region where
    # both outcomes were observable.
    #
    # `ipw_ate` returned `CI_OK` with `has_estimate = True` for exactly that design. The number is
    # arithmetically well defined, every weight is finite, and it is not an effect. `CI_ERR_NO_OVERLAP`
    # (350) was allocated in base.mojo for this and never wired in.
    #
    # Non-empty support is NOT asserted to be large: overlap_fraction and the four per-arm extremes
    # remain the caller's instrument for judging how thin it is. This refuses only the case where
    # there is none, which is the one no diagnostic can rescue.
    var support_lo = min_t if min_t > min_c else min_c
    var support_hi = max_t if max_t < max_c else max_c
    if support_hi < support_lo:
        out.status = CI_ERR_NO_OVERLAP
        return out^

    out.max_weight = max_w
    out.sum_weight_treated = sw_t
    out.sum_weight_control = sw_c
    if sw2_t > 0.0:
        out.ess_treated = sw_t * sw_t / sw2_t
    if sw2_c > 0.0:
        out.ess_control = sw_c * sw_c / sw2_c

    var ht = sum_signed / Float64(out.n_used)
    var hajek = swy_t / sw_t - swy_c / sw_c
    if (
        not ci_finite(ht)
        or not ci_finite(hajek)
        or not ci_finite(out.ess_treated)
        or not ci_finite(out.ess_control)
        or not ci_finite(max_w)
    ):
        # An overflowing weighted sum has no value. Absent, and NOT +inf: a non-finite Float64
        # on the result path ends the worker process.
        return IpwEstimate(CI_ERR_NON_FINITE)
    out.ate_ht = ht
    out.ate_hajek = hajek
    out.has_estimate = True
    return out^


# ── matching ─────────────────────────────────────────────────────────────────


fn match_nearest(
    outcomes: List[Float64], treatment: List[Int], scores: List[Float64],
    caliper: Float64, with_replacement: Bool,
) -> MatchReport:
    """Greedy nearest-neighbour matching on the propensity score, within `caliper`.

    Deterministic without an RNG: treated units are considered in index order and each takes
    the control with the smallest `|e_i - e_j|`, ties going to the LOWEST control index. Two
    runs on the same input therefore produce the same pairs, which is the premise — a matched
    sample that changes between runs cannot support a decision anybody has to explain.

    `caliper >= 0` is in score units and is not optional: a caller that wants no caliper passes
    1.0, which is the largest possible gap between two probabilities. There is no infinite
    caliper, because `+inf` is not a finite Float64 and this package does not admit one.

    A treated unit with no control inside the caliper is UNMATCHED and counted. The report's
    `matched_fraction` and `is_full_sample` exist because an ATT over the matched subset is a
    different estimand from the ATT over the treated: it is the effect among treated units that
    have a comparable control. `n_matched == 0` is `CI_ERR_NO_MATCHES` with no estimate.

    Without replacement, each control is used at most once and the greedy order matters —
    stated because it is a real property of the method, not an implementation detail. With
    replacement, `n_controls_used` reports how many distinct controls carried the whole
    comparison.

    @capability match_nearest
    complexity: O(n_treated * n_control)
    counts: none
    @endcapability
    """
    var n = len(outcomes)
    if n == 0:
        return MatchReport(CI_ERR_INSUFFICIENT_DATA)
    if len(treatment) != n or len(scores) != n:
        return MatchReport(CI_ERR_LENGTH_MISMATCH)
    if not ci_all_finite(outcomes) or not ci_all_finite(scores):
        return MatchReport(CI_ERR_NON_FINITE)
    if not ci_finite(caliper) or caliper < 0.0:
        return MatchReport(CI_ERR_INVALID_PARAMETER)
    var tdefect = ci_treatment_defect(treatment)
    if tdefect != CI_OK:
        return MatchReport(tdefect)

    var treated = List[Int]()
    var control = List[Int]()
    for i in range(n):
        if treatment[i] == 1:
            treated.append(i)
        else:
            control.append(i)
    # Bounding memory is not bounding work: the pair scan is quadratic and allocates nothing
    # per pair, so it needs its OWN budget.
    if not ci_product_fits(len(treated), len(control), MAX_CI_PAIR_CELLS):
        return MatchReport(CI_ERR_WORK_BUDGET)

    var out = MatchReport(CI_OK)
    out.with_replacement = with_replacement
    out.n_treated = len(treated)
    out.n_control = len(control)

    var used = List[Bool](capacity=len(control))
    for _ in range(len(control)):
        used.append(False)

    var total_gap = 0.0
    var max_gap = 0.0
    var att_sum = 0.0
    for a in range(len(treated)):
        var i = treated[a]
        var best = -1
        var best_gap = 0.0
        for b in range(len(control)):
            if (not with_replacement) and used[b]:
                continue
            var gap = fabs(scores[i] - scores[control[b]])
            if best < 0 or gap < best_gap:
                best = b
                best_gap = gap
        if best < 0 or best_gap > caliper:
            out.n_unmatched += 1
            continue
        var j = control[best]
        # Set unconditionally: without replacement it EXCLUDES the control from later scans
        # (the `continue` above), and with replacement it only feeds `n_controls_used`, which is
        # how a caller sees that three controls carried a thousand pairs.
        used[best] = True
        out.matched_treated.append(i)
        out.matched_control.append(j)
        out.n_matched += 1
        total_gap += best_gap
        if best_gap > max_gap:
            max_gap = best_gap
        att_sum += outcomes[i] - outcomes[j]

    for b in range(len(control)):
        if used[b]:
            out.n_controls_used += 1

    if out.n_matched == 0:
        return MatchReport(CI_ERR_NO_MATCHES)
    var att = att_sum / Float64(out.n_matched)
    if not ci_finite(att) or not ci_finite(total_gap):
        return MatchReport(CI_ERR_NON_FINITE)
    out.att = att
    out.has_estimate = True
    out.total_gap = total_gap
    out.mean_gap = total_gap / Float64(out.n_matched)
    out.max_gap = max_gap
    out.matched_fraction = Float64(out.n_matched) / Float64(out.n_treated)
    out.is_full_sample = out.n_unmatched == 0
    return out^


fn match_optimal(
    outcomes: List[Float64], treatment: List[Int], scores: List[Float64],
    caliper: Float64,
) -> MatchReport:
    """Optimal 1:1 matching — minimum TOTAL score gap — via the frozen Hungarian solver.

    `optimization.assignment.assignment_solve_masked` is called unchanged. Controls are the
    AGENTS (rows) and treated units are the TASKS (columns), because that kernel saturates
    columns and what must be saturated here is the treated arm: an ATT that leaves treated units
    out is a different estimand. Consequently `n_control >= n_treated` is required and reported
    as `CI_ERR_INSUFFICIENT_DATA` when it fails, rather than silently transposed.

    The caliper is a `Bool` MASK, not a large cost. Encoding "too far apart to compare" as a big
    number lets the pairing become choosable the moment the alternatives are worse, which is how
    an infeasible matching returns a plausible one; the frozen kernel takes the mask precisely
    so that cannot happen, and reports `ASSIGN_ERR_NO_PERFECT_MATCHING` when no complete
    matching exists inside it. That becomes `CI_ERR_NO_MATCHES` here — all or nothing. A caller
    that wants a partial matching wants `match_nearest`, which is a different estimand and says
    so.

    THE PROPERTY THE SUITE PINS: when both matchers pair every treated unit, this one's
    `total_gap` is <= `match_nearest`'s. Greedy is not optimal and the difference is measurable.

    @capability match_optimal
    complexity: O(max(n_treated, n_control)^3)
    counts: none
    @endcapability
    """
    var n = len(outcomes)
    if n == 0:
        return MatchReport(CI_ERR_INSUFFICIENT_DATA)
    if len(treatment) != n or len(scores) != n:
        return MatchReport(CI_ERR_LENGTH_MISMATCH)
    if not ci_all_finite(outcomes) or not ci_all_finite(scores):
        return MatchReport(CI_ERR_NON_FINITE)
    if not ci_finite(caliper) or caliper < 0.0:
        return MatchReport(CI_ERR_INVALID_PARAMETER)
    var tdefect = ci_treatment_defect(treatment)
    if tdefect != CI_OK:
        return MatchReport(tdefect)

    var treated = List[Int]()
    var control = List[Int]()
    for i in range(n):
        if treatment[i] == 1:
            treated.append(i)
        else:
            control.append(i)
    if len(control) < len(treated):
        return MatchReport(CI_ERR_INSUFFICIENT_DATA)
    # This matcher MATERIALISES a Float64 cost and a Bool mask per pair and the solve is cubic,
    # so its cell budget is much tighter than `match_nearest`'s scan budget. Both are needed;
    # neither substitutes for the other.
    if not ci_product_fits(len(control), len(treated), MAX_CI_MATCH_CELLS):
        return MatchReport(CI_ERR_WORK_BUDGET)

    var rows = len(control)
    var cols = len(treated)
    var cost = List[Float64](capacity=rows * cols if rows * cols > 0 else 1)
    var allowed = List[Bool](capacity=rows * cols if rows * cols > 0 else 1)
    for r in range(rows):
        for c in range(cols):
            var gap = fabs(scores[control[r]] - scores[treated[c]])
            cost.append(gap)
            allowed.append(gap <= caliper)

    var solved = assignment_solve_masked(cost, rows, cols, allowed)
    if solved.status != ASSIGN_OK:
        if solved.status == ASSIGN_ERR_FEWER_AGENTS_THAN_TASKS:
            return MatchReport(CI_ERR_INSUFFICIENT_DATA)
        # Every other failure of that kernel — non-finite cost, bad shape, overflowing total —
        # is excluded by the validation above, so the reachable case is "no complete matching
        # inside the caliper". Reported as that rather than mapped to a code claiming more.
        return MatchReport(CI_ERR_NO_MATCHES)

    var out = MatchReport(CI_OK)
    out.n_treated = cols
    out.n_control = rows
    var total_gap = 0.0
    var max_gap = 0.0
    var att_sum = 0.0
    for r in range(rows):
        var c = solved.col_of_row[r]
        if c == ASSIGN_NONE:
            continue
        var i = treated[c]
        var j = control[r]
        out.matched_treated.append(i)
        out.matched_control.append(j)
        out.n_matched += 1
        out.n_controls_used += 1
        var gap = fabs(scores[i] - scores[j])
        total_gap += gap
        if gap > max_gap:
            max_gap = gap
        att_sum += outcomes[i] - outcomes[j]

    if out.n_matched == 0:
        return MatchReport(CI_ERR_NO_MATCHES)
    out.n_unmatched = cols - out.n_matched
    var att = att_sum / Float64(out.n_matched)
    if not ci_finite(att) or not ci_finite(total_gap):
        return MatchReport(CI_ERR_NON_FINITE)
    out.att = att
    out.has_estimate = True
    out.total_gap = total_gap
    out.mean_gap = total_gap / Float64(out.n_matched)
    out.max_gap = max_gap
    out.matched_fraction = Float64(out.n_matched) / Float64(cols)
    out.is_full_sample = out.n_unmatched == 0
    return out^
