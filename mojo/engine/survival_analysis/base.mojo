"""
survival_analysis.base — the censoring contract, the guards and the risk table.

Why this module exists
----------------------
The frozen `survival.mojo` already estimates a Kaplan-Meier curve and a Nelson-Aalen
cumulative hazard. It is correct arithmetic on well-formed input, and it has no input
validation at all. Two measured consequences, both reachable from the SDK:

1. `kaplan_meier(times, events)` indexes `events[idx[i]]` for every `i < len(times)`.
   Passing 5 times and 1 indicator aborts the process:

       Assert Error: index 1 is out of bounds, valid range is 0 to 0
       mojo: error: execution crashed

   That is the uncatchable bounds assertion: no `try`/`except` anywhere above it helps,
   and inside a worker it takes every resident dataset with it.

2. A NaN time makes it loop FOREVER. The grouping loop is
   `while i < n and times[idx[i]] == t`, and `NaN == NaN` is False, so `i` never
   advances and the outer `while i < n` re-enters with identical state. Measured: the
   call printed its entry line and had still not returned after 45 s of wall clock.

Neither is a defect in the arithmetic, and neither is fixable inside a frozen file. So
this package's first job is to be the only door: every public entry point in
`survival_analysis` validates through `sa_validate_observations` before any frozen
kernel sees the data, and the frozen kernels are then called on input that provably
cannot trigger either failure.

The censoring contract
----------------------
`len(event) == len(times)`, EXACTLY, is a hard refusal — not `>=`, not "extra ignored".
Right-censoring is the whole subject of survival analysis: a censored row is neither a
death nor a survivor, it is a partial observation, and it changes both the at-risk
denominator and the estimator. An API that accepted a short indicator list would abort;
an API that accepted a long one would silently drop the tail and return a curve for a
DIFFERENT dataset than the caller described. Both are refused here with
`SA_ERR_CENSOR_LENGTH`, so a caller cannot pass censoring information that is quietly
not used.

`event` is `List[Int]` rather than `List[Bool]` for the same reason. A `Bool` has no
invalid value, so a caller who encodes their status column as 1/2 (a common convention
where 2 means "competing cause") gets silent misclassification. An `Int` code outside
{0, 1} is refused with `SA_ERR_BAD_EVENT_CODE`, and the competing-risks module takes a
wider code set explicitly.

Ties
----
The convention throughout this package is that all observations sharing a time value
form ONE tie group at one at-risk denominator, and censored observations at time t are
treated as remaining at risk AT t and leaving immediately after (Efron/standard
convention). So d_j / n_j uses n_j = #{i : t_i >= t_j}, and a censoring at exactly an
event time still contributes to that denominator. The frozen `kaplan_meier` already
does this; `sa_risk_table` publishes the (n_j, d_j) table it used so that every derived
quantity in this package — Greenwood variance, Nelson-Aalen, cumulative incidence — is
built from the SAME risk sets as the survival curve rather than a second recount that
could disagree.

Sorting is O(n log n), not the frozen insertion sort
----------------------------------------------------
`survival._sort_indices` is an insertion sort, so `kaplan_meier` is O(n^2) on unsorted
input. This module orders first with the frozen `causal_inference.base.ci_argsort_asc` --
a stable, iterative, O(n log n) merge sort over indices that already refuses a non-finite
key -- and hands the frozen estimator an already-ascending array, on which its insertion
sort degrades to a single O(n) pass. The arithmetic still belongs to the frozen kernel;
only the order of the rows changed, and row order cannot change a Kaplan-Meier estimate.

No new sort was written. `ci_argsort_asc` is the only kernel in the tree that returns a
PERMUTATION -- `sorting.mojo` and `stats.fast_sort` sort values and return no index map,
and `survival._sort_indices` is private and quadratic -- and the permutation is exactly
what `cox` needs in order to carry a covariate row alongside its time.

Status codes
------------
This package owns 900-949. `SA_OK` is 0, shared with every other package, because 0
means "nothing to report" everywhere. Codes are per-defect rather than one "invalid",
because a caller who is told "invalid" has to inspect every argument.

Resource ceilings, and the arithmetic behind them
-------------------------------------------------
`SA_MAX_OBS = 1 << 20`. `sa_risk_table` allocates, per observation: a sorted time
(8 B), a flag (1 B), one frozen `SurvivalPoint` (32 B) and four output columns
(8 B each) -- about 105 B, so the ceiling costs ~110 MB, inside the 512 MiB
single-object budget that `sparse_numerics.csr` fixes as the outer limit. Bounding
memory is not bounding work, so `sa_work_fits` exists separately and the modules that
run an iterative fit charge every factor of their loop nest against it.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_survival_analysis_base.mojo
benchmark: benchmarks/mojo_benchmarks/bench_survival_analysis.mojo
docs: gitbook/engine/survival-analysis.md
version_introduced: 0.7.0
deprecation_state: active
@endcapability
"""
from std.math import sqrt

from causal_inference.base import ci_argsort_asc, ci_is_permutation
from math_ext import norm_ppf
from numeric.reduce import is_finite_value
from survival import SurvivalPoint, kaplan_meier

# ── status codes: this package owns 900-949 ───────────────────────────────────

comptime SA_OK: Int = 0
comptime SA_ERR_EMPTY: Int = 900
comptime SA_ERR_CENSOR_LENGTH: Int = 901
comptime SA_ERR_TOO_MANY_OBS: Int = 902
comptime SA_ERR_NON_FINITE_TIME: Int = 903
comptime SA_ERR_NEGATIVE_TIME: Int = 904
comptime SA_ERR_BAD_EVENT_CODE: Int = 905
comptime SA_ERR_NO_EVENTS: Int = 906
comptime SA_ERR_BAD_CONFIDENCE: Int = 907
comptime SA_ERR_NON_MONOTONE: Int = 908
comptime SA_ERR_BAD_TAU: Int = 909
comptime SA_ERR_SHAPE: Int = 910
comptime SA_ERR_TOO_MANY_COVARIATES: Int = 911
comptime SA_ERR_NON_FINITE_COVARIATE: Int = 912
comptime SA_ERR_NO_COVARIATE_VARIATION: Int = 913
comptime SA_ERR_SINGULAR_INFORMATION: Int = 914
comptime SA_ERR_NOT_CONVERGED: Int = 915
comptime SA_ERR_SEPARATION: Int = 916
comptime SA_ERR_BAD_ITER: Int = 917
comptime SA_ERR_BAD_TOL: Int = 918
comptime SA_ERR_BAD_CAUSE_CODE: Int = 919
comptime SA_ERR_BAD_CAUSE_SELECTION: Int = 920
comptime SA_ERR_NONPOSITIVE_TIME: Int = 921
comptime SA_ERR_BAD_GRID: Int = 922
comptime SA_ERR_BAD_AGE: Int = 923
comptime SA_ERR_BAD_QUANTILE: Int = 924
comptime SA_ERR_WORK_BUDGET: Int = 925
comptime SA_ERR_QUERY_LENGTH: Int = 926
comptime SA_ERR_TOO_MANY_CAUSES: Int = 927
comptime SA_ERR_BAD_HORIZON: Int = 928
comptime SA_ERR_BAD_SHAPE_PARAM: Int = 929
comptime SA_ERR_PARTITION: Int = 930
comptime SA_ERR_LIKELIHOOD_UNBOUNDED: Int = 931
comptime SA_ERR_EM_NOT_MONOTONE: Int = 932

# ── ceilings ──────────────────────────────────────────────────────────────────

comptime SA_MAX_OBS: Int = 1 << 20
comptime SA_MAX_COVARIATES: Int = 64
comptime SA_MAX_GRID: Int = 1 << 16
comptime SA_MAX_QUERY: Int = 1 << 20
# The cause ceiling lives in `competing.mojo` as `CIF_MAX_CAUSES` and the iteration ceiling
# in `cox.mojo` / `parametric.mojo` as `COX_MAX_ITER` / `PAR_MAX_ITER`, not here. The
# capability gate requires a declared `dim x <= NAME` ceiling to resolve to a
# `comptime NAME: Int = <literal>` in the SAME file as the declaration, so that the number
# in the block cannot drift from the number the kernel compares against; a constant imported
# from here is unresolvable there and the ceiling was silently unchecked. The package still
# presents ONE iteration ceiling: `test_survival_analysis_cox.mojo` asserts
# `COX_MAX_ITER == PAR_MAX_ITER`, which is the drift gate that assertion exists to be.
# A competing-risks fit materialises FOUR `n_causes * n_event_times` columns (incidence,
# per-cause counts, per-cause cumulative hazard, its standard error). 2^22 cells is
# 4 * 4.2M * 8 B = 134 MB. `n_causes <= CIF_MAX_CAUSES` alone would allow 64 * 2^20 = 2^26
# cells and eight times the single-object budget, which is rule 1c exactly: a per-dimension
# ceiling is not a bound on the product.
comptime SA_MAX_CIF_CELLS: Int = 1 << 22
# One elementary floating-point operation per unit. 2^30 multiply-adds is ~1 s of
# single-threaded Mojo on this hardware, which is the outer limit for one synchronous
# library_execute call.
comptime SA_MAX_WORK: Int = 1 << 30

# The relative slop a survival probability is allowed when its own monotonicity is
# judged. DBL_EPSILON times the magnitude of THAT probability -- not of the curve's
# maximum, not of a sum over the curve, and not the caller's tolerance. A survival
# probability is in [0, 1], so the absolute floor is DBL_EPSILON itself.
comptime SA_DBL_EPSILON: Float64 = 2.220446049250313e-16


fn sa_status_name(code: Int) -> String:
    """Human-readable name for a `survival_analysis` status code.

    @capability sa_status_name
    complexity: O(1)
    counts: none
    @endcapability
    """
    if code == SA_OK:
        return String("ok")
    if code == SA_ERR_EMPTY:
        return String("empty_observations")
    if code == SA_ERR_CENSOR_LENGTH:
        return String("censoring_length_mismatch")
    if code == SA_ERR_TOO_MANY_OBS:
        return String("too_many_observations")
    if code == SA_ERR_NON_FINITE_TIME:
        return String("non_finite_time")
    if code == SA_ERR_NEGATIVE_TIME:
        return String("negative_time")
    if code == SA_ERR_BAD_EVENT_CODE:
        return String("event_code_not_zero_or_one")
    if code == SA_ERR_NO_EVENTS:
        return String("no_events_observed")
    if code == SA_ERR_BAD_CONFIDENCE:
        return String("confidence_level_out_of_range")
    if code == SA_ERR_NON_MONOTONE:
        return String("survival_curve_not_monotone")
    if code == SA_ERR_BAD_TAU:
        return String("truncation_time_out_of_range")
    if code == SA_ERR_SHAPE:
        return String("covariate_shape_mismatch")
    if code == SA_ERR_TOO_MANY_COVARIATES:
        return String("too_many_covariates")
    if code == SA_ERR_NON_FINITE_COVARIATE:
        return String("non_finite_covariate")
    if code == SA_ERR_NO_COVARIATE_VARIATION:
        return String("covariate_is_constant")
    if code == SA_ERR_SINGULAR_INFORMATION:
        return String("information_matrix_not_positive_definite")
    if code == SA_ERR_NOT_CONVERGED:
        return String("not_converged")
    if code == SA_ERR_SEPARATION:
        return String("likelihood_flat_or_separating")
    if code == SA_ERR_BAD_ITER:
        return String("iteration_limit_out_of_range")
    if code == SA_ERR_BAD_TOL:
        return String("tolerance_out_of_range")
    if code == SA_ERR_BAD_CAUSE_CODE:
        return String("cause_code_out_of_range")
    if code == SA_ERR_BAD_CAUSE_SELECTION:
        return String("selected_cause_absent")
    if code == SA_ERR_NONPOSITIVE_TIME:
        return String("nonpositive_time")
    if code == SA_ERR_BAD_GRID:
        return String("grid_size_out_of_range")
    if code == SA_ERR_BAD_AGE:
        return String("age_out_of_range")
    if code == SA_ERR_BAD_QUANTILE:
        return String("quantile_out_of_range")
    if code == SA_ERR_WORK_BUDGET:
        return String("work_budget_exceeded")
    if code == SA_ERR_QUERY_LENGTH:
        return String("query_length_out_of_range")
    if code == SA_ERR_TOO_MANY_CAUSES:
        return String("too_many_causes")
    if code == SA_ERR_BAD_HORIZON:
        return String("horizon_out_of_range")
    if code == SA_ERR_BAD_SHAPE_PARAM:
        return String("distribution_parameter_out_of_range")
    if code == SA_ERR_PARTITION:
        return String("cumulative_incidence_partition_violated")
    if code == SA_ERR_LIKELIHOOD_UNBOUNDED:
        return String("likelihood_unbounded_no_mle_exists")
    if code == SA_ERR_EM_NOT_MONOTONE:
        return String("em_log_likelihood_decreased")
    return String("unknown_status")


fn sa_is_finite(x: Float64) -> Bool:
    """True when `x` is neither NaN nor an infinity.

    Delegates to the frozen `numeric.reduce.is_finite_value` so the whole tree has ONE
    definition of finite. This matters more than it looks: the JSON dispatch refuses a
    non-finite rather than serialising it, so a single raw NaN in one struct field turns
    an otherwise complete answer into a typed transport error. Every value slot in this
    package is therefore checked before it is stored, and an unrepresentable quantity is
    reported through a `has_*` flag with 0.0 in the slot.

    @capability sa_is_finite
    complexity: O(1)
    counts: none
    @endcapability
    """
    return is_finite_value(x)


fn sa_work_fits(factors: List[Int], budget: Int) -> Bool:
    """True when the product of `factors` is >= 0 and <= `budget`, computed by DIVISION.

    `rows * cols` is a wrapping 64-bit multiply -- `3 * 6148914691236517206 == 2` -- so a
    product formed and then compared is not a bound at all. This grows the product one
    factor at a time and treats "would exceed the budget" as the answer, so it never
    forms a value larger than `budget`. Same shape as the frozen
    `sparse_numerics.csr.dims_fit`, generalised from two factors to n.

    A zero factor makes the product zero, which fits any non-negative budget: a loop nest
    with a zero bound performs no work.

    @capability sa_work_fits
    complexity: O(len(factors))
    counts: none
    @endcapability
    """
    if budget < 0:
        return False
    var product: Int = 1
    for i in range(len(factors)):
        var f = factors[i]
        if f < 0:
            return False
        if f == 0:
            return True
        if product > budget // f:
            return False
        product = product * f
    return product <= budget


fn sa_validate_observations(times: List[Float64], event: List[Int]) -> Int:
    """The single door into this package. Returns `SA_OK` or the first defect found.

    Checks, in the order that makes the message most useful:

    * a non-empty sample                       -> `SA_ERR_EMPTY`
    * `len(event) == len(times)` EXACTLY       -> `SA_ERR_CENSOR_LENGTH`
    * `len(times) <= SA_MAX_OBS`               -> `SA_ERR_TOO_MANY_OBS`
    * every time finite                        -> `SA_ERR_NON_FINITE_TIME`
    * every time >= 0                          -> `SA_ERR_NEGATIVE_TIME`
    * every `event[i]` in {0, 1}               -> `SA_ERR_BAD_EVENT_CODE`

    The finiteness check is what stops the frozen `kaplan_meier` NaN hang, and the length
    check is what stops its out-of-bounds abort. Both were measured; see the module
    docstring. A time of exactly 0 is accepted -- an event at entry is a real, if
    degenerate, observation -- and the modules that take a logarithm of a time
    (`parametric`) additionally refuse 0 with `SA_ERR_NONPOSITIVE_TIME`, because that is
    their constraint and not this one's.

    There is no caller-supplied count in this signature: `n` is `len(times)`, so there is
    nothing for a `counts:` relation to bound and the block is `none` rather than a `dim`
    line naming a variable that is not a parameter. The `SA_MAX_OBS` ceiling is enforced
    here all the same, as the `SA_ERR_TOO_MANY_OBS` refusal above -- a refusal is not a
    count declaration, and declaring it as one told the gate to check a relation that could
    not be checked.

    @capability sa_validate_observations
    complexity: O(n)
    counts: none
    @endcapability
    """
    var n = len(times)
    if n == 0:
        return SA_ERR_EMPTY
    if len(event) != n:
        return SA_ERR_CENSOR_LENGTH
    if n > SA_MAX_OBS:
        return SA_ERR_TOO_MANY_OBS
    for i in range(n):
        if not is_finite_value(times[i]):
            return SA_ERR_NON_FINITE_TIME
    for i in range(n):
        if times[i] < 0.0:
            return SA_ERR_NEGATIVE_TIME
    for i in range(n):
        var code = event[i]
        if code != 0 and code != 1:
            return SA_ERR_BAD_EVENT_CODE
    return SA_OK


fn sa_validate_confidence(conf_level: Float64) -> Int:
    """Accept a two-sided confidence level in [0.5, 0.999999]; otherwise refuse.

    The band is bounded on BOTH sides on purpose. The frozen `math_ext.norm_ppf` returns
    +/-1e300 for `p` outside (0, 1) -- a finite number that would pass a finiteness check
    and then be multiplied into a standard error, producing a band of width 1e300 that
    clamps to [0, 1] and looks like an honest "no information". Refusing the level names
    the real problem. The upper bound keeps `z <= 4.892`, and a level below 0.5 is not a
    confidence level.

    @capability sa_validate_confidence
    complexity: O(1)
    counts: none
    @endcapability
    """
    if not is_finite_value(conf_level):
        return SA_ERR_BAD_CONFIDENCE
    if conf_level < 0.5 or conf_level > 0.999999:
        return SA_ERR_BAD_CONFIDENCE
    return SA_OK


fn sa_z_for_confidence(conf_level: Float64) -> Float64:
    """Two-sided normal critical value for `conf_level`, or 0.0 if the level is refused.

    0.0 rather than a sentinel: a caller must call `sa_validate_confidence` first, and
    every driver in this package does. `z = 0` would collapse a band onto the point
    estimate, which is visible, whereas a large sentinel would silently widen it.

    @capability sa_z_for_confidence
    complexity: O(1)
    counts: none
    @endcapability
    """
    if sa_validate_confidence(conf_level) != SA_OK:
        return 0.0
    var tail = (1.0 - conf_level) * 0.5
    var z = norm_ppf(1.0 - tail)
    if not is_finite_value(z) or z < 0.0:
        return 0.0
    return z


struct SortedObs(Copyable, Movable):
    """Observations in canonical ascending time order, with censoring carried alongside.

    `order[r]` is the ORIGINAL index of the observation at rank `r`, so a caller with a
    per-observation covariate row can gather it into the same order without re-deriving
    the permutation and risking a different tie break. `time` and `is_event` are the
    gathered columns, present so the common case needs no gather at all.
    """

    var status: Int
    var n_obs: Int
    var n_events: Int
    var n_censored: Int
    var order: List[Int]
    var time: List[Float64]
    var is_event: List[Bool]

    fn __init__(out self, status: Int):
        self.status = status
        self.n_obs = 0
        self.n_events = 0
        self.n_censored = 0
        self.order = List[Int]()
        self.time = List[Float64]()
        self.is_event = List[Bool]()


fn sa_sort_observations(times: List[Float64], event: List[Int]) -> SortedObs:
    """Canonical ascending order by time, events before censorings inside a tie group.

    The ordering comes from the frozen `causal_inference.base.ci_argsort_asc`, a stable
    iterative merge sort over indices. Nothing new was written: it is the only frozen
    kernel that returns a permutation rather than sorted values, and a permutation is what
    a covariate matrix needs.

    Two properties are then established that the frozen argsort alone does not give:

    * Inside a tie group, events are emitted before censorings. Every estimator in this
      package groups by exact time value, so this is invisible to the arithmetic -- but it
      makes the output a canonical form of the SAMPLE rather than of the caller's row
      order, so two callers who list the same dataset differently get byte-identical
      curves. A stable sort alone preserves the caller's order inside a tie and would not.
    * The result is CHECKED to be a permutation of `0..n-1` with the frozen
      `ci_is_permutation`, not assumed to be one. Everything downstream indexes
      `x[order[r]]`, and a bad index there is the uncatchable abort, so the one cheap O(n)
      check that rules it out is worth its cost.

    Both list lengths come from the lists; no count is passed in, so `counts:` is `none`
    and the `SA_MAX_OBS` ceiling is inherited from `sa_validate_observations` above.

    @capability sa_sort_observations
    complexity: O(n log n)
    counts: none
    @endcapability
    """
    var status = sa_validate_observations(times, event)
    var out = SortedObs(status)
    if status != SA_OK:
        return out^

    var n = len(times)
    var by_time = ci_argsort_asc(times)
    if not ci_is_permutation(by_time, n):
        out.status = SA_ERR_SHAPE
        return out^

    var n_ev = 0
    var r = 0
    while r < n:
        var t = times[by_time[r]]
        var stop = r
        while stop < n and times[by_time[stop]] == t:
            stop += 1
        for s in range(r, stop):
            var idx = by_time[s]
            if event[idx] == 1:
                out.order.append(idx)
                out.time.append(t)
                out.is_event.append(True)
                n_ev += 1
        for s in range(r, stop):
            var idx = by_time[s]
            if event[idx] != 1:
                out.order.append(idx)
                out.time.append(t)
                out.is_event.append(False)
        r = stop

    if len(out.order) != n or not ci_is_permutation(out.order, n):
        return SortedObs(SA_ERR_SHAPE)
    out.n_obs = n
    out.n_events = n_ev
    out.n_censored = n - n_ev
    return out^


struct RiskTable(Copyable, Movable):
    """The (t_j, n_j, d_j) table every estimator in this package is built from.

    One row per DISTINCT time at which at least one event occurred. `at_risk[j]` is
    `#{i : t_i >= t_j}` and counts observations censored exactly at `t_j`. `survival[j]`
    is the frozen Kaplan-Meier product through `t_j`, carried here so that no derived
    quantity ever recomputes it and disagrees.

    `status != SA_OK` means every list is empty; it does NOT mean "a curve of length 0".
    """

    var status: Int
    var n_obs: Int
    var n_events: Int
    var n_censored: Int
    var n_event_times: Int
    var time: List[Float64]
    var at_risk: List[Int]
    var events: List[Int]
    var survival: List[Float64]
    var monotone: Bool

    fn __init__(out self, status: Int):
        self.status = status
        self.n_obs = 0
        self.n_events = 0
        self.n_censored = 0
        self.n_event_times = 0
        self.time = List[Float64]()
        self.at_risk = List[Int]()
        self.events = List[Int]()
        self.survival = List[Float64]()
        self.monotone = False


fn sa_risk_table(times: List[Float64], event: List[Int]) -> RiskTable:
    """Risk sets, event counts and the frozen Kaplan-Meier product, one row per event time.

    The survival column is NOT recomputed here: `survival.kaplan_meier` is called on the
    canonically sorted observations and its `SurvivalPoint.survival` is copied through.
    The frozen kernel stays the single definition of what a Kaplan-Meier estimate is; the
    composition, the guards and the O(n log n) pre-sort are what this driver adds.

    Rows are selected by `events > 0`. That is exact rather than heuristic: the frozen
    kernel emits its synthetic origin row `(0, 1.0, n, 0)` with `d = 0` and appends a row
    only when `d > 0`, so the filter drops exactly the origin and keeps exactly the event
    times -- including a genuine event at time 0, which the alternative test "skip index
    0" would have silently deleted.

    `monotone` is checked, not assumed. A survival probability must lie in [0, 1] and be
    non-increasing; a floating-point path that produces a non-monotone curve is a real
    defect, so the property is verified against a per-point tolerance
    (`SA_DBL_EPSILON * |previous S|`, that point's own magnitude and nothing else) and a
    violation sets `SA_ERR_NON_MONOTONE`. It should never fire -- round-to-nearest is
    monotone, so `fl(S * f) <= fl(S * 1) = S` for `f <= 1` -- and the point of asserting
    it is that a future change to the multiplication order cannot break the guarantee
    silently.

    No count is passed in -- `n` is `len(times)` -- so `counts:` is `none`; the `SA_MAX_OBS`
    ceiling is inherited from `sa_validate_observations`, through `sa_sort_observations`.

    @capability sa_risk_table
    complexity: O(n log n)
    counts: none
    @endcapability
    """
    var sorted = sa_sort_observations(times, event)
    var out = RiskTable(sorted.status)
    if sorted.status != SA_OK:
        return out^

    out.n_obs = sorted.n_obs
    out.n_events = sorted.n_events
    out.n_censored = sorted.n_censored

    var curve = kaplan_meier(sorted.time, sorted.is_event)
    var previous: Float64 = 1.0
    var monotone = True
    for i in range(len(curve)):
        ref point = curve[i]
        if point.events <= 0:
            continue
        var s = point.survival
        var slop = SA_DBL_EPSILON * (previous if previous > 1.0 else 1.0)
        if s < -slop or s > 1.0 + slop or s > previous + slop:
            monotone = False
        if not is_finite_value(s):
            monotone = False
            s = 0.0
        out.time.append(point.time)
        out.at_risk.append(point.at_risk)
        out.events.append(point.events)
        out.survival.append(s)
        previous = s

    out.n_event_times = len(out.time)
    out.monotone = monotone
    if not monotone:
        out.status = SA_ERR_NON_MONOTONE
    return out^


fn sa_greenwood_terms(at_risk: List[Int], events: List[Int]) -> List[Float64]:
    """Per-event-time Greenwood terms `d_j / (n_j * (n_j - d_j))`, or -1.0 where undefined.

    -1.0 is the ABSENT marker, and it is safe to use as one because every defined term is
    strictly positive: `d_j >= 1` and `n_j > d_j` on a defined row. The undefined row is
    `n_j == d_j`, where the whole risk set fails at once and the variance of the estimator
    from that point on does not exist -- reporting 0.0 there would say "we measured zero
    uncertainty" about the one point where there is no information left.

    Returns an empty list when the two columns disagree in length, rather than indexing
    the shorter one.

    `k` is `len(at_risk)`, not an argument. An earlier revision declared
    `dim k <= SA_MAX_OBS [kernel_validated]` here and this function contains no such
    comparison anywhere -- a `[kernel_validated]` claim with nothing behind it, which is the
    one declaration that is worse than none because it tells the pre-call guard to stand
    down. There is no count to bound: the only shape hazard is the list-to-list length
    relation, which the grammar deliberately does not express and which is checked above.

    @capability sa_greenwood_terms
    complexity: O(k)
    counts: none
    @endcapability
    """
    var out = List[Float64]()
    var k = len(at_risk)
    if len(events) != k:
        return out^
    for j in range(k):
        var n = at_risk[j]
        var d = events[j]
        if n <= 0 or d <= 0 or d > n or n == d:
            out.append(-1.0)
            continue
        out.append(Float64(d) / (Float64(n) * Float64(n - d)))
    return out^
