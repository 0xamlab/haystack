"""Emit the golden constants for mojo/tests/libs/test_exactnum_eft.mojo.

Every value printed here is derived with `fractions.Fraction` exact rational arithmetic, or
with mpmath at two precisions for the square root. Nothing is computed in float64 and nothing
is read back out of the Mojo implementation, so the goldens are an INDEPENDENT expectation
rather than a snapshot of current behaviour.

For a double-double result the golden is the two-term expansion of the exact value:
`hi_g = float(v)` (correctly rounded) and `lo_g = float(v - Fraction(hi_g))`. The test then
asserts the implementation's `hi` equals `hi_g` exactly and that `|result - (hi_g, lo_g)|` is
below the published double-double bound, which is checkable inside Mojo with `dd_sub`.

Run: /tmp/bb/bin/python -P gen_goldens.py
"""

from __future__ import annotations

import struct
from fractions import Fraction


def hx(v: float) -> str:
    return "0x%016X" % struct.unpack("<Q", struct.pack("<d", v))[0]


def expand(v: Fraction) -> tuple[float, float]:
    hi = float(v)
    lo = float(v - Fraction(hi))
    return hi, lo


def emit(name: str, v: Fraction) -> None:
    hi, lo = expand(v)
    print("comptime %s_HI: Float64 = bitcast[DType.float64, 1](UInt64(%s))" % (name, hx(hi)))
    print("comptime %s_LO: Float64 = bitcast[DType.float64, 1](UInt64(%s))" % (name, hx(lo)))
    print("#   %s  ~= %s" % (name, float(v)))


def main() -> None:
    a = 1.0 + 2.0**-52
    print("# a = 1 + 2^-52 = %r" % a)
    emit("TP_A_SQ", Fraction(a) * Fraction(a))
    emit("TS_POW53_ONE", Fraction(2) ** 53 + 1)
    emit("TS_TENTH_FIFTH", Fraction(0.1) + Fraction(0.2))

    A = Fraction(0.1) * Fraction(0.3)
    B = Fraction(0.3) * Fraction(0.7)
    print("# A = fl(0.1)*fl(0.3) exactly, B = fl(0.3)*fl(0.7) exactly")
    emit("DDA", A)
    emit("DDB", B)
    emit("DD_ADD_AB", A + B)
    emit("DD_SUB_AB", A - B)
    emit("DD_MUL_AB", A * B)
    emit("DD_DIV_AB", A / B)

    from mpmath import mp, mpf, sqrt as mpsqrt

    roots = []
    for dps in (80, 120):
        mp.dps = dps
        roots.append(mpsqrt(mpf(A.numerator) / mpf(A.denominator)))
    mp.dps = 120
    assert abs(roots[0] - roots[1]) <= mpf(10) ** -70 * abs(roots[1]), "witnesses disagree"
    r = roots[1]
    hi = float(r)
    mp.dps = 120
    lo = float(r - mpf(hi))
    print("# sqrt(A) from mpmath at 80 and 120 dps, agreement asserted")
    print("comptime DD_SQRT_A_HI: Float64 = bitcast[DType.float64, 1](UInt64(%s))" % hx(hi))
    print("comptime DD_SQRT_A_LO: Float64 = bitcast[DType.float64, 1](UInt64(%s))" % hx(lo))

    print("# the hard summation: 2^54 + 500 is exactly representable (spacing 4 at 2^54)")
    v = Fraction(2) ** 54 + 500
    assert Fraction(float(v)) == v
    print("comptime HARD_SUM_EXACT: Float64 = bitcast[DType.float64, 1](UInt64(%s))" % hx(float(v)))
    print("# plain sequential float64 gives 2^54 and loses all 500")
    print(
        "comptime HARD_SUM_PLAIN_WRONG: Float64 = bitcast[DType.float64, 1](UInt64(%s))"
        % hx(float(Fraction(2) ** 54))
    )

    # Wampler1: x = 0..20 integers, y = sum_{k=0}^{5} x^k, exact solution all ones. Every
    # design-matrix entry and every response is an exact integer inside float64's 2^53 grid,
    # so the exact least-squares solution IS the vector of ones and any deviation is pure
    # working-precision loss.
    xs = list(range(21))
    ys = []
    for x in xs:
        acc = 0
        for k in range(6):
            acc += x**k
        ys.append(acc)
    assert max(ys) < 2**53
    print("# Wampler1-shape check data: y_i = sum_{k=0..5} x_i^k, x = 0..20, exact beta = ones")
    print("#   max y = %d (inside 2^53, so the whole system is exact in float64)" % max(ys))


if __name__ == "__main__":
    main()
