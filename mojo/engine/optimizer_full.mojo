"""
optimizer_full.mojo — Complete optimizer stack: LBFGS, Adadelta, Nadam, Sophia, Prodigy.
Zero Python imports.

Public API:
  lbfgs_two_loop_scale           — L-BFGS two-loop recursion scale
  adadelta_update                — Adadelta parameter update
  nadam_update                   — Nadam (Adam + Nesterov) update
  sophia_hessian_clip            — Sophia Hessian diagonal clipping
  sophia_update                  — Sophia optimizer update
  prodigy_d_estimate             — Prodigy learning rate estimator
  adan_update                    — Adan (adaptive Nesterov) update
  schedule_free_update           — schedule-free SGD update
  muon_orthogonal_update         — Muon optimizer step
  gradient_centralization        — gradient centralization projection
"""
from std.math import sqrt, log, exp


fn lbfgs_two_loop_scale(
    s_dot_y: Float64, y_dot_y: Float64
) -> Float64:
    """L-BFGS initial Hessian scaling: H₀ = (sᵀy)/(yᵀy) × I.

    Args:
        s_dot_y: Dot product s · y (curvature pair).
        y_dot_y: Dot product y · y.

    Returns:
        Initial Hessian scale factor.
    """
    if y_dot_y <= 0.0:
        return 1.0
    return s_dot_y / y_dot_y


fn adadelta_update(
    param: Float64, gradient: Float64,
    eg2: Float64, edx2: Float64,
    rho: Float64, eps: Float64
) -> Float64:
    """Adadelta parameter update.

    E[g²] = ρE[g²] + (1-ρ)g²
    Δx = -sqrt(E[Δx²]+ε) / sqrt(E[g²]+ε) × g

    Args:
        param: Current parameter.
        gradient: Current gradient.
        eg2: Running average of squared gradients.
        edx2: Running average of squared updates.
        rho: Decay rate (0.95 typical).
        eps: Stability epsilon.

    Returns:
        Updated parameter.
    """
    var new_eg2 = rho * eg2 + (1.0 - rho) * gradient * gradient
    var delta = -sqrt(edx2 + eps) / sqrt(new_eg2 + eps) * gradient
    return param + delta


fn nadam_update(
    param: Float64, m_hat: Float64, v_hat: Float64,
    gradient: Float64, beta1: Float64, lr: Float64, eps: Float64
) -> Float64:
    """Nadam (Nesterov Adam) parameter update.

    θ -= lr × (β₁m̂ + (1-β₁)g/...) / (√v̂ + ε)

    Args:
        param: Current parameter.
        m_hat: Bias-corrected first moment.
        v_hat: Bias-corrected second moment.
        gradient: Current gradient.
        beta1: First moment decay.
        lr: Learning rate.
        eps: Stability epsilon.

    Returns:
        Updated parameter.
    """
    var nesterov_m = beta1 * m_hat + (1.0 - beta1) * gradient
    return param - lr * nesterov_m / (sqrt(v_hat) + eps)


fn sophia_hessian_clip(
    h_diag: Float64, rho: Float64
) -> Float64:
    """Sophia Hessian diagonal clipping.

    h_clipped = max(h, ρ)

    Args:
        h_diag: Estimated Hessian diagonal element.
        rho: Clipping threshold (ensures positive curvature).

    Returns:
        Clipped Hessian diagonal.
    """
    if h_diag < rho:
        return rho
    return h_diag


fn sophia_update(
    param: Float64, gradient: Float64, h_diag: Float64,
    lr: Float64, rho: Float64, weight_decay: Float64
) -> Float64:
    """Sophia optimizer update (Liu et al. 2023).

    θ -= lr × g / max(h, ρ) + weight_decay × θ

    Args:
        param: Current parameter.
        gradient: Current gradient.
        h_diag: Hessian diagonal estimate.
        lr: Learning rate.
        rho: Hessian clipping threshold.
        weight_decay: Weight decay λ.

    Returns:
        Updated parameter.
    """
    var h_clip = sophia_hessian_clip(h_diag, rho)
    return param - lr * gradient / h_clip - lr * weight_decay * param


fn prodigy_d_estimate(
    s: Float64, g_sq_sum: Float64,
    d_prev: Float64, beta3: Float64
) -> Float64:
    """Prodigy adaptive learning rate d estimate.

    d = (s · g_sum) / (Σ||g||²) estimate update.

    Simplified: d_new = max(d_prev, s / sqrt(g_sq_sum + 1))

    Args:
        s: Numerator signal (gradient × step).
        g_sq_sum: Accumulated squared gradient sum.
        d_prev: Previous d estimate.
        beta3: Smoothing for d estimate.

    Returns:
        Updated d estimate.
    """
    if g_sq_sum <= 0.0:
        return d_prev
    var d_candidate = s / sqrt(g_sq_sum + 1.0)
    if d_candidate > d_prev:
        return d_candidate
    return d_prev


fn adan_update(
    param: Float64, m: Float64, v: Float64, n: Float64,
    gradient: Float64, prev_gradient: Float64,
    beta1: Float64, beta2: Float64, beta3: Float64,
    lr: Float64, eps: Float64
) -> Float64:
    """Adan (Adaptive Nesterov Momentum) update.

    m = β₁m + (1-β₁)g
    v = β₂v + (1-β₂)(g - g_prev)
    n = β₃n + (1-β₃)(g + (1-β₂)(g-g_prev))²

    θ -= lr × (m + (1-β₂)v) / (√n + ε)

    Args:
        param: Current parameter.
        m: First moment.
        v: Gradient difference moment.
        n: Second moment (adapted).
        gradient: Current gradient.
        prev_gradient: Previous gradient.
        beta1, beta2, beta3: Adan momentum coefficients.
        lr: Learning rate.
        eps: Stability epsilon.

    Returns:
        Updated parameter.
    """
    var g_diff = gradient - prev_gradient
    var new_m = beta1 * m + (1.0 - beta1) * gradient
    var new_v = beta2 * v + (1.0 - beta2) * g_diff
    var combined_g = gradient + (1.0 - beta2) * g_diff
    var new_n = beta3 * n + (1.0 - beta3) * combined_g * combined_g
    return param - lr * (new_m + (1.0 - beta2) * new_v) / (sqrt(new_n) + eps)


fn schedule_free_update(
    x: Float64, z: Float64, gradient: Float64,
    lr: Float64, beta: Float64, weight_decay: Float64
) -> Float64:
    """Schedule-free SGD (Defazio 2024).

    z_{t+1} = z_t - lr × ∇f(y_t)
    x_{t+1} = (1-β) z_{t+1} + β x_t

    Args:
        x: EMA parameter (evaluation point).
        z: SGD parameter (update point).
        gradient: Gradient at y_t (interpolated point).
        lr: Learning rate.
        beta: Schedule-free momentum (0.9 typical).
        weight_decay: Weight decay.

    Returns:
        Updated x (evaluation parameter).
    """
    var z_new = z - lr * gradient - lr * weight_decay * z
    return (1.0 - beta) * z_new + beta * x


fn muon_orthogonal_update(
    param: Float64, gradient: Float64, momentum: Float64,
    projection: Float64, lr: Float64, mu: Float64
) -> Float64:
    """Muon optimizer: orthogonalize gradient via Newton-Schulz.

    Applies SGD with Nesterov momentum to orthogonalized gradient.
    projection = orthogonalized gradient component.

    Args:
        param: Current parameter.
        gradient: Raw gradient.
        momentum: Momentum buffer.
        projection: Orthogonalized gradient element.
        lr: Learning rate.
        mu: Momentum coefficient.

    Returns:
        Updated parameter.
    """
    var new_m = mu * momentum + projection
    var nesterov_g = mu * new_m + projection
    return param - lr * nesterov_g


fn gradient_centralization(
    gradient: Float64, gradient_mean: Float64
) -> Float64:
    """Gradient centralization: project gradient to have zero mean.

    g_centralized = g - mean(g)

    Args:
        gradient: Gradient element.
        gradient_mean: Mean of gradients across output dimension.

    Returns:
        Centralized gradient element.
    """
    return gradient - gradient_mean
