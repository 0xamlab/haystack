"""
query.executor — physical operators over a RecordBatch. Zero Python.

Every operator is `RecordBatch -> RecordBatch` (or `-> List[Int]` for the ones that
only select rows), so they compose without an intermediate format. Row selection is
always expressed as indices and applied through `columnar.batch.take`, which means a
filter, a sort and a top-k cannot disagree about null handling or bounds — there is
one gather.

Decisions that are easy to get wrong silently, so they are stated and tested
-----------------------------------------------------------------------------
**Sort is stable, ties broken by ascending row ordinal.** Not because stability is
nicer, but because an unstable sort makes the *output* of a plan depend on the input
order in a way the plan hash cannot see: two runs over the same rows in a different
storage order give different top-10 lists with no way to tell which is right.

**Null ordering is declared, not inherited.** `nulls_last` is an explicit argument.
SQL dialects disagree (Postgres puts nulls last ascending, others first), so
defaulting silently would mean a query moved between engines changes its answer. The
default here is nulls last for both directions, which keeps "the first row" meaning
"the smallest known value" whichever way you sort.

**DISTINCT treats nulls as equal to each other.** `null = null` is unknown, but
`DISTINCT` asks "are these the same row", and two rows that are both missing the same
field are the same row for that purpose. This is SQL's rule and it is deliberately
different from the comparison operators in `query.eval`.

**top-k does not sort.** It keeps a bounded k-element ordered insert, so cost is
O(n·k) comparisons and O(k) memory rather than O(n log n) and O(n). For the k≈10 that
a report actually asks for, that is the difference between touching 10 slots per row
and sorting a million.

**Projection pushdown is exact, not heuristic.** `required_columns` unions
`query.ir.referenced_columns` over every expression in the plan, so a scan fetches the
two columns a plan reads instead of all forty. If an expression list is empty the
answer is empty, and the caller must treat that as "no columns needed" rather than
"all columns".
"""
from columnar.array import Float64Array, float64_with_nulls
from columnar.batch import RecordBatch, indices_where, schema_of, take
from columnar.hash_index import CompositeKeyIndex
from query.eval import evaluate, evaluate_predicate
from query.ir import first_unsupported_op, referenced_columns, validation_error
from types import ExprNode

# A sentinel row index meaning "no row" — used by outer joins and by top-k before it
# has seen k rows. -1 is what `take_column` already turns into a null, so an
# unfilled slot becomes an absence rather than row 0.
comptime NO_ROW: Int = -1


# ── selection ─────────────────────────────────────────────────────────────────


def filter_indices(
    batch: RecordBatch,
    nodes: List[ExprNode],
    root: Int,
    strict: Bool,
) raises -> List[Int]:
    """Row indices where the predicate is present AND true.

    Indices rather than a batch so a caller can filter, then sort, then take once
    instead of materializing twice.
    """
    return indices_where(evaluate_predicate(nodes, root, batch, strict))


def filter_rows(
    batch: RecordBatch,
    nodes: List[ExprNode],
    root: Int,
    strict: Bool,
) raises -> RecordBatch:
    return take(batch, filter_indices(batch, nodes, root, strict))


# ── projection ────────────────────────────────────────────────────────────────


def project(
    batch: RecordBatch,
    expressions: List[ExprNode],
    roots: List[Int],
    names: List[String],
    strict: Bool,
) raises -> RecordBatch:
    """Evaluate one expression per output column.

    All expressions share the one `expressions` node array with their own root, which
    is what lets two output columns reuse a common subexpression: the evaluator fills
    each node's scratch column once per call, and a shared child is one node.

    An output name shorter than the root list is filled with `col_<i>`, so a plan that
    forgot a name still produces addressable output instead of failing at the end of a
    scan.
    """
    var out_columns = List[Float64Array]()
    var out_names = List[String]()
    for i in range(len(roots)):
        out_columns.append(evaluate(expressions, roots[i], batch, strict))
        if i < len(names):
            out_names.append(names[i])
        else:
            out_names.append("col_" + String(i))
    var n_rows = batch.n_rows
    return RecordBatch(schema_of(out_names^), out_columns^, n_rows)


def select_columns(batch: RecordBatch, columns: List[Int]) -> RecordBatch:
    """Keep the named columns, in the given order. The cheap form of projection.

    No expression evaluation and no row copy: the columns are the same buffers. An
    out-of-range index yields an all-null column named `missing_<i>` rather than
    raising, so a plan that references a dropped column produces a visibly empty
    column instead of aborting a scan halfway.
    """
    var out_columns = List[Float64Array]()
    var out_names = List[String]()
    for i in range(len(columns)):
        var index = columns[i]
        if index < 0 or index >= batch.width():
            var empty_values = List[Float64]()
            var empty_mask = List[Bool]()
            for _ in range(batch.n_rows):
                empty_values.append(0.0)
                empty_mask.append(False)
            out_columns.append(float64_with_nulls(empty_values^, empty_mask))
            out_names.append("missing_" + String(index))
        else:
            out_columns.append(batch.column(index))
            out_names.append(batch.schema.name_at(index))
    var n_rows = batch.n_rows
    return RecordBatch(schema_of(out_names^), out_columns^, n_rows)


def required_columns(nodes: List[ExprNode]) -> List[Int]:
    """Columns a plan actually reads — the pushdown set. Sorted, deduplicated."""
    return referenced_columns(nodes)


# ── ordering ──────────────────────────────────────────────────────────────────


def _key_precedes(
    left_value: Float64,
    left_present: Bool,
    right_value: Float64,
    right_present: Bool,
    descending: Bool,
    nulls_last: Bool,
) -> Bool:
    """True when `left`'s key STRICTLY precedes `right`'s. Equal keys give False.

    Strict on purpose. Every sort here is an insertion sort that shifts only on a
    strict comparison, so returning False for a tie is what makes the sort stable —
    stability is a property of this function, not an extra tie-break argument threaded
    through the callers. Callers that need a deterministic tie order get it by
    starting from row order 0..n-1 and never shifting on equality.

    Absent values are ordered by `nulls_last` in BOTH directions. A null is not a large
    number, so reversing the sort must not reverse where the unknowns go: `ORDER BY x
    DESC` should still leave the rows that have no `x` at the end. Two absent values
    tie, so their relative order is whatever the caller already had.
    """
    if not left_present or not right_present:
        if not left_present and not right_present:
            return False
        if not left_present:
            return not nulls_last
        return nulls_last

    if left_value == right_value:
        return False
    if descending:
        return left_value > right_value
    return left_value < right_value


def _sort_pass(
    mut order: List[Int],
    key: Float64Array,
    descending: Bool,
    nulls_last: Bool,
):
    """One stable insertion pass over `order` in place.

    Shifts only while the placed element strictly FOLLOWS the incoming one, so equal
    keys never move — which is exactly the definition of a stable sort, and the
    property `sort_indices_multi` composes.
    """
    for i in range(1, len(order)):
        var row = order[i]
        var row_value = key.get(row)
        var row_present = key.is_valid_at(row)
        var j = i - 1
        while j >= 0:
            var other = order[j]
            # other strictly after row  <=>  row strictly precedes other
            if _key_precedes(
                row_value,
                row_present,
                key.get(other),
                key.is_valid_at(other),
                descending,
                nulls_last,
            ):
                order[j + 1] = other
                j -= 1
            else:
                break
        order[j + 1] = row


def sort_indices(
    batch: RecordBatch,
    key_column: Int,
    descending: Bool,
    nulls_last: Bool,
) -> List[Int]:
    """Row indices in sorted order. Stable, so ties keep ascending row order.

    Insertion sort rather than quicksort: it is stable without extra bookkeeping, and
    the batches an operator chain passes around are chunk-sized rather than whole
    tables. `columnar` gains a merge sort when a chunk stops fitting.
    """
    var order = List[Int]()
    for r in range(batch.n_rows):
        order.append(r)
    _sort_pass(order, batch.column(key_column), descending, nulls_last)
    return order^


def sort_rows(
    batch: RecordBatch,
    key_column: Int,
    descending: Bool,
    nulls_last: Bool,
) -> RecordBatch:
    return take(batch, sort_indices(batch, key_column, descending, nulls_last))


def sort_indices_multi(
    batch: RecordBatch,
    key_columns: List[Int],
    descending: List[Bool],
    nulls_last: Bool,
) -> List[Int]:
    """Sort by several keys, first key most significant.

    Successive stable passes from the LAST key to the first — the radix-style
    composition, which is correct only because each pass is stable. That is the
    concrete reason stability above is a requirement rather than a preference: with an
    unstable pass, the second key's ordering would destroy the third key's.

    A `descending` list shorter than `key_columns` treats the remaining keys as
    ascending.
    """
    var order = List[Int]()
    for r in range(batch.n_rows):
        order.append(r)
    for pass_index in range(len(key_columns) - 1, -1, -1):
        var desc = descending[pass_index] if pass_index < len(descending) else False
        _sort_pass(order, batch.column(key_columns[pass_index]), desc, nulls_last)
    return order^


def sort_rows_multi(
    batch: RecordBatch,
    key_columns: List[Int],
    descending: List[Bool],
    nulls_last: Bool,
) -> RecordBatch:
    return take(batch, sort_indices_multi(batch, key_columns, descending, nulls_last))


# ── top-k ─────────────────────────────────────────────────────────────────────


def top_k_indices(
    batch: RecordBatch,
    key_column: Int,
    k: Int,
    descending: Bool,
    nulls_last: Bool,
) -> List[Int]:
    """The k best rows by `key_column`, in order, without sorting the batch.

    O(n·k) comparisons and O(k) memory. `k <= 0` is an empty result and `k` past the
    row count is the whole batch sorted — both because a report asking for the top 10
    of 3 rows wants 3 rows, not an error.

    Ties resolve toward the earlier row, the same as `sort_rows`, so `top_k(n)` and
    `sort` agree on the full ordering rather than merely on the set. That falls out of
    the strict comparison: rows arrive in ascending order and a tie does not displace
    what is already there.
    """
    var out = List[Int]()
    if k <= 0 or batch.n_rows == 0:
        return out^
    var key = batch.column(key_column)

    for r in range(batch.n_rows):
        var value = key.get(r)
        var present = key.is_valid_at(r)

        # Where does this row belong among the kept ones?
        var insert_at = len(out)
        for i in range(len(out)):
            var other = out[i]
            if _key_precedes(
                value,
                present,
                key.get(other),
                key.is_valid_at(other),
                descending,
                nulls_last,
            ):
                insert_at = i
                break
        if insert_at >= k:
            continue

        out.append(r)
        var j = len(out) - 1
        while j > insert_at:
            var swap = out[j]
            out[j] = out[j - 1]
            out[j - 1] = swap
            j -= 1
        if len(out) > k:
            _ = out.pop()
    return out^


def top_k_rows(
    batch: RecordBatch,
    key_column: Int,
    k: Int,
    descending: Bool,
    nulls_last: Bool,
) -> RecordBatch:
    return take(batch, top_k_indices(batch, key_column, k, descending, nulls_last))


# ── distinct ──────────────────────────────────────────────────────────────────


def distinct_indices(batch: RecordBatch, key_columns: List[Int]) -> List[Int]:
    """The first row of each distinct key combination, in first-seen order.

    Two rows that are both null in the same key column are the SAME key here. That is
    SQL's DISTINCT rule and it deliberately differs from `=` in `query.eval`, where
    `null = null` is unknown. DISTINCT asks whether two rows are the same row, and two
    rows missing the same field are.

    Absence is folded into the key by a sentinel bit pattern that no Float64 can
    produce, rather than by substituting a value — substituting 0.0 would merge a real
    zero with a missing one.
    """
    var out = List[Int]()
    var width = len(key_columns)
    if batch.n_rows == 0:
        return out^
    if width == 0:
        # No key columns: every row has the same (empty) key, so one row survives.
        out.append(0)
        return out^

    var key_cols = List[Float64Array]()
    for i in range(width):
        key_cols.append(batch.column(key_columns[i]))

    # One extra slot per key column carries presence, so a null and a zero cannot
    # collide. Doubling the key width is cheaper than a second index.
    var index = CompositeKeyIndex(width * 2, 64)
    for r in range(batch.n_rows):
        var key = List[Float64]()
        for c in range(width):
            var present = key_cols[c].is_valid_at(r)
            key.append(key_cols[c].get(r) if present else 0.0)
            key.append(1.0 if present else 0.0)
        var next_slot = len(out)
        var slot = index.get_or_assign(key, next_slot)
        if slot == next_slot:
            out.append(r)
    return out^


def distinct_rows(batch: RecordBatch, key_columns: List[Int]) -> RecordBatch:
    return take(batch, distinct_indices(batch, key_columns))


# ── limit / offset ────────────────────────────────────────────────────────────


def limit_rows(batch: RecordBatch, offset: Int, count: Int) -> RecordBatch:
    """A row window. Clamps rather than raising; a window past the end is empty.

    Delegates to `RecordBatch.slice`, so the columns are shared buffers — a LIMIT is
    O(1) in rows, not a copy.
    """
    return batch.slice(offset, count)


# ── plan validation ───────────────────────────────────────────────────────────


def plan_problem(
    batch_width: Int,
    nodes: List[ExprNode],
    root: Int,
) -> String:
    """"" when the expression can run against a batch this wide, else why not.

    Checks structure (`query.ir.validation_error`) AND that every opcode is one the
    columnar evaluator implements. The second half matters: a plan using a
    transcendental frozen opcode is structurally valid and would raise partway through
    a scan, after some rows were already produced.
    """
    var structural = validation_error(nodes, root, batch_width)
    if structural.byte_length() > 0:
        return structural
    var unsupported = first_unsupported_op(nodes)
    if unsupported >= 0:
        return (
            "node "
            + String(unsupported)
            + " uses opcode "
            + String(nodes[unsupported].op)
            + ", which the columnar evaluator does not implement"
        )
    return ""


def describe_batch_shape(batch: RecordBatch) -> String:
    """Row and column counts plus per-column null counts, for lineage."""
    var out = String(batch.n_rows) + " rows x " + String(batch.width()) + " cols"
    var total_nulls = 0
    for i in range(batch.width()):
        total_nulls += batch.columns[i].null_count()
    if total_nulls > 0:
        out += " (" + String(total_nulls) + " null cells)"
    return out
