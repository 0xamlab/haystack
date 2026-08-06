"""
metrics.mojo — ML evaluation metrics. Zero Python imports.
Replaces: sklearn.metrics (accuracy_score, mean_squared_error, r2_score,
          confusion_matrix, precision_recall_fscore_support).

Public API:
  accuracy            — classification accuracy
  mse                 — mean squared error
  rmse                — root mean squared error
  mae                 — mean absolute error
  r2_score            — coefficient of determination R²
  confusion_matrix    — n×n confusion matrix (integer labels)
  precision_recall_f1 — binary classification precision, recall, F1
"""
from std.math import sqrt, abs as fabs


# ── Result struct for precision/recall/f1 ─────────────────────────────────────


struct PRF1Result(Copyable, Movable):
    """Result of precision_recall_f1: precision, recall, f1."""
    var precision: Float64
    var recall: Float64
    var f1: Float64

    def __init__(out self, precision: Float64, recall: Float64, f1: Float64):
        self.precision = precision
        self.recall = recall
        self.f1 = f1


# ── Accuracy ──────────────────────────────────────────────────────────────────


def accuracy(predicted: List[Float64], actual: List[Float64]) -> Float64:
    """Classification accuracy: fraction of correct predictions.

    Compares via rounding to nearest integer for float labels.
    """
    var n = len(predicted)
    if n == 0:
        return 0.0
    if len(actual) < n:
        n = len(actual)
    # An empty actual truncates n to 0; keep the sentinel instead of dividing by n.
    if n == 0:
        return 0.0

    var correct = 0
    for i in range(n):
        if Int(predicted[i] + 0.5) == Int(actual[i] + 0.5):
            correct += 1
    return Float64(correct) / Float64(n)


# ── Mean Squared Error ────────────────────────────────────────────────────────


def mse(predicted: List[Float64], actual: List[Float64]) -> Float64:
    """Mean Squared Error: (1/n) Σ (pred - actual)²."""
    var n = len(predicted)
    if n == 0:
        return 0.0
    if len(actual) < n:
        n = len(actual)
    # An empty actual truncates n to 0; keep the sentinel instead of dividing by n.
    if n == 0:
        return 0.0

    var s: Float64 = 0.0
    for i in range(n):
        var d = predicted[i] - actual[i]
        s += d * d
    return s / Float64(n)


# ── Root Mean Squared Error ───────────────────────────────────────────────────


def rmse(predicted: List[Float64], actual: List[Float64]) -> Float64:
    """Root Mean Squared Error: sqrt(MSE)."""
    return sqrt(mse(predicted, actual))


# ── Mean Absolute Error ───────────────────────────────────────────────────────


def mae(predicted: List[Float64], actual: List[Float64]) -> Float64:
    """Mean Absolute Error: (1/n) Σ |pred - actual|."""
    var n = len(predicted)
    if n == 0:
        return 0.0
    if len(actual) < n:
        n = len(actual)
    # An empty actual truncates n to 0; keep the sentinel instead of dividing by n.
    if n == 0:
        return 0.0

    var s: Float64 = 0.0
    for i in range(n):
        s += fabs(predicted[i] - actual[i])
    return s / Float64(n)


# ── R² Score ──────────────────────────────────────────────────────────────────


def r2_score(predicted: List[Float64], actual: List[Float64]) -> Float64:
    """Coefficient of determination R².

    R² = 1 - SS_res / SS_tot
    where SS_res = Σ(actual - pred)² and SS_tot = Σ(actual - mean_actual)².
    Returns 0.0 if SS_tot is zero (constant actual values).
    """
    var n = len(predicted)
    if n == 0:
        return 0.0
    if len(actual) < n:
        n = len(actual)

    # Compute mean of actual
    var mean_actual: Float64 = 0.0
    for i in range(n):
        mean_actual += actual[i]
    mean_actual /= Float64(n)

    var ss_res: Float64 = 0.0
    var ss_tot: Float64 = 0.0
    for i in range(n):
        var d_res = actual[i] - predicted[i]
        ss_res += d_res * d_res
        var d_tot = actual[i] - mean_actual
        ss_tot += d_tot * d_tot

    if ss_tot == 0.0:
        return 0.0
    return 1.0 - ss_res / ss_tot


# ── Confusion Matrix ─────────────────────────────────────────────────────────


def confusion_matrix(
    predicted: List[Int], actual: List[Int], n_classes: Int
) -> List[List[Int]]:
    """Build an n_classes × n_classes confusion matrix.

    matrix[actual][predicted] = count.
    """
    # Initialise n_classes × n_classes zeros
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


# ── Precision / Recall / F1 (binary) ─────────────────────────────────────────


def precision_recall_f1(
    predicted: List[Int], actual: List[Int]
) -> PRF1Result:
    """Binary classification precision, recall, F1-score.

    Positive class is 1, negative class is 0.
    Returns PRF1Result(precision, recall, f1).
    """
    var tp = 0
    var fp = 0
    var fn_count = 0

    var n = len(predicted)
    if len(actual) < n:
        n = len(actual)

    for i in range(n):
        if predicted[i] == 1 and actual[i] == 1:
            tp += 1
        elif predicted[i] == 1 and actual[i] == 0:
            fp += 1
        elif predicted[i] == 0 and actual[i] == 1:
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

    return PRF1Result(precision, recall, f1)
