"""
dendrochronology.mojo — Tree ring science calculations. Zero Python imports.

Public API:
  ring_width_index             — detrended ring width (RWI)
  basal_area_increment         — BAI from consecutive radii
  standardise_negative_exp     — negative exponential age trend removal
  sensitivity_coefficient      — mean sensitivity of ring series
  first_order_autocorrelation  — lag-1 autocorrelation
  expressed_population_signal  — EPS from rbar and number of trees
  signal_free_mean             — iterative signal extraction
  pointer_year_threshold       — year-specific departure threshold
  crossdating_t_value          — Student's t for cross-correlation
  temperature_response         — ring width vs temperature regression slope
"""
from std.math import sqrt, exp, log, pow


def ring_width_index(ring_width: Float64, trend_value: Float64) -> Float64:
    """Detrended ring width index: RWI = RW / trend.

    Args:
        ring_width: Measured ring width (mm).
        trend_value: Expected trend value from age model (mm).

    Returns:
        Ring width index (1.0 = average).
    """
    if trend_value <= 0.0:
        return 0.0
    return ring_width / trend_value


def basal_area_increment(
    radius_now: Float64, radius_prev: Float64
) -> Float64:
    """Basal area increment for one year.

    BAI = π·(R_n² - R_(n-1)²)

    Args:
        radius_now: Cumulative radius at end of year (mm).
        radius_prev: Cumulative radius at start of year (mm).

    Returns:
        Annual basal area increment (mm²).
    """
    var pi = 3.141592653589793
    return pi * (radius_now * radius_now - radius_prev * radius_prev)


def standardise_negative_exp(
    ring_width: Float64, a: Float64, b: Float64, age: Float64
) -> Float64:
    """Negative exponential detrending: trend(t) = a·exp(-b·t).

    Args:
        ring_width: Observed ring width (mm).
        a: Exponential intercept parameter.
        b: Exponential decay rate.
        age: Cambial age (years).

    Returns:
        Standardised index.
    """
    var trend = a * exp(-b * age)
    if trend <= 0.0:
        return 1.0
    return ring_width / trend


def sensitivity_coefficient(mean_width: Float64, std_width: Float64) -> Float64:
    """Mean sensitivity: ratio of std to mean ring width.

    MS = σ / μ  (coefficient of variation)

    Args:
        mean_width: Mean ring width (mm).
        std_width: Standard deviation of ring widths (mm).

    Returns:
        Mean sensitivity (dimensionless).
    """
    if mean_width <= 0.0:
        return 0.0
    return std_width / mean_width


def first_order_autocorrelation(
    mean: Float64, n: Float64, sum_lag_product: Float64, sum_sq_dev: Float64
) -> Float64:
    """First-order autocorrelation coefficient r1.

    r1 = Σ(xi - x̄)(x_{i+1} - x̄) / Σ(xi - x̄)²

    Args:
        mean: Series mean.
        n: Number of observations.
        sum_lag_product: Σ(xi - x̄)(x_{i+1} - x̄).
        sum_sq_dev: Σ(xi - x̄)².

    Returns:
        Lag-1 autocorrelation (-1 to 1).
    """
    if sum_sq_dev <= 0.0:
        return 0.0
    return sum_lag_product / sum_sq_dev


def expressed_population_signal(rbar: Float64, n_trees: Float64) -> Float64:
    """Expressed Population Signal (EPS).

    EPS = n·rbar / (n·rbar + (1 - rbar))

    Args:
        rbar: Mean inter-series correlation.
        n_trees: Number of trees.

    Returns:
        EPS (0–1; EPS > 0.85 is generally accepted as adequate signal).
    """
    var denom = n_trees * rbar + (1.0 - rbar)
    if denom <= 0.0:
        return 0.0
    return n_trees * rbar / denom


def signal_free_mean(mean_rwi: Float64, signal_strength: Float64) -> Float64:
    """Signal-free chronology value (simplified iteration step).

    Residual = RWI - signal_strength * (RWI - 1)

    Args:
        mean_rwi: Mean ring width index value.
        signal_strength: Common variance fraction (rbar).

    Returns:
        Signal-free adjusted value.
    """
    return mean_rwi - signal_strength * (mean_rwi - 1.0)


def pointer_year_threshold(
    mean_width: Float64, std_width: Float64, k: Float64
) -> Float64:
    """Threshold for pointer year detection.

    threshold = mean ± k·std

    Args:
        mean_width: Long-term mean ring width or index.
        std_width: Standard deviation.
        k: Multiplier (typically 1.28 for 90th percentile).

    Returns:
        Absolute threshold for negative pointer year.
    """
    return mean_width - k * std_width


def crossdating_t_value(
    r: Float64, n: Float64
) -> Float64:
    """Student's t for cross-correlation significance.

    t = r · sqrt(n-2) / sqrt(1-r²)

    Args:
        r: Pearson correlation coefficient.
        n: Overlap length (years).

    Returns:
        t statistic.
    """
    if n <= 2.0 or r * r >= 1.0:
        return 0.0
    return r * sqrt(n - 2.0) / sqrt(1.0 - r * r)


def temperature_response(
    sum_rw_t_product: Float64, sum_t_sq: Float64, n: Float64,
    mean_rw: Float64, mean_t: Float64
) -> Float64:
    """Simple linear regression slope of ring width vs temperature.

    β = Σ(Ti - T̄)(RWi - RW̄) / Σ(Ti - T̄)²

    Args:
        sum_rw_t_product: Σ(Ti - T̄)(RWi - RW̄).
        sum_t_sq: Σ(Ti - T̄)².
        n: Number of years.
        mean_rw: Mean ring width index.
        mean_t: Mean temperature.

    Returns:
        Regression slope β (mm/°C or index/°C).
    """
    if sum_t_sq <= 0.0:
        return 0.0
    return sum_rw_t_product / sum_t_sq
