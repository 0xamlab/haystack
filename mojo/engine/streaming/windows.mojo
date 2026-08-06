"""
streaming.windows — windowed aggregates, with each one's real cost charged.

Classification of every capability here
---------------------------------------
* **existing-frozen, CALLED not rewritten.** `timeseries_stats.rolling_mean` is a sliding-sum
  moving average and is called verbatim by `window_mean`. `timeseries_stats.rolling_std` is
  the exact per-window standard deviation and is called verbatim by `window_std`.
  `online_learning.exponential_moving_average` and
  `online_learning.exponential_moving_variance` are the two EWMA updates and are the entire
  body of the loops in `ewma_series` and `ewmvar_series`.
  `pandas_groupby.group_mean_update` and `pandas_groupby.group_variance_update` are Welford's
  mean and M2 updates and are what `window_summary_prefix` accumulates with.
* **genuinely-missing.** There is no `rolling_min` and no `rolling_max` anywhere in the tree,
  and no monotonic deque. `window_min`, `window_max` and `window_range` add them in O(n)
  total -- amortised O(1) per position -- rather than the O(n*w) a per-window rescan would
  cost.
* **missing-driver.** The frozen pieces return bare lists with no length contract, no
  presence flags and no refusal: `rolling_mean` returns an EMPTY list for `window > n`, which
  a caller reading `result[0]` cannot distinguish from a valid answer without knowing the
  rule. Wrapping them in a result that carries `window`, `n_positions`, a per-position
  presence flag and a status is the driver.

The two costs are DIFFERENT, and both are charged
-------------------------------------------------
This is the module where "bounding memory is not bounding work" is concrete and measurable.

  * `window_mean` is the frozen sliding sum: **O(n)** regardless of `window`. Charged as
    `n * 1`.
  * `window_std` is the frozen exact per-window recompute: **O(n * window)**, because
    `rolling_std` recomputes each window's mean and then its sum of squares. Charged as the
    PRODUCT `n * window`, through the division-based `stm_work_fits`.
  * `window_min` / `window_max` / `window_range` are monotonic deques: **O(n)**. Charged as
    `n * 1`.

Charging `n + window` for `window_std` would let `n = 1,000,000` with `window = 500,000`
through as a cheap request and then run for minutes. That exact mistake has been measured in
this tree at 0.49s versus 23.89s under one declared cost, which is why the products differ
per function here instead of one budget covering the module.

A sliding-window variance is NOT computed by Welford removal
-----------------------------------------------------------
Welford's update has no numerically sound inverse. Subtracting a departing observation from an
M2 accumulator loses all the cancellation protection the forward update exists to provide, and
on a window whose values are large and close together it produces a NEGATIVE variance -- whose
square root is a NaN, which the dispatch refuses, so the whole response becomes a typed error.
So `window_std` pays the frozen O(n*w) exact recompute and charges for it, and
`window_summary_prefix` accumulates FORWARD only, over one window, with the frozen Welford
updates. Cheap-and-wrong was available and was not taken.

Absence
-------
`window > n` has no windows in it, so the result is `valid == True` with `n_positions == 0`
and empty lists -- not a single window over the short data, and not a zero. A per-position
`present` flag rides alongside the values because a future windowing rule that leaves a
position undefined must be expressible without changing the shape; today every present flag
in a valid series is True, and the flag being uniformly True is itself a checkable property.

Non-finite inputs are refused. A NaN inside a monotonic deque is the silent case: every
comparison against it is false, so it is never evicted and never wins, and the reported
minimum simply skips a position without any error. Refusing at the door is the only place
that is cheap.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: true
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_streaming_windows.mojo
benchmark: benchmarks/mojo_benchmarks/bench_streaming.mojo
docs: gitbook/engine/streaming-windows.md
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from std.math import sqrt

from online_learning import (
    exponential_moving_average,
    exponential_moving_variance,
)
from pandas_groupby import group_mean_update, group_variance_update
from timeseries_stats import rolling_mean, rolling_std

from streaming.contract import (
    MAX_STM_WORK,
    STM_EMPTY,
    STM_ERR_COUNT,
    STM_ERR_NON_FINITE,
    STM_ERR_PARAM_RANGE,
    STM_ERR_WINDOW,
    STM_ERR_WORK_BUDGET,
    STM_OK,
    stm_finite,
    stm_items_ok,
    stm_tolerance,
    stm_work_fits,
)

#: `contract.MAX_STM_WINDOW`, restated here because a declared ceiling must name a constant
#: in the SAME file as the kernel that tests it -- otherwise the declaration and the check
#: are two different numbers that can drift apart. This is the constant this file's guards
#: test against, and `test_streaming_windows.mojo` asserts it still equals the contract's.
comptime WINDOW_MAX_SPAN: Int = 65536


struct WindowSeries(Copyable, Movable):
    """One value per window position, with a presence flag each.

    `valid == False` means the request was refused and `status` says why; the lists are empty.
    `valid == True` with `n_positions == 0` means the request was fine and there are no
    windows in the data -- a different fact, and one a caller must be able to see without
    inferring it from an empty list.

    `window == 0` marks an aggregate with no finite window, which is what an EWMA is: its
    memory is unbounded and decaying, so quoting a window length for it would be a fiction.

    Declared in this file: a struct owned by another module is silently dropped from the
    runtime contract.
    """

    var values: List[Float64]
    var present: List[Bool]
    var window: Int
    var n_positions: Int
    var status: Int
    var valid: Bool

    def __init__(
        out self,
        values: List[Float64],
        present: List[Bool],
        window: Int,
        n_positions: Int,
        status: Int,
        valid: Bool,
    ):
        self.values = values.copy()
        self.present = present.copy()
        self.window = window
        self.n_positions = n_positions
        self.status = status
        self.valid = valid


struct WindowSummary(Copyable, Movable):
    """Mean, variance, minimum and maximum of one window, or their absence.

    `present == False` means the window had no observations in it, and all four value slots
    are 0.0 and mean nothing. A window of one observation has a mean and a variance of 0.0,
    and that IS an answer -- `present == True` -- which is exactly why the flag exists
    separately from the numbers.

    This struct is also decoded FROM caller JSON when it is passed back to `window_summary_std`,
    so none of these fields is trustworthy on that path. Anything reading a summary it did not
    itself produce validates it; `window_summary_std` says how and why.
    """

    var mean: Float64
    var variance: Float64
    var minimum: Float64
    var maximum: Float64
    var count: Int
    var present: Bool
    var status: Int

    def __init__(
        out self,
        mean: Float64,
        variance: Float64,
        minimum: Float64,
        maximum: Float64,
        count: Int,
        present: Bool,
        status: Int,
    ):
        self.mean = mean
        self.variance = variance
        self.minimum = minimum
        self.maximum = maximum
        self.count = count
        self.present = present
        self.status = status


def _refused(status: Int, window: Int) -> WindowSeries:
    """Not a series, with the reason."""
    return WindowSeries(List[Float64](), List[Bool](), window, 0, status, False)


def _empty_series(window: Int) -> WindowSeries:
    """A valid series with no positions in it: the window does not fit the data."""
    return WindowSeries(List[Float64](), List[Bool](), window, 0, STM_OK, True)


def _no_summary(status: Int) -> WindowSummary:
    """No summary, with the reason. Every value slot is 0.0 and means nothing."""
    return WindowSummary(0.0, 0.0, 0.0, 0.0, 0, False, status)


def _all_present(values: List[Float64], window: Int) -> WindowSeries:
    """Wrap a computed value list as a fully present series."""
    var flags = List[Bool]()
    for _ in range(len(values)):
        flags.append(True)
    return WindowSeries(values, flags^, window, len(values), STM_OK, True)


def _first_non_finite(values: List[Float64]) -> Int:
    """Index of the first non-finite element, or -1 when every element is finite."""
    for i in range(len(values)):
        if not stm_finite(values[i]):
            return i
    return -1


def window_positions(n_values: Int, window: Int) -> Int:
    """How many window positions `n_values` observations admit, or 0 when none do.

    `n_values - window + 1`, and 0 rather than a negative number when the window does not
    fit: a negative position count would be fed to `range()` by a caller and read nothing,
    which is a silent empty answer instead of a visible zero.

    @capability window_positions
    complexity: O(1)
    counts:
    - dim window <= WINDOW_MAX_SPAN [kernel_validated]
    @endcapability
    """
    if window < 1 or window > WINDOW_MAX_SPAN:
        return 0
    if n_values < window:
        return 0
    return n_values - window + 1


def _window_ok(values: List[Float64], window: Int, per_position: Int) -> Int:
    """`STM_OK`, or the status that refuses this windowing request.

    `per_position` is the per-position work multiplier, so the caller's cost is charged as
    the PRODUCT and never as a sum.
    """
    if window < 1 or window > WINDOW_MAX_SPAN:
        return STM_ERR_WINDOW
    if not stm_items_ok(len(values)):
        return STM_ERR_COUNT
    if _first_non_finite(values) >= 0:
        return STM_ERR_NON_FINITE
    if not stm_work_fits(len(values), per_position, MAX_STM_WORK):
        return STM_ERR_WORK_BUDGET
    return STM_OK


def window_mean(values: List[Float64], window: Int) -> WindowSeries:
    """Moving average, from the frozen `timeseries_stats.rolling_mean`.

    O(n) regardless of `window`: the frozen implementation keeps a running sum and slides it,
    so the work charge is `n * 1` and NOT `n * window`. Contrast `window_std`, which is the
    same shape of request at a genuinely different cost.

    @capability window_mean
    complexity: O(len(values))
    counts:
    - dim window <= WINDOW_MAX_SPAN [kernel_validated]
    @endcapability
    """
    var bad = _window_ok(values, window, 1)
    if bad != STM_OK:
        return _refused(bad, window)
    if window > len(values):
        return _empty_series(window)
    return _all_present(rolling_mean(values, window), window)


def window_std(values: List[Float64], window: Int) -> WindowSeries:
    """Per-window population standard deviation, from the frozen `rolling_std`.

    **O(len(values) * window)**, and charged as that product. The frozen implementation
    recomputes each window's mean and then its sum of squared deviations, which is the
    numerically sound way: there is no stable inverse of Welford's update, and subtracting a
    departing observation from an M2 accumulator produces a negative variance on
    large-and-close data, whose square root is a NaN that turns the whole response into a
    typed error.

    A request whose product exceeds the work budget is REFUSED rather than run, because a
    small-looking payload -- a million observations and a half-million-wide window -- is
    otherwise minutes of work behind a cheap-looking request.

    @capability window_std
    complexity: O(len(values) * window)
    counts:
    - dim window <= WINDOW_MAX_SPAN [kernel_validated]
    @endcapability
    """
    var bad = _window_ok(values, window, window)
    if bad != STM_OK:
        return _refused(bad, window)
    if window > len(values):
        return _empty_series(window)
    return _all_present(rolling_std(values, window), window)


def _monotonic(values: List[Float64], window: Int, want_max: Bool) -> List[Float64]:
    """Windowed minimum or maximum in O(n) via a monotonic index deque.

    The deque holds indices whose values are monotone, so its head is always the extreme of
    the current window. Each index is pushed once and popped once, which is what makes the
    whole pass amortised O(1) per position rather than O(window).
    """
    var out = List[Float64]()
    var deque = List[Int]()
    var head = 0
    for i in range(len(values)):
        # Drop indices that have left the window through the front.
        while head < len(deque) and deque[head] <= i - window:
            head += 1
        # Drop tail indices that can never be the extreme again.
        while len(deque) > head:
            var last = deque[len(deque) - 1]
            var beaten = values[last] <= values[i] if want_max else values[last] >= values[i]
            if not beaten:
                break
            _ = deque.pop()
        deque.append(i)
        if i >= window - 1:
            out.append(values[deque[head]])
    return out^


def window_max(values: List[Float64], window: Int) -> WindowSeries:
    """Windowed maximum in O(len(values)) — no frozen kernel does this.

    There is no `rolling_max` in the tree, and the obvious implementation rescans each window
    for O(n * window). A monotonic index deque gives the same answers in O(n) total, with
    each index pushed once and popped once.

    @capability window_max
    complexity: O(len(values))
    counts:
    - dim window <= WINDOW_MAX_SPAN [kernel_validated]
    @endcapability
    """
    var bad = _window_ok(values, window, 1)
    if bad != STM_OK:
        return _refused(bad, window)
    if window > len(values):
        return _empty_series(window)
    return _all_present(_monotonic(values, window, True), window)


def window_min(values: List[Float64], window: Int) -> WindowSeries:
    """Windowed minimum in O(len(values)) — no frozen kernel does this.

    @capability window_min
    complexity: O(len(values))
    counts:
    - dim window <= WINDOW_MAX_SPAN [kernel_validated]
    @endcapability
    """
    var bad = _window_ok(values, window, 1)
    if bad != STM_OK:
        return _refused(bad, window)
    if window > len(values):
        return _empty_series(window)
    return _all_present(_monotonic(values, window, False), window)


def window_range(values: List[Float64], window: Int) -> WindowSeries:
    """Windowed maximum minus minimum, in O(len(values)) — two deques, one pass each.

    The difference of two finite doubles of the same window is finite, so no non-finite value
    can appear here that the input check did not already refuse.

    @capability window_range
    complexity: O(len(values))
    counts:
    - dim window <= WINDOW_MAX_SPAN [kernel_validated]
    @endcapability
    """
    var bad = _window_ok(values, window, 2)
    if bad != STM_OK:
        return _refused(bad, window)
    if window > len(values):
        return _empty_series(window)
    var highs = _monotonic(values, window, True)
    var lows = _monotonic(values, window, False)
    var out = List[Float64]()
    for i in range(len(highs)):
        out.append(highs[i] - lows[i])
    return _all_present(out^, window)


def ewma_series(values: List[Float64], alpha: Float64) -> WindowSeries:
    """Exponentially weighted moving average, from the frozen update, one value per input.

    Seeded with `values[0]` rather than 0.0: seeding at zero makes the first several outputs
    an artefact of the seed rather than of the data, and a caller reading `result[0]` cannot
    tell. `window` is reported as 0, which this module's contract defines as "no finite
    window" -- an EWMA's memory is unbounded and decaying.

    `alpha` must be strictly inside `(0, 1)`. `alpha = 0` never moves off the seed and
    `alpha = 1` is the identity, so both are degenerate rather than useful settings and are
    refused instead of quietly returned.

    @capability ewma_series
    complexity: O(len(values))
    counts: none
    @endcapability
    """
    if not stm_finite(alpha) or alpha <= 0.0 or alpha >= 1.0:
        return _refused(STM_ERR_PARAM_RANGE, 0)
    if not stm_items_ok(len(values)):
        return _refused(STM_ERR_COUNT, 0)
    if _first_non_finite(values) >= 0:
        return _refused(STM_ERR_NON_FINITE, 0)
    if len(values) == 0:
        return _empty_series(0)
    var out = List[Float64]()
    var ema = values[0]
    out.append(ema)
    for i in range(1, len(values)):
        ema = exponential_moving_average(ema, values[i], alpha)
        out.append(ema)
    return _all_present(out^, 0)


def ewmvar_series(values: List[Float64], alpha: Float64) -> WindowSeries:
    """Exponentially weighted moving variance, from the frozen update.

    The frozen `exponential_moving_variance` needs the EMA from BEFORE the current
    observation, so the two are advanced in the right order here: variance first, then the
    mean. Reversing them silently reports a variance about the wrong centre.

    The first position is 0.0 and PRESENT: with one observation the exponentially weighted
    variance is genuinely zero, not unknown.

    @capability ewmvar_series
    complexity: O(len(values))
    counts: none
    @endcapability
    """
    if not stm_finite(alpha) or alpha <= 0.0 or alpha >= 1.0:
        return _refused(STM_ERR_PARAM_RANGE, 0)
    if not stm_items_ok(len(values)):
        return _refused(STM_ERR_COUNT, 0)
    if _first_non_finite(values) >= 0:
        return _refused(STM_ERR_NON_FINITE, 0)
    if len(values) == 0:
        return _empty_series(0)
    var out = List[Float64]()
    var ema = values[0]
    var emv: Float64 = 0.0
    out.append(0.0)
    for i in range(1, len(values)):
        emv = exponential_moving_variance(emv, ema, values[i], alpha)
        ema = exponential_moving_average(ema, values[i], alpha)
        if not stm_finite(emv):
            return _refused(STM_ERR_NON_FINITE, 0)
        out.append(emv)
    return _all_present(out^, 0)


def window_summary_prefix(
    values: List[Float64], n: Int, window: Int
) -> WindowSummary:
    """Mean, variance, minimum and maximum of the LAST window inside `values[0..n)`.

    The shape a monitor actually wants: one scalar summary of the most recent window, without
    materialising a value per position. Accumulated FORWARD with the frozen Welford pair --
    `pandas_groupby.group_mean_update` and `pandas_groupby.group_variance_update` -- so the
    variance is the numerically sound one and never the difference of two large sums.

    `n` is a redundant count and is validated in BOTH directions before anything is indexed.
    An `n` past the end reads past the `List` end, which aborts the worker in a way
    `try/except` cannot contain; a negative `n` reads nothing rather than aborting and is
    refused anyway.

    A `window` larger than `n` has no last window, so the result is ABSENT under
    `STM_ERR_WINDOW` rather than a summary of everything that happened to be there.

    @capability window_summary_prefix
    complexity: O(window)
    counts:
    - n <= len(values) [kernel_validated]
    - dim window <= WINDOW_MAX_SPAN [kernel_validated]
    @endcapability
    """
    if n < 0 or n > len(values):
        return _no_summary(STM_ERR_COUNT)
    if window < 1 or window > WINDOW_MAX_SPAN:
        return _no_summary(STM_ERR_WINDOW)
    if n == 0:
        return _no_summary(STM_EMPTY)
    if window > n:
        return _no_summary(STM_ERR_WINDOW)
    var start = n - window
    var mean: Float64 = 0.0
    var m2: Float64 = 0.0
    var lo: Float64 = 0.0
    var hi: Float64 = 0.0
    for j in range(window):
        var x = values[start + j]
        if not stm_finite(x):
            return _no_summary(STM_ERR_NON_FINITE)
        if j == 0:
            lo = x
            hi = x
        else:
            if x < lo:
                lo = x
            if x > hi:
                hi = x
        var new_mean = group_mean_update(mean, x, Float64(j + 1))
        m2 = group_variance_update(m2, mean, x, new_mean)
        mean = new_mean
    var variance = m2 / Float64(window)
    if not stm_finite(mean) or not stm_finite(variance):
        return _no_summary(STM_ERR_NON_FINITE)
    return WindowSummary(mean, variance, lo, hi, window, True, STM_OK)


def window_summary_std(summary: WindowSummary) -> Float64:
    """Standard deviation of a summary, or -1.0 when there is no summary to take one of.

    Takes the summary rather than recomputing, so a caller never pays for the window twice.

    -1.0 AND NOT 0.0 FOR AN ABSENT OR UNUSABLE SUMMARY. A standard deviation is never negative,
    so -1.0 cannot be confused with an answer -- and 0.0 can: a one-observation window has a
    standard deviation of exactly 0.0, and a constant window does too. Returning 0.0 for "there
    was nothing to compute" would be the absence-reported-as-zero this package exists to avoid,
    and it would be indistinguishable from the commonest real answer in a monitoring series.

    `WindowSummary` is decoded from caller JSON, so `variance` is a caller-supplied Float64 and
    `NaN <= 0.0` is FALSE -- a forged NaN variance reached `sqrt` and came back NaN, which the
    dispatch refuses, so one field made the WHOLE response a typed error. `stm_finite` is checked
    first for that reason. A finite variance that is negative by more than the rounding of the
    window's own squared range is likewise not a variance: a forward Welford `m2` can land a few
    epsilon below zero on a constant window, and that is the only negative worth tolerating, so
    the allowance is scaled by `(maximum - minimum)^2` -- the magnitude of the quantity being
    judged -- and not by the caller's numbers or by any other window's.

    `count < 1` beside `present == True` is refused for the same reason: a summary of minus three
    observations is not a summary, and echoing back the square root of whatever was in its
    variance slot would put a number on it.

    @capability window_summary_std
    complexity: O(1)
    counts: none
    @endcapability
    """
    if not summary.present:
        return -1.0
    if summary.count < 1:
        return -1.0
    if not stm_finite(summary.variance):
        return -1.0
    if not stm_finite(summary.minimum) or not stm_finite(summary.maximum):
        return -1.0
    var spread = summary.maximum - summary.minimum
    if summary.variance < -stm_tolerance(spread * spread, 0.0):
        return -1.0
    if summary.variance <= 0.0:
        return 0.0
    return sqrt(summary.variance)
