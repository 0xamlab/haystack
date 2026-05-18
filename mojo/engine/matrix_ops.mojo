"""
matrix_ops.mojo — Extended Matrix Operations. Zero Python imports.

Extends linalg with Kronecker product, Hadamard product, matrix power,
outer product, matrix exponential, vectorization, norms, commutator,
orthogonality check, and Gram-Schmidt orthogonalization.

Public API:
  kronecker_product  — Kronecker/tensor product A ⊗ B
  hadamard_product   — Element-wise product A ∘ B
  matrix_power       — A^n via repeated squaring
  outer_product      — a ⊗ bᵀ
  matrix_exp_approx  — Matrix exponential via Taylor series
  vec                — Vectorize matrix (column-major)
  unvec              — Reshape vector to matrix
  matrix_norm_1      — L1 norm (max column sum)
  matrix_norm_inf    — L∞ norm (max row sum)
  commutator         — [A,B] = AB - BA
  is_orthogonal      — Check if AᵀA ≈ I
  gram_schmidt       — Gram-Schmidt orthogonalization
"""
from std.math import sqrt, abs as fabs


# ── Internal helpers ──────────────────────────────────────────────────────────


fn _mat_rows(A: List[List[Float64]]) -> Int:
    return len(A)


fn _mat_cols(A: List[List[Float64]]) -> Int:
    if len(A) == 0:
        return 0
    return len(A[0])


fn _mat_mul(A: List[List[Float64]], B: List[List[Float64]]) -> List[List[Float64]]:
    """Multiply two matrices A (m×p) and B (p×n) -> (m×n)."""
    var m = _mat_rows(A)
    var p = _mat_cols(A)
    var n = _mat_cols(B)
    var C = List[List[Float64]]()
    for i in range(m):
        var row = List[Float64]()
        for j in range(n):
            var s: Float64 = 0.0
            for k in range(p):
                s += A[i][k] * B[k][j]
            row.append(s)
        C.append(row^)
    return C^


fn _mat_identity(n: Int) -> List[List[Float64]]:
    """Create n×n identity matrix."""
    var I = List[List[Float64]]()
    for i in range(n):
        var row = List[Float64]()
        for j in range(n):
            if i == j:
                row.append(1.0)
            else:
                row.append(0.0)
        I.append(row^)
    return I^


fn _mat_add(A: List[List[Float64]], B: List[List[Float64]]) -> List[List[Float64]]:
    """Add two matrices element-wise."""
    var m = _mat_rows(A)
    var n = _mat_cols(A)
    var C = List[List[Float64]]()
    for i in range(m):
        var row = List[Float64]()
        for j in range(n):
            row.append(A[i][j] + B[i][j])
        C.append(row^)
    return C^


fn _mat_sub(A: List[List[Float64]], B: List[List[Float64]]) -> List[List[Float64]]:
    """Subtract two matrices element-wise."""
    var m = _mat_rows(A)
    var n = _mat_cols(A)
    var C = List[List[Float64]]()
    for i in range(m):
        var row = List[Float64]()
        for j in range(n):
            row.append(A[i][j] - B[i][j])
        C.append(row^)
    return C^


fn _mat_scale(A: List[List[Float64]], s: Float64) -> List[List[Float64]]:
    """Scale matrix by scalar."""
    var m = _mat_rows(A)
    var n = _mat_cols(A)
    var C = List[List[Float64]]()
    for i in range(m):
        var row = List[Float64]()
        for j in range(n):
            row.append(A[i][j] * s)
        C.append(row^)
    return C^


# ── kronecker_product ─────────────────────────────────────────────────────────


fn kronecker_product(
    A: List[List[Float64]], B: List[List[Float64]]
) -> List[List[Float64]]:
    """Kronecker/tensor product A ⊗ B.

    If A is m×n and B is p×q, result is (m*p)×(n*q).
    """
    var m = _mat_rows(A)
    var n = _mat_cols(A)
    var p = _mat_rows(B)
    var q = _mat_cols(B)
    var C = List[List[Float64]]()
    for i in range(m * p):
        var row = List[Float64]()
        for j in range(n * q):
            var ai = i // p
            var bi = i % p
            var aj = j // q
            var bj = j % q
            row.append(A[ai][aj] * B[bi][bj])
        C.append(row^)
    return C^


# ── hadamard_product ──────────────────────────────────────────────────────────


fn hadamard_product(
    A: List[List[Float64]], B: List[List[Float64]]
) -> List[List[Float64]]:
    """Element-wise (Hadamard) product A ∘ B.

    A and B must have the same dimensions.
    """
    var m = _mat_rows(A)
    var n = _mat_cols(A)
    var C = List[List[Float64]]()
    for i in range(m):
        var row = List[Float64]()
        for j in range(n):
            row.append(A[i][j] * B[i][j])
        C.append(row^)
    return C^


# ── matrix_power ──────────────────────────────────────────────────────────────


fn matrix_power(
    A: List[List[Float64]], n: Int
) -> List[List[Float64]]:
    """A^n via repeated squaring (exponentiation by squaring).

    A must be square. n >= 0.
    """
    var size = _mat_rows(A)
    if n == 0:
        return _mat_identity(size)
    if n == 1:
        return A.copy()

    var result = _mat_identity(size)
    var base = A.copy()
    var exp = n
    while exp > 0:
        if exp % 2 == 1:
            result = _mat_mul(result, base)
        base = _mat_mul(base, base)
        exp = exp // 2
    return result^


# ── outer_product ─────────────────────────────────────────────────────────────


fn outer_product(
    a: List[Float64], b: List[Float64]
) -> List[List[Float64]]:
    """Outer product a ⊗ bᵀ = n×m matrix.

    Args:
        a: Column vector of length n.
        b: Row vector of length m.

    Returns:
        n×m matrix where C[i][j] = a[i]*b[j].
    """
    var n = len(a)
    var m = len(b)
    var C = List[List[Float64]]()
    for i in range(n):
        var row = List[Float64]()
        for j in range(m):
            row.append(a[i] * b[j])
        C.append(row^)
    return C^


# ── matrix_exp_approx ────────────────────────────────────────────────────────


fn matrix_exp_approx(
    A: List[List[Float64]], terms: Int = 10
) -> List[List[Float64]]:
    """Matrix exponential via Taylor series: e^A ≈ Σ A^k/k!.

    Args:
        A: Square matrix.
        terms: Number of Taylor terms (default 10).

    Returns:
        Approximation of e^A.
    """
    var size = _mat_rows(A)
    var result = _mat_identity(size)
    var term = _mat_identity(size)  # A^k / k!
    for k in range(1, terms):
        term = _mat_mul(term, A)
        term = _mat_scale(term, 1.0 / Float64(k))
        result = _mat_add(result, term)
    return result^


# ── vec ───────────────────────────────────────────────────────────────────────


fn vec(A: List[List[Float64]]) -> List[Float64]:
    """Vectorize matrix in column-major order.

    Args:
        A: Input matrix (m×n).

    Returns:
        Vector of length m*n in column-major order.
    """
    var m = _mat_rows(A)
    var n = _mat_cols(A)
    var v = List[Float64]()
    for j in range(n):
        for i in range(m):
            v.append(A[i][j])
    return v^


# ── unvec ─────────────────────────────────────────────────────────────────────


fn unvec(
    v: List[Float64], rows: Int, cols: Int
) -> List[List[Float64]]:
    """Reshape vector to matrix (column-major).

    Args:
        v: Input vector of length rows*cols.
        rows: Number of rows.
        cols: Number of columns.

    Returns:
        Matrix of dimensions rows×cols.
    """
    var A = List[List[Float64]]()
    for i in range(rows):
        var row = List[Float64]()
        for j in range(cols):
            row.append(v[j * rows + i])
        A.append(row^)
    return A^


# ── matrix_norm_1 ────────────────────────────────────────────────────────────


fn matrix_norm_1(A: List[List[Float64]]) -> Float64:
    """L1 norm: maximum absolute column sum.

    Args:
        A: Input matrix.

    Returns:
        L1 matrix norm.
    """
    var m = _mat_rows(A)
    var n = _mat_cols(A)
    var max_sum: Float64 = 0.0
    for j in range(n):
        var col_sum: Float64 = 0.0
        for i in range(m):
            col_sum += fabs(A[i][j])
        if col_sum > max_sum:
            max_sum = col_sum
    return max_sum


# ── matrix_norm_inf ───────────────────────────────────────────────────────────


fn matrix_norm_inf(A: List[List[Float64]]) -> Float64:
    """L∞ norm: maximum absolute row sum.

    Args:
        A: Input matrix.

    Returns:
        L∞ matrix norm.
    """
    var m = _mat_rows(A)
    var n = _mat_cols(A)
    var max_sum: Float64 = 0.0
    for i in range(m):
        var row_sum: Float64 = 0.0
        for j in range(n):
            row_sum += fabs(A[i][j])
        if row_sum > max_sum:
            max_sum = row_sum
    return max_sum


# ── commutator ────────────────────────────────────────────────────────────────


fn commutator(
    A: List[List[Float64]], B: List[List[Float64]]
) -> List[List[Float64]]:
    """Matrix commutator [A,B] = AB - BA.

    Args:
        A: Square matrix.
        B: Square matrix of same size.

    Returns:
        AB - BA.
    """
    var AB = _mat_mul(A, B)
    var BA = _mat_mul(B, A)
    return _mat_sub(AB, BA)


# ── is_orthogonal ─────────────────────────────────────────────────────────────


fn is_orthogonal(
    A: List[List[Float64]], tol: Float64 = 1e-8
) -> Bool:
    """Check if AᵀA ≈ I (orthogonal matrix).

    Args:
        A: Square matrix.
        tol: Tolerance for comparison (default 1e-8).

    Returns:
        True if AᵀA is approximately the identity.
    """
    var n = _mat_rows(A)
    var m = _mat_cols(A)
    # Compute AᵀA
    for i in range(m):
        for j in range(m):
            var s: Float64 = 0.0
            for k in range(n):
                s += A[k][i] * A[k][j]
            var expected: Float64 = 0.0
            if i == j:
                expected = 1.0
            if fabs(s - expected) > tol:
                return False
    return True


# ── gram_schmidt ──────────────────────────────────────────────────────────────


fn gram_schmidt(
    vectors: List[List[Float64]],
) -> List[List[Float64]]:
    """Gram-Schmidt orthogonalization.

    Takes a list of vectors and returns orthonormal vectors.

    Args:
        vectors: List of vectors (each a List[Float64]).

    Returns:
        List of orthonormalized vectors.
    """
    var n = len(vectors)
    if n == 0:
        return List[List[Float64]]()

    var dim = len(vectors[0])
    var result = List[List[Float64]]()

    for i in range(n):
        # Start with the original vector
        var v = List[Float64]()
        for d in range(dim):
            v.append(vectors[i][d])

        # Subtract projections onto previous orthonormal vectors
        for j in range(len(result)):
            var dot: Float64 = 0.0
            for d in range(dim):
                dot += v[d] * result[j][d]
            for d in range(dim):
                v[d] -= dot * result[j][d]

        # Normalize
        var norm: Float64 = 0.0
        for d in range(dim):
            norm += v[d] * v[d]
        norm = sqrt(norm)

        if norm > 1e-12:
            for d in range(dim):
                v[d] /= norm
            result.append(v^)

    return result^
