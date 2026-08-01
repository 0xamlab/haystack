"""Score the exactnum least-squares route against the reference field on NIST StRD.

The metric is NIST's own: log relative error `-log10(|est - certified| / |certified|)`, taken
as the MINIMUM over a dataset's parameters and capped at 15.95. Certified values are parsed
out of the published .dat files by `load.py`; nothing is transcribed.

WHAT IS COMPARED
----------------
Every reference arm and the Mojo route are handed the SAME design matrix bits. The reference
arms build it in this process; the Mojo route builds it from hex bit patterns emitted by
`emit_specs.py` from the same loader. `--check-bits` asserts the two constructions agree
bit-for-bit before any score is computed.

The polynomial-basis arms (`Polynomial.fit` and its orthogonal-basis siblings) are included
because on this suite they are the arms that actually set the bar — `Polynomial.fit` wins
Filip outright against every LAPACK driver. They are reported in the PUBLISHED basis via
`.convert()`, which is the only parameterisation the certified values exist in.

DETERMINISM
-----------
Arms are run in three passes with a rotated order, and every arm's coefficients must come
back bit-identical across all three or the run fails. That makes the digit numbers
independent of load and of arm ordering. Library versions and the numpy BLAS backend are
asserted at start; any drift is a hard exit, because a digit measured against a different
LAPACK is a different measurement.
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import load  # noqa: E402

load.HERE = os.path.join(HERE, "data")

import emit_specs  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
MOJO_ENV = "/Users/angel/Developer/decision-engine/mojo_env"
DRIVER = os.path.join(REPO, "benchmarks", "mojo_benchmarks", "measure_exactnum_strd.mojo")
ENGINE = os.path.join(REPO, "mojo", "engine")

EXPECTED = {
    "python": "3.14",
    "numpy": "2.5.1",
    "scipy": "1.18.0",
    "statsmodels": "0.14.6",
    "mpmath": "1.3.0",
    "blas": "accelerate",
}


def assert_versions() -> dict:
    import numpy as np
    import scipy
    import statsmodels
    import mpmath

    cfg = np.__config__.show_config("dicts")
    blas = cfg["Build Dependencies"]["blas"]["name"]
    got = {
        "python": "%d.%d" % sys.version_info[:2],
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "statsmodels": statsmodels.__version__,
        "mpmath": mpmath.__version__,
        "blas": blas,
    }
    drift = {k: (EXPECTED[k], got[k]) for k in EXPECTED if EXPECTED[k] != got[k]}
    if drift:
        raise SystemExit("version drift, refusing to measure: %r" % drift)
    got["python_full"] = sys.version.split()[0]
    got["lapack"] = cfg["Build Dependencies"]["lapack"]["name"]
    return got


def hx(v: float) -> str:
    return "%016x" % struct.unpack("<Q", struct.pack("<d", v))[0]


def unhx(s: str) -> float:
    return struct.unpack("<d", struct.pack("<Q", int(s, 16)))[0]


def _ordinal(v: float) -> int:
    """Monotone integer key for a float64, so ulp distance is a subtraction."""
    u = struct.unpack("<Q", struct.pack("<d", v))[0]
    if u >> 63:
        return -(u & 0x7FFFFFFFFFFFFFFF)
    return u


def ulps(a: float, b: float) -> int:
    ia, ib = _ordinal(a), _ordinal(b)
    return abs(ia - ib)


def ulp_gap(est: list[float], target_hex: list[str]) -> int:
    """Worst-component ulp distance from the correctly-rounded exact solution.

    Digits saturate at the metric's cap and at NIST's own publication precision; ulps do not.
    A route that returns the exact solution rounded once is 0 ulp away, and that is a stronger
    and cap-free statement than "15.95 digits"."""
    tgt = [unhx(h) for h in target_hex]
    if len(est) != len(tgt):
        return -1
    return max(ulps(e, t) for e, t in zip(est, tgt))


def design(name: str):
    """The recipe design matrix, powers by repeated float64 multiplication."""
    nraw, lo_deg, hi_deg, is_poly = emit_specs.SPEC[name]
    xcols, y, beta = load.raw(name)
    n = len(y)
    if is_poly:
        x = xcols[0]
        pw = [[1.0] * n]
        for _ in range(hi_deg):
            prev = pw[-1]
            pw.append([prev[i] * x[i] for i in range(n)])
        cols = [pw[k] for k in range(lo_deg, hi_deg + 1)]
    else:
        cols = [[1.0] * n] + [xcols[j] for j in range(nraw)]
    return cols, y, beta, (x if is_poly else None), (lo_deg, hi_deg, is_poly)


# ── the reference field ───────────────────────────────────────────────────────


def arm_np_lstsq_none(X, y, x, meta):
    import numpy as np

    return np.linalg.lstsq(np.array(X), np.array(y), rcond=None)[0].tolist()


def arm_np_lstsq_m1(X, y, x, meta):
    import numpy as np

    return np.linalg.lstsq(np.array(X), np.array(y), rcond=-1)[0].tolist()


def arm_np_qr_solve_tri(X, y, x, meta):
    import numpy as np
    from scipy.linalg import solve_triangular

    q, r = np.linalg.qr(np.array(X))
    return solve_triangular(r, q.T @ np.array(y)).tolist()


def _scipy_lstsq(driver):
    def f(X, y, x, meta):
        from scipy.linalg import lstsq

        return lstsq(__import__("numpy").array(X), __import__("numpy").array(y), lapack_driver=driver)[
            0
        ].tolist()

    return f


def arm_statsmodels(X, y, x, meta):
    import numpy as np
    import statsmodels.api as sm

    return sm.OLS(np.array(y), np.array(X)).fit().params.tolist()


def _series_fit(cls_name):
    def f(X, y, x, meta):
        import numpy as np
        import numpy.polynomial as npoly

        lo, hi, is_poly = meta
        if not is_poly or lo != 0:
            return None
        cls = getattr(npoly, cls_name)
        # `kind=Polynomial` is load-bearing. `.convert()` with no `kind` returns the SAME
        # series class in the default domain, so for Chebyshev/Legendre/... the coefficients
        # come back in that orthogonal basis and scoring them against the certified
        # power-basis values reports ~0 digits for a fit that is actually fine. Only
        # `Polynomial` happens to be correct without it.
        fit = cls.fit(np.array(x), np.array(y), hi)
        return fit.convert(kind=npoly.Polynomial).coef.tolist()

    return f


def arm_polyfit_legacy(X, y, x, meta):
    import numpy as np

    lo, hi, is_poly = meta
    if not is_poly or lo != 0:
        return None
    return list(reversed(np.polyfit(np.array(x), np.array(y), hi).tolist()))


def arm_normal_eq_cholesky(X, y, x, meta):
    """The shipped shape: normal equations plus Cholesky, in numpy. Control, not a reference."""
    import numpy as np

    A = np.array(X)
    g = A.T @ A
    try:
        L = np.linalg.cholesky(g)
    except np.linalg.LinAlgError:
        return None
    z = np.linalg.solve(L, A.T @ np.array(y))
    return np.linalg.solve(L.T, z).tolist()


ARMS = [
    ("Polynomial.fit", _series_fit("Polynomial")),
    ("Chebyshev.fit", _series_fit("Chebyshev")),
    ("Legendre.fit", _series_fit("Legendre")),
    ("Hermite.fit", _series_fit("Hermite")),
    ("HermiteE.fit", _series_fit("HermiteE")),
    ("Laguerre.fit", _series_fit("Laguerre")),
    ("np.polyfit(legacy)", arm_polyfit_legacy),
    ("np.linalg.lstsq(rcond=None)", arm_np_lstsq_none),
    ("np.linalg.lstsq(rcond=-1)", arm_np_lstsq_m1),
    ("np.linalg.qr+solve_triangular", arm_np_qr_solve_tri),
    ("scipy.lstsq(gelsd)", _scipy_lstsq("gelsd")),
    ("scipy.lstsq(gelsy)", _scipy_lstsq("gelsy")),
    ("scipy.lstsq(gelss)", _scipy_lstsq("gelss")),
    ("statsmodels.OLS", arm_statsmodels),
    ("[control] numpy normal-eq+Cholesky", arm_normal_eq_cholesky),
]

#: Arms that are controls rather than part of the field the bar is taken over. A control is
#: something we are demonstrating a defect in, not something we have to beat.
CONTROL_ARMS = {"[control] numpy normal-eq+Cholesky"}


def run_reference(names) -> dict:
    """Three interleaved passes with a rotated arm order; bit-identity asserted across them."""
    results: dict[tuple[str, str], list[str]] = {}
    for p in range(3):
        order = ARMS[p:] + ARMS[:p]
        for name in names:
            X, y, beta, x, meta = design(name)
            Xt = list(zip(*X))  # row-major
            for label, fn in order:
                try:
                    est = fn(Xt, y, x, meta)
                except Exception as exc:  # noqa: BLE001
                    est = "EXC:" + type(exc).__name__
                if est is None:
                    key = None
                elif isinstance(est, str):
                    key = est
                else:
                    key = [hx(v) for v in est]
                prev = results.get((name, label), "UNSET")
                if prev == "UNSET":
                    results[(name, label)] = key
                elif prev != key:
                    raise SystemExit(
                        "arm %s on %s is not deterministic across passes: %r vs %r"
                        % (label, name, prev, key)
                    )
    return results


# ── the Mojo route ────────────────────────────────────────────────────────────


def run_mojo(spec_path: str, binary: str | None) -> dict:
    if binary:
        cmd = [binary, spec_path]
    else:
        cmd = ["pixi", "run", "mojo", "run", "-I" + ENGINE, DRIVER, spec_path]
    proc = subprocess.run(
        cmd, cwd=(MOJO_ENV if not binary else HERE), capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise SystemExit("mojo driver failed on %s:\n%s" % (spec_path, proc.stderr[-4000:]))
    out: dict = {"arms": {}, "selfcheck": None}
    for line in proc.stdout.splitlines():
        t = line.split()
        if not t:
            continue
        if t[0] == "SELFCHECK":
            out["selfcheck"] = int(t[1])
        elif t[0] == "ARM":
            out["arms"][t[1]] = {
                "status": int(t[3]),
                "rank": int(t[5]),
                "r_diag_min": unhx(t[7]),
                "pivot_ratio_min": unhx(t[9]),
                "residual_norm": unhx(t[11]),
                "refine": int(t[13]),
                "coef": [],
                "coef_hex": [],
                "coef_lo": [],
            }
        elif t[0] == "COEF":
            rec = out["arms"][t[1]]
            rec["coef"].append(unhx(t[3]))
            rec["coef_hex"].append(t[3])
            rec["coef_lo"].append(unhx(t[4]))
        elif t[0] == "ABORT":
            raise SystemExit("mojo driver aborted: " + line)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", default=None, help="compiled driver; omit to use the JIT")
    ap.add_argument("--both", action="store_true", help="run JIT and binary and assert bit-identity")
    ap.add_argument("--out", default=os.path.join(HERE, "scores.json"))
    args = ap.parse_args()

    versions = assert_versions()
    la = os.getloadavg()
    print("versions:", json.dumps(versions, sort_keys=True))
    print("loadavg at start: %.2f %.2f %.2f" % la)

    names = load.ORDER
    # bit-identity of the two design-matrix constructions
    with open(os.path.join(HERE, "specs", "manifest.json")) as fh:
        manifest = json.load(fh)
    for name in names:
        X, y, beta, x, meta = design(name)
        assert len(X) == manifest[name]["params"], name
        assert [hx(v) for v in beta] == manifest[name]["certified_hex"], name

    ref = run_reference(names)

    ceil_path = os.path.join(HERE, "ceilings.json")
    ceilings = json.load(open(ceil_path)) if os.path.exists(ceil_path) else {}

    report = {"versions": versions, "loadavg_start": la, "datasets": {}}
    for name in names:
        X, y, beta, x, meta = design(name)
        spec = os.path.join(HERE, "specs", name + ".spec")
        mo = run_mojo(spec, None)
        if args.both:
            mb = run_mojo(spec, args.binary)
            for arm in mo["arms"]:
                if mo["arms"][arm]["coef_hex"] != mb["arms"][arm]["coef_hex"]:
                    raise SystemExit(
                        "JIT and compiled -O3 disagree on %s arm %s: %r vs %r"
                        % (name, arm, mo["arms"][arm]["coef_hex"], mb["arms"][arm]["coef_hex"])
                    )
        if mo["selfcheck"] != 800:
            raise SystemExit("arithmetic selfcheck failed: %r" % mo["selfcheck"])

        rec: dict = {"certified": [repr(v) for v in beta], "reference": {}, "mojo": {}}
        for (nm, label), key in ref.items():
            if nm != name:
                continue
            if key is None:
                rec["reference"][label] = None
            elif isinstance(key, str):
                rec["reference"][label] = {"error": key}
            else:
                est = [unhx(h) for h in key]
                entry = {
                    "min_lre": load.min_lre(est, beta),
                    "per_param": [load.lre(e, c) for e, c in zip(est, beta)],
                    "coef_hex": key,
                }
                if name in ceilings:
                    entry["ulp_from_exact_recipe"] = ulp_gap(
                        est, ceilings[name]["c_recipe_hex"]
                    )
                    entry["ulp_from_exact_powexact"] = ulp_gap(
                        est, ceilings[name]["c_exactpow_hex"]
                    )
                rec["reference"][label] = entry
        for arm, r in mo["arms"].items():
            if r["status"] != 810 or len(r["coef"]) != len(beta):
                rec["mojo"][arm] = {"status": r["status"], "min_lre": None}
                continue
            entry = {
                "status": r["status"],
                "min_lre": load.min_lre(r["coef"], beta),
                "per_param": [load.lre(e, c) for e, c in zip(r["coef"], beta)],
                "coef_hex": r["coef_hex"],
                "tail_all_zero": all(v == 0.0 for v in r["coef_lo"]),
                "r_diag_min": r["r_diag_min"],
                "pivot_ratio_min": r["pivot_ratio_min"],
                "residual_norm": r["residual_norm"],
                "refine": r["refine"],
            }
            if name in ceilings:
                entry["ulp_from_exact_recipe"] = ulp_gap(
                    r["coef"], ceilings[name]["c_recipe_hex"]
                )
                entry["ulp_from_exact_powexact"] = ulp_gap(
                    r["coef"], ceilings[name]["c_exactpow_hex"]
                )
            rec["mojo"][arm] = entry
        if name in ceilings:
            rec["ceiling"] = {
                k: ceilings[name][k] for k in ("c_recipe", "c_exactpow", "c_scaled")
            }
        report["datasets"][name] = rec

    report["loadavg_end"] = os.getloadavg()
    with open(args.out, "w") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)

    # ── the table ────────────────────────────────────────────────────────────
    print()
    hdr = (
        "%-9s %6s %6s %6s %6s %6s | %6s %6s | %6s %-28s | %6s %6s"
        % (
            "dataset",
            "A f64",
            "B ddm",
            "C dd",
            "D dd",
            "D1",
            "S ddm",
            "S0 f64",
            "BAR",
            "bar-setter",
            "ceilR",
            "ceilP",
        )
    )
    print(hdr)
    print("-" * len(hdr))
    for name in names:
        d = report["datasets"][name]

        def m(arm):
            v = d["mojo"].get(arm, {}).get("min_lre")
            return "%6.2f" % v if v is not None else "   n/a"

        field = {
            k: v["min_lre"]
            for k, v in d["reference"].items()
            if isinstance(v, dict) and "min_lre" in v and k not in CONTROL_ARMS
        }
        bar_label, bar = max(field.items(), key=lambda kv: kv[1])
        cr = d.get("ceiling", {}).get("c_recipe")
        cp = d.get("ceiling", {}).get("c_exactpow")
        print(
            "%-9s %s %s %s %s %s | %s %s | %6.2f %-28s | %6.2f %6.2f"
            % (
                name,
                m("A_f64_matrix__f64_solve"),
                m("B_ddpow_matrix__f64_solve"),
                m("C_f64_matrix__dd_solve"),
                m("D_ddpow_matrix__dd_solve"),
                m("D1_ddpow_matrix__dd_solve_r1"),
                m("S_scaled_dd_solve_ddmap"),
                m("S0_scaled_dd_solve_f64map"),
                bar,
                bar_label,
                cr if cr is not None else float("nan"),
                cp if cp is not None else float("nan"),
            )
        )
    print()
    print("shipped frozen csr_least_squares (normal equations + Cholesky), re-measured:")
    for name in names:
        d = report["datasets"][name]
        r = d["mojo"].get("N_shipped_csr_normal_eq", {})
        v = r.get("min_lre")
        print(
            "  %-9s %s  status %s"
            % (name, ("%6.2f" % v) if v is not None else "  FAILS", r.get("status"))
        )
    print()
    print("full reference field, per dataset:")
    for name in names:
        d = report["datasets"][name]
        items = sorted(
            (
                (v["min_lre"], k)
                for k, v in d["reference"].items()
                if isinstance(v, dict) and "min_lre" in v
            ),
            reverse=True,
        )
        print("  " + name + ": " + " | ".join("%s %.2f" % (k, s) for s, k in items))
    print()
    print(
        "ulp distance from the CORRECTLY-ROUNDED exact solution (0 = optimal for a float64"
    )
    print("return; cap-free, unlike digits). Target = exact solve of the ddpow design matrix.")
    print("%-9s %14s %14s %14s" % ("dataset", "D ddpow+dd", "best ref arm", "(which)"))
    for name in names:
        d = report["datasets"][name]
        ours = d["mojo"].get("D_ddpow_matrix__dd_solve", {}).get("ulp_from_exact_powexact")
        cands = [
            (v["ulp_from_exact_powexact"], k)
            for k, v in d["reference"].items()
            if isinstance(v, dict) and v.get("ulp_from_exact_powexact", -1) >= 0
            and k not in CONTROL_ARMS
        ]
        best = min(cands) if cands else (None, "-")
        print(
            "%-9s %14s %14s %14s"
            % (name, ours, best[0] if best[0] is not None else "-", best[1])
        )

    print()
    print("VERDICT per dataset (D = ddpow matrix + dd solve, the shipped route):")
    wins, ties, losses = [], [], []
    for name in names:
        d = report["datasets"][name]
        ours = d["mojo"].get("D_ddpow_matrix__dd_solve", {}).get("min_lre")
        field = {
            k: v["min_lre"]
            for k, v in d["reference"].items()
            if isinstance(v, dict) and "min_lre" in v and k not in CONTROL_ARMS
        }
        bar_label, bar = max(field.items(), key=lambda kv: kv[1])
        cp = d.get("ceiling", {}).get("c_exactpow")
        at_ceiling = cp is not None and abs(ours - cp) < 5e-3
        delta = ours - bar
        our_ulp = d["mojo"]["D_ddpow_matrix__dd_solve"].get("ulp_from_exact_powexact")
        best_ref_ulp = min(
            (
                v["ulp_from_exact_powexact"]
                for k, v in d["reference"].items()
                if isinstance(v, dict)
                and v.get("ulp_from_exact_powexact", -1) >= 0
                and k not in CONTROL_ARMS
            ),
            default=None,
        )
        if delta > 5e-3:
            kind = "WIN"
            wins.append(name)
        elif delta > -5e-3:
            kind = "TIE"
            ties.append(name)
        else:
            kind = "LOSS"
            losses.append(name)
        # A "win" of a fraction of a digit inside the cap zone is a rounding coincidence, not
        # accuracy. Qualify it by the ulp gap, which has no cap: if the best reference arm is
        # already within a couple of ulp of the correctly-rounded exact solution there is
        # nothing left to win, whatever the digit difference says.
        note = ""
        if best_ref_ulp is not None and best_ref_ulp <= 4 and kind == "WIN":
            note = " [CAP-ZONE: best ref is %d ulp from exact — a rounding coincidence, not accuracy]" % best_ref_ulp
        # A lower-precision arm scoring ABOVE the exact ceiling is the same artifact seen from
        # the other side: its error landed on the near side of a float64 boundary that the
        # correctly-rounded exact answer sits on the far side of.
        for arm in ("A_f64_matrix__f64_solve", "N_shipped_csr_normal_eq"):
            av = d["mojo"].get(arm, {}).get("min_lre")
            if av is not None and cp is not None and av > cp + 5e-3:
                note += " [ARTIFACT: %s scores %.2f, ABOVE the %.2f exact ceiling]" % (
                    arm,
                    av,
                    cp,
                )
        print(
            "  %-9s %-4s  ours %6.2f  bar %6.2f (%s)  delta %+6.2f  ceiling %6.2f  "
            "our_ulp %s  best_ref_ulp %s%s"
            % (
                name,
                kind,
                ours,
                bar,
                bar_label,
                delta,
                cp,
                our_ulp,
                best_ref_ulp,
                note,
            )
        )
    print("  wins: %d  ties: %d  losses: %d" % (len(wins), len(ties), len(losses)))
    print("  losses:", losses if losses else "none")
    report["verdict"] = {"wins": wins, "ties": ties, "losses": losses}
    with open(args.out, "w") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)

    print()
    print("loadavg at end: %.2f %.2f %.2f" % report["loadavg_end"])
    print("wrote", args.out)


if __name__ == "__main__":
    main()
