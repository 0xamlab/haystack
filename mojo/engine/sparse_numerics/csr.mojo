"""
sparse_numerics.csr — CSR and CSC over the frozen COO builder. Zero Python.

Layout
------
CSR is `indptr` (length nrows+1), `indices` (length nnz, column per stored value) and
`values` (length nnz). Row `i` occupies `[indptr[i], indptr[i+1])`. CSC is the same
three arrays transposed: `colptr` (length ncols+1) and `row_indices`.

Two flags travel with the arrays instead of being recomputed
------------------------------------------------------------
`sorted_indices` and `coalesced` are stored, not inferred. Inferring them costs a full
O(nnz) scan on every call, and — worse — an inferred flag cannot distinguish "I checked
and it holds" from "I have not checked", so a driver that needs canonical input would
either re-canonicalise every time or trust an unverified layout. The frozen COO type
guarantees neither property (duplicates are legal, order is insertion order), so a CSR
built from COO must *establish* them, and every operation here states what it preserves.

They are separate flags because they are separate properties: transpose produces sorted
indices from unsorted input for free, but cannot remove duplicates.

Duplicate policy is inherited, not invented
-------------------------------------------
`sparse.SparseMatrixCOO.to_dense` accumulates with `+=`, so two entries at the same
`(row, col)` sum. `csr_from_coo` therefore sums duplicates rather than keeping the last
or rejecting the input: any other choice would make the compressed layout denote a
different matrix from the COO it came from, which is the one thing a format conversion
must never do. `csr_to_dense` is implemented *through* `to_dense` for the same reason —
the frozen kernel stays the single definition of what a COO means.

Coalescing does not drop stored zeros. `5 + (-5)` leaves an explicit zero in the
structure, matching the COO convention that `nnz` counts what is stored, not what is
nonzero. Pruning is a separate decision with a separate cost (it invalidates any
symbolic factorisation computed from the pattern) and is not folded in here.

Out-of-range coordinates are skipped, not indexed
-------------------------------------------------
COO accepts `add_entry(row, col, val)` with no bounds check, so a COO in hand may carry
coordinates outside its own declared shape; `to_dense` would crash on one. Construction
here drops those entries and the flat drivers report how many were dropped, because a
process crash is not a diagnosable error and a silently resized matrix is worse.

Every entry point validates its dimension arguments against the real list lengths before
indexing. A structurally broken matrix has no transpose, no dense image and no canonical
form, so those return an empty result and the drivers return a status code naming the
defect — never a plausible-looking wrong matrix.
@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_sparse_numerics_csr.mojo
benchmark: benchmarks/mojo_benchmarks/bench_sparse_and_graph.mojo
docs: none
version_introduced: pre_manifest
deprecation_state: active
@endcapability
"""
from sparse import COOEntry, SparseMatrixCOO, sparse_from_dense

# ── status codes ──────────────────────────────────────────────────────────────
# Distinct per defect: a caller that gets a rejection needs to know which of its arrays
# is wrong, and a single "invalid" code would send it looking at all five.

comptime CSR_OK: Int = 0
comptime CSR_ERR_SHAPE: Int = 1
comptime CSR_ERR_LENGTH_MISMATCH: Int = 2
comptime CSR_ERR_INDPTR_LENGTH: Int = 3
comptime CSR_ERR_INDPTR_START: Int = 4
comptime CSR_ERR_INDPTR_NOT_MONOTONIC: Int = 5
comptime CSR_ERR_INDPTR_TAIL: Int = 6
comptime CSR_ERR_INDEX_OUT_OF_RANGE: Int = 7
comptime CSR_ERR_INVALID_DIMENSIONS: Int = 8
comptime CSR_ERR_DIMENSION_TOO_LARGE: Int = 9

# A result carries which axis its pointer array indexes, rather than leaving the caller
# to remember that a CSC came back in the same three arrays as a CSR.
comptime CSR_LAYOUT_ROW: Int = 0
comptime CSR_LAYOUT_COL: Int = 1

# The largest nrows/ncols a matrix may declare. A transpose or a CSC conversion allocates
# one pointer entry PER COLUMN regardless of how few non-zeros there are, so an
# unbounded ncols is an allocation bomb: `csr_transpose_driver([0], [], [], 0, 10**12)`
# is a structurally VALID empty matrix that asks for an 8 TB indptr. There is no shape
# check that catches it, because the shape is consistent — only a declared ceiling does.
# 2^26 keeps the worst-case pointer array at ~512 MB, which the 512 MiB resident-dataset
# budget in algenta_runtime.session already treats as the outer limit for one object.
comptime MAX_CSR_DIM: Int = 1 << 26


fn dims_fit(rows: Int, cols: Int, length: Int) -> Bool:
    """True when `rows` and `cols` are a sane shape for exactly `length` dense cells.

    Written with a DIVISION rather than `rows * cols == length`, because that product is a
    wrapping 64-bit multiply and therefore not a bound at all. Verified:

        3 * 6148914691236517206  ==  2

    so `csr_from_dense_driver([1.0, 2.0], 3, 6148914691236517206, 1e-15)` passed a
    `rows * cols != len(dense)` guard and then read `dense[i * cols + j]` far past the
    end — an uncatchable process crash, reachable from the SDK. This is the guard that
    was missing, not a tightening of one that worked.
    """
    if rows < 0 or cols < 0 or length < 0:
        return False
    if rows > MAX_CSR_DIM or cols > MAX_CSR_DIM:
        return False
    if cols == 0 or rows == 0:
        return length == 0
    # rows <= length // cols  <=>  rows * cols <= length, with no multiply.
    if rows > length // cols:
        return False
    return rows * cols == length


fn csr_status_name(code: Int) -> String:
    """Name for a status code, so an error surfaces the defect and not a bare number."""
    if code == CSR_OK:
        return "ok"
    if code == CSR_ERR_SHAPE:
        return "negative_shape"
    if code == CSR_ERR_LENGTH_MISMATCH:
        return "indices_values_length_mismatch"
    if code == CSR_ERR_INDPTR_LENGTH:
        return "indptr_length_not_nrows_plus_one"
    if code == CSR_ERR_INDPTR_START:
        return "indptr_does_not_start_at_zero"
    if code == CSR_ERR_INDPTR_NOT_MONOTONIC:
        return "indptr_not_monotonic"
    if code == CSR_ERR_INDPTR_TAIL:
        return "indptr_tail_not_nnz"
    if code == CSR_ERR_INDEX_OUT_OF_RANGE:
        return "index_out_of_range"
    if code == CSR_ERR_INVALID_DIMENSIONS:
        return "invalid_dimensions"
    if code == CSR_ERR_DIMENSION_TOO_LARGE:
        return "dimension_exceeds_max_csr_dim"
    return "unknown_status"


# ── CSRMatrix ─────────────────────────────────────────────────────────────────


@fieldwise_init
struct CSRMatrix(Copyable, Movable):
    """Compressed sparse row. Row `i` is `indices/values[indptr[i]:indptr[i+1]]`."""

    var indptr: List[Int]
    var indices: List[Int]
    var values: List[Float64]
    var nrows: Int
    var ncols: Int
    var coalesced: Bool
    var sorted_indices: Bool

    fn nnz(self) -> Int:
        """Stored values, including duplicates and explicit zeros — as COO counts."""
        return len(self.values)

    fn row_nnz(self, row: Int) -> Int:
        """Stored values in one row, or 0 for a row this matrix does not have.

        Returns 0 rather than a negative span for a non-monotonic `indptr`: callers use
        this to size a loop, and a negative count there would be read as "skip".
        """
        if row < 0 or row + 1 >= len(self.indptr):
            return 0
        var span = self.indptr[row + 1] - self.indptr[row]
        if span < 0:
            return 0
        return span

    fn is_canonical(self) -> Bool:
        """Sorted within each row and free of duplicate coordinates."""
        return self.coalesced and self.sorted_indices


@fieldwise_init
struct CSCMatrix(Copyable, Movable):
    """Compressed sparse column. Column `j` is `[colptr[j], colptr[j+1])`.

    A distinct type rather than "a CSR of the transpose" so a caller cannot read a
    transposed matrix's rows as if they were the original's rows; `nrows`/`ncols` here
    describe the matrix itself, not the array layout.
    """

    var colptr: List[Int]
    var row_indices: List[Int]
    var values: List[Float64]
    var nrows: Int
    var ncols: Int
    var coalesced: Bool
    var sorted_indices: Bool

    fn nnz(self) -> Int:
        return len(self.values)

    fn col_nnz(self, col: Int) -> Int:
        if col < 0 or col + 1 >= len(self.colptr):
            return 0
        var span = self.colptr[col + 1] - self.colptr[col]
        if span < 0:
            return 0
        return span


fn csr_empty(nrows: Int, ncols: Int) -> CSRMatrix:
    """An all-zero CSR. Trivially sorted and coalesced: it stores nothing."""
    var rows = nrows
    if rows < 0:
        rows = 0
    var cols = ncols
    if cols < 0:
        cols = 0
    var indptr = List[Int]()
    for _ in range(rows + 1):
        indptr.append(0)
    return CSRMatrix(
        indptr^, List[Int](), List[Float64](), rows, cols, True, True
    )


fn csc_empty(nrows: Int, ncols: Int) -> CSCMatrix:
    var rows = nrows
    if rows < 0:
        rows = 0
    var cols = ncols
    if cols < 0:
        cols = 0
    var colptr = List[Int]()
    for _ in range(cols + 1):
        colptr.append(0)
    return CSCMatrix(
        colptr^, List[Int](), List[Float64](), rows, cols, True, True
    )


# ── return-only result structs ────────────────────────────────────────────────


@fieldwise_init
struct CSRResult(Copyable, Movable):
    """A CSR or CSC returned across the flat driver boundary, with its status.

    Flat fields only, so the dispatch generator can serialise it without a nested
    struct. `layout` says whether `indptr` indexes rows (CSR) or columns (CSC).
    """

    var status: Int
    var layout: Int
    var nrows: Int
    var ncols: Int
    var nnz: Int
    var skipped: Int
    var coalesced: Bool
    var sorted_indices: Bool
    var indptr: List[Int]
    var indices: List[Int]
    var values: List[Float64]


@fieldwise_init
struct SparseSlice(Copyable, Movable):
    """One row of a CSR or one column of a CSC, with the status of the request."""

    var status: Int
    var index: Int
    var nnz: Int
    var indices: List[Int]
    var values: List[Float64]


@fieldwise_init
struct CSRVectorResult(Copyable, Movable):
    """A dense Float64 vector plus status — an absent product is not a zero vector."""

    var status: Int
    var length: Int
    var values: List[Float64]


@fieldwise_init
struct CSRIntsResult(Copyable, Movable):
    """A dense Int vector plus status.

    Exists so a driver returning counts or indices can distinguish "no rows, so no
    counts" from "these arrays are not a matrix". A bare `List[Int]` makes both an
    empty list, and a caller cannot tell that its 5-row matrix was rejected.
    """

    var status: Int
    var length: Int
    var values: List[Int]


fn _result_invalid(status: Int, layout: Int) -> CSRResult:
    """No matrix. Zero shape, so an ignored status cannot be read as a real matrix."""
    return CSRResult(
        status,
        layout,
        0,
        0,
        0,
        0,
        True,
        True,
        List[Int](),
        List[Int](),
        List[Float64](),
    )


fn _result_from_csr(
    m: CSRMatrix, status: Int, skipped: Int
) -> CSRResult:
    return CSRResult(
        status,
        CSR_LAYOUT_ROW,
        m.nrows,
        m.ncols,
        m.nnz(),
        skipped,
        m.coalesced,
        m.sorted_indices,
        m.indptr.copy(),
        m.indices.copy(),
        m.values.copy(),
    )


fn _result_from_csc(c: CSCMatrix, status: Int) -> CSRResult:
    return CSRResult(
        status,
        CSR_LAYOUT_COL,
        c.nrows,
        c.ncols,
        c.nnz(),
        0,
        c.coalesced,
        c.sorted_indices,
        c.colptr.copy(),
        c.row_indices.copy(),
        c.values.copy(),
    )


fn csr_from_arrays(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> CSRMatrix:
    """Wrap caller-supplied arrays. Neither flag is assumed.

    Arrays arriving over the wire have unknown provenance, so `coalesced` and
    `sorted_indices` start False. Claiming them would let a driver skip the coalesce it
    actually needs, and the cost of being wrong is a wrong number rather than a crash.
    Validate before use: this constructor does not.

    @capability csr_from_arrays
    complexity: O(nnz)
    counts:
    - nrows + 1 == len(indptr) [kernel_validated]
    - dim ncols <= MAX_CSR_DIM [kernel_validated]
    @endcapability
    """
    return CSRMatrix(
        indptr.copy(), indices.copy(), values.copy(), nrows, ncols, False, False
    )


fn csc_from_arrays(
    colptr: List[Int],
    row_indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> CSCMatrix:
    """Wrap caller-supplied CSC arrays; neither flag is assumed. See csr_from_arrays.

    @capability csc_from_arrays
    complexity: O(nnz)
    counts:
    - ncols + 1 == len(colptr) [kernel_validated]
    - dim nrows <= MAX_CSR_DIM [kernel_validated]
    @endcapability
    """
    return CSCMatrix(
        colptr.copy(),
        row_indices.copy(),
        values.copy(),
        nrows,
        ncols,
        False,
        False,
    )


# ── validation ────────────────────────────────────────────────────────────────


fn csr_validate_flat(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> Int:
    """`CSR_OK` for a structurally sound CSR, else the first defect's code.

    Checks are ordered so that each one only indexes what its predecessors have already
    proved to exist. This is the single gate that makes the rest of the module safe: an
    `indptr` whose entries exceed `len(values)` would make an innocent
    `for k in range(indptr[i], indptr[i+1])` read past the end of `values`, which is an
    uncatchable process crash rather than an exception.

    Monotonicity plus a zero head plus a tail equal to `len(values)` together bound
    every `indptr` entry to `[0, nnz]`, so no separate range check is needed.

    `ncols` needs its OWN ceiling even though nothing here indexes by it. It was
    previously used only as an upper bound on `indices`, so a matrix could declare a
    column count no array reflected: `csr_transpose_driver([0], [], [], 0, 10**12)` is a
    structurally consistent empty matrix, passes every check above, and then asks
    `csr_transpose` for an 8 TB pointer array. A shape check cannot catch that — the shape
    is consistent — so a declared ceiling is the only guard, and it belongs here rather
    than in each consumer.

    @capability csr_validate_flat
    complexity: O(nnz)
    counts:
    - nrows + 1 == len(indptr) [kernel_validated]
    - dim ncols <= MAX_CSR_DIM [kernel_validated]
    @endcapability
    """
    if nrows < 0 or ncols < 0:
        return CSR_ERR_SHAPE
    if nrows > MAX_CSR_DIM or ncols > MAX_CSR_DIM:
        return CSR_ERR_DIMENSION_TOO_LARGE
    if len(indices) != len(values):
        return CSR_ERR_LENGTH_MISMATCH
    if len(indptr) != nrows + 1:
        return CSR_ERR_INDPTR_LENGTH
    if indptr[0] != 0:
        return CSR_ERR_INDPTR_START
    for i in range(1, nrows + 1):
        if indptr[i] < indptr[i - 1]:
            return CSR_ERR_INDPTR_NOT_MONOTONIC
    if indptr[nrows] != len(values):
        return CSR_ERR_INDPTR_TAIL
    for k in range(len(indices)):
        if indices[k] < 0 or indices[k] >= ncols:
            return CSR_ERR_INDEX_OUT_OF_RANGE
    return CSR_OK


fn csr_validate(m: CSRMatrix) -> Int:
    """`CSR_OK` or the first defect's code. Flags are not checked: they are claims."""
    return csr_validate_flat(m.indptr, m.indices, m.values, m.nrows, m.ncols)


fn csc_validate(c: CSCMatrix) -> Int:
    """CSC soundness. A valid CSC is exactly a valid CSR of the transpose, so the row
    checks are reused rather than restated — one implementation, one behaviour."""
    return csr_validate_flat(
        c.colptr, c.row_indices, c.values, c.ncols, c.nrows
    )


# ── transpose, and the sort it gives away ─────────────────────────────────────


fn _transpose_unchecked(m: CSRMatrix) -> CSRMatrix:
    """Transpose by counting sort. Caller must have validated `m`.

    Two passes over nnz and one over ncols; no comparison sort. Because source rows are
    visited in ascending order, each output row receives its entries in ascending source
    -row order, so the result always has sorted indices even when the input did not.
    """
    var t_nrows = m.ncols
    var t_ncols = m.nrows

    var indptr = List[Int]()
    for _ in range(t_nrows + 1):
        indptr.append(0)
    for k in range(len(m.indices)):
        indptr[m.indices[k] + 1] += 1
    for j in range(t_nrows):
        indptr[j + 1] += indptr[j]

    var out_indices = List[Int]()
    var out_values = List[Float64]()
    for _ in range(len(m.values)):
        out_indices.append(0)
        out_values.append(0.0)

    # A separate write cursor per output row; mutating indptr in place and repairing it
    # afterwards saves one array but loses the ability to assert on indptr mid-way.
    var cursor = List[Int]()
    for j in range(t_nrows + 1):
        cursor.append(indptr[j])

    for i in range(m.nrows):
        for k in range(m.indptr[i], m.indptr[i + 1]):
            var j = m.indices[k]
            var dest = cursor[j]
            out_indices[dest] = i
            out_values[dest] = m.values[k]
            cursor[j] = dest + 1

    # Duplicate coordinates survive a transpose unchanged, so `coalesced` carries over;
    # `sorted_indices` is earned by the traversal order above.
    return CSRMatrix(
        indptr^, out_indices^, out_values^, t_nrows, t_ncols, m.coalesced, True
    )


fn csr_transpose(m: CSRMatrix) -> CSRMatrix:
    """A^T in CSR. An invalid matrix has no transpose: the 0x0 empty is returned."""
    if csr_validate(m) != CSR_OK:
        return csr_empty(0, 0)
    return _transpose_unchecked(m)


fn csr_sort_indices(m: CSRMatrix) -> CSRMatrix:
    """Column indices ascending within each row, values moved with them.

    Implemented as two transposes rather than a per-row sort: the counting sort inside
    `_transpose_unchecked` is O(nnz + max(nrows, ncols)) with no comparisons, versus an
    insertion sort per row that degrades on the wide rows this layout exists to serve.
    The double transpose is also stable, so equal indices keep their relative order and
    a subsequent coalesce sums them in COO insertion order.
    """
    if csr_validate(m) != CSR_OK:
        return csr_empty(0, 0)
    if m.sorted_indices:
        return m.copy()
    return _transpose_unchecked(_transpose_unchecked(m))


fn csr_coalesce(m: CSRMatrix) -> CSRMatrix:
    """Sort each row and sum duplicate coordinates. Idempotent.

    Idempotent by construction, not by luck: the output asserts both flags, and an input
    that already has both is returned unchanged, so the second call does no arithmetic
    at all. Re-running the merge would also be a no-op, but only because floating-point
    addition of a single term is exact — relying on that would make idempotence an
    accident of the data.

    Explicit zeros are kept; see the module docstring.
    """
    if csr_validate(m) != CSR_OK:
        return csr_empty(0, 0)
    if m.coalesced and m.sorted_indices:
        return m.copy()

    var s = csr_sort_indices(m)
    var out_indptr = List[Int]()
    out_indptr.append(0)
    var out_indices = List[Int]()
    var out_values = List[Float64]()
    for i in range(s.nrows):
        var end = s.indptr[i + 1]
        var k = s.indptr[i]
        while k < end:
            var col = s.indices[k]
            var acc = s.values[k]
            var j = k + 1
            while j < end and s.indices[j] == col:
                acc += s.values[j]
                j += 1
            out_indices.append(col)
            out_values.append(acc)
            k = j
        out_indptr.append(len(out_values))
    return CSRMatrix(
        out_indptr^, out_indices^, out_values^, s.nrows, s.ncols, True, True
    )


# ── CSC ───────────────────────────────────────────────────────────────────────


fn csc_from_csr(m: CSRMatrix) -> CSCMatrix:
    """CSC of the same matrix, making column access O(1) per column.

    The arrays are those of A^T in CSR — that identity is what makes this O(nnz) — but
    the shape reported is A's, because the caller asked for a view of A.
    """
    if csr_validate(m) != CSR_OK:
        return csc_empty(0, 0)
    var t = _transpose_unchecked(m)
    return CSCMatrix(
        t.indptr.copy(),
        t.indices.copy(),
        t.values.copy(),
        m.nrows,
        m.ncols,
        t.coalesced,
        t.sorted_indices,
    )


fn csr_from_csc(c: CSCMatrix) -> CSRMatrix:
    """CSR of the same matrix. Inverse of `csc_from_csr` for a valid input."""
    if csc_validate(c) != CSR_OK:
        return csr_empty(0, 0)
    # A CSC of A read as CSR is exactly A^T; transposing it returns A.
    var as_transpose = CSRMatrix(
        c.colptr.copy(),
        c.row_indices.copy(),
        c.values.copy(),
        c.ncols,
        c.nrows,
        c.coalesced,
        c.sorted_indices,
    )
    return _transpose_unchecked(as_transpose)


# ── conversions to and from the frozen COO type ───────────────────────────────
# These two are the only public functions here that the runtime contract cannot carry:
# `SparseMatrixCOO` is declared in `sparse.mojo`, and the contract only admits structs
# declared in the calling module. That costs nothing — `csr_build_from_triplets` is the
# same COO -> CSR path over the wire, and `sparse.mojo`'s own COO entry points are
# already in the contract — but a later module should reach for these in Mojo and for
# the triplet driver from an SDK.


fn csr_from_coo(mat: SparseMatrixCOO) -> CSRMatrix:
    """CSR from the frozen COO builder. Duplicates sum; out-of-range entries drop.

    Summing duplicates is not a choice made here — it is `to_dense`'s `+=`, and this
    conversion has to agree with it or the two representations of one COO would denote
    different matrices. Coordinates outside the declared shape are dropped because COO
    never bounds-checked them, and indexing with one would crash the process.
    """
    var nrows = mat.nrows
    var ncols = mat.ncols
    if nrows < 0 or ncols < 0:
        return csr_empty(0, 0)

    var indptr = List[Int]()
    for _ in range(nrows + 1):
        indptr.append(0)
    var kept = 0
    for k in range(len(mat.entries)):
        ref e = mat.entries[k]
        if e.row >= 0 and e.row < nrows and e.col >= 0 and e.col < ncols:
            indptr[e.row + 1] += 1
            kept += 1
    for i in range(nrows):
        indptr[i + 1] += indptr[i]

    var indices = List[Int]()
    var values = List[Float64]()
    for _ in range(kept):
        indices.append(0)
        values.append(0.0)
    var cursor = List[Int]()
    for i in range(nrows + 1):
        cursor.append(indptr[i])
    for k in range(len(mat.entries)):
        ref e = mat.entries[k]
        if e.row >= 0 and e.row < nrows and e.col >= 0 and e.col < ncols:
            var dest = cursor[e.row]
            indices[dest] = e.col
            values[dest] = e.val
            cursor[e.row] = dest + 1

    # Grouped by row but still in COO order within a row, and duplicates intact: the
    # canonical form is one coalesce away, and coalesce is the only place that sums.
    var grouped = CSRMatrix(
        indptr^, indices^, values^, nrows, ncols, False, False
    )
    return csr_coalesce(grouped)


fn csr_to_coo(m: CSRMatrix) -> SparseMatrixCOO:
    """COO with one entry per stored value, row-major. Empty 0x0 if `m` is invalid.

    Built through the frozen `add_entry` so the entry list is assembled the one way the
    rest of the tree assembles it.
    """
    if csr_validate(m) != CSR_OK:
        return SparseMatrixCOO(0, 0)
    var out = SparseMatrixCOO(m.nrows, m.ncols)
    for i in range(m.nrows):
        for k in range(m.indptr[i], m.indptr[i + 1]):
            out.add_entry(i, m.indices[k], m.values[k])
    return out^


fn csr_from_dense(
    dense: List[Float64], rows: Int, cols: Int, tol: Float64 = 1e-15
) -> CSRMatrix:
    """CSR from a flat row-major dense matrix; `|v| < tol` is not stored.

    Delegates the tolerance decision to the frozen `sparse_from_dense` rather than
    re-deciding what counts as a stored value, so both paths agree on a 1e-16 entry.
    That kernel takes the nested shape and infers the column count from row 0, which
    loses `cols` for a zero-row matrix — hence the explicit re-shaping afterwards.

    `rows * cols != len(dense)` is a caller error, not a matrix: the declared shape and
    the data disagree and there is no way to know which is right.

    @capability csr_from_dense
    complexity: O(rows * cols)
    counts:
    - rows * cols == len(dense) [kernel_validated]
    @endcapability
    """
    if not dims_fit(rows, cols, len(dense)):
        return csr_empty(0, 0)
    var nested = List[List[Float64]]()
    for i in range(rows):
        var row = List[Float64]()
        for j in range(cols):
            row.append(dense[i * cols + j])
        nested.append(row^)
    var coo = sparse_from_dense(nested, tol)
    var shaped = SparseMatrixCOO(coo.entries.copy(), rows, cols)
    return csr_from_coo(shaped)


fn csr_to_dense(m: CSRMatrix) -> List[Float64]:
    """Flat row-major dense image, or an empty list if `m` is invalid.

    Routed through the frozen `to_dense` instead of scattering here, so that the
    duplicate-summing semantics of a non-coalesced CSR are literally the frozen
    kernel's and cannot drift from it. `to_dense` indexes `result[row][col]` with no
    bounds check, which is safe only because validation above has already proved every
    index is in range — that ordering is load-bearing.
    """
    if csr_validate(m) != CSR_OK:
        return List[Float64]()
    var coo = csr_to_coo(m)
    var nested = coo.to_dense()
    var flat = List[Float64]()
    for i in range(m.nrows):
        for j in range(m.ncols):
            flat.append(nested[i][j])
    return flat^


# ── slicing and multiply ──────────────────────────────────────────────────────


fn csr_row_slice(m: CSRMatrix, row: Int) -> SparseSlice:
    """One row's (indices, values). O(row_nnz), which is why CSR exists."""
    if csr_validate(m) != CSR_OK:
        return SparseSlice(
            CSR_ERR_INVALID_DIMENSIONS, row, 0, List[Int](), List[Float64]()
        )
    if row < 0 or row >= m.nrows:
        return SparseSlice(
            CSR_ERR_INVALID_DIMENSIONS, row, 0, List[Int](), List[Float64]()
        )
    var indices = List[Int]()
    var values = List[Float64]()
    for k in range(m.indptr[row], m.indptr[row + 1]):
        indices.append(m.indices[k])
        values.append(m.values[k])
    var count = len(values)
    return SparseSlice(CSR_OK, row, count, indices^, values^)


fn csc_col_slice(c: CSCMatrix, col: Int) -> SparseSlice:
    """One column's (row indices, values). O(col_nnz)."""
    if csc_validate(c) != CSR_OK:
        return SparseSlice(
            CSR_ERR_INVALID_DIMENSIONS, col, 0, List[Int](), List[Float64]()
        )
    if col < 0 or col >= c.ncols:
        return SparseSlice(
            CSR_ERR_INVALID_DIMENSIONS, col, 0, List[Int](), List[Float64]()
        )
    var indices = List[Int]()
    var values = List[Float64]()
    for k in range(c.colptr[col], c.colptr[col + 1]):
        indices.append(c.row_indices[k])
        values.append(c.values[k])
    var count = len(values)
    return SparseSlice(CSR_OK, col, count, indices^, values^)


fn csr_matvec(m: CSRMatrix, x: List[Float64]) -> CSRVectorResult:
    """A @ x, one contiguous pass per row.

    A vector of the wrong length has no product; returning the partial sums that fit
    would be a plausible wrong answer, so the status says invalid_dimensions and the
    values are empty.
    """
    var status = csr_validate(m)
    if status != CSR_OK:
        return CSRVectorResult(status, 0, List[Float64]())
    if len(x) != m.ncols:
        return CSRVectorResult(CSR_ERR_INVALID_DIMENSIONS, 0, List[Float64]())
    var out = List[Float64]()
    for i in range(m.nrows):
        var acc = 0.0
        for k in range(m.indptr[i], m.indptr[i + 1]):
            acc += m.values[k] * x[m.indices[k]]
        out.append(acc)
    var count = len(out)
    return CSRVectorResult(CSR_OK, count, out^)


fn csr_row_counts(m: CSRMatrix) -> List[Int]:
    """Stored values per row, or an empty list if `m` is invalid."""
    if csr_validate(m) != CSR_OK:
        return List[Int]()
    var counts = List[Int]()
    for i in range(m.nrows):
        counts.append(m.indptr[i + 1] - m.indptr[i])
    return counts^


# ── flat-list drivers ─────────────────────────────────────────────────────────
# Lists and scalars in, a status-bearing struct out. This is what makes the package
# callable as execute(module, function, args) from the local SDKs with no new message
# type; see docs/mojo/new-kernel-package-rules.md rule 2.


fn csr_build_from_triplets(
    rows: List[Int],
    cols: List[Int],
    vals: List[Float64],
    nrows: Int,
    ncols: Int,
) -> CSRResult:
    """Canonical CSR from parallel triplet arrays. Duplicates sum, strays are counted.

    The range test is repeated here rather than delegated to `csr_from_coo` because the
    caller needs the dropped count, and a `CSRMatrix` has nowhere to put it.

    @capability csr_build_from_triplets
    complexity: O(nnz log nnz)
    counts:
    - dim nrows [kernel_validated]
    - dim ncols [kernel_validated]
    @endcapability
    """
    if (
        len(rows) != len(cols)
        or len(rows) != len(vals)
        or nrows < 0
        or ncols < 0
    ):
        return _result_invalid(CSR_ERR_INVALID_DIMENSIONS, CSR_LAYOUT_ROW)
    var coo = SparseMatrixCOO(nrows, ncols)
    var skipped = 0
    for k in range(len(rows)):
        if rows[k] >= 0 and rows[k] < nrows and cols[k] >= 0 and cols[k] < ncols:
            coo.add_entry(rows[k], cols[k], vals[k])
        else:
            skipped += 1
    return _result_from_csr(csr_from_coo(coo), CSR_OK, skipped)


fn csr_from_dense_driver(
    dense: List[Float64], rows: Int, cols: Int, tol: Float64
) -> CSRResult:
    """CSR from a flat row-major dense matrix, with a status for a shape mismatch.

    @capability csr_from_dense_driver
    complexity: O(rows * cols)
    counts:
    - rows * cols == len(dense) [kernel_validated]
    @endcapability
    """
    if not dims_fit(rows, cols, len(dense)):
        return _result_invalid(CSR_ERR_INVALID_DIMENSIONS, CSR_LAYOUT_ROW)
    return _result_from_csr(csr_from_dense(dense, rows, cols, tol), CSR_OK, 0)


fn csr_to_dense_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> CSRVectorResult:
    """Flat row-major dense image, with the status that says why it might be empty.

    The typed `csr_to_dense` returns a bare list because its caller has the matrix and
    can validate it; a driver's caller has only the reply, where an empty list would be
    indistinguishable from the dense image of a 0x0 matrix.

    @capability csr_to_dense_driver
    complexity: O(nrows * ncols)
    counts:
    - nrows + 1 == len(indptr) [kernel_validated]
    - dim ncols <= MAX_CSR_DIM [kernel_validated]
    @endcapability
    """
    var m = csr_from_arrays(indptr, indices, values, nrows, ncols)
    var status = csr_validate(m)
    if status != CSR_OK:
        return CSRVectorResult(status, 0, List[Float64]())
    var dense = csr_to_dense(m)
    var count = len(dense)
    return CSRVectorResult(CSR_OK, count, dense^)


fn csr_transpose_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> CSRResult:
    """csr_transpose_driver: declared capability.

    @capability csr_transpose_driver
    complexity: O(nnz + ncols)
    counts:
    - nrows + 1 == len(indptr) [kernel_validated]
    - dim ncols <= MAX_CSR_DIM [kernel_validated]
    @endcapability
    """
    var m = csr_from_arrays(indptr, indices, values, nrows, ncols)
    var status = csr_validate(m)
    if status != CSR_OK:
        return _result_invalid(status, CSR_LAYOUT_ROW)
    return _result_from_csr(_transpose_unchecked(m), CSR_OK, 0)


fn csr_coalesce_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> CSRResult:
    """csr_coalesce_driver: declared capability.

    @capability csr_coalesce_driver
    complexity: O(nnz + nrows)
    counts:
    - nrows + 1 == len(indptr) [kernel_validated]
    - dim ncols <= MAX_CSR_DIM [kernel_validated]
    @endcapability
    """
    var m = csr_from_arrays(indptr, indices, values, nrows, ncols)
    var status = csr_validate(m)
    if status != CSR_OK:
        return _result_invalid(status, CSR_LAYOUT_ROW)
    return _result_from_csr(csr_coalesce(m), CSR_OK, 0)


fn csr_sort_indices_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> CSRResult:
    """csr_sort_indices_driver: declared capability.

    @capability csr_sort_indices_driver
    complexity: O(nnz log nnz)
    counts:
    - nrows + 1 == len(indptr) [kernel_validated]
    - dim ncols <= MAX_CSR_DIM [kernel_validated]
    @endcapability
    """
    var m = csr_from_arrays(indptr, indices, values, nrows, ncols)
    var status = csr_validate(m)
    if status != CSR_OK:
        return _result_invalid(status, CSR_LAYOUT_ROW)
    return _result_from_csr(csr_sort_indices(m), CSR_OK, 0)


fn csc_from_csr_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> CSRResult:
    """CSC of the CSR described by these arrays; `layout` on the result says CSC.

    @capability csc_from_csr_driver
    complexity: O(nnz + ncols)
    counts:
    - nrows + 1 == len(indptr) [kernel_validated]
    - dim ncols <= MAX_CSR_DIM [kernel_validated]
    @endcapability
    """
    var m = csr_from_arrays(indptr, indices, values, nrows, ncols)
    var status = csr_validate(m)
    if status != CSR_OK:
        return _result_invalid(status, CSR_LAYOUT_COL)
    return _result_from_csc(csc_from_csr(m), CSR_OK)


fn csr_from_csc_driver(
    colptr: List[Int],
    row_indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> CSRResult:
    """csr_from_csc_driver: declared capability.

    @capability csr_from_csc_driver
    complexity: O(nnz + nrows)
    counts:
    - ncols + 1 == len(colptr) [kernel_validated]
    - dim nrows <= MAX_CSR_DIM [kernel_validated]
    @endcapability
    """
    var c = csc_from_arrays(colptr, row_indices, values, nrows, ncols)
    var status = csc_validate(c)
    if status != CSR_OK:
        return _result_invalid(status, CSR_LAYOUT_ROW)
    return _result_from_csr(csr_from_csc(c), CSR_OK, 0)


fn csr_row_slice_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    row: Int,
) -> SparseSlice:
    """csr_row_slice_driver: declared capability.

    @capability csr_row_slice_driver
    complexity: O(row_nnz)
    counts:
    - nrows + 1 == len(indptr) [kernel_validated]
    - dim ncols <= MAX_CSR_DIM [kernel_validated]
    @endcapability
    """
    return csr_row_slice(
        csr_from_arrays(indptr, indices, values, nrows, ncols), row
    )


fn csc_col_slice_driver(
    colptr: List[Int],
    row_indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    col: Int,
) -> SparseSlice:
    """csc_col_slice_driver: declared capability.

    @capability csc_col_slice_driver
    complexity: O(col_nnz)
    counts:
    - ncols + 1 == len(colptr) [kernel_validated]
    - dim nrows <= MAX_CSR_DIM [kernel_validated]
    @endcapability
    """
    return csc_col_slice(
        csc_from_arrays(colptr, row_indices, values, nrows, ncols), col
    )


fn csr_matvec_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    x: List[Float64],
) -> CSRVectorResult:
    """csr_matvec_driver: declared capability.

    @capability csr_matvec_driver
    complexity: O(nnz)
    counts:
    - nrows + 1 == len(indptr) [kernel_validated]
    - dim ncols <= MAX_CSR_DIM [kernel_validated]
    - ncols == len(x) [kernel_validated]
    @endcapability
    """
    return csr_matvec(
        csr_from_arrays(indptr, indices, values, nrows, ncols), x
    )


fn csr_row_counts_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> CSRIntsResult:
    """csr_row_counts_driver: declared capability.

    @capability csr_row_counts_driver
    complexity: O(nrows)
    counts:
    - nrows + 1 == len(indptr) [kernel_validated]
    - dim ncols <= MAX_CSR_DIM [kernel_validated]
    @endcapability
    """
    var m = csr_from_arrays(indptr, indices, values, nrows, ncols)
    var status = csr_validate(m)
    if status != CSR_OK:
        return CSRIntsResult(status, 0, List[Int]())
    var counts = csr_row_counts(m)
    var count = len(counts)
    return CSRIntsResult(CSR_OK, count, counts^)
