"""
forecasting.intermittent — Croston-family demand forecasting. Zero Python imports.

Why intermittent demand needs its own driver
--------------------------------------------
For a series where most periods are zero, every ordinary forecasting kernel in the tree gives
a defensible-looking and useless answer. `series.exponential_forecast` smooths the zeros in
with the demands and returns a small number that no period will ever equal.
`series.naive_forecast` returns whatever the last period happened to be, which is 0.0 nine
times in ten. And the error measures mislead in the same direction: MAPE divides by an actual
of zero at most points, which the frozen `series.forecast_accuracy` handles by skipping those
points and dividing by the FULL length anyway — a number that gets SMALLER the more
inapplicable the measure is. `forecasting.backtest.forecast_errors_flat` reports it absent and
counts the undefined points instead.

Croston's insight is to model two things separately: the SIZE of a demand when one occurs, and
the INTERVAL between occurrences. The per-period forecast is then the rate `z / p`, which is
an expected demand per period and is not a prediction that any individual period will equal it.

Every number comes from frozen kernels
--------------------------------------
  * both exponential smoothings are `forecasting.contract._fc_ses_level`, i.e. the frozen
    `series.exponential_forecast` — one over the demand sizes, one over the intervals;
  * the moments in `demand_classify` are `stats.compute_mean` and `stats.compute_variance`
    (the latter is the SAMPLE variance, `n - 1` in the denominator, which is why `n_nonzero`
    must be at least 2 for a CV to exist at all).

Nothing here re-implements a smoother or a variance.

The three variants and the one that annihilates itself
------------------------------------------------------
Croston's estimator is biased upward, because `E[z]/E[p]` is not `E[z/p]`. Two corrections are
in wide use and both are a multiplicative factor on the rate:

  | variant           | factor                              |
  | ----------------- | ----------------------------------- |
  | FC_CROSTON_CLASSIC| 1                                   |
  | FC_CROSTON_SBA    | `1 - alpha_interval / 2`            |
  | FC_CROSTON_SBJ    | `1 - alpha_interval / (2 - alpha_interval)` |

SBJ's factor is ZERO at `alpha_interval = 1` and negative above it. A factor of zero turns
every forecast into 0.0 under a success status — a rate estimate that says "no demand ever"
for a series that plainly has demand — so a non-positive factor is FC_ERR_PARAM_RANGE with no
forecast, and `bias_factor` is reported on every success so the correction applied is visible
rather than folded silently into the number.

The absences, per Rule 4
------------------------
  * A series with NO positive demand has no demand rate. There are no interval observations to
    smooth, so `p` does not exist and `z / p` does not either. That is FC_ERR_NO_DEMAND with
    `has_forecast = False` and an EMPTY path — not 0.0. Zero is the single most dangerous
    answer available here, because it is indistinguishable from a rate that was estimated and
    came out zero, and a reorder policy branches on exactly that difference.
  * Demand cannot be negative. A negative value makes the interval decomposition meaningless
    (is it an occurrence?) and would let a smoothed size go negative, so it is
    FC_ERR_NEGATIVE_VALUES rather than being treated as a return or clipped to zero.
  * A CV-squared needs two demand observations; a classification needs both statistics. With
    fewer, `has_cv2` is False and the class is FC_DEMAND_UNCLASSIFIED, which is a real category
    and not a fourth quadrant.

Status codes 300-319 via `forecasting.contract`; no table here.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_forecasting_intermittent.mojo
benchmark: benchmarks/mojo_benchmarks/bench_forecasting.mojo
docs: none
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from stats import compute_mean, compute_variance

from forecasting.contract import (
    FC_ERR_METHOD,
    FC_ERR_NEGATIVE_VALUES,
    FC_ERR_NON_FINITE,
    FC_ERR_NO_DEMAND,
    FC_ERR_PARAM_RANGE,
    FC_METHOD_CROSTON,
    FC_OK,
    _fc_ses_level,
    fc_finite,
    fc_horizon_defect,
    fc_series_defect,
    fc_smoothing_defect,
    fc_status_name,
)

comptime FC_CROSTON_CLASSIC: Int = 0
comptime FC_CROSTON_SBA: Int = 1
comptime FC_CROSTON_SBJ: Int = 2

# The Syntetos-Boylan-Croston quadrant cuts, from the paper that defined them. They are
# CONVENTIONS, not derived constants, which is why they are named and reported rather than
# inlined at the comparison: a caller who disagrees can read `adi` and `cv2` and cut them
# elsewhere, and a caller who accepts them gets the same boundary every time.
comptime FC_ADI_CUT: Float64 = 1.32
comptime FC_CV2_CUT: Float64 = 0.49

comptime FC_DEMAND_UNCLASSIFIED: Int = -1
comptime FC_DEMAND_SMOOTH: Int = 0
comptime FC_DEMAND_ERRATIC: Int = 1
comptime FC_DEMAND_INTERMITTENT: Int = 2
comptime FC_DEMAND_LUMPY: Int = 3


@fieldwise_init
struct IntermittentForecast(Copyable, Movable):
    """A per-period demand RATE, repeated over the horizon, plus the two levels behind it.

    `forecast[h-1]` is the expected demand in period `n + h`. It is a rate: it does not
    predict that period `n + h` will see that much demand, and for an intermittent series it
    will usually see either zero or several times the rate. That is the method working, not
    failing.

    `demand_level` is the smoothed size of a demand WHEN ONE OCCURS and `interval_level` the
    smoothed number of periods between occurrences, so `demand_level / interval_level *
    bias_factor` reproduces every element of `forecast` exactly. Both are reported because the
    rate alone cannot distinguish "large demands, rarely" from "small demands, often", and a
    stocking decision needs that distinction.

    On any refusal `forecast` is EMPTY, `has_forecast` is False and `has_levels` is False. The
    census fields (`n_periods`, `n_nonzero`, `n_zero`, `zero_fraction`) are still filled
    whenever the series was readable at all, because "there is no rate AND here is why" is
    strictly more useful than a bare status: `n_nonzero == 0` beside FC_ERR_NO_DEMAND is the
    complete explanation.
    """

    var status: Int
    var method_id: Int
    var variant: Int
    var horizon: Int
    var forecast: List[Float64]
    var has_forecast: Bool
    var demand_level: Float64
    var interval_level: Float64
    var has_levels: Bool
    var bias_factor: Float64
    var n_periods: Int
    var n_nonzero: Int
    var n_zero: Int
    var zero_fraction: Float64
    var status_name: String


@fieldwise_init
struct DemandProfile(Copyable, Movable):
    """The Syntetos-Boylan-Croston demand classification, with both statistics exposed.

    `adi` is the average inter-demand interval and `cv2` the squared coefficient of variation
    of the demand SIZES (zeros excluded — including them would measure the intermittency
    twice, once in each statistic). The quadrant is `demand_class`:

        adi < 1.32 and cv2 < 0.49  -> SMOOTH        adi < 1.32 and cv2 >= 0.49 -> ERRATIC
        adi >= 1.32 and cv2 < 0.49 -> INTERMITTENT  adi >= 1.32 and cv2 >= 0.49 -> LUMPY

    `has_adi` and `has_cv2` are separate flags because the two statistics fail
    independently: one demand observation gives an interval but no variance. When either is
    absent `demand_class` is FC_DEMAND_UNCLASSIFIED (-1) — a distinct value, never a quadrant
    reached by treating a missing statistic as 0.0, which would classify every single-demand
    series as SMOOTH.

    INTERVAL CONVENTION, stated because it changes `adi`: the first interval is measured from
    the period BEFORE the series starts, so a demand in period 0 has interval 1. The
    alternative (dropping the first interval) discards the one observation that says how long
    the series waited for its first demand, and makes `adi` undefined for a series with
    exactly one demand.
    """

    var status: Int
    var n_periods: Int
    var n_nonzero: Int
    var n_zero: Int
    var zero_fraction: Float64
    var adi: Float64
    var has_adi: Bool
    var cv2: Float64
    var has_cv2: Bool
    var mean_demand: Float64
    var has_mean_demand: Bool
    var demand_class: Int
    var class_name: String
    var status_name: String


@fieldwise_init
struct _DemandEvents(Copyable, Movable):
    """The two derived series a Croston-family method actually smooths.

    `sizes[j]` is the j-th positive demand and `intervals[j]` how many periods since the
    previous one (see the interval convention on `DemandProfile`). Both have length
    `n_nonzero`, so a single traversal produces a matched pair and no later code has to
    re-scan for occurrences.
    """

    var sizes: List[Float64]
    var intervals: List[Float64]


def _demand_events(y: List[Float64]) -> _DemandEvents:
    """Split a demand series into positive sizes and inter-demand intervals. O(n)."""
    var sizes = List[Float64]()
    var intervals = List[Float64]()
    var previous = -1
    for t in range(len(y)):
        if y[t] > 0.0:
            sizes.append(y[t])
            intervals.append(Float64(t - previous))
            previous = t
    return _DemandEvents(sizes^, intervals^)


def _bias_factor(variant: Int, alpha_interval: Float64) -> Float64:
    """The variant's multiplicative correction, or -1.0 for an unknown variant.

    -1.0 rather than 1.0 for the unknown case: 1.0 is the CLASSIC factor, so defaulting to it
    would silently answer a variant nobody asked for. A negative factor cannot be a
    correction, so the caller's check for it is the same check that rejects SBJ at
    `alpha_interval >= 1`.
    """
    if variant == FC_CROSTON_CLASSIC:
        return 1.0
    if variant == FC_CROSTON_SBA:
        return 1.0 - 0.5 * alpha_interval
    if variant == FC_CROSTON_SBJ:
        var denom = 2.0 - alpha_interval
        if denom <= 0.0:
            return -1.0
        return 1.0 - alpha_interval / denom
    return -1.0


def croston_variant_name(variant: Int) -> String:
    """Name for a Croston variant id. Unknown ids are named, not defaulted."""
    if variant == FC_CROSTON_CLASSIC:
        return "croston"
    if variant == FC_CROSTON_SBA:
        return "syntetos_boylan_approximation"
    if variant == FC_CROSTON_SBJ:
        return "shale_boylan_johnston"
    return "unknown"


def demand_class_name(demand_class: Int) -> String:
    """Name for a demand class. FC_DEMAND_UNCLASSIFIED is a real answer with a real name."""
    if demand_class == FC_DEMAND_SMOOTH:
        return "smooth"
    if demand_class == FC_DEMAND_ERRATIC:
        return "erratic"
    if demand_class == FC_DEMAND_INTERMITTENT:
        return "intermittent"
    if demand_class == FC_DEMAND_LUMPY:
        return "lumpy"
    if demand_class == FC_DEMAND_UNCLASSIFIED:
        return "unclassified"
    return "unknown"


def _no_intermittent(
    status: Int, variant: Int, horizon: Int, n_periods: Int, n_nonzero: Int
) -> IntermittentForecast:
    """A refusal that still carries the census, because the census IS the explanation."""
    var zeros = n_periods - n_nonzero
    var fraction = 0.0
    if n_periods > 0:
        fraction = Float64(zeros) / Float64(n_periods)
    return IntermittentForecast(
        status, FC_METHOD_CROSTON, variant, horizon, List[Float64](), False,
        0.0, 0.0, False, 0.0, n_periods, n_nonzero, zeros, fraction,
        fc_status_name(status),
    )


def croston_forecast(
    y: List[Float64], alpha_demand: Float64, alpha_interval: Float64,
    variant: Int, horizon: Int
) -> IntermittentForecast:
    """Croston / SBA / SBJ per-period demand rate over `horizon` periods.

    `rate = bias_factor * SES(sizes, alpha_demand) / SES(intervals, alpha_interval)`, both
    smoothings being the frozen `series.exponential_forecast` reached through
    `contract._fc_ses_level`.

    Worked example, hand-computable and asserted in the suite —
    `y = [0, 0, 5, 0, 0, 0, 10, 0, 3]` gives sizes `[5, 10, 3]` and intervals `[3, 4, 2]`. At
    `alpha_demand = alpha_interval = 1` the levels are the last observations, 3 and 2, so the
    classic rate is 1.5. At `alpha = 0.5` the levels are 5.25 and 2.75 and the rate is
    5.25/2.75 = 1.9090909...; the SBA factor at that alpha is 0.75, giving 1.4318181....

    Refuses, per Rule 4: an empty or non-finite series; a NEGATIVE value; a series with no
    positive demand at all (FC_ERR_NO_DEMAND — there is no interval to smooth, so no rate
    exists, and 0.0 would be indistinguishable from an estimated zero); an unknown variant;
    a non-positive bias factor; a non-positive smoothed interval (impossible from real
    intervals, which are all at least 1, and therefore evidence of a defect rather than a
    number to divide by).

    @capability croston_forecast
    complexity: O(n + horizon)
    counts:
    - dim horizon [kernel_validated]
    @endcapability
    """
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect != FC_OK:
        return _no_intermittent(defect, variant, horizon, n, 0)
    defect = fc_horizon_defect(n, horizon)
    if defect != FC_OK:
        return _no_intermittent(defect, variant, horizon, n, 0)
    defect = fc_smoothing_defect(alpha_demand)
    if defect != FC_OK:
        return _no_intermittent(defect, variant, horizon, n, 0)
    defect = fc_smoothing_defect(alpha_interval)
    if defect != FC_OK:
        return _no_intermittent(defect, variant, horizon, n, 0)
    for t in range(n):
        if y[t] < 0.0:
            return _no_intermittent(FC_ERR_NEGATIVE_VALUES, variant, horizon, n, 0)

    var events = _demand_events(y)
    var k = len(events.sizes)
    if k == 0:
        return _no_intermittent(FC_ERR_NO_DEMAND, variant, horizon, n, 0)

    # The variant is checked BEFORE the factor, so "I do not know this variant" and "this
    # variant's correction annihilates the forecast" stay two statuses rather than one. Folding
    # them would make an unknown id look like a parameter problem.
    if (
        variant != FC_CROSTON_CLASSIC
        and variant != FC_CROSTON_SBA
        and variant != FC_CROSTON_SBJ
    ):
        return _no_intermittent(FC_ERR_METHOD, variant, horizon, n, k)
    var factor = _bias_factor(variant, alpha_interval)
    if not fc_finite(factor) or factor <= 0.0:
        return _no_intermittent(FC_ERR_PARAM_RANGE, variant, horizon, n, k)

    var size_level = _fc_ses_level(events.sizes, alpha_demand)
    var interval_level = _fc_ses_level(events.intervals, alpha_interval)
    if len(size_level) != 1 or len(interval_level) != 1:
        return _no_intermittent(FC_ERR_NON_FINITE, variant, horizon, n, k)
    if interval_level[0] <= 0.0:
        return _no_intermittent(FC_ERR_PARAM_RANGE, variant, horizon, n, k)

    var rate = factor * size_level[0] / interval_level[0]
    if not fc_finite(rate):
        return _no_intermittent(FC_ERR_NON_FINITE, variant, horizon, n, k)
    var path = List[Float64]()
    for _ in range(horizon):
        path.append(rate)

    var zeros = n - k
    return IntermittentForecast(
        FC_OK, FC_METHOD_CROSTON, variant, horizon, path^, True,
        size_level[0], interval_level[0], True, factor, n, k, zeros,
        Float64(zeros) / Float64(n), fc_status_name(FC_OK),
    )


def demand_classify(y: List[Float64]) -> DemandProfile:
    """Syntetos-Boylan-Croston quadrant, with ADI and CV-squared reported separately.

    `adi = mean(intervals)` via the frozen `stats.compute_mean`; `cv2 = var(sizes) /
    mean(sizes)^2` via `stats.compute_mean` and the frozen SAMPLE variance
    `stats.compute_variance`.

    Both moments are only ever called with `n = len(list)` and only after that length is
    known non-zero: `compute_mean(v, 0)` computes `0.0 / 0.0`, and a non-finite Float64 on the
    result path is a serialization defect that has been MEASURED to end the worker process —
    so the guard is not a style choice.

    A series with no positive demand yields FC_ERR_NO_DEMAND: it has no demand sizes and no
    intervals, so neither statistic exists and no quadrant applies. A series with exactly one
    demand has an ADI and no CV (a sample variance of one observation is not zero, it is
    undefined), so `has_cv2` is False and the class is FC_DEMAND_UNCLASSIFIED.

    @capability demand_classify
    complexity: O(n)
    counts: none
    @endcapability
    """
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect != FC_OK:
        return DemandProfile(
            defect, n, 0, 0, 0.0, 0.0, False, 0.0, False, 0.0, False,
            FC_DEMAND_UNCLASSIFIED, demand_class_name(FC_DEMAND_UNCLASSIFIED),
            fc_status_name(defect),
        )
    for t in range(n):
        if y[t] < 0.0:
            return DemandProfile(
                FC_ERR_NEGATIVE_VALUES, n, 0, 0, 0.0, 0.0, False, 0.0, False, 0.0, False,
                FC_DEMAND_UNCLASSIFIED, demand_class_name(FC_DEMAND_UNCLASSIFIED),
                fc_status_name(FC_ERR_NEGATIVE_VALUES),
            )

    var events = _demand_events(y)
    var k = len(events.sizes)
    var zeros = n - k
    var fraction = Float64(zeros) / Float64(n)
    if k == 0:
        return DemandProfile(
            FC_ERR_NO_DEMAND, n, 0, n, 1.0, 0.0, False, 0.0, False, 0.0, False,
            FC_DEMAND_UNCLASSIFIED, demand_class_name(FC_DEMAND_UNCLASSIFIED),
            fc_status_name(FC_ERR_NO_DEMAND),
        )

    var adi = compute_mean(events.intervals, k)
    var has_adi = fc_finite(adi) and adi > 0.0
    var mean_demand = compute_mean(events.sizes, k)
    var has_mean = fc_finite(mean_demand) and mean_demand > 0.0

    var cv2: Float64 = 0.0
    var has_cv2 = False
    if k >= 2 and has_mean:
        var variance = compute_variance(events.sizes, k, mean_demand)
        if fc_finite(variance) and variance >= 0.0:
            cv2 = variance / (mean_demand * mean_demand)
            has_cv2 = fc_finite(cv2)

    var demand_class = FC_DEMAND_UNCLASSIFIED
    if has_adi and has_cv2:
        if adi < FC_ADI_CUT:
            demand_class = FC_DEMAND_ERRATIC if cv2 >= FC_CV2_CUT else FC_DEMAND_SMOOTH
        else:
            demand_class = FC_DEMAND_LUMPY if cv2 >= FC_CV2_CUT else FC_DEMAND_INTERMITTENT

    return DemandProfile(
        FC_OK, n, k, zeros, fraction, adi if has_adi else 0.0, has_adi,
        # `cv2` was passed RAW while its two neighbours on this same line were gated. When
        # `has_cv2` is False the value is a nan or +/-inf, and `demand_class` above has already
        # been decided without it -- so the report carried an unserializable number in a slot the
        # caller was told to ignore. Same discipline as `adi` and `mean_demand`: absence is the
        # flag, and the slot stays representable.
        cv2 if has_cv2 else 0.0, has_cv2, mean_demand if has_mean else 0.0, has_mean,
        demand_class, demand_class_name(demand_class), fc_status_name(FC_OK),
    )
