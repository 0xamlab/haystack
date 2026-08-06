"""
causal_inference.sensitivity — how strong an unmeasured confounder would have to be.
Zero Python imports.

Why this file exists
--------------------
Every estimator in this package, and every estimator in `causal.mojo`, is conditional on the
assumption that the measured covariates capture the confounding. Nothing in the tree quantifies
what happens if they do not. That is the gap this file fills, and the important word is
QUANTIFIES: a sensitivity analysis exists to report a NUMBER — the strength an unmeasured
confounder would need in order to overturn the conclusion — and not to reassure. There is no
`is_robust` flag anywhere in this module, because "robust" is a judgement against a standard the
caller owns.

Three independent families, each hand-checkable:

  1. *E-value* (VanderWeele & Ding). For a risk ratio, the minimum strength of association — with
     both the treatment and the outcome — that an unmeasured confounder would need to explain the
     observed ratio away entirely. `E = RR + sqrt(RR (RR - 1))` for `RR > 1`, and the reciprocal
     orientation below 1. `RR = 2` gives `2 + sqrt(2) = 3.41421356...`; `RR = 0.5` gives the same
     number, because a protective effect of the same size takes the same confounding to erase.
     `RR = 1` gives exactly 1: no confounding at all is needed to explain nothing.
  2. *Robustness value and omitted-variable bias* (Cinelli & Hazlett). For a regression
     coefficient with a t-statistic, `RV_q` is the share of residual variance in BOTH the
     treatment and the outcome that a confounder would need to explain in order to reduce the
     estimate by `100q%`. `RV_q = (sqrt(f^4 + 4 f^2) - f^2) / 2` with `f = q |t| / sqrt(dof)`.
     At `f = 1` that is `(sqrt(5) - 1) / 2 = 0.6180339887...`, the reciprocal golden ratio, which
     is the value the suite pins.
  3. *Rosenbaum bounds*. For a matched-pairs design, the worst-case one-sided p-value when the
     odds of treatment within a pair may differ by a factor of `gamma`. Computed as an EXACT
     binomial upper tail over the frozen `probability.binomial_pmf`, so a small case can be
     checked by hand: `n = 4`, `k = 4`, `gamma = 1` is `0.5^4 = 0.0625`.

THE TWO FAMILIES CROSS-CHECK EACH OTHER, EXACTLY
------------------------------------------------
`robustness_value` and `omitted_variable_bias` are derived from different starting points — one
solves a quadratic for a partial R^2, the other propagates a bias formula — so their agreement is
evidence rather than restatement. Setting a confounder's strength to exactly `RV_q` in BOTH
directions must reduce the estimate to exactly `(1 - q)` times its original size:

    bias = se sqrt(dof) R^2 / sqrt(1 - R^2)        (the bias formula, at r2_dz = r2_yz = R^2)
    q |estimate| = q |t| se                        (the definition of RV_q)
    =>  R^2 / sqrt(1 - R^2) = q |t| / sqrt(dof) = f
    =>  R^2 + f^2 R^2 - f^2 = 0  =>  R^2 = (sqrt(f^4 + 4 f^2) - f^2) / 2

which is `RV_q`. The suite asserts the round trip on several `(t, dof, q)` triples to a tolerance
built from the estimate's OWN magnitude. Agreement between two independent computations is
evidence; a single plausible number is not.

What is REUSED, unchanged
-------------------------
* `probability.binomial_pmf(k, n, p)` — the Rosenbaum tail, summed term by term. Its factors are
  `C(n, k)`, `p^k` and `(1-p)^(n-k)`, each of which stays representable up to about a thousand
  pairs and none of which is re-derived here; past that the coefficient overflows to `inf` and the
  product becomes `nan`, so `MAX_SIGN_PAIRS` refuses rather than returning one (a non-finite
  Float64 on the result path ends the worker process).

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
golden_vectors: mojo/tests/libs/test_causal_inference_sensitivity.mojo
benchmark: benchmarks/mojo_benchmarks/bench_causal_inference_report.mojo
docs: none
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs, sqrt

from probability import binomial_pmf

from causal_inference.base import (
    CI_ABSENT,
    CI_ERR_INSUFFICIENT_DATA,
    CI_ERR_INVALID_PARAMETER,
    CI_ERR_NON_FINITE,
    CI_ERR_SHAPE,
    CI_ERR_WORK_BUDGET,
    CI_OK,
    ci_all_finite,
    ci_finite,
    ci_tolerance,
)

# `probability.binomial_pmf` multiplies `C(n, k)` by `p^k` and `(1-p)^(n-k)` as three separate
# Float64 factors. `C(1000, 500)` is about 2.7e299 — the largest central coefficient that is
# still representable — and `C(1500, 750)` overflows to `inf`, at which point the product with an
# underflowed power is `nan`. So the pair count is refused past 1000 rather than answered with a
# non-finite number. Measured against the formula, not assumed: the tail is also range-checked
# after summation.
comptime MAX_SIGN_PAIRS: Int = 1000

# Bisection over `gamma` is monotone, so 200 halvings resolve any bracket to well past Float64
# precision. A cap exists at all only so a pathological tolerance cannot loop forever.
comptime MAX_GAMMA_ITER: Int = 200


# ── result structs (declared HERE; rule 2) ───────────────────────────────────


struct EValue(Copyable, Movable):
    """The minimum confounder-association strength that could explain a risk ratio away.

    `rr_oriented` is the ratio in its `>= 1` orientation and `inverted` says whether that
    required taking a reciprocal, so a caller can see which direction the E-value refers to. A
    risk ratio must be strictly positive; zero or negative is a refusal, not an infinite E-value.

    `evalue_ci_limit` is populated only by `e_value_bound`. It is the E-value for the confidence
    limit CLOSEST TO THE NULL, and it is exactly 1.0 when that limit crosses the null — the
    honest answer there being "no confounding is needed, the interval already includes no effect".
    """

    var status: Int
    var has_value: Bool
    var evalue: Float64
    var rr_oriented: Float64
    var inverted: Bool
    var has_ci_limit: Bool
    var evalue_ci_limit: Float64
    var ci_limit_crosses_null: Bool

    def __init__(out self, status: Int):
        self.status = status
        self.has_value = False
        self.evalue = CI_ABSENT
        self.rr_oriented = CI_ABSENT
        self.inverted = False
        self.has_ci_limit = False
        self.evalue_ci_limit = CI_ABSENT
        self.ci_limit_crosses_null = False


struct RobustnessValue(Copyable, Movable):
    """`RV_q`: the residual variance share a confounder needs to shrink an estimate by `100q%`.

    `partial_r2` is `t^2 / (t^2 + dof)`, the partial R^2 of the treatment with the outcome — the
    observed association, for comparison against `rv`. `f_q` is the intermediate
    `q |t| / sqrt(dof)` and is returned because it is the quantity the closed form is built from,
    so a caller can reproduce the algebra rather than trust it.

    `rv` is 0.0 when `t == 0`, and that is a real answer: an estimate that is already zero needs
    no confounding to explain away.
    """

    var status: Int
    var has_value: Bool
    var rv: Float64
    var f_q: Float64
    var partial_r2: Float64
    var has_partial_r2: Bool
    var t_abs: Float64
    var q: Float64

    def __init__(out self, status: Int):
        self.status = status
        self.has_value = False
        self.rv = CI_ABSENT
        self.f_q = CI_ABSENT
        self.partial_r2 = CI_ABSENT
        self.has_partial_r2 = False
        self.t_abs = 0.0
        self.q = 0.0


struct OvbResult(Copyable, Movable):
    """A bias-adjusted estimate under a confounder of stated strength in both directions.

    `bias` is `se sqrt(dof) sqrt(r2_yz r2_dz / (1 - r2_dz))` — the Cinelli-Hazlett bound on how
    much a confounder explaining `r2_dz` of the treatment's residual variance and `r2_yz` of the
    outcome's could move the estimate. `adjusted_estimate` moves the estimate TOWARD ZERO by that
    amount (the worst case for a caller arguing an effect exists), and `flips_sign` is True when
    the bias exceeds the estimate, which is the finding that matters.

    `adjusted_se` follows the same source: `se sqrt(dof / (dof - 1)) sqrt((1 - r2_yz) /
    (1 - r2_dz))`. `r2_dz = 1` is refused rather than returned as an infinite bias: a confounder
    that explains ALL of the treatment's residual variance leaves no variation to estimate from,
    so the quantity does not exist.
    """

    var status: Int
    var has_result: Bool
    var bias: Float64
    var adjusted_estimate: Float64
    var adjusted_se: Float64
    var adjusted_t: Float64
    var has_adjusted_t: Bool
    var flips_sign: Bool
    var original_estimate: Float64

    def __init__(out self, status: Int):
        self.status = status
        self.has_result = False
        self.bias = CI_ABSENT
        self.adjusted_estimate = 0.0
        self.adjusted_se = CI_ABSENT
        self.adjusted_t = 0.0
        self.has_adjusted_t = False
        self.flips_sign = False
        self.original_estimate = 0.0


struct SensitivityCurve(Copyable, Movable):
    """Bias-adjusted estimates across a grid of confounder strengths.

    `r2_used[k]` is the grid point and `adjusted[k]` the estimate under a confounder of that
    strength in BOTH directions (`r2_dz = r2_yz = r2_used[k]`), which is the diagonal of the
    Cinelli-Hazlett contour plot. `has_point[k]` is False for a grid point at or above 1.0, where
    the quantity does not exist — absent per point, not clamped to the nearest value that does.

    `first_sign_flip_r2` is the smallest grid point at which the adjusted estimate changes sign,
    and `has_sign_flip` is False when no grid point does. That is the one number a caller usually
    wants, reported alongside the curve rather than instead of it.
    """

    var status: Int
    var has_curve: Bool
    var r2_used: List[Float64]
    var adjusted: List[Float64]
    var bias: List[Float64]
    var has_point: List[Bool]
    var n_points: Int
    var n_absent: Int
    var has_sign_flip: Bool
    var first_sign_flip_r2: Float64

    def __init__(out self, status: Int):
        self.status = status
        self.has_curve = False
        self.r2_used = List[Float64]()
        self.adjusted = List[Float64]()
        self.bias = List[Float64]()
        self.has_point = List[Bool]()
        self.n_points = 0
        self.n_absent = 0
        self.has_sign_flip = False
        self.first_sign_flip_r2 = CI_ABSENT


struct RosenbaumBound(Copyable, Movable):
    """The worst-case one-sided p-value for a matched-pairs design under bias factor `gamma`.

    `p_plus` is `gamma / (1 + gamma)`, the largest within-pair probability that the treated unit
    is the one with the higher outcome once the odds of treatment may differ by `gamma`.
    `p_upper_bound` is `P(Bin(n_pairs, p_plus) >= n_positive)`, computed as an exact sum of frozen
    binomial PMF terms.

    `gamma_critical` is populated only by `rosenbaum_gamma_needed`: the smallest `gamma` at which
    the bound reaches the caller's threshold — i.e. the answer to "how much unmeasured bias would
    it take to make this result non-significant". `has_gamma` is False when no `gamma` inside the
    search ceiling does it, which is a real and useful answer and is NOT reported as the ceiling.
    """

    var status: Int
    var has_bound: Bool
    var p_upper_bound: Float64
    var p_plus: Float64
    var gamma: Float64
    var n_pairs: Int
    var n_positive: Int
    var has_gamma: Bool
    var gamma_critical: Float64
    var n_iter: Int

    def __init__(out self, status: Int):
        self.status = status
        self.has_bound = False
        self.p_upper_bound = CI_ABSENT
        self.p_plus = CI_ABSENT
        self.gamma = CI_ABSENT
        self.n_pairs = 0
        self.n_positive = 0
        self.has_gamma = False
        self.gamma_critical = CI_ABSENT
        self.n_iter = 0


# ── E-value ──────────────────────────────────────────────────────────────────


def _evalue_of(rr_ge_one: Float64) -> Float64:
    """`RR + sqrt(RR (RR - 1))` for `RR >= 1`. THE package's one E-value formula."""
    if rr_ge_one <= 1.0:
        return 1.0
    return rr_ge_one + sqrt(rr_ge_one * (rr_ge_one - 1.0))


def e_value_ratio(risk_ratio: Float64) -> EValue:
    """VanderWeele-Ding E-value for a point estimate expressed as a risk ratio.

    The minimum strength of association, on the risk-ratio scale, that an unmeasured confounder
    would need to have with BOTH the treatment and the outcome — above and beyond the measured
    covariates — to fully explain away an observed ratio of `risk_ratio`.

    A ratio below 1 is inverted first, so `0.5` and `2.0` give the same E-value: erasing a
    halving takes exactly as much confounding as erasing a doubling. `risk_ratio == 1` gives
    exactly 1.0.

    A risk ratio must be strictly positive. Zero, negative and non-finite inputs are refused;
    `risk_ratio = 0` in particular is NOT an infinite E-value, because an infinity on the result
    path is not returnable and "infinitely strong confounding" is not a quantity a caller can
    compare against anything.

    @capability e_value_ratio
    complexity: O(1)
    counts: none
    @endcapability
    """
    if not ci_finite(risk_ratio) or risk_ratio <= 0.0:
        return EValue(CI_ERR_INVALID_PARAMETER)
    var out = EValue(CI_OK)
    var oriented = risk_ratio
    if risk_ratio < 1.0:
        oriented = 1.0 / risk_ratio
        out.inverted = True
    if not ci_finite(oriented):
        return EValue(CI_ERR_NON_FINITE)
    var e = _evalue_of(oriented)
    if not ci_finite(e):
        return EValue(CI_ERR_NON_FINITE)
    out.rr_oriented = oriented
    out.evalue = e
    out.has_value = True
    return out^


def e_value_bound(risk_ratio: Float64, ci_limit: Float64) -> EValue:
    """`e_value_ratio` plus the E-value for the confidence limit nearer the null.

    The limit is oriented the same way as the point estimate. For `risk_ratio > 1` the relevant
    limit is the LOWER one; for `risk_ratio < 1` it is the UPPER one, inverted. A limit that
    crosses the null gives an E-value of exactly 1.0 with `ci_limit_crosses_null = True`: the
    interval already contains "no effect", so no confounding is required to reach it.

    Both limits must be positive and finite, and the limit must lie on the null side of the point
    estimate — a "lower limit" above the point estimate is not a confidence limit, and accepting
    it would produce a number with no interpretation.

    @capability e_value_bound
    complexity: O(1)
    counts: none
    @endcapability
    """
    var point = e_value_ratio(risk_ratio)
    if point.status != CI_OK:
        return point^
    if not ci_finite(ci_limit) or ci_limit <= 0.0:
        return EValue(CI_ERR_INVALID_PARAMETER)
    var out = point^
    if risk_ratio >= 1.0:
        if ci_limit > risk_ratio:
            return EValue(CI_ERR_INVALID_PARAMETER)
        if ci_limit <= 1.0:
            out.ci_limit_crosses_null = True
            out.evalue_ci_limit = 1.0
        else:
            out.evalue_ci_limit = _evalue_of(ci_limit)
    else:
        if ci_limit < risk_ratio:
            return EValue(CI_ERR_INVALID_PARAMETER)
        if ci_limit >= 1.0:
            out.ci_limit_crosses_null = True
            out.evalue_ci_limit = 1.0
        else:
            var inv = 1.0 / ci_limit
            if not ci_finite(inv):
                return EValue(CI_ERR_NON_FINITE)
            out.evalue_ci_limit = _evalue_of(inv)
    if not ci_finite(out.evalue_ci_limit):
        return EValue(CI_ERR_NON_FINITE)
    out.has_ci_limit = True
    return out^


# ── robustness value ─────────────────────────────────────────────────────────


def robustness_value(t_stat: Float64, dof: Int, q: Float64) -> RobustnessValue:
    """Cinelli-Hazlett `RV_q`: the confounder strength needed to reduce an estimate by `100q%`.

    `RV_q = (sqrt(f^4 + 4 f^2) - f^2) / 2` with `f = q |t| / sqrt(dof)`. It is the value `R^2`
    such that a confounder explaining `R^2` of the residual variance of the treatment AND `R^2`
    of the residual variance of the outcome would shrink the point estimate by a factor `q`. The
    quadratic it solves is derived in this module's docstring, and `omitted_variable_bias` is the
    independent route to the same statement — the suite asserts the round trip.

    `q` in (0, 1]: `q = 1` asks what it takes to reach zero, `q = 0.5` to halve. `dof >= 1`. A
    zero t-statistic gives `RV = 0`, a real answer.

    @capability robustness_value
    complexity: O(1)
    counts: none
    @endcapability
    """
    if not ci_finite(t_stat):
        return RobustnessValue(CI_ERR_INVALID_PARAMETER)
    if dof < 1:
        return RobustnessValue(CI_ERR_INSUFFICIENT_DATA)
    if not ci_finite(q) or q <= 0.0 or q > 1.0:
        return RobustnessValue(CI_ERR_INVALID_PARAMETER)

    var out = RobustnessValue(CI_OK)
    var ta = fabs(t_stat)
    out.t_abs = ta
    out.q = q
    var f = q * ta / sqrt(Float64(dof))
    if not ci_finite(f):
        return RobustnessValue(CI_ERR_NON_FINITE)
    var f2 = f * f
    var rv = 0.5 * (sqrt(f2 * f2 + 4.0 * f2) - f2)
    if not ci_finite(rv):
        return RobustnessValue(CI_ERR_NON_FINITE)
    if rv < 0.0:
        rv = 0.0
    out.f_q = f
    out.rv = rv
    out.has_value = True
    var denom = ta * ta + Float64(dof)
    if denom > 0.0 and ci_finite(denom):
        var pr2 = ta * ta / denom
        if ci_finite(pr2):
            out.partial_r2 = pr2
            out.has_partial_r2 = True
    return out^


# ── omitted-variable bias ────────────────────────────────────────────────────


def _ovb_bias(se: Float64, dof: Int, r2_dz: Float64, r2_yz: Float64) -> Float64:
    """`se sqrt(dof) sqrt(r2_yz r2_dz / (1 - r2_dz))`. THE package's one bias formula.

    Callers must have checked `0 <= r2_dz < 1`, `0 <= r2_yz <= 1`, `dof >= 2`, `se >= 0` and
    finiteness. Returning a sentinel here instead would give this module two definitions of a
    valid input, which is the duplicated-guard failure rule 3 describes.
    """
    return se * sqrt(Float64(dof)) * sqrt(r2_yz * r2_dz / (1.0 - r2_dz))


def omitted_variable_bias(
    estimate: Float64, se: Float64, dof: Int, r2_dz: Float64, r2_yz: Float64
) -> OvbResult:
    """The bias-adjusted estimate under an unmeasured confounder of stated strength.

    `r2_dz` is the share of the TREATMENT's residual variance the confounder would explain and
    `r2_yz` the share of the OUTCOME's. The adjustment moves the estimate toward zero by the
    Cinelli-Hazlett bound, which is the worst case for anyone arguing the effect is real, and
    `flips_sign` reports when the bias exceeds the estimate outright.

    `r2_dz` must be strictly below 1: a confounder explaining every last part of the treatment's
    residual variance leaves nothing to identify the effect from, so the adjusted estimate does
    not exist and `CI_ERR_INVALID_PARAMETER` is the answer rather than an infinity. `dof >= 2`,
    because the adjusted standard error carries a `dof / (dof - 1)` factor.

    @capability omitted_variable_bias
    complexity: O(1)
    counts: none
    @endcapability
    """
    if not ci_finite(estimate) or not ci_finite(se) or se < 0.0:
        return OvbResult(CI_ERR_INVALID_PARAMETER)
    if dof < 2:
        return OvbResult(CI_ERR_INSUFFICIENT_DATA)
    if not ci_finite(r2_dz) or r2_dz < 0.0 or r2_dz >= 1.0:
        return OvbResult(CI_ERR_INVALID_PARAMETER)
    if not ci_finite(r2_yz) or r2_yz < 0.0 or r2_yz > 1.0:
        return OvbResult(CI_ERR_INVALID_PARAMETER)

    var bias = _ovb_bias(se, dof, r2_dz, r2_yz)
    if not ci_finite(bias) or bias < 0.0:
        return OvbResult(CI_ERR_NON_FINITE)
    var out = OvbResult(CI_OK)
    out.original_estimate = estimate
    out.bias = bias

    var magnitude = fabs(estimate) - bias
    var adjusted: Float64
    if estimate >= 0.0:
        adjusted = magnitude
    else:
        adjusted = -magnitude
    if not ci_finite(adjusted):
        return OvbResult(CI_ERR_NON_FINITE)
    out.adjusted_estimate = adjusted
    out.flips_sign = magnitude < 0.0

    var adj_se = (
        se
        * sqrt(Float64(dof) / Float64(dof - 1))
        * sqrt((1.0 - r2_yz) / (1.0 - r2_dz))
    )
    if ci_finite(adj_se) and adj_se >= 0.0:
        out.adjusted_se = adj_se
        if adj_se > 0.0:
            var t = adjusted / adj_se
            if ci_finite(t):
                out.adjusted_t = t
                out.has_adjusted_t = True
    out.has_result = True
    return out^


def sensitivity_curve(
    estimate: Float64, se: Float64, dof: Int, r2_grid: List[Float64]
) -> SensitivityCurve:
    """`omitted_variable_bias` along the diagonal `r2_dz = r2_yz`, over a caller-supplied grid.

    The diagonal is the usual one-dimensional summary of the Cinelli-Hazlett contour plot: it
    answers "how strong, in both directions equally, before the conclusion changes". Each point
    goes through the SAME `_ovb_bias` the scalar entry point uses, so the curve and the point
    estimate cannot disagree.

    A grid value at or above 1.0 has no adjusted estimate and is marked absent in `has_point`
    rather than clamped to 0.999 — a clamped point would appear on the curve as a finite bias
    that the model does not imply. `first_sign_flip_r2` is the smallest grid value where the sign
    changes, absent when none does.

    The grid is taken in the order given and is not sorted, because the caller's ordering is
    information (a refinement near a suspected threshold) and re-sorting would silently discard
    it. `first_sign_flip_r2` is therefore the smallest FLIPPING value found anywhere in the grid,
    which is well defined regardless of order.

    @capability sensitivity_curve
    complexity: O(len(r2_grid))
    counts: none
    @endcapability
    """
    if not ci_finite(estimate) or not ci_finite(se) or se < 0.0:
        return SensitivityCurve(CI_ERR_INVALID_PARAMETER)
    if dof < 2:
        return SensitivityCurve(CI_ERR_INSUFFICIENT_DATA)
    if len(r2_grid) == 0:
        return SensitivityCurve(CI_ERR_INSUFFICIENT_DATA)
    if not ci_all_finite(r2_grid):
        return SensitivityCurve(CI_ERR_NON_FINITE)

    var out = SensitivityCurve(CI_OK)
    out.n_points = len(r2_grid)
    var flip_seen = False
    var flip_at = 0.0
    for k in range(len(r2_grid)):
        var r2 = r2_grid[k]
        out.r2_used.append(r2)
        if r2 < 0.0 or r2 >= 1.0:
            out.bias.append(0.0)
            out.adjusted.append(0.0)
            out.has_point.append(False)
            out.n_absent += 1
            continue
        var bias = _ovb_bias(se, dof, r2, r2)
        var magnitude = fabs(estimate) - bias
        var adjusted = magnitude if estimate >= 0.0 else -magnitude
        if not ci_finite(bias) or not ci_finite(adjusted):
            out.bias.append(0.0)
            out.adjusted.append(0.0)
            out.has_point.append(False)
            out.n_absent += 1
            continue
        out.bias.append(bias)
        out.adjusted.append(adjusted)
        out.has_point.append(True)
        if magnitude < 0.0:
            if not flip_seen or r2 < flip_at:
                flip_at = r2
                flip_seen = True
    if flip_seen:
        out.has_sign_flip = True
        out.first_sign_flip_r2 = flip_at
    out.has_curve = out.n_absent < out.n_points
    if not out.has_curve:
        out.status = CI_ERR_INVALID_PARAMETER
    return out^


# ── Rosenbaum bounds ─────────────────────────────────────────────────────────


def _binomial_upper_tail(n: Int, k: Int, p: Float64) -> Float64:
    """`P(Bin(n, p) >= k)` as an exact sum of frozen `probability.binomial_pmf` terms.

    Summed from `k` upward rather than as `1 - lower tail`, because the upper tail is the small
    quantity here and subtracting two nearly equal numbers would lose exactly the precision the
    answer consists of. Callers bound `n` by `MAX_SIGN_PAIRS` first.
    """
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    var total = 0.0
    for j in range(k, n + 1):
        total += binomial_pmf(j, n, p)
    return total


def rosenbaum_sign_bound(
    n_pairs: Int, n_positive: Int, gamma: Float64
) -> RosenbaumBound:
    """Worst-case one-sided p-value for a matched-pairs sign test under bias factor `gamma`.

    `gamma` is the largest factor by which two matched units' odds of treatment may differ
    because of an unmeasured confounder. `gamma = 1` is the randomised case. Under `gamma`, the
    within-pair probability that the treated unit has the higher outcome is at most
    `p+ = gamma / (1 + gamma)`, so the worst-case p-value is
    `P(Bin(n_pairs, p+) >= n_positive)` — computed exactly, term by term, over the frozen
    binomial PMF.

    `n_pairs` must be at least 1 and at most `MAX_SIGN_PAIRS` (1000): past that the central
    binomial coefficient overflows and the tail becomes `nan`, which is refused rather than
    returned. `n_positive` in `[0, n_pairs]`. TIED PAIRS must be excluded by the caller before
    calling — the sign test has no place to put them, and silently counting a tie as a negative
    would make the bound anti-conservative in the one direction that matters.

    @capability rosenbaum_sign_bound
    complexity: O(n_pairs)
    counts:
    - dim n_pairs <= MAX_SIGN_PAIRS [kernel_validated]
    @endcapability
    """
    if n_pairs < 1:
        return RosenbaumBound(CI_ERR_INSUFFICIENT_DATA)
    if n_pairs > MAX_SIGN_PAIRS:
        return RosenbaumBound(CI_ERR_WORK_BUDGET)
    if n_positive < 0 or n_positive > n_pairs:
        return RosenbaumBound(CI_ERR_SHAPE)
    if not ci_finite(gamma) or gamma < 1.0:
        return RosenbaumBound(CI_ERR_INVALID_PARAMETER)

    var p_plus = gamma / (1.0 + gamma)
    if not ci_finite(p_plus) or p_plus <= 0.0 or p_plus >= 1.0:
        return RosenbaumBound(CI_ERR_INVALID_PARAMETER)
    var tail = _binomial_upper_tail(n_pairs, n_positive, p_plus)
    if not ci_finite(tail) or tail < 0.0 or tail > 1.0000000001:
        return RosenbaumBound(CI_ERR_NON_FINITE)
    if tail > 1.0:
        tail = 1.0

    var out = RosenbaumBound(CI_OK)
    out.n_pairs = n_pairs
    out.n_positive = n_positive
    out.gamma = gamma
    out.p_plus = p_plus
    out.p_upper_bound = tail
    out.has_bound = True
    return out^


def rosenbaum_gamma_needed(
    n_pairs: Int, n_positive: Int, target_p: Float64,
    gamma_max: Float64, tol: Float64,
) -> RosenbaumBound:
    """The smallest bias factor `gamma` at which the sign-test bound reaches `target_p`.

    THIS is the quantity a sensitivity analysis exists to report: not "the result is robust" but
    "it would take a confounder that shifts the within-pair odds of treatment by a factor of
    `gamma_critical` to make this result non-significant at `target_p`".

    The bound is monotone increasing in `gamma`, so the search is a bisection — deterministic, no
    RNG, and its bracket is checked at both ends before it starts:

      * if the bound at `gamma = 1` already reaches `target_p`, the answer is exactly 1.0: the
        result is not significant even under perfect randomisation, and no unmeasured confounding
        is needed;
      * if the bound at `gamma_max` still has not reached `target_p`, there is NO answer inside
        the search range. `has_gamma` is False and `gamma_critical` is absent. Returning
        `gamma_max` would be a number that means "at least this", reported in a field that means
        "exactly this".

    The bracket width is judged against `tol` plus a rounding allowance built from THE BRACKET'S
    OWN endpoints, which is the only magnitude involved in that comparison.

    @capability rosenbaum_gamma_needed
    complexity: O(n_pairs * log(gamma_max))
    counts:
    - dim n_pairs <= MAX_SIGN_PAIRS [kernel_validated]
    @endcapability
    """
    if not ci_finite(target_p) or target_p <= 0.0 or target_p >= 1.0:
        return RosenbaumBound(CI_ERR_INVALID_PARAMETER)
    if not ci_finite(gamma_max) or gamma_max <= 1.0:
        return RosenbaumBound(CI_ERR_INVALID_PARAMETER)
    if not ci_finite(tol) or tol <= 0.0:
        return RosenbaumBound(CI_ERR_INVALID_PARAMETER)

    var at_one = rosenbaum_sign_bound(n_pairs, n_positive, 1.0)
    if at_one.status != CI_OK:
        return at_one^
    var out = at_one^
    if out.p_upper_bound >= target_p:
        out.has_gamma = True
        out.gamma_critical = 1.0
        return out^
    var at_max = rosenbaum_sign_bound(n_pairs, n_positive, gamma_max)
    if at_max.status != CI_OK:
        return at_max^
    if at_max.p_upper_bound < target_p:
        # No gamma inside the range does it. Absent, not `gamma_max`.
        return out^

    var lo = 1.0
    var hi = gamma_max
    var iters = 0
    for _ in range(MAX_GAMMA_ITER):
        iters += 1
        if hi - lo <= ci_tolerance(fabs(lo) + fabs(hi), tol):
            break
        var mid = 0.5 * (lo + hi)
        if mid <= lo or mid >= hi:
            break
        var probe = rosenbaum_sign_bound(n_pairs, n_positive, mid)
        if probe.status != CI_OK:
            return probe^
        if probe.p_upper_bound >= target_p:
            hi = mid
        else:
            lo = mid
    out.n_iter = iters
    out.has_gamma = True
    out.gamma_critical = hi
    return out^
