"""
query.window — ranking and framed aggregates within partitions. Zero Python.

A window function differs from a group-by in that it returns one value per ROW rather
than one per group, so every function here produces a column the same length as the
input and aligned to it. That alignment is the whole contract: a window column can be
appended to the batch it was computed from without a join.

Partition boundaries are hard
-----------------------------
`lag`, `lead`, the cumulative aggregates and the rolling frames all stop at the
partition edge. A `lag` that reads the previous partition's last row is the single most
common window bug and it produces a number that looks entirely plausible — last
December's figure attributed to a different region. Here the boundary yields a null,
because "there is no previous row in this partition" is an absence, not a zero.

`rank` gaps, `dense_rank` does not
----------------------------------
Values 10, 20, 20, 30 rank as 1, 2, 2, 4 and dense-rank as 1, 2, 2, 3. Both are
standard, they differ only after a tie, and swapping them is invisible until someone
compares two reports. Both are provided and both are tested on the same tied data.

Ordering and nulls
------------------
Rows are ordered within a partition by `query.executor`'s comparator, so a window's
notion of "previous row" is the same as `ORDER BY`'s — including `nulls_last`, which is
explicit for the same reason it is there: a null is not a large value, so reversing the
order must not move the unknowns to the front.

Empty frames follow numeric.contract, not SQL
---------------------------------------------
A frame containing no live values gives `count` 0 and `sum` 0 — real answers — and no
mean, min or max. SQL returns NULL for `SUM() OVER` on an empty frame; `numeric.contract`
says the sum of nothing is 0 and that contract is what every other new surface here
obeys, so this follows it rather than SQL. Stated because it is a real divergence.

What counts as the SAME key — `columnar.hash_index` is the reference
-------------------------------------------------------------------
`keys_equal_at` below is the one definition of key equality in this file, and it is
`columnar.hash_index.normalize_bits` — the frozen, already-shipped notion that
`query.aggregate`'s `group_by` / `group_by_multi` group by. That index is the tiebreaker
because it shipped first and because a second definition of "the same key" inside one
package is a defect on its own: the same column grouped two ways would give two
different groupings and neither docstring would say so.

Concretely, `normalize_bits` collapses every NaN onto one quiet NaN and `-0.0` onto
`+0.0`, so:

  * **all NaN rows form ONE partition**, not one partition per row. Raw `!=` would cut a
    fresh partition for every NaN row, because NaN != NaN — which also means a `rank` or
    a `partition_total` computed over them would be a per-row self-report dressed up as
    a group answer.
  * `-0.0` and `+0.0` are one partition, which raw `==` already agreed with. Normalizing
    keeps the hash and the comparison from disagreeing.

Because the sort comparator cannot order NaN (nothing precedes a NaN and a NaN precedes
nothing), NaN rows are NOT necessarily adjacent after the sort. So partitioning cannot
be a cut between adjacent rows; it is a hash grouping through the frozen
`CompositeKeyIndex`. See `partition_rows`.

Null keys still diverge from `aggregate`, deliberately
-----------------------------------------------------
`group_by` EXCLUDES a row whose key is null and counts it in `null_key_rows`; here a
null partition key forms its own partition and the row keeps its window value, which is
what `PARTITION BY` means and what `query.plan`'s header already states. That divergence
is about a row belonging to no group versus belonging to the "unknown" group — a
different question from what equality means, and it is documented on both sides rather
than silently different. Within a partition column, two nulls are the same key, matching
what the presence-comparison here has always done.
"""
from columnar.array import Float64Array, float64_with_nulls
from columnar.batch import RecordBatch
from columnar.hash_index import CompositeKeyIndex, normalize_bits
from numeric.contract import (
    AGG_AVG,
    AGG_COUNT,
    AGG_MAX,
    AGG_MIN,
    AGG_SUM,
    AGG_UNKNOWN,
)
from pandas_groupby import (
    group_count_update,
    group_max_update,
    group_mean_update,
    group_min_update,
    group_sum_update,
)
from query.executor import sort_indices_multi

comptime NO_ROW: Int = -1

# An unbounded preceding frame — "everything in this partition up to and including me".
comptime FRAME_UNBOUNDED: Int = -1


struct Partitions(Copyable, Movable):
    """Row indices grouped by partition key, each group in window order.

    `groups` is flat and `starts`/`lengths` index into it, rather than a list of lists:
    one allocation for the whole partitioning, and a partition is a contiguous span
    that a frame can walk without indirection.
    """

    var groups: List[Int]
    var starts: List[Int]
    var lengths: List[Int]

    def __init__(out self, var groups: List[Int], var starts: List[Int], var lengths: List[Int]):
        self.groups = groups^
        self.starts = starts^
        self.lengths = lengths^

    def count(self) -> Int:
        return len(self.starts)

    def row_at(self, partition: Int, position: Int) -> Int:
        """Row index at `position` within `partition`, or NO_ROW past its edge.

        The single place a partition boundary is enforced. Every frame and offset
        function goes through it, so none of them can walk into a neighbour.
        """
        if partition < 0 or partition >= len(self.starts):
            return NO_ROW
        if position < 0 or position >= self.lengths[partition]:
            return NO_ROW
        return self.groups[self.starts[partition] + position]

    def partition_of(self, row: Int) -> Int:
        """Which partition a row belongs to, or -1. Linear; for tests and lineage."""
        for p in range(len(self.starts)):
            for i in range(self.lengths[p]):
                if self.groups[self.starts[p] + i] == row:
                    return p
        return -1


def keys_equal_at(column: Float64Array, left_row: Int, right_row: Int) -> Bool:
    """Whether two rows carry the same key value, by `columnar.hash_index`'s definition.

    The ONE definition of key equality in this file, so `partition_rows` and
    `_rank_column` cannot drift into disagreeing about what a tie is — and so neither
    disagrees with `query.aggregate`, which groups through the same `normalize_bits`.

    Two absences are the same key: a partition of nulls is one partition and a run of
    nulls is one tie, which is what the presence comparison here has always done. Two
    NaNs are also the same key, because `normalize_bits` collapses them; raw `!=` would
    make every NaN row distinct from every other including itself.
    """
    var left_present = column.is_valid_at(left_row)
    var right_present = column.is_valid_at(right_row)
    if left_present != right_present:
        return False
    if not left_present:
        return True
    return normalize_bits(column.get(left_row)) == normalize_bits(
        column.get(right_row)
    )


def partition_rows(
    batch: RecordBatch,
    partition_columns: List[Int],
    order_columns: List[Int],
    descending: List[Bool],
    nulls_last: Bool,
) -> Partitions:
    """Group rows by partition key and order them within each partition.

    Ordering runs ONCE over the whole batch, keyed by the partition columns first and
    the order columns after — so a single stable multi-key sort produces every
    partition already in window order. Sorting per partition would be the obvious
    implementation and would cost a sort per group.

    Grouping is a HASH on the key tuple, not a cut between adjacent rows
    -------------------------------------------------------------------
    The earlier implementation walked the sorted rows and started a new partition
    wherever the key differed from the previous row's. That is only sound if equal keys
    are adjacent, and for a NaN key they are not: `executor._key_precedes` answers False
    in both directions for a NaN, so a NaN neither moves nor lets anything move past it
    and NaN rows stay wherever they started. Combined with `!=`, which is True for every
    pair of NaNs, EVERY NaN row became its own single-row partition while
    `aggregate.group_by` put them all in one group — the same column grouped two ways,
    two answers.

    So the key tuple goes through the frozen `columnar.hash_index.CompositeKeyIndex`,
    which is what `aggregate.group_by_multi` uses, and partition membership no longer
    depends on the sort having ordered the key at all. Each column contributes TWO
    components, `(present, value)`, because the index has no notion of a null and a
    present 0.0 must not collide with an absent cell; `normalize_bits` inside the index
    then does the NaN and `-0.0` collapsing (see the module header).

    Equal keys still occupy a CONTIGUOUS span of `groups`, in the sorted order, and
    partitions still appear in order of first appearance — so for key columns with no
    NaN this returns exactly what the adjacency cut returned. Two extra `Int` lists of
    `len(ordered)` are the cost; the caller's row cap lives in `query.plan`.

    An empty `partition_columns` is one partition over everything, which is what
    `OVER (ORDER BY ...)` with no PARTITION BY means.
    """
    var sort_keys = List[Int]()
    var sort_desc = List[Bool]()
    for i in range(len(partition_columns)):
        sort_keys.append(partition_columns[i])
        sort_desc.append(False)
    for i in range(len(order_columns)):
        sort_keys.append(order_columns[i])
        sort_desc.append(descending[i] if i < len(descending) else False)

    var ordered = sort_indices_multi(batch, sort_keys, sort_desc, nulls_last)

    var starts = List[Int]()
    var lengths = List[Int]()
    if len(partition_columns) == 0:
        starts.append(0)
        lengths.append(len(ordered))
        return Partitions(ordered^, starts^, lengths^)

    var key_cols = List[Float64Array]()
    for i in range(len(partition_columns)):
        key_cols.append(batch.column(partition_columns[i]))
    var width = len(key_cols)

    # Pass 1: a partition slot per sorted position, assigned in order of first
    # appearance. `key` is allocated once and overwritten per row rather than built per
    # row, so grouping costs no allocation per row.
    var index = CompositeKeyIndex(2 * width, 64)
    var key = List[Float64]()
    for _ in range(2 * width):
        key.append(0.0)
    var slot_of_position = List[Int]()
    for position in range(len(ordered)):
        var row = ordered[position]
        for c in range(width):
            var present = key_cols[c].is_valid_at(row)
            key[2 * c] = 1.0 if present else 0.0
            key[2 * c + 1] = key_cols[c].get(row) if present else 0.0
        var next_slot = len(lengths)
        var slot = index.get_or_assign(key, next_slot)
        if slot == next_slot:
            # A newly assigned slot; `lengths` grows with it, and this is the only place
            # the index and the length array can get out of step.
            lengths.append(0)
        lengths[slot] += 1
        slot_of_position.append(slot)

    # Pass 2: lay the partitions out contiguously. `starts` is the prefix sum of
    # `lengths`, and a per-partition cursor scatters each row into its own span while
    # preserving the sorted order within it.
    var offset = 0
    var cursor = List[Int]()
    for p in range(len(lengths)):
        starts.append(offset)
        cursor.append(offset)
        offset += lengths[p]

    var groups = List[Int]()
    for _ in range(len(ordered)):
        groups.append(0)
    for position in range(len(ordered)):
        # Every index here is in range by construction: a slot is < len(cursor), and a
        # cursor stays inside its own span because the span is exactly that slot's
        # count. Rule 1 — a read past the end would take the worker down.
        var slot = slot_of_position[position]
        groups[cursor[slot]] = ordered[position]
        cursor[slot] += 1

    return Partitions(groups^, starts^, lengths^)


def row_number(batch: RecordBatch, partitions: Partitions) -> Float64Array:
    """1-based position within the partition. Never null, never tied."""
    var values = List[Float64]()
    var mask = List[Bool]()
    for _ in range(batch.n_rows):
        values.append(0.0)
        mask.append(False)
    for p in range(partitions.count()):
        for i in range(partitions.lengths[p]):
            var row = partitions.row_at(p, i)
            values[row] = Float64(i + 1)
            mask[row] = True
    return float64_with_nulls(values^, mask)


def _rank_column(
    batch: RecordBatch,
    partitions: Partitions,
    order_column: Int,
    dense: Bool,
) -> Float64Array:
    """rank (gaps after ties) or dense_rank (no gaps), depending on `dense`.

    One implementation for both, because the difference is a single counter: `rank`
    advances by the size of the tied run, `dense_rank` by one. Written once so the two
    cannot drift into disagreeing about what a tie is.

    A tie is `keys_equal_at`, the same equality `partition_rows` groups by, so two NaNs
    tie rather than ranking 1 and 2 — one notion of equality per package, and
    `columnar.hash_index` is the reference for it (see the module header).
    """
    var key = batch.column(order_column)
    var values = List[Float64]()
    var mask = List[Bool]()
    for _ in range(batch.n_rows):
        values.append(0.0)
        mask.append(False)

    for p in range(partitions.count()):
        var current_rank = 1
        var seen = 0
        for i in range(partitions.lengths[p]):
            var row = partitions.row_at(p, i)
            if i > 0:
                var previous = partitions.row_at(p, i - 1)
                var tied = keys_equal_at(key, previous, row)
                if not tied:
                    if dense:
                        # Next distinct value, next rank. No gaps.
                        current_rank = current_rank + 1
                    else:
                        # Competition rank: skip past everyone already ranked, which is
                        # what leaves the gap after a tie.
                        current_rank = 1 + seen
            values[row] = Float64(current_rank)
            mask[row] = True
            seen += 1
    return float64_with_nulls(values^, mask)


def rank(batch: RecordBatch, partitions: Partitions, order_column: Int) -> Float64Array:
    """Competition rank: 10,20,20,30 -> 1,2,2,4. Gaps after a tie."""
    return _rank_column(batch, partitions, order_column, False)


def dense_rank(
    batch: RecordBatch, partitions: Partitions, order_column: Int
) -> Float64Array:
    """Dense rank: 10,20,20,30 -> 1,2,2,3. No gaps."""
    return _rank_column(batch, partitions, order_column, True)


def lag_lead(
    batch: RecordBatch,
    partitions: Partitions,
    value_column: Int,
    offset: Int,
) -> Float64Array:
    """The value `offset` rows away within the partition. Negative reads backwards.

    `lag(1)` is `offset = -1`, `lead(1)` is `offset = 1`. Past the partition edge the
    result is null — never the neighbouring partition's row, which is the bug this
    function exists to make impossible. An offset of 0 is the row's own value.
    """
    var source = batch.column(value_column)
    var values = List[Float64]()
    var mask = List[Bool]()
    for _ in range(batch.n_rows):
        values.append(0.0)
        mask.append(False)

    for p in range(partitions.count()):
        for i in range(partitions.lengths[p]):
            var row = partitions.row_at(p, i)
            var other = partitions.row_at(p, i + offset)
            if other == NO_ROW:
                continue
            if not source.is_valid_at(other):
                continue
            values[row] = source.get(other)
            mask[row] = True
    return float64_with_nulls(values^, mask)


def framed_aggregate(
    batch: RecordBatch,
    partitions: Partitions,
    value_column: Int,
    opcode: Int,
    preceding: Int,
) -> Float64Array:
    """A running aggregate over a trailing frame within each partition.

    `preceding = FRAME_UNBOUNDED` is a cumulative aggregate over the whole partition up
    to and including the current row. `preceding = k` is a rolling window of `k+1` rows
    ending at the current row.

    Frame boundaries clamp to the partition start, which is why an early row in a
    rolling window aggregates fewer rows rather than borrowing from the partition
    before it.

    Null values inside the frame are skipped, not treated as zero. An empty frame
    follows `numeric.contract`: count and sum give 0, everything else gives null.
    """
    var source = batch.column(value_column)
    var values = List[Float64]()
    var mask = List[Bool]()
    for _ in range(batch.n_rows):
        values.append(0.0)
        mask.append(False)
    if opcode == AGG_UNKNOWN:
        return float64_with_nulls(values^, mask)

    for p in range(partitions.count()):
        for i in range(partitions.lengths[p]):
            var row = partitions.row_at(p, i)
            var frame_start = 0
            if preceding != FRAME_UNBOUNDED:
                frame_start = i - preceding
                if frame_start < 0:
                    frame_start = 0

            var count: Float64 = 0.0
            var total: Float64 = 0.0
            var mean: Float64 = 0.0
            var minimum: Float64 = 0.0
            var maximum: Float64 = 0.0
            var seen = False
            for j in range(frame_start, i + 1):
                var member = partitions.row_at(p, j)
                if member == NO_ROW or not source.is_valid_at(member):
                    continue
                var value = source.get(member)
                count = group_count_update(count)
                total = group_sum_update(total, value)
                mean = group_mean_update(mean, value, count)
                if not seen:
                    minimum = value
                    maximum = value
                    seen = True
                else:
                    minimum = group_min_update(minimum, value)
                    maximum = group_max_update(maximum, value)

            if opcode == AGG_COUNT:
                values[row] = count
                mask[row] = True
            elif opcode == AGG_SUM:
                values[row] = total
                mask[row] = True
            elif seen:
                if opcode == AGG_AVG:
                    values[row] = mean
                elif opcode == AGG_MIN:
                    values[row] = minimum
                elif opcode == AGG_MAX:
                    values[row] = maximum
                else:
                    continue
                mask[row] = True
    return float64_with_nulls(values^, mask)


def cumulative(
    batch: RecordBatch,
    partitions: Partitions,
    value_column: Int,
    opcode: Int,
) -> Float64Array:
    """A running aggregate over the whole partition so far."""
    return framed_aggregate(
        batch, partitions, value_column, opcode, FRAME_UNBOUNDED
    )


def partition_total(
    batch: RecordBatch,
    partitions: Partitions,
    value_column: Int,
    opcode: Int,
) -> Float64Array:
    """The partition's aggregate, broadcast to every row in it.

    What `SUM(x) OVER (PARTITION BY g)` means: the group's total on every row, so a
    share-of-total can be computed without a join back. Distinct from `cumulative`,
    which grows down the partition.
    """
    var source = batch.column(value_column)
    var values = List[Float64]()
    var mask = List[Bool]()
    for _ in range(batch.n_rows):
        values.append(0.0)
        mask.append(False)
    if opcode == AGG_UNKNOWN:
        return float64_with_nulls(values^, mask)

    for p in range(partitions.count()):
        var count: Float64 = 0.0
        var total: Float64 = 0.0
        var mean: Float64 = 0.0
        var minimum: Float64 = 0.0
        var maximum: Float64 = 0.0
        var seen = False
        for i in range(partitions.lengths[p]):
            var member = partitions.row_at(p, i)
            if member == NO_ROW or not source.is_valid_at(member):
                continue
            var value = source.get(member)
            count = group_count_update(count)
            total = group_sum_update(total, value)
            mean = group_mean_update(mean, value, count)
            if not seen:
                minimum = value
                maximum = value
                seen = True
            else:
                minimum = group_min_update(minimum, value)
                maximum = group_max_update(maximum, value)

        var answer: Float64 = 0.0
        var answerable = True
        if opcode == AGG_COUNT:
            answer = count
        elif opcode == AGG_SUM:
            answer = total
        elif not seen:
            answerable = False
        elif opcode == AGG_AVG:
            answer = mean
        elif opcode == AGG_MIN:
            answer = minimum
        elif opcode == AGG_MAX:
            answer = maximum
        else:
            answerable = False

        if answerable:
            for i in range(partitions.lengths[p]):
                var member = partitions.row_at(p, i)
                if member != NO_ROW:
                    values[member] = answer
                    mask[member] = True
    return float64_with_nulls(values^, mask)


def describe_partitions(partitions: Partitions) -> String:
    """Partition count and the largest partition size, for lineage."""
    var largest = 0
    for p in range(partitions.count()):
        if partitions.lengths[p] > largest:
            largest = partitions.lengths[p]
    return (
        String(partitions.count())
        + " partitions, largest "
        + String(largest)
        + " rows"
    )
