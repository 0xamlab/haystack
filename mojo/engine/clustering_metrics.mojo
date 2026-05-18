"""
clustering_metrics.mojo — Clustering quality metrics. Zero Python imports.

Replaces sklearn.metrics.cluster with pure Mojo implementations for
Davies-Bouldin, Calinski-Harabasz, ARI, purity, contingency matrix,
inertia, cluster sizes, and cluster centroids.

Public API:
  cluster_sizes        — Count items per cluster
  cluster_centroids    — Compute centroid of each cluster
  inertia              — Within-cluster sum of squares
  davies_bouldin       — Davies-Bouldin index (lower=better)
  calinski_harabasz    — Calinski-Harabasz index (higher=better)
  contingency_matrix   — Contingency table
  purity               — Cluster purity
  adjusted_rand_index  — Adjusted Rand Index
"""
from std.math import sqrt, abs as fabs


# ── cluster_sizes ─────────────────────────────────────────────────────────────


fn cluster_sizes(labels: List[Int], k: Int) -> List[Int]:
    """Count the number of items assigned to each cluster 0..k-1."""
    var counts = List[Int]()
    for i in range(k):
        counts.append(0)
    for i in range(len(labels)):
        var c = labels[i]
        if c >= 0 and c < k:
            counts[c] += 1
    return counts^


# ── cluster_centroids ─────────────────────────────────────────────────────────


fn cluster_centroids(
    data: List[List[Float64]], labels: List[Int], k: Int
) -> List[List[Float64]]:
    """Compute the centroid (mean) of each cluster."""
    var n = len(data)
    if n == 0:
        return List[List[Float64]]()
    var dim = len(data[0])
    # Initialise sums and counts
    var sums = List[List[Float64]]()
    var counts = List[Int]()
    for c in range(k):
        var row = List[Float64]()
        for d in range(dim):
            row.append(0.0)
        sums.append(row^)
        counts.append(0)
    # Accumulate
    for i in range(n):
        var c = labels[i]
        if c >= 0 and c < k:
            counts[c] += 1
            for d in range(dim):
                sums[c][d] += data[i][d]
    # Divide
    for c in range(k):
        if counts[c] > 0:
            var cnt = Float64(counts[c])
            for d in range(dim):
                sums[c][d] /= cnt
    return sums^


# ── _euclidean_dist ───────────────────────────────────────────────────────────


fn _euclidean_dist(a: List[Float64], b: List[Float64]) -> Float64:
    """Euclidean distance between two vectors."""
    var s: Float64 = 0.0
    var n = len(a)
    for i in range(n):
        var d = a[i] - b[i]
        s += d * d
    return sqrt(s)


# ── inertia ───────────────────────────────────────────────────────────────────


fn inertia(
    data: List[List[Float64]],
    labels: List[Int],
    centroids: List[List[Float64]],
) -> Float64:
    """Within-cluster sum of squared distances to centroids."""
    var total: Float64 = 0.0
    var n = len(data)
    for i in range(n):
        var c = labels[i]
        var dim = len(data[i])
        for d in range(dim):
            var diff = data[i][d] - centroids[c][d]
            total += diff * diff
    return total


# ── davies_bouldin ────────────────────────────────────────────────────────────


fn davies_bouldin(
    data: List[List[Float64]], labels: List[Int], k: Int
) -> Float64:
    """Davies-Bouldin index (lower is better).

    DB = (1/k) Σ_i max_{j≠i} (s_i + s_j) / d(c_i, c_j)
    where s_i is avg distance from points in cluster i to centroid i.
    """
    var cents = cluster_centroids(data, labels, k)
    var n = len(data)
    # Compute scatter for each cluster
    var scatter = List[Float64]()
    var sizes = cluster_sizes(labels, k)
    for c in range(k):
        scatter.append(0.0)
    for i in range(n):
        var c = labels[i]
        scatter[c] += _euclidean_dist(data[i], cents[c])
    for c in range(k):
        if sizes[c] > 0:
            scatter[c] /= Float64(sizes[c])
    # Compute DB
    var db: Float64 = 0.0
    for i in range(k):
        var max_r: Float64 = 0.0
        for j in range(k):
            if i != j:
                var d_ij = _euclidean_dist(cents[i], cents[j])
                if d_ij > 1e-15:
                    var r = (scatter[i] + scatter[j]) / d_ij
                    if r > max_r:
                        max_r = r
        db += max_r
    if k > 0:
        db /= Float64(k)
    return db


# ── calinski_harabasz ─────────────────────────────────────────────────────────


fn calinski_harabasz(
    data: List[List[Float64]], labels: List[Int], k: Int
) -> Float64:
    """Calinski-Harabasz index (higher is better).

    CH = [B / (k-1)] / [W / (n-k)]
    B = between-cluster dispersion, W = within-cluster dispersion.
    """
    var n = len(data)
    if n <= k or k <= 1:
        return 0.0
    var dim = len(data[0])
    var cents = cluster_centroids(data, labels, k)
    var sizes = cluster_sizes(labels, k)
    # Global mean
    var global_mean = List[Float64]()
    for d in range(dim):
        global_mean.append(0.0)
    for i in range(n):
        for d in range(dim):
            global_mean[d] += data[i][d]
    for d in range(dim):
        global_mean[d] /= Float64(n)
    # Between-group dispersion B
    var bg: Float64 = 0.0
    for c in range(k):
        var dist_sq: Float64 = 0.0
        for d in range(dim):
            var diff = cents[c][d] - global_mean[d]
            dist_sq += diff * diff
        bg += Float64(sizes[c]) * dist_sq
    # Within-group dispersion W
    var wg: Float64 = 0.0
    for i in range(n):
        var c = labels[i]
        for d in range(dim):
            var diff = data[i][d] - cents[c][d]
            wg += diff * diff
    if wg < 1e-15:
        return 0.0
    return (bg / Float64(k - 1)) / (wg / Float64(n - k))


# ── contingency_matrix ────────────────────────────────────────────────────────


fn contingency_matrix(
    labels_true: List[Int],
    labels_pred: List[Int],
    n_true: Int,
    n_pred: Int,
) -> List[List[Int]]:
    """Build a contingency table (n_true x n_pred)."""
    var mat = List[List[Int]]()
    for i in range(n_true):
        var row = List[Int]()
        for j in range(n_pred):
            row.append(0)
        mat.append(row^)
    var n = len(labels_true)
    for i in range(n):
        var t = labels_true[i]
        var p = labels_pred[i]
        if t >= 0 and t < n_true and p >= 0 and p < n_pred:
            mat[t][p] += 1
    return mat^


# ── purity ────────────────────────────────────────────────────────────────────


fn purity(
    labels_true: List[Int],
    labels_pred: List[Int],
    n_true: Int,
    n_pred: Int,
) -> Float64:
    """Cluster purity: fraction of correctly assigned items."""
    var n = len(labels_true)
    if n == 0:
        return 0.0
    var mat = contingency_matrix(labels_true, labels_pred, n_true, n_pred)
    var correct: Int = 0
    for j in range(n_pred):
        var max_count: Int = 0
        for i in range(n_true):
            if mat[i][j] > max_count:
                max_count = mat[i][j]
        correct += max_count
    return Float64(correct) / Float64(n)


# ── adjusted_rand_index ──────────────────────────────────────────────────────


fn _comb2(n: Int) -> Int:
    """C(n, 2)."""
    if n < 2:
        return 0
    return n * (n - 1) // 2


fn adjusted_rand_index(
    labels_true: List[Int], labels_pred: List[Int]
) -> Float64:
    """Adjusted Rand Index: corrected-for-chance Rand index in [-1,1].

    ARI = (RI - Expected_RI) / (max_RI - Expected_RI)
    """
    var n = len(labels_true)
    if n == 0:
        return 0.0
    # Find max label values
    var max_true: Int = 0
    var max_pred: Int = 0
    for i in range(n):
        if labels_true[i] > max_true:
            max_true = labels_true[i]
        if labels_pred[i] > max_pred:
            max_pred = labels_pred[i]
    var n_true = max_true + 1
    var n_pred = max_pred + 1
    var mat = contingency_matrix(labels_true, labels_pred, n_true, n_pred)
    # Row sums and column sums
    var row_sums = List[Int]()
    for i in range(n_true):
        var s: Int = 0
        for j in range(n_pred):
            s += mat[i][j]
        row_sums.append(s)
    var col_sums = List[Int]()
    for j in range(n_pred):
        var s: Int = 0
        for i in range(n_true):
            s += mat[i][j]
        col_sums.append(s)
    # Sum of C(n_ij, 2)
    var sum_comb: Float64 = 0.0
    for i in range(n_true):
        for j in range(n_pred):
            sum_comb += Float64(_comb2(mat[i][j]))
    var sum_row: Float64 = 0.0
    for i in range(n_true):
        sum_row += Float64(_comb2(row_sums[i]))
    var sum_col: Float64 = 0.0
    for j in range(n_pred):
        sum_col += Float64(_comb2(col_sums[j]))
    var comb_n = Float64(_comb2(n))
    if comb_n < 1e-15:
        return 1.0
    var expected = sum_row * sum_col / comb_n
    var max_index = (sum_row + sum_col) / 2.0
    var denom = max_index - expected
    if fabs(denom) < 1e-15:
        return 1.0
    return (sum_comb - expected) / denom
