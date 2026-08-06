"""
dsp.mojo — Basic digital signal processing. Zero Python imports.
Replaces scipy.signal basics for the decision engine.

Public API:
  moving_average             — simple moving average
  exponential_moving_average — EMA with smoothing factor alpha
  diff                       — first differences
  cumsum                     — cumulative sum
  convolve                   — 1D convolution (full output)
  autocorrelation            — autocorrelation function up to max_lag
  detrend_linear             — remove linear trend via least-squares
  normalize_signal           — normalize signal to [-1, 1]
  zero_crossings             — count sign changes
  peak_detect                — find peaks above threshold
"""
from std.math import abs as fabs, sqrt


# ── Simple moving average ─────────────────────────────────────────────────────


def moving_average(data: List[Float64], window: Int) -> List[Float64]:
    """Simple moving average with centered output.
    Returns a list of the same length as data. For positions where the full
    window is not available, a partial average is computed.
    The window is centered: for index i, we average from i - hw to i + hw
    where hw = window // 2."""
    var n = len(data)
    var result = List[Float64]()
    if n == 0 or window <= 0:
        return result^
    var w = window
    if w > n:
        w = n

    var hw = w // 2

    for i in range(n):
        var lo = i - hw
        var hi = i + hw
        if lo < 0:
            lo = 0
        if hi >= n:
            hi = n - 1
        var s: Float64 = 0.0
        var cnt = 0
        for j in range(lo, hi + 1):
            s += data[j]
            cnt += 1
        if cnt > 0:
            result.append(s / Float64(cnt))
        else:
            result.append(0.0)
    return result^


# ── Exponential moving average ────────────────────────────────────────────────


def exponential_moving_average(data: List[Float64], alpha: Float64) -> List[Float64]:
    """Exponential moving average. alpha in (0, 1].
    EMA[0] = data[0], EMA[i] = alpha * data[i] + (1-alpha) * EMA[i-1]."""
    var n = len(data)
    var result = List[Float64]()
    if n == 0:
        return result^
    var a = alpha
    if a < 0.0:
        a = 0.0
    if a > 1.0:
        a = 1.0
    result.append(data[0])
    for i in range(1, n):
        var ema = a * data[i] + (1.0 - a) * result[i - 1]
        result.append(ema)
    return result^


# ── First differences ─────────────────────────────────────────────────────────


def diff(data: List[Float64]) -> List[Float64]:
    """First differences: result[i] = data[i+1] - data[i].
    Returns list of length max(0, n-1)."""
    var n = len(data)
    var result = List[Float64]()
    if n <= 1:
        return result^
    for i in range(n - 1):
        result.append(data[i + 1] - data[i])
    return result^


# ── Cumulative sum ────────────────────────────────────────────────────────────


def cumsum(data: List[Float64]) -> List[Float64]:
    """Cumulative sum: result[i] = sum(data[0..i])."""
    var n = len(data)
    var result = List[Float64]()
    if n == 0:
        return result^
    var s: Float64 = 0.0
    for i in range(n):
        s += data[i]
        result.append(s)
    return result^


# ── 1D Convolution ────────────────────────────────────────────────────────────


def convolve(signal_data: List[Float64], kernel: List[Float64]) -> List[Float64]:
    """1D convolution (full mode). Output length = len(signal) + len(kernel) - 1."""
    var n = len(signal_data)
    var m = len(kernel)
    var result = List[Float64]()
    if n == 0 or m == 0:
        return result^
    var out_len = n + m - 1
    for i in range(out_len):
        var s: Float64 = 0.0
        # j ranges over valid kernel indices
        var j_lo = 0
        if i >= n:
            j_lo = i - n + 1
        var j_hi = m - 1
        if i < j_hi:
            j_hi = i
        for j in range(j_lo, j_hi + 1):
            s += signal_data[i - j] * kernel[j]
        result.append(s)
    return result^


# ── Autocorrelation ───────────────────────────────────────────────────────────


def autocorrelation(data: List[Float64], max_lag: Int) -> List[Float64]:
    """Autocorrelation function for lags 0, 1, ..., max_lag.
    Normalized so that autocorrelation at lag 0 = 1.0."""
    var n = len(data)
    var result = List[Float64]()
    if n == 0:
        return result^

    # Compute mean
    var mean: Float64 = 0.0
    for i in range(n):
        mean += data[i]
    mean /= Float64(n)

    # Variance (lag 0)
    var var0: Float64 = 0.0
    for i in range(n):
        var d = data[i] - mean
        var0 += d * d

    if var0 < 1e-15:
        # Constant signal — all autocorrelations are 1.0 (or undefined)
        for lag in range(max_lag + 1):
            result.append(1.0)
        return result^

    var lags = max_lag
    if lags >= n:
        lags = n - 1

    for lag in range(lags + 1):
        var s: Float64 = 0.0
        for i in range(n - lag):
            s += (data[i] - mean) * (data[i + lag] - mean)
        result.append(s / var0)

    return result^


# ── Detrend (remove linear trend) ────────────────────────────────────────────


def detrend_linear(data: List[Float64]) -> List[Float64]:
    """Remove linear trend from data using least-squares fit.
    Result = data - (a + b*i) where a, b are fit via OLS."""
    var n = len(data)
    var result = List[Float64]()
    if n == 0:
        return result^
    if n == 1:
        result.append(0.0)
        return result^

    # Fit y = a + b*x where x = 0, 1, ..., n-1
    var sx: Float64 = 0.0
    var sy: Float64 = 0.0
    var sxx: Float64 = 0.0
    var sxy: Float64 = 0.0
    var nf = Float64(n)

    for i in range(n):
        var xi = Float64(i)
        sx += xi
        sy += data[i]
        sxx += xi * xi
        sxy += xi * data[i]

    var denom = nf * sxx - sx * sx
    var b: Float64 = 0.0
    var a: Float64 = 0.0
    if fabs(denom) > 1e-15:
        b = (nf * sxy - sx * sy) / denom
        a = (sy - b * sx) / nf
    else:
        a = sy / nf

    for i in range(n):
        result.append(data[i] - (a + b * Float64(i)))
    return result^


# ── Normalize signal to [-1, 1] ──────────────────────────────────────────────


def normalize_signal(data: List[Float64]) -> List[Float64]:
    """Normalize signal to [-1, 1] range.
    If all values are equal, returns all zeros."""
    var n = len(data)
    var result = List[Float64]()
    if n == 0:
        return result^

    var mn = data[0]
    var mx = data[0]
    for i in range(1, n):
        if data[i] < mn:
            mn = data[i]
        if data[i] > mx:
            mx = data[i]

    var rng = mx - mn
    if rng < 1e-15:
        for i in range(n):
            result.append(0.0)
        return result^

    for i in range(n):
        # Map [mn, mx] -> [-1, 1]
        result.append(2.0 * (data[i] - mn) / rng - 1.0)
    return result^


# ── Zero crossings ────────────────────────────────────────────────────────────


def zero_crossings(data: List[Float64]) -> Int:
    """Count the number of zero crossings (sign changes) in the data."""
    var n = len(data)
    if n <= 1:
        return 0
    var count = 0
    for i in range(1, n):
        # Sign change: one positive and one negative (or through zero)
        if (data[i - 1] > 0.0 and data[i] < 0.0) or (data[i - 1] < 0.0 and data[i] > 0.0):
            count += 1
        elif data[i - 1] != 0.0 and data[i] == 0.0:
            # Touching zero from nonzero
            count += 1
    return count


# ── Peak detection ────────────────────────────────────────────────────────────


def peak_detect(data: List[Float64], threshold: Float64) -> List[Int]:
    """Find indices of peaks above threshold.
    A peak is a local maximum: data[i] > data[i-1] and data[i] > data[i+1]
    and data[i] >= threshold."""
    var n = len(data)
    var peaks = List[Int]()
    if n <= 2:
        return peaks^
    for i in range(1, n - 1):
        if data[i] > data[i - 1] and data[i] > data[i + 1] and data[i] >= threshold:
            peaks.append(i)
    return peaks^
