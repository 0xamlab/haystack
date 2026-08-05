"""
filter.mojo — Digital Filters. Zero Python imports.

Replaces scipy.signal filter functions with pure Mojo implementations of
EMA low/high/band-pass, median, Savitzky-Golay, moving average, IIR,
differentiation, integration, SNR, and RMS.

Public API:
  lowpass_ema          — Exponential moving average low-pass filter
  highpass_ema         — High-pass = original - low-pass
  bandpass             — Band-pass = low(alpha_low) - low(alpha_high)
  median_filter        — Median filter with odd window
  savitzky_golay_3     — Simplified Savitzky-Golay (window=5, poly=2)
  moving_average_filter — Simple moving average filter
  iir_filter_1st       — First-order IIR filter
  diff_filter          — First difference filter
  integrate_filter     — Cumulative trapezoidal integration
  snr                  — Signal-to-noise ratio in dB
  rms                  — Root mean square
"""

from std.math import sqrt, log as math_log


# ── lowpass_ema ──────────────────────────────────────────────────────────────


fn lowpass_ema(data: List[Float64], alpha: Float64) -> List[Float64]:
    """Exponential moving average low-pass filter.
    alpha in (0,1), lower = smoother."""
    var n = len(data)
    var result = List[Float64]()
    if n == 0:
        return result^
    result.append(data[0])
    for i in range(1, n):
        var prev = result[i - 1]
        result.append(alpha * data[i] + (1.0 - alpha) * prev)
    return result^


# ── highpass_ema ─────────────────────────────────────────────────────────────


fn highpass_ema(data: List[Float64], alpha: Float64) -> List[Float64]:
    """High-pass filter = original - low-pass."""
    var lp = lowpass_ema(data, alpha)
    var n = len(data)
    var result = List[Float64]()
    for i in range(n):
        result.append(data[i] - lp[i])
    return result^


# ── bandpass ─────────────────────────────────────────────────────────────────


fn bandpass(
    data: List[Float64], alpha_low: Float64, alpha_high: Float64
) -> List[Float64]:
    """Band-pass = low-pass(alpha_low) - low-pass(alpha_high).
    alpha_low < alpha_high."""
    var lp_low = lowpass_ema(data, alpha_low)
    var lp_high = lowpass_ema(data, alpha_high)
    var n = len(data)
    var result = List[Float64]()
    for i in range(n):
        result.append(lp_low[i] - lp_high[i])
    return result^


# ── median_filter ────────────────────────────────────────────────────────────


fn _sort_window(mut arr: List[Float64]):
    """Simple insertion sort for small windows."""
    var n = len(arr)
    for i in range(1, n):
        var key = arr[i]
        var j = i - 1
        while j >= 0 and arr[j] > key:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = key


fn median_filter(data: List[Float64], window: Int) -> List[Float64]:
    """Median filter with given window size (must be odd)."""
    var n = len(data)
    var result = List[Float64]()
    # window <= 0 inverts the window bounds and reads an empty window past the
    # end; matches moving_average_filter's refusal.
    if n == 0 or window <= 0:
        return result^
    var w = window
    if w % 2 == 0:
        w += 1  # ensure odd
    var hw = w // 2
    for i in range(n):
        var lo = i - hw
        var hi = i + hw
        if lo < 0:
            lo = 0
        if hi >= n:
            hi = n - 1
        var win = List[Float64]()
        for j in range(lo, hi + 1):
            win.append(data[j])
        _sort_window(win)
        var mid = len(win) // 2
        result.append(win[mid])
    return result^


# ── savitzky_golay_3 ─────────────────────────────────────────────────────────


fn savitzky_golay_3(data: List[Float64]) -> List[Float64]:
    """Simplified Savitzky-Golay with window=5, polynomial=2.
    Coefficients: [-3, 12, 17, 12, -3] / 35."""
    var n = len(data)
    var result = List[Float64]()
    if n < 5:
        for i in range(n):
            result.append(data[i])
        return result^
    # First two points: copy
    result.append(data[0])
    result.append(data[1])
    for i in range(2, n - 2):
        var v = (-3.0 * data[i - 2] + 12.0 * data[i - 1] + 17.0 * data[i]
                 + 12.0 * data[i + 1] - 3.0 * data[i + 2]) / 35.0
        result.append(v)
    # Last two points: copy
    result.append(data[n - 2])
    result.append(data[n - 1])
    return result^


# ── moving_average_filter ────────────────────────────────────────────────────


fn moving_average_filter(data: List[Float64], window: Int) -> List[Float64]:
    """Simple moving average filter."""
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
        result.append(s / Float64(cnt))
    return result^


# ── iir_filter_1st ───────────────────────────────────────────────────────────


fn iir_filter_1st(data: List[Float64], a: Float64, b: Float64) -> List[Float64]:
    """First-order IIR: y[n] = b*x[n] + a*y[n-1]."""
    var n = len(data)
    var result = List[Float64]()
    if n == 0:
        return result^
    result.append(b * data[0])
    for i in range(1, n):
        var prev = result[i - 1]
        result.append(b * data[i] + a * prev)
    return result^


# ── diff_filter ──────────────────────────────────────────────────────────────


fn diff_filter(data: List[Float64]) -> List[Float64]:
    """First difference filter: y[n] = x[n] - x[n-1]."""
    var n = len(data)
    var result = List[Float64]()
    for i in range(1, n):
        result.append(data[i] - data[i - 1])
    return result^


# ── integrate_filter ─────────────────────────────────────────────────────────


fn integrate_filter(data: List[Float64], dt: Float64 = 1.0) -> List[Float64]:
    """Cumulative trapezoidal integration."""
    var n = len(data)
    var result = List[Float64]()
    if n == 0:
        return result^
    result.append(0.0)
    for i in range(1, n):
        var prev = result[i - 1]
        result.append(prev + 0.5 * (data[i - 1] + data[i]) * dt)
    return result^


# ── snr ──────────────────────────────────────────────────────────────────────


fn snr(signal: List[Float64], noise: List[Float64]) -> Float64:
    """Signal-to-noise ratio in dB: 10*log10(Σsig²/Σnoise²)."""
    var sig_power: Float64 = 0.0
    for i in range(len(signal)):
        sig_power += signal[i] * signal[i]
    var noise_power: Float64 = 0.0
    for i in range(len(noise)):
        noise_power += noise[i] * noise[i]
    if noise_power == 0.0:
        return 1e30  # effectively infinite
    var ratio = sig_power / noise_power
    if ratio <= 0.0:
        return -1e30
    # log10(x) = ln(x) / ln(10)
    var ln10 = 2.302585092994046
    return 10.0 * math_log(ratio) / ln10


# ── rms ──────────────────────────────────────────────────────────────────────


fn rms(data: List[Float64]) -> Float64:
    """Root mean square value."""
    var n = len(data)
    if n == 0:
        return 0.0
    var s: Float64 = 0.0
    for i in range(n):
        s += data[i] * data[i]
    return sqrt(s / Float64(n))
