"""
inference.core — the shared substrate for the inference drivers. Zero Python imports.

What this module is for
-----------------------
Five things every driver in this package needs, in one place so there is ONE of each
(rule 3: a duplicated guard is worse than a missing one, because it reads as
defence-in-depth while providing one arbitrary behaviour per call site):

1. The package's single status vocabulary, 320-339, with a name per code.
2. The single finiteness predicate, `inference_finite`.
3. The single tolerance builder, `inference_scaled_tol` — see rule 4b below.
4. The single shape/allocation/work bound helpers, `inference_dims_fit` and
   `inference_product_fits`.
5. The tail probabilities every test in this package quotes, and the weighted
   least-squares solve every IRLS driver here iterates.

Status codes: 320-339 belong to the `inference` package
------------------------------------------------------
ONE vocabulary for the whole package, per rule 4e — `assume`, `resample`, `glm`, `robust`,
`multiplicity` and `power` all import these codes rather than allocating their own, because
`optimization` shipped `81` meaning two different things in one package and no caller could
tell which. All twenty codes 320-339 are assigned below and none is reused for a second
meaning. Nothing here touches `retrieval`'s 200-219 or `optimization`'s ranges.

WHY THIS MODULE CONTAINS AN INCOMPLETE-BETA IMPLEMENTATION
=========================================================
**Historical defect, fixed upstream as of this session** — recorded below rather than
deleted, per this package's own rule about a bound pinned to a box being a fact worth
keeping (see `docs/timing/FROZEN_SPECS.md`'s "saturation does not automatically mean the
bound is wrong" for the general principle this follows: a fixed defect is still worth
knowing the shape of). `stat_tests._regularized_incomplete_beta` WAS the tree's incomplete
beta AND defective, so every t-distribution and F-distribution tail computed from it was
wrong. The defect, reproduced exactly on the toolchain of the time:

    stat_tests._regularized_incomplete_beta(0.6, 3.0, 0.5)  ->  -0.02297233739032732

A regularized incomplete beta is a probability. `-0.023` was not one. The cause was not a
missing continued-fraction level as first suspected, but a first-term error: Lentz's
recurrence special-cases its very first convergent (only `d` is set from the leading term
and reciprocated; `c` stays at its initial 1.0 through that one step), and the frozen loop
folded that first term into the same uniform per-step update it used for every subsequent
term — updating `c` there too, which corrupted the running product. Measured consequences
in the frozen tree, on the toolchain of the time:

    stat_tests._t_cdf(2.0, 6.0)   ->  1.0114861686851442   (true 0.9537868442341706)
    stat_tests._t_cdf(1.0, 5.0)   ->  0.4318922414596...   (true 0.8183912661754367)
    stat_tests.t_test_2sample([1,2,3], [4,5,6])
        -> statistic -3.6742346141747673, p_value 0.0, reject_h0 True

That last line was the whole reason this package first existed. The true two-sided p for
Welch `t = -3.674` on `df = 4` is `0.0213`. The frozen kernel computed `2 * (1 - 1.0117...)`,
got a NEGATIVE p-value, and its own `if p_val < 0.0: p_val = 0.0` clamp turned it into
`p_value = 0.0` under `reject_h0 = True` — a confident wrong answer presented as certainty,
which is exactly what rule 4 exists to prevent. A CDF above 1 also made small-`t`
p-values exceed 1 and clamp to 1.0, so the same kernel both never rejected and always
rejected, depending on the region.

**`stat_tests._regularized_incomplete_beta` is fixed** (same continued fraction, corrected
first-term handling) and now agrees with this module's independent `inference_beta_inc` to
within the two implementations' own truncation error almost everywhere — against a
`-0.023`-vs-`0.674` scale of disagreement beforehand. "Almost everywhere" is precise, not
hedging: away from the continued fraction's branch-switch threshold the two settle within
`5.8e-11` of each other (swept `df` 1-5000, `t` -8..8), but hunting the narrow region right
at that threshold (see `t_cdf_agreement`'s docstring) found gaps up to `3.4e-7` — still six
orders of magnitude below the pre-fix defect and immaterial to any real p-value decision,
but real, so `t_cdf_agreement`'s tolerance is `1e-6`, not `1e-9`. `inference_beta_inc` and
the drivers built on it (`inference_t_cdf`, `inference_f_sf`, `inference_t_quantile`) are
KEPT, not deleted: they still add real capability `stat_tests.mojo` does not have at all
(F-distribution tails, t-quantile inversion, and region-switching away from the beta
continued fraction entirely in the extreme tails), so this package remains additive-correct
rather than redundant. `stat_tests.mojo` itself was not touched beyond the one-function fix
— every other frozen tail this module deliberately does not reimplement (below) is
unaffected. `t_cdf_agreement` and `assume.t_test_checked_flat`'s
`frozen_p_value`/`frozen_p_value_usable` still report the frozen value beside the corrected
one, now as a live cross-check between two independent implementations rather than as
documentation of a known-broken one.

Two frozen tails are NOT reimplemented, because they are correct and were checked:

* `stat_tests._chi2_cdf` — verified against the closed forms
  `sf(x; 1) = erfc(sqrt(x/2))` and `sf(x; 3) = erfc(sqrt(x/2)) + sqrt(2x/pi) e^{-x/2}`:
  `sf(3.841459; 1)` frozen `0.04999999465329685` vs closed `0.04999999465319576`, and
  `sf(20; 3)` frozen `1.6974243563983027e-4` vs closed `1.6974243555282643e-4`.
  `assume.expected_counts_flat` therefore calls the frozen `chi_squared_test`.
* `math_ext.norm_cdf` / `math_ext.norm_ppf` — the tree's most accurate normal pair
  (`norm_ppf` is Acklam, ~1.15e-9; `norm_cdf` measured 6.9e-8 at `z = 1.9599639845`).
  `power` and the Wald p-values in `glm` / `robust` call them unchanged.

`special_functions.log_gamma` is called unchanged for every log-gamma this module needs.

Rule 4b: the tolerance builder, and what it refuses to be
---------------------------------------------------------
`inference_scaled_tol(quantity_magnitude, abs_tol)` is
`abs_tol + INF_ULP_BUDGET * INF_DBL_EPSILON * |quantity_magnitude|`. The relative term is
sized by DBL_EPSILON — what floating point cannot represent AT that magnitude — and never
by the caller's tolerance (spelling 4), never by a sum or a max over other items
(spellings 1 and 2), and there is no `1 +` floor that could dominate a small real scale
(spelling 3). A caller passes the magnitude of THE ONE QUANTITY BEING JUDGED. Every use in
this package names that quantity in a comment beside the call.

A non-finite `quantity_magnitude` or `abs_tol` returns **-1.0**, which is not a tolerance:
every `error > tol` against it is TRUE, so the caller refuses instead of passing. That is
the opposite of the `nan` trap in rule 4d, where `dual_tol = SLOP * (1 + nan)` made every
comparison False and an audit passed having counted zero violations. Callers still validate
finiteness first; this is the second line, pointed the safe way.

Allocation and WORK arithmetic, per rule 1c and "bounding memory is not bounding work"
--------------------------------------------------------------------------------------
`sparse_numerics.csr.MAX_CSR_DIM` (2^26) is justified for ONE array of that length and is
never modified or inherited as this package's limit. Scaled-down ceilings, with the
arithmetic:

    MAX_INFERENCE_OBS    = 2^20    an IRLS pass holds eta, mu, w, z, resid, y, weights and
                                   one scratch per observation: 8 * 8 = 64 B/obs
                                   -> 67 MB, inside the 512 MiB single-object budget.
    MAX_INFERENCE_PARAMS = 2^8     X'WX is (p+1)^2 doubles plus its List[List] row headers:
                                   257^2 * 8 = 528 KB, plus the inverse in the SE path.
    MAX_RESAMPLES        = 2^20    one statistic per resample plus a merge buffer:
                                   2 * 2^20 * 8 = 17 MB.
    MAX_ASSUME_OBS       = 2^12    SMALL on purpose, and the reason is WORK, not memory:
                                   the frozen per-group median (`stats_bootstrap._median`)
                                   and the frozen normality tests insertion-sort, so they
                                   are O(m^2). One group of 2^12 is 1.7e7 comparisons; 2^20
                                   would be 1.1e12 — a hang, which from the caller's side is
                                   the same outcome as rule 1's uncatchable abort.
    MAX_TESTS            = 2^20    p-values plus ranks plus adjusted values: 4 * 8 = 32 B.
    MAX_SAMPLE_SIZE      = 2^28    allocates nothing; it bounds the ANSWER a sample-size
                                   driver may return, so an unreachable target power is a
                                   refusal rather than a number nobody can act on.

Every dimension is ALSO bounded against what the payload contains, which is the half of
rule 1c a ceiling does not cover: `inference_dims_fit(n, p, len(x))` requires the design
matrix to hold exactly `n * p` cells (checked by DIVISION inside
`sparse_numerics.csr.dims_fit`, because `n * p == len(x)` is a wrapping multiply and
`3 * 6148914691236517206 == 2`), and every driver requires `len(y) == n` exactly rather
than looping over the smaller of the two.

Two work budgets are charged as PRODUCTS, because a budget that counts one factor of a
product is not a budget:

    MAX_IRLS_WORK     bounds  max_iter * n * (p+1) * (p+1)   — the whole IRLS cost
    MAX_RESAMPLE_WORK bounds  n_resamples * n * (n if the statistic sorts else 1)

both formed with `inference_product_fits`, which never materialises the product.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_inference_core.mojo
benchmark: benchmarks/mojo_benchmarks/bench_inference.mojo
docs: none
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs, exp, isinf, isnan, log, sqrt

from linalg import mat_from_list
from linalg_ext import mat_is_positive_definite
from linear_models import _solve_linear_system
from special_functions import log_gamma
from sparse_numerics.csr import MAX_CSR_DIM, dims_fit


# ── status vocabulary: 320-339, all twenty assigned, none reused ───────────────
comptime INF_OK: Int = 320
comptime INF_ERR_SHAPE: Int = 321
comptime INF_ERR_DIMENSION_TOO_LARGE: Int = 322
comptime INF_ERR_NON_FINITE: Int = 323
comptime INF_ERR_EMPTY: Int = 324
comptime INF_ERR_TOO_FEW: Int = 325
comptime INF_ERR_ALPHA_RANGE: Int = 326
comptime INF_ERR_RESAMPLE_COUNT: Int = 327
comptime INF_ERR_NOT_CONVERGED: Int = 328
comptime INF_ERR_SEPARABLE: Int = 329
comptime INF_ERR_RANK_DEFICIENT: Int = 330
comptime INF_ERR_RESPONSE_RANGE: Int = 331
comptime INF_ERR_GROUPS: Int = 332
comptime INF_ERR_PVALUE_RANGE: Int = 333
comptime INF_ERR_TUNING: Int = 334
comptime INF_ERR_EFFECT_ZERO: Int = 335
comptime INF_ERR_WEIGHTS: Int = 336
comptime INF_ERR_DIVERGED: Int = 337
comptime INF_ERR_NOT_SYMMETRIC: Int = 338
comptime INF_ERR_DEGENERATE: Int = 339

# ── tolerance construction (rule 4b) ─────────────────────────────────────────
comptime INF_DBL_EPSILON: Float64 = 2.220446049250313e-16
# Accumulated-rounding headroom in units of DBL_EPSILON, NOT a slop the caller chose. An
# IRLS normal-equations row sums n products, so the error grows like sqrt(n) * eps *
# magnitude; 256 ulps covers n up to ~65536 with a decade to spare and keeps the whole
# relative allowance at ~5.7e-14, far below any real disagreement.
comptime INF_ULP_BUDGET: Float64 = 256.0

# A tolerance that cannot be built. Every `error > INF_TOL_UNDEFINED` is True for finite
# error, so a caller refuses rather than passes. See the module docstring.
comptime INF_TOL_UNDEFINED: Float64 = -1.0

# ── ceilings; arithmetic in the module docstring, asserted in the suite ────────
comptime MAX_INFERENCE_OBS: Int = 1 << 20
comptime MAX_INFERENCE_PARAMS: Int = 1 << 8
comptime MAX_RESAMPLES: Int = 1 << 20
comptime MAX_ASSUME_OBS: Int = 1 << 12
comptime MAX_TESTS: Int = 1 << 20
comptime MAX_SAMPLE_SIZE: Int = 1 << 28
comptime MAX_IRLS_WORK: Int = 1 << 30
comptime MAX_RESAMPLE_WORK: Int = 1 << 28

# Iteration caps a caller may not exceed. A cap is not a convergence proof (rule 4), so
# hitting one is INF_ERR_NOT_CONVERGED and carries no coefficients.
comptime MAX_IRLS_ITER: Int = 1000
# Bisection steps for `inference_t_quantile`. 200 halvings of a [-1e4, 1e4] bracket is
# 2e4 * 2^-200, i.e. exact to the last representable double, so this is a work bound and
# never an accuracy limit.
comptime T_QUANTILE_STEPS: Int = 200
comptime T_QUANTILE_BRACKET: Float64 = 1.0e4

# ── the t tails' three regions ────────────────────────────────────────────────
#
# ONE allocation of the region codes, named by `inference_t_tail_region`, whose docstring
# carries the whole argument for why a single formula cannot cover the range. Every constant
# below is a threshold in that argument and none is a tuned slop.
comptime T_REGION_ABSENT: Int = -1
comptime T_REGION_BETA: Int = 0
comptime T_REGION_CENTRAL: Int = 1
comptime T_REGION_NORMAL: Int = 2

# `1 - x = t^2/(df + t^2)` below this has lost more than half of its 16 digits, so the
# incomplete beta is being handed an `x` that no longer carries the answer. 1e-8 is that
# half-way point exactly: at `1 - x = 1e-8` the surviving relative accuracy is
# DBL_EPSILON/1e-8 = 2.2e-8, and it degrades to nothing (x == 1.0 exactly) below ~1e-16.
comptime T_TAIL_COMPLEMENT_FLOOR: Float64 = 1.0e-8

# The central series alternates, so it loses `exp(t^2)` ulps to cancellation: 90 ulps
# (2e-14 relative) at |t| = 3, and everything by |t| = 6. Past this cap the complement being
# below the floor forces `df > 8.99e8`, where the normal is the accurate answer.
comptime T_TAIL_SERIES_MAX_T: Float64 = 3.0

# A WORK bound on the central series, not an accuracy limit: terms fall factorially once
# `j > t^2/2`, and 35 terms suffice at the |t| = 3 cap. An unconverged sum is ABSENT.
comptime T_TAIL_SERIES_TERMS: Int = 64
# Relative floor for "this term no longer moves the partial sum", judged against the partial
# sum's OWN magnitude. Below DBL_EPSILON on purpose: it is a stopping rule for an exactly
# representable comparison, not a tolerance on an answer.
comptime T_TAIL_SERIES_REL: Float64 = 1.0e-18

# Above this `df`, `log_gamma(df/2)` is too large for its own difference to survive: the
# cancellation error is DBL_EPSILON * log_gamma(df/2) in an EXPONENT. Below it, the
# asymptotic series' first omitted term is the larger error. See `_t_density_at_zero`.
comptime T_TAIL_F0_ASYMPTOTIC_DF: Float64 = 1.0e4

comptime INF_PI: Float64 = 3.141592653589793
comptime INF_INV_SQRT_2PI: Float64 = 0.3989422804014327


def inference_status_name(code: Int) -> String:
    """Name for a status code, so an error surfaces the defect and not a bare number."""
    if code == INF_OK:
        return "ok"
    if code == INF_ERR_SHAPE:
        return "declared_shape_does_not_match_payload"
    if code == INF_ERR_DIMENSION_TOO_LARGE:
        return "dimension_or_work_exceeds_inference_ceiling"
    if code == INF_ERR_NON_FINITE:
        return "non_finite_input"
    if code == INF_ERR_EMPTY:
        return "no_observations"
    if code == INF_ERR_TOO_FEW:
        return "too_few_observations_for_this_estimate"
    if code == INF_ERR_ALPHA_RANGE:
        return "alpha_or_confidence_outside_open_unit_interval"
    if code == INF_ERR_RESAMPLE_COUNT:
        return "resample_count_not_positive_or_above_ceiling"
    if code == INF_ERR_NOT_CONVERGED:
        return "iteration_cap_reached_without_convergence"
    if code == INF_ERR_SEPARABLE:
        return "separable_data_so_the_mle_does_not_exist"
    if code == INF_ERR_RANK_DEFICIENT:
        return "information_matrix_not_positive_definite"
    if code == INF_ERR_RESPONSE_RANGE:
        return "response_outside_the_range_this_family_admits"
    if code == INF_ERR_GROUPS:
        return "group_lengths_do_not_describe_the_payload"
    if code == INF_ERR_PVALUE_RANGE:
        return "a_value_offered_as_a_p_value_is_not_a_probability"
    if code == INF_ERR_TUNING:
        return "tuning_or_target_argument_out_of_range"
    if code == INF_ERR_EFFECT_ZERO:
        return "no_sample_size_detects_a_zero_effect"
    if code == INF_ERR_WEIGHTS:
        return "non_positive_weight"
    if code == INF_ERR_DIVERGED:
        return "iterate_left_the_representable_range"
    if code == INF_ERR_NOT_SYMMETRIC:
        return "normal_equations_matrix_is_not_symmetric"
    if code == INF_ERR_DEGENERATE:
        return "the_statistic_has_no_value_for_this_input"
    return "unknown"


def inference_finite(v: Float64) -> Bool:
    """True for a real number: neither NaN nor +-inf.

    PUBLIC on purpose, and the SINGLE definition of "finite" for this package — every other
    module here imports it. `optimization.model.model_finite` is the same predicate for the
    optimization package and is deliberately not imported: reaching it drags `expr`,
    `query.ir` and the LP model container into a statistics path. Two definitions in one
    package is the defect rule 3 names; two definitions in two packages with no shared
    dependency is not.
    """
    return not (isnan(v) or isinf(v))


def inference_absent() -> Float64:
    """The value that means "this number does not exist": a quiet NaN.

    Used only by the SCALAR tail functions here, where there is no room for a status field.
    NaN is outside the range of every one of them — a probability, a quantile and a
    tolerance are all real numbers — so it cannot be confused with an answer, and
    `inference_finite` is the test for it. Every driver in this package returns a STATUS
    instead, per rule 4; this exists so the scalar helpers do not have to return 0.0.
    """
    var zero: Float64 = 0.0
    return zero / zero


def inference_scaled_tol(quantity_magnitude: Float64, abs_tol: Float64) -> Float64:
    """`abs_tol + 256 * DBL_EPSILON * |quantity_magnitude|` — rule 4b, in one place.

    `quantity_magnitude` must be the magnitude of THE ONE QUANTITY BEING JUDGED, never a
    sum or a maximum over other items and never a `1 + |x|` floor. Returns
    `INF_TOL_UNDEFINED` (-1.0) for a non-finite or negative input, which every
    `error > tol` test reads as "refuse".
    """
    return inference_scaled_tol_ulps(quantity_magnitude, abs_tol, 0.0)


def inference_scaled_tol_ulps(
    quantity_magnitude: Float64, abs_tol: Float64, extra_ulps: Float64
) -> Float64:
    """`abs_tol + (256 + extra_ulps) * DBL_EPSILON * |quantity_magnitude|`.

    `extra_ulps` exists for one situation only: a quantity assembled by a KNOWN number of
    floating-point additions, where the rounding that can accumulate genuinely grows with
    that count. `optimization.explain` sets the precedent —
    `(LP_FEAS_ULP_BUDGET + Float64(additions)) * LP_DBL_EPSILON * magnitude` — and
    `wls_solve_flat` uses it with `extra_ulps = p`, one ulp per elimination step in the row
    being verified.

    It is NOT a way to widen a tolerance until a test passes: `extra_ulps` must be an
    operation COUNT the caller can name, and it still multiplies DBL_EPSILON and the judged
    quantity's own magnitude, never the caller's tolerance (rule 4b, spelling 4). A negative
    `extra_ulps` returns `INF_TOL_UNDEFINED`, so it cannot be used to tighten either.
    """
    if not inference_finite(quantity_magnitude) or not inference_finite(abs_tol):
        return INF_TOL_UNDEFINED
    if not inference_finite(extra_ulps) or extra_ulps < 0.0:
        return INF_TOL_UNDEFINED
    if abs_tol < 0.0:
        return INF_TOL_UNDEFINED
    var ulps = INF_ULP_BUDGET + extra_ulps
    return abs_tol + ulps * INF_DBL_EPSILON * fabs(quantity_magnitude)


def inference_product_fits(a: Int, b: Int, limit: Int) -> Bool:
    """True when `a * b <= limit`, decided with a DIVISION so nothing multiplies.

    `a * b` is a wrapping 64-bit multiply, so comparing the product to a limit is not a
    bound at all: `3 * 6148914691236517206 == 2`. This is `sparse_numerics.csr.dims_fit`'s
    trick generalised to an arbitrary limit, and it is how every memory AND work budget in
    this package is charged.
    """
    if a < 0 or b < 0 or limit < 0:
        return False
    if a == 0 or b == 0:
        return True
    return a <= limit // b


def inference_product3_fits(a: Int, b: Int, c: Int, limit: Int) -> Bool:
    """True when `a * b * c <= limit`, growing the product factor by factor.

    Never forms a product larger than `limit`: if `a * b` already exceeds it the answer is
    False before `c` is looked at, so no intermediate can wrap.
    """
    if a < 0 or b < 0 or c < 0 or limit < 0:
        return False
    if a == 0 or b == 0 or c == 0:
        return True
    if not inference_product_fits(a, b, limit):
        return False
    return a * b <= limit // c


def inference_dims_fit(n_rows: Int, n_cols: Int, length: Int) -> Bool:
    """True when a flat row-major design matrix of `length` cells really is `n_rows x n_cols`.

    Delegates the wrapping-safe product to the frozen `sparse_numerics.csr.dims_fit` and
    then applies THIS package's scaled-down ceilings on top, because `MAX_CSR_DIM` is
    justified for one array and an IRLS pass allocates eight per observation (see the
    module docstring). `n_cols == 0` with an empty matrix is admitted on purpose: an
    intercept-only GLM has no covariate columns, and its answer is `log` of the response
    mean — a real model, not a malformed request.
    """
    if n_rows > MAX_INFERENCE_OBS or n_cols > MAX_INFERENCE_PARAMS:
        return False
    return dims_fit(n_rows, n_cols, length)


def inference_ceilings() -> List[Int]:
    """Every ceiling this package enforces, so a caller can read them instead of guessing.

    Order: obs, params, resamples, assume_obs, tests, sample_size, irls_work,
    resample_work, MAX_CSR_DIM. The last entry is the shared outer limit, reported so the
    suite can assert that every ceiling here is strictly below it rather than trusting a
    comment. Deterministic, zero-argument.
    """
    var out = List[Int]()
    out.append(MAX_INFERENCE_OBS)
    out.append(MAX_INFERENCE_PARAMS)
    out.append(MAX_RESAMPLES)
    out.append(MAX_ASSUME_OBS)
    out.append(MAX_TESTS)
    out.append(MAX_SAMPLE_SIZE)
    out.append(MAX_IRLS_WORK)
    out.append(MAX_RESAMPLE_WORK)
    out.append(MAX_CSR_DIM)
    return out^


# ── tail probabilities ───────────────────────────────────────────────────────


def inference_beta_inc(x: Float64, a: Float64, b: Float64) -> Float64:
    """The regularized incomplete beta `I_x(a, b)`, or `inference_absent()`.

    ADDITIVE, correct, and now — as of this session — independently corroborating rather
    than merely correcting: `stat_tests._regularized_incomplete_beta` was defective and is
    fixed. See the module docstring for the full history: the frozen kernel used to return
    `-0.02297233739032732` for `I_0.6(3, 0.5)`, which made `_t_cdf(2, 6)` equal
    `1.0114861686851442` and drove `t_test_2sample` to a clamped `p_value = 0.0` under
    `reject_h0 = True`. Both are gone; the two implementations now agree to ~1e-11 away from
    the continued fraction's branch-switch threshold, and to ~1e-7 in the narrow region
    right at it (see `t_cdf_agreement`'s docstring).

    Lentz's algorithm, with the symmetry swap done ITERATIVELY (one flag, no recursion)
    per the dialect preference, and `special_functions.log_gamma` called unchanged for the
    log-beta prefactor.

    Rule 4: the returned value must BE a probability. A converged result outside
    `[0, 1]` by more than `inference_scaled_tol(1.0, 0.0)` is not one, so it is reported
    absent rather than clamped into range — clamping is what turned the frozen defect into
    a confident answer. Inside that allowance the value is clamped, because there a
    departure from `[0, 1]` really is the last bit of a probability that equals 0 or 1.
    """
    if not inference_finite(x) or not inference_finite(a) or not inference_finite(b):
        return inference_absent()
    if a <= 0.0 or b <= 0.0:
        return inference_absent()
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0

    var xx = x
    var aa = a
    var bb = b
    var flip = False
    # The continued fraction converges quickly only on the smaller side of the mode; the
    # identity I_x(a,b) = 1 - I_{1-x}(b,a) moves the evaluation there.
    if x > (a + 1.0) / (a + b + 2.0):
        xx = 1.0 - x
        aa = b
        bb = a
        flip = True

    var lbeta = log_gamma(aa) + log_gamma(bb) - log_gamma(aa + bb)
    var front = exp(log(xx) * aa + log(1.0 - xx) * bb - lbeta) / aa
    if not inference_finite(front):
        return inference_absent()

    var f: Float64 = 1.0
    var c: Float64 = 1.0
    var d: Float64 = 0.0
    # i = 0 carries numerator 1.0 and is THE level the frozen kernel skips.
    for i in range(0, 201):
        var m = i // 2
        var mf = Float64(m)
        var numerator: Float64
        if i == 0:
            numerator = 1.0
        elif i % 2 == 0:
            numerator = (mf * (bb - mf) * xx) / ((aa + 2.0 * mf - 1.0) * (aa + 2.0 * mf))
        else:
            numerator = -(
                (aa + mf) * (aa + bb + mf) * xx
            ) / ((aa + 2.0 * mf) * (aa + 2.0 * mf + 1.0))

        d = 1.0 + numerator * d
        if fabs(d) < 1e-30:
            d = 1e-30
        d = 1.0 / d
        c = 1.0 + numerator / c
        if fabs(c) < 1e-30:
            c = 1e-30
        f *= c * d
        if fabs(c * d - 1.0) < 1e-14:
            break

    var value = front * (f - 1.0)
    if not inference_finite(value):
        return inference_absent()
    if flip:
        value = 1.0 - value
    # The quantity judged is `value` itself, a probability, so its own magnitude is 1.
    var slop = inference_scaled_tol(1.0, 0.0)
    if value < -slop or value > 1.0 + slop:
        return inference_absent()
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _t_density_at_zero(df: Float64) -> Float64:
    """`f_df(0) = Gamma((df+1)/2) / (sqrt(df pi) Gamma(df/2))`, or `inference_absent()`.

    TWO routes, because each one is destroyed at the other's end of the range and there is
    no single expression that is right everywhere:

    * `df < T_TAIL_F0_ASYMPTOTIC_DF`: the log-gamma difference, evaluated with the frozen
      `special_functions.log_gamma`. Exact to a few ulps while `log_gamma(df/2)` is small.
    * `df >= T_TAIL_F0_ASYMPTOTIC_DF`: the ASYMPTOTIC series, because the log-gamma
      difference stops being computable long before `df` runs out. `log_gamma(df/2)` grows
      like `(df/2) log(df/2)` while the difference it forms is only `-0.5 log(df/2)`, so the
      cancellation error is `DBL_EPSILON * log_gamma(df/2)` in the EXPONENT. MEASURED on this
      toolchain against the asymptotic form: 9.4e-12 relative at `df = 1e4`, 5.5e-10 at
      `df = 1e6`, 8.1e-7 at `df = 1e9` — the log-gamma route is the wrong one there, not the
      series. `Gamma(z+1/2)/Gamma(z) = sqrt(z) (1 - 1/(8z) + 1/(128 z^2) + O(z^-3))` at
      `z = df/2` gives `f(0) = (1/sqrt(2 pi)) (1 - 1/(4 df) + 1/(32 df^2) + O(df^-3))`, whose
      first omitted term is `5/(1024 z^3)` = 3.9e-14 relative at the crossover.

    The crossover is therefore where BOTH routes are good to ~1e-11 relative, which for a
    quantity multiplied by a mass of at most 0.5 is at most 5e-12 absolute.
    """
    if not inference_finite(df) or df <= 0.0:
        return inference_absent()
    if df >= T_TAIL_F0_ASYMPTOTIC_DF:
        var inv = 1.0 / df
        return INF_INV_SQRT_2PI * (1.0 - 0.25 * inv + inv * inv / 32.0)
    var v = exp(
        log_gamma(0.5 * (df + 1.0)) - log_gamma(0.5 * df) - 0.5 * log(df * INF_PI)
    )
    if not inference_finite(v) or v <= 0.0:
        return inference_absent()
    return v


def _normal_cdf_clamped(t: Float64) -> Float64:
    """`Phi(t)` from the frozen `math_ext.norm_cdf`, or `inference_absent()`.

    The same frozen kernel `inference_norm_sf_two_sided` calls, imported at function scope
    for the same reason it is there: `math_ext` is reached for this one function and nothing
    else in this module needs it. A value outside `[0, 1]` is clamped, because for a CDF the
    only way out of range is the frozen erf approximation's last digits (measured 6.9e-8 at
    `z = 1.9599639845`), and a probability is what the caller is owed.
    """
    from math_ext import norm_cdf

    if not inference_finite(t):
        return inference_absent()
    var p = norm_cdf(t)
    if not inference_finite(p):
        return inference_absent()
    if p < 0.0:
        return 0.0
    if p > 1.0:
        return 1.0
    return p


def inference_t_tail_region(t: Float64, df: Float64) -> Int:
    """Which of the three regions `(t, df)` falls in — the t tails' branch geometry, exported.

    PUBLIC so the region is a value a caller (and the suite) can assert, rather than a
    branch nobody outside this file can see. `T_REGION_ABSENT` for an out-of-domain input.

    WHY THERE IS MORE THAN ONE REGION
    ---------------------------------
    The two-tail mass is `I_x(df/2, 1/2)` at `x = df/(df + t^2)`, and everything the answer
    depends on lives in the COMPLEMENT `1 - x = t^2/(df + t^2)`. `inference_beta_inc` takes
    `x`, so forming `x` keeps only what its last bits can still express about the complement.
    Once `t^2` falls below half an ulp of `df`, `df + t^2` IS `df`, `x` is exactly 1.0,
    `inference_beta_inc(1.0, a, b)` returns exactly 1.0 by its own early return, and the
    two-sided p-value is exactly 1.0 for EVERY `t` in that region. MEASURED on this
    toolchain before this fix existed:

        inference_t_sf_two_sided(1.0, 1.0e16)   ->  1.0   (true 0.31731050786291415)
        inference_t_cdf(1.0, 1.0e16)            ->  0.5   (true 0.8413447460685429)
        inference_t_sf_two_sided(0.25, 1.0e15)  ->  1.0   (true 0.8025873486341526)

    A p-value of exactly 1.0 where the truth is 0.32 is a silent non-rejection, and it
    arrives under no status at all because these are scalar helpers. Note that the
    saturation begins BEFORE `x` reaches 1.0 — at `df = 1e15, t = 0.25`, `x` is
    `0.9999999999999999` and the continued fraction still returns 1.0 — so widening the
    `x >= 1.0` early return would not close it. The information is gone when `x` is formed,
    which is why the fix is a different formula and not a wider guard.

    THE THREE REGIONS
    -----------------
    * `T_REGION_BETA` — `1 - x >= T_TAIL_COMPLEMENT_FLOOR` (1e-8), i.e. the complement still
      has at least half of its 16 digits. The incomplete beta, unchanged, exactly as before.
    * `T_REGION_CENTRAL` — the complement is below the floor and `|t| <= T_TAIL_SERIES_MAX_T`.
      The CENTRAL Taylor series in `_t_central_mass`, which never forms `x` at all.
    * `T_REGION_NORMAL` — the complement is below the floor and `|t| > T_TAIL_SERIES_MAX_T`.
      That pairing forces `df` to be enormous: `t^2 < FLOOR * (df + t^2)` rearranges to
      `df > t^2 (1 - FLOOR) / FLOOR`, so `|t| > 3` implies `df > 8.99e8`. There the t IS the
      normal to `0.16/df < 2e-10` (the Edgeworth term `phi(t)(t^3+t)/(4 df)`, whose
      coefficient maximises at 0.1582 near `t = 1.554` — computed, not assumed), so the
      answer is THE package's normal tail. Measured agreement at the handoff: the central
      series at `t = 3, df = 9e8` is `0.9986501019314376` against the normal's
      `0.9986501019683699`, a gap of 3.7e-11, matching the Edgeworth prediction of 3.7e-11.
      Returning the package's own normal also means a t test on 1e9 degrees of freedom and a
      Wald z test on the same statistic agree EXACTLY rather than in their last digits.
    """
    if not inference_finite(t) or not inference_finite(df) or df <= 0.0:
        return T_REGION_ABSENT
    var at = fabs(t)
    var at2 = at * at
    var denom = df + at2
    # An overflowed `t^2` is a `|t|` so large that the complement is 1 to every digit: the
    # incomplete beta at x = 0 is exactly 0 and that is the right answer, not a degradation.
    if not inference_finite(at2) or not inference_finite(denom) or denom <= 0.0:
        return T_REGION_BETA
    if at2 / denom >= T_TAIL_COMPLEMENT_FLOOR:
        return T_REGION_BETA
    if at > T_TAIL_SERIES_MAX_T:
        return T_REGION_NORMAL
    return T_REGION_CENTRAL


def _t_central_mass(at: Float64, df: Float64) -> Float64:
    """`P(0 <= T <= at)` for `at >= 0`, from the CENTRAL series, or `inference_absent()`.

    Not the incomplete beta and not the normal: the t density's own Taylor series, which
    never forms `df/(df + at^2)` and so cannot lose the complement.

        f_df(u) = f_df(0) (1 + u^2/df)^(-(df+1)/2)
        (1 + z)^(-m) = sum_j c_j z^j    with   c_0 = 1,  c_j = -c_{j-1} (m + j - 1) / j
        =>  P(0 <= T <= at) = f_df(0) * sum_j [ c_j / df^j ] at^(2j+1) / (2j+1)

    with `m = (df+1)/2`. The coefficient recurrence is applied with the `df^j` folded in
    (`coef = -coef * (m + j - 1) / (j * df)`) so no intermediate is ever raised to a power.

    WHY THIS CONVERGES FOR EVERY `df`: the term ratio is `(m + j - 1) at^2 / (j df)`, and
    `m/df -> 1/2`, so it behaves like `at^2 / (2j)` — the series of `exp(-at^2/2)`, which is
    the normal integral it must become as `df -> inf`. Terms grow while `j < at^2/2` and then
    fall factorially, so `T_TAIL_SERIES_TERMS` (64) is a WORK bound and not an accuracy
    limit for the `|at| <= T_TAIL_SERIES_MAX_T` region this is called on: measured term counts
    are 1 at `at = 1e-9`, 7 at `at = 0.1`, 15 at `at = 1`, 35 at `at = 3`.

    WHY `|at|` IS CAPPED AT 3 rather than trusted to the term budget: the series ALTERNATES,
    so its largest term is of order `exp(at^2/2)` while the sum is of order `exp(-at^2/2)`,
    and the cancellation costs `exp(at^2)` ulps of relative accuracy. At `at = 3` that is 90
    ulps (2e-14 relative); at `at = 6` it is 4e15 ulps, i.e. nothing left. Beyond the cap the
    caller is in `T_REGION_NORMAL`, where `df` is provably above 8.99e8 (see
    `inference_t_tail_region`) and the normal is the accurate answer anyway.

    An unconverged sum is ABSENT rather than a truncated partial: a mass is a probability and
    a truncated alternating series is not one. Same for a sum outside `[0, 0.5]` by more than
    one `inference_scaled_tol(1.0, 0.0)` — inside that allowance it is clamped, because there
    the departure is the last bit of a mass that equals 0 or 0.5.

    MEASURED against elementary closed forms, all in the region where the incomplete-beta
    path returns exactly 1.0 for the two-tail mass:

        at = 1e-9, df = 1     0.5 + mass = 0.5000000003183099   Cauchy, exact to 0 ulp
        at = 3e-8, df = 1     0.5 + mass = 0.5000000095492966   Cauchy, exact to 0 ulp
        at = 1e-6, df = 2     0.5 + mass = 0.5000003535533906   df=2 closed form, 0 ulp
        at = 1e-4, df = 3     0.5 + mass = 0.5000367552596131   df=3 closed form, 0 ulp
        at = 1,    df = 1e16  0.5 + mass = 0.841344746068543     normal, gap 1.1e-16
    """
    if at < 0.0 or not inference_finite(at) or not inference_finite(df) or df <= 0.0:
        return inference_absent()
    var f0 = _t_density_at_zero(df)
    if not inference_finite(f0):
        return inference_absent()
    var m = 0.5 * (df + 1.0)
    var at2 = at * at
    if not inference_finite(at2):
        return inference_absent()
    var total = at
    var power = at
    var coef: Float64 = 1.0
    var converged = False
    for j in range(1, T_TAIL_SERIES_TERMS + 1):
        var jf = Float64(j)
        coef = -coef * (m + jf - 1.0) / (jf * df)
        power *= at2
        var term = coef * power / (2.0 * jf + 1.0)
        if not inference_finite(term):
            return inference_absent()
        total += term
        # The judged quantity is the partial sum itself, so the floor is sized by that sum's
        # own magnitude times a fraction of DBL_EPSILON — never by a caller's tolerance.
        if fabs(term) <= T_TAIL_SERIES_REL * fabs(total):
            converged = True
            break
    if not converged:
        return inference_absent()
    var mass = f0 * total
    if not inference_finite(mass):
        return inference_absent()
    # The quantity judged is a probability mass whose own ceiling is 0.5, so magnitude 1.
    var slop = inference_scaled_tol(1.0, 0.0)
    if mass < -slop or mass > 0.5 + slop:
        return inference_absent()
    if mass < 0.0:
        return 0.0
    if mass > 0.5:
        return 0.5
    return mass


def inference_t_cdf(t: Float64, df: Float64) -> Float64:
    """`P(T <= t)` for Student's t on `df` degrees of freedom, or `inference_absent()`.

    `I_{df/(df+t^2)}(df/2, 1/2)` is the two-tail mass, halved and oriented by the sign of
    `t`. Verified against two closed forms in the suite: `df = 1` is Cauchy, so
    `P(T <= t) = 1/2 + atan(t)/pi`, and `df = 2` inverts to
    `t = (2p-1) sqrt(2 / (1 - (2p-1)^2))`.

    That is the `T_REGION_BETA` formula, and it is not used everywhere: see
    `inference_t_tail_region` for the region where forming `df/(df + t^2)` destroys the only
    part of the input the answer depends on, and what is computed instead. In the central
    region the CDF is assembled as `0.5 +- P(0 <= T <= |t|)` rather than as
    `1 - 0.5 * two_tail`, so the offset from 0.5 keeps its own relative accuracy instead of
    inheriting the rounding of a number near 1.
    """
    if not inference_finite(t) or not inference_finite(df):
        return inference_absent()
    if df <= 0.0:
        return inference_absent()
    var region = inference_t_tail_region(t, df)
    if region == T_REGION_CENTRAL:
        var mass = _t_central_mass(fabs(t), df)
        if not inference_finite(mass):
            return inference_absent()
        if t >= 0.0:
            return 0.5 + mass
        return 0.5 - mass
    if region == T_REGION_NORMAL:
        return _normal_cdf_clamped(t)
    var x = df / (df + t * t)
    var two_tail = inference_beta_inc(x, df / 2.0, 0.5)
    if not inference_finite(two_tail):
        return inference_absent()
    if t >= 0.0:
        return 1.0 - 0.5 * two_tail
    return 0.5 * two_tail


def inference_t_sf_two_sided(t: Float64, df: Float64) -> Float64:
    """`P(|T| >= |t|)` — the two-sided t p-value, or `inference_absent()`.

    Returned as `I_{df/(df+t^2)}(df/2, 1/2)` DIRECTLY rather than as
    `2 * (1 - inference_t_cdf(t, df))`. The direct form is the two-tail mass by
    construction, so it cannot exceed 1 or fall below 0 through cancellation, and it keeps
    its relative accuracy in the far tail where `1 - cdf` has none. That cancellation is
    also the shape of the frozen defect: `2 * (1 - 1.0114861686851442)` is negative.

    Regions exactly as in `inference_t_cdf`, decided by the same
    `inference_t_tail_region`, so the two functions cannot disagree about which formula
    `(t, df)` belongs to. `1 - 2 * mass` in the central region is not the cancellation this
    docstring warns about: there `mass` is a SMALL central mass computed to its own relative
    accuracy, so the subtraction is exact to half an ulp of 1 — unlike `2 * (1 - cdf)`, where
    the quantity subtracted is itself near 1 and its low bits are already gone.
    """
    if not inference_finite(t) or not inference_finite(df):
        return inference_absent()
    if df <= 0.0:
        return inference_absent()
    var region = inference_t_tail_region(t, df)
    if region == T_REGION_CENTRAL:
        var mass = _t_central_mass(fabs(t), df)
        if not inference_finite(mass):
            return inference_absent()
        return 1.0 - 2.0 * mass
    if region == T_REGION_NORMAL:
        return inference_norm_sf_two_sided(t)
    return inference_beta_inc(df / (df + t * t), df / 2.0, 0.5)


def inference_f_sf(f: Float64, df1: Float64, df2: Float64) -> Float64:
    """Upper tail `P(F >= f)` for `F(df1, df2)`, or `inference_absent()`.

    `I_{df2/(df2 + df1 f)}(df2/2, df1/2)`, with the `df1 = 1` degenerate region routed
    through the t. Verified in the suite against the closed form
    `P(F_{1,6} >= 3) = (2 - sqrt(3)) / 2` and against the exact identity
    `P(F_{1,d} >= t^2) = P(|T_d| >= |t|)`.

    THE SAME COMPLEMENT LOSS THE t TAILS HAVE, ONE FUNCTION OVER
    -----------------------------------------------------------
    `x = df2/(df2 + df1 f)` hides everything the answer depends on in `1 - x =
    df1 f/(df2 + df1 f)`, exactly as `df/(df + t^2)` does — see
    `inference_t_tail_region`, whose `T_TAIL_COMPLEMENT_FLOOR` is the same threshold and
    the same argument. MEASURED here, `df1 = 4, f = 0.5`, against the elementary
    `P(chi2_4 >= 2) = 2/e = 0.735758882342677` that `df2 -> inf` converges to:

        df2 = 1e8    1 - x = 2.0e-8    f_sf = 0.7357588486   rel err 4.6e-08
        df2 = 1e11   1 - x = 2.0e-11   f_sf = 0.7357773146   rel err 2.5e-05
        df2 = 1e13   1 - x = 2.0e-13   f_sf = 0.7390434378   rel err 4.5e-03
        df2 = 1e16   1 - x = 2.0e-16   f_sf = 0.9999240030   rel err 3.6e-01
        df2 = 1e17   1 - x = 2.0e-17   f_sf = 1.0            rel err 3.6e-01

    `df1 = 1` IS FIXED, BY THE IDENTITY THIS FILE ALREADY DOCUMENTS
    --------------------------------------------------------------
    `P(F_{1,d} >= f)` and `P(|T_d| >= sqrt(f))` are the same number by the definition of
    the F distribution, and `inference_t_sf_two_sided` is already region-aware, so below
    the floor this delegates to it rather than to an `x` with no digits left. That also
    repairs an identity the suite asserts: before this, `f_sf(1.0, 1.0, 1e16)` was `1.0`
    while `t_sf_two_sided(1.0, 1e16)` was `0.31731050786291404`, so the two halves of one
    documented equality disagreed by 0.68 — the p-value collapse of
    `inference_t_tail_region`, surviving in the sibling function. `sqrt` is
    correctly rounded, so `sqrt(f)^2` is `f` to within one ulp and the delegated mass
    moves by less than its own last bit; MEASURED at `df2 = 1e16`, the two sides are
    BIT-EQUAL and not merely close at `t = 0.3, 0.7, 1.3, 2.9`, none of them a power of
    two. The delegation needs `df1` to be EXACTLY 1.0, because that is what the identity
    needs; `df1 = 1 + 1e-9` is a different distribution and takes the beta path.

    `df1 > 1` BELOW THE FLOOR IS A RECORDED GAP, NOT A FIXED REGION
    --------------------------------------------------------------
    There the limit is `P(chi2_df1 >= df1 f)`, which needs an accurate REGULARIZED UPPER
    INCOMPLETE GAMMA. This tree does not have one: frozen
    `special_functions.regularized_gamma` is a lower-tail series with no continued
    fraction for `x > a + 1`, and it divides by `gamma_function(a)`, which overflows past
    `a = 171`. Writing one is a new primitive owing its own golden vectors, so it is NOT
    done here and the table above is the honest statement of what the beta path returns.

    The gap is also NOT blanket-refused, because a refusal there would discard answers
    that are measured to be RIGHT. Below the floor with `df1 f` small the truth is pinned
    near 1 and the beta path returns it: MEASURED at `df1 = 3, df2 = 1e6` against the
    elementary `P(chi2_3 >= x) = erfc(sqrt(x/2)) + sqrt(2x/pi) e^(-x/2)`,

        f = 1e-3   1 - x = 3.0e-09   f_sf = 0.9999563373   abs err 1.4e-07
        f = 1e-4   1 - x = 3.0e-10   f_sf = 0.9999986181   abs err 7.3e-08
        f = 1e-6   1 - x = 3.0e-12   f_sf = 0.9999999986   abs err 9.6e-09

    which is the corner `assume.levene_flat` actually reaches — `MAX_ASSUME_OBS` is 4096,
    so its `df2` is at most ~4096 and `1 - x` only falls below the floor when the F
    statistic is near zero, i.e. when the truth IS ~1. The damaging corner needs `df1 f`
    of order 1 AND a `df2` above ~1e8, which no fit in this package can produce
    (`MAX_INFERENCE_OBS` is 1048576) and which therefore arrives only from a caller
    supplying `df2` directly. Both corners are pinned by literal assertions in the suite,
    the accurate one and the wrong one, so neither can move without a failure.
    """
    if not inference_finite(f) or not inference_finite(df1) or not inference_finite(df2):
        return inference_absent()
    if df1 <= 0.0 or df2 <= 0.0:
        return inference_absent()
    if f <= 0.0:
        return 1.0
    var num = df1 * f
    var denom = df2 + num
    # An overflowed `df1 * f` is an F so large the complement is 1 to every digit; the
    # incomplete beta at x = 0 is exactly 0, which is the right answer and not a loss.
    if inference_finite(num) and inference_finite(denom) and denom > 0.0:
        if df1 == 1.0 and num / denom < T_TAIL_COMPLEMENT_FLOOR:
            return inference_t_sf_two_sided(sqrt(f), df2)
    return inference_beta_inc(df2 / (df2 + df1 * f), df2 / 2.0, df1 / 2.0)


def inference_norm_sf_two_sided(z: Float64) -> Float64:
    """`P(|Z| >= |z|)` for a standard normal, from the frozen `math_ext.norm_cdf`.

    Used for every Wald p-value in this package. `math_ext.norm_cdf` is the tree's most
    accurate normal CDF (measured error 6.9e-8 at `z = 1.9599639845`) and is called
    unchanged; the only thing added is the two-sided fold and the finiteness refusal.
    """
    if not inference_finite(z):
        return inference_absent()
    from math_ext import norm_cdf

    var p = 2.0 * (1.0 - norm_cdf(fabs(z)))
    if p < 0.0:
        return 0.0
    if p > 1.0:
        return 1.0
    return p


def inference_t_quantile(p: Float64, df: Float64) -> Float64:
    """The `p`-quantile of Student's t on `df` degrees of freedom, or `inference_absent()`.

    Genuinely missing from the tree: there is no t quantile anywhere, and `power`'s t lane
    and the Wald intervals in `glm` / `robust` all need one. Bisection on
    `inference_t_cdf`, which is monotone, so the bracket is unconditional:
    `T_QUANTILE_STEPS` halvings of `[-1e4, 1e4]` reach the last representable double, and
    the step count is a WORK bound rather than an accuracy limit.

    `p` must be strictly inside `(0, 1)`: the 0 and 1 quantiles of an unbounded
    distribution are `-inf` and `+inf`, which are not answers, so they are reported absent
    rather than returned as a large finite number (`math_ext.norm_ppf` returns `+-1e300`
    there — a number where none exists). `p == 0.5` returns exactly 0.0 by symmetry.
    """
    if not inference_finite(p) or not inference_finite(df):
        return inference_absent()
    if p <= 0.0 or p >= 1.0 or df <= 0.0:
        return inference_absent()
    if p == 0.5:
        return 0.0
    var lo = -T_QUANTILE_BRACKET
    var hi = T_QUANTILE_BRACKET
    # Bisection converges to SOMETHING whether or not the root is inside the bracket. With a fixed
    # bracket and no check, a quantile beyond +/-T_QUANTILE_BRACKET came back as the bracket EDGE --
    # a finite, plausible-looking number that is not the quantile, and with no signal that it was
    # clamped. A critical value is then used as a test threshold, so the error surfaces as a wrong
    # accept/reject rather than as a wrong number.
    #
    # So the bracket is verified to actually bracket: `cdf(lo) < p < cdf(hi)`. When it does not, the
    # quantile is outside what this bracket can express and the answer is ABSENT, which this package
    # already distinguishes from zero. Widening the bracket would only move the boundary; refusing
    # names it.
    var c_lo = inference_t_cdf(lo, df)
    var c_hi = inference_t_cdf(hi, df)
    if not inference_finite(c_lo) or not inference_finite(c_hi):
        return inference_absent()
    if p <= c_lo or p >= c_hi:
        return inference_absent()
    for _ in range(T_QUANTILE_STEPS):
        var mid = 0.5 * (lo + hi)
        var c = inference_t_cdf(mid, df)
        if not inference_finite(c):
            return inference_absent()
        if c < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


@fieldwise_init
struct CdfAgreement(Copyable, Movable):
    """What the frozen t CDF and the corrected one say about the same `(t, df)`.

    Exported so any future divergence between `stat_tests._t_cdf` and `inference_t_cdf` is
    a value a caller can measure rather than a claim in a docstring — this is how the
    original `_regularized_incomplete_beta` defect (see the module docstring) was made
    auditable, and it stays wired up now that the defect is fixed, as the ongoing
    cross-check. `frozen_is_probability` is False only if the frozen kernel ever again
    returns something outside `[0, 1]`.
    """

    var status: Int
    var t: Float64
    var df: Float64
    var frozen_cdf: Float64
    var corrected_cdf: Float64
    var frozen_is_probability: Bool
    var abs_gap: Float64
    var agree: Bool


def t_cdf_agreement(t: Float64, df: Float64) -> CdfAgreement:
    """Compare `stat_tests._t_cdf` with `inference_t_cdf` at one point.

    `agree` is decided with `inference_scaled_tol(corrected, 1e-6)`: the quantity judged
    is the CDF value itself, so the relative term is sized by that value's own magnitude
    and by DBL_EPSILON, not by any aggregate and not by the caller (rule 4b). `1e-6` is not
    the old placeholder from when `stat_tests._t_cdf` was defective (see this module's
    header), and it is looser than a first sweep suggested: away from the continued
    fraction's branch-switch threshold (`x = (a+1)/(a+b+2)`), the two implementations settle
    within `5.8e-11` of each other over `df` 1 to 5000, `t` -8 to 8. BUT close to that
    threshold — where `x = df/(df+t^2)` lands almost exactly on the switch point, which
    happens at a specific `t` for every `df` — the continued fraction converges slowly by
    construction (the threshold exists to keep each evaluation on the FAST side of it), and
    a fixed 201-iteration cap means two implementations with different `fpmin`/`eps`
    constants can truncate the slow tail at slightly different points. Hunting that regime
    directly (evaluating at the exact threshold-crossing `t` for many `df`, not a uniform
    grid that would step over the narrow spike) found gaps up to `3.4e-7` at `df = 2883`,
    against otherwise-typical gaps of `1e-9` to `1e-10` at neighboring `df`. Still six orders
    of magnitude below the pre-fix `~0.058` gap, and immaterial to any real p-value decision
    (a CDF accurate to 6-7 significant figures at its rare worst point), but not at the
    `1e-9` to `1e-11` scale this pair achieves everywhere else. `1e-6` is about 3x above the
    worst spike found, not a bound proven for every `(t, df)` -- a narrower, still-narrow
    spike elsewhere is possible and would read as `agree = False`, which is the honest
    outcome for a value neither implementation resolves to full precision there.
    """
    from stat_tests import _t_cdf

    if not inference_finite(t) or not inference_finite(df) or df <= 0.0:
        return CdfAgreement(
            INF_ERR_NON_FINITE, t, df, 0.0, 0.0, False, 0.0, False
        )
    var corrected = inference_t_cdf(t, df)
    if not inference_finite(corrected):
        return CdfAgreement(
            INF_ERR_DEGENERATE, t, df, 0.0, 0.0, False, 0.0, False
        )
    var frozen = _t_cdf(t, df)
    var is_prob = inference_finite(frozen) and frozen >= 0.0 and frozen <= 1.0
    var gap = fabs(frozen - corrected) if inference_finite(frozen) else inference_absent()
    var tol = inference_scaled_tol(corrected, 1e-6)
    var agree = inference_finite(gap) and gap <= tol
    return CdfAgreement(
        INF_OK, t, df, frozen, corrected, is_prob, gap, agree
    )


# ── weighted least squares, the step every IRLS driver here takes ─────────────


@fieldwise_init
struct WlsSolution(Copyable, Movable):
    """One weighted-least-squares solve: `(X'WX) beta = X'Wz`.

    `beta` is EMPTY unless `status == INF_OK`. A rank-deficient or unverifiable system has
    no solution, and `linalg.mat_solve` returning an all-zeros vector for a singular matrix
    is precisely the frozen behaviour this exists to replace: there, "the solution is the
    zero vector" and "there is no solution" are the same return value.

    `max_row_residual` is the largest per-row violation of the normal equations at the
    returned `beta`, and `-1.0` when it was never computed (a magnitude cannot be negative,
    so the sentinel is outside the range).
    """

    var status: Int
    var beta: List[Float64]
    var positive_definite: Bool
    var max_row_residual: Float64
    var verified: Bool


def _wls_failure(code: Int) -> WlsSolution:
    return WlsSolution(code, List[Float64](), False, -1.0, False)


def wls_solve_flat(
    a: List[Float64], b: List[Float64], p: Int
) -> WlsSolution:
    """Solve the `p x p` symmetric positive-definite system `a beta = b`, or refuse.

    `a` is flat row-major. Every frozen solve in the tree reports failure as a value a
    caller cannot distinguish from an answer — `linalg.mat_solve` returns zeros for a
    singular matrix, `linear_models._solve_linear_system` silently SKIPS a near-zero pivot
    and leaves that component at 0.0, `regression._solve_normal_equations` does the same —
    so this wrapper decides admissibility BEFORE solving and verifies afterwards:

    1. Shape, ceiling and finiteness, or a status.
    2. Exact-enough symmetry, per ENTRY PAIR: `|a_ij - a_ji|` judged against the magnitude
       of those two entries alone (rule 4b — a norm over the whole matrix would let one
       large entry excuse another entry's asymmetry).
    3. Positive definiteness via the frozen `linalg_ext.mat_is_positive_definite`, which
       attempts a Cholesky and is therefore an exact test rather than a thresholded one.
       For `X'WX` with strictly positive weights this is precisely "X has full column
       rank", which is the condition an IRLS step needs. Not PD is
       `INF_ERR_RANK_DEFICIENT` with NO beta.
    4. The solve itself is the frozen `linear_models._solve_linear_system`, unchanged.
    5. Verification: every row's residual `|(a beta)_i - b_i|` against a tolerance built
       from THAT ROW's own magnitude — `sum_j |a_ij beta_j| + |b_i|` — never from a norm
       over other rows. An unverified solve is `INF_ERR_RANK_DEFICIENT` with no beta,
       because an ill-conditioned system that Cholesky accepted has still not been solved.

    @capability wls_solve_flat
    complexity: O(p^3)
    counts:
    - p * p == len(a) [kernel_validated]
    - p == len(b) [kernel_validated]
    @endcapability
    """
    if p < 1:
        return _wls_failure(INF_ERR_TOO_FEW)
    if p > MAX_INFERENCE_PARAMS:
        return _wls_failure(INF_ERR_DIMENSION_TOO_LARGE)
    if not dims_fit(p, p, len(a)) or len(b) != p:
        return _wls_failure(INF_ERR_SHAPE)
    for i in range(len(a)):
        if not inference_finite(a[i]):
            return _wls_failure(INF_ERR_NON_FINITE)
    for i in range(p):
        if not inference_finite(b[i]):
            return _wls_failure(INF_ERR_NON_FINITE)

    for i in range(p):
        for j in range(i + 1, p):
            var upper = a[i * p + j]
            var lower = a[j * p + i]
            var scale = fabs(upper) if fabs(upper) > fabs(lower) else fabs(lower)
            # Judged quantity: the difference of these two entries. Scale: their own.
            if fabs(upper - lower) > inference_scaled_tol(scale, 0.0):
                return _wls_failure(INF_ERR_NOT_SYMMETRIC)

    if not mat_is_positive_definite(mat_from_list(a, p, p)):
        return _wls_failure(INF_ERR_RANK_DEFICIENT)

    var rows = List[List[Float64]]()
    for i in range(p):
        var row = List[Float64](capacity=p)
        for j in range(p):
            row.append(a[i * p + j])
        rows.append(row^)
    var beta = _solve_linear_system(rows, b)
    if len(beta) != p:
        return _wls_failure(INF_ERR_RANK_DEFICIENT)
    for j in range(p):
        if not inference_finite(beta[j]):
            return _wls_failure(INF_ERR_DIVERGED)

    var worst: Float64 = 0.0
    var verified = True
    for i in range(p):
        var activity: Float64 = 0.0
        var magnitude = fabs(b[i])
        for j in range(p):
            var term = a[i * p + j] * beta[j]
            activity += term
            magnitude += fabs(term)
        var residual = fabs(activity - b[i])
        if residual > worst:
            worst = residual
        # Judged quantity: this row's residual. Scale: this row's own magnitude. The extra
        # ulps are the p elimination steps that produced this row's coefficient, which is
        # the standard backward-error criterion for Gaussian elimination and not slack.
        if residual > inference_scaled_tol_ulps(magnitude, 0.0, Float64(p)):
            verified = False
    if not verified:
        return WlsSolution(
            INF_ERR_RANK_DEFICIENT, List[Float64](), True, worst, False
        )
    return WlsSolution(INF_OK, beta^, True, worst, True)
