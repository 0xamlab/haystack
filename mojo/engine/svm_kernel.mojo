"""
svm_kernel.mojo — SVM kernel functions. Zero Python imports.

Replaces sklearn.svm kernel computations with pure Mojo implementations
for linear, RBF, polynomial, and sigmoid kernels, plus Gram matrix
construction, kernel centering, alignment, and PSD checking.

Public API:
  kernel_linear             — Linear kernel: a·b
  kernel_rbf                — RBF kernel: exp(-γ‖a-b‖²)
  kernel_polynomial         — Polynomial kernel: (a·b + coef0)^degree
  kernel_sigmoid            — Sigmoid kernel: tanh(γ·a·b + coef0)
  kernel_matrix             — NxN Gram matrix for a dataset
  kernel_center             — Center kernel matrix in feature space
  kernel_alignment          — Kernel alignment score
  frobenius_norm            — Frobenius norm of a matrix
  is_positive_semidefinite  — PSD check via diagonal dominance
"""
from std.math import sqrt, exp, abs as fabs, tanh


# ── kernel_linear ─────────────────────────────────────────────────────────────


fn kernel_linear(a: List[Float64], b: List[Float64]) -> Float64:
    """Linear kernel: dot product a·b."""
    var n = len(a)
    if len(b) < n:
        n = len(b)
    var s: Float64 = 0.0
    for i in range(n):
        s += a[i] * b[i]
    return s


# ── kernel_rbf ────────────────────────────────────────────────────────────────


fn kernel_rbf(
    a: List[Float64], b: List[Float64], gamma: Float64 = 1.0
) -> Float64:
    """RBF (Gaussian) kernel: exp(-γ·‖a-b‖²)."""
    var n = len(a)
    if len(b) < n:
        n = len(b)
    var sq: Float64 = 0.0
    for i in range(n):
        var d = a[i] - b[i]
        sq += d * d
    return exp(-gamma * sq)


# ── kernel_polynomial ─────────────────────────────────────────────────────────


fn kernel_polynomial(
    a: List[Float64],
    b: List[Float64],
    degree: Int = 3,
    coef0: Float64 = 0.0,
) -> Float64:
    """Polynomial kernel: (a·b + coef0)^degree."""
    var deg = degree
    if deg > 100:
        deg = 100  # ceiling: |base|^d overflows Float64 to inf well before d=100
    var dot = kernel_linear(a, b)
    var base = dot + coef0
    var result: Float64 = 1.0
    for _ in range(deg):
        result *= base
    return result


# ── kernel_sigmoid ────────────────────────────────────────────────────────────


fn kernel_sigmoid(
    a: List[Float64],
    b: List[Float64],
    gamma: Float64 = 1.0,
    coef0: Float64 = 0.0,
) -> Float64:
    """Sigmoid kernel: tanh(γ·a·b + coef0)."""
    var dot = kernel_linear(a, b)
    return tanh(gamma * dot + coef0)


# ── kernel_matrix ─────────────────────────────────────────────────────────────


fn kernel_matrix(
    data: List[List[Float64]],
    kernel_type: Int,
    gamma: Float64 = 1.0,
    degree: Int = 3,
    coef0: Float64 = 0.0,
) -> List[List[Float64]]:
    """NxN Gram matrix. kernel_type: 0=linear, 1=rbf, 2=poly, 3=sigmoid."""
    var n = len(data)
    var K = List[List[Float64]]()
    for i in range(n):
        var row = List[Float64]()
        for j in range(n):
            if kernel_type == 0:
                row.append(kernel_linear(data[i], data[j]))
            elif kernel_type == 1:
                row.append(kernel_rbf(data[i], data[j], gamma))
            elif kernel_type == 2:
                row.append(kernel_polynomial(data[i], data[j], degree, coef0))
            else:
                row.append(kernel_sigmoid(data[i], data[j], gamma, coef0))
        K.append(row^)
    return K^


# ── kernel_center ─────────────────────────────────────────────────────────────


fn kernel_center(K: List[List[Float64]]) -> List[List[Float64]]:
    """Center kernel matrix in feature space.

    Kc = K - 1_n K - K 1_n + 1_n K 1_n
    where 1_n is the n×n matrix with all entries 1/n.
    """
    var n = len(K)
    if n == 0:
        return List[List[Float64]]()
    var inv_n = 1.0 / Float64(n)

    # Row means
    var row_mean = List[Float64]()
    for i in range(n):
        var s: Float64 = 0.0
        for j in range(n):
            s += K[i][j]
        row_mean.append(s * inv_n)

    # Column means
    var col_mean = List[Float64]()
    for j in range(n):
        var s: Float64 = 0.0
        for i in range(n):
            s += K[i][j]
        col_mean.append(s * inv_n)

    # Grand mean
    var grand: Float64 = 0.0
    for i in range(n):
        grand += row_mean[i]
    grand *= inv_n

    # Centered matrix
    var Kc = List[List[Float64]]()
    for i in range(n):
        var row = List[Float64]()
        for j in range(n):
            row.append(K[i][j] - row_mean[i] - col_mean[j] + grand)
        Kc.append(row^)
    return Kc^


# ── frobenius_norm ────────────────────────────────────────────────────────────


fn frobenius_norm(K: List[List[Float64]]) -> Float64:
    """Frobenius norm: sqrt(Σᵢⱼ K[i][j]²)."""
    var s: Float64 = 0.0
    for i in range(len(K)):
        for j in range(len(K[i])):
            s += K[i][j] * K[i][j]
    return sqrt(s)


# ── kernel_alignment ──────────────────────────────────────────────────────────


fn kernel_alignment(
    K1: List[List[Float64]], K2: List[List[Float64]]
) -> Float64:
    """Kernel alignment: ⟨K1,K2⟩_F / (‖K1‖_F · ‖K2‖_F)."""
    var n = len(K1)
    if len(K2) < n:
        return 0.0
    var inner: Float64 = 0.0
    for i in range(n):
        if len(K2[i]) < len(K1[i]):
            return 0.0
        for j in range(len(K1[i])):
            inner += K1[i][j] * K2[i][j]
    var n1 = frobenius_norm(K1)
    var n2 = frobenius_norm(K2)
    if n1 < 1e-15 or n2 < 1e-15:
        return 0.0
    return inner / (n1 * n2)


# ── is_positive_semidefinite ──────────────────────────────────────────────────


fn is_positive_semidefinite(K: List[List[Float64]]) -> Bool:
    """Check if kernel matrix is PSD using diagonal dominance heuristic.

    A symmetric diagonally dominant matrix with non-negative diagonal
    entries is PSD. This is a sufficient (not necessary) condition.
    Also checks symmetry and non-negative diagonal.
    """
    var n = len(K)
    if n == 0:
        return True
    # Check symmetry and non-negative diagonal
    for i in range(n):
        if K[i][i] < -1e-10:
            return False
        for j in range(i + 1, n):
            if fabs(K[i][j] - K[j][i]) > 1e-10:
                return False
    # Diagonal dominance check
    for i in range(n):
        var off_sum: Float64 = 0.0
        for j in range(n):
            if j != i:
                off_sum += fabs(K[i][j])
        if K[i][i] + 1e-10 < off_sum:
            return False
    return True
