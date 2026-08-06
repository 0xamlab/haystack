"""
clustering.mojo — K-Means clustering and related utilities. Zero Python imports.

Replaces sklearn.cluster.KMeans with pure Mojo implementations.

Public API:
  KMeansResult        — Struct with centroids, labels, inertia, iterations
  euclidean_distance   — L2 distance between two vectors
  assign_cluster       — Nearest centroid index for a point
  kmeans               — Lloyd's algorithm with random init
  silhouette_score     — Mean silhouette coefficient
"""
from std.math import sqrt
from std.random import random_float64


# ── KMeansResult ──────────────────────────────────────────────────────────────


struct KMeansResult(Copyable, Movable):
    """Result of k-means clustering.

    Fields:
      centroids  — Final cluster centroids.
      labels     — Cluster assignment for each data point.
      inertia    — Sum of squared distances to nearest centroid.
      iterations — Number of iterations run.
    """

    var centroids: List[List[Float64]]
    var labels: List[Int]
    var inertia: Float64
    var iterations: Int

    def __init__(out self):
        self.centroids = List[List[Float64]]()
        self.labels = List[Int]()
        self.inertia = 0.0
        self.iterations = 0


# ── euclidean_distance ────────────────────────────────────────────────────────


def euclidean_distance(a: List[Float64], b: List[Float64]) -> Float64:
    """Euclidean (L2) distance between two vectors."""
    var n = len(a)
    if len(b) < n:
        n = len(b)
    var s: Float64 = 0.0
    for i in range(n):
        var d = a[i] - b[i]
        s += d * d
    return sqrt(s)


# ── assign_cluster ────────────────────────────────────────────────────────────


def assign_cluster(point: List[Float64], centroids: List[List[Float64]]) -> Int:
    """Return index of the nearest centroid to the given point."""
    var k = len(centroids)
    if k == 0:
        return 0
    var best = 0
    var best_dist = euclidean_distance(point, centroids[0])
    for c in range(1, k):
        var d = euclidean_distance(point, centroids[c])
        if d < best_dist:
            best_dist = d
            best = c
    return best


# ── kmeans ────────────────────────────────────────────────────────────────────


def kmeans(
    data: List[List[Float64]],
    k: Int,
    max_iter: Int = 100,
    tol: Float64 = 1e-6,
) -> KMeansResult:
    """K-Means clustering via Lloyd's algorithm with random initialisation.

    Args:
        data:     List of data points (each a List[Float64]).
        k:        Number of clusters.
        max_iter: Maximum iterations.
        tol:      Convergence tolerance on centroid movement.

    Returns:
        KMeansResult with centroids, labels, inertia, and iteration count.
    """
    var result = KMeansResult()
    var n = len(data)
    if n == 0 or k <= 0:
        return result^

    var dim = len(data[0])

    # Initialise labels
    for _ in range(n):
        result.labels.append(0)

    # Random initialisation: pick k distinct centroids from data
    var centroids = List[List[Float64]]()
    var used = List[Int]()
    for _ in range(k):
        var idx = Int(random_float64() * Float64(n))
        if idx >= n:
            idx = n - 1
        if idx < 0:
            idx = 0
        # Try to avoid duplicates (best-effort for small k)
        var attempts = 0
        while attempts < 10:
            var is_dup = False
            for u in range(len(used)):
                if used[u] == idx:
                    is_dup = True
                    break
            if not is_dup:
                break
            idx = (idx + 1) % n
            attempts += 1
        used.append(idx)
        var centroid = List[Float64]()
        for d in range(dim):
            centroid.append(data[idx][d])
        centroids.append(centroid^)

    # Lloyd's algorithm
    var iters = 0
    for it in range(max_iter):
        iters = it + 1

        # Assignment step
        for i in range(n):
            result.labels[i] = assign_cluster(data[i], centroids)

        # Update step: compute new centroids
        var new_centroids = List[List[Float64]]()
        var counts = List[Int]()
        for _ in range(k):
            var c = List[Float64]()
            for _ in range(dim):
                c.append(0.0)
            new_centroids.append(c^)
            counts.append(0)

        for i in range(n):
            var label = result.labels[i]
            counts[label] = counts[label] + 1
            for d in range(dim):
                new_centroids[label][d] = new_centroids[label][d] + data[i][d]

        for c in range(k):
            if counts[c] > 0:
                for d in range(dim):
                    new_centroids[c][d] = new_centroids[c][d] / Float64(counts[c])
            else:
                # Empty cluster: reinitialise randomly
                var idx = Int(random_float64() * Float64(n))
                if idx >= n:
                    idx = n - 1
                if idx < 0:
                    idx = 0
                for d in range(dim):
                    new_centroids[c][d] = data[idx][d]

        # Check convergence: max centroid movement
        var max_shift: Float64 = 0.0
        for c in range(k):
            var shift = euclidean_distance(centroids[c], new_centroids[c])
            if shift > max_shift:
                max_shift = shift

        # Update centroids
        centroids = new_centroids^

        if max_shift < tol:
            break

    # Compute inertia (sum of squared distances to assigned centroid)
    var inertia: Float64 = 0.0
    for i in range(n):
        var d = euclidean_distance(data[i], centroids[result.labels[i]])
        inertia += d * d

    result.centroids = centroids^
    result.inertia = inertia
    result.iterations = iters

    return result^


# ── silhouette_score ──────────────────────────────────────────────────────────


def silhouette_score(data: List[List[Float64]], labels: List[Int]) -> Float64:
    """Mean silhouette coefficient over all data points.

    For each point i:
      a(i) = mean distance to points in same cluster
      b(i) = min over other clusters of mean distance to that cluster
      s(i) = (b(i) - a(i)) / max(a(i), b(i))

    Returns mean of s(i) over all points. Range [-1, 1].
    """
    var n = len(data)
    # labels is indexed below for i in range(n); a short or empty list aborts (uncatchable).
    if n < 2 or len(labels) != n:
        return 0.0

    # Find number of clusters
    var max_label = 0
    for i in range(n):
        if labels[i] > max_label:
            max_label = labels[i]
    var k = max_label + 1
    if k < 2:
        return 0.0

    var total_silhouette: Float64 = 0.0

    for i in range(n):
        var label_i = labels[i]

        # Compute mean distance to same cluster (a) and other clusters
        var sum_same: Float64 = 0.0
        var count_same: Int = 0
        var sum_other = List[Float64]()
        var count_other = List[Int]()
        for _ in range(k):
            sum_other.append(0.0)
            count_other.append(0)

        for j in range(n):
            if i == j:
                continue
            var d = euclidean_distance(data[i], data[j])
            if labels[j] == label_i:
                sum_same += d
                count_same += 1
            else:
                sum_other[labels[j]] = sum_other[labels[j]] + d
                count_other[labels[j]] = count_other[labels[j]] + 1

        var a_i: Float64 = 0.0
        if count_same > 0:
            a_i = sum_same / Float64(count_same)

        # b(i) = min mean distance to other cluster
        var b_i: Float64 = 1e300
        for c in range(k):
            if c == label_i:
                continue
            if count_other[c] > 0:
                var mean_d = sum_other[c] / Float64(count_other[c])
                if mean_d < b_i:
                    b_i = mean_d

        if b_i > 1e299:
            b_i = 0.0

        var denom = a_i
        if b_i > denom:
            denom = b_i
        var s_i: Float64 = 0.0
        if denom > 1e-15:
            s_i = (b_i - a_i) / denom

        total_silhouette += s_i

    return total_silhouette / Float64(n)
