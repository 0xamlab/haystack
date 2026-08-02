"""bench_h2o_stats.mojo — the three H2O db-benchmark questions
`bench_h2o_groupby.mojo`/`bench_h2o_composed.mojo` explicitly do NOT run:
q6 (grouped median + sd), q8 (grouped top-2) and q9 (grouped R^2).

Two modes, because a per-group correctness crosscheck and a timing loop have
opposite needs (print everything once / print nothing but a checksum, many
times):

  dump <q6|q8|q9> <workers>
    Runs the engine ONCE and prints one line per group in a fixed, greppable
    format so a Python driver can parse it and compare against DuckDB/Polars
    on the SAME seeded dataset — a correctness crosscheck, never a timing
    number.

  time <q6|q8|q9> <reps> <workers>
    Runs `reps` back-to-back repetitions and prints one `REP` line per
    repetition with wall time, group count and a checksum — the number
    `run_stats_interleaved.py` records, exactly `bench_h2o_composed.mojo`'s
    shape.

`workers` 0 means `num_physical_cores()`.
"""
from std.io.file import FileHandle
from std.sys import argv, exit, info
from std.time import perf_counter_ns

from columnar.array import Float64Array, float64_from_list
from columnar.batch import RecordBatch, schema_of
from query.comoments_packed import group_comoments_packed_parallel
from query.median_packed import group_median_sd_packed_parallel
from query.packedkey import probe_packed_domain
from query.topk_dense import group_top2_dense_parallel

comptime N_ROWS: Int = 10_000_000
comptime DATA_DIR: String = "/tmp/h2o_groupby"
comptime PROBE_ROWS: Int = 1 << 16


fn _load_column(name: String) raises -> Float64Array:
    var f = open(DATA_DIR + "/" + name + ".f64.bin", "r")
    var raw = f.read_bytes()
    f.close()
    if len(raw) != N_ROWS * 8:
        raise Error(
            name + ".f64.bin is " + String(len(raw)) + " bytes, expected "
            + String(N_ROWS * 8)
            + " — run benchmarks/h2o_groupby/generate.py first"
        )
    var fp = raw.unsafe_ptr().bitcast[Float64]()
    var values = List[Float64](capacity=N_ROWS)
    for i in range(N_ROWS):
        values.append(fp[i])
    return float64_from_list(values^)


fn _ms(ns: UInt) -> Float64:
    return Float64(Int(ns)) / 1e6


fn main() raises:
    var args = argv()
    if len(args) < 3:
        print("usage: bench_h2o_stats dump <q6|q8|q9> <workers>")
        print("       bench_h2o_stats time <q6|q8|q9> <reps> <workers>")
        exit(2)
        return
    var mode = String(args[1])
    var qname = String(args[2])
    var cores = info.num_physical_cores()

    if qname == "q8":
        var id6 = _load_column("id6")
        var v3 = _load_column("v3")
        var names = List[String]()
        names.append("id6")
        names.append("v3")
        var cols = List[Float64Array]()
        cols.append(id6^)
        cols.append(v3^)
        var batch = RecordBatch(schema_of(names^), cols^, N_ROWS)
        # id6 in H2O is 1-based, N/K distinct -> cardinality = N/K + 1.
        var cardinality = N_ROWS // 100 + 1

        if mode == "dump":
            var workers = Int(String(args[3])) if len(args) > 3 else cores
            if workers <= 0:
                workers = cores
            var res = group_top2_dense_parallel(batch, 0, cardinality, 1, workers)
            if not res.ok():
                print("DUMP_FAILED status=" + String(res.status))
                exit(1)
                return
            print("DUMP_HEADER q8 groups=" + String(res.result.n_groups()))
            for g in range(res.result.n_groups()):
                print(
                    "ROW8 " + String(Int(res.result.key_tuples[g]))
                    + " " + String(res.result.top1[g])
                    + " " + String(1 if res.result.present1[g] else 0)
                    + " " + String(res.result.top2[g])
                    + " " + String(1 if res.result.present2[g] else 0)
                )
            print("DUMP_OK q8")
            return

        var reps = Int(String(args[3]))
        var req_workers = Int(String(args[4]))
        var workers = req_workers if req_workers > 0 else cores
        for rep in range(reps):
            var t0 = perf_counter_ns()
            var res = group_top2_dense_parallel(batch, 0, cardinality, 1, workers)
            var t1 = perf_counter_ns()
            if not res.ok():
                print("BENCH_GATE h2o_stats_status q8 " + String(res.status))
                exit(1)
                return
            var checksum: Float64 = 0.0
            for g in range(res.result.n_groups()):
                if res.result.present1[g]:
                    checksum += res.result.top1[g]
                if res.result.present2[g]:
                    checksum += res.result.top2[g]
            print(
                "REP q8 " + String(rep) + " ms=" + String(_ms(t1 - t0))
                + " groups=" + String(res.result.n_groups())
                + " checksum=" + String(checksum)
            )
        print("BENCH_OK q8")
        return

    if qname == "q9":
        var id2 = _load_column("id2")
        var id4 = _load_column("id4")
        var v1 = _load_column("v1")
        var v2 = _load_column("v2")
        var names = List[String]()
        names.append("id2")
        names.append("id4")
        names.append("v1")
        names.append("v2")
        var cols = List[Float64Array]()
        cols.append(id2^)
        cols.append(id4^)
        cols.append(v1^)
        cols.append(v2^)
        var batch = RecordBatch(schema_of(names^), cols^, N_ROWS)
        var key_cols = List[Int]()
        key_cols.append(0)
        key_cols.append(1)
        var domain = probe_packed_domain(batch, key_cols, PROBE_ROWS)
        if not domain.valid():
            print("BENCH_GATE h2o_stats_domain q9 " + String(domain.status))
            exit(1)
            return

        if mode == "dump":
            var workers = Int(String(args[3])) if len(args) > 3 else cores
            if workers <= 0:
                workers = cores
            var res = group_comoments_packed_parallel(batch, key_cols, domain, 2, 3, workers)
            if not res.ok():
                print("DUMP_FAILED status=" + String(res.status))
                exit(1)
                return
            print("DUMP_HEADER q9 groups=" + String(res.result.n_groups()))
            for g in range(res.result.n_groups()):
                print(
                    "ROW9 " + String(Int(res.result.key_tuples[g * 2]))
                    + " " + String(Int(res.result.key_tuples[g * 2 + 1]))
                    + " " + String(Int(res.result.count[g]))
                    + " " + String(res.result.r2[g])
                    + " " + String(1 if res.result.present[g] else 0)
                )
            print("DUMP_OK q9")
            return

        var reps = Int(String(args[3]))
        var req_workers = Int(String(args[4]))
        var workers = req_workers if req_workers > 0 else cores
        for rep in range(reps):
            var t0 = perf_counter_ns()
            var res = group_comoments_packed_parallel(batch, key_cols, domain, 2, 3, workers)
            var t1 = perf_counter_ns()
            if not res.ok():
                print("BENCH_GATE h2o_stats_status q9 " + String(res.status))
                exit(1)
                return
            var checksum: Float64 = 0.0
            for g in range(res.result.n_groups()):
                if res.result.present[g]:
                    checksum += res.result.r2[g]
            print(
                "REP q9 " + String(rep) + " ms=" + String(_ms(t1 - t0))
                + " groups=" + String(res.result.n_groups())
                + " checksum=" + String(checksum)
            )
        print("BENCH_OK q9")
        return

    if qname == "q6":
        var id4 = _load_column("id4")
        var id5 = _load_column("id5")
        var v3 = _load_column("v3")
        var names = List[String]()
        names.append("id4")
        names.append("id5")
        names.append("v3")
        var cols = List[Float64Array]()
        cols.append(id4^)
        cols.append(id5^)
        cols.append(v3^)
        var batch = RecordBatch(schema_of(names^), cols^, N_ROWS)
        var key_cols = List[Int]()
        key_cols.append(0)
        key_cols.append(1)
        var domain = probe_packed_domain(batch, key_cols, PROBE_ROWS)
        if not domain.valid():
            print("BENCH_GATE h2o_stats_domain q6 " + String(domain.status))
            exit(1)
            return

        if mode == "dump":
            var workers = Int(String(args[3])) if len(args) > 3 else cores
            if workers <= 0:
                workers = cores
            var res = group_median_sd_packed_parallel(batch, key_cols, domain, 2, workers)
            if not res.ok():
                print("DUMP_FAILED status=" + String(res.status))
                exit(1)
                return
            print("DUMP_HEADER q6 groups=" + String(res.result.n_groups()))
            for g in range(res.result.n_groups()):
                print(
                    "ROW6 " + String(Int(res.result.key_tuples[g * 2]))
                    + " " + String(Int(res.result.key_tuples[g * 2 + 1]))
                    + " " + String(Int(res.result.count[g]))
                    + " " + String(res.result.median[g])
                    + " " + String(res.result.sd[g])
                    + " " + String(1 if res.result.present_sd[g] else 0)
                )
            print("DUMP_OK q6")
            return

        var reps = Int(String(args[3]))
        var req_workers = Int(String(args[4]))
        var workers = req_workers if req_workers > 0 else cores
        for rep in range(reps):
            var t0 = perf_counter_ns()
            var res = group_median_sd_packed_parallel(batch, key_cols, domain, 2, workers)
            var t1 = perf_counter_ns()
            if not res.ok():
                print("BENCH_GATE h2o_stats_status q6 " + String(res.status))
                exit(1)
                return
            var checksum: Float64 = 0.0
            for g in range(res.result.n_groups()):
                checksum += res.result.median[g]
                if res.result.present_sd[g]:
                    checksum += res.result.sd[g]
            print(
                "REP q6 " + String(rep) + " ms=" + String(_ms(t1 - t0))
                + " groups=" + String(res.result.n_groups())
                + " checksum=" + String(checksum)
            )
        print("BENCH_OK q6")
        return

    print("unknown question " + qname)
    exit(2)
