"""
dimensionality.mojo — PCA and related linear algebra. Zero Python imports.

Replaces sklearn.decomposition.PCA with pure Mojo implementations using
power iteration for eigenvalue extraction.

Public API:
  PCAResult             — Struct with components, explained_variance, etc.
  column_means          — Mean of each column
  center_data           — Subtract column means from each row
  covariance_matrix     — Covariance matrix of column-centered data
  power_iteration       — Find dominant eigenvector
  eigenvalue_from_vector — Compute eigenvalue given eigenvector
  deflate_matrix        — Matrix deflation: A' = A - λ*v*vᵀ
  pca                   — Principal Component Analysis
  transform_pca         — Project data onto principal components
"""
from std.math import sqrt, abs as fabs


# ── PCAResult ─────────────────────────────────────────────────────────────────


@fieldwise_init
struct PCAResult(Copyable, Movable):
    """Result of principal component analysis.

    Fields:
      components              — Eigenvectors (each a List[Float64])
      explained_variance      — Eigenvalues
      explained_variance_ratio — Fraction of total variance per component
      mean                    — Column means used for centering
    """

    var components: List[List[Float64]]
    var explained_variance: List[Float64]
    var explained_variance_ratio: List[Float64]
    var mean: List[Float64]

    fn __init__(out self):
        self.components = List[List[Float64]]()
        self.explained_variance = List[Float64]()
        self.explained_variance_ratio = List[Float64]()
        self.mean = List[Float64]()


# ── column_means ──────────────────────────────────────────────────────────────


fn column_means(data: List[List[Float64]]) -> List[Float64]:
    """Compute mean of each column."""
    var n = len(data)
    if n == 0:
        return List[Float64]()
    var d = len(data[0])
    var means = List[Float64]()
    for j in range(d):
        var s: Float64 = 0.0
        for i in range(n):
            s += data[i][j]
        means.append(s / Float64(n))
    return means^


# ── center_data ───────────────────────────────────────────────────────────────


fn center_data(data: List[List[Float64]]) -> List[List[Float64]]:
    """Subtract column means from each row."""
    var n = len(data)
    if n == 0:
        return List[List[Float64]]()
    var means = column_means(data)
    var d = len(means)
    var result = List[List[Float64]]()
    for i in range(n):
        var row = List[Float64]()
        for j in range(d):
            row.append(data[i][j] - means[j])
        result.append(row^)
    return result^


# ── covariance_matrix ─────────────────────────────────────────────────────────


fn covariance_matrix(data: List[List[Float64]]) -> List[List[Float64]]:
    """Compute covariance matrix of column-centered data.

    Cov(j, k) = (1/(n-1)) * Σᵢ data[i][j] * data[i][k]
    Data should already be centered.
    """
    var n = len(data)
    var result = List[List[Float64]]()
    if n < 2:
        return result^
    var d = len(data[0])

    for j in range(d):
        var row = List[Float64]()
        for k in range(d):
            var s: Float64 = 0.0
            for i in range(n):
                s += data[i][j] * data[i][k]
            row.append(s / Float64(n - 1))
        result.append(row^)
    return result^


# ── power_iteration ───────────────────────────────────────────────────────────


fn power_iteration(
    matrix: List[List[Float64]], n_iter: Int = 100
) -> List[Float64]:
    """Find dominant eigenvector via power iteration.

    Initialises with [1, 0, 0, ...] and iterates b ← Ab / ||Ab||.
    Returns normalised eigenvector.
    """
    var d = len(matrix)
    if d == 0:
        return List[Float64]()

    # Initialise with [1, 1, 1, ...] / sqrt(d) for robustness
    var b = List[Float64]()
    var init_val = 1.0 / sqrt(Float64(d))
    for _ in range(d):
        b.append(init_val)

    for _ in range(n_iter):
        # Matrix-vector multiply: Ab
        var ab = List[Float64]()
        for i in range(d):
            var s: Float64 = 0.0
            for j in range(d):
                s += matrix[i][j] * b[j]
            ab.append(s)

        # Normalise
        var norm: Float64 = 0.0
        for i in range(d):
            norm += ab[i] * ab[i]
        norm = sqrt(norm)
        if norm < 1e-15:
            return b^

        for i in range(d):
            b[i] = ab[i] / norm

    return b^


# ── eigenvalue_from_vector ────────────────────────────────────────────────────


fn eigenvalue_from_vector(
    matrix: List[List[Float64]], eigvec: List[Float64]
) -> Float64:
    """Compute eigenvalue given eigenvector: λ = (Av · v) / (v · v)."""
    var d = len(eigvec)
    if d == 0:
        return 0.0

    # Compute Av
    var av = List[Float64]()
    for i in range(d):
        var s: Float64 = 0.0
        for j in range(d):
            s += matrix[i][j] * eigvec[j]
        av.append(s)

    # Dot products
    var av_dot_v: Float64 = 0.0
    var v_dot_v: Float64 = 0.0
    for i in range(d):
        av_dot_v += av[i] * eigvec[i]
        v_dot_v += eigvec[i] * eigvec[i]

    if v_dot_v < 1e-30:
        return 0.0
    return av_dot_v / v_dot_v


# ── deflate_matrix ────────────────────────────────────────────────────────────


fn deflate_matrix(
    matrix: List[List[Float64]], eigval: Float64, eigvec: List[Float64]
) -> List[List[Float64]]:
    """Matrix deflation: A' = A - λ * v * vᵀ.

    Used to extract successive eigenvectors by removing the contribution
    of the dominant eigenvalue/eigenvector pair.
    """
    var d = len(matrix)
    var result = List[List[Float64]]()
    for i in range(d):
        var row = List[Float64]()
        for j in range(d):
            row.append(matrix[i][j] - eigval * eigvec[i] * eigvec[j])
        result.append(row^)
    return result^


# ── pca ───────────────────────────────────────────────────────────────────────


fn pca(data: List[List[Float64]], n_components: Int) -> PCAResult:
    """Principal Component Analysis.

    Centers data, computes covariance matrix, extracts top-k eigenvectors
    via repeated power iteration with deflation.
    """
    var result = PCAResult()
    var n = len(data)
    if n < 2:
        return result^
    var d = len(data[0])
    var k = n_components
    if k > d:
        k = d

    # Center data and store means
    result.mean = column_means(data)
    var centered = center_data(data)

    # Covariance matrix
    var cov = covariance_matrix(centered)

    # Extract eigenvalues/eigenvectors via power iteration + deflation
    var total_var: Float64 = 0.0
    # Total variance = trace of covariance matrix
    for i in range(d):
        total_var += cov[i][i]

    var current_cov = cov^
    for _ in range(k):
        var evec = power_iteration(current_cov, 200)
        var eval_ = eigenvalue_from_vector(current_cov, evec)
        if eval_ < 0.0:
            eval_ = 0.0
        result.components.append(evec^)
        result.explained_variance.append(eval_)
        current_cov = deflate_matrix(current_cov, eval_, result.components[len(result.components) - 1])

    # Compute variance ratios
    for i in range(k):
        if total_var > 1e-15:
            result.explained_variance_ratio.append(
                result.explained_variance[i] / total_var
            )
        else:
            result.explained_variance_ratio.append(0.0)

    return result^


# ── transform_pca ─────────────────────────────────────────────────────────────


fn transform_pca(
    data: List[List[Float64]], result: PCAResult
) -> List[List[Float64]]:
    """Project data onto principal components.

    Centers each row by subtracting the PCA mean, then multiplies
    by the component matrix.
    """
    var n = len(data)
    var k = len(result.components)
    var output = List[List[Float64]]()
    if n == 0 or k == 0:
        return output^
    var d = len(result.mean)

    for i in range(n):
        var row = List[Float64]()
        for c in range(k):
            var val: Float64 = 0.0
            for j in range(d):
                val += (data[i][j] - result.mean[j]) * result.components[c][j]
            row.append(val)
        output.append(row^)
    return output^
