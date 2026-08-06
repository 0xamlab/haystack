"""bench_h2o_composed.mojo — ONE H2O question per invocation, so the composed
route can actually be interleaved with polars and duckdb in one window.

Why one question per process: the measurement protocol needs all three engines
running INTERLEAVED, polars and duckdb live in another process, and Mojo's
`input()` reads once per process so a REPL protocol is not available. A cheap
process is. This file takes the question on argv, loads ONLY the columns that
question touches, and runs a fixed number of reps.
`benchmarks/h2o_groupby/run_composed_interleaved.py` drives it, alternating
with the baselines question by question and recording the load average around
every block.

Usage:
    bench_h2o_composed <q1|q2|q3|q4|q5|q7> <reps> <workers>
      workers 0 = num_physical_cores

Per rep it times, on the SAME batch, back to back:

  routed     `group_by_many`                 what a caller gets today, and the
                                             number the published page reports
  reference  the sibling engine the composed route delegates to, at the plan's
             worker count — the BIT-IDENTITY reference
  composed   `group_by_composed_parallel`    plan + engine, i.e. what a caller
                                             would get
  planned    `group_by_composed_planned`     the engine with the plan hoisted,
                                             so the router's own cost is
                                             visible rather than assumed
  serialmrg  the same engine with the parallel merge forced OFF — the
             composition's own contribution, isolated

and then asserts, on the FULL 1e7-row result, that composed is BIT-IDENTICAL to
the reference: every group key in order, every value, every `present`, every
count, compared as bit patterns. A checksum comparison would pass two results
whose groups were permuted or whose means differed by an ulp; this does not.

GATES. All three gate SHAPE or CORRECTNESS and never absolute nanoseconds:

  composed_identity   composed == reference, bitwise, every rep
  composed_serialmrg  the parallel merge changes NO BIT — the serial-merge run
                      is bit-identical to the parallel one, which is the claim
                      that makes the merge decomposition legal
  composed_route      the question takes the route it is supposed to take, so a
                      silent fallback cannot be published as a win
"""
from std.io.file import FileHandle
from std.memory import bitcast
from std.sys import argv, exit, info
from std.time import perf_counter_ns

from columnar.array import Float64Array, float64_from_list
from columnar.batch import RecordBatch, schema_of
from numeric.contract import AGG_AVG, AGG_MAX, AGG_MIN, AGG_SUM
from query.aggregate import (
    MAX_CODED_CARDINALITY,
    ManyGroupedResult,
    group_by_coded_parallel,
    group_by_many,
    group_by_many_banded,
)
from query.aggregate_late import group_by_many_radix_fused
from query.coded_dense import DENSE_BANDS_PER_CORE
from query.composed import (
    COMPOSE_ROUTE_DENSE,
    COMPOSE_ROUTE_LATE,
    COMPOSE_ROUTE_PACKED,
    compose_plan,
    compose_route_name,
    group_by_composed_dense_parallel,
    group_by_composed_planned,
    group_by_composed_parallel,
)
from query.packedkey import group_by_packed_parallel

comptime N_ROWS: Int = 10_000_000
comptime DATA_DIR: String = "/tmp/h2o_groupby"


def _load_column(name: String) raises -> Float64Array:
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


def _bits(x: Float64) -> UInt64:
    return bitcast[DType.uint64](x)


def _identical(a: ManyGroupedResult, b: ManyGroupedResult) -> Int:
    """Cells where two results differ BITWISE. 0 is identity.

    Bit patterns and not `==`: `==` calls +0.0 and -0.0 equal and calls every
    NaN unequal, and those are the two distinctions an identity claim needs.
    Keys are compared IN ORDER, so a permutation is not identity.
    """
    if a.n_groups() != b.n_groups():
        return 1_000_000_000
    if a.n_aggs != b.n_aggs or a.key_width != b.key_width:
        return 1_000_000_001
    if a.null_key_rows != b.null_key_rows:
        return 1_000_000_002
    if len(a.values) != len(b.values) or len(a.key_tuples) != len(b.key_tuples):
        return 1_000_000_003
    var bad = 0
    for i in range(len(a.key_tuples)):
        if _bits(a.key_tuples[i]) != _bits(b.key_tuples[i]):
            bad += 1
    for i in range(len(a.values)):
        if _bits(a.values[i]) != _bits(b.values[i]):
            bad += 1
        if a.present[i] != b.present[i]:
            bad += 1
        if _bits(a.counts[i]) != _bits(b.counts[i]):
            bad += 1
    return bad


def _checksum(values: List[Float64], present: List[Bool]) -> Float64:
    var total: Float64 = 0.0
    for i in range(len(values)):
        if present[i]:
            total += values[i]
    return total


def _ms(ns: UInt) -> Float64:
    return Float64(Int(ns)) / 1e6


def main() raises:
    var args = argv()
    if len(args) < 4:
        print("usage: bench_h2o_composed <q1|q2|q3|q4|q5|q7> <reps> <workers>")
        exit(2)
    var qname = String(args[1])
    var reps = Int(String(args[2]))
    var req_workers = Int(String(args[3]))
    var cores = info.num_physical_cores()
    # 0 means the composed route's OWN default band count — over-decomposed,
    # which is also the setting at which `compose_dense_workers` actually binds.
    var workers = req_workers if req_workers > 0 else cores * DENSE_BANDS_PER_CORE

    # ── question definitions, exactly the shipped bench's ────────────────────
    var key_names = List[String]()
    var value_names = List[String]()
    var opcodes = List[Int]()
    var want_route = COMPOSE_ROUTE_DENSE
    if qname == "q1":
        key_names.append("id1")
        value_names.append("v1")
        opcodes.append(AGG_SUM)
    elif qname == "q2":
        key_names.append("id1")
        key_names.append("id2")
        value_names.append("v1")
        opcodes.append(AGG_SUM)
        want_route = COMPOSE_ROUTE_PACKED
    elif qname == "q3":
        key_names.append("id3")
        value_names.append("v1")
        value_names.append("v3")
        opcodes.append(AGG_SUM)
        opcodes.append(AGG_AVG)
    elif qname == "q4":
        key_names.append("id4")
        value_names.append("v1")
        value_names.append("v2")
        value_names.append("v3")
        opcodes.append(AGG_AVG)
        opcodes.append(AGG_AVG)
        opcodes.append(AGG_AVG)
    elif qname == "q5":
        key_names.append("id6")
        value_names.append("v1")
        value_names.append("v2")
        value_names.append("v3")
        opcodes.append(AGG_SUM)
        opcodes.append(AGG_SUM)
        opcodes.append(AGG_SUM)
    elif qname == "q7":
        key_names.append("id3")
        value_names.append("v1")
        value_names.append("v2")
        opcodes.append(AGG_MAX)
        opcodes.append(AGG_MIN)
    else:
        print("unknown question " + qname)
        exit(2)
        return

    var names = List[String]()
    var cols = List[Float64Array]()
    for i in range(len(key_names)):
        names.append(key_names[i])
        cols.append(_load_column(key_names[i]))
    for j in range(len(value_names)):
        names.append(value_names[j])
        cols.append(_load_column(value_names[j]))
    var width = len(key_names)
    var n_aggs = len(value_names)
    var batch = RecordBatch(schema_of(names^), cols^, N_ROWS)

    var key_cols = List[Int]()
    for i in range(width):
        key_cols.append(i)
    var value_cols = List[Int]()
    for j in range(n_aggs):
        value_cols.append(width + j)

    var plan = compose_plan(batch, key_cols, value_cols, opcodes, workers)
    print(
        "BENCH question=" + qname + " cores=" + String(cores)
        + " workers=" + String(workers) + " n_aggs=" + String(n_aggs)
        + " width=" + String(width) + " plan=[" + plan.describe() + "]"
    )
    var route_bad = 0
    if plan.route != want_route:
        route_bad = 1
        print(
            "BENCH_GATE composed_route " + qname + " got="
            + compose_route_name(plan.route) + " want="
            + compose_route_name(want_route)
        )

    var mismatches = route_bad
    for rep in range(reps):
        # The ROUTER's own cost, measured rather than assumed: the module
        # claims the plan is cheap next to the engine, and a claim about cost
        # that is never timed is a guess.
        var p0 = perf_counter_ns()
        var rep_plan = compose_plan(batch, key_cols, value_cols, opcodes, workers)
        var p1 = perf_counter_ns()
        _ = rep_plan.route
        var t0 = perf_counter_ns()
        var routed = group_by_many(batch, key_cols, value_cols, opcodes)
        var t1 = perf_counter_ns()
        # The reference: the sibling engine this route delegates to, at the
        # plan's worker count. Bit identity is per worker count, so a reference
        # at a different count would be the wrong question.
        var ref_ok = True
        var reference = routed.copy()
        if plan.route == COMPOSE_ROUTE_DENSE:
            # SHIPPED `group_by_many_banded`, not the sibling dense engine: it
            # holds private tables per contiguous row band and merges in band
            # order, which is the identical fold association a band-local dense
            # array uses, so it owes BIT equality at the same worker count — and
            # it is not capped at `MAX_CODED_CARDINALITY`, so it is the only
            # shipped engine that can reference the 1e5-code questions at all.
            # `group_by_coded_parallel` refuses above 4096 codes, which is why
            # the dense record needed widening in the first place; the suite
            # still pins against it wherever it can answer.
            reference = group_by_many_banded(
                batch, key_cols, value_cols, opcodes, plan.workers
            )
        elif plan.route == COMPOSE_ROUTE_PACKED:
            var p = group_by_packed_parallel(
                batch, key_cols, plan.domain, value_cols, opcodes, plan.workers
            )
            ref_ok = p.ok()
            if ref_ok:
                reference = p.result.copy()
        else:
            reference = group_by_many_radix_fused(
                batch, key_cols, value_cols, opcodes, plan.workers
            )
        var t2 = perf_counter_ns()
        var composed = group_by_composed_parallel(
            batch, key_cols, value_cols, opcodes, workers
        )
        var t3 = perf_counter_ns()
        var planned = group_by_composed_planned(
            batch, key_cols, value_cols, opcodes, plan
        )
        var t4 = perf_counter_ns()
        # The composition's own contribution, isolated: the same engine with the
        # parallel merge forced off. Only meaningful on the dense route.
        var serial_ms = 0.0
        var smrg_diffs = 0
        if plan.route == COMPOSE_ROUTE_DENSE:
            var s0 = perf_counter_ns()
            var smrg = group_by_composed_dense_parallel(
                batch, key_cols[0], plan.cardinality, value_cols, opcodes,
                plan.workers, False,
            )
            var s1 = perf_counter_ns()
            serial_ms = _ms(s1 - s0)
            if not smrg.ok():
                smrg_diffs = 1
            else:
                smrg_diffs = _identical(smrg.result, composed)
            if smrg_diffs != 0:
                mismatches += 1
                print(
                    "BENCH_GATE composed_serialmrg " + qname
                    + " diffs=" + String(smrg_diffs)
                )
        if not ref_ok:
            print("BENCH_GATE composed_identity reference refused " + qname)
            mismatches += 1
            continue
        var c_vs_ref = _identical(reference, composed)
        var c_vs_planned = _identical(planned, composed)
        if c_vs_ref != 0 or c_vs_planned != 0:
            mismatches += 1
            print(
                "BENCH_GATE composed_identity " + qname
                + " composed_vs_reference=" + String(c_vs_ref)
                + " composed_vs_planned=" + String(c_vs_planned)
            )
        print(
            "REP " + qname + " " + String(rep)
            + " routed_ms=" + String(_ms(t1 - t0))
            + " reference_ms=" + String(_ms(t2 - t1))
            + " composed_ms=" + String(_ms(t3 - t2))
            + " planned_ms=" + String(_ms(t4 - t3))
            + " serialmrg_ms=" + String(serial_ms)
            + " plan_ms=" + String(_ms(p1 - p0))
            + " route=" + compose_route_name(plan.route)
            + " groups=" + String(composed.n_groups())
            + " identity_diffs=" + String(c_vs_ref)
            + " serialmrg_diffs=" + String(smrg_diffs)
            + " checksum=" + String(_checksum(composed.values, composed.present))
        )

    if mismatches != 0:
        print("BENCH_GATE FAILED mismatches=" + String(mismatches))
        exit(1)
    print("BENCH_OK " + qname)
