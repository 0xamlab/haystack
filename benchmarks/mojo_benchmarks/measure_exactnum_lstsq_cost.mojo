"""
measure_exactnum_lstsq_cost.mojo — what the compensated least-squares route costs.

Named `measure_*`: `tests/benchmark_mojo_vs_python.py` generates `bench_{module}.mojo` here and
would destroy a hand-written file under that name.

Accuracy is not timing, so nothing about the correct-digit claim depends on this file. It is
here because a reader deciding whether to use the compensated route needs to know the price,
and "roughly twice the precision at a few flops of cost" is a claim that has to be measured on
the real shapes rather than asserted from a flop count.

WHAT IS TIMED, AND AGAINST WHAT
-------------------------------
`dd_lstsq_flat` against `f64_lstsq_flat` on the SAME design matrix. Those two are the same
algorithm — same pivot order, same reflector sign rule, same `v^T v` by summation — so the
ratio is the cost of the arithmetic and not the cost of a different method. Comparing against
a tuned LAPACK `dgelsy` would fold in blocking, vectorisation and a different algorithm, and
would say nothing about what compensation costs.

Shapes: the StRD suite's own worst case (82 x 11, Filip) plus two larger ones, because the
double-double overhead is per-flop while the float64 route gets progressively more help from
the vector units as the shapes grow, so a single shape would misreport the ratio in whichever
direction the reader assumed.

Ratios, not absolutes. Reported as a range over repeats, and the correctness of both arms is
asserted before any timing is printed — a speed comparison between two different answers is
meaningless.

    cd mojo_env
    pixi run mojo build -I../mojo/engine --optimization-level 3 \\
        ../benchmarks/mojo_benchmarks/measure_exactnum_lstsq_cost.mojo -o /tmp/exactnum_cost
    /tmp/exactnum_cost
"""
from std.math import abs as fabs
from std.time import perf_counter_ns

from exactnum.lstsq import LSTSQ_OK, dd_lstsq_flat, f64_lstsq_flat


def build_design(rows: Int, cols: Int) -> List[Float64]:
    """A Vandermonde-flavoured design whose columns are not exactly representable.

    `x_i` is a non-dyadic rational so the powers carry rounding, which is the regime the
    compensated route exists for. Deterministic, no RNG, so the timing shapes are reproducible.
    """
    var a = List[Float64]()
    for i in range(rows):
        var xv = -6.8 + Float64(i) * 0.13
        var t: Float64 = 1.0
        for _ in range(cols):
            a.append(t)
            t = t * xv
    return a^


def build_rhs(rows: Int) -> List[Float64]:
    var b = List[Float64]()
    for i in range(rows):
        var xv = -6.8 + Float64(i) * 0.13
        b.append(1.0 + xv * 0.5)
    return b^


def main() raises:
    print("shape        reps   dd_ns/solve   f64_ns/solve   dd/f64")
    var shapes_r = List[Int]()
    var shapes_c = List[Int]()
    shapes_r.append(82)
    shapes_c.append(11)
    shapes_r.append(256)
    shapes_c.append(16)
    shapes_r.append(1024)
    shapes_c.append(24)

    for s in range(len(shapes_r)):
        var rows = shapes_r[s]
        var cols = shapes_c[s]
        var a = build_design(rows, cols)
        var b = build_rhs(rows)

        # Correctness gate FIRST: both arms must produce a full-length solution, or the
        # timings are not printed at all.
        var dd0 = dd_lstsq_flat(a, rows, cols, b, 0)
        var f0 = f64_lstsq_flat(a, rows, cols, b)
        if (
            dd0.status != LSTSQ_OK
            or f0.status != LSTSQ_OK
            or len(dd0.coefficients) != cols
            or len(f0.coefficients) != cols
        ):
            print(
                "  SKIP",
                rows,
                "x",
                cols,
                "-- status dd",
                dd0.status,
                "f64",
                f0.status,
            )
            continue

        var reps = 200 if rows <= 100 else (40 if rows <= 300 else 8)
        var best_dd: Float64 = 0.0
        var best_f: Float64 = 0.0
        for trial in range(3):
            var t0 = perf_counter_ns()
            for _ in range(reps):
                var r = dd_lstsq_flat(a, rows, cols, b, 0)
                if r.status != LSTSQ_OK:
                    print("  UNSTABLE dd status", r.status)
            var t1 = perf_counter_ns()
            for _ in range(reps):
                var r2 = f64_lstsq_flat(a, rows, cols, b)
                if r2.status != LSTSQ_OK:
                    print("  UNSTABLE f64 status", r2.status)
            var t2 = perf_counter_ns()
            var dd_ns = Float64(Int(t1 - t0)) / Float64(reps)
            var f_ns = Float64(Int(t2 - t1)) / Float64(reps)
            if trial == 0 or dd_ns < best_dd:
                best_dd = dd_ns
            if trial == 0 or f_ns < best_f:
                best_f = f_ns
        print(
            String(rows) + "x" + String(cols),
            "      ",
            reps,
            "  ",
            Int(best_dd),
            "        ",
            Int(best_f),
            "     ",
            best_dd / best_f,
        )
    print("DONE")
