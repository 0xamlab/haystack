"""test_sparse_numerics_diagnostics.mojo — known-value tests for the health report.

Hand-written. Every assertion here targets a frozen kernel that reports failure as a
value, so the frozen kernel is called alongside the wrapper and both answers are
asserted: `sparse.sparse_density` returning 0.0 for a matrix with no elements and 2.0
for a duplicate-bearing one, `sparse_vector.sv_max` returning the largest NEGATIVE
value for an all-negative matrix, `sparse_vector.sv_nnz` counting at 1e-30 while the
dense builders store at 1e-15, and `linalg_ext.mat_condition_number` returning exactly
1e18 for non-square, for singular AND for the empty matrix.

`matrix_ops.matrix_norm_inf`, `matrix_ops.matrix_norm_1` and
`matrix_decomp.is_symmetric` are differential oracles rather than dependencies: they
take a nested dense matrix, which is the wrong storage for a sparse layout, so the
sparse row/column sums and the sparse symmetry merge are proved equal to them on the
dense image of a small finite matrix instead of being assumed equal.

The last block calls every flat driver with exactly the arguments the generated A-Z
suite uses — five-element lists and 5 for every Int — because indexing a five-element
list at 24 is an uncatchable process crash rather than an exception.
"""
from std.math import isnan

from linalg import mat_from_list
from linalg_ext import mat_condition_number
from matrix_decomp import is_symmetric
from matrix_ops import matrix_norm_1, matrix_norm_inf
from sparse import SparseMatrixCOO, sparse_add, sparse_density
from sparse_numerics.csr import (
    CSRMatrix,
    CSR_ERR_INDEX_OUT_OF_RANGE,
    CSR_ERR_INDPTR_LENGTH,
    CSR_ERR_INVALID_DIMENSIONS,
    CSR_OK,
    csr_empty,
    csr_from_arrays,
    csr_from_dense,
)
from sparse_numerics.diagnostics import (
    DIAG_CONDITION_SENTINEL,
    DIAG_DENSE_STORE_THRESHOLD,
    DIAG_ERR_EMPTY,
    DIAG_ERR_NON_FINITE,
    DIAG_ERR_NOT_SQUARE,
    DIAG_ERR_SINGULAR,
    DIAG_ERR_TOO_LARGE,
    DIAG_SV_NNZ_THRESHOLD,
    SparseConditionEstimate,
    SparseHealthReport,
    SparseMetric,
    diag_status_name,
    sparse_condition_estimate,
    sparse_condition_estimate_driver,
    sparse_density_checked,
    sparse_density_driver,
    sparse_health,
    sparse_health_driver,
    sparse_health_from_dense_driver,
    sparse_health_summary_driver,
    sparse_max_abs,
    sparse_max_abs_driver,
    sparse_max_element,
    sparse_max_element_driver,
    sparse_min_abs_diagonal,
    sparse_min_abs_diagonal_driver,
    sparse_row_norm_inf,
    sparse_row_norm_inf_driver,
    sparse_symmetry_defect,
    sparse_symmetry_defect_driver,
    sparse_trace_checked,
    sparse_trace_driver,
)
from sparse_vector import sv_max, sv_nnz


fn _ints1(a: Int) -> List[Int]:
    var out = List[Int]()
    out.append(a)
    return out^


fn _ints2(a: Int, b: Int) -> List[Int]:
    var out = List[Int]()
    out.append(a)
    out.append(b)
    return out^


fn _ints3(a: Int, b: Int, c: Int) -> List[Int]:
    var out = List[Int]()
    out.append(a)
    out.append(b)
    out.append(c)
    return out^


fn _floats1(a: Float64) -> List[Float64]:
    var out = List[Float64]()
    out.append(a)
    return out^


fn _floats2(a: Float64, b: Float64) -> List[Float64]:
    var out = List[Float64]()
    out.append(a)
    out.append(b)
    return out^


fn _floats3(a: Float64, b: Float64, c: Float64) -> List[Float64]:
    var out = List[Float64]()
    out.append(a)
    out.append(b)
    out.append(c)
    return out^


fn _floats4(
    a: Float64, b: Float64, c: Float64, d: Float64
) -> List[Float64]:
    var out = List[Float64]()
    out.append(a)
    out.append(b)
    out.append(c)
    out.append(d)
    return out^


fn _floats6(
    a: Float64,
    b: Float64,
    c: Float64,
    d: Float64,
    e: Float64,
    f: Float64,
) -> List[Float64]:
    var out = List[Float64]()
    out.append(a)
    out.append(b)
    out.append(c)
    out.append(d)
    out.append(e)
    out.append(f)
    return out^


fn _nested(flat: List[Float64], rows: Int, cols: Int) -> List[List[Float64]]:
    """Row-of-rows image, for the frozen dense oracles only."""
    var out = List[List[Float64]]()
    for i in range(rows):
        var row = List[Float64]()
        for j in range(cols):
            row.append(flat[i * cols + j])
        out.append(row^)
    return out^


fn _dense3x3(
    a: Float64,
    b: Float64,
    c: Float64,
    d: Float64,
    e: Float64,
    f: Float64,
    g: Float64,
    h: Float64,
    i: Float64,
) -> List[Float64]:
    var out = List[Float64]()
    out.append(a)
    out.append(b)
    out.append(c)
    out.append(d)
    out.append(e)
    out.append(f)
    out.append(g)
    out.append(h)
    out.append(i)
    return out^


fn _near(actual: Float64, expected: Float64) -> Bool:
    """Tolerance only where an exact literal is not the natural value (e.g. 1/3)."""
    var delta = actual - expected
    if delta < 0.0:
        delta = -delta
    return delta < 1e-12


fn main() raises:
    var passed = 0
    var failed = 0
    var nan_value = Float64(0.0) / Float64(0.0)

    # ── a 0x0 matrix has NO density; the frozen kernel's 0.0 is a sentinel ────
    # sparse_density divides by nrows*ncols and returns 0.0 when that is zero, so an
    # empty matrix and a genuinely all-zero 5x5 come back with the same number.
    var empty_00 = csr_empty(0, 0)
    var empty_55 = csr_empty(5, 5)
    var r00 = sparse_health(empty_00)
    var r55 = sparse_health(empty_55)
    var sentinel_00 = sparse_density(SparseMatrixCOO(0, 0))
    var sentinel_55 = sparse_density(SparseMatrixCOO(5, 5))
    if (
        sentinel_00 == 0.0
        and sentinel_55 == 0.0
        and r00.status == CSR_OK
        and r00.diagnosed
        and not r00.has_elements
        and r55.has_elements
        and r55.density == 0.0
    ):
        passed += 1
        print(
            "  ✅ 0x0 has no density while an empty 5x5 has density 0.0 — the frozen"
            " kernel returns 0.0 for both"
        )
    else:
        failed += 1
        print("  ❌ empty-matrix density policy wrong:", r00.has_elements, r55.density)

    # ── nothing has a maximum, but a count of nothing is 0 ────────────────────
    # sv_max of an empty list returns 0.0. That reaches no caller through here.
    if (
        sv_max(List[Float64]()) == 0.0
        and not r00.max_abs_present
        and not r00.max_element_present
        and not r00.min_abs_diag_present
        and r00.trace_present
        and r00.trace == 0.0
        and r00.nnz == 0
        and not r00.structurally_singular
    ):
        passed += 1
        print("  ✅ 0x0: max/min absent, trace 0.0 and nnz 0 are real answers")
    else:
        failed += 1
        print("  ❌ 0x0 absence policy wrong:", r00.max_abs_present, r00.trace)

    # ── an all-negative matrix: sv_max reports its largest NEGATIVE value ────
    # diag(-3, -1) in a 2x2. Two positions are unstored, and each holds a real zero,
    # so the matrix maximum is 0.0 — a value sv_max cannot produce.
    var neg_dense = _floats4(-3.0, 0.0, 0.0, -1.0)
    var neg = csr_from_dense(neg_dense, 2, 2)
    var rneg = sparse_health(neg)
    if (
        sv_max(_floats2(-3.0, -1.0)) == -1.0
        and rneg.max_stored == -1.0
        and rneg.max_element == 0.0
        and not rneg.max_stored_is_matrix_max
        and rneg.max_abs == 3.0
    ):
        passed += 1
        print(
            "  ✅ all-negative: stored max -1.0, true max 0.0 (an implicit zero), and"
            " they are flagged as different"
        )
    else:
        failed += 1
        print(
            "  ❌ implicit-zero maximum wrong:",
            rneg.max_stored,
            rneg.max_element,
            rneg.max_stored_is_matrix_max,
        )

    # ── with NO implicit zero, the stored max IS the matrix max ───────────────
    # The 1x1 [-3] stores every position, so nothing was left out and the flag flips.
    var full_neg = csr_from_dense(_floats1(-3.0), 1, 1)
    var rfull = sparse_health(full_neg)
    if (
        rfull.max_stored_is_matrix_max
        and rfull.max_element == -3.0
        and rfull.max_stored == -3.0
    ):
        passed += 1
        print("  ✅ a fully stored all-negative matrix has maximum -3.0, not 0.0")
    else:
        failed += 1
        print("  ❌ fully-stored maximum wrong:", rfull.max_element)

    # ── the rest of the all-negative report, hand-computed ───────────────────
    if (
        rneg.nnz == 2
        and rneg.nnz_canonical == 2
        and rneg.duplicates == 0
        and rneg.density == 0.5
        and rneg.trace == -4.0
        and rneg.norm_inf == 3.0
        and rneg.norm_1 == 3.0
        and rneg.min_abs_diag == 1.0
        and rneg.missing_diagonal == 0
        and rneg.symmetric
        and rneg.symmetry_defect == 0.0
        and not rneg.structurally_singular
    ):
        passed += 1
        print("  ✅ diag(-3,-1): density 0.5, trace -4, norms 3, min |diag| 1, symmetric")
    else:
        failed += 1
        print("  ❌ all-negative report wrong:", rneg.density, rneg.trace, rneg.norm_inf)

    # ── an empty row is found, and it proves structural singularity ──────────
    # [[1,0,2],[0,0,0],[0,4,0]]: row 1 stores nothing; every column stores something.
    var gap_dense = _dense3x3(1.0, 0.0, 2.0, 0.0, 0.0, 0.0, 0.0, 4.0, 0.0)
    var gap = csr_from_dense(gap_dense, 3, 3)
    var rgap = sparse_health(gap)
    if (
        rgap.empty_rows == 1
        and rgap.empty_cols == 0
        and rgap.structurally_singular
        and rgap.nnz_canonical == 3
        and _near(rgap.density, 1.0 / 3.0)
    ):
        passed += 1
        print("  ✅ one empty row out of three: structurally singular, density 1/3")
    else:
        failed += 1
        print("  ❌ empty-row detection wrong:", rgap.empty_rows, rgap.empty_cols)

    # ── an absent diagonal entry is a ZERO, not a missing observation ─────────
    # A minimum over the STORED diagonal would report 1.0 here and hide the two zeros
    # sitting at (1,1) and (2,2) — the same lie as sv_max ignoring implicit zeros.
    if (
        rgap.missing_diagonal == 2
        and rgap.min_abs_diag_present
        and rgap.min_abs_diag == 0.0
        and rgap.trace == 1.0
    ):
        passed += 1
        print("  ✅ two absent diagonal entries drive min |A_ii| to 0.0, trace stays 1.0")
    else:
        failed += 1
        print(
            "  ❌ diagonal accounting wrong:",
            rgap.missing_diagonal,
            rgap.min_abs_diag,
        )

    # ── the sparse norms agree with the frozen dense norms ───────────────────
    # matrix_norm_inf / matrix_norm_1 take a nested dense matrix, so they are oracles
    # here, not dependencies: reaching them from CSR would cost rows*cols Float64s.
    var gap_nested = _nested(gap_dense, 3, 3)
    if (
        rgap.norm_inf == matrix_norm_inf(gap_nested)
        and rgap.norm_1 == matrix_norm_1(gap_nested)
        and rgap.norm_inf == 4.0
        and rgap.norm_1 == 4.0
    ):
        passed += 1
        print("  ✅ sparse row/column sums equal the frozen dense norms (both 4.0)")
    else:
        failed += 1
        print(
            "  ❌ norms disagree with the dense oracle:",
            rgap.norm_inf,
            matrix_norm_inf(gap_nested),
        )

    # ── the symmetry defect agrees with the frozen dense predicate ───────────
    # A_21 = 4 against A_12 = 0 is the worst pair, so the defect is 4. A merge that
    # skipped coordinates present on one side only would report 0 and call this
    # matrix symmetric.
    if (
        rgap.symmetry_defect == 4.0
        and not rgap.symmetric
        and not is_symmetric(gap_nested)
    ):
        passed += 1
        print("  ✅ one-sided coordinates counted: defect 4.0, not symmetric")
    else:
        failed += 1
        print("  ❌ symmetry defect wrong:", rgap.symmetry_defect)

    # ── an empty column is found too ─────────────────────────────────────────
    var colgap = csr_from_dense(
        _dense3x3(1.0, 0.0, 0.0, 0.0, 0.0, 2.0, 0.0, 0.0, 3.0), 3, 3
    )
    var rcolgap = sparse_health(colgap)
    if (
        rcolgap.empty_cols == 1
        and rcolgap.empty_rows == 0
        and rcolgap.structurally_singular
    ):
        passed += 1
        print("  ✅ an empty column with no empty row is still structurally singular")
    else:
        failed += 1
        print("  ❌ empty-column detection wrong:", rcolgap.empty_cols)

    # ── a genuinely symmetric matrix, checked against the frozen predicate ───
    var sym_dense = _dense3x3(2.0, 1.0, 0.0, 1.0, 3.0, 4.0, 0.0, 4.0, 5.0)
    var sym = csr_from_dense(sym_dense, 3, 3)
    var rsym = sparse_health(sym)
    if (
        rsym.symmetric
        and is_symmetric(_nested(sym_dense, 3, 3))
        and rsym.symmetry_defect == 0.0
        and rsym.symmetry_defect_present
        and rsym.trace == 10.0
        and rsym.norm_inf == 9.0
        and rsym.norm_1 == 9.0
        and rsym.min_abs_diag == 2.0
        and rsym.missing_diagonal == 0
        and not rsym.structurally_singular
    ):
        passed += 1
        print("  ✅ symmetric 3x3: defect 0, trace 10, norms 9, min |diag| 2")
    else:
        failed += 1
        print("  ❌ symmetric report wrong:", rsym.symmetric, rsym.symmetry_defect)

    # ── a non-square matrix has no trace and no symmetry defect ──────────────
    # sparse_trace sums every row==col entry whatever the shape, so it answers with a
    # number for a 2x3 matrix. That number is not a trace.
    var wide = csr_from_dense(_floats6(1.0, 2.0, 3.0, 4.0, 5.0, 6.0), 2, 3)
    var rwide = sparse_health(wide)
    var wide_trace_metric = sparse_trace_checked(wide)
    if (
        not rwide.trace_present
        and rwide.trace == 0.0
        and not wide_trace_metric.present
        and wide_trace_metric.status == DIAG_ERR_NOT_SQUARE
        and not rwide.symmetry_defect_present
        and not rwide.symmetric
        and rwide.structurally_singular
    ):
        passed += 1
        print("  ✅ a 2x3 has no trace and no symmetry defect, and is not square")
    else:
        failed += 1
        print("  ❌ non-square policy wrong:", rwide.trace_present, rwide.trace)

    # ── an out-of-range column index is DIAGNOSED, not indexed ──────────────
    # indptr is sound, so the pointer structure bounds every loop; index 7 in a 2x2 is
    # dropped and counted. Reading values[7] here would kill the process.
    var stray = csr_from_arrays(
        _ints3(0, 2, 3),
        _ints3(0, 7, 1),
        _floats3(1.0, 9.0, 2.0),
        2,
        2,
    )
    var rstray = sparse_health(stray)
    if (
        rstray.status == CSR_ERR_INDEX_OUT_OF_RANGE
        and rstray.diagnosed
        and rstray.out_of_range == 1
        and rstray.nnz == 3
        and rstray.nnz_canonical == 2
        and rstray.duplicates == 0
        and rstray.norm_inf == 2.0
        and rstray.trace == 3.0
    ):
        passed += 1
        print(
            "  ✅ an out-of-range entry is dropped, counted and named in the status —"
            " the in-range 2x2 is still diagnosed"
        )
    else:
        failed += 1
        print(
            "  ❌ out-of-range handling wrong:",
            rstray.status,
            rstray.out_of_range,
            rstray.nnz_canonical,
        )

    # ── the nnz accounting closes ────────────────────────────────────────────
    if (
        rstray.nnz
        == rstray.nnz_canonical + rstray.duplicates + rstray.out_of_range
    ):
        passed += 1
        print("  ✅ nnz == canonical + duplicates + out_of_range")
    else:
        failed += 1
        print("  ❌ nnz accounting does not close:", rstray.nnz)

    # ── duplicates: density stays in [0,1] where the frozen kernel exceeds it ─
    # A 1x1 with two entries at (0,0). sparse_add concatenates entry lists and nothing
    # coalesces, so the frozen density of that COO is 2.0.
    var one = SparseMatrixCOO(1, 1)
    one.add_entry(0, 0, 2.0)
    var doubled = sparse_add(one, one)
    var dup = csr_from_arrays(
        _ints2(0, 2), _ints2(0, 0), _floats2(2.0, 3.0), 1, 1
    )
    var rdup = sparse_health(dup)
    if (
        sparse_density(doubled) == 2.0
        and rdup.density == 1.0
        and rdup.nnz == 2
        and rdup.nnz_canonical == 1
        and rdup.duplicates == 1
        and rdup.max_abs == 5.0
        and rdup.trace == 5.0
    ):
        passed += 1
        print(
            "  ✅ duplicates summed before measuring: density 1.0 (the frozen kernel"
            " says 2.0) and max_abs 5.0, not 3.0"
        )
    else:
        failed += 1
        print(
            "  ❌ duplicate handling wrong:",
            sparse_density(doubled),
            rdup.density,
            rdup.max_abs,
        )

    # ── a stored zero is stored: coalescing does not prune it ────────────────
    # 5 + (-5) at (0,0) leaves an explicit zero, so row 0 is NOT structurally empty
    # even though it is numerically zero. stored_zeros is how a caller learns that.
    var zeroed = csr_from_arrays(
        _ints3(0, 2, 3), _ints3(0, 0, 1), _floats3(5.0, -5.0, 4.0), 2, 2
    )
    var rzero = sparse_health(zeroed)
    if (
        rzero.nnz_canonical == 2
        and rzero.duplicates == 1
        and rzero.numeric_nnz == 1
        and rzero.stored_zeros == 1
        and rzero.empty_rows == 0
        and not rzero.structurally_singular
        and rzero.min_abs_diag == 0.0
    ):
        passed += 1
        print(
            "  ✅ 5 + (-5) leaves a stored zero: row 0 is not empty, stored_zeros is 1,"
            " and structural singularity is not claimed"
        )
    else:
        failed += 1
        print(
            "  ❌ stored-zero accounting wrong:",
            rzero.numeric_nnz,
            rzero.stored_zeros,
            rzero.empty_rows,
        )

    # ── the two frozen zero-thresholds disagree, and both are reported ───────
    # sv_nnz counts |v| > 1e-30, so 1e-20 is nonzero to it; sparse_from_dense refuses
    # to store anything below 1e-15, so the same value never reaches CSR that way.
    var tiny = csr_from_arrays(_ints2(0, 1), _ints1(0), _floats1(1e-20), 1, 1)
    var rtiny = sparse_health(tiny)
    var tiny_from_dense = sparse_health(csr_from_dense(_floats1(1e-20), 1, 1))
    if (
        sv_nnz(_floats1(1e-20)) == 1
        and rtiny.diagnosed
        and rtiny.numeric_nnz == 1
        and rtiny.stored_zeros == 0
        and tiny_from_dense.nnz == 0
        and DIAG_SV_NNZ_THRESHOLD < DIAG_DENSE_STORE_THRESHOLD
    ):
        passed += 1
        print(
            "  ✅ 1e-20 counts as nonzero (sv_nnz, 1e-30) but is never stored by the"
            " dense builder (1e-15) — both thresholds named"
        )
    else:
        failed += 1
        print("  ❌ threshold reporting wrong:", rtiny.numeric_nnz, tiny_from_dense.nnz)

    # ── a NaN is located, not silently skipped ──────────────────────────────
    # Every max/min loop in the tree loses its comparison against NaN, so a NaN is
    # invisible to sv_max and counts as a zero in sv_nnz.
    var poisoned = csr_from_arrays(
        _ints3(0, 1, 3),
        _ints3(0, 0, 1),
        _floats3(1.0, nan_value, 2.0),
        2,
        2,
    )
    var rnan = sparse_health(poisoned)
    if (
        sv_nnz(_floats1(nan_value)) == 0
        and isnan(sv_max(_floats1(nan_value)))
        and rnan.nonfinite == 1
        and rnan.first_nonfinite_row == 1
        and rnan.first_nonfinite_col == 0
        and not rnan.finite
        and rnan.max_abs == 2.0
        and not isnan(rnan.max_stored)
    ):
        passed += 1
        print(
            "  ✅ the NaN at (1,0) is counted and located; sv_nnz calls it a zero and"
            " sv_max hands it straight back"
        )
    else:
        failed += 1
        print(
            "  ❌ non-finite detection wrong:",
            rnan.nonfinite,
            rnan.first_nonfinite_row,
            rnan.first_nonfinite_col,
        )

    # ── a NaN-bearing matrix is not symmetric and has no inf-norm ───────────
    # Its finite part is symmetric (defect 0.0), which is exactly why the flag must
    # not be derived from the defect alone.
    var nan_norm = sparse_row_norm_inf(poisoned)
    if (
        rnan.symmetry_defect == 0.0
        and not rnan.symmetric
        and rnan.nnz_canonical
        == rnan.numeric_nnz + rnan.stored_zeros + rnan.nonfinite
        and not nan_norm.present
        and nan_norm.status == DIAG_ERR_NON_FINITE
        and rnan.norm_inf == 2.0
    ):
        passed += 1
        print(
            "  ✅ a NaN makes the matrix asymmetric and the inf-norm absent, though the"
            " finite part sums to 2.0"
        )
    else:
        failed += 1
        print("  ❌ NaN symmetry/norm policy wrong:", rnan.symmetric, nan_norm.status)

    # ── mat_condition_number's 1e18 is three failures, not a number ─────────
    var singular_flat = _floats4(1.0, 1.0, 1.0, 1.0)
    var singular = csr_from_dense(singular_flat, 2, 2)
    var singular_cond = sparse_condition_estimate(singular, 8)
    var wide_cond = sparse_condition_estimate(wide, 8)
    var empty_cond = sparse_condition_estimate(empty_00, 8)
    if (
        mat_condition_number(mat_from_list(singular_flat, 2, 2))
        == DIAG_CONDITION_SENTINEL
        and mat_condition_number(mat_from_list(_floats3(1.0, 2.0, 3.0), 1, 3))
        == DIAG_CONDITION_SENTINEL
        and mat_condition_number(mat_from_list(List[Float64](), 0, 0))
        == DIAG_CONDITION_SENTINEL
        and not singular_cond.present
        and singular_cond.status == DIAG_ERR_SINGULAR
        and singular_cond.singular
        and not wide_cond.present
        and wide_cond.status == DIAG_ERR_NOT_SQUARE
        and not empty_cond.present
        and empty_cond.status == DIAG_ERR_EMPTY
    ):
        passed += 1
        print(
            "  ✅ 1e18 split into singular / not_square / empty_matrix — the frozen"
            " estimator returns it for all three"
        )
    else:
        failed += 1
        print(
            "  ❌ condition sentinel not split:",
            singular_cond.status,
            wide_cond.status,
            empty_cond.status,
        )

    # ── structurally singular is a PROOF, not a verdict ─────────────────────
    # [[1,1],[1,1]] has no empty row and no empty column, so the structural test
    # cannot see its singularity. The flag must therefore never be read as
    # "invertible" when False, and the condition estimate is what settles it.
    var rsingular = sparse_health(singular)
    if (
        not rsingular.structurally_singular
        and rsingular.empty_rows == 0
        and rsingular.empty_cols == 0
        and singular_cond.status == DIAG_ERR_SINGULAR
    ):
        passed += 1
        print(
            "  ✅ a singular matrix with no empty row or column is NOT flagged"
            " structurally singular — the flag proves singularity, never rules it out"
        )
    else:
        failed += 1
        print("  ❌ structural singularity over-claimed:", rsingular.structurally_singular)

    # ── a real condition number comes back as a number ──────────────────────
    var identity = csr_from_dense(_floats4(1.0, 0.0, 0.0, 1.0), 2, 2)
    var id_cond = sparse_condition_estimate(identity, 8)
    var big_cond = sparse_condition_estimate(identity, 1)
    var nan_cond = sparse_condition_estimate(poisoned, 8)
    if (
        id_cond.present
        and id_cond.status == CSR_OK
        and id_cond.condition_number == 1.0
        and id_cond.norm_inf == 1.0
        and id_cond.n == 2
        and not id_cond.singular
        and not big_cond.present
        and big_cond.status == DIAG_ERR_TOO_LARGE
        and not nan_cond.present
        and nan_cond.status == DIAG_ERR_NON_FINITE
    ):
        passed += 1
        print(
            "  ✅ the 2x2 identity is perfectly conditioned (1.0); max_n and a NaN are"
            " statuses, not slow paths"
        )
    else:
        failed += 1
        print(
            "  ❌ condition estimate wrong:",
            id_cond.condition_number,
            big_cond.status,
            nan_cond.status,
        )

    # ── the focused predicates and the report cannot disagree ───────────────
    # They delegate to sparse_health precisely so that "an absent diagonal entry is a
    # zero" has one definition rather than five.
    var m_density = sparse_density_checked(gap)
    var m_max_abs = sparse_max_abs(gap)
    var m_max_el = sparse_max_element(gap)
    var m_norm = sparse_row_norm_inf(gap)
    var m_diag = sparse_min_abs_diagonal(gap)
    var m_sym = sparse_symmetry_defect(gap)
    var m_trace = sparse_trace_checked(gap)
    if (
        m_density.present
        and m_density.value == rgap.density
        and m_max_abs.value == rgap.max_abs
        and m_max_el.value == rgap.max_element
        and m_norm.value == rgap.norm_inf
        and m_diag.value == rgap.min_abs_diag
        and m_sym.value == rgap.symmetry_defect
        and m_trace.value == rgap.trace
    ):
        passed += 1
        print("  ✅ every focused predicate returns the report's own field")
    else:
        failed += 1
        print("  ❌ a focused predicate drifted from the report:", m_diag.value)

    # ── a broken indptr yields NO numbers at all ────────────────────────────
    # Not "zeroes for a 2x2": a shape would let a caller who ignored the status read
    # the report as a measurement of a matrix that was never inspected. indptr
    # [0, 5, 1] is both non-monotonic and has the wrong tail; the name proves the
    # ordered checks stop at the first defect rather than at the cheapest one.
    var broken = sparse_health_driver(
        _ints3(0, 5, 1), _ints2(0, 1), _floats2(1.0, 2.0), 2, 2, 1e-10
    )
    if (
        not broken.diagnosed
        and broken.nrows == 0
        and broken.ncols == 0
        and broken.nnz == 0
        and not broken.max_abs_present
        and diag_status_name(broken.status) == "indptr_not_monotonic"
    ):
        passed += 1
        print("  ✅ a non-monotonic indptr produces a status and no measurements")
    else:
        failed += 1
        print(
            "  ❌ broken-indptr report wrong:",
            broken.diagnosed,
            diag_status_name(broken.status),
        )

    # ── status names, including the codes borrowed from csr.mojo ─────────────
    if (
        diag_status_name(CSR_OK) == "ok"
        and diag_status_name(CSR_ERR_INDEX_OUT_OF_RANGE) == "index_out_of_range"
        and diag_status_name(DIAG_ERR_SINGULAR) == "singular"
        and diag_status_name(DIAG_ERR_EMPTY) == "empty_matrix"
        and diag_status_name(DIAG_ERR_TOO_LARGE) == "larger_than_max_n"
        and diag_status_name(DIAG_ERR_NON_FINITE) == "non_finite_values"
        and diag_status_name(999) == "unknown_status"
    ):
        passed += 1
        print("  ✅ diag_status_name covers both code spaces and the unknown code")
    else:
        failed += 1
        print("  ❌ status naming wrong:", diag_status_name(DIAG_ERR_EMPTY))

    # ── the one-line summary names the defects it found ─────────────────────
    var stray_summary = sparse_health_summary_driver(
        _ints3(0, 2, 3), _ints3(0, 7, 1), _floats3(1.0, 9.0, 2.0), 2, 2, 1e-10
    )
    if (
        stray_summary.find("out_of_range=1") >= 0
        and stray_summary.find("index_out_of_range") >= 0
        and stray_summary.find("2x2") >= 0
    ):
        passed += 1
        print("  ✅ the summary names the shape and the defect:", stray_summary)
    else:
        failed += 1
        print("  ❌ summary wrong:", stray_summary)

    # ── a dense entry point, and its shape disagreement ─────────────────────
    var from_dense = sparse_health_from_dense_driver(sym_dense, 3, 3, 1e-10)
    var shape_clash = sparse_health_from_dense_driver(sym_dense, 3, 4, 1e-10)
    if (
        from_dense.diagnosed
        and from_dense.symmetric
        and from_dense.nnz_canonical == 7
        and not shape_clash.diagnosed
        and shape_clash.status == CSR_ERR_INVALID_DIMENSIONS
    ):
        passed += 1
        print("  ✅ the dense entry point agrees, and rejects a shape that is not the data")
    else:
        failed += 1
        print("  ❌ dense driver wrong:", from_dense.nnz_canonical, shape_clash.status)

    # ── the A-Z argument shape: five-element lists, 5 for every Int ─────────
    # This is the exact call the generated suite makes. f(A, rows=5, cols=5) on a
    # five-element list would index A[24] and take the worker process down with it, so
    # every driver is called here in that shape and must return a status instead.
    var _lf5 = List[Float64]()
    _lf5.append(0.5)
    _lf5.append(0.6)
    _lf5.append(0.7)
    _lf5.append(0.4)
    _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1)
    _li5.append(2)
    _li5.append(3)
    _li5.append(4)
    _li5.append(5)

    var az_health = sparse_health_driver(_li5, _li5, _lf5, 5, 5, 0.5)
    var az_dense = sparse_health_from_dense_driver(_lf5, 5, 5, 0.5)
    var az_summary = sparse_health_summary_driver(_li5, _li5, _lf5, 5, 5, 0.5)
    var az_density = sparse_density_driver(_li5, _li5, _lf5, 5, 5)
    var az_trace = sparse_trace_driver(_li5, _li5, _lf5, 5, 5)
    var az_max_abs = sparse_max_abs_driver(_li5, _li5, _lf5, 5, 5)
    var az_max_el = sparse_max_element_driver(_li5, _li5, _lf5, 5, 5)
    var az_norm = sparse_row_norm_inf_driver(_li5, _li5, _lf5, 5, 5)
    var az_diag = sparse_min_abs_diagonal_driver(_li5, _li5, _lf5, 5, 5)
    var az_sym = sparse_symmetry_defect_driver(_li5, _li5, _lf5, 5, 5, 0.5)
    var az_cond = sparse_condition_estimate_driver(_li5, _li5, _lf5, 5, 5, 5)
    if (
        az_health.status == CSR_ERR_INDPTR_LENGTH
        and not az_health.diagnosed
        and az_dense.status == CSR_ERR_INVALID_DIMENSIONS
        and az_summary.find("indptr_length_not_nrows_plus_one") >= 0
        and not az_density.present
        and az_density.status == CSR_ERR_INDPTR_LENGTH
        and not az_trace.present
        and not az_max_abs.present
        and not az_max_el.present
        and not az_norm.present
        and not az_diag.present
        and not az_sym.present
        and not az_cond.present
        and az_cond.status == CSR_ERR_INDPTR_LENGTH
    ):
        passed += 1
        print(
            "  ✅ every driver survives the A-Z shape (5-element lists, every Int 5)"
            " and returns a status"
        )
    else:
        failed += 1
        print(
            "  ❌ a driver mishandled the A-Z shape:",
            az_health.status,
            az_dense.status,
            az_cond.status,
        )

    print("  [sparse_numerics.diagnostics] Passed:", passed, "Failed:", failed)
