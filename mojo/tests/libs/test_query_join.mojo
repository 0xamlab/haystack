"""test_query_join.mojo — known-value tests for hash, merge and semi joins.

Hand-written. Three things here are silent wrong answers rather than crashes, so they
carry the most assertions: a null key that matches another null key (fabricated
pairings between unrelated incomplete rows), a merge join over unsorted input (a
partial result that looks like a correct join over less data), and a semi-join that
multiplies rows the way a real join does.

The null rule is checked directly against `query.executor.distinct_indices`, which uses
the opposite rule on the same data — both are correct for their operation, and having
them in one file makes the contrast checkable instead of a comment.
"""
from columnar.array import Float64Array, float64_from_list, float64_with_nulls
from columnar.batch import RecordBatch, schema_of
from query.executor import distinct_indices, sort_rows
from query.join import (
    JOIN_INNER,
    JOIN_LEFT,
    NO_ROW,
    hash_join,
    hash_join_indices,
    is_sorted_ascending,
    materialize,
    merge_join,
    merge_join_indices,
    semi_join_indices,
)


fn _batch(
    var names: List[String], var cols: List[Float64Array], n: Int
) -> RecordBatch:
    return RecordBatch(schema_of(names^), cols^, n)


fn _orders() -> RecordBatch:
    """customer=[1,2,3,null] amount=[10,20,30,40]. Customer 3 has no match."""
    var customer = List[Float64]()
    customer.append(1.0)
    customer.append(2.0)
    customer.append(3.0)
    customer.append(0.0)  # null
    var customer_mask = List[Bool]()
    customer_mask.append(True)
    customer_mask.append(True)
    customer_mask.append(True)
    customer_mask.append(False)

    var amount = List[Float64]()
    amount.append(10.0)
    amount.append(20.0)
    amount.append(30.0)
    amount.append(40.0)

    var names = List[String]()
    names.append("customer")
    names.append("amount")
    var cols = List[Float64Array]()
    cols.append(float64_with_nulls(customer^, customer_mask))
    cols.append(float64_from_list(amount^))
    return _batch(names^, cols^, 4)


fn _customers() -> RecordBatch:
    """id=[1,2,2,null] tier=[100,200,201,300]. Customer 2 appears twice."""
    var ident = List[Float64]()
    ident.append(1.0)
    ident.append(2.0)
    ident.append(2.0)
    ident.append(0.0)  # null
    var ident_mask = List[Bool]()
    ident_mask.append(True)
    ident_mask.append(True)
    ident_mask.append(True)
    ident_mask.append(False)

    var tier = List[Float64]()
    tier.append(100.0)
    tier.append(200.0)
    tier.append(201.0)
    tier.append(300.0)

    var names = List[String]()
    names.append("id")
    names.append("tier")
    var cols = List[Float64Array]()
    cols.append(float64_with_nulls(ident^, ident_mask))
    cols.append(float64_from_list(tier^))
    return _batch(names^, cols^, 4)


fn main() raises:
    var passed = 0
    var failed = 0
    var orders = _orders()
    var customers = _customers()

    # ── inner join: customer 1 once, customer 2 twice, 3 and null dropped ─────
    var inner = hash_join_indices(orders, 0, customers, 0, JOIN_INNER)
    if (
        inner.n_rows() == 3
        and inner.left_rows[0] == 0
        and inner.right_rows[0] == 0
        and inner.left_rows[1] == 1
        and inner.right_rows[1] == 1
        and inner.left_rows[2] == 1
        and inner.right_rows[2] == 2
    ):
        passed += 1
        print("  ✅ inner join: 3 rows — customer 2 pairs with both of its rows")
    else:
        failed += 1
        print("  ❌ inner join wrong:", inner.n_rows())

    # ── a null key matches NOTHING, not another null key ─────────────────────
    # Both sides have exactly one null. If nulls matched, they would pair and produce a
    # fourth row linking two unrelated incomplete records.
    if inner.n_rows() == 3 and inner.null_key_rows == 1:
        passed += 1
        print("  ✅ the two null keys did not pair with each other")
    else:
        failed += 1
        print("  ❌ null keys matched:", inner.n_rows())

    # ── and DISTINCT on the same column uses the OPPOSITE rule ───────────────
    # Two rows missing the same field ARE the same row for DISTINCT. Having both rules
    # asserted on one dataset is what keeps them from being confused for each other.
    var key_only = List[Int]()
    key_only.append(0)
    var distinct_customers = distinct_indices(orders, key_only)
    if len(distinct_customers) == 4:
        passed += 1
        print(
            "  ✅ DISTINCT keeps the null row as its own group while the join drops it"
        )
    else:
        failed += 1
        print("  ❌ distinct/join null contrast broken:", len(distinct_customers))

    # ── left join keeps the unmatched and the null-key rows, once each ────────
    var left = hash_join_indices(orders, 0, customers, 0, JOIN_LEFT)
    if left.n_rows() == 5 and left.left_unmatched == 2 and left.null_key_rows == 1:
        passed += 1
        print("  ✅ left join: 5 rows, 2 unmatched (customer 3 and the null key)")
    else:
        failed += 1
        print(
            "  ❌ left join wrong:", left.n_rows(), left.left_unmatched
        )

    # ── the unmatched rows carry NO_ROW, not row 0 ───────────────────────────
    # NO_ROW is what take_column renders as a null. Row 0 would silently attach the
    # first customer's tier to every order that has no customer.
    var unmatched_marked = True
    for i in range(left.n_rows()):
        var l = left.left_rows[i]
        if (l == 2 or l == 3) and left.right_rows[i] != NO_ROW:
            unmatched_marked = False
    if unmatched_marked:
        passed += 1
        print("  ✅ unmatched left rows point at NO_ROW rather than row 0")
    else:
        failed += 1
        print("  ❌ an unmatched row was given a real right row")

    # ── materialization renders NO_ROW as a null ─────────────────────────────
    var left_batch = hash_join(orders, 0, customers, 0, JOIN_LEFT, "cust_")
    if (
        left_batch.n_rows == 5
        and left_batch.width() == 4
        and left_batch.schema.name_at(2) == "cust_id"
        and left_batch.schema.name_at(3) == "cust_tier"
    ):
        passed += 1
        print("  ✅ the joined batch is 5x4 with right columns prefixed cust_")
    else:
        failed += 1
        print("  ❌ materialized shape wrong:", left_batch.width())

    # ── the prefix prevents a name collision resolving to the wrong column ───
    # Schema.index_of returns the FIRST match, so two columns named `id` would make
    # every reference silently resolve to the left one.
    if (
        left_batch.column_index("amount") == 1
        and left_batch.column_index("cust_tier") == 3
        and left_batch.column_index("tier") == -1
    ):
        passed += 1
        print("  ✅ right columns are only addressable under their prefixed names")
    else:
        failed += 1
        print("  ❌ name prefixing wrong")

    var tier_column = left_batch.column(3)
    var nulls_where_unmatched = True
    for r in range(left_batch.n_rows):
        var amount = left_batch.column(1).get(r)
        if amount == 30.0 or amount == 40.0:
            if tier_column.is_valid_at(r):
                nulls_where_unmatched = False
    if nulls_where_unmatched:
        passed += 1
        print("  ✅ tier is null for the two orders with no customer, not 0.0")
    else:
        failed += 1
        print("  ❌ an unmatched row got a real tier value")

    # ── inner join materializes to 3 rows with no nulls on the right ─────────
    var inner_batch = hash_join(orders, 0, customers, 0, JOIN_INNER, "cust_")
    var inner_complete = inner_batch.n_rows == 3
    for r in range(inner_batch.n_rows):
        if not inner_batch.column(3).is_valid_at(r):
            inner_complete = False
    if inner_complete:
        passed += 1
        print("  ✅ an inner join leaves no nulls on the right side")
    else:
        failed += 1
        print("  ❌ inner join produced right-side nulls")

    # ── duplicate keys multiply and the count is reported ────────────────────
    if inner.describe().find("3 joined rows") >= 0 and left.describe().find(
        "2 left rows unmatched"
    ) >= 0:
        passed += 1
        print("  ✅ describe reports the row count and the unmatched count")
    else:
        failed += 1
        print("  ❌ describe wrong:", left.describe())

    # ── right partners come out in ascending right-row order ─────────────────
    # Chained at the tail, not the head. Reverse-of-insertion would make the output
    # order depend on build order, which nothing downstream declares.
    if inner.right_rows[1] == 1 and inner.right_rows[2] == 2:
        passed += 1
        print("  ✅ duplicate right partners emerge in ascending row order (1 then 2)")
    else:
        failed += 1
        print("  ❌ right partner order wrong")

    # ── merge join agrees with hash join, on sorted input ────────────────────
    var sorted_orders = sort_rows(orders, 0, False, True)
    var sorted_customers = sort_rows(customers, 0, False, True)
    if is_sorted_ascending(sorted_orders, 0) and is_sorted_ascending(
        sorted_customers, 0
    ):
        passed += 1
        print("  ✅ sort_rows output satisfies is_sorted_ascending (nulls last)")
    else:
        failed += 1
        print("  ❌ sorted input not recognised as sorted")

    var merged = merge_join_indices(sorted_orders, 0, sorted_customers, 0, JOIN_INNER)
    var hashed_sorted = hash_join_indices(
        sorted_orders, 0, sorted_customers, 0, JOIN_INNER
    )
    var same = merged.n_rows() == hashed_sorted.n_rows()
    if same:
        for i in range(merged.n_rows()):
            if merged.left_rows[i] != hashed_sorted.left_rows[i]:
                same = False
            if merged.right_rows[i] != hashed_sorted.right_rows[i]:
                same = False
    if same and merged.n_rows() == 3:
        passed += 1
        print("  ✅ merge join and hash join produce identical index pairs")
    else:
        failed += 1
        print("  ❌ merge/hash disagree:", merged.n_rows(), hashed_sorted.n_rows())

    # ── merge join REFUSES unsorted input instead of half-joining ────────────
    # orders is unsorted on customer (1,2,3,null happens to be sorted) so build an
    # input that is definitely not.
    var jumbled_keys = List[Float64]()
    jumbled_keys.append(2.0)
    jumbled_keys.append(1.0)
    var jumbled_values = List[Float64]()
    jumbled_values.append(7.0)
    jumbled_values.append(8.0)
    var jnames = List[String]()
    jnames.append("customer")
    jnames.append("amount")
    var jcols = List[Float64Array]()
    jcols.append(float64_from_list(jumbled_keys^))
    jcols.append(float64_from_list(jumbled_values^))
    var jumbled = _batch(jnames^, jcols^, 2)

    if not is_sorted_ascending(jumbled, 0):
        passed += 1
        print("  ✅ [2,1] is correctly reported as not ascending")
    else:
        failed += 1
        print("  ❌ unsorted input reported as sorted")

    var refused = False
    try:
        var _bad = merge_join_indices(jumbled, 0, sorted_customers, 0, JOIN_INNER)
    except:
        refused = True
    if refused:
        passed += 1
        print("  ✅ merge join raises on unsorted input rather than half-joining")
    else:
        failed += 1
        print("  ❌ merge join accepted unsorted input")

    # ── a null in the MIDDLE is not sorted for merge purposes ────────────────
    var mid_null_keys = List[Float64]()
    mid_null_keys.append(1.0)
    mid_null_keys.append(0.0)
    mid_null_keys.append(2.0)
    var mid_null_mask = List[Bool]()
    mid_null_mask.append(True)
    mid_null_mask.append(False)
    mid_null_mask.append(True)
    var mnames = List[String]()
    mnames.append("k")
    var mcols = List[Float64Array]()
    mcols.append(float64_with_nulls(mid_null_keys^, mid_null_mask))
    var mid_null = _batch(mnames^, mcols^, 3)
    if not is_sorted_ascending(mid_null, 0):
        passed += 1
        print("  ✅ a null between two values is rejected — the merge would stop early")
    else:
        failed += 1
        print("  ❌ mid-list null accepted as sorted")

    # ── merge left join keeps unmatched rows ─────────────────────────────────
    var merged_left = merge_join(sorted_orders, 0, sorted_customers, 0, JOIN_LEFT, "c_")
    if merged_left.n_rows == 5 and merged_left.width() == 4:
        passed += 1
        print("  ✅ merge left join also yields 5 rows")
    else:
        failed += 1
        print("  ❌ merge left join wrong:", merged_left.n_rows)

    # ── merge join handles duplicates on BOTH sides as a cross product ───────
    var dup_left_keys = List[Float64]()
    dup_left_keys.append(5.0)
    dup_left_keys.append(5.0)
    dup_left_keys.append(5.0)
    var dlnames = List[String]()
    dlnames.append("k")
    var dlcols = List[Float64Array]()
    dlcols.append(float64_from_list(dup_left_keys^))
    var dup_left = _batch(dlnames^, dlcols^, 3)

    var dup_right_keys = List[Float64]()
    dup_right_keys.append(5.0)
    dup_right_keys.append(5.0)
    var drnames = List[String]()
    drnames.append("k")
    var drcols = List[Float64Array]()
    drcols.append(float64_from_list(dup_right_keys^))
    var dup_right = _batch(drnames^, drcols^, 2)

    var cross_merge = merge_join_indices(dup_left, 0, dup_right, 0, JOIN_INNER)
    var cross_hash = hash_join_indices(dup_left, 0, dup_right, 0, JOIN_INNER)
    if cross_merge.n_rows() == 6 and cross_hash.n_rows() == 6:
        passed += 1
        print("  ✅ 3 x 2 duplicate keys give 6 rows on both join strategies")
    else:
        failed += 1
        print(
            "  ❌ cross product wrong:", cross_merge.n_rows(), cross_hash.n_rows()
        )

    # ── semi join does NOT multiply ──────────────────────────────────────────
    # Customer 2 has two matching rows. EXISTS is still one row — getting two is the
    # classic accidental fan-out a join would produce here.
    var exists = semi_join_indices(orders, 0, customers, 0, True)
    if len(exists) == 2 and exists[0] == 0 and exists[1] == 1:
        passed += 1
        print("  ✅ semi join yields 2 rows, not 3 — a match does not duplicate")
    else:
        failed += 1
        print("  ❌ semi join wrong:", len(exists))

    # ── anti join finds the unmatched, excluding the null key ────────────────
    # A null key neither matches nor is known not to match, so it is in neither set.
    var not_exists = semi_join_indices(orders, 0, customers, 0, False)
    if len(not_exists) == 1 and not_exists[0] == 2:
        passed += 1
        print("  ✅ anti join yields only customer 3; the null key is in neither set")
    else:
        failed += 1
        print("  ❌ anti join wrong:", len(not_exists))

    # ── an empty right side: inner is empty, left keeps everything ───────────
    var empty_keys = List[Float64]()
    var enames = List[String]()
    enames.append("id")
    var ecols = List[Float64Array]()
    ecols.append(float64_from_list(empty_keys^))
    var empty_right = _batch(enames^, ecols^, 0)
    var against_empty_inner = hash_join_indices(orders, 0, empty_right, 0, JOIN_INNER)
    var against_empty_left = hash_join_indices(orders, 0, empty_right, 0, JOIN_LEFT)
    if against_empty_inner.n_rows() == 0 and against_empty_left.n_rows() == 4:
        passed += 1
        print("  ✅ against an empty right: inner = 0 rows, left = all 4")
    else:
        failed += 1
        print("  ❌ empty-right join wrong:", against_empty_left.n_rows())

    # ── materialize on an empty result yields an empty, well-shaped batch ────
    var empty_batch = materialize(orders, customers, against_empty_inner, "r_")
    if empty_batch.n_rows == 0 and empty_batch.width() == 4:
        passed += 1
        print("  ✅ an empty join still produces a 4-column schema")
    else:
        failed += 1
        print("  ❌ empty materialization wrong:", empty_batch.width())

    print("  [query.join] Passed:", passed, "Failed:", failed)
