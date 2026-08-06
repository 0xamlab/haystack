"""
sparse_numerics.spmv — sparse products over the CSR layout. Zero Python.

What this adds
--------------
`sparse_numerics.csr` gives the layout, its validation gate and `A @ x`. This module
adds the products that need more than one pass over one matrix: `A^T y` without ever
building `A^T`, a row against a sparse vector, `A * B`, `A + B`, a scale, the Frobenius
norm, and a compensated `A @ x` for rows whose terms cancel catastrophically.

Shape policy: an absent product is empty, never short
-----------------------------------------------------
`tensor2d.m2_matvec` returns an empty list when `a.cols != len(x)`; `sparse.sparse_matvec`
performs no check at all and scatters into `result[e.row]` with `vec[e.col]`, which on a
short vector reads past the end and takes down the process. This module follows the
first: every dimension argument is checked against the real list lengths before any
index, and a rejected call returns a status plus an empty payload. A product of the
wrong length is the failure mode that matters, because it is arithmetically plausible —
`A^T y` for a 3x4 `A` with `len(y) == 4` would silently produce a 4-vector of nonsense if
the check were written against `ncols` instead of `nrows`.

Which frozen kernel each operation is
-------------------------------------
* the row-against-sparse-vector inner product is `sparse_vector.sv_dot`
* the L2 over a values buffer is `sparse_vector.sv_norm`
* the scale is `sparse_vector.sv_scale`
* the compensated row sum is `numerical_stability.kahan_sum`
* summing duplicate coordinates is `csr.csr_coalesce`, the one place in this package
  that sums duplicates, so `A + B` cannot disagree with `csr_from_coo` about what a
  repeated coordinate means

`sv_dot` needs STRICTLY ascending indices, and that is verified, not trusted
---------------------------------------------------------------------------
`sv_dot` is a two-pointer merge. On a match it advances *both* pointers, so it is wrong
in two distinct ways on a non-canonical operand: unsorted indices make it skip matches,
and a *duplicated* index makes it consume only the first copy. Both return a too-small
number with no indication. So a row is admissible for `sv_dot` only if its indices are
strictly increasing — sorted *and* free of duplicates.

That precondition is checked by scanning the operand, not by reading `sorted_indices`.
The flag is a claim that travels with the arrays, and `csr_from_arrays` deliberately sets
it False for anything supplied over the wire; gating on the flag would therefore reject
every genuinely-sorted matrix that arrived through a driver, which is all of them. The
scan costs O(row_nnz + len(idx_b)), the same order as the dot it guards, so verifying is
asymptotically free — and unlike the flag it cannot be wrong.

Statuses
--------
`csr`'s codes are reused unchanged, so one vocabulary covers the package; the two codes
added here start at 20 to stay disjoint. For a two-operand call the first defective
operand's status is returned and A is checked before B, so a caller with two broken
matrices hears about A first and fixes them one at a time.

One wire name per operation
---------------------------
`csr.csr_matvec_driver` is already the flat entry point for `A @ x`, so no second one is
exported here; a duplicate wire name would be two functions that must never disagree.
The typed `spmv_matvec` exists only so a Mojo caller composing this module gets all its
results in this module's result types.
"""
from numerical_stability import kahan_sum
from sparse_numerics.csr import (
    CSRMatrix,
    CSR_ERR_INDEX_OUT_OF_RANGE,
    CSR_ERR_INVALID_DIMENSIONS,
    CSR_ERR_LENGTH_MISMATCH,
    CSR_OK,
    csr_coalesce,
    csr_empty,
    csr_from_arrays,
    csr_matvec,
    csr_sort_indices,
    csr_status_name,
    csr_validate,
)
from sparse_vector import sv_dot, sv_norm, sv_scale

# ── status codes ──────────────────────────────────────────────────────────────
# Disjoint from `csr`'s 0-8 so a status can be routed to one namer without ambiguity.

comptime SPMV_ERR_NOT_STRICTLY_SORTED: Int = 20
comptime SPMV_ERR_SHAPE_MISMATCH: Int = 21


def spmv_status_name(code: Int) -> String:
    """Name for a status code from this module or from `csr`.

    Checks this module's codes first, because `csr_status_name` answers
    "unknown_status" for them and a delegation in the other order would lose them.
    """
    if code == SPMV_ERR_NOT_STRICTLY_SORTED:
        return "operand_not_strictly_sorted"
    if code == SPMV_ERR_SHAPE_MISMATCH:
        return "operand_shape_mismatch"
    return csr_status_name(code)


# ── return-only result structs ────────────────────────────────────────────────
# Declared here, not imported: `apps/runtime/mojo_inventory.py` reads struct specs one
# file at a time, so a driver returning `csr.CSRVectorResult` would be dropped from the
# runtime contract silently. Flat fields only, for the same reason.


@fieldwise_init
struct SpmvVector(Copyable, Movable):
    """A dense Float64 result vector plus the status of the request.

    `length` is carried explicitly so a caller reading a reply can tell the product of a
    0-row matrix (status ok, length 0) from a rejected call (status set, length 0).
    """

    var status: Int
    var length: Int
    var values: List[Float64]


@fieldwise_init
struct SpmvScalar(Copyable, Movable):
    """A single Float64 answer plus status.

    `value` is 0.0 whenever `status != CSR_OK`, and that 0.0 means nothing: a norm or a
    dot product that was never computed is absent, and the status is the only field that
    says whether the number is an answer.
    """

    var status: Int
    var value: Float64


@fieldwise_init
struct SpmvMatrix(Copyable, Movable):
    """A CSR result matrix plus status. Always row layout — nothing here returns CSC."""

    var status: Int
    var nrows: Int
    var ncols: Int
    var nnz: Int
    var coalesced: Bool
    var sorted_indices: Bool
    var indptr: List[Int]
    var indices: List[Int]
    var values: List[Float64]


def _vector_invalid(status: Int) -> SpmvVector:
    return SpmvVector(status, 0, List[Float64]())


def _matrix_invalid(status: Int) -> SpmvMatrix:
    """No matrix. Zero shape, so an ignored status cannot read as a real 0-nnz matrix."""
    return SpmvMatrix(
        status, 0, 0, 0, True, True, List[Int](), List[Int](), List[Float64]()
    )


def _matrix_from_csr(m: CSRMatrix, status: Int) -> SpmvMatrix:
    return SpmvMatrix(
        status,
        m.nrows,
        m.ncols,
        m.nnz(),
        m.coalesced,
        m.sorted_indices,
        m.indptr.copy(),
        m.indices.copy(),
        m.values.copy(),
    )


def _is_strictly_ascending(indices: List[Int]) -> Bool:
    """True when every index is greater than the one before it.

    Strict, not merely non-decreasing: `sv_dot` advances both pointers on a match, so a
    repeated index contributes once and the rest of the run is silently dropped.
    """
    for k in range(1, len(indices)):
        if indices[k] <= indices[k - 1]:
            return False
    return True


# ── matrix-vector products ────────────────────────────────────────────────────


def spmv_matvec(m: CSRMatrix, x: List[Float64]) -> SpmvVector:
    """A @ x. Delegates to `csr.csr_matvec` and restates its result in this module's type.

    Not a second implementation: the arithmetic, the validation and the dimension policy
    are all `csr_matvec`'s, so the two cannot drift. The only work here is the type,
    which is what lets a caller handle every result in this module uniformly.
    """
    var inner = csr_matvec(m, x)
    return SpmvVector(inner.status, inner.length, inner.values.copy())


def spmv_matvec_transpose(m: CSRMatrix, y: List[Float64]) -> SpmvVector:
    """A^T @ y, without materialising A^T.

    A^T's rows are A's columns, so the product is a scatter: each stored `(i, j, v)`
    contributes `v * y[i]` to output slot `j`. That reads A exactly once in its stored
    order, where transposing first would cost a second O(nnz + max(nrows, ncols)) pass
    and a second copy of the matrix — real money in the iterative solvers that need both
    `A x` and `A^T y` every iteration.

    `y` is indexed by ROW, so its length must be `nrows`; the output length is `ncols`.
    Checking against `ncols` instead would accept a wrong-length `y` on any matrix that
    happens to be square-ish and return a plausible vector of nonsense.

    Duplicate coordinates add, matching `to_dense`'s `+=` and therefore `csr_matvec`.
    """
    var status = csr_validate(m)
    if status != CSR_OK:
        return _vector_invalid(status)
    if len(y) != m.nrows:
        return _vector_invalid(CSR_ERR_INVALID_DIMENSIONS)
    var out = List[Float64]()
    for _ in range(m.ncols):
        out.append(0.0)
    for i in range(m.nrows):
        var yi = y[i]
        for k in range(m.indptr[i], m.indptr[i + 1]):
            out[m.indices[k]] += m.values[k] * yi
    var count = len(out)
    return SpmvVector(CSR_OK, count, out^)


def spmv_matvec_kahan(m: CSRMatrix, x: List[Float64]) -> SpmvVector:
    """A @ x with a compensated sum per row.

    Same dimension policy and same terms as `spmv_matvec`; only the accumulation differs.
    A row that mixes magnitudes — `1e16, 1, 1, -1e16` — loses both unit terms to rounding
    under a running sum and returns 0.0 instead of 2.0. That is a wrong answer that looks
    like a right one, which is the whole reason this variant is separate rather than the
    default: it costs one `List[Float64]` per row, and most rows do not need it.

    The products are collected and handed to the frozen `kahan_sum` rather than
    compensating inline. Inlining would save the allocation and would put a second
    definition of compensated summation in the tree, which is the trade rule 3 forbids.
    """
    var status = csr_validate(m)
    if status != CSR_OK:
        return _vector_invalid(status)
    if len(x) != m.ncols:
        return _vector_invalid(CSR_ERR_INVALID_DIMENSIONS)
    var out = List[Float64]()
    for i in range(m.nrows):
        var products = List[Float64]()
        for k in range(m.indptr[i], m.indptr[i + 1]):
            products.append(m.values[k] * x[m.indices[k]])
        out.append(kahan_sum(products))
    var count = len(out)
    return SpmvVector(CSR_OK, count, out^)


# ── row against a sparse vector ───────────────────────────────────────────────


def spmv_row_dot(
    m: CSRMatrix, row: Int, idx_b: List[Int], val_b: List[Float64]
) -> SpmvScalar:
    """Inner product of row `row` with the sparse vector `(idx_b, val_b)`.

    O(row_nnz + len(idx_b)) via `sv_dot`'s merge — no dense workspace, which is the point
    of doing this against a sparse vector rather than densifying one side.

    Both operands must be strictly ascending; see the module docstring for why that is
    verified rather than read off `sorted_indices`, and why a merely-sorted row with a
    duplicate column is also rejected. A caller holding a rejected matrix fixes it with
    `csr.csr_coalesce`; this function will not silently canonicalise on its behalf,
    because that would hide a per-row sort inside a dot product and make a loop over
    every row quadratic in the row width.

    `idx_b` must index columns of `m`. An index outside `[0, ncols)` is not a zero
    column, it is a vector from a different space, and `sv_dot` would quietly treat it as
    a non-match.

    The row's own arrays are copied out with a span loop instead of via
    `csr.csr_row_slice`, because that entry point re-validates the whole matrix — O(nnz)
    — and calling it here would make a loop over all rows quadratic. The reuse that
    carries the arithmetic is `sv_dot`.
    """
    var status = csr_validate(m)
    if status != CSR_OK:
        return SpmvScalar(status, 0.0)
    if row < 0 or row >= m.nrows:
        return SpmvScalar(CSR_ERR_INVALID_DIMENSIONS, 0.0)
    if len(idx_b) != len(val_b):
        return SpmvScalar(CSR_ERR_LENGTH_MISMATCH, 0.0)
    for k in range(len(idx_b)):
        if idx_b[k] < 0 or idx_b[k] >= m.ncols:
            return SpmvScalar(CSR_ERR_INDEX_OUT_OF_RANGE, 0.0)
    if not _is_strictly_ascending(idx_b):
        return SpmvScalar(SPMV_ERR_NOT_STRICTLY_SORTED, 0.0)

    var idx_a = List[Int]()
    var val_a = List[Float64]()
    for k in range(m.indptr[row], m.indptr[row + 1]):
        idx_a.append(m.indices[k])
        val_a.append(m.values[k])
    if not _is_strictly_ascending(idx_a):
        return SpmvScalar(SPMV_ERR_NOT_STRICTLY_SORTED, 0.0)
    return SpmvScalar(CSR_OK, sv_dot(idx_a, val_a, idx_b, val_b))


# ── scale, add, product, norm ─────────────────────────────────────────────────


def spmv_scale(m: CSRMatrix, alpha: Float64) -> CSRMatrix:
    """alpha * A. Pattern unchanged; an invalid matrix has no scale (0x0 empty).

    `alpha == 0.0` leaves every stored value as an explicit zero rather than emptying the
    matrix, matching `csr_coalesce`'s refusal to prune: pruning changes the pattern any
    symbolic factorisation was computed from, and is a separate decision with a separate
    cost.

    Both flags carry over untouched. Scaling can neither sort indices nor merge
    duplicates, so claiming either would be a lie, and clearing either would throw away
    a property the caller had already paid for.
    """
    if csr_validate(m) != CSR_OK:
        return csr_empty(0, 0)
    return CSRMatrix(
        m.indptr.copy(),
        m.indices.copy(),
        sv_scale(m.values, alpha),
        m.nrows,
        m.ncols,
        m.coalesced,
        m.sorted_indices,
    )


def spmv_add(a: CSRMatrix, b: CSRMatrix) -> CSRMatrix:
    """A + B for matrices of the same shape. Result is canonical. 0x0 empty on failure.

    Implemented as "concatenate each row's stored entries, then coalesce". The alternative
    — a two-pointer merge per row — needs both operands already sorted and would put a
    second place in this package that adds coincident coordinates. One summation site is
    why `A + B` and `csr_from_coo` cannot disagree about a duplicate.

    A's entries precede B's within a row, so a cancelling pair sums in A-then-B order.
    That is deterministic rather than arbitrary, which matters when the sum is exact only
    in one order.

    A stored zero produced by cancellation is kept, per `csr_coalesce`.
    """
    if csr_validate(a) != CSR_OK or csr_validate(b) != CSR_OK:
        return csr_empty(0, 0)
    if a.nrows != b.nrows or a.ncols != b.ncols:
        return csr_empty(0, 0)
    var indptr = List[Int]()
    indptr.append(0)
    var indices = List[Int]()
    var values = List[Float64]()
    for i in range(a.nrows):
        for k in range(a.indptr[i], a.indptr[i + 1]):
            indices.append(a.indices[k])
            values.append(a.values[k])
        for k in range(b.indptr[i], b.indptr[i + 1]):
            indices.append(b.indices[k])
            values.append(b.values[k])
        indptr.append(len(values))
    # Row-grouped and duplicate-bearing, exactly the shape `csr_coalesce` expects; both
    # flags are False because neither holds yet.
    var merged = CSRMatrix(
        indptr^, indices^, values^, a.nrows, a.ncols, False, False
    )
    return csr_coalesce(merged)


def spmv_spgemm(a: CSRMatrix, b: CSRMatrix) -> CSRMatrix:
    """A(m x k) * B(k x n) in CSR. Canonical result. 0x0 empty on failure.

    Row-wise expansion (Gustavson): for each stored `a[i,k]`, accumulate `a[i,k] * B[k,:]`
    into a per-row workspace keyed by column. Total work is proportional to the actual
    multiply-adds, so a sparse product stays sparse — structural zeros are never stored.

    Rejected: one `sv_dot` per (row of A, column of B) pair. That is the natural use of
    the merge kernel and it is O(m * n) merges regardless of how few products are
    nonzero, which defeats the reason for a sparse layout. `sv_dot` is the right kernel
    for `spmv_row_dot`, where the caller has already chosen the one row it wants.

    The workspace is an O(n) marker array reset per row by walking only the columns that
    row touched, so it is allocated once for the whole product rather than per row. The
    cost is O(b.ncols) memory even for a single-entry row — the standard trade, and the
    reason this is a driver over CSR rather than something to run on a matrix with
    billions of columns.

    First-touch order is not column order, so the raw output is unsorted. It is passed
    through `csr_sort_indices` (two counting-sort transposes) rather than returned as-is:
    an unsorted result is a correct matrix that silently breaks the next `sv_dot` in the
    chain. Duplicates cannot occur — the accumulator merges them as it goes — so the
    result is coalesced without a coalesce pass.
    """
    if csr_validate(a) != CSR_OK or csr_validate(b) != CSR_OK:
        return csr_empty(0, 0)
    if a.ncols != b.nrows:
        return csr_empty(0, 0)

    var n = b.ncols
    # -1 means "this column is not yet in the current output row"; otherwise it holds the
    # column's position in `out_values`, so a repeat hit accumulates in place.
    var slot_of = List[Int]()
    for _ in range(n):
        slot_of.append(-1)

    var out_indptr = List[Int]()
    out_indptr.append(0)
    var out_indices = List[Int]()
    var out_values = List[Float64]()

    for i in range(a.nrows):
        var row_start = len(out_indices)
        for ka in range(a.indptr[i], a.indptr[i + 1]):
            var k = a.indices[ka]
            var aik = a.values[ka]
            for kb in range(b.indptr[k], b.indptr[k + 1]):
                var j = b.indices[kb]
                var slot = slot_of[j]
                if slot < 0:
                    slot_of[j] = len(out_indices)
                    out_indices.append(j)
                    out_values.append(aik * b.values[kb])
                else:
                    out_values[slot] += aik * b.values[kb]
        for p in range(row_start, len(out_indices)):
            slot_of[out_indices[p]] = -1
        out_indptr.append(len(out_values))

    var unsorted = CSRMatrix(
        out_indptr^, out_indices^, out_values^, a.nrows, n, True, False
    )
    return csr_sort_indices(unsorted)


def spmv_frobenius_norm(m: CSRMatrix) -> SpmvScalar:
    """sqrt(sum of squares of the matrix entries), via `sv_norm`.

    Coalesces first when the matrix does not already claim to be coalesced. This is the
    whole content of the function: `sv_norm` squares each STORED value, and squaring is
    not additive, so a matrix holding 3 and 4 at one coordinate has stored-value norm 5
    and true Frobenius norm 7. Handing the raw buffer to `sv_norm` would be a plausible
    wrong number on every non-canonical matrix — which is every matrix that arrived over
    the wire, since `csr_from_arrays` claims nothing.

    Explicit stored zeros contribute nothing, so keeping them costs only time.
    """
    var status = csr_validate(m)
    if status != CSR_OK:
        return SpmvScalar(status, 0.0)
    if m.coalesced:
        return SpmvScalar(CSR_OK, sv_norm(m.values))
    var canonical = csr_coalesce(m)
    return SpmvScalar(CSR_OK, sv_norm(canonical.values))


# ── flat-list drivers ─────────────────────────────────────────────────────────
# Lists and scalars in, a status-bearing struct declared above out. Every one validates
# its dimension arguments against the real list lengths before indexing anything: the
# generated A-Z suite calls each of these with 5-element lists and 5 for every Int, and
# an unguarded `indptr[nrows]` on a 5-element list is an uncatchable process crash.
#
# The two ten-parameter signatures below pack several parameters per line ON PURPOSE.
# `mojo_inventory._parse_runtime_function_specs` gives a signature at most nine
# continuation lines before it abandons the parse, and an abandoned parse drops the
# function from the runtime contract and the dispatch with no error at all. One
# parameter per line puts them over that limit, so re-wrapping these is not cosmetic.


def spmv_matvec_transpose_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    y: List[Float64],
) -> SpmvVector:
    """A^T @ y for the CSR described by these arrays. `len(y)` must be `nrows`."""
    return spmv_matvec_transpose(
        csr_from_arrays(indptr, indices, values, nrows, ncols), y
    )


def spmv_matvec_kahan_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    x: List[Float64],
) -> SpmvVector:
    """A @ x with a compensated sum per row. `len(x)` must be `ncols`."""
    return spmv_matvec_kahan(
        csr_from_arrays(indptr, indices, values, nrows, ncols), x
    )


def spmv_row_dot_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    row: Int,
    idx_b: List[Int],
    val_b: List[Float64],
) -> SpmvScalar:
    """Row `row` of this CSR against the sparse vector `(idx_b, val_b)`.

    Rejects a non-canonical row with `operand_not_strictly_sorted` instead of returning
    `sv_dot`'s too-small merge; call `csr_coalesce_driver` first.
    """
    return spmv_row_dot(
        csr_from_arrays(indptr, indices, values, nrows, ncols),
        row,
        idx_b,
        val_b,
    )


def spmv_frobenius_norm_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> SpmvScalar:
    """Frobenius norm, coalescing duplicates first so the answer is the matrix's."""
    var m = csr_from_arrays(indptr, indices, values, nrows, ncols)
    return spmv_frobenius_norm(m)


def spmv_scale_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    alpha: Float64,
) -> SpmvMatrix:
    """alpha * A. Validates here so the reply carries the defect, not an empty matrix."""
    var m = csr_from_arrays(indptr, indices, values, nrows, ncols)
    var status = csr_validate(m)
    if status != CSR_OK:
        return _matrix_invalid(status)
    return _matrix_from_csr(spmv_scale(m, alpha), CSR_OK)


def spmv_add_driver(
    a_indptr: List[Int], a_indices: List[Int], a_values: List[Float64],
    a_nrows: Int, a_ncols: Int,
    b_indptr: List[Int], b_indices: List[Int], b_values: List[Float64],
    b_nrows: Int, b_ncols: Int,
) -> SpmvMatrix:
    """A + B, canonical. A is validated before B, so its defect is reported first."""
    var a = csr_from_arrays(a_indptr, a_indices, a_values, a_nrows, a_ncols)
    var status_a = csr_validate(a)
    if status_a != CSR_OK:
        return _matrix_invalid(status_a)
    var b = csr_from_arrays(b_indptr, b_indices, b_values, b_nrows, b_ncols)
    var status_b = csr_validate(b)
    if status_b != CSR_OK:
        return _matrix_invalid(status_b)
    if a_nrows != b_nrows or a_ncols != b_ncols:
        return _matrix_invalid(SPMV_ERR_SHAPE_MISMATCH)
    return _matrix_from_csr(spmv_add(a, b), CSR_OK)


def spmv_spgemm_driver(
    a_indptr: List[Int], a_indices: List[Int], a_values: List[Float64],
    a_nrows: Int, a_ncols: Int,
    b_indptr: List[Int], b_indices: List[Int], b_values: List[Float64],
    b_nrows: Int, b_ncols: Int,
) -> SpmvMatrix:
    """A * B, canonical. `a_ncols` must equal `b_nrows` or the status says so."""
    var a = csr_from_arrays(a_indptr, a_indices, a_values, a_nrows, a_ncols)
    var status_a = csr_validate(a)
    if status_a != CSR_OK:
        return _matrix_invalid(status_a)
    var b = csr_from_arrays(b_indptr, b_indices, b_values, b_nrows, b_ncols)
    var status_b = csr_validate(b)
    if status_b != CSR_OK:
        return _matrix_invalid(status_b)
    if a_ncols != b_nrows:
        return _matrix_invalid(SPMV_ERR_SHAPE_MISMATCH)
    return _matrix_from_csr(spmv_spgemm(a, b), CSR_OK)
