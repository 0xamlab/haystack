"""
series.mojo — Time series forecasting. Zero Python imports.

Replaces prophet / custom forecasting code with pure Mojo implementations
for SMA, linear extrapolation, exponential smoothing, naive, seasonal naive,
drift, forecast accuracy, trend strength, and seasonality detection.

Public API:
  sma_forecast          — Simple moving average forecast
  linear_extrapolation  — OLS linear extrapolation
  weighted_moving_avg   — Weighted moving average (single value)
  exponential_forecast  — Single exponential smoothing forecast
  naive_forecast        — Repeat last value
  seasonal_naive        — Repeat last season cyclically
  drift_forecast        — Drift (average change) method
  forecast_accuracy     — MAE, MAPE, RMSE
  trend_strength        — 1 - var(residuals)/var(data)
  detect_seasonality    — Dominant period by autocorrelation
"""
from std.math import sqrt, abs as fabs


# ── sma_forecast ──────────────────────────────────────────────────────────────


def sma_forecast(data: List[Float64], window: Int, horizon: Int) -> List[Float64]:
    """Forecast next horizon values using SMA of last window values."""
    var n = len(data)
    var result = List[Float64]()
    # Empty data or window <= 0 would divide the average by zero (NaN cannot
    # cross the result wire); horizon zeros match drift/exponential forecast.
    if n == 0 or window <= 0:
        for _ in range(horizon):
            result.append(0.0)
        return result^
    var w = window
    if w > n:
        w = n
    var total: Float64 = 0.0
    for i in range(n - w, n):
        total += data[i]
    var sma = total / Float64(w)
    for _ in range(horizon):
        result.append(sma)
    return result^


# ── _ols_fit (helper) ─────────────────────────────────────────────────────────


def _ols_fit(data: List[Float64]) -> List[Float64]:
    """Fit y = a + b*x by OLS. Returns [a, b]."""
    var n = len(data)
    var sx: Float64 = 0.0
    var sy: Float64 = 0.0
    var sxx: Float64 = 0.0
    var sxy: Float64 = 0.0
    for i in range(n):
        var x = Float64(i)
        sx += x
        sy += data[i]
        sxx += x * x
        sxy += x * data[i]
    var nf = Float64(n)
    var denom = nf * sxx - sx * sx
    if fabs(denom) < 1e-15:
        var result = List[Float64]()
        result.append(sy / nf)
        result.append(0.0)
        return result^
    var b = (nf * sxy - sx * sy) / denom
    var a = (sy - b * sx) / nf
    var result = List[Float64]()
    result.append(a)
    result.append(b)
    return result^


# ── linear_extrapolation ─────────────────────────────────────────────────────


def linear_extrapolation(data: List[Float64], horizon: Int) -> List[Float64]:
    """Fit a line to all data (OLS), extrapolate horizon steps."""
    var n = len(data)
    var result = List[Float64]()
    # An empty series fits no line — _ols_fit would divide by zero and NaN
    # cannot cross the result wire. Horizon zeros match the sibling forecasters.
    if n == 0:
        for _ in range(horizon):
            result.append(0.0)
        return result^
    var fit = _ols_fit(data)
    var a = fit[0]
    var b = fit[1]
    for h in range(horizon):
        result.append(a + b * Float64(n + h))
    return result^


# ── weighted_moving_avg ───────────────────────────────────────────────────────


def weighted_moving_avg(data: List[Float64], weights: List[Float64]) -> Float64:
    """Weighted average of last len(weights) values."""
    var n = len(data)
    var w = len(weights)
    var total: Float64 = 0.0
    var wsum: Float64 = 0.0
    for i in range(w):
        var idx = n - w + i
        if idx >= 0:
            total += data[idx] * weights[i]
            wsum += weights[i]
    if wsum < 1e-15:
        return 0.0
    return total / wsum


# ── exponential_forecast ──────────────────────────────────────────────────────


def exponential_forecast(
    data: List[Float64], alpha: Float64, horizon: Int
) -> List[Float64]:
    """Single exponential smoothing. All forecasts = last smoothed value."""
    var n = len(data)
    if n == 0:
        var result = List[Float64]()
        for _ in range(horizon):
            result.append(0.0)
        return result^
    var s = data[0]
    for i in range(1, n):
        s = alpha * data[i] + (1.0 - alpha) * s
    var result = List[Float64]()
    for _ in range(horizon):
        result.append(s)
    return result^


# ── naive_forecast ────────────────────────────────────────────────────────────


def naive_forecast(data: List[Float64], horizon: Int) -> List[Float64]:
    """Repeat last value for horizon steps."""
    var result = List[Float64]()
    # data[len-1] on an empty list is an uncatchable out-of-bounds read;
    # horizon zeros match drift/exponential forecast.
    if len(data) == 0:
        for _ in range(horizon):
            result.append(0.0)
        return result^
    var last = data[len(data) - 1]
    for _ in range(horizon):
        result.append(last)
    return result^


# ── seasonal_naive ────────────────────────────────────────────────────────────


def seasonal_naive(
    data: List[Float64], period: Int, horizon: Int
) -> List[Float64]:
    """Repeat the last season (last period values) cyclically for horizon."""
    var n = len(data)
    var result = List[Float64]()
    # period <= 0 makes h % period undefined and period > n reads before the
    # list start — both uncatchable. Horizon zeros match the sibling forecasters.
    if n == 0 or period <= 0:
        for _ in range(horizon):
            result.append(0.0)
        return result^
    var p = period
    if p > n:
        p = n  # clamp like sma_forecast clamps window
    for h in range(horizon):
        var idx = n - p + (h % p)
        result.append(data[idx])
    return result^


# ── drift_forecast ────────────────────────────────────────────────────────────


def drift_forecast(data: List[Float64], horizon: Int) -> List[Float64]:
    """Drift: y_{T+h} = y_T + h * (y_T - y_1) / (T-1)."""
    var n = len(data)
    var result = List[Float64]()
    if n < 2:
        for _ in range(horizon):
            result.append(data[0] if n > 0 else 0.0)
        return result^
    var y_T = data[n - 1]
    var y_1 = data[0]
    var slope = (y_T - y_1) / Float64(n - 1)
    for h in range(1, horizon + 1):
        result.append(y_T + Float64(h) * slope)
    return result^


# ── forecast_accuracy ─────────────────────────────────────────────────────────


def forecast_accuracy(
    actual: List[Float64], predicted: List[Float64]
) -> List[Float64]:
    """Returns [MAE, MAPE, RMSE]."""
    var n = len(actual)
    # predicted[i] is read for every actual, and n == 0 would divide the
    # metrics by zero: no data, no accuracy.
    if n == 0 or len(predicted) < n:
        return List[Float64]()
    var mae: Float64 = 0.0
    var mape: Float64 = 0.0
    var mse: Float64 = 0.0
    for i in range(n):
        var err = fabs(actual[i] - predicted[i])
        mae += err
        if fabs(actual[i]) > 1e-15:
            mape += err / fabs(actual[i])
        var d = actual[i] - predicted[i]
        mse += d * d
    var nf = Float64(n)
    var result = List[Float64]()
    result.append(mae / nf)
    result.append(mape / nf * 100.0)
    result.append(sqrt(mse / nf))
    return result^


# ── trend_strength ────────────────────────────────────────────────────────────


def trend_strength(data: List[Float64]) -> Float64:
    """Trend strength: 1 - var(residuals)/var(data)."""
    var n = len(data)
    if n < 2:
        return 0.0
    var fit = _ols_fit(data)
    var a = fit[0]
    var b = fit[1]
    # Compute residuals variance and data variance
    var mean_d: Float64 = 0.0
    for i in range(n):
        mean_d += data[i]
    mean_d /= Float64(n)
    var var_data: Float64 = 0.0
    var var_resid: Float64 = 0.0
    for i in range(n):
        var dd = data[i] - mean_d
        var_data += dd * dd
        var r = data[i] - (a + b * Float64(i))
        var_resid += r * r
    if var_data < 1e-15:
        return 0.0
    var strength = 1.0 - var_resid / var_data
    if strength < 0.0:
        strength = 0.0
    return strength


# ── _autocorrelation (helper) ─────────────────────────────────────────────────


def _autocorrelation(data: List[Float64], lag: Int) -> Float64:
    """Autocorrelation at given lag."""
    var n = len(data)
    if lag >= n:
        return 0.0
    var mean: Float64 = 0.0
    for i in range(n):
        mean += data[i]
    mean /= Float64(n)
    var num: Float64 = 0.0
    var den: Float64 = 0.0
    for i in range(n):
        den += (data[i] - mean) * (data[i] - mean)
    if den < 1e-15:
        return 0.0
    for i in range(n - lag):
        num += (data[i] - mean) * (data[i + lag] - mean)
    return num / den


# ── detect_seasonality ────────────────────────────────────────────────────────


def detect_seasonality(data: List[Float64], max_period: Int) -> Int:
    """Detect dominant seasonality period (2..max_period) by autocorrelation."""
    var best_period = 2
    var best_acf: Float64 = -2.0
    var limit = max_period
    if limit >= len(data):
        limit = len(data) - 1
    for p in range(2, limit + 1):
        var acf = _autocorrelation(data, p)
        if acf > best_acf:
            best_acf = acf
            best_period = p
    return best_period
