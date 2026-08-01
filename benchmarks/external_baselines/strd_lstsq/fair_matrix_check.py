"""Close the strongest objection to the StRD result: "you won by building a better matrix."

The shipped route (`D_ddpow_matrix__dd_solve`) does two things the reference arms do not: it
forms the powers of x in double-double, and it carries the factorisation in double-double.
`score.py` separates those with arms B and C, but both of those are the *engine's own* float64
Householder, so a reader can still ask whether a tuned LAPACK driver handed the better matrix
would close the gap on its own.

This script answers that directly. It builds the design matrix with the powers formed EXACTLY
over `fractions.Fraction` and rounded once to float64 — which is the best float64 design matrix
that exists for this model, and is bit-identical to what double-double power formation produces
up to its own ~2^-106 error — then hands that matrix to every LAPACK-backed reference arm and
scores it against the certified values by the same metric.

If the arms do not improve, the design-matrix construction is not where their digits were going
and the compensated solve is what is buying the result. Reported either way.

    /tmp/bb/bin/python -P fair_matrix_check.py
"""

from __future__ import annotations

import json
import os
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import load  # noqa: E402

load.HERE = os.path.join(HERE, "data")

import emit_specs  # noqa: E402
import score  # noqa: E402


def exact_power_design(name: str):
    """Design matrix with powers formed exactly over the rationals, rounded once to float64."""
    nraw, lo_deg, hi_deg, is_poly = emit_specs.SPEC[name]
    xcols, y, beta = load.raw(name)
    n = len(y)
    if not is_poly:
        return None
    fx = [Fraction(v) for v in xcols[0]]
    pw = [[Fraction(1)] * n]
    for _ in range(hi_deg):
        prev = pw[-1]
        pw.append([prev[i] * fx[i] for i in range(n)])
    cols = [[float(v) for v in pw[k]] for k in range(lo_deg, hi_deg + 1)]
    return cols, y, beta, xcols[0], (lo_deg, hi_deg, is_poly)


#: Arms that consume a design matrix. The series-fit arms build their own basis from x and are
#: therefore unaffected by this substitution, so they are excluded rather than reported twice.
MATRIX_ARMS = [
    (label, fn)
    for label, fn in score.ARMS
    if label
    not in {
        "Polynomial.fit",
        "Chebyshev.fit",
        "Legendre.fit",
        "Hermite.fit",
        "HermiteE.fit",
        "Laguerre.fit",
        "np.polyfit(legacy)",
    }
]


def main() -> None:
    versions = score.assert_versions()
    print("versions:", json.dumps(versions, sort_keys=True))
    print("loadavg: %.2f %.2f %.2f" % os.getloadavg())
    print()
    print("Every arm below is run TWICE on the same dataset: once on the published recipe matrix")
    print("(powers by repeated float64 multiplication) and once on the exactly-formed power")
    print("matrix rounded to float64. `exactnum` is the compensated route, for reference.")
    print()
    out = {}
    hdr = "%-9s %-32s %8s %8s %8s" % ("dataset", "arm", "recipe", "exactpow", "delta")
    print(hdr)
    print("-" * len(hdr))
    improved = 0
    total = 0
    best_exactpow = {}
    for name in load.ORDER:
        got = exact_power_design(name)
        if got is None:
            continue
        colsE, y, beta, x, meta = got
        colsR, _, _, _, _ = score.design(name)
        XE = list(zip(*colsE))
        XR = list(zip(*colsR))
        for label, fn in MATRIX_ARMS:
            try:
                estR = fn(XR, y, x, meta)
                estE = fn(XE, y, x, meta)
            except Exception as exc:  # noqa: BLE001
                print("%-9s %-32s   EXC %s" % (name, label, type(exc).__name__))
                continue
            if estR is None or estE is None:
                continue
            lreR = load.min_lre(estR, beta)
            lreE = load.min_lre(estE, beta)
            total += 1
            if lreE > lreR + 5e-3:
                improved += 1
            if label not in score.CONTROL_ARMS:
                best_exactpow[name] = max(best_exactpow.get(name, 0.0), lreE)
            out.setdefault(name, {})[label] = {"recipe": lreR, "exactpow": lreE}
            print(
                "%-9s %-32s %8.2f %8.2f %+8.2f"
                % (name, label, lreR, lreE, lreE - lreR)
            )
        print()

    scores = json.load(open(os.path.join(HERE, "scores.json")))
    print("Does the better matrix alone let any LAPACK arm reach the compensated route?")
    print("%-9s %14s %14s %10s" % ("dataset", "best exactpow", "exactnum", "still short by"))
    verdict_ok = True
    for name in sorted(best_exactpow, key=load.ORDER.index):
        ours = scores["datasets"][name]["mojo"]["D_ddpow_matrix__dd_solve"]["min_lre"]
        b = best_exactpow[name]
        print("%-9s %14.2f %14.2f %10.2f" % (name, b, ours, ours - b))
        if b > ours + 5e-3:
            verdict_ok = False
    print()
    print("arms that improved on the exactly-formed matrix: %d of %d" % (improved, total))
    print(
        "no reference arm overtakes the compensated route on the better matrix: %s"
        % verdict_ok
    )
    with open(os.path.join(HERE, "fair_matrix.json"), "w") as fh:
        json.dump(
            {"versions": versions, "arms": out, "improved": improved, "total": total,
             "no_arm_overtakes": verdict_ok},
            fh,
            indent=2,
            sort_keys=True,
        )
    print("wrote fair_matrix.json")
    raise SystemExit(0 if verdict_ok else 1)


if __name__ == "__main__":
    main()
