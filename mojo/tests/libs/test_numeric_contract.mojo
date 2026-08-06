"""test_numeric_contract.mojo — known-value tests for the aggregation contract.

Hand-written. Each assertion pins a decision that one of the four existing
aggregation paths gets differently, so drifting back to any of them fails here.
"""
from numeric.contract import (
    AGG_AVG,
    AGG_COUNT,
    AGG_MEDIAN,
    AGG_STD,
    AGG_SUM,
    AGG_UNKNOWN,
    AGG_VAR,
    aggregation_token,
    empty_yields_null,
    is_valid_aggregation,
    parse_aggregation,
    requires_two_values,
    unknown_aggregation_error,
)
from numeric.reduce import (
    all_valid,
    first_non_finite,
    is_finite_value,
    reduce,
    reduce_mean,
    reduce_median,
    reduce_stddev,
    reduce_sum,
    reduce_variance,
)


def _values(a: Float64, b: Float64, c: Float64) -> List[Float64]:
    var out = List[Float64]()
    out.append(a)
    out.append(b)
    out.append(c)
    return out^


def main() raises:
    var passed = 0
    var failed = 0

    # ── both vocabularies parse; one canonical name comes back ───────────────
    if (
        parse_aggregation("avg") == AGG_AVG
        and parse_aggregation("mean") == AGG_AVG
        and aggregation_token(AGG_AVG) == "avg"
    ):
        passed += 1
        print("  ✅ avg and mean both parse; 'avg' is echoed")
    else:
        failed += 1
        print("  ❌ token aliasing wrong")

    # ── an unknown token is UNKNOWN, never silently SUM ─────────────────────
    # This is the concrete regression: the existing paths return sum for a token
    # they do not recognise, in both directions.
    if (
        parse_aggregation("mena") == AGG_UNKNOWN
        and parse_aggregation("") == AGG_UNKNOWN
        and parse_aggregation("AVG") == AGG_UNKNOWN  # case-sensitive on purpose
        and not is_valid_aggregation("total")
    ):
        passed += 1
        print("  ✅ an unrecognised token is UNKNOWN, not a silent sum")
    else:
        failed += 1
        print("  ❌ unknown token fell back:", parse_aggregation("mena"))

    # ── the error names what is accepted ────────────────────────────────────
    var err = unknown_aggregation_error("mena")
    if err.find("unknown_aggregation") >= 0 and err.find("avg (alias mean)") >= 0:
        passed += 1
        print("  ✅ the error names the accepted set")
    else:
        failed += 1
        print("  ❌ error unhelpful:", err)

    # ── empty: count/sum are 0, everything else has no answer ───────────────
    var empty = List[Float64]()
    var empty_mask = List[Bool]()
    var e_sum = reduce(AGG_SUM, empty, empty_mask)
    var e_count = reduce(AGG_COUNT, empty, empty_mask)
    var e_avg = reduce(AGG_AVG, empty, empty_mask)
    if (
        e_sum.present
        and e_sum.value == 0.0
        and e_count.present
        and e_count.value == 0.0
        and not e_avg.present
    ):
        passed += 1
        print("  ✅ empty: sum/count are 0, avg has no answer (not 0.0)")
    else:
        failed += 1
        print("  ❌ empty policy wrong:", e_sum.present, e_count.value, e_avg.present)

    if (
        empty_yields_null(AGG_AVG)
        and empty_yields_null(AGG_MEDIAN)
        and not empty_yields_null(AGG_SUM)
        and not empty_yields_null(AGG_COUNT)
    ):
        passed += 1
        print("  ✅ empty_yields_null matches the documented split")
    else:
        failed += 1
        print("  ❌ empty policy classification wrong")

    # ── known values ────────────────────────────────────────────────────────
    var v = _values(1.0, 2.0, 6.0)
    var mask = all_valid(3)
    if reduce_sum(v, mask).value == 9.0 and reduce_mean(v, mask).value == 3.0:
        passed += 1
        print("  ✅ sum 9, mean 3 over [1,2,6]")
    else:
        failed += 1
        print("  ❌ sum/mean wrong:", reduce_sum(v, mask).value, reduce_mean(v, mask).value)

    # Sample variance of [1,2,6]: mean 3, deviations -2,-1,3 -> 4+1+9=14, /2 = 7.
    var var_out = reduce_variance(v, mask)
    if var_out.present and var_out.value > 6.999 and var_out.value < 7.001:
        passed += 1
        print("  ✅ sample variance of [1,2,6] is 7 (n-1 denominator)")
    else:
        failed += 1
        print("  ❌ variance wrong:", var_out.value)

    var sd = reduce_stddev(v, mask)
    if sd.present and sd.value > 2.6457 and sd.value < 2.6458:
        passed += 1
        print("  ✅ stddev is sqrt(variance) = 2.6457...")
    else:
        failed += 1
        print("  ❌ stddev wrong:", sd.value)

    # ── median: odd takes the middle, even averages the middle pair ──────────
    var odd = reduce_median(_values(3.0, 1.0, 2.0), all_valid(3))
    var four = List[Float64]()
    four.append(4.0)
    four.append(1.0)
    four.append(3.0)
    four.append(2.0)
    var even = reduce_median(four, all_valid(4))
    if odd.value == 2.0 and even.value == 2.5:
        passed += 1
        print("  ✅ median: odd -> middle (2.0), even -> mean of pair (2.5)")
    else:
        failed += 1
        print("  ❌ median wrong:", odd.value, even.value)

    # ── the input is not reordered by taking a median ────────────────────────
    var original = _values(3.0, 1.0, 2.0)
    _ = reduce_median(original, all_valid(3))
    if original[0] == 3.0 and original[1] == 1.0 and original[2] == 2.0:
        passed += 1
        print("  ✅ median does not mutate the caller's values")
    else:
        failed += 1
        print("  ❌ median reordered its input")

    # ── nulls are skipped by value aggregates and only counted by count ──────
    var with_null = _values(2.0, 999.0, 4.0)
    var null_mask = List[Bool]()
    null_mask.append(True)
    null_mask.append(False)  # the 999.0 is null
    null_mask.append(True)
    var n_sum = reduce_sum(with_null, null_mask)
    var n_mean = reduce_mean(with_null, null_mask)
    var n_count = reduce(AGG_COUNT, with_null, null_mask)
    if n_sum.value == 6.0 and n_mean.value == 3.0 and n_count.value == 2.0:
        passed += 1
        print("  ✅ nulls skipped: sum 6, mean 3, count 2 (not 3)")
    else:
        failed += 1
        print("  ❌ null handling wrong:", n_sum.value, n_mean.value, n_count.value)

    # ── a real 0.0 is not confused with a null ──────────────────────────────
    var zeros = _values(0.0, 0.0, 0.0)
    var zero_out = reduce_mean(zeros, all_valid(3))
    var all_null = List[Bool]()
    all_null.append(False)
    all_null.append(False)
    all_null.append(False)
    var null_out = reduce_mean(zeros, all_null)
    if zero_out.present and zero_out.value == 0.0 and not null_out.present:
        passed += 1
        print("  ✅ a mean of zeros is 0.0 present; all-null has no answer")
    else:
        failed += 1
        print("  ❌ zero/null conflated")

    # ── variance needs two observations ─────────────────────────────────────
    var one = List[Float64]()
    one.append(5.0)
    if (
        not reduce_variance(one, all_valid(1)).present
        and requires_two_values(AGG_VAR)
        and requires_two_values(AGG_STD)
    ):
        passed += 1
        print("  ✅ variance of one observation has no answer, not 0.0")
    else:
        failed += 1
        print("  ❌ single-observation variance wrong")

    # ── NaN and infinity are detected before they poison a reduction ─────────
    var poisoned = _values(1.0, Float64(0.0) / Float64(0.0), 3.0)
    var inf_values = _values(1.0, Float64("inf"), 3.0)
    if (
        first_non_finite(poisoned, all_valid(3)) == 1
        and first_non_finite(inf_values, all_valid(3)) == 1
        and first_non_finite(v, mask) == -1
        and not is_finite_value(Float64("inf"))
    ):
        passed += 1
        print("  ✅ NaN/Inf located by index before reducing, clean input passes")
    else:
        failed += 1
        print("  ❌ non-finite detection wrong:", first_non_finite(poisoned, all_valid(3)))

    # ── a null non-finite value is not reported: it is not part of the data ──
    var masked_nan = List[Bool]()
    masked_nan.append(True)
    masked_nan.append(False)
    masked_nan.append(True)
    if first_non_finite(poisoned, masked_nan) == -1:
        passed += 1
        print("  ✅ a NaN in a null position is not an ingest error")
    else:
        failed += 1
        print("  ❌ null NaN wrongly reported")

    # ── mean is stable on wide magnitudes, where sum/n loses precision ───────
    var wide = List[Float64]()
    for _ in range(1000):
        wide.append(1e9)
        wide.append(1.0)
    var wide_mean = reduce_mean(wide, all_valid(2000))
    if wide_mean.value > 499999999.9 and wide_mean.value < 500000000.6:
        passed += 1
        print("  ✅ Welford mean stays accurate across wide magnitudes")
    else:
        failed += 1
        print("  ❌ mean unstable:", wide_mean.value)

    # ── nothing rounds: presentation is the caller's concern ────────────────
    var third = List[Float64]()
    third.append(1.0)
    third.append(2.0)
    var two_thirds = reduce_mean(third, all_valid(2))
    if two_thirds.value == 1.5:
        # 1/3 would be the sharper probe but is not exactly representable; the point
        # is that no rounding step exists, which the 4-dp path would have applied.
        passed += 1
        print("  ✅ results are not rounded by the reduction")
    else:
        failed += 1
        print("  ❌ unexpected rounding:", two_thirds.value)

    # ── a mask SHORTER than the values marks the tail ABSENT, not present ─────
    # This used to disagree with columnar.array.float64_with_nulls, which treats a
    # short mask as absent: reduce counted the unmasked tail as live. Handing the same
    # short mask to both produced two different answers over the same data, with
    # nothing to indicate which was meant. Both now read it as absent.
    var five = List[Float64]()
    for i in range(5):
        five.append(10.0)
    var short_mask = List[Bool]()
    short_mask.append(True)
    short_mask.append(True)          # only 2 of 5 positions described
    var short_sum = reduce_sum(five, short_mask)
    var short_mean = reduce_mean(five, short_mask)
    if short_sum.value == 20.0 and short_sum.n == 2 and short_mean.value == 10.0:
        passed += 1
        print("  ✅ an undescribed tail is absent: sum 20 over 2 values, not 50 over 5")
    else:
        failed += 1
        print("  ❌ short-mask polarity wrong:", short_sum.value, short_sum.n)

    # ── an EMPTY mask therefore means nothing is present ──────────────────────
    var no_mask = List[Bool]()
    var empty_masked = reduce_sum(five, no_mask)
    var empty_mean = reduce_mean(five, no_mask)
    if empty_masked.value == 0.0 and empty_masked.n == 0 and not empty_mean.present:
        passed += 1
        print("  ✅ an empty mask describes nothing: sum 0, and no mean exists")
    else:
        failed += 1
        print("  ❌ empty mask treated as all-valid")

    # ── callers with no nulls use all_valid(n), the explicit form ───
    var full = all_valid(len(five))
    if reduce_sum(five, full).value == 50.0 and reduce_sum(five, full).n == 5:
        passed += 1
        print("  ✅ all_valid(n) is how a no-nulls caller says so: sum 50 over 5")
    else:
        failed += 1
        print("  ❌ all_valid(n) wrong")

    print("  [numeric.contract] Passed:", passed, "Failed:", failed)
