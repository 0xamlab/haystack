"""bench_h2o_join_direct_address.mojo — investigation-only harness for H2O join q5.

Every constant-factor and loop-shape lever `benchmarks/h2o_join/RESULTS.md` has tried
on q5 (the 10,000,000-row near-1:1 `big.id3` join) works WITHIN the hash-join
algorithm: same `HashIndex`, same radix-partitioned build, a different probe access
pattern. This harness measures a genuinely different ALGORITHM instead:
`_build_direct_address_table` / `_hash_join_probe_parallel_direct_address` in
`query.join`, which replace the hash table with a flat array indexed directly by key —
valid only because `benchmarks/h2o_join/generate.py`'s own `split_xlr` draws `id3` as a
permutation of a dense `1..round(n * 1.1)` range, so every id3 value on both sides sits
in one bounded span and appears at most once per side (verified against the real
`generate.py` source, not assumed).

Measures BOTH phases the algorithm swap touches, since a fair comparison against the
existing radix-partitioned hash build + row-band partitioned probe needs the whole
pipeline, not just the probe:

  1. build:  `_build_right_index_parallel` (hash)  vs `_build_direct_address_table`
  2. probe:  `_hash_join_probe_parallel_partitioned` (hash) vs
             `_hash_join_probe_parallel_direct_address`
  3. total:  build + probe, both algorithms, end to end

Calls the private build/probe functions directly rather than through
`hash_join_indices`, exactly like `bench_h2o_join_clustered_probe.mojo`, so nothing
about `materialize` or the gather differs between the two paths measured -- for the
build/probe phase breakdown. A final section then measures the TRUE full pipeline
(build + probe + `materialize` + checksum, `bench_h2o_join.mojo`'s own q5 shape
exactly) for both algorithms, back to back in this same process, so the number that
belongs next to DuckDB/Polars in `benchmarks/h2o_join/RESULTS.md` is not extrapolated
from the phase breakdown above it.
"""
from std.time import perf_counter_ns

from columnar.array import Float64Array, float64_from_list
from columnar.batch import RecordBatch, schema_of
from query.join import (
    JOIN_INNER,
    _build_direct_address_table,
    _build_right_index_parallel,
    _hash_join_probe_parallel_direct_address,
    _hash_join_probe_parallel_partitioned,
    hash_join_indices,
    materialize,
)
from columnar.hash_index import HashIndex

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
    print("=== H2O join q5, direct-address vs radix-partitioned hash join ===")
    print("  loading id3 columns from " + DATA_DIR + " ...")
    var left_key = _load_column("x", "id3", N_X)
    var right_key = _load_column("big", "id3", N_BIG)
    print("  loaded.")
    print("")

    # ── build phase: hash vs direct-address, min over REPS, fresh build every rep ──
    var best_hash_build = 1e30
    var last_hash_null_keys = 0
    for rep in range(REPS):
        var tables = List[HashIndex]()
        var first_row = List[List[Int]]()
        var next_row = List[Int]()
        var build_ok = True
        var t0 = perf_counter_ns()
        var null_keys = _build_right_index_parallel(
            right_key, N_BIG, BUILD_WORKERS, tables, first_row, next_row, build_ok
        )
        var t1 = perf_counter_ns()
        if not build_ok:
            raise Error("hash build reported ok=False")
        var elapsed = Float64(Int(t1 - t0)) / 1e9
        if elapsed < best_hash_build:
            best_hash_build = elapsed
        last_hash_null_keys = null_keys
    print("  hash build (radix-partitioned):   min=" + String(best_hash_build) + "s"
        + "  null_keys=" + String(last_hash_null_keys))

    var best_da_build = 1e30
    var last_da_null_keys = 0
    var da_ok = False
    for rep in range(REPS):
        var table = List[Int]()
        var key_lo = 0
        var key_hi = 0
        var build_ok = True
        var t0 = perf_counter_ns()
        var null_keys = _build_direct_address_table(
            right_key, N_BIG, BUILD_WORKERS, table, key_lo, key_hi, build_ok
        )
        var t1 = perf_counter_ns()
        da_ok = build_ok
        if not build_ok:
            print("  direct-address build reported ok=False -- shape assumption failed on real data")
            break
        var elapsed = Float64(Int(t1 - t0)) / 1e9
        if elapsed < best_da_build:
            best_da_build = elapsed
        last_da_null_keys = null_keys
        if rep == 0:
            print(
                "  direct-address span: key_lo=" + String(key_lo) + " key_hi=" + String(key_hi)
                + " span=" + String(key_hi - key_lo + 1) + " rows=" + String(N_BIG)
            )
    if not da_ok:
        raise Error("direct-address build did not hold on real q5 data -- see message above")
    print("  direct-address build:             min=" + String(best_da_build) + "s"
        + "  null_keys=" + String(last_da_null_keys))
    var build_speedup = best_hash_build / best_da_build
    print(
        "  build: direct-address vs hash: " + String(build_speedup) + "x"
        + (" (direct-address faster)" if build_speedup > 1.0 else " (direct-address SLOWER)")
    )
    print("")

    # ── probe phase: build ONCE per algorithm, then probe REPS times, min taken ────
    var tables = List[HashIndex]()
    var first_row = List[List[Int]]()
    var next_row = List[Int]()
    var hash_build_ok = True
    _ = _build_right_index_parallel(
        right_key, N_BIG, BUILD_WORKERS, tables, first_row, next_row, hash_build_ok
    )
    if not hash_build_ok:
        raise Error("hash build reported ok=False on the probe-phase build")

    var best_hash_probe = 1e30
    var hash_rows = 0
    for rep in range(REPS):
        var t0 = perf_counter_ns()
        var result = _hash_join_probe_parallel_partitioned(
            left_key, N_X, tables, first_row, next_row, JOIN_INNER, BUILD_WORKERS
        )
        var t1 = perf_counter_ns()
        var elapsed = Float64(Int(t1 - t0)) / 1e9
        if elapsed < best_hash_probe:
            best_hash_probe = elapsed
        if rep == 0:
            hash_rows = result.n_rows()
    print("  hash probe (row-band partitioned): min=" + String(best_hash_probe) + "s"
        + "  rows=" + String(hash_rows))

    var da_table = List[Int]()
    var da_key_lo = 0
    var da_key_hi = 0
    var da_build_ok = True
    _ = _build_direct_address_table(
        right_key, N_BIG, BUILD_WORKERS, da_table, da_key_lo, da_key_hi, da_build_ok
    )
    if not da_build_ok:
        raise Error("direct-address build reported ok=False on the probe-phase build")

    var best_da_probe = 1e30
    var da_rows = 0
    for rep in range(REPS):
        var t0 = perf_counter_ns()
        var result = _hash_join_probe_parallel_direct_address(
            left_key, N_X, da_table, da_key_lo, da_key_hi, JOIN_INNER, BUILD_WORKERS
        )
        var t1 = perf_counter_ns()
        var elapsed = Float64(Int(t1 - t0)) / 1e9
        if elapsed < best_da_probe:
            best_da_probe = elapsed
        if rep == 0:
            da_rows = result.n_rows()
    print("  direct-address probe:              min=" + String(best_da_probe) + "s"
        + "  rows=" + String(da_rows))

    if hash_rows != da_rows:
        raise Error(
            "ROW COUNT MISMATCH: hash=" + String(hash_rows) + " direct_address=" + String(da_rows)
            + " -- the two algorithms disagree on real data, do not trust either speedup number"
        )

    var probe_speedup = best_hash_probe / best_da_probe
    print(
        "  probe: direct-address vs hash: " + String(probe_speedup) + "x"
        + (" (direct-address faster)" if probe_speedup > 1.0 else " (direct-address SLOWER)")
    )
    print("")

    # ── total: build + probe, best-of-REPS numbers from above, both algorithms ─────
    var total_hash = best_hash_build + best_hash_probe
    var total_da = best_da_build + best_da_probe
    var total_speedup = total_hash / total_da
    print("  === total (build + probe, min-of-" + String(REPS) + " each phase) ===")
    print("  hash join total:            " + String(total_hash) + "s")
    print("  direct-address join total:  " + String(total_da) + "s")
    print(
        "  total: direct-address vs hash: " + String(total_speedup) + "x"
        + (" (direct-address faster)" if total_speedup > 1.0 else " (direct-address SLOWER)")
    )
    print("")

    # ── full pipeline: build + probe + materialize + checksum, `bench_h2o_join.mojo`'s
    #    own q5 shape exactly (x.* + big.id1/id2/v2, checksum = sum(v1) + sum(v2) over
    #    the matched rows) -- the number that actually belongs next to DuckDB/Polars,
    #    not an extrapolation from the phase breakdown above. ─────────────────────────
    print("  === full pipeline (build + probe + materialize + checksum) ===")
    var x_id1 = _load_column("x", "id1", N_X)
    var x_id2 = _load_column("x", "id2", N_X)
    var x_v1 = _load_column("x", "v1", N_X)
    var x_names = List[String]()
    x_names.append("id1")
    x_names.append("id2")
    x_names.append("id3")
    x_names.append("v1")
    var x_cols = List[Float64Array]()
    x_cols.append(x_id1^)
    x_cols.append(x_id2^)
    x_cols.append(left_key^)
    x_cols.append(x_v1^)
    var x = RecordBatch(schema_of(x_names^), x_cols^, N_X)

    var big_id1 = _load_column("big", "id1", N_BIG)
    var big_id2 = _load_column("big", "id2", N_BIG)
    var big_v2 = _load_column("big", "v2", N_BIG)
    var big_names = List[String]()
    big_names.append("id1")
    big_names.append("id2")
    big_names.append("id3")
    big_names.append("v2")
    var big_cols = List[Float64Array]()
    big_cols.append(big_id1^)
    big_cols.append(big_id2^)
    big_cols.append(right_key^)
    big_cols.append(big_v2^)
    var big = RecordBatch(schema_of(big_names^), big_cols^, N_BIG)

    var v1_idx = x.schema.index_of("v1")
    var v2_idx = big.schema.index_of("v2")

    var best_hash_e2e = 1e30
    var hash_e2e_rows = 0
    var hash_e2e_checksum: Float64 = 0.0
    for rep in range(REPS):
        var t0 = perf_counter_ns()
        var result = hash_join_indices(x, 2, big, 2, JOIN_INNER)
        var answer = materialize(x, big, result, "right.")
        var t1 = perf_counter_ns()
        var elapsed = Float64(Int(t1 - t0)) / 1e9
        if elapsed < best_hash_e2e:
            best_hash_e2e = elapsed
        hash_e2e_rows = answer.n_rows
        var v1_sum: Float64 = 0.0
        for i in range(answer.columns[v1_idx].length):
            if answer.columns[v1_idx].is_valid_at(i):
                v1_sum += answer.columns[v1_idx].get(i)
        var v2_col_idx = x.width() + v2_idx
        var v2_sum: Float64 = 0.0
        for i in range(answer.columns[v2_col_idx].length):
            if answer.columns[v2_col_idx].is_valid_at(i):
                v2_sum += answer.columns[v2_col_idx].get(i)
        hash_e2e_checksum = v1_sum + v2_sum
    print(
        "  hash join full pipeline:           min=" + String(best_hash_e2e) + "s"
        + "  rows=" + String(hash_e2e_rows)
        + "  checksum=" + String(hash_e2e_checksum)
    )

    var best_da_e2e = 1e30
    var da_e2e_rows = 0
    var da_e2e_checksum: Float64 = 0.0
    for rep in range(REPS):
        var t0 = perf_counter_ns()
        var table2 = List[Int]()
        var key_lo2 = 0
        var key_hi2 = 0
        var build_ok2 = True
        _ = _build_direct_address_table(
            big.column(2), N_BIG, BUILD_WORKERS, table2, key_lo2, key_hi2, build_ok2
        )
        if not build_ok2:
            raise Error("direct-address build reported ok=False in the full-pipeline rep")
        var result = _hash_join_probe_parallel_direct_address(
            x.column(2), N_X, table2, key_lo2, key_hi2, JOIN_INNER, BUILD_WORKERS
        )
        var answer = materialize(x, big, result, "right.")
        var t1 = perf_counter_ns()
        var elapsed = Float64(Int(t1 - t0)) / 1e9
        if elapsed < best_da_e2e:
            best_da_e2e = elapsed
        da_e2e_rows = answer.n_rows
        var v1_sum: Float64 = 0.0
        for i in range(answer.columns[v1_idx].length):
            if answer.columns[v1_idx].is_valid_at(i):
                v1_sum += answer.columns[v1_idx].get(i)
        var v2_col_idx = x.width() + v2_idx
        var v2_sum: Float64 = 0.0
        for i in range(answer.columns[v2_col_idx].length):
            if answer.columns[v2_col_idx].is_valid_at(i):
                v2_sum += answer.columns[v2_col_idx].get(i)
        da_e2e_checksum = v1_sum + v2_sum
    print(
        "  direct-address full pipeline:      min=" + String(best_da_e2e) + "s"
        + "  rows=" + String(da_e2e_rows)
        + "  checksum=" + String(da_e2e_checksum)
    )

    if hash_e2e_rows != da_e2e_rows or hash_e2e_checksum != da_e2e_checksum:
        raise Error(
            "FULL PIPELINE MISMATCH: hash_rows=" + String(hash_e2e_rows)
            + " da_rows=" + String(da_e2e_rows)
            + " hash_checksum=" + String(hash_e2e_checksum)
            + " da_checksum=" + String(da_e2e_checksum)
        )

    var e2e_speedup = best_hash_e2e / best_da_e2e
    print(
        "  full pipeline: direct-address vs hash: " + String(e2e_speedup) + "x"
        + (" (direct-address faster)" if e2e_speedup > 1.0 else " (direct-address SLOWER)")
    )
