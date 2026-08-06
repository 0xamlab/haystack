"""
measure_exactnum_eft_codegen.mojo — every EFT primitive, on opaque runtime inputs.

Named `measure_*` rather than `bench_*`: `tests/benchmark_mojo_vs_python.py` writes
`bench_{module}.mojo` in this directory from a generator and would destroy a hand-written
file under that name.

WHY THIS EXISTS AND WHAT IT IS FOR
----------------------------------
A double-double routine that has silently degraded to plain float64 still passes any test
whose expected value plain float64 already gets right. So the arithmetic has to be checked
two ways at once:

  * against an INDEPENDENT exact source — `benchmarks/external_baselines/strd_lstsq/
    eft_codegen_check.py` computes every expected value below with `fractions.Fraction`
    exact rational arithmetic (and mpmath for the square root), never with float64
  * across CODEGEN PATHS — the same binary at `--optimization-level 0`, at `3` (what
    `scripts/build_mojo_binary.sh` ships) and under the JIT, because a reassociation or an
    unwanted contraction in any one of them would destroy the compensation invisibly

Every operand arrives as a 16-digit hex IEEE-754 bit pattern on argv, so the compiler sees
opaque runtime values and cannot constant-fold the arithmetic under test. That matters: a
folded expression is evaluated by the compiler's own exact model and comes out right no
matter what the generated code would have done, which would turn the whole check into a
tautology.

Each compensated primitive is printed next to its plain-float64 counterpart, and the checker
requires the two to DIFFER on the designated hard cases. That is the anti-vacuity condition:
if `two_product`'s error term were zero, or `Sum2` collapsed to sequential addition, the
pair would agree and the check fails.

    cd mojo_env
    pixi run mojo build -I../mojo/engine --optimization-level 3 \\
        ../benchmarks/mojo_benchmarks/measure_exactnum_eft_codegen.mojo -o /tmp/eft_O3
    /tmp/eft_O3 <a_hex> <b_hex> <c_hex>
"""
from sys import argv

from std.memory import bitcast

from exactnum.eft import (
    DD,
    dd_add,
    dd_div,
    dd_mul,
    dd_sqrt,
    dd_sub,
    _dot2,
    eft_fast_two_sum,
    eft_selfcheck_code,
    eft_two_product,
    eft_two_product_dekker,
    eft_two_sum,
    eft_kahan_sum_f64,
    _sum2,
)


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
        var nib = Int((u >> ((15 - i) * 4)) & 0xF)
        out += chr(nib + 48) if nib < 10 else chr(nib + 87)
    return out


def show(key: String, v: Float64):
    print(key, f64_to_hex(v))


def show_dd(key: String, v: DD):
    print(key + "_HI", f64_to_hex(v.hi))
    print(key + "_LO", f64_to_hex(v.lo))


def main() raises:
    var args = argv()
    if len(args) < 4:
        print("usage: measure_exactnum_eft_codegen <a_hex> <b_hex> <c_hex>")
        return
    var a = hex_to_f64(args[1])
    var b = hex_to_f64(args[2])
    var c = hex_to_f64(args[3])
    show(String("IN_A"), a)
    show(String("IN_B"), b)
    show(String("IN_C"), c)
    print("SELFCHECK", eft_selfcheck_code())

    # ── two_sum: exact for any finite pair, and NOT symmetric in the error term's
    # computation path even though the value is. Both orders are printed so a reordering
    # optimisation would show up as a difference between them where none is allowed.
    show_dd(String("TWO_SUM_AB"), eft_two_sum(a, b))
    show_dd(String("TWO_SUM_BA"), eft_two_sum(b, a))
    show(String("PLAIN_SUM_AB"), a + b)

    # fast_two_sum is only valid when |a| >= |b|; the checker knows which of the two orders
    # satisfies that and only validates the valid one.
    show_dd(String("FAST_TWO_SUM_AB"), eft_fast_two_sum(a, b))
    show_dd(String("FAST_TWO_SUM_BA"), eft_fast_two_sum(b, a))

    # ── two_product three ways. FMA and Dekker splitting must agree bit-for-bit; the naive
    # form must NOT, or there is no fused multiply-add and every product tail is a lie.
    var tp = eft_two_product(a, b)
    var tpd = eft_two_product_dekker(a, b)
    show_dd(String("TP_FMA_AB"), tp)
    show_dd(String("TP_DEKKER_AB"), tpd)
    var p_ab = a * b
    show(String("TP_NAIVE_LO_AB"), (a * b) - p_ab)
    show(String("PLAIN_PROD_AB"), p_ab)
    show(String("FMA_A_B_C"), a.fma(b, c))
    show(String("MUL_ADD_A_B_C"), a * b + c)

    # ── double-double arithmetic on two EXACT double-double operands, so the expected value
    # is an exact rational the checker can compute without any floating point at all.
    var A = eft_two_product(a, b)
    var B = eft_two_product(b, c)
    show_dd(String("DD_A"), A)
    show_dd(String("DD_B"), B)
    show_dd(String("DD_ADD"), dd_add(A, B))
    show_dd(String("DD_SUB"), dd_sub(A, B))
    show_dd(String("DD_MUL"), dd_mul(A, B))
    show_dd(String("DD_DIV"), dd_div(A, B))
    var absA = A if A.hi >= 0.0 else DD(-A.hi, -A.lo)
    show_dd(String("DD_SQRT_ABS_A"), dd_sqrt(absA))
    # the float64 counterparts, which the checker requires to be WORSE
    show(String("PLAIN_ADD"), A.hi + B.hi)
    show(String("PLAIN_MUL"), A.hi * B.hi)
    show(String("PLAIN_DIV"), A.hi / B.hi)

    # ── Dot2 and Sum2 on a sequence built to make plain float64 fail outright.
    # [2^53, 1, -1, 2^53] followed by 500 ones sums exactly to 2^54 + 500; sequential float64
    # addition returns 2^54 and loses all 500 of them.
    var pow53: Float64 = 1.0
    for _ in range(53):
        pow53 = pow53 * 2.0
    var hard = List[Float64]()
    hard.append(pow53)
    hard.append(1.0)
    hard.append(-1.0)
    hard.append(pow53)
    for _ in range(500):
        hard.append(1.0)
    var plain_seq: Float64 = 0.0
    for i in range(len(hard)):
        plain_seq += hard[i]
    show(String("HARD_PLAIN_SUM"), plain_seq)
    show(String("HARD_KAHAN_FROZEN"), eft_kahan_sum_f64(hard))
    show_dd(String("HARD_SUM2"), _sum2(hard, len(hard)))

    # A dot product whose terms cancel: x = [a, b, c, -a, -b, -c] against y built from the
    # same values, so the exact answer is a small residue of large products.
    var xs = List[Float64]()
    var ys = List[Float64]()
    xs.append(a)
    ys.append(b)
    xs.append(b)
    ys.append(c)
    xs.append(c)
    ys.append(a)
    xs.append(-a)
    ys.append(b)
    xs.append(-b)
    ys.append(c)
    xs.append(-c)
    ys.append(a)
    xs.append(a * b)
    ys.append(1.0)
    var plain_dot: Float64 = 0.0
    for i in range(len(xs)):
        plain_dot += xs[i] * ys[i]
    show(String("DOT_PLAIN"), plain_dot)
    show_dd(String("DOT2"), _dot2(xs, ys, len(xs)))

    # A dot product DESIGNED so plain float64 provably fails, independent of the operands:
    # x = [2^53, 1, 1, -2^53], y = [1, 1, 1, 1]. The exact answer is 2, sequential float64
    # addition returns 0 because 2^53 + 1 rounds back to 2^53 twice over. This is the
    # anti-vacuity case for Dot2 — a route that had degraded to plain float64 returns 0 here
    # and cannot be mistaken for a working one.
    var hx2 = List[Float64]()
    var hy2 = List[Float64]()
    hx2.append(pow53)
    hy2.append(1.0)
    hx2.append(1.0)
    hy2.append(1.0)
    hx2.append(1.0)
    hy2.append(1.0)
    hx2.append(-pow53)
    hy2.append(1.0)
    var hard_plain_dot: Float64 = 0.0
    for i in range(len(hx2)):
        hard_plain_dot += hx2[i] * hy2[i]
    show(String("HARD_DOT_PLAIN"), hard_plain_dot)
    show_dd(String("HARD_DOT2"), _dot2(hx2, hy2, len(hx2)))

    # ── DOES THE COMPILER CONTRACT `c - a*b` INTO AN FMA? Measured, not assumed.
    # This is the one codegen question that decides whether the float64 CONTROL arm is
    # reproducible, and the answer on this toolchain is level-dependent. `acc += w[i] - a*v[i]`
    # is the exact shape of a Householder reflector update, so this is not a synthetic case.
    # If AXPY_PLAIN == AXPY_FMA the compiler fused it; if they differ it did not.
    # Error-free transformations are unaffected either way: `two_sum` contains no
    # multiplication at all, and `two_product` names its FMA explicitly.
    var vv = List[Float64]()
    var ww = List[Float64]()
    for i in range(8):
        vv.append(a + Float64(i))
        ww.append(b - Float64(i) * 0.5)
    var axpy_plain: Float64 = 0.0
    for i in range(8):
        axpy_plain += ww[i] - c * vv[i]
    var axpy_fma: Float64 = 0.0
    for i in range(8):
        axpy_fma += (-c).fma(vv[i], ww[i])
    show(String("AXPY_PLAIN"), axpy_plain)
    show(String("AXPY_FMA"), axpy_fma)
    print("AXPY_CONTRACTED", "1" if axpy_plain == axpy_fma else "0")
    print("DONE")
