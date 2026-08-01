"""Validate every exactnum EFT primitive against exact rational arithmetic, at three codegen levels.

Two independent things are checked and they are not the same check:

1. CORRECTNESS against a source that is not float64. Every expected value below comes from
   `fractions.Fraction` (float64 values are dyadic rationals, so `Fraction(x)` is exact and
   sums/products/quotients of them are exact) or, for the square root, from mpmath at 80 and
   120 digits with agreement asserted. No expectation is computed in float64, so a routine
   that silently degraded to float64 cannot agree with it.

2. ANTI-VACUITY. For the designated hard cases the plain-float64 counterpart must give a
   DIFFERENT answer from the compensated one, and the compensated one must be the correct
   one. A test that both routes pass proves nothing about compensation.

3. CODEGEN. The same source is run at `--optimization-level 0`, at `3` (the level
   `scripts/build_mojo_binary.sh` ships) and under the JIT. Every EFT primitive's output must
   be bit-identical across all three. Where something is NOT bit-identical this script says
   so rather than hiding it — see the report at the end.

Operands cross into Mojo as hex bit patterns on argv so the compiler cannot constant-fold the
arithmetic under test and have the fold be mistaken for evidence about generated code.
"""

from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
MOJO_ENV = "/Users/angel/Developer/decision-engine/mojo_env"
SRC = os.path.join(REPO, "benchmarks", "mojo_benchmarks", "measure_exactnum_eft_codegen.mojo")
ENGINE = os.path.join(REPO, "mojo", "engine")


def hx(v: float) -> str:
    return "%016x" % struct.unpack("<Q", struct.pack("<d", v))[0]


def unhx(s: str) -> float:
    return struct.unpack("<d", struct.pack("<Q", int(s, 16)))[0]


def rnd(q: Fraction) -> float:
    """Correctly-rounded float64 of an exact rational. `float(Fraction)` is round-to-nearest."""
    return float(q)


# Operand triples. Each row is chosen so at least one primitive's compensated and plain
# results provably differ.
CASES = [
    # 1 + 2^-52 twice: exact product is 1 + 2^-51 + 2^-104, the tail is the decisive bit.
    (1.0 + 2.0**-52, 1.0 + 2.0**-52, 1.0),
    # a real Filip magnitude: (-6.860120914)^5, whose square needs 106 bits.
    (-6.860120914**5, -6.860120914**5, 1.0 - 2.0**-53),
    # catastrophic magnitude gap, where two_sum's error term carries everything
    (2.0**60, 1.0 + 2.0**-52, 3.0**-7),
    # irrational-ish decimals with long binary expansions
    (0.1, 0.3, 0.7),
    # near-cancelling pair, the case a reflector generates
    (1.0 + 2.0**-40, -(1.0 + 2.0**-41), 2.0**-30),
]


def build(level: int) -> str:
    out = "/tmp/exactnum_eft_O%d" % level
    proc = subprocess.run(
        [
            "pixi", "run", "mojo", "build", "-I" + ENGINE,
            "--optimization-level", str(level), SRC, "-o", out,
        ],
        cwd=MOJO_ENV, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise SystemExit("build -O%d failed:\n%s" % (level, proc.stderr[-3000:]))
    return out


def run(cmd: list[str], cwd: str, argv: list[str]) -> dict[str, str]:
    proc = subprocess.run(cmd + argv, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit("probe failed:\n%s" % proc.stderr[-3000:])
    out = {}
    for line in proc.stdout.splitlines():
        t = line.split()
        if len(t) == 2:
            out[t[0]] = t[1]
        elif len(t) == 1:
            out[t[0]] = ""
    return out


def check_case(a: float, b: float, c: float, keys: dict[str, str]) -> list[tuple[str, bool, str]]:
    """Every assertion for one operand triple. Returns (name, ok, detail)."""
    res: list[tuple[str, bool, str]] = []
    fa, fb, fc = Fraction(a), Fraction(b), Fraction(c)

    def dd_of(prefix: str) -> tuple[float, float]:
        return unhx(keys[prefix + "_HI"]), unhx(keys[prefix + "_LO"])

    def add(name: str, ok: bool, detail: str = "") -> None:
        res.append((name, ok, detail))

    add("selfcheck_ok", keys["SELFCHECK"] == "800", keys["SELFCHECK"])

    # ── two_sum is EXACT: hi + lo == a + b as rationals, with no tolerance at all.
    for tag, (u, v) in (("AB", (fa, fb)), ("BA", (fb, fa))):
        hi, lo = dd_of("TWO_SUM_" + tag)
        add(
            "two_sum_%s_exact" % tag,
            Fraction(hi) + Fraction(lo) == u + v,
            "%r + %r vs exact" % (hi, lo),
        )
        add("two_sum_%s_hi_is_rounded_sum" % tag, hi == rnd(u + v))
    # value symmetry: the sum is symmetric even though the code path is not
    add(
        "two_sum_order_symmetric",
        keys["TWO_SUM_AB_HI"] == keys["TWO_SUM_BA_HI"]
        and Fraction(unhx(keys["TWO_SUM_AB_LO"])) == Fraction(unhx(keys["TWO_SUM_BA_LO"])),
    )

    # fast_two_sum is exact only for the order with the larger magnitude first.
    tag = "AB" if abs(a) >= abs(b) else "BA"
    u, v = (fa, fb) if tag == "AB" else (fb, fa)
    hi, lo = dd_of("FAST_TWO_SUM_" + tag)
    add(
        "fast_two_sum_valid_order_exact",
        Fraction(hi) + Fraction(lo) == u + v,
        "order " + tag,
    )

    # ── two_product is EXACT, and the naive form must lose the tail on the hard cases.
    hi, lo = dd_of("TP_FMA_AB")
    exact_prod = fa * fb
    add("two_product_fma_exact", Fraction(hi) + Fraction(lo) == exact_prod)
    add("two_product_hi_is_rounded_product", hi == rnd(exact_prod))
    dhi, dlo = dd_of("TP_DEKKER_AB")
    add(
        "two_product_dekker_matches_fma",
        (dhi, dlo) == (hi, lo),
        "dekker %r vs fma %r" % ((dhi, dlo), (hi, lo)),
    )
    naive_lo = unhx(keys["TP_NAIVE_LO_AB"])
    tail_is_nonzero = lo != 0.0
    add(
        "ANTIVACUITY_naive_two_product_loses_tail",
        (not tail_is_nonzero) or naive_lo == 0.0,
        "exact tail %r, naive tail %r" % (lo, naive_lo),
    )
    # fma vs mul-then-add on the same triple
    fma_v = unhx(keys["FMA_A_B_C"])
    add("fma_single_rounding", Fraction(fma_v) == Fraction(rnd(fa * fb + fc)))

    # ── double-double arithmetic against exact rationals. dd is not exact, so the bound is
    # the published one: ~2^-105 relative for add/sub/mul, ~2^-104 for div. `hi` must also be
    # the correctly-rounded float64 of the exact result, which is the property the whole
    # "round once at the end" design rests on.
    Ahi, Alo = dd_of("DD_A")
    Bhi, Blo = dd_of("DD_B")
    ea = Fraction(Ahi) + Fraction(Alo)
    eb = Fraction(Bhi) + Fraction(Blo)
    add("dd_a_is_exact_product", ea == fa * fb)
    add("dd_b_is_exact_product", eb == fb * fc)

    def dd_close(name: str, prefix: str, exact: Fraction, bits: int) -> None:
        hi, lo = dd_of(prefix)
        got = Fraction(hi) + Fraction(lo)
        if exact == 0:
            add(name, got == 0)
            return
        rel = abs(got - exact) / abs(exact)
        add(name, rel <= Fraction(2) ** (-bits), "rel 2^%.1f" % _log2(rel))
        add(name + "_hi_correctly_rounded", hi == rnd(exact), "%r vs %r" % (hi, rnd(exact)))

    dd_close("dd_add", "DD_ADD", ea + eb, 100)
    dd_close("dd_sub", "DD_SUB", ea - eb, 100)
    dd_close("dd_mul", "DD_MUL", ea * eb, 100)
    if eb != 0:
        dd_close("dd_div", "DD_DIV", ea / eb, 98)

    # dd_sqrt against mpmath at two precisions, agreement asserted, so convergence is proven.
    from mpmath import mp, mpf, sqrt as mpsqrt

    target = abs(ea)
    hi, lo = dd_of("DD_SQRT_ABS_A")
    got = Fraction(hi) + Fraction(lo)
    roots = []
    for dps in (80, 120):
        mp.dps = dps
        roots.append(mpsqrt(mpf(target.numerator) / mpf(target.denominator)))
    mp.dps = 120
    agree = abs(roots[0] - roots[1]) <= mpf(10) ** (-70) * abs(roots[1])
    add("dd_sqrt_witnesses_agree", bool(agree))
    if target > 0:
        mp.dps = 120
        rel = abs(mpf(got.numerator) / mpf(got.denominator) - roots[1]) / abs(roots[1])
        add("dd_sqrt_rel_le_2e-100", bool(rel <= mpf(2) ** -100), "rel %s" % mp.nstr(rel, 5))
        # hi must be the correctly-rounded square root
        add("dd_sqrt_hi_correctly_rounded", hi == float(roots[1]))

    # ── the hard summation: plain float64 provably wrong, compensated provably right.
    exact_hard = Fraction(2) ** 54 + 500
    plain = unhx(keys["HARD_PLAIN_SUM"])
    kahan = unhx(keys["HARD_KAHAN_FROZEN"])
    shi, slo = dd_of("HARD_SUM2")
    add(
        "ANTIVACUITY_plain_sum_is_wrong",
        Fraction(plain) != exact_hard,
        "plain %r vs exact %s" % (plain, exact_hard),
    )
    add("sum2_is_exact", Fraction(shi) + Fraction(slo) == exact_hard, "%r %r" % (shi, slo))
    add("frozen_kahan_also_recovers_it", Fraction(kahan) == exact_hard, repr(kahan))

    # ── Dot2 against the exact rational dot product.
    xs = [fa, fb, fc, -fa, -fb, -fc, Fraction(a * b)]
    ys = [fb, fc, fa, fb, fc, fa, Fraction(1)]
    exact_dot = sum(u * v for u, v in zip(xs, ys))
    dhi2, dlo2 = dd_of("DOT2")
    got = Fraction(dhi2) + Fraction(dlo2)
    if exact_dot == 0:
        add("dot2_exact_zero", got == 0)
    else:
        rel = abs(got - exact_dot) / abs(exact_dot)
        add("dot2_rel_le_2e-100", rel <= Fraction(2) ** -100, "rel 2^%.1f" % _log2(rel))
        add("dot2_hi_correctly_rounded", dhi2 == rnd(exact_dot))

    # The DESIGNED hard dot product: exact answer 2, plain sequential float64 returns 0.
    # This is the operand-independent anti-vacuity case for Dot2. On the generic triples above
    # plain float64 sometimes happens to be right, which is exactly why a purpose-built case
    # is needed and why "the two arms differ" is not asserted there.
    hp = unhx(keys["HARD_DOT_PLAIN"])
    hhi, hlo = dd_of("HARD_DOT2")
    add("ANTIVACUITY_hard_dot_plain_is_wrong", Fraction(hp) != 2, repr(hp))
    add("hard_dot2_is_exact", Fraction(hhi) + Fraction(hlo) == 2, "%r %r" % (hhi, hlo))
    return res


def _log2(q: Fraction) -> float:
    import math

    if q == 0:
        return float("-inf")
    return math.log2(float(q)) if float(q) > 0 else -400.0


#: Keys whose value is allowed to differ between codegen levels, with the reason. Anything
#: else differing is a hard failure.
CODEGEN_TOLERATED = {
    # `w[i] - a * v[i]` and `p.lo + a.hi * b.lo` are contracted into an FMA at -O3 and under
    # the JIT but not at -O0 (proved separately in the report below). Inside dd_mul / dd_div
    # that term is the O(eps) correction whose own error is O(eps^2) — below what a
    # double-double can hold — so contracting it moves the TAIL and can never move `hi`.
    "DD_MUL_LO", "DD_DIV_LO", "DD_SQRT_ABS_A_LO",
    # the plain-float64 counterparts are contraction-sensitive by construction; that is the
    # point of printing them
    "MUL_ADD_A_B_C", "DOT_PLAIN", "PLAIN_ADD", "PLAIN_MUL", "PLAIN_DIV",
    # the contraction probe itself: its whole purpose is to come out differently per level
    "AXPY_PLAIN", "AXPY_CONTRACTED",
}


def main() -> None:
    o0 = build(0)
    o3 = build(3)
    runners = {
        "O0": (lambda av: run([o0], HERE, av)),
        "O3": (lambda av: run([o3], HERE, av)),
        "JIT": (
            lambda av: run(
                ["pixi", "run", "mojo", "run", "-I" + ENGINE, SRC], MOJO_ENV, av
            )
        ),
    }

    total = 0
    failed: list[str] = []
    codegen_diffs: list[str] = []
    report = {"cases": []}
    for (a, b, c) in CASES:
        argv = [hx(a), hx(b), hx(c)]
        outs = {k: fn(argv) for k, fn in runners.items()}
        # codegen identity
        for key in sorted(outs["O3"]):
            vals = {lvl: outs[lvl].get(key) for lvl in outs}
            if len(set(vals.values())) != 1:
                line = "%s %s: %r" % (argv, key, vals)
                codegen_diffs.append(line)
                if key not in CODEGEN_TOLERATED:
                    failed.append("CODEGEN " + line)
        # correctness, on the shipped level
        for lvl in ("O0", "O3", "JIT"):
            for name, ok, detail in check_case(a, b, c, outs[lvl]):
                total += 1
                if not ok:
                    failed.append("%s %s %s %s" % (lvl, argv, name, detail))
        report["cases"].append({"operands": argv, "o3": outs["O3"]})

    print("assertions run: %d" % total)
    print("failures: %d" % len(failed))
    for f in failed[:40]:
        print("  FAIL", f)
    print()
    print("keys that are NOT bit-identical across -O0 / -O3 / JIT: %d" % len(codegen_diffs))
    for line in codegen_diffs[:40]:
        print("  DIFF", line)
    print()
    print("FMA CONTRACTION of `acc += w[i] - a*v[i]` (the reflector-update shape), per level:")
    print("  1 = the compiler fused it into an FMA, 0 = it did not")
    for (a, b, c) in CASES:
        argv = [hx(a), hx(b), hx(c)]
        row = {lvl: fn(argv).get("AXPY_CONTRACTED") for lvl, fn in runners.items()}
        print("  %s  O0=%s O3=%s JIT=%s" % (argv, row["O0"], row["O3"], row["JIT"]))
    report["contraction_note"] = (
        "contraction is level-dependent on this toolchain; it moves plain-float64 answers and "
        "double-double TAILS, never a double-double hi"
    )
    report["failures"] = failed
    report["codegen_diffs"] = codegen_diffs
    with open(os.path.join(HERE, "eft_codegen.json"), "w") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
    if failed:
        raise SystemExit(1)
    print("ALL_CHECKS_PASS")


if __name__ == "__main__":
    main()
