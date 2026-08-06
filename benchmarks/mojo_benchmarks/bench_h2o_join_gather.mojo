"""bench_h2o_join_gather.mojo — isolated benchmark for `query.join`'s materialize gather.

Update #3 (`benchmarks/h2o_join/RESULTS.md`) diagnosed `materialize`'s per-column
gather (`_take_column_join` -> `columnar.batch.take_column`) as 70-90% of the
REMAINING Polars gap on q1-q4 after the probe/build/per-row fixes already shipped.
That diagnosis was never followed up with an attempt at a genuinely different gather
loop shape -- this harness isolates the gather ALONE (no build, no probe, no hash) at
H2O join-track output sizes, so a candidate rewrite can be measured against the
current scalar loop with nothing else in the way.

`take_column`'s job: for each output row, read a (possibly out-of-order, possibly
duplicate, possibly out-of-range) source row index and either copy the source cell
(value + validity) or write a null. On real hardware without a gather instruction
(this host, Apple Silicon: confirmed no HW SIMD gather earlier in this file's own
history -- ARM has no `vpgatherqd`-equivalent), the VALUE READ itself cannot be
vectorized into one wide load; what CAN plausibly change is the per-row branch
(bounds check + validity bit test + if/else) -- a branchless, arithmetic version of
the same predicate is the candidate this harness measures against the current
if/else scalar loop, not a claim that this becomes a true SIMD gather.

Result (see `benchmarks/h2o_join/RESULTS.md`'s Update #7 for the full writeup):
branchless is a real, reproducible 1.15x-1.20x win in the SERIAL loop, but a real,
reproducible 0.95x-0.97x REGRESSION in the PARALLEL one -- which is the one that
actually runs at H2O join-track sizes. Kept as a measured, disclosed negative result
and NOT wired into `_take_column_join`; do not re-attempt without a new idea, this
one is closed.
"""
from std.algorithm.functional import parallelize
from std.sys import info
from std.time import perf_counter_ns

from columnar.array import Float64Array, float64_from_list, float64_with_nulls
from columnar.batch import take_column
from query.join import _take_column_join

comptime N_SOURCE: Int = 10_000_000
comptime N_OUTPUT: Int = 9_000_000
comptime REPS: Int = 5


def _xorshift_next(state: UInt64) -> UInt64:
    var s = state
    s = s ^ (s << 13)
    s = s ^ (s >> 7)
    s = s ^ (s << 17)
    return s


def _build_source(n: Int, null_every: Int, seed: Int) -> Float64Array:
    var values = List[Float64](capacity=n)
    var mask = List[Bool](capacity=n)
    for i in range(n):
        if null_every > 0 and i % null_every == 0:
            values.append(0.0)
            mask.append(False)
        else:
            values.append(Float64(i) * 1.0000001)
            mask.append(True)
    _ = seed
    return float64_with_nulls(values^, mask)


def _build_indices(n_output: Int, n_source: Int, unmatched_every: Int, seed: Int) -> List[Int]:
    """A realistic gather index list: mostly valid, permuted (not sequential -- a
    join's output order tracks the LEFT side, not the right side's storage order),
    with a periodic NO_ROW (-1) standing in for an unmatched row, exactly the shape
    `materialize` actually gathers over."""
    var out = List[Int](capacity=n_output)
    var state = UInt64(seed) + 1
    for i in range(n_output):
        if unmatched_every > 0 and i % unmatched_every == 0:
            out.append(-1)
            continue
        state = _xorshift_next(state)
        out.append(Int(state % UInt64(n_source)))
    return out^


def _take_column_branchless(source: Float64Array, indices: List[Int]) -> Float64Array:
    """Same contract as `take_column`, branchless per row: compute validity via
    arithmetic (no `if`), always perform a clamped read (never an out-of-bounds one),
    and mask the value to 0.0 when invalid AFTER the read rather than skipping the
    read -- trading "a branch that is right ~50%+ of the time on scattered indices"
    for "always the same handful of arithmetic ops, no misprediction possible."
    """
    var n = len(indices)
    var values = List[Float64](length=n, fill=0.0)
    var mask = List[Bool](length=n, fill=False)
    var vp = values.unsafe_ptr()
    var src_len = source.length
    for i in range(n):
        var index = indices[i]
        var in_range = index >= 0 and index < src_len
        # Clamp so the read is always safe, whether or not `in_range` -- reading
        # index 0 on an out-of-range request is discarded by the mask below, never
        # observed, so clamping introduces no wrong answer, only a safe dummy read.
        var clamped = index if in_range else 0
        var valid_bit = in_range and source.is_valid_at(clamped)
        vp[i] = source.get_unchecked(clamped) if valid_bit else 0.0
        mask[i] = valid_bit
    return float64_with_nulls(values^, mask)


def _take_column_branchless_parallel(source: Float64Array, indices: List[Int], workers: Int) -> Float64Array:
    """`_take_column_join`'s exact row-band parallel shape, branchless body -- the
    real comparison that matters, since H2O join-track output sizes (9-10M rows) run
    the PARALLEL gather in production, never the plain serial one."""
    var n = len(indices)
    var values = List[Float64](length=n, fill=0.0)
    var mask = List[Bool](length=n, fill=False)
    var vp = values.unsafe_ptr()
    var mp = mask.unsafe_ptr()
    var ip = indices.unsafe_ptr()
    var band = (n + workers - 1) // workers
    var src_len = source.length

    @parameter
    def gather_worker(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n:
            hi = n
        for i in range(lo, hi):
            var index = ip[i]
            var in_range = index >= 0 and index < src_len
            var clamped = index if in_range else 0
            var valid_bit = in_range and source.is_valid_at(clamped)
            vp[i] = source.get_unchecked(clamped) if valid_bit else 0.0
            mp[i] = valid_bit

    parallelize[gather_worker](workers)
    _ = len(indices)
    return float64_with_nulls(values^, mask)


def main() raises:
    print("=== H2O join materialize gather, isolated (no build/probe/hash) ===")

    var source = _build_source(N_SOURCE, 97, 11)
    var indices = _build_indices(N_OUTPUT, N_SOURCE, 131, 22)
    print("  source rows=" + String(N_SOURCE) + " output rows=" + String(N_OUTPUT))
    print("")

    # ── correctness: branchless must match the scalar reference row for row ────────
    var reference = take_column(source, indices)
    var candidate = _take_column_branchless(source, indices)
    var ok = reference.length == candidate.length
    if ok:
        for i in range(reference.length):
            if reference.is_valid_at(i) != candidate.is_valid_at(i):
                ok = False
                print("  mismatch at " + String(i) + ": validity differs")
                break
            if reference.is_valid_at(i) and reference.get(i) != candidate.get(i):
                ok = False
                print("  mismatch at " + String(i) + ": value differs")
                break
    if not ok:
        raise Error("branchless gather does not match the serial reference -- not trustworthy, do not benchmark further")
    print("  correctness: branchless gather matches the serial reference row for row. OK.")
    print("")

    # ── timing: current scalar take_column vs the branchless candidate ─────────────
    var best_scalar = 1e30
    for rep in range(REPS):
        var t0 = perf_counter_ns()
        var result = take_column(source, indices)
        var t1 = perf_counter_ns()
        var elapsed = Float64(Int(t1 - t0)) / 1e9
        if elapsed < best_scalar:
            best_scalar = elapsed
        if rep == 0:
            print("  scalar (current) rows=" + String(result.length))
    print("  scalar take_column (current):  min=" + String(best_scalar) + "s")

    var best_branchless = 1e30
    for rep in range(REPS):
        var t0 = perf_counter_ns()
        var result = _take_column_branchless(source, indices)
        var t1 = perf_counter_ns()
        var elapsed = Float64(Int(t1 - t0)) / 1e9
        if elapsed < best_branchless:
            best_branchless = elapsed
        if rep == 0:
            print("  branchless rows=" + String(result.length))
    print("  branchless gather (candidate): min=" + String(best_branchless) + "s")

    var speedup = best_scalar / best_branchless
    print("")
    print(
        "  branchless vs scalar (serial):    " + String(speedup) + "x"
        + (" (branchless faster)" if speedup > 1.0 else " (branchless SLOWER)")
    )
    print("")

    # ── the comparison that actually matters: PARALLEL, at H2O join scale ──────────
    var workers = info.num_physical_cores()
    if workers < 1:
        workers = 1
    print("  === parallel gather (workers=" + String(workers) + ", real H2O join scale) ===")

    var parallel_reference = _take_column_join(source, indices)
    var parallel_candidate = _take_column_branchless_parallel(source, indices, workers)
    var parallel_ok = parallel_reference.length == parallel_candidate.length
    if parallel_ok:
        for i in range(parallel_reference.length):
            if parallel_reference.is_valid_at(i) != parallel_candidate.is_valid_at(i):
                parallel_ok = False
                break
            if parallel_reference.is_valid_at(i) and parallel_reference.get(i) != parallel_candidate.get(i):
                parallel_ok = False
                break
    if not parallel_ok:
        raise Error("parallel branchless gather does not match _take_column_join row for row -- not trustworthy")
    print("  correctness: parallel branchless gather matches _take_column_join row for row. OK.")

    var best_parallel_scalar = 1e30
    for rep in range(REPS):
        var t0 = perf_counter_ns()
        var result = _take_column_join(source, indices)
        var t1 = perf_counter_ns()
        var elapsed = Float64(Int(t1 - t0)) / 1e9
        if elapsed < best_parallel_scalar:
            best_parallel_scalar = elapsed
        if rep == 0:
            print("  parallel scalar (current) rows=" + String(result.length))
    print("  parallel scalar _take_column_join (current):  min=" + String(best_parallel_scalar) + "s")

    var best_parallel_branchless = 1e30
    for rep in range(REPS):
        var t0 = perf_counter_ns()
        var result = _take_column_branchless_parallel(source, indices, workers)
        var t1 = perf_counter_ns()
        var elapsed = Float64(Int(t1 - t0)) / 1e9
        if elapsed < best_parallel_branchless:
            best_parallel_branchless = elapsed
        if rep == 0:
            print("  parallel branchless rows=" + String(result.length))
    print("  parallel branchless gather (candidate):        min=" + String(best_parallel_branchless) + "s")

    var parallel_speedup = best_parallel_scalar / best_parallel_branchless
    print("")
    print(
        "  branchless vs scalar (parallel):  " + String(parallel_speedup) + "x"
        + (" (branchless faster)" if parallel_speedup > 1.0 else " (branchless SLOWER)")
    )
