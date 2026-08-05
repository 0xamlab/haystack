"""
anomaly.mojo — Anomaly / outlier detection. Zero Python imports.

Replaces sklearn.ensemble.IsolationForest, scipy outlier detection
with pure Mojo implementations for Z-score, IQR, modified Z-score,
isolation forest scoring, and Grubbs test.

Public API:
  zscore_detect           — Z-score anomaly detection
  iqr_detect              — IQR-based outlier detection
  modified_zscore_detect  — Modified Z-score using MAD
  percentile              — Percentile via linear interpolation
  median                  — Median value
  mad                     — Median Absolute Deviation
  isolation_score         — Simplified 1D isolation forest score
  grubbs_test_statistic   — Grubbs test statistic G
  count_anomalies         — Count True flags
"""
from std.math import sqrt, abs as fabs, log
from std.random import random_float64


# ── Sorting helper ────────────────────────────────────────────────────────────


fn _sort_copy(data: List[Float64]) -> List[Float64]:
    """Return a sorted copy (insertion sort)."""
    var out = data.copy()
    var n = len(out)
    for i in range(1, n):
        var k = out[i]
        var j = i - 1
        while j >= 0 and out[j] > k:
            out[j + 1] = out[j]
            j -= 1
        out[j + 1] = k
    return out^


# ── percentile ────────────────────────────────────────────────────────────────


fn percentile(data: List[Float64], p: Float64) -> Float64:
    """Percentile (0-100) using linear interpolation.

    Sorts the data, then interpolates between the two nearest ranks.
    """
    var n = len(data)
    if n == 0:
        return 0.0
    if n == 1:
        return data[0]
    var sorted = _sort_copy(data)
    var idx = (p / 100.0) * Float64(n - 1)
    var lo = Int(idx)
    var hi = lo + 1
    if hi >= n:
        return sorted[n - 1]
    var frac = idx - Float64(lo)
    return sorted[lo] * (1.0 - frac) + sorted[hi] * frac


# ── median ────────────────────────────────────────────────────────────────────


fn median(data: List[Float64]) -> Float64:
    """Median value of a list."""
    var n = len(data)
    if n == 0:
        return 0.0
    var sorted = _sort_copy(data)
    if n % 2 == 1:
        return sorted[n // 2]
    return (sorted[n // 2 - 1] + sorted[n // 2]) / 2.0


# ── mad ───────────────────────────────────────────────────────────────────────


fn mad(data: List[Float64]) -> Float64:
    """Median Absolute Deviation = median(|x_i - median(x)|)."""
    var n = len(data)
    if n == 0:
        return 0.0
    var med = median(data)
    var deviations = List[Float64]()
    for i in range(n):
        deviations.append(fabs(data[i] - med))
    return median(deviations)


# ── zscore_detect ─────────────────────────────────────────────────────────────


fn zscore_detect(data: List[Float64], threshold: Float64 = 3.0) -> List[Bool]:
    """Z-score anomaly detection. Returns True where |z| > threshold."""
    var n = len(data)
    var flags = List[Bool]()
    if n < 2:
        for _ in range(n):
            flags.append(False)
        return flags^

    # Compute mean
    var mean: Float64 = 0.0
    for i in range(n):
        mean += data[i]
    mean /= Float64(n)

    # Compute std
    var var_sum: Float64 = 0.0
    for i in range(n):
        var d = data[i] - mean
        var_sum += d * d
    var std = sqrt(var_sum / Float64(n))

    if std < 1e-15:
        for _ in range(n):
            flags.append(False)
        return flags^

    for i in range(n):
        var z = fabs((data[i] - mean) / std)
        flags.append(z > threshold)
    return flags^


# ── iqr_detect ────────────────────────────────────────────────────────────────


fn iqr_detect(data: List[Float64], factor: Float64 = 1.5) -> List[Bool]:
    """IQR-based outlier detection.

    Outlier if value < Q1 - factor*IQR or value > Q3 + factor*IQR.
    """
    var n = len(data)
    var flags = List[Bool]()
    if n < 4:
        for _ in range(n):
            flags.append(False)
        return flags^

    var q1 = percentile(data, 25.0)
    var q3 = percentile(data, 75.0)
    var iqr_val = q3 - q1
    var lower = q1 - factor * iqr_val
    var upper = q3 + factor * iqr_val

    for i in range(n):
        flags.append(data[i] < lower or data[i] > upper)
    return flags^


# ── modified_zscore_detect ────────────────────────────────────────────────────


fn modified_zscore_detect(
    data: List[Float64], threshold: Float64 = 3.5
) -> List[Bool]:
    """Modified Z-score using median and MAD.

    Modified Z = 0.6745 * (x_i - median) / MAD.
    Returns True where |modified Z| > threshold.
    """
    var n = len(data)
    var flags = List[Bool]()
    if n < 2:
        for _ in range(n):
            flags.append(False)
        return flags^

    var med = median(data)
    var mad_val = mad(data)

    if mad_val < 1e-15:
        for _ in range(n):
            flags.append(False)
        return flags^

    for i in range(n):
        var mz = fabs(0.6745 * (data[i] - med) / mad_val)
        flags.append(mz > threshold)
    return flags^


# ── isolation_score ───────────────────────────────────────────────────────────


fn _avg_path_length(n: Float64) -> Float64:
    """Average path length of unsuccessful search in BST of size n."""
    if n <= 1.0:
        return 0.0
    if n <= 2.0:
        return 1.0
    # c(n) = 2*H(n-1) - 2*(n-1)/n, H approximated by ln
    var h = log(n - 1.0) + 0.5772156649  # Euler-Mascheroni
    return 2.0 * h - 2.0 * (n - 1.0) / n


fn isolation_score(
    data: List[Float64],
    point: Float64,
    n_trees: Int = 100,
    sample_size: Int = 32,
) -> Float64:
    """Simplified 1D isolation forest score.

    Score ∈ [0,1], higher = more anomalous.
    Uses random splits to estimate average path length for the point.
    """
    var n = len(data)
    if n == 0:
        return 0.5
    # sample_size <= 0 builds an empty subsample and aborts on sample[0].
    if sample_size <= 0:
        return 0.5
    var actual_sample = sample_size
    if actual_sample > n:
        actual_sample = n
    var max_depth = 10
    if actual_sample > 2:
        # ceil(log2(sample_size))
        var d: Int = 0
        var v = actual_sample
        while v > 1:
            v = v // 2
            d += 1
        max_depth = d + 1

    var total_path: Float64 = 0.0

    for t in range(n_trees):
        # Build a random subsample
        var sample = List[Float64]()
        for s in range(actual_sample):
            var idx = Int(random_float64() * Float64(n)) % n
            sample.append(data[idx])

        # Find min/max of sample
        var lo = sample[0]
        var hi = sample[0]
        for s in range(1, len(sample)):
            if sample[s] < lo:
                lo = sample[s]
            if sample[s] > hi:
                hi = sample[s]

        # Simulate random splits to isolate the point
        var depth: Int = 0
        var cur_lo = lo
        var cur_hi = hi
        var cur_size = actual_sample
        while depth < max_depth and cur_size > 1:
            if cur_hi - cur_lo < 1e-15:
                break
            var split = cur_lo + random_float64() * (cur_hi - cur_lo)
            # Count how many go left vs right
            var n_left: Int = 0
            for s in range(len(sample)):
                if sample[s] < split:
                    n_left += 1
            var n_right = cur_size - n_left
            if point < split:
                cur_hi = split
                cur_size = n_left
            else:
                cur_lo = split
                cur_size = n_right
            depth += 1

        # Add adjustment for remaining items
        var path = Float64(depth) + _avg_path_length(Float64(cur_size))
        total_path += path

    var avg_path = total_path / Float64(n_trees)
    var c_n = _avg_path_length(Float64(actual_sample))
    if c_n < 1e-15:
        return 0.5

    # score = 2^(-avg_path / c(n))
    var exponent = -avg_path / c_n
    # 2^x = e^(x * ln2)
    var ln2: Float64 = 0.6931471805599453
    var score = exp_approx(exponent * ln2)
    return score


fn exp_approx(x: Float64) -> Float64:
    """Fast exp approximation via Taylor series."""
    # Clamp to avoid overflow
    var clamped = x
    if clamped > 20.0:
        clamped = 20.0
    if clamped < -20.0:
        clamped = -20.0
    var result: Float64 = 1.0
    var term: Float64 = 1.0
    for i in range(1, 30):
        term *= clamped / Float64(i)
        result += term
    return result


# ── grubbs_test_statistic ─────────────────────────────────────────────────────


fn grubbs_test_statistic(data: List[Float64]) -> Float64:
    """Grubbs test statistic G = max|x_i - mean| / std."""
    var n = len(data)
    if n < 3:
        return 0.0

    var mean: Float64 = 0.0
    for i in range(n):
        mean += data[i]
    mean /= Float64(n)

    var var_sum: Float64 = 0.0
    for i in range(n):
        var d = data[i] - mean
        var_sum += d * d
    var std = sqrt(var_sum / Float64(n))

    if std < 1e-15:
        return 0.0

    var max_dev: Float64 = 0.0
    for i in range(n):
        var dev = fabs(data[i] - mean)
        if dev > max_dev:
            max_dev = dev
    return max_dev / std


# ── count_anomalies ───────────────────────────────────────────────────────────


fn count_anomalies(flags: List[Bool]) -> Int:
    """Count True values in a flag list."""
    var count: Int = 0
    for i in range(len(flags)):
        if flags[i]:
            count += 1
    return count
