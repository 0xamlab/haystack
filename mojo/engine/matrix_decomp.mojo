"""
matrix_decomp.mojo — Matrix decompositions. Zero Python imports.

Replaces numpy.linalg advanced decomposition routines with pure Mojo
implementations of LU, Cholesky, eigenvalue (2×2), determinants,
triangular solvers, and matrix property checks.

Public API:
  lu_decompose          — LU decomposition with partial pivoting
  cholesky              — Cholesky decomposition for SPD matrices
  eigen_2x2             — Eigenvalues and eigenvectors for 2×2
  det_2x2               — Determinant of 2×2 matrix
  det_3x3               — Determinant of 3×3 matrix
  trace                 — Sum of diagonal elements
  is_symmetric          — Check if A == A^T
  is_positive_definite  — Check via Cholesky attempt
  forward_substitution  — Solve Lx = b (lower triangular)
  back_substitution     — Solve Ux = b (upper triangular)
  solve_lu              — Solve Ax = b via LU decomposition
"""
from std.math import sqrt, abs as fabs, isinf, isnan


# ── det_2x2 ──────────────────────────────────────────────────────────────────


fn det_2x2(A: List[List[Float64]]) -> Float64:
    """Determinant of 2×2 matrix: ad - bc."""
    # A short or ragged matrix would be read past its end below (uncatchable
    # abort), so refuse with the degenerate determinant.
    if len(A) < 2 or len(A[0]) < 2 or len(A[1]) < 2:
        return 0.0
    return A[0][0] * A[1][1] - A[0][1] * A[1][0]


# ── det_3x3 ──────────────────────────────────────────────────────────────────


fn det_3x3(A: List[List[Float64]]) -> Float64:
    """Determinant of 3×3 matrix via cofactor expansion along row 0."""
    # A short or ragged matrix would be read past its end below (uncatchable
    # abort), so refuse with the degenerate determinant.
    if len(A) < 3 or len(A[0]) < 3 or len(A[1]) < 3 or len(A[2]) < 3:
        return 0.0
    var a = A[0][0]
    var b = A[0][1]
    var c = A[0][2]
    return (
        a * (A[1][1] * A[2][2] - A[1][2] * A[2][1])
        - b * (A[1][0] * A[2][2] - A[1][2] * A[2][0])
        + c * (A[1][0] * A[2][1] - A[1][1] * A[2][0])
    )


# ── trace ─────────────────────────────────────────────────────────────────────


fn trace(A: List[List[Float64]]) -> Float64:
    """Sum of diagonal elements."""
    var s: Float64 = 0.0
    var n = len(A)
    for i in range(n):
        s += A[i][i]
    return s


# ── is_symmetric ─────────────────────────────────────────────────────────────


fn is_symmetric(A: List[List[Float64]], tol: Float64 = 1e-10) -> Bool:
    """Check if A == A^T within tolerance."""
    var n = len(A)
    for i in range(n):
        if len(A[i]) != n:
            return False
        for j in range(i + 1, n):
            if fabs(A[i][j] - A[j][i]) > tol:
                return False
    return True


# ── cholesky ─────────────────────────────────────────────────────────────────


fn cholesky(A: List[List[Float64]]) -> List[List[Float64]]:
    """Cholesky decomposition for symmetric positive-definite matrix.
    Returns lower triangular L where A = L * L^T.
    Returns empty list if not SPD."""
    var n = len(A)
    # Build L as n×n zero matrix
    var L = List[List[Float64]]()
    for i in range(n):
        var row = List[Float64]()
        for j in range(n):
            row.append(0.0)
        L.append(row^)
    for i in range(n):
        for j in range(i + 1):
            var s: Float64 = 0.0
            for k in range(j):
                s += L[i][k] * L[j][k]
            if i == j:
                var val = A[i][i] - s
                if val <= 0.0:
                    return List[List[Float64]]()  # not PD
                L[i][j] = sqrt(val)
            else:
                if L[j][j] == 0.0:
                    return List[List[Float64]]()
                L[i][j] = (A[i][j] - s) / L[j][j]
    return L^


# ── is_positive_definite ─────────────────────────────────────────────────────


fn is_positive_definite(A: List[List[Float64]]) -> Bool:
    """Check if matrix is positive definite via Cholesky attempt."""
    var L = cholesky(A)
    return len(L) > 0


# ── lu_decompose ─────────────────────────────────────────────────────────────


fn lu_decompose(A: List[List[Float64]]) -> List[List[List[Float64]]]:
    """LU decomposition with partial pivoting.
    Returns [L, U] as list of two n×n matrices.
    Uses Doolittle algorithm (L has 1s on diagonal)."""
    var n = len(A)
    # Copy A into U
    var U = List[List[Float64]]()
    for i in range(n):
        var row = List[Float64]()
        for j in range(n):
            row.append(A[i][j])
        U.append(row^)
    # Initialize L as identity
    var L = List[List[Float64]]()
    for i in range(n):
        var row = List[Float64]()
        for j in range(n):
            if i == j:
                row.append(1.0)
            else:
                row.append(0.0)
        L.append(row^)
    for k in range(n):
        # Partial pivoting: find max in column k below diagonal
        var max_val = fabs(U[k][k])
        var max_row = k
        for i in range(k + 1, n):
            if fabs(U[i][k]) > max_val:
                max_val = fabs(U[i][k])
                max_row = i
        if max_row != k:
            # Swap rows in U
            var tmp_u = U[k].copy()
            U[k] = U[max_row].copy()
            U[max_row] = tmp_u^
            # Swap rows in L (only columns < k)
            for j in range(k):
                var tmp = L[k][j]
                L[k][j] = L[max_row][j]
                L[max_row][j] = tmp
        # Elimination
        for i in range(k + 1, n):
            if U[k][k] == 0.0:
                continue
            var factor = U[i][k] / U[k][k]
            L[i][k] = factor
            for j in range(k, n):
                U[i][j] = U[i][j] - factor * U[k][j]
    var result = List[List[List[Float64]]]()
    result.append(L^)
    result.append(U^)
    return result^


# ── eigen_2x2 ────────────────────────────────────────────────────────────────


fn eigen_2x2(A: List[List[Float64]]) -> List[List[Float64]]:
    """Eigenvalues and eigenvectors for 2×2 matrix.
    Returns [[λ1, λ2], [v1x, v1y], [v2x, v2y]]."""
    # A short or ragged matrix would be read past its end below (uncatchable
    # abort), so refuse with an empty result.
    if len(A) < 2 or len(A[0]) < 2 or len(A[1]) < 2:
        return List[List[Float64]]()
    var a = A[0][0]
    var b = A[0][1]
    var c = A[1][0]
    var d = A[1][1]
    # Characteristic equation: λ² - (a+d)λ + (ad-bc) = 0
    var tr = a + d
    var det = a * d - b * c
    var disc = tr * tr - 4.0 * det
    if disc < 0.0:
        disc = 0.0
    var sq = sqrt(disc)
    var l1 = (tr + sq) / 2.0
    var l2 = (tr - sq) / 2.0
    # Eigenvectors
    var eigenvalues = List[Float64]()
    eigenvalues.append(l1)
    eigenvalues.append(l2)
    # For each eigenvalue, solve (A - λI)v = 0
    var v1 = List[Float64]()
    var v2 = List[Float64]()
    # Eigenvector for l1
    if fabs(b) > 1e-15:
        v1.append(b)
        v1.append(l1 - a)
    elif fabs(c) > 1e-15:
        v1.append(l1 - d)
        v1.append(c)
    else:
        v1.append(1.0)
        v1.append(0.0)
    # Eigenvector for l2
    if fabs(b) > 1e-15:
        v2.append(b)
        v2.append(l2 - a)
    elif fabs(c) > 1e-15:
        v2.append(l2 - d)
        v2.append(c)
    else:
        v2.append(0.0)
        v2.append(1.0)
    # Normalize eigenvectors
    var mag1 = sqrt(v1[0] * v1[0] + v1[1] * v1[1])
    if mag1 > 1e-15:
        v1[0] = v1[0] / mag1
        v1[1] = v1[1] / mag1
    var mag2 = sqrt(v2[0] * v2[0] + v2[1] * v2[1])
    if mag2 > 1e-15:
        v2[0] = v2[0] / mag2
        v2[1] = v2[1] / mag2
    var result = List[List[Float64]]()
    result.append(eigenvalues^)
    result.append(v1^)
    result.append(v2^)
    return result^


# ── forward_substitution ─────────────────────────────────────────────────────


fn forward_substitution(L: List[List[Float64]], b: List[Float64]) -> List[Float64]:
    """Solve Lx = b where L is lower triangular."""
    var n = len(b)
    # A short or ragged L would be read past its end below (uncatchable
    # abort), and a non-finite b would poison the result (nan/inf cannot
    # cross the JSON result wire), so refuse with an empty solution.
    if len(L) < n:
        return List[Float64]()
    for i in range(n):
        if len(L[i]) < i + 1 or isnan(b[i]) or isinf(b[i]):
            return List[Float64]()
    var x = List[Float64]()
    for i in range(n):
        x.append(0.0)
    for i in range(n):
        var s: Float64 = 0.0
        for j in range(i):
            s += L[i][j] * x[j]
        if L[i][i] == 0.0:
            x[i] = 0.0
        else:
            x[i] = (b[i] - s) / L[i][i]
    return x^


# ── back_substitution ────────────────────────────────────────────────────────


fn back_substitution(U: List[List[Float64]], b: List[Float64]) -> List[Float64]:
    """Solve Ux = b where U is upper triangular."""
    var n = len(b)
    # A short or ragged U would be read past its end below (uncatchable
    # abort), and a non-finite b would poison the result (nan/inf cannot
    # cross the JSON result wire), so refuse with an empty solution.
    if len(U) < n:
        return List[Float64]()
    for i in range(n):
        if len(U[i]) < n or isnan(b[i]) or isinf(b[i]):
            return List[Float64]()
    var x = List[Float64]()
    for i in range(n):
        x.append(0.0)
    for i in range(n - 1, -1, -1):
        var s: Float64 = 0.0
        for j in range(i + 1, n):
            s += U[i][j] * x[j]
        if U[i][i] == 0.0:
            x[i] = 0.0
        else:
            x[i] = (b[i] - s) / U[i][i]
    return x^


# ── solve_lu ─────────────────────────────────────────────────────────────────


fn solve_lu(A: List[List[Float64]], b: List[Float64]) -> List[Float64]:
    """Solve Ax = b via Gaussian elimination with partial pivoting."""
    var n = len(b)
    # A short or ragged A would be read past its end below (uncatchable
    # abort), and a non-finite b would poison the result (nan/inf cannot
    # cross the JSON result wire), so refuse with an empty solution.
    if len(A) < n:
        return List[Float64]()
    for i in range(n):
        if len(A[i]) < n or isnan(b[i]) or isinf(b[i]):
            return List[Float64]()
    # Build augmented matrix [A|b]
    var M = List[List[Float64]]()
    for i in range(n):
        var row = List[Float64]()
        for j in range(n):
            row.append(A[i][j])
        row.append(b[i])
        M.append(row^)
    # Forward elimination with partial pivoting
    for k in range(n):
        # Find pivot
        var max_val = fabs(M[k][k])
        var max_row = k
        for i in range(k + 1, n):
            if fabs(M[i][k]) > max_val:
                max_val = fabs(M[i][k])
                max_row = i
        if max_row != k:
            var tmp = M[k].copy()
            M[k] = M[max_row].copy()
            M[max_row] = tmp^
        # Eliminate below
        for i in range(k + 1, n):
            if M[k][k] == 0.0:
                continue
            var factor = M[i][k] / M[k][k]
            for j in range(k, n + 1):
                M[i][j] = M[i][j] - factor * M[k][j]
    # Back substitution
    var x = List[Float64]()
    for i in range(n):
        x.append(0.0)
    for i in range(n - 1, -1, -1):
        var s: Float64 = 0.0
        for j in range(i + 1, n):
            s += M[i][j] * x[j]
        if M[i][i] == 0.0:
            x[i] = 0.0
        else:
            x[i] = (M[i][n] - s) / M[i][i]
    return x^
