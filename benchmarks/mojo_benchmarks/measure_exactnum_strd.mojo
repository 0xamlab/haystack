"""
measure_exactnum_strd.mojo — the NIST StRD linear-regression suite through every arm.

Named `measure_*` rather than `bench_*` deliberately: `tests/benchmark_mojo_vs_python.py`
writes `bench_{module}.mojo` in this directory from a generator, and a hand-written file
under that name is destroyed on the next run.

WHAT THIS PRINTS AND WHAT IT DOES NOT
-------------------------------------
It prints coefficients as raw 16-hex-digit IEEE-754 bit patterns and nothing else. The
accuracy metric (NIST's log relative error against the certified values) is computed in
`benchmarks/external_baselines/strd_lstsq/score.py`, in the same process that runs the
numpy / scipy / statsmodels reference arms. Scoring here would mean two implementations of
the metric and no way to know which one flattered which side.

Input arrives the same way: every value in the `.spec` files is a hex bit pattern, so the
design matrix built here is provably built from the same bits the reference arms are handed.
An ASCII decimal round trip would be *probably* the same bits, which is a different claim.

THE ARMS, AND WHY EACH ONE EXISTS
---------------------------------
Two levers are independent and the suite separates them, because on this data they do not
have the same effect and a single number would hide that:

  * how the DESIGN MATRIX is built — powers of x by repeated float64 multiplication (the
    recipe every reference implementation uses) versus by repeated double-double
    multiplication from the same float64 x
  * what precision the SOLVE carries — plain float64 versus double-double

    A  f64_matrix__f64_solve      the control: plain float64 end to end
    B  ddpow_matrix__f64_solve    better matrix, float64 solve
    C  f64_matrix__dd_solve       recipe matrix, compensated solve
    D  ddpow_matrix__dd_solve     both compensated
    D1 ddpow_matrix__dd_solve_r1  D plus one residual-refinement step
    S  scaled_dd_solve_ddmap      centred/scaled basis, compensated map back to the
                                  published parameterisation
    S0 scaled_dd_solve_f64map     the same fit with the map back done in float64, so the
                                  cost of that one step is visible as a number
    N  shipped_csr_normal_eq      the FROZEN sparse_numerics.factor.csr_least_squares —
                                  normal equations plus Cholesky, i.e. what the tree ships
                                  today — re-measured here rather than quoted

A and C differ only in the arithmetic: identical pivot order, identical reflector sign rule,
identical v^T v by summation. That is what makes any gap attributable to the arithmetic.

S and S0 both report coefficients in the PUBLISHED parameterisation. Digits measured in the
scaled basis are several digits better and do not hold for the reported coefficients; this
file therefore never prints the scaled-basis coefficients at all, so they cannot be scored by
accident.

Build it compiled as well as under the JIT and diff the output. Rule 1b of
docs/mojo/new-kernel-package-rules.md: `mojo run` cannot prove memory soundness. Here it also
cannot prove the arithmetic, because the JIT and the -O3 object are different codegen paths
and a reassociation in either one would silently destroy every compensated result:

    cd mojo_env
    pixi run mojo build -I../mojo/engine --optimization-level 3 \\
        ../benchmarks/mojo_benchmarks/measure_exactnum_strd.mojo -o /tmp/measure_strd
    /tmp/measure_strd <spec_file>
"""
from sys import argv

from std.memory import bitcast

from exactnum.eft import EFT_OK, eft_selfcheck_code
from exactnum.lstsq import (
    LSTSQ_OK,
    dd_lstsq_flat,
    dd_poly_lstsq,
    dd_poly_lstsq_scaled,
    f64_lstsq_flat,
    f64_poly_lstsq,
    DDLstsq,
)
from sparse_numerics.factor import csr_least_squares


def hex_to_f64(s: StringSlice) raises -> Float64:
    var acc: UInt64 = 0
    var raw = s.as_bytes()
    if len(raw) != 16:
        raise Error("hex token must be 16 digits")
    for i in range(16):
        var c = Int(raw[i])
        var d: Int
        if c >= 48 and c <= 57:
            d = c - 48
        elif c >= 97 and c <= 102:
            d = c - 87
        elif c >= 65 and c <= 70:
            d = c - 55
        else:
            raise Error("bad hex digit")
        acc = (acc << 4) | UInt64(d)
    return bitcast[DType.float64, 1](acc)


def f64_to_hex(v: Float64) -> String:
    var u = v.to_bits()
    var out = String("")
    for i in range(16):
        var shift = (15 - i) * 4
        var nib = Int((u >> shift) & 0xF)
        out += chr(nib + 48) if nib < 10 else chr(nib + 87)
    return out


def read_all(path: String) raises -> String:
    var f = open(path, "r")
    var s = f.read()
    f.close()
    return s


def emit(arm: String, r: DDLstsq):
    print(
        "ARM",
        arm,
        "STATUS",
        r.status,
        "RANK",
        r.rank,
        "RDIAGMIN",
        f64_to_hex(r.r_diag_min),
        "PIVRATIO",
        f64_to_hex(r.pivot_ratio_min),
        "RESID",
        f64_to_hex(r.residual_norm),
        "REFINE",
        r.refine_steps,
    )
    for j in range(len(r.coefficients)):
        print(
            "COEF",
            arm,
            j,
            f64_to_hex(r.coefficients[j]),
            f64_to_hex(r.coefficients_lo[j]),
        )


def shipped_normal_equations(
    a: List[Float64], rows: Int, cols: Int, b: List[Float64]
) -> DDLstsq:
    """The FROZEN `csr_least_squares` on the same design matrix, as dense-in-CSR.

    Not a reimplementation of the shipped route — a call into it (rule 3). Its result struct
    lives in another module, so it is repacked into this file's `DDLstsq` to be printed
    alongside the others; `refine_steps` is -1 to mark it as not one of this package's arms.

    A dense matrix stored as CSR is exactly what `csr_least_squares` receives when a caller
    hands it a regression design, which is the shape the 'shipped tree' claim is about."""
    var indptr = List[Int]()
    var indices = List[Int]()
    var values = List[Float64]()
    indptr.append(0)
    for i in range(rows):
        for j in range(cols):
            indices.append(j)
            values.append(a[i * cols + j])
        indptr.append((i + 1) * cols)
    var s = csr_least_squares(indptr, indices, values, rows, cols, b)
    var out = List[Float64]()
    var lo = List[Float64]()
    for j in range(len(s.x)):
        out.append(s.x[j])
        lo.append(0.0)
    var status = LSTSQ_OK if len(s.x) == cols else s.status
    return DDLstsq(out^, lo^, status, cols, 0.0, 0.0, s.residual_norm, -1)


def main() raises:
    var args = argv()
    if len(args) < 2:
        print("usage: measure_exactnum_strd <spec_file>")
        return
    var text = read_all(String(args[1]))
    var lines = text.split("\n")
    var head = lines[0].split(" ")
    var rows = Int(head[0])
    var nraw = Int(head[1])
    var lo_deg = Int(head[2])
    var hi_deg = Int(head[3])
    var is_poly = Int(head[4]) == 1

    var y = List[Float64]()
    var xcols = List[List[Float64]]()
    for _ in range(nraw):
        xcols.append(List[Float64]())
    for i in range(rows):
        var toks = lines[1 + i].split(" ")
        if len(toks) != nraw + 1:
            raise Error("bad row width")
        y.append(hex_to_f64(toks[0]))
        for j in range(nraw):
            xcols[j].append(hex_to_f64(toks[1 + j]))

    print("SELFCHECK", eft_selfcheck_code())
    if eft_selfcheck_code() != EFT_OK:
        # Rule 4: no answer exists if the arithmetic assumption this package rests on is
        # false. Printing coefficients anyway would produce plausible numbers that are lies.
        print("ABORT arithmetic_selfcheck_failed")
        return
    print("ROWS", rows, "NRAW", nraw, "LODEG", lo_deg, "HIDEG", hi_deg)

    if is_poly:
        var x = xcols[0].copy()
        var cols = hi_deg - lo_deg + 1
        # The recipe design matrix, built once here so the frozen normal-equations arm and
        # the float64 control see byte-identical input.
        var a_recipe = List[Float64]()
        for i in range(rows):
            var t: Float64 = 1.0
            for k in range(hi_deg + 1):
                if k >= lo_deg:
                    a_recipe.append(t)
                t = t * x[i]
        print("COLS", cols)
        emit(
            String("A_f64_matrix__f64_solve"),
            f64_poly_lstsq(x, y, rows, lo_deg, hi_deg, False),
        )
        emit(
            String("B_ddpow_matrix__f64_solve"),
            f64_poly_lstsq(x, y, rows, lo_deg, hi_deg, True),
        )
        emit(
            String("C_f64_matrix__dd_solve"),
            dd_poly_lstsq(x, y, rows, lo_deg, hi_deg, False, 0),
        )
        emit(
            String("D_ddpow_matrix__dd_solve"),
            dd_poly_lstsq(x, y, rows, lo_deg, hi_deg, True, 0),
        )
        emit(
            String("D1_ddpow_matrix__dd_solve_r1"),
            dd_poly_lstsq(x, y, rows, lo_deg, hi_deg, True, 1),
        )
        if lo_deg == 0:
            emit(
                String("S_scaled_dd_solve_ddmap"),
                dd_poly_lstsq_scaled(x, y, rows, hi_deg, True, True, 0),
            )
            emit(
                String("S0_scaled_dd_solve_f64map"),
                dd_poly_lstsq_scaled(x, y, rows, hi_deg, True, False, 0),
            )
        emit(
            String("N_shipped_csr_normal_eq"),
            shipped_normal_equations(a_recipe, rows, cols, y),
        )
    else:
        # Published columns, intercept first. No powers to form, so the matrix-construction
        # lever does not exist here and B is definitionally A.
        var cols = nraw + 1
        var a = List[Float64]()
        for i in range(rows):
            a.append(1.0)
            for j in range(nraw):
                a.append(xcols[j][i])
        print("COLS", cols)
        emit(
            String("A_f64_matrix__f64_solve"), f64_lstsq_flat(a, rows, cols, y)
        )
        emit(
            String("C_f64_matrix__dd_solve"), dd_lstsq_flat(a, rows, cols, y, 0)
        )
        emit(
            String("D_ddpow_matrix__dd_solve"),
            dd_lstsq_flat(a, rows, cols, y, 0),
        )
        emit(
            String("D1_ddpow_matrix__dd_solve_r1"),
            dd_lstsq_flat(a, rows, cols, y, 1),
        )
        emit(
            String("N_shipped_csr_normal_eq"),
            shipped_normal_equations(a, rows, cols, y),
        )
    print("DONE")
