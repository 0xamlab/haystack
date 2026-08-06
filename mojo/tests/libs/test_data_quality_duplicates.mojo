"""test_data_quality_duplicates.mojo — known-value tests for grouping on a stated key.

Hand-written. The worked table is 5 rows x 2 columns (id, amount):

    row 0:  id = 1        amount = 10
    row 1:  id = 2        amount = 20
    row 2:  id = 1        amount = 10      identical to row 0 on (id, amount) AND on (id)
    row 3:  id = 1        amount = 99      identical to row 0 on (id) only
    row 4:  id = ABSENT   amount = 5       a null key: not a duplicate of anything

Under key (id, amount) the partition is {0, 2}, {1}, {3} — three groups, one removable
row, largest group 2. Under key (id) it is {0, 2, 3}, {1} — two groups, two removable rows,
largest group 3. Both are derived above by reading the table, and BOTH are asserted,
because the whole point is that "duplicate" has no meaning without the key.

Equality references
-------------------
`columnar.hash_index.normalize_bits` collapses `-0.0` to `+0.0` and every NaN to one quiet
NaN. So a column holding `-0.0` and `+0.0` is ONE group, and a column of two NaNs is ONE
group rather than two. Those are properties of the frozen kernel, asserted here so a change
to the equality cannot pass unnoticed.

Grid reference: `1.001` and `1.002` are distinct binary64 values and both round to `1.00`
at two decimal places (CPython `math.floor(v*100+0.5)/100` gives 1.0 for each), so an exact
scan sees two groups and a 2-place scan sees one.
"""
from data_quality.contract import (
    DQ_ERR_COLUMN_INDEX,
    DQ_ERR_DECIMALS,
    DQ_ERR_MASK_LENGTH,
    DQ_ERR_NOT_QUANTIZABLE,
    DQ_ERR_TABLE_SHAPE,
    DQ_OK,
    dq_mask_all_valid,
)
from data_quality.duplicates import (
    DQ_DUP_ERR_NO_KEY_COLS,
    DQ_DUP_ERR_REPEATED_KEY_COL,
    DQ_DUP_ERR_TOO_MANY_KEY_COLS,
    DQ_DUP_EXACT_BITS,
    DuplicateReport,
    duplicate_key_defect,
    duplicate_rows_of_group,
    duplicate_scan_flat,
    duplicate_status_name,
)


def _nan() -> Float64:
    var zero: Float64 = 0.0
    return zero / zero


def _demo_table() -> List[Float64]:
    var t = List[Float64]()
    t.append(1.0)
    t.append(10.0)
    t.append(2.0)
    t.append(20.0)
    t.append(1.0)
    t.append(10.0)
    t.append(1.0)
    t.append(99.0)
    t.append(0.0)
    t.append(5.0)
    return t^


def _demo_mask() -> List[Bool]:
    """Row 4's id (cell 8) is absent."""
    var m = dq_mask_all_valid(10)
    m[8] = False
    return m^


def _ints(a: Int) -> List[Int]:
    var o = List[Int]()
    o.append(a)
    return o^


def _ints2(a: Int, b: Int) -> List[Int]:
    var o = List[Int]()
    o.append(a)
    o.append(b)
    return o^


def _invariants(r: DuplicateReport) -> Bool:
    if r.n_rows != r.n_comparable_rows + r.n_null_key_rows:
        return False
    if r.n_comparable_rows != r.n_groups + r.n_duplicate_rows:
        return False
    if r.n_duplicated_groups > r.n_groups:
        return False
    return len(r.group_of_row) == r.n_rows


def check():
    var passed = 0
    var failed = 0
    var t = _demo_table()
    var m = _demo_mask()

    # ── key (id, amount) ──────────────────────────────────────────────────────
    var full = duplicate_scan_flat(t, 5, 2, m, _ints2(0, 1), DQ_DUP_EXACT_BITS, 32)
    if full.status == DQ_OK and full.n_key_cols == 2 and full.decimals == DQ_DUP_EXACT_BITS:
        passed += 1
        print("  ✅ the report carries the key width and the equality it used")
    else:
        failed += 1
        print("  ❌ report metadata wrong:", duplicate_status_name(full.status))

    if full.n_comparable_rows == 4 and full.n_null_key_rows == 1:
        passed += 1
        print("  ✅ 4 comparable rows, 1 excluded for a null key — and the count is reported")
    else:
        failed += 1
        print("  ❌ comparability census wrong:", full.n_comparable_rows, full.n_null_key_rows)

    if full.n_groups == 3 and full.n_duplicate_rows == 1 and full.n_duplicated_groups == 1:
        passed += 1
        print("  ✅ key (id, amount): 3 groups, 1 removable row, 1 duplicated group")
    else:
        failed += 1
        print("  ❌ (id, amount) grouping wrong:", full.n_groups, full.n_duplicate_rows)

    if full.largest_group_size == 2 and full.first_duplicate_row == 2:
        passed += 1
        print("  ✅ the largest group has 2 rows and the first repeat is row 2")
    else:
        failed += 1
        print("  ❌ group size / first duplicate wrong:", full.largest_group_size, full.first_duplicate_row)

    if (
        full.group_of_row[0] == 0
        and full.group_of_row[2] == 0
        and full.group_of_row[1] == 1
        and full.group_of_row[3] == 2
        and full.group_of_row[4] == -1
    ):
        passed += 1
        print("  ✅ group_of_row is [0, 1, 0, 2, -1] — the null-key row gets -1, not a group")
    else:
        failed += 1
        print("  ❌ group assignment wrong")

    if full.n_reported == 1 and full.duplicate_group_first_rows[0] == 0 and full.duplicate_group_sizes[0] == 2:
        passed += 1
        print("  ✅ the duplicated group is reported by its first row (0) and size (2)")
    else:
        failed += 1
        print("  ❌ duplicated-group reporting wrong")

    var g0 = duplicate_rows_of_group(full.group_of_row, 0, 16)
    if len(g0) == 2 and g0[0] == 0 and g0[1] == 2:
        passed += 1
        print("  ✅ group 0 resolves back to rows [0, 2]")
    else:
        failed += 1
        print("  ❌ group-to-rows resolution wrong, length", len(g0))

    if len(duplicate_rows_of_group(full.group_of_row, -1, 16)) == 0:
        passed += 1
        print("  ✅ -1 is not a group: the excluded rows are not returned under it")
    else:
        failed += 1
        print("  ❌ the null-key marker was treated as a group")

    if _invariants(full):
        passed += 1
        print("  ✅ rows = comparable + null-key, and comparable = groups + duplicates")
    else:
        failed += 1
        print("  ❌ the duplicate report does not add up")

    # ── the SAME table under key (id) gives a DIFFERENT answer ────────────────
    var by_id = duplicate_scan_flat(t, 5, 2, m, _ints(0), DQ_DUP_EXACT_BITS, 32)
    if by_id.n_groups == 2 and by_id.n_duplicate_rows == 2 and by_id.largest_group_size == 3:
        passed += 1
        print("  ✅ key (id): 2 groups, 2 removable rows, largest group 3 — the key decides")
    else:
        failed += 1
        print("  ❌ (id) grouping wrong:", by_id.n_groups, by_id.n_duplicate_rows)

    if _invariants(by_id) and by_id.n_comparable_rows == 4:
        passed += 1
        print("  ✅ the invariants hold under the second key too")
    else:
        failed += 1
        print("  ❌ invariants broken under key (id)")

    # ── the stated equality, inherited from the frozen index ──────────────────
    var signed = List[Float64]()
    signed.append(-0.0)
    signed.append(0.0)
    var signed_scan = duplicate_scan_flat(signed, 2, 1, dq_mask_all_valid(2), _ints(0), DQ_DUP_EXACT_BITS, 8)
    if signed_scan.n_groups == 1 and signed_scan.n_duplicate_rows == 1:
        passed += 1
        print("  ✅ -0.0 and +0.0 are one key, so they are duplicates")
    else:
        failed += 1
        print("  ❌ -0.0 and +0.0 were split into two groups")

    var nans = List[Float64]()
    nans.append(_nan())
    nans.append(_nan())
    nans.append(_nan())
    var nan_scan = duplicate_scan_flat(nans, 3, 1, dq_mask_all_valid(3), _ints(0), DQ_DUP_EXACT_BITS, 8)
    if nan_scan.n_groups == 1 and nan_scan.n_duplicate_rows == 2 and nan_scan.n_non_finite_key_rows == 3:
        passed += 1
        print("  ✅ three NaN keys are ONE group, not three, and the non-finites are counted")
    else:
        failed += 1
        print("  ❌ NaN keying wrong:", nan_scan.n_groups, nan_scan.n_non_finite_key_rows)

    # A tolerance is not an equivalence relation, so the alternative is a declared grid.
    var near = List[Float64]()
    near.append(1.001)
    near.append(1.002)
    var exact_scan = duplicate_scan_flat(near, 2, 1, dq_mask_all_valid(2), _ints(0), DQ_DUP_EXACT_BITS, 8)
    var grid_scan = duplicate_scan_flat(near, 2, 1, dq_mask_all_valid(2), _ints(0), 2, 8)
    if exact_scan.n_groups == 2 and grid_scan.n_groups == 1 and grid_scan.decimals == 2:
        passed += 1
        print("  ✅ 1.001 and 1.002: two groups exactly, one group on a 2-place grid")
    else:
        failed += 1
        print("  ❌ grid comparison wrong:", exact_scan.n_groups, grid_scan.n_groups)

    var grid3 = duplicate_scan_flat(near, 2, 1, dq_mask_all_valid(2), _ints(0), 3, 8)
    if grid3.n_groups == 2:
        passed += 1
        print("  ✅ a 3-place grid keeps them apart — the grid is the caller's declaration")
    else:
        failed += 1
        print("  ❌ a 3-place grid merged 1.001 and 1.002")

    # ── a value that cannot be placed on the declared grid refuses the scan ────
    var huge = List[Float64]()
    huge.append(1e300)
    huge.append(1.0)
    if duplicate_scan_flat(huge, 2, 1, dq_mask_all_valid(2), _ints(0), 2, 8).status == DQ_ERR_NOT_QUANTIZABLE:
        passed += 1
        print("  ✅ 1e300 cannot sit on a 2-place grid, so the scan refuses rather than mixing")
    else:
        failed += 1
        print("  ❌ an unplaceable value was grouped anyway")

    # A non-finite is not a caller error: it is never placeable on any grid, so it keeps the
    # frozen normalization and is counted instead of refusing the whole scan.
    var mixed = List[Float64]()
    mixed.append(_nan())
    mixed.append(1.0)
    var mixed_scan = duplicate_scan_flat(mixed, 2, 1, dq_mask_all_valid(2), _ints(0), 2, 8)
    if mixed_scan.status == DQ_OK and mixed_scan.n_groups == 2 and mixed_scan.n_non_finite_key_rows == 1:
        passed += 1
        print("  ✅ a NaN key on a grid is counted, not refused, and stays its own group")
    else:
        failed += 1
        print("  ❌ a NaN key on a grid behaved unexpectedly:", duplicate_status_name(mixed_scan.status))

    # ── the report cap keeps the counts ───────────────────────────────────────
    var many = List[Float64]()
    many.append(1.0)
    many.append(1.0)
    many.append(2.0)
    many.append(2.0)
    var capped = duplicate_scan_flat(many, 4, 1, dq_mask_all_valid(4), _ints(0), DQ_DUP_EXACT_BITS, 1)
    if (
        capped.n_duplicated_groups == 2
        and capped.n_reported == 1
        and capped.reports_truncated
        and capped.n_duplicate_rows == 2
    ):
        passed += 1
        print("  ✅ max_reports=1 caps the listed groups at 1 while the counts stay complete")
    else:
        failed += 1
        print("  ❌ the cap dropped a count:", capped.n_duplicated_groups, capped.n_reported)

    # `max_reports` is CLAMPED into [0, DQ_MAX_REPORTS], not validated — the relation now
    # says `[clamped]` rather than `[kernel_validated]`, which claimed a typed status this
    # function never returns for it. Both ends of the clamp keep the request WORKING and
    # keep the counts complete; a refusal would have been the behaviour change.
    var neg_cap = duplicate_scan_flat(
        many, 4, 1, dq_mask_all_valid(4), _ints(0), DQ_DUP_EXACT_BITS, -7
    )
    var huge_cap = duplicate_scan_flat(
        many, 4, 1, dq_mask_all_valid(4), _ints(0), DQ_DUP_EXACT_BITS, 1 << 40
    )
    if (
        neg_cap.status == DQ_OK
        and neg_cap.n_duplicated_groups == 2 and neg_cap.n_reported == 0
        and neg_cap.reports_truncated
        and huge_cap.status == DQ_OK
        and huge_cap.n_duplicated_groups == 2 and huge_cap.n_reported == 2
        and not huge_cap.reports_truncated
    ):
        passed += 1
        print("  ✅ max_reports clamps at both ends and never refuses — 2 groups either way")
    else:
        failed += 1
        print(
            "  ❌ max_reports was validated instead of clamped:",
            neg_cap.status, neg_cap.n_reported, huge_cap.status, huge_cap.n_reported,
        )

    # `duplicate_rows_of_group` clamps `max_rows` for a stronger reason: it returns a
    # `List[Int]` and has no channel for a status, so a refusal would be an empty list —
    # indistinguishable from "this group has no rows". Group 0 of the four rows above holds
    # rows 0 and 1, so a cap of 1 returns [0] and a negative cap returns nothing.
    var g0_all = duplicate_rows_of_group(capped.group_of_row, 0, 16)
    var g0_one = duplicate_rows_of_group(capped.group_of_row, 0, 1)
    var g0_neg = duplicate_rows_of_group(capped.group_of_row, 0, -3)
    var g0_huge = duplicate_rows_of_group(capped.group_of_row, 0, 1 << 40)
    if (
        len(g0_all) == 2 and g0_all[0] == 0 and g0_all[1] == 1
        and len(g0_one) == 1 and g0_one[0] == 0
        and len(g0_neg) == 0
        and len(g0_huge) == 2
    ):
        passed += 1
        print("  ✅ max_rows clamps to [0, DQ_MAX_REPORTS]: group 0 is rows [0, 1], cap 1 -> [0]")
    else:
        failed += 1
        print(
            "  ❌ max_rows was not clamped:",
            len(g0_all), len(g0_one), len(g0_neg), len(g0_huge),
        )

    # ── key validation ────────────────────────────────────────────────────────
    var empty = List[Int]()
    if duplicate_key_defect(empty, 2) == DQ_DUP_ERR_NO_KEY_COLS:
        passed += 1
        print("  ✅ there is no such thing as a duplicate with no key")
    else:
        failed += 1
        print("  ❌ an empty key was accepted")

    if duplicate_key_defect(_ints2(0, 0), 2) == DQ_DUP_ERR_REPEATED_KEY_COL:
        passed += 1
        print("  ✅ a column listed twice is refused, not silently deduplicated")
    else:
        failed += 1
        print("  ❌ a repeated key column was accepted")

    if duplicate_key_defect(_ints(-1), 2) == DQ_ERR_COLUMN_INDEX and duplicate_key_defect(_ints(2), 2) == DQ_ERR_COLUMN_INDEX:
        passed += 1
        print("  ✅ a key column out of range in either direction is refused")
    else:
        failed += 1
        print("  ❌ an out-of-range key column reached a subscript")

    var wide = List[Int]()
    for i in range(65):
        wide.append(i)
    if duplicate_key_defect(wide, 128) == DQ_DUP_ERR_TOO_MANY_KEY_COLS:
        passed += 1
        print("  ✅ a 65-column key exceeds the ceiling and is refused")
    else:
        failed += 1
        print("  ❌ the key-width ceiling was not enforced")

    if duplicate_key_defect(_ints2(0, 1), 2) == DQ_OK:
        passed += 1
        print("  ✅ a sound key validates before a whole table is sent")
    else:
        failed += 1
        print("  ❌ a sound key was refused")

    # ── shape and grid refusals ───────────────────────────────────────────────
    if duplicate_scan_flat(t, 5, 3, m, _ints(0), DQ_DUP_EXACT_BITS, 8).status == DQ_ERR_TABLE_SHAPE:
        passed += 1
        print("  ✅ a declared shape that does not match the cell count is refused")
    else:
        failed += 1
        print("  ❌ a wrong shape was indexed")

    var short_mask = List[Bool]()
    short_mask.append(True)
    if duplicate_scan_flat(t, 5, 2, short_mask, _ints(0), DQ_DUP_EXACT_BITS, 8).status == DQ_ERR_MASK_LENGTH:
        passed += 1
        print("  ✅ a mask that does not cover the table is refused")
    else:
        failed += 1
        print("  ❌ a short mask was accepted")

    if (
        duplicate_scan_flat(t, 5, 2, m, _ints(0), 99, 8).status == DQ_ERR_DECIMALS
        and duplicate_scan_flat(t, 5, 2, m, _ints(0), -2, 8).status == DQ_ERR_DECIMALS
    ):
        passed += 1
        print("  ✅ a grid outside [0, 15] is refused; only -1 means 'exact bits'")
    else:
        failed += 1
        print("  ❌ an out-of-range grid was accepted")

    # ── an all-null key column: everything excluded, nothing invented ──────────
    var all_absent = List[Bool]()
    all_absent.append(False)
    all_absent.append(False)
    var absent_scan = duplicate_scan_flat(signed, 2, 1, all_absent, _ints(0), DQ_DUP_EXACT_BITS, 8)
    if (
        absent_scan.status == DQ_OK
        and absent_scan.n_null_key_rows == 2
        and absent_scan.n_groups == 0
        and absent_scan.n_duplicate_rows == 0
        and absent_scan.first_duplicate_row == -1
    ):
        passed += 1
        print("  ✅ two null keys are not duplicates of each other — 0 groups, 0 duplicates")
    else:
        failed += 1
        print("  ❌ null keys were grouped together")

    # ── the A-Z argument shape returns statuses, never a crash ────────────────
    var lf5 = List[Float64]()
    var lb5 = List[Bool]()
    var li5 = List[Int]()
    for i in range(5):
        lf5.append(0.5)
        lb5.append(True)
        li5.append(i + 1)
    if (
        duplicate_scan_flat(lf5, 5, 5, lb5, li5, 5, 5).status != DQ_OK
        and duplicate_key_defect(li5, 5) == DQ_ERR_COLUMN_INDEX
        and len(duplicate_rows_of_group(li5, 5, 5)) == 1
    ):
        passed += 1
        print("  ✅ the A-Z shape is refused with a status and nothing aborts")
    else:
        failed += 1
        print("  ❌ the A-Z shape behaved unexpectedly")

    print("  [data_quality.duplicates] Passed:", passed, "Failed:", failed)


def main():
    check()
