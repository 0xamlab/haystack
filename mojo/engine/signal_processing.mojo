"""
signal_processing.mojo — Advanced signal processing. Zero Python imports.

Replaces scipy.signal advanced with pure Mojo implementations for
window functions, peak detection, zero crossings, and spectral features.

Public API:
  hamming_window    — Hamming window coefficients
  hann_window       — Hann window coefficients
  blackman_window   — Blackman window coefficients
  apply_window      — Element-wise multiply data by window
  peak_detect       — Find local peaks above threshold
  zero_crossings    — Find zero-crossing indices
  spectral_energy   — Total spectral energy Σ|X[k]|²
  spectral_centroid — Weighted mean frequency
  spectral_flatness — Geometric mean / arithmetic mean (Wiener entropy)
  signal_power      — Mean of x²
"""
from std.math import cos, log, exp, sqrt


# ── Constants ──────────────────────────────────────────────────────────────────

alias PI: Float64 = 3.141592653589793
alias TWO_PI: Float64 = 6.283185307179586


# ── Window functions ───────────────────────────────────────────────────────────


fn hamming_window(n: Int) -> List[Float64]:
    """Hamming window: 0.54 - 0.46*cos(2πk/(n-1)).

    Returns n coefficients for the symmetric Hamming window.
    """
    var w = List[Float64]()
    if n <= 0:
        return w^
    if n == 1:
        w.append(1.0)
        return w^
    var denom = Float64(n - 1)
    for k in range(n):
        var val = 0.54 - 0.46 * cos(TWO_PI * Float64(k) / denom)
        w.append(val)
    return w^


fn hann_window(n: Int) -> List[Float64]:
    """Hann window: 0.5*(1 - cos(2πk/(n-1))).

    Returns n coefficients for the symmetric Hann window.
    """
    var w = List[Float64]()
    if n <= 0:
        return w^
    if n == 1:
        w.append(1.0)
        return w^
    var denom = Float64(n - 1)
    for k in range(n):
        var val = 0.5 * (1.0 - cos(TWO_PI * Float64(k) / denom))
        w.append(val)
    return w^


fn blackman_window(n: Int) -> List[Float64]:
    """Blackman window: 0.42 - 0.5*cos(2πk/(n-1)) + 0.08*cos(4πk/(n-1)).

    Returns n coefficients for the symmetric Blackman window.
    """
    var w = List[Float64]()
    if n <= 0:
        return w^
    if n == 1:
        w.append(1.0)
        return w^
    var denom = Float64(n - 1)
    for k in range(n):
        var fk = Float64(k)
        var val = 0.42 - 0.5 * cos(TWO_PI * fk / denom) + 0.08 * cos(
            2.0 * TWO_PI * fk / denom
        )
        w.append(val)
    return w^


# ── Window application ─────────────────────────────────────────────────────────


fn apply_window(
    data: List[Float64], window: List[Float64]
) -> List[Float64]:
    """Element-wise multiply data by window.

    Uses the minimum length of data and window.
    """
    var n = len(data)
    var m = len(window)
    var sz = n if n < m else m
    var out = List[Float64]()
    for i in range(sz):
        out.append(data[i] * window[i])
    return out^


# ── Peak detection ─────────────────────────────────────────────────────────────


fn peak_detect(data: List[Float64], threshold: Float64) -> List[Int]:
    """Find local peaks above threshold.

    A peak at index i means data[i] > data[i-1] and data[i] > data[i+1]
    and data[i] > threshold.
    """
    var peaks = List[Int]()
    var n = len(data)
    if n < 3:
        return peaks^
    for i in range(1, n - 1):
        if data[i] > data[i - 1] and data[i] > data[i + 1] and data[i] > threshold:
            peaks.append(i)
    return peaks^


# ── Zero crossings ─────────────────────────────────────────────────────────────


fn zero_crossings(data: List[Float64]) -> List[Int]:
    """Find zero-crossing indices.

    Index i is a crossing if sign(data[i]) != sign(data[i+1]).
    Returns indices where crossings occur.
    """
    var crossings = List[Int]()
    var n = len(data)
    if n < 2:
        return crossings^
    for i in range(n - 1):
        var s1: Float64 = 1.0 if data[i] >= 0.0 else -1.0
        var s2: Float64 = 1.0 if data[i + 1] >= 0.0 else -1.0
        if s1 != s2:
            crossings.append(i)
    return crossings^


# ── Spectral features ─────────────────────────────────────────────────────────


fn spectral_energy(magnitudes: List[Float64]) -> Float64:
    """Total spectral energy: Σ|X[k]|².

    Sum of squared magnitudes.
    """
    var energy: Float64 = 0.0
    for i in range(len(magnitudes)):
        energy += magnitudes[i] * magnitudes[i]
    return energy


fn spectral_centroid(
    magnitudes: List[Float64], sample_rate: Float64
) -> Float64:
    """Weighted mean frequency.

    centroid = Σ(f_k * |X[k]|) / Σ|X[k]|
    where f_k = k * sample_rate / (2 * N) for N frequency bins.
    """
    var n = len(magnitudes)
    if n == 0:
        return 0.0
    var weighted_sum: Float64 = 0.0
    var total: Float64 = 0.0
    var freq_step = sample_rate / (2.0 * Float64(n))
    for k in range(n):
        var freq = Float64(k) * freq_step
        var mag = magnitudes[k]
        if mag < 0.0:
            mag = -mag
        weighted_sum += freq * mag
        total += mag
    if total == 0.0:
        return 0.0
    return weighted_sum / total


fn spectral_flatness(magnitudes: List[Float64]) -> Float64:
    """Spectral flatness: geometric mean / arithmetic mean (Wiener entropy).

    Returns value in [0, 1]. 1 = flat (white noise), 0 = tonal.
    Uses log-domain computation for numerical stability.
    """
    var n = len(magnitudes)
    if n == 0:
        return 0.0
    var log_sum: Float64 = 0.0
    var arith_sum: Float64 = 0.0
    var count: Int = 0
    for i in range(n):
        var mag = magnitudes[i]
        if mag < 0.0:
            mag = -mag
        if mag < 1e-20:
            mag = 1e-20
        log_sum += log(mag)
        arith_sum += mag
        count += 1
    if count == 0 or arith_sum == 0.0:
        return 0.0
    var geo_mean = exp(log_sum / Float64(count))
    var arith_mean = arith_sum / Float64(count)
    var result = geo_mean / arith_mean
    if result > 1.0:
        result = 1.0
    if result < 0.0:
        result = 0.0
    return result


# ── Signal power ───────────────────────────────────────────────────────────────


fn signal_power(data: List[Float64]) -> Float64:
    """Mean of x² (signal power).

    Returns the average power of the signal.
    """
    var n = len(data)
    if n == 0:
        return 0.0
    var total: Float64 = 0.0
    for i in range(n):
        total += data[i] * data[i]
    return total / Float64(n)
