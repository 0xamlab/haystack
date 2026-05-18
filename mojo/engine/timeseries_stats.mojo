"""
timeseries_stats.mojo — Time series statistics. Zero Python imports.

Replaces statsmodels with pure Mojo implementations for autocorrelation,
partial autocorrelation, rolling statistics, exponential smoothing,
differencing, and Augmented Dickey-Fuller test statistics.

Public API:
  autocorrelation          — Sample autocorrelation at given lag
  autocorrelation_function — ACF for lags 0..max_lag
  partial_autocorrelation  — PACF via Durbin-Levinson recursion
  rolling_mean             — Simple moving average
  rolling_std              — Rolling standard deviation
  exponential_smoothing    — Single exponential smoothing (SES)
  difference               — First or higher-order differencing
  adf_test_statistic       — Simplified Augmented Dickey-Fuller test statistic
  holt_linear              — Holt's linear trend method (double exponential smoothing)
"""
from std.math import sqrt, abs as fabs


# ── autocorrelation ──────────────────────────────────────────────────────────


fn autocorrelation(data: List[Float64], lag: Int) -> Float64:
    """Sample autocorrelation at the given lag.

    r(k) = Σ(xₜ - x̄)(xₜ₊ₖ - x̄) / Σ(xₜ - x̄)²

    Args:
        data: Time series values.
        lag:  Non-negative lag.

    Returns:
        Autocorrelation coefficient at the given lag. Returns 1.0 for lag=0.
    """
    var n = len(data)
    if n == 0 or lag < 0 or lag >= n:
        return 0.0

    # Compute mean
    var mean: Float64 = 0.0
    for i in range(n):
        mean += data[i]
    mean /= Float64(n)

    # Denominator: variance sum
    var denom: Float64 = 0.0
    for i in range(n):
        var d = data[i] - mean
        denom += d * d

    if fabs(denom) < 1e-15:
        return 0.0

    # Numerator: lagged covariance
    var num: Float64 = 0.0
    for i in range(n - lag):
        num += (data[i] - mean) * (data[i + lag] - mean)

    return num / denom


# ── autocorrelation_function ─────────────────────────────────────────────────


fn autocorrelation_function(data: List[Float64], max_lag: Int) -> List[Float64]:
    """Autocorrelation function for lags 0..max_lag.

    Args:
        data:    Time series values.
        max_lag: Maximum lag (inclusive).

    Returns:
        List of ACF values of length max_lag + 1.
    """
    var result = List[Float64]()
    for k in range(max_lag + 1):
        result.append(autocorrelation(data, k))
    return result^


# ── partial_autocorrelation ──────────────────────────────────────────────────


fn partial_autocorrelation(data: List[Float64], max_lag: Int) -> List[Float64]:
    """Partial autocorrelation function via Durbin-Levinson recursion.

    Args:
        data:    Time series values.
        max_lag: Maximum lag (inclusive).

    Returns:
        List of PACF values of length max_lag + 1.
        pacf[0] = 1.0 by convention.
    """
    var acf = autocorrelation_function(data, max_lag)
    var result = List[Float64]()
    result.append(1.0)  # PACF at lag 0 is always 1.0

    if max_lag == 0:
        return result^

    # Durbin-Levinson recursion
    # phi[k][j] represents the j-th coefficient at order k
    # We only need current and previous order
    var phi_prev = List[Float64]()
    for _ in range(max_lag + 1):
        phi_prev.append(0.0)

    var phi_curr = List[Float64]()
    for _ in range(max_lag + 1):
        phi_curr.append(0.0)

    # Order 1
    phi_curr[1] = acf[1]
    result.append(phi_curr[1])

    if max_lag == 1:
        return result^

    for k in range(2, max_lag + 1):
        # Copy current to previous
        for j in range(max_lag + 1):
            phi_prev[j] = phi_curr[j]

        # Numerator: r(k) - sum_{j=1}^{k-1} phi_{k-1,j} * r(k-j)
        var num: Float64 = acf[k]
        for j in range(1, k):
            num -= phi_prev[j] * acf[k - j]

        # Denominator: 1 - sum_{j=1}^{k-1} phi_{k-1,j} * r(j)
        var den: Float64 = 1.0
        for j in range(1, k):
            den -= phi_prev[j] * acf[j]

        if fabs(den) < 1e-15:
            phi_curr[k] = 0.0
        else:
            phi_curr[k] = num / den

        # Update coefficients
        for j in range(1, k):
            phi_curr[j] = phi_prev[j] - phi_curr[k] * phi_prev[k - j]

        result.append(phi_curr[k])

    return result^


# ── rolling_mean ─────────────────────────────────────────────────────────────


fn rolling_mean(data: List[Float64], window: Int) -> List[Float64]:
    """Simple moving average with given window size.

    Args:
        data:   Time series values.
        window: Window size (must be >= 1).

    Returns:
        List of length len(data) - window + 1.
    """
    var n = len(data)
    var result = List[Float64]()
    if window <= 0 or window > n:
        return result^

    # Initial window sum
    var s: Float64 = 0.0
    for i in range(window):
        s += data[i]
    result.append(s / Float64(window))

    # Slide window
    for i in range(window, n):
        s += data[i] - data[i - window]
        result.append(s / Float64(window))

    return result^


# ── rolling_std ──────────────────────────────────────────────────────────────


fn rolling_std(data: List[Float64], window: Int) -> List[Float64]:
    """Rolling standard deviation with given window size.

    Uses population standard deviation (ddof=0) within each window.

    Args:
        data:   Time series values.
        window: Window size (must be >= 1).

    Returns:
        List of length len(data) - window + 1.
    """
    var n = len(data)
    var result = List[Float64]()
    if window <= 0 or window > n:
        return result^

    for i in range(n - window + 1):
        var mean: Float64 = 0.0
        for j in range(window):
            mean += data[i + j]
        mean /= Float64(window)

        var var_sum: Float64 = 0.0
        for j in range(window):
            var d = data[i + j] - mean
            var_sum += d * d
        result.append(sqrt(var_sum / Float64(window)))

    return result^


# ── exponential_smoothing ────────────────────────────────────────────────────


fn exponential_smoothing(data: List[Float64], alpha: Float64) -> List[Float64]:
    """Single exponential smoothing (SES).

    s_0 = x_0
    s_t = α * x_t + (1 - α) * s_{t-1}

    Args:
        data:  Time series values.
        alpha: Smoothing factor in (0, 1].

    Returns:
        Smoothed series of same length as data.
    """
    var n = len(data)
    var result = List[Float64]()
    if n == 0:
        return result^

    result.append(data[0])
    for i in range(1, n):
        var s = alpha * data[i] + (1.0 - alpha) * result[i - 1]
        result.append(s)

    return result^


# ── difference ───────────────────────────────────────────────────────────────


fn difference(data: List[Float64], order: Int = 1) -> List[Float64]:
    """First or higher-order differencing.

    For order=1: diff[i] = data[i+1] - data[i]
    Higher orders apply differencing recursively.

    Args:
        data:  Time series values.
        order: Differencing order (default 1).

    Returns:
        Differenced series of length len(data) - order.
    """
    var current = List[Float64]()
    for i in range(len(data)):
        current.append(data[i])

    for _ in range(order):
        var next_list = List[Float64]()
        for i in range(len(current) - 1):
            next_list.append(current[i + 1] - current[i])
        current = next_list^

    return current^


# ── adf_test_statistic ───────────────────────────────────────────────────────


fn adf_test_statistic(data: List[Float64]) -> Float64:
    """Simplified Augmented Dickey-Fuller test statistic.

    Performs OLS regression of diff(y) on y_{t-1} (no additional lags).
    DF statistic = γ̂ / SE(γ̂)

    Args:
        data: Time series values (length >= 3 recommended).

    Returns:
        ADF test statistic (more negative → more likely stationary).
    """
    var n = len(data)
    if n < 3:
        return 0.0

    # diff(y) = y_t - y_{t-1} for t=1..n-1
    # Regress diff_y on y_{t-1}
    var m = n - 1  # number of observations

    # x = y_{t-1}, y_dep = diff(y_t)
    var sum_x: Float64 = 0.0
    var sum_y: Float64 = 0.0
    var sum_xx: Float64 = 0.0
    var sum_xy: Float64 = 0.0

    for i in range(m):
        var x = data[i]
        var y_dep = data[i + 1] - data[i]
        sum_x += x
        sum_y += y_dep
        sum_xx += x * x
        sum_xy += x * y_dep

    var fm = Float64(m)
    var denom = fm * sum_xx - sum_x * sum_x
    if fabs(denom) < 1e-15:
        return 0.0

    # OLS slope (gamma_hat)
    var gamma_hat = (fm * sum_xy - sum_x * sum_y) / denom

    # Residual sum of squares
    var intercept = (sum_y - gamma_hat * sum_x) / fm
    var rss: Float64 = 0.0
    for i in range(m):
        var x = data[i]
        var y_dep = data[i + 1] - data[i]
        var resid = y_dep - intercept - gamma_hat * x
        rss += resid * resid

    var s2 = rss / Float64(m - 2) if m > 2 else rss
    var se_gamma = sqrt(s2 * fm / denom)
    if fabs(se_gamma) < 1e-15:
        return 0.0

    return gamma_hat / se_gamma


# ── holt_linear ──────────────────────────────────────────────────────────────


fn holt_linear(
    data: List[Float64], alpha: Float64, beta: Float64
) -> List[Float64]:
    """Holt's linear trend method (double exponential smoothing).

    Level:  l_t = α * x_t + (1-α) * (l_{t-1} + b_{t-1})
    Trend:  b_t = β * (l_t - l_{t-1}) + (1-β) * b_{t-1}
    Fitted: f_t = l_t

    Initialisation: l_0 = x_0, b_0 = x_1 - x_0 (if available, else 0).

    Args:
        data:  Time series values.
        alpha: Level smoothing factor in (0, 1].
        beta:  Trend smoothing factor in (0, 1].

    Returns:
        Smoothed series of same length as data.
    """
    var n = len(data)
    var result = List[Float64]()
    if n == 0:
        return result^

    # Initialise
    var level = data[0]
    var trend: Float64 = 0.0
    if n > 1:
        trend = data[1] - data[0]

    result.append(level)

    for i in range(1, n):
        var prev_level = level
        level = alpha * data[i] + (1.0 - alpha) * (prev_level + trend)
        trend = beta * (level - prev_level) + (1.0 - beta) * trend
        result.append(level)

    return result^
