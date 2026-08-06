"""test_causal_inference_base.mojo — known-value tests for the package's shared vocabulary.

Hand-written. The four things this suite exists to pin, none of which is a "it returned
something" check:

1. THE WRAPPING MULTIPLY. `3 * 6148914691236517206 == 2` is asserted here as an arithmetic fact
   before `ci_product_fits` is asked about the same pair, so the test proves the hazard exists
   and then proves the guard catches it. A guard written on the product instead of a division
   would pass a budget check for 1.8e19 units of work.
2. THE TOLERANCE HAS NO FLOOR. `ci_tolerance(0.0, t) == t` exactly, and doubling the magnitude
   exactly doubles the relative term. That is rule 4b spelling 3: a `1 + |x|` form would return
   `t + 1024*eps` at magnitude zero, an absolute allowance nobody asked for.
3. THE MACHINE EPSILON DOES NOT DRIFT. `CI_DBL_EPSILON` is asserted equal to
   `optimization.linear.LP_DBL_EPSILON`, which is the promise `base.mojo`'s docstring makes when
   it declares the constant locally instead of importing a simplex to read one number.
4. THE INDEX SORT IS THE FROZEN SORT. No frozen kernel returns a permutation, so
   `ci_argsort_asc` is validated DIFFERENTIALLY: the values gathered through the permutation are
   compared element by element against `sorting.mergesort` of the same input. Agreement between
   two independent computations is evidence; a plausible-looking order is not.

Plus stability (equal keys keep their original order, in both directions), absence on a
non-finite key, and the fixed five-element/five-integer argument pattern the A-Z harness uses.
"""
from std.math import sqrt

from sorting import mergesort
from optimization.linear import LP_DBL_EPSILON

from causal_inference.base import (
    CI_ABSENT,
    CI_DBL_EPSILON,
    CI_ERR_DEGENERATE_PROPENSITY,
    CI_ERR_DIMENSION_TOO_LARGE,
    CI_ERR_DUPLICATE,
    CI_ERR_INDEX,
    CI_ERR_INSUFFICIENT_DATA,
    CI_ERR_INVALID_PARAMETER,
    CI_ERR_LENGTH_MISMATCH,
    CI_ERR_NON_FINITE,
    CI_ERR_NOT_A_DAG,
    CI_ERR_NOT_CONVERGED,
    CI_ERR_NOT_IDENTIFIED,
    CI_ERR_NO_CONTROL,
    CI_ERR_NO_MATCHES,
    CI_ERR_NO_OVERLAP,
    CI_ERR_NO_TREATED,
    CI_ERR_SHAPE,
    CI_ERR_SINGULAR,
    CI_ERR_TREATMENT_NOT_BINARY,
    CI_ERR_WORK_BUDGET,
    CI_OK,
    CI_ULP_BUDGET,
    MAX_CI_DESIGN_CELLS,
    MAX_CI_FEATURES,
    MAX_CI_UNITS,
    ci_all_finite,
    ci_argsort_asc,
    ci_argsort_desc,
    ci_count_treated,
    ci_finite,
    ci_is_permutation,
    ci_matrix_fits,
    ci_panel_fits,
    ci_product3_fits,
    ci_product_fits,
    ci_status_name,
    ci_tolerance,
    ci_treatment_defect,
)


def _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _ints(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _same_ints(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


def _lf5() -> List[Float64]:
    return _floats(0.5, 0.6, 0.7, 0.4, 0.3)


def _li5() -> List[Int]:
    return _ints(1, 2, 3, 4, 5)


def _nan() -> Float64:
    """A real NaN, produced rather than written: `sqrt(-1)` is NaN on every IEEE double."""
    return sqrt(-1.0)


def _inf() -> Float64:
    return 1.0e308 * 10.0


def main() raises:
    var passed = 0
    var failed = 0

    # ── the wrapping multiply, asserted as a fact and then as a guard ─────────
    var huge = 6148914691236517206
    if 3 * huge == 2:
        passed += 1
        print("  ✅ 3 * 6148914691236517206 wraps to 2 — a product is NOT a bound")
    else:
        failed += 1
        print("  ❌ the wrapping multiply did not reproduce:", 3 * huge)

    if (
        not ci_product_fits(3, huge, 100)
        and not ci_product_fits(huge, 3, 100)
        and not ci_matrix_fits(3, huge, 2)
    ):
        passed += 1
        print("  ✅ the wrapping pair is refused by both budget and shape guards")
    else:
        failed += 1
        print("  ❌ a wrapping product passed a guard")

    # ── budgets: exact boundaries, not approximate ones ───────────────────────
    if (
        ci_product_fits(10, 10, 100)
        and not ci_product_fits(10, 11, 100)
        and ci_product_fits(0, huge, 100)
        and ci_product_fits(-5, huge, 100)
        and not ci_product_fits(1, 1, -1)
    ):
        passed += 1
        print("  ✅ ci_product_fits is exact at the boundary; a non-positive factor is no work")
    else:
        failed += 1
        print("  ❌ ci_product_fits boundary wrong")

    if (
        ci_product3_fits(10, 10, 10, 1000)
        and not ci_product3_fits(10, 10, 11, 1000)
        and not ci_product3_fits(1000, 1000, 1000, 1 << 29)
        and ci_product3_fits(1000, 1000, 1000, 1 << 30)
    ):
        passed += 1
        print("  ✅ ci_product3_fits charges ALL THREE factors (1e9 fits 2^30, not 2^29)")
    else:
        failed += 1
        print("  ❌ ci_product3_fits does not charge every factor")

    # ── shape: exact cells, both ceilings, and the joint cell budget ──────────
    if (
        ci_matrix_fits(3, 4, 12)
        and not ci_matrix_fits(3, 4, 11)
        and not ci_matrix_fits(3, 4, 13)
        and ci_matrix_fits(0, 0, 0)
        and not ci_matrix_fits(1, MAX_CI_FEATURES + 1, MAX_CI_FEATURES + 1)
        and not ci_matrix_fits(MAX_CI_UNITS + 1, 1, MAX_CI_UNITS + 1)
    ):
        passed += 1
        print("  ✅ ci_matrix_fits: exact cells and both per-axis ceilings")
    else:
        failed += 1
        print("  ❌ ci_matrix_fits wrong")

    # Both axes legal, product not. This is the case a per-axis check alone admits: 2^20 units
    # by 2^7 features is 2^27 cells, a 1 GB payload.
    if (
        MAX_CI_UNITS <= MAX_CI_UNITS
        and not ci_product_fits(MAX_CI_UNITS, MAX_CI_FEATURES, MAX_CI_DESIGN_CELLS)
        and not ci_matrix_fits(MAX_CI_UNITS, MAX_CI_FEATURES, 1)
    ):
        passed += 1
        print("  ✅ both axes inside their ceilings and the JOINT cell budget still refuses")
    else:
        failed += 1
        print("  ❌ the joint design-cell budget is not enforced")

    if ci_panel_fits(4, 3, 12) and not ci_panel_fits(4, 3, 13) and not ci_panel_fits(-1, 3, 0):
        passed += 1
        print("  ✅ ci_panel_fits: exact cells, negative refused")
    else:
        failed += 1
        print("  ❌ ci_panel_fits wrong")

    # ── the tolerance has NO floor and scales with the ONE judged quantity ────
    var t_abs = 1.0e-9
    if ci_tolerance(0.0, t_abs) == t_abs:
        passed += 1
        print("  ✅ ci_tolerance at magnitude 0 is EXACTLY the caller's absolute tolerance")
    else:
        failed += 1
        print("  ❌ ci_tolerance has a hidden floor:", ci_tolerance(0.0, t_abs), "vs", t_abs)

    var tol_m = ci_tolerance(1.0e6, 0.0)
    var tol_2m = ci_tolerance(2.0e6, 0.0)
    var expected_m = CI_ULP_BUDGET * CI_DBL_EPSILON * 1.0e6
    if tol_m == expected_m and tol_2m == 2.0 * tol_m:
        passed += 1
        print("  ✅ the relative term is 1024 * DBL_EPSILON * magnitude, exactly linear")
    else:
        failed += 1
        print("  ❌ relative term wrong:", tol_m, expected_m, tol_2m)

    # A nan magnitude must not produce a nan threshold, which would pass every comparison.
    if ci_tolerance(_nan(), 1.0e-9) == 0.0 and ci_tolerance(1.0, _nan()) == 0.0:
        passed += 1
        print("  ✅ a non-finite input yields a tolerance of 0.0, not nan (rule 4d)")
    else:
        failed += 1
        print("  ❌ a nan defeated the tolerance builder")

    if CI_DBL_EPSILON == LP_DBL_EPSILON:
        passed += 1
        print("  ✅ CI_DBL_EPSILON == optimization.linear.LP_DBL_EPSILON — no drift")
    else:
        failed += 1
        print("  ❌ machine epsilon drifted:", CI_DBL_EPSILON, LP_DBL_EPSILON)

    # ── finiteness ───────────────────────────────────────────────────────────
    if (
        ci_finite(0.0)
        and ci_finite(-1.0e300)
        and not ci_finite(_nan())
        and not ci_finite(_inf())
        and not ci_finite(-_inf())
        and ci_all_finite(_lf5())
        and not ci_all_finite(_floats(1.0, _nan()))
        and not ci_all_finite(_floats(1.0, _inf()))
        and ci_all_finite(List[Float64]())
    ):
        passed += 1
        print("  ✅ ci_finite / ci_all_finite catch NaN and both infinities")
    else:
        failed += 1
        print("  ❌ finiteness test wrong")

    # ── treatment vectors ────────────────────────────────────────────────────
    if (
        ci_treatment_defect(_ints(1, 0)) == CI_OK
        and ci_treatment_defect(_ints(1, 1)) == CI_ERR_NO_CONTROL
        and ci_treatment_defect(_ints(0, 0)) == CI_ERR_NO_TREATED
        and ci_treatment_defect(_ints(1, 0, 2)) == CI_ERR_TREATMENT_NOT_BINARY
        and ci_treatment_defect(_ints(1, 0, -1)) == CI_ERR_TREATMENT_NOT_BINARY
        and ci_treatment_defect(List[Int]()) == CI_ERR_NO_TREATED
        and ci_count_treated(_ints(1, 0, 1, 2)) == 2
    ):
        passed += 1
        print("  ✅ a third arm is refused, not pooled into control")
    else:
        failed += 1
        print("  ❌ treatment validation wrong")

    # ── the index sort IS the frozen sort ────────────────────────────────────
    var keys = _floats(3.0, -1.0, 2.5, -1.0, 7.25, 0.0)
    var asc = ci_argsort_asc(keys)
    var frozen_sorted = mergesort(keys)
    var gathered_ok = len(asc) == len(keys) and len(frozen_sorted) == len(keys)
    if gathered_ok:
        for i in range(len(keys)):
            if keys[asc[i]] != frozen_sorted[i]:
                gathered_ok = False
    if gathered_ok and ci_is_permutation(asc, len(keys)):
        passed += 1
        print("  ✅ ci_argsort_asc gathers EXACTLY sorting.mergesort, and is a permutation")
    else:
        failed += 1
        print("  ❌ the index sort disagrees with the frozen sort")

    var desc = ci_argsort_desc(keys)
    var desc_ok = len(desc) == len(keys)
    if desc_ok:
        for i in range(len(keys)):
            if keys[desc[i]] != frozen_sorted[len(keys) - 1 - i]:
                desc_ok = False
    if desc_ok:
        passed += 1
        print("  ✅ ci_argsort_desc is the reversed frozen order, value for value")
    else:
        failed += 1
        print("  ❌ descending order disagrees with the frozen sort")

    # Stability in BOTH directions: three equal keys keep their original order. A quicksort
    # would not, and the permutation would then depend on pivot choices rather than on the data.
    var flat = _floats(2.0, 2.0, 2.0, 2.0)
    if (
        _same_ints(ci_argsort_asc(flat), _ints(0, 1, 2, 3))
        and _same_ints(ci_argsort_desc(flat), _ints(0, 1, 2, 3))
    ):
        passed += 1
        print("  ✅ equal keys keep their original order in both directions (stable)")
    else:
        failed += 1
        print("  ❌ the sort is not stable")

    # Ties inside a real ordering: keys[1] and keys[3] are both -1.0 and must stay 1 before 3.
    if _same_ints(asc, _ints(1, 3, 5, 2, 0, 4)):
        passed += 1
        print("  ✅ tie at -1.0 resolves to index 1 then 3 — hand-enumerated order")
    else:
        failed += 1
        print("  ❌ ascending order wrong:", asc[0], asc[1], asc[2], asc[3], asc[4], asc[5])

    if (
        len(ci_argsort_asc(_floats(1.0, _nan(), 2.0))) == 0
        and len(ci_argsort_desc(_floats(1.0, _inf()))) == 0
        and len(ci_argsort_asc(List[Float64]())) == 0
        and _same_ints(ci_argsort_asc(_floats(9.0)), _ints(0))
    ):
        passed += 1
        print("  ✅ an ordering that does not exist is ABSENT (empty), not a garbage order")
    else:
        failed += 1
        print("  ❌ a non-finite key produced an order")

    # ── ci_is_permutation checks rather than trusts ───────────────────────────
    if (
        ci_is_permutation(_ints(0, 1, 2), 3)
        and ci_is_permutation(_ints(2, 0, 1), 3)
        and not ci_is_permutation(_ints(0, 0, 2), 3)
        and not ci_is_permutation(_ints(0, 1, 3), 3)
        and not ci_is_permutation(_ints(0, 1, -1), 3)
        and not ci_is_permutation(_ints(0, 1), 3)
        and not ci_is_permutation(_ints(0, 1, 2), 2)
        and ci_is_permutation(List[Int](), 0)
        and not ci_is_permutation(_ints(0), -1)
    ):
        passed += 1
        print("  ✅ ci_is_permutation rejects duplicates, out-of-range and wrong length")
    else:
        failed += 1
        print("  ❌ ci_is_permutation wrong")

    # ── all twenty status codes are 340-359 and have distinct names ───────────
    var codes = _ints(
        CI_OK, CI_ERR_SHAPE, CI_ERR_LENGTH_MISMATCH, CI_ERR_NON_FINITE,
        CI_ERR_DIMENSION_TOO_LARGE, CI_ERR_NOT_A_DAG, CI_ERR_INDEX,
        CI_ERR_NOT_IDENTIFIED, CI_ERR_NO_TREATED, CI_ERR_NO_CONTROL,
        CI_ERR_NO_OVERLAP, CI_ERR_DEGENERATE_PROPENSITY, CI_ERR_NOT_CONVERGED,
        CI_ERR_SINGULAR, CI_ERR_INSUFFICIENT_DATA, CI_ERR_NO_MATCHES,
        CI_ERR_TREATMENT_NOT_BINARY, CI_ERR_WORK_BUDGET, CI_ERR_DUPLICATE,
        CI_ERR_INVALID_PARAMETER,
    )
    var range_ok = len(codes) == 20
    for i in range(len(codes)):
        if codes[i] < 340 or codes[i] > 359:
            range_ok = False
        for j in range(i + 1, len(codes)):
            if codes[i] == codes[j]:
                range_ok = False
    var names_ok = True
    for i in range(len(codes)):
        var nm = ci_status_name(codes[i])
        if len(nm) == 0:
            names_ok = False
        for j in range(i + 1, len(codes)):
            if ci_status_name(codes[i]) == ci_status_name(codes[j]):
                names_ok = False
    if (
        range_ok
        and names_ok
        and ci_status_name(339) == "unknown_status_339"
        and ci_status_name(360) == "unknown_status_360"
        and ci_status_name(CI_OK) == "ok"
    ):
        passed += 1
        print("  ✅ all 20 codes lie in 340-359, are distinct, and name distinctly")
    else:
        failed += 1
        print("  ❌ status-code allocation broken:", range_ok, names_ok)

    if CI_ABSENT == -1.0:
        passed += 1
        print("  ✅ CI_ABSENT is -1.0, outside the range of every non-negative diagnostic")
    else:
        failed += 1
        print("  ❌ CI_ABSENT changed value")

    # ── the A-Z harness pattern ──────────────────────────────────────────────
    if (
        not ci_is_permutation(_li5(), 5)
        and len(ci_argsort_asc(_lf5())) == 5
        and not ci_matrix_fits(5, 5, 5)
        and not ci_product_fits(5, 5, 5)
        and ci_treatment_defect(_li5()) == CI_ERR_TREATMENT_NOT_BINARY
    ):
        passed += 1
        print("  ✅ the fixed 5-element / 5-integer harness pattern is handled, not indexed")
    else:
        failed += 1
        print("  ❌ the A-Z argument pattern is mishandled")

    print("  [causal_inference.base] Passed:", passed, "Failed:", failed)
