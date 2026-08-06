"""test_columnar_batch.mojo — known-value tests for RecordBatch, take and filter.

Hand-written. `take` is the primitive filter and sort share, so its null and bounds
behaviour is pinned here rather than in each caller: an out-of-range index must yield
a null, never a 0.0 that an aggregate would treat as data.
"""
from columnar.array import Float64Array, float64_from_list, float64_with_nulls
from columnar.batch import (
    RecordBatch,
    Schema,
    filter_batch,
    indices_where,
    schema_of,
    take,
    take_column,
    valid_mask,
)
from columnar.dtype import DTYPE_FLOAT64
from numeric.reduce import reduce_mean, reduce_sum


def _batch() -> RecordBatch:
    """Two columns, four rows. `qty` row 2 is null."""
    var amount = List[Float64]()
    amount.append(10.0)
    amount.append(20.0)
    amount.append(30.0)
    amount.append(40.0)

    var qty = List[Float64]()
    qty.append(1.0)
    qty.append(2.0)
    qty.append(0.0)  # stored, but null
    qty.append(4.0)
    var qty_mask = List[Bool]()
    qty_mask.append(True)
    qty_mask.append(True)
    qty_mask.append(False)
    qty_mask.append(True)

    var names = List[String]()
    names.append("amount")
    names.append("qty")

    var cols = List[Float64Array]()
    cols.append(float64_from_list(amount^))
    cols.append(float64_with_nulls(qty^, qty_mask))
    return RecordBatch(schema_of(names^), cols^, 4)


def main() raises:
    var passed = 0
    var failed = 0

    var batch = _batch()

    # ── shape and schema ────────────────────────────────────────────────────
    if (
        batch.n_rows == 4
        and batch.width() == 2
        and batch.is_consistent()
        and batch.column_index("qty") == 1
        and batch.column_index("missing") == -1
    ):
        passed += 1
        print("  ✅ batch reports 4 rows, 2 columns, and resolves names")
    else:
        failed += 1
        print("  ❌ shape/schema wrong:", batch.describe())

    # ── a ragged batch is detected, not silently truncated ──────────────────
    var short = List[Float64]()
    short.append(1.0)
    var ragged_names = List[String]()
    ragged_names.append("a")
    ragged_names.append("b")
    var ragged_cols = List[Float64Array]()
    ragged_cols.append(float64_from_list(short^))
    var one_more = List[Float64]()
    one_more.append(1.0)
    one_more.append(2.0)
    ragged_cols.append(float64_from_list(one_more^))
    var ragged = RecordBatch(schema_of(ragged_names^), ragged_cols^, 2)
    if not ragged.is_consistent():
        passed += 1
        print("  ✅ a ragged batch fails is_consistent instead of truncating")
    else:
        failed += 1
        print("  ❌ ragged batch accepted")

    # ── column access by name and position ──────────────────────────────────
    if (
        batch.column_by_name("amount").get(0) == 10.0
        and batch.column(1).get(1) == 2.0
        and batch.column_by_name("qty").null_count() == 1
    ):
        passed += 1
        print("  ✅ columns resolve by name and position, nulls preserved")
    else:
        failed += 1
        print("  ❌ column access wrong")

    # ── a missing column is empty, so the failure can be reported by name ────
    if batch.column_by_name("nope").length == 0 and batch.column(99).length == 0:
        passed += 1
        print("  ✅ a missing column is empty rather than raising mid-scan")
    else:
        failed += 1
        print("  ❌ missing column wrong")

    # ── row windows apply across every column ───────────────────────────────
    var window = batch.slice(1, 2)
    if (
        window.n_rows == 2
        and window.width() == 2
        and window.column_by_name("amount").get(0) == 20.0
        and window.column_by_name("qty").null_count() == 1  # row 2 was the null
        and window.is_consistent()
    ):
        passed += 1
        print("  ✅ slice(1,2) windows all columns and keeps validity")
    else:
        failed += 1
        print("  ❌ batch slice wrong:", window.describe())

    # ── take reorders and repeats rows ──────────────────────────────────────
    var order = List[Int]()
    order.append(3)
    order.append(0)
    order.append(3)
    var reordered = take(batch, order)
    if (
        reordered.n_rows == 3
        and reordered.column_by_name("amount").get(0) == 40.0
        and reordered.column_by_name("amount").get(1) == 10.0
        and reordered.column_by_name("amount").get(2) == 40.0
    ):
        passed += 1
        print("  ✅ take reorders and can repeat a row")
    else:
        failed += 1
        print("  ❌ take wrong")

    # ── an out-of-range index yields a NULL, not a 0.0 ──────────────────────
    # The load-bearing case: 0.0 would enter an aggregate as real data.
    var bad = List[Int]()
    bad.append(0)
    bad.append(99)
    bad.append(-1)
    var gathered = take_column(batch.column_by_name("amount"), bad)
    if (
        gathered.length == 3
        and gathered.is_valid_at(0)
        and not gathered.is_valid_at(1)
        and not gathered.is_valid_at(2)
        and gathered.null_count() == 2
    ):
        passed += 1
        print("  ✅ an out-of-range take index yields null, not 0.0")
    else:
        failed += 1
        print("  ❌ out-of-range take wrong:", gathered.null_count())

    # ── taking a null row keeps it null ─────────────────────────────────────
    var null_row = List[Int]()
    null_row.append(2)
    var took_null = take_column(batch.column_by_name("qty"), null_row)
    if not took_null.is_valid_at(0):
        passed += 1
        print("  ✅ taking a null row preserves its nullness")
    else:
        failed += 1
        print("  ❌ null row became valid")

    # ── filter keeps the marked rows ────────────────────────────────────────
    var keep = List[Bool]()
    keep.append(False)
    keep.append(True)
    keep.append(False)
    keep.append(True)
    var filtered = filter_batch(batch, keep)
    if (
        filtered.n_rows == 2
        and filtered.column_by_name("amount").get(0) == 20.0
        and filtered.column_by_name("amount").get(1) == 40.0
    ):
        passed += 1
        print("  ✅ filter_batch keeps exactly the marked rows")
    else:
        failed += 1
        print("  ❌ filter wrong:", filtered.n_rows)

    # ── indices_where matches what filter used ──────────────────────────────
    var picked = indices_where(keep)
    if len(picked) == 2 and picked[0] == 1 and picked[1] == 3:
        passed += 1
        print("  ✅ indices_where yields the selection vector")
    else:
        failed += 1
        print("  ❌ indices_where wrong")

    # ── filtering to the valid rows of a nullable column ────────────────────
    var non_null = filter_batch(batch, valid_mask(batch.column_by_name("qty")))
    if non_null.n_rows == 3 and non_null.column_by_name("qty").null_count() == 0:
        passed += 1
        print("  ✅ filtering by valid_mask drops the null row")
    else:
        failed += 1
        print("  ❌ valid_mask filter wrong:", non_null.n_rows)

    # ── an empty filter yields an empty but consistent batch ────────────────
    var none = List[Bool]()
    for _ in range(4):
        none.append(False)
    var empty = filter_batch(batch, none)
    if empty.n_rows == 0 and empty.width() == 2 and empty.is_consistent():
        passed += 1
        print("  ✅ an all-false filter gives an empty, still-consistent batch")
    else:
        failed += 1
        print("  ❌ empty filter wrong")

    # ── end to end: filter then aggregate, agreeing with the numeric contract ─
    var live = filter_batch(batch, valid_mask(batch.column_by_name("qty")))
    var col = live.column_by_name("qty")
    var summed = reduce_sum(col.values_list(), col.mask_list())
    var averaged = reduce_mean(col.values_list(), col.mask_list())
    # Live qty values are 1, 2, 4 -> sum 7, mean 7/3.
    if (
        summed.value == 7.0
        and averaged.present
        and averaged.value > 2.333
        and averaged.value < 2.334
    ):
        passed += 1
        print("  ✅ filter -> aggregate gives sum 7, mean 2.333 over the live rows")
    else:
        failed += 1
        print("  ❌ end-to-end wrong:", summed.value, averaged.value)

    # ── aggregating an empty batch has no mean ──────────────────────────────
    var empty_col = empty.column_by_name("qty")
    if not reduce_mean(empty_col.values_list(), empty_col.mask_list()).present:
        passed += 1
        print("  ✅ an empty batch has no mean, rather than 0.0")
    else:
        failed += 1
        print("  ❌ empty aggregate returned a value")

    # ── schema description is readable ──────────────────────────────────────
    if batch.schema.describe() == "amount:float64, qty:float64" and batch.schema.dtype_at(
        0
    ) == DTYPE_FLOAT64:
        passed += 1
        print("  ✅ schema describes itself readably")
    else:
        failed += 1
        print("  ❌ schema describe wrong:", batch.schema.describe())

    print("  [columnar.batch] Passed:", passed, "Failed:", failed)
