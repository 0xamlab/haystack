"""
preprocessing.mojo — Feature preprocessing. Zero Python imports.
Replaces: sklearn.preprocessing (MinMaxScaler, StandardScaler, RobustScaler,
          OneHotEncoder, PolynomialFeatures, train_test_split).

Public API:
  normalize_minmax      — scale to [0, 1]
  normalize_zscore      — standard score (mean=0, std=1)
  normalize_robust      — median-IQR scaling
  one_hot_encode        — integer categories → one-hot rows
  polynomial_features   — [x, x², …, xᵈ]
  train_test_split      — split data/labels by ratio
"""
from math_ext import mean, stdev, median, iqr


# ── Result struct for train/test split ────────────────────────────────────────


struct SplitResult(Movable):
    """Result of train_test_split: train_data, test_data, train_labels, test_labels."""
    var train_data: List[Float64]
    var test_data: List[Float64]
    var train_labels: List[Float64]
    var test_labels: List[Float64]

    def __init__(out self):
        self.train_data = List[Float64]()
        self.test_data = List[Float64]()
        self.train_labels = List[Float64]()
        self.test_labels = List[Float64]()


# ── Min-Max normalisation ────────────────────────────────────────────────────


def normalize_minmax(data: List[Float64]) -> List[Float64]:
    """Scale values to [0, 1] range.

    formula: (x - min) / (max - min)
    If all values are identical, returns list of zeros.
    """
    var n = len(data)
    var result = List[Float64]()
    if n == 0:
        return result^

    var lo = data[0]
    var hi = data[0]
    for i in range(1, n):
        if data[i] < lo:
            lo = data[i]
        if data[i] > hi:
            hi = data[i]

    var rng = hi - lo
    for i in range(n):
        if rng == 0.0:
            result.append(0.0)
        else:
            result.append((data[i] - lo) / rng)
    return result^


# ── Z-score normalisation ────────────────────────────────────────────────────


def normalize_zscore(data: List[Float64]) -> List[Float64]:
    """Standard score: (x - mean) / std.

    If std is zero, returns list of zeros.
    """
    var n = len(data)
    var result = List[Float64]()
    if n == 0:
        return result^

    var m = mean(data)
    var s = stdev(data)

    for i in range(n):
        if s == 0.0:
            result.append(0.0)
        else:
            result.append((data[i] - m) / s)
    return result^


# ── Robust normalisation ─────────────────────────────────────────────────────


def normalize_robust(data: List[Float64]) -> List[Float64]:
    """Median-IQR scaling: (x - median) / IQR.

    Robust to outliers. If IQR is zero, returns list of zeros.
    """
    var n = len(data)
    var result = List[Float64]()
    if n == 0:
        return result^

    var med = median(data)
    var q_range = iqr(data)

    for i in range(n):
        if q_range == 0.0:
            result.append(0.0)
        else:
            result.append((data[i] - med) / q_range)
    return result^


# ── One-hot encoding ─────────────────────────────────────────────────────────


def one_hot_encode(categories: List[Int], n_classes: Int) -> List[List[Float64]]:
    """One-hot encode integer category labels.

    Each category value maps to a row of length n_classes with a 1.0
    at the category index and 0.0 elsewhere.
    """
    var result = List[List[Float64]]()
    for i in range(len(categories)):
        var row = List[Float64]()
        for j in range(n_classes):
            if j == categories[i]:
                row.append(1.0)
            else:
                row.append(0.0)
        result.append(row^)
    return result^


# ── Polynomial features ──────────────────────────────────────────────────────


def polynomial_features(x: List[Float64], degree: Int) -> List[List[Float64]]:
    """Generate polynomial features [x, x², …, x^degree] for each input value.

    Returns a list of rows, one per data point.
    Each row has `degree` columns: [x¹, x², ..., x^degree].
    """
    var result = List[List[Float64]]()
    for i in range(len(x)):
        var row = List[Float64]()
        var val: Float64 = 1.0
        for _ in range(degree):
            val = val * x[i]
            row.append(val)
        result.append(row^)
    return result^


# ── Train/test split ─────────────────────────────────────────────────────────


def train_test_split(
    data: List[Float64],
    labels: List[Float64],
    test_ratio: Float64,
) -> SplitResult:
    """Split data and labels into train/test sets.

    Returns SplitResult(train_data, test_data, train_labels, test_labels).
    Split is deterministic (first N for train, rest for test).
    """
    var n = len(data)
    # A short or empty labels list would be read past its end below (uncatchable abort).
    if len(labels) != n:
        return SplitResult()
    var n_test = Int(Float64(n) * test_ratio)
    if n_test < 0:
        n_test = 0
    if n_test > n:
        n_test = n
    var n_train = n - n_test

    var result = SplitResult()

    for i in range(n_train):
        result.train_data.append(data[i])
        result.train_labels.append(labels[i])

    for i in range(n_train, n):
        result.test_data.append(data[i])
        result.test_labels.append(labels[i])

    return result^
