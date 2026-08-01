"""Exact least-squares ceilings for the NIST StRD linear-regression suite.

A ceiling here is: solve the least-squares problem EXACTLY over the rationals, round the
answer ONCE to float64, and score that against the certified values. No float64-returning
solver can beat it, whatever precision it carries internally, because it is limited only by
the input bits and by the return format.

Every float64 is a dyadic rational, so `fractions.Fraction` represents each design-matrix
entry and each response exactly; `X^T X` and `X^T y` are then exact and Gaussian elimination
over `Fraction` gives the exact minimiser with zero rounding anywhere. The normal equations
are numerically catastrophic and arithmetically irrelevant — there is no rounding to amplify.

Two ceilings matter, and the difference between them is the whole argument about Filip:

  c_recipe   float64 x, powers by repeated float64 multiplication. The published recipe, and
             what every reference arm is handed. If this is below the reference bar, no solver
             can win on the raw basis — the loss happened before any solver ran.
  c_exactpow float64 x, powers formed EXACTLY. The limit of forming the design matrix in
             extended precision from the same float64 inputs. Double-double power formation
             carries ~106 bits, so its own error is far below this bound and this is the
             ceiling the `ddpow` arms are measured against.

A third number is reported for context only: `c_scaled`, the exact solve in the
centred/scaled basis followed by an EXACT map back to the published parameterisation. It
exists to show that basis conditioning changes the reachable ceiling — upward on Filip,
sharply downward on the Wampler family — which is a property of the reparameterisation and
not of any arithmetic.

Cross-checked against mpmath at two precisions so convergence is proven rather than assumed.
"""

from __future__ import annotations

import json
import os
import struct
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import load  # noqa: E402

load.HERE = os.path.join(HERE, "data")

import emit_specs  # noqa: E402


def f64(v: Fraction) -> float:
    """Round an exact rational to the nearest float64. `float(Fraction)` is correctly rounded."""
    return float(v)


def solve_exact(cols: list[list[Fraction]], y: list[Fraction]) -> list[Fraction]:
    """Exact least-squares minimiser via the normal equations over Fraction."""
    p = len(cols)
    n = len(y)
    g = [[sum(cols[i][k] * cols[j][k] for k in range(n)) for j in range(p)] for i in range(p)]
    rhs = [sum(cols[i][k] * y[k] for k in range(n)) for i in range(p)]
    # Gaussian elimination with partial pivoting on magnitude (exact, so pivoting is only
    # needed to avoid a zero pivot).
    for i in range(p):
        piv = max(range(i, p), key=lambda r: abs(g[r][i]))
        if g[piv][i] == 0:
            raise ValueError("singular gram matrix")
        g[i], g[piv] = g[piv], g[i]
        rhs[i], rhs[piv] = rhs[piv], rhs[i]
        for r in range(i + 1, p):
            f = g[r][i] / g[i][i]
            if f:
                for c in range(i, p):
                    g[r][c] -= f * g[i][c]
                rhs[r] -= f * rhs[i]
    out = [Fraction(0)] * p
    for i in range(p - 1, -1, -1):
        s = rhs[i] - sum(g[i][j] * out[j] for j in range(i + 1, p))
        out[i] = s / g[i][i]
    return out


def build_cols(x: list[float], lo: int, hi: int, exact_powers: bool) -> list[list[Fraction]]:
    n = len(x)
    fx = [Fraction(v) for v in x]
    if exact_powers:
        pw = [[Fraction(1)] * n]
        for _ in range(hi):
            prev = pw[-1]
            pw.append([prev[i] * fx[i] for i in range(n)])
    else:
        # powers by repeated FLOAT64 multiplication, then lifted exactly
        pwf = [[1.0] * n]
        for _ in range(hi):
            prev = pwf[-1]
            pwf.append([prev[i] * x[i] for i in range(n)])
        pw = [[Fraction(v) for v in col] for col in pwf]
    return [pw[k] for k in range(lo, hi + 1)]


def mp_check(cols_f: list[list[float]], y: list[float], dps: int) -> list[float]:
    """Independent witness: the same normal equations solved with mpmath at `dps` digits."""
    from mpmath import mp, matrix, lu_solve

    mp.dps = dps
    p = len(cols_f)
    n = len(y)
    g = matrix(p, p)
    r = matrix(p, 1)
    for i in range(p):
        for j in range(p):
            g[i, j] = sum(mp.mpf(cols_f[i][k]) * mp.mpf(cols_f[j][k]) for k in range(n))
        r[i] = sum(mp.mpf(cols_f[i][k]) * mp.mpf(y[k]) for k in range(n))
    sol = lu_solve(g, r)
    return [float(sol[i]) for i in range(p)]


def main() -> None:
    out = {}
    for name in load.ORDER:
        nraw, lo_deg, hi_deg, is_poly = emit_specs.SPEC[name]
        xcols, y, beta = load.raw(name)
        fy = [Fraction(v) for v in y]
        rec: dict[str, object] = {}

        if is_poly:
            x = xcols[0]
            variants = {
                "c_recipe": build_cols(x, lo_deg, hi_deg, False),
                "c_exactpow": build_cols(x, lo_deg, hi_deg, True),
            }
        else:
            cols = [[Fraction(1)] * len(y)] + [
                [Fraction(v) for v in xcols[j]] for j in range(nraw)
            ]
            variants = {"c_recipe": cols, "c_exactpow": cols}

        for key, cols in variants.items():
            sol = solve_exact(cols, fy)
            est = [f64(v) for v in sol]
            rec[key] = load.min_lre(est, beta)
            rec[key + "_per_param"] = [load.lre(e, c) for e, c in zip(est, beta)]
            rec[key + "_hex"] = [
                "%016x" % struct.unpack("<Q", struct.pack("<d", v))[0] for v in est
            ]

        # Two independent mpmath witnesses on the recipe basis, to prove the exact-rational
        # arm is not the only thing saying this.
        cols_f = [[float(v) for v in c] for c in variants["c_recipe"]]
        w120 = mp_check(cols_f, y, 120)
        w200 = mp_check(cols_f, y, 200)
        rec["mp120_min_lre"] = load.min_lre(w120, beta)
        rec["mp200_min_lre"] = load.min_lre(w200, beta)
        rec["mp_witness_agree"] = all(
            a == b or abs(a - b) <= 1e-12 * max(abs(a), abs(b)) for a, b in zip(w120, w200)
        )

        # c_scaled: exact solve in numpy's conditioned basis, EXACT map back.
        if is_poly and lo_deg == 0:
            x = xcols[0]
            xmin, xmax = min(x), max(x)
            span = xmax - xmin
            scl = 2.0 / span
            off = -(xmax + xmin) / span
            t = [off + scl * xv for xv in x]  # float64, exactly as numpy does it
            tcols = build_cols(t, 0, hi_deg, True)
            csol = solve_exact(tcols, fy)
            # beta_j = scl^j * sum_{k>=j} c_k * C(k,j) * off^(k-j), exactly
            fo, fs = Fraction(off), Fraction(scl)
            deg = hi_deg
            binom = [[0] * (deg + 1) for _ in range(deg + 1)]
            for k in range(deg + 1):
                binom[k][0] = 1
                for j in range(1, k + 1):
                    binom[k][j] = binom[k - 1][j - 1] + binom[k - 1][j]
            bexact = []
            for j in range(deg + 1):
                acc = Fraction(0)
                for k in range(j, deg + 1):
                    acc += csol[k] * binom[k][j] * fo ** (k - j)
                bexact.append(acc * fs**j)
            rec["c_scaled"] = load.min_lre([f64(v) for v in bexact], beta)
            rec["c_scaled_inbasis_note"] = "reported in the PUBLISHED basis, mapped back exactly"
        else:
            rec["c_scaled"] = None

        rec["certified"] = [repr(v) for v in beta]
        out[name] = rec
        print(
            "%-9s c_recipe %7.4f  c_exactpow %7.4f  c_scaled %s  mp120 %7.4f mp200 %7.4f agree %s"
            % (
                name,
                rec["c_recipe"],
                rec["c_exactpow"],
                ("%7.4f" % rec["c_scaled"]) if rec["c_scaled"] is not None else "    n/a",
                rec["mp120_min_lre"],
                rec["mp200_min_lre"],
                rec["mp_witness_agree"],
            )
        )
    with open(os.path.join(HERE, "ceilings.json"), "w") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
