"""
query.join — hash and merge joins over RecordBatches. Zero Python.

A join is expressed as two aligned index lists — `left_rows` and `right_rows` — and
only then materialized through `columnar.batch.take_column`. Keeping the row pairing
separate from the gather means an outer join's unmatched side is just `NO_ROW` in the
index list, and `take_column` already turns an out-of-range index into a null. There is
no second code path for "the row that isn't there".

A null key matches nothing. This is the opposite of DISTINCT
-----------------------------------------------------------
`null = null` is unknown, and a join is a sequence of equality tests, so a row whose
key is missing joins to nothing:

  * INNER — the row disappears.
  * LEFT  — the row survives once, with nulls across every right column.

`query.executor.distinct_indices` deliberately does the opposite: there, two rows
missing the same field ARE the same row. Both rules are right for their operation and
using either one for the other is a silent wrong answer — an inner join that matched
nulls would fabricate pairings between unrelated rows that happen to both be
incomplete. Both are tested against each other.

Duplicate keys multiply, they do not collapse
--------------------------------------------
Three left rows and two right rows sharing a key produce six output rows. That is what
a join means and it is the usual source of a surprise row count, so `JoinResult`
carries `left_unmatched` and the output length rather than making a caller infer them.

Hash join vs merge join
-----------------------
`hash_join` builds a table on the right and probes with the left: O(n+m), no ordering
requirement. `merge_join` walks two already-sorted inputs: O(n+m) with no table at all,
which is what makes it the right choice when a previous operator already sorted — the
plan should not pay twice. `merge_join` verifies its inputs are sorted rather than
trusting the claim, because an unsorted input silently produces a partial join, and a
join that quietly drops matches is worse than one that refuses.
"""
from columnar.array import Float64Array
from columnar.batch import RecordBatch, Schema, take_column
from columnar.hash_index import HashIndex

# Matches `query.executor.NO_ROW`. An index of -1 is what `take_column` turns into a
# null, so an unmatched outer row needs no special case anywhere downstream.
comptime NO_ROW: Int = -1

comptime JOIN_INNER: Int = 0
comptime JOIN_LEFT: Int = 1


struct JoinResult(Copyable, Movable):
    """Aligned row indices for the two sides, plus what did not match.

    `right_rows[i] == NO_ROW` marks a left row that found no partner. Counting them
    separately as `left_unmatched` means a caller can report "40 of 500 orders had no
    customer" without rescanning the result.
    """

    var left_rows: List[Int]
    var right_rows: List[Int]
    var left_unmatched: Int
    var null_key_rows: Int

    fn __init__(
        out self,
        var left_rows: List[Int],
        var right_rows: List[Int],
        left_unmatched: Int,
        null_key_rows: Int,
    ):
        self.left_rows = left_rows^
        self.right_rows = right_rows^
        self.left_unmatched = left_unmatched
        self.null_key_rows = null_key_rows

    fn n_rows(self) -> Int:
        return len(self.left_rows)

    fn describe(self) -> String:
        var out = String(len(self.left_rows)) + " joined rows"
        if self.left_unmatched > 0:
            out += ", " + String(self.left_unmatched) + " left rows unmatched"
        if self.null_key_rows > 0:
            out += ", " + String(self.null_key_rows) + " left rows had a null key"
        return out


fn _build_right_index(
    right_key: Float64Array,
    n_rows: Int,
    mut slot_of: HashIndex,
    mut first_row: List[Int],
    mut next_row: List[Int],
) -> Int:
    """A key -> chain-of-rows table over the right side. Returns the null-key count.

    One slot per distinct key holding the head of a linked list through `next_row`,
    which is how duplicate right keys are represented without a list-of-lists: row
    chaining costs one Int per row and no allocation per key.

    Rows are chained in ASCENDING order (the list is appended to at the tail) so a
    probe emits partners in right-row order, which makes the join output deterministic
    rather than reverse-of-insertion.
    """
    var null_keys = 0
    var last_row = List[Int]()
    for r in range(n_rows):
        next_row.append(NO_ROW)
    for r in range(n_rows):
        if not right_key.is_valid_at(r):
            null_keys += 1
            continue
        var next_slot = len(first_row)
        var slot = slot_of.get_or_assign(right_key.get(r), next_slot)
        if slot == next_slot:
            first_row.append(r)
            last_row.append(r)
        else:
            next_row[last_row[slot]] = r
            last_row[slot] = r
    return null_keys


fn hash_join_indices(
    left: RecordBatch,
    left_key_column: Int,
    right: RecordBatch,
    right_key_column: Int,
    join_type: Int,
) -> JoinResult:
    """Pair left rows with right rows on equal keys. Build on the right, probe left.

    A left row with a null key matches nothing: under INNER it vanishes, under LEFT it
    emits once with NO_ROW opposite it. Right rows with null keys are never matchable
    and so never appear.
    """
    var left_key = left.column(left_key_column)
    var right_key = right.column(right_key_column)

    var slot_of = HashIndex(64)
    var first_row = List[Int]()
    var next_row = List[Int]()
    _ = _build_right_index(right_key, right.n_rows, slot_of, first_row, next_row)

    var out_left = List[Int]()
    var out_right = List[Int]()
    var unmatched = 0
    var null_keys = 0

    for l in range(left.n_rows):
        if not left_key.is_valid_at(l):
            null_keys += 1
            # An unknown key equals nothing, not even another unknown.
            if join_type == JOIN_LEFT:
                out_left.append(l)
                out_right.append(NO_ROW)
                unmatched += 1
            continue

        var slot = slot_of.find(left_key.get(l))
        if slot < 0:
            if join_type == JOIN_LEFT:
                out_left.append(l)
                out_right.append(NO_ROW)
                unmatched += 1
            continue

        var r = first_row[slot]
        while r != NO_ROW:
            out_left.append(l)
            out_right.append(r)
            r = next_row[r]

    return JoinResult(out_left^, out_right^, unmatched, null_keys)


fn is_sorted_ascending(batch: RecordBatch, key_column: Int) -> Bool:
    """True when the key ascends, with every null at the end.

    Nulls at the end because that is `query.executor.sort_indices(..., nulls_last=True)`
    output, which is what a merge join is meant to consume. A null in the middle means
    the input was not produced by that sort and the merge would stop early.
    """
    var key = batch.column(key_column)
    var seen_null = False
    var previous: Float64 = 0.0
    var have_previous = False
    for r in range(batch.n_rows):
        if not key.is_valid_at(r):
            seen_null = True
            continue
        if seen_null:
            return False
        var value = key.get(r)
        if have_previous and value < previous:
            return False
        previous = value
        have_previous = True
    return True


fn merge_join_indices(
    left: RecordBatch,
    left_key_column: Int,
    right: RecordBatch,
    right_key_column: Int,
    join_type: Int,
) raises -> JoinResult:
    """Join two ascending-sorted inputs with no hash table.

    Raises if either side is not sorted. Checked rather than trusted: an unsorted input
    makes the merge terminate early and return a subset of the real matches, which
    looks like a correct join over less data — the failure mode that a "you must sort
    first" comment does not prevent.

    Equal-key runs on both sides produce their full cross product, walked in ascending
    row order on both sides so the output matches `hash_join_indices` exactly.
    """
    if not is_sorted_ascending(left, left_key_column):
        raise Error(
            "query.join: merge_join requires the left input sorted ascending on column "
            + String(left_key_column)
            + " with nulls last"
        )
    if not is_sorted_ascending(right, right_key_column):
        raise Error(
            "query.join: merge_join requires the right input sorted ascending on column "
            + String(right_key_column)
            + " with nulls last"
        )

    var left_key = left.column(left_key_column)
    var right_key = right.column(right_key_column)

    var out_left = List[Int]()
    var out_right = List[Int]()
    var unmatched = 0
    var null_keys = 0

    var l = 0
    var r = 0
    while l < left.n_rows:
        if not left_key.is_valid_at(l):
            # Nulls are last, so everything from here on is a null key.
            null_keys += 1
            if join_type == JOIN_LEFT:
                out_left.append(l)
                out_right.append(NO_ROW)
                unmatched += 1
            l += 1
            continue

        var lv = left_key.get(l)

        # Advance the right cursor to the first row that could match. A right null
        # stops the scan outright rather than being skipped past: nulls are last, so a
        # null here means there is nothing matchable left.
        while r < right.n_rows and right_key.is_valid_at(r) and right_key.get(r) < lv:
            r += 1

        if r >= right.n_rows or not right_key.is_valid_at(r) or right_key.get(r) > lv:
            if join_type == JOIN_LEFT:
                out_left.append(l)
                out_right.append(NO_ROW)
                unmatched += 1
            l += 1
            continue

        # A run of equal keys on the right; emit the cross product with the left run.
        var run_start = r
        var run_end = r
        while run_end < right.n_rows and right_key.is_valid_at(run_end) and right_key.get(
            run_end
        ) == lv:
            run_end += 1

        var left_run_end = l
        while left_run_end < left.n_rows and left_key.is_valid_at(
            left_run_end
        ) and left_key.get(left_run_end) == lv:
            left_run_end += 1

        for li in range(l, left_run_end):
            for ri in range(run_start, run_end):
                out_left.append(li)
                out_right.append(ri)

        l = left_run_end
        # The right cursor stays at run_start: the next left key may equal this one
        # only if the left run ended, which it did, so advancing to run_end is safe.
        r = run_end

    return JoinResult(out_left^, out_right^, unmatched, null_keys)


fn materialize(
    left: RecordBatch,
    right: RecordBatch,
    result: JoinResult,
    right_name_prefix: String,
) -> RecordBatch:
    """Build the joined batch: every left column then every right column.

    Right column names get `right_name_prefix` so a self-join or a shared column name
    does not produce two columns answering to the same name — `Schema.index_of` returns
    the first match, so a collision would silently resolve every reference to the left
    one.

    Unmatched right rows are NO_ROW, which `take_column` renders as a null. That is why
    an outer join needs no separate materialization path.
    """
    var columns = List[Float64Array]()
    var names = List[String]()
    var dtypes = List[Int]()

    for c in range(left.width()):
        columns.append(take_column(left.columns[c], result.left_rows))
        names.append(left.schema.name_at(c))
        dtypes.append(left.schema.dtype_at(c))
    for c in range(right.width()):
        columns.append(take_column(right.columns[c], result.right_rows))
        names.append(right_name_prefix + right.schema.name_at(c))
        dtypes.append(right.schema.dtype_at(c))

    return RecordBatch(Schema(names^, dtypes^), columns^, result.n_rows())


fn hash_join(
    left: RecordBatch,
    left_key_column: Int,
    right: RecordBatch,
    right_key_column: Int,
    join_type: Int,
    right_name_prefix: String,
) -> RecordBatch:
    return materialize(
        left,
        right,
        hash_join_indices(left, left_key_column, right, right_key_column, join_type),
        right_name_prefix,
    )


fn merge_join(
    left: RecordBatch,
    left_key_column: Int,
    right: RecordBatch,
    right_key_column: Int,
    join_type: Int,
    right_name_prefix: String,
) raises -> RecordBatch:
    return materialize(
        left,
        right,
        merge_join_indices(left, left_key_column, right, right_key_column, join_type),
        right_name_prefix,
    )


fn semi_join_indices(
    left: RecordBatch,
    left_key_column: Int,
    right: RecordBatch,
    right_key_column: Int,
    keep_matching: Bool,
) -> List[Int]:
    """Left rows that have (or lack) a partner. One row out per row in, never more.

    `keep_matching=True` is EXISTS, `False` is NOT EXISTS. Distinct from a join because
    it cannot multiply rows: `EXISTS` over three partners is still one row, and getting
    three is the classic accidental fan-out.

    A null left key satisfies neither: it does not match, and it is not *known* not to
    match. It is excluded from both, which is what SQL's `NOT IN` with nulls does and
    the reason that construct surprises people.
    """
    var left_key = left.column(left_key_column)
    var right_key = right.column(right_key_column)

    var slot_of = HashIndex(64)
    var first_row = List[Int]()
    var next_row = List[Int]()
    _ = _build_right_index(right_key, right.n_rows, slot_of, first_row, next_row)

    var out = List[Int]()
    for l in range(left.n_rows):
        if not left_key.is_valid_at(l):
            continue
        var found = slot_of.find(left_key.get(l)) >= 0
        if found == keep_matching:
            out.append(l)
    return out^
