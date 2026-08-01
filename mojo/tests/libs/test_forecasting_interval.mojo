"""test_forecasting_interval.mojo — known-value tests for the prediction bands.

Hand-written. The residual matrix is constructed so that every quantile is a hand-computable
type-7 interpolation.

    40 origins x 2 steps.   step 0 residual at origin j is  j - 20   (so -20 .. 19)
                            step 1 residual at origin j is  2*(j-20)
    point forecast = [100, 200]

Column 0 sorted is -20..19, so the type-7 index for p is 39p:
    p = 0.025 -> index 0.975 -> -20 + 0.975 = -19.025      lower = 100 - 19.025 = 80.975
    p = 0.975 -> index 38.025 -> 18 + 0.025 = 18.025       upper = 100 + 18.025 = 118.025
Column 1 is exactly twice column 0, so its quantiles are exactly twice as far out:
    lower = 200 - 38.05 = 161.95      upper = 200 + 36.05 = 236.05
All four are asserted exactly, and each is also asserted equal to
`point[h] + fc_quantile_of(column, p).value` computed here from the frozen quantile, so the band
is proven to be the frozen kernel plus the point forecast and nothing else.

Four properties beyond the arithmetic:

1. *Estimability, and the trap the bootstrap could hide.* A 95% band needs 40 residuals per
   step. With 5 it is FC_ERR_NO_RESIDUALS and every list is empty. Crucially the BOOTSTRAP path
   refuses the same 5-residual input even when asked for 4000 draws — a bootstrap smooths an
   estimate, it cannot manufacture information, and letting `n_draws` satisfy the gate would turn
   this driver into a machine for laundering small samples into tight-looking bands.

2. *Determinism, which is the premise.* The same `(seed, stream, n_draws)` must give a
   BIT-IDENTICAL band; a different seed and a different stream must both change it. Asserted on
   all four numbers of a 2-step band at once, because a single quantile of a discrete residual
   set often lands on the same value under two seeds and would make a broken generator look
   deterministic.

3. *Self-consistency.* `lower <= upper` at every step where `has_interval` is True. Two mutually
   exclusive claims in one returned value means a caller can use neither.

4. *Coverage is MEASURED.* A band labelled 95% is a hypothesis; `interval_coverage_flat` is the
   test. The misses are split by side (a band biased low and a band merely narrow are different
   diagnoses) and an impossible `lower > upper` row is counted in `n_degenerate` and excluded
   from BOTH tallies rather than being scored as a forecasting miss.
"""
from std.math import abs as fabs

from determinism.counter_rng import rng_version

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
    FC_INTERVAL_METHOD_MAX,
    FC_INTERVAL_METHOD_MIN,
    FC_MAX_QUANTILE_SAMPLES,
    FC_METHOD_MAX,
    FC_METHOD_NAIVE,
    FC_OK,
    HIER_BOTTOM_UP,
    fc_method_family,
    fc_method_name,
    fc_min_samples_for_level,
    fc_quantile_of,
)
from forecasting.interval import (
    IntervalBand,
    interval_bootstrap_flat,
    interval_coverage_flat,
    interval_empirical_flat,
)


fn _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _no_band(b: IntervalBand) -> Bool:
    """A refusal carries no band at all — no padded lists, no per-step flags."""
    return (
        b.status != FC_OK
        and len(b.lower) == 0
        and len(b.upper) == 0
        and len(b.center) == 0
        and len(b.has_interval) == 0
        and len(b.n_residuals) == 0
        and b.n_steps_covered == 0
    )


fn _same_band(a: IntervalBand, b: IntervalBand) -> Bool:
    """Bit equality of every number in two bands — the determinism assertion."""
    if len(a.lower) != len(b.lower) or len(a.upper) != len(b.upper):
        return False
    for h in range(len(a.lower)):
        if a.lower[h] != b.lower[h] or a.upper[h] != b.upper[h]:
            return False
        if a.has_interval[h] != b.has_interval[h]:
            return False
    return True


fn _band_differs(a: IntervalBand, b: IntervalBand) -> Bool:
    """At least one number differs. A single quantile can coincide under two seeds, so the
    whole band is compared rather than one endpoint."""
    if len(a.lower) != len(b.lower):
        return True
    for h in range(len(a.lower)):
        if a.lower[h] != b.lower[h] or a.upper[h] != b.upper[h]:
            return True
    return False


fn main():
    var passed = 0
    var failed = 0
    print("\n[forecasting.interval] known-value suite")

    var horizon = 2
    var origins = 40
    var error = List[Float64]()
    for j in range(origins):
        error.append(Float64(j) - 20.0)
        error.append(2.0 * (Float64(j) - 20.0))
    var point = _floats(100.0, 200.0)
    var column0 = List[Float64]()
    var column1 = List[Float64]()
    for j in range(origins):
        column0.append(Float64(j) - 20.0)
        column1.append(2.0 * (Float64(j) - 20.0))

    # ══ the empirical band, every endpoint hand-computed ═══════════════════════════
    var band = interval_empirical_flat(error, origins, horizon, point, 0.95)
    if (
        band.status == FC_OK
        and band.method_id == FC_INTERVAL_EMPIRICAL
        and band.n_steps_covered == 2
        and band.min_residuals_required == 40
        and band.n_residuals[0] == 40 and band.n_residuals[1] == 40
        and band.has_interval[0] and band.has_interval[1]
        and band.center[0] == 100.0 and band.center[1] == 200.0
        and band.lower[0] == 80.975 and band.upper[0] == 118.025
        and band.lower[1] == 161.95 and band.upper[1] == 236.05
    ):
        passed += 1
        print("  ✅ 95% band is [80.975, 118.025] and [161.95, 236.05], exactly as computed")
    else:
        failed += 1
        print("  ❌ empirical band wrong:", band.lower[0], band.upper[0], band.lower[1])

    # The band IS the frozen quantile plus the point forecast — proven, not assumed.
    var q_low0 = fc_quantile_of(column0, 0.025)
    var q_high0 = fc_quantile_of(column0, 0.975)
    var q_low1 = fc_quantile_of(column1, 0.025)
    var q_high1 = fc_quantile_of(column1, 0.975)
    if (
        q_low0.has_value and q_low0.value == -19.025
        and q_high0.has_value and q_high0.value == 18.025
        and band.lower[0] == point[0] + q_low0.value
        and band.upper[0] == point[0] + q_high0.value
        and band.lower[1] == point[1] + q_low1.value
        and band.upper[1] == point[1] + q_high1.value
        and q_low1.value == 2.0 * q_low0.value
    ):
        passed += 1
        print("  ✅ each endpoint is point[h] + the FROZEN residual quantile, bit for bit")
    else:
        failed += 1
        print("  ❌ the band is not the frozen quantile:", q_low0.value, band.lower[0])

    # Residuals are per LEAD TIME: column 1 is exactly twice column 0, so its band must be
    # exactly twice as wide. Pooling lead times would give both steps the same width.
    var width0 = band.upper[0] - band.lower[0]
    var width1 = band.upper[1] - band.lower[1]
    if width1 == 2.0 * width0 and width0 > 0.0:
        passed += 1
        print("  ✅ step 2's band is exactly twice step 1's — lead times are NOT pooled")
    else:
        failed += 1
        print("  ❌ widths pooled or wrong:", width0, width1)

    # Self-consistency: lower <= upper wherever the band exists.
    var ordered = True
    for h in range(len(band.lower)):
        if band.has_interval[h] and band.lower[h] > band.upper[h]:
            ordered = False
    if ordered and band.rng_version == rng_version():
        passed += 1
        print("  ✅ lower <= upper at every covered step; the generator id travels with it")
    else:
        failed += 1
        print("  ❌ band self-consistency broken")

    # ══ estimability, at three levels ═════════════════════════════════════════════
    # 90% needs 20 residuals: on a 20-residual column the type-7 5% index is 0.95, so
    # -10 + 0.95 = -9.05 and the band around 50 is [40.95, 58.05].
    var twenty = List[Float64]()
    for j in range(20):
        twenty.append(Float64(j) - 10.0)
    var band90 = interval_empirical_flat(twenty, 20, 1, _floats(50.0), 0.90)
    if (
        band90.status == FC_OK
        and band90.min_residuals_required == 20
        and band90.n_residuals[0] == 20
        and band90.lower[0] == 40.95
        and band90.upper[0] == 58.05
        and fc_min_samples_for_level(0.90) == 20
    ):
        passed += 1
        print("  ✅ a 90% band on exactly 20 residuals is [40.95, 58.05]")
    else:
        failed += 1
        print("  ❌ 90% band wrong:", band90.status, band90.lower[0], band90.upper[0])

    # 99% needs 200, so the same 40-residual matrix has no estimable step at all.
    var too_strict = interval_empirical_flat(error, origins, horizon, point, 0.99)
    var too_few = List[Float64]()
    for j in range(5):
        too_few.append(Float64(j))
        too_few.append(Float64(j))
    var short_band = interval_empirical_flat(too_few, 5, 2, point, 0.95)
    if (
        too_strict.status == FC_ERR_NO_RESIDUALS
        and _no_band(too_strict)
        and too_strict.min_residuals_required == 200
        and short_band.status == FC_ERR_NO_RESIDUALS
        and _no_band(short_band)
        and short_band.min_residuals_required == 40
    ):
        passed += 1
        print("  ✅ 40 residuals cannot support a 99% band, and 5 cannot support a 95% one")
    else:
        failed += 1
        print("  ❌ estimability gate wrong:", too_strict.status, short_band.status)

    # ══ the bootstrap does NOT launder a small sample ══════════════════════════════
    var laundered = interval_bootstrap_flat(too_few, 5, 2, point, 0.95, 4000, 1, 1)
    if (
        laundered.status == FC_ERR_NO_RESIDUALS
        and _no_band(laundered)
        and laundered.draws_per_step == 4000
    ):
        passed += 1
        print("  ✅ 4000 draws from 5 residuals is STILL refused — the gate is on the sample")
    else:
        failed += 1
        print("  ❌ the bootstrap laundered a 5-residual sample:", laundered.status)

    # ══ determinism: same seed bit-identical, different seed/stream different ══════
    var seeded_a = interval_bootstrap_flat(error, origins, horizon, point, 0.95, 300, 7, 3)
    var seeded_b = interval_bootstrap_flat(error, origins, horizon, point, 0.95, 300, 7, 3)
    var other_seed = interval_bootstrap_flat(error, origins, horizon, point, 0.95, 300, 8, 3)
    var other_stream = interval_bootstrap_flat(error, origins, horizon, point, 0.95, 300, 7, 9)
    if (
        seeded_a.status == FC_OK
        and seeded_a.n_steps_covered == 2
        and _same_band(seeded_a, seeded_b)
        and _band_differs(seeded_a, other_seed)
        and _band_differs(seeded_a, other_stream)
        and seeded_a.seed == 7 and seeded_a.stream == 3
        and seeded_a.draws_per_step == 300
        and seeded_a.rng_version == rng_version()
        and seeded_a.method_id == FC_INTERVAL_BOOTSTRAP
    ):
        passed += 1
        print("  ✅ same seed -> BIT-IDENTICAL band; a different seed or stream changes it")
    else:
        failed += 1
        print("  ❌ determinism broken:", _same_band(seeded_a, seeded_b),
              _band_differs(seeded_a, other_seed))

    # A resampled band must still be ordered, and must sit inside the residual range: the
    # bootstrap draws only values that are IN the sample, so it cannot exceed the extremes.
    var inside = True
    for h in range(len(seeded_a.lower)):
        if not seeded_a.has_interval[h]:
            continue
        if seeded_a.lower[h] > seeded_a.upper[h]:
            inside = False
        if seeded_a.lower[h] < point[h] - 40.0 or seeded_a.upper[h] > point[h] + 40.0:
            inside = False
    if inside:
        passed += 1
        print("  ✅ a bootstrap band is ordered and cannot leave the residual sample's range")
    else:
        failed += 1
        print("  ❌ bootstrap band left its own sample's range")

    # ══ the refusals ══════════════════════════════════════════════════════════════
    var nan = 0.0 / 0.0
    if (
        interval_empirical_flat(error, origins, horizon, point, 1.0).status
            == FC_ERR_LEVEL_RANGE
        and interval_empirical_flat(error, origins, horizon, point, 0.0).status
            == FC_ERR_LEVEL_RANGE
        and interval_empirical_flat(error, origins, horizon, point, nan).status
            == FC_ERR_LEVEL_RANGE
        and interval_empirical_flat(error, 5, horizon, point, 0.95).status
            == FC_ERR_LENGTH_MISMATCH
        and interval_empirical_flat(error, origins, horizon, _floats(1.0), 0.95).status
            == FC_ERR_LENGTH_MISMATCH
        and interval_empirical_flat(_floats(1.0, 2.0), 3, 6148914691236517206, point, 0.95).status
            == FC_ERR_LENGTH_MISMATCH
        and interval_empirical_flat(List[Float64](), 1, 1, _floats(1.0), 0.95).status
            == FC_ERR_EMPTY_SERIES
    ):
        passed += 1
        print("  ✅ level, shape and the WRAPPING product are all refused before any indexing")
    else:
        failed += 1
        print("  ❌ an input guard is missing")

    if (
        interval_bootstrap_flat(error, origins, horizon, point, 0.95, 300, -1, 0).status
            == FC_ERR_SEED_RANGE
        and interval_bootstrap_flat(error, origins, horizon, point, 0.95, 300, 0, -1).status
            == FC_ERR_SEED_RANGE
        and interval_bootstrap_flat(error, origins, horizon, point, 0.95, 0, 1, 1).status
            == FC_ERR_PARAM_RANGE
        and interval_bootstrap_flat(
            error, origins, horizon, point, 0.95, FC_MAX_QUANTILE_SAMPLES + 1, 1, 1
        ).status == FC_ERR_WORK_BUDGET
    ):
        passed += 1
        print("  ✅ a negative seed is refused, not wrapped; the draw budget is charged")
    else:
        failed += 1
        print("  ❌ seed / draw-budget guards wrong")

    # ══ coverage is measured, and a broken band is not a forecasting miss ══════════
    # actual 1 inside [0,2]; 5 above; -5 below; the fourth row has lower > upper.
    var actual = _floats(1.0, 5.0, -5.0, 1.0)
    var lower = _floats(0.0, 0.0, 0.0, 3.0)
    var upper = _floats(2.0, 2.0, 2.0, 2.0)
    var coverage = interval_coverage_flat(actual, lower, upper)
    if (
        coverage.status == FC_OK
        and coverage.n_points == 4
        and coverage.n_covered == 1
        and coverage.n_above == 1
        and coverage.n_below == 1
        and coverage.n_degenerate == 1
        and coverage.has_coverage
        and coverage.coverage == 1.0 / 3.0
    ):
        passed += 1
        print("  ✅ coverage 1/3 over the 3 JUDGED points; the impossible row is degenerate")
    else:
        failed += 1
        print("  ❌ coverage wrong:", coverage.n_covered, coverage.n_degenerate,
              coverage.coverage)

    # Inclusive at both ends: a quantile IS an observed value, so excluding the endpoints would
    # under-count coverage on small samples for no reason.
    var edge = interval_coverage_flat(_floats(0.0, 2.0), _floats(0.0, 0.0), _floats(2.0, 2.0))
    if (
        edge.n_covered == 2
        and edge.coverage == 1.0
        and interval_coverage_flat(actual, lower, _floats(1.0)).status
            == FC_ERR_LENGTH_MISMATCH
        and not interval_coverage_flat(actual, lower, _floats(1.0)).has_coverage
        and interval_coverage_flat(List[Float64](), List[Float64](), List[Float64]()).status
            == FC_ERR_EMPTY_SERIES
        and not interval_coverage_flat(
            List[Float64](), List[Float64](), List[Float64]()
        ).has_coverage
        and interval_coverage_flat(_floats(nan), _floats(0.0), _floats(1.0)).status
            == FC_ERR_NON_FINITE
    ):
        passed += 1
        print("  ✅ coverage is inclusive at the endpoints; nothing measured is ABSENT, not 0")
    else:
        failed += 1
        print("  ❌ coverage edge cases wrong:", edge.n_covered)

    # The band this suite computed, scored against the residual-shifted actuals it was built
    # from: a 95% empirical band over its OWN sample must cover at least 95% of it. That is a
    # sanity property of the construction, and it is checkable.
    var self_actual = List[Float64]()
    var self_lower = List[Float64]()
    var self_upper = List[Float64]()
    for j in range(origins):
        self_actual.append(point[0] + column0[j])
        self_lower.append(band.lower[0])
        self_upper.append(band.upper[0])
    var self_cov = interval_coverage_flat(self_actual, self_lower, self_upper)
    if (
        self_cov.status == FC_OK
        and self_cov.has_coverage
        and self_cov.coverage >= 0.95
        and self_cov.n_degenerate == 0
    ):
        passed += 1
        print("  ✅ the 95% band covers >= 95% of the very sample it was built from")
    else:
        failed += 1
        print("  ❌ in-sample coverage below the nominal level:", self_cov.coverage)

    # ══ THE MIRROR the docstring argued for and no assertion covered ══════════════
    # `required` gated `k` (the residual count) while both quantiles were read from `resample`,
    # whose length is `n_draws`. So plenty of residuals with too few draws walked straight
    # through. MEASURED before the gate was added, with these exact arguments:
    #   n_draws = 1 -> status FC_OK, has_interval True, n_residuals 40,
    #                  min_residuals_required 40, lower == upper == 116.0
    # A ZERO-WIDTH 95% prediction interval, reported as estimable. `lo > hi` is false at zero
    # width, so the self-consistency check passed it too.
    var starved = interval_bootstrap_flat(
        error, origins, horizon, point, 0.95, 1, 7, 0
    )
    if starved.status == FC_ERR_PARAM_RANGE and starved.n_steps_covered == 0:
        passed += 1
        print("  ✅ too few DRAWS is refused, not answered with a zero-width band")
    else:
        failed += 1
        print(
            "  ❌ n_draws=1 produced status",
            starved.status,
            "covered",
            starved.n_steps_covered,
        )

    # ...and the direction the suite already covered stays refused.
    var few_residuals = interval_bootstrap_flat(
        _floats(1.0, 2.0), 2, 1, _floats(100.0, 0.0), 0.95, 4000, 7, 0
    )
    if few_residuals.n_steps_covered == 0:
        passed += 1
        print("  ✅ many draws cannot launder too few residuals")
    else:
        failed += 1
        print("  ❌ draws laundered a short residual column")

    # ══ the method_id says WHICH vocabulary it is in ═══════════════════════════════
    # `IntervalBand.method_id` used to be 0 and 1, numbered in `interval.mojo` itself. So did
    # `Reconciliation.method_id` in `hierarchy.mojo`, and `FC_METHOD_NAIVE`/`FC_METHOD_DRIFT`
    # are 0 and 1 in the table both files import from: one number, three meanings, in one
    # package. The Mojo type kept them apart inside the process and nothing kept them apart in
    # a log line, a stored report or a flat `"method_id": 0` field.
    #
    # The interval ids now come out of the contract's INTERVAL range and the assertions below
    # are the ones that could not have held before: a band's id is OUTSIDE the forecasting
    # range, it names itself, and its family is "interval" rather than ambiguous.
    var bootstrap_band = interval_bootstrap_flat(
        error, origins, horizon, point, 0.95, 400, 11, 0
    )
    if (
        band.method_id == FC_INTERVAL_EMPIRICAL
        and bootstrap_band.method_id == FC_INTERVAL_BOOTSTRAP
        # Disjoint from the forecasting range, in both directions.
        and band.method_id > FC_METHOD_MAX
        and bootstrap_band.method_id > FC_METHOD_MAX
        and FC_INTERVAL_METHOD_MIN > FC_METHOD_MAX
        and band.method_id != FC_METHOD_NAIVE
        and band.method_id != HIER_BOTTOM_UP
        # ... and disjoint from the reconciliation range.
        and FC_INTERVAL_METHOD_MAX < HIER_BOTTOM_UP
        # A bare id names itself and its family without the struct around it.
        and fc_method_name(band.method_id) == "interval_empirical"
        and fc_method_name(bootstrap_band.method_id) == "interval_bootstrap"
        and fc_method_family(band.method_id) == "interval"
        and fc_method_family(bootstrap_band.method_id) == "interval"
        and fc_method_family(FC_METHOD_NAIVE) == "forecast"
        and fc_method_family(HIER_BOTTOM_UP) == "reconciliation"
        # Every code in the interval range is assigned; nothing beside it is.
        and FC_INTERVAL_METHOD_MIN == FC_INTERVAL_EMPIRICAL
        and FC_INTERVAL_METHOD_MAX == FC_INTERVAL_BOOTSTRAP
        and fc_method_name(FC_INTERVAL_METHOD_MIN - 1) == "unknown"
        and fc_method_name(FC_INTERVAL_METHOD_MAX + 1) == "unknown"
        # A refusal carries the id too, so the vocabulary survives the error path.
        and interval_empirical_flat(
            List[Float64](), 0, horizon, point, 0.95
        ).method_id
        == FC_INTERVAL_EMPIRICAL
        and interval_bootstrap_flat(
            List[Float64](), 0, horizon, point, 0.95, 400, 11, 0
        ).method_id
        == FC_INTERVAL_BOOTSTRAP
    ):
        passed += 1
        print("  ✅ the band's method_id is in the interval range, disjoint and self-naming")
    else:
        failed += 1
        print(
            "  ❌ interval method_id vocabulary:",
            band.method_id,
            fc_method_name(band.method_id),
            fc_method_family(band.method_id),
        )

    print("  [forecasting.interval] Passed:", passed, "Failed:", failed)
