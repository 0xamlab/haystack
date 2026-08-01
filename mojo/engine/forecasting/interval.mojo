"""
forecasting.interval — prediction bands from BACKTEST residuals. Zero Python imports.

Where the uncertainty comes from
--------------------------------
A prediction interval is only as honest as the errors it was built from. These drivers take the
`error` matrix produced by `forecasting.backtest.backtest_flat` — out-of-sample residuals, one
row per rolling origin — and turn it into a band around a point forecast. No distributional
assumption is made anywhere: there is no normal quantile, no fitted sigma and no analytic
variance formula. The band is the empirical spread of errors the method actually made at that
lead time.

PER LEAD TIME, never pooled
---------------------------
Step `h`'s band is built from column `h` of the error matrix: one residual per origin, all at
lead time `h + 1`. Pooling lead times would mix one-step and h-step uncertainty, which grow at
different rates, and produce a band that is too wide near and too narrow far — wrong in both
directions at once and looking reasonable on average. `backtest.backtest_residuals_at_step`
extracts the column and is called here rather than re-implemented.

ESTIMABILITY IS THE RULE-4 CASE, and the bootstrap does not change it
--------------------------------------------------------------------
A two-sided band at level `L` needs the `(1-L)/2` and `(1+L)/2` quantiles. The smallest nonzero
tail probability `k` order statistics can express is `1/k`, so the band needs
`k >= 2 / (1 - L)` residuals: 40 for 95%, 20 for 90%, 200 for 99%
(`contract.fc_min_samples_for_level`). Below that, the "95% interval" is the min and max of a
handful of numbers wearing a confidence label — a confident wrong answer, and downstream code
branches on the width.

So a step with too few residuals gets `has_interval[h] = False` and `n_residuals[h]` reporting
the count, and if NO step is estimable the whole call is FC_ERR_NO_RESIDUALS with empty lists.
`lower` and `upper` are 0.0 at a non-estimable step: PADDING, not a zero-width band, and only
meaningful where `has_interval[h]` is True. `n_steps_covered` counts the steps that got one.

**The bootstrap is gated on the ORIGINAL residual count, not on `n_draws`.** Drawing 10,000
resamples from 6 residuals produces a beautifully smooth distribution supported on those same
six values; the 2.5% quantile of it is still an order statistic of six numbers. A bootstrap
cannot manufacture information the sample does not contain, and letting `n_draws` satisfy the
estimability test would turn this driver into a machine for laundering small samples into
tight-looking bands. It is the same gate on both paths.

Determinism
-----------
`interval_bootstrap_flat` is the only sampled surface in `forecasting/`. It draws through the
frozen `determinism.sampling_keyed.bootstrap_keyed`, which sits on
`determinism/counter_rng`'s Philox4x64-10 counter-based generator: a draw is a pure function of
its coordinates, so it does not depend on what was drawn before it, in what order, or on which
machine. `random_float64` and `seed(` appear nowhere in this package.

Coordinates: horizon step `h` uses `draw_index = h * n_draws`, so each step owns a contiguous
block of the counter space and no two steps share a draw. `master_seed = seed` and
`stream = stream` come from the caller. Consequences the suite asserts: the same `(seed, stream,
n_draws)` gives a BIT-IDENTICAL band; a different seed gives a different one; and the band does
not change if the steps are computed in a different order, because nothing is sequential.

`IntervalBand.rng_version` carries `counter_rng.rng_version()` back, so a stored band names the
generator that produced it. A band that changed between runs could not be used in a decision
that has to be explained.

What a band from this file does NOT claim
----------------------------------------
It is the empirical spread of the errors this method made on THIS series over the origins the
backtest ran. It is not a probability statement about the future, it inherits every bias the
backtest had, and its own sampling error is of order `1/sqrt(k)` in the tails. Coverage is a
measurable property, so `interval_coverage_flat` measures it rather than asserting it — a band
labelled 95% that covers 62% of held-out actuals is a fact worth having, and it is the only way
to find out.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: optional
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_forecasting_interval.mojo
benchmark: benchmarks/mojo_benchmarks/bench_forecasting.mojo
docs: none
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from determinism.counter_rng import rng_version
from determinism.sampling_keyed import bootstrap_keyed

from forecasting.backtest import backtest_residuals_at_step
from forecasting.contract import (
    FC_ERR_EMPTY_SERIES,
    FC_ERR_LENGTH_MISMATCH,
    FC_ERR_LEVEL_RANGE,
    FC_ERR_NON_FINITE,
    FC_ERR_NO_RESIDUALS,
    FC_ERR_PARAM_RANGE,
    FC_ERR_SEED_RANGE,
    FC_ERR_WORK_BUDGET,
    FC_INTERVAL_BOOTSTRAP,
    FC_INTERVAL_EMPIRICAL,
    FC_MAX_QUANTILE_SAMPLES,
    FC_MAX_QUANTILE_WORK,
    FC_OK,
    fc_all_finite,
    fc_cells_fit,
    fc_finite,
    fc_level_defect,
    fc_min_samples_for_level,
    fc_quantile_of,
    fc_status_name,
    fc_work_fits,
)



@fieldwise_init
struct IntervalBand(Copyable, Movable):
    """A per-step prediction band, with per-step presence and per-step sample sizes.

    `center[h]`, `lower[h]`, `upper[h]` describe horizon step `h + 1`. `center` echoes the point
    forecast the caller supplied, so the band travels with the number it brackets.

    `has_interval[h]` IS THE AUTHORITY. Where it is False, `lower[h]` and `upper[h]` are 0.0 as
    padding and mean nothing — not a zero-width interval, not a point estimate.
    `n_residuals[h]` says how many residuals that step had and
    `min_residuals_required` how many it needed, so a caller can see exactly why a step is
    missing and what would fix it. `n_steps_covered` is how many steps got a band.

    `method_id` is `FC_INTERVAL_EMPIRICAL` (100) or `FC_INTERVAL_BOOTSTRAP` (101), allocated in
    `forecasting.contract` out of the INTERVAL range (100-101) rather than in this file. It
    used to be 0 and 1 numbered here, which made `IntervalBand.method_id == 0` indistinguishable
    from `FC_METHOD_NAIVE` and from `hierarchy`'s `HIER_BOTTOM_UP` — three meanings for one
    number in one package. `contract.fc_method_name(method_id)` names it and
    `contract.fc_method_family(method_id)` returns `"interval"`, so a bare id on a wire, in a
    log or in a stored report says which vocabulary it belongs to without the struct around it.

    `seed`, `stream`, `draws_per_step` and `rng_version` are 0 / 0 / 0 / the generator id on the
    empirical path, which draws nothing. On the bootstrap path they name the exact draws that
    produced the band, which is what makes it reproducible from the report alone.

    On any refusal every list is empty and `n_steps_covered` is 0.
    """

    var status: Int
    var method_id: Int
    var horizon: Int
    var n_origins: Int
    var level: Float64
    var min_residuals_required: Int
    var center: List[Float64]
    var lower: List[Float64]
    var upper: List[Float64]
    var has_interval: List[Bool]
    var n_residuals: List[Int]
    var n_steps_covered: Int
    var draws_per_step: Int
    var seed: Int
    var stream: Int
    var rng_version: String
    var status_name: String


@fieldwise_init
struct CoverageReport(Copyable, Movable):
    """Measured coverage of a band against held-out actuals, with the misses split by side.

    `coverage` is `n_covered / (n_points - n_degenerate)` — the fraction of the points the audit
    could actually JUDGE that satisfied `lower <= actual <= upper`. Dividing by `n_points` would
    charge a corrupt band's rows against the forecast's coverage.
    `n_below` / `n_above` say which side the misses fell on. The split matters: 5% missing
    entirely above is a band that is biased low, while 2.5% each side is a band that is simply
    a little narrow, and the single coverage figure cannot tell those apart.

    `has_coverage` is False for an empty comparison. A coverage of 0.0 over zero points is not
    0% coverage, it is no measurement, and 0.0 cannot express both.

    `n_degenerate` counts points whose supplied band had `lower > upper` — an impossible band.
    Those points are NOT counted as covered and NOT counted as misses, because a broken band is
    not evidence about the forecast; they are reported so a caller cannot mistake a corrupt
    input for poor coverage.
    """

    var status: Int
    var n_points: Int
    var n_covered: Int
    var n_below: Int
    var n_above: Int
    var n_degenerate: Int
    var coverage: Float64
    var has_coverage: Bool
    var status_name: String


fn _no_band(
    status: Int, method_id: Int, horizon: Int, n_origins: Int, level: Float64,
    required: Int, draws: Int, seed: Int, stream: Int
) -> IntervalBand:
    """A refusal: no band anywhere, and the configuration echoed so the caller can fix it."""
    return IntervalBand(
        status, method_id, horizon, n_origins, level, required,
        List[Float64](), List[Float64](), List[Float64](), List[Bool](),
        List[Int](), 0, draws, seed, stream, rng_version(), fc_status_name(status),
    )


fn _band_input_defect(
    error: List[Float64], n_origins: Int, horizon: Int,
    point: List[Float64], level: Float64
) -> Int:
    """Every shape and range condition both band drivers share. One definition, two callers.

    Checks, in the order a caller most needs distinguished: the level (before any tolerance or
    quantile probability is derived from it), the cell shape via `contract.fc_cells_fit` (a
    DIVISION — `n_origins * horizon == len(error)` is a wrapping multiply and therefore not a
    bound), `len(point) == horizon`, finiteness of both arrays, and the O(k^2) quantile work
    charged against `FC_MAX_QUANTILE_WORK` with EVERY factor counted (`horizon * k * k`, formed
    by division).
    """
    if fc_level_defect(level) != FC_OK:
        return FC_ERR_LEVEL_RANGE
    if horizon < 1 or n_origins < 1:
        return FC_ERR_PARAM_RANGE
    if len(error) == 0:
        return FC_ERR_EMPTY_SERIES
    if not fc_cells_fit(n_origins, horizon, len(error)):
        return FC_ERR_LENGTH_MISMATCH
    if len(point) != horizon:
        return FC_ERR_LENGTH_MISMATCH
    if not fc_all_finite(error) or not fc_all_finite(point):
        return FC_ERR_NON_FINITE
    if n_origins > FC_MAX_QUANTILE_SAMPLES:
        return FC_ERR_WORK_BUDGET
    if not fc_work_fits(n_origins, n_origins, FC_MAX_QUANTILE_WORK):
        return FC_ERR_WORK_BUDGET
    if not fc_work_fits(horizon, n_origins * n_origins, FC_MAX_QUANTILE_WORK):
        return FC_ERR_WORK_BUDGET
    return FC_OK


fn _assemble(
    center: List[Float64], lower: List[Float64], upper: List[Float64],
    has_interval: List[Bool], n_residuals: List[Int], covered: Int,
    method_id: Int, horizon: Int, n_origins: Int, level: Float64,
    required: Int, draws: Int, seed: Int, stream: Int
) -> IntervalBand:
    """Finish a band, or turn "not one estimable step" into FC_ERR_NO_RESIDUALS.

    A band in which every step is absent is not a band. Returning it under FC_OK would make the
    caller responsible for noticing that `n_steps_covered == 0`, and the whole point of a status
    is that they do not have to.
    """
    if covered == 0:
        return _no_band(
            FC_ERR_NO_RESIDUALS, method_id, horizon, n_origins, level,
            required, draws, seed, stream,
        )
    return IntervalBand(
        FC_OK, method_id, horizon, n_origins, level, required,
        center.copy(), lower.copy(), upper.copy(), has_interval.copy(),
        n_residuals.copy(), covered, draws, seed, stream, rng_version(),
        fc_status_name(FC_OK),
    )


fn interval_empirical_flat(
    error: List[Float64], n_origins: Int, horizon: Int,
    point: List[Float64], level: Float64
) -> IntervalBand:
    """Empirical prediction band: the residual quantiles at each lead time, added to `point`.

    `error` is the row-major `n_origins x horizon` matrix from `backtest_flat` and holds
    `actual - forecast`, so `point[h] + quantile_of(column h)` is the band directly — no sign
    flip, no re-centring, and no assumption that the residuals have mean zero. If the method is
    biased at lead time 3, step 3's band is shifted, which is correct: the interval should
    contain the future value, not be symmetric about a forecast that is known to be off.

    Quantiles come from `contract.fc_quantile_of`, i.e. the frozen `risk.value_at_risk`, so this
    package has ONE definition of an empirical quantile.

    A step with fewer than `fc_min_samples_for_level(level)` residuals gets no band — see the
    module docstring. A step whose two quantiles come back in the wrong order (impossible from a
    monotone quantile, therefore evidence of a defect) also gets no band rather than an inverted
    one: two mutually exclusive claims in one returned value means a caller can use neither.

    @capability interval_empirical_flat
    complexity: O(horizon * n_origins^2)
    counts:
    - n_origins * horizon == len(error) [kernel_validated]
    @endcapability
    """
    var required = fc_min_samples_for_level(level)
    var defect = _band_input_defect(error, n_origins, horizon, point, level)
    if defect != FC_OK:
        return _no_band(
            defect, FC_INTERVAL_EMPIRICAL, horizon, n_origins, level, required, 0, 0, 0
        )
    if required < 1:
        return _no_band(
            FC_ERR_LEVEL_RANGE, FC_INTERVAL_EMPIRICAL, horizon, n_origins,
            level, required, 0, 0, 0,
        )

    var lower_p = 0.5 * (1.0 - level)
    var upper_p = 1.0 - lower_p
    var center = List[Float64]()
    var lower = List[Float64]()
    var upper = List[Float64]()
    var has_interval = List[Bool]()
    var counts = List[Int]()
    var covered = 0

    for h in range(horizon):
        var column = backtest_residuals_at_step(error, n_origins, horizon, h)
        var k = len(column)
        center.append(point[h])
        counts.append(k)
        if k < required:
            lower.append(0.0)
            upper.append(0.0)
            has_interval.append(False)
            continue
        var low = fc_quantile_of(column, lower_p)
        var high = fc_quantile_of(column, upper_p)
        if not low.has_value or not high.has_value or low.value > high.value:
            lower.append(0.0)
            upper.append(0.0)
            has_interval.append(False)
            continue
        var lo = point[h] + low.value
        var hi = point[h] + high.value
        if not fc_finite(lo) or not fc_finite(hi) or lo > hi:
            lower.append(0.0)
            upper.append(0.0)
            has_interval.append(False)
            continue
        lower.append(lo)
        upper.append(hi)
        has_interval.append(True)
        covered += 1

    return _assemble(
        center, lower, upper, has_interval, counts, covered,
        FC_INTERVAL_EMPIRICAL, horizon, n_origins, level, required, 0, 0, 0,
    )


fn interval_bootstrap_flat(
    error: List[Float64], n_origins: Int, horizon: Int, point: List[Float64],
    level: Float64, n_draws: Int, seed: Int, stream: Int
) -> IntervalBand:
    """Seeded-bootstrap prediction band: resample each lead time's residuals, then quantile.

    Step `h` resamples its residual column WITH REPLACEMENT through the frozen
    `determinism.sampling_keyed.bootstrap_keyed` at coordinates
    `(master_seed = seed, stream = stream, draw_index = h * n_draws)`, so every step owns a
    disjoint block of the Philox counter space and the whole band is a pure function of
    `(error, point, level, n_draws, seed, stream)`. The same arguments give a bit-identical
    band; the suite asserts that, and asserts that a different seed gives a different one.

    The estimability gate is on the ORIGINAL column length, not on `n_draws` — see the module
    docstring. A bootstrap smooths an estimate; it does not add information.

    `seed` and `stream` are non-negative `Int`s (converted to the generator's `UInt64`
    coordinates internally). A negative value is FC_ERR_SEED_RANGE rather than being wrapped:
    `UInt64(-1)` is a perfectly good coordinate, so wrapping would silently accept two different
    seeds that a caller believes are different and get one that they cannot reconstruct from the
    report.

    @capability interval_bootstrap_flat
    complexity: O(horizon * n_draws^2)
    counts:
    - n_origins * horizon == len(error) [kernel_validated]
    - dim n_draws [kernel_validated]
    @endcapability
    """
    var required = fc_min_samples_for_level(level)
    var defect = _band_input_defect(error, n_origins, horizon, point, level)
    if defect != FC_OK:
        return _no_band(
            defect, FC_INTERVAL_BOOTSTRAP, horizon, n_origins, level, required,
            n_draws, seed, stream,
        )
    if required < 1:
        return _no_band(
            FC_ERR_LEVEL_RANGE, FC_INTERVAL_BOOTSTRAP, horizon, n_origins, level,
            required, n_draws, seed, stream,
        )
    if seed < 0 or stream < 0:
        return _no_band(
            FC_ERR_SEED_RANGE, FC_INTERVAL_BOOTSTRAP, horizon, n_origins, level,
            required, n_draws, seed, stream,
        )
    if n_draws < 1:
        return _no_band(
            FC_ERR_PARAM_RANGE, FC_INTERVAL_BOOTSTRAP, horizon, n_origins, level,
            required, n_draws, seed, stream,
        )
    # Both quantiles are read from `resample`, whose length is `n_draws` -- NOT from `column`,
    # whose length `k` is what the estimability gate below tests. So `required` has to bind
    # `n_draws` too, and this module's whole argument is that it must bind the SMALLER of the two.
    #
    # The docstring warns at length against letting `n_draws` SATISFY the gate ("a machine for
    # laundering small samples into tight-looking bands") and the suite asserts that direction: 5
    # residuals with 4000 draws is refused. The mirror was open and untested. MEASURED with 40
    # residuals (-20..19), horizon 1, point [100.0], level 0.95, seed 7, stream 0:
    #   n_draws = 1  -> status FC_OK, has_interval True, n_residuals 40, min_residuals_required 40,
    #                   lower == upper == 116.0  -- a ZERO-WIDTH 95% prediction interval
    #   n_draws = 2  -> [111.125, 115.875], width 4.75
    #   correct empirical band                  -> [80.975, 118.025], width 37.05
    # The report advertised that the requirement was met, and `lo > hi` is false at zero width so
    # the self-consistency guard passed it. Everything downstream branches on band width.
    if n_draws < required:
        return _no_band(
            FC_ERR_PARAM_RANGE, FC_INTERVAL_BOOTSTRAP, horizon, n_origins, level,
            required, n_draws, seed, stream,
        )
    # Every factor of the O(horizon * n_draws^2) cost is charged, by division.
    if n_draws > FC_MAX_QUANTILE_SAMPLES:
        return _no_band(
            FC_ERR_WORK_BUDGET, FC_INTERVAL_BOOTSTRAP, horizon, n_origins, level,
            required, n_draws, seed, stream,
        )
    if not fc_work_fits(n_draws, n_draws, FC_MAX_QUANTILE_WORK):
        return _no_band(
            FC_ERR_WORK_BUDGET, FC_INTERVAL_BOOTSTRAP, horizon, n_origins, level,
            required, n_draws, seed, stream,
        )
    if not fc_work_fits(horizon, n_draws * n_draws, FC_MAX_QUANTILE_WORK):
        return _no_band(
            FC_ERR_WORK_BUDGET, FC_INTERVAL_BOOTSTRAP, horizon, n_origins, level,
            required, n_draws, seed, stream,
        )

    var lower_p = 0.5 * (1.0 - level)
    var upper_p = 1.0 - lower_p
    var center = List[Float64]()
    var lower = List[Float64]()
    var upper = List[Float64]()
    var has_interval = List[Bool]()
    var counts = List[Int]()
    var covered = 0

    for h in range(horizon):
        var column = backtest_residuals_at_step(error, n_origins, horizon, h)
        var k = len(column)
        center.append(point[h])
        counts.append(k)
        if k < required:
            lower.append(0.0)
            upper.append(0.0)
            has_interval.append(False)
            continue
        var draw_index = UInt64(h) * UInt64(n_draws)
        var resample = bootstrap_keyed(
            column, n_draws, UInt64(seed), UInt64(stream), draw_index
        )
        if len(resample) != n_draws:
            lower.append(0.0)
            upper.append(0.0)
            has_interval.append(False)
            continue
        var low = fc_quantile_of(resample, lower_p)
        var high = fc_quantile_of(resample, upper_p)
        if not low.has_value or not high.has_value or low.value > high.value:
            lower.append(0.0)
            upper.append(0.0)
            has_interval.append(False)
            continue
        var lo = point[h] + low.value
        var hi = point[h] + high.value
        if not fc_finite(lo) or not fc_finite(hi) or lo > hi:
            lower.append(0.0)
            upper.append(0.0)
            has_interval.append(False)
            continue
        lower.append(lo)
        upper.append(hi)
        has_interval.append(True)
        covered += 1

    return _assemble(
        center, lower, upper, has_interval, counts, covered,
        FC_INTERVAL_BOOTSTRAP, horizon, n_origins, level, required,
        n_draws, seed, stream,
    )


fn interval_coverage_flat(
    actual: List[Float64], lower: List[Float64], upper: List[Float64]
) -> CoverageReport:
    """MEASURED coverage of a band against held-out actuals, with the misses split by side.

    A band labelled 95% is a hypothesis, and this is the test. `lower <= actual <= upper` counts
    as covered, inclusive at both ends, because a quantile IS an observed value and excluding
    the endpoints would under-count coverage on small samples for no reason.

    A point whose supplied band has `lower > upper` is impossible; it is counted in
    `n_degenerate` and excluded from both the covered and the missed tallies, and it never turns
    into a "miss" that a caller would read as poor forecasting. See `CoverageReport` for the
    rest of the accounting.

    Refuses only on unequal lengths, an empty comparison or a non-finite input. `coverage` is
    absent for an empty comparison rather than 0.0, which would read as 0% coverage.

    @capability interval_coverage_flat
    complexity: O(n)
    counts: none
    @endcapability
    """
    var n = len(actual)
    if n != len(lower) or n != len(upper):
        return CoverageReport(
            FC_ERR_LENGTH_MISMATCH, n, 0, 0, 0, 0, 0.0, False,
            fc_status_name(FC_ERR_LENGTH_MISMATCH),
        )
    if n == 0:
        return CoverageReport(
            FC_ERR_EMPTY_SERIES, 0, 0, 0, 0, 0, 0.0, False,
            fc_status_name(FC_ERR_EMPTY_SERIES),
        )
    if not fc_all_finite(actual) or not fc_all_finite(lower) or not fc_all_finite(upper):
        return CoverageReport(
            FC_ERR_NON_FINITE, n, 0, 0, 0, 0, 0.0, False,
            fc_status_name(FC_ERR_NON_FINITE),
        )
    var covered = 0
    var below = 0
    var above = 0
    var degenerate = 0
    for i in range(n):
        if lower[i] > upper[i]:
            degenerate += 1
            continue
        if actual[i] < lower[i]:
            below += 1
        elif actual[i] > upper[i]:
            above += 1
        else:
            covered += 1
    var judged = n - degenerate
    var fraction: Float64 = 0.0
    var has_coverage = False
    if judged > 0:
        fraction = Float64(covered) / Float64(judged)
        has_coverage = fc_finite(fraction)
    return CoverageReport(
        FC_OK, n, covered, below, above, degenerate, fraction, has_coverage,
        fc_status_name(FC_OK),
    )
