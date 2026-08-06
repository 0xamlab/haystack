"""
time_series_decompose.mojo — Time Series Decomposition. Zero Python imports.

Replaces statsmodels.tsa with pure Mojo implementations for additive
decomposition, trend extraction, seasonal estimation, and simplified STL.

Public API:
  moving_average_trend  — Extract trend via centered moving average
  detrend               — Remove trend: data - trend
  seasonal_component    — Extract seasonal pattern by period averaging
  residual              — Residual = data - trend - seasonal
  decompose_additive    — Full additive decomposition
  seasonal_strength     — 1 - var(residual)/var(seasonal+residual)
  trend_strength        — 1 - var(residual)/var(trend+residual)
  detect_period         — Auto-detect dominant period via autocorrelation peak
  stl_like              — Simplified STL iterative decomposition
"""

from std.math import sqrt, abs as fabs


# ── helpers ──────────────────────────────────────────────────────────────────


def _mean(data: List[Float64]) -> Float64:
    """Mean of a list."""
    var n = len(data)
    if n == 0:
        return 0.0
    var s: Float64 = 0.0
    for i in range(n):
        s += data[i]
    return s / Float64(n)


def _variance(data: List[Float64]) -> Float64:
    """Population variance."""
    var n = len(data)
    if n == 0:
        return 0.0
    var m = _mean(data)
    var s: Float64 = 0.0
    for i in range(n):
        var d = data[i] - m
        s += d * d
    return s / Float64(n)


# ── moving_average_trend ─────────────────────────────────────────────────────


def moving_average_trend(data: List[Float64], window: Int) -> List[Float64]:
    """Extract trend via centered moving average.

    Returns same-length list with edges zero-padded where the window doesn't fit.
    """
    var n = len(data)
    var result = List[Float64]()
    for i in range(n):
        result.append(0.0)
    if n == 0 or window <= 0:
        return result^
    var half = window // 2
    for i in range(n):
        if i < half or i >= n - half:
            result[i] = 0.0
        else:
            var s: Float64 = 0.0
            for j in range(i - half, i - half + window):
                s += data[j]
            result[i] = s / Float64(window)
    return result^


# ── detrend ──────────────────────────────────────────────────────────────────


def detrend(data: List[Float64], trend: List[Float64]) -> List[Float64]:
    """Remove trend: data - trend."""
    var n = len(data)
    var result = List[Float64]()
    for i in range(n):
        if i < len(trend):
            result.append(data[i] - trend[i])
        else:
            result.append(data[i])
    return result^


# ── seasonal_component ───────────────────────────────────────────────────────


def seasonal_component(detrended: List[Float64], period: Int) -> List[Float64]:
    """Extract seasonal pattern: average each position within period, then tile."""
    var n = len(detrended)
    if n == 0 or period <= 0:
        return List[Float64]()
    var season_avg = List[Float64]()
    for p in range(period):
        var s: Float64 = 0.0
        var count: Int = 0
        var idx = p
        while idx < n:
            s += detrended[idx]
            count += 1
            idx += period
        if count > 0:
            season_avg.append(s / Float64(count))
        else:
            season_avg.append(0.0)
    var result = List[Float64]()
    for i in range(n):
        result.append(season_avg[i % period])
    return result^


# ── residual ─────────────────────────────────────────────────────────────────


def residual(data: List[Float64], trend: List[Float64],
            seasonal: List[Float64]) -> List[Float64]:
    """Residual = data - trend - seasonal."""
    var n = len(data)
    var result = List[Float64]()
    for i in range(n):
        var t: Float64 = 0.0
        var s: Float64 = 0.0
        if i < len(trend):
            t = trend[i]
        if i < len(seasonal):
            s = seasonal[i]
        result.append(data[i] - t - s)
    return result^


# ── decompose_additive ──────────────────────────────────────────────────────


def decompose_additive(data: List[Float64],
                      period: Int) -> List[List[Float64]]:
    """Full additive decomposition. Returns [trend, seasonal, residual]."""
    var trend_comp = moving_average_trend(data, period)
    var detrended = detrend(data, trend_comp)
    var seasonal_comp = seasonal_component(detrended, period)
    var resid = residual(data, trend_comp, seasonal_comp)
    var result = List[List[Float64]]()
    result.append(trend_comp^)
    result.append(seasonal_comp^)
    result.append(resid^)
    return result^


# ── seasonal_strength ────────────────────────────────────────────────────────


def seasonal_strength(resid: List[Float64],
                     seasonal_plus_residual: List[Float64]) -> Float64:
    """1 - var(residual) / var(seasonal + residual)."""
    var var_r = _variance(resid)
    var var_sr = _variance(seasonal_plus_residual)
    if var_sr < 1e-15:
        return 0.0
    var val = 1.0 - var_r / var_sr
    if val < 0.0:
        return 0.0
    if val > 1.0:
        return 1.0
    return val


# ── trend_strength ───────────────────────────────────────────────────────────


def trend_strength(resid: List[Float64],
                  trend_plus_residual: List[Float64]) -> Float64:
    """1 - var(residual) / var(trend + residual)."""
    var var_r = _variance(resid)
    var var_tr = _variance(trend_plus_residual)
    if var_tr < 1e-15:
        return 0.0
    var val = 1.0 - var_r / var_tr
    if val < 0.0:
        return 0.0
    if val > 1.0:
        return 1.0
    return val


# ── detect_period ────────────────────────────────────────────────────────────


def detect_period(data: List[Float64], max_period: Int) -> Int:
    """Auto-detect dominant period via autocorrelation peak."""
    var n = len(data)
    if n < 4 or max_period < 2:
        return 1
    var m = _mean(data)
    var denom: Float64 = 0.0
    for i in range(n):
        var d = data[i] - m
        denom += d * d
    if denom < 1e-15:
        return 1
    var best_lag: Int = 1
    var best_acf: Float64 = -2.0
    var limit = max_period
    if limit >= n:
        limit = n - 1
    for lag in range(2, limit + 1):
        var numer: Float64 = 0.0
        for t in range(n - lag):
            numer += (data[t] - m) * (data[t + lag] - m)
        var acf = numer / denom
        if acf > best_acf:
            best_acf = acf
            best_lag = lag
    return best_lag


# ── stl_like ─────────────────────────────────────────────────────────────────


def stl_like(data: List[Float64], period: Int,
            n_iter: Int = 2) -> List[List[Float64]]:
    """Simplified STL: iterative trend + seasonal extraction.

    Returns [trend, seasonal, residual].
    """
    var n = len(data)
    # period > n would allocate a period-sized seasonal table and crash the
    # second iteration (empty seasonal list subscripted below).
    if period <= 0 or period > n:
        return List[List[Float64]]()
    var trend_comp = List[Float64]()
    for i in range(n):
        trend_comp.append(0.0)
    var seasonal_comp = List[Float64]()
    for i in range(n):
        seasonal_comp.append(0.0)

    for _iter in range(n_iter):
        var deseasoned = List[Float64]()
        for i in range(n):
            deseasoned.append(data[i] - seasonal_comp[i])
        trend_comp = moving_average_trend(deseasoned, period)
        var detrended = detrend(data, trend_comp)
        seasonal_comp = seasonal_component(detrended, period)

    var resid = residual(data, trend_comp, seasonal_comp)
    var result = List[List[Float64]]()
    result.append(trend_comp^)
    result.append(seasonal_comp^)
    result.append(resid^)
    return result^
