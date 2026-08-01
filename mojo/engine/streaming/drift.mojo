"""
streaming.drift — Page-Hinkley change detection, resumable, plus a DDM scan.

WHICH DETECTOR, AND WHY: **Page-Hinkley**, not ADWIN.

ADWIN keeps a bucketed window and, on every update, searches every split of that window for
a statistically significant difference. Its memory is O(log n) and its WORK PER UPDATE is
O(number of buckets) -- so the honest cost of an ADWIN update is not O(1), and a package that
charged O(1) for it would be repeating the exact defect this tree measured elsewhere: 0.49s
versus 23.89s at an identical declared cost. Page-Hinkley keeps FIVE scalars, costs O(1) per
update with no hidden search, and is exactly resumable from those five scalars -- which is
what makes `page_hinkley_step` a real streaming surface over a stateless dispatch rather than
a simulation of one. The trade is stated rather than hidden: ADWIN adapts its window
automatically and Page-Hinkley needs `delta` and `threshold` chosen for the series.

Classification of every capability here
---------------------------------------
* **existing-frozen, CALLED not rewritten.** `pandas_groupby.group_mean_update` is Welford's
  online mean and is the running mean Page-Hinkley subtracts -- not re-derived here.
  `online_learning.concept_drift_ddm_error` is the frozen DDM alert-level rule and is the
  entire decision inside `ddm_scan`; this module supplies the running error rate, its
  standard error, and the historical minimum that the frozen rule compares against.
* **missing-driver.** `concept_drift_ddm_error` takes six scalars and returns 0, 1 or 2 for
  ONE instant. Nothing in the tree tracks the running error rate or the historical minimum,
  so nothing can actually call it over a stream. That accumulator is what is added.
* **genuinely-missing.** Page-Hinkley itself, in both directions, with an explicit resumable
  state and a typed verdict.

Absence, and the index that is not an index
-------------------------------------------
`DriftVerdict.change_index` is -1 when nothing was detected. -1 is deliberately NOT a
subscript anywhere in this package: a negative index aborts the process where a negative
count merely reads nothing, so a sentinel that could be fed back into a `List` read would be
a trap. Callers must test `detected` before using `change_index`, and the docstring says so
because the type cannot.

A verdict over an empty series is ABSENT, under `STM_EMPTY`, with `statistic` at 0.0 and
`detected` False. "No drift" and "no data to look at" are different answers, and reporting
the first for the second is the failure mode where a monitoring dashboard goes green because
its input stopped arriving.

Non-finite inputs are refused at the door. A NaN observation poisons the running mean, and
from then on every comparison against the cumulative sum is false, so the detector silently
never fires again -- a detector that has stopped working while still reporting "no drift".

Bounding memory AND work
------------------------
`page_hinkley_step` is five scalar updates: O(1) work, O(1) memory, and the state is small
enough to travel in a JSON response, which is the point. A scan over `n` observations is
therefore O(n) with no per-update search. `ddm_scan` is O(n) likewise: one frozen alert-level
call per observation.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: true
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_streaming_drift.mojo
benchmark: benchmarks/mojo_benchmarks/bench_streaming.mojo
docs: gitbook/engine/streaming-sketches.md
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from std.math import sqrt

from online_learning import concept_drift_ddm_error
from pandas_groupby import group_mean_update

from streaming.contract import (
    MAX_STM_WORK,
    STM_EMPTY,
    STM_ERR_COUNT,
    STM_ERR_INVALID_SKETCH,
    STM_ERR_ITEM_BUDGET,
    STM_ERR_NON_FINITE,
    STM_ERR_PARAM_RANGE,
    STM_OK,
    stm_finite,
    stm_items_ok,
    stm_work_fits,
)

#: DDM's published guidance: fewer observations than this do not support a decision, so a
#: shorter series is reported absent rather than judged on three data points.
comptime DDM_MIN_OBSERVATIONS: Int = 30


struct PageHinkleyState(Copyable, Movable):
    """The five scalars a Page-Hinkley detector needs, plus its verdict so far.

    Small on purpose: this is the whole detector, so it round-trips through a JSON response
    and a stateless dispatch can drive a genuinely online detector by handing the state back.

    `valid == False` means this is not a state and `status` says why; every function here
    refuses an invalid state rather than reading its fields.

    `change_index` is -1 until something is detected and is never used as a subscript.

    Declared in this file: a struct owned by another module is silently dropped from the
    runtime contract.
    """

    var mean: Float64
    var cum_up: Float64
    var min_up: Float64
    var cum_down: Float64
    var max_down: Float64
    var count: Int
    var detected: Bool
    var change_index: Int
    var statistic: Float64
    var status: Int
    var valid: Bool

    fn __init__(
        out self,
        mean: Float64,
        cum_up: Float64,
        min_up: Float64,
        cum_down: Float64,
        max_down: Float64,
        count: Int,
        detected: Bool,
        change_index: Int,
        statistic: Float64,
        status: Int,
        valid: Bool,
    ):
        self.mean = mean
        self.cum_up = cum_up
        self.min_up = min_up
        self.cum_down = cum_down
        self.max_down = max_down
        self.count = count
        self.detected = detected
        self.change_index = change_index
        self.statistic = statistic
        self.status = status
        self.valid = valid


struct DriftVerdict(Copyable, Movable):
    """Whether a change was detected, where, and on what statistic — or absence.

    `present == False` means there was nothing to decide: an empty series, an invalid state,
    or a refused parameter. `statistic` is then 0.0 and `detected` is False, and neither is
    an answer -- which is exactly why `present` exists. "No drift detected" and "no data"
    must not look the same.

    `change_index` is the zero-based position of the FIRST observation at which the statistic
    crossed the threshold, and -1 when `detected` is False. Test `detected` first: -1 is not
    a valid subscript and this package never uses it as one.
    """

    var detected: Bool
    var change_index: Int
    var statistic: Float64
    var threshold: Float64
    var n_seen: Int
    var present: Bool
    var status: Int

    fn __init__(
        out self,
        detected: Bool,
        change_index: Int,
        statistic: Float64,
        threshold: Float64,
        n_seen: Int,
        present: Bool,
        status: Int,
    ):
        self.detected = detected
        self.change_index = change_index
        self.statistic = statistic
        self.threshold = threshold
        self.n_seen = n_seen
        self.present = present
        self.status = status


fn _invalid_state(status: Int) -> PageHinkleyState:
    """Not a state, with the reason."""
    return PageHinkleyState(
        0.0, 0.0, 0.0, 0.0, 0.0, 0, False, -1, 0.0, status, False
    )


fn _no_verdict(status: Int, n_seen: Int, threshold: Float64) -> DriftVerdict:
    """No decision, with the reason. `statistic` is 0.0 and means nothing."""
    var safe = threshold if stm_finite(threshold) else 0.0
    return DriftVerdict(False, -1, 0.0, safe, n_seen, False, status)


fn _params_ok(delta: Float64, threshold: Float64) -> Int:
    """`STM_OK`, or the status that refuses these parameters.

    `delta` is the change magnitude tolerated before the cumulative sum starts to grow and
    must be non-negative; a negative `delta` makes the detector accumulate on ordinary noise
    and fire on every series. `threshold` must be positive and finite: a threshold of zero
    fires on the first observation, and a non-finite one never fires, so both are refusals
    rather than settings.
    """
    if not stm_finite(delta) or delta < 0.0:
        return STM_ERR_PARAM_RANGE
    if not stm_finite(threshold) or threshold <= 0.0:
        return STM_ERR_PARAM_RANGE
    return STM_OK


fn _state_ok(state: PageHinkleyState) -> Int:
    """`STM_OK`, or the status refusing this state. O(1).

    THE STRUCT PATH IS A CALLER PATH. `PageHinkleyState` is decoded from caller JSON by the
    generated dispatch, which validates FIELD TYPES and no cross-field invariant. There is no
    subscript in this module to abort, so this is not a crash guard -- it is a non-finite guard
    and a coherence guard, and both have teeth:

      * `page_hinkley_verdict` returns `state.statistic` VERBATIM. A forged non-finite there
        makes the whole response a typed error rather than one field being wrong, because the
        dispatch refuses to serialise a non-finite. Every scalar is checked, not just the one
        being returned, because `page_hinkley_step` folds all five into the next statistic.
      * `change_index` must be -1 when nothing was detected and a real position inside `count`
        otherwise. A state claiming `detected: true, change_index: 900` after 3 observations is
        not a detector state, and echoing it back would put a position into a report that names
        an observation that never arrived. -1 is never used as a subscript by this package, and
        this check is what keeps the other values from becoming one.
    """
    if not state.valid:
        return STM_ERR_INVALID_SKETCH
    if not stm_finite(state.mean) or not stm_finite(state.statistic):
        return STM_ERR_NON_FINITE
    if not stm_finite(state.cum_up) or not stm_finite(state.min_up):
        return STM_ERR_NON_FINITE
    if not stm_finite(state.cum_down) or not stm_finite(state.max_down):
        return STM_ERR_NON_FINITE
    if state.count < 0 or not stm_items_ok(state.count):
        return STM_ERR_ITEM_BUDGET
    if state.detected:
        if state.change_index < 0 or state.change_index >= state.count:
            return STM_ERR_PARAM_RANGE
    elif state.change_index != -1:
        return STM_ERR_PARAM_RANGE
    return STM_OK


fn page_hinkley_init() -> PageHinkleyState:
    """A fresh detector that has seen nothing.

    Valid, with `count == 0`. `page_hinkley_verdict` reports ABSENT for it, because a
    detector that has seen nothing has not decided that there is no drift.

    @capability page_hinkley_init
    complexity: O(1)
    counts: none
    @endcapability
    """
    return PageHinkleyState(0.0, 0.0, 0.0, 0.0, 0.0, 0, False, -1, 0.0, STM_OK, True)


fn page_hinkley_step(
    state: PageHinkleyState, x: Float64, delta: Float64, threshold: Float64
) -> PageHinkleyState:
    """The detector after one more observation, as a new value.

    The running mean is the frozen `pandas_groupby.group_mean_update` -- Welford's update, so
    the mean does not drift from repeated addition the way a running `sum / count` does. Two
    cumulative sums are then maintained:

        cum_up   += x - mean - delta      min_up  = min(min_up, cum_up)
        cum_down += x - mean + delta      max_down = max(max_down, cum_down)

    and the statistic is the larger of `cum_up - min_up` (an upward shift) and
    `max_down - cum_down` (a downward shift). Detection is sticky: once `detected` is True it
    stays True and `change_index` keeps naming the FIRST crossing, because the caller asked
    where the change was and not where it most recently still was.

    @capability page_hinkley_step
    complexity: O(1)
    counts: none
    @endcapability
    """
    var shape = _state_ok(state)
    if shape != STM_OK:
        return _invalid_state(shape)
    if not stm_finite(x):
        return _invalid_state(STM_ERR_NON_FINITE)
    var bad = _params_ok(delta, threshold)
    if bad != STM_OK:
        return _invalid_state(bad)
    if not stm_items_ok(state.count + 1):
        return _invalid_state(STM_ERR_ITEM_BUDGET)

    var count = state.count + 1
    var mean = group_mean_update(state.mean, x, Float64(count))
    var cum_up = state.cum_up + (x - mean - delta)
    var cum_down = state.cum_down + (x - mean + delta)
    var min_up = cum_up if cum_up < state.min_up else state.min_up
    var max_down = cum_down if cum_down > state.max_down else state.max_down
    var up = cum_up - min_up
    var down = max_down - cum_down
    var statistic = up if up > down else down
    if not stm_finite(statistic) or not stm_finite(mean):
        return _invalid_state(STM_ERR_NON_FINITE)

    var detected = state.detected
    var change_index = state.change_index
    if not detected and statistic > threshold:
        detected = True
        change_index = count - 1
    return PageHinkleyState(
        mean, cum_up, min_up, cum_down, max_down, count, detected, change_index,
        statistic, STM_OK, True,
    )


fn page_hinkley_verdict(
    state: PageHinkleyState, threshold: Float64
) -> DriftVerdict:
    """The detector's decision, or ABSENCE when it has seen nothing.

    @capability page_hinkley_verdict
    complexity: O(1)
    counts: none
    @endcapability
    """
    var shape = _state_ok(state)
    if shape != STM_OK:
        return _no_verdict(shape, 0, threshold)
    if state.count <= 0:
        return _no_verdict(STM_EMPTY, 0, threshold)
    if not stm_finite(threshold):
        return _no_verdict(STM_ERR_PARAM_RANGE, state.count, 0.0)
    return DriftVerdict(
        state.detected, state.change_index, state.statistic, threshold,
        state.count, True, STM_OK,
    )


fn page_hinkley_resume(
    state: PageHinkleyState, values: List[Float64], delta: Float64, threshold: Float64
) -> PageHinkleyState:
    """The detector after a whole further chunk, as a new value.

    This is the shape of the actual job: a worker holds a stored state, receives the next
    chunk, and must not restart. Feeding the same chunks in the same order through
    `page_hinkley_resume` produces the state a single `page_hinkley_scan` over the
    concatenation would produce -- the detector is exactly resumable, and the suite asserts
    that with `==` on all five scalars rather than on the verdict alone.

    @capability page_hinkley_resume
    complexity: O(len(values))
    counts: none
    @endcapability
    """
    var shape = _state_ok(state)
    if shape != STM_OK:
        return _invalid_state(shape)
    var bad = _params_ok(delta, threshold)
    if bad != STM_OK:
        return _invalid_state(bad)
    if not stm_work_fits(len(values), 1, MAX_STM_WORK):
        return _invalid_state(STM_ERR_ITEM_BUDGET)
    var current = state.copy()
    for i in range(len(values)):
        current = page_hinkley_step(current, values[i], delta, threshold)
        if not current.valid:
            return current^
    return current^


fn page_hinkley_scan(
    values: List[Float64], delta: Float64, threshold: Float64
) -> DriftVerdict:
    """Two-sided Page-Hinkley over the whole series.

    The element count is `len(values)` and is never a parameter, which removes the
    `n > len(v)` class from this entry point by construction.

    @capability page_hinkley_scan
    complexity: O(len(values))
    counts: none
    @endcapability
    """
    return page_hinkley_scan_prefix(values, len(values), delta, threshold)


fn page_hinkley_scan_prefix(
    values: List[Float64], n: Int, delta: Float64, threshold: Float64
) -> DriftVerdict:
    """Two-sided Page-Hinkley over `values[0..n)`.

    `n` is a redundant count and is validated in BOTH directions before anything is indexed.
    An `n` past the end reads past the `List` end, which aborts the worker process in a way
    `try/except` cannot contain; a negative `n` reads nothing rather than aborting and is
    refused anyway, because "scan minus three observations" has no answer.

    @capability page_hinkley_scan_prefix
    complexity: O(n)
    counts:
    - n <= len(values) [kernel_validated]
    @endcapability
    """
    var bad = _params_ok(delta, threshold)
    if bad != STM_OK:
        return _no_verdict(bad, 0, threshold)
    if n < 0 or n > len(values):
        return _no_verdict(STM_ERR_COUNT, 0, threshold)
    if n == 0:
        return _no_verdict(STM_EMPTY, 0, threshold)
    if not stm_items_ok(n):
        return _no_verdict(STM_ERR_ITEM_BUDGET, n, threshold)
    var state = page_hinkley_init()
    for i in range(n):
        state = page_hinkley_step(state, values[i], delta, threshold)
        if not state.valid:
            return _no_verdict(state.status, i, threshold)
    return page_hinkley_verdict(state, threshold)


fn _ddm_params_bad(warning_level: Float64, drift_level: Float64) -> Bool:
    """True when the two DDM multipliers are not a usable pair.

    `drift_level` below `warning_level` would make the drift band a subset of the warning
    band, so the frozen rule would report drift for series it never warned about.
    """
    if not stm_finite(warning_level) or not stm_finite(drift_level):
        return True
    return warning_level <= 0.0 or drift_level < warning_level


fn _ddm_levels(
    errors: List[Bool], warning_level: Float64, drift_level: Float64
) -> List[Int]:
    """The shared DDM accumulator. One implementation, two public shapes over it.

    Written once on purpose: `ddm_scan` and `ddm_levels` differ only in what they return, and
    two copies of an accumulator drift into two behaviours under one name -- a duplicated
    guard reads as defence in depth while providing one arbitrary answer per call site.

    THE DEGENERATE MINIMUM, AND WHY THE MINIMUM IS ONLY TRACKED WHERE s > 0
    ----------------------------------------------------------------------
    The frozen `concept_drift_ddm_error` declares drift when
    `p + s > p_min + s_min + drift_level * s_min`. With `s_min == 0` that collapses to
    `p + s > p_min`, so a run of perfect predictions -- `p = 0`, `s = 0`, hence
    `p_min + s_min = 0` -- makes the FIRST single error satisfy it. Measured here before this
    guard existed: 40 correct predictions followed by errors reported drift at the very first
    error, index 40, on a `p` of 1/41.

    That is not a defect in the frozen rule; the rule has no standard error to work with and
    is being asked for a decision anyway. So this accumulator only records a historical
    minimum at instants where `s > 0` -- where a standard error actually exists -- and reports
    level 0 until one does. The frozen rule is called unchanged; what changed is that it is no
    longer fed a minimum that means "no information".
    """
    var out = List[Int]()
    var n = len(errors)
    var wrong = 0
    var min_signal = 0.0
    var min_error = 0.0
    var min_std = 0.0
    var have_min = False
    for i in range(n):
        if errors[i]:
            wrong += 1
        var seen = Float64(i + 1)
        var p = Float64(wrong) / seen
        var s = sqrt(p * (1.0 - p) / seen)
        if s > 0.0 and (not have_min or (p + s) < min_signal):
            min_signal = p + s
            min_error = p
            min_std = s
            have_min = True
        if not have_min:
            out.append(0)
            continue
        out.append(
            Int(
                concept_drift_ddm_error(
                    p, s, min_error, min_std, warning_level, drift_level
                )
            )
        )
    return out^


fn ddm_scan(
    errors: List[Bool], warning_level: Float64, drift_level: Float64
) -> DriftVerdict:
    """Drift Detection Method over a stream of classification errors.

    The decision at every instant is the frozen `online_learning.concept_drift_ddm_error`,
    unchanged. What is added is the accumulator it needs and that nothing in the tree
    provides: the running error rate `p_i`, its standard error `sqrt(p_i (1 - p_i) / i)`, and
    the historical minimum of `p_i + s_i` with the `s_i` recorded at that minimum -- tracked
    only at instants where that standard error is non-zero, for the reason set out in
    `_ddm_levels`.

    `change_index` names the first instant the frozen rule returned 2 (drift). A warning-only
    series is `detected == False` with `statistic == 1.0`, so the two levels stay
    distinguishable in the verdict instead of collapsing into a boolean.

    DDM's own guidance is that fewer than `DDM_MIN_OBSERVATIONS` observations do not support a
    decision, so a shorter series is reported ABSENT under `STM_EMPTY` rather than judged.

    @capability ddm_scan
    complexity: O(len(errors))
    counts: none
    @endcapability
    """
    if _ddm_params_bad(warning_level, drift_level):
        return _no_verdict(STM_ERR_PARAM_RANGE, len(errors), drift_level)
    var n = len(errors)
    if n < DDM_MIN_OBSERVATIONS:
        return _no_verdict(STM_EMPTY, n, drift_level)
    if not stm_items_ok(n):
        return _no_verdict(STM_ERR_ITEM_BUDGET, n, drift_level)
    var levels = _ddm_levels(errors, warning_level, drift_level)
    var worst = 0
    var change_index = -1
    for i in range(len(levels)):
        if levels[i] > worst:
            worst = levels[i]
        if levels[i] >= 2 and change_index < 0:
            change_index = i
    return DriftVerdict(
        change_index >= 0, change_index, Float64(worst), drift_level, n, True, STM_OK
    )


fn ddm_levels(
    errors: List[Bool], warning_level: Float64, drift_level: Float64
) -> List[Int]:
    """The frozen DDM alert level (0 normal, 1 warning, 2 drift) at every instant.

    Returns an EMPTY list when the parameters are refused or the series is too short to
    judge, which is distinguishable from a series of zeros: a list of zeros says "checked at
    every instant, nothing wrong", and an empty list says "not checked".

    @capability ddm_levels
    complexity: O(len(errors))
    counts: none
    @endcapability
    """
    if _ddm_params_bad(warning_level, drift_level):
        return List[Int]()
    var n = len(errors)
    if n < DDM_MIN_OBSERVATIONS or not stm_items_ok(n):
        return List[Int]()
    return _ddm_levels(errors, warning_level, drift_level)
