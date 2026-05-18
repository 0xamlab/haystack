"""
gradient_descent.mojo — Optimizer update rules for ML training. Zero Python imports.

Public API:
  sgd_update                    — vanilla SGD step
  sgd_momentum_update           — SGD with momentum
  adam_update                   — Adam parameter update
  adamw_update                  — AdamW (decoupled weight decay)
  rmsprop_update                — RMSProp update
  adagrad_update                — AdaGrad accumulated update
  lars_update                   — LARS for large-batch training
  lion_update                   — Lion optimizer update
  gradient_clipping             — gradient norm clipping
  lr_cosine_schedule            — cosine annealing learning rate
"""
from std.math import sqrt, cos, exp, log


fn sgd_update(
    param: Float64, gradient: Float64, lr: Float64
) -> Float64:
    """Vanilla SGD parameter update: θ -= lr × ∇.

    Args:
        param: Current parameter value.
        gradient: Gradient.
        lr: Learning rate.

    Returns:
        Updated parameter.
    """
    return param - lr * gradient


fn sgd_momentum_update(
    param: Float64, velocity: Float64,
    gradient: Float64, lr: Float64, momentum: Float64
) -> Float64:
    """SGD with momentum: v = μv + g; θ -= lr × v.

    Args:
        param: Current parameter.
        velocity: Velocity term from previous step.
        gradient: Current gradient.
        lr: Learning rate.
        momentum: Momentum coefficient (0.9 typical).

    Returns:
        Updated parameter (caller must also update velocity = momentum×velocity + gradient).
    """
    var new_v = momentum * velocity + gradient
    return param - lr * new_v


fn adam_update(
    param: Float64, m_hat: Float64, v_hat: Float64,
    lr: Float64, eps: Float64
) -> Float64:
    """Adam parameter update (Kingma & Ba 2015).

    θ -= lr × m̂ / (√v̂ + ε)

    Args:
        param: Current parameter.
        m_hat: Bias-corrected first moment estimate.
        v_hat: Bias-corrected second moment estimate.
        lr: Learning rate.
        eps: Numerical stability (1e-8 typical).

    Returns:
        Updated parameter.
    """
    return param - lr * m_hat / (sqrt(v_hat) + eps)


fn adamw_update(
    param: Float64, m_hat: Float64, v_hat: Float64,
    lr: Float64, weight_decay: Float64, eps: Float64
) -> Float64:
    """AdamW (decoupled weight decay, Loshchilov & Hutter 2019).

    θ -= lr × (m̂ / (√v̂ + ε) + λ × θ)

    Args:
        param: Current parameter.
        m_hat: Bias-corrected first moment.
        v_hat: Bias-corrected second moment.
        lr: Learning rate.
        weight_decay: λ (0.01–0.1 typical).
        eps: Stability epsilon.

    Returns:
        Updated parameter.
    """
    return param - lr * (m_hat / (sqrt(v_hat) + eps) + weight_decay * param)


fn rmsprop_update(
    param: Float64, gradient: Float64,
    running_avg_sq: Float64, lr: Float64,
    decay: Float64, eps: Float64
) -> Float64:
    """RMSProp update.

    E[g²] = ρ E[g²] + (1-ρ)g²
    θ -= lr × g / sqrt(E[g²] + ε)

    Args:
        param: Current parameter.
        gradient: Current gradient.
        running_avg_sq: Running average of squared gradients.
        lr: Learning rate.
        decay: Decay rate ρ (0.9 typical).
        eps: Stability epsilon.

    Returns:
        Updated parameter.
    """
    var new_avg = decay * running_avg_sq + (1.0 - decay) * gradient * gradient
    return param - lr * gradient / sqrt(new_avg + eps)


fn adagrad_update(
    param: Float64, gradient: Float64,
    accumulated_sq: Float64, lr: Float64, eps: Float64
) -> Float64:
    """AdaGrad update.

    G += g²;  θ -= lr × g / sqrt(G + ε)

    Args:
        param: Current parameter.
        gradient: Current gradient.
        accumulated_sq: Sum of squared gradients so far.
        lr: Learning rate.
        eps: Stability epsilon.

    Returns:
        Updated parameter.
    """
    var new_acc = accumulated_sq + gradient * gradient
    return param - lr * gradient / sqrt(new_acc + eps)


fn lars_update(
    param: Float64, gradient: Float64, param_norm: Float64,
    grad_norm: Float64, lr: Float64,
    trust_coeff: Float64, weight_decay: Float64
) -> Float64:
    """LARS (Layer-wise Adaptive Rate Scaling) update.

    local_lr = trust_coeff × ||θ|| / (||g|| + λ||θ||)
    θ -= lr × local_lr × (g + λθ)

    Args:
        param: Current parameter.
        gradient: Current gradient.
        param_norm: L2 norm of parameter vector.
        grad_norm: L2 norm of gradient vector.
        lr: Global learning rate.
        trust_coeff: LARS trust coefficient η (0.001 typical).
        weight_decay: Weight decay λ.

    Returns:
        Updated parameter.
    """
    var denom = grad_norm + weight_decay * param_norm
    if denom <= 0.0:
        return param
    var local_lr = trust_coeff * param_norm / denom
    return param - lr * local_lr * (gradient + weight_decay * param)


fn lion_update(
    param: Float64, m: Float64, gradient: Float64,
    lr: Float64, beta1: Float64, beta2: Float64, weight_decay: Float64
) -> Float64:
    """Lion optimizer (Chen et al. 2023) update.

    c = sign(β₁m + (1-β₁)g)
    θ -= lr × (c + λθ)

    Args:
        param: Current parameter.
        m: Momentum from previous step.
        gradient: Current gradient.
        lr: Learning rate.
        beta1: First momentum coefficient (0.9 typical).
        beta2: Second coefficient for updating m (0.99 typical).
        weight_decay: λ.

    Returns:
        Updated parameter.
    """
    var c_val = beta1 * m + (1.0 - beta1) * gradient
    var sign_c = 1.0
    if c_val < 0.0:
        sign_c = -1.0
    elif c_val == 0.0:
        sign_c = 0.0
    return param - lr * (sign_c + weight_decay * param)


fn gradient_clipping(
    gradient: Float64, grad_norm: Float64, max_norm: Float64
) -> Float64:
    """Gradient clipping by global norm.

    g_clipped = g × max_norm / max(grad_norm, max_norm)

    Args:
        gradient: Individual gradient element.
        grad_norm: Global gradient norm across all params.
        max_norm: Maximum allowed gradient norm.

    Returns:
        Clipped gradient element.
    """
    if grad_norm <= max_norm:
        return gradient
    return gradient * max_norm / grad_norm


fn lr_cosine_schedule(
    step: Float64, total_steps: Float64,
    lr_max: Float64, lr_min: Float64
) -> Float64:
    """Cosine annealing learning rate schedule.

    lr(t) = lr_min + 0.5(lr_max - lr_min)(1 + cos(πt/T))

    Args:
        step: Current training step.
        total_steps: Total training steps T.
        lr_max: Peak learning rate.
        lr_min: Minimum (final) learning rate.

    Returns:
        Learning rate at this step.
    """
    var pi = 3.141592653589793
    if total_steps <= 0.0:
        return lr_min
    return lr_min + 0.5 * (lr_max - lr_min) * (1.0 + cos(pi * step / total_steps))
