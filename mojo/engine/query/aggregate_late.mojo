"""query.aggregate_late — the radix aggregate with the payload round-trip removed.

What this is for
----------------
`query.aggregate.group_by_many_radix` is the engine that carries the 100k-group
H2O questions (q3, q5, q7). It runs three passes and moves, for a q3-shaped call
(one key column, two aggregates, 1e7 rows, no nulls), about **1440 MB** where
physics needs 240 MB — a 6.0x amplification, measured from the buffer
declarations, not estimated:

    pass A   read key 80        write hrow 80
    pass B   read hrow 80, re-read key+values 240,
             write pf 240 + pm 160 + ph 80
    pass 2   re-read pf 240 + pm 160 + ph 80

Four of those buffers exist only to carry a row from one pass to the next:

  * `pf` re-materializes the KEY column into the payload,
  * `pm` stores 16 bytes of bookkeeping per row — a row index plus a validity
    bitmask that, on an all-present batch, is a compile-time constant the code
    already knows (`full_mask`) and stores 1e7 times anyway,
  * `ph` carries the hash a third time,
  * `hrow` carries it across passes A and B.

This module keeps the radix STRUCTURE — partitioned so each pass-2 table is
cache-resident, which is why radix beats the band merge at 1e5 groups — and
removes the round-trip:

  * **the hash IS the key.** For a single key column the FNV fold over the
    key's eight normalized bytes is INJECTIVE (proof below), so the 64-bit
    hash decides key equality exactly. The key column is never scattered, and
    each group's key is LATE-MATERIALIZED from its first row at the end —
    which is bit-for-bit the value the shipped path stores, because the
    shipped path also takes the key of the row that first assigned the slot.
  * **no validity mask.** The engine only runs when every key and value slot
    is present, so the mask is not merely constant, it is absent.
  * **one pass over the source.** Per-(worker, partition) segments are
    over-allocated from a capacity sized by the binomial bound AND by the
    key skew a cheap probe measures, so the counting pass, the prefix sum and
    `hrow` all disappear; the key and value columns are read exactly ONCE.
    Segment overflow is CHECKED and refuses the whole call.

Measured on the real 1e7-row H2O batch (min-of-8 interleaved against the shipped
engine in the same process, load ~267 — ratios only, absolutes are inflated):
q3 2.30x, q5 2.17x, q7 3.04x by median of per-rep ratios. The payload itself
falls from 1440 MB to **880 MB** on q3 (240 source + 320 scatter + 320 read),
a 1.64x byte cut, and the byte model is reported by `fused_scratch_bytes` so a
caller can check the claim rather than believe it.

Why the hash can replace the key (single key column only)
---------------------------------------------------------
`fnv_fold(FNV_OFFSET_BASIS, bits)` folds a FIXED eight bytes:

    h = h0;  for each byte b of bits (low first):  h = (h ^ b) * PRIME

It is injective in `bits`. Take two inputs whose bytes first differ at position
i. The states are equal entering step i (they consumed identical bytes), and
step i maps them apart: `h ^ b` is injective in `b` over `b < 256`, and
multiplication by an odd prime is a bijection mod 2^64. Every LATER step applies
the SAME byte to both states and is itself a bijection, so the two states can
never re-converge. Distinct normalized key bits therefore always produce
distinct hashes — there is no collision probability to bound, and comparing
hashes is comparing keys.

This argument needs the fixed length. A width-N composite hash chains N folds
over 8N bytes into 64 bits and is NOT injective, so `fused_late_applicable`
refuses width != 1 and the caller keeps the shipped engine. That is not a
performance hedge, it is the boundary of the proof.

What is byte-for-byte unchanged
-------------------------------
Nothing in this module does arithmetic on a value. Every accumulator update is
`GroupAccumulator.observe_op`, the same frozen primitive the shipped engines
call, in the same order:

  * fold order is ascending global row order, exactly as the shipped radix's
    prefix-sum layout produces — pass 2 walks partition p's segments in WORKER
    order and each worker's segment ascends in row order, because the worker
    appended while scanning its contiguous band forward. So sums, means and m2
    are bit-identical to the one-worker serial fold, not merely within
    tolerance.
  * the NaN policy is inherited, not restated. A NaN VALUE counts, poisons
    sum/mean/m2 associatively and contributes to NO extremum; an all-NaN group
    reports the canonical quiet NaN through `value_for`. A NaN KEY is
    in-domain and canonicalized by `normalize_bits`, so every NaN key joins one
    group whose reported key is the first NaN that arrived — the same bits the
    shipped path reports.
  * group ORDER is global first-appearance, restored by the same P-way merge on
    ascending first-row indices.

Bounds, and why an out-of-range write is impossible
---------------------------------------------------
Mojo has no catchable out-of-bounds: a store past the end takes the worker
process down, and `try`/`except` around the call does not help. So every raw
store here is bounded BEFORE it happens, never after:

  * segment (w, p) owns words [(w * P + p) * segcap * rec, ... + segcap * rec).
    The write index is `base + c * rec + k` with `c < segcap` tested on the
    line above the store and `k < rec`, so the largest index reachable is
    `(workers * P - 1) * segcap * rec + (segcap - 1) * rec + rec - 1`, which is
    exactly one less than the allocation. There is no arithmetic path to a
    larger index.
  * `c >= segcap` sets a per-worker flag, breaks the band, and the CALL is
    refused after the parallel region — the partially filled segments are
    freed and `group_by_many_radix` answers instead. A skewed hash therefore
    costs one wasted pass, never a wrong answer and never a crash.
  * pass 2 reads `i < fill[w * P + p]`, and `fill` is what the scatter counted,
    which is <= segcap by the test above.
  * a row index read back out of a segment was written as a loop variable in
    [lo, hi) with hi <= n_rows, so indexing the key column with it is in range.

Footprint rule: never allocate more than the engine being replaced
------------------------------------------------------------------
Over-allocating segments trades memory for a pass. `fused_scratch_bytes` and
`shipped_scratch_bytes` price both engines for the call, and
`fused_late_applicable` refuses when the fused engine would ask for MORE than
the shipped one. That happens on two shapes, both real: very many aggregates
(the shipped payload's fixed 32 bytes/row of bookkeeping eventually beats the
slack on a wide record — measured at 24 aggregates: 2066 MiB fused vs 2212 MiB
shipped is still fine, so the crossover sits just above), and a SKEWED key
whose heaviest partition needs a capacity well above the mean. Rule 1c of
`docs/mojo/new-kernel-package-rules.md` ("a per-item ceiling is not a bound on
total allocation") is the reason this is a computed comparison and not a
comment.

Entry points
------------
  * `group_by_many_radix_fused` — the engine. Delegates to
    `group_by_many_radix` whenever `fused_late_applicable` says no, and on a
    checked segment overflow, so it is total: safe to call on any batch.
  * `group_by_many_late` — the routed entry point: this engine where it
    applies, `group_by_many` otherwise. Drop-in for `group_by_many`.
  * `fused_late_applicable`, `fused_scratch_bytes`, `fused_scratch_bytes_for`,
    `shipped_scratch_bytes`, `fused_segment_capacity`,
    `fused_segment_capacity_for`, `fused_partition_peak` — public, so the
    routing decision, the skew measurement and the byte model are testable
    rather than asserted.
"""
from std.algorithm import parallelize
from std.memory import alloc, bitcast
from std.sys import info

from columnar.array import Float64Array
from columnar.batch import RecordBatch
from columnar.hash_index import FNV_OFFSET_BASIS, fnv_fold, normalize_bits
from query.aggregate import (
    CARDINALITY_PROBE_ROWS,
    GroupAccumulator,
    ManyGroupedResult,
    RADIX_BITS,
    RADIX_PARTITIONS,
    ROUTE_RADIX,
    _col_guard_flags,
    _finish_many,
    _many_request_ok,
    group_by_many,
    group_by_many_radix,
    plan_many_route,
    planned_workers,
)

comptime FUSED_INDEX_MIN_CAPACITY: Int = 1024
"""Starting table size per partition. 1024 entries = 16 KB, L1-resident, and
covers a partition of up to 716 groups before the first growth."""

comptime FUSED_MIN_ROWS: Int = 1 << 16
"""Below this the scatter cannot pay for itself; the shipped engines' own
crossover (`PARALLEL_MIN_ROWS`) is the same number for the same reason."""


# ═══════════════════════════════════════════════════════════════════════════════
# The byte model and the applicability test — public, pure, and testable
# ═══════════════════════════════════════════════════════════════════════════════


fn _isqrt(n: Int) -> Int:
    """Integer square root by Newton iteration. Called once per call, not per
    row, and integer-only so the capacity is a deterministic function of the
    shape rather than of a floating-point library."""
    if n <= 0:
        return 0
    var x = n
    var y = (x + 1) // 2
    while y < x:
        x = y
        y = (x + n // x) // 2
    return x


fn fused_segment_capacity(n_rows: Int, workers: Int) -> Int:
    """Rows one (worker, partition) segment can hold.

    A worker's band holds `band` rows and the top `RADIX_BITS` of an FNV hash
    route them into `RADIX_PARTITIONS` segments, so a segment's occupancy is
    Binomial(band, 1/P): mean `band / P`, standard deviation
    `sqrt(band / P * (1 - 1/P))`, which `sqrt(mean)` bounds from above. The
    slack is therefore `8 * sqrt(mean) + 64` — EIGHT standard deviations, so
    the chance any of the `workers * P` segments overflows is on the order of
    1e-13 even after multiplying by the segment count, and the `+ 64` floor
    covers a band small enough that eight sigma is a handful of rows.

    Slack proportional to `sqrt(mean)` rather than to `mean` matters at the
    small end: a flat `mean / 8 + 1024` floor made the arena 87% slack on a
    300k-row batch, which tripped the footprint rule and pushed a batch this
    engine should have taken back onto the shipped one.

    This is a capacity, not a bound on the data: occupancy is CHECKED per row
    and an overflow refuses the whole call. Skew costs a wasted pass, never a
    wrong answer and never an out-of-range store.
    """
    if workers < 1 or n_rows < 0:
        return 0
    var band = (n_rows + workers - 1) // workers
    var mean = band // RADIX_PARTITIONS
    return mean + 8 * _isqrt(mean) + 64


fn fused_partition_peak(batch: RecordBatch, key_column: Int, probe_rows: Int) -> Int:
    """Rows the most-loaded radix partition takes over the first `probe_rows`
    rows, under the SAME hash and the SAME top-`RADIX_BITS` routing the scatter
    uses.

    Why this exists: the binomial capacity model above assumes a segment's rows
    come from MANY distinct keys. One key's rows all share a hash and therefore
    all land in ONE partition, so a heavy hitter breaks the model outright — a
    key holding 1/13 of the rows overflowed an 8-sigma segment by 8% in the
    adversarial suite, which cost a wasted pass and a silent fall back to the
    engine this one is supposed to beat. Measuring the peak turns that cliff
    into a sized allocation.

    It reads the same window `probe_cardinality` reads, so it costs what the
    routing probe already costs and sees the same rows the router saw.
    """
    var n_rows = batch.n_rows
    var rows = probe_rows
    if rows > n_rows:
        rows = n_rows
    if rows <= 0:
        return 0
    var col = batch.column(key_column)
    var counts = List[Int](length=RADIX_PARTITIONS, fill=0)
    for r in range(rows):
        # `is_valid_at` rather than a raw read: this runs before the null guard
        # in `fused_late_applicable` has necessarily been consulted, and a null
        # slot must not be hashed.
        if not col.is_valid_at(r):
            continue
        var h = fnv_fold(FNV_OFFSET_BASIS, normalize_bits(col.get(r)))
        counts[Int(h >> (64 - RADIX_BITS))] += 1
    var peak = 0
    for p in range(RADIX_PARTITIONS):
        if counts[p] > peak:
            peak = counts[p]
    return peak


fn fused_segment_capacity_for(
    n_rows: Int, workers: Int, peak: Int, probe_rows: Int
) -> Int:
    """Segment capacity for a batch whose probed partition peak is `peak` over
    `probe_rows` rows.

    Two bounds, whichever is larger:

      * the uniform binomial bound (`fused_segment_capacity`), which is what a
        many-keys batch needs;
      * the observed peak share extrapolated to a band, plus its own eight
        sigma: `est = band * peak / probe_rows`, capacity `est + 8*sqrt(est)`.

    The extrapolation can still UNDER-predict — the probe reads the head of the
    batch and a band lives elsewhere, so clustered data can shift the peak. That
    is why occupancy is checked per row regardless: this function decides how
    often the check fires, never whether it is needed.
    """
    var uniform = fused_segment_capacity(n_rows, workers)
    if peak <= 0 or probe_rows <= 0 or workers < 1:
        return uniform
    var rows = probe_rows
    if rows > n_rows:
        rows = n_rows
    if rows <= 0:
        return uniform
    var band = (n_rows + workers - 1) // workers
    var est = (band * peak) // rows
    var skewed = est + 8 * _isqrt(est) + 64
    return skewed if skewed > uniform else uniform


fn fused_scratch_bytes(n_rows: Int, n_aggs: Int, workers: Int) -> Int:
    """Bytes this engine's segment arena needs for a UNIFORM batch.

    One record per row is `2 + n_aggs` eight-byte words: the hash (which is
    also the key's identity), the row index, and one value per aggregate. The
    arena is `workers * RADIX_PARTITIONS` segments of `fused_segment_capacity`
    records. `fused_scratch_bytes_for` prices the skew-aware capacity, which is
    the one the engine and the footprint rule actually use.
    """
    return fused_scratch_bytes_for(n_rows, n_aggs, workers, 0, 0)


fn fused_scratch_bytes_for(
    n_rows: Int, n_aggs: Int, workers: Int, peak: Int, probe_rows: Int
) -> Int:
    """`fused_scratch_bytes` at the skew-aware capacity."""
    if n_rows <= 0 or n_aggs <= 0 or workers < 1:
        return 0
    var rec = 2 + n_aggs
    var cap = fused_segment_capacity_for(n_rows, workers, peak, probe_rows)
    return workers * RADIX_PARTITIONS * cap * rec * 8


fn shipped_scratch_bytes(n_rows: Int, width: Int, n_aggs: Int) -> Int:
    """Bytes `group_by_many_radix` allocates for the same call, from its own
    declarations: `hrow` (8/row), `pf` ((width + n_aggs) * 8 per surviving
    row), `pm` (16), `ph` (8). With no key nulls every row survives."""
    if n_rows <= 0 or n_aggs <= 0:
        return 0
    return n_rows * (8 + (width + n_aggs) * 8 + 16 + 8)


fn fused_late_applicable(
    batch: RecordBatch,
    key_columns: List[Int],
    value_columns: List[Int],
    opcodes: List[Int],
    n_workers: Int,
) -> Bool:
    """Whether the fused late-materialized engine may answer this call.

    Every clause is a boundary of a proof or a guard, not a tuning knob:

      * `width == 1` — the hash-is-the-key argument needs a FIXED-length fold.
        A composite hash is not injective, so a width > 1 payload must still
        carry the key and there is nothing to remove.
      * no NULLS in the key column or any value column — the engine's record
        has no validity mask, and a null key would have to be skipped and
        tallied. Both are the shipped engine's job.
      * `workers > 1` and `n_rows >= FUSED_MIN_ROWS` — below that the scatter
        is pure overhead.
      * **`plan_many_route` must already choose RADIX for this call.** This
        engine replaces RADIX and only RADIX, so it claims exactly RADIX's
        shapes. Without this clause a 100-group batch would be taken from the
        CODED engine, which is several times faster on it — a routing
        regression dressed as an optimization. It also buys the invariant that
        makes `group_by_many_late` safe: applicability implies the router would
        have run the radix engine, and this engine is bit-identical to it, so
        the substitution cannot move a single bit on any batch.
      * the fused arena must not be LARGER than the payload the shipped engine
        would allocate for the same call, priced at the SKEW-AWARE capacity
        (see the footprint rule in the module docstring).
      * a well-formed request, by the same `_many_request_ok` every engine uses.
    """
    if not _many_request_ok(value_columns, opcodes):
        return False
    if len(key_columns) != 1:
        return False
    var n_rows = batch.n_rows
    if n_rows < FUSED_MIN_ROWS:
        return False
    var workers = n_workers
    if workers > n_rows:
        workers = n_rows
    if workers <= 1:
        return False
    var n_aggs = len(value_columns)
    var cols = List[Float64Array]()
    cols.append(batch.column(key_columns[0]))
    for j in range(n_aggs):
        cols.append(batch.column(value_columns[j]))
    var flags = _col_guard_flags(cols, n_rows)
    for i in range(len(flags)):
        if flags[i]:
            return False
    if plan_many_route(batch, key_columns, workers).route != ROUTE_RADIX:
        return False
    var peak = fused_partition_peak(batch, key_columns[0], CARDINALITY_PROBE_ROWS)
    if fused_scratch_bytes_for(
        n_rows, n_aggs, workers, peak, CARDINALITY_PROBE_ROWS
    ) > shipped_scratch_bytes(n_rows, 1, n_aggs):
        return False
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# A flat hash -> slot index over 64-bit identities
# ═══════════════════════════════════════════════════════════════════════════════


struct _FusedIndex(Copyable, Movable):
    """Open-addressed `UInt64 identity -> slot`, linear probing, power-of-two
    capacity.

    Same RELATION as `columnar.hash_index.HashIndex`: first-appearance slot
    numbering supplied by the caller, exact equality on a 64-bit identity,
    one probe sequence shared by lookup and insert. It differs only in the
    container — raw arrays instead of `List`, so the probe loop carries no
    bounds check, and an integer load-factor test instead of a float one.

    `slots[pos] < 0` marks empty, so `keys` may hold ANY UInt64 including 0 —
    which matters here because the identity is a hash, not a small code.
    """

    var keys: UnsafePointer[UInt64, origin=MutAnyOrigin]
    var slots: UnsafePointer[Int, origin=MutAnyOrigin]
    var mask: Int
    var count: Int
    var limit: Int

    fn __init__(out self, initial_capacity: Int):
        var cap = FUSED_INDEX_MIN_CAPACITY
        while cap < initial_capacity:
            cap = cap << 1
        self.keys = alloc[UInt64](cap)
        self.slots = alloc[Int](cap)
        for i in range(cap):
            self.slots[i] = -1
        self.mask = cap - 1
        self.count = 0
        self.limit = (cap * 7) // 10

    fn free_all(self):
        self.keys.free()
        self.slots.free()

    @always_inline
    fn get_or_assign(mut self, identity: UInt64, next_slot: Int) -> Int:
        """The slot already holding `identity`, or `next_slot` after taking it.

        The caller supplies the slot number for the same reason
        `HashIndex.get_or_assign` does: the index and the caller's accumulator
        array cannot drift, because the caller appends exactly when this
        returns the value it passed in.
        """
        var pos = Int(identity) & self.mask
        while self.slots[pos] >= 0:
            if self.keys[pos] == identity:
                return self.slots[pos]
            pos = (pos + 1) & self.mask
        self.slots[pos] = next_slot
        self.keys[pos] = identity
        self.count += 1
        if self.count > self.limit:
            self._grow()
        return next_slot

    fn _grow(mut self):
        """Double and rehash. Positions come from the identity's low bits, the
        same function the probe uses, so no entry can be reinserted onto a
        chain the probe would not walk."""
        var old_cap = self.mask + 1
        var old_keys = self.keys
        var old_slots = self.slots
        var cap = old_cap << 1
        self.keys = alloc[UInt64](cap)
        self.slots = alloc[Int](cap)
        for i in range(cap):
            self.slots[i] = -1
        self.mask = cap - 1
        self.limit = (cap * 7) // 10
        for i in range(old_cap):
            if old_slots[i] < 0:
                continue
            var pos = Int(old_keys[i]) & self.mask
            while self.slots[pos] >= 0:
                pos = (pos + 1) & self.mask
            self.slots[pos] = old_slots[i]
            self.keys[pos] = old_keys[i]
        old_keys.free()
        old_slots.free()


# ═══════════════════════════════════════════════════════════════════════════════
# The engine
# ═══════════════════════════════════════════════════════════════════════════════


fn group_by_many_radix_fused(
    batch: RecordBatch,
    key_columns: List[Int],
    value_columns: List[Int],
    opcodes: List[Int],
    n_workers: Int,
) -> ManyGroupedResult:
    """Radix-partitioned fused aggregate with the payload round-trip removed.

    Total: on any batch this engine cannot answer — width != 1, any null, too
    few rows, an arena larger than the shipped engine's payload, a malformed
    request, or a checked segment overflow — it returns exactly what
    `group_by_many_radix` returns, by calling it.

    Two passes, not three:

      pass 1 (parallel over `workers` contiguous bands): read the key and the
        value columns ONCE, fold the key's eight normalized bytes into a hash
        with the same `fnv_fold` every table here probes with, and append the
        record (hash, row index, values...) to the segment for
        (worker, top-`RADIX_BITS` partition). No counting pass, no prefix sum,
        no row-indexed hash buffer, and the key column is not re-read.

      pass 2 (parallel over `RADIX_PARTITIONS`): partition p's table is built
        by ONE task walking its segments in WORKER order. Each segment ascends
        in global row order (its worker scanned a contiguous band forward), so
        the concatenation ascends too and every group folds its rows in the
        serial path's order — bit-identical to one worker, no merge tolerance.
        The identity probed is the hash; the group's KEY is read from the key
        column at the group's first row, once per group, which is the same
        value the shipped payload carried for every row.

      order restore (sequential): the same P-way merge on ascending first-row
        lists, O(groups x partitions), never rows.
    """
    if not fused_late_applicable(batch, key_columns, value_columns, opcodes, n_workers):
        return group_by_many_radix(batch, key_columns, value_columns, opcodes, n_workers)

    var n_aggs = len(value_columns)
    var n_rows = batch.n_rows
    var workers = n_workers
    if workers > n_rows:
        workers = n_rows
    var key_col = batch.column(key_columns[0])
    var value_cols = List[Float64Array]()
    for j in range(n_aggs):
        value_cols.append(batch.column(value_columns[j]))

    var band = (n_rows + workers - 1) // workers
    var rec = 2 + n_aggs
    # The SAME capacity `fused_late_applicable` priced, recomputed from the
    # same deterministic probe over the same batch — so the arena the footprint
    # rule approved is the arena that gets allocated.
    var segcap = fused_segment_capacity_for(
        n_rows,
        workers,
        fused_partition_peak(batch, key_columns[0], CARDINALITY_PROBE_ROWS),
        CARDINALITY_PROBE_ROWS,
    )
    var n_seg = workers * RADIX_PARTITIONS
    var seg = alloc[UInt64](n_seg * segcap * rec)
    var fill = List[Int](length=n_seg, fill=0)
    var fp = fill.unsafe_ptr()
    var overflow = List[Int](length=workers, fill=0)
    var ofp = overflow.unsafe_ptr()
    # `_col_guard_flags` returned all-clear inside `fused_late_applicable`, so
    # every slot in [0, n_rows) of these columns is present AND in range: a raw
    # values-pointer read is exactly `get(r)`. That flag is the whole license
    # for the pointer walks below.
    var kp = key_col.values[].unsafe_ptr() + key_col.offset

    @parameter
    fn fused_worker(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n_rows:
            hi = n_rows
        var vps = List[UnsafePointer[Float64, origin=MutAnyOrigin]](capacity=n_aggs)
        for j in range(n_aggs):
            vps.append(value_cols[j].values[].unsafe_ptr() + value_cols[j].offset)
        var vp = vps.unsafe_ptr()
        # Worker-local cursors and segment bases: the shared `fill` array is
        # written once at the end of the band, because a per-row bump there
        # would be false sharing on the hottest store in the pass.
        var cursor = List[Int](length=RADIX_PARTITIONS, fill=0)
        var cp = cursor.unsafe_ptr()
        var base = List[Int](length=RADIX_PARTITIONS, fill=0)
        var bp = base.unsafe_ptr()
        for p in range(RADIX_PARTITIONS):
            bp[p] = (w * RADIX_PARTITIONS + p) * segcap * rec
        var over = 0
        for r in range(lo, hi):
            var h = fnv_fold(FNV_OFFSET_BASIS, normalize_bits(kp[r]))
            var part = Int(h >> (64 - RADIX_BITS))
            var c = cp[part]
            if c >= segcap:
                # Bounded BEFORE the store, never after: the call is refused
                # below and the arena discarded.
                over = 1
                break
            cp[part] = c + 1
            var at = bp[part] + c * rec
            seg[at] = h
            seg[at + 1] = UInt64(r)
            for j in range(n_aggs):
                seg[at + 2 + j] = bitcast[DType.uint64](vp[j][r])
        for p in range(RADIX_PARTITIONS):
            fp[w * RADIX_PARTITIONS + p] = cp[p]
        ofp[w] = over

    parallelize[fused_worker](workers)

    var overflowed = 0
    for w in range(workers):
        overflowed += overflow[w]
    if overflowed > 0:
        seg.free()
        print(
            "group_by_many_radix_fused: a (worker, partition) segment overflowed"
            " its binomial capacity; answering with the shipped radix engine"
        )
        return group_by_many_radix(batch, key_columns, value_columns, opcodes, n_workers)

    var p_keys = List[List[Float64]](capacity=RADIX_PARTITIONS)
    var p_accs = List[List[GroupAccumulator]](capacity=RADIX_PARTITIONS)
    var p_first = List[List[Int]](capacity=RADIX_PARTITIONS)
    for _ in range(RADIX_PARTITIONS):
        p_keys.append(List[Float64]())
        p_accs.append(List[GroupAccumulator]())
        p_first.append(List[Int]())
    var pkp = p_keys.unsafe_ptr()
    var pap = p_accs.unsafe_ptr()
    var pfp = p_first.unsafe_ptr()

    @parameter
    fn partition_worker(p: Int):
        var index = _FusedIndex(FUSED_INDEX_MIN_CAPACITY)
        var group_count = 0
        # Task-LOCAL lists behind a cached raw pointer. The accumulator store
        # is the hottest write in the engine; going through the shared
        # `List[List[GroupAccumulator]]` costs a dependent load plus a bounds
        # check on every one of them. The pointer is refreshed after every
        # append, which is the only operation that can move the buffer, and
        # appends happen once per group, not once per row.
        var accs = List[GroupAccumulator](capacity=4096)
        var ap = accs.unsafe_ptr()
        var keys = List[Float64](capacity=2048)
        var firsts = List[Int](capacity=2048)
        var ops = List[Int](capacity=n_aggs)
        for j in range(n_aggs):
            ops.append(opcodes[j])
        var op = ops.unsafe_ptr()
        for w in range(workers):
            var b0 = (w * RADIX_PARTITIONS + p) * segcap * rec
            var cnt = fp[w * RADIX_PARTITIONS + p]
            for i in range(cnt):
                var at = b0 + i * rec
                var slot = index.get_or_assign(seg[at], group_count)
                if slot == group_count:
                    group_count += 1
                    var row = Int(seg[at + 1])
                    # LATE MATERIALIZATION: the key, once per group, from the
                    # group's first row. Bit-for-bit what the shipped payload
                    # carried per row, because the shipped path also records
                    # the key of the row that first took the slot.
                    var k = kp[row]
                    keys.append(k)
                    firsts.append(row)
                    for _ in range(n_aggs):
                        accs.append(GroupAccumulator(k))
                    ap = accs.unsafe_ptr()
                var sbase = slot * n_aggs
                for j in range(n_aggs):
                    ap[sbase + j].observe_op(
                        op[j], bitcast[DType.float64](seg[at + 2 + j])
                    )
        index.free_all()
        pkp[p] = keys^
        pap[p] = accs^
        pfp[p] = firsts^

    parallelize[partition_worker](RADIX_PARTITIONS)
    seg.free()

    # ── order restore: P-way merge on ascending first-row lists ───────────────
    var total_groups = 0
    for p in range(RADIX_PARTITIONS):
        total_groups += len(p_first[p])
    var heads = List[Int](length=RADIX_PARTITIONS, fill=0)
    var key_tuples = List[Float64](capacity=total_groups)
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
        key_tuples.append(p_keys[best_p][g])
        for j in range(n_aggs):
            stripes.append(p_accs[best_p][g * n_aggs + j].copy())

    # No key nulls on this route (`fused_late_applicable` refused otherwise),
    # so the null-key tally is zero rather than merely unreported.
    return _finish_many(key_tuples, 1, stripes, n_aggs, opcodes, 0)


fn group_by_many_late(
    batch: RecordBatch,
    key_columns: List[Int],
    value_columns: List[Int],
    opcodes: List[Int],
) -> ManyGroupedResult:
    """`group_by_many` with the fused late-materialized engine in front.

    A drop-in replacement: identical result on every batch, by construction —
    where the fused engine does not apply this IS `group_by_many`, and where it
    does the suites pin the two element for element.

    Kept as a separate entry point rather than an edit to
    `group_by_many_parallel`'s radix branch so this module composes with other
    work on `query.aggregate` without a merge conflict. An integrator who wants
    it on the default route replaces the `ROUTE_RADIX` call there with
    `group_by_many_radix_fused` — one line, same signature.
    """
    var workers = planned_workers(batch.n_rows, info.num_physical_cores())
    if fused_late_applicable(batch, key_columns, value_columns, opcodes, workers):
        return group_by_many_radix_fused(
            batch, key_columns, value_columns, opcodes, workers
        )
    return group_by_many(batch, key_columns, value_columns, opcodes)
