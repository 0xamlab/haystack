"""test_exactnum_lstsq.mojo — known-value tests for the compensated Householder QR route.

Hand-written. Registered in `tests/generate_mojo_tests.py` HANDWRITTEN_TESTS.

THE LOAD-BEARING TEST, AND WHY ITS EXPECTED VALUE NEEDS NO EXTERNAL SOURCE
-------------------------------------------------------------------------
`x = 0, 1, ..., 20` and `y_i = 1 + x_i + x_i^2 + x_i^3 + x_i^4 + x_i^5`. This is the shape of
NIST StRD Wampler1, and it has a property that makes it the ideal test: every design-matrix
entry (`x^5` at most `20^5 = 3,200,000`) and every response (`max 3,368,421`) is an integer
well inside float64's exact 2^53 grid. So the system is represented EXACTLY in float64, the
exact least-squares solution is provably the vector of ones, and the expected value is
`1.0` in every component with no rounding assumption and no external witness needed.

Every digit a solver loses here is therefore pure working-precision loss, and it is severe:
the float64 control on the identical algorithm returns values that are NOT 1.0, while the
compensated route returns 1.0 exactly in all six components. That is the anti-vacuity proof at
the solver layer, and it is the same effect that produces the +6.2 to +7.9 correct-digit
margins over LAPACK on the real StRD Wampler datasets.

The full suite against the published NIST files, with the reference field, lives in
`benchmarks/external_baselines/strd_lstsq/score.py`; it needs the .dat files and numpy, so it
cannot run here. This file covers the contract, the guards and the arithmetic claim.
"""
from exactnum.eft import EFT_OK, eft_selfcheck_code
from exactnum.lstsq import (
    LSTSQ_ERR_A_LENGTH,
    LSTSQ_ERR_B_LENGTH,
    LSTSQ_ERR_BASIS_NOT_APPLICABLE,
    LSTSQ_ERR_CELLS_TOO_LARGE,
    LSTSQ_ERR_EMPTY_DIM,
    LSTSQ_ERR_NON_FINITE_INPUT,
    LSTSQ_ERR_RANK_DEFICIENT,
    LSTSQ_ERR_UNDERDETERMINED,
    LSTSQ_ERR_WORK_TOO_LARGE,
    LSTSQ_MAX_CELLS,
    LSTSQ_MAX_COLS,
    LSTSQ_MAX_WORK,
    LSTSQ_OK,
    dd_lstsq_flat,
    dd_poly_lstsq,
    dd_poly_lstsq_scaled,
    f64_lstsq_flat,
    f64_poly_lstsq,
    lstsq_cells_fit,
    lstsq_status_name,
    lstsq_work_fits,
)


fn wampler_x() -> List[Float64]:
    """x = 0..20, integers, exactly representable in float64."""
    var x = List[Float64]()
    for i in range(21):
        x.append(Float64(i))
    return x^


fn wampler_y() -> List[Float64]:
    """y_i = sum_{k=0..5} x_i^k. Every value is an integer inside the 2^53 exact grid, so the
    exact least-squares solution is provably the vector of ones."""
    var y = List[Float64]()
    for i in range(21):
        var xv = Float64(i)
        var acc: Float64 = 0.0
        var t: Float64 = 1.0
        for _ in range(6):
            acc += t
            t = t * xv
        y.append(acc)
    return y^


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    if eft_selfcheck_code() == EFT_OK:
        passed += 1
        print("  ✅ the arithmetic assumption the solver rests on holds on this build")
    else:
        failed += 1
        print("  ❌ arithmetic selfcheck failed; no result from this module can be trusted")

    # ── status vocabulary: distinct, inside 810-819, no overlap with eft's 800-809 ──
    var codes = List[Int]()
    codes.append(LSTSQ_OK)
    codes.append(LSTSQ_ERR_EMPTY_DIM)
    codes.append(LSTSQ_ERR_A_LENGTH)
    codes.append(LSTSQ_ERR_B_LENGTH)
    codes.append(LSTSQ_ERR_UNDERDETERMINED)
    codes.append(LSTSQ_ERR_CELLS_TOO_LARGE)
    codes.append(LSTSQ_ERR_WORK_TOO_LARGE)
    codes.append(LSTSQ_ERR_NON_FINITE_INPUT)
    codes.append(LSTSQ_ERR_RANK_DEFICIENT)
    codes.append(LSTSQ_ERR_BASIS_NOT_APPLICABLE)
    var distinct = True
    var in_range = True
    for i in range(len(codes)):
        if codes[i] < 810 or codes[i] > 819:
            in_range = False
        for j in range(len(codes)):
            if i != j and lstsq_status_name(codes[i]) == lstsq_status_name(codes[j]):
                distinct = False
    if distinct and in_range and lstsq_status_name(800) == String("unknown_status"):
        passed += 1
        print(
            "  ✅ lstsq statuses are distinct, inside 810-819, and do not claim eft's 800-809",
        )
    else:
        failed += 1
        print("  ❌ lstsq status codes collide or overlap the eft range (rule 4e)")

    # ── THE LOAD-BEARING TEST ────────────────────────────────────────────────
    var wx = wampler_x()
    var wy = wampler_y()
    var dd_fit = dd_poly_lstsq(wx, wy, 21, 0, 5, True, 0)
    var f64_fit = f64_poly_lstsq(wx, wy, 21, 0, 5, False)
    var dd_all_exact = dd_fit.status == LSTSQ_OK and len(dd_fit.coefficients) == 6
    if dd_all_exact:
        for j in range(6):
            if dd_fit.coefficients[j] != 1.0:
                dd_all_exact = False
    var f64_any_wrong = f64_fit.status == LSTSQ_OK and len(f64_fit.coefficients) == 6
    var f64_wrong_count = 0
    if f64_any_wrong:
        for j in range(6):
            if f64_fit.coefficients[j] != 1.0:
                f64_wrong_count += 1
    if dd_all_exact and f64_wrong_count > 0:
        passed += 1
        print(
            "  ✅ ANTI-VACUITY: on a system that is EXACT in float64 (x = 0..20 integers,",
            "y integers, exact solution all ones) the compensated route returns 1.0 in all 6",
            "components while the identical algorithm in float64 gets",
            f64_wrong_count,
            "of 6 wrong",
        )
    else:
        failed += 1
        print(
            "  ❌ either the compensated route did not reach the exact solution, or float64",
            "already did — in which case this case proves nothing about the compensation",
        )

    # the double-double tail is published, and a tail that is identically zero on an inexact
    # problem is the signature of the compensation having degraded
    var norris_like_x = List[Float64]()
    var norris_like_y = List[Float64]()
    for i in range(9):
        norris_like_x.append(0.1 * Float64(i) + 0.3)
        norris_like_y.append(0.7 * (0.1 * Float64(i) + 0.3) + 0.2)
    var inexact = dd_poly_lstsq(norris_like_x, norris_like_y, 9, 0, 1, True, 0)
    var tail_nonzero = False
    if inexact.status == LSTSQ_OK:
        for j in range(len(inexact.coefficients_lo)):
            if inexact.coefficients_lo[j] != 0.0:
                tail_nonzero = True
    var f64_tail_zero = True
    var f64_inexact = f64_poly_lstsq(norris_like_x, norris_like_y, 9, 0, 1, False)
    if f64_inexact.status == LSTSQ_OK:
        for j in range(len(f64_inexact.coefficients_lo)):
            if f64_inexact.coefficients_lo[j] != 0.0:
                f64_tail_zero = False
    if tail_nonzero and f64_tail_zero:
        passed += 1
        print(
            "  ✅ the dd route publishes a nonzero double-double tail on an inexact problem",
            "and the float64 control publishes all zeros — the tail is real, not decoration",
        )
    else:
        failed += 1
        print("  ❌ the published double-double tail is identically zero (degraded to float64?)")

    # ── dimension guards. Rule 1: the generated A-Z suite calls every contract function
    # with 5-element lists and every Int as 5, so an unguarded count indexes a[24] on a
    # 5-element list and takes the whole worker down uncatchably.
    var lf5 = List[Float64]()
    for _ in range(5):
        lf5.append(1.0)
    var g_az = dd_lstsq_flat(lf5, 5, 5, lf5, 5)
    var g_az_f = f64_lstsq_flat(lf5, 5, 5, lf5)
    var g_short_a = dd_lstsq_flat(lf5, 3, 2, lf5, 0)
    var g_short_b = dd_lstsq_flat(lf5, 5, 1, lf5, 0)
    var g_zero = dd_lstsq_flat(lf5, 0, 2, lf5, 0)
    var g_wide = dd_lstsq_flat(lf5, 2, 3, lf5, 0)
    if (
        g_az.status == LSTSQ_ERR_A_LENGTH
        and g_az_f.status == LSTSQ_ERR_A_LENGTH
        and len(g_az.coefficients) == 0
        and g_short_a.status == LSTSQ_ERR_A_LENGTH
        and g_zero.status == LSTSQ_ERR_EMPTY_DIM
        and g_wide.status == LSTSQ_ERR_UNDERDETERMINED
    ):
        passed += 1
        print(
            "  ✅ the A-Z generated call shape (5-element lists, every Int 5) is refused with",
            "a status and no coefficients, not indexed past the end (rule 1)",
        )
    else:
        failed += 1
        print("  ❌ a dimension argument was trusted against a shorter buffer")

    # b of the wrong length is a DIFFERENT defect from a of the wrong length
    var b3 = List[Float64]()
    for _ in range(3):
        b3.append(1.0)
    var a6 = List[Float64]()
    for _ in range(6):
        a6.append(1.0)
    if dd_lstsq_flat(a6, 2, 3, b3, 0).status == LSTSQ_ERR_UNDERDETERMINED:
        passed += 1
        print("  ✅ fewer rows than columns is reported as underdetermined, not solved")
    else:
        failed += 1
        print("  ❌ an underdetermined system was not refused")
    var a9 = List[Float64]()
    for _ in range(9):
        a9.append(1.0)
    if dd_lstsq_flat(a9, 3, 3, b3, 0).status != LSTSQ_ERR_B_LENGTH:
        # 3x3 with len(b)=3 is a legitimate shape; the B_LENGTH path needs a real mismatch
        if dd_lstsq_flat(a9, 3, 3, lf5, 0).status == LSTSQ_ERR_B_LENGTH:
            passed += 1
            print("  ✅ a response vector whose length disagrees with `rows` is refused")
        else:
            failed += 1
            print("  ❌ a mismatched response length was accepted")
    else:
        failed += 1
        print("  ❌ a valid 3x3 shape was rejected as a length mismatch")

    # ── wrapping-product guards. `3 * 6148914691236517206 == 2` in 64-bit wrapping
    # arithmetic, which is how a product guard was walked past in sparse_numerics and
    # aborted the worker. Both budgets are checked by division for exactly this reason.
    var huge = 6148914691236517206
    if (
        not lstsq_cells_fit(3, huge, LSTSQ_MAX_CELLS)
        and not lstsq_work_fits(3, huge, LSTSQ_MAX_WORK)
        and lstsq_cells_fit(100, 10, LSTSQ_MAX_CELLS)
        and lstsq_work_fits(100, 10, LSTSQ_MAX_WORK)
        and not lstsq_cells_fit(0, 10, LSTSQ_MAX_CELLS)
        and not lstsq_work_fits(10, 0, LSTSQ_MAX_WORK)
    ):
        passed += 1
        print("  ✅ the cell and work budgets are division-based, so the product cannot wrap")
    else:
        failed += 1
        print("  ❌ a budget guard can be walked past with a wrapping product")

    # bounding memory is not bounding work (rule 1c): a shape inside the cell budget whose
    # rows*cols^2 is not
    var wide_ok_cells = lstsq_cells_fit(1024, LSTSQ_MAX_COLS, LSTSQ_MAX_CELLS)
    var wide_bad_work = not lstsq_work_fits(1024, LSTSQ_MAX_COLS, LSTSQ_MAX_WORK)
    if wide_ok_cells and wide_bad_work:
        passed += 1
        print(
            "  ✅ a shape inside the CELL budget whose rows*cols^2 is not is refused —",
            "bounding memory is not bounding work (rule 1c)",
        )
    else:
        failed += 1
        print("  ❌ the work budget does not bind independently of the memory budget")

    # ── rank deficiency: absent, not zero (rule 4) ───────────────────────────
    # A duplicated column makes the minimiser non-unique. The frozen linalg.mat_solve returns
    # an all-zeros vector of length n here, so "the answer is zero" and "there is no answer"
    # are the same return value there. This must not do that.
    var dup = List[Float64]()
    var dupb = List[Float64]()
    for i in range(6):
        dup.append(1.0)
        dup.append(Float64(i))
        dup.append(Float64(i))
        dupb.append(1.0 + Float64(i))
    var rd = dd_lstsq_flat(dup, 6, 3, dupb, 0)
    var rdf = f64_lstsq_flat(dup, 6, 3, dupb)
    if (
        rd.status == LSTSQ_ERR_RANK_DEFICIENT
        and len(rd.coefficients) == 0
        and rdf.status == LSTSQ_ERR_RANK_DEFICIENT
        and len(rdf.coefficients) == 0
    ):
        passed += 1
        print(
            "  ✅ a dependent column gives a status and NO coefficients — never a zero vector",
            "a caller cannot tell apart from an answer (rule 4)",
        )
    else:
        failed += 1
        print("  ❌ a rank-deficient system returned numbers: dd", rd.status, len(rd.coefficients), "f64", rdf.status, len(rdf.coefficients), "rdiag", rd.r_diag_min, rdf.r_diag_min)

    # ── non-finite input is refused before anything is built from it ─────────
    var nan_a = List[Float64]()
    for i in range(6):
        nan_a.append(1.0)
    nan_a[3] = 0.0 / 0.0
    var b3b = List[Float64]()
    for _ in range(3):
        b3b.append(1.0)
    var inf_b = List[Float64]()
    for _ in range(3):
        inf_b.append(1.0)
    inf_b[1] = 1.0 / 0.0
    var good_a = List[Float64]()
    for i in range(3):
        good_a.append(1.0)
        good_a.append(Float64(i))
    if (
        dd_lstsq_flat(nan_a, 3, 2, b3b, 0).status == LSTSQ_ERR_NON_FINITE_INPUT
        and dd_lstsq_flat(good_a, 3, 2, inf_b, 0).status == LSTSQ_ERR_NON_FINITE_INPUT
        and f64_lstsq_flat(nan_a, 3, 2, b3b).status == LSTSQ_ERR_NON_FINITE_INPUT
    ):
        passed += 1
        print("  ✅ a NaN or infinity in the design matrix or the response is refused (rule 4d)")
    else:
        failed += 1
        print("  ❌ a non-finite input travelled into the factorisation")

    # ── the conditioned-basis arm refuses what it cannot map back ────────────
    # Centring reparameterises the WHOLE polynomial space; a no-intercept model is not that
    # space, so there is no correct map back and approximating one would be a wrong answer
    # dressed as a right one.
    var flat_x = List[Float64]()
    var flat_y = List[Float64]()
    for _ in range(5):
        flat_x.append(2.0)
        flat_y.append(1.0)
    var span0 = dd_poly_lstsq_scaled(flat_x, flat_y, 5, 1, True, True, 0)
    if span0.status == LSTSQ_ERR_BASIS_NOT_APPLICABLE and len(span0.coefficients) == 0:
        passed += 1
        print(
            "  ✅ a predictor with zero span has no conditioned basis and is refused, not",
            "silently fitted in the unscaled one",
        )
    else:
        failed += 1
        print("  ❌ the scaled arm accepted a degenerate domain:", span0.status)

    # and the scaled arm on the load-bearing data reports in the PUBLISHED basis, which on
    # exactly-representable integer data is WORSE than the raw basis — the antagonism the
    # route's docstring declares, asserted so a future change cannot quietly reverse it
    var scaled = dd_poly_lstsq_scaled(wx, wy, 21, 5, True, True, 0)
    var scaled_exact = scaled.status == LSTSQ_OK and len(scaled.coefficients) == 6
    if scaled_exact:
        for j in range(6):
            if scaled.coefficients[j] != 1.0:
                scaled_exact = False
    if scaled.status == LSTSQ_OK and not scaled_exact and dd_all_exact:
        passed += 1
        print(
            "  ✅ on exactly-representable integer data the conditioned basis is WORSE after",
            "map back than the raw basis — basis conditioning and compensation are",
            "antagonistic here, and the raw basis is the declared route",
        )
    else:
        failed += 1
        print("  ❌ the declared antagonism between conditioning and the raw basis did not hold")

    # ── self-consistency of the returned report (rule 4b's closing note) ─────
    var consistent = True
    if dd_fit.status == LSTSQ_OK:
        if dd_fit.rank != len(dd_fit.coefficients):
            consistent = False
        if len(dd_fit.coefficients) != len(dd_fit.coefficients_lo):
            consistent = False
        if dd_fit.residual_norm < 0.0:
            consistent = False
        if dd_fit.r_diag_min <= 0.0:
            consistent = False
        if dd_fit.refine_steps != 0:
            consistent = False
    var refined = dd_poly_lstsq(wx, wy, 21, 0, 5, True, 2)
    if refined.status != LSTSQ_OK or refined.refine_steps != 2:
        consistent = False
    if consistent:
        passed += 1
        print(
            "  ✅ the result's own fields agree with each other: rank == len(coefficients),",
            "tails are the same length, residual >= 0, r_diag_min > 0, refine count reported",
        )
    else:
        failed += 1
        print("  ❌ the returned report contradicts itself")

    # a refine count outside the admitted range is refused rather than clamped
    if dd_poly_lstsq(wx, wy, 21, 0, 5, True, 99).status == LSTSQ_ERR_EMPTY_DIM:
        passed += 1
        print("  ✅ an out-of-range refinement count is refused, not silently clamped")
    else:
        failed += 1
        print("  ❌ an out-of-range refinement count was accepted")

    print("  [exactnum.lstsq] Passed:", passed, "Failed:", failed)
