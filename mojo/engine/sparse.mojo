"""
sparse.mojo — Sparse matrix operations in COO format. Zero Python imports.

Replaces scipy.sparse with pure Mojo implementations for coordinate-format
sparse matrices, matrix-vector multiply, addition, transpose, and conversion.

Public API:
  COOEntry            — Single non-zero entry (row, col, val)
  SparseMatrixCOO     — COO sparse matrix with add_entry, nnz, to_dense
  sparse_from_dense   — Create sparse from dense matrix
  sparse_matvec       — Sparse matrix-vector multiply
  sparse_add          — Element-wise sparse matrix addition
  sparse_transpose    — Transpose sparse matrix
  sparse_density      — Fraction of non-zero entries
  sparse_trace        — Sum of diagonal entries
"""
from std.math import abs as fabs


# ── COOEntry struct ──────────────────────────────────────────────────────────


struct COOEntry(Copyable, Movable):
    """A single non-zero entry in a sparse matrix."""

    var row: Int
    var col: Int
    var val: Float64

    fn __init__(out self, row: Int, col: Int, val: Float64):
        self.row = row
        self.col = col
        self.val = val


# ── SparseMatrixCOO struct ───────────────────────────────────────────────────


struct SparseMatrixCOO(Copyable, Movable):
    """Sparse matrix in COOrdinate (triplet) format."""

    var entries: List[COOEntry]
    var nrows: Int
    var ncols: Int

    fn __init__(out self, nrows: Int, ncols: Int):
        self.entries = List[COOEntry]()
        self.nrows = nrows
        self.ncols = ncols

    fn add_entry(mut self, row: Int, col: Int, val: Float64):
        """Add a non-zero entry."""
        self.entries.append(COOEntry(row, col, val))

    fn nnz(self) -> Int:
        """Number of non-zero entries."""
        return len(self.entries)

    fn to_dense(self) -> List[List[Float64]]:
        """Convert to dense matrix (List of rows)."""
        var result = List[List[Float64]]()
        for i in range(self.nrows):
            var row = List[Float64]()
            for _ in range(self.ncols):
                row.append(0.0)
            result.append(row^)
        for i in range(len(self.entries)):
            var e = self.entries[i].copy()
            result[e.row][e.col] = result[e.row][e.col] + e.val
        return result^


# ── sparse_from_dense ────────────────────────────────────────────────────────


fn sparse_from_dense(dense: List[List[Float64]], tol: Float64 = 1e-15) -> SparseMatrixCOO:
    """Create sparse matrix from dense, ignoring values with |v| < tol."""
    var nrows = len(dense)
    var ncols = 0
    if nrows > 0:
        ncols = len(dense[0])
    var mat = SparseMatrixCOO(nrows, ncols)
    for i in range(nrows):
        for j in range(len(dense[i])):
            if fabs(dense[i][j]) >= tol:
                mat.add_entry(i, j, dense[i][j])
    return mat^


# ── sparse_matvec ────────────────────────────────────────────────────────────


fn sparse_matvec(mat: SparseMatrixCOO, vec: List[Float64]) -> List[Float64]:
    """Sparse matrix-vector multiply: result = mat @ vec."""
    var result = List[Float64]()
    for _ in range(mat.nrows):
        result.append(0.0)
    for i in range(len(mat.entries)):
        var e = mat.entries[i].copy()
        result[e.row] = result[e.row] + e.val * vec[e.col]
    return result^


# ── sparse_add ───────────────────────────────────────────────────────────────


fn sparse_add(a: SparseMatrixCOO, b: SparseMatrixCOO) -> SparseMatrixCOO:
    """Element-wise addition of two sparse matrices (same dimensions)."""
    var result = SparseMatrixCOO(a.nrows, a.ncols)
    for i in range(len(a.entries)):
        var e = a.entries[i].copy()
        result.add_entry(e.row, e.col, e.val)
    for i in range(len(b.entries)):
        var e = b.entries[i].copy()
        result.add_entry(e.row, e.col, e.val)
    return result^


# ── sparse_transpose ─────────────────────────────────────────────────────────


fn sparse_transpose(mat: SparseMatrixCOO) -> SparseMatrixCOO:
    """Transpose sparse matrix (swap row and col in each entry)."""
    var result = SparseMatrixCOO(mat.ncols, mat.nrows)
    for i in range(len(mat.entries)):
        var e = mat.entries[i].copy()
        result.add_entry(e.col, e.row, e.val)
    return result^


# ── sparse_density ───────────────────────────────────────────────────────────


fn sparse_density(mat: SparseMatrixCOO) -> Float64:
    """Fraction of non-zero entries: nnz / (nrows * ncols)."""
    var total = mat.nrows * mat.ncols
    if total == 0:
        return 0.0
    return Float64(mat.nnz()) / Float64(total)


# ── sparse_trace ─────────────────────────────────────────────────────────────


fn sparse_trace(mat: SparseMatrixCOO) -> Float64:
    """Sum of diagonal entries (where row == col)."""
    var s: Float64 = 0.0
    for i in range(len(mat.entries)):
        var e = mat.entries[i].copy()
        if e.row == e.col:
            s += e.val
    return s
