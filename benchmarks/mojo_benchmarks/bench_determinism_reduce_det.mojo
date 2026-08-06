"""bench_determinism_reduce_det.mojo — the gate behind determinism.reduce_det's claims.

Hand-written, not generated. `benchmark_mojo_vs_python.py` only writes `bench_<lib>.mojo`
for libraries in the runtime inventory, and `determinism` is in
`mojo_inventory._SKIP_RUNTIME_DIRS`, so no generated file can claim this name — the same
reasoning that protects `bench_determinism_counter_rng.mojo` beside it.

What is measured, and why each one is the claim that matters
-----------------------------------------------------------
1. **The problem is real.** A left-to-right sum of the SAME array, chunked several ways,
   returns several different numbers. This is measured first, because every other claim
   here is worthless if the baseline is too benign to distinguish orderings. It gates on
   the count of DISTINCT answers being > 1.

2. **The tree is invariant, with `==`.** `det_sum` and `det_sum_chunked` must agree
   bit-for-bit across every chunk size, at several lengths. Asserted with `==` and never a
   tolerance: a tolerance accepts exactly the drift the module exists to remove. Zero
   violations is the gate.

3. **What it costs.** ns per element for the sequential sum, the tree, the frozen
   `kahan_sum`, and Neumaier. The tree is SLOWER than a sequential sum and the number is
   printed rather than hidden. The gate is a loose ceiling on the ratio, so a real
   regression is caught while absolute nanoseconds stay machine-dependent.

4. **Compensation is not association.** Neumaier recovers the exact 2.0 on
   `[1.0, 1e100, 1.0, -1e100]` where the frozen `kahan_sum` returns 0.0 — the documented
   limit that justifies adding a second compensated form instead of extending the frozen
   one. And Neumaier is NOT chunk-invariant, which is gated too, because the module's
   docstring says only `det_sum` is.

5. **Absent, not zero.** A mean of nothing, an overflowed sum, a count past the end of the
   list, and a chunk size below one must each come back `present == False` under a
   non-success status.

JIT vs compiled
---------------
`make` runs this under `mojo run`, i.e. the JIT. The absolute numbers quoted in
`determinism/reduce_det.mojo`'s docstring (21.9 ms sequential / 51.8 ms tree over
10,000,001 elements, ratio 2.4x) come from a COMPILED binary on macOS arm64, and JIT
numbers here will differ — often by more than the ratio being reported. The ratio and the
invariance are the portable claims; the millisecond figures are provenance-tagged.

Running it
----------
No Makefile target is added here (this build was scoped to add nothing to existing files
beyond one test registration line). Run it directly, from `mojo_env/`:

    pixi run mojo run -I../mojo/engine \
        ../benchmarks/mojo_benchmarks/bench_determinism_reduce_det.mojo

Measured 2026-07-31 under the JIT: 87 chunk comparisons, 0 violations; the sequential
baseline gave 8 distinct answers over 11 chunkings of one 1025-element array; tree /
sequential = 3.11x per element at n = 2^20 + 1.

Gate
----
Fails on the properties, never on absolute nanoseconds:
  * the sequential baseline must give more than one answer over the same data
  * `det_sum_chunked` must equal `det_sum` exactly, for every chunk size tried
  * the tree must stay under 20x the sequential sum per element
  * Neumaier must return 2.0 where Kahan returns 0.0, and must NOT be chunk-invariant
  * five no-answer paths must be absent under a non-success status
"""
from std.time import perf_counter_ns

from determinism.reduce_det import (
    DET_EMPTY,
    DET_ERR_CHUNK,
    DET_ERR_COUNT,
    DET_ERR_OVERFLOW,
    DET_OK,
    det_dot,
    det_kahan_sum,
    det_mean,
    det_naive_sum,
    det_naive_sum_chunked,
    det_neumaier_sum,
    det_status_name,
    det_sum,
    det_sum_chunked,
    det_sum_squares,
)

comptime WARMUP: Int = 2


def _ns_per(elapsed: UInt, work: Int, reps: Int) -> Float64:
    """`perf_counter_ns` yields UInt, so the delta stays unsigned until here."""
    if work <= 0 or reps <= 0:
        return 0.0
    return Float64(Int(elapsed)) / Float64(work * reps)


def big_then_ones(n_ones: Int) -> List[Float64]:
    """`[1e16] + n_ones x 1.0`. 1e16 has an ulp of 2.0, so `1e16 + 1.0` rounds back to 1e16
    and a sequential sum discards every term after the first."""
    var out = List[Float64]()
    out.append(1e16)
    for _ in range(n_ones):
        out.append(1.0)
    return out^


def ragged(m: Int) -> List[Float64]:
    """Mixed magnitudes and alternating signs, so association order changes the answer for
    reasons unrelated to the one big value above."""
    var out = List[Float64]()
    for i in range(m):
        var sign = 1.0 if (i % 3) == 0 else -1.0
        out.append(sign * Float64(i + 1) * 1e-7 * Float64((i % 17) + 1))
        if i % 101 == 0:
            out.append(1e9)
    return out^


def chunk_grid(n: Int) -> List[Int]:
    var cs = List[Int]()
    cs.append(1)
    cs.append(2)
    cs.append(3)
    cs.append(7)
    cs.append(31)
    cs.append(64)
    cs.append(1000)
    cs.append(4096)
    if n // 2 > 0:
        cs.append(n // 2)
    cs.append(n)
    cs.append(n + 5)
    return cs^


def main() raises:
    var failures = 0
    print("bench_determinism_reduce_det")
    print("")

    # ── 1. the problem: a sequential sum is a different function per chunking ─
    print("[1] sequential sum, same data, different chunkings")
    var d10 = big_then_ones(1 << 10)
    var n10 = len(d10)
    var seen = List[Float64]()
    var probe = chunk_grid(n10)
    for i in range(len(probe)):
        var g = det_naive_sum_chunked(d10, n10, probe[i]).value
        var novel = True
        for j in range(len(seen)):
            if seen[j] == g:
                novel = False
        if novel:
            seen.append(g)
    print("  exact             = 10000000000001024")
    print("  whole-array       =", det_naive_sum(d10, n10).value)
    print("  distinct answers over", len(probe), "chunkings =", len(seen))
    for j in range(len(seen)):
        print("    ", seen[j])
    if len(seen) > 1:
        print("  ✅ the baseline is genuinely order-dependent, so the invariance below is",
              "a result and not a tautology")
    else:
        failures += 1
        print("  ❌ the baseline gave one answer; this data cannot distinguish orderings")
    print("")

    # ── 2. the tree: bit-identical under every chunking ──────────────────────
    print("[2] det_sum vs det_sum_chunked, asserted with ==")
    var violations = 0
    var compared = 0

    var d16 = big_then_ones(1 << 16)
    var d20 = big_then_ones(1 << 20)
    var rag = ragged(1037)

    var whole10 = det_sum(d10, n10)
    for i in range(len(probe)):
        compared += 1
        if det_sum_chunked(d10, n10, probe[i]).value != whole10.value:
            violations += 1
            print("  ❌ n=" + String(n10), "chunk=" + String(probe[i]))

    var whole16 = det_sum(d16, len(d16))
    var g16 = chunk_grid(len(d16))
    for i in range(len(g16)):
        compared += 1
        if det_sum_chunked(d16, len(d16), g16[i]).value != whole16.value:
            violations += 1
            print("  ❌ n=" + String(len(d16)), "chunk=" + String(g16[i]))

    var whole20 = det_sum(d20, len(d20))
    var g20 = List[Int]()
    g20.append(1)
    g20.append(3)
    g20.append(4096)
    g20.append(len(d20) // 2)
    g20.append(len(d20))
    for i in range(len(g20)):
        compared += 1
        if det_sum_chunked(d20, len(d20), g20[i]).value != whole20.value:
            violations += 1
            print("  ❌ n=" + String(len(d20)), "chunk=" + String(g20[i]))

    # Every chunk size from 1 to 60 on ragged data: the alignment of a chunk boundary
    # against the tree's aligned blocks is what this sweeps.
    var whole_rag = det_sum(rag, len(rag))
    for c in range(1, 61):
        compared += 1
        if det_sum_chunked(rag, len(rag), c).value != whole_rag.value:
            violations += 1
            print("  ❌ ragged n=" + String(len(rag)), "chunk=" + String(c))

    print("  comparisons =", compared, " violations =", violations)
    print("  tree value at n=" + String(n10), "=", whole10.value, "(exact:",
          "10000000000001024)")
    if violations == 0:
        print("  ✅ every chunking produced the SAME Float64 bit pattern")
    else:
        failures += 1
        print("  ❌", violations, "chunkings disagreed with the whole-array reduction")
    print("")

    # ── 3. what it costs ─────────────────────────────────────────────────────
    print("[3] cost per element (JIT — see the docstring for compiled figures)")
    var nb = len(d20)
    for _ in range(WARMUP):
        var w = det_sum(d20, nb).value + det_naive_sum(d20, nb).value
        if w == 0.0:
            print("  unreachable")
    var t0 = perf_counter_ns()
    var r_naive = det_naive_sum(d20, nb)
    var t1 = perf_counter_ns()
    var r_tree = det_sum(d20, nb)
    var t2 = perf_counter_ns()
    var r_kah = det_kahan_sum(d20, nb)
    var t3 = perf_counter_ns()
    var r_neu = det_neumaier_sum(d20, nb)
    var t4 = perf_counter_ns()
    var ns_naive = _ns_per(t1 - t0, nb, 1)
    var ns_tree = _ns_per(t2 - t1, nb, 1)
    var ns_kah = _ns_per(t3 - t2, nb, 1)
    var ns_neu = _ns_per(t4 - t3, nb, 1)
    print("  n =", nb)
    print("  sequential  ns/elem =", ns_naive, " value", r_naive.value)
    print("  fixed tree  ns/elem =", ns_tree, " value", r_tree.value)
    print("  kahan       ns/elem =", ns_kah, " value", r_kah.value)
    print("  neumaier    ns/elem =", ns_neu, " value", r_neu.value)
    var ratio = ns_tree / ns_naive if ns_naive > 0.0 else 999.0
    print("  tree / sequential =", ratio, "x")
    if ratio <= 20.0:
        print("  ✅ the tree costs", ratio, "x a sequential sum — a real cost, gated at 20x")
    else:
        failures += 1
        print("  ❌ the tree costs", ratio, "x a sequential sum; something regressed")
    print("")

    # ── 4. compensation reduces error; it does not make addition associative ──
    print("[4] compensated summation, and its limits")
    var canc = List[Float64]()
    canc.append(1.0)
    canc.append(1e100)
    canc.append(1.0)
    canc.append(-1e100)
    var c_naive = det_naive_sum(canc, 4).value
    var c_kah = det_kahan_sum(canc, 4).value
    var c_tree = det_sum(canc, 4).value
    var c_neu = det_neumaier_sum(canc, 4).value
    print("  [1.0, 1e100, 1.0, -1e100], exact 2.0")
    print("    sequential", c_naive, " kahan", c_kah, " tree", c_tree, " neumaier", c_neu)
    if c_kah == 0.0 and c_neu == 2.0:
        print("  ✅ the frozen kahan_sum's documented limit reproduces, and Neumaier",
              "recovers the exact answer — which is why both exist")
    else:
        failures += 1
        print("  ❌ expected kahan 0.0 and neumaier 2.0")
    # Neumaier is sequential, so it must NOT be chunk-invariant.
    var tail = List[Float64]()
    tail.append(canc[2])
    tail.append(canc[3])
    var neu_split = det_neumaier_sum(canc, 2).value + det_neumaier_sum(tail, 2).value
    print("  neumaier whole", c_neu, " in two halves", neu_split)
    if neu_split != c_neu:
        print("  ✅ Neumaier is NOT chunk-invariant, exactly as the module says")
    else:
        failures += 1
        print("  ❌ Neumaier came out chunk-invariant here; the module's claim that only",
              "det_sum is reproducible would need restating")
    print("")

    # ── 5. absent, not zero ──────────────────────────────────────────────────
    print("[5] no-answer paths")
    var empty = List[Float64]()
    var huge = List[Float64]()
    huge.append(1.7e308)
    huge.append(1.7e308)
    var short = List[Float64]()
    short.append(1.0)

    var absent_ok = 0
    var absent_want = 5

    var m0 = det_mean(empty, 0)
    if not m0.present and m0.status == DET_EMPTY:
        absent_ok += 1
    else:
        print("  ❌ mean of nothing:", m0.present, det_status_name(m0.status))
    var ov = det_sum(huge, 2)
    if not ov.present and ov.status == DET_ERR_OVERFLOW:
        absent_ok += 1
    else:
        print("  ❌ overflowed sum:", ov.present, det_status_name(ov.status))
    var oc = det_sum(short, 25)
    if not oc.present and oc.status == DET_ERR_COUNT:
        absent_ok += 1
    else:
        print("  ❌ count past the end:", oc.present, det_status_name(oc.status))
    var ch = det_sum_chunked(short, 1, 0)
    if not ch.present and ch.status == DET_ERR_CHUNK:
        absent_ok += 1
    else:
        print("  ❌ chunk below one:", ch.present, det_status_name(ch.status))
    var dd = det_dot(short, empty, 1)
    if not dd.present:
        absent_ok += 1
    else:
        print("  ❌ dot over a shorter second list:", dd.present,
              det_status_name(dd.status))

    # And the answers that DO exist are present under DET_OK.
    var s0 = det_sum(empty, 0)
    var sq = det_sum_squares(short, 1)
    print("  absent-as-required", absent_ok, "of", absent_want)
    if absent_ok == absent_want and s0.present and s0.status == DET_OK \
            and s0.value == 0.0 and sq.present and sq.value == 1.0:
        print("  ✅ five no-answer paths absent under a non-success status; sum of nothing",
              "is still 0 and present")
    else:
        failures += 1
        print("  ❌ the absent/present split is not being honoured")
    print("")

    if failures == 0:
        print("BENCH_GATE determinism_reduce_det PASS")
    else:
        print("BENCH_GATE determinism_reduce_det FAIL " + String(failures))
        raise Error(
            "bench_determinism_reduce_det: " + String(failures) + " gate failure(s)"
        )
