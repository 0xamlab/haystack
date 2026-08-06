"""test_sparse_numerics_iterative.mojo — known-value tests for the Krylov solvers.

Hand-written. The assertions target the failure this module exists to prevent: a solver
that returns a vector which is not a solution, with nothing in the reply to say so. So
every status is asserted, not just the numbers, and in particular:

* a CG that hits its iteration cap reports `iteration_limit` with `converged == False`
* a matrix that is not symmetric is rejected before any iteration happens
* an indefinite matrix produces `curvature_breakdown` and **no** iterate
* a zero right-hand side produces x == 0 and a clean status, with no division

The 1D Laplacian is the SPD fixture because its solution for b = 1 is known in closed
form (x_i = (i+1)(n-i)/2), so the numbers here are hand-computed rather than captured
from a run; the frozen dense `linalg.mat_solve` is used as a second, independent oracle
on the same system, and `sparse_numerics.csr.csr_to_dense` builds the dense image it
consumes. For least squares the normal equations are solved by hand *and* by `mat_solve`
on the 2x2 system, and the assertion that matters is that the exact answer has a large
`residual_norm` and a zero `normal_residual_norm` at the same time.
"""
from std.math import isinf, isnan, sqrt

from linalg import mat_from_list, mat_solve, vec_norm
from sparse_numerics.csr import (
    CSRMatrix,
    CSR_OK,
    csr_from_arrays,
    csr_from_dense,
    csr_matvec,
    csr_to_dense,
    csr_validate,
)
from sparse_numerics.iterative import (
    ITER_CONVERGED,
    ITER_CURVATURE_BREAKDOWN,
    ITER_INVALID_CSR,
    ITER_INVALID_PARAMETER,
    ITER_ITERATION_LIMIT,
    ITER_KRYLOV_BREAKDOWN,
    ITER_NON_FINITE,
    ITER_NOT_SYMMETRIC,
    ITER_OK,
    ITER_SHAPE_MISMATCH,
    ITER_ZERO_DIAGONAL,
    ITER_ZERO_RHS,
    IterativeResult,
    IterativeVectorResult,
    LeastSquaresResult,
    PRECOND_JACOBI,
    PRECOND_NONE,
    PRECOND_SGS,
    SymmetryResult,
    csr_cg,
    csr_cg_driver,
    csr_cgls,
    csr_cgls_driver,
    csr_diagonal,
    csr_gmres,
    csr_gmres_driver,
    csr_is_symmetric,
    csr_jacobi_inverse,
    csr_pcg,
    csr_pcg_driver,
    csr_sgs_apply,
    csr_symmetry,
    iter_status_name,
)


# ── builders (List has no `+`, and List[Int](3) is not a one-element list) ─────


def _ints(a: Int, b: Int, c: Int) -> List[Int]:
    var out = List[Int]()
    out.append(a)
    out.append(b)
    out.append(c)
    return out^


def _ints2(a: Int, b: Int) -> List[Int]:
    var out = List[Int]()
    out.append(a)
    out.append(b)
    return out^


def _five_ints() -> List[Int]:
    """The generated A-Z suite's sample List[Int]: 1..5. Not a valid indptr."""
    var out = List[Int]()
    for i in range(5):
        out.append(i + 1)
    return out^


def _five_floats() -> List[Float64]:
    var out = List[Float64]()
    out.append(0.5)
    out.append(0.6)
    out.append(0.7)
    out.append(0.4)
    out.append(0.3)
    return out^


def _ones(n: Int) -> List[Float64]:
    var out = List[Float64]()
    for _ in range(n):
        out.append(1.0)
    return out^


def _zeros(n: Int) -> List[Float64]:
    var out = List[Float64]()
    for _ in range(n):
        out.append(0.0)
    return out^


def _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    var d = a - b
    if d < 0.0:
        d = -d
    return d <= tol


def _vec_close(a: List[Float64], b: List[Float64], tol: Float64) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not _close(a[i], b[i], tol):
            return False
    return True


def _laplacian(n: Int) -> CSRMatrix:
    """1D Dirichlet Laplacian: 2 on the diagonal, -1 either side. SPD for every n."""
    var indptr = List[Int]()
    var indices = List[Int]()
    var values = List[Float64]()
    indptr.append(0)
    for i in range(n):
        if i > 0:
            indices.append(i - 1)
            values.append(-1.0)
        indices.append(i)
        values.append(2.0)
        if i < n - 1:
            indices.append(i + 1)
            values.append(-1.0)
        indptr.append(len(values))
    return csr_from_arrays(indptr, indices, values, n, n)


def _laplacian_exact(n: Int) -> List[Float64]:
    """Solution of L x = 1: x_i = (i+1)(n-i)/2. For n=5: [2.5, 4, 4.5, 4, 2.5]."""
    var out = List[Float64]()
    for i in range(n):
        out.append(Float64((i + 1) * (n - i)) / 2.0)
    return out^


def _dense_solve(m: CSRMatrix, b: List[Float64]) -> List[Float64]:
    """The frozen dense oracle: Gaussian elimination on the dense image of m."""
    var dense = csr_to_dense(m)
    var a = mat_from_list(dense, m.nrows, m.ncols)
    return mat_solve(a, b)


def _nonsymmetric() -> CSRMatrix:
    """[[2,1,0],[0,3,1],[1,0,4]]. 2x+y=1, 3y+z=2, x+4z=3 -> x=[0.28,0.44,0.68]."""
    var dense = List[Float64]()
    dense.append(2.0)
    dense.append(1.0)
    dense.append(0.0)
    dense.append(0.0)
    dense.append(3.0)
    dense.append(1.0)
    dense.append(1.0)
    dense.append(0.0)
    dense.append(4.0)
    return csr_from_dense(dense, 3, 3)


def _indefinite() -> CSRMatrix:
    """[[1,2],[2,1]] — symmetric, eigenvalues 3 and -1, so not positive definite."""
    var dense = List[Float64]()
    dense.append(1.0)
    dense.append(2.0)
    dense.append(2.0)
    dense.append(1.0)
    return csr_from_dense(dense, 2, 2)


def _design() -> CSRMatrix:
    """[[1,0],[1,1],[1,2]] — the design matrix of a straight-line fit, 3x2."""
    var dense = List[Float64]()
    dense.append(1.0)
    dense.append(0.0)
    dense.append(1.0)
    dense.append(1.0)
    dense.append(1.0)
    dense.append(2.0)
    return csr_from_dense(dense, 3, 2)


def _sgs_operator_apply(
    m: CSRMatrix, z: List[Float64]
) -> List[Float64]:
    """M z for M = (D+L) D^-1 (D+U), from the dense image — the differential oracle.

    Built the long way round on purpose: `csr_sgs_apply` claims to invert this operator,
    and the only way to check an inverse is to apply the forward operator and land back
    on the input. A tolerance check against a hand-typed vector would not catch the two
    substitutions being inverses of the *wrong* split.
    """
    var n = m.nrows
    var a = csr_to_dense(m)
    var upper = _zeros(n)
    for i in range(n):
        var acc = 0.0
        for j in range(i, n):
            acc += a[i * n + j] * z[j]
        upper[i] = acc
    var scaled = _zeros(n)
    for i in range(n):
        scaled[i] = upper[i] / a[i * n + i]
    var out = _zeros(n)
    for i in range(n):
        var acc = 0.0
        for j in range(i + 1):
            acc += a[i * n + j] * scaled[j]
        out[i] = acc
    return out^


def _twos() -> List[Float64]:
    var out = List[Float64]()
    for _ in range(5):
        out.append(2.0)
    return out^


def _twos_2() -> List[Float64]:
    var out = List[Float64]()
    out.append(2.0)
    out.append(2.0)
    return out^


def _laplacian_zero_row() -> List[Float64]:
    """Values for [[2, 0], [0, 3]] stored as (0,0)=2, (0,1)=0 explicitly, (1,1)=3.

    The explicit zero at (0,1) has no counterpart stored at (1,0), which is the
    structural asymmetry the symmetry test must see through.
    """
    var out = List[Float64]()
    out.append(2.0)
    out.append(0.0)
    out.append(3.0)
    return out^


def main() raises:
    var passed = 0
    var failed = 0

    var lap = _laplacian(5)
    var ones5 = _ones(5)
    var exact5 = _laplacian_exact(5)

    # ── the fixture itself, before anything is asserted about the solvers ──────
    # If the Laplacian were mis-assembled every number below would be measured against
    # the wrong system, and the differential oracles would agree with each other on it.
    var lap_check = csr_matvec(lap, exact5)
    if (
        csr_validate(lap) == CSR_OK
        and lap_check.status == CSR_OK
        and _vec_close(lap_check.values, ones5, 1e-12)
    ):
        passed += 1
        print("  ✅ fixture: L @ [2.5,4,4.5,4,2.5] == [1,1,1,1,1] exactly")
    else:
        failed += 1
        print("  ❌ fixture Laplacian is wrong:", csr_validate(lap))

    # ── CG on an SPD system: hand-computed answer and the dense oracle ─────────
    var cg = csr_cg(lap, ones5, 1e-12, 100)
    if (
        cg.status == ITER_CONVERGED
        and cg.converged
        and not cg.breakdown
        and _vec_close(cg.x, exact5, 1e-9)
    ):
        passed += 1
        print("  ✅ CG matches the closed-form Laplacian solution")
    else:
        failed += 1
        print("  ❌ CG solution wrong:", iter_status_name(cg.status), len(cg.x))

    var dense_x = _dense_solve(lap, ones5)
    if len(dense_x) == 5 and _vec_close(cg.x, dense_x, 1e-9):
        passed += 1
        print("  ✅ CG agrees with the frozen dense mat_solve on the same system")
    else:
        failed += 1
        print("  ❌ CG disagrees with mat_solve:", len(dense_x))

    # CG on an n x n SPD system converges in at most n iterations in exact arithmetic;
    # a solver that needed more would be accumulating error somewhere.
    if cg.iterations >= 1 and cg.iterations <= 5:
        passed += 1
        print("  ✅ CG converged in", cg.iterations, "iterations (n = 5)")
    else:
        failed += 1
        print("  ❌ CG took", cg.iterations, "iterations for n = 5")

    # The reported residual must be the residual of the vector actually returned.
    var cg_resid = csr_matvec(lap, cg.x)
    var true_r = _zeros(5)
    for i in range(5):
        true_r[i] = ones5[i] - cg_resid.values[i]
    if (
        _close(cg.residual_norm, vec_norm(true_r), 1e-15)
        and _close(cg.rhs_norm, vec_norm(ones5), 1e-15)
        and _close(cg.relative_residual, cg.residual_norm / cg.rhs_norm, 1e-15)
    ):
        passed += 1
        print("  ✅ reported residual is ||b - A x|| of the returned x")
    else:
        failed += 1
        print("  ❌ reported residual is not the true one:", cg.residual_norm)

    # ── one loop serves CG and PCG, and the suite proves it ───────────────────
    var pcg_none = csr_pcg(lap, ones5, 1e-12, 100, PRECOND_NONE)
    var identical = pcg_none.iterations == cg.iterations
    if identical:
        for i in range(5):
            if pcg_none.x[i] != cg.x[i]:
                identical = False
    if identical and pcg_none.status == ITER_CONVERGED:
        passed += 1
        print("  ✅ PCG with the identity preconditioner is bit-identical to CG")
    else:
        failed += 1
        print("  ❌ PCG(NONE) differs from CG:", pcg_none.iterations, cg.iterations)

    # diag(L) = 2I, a scalar multiple of the identity, and CG is invariant under a
    # scalar preconditioner — so Jacobi must take the same number of iterations here.
    var pcg_jac = csr_pcg(lap, ones5, 1e-12, 100, PRECOND_JACOBI)
    if (
        pcg_jac.status == ITER_CONVERGED
        and pcg_jac.iterations == cg.iterations
        and _vec_close(pcg_jac.x, exact5, 1e-9)
    ):
        passed += 1
        print("  ✅ Jacobi PCG converges in the same count (D = 2I is a scalar)")
    else:
        failed += 1
        print("  ❌ Jacobi PCG:", iter_status_name(pcg_jac.status), pcg_jac.iterations)

    # Deliberately NOT asserted: that SGS takes fewer iterations than plain CG. It does
    # not, at this size — measured 5 against 3 here, because b = 1 excites only half the
    # spectrum of L so the unpreconditioned Krylov space reaches the answer in ~n/2
    # steps, and preconditioning destroys exactly that structure. The acceleration is
    # real but asymptotic (measured n=300 with a non-symmetric rhs: 304 steps
    # unpreconditioned against 123 with SGS). What IS guaranteed at every size is
    # termination within n steps and agreement with the same solution, so that is what
    # this asserts — an iteration-count assertion here would be asserting a coincidence.
    var pcg_sgs = csr_pcg(lap, ones5, 1e-12, 100, PRECOND_SGS)
    if (
        pcg_sgs.status == ITER_CONVERGED
        and pcg_sgs.converged
        and _vec_close(pcg_sgs.x, exact5, 1e-9)
        and pcg_sgs.iterations <= 5
        and pcg_sgs.relative_residual <= 1e-12
    ):
        passed += 1
        print("  ✅ SGS PCG converges to the same solution in", pcg_sgs.iterations)
    else:
        failed += 1
        print("  ❌ SGS PCG:", iter_status_name(pcg_sgs.status), pcg_sgs.iterations)

    # ── the failure this file exists to prevent ───────────────────────────────
    # One CG step on this system is hand-computable: p = b, A p = [1,0,0,0,1],
    # p^T A p = 2, r^T r = 5, so alpha = 2.5 and x = [2.5]*5. The true residual is then
    # [-1.5,1,1,1,-1.5] with norm sqrt(7.5), i.e. a *relative* residual of sqrt(1.5) —
    # larger than 1, because CG minimises the A-norm of the error and not the residual.
    # An implementation that reported the recursive residual, or that clamped the ratio,
    # would miss this.
    var capped = csr_cg(lap, ones5, 1e-12, 1)
    var first_step = _zeros(5)
    for i in range(5):
        first_step[i] = 2.5
    if (
        capped.status == ITER_ITERATION_LIMIT
        and not capped.converged
        and not capped.breakdown
        and capped.iterations == 1
        and len(capped.x) == 5
        and _vec_close(capped.x, first_step, 1e-15)
        and not _vec_close(capped.x, exact5, 1e-3)
        and _close(capped.residual_norm, sqrt(7.5), 1e-14)
        and _close(capped.relative_residual, sqrt(1.5), 1e-14)
    ):
        passed += 1
        print("  ✅ a 1-iteration cap reports iteration_limit with converged == False")
    else:
        failed += 1
        print(
            "  ❌ capped CG lied:",
            iter_status_name(capped.status),
            capped.converged,
            capped.relative_residual,
        )

    # A zero budget is not an error, but it is certainly not convergence.
    var zero_budget = csr_cg(lap, ones5, 1e-12, 0)
    if (
        zero_budget.status == ITER_ITERATION_LIMIT
        and not zero_budget.converged
        and zero_budget.iterations == 0
        and _close(zero_budget.relative_residual, 1.0, 1e-15)
    ):
        passed += 1
        print("  ✅ max_iter = 0 returns x = 0 with relative residual 1.0")
    else:
        failed += 1
        print("  ❌ max_iter = 0:", iter_status_name(zero_budget.status))

    # ── a non-symmetric matrix is rejected, not iterated ─────────────────────
    var nonsym = _nonsymmetric()
    var b3 = List[Float64]()
    b3.append(1.0)
    b3.append(2.0)
    b3.append(3.0)
    var cg_nonsym = csr_cg(nonsym, b3, 1e-12, 100)
    if (
        cg_nonsym.status == ITER_NOT_SYMMETRIC
        and not cg_nonsym.converged
        and cg_nonsym.iterations == 0
        and len(cg_nonsym.x) == 0
    ):
        passed += 1
        print("  ✅ CG reports not_symmetric with no iterate at all")
    else:
        failed += 1
        print(
            "  ❌ CG accepted a non-symmetric matrix:",
            iter_status_name(cg_nonsym.status),
            cg_nonsym.iterations,
        )

    # ── an indefinite matrix breaks down on curvature ────────────────────────
    # [[1,2],[2,1]] with b = [1,0]: iteration 1 has p^T A p = 1 > 0, iteration 2 has
    # p = [4,-2] and p^T A p = -12, which is the proof that A is not SPD.
    var indef = _indefinite()
    var b2 = List[Float64]()
    b2.append(1.0)
    b2.append(0.0)
    var cg_indef = csr_cg(indef, b2, 1e-12, 100)
    if (
        cg_indef.status == ITER_CURVATURE_BREAKDOWN
        and cg_indef.breakdown
        and not cg_indef.converged
        and len(cg_indef.x) == 0
    ):
        passed += 1
        print("  ✅ an indefinite matrix reports curvature_breakdown, x absent")
    else:
        failed += 1
        print(
            "  ❌ indefinite CG:",
            iter_status_name(cg_indef.status),
            cg_indef.breakdown,
            len(cg_indef.x),
        )

    # The matrix is symmetric, so the rejection above came from the curvature test and
    # not from the symmetry gate — otherwise the test would prove nothing about it.
    if csr_is_symmetric(indef):
        passed += 1
        print("  ✅ the indefinite fixture is symmetric, so the gate it hit is curvature")
    else:
        failed += 1
        print("  ❌ the indefinite fixture is not symmetric — wrong gate")

    # ── a zero right-hand side ───────────────────────────────────────────────
    var zero_rhs = csr_cg(lap, _zeros(5), 1e-12, 100)
    if (
        zero_rhs.status == ITER_ZERO_RHS
        and zero_rhs.converged
        and not zero_rhs.breakdown
        and zero_rhs.iterations == 0
        and _vec_close(zero_rhs.x, _zeros(5), 0.0)
        and zero_rhs.residual_norm == 0.0
        and zero_rhs.relative_residual == 0.0
        and not isnan(zero_rhs.relative_residual)
    ):
        passed += 1
        print("  ✅ a zero rhs gives x == 0, zero_rhs status, and no 0/0")
    else:
        failed += 1
        print(
            "  ❌ zero rhs:",
            iter_status_name(zero_rhs.status),
            zero_rhs.relative_residual,
        )

    var zero_rhs_gmres = csr_gmres(lap, _zeros(5), 1e-12, 100, 30)
    var zero_rhs_ls = csr_cgls(_design(), _zeros(3), 1e-12, 100)
    if (
        zero_rhs_gmres.status == ITER_ZERO_RHS
        and _vec_close(zero_rhs_gmres.x, _zeros(5), 0.0)
        and zero_rhs_ls.status == ITER_ZERO_RHS
        and len(zero_rhs_ls.x) == 2
        and _vec_close(zero_rhs_ls.x, _zeros(2), 0.0)
    ):
        passed += 1
        print("  ✅ GMRES and CGLS handle a zero rhs the same way")
    else:
        failed += 1
        print(
            "  ❌ zero rhs elsewhere:",
            iter_status_name(zero_rhs_gmres.status),
            iter_status_name(zero_rhs_ls.status),
        )

    # ── GMRES on a nonsymmetric system ───────────────────────────────────────
    # Hand solution of 2x+y=1, 3y+z=2, x+4z=3 is [7/25, 11/25, 17/25].
    var nonsym_exact = List[Float64]()
    nonsym_exact.append(0.28)
    nonsym_exact.append(0.44)
    nonsym_exact.append(0.68)
    var gm = csr_gmres(nonsym, b3, 1e-12, 100, 30)
    var nonsym_dense_x = _dense_solve(nonsym, b3)
    if (
        gm.status == ITER_CONVERGED
        and gm.converged
        and not gm.breakdown
        and _vec_close(gm.x, nonsym_exact, 1e-10)
        and _vec_close(gm.x, nonsym_dense_x, 1e-10)
        and gm.iterations <= 3
    ):
        passed += 1
        print("  ✅ GMRES matches the hand solution and mat_solve in", gm.iterations)
    else:
        failed += 1
        print(
            "  ❌ GMRES nonsymmetric:",
            iter_status_name(gm.status),
            gm.iterations,
            len(gm.x),
        )

    # restart = 1 exercises the outer restart loop: no single Krylov step can solve
    # this, so convergence proves the cycles compose.
    var gm1 = csr_gmres(nonsym, b3, 1e-12, 500, 1)
    if (
        gm1.status == ITER_CONVERGED
        and gm1.converged
        and _vec_close(gm1.x, nonsym_exact, 1e-9)
        and gm1.iterations > 3
    ):
        passed += 1
        print("  ✅ GMRES(1) still converges, in", gm1.iterations, "restarted steps")
    else:
        failed += 1
        print("  ❌ GMRES(1):", iter_status_name(gm1.status), gm1.iterations)

    # Two different Krylov methods on the same SPD system must land on the same point.
    var gm_spd = csr_gmres(lap, ones5, 1e-12, 100, 30)
    if gm_spd.status == ITER_CONVERGED and _vec_close(gm_spd.x, cg.x, 1e-8):
        passed += 1
        print("  ✅ GMRES and CG agree on the SPD system")
    else:
        failed += 1
        print("  ❌ GMRES/CG disagree:", iter_status_name(gm_spd.status))

    var gm_capped = csr_gmres(lap, ones5, 1e-12, 1, 30)
    if (
        gm_capped.status == ITER_ITERATION_LIMIT
        and not gm_capped.converged
        and gm_capped.iterations == 1
        and len(gm_capped.x) == 5
    ):
        passed += 1
        print("  ✅ GMRES honours its cap and says iteration_limit")
    else:
        failed += 1
        print(
            "  ❌ capped GMRES:",
            iter_status_name(gm_capped.status),
            gm_capped.iterations,
        )

    # ── a singular system has no solution, and says so ───────────────────────
    # A = [[1,1],[1,1]] with b = [1,0]: b is not in the range of A, so no x solves it.
    # The Arnoldi basis saturates at dimension 1 and the second column is annihilated by
    # the first rotation, leaving a singular triangular factor — GMRES reports
    # krylov_breakdown and returns nothing. The frozen dense solver on the same system
    # returns [0, 0], which is indistinguishable from "the solution is the zero vector";
    # that contrast is the entire reason this module exists.
    var singular_dense = List[Float64]()
    singular_dense.append(1.0)
    singular_dense.append(1.0)
    singular_dense.append(1.0)
    singular_dense.append(1.0)
    var singular = csr_from_dense(singular_dense, 2, 2)
    var gm_sing = csr_gmres(singular, b2, 1e-12, 50, 30)
    var dense_sing = mat_solve(mat_from_list(singular_dense, 2, 2), b2)
    if (
        gm_sing.status == ITER_KRYLOV_BREAKDOWN
        and gm_sing.breakdown
        and not gm_sing.converged
        and len(gm_sing.x) == 0
        and len(dense_sing) == 2
        and dense_sing[0] == 0.0
        and dense_sing[1] == 0.0
    ):
        passed += 1
        print("  ✅ singular system: GMRES says krylov_breakdown, mat_solve says [0,0]")
    else:
        failed += 1
        print(
            "  ❌ singular system:",
            iter_status_name(gm_sing.status),
            len(gm_sing.x),
        )

    # ── CGLS: the exact answer to an inconsistent system has a big residual ───
    # A = [[1,0],[1,1],[1,2]], b = [1,2,2]. Normal equations [[3,3],[3,5]] x = [5,6]
    # give x = [7/6, 1/2]; then b - A x = [-1/6, 1/3, -1/6], ||.|| = sqrt(1/6), and
    # A^T (b - A x) = [0, 0] exactly.
    var design = _design()
    var b_ls = List[Float64]()
    b_ls.append(1.0)
    b_ls.append(2.0)
    b_ls.append(2.0)
    var ls_exact = List[Float64]()
    ls_exact.append(7.0 / 6.0)
    ls_exact.append(0.5)
    var ls = csr_cgls(design, b_ls, 1e-12, 100)
    if (
        ls.status == ITER_CONVERGED
        and ls.converged
        and not ls.breakdown
        and _vec_close(ls.x, ls_exact, 1e-9)
        and ls.iterations <= 2
    ):
        passed += 1
        print("  ✅ CGLS finds the least-squares solution in", ls.iterations)
    else:
        failed += 1
        print("  ❌ CGLS solution:", iter_status_name(ls.status), ls.iterations)

    if (
        _close(ls.residual_norm, sqrt(1.0 / 6.0), 1e-9)
        and ls.normal_residual_norm < 1e-9
        and ls.relative_residual < 1e-9
        and ls.converged
    ):
        passed += 1
        print("  ✅ CGLS: converged with residual_norm 0.408, normal residual ~0")
    else:
        failed += 1
        print(
            "  ❌ CGLS residuals conflated:",
            ls.residual_norm,
            ls.normal_residual_norm,
        )

    # Second oracle: the frozen dense solver on the 2x2 normal equations.
    var normal_a = List[Float64]()
    normal_a.append(3.0)
    normal_a.append(3.0)
    normal_a.append(3.0)
    normal_a.append(5.0)
    var normal_b = List[Float64]()
    normal_b.append(5.0)
    normal_b.append(6.0)
    var normal_x = mat_solve(mat_from_list(normal_a, 2, 2), normal_b)
    if len(normal_x) == 2 and _vec_close(ls.x, normal_x, 1e-9):
        passed += 1
        print("  ✅ CGLS agrees with mat_solve on the explicit normal equations")
    else:
        failed += 1
        print("  ❌ CGLS disagrees with the normal-equation oracle")

    # b orthogonal to range(A): x = 0 is exact, and the residual is all of b. Reporting
    # a zero residual, or iteration_limit, would both be wrong.
    var null_a = csr_from_arrays(_ints2(0, 0), List[Int](), List[Float64](), 1, 2)
    var null_b = List[Float64]()
    null_b.append(1.0)
    var ls_null = csr_cgls(null_a, null_b, 1e-12, 100)
    if (
        ls_null.status == ITER_CONVERGED
        and ls_null.converged
        and ls_null.iterations == 0
        and len(ls_null.x) == 2
        and _close(ls_null.residual_norm, 1.0, 0.0)
        and ls_null.normal_residual_norm == 0.0
    ):
        passed += 1
        print("  ✅ CGLS: A = 0 gives the exact x = 0 with residual ||b||")
    else:
        failed += 1
        print(
            "  ❌ CGLS null case:",
            iter_status_name(ls_null.status),
            ls_null.residual_norm,
        )

    var ls_capped = csr_cgls(design, b_ls, 1e-12, 1)
    if (
        ls_capped.status == ITER_ITERATION_LIMIT
        and not ls_capped.converged
        and ls_capped.iterations == 1
        and len(ls_capped.x) == 2
        and ls_capped.normal_residual_norm > 1e-9
    ):
        passed += 1
        print("  ✅ CGLS honours its cap with converged == False")
    else:
        failed += 1
        print("  ❌ capped CGLS:", iter_status_name(ls_capped.status))

    # ── symmetry ─────────────────────────────────────────────────────────────
    var sym_lap = csr_symmetry(lap)
    var sym_non = csr_symmetry(nonsym)
    # For [[2,1,0],[0,3,1],[1,0,4]] the three mismatched pairs each differ by 1.
    if (
        sym_lap.status == ITER_OK
        and sym_lap.symmetric
        and sym_lap.max_asymmetry == 0.0
        and sym_non.status == ITER_OK
        and not sym_non.symmetric
        and _close(sym_non.max_asymmetry, 1.0, 0.0)
    ):
        passed += 1
        print("  ✅ symmetry: 0.0 for the Laplacian, exactly 1.0 off for the fixture")
    else:
        failed += 1
        print(
            "  ❌ symmetry verdicts:",
            sym_lap.max_asymmetry,
            sym_non.max_asymmetry,
        )

    # An explicit stored zero on one side only is still a symmetric matrix; a purely
    # structural comparison would call this asymmetric and refuse a legal CG.
    var half_stored = csr_from_arrays(
        _ints(0, 2, 3), _ints(0, 1, 1), _laplacian_zero_row(), 2, 2
    )
    if csr_is_symmetric(half_stored):
        passed += 1
        print("  ✅ an explicit zero stored on one side only is still symmetric")
    else:
        failed += 1
        print("  ❌ structural asymmetry misread as numerical asymmetry")

    # ── diagonal and preconditioners ─────────────────────────────────────────
    var diag = csr_diagonal(lap)
    var jac = csr_jacobi_inverse(lap)
    var halves = _zeros(5)
    for i in range(5):
        halves[i] = 0.5
    if (
        diag.status == ITER_OK
        and diag.length == 5
        and diag.zero_pivots == 0
        and _vec_close(diag.values, _twos(), 0.0)
        and jac.status == ITER_OK
        and _vec_close(jac.values, halves, 0.0)
    ):
        passed += 1
        print("  ✅ diag(L) == 2 and its Jacobi inverse == 0.5, exactly")
    else:
        failed += 1
        print("  ❌ diagonal/Jacobi:", diag.length, jac.status)

    # A row with no diagonal entry has no Jacobi preconditioner. Returning 1.0 for the
    # missing reciprocal would silently solve a different problem.
    var no_diag = csr_from_arrays(_ints(0, 1, 2), _ints2(1, 0), _ones(2), 2, 2)
    var jac_bad = csr_jacobi_inverse(no_diag)
    var diag_bad = csr_diagonal(no_diag)
    if (
        jac_bad.status == ITER_ZERO_DIAGONAL
        and len(jac_bad.values) == 0
        and jac_bad.zero_pivots == 2
        and diag_bad.status == ITER_OK
        and diag_bad.zero_pivots == 2
    ):
        passed += 1
        print("  ✅ a missing diagonal is zero_diagonal with a pivot count, not a 1.0")
    else:
        failed += 1
        print(
            "  ❌ zero-diagonal handling:",
            iter_status_name(jac_bad.status),
            jac_bad.zero_pivots,
        )

    # SGS claims to apply M^-1 for M = (D+L) D^-1 (D+U); applying M to the result must
    # return the input. This is the only assertion that can catch the two substitutions
    # inverting the wrong split.
    var rhs_sgs = _five_floats()
    var z_sgs = csr_sgs_apply(lap, rhs_sgs)
    var round_trip = _sgs_operator_apply(lap, z_sgs.values)
    if (
        z_sgs.status == ITER_OK
        and z_sgs.length == 5
        and _vec_close(round_trip, rhs_sgs, 1e-12)
    ):
        passed += 1
        print("  ✅ SGS apply inverts (D+L) D^-1 (D+U) to round-trip precision")
    else:
        failed += 1
        print("  ❌ SGS apply is not the inverse of its own operator")

    # On a diagonal matrix the SGS operator collapses to D, so SGS == Jacobi there.
    var diag_only = csr_from_arrays(_ints(0, 1, 2), _ints2(0, 1), _twos_2(), 2, 2)
    var r2 = List[Float64]()
    r2.append(3.0)
    r2.append(-5.0)
    var sgs_diag = csr_sgs_apply(diag_only, r2)
    var expect_diag = List[Float64]()
    expect_diag.append(1.5)
    expect_diag.append(-2.5)
    if sgs_diag.status == ITER_OK and _vec_close(
        sgs_diag.values, expect_diag, 0.0
    ):
        passed += 1
        print("  ✅ on a diagonal matrix SGS reduces to Jacobi exactly")
    else:
        failed += 1
        print("  ❌ SGS on a diagonal matrix:", iter_status_name(sgs_diag.status))

    # ── structural rejections, and the five-element hazard ───────────────────
    # A broken indptr must never be indexed: reading past the end of `values` is an
    # uncatchable process crash, so every driver validates before it iterates.
    var broken = csr_from_arrays(_ints(0, 2, 1), _ints(0, 1, 1), _ones(3), 2, 3)
    var cg_broken = csr_cg(broken, _ones(2), 1e-12, 10)
    var gm_broken = csr_gmres(broken, _ones(2), 1e-12, 10, 5)
    var ls_broken = csr_cgls(broken, _ones(2), 1e-12, 10)
    if (
        cg_broken.status == ITER_INVALID_CSR
        and gm_broken.status == ITER_INVALID_CSR
        and ls_broken.status == ITER_INVALID_CSR
        and len(cg_broken.x) == 0
        and len(gm_broken.x) == 0
        and len(ls_broken.x) == 0
    ):
        passed += 1
        print("  ✅ a non-monotonic indptr is rejected by all three solvers")
    else:
        failed += 1
        print(
            "  ❌ broken CSR accepted:",
            iter_status_name(cg_broken.status),
            iter_status_name(gm_broken.status),
        )

    # Exactly what the generated A-Z suite does: five-element lists and 5 for each Int.
    # indptr of length 5 is not nrows+1 = 6, so this must be rejected on the length
    # check before anything indexes indptr[5].
    var li5 = _five_ints()
    var lf5 = _five_floats()
    var az_cg = csr_cg_driver(li5, li5, lf5, 5, 5, lf5, 0.5, 5)
    var az_pcg = csr_pcg_driver(li5, li5, lf5, 5, 5, lf5, 0.5, 5, 5)
    var az_gm = csr_gmres_driver(li5, li5, lf5, 5, 5, lf5, 0.5, 5, 5)
    var az_ls = csr_cgls_driver(li5, li5, lf5, 5, 5, lf5, 0.5, 5)
    if (
        az_cg.status == ITER_INVALID_CSR
        and az_gm.status == ITER_INVALID_CSR
        and az_ls.status == ITER_INVALID_CSR
        and len(az_cg.x) == 0
        and len(az_gm.x) == 0
        and len(az_ls.x) == 0
        and az_pcg.status == ITER_INVALID_PARAMETER
    ):
        passed += 1
        print("  ✅ the all-fives contract call is rejected, never indexed")
    else:
        failed += 1
        print(
            "  ❌ all-fives call:",
            iter_status_name(az_cg.status),
            iter_status_name(az_pcg.status),
        )

    # A right-hand side of the wrong length, and a rectangular matrix into CG.
    var short_b = csr_cg(lap, _ones(4), 1e-12, 10)
    var rect_cg = csr_cg(_design(), _ones(3), 1e-12, 10)
    if (
        short_b.status == ITER_SHAPE_MISMATCH
        and rect_cg.status == ITER_SHAPE_MISMATCH
        and len(short_b.x) == 0
        and len(rect_cg.x) == 0
    ):
        passed += 1
        print("  ✅ a short rhs and a rectangular matrix are shape_mismatch")
    else:
        failed += 1
        print(
            "  ❌ shape checks:",
            iter_status_name(short_b.status),
            iter_status_name(rect_cg.status),
        )

    # Parameters that cannot be satisfied are rejected rather than reinterpreted.
    var neg_iter = csr_cg(lap, ones5, 1e-12, -1)
    var neg_tol = csr_cg(lap, ones5, -1.0, 10)
    var bad_restart = csr_gmres(lap, ones5, 1e-12, 10, 0)
    var bad_precond = csr_pcg(lap, ones5, 1e-12, 10, 7)
    if (
        neg_iter.status == ITER_INVALID_PARAMETER
        and neg_tol.status == ITER_INVALID_PARAMETER
        and bad_restart.status == ITER_INVALID_PARAMETER
        and bad_precond.status == ITER_INVALID_PARAMETER
    ):
        passed += 1
        print("  ✅ negative budgets, a zero restart and an unknown precond are rejected")
    else:
        failed += 1
        print(
            "  ❌ parameter validation:",
            iter_status_name(neg_iter.status),
            iter_status_name(bad_restart.status),
        )

    # ── non-finite input ─────────────────────────────────────────────────────
    # Built at run time from a list so it cannot be folded away, and checked to be
    # infinite before it is used, so the assertion below tests what it claims to.
    var overflow = List[Float64]()
    overflow.append(1.0e308)
    var inf = overflow[0] * 10.0
    var b_inf = _ones(5)
    b_inf[2] = inf
    var cg_inf = csr_cg(lap, b_inf, 1e-12, 10)
    var lap_inf_values = List[Float64]()
    for i in range(len(lap.values)):
        lap_inf_values.append(lap.values[i])
    lap_inf_values[0] = inf
    var lap_inf = csr_from_arrays(
        lap.indptr, lap.indices, lap_inf_values, 5, 5
    )
    var cg_inf_matrix = csr_cg(lap_inf, ones5, 1e-12, 10)
    if (
        isinf(inf)
        and cg_inf.status == ITER_NON_FINITE
        and cg_inf_matrix.status == ITER_NON_FINITE
        and len(cg_inf.x) == 0
        and len(cg_inf_matrix.x) == 0
    ):
        passed += 1
        print("  ✅ a non-finite entry in b or in A is caught before iterating")
    else:
        failed += 1
        print(
            "  ❌ non-finite input:",
            iter_status_name(cg_inf.status),
            iter_status_name(cg_inf_matrix.status),
        )

    # ── the empty system ─────────────────────────────────────────────────────
    var empty = csr_from_arrays(_ints(0, 0, 0), List[Int](), List[Float64](), 0, 0)
    var empty_indptr = List[Int]()
    empty_indptr.append(0)
    var real_empty = csr_from_arrays(
        empty_indptr, List[Int](), List[Float64](), 0, 0
    )
    var cg_empty = csr_cg(real_empty, List[Float64](), 1e-12, 10)
    var gm_empty = csr_gmres(real_empty, List[Float64](), 1e-12, 10, 5)
    if (
        cg_empty.status == ITER_ZERO_RHS
        and len(cg_empty.x) == 0
        and gm_empty.status == ITER_ZERO_RHS
        and csr_validate(empty) != CSR_OK
    ):
        passed += 1
        print("  ✅ the 0x0 system returns cleanly instead of dividing by zero")
    else:
        failed += 1
        print("  ❌ empty system:", iter_status_name(cg_empty.status))

    # ── status names ─────────────────────────────────────────────────────────
    if (
        iter_status_name(ITER_CONVERGED) == "converged"
        and iter_status_name(ITER_ITERATION_LIMIT) == "iteration_limit"
        and iter_status_name(ITER_NOT_SYMMETRIC) == "not_symmetric"
        and iter_status_name(ITER_CURVATURE_BREAKDOWN) == "curvature_breakdown"
        and iter_status_name(ITER_NON_FINITE) == "non_finite_encountered"
        and iter_status_name(ITER_ZERO_RHS) == "zero_rhs"
        and iter_status_name(99) == "unknown_status"
    ):
        passed += 1
        print("  ✅ every status has a name, and an unknown code says so")
    else:
        failed += 1
        print("  ❌ status names are wrong:", iter_status_name(ITER_ZERO_RHS))

    # ── a larger SPD system, to exercise the finite-termination bound ─────────
    # CG on an n x n SPD system terminates in at most n iterations; the bound is exact
    # arithmetic's, and it holds comfortably at n = 20 (measured 10 and 16). It stops
    # holding at scale in floating point — measured 304 iterations for n = 300 with a
    # non-symmetric rhs — which is why this is asserted here and not extrapolated.
    var lap20 = _laplacian(20)
    var b20 = _ones(20)
    var cg20 = csr_cg(lap20, b20, 1e-12, 200)
    var exact20 = _laplacian_exact(20)
    var sgs20 = csr_pcg(lap20, b20, 1e-12, 200, PRECOND_SGS)
    if (
        cg20.status == ITER_CONVERGED
        and cg20.iterations <= 20
        and _vec_close(cg20.x, exact20, 1e-6)
        and sgs20.status == ITER_CONVERGED
        and sgs20.iterations <= 20
        and _vec_close(sgs20.x, exact20, 1e-6)
    ):
        passed += 1
        print(
            "  ✅ n=20: CG in",
            cg20.iterations,
            "iterations, SGS-PCG in",
            sgs20.iterations,
        )
    else:
        failed += 1
        print(
            "  ❌ n=20 solve:",
            iter_status_name(cg20.status),
            cg20.iterations,
            sgs20.iterations,
        )

    print("  [sparse_numerics.iterative] Passed:", passed, "Failed:", failed)
