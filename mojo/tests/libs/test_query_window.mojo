"""test_query_window.mojo — known-value tests for partitioned window functions.

Hand-written. Two failures here are plausible-looking wrong numbers rather than errors,
so they carry the most assertions:

  * a lag/lead or a frame that reads across a partition boundary — last December's
    figure attributed to a different region, with nothing to indicate it;
  * rank and dense_rank swapped — identical output until a tie appears.

Both are checked on data built specifically to expose them: adjacent partitions with
distinctive values, and a tie in the middle of a partition.
"""
from columnar.array import Float64Array, float64_from_list, float64_with_nulls
from columnar.batch import RecordBatch, schema_of
from numeric.contract import AGG_AVG, AGG_COUNT, AGG_MAX, AGG_MIN, AGG_SUM
from query.window import (
    FRAME_UNBOUNDED,
    NO_ROW,
    Partitions,
    cumulative,
    dense_rank,
    describe_partitions,
    framed_aggregate,
    lag_lead,
    partition_rows,
    partition_total,
    rank,
    row_number,
)


fn _batch(
    var names: List[String], var cols: List[Float64Array], n: Int
) -> RecordBatch:
    return RecordBatch(schema_of(names^), cols^, n)


fn _sales() -> RecordBatch:
    """Two regions, deliberately interleaved so a boundary bug shows up.

        row  region  month  amount
        0    1       1      100
        1    2       1      999      <- a distinctive neighbour value
        2    1       2      200
        3    1       3      200      <- ties with row 2 on amount
        4    2       2      888
        5    1       4      400
    """
    var region = List[Float64]()
    var month = List[Float64]()
    var amount = List[Float64]()
    region.append(1.0); month.append(1.0); amount.append(100.0)
    region.append(2.0); month.append(1.0); amount.append(999.0)
    region.append(1.0); month.append(2.0); amount.append(200.0)
    region.append(1.0); month.append(3.0); amount.append(200.0)
    region.append(2.0); month.append(2.0); amount.append(888.0)
    region.append(1.0); month.append(4.0); amount.append(400.0)

    var names = List[String]()
    names.append("region")
    names.append("month")
    names.append("amount")
    var cols = List[Float64Array]()
    cols.append(float64_from_list(region^))
    cols.append(float64_from_list(month^))
    cols.append(float64_from_list(amount^))
    return _batch(names^, cols^, 6)


fn _partitions(batch: RecordBatch) -> Partitions:
    var by = List[Int]()
    by.append(0)  # region
    var order = List[Int]()
    order.append(1)  # month ascending
    var desc = List[Bool]()
    desc.append(False)
    return partition_rows(batch, by, order, desc, True)


fn main() raises:
    var passed = 0
    var failed = 0
    var sales = _sales()
    var parts = _partitions(sales)

    # ── partitioning: two regions, ordered by month within each ──────────────
    if (
        parts.count() == 2
        and parts.lengths[0] == 4
        and parts.lengths[1] == 2
        and parts.row_at(0, 0) == 0
        and parts.row_at(0, 1) == 2
        and parts.row_at(0, 2) == 3
        and parts.row_at(0, 3) == 5
        and parts.row_at(1, 0) == 1
        and parts.row_at(1, 1) == 4
    ):
        passed += 1
        print("  ✅ 2 partitions: region 1 = rows 0,2,3,5 and region 2 = rows 1,4")
    else:
        failed += 1
        print("  ❌ partitioning wrong:", parts.count(), parts.lengths[0])

    # ── row_at refuses to leave the partition ────────────────────────────────
    # The single boundary check every frame and offset goes through.
    if (
        parts.row_at(0, 4) == NO_ROW
        and parts.row_at(0, -1) == NO_ROW
        and parts.row_at(1, 2) == NO_ROW
        and parts.row_at(9, 0) == NO_ROW
    ):
        passed += 1
        print("  ✅ row_at past either edge, or a bad partition, is NO_ROW")
    else:
        failed += 1
        print("  ❌ row_at leaked past a partition edge")

    if parts.partition_of(4) == 1 and parts.partition_of(0) == 0:
        passed += 1
        print("  ✅ partition_of maps rows back to their partition")
    else:
        failed += 1
        print("  ❌ partition_of wrong")

    # ── row_number is 1-based within the partition ───────────────────────────
    var rn = row_number(sales, parts)
    if (
        rn.get(0) == 1.0
        and rn.get(2) == 2.0
        and rn.get(3) == 3.0
        and rn.get(5) == 4.0
        and rn.get(1) == 1.0   # region 2 restarts at 1
        and rn.get(4) == 2.0
    ):
        passed += 1
        print("  ✅ row_number restarts at 1 in each partition")
    else:
        failed += 1
        print("  ❌ row_number wrong:", rn.get(1))

    # ── lag stops at the partition edge ──────────────────────────────────────
    # Row 1 is region 2's first month. In row order its predecessor is row 0, which is
    # region 1 with amount 100. If lag crossed the boundary it would report 100 as
    # region 2's previous month — plausible and wrong.
    var lag1 = lag_lead(sales, parts, 2, -1)
    if not lag1.is_valid_at(0) and not lag1.is_valid_at(1):
        passed += 1
        print("  ✅ lag(1) is null for the first row of BOTH partitions")
    else:
        failed += 1
        print("  ❌ lag crossed a partition boundary:", lag1.get(1))

    if lag1.get(2) == 100.0 and lag1.get(3) == 200.0 and lag1.get(5) == 200.0:
        passed += 1
        print("  ✅ lag(1) within region 1 reads 100, 200, 200 in month order")
    else:
        failed += 1
        print("  ❌ lag values wrong:", lag1.get(2))

    if lag1.get(4) == 999.0:
        passed += 1
        print("  ✅ region 2's second month lags to 999, its own first month")
    else:
        failed += 1
        print("  ❌ lag in region 2 wrong:", lag1.get(4))

    # ── lead stops at the other edge ─────────────────────────────────────────
    var lead1 = lag_lead(sales, parts, 2, 1)
    if (
        not lead1.is_valid_at(5)   # region 1's last month
        and not lead1.is_valid_at(4)  # region 2's last month
        and lead1.get(0) == 200.0
        and lead1.get(1) == 888.0
    ):
        passed += 1
        print("  ✅ lead(1) is null at each partition's last row")
    else:
        failed += 1
        print("  ❌ lead crossed a boundary or is wrong:", lead1.get(4))

    # ── offset 0 is the row's own value ──────────────────────────────────────
    var self_ref = lag_lead(sales, parts, 2, 0)
    if self_ref.get(0) == 100.0 and self_ref.get(4) == 888.0:
        passed += 1
        print("  ✅ offset 0 returns the row's own value")
    else:
        failed += 1
        print("  ❌ offset 0 wrong")

    # ── a lag of 2 also respects the edge ────────────────────────────────────
    var lag2 = lag_lead(sales, parts, 2, -2)
    if (
        not lag2.is_valid_at(0)
        and not lag2.is_valid_at(2)
        and lag2.get(3) == 100.0
        and not lag2.is_valid_at(4)  # region 2 has only 2 rows
    ):
        passed += 1
        print("  ✅ lag(2) is null until a partition has two predecessors")
    else:
        failed += 1
        print("  ❌ lag(2) wrong")

    # ── rank GAPS after a tie, dense_rank does not ───────────────────────────
    # Region 1's amounts in month order are 100, 200, 200, 400.
    #   rank       -> 1, 2, 2, 4
    #   dense_rank -> 1, 2, 2, 3
    # These differ in exactly one cell. Swapping them is invisible without a tie.
    var r = rank(sales, parts, 2)
    var dr = dense_rank(sales, parts, 2)
    if (
        r.get(0) == 1.0
        and r.get(2) == 2.0
        and r.get(3) == 2.0
        and r.get(5) == 4.0
    ):
        passed += 1
        print("  ✅ rank gives 1,2,2,4 — the gap after the tie is present")
    else:
        failed += 1
        print("  ❌ rank wrong:", r.get(0), r.get(2), r.get(3), r.get(5))

    if (
        dr.get(0) == 1.0
        and dr.get(2) == 2.0
        and dr.get(3) == 2.0
        and dr.get(5) == 3.0
    ):
        passed += 1
        print("  ✅ dense_rank gives 1,2,2,3 — no gap")
    else:
        failed += 1
        print("  ❌ dense_rank wrong:", dr.get(5))

    if r.get(5) != dr.get(5):
        passed += 1
        print("  ✅ rank and dense_rank actually differ on the tied data")
    else:
        failed += 1
        print("  ❌ rank and dense_rank are identical — one is wrong")

    # ── ranks restart per partition ──────────────────────────────────────────
    if r.get(1) == 1.0 and r.get(4) == 2.0:
        passed += 1
        print("  ✅ ranks restart at 1 in region 2")
    else:
        failed += 1
        print("  ❌ ranks did not restart")

    # ── cumulative sum stops at the partition start ──────────────────────────
    # Region 2's first row must be 999, not 999+100.
    var running = cumulative(sales, parts, 2, AGG_SUM)
    if (
        running.get(0) == 100.0
        and running.get(2) == 300.0
        and running.get(3) == 500.0
        and running.get(5) == 900.0
        and running.get(1) == 999.0
        and running.get(4) == 1887.0
    ):
        passed += 1
        print("  ✅ cumulative sum: 100,300,500,900 and 999,1887 — no bleed across")
    else:
        failed += 1
        print("  ❌ cumulative sum wrong:", running.get(1), running.get(4))

    # ── a rolling frame clamps to the partition start ────────────────────────
    # 2 preceding = a 3-row trailing window. Region 1's first row averages 1 value, its
    # second 2, and only from the third does the window fill.
    var rolling = framed_aggregate(sales, parts, 2, AGG_AVG, 2)
    if (
        rolling.get(0) == 100.0                      # just itself
        and rolling.get(2) == 150.0                  # (100+200)/2
        and rolling.get(3) > 166.6 and rolling.get(3) < 166.7  # (100+200+200)/3
        and rolling.get(5) > 266.6 and rolling.get(5) < 266.7  # (200+200+400)/3
    ):
        passed += 1
        print("  ✅ a 3-row rolling mean clamps at the partition start, never borrows")
    else:
        failed += 1
        print("  ❌ rolling frame wrong:", rolling.get(0), rolling.get(2))

    # ── the rolling frame does not reach into the previous partition ─────────
    # Region 2's first row must average 999 alone. Borrowing rows 0 and 2 would give
    # (100+200+999)/3 = 433, a number that looks like data.
    if rolling.get(1) == 999.0:
        passed += 1
        print("  ✅ region 2's first rolling mean is 999, not a blend with region 1")
    else:
        failed += 1
        print("  ❌ rolling frame crossed a boundary:", rolling.get(1))

    # ── framed count and min/max ─────────────────────────────────────────────
    var frame_count = framed_aggregate(sales, parts, 2, AGG_COUNT, 2)
    var frame_min = framed_aggregate(sales, parts, 2, AGG_MIN, FRAME_UNBOUNDED)
    var frame_max = framed_aggregate(sales, parts, 2, AGG_MAX, FRAME_UNBOUNDED)
    if (
        frame_count.get(0) == 1.0
        and frame_count.get(3) == 3.0
        and frame_min.get(5) == 100.0
        and frame_max.get(5) == 400.0
        and frame_max.get(0) == 100.0
    ):
        passed += 1
        print("  ✅ framed count/min/max follow the same frame as the mean")
    else:
        failed += 1
        print("  ❌ framed count/min/max wrong")

    # ── partition_total broadcasts the group's answer to every row ───────────
    var total = partition_total(sales, parts, 2, AGG_SUM)
    if (
        total.get(0) == 900.0
        and total.get(2) == 900.0
        and total.get(3) == 900.0
        and total.get(5) == 900.0
        and total.get(1) == 1887.0
        and total.get(4) == 1887.0
    ):
        passed += 1
        print("  ✅ partition_total puts 900 on every region-1 row and 1887 on region 2")
    else:
        failed += 1
        print("  ❌ partition_total wrong:", total.get(0), total.get(1))

    # ── partition_total differs from cumulative — they are not the same thing ─
    if total.get(0) != running.get(0) and total.get(5) == running.get(5):
        passed += 1
        print("  ✅ partition_total is flat while cumulative grows; they agree at the end")
    else:
        failed += 1
        print("  ❌ partition_total and cumulative are not distinguished")

    # ── nulls in the value column are skipped, not zeroed ────────────────────
    # A partition of [null, 10, null, 20]: sum 30, count 2, mean 15. Treating nulls as
    # 0 would give the same sum but a mean of 7.5 — the classic silent divergence.
    var nv = List[Float64]()
    nv.append(0.0)
    nv.append(10.0)
    nv.append(0.0)
    nv.append(20.0)
    var nmask = List[Bool]()
    nmask.append(False)
    nmask.append(True)
    nmask.append(False)
    nmask.append(True)
    var nmonth = List[Float64]()
    for i in range(4):
        nmonth.append(Float64(i))
    var nnames = List[String]()
    nnames.append("month")
    nnames.append("v")
    var ncols = List[Float64Array]()
    ncols.append(float64_from_list(nmonth^))
    ncols.append(float64_with_nulls(nv^, nmask))
    var nbatch = _batch(nnames^, ncols^, 4)

    var no_partition = List[Int]()
    var norder = List[Int]()
    norder.append(0)
    var ndesc = List[Bool]()
    ndesc.append(False)
    var nparts = partition_rows(nbatch, no_partition, norder, ndesc, True)

    if nparts.count() == 1 and nparts.lengths[0] == 4:
        passed += 1
        print("  ✅ no PARTITION BY is one partition over everything")
    else:
        failed += 1
        print("  ❌ empty partition list wrong:", nparts.count())

    var nsum = cumulative(nbatch, nparts, 1, AGG_SUM)
    var nmean = cumulative(nbatch, nparts, 1, AGG_AVG)
    var ncount = cumulative(nbatch, nparts, 1, AGG_COUNT)
    if (
        nsum.get(3) == 30.0
        and ncount.get(3) == 2.0
        and nmean.get(3) == 15.0
    ):
        passed += 1
        print("  ✅ nulls are skipped: sum 30, count 2, mean 15 — not a mean of 7.5")
    else:
        failed += 1
        print("  ❌ null handling wrong:", nsum.get(3), ncount.get(3), nmean.get(3))

    # ── an all-null frame: count 0 and sum 0 are answers, the mean is not ────
    # Follows numeric.contract rather than SQL, which returns NULL for SUM() OVER.
    if (
        ncount.get(0) == 0.0
        and ncount.is_valid_at(0)
        and nsum.get(0) == 0.0
        and nsum.is_valid_at(0)
        and not nmean.is_valid_at(0)
    ):
        passed += 1
        print("  ✅ an all-null frame: count 0 and sum 0 present, mean absent")
    else:
        failed += 1
        print("  ❌ empty-frame policy wrong")

    # ── lineage description ──────────────────────────────────────────────────
    if describe_partitions(parts).find("2 partitions, largest 4 rows") >= 0:
        passed += 1
        print("  ✅ describe_partitions reports 2 partitions, largest 4 rows")
    else:
        failed += 1
        print("  ❌ describe_partitions wrong:", describe_partitions(parts))

    print("  [query.window] Passed:", passed, "Failed:", failed)
