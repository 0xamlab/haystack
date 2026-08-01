"""
query.aggregate — one-pass hash aggregate over a RecordBatch. Zero Python.

The frozen primitives this drives
---------------------------------
`pandas_groupby.mojo` has held exactly the right inner loop the whole time —
`group_mean_update` (Welford), `group_variance_update`, `group_min/max/sum/count_update`,
`group_std_from_variance` — and **nothing has ever called it**. This is the driver
those primitives were missing. They are used unchanged; all the new code here is the
grouping and the accumulator bookkeeping around them.

Why one pass matters
--------------------
The existing group-by paths materialise every value per group before reducing:
`buckets.setdefault(key, []).append(value)` in the Python path, and a nested
rescan-per-group in `data/dataframe.mojo` and `database.mojo`. Both are O(n) memory in
the largest group, and the Mojo ones are O(n·k) in time.

Streaming accumulators make it O(groups) memory and one pass in time, which is the
whole reason Welford is in `pandas_groupby` rather than a second sum-of-squares loop.

Nulls and empties follow numeric.contract
-----------------------------------------
A null contributes to no accumulator: it is not a zero. A group whose values are all
null has a count of 0 and no mean — absent, not 0.0, matching `numeric.reduce`. The
existing path returns 0.0 there, which is a real-looking answer to a question with no
answer.

Group keys are Float64 because the batch is. String keys need `columnar.array`'s
StringArray in the batch first; the hash index below is keyed on the bit pattern, so
it will extend without changing shape.

Parallel grouping (2026-08)
---------------------------
`group_by` and `group_by_multi` fan out over contiguous row bands above
`PARALLEL_MIN_ROWS`: one PRIVATE hash table and accumulator array per worker (no
locks, no sharing), then a SEQUENTIAL merge in worker-index order. The same shape
as `determinism.reduce_det.det_sum_parallel` and `gemm.blocked`: private state,
deterministic merge, and a measured crossover below which one thread is faster.

What the merge preserves, exactly and provably:

  * group ORDER stays global first-appearance order for EVERY worker count.
    Bands are contiguous and merged in band order, so the first band containing a
    group is the band holding its globally first row, and within a band local
    insertion order is first-appearance order. That composes to the global order,
    independent of where the band boundaries fall — the order promise this module
    has always made survives unchanged.
  * counts, min and max are bit-identical to the single-worker path: counting and
    comparison have no association to reorder.
  * sums, means and m2 are combined with the standard parallel-Welford merge, so
    they differ from the sequential fold only by floating-point association —
    same inputs, same worker count, same machine is bit-reproducible, and across
    worker counts the suite pins the drift to tolerance.

`group_by_parallel` / `group_by_multi_parallel` take the worker count explicitly
(that is what the suite uses to compare 1 worker against N); the unsuffixed
entry points plan it via `planned_workers`, which is where the crossover lives.
"""
from std.algorithm import parallelize
from std.sys import info

from columnar.array import Float64Array, float64_with_nulls
from columnar.batch import RecordBatch
from columnar.hash_index import CompositeKeyIndex, HashIndex
from numeric.contract import (
    AGG_AVG,
    AGG_COUNT,
    AGG_MAX,
    AGG_MIN,
    AGG_STD,
    AGG_SUM,
    AGG_VAR,
    aggregation_token,
)
from pandas_groupby import (
    group_count_update,
    group_max_update,
    group_mean_update,
    group_min_update,
    group_std_from_variance,
    group_sum_update,
    group_variance_update,
)

comptime PARALLEL_MIN_ROWS: Int = 1 << 16
"""Below ~65k rows, group in one thread.

`parallelize` costs tens of microseconds to fan out and join, and the merge costs
O(workers x groups) on top. Measured on this host (16 physical cores, 100-group
key): the parallel path crosses the serial one between 16k and 64k rows, so the
threshold sits at the first power of two where the win is unambiguous. Same
pattern and same reasoning as `PARALLEL_MIN_CELLS` in `gemm/blocked.mojo`."""


fn planned_workers(n_rows: Int, requested: Int) -> Int:
    """How many workers the unsuffixed entry points will actually use.

    The crossover policy in one testable place: below `PARALLEL_MIN_ROWS` the
    answer is 1 whatever was requested — a small input must not pay the fan-out —
    and above it the request is honoured, clamped to one row per worker and to a
    floor of 1 for a non-positive request (a computed core count that came back 0
    wants a working aggregate, not an error).
    """
    if requested < 1:
        return 1
    if n_rows < PARALLEL_MIN_ROWS:
        return 1
    if requested > n_rows:
        return n_rows
    return requested


struct GroupAccumulator(Copyable, Movable):
    """Streaming state for one group: enough for every supported aggregation.

    Carries all of them rather than only the requested one so a single pass can
    answer several aggregations at once — the common shape of a report — without
    re-scanning per aggregate.
    """

    var key: Float64
    var count: Float64
    var total: Float64
    var mean: Float64
    var m2: Float64
    var minimum: Float64
    var maximum: Float64
    var seen: Bool

    fn __init__(out self, key: Float64):
        self.key = key
        self.count = 0.0
        self.total = 0.0
        self.mean = 0.0
        self.m2 = 0.0
        self.minimum = 0.0
        self.maximum = 0.0
        self.seen = False

    fn observe(mut self, value: Float64):
        """Fold one live value in, using the frozen update primitives."""
        self.count = group_count_update(self.count)
        self.total = group_sum_update(self.total, value)
        var new_mean = group_mean_update(self.mean, value, self.count)
        self.m2 = group_variance_update(self.m2, self.mean, value, new_mean)
        self.mean = new_mean
        if not self.seen:
            self.minimum = value
            self.maximum = value
            self.seen = True
        else:
            self.minimum = group_min_update(self.minimum, value)
            self.maximum = group_max_update(self.maximum, value)

    fn merge_from(mut self, other: GroupAccumulator):
        """Fold another accumulator's state in — the parallel-merge combine.

        The mean/m2 update is Chan et al.'s pairwise combine, the standard
        parallel-variance merge:

            n     = n_a + n_b
            delta = mean_b - mean_a
            mean  = mean_a + delta * n_b / n
            M2    = M2_a + M2_b + delta^2 * n_a * n_b / n

        The naive `M2_a + M2_b` is wrong by exactly the between-bands term
        `delta^2 * n_a * n_b / n`, and the suite proves that with two bands whose
        means differ. min/max reuse the frozen update primitives — a merge is
        just an update with the other side's extremum. An empty side (count 0)
        contributes nothing, matching how a null value moves no accumulator.
        """
        if other.count == 0.0:
            return
        if self.count == 0.0:
            self.count = other.count
            self.total = other.total
            self.mean = other.mean
            self.m2 = other.m2
            self.minimum = other.minimum
            self.maximum = other.maximum
            self.seen = other.seen
            return
        var combined = self.count + other.count
        var delta = other.mean - self.mean
        self.m2 = self.m2 + other.m2 + delta * delta * self.count * other.count / combined
        self.mean = self.mean + delta * (other.count / combined)
        self.total = self.total + other.total
        self.count = combined
        self.minimum = group_min_update(self.minimum, other.minimum)
        self.maximum = group_max_update(self.maximum, other.maximum)

    fn value_for(self, opcode: Int) -> Float64:
        if opcode == AGG_COUNT:
            return self.count
        if opcode == AGG_SUM:
            return self.total
        if opcode == AGG_AVG:
            return self.mean
        if opcode == AGG_MIN:
            return self.minimum
        if opcode == AGG_MAX:
            return self.maximum
        if opcode == AGG_VAR:
            # Guarded, not merely "only called behind has_answer". value_for is public,
            # and with count==1 this is 0.0/0.0 -> NaN, which propagates into a sum or a
            # comparison as a number-shaped non-answer. group_std_from_variance already
            # guards its own denominator; this now matches it.
            if self.count < 2.0:
                return 0.0
            return self.m2 / (self.count - 1.0)
        if opcode == AGG_STD:
            return group_std_from_variance(self.m2, self.count, 1.0)
        return 0.0

    fn has_answer(self, opcode: Int) -> Bool:
        """Whether this group can answer `opcode`, per numeric.contract.

        count and sum always can — 0 and 0.0 are real answers for an empty group.
        A mean/min/max of nothing does not exist, and a sample variance needs two
        observations.
        """
        if opcode == AGG_COUNT or opcode == AGG_SUM:
            return True
        if opcode == AGG_VAR or opcode == AGG_STD:
            return self.count >= 2.0
        return self.count >= 1.0


struct GroupedResult(Copyable, Movable):
    """Group keys and one aggregated column, aligned by index."""

    var keys: List[Float64]
    var values: List[Float64]
    var present: List[Bool]
    var counts: List[Float64]
    var opcode: Int
    var null_key_rows: Int

    fn __init__(
        out self,
        var keys: List[Float64],
        var values: List[Float64],
        var present: List[Bool],
        var counts: List[Float64],
        opcode: Int,
        null_key_rows: Int,
    ):
        self.keys = keys^
        self.values = values^
        self.present = present^
        self.counts = counts^
        self.opcode = opcode
        self.null_key_rows = null_key_rows

    fn n_groups(self) -> Int:
        return len(self.keys)

    fn describe(self) -> String:
        return (
            aggregation_token(self.opcode)
            + " over "
            + String(len(self.keys))
            + " groups"
            + (
                " (" + String(self.null_key_rows) + " rows had a null key)"
                if self.null_key_rows > 0
                else ""
            )
        )


fn find_group(keys: List[Float64], key: Float64) -> Int:
    """Linear scan for `key` — O(groups). The small-group fast path.

    `group_by` uses `columnar.hash_index` instead, because `bench_query_plane.mojo`
    measures this scan at ~6 ns/row over 4 groups but ~2100 ns/row over 2048, while
    the hash lookup stays flat — a 200-360x difference in how the two scale.

    It stays exported because the same benchmark shows the crossover sits near 32
    groups: below that the scan is genuinely *faster* than hashing, since a handful of
    float compares beat a hash plus a probe. A caller that knows it has a few groups
    should use this. It is also what the hash path is checked against in the tests, so
    the two agreeing is verified rather than assumed.
    """
    for i in range(len(keys)):
        if keys[i] == key:
            return i
    return -1


fn _finish_groups(
    keys: List[Float64],
    accumulators: List[GroupAccumulator],
    opcode: Int,
    null_key_rows: Int,
) -> GroupedResult:
    """Accumulators to a result — one extraction shared by every path, so the
    serial and parallel forms cannot disagree about answerability."""
    var out_keys = keys.copy()
    var values = List[Float64]()
    var present = List[Bool]()
    var counts = List[Float64]()
    for i in range(len(accumulators)):
        ref acc = accumulators[i]
        var answerable = acc.has_answer(opcode)
        values.append(acc.value_for(opcode) if answerable else 0.0)
        present.append(answerable)
        counts.append(acc.count)
    return GroupedResult(out_keys^, values^, present^, counts^, opcode, null_key_rows)


fn group_by(
    batch: RecordBatch,
    key_column: Int,
    value_column: Int,
    opcode: Int,
) -> GroupedResult:
    """Aggregate `value_column` grouped by `key_column`, in one pass.

    Rows with a null KEY are excluded and counted separately — they belong to no
    group, and silently folding them into one would invent a category. Rows with a
    null VALUE join their group but contribute to no accumulator.

    Group slots come from `columnar.hash_index`, so the per-row cost does not grow
    with the number of groups. Insertion order is preserved in `keys`, which makes the
    result reproducible run to run rather than dependent on table layout.

    Above `PARALLEL_MIN_ROWS` the scan fans out over row bands (see the module
    header for what that preserves — order exactly, counts/min/max exactly, float
    folds to association). Below it, one thread, bit-identical to what this
    function has always produced.
    """
    return group_by_parallel(
        batch,
        key_column,
        value_column,
        opcode,
        planned_workers(batch.n_rows, info.num_physical_cores()),
    )


fn group_by_parallel(
    batch: RecordBatch,
    key_column: Int,
    value_column: Int,
    opcode: Int,
    n_workers: Int,
) -> GroupedResult:
    """`group_by` on an explicit worker count. 1 is exactly the serial path.

    The worker count is honoured (clamped to one row per worker), NOT planned:
    this is the function the suite uses to hold the data fixed and vary only the
    parallelism, so it must not second-guess the caller. Use `group_by` unless
    you are measuring or testing the parallelism itself.
    """
    var key_col = batch.column(key_column)
    var value_col = batch.column(value_column)
    var n_rows = batch.n_rows

    var workers = n_workers
    if workers < 1:
        workers = 1
    if workers > n_rows:
        workers = n_rows

    if workers <= 1:
        # The serial path, unchanged: small inputs keep producing bit-identical
        # results to every release since this module landed.
        var keys = List[Float64]()
        var accumulators = List[GroupAccumulator]()
        var index = HashIndex(64)
        var null_key_rows = 0

        for r in range(n_rows):
            if not key_col.is_valid_at(r):
                null_key_rows += 1
                continue
            var key = key_col.get(r)
            var next_slot = len(keys)
            var slot = index.get_or_assign(key, next_slot)
            if slot == next_slot:
                # A newly assigned slot; the accumulator array must grow with it, and this
                # is the only place the two can get out of step.
                keys.append(key)
                accumulators.append(GroupAccumulator(key))
            # A null value still belongs to the group; it just moves no accumulator.
            if value_col.is_valid_at(r):
                accumulators[slot].observe(value_col.get(r))

        return _finish_groups(keys, accumulators, opcode, null_key_rows)

    # ── parallel: private tables per band, sequential merge in band order ──────
    # Contiguous bands, one slot of worker-owned state each. No worker touches
    # another's slot, so there is no lock and no false sharing on the Lists
    # themselves — the same ownership shape as det_sum_parallel.
    var band = (n_rows + workers - 1) // workers
    var w_keys = List[List[Float64]](capacity=workers)
    var w_accs = List[List[GroupAccumulator]](capacity=workers)
    var w_nulls = List[Int](capacity=workers)
    for _ in range(workers):
        w_keys.append(List[Float64]())
        w_accs.append(List[GroupAccumulator]())
        w_nulls.append(0)
    var kp = w_keys.unsafe_ptr()
    var ap = w_accs.unsafe_ptr()
    var np = w_nulls.unsafe_ptr()

    @parameter
    fn band_worker(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n_rows:
            hi = n_rows
        # The hash table is worker-LOCAL: group slots are meaningful only against
        # this worker's key/accumulator lists, and are renumbered by the merge.
        var index = HashIndex(64)
        var nulls = 0
        for r in range(lo, hi):
            if not key_col.is_valid_at(r):
                nulls += 1
                continue
            var key = key_col.get(r)
            var next_slot = len(kp[w])
            var slot = index.get_or_assign(key, next_slot)
            if slot == next_slot:
                kp[w].append(key)
                ap[w].append(GroupAccumulator(key))
            if value_col.is_valid_at(r):
                ap[w][slot].observe(value_col.get(r))
        np[w] = nulls

    parallelize[band_worker](workers)

    # Sequential merge in WORKER INDEX order. Bands are contiguous, so walking
    # workers in order visits groups in global first-appearance order — the
    # order promise costs nothing to keep.
    var keys = List[Float64]()
    var accumulators = List[GroupAccumulator]()
    var merged = HashIndex(64)
    var null_key_rows = 0
    for w in range(workers):
        null_key_rows += w_nulls[w]
        for i in range(len(w_keys[w])):
            var key = w_keys[w][i]
            var next_slot = len(keys)
            var slot = merged.get_or_assign(key, next_slot)
            if slot == next_slot:
                keys.append(key)
                accumulators.append(GroupAccumulator(key))
            accumulators[slot].merge_from(w_accs[w][i])

    return _finish_groups(keys, accumulators, opcode, null_key_rows)


struct MultiGroupedResult(Copyable, Movable):
    """A grouped result whose key is a tuple of columns.

    `key_tuples` is flat, `key_width` wide per group: group `g`'s key occupies
    `[g*key_width, (g+1)*key_width)`. Flat rather than nested so the result serializes
    the same way a column does, and so a group's key can be read without allocating.
    """

    var key_tuples: List[Float64]
    var key_width: Int
    var values: List[Float64]
    var present: List[Bool]
    var counts: List[Float64]
    var opcode: Int
    var null_key_rows: Int

    fn __init__(
        out self,
        var key_tuples: List[Float64],
        key_width: Int,
        var values: List[Float64],
        var present: List[Bool],
        var counts: List[Float64],
        opcode: Int,
        null_key_rows: Int,
    ):
        self.key_tuples = key_tuples^
        self.key_width = key_width
        self.values = values^
        self.present = present^
        self.counts = counts^
        self.opcode = opcode
        self.null_key_rows = null_key_rows

    fn n_groups(self) -> Int:
        if self.key_width <= 0:
            return 0
        return len(self.key_tuples) // self.key_width

    fn key_at(self, group: Int) -> List[Float64]:
        var out = List[Float64]()
        if group < 0 or group >= self.n_groups():
            return out^
        var base = group * self.key_width
        for i in range(self.key_width):
            out.append(self.key_tuples[base + i])
        return out^


fn _finish_multi(
    key_tuples: List[Float64],
    width: Int,
    accumulators: List[GroupAccumulator],
    opcode: Int,
    null_key_rows: Int,
) -> MultiGroupedResult:
    """Accumulators to a multi-key result — shared by the serial and parallel paths."""
    var out_tuples = key_tuples.copy()
    var values = List[Float64]()
    var present = List[Bool]()
    var counts = List[Float64]()
    for i in range(len(accumulators)):
        ref acc = accumulators[i]
        var answerable = acc.has_answer(opcode)
        values.append(acc.value_for(opcode) if answerable else 0.0)
        present.append(answerable)
        counts.append(acc.count)
    return MultiGroupedResult(
        out_tuples^, width, values^, present^, counts^, opcode, null_key_rows
    )


fn group_by_multi(
    batch: RecordBatch,
    key_columns: List[Int],
    value_column: Int,
    opcode: Int,
) -> MultiGroupedResult:
    """Group by several columns at once, in one pass and with no string keys.

    A row is excluded if ANY key column is null. That is stricter than dropping only
    fully-null keys, and it is the right rule: `(region=EU, channel=null)` is not a
    group, it is a row whose group is unknown, and putting it under `EU` would report
    a total for EU that includes rows nobody can attribute.

    Keys keep insertion order, so two runs over the same batch produce the same group
    order. That holds on the parallel path too — see the module header.
    """
    return group_by_multi_parallel(
        batch,
        key_columns,
        value_column,
        opcode,
        planned_workers(batch.n_rows, info.num_physical_cores()),
    )


fn group_by_multi_parallel(
    batch: RecordBatch,
    key_columns: List[Int],
    value_column: Int,
    opcode: Int,
    n_workers: Int,
) -> MultiGroupedResult:
    """`group_by_multi` on an explicit worker count. 1 is exactly the serial path.

    The per-row key buffer is allocated ONCE per scan and overwritten in place —
    a `List[Float64]` per row was this module's dominant cost at 1e7 rows (a heap
    allocation and free per row dwarfs the hash), measured at ~3x the per-row
    time of the reused buffer on the H2O q2 shape. `width == 0` (one group over
    everything) stays serial whatever was requested: it has no per-group hash
    work to spread, and a reduction over one accumulator is `aggregate_column`'s
    job, not a fan-out's.
    """
    var width = len(key_columns)
    var n_rows = batch.n_rows

    if width == 0:
        # No grouping columns is a single group over everything, not zero groups.
        var empty_tuples = List[Float64]()
        var single = GroupAccumulator(0.0)
        var value_col_all = batch.column(value_column)
        for r in range(n_rows):
            if value_col_all.is_valid_at(r):
                single.observe(value_col_all.get(r))
        var one_value = List[Float64]()
        var one_present = List[Bool]()
        var one_count = List[Float64]()
        var answerable_all = single.has_answer(opcode)
        one_value.append(single.value_for(opcode) if answerable_all else 0.0)
        one_present.append(answerable_all)
        one_count.append(single.count)
        return MultiGroupedResult(
            empty_tuples^, 0, one_value^, one_present^, one_count^, opcode, 0
        )

    var key_cols = List[Float64Array]()
    for i in range(width):
        key_cols.append(batch.column(key_columns[i]))
    var value_col = batch.column(value_column)

    var workers = n_workers
    if workers < 1:
        workers = 1
    if workers > n_rows:
        workers = n_rows

    if workers <= 1:
        var key_tuples = List[Float64]()
        var accumulators = List[GroupAccumulator]()
        var index = CompositeKeyIndex(width, 64)
        var null_key_rows = 0

        # The reused key buffer: fixed width, overwritten per row. Rows that hit a
        # null key column leave later positions stale, and that is fine — those
        # rows are excluded before the buffer is read.
        var key = List[Float64](capacity=width)
        for _ in range(width):
            key.append(0.0)

        for r in range(n_rows):
            var any_null = False
            for c in range(width):
                if not key_cols[c].is_valid_at(r):
                    any_null = True
                    break
                key[c] = key_cols[c].get(r)
            if any_null:
                null_key_rows += 1
                continue

            var next_slot = len(accumulators)
            var slot = index.get_or_assign(key, next_slot)
            if slot == next_slot:
                accumulators.append(GroupAccumulator(key[0]))
                for c in range(width):
                    key_tuples.append(key[c])
            if value_col.is_valid_at(r):
                accumulators[slot].observe(value_col.get(r))

        return _finish_multi(key_tuples, width, accumulators, opcode, null_key_rows)

    # ── parallel: private composite tables per band, merge in band order ───────
    var band = (n_rows + workers - 1) // workers
    var w_tuples = List[List[Float64]](capacity=workers)
    var w_accs = List[List[GroupAccumulator]](capacity=workers)
    var w_nulls = List[Int](capacity=workers)
    for _ in range(workers):
        w_tuples.append(List[Float64]())
        w_accs.append(List[GroupAccumulator]())
        w_nulls.append(0)
    var tp = w_tuples.unsafe_ptr()
    var ap = w_accs.unsafe_ptr()
    var np = w_nulls.unsafe_ptr()

    @parameter
    fn band_worker(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n_rows:
            hi = n_rows
        var index = CompositeKeyIndex(width, 64)
        var nulls = 0
        # One key buffer per WORKER, not per row — same reuse as the serial path.
        var key = List[Float64](capacity=width)
        for _ in range(width):
            key.append(0.0)
        for r in range(lo, hi):
            var any_null = False
            for c in range(width):
                if not key_cols[c].is_valid_at(r):
                    any_null = True
                    break
                key[c] = key_cols[c].get(r)
            if any_null:
                nulls += 1
                continue
            var next_slot = len(ap[w])
            var slot = index.get_or_assign(key, next_slot)
            if slot == next_slot:
                ap[w].append(GroupAccumulator(key[0]))
                for c in range(width):
                    tp[w].append(key[c])
            if value_col.is_valid_at(r):
                ap[w][slot].observe(value_col.get(r))
        np[w] = nulls

    parallelize[band_worker](workers)

    # Sequential merge in worker-index order; same order argument as group_by_parallel.
    var key_tuples = List[Float64]()
    var accumulators = List[GroupAccumulator]()
    var merged = CompositeKeyIndex(width, 64)
    var null_key_rows = 0
    var key = List[Float64](capacity=width)
    for _ in range(width):
        key.append(0.0)
    for w in range(workers):
        null_key_rows += w_nulls[w]
        var local_groups = len(w_accs[w])
        for g in range(local_groups):
            for c in range(width):
                key[c] = w_tuples[w][g * width + c]
            var next_slot = len(accumulators)
            var slot = merged.get_or_assign(key, next_slot)
            if slot == next_slot:
                accumulators.append(GroupAccumulator(key[0]))
                for c in range(width):
                    key_tuples.append(key[c])
            accumulators[slot].merge_from(w_accs[w][g])

    return _finish_multi(key_tuples, width, accumulators, opcode, null_key_rows)


fn aggregate_column(batch: RecordBatch, value_column: Int, opcode: Int) -> Float64:
    """Aggregate a whole column with no grouping. 0.0 when unanswerable.

    `aggregate_column_present` reports answerability; this is the convenience form for
    callers that have already checked.
    """
    var column = batch.column(value_column)
    var acc = GroupAccumulator(0.0)
    for r in range(column.length):
        if column.is_valid_at(r):
            acc.observe(column.get(r))
    if not acc.has_answer(opcode):
        return 0.0
    return acc.value_for(opcode)


fn aggregate_column_present(batch: RecordBatch, value_column: Int, opcode: Int) -> Bool:
    """Whether an ungrouped aggregate has an answer at all."""
    var column = batch.column(value_column)
    var acc = GroupAccumulator(0.0)
    for r in range(column.length):
        if column.is_valid_at(r):
            acc.observe(column.get(r))
    return acc.has_answer(opcode)


fn grouped_to_column(result: GroupedResult) -> Float64Array:
    """The aggregated values as a nullable column, absences preserved."""
    var values = List[Float64]()
    var mask = List[Bool]()
    for i in range(len(result.values)):
        values.append(result.values[i])
        mask.append(result.present[i])
    return float64_with_nulls(values^, mask)
