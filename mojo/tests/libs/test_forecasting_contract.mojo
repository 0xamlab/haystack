"""test_forecasting_contract.mojo — known-value tests for the forecasting package vocabulary.

Hand-written. Every expected value below was derived on paper and is stated beside the
assertion.

Four things do the real work here, and they are the four that no downstream suite can check
for itself:

1. *The tolerance builders, against all four measured spellings of rule 4b.*
   `fc_tolerance(0, 0)` must be EXACTLY 0.0 — the `1 + |x|` spelling would return 1.4e-14 there,
   which is a "relative" tolerance that has silently become absolute. `fc_tolerance` must scale
   LINEARLY with the judged magnitude (doubling the magnitude doubles the tolerance, exactly,
   because 2 is a power of two). And it must NOT multiply the caller's tolerance by the
   magnitude: `fc_tolerance(1e9, 1e-6)` is about 1.5e-5, where the fourth spelling would give
   1e3 — a measured gap of 400,000,000 once reported `at_optimum = True` that way.

2. *`fc_cells_fit` on the wrapping multiply.* `3 * 6148914691236517206 == 2` is asserted here as
   a fact about the machine, and then `fc_cells_fit(3, 6148914691236517206, 2)` is asserted
   False. That exact shape walked past a `rows * cols != len` guard in a sibling package and
   aborted the worker; the division-based test is the fix and this is its regression.

3. *One integer, one meaning.* All twenty status codes 300-319 are checked to produce twenty
   DISTINCT names, and 299 / 320 to produce "unknown". `optimization.integer` and
   `optimization.explain` both claimed 80-84 and one integer acquired two meanings; a name
   collision here would be the same defect and nothing else would catch it.

4. *The empirical quantile IS the frozen kernel.* `fc_quantile_of(v, p).value` is asserted
   BIT-EQUAL to `-risk.value_at_risk(v, 1 - p)`, which is what proves this package added no
   second definition of a quantile, plus hand-computed type-7 values on 1..5.

`fc_min_samples_for_level` gets its own attention because it is a discrete threshold derived
from a floating division: `1 - 0.9` is 0.09999999999999998, so a bare `ceil(1/tail)` returns 21
for a 90% level and refuses a perfectly estimable 20-sample band. 0.90 -> 20 is asserted for
exactly that reason.
"""
from std.math import abs as fabs

from risk import value_at_risk
from sparse_numerics.csr import MAX_CSR_DIM

from forecasting.contract import (
    FC_DBL_EPSILON,
    FC_ERR_ALL_UNDEFINED,
    FC_ERR_DIMENSION_TOO_LARGE,
    FC_ERR_EMPTY_SERIES,
    FC_ERR_HIERARCHY_SHAPE,
    FC_ERR_HORIZON,
    FC_ERR_INCOHERENT,
    FC_ERR_INSUFFICIENT_HISTORY,
    FC_ERR_LENGTH_MISMATCH,
    FC_ERR_LEVEL_RANGE,
    FC_ERR_METHOD,
    FC_ERR_NEGATIVE_VALUES,
    FC_ERR_NON_FINITE,
    FC_ERR_NO_DEMAND,
    FC_ERR_NO_ORIGINS,
    FC_ERR_NO_RESIDUALS,
    FC_ERR_PARAM_RANGE,
    FC_ERR_PERIOD,
    FC_ERR_SEED_RANGE,
    FC_ERR_WORK_BUDGET,
    FC_INTERVAL_BOOTSTRAP,
    FC_INTERVAL_EMPIRICAL,
    FC_INTERVAL_METHOD_MAX,
    FC_INTERVAL_METHOD_MIN,
    FC_MAX_QUANTILE_SAMPLES,
    FC_MAX_SEASONAL_WORK,
    FC_METHOD_MAX,
    FC_METHOD_MIN,
    FC_METHOD_NAIVE,
    FC_OK,
    HIER_BOTTOM_UP,
    HIER_METHOD_MAX,
    HIER_METHOD_MIN,
    HIER_TOP_DOWN,
    FC_TOL_SLACK,
    MAX_FC_CELLS,
    MAX_FC_HORIZON,
    fc_all_finite,
    fc_ceilings,
    fc_cells_fit,
    fc_damping_defect,
    fc_finite,
    fc_horizon_defect,
    fc_level_defect,
    fc_method_family,
    fc_method_name,
    fc_min_samples_for_level,
    fc_period_defect,
    fc_quantile_of,
    fc_series_defect,
    fc_smoothing_defect,
    fc_status_name,
    fc_sum_tolerance,
    fc_tolerance,
    fc_work_fits,
)


fn _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn main():
    var passed = 0
    var failed = 0
    print("\n[forecasting.contract] known-value suite")

    var inf = 1.0 / 0.0
    var nan = 0.0 / 0.0

    # ══ rule 4b, spelling 3: a tolerance with a 1.0 floor is ABSOLUTE ═══════════════
    # fc_tolerance(0, 0) is exactly 0.0. The `1 + |x|` idiom would return 64*eps here, an
    # allowance of 1.4e-14 that the caller never asked for and that dominates whenever the
    # real scale is smaller than 1.
    if fc_tolerance(0.0, 0.0) == 0.0 and fc_tolerance(0.0, 0.25) == 0.25:
        passed += 1
        print("  ✅ fc_tolerance has NO 1.0 floor; the absolute term passes through exactly")
    else:
        failed += 1
        print("  ❌ fc_tolerance(0,0) =", fc_tolerance(0.0, 0.0), "expected 0.0")

    # Linear in the judged magnitude, and doubling is exact in binary floating point.
    # |quantity| is used, so the sign of the judged quantity cannot change the budget.
    if (
        fc_tolerance(2.0, 0.0) == 2.0 * fc_tolerance(1.0, 0.0)
        and fc_tolerance(-3.0, 0.0) == fc_tolerance(3.0, 0.0)
        and fc_tolerance(1.0, 0.0) == FC_TOL_SLACK * FC_DBL_EPSILON
    ):
        passed += 1
        print("  ✅ fc_tolerance is DBL_EPSILON x |the judged quantity|, exactly linear")
    else:
        failed += 1
        print("  ❌ fc_tolerance scaling wrong:", fc_tolerance(2.0, 0.0), fc_tolerance(1.0, 0.0))

    # ══ rule 4b, spelling 4: the caller's tolerance is never the RELATIVE multiplier ══
    # fc_tolerance(1e9, 1e-6) = 1e-6 + 64*eps*1e9 ~ 1.5e-5. Sizing the relative term by the
    # caller's tolerance instead of DBL_EPSILON would give 1e-6 * 1e9 = 1e3, which is how a
    # measured gap of 400,000,000 came back as at_optimum = True.
    var mixed = fc_tolerance(1.0e9, 1.0e-6)
    if mixed < 1.0 and mixed > 1.0e-6 and mixed < 1.0e-3:
        passed += 1
        print("  ✅ caller tol is ADDITIVE, not a relative multiplier —", mixed)
    else:
        failed += 1
        print("  ❌ fc_tolerance(1e9, 1e-6) =", mixed, "expected ~1.5e-5")

    # A NaN must not produce a tolerance every comparison passes. -1.0 fails every
    # `error > tol` test, which is the opposite failure mode from `tol = nan`.
    if (
        fc_tolerance(nan, 0.0) == -1.0
        and fc_tolerance(1.0, nan) == -1.0
        and fc_tolerance(inf, 0.0) == -1.0
        and fc_tolerance(1.0, -1.0) == -1.0
    ):
        passed += 1
        print("  ✅ non-finite or negative input yields -1.0, which no comparison passes")
    else:
        failed += 1
        print("  ❌ fc_tolerance did not reject non-finite input")

    # ══ fc_sum_tolerance: the ONE aggregate, and it counts its own terms ════════════
    # abs_tol + eps*(n_terms+1)*term_sum. With term_sum = 10 and 3 terms: eps*4*10.
    if (
        fc_sum_tolerance(0.0, 3, 0.0) == 0.0
        and fc_sum_tolerance(10.0, 3, 0.0) == FC_DBL_EPSILON * 4.0 * 10.0
        and fc_sum_tolerance(10.0, 7, 0.0) > fc_sum_tolerance(10.0, 3, 0.0)
        and fc_sum_tolerance(10.0, 3, -1.0) == -1.0
        and fc_sum_tolerance(nan, 3, 0.0) == -1.0
    ):
        passed += 1
        print("  ✅ fc_sum_tolerance is eps x (n_terms+1) x the terms that form the sum")
    else:
        failed += 1
        print("  ❌ fc_sum_tolerance wrong:", fc_sum_tolerance(10.0, 3, 0.0))

    # ══ the wrapping multiply is real, and fc_cells_fit does not fall for it ════════
    var wrapped = 3 * 6148914691236517206
    if wrapped == 2:
        passed += 1
        print("  ✅ 3 * 6148914691236517206 really is 2 — a product is not a bound")
    else:
        failed += 1
        print("  ❌ the wrapping multiply did not reproduce:", wrapped)

    if (
        not fc_cells_fit(3, 6148914691236517206, 2)
        and fc_cells_fit(2, 3, 6)
        and not fc_cells_fit(2, 3, 5)
        and fc_cells_fit(0, 5, 0)
        and not fc_cells_fit(-1, 5, 0)
        and not fc_cells_fit(1, MAX_FC_CELLS + 1, MAX_FC_CELLS + 1)
    ):
        passed += 1
        print("  ✅ fc_cells_fit divides, and holds this package's tighter cell ceiling")
    else:
        failed += 1
        print("  ❌ fc_cells_fit accepted a wrapping or oversized shape")

    if (
        fc_work_fits(3, 4, 12)
        and not fc_work_fits(3, 5, 12)
        and fc_work_fits(0, 1000000, 0)
        and fc_work_fits(1000000, 0, 0)
        and not fc_work_fits(-1, 1, 10)
    ):
        passed += 1
        print("  ✅ fc_work_fits charges by division; zero units or zero cost is free")
    else:
        failed += 1
        print("  ❌ fc_work_fits budget arithmetic wrong")

    # ══ ceilings: reported, scaled below the tree's shared one, never redefined ═════
    # Indices 0-5 are DIMENSION ceilings and must sit at or below the tree's shared one
    # (rule 1c: MAX_CSR_DIM is the budget for ONE object, and these drivers allocate several
    # arrays per unit). Indices 6-8 are WORK budgets — counts of operations, not of allocated
    # slots — so they are deliberately larger and are checked separately.
    var ceilings = fc_ceilings()
    var below_shared = True
    for i in range(6):
        if ceilings[i] > MAX_CSR_DIM:
            below_shared = False
    if (
        len(ceilings) == 10
        and below_shared
        and ceilings[6] == 268435456
        and ceilings[7] == 268435456
        and ceilings[8] == 1073741824
        and ceilings[8] == FC_MAX_SEASONAL_WORK
        and ceilings[9] == MAX_CSR_DIM
        and ceilings[2] == MAX_FC_CELLS
        and MAX_FC_CELLS == 2097152
        and MAX_FC_HORIZON == 65536
        and FC_MAX_QUANTILE_SAMPLES == 4096
    ):
        passed += 1
        print("  ✅ ten ceilings: six dimensions at or below MAX_CSR_DIM, three work budgets")
    else:
        failed += 1
        print("  ❌ ceiling report wrong:", len(ceilings))

    # BOUNDING MEMORY IS NOT BOUNDING WORK. `fc_period_defect` admits period up to n_obs/2 on
    # shape alone, so `n_obs = 2^22, period = 2^21` is a structurally VALID request for 2^43
    # window sums — a hang. The work charge refuses it, and refuses it as a BUDGET defect
    # rather than as a period defect, so the caller knows which knob to turn.
    if (
        fc_period_defect(1 << 22, 1 << 21) == FC_ERR_WORK_BUDGET
        and fc_period_defect(1 << 22, 1 << 8) == FC_OK
        and fc_period_defect(100000, 365) == FC_OK
        and fc_work_fits(1 << 22, 1 << 21, FC_MAX_SEASONAL_WORK) == False
        and fc_work_fits(100000, 365, FC_MAX_SEASONAL_WORK)
    ):
        passed += 1
        print("  ✅ n_obs x period is charged: 2^22 x 2^21 is a WORK refusal, 100k x 365 is fine")
    else:
        failed += 1
        print("  ❌ the seasonal work charge is missing:", fc_period_defect(1 << 22, 1 << 21))

    # ══ one integer, one meaning: twenty codes, twenty distinct names ═══════════════
    var codes = List[Int]()
    codes.append(FC_OK)
    codes.append(FC_ERR_EMPTY_SERIES)
    codes.append(FC_ERR_NON_FINITE)
    codes.append(FC_ERR_DIMENSION_TOO_LARGE)
    codes.append(FC_ERR_LENGTH_MISMATCH)
    codes.append(FC_ERR_HORIZON)
    codes.append(FC_ERR_INSUFFICIENT_HISTORY)
    codes.append(FC_ERR_PARAM_RANGE)
    codes.append(FC_ERR_PERIOD)
    codes.append(FC_ERR_NO_ORIGINS)
    codes.append(FC_ERR_WORK_BUDGET)
    codes.append(FC_ERR_METHOD)
    codes.append(FC_ERR_NEGATIVE_VALUES)
    codes.append(FC_ERR_NO_DEMAND)
    codes.append(FC_ERR_HIERARCHY_SHAPE)
    codes.append(FC_ERR_INCOHERENT)
    codes.append(FC_ERR_NO_RESIDUALS)
    codes.append(FC_ERR_LEVEL_RANGE)
    codes.append(FC_ERR_SEED_RANGE)
    codes.append(FC_ERR_ALL_UNDEFINED)
    var contiguous = True
    var distinct = True
    for i in range(len(codes)):
        if codes[i] != 300 + i:
            contiguous = False
        for j in range(i + 1, len(codes)):
            if fc_status_name(codes[i]) == fc_status_name(codes[j]):
                distinct = False
    if (
        len(codes) == 20
        and contiguous
        and distinct
        and fc_status_name(299) == "unknown"
        and fc_status_name(320) == "unknown"
        and fc_status_name(FC_OK) == "ok"
    ):
        passed += 1
        print("  ✅ 300-319 exactly, twenty distinct names, nothing outside the range named")
    else:
        failed += 1
        print("  ❌ status vocabulary broken: contiguous", contiguous, "distinct", distinct)

    var methods_distinct = True
    for i in range(FC_METHOD_MAX + 1):
        for j in range(i + 1, FC_METHOD_MAX + 1):
            if fc_method_name(i) == fc_method_name(j):
                methods_distinct = False
    if (
        FC_METHOD_MAX == 10
        and methods_distinct
        and fc_method_name(FC_METHOD_MAX + 1) == "unknown"
        and fc_method_name(-1) == "unknown"
    ):
        passed += 1
        print("  ✅ eleven method ids, all distinct, and no default for an unknown one")
    else:
        failed += 1
        print("  ❌ method vocabulary broken")

    # ══ three method ranges: disjoint, fully assigned, every name distinct ══════════
    # `interval` and `hierarchy` each used to number their own two methods 0 and 1 in their
    # own files, so `method_id = 0` meant `naive point forecast`, `empirical interval` AND
    # `bottom-up reconciliation` at the same time. This walks all three declared spans instead
    # of trusting the allocation comment: every id inside a span has a name, no two ids
    # anywhere across the three spans share a name, the spans do not overlap or touch, and the
    # numbers between them are unassigned.
    var all_ids = List[Int]()
    for i in range(FC_METHOD_MIN, FC_METHOD_MAX + 1):
        all_ids.append(i)
    for i in range(FC_INTERVAL_METHOD_MIN, FC_INTERVAL_METHOD_MAX + 1):
        all_ids.append(i)
    for i in range(HIER_METHOD_MIN, HIER_METHOD_MAX + 1):
        all_ids.append(i)
    var every_id_named = True
    var every_id_has_a_family = True
    var all_names_distinct = True
    for i in range(len(all_ids)):
        if fc_method_name(all_ids[i]) == "unknown":
            every_id_named = False
        if fc_method_family(all_ids[i]) == "unknown":
            every_id_has_a_family = False
        for j in range(i + 1, len(all_ids)):
            if all_ids[i] == all_ids[j]:
                all_names_distinct = False
            if fc_method_name(all_ids[i]) == fc_method_name(all_ids[j]):
                all_names_distinct = False
    # Every id in the gaps BETWEEN the ranges is unassigned in both functions.
    var gaps_unassigned = True
    for i in range(FC_METHOD_MAX + 1, FC_INTERVAL_METHOD_MIN):
        if fc_method_name(i) != "unknown" or fc_method_family(i) != "unknown":
            gaps_unassigned = False
    for i in range(FC_INTERVAL_METHOD_MAX + 1, HIER_METHOD_MIN):
        if fc_method_name(i) != "unknown" or fc_method_family(i) != "unknown":
            gaps_unassigned = False
    if (
        len(all_ids) == 15
        and every_id_named
        and every_id_has_a_family
        and all_names_distinct
        and gaps_unassigned
        # The spans are strictly ordered and strictly separated, so no arithmetic on one can
        # land in another.
        and FC_METHOD_MAX < FC_INTERVAL_METHOD_MIN - 1
        and FC_INTERVAL_METHOD_MAX < HIER_METHOD_MIN - 1
        # The three ids that used to collide are now three different numbers.
        and FC_METHOD_NAIVE != FC_INTERVAL_EMPIRICAL
        and FC_INTERVAL_EMPIRICAL != HIER_BOTTOM_UP
        and FC_METHOD_NAIVE != HIER_BOTTOM_UP
        and FC_INTERVAL_EMPIRICAL == 100
        and FC_INTERVAL_BOOTSTRAP == 101
        and HIER_BOTTOM_UP == 200
        and HIER_TOP_DOWN == 201
        # A family is a total function of the id, and outside the three spans it says so.
        and fc_method_family(FC_METHOD_NAIVE) == "forecast"
        and fc_method_family(FC_INTERVAL_BOOTSTRAP) == "interval"
        and fc_method_family(HIER_TOP_DOWN) == "reconciliation"
        and fc_method_family(-1) == "unknown"
        and fc_method_family(11) == "unknown"
        and fc_method_family(202) == "unknown"
        and fc_method_name(202) == "unknown"
    ):
        passed += 1
        print("  ✅ three method ranges, 15 ids, disjoint and every one named with a family")
    else:
        failed += 1
        print(
            "  ❌ method ranges broken:",
            len(all_ids),
            every_id_named,
            all_names_distinct,
            gaps_unassigned,
        )

    # ══ fc_min_samples_for_level: a discrete threshold off a floating division ══════
    # 2/(1-L): 40 at 95%, 20 at 90%, 200 at 99%, 4 at 50%. The 90% case is the regression:
    # `1 - 0.9` is 0.09999999999999998, so a bare ceil(1/tail) returns 21.
    if (
        fc_min_samples_for_level(0.95) == 40
        and fc_min_samples_for_level(0.90) == 20
        and fc_min_samples_for_level(0.99) == 200
        and fc_min_samples_for_level(0.5) == 4
    ):
        passed += 1
        print("  ✅ estimability thresholds 40 / 20 / 200 / 4 — the 0.90 case does not drift")
    else:
        failed += 1
        print("  ❌ min samples wrong:", fc_min_samples_for_level(0.95),
              fc_min_samples_for_level(0.90))

    if (
        fc_min_samples_for_level(1.0) == -1
        and fc_min_samples_for_level(0.0) == -1
        and fc_min_samples_for_level(1.5) == -1
        and fc_min_samples_for_level(nan) == -1
        and fc_min_samples_for_level(1.0 - 1.0e-15) == -1
    ):
        passed += 1
        print("  ✅ no answer is -1, impossible for a real sample count")
    else:
        failed += 1
        print("  ❌ min samples did not refuse an impossible level")

    # ══ the empirical quantile IS risk.value_at_risk, by identity ══════════════════
    var v = _floats(1.0, 2.0, 3.0, 4.0, 5.0)
    var q0 = fc_quantile_of(v, 0.0)
    var q25 = fc_quantile_of(v, 0.25)
    var q50 = fc_quantile_of(v, 0.5)
    var q100 = fc_quantile_of(v, 1.0)
    # Type 7 on 1..5: index p*(n-1) = 4p, so p=0.25 lands exactly on element 2.0.
    if (
        q0.has_value and q0.value == 1.0
        and q25.has_value and q25.value == 2.0
        and q50.has_value and q50.value == 3.0
        and q100.has_value and q100.value == 5.0
        and q50.n_samples == 5
        and q50.status == FC_OK
    ):
        passed += 1
        print("  ✅ type-7 quantiles on 1..5 are 1, 2, 3, 5 at p = 0, .25, .5, 1")
    else:
        failed += 1
        print("  ❌ quantile values wrong:", q0.value, q25.value, q50.value, q100.value)

    var identical = True
    for i in range(11):
        var p = Float64(i) * 0.1
        var mine = fc_quantile_of(v, p)
        if not mine.has_value or mine.value != -value_at_risk(v, 1.0 - p):
            identical = False
    if identical:
        passed += 1
        print("  ✅ fc_quantile_of(v,p) is BIT-EQUAL to -value_at_risk(v,1-p) at 11 levels")
    else:
        failed += 1
        print("  ❌ the quantile is not the frozen kernel")

    # value_at_risk([], c) returns 0.0 — a quantile of nothing indistinguishable from a real
    # answer. That frozen behaviour is asserted here, next to the wrapper refusing it.
    var empty = List[Float64]()
    var q_empty = fc_quantile_of(empty, 0.5)
    if (
        value_at_risk(empty, 0.95) == 0.0
        and not q_empty.has_value
        and q_empty.value == 0.0
        and q_empty.status == FC_ERR_EMPTY_SERIES
        and not fc_quantile_of(v, 1.5).has_value
        and not fc_quantile_of(_floats(1.0, nan), 0.5).has_value
    ):
        passed += 1
        print("  ✅ the frozen 0.0-for-nothing is made ABSENT, and p / NaN are refused")
    else:
        failed += 1
        print("  ❌ quantile absence handling wrong")

    # ══ the guards ═════════════════════════════════════════════════════════════════
    if (
        fc_series_defect(v) == FC_OK
        and fc_series_defect(empty) == FC_ERR_EMPTY_SERIES
        and fc_series_defect(_floats(1.0, inf)) == FC_ERR_NON_FINITE
        and fc_series_defect(_floats(1.0, nan)) == FC_ERR_NON_FINITE
        and fc_all_finite(v)
        and not fc_all_finite(_floats(nan))
        and fc_finite(0.0)
        and not fc_finite(inf)
    ):
        passed += 1
        print("  ✅ series validation: empty and non-finite are distinct refusals")
    else:
        failed += 1
        print("  ❌ fc_series_defect wrong")

    # The horizon is bounded by the PAYLOAD (n_obs), not only by the ceiling. That is the
    # rule-4 refusal: 5 observations cannot support a 6-step forecast and cannot backtest one.
    if (
        fc_horizon_defect(5, 5) == FC_OK
        and fc_horizon_defect(5, 6) == FC_ERR_HORIZON
        and fc_horizon_defect(5, 0) == FC_ERR_HORIZON
        and fc_horizon_defect(5, -1) == FC_ERR_HORIZON
        and fc_horizon_defect(0, 3) == FC_ERR_EMPTY_SERIES
        and fc_horizon_defect(1000000, MAX_FC_HORIZON + 1) == FC_ERR_DIMENSION_TOO_LARGE
    ):
        passed += 1
        print("  ✅ horizon <= n_obs is enforced, and the ceiling is a separate refusal")
    else:
        failed += 1
        print("  ❌ fc_horizon_defect wrong")

    # A period needs one COMPLETE cycle inside the region where the frozen centered trend
    # exists: n >= period + 2*(period//2). Even period 4 needs 8; odd period 3 needs 5.
    if (
        fc_period_defect(12, 4) == FC_OK
        and fc_period_defect(8, 4) == FC_OK
        and fc_period_defect(7, 4) == FC_ERR_PERIOD
        and fc_period_defect(5, 3) == FC_OK
        and fc_period_defect(4, 3) == FC_ERR_PERIOD
        and fc_period_defect(10, 1) == FC_OK
        and fc_period_defect(10, 0) == FC_ERR_PERIOD
        and fc_period_defect(0, 4) == FC_ERR_EMPTY_SERIES
    ):
        passed += 1
        print("  ✅ period needs an interior cycle: 4 needs 8 points, 3 needs 5, 1 is free")
    else:
        failed += 1
        print("  ❌ fc_period_defect wrong:", fc_period_defect(8, 4), fc_period_defect(7, 4))

    # alpha = 0 means "never update": the level stays at y[0] forever. A defensible
    # recursion and an indefensible forecast, so it is refused rather than clamped.
    if (
        fc_smoothing_defect(1.0) == FC_OK
        and fc_smoothing_defect(0.5) == FC_OK
        and fc_smoothing_defect(0.0) == FC_ERR_PARAM_RANGE
        and fc_smoothing_defect(1.5) == FC_ERR_PARAM_RANGE
        and fc_smoothing_defect(nan) == FC_ERR_NON_FINITE
        and fc_damping_defect(1.0) == FC_OK
        and fc_damping_defect(1.0001) == FC_ERR_PARAM_RANGE
        and fc_level_defect(0.95) == FC_OK
        and fc_level_defect(1.0) == FC_ERR_LEVEL_RANGE
        and fc_level_defect(0.0) == FC_ERR_LEVEL_RANGE
    ):
        passed += 1
        print("  ✅ alpha in (0,1], phi in (0,1], level strictly inside (0,1)")
    else:
        failed += 1
        print("  ❌ parameter guards wrong")

    print("  [forecasting.contract] Passed:", passed, "Failed:", failed)
