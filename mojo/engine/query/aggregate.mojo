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
  * counts are bit-identical to the single-worker path: counting has no
    association to reorder.
  * min and max are bit-identical to the single-worker path — including when a
    NaN appears among the VALUES, because a NaN contributes to no extremum
    (see "NaN values and the extrema" below). Comparison over the remaining
    live values has no association to reorder, and a tie between +0.0 and -0.0
    keeps the first appearance under any banding, because bands merge in band
    order and the frozen updates keep `current` on a tie.
  * sums, means and m2 are combined with the standard parallel-Welford merge, so
    they differ from the sequential fold only by floating-point association —
    same inputs, same worker count, same machine is bit-reproducible, and across
    worker counts the suite pins the drift to tolerance. A NaN value poisons
    them in EVERY band split identically, because NaN propagation through
    sum/mean/m2 is associative.

NaN values and the extrema (2026-08)
------------------------------------
A NaN VALUE (not a null: a live Float64 whose bits happen to be NaN — in-domain
here, since `hash_index` deliberately canonicalizes NaN keys) is excluded from
min and max, the IEEE-754 fmin/fmax rule: NaN is unordered, so it names no
minimum. It still counts, and it still poisons sum/mean/m2 — those folds treat
it associatively, so they cannot diverge across worker counts. A group whose
values are ALL NaN reports the canonical quiet NaN for min/max — the fmin/fmax
fold of all-NaN — with `present` true, matching the NaN its sum reports.

This is a policy, not just an optimisation detail: the previous behaviour
(seed min/max with the first value unconditionally, then update through the
frozen `group_min_update`, which keeps `current` when the comparison is false)
made the serial fold ORDER-DEPENDENT — NaN-first poisoned the extremum, NaN
anywhere else was dropped — and no band merge can reproduce an order-dependent,
non-associative fold. A band whose first row was NaN reported a NaN extremum,
the sequential merge then dropped that NaN via `group_min_update(live, NaN)`,
and every live value that band had folded was silently discarded: the same data
returned a different minimum at different worker counts, and `group_by` plans
workers from the machine's core count. The skip-NaN rule is associative, so
serial and every banding agree exactly, and the suite proves it.

`group_by_parallel` / `group_by_multi_parallel` take the worker count explicitly
(that is what the suite uses to compare 1 worker against N); the unsuffixed
entry points plan it via `planned_workers`, which is where the crossover lives.

Fused, radix-partitioned and code-indexed grouping (2026-08, round 2)
---------------------------------------------------------------------
Round 1 parallelized the scan; the remaining measured gap to polars/duckdb on
the H2O groupby tier had two causes, plus one cheap win, addressed by three new
entry points that COMPOSE the machinery above rather than replacing it:

  * `group_by_many` — one scan, one key hash and one probe per row, N
    accumulators updated per group. A question like "mean of v1..v3 by id4"
    was three full `group_by` passes (three hashings, three probes per row);
    now the per-group state is a contiguous STRIPE of `n_aggs` accumulators
    (`stripes[slot * n_aggs + j]`), so the per-row update walks one cache-line
    region instead of three separate tables. Same frozen `group_*_update`
    primitives, same `GroupAccumulator` — this is a driver, not new arithmetic.
  * `group_by_many_radix` — above `RADIX_MIN_GROUPS` distinct keys the round-1
    band merge is O(workers x groups) and each worker's table spans the FULL
    key space. Radix instead: pass 1 hashes each key ONCE (the same
    `hash_composite` the tables probe with), routes the row by the top
    `RADIX_BITS` bits into a worker-private bucket per partition; pass 2 builds
    each partition's table in ONE task from all workers' buckets, concatenated
    in band order — which is ascending global row order, so every group's
    accumulator is folded in exactly the serial order (bit-identical to one
    worker, stronger than the band path's merge-tolerance) and per-partition
    group lists ascend in first-appearance row. A final P-way merge on those
    first-row indices — O(groups x partitions), never rows — restores the
    module's global first-appearance order promise exactly.
  * `group_by_coded` — a single key column that is already dictionary CODES
    (`columnar.dictionary` hands them out dense from 0) with small known
    cardinality skips hashing entirely: the accumulator array is indexed by
    the code itself. Every present key is validated to be an integral value in
    [0, cardinality) BEFORE it indexes anything — an out-of-range code is a
    typed refusal (`GROUP_CODED_KEY_NOT_A_CODE`), never an out-of-bounds write,
    which in Mojo is an uncatchable abort that takes the worker process with it.

`group_by_many_parallel` picks band vs radix per call via `probe_cardinality`
over the first `CARDINALITY_PROBE_ROWS` rows. When the probe under-reads the
true cardinality the data is necessarily clustered (a group absent from the
probe window is concentrated later in the batch), which is exactly the shape
where each group touches few bands and the band merge is cheap anyway — the
probe's failure mode and the band path's cheap case coincide.
"""
from std.algorithm import parallelize
from std.memory import bitcast
from std.sys import info

from columnar.array import Float64Array, float64_with_nulls
from columnar.batch import RecordBatch
from columnar.hash_index import CANONICAL_NAN_BITS, CompositeKeyIndex, HashIndex, hash_composite
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


fn _canonical_nan() -> Float64:
    """The one quiet NaN this module reports, min/max of an all-NaN group.

    The same bit pattern `hash_index` canonicalizes NaN KEYS to, so an all-NaN
    extremum is deterministic down to the bits whatever NaN payloads arrived —
    which is what lets the bit-identical promise cover it.
    """
    return bitcast[DType.float64](CANONICAL_NAN_BITS)


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
        """Fold one live value in, using the frozen update primitives.

        A NaN value counts and poisons sum/mean/m2 (associatively — the same
        NaN answer under any banding), but contributes to NO extremum: NaN is
        unordered, so seeding or comparing with it would make min/max depend on
        where the NaN sits in the scan order, which no parallel merge can
        reproduce. `seen` therefore means "min/max hold a live, ordered
        extremum", not merely "a value arrived".
        """
        self.count = group_count_update(self.count)
        self.total = group_sum_update(self.total, value)
        var new_mean = group_mean_update(self.mean, value, self.count)
        self.m2 = group_variance_update(self.m2, self.mean, value, new_mean)
        self.mean = new_mean
        if value != value:
            # NaN — the only Float64 not equal to itself. No extremum to move.
            return
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
        just an update with the other side's extremum — but ONLY when the other
        side holds one: `seen` is false on a side whose values were all NaN
        (extrema skip NaN, see `observe`), and folding its stale 0.0 in would
        invent a value nobody observed. An empty side (count 0) contributes
        nothing, matching how a null value moves no accumulator.
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
        if other.seen:
            if self.seen:
                self.minimum = group_min_update(self.minimum, other.minimum)
                self.maximum = group_max_update(self.maximum, other.maximum)
            else:
                self.minimum = other.minimum
                self.maximum = other.maximum
                self.seen = True

    fn value_for(self, opcode: Int) -> Float64:
        if opcode == AGG_COUNT:
            return self.count
        if opcode == AGG_SUM:
            return self.total
        if opcode == AGG_AVG:
            return self.mean
        if opcode == AGG_MIN:
            if self.count >= 1.0 and not self.seen:
                # Values arrived but none ordered: every one was NaN. The
                # fmin fold of all-NaN is NaN — the canonical one, so the
                # answer has one bit pattern whatever payloads came in.
                return _canonical_nan()
            return self.minimum
        if opcode == AGG_MAX:
            if self.count >= 1.0 and not self.seen:
                return _canonical_nan()
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
    null VALUE join their group but contribute to no accumulator. A NaN VALUE is
    not a null: it counts and poisons sum/mean/m2, but names no min/max — the
    module header's "NaN values and the extrema" policy.

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
        # The serial path. One deliberate change from the module's first
        # release: a NaN VALUE no longer poisons min/max when it happens to
        # arrive first (see "NaN values and the extrema" in the module header) —
        # the old fold was order-dependent, which no parallel merge can match.
        # NaN-free inputs keep producing bit-identical results to every release.
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


# ═══════════════════════════════════════════════════════════════════════════════
# Fused multi-aggregate grouping — one scan, one probe per row, N accumulators
# ═══════════════════════════════════════════════════════════════════════════════

comptime RADIX_BITS: Int = 4
"""Partition count exponent: 16 partitions from the hash's top 4 bits.

Top bits rather than bottom because the open-addressed tables index with
`hash & mask` — the BOTTOM bits. Partitioning on the top bits keeps the two
uses of the one hash independent: within a partition the low bits still spread
keys across the whole table."""

comptime RADIX_PARTITIONS: Int = 1 << RADIX_BITS

comptime CARDINALITY_PROBE_ROWS: Int = 1 << 16
"""How many leading rows `probe_cardinality` reads before the band/radix choice.

The same 64k the parallel crossover uses: cheap against a >= PARALLEL_MIN_ROWS
scan (one hash per row, no accumulators), and on uniformly-mixed data — the
shape where the band merge is expensive — 64k rows saturate well past
`RADIX_MIN_GROUPS` distinct keys whenever the true count does."""

comptime RADIX_MIN_GROUPS: Int = 32768
"""PROBED distinct-key count at which `group_by_many_parallel` switches from
the band-merge path to the radix path.

Measured on this host (16 physical cores, 1e7 rows, 2 aggregates, load ~8;
sweep in bench_groupby_fused.mojo). `probed` is what `probe_cardinality`
reports over its 64k window for that true cardinality — the number this
threshold actually sees:

    true groups   probed   banded    radix     radix advantage
        10 000     9 986   0.075s    0.067s    ~par (0.97-1.13x across runs)
        16 384    16 076   0.062s    0.072s    0.86x
        32 768    28 352   0.088s    0.093s    0.95x
        50 000    36 594   0.119s    0.076s    1.57x
        65 536    41 466   0.142s    0.083s    1.72x
       100 000    48 154   0.210s    0.083s    2.54x

Below ~30k probed the paths are within noise of each other (the scatter's
bucket materialisation buys back roughly what the merge costs); from ~36k
probed the radix win is unambiguous and grows with cardinality. 32768 is the
first power of two above the measured par zone."""

comptime MAX_FUSED_AGGS: Int = 32
"""Ceiling on aggregates per fused call. The radix scatter packs per-row value
validity into one Int bitmask, so the ceiling keeps that total; a report
wanting more than 32 aggregates of one grouping can call twice."""

comptime MAX_CODED_CARDINALITY: Int = 4096
"""Ceiling on `group_by_coded`'s dense accumulator array, PER WORKER.

4096 stripes x up to 32 accumulators x ~64 bytes is ~8 MiB per worker at the
widest — bounded before allocation, not discovered by it. Beyond this the
dense array stops fitting cache and the hash path stops losing; DuckDB's
equivalent (perfect-hash grouping) draws the same order-of-magnitude line."""

# ── status codes: query.aggregate owns 330-339 (rule 4e: one integer, one
#    meaning per package; 300-329 are taken by columnar) ──────────────────────
comptime GROUP_CODED_OK: Int = 330
comptime GROUP_CODED_CARDINALITY_INVALID: Int = 331
comptime GROUP_CODED_KEY_NOT_A_CODE: Int = 332
comptime GROUP_CODED_BAD_REQUEST: Int = 333


struct ManyGroupedResult(Copyable, Movable):
    """Group keys and SEVERAL aggregated columns from one scan, aligned by index.

    `key_tuples` is flat, `key_width` wide per group — the `MultiGroupedResult`
    layout. `values`/`present`/`counts` are flat and GROUP-MAJOR: aggregate `j`
    of group `g` sits at `g * n_aggs + j`. Group-major because one group's
    aggregates are the unit a report row reads, so they should be contiguous —
    the same reason the accumulator stripes are laid out this way during the
    scan.

    `counts` is per (group, aggregate), not per group: each value column has
    its own nulls, so "how many observations fed this number" is a property of
    the pair, and one shared count would be wrong for every column but one.
    """

    var key_tuples: List[Float64]
    var key_width: Int
    var n_aggs: Int
    var opcodes: List[Int]
    var values: List[Float64]
    var present: List[Bool]
    var counts: List[Float64]
    var null_key_rows: Int

    fn __init__(
        out self,
        var key_tuples: List[Float64],
        key_width: Int,
        n_aggs: Int,
        var opcodes: List[Int],
        var values: List[Float64],
        var present: List[Bool],
        var counts: List[Float64],
        null_key_rows: Int,
    ):
        self.key_tuples = key_tuples^
        self.key_width = key_width
        self.n_aggs = n_aggs
        self.opcodes = opcodes^
        self.values = values^
        self.present = present^
        self.counts = counts^
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

    fn _flat(self, group: Int, agg: Int) -> Int:
        """Flat position, or -1 out of range — the bounds check every accessor shares."""
        if agg < 0 or agg >= self.n_aggs:
            return -1
        var flat = group * self.n_aggs + agg
        if group < 0 or flat >= len(self.values):
            return -1
        return flat

    fn value_at(self, group: Int, agg: Int) -> Float64:
        var flat = self._flat(group, agg)
        return self.values[flat] if flat >= 0 else 0.0

    fn present_at(self, group: Int, agg: Int) -> Bool:
        var flat = self._flat(group, agg)
        return self.present[flat] if flat >= 0 else False

    fn count_at(self, group: Int, agg: Int) -> Float64:
        var flat = self._flat(group, agg)
        return self.counts[flat] if flat >= 0 else 0.0


struct CodedGroupedResult(Copyable, Movable):
    """A `ManyGroupedResult` plus the status that says whether it exists.

    `group_by_coded` can REFUSE (bad cardinality, a key that is not a code, a
    malformed request), and a refusal must not look like an empty answer to a
    real question — so the status rides with the result. On any status other
    than `GROUP_CODED_OK` the result is EMPTY: zero groups, zero aggregates.
    """

    var status: Int
    var result: ManyGroupedResult

    fn __init__(out self, status: Int, var result: ManyGroupedResult):
        self.status = status
        self.result = result^

    fn ok(self) -> Bool:
        return self.status == GROUP_CODED_OK


fn coded_status_name(status: Int) -> String:
    """The vocabulary for 330-339."""
    if status == GROUP_CODED_OK:
        return "ok"
    if status == GROUP_CODED_CARDINALITY_INVALID:
        return "cardinality_invalid"
    if status == GROUP_CODED_KEY_NOT_A_CODE:
        return "key_not_a_code"
    if status == GROUP_CODED_BAD_REQUEST:
        return "bad_request"
    return "unknown"


fn _empty_many() -> ManyGroupedResult:
    """Zero groups, zero aggregates — what a malformed request gets back."""
    return ManyGroupedResult(
        List[Float64](), 0, 0, List[Int](), List[Float64](), List[Bool](), List[Float64](), 0
    )


fn _many_request_ok(value_columns: List[Int], opcodes: List[Int]) -> Bool:
    """Whether the (value column, opcode) pairing is well-formed.

    One opcode per value column, at least one, at most `MAX_FUSED_AGGS`. A
    mismatch is a caller bug with no right answer — pairing by position would
    silently aggregate the wrong column — so the entry points return the empty
    result rather than guessing.
    """
    var n_aggs = len(value_columns)
    if n_aggs < 1 or n_aggs > MAX_FUSED_AGGS:
        return False
    return len(opcodes) == n_aggs


fn _finish_many(
    key_tuples: List[Float64],
    width: Int,
    stripes: List[GroupAccumulator],
    n_aggs: Int,
    opcodes: List[Int],
    null_key_rows: Int,
) -> ManyGroupedResult:
    """Accumulator stripes to a result — one extraction shared by every fused
    path, so serial, banded, radix and coded cannot disagree about answerability."""
    var out_tuples = key_tuples.copy()
    var out_ops = opcodes.copy()
    var values = List[Float64]()
    var present = List[Bool]()
    var counts = List[Float64]()
    var n_groups = 0
    if n_aggs > 0:
        n_groups = len(stripes) // n_aggs
    for g in range(n_groups):
        for j in range(n_aggs):
            ref acc = stripes[g * n_aggs + j]
            var op = opcodes[j]
            var answerable = acc.has_answer(op)
            values.append(acc.value_for(op) if answerable else 0.0)
            present.append(answerable)
            counts.append(acc.count)
    return ManyGroupedResult(
        out_tuples^, width, n_aggs, out_ops^, values^, present^, counts^, null_key_rows
    )


fn _group_many_width0(
    batch: RecordBatch, value_columns: List[Int], opcodes: List[Int]
) -> ManyGroupedResult:
    """No key columns is one group over everything — `group_by_multi`'s rule,
    with a stripe of aggregates instead of one."""
    var n_aggs = len(value_columns)
    var value_cols = List[Float64Array]()
    for j in range(n_aggs):
        value_cols.append(batch.column(value_columns[j]))
    var stripes = List[GroupAccumulator]()
    for _ in range(n_aggs):
        stripes.append(GroupAccumulator(0.0))
    for r in range(batch.n_rows):
        for j in range(n_aggs):
            if value_cols[j].is_valid_at(r):
                stripes[j].observe(value_cols[j].get(r))
    return _finish_many(List[Float64](), 0, stripes, n_aggs, opcodes, 0)


fn probe_cardinality(batch: RecordBatch, key_columns: List[Int], probe_rows: Int) -> Int:
    """Distinct keys among the first `min(probe_rows, n_rows)` rows. Null keys skipped.

    The band/radix dispatch input. An ESTIMATE of the batch's cardinality, and a
    deliberate one-sided one: it can only under-count (a probe window cannot
    contain more distinct keys than the batch), and the under-count case implies
    clustering, which is the band path's cheap case — see the module header.
    """
    var width = len(key_columns)
    if width == 0:
        return 1
    var n = batch.n_rows
    if probe_rows < n:
        n = probe_rows
    if n <= 0:
        return 0
    if width == 1:
        var key_col = batch.column(key_columns[0])
        var index = HashIndex(64)
        for r in range(n):
            if not key_col.is_valid_at(r):
                continue
            _ = index.get_or_assign(key_col.get(r), index.size())
        return index.size()
    var key_cols = List[Float64Array]()
    for i in range(width):
        key_cols.append(batch.column(key_columns[i]))
    var index = CompositeKeyIndex(width, 64)
    var key = List[Float64](capacity=width)
    for _ in range(width):
        key.append(0.0)
    for r in range(n):
        var any_null = False
        for c in range(width):
            if not key_cols[c].is_valid_at(r):
                any_null = True
                break
            key[c] = key_cols[c].get(r)
        if any_null:
            continue
        _ = index.get_or_assign(key, index.size())
    return index.size()


fn group_by_many(
    batch: RecordBatch,
    key_columns: List[Int],
    value_columns: List[Int],
    opcodes: List[Int],
) -> ManyGroupedResult:
    """Aggregate SEVERAL value columns grouped by `key_columns`, in ONE pass.

    `opcodes[j]` applies to `value_columns[j]` — flat parallel lists, one
    result column per pair. The same column may appear twice with different
    opcodes. Key hashing and the group probe happen once per row however many
    aggregates are requested; that is the entire point (a three-aggregate
    question was three full scans).

    Everything `group_by`/`group_by_multi` promise holds here: rows with any
    null KEY column are excluded and tallied, a null VALUE joins its group but
    moves only its own accumulator, groups come back in global first-appearance
    order on every path and worker count.

    A malformed request — zero value columns, more than `MAX_FUSED_AGGS`, or
    `len(opcodes) != len(value_columns)` — returns the EMPTY result (zero
    groups, zero aggregates): pairing by position would silently aggregate the
    wrong column, and there is no status channel on this result on purpose
    (the coded path, which can refuse on DATA, carries one; a malformed
    request is a caller bug visible at the call site).
    """
    return group_by_many_parallel(
        batch,
        key_columns,
        value_columns,
        opcodes,
        planned_workers(batch.n_rows, info.num_physical_cores()),
    )


fn group_by_many_parallel(
    batch: RecordBatch,
    key_columns: List[Int],
    value_columns: List[Int],
    opcodes: List[Int],
    n_workers: Int,
) -> ManyGroupedResult:
    """`group_by_many` on an explicit worker count, band/radix chosen by probe.

    1 worker is exactly the serial path. Above 1, `probe_cardinality` over the
    first `CARDINALITY_PROBE_ROWS` rows picks the band-merge path (small key
    spaces: the merge is trivial and the scatter would be pure overhead) or the
    radix path (large key spaces: the O(workers x groups) merge and the
    full-key-space per-worker tables are what kill 100k-group questions).
    `group_by_many_banded` / `group_by_many_radix` pin either path directly —
    that is what the suite and the gate use to compare them on identical data.
    """
    if not _many_request_ok(value_columns, opcodes):
        return _empty_many()
    if len(key_columns) == 0:
        return _group_many_width0(batch, value_columns, opcodes)
    var workers = n_workers
    if workers < 1:
        workers = 1
    if workers > batch.n_rows:
        workers = batch.n_rows
    if workers <= 1:
        return _group_many_serial(batch, key_columns, value_columns, opcodes)
    if probe_cardinality(batch, key_columns, CARDINALITY_PROBE_ROWS) >= RADIX_MIN_GROUPS:
        return group_by_many_radix(batch, key_columns, value_columns, opcodes, workers)
    return group_by_many_banded(batch, key_columns, value_columns, opcodes, workers)


fn _group_many_serial(
    batch: RecordBatch,
    key_columns: List[Int],
    value_columns: List[Int],
    opcodes: List[Int],
) -> ManyGroupedResult:
    """The one-thread fused scan: one probe per row, a stripe update per group.

    Callers have already validated the request and handled width 0. Fold order
    is row order, so for a single value column this produces accumulator states
    bit-identical to `group_by`'s serial path — the equivalence the suite pins
    per opcode.
    """
    var width = len(key_columns)
    var n_aggs = len(value_columns)
    var n_rows = batch.n_rows
    var value_cols = List[Float64Array]()
    for j in range(n_aggs):
        value_cols.append(batch.column(value_columns[j]))

    var key_tuples = List[Float64]()
    var stripes = List[GroupAccumulator]()
    var null_key_rows = 0
    var group_count = 0

    if width == 1:
        var key_col = batch.column(key_columns[0])
        var index = HashIndex(64)
        for r in range(n_rows):
            if not key_col.is_valid_at(r):
                null_key_rows += 1
                continue
            var key = key_col.get(r)
            var slot = index.get_or_assign(key, group_count)
            if slot == group_count:
                group_count += 1
                key_tuples.append(key)
                for _ in range(n_aggs):
                    stripes.append(GroupAccumulator(key))
            for j in range(n_aggs):
                if value_cols[j].is_valid_at(r):
                    stripes[slot * n_aggs + j].observe(value_cols[j].get(r))
        return _finish_many(key_tuples, width, stripes, n_aggs, opcodes, null_key_rows)

    var key_cols = List[Float64Array]()
    for i in range(width):
        key_cols.append(batch.column(key_columns[i]))
    var index = CompositeKeyIndex(width, 64)
    # One key buffer per scan, overwritten per row — round 1's allocation fix.
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
        var slot = index.get_or_assign(key, group_count)
        if slot == group_count:
            group_count += 1
            for c in range(width):
                key_tuples.append(key[c])
            for _ in range(n_aggs):
                stripes.append(GroupAccumulator(key[0]))
        for j in range(n_aggs):
            if value_cols[j].is_valid_at(r):
                stripes[slot * n_aggs + j].observe(value_cols[j].get(r))
    return _finish_many(key_tuples, width, stripes, n_aggs, opcodes, null_key_rows)


fn group_by_many_banded(
    batch: RecordBatch,
    key_columns: List[Int],
    value_columns: List[Int],
    opcodes: List[Int],
    n_workers: Int,
) -> ManyGroupedResult:
    """The fused scan on round 1's shape: private tables per contiguous row band,
    sequential merge in worker-index order.

    Right when groups are FEW: each worker's table is small, and the merge —
    O(workers x groups), `merge_from` per stripe entry with the Chan m2 combine —
    is trivial. Order survives by round 1's argument verbatim: bands are
    contiguous and merged in band order, so first-band-containing-a-group is
    first-appearance. Wrong when groups are MANY; that is `group_by_many_radix`.
    """
    if not _many_request_ok(value_columns, opcodes):
        return _empty_many()
    var width = len(key_columns)
    if width == 0:
        return _group_many_width0(batch, value_columns, opcodes)
    var n_aggs = len(value_columns)
    var n_rows = batch.n_rows
    var workers = n_workers
    if workers < 1:
        workers = 1
    if workers > n_rows:
        workers = n_rows
    if workers <= 1:
        return _group_many_serial(batch, key_columns, value_columns, opcodes)

    var key_cols = List[Float64Array]()
    for i in range(width):
        key_cols.append(batch.column(key_columns[i]))
    var value_cols = List[Float64Array]()
    for j in range(n_aggs):
        value_cols.append(batch.column(value_columns[j]))

    var band = (n_rows + workers - 1) // workers
    var w_tuples = List[List[Float64]](capacity=workers)
    var w_stripes = List[List[GroupAccumulator]](capacity=workers)
    var w_nulls = List[Int](capacity=workers)
    for _ in range(workers):
        w_tuples.append(List[Float64]())
        w_stripes.append(List[GroupAccumulator]())
        w_nulls.append(0)
    var tp = w_tuples.unsafe_ptr()
    var sp = w_stripes.unsafe_ptr()
    var np = w_nulls.unsafe_ptr()

    @parameter
    fn band_worker(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n_rows:
            hi = n_rows
        var nulls = 0
        var group_count = 0
        if width == 1:
            var index = HashIndex(64)
            for r in range(lo, hi):
                if not key_cols[0].is_valid_at(r):
                    nulls += 1
                    continue
                var key = key_cols[0].get(r)
                var slot = index.get_or_assign(key, group_count)
                if slot == group_count:
                    group_count += 1
                    tp[w].append(key)
                    for _ in range(n_aggs):
                        sp[w].append(GroupAccumulator(key))
                for j in range(n_aggs):
                    if value_cols[j].is_valid_at(r):
                        sp[w][slot * n_aggs + j].observe(value_cols[j].get(r))
        else:
            var index = CompositeKeyIndex(width, 64)
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
                var slot = index.get_or_assign(key, group_count)
                if slot == group_count:
                    group_count += 1
                    for c in range(width):
                        tp[w].append(key[c])
                    for _ in range(n_aggs):
                        sp[w].append(GroupAccumulator(key[0]))
                for j in range(n_aggs):
                    if value_cols[j].is_valid_at(r):
                        sp[w][slot * n_aggs + j].observe(value_cols[j].get(r))
        np[w] = nulls

    parallelize[band_worker](workers)

    # Sequential merge in worker-index order — round 1's order argument verbatim.
    var key_tuples = List[Float64]()
    var stripes = List[GroupAccumulator]()
    var h_merged = HashIndex(64)
    var c_merged = CompositeKeyIndex(width, 64)
    var null_key_rows = 0
    var group_count = 0
    var key = List[Float64](capacity=width)
    for _ in range(width):
        key.append(0.0)
    for w in range(workers):
        null_key_rows += w_nulls[w]
        var local_groups = len(w_tuples[w]) // width
        for g in range(local_groups):
            for c in range(width):
                key[c] = w_tuples[w][g * width + c]
            var slot = (
                h_merged.get_or_assign(key[0], group_count) if width == 1
                else c_merged.get_or_assign(key, group_count)
            )
            if slot == group_count:
                group_count += 1
                for c in range(width):
                    key_tuples.append(key[c])
                for _ in range(n_aggs):
                    stripes.append(GroupAccumulator(key[0]))
            for j in range(n_aggs):
                stripes[slot * n_aggs + j].merge_from(w_stripes[w][g * n_aggs + j])

    return _finish_many(key_tuples, width, stripes, n_aggs, opcodes, null_key_rows)


fn group_by_many_radix(
    batch: RecordBatch,
    key_columns: List[Int],
    value_columns: List[Int],
    opcodes: List[Int],
    n_workers: Int,
) -> ManyGroupedResult:
    """The fused scan radix-partitioned: hash once, scatter, build partitions
    independently, restore first-appearance order by first-row index.

    Design (b) of the two viable shapes — scatter over two-pass ownership —
    because its memory traffic is CONSTANT in the worker count: pass 1 reads
    the batch once and writes each surviving row once into a worker-private
    bucket per partition; pass 2 reads the buckets once. The two-pass
    alternative re-reads the batch (or a materialised hash array) once PER
    WORKER — W x traffic at exactly the row counts where this path is chosen.
    Scatter also gets the order argument for free, see below.

    What each pass does:

      pass 1 (parallel over `workers` contiguous bands): per surviving row,
        gather the key ONCE into the reused buffer, `hash_composite` it ONCE —
        the same hash every table here probes with, exported from
        `columnar.hash_index` precisely so routing and probing cannot diverge —
        route by the top `RADIX_BITS` bits, and append (keys, values, global
        row index, value-validity bitmask) to bucket[w][p]. No worker touches
        another's buckets.

      pass 2 (parallel over `RADIX_PARTITIONS`): partition p's table is built
        by ONE task from buckets [0][p], [1][p], ... in band order. Bands are
        contiguous ascending row ranges and each bucket preserves scan order,
        so that concatenation is ascending GLOBAL row order — every group's
        accumulator folds its rows in exactly the serial path's order (results
        are bit-identical to 1 worker, no merge tolerance anywhere), each
        group's recorded first row IS its global first appearance, and each
        partition's group list ascends in that index.

      order restore (sequential): P cursors, repeatedly emit the partition
        whose head has the smallest first-row index — a P-way merge of sorted
        lists, O(groups x partitions) on GROUPS, never rows. The result is
        global first-appearance order, exactly; the suite asserts it against
        the serial path element by element, which is what makes this shippable.
    """
    if not _many_request_ok(value_columns, opcodes):
        return _empty_many()
    var width = len(key_columns)
    if width == 0:
        return _group_many_width0(batch, value_columns, opcodes)
    var n_aggs = len(value_columns)
    var n_rows = batch.n_rows
    var workers = n_workers
    if workers < 1:
        workers = 1
    if workers > n_rows:
        workers = n_rows
    if workers <= 1:
        return _group_many_serial(batch, key_columns, value_columns, opcodes)

    var key_cols = List[Float64Array]()
    for i in range(width):
        key_cols.append(batch.column(key_columns[i]))
    var value_cols = List[Float64Array]()
    for j in range(n_aggs):
        value_cols.append(batch.column(value_columns[j]))

    var band = (n_rows + workers - 1) // workers
    var row_floats = width + n_aggs

    # ── pass 1: scatter into worker-owned partition buckets ───────────────────
    # bucket (w, p) lives at w * RADIX_PARTITIONS + p. Floats carry the row's
    # keys then values (0.0 where the value is null — never read, the bitmask
    # says so); meta carries (global row index, validity bitmask) pairs.
    var expect = band // RADIX_PARTITIONS + band // (RADIX_PARTITIONS * 4) + 16
    var b_floats = List[List[Float64]](capacity=workers * RADIX_PARTITIONS)
    var b_meta = List[List[Int]](capacity=workers * RADIX_PARTITIONS)
    var w_nulls = List[Int](capacity=workers)
    for _ in range(workers * RADIX_PARTITIONS):
        b_floats.append(List[Float64](capacity=expect * row_floats))
        b_meta.append(List[Int](capacity=expect * 2))
    for _ in range(workers):
        w_nulls.append(0)
    var fp = b_floats.unsafe_ptr()
    var mp = b_meta.unsafe_ptr()
    var np = w_nulls.unsafe_ptr()

    @parameter
    fn scatter_worker(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n_rows:
            hi = n_rows
        var key = List[Float64](capacity=width)
        for _ in range(width):
            key.append(0.0)
        var nulls = 0
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
            var h = hash_composite(key, width)
            var b = w * RADIX_PARTITIONS + Int(h >> (64 - RADIX_BITS))
            for c in range(width):
                fp[b].append(key[c])
            var vmask = 0
            for j in range(n_aggs):
                if value_cols[j].is_valid_at(r):
                    vmask = vmask | (1 << j)
                    fp[b].append(value_cols[j].get(r))
                else:
                    fp[b].append(0.0)
            mp[b].append(r)
            mp[b].append(vmask)
        np[w] = nulls

    parallelize[scatter_worker](workers)

    # ── pass 2: one task per partition, buckets concatenated in band order ─────
    var p_tuples = List[List[Float64]](capacity=RADIX_PARTITIONS)
    var p_stripes = List[List[GroupAccumulator]](capacity=RADIX_PARTITIONS)
    var p_first = List[List[Int]](capacity=RADIX_PARTITIONS)
    for _ in range(RADIX_PARTITIONS):
        p_tuples.append(List[Float64]())
        p_stripes.append(List[GroupAccumulator]())
        p_first.append(List[Int]())
    var ptp = p_tuples.unsafe_ptr()
    var psp = p_stripes.unsafe_ptr()
    var pfp = p_first.unsafe_ptr()

    @parameter
    fn partition_worker(p: Int):
        var group_count = 0
        if width == 1:
            var index = HashIndex(64)
            for w in range(workers):
                var b = w * RADIX_PARTITIONS + p
                var bucket_rows = len(mp[b]) // 2
                for i in range(bucket_rows):
                    var base = i * row_floats
                    var key = fp[b][base]
                    var slot = index.get_or_assign(key, group_count)
                    if slot == group_count:
                        group_count += 1
                        ptp[p].append(key)
                        for _ in range(n_aggs):
                            psp[p].append(GroupAccumulator(key))
                        pfp[p].append(mp[b][2 * i])
                    var vmask = mp[b][2 * i + 1]
                    for j in range(n_aggs):
                        if ((vmask >> j) & 1) == 1:
                            psp[p][slot * n_aggs + j].observe(fp[b][base + 1 + j])
        else:
            var index = CompositeKeyIndex(width, 64)
            var key = List[Float64](capacity=width)
            for _ in range(width):
                key.append(0.0)
            for w in range(workers):
                var b = w * RADIX_PARTITIONS + p
                var bucket_rows = len(mp[b]) // 2
                for i in range(bucket_rows):
                    var base = i * row_floats
                    for c in range(width):
                        key[c] = fp[b][base + c]
                    var slot = index.get_or_assign(key, group_count)
                    if slot == group_count:
                        group_count += 1
                        for c in range(width):
                            ptp[p].append(key[c])
                        for _ in range(n_aggs):
                            psp[p].append(GroupAccumulator(key[0]))
                        pfp[p].append(mp[b][2 * i])
                    var vmask = mp[b][2 * i + 1]
                    for j in range(n_aggs):
                        if ((vmask >> j) & 1) == 1:
                            psp[p][slot * n_aggs + j].observe(fp[b][base + width + j])

    parallelize[partition_worker](RADIX_PARTITIONS)

    # ── order restore: P-way merge on ascending first-row lists ────────────────
    var null_key_rows = 0
    for w in range(workers):
        null_key_rows += w_nulls[w]
    var total_groups = 0
    for p in range(RADIX_PARTITIONS):
        total_groups += len(p_first[p])

    var cursors = List[Int](capacity=RADIX_PARTITIONS)
    for _ in range(RADIX_PARTITIONS):
        cursors.append(0)
    var key_tuples = List[Float64](capacity=total_groups * width)
    var stripes = List[GroupAccumulator](capacity=total_groups * n_aggs)
    for _ in range(total_groups):
        var best_p = -1
        var best_row = n_rows  # every recorded first row is < n_rows
        for p in range(RADIX_PARTITIONS):
            if cursors[p] < len(p_first[p]) and p_first[p][cursors[p]] < best_row:
                best_p = p
                best_row = p_first[p][cursors[p]]
        if best_p < 0:
            break  # unreachable: total_groups is the sum of the list lengths
        var g = cursors[best_p]
        cursors[best_p] = g + 1
        for c in range(width):
            key_tuples.append(p_tuples[best_p][g * width + c])
        for j in range(n_aggs):
            stripes.append(p_stripes[best_p][g * n_aggs + j].copy())

    return _finish_many(key_tuples, width, stripes, n_aggs, opcodes, null_key_rows)


# ═══════════════════════════════════════════════════════════════════════════════
# Code-indexed grouping — no hash table when the key is already a small code
# ═══════════════════════════════════════════════════════════════════════════════


fn group_by_coded(
    batch: RecordBatch,
    key_column: Int,
    cardinality: Int,
    value_columns: List[Int],
    opcodes: List[Int],
) -> CodedGroupedResult:
    """Fused grouping for a key column of dictionary CODES: the accumulator
    array is indexed by the code itself, no hash, no probe.

    For whom: a column `columnar.dictionary` encoded (codes are dense from 0 in
    first-appearance order; `cardinality` = `n_distinct`, read from the
    dictionary), or any integer-coded column whose ceiling the caller knows.
    On such data this returns EXACTLY what `group_by_many` returns — same
    groups, same first-appearance order, same values — it is only faster.

    The guard is the point: every PRESENT key must be an integral value in
    [0, cardinality). The range check runs in FLOAT domain first — NaN and
    negatives fail `k >= 0.0`, +inf and oversized fail `k < cardinality` — so
    `Int(k)` is only reached where it is total (`fptosi` outside range is
    undefined, not clamped; same discipline as `arrow_wire.packed_floats_to_bytes`).
    A violation is a TYPED REFUSAL (`GROUP_CODED_KEY_NOT_A_CODE`, empty result):
    indexing the array with a bad code would be an out-of-bounds write, which
    is an uncatchable abort that kills the worker process and every resident
    dataset with it. A null key is not a violation — it is exclusion, tallied,
    exactly as on the hash paths.
    """
    return group_by_coded_parallel(
        batch,
        key_column,
        cardinality,
        value_columns,
        opcodes,
        planned_workers(batch.n_rows, info.num_physical_cores()),
    )


fn group_by_coded_parallel(
    batch: RecordBatch,
    key_column: Int,
    cardinality: Int,
    value_columns: List[Int],
    opcodes: List[Int],
    n_workers: Int,
) -> CodedGroupedResult:
    """`group_by_coded` on an explicit worker count. 1 is exactly the serial path.

    Parallel shape: round 1's contiguous bands, but the per-worker state is a
    DENSE stripe array indexed by code plus a band-local first-appearance list.
    The merge is `merge_from` per (code, aggregate) in worker-index order — the
    same association as `group_by_parallel`'s band merge over identical bands,
    which is why the suite can assert bit-equality against it — and the order
    merge walks workers' local lists in band order, round 1's argument again.
    """
    if cardinality <= 0 or cardinality > MAX_CODED_CARDINALITY:
        return CodedGroupedResult(GROUP_CODED_CARDINALITY_INVALID, _empty_many())
    if not _many_request_ok(value_columns, opcodes):
        return CodedGroupedResult(GROUP_CODED_BAD_REQUEST, _empty_many())

    var n_aggs = len(value_columns)
    var n_rows = batch.n_rows
    var key_col = batch.column(key_column)
    var value_cols = List[Float64Array]()
    for j in range(n_aggs):
        value_cols.append(batch.column(value_columns[j]))
    var bound = Float64(cardinality)

    var workers = n_workers
    if workers < 1:
        workers = 1
    if workers > n_rows:
        workers = n_rows

    if workers <= 1:
        var stripes = List[GroupAccumulator](capacity=cardinality * n_aggs)
        for _ in range(cardinality * n_aggs):
            stripes.append(GroupAccumulator(0.0))
        var seen = List[Bool](capacity=cardinality)
        for _ in range(cardinality):
            seen.append(False)
        var order = List[Int]()
        var null_key_rows = 0
        for r in range(n_rows):
            if not key_col.is_valid_at(r):
                null_key_rows += 1
                continue
            var k = key_col.get(r)
            if not (k >= 0.0) or k >= bound:
                return CodedGroupedResult(GROUP_CODED_KEY_NOT_A_CODE, _empty_many())
            var code = Int(k)
            if Float64(code) != k:
                return CodedGroupedResult(GROUP_CODED_KEY_NOT_A_CODE, _empty_many())
            if not seen[code]:
                seen[code] = True
                order.append(code)
            for j in range(n_aggs):
                if value_cols[j].is_valid_at(r):
                    stripes[code * n_aggs + j].observe(value_cols[j].get(r))
        # Emit in first-appearance order — NOT code order. Codes from
        # `columnar.dictionary` happen to be assigned in first-appearance order
        # of the encoding pass, but this batch may be a filtered or reordered
        # view of that pass, and the module's promise is about THIS batch.
        var key_tuples = List[Float64](capacity=len(order))
        var out_stripes = List[GroupAccumulator](capacity=len(order) * n_aggs)
        for i in range(len(order)):
            var code = order[i]
            key_tuples.append(Float64(code))
            for j in range(n_aggs):
                out_stripes.append(stripes[code * n_aggs + j].copy())
        return CodedGroupedResult(
            GROUP_CODED_OK,
            _finish_many(key_tuples, 1, out_stripes, n_aggs, opcodes, null_key_rows),
        )

    # ── parallel: dense private arrays per band, merge in worker-index order ──
    var band = (n_rows + workers - 1) // workers
    var w_stripes = List[List[GroupAccumulator]](capacity=workers)
    var w_seen = List[List[Bool]](capacity=workers)
    var w_order = List[List[Int]](capacity=workers)
    var w_nulls = List[Int](capacity=workers)
    var w_bad = List[Bool](capacity=workers)
    for _ in range(workers):
        var stripes_w = List[GroupAccumulator](capacity=cardinality * n_aggs)
        for _ in range(cardinality * n_aggs):
            stripes_w.append(GroupAccumulator(0.0))
        w_stripes.append(stripes_w^)
        var seen_w = List[Bool](capacity=cardinality)
        for _ in range(cardinality):
            seen_w.append(False)
        w_seen.append(seen_w^)
        w_order.append(List[Int]())
        w_nulls.append(0)
        w_bad.append(False)
    var sp = w_stripes.unsafe_ptr()
    var ep = w_seen.unsafe_ptr()
    var op = w_order.unsafe_ptr()
    var np = w_nulls.unsafe_ptr()
    var bp = w_bad.unsafe_ptr()

    @parameter
    fn coded_worker(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n_rows:
            hi = n_rows
        var nulls = 0
        for r in range(lo, hi):
            if not key_col.is_valid_at(r):
                nulls += 1
                continue
            var k = key_col.get(r)
            if not (k >= 0.0) or k >= bound:
                bp[w] = True
                break  # the whole call refuses; nothing this band saw survives
            var code = Int(k)
            if Float64(code) != k:
                bp[w] = True
                break
            if not ep[w][code]:
                ep[w][code] = True
                op[w].append(code)
            for j in range(n_aggs):
                if value_cols[j].is_valid_at(r):
                    sp[w][code * n_aggs + j].observe(value_cols[j].get(r))
        np[w] = nulls

    parallelize[coded_worker](workers)

    for w in range(workers):
        if w_bad[w]:
            return CodedGroupedResult(GROUP_CODED_KEY_NOT_A_CODE, _empty_many())

    # Global first-appearance order: walk workers in band order, appending each
    # code the first time any band's local (already first-appearance) list
    # yields it — the same composition round 1's merge uses for its keys.
    var g_seen = List[Bool](capacity=cardinality)
    for _ in range(cardinality):
        g_seen.append(False)
    var g_order = List[Int]()
    var null_key_rows = 0
    for w in range(workers):
        null_key_rows += w_nulls[w]
        for i in range(len(w_order[w])):
            var code = w_order[w][i]
            if not g_seen[code]:
                g_seen[code] = True
                g_order.append(code)

    var key_tuples = List[Float64](capacity=len(g_order))
    var out_stripes = List[GroupAccumulator](capacity=len(g_order) * n_aggs)
    for i in range(len(g_order)):
        var code = g_order[i]
        key_tuples.append(Float64(code))
        for j in range(n_aggs):
            var acc = GroupAccumulator(Float64(code))
            for w in range(workers):
                if w_seen[w][code]:
                    acc.merge_from(w_stripes[w][code * n_aggs + j])
            out_stripes.append(acc^)
    return CodedGroupedResult(
        GROUP_CODED_OK,
        _finish_many(key_tuples, 1, out_stripes, n_aggs, opcodes, null_key_rows),
    )
