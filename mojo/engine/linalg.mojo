"""
linalg.mojo — Linear algebra operations. Zero Python imports.
Replaces: numpy.linalg.solve, inv, det, eig (2x2), dot, norm

Row-major List[Float64] storage. Gaussian elimination with partial pivoting.

Public API:
  Matrix struct (with get/set)
  mat_zeros, mat_identity, mat_from_list
  mat_add, mat_sub, mat_mul, mat_scale, mat_transpose
  mat_det, mat_inv, mat_solve
  vec_dot, vec_norm, vec_cross
  mat_lu, mat_eigenvalues_2x2
"""
from std.math import sqrt, abs as fabs


# ── Matrix struct ─────────────────────────────────────────────────────────────


@fieldwise_init
struct Matrix(Copyable, Movable):
    """Dense matrix with row-major List[Float64] storage."""
    var data: List[Float64]  # row-major storage
    var rows: Int
    var cols: Int

    def __init__(out self, rows: Int, cols: Int):
        """Create a zero-initialized matrix of given dimensions."""
        self.rows = rows
        self.cols = cols
        self.data = List[Float64]()
        for i in range(rows * cols):
            self.data.append(0.0)

    def get(self, i: Int, j: Int) -> Float64:
        """Get element at row i, column j."""
        return self.data[i * self.cols + j]

    def set(mut self, i: Int, j: Int, val: Float64):
        """Set element at row i, column j."""
        self.data[i * self.cols + j] = val


# ── Factory functions ─────────────────────────────────────────────────────────


def mat_zeros(rows: Int, cols: Int) -> Matrix:
    """Create a zero matrix."""
    return Matrix(rows, cols)


def mat_identity(n: Int) -> Matrix:
    """Create an n×n identity matrix."""
    var m = Matrix(n, n)
    for i in range(n):
        m.set(i, i, 1.0)
    return m^


def mat_from_list(data: List[Float64], rows: Int, cols: Int) -> Matrix:
    """Create matrix from row-major flat list."""
    var m = Matrix(rows, cols)
    var n = len(data)
    var total = rows * cols
    for i in range(total):
        if i < n:
            m.data[i] = data[i]
    return m^


# ── Element-wise operations ───────────────────────────────────────────────────


def mat_add(a: Matrix, b: Matrix) -> Matrix:
    """Element-wise addition. Dimensions must match."""
    var r = a.rows
    var c = a.cols
    var m = Matrix(r, c)
    for i in range(r * c):
        m.data[i] = a.data[i] + b.data[i]
    return m^


def mat_sub(a: Matrix, b: Matrix) -> Matrix:
    """Element-wise subtraction. Dimensions must match."""
    var r = a.rows
    var c = a.cols
    var m = Matrix(r, c)
    for i in range(r * c):
        m.data[i] = a.data[i] - b.data[i]
    return m^


def mat_scale(a: Matrix, s: Float64) -> Matrix:
    """Scalar multiplication."""
    var m = Matrix(a.rows, a.cols)
    for i in range(a.rows * a.cols):
        m.data[i] = a.data[i] * s
    return m^


def mat_transpose(a: Matrix) -> Matrix:
    """Matrix transpose."""
    var m = Matrix(a.cols, a.rows)
    for i in range(a.rows):
        for j in range(a.cols):
            m.set(j, i, a.get(i, j))
    return m^


# ── Matrix multiplication ────────────────────────────────────────────────────


def mat_mul(a: Matrix, b: Matrix) -> Matrix:
    """Matrix multiplication: C = A × B.
    A is (m×k), B is (k×n), result is (m×n)."""
    var m = a.rows
    var k = a.cols
    var n = b.cols
    var c = Matrix(m, n)

    for i in range(m):
        for j in range(n):
            var s: Float64 = 0.0
            for p in range(k):
                s += a.get(i, p) * b.get(p, j)
            c.set(i, j, s)

    return c^


# ── Determinant ───────────────────────────────────────────────────────────────


def mat_det(a: Matrix) -> Float64:
    """Determinant of a square matrix.
    Direct formulas for 1×1, 2×2, 3×3; LU-based for larger."""
    var n = a.rows
    if n != a.cols:
        return 0.0

    if n == 1:
        return a.get(0, 0)

    if n == 2:
        return a.get(0, 0) * a.get(1, 1) - a.get(0, 1) * a.get(1, 0)

    if n == 3:
        return (a.get(0, 0) * (a.get(1, 1) * a.get(2, 2) - a.get(1, 2) * a.get(2, 1))
              - a.get(0, 1) * (a.get(1, 0) * a.get(2, 2) - a.get(1, 2) * a.get(2, 0))
              + a.get(0, 2) * (a.get(1, 0) * a.get(2, 1) - a.get(1, 1) * a.get(2, 0)))

    if n == 4:
        # Expand by cofactors along first row
        var det: Float64 = 0.0
        for j in range(4):
            var minor = _minor_3x3(a, 0, j)
            if j % 2 == 0:
                det += a.get(0, j) * minor
            else:
                det -= a.get(0, j) * minor
        return det

    # General case: LU decomposition
    return _det_lu(a)


def _minor_3x3(a: Matrix, skip_row: Int, skip_col: Int) -> Float64:
    """Compute 3×3 minor determinant for a 4×4 matrix."""
    var m = List[Float64]()
    for i in range(4):
        if i == skip_row:
            continue
        for j in range(4):
            if j == skip_col:
                continue
            m.append(a.get(i, j))
    # 3×3 determinant
    return (m[0] * (m[4] * m[8] - m[5] * m[7])
          - m[1] * (m[3] * m[8] - m[5] * m[6])
          + m[2] * (m[3] * m[7] - m[4] * m[6]))


def _det_lu(a: Matrix) -> Float64:
    """Determinant via LU decomposition with partial pivoting."""
    var n = a.rows
    # Copy matrix
    var u = Matrix(n, n)
    for i in range(n * n):
        u.data[i] = a.data[i]

    var sign: Float64 = 1.0

    for col in range(n):
        # Find pivot
        var max_val: Float64 = 0.0
        var max_row = col
        for row in range(col, n):
            var v = fabs(u.get(row, col))
            if v > max_val:
                max_val = v
                max_row = row

        if max_val < 1e-15:
            return 0.0  # Singular

        # Swap rows
        if max_row != col:
            for j in range(n):
                var tmp = u.get(col, j)
                u.set(col, j, u.get(max_row, j))
                u.set(max_row, j, tmp)
            sign = -sign

        # Eliminate below
        for row in range(col + 1, n):
            var factor = u.get(row, col) / u.get(col, col)
            for j in range(col, n):
                u.set(row, j, u.get(row, j) - factor * u.get(col, j))

    # Determinant is product of diagonal
    var det = sign
    for i in range(n):
        det *= u.get(i, i)

    return det


# ── Matrix inverse ────────────────────────────────────────────────────────────


def mat_inv(a: Matrix) -> Matrix:
    """Matrix inverse using Gauss-Jordan elimination with partial pivoting.
    Returns zero matrix if singular."""
    var n = a.rows
    if n != a.cols:
        return Matrix(n, n)

    # Augmented matrix [A | I]
    var aug = Matrix(n, 2 * n)
    for i in range(n):
        for j in range(n):
            aug.set(i, j, a.get(i, j))
        aug.set(i, n + i, 1.0)

    # Forward elimination with partial pivoting
    for col in range(n):
        # Find pivot
        var max_val: Float64 = 0.0
        var max_row = col
        for row in range(col, n):
            var v = fabs(aug.get(row, col))
            if v > max_val:
                max_val = v
                max_row = row

        if max_val < 1e-15:
            return Matrix(n, n)  # Singular

        # Swap rows
        if max_row != col:
            for j in range(2 * n):
                var tmp = aug.get(col, j)
                aug.set(col, j, aug.get(max_row, j))
                aug.set(max_row, j, tmp)

        # Scale pivot row
        var pivot = aug.get(col, col)
        for j in range(2 * n):
            aug.set(col, j, aug.get(col, j) / pivot)

        # Eliminate column in all other rows
        for row in range(n):
            if row == col:
                continue
            var factor = aug.get(row, col)
            for j in range(2 * n):
                aug.set(row, j, aug.get(row, j) - factor * aug.get(col, j))

    # Extract inverse from right half
    var inv = Matrix(n, n)
    for i in range(n):
        for j in range(n):
            inv.set(i, j, aug.get(i, n + j))

    return inv^


# ── Linear system solver ──────────────────────────────────────────────────────


def mat_solve(a: Matrix, b: List[Float64]) -> List[Float64]:
    """Solve Ax = b using Gaussian elimination with partial pivoting.
    Returns solution vector x."""
    var n = a.rows
    if n != a.cols or len(b) != n:
        var empty = List[Float64]()
        return empty^

    # Augmented matrix [A | b]
    var aug = Matrix(n, n + 1)
    for i in range(n):
        for j in range(n):
            aug.set(i, j, a.get(i, j))
        aug.set(i, n, b[i])

    # Forward elimination with partial pivoting
    for col in range(n):
        # Find pivot
        var max_val: Float64 = 0.0
        var max_row = col
        for row in range(col, n):
            var v = fabs(aug.get(row, col))
            if v > max_val:
                max_val = v
                max_row = row

        if max_val < 1e-15:
            # Singular; return zeros
            var zeros = List[Float64]()
            for i in range(n):
                zeros.append(0.0)
            return zeros^

        # Swap rows
        if max_row != col:
            for j in range(n + 1):
                var tmp = aug.get(col, j)
                aug.set(col, j, aug.get(max_row, j))
                aug.set(max_row, j, tmp)

        # Eliminate below
        for row in range(col + 1, n):
            var factor = aug.get(row, col) / aug.get(col, col)
            for j in range(col, n + 1):
                aug.set(row, j, aug.get(row, j) - factor * aug.get(col, j))

    # Back substitution
    var x = List[Float64]()
    for i in range(n):
        x.append(0.0)

    var i = n - 1
    while i >= 0:
        var s = aug.get(i, n)
        for j in range(i + 1, n):
            s -= aug.get(i, j) * x[j]
        if fabs(aug.get(i, i)) < 1e-15:
            x[i] = 0.0
        else:
            x[i] = s / aug.get(i, i)
        i -= 1

    return x^


# ── Vector operations ─────────────────────────────────────────────────────────


def vec_dot(a: List[Float64], b: List[Float64]) -> Float64:
    """Dot product of two vectors."""
    var n = len(a)
    if len(b) < n:
        n = len(b)
    var s: Float64 = 0.0
    for i in range(n):
        s += a[i] * b[i]
    return s


def vec_norm(a: List[Float64]) -> Float64:
    """Euclidean (L2) norm of a vector."""
    return sqrt(vec_dot(a, a))


def vec_cross(a: List[Float64], b: List[Float64]) -> List[Float64]:
    """Cross product of two 3D vectors.
    Requires len(a) >= 3 and len(b) >= 3."""
    var result = List[Float64]()
    if len(a) < 3 or len(b) < 3:
        result.append(0.0)
        result.append(0.0)
        result.append(0.0)
        return result^

    result.append(a[1] * b[2] - a[2] * b[1])
    result.append(a[2] * b[0] - a[0] * b[2])
    result.append(a[0] * b[1] - a[1] * b[0])
    return result^


# ── LU decomposition ─────────────────────────────────────────────────────────


struct LUResult(Copyable, Movable):
    """Result of LU decomposition."""
    var L: Matrix
    var U: Matrix
    var pivots: List[Int]

    def __init__(out self, L: Matrix, U: Matrix, pivots: List[Int]):
        self.L = L.copy()
        self.U = U.copy()
        self.pivots = pivots.copy()


def mat_lu(a: Matrix) -> LUResult:
    """LU decomposition with partial pivoting.
    Returns LUResult(L, U, pivots) such that P*A = L*U
    where P is encoded by pivot_indices."""
    var n = a.rows
    var L = mat_identity(n)
    var U = Matrix(n, n)
    for i in range(n * n):
        U.data[i] = a.data[i]

    var pivots = List[Int]()
    for i in range(n):
        pivots.append(i)

    for col in range(n):
        # Find pivot
        var max_val: Float64 = 0.0
        var max_row = col
        for row in range(col, n):
            var v = fabs(U.get(row, col))
            if v > max_val:
                max_val = v
                max_row = row

        if max_val < 1e-15:
            continue

        # Swap rows in U
        if max_row != col:
            for j in range(n):
                var tmp = U.get(col, j)
                U.set(col, j, U.get(max_row, j))
                U.set(max_row, j, tmp)

            # Swap rows in L (only columns 0..col-1)
            for j in range(col):
                var tmp = L.get(col, j)
                L.set(col, j, L.get(max_row, j))
                L.set(max_row, j, tmp)

            # Record pivot swap
            var tmp_p = pivots[col]
            pivots[col] = pivots[max_row]
            pivots[max_row] = tmp_p

        # Elimination
        for row in range(col + 1, n):
            var factor = U.get(row, col) / U.get(col, col)
            L.set(row, col, factor)
            for j in range(col, n):
                U.set(row, j, U.get(row, j) - factor * U.get(col, j))

    return LUResult(L, U, pivots)


# ── Eigenvalues (2×2) ────────────────────────────────────────────────────────


struct EigResult2x2(Copyable, Movable):
    """Result of 2x2 eigenvalue computation."""
    var lambda1: Float64
    var lambda2: Float64

    def __init__(out self, lambda1: Float64, lambda2: Float64):
        self.lambda1 = lambda1
        self.lambda2 = lambda2


def mat_eigenvalues_2x2(a: Matrix) -> EigResult2x2:
    """Eigenvalues of a 2×2 matrix using the quadratic formula.
    For [[a, b], [c, d]]:
      λ = ((a+d) ± sqrt((a+d)² - 4(ad-bc))) / 2
    Returns EigResult2x2(lambda1, lambda2). If complex, returns real parts."""
    if a.rows != 2 or a.cols != 2:
        return EigResult2x2(0.0, 0.0)

    var trace = a.get(0, 0) + a.get(1, 1)
    var det = a.get(0, 0) * a.get(1, 1) - a.get(0, 1) * a.get(1, 0)
    var disc = trace * trace - 4.0 * det

    if disc < 0.0:
        # Complex eigenvalues — return real part
        var re = trace / 2.0
        return EigResult2x2(re, re)

    var sq = sqrt(disc)
    return EigResult2x2((trace + sq) / 2.0, (trace - sq) / 2.0)
