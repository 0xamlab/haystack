"""test_query_aggregate.mojo — known-value tests for the one-pass hash aggregate.

Hand-written. This driver is the first caller the frozen pandas_groupby primitives
have ever had, so the assertions check the maths against hand-computed values, and
check the two decisions the existing group-by paths get differently: a null key does
not become a category, and a group with nothing to average has no answer rather
than 0.0.
"""
from std.math import isnan, sqrt
from std.memory import bitcast

from columnar.array import (
    Float64Array,
    Int64Array,
    float64_from_list,
    float64_with_nulls,
    int64_from_list,
    int64_with_nulls,
)
from columnar.batch import RecordBatch, schema_of
from numeric.contract import (
    AGG_AVG,
    AGG_COUNT,
    AGG_MAX,
    AGG_MIN,
    AGG_STD,
    AGG_SUM,
    AGG_VAR,
)
from query.aggregate import (
    GroupAccumulator,
    GroupedResult,
    IntGroupedResult,
    aggregate_column,
    aggregate_column_present,
    find_group,
    find_group_int64,
    group_by,
    group_by_int64,
    group_by_multi,
    grouped_to_column,
)


fn _batch() -> RecordBatch:
    """region = [1,1,2,2,2,null];  amount = [10,20,30,40,null,100]."""
    var region = List[Float64]()
    region.append(1.0)
    region.append(1.0)
    region.append(2.0)
    region.append(2.0)
    region.append(2.0)
    region.append(0.0)  # null key
    var region_mask = List[Bool]()
    for _ in range(5):
        region_mask.append(True)
    region_mask.append(False)

    var amount = List[Float64]()
    amount.append(10.0)
    amount.append(20.0)
    amount.append(30.0)
    amount.append(40.0)
    amount.append(0.0)  # null value
    amount.append(100.0)
    var amount_mask = List[Bool]()
    amount_mask.append(True)
    amount_mask.append(True)
    amount_mask.append(True)
    amount_mask.append(True)
    amount_mask.append(False)
    amount_mask.append(True)

    var names = List[String]()
    names.append("region")
    names.append("amount")
    var cols = List[Float64Array]()
    cols.append(float64_with_nulls(region^, region_mask))
    cols.append(float64_with_nulls(amount^, amount_mask))
    return RecordBatch(schema_of(names^), cols^, 6)


fn _group_index(result: GroupedResult, key: Float64) -> Int:
    """Locate a group by key, so the assertions never depend on insertion order."""
    for i in range(len(result.keys)):
        if result.keys[i] == key:
            return i
    return -1


fn main() raises:
    var passed = 0
    var failed = 0
    var batch = _batch()

    # ── sums per group, with the null-key row excluded ────────────────────────
    var sums = group_by(batch, 0, 1, AGG_SUM)
    var g1 = _group_index(sums, 1.0)
    var g2 = _group_index(sums, 2.0)
    if (
        sums.n_groups() == 2
        and sums.null_key_rows == 1
        and sums.values[g1] == 30.0   # 10 + 20
        and sums.values[g2] == 70.0   # 30 + 40, the null value contributes nothing
    ):
        passed += 1
        print("  ✅ sums 30 and 70 per group; the null-key row is excluded")
    else:
        failed += 1
        print("  ❌ grouped sum wrong:", sums.n_groups(), sums.null_key_rows)

    # ── a null key does NOT become its own category ───────────────────────────
    # 100.0 sits behind a null key; folding it into a group would invent a category,
    # and folding it into key 0.0 (the value `get` returns for an absent slot) would
    # be worse still — a group named after the type's zero.
    if _group_index(sums, 0.0) == -1 and sums.values[g1] + sums.values[g2] == 100.0:
        passed += 1
        print("  ✅ a null key forms no group, and its value is not counted anywhere")
    else:
        failed += 1
        print("  ❌ null key leaked into a group")

    # ── counts skip null values but keep the row's group ──────────────────────
    var counts = group_by(batch, 0, 1, AGG_COUNT)
    if counts.values[_group_index(counts, 1.0)] == 2.0 and counts.values[
        _group_index(counts, 2.0)
    ] == 2.0:
        passed += 1
        print("  ✅ group 2 counts 2, not 3 — the null value is not counted")
    else:
        failed += 1
        print("  ❌ counts wrong:", counts.values[_group_index(counts, 2.0)])

    # ── means computed by the frozen Welford primitive ────────────────────────
    var means = group_by(batch, 0, 1, AGG_AVG)
    if means.values[_group_index(means, 1.0)] == 15.0 and means.values[
        _group_index(means, 2.0)
    ] == 35.0:
        passed += 1
        print("  ✅ means 15 and 35 via the frozen Welford update")
    else:
        failed += 1
        print("  ❌ grouped mean wrong")

    # ── min and max per group ────────────────────────────────────────────────
    var mins = group_by(batch, 0, 1, AGG_MIN)
    var maxs = group_by(batch, 0, 1, AGG_MAX)
    if (
        mins.values[_group_index(mins, 1.0)] == 10.0
        and maxs.values[_group_index(maxs, 1.0)] == 20.0
        and mins.values[_group_index(mins, 2.0)] == 30.0
        and maxs.values[_group_index(maxs, 2.0)] == 40.0
    ):
        passed += 1
        print("  ✅ min/max per group are 10/20 and 30/40")
    else:
        failed += 1
        print("  ❌ min/max wrong")

    # ── sample variance and stddev, hand-checked ──────────────────────────────
    # Group 1 = [10, 20]: mean 15, deviations ±5 -> M2 = 50, var = 50/1 = 50.
    var vars_out = group_by(batch, 0, 1, AGG_VAR)
    var stds_out = group_by(batch, 0, 1, AGG_STD)
    var v1 = vars_out.values[_group_index(vars_out, 1.0)]
    var s1 = stds_out.values[_group_index(stds_out, 1.0)]
    if v1 > 49.99 and v1 < 50.01 and s1 > 7.07 and s1 < 7.072:
        passed += 1
        print("  ✅ sample variance 50 and stddev 7.071 for [10,20]")
    else:
        failed += 1
        print("  ❌ variance/stddev wrong:", v1, s1)

    # ── a group with a single observation has no variance ─────────────────────
    var single_region = List[Float64]()
    single_region.append(7.0)
    var single_amount = List[Float64]()
    single_amount.append(5.0)
    var single_names = List[String]()
    single_names.append("region")
    single_names.append("amount")
    var single_cols = List[Float64Array]()
    single_cols.append(float64_from_list(single_region^))
    single_cols.append(float64_from_list(single_amount^))
    var single = RecordBatch(schema_of(single_names^), single_cols^, 1)
    var single_var = group_by(single, 0, 1, AGG_VAR)
    if not single_var.present[0] and group_by(single, 0, 1, AGG_AVG).present[0]:
        passed += 1
        print("  ✅ one observation has a mean but no variance, rather than 0.0")
    else:
        failed += 1
        print("  ❌ single-observation variance wrong")

    # ── a group whose values are ALL null has no mean ─────────────────────────
    var allnull_keys = List[Float64]()
    allnull_keys.append(5.0)
    allnull_keys.append(5.0)
    var allnull_vals = List[Float64]()
    allnull_vals.append(0.0)
    allnull_vals.append(0.0)
    var allnull_mask = List[Bool]()
    allnull_mask.append(False)
    allnull_mask.append(False)
    var an_names = List[String]()
    an_names.append("region")
    an_names.append("amount")
    var an_cols = List[Float64Array]()
    an_cols.append(float64_from_list(allnull_keys^))
    an_cols.append(float64_with_nulls(allnull_vals^, allnull_mask))
    var an_batch = RecordBatch(schema_of(an_names^), an_cols^, 2)
    var an_mean = group_by(an_batch, 0, 1, AGG_AVG)
    var an_count = group_by(an_batch, 0, 1, AGG_COUNT)
    var an_sum = group_by(an_batch, 0, 1, AGG_SUM)
    if (
        an_mean.n_groups() == 1
        and not an_mean.present[0]          # no mean exists
        and an_count.present[0]
        and an_count.values[0] == 0.0       # but the count is a real 0
        and an_sum.present[0]
        and an_sum.values[0] == 0.0         # and the sum is a real 0
    ):
        passed += 1
        print("  ✅ an all-null group: count 0 and sum 0 are answers, mean is absent")
    else:
        failed += 1
        print("  ❌ all-null group wrong")

    # ── absences survive into the result column ──────────────────────────────
    var as_column = grouped_to_column(an_mean)
    if as_column.length == 1 and not as_column.is_valid_at(0):
        passed += 1
        print("  ✅ an absent group value becomes a null in the result column")
    else:
        failed += 1
        print("  ❌ absence lost when converting to a column")

    # ── ungrouped aggregation over the whole column ──────────────────────────
    # Live amounts are 10,20,30,40,100 -> sum 200, mean 40, count 5. The null-key row
    # counts here: a null KEY only matters when there is a grouping.
    if (
        aggregate_column(batch, 1, AGG_SUM) == 200.0
        and aggregate_column(batch, 1, AGG_COUNT) == 5.0
        and aggregate_column(batch, 1, AGG_AVG) == 40.0
    ):
        passed += 1
        print("  ✅ ungrouped: sum 200, count 5, mean 40 over every live value")
    else:
        failed += 1
        print("  ❌ ungrouped aggregate wrong:", aggregate_column(batch, 1, AGG_SUM))

    # ── an empty column has no mean but a real count of 0 ────────────────────
    var empty_names = List[String]()
    empty_names.append("v")
    var empty_cols = List[Float64Array]()
    var no_values = List[Float64]()
    empty_cols.append(float64_from_list(no_values^))
    var empty_batch = RecordBatch(schema_of(empty_names^), empty_cols^, 0)
    if (
        not aggregate_column_present(empty_batch, 0, AGG_AVG)
        and aggregate_column_present(empty_batch, 0, AGG_COUNT)
        and aggregate_column(empty_batch, 0, AGG_COUNT) == 0.0
    ):
        passed += 1
        print("  ✅ an empty column: count 0 is an answer, mean is not")
    else:
        failed += 1
        print("  ❌ empty-column policy wrong")

    # ── one pass answers several aggregations from the same accumulator ───────
    var acc = GroupAccumulator(0.0)
    acc.observe(2.0)
    acc.observe(4.0)
    acc.observe(6.0)
    if (
        acc.value_for(AGG_SUM) == 12.0
        and acc.value_for(AGG_AVG) == 4.0
        and acc.value_for(AGG_MIN) == 2.0
        and acc.value_for(AGG_MAX) == 6.0
        and acc.value_for(AGG_COUNT) == 3.0
        and acc.value_for(AGG_VAR) > 3.99
        and acc.value_for(AGG_VAR) < 4.01
    ):
        passed += 1
        print("  ✅ one accumulator answers sum/mean/min/max/count/var in a single pass")
    else:
        failed += 1
        print("  ❌ accumulator wrong:", acc.value_for(AGG_VAR))

    # ── the describe line names the aggregation and the null-key count ────────
    if sums.describe().find("sum over 2 groups") >= 0 and sums.describe().find(
        "1 rows had a null key"
    ) >= 0:
        passed += 1
        print("  ✅ describe reports the aggregation and the excluded null keys")
    else:
        failed += 1
        print("  ❌ describe wrong:", sums.describe())

    # ── the hash path agrees with the linear scan over many groups ────────────
    # group_by resolves slots through columnar.hash_index; find_group is the linear
    # equivalent it replaced. Over 300 groups they must produce identical group sets
    # and identical per-group sums, or the speed-up changed the answer.
    var many_keys = List[Float64]()
    var many_values = List[Float64]()
    for i in range(3000):
        many_keys.append(Float64(i % 317) * 0.25)
        many_values.append(Float64(i % 13) + 0.5)
    var many_names = List[String]()
    many_names.append("k")
    many_names.append("v")
    var many_cols = List[Float64Array]()
    many_cols.append(float64_from_list(many_keys^))
    many_cols.append(float64_from_list(many_values^))
    var many = RecordBatch(schema_of(many_names^), many_cols^, 3000)
    var hashed = group_by(many, 0, 1, AGG_SUM)

    # The same grouping via the linear scan, computed here independently.
    var linear_keys = List[Float64]()
    var linear_sums = List[Float64]()
    var key_column = many.column(0)
    var value_column = many.column(1)
    for r in range(many.n_rows):
        var k = key_column.get(r)
        var slot = find_group(linear_keys, k)
        if slot < 0:
            linear_keys.append(k)
            linear_sums.append(0.0)
            slot = len(linear_keys) - 1
        linear_sums[slot] = linear_sums[slot] + value_column.get(r)

    var paths_agree = hashed.n_groups() == len(linear_keys)
    if paths_agree:
        for i in range(len(linear_keys)):
            var hashed_slot = _group_index(hashed, linear_keys[i])
            if hashed_slot < 0:
                paths_agree = False
            elif hashed.values[hashed_slot] != linear_sums[i]:
                paths_agree = False
    if paths_agree and hashed.n_groups() == 317:
        passed += 1
        print(
            "  ✅ hash and linear grouping agree exactly over 317 groups / 3000 rows"
        )
    else:
        failed += 1
        print(
            "  ❌ hash and linear grouping disagree:",
            hashed.n_groups(),
            len(linear_keys),
        )

    # ── group keys keep insertion order, so results are reproducible ──────────
    # Table layout must not leak into the output ordering, or two runs of the same
    # plan produce the same numbers in a different order and diffing them fails.
    var order_stable = True
    for i in range(hashed.n_groups()):
        if hashed.keys[i] != Float64(i % 317) * 0.25:
            order_stable = False
    if order_stable:
        passed += 1
        print("  ✅ groups come back in first-seen order, not hash-table order")
    else:
        failed += 1
        print("  ❌ group order depends on table layout")

    # ── -0.0 does not open a second group ────────────────────────────────────
    var signed_keys = List[Float64]()
    signed_keys.append(0.0)
    signed_keys.append(-0.0)
    signed_keys.append(0.0)
    var signed_values = List[Float64]()
    signed_values.append(1.0)
    signed_values.append(2.0)
    signed_values.append(3.0)
    var signed_names = List[String]()
    signed_names.append("k")
    signed_names.append("v")
    var signed_cols = List[Float64Array]()
    signed_cols.append(float64_from_list(signed_keys^))
    signed_cols.append(float64_from_list(signed_values^))
    var signed = RecordBatch(schema_of(signed_names^), signed_cols^, 3)
    var signed_sum = group_by(signed, 0, 1, AGG_SUM)
    if signed_sum.n_groups() == 1 and signed_sum.values[0] == 6.0:
        passed += 1
        print("  ✅ a -0.0 key joins the +0.0 group; one group totalling 6")
    else:
        failed += 1
        print("  ❌ -0.0 split the zero group:", signed_sum.n_groups())

    # ── multi-column grouping ────────────────────────────────────────────────
    # region x channel: (1,1)=10+30, (1,2)=20, (2,1)=40, and one row with a null
    # channel that belongs to no group.
    var mregion = List[Float64]()
    var mchannel = List[Float64]()
    var mamount = List[Float64]()
    mregion.append(1.0); mchannel.append(1.0); mamount.append(10.0)
    mregion.append(1.0); mchannel.append(2.0); mamount.append(20.0)
    mregion.append(1.0); mchannel.append(1.0); mamount.append(30.0)
    mregion.append(2.0); mchannel.append(1.0); mamount.append(40.0)
    mregion.append(1.0); mchannel.append(0.0); mamount.append(50.0)
    var channel_mask = List[Bool]()
    for _ in range(4):
        channel_mask.append(True)
    channel_mask.append(False)  # the last row's channel is unknown

    var mnames = List[String]()
    mnames.append("region")
    mnames.append("channel")
    mnames.append("amount")
    var mcols = List[Float64Array]()
    mcols.append(float64_from_list(mregion^))
    mcols.append(float64_with_nulls(mchannel^, channel_mask))
    mcols.append(float64_from_list(mamount^))
    var mbatch = RecordBatch(schema_of(mnames^), mcols^, 5)

    var key_cols = List[Int]()
    key_cols.append(0)
    key_cols.append(1)
    var multi = group_by_multi(mbatch, key_cols, 2, AGG_SUM)
    if (
        multi.n_groups() == 3
        and multi.null_key_rows == 1
        and multi.values[0] == 40.0   # (1,1) = 10 + 30
        and multi.values[1] == 20.0   # (1,2)
        and multi.values[2] == 40.0   # (2,1)
    ):
        passed += 1
        print("  ✅ (region, channel) yields 3 groups: 40, 20, 40")
    else:
        failed += 1
        print("  ❌ multi-column grouping wrong:", multi.n_groups(), multi.null_key_rows)

    # ── one null key column excludes the row entirely ─────────────────────────
    # (region=1, channel=null) is not part of region 1: it is a row whose group is
    # unknown. Folding it under region 1 would report a total nobody can attribute.
    var region1_total = multi.values[0] + multi.values[1]
    if region1_total == 60.0 and multi.null_key_rows == 1:
        passed += 1
        print("  ✅ a row with one unknown key column joins no group (region 1 = 60)")
    else:
        failed += 1
        print("  ❌ a partially-null key leaked into a group:", region1_total)

    # ── the key tuple is recoverable from the result ──────────────────────────
    var tuple_1_2 = multi.key_at(1)
    if (
        multi.key_width == 2
        and len(tuple_1_2) == 2
        and tuple_1_2[0] == 1.0
        and tuple_1_2[1] == 2.0
    ):
        passed += 1
        print("  ✅ key_at names a group by its full tuple")
    else:
        failed += 1
        print("  ❌ key_at wrong")

    # ── no key columns is one group over everything, not zero groups ──────────
    var no_keys = List[Int]()
    var ungrouped = group_by_multi(mbatch, no_keys, 2, AGG_SUM)
    if (
        ungrouped.n_groups() == 0          # no key tuples exist to name
        and len(ungrouped.values) == 1     # but there is exactly one answer
        and ungrouped.values[0] == 150.0   # 10+20+30+40+50, every live value
        and ungrouped.present[0]
    ):
        passed += 1
        print("  ✅ grouping by no columns totals everything once: 150")
    else:
        failed += 1
        print("  ❌ empty key list wrong:", len(ungrouped.values))

    # ── NaN VALUES: excluded from min/max, wherever they sit in the scan ──────
    # The policy in the module header ("NaN values and the extrema"). The bite:
    # before it, a NaN that arrived FIRST seeded min/max and stuck (x < NaN is
    # false in the frozen updates), so [NaN, 1, 2] reported min = NaN while
    # [1, NaN, 2] reported 1.0 — an order-dependent fold. Now both report 1.0.
    var nan = sqrt(Float64(-1.0))
    var nkeys = List[Float64]()
    var nvalues = List[Float64]()
    for _ in range(3):
        nkeys.append(7.0)
    nvalues.append(nan)
    nvalues.append(1.0)
    nvalues.append(2.0)
    var nnames = List[String]()
    nnames.append("k")
    nnames.append("v")
    var ncols = List[Float64Array]()
    ncols.append(float64_from_list(nkeys^))
    ncols.append(float64_from_list(nvalues^))
    var nan_first = RecordBatch(schema_of(nnames^), ncols^, 3)
    var nf_min = group_by(nan_first, 0, 1, AGG_MIN)
    var nf_max = group_by(nan_first, 0, 1, AGG_MAX)
    var nf_count = group_by(nan_first, 0, 1, AGG_COUNT)
    var nf_sum = group_by(nan_first, 0, 1, AGG_SUM)
    if (
        nf_min.values[0] == 1.0
        and nf_max.values[0] == 2.0
        and nf_count.values[0] == 3.0      # a NaN value still counts
        and isnan(nf_sum.values[0])        # and still poisons the sum
    ):
        passed += 1
        print("  ✅ a NaN value that arrives first names no extremum: min 1, max 2")
    else:
        failed += 1
        print("  ❌ NaN-first extrema wrong:", nf_min.values[0], nf_max.values[0])

    # ── all-NaN group: min/max are the CANONICAL quiet NaN, present ───────────
    # And one live value after two NaNs must claim both extrema — the old fold
    # kept the seeded NaN forever, so 5.0 could never take over.
    var acc_nan = GroupAccumulator(1.0)
    acc_nan.observe(nan)
    acc_nan.observe(nan)
    var all_nan_min = acc_nan.value_for(AGG_MIN)
    var all_nan_max = acc_nan.value_for(AGG_MAX)
    acc_nan.observe(5.0)
    if (
        bitcast[DType.uint64](all_nan_min) == 0x7FF8000000000000
        and bitcast[DType.uint64](all_nan_max) == 0x7FF8000000000000
        and acc_nan.has_answer(AGG_MIN)
        and acc_nan.value_for(AGG_MIN) == 5.0
        and acc_nan.value_for(AGG_MAX) == 5.0
        and acc_nan.count == 3.0
    ):
        passed += 1
        print("  ✅ all-NaN min/max = one canonical NaN; a later live value takes over")
    else:
        failed += 1
        print(
            "  ❌ all-NaN extrema policy wrong:",
            all_nan_min,
            acc_nan.value_for(AGG_MIN),
        )

    # ── int64-columnar-fidelity: TODAY's corruption, through the real aggregate path ──
    # This is what ingest already produces for two distinct Int64 ids above 2^53: both
    # collapse to the SAME Float64 (`9007199254740992.0`) before `group_by` ever sees
    # them, because a double's mantissa holds only 53 bits of integer precision. Two
    # source rows that should be two groups become one. This is `group_by` working
    # exactly as designed on a Float64 key column — the bug is upstream of this
    # function, in whatever coerced an Int64 id to Float64 before it arrived — but the
    # visible, measurable damage happens here: a silently doubled count and sum.
    var collided_key = List[Float64]()
    collided_key.append(9007199254740992.0)  # what 2^53   widens to
    collided_key.append(9007199254740992.0)  # what 2^53+1 widens to — SAME double
    var collided_value = List[Float64]()
    collided_value.append(1.0)
    collided_value.append(1.0)
    var collided_names = List[String]()
    collided_names.append("id")
    collided_names.append("amount")
    var collided_cols = List[Float64Array]()
    collided_cols.append(float64_from_list(collided_key^))
    collided_cols.append(float64_from_list(collided_value^))
    var collided_batch = RecordBatch(schema_of(collided_names^), collided_cols^, 2)
    var corrupted = group_by(collided_batch, 0, 1, AGG_SUM)
    var corrupted_count = group_by(collided_batch, 0, 1, AGG_COUNT)
    if (
        corrupted.n_groups() == 1
        and corrupted.values[0] == 2.0            # sum silently doubled: 1.0 + 1.0
        and corrupted_count.values[0] == 2.0      # two distinct ids counted as one
    ):
        passed += 1
        print("  ✅ TODAY: two distinct Int64 ids widened to Float64 merge into 1 group, sum doubles — the corruption, measured")
    else:
        failed += 1
        print("  ❌ the Float64-keyed collision did not reproduce — has group_by's keying changed?", corrupted.n_groups(), corrupted.values[0])

    # ── the fix: group_by_int64 keeps the same two ids as two groups ────────────────
    var exact_keys = List[Int]()
    exact_keys.append(9007199254740992)  # 2^53
    exact_keys.append(9007199254740993)  # 2^53 + 1 — DISTINCT from the row above
    var exact_values = List[Float64]()
    exact_values.append(1.0)
    exact_values.append(1.0)
    var exact_keys_2 = List[Int]()
    exact_keys_2.append(9007199254740992)
    exact_keys_2.append(9007199254740993)
    var exact_values_2 = List[Float64]()
    exact_values_2.append(1.0)
    exact_values_2.append(1.0)
    var fixed = group_by_int64(int64_from_list(exact_keys^), float64_from_list(exact_values^), AGG_SUM)
    var fixed_count = group_by_int64(
        int64_from_list(exact_keys_2^), float64_from_list(exact_values_2^), AGG_COUNT
    )
    var fg1 = find_group_int64(fixed.keys, 9007199254740992)
    var fg2 = find_group_int64(fixed.keys, 9007199254740993)
    if (
        fixed.n_groups() == 2
        and fg1 != -1 and fg2 != -1 and fg1 != fg2
        and fixed.values[fg1] == 1.0
        and fixed.values[fg2] == 1.0
        and fixed.keys[fg1] == 9007199254740992
        and fixed.keys[fg2] == 9007199254740993
        and fixed_count.n_groups() == 2
        and fixed_count.values[find_group_int64(fixed_count.keys, 9007199254740992)] == 1.0
        and fixed_count.values[find_group_int64(fixed_count.keys, 9007199254740993)] == 1.0
    ):
        passed += 1
        print("  ✅ FIXED: group_by_int64 keeps 2^53 and 2^53+1 as two groups, sum/count exact")
    else:
        failed += 1
        print("  ❌ group_by_int64 merged the two ids:", fixed.n_groups(), fg1, fg2)

    # ── group_by_int64 keeps group_by's null-key / null-value policy ────────────────
    var null_keys = List[Int]()
    null_keys.append(1)
    null_keys.append(2)
    null_keys.append(2)
    var key_mask = List[Bool]()
    key_mask.append(False)  # null key: excluded from every group
    key_mask.append(True)
    key_mask.append(True)
    var null_key_col = int64_with_nulls(null_keys^, key_mask)
    var val_list = List[Float64]()
    val_list.append(100.0)  # sits behind the null key; must not join any group
    val_list.append(10.0)
    val_list.append(0.0)
    var val_mask = List[Bool]()
    val_mask.append(True)
    val_mask.append(True)
    val_mask.append(False)  # null value: row still joins the group, contributes nothing
    var value_col2 = float64_with_nulls(val_list^, val_mask)
    var with_nulls = group_by_int64(null_key_col, value_col2, AGG_SUM)
    var with_nulls_count = group_by_int64(null_key_col, value_col2, AGG_COUNT)
    var wg2 = find_group_int64(with_nulls.keys, 2)
    if (
        with_nulls.n_groups() == 1               # key 1 excluded (null); only key 2 remains
        and with_nulls.null_key_rows == 1
        and find_group_int64(with_nulls.keys, 1) == -1
        and wg2 != -1
        and with_nulls.values[wg2] == 10.0         # the null value contributes nothing
        # matches group_by exactly (see this file's first test, "group 2 counts 2, not
        # 3 — the null value is not counted"): AGG_COUNT counts valid VALUES observed,
        # not rows in the group, so key 2's null-value row (row 2) is excluded from 1.0.
        and with_nulls_count.values[find_group_int64(with_nulls_count.keys, 2)] == 1.0
    ):
        passed += 1
        print("  ✅ group_by_int64: null key excluded, null value counted but not summed — matches group_by")
    else:
        failed += 1
        print("  ❌ group_by_int64 null policy wrong:", with_nulls.n_groups(), with_nulls.null_key_rows)

    print("  [query.aggregate] Passed:", passed, "Failed:", failed)
