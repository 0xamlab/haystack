"""
feature_engineering.mojo — Feature scaling, encoding, and transformation.
Zero Python imports.

Public API:
  minmax_scale                   — min-max normalisation
  standard_scale                 — z-score standardisation
  robust_scale                   — median/IQR robust scaling
  log_transform                  — log1p feature transformation
  box_cox_transform              — Box-Cox power transformation
  yeo_johnson_transform          — Yeo-Johnson transformation
  feature_cross                  — polynomial feature cross
  quantile_rank                  — percentile rank of a value
  target_encode_smooth           — Bayesian target encoding
  binning_equal_width            — equal-width bin assignment
"""
from std.math import sqrt, log, exp


fn minmax_scale(
    x: Float64, x_min: Float64, x_max: Float64
) -> Float64:
    """Min-max normalisation: (x - min) / (max - min).

    Args:
        x: Input value.
        x_min: Feature minimum.
        x_max: Feature maximum.

    Returns:
        Normalised value in [0, 1].
    """
    var rng = x_max - x_min
    if rng <= 0.0:
        return 0.0
    return (x - x_min) / rng


fn standard_scale(x: Float64, mean: Float64, std: Float64) -> Float64:
    """Z-score standardisation: (x - μ) / σ.

    Args:
        x: Input value.
        mean: Feature mean.
        std: Feature standard deviation.

    Returns:
        Standardised value.
    """
    if std <= 0.0:
        return 0.0
    return (x - mean) / std


fn robust_scale(
    x: Float64, median: Float64, iqr: Float64
) -> Float64:
    """Robust scaling: (x - median) / IQR.

    Robust to outliers.

    Args:
        x: Input value.
        median: Feature median.
        iqr: Interquartile range (Q3 - Q1).

    Returns:
        Robustly scaled value.
    """
    if iqr <= 0.0:
        return 0.0
    return (x - median) / iqr


fn log_transform(x: Float64) -> Float64:
    """Log1p feature transformation: log(1 + x).

    Handles right-skewed distributions.

    Args:
        x: Input (x > -1).

    Returns:
        log(1 + x).
    """
    if x <= -1.0:
        return -1e300
    return log(1.0 + x)


fn box_cox_transform(x: Float64, lam: Float64) -> Float64:
    """Box-Cox power transformation.

    T(x) = (x^λ - 1) / λ  if λ ≠ 0, else log(x)

    Args:
        x: Input (must be > 0).
        lam: Lambda parameter.

    Returns:
        Transformed value.
    """
    if x <= 0.0:
        return -1e300
    if lam == 0.0:
        return log(x)
    return (exp(lam * log(x)) - 1.0) / lam


fn yeo_johnson_transform(x: Float64, lam: Float64) -> Float64:
    """Yeo-Johnson transformation (works for x ≥ 0 and x < 0).

    For x ≥ 0, λ ≠ 0: ((x+1)^λ - 1) / λ
    For x ≥ 0, λ = 0: log(x+1)

    Args:
        x: Input value (any real).
        lam: Lambda parameter.

    Returns:
        Transformed value.
    """
    if x >= 0.0:
        if lam == 0.0:
            return log(x + 1.0)
        return (exp(lam * log(x + 1.0)) - 1.0) / lam
    else:
        var two_minus_lam = 2.0 - lam
        if two_minus_lam == 0.0:
            return -log(-x + 1.0)
        return -(exp(two_minus_lam * log(-x + 1.0)) - 1.0) / two_minus_lam


fn feature_cross(x: Float64, y: Float64, degree: Float64) -> Float64:
    """Polynomial feature cross: x^a × y^b, simplified as (x×y)^(degree/2).

    Args:
        x: First feature.
        y: Second feature.
        degree: Polynomial degree.

    Returns:
        Feature cross value.
    """
    var product = x * y
    if degree == 2.0:
        return product
    if product <= 0.0 and degree != Float64(Int64(degree)):
        return 0.0
    return exp(degree / 2.0 * log(product if product > 0.0 else 1e-300))


fn quantile_rank(
    x: Float64, sorted_sum_below: Float64, total: Float64
) -> Float64:
    """Percentile rank: fraction of values ≤ x.

    Args:
        x: Value (unused here — rank based on count below).
        sorted_sum_below: Count of observations ≤ x.
        total: Total observations.

    Returns:
        Percentile rank (0–1).
    """
    if total <= 0.0:
        return 0.0
    return sorted_sum_below / total


fn target_encode_smooth(
    category_mean: Float64, global_mean: Float64,
    category_count: Float64, smoothing: Float64
) -> Float64:
    """Bayesian smoothed target encoding.

    encoded = (count × cat_mean + smoothing × global_mean) / (count + smoothing)

    Args:
        category_mean: Mean target for this category.
        global_mean: Overall mean target.
        category_count: Number of samples in this category.
        smoothing: Smoothing strength (1–100 typical).

    Returns:
        Smoothed target encoding.
    """
    var denom = category_count + smoothing
    if denom <= 0.0:
        return global_mean
    return (category_count * category_mean + smoothing * global_mean) / denom


fn binning_equal_width(
    x: Float64, x_min: Float64, x_max: Float64, n_bins: Float64
) -> Float64:
    """Equal-width binning: bin index for value x.

    Args:
        x: Input value.
        x_min: Feature minimum.
        x_max: Feature maximum.
        n_bins: Number of bins.

    Returns:
        Bin index (0 to n_bins-1).
    """
    var rng = x_max - x_min
    if rng <= 0.0 or n_bins <= 0.0:
        return 0.0
    var bin = Float64(Int64((x - x_min) / rng * n_bins))
    if bin >= n_bins:
        return n_bins - 1.0
    if bin < 0.0:
        return 0.0
    return bin
