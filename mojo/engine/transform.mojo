"""
transform.mojo — Data transformation utilities. Zero Python imports.

Replaces sklearn.preprocessing transforms with pure Mojo implementations
of log, Box-Cox, standardize, min-max scaling, robust scaling, quantile,
power, clamp, rank, abs, and reciprocal transforms.

Public API:
  log_transform         — natural log of each value
  log1p_transform       — log(1+x) for each value
  box_cox               — Box-Cox transform
  standardize           — Z-score normalization
  min_max_scale         — scale to [new_min, new_max]
  robust_scale          — (x - median) / IQR
  quantile_transform    — map to percentile rank [0,1]
  power_transform       — x^power
  clamp_values          — clamp to [lo, hi]
  rank_transform        — replace with 1-based rank (average ties)
  abs_transform         — absolute value
  reciprocal_transform  — 1/x
"""

from std.math import abs as fabs, log, sqrt


# ── log_transform ────────────────────────────────────────────────────────────


fn log_transform(data: List[Float64]) raises -> List[Float64]:
    """Natural log of each value. Raises on non-positive values."""
    var result = List[Float64]()
    for i in range(len(data)):
        if data[i] <= 0.0:
            raise Error("log_transform: non-positive value at index " + String(i))
        result.append(log(data[i]))
    return result^


# ── log1p_transform ──────────────────────────────────────────────────────────


fn log1p_transform(data: List[Float64]) raises -> List[Float64]:
    """log(1 + x) for each value. Raises if 1+x <= 0."""
    var result = List[Float64]()
    for i in range(len(data)):
        var v = 1.0 + data[i]
        if v <= 0.0:
            raise Error("log1p_transform: 1+x non-positive at index " + String(i))
        result.append(log(v))
    return result^


# ── box_cox ──────────────────────────────────────────────────────────────────


fn box_cox(data: List[Float64], lmbda: Float64) raises -> List[Float64]:
    """Box-Cox transform: (x^λ - 1)/λ for λ≠0, log(x) for λ=0.

    All values must be positive.
    """
    var result = List[Float64]()
    for i in range(len(data)):
        if data[i] <= 0.0:
            raise Error("box_cox: non-positive value at index " + String(i))
        if fabs(lmbda) < 1e-12:
            result.append(log(data[i]))
        else:
            # x^lambda via exp(lambda * log(x))
            var powered = _exp(lmbda * log(data[i]))
            result.append((powered - 1.0) / lmbda)
    return result^


fn _exp(x: Float64) -> Float64:
    """Compute e^x using std.math."""
    # Use the identity: e^x = 2^(x / ln2) but simpler: Taylor or use log inverse
    # Actually we can use pow-like approach. Let's use a direct computation.
    # For Box-Cox we need exp. We'll compute via repeated squaring of e.
    # Simpler: import from std.math
    from std.math import exp
    return exp(x)


# ── standardize ──────────────────────────────────────────────────────────────


fn standardize(data: List[Float64]) raises -> List[Float64]:
    """Z-score normalization: (x - mean) / std.

    Raises if data is empty or std is zero.
    """
    var n = len(data)
    if n == 0:
        raise Error("standardize: empty data")
    var s = 0.0
    for i in range(n):
        s += data[i]
    var mean = s / Float64(n)
    var ss = 0.0
    for i in range(n):
        var d = data[i] - mean
        ss += d * d
    var std = sqrt(ss / Float64(n))
    if std < 1e-15:
        raise Error("standardize: zero standard deviation")
    var result = List[Float64]()
    for i in range(n):
        result.append((data[i] - mean) / std)
    return result^


# ── min_max_scale ────────────────────────────────────────────────────────────


fn min_max_scale(
    data: List[Float64], new_min: Float64 = 0.0, new_max: Float64 = 1.0
) raises -> List[Float64]:
    """Scale data to [new_min, new_max]. Raises if data is empty or constant."""
    var n = len(data)
    if n == 0:
        raise Error("min_max_scale: empty data")
    var lo = data[0]
    var hi = data[0]
    for i in range(1, n):
        if data[i] < lo:
            lo = data[i]
        if data[i] > hi:
            hi = data[i]
    var rng = hi - lo
    if rng < 1e-15:
        raise Error("min_max_scale: constant data")
    var result = List[Float64]()
    for i in range(n):
        var scaled = (data[i] - lo) / rng
        result.append(new_min + scaled * (new_max - new_min))
    return result^


# ── robust_scale ─────────────────────────────────────────────────────────────


fn _sorted_copy(data: List[Float64]) -> List[Float64]:
    """Return a sorted copy of the data (insertion sort for simplicity)."""
    var s = List[Float64]()
    for i in range(len(data)):
        s.append(data[i])
    var n = len(s)
    for i in range(1, n):
        var key = s[i]
        var j = i - 1
        while j >= 0 and s[j] > key:
            s[j + 1] = s[j]
            j -= 1
        s[j + 1] = key
    return s^


fn _percentile(sorted_data: List[Float64], p: Float64) -> Float64:
    """Percentile from sorted data using linear interpolation."""
    var n = len(sorted_data)
    if n == 1:
        return sorted_data[0]
    var idx = p * Float64(n - 1)
    var lo = Int(idx)
    var hi = lo + 1
    if hi >= n:
        return sorted_data[n - 1]
    var frac = idx - Float64(lo)
    return sorted_data[lo] * (1.0 - frac) + sorted_data[hi] * frac


fn robust_scale(data: List[Float64]) raises -> List[Float64]:
    """(x - median) / IQR. Robust to outliers.

    IQR = Q3 - Q1. Raises if data is empty or IQR is zero.
    """
    var n = len(data)
    if n == 0:
        raise Error("robust_scale: empty data")
    var s = _sorted_copy(data)
    var median = _percentile(s, 0.5)
    var q1 = _percentile(s, 0.25)
    var q3 = _percentile(s, 0.75)
    var iqr = q3 - q1
    if iqr < 1e-15:
        raise Error("robust_scale: zero IQR")
    var result = List[Float64]()
    for i in range(n):
        result.append((data[i] - median) / iqr)
    return result^


# ── quantile_transform ───────────────────────────────────────────────────────


fn quantile_transform(data: List[Float64]) raises -> List[Float64]:
    """Map each value to its percentile rank in [0, 1].

    Ties get the average percentile. Raises if data is empty.
    """
    var n = len(data)
    if n == 0:
        raise Error("quantile_transform: empty data")
    if n == 1:
        var result = List[Float64]()
        result.append(0.5)
        return result^

    # For each value, count how many are strictly less and how many are equal
    var result = List[Float64]()
    for i in range(n):
        var less = 0
        var equal = 0
        for j in range(n):
            if data[j] < data[i]:
                less += 1
            elif data[j] == data[i]:
                equal += 1
        # Average rank percentile
        var avg_rank = Float64(less) + Float64(equal - 1) / 2.0
        result.append(avg_rank / Float64(n - 1))
    return result^


# ── power_transform ──────────────────────────────────────────────────────────


fn power_transform(data: List[Float64], power: Float64) -> List[Float64]:
    """x^power for each value. Uses exp(power * log(|x|)) with sign preservation."""
    from std.math import exp
    var result = List[Float64]()
    for i in range(len(data)):
        var x = data[i]
        if x == 0.0:
            result.append(0.0)
        elif x > 0.0:
            result.append(exp(power * log(x)))
        else:
            # Negative: preserve sign for integer-like powers
            result.append(-exp(power * log(-x)))
    return result^


# ── clamp_values ─────────────────────────────────────────────────────────────


fn clamp_values(data: List[Float64], lo: Float64, hi: Float64) -> List[Float64]:
    """Clamp each value to [lo, hi]."""
    var result = List[Float64]()
    for i in range(len(data)):
        var v = data[i]
        if v < lo:
            v = lo
        if v > hi:
            v = hi
        result.append(v)
    return result^


# ── rank_transform ───────────────────────────────────────────────────────────


fn rank_transform(data: List[Float64]) -> List[Float64]:
    """Replace each value with its rank (1-based, average ties)."""
    var n = len(data)
    var result = List[Float64]()
    for i in range(n):
        var rank_sum = 0.0
        var count = 0
        for j in range(n):
            if data[j] < data[i]:
                rank_sum += 1.0
            if data[j] == data[i]:
                count += 1
        # Average rank: (number less than) + (count of equals + 1) / 2
        var avg = rank_sum + Float64(count + 1) / 2.0
        result.append(avg)
    return result^


# ── abs_transform ────────────────────────────────────────────────────────────


fn abs_transform(data: List[Float64]) -> List[Float64]:
    """Absolute value of each element."""
    var result = List[Float64]()
    for i in range(len(data)):
        result.append(fabs(data[i]))
    return result^


# ── reciprocal_transform ────────────────────────────────────────────────────


fn reciprocal_transform(data: List[Float64]) raises -> List[Float64]:
    """1/x for each value. Raises on zero."""
    var result = List[Float64]()
    for i in range(len(data)):
        if fabs(data[i]) < 1e-15:
            raise Error("reciprocal_transform: zero value at index " + String(i))
        result.append(1.0 / data[i])
    return result^
