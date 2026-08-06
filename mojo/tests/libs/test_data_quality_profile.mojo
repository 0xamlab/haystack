"""test_data_quality_profile.mojo — known-value tests for the null / NaN / zero census.

Hand-written. The worked column, used throughout:

    values  = [1.0, 0.0, 3.0, 0.0, 2.0]
    present = [ T ,  T ,  F ,  T ,  T ]     so row 2's 3.0 is ABSENT and never read

    live values  1.0, 0.0, 0.0, 2.0          n = 4
    sum          3.0                          mean = 3/4 = 0.75
    deviations   0.25, -0.75, -0.75, 1.25
    squares      0.0625 + 0.5625 + 0.5625 + 1.5625 = 2.75
    sample var   2.75 / (4 - 1) = 0.9166666...  sd = sqrt(2.75/3) = 0.9574271077563381
    sorted       [0.0, 0.0, 1.0, 2.0]         median = (0.0 + 1.0)/2 = 0.5
    distinct     {0.0, 1.0, 2.0}              = 3
    nulls        1 of 5                       null_fraction = 0.2

Every one of those is derived above, not read out of the implementation. The standard
deviation digits come from CPython's `math.sqrt(2.75/3)`.

The second oracle is a CROSS-CHECK between two frozen kernels: `stats.median` (used by the
profile, O(n log n) through `fast_sort`) and `numeric.reduce.reduce_median` (O(n^2)
insertion sort, null-aware). They are independent implementations and must agree, which is
what makes the profile's choice of the faster one safe.
"""
from numeric.reduce import reduce_median
from stats import median as stats_median

from data_quality.contract import (
    DQ_ERR_COLUMN_INDEX,
    DQ_ERR_LENGTH_MISMATCH,
    DQ_ERR_MASK_LENGTH,
    DQ_OK,
    dq_is_finite,
    dq_live_and_finite,
    dq_mask_all_valid,
)
from data_quality.profile import (
    ColumnProfile,
    DQ_PROFILE_ERR_NO_COLUMNS,
    profile_column,
    profile_column_at,
    profile_is_constant,
    profile_status_name,
    profile_table,
)


def _nan() -> Float64:
    var zero: Float64 = 0.0
    return zero / zero


def _pos_inf() -> Float64:
    var zero: Float64 = 0.0
    return 1.0 / zero


def _floats5(a: Float64, b: Float64, c: Float64, d: Float64, e: Float64) -> List[Float64]:
    var o = List[Float64]()
    o.append(a)
    o.append(b)
    o.append(c)
    o.append(d)
    o.append(e)
    return o^


def _floats3(a: Float64, b: Float64, c: Float64) -> List[Float64]:
    var o = List[Float64]()
    o.append(a)
    o.append(b)
    o.append(c)
    return o^


def _bools3(a: Bool, b: Bool, c: Bool) -> List[Bool]:
    var o = List[Bool]()
    o.append(a)
    o.append(b)
    o.append(c)
    return o^


def _bools5(a: Bool, b: Bool, c: Bool, d: Bool, e: Bool) -> List[Bool]:
    var o = List[Bool]()
    o.append(a)
    o.append(b)
    o.append(c)
    o.append(d)
    o.append(e)
    return o^


def _all_value_slots_finite(p: ColumnProfile) -> Bool:
    """No Float64 field may hold a raw non-finite: the dispatch refuses to serialize one,
    so a single NaN in a slot turns the whole response into a typed error."""
    return (
        dq_is_finite(p.null_fraction)
        and dq_is_finite(p.mean)
        and dq_is_finite(p.stddev)
        and dq_is_finite(p.min_value)
        and dq_is_finite(p.max_value)
        and dq_is_finite(p.median_value)
    )


def _census_sums(p: ColumnProfile) -> Bool:
    """The five classifications partition the rows, and the finite ones partition presence."""
    if p.n_rows != p.n_null + p.n_present:
        return False
    return p.n_present == p.n_nan + p.n_pos_inf + p.n_neg_inf + p.n_finite


def check() raises:
    var passed = 0
    var failed = 0

    var values = _floats5(1.0, 0.0, 3.0, 0.0, 2.0)
    var present = _bools5(True, True, False, True, True)
    var p = profile_column(values, present, 5)

    if p.status == DQ_OK and p.n_rows == 5 and p.n_present == 4 and p.n_null == 1:
        passed += 1
        print("  ✅ 5 rows, 4 present, 1 absent")
    else:
        failed += 1
        print("  ❌ presence census wrong:", p.n_present, p.n_null)

    if p.n_nan == 0 and p.n_pos_inf == 0 and p.n_neg_inf == 0 and p.n_finite == 4:
        passed += 1
        print("  ✅ all four present values are finite; no NaN or infinity counted")
    else:
        failed += 1
        print("  ❌ finiteness census wrong")

    if p.n_zero == 2 and p.n_negative == 0 and p.n_positive == 2:
        passed += 1
        print("  ✅ two zeros, two positives, no negatives — zero is its own count")
    else:
        failed += 1
        print("  ❌ sign census wrong:", p.n_zero, p.n_negative, p.n_positive)

    if p.n_distinct_finite == 3:
        passed += 1
        print("  ✅ distinct live values {0.0, 1.0, 2.0} = 3 (the absent 3.0 is not one)")
    else:
        failed += 1
        print("  ❌ distinct count is", p.n_distinct_finite)

    if p.has_mean and p.mean == 0.75:
        passed += 1
        print("  ✅ mean = 3.0/4 = 0.75, computed over live values only")
    else:
        failed += 1
        print("  ❌ mean is", p.mean, "present", p.has_mean)

    if p.has_stddev and p.stddev == 0.9574271077563381:
        passed += 1
        print("  ✅ sample stddev = sqrt(2.75/3) = 0.9574271077563381")
    else:
        failed += 1
        print("  ❌ stddev is", p.stddev)

    if p.has_min and p.min_value == 0.0 and p.has_max and p.max_value == 2.0:
        passed += 1
        print("  ✅ min 0.0, max 2.0 — the absent 3.0 is not the maximum")
    else:
        failed += 1
        print("  ❌ extrema wrong:", p.min_value, p.max_value)

    if p.has_median and p.median_value == 0.5:
        passed += 1
        print("  ✅ median of [0,0,1,2] = (0+1)/2 = 0.5")
    else:
        failed += 1
        print("  ❌ median is", p.median_value)

    if p.has_null_fraction and p.null_fraction == 0.2:
        passed += 1
        print("  ✅ null fraction = 1/5 = 0.2")
    else:
        failed += 1
        print("  ❌ null fraction is", p.null_fraction)

    if _census_sums(p) and _all_value_slots_finite(p):
        passed += 1
        print("  ✅ the census sums to n_rows and no value slot holds a non-finite")
    else:
        failed += 1
        print("  ❌ census does not sum, or a slot holds a non-finite")

    # ── cross-oracle: two independent frozen medians must agree ────────────────
    var live = dq_live_and_finite(values, present)
    var dense = List[Float64]()
    for i in range(5):
        if live[i]:
            dense.append(values[i])
    var frozen_reduce = reduce_median(values, live)
    var frozen_stats = stats_median(dense, len(dense))
    if frozen_reduce.present and frozen_reduce.value == 0.5 and frozen_stats == 0.5:
        passed += 1
        print("  ✅ numeric.reduce.reduce_median and stats.median both say 0.5")
    else:
        failed += 1
        print("  ❌ the two frozen medians disagree:", frozen_reduce.value, frozen_stats)

    # ── NULL, NaN and ZERO are three different columns ────────────────────────
    var m3 = dq_mask_all_valid(3)
    var absent3 = List[Bool]()
    absent3.append(False)
    absent3.append(False)
    absent3.append(False)

    var zeros = List[Float64]()
    zeros.append(0.0)
    zeros.append(0.0)
    zeros.append(0.0)
    var nans = List[Float64]()
    nans.append(_nan())
    nans.append(_nan())
    nans.append(_nan())

    var p_null = profile_column(zeros, absent3, 3)
    var p_nan = profile_column(nans, m3, 3)
    var p_zero = profile_column(zeros, m3, 3)

    if p_null.n_null == 3 and p_null.n_nan == 0 and p_null.n_zero == 0:
        passed += 1
        print("  ✅ an all-absent column: 3 nulls, 0 NaN, 0 zeros")
    else:
        failed += 1
        print("  ❌ all-absent census wrong")

    if p_nan.n_null == 0 and p_nan.n_nan == 3 and p_nan.n_zero == 0 and p_nan.n_finite == 0:
        passed += 1
        print("  ✅ an all-NaN present column: 0 nulls, 3 NaN, 0 zeros, 0 finite")
    else:
        failed += 1
        print("  ❌ all-NaN census wrong:", p_nan.n_null, p_nan.n_nan)

    if p_zero.n_null == 0 and p_zero.n_nan == 0 and p_zero.n_zero == 3 and p_zero.n_finite == 3:
        passed += 1
        print("  ✅ an all-zero column: 0 nulls, 0 NaN, 3 zeros, 3 finite")
    else:
        failed += 1
        print("  ❌ all-zero census wrong")

    # A mean of zeros is 0.0 PRESENT. A mean of nothing is ABSENT. The two are the
    # distinction this package exists for, and they are not the same value.
    if p_zero.has_mean and p_zero.mean == 0.0 and not p_null.has_mean and not p_nan.has_mean:
        passed += 1
        print("  ✅ mean of zeros is 0.0 present; mean of nulls and of NaNs is ABSENT")
    else:
        failed += 1
        print("  ❌ absence and a computed zero are being conflated")

    if _all_value_slots_finite(p_nan) and p_nan.mean == 0.0 and p_nan.median_value == 0.0:
        passed += 1
        print("  ✅ an all-NaN column returns 0.0 in every absent slot, never a NaN")
    else:
        failed += 1
        print("  ❌ a NaN reached a value slot")

    if p_null.n_distinct_finite == 0 and p_nan.n_distinct_finite == 0:
        passed += 1
        print("  ✅ nothing live means no distinct values, not one")
    else:
        failed += 1
        print("  ❌ distinct count over an empty live set is not zero")

    # Infinity is its own fact, signed, and it is not a maximum.
    var with_inf = List[Float64]()
    with_inf.append(1.0)
    with_inf.append(_pos_inf())
    with_inf.append(-_pos_inf())
    var p_inf = profile_column(with_inf, m3, 3)
    if (
        p_inf.n_pos_inf == 1
        and p_inf.n_neg_inf == 1
        and p_inf.n_finite == 1
        and p_inf.has_max
        and p_inf.max_value == 1.0
        and p_inf.min_value == 1.0
    ):
        passed += 1
        print("  ✅ +inf and -inf are counted separately and neither becomes an extremum")
    else:
        failed += 1
        print("  ❌ infinity census wrong:", p_inf.n_pos_inf, p_inf.n_neg_inf, p_inf.max_value)

    # ── constancy, on the frozen identity ─────────────────────────────────────
    var signed_zeros = List[Float64]()
    signed_zeros.append(-0.0)
    signed_zeros.append(0.0)
    signed_zeros.append(0.0)
    if profile_is_constant(signed_zeros, m3, 3):
        passed += 1
        print("  ✅ a column of -0.0 and +0.0 is constant (the frozen normalization)")
    else:
        failed += 1
        print("  ❌ -0.0 and +0.0 were treated as two values")

    if not profile_is_constant(zeros, absent3, 3):
        passed += 1
        print("  ✅ a column with nothing live is NOT constant — nothing is not one thing")
    else:
        failed += 1
        print("  ❌ an all-absent column was reported constant")

    # A column of NaNs is NOT constant, and the docstring used to claim it was. The frozen
    # hash index does collapse every NaN to one key, but `dq_live_and_finite` strips
    # non-finites BEFORE the index sees them, so the live-and-finite count is 0 — the same
    # answer as an all-absent column and for the same reason.
    if not profile_is_constant(nans, m3, 3) and p_nan.n_distinct_finite == 0:
        passed += 1
        print("  ✅ a column of NaNs is NOT constant: non-finites never reach the index")
    else:
        failed += 1
        print(
            "  ❌ the NaN column's constancy contradicts its distinct count:",
            profile_is_constant(nans, m3, 3), p_nan.n_distinct_finite,
        )

    if profile_is_constant(zeros, m3, 3) and not profile_is_constant(values, present, 5):
        passed += 1
        print("  ✅ constancy agrees with n_distinct_finite == 1 on both answers")
    else:
        failed += 1
        print("  ❌ constancy disagrees with the distinct count")

    # ── monotonicity, over the dense live values ──────────────────────────────
    var up = List[Float64]()
    up.append(1.0)
    up.append(2.0)
    up.append(3.0)
    var down = List[Float64]()
    down.append(3.0)
    down.append(2.0)
    down.append(1.0)
    var mixed = List[Float64]()
    mixed.append(1.0)
    mixed.append(3.0)
    mixed.append(2.0)
    var gap_mask = List[Bool]()
    gap_mask.append(True)
    gap_mask.append(False)
    gap_mask.append(True)
    if (
        profile_column(up, m3, 3).monotonic_direction == 1
        and profile_column(down, m3, 3).monotonic_direction == -1
        and profile_column(mixed, m3, 3).monotonic_direction == 0
        and profile_column(mixed, gap_mask, 3).monotonic_direction == 1
    ):
        passed += 1
        print("  ✅ monotonic 1 / -1 / 0, and a null gap does not break a run")
    else:
        failed += 1
        print("  ❌ monotonicity wrong")

    # ── monotonic_direction is FLAG-PAIRED, because an order needs two values ─
    # Every one of the four columns below used to answer a bare Int that a caller could not
    # tell apart from a computed one. The frozen `check_monotonic` answers 1 for a sequence
    # of length 0 or 1 — vacuously true in both directions — so a column with exactly ONE
    # live value published "strictly increasing" as a fact about a single point.
    var one_live = profile_column(_floats3(5.0, 0.0, 0.0), _bools3(True, False, False), 3)
    if (
        not one_live.has_monotonic_direction
        and one_live.monotonic_direction == 0
        and one_live.n_distinct_finite == 1
    ):
        passed += 1
        print("  ✅ ONE live value has no order to report: absent, not 'strictly increasing'")
    else:
        failed += 1
        print(
            "  ❌ a single point was given a direction:",
            one_live.has_monotonic_direction, one_live.monotonic_direction,
        )

    # `p_null` is the all-absent column and `p_nan` the all-NaN one, both from the census
    # block above: neither has a single live-and-finite value.
    if (
        not p_null.has_monotonic_direction and p_null.monotonic_direction == 0
        and not p_nan.has_monotonic_direction and p_nan.monotonic_direction == 0
    ):
        passed += 1
        print("  ✅ nothing to order (all-null, all-NaN) reports the direction ABSENT")
    else:
        failed += 1
        print(
            "  ❌ a column with no live values reported an order:",
            p_null.has_monotonic_direction, p_nan.has_monotonic_direction,
        )

    # With the flag True a 0 still covers two cases — constant and genuinely out of order —
    # and they are separable INSIDE the same struct from n_distinct_finite.
    var const_col = profile_column(_floats3(4.0, 4.0, 4.0), m3, 3)
    var unsorted_col = profile_column(mixed, m3, 3)
    if (
        const_col.has_monotonic_direction and const_col.monotonic_direction == 0
        and const_col.n_distinct_finite == 1
        and unsorted_col.has_monotonic_direction and unsorted_col.monotonic_direction == 0
        and unsorted_col.n_distinct_finite == 3
    ):
        passed += 1
        print("  ✅ constant vs out-of-order both read 0, told apart by n_distinct_finite")
    else:
        failed += 1
        print("  ❌ a present direction is not separable from the distinct count")

    # And two live values IS enough for an order — the floor is 2, not 3.
    var two_live = profile_column(_floats3(1.0, 2.0, 0.0), _bools3(True, True, False), 3)
    if two_live.has_monotonic_direction and two_live.monotonic_direction == 1:
        passed += 1
        print("  ✅ two live values are an order: [1, 2] is strictly increasing")
    else:
        failed += 1
        print("  ❌ two live values were treated as no order:", two_live.monotonic_direction)

    # ── whole-table pass ──────────────────────────────────────────────────────
    # 3 rows x 3 cols, row-major:
    #   col 0 = [5, 5, 5]        constant
    #   col 1 = [1, 2, 3]        varied
    #   col 2 = [_, _, _]        entirely absent
    var table = List[Float64]()
    table.append(5.0)
    table.append(1.0)
    table.append(0.0)
    table.append(5.0)
    table.append(2.0)
    table.append(0.0)
    table.append(5.0)
    table.append(3.0)
    table.append(0.0)
    var tmask = dq_mask_all_valid(9)
    tmask[2] = False
    tmask[5] = False
    tmask[8] = False

    var tp = profile_table(table, 3, 3, tmask)
    if tp.status == DQ_OK and tp.n_cols == 3 and tp.n_rows == 3:
        passed += 1
        print("  ✅ a 3x3 table profiles into three per-column entries")
    else:
        failed += 1
        print("  ❌ table profile status", profile_status_name(tp.status))

    if (
        len(tp.null_counts) == 3
        and tp.null_counts[0] == 0
        and tp.null_counts[1] == 0
        and tp.null_counts[2] == 3
    ):
        passed += 1
        print("  ✅ per-column null counts are [0, 0, 3]")
    else:
        failed += 1
        print("  ❌ per-column null counts wrong")

    if (
        len(tp.constant_columns) == 1
        and tp.constant_columns[0] == 0
        and len(tp.all_absent_columns) == 1
        and tp.all_absent_columns[0] == 2
    ):
        passed += 1
        print("  ✅ column 0 is constant, column 2 is all-absent, and they are not the same list")
    else:
        failed += 1
        print(
            "  ❌ constant/all-absent columns wrong:",
            len(tp.constant_columns), len(tp.all_absent_columns),
        )

    if tp.distinct_counts[0] == 1 and tp.distinct_counts[1] == 3 and tp.distinct_counts[2] == 0:
        passed += 1
        print("  ✅ distinct counts per column are [1, 3, 0]")
    else:
        failed += 1
        print("  ❌ distinct counts wrong")

    var col1_profile = profile_column_at(table, 3, 3, 1, tmask)
    if col1_profile.status == DQ_OK and col1_profile.has_mean and col1_profile.mean == 2.0:
        passed += 1
        print("  ✅ profile_column_at reads the right column: mean of [1,2,3] is 2.0")
    else:
        failed += 1
        print("  ❌ profile_column_at wrong:", col1_profile.mean)

    # ── refusals: nothing is guessed, and nothing is indexed ──────────────────
    var short_mask = List[Bool]()
    short_mask.append(True)
    if profile_column(values, short_mask, 5).status == DQ_ERR_MASK_LENGTH:
        passed += 1
        print("  ✅ a mask shorter than n_rows is refused, not read as 'mostly absent'")
    else:
        failed += 1
        print("  ❌ a short mask was accepted")

    var short_values = List[Float64]()
    short_values.append(1.0)
    if profile_column(short_values, dq_mask_all_valid(5), 5).status == DQ_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ n_rows greater than len(values) is refused before any read")
    else:
        failed += 1
        print("  ❌ a caller's oversized count was trusted")

    if (
        profile_column_at(table, 3, 3, -1, tmask).status == DQ_ERR_COLUMN_INDEX
        and profile_column_at(table, 3, 3, 3, tmask).status == DQ_ERR_COLUMN_INDEX
    ):
        passed += 1
        print("  ✅ a column index out of range in either direction is refused")
    else:
        failed += 1
        print("  ❌ an out-of-range column index reached a subscript")

    var no_cols = List[Float64]()
    if profile_table(no_cols, 0, 0, List[Bool]()).status == DQ_PROFILE_ERR_NO_COLUMNS:
        passed += 1
        print("  ✅ a table with no columns has nothing to profile and says so")
    else:
        failed += 1
        print("  ❌ a zero-column table was profiled anyway")

    # The A-Z generated suite calls every contract function with a 5-element list and 5 for
    # every Int, which is exactly the shape that used to abort the worker.
    var lf5 = _floats5(0.5, 0.6, 0.7, 0.4, 0.3)
    var lb5 = _bools5(True, False, True, True, False)
    var az_column = profile_column(lf5, lb5, 5)
    var az_at = profile_column_at(lf5, 5, 5, 5, lb5)
    var az_table = profile_table(lf5, 5, 5, lb5)
    if az_column.status == DQ_OK and az_at.status != DQ_OK and az_table.status != DQ_OK:
        passed += 1
        print("  ✅ the A-Z argument shape returns statuses, never a crash")
    else:
        failed += 1
        print("  ❌ the A-Z shape behaved unexpectedly")

    print("  [data_quality.profile] Passed:", passed, "Failed:", failed)


def main() raises:
    check()
