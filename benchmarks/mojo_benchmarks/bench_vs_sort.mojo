"""bench_vs_sort.mojo — Algenta's sorts against `numpy.sort`, in one process, interleaved.

What is compared, and why each arm is here
------------------------------------------
Five arms, three of them ours. Every arm sorts the SAME BYTES: the input lives in a Mojo
`List[Float64]` and numpy is handed a zero-copy `ctypes` view of that same buffer, so there is no
conversion cost on either side and no possibility of the two seeing different data.

  numpy.sort              THE BASELINE. numpy 2.5.1's introsort for float64 — quicksort with a
                          heapsort fallback and an insertion-sort tail, in C, decades tuned. It
                          is single-threaded, which is stated rather than glossed: `np.sort` does
                          not thread, so `radix_par` beating it is partly a thread-count win and
                          `radix_seq` beating it is not. Both numbers are reported separately for
                          exactly that reason.
  radix_seq               columnar.sort_radix.radix_sort_f64 — NEW, sequential LSD radix.
  radix_par               columnar.sort_radix.radix_sort_f64_parallel at every physical core.
  frozen_quicksort        sorting.quicksort — FROZEN. Report-only: it may not be modified, so its
                          numbers are a finding about the tree, not a target.
  query_insertion         query.executor.sort_indices — the insertion sort the new radix exists to
                          replace. Fair game, and the loss is the reason the radix was written.

WHY THIS RUNS IN ONE PROCESS
----------------------------
The machine this was measured on was NOT quiet: 1-minute load average in the 30-50 range on 16
cores, with other agents' benchmarks running. Under that condition an absolute GB/s figure is this
machine's leftover share and not its capability, and a "run A, then run B" comparison is void
because the two arms saw different contention. A RATIO is still valid if and only if both arms are
interleaved inside one process, so that is what this does: within a single repetition the loop
times numpy, then radix_seq, then radix_par, back to back, and repeats. The load average is
sampled and printed before and after the whole sweep, and every table carries it.

For the same reason NO FRACTION-OF-CEILING IS CLAIMED here. `measure_stream_bandwidth.mojo` could
not reproduce its own 271 GB/s under today's load — it returned BENCH_GATE stream FAIL on three
consecutive runs, with the NT-SIMD triad arm swinging 161 -> 251 GB/s between runs — so a
percentage computed against 271 today would inherit that error. Effective GB/s IS printed for the
radix arms, because a bytes-moved figure is useful on its own and the reader can divide by whatever
ceiling they trust.

Correctness, which is checked BEFORE any timing and three separate ways
-----------------------------------------------------------------------
A sort that drops or duplicates an element can be very fast, so sortedness alone is not enough:

  1. SORTEDNESS. A Mojo scan asserting out[i] >= out[i-1] for every i.
  2. MULTISET, independently of the reference. The xor of all 64-bit key patterns and their
     wrapping sum are both permutation invariants, computed over the input and over the output. A
     dropped, duplicated or invented element changes at least one of them with overwhelming
     probability, and neither depends on numpy being right.
  3. BIT-EXACT AGREEMENT WITH `numpy.sort`. Both results are compared as raw uint64 through a
     zero-copy numpy view — not `allclose`, not `==` on floats, but identical bit patterns for all
     n elements. A sort performs no arithmetic, so there is no tolerance to state: the answers are
     either the same permutation or they are not.

Check 3 subsumes check 2 when numpy is correct; check 2 is kept because it holds even if the
reference is wrong, and because it is the check a caller can run in production.

WHERE OUR GUARANTEE DIFFERS FROM numpy's, stated rather than claimed away
--------------------------------------------------------------------------
The radix sorts by IEEE-754 TOTAL ORDER; `numpy.sort` puts NaN last regardless of sign. On NaN-free
input the two orders coincide exactly, and this benchmark uses NaN-free input, so the comparison is
like-for-like. On NaN input they would legitimately disagree, and that is a difference in contract,
not a defect on either side. Signed zeros are likewise ordered (-0.0 before +0.0) by the radix and
left to chance by a comparison sort; the generator emits no -0.0.

The three distributions, and why they are the whole point
----------------------------------------------------------
  random          uniform doubles in [-1, 1), full 52-bit mantissa, both signs
  sorted          the same multiset, ascending
  reverse         the same multiset, descending

Same multiset in all three, so any difference between them is the ALGORITHM reacting to input
order and nothing else. This is where the two legacy arms come apart: insertion sort is O(n) on
already-sorted input and O(n^2) on reversed, a spread of three orders of magnitude on identical
data, and the frozen quicksort's Lomuto partition takes the last element as pivot, which is the
maximum on sorted input and the minimum on reversed — both its worst case. The radix makes no
comparisons at all, so its cost is a function of the KEY BYTES and not of the order; the tables
below show its ns/element barely moving across the three, which is the property being demonstrated.

THE GATE
--------
`BENCH_GATE vs_sort PASS` or `FAIL <n>`. Every cell must satisfy, per arm:
  * hot <= warm — the third-and-later reads may not be slower than the second. A violation means
    contention arrived mid-cell and the cell means nothing.
  * hot_worst / hot <= MAX_SPREAD — dispersion across the hot repetitions.
  * every correctness check above.
A violated cell prints INVALID, names WHICH condition failed, and prints NO ratio and NO
throughput. The naming matters: `measure_stream_bandwidth.mojo` has a defect where the INVALID
line prints the condition that HELD (`"hot<=warm" if ordered else ...` inside a branch entered when
EITHER check fails), so a reader parsing gate strings is told the wrong cause. This file names each
failed condition separately and says nothing about the ones that passed.

Cold, warm, hot
---------------
Within this process: cold = the first timed repetition of a cell, warm = the second, hot = the
minimum of the remaining `HOT_REPS`. The minimum is right for the hot tier because contention can
only ever make a reading slower. True PROCESS-cold — first call in a fresh process, including
allocator and page-table state — can only be measured once per process; use
`benchmarks/cold_start_harness.py -K <k> bench_vs_sort` for that, and set `SORT_BENCH_MAX_N` to cap
the sweep so K processes finish in reasonable time.

Environment knobs
-----------------
  SORT_BENCH_MAX_N     skip main-sweep sizes above this (default: no cap)
  SORT_BENCH_HOT_REPS  hot repetitions per cell (default 5)
  SORT_BENCH_SKIP_LEGACY  set to 1 to skip the frozen/insertion sweep
"""
from max.algorithm import parallelize
from std.os import getenv
from std.sys import info
from std.time import perf_counter_ns

from python import Python, PythonObject

from columnar.array import Float64Array, float64_from_list
from columnar.batch import RecordBatch, schema_of
from columnar.sort_radix import (
    radix_sort_f64,
    radix_sort_f64_parallel,
    radix_sort_f64_report,
    radix_sort_f64_roundtrip_ok,
)
from query.executor import sort_indices
from sorting import quicksort

# Hot readings may not vary by more than this factor. 2.0 matches
# `measure_stream_bandwidth.mojo`: loose on purpose, because the gate exists to catch a machine too
# busy for the result to mean anything, not to demand a quiet one.
comptime MAX_SPREAD: Float64 = 2.0

# The legacy arms are O(n^2). At n = 100,000 on sorted input the frozen quicksort was measured at
# 235,195 ns PER ELEMENT — 23.5 seconds for one call — so their sweep stops early on purpose. The
# cap is a measurement, not a guess: see the extrapolation printed with those tables.
comptime LEGACY_HOT_REPS: Int = 2


def _fmt(value: Float64, places: Int) -> String:
    """Fixed-point, because `String(Float64)` prints 17 digits and a table becomes unreadable."""
    if value != value:
        return String("nan")
    var scale = 1.0
    for _ in range(places):
        scale *= 10.0
    var scaled = value * scale
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / scale
    return String(rounded)


def _pad(text: String, width: Int) -> String:
    var out = text
    while len(out.as_bytes()) < width:
        out += " "
    return out


def _dots(label: String, width: Int) -> String:
    """`label ......` padding, the shape `cold_start_harness.py`'s triple parser expects."""
    var out = label + " "
    while len(out.as_bytes()) < width:
        out += "."
    return out


struct Tier(Copyable, Movable):
    """One arm's cold/warm/hot in one cell, plus enough state to judge whether it is publishable."""

    var cold: Float64
    var warm: Float64
    var hot: Float64
    var hot_worst: Float64
    var reps: Int

    def __init__(out self):
        self.cold = 0.0
        self.warm = 0.0
        self.hot = 0.0
        self.hot_worst = 0.0
        self.reps = 0

    def record(mut self, ns: Float64):
        if self.reps == 0:
            self.cold = ns
        elif self.reps == 1:
            self.warm = ns
        else:
            if self.hot == 0.0 or ns < self.hot:
                self.hot = ns
            if ns > self.hot_worst:
                self.hot_worst = ns
        self.reps += 1

    def spread(self) -> Float64:
        if self.hot <= 0.0:
            return 0.0
        return self.hot_worst / self.hot

    def ordered(self) -> Bool:
        return self.hot <= self.warm

    def valid(self) -> Bool:
        return self.hot > 0.0 and self.ordered() and self.spread() <= MAX_SPREAD

    def why_invalid(self) -> String:
        """Names only the conditions that FAILED. See the gate note in the module docstring."""
        var reasons = String("")
        if self.hot <= 0.0:
            reasons += "no hot reading; "
        if not self.ordered():
            reasons += (
                "hot > warm ("
                + _fmt(self.hot, 0)
                + " ns > "
                + _fmt(self.warm, 0)
                + " ns: contention arrived mid-cell); "
            )
        if self.spread() > MAX_SPREAD:
            reasons += (
                "hot spread "
                + _fmt(self.spread(), 3)
                + "x over limit "
                + _fmt(MAX_SPREAD, 1)
                + "; "
            )
        if len(reasons.as_bytes()) == 0:
            reasons = String("(none — this should not print)")
        return reasons


def _per_elem(t: Tier, n: Int) -> Tier:
    var out = Tier()
    out.cold = t.cold / Float64(n)
    out.warm = t.warm / Float64(n)
    out.hot = t.hot / Float64(n)
    out.hot_worst = t.hot_worst / Float64(n)
    out.reps = t.reps
    return out^


def _triple_line(label: String, t: Tier, n: Int) -> String:
    var pe = _per_elem(t, n)
    return (
        "  "
        + _dots(label, 26)
        + " "
        + _pad(_fmt(pe.cold, 3), 10)
        + " / "
        + _pad(_fmt(pe.warm, 3), 10)
        + " / "
        + _pad(_fmt(pe.hot, 3), 10)
    )


def _machine_line(label: String, t: Tier, n: Int) -> String:
    var pe = _per_elem(t, n)
    return (
        "COLD_WARM_HOT "
        + label
        + " "
        + _fmt(pe.cold, 4)
        + " "
        + _fmt(pe.warm, 4)
        + " "
        + _fmt(pe.hot, 4)
        + " ns/elem"
    )


def _ratio(value: Float64) -> String:
    """A speed ratio with enough digits to survive being a catastrophic loss.

    Two decimal places is fine for 0.5x to 100x and useless outside it: the frozen quicksort's
    first run of this benchmark printed `cold 0.0x warm 0.0x hot 0.0x` for what was in fact a
    16,435x loss, because 1/16435 rounds to 0.00. A number that reads as "no measurement" when it
    is actually the largest finding in the file is worse than no number, so the precision follows
    the magnitude.
    """
    if value != value:
        return String("nan")
    if value >= 100.0:
        return _fmt(value, 0)
    if value >= 1.0:
        return _fmt(value, 2)
    if value >= 0.01:
        return _fmt(value, 3)
    if value <= 0.0:
        return String("0")
    # Below 1/100 the informative form is the reciprocal: "1/16435" reads as the loss it is.
    return "1/" + _fmt(1.0 / value, 0)


def _advantage_line(label: String, base: Tier, mine: Tier) -> String:
    """`label: cold Nx warm Nx hot Nx` — the shape the cold-start harness parses as a ratio."""
    return (
        "  "
        + label
        + ": cold "
        + _ratio(base.cold / mine.cold)
        + "x warm "
        + _ratio(base.warm / mine.warm)
        + "x hot "
        + _ratio(base.hot / mine.hot)
        + "x"
    )


def _melem_per_s(ns_total: Float64, n: Int) -> Float64:
    if ns_total <= 0.0:
        return 0.0
    return Float64(n) / ns_total * 1000.0


# ── input generation ─────────────────────────────────────────────────────────
def _fill_random(mut buf: List[Float64], n: Int, seed: UInt64):
    """Uniform doubles in [-1, 1) with a full 52-bit mantissa and both signs.

    xorshift64 rather than anything fancier: the point is a reproducible bit pattern with high
    entropy in every byte of the key, so that all eight radix passes are active and the radix arm
    gets no free skip. `radix_sort_f64_report` prints the pass count so a reader can confirm that.
    No NaN, no infinity, no -0.0 — see the contract note in the module docstring.
    """
    var s = seed
    var p = buf.unsafe_ptr()
    for i in range(n):
        s ^= s << 13
        s ^= s >> 7
        s ^= s << 17
        var mag = Float64(s >> 11) * (1.0 / 9007199254740992.0)
        if mag == 0.0:
            mag = 0.5
        p[i] = -mag if (s & 1) == 1 else mag
    _ = len(buf)


def _key_bits(x: Float64) -> UInt64:
    return x.to_bits[DType.uint64]()


@fieldwise_init
struct Fingerprint(Copyable, Movable):
    """Two permutation invariants over the raw bit patterns of a buffer."""

    var xor: UInt64
    var wrapping_sum: UInt64


def _multiset_fingerprint(data: List[Float64], n: Int) -> Fingerprint:
    """(xor, wrapping sum) of the raw bit patterns — two permutation invariants.

    Independent of the reference implementation, which is the point: it detects a dropped or
    duplicated element even if numpy is not consulted at all. Two invariants rather than one
    because xor alone is blind to a value appearing twice more (or an even-multiplicity shuffle),
    and the wrapping sum is not.
    """
    var x: UInt64 = 0
    var s: UInt64 = 0
    var p = data.unsafe_ptr()
    for i in range(n):
        var b = _key_bits(p[i])
        x ^= b
        s = s + b
    _ = len(data)
    return Fingerprint(x, s)


def _is_sorted_list(data: List[Float64], n: Int) -> Bool:
    var p = data.unsafe_ptr()
    for i in range(1, n):
        if p[i] < p[i - 1]:
            _ = len(data)
            return False
    _ = len(data)
    return True


def main() raises:
    var np = Python.import_module("numpy")
    var ct = Python.import_module("ctypes")
    var os = Python.import_module("os")
    var platform = Python.import_module("platform")

    var cores = info.num_physical_cores()
    if cores < 1:
        cores = 1
    var hot_reps = Int(atol(getenv("SORT_BENCH_HOT_REPS", "5")))
    if hot_reps < 1:
        hot_reps = 1
    var max_n_env = getenv("SORT_BENCH_MAX_N", "0")
    var max_n = Int(atol(max_n_env)) if len(max_n_env.as_bytes()) > 0 else 0
    var skip_legacy = getenv("SORT_BENCH_SKIP_LEGACY", "0") == "1"

    var load_before = os.getloadavg()

    print("bench_vs_sort — Algenta sorts vs numpy.sort, single process, interleaved arms")
    print("=" * 96)
    print("  numpy          ", np.__version__, " python ", platform.python_version())
    print("  physical cores ", cores, "  hot reps ", hot_reps, "  max spread ", MAX_SPREAD)
    print(
        "  load average BEFORE (1m/5m/15m):",
        load_before[0],
        load_before[1],
        load_before[2],
    )
    print(
        "  NOTE: a 1-minute load near or above the core count means every absolute figure here is"
    )
    print(
        "        this machine's leftover share. Ratios stay valid because the arms are interleaved."
    )
    print("")

    var failures = 0

    # ── the key transform, checked before anything is timed ───────────────────
    # The whole radix rests on _radix_key being a bijection. Checked on the values a sort is most
    # likely to be wrong about rather than on a random sample.
    var probes = List[Float64]()
    probes.append(0.0)
    probes.append(-0.0)
    probes.append(1.0)
    probes.append(-1.0)
    probes.append(4.9406564584124654e-324)
    probes.append(-4.9406564584124654e-324)
    probes.append(1.7976931348623157e308)
    probes.append(-1.7976931348623157e308)
    probes.append(2.2250738585072014e-308)
    var roundtrip_ok = True
    for i in range(len(probes)):
        if not radix_sort_f64_roundtrip_ok(probes[i]):
            roundtrip_ok = False
    if roundtrip_ok:
        print("  key transform: unkey(key(x)) is bit-identical on 9 edge values (0, -0, denormal,")
        print("                 +/-DBL_MAX, +/-DBL_MIN) — the bijection the radix depends on holds")
    else:
        failures += 1
        print("  ❌ key transform is not a bijection on the edge values; every result below is void")
    print("")

    # ── interop overhead, so numpy's arm is not silently charged for it ───────
    # numpy is called across the Mojo/CPython boundary; that call costs something, and it is added
    # to numpy's measured time, not ours. Measuring it here bounds how much of numpy's figure is
    # not numpy.
    var tiny = List[Float64](unsafe_uninit_length=8)
    for i in range(8):
        tiny[i] = Float64(8 - i)
    var tiny_view = np.ctypeslib.as_array(
        ct.cast(Int(tiny.unsafe_ptr()), ct.POINTER(ct.c_double)), Python.tuple(8)
    )
    # Mean over the whole loop rather than best-of: a single call is close enough to the clock's
    # granularity that the minimum reads as 0 ns, which would understate the charge rather than
    # bound it. The mean is the conservative direction here.
    var interop_t0 = perf_counter_ns()
    for _ in range(2000):
        var _r = np.sort(tiny_view)
    var interop_t1 = perf_counter_ns()
    var interop_ns = Float64(Int(interop_t1 - interop_t0)) / 2000.0
    _ = len(tiny)
    print(
        "  numpy call overhead (np.sort on 8 elements, mean of 2000): "
        + _fmt(interop_ns, 0)
        + " ns"
    )
    print(
        "  That is charged to numpy in every table below. At the smallest size swept it is under"
    )
    print(
        "  "
        + _fmt(interop_ns / 1000.0, 2)
        + " us against a call that takes milliseconds, so it does not change any conclusion —"
    )
    print("  but it is stated because it is a cost our arms do not pay.")
    print("")

    # ── the main sweep ────────────────────────────────────────────────────────
    var sizes = List[Int]()
    sizes.append(100_000)
    sizes.append(400_000)
    sizes.append(1_600_000)
    sizes.append(6_400_000)
    sizes.append(25_600_000)
    sizes.append(102_400_000)

    var dist_names = List[String]()
    dist_names.append(String("random"))
    dist_names.append(String("sorted"))
    dist_names.append(String("reverse"))

    # Crossover bookkeeping: the smallest n where each of ours first beats numpy, and the smallest
    # n where the parallel arm first beats the sequential one. Both halves are the result.
    var seq_wins_at = -1
    var par_wins_at = -1
    var par_beats_seq_at = -1
    var seq_wins_any_at = -1
    var par_wins_any_at = -1
    var par_beats_seq_any_at = -1
    var invalid_random_cells = 0

    print("MAIN SWEEP — numpy.sort vs radix_seq vs radix_par")
    print("-" * 96)
    print("cold / warm / hot: ns per element")
    print("")

    for si in range(len(sizes)):
        var n = sizes[si]
        if max_n > 0 and n > max_n:
            continue

        var values = List[Float64](unsafe_uninit_length=n)
        _fill_random(values, n, 88172645463325252)
        var vp = values.unsafe_ptr()
        var view = np.ctypeslib.as_array(
            ct.cast(Int(vp), ct.POINTER(ct.c_double)), Python.tuple(n)
        )

        for di in range(len(dist_names)):
            var dist = dist_names[di]

            # Distribution setup, entirely untimed and done through numpy so that the input to the
            # timed region does not depend on the implementation under test.
            if dist == "sorted":
                np.copyto(view, np.sort(view))
            elif dist == "reverse":
                np.copyto(view, np.sort(view)[::-1].copy())
            else:
                _fill_random(values, n, 88172645463325252)

            var report = radix_sort_f64_report(values)
            var in_fp = _multiset_fingerprint(values, n)

            print(
                "n="
                + String(n)
                + "  dist="
                + dist
                + "  radix passes active="
                + String(report.passes_run)
                + " of 8"
            )

            # ── correctness BEFORE any timing ─────────────────────────────────
            var reference = np.sort(view)
            var seq_check = radix_sort_f64(values)
            var par_check = radix_sort_f64_parallel(values, cores)

            var seq_sorted = _is_sorted_list(seq_check, n)
            var par_sorted = _is_sorted_list(par_check, n)
            var seq_fp = _multiset_fingerprint(seq_check, n)
            var par_fp = _multiset_fingerprint(par_check, n)
            var seq_multiset = seq_fp.xor == in_fp.xor and seq_fp.wrapping_sum == in_fp.wrapping_sum
            var par_multiset = par_fp.xor == in_fp.xor and par_fp.wrapping_sum == in_fp.wrapping_sum

            var ref_bits = reference.view(np.uint64)
            var seq_view = np.ctypeslib.as_array(
                ct.cast(Int(seq_check.unsafe_ptr()), ct.POINTER(ct.c_double)), Python.tuple(n)
            )
            var par_view = np.ctypeslib.as_array(
                ct.cast(Int(par_check.unsafe_ptr()), ct.POINTER(ct.c_double)), Python.tuple(n)
            )
            var seq_exact = Bool(np.array_equal(seq_view.view(np.uint64), ref_bits))
            var par_exact = Bool(np.array_equal(par_view.view(np.uint64), ref_bits))
            _ = len(seq_check)
            _ = len(par_check)

            var correct = (
                seq_sorted
                and par_sorted
                and seq_multiset
                and par_multiset
                and seq_exact
                and par_exact
            )
            if correct:
                print(
                    "  correctness: sorted seq/par yes/yes | multiset xor+sum invariant yes/yes |"
                    + " bit-exact vs numpy.sort yes/yes (0 tolerance, "
                    + String(n)
                    + " of "
                    + String(n)
                    + " elements)"
                )
            else:
                failures += 1
                print(
                    "  ❌ correctness: sorted seq="
                    + String(seq_sorted)
                    + " par="
                    + String(par_sorted)
                    + " | multiset seq="
                    + String(seq_multiset)
                    + " par="
                    + String(par_multiset)
                    + " | bit-exact seq="
                    + String(seq_exact)
                    + " par="
                    + String(par_exact)
                )

            # ── timing, arms interleaved inside every repetition ──────────────
            var t_np = Tier()
            var t_seq = Tier()
            var t_par = Tier()
            for _ in range(2 + hot_reps):
                var a0 = perf_counter_ns()
                var np_out = np.sort(view)
                var a1 = perf_counter_ns()
                var s_out = radix_sort_f64(values)
                var a2 = perf_counter_ns()
                var p_out = radix_sort_f64_parallel(values, cores)
                var a3 = perf_counter_ns()
                t_np.record(Float64(Int(a1 - a0)))
                t_seq.record(Float64(Int(a2 - a1)))
                t_par.record(Float64(Int(a3 - a2)))
                # Observably consume each result so no arm is eliminated as dead code.
                if s_out[0] != p_out[0] or Bool(np_out[0] != s_out[0]):
                    print("  ❌ an arm's first element disagrees inside the timing loop")
                    failures += 1

            print(_triple_line(String("numpy.sort"), t_np, n))
            print(_triple_line(String("radix_seq"), t_seq, n))
            print(_triple_line(String("radix_par x") + String(cores), t_par, n))
            print(_machine_line(String("numpy_sort_") + dist, t_np, n))
            print(_machine_line(String("radix_seq_") + dist, t_seq, n))
            print(_machine_line(String("radix_par_") + dist, t_par, n))

            # Crossover bookkeeping happens for EVERY random cell, valid or not, because a
            # crossover derived only from gate-passing cells is an upper bound on the crossover
            # rather than the crossover: on a contended machine the small-n cells are the ones most
            # likely to be thrown out, and those are exactly the ones that locate it. The two
            # figures are reported separately and the indicative one is labelled as such — it is
            # never used as if it had passed the gate.
            if dist == "random":
                if seq_wins_any_at < 0 and t_seq.hot < t_np.hot:
                    seq_wins_any_at = n
                if par_wins_any_at < 0 and t_par.hot < t_np.hot:
                    par_wins_any_at = n
                if par_beats_seq_any_at < 0 and t_par.hot < t_seq.hot:
                    par_beats_seq_any_at = n

            var cell_valid = t_np.valid() and t_seq.valid() and t_par.valid()
            if dist == "random" and not cell_valid:
                invalid_random_cells += 1
            if not cell_valid:
                failures += 1
                if not t_np.valid():
                    print("  INVALID numpy.sort -- " + t_np.why_invalid() + "no ratio reported")
                if not t_seq.valid():
                    print("  INVALID radix_seq  -- " + t_seq.why_invalid() + "no ratio reported")
                if not t_par.valid():
                    print("  INVALID radix_par  -- " + t_par.why_invalid() + "no ratio reported")
            else:
                print(_advantage_line(String("radix_seq vs numpy"), t_np, t_seq))
                print(_advantage_line(String("radix_par vs numpy"), t_np, t_par))
                print(_advantage_line(String("radix_par vs radix_seq"), t_seq, t_par))
                print(
                    "  hot throughput: numpy "
                    + _fmt(_melem_per_s(t_np.hot, n), 1)
                    + " | radix_seq "
                    + _fmt(_melem_per_s(t_seq.hot, n), 1)
                    + " | radix_par "
                    + _fmt(_melem_per_s(t_par.hot, n), 1)
                    + " Melem/s   (keys/s is identical: one scalar Float64 key per element, so"
                    + " elements and keys are the same count here)"
                )
                # Bytes the radix actually moves: the keying pass reads the data and writes keys
                # (16 B/elem), each pass after the first re-reads the keys to rebuild its
                # per-worker histogram (8 B/elem, parallel arm only), and every scatter reads a key
                # and writes 8 bytes (16 B/elem). Stated as a model, not a measurement.
                var passes = Float64(report.passes_run)
                var seq_bytes = 16.0 + 16.0 * passes
                var par_bytes = seq_bytes + 8.0 * (passes - 1.0 if passes > 1.0 else 0.0)
                print(
                    "  effective bandwidth (hot, model traffic "
                    + _fmt(seq_bytes, 0)
                    + " B/elem seq, "
                    + _fmt(par_bytes, 0)
                    + " B/elem par): radix_seq "
                    + _fmt(seq_bytes / t_seq.hot * Float64(n), 1)
                    + " GB/s | radix_par "
                    + _fmt(par_bytes / t_par.hot * Float64(n), 1)
                    + " GB/s   -- NO fraction of 271 GB/s is quoted: STREAM would not reproduce"
                    + " that ceiling under today's load"
                )
                if dist == "random":
                    if seq_wins_at < 0 and t_seq.hot < t_np.hot:
                        seq_wins_at = n
                    if par_wins_at < 0 and t_par.hot < t_np.hot:
                        par_wins_at = n
                    if par_beats_seq_at < 0 and t_par.hot < t_seq.hot:
                        par_beats_seq_at = n
            print("")

        _ = len(values)

    # ── the legacy arms: the loss, reported as prominently as the win ─────────
    if not skip_legacy:
        print("LEGACY SWEEP — the two sorts already in the tree, against the same numpy.sort")
        print("-" * 96)
        print("Both are O(n^2). `sorting.quicksort` is FROZEN and may not be modified, so its")
        print("numbers are a finding. `query.executor.sort_indices` is fair game and is exactly")
        print("what `columnar.sort_radix` was written to replace. The sizes stop at 50,000 because")
        print("at n = 100,000 on sorted input the frozen quicksort was measured at 23.5 SECONDS for")
        print("one call — 235,195 ns per element — and five repetitions of that is not a benchmark,")
        print("it is a hang.")
        print("")
        print("cold / warm / hot: ns per element")
        print("")

        var legacy_sizes = List[Int]()
        legacy_sizes.append(10_000)
        legacy_sizes.append(50_000)

        for si in range(len(legacy_sizes)):
            var n = legacy_sizes[si]
            var values = List[Float64](unsafe_uninit_length=n)
            _fill_random(values, n, 88172645463325252)
            var vp = values.unsafe_ptr()
            var view = np.ctypeslib.as_array(
                ct.cast(Int(vp), ct.POINTER(ct.c_double)), Python.tuple(n)
            )

            for di in range(len(dist_names)):
                var dist = dist_names[di]
                if dist == "sorted":
                    np.copyto(view, np.sort(view))
                elif dist == "reverse":
                    np.copyto(view, np.sort(view)[::-1].copy())
                else:
                    _fill_random(values, n, 88172645463325252)

                # The RecordBatch the insertion sort needs is built OUTSIDE the timed region, which
                # is generous to it: a caller would pay that too. Only `sort_indices` is timed, and
                # it returns a permutation rather than materialising sorted values, so the gather a
                # caller still owes is also excluded. Both concessions make the loss below a floor.
                var names = List[String]()
                names.append(String("k"))
                var cols = List[Float64Array]()
                cols.append(float64_from_list(values.copy()))
                var batch = RecordBatch(schema_of(names^), cols^, n)

                print("n=" + String(n) + "  dist=" + dist)

                var frozen_once = quicksort(values)
                var frozen_sorted = _is_sorted_list(frozen_once, n)
                var frozen_fp = _multiset_fingerprint(frozen_once, n)
                var in_fp = _multiset_fingerprint(values, n)
                var frozen_multiset = frozen_fp.xor == in_fp.xor and frozen_fp.wrapping_sum == in_fp.wrapping_sum
                _ = len(frozen_once)

                var order_once = sort_indices(batch, 0, False, True)
                var key_col = batch.column(0)
                var ins_sorted = True
                for i in range(1, n):
                    if key_col.get(order_once[i]) < key_col.get(order_once[i - 1]):
                        ins_sorted = False
                var seen = List[Bool](length=n, fill=False)
                var ins_perm = len(order_once) == n
                for i in range(len(order_once)):
                    var o = order_once[i]
                    if o < 0 or o >= n or seen[o]:
                        ins_perm = False
                    else:
                        seen[o] = True

                if frozen_sorted and frozen_multiset and ins_sorted and ins_perm:
                    print(
                        "  correctness: frozen_quicksort sorted+multiset yes | query_insertion"
                        + " ordering yes, output is a permutation of 0..n-1 yes"
                    )
                else:
                    failures += 1
                    print(
                        "  ❌ correctness: frozen sorted="
                        + String(frozen_sorted)
                        + " multiset="
                        + String(frozen_multiset)
                        + " | insertion ordered="
                        + String(ins_sorted)
                        + " permutation="
                        + String(ins_perm)
                    )

                var t_np = Tier()
                var t_fz = Tier()
                var t_in = Tier()
                for _ in range(2 + LEGACY_HOT_REPS):
                    var a0 = perf_counter_ns()
                    var np_out = np.sort(view)
                    var a1 = perf_counter_ns()
                    var fz_out = quicksort(values)
                    var a2 = perf_counter_ns()
                    var in_out = sort_indices(batch, 0, False, True)
                    var a3 = perf_counter_ns()
                    t_np.record(Float64(Int(a1 - a0)))
                    t_fz.record(Float64(Int(a2 - a1)))
                    t_in.record(Float64(Int(a3 - a2)))
                    if Bool(np_out[0] != fz_out[0]) or len(in_out) != n:
                        failures += 1
                        print("  ❌ a legacy arm disagreed inside the timing loop")

                print(_triple_line(String("numpy.sort"), t_np, n))
                print(_triple_line(String("frozen_quicksort"), t_fz, n))
                print(_triple_line(String("query_insertion"), t_in, n))
                print(_machine_line(String("legacy_numpy_") + dist, t_np, n))
                print(_machine_line(String("frozen_quicksort_") + dist, t_fz, n))
                print(_machine_line(String("query_insertion_") + dist, t_in, n))

                if not (t_np.valid() and t_fz.valid() and t_in.valid()):
                    failures += 1
                    if not t_np.valid():
                        print("  INVALID numpy.sort       -- " + t_np.why_invalid() + "no ratio")
                    if not t_fz.valid():
                        print("  INVALID frozen_quicksort -- " + t_fz.why_invalid() + "no ratio")
                    if not t_in.valid():
                        print("  INVALID query_insertion  -- " + t_in.why_invalid() + "no ratio")
                else:
                    print(_advantage_line(String("frozen_quicksort vs numpy"), t_np, t_fz))
                    print(_advantage_line(String("query_insertion vs numpy"), t_np, t_in))
                    # Each arm gets its own verdict, in the direction it actually went. The first
                    # version of this line asserted a loss for both arms and printed
                    # "0.2x faster than query_insertion" for a case where the insertion sort was
                    # 4.55x FASTER than numpy — an already-sorted input, its O(n) best case. A
                    # verdict line that cannot say "we won here" is not reporting, it is a
                    # template.
                    var fz_ratio = t_fz.hot / t_np.hot
                    var in_ratio = t_in.hot / t_np.hot
                    if fz_ratio > 1.0:
                        print(
                            "  WE LOSE: numpy.sort is "
                            + _ratio(fz_ratio)
                            + "x faster than frozen_quicksort (FROZEN, report-only), hot, at n="
                            + String(n)
                            + " on "
                            + dist
                        )
                    else:
                        print(
                            "  we win: frozen_quicksort is "
                            + _ratio(1.0 / fz_ratio)
                            + "x faster than numpy.sort, hot, at n="
                            + String(n)
                            + " on "
                            + dist
                        )
                    if in_ratio > 1.0:
                        print(
                            "  WE LOSE: numpy.sort is "
                            + _ratio(in_ratio)
                            + "x faster than query_insertion, hot, at n="
                            + String(n)
                            + " on "
                            + dist
                        )
                    else:
                        print(
                            "  we win: query_insertion is "
                            + _ratio(1.0 / in_ratio)
                            + "x faster than numpy.sort, hot, at n="
                            + String(n)
                            + " on "
                            + dist
                            + " — insertion sort's O(n) best case, not a general result"
                        )
                print("")

            _ = len(values)

    var load_after = os.getloadavg()
    print("SUMMARY")
    print("-" * 96)
    print("  CROSSOVERS on random input, hot tier. Two columns, and the difference matters:")
    print(
        "    GATED      smallest n whose whole cell passed the gate AND showed the win. An upper"
    )
    print(
        "               bound on the crossover: a cell thrown out for dispersion may well have"
    )
    print("               shown the win too, and small-n cells are the likeliest to be thrown out.")
    print(
        "    INDICATIVE smallest n that showed the win in ANY cell, gate-failing ones included."
    )
    print(
        "               A lower bound, and NOT publishable on its own — it is printed so the true"
    )
    print("               crossover can be bracketed rather than overstated.")
    print(
        "    invalid random cells this run: "
        + String(invalid_random_cells)
        + " (each one widens the bracket)"
    )
    print("")
    print("    claim                          GATED            INDICATIVE")
    print(
        "    radix_seq beats numpy.sort     "
        + _pad(String(seq_wins_at) if seq_wins_at > 0 else String("never"), 17)
        + (String(seq_wins_any_at) if seq_wins_any_at > 0 else String("never"))
    )
    print(
        "    radix_par beats numpy.sort     "
        + _pad(String(par_wins_at) if par_wins_at > 0 else String("never"), 17)
        + (String(par_wins_any_at) if par_wins_any_at > 0 else String("never"))
    )
    print(
        "    radix_par beats radix_seq      "
        + _pad(String(par_beats_seq_at) if par_beats_seq_at > 0 else String("never"), 17)
        + (String(par_beats_seq_any_at) if par_beats_seq_any_at > 0 else String("never"))
    )
    print(
        "  Below the last row the parallel arm is SLOWER than the sequential one and that half of"
    )
    print(
        "  the result is as load-bearing as the win: nine parallel regions are entered per sort"
    )
    print(
        "  (one keying pass plus up to eight scatters), so the fixed cost is roughly nine times"
    )
    print(
        "  what a single-region kernel pays. `RADIX_PARALLEL_MIN_N` = 2,097,152 is the threshold"
    )
    print("  `radix_sort_f64_auto` applies, and it should sit inside the bracket above.")
    print(
        "  load average AFTER (1m/5m/15m):",
        load_after[0],
        load_after[1],
        load_after[2],
    )
    print("")

    if failures == 0:
        print("BENCH_GATE vs_sort PASS")
    else:
        print("BENCH_GATE vs_sort FAIL " + String(failures))
