"""query.median_packed — grouped MEDIAN (plus SD, free) over a packed
composite key, for the one H2O question this plane's streaming accumulators
structurally cannot answer.

Why median cannot be an accumulator opcode
--------------------------------------------
Every aggregate this plane has ever shipped — sum, mean, min, max, var, std —
is a Welford-style O(1) FOLD: one running state per group, updated per row,
merged pairwise across bands. A median is an ORDER STATISTIC: it needs the
group's actual values, sorted, because "the middle value" is not expressible
as any running combination of the values seen so far (`pandas_groupby`'s own
`group_median_approx` — a P^2-style incremental nudge — is explicitly the
streaming APPROXIMATION this module refuses to be: it would not match
DuckDB/Polars' exact median and is unsuitable for a correctness crosscheck).
So this module does not extend `GroupAccumulator`; it materialises each
group's values into a contiguous region and calls the frozen, unmodified
`sorting.quicksort` on each one.

The two-pass counted scatter (`query.aggregate`'s round-3 idiom, generalised)
------------------------------------------------------------------------------
Pass A scans once: validates every key (the same `_packed_digit` guard
`query.packedkey` uses — a key that is not a code refuses the WHOLE call,
never an out-of-bounds write), records each row's packed SLOT into a
row-indexed buffer (`row_slot`, so pass B never re-derives it), and folds a
`GroupAccumulator.observe` per (worker, slot) — which is SD for free: the
Welford mean/m2 this fold already maintains is exactly what
`group_std_from_variance` needs, at no extra pass over v3 beyond the one
this module was already going to take. This is, bit-for-bit, the same fold
`query.packedkey.group_by_packed_parallel` would perform for `AGG_STD` at the
same band split — so a caller who wants ONLY the sd half can keep calling
that engine unchanged (no new work, per the module this one supplements), and
a caller who wants both never pays for the value column twice.

Between pass A and pass B, one serial pass turns each (worker, slot)'s COUNT
into a scatter OFFSET: `slot_offset[slot]` is a prefix sum of every slot's
total count (so each group's values land in one contiguous region of a
single shared buffer), and `starts[worker, slot]` is `slot_offset[slot]` plus
the counts of every EARLIER worker for that slot — `query.aggregate`'s "pass A
counts, a prefix sum turns counts into segment offsets, pass B writes at a
cursor" scatter, with the segments keyed by SLOT instead of by radix
partition.

Pass B re-walks the same bands, using `row_slot` rather than re-deriving the
guard, and writes each row's v3 at `cursor[worker, slot]`, incrementing the
cursor. SAFETY ARGUMENT for the raw stores, stated because an out-of-bounds
write here is exactly the uncatchable abort every guard in this plane exists
to prevent: `cursor[w, slot]` starts at `starts[w, slot]` and is bumped once
per row this worker scatters for that slot, so every write index is
`< starts[w, slot] + count[w, slot]` by construction, which by the prefix-sum
step is `<= slot_offset[slot] + total_count[slot] <= len(buffer)`. The pass
CHECKS the final cursors against `starts[w, slot] + count[w, slot]` afterward
and refuses loudly on a mismatch rather than trusting the arithmetic silently
— `query.aggregate`'s own round-3 scatter does the same check for the same
reason.

Pass C, band-parallel over GROUP ranges (`query.composed`'s
`merge_one_range` decomposition): copy each group's region out of the shared
buffer into a small owned `List[Float64]`, `sorting.quicksort` it (frozen,
unmodified), and read the median off the sorted copy — the average of the two
middle elements on an even count, the exact `anomaly.median` formula, just
without paying for `anomaly.median`'s own O(n^2) insertion sort at the
~1 000-row group sizes this question's shape produces (10 000 slots over
1e7 rows). Groups are independent, so this is an embarrassingly parallel
decomposition, not a new merge to prove correct.
"""
from std.algorithm import parallelize
from std.sys import info

from columnar.array import Float64Array
from columnar.batch import RecordBatch
from numeric.contract import AGG_STD
from pandas_groupby import group_std_from_variance
from query.aggregate import (
    CARDINALITY_PROBE_ROWS,
    GROUP_CODED_BAD_REQUEST,
    GROUP_CODED_KEY_NOT_A_CODE,
    GROUP_CODED_OK,
    GroupAccumulator,
    _col_guard_flags,
    planned_workers,
)
from query.packedkey import (
    GROUP_PACKED_DOMAIN_TOO_LARGE,
    MAX_PACKED_WIDTH,
    PackedDomain,
    packed_status_name,
    probe_packed_domain,
    _packed_digit,
)
from sorting import quicksort

# ── status: continuing query's 330-339 block. 337 topk_dense's, 338
#    comoments_packed's. 339 is the last free slot in this block. ──────────
comptime GROUP_MEDIAN_STATE_TOO_LARGE: Int = 339
"""The per-(band, slot) `GroupAccumulator` array, or the row-indexed scatter
scratch (`row_slot` plus the value buffer, bounded by `n_rows`), would exceed
`MEDIAN_MAX_STATE_BYTES`."""

comptime MEDIAN_MAX_STATE_BYTES: Int = 64 << 20
"""64 MiB for the (band, slot) accumulator array — `topk_dense`/
`comoments_packed`'s budget. Deliberately NOT counting the `row_slot` buffer
or the value-scatter buffer here: both are sized by `n_rows`, a caller-visible
quantity already bounded by the batch itself (rule 1c still holds — see
`median_route_ok`, which bounds the ROW-scaled scratch separately against the
resident-dataset-sized `MEDIAN_MAX_ROW_SCRATCH_BYTES` rather than pretending
one constant can bound both a slot-scaled and a row-scaled allocation)."""

comptime MEDIAN_MAX_ROW_SCRATCH_BYTES: Int = 256 << 20
"""Ceiling on `row_slot` (8 bytes/row) plus the value-scatter buffer (up to
8 bytes/row): 256 MiB caps this module's row-scaled scratch at 1.6e7 rows,
comfortably past the H2O 0.5 GB tier's 1e7."""


fn median_status_name(status: Int) -> String:
    if status == GROUP_CODED_OK:
        return "ok"
    if status == GROUP_CODED_BAD_REQUEST:
        return "bad_request"
    if status == GROUP_CODED_KEY_NOT_A_CODE:
        return "key_not_a_code"
    if status == GROUP_PACKED_DOMAIN_TOO_LARGE:
        return "domain_too_large"
    if status == GROUP_MEDIAN_STATE_TOO_LARGE:
        return "state_too_large"
    return packed_status_name(status)


fn median_state_bytes(slots: Int, workers: Int) -> Int:
    """`workers x slots` `GroupAccumulator`s, plus the per-band first-appearance
    order list and `seen` bitmap this module needs to reconstruct group order
    — the slot-scaled scratch `MEDIAN_MAX_STATE_BYTES` bounds."""
    if slots <= 0 or workers <= 0:
        return 0
    var acc_bytes = 64  # size_of[GroupAccumulator](): key,count,total,mean,m2,min,max (7 f64) + 1 bool, padded
    var payload = workers * slots * acc_bytes
    var order = workers * slots * 8
    var seen = workers * slots
    return payload + order + seen


fn median_row_scratch_bytes(n_rows: Int) -> Int:
    """`row_slot` (8 B/row) plus the value-scatter buffer (<= 8 B/row) — the
    row-scaled scratch `MEDIAN_MAX_ROW_SCRATCH_BYTES` bounds."""
    if n_rows <= 0:
        return 0
    return n_rows * 8 + n_rows * 8


fn median_route_ok(
    batch: RecordBatch, key_columns: List[Int], n_workers: Int
) -> PackedDomain:
    """`probe_packed_domain` plus BOTH this module's byte ceilings — slot-scaled
    and row-scaled are two different quantities and rule 1c requires bounding
    each, not just the one that happens to be smaller on the H2O shape."""
    var domain = probe_packed_domain(batch, key_columns, CARDINALITY_PROBE_ROWS)
    if not domain.valid():
        return domain^
    if median_row_scratch_bytes(batch.n_rows) > MEDIAN_MAX_ROW_SCRATCH_BYTES:
        return PackedDomain(GROUP_MEDIAN_STATE_TOO_LARGE)
    var bands = n_workers
    if bands < 1:
        bands = 1
    if median_state_bytes(domain.slots, bands) > MEDIAN_MAX_STATE_BYTES:
        return PackedDomain(GROUP_MEDIAN_STATE_TOO_LARGE)
    return domain^


struct MedianGroupedResult(Copyable, Movable):
    """One packed key tuple's groups, each with its median and sample sd of
    one value column. `key_tuples` is flat, `key_width` wide per group."""

    var key_tuples: List[Float64]
    var key_width: Int
    var count: List[Float64]
    var median: List[Float64]
    var present_median: List[Bool]
    var sd: List[Float64]
    var present_sd: List[Bool]
    var null_key_rows: Int

    fn __init__(
        out self,
        var key_tuples: List[Float64],
        key_width: Int,
        var count: List[Float64],
        var median: List[Float64],
        var present_median: List[Bool],
        var sd: List[Float64],
        var present_sd: List[Bool],
        null_key_rows: Int,
    ):
        self.key_tuples = key_tuples^
        self.key_width = key_width
        self.count = count^
        self.median = median^
        self.present_median = present_median^
        self.sd = sd^
        self.present_sd = present_sd^
        self.null_key_rows = null_key_rows

    fn n_groups(self) -> Int:
        if self.key_width <= 0:
            return 0
        return len(self.key_tuples) // self.key_width


fn _empty_median(width: Int) -> MedianGroupedResult:
    return MedianGroupedResult(
        List[Float64](), width, List[Float64](), List[Float64](), List[Bool](),
        List[Float64](), List[Bool](), 0,
    )


struct CodedMedianResult(Copyable, Movable):
    var status: Int
    var result: MedianGroupedResult

    fn __init__(out self, status: Int, var result: MedianGroupedResult):
        self.status = status
        self.result = result^

    fn ok(self) -> Bool:
        return self.status == GROUP_CODED_OK


fn _median_of_sorted(sorted_vals: List[Float64]) -> Float64:
    """`anomaly.median`'s formula, over an ALREADY-sorted list — the one place
    this module states the selection rule, so pass C and the hand-suite's
    naive reference cannot each spell it slightly differently."""
    var n = len(sorted_vals)
    if n == 0:
        return 0.0
    if n % 2 == 1:
        return sorted_vals[n // 2]
    return (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0


fn group_median_sd_packed(
    batch: RecordBatch, key_columns: List[Int], domain: PackedDomain, value_column: Int,
) -> CodedMedianResult:
    """`group_median_sd_packed_parallel`'s drop-in, at `planned_workers`'s
    count."""
    return group_median_sd_packed_parallel(
        batch, key_columns, domain, value_column,
        planned_workers(batch.n_rows, info.num_physical_cores()),
    )


fn group_median_sd_packed_parallel(
    batch: RecordBatch, key_columns: List[Int], domain: PackedDomain,
    value_column: Int, n_workers: Int,
) -> CodedMedianResult:
    """Grouped median and sample sd of `value_column`, packed key. See the
    module header for the three-pass shape."""
    var width = len(key_columns)
    if width < 1 or width > MAX_PACKED_WIDTH:
        return CodedMedianResult(GROUP_CODED_BAD_REQUEST, _empty_median(width))
    if not domain.valid():
        var reason = domain.status
        if reason == GROUP_CODED_OK:
            reason = GROUP_PACKED_DOMAIN_TOO_LARGE
        return CodedMedianResult(reason, _empty_median(width))
    if domain.width != width:
        return CodedMedianResult(GROUP_CODED_BAD_REQUEST, _empty_median(width))

    var n_rows = batch.n_rows
    var slots = domain.slots

    var bands = n_workers
    if bands < 1:
        bands = 1
    if bands > n_rows:
        bands = n_rows
    if bands < 1:
        bands = 1
    if median_row_scratch_bytes(n_rows) > MEDIAN_MAX_ROW_SCRATCH_BYTES:
        return CodedMedianResult(GROUP_MEDIAN_STATE_TOO_LARGE, _empty_median(width))
    if median_state_bytes(slots, bands) > MEDIAN_MAX_STATE_BYTES:
        return CodedMedianResult(GROUP_MEDIAN_STATE_TOO_LARGE, _empty_median(width))

    var key_cols = List[Float64Array]()
    for c in range(width):
        key_cols.append(batch.column(key_columns[c]))
    var value_col = batch.column(value_column)
    var value_only = List[Float64Array]()
    value_only.append(value_col.copy())
    var value_has_nulls = _col_guard_flags(value_only, n_rows)[0]
    var key_null_flags = _col_guard_flags(key_cols, n_rows)
    var any_key_nulls = False
    for c in range(width):
        if key_null_flags[c]:
            any_key_nulls = True

    # ── PASS A: guard + Welford fold + row -> slot ───────────────────────────
    var state = List[GroupAccumulator](capacity=bands * slots)
    for _ in range(bands * slots):
        state.append(GroupAccumulator(0.0))
    var statp = state.unsafe_ptr()
    var seen = List[UInt8](length=bands * slots, fill=0)
    var seenp = seen.unsafe_ptr()
    var band_orders = List[List[Int]](capacity=bands)
    for _ in range(bands):
        band_orders.append(List[Int]())
    var op_ptr = band_orders.unsafe_ptr()
    var w_nulls = List[Int](length=bands, fill=0)
    var np_ptr = w_nulls.unsafe_ptr()
    var w_bad = List[Bool](length=bands, fill=False)
    var bp_ptr = w_bad.unsafe_ptr()
    var row_slot = List[Int](length=n_rows, fill=-1)
    var rsp = row_slot.unsafe_ptr()

    var lo_f = domain.los.unsafe_ptr()
    var hi_f = domain.his.unsafe_ptr()
    var lo_i = domain.lo_ints.unsafe_ptr()
    var stride = domain.strides.unsafe_ptr()
    var band_rows = (n_rows + bands - 1) // bands
    var vp = value_col.values[].unsafe_ptr() + value_col.offset

    @parameter
    fn pass_a_worker(w: Int):
        var lo_row = w * band_rows
        var hi_row = lo_row + band_rows
        if hi_row > n_rows:
            hi_row = n_rows
        var sbase_w = w * slots
        var ebase_w = w * slots
        if lo_row >= hi_row:
            return

        var kps = List[UnsafePointer[Float64, origin=MutAnyOrigin]](capacity=width)
        for c in range(width):
            kps.append(key_cols[c].values[].unsafe_ptr() + key_cols[c].offset)
        var kp = kps.unsafe_ptr()
        var nulls = 0
        var bad = False

        @parameter
        @always_inline
        fn commit(r: Int, slot: Int):
            rsp[r] = slot
            if seenp[ebase_w + slot] == 0:
                seenp[ebase_w + slot] = 1
                op_ptr[w].append(slot)
            if not (value_has_nulls and not value_col.is_valid_at(r)):
                statp[sbase_w + slot].observe(vp[r])

        if not any_key_nulls and width == 1:
            var kp0 = kp[0]
            var lo0 = lo_f[0]
            var hi0 = hi_f[0]
            var li0 = lo_i[0]
            for r in range(lo_row, hi_row):
                var d0 = _packed_digit(kp0[r], lo0, hi0, li0)
                if d0 < 0:
                    bad = True
                    break
                commit(r, d0)
        elif not any_key_nulls and width == 2:
            var kp0 = kp[0]
            var kp1 = kp[1]
            var lo0 = lo_f[0]
            var hi0 = hi_f[0]
            var li0 = lo_i[0]
            var lo1 = lo_f[1]
            var hi1 = hi_f[1]
            var li1 = lo_i[1]
            var st1 = stride[1]
            for r in range(lo_row, hi_row):
                var d0 = _packed_digit(kp0[r], lo0, hi0, li0)
                var d1 = _packed_digit(kp1[r], lo1, hi1, li1)
                if d0 < 0 or d1 < 0:
                    bad = True
                    break
                commit(r, d0 + d1 * st1)
        else:
            for r in range(lo_row, hi_row):
                var null_key = False
                var slot = 0
                for c in range(width):
                    if any_key_nulls and not key_cols[c].is_valid_at(r):
                        null_key = True
                        break
                    var d = _packed_digit(kp[c][r], lo_f[c], hi_f[c], lo_i[c])
                    if d < 0:
                        bad = True
                        break
                    slot += d * stride[c]
                if bad:
                    break
                if null_key:
                    nulls += 1
                    continue
                commit(r, slot)
        bp_ptr[w] = bad
        np_ptr[w] = nulls

    parallelize[pass_a_worker](bands)

    for w in range(bands):
        if w_bad[w]:
            return CodedMedianResult(GROUP_CODED_KEY_NOT_A_CODE, _empty_median(width))

    var slot_to_group = List[Int](length=slots, fill=-1)
    var g_order = List[Int]()
    var null_key_rows = 0
    for w in range(bands):
        null_key_rows += w_nulls[w]
        for i in range(len(band_orders[w])):
            var slot = band_orders[w][i]
            if slot_to_group[slot] < 0:
                slot_to_group[slot] = len(g_order)
                g_order.append(slot)
    var n_groups = len(g_order)

    # ── between passes: counts -> per-slot offset, per-(worker,slot) start ──
    var slot_offset = List[Int](length=slots, fill=0)
    var running = 0
    for slot in range(slots):
        slot_offset[slot] = running
        var total = 0
        for w in range(bands):
            total += Int(statp[w * slots + slot].count)
        running += total
    var starts = List[Int](length=bands * slots, fill=0)
    for slot in range(slots):
        var acc = slot_offset[slot]
        for w in range(bands):
            starts[w * slots + slot] = acc
            acc += Int(statp[w * slots + slot].count)

    # ── PASS B: scatter v3 into one contiguous region per group ────────────
    var buffer = List[Float64](length=running, fill=0.0)
    var bufp = buffer.unsafe_ptr()
    var cursor = starts.copy()
    var curp = cursor.unsafe_ptr()

    @parameter
    fn pass_b_worker(w: Int):
        var lo_row = w * band_rows
        var hi_row = lo_row + band_rows
        if hi_row > n_rows:
            hi_row = n_rows
        var cbase = w * slots
        for r in range(lo_row, hi_row):
            var slot = rsp[r]
            if slot < 0:
                continue
            if value_has_nulls and not value_col.is_valid_at(r):
                continue
            var pos = curp[cbase + slot]
            bufp[pos] = vp[r]
            curp[cbase + slot] = pos + 1

    parallelize[pass_b_worker](bands)
    _ = len(cursor)

    # The load-bearing self-check: every (worker, slot) cursor must land
    # EXACTLY at its start plus its own count, or the scatter placed a value
    # somewhere pass C will not look — a silent wrong answer, not a crash,
    # which is why this is checked rather than trusted.
    var scatter_ok = True
    for w in range(bands):
        for slot in range(slots):
            var idx = w * slots + slot
            if cursor[idx] != starts[idx] + Int(statp[idx].count):
                scatter_ok = False
    if not scatter_ok:
        return CodedMedianResult(GROUP_MEDIAN_STATE_TOO_LARGE, _empty_median(width))

    # ── PASS C: per-group median, band-parallel over GROUP ranges ──────────
    var median_out = List[Float64](length=n_groups, fill=0.0)
    var present_out = List[Bool](length=n_groups, fill=False)
    var medp = median_out.unsafe_ptr()
    var gp = g_order.unsafe_ptr()

    var mw = bands
    if mw > n_groups:
        mw = n_groups
    if mw < 1:
        mw = 1
    var gband = (n_groups + mw - 1) // mw

    @parameter
    fn median_worker(m: Int):
        var g_lo = m * gband
        var g_hi = g_lo + gband
        if g_hi > n_groups:
            g_hi = n_groups
        for gi in range(g_lo, g_hi):
            var slot = gp[gi]
            var base = slot_offset[slot]
            var cnt = 0
            for w in range(bands):
                cnt += Int(statp[w * slots + slot].count)
            if cnt <= 0:
                continue
            var vals = List[Float64](capacity=cnt)
            for i in range(cnt):
                vals.append(bufp[base + i])
            var sorted_vals = quicksort(vals)
            medp[gi] = _median_of_sorted(sorted_vals)
            present_out[gi] = True

    parallelize[median_worker](mw)

    var key_tuples = List[Float64](capacity=n_groups * width)
    var counts_out = List[Float64](capacity=n_groups)
    var sd_out = List[Float64](capacity=n_groups)
    var present_sd_out = List[Bool](capacity=n_groups)
    for g in range(n_groups):
        var slot = g_order[g]
        for c in range(width):
            var digit = (slot // domain.strides[c]) % domain.spans[c]
            key_tuples.append(Float64(domain.lo_ints[c] + digit))
        var merged = GroupAccumulator(0.0)
        for w in range(bands):
            merged.merge_from(state[w * slots + slot])
        counts_out.append(merged.count)
        var has_sd = merged.has_answer(AGG_STD)
        sd_out.append(group_std_from_variance(merged.m2, merged.count, 1.0) if has_sd else 0.0)
        present_sd_out.append(has_sd)

    return CodedMedianResult(
        GROUP_CODED_OK,
        MedianGroupedResult(
            key_tuples^, width, counts_out^, median_out^, present_out^, sd_out^,
            present_sd_out^, null_key_rows,
        ),
    )
