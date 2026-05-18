"""
online_learning.mojo — Streaming / online learning update primitives.
Zero Python imports.

Public API:
  exponential_moving_average     — EMA update
  exponential_moving_variance    — EMA variance (Welford-like)
  river_sgd_update               — online SGD (River / Vowpal Wabbit style)
  perceptron_update              — online Perceptron weight update
  passive_aggressive_step        — PA-I update step size
  adagrad_online_update          — online AdaGrad accumulator update
  ftrl_step                      — FTRL-Proximal z/n update
  streaming_mean_update          — Welford streaming mean
  streaming_variance_update      — Welford streaming variance
  concept_drift_ddm_error        — DDM drift detection error signal
"""
from std.math import sqrt, log, exp


fn exponential_moving_average(
    ema_prev: Float64, x: Float64, alpha: Float64
) -> Float64:
    """EMA update: EMA_t = α × x + (1-α) × EMA_{t-1}.

    Args:
        ema_prev: Previous EMA value.
        x: New observation.
        alpha: Smoothing factor (0 < α < 1).

    Returns:
        Updated EMA.
    """
    return alpha * x + (1.0 - alpha) * ema_prev


fn exponential_moving_variance(
    emv_prev: Float64, ema_prev: Float64,
    x: Float64, alpha: Float64
) -> Float64:
    """EMA variance: V_t = (1-α)(V_{t-1} + α(x - EMA_{t-1})²).

    Args:
        emv_prev: Previous EMA variance.
        ema_prev: Previous EMA (before this update).
        x: New observation.
        alpha: Smoothing factor.

    Returns:
        Updated EMA variance.
    """
    var diff = x - ema_prev
    return (1.0 - alpha) * (emv_prev + alpha * diff * diff)


fn river_sgd_update(
    weight: Float64, gradient: Float64, lr: Float64
) -> Float64:
    """Online SGD weight update (one sample at a time).

    w = w - lr × ∂L/∂w

    Args:
        weight: Current weight.
        gradient: Gradient from this sample.
        lr: Learning rate.

    Returns:
        Updated weight.
    """
    return weight - lr * gradient


fn perceptron_update(
    weight: Float64, x: Float64,
    y_true: Float64, y_pred: Float64, lr: Float64
) -> Float64:
    """Online Perceptron weight update.

    w += lr × (y_true - y_pred) × x

    Args:
        weight: Current weight.
        x: Feature value.
        y_true: True label.
        y_pred: Predicted label.
        lr: Learning rate.

    Returns:
        Updated weight.
    """
    return weight + lr * (y_true - y_pred) * x


fn passive_aggressive_step(
    loss: Float64, x_norm_sq: Float64, c: Float64
) -> Float64:
    """PA-I (Passive-Aggressive) update step size τ.

    τ = min(C, loss / ||x||²)

    Args:
        loss: Hinge loss for this sample.
        x_norm_sq: Squared L2 norm of feature vector.
        c: Aggressiveness parameter C.

    Returns:
        Step size τ.
    """
    if x_norm_sq <= 0.0:
        return 0.0
    var tau = loss / x_norm_sq
    if tau > c:
        return c
    return tau


fn adagrad_online_update(
    weight: Float64, gradient: Float64,
    accumulated_sq: Float64, lr: Float64, eps: Float64
) -> Float64:
    """Online AdaGrad update (single sample).

    G += g²;  w -= lr × g / sqrt(G + ε)

    Args:
        weight: Current weight.
        gradient: Gradient for this sample.
        accumulated_sq: Current accumulated squared gradients.
        lr: Learning rate.
        eps: Stability epsilon.

    Returns:
        Updated weight.
    """
    var new_acc = accumulated_sq + gradient * gradient
    return weight - lr * gradient / sqrt(new_acc + eps)


fn ftrl_step(
    z: Float64, n: Float64, alpha: Float64,
    beta: Float64, l1: Float64, l2: Float64
) -> Float64:
    """FTRL-Proximal weight from z, n accumulators.

    w_i = 0 if |z_i| < λ1 else -(z_i - sign(z_i)λ1) / (λ2 + (β+√n)/α)

    Args:
        z: FTRL z accumulator.
        n: FTRL n accumulator (sum of squared gradients).
        alpha: Learning rate.
        beta: FTRL beta parameter.
        l1: L1 regularisation.
        l2: L2 regularisation.

    Returns:
        Weight w.
    """
    var abs_z = z if z >= 0.0 else -z
    if abs_z <= l1:
        return 0.0
    var sign_z = 1.0 if z > 0.0 else -1.0
    var denom = l2 + (beta + sqrt(n)) / alpha
    if denom == 0.0:
        return 0.0
    return -(z - sign_z * l1) / denom


fn streaming_mean_update(
    mean: Float64, x: Float64, count: Float64
) -> Float64:
    """Welford streaming mean: μ_n = μ_{n-1} + (x - μ_{n-1}) / n.

    Args:
        mean: Current mean estimate.
        x: New observation.
        count: Count after including this observation.

    Returns:
        Updated mean.
    """
    if count <= 0.0:
        return x
    return mean + (x - mean) / count


fn streaming_variance_update(
    m2: Float64, old_mean: Float64, new_mean: Float64, x: Float64
) -> Float64:
    """Welford M2 update for streaming variance.

    M2 += (x - old_mean)(x - new_mean)

    Args:
        m2: Running M2 accumulator.
        old_mean: Mean before this observation.
        new_mean: Mean after this observation.
        x: New observation.

    Returns:
        Updated M2.
    """
    return m2 + (x - old_mean) * (x - new_mean)


fn concept_drift_ddm_error(
    error_rate: Float64, std_error: Float64,
    min_error: Float64, min_std: Float64,
    warning_level: Float64, drift_level: Float64
) -> Float64:
    """Drift Detection Method (DDM) alert level.

    Returns 0 = normal, 1 = warning, 2 = drift.

    Args:
        error_rate: Current error rate p_i.
        std_error: Standard deviation s_i = sqrt(p_i(1-p_i)/n).
        min_error: Historical minimum p_min.
        min_std: Historical std at minimum p_min + s_min.
        warning_level: Warning threshold multiplier (2.0 typical).
        drift_level: Drift threshold multiplier (3.0 typical).

    Returns:
        Alert level (0, 1, or 2).
    """
    var signal = error_rate + std_error
    var min_signal = min_error + min_std
    if signal > min_signal + drift_level * min_std:
        return 2.0
    if signal > min_signal + warning_level * min_std:
        return 1.0
    return 0.0
