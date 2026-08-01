"""
data_quality.duplicates — grouping on a STATED key with a STATED equality. Zero Python.

The two things a duplicate check must declare
--------------------------------------------
1. THE KEY. Nothing is a duplicate of anything in the abstract. `key_cols` names the
   columns that constitute identity, and two rows are duplicates exactly when their
   projections onto those columns are equal. Every count in `DuplicateReport` is relative
   to that key and means nothing without it, which is why `n_key_cols` travels in the
   report.

2. THE EQUALITY. It is the frozen `columnar.hash_index` normalized IEEE-754 bit pattern:
   `-0.0` collapses to `+0.0`, and every NaN collapses to one quiet NaN. Two consequences
   are inherited rather than invented — `-0.0` and `+0.0` are the same key, and all NaN
   keys land in ONE group instead of one group per row.

   It is NOT `abs(a - b) < tol`. That relation is not transitive (0 ~ tol/2 ~ tol, but
   0 !~ tol), so it is not an equivalence relation, it cannot key a hash table, and the
   groups it produces depend on the order the rows arrived in. A caller who needs measured
   floats compared at a tolerance states a DECIMAL GRID instead — `decimals >= 0` rounds
   every key value to that many places through `contract.dq_quantize` first, which IS an
   equivalence relation because the grid is fixed independently of the data.

   `decimals = -1` means exact bit-pattern equality and no rounding.

A null key is not a duplicate of another null key
-------------------------------------------------
A row with a null in any key column is EXCLUDED from grouping and counted in
`n_null_key_rows`. Null means unknown, so two unknown keys are not known to be equal —
the same reading a SQL `UNIQUE` constraint takes. Excluding them silently would be the
failure this package is about, so the count is a field, and `group_of_row` holds -1 for
those rows rather than a group number they do not belong to.

Frozen kernels called
---------------------
EXISTING-FROZEN: `columnar.hash_index.CompositeKeyIndex` is the index. It hashes N columns
per row without concatenating strings, keeps the full key tuple for the equality check (so
a hash collision splits into two groups rather than silently merging two different keys),
and grows by rehashing at 0.7 load. `contract.dq_quantize` / `dq_quantize_exact` are the
grid. `sparse_numerics.csr.dims_fit`, through `contract.dq_table_defect`, is the shape
check.

MISSING-DRIVER, which is this file: `query.aggregate` groups WITH the index to compute
aggregates. Nothing reported duplicate ROWS, group sizes, the first row of each group, or
which rows were excluded and why.

Refused, not partial
--------------------
A request over `contract.DQ_MAX_WORK` is REFUSED rather than scanned over a prefix. Unlike
an expectation — where a checked prefix is a real partial answer about the rows it checked
— a duplicate count over a prefix is a different statistic wearing the same name: a row's
duplicate may be the row after the cut, so "0 duplicates in the first N rows" says nothing
about the table and reads exactly like "no duplicates".

Status codes: duplicates owns 440-449 of the package's 400-449.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64, bool
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_data_quality_duplicates.mojo
benchmark: benchmarks/mojo_benchmarks/bench_data_quality.mojo
docs: gitbook/engine/data-quality.md
version_introduced: 0.1.0
deprecation_state: active
@endcapability
"""
from columnar.hash_index import CompositeKeyIndex

from data_quality.contract import (
    DQ_ERR_COLUMN_INDEX,
    DQ_ERR_DECIMALS,
    DQ_ERR_NOT_QUANTIZABLE,
    DQ_ERR_WORK_BUDGET,
    DQ_MAX_DECIMALS,
    DQ_MAX_KEY_COLS,
    DQ_MAX_REPORTS,
    DQ_OK,
    dq_is_finite,
    dq_mask_defect,
    dq_quantize,
    dq_quantize_exact,
    dq_status_name,
    dq_table_defect,
    dq_work_fits,
)

# ── status codes: duplicates owns 440-449 ─────────────────────────────────────
comptime DQ_DUP_ERR_NO_KEY_COLS: Int = 440
comptime DQ_DUP_ERR_TOO_MANY_KEY_COLS: Int = 441
comptime DQ_DUP_ERR_REPEATED_KEY_COL: Int = 442

# `decimals = -1` is the sentinel for "no grid, compare the exact bit pattern". It is an
# out-of-band value rather than a separate Bool because a Bool plus an Int lets a caller
# state two things that contradict each other.
comptime DQ_DUP_EXACT_BITS: Int = -1


struct DuplicateReport(Copyable, Movable):
    """Grouping of a table's rows under a stated key.

    Invariants the suite asserts, because a report whose parts do not add up lets a caller
    trust neither half:

        n_rows              == n_comparable_rows + n_null_key_rows
        n_comparable_rows   == n_groups + n_duplicate_rows
        n_duplicated_groups <= n_groups

    `n_duplicate_rows` is the number of rows that could be removed to leave one per group
    — the actionable number — not the number of rows involved in a duplication.
    """

    var status: Int
    var n_rows: Int
    var n_key_cols: Int
    var decimals: Int
    var n_comparable_rows: Int
    var n_null_key_rows: Int
    var n_non_finite_key_rows: Int
    var n_groups: Int
    var n_duplicate_rows: Int
    var n_duplicated_groups: Int
    var largest_group_size: Int
    var first_duplicate_row: Int
    var group_of_row: List[Int]
    var n_reported: Int
    var reports_truncated: Bool
    var duplicate_group_first_rows: List[Int]
    var duplicate_group_sizes: List[Int]

    fn __init__(out self, status: Int, n_rows: Int, n_key_cols: Int, decimals: Int):
        self.status = status
        self.n_rows = n_rows
        self.n_key_cols = n_key_cols
        self.decimals = decimals
        self.n_comparable_rows = 0
        self.n_null_key_rows = 0
        self.n_non_finite_key_rows = 0
        self.n_groups = 0
        self.n_duplicate_rows = 0
        self.n_duplicated_groups = 0
        self.largest_group_size = 0
        self.first_duplicate_row = -1
        self.group_of_row = List[Int]()
        self.n_reported = 0
        self.reports_truncated = False
        self.duplicate_group_first_rows = List[Int]()
        self.duplicate_group_sizes = List[Int]()


fn duplicate_status_name(code: Int) -> String:
    """Name for a status this module can return. One vocabulary, in `contract`.

    @capability duplicate_status_name
    complexity: O(1)
    counts: none
    @endcapability
    """
    return dq_status_name(code)


fn duplicate_key_defect(key_cols: List[Int], n_cols: Int) -> Int:
    """`DQ_OK` when `key_cols` is a usable key for a table of `n_cols` columns.

    Refused: an empty key (there is no such thing as a duplicate with no key), more than
    `DQ_MAX_KEY_COLS` columns, an index outside `[0, n_cols)` in EITHER direction, and a
    column listed twice.

    The repeat is refused rather than deduplicated because `(a, a)` induces exactly the
    same partition as `(a)` while costing twice the hashing — so silently accepting it
    would report a key the caller did not ask for at a price they did not expect. A caller
    who meant `(a)` should say `(a)`.

    Public so a caller can validate a key before sending a whole table.

    @capability duplicate_key_defect
    complexity: O(len(key_cols)^2)
    counts:
    - dim n_cols [kernel_validated]
    @endcapability
    """
    var k = len(key_cols)
    if k == 0:
        return DQ_DUP_ERR_NO_KEY_COLS
    if k > DQ_MAX_KEY_COLS:
        return DQ_DUP_ERR_TOO_MANY_KEY_COLS
    for i in range(k):
        if key_cols[i] < 0 or key_cols[i] >= n_cols:
            return DQ_ERR_COLUMN_INDEX
        for j in range(i + 1, k):
            if key_cols[i] == key_cols[j]:
                return DQ_DUP_ERR_REPEATED_KEY_COL
    return DQ_OK


fn duplicate_scan_flat(
    table: List[Float64], n_rows: Int, n_cols: Int, null_mask: List[Bool],
    key_cols: List[Int], decimals: Int, max_reports: Int,
) -> DuplicateReport:
    """Group the rows of a row-major table under the key `key_cols`.

    One pass, O(n_rows * n_key_cols) expected, through the frozen `CompositeKeyIndex`.
    An O(n^2) pairwise comparison is not an option at any useful table size and would
    additionally have to invent an equality; the index already states one.

    `decimals` is either `DQ_DUP_EXACT_BITS` (-1, compare exact bit patterns) or a grid in
    [0, DQ_MAX_DECIMALS]. On a grid, EVERY comparable key value must be placeable on it:
    if one is not (a magnitude so large that `value * 10^decimals` leaves the range where
    Float64 represents every integer), the whole scan is refused with
    `DQ_ERR_NOT_QUANTIZABLE` rather than grouping some rows on rounded values and others
    on raw ones.

    The key is read through the table's own bounds-checked accessor and `key_cols` is
    validated first, so no index derived from caller input reaches a subscript.

    `decimals` is VALIDATED (a status, `DQ_ERR_DECIMALS`) because it changes the answer.
    `max_reports` is CLAMPED into [0, DQ_MAX_REPORTS] because it changes only how much of
    the answer is listed, and `reports_truncated` already says the list was cut. The two
    relations below are tagged accordingly; `max_reports` said `[kernel_validated]`, which
    claims a typed status this function never returns for it.

    @capability duplicate_scan_flat
    complexity: O(n_rows * len(key_cols))
    counts:
    - n_rows * n_cols == len(table, null_mask) [kernel_validated]
    - dim decimals [kernel_validated]
    - dim max_reports [clamped]
    @endcapability
    """
    var k = len(key_cols)
    var defect = dq_table_defect(table, n_rows, n_cols)
    if defect != DQ_OK:
        return DuplicateReport(defect, 0, k, decimals)
    if len(null_mask) != len(table):
        return DuplicateReport(dq_mask_defect(null_mask, len(table)), 0, k, decimals)
    var key_defect = duplicate_key_defect(key_cols, n_cols)
    if key_defect != DQ_OK:
        return DuplicateReport(key_defect, n_rows, k, decimals)
    if decimals != DQ_DUP_EXACT_BITS and (decimals < 0 or decimals > DQ_MAX_DECIMALS):
        return DuplicateReport(DQ_ERR_DECIMALS, n_rows, k, decimals)
    # The key store is `n_key_cols` Float64 per GROUP, and the worst case is one group per
    # row, so this product is the real allocation and it is charged, not assumed.
    if not dq_work_fits(n_rows, k):
        return DuplicateReport(DQ_ERR_WORK_BUDGET, n_rows, k, decimals)

    var cap = max_reports
    if cap < 0:
        cap = 0
    if cap > DQ_MAX_REPORTS:
        cap = DQ_MAX_REPORTS

    var out = DuplicateReport(DQ_OK, n_rows, k, decimals)
    var index = CompositeKeyIndex(k)
    var group_first_row = List[Int]()
    var group_size = List[Int]()

    for r in range(n_rows):
        var base = r * n_cols
        var comparable = True
        var non_finite = False
        var key = List[Float64]()
        for j in range(k):
            var cell = base + key_cols[j]
            if not null_mask[cell]:
                comparable = False
                break
            var value = table[cell]
            if not dq_is_finite(value):
                non_finite = True
            if decimals == DQ_DUP_EXACT_BITS:
                key.append(value)
            else:
                if not dq_quantize_exact(value, decimals):
                    # Non-finite values are never placeable on a grid; that is a property
                    # of the value, not a caller error, so they keep the frozen index's
                    # own normalization and are counted rather than refused.
                    if dq_is_finite(value):
                        return DuplicateReport(
                            DQ_ERR_NOT_QUANTIZABLE, n_rows, k, decimals
                        )
                    key.append(value)
                else:
                    key.append(dq_quantize(value, decimals))
        if not comparable:
            out.n_null_key_rows += 1
            out.group_of_row.append(-1)
            continue
        if non_finite:
            out.n_non_finite_key_rows += 1
        out.n_comparable_rows += 1
        var slot = index.get_or_assign(key, out.n_groups)
        if slot == out.n_groups:
            out.n_groups += 1
            group_first_row.append(r)
            group_size.append(1)
        else:
            group_size[slot] = group_size[slot] + 1
            out.n_duplicate_rows += 1
            if out.first_duplicate_row < 0:
                out.first_duplicate_row = r
        out.group_of_row.append(slot)

    for g in range(out.n_groups):
        if group_size[g] > out.largest_group_size:
            out.largest_group_size = group_size[g]
        if group_size[g] < 2:
            continue
        out.n_duplicated_groups += 1
        if len(out.duplicate_group_first_rows) >= cap:
            out.reports_truncated = True
            continue
        out.duplicate_group_first_rows.append(group_first_row[g])
        out.duplicate_group_sizes.append(group_size[g])
    out.n_reported = len(out.duplicate_group_first_rows)
    return out^


fn duplicate_rows_of_group(group_of_row: List[Int], group: Int, max_rows: Int) -> List[Int]:
    """Every row assigned to `group`, in ascending order, capped at `max_rows`.

    The companion to `DuplicateReport.group_of_row`: the report says which group each row
    landed in, and this turns one group number back into the row addresses a reader has to
    look at. Kept as a separate function so the report does not have to carry a
    group-to-rows structure whose size is the table's.

    An out-of-range or negative `group` yields an empty list — `group` is compared, never
    used as a subscript, so no bound on it is required for safety; `-1` is the report's own
    marker for a row excluded by a null key and returning those rows under it would present
    "not comparable" as a group.

    `max_rows` is CLAMPED into [0, DQ_MAX_REPORTS], not validated: this function returns a
    `List[Int]` and has no channel to return a status on, so a refusal would be an empty
    list — indistinguishable from "the group has no rows". It was tagged
    `[kernel_validated]`, which promises a typed status that cannot exist here.

    @capability duplicate_rows_of_group
    complexity: O(len(group_of_row))
    counts:
    - dim max_rows [clamped]
    @endcapability
    """
    var out = List[Int]()
    if group < 0:
        return out^
    var cap = max_rows
    if cap < 0:
        cap = 0
    if cap > DQ_MAX_REPORTS:
        cap = DQ_MAX_REPORTS
    for r in range(len(group_of_row)):
        if len(out) >= cap:
            break
        if group_of_row[r] == group:
            out.append(r)
    return out^
