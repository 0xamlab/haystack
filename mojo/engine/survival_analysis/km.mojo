"""
survival_analysis.km — Kaplan-Meier with Greenwood variance and confidence bands.

What was already there, and what is added
-----------------------------------------
The frozen `survival.kaplan_meier` computes the product-limit estimate correctly and
returns `(time, survival, at_risk, events)` per event time. It is CALLED here, never
reimplemented: `base.sa_risk_table` copies its `survival` column through, so there is
exactly one definition of a Kaplan-Meier estimate in this tree.

What did not exist anywhere is the uncertainty. A survival curve without a variance is
not a usable estimate -- two curves that differ by a factor of two can be statistically
indistinguishable at n = 12 and decisively different at n = 1200, and the point estimate
alone cannot tell those apart. This module adds:

* the Greenwood variance estimator,
* a log-log transformed confidence band, which is the convention R's `survfit` uses by
  default,
* the median survival time under BOTH tie conventions in circulation,
* restricted mean survival time and step-function lookup, wrapping the frozen
  `restricted_mean` and `survival_at_time` behind the validation the frozen entry points
  do not have.

Greenwood, and where it does not exist
--------------------------------------
    Var(S(t)) = S(t)^2 * sum_{t_j <= t} d_j / (n_j * (n_j - d_j))

The term at `n_j == d_j` -- every remaining subject fails at the same time -- has a zero
denominator. The variance there does not exist, and this is not a corner case to be
smoothed over: it happens on every dataset whose largest observation is an event, which
is most of them. Reporting 0.0 would claim perfect certainty at the exact point where the
data have run out. So `has_std_error[j]` is False from that row onward and the value slot
holds 0.0, which the JSON dispatch can serialise -- a raw infinity in that slot would
turn the entire response into a typed transport error.

Why the band is log-log rather than S +/- z*se
----------------------------------------------
A linear band on S runs outside [0, 1] whenever S is near either end, which is precisely
where survival curves spend their time. Clamping it hides the problem and makes the
coverage wrong asymmetrically. The log-log band

    [ S^exp(+z*se_ll), S^exp(-z*se_ll) ]   with  se_ll = sqrt(sigma2(t)) / |log S(t)|

is confined to (0, 1) by construction because it is a band on log(-log S), which is
unbounded in both directions. `se_ll` is undefined where `log S = 0` or `S = 0`, and both
are reported ABSENT rather than clamped. The linear band is one line for a caller who
wants it -- `survival[j] +/- z * std_error[j]` -- and `std_error` is published for exactly
that reason; the transformed band is the one this module takes responsibility for.

Two median conventions, both reported
-------------------------------------
The textbook median is `min{ t : S(t) <= 0.5 }`. The frozen `survival.median_survival`
implements `min{ t : S(t) < 0.5 }`, which is a DIFFERENT number whenever the curve lands
on exactly 0.5 -- and it lands there often, because a curve with an even number of
subjects and no censoring passes through 0.5 exactly. On `times = [1, 2, 3, 4]` with every
observation an event, S = (0.75, 0.5, 0.25, 0.0): the textbook median is 2 and the frozen
kernel returns 3.

Rather than pick one and bury the difference, both are returned: `median_time` under
`<= 0.5`, and `median_strict_time` computed by CALLING the frozen kernel. A caller
comparing this package's output against an existing report knows which convention it was
built with, and neither number is silently substituted for the other.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_survival_analysis_km.mojo
benchmark: benchmarks/mojo_benchmarks/bench_survival_analysis.mojo
docs: gitbook/engine/survival-analysis.md
version_introduced: 0.7.0
deprecation_state: active
@endcapability
"""
from std.math import exp, log, sqrt

from survival import SurvivalPoint, restricted_mean, survival_at_time
from survival import median_survival as frozen_median_survival

from survival_analysis.base import (
    SA_ERR_BAD_TAU,
    SA_ERR_QUERY_LENGTH,
    SA_ERR_WORK_BUDGET,
    SA_MAX_QUERY,
    SA_MAX_WORK,
    SA_OK,
    sa_greenwood_terms,
    sa_is_finite,
    sa_risk_table,
    sa_validate_confidence,
    sa_work_fits,
    sa_z_for_confidence,
)


struct KMFit(Copyable, Movable):
    """A Kaplan-Meier estimate with its uncertainty.

    Every list has `n_event_times` entries and index `j` refers to `time[j]` throughout.
    `has_std_error[j]` False means the Greenwood variance does not exist at that time, and
    `std_error[j]` is then 0.0 -- a placeholder, not a measurement. `has_band[j]` False
    means the transformed band does not exist there; `lower[j]` and `upper[j]` are then
    0.0 and 1.0, the trivial bound, which is true but carries no information.

    `status != SA_OK` means every list is empty. It never means "an estimate over zero
    event times".
    """

    var status: Int
    var n_obs: Int
    var n_events: Int
    var n_censored: Int
    var n_event_times: Int
    var conf_level: Float64
    var z: Float64
    var monotone: Bool
    var time: List[Float64]
    var survival: List[Float64]
    var at_risk: List[Int]
    var events: List[Int]
    var std_error: List[Float64]
    var has_std_error: List[Bool]
    var lower: List[Float64]
    var upper: List[Float64]
    var has_band: List[Bool]
    var median_time: Float64
    var has_median: Bool
    var median_strict_time: Float64
    var has_median_strict: Bool

    fn __init__(out self, status: Int):
        self.status = status
        self.n_obs = 0
        self.n_events = 0
        self.n_censored = 0
        self.n_event_times = 0
        self.conf_level = 0.0
        self.z = 0.0
        self.monotone = False
        self.time = List[Float64]()
        self.survival = List[Float64]()
        self.at_risk = List[Int]()
        self.events = List[Int]()
        self.std_error = List[Float64]()
        self.has_std_error = List[Bool]()
        self.lower = List[Float64]()
        self.upper = List[Float64]()
        self.has_band = List[Bool]()
        self.median_time = 0.0
        self.has_median = False
        self.median_strict_time = 0.0
        self.has_median_strict = False


fn _km_curve_points(time: List[Float64], survival: List[Float64], n_obs: Int) -> List[SurvivalPoint]:
    """Rebuild the frozen `List[SurvivalPoint]` shape, origin row included.

    The frozen `restricted_mean`, `survival_at_time` and `median_survival` all take that
    shape, and `restricted_mean` integrates from the origin, so the synthetic
    `(0, 1.0, n, 0)` row the frozen estimator emits has to be present or the area under
    the first step is lost. `at_risk` and `events` are not read by any of the three, so
    they are filled with the values that keep the row self-describing rather than
    recomputed.

    Returns an empty list on a length mismatch instead of indexing the shorter column.
    """
    var out = List[SurvivalPoint]()
    var k = len(time)
    if len(survival) != k:
        return out^
    out.append(SurvivalPoint(0.0, 1.0, n_obs, 0))
    for j in range(k):
        out.append(SurvivalPoint(time[j], survival[j], 0, 1))
    return out^


fn km_fit(times: List[Float64], event: List[Int], conf_level: Float64) -> KMFit:
    """Kaplan-Meier estimate with Greenwood standard errors and a log-log band.

    `event[i]` is 1 for an observed event at `times[i]` and 0 for a right-censored
    observation. `len(event) == len(times)` is required exactly and refused with
    `SA_ERR_CENSOR_LENGTH` otherwise: that relation is list-to-list, which the `counts:`
    grammar deliberately does not express, so it is validated in the kernel and stated
    here for greppability as `len(event) == len(times)`.

    `conf_level` is a two-sided level in [0.5, 0.999999]; outside that it is
    `SA_ERR_BAD_CONFIDENCE` rather than a band of width 1e300 (see
    `base.sa_validate_confidence`).

    The Greenwood sum is a running total of strictly positive terms, so it is accumulated
    directly rather than through the frozen `numerical_stability.kahan_sum`: a compensated
    PREFIX sum would mean re-summing the prefix at every event time, turning an O(k)
    accumulation into O(k^2) for an error term that cancellation cannot reach when every
    addend has the same sign.

    @capability km_fit
    complexity: O(n log n)
    counts: none
    @endcapability
    """
    var conf_status = sa_validate_confidence(conf_level)
    if conf_status != SA_OK:
        return KMFit(conf_status)

    var table = sa_risk_table(times, event)
    if table.status != SA_OK:
        return KMFit(table.status)

    var out = KMFit(SA_OK)
    out.n_obs = table.n_obs
    out.n_events = table.n_events
    out.n_censored = table.n_censored
    out.n_event_times = table.n_event_times
    out.conf_level = conf_level
    out.monotone = table.monotone
    var z = sa_z_for_confidence(conf_level)
    out.z = z

    var terms = sa_greenwood_terms(table.at_risk, table.events)
    var running: Float64 = 0.0
    var variance_defined = True

    for j in range(table.n_event_times):
        var s = table.survival[j]
        out.time.append(table.time[j])
        out.survival.append(s)
        out.at_risk.append(table.at_risk[j])
        out.events.append(table.events[j])

        if terms[j] < 0.0:
            # n_j == d_j: the Greenwood term is 1/0. The variance does not exist at this
            # time nor at any later one, because every later sum contains this term.
            variance_defined = False
        else:
            running += terms[j]

        var se: Float64 = 0.0
        var has_se = False
        if variance_defined:
            var v = s * s * running
            if sa_is_finite(v) and v >= 0.0:
                se = sqrt(v)
                has_se = sa_is_finite(se)
        out.std_error.append(se if has_se else 0.0)
        out.has_std_error.append(has_se)

        var lo: Float64 = 0.0
        var hi: Float64 = 1.0
        var has_band = False
        if has_se and s > 0.0 and s < 1.0 and running > 0.0:
            var log_s = log(s)
            var se_ll = sqrt(running) / (-log_s)
            var spread = z * se_ll
            if sa_is_finite(spread):
                var cand_lo = _pow_survival(s, exp(spread))
                var cand_hi = _pow_survival(s, exp(-spread))
                if sa_is_finite(cand_lo) and sa_is_finite(cand_hi) and cand_lo <= cand_hi:
                    lo = cand_lo
                    hi = cand_hi
                    has_band = True
        out.lower.append(lo)
        out.upper.append(hi)
        out.has_band.append(has_band)

    for j in range(table.n_event_times):
        if table.survival[j] <= 0.5:
            out.median_time = table.time[j]
            out.has_median = True
            break

    var points = _km_curve_points(table.time, table.survival, table.n_obs)
    var strict = frozen_median_survival(points)
    if strict >= 0.0:
        out.median_strict_time = strict
        out.has_median_strict = True

    return out^


fn _pow_survival(s: Float64, power: Float64) -> Float64:
    """`s ** power` for `s` in (0, 1), via exp/log so a huge power underflows to 0.

    `std.math.pow` is fine here too; exp(power * log s) is used because `log s` is already
    the quantity the band is built from, and because a `power` large enough to underflow
    gives exactly 0.0 -- the correct limit for a band on a curve that has reached the end
    of its information.
    """
    if s <= 0.0:
        return 0.0
    if s >= 1.0:
        return 1.0
    var v = exp(power * log(s))
    if not sa_is_finite(v):
        return 0.0
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


struct KMRmst(Copyable, Movable):
    """Restricted mean survival time up to `tau`, or a refusal."""

    var status: Int
    var tau: Float64
    var rmst: Float64
    var has_rmst: Bool
    var n_obs: Int
    var n_events: Int
    var max_observed_time: Float64

    fn __init__(out self, status: Int):
        self.status = status
        self.tau = 0.0
        self.rmst = 0.0
        self.has_rmst = False
        self.n_obs = 0
        self.n_events = 0
        self.max_observed_time = 0.0


fn km_rmst(times: List[Float64], event: List[Int], tau: Float64) -> KMRmst:
    """Area under the Kaplan-Meier curve on [0, tau], via the frozen `restricted_mean`.

    `tau` must be finite, strictly positive and no greater than the largest observed
    time. The upper limit is the honest one: past the last observation the step function
    is a continuation of the last known level, not an estimate, so integrating beyond it
    manufactures area from nothing. `SA_ERR_BAD_TAU` names that rather than returning a
    plausible larger number.

    @capability km_rmst
    complexity: O(n log n)
    counts: none
    @endcapability
    """
    var table = sa_risk_table(times, event)
    if table.status != SA_OK:
        return KMRmst(table.status)

    var max_time: Float64 = 0.0
    for i in range(len(times)):
        if times[i] > max_time:
            max_time = times[i]

    var out = KMRmst(SA_OK)
    out.n_obs = table.n_obs
    out.n_events = table.n_events
    out.max_observed_time = max_time
    out.tau = tau

    if not sa_is_finite(tau) or tau <= 0.0 or tau > max_time:
        out.status = SA_ERR_BAD_TAU
        return out^

    var points = _km_curve_points(table.time, table.survival, table.n_obs)
    var area = restricted_mean(points, tau)
    if not sa_is_finite(area) or area < 0.0:
        out.status = SA_ERR_BAD_TAU
        return out^
    out.rmst = area
    out.has_rmst = True
    return out^


struct KMLookup(Copyable, Movable):
    """`S(t)` for each requested `t`, aligned with the request order.

    `has_value[q]` is False where the curve does not answer: a negative or non-finite query,
    and any query PAST `max_observed_time`. `survival[q]` is then 0.0, a placeholder.
    """

    var status: Int
    var n_queries: Int
    var max_observed_time: Float64
    var n_beyond_support: Int
    var query_time: List[Float64]
    var survival: List[Float64]
    var has_value: List[Bool]

    fn __init__(out self, status: Int):
        self.status = status
        self.n_queries = 0
        self.max_observed_time = 0.0
        self.n_beyond_support = 0
        self.query_time = List[Float64]()
        self.survival = List[Float64]()
        self.has_value = List[Bool]()


fn km_survival_at(times: List[Float64], event: List[Int], query: List[Float64]) -> KMLookup:
    """Step-function lookup of `S(t)` at each `query[q]`, via the frozen `survival_at_time`.

    Two bounds, because they are two different things. Memory is bounded by
    `len(query) <= SA_MAX_QUERY`. WORK is not: the frozen lookup is a linear scan of the
    curve, so the cost is `len(query) * n_event_times`, and both factors can independently
    sit at 2^20 -- a structurally valid request for 2^40 comparisons that would return
    eventually, in about a fortnight. `sa_work_fits` charges the product against
    `SA_MAX_WORK` by division and refuses with `SA_ERR_WORK_BUDGET`.

    A query at a negative or non-finite time has no answer and is reported absent, with
    0.0 in the value slot; it does not fail the whole request, because one bad row in a
    lookup batch is not a reason to discard the other 2^20 answers.

    A query PAST the largest observed time is also absent, for the reason `km_rmst` refuses
    a `tau` past it: beyond the last observation the step function is a continuation of the
    last known level, not an estimate. Nobody was still under observation there, so the
    curve carries no information about it -- `S(1e300) = 0.25` on a sample whose largest
    observation is 10 is a manufactured answer, and it was being published with
    `has_value = true`. This is also what `survfit` reports in R: NA past the last
    follow-up time, not the last level carried forward. `max_observed_time` and
    `n_beyond_support` are returned so a caller can see how much of a batch fell outside.

    @capability km_survival_at
    complexity: O(n log n + q * k)
    counts: none
    @endcapability
    """
    var table = sa_risk_table(times, event)
    if table.status != SA_OK:
        return KMLookup(table.status)

    var n_q = len(query)
    if n_q > SA_MAX_QUERY:
        return KMLookup(SA_ERR_QUERY_LENGTH)

    var factors = List[Int]()
    factors.append(n_q)
    factors.append(table.n_event_times + 1)
    if not sa_work_fits(factors, SA_MAX_WORK):
        return KMLookup(SA_ERR_WORK_BUDGET)

    # The support is every observed time, censored ones included: a subject censored at 10 was
    # under observation up to 10, so the curve is defined there even though it does not step.
    var max_time: Float64 = 0.0
    for i in range(len(times)):
        if times[i] > max_time:
            max_time = times[i]

    var points = _km_curve_points(table.time, table.survival, table.n_obs)
    var out = KMLookup(SA_OK)
    out.n_queries = n_q
    out.max_observed_time = max_time
    for q in range(n_q):
        var t = query[q]
        out.query_time.append(t if sa_is_finite(t) else 0.0)
        if not sa_is_finite(t) or t < 0.0:
            out.survival.append(0.0)
            out.has_value.append(False)
            continue
        if t > max_time:
            out.survival.append(0.0)
            out.has_value.append(False)
            out.n_beyond_support += 1
            continue
        var s = survival_at_time(points, t)
        if not sa_is_finite(s) or s < 0.0 or s > 1.0:
            out.survival.append(0.0)
            out.has_value.append(False)
            continue
        out.survival.append(s)
        out.has_value.append(True)
    return out^
