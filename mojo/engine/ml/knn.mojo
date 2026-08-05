"""
knn.mojo — K-Nearest Neighbors. Zero Python imports.

Replaces sklearn.neighbors with pure Mojo implementations for KNN
classification, regression, distance-weighted voting, LOO cross-validation,
and optimal k selection.

Public API:
  euclidean_distance_knn  — L2 distance
  manhattan_distance      — L1 distance
  knn_distances           — Distances from test point to all training points
  k_nearest_indices       — Indices of k nearest points
  knn_predict             — KNN classification (majority vote)
  knn_predict_batch       — Batch KNN classification
  weighted_knn_predict    — Distance-weighted KNN classification
  knn_regression          — KNN for regression
  leave_one_out_cv        — LOO cross-validation accuracy
  optimal_k               — Find best k via LOO CV
"""

from std.math import sqrt, abs as fabs


# ── euclidean_distance_knn ───────────────────────────────────────────────────


fn euclidean_distance_knn(a: List[Float64], b: List[Float64]) -> Float64:
    """Euclidean (L2) distance between two vectors."""
    var n = len(a)
    if len(b) < n:
        n = len(b)
    var s: Float64 = 0.0
    for i in range(n):
        var d = a[i] - b[i]
        s += d * d
    return sqrt(s)


# ── manhattan_distance ───────────────────────────────────────────────────────


fn manhattan_distance(a: List[Float64], b: List[Float64]) -> Float64:
    """Manhattan (L1) distance between two vectors."""
    var n = len(a)
    if len(b) < n:
        n = len(b)
    var s: Float64 = 0.0
    for i in range(n):
        s += fabs(a[i] - b[i])
    return s


# ── knn_distances ────────────────────────────────────────────────────────────


fn knn_distances(X_train: List[List[Float64]],
                 x_test: List[Float64]) -> List[Float64]:
    """Compute Euclidean distances from test point to all training points."""
    var result = List[Float64]()
    for i in range(len(X_train)):
        result.append(euclidean_distance_knn(X_train[i], x_test))
    return result^


# ── k_nearest_indices ────────────────────────────────────────────────────────


fn k_nearest_indices(distances: List[Float64], k: Int) -> List[Int]:
    """Find indices of k nearest points (smallest distances)."""
    var n = len(distances)
    var actual_k = k
    if actual_k > n:
        actual_k = n
    var used = List[Bool]()
    for i in range(n):
        used.append(False)
    var indices = List[Int]()
    for _i in range(actual_k):
        var best_idx: Int = -1
        var best_dist: Float64 = 1e300
        for j in range(n):
            if not used[j] and distances[j] < best_dist:
                best_dist = distances[j]
                best_idx = j
        if best_idx >= 0:
            indices.append(best_idx)
            used[best_idx] = True
    return indices^


# ── _majority_vote ───────────────────────────────────────────────────────────


fn _majority_vote(labels: List[Int]) -> Int:
    """Return the most common label. Ties broken by first occurrence."""
    var n = len(labels)
    if n == 0:
        return 0
    var best_label = labels[0]
    var best_count: Int = 0
    for i in range(n):
        var count: Int = 0
        for j in range(n):
            if labels[j] == labels[i]:
                count += 1
        if count > best_count:
            best_count = count
            best_label = labels[i]
    return best_label


# ── knn_predict ──────────────────────────────────────────────────────────────


fn knn_predict(X_train: List[List[Float64]], y_train: List[Int],
               x_test: List[Float64], k: Int) -> Int:
    """Predict class for single test point using k-NN (majority vote)."""
    # A short or empty y_train would be indexed past its end below (uncatchable abort).
    if len(y_train) == 0 or len(y_train) != len(X_train):
        return 0
    var dists = knn_distances(X_train, x_test)
    var indices = k_nearest_indices(dists, k)
    var neighbor_labels = List[Int]()
    for i in range(len(indices)):
        neighbor_labels.append(y_train[indices[i]])
    return _majority_vote(neighbor_labels)


# ── knn_predict_batch ────────────────────────────────────────────────────────


fn knn_predict_batch(X_train: List[List[Float64]], y_train: List[Int],
                     X_test: List[List[Float64]], k: Int) -> List[Int]:
    """Batch prediction for multiple test points."""
    var result = List[Int]()
    # A short or empty y_train would be indexed past its end in knn_predict (uncatchable abort).
    if len(y_train) == 0 or len(y_train) != len(X_train):
        return result^
    for i in range(len(X_test)):
        result.append(knn_predict(X_train, y_train, X_test[i], k))
    return result^


# ── weighted_knn_predict ─────────────────────────────────────────────────────


fn weighted_knn_predict(X_train: List[List[Float64]], y_train: List[Int],
                        x_test: List[Float64], k: Int) -> Int:
    """Distance-weighted k-NN: weight = 1/distance."""
    # A short or empty y_train would be indexed past its end below (uncatchable abort).
    if len(y_train) == 0 or len(y_train) != len(X_train):
        return 0
    var dists = knn_distances(X_train, x_test)
    var indices = k_nearest_indices(dists, k)

    # Collect unique classes
    var classes = List[Int]()
    for i in range(len(indices)):
        var label = y_train[indices[i]]
        var found = False
        for j in range(len(classes)):
            if classes[j] == label:
                found = True
                break
        if not found:
            classes.append(label)

    var best_class = 0
    var best_weight: Float64 = -1.0
    for c in range(len(classes)):
        var w: Float64 = 0.0
        for i in range(len(indices)):
            if y_train[indices[i]] == classes[c]:
                var d = dists[indices[i]]
                if d < 1e-15:
                    w += 1e12
                else:
                    w += 1.0 / d
        if w > best_weight:
            best_weight = w
            best_class = classes[c]
    return best_class


# ── knn_regression ───────────────────────────────────────────────────────────


fn knn_regression(X_train: List[List[Float64]], y_train: List[Float64],
                  x_test: List[Float64], k: Int) -> Float64:
    """KNN for regression: average of k nearest y values."""
    # A short or empty y_train would be indexed past its end below (uncatchable abort).
    if len(y_train) == 0 or len(y_train) != len(X_train):
        return 0.0
    var dists = knn_distances(X_train, x_test)
    var indices = k_nearest_indices(dists, k)
    if len(indices) == 0:
        return 0.0
    var s: Float64 = 0.0
    for i in range(len(indices)):
        s += y_train[indices[i]]
    return s / Float64(len(indices))


# ── leave_one_out_cv ─────────────────────────────────────────────────────────


fn leave_one_out_cv(X: List[List[Float64]], y: List[Int],
                    k: Int) -> Float64:
    """Leave-one-out cross-validation accuracy for k-NN classification."""
    var n = len(X)
    # A short y would be read past its end below (uncatchable abort), so refuse with the sentinel.
    if len(y) != n:
        return 0.0
    if n <= 1:
        return 0.0
    var correct: Int = 0
    for i in range(n):
        var X_train = List[List[Float64]]()
        var y_train = List[Int]()
        for j in range(n):
            if j != i:
                X_train.append(X[j].copy())
                y_train.append(y[j])
        var pred = knn_predict(X_train, y_train, X[i], k)
        if pred == y[i]:
            correct += 1
    return Float64(correct) / Float64(n)


# ── optimal_k ────────────────────────────────────────────────────────────────


fn optimal_k(X: List[List[Float64]], y: List[Int], max_k: Int) -> Int:
    """Find best k in [1, max_k] via LOO cross-validation accuracy."""
    var n = len(X)
    # A short y would be read past its end in leave_one_out_cv (uncatchable abort).
    if len(y) != n:
        return 0
    var limit = max_k
    if limit >= n:
        limit = n - 1
    if limit < 1:
        limit = 1
    var best_k: Int = 1
    var best_acc: Float64 = -1.0
    for k in range(1, limit + 1):
        var acc = leave_one_out_cv(X, y, k)
        if acc > best_acc:
            best_acc = acc
            best_k = k
    return best_k
