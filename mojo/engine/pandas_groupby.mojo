"""
pandas_groupby.mojo — GroupBy aggregation arithmetic primitives.
Zero Python imports.

Public API:
  group_mean_update              — Welford online mean update
  group_variance_update          — Welford online variance update
  group_min_update               — running group minimum
  group_max_update               — running group maximum
  group_sum_update               — group cumulative sum
  group_count_update             — group count increment
  group_std_from_variance        — std from Welford variance
  weighted_group_mean            — weighted mean contribution
  group_median_approx            — P² median approximation update
  group_skewness_term            — skewness accumulation term
"""
from std.math import sqrt, log, exp


fn group_mean_update(
    current_mean: Float64, new_value: Float64, count: Float64
) -> Float64:
    """Welford online mean update: μ_n = μ_{n-1} + (x_n - μ_{n-1}) / n.

    Args:
        current_mean: Running mean before this observation.
        new_value: New data point.
        count: New count n (after including this point).

    Returns:
        Updated mean.
    """
    if count <= 0.0:
        return new_value
    return current_mean + (new_value - current_mean) / count


fn group_variance_update(
    current_m2: Float64, current_mean: Float64,
    new_value: Float64, new_mean: Float64
) -> Float64:
    """Welford online M2 (sum of squared deviations) update.

    M2 += (x - old_mean) × (x - new_mean)

    Args:
        current_m2: Running M2 accumulator.
        current_mean: Mean before this observation.
        new_value: New data point.
        new_mean: Updated mean after this observation.

    Returns:
        Updated M2.
    """
    return current_m2 + (new_value - current_mean) * (new_value - new_mean)


fn group_min_update(current_min: Float64, new_value: Float64) -> Float64:
    """Running minimum: min(current, new).

    Args:
        current_min: Current minimum.
        new_value: New observation.

    Returns:
        Updated minimum.
    """
    if new_value < current_min:
        return new_value
    return current_min


fn group_max_update(current_max: Float64, new_value: Float64) -> Float64:
    """Running maximum: max(current, new).

    Args:
        current_max: Current maximum.
        new_value: New observation.

    Returns:
        Updated maximum.
    """
    if new_value > current_max:
        return new_value
    return current_max


fn group_sum_update(current_sum: Float64, new_value: Float64) -> Float64:
    """Cumulative group sum.

    Args:
        current_sum: Running sum.
        new_value: New observation.

    Returns:
        Updated sum.
    """
    return current_sum + new_value


fn group_count_update(current_count: Float64) -> Float64:
    """Increment group element count.

    Args:
        current_count: Current element count.

    Returns:
        Incremented count.
    """
    return current_count + 1.0


fn group_std_from_variance(m2: Float64, count: Float64, ddof: Float64) -> Float64:
    """Standard deviation from Welford M2 accumulator.

    std = sqrt(M2 / (n - ddof))

    Args:
        m2: Welford M2 accumulator.
        count: Number of observations.
        ddof: Delta degrees of freedom (0=population, 1=sample).

    Returns:
        Standard deviation.
    """
    var denom = count - ddof
    if denom <= 0.0:
        return 0.0
    return sqrt(m2 / denom)


fn weighted_group_mean(
    weighted_sum: Float64, total_weight: Float64
) -> Float64:
    """Weighted mean from accumulated weighted sum.

    Args:
        weighted_sum: Σ w_i × x_i.
        total_weight: Σ w_i.

    Returns:
        Weighted mean.
    """
    if total_weight <= 0.0:
        return 0.0
    return weighted_sum / total_weight


fn group_median_approx(
    q: Float64, n: Float64, new_value: Float64
) -> Float64:
    """P² algorithm median estimate update (simplified incremental).

    Returns updated quantile estimate using linear interpolation step.

    Args:
        q: Current quantile estimate.
        n: Observations so far.
        new_value: New observation.

    Returns:
        Updated median estimate.
    """
    if n <= 0.0:
        return new_value
    var step = 1.0 / (n + 1.0)
    if new_value > q:
        return q + step
    if new_value < q:
        return q - step
    return q


fn group_skewness_term(
    x: Float64, mean: Float64, std: Float64
) -> Float64:
    """Per-observation contribution to skewness ((x-μ)/σ)³.

    Args:
        x: Observation.
        mean: Group mean.
        std: Group standard deviation.

    Returns:
        Cubed standardised value.
    """
    if std <= 0.0:
        return 0.0
    var z = (x - mean) / std
    return z * z * z
