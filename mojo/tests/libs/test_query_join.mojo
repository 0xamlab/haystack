"""test_query_join.mojo — known-value tests for hash, merge and semi joins.

Hand-written. Three things here are silent wrong answers rather than crashes, so they
carry the most assertions: a null key that matches another null key (fabricated
pairings between unrelated incomplete rows), a merge join over unsorted input (a
partial result that looks like a correct join over less data), and a semi-join that
multiplies rows the way a real join does.

The null rule is checked directly against `query.executor.distinct_indices`, which uses
the opposite rule on the same data — both are correct for their operation, and having
them in one file makes the contrast checkable instead of a comment.

A fourth class is worse than a wrong answer: a NaN key once made `merge_join_indices`
advance neither cursor and spin forever, which presents to a client as a timeout and
takes the whole worker — every resident dataset with it — down. The NaN block below
asserts the chosen semantics (a NaN key is a missing key) on BOTH algorithms, because a
merge and a hash join that disagree about what matches is the same silent wrong answer as
matching nulls.
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
    is_matchable_key,
    is_sorted_ascending,
    join_output_rows,
    materialize,
    merge_join,
    merge_join_indices,
    semi_join_indices,
)


def _batch(
    var names: List[String], var cols: List[Float64Array], n: Int
) -> RecordBatch:
    return RecordBatch(schema_of(names^), cols^, n)


def _orders() -> RecordBatch:
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


def _customers() -> RecordBatch:
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


def _nan_from_finite() -> Float64:
    """A NaN produced the way one actually arrives: `inf - inf` over finite input.

    Written out rather than parsed from a literal because that is the point — the
    reproduction that hung the worker came from `(1e300*1e300) - (1e300*1e300)` in a
    `project` expression over the row `[1.0]`. Rejecting NaN literals at ingest would not
    have closed it, so the join is where it has to be handled.
    """
    var huge = 1.0e300
    var infinite = huge * huge
    return infinite - infinite


def _keys(var values: List[Float64]) -> RecordBatch:
    """A one-column all-present batch named `k`."""
    var n = len(values)
    var names = List[String]()
    names.append("k")
    var cols = List[Float64Array]()
    cols.append(float64_from_list(values^))
    return _batch(names^, cols^, n)


def main() raises:
    var passed = 0
    var failed = 0
    var orders = _orders()
    var customers = _customers()
    var nan = _nan_from_finite()

    # ── the NaN under test is a real NaN, from finite arithmetic ──────────────
    if nan != nan and not (nan == nan) and not (nan < 1.0) and not (nan > 1.0):
        passed += 1
        print("  ✅ inf - inf is a NaN that answers False to <, > and == alike")
    else:
        failed += 1
        print("  ❌ the NaN fixture is not a NaN:", nan)

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

    # ── an INNER join COUNTS the rows it drops ────────────────────────────────
    # 4 orders in, 3 rows out, and the arithmetic only closes because the two dropped
    # rows are reported: customer 3 (no partner) and the null key. `left_unmatched` used
    # to be incremented only under JOIN_LEFT, so an inner join reported 0 dropped rows
    # and `describe()` omitted the count — the one join that discards rows saying nothing
    # about it.
    var inner_matched_left = 0
    for i in range(inner.n_rows()):
        if inner.right_rows[i] != NO_ROW:
            inner_matched_left += 1
    if (
        inner.left_unmatched == 2
        and inner_matched_left == 3
        and inner.describe().find("2 left rows unmatched") >= 0
        and inner.describe().find("(dropped)") >= 0
    ):
        passed += 1
        print("  ✅ inner join reports 2 dropped left rows and says they were dropped")
    else:
        failed += 1
        print("  ❌ inner unmatched count wrong:", inner.left_unmatched, inner.describe())

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

    # ── the two counters OVERLAP, and the totals only close if you know that ──
    # Under `how = left` the null-key row (order index 3) is counted in BOTH
    # `left_unmatched` and `null_key_rows`. Checked against n_rows both ways so the
    # overlap is asserted rather than assumed: matched + unmatched IS n_rows, while
    # matched + unmatched + null_key_rows OVERSHOOTS it by exactly the shared row.
    var left_matched = 0
    var left_null_marked = 0
    for i in range(left.n_rows()):
        if left.right_rows[i] != NO_ROW:
            left_matched += 1
        elif left.left_rows[i] == 3:
            left_null_marked += 1
    # n_rows() is 5 here (customer 2 fans out to two rows), so the closure is stated in
    # the form that is actually invariant: every output row is either a match or one of
    # the unmatched rows, and nothing is counted twice.
    if (
        left_matched == 3
        and left.left_unmatched == 2
        and left.null_key_rows == 1
        and left_null_marked == 1
        and left_matched + left.left_unmatched == left.n_rows()
        and left.null_key_rows <= left.left_unmatched
        and left_matched + left.left_unmatched + left.null_key_rows > left.n_rows()
        and left.describe().find("already inside the unmatched count") >= 0
    ):
        passed += 1
        print(
            "  ✅ matched + unmatched = n_rows, null_key_rows is a SUBSET, and describe"
            " says so"
        )
    else:
        failed += 1
        print(
            "  ❌ counters do not close:",
            left_matched,
            left.left_unmatched,
            left.null_key_rows,
            left.n_rows(),
            left.describe(),
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

    # ══ a NaN key is a MISSING key, on both algorithms ════════════════════════
    # Chosen semantics: NaN never compares equal to anything, including itself, so it
    # cannot satisfy a join's equality test and is routed through the existing null path
    # — counted in null_key_rows, dropped by INNER, emitted once with NO_ROW by LEFT, in
    # neither half of semi/anti. The alternative (a typed rejection) would refuse a query
    # whose answer is well defined.

    # ── the predicate itself: NaN is not matchable, a valid 0.0 is ────────────
    var nan_only_keys = List[Float64]()
    nan_only_keys.append(nan)
    var nan_only = _keys(nan_only_keys^)
    var zero_keys = List[Float64]()
    zero_keys.append(0.0)
    var zero_only = _keys(zero_keys^)
    if (
        not is_matchable_key(nan_only.column(0), 0)
        and is_matchable_key(zero_only.column(0), 0)
        and not is_matchable_key(orders.column(0), 3)  # the genuine null
        and not is_matchable_key(zero_only.column(0), 7)  # out of range, no crash
    ):
        passed += 1
        print("  ✅ is_matchable_key rejects NaN and null, keeps a real 0.0, bounds-checks")
    else:
        failed += 1
        print("  ❌ is_matchable_key wrong")

    # ── THE hang: one NaN left key against one finite right key, merge method ─
    # Reproduction from the SDK: project k = (1e300*1e300) - (1e300*1e300) over the row
    # [1.0], then merge-join it to a table holding id = 1.0. Every cursor update in the
    # old loop was derived from a `< > ==` ladder, which a NaN answers False to three
    # times, so neither cursor moved and the request never returned. Reaching the next
    # line at all is the assertion.
    var one_finite_keys = List[Float64]()
    one_finite_keys.append(1.0)
    var one_finite = _keys(one_finite_keys^)
    var nan_left_keys = List[Float64]()
    nan_left_keys.append(nan)
    var nan_left = _keys(nan_left_keys^)

    var nan_merge_inner = merge_join_indices(nan_left, 0, one_finite, 0, JOIN_INNER)
    var nan_merge_left = merge_join_indices(nan_left, 0, one_finite, 0, JOIN_LEFT)
    if (
        nan_merge_inner.n_rows() == 0
        and nan_merge_inner.null_key_rows == 1
        and nan_merge_inner.left_unmatched == 1
        and nan_merge_left.n_rows() == 1
        and nan_merge_left.right_rows[0] == NO_ROW
        and nan_merge_left.null_key_rows == 1
        and nan_merge_left.left_unmatched == 1
    ):
        passed += 1
        print("  ✅ merge join TERMINATES on a NaN key: 0 rows inner, 1 null row left")
    else:
        failed += 1
        print("  ❌ NaN merge join wrong:", nan_merge_inner.n_rows(), nan_merge_left.n_rows())

    # ── and the hash method agrees exactly, key for key ──────────────────────
    # It could easily not: columnar.hash_index.normalize_bits collapses every NaN to ONE
    # canonical bit pattern (correct for group-by), so a NaN left key probing a table that
    # held a NaN right key would find it and report a match IEEE-754 denies. Both sides
    # carry a NaN here so that pairing is available to be wrongly made.
    var nan_both_left_keys = List[Float64]()
    nan_both_left_keys.append(1.0)
    nan_both_left_keys.append(nan)
    var nan_both_left = _keys(nan_both_left_keys^)
    var nan_both_right_keys = List[Float64]()
    nan_both_right_keys.append(1.0)
    nan_both_right_keys.append(nan)
    var nan_both_right = _keys(nan_both_right_keys^)

    var nan_hash = hash_join_indices(nan_both_left, 0, nan_both_right, 0, JOIN_INNER)
    var nan_merge = merge_join_indices(nan_both_left, 0, nan_both_right, 0, JOIN_INNER)
    var nan_agree = nan_hash.n_rows() == nan_merge.n_rows()
    if nan_agree:
        for i in range(nan_hash.n_rows()):
            if nan_hash.left_rows[i] != nan_merge.left_rows[i]:
                nan_agree = False
            if nan_hash.right_rows[i] != nan_merge.right_rows[i]:
                nan_agree = False
    if (
        nan_agree
        and nan_hash.n_rows() == 1
        and nan_hash.left_rows[0] == 0
        and nan_hash.right_rows[0] == 0
        and nan_hash.null_key_rows == 1
        and nan_hash.left_unmatched == 1
        and nan_merge.null_key_rows == 1
        and nan_merge.left_unmatched == 1
    ):
        passed += 1
        print("  ✅ NaN does not pair with NaN, and hash and merge agree row for row")
    else:
        failed += 1
        print(
            "  ❌ NaN pairing/agreement wrong:",
            nan_hash.n_rows(),
            nan_merge.n_rows(),
            nan_hash.null_key_rows,
        )

    # ── the LEFT variant keeps the NaN row exactly once, with NO_ROW ─────────
    var nan_hash_left = hash_join_indices(nan_both_left, 0, nan_both_right, 0, JOIN_LEFT)
    var nan_merge_left2 = merge_join_indices(
        nan_both_left, 0, nan_both_right, 0, JOIN_LEFT
    )
    if (
        nan_hash_left.n_rows() == 2
        and nan_hash_left.right_rows[1] == NO_ROW
        and nan_merge_left2.n_rows() == 2
        and nan_merge_left2.right_rows[1] == NO_ROW
    ):
        passed += 1
        print("  ✅ under LEFT the NaN row survives once with nulls, on both methods")
    else:
        failed += 1
        print(
            "  ❌ NaN left join wrong:",
            nan_hash_left.n_rows(),
            nan_merge_left2.n_rows(),
        )

    # ── the pre-flight size count uses the same rule as the join ─────────────
    # A count looser than the join under-counts, and the cap it enforces is the only
    # thing standing between a 1 MB request and a multi-gigabyte allocation.
    if (
        join_output_rows(nan_both_left, 0, nan_both_right, 0, JOIN_INNER)
        == nan_hash.n_rows()
        and join_output_rows(nan_both_left, 0, nan_both_right, 0, JOIN_LEFT)
        == nan_hash_left.n_rows()
    ):
        passed += 1
        print("  ✅ join_output_rows counts a NaN key exactly as the join treats it")
    else:
        failed += 1
        print("  ❌ output-row pre-flight disagrees on NaN")

    # ── a NaN on the RIGHT does not swallow later left rows ──────────────────
    # The old "no partner" test was `right > lv`, which a NaN answers False to, so the
    # branch was skipped, an empty right run was emitted and the left row vanished from a
    # LEFT join without being counted anywhere.
    var right_nan_keys = List[Float64]()
    right_nan_keys.append(nan)
    var right_nan = _keys(right_nan_keys^)
    var swallowed = merge_join_indices(one_finite, 0, right_nan, 0, JOIN_LEFT)
    if (
        swallowed.n_rows() == 1
        and swallowed.right_rows[0] == NO_ROW
        and swallowed.left_unmatched == 1
        and swallowed.null_key_rows == 0  # the LEFT key was fine; the right one was not
    ):
        passed += 1
        print("  ✅ a NaN right key makes the left row unmatched, not silently dropped")
    else:
        failed += 1
        print("  ❌ NaN right key wrong:", swallowed.n_rows(), swallowed.left_unmatched)

    # ── a NaN is held to the null POSITION rule: last, or the merge refuses ──
    # NaN < x and x < NaN are both False, so a NaN between two values certifies an
    # ordering that does not exist. Rejected by the same predicate that rejects a
    # mid-column null, and the refusal is a typed error rather than a partial join.
    var mid_nan_keys = List[Float64]()
    mid_nan_keys.append(1.0)
    mid_nan_keys.append(nan)
    mid_nan_keys.append(2.0)
    var mid_nan = _keys(mid_nan_keys^)
    var trailing_nan_keys = List[Float64]()
    trailing_nan_keys.append(1.0)
    trailing_nan_keys.append(2.0)
    trailing_nan_keys.append(nan)
    var trailing_nan = _keys(trailing_nan_keys^)
    var refused_nan = False
    try:
        var _bad_nan = merge_join_indices(mid_nan, 0, one_finite, 0, JOIN_INNER)
    except:
        refused_nan = True
    if (
        not is_sorted_ascending(mid_nan, 0)
        and is_sorted_ascending(trailing_nan, 0)
        and refused_nan
    ):
        passed += 1
        print("  ✅ a mid-column NaN is not 'sorted'; the merge refuses instead of spinning")
    else:
        failed += 1
        print("  ❌ NaN sortedness rule wrong")

    # ── semi and anti both exclude a NaN key, like a null ────────────────────
    var nan_exists = semi_join_indices(nan_both_left, 0, nan_both_right, 0, True)
    var nan_not_exists = semi_join_indices(nan_both_left, 0, nan_both_right, 0, False)
    if (
        len(nan_exists) == 1
        and nan_exists[0] == 0
        and len(nan_not_exists) == 0
        and len(nan_exists) + len(nan_not_exists) == 1  # the NaN row is in neither
    ):
        passed += 1
        print("  ✅ a NaN key satisfies neither EXISTS nor NOT EXISTS")
    else:
        failed += 1
        print("  ❌ NaN semi/anti wrong:", len(nan_exists), len(nan_not_exists))

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
