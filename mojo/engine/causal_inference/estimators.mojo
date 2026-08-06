"""
causal_inference.estimators — outcome regression, doubly-robust AIPW, stratification, and a
deterministic bootstrap. Zero Python imports.

Why this file exists
--------------------
The tree has `causal.ate` (a difference in means), `causal.ipw_estimate` (a weighted difference
in means) and `causal.stratified_ate` (a weighted average of within-stratum differences). It has
no outcome-regression estimator, no doubly-robust estimator, and no way to attach an interval to
any of them.

The doubly-robust estimator is the one that earns its place, and its reason for existing is a
property that can be checked exactly rather than a claim about efficiency:

    psi_i = mu1_i - mu0_i
          + T_i (Y_i - mu1_i) / e_i
          - (1 - T_i) (Y_i - mu0_i) / (1 - e_i)

    ATE_dr = mean(psi)

is consistent if EITHER the outcome model (`mu0`, `mu1`) or the propensity model (`e`) is right.
Two exact identities follow, and both are asserted in the suite because a doubly-robust
estimator that satisfies neither is just an estimator with extra arithmetic:

  1. *The outcome model fits perfectly.* If `mu1_i == Y_i` for every treated unit and
     `mu0_i == Y_i` for every control, both correction terms are exactly zero and
     `ATE_dr == mean(mu1 - mu0)` — the outcome-regression estimate, bit for bit, whatever the
     propensities are.
  2. *The outcome model is a constant and the propensity model is right.* With
     `mu0 == mu1 == c` the regression term vanishes and, with `e == 0.5` and balanced arms, the
     correction collapses to the Horvitz-Thompson IPW estimate, which is the difference in
     means. Constants cancel because the treated and control weights are equal in number.

Those are the two directions of double robustness, written as equalities rather than as
asymptotics, and they are what `decomposition_residual` reports on every call: `ATE_dr` minus
its regression part minus its correction part is exactly 0 by construction, so a nonzero value
means the parts and the whole disagree and the caller can use neither. Rule 4b's closing note —
"self-consistency is a testable property, so test it" — applies to a package's own reports.

What is REUSED, unchanged
-------------------------
* `linear_models.elasticnet_fit(X, y, l1, l2, max_iter, tol)` — the per-arm outcome model.
  Cyclic coordinate descent with exact soft-thresholding, an unpenalised intercept, all-zero
  columns pinned at 0, and a `converged` flag that means what it says. `l1 = l2 = 0` is OLS on
  this scaling, which is what `outcome_regression_ate` uses by default; a caller facing more
  covariates than units passes a positive `l2` and gets ridge.
* `math_ext.mean` / `math_ext.variance` (ddof = 1) — the arm summaries and the
  influence-function standard error. The AIPW standard error IS `sqrt(var(psi) / n)`, so the
  frozen sample variance is the whole computation and nothing is re-derived here.
* `stats.quantile` — the bootstrap percentile interval endpoints. `stats` and not `math_ext`,
  which has a `quantile` of the same definition: `math_ext._sort_copy` is an insertion sort, so
  its cost is quadratic in the replicate count, which is a caller's integer and is bounded only
  by a work budget that does not charge for it. `stats.quantile` sorts through `stats.fast_sort`,
  an introsort. Measured at charges the budget admits exactly, the difference is 353.9 s against
  1.56 s; see `aipw_bootstrap_ci`.
* `causal.stratified_ate` — called by the suite as the differential oracle for `strata_ate`,
  which must reproduce it exactly whenever every stratum is usable, and must DIVERGE (visibly,
  with a reported coverage) when one is not.
* `determinism.sampling_keyed.uniform_int_keyed` + `determinism.streams.stream_id` — the
  bootstrap resample. Counter-based, so replicate `b`'s unit `k` is a pure function of
  `(seed, b, k)` and of nothing that ran before it. `random_float64` and `seed(` appear nowhere
  in this package: a resampled interval that moves between runs cannot appear in a decision
  anybody has to explain, which is the entire premise.

What is deliberately NOT reused
-------------------------------
`stats_bootstrap.bootstrap_replicate` and the `bootstrap_*_ci` family resample a single
`List[Float64]`. An AIPW bootstrap must resample UNITS — carrying `(Y, T, e, mu0, mu1)` together
— so a value resampler cannot express it; drawing five independent value resamples would
destroy exactly the unit-level association the estimator is built on. `uniform_int_keyed` gives
the index, which is the primitive that composes.

Status codes: from `base.mojo`'s 340-359 allocation. None are defined here.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: optional
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_causal_inference_estimators.mojo
benchmark: benchmarks/mojo_benchmarks/bench_causal_inference_panel.mojo
docs: none
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from std.math import sqrt

from linear_models import elasticnet_fit
from math_ext import mean as ext_mean, variance as ext_variance
# `stats.quantile` and NOT `math_ext.quantile`. Both are frozen, both are numpy's 'linear'
# interpolation, and on the finite input this file hands them they agree to the last bit — but
# `math_ext.quantile` sorts through `math_ext._sort_copy`, which is `_ins_sort`: O(B^2).
# `stats.quantile` sorts through `stats.sort_values` -> `stats.fast_sort`, an introsort: O(B log B).
# `B` is `n_replicates`, a caller's integer, and the difference is the whole cost of
# `aipw_bootstrap_ci` at the extreme its work budget admits — see the comment there.
# `evaluation.resample` and `strategy.tournament`, the other two bootstrap percentile intervals in
# this tree, already take `stats.quantile`; this file was the one that did not.
from stats import quantile as stats_quantile

from determinism.sampling_keyed import uniform_int_keyed
from determinism.streams import stream_id

from causal_inference.base import (
    CI_ABSENT,
    CI_ERR_DEGENERATE_PROPENSITY,
    CI_ERR_INDEX,
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
    MAX_CI_BOOTSTRAP_WORK,
    MAX_CI_FIT_WORK,
    MAX_CI_ITERATIONS,
    MAX_CI_UNITS,
    ci_all_finite,
    ci_finite,
    ci_matrix_fits,
    ci_product_fits,
    ci_treatment_defect,
)

# The bootstrap's RNG stream, derived from a NAME rather than picked as an integer. Ids 1-7 are
# reserved by `counter_rng`'s first consumer and reusing one would silently change values that
# consumer already drew; `stream_id` hashes into the space above them.
comptime _BOOTSTRAP_STREAM_NAME: String = "causal_inference.aipw_bootstrap"


# ── result structs (declared HERE; rule 2) ───────────────────────────────────


struct ArmContrast(Copyable, Movable):
    """The unadjusted difference in means, with the pieces it is made of.

    The baseline every adjusted estimator must reproduce when there is no confounding, which is
    the strongest test available for the whole package: on data generated with a known effect and
    randomised treatment, `diff` and every adjusted estimate must agree with the truth and with
    each other. `se` is the two-sample (Welch) standard error, absent when either arm has fewer
    than two units, because a variance of one observation does not exist.
    """

    var status: Int
    var has_diff: Bool
    var diff: Float64
    var mean_treated: Float64
    var mean_control: Float64
    var var_treated: Float64
    var var_control: Float64
    var n_treated: Int
    var n_control: Int
    var se: Float64
    var has_se: Bool

    def __init__(out self, status: Int):
        self.status = status
        self.has_diff = False
        self.diff = 0.0
        self.mean_treated = 0.0
        self.mean_control = 0.0
        self.var_treated = CI_ABSENT
        self.var_control = CI_ABSENT
        self.n_treated = 0
        self.n_control = 0
        self.se = CI_ABSENT
        self.has_se = False


struct OutcomeModel(Copyable, Movable):
    """Per-arm outcome regressions and the ATE they imply.

    `mu0[i]` and `mu1[i]` are the predicted outcome for unit `i` under control and under
    treatment, for EVERY unit — that is what makes them the input to the doubly-robust
    estimator. `ate` is `mean(mu1 - mu0)`, the g-formula / T-learner estimate.

    Both arms must converge. A coefficient vector from an interrupted coordinate descent is not
    the minimiser, and predictions from it are not the regression's predictions, so a
    non-converged arm is `CI_ERR_NOT_CONVERGED` with `has_ate = False` and the mu lists empty.

    Under collinear covariates the coefficient vector is not unique (coordinate descent lands on
    one of the minimisers, deterministically, in cyclic order) while the FITTED VALUES are unique
    in exact arithmetic. So `ate` is well determined where `coef_treated` is not, and that is
    stated rather than left for a caller to discover.
    """

    var status: Int
    var has_ate: Bool
    var ate: Float64
    var mu0: List[Float64]
    var mu1: List[Float64]
    var coef_treated: List[Float64]
    var coef_control: List[Float64]
    var bias_treated: Float64
    var bias_control: Float64
    var converged_treated: Bool
    var converged_control: Bool
    var n_iter_treated: Int
    var n_iter_control: Int
    var n_treated: Int
    var n_control: Int

    def __init__(out self, status: Int):
        self.status = status
        self.has_ate = False
        self.ate = 0.0
        self.mu0 = List[Float64]()
        self.mu1 = List[Float64]()
        self.coef_treated = List[Float64]()
        self.coef_control = List[Float64]()
        self.bias_treated = 0.0
        self.bias_control = 0.0
        self.converged_treated = False
        self.converged_control = False
        self.n_iter_treated = 0
        self.n_iter_control = 0
        self.n_treated = 0
        self.n_control = 0


struct DrEstimate(Copyable, Movable):
    """An augmented-IPW (doubly-robust) ATE, decomposed so the two halves are visible.

    `ate = ate_regression + ate_correction` EXACTLY, by construction, and
    `decomposition_residual` is that identity's measured residual. It is reported rather than
    asserted internally because a self-consistency check a caller can read is worth more than
    one it has to trust: two mutually exclusive claims inside one returned value means the caller
    can use neither.

    `se` is the influence-function standard error `sqrt(var(psi) / n_used)`, and
    `ci_lo`/`ci_hi` the normal-approximation interval at the caller's `z`. It is a large-sample
    interval and says nothing about the small-sample behaviour of an estimator with extreme
    weights — which is why `ess_treated`/`ess_control` travel beside it.
    """

    var status: Int
    var has_ate: Bool
    var ate: Float64
    var ate_regression: Float64
    var ate_correction: Float64
    var decomposition_residual: Float64
    var se: Float64
    var has_se: Bool
    var ci_lo: Float64
    var ci_hi: Float64
    var has_ci: Bool
    var n_units: Int
    var n_used: Int
    var n_trimmed: Int
    var n_extreme: Int
    var max_weight: Float64
    var ess_treated: Float64
    var ess_control: Float64

    def __init__(out self, status: Int):
        self.status = status
        self.has_ate = False
        self.ate = 0.0
        self.ate_regression = 0.0
        self.ate_correction = 0.0
        self.decomposition_residual = 0.0
        self.se = CI_ABSENT
        self.has_se = False
        self.ci_lo = 0.0
        self.ci_hi = 0.0
        self.has_ci = False
        self.n_units = 0
        self.n_used = 0
        self.n_trimmed = 0
        self.n_extreme = 0
        self.max_weight = CI_ABSENT
        self.ess_treated = CI_ABSENT
        self.ess_control = CI_ABSENT


struct StrataAte(Copyable, Movable):
    """A stratified ATE that reports the strata it could NOT use.

    `causal.stratified_ate` weights each usable stratum by `stratum_size / n` where `n` is the
    WHOLE sample, and silently skips any stratum missing an arm. So dropping strata makes the
    weights sum to less than one and pulls the estimate toward zero, with nothing in the return
    value saying it happened. Here the weights are renormalised over the COVERED mass,
    `covered_fraction` reports how much of the sample that is, and `is_full_sample` is False the
    moment a single stratum was unusable — because the estimand has changed: it is the ATE among
    strata where both arms are present.

    `stratum_ate[s]` is meaningful only where `stratum_has_ate[s]` is True. Parallel lists rather
    than a sentinel value, because an ATE of 0.0 is a perfectly ordinary real answer.
    """

    var status: Int
    var has_ate: Bool
    var ate: Float64
    var ate_uncovered_as_zero: Float64
    var n_strata: Int
    var n_usable: Int
    var n_units: Int
    var n_covered: Int
    var covered_fraction: Float64
    var is_full_sample: Bool
    var stratum_ate: List[Float64]
    var stratum_has_ate: List[Bool]
    var stratum_n: List[Int]
    var stratum_n_treated: List[Int]

    def __init__(out self, status: Int):
        self.status = status
        self.has_ate = False
        self.ate = 0.0
        self.ate_uncovered_as_zero = 0.0
        self.n_strata = 0
        self.n_usable = 0
        self.n_units = 0
        self.n_covered = 0
        self.covered_fraction = CI_ABSENT
        self.is_full_sample = False
        self.stratum_ate = List[Float64]()
        self.stratum_has_ate = List[Bool]()
        self.stratum_n = List[Int]()
        self.stratum_n_treated = List[Int]()


struct BootCI(Copyable, Movable):
    """A percentile bootstrap interval for the doubly-robust ATE, addressed by seed.

    Bit-identical for a fixed `seed`, because every draw is `uniform_int_keyed(0, n-1, seed,
    stream, b * n + k)` — a pure function of its coordinates, not of how many draws preceded it.
    The suite asserts that identity, and asserts that a different seed moves the interval; a
    resampling result that changes between runs cannot be used in a decision that has to be
    explained.

    `n_replicates_dropped` counts replicates whose resample happened to contain no treated or no
    control unit. Those have no ATE, so they are dropped rather than counted as zero — and the
    count is reported, because an interval built from 40 of 200 replicates is a different object
    from one built from 200.
    """

    var status: Int
    var has_ci: Bool
    var point: Float64
    var ci_lo: Float64
    var ci_hi: Float64
    var se_boot: Float64
    var has_se: Bool
    var n_replicates: Int
    var n_replicates_used: Int
    var n_replicates_dropped: Int
    var seed_used: Int

    def __init__(out self, status: Int):
        self.status = status
        self.has_ci = False
        self.point = 0.0
        self.ci_lo = 0.0
        self.ci_hi = 0.0
        self.se_boot = CI_ABSENT
        self.has_se = False
        self.n_replicates = 0
        self.n_replicates_used = 0
        self.n_replicates_dropped = 0
        self.seed_used = 0


# ── shared internals: ONE implementation each (rule 3, inside the package too) ─


def _predict_flat(
    x: List[Float64], n_units: Int, p: Int, w: List[Float64], b: Float64
) -> List[Float64]:
    """`x . w + b` per row of a flat row-major `n_units x p` matrix.

    THE package's linear predictor, in one place. `linear_models.logistic_predict_proba` is the
    same loop with a sigmoid on the end and there is no linear sibling in the tree;
    `regression.predict` exists but takes `List[List[Float64]]`, so calling it would mean
    materialising a nested copy of the whole design — 32 MB at the cell ceiling, doubled, for a
    dot product. Callers must have validated `n_units * p == len(x)` and `len(w) == p`.
    """
    var out = List[Float64](capacity=n_units if n_units > 0 else 1)
    for i in range(n_units):
        var z = b
        for j in range(p):
            z += x[i * p + j] * w[j]
        out.append(z)
    return out^


def _aipw_core(
    outcomes: List[Float64], treatment: List[Int], scores: List[Float64],
    mu0: List[Float64], mu1: List[Float64], trim_eps: Float64,
    threshold: Float64, use: List[Bool],
) -> DrEstimate:
    """The AIPW estimator over the units flagged in `use`. Internal; all validation done above.

    `use` is how the bootstrap reuses this without copying five arrays per replicate: a replicate
    is a multiset of indices, so the bootstrap builds its own resampled arrays instead and passes
    an all-True mask. Callers of the public entry point pass an all-True mask too — the parameter
    exists so that internal and public paths run the SAME code, which rule 4d asks for after a
    sibling's internal path skipped the public validation.
    """
    var n = len(outcomes)
    var out = DrEstimate(CI_OK)
    out.n_units = n

    var psi = List[Float64]()
    var reg_sum = 0.0
    var corr_sum = 0.0
    var sw_t = 0.0
    var sw2_t = 0.0
    var sw_c = 0.0
    var sw2_c = 0.0
    var max_w = 0.0
    var n_t = 0
    var n_c = 0

    for i in range(n):
        if not use[i]:
            continue
        var p = scores[i]
        if trim_eps > 0.0 and (p < trim_eps or p > 1.0 - trim_eps):
            out.n_trimmed += 1
            continue
        var reg = mu1[i] - mu0[i]
        var corr: Float64
        var w: Float64
        if treatment[i] == 1:
            if p <= 0.0:
                return DrEstimate(CI_ERR_DEGENERATE_PROPENSITY)
            w = 1.0 / p
            corr = (outcomes[i] - mu1[i]) * w
            n_t += 1
            sw_t += w
            sw2_t += w * w
        else:
            if p >= 1.0:
                return DrEstimate(CI_ERR_DEGENERATE_PROPENSITY)
            w = 1.0 / (1.0 - p)
            corr = -(outcomes[i] - mu0[i]) * w
            n_c += 1
            sw_c += w
            sw2_c += w * w
        if not ci_finite(w):
            return DrEstimate(CI_ERR_DEGENERATE_PROPENSITY)
        if w > max_w:
            max_w = w
        if w > threshold:
            out.n_extreme += 1
        reg_sum += reg
        corr_sum += corr
        psi.append(reg + corr)
        out.n_used += 1

    if n_t == 0:
        out.status = CI_ERR_NO_TREATED
        return out^
    if n_c == 0:
        out.status = CI_ERR_NO_CONTROL
        return out^

    var m = Float64(out.n_used)
    var ate = ext_mean(psi)
    var reg_part = reg_sum / m
    var corr_part = corr_sum / m
    if not ci_finite(ate) or not ci_finite(reg_part) or not ci_finite(corr_part):
        return DrEstimate(CI_ERR_NON_FINITE)

    out.ate = ate
    out.ate_regression = reg_part
    out.ate_correction = corr_part
    out.decomposition_residual = ate - reg_part - corr_part
    out.max_weight = max_w
    if sw2_t > 0.0:
        out.ess_treated = sw_t * sw_t / sw2_t
    if sw2_c > 0.0:
        out.ess_control = sw_c * sw_c / sw2_c
    if not ci_finite(out.ess_treated) or not ci_finite(out.ess_control):
        return DrEstimate(CI_ERR_NON_FINITE)
    out.has_ate = True

    if out.n_used >= 2:
        # The influence-function variance: var(psi) / n, from the frozen ddof=1 sample variance.
        var v = ext_variance(psi)
        if ci_finite(v) and v >= 0.0:
            var se = sqrt(v / m)
            if ci_finite(se):
                out.se = se
                out.has_se = True
    return out^


# ── naive_ate ────────────────────────────────────────────────────────────────


def naive_ate(outcomes: List[Float64], treatment: List[Int]) -> ArmContrast:
    """The unadjusted difference in arm means, with variances, counts and a Welch standard error.

    Deliberately NOT called an ATE without qualification: it is the average treatment effect
    exactly when assignment was randomised, and a difference in group means otherwise. The name
    of the struct is `ArmContrast` for that reason. `causal.ate` computes the same difference and
    the suite asserts they agree exactly; what this adds is the counts, the spread and the
    absence flags, so a caller can see that the "effect" rests on two observations.

    @capability naive_ate
    complexity: O(n)
    counts: none
    @endcapability
    """
    var n = len(outcomes)
    if n == 0:
        return ArmContrast(CI_ERR_INSUFFICIENT_DATA)
    if len(treatment) != n:
        return ArmContrast(CI_ERR_LENGTH_MISMATCH)
    if not ci_all_finite(outcomes):
        return ArmContrast(CI_ERR_NON_FINITE)
    var tdefect = ci_treatment_defect(treatment)
    if tdefect != CI_OK:
        return ArmContrast(tdefect)

    var yt = List[Float64]()
    var yc = List[Float64]()
    for i in range(n):
        if treatment[i] == 1:
            yt.append(outcomes[i])
        else:
            yc.append(outcomes[i])

    var out = ArmContrast(CI_OK)
    out.n_treated = len(yt)
    out.n_control = len(yc)
    out.mean_treated = ext_mean(yt)
    out.mean_control = ext_mean(yc)
    var diff = out.mean_treated - out.mean_control
    if not ci_finite(diff):
        return ArmContrast(CI_ERR_NON_FINITE)
    out.diff = diff
    out.has_diff = True
    if out.n_treated >= 2 and out.n_control >= 2:
        var vt = ext_variance(yt)
        var vc = ext_variance(yc)
        out.var_treated = vt
        out.var_control = vc
        var se = sqrt(vt / Float64(out.n_treated) + vc / Float64(out.n_control))
        if ci_finite(se):
            out.se = se
            out.has_se = True
    return out^


# ── outcome_regression_ate ───────────────────────────────────────────────────


# Signature packing is load-bearing: `mojo_inventory` matches a signature inside a NINE-LINE
# window and a signature closing on the tenth line is dropped from the contract and the dispatch
# with no error anywhere. Four lines here leaves five of headroom.
def outcome_regression_ate(
    x: List[Float64], n_units: Int, n_features: Int, treatment: List[Int],
    outcomes: List[Float64], l1: Float64, l2: Float64, max_iter: Int, tol: Float64,
) -> OutcomeModel:
    """Fit the outcome model separately per arm and report `mean(mu1 - mu0)` (the g-formula ATE).

    `x` is flat row-major `n_units x n_features`. Each arm's rows are gathered into their own
    design matrix and handed to the frozen `linear_models.elasticnet_fit`; `l1 = l2 = 0` is OLS
    on that scaling. Both arms are then predicted for EVERY unit, which is what makes `mu0`/`mu1`
    usable as the regression half of `aipw_ate`.

    An arm with fewer rows than `n_features + 1` cannot identify its own regression and is
    `CI_ERR_INSUFFICIENT_DATA` — not a fit with an arbitrary coefficient in the free direction.
    An arm that did not converge is `CI_ERR_NOT_CONVERGED` with everything absent.

    @capability outcome_regression_ate
    complexity: O(max_iter * n_units * n_features)
    counts:
    - n_units * n_features == len(x) [kernel_validated]
    - n_units == len(treatment, outcomes) [kernel_validated]
    @endcapability
    """
    if n_units <= 0 or n_features <= 0:
        return OutcomeModel(CI_ERR_SHAPE)
    if not ci_matrix_fits(n_units, n_features, len(x)):
        return OutcomeModel(CI_ERR_SHAPE)
    if len(treatment) != n_units or len(outcomes) != n_units:
        return OutcomeModel(CI_ERR_LENGTH_MISMATCH)
    if not ci_all_finite(x) or not ci_all_finite(outcomes):
        return OutcomeModel(CI_ERR_NON_FINITE)
    if not ci_finite(l1) or l1 < 0.0 or not ci_finite(l2) or l2 < 0.0:
        return OutcomeModel(CI_ERR_INVALID_PARAMETER)
    if not ci_finite(tol) or tol <= 0.0:
        return OutcomeModel(CI_ERR_INVALID_PARAMETER)
    # An explicit iteration ceiling as well as the product budget: `max_iter * n * p <= 2^30`
    # admits a billion nearly-free sweeps, and each sweep still costs a pass over the residual.
    if max_iter < 1 or max_iter > MAX_CI_ITERATIONS:
        return OutcomeModel(CI_ERR_INVALID_PARAMETER)
    var tdefect = ci_treatment_defect(treatment)
    if tdefect != CI_OK:
        return OutcomeModel(tdefect)
    # Coordinate descent is O(max_iter * n * p) per arm. Both factors of the inner product are
    # charged, not just the iteration count.
    if not ci_product_fits(max_iter, n_units * n_features, MAX_CI_FIT_WORK):
        return OutcomeModel(CI_ERR_WORK_BUDGET)

    var xt = List[Float64]()
    var yt = List[Float64]()
    var xc = List[Float64]()
    var yc = List[Float64]()
    for i in range(n_units):
        if treatment[i] == 1:
            for j in range(n_features):
                xt.append(x[i * n_features + j])
            yt.append(outcomes[i])
        else:
            for j in range(n_features):
                xc.append(x[i * n_features + j])
            yc.append(outcomes[i])

    var out = OutcomeModel(CI_OK)
    out.n_treated = len(yt)
    out.n_control = len(yc)
    if out.n_treated < n_features + 1 or out.n_control < n_features + 1:
        return OutcomeModel(CI_ERR_INSUFFICIENT_DATA)

    var ft = elasticnet_fit(xt, yt, l1, l2, max_iter, tol)
    var fc = elasticnet_fit(xc, yc, l1, l2, max_iter, tol)
    out.converged_treated = ft.converged
    out.converged_control = fc.converged
    out.n_iter_treated = ft.n_iter
    out.n_iter_control = fc.n_iter
    if not ft.converged or not fc.converged:
        out.status = CI_ERR_NOT_CONVERGED
        return out^
    if len(ft.weights) != n_features or len(fc.weights) != n_features:
        out.status = CI_ERR_SHAPE
        return out^
    if not ci_all_finite(ft.weights) or not ci_all_finite(fc.weights):
        out.status = CI_ERR_NON_FINITE
        return out^
    if not ci_finite(ft.bias) or not ci_finite(fc.bias):
        out.status = CI_ERR_NON_FINITE
        return out^

    var mu1 = _predict_flat(x, n_units, n_features, ft.weights, ft.bias)
    var mu0 = _predict_flat(x, n_units, n_features, fc.weights, fc.bias)
    if not ci_all_finite(mu1) or not ci_all_finite(mu0):
        out.status = CI_ERR_NON_FINITE
        return out^
    var total = 0.0
    for i in range(n_units):
        total += mu1[i] - mu0[i]
    var ate = total / Float64(n_units)
    if not ci_finite(ate):
        out.status = CI_ERR_NON_FINITE
        return out^

    out.ate = ate
    out.has_ate = True
    out.mu1 = mu1^
    out.mu0 = mu0^
    out.coef_treated = ft.weights.copy()
    out.coef_control = fc.weights.copy()
    out.bias_treated = ft.bias
    out.bias_control = fc.bias
    return out^


# ── aipw_ate ─────────────────────────────────────────────────────────────────


def aipw_ate(
    outcomes: List[Float64], treatment: List[Int], scores: List[Float64],
    mu0: List[Float64], mu1: List[Float64], trim_eps: Float64,
    extreme_weight_threshold: Float64, z: Float64,
) -> DrEstimate:
    """Augmented IPW: the doubly-robust ATE, its decomposition, and its interval.

    `mu0`/`mu1` come from `outcome_regression_ate` (or from any model the caller trusts) and
    `scores` from `propensity_fit`. The estimator is consistent if either is correct, and the two
    exact identities that make that claim checkable are stated at the top of this module and
    asserted in the suite.

    A degenerate propensity is refused, never clamped: the correction term divides by `e_i`, and
    a treated unit at `e_i = 0` has no weight. `trim_eps` in [0, 0.5) is the caller's decision and
    `n_trimmed` always reports its size, because the trimmed ATE is a different estimand.

    `z` is the normal quantile for the interval (1.96 for 95%); a non-positive `z` suppresses the
    interval rather than producing a degenerate one. The interval is the large-sample one and
    `ess_treated`/`ess_control` sit beside it precisely because it is not to be believed when
    they are small.

    @capability aipw_ate
    complexity: O(n)
    counts: none
    @endcapability
    """
    var n = len(outcomes)
    if n == 0:
        return DrEstimate(CI_ERR_INSUFFICIENT_DATA)
    if len(treatment) != n or len(scores) != n or len(mu0) != n or len(mu1) != n:
        return DrEstimate(CI_ERR_LENGTH_MISMATCH)
    if not ci_all_finite(outcomes) or not ci_all_finite(scores):
        return DrEstimate(CI_ERR_NON_FINITE)
    if not ci_all_finite(mu0) or not ci_all_finite(mu1):
        return DrEstimate(CI_ERR_NON_FINITE)
    if not ci_finite(trim_eps) or trim_eps < 0.0 or trim_eps >= 0.5:
        return DrEstimate(CI_ERR_INVALID_PARAMETER)
    if not ci_finite(extreme_weight_threshold) or extreme_weight_threshold <= 0.0:
        return DrEstimate(CI_ERR_INVALID_PARAMETER)
    if not ci_finite(z):
        return DrEstimate(CI_ERR_INVALID_PARAMETER)
    var tdefect = ci_treatment_defect(treatment)
    if tdefect != CI_OK:
        return DrEstimate(tdefect)

    var use = List[Bool](capacity=n)
    for _ in range(n):
        use.append(True)
    var out = _aipw_core(
        outcomes, treatment, scores, mu0, mu1, trim_eps,
        extreme_weight_threshold, use,
    )
    if out.status != CI_OK or not out.has_ate:
        return out^
    if out.has_se and z > 0.0:
        var lo = out.ate - z * out.se
        var hi = out.ate + z * out.se
        if ci_finite(lo) and ci_finite(hi):
            out.ci_lo = lo
            out.ci_hi = hi
            out.has_ci = True
    return out^


# ── strata_ate ───────────────────────────────────────────────────────────────


def strata_ate(
    outcomes: List[Float64], treatment: List[Int], strata: List[Int], n_strata: Int
) -> StrataAte:
    """Stratified ATE, reporting the strata it could not use instead of absorbing them.

    One pass over units with per-stratum accumulators, so the cost is O(n + n_strata) rather
    than the frozen kernel's O(n_strata * n) rescan.

    `n_strata <= len(outcomes)` is REQUIRED, and that is a payload tie rather than a
    convenience: a stratum needs at least one unit to be usable, so declaring more strata than
    units guarantees empties and means the count came from the caller's imagination rather than
    from the data (rule 1c — derive the dimension from the payload or reject the mismatch). Every
    `strata[i]` must lie in `[0, n_strata)`; `causal.stratified_ate` indexes `strata[i]` against
    nothing at all, and an out-of-range label there is silently ignored rather than reported.

    TWO estimates come back, and the second exists only as the differential oracle: `ate`
    renormalises the weights over the covered mass, while `ate_uncovered_as_zero` reproduces the
    frozen kernel's convention of dividing by the WHOLE sample. They are equal exactly when every
    stratum is usable, which the suite checks against `causal.stratified_ate` itself; when they
    differ, the difference is the bias the frozen convention introduces, and `covered_fraction`
    is its size.

    @capability strata_ate
    complexity: O(n + n_strata)
    counts:
    - n_strata <= len(outcomes) [kernel_validated]
    @endcapability
    """
    var n = len(outcomes)
    if n == 0:
        return StrataAte(CI_ERR_INSUFFICIENT_DATA)
    if len(treatment) != n or len(strata) != n:
        return StrataAte(CI_ERR_LENGTH_MISMATCH)
    if n_strata <= 0 or n_strata > n or n_strata > MAX_CI_UNITS:
        return StrataAte(CI_ERR_SHAPE)
    if not ci_all_finite(outcomes):
        return StrataAte(CI_ERR_NON_FINITE)
    var tdefect = ci_treatment_defect(treatment)
    if tdefect != CI_OK:
        return StrataAte(tdefect)
    for i in range(n):
        if strata[i] < 0 or strata[i] >= n_strata:
            return StrataAte(CI_ERR_INDEX)

    var sum_t = List[Float64](capacity=n_strata)
    var sum_c = List[Float64](capacity=n_strata)
    var cnt_t = List[Int](capacity=n_strata)
    var cnt_c = List[Int](capacity=n_strata)
    for _ in range(n_strata):
        sum_t.append(0.0)
        sum_c.append(0.0)
        cnt_t.append(0)
        cnt_c.append(0)
    for i in range(n):
        var s = strata[i]
        if treatment[i] == 1:
            sum_t[s] += outcomes[i]
            cnt_t[s] += 1
        else:
            sum_c[s] += outcomes[i]
            cnt_c[s] += 1

    var out = StrataAte(CI_OK)
    out.n_strata = n_strata
    out.n_units = n
    var weighted = 0.0
    for s in range(n_strata):
        var size = cnt_t[s] + cnt_c[s]
        out.stratum_n.append(size)
        out.stratum_n_treated.append(cnt_t[s])
        if cnt_t[s] > 0 and cnt_c[s] > 0:
            var a = sum_t[s] / Float64(cnt_t[s]) - sum_c[s] / Float64(cnt_c[s])
            if not ci_finite(a):
                return StrataAte(CI_ERR_NON_FINITE)
            out.stratum_ate.append(a)
            out.stratum_has_ate.append(True)
            out.n_usable += 1
            out.n_covered += size
            weighted += a * Float64(size)
        else:
            out.stratum_ate.append(0.0)
            out.stratum_has_ate.append(False)

    if out.n_usable == 0:
        out.status = CI_ERR_INSUFFICIENT_DATA
        return out^
    out.covered_fraction = Float64(out.n_covered) / Float64(n)
    out.is_full_sample = out.n_covered == n
    var ate = weighted / Float64(out.n_covered)
    var frozen_convention = weighted / Float64(n)
    if not ci_finite(ate) or not ci_finite(frozen_convention):
        return StrataAte(CI_ERR_NON_FINITE)
    out.ate = ate
    out.ate_uncovered_as_zero = frozen_convention
    out.has_ate = True
    return out^


# ── aipw_bootstrap_ci ────────────────────────────────────────────────────────


def aipw_bootstrap_ci(
    outcomes: List[Float64], treatment: List[Int], scores: List[Float64],
    mu0: List[Float64], mu1: List[Float64], n_replicates: Int,
    seed: Int, alpha: Float64,
) -> BootCI:
    """Percentile bootstrap interval for the doubly-robust ATE. Deterministic, addressed by seed.

    Units — not values — are resampled with replacement, carrying `(Y, T, e, mu0, mu1)` together,
    because the estimator is built on the unit-level association between them. Replicate `b`'s
    `k`-th draw is `uniform_int_keyed(0, n-1, seed, stream, b * n + k)` from the frozen
    counter-based generator, so it is a pure function of `(seed, b, k)` and of nothing that ran
    before it. The stream id is derived from the NAME "causal_inference.aipw_bootstrap" via
    `determinism.streams.stream_id` rather than picked as an integer: ids 1-7 are reserved and
    reusing one would silently change values another consumer already drew.

    That makes the interval reproducible bit for bit for a fixed seed, which the suite asserts —
    and it is the reason the resampling lives here rather than on `random_utils.random_choice`,
    which takes no seed at all and draws from process-global state.

    `mu0`/`mu1` are held FIXED across replicates. This is the fixed-nuisance bootstrap: it
    propagates the sampling variability of the estimating equation, not of the nuisance model
    fits, so it will understate uncertainty when those fits are themselves unstable. Stated
    because refitting per replicate is a different (and much more expensive) procedure, and a
    caller must know which one it has.

    `alpha` in (0, 1) gives the `[alpha/2, 1 - alpha/2]` percentile interval. Replicates whose
    resample contains no treated or no control unit have no ATE and are DROPPED with a count,
    never counted as zero; fewer than two surviving replicates is `CI_ERR_INSUFFICIENT_DATA`
    because a percentile of one number is not an interval.

    @capability aipw_bootstrap_ci
    complexity: O(n_replicates * n)
    counts:
    - dim n_replicates [kernel_validated]
    @endcapability
    """
    var n = len(outcomes)
    if n == 0:
        return BootCI(CI_ERR_INSUFFICIENT_DATA)
    if len(treatment) != n or len(scores) != n or len(mu0) != n or len(mu1) != n:
        return BootCI(CI_ERR_LENGTH_MISMATCH)
    if not ci_all_finite(outcomes) or not ci_all_finite(scores):
        return BootCI(CI_ERR_NON_FINITE)
    if not ci_all_finite(mu0) or not ci_all_finite(mu1):
        return BootCI(CI_ERR_NON_FINITE)
    # Two bounds, for the same reason: a product budget alone admits half a million replicates on
    # a two-unit sample, and each replicate allocates six n-length lists.
    if n_replicates < 2 or n_replicates > MAX_CI_ITERATIONS:
        return BootCI(CI_ERR_INVALID_PARAMETER)
    if not ci_finite(alpha) or alpha <= 0.0 or alpha >= 1.0:
        return BootCI(CI_ERR_INVALID_PARAMETER)
    if seed < 0:
        return BootCI(CI_ERR_INVALID_PARAMETER)
    var tdefect = ci_treatment_defect(treatment)
    if tdefect != CI_OK:
        return BootCI(tdefect)
    # Charged against the BOOTSTRAP's own ceiling, not the Newton fit's. `MAX_CI_FIT_WORK` is
    # calibrated for a ~1 ns multiply-accumulate inside an IRLS loop; a bootstrap draw allocates
    # six n-length lists per replicate and runs a keyed RNG call per unit, and MEASURING it gave
    # 98-141 ns per charged (replicate x unit) — 118-151 SECONDS at 2^30, against a comment
    # promising order-of-seconds. `MAX_CI_BOOTSTRAP_WORK` (2^24) was measured AT the ceiling:
    # 1.8-2.3 s. Borrowing a ceiling whose justification was written for a different inner loop
    # is not a budget, it is a coincidence.
    if not ci_product_fits(n_replicates, n, MAX_CI_BOOTSTRAP_WORK):
        return BootCI(CI_ERR_WORK_BUDGET)
    # Every score must be strictly interior BEFORE any replicate runs. A degenerate propensity
    # is a property of the data, not of a resample, so it is refused once here instead of
    # silently dropping every replicate that happens to include the offending unit.
    for i in range(n):
        var p = scores[i]
        if treatment[i] == 1 and p <= 0.0:
            return BootCI(CI_ERR_DEGENERATE_PROPENSITY)
        if treatment[i] == 0 and p >= 1.0:
            return BootCI(CI_ERR_DEGENERATE_PROPENSITY)

    var full_use = List[Bool](capacity=n)
    for _ in range(n):
        full_use.append(True)
    var point = _aipw_core(
        outcomes, treatment, scores, mu0, mu1, 0.0, 1.0e300, full_use
    )
    if point.status != CI_OK or not point.has_ate:
        return BootCI(point.status)

    var out = BootCI(CI_OK)
    out.n_replicates = n_replicates
    out.seed_used = seed
    var stream = stream_id(_BOOTSTRAP_STREAM_NAME)
    var master = UInt64(seed)
    var reps = List[Float64]()

    for b in range(n_replicates):
        var ry = List[Float64](capacity=n)
        var rt = List[Int](capacity=n)
        var re = List[Float64](capacity=n)
        var r0 = List[Float64](capacity=n)
        var r1 = List[Float64](capacity=n)
        var ruse = List[Bool](capacity=n)
        for k in range(n):
            var draw = UInt64(b) * UInt64(n) + UInt64(k)
            var idx = uniform_int_keyed(0, n - 1, master, stream, draw)
            if idx < 0 or idx >= n:
                # `uniform_int_keyed` clamps its own offset, so this is unreachable. Checked
                # rather than assumed: an out-of-range index here would be an uncatchable abort.
                return BootCI(CI_ERR_INDEX)
            ry.append(outcomes[idx])
            rt.append(treatment[idx])
            re.append(scores[idx])
            r0.append(mu0[idx])
            r1.append(mu1[idx])
            ruse.append(True)
        var rep = _aipw_core(ry, rt, re, r0, r1, 0.0, 1.0e300, ruse)
        if rep.status != CI_OK or not rep.has_ate:
            out.n_replicates_dropped += 1
            continue
        reps.append(rep.ate)
        out.n_replicates_used += 1

    if out.n_replicates_used < 2:
        out.status = CI_ERR_INSUFFICIENT_DATA
        return out^
    # Two sorts of a `n_replicates`-long list. Charging `n_replicates x n` bounds the DRAWING
    # loop above and says nothing at all about these two calls, whose cost is in `n_replicates`
    # ALONE — the shape of undercharge rule 4b names: a budget that counts only the product.
    # MEASURED at charges that are exactly at `MAX_CI_BOOTSTRAP_WORK`, so every one of them is
    # admitted, with `math_ext.quantile`'s O(B^2) insertion sort:
    #
    #     n = 1024, B = 16384    1.12 s
    #     n =  256, B = 65536    1.84 s
    #     n =   64, B = 262144   20.8 s
    #     n =   16, B = 1048576  353.9 s      <- six minutes, and the suite asserted it admitted
    #
    # The same four shapes through `stats.quantile`'s introsort: 0.70 s, 0.74 s, 0.99 s, 1.56 s.
    # The cost is now FLAT in the shape at a fixed charge, which is what a budget that charges
    # `n_replicates x n` is entitled to assume and previously could not.
    #
    # Neither the ceiling nor the hard `MAX_CI_ITERATIONS` cap could have caught this: both bound
    # `B`, and no bound on `B` that still permits an ordinary 10,000-replicate bootstrap keeps a
    # quadratic sort inside seconds. The fix is the O(B log B) frozen kernel, not a lower ceiling.
    var lo = stats_quantile(reps, len(reps), 0.5 * alpha)
    var hi = stats_quantile(reps, len(reps), 1.0 - 0.5 * alpha)
    var v = ext_variance(reps)
    if not ci_finite(lo) or not ci_finite(hi) or not ci_finite(v):
        return BootCI(CI_ERR_NON_FINITE)
    out.point = point.ate
    out.ci_lo = lo
    out.ci_hi = hi
    out.has_ci = True
    if v >= 0.0:
        var se = sqrt(v)
        if ci_finite(se):
            out.se_boot = se
            out.has_se = True
    return out^
