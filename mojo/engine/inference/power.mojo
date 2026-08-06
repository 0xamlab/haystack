"""
inference.power — power and sample size for a two-sample mean comparison. Zero Python.

Why this module exists
----------------------
`ab_testing` covers PROPORTIONS: `sample_size_proportion`, `power_analysis`, `mde`,
`z_test_proportions`. Nothing anywhere covers a mean comparison, which is the design question
a caller with continuous measurements actually has, and there is no sample-size INVERSION for
a standardized effect at all.

Three frozen behaviours this module exists to replace with statuses:

* `ab_testing.sample_size_proportion` returns the literal `1000000` when the two proportions
  are equal, with the comment "Infinite sample needed for zero effect". A million is not a
  sample size for an undetectable effect; it is a number a caller will budget against.
  `INF_ERR_EFFECT_ZERO` is the answer.
* `ab_testing.power_analysis`, `mde` and `sample_size_proportion` validate nothing. `alpha`
  outside `(0, 1)` reaches `_norm_ppf`, which CLAMPS `p` into `[1e-10, 1-1e-10]` and returns a
  number, so `power_analysis(0.5, 100, 3.0)` answers rather than refusing.
* `math_ext.norm_ppf` returns `+-1e300` for `p` at or past the ends. `1e300` is finite, so a
  finiteness guard does not catch it, and it then multiplies into a sample size of `1e600`
  which becomes `inf`. Every quantile used here is range-checked against
  `POWER_MAX_ABS_Z` (40 standard deviations) instead.

What is reused rather than rebuilt
----------------------------------
* `ab_testing.power_analysis` — the two-sided normal-approximation power, called unchanged.
  It is exactly `Phi(nc - z) + Phi(-nc - z)` with `nc = d sqrt(n/2)`, which is the two-sample
  standardized-effect formula, so the two-sided normal lane here IS that frozen kernel plus
  validation. The one-sided lane cannot use it — the frozen function has no directional form —
  and composes `math_ext.norm_cdf` and `norm_ppf` instead. The two lanes therefore differ in
  their probit: `ab_testing._norm_ppf` is the Abramowitz-Stegun rational form (~4.5e-4) while
  `math_ext.norm_ppf` is Acklam (~1.15e-9), so a two-sided power from this module and twice a
  one-sided power at half alpha agree to about 1e-4 and not to 1e-9. That is stated here, and
  the suite asserts it at 1e-3 rather than pretending to more.
* `math_ext.norm_cdf` / `norm_ppf` — the normal tail and quantile.
* `inference.core.inference_t_cdf` / `inference_t_quantile` — the t lane. The t quantile does
  not exist anywhere else in the tree, and `inference.core`'s own t CDF adds region-switching
  the frozen `stat_tests._t_cdf` still lacks even after its incomplete-beta defect was fixed
  (see that module's docstring for the history and the two implementations' measured
  agreement).
* `optimization.model._ceil_f` — the sample-size rounding, per rule 4c: never
  `Float64(Int(v))`, whose out-of-range `fptosi` is poison rather than truncation.

Rule 4 in this module: a returned sample size is VERIFIED, not asserted
----------------------------------------------------------------------
The closed form `n = 2 ((z_alpha + z_beta) / d)^2` inverts the normal approximation, and a
closed form that is merely printed is a claim. So every sample size returned here is checked
by re-evaluating power through the SAME power function the caller would use:

    achieved_power        power at the returned n            must be >= target_power
    power_at_n_minus_1    power at n - 1                     must be <  target_power

and `minimal` is True only when both hold. That makes minimality a MEASURED property of the
returned number rather than a property of the algebra, and it is the self-consistency
assertion rule 4b asks for: a package's own reports must agree with each other, and this one
tests the inversion against the forward evaluation instead of against a second copy of the
same algebra. When the closed form and the verification disagree — which happens at the
boundary, because the two lanes' probits differ in the 4th decimal — a bounded search of at
most `POWER_SEARCH_STEPS` integers moves `n` to the smallest value that verifies, and
`search_steps` reports how far it had to go. If nothing in that window verifies, `minimal` is
False and the caller can see it; the number is never silently blessed.

`INF_ERR_EFFECT_ZERO` for a zero effect, `INF_ERR_DIMENSION_TOO_LARGE` when the required `n`
exceeds `MAX_SAMPLE_SIZE`, `INF_ERR_ALPHA_RANGE` for an `alpha` or `target_power` outside
`(0, 1)` or a quantile past 40 sigma. Nothing is clamped.

The t lane is an APPROXIMATION and says so
------------------------------------------
Exact power for a t test is the noncentral-t distribution function, which the tree does not
have and which this module does not add. The t lane uses the central-t shift
`1 - T_df(t_crit - nc)`, i.e. it takes the t critical value but a shifted CENTRAL t for the
alternative. `PowerReport.method` is `central_t_shift_approximation` so the caller is told,
and the approximation is a good one at the sizes power calculations use: at `d = 0.5`,
`alpha = 0.05` two-sided, it gives `n = 64` per group, which is the textbook noncentral-t
answer, while the normal lane gives 63.

Status codes 320-339 belong to the `inference` package; this module allocates none of its own
(rule 4e). Nothing here allocates per-observation memory, so the only bound that matters is
`MAX_SAMPLE_SIZE` on the ANSWER and `POWER_SEARCH_STEPS` on the search.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_inference_power.mojo
benchmark: benchmarks/mojo_benchmarks/bench_inference.mojo
docs: none
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs, sqrt

from ab_testing import power_analysis
from inference.core import (
    INF_ERR_ALPHA_RANGE,
    INF_ERR_DIMENSION_TOO_LARGE,
    INF_ERR_EFFECT_ZERO,
    INF_ERR_NOT_CONVERGED,
    INF_ERR_TOO_FEW,
    INF_OK,
    MAX_SAMPLE_SIZE,
    inference_finite,
    inference_t_cdf,
    inference_t_quantile,
)
from math_ext import norm_cdf, norm_ppf
from optimization.model import _ceil_f

# Beyond forty standard deviations no normal tail is a meaningful quantity, and
# `math_ext.norm_ppf` returns the FINITE sentinel 1e300 past the ends of (0,1) — which a
# finiteness guard cannot catch. Any quantile outside this range is a refusal.
comptime POWER_MAX_ABS_Z: Float64 = 40.0

# How far the verification search may move the closed-form n. The closed form and the
# verification differ only at the boundary (the two lanes' probits differ in the 4th
# decimal), so a handful of integers is all that is ever needed; the cap is what makes this a
# bounded search rather than an open loop.
comptime POWER_SEARCH_STEPS: Int = 64

comptime METHOD_NORMAL_TWO_SIDED: String = "normal_approximation_two_sided"
comptime METHOD_NORMAL_ONE_SIDED: String = "normal_approximation_one_sided"
comptime METHOD_T_TWO_SIDED: String = "central_t_shift_approximation_two_sided"
comptime METHOD_T_ONE_SIDED: String = "central_t_shift_approximation_one_sided"


@fieldwise_init
struct PowerReport(Copyable, Movable):
    """The power of a two-sample mean comparison at a stated design, or a refusal.

    `power` is meaningful only when `status == INF_OK`; `power_known` says so explicitly so a
    refusal cannot be read as "power is 0.0", which is a legitimate value of the real
    quantity (an effect of zero under a one-sided test approaches it).

    `method` is part of the answer, not decoration: a normal-approximation power and a
    central-t-shift power at the same design differ by about half a percentage point at
    `n = 64`, and which one was computed determines whether `n` should be 63 or 64.

    `df` is `2n - 2` for the t lane and -1 for the normal lane, where no degrees of freedom
    enter. `critical_value` is the rejection threshold on the test statistic's own scale.
    """

    var status: Int
    var method: String
    var effect_size: Float64
    var n_per_group: Int
    var alpha: Float64
    var one_sided: Bool
    var power_known: Bool
    var power: Float64
    var df: Float64
    var critical_value: Float64


fn _power_failure(
    code: Int, method: String, d: Float64, n: Int, alpha: Float64, one_sided: Bool
) -> PowerReport:
    return PowerReport(
        code, method, d, n, alpha, one_sided, False, 0.0, -1.0, 0.0
    )


fn power_design_defect(effect_size: Float64, n_per_group: Int, alpha: Float64) -> Int:
    """`INF_OK`, or the one status describing what is wrong with this design.

    PUBLIC and the SINGLE design validator for both lanes, so the normal and t lanes cannot
    disagree about what a valid design is (rule 3). `n_per_group` must be at least 2 because a
    two-sample comparison needs a within-group variance estimate, and at most
    `MAX_SAMPLE_SIZE` so the t lane's degrees of freedom stay well inside the Float64 integer
    grid. `alpha` must be strictly inside `(0, 1)`: at 0 nothing is ever rejected and at 1
    everything is, so neither is a decision rule.
    """
    if not inference_finite(effect_size):
        return INF_ERR_ALPHA_RANGE
    if n_per_group < 2:
        return INF_ERR_TOO_FEW
    if n_per_group > MAX_SAMPLE_SIZE:
        return INF_ERR_DIMENSION_TOO_LARGE
    if not inference_finite(alpha) or alpha <= 0.0 or alpha >= 1.0:
        return INF_ERR_ALPHA_RANGE
    return INF_OK


fn _checked_normal_quantile(p: Float64) -> Float64:
    """`math_ext.norm_ppf(p)` when the answer is a real quantile, else `-1e308` as a marker.

    `norm_ppf` returns the FINITE sentinel `+-1e300` for `p` at or past the ends of `(0, 1)`,
    so `inference_finite` cannot detect the failure. The magnitude check against
    `POWER_MAX_ABS_Z` can, and a caller tests the return with
    `not inference_finite(z) or fabs(z) > POWER_MAX_ABS_Z`.
    """
    if not inference_finite(p) or p <= 0.0 or p >= 1.0:
        return -1.0e308
    var z = norm_ppf(p)
    if not inference_finite(z) or fabs(z) > POWER_MAX_ABS_Z:
        return -1.0e308
    return z


fn power_two_means_flat(
    effect_size: Float64, n_per_group: Int, alpha: Float64, one_sided: Bool
) -> PowerReport:
    """Normal-approximation power for a two-sample comparison of means at `n` per group.

    `effect_size` is Cohen's d — the mean difference in standard-deviation units — so the
    noncentrality is `d sqrt(n/2)`.

    The two-sided lane is the frozen `ab_testing.power_analysis(d, n, alpha)`, called
    unchanged; it already computes `Phi(nc - z) + Phi(-nc - z)` and there is nothing to add
    but the validation it lacks. The one-sided lane has no frozen form and is
    `Phi(|nc| - z_{1-alpha})` from `math_ext.norm_cdf` / `norm_ppf`; the absolute value makes
    the test directed at the effect's own sign, which is the only one-sided test anyone means
    to power.

    See the module docstring for why the two lanes agree only to ~1e-4: they draw their
    quantile from two different frozen probits.
    """
    var method = METHOD_NORMAL_ONE_SIDED if one_sided else METHOD_NORMAL_TWO_SIDED
    var defect = power_design_defect(effect_size, n_per_group, alpha)
    if defect != INF_OK:
        return _power_failure(defect, method, effect_size, n_per_group, alpha, one_sided)

    var nc = fabs(effect_size) * sqrt(Float64(n_per_group) / 2.0)
    if not inference_finite(nc):
        return _power_failure(
            INF_ERR_DIMENSION_TOO_LARGE, method, effect_size, n_per_group, alpha, one_sided
        )
    if one_sided:
        var z = _checked_normal_quantile(1.0 - alpha)
        if not inference_finite(z) or fabs(z) > POWER_MAX_ABS_Z:
            return _power_failure(
                INF_ERR_ALPHA_RANGE, method, effect_size, n_per_group, alpha, one_sided
            )
        var pw = norm_cdf(nc - z)
        if pw < 0.0:
            pw = 0.0
        if pw > 1.0:
            pw = 1.0
        return PowerReport(
            INF_OK, method, effect_size, n_per_group, alpha, one_sided, True, pw, -1.0, z
        )

    var z2 = _checked_normal_quantile(1.0 - alpha / 2.0)
    if not inference_finite(z2) or fabs(z2) > POWER_MAX_ABS_Z:
        return _power_failure(
            INF_ERR_ALPHA_RANGE, method, effect_size, n_per_group, alpha, one_sided
        )
    var frozen = power_analysis(effect_size, n_per_group, alpha)
    if not inference_finite(frozen) or frozen < 0.0 or frozen > 1.0:
        return _power_failure(
            INF_ERR_ALPHA_RANGE, method, effect_size, n_per_group, alpha, one_sided
        )
    return PowerReport(
        INF_OK, method, effect_size, n_per_group, alpha, one_sided, True, frozen, -1.0, z2
    )


fn power_two_means_t_flat(
    effect_size: Float64, n_per_group: Int, alpha: Float64, one_sided: Bool
) -> PowerReport:
    """Central-t-shift power for a two-sample t test at `n` per group. An APPROXIMATION.

    `df = 2n - 2`, `t_crit = inference_t_quantile(1 - alpha/2, df)` (or `1 - alpha` one-sided),
    `nc = |d| sqrt(n/2)`, and

        power = 1 - T_df(t_crit - nc)                     one-sided
        power = 1 - T_df(t_crit - nc) + T_df(-t_crit - nc) two-sided

    The exact quantity is the NONCENTRAL t distribution function, which this module does not
    add; `method` says `central_t_shift_approximation` so nobody reads the result as exact.
    The approximation is close where power calculations live — at `d = 0.5`, two-sided
    `alpha = 0.05` it returns `n = 64` per group, the textbook noncentral-t answer — and it is
    the right lane whenever `n` is small enough for the normal approximation's missing
    variance-estimation penalty to matter.

    Refuses when the t quantile or either tail does not exist, rather than substituting a
    normal one: an approximation that silently changes distribution is not the method its
    label claims.
    """
    var method = METHOD_T_ONE_SIDED if one_sided else METHOD_T_TWO_SIDED
    var defect = power_design_defect(effect_size, n_per_group, alpha)
    if defect != INF_OK:
        return _power_failure(defect, method, effect_size, n_per_group, alpha, one_sided)

    var df = Float64(2 * n_per_group - 2)
    if df < 1.0:
        return _power_failure(
            INF_ERR_TOO_FEW, method, effect_size, n_per_group, alpha, one_sided
        )
    var tail = alpha if one_sided else alpha / 2.0
    var t_crit = inference_t_quantile(1.0 - tail, df)
    if not inference_finite(t_crit):
        return _power_failure(
            INF_ERR_ALPHA_RANGE, method, effect_size, n_per_group, alpha, one_sided
        )
    var nc = fabs(effect_size) * sqrt(Float64(n_per_group) / 2.0)
    if not inference_finite(nc):
        return _power_failure(
            INF_ERR_DIMENSION_TOO_LARGE, method, effect_size, n_per_group, alpha, one_sided
        )
    var upper = inference_t_cdf(t_crit - nc, df)
    if not inference_finite(upper):
        return _power_failure(
            INF_ERR_ALPHA_RANGE, method, effect_size, n_per_group, alpha, one_sided
        )
    var pw = 1.0 - upper
    if not one_sided:
        var lower = inference_t_cdf(-t_crit - nc, df)
        if not inference_finite(lower):
            return _power_failure(
                INF_ERR_ALPHA_RANGE, method, effect_size, n_per_group, alpha, one_sided
            )
        pw += lower
    if pw < 0.0:
        pw = 0.0
    if pw > 1.0:
        pw = 1.0
    return PowerReport(
        INF_OK, method, effect_size, n_per_group, alpha, one_sided, True, pw, df, t_crit
    )


@fieldwise_init
struct SampleSizeReport(Copyable, Movable):
    """The per-group sample size a target power needs, with the verification that it does.

    `n_per_group` is meaningful only when `status == INF_OK`, and `minimal` says whether the
    number was VERIFIED to be the smallest that reaches `target_power`:

        minimal = (achieved_power >= target_power) and (power_at_n_minus_1 < target_power)

    Both halves are measured by re-evaluating the power function at `n` and `n - 1`, so this
    is not the algebra restating itself. `closed_form_n` is what the inversion produced before
    verification and `search_steps` is how far the search had to move it; a nonzero
    `search_steps` is the boundary case, not a defect.

    `minimal = False` with `status == INF_OK` is a real outcome and is reported rather than
    hidden: it means `n_per_group` reaches the target but the search window could not confirm
    that `n - 1` does not.
    """

    var status: Int
    var method: String
    var effect_size: Float64
    var alpha: Float64
    var target_power: Float64
    var one_sided: Bool
    var n_per_group: Int
    var closed_form_n: Int
    var search_steps: Int
    var achieved_power: Float64
    var power_at_n_minus_1: Float64
    var minimal: Bool


fn _size_failure(
    code: Int, method: String, d: Float64, alpha: Float64,
    target: Float64, one_sided: Bool,
) -> SampleSizeReport:
    return SampleSizeReport(
        code, method, d, alpha, target, one_sided, 0, 0, 0, 0.0, 0.0, False
    )


fn _power_at(n: Int, d: Float64, alpha: Float64, one_sided: Bool, use_t: Bool) -> Float64:
    """Power at `n` per group through whichever lane the caller asked for, or absent.

    One place routes the verification to the same function a caller would call, so a sample
    size verified here cannot disagree with the power a caller computes for it. Returns a
    negative value when the lane refused, which every `>= target_power` test reads as "did
    not reach it".
    """
    if use_t:
        var rt = power_two_means_t_flat(d, n, alpha, one_sided)
        if rt.status != INF_OK or not rt.power_known:
            return -1.0
        return rt.power
    var rn = power_two_means_flat(d, n, alpha, one_sided)
    if rn.status != INF_OK or not rn.power_known:
        return -1.0
    return rn.power


fn _sample_size(
    effect_size: Float64, alpha: Float64, target_power: Float64,
    one_sided: Bool, use_t: Bool, method: String,
) -> SampleSizeReport:
    """The shared inversion + verification, so the two lanes cannot drift apart.

    Closed form, then a bounded search that moves `n` to the smallest integer whose MEASURED
    power reaches `target_power`. The search is the reason `minimal` can be trusted: the
    closed form inverts the normal approximation and the t lane's power is not that function,
    so on the t lane the inversion is only a starting point and the verification is what
    decides.
    """
    if not inference_finite(effect_size):
        return _size_failure(
            INF_ERR_ALPHA_RANGE, method, effect_size, alpha, target_power, one_sided
        )
    if effect_size == 0.0:
        # No sample size detects an effect of exactly zero: power equals alpha for every n.
        # `ab_testing.sample_size_proportion` returns 1000000 here.
        return _size_failure(
            INF_ERR_EFFECT_ZERO, method, effect_size, alpha, target_power, one_sided
        )
    if not inference_finite(alpha) or alpha <= 0.0 or alpha >= 1.0:
        return _size_failure(
            INF_ERR_ALPHA_RANGE, method, effect_size, alpha, target_power, one_sided
        )
    if not inference_finite(target_power) or target_power <= 0.0 or target_power >= 1.0:
        return _size_failure(
            INF_ERR_ALPHA_RANGE, method, effect_size, alpha, target_power, one_sided
        )

    var tail = alpha if one_sided else alpha / 2.0
    var z_alpha = _checked_normal_quantile(1.0 - tail)
    var z_beta = _checked_normal_quantile(target_power)
    if fabs(z_alpha) > POWER_MAX_ABS_Z or fabs(z_beta) > POWER_MAX_ABS_Z:
        return _size_failure(
            INF_ERR_ALPHA_RANGE, method, effect_size, alpha, target_power, one_sided
        )
    var ratio = (z_alpha + z_beta) / fabs(effect_size)
    var raw = 2.0 * ratio * ratio
    if not inference_finite(raw) or raw < 0.0:
        return _size_failure(
            INF_ERR_DIMENSION_TOO_LARGE, method, effect_size, alpha, target_power, one_sided
        )
    var ceiled = _ceil_f(raw)
    # Compared as a Float64 BEFORE any Int conversion: `Int()` past the Float64 integer grid
    # is an out-of-range fptosi, which is poison rather than truncation (rule 4c), so a guard
    # placed after the conversion is already too late.
    if not inference_finite(ceiled) or ceiled > Float64(MAX_SAMPLE_SIZE):
        return _size_failure(
            INF_ERR_DIMENSION_TOO_LARGE, method, effect_size, alpha, target_power, one_sided
        )
    var closed = Int(ceiled)
    if closed < 2:
        closed = 2

    var n = closed
    var steps = 0
    # Walk up while the target is not reached, then down while n-1 still reaches it. Both
    # loops are capped, so this is a bounded refinement of a closed form and never a search.
    while steps < POWER_SEARCH_STEPS and n < MAX_SAMPLE_SIZE:
        if _power_at(n, effect_size, alpha, one_sided, use_t) >= target_power:
            break
        n += 1
        steps += 1
    while steps < POWER_SEARCH_STEPS and n > 2:
        if _power_at(n - 1, effect_size, alpha, one_sided, use_t) < target_power:
            break
        n -= 1
        steps += 1

    var achieved = _power_at(n, effect_size, alpha, one_sided, use_t)
    var below = _power_at(n - 1, effect_size, alpha, one_sided, use_t) if n > 2 else -1.0
    if achieved < 0.0:
        return _size_failure(
            INF_ERR_DIMENSION_TOO_LARGE, method, effect_size, alpha, target_power, one_sided
        )
    var minimal = achieved >= target_power and (n <= 2 or below < target_power)
    # The walk-up loop breaks on `steps < POWER_SEARCH_STEPS and n < MAX_SAMPLE_SIZE`, so it can
    # stop having NEVER reached the target. `INF_OK` was returned regardless, and a sample-size
    # calculator answering OK with an underpowered `n` is the worst shape this package can produce:
    # the number goes straight into a study design, and by the time the power is missing the data
    # is already collected.
    #
    # `minimal = False` did not carry this. It conflates two unrelated facts -- "this n reaches the
    # target but a smaller one might too" and "this n does not reach the target at all" -- in one
    # boolean, and the first is a rounding nicety while the second invalidates the answer.
    #
    # INF_ERR_NOT_CONVERGED (328) is the package's existing code for exactly this: the bounded
    # refinement did not arrive. The diagnostic fields are kept populated rather than blanked, so a
    # caller can see how far it got (`n`, `achieved_power`, `steps`) and decide whether to widen the
    # budget -- an empty report would hide the one number that explains the refusal.
    if achieved < target_power:
        return SampleSizeReport(
            INF_ERR_NOT_CONVERGED, method, effect_size, alpha, target_power, one_sided,
            n, closed, steps, achieved, below, False,
        )
    return SampleSizeReport(
        INF_OK, method, effect_size, alpha, target_power, one_sided,
        n, closed, steps, achieved, below, minimal,
    )


fn sample_size_two_means_flat(
    effect_size: Float64, alpha: Float64, target_power: Float64, one_sided: Bool
) -> SampleSizeReport:
    """Per-group sample size for a target power, normal approximation, VERIFIED.

    `n = ceil(2 ((z_alpha + z_beta) / d)^2)` inverted from the normal approximation, then
    checked by re-evaluating `power_two_means_flat` at `n` and `n - 1` — see the module
    docstring for why the verification is the deliverable and not the algebra.

    Known values, both asserted in the suite: `d = 0.5`, two-sided `alpha = 0.05`,
    `target_power = 0.80` gives `n = 63` with `achieved_power = 0.80130` and
    `power_at_n_minus_1 = 0.79501`, so `minimal` is True. (The t lane gives 64, which is the
    textbook answer for a t test — the difference is exactly the variance-estimation penalty
    the normal approximation omits.)
    """
    var method = METHOD_NORMAL_ONE_SIDED if one_sided else METHOD_NORMAL_TWO_SIDED
    return _sample_size(effect_size, alpha, target_power, one_sided, False, method)


fn sample_size_two_means_t_flat(
    effect_size: Float64, alpha: Float64, target_power: Float64, one_sided: Bool
) -> SampleSizeReport:
    """Per-group sample size for a target power, central-t-shift lane, VERIFIED.

    Starts from the normal-approximation closed form and then searches on the MEASURED t-lane
    power, which is the whole reason the search exists: the closed form does not invert this
    lane's power function, so `search_steps` is normally 1 here and `minimal` is what proves
    the answer.

    Known value, asserted in the suite: `d = 0.5`, two-sided `alpha = 0.05`,
    `target_power = 0.80` gives `n = 64`, the textbook noncentral-t answer, with
    `achieved_power = 0.80138` and `power_at_n_minus_1 = 0.79508`.
    """
    var method = METHOD_T_ONE_SIDED if one_sided else METHOD_T_TWO_SIDED
    return _sample_size(effect_size, alpha, target_power, one_sided, True, method)
