"""bench_vs_pearsonr.mojo — `stat_tests.pearson_r` against `scipy.stats.pearsonr` (Mojo arm).

Run through `benchmarks/mojo_benchmarks/bench_vs_pearsonr_driver.py`, which interleaves
this process with `bench_vs_pearsonr_scipy.py` round by round and compares the outputs.
Run alone it still prints everything except the cross-language comparison.

WHY `pearson_r`, AND NOT ONE OF THE OTHER TEN FUNCTIONS IN THIS MODULE
-----------------------------------------------------------------------
`stat_tests.mojo` exports 11 public functions. Most of them (`ks_test_2sample`,
`ks_test_normal`, `anderson_darling_normal`, `shapiro_wilk_approx`, `spearman_r`) sort
their input with a hand-written O(n^2) insertion sort (`_insertion_sort` / `_rank`), so a
sweep into the range where "Mojo vs Python" is actually interesting (n in the hundreds of
thousands or millions) would be dominated by that algorithmic choice rather than by the
per-element cost of the statistic itself -- a real, closeable gap, but a different
investigation from this one. `pearson_r` is the one O(n), single-pass function in the
module: one pass to accumulate `sxy`, `sxx`, `syy` against the running means, no sort, no
O(n^2) anywhere in its call graph. That makes it the fair, apples-to-apples comparison for
a wide sweep.

CORRECTNESS BEFORE ANY TIMING, ON TWO SEPARATE AXES
----------------------------------------------------------------------
Both axes are checked by the driver, not hidden by this file, because they come out
DIFFERENTLY:

  r        Both sides compute the identical `cov(x,y) / sqrt(var(x)*var(y))` in IEEE-754
           double. Expected to match scipy to close to machine epsilon; the driver's gate
           is rtol 1e-9, far looser than what is actually measured, specifically so that
           legitimate summation-order noise cannot trip it.

  p_value  `pearson_r`'s p-value is computed from `_t_cdf`, which is built on
           `_regularized_incomplete_beta`. That function USED TO be independently verified
           (against `scipy.special.betainc`, not against this benchmark) to be WRONG for
           common inputs: `betainc(4,4,0.5)` had to be 0.5 by symmetry and the frozen
           implementation returned -0.099. It is fixed as of this session (see
           `mojo/engine/stat_tests.mojo`'s `_betacf` and `inference.core`'s module
           docstring for the history), and `pearson_r`'s p-value now matches
           `scipy.stats.pearsonr`'s to a relative difference the driver's rtol comfortably
           covers. Expect the driver's p_value comparison to PASS -- a change from when this
           file was first written, when the same comparison was expected to fail and that
           failure was this benchmark's headline finding.

THE DATA
--------
Two independent counter-based SplitMix64 streams -- `x[i]` from counter `2*i`, `noise[i]`
from counter `2*i+1` -- so `bench_vs_pearsonr_scipy.py` can reproduce the identical bit
patterns in NumPy with no loop and no seed handshake, and `y[i] = 0.6*x[i] + 0.4*noise[i]`
gives a real, imperfect linear relationship (neither r=0 nor r=1, both of which are
degenerate special cases inside `pearson_r`). Every swept size is a PREFIX of one
10,000,000-element pair, so every cell computes over a subset of the exact same bits.

`x` matches scipy's regenerated array bit for bit at every size (verified by the driver's
fingerprint check) -- it is pure `to_unit(splitmix64(...))`, no floating-point combination.
`y` does NOT match bit for bit: it is a linear combination, `0.6*xi + 0.4*ni`, and compiled
Mojo fuses that into a single hardware FMA (one rounding) where CPython and NumPy always
perform the multiply and the add as two separately-rounded operations. Measured directly:
332 of 2000 sampled `y` values (16.6%) differ from Python's by exactly 1 ULP, none by more,
and NumPy-vectorized and pure-Python-scalar agree with EACH OTHER on all 2000 -- so the
mismatch is Mojo-side FMA contraction, not a generator bug on either side. This is reported
by the driver as informational, not gated, and is exactly the kind of noise the r-value
rtol (1e-9, against a measured ~5e-16) is wide enough to absorb.

THE DISPERSION GATE
--------------------
Identical in shape to `bench_vs_topk.mojo`: `hot <= warm`, `median/min <= MAX_SPREAD`, and
`p90/min <= MAX_P90_SPREAD`, computed over HOT_REPS timed units, each unit itself a batch
of `inner` calls sized so the batch spans at least UNIT_FLOOR_NS. A cell that violates any
condition prints INVALID, names every failed condition, and prints NO rate.
"""
from std.time import perf_counter_ns

from stat_tests import pearson_r, CorrResult

# ── configuration ─────────────────────────────────────────────────────────────

comptime MAX_N: Int = 10_000_000
"""The one pair of allocations. Every swept size is a PREFIX of it."""

comptime HOT_REPS: Int = 25
"""Timed units after the warm one. HOT is their minimum."""

comptime UNIT_FLOOR_NS: Float64 = 5_000_000.0
"""A timed UNIT repeats the call until it spans at least this long, then divides by the
repeat count -- see `bench_vs_topk.mojo` for the full rationale (clock granularity)."""

comptime CELL_BUDGET_NS: Float64 = 2_000_000_000.0
"""EQUAL WALL-CLOCK PER CELL, on both sides of the comparison. `bench_vs_pearsonr_scipy.py`
applies the identical rule with the identical constants."""

comptime MIN_REPS: Int = 3
comptime MAX_INNER: Int = 2_000_000

comptime MAX_P90_SPREAD: Float64 = 4.0
comptime MAX_SPREAD: Float64 = 2.0

comptime GOLDEN: UInt64 = 0x9E3779B97F4A7C15

# ── data ──────────────────────────────────────────────────────────────────────


def splitmix64(counter: UInt64) -> UInt64:
    """SplitMix64 finalizer over a COUNTER, not carried state -- see `bench_vs_topk.mojo`."""
    var z = counter * GOLDEN + GOLDEN
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9
    z = (z ^ (z >> 27)) * 0x94D049BB133111EB
    return z ^ (z >> 31)


def to_unit(bits: UInt64) -> Float64:
    """Top 53 bits -> Float64 in [0, 1)."""
    return Float64(bits >> 11) * (1.0 / 9007199254740992.0)


def gen_pair(n: Int, mut x: List[Float64], mut y: List[Float64]):
    """`x[i]` from counter `2i`, `noise[i]` from counter `2i+1`, `y = 0.6x + 0.4*noise`.

    Disjoint counters by construction (even vs odd), so the two streams never collide for
    any `n`, and NumPy reproduces both with a single vectorised `2*arange(n)[+1]`.
    """
    for i in range(n):
        var xi = to_unit(splitmix64(UInt64(2 * i)))
        var ni = to_unit(splitmix64(UInt64(2 * i + 1)))
        x.append(xi)
        y.append(0.6 * xi + 0.4 * ni)


def bits_of(v: Float64) -> UInt64:
    return v.to_bits[DType.uint64]()


def fingerprint(a: List[Float64], n: Int) -> UInt64:
    """XOR fingerprint of the raw bit patterns -- proves both sides got the same array."""
    var h = UInt64(0)
    for i in range(n):
        h = h ^ bits_of(a[i])
    return h


# ── timing (identical shape to bench_vs_topk.mojo's judge/reps_for/batch_size) ────────


def reps_for(unit_ns: Float64) -> Int:
    if unit_ns <= 0.0:
        return HOT_REPS
    var want = Int(CELL_BUDGET_NS / unit_ns)
    if want < MIN_REPS:
        return MIN_REPS
    if want > HOT_REPS:
        return HOT_REPS
    return want


def batch_size(pilot_ns: Float64) -> Int:
    if pilot_ns <= 0.0:
        return MAX_INNER
    var want = Int(UNIT_FLOOR_NS / pilot_ns) + 1
    if want < 1:
        return 1
    if want > MAX_INNER:
        return MAX_INNER
    return want


struct Cell(Copyable, Movable):
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

    def __init__(
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


def judge(cold: Float64, warm: Float64, var units: List[Float64], inner: Int) -> Cell:
    """Every failing condition is named, never one that held. See bench_vs_topk.mojo."""
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


def time_pearson(x: List[Float64], y: List[Float64], n: Int, mut sink: Float64) -> Cell:
    """COLD = call one, alone. WARM and HOT = per-call figures from equal-sized units."""
    var t0 = perf_counter_ns()
    var r0 = pearson_r(x, y)
    var t1 = perf_counter_ns()
    var cold = Float64(Int(t1 - t0))
    sink += r0.r
    var inner = batch_size(cold)

    var t2 = perf_counter_ns()
    for _ in range(inner):
        var rw = pearson_r(x, y)
        sink += rw.r
    var t3 = perf_counter_ns()
    var unit_ns = Float64(Int(t3 - t2))
    var warm = unit_ns / Float64(inner)
    var reps = reps_for(unit_ns)

    var units = List[Float64](capacity=reps)
    for _ in range(reps):
        var b0 = perf_counter_ns()
        for _ in range(inner):
            var r = pearson_r(x, y)
            sink += r.r
        var b1 = perf_counter_ns()
        units.append(Float64(Int(b1 - b0)) / Float64(inner))
    return judge(cold, warm, units^, inner)


def report(mut failures: Int, n: Int, cell: Cell):
    var head = "PEARSONR pearson_r n=" + String(n)
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
        "VALID",
    )
    print("COLD_WARM_HOT pearsonr.mojo.n" + String(n), cell.cold, cell.warm, cell.hot, "ns")


# ── main ──────────────────────────────────────────────────────────────────────


def main():
    var failures = 0
    var sink: Float64 = 0.0

    print("== pearson_r: Algenta stat_tests vs scipy.stats.pearsonr (Mojo arm) ==")
    print("  HOT = min of", HOT_REPS, "| data: two independent counter-based SplitMix64")
    print("  streams, y = 0.6*x + 0.4*noise, one", MAX_N, "element pair; every sweep size")
    print("  is a PREFIX of it, so scipy computes over identical bits.")
    print(
        "CONSTANTS", "HOT_REPS=" + String(HOT_REPS), "MIN_REPS=" + String(MIN_REPS),
        "UNIT_FLOOR_NS=" + String(UNIT_FLOOR_NS),
        "CELL_BUDGET_NS=" + String(CELL_BUDGET_NS),
        "MAX_SPREAD=" + String(MAX_SPREAD),
        "MAX_P90_SPREAD=" + String(MAX_P90_SPREAD),
        "MAX_N=" + String(MAX_N),
    )

    var x = List[Float64](capacity=MAX_N)
    var y = List[Float64](capacity=MAX_N)
    var gen0 = perf_counter_ns()
    gen_pair(MAX_N, x, y)
    var gen1 = perf_counter_ns()
    print(
        "  generated", MAX_N, "pairs in", Float64(Int(gen1 - gen0)) / 1.0e6, "ms",
        "(untimed setup, and scipy pays its own)",
    )
    print("")

    # ── 1. correctness data: fingerprints + r/p bits, BEFORE any timing ───────
    # 10 and 100 are extra, UNTIMED sizes -- not part of the timing sweep below -- included
    # specifically because they land the t-statistic in scipy's NORMAL (non-underflowed)
    # p-value range, e.g. scipy reports p=0.00196 at n=10, so the incomplete-beta bug shows
    # as a clean, unambiguous numeric disagreement instead of "both sides underflowed to 0,"
    # which is what happens to every size in the timing sweep at n >= 10,000.
    print("-- 1. CORRECTNESS: fingerprints and r/p_value, for the driver to cross-check --")
    for n in [10, 100, 1_000, 10_000, 100_000, 1_000_000, 10_000_000]:
        var fx = fingerprint(x, n)
        var fy = fingerprint(y, n)
        # pearson_r has no n-argument -- it reads min(len(x), len(y)) itself, so a PREFIX
        # comparison at size n needs prefix slices, not the full MAX_N arrays.
        var px = List[Float64](capacity=n)
        var py = List[Float64](capacity=n)
        for i in range(n):
            px.append(x[i])
            py.append(y[i])
        var r_n = pearson_r(px, py)
        print(
            "PEARSONR_DIGEST n=" + String(n),
            "fx=" + String(fx),
            "fy=" + String(fy),
            "r=" + String(r_n.r),
            "r_bits=" + String(bits_of(r_n.r)),
            "p_value=" + String(r_n.p_value),
            "p_bits=" + String(bits_of(r_n.p_value)),
        )
    print("")

    # ── 2. the sweep ──────────────────────────────────────────────────────────
    print("-- 2. SWEEP: n = 1e3 .. 1e7, single-pass O(n) reduction --")
    for n in [1_000, 10_000, 100_000, 1_000_000, 10_000_000]:
        var px = List[Float64](capacity=n)
        var py = List[Float64](capacity=n)
        for i in range(n):
            px.append(x[i])
            py.append(y[i])
        var cell = time_pearson(px, py, n, sink)
        report(failures, n, cell)
    print("")

    # Keep the arrays and every timed result observably alive.
    var alive = x[0] + x[MAX_N - 1] + y[0] + y[MAX_N - 1]
    if alive != alive or sink != sink:
        print("  checksum is impossible here:", alive, sink)

    if failures == 0:
        print("BENCH_GATE pearsonr_mojo PASS")
    else:
        print("BENCH_GATE pearsonr_mojo FAIL " + String(failures))
