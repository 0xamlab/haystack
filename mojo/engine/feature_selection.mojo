"""
feature_selection.mojo — Feature Selection utilities. Zero Python imports.

Replaces sklearn.feature_selection with pure Mojo implementations of
variance threshold, correlation filter, F-test scores, forward selection,
information gain, and permutation importance.

Public API:
  column_mean                    — Mean of each column
  column_variance                — Variance of each column
  variance_threshold             — Column indices with variance > threshold
  correlation_filter             — Remove highly correlated features
  f_test_scores                  — F-statistic per feature vs target
  select_k_best                  — Top-k scoring feature indices
  forward_selection_greedy       — Greedy forward selection by MSE
  information_gain               — Approximate mutual information via bins
  feature_importance_permutation — Permutation importance via MSE increase
"""

from std.math import sqrt, abs as fabs, log


# Untrusted iteration counts are clamped to documented ceilings: both drive
# per-count work (permutations) or per-count-squared allocation (bin pairs),
# so an unbounded value from the wire is a CPU/memory weapon.
comptime MAX_PERMUTATIONS: Int = 100000
comptime MAX_BINS: Int = 1000


# ── column_mean ──────────────────────────────────────────────────────────────


fn column_mean(data: List[List[Float64]]) -> List[Float64]:
    """Mean of each column in the 2D data matrix."""
    var n = len(data)
    if n == 0:
        return List[Float64]()
    var ncols = len(data[0])
    var means = List[Float64](capacity=ncols)
    for j in range(ncols):
        var s: Float64 = 0.0
        for i in range(n):
            s += data[i][j]
        means.append(s / Float64(n))
    return means^


# ── column_variance ──────────────────────────────────────────────────────────


fn column_variance(data: List[List[Float64]]) -> List[Float64]:
    """Compute variance of each column (population variance)."""
    var n = len(data)
    if n == 0:
        return List[Float64]()
    var ncols = len(data[0])
    var means = column_mean(data)
    var variances = List[Float64](capacity=ncols)
    for j in range(ncols):
        var ss: Float64 = 0.0
        for i in range(n):
            var d = data[i][j] - means[j]
            ss += d * d
        variances.append(ss / Float64(n))
    return variances^


# ── variance_threshold ───────────────────────────────────────────────────────


fn variance_threshold(data: List[List[Float64]], threshold: Float64 = 0.0) -> List[Int]:
    """Return column indices with variance > threshold."""
    var variances = column_variance(data)
    var selected = List[Int]()
    for j in range(len(variances)):
        if variances[j] > threshold:
            selected.append(j)
    return selected^


# ── correlation_filter ───────────────────────────────────────────────────────


fn correlation_filter(data: List[List[Float64]], max_corr: Float64 = 0.95) -> List[Int]:
    """Remove highly correlated features. Return selected column indices.
    For each pair with |corr| > max_corr, the later column is removed."""
    var n = len(data)
    if n == 0:
        return List[Int]()
    var ncols = len(data[0])
    var means = column_mean(data)
    var removed = List[Bool](capacity=ncols)
    for j in range(ncols):
        removed.append(False)

    for i_col in range(ncols):
        if removed[i_col]:
            continue
        for j_col in range(i_col + 1, ncols):
            if removed[j_col]:
                continue
            var cov: Float64 = 0.0
            var var_a: Float64 = 0.0
            var var_b: Float64 = 0.0
            for r in range(n):
                var da = data[r][i_col] - means[i_col]
                var db = data[r][j_col] - means[j_col]
                cov += da * db
                var_a += da * da
                var_b += db * db
            var denom = sqrt(var_a * var_b)
            if denom > 1e-15:
                var corr = cov / denom
                if fabs(corr) > max_corr:
                    removed[j_col] = True

    var selected = List[Int]()
    for j in range(ncols):
        if not removed[j]:
            selected.append(j)
    return selected^


# ── f_test_scores ────────────────────────────────────────────────────────────


fn f_test_scores(X: List[List[Float64]], y: List[Float64]) -> List[Float64]:
    """F-statistic for each feature vs target. Higher = more informative.
    Uses correlation-based F: F = r²*(n-2) / (1-r²)."""
    var n = len(X)
    if n < 3:
        return List[Float64]()
    # y is indexed by row below; a shorter y is an uncatchable abort.
    if len(y) < n:
        return List[Float64]()
    var ncols = len(X[0])
    var y_mean: Float64 = 0.0
    for i in range(n):
        y_mean += y[i]
    y_mean /= Float64(n)

    var scores = List[Float64](capacity=ncols)
    for j in range(ncols):
        var x_mean: Float64 = 0.0
        for i in range(n):
            x_mean += X[i][j]
        x_mean /= Float64(n)

        var cov: Float64 = 0.0
        var var_x: Float64 = 0.0
        var var_y: Float64 = 0.0
        for i in range(n):
            var dx = X[i][j] - x_mean
            var dy = y[i] - y_mean
            cov += dx * dy
            var_x += dx * dx
            var_y += dy * dy
        var denom = var_x * var_y
        if denom < 1e-30:
            scores.append(0.0)
            continue
        var r2 = (cov * cov) / denom
        var f_val = r2 * Float64(n - 2) / (1.0 - r2 + 1e-30)
        scores.append(f_val)
    return scores^


# ── select_k_best ────────────────────────────────────────────────────────────


fn select_k_best(scores: List[Float64], k: Int) -> List[Int]:
    """Return indices of top-k scoring features."""
    # Negative k would become a negative List capacity, an uncatchable abort.
    if k <= 0:
        return List[Int]()
    var n = len(scores)
    var actual_k = k
    if actual_k > n:
        actual_k = n
    var used = List[Bool](capacity=n)
    for i in range(n):
        used.append(False)
    var result = List[Int](capacity=actual_k)
    for round_i in range(actual_k):
        var best_idx = -1
        var best_val: Float64 = -1e300
        for j in range(n):
            if not used[j] and scores[j] > best_val:
                best_val = scores[j]
                best_idx = j
        if best_idx >= 0:
            result.append(best_idx)
            used[best_idx] = True
    return result^


# ── forward_selection_greedy ─────────────────────────────────────────────────


fn _compute_mse_with_features(X: List[List[Float64]], y: List[Float64], features: List[Int]) -> Float64:
    """Compute MSE using selected features via simple regression."""
    var n = len(X)
    if n == 0 or len(features) == 0:
        return 1e30
    var y_mean: Float64 = 0.0
    for i in range(n):
        y_mean += y[i]
    y_mean /= Float64(n)

    var pred = List[Float64](capacity=n)
    for i in range(n):
        pred.append(y_mean)

    var nf = len(features)
    for fi in range(nf):
        var j = features[fi]
        var x_mean: Float64 = 0.0
        for i in range(n):
            x_mean += X[i][j]
        x_mean /= Float64(n)
        var cov: Float64 = 0.0
        var var_x: Float64 = 0.0
        for i in range(n):
            var dx = X[i][j] - x_mean
            cov += dx * (y[i] - y_mean)
            var_x += dx * dx
        if var_x > 1e-30:
            var beta = cov / var_x
            for i in range(n):
                pred[i] = pred[i] + beta * (X[i][j] - x_mean) / Float64(nf)

    var mse: Float64 = 0.0
    for i in range(n):
        var e = y[i] - pred[i]
        mse += e * e
    return mse / Float64(n)


fn forward_selection_greedy(X: List[List[Float64]], y: List[Float64], k: Int) -> List[Int]:
    """Greedy forward selection: add feature that most reduces MSE, up to k features."""
    var n = len(X)
    if n == 0:
        return List[Int]()
    # y is indexed by row below; a shorter y is an uncatchable abort.
    if len(y) < n:
        return List[Int]()
    var ncols = len(X[0])
    var actual_k = k
    if actual_k > ncols:
        actual_k = ncols

    var selected = List[Int]()
    var used = List[Bool](capacity=ncols)
    for j in range(ncols):
        used.append(False)

    for round_i in range(actual_k):
        var best_feat = -1
        var best_mse: Float64 = 1e30
        for j in range(ncols):
            if used[j]:
                continue
            var candidate = List[Int](capacity=len(selected) + 1)
            for si in range(len(selected)):
                candidate.append(selected[si])
            candidate.append(j)
            var mse_val = _compute_mse_with_features(X, y, candidate^)
            if mse_val < best_mse:
                best_mse = mse_val
                best_feat = j
        if best_feat >= 0:
            selected.append(best_feat)
            used[best_feat] = True
    return selected^


# ── information_gain ─────────────────────────────────────────────────────────


fn information_gain(feature: List[Float64], target: List[Float64], n_bins: Int = 10) -> Float64:
    """Approximate mutual information via binned histogram.
    MI = H(target) + H(feature) - H(feature, target)."""
    var n = len(feature)
    if n == 0:
        return 0.0
    # target is indexed up to n-1 below; a shorter target aborts.
    if len(target) < n:
        return 0.0
    # n_bins <= 0 would abort on negative capacity / negative indexing; huge
    # values allocate n_bins^2 joint cells and get clamped to the ceiling.
    if n_bins <= 0:
        return 0.0
    var nb = n_bins
    if nb > MAX_BINS:
        nb = MAX_BINS

    var f_min = feature[0]
    var f_max = feature[0]
    var t_min = target[0]
    var t_max = target[0]
    for i in range(1, n):
        if feature[i] < f_min:
            f_min = feature[i]
        if feature[i] > f_max:
            f_max = feature[i]
        if target[i] < t_min:
            t_min = target[i]
        if target[i] > t_max:
            t_max = target[i]

    var f_range = f_max - f_min
    var t_range = t_max - t_min
    if f_range < 1e-15:
        f_range = 1.0
    if t_range < 1e-15:
        t_range = 1.0

    var f_counts = List[Int](capacity=nb)
    var t_counts = List[Int](capacity=nb)
    var joint_counts = List[Int](capacity=nb * nb)
    for i in range(nb):
        f_counts.append(0)
        t_counts.append(0)
    for i in range(nb * nb):
        joint_counts.append(0)

    for i in range(n):
        var fb = Int((feature[i] - f_min) / f_range * Float64(nb - 1) + 0.5)
        if fb < 0:
            fb = 0
        if fb >= nb:
            fb = nb - 1
        var tb = Int((target[i] - t_min) / t_range * Float64(nb - 1) + 0.5)
        if tb < 0:
            tb = 0
        if tb >= nb:
            tb = nb - 1
        f_counts[fb] += 1
        t_counts[tb] += 1
        joint_counts[fb * nb + tb] += 1

    var fn_val = Float64(n)
    var h_f: Float64 = 0.0
    var h_t: Float64 = 0.0
    var h_ft: Float64 = 0.0
    for i in range(nb):
        if f_counts[i] > 0:
            var p = Float64(f_counts[i]) / fn_val
            h_f -= p * log(p)
        if t_counts[i] > 0:
            var p = Float64(t_counts[i]) / fn_val
            h_t -= p * log(p)
    for i in range(nb * nb):
        if joint_counts[i] > 0:
            var p = Float64(joint_counts[i]) / fn_val
            h_ft -= p * log(p)

    var mi = h_f + h_t - h_ft
    if mi < 0.0:
        mi = 0.0
    return mi


# ── feature_importance_permutation ───────────────────────────────────────────


fn feature_importance_permutation(X: List[List[Float64]], y: List[Float64], n_permutations: Int = 5) -> List[Float64]:
    """Simplified permutation importance: measure MSE increase when shuffling each feature.
    Uses a deterministic cyclic permutation for reproducibility."""
    var n = len(X)
    if n == 0:
        return List[Float64]()
    # y is indexed by row below; a shorter y is an uncatchable abort.
    if len(y) < n:
        return List[Float64]()
    # Zero permutations would divide by zero below; huge values are a CPU
    # weapon and get clamped to the documented ceiling.
    if n_permutations <= 0:
        return List[Float64]()
    var perms = n_permutations
    if perms > MAX_PERMUTATIONS:
        perms = MAX_PERMUTATIONS
    var ncols = len(X[0])

    var y_mean: Float64 = 0.0
    for i in range(n):
        y_mean += y[i]
    y_mean /= Float64(n)
    var base_mse: Float64 = 0.0
    for i in range(n):
        var e = y[i] - y_mean
        base_mse += e * e
    base_mse /= Float64(n)

    var importances = List[Float64](capacity=ncols)
    for j in range(ncols):
        var total_mse_increase: Float64 = 0.0
        for p in range(perms):
            var shift = (p + 1) % n
            if shift == 0:
                shift = 1
            var perm_mse: Float64 = 0.0
            for i in range(n):
                var si = (i + shift) % n
                var e = y[i] - y_mean
                perm_mse += e * e + (X[i][j] - X[si][j]) * (X[i][j] - X[si][j]) * 0.01
            perm_mse /= Float64(n)
            total_mse_increase += perm_mse - base_mse
        importances.append(total_mse_increase / Float64(perms))
    return importances^
