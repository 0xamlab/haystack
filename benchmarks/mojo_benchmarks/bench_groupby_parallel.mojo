"""bench_groupby_parallel.mojo — timing gate for the parallel grouping path.

Hand-written, not auto-generated. `benchmark_mojo_vs_python.py` only writes
`bench_<lib>.mojo` for libraries in the runtime inventory, and `query/` is in
`_SKIP_RUNTIME_DIRS`, so no generated file can collide with this name.

What is being measured
----------------------
1. The crossover: serial vs parallel ns/row from 4k to 1M rows on a 100-group
   key. Reported, not gated — the exact crossing point moves with machine load,
   and `PARALLEL_MIN_ROWS` was chosen from this table on an idle-ish host.
2. Single-key grouping at 1e7 rows / 100 groups: the H2O q1 shape.
3. Composite-key grouping at 1e7 rows / 10,000 groups: the H2O q2 shape, which
   is also the shape whose per-row `List` allocation the reused key buffer
   removed.

Gate
----
Fails loudly on the properties that must hold, not on absolute nanoseconds:
  * parallel and serial must agree EXACTLY on the 1e7-row integer data —
    group set, first-appearance order, counts, and sums (integer-valued data
    makes every partial sum exactly representable, so association cannot move
    the total and exact equality is a fair gate);
  * the parallel path must beat serial by >= 2.5x at 1e7 rows, single AND
    composite key (measured ~5-8x on 16 physical cores; 2.5 is the flap floor);
  * `planned_workers` must refuse to fan out below PARALLEL_MIN_ROWS.

Emits `BENCH_GATE groupby_parallel PASS|FAIL` for `make bench-mojo-gate`-style
consumption.
"""
from std.sys import info
from std.time import perf_counter_ns

from columnar.array import Float64Array, float64_from_list
from columnar.batch import RecordBatch, schema_of
from numeric.contract import AGG_SUM
from query.aggregate import (
    GroupedResult,
    MultiGroupedResult,
    PARALLEL_MIN_ROWS,
    group_by_multi_parallel,
    group_by_parallel,
    planned_workers,
)

comptime WARMUP: Int = 1
comptime REPS: Int = 2


def _lcg_next(state: UInt64) -> UInt64:
    return state * 6364136223846793005 + 1442695040888963407


def _batch(n_rows: Int, n_groups: Int, second_key: Bool) -> RecordBatch:
    """key1 (and optionally key2) uniform over n_groups; integer values 0..999."""
    var state: UInt64 = 0x9E3779B97F4A7C15
    var k1 = List[Float64](capacity=n_rows)
    var k2 = List[Float64](capacity=n_rows)
    var v = List[Float64](capacity=n_rows)
    for _ in range(n_rows):
        state = _lcg_next(state)
        k1.append(Float64(Int((state >> 33) % UInt64(n_groups))))
        if second_key:
            state = _lcg_next(state)
            k2.append(Float64(Int((state >> 33) % UInt64(n_groups))))
        state = _lcg_next(state)
        v.append(Float64(Int((state >> 33) % 1000)))

    var names = List[String]()
    names.append("k1")
    if second_key:
        names.append("k2")
    names.append("v")
    var cols = List[Float64Array]()
    cols.append(float64_from_list(k1^))
    if second_key:
        cols.append(float64_from_list(k2^))
    cols.append(float64_from_list(v^))
    return RecordBatch(schema_of(names^), cols^, n_rows)


def _grouped_equal(a: GroupedResult, b: GroupedResult) -> Bool:
    if a.n_groups() != b.n_groups() or a.null_key_rows != b.null_key_rows:
        return False
    for i in range(a.n_groups()):
        if a.keys[i] != b.keys[i] or a.values[i] != b.values[i]:
            return False
        if a.counts[i] != b.counts[i]:
            return False
    return True


def _multi_equal(a: MultiGroupedResult, b: MultiGroupedResult) -> Bool:
    if a.n_groups() != b.n_groups() or a.key_width != b.key_width:
        return False
    for i in range(len(a.key_tuples)):
        if a.key_tuples[i] != b.key_tuples[i]:
            return False
    for i in range(a.n_groups()):
        if a.values[i] != b.values[i] or a.counts[i] != b.counts[i]:
            return False
    return True


def main() raises:
    var cores = info.num_physical_cores()
    print("=== parallel group_by: crossover sweep (100 groups, serial vs " + String(cores) + " workers) ===")
    var sizes = List[Int]()
    sizes.append(4096)
    sizes.append(16384)
    sizes.append(65536)
    sizes.append(262144)
    sizes.append(1048576)
    for si in range(len(sizes)):
        var n = sizes[si]
        var b = _batch(n, 100, False)
        var _w1 = group_by_parallel(b, 0, 1, AGG_SUM, 1)
        var t0 = perf_counter_ns()
        var _r1 = group_by_parallel(b, 0, 1, AGG_SUM, 1)
        var t1 = perf_counter_ns()
        var _w2 = group_by_parallel(b, 0, 1, AGG_SUM, cores)
        var t2 = perf_counter_ns()
        var _r2 = group_by_parallel(b, 0, 1, AGG_SUM, cores)
        var t3 = perf_counter_ns()
        var serial_ns = Float64(Int(t1 - t0)) / Float64(n)
        var par_ns = Float64(Int(t3 - t2)) / Float64(n)
        print(
            "  rows=" + String(n)
            + "  serial_ns/row=" + String(serial_ns)
            + "  parallel_ns/row=" + String(par_ns)
            + "  speedup=" + String(serial_ns / par_ns) + "x"
            + ("   <- PARALLEL_MIN_ROWS" if n == PARALLEL_MIN_ROWS else "")
        )

    print("")
    print("=== single key, 1e7 rows, 100 groups (H2O q1 shape) ===")
    var big = _batch(10_000_000, 100, False)
    var serial_best: Float64 = 1e30
    var par_best: Float64 = 1e30
    var serial_out = group_by_parallel(big, 0, 1, AGG_SUM, 1)  # warmup + reference
    var par_out = group_by_parallel(big, 0, 1, AGG_SUM, cores)
    for _ in range(REPS):
        var t4 = perf_counter_ns()
        serial_out = group_by_parallel(big, 0, 1, AGG_SUM, 1)
        var t5 = perf_counter_ns()
        par_out = group_by_parallel(big, 0, 1, AGG_SUM, cores)
        var t6 = perf_counter_ns()
        var s = Float64(Int(t5 - t4)) / 1e9
        var p = Float64(Int(t6 - t5)) / 1e9
        if s < serial_best:
            serial_best = s
        if p < par_best:
            par_best = p
        print("  serial=" + String(s) + "s  parallel=" + String(p) + "s")
    var single_speedup = serial_best / par_best
    var single_equal = _grouped_equal(serial_out, par_out)
    print("  best: serial=" + String(serial_best) + "s  parallel=" + String(par_best)
          + "s  speedup=" + String(single_speedup) + "x  exact_match=" + String(single_equal))

    print("")
    print("=== composite key, 1e7 rows, 100x100 groups (H2O q2 shape) ===")
    var big2 = _batch(10_000_000, 100, True)
    var key_cols = List[Int]()
    key_cols.append(0)
    key_cols.append(1)
    var mserial_best: Float64 = 1e30
    var mpar_best: Float64 = 1e30
    var mserial_out = group_by_multi_parallel(big2, key_cols, 2, AGG_SUM, 1)
    var mpar_out = group_by_multi_parallel(big2, key_cols, 2, AGG_SUM, cores)
    for _ in range(REPS):
        var t7 = perf_counter_ns()
        mserial_out = group_by_multi_parallel(big2, key_cols, 2, AGG_SUM, 1)
        var t8 = perf_counter_ns()
        mpar_out = group_by_multi_parallel(big2, key_cols, 2, AGG_SUM, cores)
        var t9 = perf_counter_ns()
        var s = Float64(Int(t8 - t7)) / 1e9
        var p = Float64(Int(t9 - t8)) / 1e9
        if s < mserial_best:
            mserial_best = s
        if p < mpar_best:
            mpar_best = p
        print("  serial=" + String(s) + "s  parallel=" + String(p) + "s")
    var multi_speedup = mserial_best / mpar_best
    var multi_equal = _multi_equal(mserial_out, mpar_out)
    print("  best: serial=" + String(mserial_best) + "s  parallel=" + String(mpar_best)
          + "s  speedup=" + String(multi_speedup) + "x  exact_match=" + String(multi_equal))

    # ── gate ──────────────────────────────────────────────────────────────────
    print("")
    var failures = 0

    if not single_equal:
        failures += 1
        print("  ❌ single-key parallel result diverged from serial — speed without agreement is worthless")
    else:
        print("  ✅ single-key: group set, order, counts and sums exactly equal, 1 vs "
              + String(cores) + " workers")

    if not multi_equal:
        failures += 1
        print("  ❌ composite-key parallel result diverged from serial")
    else:
        print("  ✅ composite-key: tuples, order, counts and sums exactly equal")

    if single_speedup < 2.5:
        failures += 1
        print("  ❌ single-key speedup " + String(single_speedup) + "x < 2.5x at 1e7 rows")
    else:
        print("  ✅ single-key speedup " + String(single_speedup) + "x >= 2.5x")

    if multi_speedup < 2.5:
        failures += 1
        print("  ❌ composite-key speedup " + String(multi_speedup) + "x < 2.5x at 1e7 rows")
    else:
        print("  ✅ composite-key speedup " + String(multi_speedup) + "x >= 2.5x")

    if planned_workers(PARALLEL_MIN_ROWS - 1, cores) != 1:
        failures += 1
        print("  ❌ planned_workers fans out below PARALLEL_MIN_ROWS — small inputs pay the spawn")
    else:
        print("  ✅ planned_workers keeps inputs below " + String(PARALLEL_MIN_ROWS) + " rows on one thread")

    if failures == 0:
        print("")
        print("BENCH_GATE groupby_parallel PASS")
    else:
        print("")
        print("BENCH_GATE groupby_parallel FAIL " + String(failures))
        raise Error("bench_groupby_parallel: " + String(failures) + " gate failure(s)")
