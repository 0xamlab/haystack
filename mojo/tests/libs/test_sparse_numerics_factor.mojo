"""test_sparse_numerics_factor.mojo — known-value tests for the direct sparse solves.

Hand-written. The assertions target the failure this module exists to remove: the frozen
`linalg.mat_solve` returns an all-zeros vector for a singular matrix and an empty list
for a non-square one, so "x = 0" and "there is no x" are the same return value. Several
assertions here are therefore *differential against the frozen kernel* — they check that
`mat_solve` really does hand back a plausible zeros vector on the same input where
`csr_solve` reports `singular`, and that the frozen `back_substitution` really does
return a full-length vector for a triangular system with a dead pivot.

The oracles are all frozen kernels: `mat_solve` for the answer on a well-posed system,
`mat_mul` for the P A = L U identity (which is what catches a wrong permutation
convention — a single row swap is its own inverse, so the 3x3 case here is chosen to
produce a 3-cycle instead), and `mat_solve` on the Gram matrix for the least-squares
answer.

Numbers are hand-computed and asserted exactly wherever the arithmetic is exact in
binary floating point: the 3x3 system factors with a unit L, so its solution is a
division-free back substitution over small integers. Tolerances appear only where a
division genuinely rounds (the 32x32 arrowhead).
"""
from linalg import (
    mat_from_list,
    mat_lu,
    mat_mul,
    mat_solve,
    mat_transpose,
    vec_norm,
)
from matrix_decomp import back_substitution
from sparse_numerics.csr import csr_from_arrays, csr_to_dense
from sparse_numerics.factor import (
    FACTOR_ERR_INVALID_DIMENSIONS,
    FACTOR_ERR_NOT_FACTORED,
    FACTOR_ERR_NOT_SPD,
    FACTOR_ERR_NOT_SQUARE,
    FACTOR_ERR_RANK_DEFICIENT,
    FACTOR_ERR_SINGULAR,
    FACTOR_ERR_STRUCTURE,
    FACTOR_FALLBACK_FILL_IN,
    FACTOR_FALLBACK_NONE,
    FACTOR_FALLBACK_SMALL_SYSTEM,
    FACTOR_FILL_LIMIT_MULTIPLE,
    FACTOR_OK,
    FACTOR_RESIDUAL_ABSENT,
    FACTOR_STRATEGY_CHOLESKY,
    FACTOR_STRATEGY_DENSE_SOLVE,
    FACTOR_STRATEGY_NORMAL_EQUATIONS,
    FACTOR_STRATEGY_SPARSE_LU,
    FACTOR_STRATEGY_TRIVIAL,
    FactorVector,
    SparseLU,
    SparseSolve,
    csr_least_squares,
    csr_lu_factor,
    csr_lu_solve,
    csr_residual,
    csr_solve,
    csr_solve_spd,
    factor_fallback_reason_name,
    factor_status_name,
    factor_strategy_name,
    tri_back_solve,
    tri_forward_solve,
)


fn _ints(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _same_floats(a: List[Float64], b: List[Float64]) -> Bool:
    """Exact equality. Every value compared with this helper is a small integer or a
    dyadic fraction, so a tolerance would hide a genuine mis-accumulation."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    var d = a - b
    if d < 0.0:
        d = -d
    return d <= tol


fn _all_close(a: List[Float64], b: List[Float64], tol: Float64) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not _close(a[i], b[i], tol):
            return False
    return True


# ── the hand-verified 3x3 ─────────────────────────────────────────────────────
# A = [[0, 0, 1],
#      [1, 2, 0],
#      [0, 3, 4]]     nnz = 5, det = 3.
#
# Chosen because partial pivoting on it produces a 3-CYCLE, not a single swap: column 0
# pivots to row 1, then column 1 pivots to what is now row 2, giving perm = [1, 2, 0].
# A permutation that is its own inverse would let a reversed convention (iperm where perm
# belongs) still produce the right answer, so this matrix is what makes the P A = L U
# assertion below meaningful.
#
# With x = [1, 2, 3]:  A x = [3, 5, 18].
# With x = [2, 0, -1]: A x = [-1, 2, -4].


fn _a3_indptr() -> List[Int]:
    return _ints(0, 1, 3, 5)


fn _a3_indices() -> List[Int]:
    return _ints(2, 0, 1, 1, 2)


fn _a3_values() -> List[Float64]:
    return _floats(1.0, 1.0, 2.0, 3.0, 4.0)


fn _a3_dense() -> List[Float64]:
    return _floats(0.0, 0.0, 1.0, 1.0, 2.0, 0.0, 0.0, 3.0, 4.0)


fn main() raises:
    var passed = 0
    var failed = 0

    # ── the permutation is reported, and it is the one the pivoting chose ─────
    var f3 = csr_lu_factor(_a3_indptr(), _a3_indices(), _a3_values(), 3, 3)
    if (
        f3.status == FACTOR_OK
        and not f3.singular
        and f3.n == 3
        and f3.min_pivot == 1.0
        and f3.nnz_input == 5
        and f3.fill_nnz == 0
        and len(f3.perm) == 3
        and f3.perm[0] == 1
        and f3.perm[1] == 2
        and f3.perm[2] == 0
        and f3.iperm[0] == 2
        and f3.iperm[1] == 0
        and f3.iperm[2] == 1
        and f3.is_usable()
    ):
        passed += 1
        print("  ✅ csr_lu_factor reports the 3-cycle permutation and its inverse")
    else:
        failed += 1
        print(
            "  ❌ factor perm wrong:",
            f3.status,
            f3.min_pivot,
            f3.fill_nnz,
            len(f3.perm),
        )

    # iperm must be the inverse of perm, not a second copy of it. Checked as an identity
    # rather than against the literals above so the property is asserted, not the example.
    var inverse_holds = len(f3.iperm) == 3
    if inverse_holds:
        for i in range(3):
            if f3.iperm[f3.perm[i]] != i:
                inverse_holds = False
    if inverse_holds:
        passed += 1
        print("  ✅ iperm[perm[i]] == i")
    else:
        failed += 1
        print("  ❌ iperm is not the inverse of perm")

    # ── P A = L U, verified with the frozen mat_mul ───────────────────────────
    # The permutation convention is the silent failure here: a wrong one still solves a
    # symmetric permutation correctly and only breaks on a cycle.
    var lu_product = mat_mul(
        mat_from_list(f3.lower, 3, 3), mat_from_list(f3.upper, 3, 3)
    )
    var a3d = _a3_dense()
    var permuted = List[Float64]()
    for i in range(3):
        for j in range(3):
            permuted.append(a3d[f3.perm[i] * 3 + j])
    if _same_floats(lu_product.data, permuted):
        passed += 1
        print("  ✅ L @ U == P @ A exactly, with (P A)[i] = A[perm[i]]")
    else:
        failed += 1
        print("  ❌ L @ U != P @ A:", lu_product.data[0], permuted[0])

    # ── the factorisation solves, and agrees with the dense oracle ───────────
    var b1 = _floats(3.0, 5.0, 18.0)
    var b2 = _floats(-1.0, 2.0, -4.0)
    var x1 = csr_lu_solve(f3, b1)
    var oracle1 = mat_solve(mat_from_list(a3d, 3, 3), b1)
    if (
        x1.status == FACTOR_OK
        and x1.strategy == FACTOR_STRATEGY_SPARSE_LU
        and x1.fallback_reason == FACTOR_FALLBACK_NONE
        and not x1.singular
        and _same_floats(x1.x, _floats(1.0, 2.0, 3.0))
        and _same_floats(x1.x, oracle1)
        and x1.residual_norm == 0.0
    ):
        passed += 1
        print("  ✅ csr_lu_solve == [1, 2, 3] == mat_solve, residual exactly 0")
    else:
        failed += 1
        print("  ❌ sparse LU solve wrong:", x1.status, len(x1.x), x1.residual_norm)

    # ── factor once, solve twice == two one-shot solves ──────────────────────
    # This is the entire point of exposing a factorisation, so it is asserted against the
    # independent path rather than against itself.
    var x2 = csr_lu_solve(f3, b2)
    var one1 = csr_solve(_a3_indptr(), _a3_indices(), _a3_values(), 3, 3, b1)
    var one2 = csr_solve(_a3_indptr(), _a3_indices(), _a3_values(), 3, 3, b2)
    if (
        x2.status == FACTOR_OK
        and _same_floats(x2.x, _floats(2.0, 0.0, -1.0))
        and _same_floats(x1.x, one1.x)
        and _same_floats(x2.x, one2.x)
        and one1.status == FACTOR_OK
        and one2.status == FACTOR_OK
    ):
        passed += 1
        print("  ✅ one factorisation, two right-hand sides == two one-shot solves")
    else:
        failed += 1
        print("  ❌ reuse disagrees with one-shot:", x2.status, len(x2.x))

    # ── the small-system fallback is announced, not silent ───────────────────
    if (
        one1.strategy == FACTOR_STRATEGY_DENSE_SOLVE
        and one1.fallback_reason == FACTOR_FALLBACK_SMALL_SYSTEM
        and one1.residual_norm == 0.0
        and factor_strategy_name(one1.strategy) == "dense_mat_solve"
        and factor_fallback_reason_name(one1.fallback_reason)
        == "below_dense_threshold"
    ):
        passed += 1
        print("  ✅ a 3x3 says it used the dense fallback and why")
    else:
        failed += 1
        print(
            "  ❌ fallback not reported:", one1.strategy, one1.fallback_reason
        )

    # ── partial pivoting on a matrix whose first pivot is a structural zero ──
    # A = [[0, 1], [1, 0]], b = [2, 3] -> x = [3, 2]. Without a row swap the first pivot
    # is 0 and the system reads as singular.
    var swap_solve = csr_solve(
        _ints(0, 1, 2), _ints(1, 0), _floats(1.0, 1.0), 2, 2, _floats(2.0, 3.0)
    )
    if (
        swap_solve.status == FACTOR_OK
        and not swap_solve.singular
        and _same_floats(swap_solve.x, _floats(3.0, 2.0))
        and swap_solve.min_pivot == 1.0
    ):
        passed += 1
        print("  ✅ a zero leading pivot is swapped away, not reported singular")
    else:
        failed += 1
        print("  ❌ row swap failed:", swap_solve.status, swap_solve.singular)

    # ── a singular matrix has no solution, and mat_solve says it has one ─────
    # A = [[1, 2], [2, 4]] — row 2 is twice row 1.
    var sing_indptr = _ints(0, 2, 4)
    var sing_indices = _ints(0, 1, 0, 1)
    var sing_values = _floats(1.0, 2.0, 2.0, 4.0)
    var sing_b = _floats(1.0, 2.0)
    var sing = csr_solve(sing_indptr, sing_indices, sing_values, 2, 2, sing_b)
    var frozen_zeros = mat_solve(
        mat_from_list(_floats(1.0, 2.0, 2.0, 4.0), 2, 2), sing_b
    )
    if (
        sing.status == FACTOR_ERR_SINGULAR
        and sing.singular
        and len(sing.x) == 0
        and sing.residual_norm == FACTOR_RESIDUAL_ABSENT
        and factor_status_name(sing.status) == "singular"
        and len(frozen_zeros) == 2
        and frozen_zeros[0] == 0.0
        and frozen_zeros[1] == 0.0
    ):
        passed += 1
        print(
            "  ✅ singular: csr_solve returns no vector where mat_solve returns"
            " two zeros"
        )
    else:
        failed += 1
        print(
            "  ❌ singular handling:",
            sing.status,
            sing.singular,
            len(sing.x),
            len(frozen_zeros),
        )

    # ── a singular factorisation is an error, but keeps its arrays ───────────
    var sing_f = csr_lu_factor(sing_indptr, sing_indices, sing_values, 2, 2)
    var sing_reuse = csr_lu_solve(sing_f, sing_b)
    if (
        sing_f.status == FACTOR_ERR_SINGULAR
        and sing_f.singular
        and sing_f.min_pivot < 1e-15
        and len(sing_f.lower) == 4
        and len(sing_f.upper) == 4
        and not sing_f.is_usable()
        and sing_reuse.status == FACTOR_ERR_SINGULAR
        and sing_reuse.singular
        and len(sing_reuse.x) == 0
    ):
        passed += 1
        print("  ✅ a singular factorisation is unusable but still inspectable")
    else:
        failed += 1
        print(
            "  ❌ singular factor:",
            sing_f.status,
            sing_f.min_pivot,
            len(sing_f.lower),
            sing_reuse.status,
        )

    # ── the residual is small for a good x and large for a perturbed one ─────
    # A @ [1, 2, 4] = [4, 5, 22], so r = [1, 0, 4] and ||r|| = sqrt(17).
    var good_r = csr_residual(
        _a3_indptr(),
        _a3_indices(),
        _a3_values(),
        3,
        3,
        _floats(1.0, 2.0, 3.0),
        b1,
    )
    var bad_r = csr_residual(
        _a3_indptr(),
        _a3_indices(),
        _a3_values(),
        3,
        3,
        _floats(1.0, 2.0, 4.0),
        b1,
    )
    if (
        good_r.status == FACTOR_OK
        and good_r.norm == 0.0
        and bad_r.status == FACTOR_OK
        and _same_floats(bad_r.values, _floats(1.0, 0.0, 4.0))
        and _close(bad_r.norm, 4.123105625617661, 1e-12)
        and bad_r.norm > 4.0
    ):
        passed += 1
        print("  ✅ residual: 0 for the solution, sqrt(17) for x perturbed by 1")
    else:
        failed += 1
        print("  ❌ residual wrong:", good_r.norm, bad_r.norm, bad_r.status)

    # ── the sparse path is actually taken above the threshold ────────────────
    # 20x20 upper bidiagonal: 2 on the diagonal, 1 above it. L is the identity and U is A,
    # so fill-in is exactly 0 and the back substitution is exact: x = 1 everywhere.
    var big_n = 20
    var big_indptr = List[Int]()
    var big_indices = List[Int]()
    var big_values = List[Float64]()
    var big_b = List[Float64]()
    big_indptr.append(0)
    for i in range(big_n):
        big_indices.append(i)
        big_values.append(2.0)
        if i + 1 < big_n:
            big_indices.append(i + 1)
            big_values.append(1.0)
            big_b.append(3.0)
        else:
            big_b.append(2.0)
        big_indptr.append(len(big_values))
    var big = csr_solve(
        big_indptr, big_indices, big_values, big_n, big_n, big_b
    )
    var big_expected = List[Float64]()
    for _ in range(big_n):
        big_expected.append(1.0)
    var big_oracle = mat_solve(
        mat_from_list(
            csr_to_dense(
                csr_from_arrays(
                    big_indptr, big_indices, big_values, big_n, big_n
                )
            ),
            big_n,
            big_n,
        ),
        big_b,
    )
    if (
        big.status == FACTOR_OK
        and big.strategy == FACTOR_STRATEGY_SPARSE_LU
        and big.fallback_reason == FACTOR_FALLBACK_NONE
        and big.fill_nnz == 0
        and big.min_pivot == 2.0
        and _same_floats(big.x, big_expected)
        and _same_floats(big.x, big_oracle)
        and big.residual_norm == 0.0
    ):
        passed += 1
        print("  ✅ a 20x20 bidiagonal uses the sparse LU, zero fill, exact x")
    else:
        failed += 1
        print(
            "  ❌ sparse path not taken:",
            big.status,
            big.strategy,
            big.fill_nnz,
        )

    # ── fill-in above the limit falls back, and says so ──────────────────────
    # 32x32 arrowhead: a dense first row and column. Its LU is completely dense, which is
    # the case the fill-in guard exists for. b = A @ 1 so x = 1 everywhere.
    var arrow_n = 32
    var arrow_indptr = List[Int]()
    var arrow_indices = List[Int]()
    var arrow_values = List[Float64]()
    var arrow_b = List[Float64]()
    arrow_indptr.append(0)
    for j in range(arrow_n):
        arrow_indices.append(j)
        arrow_values.append(1.0)
    arrow_indptr.append(len(arrow_values))
    arrow_b.append(Float64(arrow_n))
    for i in range(1, arrow_n):
        arrow_indices.append(0)
        arrow_values.append(1.0)
        arrow_indices.append(i)
        arrow_values.append(1.0)
        arrow_indptr.append(len(arrow_values))
        arrow_b.append(2.0)
    var arrow_nnz = len(arrow_values)
    var arrow = csr_solve(
        arrow_indptr, arrow_indices, arrow_values, arrow_n, arrow_n, arrow_b
    )
    var arrow_f = csr_lu_factor(
        arrow_indptr, arrow_indices, arrow_values, arrow_n, arrow_n
    )
    var arrow_reuse = csr_lu_solve(arrow_f, arrow_b)
    var arrow_expected = List[Float64]()
    for _ in range(arrow_n):
        arrow_expected.append(1.0)
    if (
        arrow.status == FACTOR_OK
        and arrow.strategy == FACTOR_STRATEGY_DENSE_SOLVE
        and arrow.fallback_reason == FACTOR_FALLBACK_FILL_IN
        and Float64(arrow.fill_nnz)
        > FACTOR_FILL_LIMIT_MULTIPLE * Float64(arrow_nnz)
        and _all_close(arrow.x, arrow_expected, 1e-9)
        and _all_close(arrow_reuse.x, arrow.x, 1e-9)
        and arrow.residual_norm < 1e-9
    ):
        passed += 1
        print(
            "  ✅ a 32x32 arrowhead falls back on fill-in and reports the reason"
        )
    else:
        failed += 1
        print(
            "  ❌ fill-in fallback:",
            arrow.status,
            arrow.strategy,
            arrow.fallback_reason,
            arrow.fill_nnz,
            arrow_nnz,
        )

    # ── triangular substitution, known values ───────────────────────────────
    # L = [[1, 0], [2, 1]], b = [3, 4] -> y = [3, -2].
    # U = [[2, 1], [0, 4]], b = [4, 8] -> x = [1, 2].
    var fwd = tri_forward_solve(
        _floats(1.0, 0.0, 2.0, 1.0), 2, _floats(3.0, 4.0)
    )
    var back = tri_back_solve(
        _floats(2.0, 1.0, 0.0, 4.0), 2, _floats(4.0, 8.0)
    )
    if (
        fwd.status == FACTOR_OK
        and _same_floats(fwd.values, _floats(3.0, -2.0))
        and _close(fwd.norm, vec_norm(fwd.values), 0.0)
        and back.status == FACTOR_OK
        and _same_floats(back.values, _floats(1.0, 2.0))
    ):
        passed += 1
        print("  ✅ forward and back substitution match hand-computed values")
    else:
        failed += 1
        print("  ❌ substitution wrong:", fwd.status, back.status)

    # ── a dead triangular pivot has no solution; the frozen kernel invents one ─
    var dead = _floats(0.0, 1.0, 0.0, 4.0)  # U with U[0][0] = 0
    var dead_back = tri_back_solve(dead, 2, _floats(1.0, 8.0))
    var dead_nested = List[List[Float64]]()
    dead_nested.append(_floats(0.0, 1.0))
    dead_nested.append(_floats(0.0, 4.0))
    var frozen_dead = back_substitution(dead_nested, _floats(1.0, 8.0))
    if (
        dead_back.status == FACTOR_ERR_SINGULAR
        and len(dead_back.values) == 0
        and dead_back.norm == FACTOR_RESIDUAL_ABSENT
        and len(frozen_dead) == 2
        and frozen_dead[0] == 0.0
    ):
        passed += 1
        print(
            "  ✅ a zero diagonal yields no vector where back_substitution"
            " yields x[0] = 0"
        )
    else:
        failed += 1
        print(
            "  ❌ dead pivot:",
            dead_back.status,
            len(dead_back.values),
            len(frozen_dead),
        )

    # ── least squares on an inconsistent overdetermined system ──────────────
    # A = [[1, 0], [1, 1], [1, 2]], b = [0, 0, 3]: fitting a line through three points
    # that are not collinear. AᵀA = [[3, 3], [3, 5]], Aᵀb = [3, 6] -> x = [-0.5, 1.5].
    # A x = [-0.5, 1.0, 2.5], r = [-0.5, 1.0, -0.5], ||r|| = sqrt(1.5).
    var ls_indptr = _ints(0, 1, 3, 5)
    var ls_indices = _ints(0, 0, 1, 0, 1)
    var ls_values = _floats(1.0, 1.0, 1.0, 1.0, 2.0)
    var ls_b = _floats(0.0, 0.0, 3.0)
    var ls = csr_least_squares(ls_indptr, ls_indices, ls_values, 3, 2, ls_b)
    var gram_oracle = mat_solve(
        mat_from_list(_floats(3.0, 3.0, 3.0, 5.0), 2, 2), _floats(3.0, 6.0)
    )
    if (
        ls.status == FACTOR_OK
        and ls.strategy == FACTOR_STRATEGY_NORMAL_EQUATIONS
        and _same_floats(ls.x, _floats(-0.5, 1.5))
        and _all_close(ls.x, gram_oracle, 1e-12)
        and _close(ls.residual_norm, 1.224744871391589, 1e-12)
    ):
        passed += 1
        print("  ✅ least squares == [-0.5, 1.5], residual sqrt(1.5)")
    else:
        failed += 1
        print(
            "  ❌ least squares wrong:",
            ls.status,
            len(ls.x),
            ls.residual_norm,
        )

    # ── a rank-deficient least-squares problem has no unique minimiser ──────
    # A = [[1, 1], [2, 2], [3, 3]]: the two columns are identical, so AᵀA is singular and
    # every point on a line minimises the residual. mat_solve on the same normal
    # equations returns zeros, which is a point that does NOT minimise it.
    var rd = csr_least_squares(
        _ints(0, 2, 4, 6),
        _ints(0, 1, 0, 1, 0, 1),
        _floats(1.0, 1.0, 2.0, 2.0, 3.0, 3.0),
        3,
        2,
        _floats(1.0, 1.0, 1.0),
    )
    var rd_oracle = mat_solve(
        mat_from_list(_floats(14.0, 14.0, 14.0, 14.0), 2, 2),
        _floats(6.0, 6.0),
    )
    if (
        rd.status == FACTOR_ERR_RANK_DEFICIENT
        and len(rd.x) == 0
        and rd.residual_norm == FACTOR_RESIDUAL_ABSENT
        and factor_status_name(rd.status) == "rank_deficient"
        and len(rd_oracle) == 2
        and rd_oracle[0] == 0.0
    ):
        passed += 1
        print("  ✅ rank-deficient least squares returns no vector at all")
    else:
        failed += 1
        print("  ❌ rank deficiency:", rd.status, len(rd.x), len(rd_oracle))

    # ── the SPD path uses the frozen Cholesky and agrees with mat_solve ──────
    # A = [[4, 2], [2, 3]], b = [10, 5] -> x = [2.5, 0]. L = [[2, 0], [1, sqrt(2)]].
    var spd_indptr = _ints(0, 2, 4)
    var spd_indices = _ints(0, 1, 0, 1)
    var spd_values = _floats(4.0, 2.0, 2.0, 3.0)
    var spd_b = _floats(10.0, 5.0)
    var spd = csr_solve_spd(spd_indptr, spd_indices, spd_values, 2, 2, spd_b)
    var spd_oracle = mat_solve(
        mat_from_list(_floats(4.0, 2.0, 2.0, 3.0), 2, 2), spd_b
    )
    if (
        spd.status == FACTOR_OK
        and spd.strategy == FACTOR_STRATEGY_CHOLESKY
        and _same_floats(spd.x, _floats(2.5, 0.0))
        and _all_close(spd.x, spd_oracle, 1e-12)
        and spd.residual_norm == 0.0
    ):
        passed += 1
        print("  ✅ csr_solve_spd == [2.5, 0] == mat_solve, residual 0")
    else:
        failed += 1
        print("  ❌ SPD solve:", spd.status, len(spd.x), spd.residual_norm)

    # ── not-SPD is refused, and is not the same claim as singular ────────────
    # [[0, 1], [1, 0]] is symmetric, indefinite and perfectly invertible: the Cholesky
    # path must refuse it while the LU path solves it.
    var indef = csr_solve_spd(
        _ints(0, 1, 2), _ints(1, 0), _floats(1.0, 1.0), 2, 2, _floats(2.0, 3.0)
    )
    var asym = csr_solve_spd(
        _a3_indptr(), _a3_indices(), _a3_values(), 3, 3, b1
    )
    if (
        indef.status == FACTOR_ERR_NOT_SPD
        and not indef.singular
        and len(indef.x) == 0
        and asym.status == FACTOR_ERR_NOT_SPD
        and not asym.singular
        and factor_status_name(asym.status)
        == "not_symmetric_positive_definite"
        and swap_solve.status == FACTOR_OK
    ):
        passed += 1
        print("  ✅ indefinite and asymmetric are not_spd, and not singular")
    else:
        failed += 1
        print("  ❌ SPD gate:", indef.status, indef.singular, asym.status)

    # ── non-square and length mismatches are named, not merged ───────────────
    # mat_solve returns an empty list for both, so a caller cannot tell which argument to
    # fix; these two statuses are the difference.
    var not_sq = csr_solve(
        _ints(0, 1, 2), _ints(0, 2), _floats(1.0, 1.0), 2, 3, _floats(1.0, 1.0)
    )
    var bad_b = csr_solve(
        _ints(0, 1, 2), _ints(1, 0), _floats(1.0, 1.0), 2, 2, _floats(1.0)
    )
    if (
        not_sq.status == FACTOR_ERR_NOT_SQUARE
        and len(not_sq.x) == 0
        and bad_b.status == FACTOR_ERR_INVALID_DIMENSIONS
        and len(bad_b.x) == 0
        and factor_status_name(not_sq.status) == "not_square"
    ):
        passed += 1
        print("  ✅ non-square and wrong-length b get distinct statuses")
    else:
        failed += 1
        print("  ❌ shape statuses:", not_sq.status, bad_b.status)

    # ── the all-fives contract call must be rejected, not indexed ────────────
    # The generated A-Z suite calls every contract function with a 5-element list and 5
    # for every Int. Reading past the end of a List is an uncatchable process crash, so
    # these four calls are the guard that keeps this module from killing the worker.
    var five_i = _ints(1, 2, 3, 4, 5)
    var five_f = _floats(0.5, 0.6, 0.7, 0.4, 0.3)
    var fives_solve = csr_solve(five_i, five_i, five_f, 5, 5, five_f)
    var fives_factor = csr_lu_factor(five_i, five_i, five_f, 5, 5)
    var fives_resid = csr_residual(five_i, five_i, five_f, 5, 5, five_f, five_f)
    var fives_tri = tri_forward_solve(five_f, 5, five_f)
    var fives_back = tri_back_solve(five_f, 5, five_f)
    var fives_ls = csr_least_squares(five_i, five_i, five_f, 5, 5, five_f)
    var fives_spd = csr_solve_spd(five_i, five_i, five_f, 5, 5, five_f)
    if (
        fives_solve.status == FACTOR_ERR_STRUCTURE
        and len(fives_solve.x) == 0
        and fives_factor.status == FACTOR_ERR_STRUCTURE
        and not fives_factor.singular
        and fives_resid.status == FACTOR_ERR_STRUCTURE
        and fives_tri.status == FACTOR_ERR_INVALID_DIMENSIONS
        and fives_back.status == FACTOR_ERR_INVALID_DIMENSIONS
        and fives_ls.status == FACTOR_ERR_STRUCTURE
        and fives_spd.status == FACTOR_ERR_STRUCTURE
    ):
        passed += 1
        print("  ✅ five-element lists with n = 5 are rejected, not indexed")
    else:
        failed += 1
        print(
            "  ❌ all-fives guard:",
            fives_solve.status,
            fives_factor.status,
            fives_tri.status,
            fives_ls.status,
        )

    # ── a factorisation arriving from the wire is dimension-checked ──────────
    # SparseLU is @fieldwise_init, so the generated dispatch can build one with arrays
    # that do not match its n. Substituting through it would index past the end.
    var forged = SparseLU(
        FACTOR_OK,
        3,
        False,
        1.0,
        3,
        0,
        _floats(1.0),
        _floats(1.0),
        _ints(0),
        _ints(0),
        _ints(0, 1, 2, 3),
        _ints(0, 0, 0),
        _floats(1.0, 1.0, 1.0),
    )
    var forged_solve = csr_lu_solve(forged, _floats(1.0, 2.0, 3.0))
    if (
        not forged.is_usable()
        and forged_solve.status == FACTOR_ERR_NOT_FACTORED
        and len(forged_solve.x) == 0
        and factor_status_name(forged_solve.status) == "not_factored"
    ):
        passed += 1
        print("  ✅ a SparseLU whose triangles do not match n is refused")
    else:
        failed += 1
        print("  ❌ forged factorisation accepted:", forged_solve.status)

    # ── the empty system has an answer; a rejected one does not ──────────────
    # 0 unknowns is a real solution (the empty vector, residual 0), which is why it is
    # FACTOR_OK with a TRIVIAL strategy rather than an error. Least squares with no
    # columns has the same shape of answer, and its residual is ||b||.
    var trivial = csr_solve(
        _ints(0), List[Int](), List[Float64](), 0, 0, List[Float64]()
    )
    var no_cols = csr_least_squares(
        _ints(0, 0, 0), List[Int](), List[Float64](), 2, 0, _floats(3.0, 4.0)
    )
    if (
        trivial.status == FACTOR_OK
        and trivial.strategy == FACTOR_STRATEGY_TRIVIAL
        and len(trivial.x) == 0
        and trivial.residual_norm == 0.0
        and no_cols.status == FACTOR_OK
        and len(no_cols.x) == 0
        and no_cols.residual_norm == 5.0
    ):
        passed += 1
        print("  ✅ the 0-unknown system solves; the 0-column fit reports ||b||")
    else:
        failed += 1
        print(
            "  ❌ empty system:",
            trivial.status,
            trivial.residual_norm,
            no_cols.status,
            no_cols.residual_norm,
        )

    print("  [sparse_numerics.factor] Passed:", passed, "Failed:", failed)
