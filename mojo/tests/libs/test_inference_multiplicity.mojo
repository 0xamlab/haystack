"""test_inference_multiplicity.mojo — known-value tests for the three corrections.

Hand-written. The whole family is exact arithmetic on p-values, so almost every expected value
here is computed on paper and asserted BITWISE rather than with a tolerance — a tolerance would
hide a wrong multiplier, and the multipliers are the entire content of these procedures.

The canonical family is `p = [0.01, 0.02, 0.03, 0.04, 0.05]` at `alpha = 0.05`, already
sorted so the sorted-order arithmetic can be read straight off:

    Bonferroni   5p              = [0.05, 0.10, 0.15, 0.20, 0.25]   -> 1 rejection
    Holm         max_{j<=i} (6-j) p_(j)
                 = [5(0.01), max(.05, 4(0.02)), max(.08, 3(0.03)),
                    max(.09, 2(0.04)), max(.09, 1(0.05))]
                 = [0.05, 0.08, 0.09, 0.09, 0.09]                   -> 1 rejection
    BH           min_{j>=i} 5 p_(j) / j — every term is exactly 0.05
                 = [0.05, 0.05, 0.05, 0.05, 0.05]                   -> 5 rejections

One family, one rejection under family-wise control and five under false-discovery control:
that difference IS why `Correction.method` travels with the numbers, and this suite asserts
both counts so a change in either procedure cannot pass as the other.

Three structural properties are asserted as well, and each is provable rather than empirical:

1. *Bonferroni and Holm agree BITWISE on the smallest p-value.* Both give `n * p_min`. Not
   "approximately": the same product of the same two doubles.
2. *BH_(i) <= Holm_(i) <= Bonferroni_(i) at every position.* From
   `n p_(i) / (i+1) <= (n - i) p_(i) <= n p_(i)`, which holds for every `1 <= i+1 <= n`.
3. *Ties adjust identically.* Two equal raw p-values must receive equal adjusted values under
   all three procedures, which follows from the running max / running min but only if the
   ORDER used is total — so the tie-break on the original position is load-bearing and is
   asserted with a family containing three copies of one value.

The nominal-rate check is the one place a simulation is the right instrument: 200 independent
families of 20 uniform p-values, all null, drawn from `determinism.counter_rng.rng_uniform`
under a FIXED seed so the number below is reproducible. Under all nulls BH's false-discovery
rate is exactly its probability of any rejection, which must sit near `alpha = 0.05`; the
measured value is 0.065, and 200 replications give a standard error of 0.0154, so 0.065 is one
standard error above nominal. The assertion is `<= 0.12` (four standard errors) because the
claim being tested is "approximately the nominal rate", and a tighter bound would be asserting
the Monte-Carlo noise rather than the procedure.
"""
from determinism.counter_rng import rng_uniform
from inference.core import (
    INF_ERR_ALPHA_RANGE,
    INF_ERR_DIMENSION_TOO_LARGE,
    INF_ERR_EMPTY,
    INF_ERR_PVALUE_RANGE,
    INF_ERR_SHAPE,
    INF_OK,
    MAX_TESTS,
    inference_absent,
)
from inference.multiplicity import (
    METHOD_BH,
    METHOD_BONFERRONI,
    METHOD_HOLM,
    MULT_P_ABSENT,
    benjamini_hochberg_flat,
    bonferroni_flat,
    correction_agreement_flat,
    holm_flat,
    multiplicity_input_defect,
)


fn _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _rejected(c: Correction) -> Bool:
    """A refusal carries no adjusted values and no rejections at all."""
    return (
        c.status != INF_OK
        and len(c.adjusted) == 0
        and len(c.rejected) == 0
        and c.n_rejected == 0
        and c.max_rejected_p == MULT_P_ABSENT
    )


from inference.multiplicity import Correction


fn main():
    var passed: Int = 0
    var failed: Int = 0

    var family = _floats(0.01, 0.02, 0.03, 0.04, 0.05)
    var bonf = bonferroni_flat(family, 5, 0.05)
    var holm = holm_flat(family, 5, 0.05)
    var bh = benjamini_hochberg_flat(family, 5, 0.05)

    # ── 1. Bonferroni, bitwise ─────────────────────────────────────────────────
    if (
        bonf.status == INF_OK
        and bonf.method == METHOD_BONFERRONI
        and bonf.n_tests == 5
        and len(bonf.adjusted) == 5
        # The right-hand side reads the p-value back out of the LIST so the multiply happens
        # at run time. Mojo folds a literal product (`5.0 * 0.01`) in higher precision than a
        # Float64 multiply, so a literal on the right is a different number for some pairs —
        # `3.0 * 0.2` folds to 0.5999999999999999778 while the double product is
        # 0.6000000000000000888. Reading the operand from the list removes that difference.
        and bonf.adjusted[0] == Float64(5) * family[0]
        and bonf.adjusted[1] == Float64(5) * family[1]
        and bonf.adjusted[2] == Float64(5) * family[2]
        and bonf.adjusted[3] == Float64(5) * family[3]
        and bonf.adjusted[4] == Float64(5) * family[4]
        and bonf.n_rejected == 1
        and bonf.rejected[0]
        and not bonf.rejected[1]
        and bonf.min_p == 0.01
        and bonf.max_rejected_p == 0.01
    ):
        passed += 1
        print("  ✅ Bonferroni is 5p bitwise, rejects exactly the 0.01, and names its method")
    else:
        failed += 1
        print("  ❌ Bonferroni wrong:", bonf.status, bonf.n_rejected, bonf.adjusted[0])

    # ── 2. Holm, hand-computed running maximum ─────────────────────────────────
    if (
        holm.status == INF_OK
        and holm.method == METHOD_HOLM
        and holm.adjusted[0] == Float64(5) * family[0]
        and holm.adjusted[1] == Float64(4) * family[1]
        and holm.adjusted[2] == Float64(3) * family[2]
        # positions 3 and 4 are the running MAXIMUM (2*0.04 = 0.08 and 1*0.05 = 0.05 are both
        # below 3*0.03 = 0.09), which is the step that makes the sequence monotone
        and holm.adjusted[3] == Float64(3) * family[2]
        and holm.adjusted[4] == Float64(3) * family[2]
        and holm.n_rejected == 1
        and holm.max_rejected_p == 0.01
    ):
        passed += 1
        print("  ✅ Holm is [.05, .08, .09, .09, .09] — the running max is doing its job")
    else:
        failed += 1
        print("  ❌ Holm wrong:", holm.adjusted[1], holm.adjusted[3], holm.n_rejected)

    # ── 3. BH, and the same family rejecting five instead of one ───────────────
    var bh_all_at_alpha = True
    for i in range(5):
        if bh.adjusted[i] > 0.05:
            bh_all_at_alpha = False
        if not bh.rejected[i]:
            bh_all_at_alpha = False
    if (
        bh.status == INF_OK
        and bh.method == METHOD_BH
        and bh_all_at_alpha
        and bh.n_rejected == 5
        and bh.max_rejected_p == 0.05
        and bh.adjusted[4] == Float64(5) * family[4] / Float64(5)
    ):
        passed += 1
        print("  ✅ BH rejects all five where Holm rejected one — the guarantee differs")
    else:
        failed += 1
        print("  ❌ BH wrong:", bh.n_rejected, bh.adjusted[0], bh.adjusted[4])

    # ── 4. the provable orderings, at every position ───────────────────────────
    var order_ok = True
    for i in range(5):
        if bh.adjusted[i] > holm.adjusted[i]:
            order_ok = False
        if holm.adjusted[i] > bonf.adjusted[i]:
            order_ok = False
    if (
        order_ok
        # BITWISE at the smallest p-value: both are n * p_min, the same product.
        and bonf.adjusted[0] == holm.adjusted[0]
        and bonf.n_rejected <= holm.n_rejected
        and holm.n_rejected <= bh.n_rejected
    ):
        passed += 1
        print("  ✅ BH <= Holm <= Bonferroni everywhere, and the two agree bitwise at p_min")
    else:
        failed += 1
        print("  ❌ ordering violated")

    # ── 5. the exported self-consistency report ────────────────────────────────
    var agreement = correction_agreement_flat(family, 5, 0.05)
    if (
        agreement.status == INF_OK
        and agreement.n_tests == 5
        and agreement.n_rejected_bonferroni == 1
        and agreement.n_rejected_holm == 1
        and agreement.n_rejected_bh == 5
        and agreement.smallest_p_identical
        and agreement.monotone_bh_le_holm_le_bonferroni
        and agreement.power_ordering_holds
    ):
        passed += 1
        print("  ✅ the package's own agreement report confirms all three coherence claims")
    else:
        failed += 1
        print("  ❌ agreement report wrong:", agreement.status, agreement.n_rejected_bh)

    # ── 6. an UNSORTED family, so the permutation round-trip is exercised ──────
    # Same five values shuffled: adjusted values must come back in the CALLER's order.
    var shuffled = _floats(0.04, 0.01, 0.05, 0.02, 0.03)
    var h2 = holm_flat(shuffled, 5, 0.05)
    var bh2 = benjamini_hochberg_flat(shuffled, 5, 0.05)
    if (
        h2.status == INF_OK
        and h2.adjusted[1] == Float64(5) * shuffled[1]
        and h2.adjusted[3] == Float64(4) * shuffled[3]
        and h2.adjusted[4] == Float64(3) * shuffled[4]
        and h2.adjusted[0] == Float64(3) * shuffled[4]
        and h2.adjusted[2] == Float64(3) * shuffled[4]
        and h2.n_rejected == 1
        and h2.rejected[1]
        and bh2.n_rejected == 5
    ):
        passed += 1
        print("  ✅ an unsorted family adjusts to the same values, returned in caller order")
    else:
        failed += 1
        print("  ❌ unsorted family wrong:", h2.adjusted[0], h2.adjusted[1])

    # ── 7. ties adjust identically under all three ─────────────────────────────
    # Three copies of 0.02 plus two others. The running max / running min give tied raw
    # p-values equal adjusted values ONLY if the sort order is total, which is why the
    # tie-break on the original position matters.
    var tied = _floats(0.02, 0.01, 0.02, 0.02, 0.30)
    var tb = bonferroni_flat(tied, 5, 0.05)
    var th = holm_flat(tied, 5, 0.05)
    var tbh = benjamini_hochberg_flat(tied, 5, 0.05)
    if (
        tb.adjusted[0] == tb.adjusted[2]
        and tb.adjusted[2] == tb.adjusted[3]
        and th.adjusted[0] == th.adjusted[2]
        and th.adjusted[2] == th.adjusted[3]
        and tbh.adjusted[0] == tbh.adjusted[2]
        and tbh.adjusted[2] == tbh.adjusted[3]
        # Holm on the tie: 5(0.01) = 0.05, then 4(0.02) = 0.08 which the running max holds
        # for all three copies.
        and th.adjusted[1] == Float64(5) * tied[1]
        and th.adjusted[0] == Float64(4) * tied[0]
    ):
        passed += 1
        print("  ✅ three tied p-values receive three identical adjusted values, all methods")
    else:
        failed += 1
        print("  ❌ ties adjusted differently:", th.adjusted[0], th.adjusted[2], th.adjusted[3])

    # ── 8. clamping at 1, which is where a probability stops ──────────────────
    # 3 * 0.5 and 3 * 0.9 both exceed 1 and clamp; 3 * 0.2 does not and must survive exactly
    # (it is 0.6000000000000001 in doubles, which is what "bitwise" means here).
    var big = _floats(0.2, 0.5, 0.9)
    var cb = bonferroni_flat(big, 3, 0.05)
    var ch = holm_flat(big, 3, 0.05)
    if (
        cb.adjusted[1] == 1.0
        and cb.adjusted[2] == 1.0
        and cb.adjusted[0] == Float64(3) * big[0]
        and ch.adjusted[2] == 1.0
        and cb.n_rejected == 0
        and cb.max_rejected_p == MULT_P_ABSENT
        and ch.n_rejected == 0
        and ch.max_rejected_p == MULT_P_ABSENT
    ):
        passed += 1
        print("  ✅ adjusted values clamp at 1.0 and 'nothing rejected' is -1.0, not 0.0")
    else:
        failed += 1
        print("  ❌ clamping wrong:", cb.adjusted[0], cb.adjusted[1], cb.max_rejected_p)

    # ── 9. refusals: a value offered as a p-value that is not one ─────────────
    if (
        _rejected(bonferroni_flat(_floats(0.1, 1.5), 2, 0.05))
        and bonferroni_flat(_floats(0.1, 1.5), 2, 0.05).status == INF_ERR_PVALUE_RANGE
        and _rejected(holm_flat(_floats(0.1, -0.2), 2, 0.05))
        and _rejected(benjamini_hochberg_flat(_floats(0.1, inference_absent()), 2, 0.05))
        and benjamini_hochberg_flat(_floats(0.1, inference_absent()), 2, 0.05).status
        == INF_ERR_PVALUE_RANGE
        # a declared family larger than the payload is never silently shortened
        and bonferroni_flat(_floats(0.1, 0.2), 5, 0.05).status == INF_ERR_SHAPE
        and bonferroni_flat(_floats(0.1), 0, 0.05).status == INF_ERR_EMPTY
        and bonferroni_flat(_floats(0.1), 1, 0.0).status == INF_ERR_ALPHA_RANGE
        and bonferroni_flat(_floats(0.1), 1, 1.0).status == INF_ERR_ALPHA_RANGE
        and bonferroni_flat(_floats(0.1), MAX_TESTS + 1, 0.05).status
        == INF_ERR_DIMENSION_TOO_LARGE
        and multiplicity_input_defect(_floats(0.1, 0.2), 2, 0.05) == INF_OK
        and multiplicity_input_defect(_floats(0.1, 2.0), 2, 0.05) == INF_ERR_PVALUE_RANGE
    ):
        passed += 1
        print("  ✅ a non-probability, a short payload and a degenerate alpha are all refused")
    else:
        failed += 1
        print("  ❌ a refusal leaked:", bonferroni_flat(_floats(0.1, 1.5), 2, 0.05).status)

    # ── 10. the declared family size is the caller's, not the payload's ────────
    # Correcting five supplied p-values as a family of three would understate every adjusted
    # value; correcting three of five is a legitimate request and must use n = 3.
    var subset = bonferroni_flat(family, 3, 0.05)
    if (
        subset.status == INF_OK
        and subset.n_tests == 3
        and len(subset.adjusted) == 3
        and subset.adjusted[0] == 3.0 * 0.01
        and subset.adjusted[2] == 3.0 * 0.03
    ):
        passed += 1
        print("  ✅ n is the declared family size and multiplies the adjustment, not len()")
    else:
        failed += 1
        print("  ❌ subset family wrong:", subset.n_tests, subset.adjusted[0])

    # ── 11. the nominal rate on independent uniform nulls ─────────────────────
    # 200 families of 20 all-null p-values from the counter RNG at a fixed seed. Under all
    # nulls the false-discovery rate IS the probability of any rejection, so BH's must sit
    # near alpha. Measured 0.065 with a 0.0154 standard error over 200 replications.
    var bh_hits = 0
    var bonf_hits = 0
    for rep in range(200):
        var draws = List[Float64](capacity=20)
        for j in range(20):
            draws.append(rng_uniform(4242, 0, 0, 0, 0, 9, UInt64(rep * 20 + j)))
        if benjamini_hochberg_flat(draws, 20, 0.05).n_rejected > 0:
            bh_hits += 1
        if bonferroni_flat(draws, 20, 0.05).n_rejected > 0:
            bonf_hits += 1
    var bh_rate = Float64(bh_hits) / 200.0
    var bonf_rate = Float64(bonf_hits) / 200.0
    if (
        bh_rate == 0.065
        and bh_rate <= 0.12
        and bonf_rate <= bh_rate
        and bh_rate > 0.0
    ):
        passed += 1
        print("  ✅ BH rejects a null family 6.5% of the time at alpha=0.05, reproducibly")
    else:
        failed += 1
        print("  ❌ nominal rate off:", bh_rate, bonf_rate)

    # ── 12. the A-Z harness shape, which must not abort ───────────────────────
    # The generated suite calls with _lf5 = [0.5, 0.6, 0.7, 0.4, 0.3] and 5 for every Int, so
    # every value is a legal p-value and the call runs rather than refusing. It must not
    # index past the end and it must reject nothing at alpha = 0.5 * ... except by the real
    # arithmetic: 5 * 0.3 = 1.5 -> clamped to 1.0, none below 0.5.
    var lf5 = _floats(0.5, 0.6, 0.7, 0.4, 0.3)
    var harness = bonferroni_flat(lf5, 5, 0.5)
    if (
        harness.status == INF_OK
        and harness.n_rejected == 0
        and harness.adjusted[4] == 1.0
        and harness.min_p == 0.3
        and holm_flat(lf5, 5, 0.5).status == INF_OK
        and benjamini_hochberg_flat(lf5, 5, 0.5).status == INF_OK
        and correction_agreement_flat(lf5, 5, 0.5).status == INF_OK
    ):
        passed += 1
        print("  ✅ the harness's five-element call runs and rejects nothing")
    else:
        failed += 1
        print("  ❌ harness call wrong:", harness.status, harness.n_rejected)

    print("  [inference.multiplicity] Passed:", passed, "Failed:", failed)
