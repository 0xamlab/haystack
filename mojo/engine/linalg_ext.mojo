"""
linalg_ext.mojo — Extended linear algebra. Zero Python imports.
QR decomposition, norms, matrix properties, power iteration.
Builds on existing linalg.mojo Matrix struct.

Public API:
  QRResult, PowerIterResult,
  mat_qr, mat_norm_frobenius, mat_norm_inf, mat_trace,
  mat_is_symmetric, mat_is_positive_definite,
  mat_power_iteration, mat_condition_number
"""
from std.math import sqrt, abs as fabs
from linalg import (
    Matrix,
    mat_zeros,
    mat_identity,
    mat_from_list,
    mat_mul,
    mat_transpose,
    mat_inv,
    mat_det,
    vec_dot,
    vec_norm,
)


# ── Result structs ────────────────────────────────────────────────────────────


struct QRResult(Copyable, Movable):
    """Result of QR decomposition."""
    var Q: Matrix
    var R: Matrix

    def __init__(out self, Q: Matrix, R: Matrix):
        self.Q = Q.copy()
        self.R = R.copy()


struct PowerIterResult(Copyable, Movable):
    """Result of power iteration: dominant eigenvalue + eigenvector."""
    var eigenvalue: Float64
    var eigenvector: List[Float64]

    def __init__(out self, eigenvalue: Float64, eigenvector: List[Float64]):
        self.eigenvalue = eigenvalue
        self.eigenvector = eigenvector.copy()


# ── QR Decomposition (Modified Gram-Schmidt) ─────────────────────────────────


def mat_qr(a: Matrix) -> QRResult:
    """QR decomposition via Modified Gram-Schmidt.
    A = Q * R where Q is orthogonal and R is upper triangular.
    A is (m x n), Q is (m x n), R is (n x n). Assumes m >= n."""
    var m = a.rows
    var n = a.cols

    # Work with column vectors stored as lists
    # Extract columns of A
    var cols = List[List[Float64]]()
    for j in range(n):
        var col = List[Float64]()
        for i in range(m):
            col.append(a.get(i, j))
        cols.append(col^)

    # Modified Gram-Schmidt
    var q_cols = List[List[Float64]]()
    var r = mat_zeros(n, n)

    for j in range(n):
        # Start with column j
        var v = List[Float64]()
        for i in range(m):
            v.append(cols[j][i])

        # Subtract projections onto previous q vectors
        for i in range(j):
            var dot_val: Float64 = 0.0
            for k in range(m):
                dot_val += q_cols[i][k] * v[k]
            r.set(i, j, dot_val)
            for k in range(m):
                v[k] -= dot_val * q_cols[i][k]

        # Compute norm
        var norm_v: Float64 = 0.0
        for k in range(m):
            norm_v += v[k] * v[k]
        norm_v = sqrt(norm_v)

        r.set(j, j, norm_v)

        # Normalize
        if norm_v > 1e-15:
            for k in range(m):
                v[k] /= norm_v

        q_cols.append(v^)

    # Build Q matrix from columns
    var q = mat_zeros(m, n)
    for j in range(n):
        for i in range(m):
            q.set(i, j, q_cols[j][i])

    return QRResult(q^, r^)


# ── Frobenius Norm ────────────────────────────────────────────────────────────


def mat_norm_frobenius(a: Matrix) -> Float64:
    """Frobenius norm: sqrt(sum of squares of all elements)."""
    var s: Float64 = 0.0
    for i in range(a.rows * a.cols):
        s += a.data[i] * a.data[i]
    return sqrt(s)


# ── Infinity Norm ─────────────────────────────────────────────────────────────


def mat_norm_inf(a: Matrix) -> Float64:
    """Infinity norm: maximum absolute row sum."""
    var max_sum: Float64 = 0.0
    for i in range(a.rows):
        var row_sum: Float64 = 0.0
        for j in range(a.cols):
            row_sum += fabs(a.get(i, j))
        if row_sum > max_sum:
            max_sum = row_sum
    return max_sum


# ── Trace ─────────────────────────────────────────────────────────────────────


def mat_trace(a: Matrix) -> Float64:
    """Sum of diagonal elements."""
    var n = a.rows
    if a.cols < n:
        n = a.cols
    var s: Float64 = 0.0
    for i in range(n):
        s += a.get(i, i)
    return s


# ── Symmetry Check ────────────────────────────────────────────────────────────


def mat_is_symmetric(a: Matrix, tol: Float64 = 1e-10) -> Bool:
    """Check if matrix is symmetric within tolerance."""
    if a.rows != a.cols:
        return False
    var n = a.rows
    for i in range(n):
        for j in range(i + 1, n):
            if fabs(a.get(i, j) - a.get(j, i)) > tol:
                return False
    return True


# ── Positive Definite Check (via Cholesky attempt) ────────────────────────────


def mat_is_positive_definite(a: Matrix) -> Bool:
    """Check if matrix is positive definite by attempting Cholesky decomposition.
    Matrix must be symmetric."""
    if a.rows != a.cols:
        return False
    if not mat_is_symmetric(a):
        return False

    var n = a.rows
    # Attempt Cholesky: A = L * L^T
    var l = mat_zeros(n, n)

    for i in range(n):
        for j in range(i + 1):
            var s: Float64 = 0.0
            for k in range(j):
                s += l.get(i, k) * l.get(j, k)

            if i == j:
                var diag = a.get(i, i) - s
                if diag <= 0.0:
                    return False  # Not positive definite
                l.set(i, j, sqrt(diag))
            else:
                var lval = l.get(j, j)
                if fabs(lval) < 1e-15:
                    return False
                l.set(i, j, (a.get(i, j) - s) / lval)

    return True


# ── Power Iteration ───────────────────────────────────────────────────────────


def mat_power_iteration(a: Matrix, max_iter: Int = 100) -> PowerIterResult:
    """Find dominant eigenvalue and eigenvector using power iteration.
    Returns PowerIterResult(eigenvalue, eigenvector).
    Matrix must be square."""
    var n = a.rows

    # Initial guess: [1, 1, ..., 1] normalized
    var v = List[Float64]()
    var inv_sqrt_n = 1.0 / sqrt(Float64(n))
    for i in range(n):
        v.append(inv_sqrt_n)

    var eigenvalue: Float64 = 0.0

    for _iter in range(max_iter):
        # w = A * v
        var w = List[Float64]()
        for i in range(n):
            var s: Float64 = 0.0
            for j in range(n):
                s += a.get(i, j) * v[j]
            w.append(s)

        # Rayleigh quotient: eigenvalue = v^T * w / (v^T * v)
        var vw: Float64 = 0.0
        var vv: Float64 = 0.0
        for i in range(n):
            vw += v[i] * w[i]
            vv += v[i] * v[i]
        if vv > 1e-15:
            eigenvalue = vw / vv

        # Normalize w
        var norm_w: Float64 = 0.0
        for i in range(n):
            norm_w += w[i] * w[i]
        norm_w = sqrt(norm_w)

        if norm_w < 1e-15:
            break

        for i in range(n):
            v[i] = w[i] / norm_w

    return PowerIterResult(eigenvalue, v^)


# ── Approximate Condition Number ──────────────────────────────────────────────


def mat_condition_number(a: Matrix) -> Float64:
    """Approximate condition number using infinity norms: ||A||_inf * ||A^-1||_inf.
    Returns a large number if the matrix is singular."""
    if a.rows != a.cols:
        return 1e18

    var norm_a = mat_norm_inf(a)
    var a_inv = mat_inv(a)

    # Check if inverse is valid (not all zeros)
    var inv_is_zero = True
    for i in range(a_inv.rows * a_inv.cols):
        if fabs(a_inv.data[i]) > 1e-15:
            inv_is_zero = False
            break

    if inv_is_zero:
        return 1e18  # Singular matrix

    var norm_a_inv = mat_norm_inf(a_inv)
    return norm_a * norm_a_inv
