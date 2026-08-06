"""
classifiers.mojo — Simple ML classifiers and utilities. Zero Python imports.
Replaces: sklearn.neighbors.KNeighborsClassifier, sklearn.cluster.KMeans,
          basic distance/activation functions.

Public API:
  euclidean_distance  — L2 distance between two vectors
  manhattan_distance  — L1 distance between two vectors
  cosine_similarity   — cosine similarity between two vectors
  logistic_sigmoid    — σ(x) = 1 / (1 + exp(-x))
  softmax             — softmax over a list of values
  knn_predict         — k-nearest neighbors prediction (majority vote)
  kmeans_cluster      — k-means clustering (Lloyd's algorithm); raises on a
                        dimension mismatch in `data` (see its docstring)
"""
from std.math import sqrt, exp, abs as fabs
from std.random import random_float64


# ── Distance functions ────────────────────────────────────────────────────────


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


def manhattan_distance(a: List[Float64], b: List[Float64]) -> Float64:
    """Manhattan (L1) distance between two vectors."""
    var n = len(a)
    if len(b) < n:
        n = len(b)
    var s: Float64 = 0.0
    for i in range(n):
        s += fabs(a[i] - b[i])
    return s


def cosine_similarity(a: List[Float64], b: List[Float64]) -> Float64:
    """Cosine similarity: dot(a,b) / (||a|| * ||b||).

    Returns 0.0 if either vector has zero norm.
    """
    var n = len(a)
    if len(b) < n:
        n = len(b)

    var dot: Float64 = 0.0
    var norm_a: Float64 = 0.0
    var norm_b: Float64 = 0.0
    for i in range(n):
        dot += a[i] * b[i]
        norm_a += a[i] * a[i]
        norm_b += b[i] * b[i]

    var denom = sqrt(norm_a) * sqrt(norm_b)
    if denom == 0.0:
        return 0.0
    return dot / denom


# ── Activation functions ──────────────────────────────────────────────────────


def logistic_sigmoid(x: Float64) -> Float64:
    """Logistic sigmoid: σ(x) = 1 / (1 + exp(-x))."""
    if x >= 500.0:
        return 1.0
    if x <= -500.0:
        return 0.0
    return 1.0 / (1.0 + exp(-x))


def softmax(values: List[Float64]) -> List[Float64]:
    """Softmax: exp(x_i - max) / Σ exp(x_j - max).

    Numerically stable via max-subtraction.
    """
    var n = len(values)
    var result = List[Float64]()
    if n == 0:
        return result^

    # Find max for numerical stability
    var max_val = values[0]
    for i in range(1, n):
        if values[i] > max_val:
            max_val = values[i]

    # Compute exp(x - max) and sum
    var sum_exp: Float64 = 0.0
    for i in range(n):
        var e = exp(values[i] - max_val)
        result.append(e)
        sum_exp += e

    # Normalise
    if sum_exp > 0.0:
        for i in range(n):
            result[i] = result[i] / sum_exp

    return result^


# ── KNN prediction ────────────────────────────────────────────────────────────


def knn_predict(
    train_x: List[List[Float64]],
    train_y: List[Float64],
    test_point: List[Float64],
    k: Int,
) -> Float64:
    """K-nearest neighbors prediction (majority vote for classification).

    Computes Euclidean distance from test_point to every training point,
    finds the k nearest neighbours, and returns the most common label.
    For regression, this returns the mean of the k nearest labels.
    """
    var n = len(train_x)
    # k <= 0 leaves labels empty and labels[0] below aborts (uncatchable);
    # a short or mismatched train_y would be indexed past its end.
    if n == 0 or k <= 0 or len(train_y) != n:
        return 0.0

    # Compute all distances
    var distances = List[Float64]()
    var indices = List[Int]()
    for i in range(n):
        distances.append(euclidean_distance(train_x[i], test_point))
        indices.append(i)

    # Selection sort to find k nearest (partial sort)
    var k_actual = k
    if k_actual > n:
        k_actual = n

    for i in range(k_actual):
        var min_idx = i
        for j in range(i + 1, n):
            if distances[j] < distances[min_idx]:
                min_idx = j
        # Swap distances
        var tmp_d = distances[i]
        distances[i] = distances[min_idx]
        distances[min_idx] = tmp_d
        # Swap indices
        var tmp_i = indices[i]
        indices[i] = indices[min_idx]
        indices[min_idx] = tmp_i

    # Majority vote among k nearest — find distinct labels and their counts
    # Simple approach: collect k labels and find mode
    var labels = List[Float64]()
    for i in range(k_actual):
        labels.append(train_y[indices[i]])

    # Find mode (most frequent label)
    var best_label = labels[0]
    var best_count = 0

    for i in range(k_actual):
        var count = 0
        for j in range(k_actual):
            # Compare with tolerance for float labels
            if fabs(labels[i] - labels[j]) < 1e-9:
                count += 1
        if count > best_count:
            best_count = count
            best_label = labels[i]

    return best_label


# ── K-Means clustering ───────────────────────────────────────────────────────


def kmeans_cluster(
    data: List[List[Float64]], k: Int, max_iter: Int = 100
) raises -> List[Int]:
    """K-means clustering (Lloyd's algorithm).

    Args:
        data: list of data points (each a List[Float64]).
        k: number of clusters.
        max_iter: maximum iterations (default 100).

    Returns:
        List of cluster assignments (0..k-1) for each data point.

    Raises if any point after the first has a different length than
    `data[0]`. `dim` below is taken from `data[0]` alone, and both the random
    centroid initialisation (`data[idx][d]` for an arbitrary `idx`) and the
    update step (`data[i][d]` for every `i`) index every point in `data` up
    to `dim - 1` -- a shorter point anywhere in the list is an out-of-bounds
    `List` access, an uncatchable, worker-killing bounds assertion in this
    runtime rather than a normal exception (the exact same bug shape as
    `embeddings.centroid`, which raises for the same reason). Unlike this
    module's lenient min-length distance functions above, a crash is never
    correct behavior for any caller, so this is fixed in place rather than
    given a `_strict` sibling.
    """
    var n = len(data)
    if n == 0 or k <= 0:
        return List[Int]()

    var dim = len(data[0])
    for i in range(1, n):
        if len(data[i]) != dim:
            raise Error(
                "kmeans_cluster: data[0] has "
                + String(dim)
                + " dimensions but data["
                + String(i)
                + "] has "
                + String(len(data[i]))
                + "; all points must share the same dimensionality"
            )

    # Initialise assignments
    var assignments = List[Int]()
    for _ in range(n):
        assignments.append(0)

    # Random initialisation: pick k centroids from data indices
    var centroids = List[List[Float64]]()
    for _ in range(k):
        var idx = Int(random_float64() * Float64(n))
        if idx >= n:
            idx = n - 1
        if idx < 0:
            idx = 0
        var centroid = List[Float64]()
        for d in range(dim):
            centroid.append(data[idx][d])
        centroids.append(centroid^)

    # Lloyd's algorithm
    for _ in range(max_iter):
        var changed = False

        # Assignment step: assign each point to nearest centroid
        for i in range(n):
            var best_cluster = 0
            var best_dist: Float64 = 1e300
            for c in range(k):
                var dist = euclidean_distance(data[i], centroids[c])
                if dist < best_dist:
                    best_dist = dist
                    best_cluster = c
            if assignments[i] != best_cluster:
                assignments[i] = best_cluster
                changed = True

        # Early termination if no assignments changed
        if not changed:
            break

        # Update step: recompute centroids
        # Reset centroids to zero
        for c in range(k):
            for d in range(dim):
                centroids[c][d] = 0.0

        var counts = List[Int]()
        for _ in range(k):
            counts.append(0)

        for i in range(n):
            var c = assignments[i]
            counts[c] = counts[c] + 1
            for d in range(dim):
                centroids[c][d] = centroids[c][d] + data[i][d]

        for c in range(k):
            if counts[c] > 0:
                for d in range(dim):
                    centroids[c][d] = centroids[c][d] / Float64(counts[c])
            else:
                # Empty cluster: reinitialise randomly
                var idx = Int(random_float64() * Float64(n))
                if idx >= n:
                    idx = n - 1
                if idx < 0:
                    idx = 0
                for d in range(dim):
                    centroids[c][d] = data[idx][d]

    return assignments^
