"""
sparse_numerics.iterative — Krylov solvers over CSR. Zero Python.

Why a status is the whole design
--------------------------------
Every other kernel in this package either produces a matrix or fails to. A solver is
different: it always has *a vector in hand*, and that vector looks exactly like an
answer whether or not it is one. `linalg.mat_solve` shows the failure mode — it returns
an all-zeros vector of length n for a singular matrix, so "the solution is zero" and
"there is no solution" are the same return value. An iterative solver has three more
ways to hand back a plausible non-answer: it can stop at its iteration cap, it can be
handed a matrix that is not symmetric positive definite (CG's precondition, which CG
itself will not notice — it will happily converge to something that solves nothing), and
it can break down on a non-positive curvature.

So every solver here returns a struct carrying `status`, `converged` and `breakdown`
alongside the numbers, and the rules are:

* `converged` is true only for an x whose *recomputed* residual meets the tolerance.
* Hitting `max_iter` is `ITER_ITERATION_LIMIT` with `converged == False`. The iterate is
  still returned, because it is a legitimate warm start and its reported residual says
  exactly how good it is — the sin the caller must be protected from is the missing
  indication, not the vector.
* Every other non-convergence (a rejected matrix, a breakdown, a non-finite quantity)
  returns an **empty** x. There is no iterate to report: either the solve never started
  or the step that produced the current point was invalid. An empty list cannot be
  mistaken for a solution the way a zero vector can.

The residual is recomputed, not accumulated
-------------------------------------------
CG and CGLS update the residual recursively (`r -= alpha * A p`), which is one spmv
cheaper per iteration and drifts: after enough iterations the recursive r can be orders
of magnitude smaller than `b - A x`, so a solver that tests the recursive norm declares
convergence it has not reached. Every convergence claim here is therefore verified by a
fresh `b - A x`, and on a false claim the true residual *replaces* the recursive one and
the recursion restarts from it (standard residual replacement). That costs one extra
spmv per convergence test, not per iteration, and it is the difference between reporting
convergence and having it. GMRES needs no such trick: its cycle boundary recomputes the
true residual anyway, so the Givens estimate is only ever used to decide when to stop
building the Krylov basis, never to decide that the answer is good.

What is checked up front, and what cannot be
--------------------------------------------
Symmetry is O(nnz) via a transpose, which is free next to an O(n·nnz) solve, so CG
checks it and reports `ITER_NOT_SYMMETRIC` rather than iterating on a matrix it cannot
solve. Positive definiteness has no cheap test — `linalg_ext.mat_is_positive_definite`
needs a dense Cholesky — so it is detected at run time as `ITER_CURVATURE_BREAKDOWN`
(a non-positive p^T A p), which is a proof that the matrix was not SPD and is reported
as such instead of being clamped or skipped.

Duplicate coordinates sum, as everywhere else in this package
-------------------------------------------------------------
`csr_matvec` adds every stored value, so a duplicate-bearing CSR multiplies the way its
COO would materialise. The diagonal extraction and the Gauss-Seidel substitutions here
sum duplicates for the same reason: they must agree with the operator the matvec
applies, or the preconditioner would be built from a different matrix than the one being
solved. No coalesce is needed for that; the symmetry check does coalesce, because
comparing A with A^T needs both in canonical form.

Reuse
-----
`csr.csr_matvec` for every `A x`, `spmv.spmv_matvec_transpose` for every `A^T y` (it
scatters through the stored order instead of building A^T, so CGLS needs no second copy
of the matrix), `csr_transpose` / `csr_coalesce` for the symmetry check,
`linalg.vec_dot` and `linalg.vec_norm` for inner products and norms,
`scipy_optimize_ops.conjugate_gradient_beta_fr` for the CG direction coefficient (it is
literally the Fletcher-Reeves ratio `new/old`), and `numerical_stability.kahan_sum` for
the GMRES basis combination, where terms alternate in sign and cancel.

Rejected `spmv.spmv_matvec_kahan` as the default apply: it allocates a `List[Float64]`
per row, every row, every iteration, and the mixed-magnitude rows it protects against
are a property of the matrix rather than of the solve. The compensated summation is spent
where the cancellation is structural instead — on the GMRES correction.

No `x0` parameter. Rejected one because every solver here starts from zero, which makes
the initial residual exactly b (no spmv) and the reported relative residual
reproducible; a caller with a warm start can pass `b - A x0` and add x0 back.
"""
from std.math import abs as fabs, isinf, isnan, sqrt

from linalg import vec_dot, vec_norm
from numerical_stability import kahan_sum
from scipy_optimize_ops import conjugate_gradient_beta_fr
from sparse_numerics.diagnostics import (
    DIAG_SYMMETRY_TOL,
    sparse_symmetry_defect,
)
from sparse_numerics.csr import (
    CSRMatrix,
    CSR_OK,
    csr_coalesce,
    csr_from_arrays,
    csr_matvec,
    csr_transpose,
    csr_validate,
)
from sparse_numerics.spmv import spmv_matvec_transpose

# ── status codes ──────────────────────────────────────────────────────────────
# One code per outcome, because a caller that gets a non-solution needs to know whether
# to fix its matrix (not_symmetric), fix its call (shape_mismatch), spend more
# iterations (iteration_limit) or change algorithm entirely (curvature_breakdown).

comptime ITER_CONVERGED: Int = 0
# Same code under a second name for the non-solver results (a diagonal extraction does
# not "converge"). One number on the wire, two readings in the source.
comptime ITER_OK: Int = 0
comptime ITER_ITERATION_LIMIT: Int = 1
comptime ITER_INVALID_CSR: Int = 2
comptime ITER_SHAPE_MISMATCH: Int = 3
comptime ITER_NOT_SYMMETRIC: Int = 4
comptime ITER_CURVATURE_BREAKDOWN: Int = 5
comptime ITER_NON_FINITE: Int = 6
comptime ITER_ZERO_RHS: Int = 7
comptime ITER_KRYLOV_BREAKDOWN: Int = 8
comptime ITER_ZERO_DIAGONAL: Int = 9
comptime ITER_PRECOND_NOT_SPD: Int = 10
comptime ITER_INVALID_PARAMETER: Int = 11

# Preconditioner selector. An Int rather than a String so the flat drivers stay
# JSON-scalar and the dispatch needs no string parsing.
comptime PRECOND_NONE: Int = 0
comptime PRECOND_JACOBI: Int = 1
comptime PRECOND_SGS: Int = 2

# Below this magnitude a diagonal entry is not invertible at working precision, so the
# Jacobi and Gauss-Seidel preconditioners do not exist rather than being built from a
# reciprocal of ~1e300.
comptime ITER_DIAG_EPS: Float64 = 1e-300

# Relative slack for the symmetry test: `|a_ij - a_ji| <= tol * (1 + max|a|)`. The
# frozen dense `matrix_decomp.is_symmetric` compares against an absolute 1e-10, which
# calls a matrix with 1e12 entries asymmetric for a rounding difference; scaling by the
# largest magnitude keeps the same meaning at unit scale and stays meaningful above it.
comptime ITER_SYM_TOL: Float64 = 1e-10


fn iter_status_name(code: Int) -> String:
    """Name for a status code, so a failure surfaces the outcome and not a bare number."""
    if code == ITER_CONVERGED:
        return "converged"
    if code == ITER_ITERATION_LIMIT:
        return "iteration_limit"
    if code == ITER_INVALID_CSR:
        return "invalid_csr"
    if code == ITER_SHAPE_MISMATCH:
        return "shape_mismatch"
    if code == ITER_NOT_SYMMETRIC:
        return "not_symmetric"
    if code == ITER_CURVATURE_BREAKDOWN:
        return "curvature_breakdown"
    if code == ITER_NON_FINITE:
        return "non_finite_encountered"
    if code == ITER_ZERO_RHS:
        return "zero_rhs"
    if code == ITER_KRYLOV_BREAKDOWN:
        return "krylov_breakdown"
    if code == ITER_ZERO_DIAGONAL:
        return "zero_diagonal"
    if code == ITER_PRECOND_NOT_SPD:
        return "preconditioner_not_spd"
    if code == ITER_INVALID_PARAMETER:
        return "invalid_parameter"
    return "unknown_status"


# ── return-only result structs ────────────────────────────────────────────────
# Declared here rather than reused from `csr.mojo` because the runtime contract only
# admits a returned struct whose spec is parsed from the same module: returning
# `csr.CSRVectorResult` would silently drop these functions from the dispatch.


@fieldwise_init
struct IterativeResult(Copyable, Movable):
    """Solution of a square system, plus everything needed to distrust it.

    `residual_norm` is always `||b - A x||` recomputed from the returned x — never the
    solver's internal recursive residual. `relative_residual` is that over `rhs_norm`,
    and is 0.0 (not NaN) for a zero right-hand side, where no division is performed.
    `iterations` counts matrix applications in the iteration proper.

    `converged` and `breakdown` are separate booleans, not two values of one flag,
    because they answer different questions: `converged` is "may I use x", `breakdown`
    is "was my matrix inadmissible for this algorithm". Both false with
    `ITER_ITERATION_LIMIT` means "keep going"; `breakdown` true means "do not retry with
    a bigger budget".
    """

    var status: Int
    var converged: Bool
    var breakdown: Bool
    var iterations: Int
    var residual_norm: Float64
    var relative_residual: Float64
    var rhs_norm: Float64
    var x: List[Float64]


@fieldwise_init
struct LeastSquaresResult(Copyable, Movable):
    """Solution of `min ||A x - b||`, which has two residuals and needs both.

    A separate struct from `IterativeResult` on purpose. For an inconsistent
    overdetermined system the exact answer has a *large* `residual_norm` — that is what
    least squares means — while `normal_residual_norm` (`||A^T (b - A x)||`, the
    gradient of the objective) goes to zero. Packing those into one `residual_norm`
    field would make the correct answer look like a failed solve, or worse, invite a
    caller to test the wrong one against a tolerance. `relative_residual` is the
    normal-equation residual over its initial value, which is the quantity the
    tolerance is actually applied to.
    """

    var status: Int
    var converged: Bool
    var breakdown: Bool
    var iterations: Int
    var residual_norm: Float64
    var normal_residual_norm: Float64
    var relative_residual: Float64
    var normal_rhs_norm: Float64
    var x: List[Float64]


@fieldwise_init
struct SymmetryResult(Copyable, Movable):
    """Whether A == A^T, and by how much it misses.

    `max_asymmetry` is reported absolutely so a caller can judge a borderline matrix
    itself, and `threshold` is the scaled bound actually used, so the verdict is
    reproducible without knowing this module's constants.
    """

    var status: Int
    var symmetric: Bool
    var max_asymmetry: Float64
    var threshold: Float64
    var compared: Int


@fieldwise_init
struct IterativeVectorResult(Copyable, Movable):
    """A dense vector plus status — a diagonal, its inverse, or `M^-1 r`.

    `zero_pivots` counts diagonal entries too small to invert. It is a count and not a
    bool because a caller fixing its assembly wants to know whether one row or every
    row is missing its diagonal.
    """

    var status: Int
    var length: Int
    var zero_pivots: Int
    var values: List[Float64]


fn _failed(status: Int, breakdown: Bool) -> IterativeResult:
    """No iterate at all: empty x, so an ignored status cannot be read as a solution."""
    return IterativeResult(
        status, False, breakdown, 0, 0.0, 0.0, 0.0, List[Float64]()
    )


fn _ls_failed(status: Int, breakdown: Bool) -> LeastSquaresResult:
    return LeastSquaresResult(
        status, False, breakdown, 0, 0.0, 0.0, 0.0, 0.0, List[Float64]()
    )


# ── small internal helpers ────────────────────────────────────────────────────


fn _zeros(n: Int) -> List[Float64]:
    var out = List[Float64]()
    for _ in range(n):
        out.append(0.0)
    return out^


fn _finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)


fn _all_finite(v: List[Float64]) -> Bool:
    """Reject NaN/Inf at the door.

    A single NaN in A or b propagates into x, alpha and the residual norm, and every
    comparison against the tolerance then returns False — so the solver would run to its
    iteration cap and report a plausible `iteration_limit` for what is really a
    corrupted input. One O(nnz) scan turns that into `ITER_NON_FINITE`.
    """
    for i in range(len(v)):
        if not _finite(v[i]):
            return False
    return True


fn _apply(m: CSRMatrix, x: List[Float64]) -> List[Float64]:
    """A @ x through the frozen-package matvec, or an empty list if it refused.

    The callers have already validated m and pass an x of length ncols, so the refusal
    path is unreachable; it is still checked (`len(result) != n`) at each call site
    rather than trusted, because the alternative to a length check is indexing a short
    list, and that is an uncatchable process crash rather than a wrong number.
    """
    var r = csr_matvec(m, x)
    if r.status != CSR_OK:
        return List[Float64]()
    return r.values.copy()


fn _apply_transpose(m: CSRMatrix, y: List[Float64]) -> List[Float64]:
    """A^T @ y, or an empty list if it refused. Length `ncols`; `y` is indexed by row.

    Rejected `csr_matvec(csr_transpose(m), y)`: it is the same numbers, but it copies the
    whole matrix once per solve and CGLS needs this product every iteration. The scatter
    in `spmv_matvec_transpose` reads A once in stored order and allocates only the output.
    """
    var r = spmv_matvec_transpose(m, y)
    if r.status != CSR_OK:
        return List[Float64]()
    return r.values.copy()


fn _residual(m: CSRMatrix, b: List[Float64], x: List[Float64]) -> List[Float64]:
    """b - A x, computed fresh. Empty if the matvec refused."""
    var ax = _apply(m, x)
    if len(ax) != len(b):
        return List[Float64]()
    var out = List[Float64]()
    for i in range(len(b)):
        out.append(b[i] - ax[i])
    return out^


# ── symmetry ──────────────────────────────────────────────────────────────────


fn csr_symmetry(m: CSRMatrix, tol: Float64 = ITER_SYM_TOL) -> SymmetryResult:
    """Whether A is symmetric enough for CG, using the package's ONE defect definition.

    The defect itself — `max |A_ij - A_ji|` over a sorted two-pointer merge of A against
    A^T, O(nnz) with no dense image — lives in `diagnostics.sparse_symmetry_defect` and is
    computed there. This function only applies the DECISION: is that defect small relative
    to the largest magnitude in the matrix.

    Those were previously two separate merge implementations in one package, which meant
    two answers to "is this matrix symmetric": diagnostics reported a raw absolute defect
    while this compared against a magnitude-scaled threshold, so for a matrix with entries
    around 1e12 they disagreed. Both were individually defensible and that was the
    problem — a caller reading `symmetry_defect` from one and `symmetric` from the other
    got an inconsistent pair. One definition, one decision site.

    Rejected `matrix_decomp.is_symmetric`: it takes `List[List[Float64]]` and so needs an
    O(n^2) dense materialisation of a matrix stored sparsely precisely to avoid one. For a
    10^6-row Laplacian that is not a slower check, it is an impossible one.

    The threshold is RELATIVE (`tol * (1 + max|A_ij|)`) because an absolute tolerance is
    meaningless across scales: 1e-9 is exact for a matrix of unit entries and is noise for
    one of 1e12 entries. A structural asymmetry — an entry stored on one side only — is
    compared against the implicit zero on the other, so an explicit stored zero at (i,j)
    with nothing at (j,i) is symmetric, which it is.
    """
    var status = csr_validate(m)
    if status != CSR_OK:
        return SymmetryResult(ITER_INVALID_CSR, False, 0.0, 0.0, 0)
    if m.nrows != m.ncols:
        return SymmetryResult(ITER_SHAPE_MISMATCH, False, 0.0, 0.0, 0)
    if not _all_finite(m.values):
        return SymmetryResult(ITER_NON_FINITE, False, 0.0, 0.0, 0)

    var amax = 0.0
    for k in range(len(m.values)):
        var v = fabs(m.values[k])
        if v > amax:
            amax = v
    var threshold = tol * (1.0 + amax)

    var metric = sparse_symmetry_defect(m, DIAG_SYMMETRY_TOL)
    if not metric.present:
        # diagnostics already rejected it for a reason this function's own guards above
        # did not catch; surface that rather than inventing a verdict.
        return SymmetryResult(ITER_INVALID_CSR, False, 0.0, 0.0, 0)

    var worst = metric.value
    return SymmetryResult(
        ITER_OK, worst <= threshold, worst, threshold, len(m.values)
    )


fn csr_is_symmetric(m: CSRMatrix, tol: Float64 = ITER_SYM_TOL) -> Bool:
    """True only for a valid square matrix that equals its transpose within `tol`."""
    var r = csr_symmetry(m, tol)
    return r.status == ITER_OK and r.symmetric


# ── diagonal and preconditioners ──────────────────────────────────────────────


fn _diagonal_unchecked(m: CSRMatrix) -> List[Float64]:
    """The diagonal of a validated square matrix, duplicates summed.

    Summing is not a choice made here: `csr_matvec` adds every stored value, so this is
    the only diagonal that belongs to the operator being solved.
    """
    var d = _zeros(m.nrows)
    for i in range(m.nrows):
        var acc = 0.0
        for k in range(m.indptr[i], m.indptr[i + 1]):
            if m.indices[k] == i:
                acc += m.values[k]
        d[i] = acc
    return d^


fn csr_diagonal(m: CSRMatrix) -> IterativeVectorResult:
    """The main diagonal. A missing diagonal entry is 0.0 and is counted in
    `zero_pivots`, because "not stored" and "stored as zero" are the same matrix."""
    var status = csr_validate(m)
    if status != CSR_OK:
        return IterativeVectorResult(ITER_INVALID_CSR, 0, 0, List[Float64]())
    if m.nrows != m.ncols:
        return IterativeVectorResult(ITER_SHAPE_MISMATCH, 0, 0, List[Float64]())
    var d = _diagonal_unchecked(m)
    var zeros = 0
    for i in range(len(d)):
        if fabs(d[i]) <= ITER_DIAG_EPS:
            zeros += 1
    var n = len(d)
    return IterativeVectorResult(ITER_OK, n, zeros, d^)


fn csr_jacobi_inverse(m: CSRMatrix) -> IterativeVectorResult:
    """The Jacobi preconditioner `diag(A)^-1`.

    A zero diagonal entry means this preconditioner does not exist, so the status says
    `ITER_ZERO_DIAGONAL` and the values are empty. Substituting 1.0 for the missing
    reciprocal — the usual shortcut — silently changes the preconditioner into a
    different operator, and a preconditioner that is not the one you asked for is a
    wrong answer that converges.
    """
    var d = csr_diagonal(m)
    if d.status != ITER_OK:
        return IterativeVectorResult(d.status, 0, 0, List[Float64]())
    if d.zero_pivots > 0:
        return IterativeVectorResult(
            ITER_ZERO_DIAGONAL, 0, d.zero_pivots, List[Float64]()
        )
    var out = List[Float64]()
    for i in range(d.length):
        out.append(1.0 / d.values[i])
    var n = len(out)
    return IterativeVectorResult(ITER_OK, n, 0, out^)


fn _sgs_apply_unchecked(
    m: CSRMatrix, d: List[Float64], r: List[Float64]
) -> List[Float64]:
    """`M^-1 r` for the symmetric Gauss-Seidel `M = (D+L) D^-1 (D+U)`.

    Two triangular substitutions with a diagonal scaling between them; no triangular
    factor is ever materialised, so this is O(nnz) with no extra storage. The row scan
    picks L and U entries by column index instead of relying on sorted indices, so an
    unsorted CSR needs no canonicalisation, and duplicate coordinates contribute to
    both substitutions exactly as they contribute to the matvec.

    Caller must have established `|d[i]| > ITER_DIAG_EPS` for every i.
    """
    var n = m.nrows
    var t = _zeros(n)
    for i in range(n):
        var s = r[i]
        for k in range(m.indptr[i], m.indptr[i + 1]):
            var j = m.indices[k]
            if j < i:
                s -= m.values[k] * t[j]
        t[i] = s / d[i]

    var z = _zeros(n)
    var i = n - 1
    while i >= 0:
        # (D+U) z = D t, so the right-hand side is the diagonal scaling of t.
        var s = d[i] * t[i]
        for k in range(m.indptr[i], m.indptr[i + 1]):
            var j = m.indices[k]
            if j > i:
                s -= m.values[k] * z[j]
        z[i] = s / d[i]
        i -= 1
    return z^


fn csr_sgs_apply(m: CSRMatrix, r: List[Float64]) -> IterativeVectorResult:
    """Apply the symmetric Gauss-Seidel preconditioner to one vector."""
    var d = csr_diagonal(m)
    if d.status != ITER_OK:
        return IterativeVectorResult(d.status, 0, 0, List[Float64]())
    if d.zero_pivots > 0:
        return IterativeVectorResult(
            ITER_ZERO_DIAGONAL, 0, d.zero_pivots, List[Float64]()
        )
    if len(r) != m.nrows:
        return IterativeVectorResult(ITER_SHAPE_MISMATCH, 0, 0, List[Float64]())
    if not _all_finite(r):
        return IterativeVectorResult(ITER_NON_FINITE, 0, 0, List[Float64]())
    var z = _sgs_apply_unchecked(m, d.values, r)
    var n = len(z)
    return IterativeVectorResult(ITER_OK, n, 0, z^)


fn _precond_apply(
    m: CSRMatrix,
    precond: Int,
    dinv: List[Float64],
    d: List[Float64],
    r: List[Float64],
) -> List[Float64]:
    """`M^-1 r` for the selected preconditioner; the identity for `PRECOND_NONE`.

    The identity case is what lets one loop serve both CG and PCG — see `_pcg_core`.
    """
    if precond == PRECOND_JACOBI:
        var out = List[Float64]()
        for i in range(len(r)):
            out.append(r[i] * dinv[i])
        return out^
    if precond == PRECOND_SGS:
        return _sgs_apply_unchecked(m, d, r)
    return r.copy()


# ── conjugate gradient, preconditioned and not ────────────────────────────────


fn _pcg_core(
    m: CSRMatrix, b: List[Float64], tol: Float64, max_iter: Int, precond: Int
) -> IterativeResult:
    """Preconditioned CG. `PRECOND_NONE` reduces it to textbook CG exactly.

    One loop for both, rather than a CG and a PCG side by side: two implementations of
    the same recurrence are two chances to get the recurrence wrong, and the difference
    between them would show up as a wrong answer rather than a compile error. The
    identity preconditioner costs one vector copy per iteration, which is the price of
    having a single definition of "conjugate gradient" in this module. The suite asserts
    the two agree bit for bit.
    """
    if max_iter < 0 or tol < 0.0 or not _finite(tol):
        return _failed(ITER_INVALID_PARAMETER, False)
    if precond != PRECOND_NONE and precond != PRECOND_JACOBI and precond != PRECOND_SGS:
        return _failed(ITER_INVALID_PARAMETER, False)
    if csr_validate(m) != CSR_OK:
        return _failed(ITER_INVALID_CSR, False)
    var n = m.nrows
    if m.ncols != n or len(b) != n:
        return _failed(ITER_SHAPE_MISMATCH, False)
    if not _all_finite(m.values) or not _all_finite(b):
        return _failed(ITER_NON_FINITE, False)

    # CG solves SPD systems only. Symmetry is O(nnz) and therefore free next to the
    # solve; definiteness is not testable cheaply and shows up below as a curvature
    # breakdown.
    var sym = csr_symmetry(m)
    if sym.status != ITER_OK:
        return _failed(sym.status, False)
    if not sym.symmetric:
        return _failed(ITER_NOT_SYMMETRIC, False)

    var bnorm = vec_norm(b)
    if bnorm == 0.0:
        # x = 0 solves A x = 0 exactly, so this is an answer and not a failure — but it
        # gets its own status because `relative_residual` has no denominator here and a
        # caller must not compare it to a tolerance. No division is performed.
        return IterativeResult(
            ITER_ZERO_RHS, True, False, 0, 0.0, 0.0, 0.0, _zeros(n)
        )

    var dinv = List[Float64]()
    var diag = List[Float64]()
    if precond == PRECOND_JACOBI:
        var jac = csr_jacobi_inverse(m)
        if jac.status != ITER_OK:
            return _failed(jac.status, False)
        dinv = jac.values.copy()
        for i in range(len(dinv)):
            # M = D must be SPD for the preconditioned recurrence to be a CG at all; a
            # negative diagonal also proves A is not SPD.
            if dinv[i] <= 0.0:
                return _failed(ITER_PRECOND_NOT_SPD, False)
    elif precond == PRECOND_SGS:
        var dd = csr_diagonal(m)
        if dd.status != ITER_OK:
            return _failed(dd.status, False)
        if dd.zero_pivots > 0:
            return _failed(ITER_ZERO_DIAGONAL, False)
        diag = dd.values.copy()
        for i in range(len(diag)):
            if diag[i] <= 0.0:
                return _failed(ITER_PRECOND_NOT_SPD, False)

    var x = _zeros(n)
    # x starts at zero, so the initial residual is b itself; no spmv is needed.
    var r = b.copy()
    var z = _precond_apply(m, precond, dinv, diag, r)
    if len(z) != n:
        return _failed(ITER_INVALID_CSR, False)
    var p = z.copy()
    var rz = vec_dot(r, z)
    if not _finite(rz):
        return _failed(ITER_NON_FINITE, True)
    if rz <= 0.0:
        # r != 0 here (bnorm > 0), so a non-positive r^T M^-1 r proves M is not SPD.
        return _failed(ITER_PRECOND_NOT_SPD, True)

    var it = 0
    var rnorm = bnorm
    var converged = False
    while it < max_iter:
        var ap = _apply(m, p)
        if len(ap) != n:
            return _failed(ITER_INVALID_CSR, False)
        var pap = vec_dot(p, ap)
        if not _finite(pap):
            return _failed(ITER_NON_FINITE, True)
        if pap <= 0.0:
            # p^T A p <= 0 with p != 0 is a proof that A is not positive definite. The
            # iterate at this point solves nothing, so it is not returned.
            return _failed(ITER_CURVATURE_BREAKDOWN, True)
        var alpha = rz / pap
        if not _finite(alpha):
            return _failed(ITER_NON_FINITE, True)
        for i in range(n):
            x[i] += alpha * p[i]
            r[i] -= alpha * ap[i]
        it += 1

        rnorm = vec_norm(r)
        if not _finite(rnorm):
            return _failed(ITER_NON_FINITE, True)

        var replaced = False
        if rnorm <= tol * bnorm:
            # The recursive residual is a claim; b - A x is the fact.
            var tr = _residual(m, b, x)
            if len(tr) != n:
                return _failed(ITER_INVALID_CSR, False)
            var tnorm = vec_norm(tr)
            if not _finite(tnorm):
                return _failed(ITER_NON_FINITE, True)
            if tnorm <= tol * bnorm:
                rnorm = tnorm
                converged = True
                break
            # Drift, not convergence: adopt the true residual and restart the
            # recurrence from it rather than reporting a tolerance that is not met.
            for i in range(n):
                r[i] = tr[i]
            rnorm = tnorm
            replaced = True

        var z_new = _precond_apply(m, precond, dinv, diag, r)
        if len(z_new) != n:
            return _failed(ITER_INVALID_CSR, False)
        var rz_new = vec_dot(r, z_new)
        if not _finite(rz_new):
            return _failed(ITER_NON_FINITE, True)
        if rz_new <= 0.0:
            return _failed(ITER_PRECOND_NOT_SPD, True)
        if replaced:
            # A replaced residual breaks conjugacy with the old direction, so the
            # recurrence restarts with a steepest-descent step instead of carrying a
            # beta that no longer means anything.
            p = z_new.copy()
        else:
            var beta = conjugate_gradient_beta_fr(rz_new, rz)
            for i in range(n):
                p[i] = z_new[i] + beta * p[i]
        rz = rz_new

    if not converged:
        # Report the true residual of the iterate we are handing back, not the drifted
        # recursive one: the whole point of returning the iterate is that its reported
        # quality is trustworthy.
        var tr = _residual(m, b, x)
        if len(tr) != n:
            return _failed(ITER_INVALID_CSR, False)
        rnorm = vec_norm(tr)
        if not _finite(rnorm):
            return _failed(ITER_NON_FINITE, True)
        return IterativeResult(
            ITER_ITERATION_LIMIT,
            False,
            False,
            it,
            rnorm,
            rnorm / bnorm,
            bnorm,
            x^,
        )
    return IterativeResult(
        ITER_CONVERGED, True, False, it, rnorm, rnorm / bnorm, bnorm, x^
    )


fn csr_cg(
    m: CSRMatrix, b: List[Float64], tol: Float64 = 1e-10, max_iter: Int = 1000
) -> IterativeResult:
    """Conjugate gradient for a symmetric positive definite A. Unpreconditioned."""
    return _pcg_core(m, b, tol, max_iter, PRECOND_NONE)


fn csr_pcg(
    m: CSRMatrix,
    b: List[Float64],
    tol: Float64 = 1e-10,
    max_iter: Int = 1000,
    precond: Int = PRECOND_JACOBI,
) -> IterativeResult:
    """Preconditioned conjugate gradient. `precond` is one of the `PRECOND_*` codes."""
    return _pcg_core(m, b, tol, max_iter, precond)


# ── CGLS: least squares / nonsymmetric ────────────────────────────────────────


fn csr_cgls(
    m: CSRMatrix, b: List[Float64], tol: Float64 = 1e-10, max_iter: Int = 1000
) -> LeastSquaresResult:
    """CG on the normal equations, applied as `A` and `A^T` and never formed.

    Solves `min ||A x - b||` for any shape, so it covers the nonsymmetric square case
    and the overdetermined case with one code path. `A^T A` is never materialised:
    forming it squares the condition number and can turn a sparse A into a dense
    product, which is the whole reason CGLS exists rather than "build the normal
    equations and call CG".

    The convergence test is on `||A^T (b - A x)||`, the gradient of the objective, not
    on `||b - A x||` — for an inconsistent system the latter never approaches zero, and
    testing it would report `iteration_limit` for an exactly correct answer.
    """
    if max_iter < 0 or tol < 0.0 or not _finite(tol):
        return _ls_failed(ITER_INVALID_PARAMETER, False)
    if csr_validate(m) != CSR_OK:
        return _ls_failed(ITER_INVALID_CSR, False)
    var rows = m.nrows
    var cols = m.ncols
    if len(b) != rows:
        return _ls_failed(ITER_SHAPE_MISMATCH, False)
    if not _all_finite(m.values) or not _all_finite(b):
        return _ls_failed(ITER_NON_FINITE, False)

    var bnorm = vec_norm(b)
    if bnorm == 0.0:
        return LeastSquaresResult(
            ITER_ZERO_RHS, True, False, 0, 0.0, 0.0, 0.0, 0.0, _zeros(cols)
        )

    var x = _zeros(cols)
    var r = b.copy()
    var s = _apply_transpose(m, r)
    if len(s) != cols:
        return _ls_failed(ITER_INVALID_CSR, False)
    var gnorm0 = vec_norm(s)
    if gnorm0 == 0.0:
        # b is orthogonal to the range of A, so x = 0 is the exact minimiser and the
        # residual is all of b. Reporting `iteration_limit` here (or a zero residual)
        # would both be lies; the answer exists and is exact.
        return LeastSquaresResult(
            ITER_CONVERGED, True, False, 0, bnorm, 0.0, 0.0, 0.0, x^
        )

    var p = s.copy()
    var gamma = vec_dot(s, s)
    var it = 0
    var gnorm = gnorm0
    var converged = False
    while it < max_iter:
        var q = _apply(m, p)
        if len(q) != rows:
            return _ls_failed(ITER_INVALID_CSR, False)
        var denom = vec_dot(q, q)
        if not _finite(denom):
            return _ls_failed(ITER_NON_FINITE, True)
        if denom <= 0.0:
            # A p == 0 with p != 0: p^T (A^T A) p == 0, so the normal-equation matrix is
            # singular in this direction. Same defect as CG's curvature breakdown, hence
            # the same status.
            return _ls_failed(ITER_CURVATURE_BREAKDOWN, True)
        var alpha = gamma / denom
        if not _finite(alpha):
            return _ls_failed(ITER_NON_FINITE, True)
        for i in range(cols):
            x[i] += alpha * p[i]
        for i in range(rows):
            r[i] -= alpha * q[i]
        it += 1

        s = _apply_transpose(m, r)
        if len(s) != cols:
            return _ls_failed(ITER_INVALID_CSR, False)
        gnorm = vec_norm(s)
        if not _finite(gnorm):
            return _ls_failed(ITER_NON_FINITE, True)

        var replaced = False
        if gnorm <= tol * gnorm0:
            var tr = _residual(m, b, x)
            if len(tr) != rows:
                return _ls_failed(ITER_INVALID_CSR, False)
            var ts = _apply_transpose(m, tr)
            if len(ts) != cols:
                return _ls_failed(ITER_INVALID_CSR, False)
            var tnorm = vec_norm(ts)
            if not _finite(tnorm):
                return _ls_failed(ITER_NON_FINITE, True)
            if tnorm <= tol * gnorm0:
                for i in range(rows):
                    r[i] = tr[i]
                s = ts.copy()
                gnorm = tnorm
                converged = True
                break
            for i in range(rows):
                r[i] = tr[i]
            s = ts.copy()
            gnorm = tnorm
            replaced = True

        var gamma_new = vec_dot(s, s)
        if not _finite(gamma_new):
            return _ls_failed(ITER_NON_FINITE, True)
        if replaced:
            p = s.copy()
        else:
            var beta = conjugate_gradient_beta_fr(gamma_new, gamma)
            for i in range(cols):
                p[i] = s[i] + beta * p[i]
        gamma = gamma_new

    # Both residuals are recomputed from the returned x, whether or not it converged:
    # the least-squares residual is a headline number and must not be a drifted one.
    var final_r = _residual(m, b, x)
    if len(final_r) != rows:
        return _ls_failed(ITER_INVALID_CSR, False)
    var rnorm = vec_norm(final_r)
    var final_s = _apply_transpose(m, final_r)
    if len(final_s) != cols:
        return _ls_failed(ITER_INVALID_CSR, False)
    var final_g = vec_norm(final_s)
    if not _finite(rnorm) or not _finite(final_g):
        return _ls_failed(ITER_NON_FINITE, True)
    var status = ITER_ITERATION_LIMIT
    if converged:
        status = ITER_CONVERGED
    return LeastSquaresResult(
        status,
        converged,
        False,
        it,
        rnorm,
        final_g,
        final_g / gnorm0,
        gnorm0,
        x^,
    )


# ── restarted GMRES ───────────────────────────────────────────────────────────


fn csr_gmres(
    m: CSRMatrix,
    b: List[Float64],
    tol: Float64 = 1e-10,
    max_iter: Int = 1000,
    restart: Int = 30,
) -> IterativeResult:
    """GMRES(restart) for a square nonsymmetric A.

    Arnoldi with modified Gram-Schmidt, and the small least-squares problem solved by
    Givens rotations maintained incrementally. Rejected forming `H^T H` and calling the
    frozen `linalg.mat_solve` on it: the normal equations square the condition number of
    exactly the object whose ill-conditioning GMRES is being used to survive, and the
    Givens recurrence also yields the residual estimate for free, which is what lets a
    cycle stop early.

    `restart` is clamped to `n`, not rejected above it: the Krylov space saturates at
    dimension n (the Arnoldi vector becomes zero — a "happy breakdown", which is exact
    convergence, not a failure), so a larger basis cannot exist and allocating one would
    only waste `n * restart` doubles.

    `iterations` counts Arnoldi steps, i.e. applications of A inside the cycles. The
    residual recomputations at the cycle boundaries are not counted, so the number is
    comparable with CG's.
    """
    if max_iter < 0 or restart < 1 or tol < 0.0 or not _finite(tol):
        return _failed(ITER_INVALID_PARAMETER, False)
    if csr_validate(m) != CSR_OK:
        return _failed(ITER_INVALID_CSR, False)
    var n = m.nrows
    if m.ncols != n or len(b) != n:
        return _failed(ITER_SHAPE_MISMATCH, False)
    if not _all_finite(m.values) or not _all_finite(b):
        return _failed(ITER_NON_FINITE, False)

    var bnorm = vec_norm(b)
    if bnorm == 0.0:
        return IterativeResult(
            ITER_ZERO_RHS, True, False, 0, 0.0, 0.0, 0.0, _zeros(n)
        )

    var cap = restart
    if cap > n:
        cap = n

    var x = _zeros(n)
    var total = 0
    var rnorm = bnorm
    var converged = False

    while True:
        # Every convergence decision is made here, on a residual computed from x by the
        # matvec — never on the Givens estimate, which is only used to end a cycle.
        var r = _residual(m, b, x)
        if len(r) != n:
            return _failed(ITER_INVALID_CSR, False)
        var beta = vec_norm(r)
        if not _finite(beta):
            return _failed(ITER_NON_FINITE, True)
        rnorm = beta
        if beta <= tol * bnorm:
            converged = True
            break
        if total >= max_iter:
            break

        var kmax = cap
        if kmax > max_iter - total:
            kmax = max_iter - total

        # V holds kmax+1 basis vectors row-major; H is (kmax+1) x kmax, also row-major.
        # Flat lists, per the package rule that a 2D array is flat plus its extents.
        var v = _zeros((kmax + 1) * n)
        var h = _zeros((kmax + 1) * kmax)
        var cs = _zeros(kmax)
        var sn = _zeros(kmax)
        var g = _zeros(kmax + 1)
        g[0] = beta
        for i in range(n):
            v[i] = r[i] / beta

        var k = 0
        var singular = False
        for j in range(kmax):
            var vj = List[Float64]()
            for i in range(n):
                vj.append(v[j * n + i])
            var w = _apply(m, vj)
            if len(w) != n:
                return _failed(ITER_INVALID_CSR, False)
            total += 1

            # Modified Gram-Schmidt: orthogonalise against each basis vector in turn,
            # updating w before the next projection. Rejected classical Gram-Schmidt
            # (all projections from the same w) — it loses orthogonality on
            # ill-conditioned bases, which shows up as a residual estimate that no
            # longer matches the true residual, i.e. as a false convergence claim.
            for i in range(j + 1):
                var acc = 0.0
                for t in range(n):
                    acc += w[t] * v[i * n + t]
                h[i * kmax + j] = acc
                for t in range(n):
                    w[t] -= acc * v[i * n + t]
            var hnext = vec_norm(w)
            if not _finite(hnext):
                return _failed(ITER_NON_FINITE, True)
            h[(j + 1) * kmax + j] = hnext
            if hnext > 0.0:
                for t in range(n):
                    v[(j + 1) * n + t] = w[t] / hnext

            # Apply the rotations already computed to the new column.
            for i in range(j):
                var t1 = cs[i] * h[i * kmax + j] + sn[i] * h[(i + 1) * kmax + j]
                h[(i + 1) * kmax + j] = (
                    -sn[i] * h[i * kmax + j] + cs[i] * h[(i + 1) * kmax + j]
                )
                h[i * kmax + j] = t1

            var h1 = h[j * kmax + j]
            var h2 = h[(j + 1) * kmax + j]
            var nu = sqrt(h1 * h1 + h2 * h2)
            if not (nu > 0.0):
                # The whole column vanished under the previous rotations: the upper
                # triangular factor is singular and this cycle has no least-squares
                # solution. Not the same thing as a happy breakdown.
                singular = True
                break
            cs[j] = h1 / nu
            sn[j] = h2 / nu
            h[j * kmax + j] = nu
            h[(j + 1) * kmax + j] = 0.0
            g[j + 1] = -sn[j] * g[j]
            g[j] = cs[j] * g[j]
            k = j + 1

            # |g[k]| is the exact residual norm of the least-squares solution of this
            # cycle. A happy breakdown (hnext == 0) forces sn[j] == 0, hence g[k] == 0,
            # so it ends the cycle through this same test.
            if fabs(g[k]) <= tol * bnorm:
                break
        if singular:
            return _failed(ITER_KRYLOV_BREAKDOWN, True)
        if k == 0:
            # No usable Arnoldi step, yet the residual above was above tolerance: no
            # progress is possible and looping again would spin.
            return _failed(ITER_KRYLOV_BREAKDOWN, True)

        # Back-substitute R y = g over the k x k leading block.
        var y = _zeros(k)
        var ii = k - 1
        while ii >= 0:
            var s = g[ii]
            for jj in range(ii + 1, k):
                s -= h[ii * kmax + jj] * y[jj]
            var diag = h[ii * kmax + ii]
            if not (fabs(diag) > 0.0):
                return _failed(ITER_KRYLOV_BREAKDOWN, True)
            y[ii] = s / diag
            ii -= 1

        # x += V y, compensated. The terms alternate sign and cancel — that is what a
        # minimum-residual correction is — so this is exactly the accumulation Kahan
        # summation exists for. One temporary list per component per cycle, not per
        # iteration; the alternative (a running sum) loses digits precisely on the
        # ill-conditioned problems that motivated a Krylov method.
        for i in range(n):
            var terms = List[Float64]()
            for j in range(k):
                terms.append(y[j] * v[j * n + i])
            x[i] += kahan_sum(terms)

    if converged:
        return IterativeResult(
            ITER_CONVERGED, True, False, total, rnorm, rnorm / bnorm, bnorm, x^
        )
    return IterativeResult(
        ITER_ITERATION_LIMIT,
        False,
        False,
        total,
        rnorm,
        rnorm / bnorm,
        bnorm,
        x^,
    )


# ── flat-list drivers ─────────────────────────────────────────────────────────
# Lists and scalars in, a status-bearing struct out, so the package is callable as
# execute(module, function, args) from the local SDKs with no new message type.
# Every one of these validates the CSR arrays before any indexing: the generated A-Z
# suite calls each with five-element lists and 5 for every Int, and an unguarded
# indptr[5] on a five-element list crashes the worker process outright.
#
# SIGNATURES BELOW MUST FIT IN TEN PHYSICAL LINES. `_parse_runtime_function_specs` in
# apps/runtime/mojo_inventory.py scans at most `index + 10` lines for the closing
# `) -> T:` and gives up otherwise — and "gives up" means the function is dropped from
# the runtime contract and the dispatch with no error, exactly like a returned struct
# declared in another module. The two nine-parameter drivers therefore pack their
# trailing scalars onto one line; re-splitting them one-per-line compiles fine and
# silently removes them from the SDK surface. (Measured: `gbdt.gbdt_fit` and
# `seq_nn.lstm_cell_backward` are already invisible for this reason.)


fn csr_cg_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    b: List[Float64],
    tol: Float64,
    max_iter: Int,
) -> IterativeResult:
    """Unpreconditioned CG from wire arrays."""
    return csr_cg(
        csr_from_arrays(indptr, indices, values, nrows, ncols), b, tol, max_iter
    )


fn csr_pcg_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    b: List[Float64],
    tol: Float64, max_iter: Int, precond: Int,
) -> IterativeResult:
    """Preconditioned CG from wire arrays; `precond` is a `PRECOND_*` code."""
    return csr_pcg(
        csr_from_arrays(indptr, indices, values, nrows, ncols),
        b,
        tol,
        max_iter,
        precond,
    )


fn csr_cgls_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    b: List[Float64],
    tol: Float64,
    max_iter: Int,
) -> LeastSquaresResult:
    """Least-squares solve from wire arrays. A may be rectangular."""
    return csr_cgls(
        csr_from_arrays(indptr, indices, values, nrows, ncols), b, tol, max_iter
    )


fn csr_gmres_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    b: List[Float64],
    tol: Float64, max_iter: Int, restart: Int,
) -> IterativeResult:
    """Restarted GMRES from wire arrays."""
    return csr_gmres(
        csr_from_arrays(indptr, indices, values, nrows, ncols),
        b,
        tol,
        max_iter,
        restart,
    )


fn csr_symmetry_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    tol: Float64,
) -> SymmetryResult:
    """Symmetry verdict plus the worst elementwise asymmetry found."""
    return csr_symmetry(
        csr_from_arrays(indptr, indices, values, nrows, ncols), tol
    )


fn csr_diagonal_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> IterativeVectorResult:
    """The main diagonal, duplicates summed, with a count of non-invertible entries."""
    return csr_diagonal(csr_from_arrays(indptr, indices, values, nrows, ncols))


fn csr_jacobi_inverse_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> IterativeVectorResult:
    """`diag(A)^-1`, or `ITER_ZERO_DIAGONAL` and no values."""
    return csr_jacobi_inverse(
        csr_from_arrays(indptr, indices, values, nrows, ncols)
    )


fn csr_sgs_apply_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    r: List[Float64],
) -> IterativeVectorResult:
    """One application of the symmetric Gauss-Seidel preconditioner."""
    return csr_sgs_apply(
        csr_from_arrays(indptr, indices, values, nrows, ncols), r
    )
