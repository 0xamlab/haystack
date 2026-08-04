"""bench_h2o_join.mojo — the H2O db-benchmark join questions, unrouted, on the
CURRENT engine: `hash_join_indices` called directly with no shape-aware dispatch.

This is a BASELINE measurement, not a submission. It exists to answer one question
before any router or partitioned-hash-join variant gets built: is the plane's single
hash-join path already close enough to DuckDB and Polars (say, within ~2x) on this
track's five questions that a composed router (the groupby page's playbook) is likely
to close the rest, or is the gap wide enough that routing alone will not be enough?

Data comes from `benchmarks/h2o_join/generate.py` (seeded, deterministic, following
the h2oai/db-benchmark `join-datagen.R` spec) into /tmp/h2o_join. This file refuses to
invent data if it is missing.

Questions (0.5 GB tier, N=1e7 fact rows `x`; matches the official suite's q1-q5):

  q1  small  inner  on id1   (dimension has 10 rows           -- N/1e6)
  q2  medium inner  on id2   (dimension has 10,000 rows       -- N/1e3)
  q3  medium left   on id2   (same dimension, LEFT join: has real unmatched rows)
  q4  medium inner  on id2   (the official suite's q4 joins on id5, the STRING form
                              of id2; this engine has no string dtype and, following
                              this project's own established convention for the H2O
                              track -- see gitbook/benchmarks/dataframe-groupby.md's
                              Method section, "categorical columns are emitted as
                              integer dictionary codes for every engine equally" --
                              every engine measured here gets the SAME int64 id2
                              column for q4 too. That makes q4 THE SAME OPERATION AS
                              q2 on this data; its number is reported anyway, to keep
                              five slots matching the official suite's five questions,
                              but it tests nothing q2 does not already test.)
  q5  big    inner  on id3   (dimension has N=1e7 rows -- the near-1:1 tier the
                              feasibility research flagged as the real risk for a
                              naive hash join: building a hash table over 1e7 rows
                              costs real memory and real insert time that q1/q2/q3's
                              tiny-or-medium build sides do not pay.)

Every question times ONE call to `hash_join_indices` (the plane's only join
implementation reachable without a caller naming a `method` -- see `plan._apply_join`,
which defaults to `method="hash"` and has no shape-aware dispatch today) plus one call
to `materialize`, because a join that is never turned into an answer batch is not the
operation DuckDB and Polars are timed doing either (their SQL/`.join()` calls both
produce a full result table, which is what `chk` sums over).

Checksum is sum(v1) + sum(v2) over the materialized result -- the same two columns
`join-duckdb.R` and `join-polars.py` both sum for their own `chk`. Row count and
checksum are both printed so a cross-engine driver can compare them on the bits
before trusting any timing.
"""
from std.io.file import FileHandle
from std.time import perf_counter_ns

from columnar.array import Float64Array, float64_from_list
from columnar.batch import RecordBatch, schema_of
from query.join import JOIN_INNER, JOIN_LEFT, JoinResult, hash_join_indices, materialize

comptime DATA_DIR: String = "/tmp/h2o_join"
comptime N_X: Int = 10_000_000
comptime N_SMALL: Int = 10
comptime N_MEDIUM: Int = 10_000
comptime N_BIG: Int = 10_000_000
comptime REPS: Int = 3


fn _load_column(table: String, col: String, n_rows: Int) raises -> Float64Array:
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


fn _batch(var names: List[String], var cols: List[Float64Array], n: Int) -> RecordBatch:
    return RecordBatch(schema_of(names^), cols^, n)


fn _sum(col: Float64Array) -> Float64:
    var total: Float64 = 0.0
    for i in range(col.length):
        if col.is_valid_at(i):
            total += col.get(i)
    return total


fn _run_question(
    name: String,
    left: RecordBatch,
    left_key: Int,
    right: RecordBatch,
    right_key: Int,
    join_type: Int,
) raises -> Float64:
    """Times REPS reps of hash_join_indices + materialize; returns the min seconds."""
    var best = 1e30
    var out_rows = -1
    var checksum: Float64 = 0.0
    var left_unmatched = -1
    for rep in range(REPS):
        var t0 = perf_counter_ns()
        var result = hash_join_indices(left, left_key, right, right_key, join_type)
        var answer = materialize(left, right, result, "right.")
        var t1 = perf_counter_ns()
        var elapsed = Float64(Int(t1 - t0)) / 1e9
        if elapsed < best:
            best = elapsed
        out_rows = answer.n_rows
        left_unmatched = result.left_unmatched
        # checksum: sum(v1) over left + sum(v2) over right, on the MATCHED rows --
        # matches join-duckdb.R / join-polars.py's chk = SUM(v1), SUM(v2) over ans.
        var v1_idx = left.schema.index_of("v1")
        var v2_idx = right.schema.index_of("v2")
        checksum = _sum(answer.columns[v1_idx]) + _sum(
            answer.columns[left.width() + v2_idx]
        )
    print(
        "  " + name
        + "  min=" + String(best) + "s"
        + "  out_rows=" + String(out_rows)
        + "  left_unmatched=" + String(left_unmatched)
        + "  checksum=" + String(checksum)
    )
    return best


fn main() raises:
    print("=== H2O join 0.5 GB tier (N=1e7) -- unrouted hash_join_indices baseline ===")
    print("  loading tables from " + DATA_DIR + " ...")

    var x_id1 = _load_column("x", "id1", N_X)
    var x_id2 = _load_column("x", "id2", N_X)
    var x_id3 = _load_column("x", "id3", N_X)
    var x_v1 = _load_column("x", "v1", N_X)
    var x_names = List[String]()
    x_names.append("id1")
    x_names.append("id2")
    x_names.append("id3")
    x_names.append("v1")
    var x_cols = List[Float64Array]()
    x_cols.append(x_id1^)
    x_cols.append(x_id2^)
    x_cols.append(x_id3^)
    x_cols.append(x_v1^)
    var x = _batch(x_names^, x_cols^, N_X)

    var small_id1 = _load_column("small", "id1", N_SMALL)
    var small_v2 = _load_column("small", "v2", N_SMALL)
    var small_names = List[String]()
    small_names.append("id1")
    small_names.append("v2")
    var small_cols = List[Float64Array]()
    small_cols.append(small_id1^)
    small_cols.append(small_v2^)
    var small = _batch(small_names^, small_cols^, N_SMALL)

    var medium_id1 = _load_column("medium", "id1", N_MEDIUM)
    var medium_id2 = _load_column("medium", "id2", N_MEDIUM)
    var medium_v2 = _load_column("medium", "v2", N_MEDIUM)
    var medium_names = List[String]()
    medium_names.append("id1")
    medium_names.append("id2")
    medium_names.append("v2")
    var medium_cols = List[Float64Array]()
    medium_cols.append(medium_id1^)
    medium_cols.append(medium_id2^)
    medium_cols.append(medium_v2^)
    var medium = _batch(medium_names^, medium_cols^, N_MEDIUM)

    var big_id1 = _load_column("big", "id1", N_BIG)
    var big_id2 = _load_column("big", "id2", N_BIG)
    var big_id3 = _load_column("big", "id3", N_BIG)
    var big_v2 = _load_column("big", "v2", N_BIG)
    var big_names = List[String]()
    big_names.append("id1")
    big_names.append("id2")
    big_names.append("id3")
    big_names.append("v2")
    var big_cols = List[Float64Array]()
    big_cols.append(big_id1^)
    big_cols.append(big_id2^)
    big_cols.append(big_id3^)
    big_cols.append(big_v2^)
    var big = _batch(big_names^, big_cols^, N_BIG)

    print(
        "  loaded: x=" + String(N_X) + " small=" + String(N_SMALL)
        + " medium=" + String(N_MEDIUM) + " big=" + String(N_BIG)
    )
    print("")

    var q1 = _run_question("q1 small  inner on id1  ", x, 0, small, 0, JOIN_INNER)
    var q2 = _run_question("q2 medium inner on id2  ", x, 1, medium, 1, JOIN_INNER)
    var q3 = _run_question("q3 medium left  on id2  ", x, 1, medium, 1, JOIN_LEFT)
    var q4 = _run_question("q4 medium inner on id2* ", x, 1, medium, 1, JOIN_INNER)
    var q5 = _run_question("q5 big    inner on id3  ", x, 2, big, 2, JOIN_INNER)

    print("")
    print("  * q4 is the same operation as q2 on this engine -- see file docstring.")
    print("  summary (min seconds): q1=" + String(q1) + " q2=" + String(q2)
        + " q3=" + String(q3) + " q4=" + String(q4) + " q5=" + String(q5))
