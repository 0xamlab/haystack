"""
spectral.mojo — Spectral Analysis Library. Zero Python imports.

Pure Mojo implementations for power spectral density, cross-spectral
density, coherence, spectral centroid/bandwidth/rolloff/flatness/entropy,
band energy, and peak frequency.

Public API:
  power_spectral_density    — PSD via periodogram
  cross_spectral_density    — Cross-PSD between two signals
  coherence                 — Magnitude-squared coherence
  spectral_centroid         — Weighted mean frequency
  spectral_bandwidth        — Spectral spread around centroid
  spectral_rolloff          — Freq below which threshold% of energy
  spectral_flatness         — Geometric mean / arithmetic mean
  spectral_entropy          — Shannon entropy of normalized spectrum
  band_energy               — Energy in a frequency band
  peak_frequency            — Frequency with highest magnitude
"""
from std.math import sqrt, abs as fabs, log, exp


# ── Constants ────────────────────────────────────────────────────────────────

comptime PI: Float64 = 3.141592653589793


# ── Trig helpers ─────────────────────────────────────────────────────────────


fn _sin(x: Float64) -> Float64:
    """Sin via range reduction + Taylor series."""
    var v = x
    while v > PI:
        v -= 2.0 * PI
    while v < -PI:
        v += 2.0 * PI
    var x2 = v * v
    var x3 = v * x2
    var x5 = x3 * x2
    var x7 = x5 * x2
    var x9 = x7 * x2
    var x11 = x9 * x2
    return v - x3 / 6.0 + x5 / 120.0 - x7 / 5040.0 + x9 / 362880.0 - x11 / 39916800.0


fn _cos(x: Float64) -> Float64:
    """Cos via sin(x + pi/2)."""
    return _sin(x + PI / 2.0)


# ── DFT helper ───────────────────────────────────────────────────────────────


fn _dft_real(signal: List[Float64]) -> List[Float64]:
    """Compute |DFT[k]|^2 for k=0..N/2. Returns N/2+1 power values."""
    var n = len(signal)
    var half = n // 2 + 1
    var result = List[Float64]()
    for k in range(half):
        var re: Float64 = 0.0
        var im: Float64 = 0.0
        for j in range(n):
            var angle = 2.0 * PI * Float64(k) * Float64(j) / Float64(n)
            re += signal[j] * _cos(angle)
            im -= signal[j] * _sin(angle)
        result.append(re * re + im * im)
    return result^


fn _dft_complex(signal: List[Float64]) -> List[Float64]:
    """Return interleaved [re0, im0, re1, im1, ...] for k=0..N/2."""
    var n = len(signal)
    var half = n // 2 + 1
    var result = List[Float64]()
    for k in range(half):
        var re: Float64 = 0.0
        var im: Float64 = 0.0
        for j in range(n):
            var angle = 2.0 * PI * Float64(k) * Float64(j) / Float64(n)
            re += signal[j] * _cos(angle)
            im -= signal[j] * _sin(angle)
        result.append(re)
        result.append(im)
    return result^


# ── power_spectral_density ───────────────────────────────────────────────────


fn power_spectral_density(signal: List[Float64], fs: Float64) -> List[Float64]:
    """Estimate PSD using periodogram: |DFT|^2 / (N * fs)."""
    var n = len(signal)
    if n == 0:
        return List[Float64]()
    var pows = _dft_real(signal)
    var result = List[Float64]()
    var nf = Float64(n) * fs
    for i in range(len(pows)):
        result.append(pows[i] / nf)
    return result^


# ── cross_spectral_density ───────────────────────────────────────────────────


fn cross_spectral_density(x: List[Float64], y: List[Float64], fs: Float64) -> List[Float64]:
    """Cross-PSD: Re(X* Y) / (N * fs). Returns magnitude of cross-spectrum."""
    var n = len(x)
    if n == 0 or len(y) != n:
        return List[Float64]()
    var dx = _dft_complex(x)
    var dy = _dft_complex(y)
    var half = n // 2 + 1
    var nf = Float64(n) * fs
    var result = List[Float64]()
    for k in range(half):
        var xr = dx[k * 2]
        var xi = dx[k * 2 + 1]
        var yr = dy[k * 2]
        var yi = dy[k * 2 + 1]
        # X* Y = (xr - j*xi)(yr + j*yi) = (xr*yr + xi*yi) + j(xr*yi - xi*yr)
        var csd_re = (xr * yr + xi * yi) / nf
        var csd_im = (xr * yi - xi * yr) / nf
        result.append(sqrt(csd_re * csd_re + csd_im * csd_im))
    return result^


# ── coherence ────────────────────────────────────────────────────────────────


fn coherence(x: List[Float64], y: List[Float64], fs: Float64) -> List[Float64]:
    """Magnitude-squared coherence: |Sxy|^2 / (Sxx * Syy)."""
    var csd = cross_spectral_density(x, y, fs)
    var pxx = power_spectral_density(x, fs)
    var pyy = power_spectral_density(y, fs)
    var result = List[Float64]()
    for i in range(len(csd)):
        var denom = pxx[i] * pyy[i]
        if denom < 1e-30:
            result.append(0.0)
        else:
            var val = (csd[i] * csd[i]) / denom
            if val > 1.0:
                val = 1.0
            result.append(val)
    return result^


# ── spectral_centroid ────────────────────────────────────────────────────────


fn spectral_centroid(magnitudes: List[Float64], frequencies: List[Float64]) -> Float64:
    """Weighted mean frequency: sum(f*m) / sum(m)."""
    if len(magnitudes) != len(frequencies):
        return 0.0
    var num: Float64 = 0.0
    var den: Float64 = 0.0
    for i in range(len(magnitudes)):
        num += frequencies[i] * magnitudes[i]
        den += magnitudes[i]
    if den < 1e-30:
        return 0.0
    return num / den


# ── spectral_bandwidth ──────────────────────────────────────────────────────


fn spectral_bandwidth(magnitudes: List[Float64], frequencies: List[Float64], centroid: Float64) -> Float64:
    """Spectral spread: sqrt(sum(m*(f-c)^2) / sum(m))."""
    if len(magnitudes) != len(frequencies):
        return 0.0
    var num: Float64 = 0.0
    var den: Float64 = 0.0
    for i in range(len(magnitudes)):
        var diff = frequencies[i] - centroid
        num += magnitudes[i] * diff * diff
        den += magnitudes[i]
    if den < 1e-30:
        return 0.0
    return sqrt(num / den)


# ── spectral_rolloff ────────────────────────────────────────────────────────


fn spectral_rolloff(magnitudes: List[Float64], frequencies: List[Float64], threshold: Float64) -> Float64:
    """Frequency below which threshold fraction of total energy lies."""
    if len(magnitudes) != len(frequencies):
        return 0.0
    var total: Float64 = 0.0
    for i in range(len(magnitudes)):
        total += magnitudes[i]
    var target = total * threshold
    var cumsum: Float64 = 0.0
    for i in range(len(magnitudes)):
        cumsum += magnitudes[i]
        if cumsum >= target:
            return frequencies[i]
    if len(frequencies) > 0:
        return frequencies[len(frequencies) - 1]
    return 0.0


# ── spectral_flatness ───────────────────────────────────────────────────────


fn spectral_flatness(magnitudes: List[Float64]) -> Float64:
    """Geometric mean / arithmetic mean of spectrum. 1=white noise, 0=tonal."""
    var n = len(magnitudes)
    if n == 0:
        return 0.0
    var log_sum: Float64 = 0.0
    var arith_sum: Float64 = 0.0
    var count: Int = 0
    for i in range(n):
        if magnitudes[i] > 1e-30:
            log_sum += log(magnitudes[i])
            arith_sum += magnitudes[i]
            count += 1
        else:
            return 0.0  # zero value → flatness is 0
    if count == 0 or arith_sum < 1e-30:
        return 0.0
    var geo_mean = exp(log_sum / Float64(count))
    var arith_mean = arith_sum / Float64(count)
    return geo_mean / arith_mean


# ── spectral_entropy ─────────────────────────────────────────────────────────


fn spectral_entropy(magnitudes: List[Float64]) -> Float64:
    """Shannon entropy of normalized spectrum. Higher = more uniform."""
    var n = len(magnitudes)
    if n == 0:
        return 0.0
    var total: Float64 = 0.0
    for i in range(n):
        total += magnitudes[i]
    if total < 1e-30:
        return 0.0
    var entropy: Float64 = 0.0
    for i in range(n):
        var p = magnitudes[i] / total
        if p > 1e-30:
            entropy -= p * log(p)
    return entropy


# ── band_energy ──────────────────────────────────────────────────────────────


fn band_energy(magnitudes: List[Float64], frequencies: List[Float64], low: Float64, high: Float64) -> Float64:
    """Energy in frequency band [low, high]."""
    if len(magnitudes) != len(frequencies):
        return 0.0
    var energy: Float64 = 0.0
    for i in range(len(magnitudes)):
        if frequencies[i] >= low and frequencies[i] <= high:
            energy += magnitudes[i] * magnitudes[i]
    return energy


# ── peak_frequency ───────────────────────────────────────────────────────────


fn peak_frequency(magnitudes: List[Float64], frequencies: List[Float64]) -> Float64:
    """Frequency with highest magnitude."""
    if len(magnitudes) == 0 or len(magnitudes) != len(frequencies):
        return 0.0
    var max_val = magnitudes[0]
    var max_idx: Int = 0
    for i in range(1, len(magnitudes)):
        if magnitudes[i] > max_val:
            max_val = magnitudes[i]
            max_idx = i
    return frequencies[max_idx]
