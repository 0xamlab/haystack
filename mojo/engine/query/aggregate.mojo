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

Opcode-specialized updates, counted scatter, batched hashing (2026-08, round 3)
-------------------------------------------------------------------------------
Round 2's measured residuals against polars/duckdb had three named causes; each
gets one mechanism, and none of them changes what any entry point RETURNS —
that is the round's contract, pinned by the suites:

  * `observe()` maintains count/sum/mean/m2/min/max whatever the caller asked
    for. `observe_op` dispatches to a per-opcode update that touches only the
    fields that opcode's `value_for`/`has_answer` read — same frozen
    `group_*_update` primitives, same call sequence for the fields kept, so a
    specialized accumulator's answer is BIT-EQUAL to the full one's for its
    opcode (mean included: it keeps the Welford recurrence, not sum/count).
    VAR/STD need everything and keep the full `observe`.
  * The radix scatter appended each surviving row into a per-(worker,
    partition) List — an amortized-growth store plus bounds logic per element,
    the dominant cost at 1e7 rows. Now: pass A hashes each key once (hash
    kept in a row-indexed buffer) and COUNTS rows per (worker, partition);
    a serial prefix sum turns counts into segment offsets over ONE
    preallocated payload buffer; pass B re-walks the band and writes each
    row's payload at its cursor with raw stores. Safety argument for the raw
    stores: cursor(w,p) starts at offset(w,p) and is bumped once per counted
    row, so every write index is < offset(w,p) + count(w,p) <= survivors by
    the prefix-sum construction; the final cursors are CHECKED against the
    counts after the pass, and a mismatch falls back to the independent
    banded engine (loudly) rather than trusting a broken scatter. Partition
    segments hold workers' rows in band order, each ascending, so fold order
    is still ascending global row order — the bit-equal-to-serial promise and
    the first-appearance order restore are unchanged.
  * Key hashing ran one FNV fold per row inside the probe call. The scan
    fast path (no nulls in any key column) now hashes `HASH_BLOCK` rows into
    a preallocated buffer in a tight loop — independent chains the CPU can
    overlap, no per-row method dispatch — then probes with
    `get_or_assign_bits`/`get_or_assign_hashed`, which take the precomputed
    hash instead of re-deriving it. Key columns WITH nulls keep the exact
    per-row path; both paths are pinned to the same references.

Routing (`plan_many_route`) now covers all four engines: a single key column
whose probed window holds only integral codes in [0, MAX_CODED_CARDINALITY)
routes CODED and falls back to the hash engines if rows beyond the window
refuse (correct, one wasted partial pass, and only reachable on data whose
probe window lied); otherwise the cardinality probe picks BANDED or RADIX as
in round 2. The route is a public, testable function so a routing mistake is
a failing table entry, and the H2O bench gates round 3 against the best of
rounds 1 and 2 per question — a routing regression cannot ship silently.

`group_by_int64` — grouping without the Float64 detour (2026-08, round 4, int64-columnar-fidelity)
----------------------------------------------------------------------------------------------------
Every entry point above groups on `Float64Array`, because `columnar.batch.RecordBatch`
is Float64-only by design (see its own header). That is fine for a genuinely Float64
key. It is silently wrong for a caller holding a real Int64 key column
(`columnar.array.Int64Array`) above 2^53: two distinct Int64 values there can share one
double (`9007199254740992` and `9007199254740993` both round to the same bit pattern),
so `group_by(batch, ...)` on a key column that was widened to Float64 upstream merges
them into one group — `test_query_aggregate.mojo` proves the merge (count and sum both
silently double) through this exact path, on the value that pair actually collides at.

`group_by_int64` is the fix, not a rewrite of `group_by`: it takes the key as an
`Int64Array` and never widens it. Grouping runs through
`columnar.hash_index.Int64HashIndex` — `Int -> Int`, no Float64 anywhere — so two
distinct Int64 keys stay two groups at every magnitude the type can hold. Value-side
accumulation is unchanged: the same frozen `pandas_groupby` primitives via
`GroupAccumulator.observe`, and the same null policy `group_by` already has (a null key
excludes its row and is counted in `null_key_rows`; a null value joins its group's row
count but moves no accumulator). Serial only, matching where `group_by` itself started —
parallelizing this path is a possible follow-up, not a correctness requirement.
"""
from std.algorithm import parallelize
from std.memory import alloc, bitcast
from std.sys import info

from columnar.array import Float64Array, Int64Array, float64_with_nulls
from columnar.batch import RecordBatch
from columnar.hash_index import (
    CANONICAL_NAN_BITS,
    CompositeKeyIndex,
    FNV_OFFSET_BASIS,
    HashIndex,
    Int64HashIndex,
    fnv_fold,
    hash_bits,
    hash_composite,
    normalize_bits,
)
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

    # ── opcode-specialized updates (round 3) ──────────────────────────────────
    # Each maintains EXACTLY the fields its opcode's `value_for`/`has_answer`
    # read (plus `count`, which every result reports), with the same frozen
    # primitive in the same sequence `observe` runs — so per opcode the answer
    # is bit-equal to the full update's, and `merge_from` still composes: the
    # fields an opcode never reads stay 0.0/False on both sides of a merge,
    # and the fields it does read are maintained identically. The suite pins
    # this field-for-field per opcode, on random and adversarial data.

    @always_inline
    fn observe_count(mut self):
        self.count = group_count_update(self.count)

    @always_inline
    fn observe_sum(mut self, value: Float64):
        self.count = group_count_update(self.count)
        self.total = group_sum_update(self.total, value)

    @always_inline
    fn observe_mean(mut self, value: Float64):
        # The Welford recurrence, NOT sum-then-divide: bit-equal to `observe`'s
        # mean, which is what lets the fused paths specialize without moving
        # any answer by even an ulp.
        self.count = group_count_update(self.count)
        self.mean = group_mean_update(self.mean, value, self.count)

    @always_inline
    fn observe_min(mut self, value: Float64):
        self.count = group_count_update(self.count)
        # Same NaN policy as `observe`, or the #459 defect returns through this
        # path: a NaN contributes to NO extremum, because seeding or comparing
        # with one makes min/max depend on where the NaN sits in the scan order,
        # which no parallel merge can reproduce.
        if value != value:
            return
        if not self.seen:
            self.minimum = value
            self.seen = True
        else:
            self.minimum = group_min_update(self.minimum, value)

    @always_inline
    fn observe_max(mut self, value: Float64):
        self.count = group_count_update(self.count)
        # Same NaN policy as `observe` — see `observe_min`.
        if value != value:
            return
        if not self.seen:
            self.maximum = value
            self.seen = True
        else:
            self.maximum = group_max_update(self.maximum, value)

    @always_inline
    fn observe_op(mut self, opcode: Int, value: Float64):
        """`observe`, but paying only for what `opcode` will read.

        VAR/STD — and any opcode this dispatch does not recognise — fall
        through to the full `observe`: correctness never depends on the
        specialization list being complete.
        """
        if opcode == AGG_SUM:
            self.observe_sum(value)
        elif opcode == AGG_AVG:
            self.observe_mean(value)
        elif opcode == AGG_MIN:
            self.observe_min(value)
        elif opcode == AGG_MAX:
            self.observe_max(value)
        elif opcode == AGG_COUNT:
            self.observe_count()
        else:
            self.observe(value)

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


struct IntGroupedResult(Copyable, Movable):
    """`GroupedResult`'s Int64-key analog: groups keyed by an EXACT Int, never a
    Float64 bit pattern.

    Exists because `GroupedResult.keys: List[Float64]` is precisely the coercion
    `group_by_int64` exists to avoid — a second `keys` type would defeat the whole
    point if this struct reused it. Everything else (`values`/`present`/`counts`,
    aligned by index; `opcode`; `null_key_rows`) mirrors `GroupedResult` exactly.
    """

    var keys: List[Int]
    var values: List[Float64]
    var present: List[Bool]
    var counts: List[Float64]
    var opcode: Int
    var null_key_rows: Int

    fn __init__(
        out self,
        var keys: List[Int],
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
            + " int64-keyed groups"
            + (
                " (" + String(self.null_key_rows) + " rows had a null key)"
                if self.null_key_rows > 0
                else ""
            )
        )


fn find_group_int64(keys: List[Int], key: Int) -> Int:
    """Linear scan for an exact Int key — `find_group`'s Int64 analog.

    Same role as `find_group`: a small-cardinality fast path, and what the tests use
    to locate a group without depending on insertion order. No precision concern here
    either way (`Int` equality is exact), so this exists for parallel structure with
    the Float64 path, not because it is fixing anything of its own.
    """
    for i in range(len(keys)):
        if keys[i] == key:
            return i
    return -1


fn _finish_groups_int64(
    keys: List[Int],
    accumulators: List[GroupAccumulator],
    opcode: Int,
    null_key_rows: Int,
) -> IntGroupedResult:
    """`_finish_groups`'s Int64-key analog — identical extraction, Int keys untouched."""
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
    return IntGroupedResult(out_keys^, values^, present^, counts^, opcode, null_key_rows)


fn group_by_int64(keys: Int64Array, values: Float64Array, opcode: Int) -> IntGroupedResult:
    """Aggregate `values` grouped by `keys`, with the key held as an exact Int64 the
    whole way through — never widened to Float64. See the module header
    ("`group_by_int64` — grouping without the Float64 detour") for why `group_by`
    itself cannot be used for this: its key column is a `Float64Array`, and getting an
    Int64 id into one already lost the distinction this function exists to keep.

    `keys` and `values` are not required to share one `RecordBatch` (there is no
    Int64-carrying batch type to share — see `columnar.batch`'s header), so neither
    array's length is trusted over the other: rows run over `[0, n)` where
    `n = min(keys.length, values.length)`, the same "derive the bound from what is
    actually there" rule the frozen-kernel-package rules require for any dimension
    that is not itself the caller's to assert. A caller that built both columns from
    one already-consistent source gets `n = keys.length` for free.

    Null policy matches `group_by` exactly: a null key excludes its row from every
    group and is tallied in `null_key_rows`; a null value still joins its group (its
    row is counted) but moves no accumulator.
    """
    var n = keys.length
    if values.length < n:
        n = values.length

    var out_keys = List[Int]()
    var accumulators = List[GroupAccumulator]()
    var index = Int64HashIndex(64)
    var null_key_rows = 0

    for r in range(n):
        if not keys.is_valid_at(r):
            null_key_rows += 1
            continue
        var key = keys.get(r)
        var next_slot = len(out_keys)
        var slot = index.get_or_assign(key, next_slot)
        if slot == next_slot:
            # A newly assigned slot; the accumulator array grows with it. `0.0` is a
            # placeholder for `GroupAccumulator.key`, which nothing in this module
            # reads back (see `GroupAccumulator.__init__` — the field is write-only
            # today); the group's real, exact key lives in `out_keys`, not here.
            out_keys.append(key)
            accumulators.append(GroupAccumulator(0.0))
        if values.is_valid_at(r):
            accumulators[slot].observe(values.get(r))

    return _finish_groups_int64(out_keys, accumulators, opcode, null_key_rows)


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

comptime RADIX_MIN_GROUPS: Int = 16384
"""PROBED distinct-key count at which `group_by_many_parallel` switches from
the band-merge path to the radix path.

Round 2 measured this crossover at 32768; round 3's counted scatter removed
the radix path's per-element append cost, which moved it DOWN. Re-measured on
this host (16 physical cores, 1e7 rows, 2 aggregates, load ~8.5; sweep in
bench_groupby_fused.mojo plus a 2k-12k fill-in). `probed` is what the probe
reports over its 64k window for that true cardinality — the number this
threshold actually sees:

    true groups   probed   banded    radix     radix advantage
         1 000     1 000   0.022s    0.029s    0.77x
         2 000     2 000   0.040s    0.053s    0.75x
         4 000     4 000   0.044s    0.055s    0.80x
         6 000     6 000   0.057s    0.052s    1.08x
         8 000     7 997   0.066s    0.056s    1.18x
        10 000     9 986   0.039s    0.032s    1.20x  (0.83x on a later run)
        12 000    11 948   0.060s    0.062s    0.97x
        32 768    28 352   0.059s    0.044s    1.34x
       100 000    48 154   0.137s    0.044s    3.14x

Below ~4k probed banded wins clearly. From ~6k to ~12k the two are a
COIN FLIP under load — the same 10k-group shape measured 1.20x radix-favor
in one session and 0.83x in the next, which the H2O q2 routing gate caught
when the threshold briefly sat at 8192. A dispatcher must not gamble: the
threshold sits at the first power of two ABOVE the measured coin-flip zone,
where the radix lean is consistent across runs and grows with cardinality
(1.34x at 28k probed, 3.1x at 48k). The H2O bench gates the routed time
against both explicit engines per question, so a mistuned threshold fails a
gate instead of shipping."""

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

comptime HASH_BLOCK: Int = 1024
"""Rows hashed per block on the no-null-keys scan fast path.

The FNV fold is a serial chain of ~8 dependent ops per element; hashed one row
at a time inside the probe call, each chain's latency is exposed. Hashing a
block into a preallocated buffer makes consecutive rows' chains independent —
the CPU overlaps them — and the buffer is 8 KiB (16 KiB with the width-1 bits
buffer), L1-resident. 1024 is comfortably past where the loop overhead
amortizes; the win is flat from ~256 up, so the exact value is not sensitive."""

# ── group_by_many routing (round 3): one testable table, four engines ────────
comptime ROUTE_SERIAL: Int = 0
comptime ROUTE_CODED: Int = 1
comptime ROUTE_BANDED: Int = 2
comptime ROUTE_RADIX: Int = 3


struct ManyRoutePlan(Copyable, Movable):
    """Where `group_by_many_parallel` will send a request, decided up front.

    `route` is one of the ROUTE_* codes; `coded_bound` carries the dense-array
    cardinality the CODED route needs (max probed code + 1) and is 0 on every
    other route. A struct rather than a bare Int so the entry point runs the
    probes ONCE and the suite can assert the whole decision, not just its
    first coordinate.
    """

    var route: Int
    var coded_bound: Int

    fn __init__(out self, route: Int, coded_bound: Int):
        self.route = route
        self.coded_bound = coded_bound

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


fn probe_at_least(
    batch: RecordBatch, key_columns: List[Int], probe_rows: Int, threshold: Int
) -> Bool:
    """Whether the probe window holds at least `threshold` distinct keys —
    `probe_cardinality(...) >= threshold`, with an early exit at the answer.

    The routing probe on a high-cardinality batch reaches the radix threshold
    within the first few thousand rows; scanning the rest of the 64k window
    would hash-insert tens of thousands more keys for a decision already
    made — a measurable tax on exactly the questions the radix engine wins
    (the H2O routing gate caught it at ~6% of q3/q5). Low-cardinality windows
    scan fully and answer False, exactly as the full count would. The table
    is preallocated past the threshold so the early-exit path never pays a
    resize.
    """
    if threshold <= 0:
        return True
    var width = len(key_columns)
    if width == 0:
        return 1 >= threshold
    var n = batch.n_rows
    if probe_rows < n:
        n = probe_rows
    if n <= 0:
        return False
    var capacity = threshold * 2
    if width == 1:
        var key_col = batch.column(key_columns[0])
        var index = HashIndex(capacity)
        for r in range(n):
            if not key_col.is_valid_at(r):
                continue
            _ = index.get_or_assign(key_col.get(r), index.size())
            if index.size() >= threshold:
                return True
        return False
    var key_cols = List[Float64Array]()
    for i in range(width):
        key_cols.append(batch.column(key_columns[i]))
    var index = CompositeKeyIndex(width, capacity)
    var key = List[Float64](length=width, fill=0.0)
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
        if index.size() >= threshold:
            return True
    return False


fn probe_coded_bound(batch: RecordBatch, key_column: Int, probe_rows: Int) -> Int:
    """The `group_by_coded` cardinality this key column supports, judged from
    the first `min(probe_rows, n_rows)` rows: max integral code + 1 when EVERY
    present probed key is an integral float in [0, MAX_CODED_CARDINALITY),
    else -1. A window with no present keys is -1 — no evidence, no route.

    One-sided like `probe_cardinality`, and in the same direction: rows past
    the window can only make the answer MORE conservative at scan time, never
    less — a non-code beyond the window is a typed refusal from the coded
    engine, which `group_by_many_parallel` treats as its fallback signal. A
    lying window therefore costs one partial pass, never a wrong answer.

    Deliberately hash-free (compares and a truncation per row, no table): it
    runs in front of questions the coded engine answers in single-digit
    milliseconds, where `probe_cardinality`'s hash insertions would be a
    measurable tax.
    """
    var key_col = batch.column(key_column)
    var n = batch.n_rows
    if probe_rows < n:
        n = probe_rows
    if n <= 0:
        return -1
    var bound = Float64(MAX_CODED_CARDINALITY)
    var kp = key_col.values[].unsafe_ptr() + key_col.offset
    # A column shorter than the window keeps the per-row check: is_valid_at
    # reads out-of-range as absent, which is what a ragged batch always meant.
    var has_nulls = key_col.null_count() > 0 or key_col.length < n
    var max_code = -1
    for r in range(n):
        if has_nulls and not key_col.is_valid_at(r):
            continue
        var k = kp[r]
        # Float-domain first, exactly as the coded engine itself validates:
        # NaN and negatives fail `k >= 0.0`, +inf and oversized fail the bound,
        # so Int(k) is only reached where fptosi is defined.
        if not (k >= 0.0) or k >= bound:
            return -1
        var code = Int(k)
        if Float64(code) != k:
            return -1
        if code > max_code:
            max_code = code
    if max_code < 0:
        return -1
    return max_code + 1


fn plan_many_route(
    batch: RecordBatch, key_columns: List[Int], n_workers: Int
) -> ManyRoutePlan:
    """The `group_by_many_parallel` routing table, in one testable place.

    SERIAL for width 0 or a worker count that clamps to <= 1. CODED for a
    single key column whose probe window holds only small integral codes
    (`coded_bound` carries the dense-array cardinality). Otherwise round 2's
    cardinality dispatch: RADIX at or above `RADIX_MIN_GROUPS` probed groups,
    BANDED below. The CODED route can still be refused at scan time by a
    non-code beyond the window; the entry point then falls back to BANDED —
    necessarily BANDED, because a window whose every key fit under
    `MAX_CODED_CARDINALITY` probed at most 4096 distinct keys, far below the
    radix threshold.

    Thresholds are measured on the H2O shapes (see `RADIX_MIN_GROUPS` and the
    bench sweep), and the H2O bench gates the routed time against the best
    explicit engine per question — a routing mistake fails the gate rather
    than shipping as a silent regression.
    """
    var workers = n_workers
    if workers > batch.n_rows:
        workers = batch.n_rows
    if workers <= 1 or len(key_columns) == 0:
        return ManyRoutePlan(ROUTE_SERIAL, 0)
    if len(key_columns) == 1:
        var bound = probe_coded_bound(batch, key_columns[0], CARDINALITY_PROBE_ROWS)
        if bound > 0:
            return ManyRoutePlan(ROUTE_CODED, bound)
    if probe_at_least(batch, key_columns, CARDINALITY_PROBE_ROWS, RADIX_MIN_GROUPS):
        return ManyRoutePlan(ROUTE_RADIX, 0)
    return ManyRoutePlan(ROUTE_BANDED, 0)


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
    """`group_by_many` on an explicit worker count, engine chosen by
    `plan_many_route`.

    1 worker is exactly the serial path. Above 1 the routing table picks
    CODED (single small-integral-code key: dense array, no hash), RADIX
    (large key spaces, where the O(workers x groups) merge and full-key-space
    per-worker tables kill 100k-group questions) or BANDED (everything else:
    the merge is trivial and a scatter would be pure overhead). A CODED
    refusal — a non-code beyond the probe window — falls back to BANDED,
    which is correct on any data and costs one partial pass, only on data
    whose window lied. `group_by_many_banded` / `group_by_many_radix` /
    `group_by_coded_parallel` pin each engine directly — that is what the
    suite and the gates use to compare them on identical data.
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
    var plan = plan_many_route(batch, key_columns, workers)
    if plan.route == ROUTE_CODED:
        var coded = group_by_coded_parallel(
            batch, key_columns[0], plan.coded_bound, value_columns, opcodes, workers
        )
        if coded.ok():
            return coded.result.copy()
        # The window lied: a row past it is not a code. Fall back to BANDED —
        # see plan_many_route for why radix is unreachable from here.
        return group_by_many_banded(batch, key_columns, value_columns, opcodes, workers)
    if plan.route == ROUTE_RADIX:
        return group_by_many_radix(batch, key_columns, value_columns, opcodes, workers)
    return group_by_many_banded(batch, key_columns, value_columns, opcodes, workers)


fn _col_guard_flags(cols: List[Float64Array], n_rows: Int) -> List[Bool]:
    """Whether each column needs its per-row validity check, hoisted once.

    True when the column has any null OR is shorter than the scan (`n_rows`
    is authoritative on a RecordBatch, and `is_consistent` is advisory — a
    ragged batch has always read its missing tail as null through
    `is_valid_at`'s bounds check, and must keep doing so). When the flag is
    False, every scanned slot is present AND in range, so a raw
    values-pointer read is exactly `get(r)` — that is the entire license for
    the pointer fast paths below, which is why the flag must fail toward
    True.
    """
    var flags = List[Bool](capacity=len(cols))
    for i in range(len(cols)):
        flags.append(cols[i].null_count() > 0 or cols[i].length < n_rows)
    return flags^


fn _fused_scan_w1(
    key_col: Float64Array,
    value_cols: List[Float64Array],
    opcodes: List[Int],
    key_nulls: Bool,
    value_nulls: List[Bool],
    lo: Int,
    hi: Int,
    mut index: HashIndex,
    mut key_tuples: List[Float64],
    mut stripes: List[GroupAccumulator],
) -> Int:
    """One single-key fused scan over rows [lo, hi) into caller-owned state.
    Returns the null-key rows seen.

    THE shared inner loop (round 3): the serial path scans [0, n) with its one
    table, each band worker scans its own band with its private table — one
    body, so the two cannot diverge, which is what the banded-8 ==
    `group_by_parallel`-8 bit-equality rides on.

    Fast path (`key_nulls == False`): hash `HASH_BLOCK` rows at a time into a
    preallocated buffer — `normalize_bits` + `fnv_fold`, a loop of independent
    chains with no method dispatch — then probe with the precomputed
    (bits, hash) pair via `get_or_assign_bits`. With null keys: round 2's
    per-row loop, unchanged. Values are read through the raw pointer exactly
    where validity is already established (column-level no-nulls, or the
    per-row check passed) — positions where `get(r)` returns the same number.
    Updates go through `observe_op`, the opcode-specialized update.
    """
    var n_aggs = len(value_cols)
    var nulls = 0
    var group_count = len(key_tuples)
    var kp = key_col.values[].unsafe_ptr() + key_col.offset
    var vps = List[UnsafePointer[Float64, origin=MutAnyOrigin]](capacity=n_aggs)
    for j in range(n_aggs):
        vps.append(value_cols[j].values[].unsafe_ptr() + value_cols[j].offset)

    if not key_nulls:
        var hbuf = List[UInt64](length=HASH_BLOCK, fill=0)
        var bbuf = List[UInt64](length=HASH_BLOCK, fill=0)
        var hp = hbuf.unsafe_ptr()
        var bp = bbuf.unsafe_ptr()
        var r = lo
        while r < hi:
            var blk = hi - r
            if blk > HASH_BLOCK:
                blk = HASH_BLOCK
            for i in range(blk):
                var bits = normalize_bits(kp[r + i])
                bp[i] = bits
                hp[i] = fnv_fold(FNV_OFFSET_BASIS, bits)
            for i in range(blk):
                var slot = index.get_or_assign_bits(bp[i], hp[i], group_count)
                if slot == group_count:
                    group_count += 1
                    key_tuples.append(kp[r + i])
                    for _ in range(n_aggs):
                        stripes.append(GroupAccumulator(kp[r + i]))
                var sbase = slot * n_aggs
                for j in range(n_aggs):
                    if not value_nulls[j] or value_cols[j].is_valid_at(r + i):
                        stripes[sbase + j].observe_op(opcodes[j], vps[j][r + i])
            r += blk
        return 0

    for r in range(lo, hi):
        if not key_col.is_valid_at(r):
            nulls += 1
            continue
        var key = kp[r]
        var slot = index.get_or_assign(key, group_count)
        if slot == group_count:
            group_count += 1
            key_tuples.append(key)
            for _ in range(n_aggs):
                stripes.append(GroupAccumulator(key))
        var sbase = slot * n_aggs
        for j in range(n_aggs):
            if not value_nulls[j] or value_cols[j].is_valid_at(r):
                stripes[sbase + j].observe_op(opcodes[j], vps[j][r])
    return nulls


fn _fused_scan_wn(
    key_cols: List[Float64Array],
    value_cols: List[Float64Array],
    opcodes: List[Int],
    key_nulls: Bool,
    value_nulls: List[Bool],
    lo: Int,
    hi: Int,
    mut index: CompositeKeyIndex,
    mut key_tuples: List[Float64],
    mut stripes: List[GroupAccumulator],
) -> Int:
    """`_fused_scan_w1` for a composite key. Returns the null-key rows seen.

    The block loop chains `fnv_fold` over the normalized elements exactly as
    `hash_composite` does — same seed, same order — and probes with
    `get_or_assign_hashed`, so the batched hash and the table's own hash
    cannot disagree (the table's `get_or_assign` delegates to the same probe).
    """
    var width = len(key_cols)
    var n_aggs = len(value_cols)
    var nulls = 0
    var group_count = 0
    if width > 0:
        group_count = len(key_tuples) // width
    var kps = List[UnsafePointer[Float64, origin=MutAnyOrigin]](capacity=width)
    for c in range(width):
        kps.append(key_cols[c].values[].unsafe_ptr() + key_cols[c].offset)
    var vps = List[UnsafePointer[Float64, origin=MutAnyOrigin]](capacity=n_aggs)
    for j in range(n_aggs):
        vps.append(value_cols[j].values[].unsafe_ptr() + value_cols[j].offset)
    # One key buffer per scan, overwritten per row — round 1's allocation fix.
    var key = List[Float64](length=width, fill=0.0)
    var kb = key.unsafe_ptr()

    if not key_nulls:
        var hbuf = List[UInt64](length=HASH_BLOCK, fill=0)
        var hp = hbuf.unsafe_ptr()
        var r = lo
        while r < hi:
            var blk = hi - r
            if blk > HASH_BLOCK:
                blk = HASH_BLOCK
            for i in range(blk):
                var h = FNV_OFFSET_BASIS
                for c in range(width):
                    h = fnv_fold(h, normalize_bits(kps[c][r + i]))
                hp[i] = h
            for i in range(blk):
                for c in range(width):
                    kb[c] = kps[c][r + i]
                var slot = index.get_or_assign_hashed(key, hp[i], group_count)
                if slot == group_count:
                    group_count += 1
                    for c in range(width):
                        key_tuples.append(kb[c])
                    for _ in range(n_aggs):
                        stripes.append(GroupAccumulator(kb[0]))
                var sbase = slot * n_aggs
                for j in range(n_aggs):
                    if not value_nulls[j] or value_cols[j].is_valid_at(r + i):
                        stripes[sbase + j].observe_op(opcodes[j], vps[j][r + i])
            r += blk
        return 0

    for r in range(lo, hi):
        var any_null = False
        for c in range(width):
            if not key_cols[c].is_valid_at(r):
                any_null = True
                break
            kb[c] = kps[c][r]
        if any_null:
            nulls += 1
            continue
        var slot = index.get_or_assign(key, group_count)
        if slot == group_count:
            group_count += 1
            for c in range(width):
                key_tuples.append(kb[c])
            for _ in range(n_aggs):
                stripes.append(GroupAccumulator(kb[0]))
        var sbase = slot * n_aggs
        for j in range(n_aggs):
            if not value_nulls[j] or value_cols[j].is_valid_at(r):
                stripes[sbase + j].observe_op(opcodes[j], vps[j][r])
    return nulls


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
    per opcode. Since round 3 the body is `_fused_scan_w1`/`_fused_scan_wn`
    over [0, n): the same shared loop the band workers run.
    """
    var width = len(key_columns)
    var n_aggs = len(value_columns)
    var n_rows = batch.n_rows
    var value_cols = List[Float64Array]()
    for j in range(n_aggs):
        value_cols.append(batch.column(value_columns[j]))
    var value_nulls = _col_guard_flags(value_cols, n_rows)

    var key_tuples = List[Float64]()
    var stripes = List[GroupAccumulator]()

    if width == 1:
        var key_col = batch.column(key_columns[0])
        var index = HashIndex(64)
        var null_key_rows = _fused_scan_w1(
            key_col,
            value_cols,
            opcodes,
            key_col.null_count() > 0 or key_col.length < n_rows,
            value_nulls,
            0,
            n_rows,
            index,
            key_tuples,
            stripes,
        )
        return _finish_many(key_tuples, width, stripes, n_aggs, opcodes, null_key_rows)

    var key_cols = List[Float64Array]()
    for i in range(width):
        key_cols.append(batch.column(key_columns[i]))
    var key_null_flags = _col_guard_flags(key_cols, n_rows)
    var key_nulls = False
    for i in range(width):
        if key_null_flags[i]:
            key_nulls = True
    var index = CompositeKeyIndex(width, 64)
    var null_key_rows = _fused_scan_wn(
        key_cols,
        value_cols,
        opcodes,
        key_nulls,
        value_nulls,
        0,
        n_rows,
        index,
        key_tuples,
        stripes,
    )
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
    var value_nulls = _col_guard_flags(value_cols, n_rows)
    var key_null_flags = _col_guard_flags(key_cols, n_rows)
    var key_nulls = False
    for i in range(width):
        if key_null_flags[i]:
            key_nulls = True

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
        # The SAME scan body the serial path runs, over this worker's band and
        # private state — one loop, so serial and banded cannot diverge.
        if width == 1:
            var index = HashIndex(64)
            np[w] = _fused_scan_w1(
                key_cols[0], value_cols, opcodes, key_nulls, value_nulls,
                lo, hi, index, tp[w], sp[w],
            )
        else:
            var index = CompositeKeyIndex(width, 64)
            np[w] = _fused_scan_wn(
                key_cols, value_cols, opcodes, key_nulls, value_nulls,
                lo, hi, index, tp[w], sp[w],
            )

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
    """The fused scan radix-partitioned: hash once, counted two-phase scatter,
    build partitions independently, restore first-appearance order by
    first-row index.

    Round 3 replaced round 2's per-element `List.append` bucket build — an
    amortized-growth store plus bounds logic per surviving row, the measured
    dominant cost at 1e7 rows — with a counted scatter over ONE preallocated
    payload buffer. The partition CONTENTS and their order are exactly what
    the appends produced; only the store machinery changed, which is why the
    round-2 suite (radix == serial bit-for-bit, order included) still pins it.

    What each pass does:

      pass A (parallel over `workers` contiguous bands): per surviving row,
        chain `fnv_fold` over the normalized key elements ONCE — the same
        fold every table here probes with, from `columnar.hash_index`, so
        routing and probing cannot diverge — keep the hash in a row-indexed
        buffer, and COUNT the row into (worker, top-`RADIX_BITS` partition).

      prefix sum (serial, workers x partitions entries): counts become
        segment offsets, partition-major with band order inside a partition —
        so partition p's region holds ascending global row order.

      pass B (parallel over the same bands): re-walk the band, re-apply pass
        A's null test (deterministic, so the same rows survive), and write
        (keys, values-or-0.0, row index, validity bitmask, stored hash) at
        the (worker, partition) cursor with raw stores. Bounds argument:
        each cursor starts at its offset and bumps once per counted row, so
        every index stays under offset + count <= survivors by construction —
        and the final cursors are CHECKED; a mismatch falls back to the
        independent banded engine loudly instead of trusting the scatter.

      pass 2 (parallel over `RADIX_PARTITIONS`): partition p's table is built
        by ONE task over its contiguous segment, probing with the STORED hash
        (`get_or_assign_bits`/`get_or_assign_hashed`). The segment ascends in
        global row order, so every group's accumulator folds its rows in
        exactly the serial path's order (results bit-identical to 1 worker,
        no merge tolerance anywhere), each group's recorded first row IS its
        global first appearance, and each partition's group list ascends in
        that index. Updates are opcode-specialized (`observe_op`).

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
    var value_nulls = _col_guard_flags(value_cols, n_rows)
    var key_null_flags = _col_guard_flags(key_cols, n_rows)
    var key_nulls = False
    for i in range(width):
        if key_null_flags[i]:
            key_nulls = True

    var band = (n_rows + workers - 1) // workers
    var row_floats = width + n_aggs

    # ── pass A: hash every surviving row ONCE, count rows per (worker,
    #    partition). No stores but the hash and a 16-counter bump — round 2's
    #    per-element List.append bucket build is what this pass replaces. ─────
    var hrow = alloc[UInt64](n_rows)
    var counts = List[Int](length=workers * RADIX_PARTITIONS, fill=0)
    var w_nulls = List[Int](length=workers, fill=0)
    var cp = counts.unsafe_ptr()
    var np = w_nulls.unsafe_ptr()

    @parameter
    fn count_worker(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n_rows:
            hi = n_rows
        var kps = List[UnsafePointer[Float64, origin=MutAnyOrigin]](capacity=width)
        for c in range(width):
            kps.append(key_cols[c].values[].unsafe_ptr() + key_cols[c].offset)
        # Worker-local counters, copied out once: adjacent workers' slices of
        # the shared counts array share cache lines, and a per-row bump there
        # would be false sharing on the hottest store in the pass.
        var local = List[Int](length=RADIX_PARTITIONS, fill=0)
        var lp = local.unsafe_ptr()
        var nulls = 0
        if width == 1 and not key_nulls:
            # The H2O q3/q5/q7 shape: one key column, no nulls — worth its own
            # loop so the width loop's per-row branch disappears.
            var kp0 = kps[0]
            for r in range(lo, hi):
                var h = fnv_fold(FNV_OFFSET_BASIS, normalize_bits(kp0[r]))
                hrow[r] = h
                lp[Int(h >> (64 - RADIX_BITS))] += 1
        else:
            for r in range(lo, hi):
                if key_nulls:
                    var any_null = False
                    for c in range(width):
                        if not key_cols[c].is_valid_at(r):
                            any_null = True
                            break
                    if any_null:
                        nulls += 1
                        continue
                var h = FNV_OFFSET_BASIS
                for c in range(width):
                    h = fnv_fold(h, normalize_bits(kps[c][r]))
                hrow[r] = h
                lp[Int(h >> (64 - RADIX_BITS))] += 1
        for p in range(RADIX_PARTITIONS):
            cp[w * RADIX_PARTITIONS + p] = lp[p]
        np[w] = nulls

    parallelize[count_worker](workers)

    # ── prefix sum: counts to segment offsets, partition-major, band order
    #    within a partition. Segment (w, p) therefore holds ascending global
    #    rows, and partition p's whole region is ascending too — the fold
    #    order the bit-equal-to-serial promise needs. ─────────────────────────
    var offsets = List[Int](length=workers * RADIX_PARTITIONS, fill=0)
    var part_start = List[Int](length=RADIX_PARTITIONS + 1, fill=0)
    var running = 0
    for p in range(RADIX_PARTITIONS):
        part_start[p] = running
        for w in range(workers):
            offsets[w * RADIX_PARTITIONS + p] = running
            running += counts[w * RADIX_PARTITIONS + p]
    part_start[RADIX_PARTITIONS] = running
    var survivors = running

    # ── pass B: write each surviving row's payload at its cursor, raw stores.
    #    SAFETY: cursor(w, p) starts at offset(w, p) and bumps once per row
    #    pass A counted for (w, p) — pass A and pass B run the SAME null test
    #    and the SAME stored hash, so the row sets are identical and every
    #    write index is < offset(w, p) + count(w, p) <= survivors by the
    #    prefix-sum construction. The final cursors are CHECKED below; a
    #    mismatch abandons the scatter for the independent banded engine
    #    rather than trusting it. ─────────────────────────────────────────────
    var pf = alloc[Float64](survivors * row_floats if survivors > 0 else 1)
    var pm = alloc[Int](survivors * 2 if survivors > 0 else 1)
    var ph = alloc[UInt64](survivors if survivors > 0 else 1)
    var cursors = List[Int](length=workers * RADIX_PARTITIONS, fill=0)
    for i in range(workers * RADIX_PARTITIONS):
        cursors[i] = offsets[i]
    var up = cursors.unsafe_ptr()

    @parameter
    fn scatter_worker(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n_rows:
            hi = n_rows
        var kps = List[UnsafePointer[Float64, origin=MutAnyOrigin]](capacity=width)
        for c in range(width):
            kps.append(key_cols[c].values[].unsafe_ptr() + key_cols[c].offset)
        var vps = List[UnsafePointer[Float64, origin=MutAnyOrigin]](capacity=n_aggs)
        for j in range(n_aggs):
            vps.append(value_cols[j].values[].unsafe_ptr() + value_cols[j].offset)
        var local = List[Int](length=RADIX_PARTITIONS, fill=0)
        var lp = local.unsafe_ptr()
        for p in range(RADIX_PARTITIONS):
            lp[p] = up[w * RADIX_PARTITIONS + p]
        var any_value_nulls = False
        for j in range(n_aggs):
            if value_nulls[j]:
                any_value_nulls = True
        if width == 1 and not key_nulls and not any_value_nulls:
            # The all-present single-key shape, again worth its own loop: no
            # validity anywhere, the full bitmask is a constant.
            var kp0 = kps[0]
            var full_mask = (1 << n_aggs) - 1
            for r in range(lo, hi):
                var h = hrow[r]
                var part = Int(h >> (64 - RADIX_BITS))
                var s = lp[part]
                lp[part] = s + 1
                var base = s * row_floats
                pf[base] = kp0[r]
                for j in range(n_aggs):
                    pf[base + 1 + j] = vps[j][r]
                pm[2 * s] = r
                pm[2 * s + 1] = full_mask
                ph[s] = h
        else:
            for r in range(lo, hi):
                if key_nulls:
                    # The same test pass A ran; deterministic, so the same rows skip.
                    var any_null = False
                    for c in range(width):
                        if not key_cols[c].is_valid_at(r):
                            any_null = True
                            break
                    if any_null:
                        continue
                var h = hrow[r]
                var part = Int(h >> (64 - RADIX_BITS))
                var s = lp[part]
                lp[part] = s + 1
                var base = s * row_floats
                for c in range(width):
                    pf[base + c] = kps[c][r]
                var vmask = 0
                for j in range(n_aggs):
                    if not value_nulls[j] or value_cols[j].is_valid_at(r):
                        vmask = vmask | (1 << j)
                        pf[base + width + j] = vps[j][r]
                    else:
                        pf[base + width + j] = 0.0
                pm[2 * s] = r
                pm[2 * s + 1] = vmask
                ph[s] = h
        for p in range(RADIX_PARTITIONS):
            up[w * RADIX_PARTITIONS + p] = lp[p]

    parallelize[scatter_worker](workers)
    hrow.free()

    # The raw stores' bounds argument, checked rather than trusted.
    var scatter_ok = True
    for i in range(workers * RADIX_PARTITIONS):
        if cursors[i] != offsets[i] + counts[i]:
            scatter_ok = False
    if not scatter_ok:
        pf.free()
        pm.free()
        ph.free()
        print(
            "group_by_many_radix: scatter cursor invariant violated;"
            " falling back to the banded engine"
        )
        return group_by_many_banded(batch, key_columns, value_columns, opcodes, n_workers)

    # ── pass 2: one task per partition, over its contiguous payload segment.
    #    Probes reuse pass A's stored hash; fold order is ascending global row
    #    order by the prefix-sum layout, exactly as round 2's concatenation. ──
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
        var s0 = part_start[p]
        var s1 = part_start[p + 1]
        if width == 1:
            var index = HashIndex(64)
            for s in range(s0, s1):
                var base = s * row_floats
                var key = pf[base]
                var slot = index.get_or_assign_bits(
                    normalize_bits(key), ph[s], group_count
                )
                if slot == group_count:
                    group_count += 1
                    ptp[p].append(key)
                    for _ in range(n_aggs):
                        psp[p].append(GroupAccumulator(key))
                    pfp[p].append(pm[2 * s])
                var vmask = pm[2 * s + 1]
                var sbase = slot * n_aggs
                for j in range(n_aggs):
                    if ((vmask >> j) & 1) == 1:
                        psp[p][sbase + j].observe_op(opcodes[j], pf[base + 1 + j])
        else:
            var index = CompositeKeyIndex(width, 64)
            var key = List[Float64](length=width, fill=0.0)
            var kb = key.unsafe_ptr()
            for s in range(s0, s1):
                var base = s * row_floats
                for c in range(width):
                    kb[c] = pf[base + c]
                var slot = index.get_or_assign_hashed(key, ph[s], group_count)
                if slot == group_count:
                    group_count += 1
                    for c in range(width):
                        ptp[p].append(kb[c])
                    for _ in range(n_aggs):
                        psp[p].append(GroupAccumulator(kb[0]))
                    pfp[p].append(pm[2 * s])
                var vmask = pm[2 * s + 1]
                var sbase = slot * n_aggs
                for j in range(n_aggs):
                    if ((vmask >> j) & 1) == 1:
                        psp[p][sbase + j].observe_op(opcodes[j], pf[base + width + j])

    parallelize[partition_worker](RADIX_PARTITIONS)
    pf.free()
    pm.free()
    ph.free()

    # ── order restore: P-way merge on ascending first-row lists ────────────────
    var null_key_rows = 0
    for w in range(workers):
        null_key_rows += w_nulls[w]
    var total_groups = 0
    for p in range(RADIX_PARTITIONS):
        total_groups += len(p_first[p])

    var heads = List[Int](capacity=RADIX_PARTITIONS)
    for _ in range(RADIX_PARTITIONS):
        heads.append(0)
    var key_tuples = List[Float64](capacity=total_groups * width)
    var stripes = List[GroupAccumulator](capacity=total_groups * n_aggs)
    for _ in range(total_groups):
        var best_p = -1
        var best_row = n_rows  # every recorded first row is < n_rows
        for p in range(RADIX_PARTITIONS):
            if heads[p] < len(p_first[p]) and p_first[p][heads[p]] < best_row:
                best_p = p
                best_row = p_first[p][heads[p]]
        if best_p < 0:
            break  # unreachable: total_groups is the sum of the list lengths
        var g = heads[best_p]
        heads[best_p] = g + 1
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
    var value_nulls = _col_guard_flags(value_cols, n_rows)
    var key_has_nulls = key_col.null_count() > 0 or key_col.length < n_rows
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
        var kp = key_col.values[].unsafe_ptr() + key_col.offset
        var vps = List[UnsafePointer[Float64, origin=MutAnyOrigin]](capacity=n_aggs)
        for j in range(n_aggs):
            vps.append(value_cols[j].values[].unsafe_ptr() + value_cols[j].offset)
        for r in range(n_rows):
            if key_has_nulls and not key_col.is_valid_at(r):
                null_key_rows += 1
                continue
            var k = kp[r]
            if not (k >= 0.0) or k >= bound:
                return CodedGroupedResult(GROUP_CODED_KEY_NOT_A_CODE, _empty_many())
            var code = Int(k)
            if Float64(code) != k:
                return CodedGroupedResult(GROUP_CODED_KEY_NOT_A_CODE, _empty_many())
            if not seen[code]:
                seen[code] = True
                order.append(code)
            var sbase = code * n_aggs
            for j in range(n_aggs):
                if not value_nulls[j] or value_cols[j].is_valid_at(r):
                    stripes[sbase + j].observe_op(opcodes[j], vps[j][r])
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
        var kp = key_col.values[].unsafe_ptr() + key_col.offset
        var vps = List[UnsafePointer[Float64, origin=MutAnyOrigin]](capacity=n_aggs)
        for j in range(n_aggs):
            vps.append(value_cols[j].values[].unsafe_ptr() + value_cols[j].offset)
        for r in range(lo, hi):
            if key_has_nulls and not key_col.is_valid_at(r):
                nulls += 1
                continue
            var k = kp[r]
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
            var sbase = code * n_aggs
            for j in range(n_aggs):
                if not value_nulls[j] or value_cols[j].is_valid_at(r):
                    sp[w][sbase + j].observe_op(opcodes[j], vps[j][r])
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
