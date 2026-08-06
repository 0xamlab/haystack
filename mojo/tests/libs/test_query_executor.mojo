"""test_query_executor.mojo — known-value tests for the physical operators.

Hand-written. The assertions target the behaviours that are wrong silently rather than
loudly: an unstable sort (right set, unpredictable order), nulls treated as large
numbers, DISTINCT merging a real zero with a missing value, and top-k disagreeing with
a full sort about which row is first.
"""
from columnar.array import Float64Array, float64_from_list, float64_with_nulls
from columnar.batch import RecordBatch, schema_of
from query.executor import (
    describe_batch_shape,
    distinct_indices,
    distinct_rows,
    filter_indices,
    filter_rows,
    limit_rows,
    plan_problem,
    project,
    required_columns,
    select_columns,
    sort_indices,
    sort_indices_multi,
    sort_rows,
    top_k_indices,
    top_k_rows,
)
from query.ir import (
    OP_ADD,
    OP_AND,
    OP_GT,
    OP_LT,
    OP_MUL,
    binary,
    col_ref,
    literal,
    unary,
)
from types import ExprNode

comptime OP_SQRT_FROZEN: Int = 12  # a frozen transcendental the evaluator omits


def _named(var names: List[String], var cols: List[Float64Array], n: Int) -> RecordBatch:
    return RecordBatch(schema_of(names^), cols^, n)


def _sales() -> RecordBatch:
    """region=[1,2,1,3,2] amount=[10,50,30,null,50] units=[1,2,3,4,5]."""
    var region = List[Float64]()
    region.append(1.0)
    region.append(2.0)
    region.append(1.0)
    region.append(3.0)
    region.append(2.0)

    var amount = List[Float64]()
    amount.append(10.0)
    amount.append(50.0)
    amount.append(30.0)
    amount.append(0.0)  # null
    amount.append(50.0)
    var amount_mask = List[Bool]()
    amount_mask.append(True)
    amount_mask.append(True)
    amount_mask.append(True)
    amount_mask.append(False)
    amount_mask.append(True)

    var units = List[Float64]()
    for i in range(5):
        units.append(Float64(i + 1))

    var names = List[String]()
    names.append("region")
    names.append("amount")
    names.append("units")
    var cols = List[Float64Array]()
    cols.append(float64_from_list(region^))
    cols.append(float64_with_nulls(amount^, amount_mask))
    cols.append(float64_from_list(units^))
    return _named(names^, cols^, 5)


def main() raises:
    var passed = 0
    var failed = 0
    var sales = _sales()

    # ── filter: an unknown predicate does not pass ────────────────────────────
    # Row 3's amount is null, so `amount > 20` is unknown there. It must not survive:
    # an unknown is not a true.
    var gt20 = List[ExprNode]()
    gt20.append(col_ref(1))
    gt20.append(literal(20.0))
    gt20.append(binary(OP_GT, 0, 1))
    var kept = filter_indices(sales, gt20, 2, False)
    if len(kept) == 3 and kept[0] == 1 and kept[1] == 2 and kept[2] == 4:
        passed += 1
        print("  ✅ filter keeps rows 1,2,4; the null-amount row is not true")
    else:
        failed += 1
        print("  ❌ filter wrong:", len(kept))

    var filtered = filter_rows(sales, gt20, 2, False)
    if filtered.n_rows == 3 and filtered.width() == 3 and filtered.is_consistent():
        passed += 1
        print("  ✅ filter_rows yields a consistent 3-row batch across all columns")
    else:
        failed += 1
        print("  ❌ filter_rows shape wrong:", filtered.n_rows)

    # ── projection evaluates expressions per output column ───────────────────
    # amount + units, and units * 2, sharing one node array.
    var proj = List[ExprNode]()
    proj.append(col_ref(1))              # 0 amount
    proj.append(col_ref(2))              # 1 units
    proj.append(binary(OP_ADD, 0, 1))    # 2 amount + units
    proj.append(literal(2.0))            # 3
    proj.append(binary(OP_MUL, 1, 3))    # 4 units * 2
    var roots = List[Int]()
    roots.append(2)
    roots.append(4)
    var pnames = List[String]()
    pnames.append("total")
    pnames.append("double_units")
    var projected = project(sales, proj, roots, pnames, False)
    if (
        projected.width() == 2
        and projected.n_rows == 5
        and projected.schema.name_at(0) == "total"
        and projected.column(0).get(0) == 11.0    # 10 + 1
        and projected.column(1).get(4) == 10.0    # 5 * 2
    ):
        passed += 1
        print("  ✅ projection computes amount+units and units*2 into named columns")
    else:
        failed += 1
        print("  ❌ projection wrong:", projected.width())

    # ── a null propagates through the projected expression ───────────────────
    if not projected.column(0).is_valid_at(3) and projected.column(1).is_valid_at(3):
        passed += 1
        print("  ✅ null amount makes total null, while double_units stays known")
    else:
        failed += 1
        print("  ❌ null propagation through projection wrong")

    # ── a missing output name gets a positional one, not a failure ────────────
    var no_names = List[String]()
    var unnamed = project(sales, proj, roots, no_names, False)
    if unnamed.schema.name_at(0) == "col_0" and unnamed.schema.name_at(1) == "col_1":
        passed += 1
        print("  ✅ unnamed projections become col_0 / col_1 rather than failing")
    else:
        failed += 1
        print("  ❌ unnamed projection wrong")

    # ── select_columns reorders without evaluating ────────────────────────────
    var pick = List[Int]()
    pick.append(2)
    pick.append(0)
    var picked = select_columns(sales, pick)
    if (
        picked.width() == 2
        and picked.schema.name_at(0) == "units"
        and picked.schema.name_at(1) == "region"
        and picked.column(0).get(0) == 1.0
    ):
        passed += 1
        print("  ✅ select_columns reorders to (units, region) with no evaluation")
    else:
        failed += 1
        print("  ❌ select_columns wrong")

    # ── an out-of-range column is an all-null column, not an abort ────────────
    var bad_pick = List[Int]()
    bad_pick.append(0)
    bad_pick.append(99)
    var bad_picked = select_columns(sales, bad_pick)
    if (
        bad_picked.width() == 2
        and bad_picked.schema.name_at(1) == "missing_99"
        and not bad_picked.column(1).is_valid_at(0)
        and bad_picked.column(1).length == 5
    ):
        passed += 1
        print("  ✅ a dropped column becomes a visibly null column named missing_99")
    else:
        failed += 1
        print("  ❌ out-of-range column handling wrong")

    # ── pushdown reports exactly the columns read ────────────────────────────
    var needed = required_columns(proj)
    if len(needed) == 2 and needed[0] == 1 and needed[1] == 2:
        passed += 1
        print("  ✅ pushdown reports columns 1 and 2 — the two the plan reads")
    else:
        failed += 1
        print("  ❌ pushdown set wrong:", len(needed))

    # ── sort is stable: equal keys keep ascending row order ───────────────────
    # amount 50 appears at rows 1 and 4. Descending, row 1 must come before row 4.
    # An unstable sort gets the same SET with an unpredictable order, so the top-1 of
    # this data would differ run to run with nothing to indicate it.
    var desc = sort_indices(sales, 1, True, True)
    if desc[0] == 1 and desc[1] == 4 and desc[2] == 2 and desc[3] == 0:
        passed += 1
        print("  ✅ descending sort is stable: tied 50s stay in row order 1 then 4")
    else:
        failed += 1
        print("  ❌ sort not stable:", desc[0], desc[1], desc[2], desc[3])

    # ── nulls go last in BOTH directions when nulls_last ─────────────────────
    # A null is not a large number. Reversing the sort must not move the unknowns to
    # the front, or `ORDER BY amount DESC` silently answers with rows that have no
    # amount at all.
    var asc = sort_indices(sales, 1, False, True)
    if desc[4] == 3 and asc[4] == 3:
        passed += 1
        print("  ✅ the null-amount row is last ascending AND descending")
    else:
        failed += 1
        print("  ❌ null ordering flipped with direction:", asc[4], desc[4])

    # ── nulls_last=False puts them first, in both directions ─────────────────
    var nulls_first = sort_indices(sales, 1, False, False)
    if nulls_first[0] == 3:
        passed += 1
        print("  ✅ nulls_last=False puts the unknown row first — declared, not guessed")
    else:
        failed += 1
        print("  ❌ nulls_first wrong:", nulls_first[0])

    # ── ascending order is actually ascending ────────────────────────────────
    if asc[0] == 0 and asc[1] == 2 and asc[2] == 1 and asc[3] == 4:
        passed += 1
        print("  ✅ ascending gives 10, 30, 50, 50 with the tie in row order")
    else:
        failed += 1
        print("  ❌ ascending order wrong:", asc[0], asc[1], asc[2], asc[3])

    var sorted_batch = sort_rows(sales, 1, False, True)
    if (
        sorted_batch.n_rows == 5
        and sorted_batch.column(1).get(0) == 10.0
        and not sorted_batch.column(1).is_valid_at(4)
        and sorted_batch.column(2).get(0) == 1.0  # units travelled with its row
    ):
        passed += 1
        print("  ✅ sort_rows carries every column along with its row")
    else:
        failed += 1
        print("  ❌ sort_rows wrong")

    # ── multi-key sort: region ascending, then amount descending ─────────────
    # Correct only if each pass is stable; an unstable pass would let the amount pass
    # scramble the region grouping.
    var multi_keys = List[Int]()
    multi_keys.append(0)  # region asc
    multi_keys.append(1)  # amount desc
    var multi_desc = List[Bool]()
    multi_desc.append(False)
    multi_desc.append(True)
    var multi = sort_indices_multi(sales, multi_keys, multi_desc, True)
    # region 1: rows 0(10) and 2(30) -> 2 then 0.  region 2: rows 1(50), 4(50) -> 1,4.
    # region 3: row 3.
    if (
        multi[0] == 2
        and multi[1] == 0
        and multi[2] == 1
        and multi[3] == 4
        and multi[4] == 3
    ):
        passed += 1
        print("  ✅ (region asc, amount desc) = rows 2,0,1,4,3 — passes composed")
    else:
        failed += 1
        print(
            "  ❌ multi-key sort wrong:",
            multi[0],
            multi[1],
            multi[2],
            multi[3],
            multi[4],
        )

    # ── top-k agrees with a full sort, without sorting ───────────────────────
    var top2 = top_k_indices(sales, 1, 2, True, True)
    if len(top2) == 2 and top2[0] == desc[0] and top2[1] == desc[1]:
        passed += 1
        print("  ✅ top-2 matches the first two of the full descending sort")
    else:
        failed += 1
        print("  ❌ top-k disagrees with sort:", len(top2))

    # ── top-k over the whole batch equals the full sort ──────────────────────
    var top_all = top_k_indices(sales, 1, 99, True, True)
    var agrees = len(top_all) == 5
    if agrees:
        for i in range(5):
            if top_all[i] != desc[i]:
                agrees = False
    if agrees:
        passed += 1
        print("  ✅ top-k with k past the row count reproduces the full sort exactly")
    else:
        failed += 1
        print("  ❌ top-k(99) != sort:", len(top_all))

    # ── k <= 0 is empty, not an error and not everything ─────────────────────
    if len(top_k_indices(sales, 1, 0, True, True)) == 0 and len(
        top_k_indices(sales, 1, -5, True, True)
    ) == 0:
        passed += 1
        print("  ✅ top-k with k<=0 is empty")
    else:
        failed += 1
        print("  ❌ top-k with k<=0 returned rows")

    var top_batch = top_k_rows(sales, 1, 2, True, True)
    if top_batch.n_rows == 2 and top_batch.column(1).get(0) == 50.0:
        passed += 1
        print("  ✅ top_k_rows returns a 2-row batch of the largest amounts")
    else:
        failed += 1
        print("  ❌ top_k_rows wrong")

    # ── distinct over one column, first-seen order ───────────────────────────
    var region_only = List[Int]()
    region_only.append(0)
    var distinct_regions = distinct_indices(sales, region_only)
    if (
        len(distinct_regions) == 3
        and distinct_regions[0] == 0
        and distinct_regions[1] == 1
        and distinct_regions[2] == 3
    ):
        passed += 1
        print("  ✅ distinct regions = first rows 0,1,3 in first-seen order")
    else:
        failed += 1
        print("  ❌ distinct wrong:", len(distinct_regions))

    # ── DISTINCT treats two nulls as the same row ────────────────────────────
    # Different from `=`, where null = null is unknown. DISTINCT asks whether two rows
    # are the same row, and two rows missing the same field are.
    var dn_values = List[Float64]()
    dn_values.append(0.0)
    dn_values.append(0.0)
    dn_values.append(0.0)
    var dn_mask = List[Bool]()
    dn_mask.append(False)  # null
    dn_mask.append(False)  # null
    dn_mask.append(True)   # a REAL zero
    var dn_names = List[String]()
    dn_names.append("v")
    var dn_cols = List[Float64Array]()
    dn_cols.append(float64_with_nulls(dn_values^, dn_mask))
    var dn = _named(dn_names^, dn_cols^, 3)
    var dn_keys = List[Int]()
    dn_keys.append(0)
    var dn_distinct = distinct_indices(dn, dn_keys)
    if len(dn_distinct) == 2 and dn_distinct[0] == 0 and dn_distinct[1] == 2:
        passed += 1
        print("  ✅ two nulls collapse to one row, and a real 0 stays separate from them")
    else:
        failed += 1
        print("  ❌ distinct null handling wrong:", len(dn_distinct))

    # ── distinct over several columns uses the whole tuple ───────────────────
    # Rows 1 and 4 are both (region=2, amount=50), so 4 rows survive, not 5. Keying on
    # region alone would give 3 and keying on amount alone would give 4 by coincidence,
    # so this also checks the tuple is what is compared.
    var pair_keys = List[Int]()
    pair_keys.append(0)
    pair_keys.append(1)
    var pair_distinct_indices = distinct_indices(sales, pair_keys)
    var pair_distinct = distinct_rows(sales, pair_keys)
    if (
        pair_distinct.n_rows == 4
        and len(pair_distinct_indices) == 4
        and pair_distinct_indices[0] == 0
        and pair_distinct_indices[1] == 1
        and pair_distinct_indices[2] == 2
        and pair_distinct_indices[3] == 3  # row 4 dropped: duplicate of row 1
    ):
        passed += 1
        print("  ✅ (region, amount) keeps 4 rows; row 4 duplicates row 1's (2,50)")
    else:
        failed += 1
        print("  ❌ composite distinct wrong:", pair_distinct.n_rows)

    # ── the same tuple in a different column order is still one key ───────────
    var reversed_keys = List[Int]()
    reversed_keys.append(1)
    reversed_keys.append(0)
    if distinct_rows(sales, reversed_keys).n_rows == 4:
        passed += 1
        print("  ✅ (amount, region) finds the same 4 distinct rows")
    else:
        failed += 1
        print("  ❌ key column order changed the distinct count")

    # ── no key columns collapses to a single row ─────────────────────────────
    var no_key = List[Int]()
    if len(distinct_indices(sales, no_key)) == 1:
        passed += 1
        print("  ✅ DISTINCT with no columns is one row, not zero and not five")
    else:
        failed += 1
        print("  ❌ empty-key distinct wrong")

    # ── limit is a window, and clamps ────────────────────────────────────────
    var window = limit_rows(sales, 1, 2)
    if (
        window.n_rows == 2
        and window.column(0).get(0) == 2.0
        and limit_rows(sales, 4, 100).n_rows == 1
        and limit_rows(sales, 99, 5).n_rows == 0
    ):
        passed += 1
        print("  ✅ limit windows and clamps: (1,2)=2 rows, (4,100)=1, (99,5)=0")
    else:
        failed += 1
        print("  ❌ limit wrong:", window.n_rows)

    # ── plan validation rejects before any row is produced ───────────────────
    # A structurally valid plan using a frozen transcendental opcode would raise
    # partway through a scan, after rows had already been emitted.
    var frozen_plan = List[ExprNode]()
    frozen_plan.append(col_ref(1))
    frozen_plan.append(unary(OP_SQRT_FROZEN, 0))
    var frozen_problem = plan_problem(sales.width(), frozen_plan, 1)
    if len(frozen_problem) > 0 and frozen_problem.find("does not implement") >= 0:
        passed += 1
        print("  ✅ an unimplemented opcode is rejected up front, naming the node")
    else:
        failed += 1
        print("  ❌ unimplemented opcode not rejected:", frozen_problem)

    # ── a plan referencing a column the batch does not have is rejected ──────
    var wide_plan = List[ExprNode]()
    wide_plan.append(col_ref(99))
    if len(plan_problem(sales.width(), wide_plan, 0)) > 0:
        passed += 1
        print("  ✅ a reference to a nonexistent column is rejected")
    else:
        failed += 1
        print("  ❌ out-of-range column reference accepted")

    # ── a good plan reports no problem ───────────────────────────────────────
    if len(plan_problem(sales.width(), gt20, 2)) == 0:
        passed += 1
        print("  ✅ a well-formed predicate reports no problem")
    else:
        failed += 1
        print("  ❌ good plan rejected:", plan_problem(sales.width(), gt20, 2))

    # ── filter then sort then limit compose over one gather each ─────────────
    var compound = limit_rows(sort_rows(filter_rows(sales, gt20, 2, False), 1, True, True), 0, 2)
    if (
        compound.n_rows == 2
        and compound.column(1).get(0) == 50.0
        and compound.column(1).get(1) == 50.0
        and compound.column(2).get(0) == 2.0  # row 1's units
    ):
        passed += 1
        print("  ✅ filter -> sort -> limit composes to the two 50s with units intact")
    else:
        failed += 1
        print("  ❌ operator composition wrong:", compound.n_rows)

    # ── lineage description reports shape and nulls ──────────────────────────
    var shape = describe_batch_shape(sales)
    if shape.find("5 rows x 3 cols") >= 0 and shape.find("1 null cells") >= 0:
        passed += 1
        print("  ✅ describe_batch_shape reports 5x3 and the one null cell")
    else:
        failed += 1
        print("  ❌ describe_batch_shape wrong:", shape)

    # ── an all-true compound predicate keeps everything decidable ────────────
    var wide_and = List[ExprNode]()
    wide_and.append(col_ref(2))            # 0 units
    wide_and.append(literal(0.0))          # 1
    wide_and.append(binary(OP_GT, 0, 1))   # 2 units > 0
    wide_and.append(literal(100.0))        # 3
    wide_and.append(binary(OP_LT, 0, 3))   # 4 units < 100
    wide_and.append(binary(OP_AND, 2, 4))  # 5
    if len(filter_indices(sales, wide_and, 5, False)) == 5:
        passed += 1
        print("  ✅ a conjunction over a non-null column keeps all 5 rows")
    else:
        failed += 1
        print("  ❌ conjunction filter wrong")

    print("  [query.executor] Passed:", passed, "Failed:", failed)
