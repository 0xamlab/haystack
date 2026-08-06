"""
sparse_numerics.factor — direct solves over CSR, with a failure value you can see.

What the tree has today, and the exact bug this file exists not to repeat
-----------------------------------------------------------------------
`linalg.mat_solve` is the only linear solver in the repo. Read its two failure paths:

* a singular matrix returns **an all-zeros vector of length n** (`linalg.mojo:319-324`)
* a non-square matrix, or a right-hand side of the wrong length, returns **an empty
  list** (`linalg.mojo:297-299`)

So "the solution is the zero vector" — a perfectly ordinary answer, and the exact answer
whenever `b` is zero — is byte-identical to "this matrix has no inverse". There is no
flag, no status and no residual, and back substitution additionally writes `x[i] = 0.0`
on a zero pivot (`linalg.mojo:349-350`) so even a partially dead system comes back
looking like a solution.

`linalg.mat_lu` is worse in a quieter way: on a column whose pivot candidates are all
below 1e-15 it executes `continue` (`linalg.mojo:432-433`), leaving that column
un-eliminated and returning L and U with no indication that anything happened. The
factorisation it returns is in fact still valid — the entries it declined to eliminate
were already zero to within the tolerance — but `U` has a zero on the diagonal and
nothing says so. `matrix_decomp.forward_substitution` / `back_substitution` have the same
shape of hole: `if L[i][i] == 0.0: x[i] = 0.0`.

Every public function here therefore returns a status and a `singular` flag alongside its
numbers, and returns **no vector at all** when there is no solution. That is rule 4 of
docs/mojo/new-kernel-package-rules.md applied to the one place in numerics where a wrong
answer looks most like a right one.

The arithmetic is frozen; the composition is here
-------------------------------------------------
Nothing in this file re-implements an elimination. `csr_lu_factor` calls
`linalg.mat_lu`, the triangular solves call `matrix_decomp.forward_substitution` and
`back_substitution`, the dense fallback calls `linalg.mat_solve`, the SPD and
least-squares paths call `matrix_decomp.cholesky` (the tree already has one — a second
would be a second definition of positive-definiteness), the Gram matrix is
`linalg.mat_mul(mat_transpose(A), A)` and the residual norm is `linalg.vec_norm` over
`sparse_numerics.csr.csr_matvec` — directly, not through `spmv.spmv_matvec`, which is by
its own docstring a restatement of `csr_matvec` in that module's result type and changes
no number. What this module adds is the CSR ingestion, the
permutation the caller never got to see, the singularity test the frozen kernels never
performed, the fill-in measurement, the reuse of one factorisation across many
right-hand sides, and the residual.

Two frozen kernels take `List[List[Float64]]`. New matrices here are flat row-major
`List[Float64]` plus `n`, per rule 5; `_nested_from_flat` exists only as an adapter at
those two call sites and no nested matrix is ever stored or returned.

The strategy switch is reported, never silent
---------------------------------------------
`csr_solve` can answer through the sparse factorisation or through the dense
`mat_solve`, and every result says which (`strategy`) and why (`fallback_reason`). The
two triggers are deliberately asymmetric:

* **below `FACTOR_DENSE_MIN_N`** the decision is made *before* factoring, because the
  bookkeeping a sparse factorisation carries (a permutation, a fill count, two n×n
  triangles) costs more than the elimination it saves at that size, and nothing has been
  spent yet.
* **fill-in above `FACTOR_FILL_LIMIT_MULTIPLE` × nnz(A)** can only be decided *after*
  factoring: with partial pivoting the fill depends on the values, not just the pattern,
  so no honest a-priori estimate exists. The one-shot answer is then taken from
  `mat_solve` — the tree's reference solver — and the caller learns from
  `fallback_reason` that keeping this factorisation around would buy it nothing. This
  costs one extra elimination, which is the price of not guessing.

A caller that wants the factorisation regardless calls `csr_lu_factor` directly; the
threshold governs `csr_solve` only.

Status codes are this module's own numbering
--------------------------------------------
A structurally broken CSR reports `FACTOR_ERR_STRUCTURE` rather than forwarding the
`CSR_ERR_*` code. The two numbering spaces overlap (`CSR_ERR_SHAPE` and
`FACTOR_ERR_INVALID_DIMENSIONS` are both 1), so a forwarded number would leave the caller
unable to tell which table to read it in. `csr_validate_flat` remains available for the
precise defect.
"""
from std.math import abs as fabs

from linalg import (
    Matrix,
    mat_from_list,
    mat_lu,
    mat_mul,
    mat_solve,
    mat_transpose,
    vec_norm,
)
from matrix_decomp import (
    back_substitution,
    cholesky,
    forward_substitution,
    is_symmetric,
)
from sparse_numerics.csr import (
    CSRMatrix,
    CSR_OK,
    csr_from_arrays,
    csr_matvec,
    csr_to_dense,
    csr_transpose,
    csr_validate_flat,
)

# ── status codes ──────────────────────────────────────────────────────────────

comptime FACTOR_OK: Int = 0
comptime FACTOR_ERR_INVALID_DIMENSIONS: Int = 1
comptime FACTOR_ERR_STRUCTURE: Int = 2
comptime FACTOR_ERR_NOT_SQUARE: Int = 3
comptime FACTOR_ERR_SINGULAR: Int = 4
comptime FACTOR_ERR_NOT_FACTORED: Int = 5
comptime FACTOR_ERR_NOT_SPD: Int = 6
comptime FACTOR_ERR_RANK_DEFICIENT: Int = 7

# ── which path produced the numbers ───────────────────────────────────────────
# Reported on every solve. A caller comparing two runs needs to know whether it is
# comparing two answers or two algorithms.

comptime FACTOR_STRATEGY_SPARSE_LU: Int = 0
comptime FACTOR_STRATEGY_DENSE_SOLVE: Int = 1
comptime FACTOR_STRATEGY_CHOLESKY: Int = 2
comptime FACTOR_STRATEGY_NORMAL_EQUATIONS: Int = 3
comptime FACTOR_STRATEGY_TRIVIAL: Int = 4
comptime FACTOR_STRATEGY_NONE: Int = 5

comptime FACTOR_FALLBACK_NONE: Int = 0
comptime FACTOR_FALLBACK_SMALL_SYSTEM: Int = 1
comptime FACTOR_FALLBACK_FILL_IN: Int = 2

# ── tunables ──────────────────────────────────────────────────────────────────

# Below this order the sparse path's bookkeeping exceeds the elimination it saves.
comptime FACTOR_DENSE_MIN_N: Int = 16

# Fill-in beyond 8x the stored count means the triangles are no longer sparse in any
# useful sense; 8 rather than 2 or 3 because a banded factor legitimately doubles or
# triples nnz and switching on that would send almost everything dense.
comptime FACTOR_FILL_LIMIT_MULTIPLE: Float64 = 8.0

# Matches `mat_lu`'s and `mat_solve`'s own internal 1e-15 pivot floor exactly. A looser
# tolerance here would call a matrix singular that the frozen kernel happily eliminated,
# and a tighter one would accept a pivot the frozen kernel had already skipped.
comptime FACTOR_PIVOT_TOL: Float64 = 1e-15

# Counting threshold for "this entry of the factor is structurally present".
comptime FACTOR_NNZ_TOL: Float64 = 1e-15

# `matrix_decomp.is_symmetric`'s own default, restated so the SPD gate is one number.
comptime FACTOR_SYMMETRY_TOL: Float64 = 1e-10

# A norm is never negative, so a negative value cannot be mistaken for a small residual.
comptime FACTOR_RESIDUAL_ABSENT: Float64 = -1.0


def factor_status_name(code: Int) -> String:
    """Name for a status code, so a rejection surfaces the defect and not a number."""
    if code == FACTOR_OK:
        return "ok"
    if code == FACTOR_ERR_INVALID_DIMENSIONS:
        return "invalid_dimensions"
    if code == FACTOR_ERR_STRUCTURE:
        return "invalid_csr_structure"
    if code == FACTOR_ERR_NOT_SQUARE:
        return "not_square"
    if code == FACTOR_ERR_SINGULAR:
        return "singular"
    if code == FACTOR_ERR_NOT_FACTORED:
        return "not_factored"
    if code == FACTOR_ERR_NOT_SPD:
        return "not_symmetric_positive_definite"
    if code == FACTOR_ERR_RANK_DEFICIENT:
        return "rank_deficient"
    return "unknown_status"


def factor_strategy_name(code: Int) -> String:
    """Which solver produced the numbers."""
    if code == FACTOR_STRATEGY_SPARSE_LU:
        return "sparse_lu"
    if code == FACTOR_STRATEGY_DENSE_SOLVE:
        return "dense_mat_solve"
    if code == FACTOR_STRATEGY_CHOLESKY:
        return "cholesky"
    if code == FACTOR_STRATEGY_NORMAL_EQUATIONS:
        return "normal_equations_cholesky"
    if code == FACTOR_STRATEGY_TRIVIAL:
        return "trivial"
    if code == FACTOR_STRATEGY_NONE:
        return "none"
    return "unknown_strategy"


def factor_fallback_reason_name(code: Int) -> String:
    """Why the dense path was taken. `none` means the strategy was the primary one."""
    if code == FACTOR_FALLBACK_NONE:
        return "none"
    if code == FACTOR_FALLBACK_SMALL_SYSTEM:
        return "below_dense_threshold"
    if code == FACTOR_FALLBACK_FILL_IN:
        return "fill_in_exceeded_limit"
    return "unknown_reason"


# ── result structs ────────────────────────────────────────────────────────────


@fieldwise_init
struct SparseLU(Copyable, Movable):
    """An LU factorisation of a square CSR matrix, with the permutation exposed.

    `lower` and `upper` are flat row-major n×n. `perm` is the row permutation the
    pivoting chose: row `i` of the factored system is row `perm[i]` of A, so
    `(P A)[i] = A[perm[i]]` and a right-hand side is permuted as `pb[i] = b[perm[i]]`.
    `iperm` is its inverse (`iperm[perm[i]] == i`) and is carried rather than recomputed
    because a caller mapping a solution component back to an original row needs it and
    inverting a permutation it did not validate is exactly how an off-by-one becomes a
    wrong row.

    A copy of A's CSR arrays travels with the factorisation so that every solve can
    report `||Ax - b||` without the caller re-supplying A. Re-supplying it would let a
    caller hand in a *different* matrix from the one that was factored, which makes the
    residual — the one number that would have caught the mistake — meaningless.

    `status` is `FACTOR_ERR_SINGULAR` when `singular` is set. The arrays are still
    returned in that case, because `min_pivot` plus a look at `upper`'s diagonal is how a
    caller localises the rank deficiency; but a factorisation you must not solve with is
    reported as an error, not as a success with a warning field.
    """

    var status: Int
    var n: Int
    var singular: Bool
    var min_pivot: Float64
    var nnz_input: Int
    var fill_nnz: Int
    var lower: List[Float64]
    var upper: List[Float64]
    var perm: List[Int]
    var iperm: List[Int]
    var a_indptr: List[Int]
    var a_indices: List[Int]
    var a_values: List[Float64]

    def is_usable(self) -> Bool:
        """True only if this factorisation can be substituted through.

        Checks the array lengths as well as the status: a `SparseLU` can arrive from the
        wire, and substituting through an n that its triangles do not match would read
        past the end of a `List`, which is a process crash and not an exception.
        """
        if self.status != FACTOR_OK or self.singular:
            return False
        if self.n < 0:
            return False
        var square = self.n * self.n
        if len(self.lower) != square or len(self.upper) != square:
            return False
        return len(self.perm) == self.n


@fieldwise_init
struct SparseSolve(Copyable, Movable):
    """A solution vector, or the absence of one, plus everything needed to trust it.

    `x` is empty whenever `status != FACTOR_OK`; there is no "best effort" vector here.
    `residual_norm` is `||Ax - b||` computed from A itself, or `FACTOR_RESIDUAL_ABSENT`
    (negative, so it cannot read as a good residual) when no solution was produced.
    """

    var status: Int
    var n: Int
    var strategy: Int
    var fallback_reason: Int
    var singular: Bool
    var residual_norm: Float64
    var min_pivot: Float64
    var fill_nnz: Int
    var x: List[Float64]


@fieldwise_init
struct FactorVector(Copyable, Movable):
    """A vector with a status and its own L2 norm.

    `norm` is always `vec_norm(values)`, whatever the vector means — for a triangular
    solve that is the magnitude of the solution, for `csr_residual` it is `||Ax - b||`.
    One rule for one field, rather than a field whose meaning changes per caller.
    """

    var status: Int
    var length: Int
    var norm: Float64
    var values: List[Float64]


def _vector_absent(status: Int) -> FactorVector:
    return FactorVector(status, 0, FACTOR_RESIDUAL_ABSENT, List[Float64]())


def _lu_absent(status: Int) -> SparseLU:
    """No factorisation. `singular` stays False: it is a claim about a matrix, and a
    rejected input means we never examined one. `status` is the field that says there is
    nothing here."""
    return SparseLU(
        status,
        0,
        False,
        0.0,
        0,
        0,
        List[Float64](),
        List[Float64](),
        List[Int](),
        List[Int](),
        List[Int](),
        List[Int](),
        List[Float64](),
    )


def _solve_absent(status: Int) -> SparseSolve:
    """No solution, and n = 0 so an ignored status cannot be read as a real answer."""
    return SparseSolve(
        status,
        0,
        FACTOR_STRATEGY_NONE,
        FACTOR_FALLBACK_NONE,
        False,
        FACTOR_RESIDUAL_ABSENT,
        0.0,
        0,
        List[Float64](),
    )


def _solve_singular(n: Int, min_pivot: Float64, fill_nnz: Int) -> SparseSolve:
    """The matrix has no inverse. No vector, `singular` set, and the pivot that proves it.

    This is the whole point of the module: `mat_solve` would have returned n zeros here.
    """
    return SparseSolve(
        FACTOR_ERR_SINGULAR,
        n,
        FACTOR_STRATEGY_NONE,
        FACTOR_FALLBACK_NONE,
        True,
        FACTOR_RESIDUAL_ABSENT,
        min_pivot,
        fill_nnz,
        List[Float64](),
    )


def _solve_trivial() -> SparseSolve:
    """The 0x0 system. Its solution is the empty vector — a real answer, not an absence.

    `numeric/contract.mojo`'s rule: a count of nothing is 0, a mean of nothing does not
    exist. A system with no unknowns genuinely has exactly one solution, the empty one,
    and its residual is genuinely 0, so this returns `FACTOR_OK`.
    """
    return SparseSolve(
        FACTOR_OK,
        0,
        FACTOR_STRATEGY_TRIVIAL,
        FACTOR_FALLBACK_NONE,
        False,
        0.0,
        0.0,
        0,
        List[Float64](),
    )


# ── flat <-> nested adapters for the two frozen nested-list kernels ───────────


def _nested_from_flat(data: List[Float64], n: Int) -> List[List[Float64]]:
    """n×n nested view of a flat row-major matrix, for `cholesky` and the substitutions.

    Reads out of range as 0.0 instead of indexing blindly. Every caller here has already
    checked `len(data) == n*n`, so the guard is unreachable — but an unreachable guard
    turns a future mistake into a wrong number rather than a dead worker process.
    """
    var out = List[List[Float64]]()
    if n <= 0:
        return out^
    var total = len(data)
    for i in range(n):
        var row = List[Float64]()
        for j in range(n):
            var k = i * n + j
            if k < total:
                row.append(data[k])
            else:
                row.append(0.0)
        out.append(row^)
    return out^


def _flatten_nested(nested: List[List[Float64]], n: Int) -> List[Float64]:
    """Flat row-major n×n from a nested matrix; short rows read as 0.0."""
    var out = List[Float64]()
    if n <= 0:
        return out^
    for i in range(n):
        for j in range(n):
            if i < len(nested) and j < len(nested[i]):
                out.append(nested[i][j])
            else:
                out.append(0.0)
    return out^


def _min_diag_abs(data: List[Float64], n: Int) -> Float64:
    """Smallest |diagonal| of a flat n×n matrix. 0.0 for n <= 0 — no diagonal exists,
    and every caller handles the empty system before asking."""
    if n <= 0 or len(data) < n * n:
        return 0.0
    var smallest = fabs(data[0])
    for i in range(1, n):
        var v = fabs(data[i * n + i])
        if v < smallest:
            smallest = v
    return smallest


def _factor_nnz(lower: List[Float64], upper: List[Float64], n: Int) -> Int:
    """Structurally present entries of L (strictly below) plus U (diagonal and above).

    L's unit diagonal is not counted: it is implied by the algorithm, not stored data,
    so counting it would inflate every fill measurement by exactly n and make the
    fill-in threshold depend on the order of the matrix.
    """
    if n <= 0 or len(lower) < n * n or len(upper) < n * n:
        return 0
    var count = 0
    for i in range(n):
        for j in range(n):
            if i > j:
                if fabs(lower[i * n + j]) > FACTOR_NNZ_TOL:
                    count += 1
            else:
                if fabs(upper[i * n + j]) > FACTOR_NNZ_TOL:
                    count += 1
    return count


def _fill_from_counts(factor_nnz: Int, nnz_input: Int) -> Int:
    """Fill-in, floored at zero.

    Cancellation and explicitly stored zeros can leave the factor with fewer stored
    entries than A had, and a negative fill-in is not a thing; reporting one would make
    the threshold comparison in `csr_solve` meaningless.
    """
    var fill = factor_nnz - nnz_input
    if fill < 0:
        return 0
    return fill


def _residual(m: CSRMatrix, x: List[Float64], b: List[Float64]) -> FactorVector:
    """Ax - b and its norm, through the frozen sparse multiply.

    `csr_matvec` validates the matrix and the vector length and refuses a mismatch, so a
    residual is either right or absent — never a partial sum.
    """
    var product = csr_matvec(m, x)
    if product.status != CSR_OK or len(product.values) != len(b):
        return _vector_absent(FACTOR_ERR_INVALID_DIMENSIONS)
    var r = List[Float64]()
    for i in range(len(b)):
        r.append(product.values[i] - b[i])
    var count = len(r)
    var norm = vec_norm(r)
    return FactorVector(FACTOR_OK, count, norm, r^)


# ── triangular substitution ───────────────────────────────────────────────────


def tri_forward_solve(
    lower: List[Float64], n: Int, b: List[Float64]
) -> FactorVector:
    """Solve Lx = b for lower-triangular flat row-major n×n L.

    The frozen `forward_substitution` writes `x[i] = 0.0` when `L[i][i] == 0.0` and
    carries on, so a system with no solution comes back as a full-length vector. This
    wrapper checks every diagonal entry against `FACTOR_PIVOT_TOL` first and returns no
    vector at all when one is dead — the frozen arithmetic, an honest failure value.
    """
    if n < 0 or len(lower) != n * n or len(b) != n:
        return _vector_absent(FACTOR_ERR_INVALID_DIMENSIONS)
    if n == 0:
        return FactorVector(FACTOR_OK, 0, 0.0, List[Float64]())
    for i in range(n):
        if fabs(lower[i * n + i]) < FACTOR_PIVOT_TOL:
            return _vector_absent(FACTOR_ERR_SINGULAR)
    var nested = _nested_from_flat(lower, n)
    var x = forward_substitution(nested, b)
    if len(x) != n:
        return _vector_absent(FACTOR_ERR_INVALID_DIMENSIONS)
    var count = len(x)
    var norm = vec_norm(x)
    return FactorVector(FACTOR_OK, count, norm, x^)


def tri_back_solve(
    upper: List[Float64], n: Int, b: List[Float64]
) -> FactorVector:
    """Solve Ux = b for upper-triangular flat row-major n×n U. See `tri_forward_solve`
    for why the zero-diagonal check happens here and not inside the frozen kernel."""
    if n < 0 or len(upper) != n * n or len(b) != n:
        return _vector_absent(FACTOR_ERR_INVALID_DIMENSIONS)
    if n == 0:
        return FactorVector(FACTOR_OK, 0, 0.0, List[Float64]())
    for i in range(n):
        if fabs(upper[i * n + i]) < FACTOR_PIVOT_TOL:
            return _vector_absent(FACTOR_ERR_SINGULAR)
    var nested = _nested_from_flat(upper, n)
    var x = back_substitution(nested, b)
    if len(x) != n:
        return _vector_absent(FACTOR_ERR_INVALID_DIMENSIONS)
    var count = len(x)
    var norm = vec_norm(x)
    return FactorVector(FACTOR_OK, count, norm, x^)


# ── LU factorisation ──────────────────────────────────────────────────────────


def csr_lu_factor(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> SparseLU:
    """P A = L U for a square CSR matrix, with the permutation and a real singular flag.

    The elimination is `linalg.mat_lu` — reimplementing it would be a second definition
    of partial pivoting in the tree. What is added is: the CSR ingestion, a singularity
    test (`mat_lu` reports none), the permutation inverse, and the fill-in count.

    Singularity is decided by scanning U's diagonal rather than by watching the
    elimination, which is not observable from outside `mat_lu`. That scan is exactly
    equivalent: `mat_lu` skips a column only when every candidate pivot is already below
    1e-15, which leaves that diagonal entry below 1e-15 too.
    """
    if csr_validate_flat(indptr, indices, values, nrows, ncols) != CSR_OK:
        return _lu_absent(FACTOR_ERR_STRUCTURE)
    if nrows != ncols:
        return _lu_absent(FACTOR_ERR_NOT_SQUARE)
    var n = nrows
    if n == 0:
        # The empty matrix factors as the empty product and is not singular: its
        # determinant is 1. Reporting it singular would be a claim about a matrix that
        # has no diagonal to be deficient in.
        return SparseLU(
            FACTOR_OK,
            0,
            False,
            0.0,
            0,
            0,
            List[Float64](),
            List[Float64](),
            List[Int](),
            List[Int](),
            indptr.copy(),
            List[Int](),
            List[Float64](),
        )

    var m = csr_from_arrays(indptr, indices, values, nrows, ncols)
    var dense = csr_to_dense(m)
    if len(dense) != n * n:
        return _lu_absent(FACTOR_ERR_STRUCTURE)
    var a = mat_from_list(dense, n, n)
    var lu = mat_lu(a)
    if (
        len(lu.L.data) != n * n
        or len(lu.U.data) != n * n
        or len(lu.pivots) != n
    ):
        return _lu_absent(FACTOR_ERR_STRUCTURE)

    # Invert the permutation, validating it in the same pass. `mat_lu` builds `pivots`
    # from swaps so it is one — but `iperm[perm[i]] = i` on an unvalidated `perm` would
    # index past the end of a List, and that is a process crash, not an exception.
    var iperm = List[Int]()
    for _ in range(n):
        iperm.append(-1)
    for i in range(n):
        var p = lu.pivots[i]
        if p < 0 or p >= n or iperm[p] != -1:
            return _lu_absent(FACTOR_ERR_STRUCTURE)
        iperm[p] = i

    var min_pivot = _min_diag_abs(lu.U.data, n)
    var singular = min_pivot < FACTOR_PIVOT_TOL
    var nnz_input = len(values)
    var fill = _fill_from_counts(
        _factor_nnz(lu.L.data, lu.U.data, n), nnz_input
    )
    var status = FACTOR_OK
    if singular:
        status = FACTOR_ERR_SINGULAR
    return SparseLU(
        status,
        n,
        singular,
        min_pivot,
        nnz_input,
        fill,
        lu.L.data.copy(),
        lu.U.data.copy(),
        lu.pivots.copy(),
        iperm^,
        indptr.copy(),
        indices.copy(),
        values.copy(),
    )


def csr_lu_solve(f: SparseLU, b: List[Float64]) -> SparseSolve:
    """Solve A x = b from an existing factorisation: two substitutions, no elimination.

    This is the reason to factor at all — a second right-hand side costs O(n²) here
    against O(n³) for a fresh `csr_solve`. The residual is computed against the A that
    was factored, which travels inside `f`.
    """
    if f.status != FACTOR_OK:
        # A singular matrix stays singular: forwarding `not_factored` would hide the one
        # thing the caller most needs to know about its matrix.
        if f.singular:
            return _solve_singular(f.n, f.min_pivot, f.fill_nnz)
        return _solve_absent(FACTOR_ERR_NOT_FACTORED)
    if not f.is_usable():
        return _solve_absent(FACTOR_ERR_NOT_FACTORED)
    var n = f.n
    if len(b) != n:
        return _solve_absent(FACTOR_ERR_INVALID_DIMENSIONS)
    if n == 0:
        return _solve_trivial()

    # P b, then L y = P b, then U x = y.
    var pb = List[Float64]()
    for i in range(n):
        var p = f.perm[i]
        if p < 0 or p >= n:
            return _solve_absent(FACTOR_ERR_INVALID_DIMENSIONS)
        pb.append(b[p])

    var y = tri_forward_solve(f.lower, n, pb)
    if y.status != FACTOR_OK:
        if y.status == FACTOR_ERR_SINGULAR:
            return _solve_singular(n, f.min_pivot, f.fill_nnz)
        return _solve_absent(y.status)
    var x = tri_back_solve(f.upper, n, y.values)
    if x.status != FACTOR_OK:
        if x.status == FACTOR_ERR_SINGULAR:
            return _solve_singular(n, f.min_pivot, f.fill_nnz)
        return _solve_absent(x.status)

    var a = csr_from_arrays(f.a_indptr, f.a_indices, f.a_values, n, n)
    var r = _residual(a, x.values, b)
    var residual_norm = FACTOR_RESIDUAL_ABSENT
    if r.status == FACTOR_OK:
        residual_norm = r.norm
    return SparseSolve(
        FACTOR_OK,
        n,
        FACTOR_STRATEGY_SPARSE_LU,
        FACTOR_FALLBACK_NONE,
        False,
        residual_norm,
        f.min_pivot,
        f.fill_nnz,
        x.values.copy(),
    )


# ── one-shot drivers ──────────────────────────────────────────────────────────


def _dense_solve(
    m: CSRMatrix, b: List[Float64], n: Int, nnz_input: Int, reason: Int
) -> SparseSolve:
    """Answer through the frozen dense `mat_solve`, having first proved A is invertible.

    `mat_solve` returns n zeros for a singular matrix, and the zero vector is also the
    correct answer whenever b is zero, so its return value cannot be interrogated. The
    factorisation therefore runs first purely to obtain the pivot — one extra O(n³)
    elimination, which is affordable precisely because this path is chosen for small n.
    Rejected: trusting the zeros (indistinguishable from an answer). Rejected: open-coding
    the elimination here to get the flag for free (rule 3 — the frozen kernel stays the
    single implementation).
    """
    var dense = csr_to_dense(m)
    if len(dense) != n * n:
        return _solve_absent(FACTOR_ERR_STRUCTURE)
    var a = mat_from_list(dense, n, n)
    var lu = mat_lu(a)
    if len(lu.L.data) != n * n or len(lu.U.data) != n * n:
        return _solve_absent(FACTOR_ERR_STRUCTURE)
    var min_pivot = _min_diag_abs(lu.U.data, n)
    var fill = _fill_from_counts(
        _factor_nnz(lu.L.data, lu.U.data, n), nnz_input
    )
    if min_pivot < FACTOR_PIVOT_TOL:
        return _solve_singular(n, min_pivot, fill)

    var x = mat_solve(a, b)
    if len(x) != n:
        return _solve_absent(FACTOR_ERR_INVALID_DIMENSIONS)
    var r = _residual(m, x, b)
    var residual_norm = FACTOR_RESIDUAL_ABSENT
    if r.status == FACTOR_OK:
        residual_norm = r.norm
    return SparseSolve(
        FACTOR_OK,
        n,
        FACTOR_STRATEGY_DENSE_SOLVE,
        reason,
        False,
        residual_norm,
        min_pivot,
        fill,
        x^,
    )


def csr_solve(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    b: List[Float64],
) -> SparseSolve:
    """Solve A x = b once, choosing a strategy and saying which one it chose.

    Order of the two fallback tests is the design: the size test happens before any work
    is spent, the fill-in test can only happen after, because fill under partial pivoting
    is a property of the values. See the module docstring.
    """
    if csr_validate_flat(indptr, indices, values, nrows, ncols) != CSR_OK:
        return _solve_absent(FACTOR_ERR_STRUCTURE)
    if nrows != ncols:
        # `mat_solve` returns an empty list here, which is also what it returns for a
        # length mismatch on b; a caller needs to know which of its arguments to fix.
        return _solve_absent(FACTOR_ERR_NOT_SQUARE)
    if len(b) != nrows:
        return _solve_absent(FACTOR_ERR_INVALID_DIMENSIONS)
    var n = nrows
    if n == 0:
        return _solve_trivial()

    var m = csr_from_arrays(indptr, indices, values, nrows, ncols)
    if n < FACTOR_DENSE_MIN_N:
        return _dense_solve(
            m, b, n, len(values), FACTOR_FALLBACK_SMALL_SYSTEM
        )

    var f = csr_lu_factor(indptr, indices, values, nrows, ncols)
    if f.status != FACTOR_OK:
        if f.singular:
            return _solve_singular(f.n, f.min_pivot, f.fill_nnz)
        return _solve_absent(f.status)
    if Float64(f.fill_nnz) > FACTOR_FILL_LIMIT_MULTIPLE * Float64(f.nnz_input):
        # The factorisation is dense in all but name, so the answer comes from the
        # reference solver and `fallback_reason` tells the caller that holding on to a
        # factorisation of this matrix would save it nothing.
        var fallback = _dense_solve(
            m, b, n, len(values), FACTOR_FALLBACK_FILL_IN
        )
        return SparseSolve(
            fallback.status,
            fallback.n,
            fallback.strategy,
            fallback.fallback_reason,
            fallback.singular,
            fallback.residual_norm,
            f.min_pivot,
            f.fill_nnz,
            fallback.x.copy(),
        )
    return csr_lu_solve(f, b)


def csr_solve_spd(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    b: List[Float64],
) -> SparseSolve:
    """Solve A x = b for symmetric positive-definite A, via the frozen Cholesky.

    Half the work of LU and no pivoting, but it is a separate entry point rather than an
    automatic branch inside `csr_solve`: detecting SPD costs a full Cholesky attempt, and
    a driver that silently changes algorithm based on the data gives two callers with the
    same matrix class different numerics. A caller that knows its matrix is a Laplacian
    or a Gram matrix asks for this; everyone else gets LU.

    `matrix_decomp.cholesky` returns an empty list for a non-positive-definite matrix,
    which is the one frozen failure value in this area that is already honest — an empty
    L cannot be mistaken for a factor. It becomes `FACTOR_ERR_NOT_SPD` here, and note
    that not-SPD is *not* singular: an indefinite matrix can be perfectly invertible, so
    `singular` stays False and the caller is pointed at `csr_solve`.
    """
    if csr_validate_flat(indptr, indices, values, nrows, ncols) != CSR_OK:
        return _solve_absent(FACTOR_ERR_STRUCTURE)
    if nrows != ncols:
        return _solve_absent(FACTOR_ERR_NOT_SQUARE)
    if len(b) != nrows:
        return _solve_absent(FACTOR_ERR_INVALID_DIMENSIONS)
    var n = nrows
    if n == 0:
        return _solve_trivial()

    var m = csr_from_arrays(indptr, indices, values, nrows, ncols)
    var dense = csr_to_dense(m)
    if len(dense) != n * n:
        return _solve_absent(FACTOR_ERR_STRUCTURE)
    var nested = _nested_from_flat(dense, n)
    if not is_symmetric(nested, FACTOR_SYMMETRY_TOL):
        return _solve_absent(FACTOR_ERR_NOT_SPD)
    var lower_nested = cholesky(nested)
    if len(lower_nested) != n:
        return _solve_absent(FACTOR_ERR_NOT_SPD)
    var lower = _flatten_nested(lower_nested, n)

    var solved = _solve_lower_upper_pair(lower, n, b)
    if solved.status != FACTOR_OK:
        return _solve_absent(solved.status)

    # Fill-in for a Cholesky is measured against A's stored lower triangle, since that is
    # the only half L can be compared with; using all of nnz(A) would report negative
    # fill for every symmetric matrix.
    var lower_input = 0
    for i in range(n):
        for k in range(indptr[i], indptr[i + 1]):
            if indices[k] <= i:
                lower_input += 1
    var factor_nnz = 0
    for i in range(n):
        for j in range(i + 1):
            if fabs(lower[i * n + j]) > FACTOR_NNZ_TOL:
                factor_nnz += 1

    var r = _residual(m, solved.values, b)
    var residual_norm = FACTOR_RESIDUAL_ABSENT
    if r.status == FACTOR_OK:
        residual_norm = r.norm
    return SparseSolve(
        FACTOR_OK,
        n,
        FACTOR_STRATEGY_CHOLESKY,
        FACTOR_FALLBACK_NONE,
        False,
        residual_norm,
        _min_diag_abs(lower, n),
        _fill_from_counts(factor_nnz, lower_input),
        solved.values.copy(),
    )


def _solve_lower_upper_pair(
    lower: List[Float64], n: Int, b: List[Float64]
) -> FactorVector:
    """Solve L Lᵀ x = b given L. The transpose comes from the frozen `mat_transpose`.

    Used by both Cholesky paths. Building Lᵀ by hand would be three lines, but
    `mat_transpose` is the tree's transpose and this file's job is composition.
    """
    var y = tri_forward_solve(lower, n, b)
    if y.status != FACTOR_OK:
        return _vector_absent(y.status)
    var upper = mat_transpose(mat_from_list(lower, n, n))
    return tri_back_solve(upper.data, n, y.values)


def csr_least_squares(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    b: List[Float64],
) -> SparseSolve:
    """Minimise ||A x - b|| for a rectangular CSR A, via the normal equations.

    AᵀA is formed with the frozen `mat_mul(mat_transpose(A), A)` and factored with the
    frozen `cholesky`; Aᵀb is `csr_matvec` on `csr_transpose(A)`, so the sparse
    structure is used for the right-hand side even though the Gram matrix is dense.

    Rank deficiency is reported, never papered over. When A's columns are dependent AᵀA
    is singular, the minimiser is not unique, and there is no vector to return — the
    Cholesky's empty result becomes `FACTOR_ERR_RANK_DEFICIENT` and `x` is empty. Handing
    back the pseudo-inverse solution would require an SVD the tree does not have, and
    handing back `mat_solve`'s zeros would be the failure this whole module exists to
    remove.

    Normal equations square the condition number, which is a real cost. It is accepted
    here because the alternative — a sparse QR — is a much larger addition, and because
    `residual_norm` on every result lets a caller detect the loss rather than assume it
    away.
    """
    if csr_validate_flat(indptr, indices, values, nrows, ncols) != CSR_OK:
        return _solve_absent(FACTOR_ERR_STRUCTURE)
    if len(b) != nrows:
        return _solve_absent(FACTOR_ERR_INVALID_DIMENSIONS)
    var m_rows = nrows
    var n = ncols
    var a = csr_from_arrays(indptr, indices, values, nrows, ncols)
    if n == 0:
        # No unknowns: the empty x is the unique minimiser and its residual is ||b||.
        var norm = vec_norm(b)
        return SparseSolve(
            FACTOR_OK,
            0,
            FACTOR_STRATEGY_TRIVIAL,
            FACTOR_FALLBACK_NONE,
            False,
            norm,
            0.0,
            0,
            List[Float64](),
        )

    var dense = csr_to_dense(a)
    if len(dense) != m_rows * n:
        return _solve_absent(FACTOR_ERR_STRUCTURE)
    var a_dense = mat_from_list(dense, m_rows, n)
    var gram = mat_mul(mat_transpose(a_dense), a_dense)
    if len(gram.data) != n * n:
        return _solve_absent(FACTOR_ERR_STRUCTURE)
    var lower_nested = cholesky(_nested_from_flat(gram.data, n))
    if len(lower_nested) != n:
        return _solve_absent(FACTOR_ERR_RANK_DEFICIENT)
    var lower = _flatten_nested(lower_nested, n)

    var rhs = csr_matvec(csr_transpose(a), b)
    if rhs.status != CSR_OK or len(rhs.values) != n:
        return _solve_absent(FACTOR_ERR_INVALID_DIMENSIONS)
    var solved = _solve_lower_upper_pair(lower, n, rhs.values)
    if solved.status != FACTOR_OK:
        return _solve_absent(solved.status)

    var r = _residual(a, solved.values, b)
    var residual_norm = FACTOR_RESIDUAL_ABSENT
    if r.status == FACTOR_OK:
        residual_norm = r.norm
    var factor_nnz = 0
    for i in range(n):
        for j in range(i + 1):
            if fabs(lower[i * n + j]) > FACTOR_NNZ_TOL:
                factor_nnz += 1
    return SparseSolve(
        FACTOR_OK,
        n,
        FACTOR_STRATEGY_NORMAL_EQUATIONS,
        FACTOR_FALLBACK_NONE,
        False,
        residual_norm,
        _min_diag_abs(lower, n),
        _fill_from_counts(factor_nnz, len(values)),
        solved.values.copy(),
    )


def csr_residual(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    x: List[Float64],
    b: List[Float64],
) -> FactorVector:
    """Ax - b and ||Ax - b|| for any candidate x, from A's CSR arrays.

    Exposed so a caller can audit a solution it got somewhere else — including one from
    `mat_solve`, whose zeros vector this will immediately expose as having a residual of
    ||b||.
    """
    if csr_validate_flat(indptr, indices, values, nrows, ncols) != CSR_OK:
        return _vector_absent(FACTOR_ERR_STRUCTURE)
    if len(x) != ncols or len(b) != nrows:
        return _vector_absent(FACTOR_ERR_INVALID_DIMENSIONS)
    return _residual(
        csr_from_arrays(indptr, indices, values, nrows, ncols), x, b
    )
