"""
naive_bayes.mojo — Gaussian Naive Bayes classifier. Zero Python imports.

Replaces Python's sklearn.naive_bayes.GaussianNB with pure Mojo implementation.

Public API:
  gaussian_nb_fit           — Fit: compute per-class mean/std for each feature
  gaussian_nb_predict       — Predict single sample
  gaussian_nb_predict_batch — Predict batch of samples
  compute_priors            — Prior probabilities from labels
  gaussian_log_likelihood   — Log-likelihood of single value given mean/std
  accuracy                  — Classification accuracy (Int labels)
  confusion_matrix          — n×n confusion matrix
  precision_recall          — [precision, recall, f1] for target class
"""
from std.math import sqrt, log, abs as fabs

comptime PI: Float64 = 3.141592653589793
comptime MIN_STD: Float64 = 1e-9


# ── Priors ────────────────────────────────────────────────────────────────────


fn compute_priors(y: List[Int], n_classes: Int) -> List[Float64]:
    """Compute prior probabilities from integer labels.

    Returns a list of length n_classes with P(class=c) = count(c)/n.
    """
    var counts = List[Float64]()
    for _ in range(n_classes):
        counts.append(0.0)
    var n = len(y)
    for i in range(n):
        var c = y[i]
        if c >= 0 and c < n_classes:
            counts[c] = counts[c] + 1.0
    if n > 0:
        for c in range(n_classes):
            counts[c] = counts[c] / Float64(n)
    return counts^


# ── Gaussian Log-Likelihood ───────────────────────────────────────────────────


fn gaussian_log_likelihood(x: Float64, mean: Float64, std: Float64) -> Float64:
    """Log-likelihood of x under Gaussian(mean, std).

    log(1/(sqrt(2π)σ)) - (x-μ)²/(2σ²)
    """
    var s = std
    if s < MIN_STD:
        s = MIN_STD
    var diff = x - mean
    return -0.5 * log(2.0 * PI) - log(s) - (diff * diff) / (2.0 * s * s)


# ── Fit ───────────────────────────────────────────────────────────────────────


fn gaussian_nb_fit(
    X: List[List[Float64]], y: List[Int], n_classes: Int
) -> List[List[Float64]]:
    """Fit Gaussian Naive Bayes.

    Returns params where params[c] has n_features*2 values:
    [mean_f0, std_f0, mean_f1, std_f1, ...] for class c.
    """
    var n_samples = len(X)
    var n_features = 0
    if n_samples > 0:
        n_features = len(X[0])

    # Count per class
    var counts = List[Int]()
    for _ in range(n_classes):
        counts.append(0)
    for i in range(n_samples):
        var c = y[i]
        if c >= 0 and c < n_classes:
            counts[c] = counts[c] + 1

    # Sum per class per feature
    var sums = List[List[Float64]]()
    var sq_sums = List[List[Float64]]()
    for _ in range(n_classes):
        var row = List[Float64]()
        var sq_row = List[Float64]()
        for _ in range(n_features):
            row.append(0.0)
            sq_row.append(0.0)
        sums.append(row^)
        sq_sums.append(sq_row^)

    for i in range(n_samples):
        var c = y[i]
        if c >= 0 and c < n_classes:
            for f in range(n_features):
                var v = X[i][f]
                sums[c][f] = sums[c][f] + v
                sq_sums[c][f] = sq_sums[c][f] + v * v

    # Compute mean and std
    var params = List[List[Float64]]()
    for c in range(n_classes):
        var row = List[Float64]()
        var cnt = Float64(counts[c])
        for f in range(n_features):
            if cnt > 0.0:
                var mean = sums[c][f] / cnt
                var variance = sq_sums[c][f] / cnt - mean * mean
                if variance < 0.0:
                    variance = 0.0
                var std = sqrt(variance)
                if std < MIN_STD:
                    std = MIN_STD
                row.append(mean)
                row.append(std)
            else:
                row.append(0.0)
                row.append(MIN_STD)
        params.append(row^)

    return params^


# ── Predict Single ────────────────────────────────────────────────────────────


fn gaussian_nb_predict(
    params: List[List[Float64]],
    priors: List[Float64],
    x: List[Float64],
) -> Int:
    """Predict class for a single sample using Gaussian NB.

    Uses log-posterior: log(prior) + Σ log_likelihood(x_f | mean, std).
    """
    var n_classes = len(params)
    var best_class = 0
    var best_score = -1e308

    for c in range(n_classes):
        var score: Float64 = 0.0
        if priors[c] > 0.0:
            score = log(priors[c])
        else:
            score = -1e308

        var n_features = len(x)
        for f in range(n_features):
            var mean = params[c][f * 2]
            var std = params[c][f * 2 + 1]
            score += gaussian_log_likelihood(x[f], mean, std)

        if score > best_score:
            best_score = score
            best_class = c

    return best_class


# ── Predict Batch ─────────────────────────────────────────────────────────────


fn gaussian_nb_predict_batch(
    params: List[List[Float64]],
    priors: List[Float64],
    X: List[List[Float64]],
) -> List[Int]:
    """Predict classes for a batch of samples."""
    var results = List[Int]()
    for i in range(len(X)):
        results.append(gaussian_nb_predict(params, priors, X[i]))
    return results^


# ── Accuracy ──────────────────────────────────────────────────────────────────


fn accuracy(predicted: List[Int], actual: List[Int]) -> Float64:
    """Classification accuracy: fraction of correct predictions."""
    var n = len(predicted)
    if len(actual) < n:
        n = len(actual)
    if n == 0:
        return 0.0
    var correct = 0
    for i in range(n):
        if predicted[i] == actual[i]:
            correct += 1
    return Float64(correct) / Float64(n)


# ── Confusion Matrix ─────────────────────────────────────────────────────────


fn confusion_matrix(
    predicted: List[Int], actual: List[Int], n_classes: Int
) -> List[List[Int]]:
    """Build an n_classes × n_classes confusion matrix.

    matrix[actual][predicted] = count.
    """
    var mat = List[List[Int]]()
    for _ in range(n_classes):
        var row = List[Int]()
        for _ in range(n_classes):
            row.append(0)
        mat.append(row^)

    var n = len(predicted)
    if len(actual) < n:
        n = len(actual)

    for i in range(n):
        var a = actual[i]
        var p = predicted[i]
        if a >= 0 and a < n_classes and p >= 0 and p < n_classes:
            mat[a][p] = mat[a][p] + 1

    return mat^


# ── Precision / Recall / F1 ──────────────────────────────────────────────────


fn precision_recall(
    predicted: List[Int], actual: List[Int], target_class: Int
) -> List[Float64]:
    """Compute [precision, recall, f1] for a target class.

    Uses one-vs-rest: positive = target_class, negative = everything else.
    """
    var tp = 0
    var fp = 0
    var fn_count = 0

    var n = len(predicted)
    if len(actual) < n:
        n = len(actual)

    for i in range(n):
        if predicted[i] == target_class and actual[i] == target_class:
            tp += 1
        elif predicted[i] == target_class and actual[i] != target_class:
            fp += 1
        elif predicted[i] != target_class and actual[i] == target_class:
            fn_count += 1

    var precision: Float64 = 0.0
    if tp + fp > 0:
        precision = Float64(tp) / Float64(tp + fp)

    var recall: Float64 = 0.0
    if tp + fn_count > 0:
        recall = Float64(tp) / Float64(tp + fn_count)

    var f1: Float64 = 0.0
    if precision + recall > 0.0:
        f1 = 2.0 * precision * recall / (precision + recall)

    var result = List[Float64]()
    result.append(precision)
    result.append(recall)
    result.append(f1)
    return result^
