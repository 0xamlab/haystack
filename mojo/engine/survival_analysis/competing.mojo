"""
survival_analysis.competing — competing risks: Aalen-Johansen cumulative incidence.

The mistake this module exists to prevent
-----------------------------------------
With more than one cause of failure, `1 - S_k(t)` from a Kaplan-Meier estimate that treats
the other causes as CENSORED is not the probability of failing from cause k by time t. It
is the probability in a hypothetical world where the other causes do not exist, and it is
biased upward -- often severely, because the other causes remove subjects who would
otherwise have been available to fail from cause k. The quantity a reader almost always
wants is the cumulative incidence function

    CIF_k(t) = sum_{t_j <= t} S(t_{j-1}) * d_kj / n_j

where `S` is the ALL-CAUSE Kaplan-Meier estimate and `d_kj` counts only the cause-k events
at `t_j`. This is the Aalen-Johansen estimator for a competing-risks model.

Nothing in the frozen tree computes it, and the frozen `survival.kaplan_meier` cannot be
asked for it: it takes `List[Bool]`, so a cause code has nowhere to go and the only way to
express three causes is three separate calls that each silently make the wrong assumption.
That is what makes the API shape here load-bearing rather than cosmetic -- `cause` is a
`List[Int]` whose codes are validated, so "0 means censored, k means cause k" cannot be
mistaken for "1 means the event I care about".

The frozen estimator is still the one that computes `S`: the all-cause indicator is derived
from the cause codes and handed to `base.sa_risk_table`, whose survival column is the frozen
`kaplan_meier` output. The composition is the new part.

The partition identity is checked, not assumed
----------------------------------------------
    S(t) + sum_k CIF_k(t) = 1     at every event time

This is exact algebra, not an approximation: each event time adds `S(t_{j-1}) d_j / n_j`
to the incidence total and subtracts exactly the same amount from `S`, and the induction
starts at `S = 1`, `CIF = 0`. So a violation is an indexing or accumulation defect, and the
residual is reported (`partition_max_error`) and enforced (`SA_ERR_PARTITION`). The
tolerance is `8 * n_event_times * DBL_EPSILON`: the quantity judged has magnitude 1 and is
built from one rounding per row, so its own error budget grows with the number of rows --
that is this quantity's accumulated error, not an aggregate borrowed from other items.

Ties across causes
------------------
Two failures at the same time from DIFFERENT causes share one at-risk denominator `n_j` and
each contributes to its own cause's increment. That is handled explicitly: the tie group at
`t_j` is scanned once, `d_j` is the total and `d_kj` the per-cause split, and the single
`S(t_{j-1})` factor is applied to each. Treating them as two successive times would use
`n_j` for one and `n_j - 1` for the other and break the partition identity -- which is how
the check earns its cost.

What is deliberately NOT here
-----------------------------
No confidence band for the incidence. The delta-method variance of an Aalen-Johansen
estimate has three interacting terms and no closed form this package can verify against a
hand-derived value or a named reference, and a plausible-looking interval that is wrong is
worse than a stated absence. What IS provided with uncertainty is the CAUSE-SPECIFIC
cumulative hazard, `H_k(t) = sum d_kj / n_j`, with the same Aalen variance
`sum d_kj / n_j^2` the `hazard` module uses -- that one is a sum of independent increments
and both the estimator and its variance are hand-checkable.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_survival_analysis_competing.mojo
benchmark: benchmarks/mojo_benchmarks/bench_survival_analysis.mojo
docs: gitbook/engine/survival-analysis.md
version_introduced: 0.7.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs
from std.math import sqrt

from survival_analysis.base import (
    SA_DBL_EPSILON,
    SA_ERR_BAD_CAUSE_CODE,
    SA_ERR_BAD_CAUSE_SELECTION,
    SA_ERR_CENSOR_LENGTH,
    SA_ERR_NON_MONOTONE,
    SA_ERR_NO_EVENTS,
    SA_ERR_PARTITION,
    SA_ERR_QUERY_LENGTH,
    SA_ERR_TOO_MANY_CAUSES,
    SA_ERR_WORK_BUDGET,
    SA_MAX_CIF_CELLS,
    SA_MAX_QUERY,
    SA_OK,
    sa_is_finite,
    sa_risk_table,
    sa_validate_observations,
    sa_work_fits,
)

# The cause ceiling. Declared HERE, as a literal, rather than imported from `base`: the
# capability gate resolves a `dim x <= NAME` ceiling only against a
# `comptime NAME: Int = <literal>` in the same file, so an imported name left the four
# declarations below unresolvable — a stated ceiling nothing could check. 64 causes is
# already far past any real competing-risks study; the product `n_causes * n_event_times`
# is what actually bounds memory and it is charged separately against `SA_MAX_CIF_CELLS`.
comptime CIF_MAX_CAUSES: Int = 64


fn cif_validate_causes(times: List[Float64], cause: List[Int], n_causes: Int) -> Int:
    """Validate a competing-risks sample: times, alignment, and cause codes in [0, n_causes].

    `cause[i] == 0` is a right-censored observation; `1 <= cause[i] <= n_causes` is an event
    from that cause. Anything else is `SA_ERR_BAD_CAUSE_CODE` -- including a code ABOVE
    `n_causes`, which is the realistic mistake: a status column recorded as 1/2/3 passed with
    `n_causes = 2` would otherwise drop every cause-3 failure into nothing at all, shrinking
    the risk set correctly and the incidence silently wrongly.

    The length check runs FIRST and independently of `base.sa_validate_observations`, because
    deriving the all-cause indicator from `cause` reads `cause[i]` for every `i` in `times`
    and a short `cause` would abort the process before any validator saw it.

    @capability cif_validate_causes
    complexity: O(n)
    counts:
    - dim n_causes <= CIF_MAX_CAUSES [kernel_validated]
    @endcapability
    """
    if n_causes < 1:
        return SA_ERR_BAD_CAUSE_CODE
    if n_causes > CIF_MAX_CAUSES:
        return SA_ERR_TOO_MANY_CAUSES
    if len(cause) != len(times):
        return SA_ERR_CENSOR_LENGTH
    var event = List[Int]()
    for i in range(len(cause)):
        var c = cause[i]
        if c < 0 or c > n_causes:
            return SA_ERR_BAD_CAUSE_CODE
        event.append(1 if c > 0 else 0)
    return sa_validate_observations(times, event)


struct CIFFit(Copyable, Movable):
    """Aalen-Johansen cumulative incidence for every declared cause.

    Per-cause columns are flattened row-major BY CAUSE: the value for cause `k` (1-based) at
    event time index `j` is at `(k - 1) * n_event_times + j`. `n_causes` and `n_event_times`
    are both returned so the caller never has to infer the stride.

    `partition_holds` is the algebraic law `S + sum_k CIF_k == 1` at every event time.
    `monotone` is `CIF_k` non-decreasing in `j` for every cause and the all-cause survival
    non-increasing. Both are checked; a False in either with `status == SA_OK` cannot happen
    because the status is set from them.
    """

    var status: Int
    var n_obs: Int
    var n_events: Int
    var n_censored: Int
    var n_causes: Int
    var n_event_times: Int
    var monotone: Bool
    var partition_holds: Bool
    var partition_max_error: Float64
    var time: List[Float64]
    var at_risk: List[Int]
    var events_total: List[Int]
    var overall_survival: List[Float64]
    var cause_events: List[Int]
    var incidence: List[Float64]
    var cause_cum_hazard: List[Float64]
    var cause_cum_hazard_se: List[Float64]
    var cause_event_count: List[Int]

    fn __init__(out self, status: Int):
        self.status = status
        self.n_obs = 0
        self.n_events = 0
        self.n_censored = 0
        self.n_causes = 0
        self.n_event_times = 0
        self.monotone = False
        self.partition_holds = False
        self.partition_max_error = 0.0
        self.time = List[Float64]()
        self.at_risk = List[Int]()
        self.events_total = List[Int]()
        self.overall_survival = List[Float64]()
        self.cause_events = List[Int]()
        self.incidence = List[Float64]()
        self.cause_cum_hazard = List[Float64]()
        self.cause_cum_hazard_se = List[Float64]()
        self.cause_event_count = List[Int]()


fn cif_fit(times: List[Float64], cause: List[Int], n_causes: Int) -> CIFFit:
    """Cumulative incidence per cause, plus the all-cause survival it is built from.

    `cause[i]` is 0 for right-censored and `k` in `1..n_causes` for a cause-k failure.

    Memory is bounded by the PRODUCT `n_causes * n_event_times`, not by `n_causes` alone:
    four per-cause columns at the individual ceilings would be 2^26 cells and eight times
    the single-object budget, so the product is charged against `SA_MAX_CIF_CELLS` by
    division and refused with `SA_ERR_WORK_BUDGET`.

    @capability cif_fit
    complexity: O(n log n + n_causes * n_event_times)
    counts:
    - dim n_causes <= CIF_MAX_CAUSES [kernel_validated]
    @endcapability
    """
    var status = cif_validate_causes(times, cause, n_causes)
    if status != SA_OK:
        return CIFFit(status)

    var n = len(times)
    var event = List[Int]()
    var per_cause_total = List[Int]()
    for _k in range(n_causes):
        per_cause_total.append(0)
    for i in range(n):
        var c = cause[i]
        event.append(1 if c > 0 else 0)
        if c > 0:
            per_cause_total[c - 1] += 1

    var table = sa_risk_table(times, event)
    if table.status != SA_OK:
        return CIFFit(table.status)
    if table.n_events == 0:
        return CIFFit(SA_ERR_NO_EVENTS)

    var k_rows = table.n_event_times
    var cells = List[Int]()
    cells.append(n_causes)
    cells.append(k_rows)
    if not sa_work_fits(cells, SA_MAX_CIF_CELLS):
        return CIFFit(SA_ERR_WORK_BUDGET)

    # Per-cause event counts at each distinct event time. A linear scan of the rows per
    # observation would be O(n * k_rows) -- 2^40 comparisons at the ceilings, memory-bounded
    # and work-unbounded, which is the trap rule 1c names. The row index is found by BINARY
    # SEARCH on the ascending `table.time`, so the placement is O(n log k_rows).
    var cause_events = List[Int]()
    for _c in range(n_causes * k_rows):
        cause_events.append(0)

    var order_ok = True
    for i in range(n):
        var c = cause[i]
        if c <= 0:
            continue
        var t = times[i]
        var found = -1
        var lo = 0
        var hi = k_rows - 1
        while lo <= hi:
            var mid = lo + (hi - lo) // 2
            var mt = table.time[mid]
            if mt == t:
                found = mid
                break
            if mt < t:
                lo = mid + 1
            else:
                hi = mid - 1
        if found < 0:
            order_ok = False
            break
        cause_events[(c - 1) * k_rows + found] += 1
    if not order_ok:
        return CIFFit(SA_ERR_BAD_CAUSE_SELECTION)

    var out = CIFFit(SA_OK)
    out.n_obs = table.n_obs
    out.n_events = table.n_events
    out.n_censored = table.n_censored
    out.n_causes = n_causes
    out.n_event_times = k_rows
    out.time = table.time.copy()
    out.at_risk = table.at_risk.copy()
    out.events_total = table.events.copy()
    out.overall_survival = table.survival.copy()
    out.cause_events = cause_events.copy()
    out.cause_event_count = per_cause_total.copy()

    for _c in range(n_causes * k_rows):
        out.incidence.append(0.0)
        out.cause_cum_hazard.append(0.0)
        out.cause_cum_hazard_se.append(0.0)

    var monotone = True
    for c in range(n_causes):
        var cif: Float64 = 0.0
        var cum_h: Float64 = 0.0
        var var_h: Float64 = 0.0
        var s_prev: Float64 = 1.0
        for j in range(k_rows):
            var nj = Float64(table.at_risk[j])
            var dkj = Float64(cause_events[c * k_rows + j])
            if nj > 0.0 and dkj > 0.0:
                cif += s_prev * dkj / nj
                cum_h += dkj / nj
                var_h += dkj / (nj * nj)
            if not sa_is_finite(cif) or cif < 0.0 or cif > 1.0 + SA_DBL_EPSILON:
                monotone = False
                cif = 0.0
            out.incidence[c * k_rows + j] = cif
            out.cause_cum_hazard[c * k_rows + j] = cum_h if sa_is_finite(cum_h) else 0.0
            var se = sqrt(var_h) if var_h > 0.0 else 0.0
            out.cause_cum_hazard_se[c * k_rows + j] = se if sa_is_finite(se) else 0.0
            s_prev = table.survival[j]

    for c in range(n_causes):
        for j in range(1, k_rows):
            if out.incidence[c * k_rows + j] + SA_DBL_EPSILON < out.incidence[c * k_rows + j - 1]:
                monotone = False
    out.monotone = monotone and table.monotone
    if not out.monotone:
        out.status = SA_ERR_NON_MONOTONE
        return out^

    # The partition identity. Its own error budget is one rounding per row, so the tolerance
    # grows with the number of rows and with nothing else.
    var tol = 8.0 * Float64(k_rows if k_rows > 1 else 1) * SA_DBL_EPSILON
    var worst: Float64 = 0.0
    for j in range(k_rows):
        var total = table.survival[j]
        for c in range(n_causes):
            total += out.incidence[c * k_rows + j]
        var err = fabs(total - 1.0)
        if err > worst:
            worst = err
    out.partition_max_error = worst if sa_is_finite(worst) else 1.0
    out.partition_holds = out.partition_max_error <= tol
    if not out.partition_holds:
        out.status = SA_ERR_PARTITION
    return out^


struct CIFAtTime(Copyable, Movable):
    """Cumulative incidence for ONE cause, looked up at each requested time.

    `has_value[q]` is False for a negative or non-finite query and for any query past
    `max_observed_time`; `incidence[q]` is then 0.0, a placeholder and not an incidence.
    """

    var status: Int
    var cause: Int
    var n_queries: Int
    var max_observed_time: Float64
    var n_beyond_support: Int
    var query_time: List[Float64]
    var incidence: List[Float64]
    var has_value: List[Bool]

    fn __init__(out self, status: Int):
        self.status = status
        self.cause = 0
        self.n_queries = 0
        self.max_observed_time = 0.0
        self.n_beyond_support = 0
        self.query_time = List[Float64]()
        self.incidence = List[Float64]()
        self.has_value = List[Bool]()


fn cif_at_time(
    times: List[Float64], cause: List[Int], n_causes: Int, selected: Int, query: List[Float64]
) -> CIFAtTime:
    """Step-function lookup of `CIF_selected(t)` at each `query[q]`.

    A cumulative incidence is right-continuous and constant between event times, so the
    answer at `t` is the value at the largest event time `<= t`, and 0.0 before the first
    event time -- a real answer there, not an absence: nobody has failed yet.

    A query at a negative or non-finite time has no answer and is reported absent. So is a
    query PAST the largest observed time: past the last observation the step function is a
    continuation of the last known level and not an estimate, which is the same rule
    `km_rmst` enforces on `tau` and the same rule `km_survival_at` follows. Publishing
    `CIF(1e300) = 0.5` from a sample that ends at 10, with `has_value = true`, was
    extrapolation reported as measurement.

    `selected` must name a declared cause (`1..n_causes`), otherwise
    `SA_ERR_BAD_CAUSE_SELECTION`.

    @capability cif_at_time
    complexity: O(n log n + q * log k)
    counts:
    - dim n_causes <= CIF_MAX_CAUSES [kernel_validated]
    - dim selected <= CIF_MAX_CAUSES [kernel_validated]
    @endcapability
    """
    if len(query) > SA_MAX_QUERY:
        return CIFAtTime(SA_ERR_QUERY_LENGTH)
    var fit = cif_fit(times, cause, n_causes)
    if fit.status != SA_OK:
        return CIFAtTime(fit.status)
    if selected < 1 or selected > fit.n_causes:
        return CIFAtTime(SA_ERR_BAD_CAUSE_SELECTION)

    var k_rows = fit.n_event_times
    var base = (selected - 1) * k_rows
    var out = CIFAtTime(SA_OK)
    out.cause = selected
    out.n_queries = len(query)
    # Every observed time, censored ones included: a subject censored at 10 was under
    # observation up to 10, so the estimate is defined there even though it does not step.
    var max_time: Float64 = 0.0
    for i in range(len(times)):
        if times[i] > max_time:
            max_time = times[i]
    out.max_observed_time = max_time
    for q in range(len(query)):
        var t = query[q]
        out.query_time.append(t if sa_is_finite(t) else 0.0)
        if not sa_is_finite(t) or t < 0.0:
            out.incidence.append(0.0)
            out.has_value.append(False)
            continue
        if t > max_time:
            out.incidence.append(0.0)
            out.has_value.append(False)
            out.n_beyond_support += 1
            continue
        var value: Float64 = 0.0
        var lo = 0
        var hi = k_rows - 1
        while lo <= hi:
            var mid = lo + (hi - lo) // 2
            if fit.time[mid] <= t:
                value = fit.incidence[base + mid]
                lo = mid + 1
            else:
                hi = mid - 1
        out.incidence.append(value)
        out.has_value.append(True)
    return out^
