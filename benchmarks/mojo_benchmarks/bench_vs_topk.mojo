"""bench_vs_topk.mojo — the Mojo arm of top-k selection vs `numpy.argpartition`.

Run it through `benchmarks/mojo_benchmarks/bench_vs_topk_driver.py`, which interleaves
this process with `bench_vs_topk_numpy.py` round by round and compares the digests. Run
alone it still prints everything except the cross-language comparison.

WHAT IS BEING COMPARED, AND WITH HOW MANY THREADS EACH
------------------------------------------------------
Four arms, and the thread count is part of the arm's name because a fraction or a ratio
that does not say which arm it was computed against is circular:

  exec_topk   `query.executor.top_k_indices` over a `RecordBatch`. 1 thread. The kernel
              a caller reaches today. Its own docstring declares `O(n*k)`, and this
              benchmark measures the constant so the loss can be extrapolated to the
              cells that are too slow to run.
  heap_1t     `query.topk.top_k_flat[buffered=False]`. 1 thread. Bounded min-heap with
              a SIMD threshold screen.
  buf_1t      `query.topk.top_k_flat[buffered=True]`. 1 thread. Same screen, but
              accepted candidates go to a 2k buffer reduced by introselect, so the cost
              per acceptance is O(1) amortised instead of O(log k). This is the arm to
              compare with `np.argpartition`: both are single-threaded.
  buf_16t     `query.topk.top_k_flat_parallel[buffered=True]` on `num_physical_cores()`.
              16 threads here. It must NOT be compared with a 1-thread NumPy call and
              called a like-for-like win; it is reported separately and labelled.

`numpy.argpartition` is introselect in C, single-threaded, and it is the right baseline:
it is what a retrieval or RAG pipeline actually calls. `bench_vs_topk_numpy.py` also
times `np.partition` (values only, no index array), which is the fastest thing NumPy can
do for this question, so nobody can say the slow NumPy entry point was chosen.

CORRECTNESS BEFORE ANY TIMING
-----------------------------
Section 1 runs before a single clock is read:

  * all four arms must return the IDENTICAL index list, not merely the same set;
  * `TOPK_DIGEST` publishes two FNV-1a-64 digests for the driver to compare against
    NumPy's — one over `(index, value_bits)` pairs in ascending index order, which is
    strict index-set identity, and one over the value bit patterns in best-first order,
    which is multiset-of-values identity;
  * `boundary_distinct` says whether the k-th and (k+1)-th best values differ. When they
    do, the top-k SET is unique and NumPy must agree on the indices too. When they do
    not, ties straddle the boundary and only the value multiset can be required to
    match, because `np.argpartition` makes no promise about which of several equal
    values it keeps. See `query/topk.mojo` on the tie rule; ours is `(value, index)`
    with the lower index winning, which is a strict total order and therefore unique.

THE DATA, AND WHY IT IS GENERATED THIS WAY
------------------------------------------
A counter-based SplitMix64 — `value[i] = f(i)`, no carried state — so `bench_vs_topk_numpy.py`
can vectorise the identical bit patterns in NumPy and both sides provably select from the
same array. Both sides print the bit pattern of element 0 and it is 4606131375998723001;
the NumPy arm fails its own gate if that number differs, because two benchmarks selecting
from two different arrays would compare nothing at all.

Every size is a PREFIX of one 100,000,000-element array rather than a fresh allocation,
which keeps the two languages consistent (NumPy slices the same prefix) and keeps the
process to one big allocation. The consequence for the cold tier is stated where it is
printed: pages are already mapped by the generator, so a per-cell COLD here is the first
call at that size, not a page-fault-inclusive process cold. The process cold is what
`benchmarks/cold_start_harness.py -K` measures across K processes, and the K belongs with
any cold figure quoted from it.

Section 4 repeats the measurement on ASCENDING input, which is this kernel's worst case
(every element beats the running threshold). A selection kernel whose cost depends on
input order must say by how much, and on that input we LOSE to `np.argpartition` — the
number is in section 4 and in the driver's summary.

THE DISPERSION GATE
-------------------
Every cell checks three things: `hot <= warm`, `median/min <= MAX_SPREAD`, and
`p90/min <= MAX_P90_SPREAD`, all across the hot units. A cell that violates any of them
prints INVALID, names EVERY condition that actually failed, and prints NO rate. A rate is
a claim; a claim from a contended measurement is worse than no claim. `max/min` is printed
on every line and deliberately not gated — see `MAX_SPREAD` for why gating a max-order
statistic gates the rep count instead of the measurement.

Note the shape of the failure message. `measure_stream_bandwidth.mojo` has a bug this
file deliberately does not copy: its 1T arm prints `"hot<=warm" if ordered else "..."`,
so when the real violation is spread it names the condition that HELD. Here the reasons
are accumulated from the checks that failed, and a cell failing two says both.

The gate PRINTS its verdict and exits 0. It does not raise, matching
`measure_stream_bandwidth.mojo` rather than `bench_streaming.mojo`, because this file is
run K times by the cold-start harness on a machine that is often contended, and a
non-zero exit there loses the output of a run whose figures are still worth aggregating.
The driver reads the gate line.
"""
from columnar.array import Float64Array, float64_from_list
from columnar.batch import RecordBatch, schema_of
from query.executor import top_k_indices
from query.topk import (
    TopKSelection,
    top_k_flat,
    top_k_flat_parallel,
)
from std.sys import info
from std.time import perf_counter_ns

# ── configuration ─────────────────────────────────────────────────────────────

comptime MAX_N: Int = 100_000_000
"""The one allocation. 800 MB of Float64; every sweep size is a prefix of it."""

comptime HOT_REPS: Int = 25
"""Timed units after the warm one. HOT is their minimum: contention can only make a
reading slower than the work takes, so the minimum is the closest available estimate of
the uncontended cost, and the dispersion across them says how contended the box was."""

comptime UNIT_FLOOR_NS: Float64 = 5_000_000.0
"""A timed UNIT repeats the call until it spans at least this long, and the unit's time
is divided by the repeat count.

`perf_counter_ns` on this host has an observed granularity of 1 us — every reading comes
back an exact multiple of 1000 — so a 14 us call is measured to 7%. Repeating removes
that, and it hides nothing: every repeat pays the full per-call cost, allocation and
thread spawn and final sort included.

THE TRAP THIS AVOIDS, found the hard way in an earlier draft of this file. If WARM is one
call and HOT is the mean of a 20 ms batch, the two are not the same statistic, and on a
loaded box the single short call is systematically LUCKIER: it can slip between
preemptions where a 20 ms window cannot. That draft reported `hot > warm` by 3.55x on a
cell where nothing was wrong, and the gate dutifully failed it. WARM and HOT are now both
per-call figures from units of the SAME repeat count, so `hot <= warm` compares like with
like. COLD stays a single call, because a cold reading averaged over a thousand calls is
not a cold reading — and it is therefore excluded from the ordering check when the repeat
count is above one, which the output says explicitly."""

comptime CELL_BUDGET_NS: Float64 = 2_000_000_000.0
"""EQUAL WALL-CLOCK PER CELL, on both sides of the comparison.

The rep count is not a constant, it is whatever fits in this budget between a floor of
`MIN_REPS` and a cap of `HOT_REPS`. `bench_vs_topk_numpy.py` applies the identical rule
with the identical constants, which is the only way the two `min` statistics are
comparable: min-of-25 is a better floor estimate than min-of-6, so handing one side more
reps than the other is a thumb on the scale. Equal time is the fair currency here because
a slow arm's whole problem is that it is slow.

The visible consequence: an arm costing 0.5 s per call gets 6 units and an arm costing
5 ms gets 25. Both numbers are printed as `reps=` so the asymmetry is auditable."""

comptime MIN_REPS: Int = 3

comptime MAX_INNER: Int = 200_000
"""Cap on the repeat count, so a pathologically fast cell cannot spin for minutes."""

comptime MAX_P90_SPREAD: Float64 = 4.0
"""Bound on P90/MIN. A second quantile so a cell where a QUARTER of the readings were
disturbed is refused even though its median looked fine. Like the median, p90 is a fixed
quantile and does not drift with the rep count."""

comptime MAX_SPREAD: Float64 = 2.0
"""Bound on MEDIAN/MIN across the hot units. Same number as
`measure_stream_bandwidth.mojo`, applied to a different statistic, and the difference is
deliberate rather than a loosening:

`max/min` is a max-order statistic. On a contended machine its expected value GROWS with
the number of reps, so a gate on it is partly a gate on `HOT_REPS` and on what the
neighbours are doing, and taking more samples — which makes the `min` strictly better —
makes the verdict strictly worse. Measured here: at load 91 the cells had `median/min`
between 1.00 and 1.46 while `max/min` ran from 10 to 52, on the same 25 readings. Those
two numbers describe the same data; only one of them is about the measurement.

So the gate is on two FIXED QUANTILES, `median/min <= MAX_SPREAD` and
`p90/min <= MAX_P90_SPREAD`, neither of which drifts with the rep count. `max/min` is
computed and PRINTED on every line, valid or not, and never gated — a reader who prefers
it can apply it, and hiding it would be the actual loosening. No cell is dropped from the
failure count and no per-cell exception exists."""

comptime EXEC_MAX_WORK: Int = 100_000_000
"""`n * k` budget for the O(n*k) executor arm. At the measured ~1.9 ns per (element*k)
this is ~0.19 s per call, so nine reps of a budgeted cell take under two seconds. Cells
past the budget are EXTRAPOLATED from the measured constant and labelled as such — an
extrapolation stated as one is honest; a missing row is not."""

comptime GOLDEN: UInt64 = 0x9E3779B97F4A7C15
comptime FNV_OFFSET: UInt64 = 0xCBF29CE484222325
comptime FNV_PRIME: UInt64 = 0x00000100000001B3


# ── data ──────────────────────────────────────────────────────────────────────


fn splitmix64(counter: UInt64) -> UInt64:
    """SplitMix64 finalizer over a COUNTER, not over carried state.

    Counter-based so `value[i]` depends on `i` alone: NumPy computes the identical bit
    patterns with three vectorised multiplies and no loop, which is what makes the
    cross-language comparison a comparison of kernels rather than of generators.
    """
    var z = counter * GOLDEN + GOLDEN
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9
    z = (z ^ (z >> 27)) * 0x94D049BB133111EB
    return z ^ (z >> 31)


fn uniform_values(n: Int) -> List[Float64]:
    """`n` uniform Float64 in [0, 1). 53 bits of mantissa from the top 53 output bits."""
    var out = List[Float64](capacity=n)
    for i in range(n):
        out.append(Float64(splitmix64(UInt64(i)) >> 11) * (1.0 / 9007199254740992.0))
    return out^


fn ascending_values(n: Int) -> List[Float64]:
    """The adversarial order: every element beats the running threshold."""
    var out = List[Float64](capacity=n)
    for i in range(n):
        out.append(Float64(i))
    return out^


fn reps_for(unit_ns: Float64) -> Int:
    """Units that fit in `CELL_BUDGET_NS`, clamped to [`MIN_REPS`, `HOT_REPS`]."""
    if unit_ns <= 0.0:
        return HOT_REPS
    var want = Int(CELL_BUDGET_NS / unit_ns)
    if want < MIN_REPS:
        return MIN_REPS
    if want > HOT_REPS:
        return HOT_REPS
    return want


fn batch_size(pilot_ns: Float64) -> Int:
    """Repeats needed for one timed unit to span `UNIT_FLOOR_NS`, from the cold reading.

    The cold reading OVERSTATES the steady-state cost, so this understates the repeat
    count — which is the safe direction: a unit that comes out longer than the floor is
    fine, one that comes out shorter is back inside the clock's resolution.
    """
    if pilot_ns <= 0.0:
        return MAX_INNER
    var want = Int(UNIT_FLOOR_NS / pilot_ns) + 1
    if want < 1:
        return 1
    if want > MAX_INNER:
        return MAX_INNER
    return want


# ── digests ───────────────────────────────────────────────────────────────────


@always_inline
fn _fnv_bytes(h: UInt64, v: UInt64) -> UInt64:
    var acc = h
    for b in range(8):
        acc = (acc ^ ((v >> (UInt64(b) * 8)) & 0xFF)) * FNV_PRIME
    return acc


fn pair_digest(indices: List[Int], values: List[Float64]) -> UInt64:
    """FNV-1a-64 over `(index, value_bits)` in ASCENDING INDEX order.

    Ascending index order rather than the returned order, so the digest is a property of
    the SET. Two implementations that pick the same rows agree here whatever order they
    emit them in, which is the comparison the task actually needs.
    """
    var sorted_idx = indices.copy()
    for i in range(1, len(sorted_idx)):
        var v = sorted_idx[i]
        var j = i - 1
        while j >= 0 and sorted_idx[j] > v:
            sorted_idx[j + 1] = sorted_idx[j]
            j -= 1
        sorted_idx[j + 1] = v
    var h = FNV_OFFSET
    for i in range(len(sorted_idx)):
        var at = sorted_idx[i]
        h = _fnv_bytes(h, UInt64(at))
        h = _fnv_bytes(h, values[at].to_bits[DType.uint64]())
    return h


fn value_digest(indices: List[Int], values: List[Float64]) -> UInt64:
    """FNV-1a-64 over the value BIT PATTERNS in the returned (best-first) order.

    Order-independent among ties, because tied values have identical bits. So this is a
    multiset comparison, and it is the only correctness claim that survives when ties
    straddle the k-boundary and two implementations legitimately keep different rows.
    """
    var h = FNV_OFFSET
    for i in range(len(indices)):
        h = _fnv_bytes(h, values[indices[i]].to_bits[DType.uint64]())
    return h


fn same_list(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


# ── timing ────────────────────────────────────────────────────────────────────


struct Cell(Copyable, Movable):
    """One (arm, n, k) measurement, and whether it may be quoted."""

    var cold: Float64
    var warm: Float64
    var hot: Float64
    var spread_med: Float64
    var spread_p90: Float64
    var spread_max: Float64
    var valid: Bool
    var reason: String
    var inner: Int
    var reps: Int

    fn __init__(
        out self,
        cold: Float64,
        warm: Float64,
        hot: Float64,
        spread_med: Float64,
        spread_p90: Float64,
        spread_max: Float64,
        var reason: String,
        valid: Bool,
        inner: Int,
        reps: Int,
    ):
        self.cold = cold
        self.warm = warm
        self.hot = hot
        self.spread_med = spread_med
        self.spread_p90 = spread_p90
        self.spread_max = spread_max
        self.valid = valid
        self.reason = reason^
        self.inner = inner
        self.reps = reps


fn judge(cold: Float64, warm: Float64, var units: List[Float64], inner: Int) -> Cell:
    """Apply the dispersion gate. EVERY failing condition is named, never one that held.

    That last clause is not decoration. `measure_stream_bandwidth.mojo`'s 1T arm prints
    `"hot<=warm" if ordered else "hot > warm (...)"` for a failure that may have been
    caused by spread alone, so it names the condition that HELD; a reader parsing gate
    strings reads the wrong cause. Here the reasons are accumulated from the checks that
    actually failed, and a cell that fails two says both.
    """
    for i in range(1, len(units)):
        var v = units[i]
        var j = i - 1
        while j >= 0 and units[j] > v:
            units[j + 1] = units[j]
            j -= 1
        units[j + 1] = v
    var count = len(units)
    var hot = units[0]
    var worst = units[count - 1]
    var median = units[count // 2]
    var p90_at = (count * 9) // 10
    if p90_at >= count:
        p90_at = count - 1
    var p90 = units[p90_at]
    var spread_med = median / hot if hot > 0.0 else 0.0
    var spread_p90 = p90 / hot if hot > 0.0 else 0.0
    var spread_max = worst / hot if hot > 0.0 else 0.0

    var reason = String("")
    if hot <= 0.0:
        reason += "hot<=0(below clock resolution)"
    if hot > warm:
        if reason.byte_length() > 0:
            reason += "+"
        reason += "hot>warm(" + String(hot / warm) + "x)"
    if spread_med > MAX_SPREAD:
        if reason.byte_length() > 0:
            reason += "+"
        reason += "median/min=" + String(spread_med) + ">" + String(MAX_SPREAD)
    if spread_p90 > MAX_P90_SPREAD:
        if reason.byte_length() > 0:
            reason += "+"
        reason += "p90/min=" + String(spread_p90) + ">" + String(MAX_P90_SPREAD)
    var ok = reason.byte_length() == 0
    return Cell(
        cold, warm, hot, spread_med, spread_p90, spread_max, reason^, ok, inner, count
    )


fn report(mut failures: Int, arm: String, n: Int, k: Int, cell: Cell, candidates: Int):
    """One machine-readable line per cell. INVALID lines carry no rate, by design."""
    var head = "TOPK " + arm + " n=" + String(n) + " k=" + String(k)
    var common = (
        " cold_ns=" + String(cell.cold)
        + " warm_ns=" + String(cell.warm)
        + " hot_ns=" + String(cell.hot)
        + " spread_med=" + String(cell.spread_med)
        + " spread_p90=" + String(cell.spread_p90)
        + " spread_max=" + String(cell.spread_max)
        + " inner_reps=" + String(cell.inner)
        + " reps=" + String(cell.reps)
    )
    if not cell.valid:
        failures += 1
        print(head + " INVALID reasons=" + cell.reason + common + " ; no rate reported")
        return
    print(
        head + common,
        "ns_per_elem=" + String(cell.hot / Float64(n)),
        "elems_per_s=" + String(Float64(n) / (cell.hot / 1.0e9)),
        "gb_per_s=" + String(8.0 * Float64(n) / cell.hot),
        "cand=" + String(candidates),
        "VALID",
    )
    print(
        "COLD_WARM_HOT topk." + arm + ".n" + String(n) + ".k" + String(k),
        cell.cold,
        cell.warm,
        cell.hot,
        "ns",
    )


# ── the arms ──────────────────────────────────────────────────────────────────
#
# Each returns (indices, candidate count) and is timed by the same driver loop below, so
# no arm can accidentally be given a different rep schedule from another.


fn time_flat[buffered: Bool](
    values: List[Float64],
    n: Int,
    k: Int,
    mut out_indices: List[Int],
    mut cand: Int,
    mut sink: Int,
) -> Cell:
    """COLD = call one, alone. WARM and HOT = per-call figures from equal-sized units."""
    var t0 = perf_counter_ns()
    var r0 = top_k_flat[True, buffered](values, n, k)
    var t1 = perf_counter_ns()
    var cold = Float64(Int(t1 - t0))
    out_indices = r0.indices.copy()
    cand = r0.candidates
    sink += r0.indices[0]
    var inner = batch_size(cold)

    var t2 = perf_counter_ns()
    for _ in range(inner):
        var rw = top_k_flat[True, buffered](values, n, k)
        sink += rw.indices[0]
    var t3 = perf_counter_ns()
    var unit_ns = Float64(Int(t3 - t2))
    var warm = unit_ns / Float64(inner)
    var reps = reps_for(unit_ns)

    var units = List[Float64](capacity=reps)
    for _ in range(reps):
        var b0 = perf_counter_ns()
        for _ in range(inner):
            var r = top_k_flat[True, buffered](values, n, k)
            sink += r.indices[0]
        var b1 = perf_counter_ns()
        units.append(Float64(Int(b1 - b0)) / Float64(inner))
    return judge(cold, warm, units^, inner)


fn time_parallel[buffered: Bool](
    values: List[Float64],
    n: Int,
    k: Int,
    workers: Int,
    mut out_indices: List[Int],
    mut cand: Int,
    mut sink: Int,
) -> Cell:
    var t0 = perf_counter_ns()
    var r0 = top_k_flat_parallel[True, buffered](values, n, k, workers)
    var t1 = perf_counter_ns()
    var cold = Float64(Int(t1 - t0))
    out_indices = r0.indices.copy()
    cand = r0.candidates
    sink += r0.indices[0]
    var inner = batch_size(cold)

    var t2 = perf_counter_ns()
    for _ in range(inner):
        var rw = top_k_flat_parallel[True, buffered](values, n, k, workers)
        sink += rw.indices[0]
    var t3 = perf_counter_ns()
    var unit_ns = Float64(Int(t3 - t2))
    var warm = unit_ns / Float64(inner)
    var reps = reps_for(unit_ns)

    var units = List[Float64](capacity=reps)
    for _ in range(reps):
        var b0 = perf_counter_ns()
        for _ in range(inner):
            var r = top_k_flat_parallel[True, buffered](values, n, k, workers)
            sink += r.indices[0]
        var b1 = perf_counter_ns()
        units.append(Float64(Int(b1 - b0)) / Float64(inner))
    return judge(cold, warm, units^, inner)


fn time_executor(
    batch: RecordBatch, k: Int, mut out_indices: List[Int], mut sink: Int
) -> Cell:
    """The existing `query.executor` path, under the same equal-time rule as every other
    arm. It is `O(n*k)`, so the budget buys it `MIN_REPS` units where a fast arm gets
    `HOT_REPS`; both counts are printed."""
    var t0 = perf_counter_ns()
    var r0 = top_k_indices(batch, 0, k, True, True)
    var t1 = perf_counter_ns()
    var cold = Float64(Int(t1 - t0))
    out_indices = r0.copy()
    sink += r0[0]
    var inner = batch_size(cold)

    var t2 = perf_counter_ns()
    for _ in range(inner):
        var rw = top_k_indices(batch, 0, k, True, True)
        sink += rw[0]
    var t3 = perf_counter_ns()
    var unit_ns = Float64(Int(t3 - t2))
    var warm = unit_ns / Float64(inner)
    var reps = reps_for(unit_ns)

    var units = List[Float64](capacity=reps)
    for _ in range(reps):
        var b0 = perf_counter_ns()
        for _ in range(inner):
            var r = top_k_indices(batch, 0, k, True, True)
            sink += r[0]
        var b1 = perf_counter_ns()
        units.append(Float64(Int(b1 - b0)) / Float64(inner))
    return judge(cold, warm, units^, inner)


fn build_batch(values: List[Float64], n: Int) -> RecordBatch:
    """A one-column `RecordBatch` over the prefix, built OUTSIDE every timed region.

    The copy and the validity bitmap are a real cost of the executor path and they are
    excluded here — a favour TO the arm we are about to beat, which is the only direction
    a favour may go.
    """
    var prefix = List[Float64](capacity=n)
    for i in range(n):
        prefix.append(values[i])
    var cols = List[Float64Array]()
    cols.append(float64_from_list(prefix^))
    var names = List[String]()
    names.append(String("score"))
    return RecordBatch(schema_of(names^), cols^, n)


# ── main ──────────────────────────────────────────────────────────────────────


fn main():
    var workers = info.num_physical_cores()
    var failures = 0
    # Consumed at the end so no timed call can be eliminated as dead code.
    var sink = 0

    print("== top-k selection: Algenta vs numpy.argpartition (Mojo arm) ==")
    print("  physical cores", workers, "| SIMD screen width 8 Float64 | HOT = min of", HOT_REPS)
    print("  data: counter-based SplitMix64, uniform [0,1), one", MAX_N, "element array;")
    print("  every sweep size is a PREFIX of it, so NumPy selects from identical bits.")
    print(
        "CONSTANTS", "HOT_REPS=" + String(HOT_REPS), "MIN_REPS=" + String(MIN_REPS),
        "UNIT_FLOOR_NS=" + String(UNIT_FLOOR_NS),
        "CELL_BUDGET_NS=" + String(CELL_BUDGET_NS),
        "MAX_SPREAD=" + String(MAX_SPREAD),
        "MAX_P90_SPREAD=" + String(MAX_P90_SPREAD),
        "MAX_N=" + String(MAX_N),
        "cores=" + String(workers),
    )
    print("  COLD here = first call at this (arm, n, k) in this process. Pages are")
    print("  already mapped by the generator, so it is NOT a page-fault-inclusive cold;")
    print("  that one is benchmarks/cold_start_harness.py -K, and K belongs with it.")

    var gen0 = perf_counter_ns()
    var values = uniform_values(MAX_N)
    var gen1 = perf_counter_ns()
    print(
        "  generated", MAX_N, "values in", Float64(Int(gen1 - gen0)) / 1.0e6, "ms",
        "(untimed setup, and NumPy pays its own)",
    )
    print("")

    # ── 1. correctness, before any clock is read ──────────────────────────────
    print("-- 1. CORRECTNESS (all four arms, then the digests NumPy must match) --")
    var agree_failures = 0
    for n in [100_000, 1_000_000]:
        for k in [10, 100, 1000]:
            var a_heap = top_k_flat[True, False](values, n, k)
            var a_buf = top_k_flat[True, True](values, n, k)
            var a_par = top_k_flat_parallel[True, True](values, n, k, workers)
            var a_par_h = top_k_flat_parallel[True, False](values, n, k, workers)
            var batch = build_batch(values, n)
            var a_exec = top_k_indices(batch, 0, k, True, True)
            var ok = (
                same_list(a_heap.indices, a_buf.indices)
                and same_list(a_heap.indices, a_par.indices)
                and same_list(a_heap.indices, a_par_h.indices)
                and same_list(a_heap.indices, a_exec)
            )
            if not ok:
                agree_failures += 1
            print(
                "  n=" + String(n),
                "k=" + String(k),
                "exec==heap_1t==buf_1t==buf_16t==heap_16t:",
                "IDENTICAL LIST" if ok else "*** DISAGREE ***",
            )
            print(
                "TOPK_XCHECK n=" + String(n),
                "k=" + String(k),
                "all_arms_identical=" + ("1" if ok else "0"),
            )
    if agree_failures != 0:
        failures += agree_failures

    # Worker-count invariance: the parallel result must be the same LIST at every count,
    # which is the property the (value, index) total order buys and the reason no merge
    # race can change the answer.
    var invariance_ok = True
    var reference = top_k_flat[True, True](values, 4_000_000, 100)
    for w in [1, 2, 3, 5, 8, 13, 16, 31]:
        var r = top_k_flat_parallel[True, True](values, 4_000_000, 100, w)
        if not same_list(reference.indices, r.indices):
            invariance_ok = False
    if not invariance_ok:
        failures += 1
    print(
        "  worker-count invariance at n=4,000,000 k=100 over w in {1,2,3,5,8,13,16,31}:",
        "IDENTICAL LIST at every count" if invariance_ok else "*** VARIES WITH w ***",
    )

    # Digests for the driver, plus whether the k-boundary is tie-free.
    for n in [100_000, 1_000_000, 10_000_000, 100_000_000]:
        for k in [10, 100, 1000]:
            var sel = top_k_flat[True, True](values, n, k)
            var plus = top_k_flat[True, True](values, n, k + 1)
            var kth = values[sel.indices[k - 1]]
            var next_best = values[plus.indices[k]]
            var distinct = kth != next_best
            print(
                "TOPK_DIGEST n=" + String(n),
                "k=" + String(k),
                "pair=" + String(pair_digest(sel.indices, values)),
                "vals=" + String(value_digest(sel.indices, values)),
                "kth_bits=" + String(kth.to_bits[DType.uint64]()),
                "boundary_distinct=" + ("1" if distinct else "0"),
            )
    print("")

    # ── 2. the sweep ──────────────────────────────────────────────────────────
    print("-- 2. SWEEP: n = 1e5 .. 1e8, k = 10/100/1000, uniform random order --")
    print("   exec_topk = query.executor.top_k_indices (1T, O(n*k), the kernel today)")
    print("   heap_1t / buf_1t = query.topk.top_k_flat (1T) -- compare THESE with NumPy")
    print("   buf_16t = query.topk.top_k_flat_parallel on", workers, "threads (NOT 1T)")
    var exec_ns_per_work = 0.0
    var exec_samples = 0
    for n in [100_000, 1_000_000, 10_000_000, 100_000_000]:
        var have_batch = n * 10 <= EXEC_MAX_WORK
        var batch = build_batch(values, n if have_batch else 1)
        for k in [10, 100, 1000]:
            var idx_heap = List[Int]()
            var idx_buf = List[Int]()
            var idx_par = List[Int]()
            var c_heap = 0
            var c_buf = 0
            var c_par = 0
            var cell_heap = time_flat[False](values, n, k, idx_heap, c_heap, sink)
            var cell_buf = time_flat[True](values, n, k, idx_buf, c_buf, sink)
            var cell_par = time_parallel[True](
                values, n, k, workers, idx_par, c_par, sink
            )

            if have_batch and n * k <= EXEC_MAX_WORK:
                var idx_exec = List[Int]()
                var cell_exec = time_executor(batch, k, idx_exec, sink)
                if not same_list(idx_exec, idx_buf):
                    failures += 1
                    print("  *** exec_topk disagrees with buf_1t at n=", n, "k=", k)
                if cell_exec.valid:
                    exec_ns_per_work += cell_exec.hot / (Float64(n) * Float64(k))
                    exec_samples += 1
                report(failures, String("exec_topk"), n, k, cell_exec, 0)
            else:
                print(
                    "TOPK exec_topk n=" + String(n),
                    "k=" + String(k),
                    "SKIPPED over_budget n*k=" + String(n * k),
                    "> EXEC_MAX_WORK=" + String(EXEC_MAX_WORK),
                    "; see the EXTRAPOLATED line below",
                )

            if not same_list(idx_heap, idx_buf) or not same_list(idx_heap, idx_par):
                failures += 1
                print("  *** arms disagree at n=", n, "k=", k)
            report(failures, String("heap_1t"), n, k, cell_heap, c_heap)
            report(failures, String("buf_1t"), n, k, cell_buf, c_buf)
            report(failures, String("buf_16t"), n, k, cell_par, c_par)
    if exec_samples > 0:
        var per_work = exec_ns_per_work / Float64(exec_samples)
        print(
            "  exec_topk measured constant:", per_work, "ns per (element * k), from",
            exec_samples, "valid cells. EXTRAPOLATED, not measured:",
        )
        for n in [10_000_000, 100_000_000]:
            for k in [100, 1000]:
                print(
                    "TOPK_EXTRAPOLATED exec_topk n=" + String(n),
                    "k=" + String(k),
                    "ns=" + String(per_work * Float64(n) * Float64(k)),
                    "seconds=" + String(per_work * Float64(n) * Float64(k) / 1.0e9),
                )
    print("")

    # ── 3. the sequential -> parallel crossover ───────────────────────────────
    print("-- 3. CROSSOVER: where does", workers, "threads start beating one? k=100 --")
    print("   Below the crossover the parallel path is SLOWER. Both halves are the result.")
    var crossover_at = 0
    for shift in range(14, 28):
        var n = 1 << shift
        if n > MAX_N:
            break
        var idx_s = List[Int]()
        var idx_p = List[Int]()
        var c_s = 0
        var c_p = 0
        var cs = time_flat[True](values, n, 100, idx_s, c_s, sink)
        var cp = time_parallel[True](values, n, 100, workers, idx_p, c_p, sink)
        if not cs.valid or not cp.valid:
            failures += 1
            print(
                "TOPK_CROSSOVER n=" + String(n),
                "INVALID seq=" + (cs.reason if not cs.valid else "ok"),
                "par=" + (cp.reason if not cp.valid else "ok"),
                "; no ratio reported",
            )
            continue
        var speedup = cs.hot / cp.hot
        if speedup >= 1.0 and crossover_at == 0:
            crossover_at = n
        print(
            "TOPK_CROSSOVER n=" + String(n),
            "seq_ns_per_elem=" + String(cs.hot / Float64(n)),
            "par_ns_per_elem=" + String(cp.hot / Float64(n)),
            "speedup=" + String(speedup),
            "par_gb_per_s=" + String(8.0 * Float64(n) / cp.hot),
        )
    if crossover_at > 0:
        print("  CROSSOVER: 16 threads first beat 1 thread at n =", crossover_at)
    else:
        print("  CROSSOVER: not reached inside the swept range under this load")
    print("")

    # ── 4. input-order sensitivity: our worst case ────────────────────────────
    print("-- 4. ADVERSARIAL ORDER: ascending input, n = 10,000,000 --")
    print("   Every element beats the running threshold, so the screen never rejects.")
    print("   This is where we LOSE to np.argpartition; the driver quantifies by how much.")
    var asc = ascending_values(10_000_000)
    for k in [10, 100, 1000]:
        var i1 = List[Int]()
        var i2 = List[Int]()
        var i3 = List[Int]()
        var i4 = List[Int]()
        var c1 = 0
        var c2 = 0
        var c3 = 0
        var c4 = 0
        var h1 = time_flat[False](asc, 10_000_000, k, i1, c1, sink)
        var h2 = time_flat[True](asc, 10_000_000, k, i2, c2, sink)
        var h3 = time_parallel[False](asc, 10_000_000, k, workers, i3, c3, sink)
        var h4 = time_parallel[True](asc, 10_000_000, k, workers, i4, c4, sink)
        if not same_list(i1, i2) or not same_list(i1, i3) or not same_list(i1, i4):
            failures += 1
            print("  *** arms disagree on ascending input at k=", k)
        report(failures, String("asc_heap_1t"), 10_000_000, k, h1, c1)
        report(failures, String("asc_buf_1t"), 10_000_000, k, h2, c2)
        report(failures, String("asc_heap_16t"), 10_000_000, k, h3, c3)
        report(failures, String("asc_buf_16t"), 10_000_000, k, h4, c4)
        if h1.valid and h2.valid:
            print(
                "  k=" + String(k),
                "the 2k buffer buys", h1.hot / h2.hot, "x on 1 thread;",
                "candidates accepted:", c1, "of 10,000,000 (the worst case, by design)",
            )
    print("")

    # Keep the arrays and every timed result observably alive, so nothing above can be
    # eliminated as dead code and reported as infinitely fast.
    var alive = values[0] + values[MAX_N - 1] + asc[0]
    if alive != alive or sink < 0:
        print("  checksum is impossible here:", alive, sink)

    if failures == 0:
        print("BENCH_GATE topk_mojo PASS")
    else:
        print("BENCH_GATE topk_mojo FAIL " + String(failures))
