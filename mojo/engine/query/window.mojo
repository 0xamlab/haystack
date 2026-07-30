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
"""
from columnar.array import Float64Array, float64_with_nulls
from columnar.batch import RecordBatch
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

    fn __init__(out self, var groups: List[Int], var starts: List[Int], var lengths: List[Int]):
        self.groups = groups^
        self.starts = starts^
        self.lengths = lengths^

    fn count(self) -> Int:
        return len(self.starts)

    fn row_at(self, partition: Int, position: Int) -> Int:
        """Row index at `position` within `partition`, or NO_ROW past its edge.

        The single place a partition boundary is enforced. Every frame and offset
        function goes through it, so none of them can walk into a neighbour.
        """
        if partition < 0 or partition >= len(self.starts):
            return NO_ROW
        if position < 0 or position >= self.lengths[partition]:
            return NO_ROW
        return self.groups[self.starts[partition] + position]

    fn partition_of(self, row: Int) -> Int:
        """Which partition a row belongs to, or -1. Linear; for tests and lineage."""
        for p in range(len(self.starts)):
            for i in range(self.lengths[p]):
                if self.groups[self.starts[p] + i] == row:
                    return p
        return -1


fn partition_rows(
    batch: RecordBatch,
    partition_columns: List[Int],
    order_columns: List[Int],
    descending: List[Bool],
    nulls_last: Bool,
) -> Partitions:
    """Group rows by partition key and order them within each partition.

    Ordering runs ONCE over the whole batch, keyed by the partition columns first and
    the order columns after — so a single stable multi-key sort produces every
    partition already in window order, contiguously. Sorting per partition would be the
    obvious implementation and would cost a sort per group.

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

    # Walk the ordered rows and cut a new partition whenever the key tuple changes.
    # Sound only because the sort put the partition columns first: equal keys are
    # adjacent by construction, so no index is needed here.
    var key_cols = List[Float64Array]()
    for i in range(len(partition_columns)):
        key_cols.append(batch.column(partition_columns[i]))

    var current_start = 0
    for position in range(len(ordered)):
        if position == 0:
            continue
        var previous = ordered[position - 1]
        var row = ordered[position]
        var changed = False
        for c in range(len(key_cols)):
            var prev_present = key_cols[c].is_valid_at(previous)
            var row_present = key_cols[c].is_valid_at(row)
            if prev_present != row_present:
                changed = True
            elif prev_present and key_cols[c].get(previous) != key_cols[c].get(row):
                changed = True
        if changed:
            starts.append(current_start)
            lengths.append(position - current_start)
            current_start = position
    if len(ordered) > 0:
        starts.append(current_start)
        lengths.append(len(ordered) - current_start)

    return Partitions(ordered^, starts^, lengths^)


fn row_number(batch: RecordBatch, partitions: Partitions) -> Float64Array:
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


fn _rank_column(
    batch: RecordBatch,
    partitions: Partitions,
    order_column: Int,
    dense: Bool,
) -> Float64Array:
    """rank (gaps after ties) or dense_rank (no gaps), depending on `dense`.

    One implementation for both, because the difference is a single counter: `rank`
    advances by the size of the tied run, `dense_rank` by one. Written once so the two
    cannot drift into disagreeing about what a tie is.
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
                var prev_present = key.is_valid_at(previous)
                var row_present = key.is_valid_at(row)
                var tied = prev_present == row_present and (
                    not row_present or key.get(previous) == key.get(row)
                )
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


fn rank(batch: RecordBatch, partitions: Partitions, order_column: Int) -> Float64Array:
    """Competition rank: 10,20,20,30 -> 1,2,2,4. Gaps after a tie."""
    return _rank_column(batch, partitions, order_column, False)


fn dense_rank(
    batch: RecordBatch, partitions: Partitions, order_column: Int
) -> Float64Array:
    """Dense rank: 10,20,20,30 -> 1,2,2,3. No gaps."""
    return _rank_column(batch, partitions, order_column, True)


fn lag_lead(
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


fn framed_aggregate(
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


fn cumulative(
    batch: RecordBatch,
    partitions: Partitions,
    value_column: Int,
    opcode: Int,
) -> Float64Array:
    """A running aggregate over the whole partition so far."""
    return framed_aggregate(
        batch, partitions, value_column, opcode, FRAME_UNBOUNDED
    )


fn partition_total(
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


fn describe_partitions(partitions: Partitions) -> String:
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
