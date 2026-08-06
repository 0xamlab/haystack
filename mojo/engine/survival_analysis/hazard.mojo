"""
survival_analysis.hazard — Nelson-Aalen cumulative hazard with its variance and band.

Composition, not arithmetic
--------------------------
The cumulative hazard itself comes from the frozen `survival.nelson_aalen`: it is called
on the canonically sorted observations and its `H` column is copied through unchanged, so
`sum d_j / n_j` has exactly one implementation in this tree. What is added here is
everything the frozen kernel does not have -- validation (it shares both of
`kaplan_meier`'s measured failure modes, the out-of-bounds abort on a short indicator list
and the infinite loop on a NaN time, because it has the same grouping loop), the variance,
a confidence band, and the alignment check between the frozen output and the risk table
the variance is computed from.

The variance estimator, and why this one
----------------------------------------
    sigma2(t) = sum_{t_j <= t} d_j / n_j^2

This is the Aalen estimator, which is what `survfit(type = "aalen")` reports. The
alternative in circulation is `sum d_j (n_j - d_j) / n_j^3`, which is smaller and is the
finite-sample-corrected form; the two agree to O(1/n). One is chosen and named rather than
averaged, and the choice is visible in the field name.

The important practical difference from Greenwood is that this one always EXISTS. Its
denominator is `n_j^2`, never `n_j - d_j`, so the tie group in which the whole risk set
fails -- the case that makes the Kaplan-Meier variance undefined -- is an ordinary row
here. That asymmetry is real and is the reason both estimators are worth having.

The band is on log H
--------------------
    [ H * exp(-z * sigma / H), H * exp(+z * sigma / H) ]

A cumulative hazard is non-negative and unbounded above, so a linear band crosses zero for
any H smaller than `z * sigma` -- which is most of the early curve. The log band cannot,
because it is a band on log H, which is unbounded in both directions. It is undefined at
`H = 0`; on this package's rows `d_j >= 1`, so `H > 0` on every row and the flag is there
for the caller's benefit rather than because the case arises.

Kernel-smoothed hazard RATE: genuinely-missing, NOT a wrapper
------------------------------------------------------------
An earlier revision of this module published the frozen `survival.hazard_rate` behind a
bandwidth guard and called the capability "surface-gap + missing-driver, wrapped". That
classification was WRONG and the published numbers were wrong with it. The frozen kernel
computes, at each distinct event time `t`,

    num = sum_{i : |t - t_i| <= b}  K(u_i) * [t_i is an event]
    den = sum_{i : |t - t_i| <= b}  K(u_i)                        <- ALL observations
    h   = num / (den * b)

`den` sums over observations whose TIME is near `t`; it is not the at-risk set, and it is
not the number of subjects who could have failed at `t`. On a sample with no censoring
every observation is an event, so `num == den` term for term and `h` is EXACTLY `1/b` at
every event time, for every dataset. Measured before the repair, times 1..5 all events,
`b = 2`: rate = 0.5, 0.5, 0.5, 0.5, 0.5. Data-independent. The correct curve for that
sample rises 3.5x across its length.

So the estimator did not exist in this tree and is written here, in this namespace. It is
the standard kernel-smoothed hazard, Klein & Moeschberger *Survival Analysis* eq. 6.2.1:

    h(t) = (1/b) * sum_j K((t - t_j)/b) * dH_j        dH_j = d_j / n_j

with the Epanechnikov kernel `K(u) = 0.75 (1 - u^2)` on `|u| <= 1`. The increments `dH_j`
are the Nelson-Aalen increments -- the same `Float64(d_j)/Float64(n_j)` the frozen
`nelson_aalen` accumulates, taken from the risk table so that the smoother and the
cumulative hazard are built from ONE set of risk sets. The composition is then CHECKED, not
asserted: `sum_j dH_j` is compared against the frozen kernel's own `H` at the last event
time, and a disagreement beyond that sum's own error budget (`8 * k * DBL_EPSILON * |H|`,
one rounding per row of the quantity being judged) refuses the fit rather than reporting a
smoother built on increments the frozen kernel would not recognise.

What the smoother reports absent, and what it reports as bias
------------------------------------------------------------
Every returned time is an event time, so its own increment is always in the window with
`u = 0` and `K(0) = 0.75 > 0`: the estimate is strictly positive at every returned time and
`has_rate` is False only if the value is not representable (a denormal bandwidth can
overflow the division). A zero is therefore never published as a rate.

`boundary[j]` is True when the window `[t_j - b, t_j + b]` extends past the first or last
event time. There the kernel integrates over a region where no increment can exist, while
the `1/b` normalisation assumes a full window, so the estimate is biased TOWARD ZERO. No
boundary kernel is applied -- that is a second estimator with its own bias-variance
trade-off and no hand-checkable reference here -- and the flag says so per point instead of
leaving the reader to rediscover it. On times 1..5 with `b = 2`, points 1, 2, 4 and 5 are
flagged and only `t = 3` is interior.

Bounding memory is not bounding work, and the charge is EXACT
------------------------------------------------------------
The cost is the number of (event time, event time) pairs inside one bandwidth, which
depends on `b` and on the spacing -- from `k` (tiny `b`) to `k^2` (`b` spanning the
sample). Charging `k * n` once, as the wrapper did, undercharged the frozen kernel's two
`O(k * n)` passes by 6x: a request declared at ~1 s measured 5.97 s. Here the pair count is
computed EXACTLY by a two-pointer pass in `O(k)` before any kernel is evaluated, charged
against `SA_MAX_WORK`, and then the evaluation performs exactly that many kernel
evaluations -- the declared unit cost is the measured one, and it is published as
`kernel_pairs` so a caller can see what was charged.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_survival_analysis_hazard.mojo
benchmark: benchmarks/mojo_benchmarks/bench_survival_analysis.mojo
docs: gitbook/engine/survival-analysis.md
version_introduced: 0.7.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs
from std.math import exp, sqrt

from survival import nelson_aalen as frozen_nelson_aalen

from survival_analysis.base import (
    SA_DBL_EPSILON,
    SA_ERR_BAD_SHAPE_PARAM,
    SA_ERR_SHAPE,
    SA_ERR_WORK_BUDGET,
    SA_MAX_WORK,
    SA_OK,
    sa_is_finite,
    sa_risk_table,
    sa_sort_observations,
    sa_validate_confidence,
    sa_work_fits,
    sa_z_for_confidence,
)

# The Epanechnikov kernel's peak, `K(0) = 3/4`. Named because both the estimator and the
# hand-checkable known values in the suite are written in terms of it.
comptime SA_EPANECHNIKOV_PEAK: Float64 = 0.75


struct NAFit(Copyable, Movable):
    """A Nelson-Aalen cumulative hazard estimate with its uncertainty.

    Every list has `n_event_times` entries, index `j` refers to `time[j]`, and the `hazard`
    column is the frozen `survival.nelson_aalen` output verbatim.

    `frozen_rows_aligned` is False only if the frozen kernel and the risk table disagreed
    about how many event times the sample has, which would mean one of them was reading a
    different dataset; the fit is refused in that case rather than reported with a variance
    attached to the wrong times.
    """

    var status: Int
    var n_obs: Int
    var n_events: Int
    var n_censored: Int
    var n_event_times: Int
    var conf_level: Float64
    var z: Float64
    var frozen_rows_aligned: Bool
    var time: List[Float64]
    var hazard: List[Float64]
    var at_risk: List[Int]
    var events: List[Int]
    var std_error: List[Float64]
    var has_std_error: List[Bool]
    var lower: List[Float64]
    var upper: List[Float64]
    var has_band: List[Bool]

    def __init__(out self, status: Int):
        self.status = status
        self.n_obs = 0
        self.n_events = 0
        self.n_censored = 0
        self.n_event_times = 0
        self.conf_level = 0.0
        self.z = 0.0
        self.frozen_rows_aligned = False
        self.time = List[Float64]()
        self.hazard = List[Float64]()
        self.at_risk = List[Int]()
        self.events = List[Int]()
        self.std_error = List[Float64]()
        self.has_std_error = List[Bool]()
        self.lower = List[Float64]()
        self.upper = List[Float64]()
        self.has_band = List[Bool]()


def na_fit(times: List[Float64], event: List[Int], conf_level: Float64) -> NAFit:
    """Nelson-Aalen cumulative hazard, Aalen variance and a log-transformed band.

    `event[i]` is 1 for an event and 0 for a right-censored observation, and
    `len(event) == len(times)` is required exactly -- a list-to-list relation the `counts:`
    grammar does not express, validated in the kernel as `SA_ERR_CENSOR_LENGTH`.

    The `hazard` column is the frozen kernel's; only the variance and the band are new. The
    frozen output carries a synthetic origin row `[0.0, 0.0]` which is dropped, and the
    remaining row count is checked against the risk table before either is indexed.

    @capability na_fit
    complexity: O(n log n)
    counts: none
    @endcapability
    """
    var conf_status = sa_validate_confidence(conf_level)
    if conf_status != SA_OK:
        return NAFit(conf_status)

    var sorted = sa_sort_observations(times, event)
    if sorted.status != SA_OK:
        return NAFit(sorted.status)
    var table = sa_risk_table(times, event)
    if table.status != SA_OK:
        return NAFit(table.status)

    var frozen = frozen_nelson_aalen(sorted.time, sorted.is_event)
    # Row 0 of the frozen output is the synthetic origin [0.0, 0.0]; the rest are one per
    # distinct event time, in ascending order, which is the risk table's own row order.
    var frozen_rows = len(frozen) - 1
    if frozen_rows != table.n_event_times:
        var mismatch = NAFit(SA_ERR_SHAPE)
        return mismatch^

    var out = NAFit(SA_OK)
    out.n_obs = table.n_obs
    out.n_events = table.n_events
    out.n_censored = table.n_censored
    out.n_event_times = table.n_event_times
    out.conf_level = conf_level
    out.frozen_rows_aligned = True
    var z = sa_z_for_confidence(conf_level)
    out.z = z

    var running: Float64 = 0.0
    for j in range(table.n_event_times):
        ref row = frozen[j + 1]
        if len(row) < 2:
            return NAFit(SA_ERR_SHAPE)
        var h = row[1]
        out.time.append(table.time[j])
        out.at_risk.append(table.at_risk[j])
        out.events.append(table.events[j])
        if not sa_is_finite(h) or h < 0.0:
            return NAFit(SA_ERR_SHAPE)
        out.hazard.append(h)

        var n = Float64(table.at_risk[j])
        var d = Float64(table.events[j])
        if n > 0.0:
            running += d / (n * n)

        var se: Float64 = 0.0
        var has_se = False
        if running > 0.0:
            var cand = sqrt(running)
            if sa_is_finite(cand):
                se = cand
                has_se = True
        out.std_error.append(se)
        out.has_std_error.append(has_se)

        var lo: Float64 = 0.0
        var hi: Float64 = 0.0
        var has_band = False
        if has_se and h > 0.0:
            var spread = z * se / h
            if sa_is_finite(spread):
                var cand_lo = h * exp(-spread)
                var cand_hi = h * exp(spread)
                if sa_is_finite(cand_lo) and sa_is_finite(cand_hi) and cand_lo <= cand_hi:
                    lo = cand_lo
                    hi = cand_hi
                    has_band = True
        out.lower.append(lo)
        out.upper.append(hi)
        out.has_band.append(has_band)

    return out^


struct SmoothedHazard(Copyable, Movable):
    """A kernel-smoothed hazard RATE at each distinct event time.

    `rate[j]` is `h(time[j])` from Klein & Moeschberger eq. 6.2.1 and `increment[j]` is the
    Nelson-Aalen increment `d_j / n_j` it was built from, published so the estimate can be
    recomputed by hand from the returned columns alone.

    `boundary[j]` True means the kernel window reached past the first or last event time, so
    that point is biased toward zero; the estimate is still returned, flagged.

    `increment_sum` is `sum_j increment[j]` and `frozen_cumulative_hazard` is the frozen
    `survival.nelson_aalen` total. `frozen_agrees` is their agreement within the sum's own
    error budget, and `status` is a refusal when it is False -- the smoother and the
    cumulative hazard in this package are not allowed to disagree about the increments.

    `kernel_pairs` is the number of kernel evaluations performed, which is exactly the
    number charged against the work budget before any of them ran.
    """

    var status: Int
    var bandwidth: Float64
    var n_obs: Int
    var n_events: Int
    var n_event_times: Int
    var kernel_pairs: Int
    var increment_sum: Float64
    var frozen_cumulative_hazard: Float64
    var frozen_residual: Float64
    var frozen_agrees: Bool
    var time: List[Float64]
    var rate: List[Float64]
    var has_rate: List[Bool]
    var increment: List[Float64]
    var boundary: List[Bool]

    def __init__(out self, status: Int):
        self.status = status
        self.bandwidth = 0.0
        self.n_obs = 0
        self.n_events = 0
        self.n_event_times = 0
        self.kernel_pairs = 0
        self.increment_sum = 0.0
        self.frozen_cumulative_hazard = 0.0
        self.frozen_residual = 0.0
        self.frozen_agrees = False
        self.time = List[Float64]()
        self.rate = List[Float64]()
        self.has_rate = List[Bool]()
        self.increment = List[Float64]()
        self.boundary = List[Bool]()


def na_smoothed_hazard(
    times: List[Float64], event: List[Int], bandwidth: Float64
) -> SmoothedHazard:
    """Epanechnikov kernel-smoothed hazard rate, Klein & Moeschberger eq. 6.2.1.

        h(t) = (1/b) * sum_j K((t - t_j)/b) * d_j / n_j       K(u) = 0.75 (1 - u^2)

    evaluated at every distinct event time. `event[i]` is 1 for an event and 0 for a
    right-censored observation, and `len(event) == len(times)` is required exactly.

    `bandwidth` must be finite and strictly positive: `SA_ERR_BAD_SHAPE_PARAM` otherwise.
    A zero bandwidth is a division by zero, not a narrow window, and a negative one inverts
    the `|u| <= 1` test so the window becomes the complement of itself.

    This is NOT `survival.hazard_rate`. That kernel divides a sum over events by a sum over
    all observations at the same times, which equals `1/b` on any uncensored sample
    regardless of the data; see the module docstring for the measurement. The estimator is
    written here and the increments it uses are cross-checked against the frozen
    `nelson_aalen` total, so the two cannot drift apart.

    Work is charged EXACTLY: the number of in-window (event time, event time) pairs is
    counted by a two-pointer pass in `O(k)` and charged against `SA_MAX_WORK` before the
    first kernel evaluation. `k` here is the number of distinct event times, at most `n`.

    @capability na_smoothed_hazard
    complexity: O(n log n + kernel_pairs)
    counts: none
    @endcapability
    """
    var sorted = sa_sort_observations(times, event)
    if sorted.status != SA_OK:
        return SmoothedHazard(sorted.status)
    if not sa_is_finite(bandwidth) or bandwidth <= 0.0:
        return SmoothedHazard(SA_ERR_BAD_SHAPE_PARAM)

    var table = sa_risk_table(times, event)
    if table.status != SA_OK:
        return SmoothedHazard(table.status)
    var k = table.n_event_times
    if k == 0:
        return SmoothedHazard(SA_ERR_SHAPE)
    if len(table.time) != k or len(table.at_risk) != k or len(table.events) != k:
        return SmoothedHazard(SA_ERR_SHAPE)

    # The Nelson-Aalen increments, `Float64(d_j) / Float64(n_j)` -- the same division the
    # frozen `nelson_aalen` performs, on the same risk sets, so the sum below is comparable
    # to the frozen total bit for bit rather than approximately.
    var inc = List[Float64]()
    var inc_sum: Float64 = 0.0
    for j in range(k):
        var nj = table.at_risk[j]
        var dj = table.events[j]
        if nj <= 0 or dj <= 0 or dj > nj:
            return SmoothedHazard(SA_ERR_SHAPE)
        var d = Float64(dj) / Float64(nj)
        if not sa_is_finite(d) or d <= 0.0:
            return SmoothedHazard(SA_ERR_SHAPE)
        inc.append(d)
        inc_sum += d

    # The exact pair count, before any kernel is evaluated. `lo` and `hi` are monotone in
    # `j` because `table.time` is ascending, so this pass is O(k) and the count it produces
    # is precisely the number of evaluations the loop below performs. Differences of
    # observed times are used rather than `t_j +/- b`, which would lose the comparison to
    # rounding at extreme magnitudes.
    var lo = 0
    var hi = 0
    var pairs: Int = 0
    for j in range(k):
        var t = table.time[j]
        while lo < k and t - table.time[lo] > bandwidth:
            lo += 1
        while hi < k and table.time[hi] - t <= bandwidth:
            hi += 1
        pairs += hi - lo
    var factors = List[Int]()
    factors.append(pairs)
    if not sa_work_fits(factors, SA_MAX_WORK):
        return SmoothedHazard(SA_ERR_WORK_BUDGET)

    var out = SmoothedHazard(SA_OK)
    out.bandwidth = bandwidth
    out.n_obs = table.n_obs
    out.n_events = table.n_events
    out.n_event_times = k
    out.kernel_pairs = pairs
    out.increment_sum = inc_sum if sa_is_finite(inc_sum) else 0.0

    # The frozen cumulative hazard, as the check on the increments. `nelson_aalen`'s row 0
    # is the synthetic origin; the last row carries H at the last event time.
    var frozen = frozen_nelson_aalen(sorted.time, sorted.is_event)
    if len(frozen) != k + 1:
        return SmoothedHazard(SA_ERR_SHAPE)
    ref last = frozen[k]
    if len(last) < 2:
        return SmoothedHazard(SA_ERR_SHAPE)
    var frozen_h = last[1]
    if not sa_is_finite(frozen_h):
        return SmoothedHazard(SA_ERR_SHAPE)
    out.frozen_cumulative_hazard = frozen_h
    # The quantity judged is a sum of `k` rounded increments, so its error budget is
    # `k * DBL_EPSILON * |sum|` -- the magnitude of THIS aggregate against the other
    # computation of the SAME aggregate, and nothing borrowed from a different item.
    var residual = fabs(inc_sum - frozen_h)
    out.frozen_residual = residual if sa_is_finite(residual) else 0.0
    var budget = 8.0 * Float64(k) * SA_DBL_EPSILON * fabs(frozen_h) + SA_DBL_EPSILON
    out.frozen_agrees = sa_is_finite(residual) and residual <= budget
    if not out.frozen_agrees:
        out.status = SA_ERR_SHAPE
        return out^

    var first_event = table.time[0]
    var last_event = table.time[k - 1]
    lo = 0
    hi = 0
    var performed: Int = 0
    for j in range(k):
        var t = table.time[j]
        while lo < k and t - table.time[lo] > bandwidth:
            lo += 1
        while hi < k and table.time[hi] - t <= bandwidth:
            hi += 1
        # Every addend is non-negative (K >= 0 on the window, every increment > 0), so a
        # compensated sum would compensate for a cancellation that cannot occur; the
        # accumulation is direct for the same reason `km_fit`'s Greenwood prefix is.
        var acc: Float64 = 0.0
        for i in range(lo, hi):
            var u = (t - table.time[i]) / bandwidth
            if u < 0.0:
                u = -u
            if u <= 1.0:
                acc += SA_EPANECHNIKOV_PEAK * (1.0 - u * u) * inc[i]
            performed += 1
        var h = acc / bandwidth
        out.time.append(t)
        out.increment.append(inc[j])
        if sa_is_finite(h) and h > 0.0:
            out.rate.append(h)
            out.has_rate.append(True)
        else:
            # Unreachable for a normal bandwidth: `u = 0` at `t_j` itself contributes
            # `0.75 * inc[j] > 0`. A denormal bandwidth can still overflow the division,
            # and a non-representable rate is reported absent with 0.0 in the slot rather
            # than turned into a transport error by a raw infinity.
            out.rate.append(0.0)
            out.has_rate.append(False)
        out.boundary.append(t - first_event < bandwidth or last_event - t < bandwidth)

    if performed != pairs:
        return SmoothedHazard(SA_ERR_SHAPE)
    return out^
