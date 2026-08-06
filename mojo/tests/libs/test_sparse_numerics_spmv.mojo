"""test_sparse_numerics_spmv.mojo — known-value tests for the sparse products.

Hand-written. Every assertion targets a failure that is SILENT rather than loud, because
a sparse product that is wrong is still a vector of plausible numbers:

* a dimension mismatch that produces a short-but-believable vector instead of nothing —
  `A^T y` for a 3x4 `A` checked against `ncols` rather than `nrows` accepts a 4-vector
* `sv_dot` on a non-canonical row, which silently returns a too-small answer; both the
  unsorted and the duplicated-index cases are pinned by computing `sv_dot` directly on
  the bad operand and showing it disagrees with the truth
* a Frobenius norm taken over stored values, which is right for a canonical matrix and
  wrong for a duplicate-bearing one (stored 3 and 4 at one coordinate: 5, not 7)
* a running row sum that loses the whole answer to cancellation (0.0 instead of 2.0)
* an SpGEMM whose output is correct but unsorted, which breaks the next `sv_dot`
* an unguarded `indptr[nrows]` on a 5-element list, which is a process crash rather than
  an exception, and is exactly how the generated A-Z suite calls every flat driver

Three frozen kernels are used as differential oracles rather than hand-typed numbers:
`sparse.sparse_matvec` for `A @ x`, `tensor2d.m2_transpose` + `m2_matvec` for `A^T y`,
and `linalg.mat_mul` for `A * B`. Each reaches the answer by densifying, which is the
independent path.
"""
from linalg import mat_from_list, mat_mul
from sparse import sparse_matvec
from sparse_numerics.csr import (
    CSRMatrix,
    CSR_ERR_INDEX_OUT_OF_RANGE,
    CSR_ERR_INDPTR_LENGTH,
    CSR_ERR_INDPTR_NOT_MONOTONIC,
    CSR_ERR_INVALID_DIMENSIONS,
    CSR_ERR_LENGTH_MISMATCH,
    CSR_OK,
    csr_coalesce,
    csr_empty,
    csr_from_arrays,
    csr_to_coo,
    csr_to_dense,
    csr_validate,
)
from sparse_numerics.spmv import (
    SPMV_ERR_NOT_STRICTLY_SORTED,
    SPMV_ERR_SHAPE_MISMATCH,
    spmv_add,
    spmv_add_driver,
    spmv_frobenius_norm,
    spmv_frobenius_norm_driver,
    spmv_matvec,
    spmv_matvec_kahan,
    spmv_matvec_kahan_driver,
    spmv_matvec_transpose,
    spmv_matvec_transpose_driver,
    spmv_row_dot,
    spmv_row_dot_driver,
    spmv_scale,
    spmv_scale_driver,
    spmv_spgemm,
    spmv_spgemm_driver,
    spmv_status_name,
)
from sparse_vector import sv_dot, sv_norm
from tensor2d import m2_from_list, m2_matvec, m2_transpose


# ── list builders (this dialect has no List literal) ───────────────────────────


def _ints(*values: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(values)):
        out.append(values[i])
    return out^


def _floats(*values: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(values)):
        out.append(values[i])
    return out^


def _same_ints(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


def _close(a: Float64, b: Float64) -> Bool:
    var d = a - b
    if d < 0.0:
        d = -d
    return d < 1e-9


def _same_floats(a: List[Float64], b: List[Float64]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not _close(a[i], b[i]):
            return False
    return True


# ── fixtures ──────────────────────────────────────────────────────────────────
# Built with csr_from_arrays on purpose: it sets both flags False even though these
# arrays are canonical, which is the state every matrix arriving over the wire is in.


def _a_3x4() -> CSRMatrix:
    """[[1,0,2,0], [0,3,0,0], [4,0,0,5]] — no duplicates, all indices in range."""
    return csr_from_arrays(
        _ints(0, 2, 3, 5),
        _ints(0, 2, 1, 0, 3),
        _floats(1.0, 2.0, 3.0, 4.0, 5.0),
        3,
        4,
    )


def _a_dense() -> List[Float64]:
    return _floats(
        1.0, 0.0, 2.0, 0.0, 0.0, 3.0, 0.0, 0.0, 4.0, 0.0, 0.0, 5.0
    )


def _b_4x2() -> CSRMatrix:
    """[[1,0], [0,2], [3,0], [0,4]]."""
    return csr_from_arrays(
        _ints(0, 1, 2, 3, 4),
        _ints(0, 1, 0, 1),
        _floats(1.0, 2.0, 3.0, 4.0),
        4,
        2,
    )


def _b_dense() -> List[Float64]:
    return _floats(1.0, 0.0, 0.0, 2.0, 3.0, 0.0, 0.0, 4.0)


def _dup_2x2() -> CSRMatrix:
    """Row 0 stores 3 and 4 at column 0. A legal CSR; the matrix has 7 there."""
    return csr_from_arrays(
        _ints(0, 2, 2),
        _ints(0, 0),
        _floats(3.0, 4.0),
        2,
        2,
    )


def main() raises:
    var passed = 0
    var failed = 0

    var a = _a_3x4()
    var b = _b_4x2()
    var x4 = _floats(1.0, 2.0, 3.0, 4.0)
    var y3 = _floats(1.0, 2.0, 3.0)

    # ── A @ x against the frozen COO oracle ──────────────────────────────────
    # sparse_matvec reaches the same numbers by scattering over COO entries, so an
    # indexing error in the compressed row walk cannot hide behind a hand-typed vector.
    var prod = spmv_matvec(a, x4)
    var oracle_prod = sparse_matvec(csr_to_coo(a), x4)
    var want_prod = _floats(7.0, 6.0, 24.0)
    if (
        prod.status == CSR_OK
        and prod.length == 3
        and _same_floats(prod.values, want_prod)
        and _same_floats(oracle_prod, want_prod)
    ):
        passed += 1
        print("  ✅ A @ x matches the frozen sparse_matvec oracle and [7, 6, 24]")
    else:
        failed += 1
        print("  ❌ A @ x wrong:", prod.status, prod.length)

    # ── A^T y without materialising A^T, against the dense transpose ─────────
    var t_prod = spmv_matvec_transpose(a, y3)
    var dense_t = m2_transpose(m2_from_list(_a_dense(), 3, 4))
    var oracle_t = m2_matvec(dense_t, y3)
    var want_t = _floats(13.0, 6.0, 2.0, 15.0)
    if (
        t_prod.status == CSR_OK
        and t_prod.length == 4
        and _same_floats(t_prod.values, want_t)
        and _same_floats(oracle_t, want_t)
    ):
        passed += 1
        print("  ✅ A^T y equals (dense A^T) y = [13, 6, 2, 15] with no A^T built")
    else:
        failed += 1
        print("  ❌ A^T y wrong:", t_prod.status, t_prod.length)

    # ── the wrong-axis vector is the plausible failure, so it must be empty ──
    # len(x4) == 4 == a.ncols, which is exactly the length a check written against the
    # wrong axis would accept; the output would be a believable 4-vector of nonsense.
    var t_bad = spmv_matvec_transpose(a, x4)
    var mv_bad = spmv_matvec(a, y3)
    var kahan_bad = spmv_matvec_kahan(a, y3)
    if (
        t_bad.status == CSR_ERR_INVALID_DIMENSIONS
        and t_bad.length == 0
        and len(t_bad.values) == 0
        and mv_bad.status == CSR_ERR_INVALID_DIMENSIONS
        and len(mv_bad.values) == 0
        and kahan_bad.status == CSR_ERR_INVALID_DIMENSIONS
        and len(kahan_bad.values) == 0
    ):
        passed += 1
        print("  ✅ a wrong-length vector gives empty + invalid_dimensions, not a short vector")
    else:
        failed += 1
        print("  ❌ dimension mismatch produced a vector:", t_bad.length, mv_bad.length)

    # ── the compensated variant earns its allocation ─────────────────────────
    # Row (1e16, 1, 1, -1e16) against ones: a running sum loses both unit terms to
    # rounding and returns 0.0. The answer is 2.0, and nothing about 0.0 looks wrong.
    var kahan_row = csr_from_arrays(
        _ints(0, 4),
        _ints(0, 1, 2, 3),
        _floats(1.0e16, 1.0, 1.0, -1.0e16),
        1,
        4,
    )
    var ones4 = _floats(1.0, 1.0, 1.0, 1.0)
    var naive = spmv_matvec(kahan_row, ones4)
    var compensated = spmv_matvec_kahan(kahan_row, ones4)
    if (
        naive.status == CSR_OK
        and compensated.status == CSR_OK
        and naive.values[0] == 0.0
        and compensated.values[0] == 2.0
    ):
        passed += 1
        print("  ✅ kahan matvec recovers 2.0 where the running sum returns 0.0")
    else:
        failed += 1
        print("  ❌ kahan matvec:", naive.values[0], compensated.values[0])

    # ── the two matvec variants agree when there is nothing to compensate ────
    var kahan_ok = spmv_matvec_kahan(a, x4)
    if kahan_ok.status == CSR_OK and _same_floats(kahan_ok.values, want_prod):
        passed += 1
        print("  ✅ kahan matvec agrees with the plain product on well-scaled data")
    else:
        failed += 1
        print("  ❌ kahan matvec diverged on well-scaled data")

    # ── row against a sparse vector ──────────────────────────────────────────
    # Row 2 is (col 0 -> 4, col 3 -> 5); b is (0 -> 10, 1 -> 100, 3 -> 1000).
    var idx_b = _ints(0, 1, 3)
    var val_b = _floats(10.0, 100.0, 1000.0)
    var dot = spmv_row_dot(a, 2, idx_b, val_b)
    if dot.status == CSR_OK and _close(dot.value, 5040.0):
        passed += 1
        print("  ✅ row 2 against a sparse vector is 4*10 + 5*1000 = 5040")
    else:
        failed += 1
        print("  ❌ row dot wrong:", dot.status, dot.value)

    # ── sortedness is verified, not read off the flag ─────────────────────────
    # csr_from_arrays sets sorted_indices False for these canonical arrays. Gating on the
    # flag would have rejected the call above, i.e. every matrix from the wire.
    if (not a.sorted_indices) and dot.status == CSR_OK:
        passed += 1
        print("  ✅ a sorted matrix with a False sorted_indices flag is still accepted")
    else:
        failed += 1
        print("  ❌ the flag, not the data, decided admissibility:", a.sorted_indices)

    # ── an unsorted sparse vector is rejected, and sv_dot shows why ───────────
    var idx_rev = _ints(3, 0)
    var val_rev = _floats(1000.0, 10.0)
    var dot_rev = spmv_row_dot(a, 2, idx_rev, val_rev)
    var row2_idx = _ints(0, 3)
    var row2_val = _floats(4.0, 5.0)
    var sv_on_unsorted = sv_dot(row2_idx, row2_val, idx_rev, val_rev)
    if (
        dot_rev.status == SPMV_ERR_NOT_STRICTLY_SORTED
        and dot_rev.value == 0.0
        and _close(sv_on_unsorted, 5000.0)
    ):
        passed += 1
        print("  ✅ unsorted operand rejected; raw sv_dot would return 5000 not 5040")
    else:
        failed += 1
        print("  ❌ unsorted operand:", dot_rev.status, sv_on_unsorted)

    # ── a duplicated index is also inadmissible, for a different reason ───────
    # The row is sorted, so a non-strict check would pass it; sv_dot consumes only the
    # first copy of a repeated index and returns 6 where the matrix says 14.
    var dup = _dup_2x2()
    var idx_one = _ints(0)
    var val_two = _floats(2.0)
    var dot_dup = spmv_row_dot(dup, 0, idx_one, val_two)
    var dup_row_idx = _ints(0, 0)
    var dup_row_val = _floats(3.0, 4.0)
    var sv_on_dup = sv_dot(dup_row_idx, dup_row_val, idx_one, val_two)
    var dot_fixed = spmv_row_dot(csr_coalesce(dup), 0, idx_one, val_two)
    if (
        dot_dup.status == SPMV_ERR_NOT_STRICTLY_SORTED
        and _close(sv_on_dup, 6.0)
        and dot_fixed.status == CSR_OK
        and _close(dot_fixed.value, 14.0)
    ):
        passed += 1
        print("  ✅ duplicate column rejected (sv_dot gives 6); coalesced it gives 14")
    else:
        failed += 1
        print("  ❌ duplicate column:", dot_dup.status, sv_on_dup, dot_fixed.value)

    # ── row dot rejects everything it cannot answer ──────────────────────────
    var dot_row_oob = spmv_row_dot(a, 5, idx_b, val_b)
    var dot_len = spmv_row_dot(a, 2, idx_b, val_two)
    var dot_col_oob = spmv_row_dot(a, 2, _ints(4), val_two)
    if (
        dot_row_oob.status == CSR_ERR_INVALID_DIMENSIONS
        and dot_len.status == CSR_ERR_LENGTH_MISMATCH
        and dot_col_oob.status == CSR_ERR_INDEX_OUT_OF_RANGE
    ):
        passed += 1
        print("  ✅ row dot names its defect: absent row, unpaired arrays, column out of range")
    else:
        failed += 1
        print(
            "  ❌ row dot statuses:",
            dot_row_oob.status,
            dot_len.status,
            dot_col_oob.status,
        )

    # ── SpGEMM against the dense product ────────────────────────────────────
    var c = spmv_spgemm(a, b)
    var dense_c = mat_mul(
        mat_from_list(_a_dense(), 3, 4), mat_from_list(_b_dense(), 4, 2)
    )
    var want_c_indptr = _ints(0, 1, 2, 4)
    var want_c_indices = _ints(0, 1, 0, 1)
    var want_c_values = _floats(7.0, 6.0, 4.0, 20.0)
    if (
        c.nrows == 3
        and c.ncols == 2
        and c.nnz() == 4
        and _same_ints(c.indptr, want_c_indptr)
        and _same_ints(c.indices, want_c_indices)
        and _same_floats(c.values, want_c_values)
        and _same_floats(csr_to_dense(c), dense_c.data)
    ):
        passed += 1
        print("  ✅ A*B matches the dense linalg.mat_mul and stores only 4 of 6 slots")
    else:
        failed += 1
        print("  ❌ A*B wrong:", c.nrows, c.ncols, c.nnz())

    # ── SpGEMM output is sorted, not first-touch order ───────────────────────
    # A2 = [1,1]; B2 stores column 1 in row 0 and column 0 in row 1, so the accumulator
    # touches column 1 before column 0. Unsorted output is a correct matrix that breaks
    # the next sv_dot, which is why the result is passed through csr_sort_indices.
    var a2 = csr_from_arrays(_ints(0, 2), _ints(0, 1), _floats(1.0, 1.0), 1, 2)
    var b2 = csr_from_arrays(
        _ints(0, 1, 2), _ints(1, 0), _floats(5.0, 7.0), 2, 2
    )
    var c2 = spmv_spgemm(a2, b2)
    if (
        c2.sorted_indices
        and c2.coalesced
        and _same_ints(c2.indices, _ints(0, 1))
        and _same_floats(c2.values, _floats(7.0, 5.0))
        and csr_validate(c2) == CSR_OK
    ):
        passed += 1
        print("  ✅ A*B canonicalises a reversed first-touch order into [0, 1]")
    else:
        failed += 1
        print("  ❌ A*B left first-touch order:", c2.sorted_indices, c2.indices[0])

    # ── A + B and the zero it is not allowed to prune ────────────────────────
    var a_plus_a = spmv_add(a, a)
    var want_double = _floats(2.0, 4.0, 6.0, 8.0, 10.0)
    var cancel = csr_from_arrays(
        _ints(0, 1, 1, 1), _ints(0), _floats(-1.0), 3, 4
    )
    var cancelled = spmv_add(a, cancel)
    if (
        a_plus_a.nnz() == 5
        and a_plus_a.is_canonical()
        and _same_floats(a_plus_a.values, want_double)
        and cancelled.nnz() == 5
        and cancelled.values[0] == 0.0
    ):
        passed += 1
        print("  ✅ A+A doubles every value; a cancelling pair leaves a stored zero")
    else:
        failed += 1
        print("  ❌ A+B wrong:", a_plus_a.nnz(), cancelled.nnz())

    # ── scale keeps the pattern, including at alpha = 0 ──────────────────────
    var scaled = spmv_scale(a, 2.5)
    var zeroed = spmv_scale(a, 0.0)
    var dense_scaled = csr_to_dense(scaled)
    var dense_a = csr_to_dense(a)
    var scale_matches = len(dense_scaled) == 12
    for i in range(len(dense_scaled)):
        if not _close(dense_scaled[i], 2.5 * dense_a[i]):
            scale_matches = False
    if (
        scale_matches
        and zeroed.nnz() == 5
        and zeroed.values[4] == 0.0
        and scaled.sorted_indices == a.sorted_indices
        and scaled.coalesced == a.coalesced
    ):
        passed += 1
        print("  ✅ alpha*A scales the dense image and alpha=0 keeps all 5 stored zeros")
    else:
        failed += 1
        print("  ❌ scale wrong:", scale_matches, zeroed.nnz())

    # ── Frobenius norm coalesces first ──────────────────────────────────────
    # This is the whole function: sv_norm squares each STORED value, and squaring is not
    # additive, so the duplicate-bearing matrix would come back 5 instead of 7.
    var norm_a = spmv_frobenius_norm(a)
    var norm_dup = spmv_frobenius_norm(dup)
    var naive_dup = sv_norm(dup.values)
    if (
        norm_a.status == CSR_OK
        and norm_a.value == sv_norm(a.values)
        and _close(norm_a.value, 7.416198487095663)
        and norm_dup.status == CSR_OK
        and _close(norm_dup.value, 7.0)
        and _close(naive_dup, 5.0)
    ):
        passed += 1
        print("  ✅ Frobenius norm is 7 for stored (3,4) at one coordinate, not sv_norm's 5")
    else:
        failed += 1
        print("  ❌ Frobenius norm:", norm_a.value, norm_dup.value, naive_dup)

    # ── a real zero answer and a refused one are different ───────────────────
    var norm_empty = spmv_frobenius_norm(csr_empty(0, 0))
    var norm_zeroed = spmv_frobenius_norm(zeroed)
    var broken = csr_from_arrays(_ints(0, 2, 1), _ints(0), _floats(1.0), 2, 3)
    var norm_broken = spmv_frobenius_norm(broken)
    if (
        norm_empty.status == CSR_OK
        and norm_empty.value == 0.0
        and norm_zeroed.status == CSR_OK
        and norm_zeroed.value == 0.0
        and norm_broken.status == CSR_ERR_INDPTR_NOT_MONOTONIC
        and norm_broken.value == 0.0
    ):
        passed += 1
        print("  ✅ norm 0.0 with ok is an answer; 0.0 with a status is not")
    else:
        failed += 1
        print("  ❌ absent vs zero:", norm_empty.status, norm_broken.status)

    # ── an invalid matrix has no product and no scale ───────────────────────
    var broken_t = spmv_matvec_transpose(broken, _floats(1.0, 2.0))
    var broken_scale = spmv_scale(broken, 2.0)
    var broken_add = spmv_add(a, broken)
    var broken_gemm = spmv_spgemm(broken, b)
    if (
        broken_t.status == CSR_ERR_INDPTR_NOT_MONOTONIC
        and len(broken_t.values) == 0
        and broken_scale.nnz() == 0
        and broken_scale.nrows == 0
        and broken_add.nnz() == 0
        and broken_gemm.nnz() == 0
        and broken_gemm.nrows == 0
    ):
        passed += 1
        print("  ✅ a non-monotonic indptr yields no transpose product, scale, sum or product")
    else:
        failed += 1
        print("  ❌ a broken matrix produced results:", broken_scale.nrows, broken_gemm.nrows)

    # ── operand shapes that cannot combine ──────────────────────────────────
    var gemm_mismatch = spmv_spgemm_driver(
        a.indptr, a.indices, a.values, 3, 4,
        a.indptr, a.indices, a.values, 3, 4,
    )
    var add_mismatch = spmv_add_driver(
        a.indptr, a.indices, a.values, 3, 4,
        b.indptr, b.indices, b.values, 4, 2,
    )
    if (
        gemm_mismatch.status == SPMV_ERR_SHAPE_MISMATCH
        and gemm_mismatch.nnz == 0
        and gemm_mismatch.nrows == 0
        and add_mismatch.status == SPMV_ERR_SHAPE_MISMATCH
        and add_mismatch.nnz == 0
    ):
        passed += 1
        print("  ✅ A*A (4 != 3) and A+B (3x4 vs 4x2) are refused with shape_mismatch")
    else:
        failed += 1
        print("  ❌ shape mismatch:", gemm_mismatch.status, add_mismatch.status)

    # ── drivers agree with the typed path ───────────────────────────────────
    var gemm_driver = spmv_spgemm_driver(
        a.indptr, a.indices, a.values, 3, 4,
        b.indptr, b.indices, b.values, 4, 2,
    )
    var add_driver = spmv_add_driver(
        a.indptr, a.indices, a.values, 3, 4,
        a.indptr, a.indices, a.values, 3, 4,
    )
    var scale_driver = spmv_scale_driver(
        a.indptr, a.indices, a.values, 3, 4, 2.5
    )
    var t_driver = spmv_matvec_transpose_driver(
        a.indptr, a.indices, a.values, 3, 4, y3
    )
    var norm_driver = spmv_frobenius_norm_driver(
        dup.indptr, dup.indices, dup.values, 2, 2
    )
    var dot_driver = spmv_row_dot_driver(
        a.indptr, a.indices, a.values, 3, 4, 2, idx_b, val_b
    )
    var kahan_driver = spmv_matvec_kahan_driver(
        kahan_row.indptr, kahan_row.indices, kahan_row.values, 1, 4, ones4
    )
    if (
        gemm_driver.status == CSR_OK
        and _same_floats(gemm_driver.values, want_c_values)
        and add_driver.status == CSR_OK
        and _same_floats(add_driver.values, want_double)
        and scale_driver.status == CSR_OK
        and scale_driver.nnz == 5
        and t_driver.status == CSR_OK
        and _same_floats(t_driver.values, want_t)
        and norm_driver.status == CSR_OK
        and _close(norm_driver.value, 7.0)
        and dot_driver.status == CSR_OK
        and _close(dot_driver.value, 5040.0)
        and kahan_driver.status == CSR_OK
        and kahan_driver.values[0] == 2.0
    ):
        passed += 1
        print("  ✅ every flat driver reproduces its typed counterpart")
    else:
        failed += 1
        print(
            "  ❌ driver mismatch:",
            gemm_driver.status,
            add_driver.status,
            scale_driver.status,
            t_driver.status,
            norm_driver.status,
            dot_driver.status,
            kahan_driver.status,
        )

    # ── a defective operand's own status reaches the caller ─────────────────
    var add_broken = spmv_add_driver(
        broken.indptr, broken.indices, broken.values, 2, 3,
        a.indptr, a.indices, a.values, 3, 4,
    )
    if (
        add_broken.status == CSR_ERR_INDPTR_NOT_MONOTONIC
        and add_broken.nnz == 0
        and spmv_status_name(SPMV_ERR_NOT_STRICTLY_SORTED)
        == "operand_not_strictly_sorted"
        and spmv_status_name(SPMV_ERR_SHAPE_MISMATCH) == "operand_shape_mismatch"
        and spmv_status_name(CSR_ERR_INDPTR_NOT_MONOTONIC)
        == "indptr_not_monotonic"
        and spmv_status_name(CSR_OK) == "ok"
    ):
        passed += 1
        print("  ✅ the defective operand's status survives, and every code has a name")
    else:
        failed += 1
        print("  ❌ operand status or name:", add_broken.status)

    # ── the A-Z hazard: 5-element lists and 5 for every Int ─────────────────
    # This is verbatim how tests/generate_mojo_tests.py calls a contract function. With
    # nrows = 5 and a 5-element indptr, an unguarded indptr[5] reads past the end, which
    # kills the worker process rather than raising. Reaching the print below at all is
    # the assertion; the statuses confirm the rejection was by the length gate.
    var li5 = _ints(1, 2, 3, 4, 5)
    var lf5 = _floats(0.5, 0.6, 0.7, 0.4, 0.3)
    var g_t = spmv_matvec_transpose_driver(li5, li5, lf5, 5, 5, lf5)
    var g_k = spmv_matvec_kahan_driver(li5, li5, lf5, 5, 5, lf5)
    var g_dot = spmv_row_dot_driver(li5, li5, lf5, 5, 5, 5, li5, lf5)
    var g_norm = spmv_frobenius_norm_driver(li5, li5, lf5, 5, 5)
    var g_scale = spmv_scale_driver(li5, li5, lf5, 5, 5, 0.5)
    var g_add = spmv_add_driver(li5, li5, lf5, 5, 5, li5, li5, lf5, 5, 5)
    var g_gemm = spmv_spgemm_driver(li5, li5, lf5, 5, 5, li5, li5, lf5, 5, 5)
    if (
        g_t.status == CSR_ERR_INDPTR_LENGTH
        and g_k.status == CSR_ERR_INDPTR_LENGTH
        and g_dot.status == CSR_ERR_INDPTR_LENGTH
        and g_norm.status == CSR_ERR_INDPTR_LENGTH
        and g_scale.status == CSR_ERR_INDPTR_LENGTH
        and g_add.status == CSR_ERR_INDPTR_LENGTH
        and g_gemm.status == CSR_ERR_INDPTR_LENGTH
        and len(g_t.values) == 0
        and len(g_gemm.values) == 0
    ):
        passed += 1
        print("  ✅ every driver survives the all-fives sample and rejects it by length")
    else:
        failed += 1
        print(
            "  ❌ all-fives sample:",
            g_t.status,
            g_k.status,
            g_dot.status,
            g_norm.status,
            g_scale.status,
            g_add.status,
            g_gemm.status,
        )

    print("  [sparse_numerics.spmv] Passed:", passed, "Failed:", failed)
