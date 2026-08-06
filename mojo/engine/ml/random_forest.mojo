"""
random_forest.mojo — Random Forest regressor. Zero Python imports.

Replaces sklearn.ensemble.RandomForestRegressor with pure Mojo
implementations using bootstrap aggregation of simple decision stumps.

Public API:
  bootstrap_indices          — Random sample with replacement
  feature_subsample          — Random subset of feature indices
  tree_predict_simple        — Simple stump predictor
  random_forest_predict      — Ensemble prediction (average of stumps)
  random_forest_predict_batch — Batch prediction
  oob_score                  — Out-of-bag R² estimate
  feature_importance_rf      — Permutation-based feature importance
  bagging_variance           — Variance across tree predictions
"""
from std.math import sqrt, abs as fabs, isnan, isinf
from std.random import random_float64


# Ceilings on wire-supplied counts: bound per-call iteration/allocation.
comptime MAX_RF_TREES: Int = 10000
comptime MAX_RF_SAMPLE: Int = 1000000
comptime MAX_RF_FEATURES: Int = 1000000


# ── Bootstrap / Subsample ────────────────────────────────────────────────────


def bootstrap_indices(n: Int, sample_size: Int) -> List[Int]:
    """Random sample of sample_size indices in [0, n) with replacement."""
    # sample_size drives the allocation; clamp the wire-supplied count.
    var count = sample_size
    if count > MAX_RF_SAMPLE:
        count = MAX_RF_SAMPLE
    var result = List[Int]()
    for _ in range(count):
        var idx = Int(random_float64() * Float64(n))
        if idx >= n:
            idx = n - 1
        if idx < 0:
            idx = 0
        result.append(idx)
    return result^


def feature_subsample(n_features: Int, max_features: Int) -> List[Int]:
    """Random subset of feature indices (no duplicates).
    Uses Fisher-Yates partial shuffle."""
    # n_features drives the allocation; clamp the wire-supplied count.
    var nf = n_features
    if nf > MAX_RF_FEATURES:
        nf = MAX_RF_FEATURES
    var m = max_features
    if m > nf:
        m = nf
    # Build array [0, 1, ..., nf-1]
    var arr = List[Int]()
    for i in range(nf):
        arr.append(i)
    # Partial Fisher-Yates
    for i in range(m):
        var remaining = nf - i
        var j = i + Int(random_float64() * Float64(remaining))
        if j >= nf:
            j = nf - 1
        # Swap arr[i] and arr[j]
        var tmp = arr[i]
        arr[i] = arr[j]
        arr[j] = tmp
    var result = List[Int]()
    for i in range(m):
        result.append(arr[i])
    return result^


# ── Simple Stump Predictor ───────────────────────────────────────────────────


def _mean(vals: List[Float64]) -> Float64:
    """Mean of a list."""
    if len(vals) == 0:
        return 0.0
    var s: Float64 = 0.0
    for i in range(len(vals)):
        s += vals[i]
    return s / Float64(len(vals))


def _variance(vals: List[Float64]) -> Float64:
    """Variance of a list."""
    if len(vals) <= 1:
        return 0.0
    var m = _mean(vals)
    var s: Float64 = 0.0
    for i in range(len(vals)):
        var d = vals[i] - m
        s += d * d
    return s / Float64(len(vals))


def _sse(vals: List[Float64]) -> Float64:
    """Sum of squared errors from mean."""
    if len(vals) == 0:
        return 0.0
    var m = _mean(vals)
    var s: Float64 = 0.0
    for i in range(len(vals)):
        var d = vals[i] - m
        s += d * d
    return s


def tree_predict_simple(
    X_train: List[List[Float64]],
    y_train: List[Float64],
    x_test: List[Float64],
    feature_subset: List[Int],
) -> Float64:
    """Simple stump predictor: find best single split on feature subset,
    return mean of the side x_test falls into."""
    var n = len(X_train)
    if n == 0:
        return 0.0
    # A short y_train/x_test or ragged X_train row would be read past its end
    # below (uncatchable abort); a non-finite label would poison every split
    # score; an out-of-range feature index is refused outright.
    var n_feat = len(X_train[0])
    if len(y_train) < n or len(x_test) < n_feat:
        return 0.0
    for i in range(n):
        if len(X_train[i]) < n_feat:
            return 0.0
        if isnan(y_train[i]) or isinf(y_train[i]):
            return 0.0
    for fi in range(len(feature_subset)):
        var f = feature_subset[fi]
        if f < 0 or f >= n_feat:
            return 0.0
    var best_feat = 0
    var best_thresh: Float64 = 0.0
    var best_reduction: Float64 = -1.0
    var total_sse = _sse(y_train)

    for fi in range(len(feature_subset)):
        var f = feature_subset[fi]
        # Try a few thresholds: min, max, and quartiles
        var fmin: Float64 = X_train[0][f]
        var fmax: Float64 = X_train[0][f]
        for i in range(1, n):
            if X_train[i][f] < fmin:
                fmin = X_train[i][f]
            if X_train[i][f] > fmax:
                fmax = X_train[i][f]
        if fmax - fmin < 1e-12:
            continue
        # Try 5 candidate thresholds
        for t in range(1, 6):
            var thresh = fmin + Float64(t) / 6.0 * (fmax - fmin)
            var left = List[Float64]()
            var right = List[Float64]()
            for i in range(n):
                if X_train[i][f] <= thresh:
                    left.append(y_train[i])
                else:
                    right.append(y_train[i])
            if len(left) == 0 or len(right) == 0:
                continue
            var reduction = total_sse - _sse(left) - _sse(right)
            if reduction > best_reduction:
                best_reduction = reduction
                best_feat = f
                best_thresh = thresh

    # Predict: which side does x_test fall?
    if best_reduction < 0.0:
        return _mean(y_train)
    var left_vals = List[Float64]()
    var right_vals = List[Float64]()
    for i in range(n):
        if X_train[i][best_feat] <= best_thresh:
            left_vals.append(y_train[i])
        else:
            right_vals.append(y_train[i])
    if x_test[best_feat] <= best_thresh:
        return _mean(left_vals)
    return _mean(right_vals)


# ── Random Forest Predict ────────────────────────────────────────────────────


def random_forest_predict(
    X_train: List[List[Float64]],
    y_train: List[Float64],
    x_test: List[Float64],
    n_trees: Int,
    max_features: Int,
) -> Float64:
    """Ensemble prediction: average of n_trees bootstrap stumps."""
    var n = len(X_train)
    if n == 0:
        return 0.0
    # A short y_train would be read past its end below (uncatchable abort);
    # n_trees drives both the iteration count and the final divisor.
    if len(y_train) < n or n_trees <= 0:
        return 0.0
    var trees = n_trees
    if trees > MAX_RF_TREES:
        trees = MAX_RF_TREES
    var n_feat = len(X_train[0])
    var total: Float64 = 0.0
    for _t in range(trees):
        var idxs = bootstrap_indices(n, n)
        var X_b = List[List[Float64]]()
        var y_b = List[Float64]()
        for i in range(len(idxs)):
            X_b.append(X_train[idxs[i]].copy())
            y_b.append(y_train[idxs[i]])
        var feats = feature_subsample(n_feat, max_features)
        total += tree_predict_simple(X_b, y_b, x_test, feats)
    return total / Float64(trees)


def random_forest_predict_batch(
    X_train: List[List[Float64]],
    y_train: List[Float64],
    X_test: List[List[Float64]],
    n_trees: Int,
    max_features: Int,
) -> List[Float64]:
    """Batch prediction for multiple test points."""
    var result = List[Float64]()
    for i in range(len(X_test)):
        result.append(
            random_forest_predict(X_train, y_train, X_test[i], n_trees, max_features)
        )
    return result^


# ── Out-of-Bag Score ─────────────────────────────────────────────────────────


def oob_score(
    X: List[List[Float64]],
    y: List[Float64],
    n_trees: Int,
    max_features: Int,
) -> Float64:
    """Out-of-bag R² score estimate."""
    var n = len(X)
    if n == 0:
        return 0.0
    # A short y would be read past its end below (uncatchable abort).
    if len(y) < n:
        return 0.0
    # n_trees drives the iteration count; clamp the wire-supplied count.
    var trees = n_trees
    if trees > MAX_RF_TREES:
        trees = MAX_RF_TREES
    var n_feat = len(X[0])
    var oob_sum = List[Float64]()
    var oob_count = List[Int]()
    for _i in range(n):
        oob_sum.append(0.0)
        oob_count.append(0)

    for _t in range(trees):
        var idxs = bootstrap_indices(n, n)
        # Mark in-bag
        var in_bag = List[Bool]()
        for _i in range(n):
            in_bag.append(False)
        for i in range(len(idxs)):
            in_bag[idxs[i]] = True
        # Build bootstrap sample
        var X_b = List[List[Float64]]()
        var y_b = List[Float64]()
        for i in range(len(idxs)):
            X_b.append(X[idxs[i]].copy())
            y_b.append(y[idxs[i]])
        var feats = feature_subsample(n_feat, max_features)
        # Predict OOB samples
        for i in range(n):
            if not in_bag[i]:
                var pred = tree_predict_simple(X_b, y_b, X[i], feats)
                oob_sum[i] = oob_sum[i] + pred
                oob_count[i] = oob_count[i] + 1

    # Compute R²
    var y_mean = _mean(y)
    var ss_res: Float64 = 0.0
    var ss_tot: Float64 = 0.0
    var valid = 0
    for i in range(n):
        if oob_count[i] > 0:
            var pred = oob_sum[i] / Float64(oob_count[i])
            ss_res += (y[i] - pred) * (y[i] - pred)
            ss_tot += (y[i] - y_mean) * (y[i] - y_mean)
            valid += 1
    if ss_tot < 1e-15 or valid == 0:
        return 0.0
    return 1.0 - ss_res / ss_tot


# ── Feature Importance ───────────────────────────────────────────────────────


def feature_importance_rf(
    X: List[List[Float64]],
    y: List[Float64],
    n_trees: Int,
    max_features: Int,
) -> List[Float64]:
    """Permutation-based feature importance.
    For each feature, shuffle it and measure prediction degradation."""
    var n = len(X)
    if n == 0:
        return List[Float64]()
    var n_feat = len(X[0])
    # A short y or ragged X row would be read past its end below
    # (uncatchable abort).
    if len(y) < n:
        return List[Float64]()
    for i in range(n):
        if len(X[i]) < n_feat:
            return List[Float64]()
    # Baseline MSE
    var preds = random_forest_predict_batch(X, y, X, n_trees, max_features)
    var base_mse: Float64 = 0.0
    for i in range(n):
        var d = y[i] - preds[i]
        base_mse += d * d
    base_mse = base_mse / Float64(n)

    var importance = List[Float64]()
    for f in range(n_feat):
        # Create permuted copy (shift by 1)
        var X_perm = List[List[Float64]]()
        for i in range(n):
            var row = List[Float64]()
            for j in range(n_feat):
                if j == f:
                    row.append(X[(i + 1) % n][j])
                else:
                    row.append(X[i][j])
            X_perm.append(row^)
        var preds_perm = random_forest_predict_batch(X, y, X_perm, n_trees, max_features)
        var perm_mse: Float64 = 0.0
        for i in range(n):
            var d = y[i] - preds_perm[i]
            perm_mse += d * d
        perm_mse = perm_mse / Float64(n)
        importance.append(perm_mse - base_mse)
    return importance^


# ── Bagging Variance ─────────────────────────────────────────────────────────


def bagging_variance(predictions: List[List[Float64]]) -> List[Float64]:
    """Variance across tree predictions for each sample.
    predictions[t][i] = prediction of tree t for sample i."""
    if len(predictions) == 0:
        return List[Float64]()
    var n_samples = len(predictions[0])
    var n_trees = len(predictions)
    var result = List[Float64]()
    for i in range(n_samples):
        var vals = List[Float64]()
        for t in range(n_trees):
            if i < len(predictions[t]):
                vals.append(predictions[t][i])
        result.append(_variance(vals))
    return result^
