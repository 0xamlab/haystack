"""bench_groupby_fused.mojo — timing gates for the fused / radix / coded grouping paths.

Hand-written, not auto-generated. `benchmark_mojo_vs_python.py` only writes
`bench_<lib>.mojo` for libraries in the runtime inventory, and `query/` is in
`_SKIP_RUNTIME_DIRS`, so no generated file can collide with this name.

What is being measured
----------------------
1. FUSION (cause 1): three aggregates by one key at 1e7 rows — three `group_by`
   passes (round 1's only option, the H2O q4/q5 shape) against ONE
   `group_by_many` pass, at BOTH 100 groups and 100k groups. The fused pass
   hashes and probes each row once instead of three times; the saving scales
   with how expensive the probe is, so it is modest when the table is
   cache-resident (measured ~1.5x at 100 groups) and large when it is not
   (measured ~5x at 100k groups, where the fused pass also rides the radix path).
2. RADIX (cause 2): 1e7 rows over 100k groups (the H2O q3/q5/q7 key shape) —
   the band-merge path against the radix-partitioned path at equal workers,
   plus a REPORTED (not gated) sweep over group counts from 100 to 100k, which
   is the measurement `RADIX_MIN_GROUPS` was chosen from.
3. CODED (cause 3): sum by a 100-code key at 1e7 rows — the hash path against
   the code-indexed dense-array path, plus the refusal probe (a key at the
   cardinality must refuse, never index).

Gate
----
Fails loudly on properties, not on absolute nanoseconds:
  * every fused/radix/coded result must EQUAL its reference — group set,
    first-appearance order, counts, values (bit-exact where the fold order or
    merge association is shared; the radix path owes bit-equality to SERIAL);
  * fused >= 1.35x over three passes at 100 groups (measured ~1.5x) and
    >= 2.5x at 100k groups (measured ~5x) — each floor sits under its own
    measurement, because the two shapes have different physics (see above);
  * radix >= 1.3x over banded at 100k groups (measured ~2.5x);
  * coded >= 1.2x over hashed at 100 codes (measured ~1.6x);
  * a key at the cardinality refuses with GROUP_CODED_KEY_NOT_A_CODE.

Emits one `BENCH_GATE groupby_<fused|radix|coded> PASS|FAIL` line per section.
"""
from std.sys import info
from std.time import perf_counter_ns

from columnar.array import Float64Array, float64_from_list
from columnar.batch import RecordBatch, schema_of
from numeric.contract import AGG_AVG, AGG_SUM
from query.aggregate import (
    GROUP_CODED_KEY_NOT_A_CODE,
    GroupedResult,
    ManyGroupedResult,
    group_by,
    group_by_coded,
    group_by_many,
    group_by_many_banded,
    group_by_many_parallel,
    group_by_many_radix,
    group_by_parallel,
)

comptime REPS: Int = 2
comptime N_ROWS: Int = 10_000_000


def _lcg_next(state: UInt64) -> UInt64:
    return state * 6364136223846793005 + 1442695040888963407


def _batch(n_rows: Int, n_groups: Int) -> RecordBatch:
    """k in 0..n_groups-1; v1/v2/v3 integer-valued so sums compare exactly."""
    var state: UInt64 = 0x9E3779B97F4A7C15
    var k = List[Float64](capacity=n_rows)
    var v1 = List[Float64](capacity=n_rows)
    var v2 = List[Float64](capacity=n_rows)
    var v3 = List[Float64](capacity=n_rows)
    for _ in range(n_rows):
        state = _lcg_next(state)
        k.append(Float64(Int((state >> 33) % UInt64(n_groups))))
        state = _lcg_next(state)
        v1.append(Float64(Int((state >> 33) % 1000)))
        state = _lcg_next(state)
        v2.append(Float64(Int((state >> 33) % 500)))
        state = _lcg_next(state)
        v3.append(Float64(Int((state >> 33) % 100)))
    var names = List[String]()
    names.append("k")
    names.append("v1")
    names.append("v2")
    names.append("v3")
    var cols = List[Float64Array]()
    cols.append(float64_from_list(k^))
    cols.append(float64_from_list(v1^))
    cols.append(float64_from_list(v2^))
    cols.append(float64_from_list(v3^))
    return RecordBatch(schema_of(names^), cols^, n_rows)


def _rekey(batch: RecordBatch, n_groups: Int) -> RecordBatch:
    """The same value columns under a fresh key of different cardinality."""
    var state: UInt64 = 0xBADC0FFEE0DDF00D
    var k = List[Float64](capacity=batch.n_rows)
    for _ in range(batch.n_rows):
        state = _lcg_next(state)
        k.append(Float64(Int((state >> 33) % UInt64(n_groups))))
    var names = List[String]()
    names.append("k")
    names.append("v1")
    names.append("v2")
    names.append("v3")
    var cols = List[Float64Array]()
    cols.append(float64_from_list(k^))
    cols.append(batch.column(1))
    cols.append(batch.column(2))
    cols.append(batch.column(3))
    return RecordBatch(schema_of(names^), cols^, batch.n_rows)


def _many_matches_grouped(many: ManyGroupedResult, agg: Int, single: GroupedResult) -> Bool:
    if many.n_groups() != single.n_groups() or many.key_width != 1:
        return False
    if many.null_key_rows != single.null_key_rows:
        return False
    for g in range(single.n_groups()):
        if many.key_tuples[g] != single.keys[g]:
            return False
        if many.value_at(g, agg) != single.values[g]:
            return False
        if many.count_at(g, agg) != single.counts[g]:
            return False
    return True


def _many_identical_exact(a: ManyGroupedResult, b: ManyGroupedResult) -> Bool:
    if a.n_groups() != b.n_groups() or a.key_width != b.key_width:
        return False
    if a.n_aggs != b.n_aggs or a.null_key_rows != b.null_key_rows:
        return False
    for i in range(len(a.key_tuples)):
        if a.key_tuples[i] != b.key_tuples[i]:
            return False
    for i in range(len(a.values)):
        if a.values[i] != b.values[i]:
            return False
        if a.counts[i] != b.counts[i]:
            return False
    return True


def main() raises:
    var cores = info.num_physical_cores()
    var failures_fused = 0
    var failures_radix = 0
    var failures_coded = 0

    var kc = List[Int]()
    kc.append(0)
    var vc3 = List[Int]()
    vc3.append(1)
    vc3.append(2)
    vc3.append(3)
    var sums3 = List[Int]()
    sums3.append(AGG_SUM)
    sums3.append(AGG_SUM)
    sums3.append(AGG_SUM)
    var vc1 = List[Int]()
    vc1.append(1)
    var sum1 = List[Int]()
    sum1.append(AGG_SUM)

    # ══ 1. fusion: one pass vs three, 100 groups, 1e7 rows ═════════════════════
    print("=== fused: 3 x group_by vs 1 x group_by_many (1e7 rows, 100 groups, " + String(cores) + " workers) ===")
    var low = _batch(N_ROWS, 100)
    var three_best: Float64 = 1e30
    var fused_best: Float64 = 1e30
    var a1 = group_by(low, 0, 1, AGG_SUM)  # warmup + references
    var a2 = group_by(low, 0, 2, AGG_SUM)
    var a3 = group_by(low, 0, 3, AGG_SUM)
    var fused = group_by_many(low, kc, vc3, sums3)
    for _ in range(REPS):
        var t0 = perf_counter_ns()
        a1 = group_by(low, 0, 1, AGG_SUM)
        a2 = group_by(low, 0, 2, AGG_SUM)
        a3 = group_by(low, 0, 3, AGG_SUM)
        var t1 = perf_counter_ns()
        fused = group_by_many(low, kc, vc3, sums3)
        var t2 = perf_counter_ns()
        var three = Float64(Int(t1 - t0)) / 1e9
        var one = Float64(Int(t2 - t1)) / 1e9
        if three < three_best:
            three_best = three
        if one < fused_best:
            fused_best = one
        print("  three_pass=" + String(three) + "s  fused=" + String(one) + "s")
    var fused_speedup = three_best / fused_best
    var fused_equal = (
        _many_matches_grouped(fused, 0, a1)
        and _many_matches_grouped(fused, 1, a2)
        and _many_matches_grouped(fused, 2, a3)
    )
    print("  best: three_pass=" + String(three_best) + "s  fused=" + String(fused_best)
          + "s  speedup=" + String(fused_speedup) + "x  exact_match=" + String(fused_equal))
    if not fused_equal:
        failures_fused += 1
        print("  ❌ fused columns diverged from the three separate passes")
    else:
        print("  ✅ fused: every column bit-equal to its own pass, order included")
    if fused_speedup < 1.35:
        failures_fused += 1
        print("  ❌ fused speedup " + String(fused_speedup) + "x < 1.35x over three passes at 100 groups")
    else:
        print("  ✅ fused speedup " + String(fused_speedup) + "x >= 1.35x at 100 groups")

    # The same question where the probe is NOT cache-resident: 100k groups, the
    # H2O q5 shape. This is where cause 1 and cause 2 compound.
    print("")
    print("=== fused: 3 x group_by vs 1 x group_by_many (1e7 rows, 100k groups) ===")
    var hi_f = _rekey(low, 100_000)
    var hthree_best: Float64 = 1e30
    var hfused_best: Float64 = 1e30
    var h1 = group_by(hi_f, 0, 1, AGG_SUM)
    var h2 = group_by(hi_f, 0, 2, AGG_SUM)
    var h3 = group_by(hi_f, 0, 3, AGG_SUM)
    var hfused = group_by_many(hi_f, kc, vc3, sums3)
    for _ in range(REPS):
        var ht0 = perf_counter_ns()
        h1 = group_by(hi_f, 0, 1, AGG_SUM)
        h2 = group_by(hi_f, 0, 2, AGG_SUM)
        h3 = group_by(hi_f, 0, 3, AGG_SUM)
        var ht1 = perf_counter_ns()
        hfused = group_by_many(hi_f, kc, vc3, sums3)
        var ht2 = perf_counter_ns()
        var hthree = Float64(Int(ht1 - ht0)) / 1e9
        var hone = Float64(Int(ht2 - ht1)) / 1e9
        if hthree < hthree_best:
            hthree_best = hthree
        if hone < hfused_best:
            hfused_best = hone
        print("  three_pass=" + String(hthree) + "s  fused=" + String(hone) + "s")
    var hfused_speedup = hthree_best / hfused_best
    var hfused_equal = (
        _many_matches_grouped(hfused, 0, h1)
        and _many_matches_grouped(hfused, 1, h2)
        and _many_matches_grouped(hfused, 2, h3)
    )
    print("  best: three_pass=" + String(hthree_best) + "s  fused=" + String(hfused_best)
          + "s  speedup=" + String(hfused_speedup) + "x  exact_match=" + String(hfused_equal))
    if not hfused_equal:
        failures_fused += 1
        print("  ❌ fused columns diverged from the three passes at 100k groups")
    else:
        print("  ✅ fused at 100k groups: every column bit-equal to its own pass")
    if hfused_speedup < 2.5:
        failures_fused += 1
        print("  ❌ fused speedup " + String(hfused_speedup) + "x < 2.5x over three passes at 100k groups")
    else:
        print("  ✅ fused speedup " + String(hfused_speedup) + "x >= 2.5x at 100k groups")

    # ══ 2. radix vs banded: the 100k-group merge, and the crossover sweep ══════
    print("")
    print("=== radix vs banded sweep (1e7 rows, 2 aggregates, " + String(cores) + " workers; reported) ===")
    var sizes = List[Int]()
    sizes.append(100)
    sizes.append(1000)
    sizes.append(10000)
    sizes.append(32768)
    sizes.append(50000)
    sizes.append(100000)
    var vc2 = List[Int]()
    vc2.append(1)
    vc2.append(2)
    var ops2 = List[Int]()
    ops2.append(AGG_SUM)
    ops2.append(AGG_AVG)
    for si in range(len(sizes)):
        var g = sizes[si]
        var b = _rekey(low, g)
        var _wb = group_by_many_banded(b, kc, vc2, ops2, cores)
        var t0 = perf_counter_ns()
        var _rb = group_by_many_banded(b, kc, vc2, ops2, cores)
        var t1 = perf_counter_ns()
        var _wr = group_by_many_radix(b, kc, vc2, ops2, cores)
        var t2 = perf_counter_ns()
        var _rr = group_by_many_radix(b, kc, vc2, ops2, cores)
        var t3 = perf_counter_ns()
        var banded_s = Float64(Int(t1 - t0)) / 1e9
        var radix_s = Float64(Int(t3 - t2)) / 1e9
        print(
            "  groups=" + String(g)
            + "  banded=" + String(banded_s) + "s"
            + "  radix=" + String(radix_s) + "s"
            + "  radix_speedup=" + String(banded_s / radix_s) + "x"
        )

    print("")
    print("=== radix gate: 1e7 rows, 100k groups ===")
    var hi = _rekey(low, 100_000)
    var serial_ref = group_by_many_parallel(hi, kc, vc2, ops2, 1)
    var banded_best: Float64 = 1e30
    var radix_best: Float64 = 1e30
    var banded_out = group_by_many_banded(hi, kc, vc2, ops2, cores)
    var radix_out = group_by_many_radix(hi, kc, vc2, ops2, cores)
    for _ in range(REPS):
        var t4 = perf_counter_ns()
        banded_out = group_by_many_banded(hi, kc, vc2, ops2, cores)
        var t5 = perf_counter_ns()
        radix_out = group_by_many_radix(hi, kc, vc2, ops2, cores)
        var t6 = perf_counter_ns()
        var bs = Float64(Int(t5 - t4)) / 1e9
        var rs = Float64(Int(t6 - t5)) / 1e9
        if bs < banded_best:
            banded_best = bs
        if rs < radix_best:
            radix_best = rs
        print("  banded=" + String(bs) + "s  radix=" + String(rs) + "s")
    var radix_speedup = banded_best / radix_best
    # The radix path owes SERIAL bit-equality (per-group folds run in global row
    # order), order included — a stronger check than banded's merge tolerance.
    var radix_equal = _many_identical_exact(radix_out, serial_ref)
    print("  best: banded=" + String(banded_best) + "s  radix=" + String(radix_best)
          + "s  speedup=" + String(radix_speedup) + "x  exact_match_vs_serial=" + String(radix_equal))
    if not radix_equal:
        failures_radix += 1
        print("  ❌ radix result diverged from serial — speed without agreement is worthless")
    else:
        print("  ✅ radix == serial bit-for-bit at 100k groups, order included")
    if radix_speedup < 1.3:
        failures_radix += 1
        print("  ❌ radix speedup " + String(radix_speedup) + "x < 1.3x over banded at 100k groups")
    else:
        print("  ✅ radix speedup " + String(radix_speedup) + "x >= 1.3x over banded")

    # ══ 3. coded vs hashed: 100 codes, 1e7 rows ════════════════════════════════
    print("")
    print("=== coded gate: dense array by code vs hash table (1e7 rows, 100 codes) ===")
    var hash_best: Float64 = 1e30
    var coded_best: Float64 = 1e30
    var hash_out = group_by(low, 0, 1, AGG_SUM)
    var coded_out = group_by_coded(low, 0, 100, vc1, sum1)
    for _ in range(REPS):
        var t7 = perf_counter_ns()
        hash_out = group_by(low, 0, 1, AGG_SUM)
        var t8 = perf_counter_ns()
        coded_out = group_by_coded(low, 0, 100, vc1, sum1)
        var t9 = perf_counter_ns()
        var hs = Float64(Int(t8 - t7)) / 1e9
        var cs = Float64(Int(t9 - t8)) / 1e9
        if hs < hash_best:
            hash_best = hs
        if cs < coded_best:
            coded_best = cs
        print("  hashed=" + String(hs) + "s  coded=" + String(cs) + "s")
    var coded_speedup = hash_best / coded_best
    var coded_equal = coded_out.ok() and _many_matches_grouped(coded_out.result, 0, hash_out)
    print("  best: hashed=" + String(hash_best) + "s  coded=" + String(coded_best)
          + "s  speedup=" + String(coded_speedup) + "x  exact_match=" + String(coded_equal))
    if not coded_equal:
        failures_coded += 1
        print("  ❌ coded result diverged from the hash path")
    else:
        print("  ✅ coded == hashed: groups, order, counts, sums")
    if coded_speedup < 1.2:
        failures_coded += 1
        print("  ❌ coded speedup " + String(coded_speedup) + "x < 1.2x over the hash path")
    else:
        print("  ✅ coded speedup " + String(coded_speedup) + "x >= 1.2x")
    # The refusal is part of the contract: cardinality 99 makes key 99.0 (which
    # the data contains) out of range, and that must be a typed refusal.
    var refused = group_by_coded(low, 0, 99, vc1, sum1)
    if refused.status != GROUP_CODED_KEY_NOT_A_CODE or refused.result.n_groups() != 0:
        failures_coded += 1
        print("  ❌ an out-of-range code did not refuse: status " + String(refused.status))
    else:
        print("  ✅ a key at the cardinality refuses with key_not_a_code, empty result")

    # ── gate lines ──────────────────────────────────────────────────────────────
    print("")
    if failures_fused == 0:
        print("BENCH_GATE groupby_fused PASS")
    else:
        print("BENCH_GATE groupby_fused FAIL " + String(failures_fused))
    if failures_radix == 0:
        print("BENCH_GATE groupby_radix PASS")
    else:
        print("BENCH_GATE groupby_radix FAIL " + String(failures_radix))
    if failures_coded == 0:
        print("BENCH_GATE groupby_coded PASS")
    else:
        print("BENCH_GATE groupby_coded FAIL " + String(failures_coded))
    var total = failures_fused + failures_radix + failures_coded
    if total > 0:
        raise Error("bench_groupby_fused: " + String(total) + " gate failure(s)")
