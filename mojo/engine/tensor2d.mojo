"""
tensor2d.mojo — Minimal dense 2D matrix type for ML kernels. Zero Python imports.

Replaces numpy 2D essentials (np.zeros, 2D np.array, A @ B, A @ x, A.T,
A + B, c * A, row/column slicing). Complements tensor.mojo (1D Tensor1D)
and linalg.mojo (solvers/decompositions): this file is only the dense
storage type plus the core products ML kernels need.

Shape-mismatch policy (deterministic, never traps): binary ops on
incompatible shapes return an empty 0x0 Matrix2D (or empty List for
m2_matvec); out-of-range m2_get returns 0.0; out-of-range m2_set is a
no-op. Callers gate on rows/cols > 0.

Public API:
  struct Matrix2D  — rows, cols, data (row-major List[Float64])
  m2_zeros         — rows x cols zero matrix
  m2_from_list     — build from row-major flat list (short input zero-padded)
  m2_get           — element at (i, j); 0.0 if out of range
  m2_set           — write element at (i, j); no-op if out of range
  m2_matmul        — matrix product A(m x p) @ B(p x n) -> (m x n)
  m2_matvec        — matrix-vector product A(m x n) @ x(n) -> List of m
  m2_transpose     — A^T (n x m from m x n)
  m2_add           — element-wise A + B (same shape)
  m2_scale         — c * A
  m2_row           — copy of row i as List[Float64] (empty if out of range)
  m2_col           — copy of column j as List[Float64] (empty if out of range)
"""


# ── Matrix2D struct ───────────────────────────────────────────────────────────


@fieldwise_init
struct Matrix2D(Copyable, Movable):
    """Dense 2D matrix with row-major List[Float64] storage.

    Element (i, j) lives at data[i * cols + j]. Invariant:
    len(data) == rows * cols; negative dimensions are clamped to 0.
    """

    var rows: Int
    var cols: Int
    var data: List[Float64]

    fn __init__(out self, rows: Int, cols: Int):
        """Create a zero-initialized rows x cols matrix."""
        self.rows = rows
        self.cols = cols
        if self.rows < 0:
            self.rows = 0
        if self.cols < 0:
            self.cols = 0
        self.data = List[Float64](capacity=self.rows * self.cols)
        for _ in range(self.rows * self.cols):
            self.data.append(0.0)

    fn _in_range(self, i: Int, j: Int) -> Bool:
        return i >= 0 and i < self.rows and j >= 0 and j < self.cols


# ── constructors ─────────────────────────────────────────────────────────────


fn m2_zeros(rows: Int, cols: Int) -> Matrix2D:
    """rows x cols matrix of zeros (negative dims clamp to 0)."""
    return Matrix2D(rows, cols)


fn m2_from_list(data: List[Float64], rows: Int, cols: Int) -> Matrix2D:
    """Build a rows x cols matrix from a row-major flat list.

    Missing trailing values are zero-filled; extra values are ignored.
    """
    var m = Matrix2D(rows, cols)
    var total = m.rows * m.cols
    var n = len(data)
    for i in range(total):
        if i < n:
            m.data[i] = data[i]
    return m^


# ── element access ───────────────────────────────────────────────────────────


fn m2_get(m: Matrix2D, i: Int, j: Int) -> Float64:
    """Element at (i, j); returns 0.0 when the index is out of range."""
    if not m._in_range(i, j):
        return 0.0
    return m.data[i * m.cols + j]


fn m2_set(mut m: Matrix2D, i: Int, j: Int, val: Float64):
    """Write val at (i, j); silently no-op when the index is out of range."""
    if not m._in_range(i, j):
        return
    m.data[i * m.cols + j] = val


# ── products ─────────────────────────────────────────────────────────────────


fn m2_matmul(a: Matrix2D, b: Matrix2D) -> Matrix2D:
    """Matrix product A(m x p) @ B(p x n) -> (m x n).

    Returns an empty 0x0 matrix when a.cols != b.rows. i-k-j loop order
    (row-major streaming) keeps the inner loop contiguous in both B and C.
    O(m*p*n): sub-ms for typical ML-kernel shapes (e.g. 100x100x100 ~ 1e6
    mul-adds); a full 10k x 10k dense product is inherently >> 1ms and out
    of scope for this minimal type.
    """
    if a.cols != b.rows:
        return Matrix2D(0, 0)
    var out = Matrix2D(a.rows, b.cols)
    for i in range(a.rows):
        for k in range(a.cols):
            var aik = a.data[i * a.cols + k]
            var b_off = k * b.cols
            var o_off = i * b.cols
            for j in range(b.cols):
                out.data[o_off + j] += aik * b.data[b_off + j]
    return out^


fn m2_matvec(a: Matrix2D, x: List[Float64]) -> List[Float64]:
    """Matrix-vector product A(m x n) @ x(n) -> list of m values.

    Returns an empty list when a.cols != len(x). O(m*n).
    """
    var out = List[Float64]()
    if a.cols != len(x):
        return out^
    for i in range(a.rows):
        var acc: Float64 = 0.0
        var off = i * a.cols
        for j in range(a.cols):
            acc += a.data[off + j] * x[j]
        out.append(acc)
    return out^


# ── shape / element-wise ops ─────────────────────────────────────────────────


fn m2_transpose(a: Matrix2D) -> Matrix2D:
    """A^T: (m x n) -> (n x m). O(m*n)."""
    var out = Matrix2D(a.cols, a.rows)
    for i in range(a.rows):
        for j in range(a.cols):
            out.data[j * a.rows + i] = a.data[i * a.cols + j]
    return out^


fn m2_add(a: Matrix2D, b: Matrix2D) -> Matrix2D:
    """Element-wise A + B; empty 0x0 matrix when shapes differ. O(m*n)."""
    if a.rows != b.rows or a.cols != b.cols:
        return Matrix2D(0, 0)
    var out = Matrix2D(a.rows, a.cols)
    for i in range(len(a.data)):
        out.data[i] = a.data[i] + b.data[i]
    return out^


fn m2_scale(a: Matrix2D, c: Float64) -> Matrix2D:
    """Scalar multiple c * A. O(m*n)."""
    var out = Matrix2D(a.rows, a.cols)
    for i in range(len(a.data)):
        out.data[i] = c * a.data[i]
    return out^


# ── row / column extraction ──────────────────────────────────────────────────


fn m2_row(a: Matrix2D, i: Int) -> List[Float64]:
    """Copy of row i (length cols); empty list when i is out of range."""
    var out = List[Float64]()
    if i < 0 or i >= a.rows:
        return out^
    var off = i * a.cols
    for j in range(a.cols):
        out.append(a.data[off + j])
    return out^


fn m2_col(a: Matrix2D, j: Int) -> List[Float64]:
    """Copy of column j (length rows); empty list when j is out of range."""
    var out = List[Float64]()
    if j < 0 or j >= a.cols:
        return out^
    for i in range(a.rows):
        out.append(a.data[i * a.cols + j])
    return out^
