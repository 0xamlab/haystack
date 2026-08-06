"""test_exactnum_eft.mojo — known-value tests for the error-free transformations.

Hand-written. Registered in `tests/generate_mojo_tests.py` HANDWRITTEN_TESTS; the generator
destroys any unregistered `test_<module>.mojo` in this directory.

WHERE THE EXPECTED VALUES COME FROM, AND WHY IT MATTERS HERE MORE THAN USUAL
---------------------------------------------------------------------------
A compensated routine that has silently degraded to plain float64 still passes any test whose
expected value plain float64 already gets right. So a naive known-value suite over this module
would be vacuous. Two things fix that:

1. Every golden below is produced by `benchmarks/external_baselines/strd_lstsq/gen_goldens.py`
   from `fractions.Fraction` EXACT rational arithmetic — a float64 is a dyadic rational, so
   sums, products and quotients of them are exact — and, for the square root, from mpmath at
   80 and 120 digits with agreement asserted. No golden is computed in float64 and none is
   read back out of this implementation, so they are an independent expectation rather than a
   snapshot of current behaviour. They are stored as raw bit patterns because a decimal
   literal is only *probably* the value intended.

2. Several assertions are constructed so that PLAIN FLOAT64 PROVABLY FAILS. `two_product`'s
   error term for `(1+2^-52)^2` is exactly `2^-104` and the same expression without a fused
   multiply-add gives exactly zero. `Sum2` of `[2^53, 1, -1, 2^53] + 500 ones` is exactly
   `2^54 + 500` and sequential float64 addition returns `2^54`, losing all 500. Those are the
   anti-vacuity tests: a degraded implementation cannot pass them.

For a double-double result the golden is the two-term expansion of the exact value — `hi_g =
correctly-rounded(v)`, `lo_g = correctly-rounded(v - hi_g)`. The test asserts `hi` matches
`hi_g` bit-for-bit (which is the property "round once at the end" depends on) and that the
whole pair agrees with the exact value to the published double-double bound, measured with
`dd_sub` against the golden pair.
"""
from std.memory import bitcast

from numerical_stability import kahan_sum

from exactnum.eft import (
    DD,
    EFT_ERR_COMPILER_CONTRACTS_FMA,
    EFT_ERR_COMPILER_REASSOCIATES,
    EFT_ERR_INVALID_LENGTH,
    EFT_ERR_NEGATIVE_RADICAND,
    EFT_ERR_NON_FINITE_INPUT,
    EFT_ERR_NO_FUSED_MULTIPLY_ADD,
    EFT_MAX_TERMS,
    EFT_OK,
    dd_add,
    dd_div,
    dd_mul,
    dd_sqrt,
    dd_sub,
    _dot2,
    eft_dd_add,
    eft_dd_mul,
    eft_dot2,
    eft_fast_two_sum,
    eft_kahan_sum_f64,
    eft_selfcheck_code,
    eft_status_name,
    eft_sum2,
    eft_two_product,
    eft_two_product_dekker,
    eft_two_sum,
    _sum2,
)

# ── goldens: exact rational / mpmath, via gen_goldens.py. Not float64-derived. ─────
comptime TP_A_SQ_HI: Float64 = bitcast[DType.float64, 1](UInt64(0x3FF0000000000002))
comptime TP_A_SQ_LO: Float64 = bitcast[DType.float64, 1](UInt64(0x3970000000000000))
comptime TS_POW53_ONE_HI: Float64 = bitcast[DType.float64, 1](UInt64(0x4340000000000000))
comptime TS_POW53_ONE_LO: Float64 = bitcast[DType.float64, 1](UInt64(0x3FF0000000000000))
comptime TS_TENTH_FIFTH_HI: Float64 = bitcast[DType.float64, 1](UInt64(0x3FD3333333333334))
comptime TS_TENTH_FIFTH_LO: Float64 = bitcast[DType.float64, 1](UInt64(0xBC80000000000000))
comptime DDA_HI: Float64 = bitcast[DType.float64, 1](UInt64(0x3F9EB851EB851EB8))
comptime DDA_LO: Float64 = bitcast[DType.float64, 1](UInt64(0x3C3EB851EB851EB8))
comptime DDB_HI: Float64 = bitcast[DType.float64, 1](UInt64(0x3FCAE147AE147AE1))
comptime DDB_LO: Float64 = bitcast[DType.float64, 1](UInt64(0xBC6EB851EB851EB8))
comptime DD_ADD_AB_HI: Float64 = bitcast[DType.float64, 1](UInt64(0x3FCEB851EB851EB8))
comptime DD_ADD_AB_LO: Float64 = bitcast[DType.float64, 1](UInt64(0xBC6AE147AE147AE1))
comptime DD_SUB_AB_HI: Float64 = bitcast[DType.float64, 1](UInt64(0xBFC70A3D70A3D709))
comptime DD_SUB_AB_LO: Float64 = bitcast[DType.float64, 1](UInt64(0xBC6D70A3D70A3D71))
comptime DD_MUL_AB_HI: Float64 = bitcast[DType.float64, 1](UInt64(0x3F79CE075F6FD21F))
comptime DD_MUL_AB_LO: Float64 = bitcast[DType.float64, 1](UInt64(0x3C16A161E4F765FD))
comptime DD_DIV_AB_HI: Float64 = bitcast[DType.float64, 1](UInt64(0x3FC2492492492493))
comptime DD_DIV_AB_LO: Float64 = bitcast[DType.float64, 1](UInt64(0xBC4A1F58D0FAC685))
comptime DD_SQRT_A_HI: Float64 = bitcast[DType.float64, 1](UInt64(0x3FC62B9586AD0A22))
comptime DD_SQRT_A_LO: Float64 = bitcast[DType.float64, 1](UInt64(0x3C23BFFB4E172217))
comptime HARD_SUM_EXACT: Float64 = bitcast[DType.float64, 1](UInt64(0x435000000000007D))
comptime HARD_SUM_PLAIN_WRONG: Float64 = bitcast[DType.float64, 1](
    UInt64(0x4350000000000000)
)
comptime TWO_POW_M104: Float64 = bitcast[DType.float64, 1](UInt64(0x3970000000000000))

# A second dd operand pair, chosen by exhaustive search over simple decimals for the property
# that plain float64 `*` AND `/` on the leading words BOTH miss the correctly-rounded exact
# answer by one ulp: A = fl(0.1)*fl(0.1), B = fl(0.1)*fl(1.3), exact. Without a case like this
# the "compensation is load-bearing" assertion is vacuous — on the 0.1/0.3 pair above plain
# float64 happens to land on the correctly-rounded value and proves nothing.
comptime MF_A_HI: Float64 = bitcast[DType.float64, 1](UInt64(0x3F847AE147AE147C))
comptime MF_A_LO: Float64 = bitcast[DType.float64, 1](UInt64(0xBC2EB851EB851EB8))
comptime MF_B_HI: Float64 = bitcast[DType.float64, 1](UInt64(0x3FC0A3D70A3D70A4))
comptime MF_B_LO: Float64 = bitcast[DType.float64, 1](UInt64(0x3C60A3D70A3D70A4))
comptime MF_MUL_HI: Float64 = bitcast[DType.float64, 1](UInt64(0x3F554C985F06F695))
comptime MF_MUL_LO: Float64 = bitcast[DType.float64, 1](UInt64(0x3BFE9E1B089A0277))
comptime MF_DIV_HI: Float64 = bitcast[DType.float64, 1](UInt64(0x3FB3B13B13B13B14))
comptime MF_DIV_LO: Float64 = bitcast[DType.float64, 1](UInt64(0xBC483C977AB2BEDD))


def rel_agrees(got: DD, hi_g: Float64, lo_g: Float64, bits: Int) -> Bool:
    """`|got - (hi_g, lo_g)| <= 2^-bits * |hi_g|`, the double-double error measured in dd.

    The tolerance is built from the magnitude of THE QUANTITY BEING JUDGED — this golden's own
    `hi` — and from nothing else. Rule 4b: an aggregate over other values, or a `1 + |x|`
    floor, would let one number's units pay for another's error."""
    var d = dd_sub(got, DD(hi_g, lo_g))
    var scale = hi_g if hi_g >= 0.0 else -hi_g
    var tol = scale
    for _ in range(bits):
        tol = tol * 0.5
    var mag = d.hi if d.hi >= 0.0 else -d.hi
    return mag <= tol


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── the runtime arithmetic self-check ────────────────────────────────────
    if eft_selfcheck_code() == EFT_OK:
        passed += 1
        print("  ✅ fused multiply-add is real and addition is not reassociated on this build")
    else:
        failed += 1
        print(
            "  ❌ arithmetic selfcheck failed:",
            eft_status_name(eft_selfcheck_code()),
            "— every compensated result in this package would be a lie",
        )

    # ── status vocabulary: distinct, inside 800-809, unknown labelled ────────
    var codes = List[Int]()
    codes.append(EFT_OK)
    codes.append(EFT_ERR_NO_FUSED_MULTIPLY_ADD)
    codes.append(EFT_ERR_COMPILER_CONTRACTS_FMA)
    codes.append(EFT_ERR_COMPILER_REASSOCIATES)
    codes.append(EFT_ERR_INVALID_LENGTH)
    codes.append(EFT_ERR_NON_FINITE_INPUT)
    codes.append(EFT_ERR_NEGATIVE_RADICAND)
    var distinct = True
    var in_range = True
    for i in range(len(codes)):
        if codes[i] < 800 or codes[i] > 809:
            in_range = False
        for j in range(len(codes)):
            if i != j and eft_status_name(codes[i]) == eft_status_name(codes[j]):
                distinct = False
    if distinct and in_range and eft_status_name(7) == String("unknown_status"):
        passed += 1
        print("  ✅ eft statuses are distinct, inside its own 800-809 range (rule 4e)")
    else:
        failed += 1
        print("  ❌ eft status codes collide, escaped 800-809, or mislabel an unknown")

    # ── two_sum is EXACT, including where the sum itself is lossy ────────────
    var pow53: Float64 = 1.0
    for _ in range(53):
        pow53 = pow53 * 2.0
    var ts = eft_two_sum(pow53, 1.0)
    if ts.hi == TS_POW53_ONE_HI and ts.lo == TS_POW53_ONE_LO:
        passed += 1
        print("  ✅ two_sum(2^53, 1) recovers the bit float64 addition threw away")
    else:
        failed += 1
        print("  ❌ two_sum lost the error term at the 2^53 threshold")

    var ts2 = eft_two_sum(0.1, 0.2)
    var ts2r = eft_two_sum(0.2, 0.1)
    if (
        ts2.hi == TS_TENTH_FIFTH_HI
        and ts2.lo == TS_TENTH_FIFTH_LO
        and ts2r.hi == ts2.hi
        and ts2r.lo == ts2.lo
    ):
        passed += 1
        print("  ✅ two_sum(0.1, 0.2) matches exact rational arithmetic, both operand orders")
    else:
        failed += 1
        print("  ❌ two_sum disagreed with exact rational arithmetic or with itself reordered")

    var fts = eft_fast_two_sum(pow53, 1.0)
    if fts.hi == TS_POW53_ONE_HI and fts.lo == TS_POW53_ONE_LO:
        passed += 1
        print("  ✅ fast_two_sum agrees with two_sum when its |a| >= |b| precondition holds")
    else:
        failed += 1
        print("  ❌ fast_two_sum wrong on a valid ordering")

    # ── two_product: the anti-vacuity case. Plain float64 returns zero here. ─
    var eps: Float64 = 1.0
    for _ in range(52):
        eps = eps * 0.5
    var a = 1.0 + eps
    var tp = eft_two_product(a, a)
    var tpd = eft_two_product_dekker(a, a)
    var p = a * a
    var naive_tail = (a * a) - p
    if (
        tp.hi == TP_A_SQ_HI
        and tp.lo == TP_A_SQ_LO
        and tp.lo == TWO_POW_M104
        and naive_tail == 0.0
    ):
        passed += 1
        print(
            "  ✅ ANTI-VACUITY: two_product((1+2^-52)^2) tail is exactly 2^-104 while the",
            "same expression without an fma gives 0 — a degraded route cannot pass this",
        )
    else:
        failed += 1
        print("  ❌ two_product's tail is not the exact product residue (fma is not fused?)")

    if tpd.hi == tp.hi and tpd.lo == tp.lo:
        passed += 1
        print("  ✅ the 17-flop Dekker-splitting fallback agrees with the fma form bit-for-bit")
    else:
        failed += 1
        print("  ❌ Dekker splitting and the fma form disagree — one of them is wrong")

    # ── double-double arithmetic against exact rationals ─────────────────────
    var A = eft_two_product(0.1, 0.3)
    var B = eft_two_product(0.3, 0.7)
    if A.hi == DDA_HI and A.lo == DDA_LO and B.hi == DDB_HI and B.lo == DDB_LO:
        passed += 1
        print("  ✅ the two dd operands are the EXACT products, matching Fraction")
    else:
        failed += 1
        print("  ❌ two_product did not produce the exact product of the test operands")

    var ok_ops = True
    var r_add = dd_add(A, B)
    if not (r_add.hi == DD_ADD_AB_HI and rel_agrees(r_add, DD_ADD_AB_HI, DD_ADD_AB_LO, 100)):
        ok_ops = False
    var r_sub = dd_sub(A, B)
    if not (r_sub.hi == DD_SUB_AB_HI and rel_agrees(r_sub, DD_SUB_AB_HI, DD_SUB_AB_LO, 100)):
        ok_ops = False
    var r_mul = dd_mul(A, B)
    if not (r_mul.hi == DD_MUL_AB_HI and rel_agrees(r_mul, DD_MUL_AB_HI, DD_MUL_AB_LO, 100)):
        ok_ops = False
    var r_div = dd_div(A, B)
    if not (r_div.hi == DD_DIV_AB_HI and rel_agrees(r_div, DD_DIV_AB_HI, DD_DIV_AB_LO, 98)):
        ok_ops = False
    var r_sqrt = dd_sqrt(A)
    if not (
        r_sqrt.hi == DD_SQRT_A_HI and rel_agrees(r_sqrt, DD_SQRT_A_HI, DD_SQRT_A_LO, 100)
    ):
        ok_ops = False
    if ok_ops:
        passed += 1
        print(
            "  ✅ dd_add/sub/mul/div/sqrt each round to the CORRECTLY-ROUNDED float64 of the",
            "exact value and the pair agrees with it to 2^-98 or better",
        )
    else:
        failed += 1
        print("  ❌ a dd operation missed the correctly-rounded result or its error bound")

    # ── ANTI-VACUITY for dd_mul / dd_div: a pair where plain float64 provably misses ──
    # On the 0.1/0.3 operands above, plain float64 `*` happens to land on the correctly-rounded
    # value, so that case alone would prove nothing about the compensation. This pair was found
    # by exhaustive search for the property that both `*` and `/` on the leading words are off
    # by one ulp from the correctly-rounded exact result.
    var MA = eft_two_product(0.1, 0.1)
    var MB = eft_two_product(0.1, 1.3)
    var mm = dd_mul(MA, MB)
    var md = dd_div(MA, MB)
    var plain_m = MA.hi * MB.hi
    var plain_d = MA.hi / MB.hi
    if (
        MA.hi == MF_A_HI
        and MA.lo == MF_A_LO
        and MB.hi == MF_B_HI
        and MB.lo == MF_B_LO
        and mm.hi == MF_MUL_HI
        and md.hi == MF_DIV_HI
        and rel_agrees(mm, MF_MUL_HI, MF_MUL_LO, 100)
        and rel_agrees(md, MF_DIV_HI, MF_DIV_LO, 98)
        and plain_m != MF_MUL_HI
        and plain_d != MF_DIV_HI
    ):
        passed += 1
        print(
            "  ✅ ANTI-VACUITY: on operands where plain float64 * and / are BOTH one ulp from",
            "the correctly-rounded exact answer, dd_mul and dd_div land on it",
        )
    else:
        failed += 1
        print("  ❌ dd_mul/dd_div did not beat plain float64 on a case float64 provably fails")

    # a negative radicand has no real square root: NaN pair, never a plausible number
    var neg = DD(-1.0, 0.0)
    var rs = dd_sqrt(neg)
    if not (rs.hi == rs.hi):  # NaN != NaN
        passed += 1
        print("  ✅ dd_sqrt of a negative radicand is NaN, not a plausible-looking number")
    else:
        failed += 1
        print("  ❌ dd_sqrt invented a root for a negative radicand")

    if dd_sqrt(DD(0.0, 0.0)).hi == 0.0:
        passed += 1
        print("  ✅ dd_sqrt(0) is 0, which is a real answer and must not be absent")
    else:
        failed += 1
        print("  ❌ dd_sqrt(0) is not 0")

    # ── Sum2: the sequence plain float64 provably cannot sum ─────────────────
    var hard = List[Float64]()
    hard.append(pow53)
    hard.append(1.0)
    hard.append(-1.0)
    hard.append(pow53)
    for _ in range(500):
        hard.append(1.0)
    var plain: Float64 = 0.0
    for i in range(len(hard)):
        plain += hard[i]
    var s2 = _sum2(hard, len(hard))
    if (
        plain == HARD_SUM_PLAIN_WRONG
        and s2.hi == HARD_SUM_EXACT
        and s2.lo == 0.0
        and plain != s2.hi
    ):
        passed += 1
        print(
            "  ✅ ANTI-VACUITY: Sum2 returns exactly 2^54 + 500 where sequential float64",
            "returns 2^54 and loses all 500 ones",
        )
    else:
        failed += 1
        print("  ❌ Sum2 did not recover the 500 lost ones, or float64 did not lose them")

    # the frozen kahan_sum recovers it too, and eft_kahan_sum_f64 forwards to it (rule 3)
    if eft_kahan_sum_f64(hard) == kahan_sum(hard) and kahan_sum(hard) == HARD_SUM_EXACT:
        passed += 1
        print("  ✅ eft_kahan_sum_f64 is the frozen numerical_stability.kahan_sum, forwarded")
    else:
        failed += 1
        print("  ❌ eft_kahan_sum_f64 is not the frozen kernel, or the frozen kernel changed")

    # ── Dot2: designed so plain float64 returns 0 and the exact answer is 2 ──
    var dx = List[Float64]()
    var dy = List[Float64]()
    dx.append(pow53)
    dy.append(1.0)
    dx.append(1.0)
    dy.append(1.0)
    dx.append(1.0)
    dy.append(1.0)
    dx.append(-pow53)
    dy.append(1.0)
    var plain_dot: Float64 = 0.0
    for i in range(len(dx)):
        plain_dot += dx[i] * dy[i]
    var d2 = _dot2(dx, dy, len(dx))
    if plain_dot == 0.0 and d2.hi == 2.0 and d2.lo == 0.0:
        passed += 1
        print("  ✅ ANTI-VACUITY: Dot2 returns exactly 2 where the plain float64 dot returns 0")
    else:
        failed += 1
        print("  ❌ Dot2 did not recover the exact dot product of the designed case")

    # ── rule 1: a count past the end of the buffer must be REFUSED, not read ─
    # The generated A-Z suite calls every contract function with 5-element lists and Int 5,
    # so an unguarded count is not hypothetical. A read past the end is an uncatchable abort.
    var lf5 = List[Float64]()
    for _ in range(5):
        lf5.append(1.0)
    var g_ok = eft_dot2(lf5, lf5, 5)
    var g_long = eft_dot2(lf5, lf5, 25)
    var g_neg = eft_dot2(lf5, lf5, -1)
    var g_big = eft_dot2(lf5, lf5, EFT_MAX_TERMS + 1)
    if (
        g_ok.status == EFT_OK
        and g_ok.hi == 5.0
        and g_long.status == EFT_ERR_INVALID_LENGTH
        and g_neg.status == EFT_ERR_INVALID_LENGTH
        and g_big.status == EFT_ERR_INVALID_LENGTH
        and g_long.terms == 0
    ):
        passed += 1
        print("  ✅ a count longer than the buffer, negative, or past the ceiling is refused")
    else:
        failed += 1
        print("  ❌ a dimension argument was trusted against a shorter buffer (rule 1)")

    var nanl = List[Float64]()
    nanl.append(1.0)
    nanl.append(0.0 / 0.0)
    nanl.append(1.0)
    nanl.append(1.0)
    nanl.append(1.0)
    var infl = List[Float64]()
    for _ in range(5):
        infl.append(1.0)
    infl[3] = 1.0 / 0.0
    if (
        eft_dot2(nanl, lf5, 5).status == EFT_ERR_NON_FINITE_INPUT
        and eft_sum2(infl, 5).status == EFT_ERR_NON_FINITE_INPUT
        and eft_dot2(nanl, lf5, 5).hi == 0.0
    ):
        passed += 1
        print("  ✅ a NaN or infinite element is refused before any tolerance is built from it")
    else:
        failed += 1
        print("  ❌ a non-finite element travelled into the reduction (rule 4d)")

    # ── the flat public wrappers agree with the internal ones ────────────────
    var w1 = eft_dd_add(A.hi, A.lo, B.hi, B.lo)
    var w2 = eft_dd_mul(A.hi, A.lo, B.hi, B.lo)
    if w1.hi == r_add.hi and w1.lo == r_add.lo and w2.hi == r_mul.hi and w2.lo == r_mul.lo:
        passed += 1
        print("  ✅ the contract-shaped wrappers are the same arithmetic, not a second copy")
    else:
        failed += 1
        print("  ❌ a public wrapper diverged from the internal operation it wraps (rule 3)")

    print("  [exactnum.eft] Passed:", passed, "Failed:", failed)
