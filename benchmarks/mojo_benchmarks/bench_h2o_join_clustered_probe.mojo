"""bench_h2o_join_clustered_probe.mojo — investigation-only harness for H2O join q5.

Not a submission and not shipped as a claim anywhere: this exists purely to measure,
phase by phase, whether partition-clustering the probe (`_hash_join_probe_parallel_
clustered` in `query.join`) actually reduces q5's remaining DuckDB gap versus the
row-band partitioned probe it is an alternative to (`_hash_join_probe_parallel_
partitioned`), and if so, which of its three phases (bucket / clustered-count /
clustered-emit) the time actually goes to.

Calls the private build/probe functions directly (same data, same
`_build_right_index_parallel` build for every path measured) rather than going
through `hash_join_indices`, so the comparison isolates the PROBE shape only --
nothing about the build, the gather, or `materialize` differs between runs.
"""
from std.time import perf_counter_ns

from columnar.array import Float64Array, float64_from_list
from columnar.hash_index import HashIndex
from query.join import (
    JOIN_INNER,
    _build_right_index_parallel,
    _clustered_count_matches,
    _clustered_emit_matches,
    _hash_join_probe_parallel_clustered,
    _hash_join_probe_parallel_partitioned,
    _partition_left_rows_for_probe,
)

comptime DATA_DIR: String = "/tmp/h2o_join"
comptime N_X: Int = 10_000_000
comptime N_BIG: Int = 10_000_000
comptime REPS: Int = 5
comptime BUILD_WORKERS: Int = 16


def _load_column(table: String, col: String, n_rows: Int) raises -> Float64Array:
    var path = DATA_DIR + "/" + table + "_" + col + ".f64.bin"
    var f = open(path, "r")
    var raw = f.read_bytes()
    f.close()
    if len(raw) != n_rows * 8:
        raise Error(
            path + " is " + String(len(raw)) + " bytes, expected "
            + String(n_rows * 8) + " -- run benchmarks/h2o_join/generate.py first"
        )
    var fp = raw.unsafe_ptr().bitcast[Float64]()
    var values = List[Float64](capacity=n_rows)
    for i in range(n_rows):
        values.append(fp[i])
    return float64_from_list(values^)


def main() raises:
    print("=== H2O join q5, clustered probe vs row-band partitioned probe ===")
    print("  loading id3 columns from " + DATA_DIR + " ...")
    var left_key = _load_column("x", "id3", N_X)
    var right_key = _load_column("big", "id3", N_BIG)
    print("  loaded. building the shared radix-partitioned index once ...")

    var tables = List[HashIndex]()
    var first_row = List[List[Int]]()
    var next_row = List[Int]()
    var build_ok = True
    var t_build0 = perf_counter_ns()
    var _null_keys = _build_right_index_parallel(
        right_key, N_BIG, BUILD_WORKERS, tables, first_row, next_row, build_ok
    )
    var t_build1 = perf_counter_ns()
    if not build_ok:
        raise Error("build reported ok=False -- cannot compare probes without it")
    print(
        "  build done in " + String(Float64(Int(t_build1 - t_build0)) / 1e9) + "s"
        + " (shared by every probe measured below)"
    )
    print("")

    # ── baseline: the row-band partitioned probe already shipping ──────────────────
    var best_baseline = 1e30
    for rep in range(REPS):
        var t0 = perf_counter_ns()
        var result = _hash_join_probe_parallel_partitioned(
            left_key, N_X, tables, first_row, next_row, JOIN_INNER, BUILD_WORKERS
        )
        var t1 = perf_counter_ns()
        var elapsed = Float64(Int(t1 - t0)) / 1e9
        if elapsed < best_baseline:
            best_baseline = elapsed
        if rep == 0:
            print("  baseline rows=" + String(result.n_rows()))
    print("  row-band partitioned probe (baseline): min=" + String(best_baseline) + "s")
    print("")

    # ── clustered probe, end to end (matches the baseline's own call shape) ────────
    var best_clustered = 1e30
    for rep in range(REPS):
        var t0 = perf_counter_ns()
        var result = _hash_join_probe_parallel_clustered(
            left_key, N_X, tables, first_row, next_row, JOIN_INNER, BUILD_WORKERS
        )
        var t1 = perf_counter_ns()
        var elapsed = Float64(Int(t1 - t0)) / 1e9
        if elapsed < best_clustered:
            best_clustered = elapsed
        if rep == 0:
            print("  clustered rows=" + String(result.n_rows()))
    print("  clustered probe (end to end):          min=" + String(best_clustered) + "s")
    print("")

    var speedup = best_baseline / best_clustered
    print(
        "  clustered vs row-band baseline: "
        + String(speedup) + "x"
        + (" (clustered faster)" if speedup > 1.0 else " (clustered SLOWER)")
    )
    print("")

    # ── per-phase breakdown of the clustered path, same REPS, same tables ──────────
    print("  === clustered probe, per-phase breakdown (min over " + String(REPS) + " reps) ===")
    var best_bucket = 1e30
    var best_count = 1e30
    var best_prefix = 1e30
    var best_emit = 1e30
    for rep in range(REPS):
        var prow = List[Int]()
        var phash = List[UInt64]()
        var part_start = List[Int]()
        var bucket_ok = True
        var tb0 = perf_counter_ns()
        var null_keys = _partition_left_rows_for_probe(
            left_key, N_X, BUILD_WORKERS, prow, phash, part_start, bucket_ok
        )
        var tb1 = perf_counter_ns()
        if not bucket_ok:
            raise Error("bucketing reported ok=False")
        var t_bucket = Float64(Int(tb1 - tb0)) / 1e9
        if t_bucket < best_bucket:
            best_bucket = t_bucket

        var match_count = List[Int](length=N_X, fill=0)
        var tc0 = perf_counter_ns()
        var matchable_unmatched = _clustered_count_matches(
            left_key, prow, phash, part_start, tables, first_row, next_row,
            JOIN_INNER, match_count,
        )
        var tc1 = perf_counter_ns()
        var t_count = Float64(Int(tc1 - tc0)) / 1e9
        if t_count < best_count:
            best_count = t_count

        var row_offset = List[Int](length=N_X, fill=0)
        var tp0 = perf_counter_ns()
        var running = 0
        for l in range(N_X):
            row_offset[l] = running
            running += match_count[l]
        var total = running
        var tp1 = perf_counter_ns()
        var t_prefix = Float64(Int(tp1 - tp0)) / 1e9
        if t_prefix < best_prefix:
            best_prefix = t_prefix

        var out_left = List[Int](length=total, fill=0)
        var out_right = List[Int](length=total, fill=0)
        var te0 = perf_counter_ns()
        _clustered_emit_matches(
            left_key, prow, phash, part_start, tables, first_row, next_row,
            JOIN_INNER, row_offset, out_left, out_right,
        )
        var te1 = perf_counter_ns()
        var t_emit = Float64(Int(te1 - te0)) / 1e9
        if t_emit < best_emit:
            best_emit = t_emit

        if rep == 0:
            print(
                "  phase-0 rows=" + String(total)
                + " null_keys=" + String(null_keys)
                + " matchable_unmatched=" + String(matchable_unmatched)
            )

    print("  phase 1 (partition-bucket left rows): min=" + String(best_bucket) + "s")
    print("  phase 2 (clustered count pass):       min=" + String(best_count) + "s")
    print("  phase 3 (prefix sum, sequential):     min=" + String(best_prefix) + "s")
    print("  phase 4 (clustered emit pass):        min=" + String(best_emit) + "s")
    print(
        "  phase sum:                            "
        + String(best_bucket + best_count + best_prefix + best_emit) + "s"
    )
