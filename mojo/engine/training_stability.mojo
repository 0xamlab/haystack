"""
training_stability.mojo — Training stability: loss scaling, warmup, NaN guards, EMA.
Zero Python imports.

Public API:
  loss_scale_adjust              — dynamic loss scale update
  is_finite_check                — NaN/Inf guard for gradient
  gradient_accumulation_step     — accumulate gradients over steps
  warmup_lr_schedule             — linear warmup learning rate
  cosine_warmup_schedule         — warmup + cosine decay schedule
  ema_weight_update              — exponential moving average weights
  overflow_skip_step             — skip optimizer step on overflow
  grad_norm_finite               — check gradient norm is finite
  loss_spike_detector            — detect anomalous loss spikes
  training_step_budget           — Chinchilla compute budget check
"""
from std.math import sqrt, log, exp, cos


fn loss_scale_adjust(
    current_scale: Float64, overflow_occurred: Float64,
    scale_up_factor: Float64, scale_down_factor: Float64,
    growth_interval: Float64, steps_since_overflow: Float64
) -> Float64:
    """Dynamic loss scale adjustment (AMP).

    If overflow: scale /= scale_down_factor
    If no overflow for growth_interval steps: scale *= scale_up_factor

    Args:
        current_scale: Current loss scale.
        overflow_occurred: 1.0 if overflow detected this step.
        scale_up_factor: Multiply scale by this after stable interval.
        scale_down_factor: Divide scale by this after overflow.
        growth_interval: Steps between scale-up attempts.
        steps_since_overflow: Steps since last overflow.

    Returns:
        New loss scale.
    """
    if overflow_occurred > 0.5:
        return current_scale / scale_down_factor
    if steps_since_overflow >= growth_interval:
        return current_scale * scale_up_factor
    return current_scale


fn is_finite_check(value: Float64) -> Float64:
    """Check if value is finite (not NaN or Inf).

    Uses the property that NaN != NaN and |Inf| > any finite bound.

    Args:
        value: Value to check.

    Returns:
        1.0 if finite, 0.0 if NaN or Inf.
    """
    if value != value:  # NaN check
        return 0.0
    var abs_val = value if value >= 0.0 else -value
    if abs_val > 1e308:
        return 0.0
    return 1.0


fn gradient_accumulation_step(
    accumulated_grad: Float64, new_grad: Float64,
    accumulation_steps: Float64
) -> Float64:
    """Gradient accumulation: sum gradients over N micro-steps.

    Divides by accumulation_steps to match full-batch gradient.

    Args:
        accumulated_grad: Running gradient sum.
        new_grad: Gradient from current micro-batch.
        accumulation_steps: Total accumulation steps N.

    Returns:
        Updated accumulated gradient.
    """
    if accumulation_steps <= 0.0:
        return accumulated_grad + new_grad
    return accumulated_grad + new_grad / accumulation_steps


fn warmup_lr_schedule(
    step: Float64, warmup_steps: Float64, target_lr: Float64
) -> Float64:
    """Linear learning rate warmup.

    lr = target_lr × min(1, step / warmup_steps)

    Args:
        step: Current training step.
        warmup_steps: Steps to reach full learning rate.
        target_lr: Peak learning rate after warmup.

    Returns:
        Current learning rate.
    """
    if warmup_steps <= 0.0:
        return target_lr
    var ratio = step / warmup_steps
    if ratio > 1.0:
        return target_lr
    return target_lr * ratio


fn cosine_warmup_schedule(
    step: Float64, warmup_steps: Float64,
    total_steps: Float64, lr_max: Float64, lr_min: Float64
) -> Float64:
    """Warmup + cosine decay learning rate schedule.

    Args:
        step: Current training step.
        warmup_steps: Linear warmup period.
        total_steps: Total training steps.
        lr_max: Peak learning rate.
        lr_min: Minimum (final) learning rate.

    Returns:
        Current learning rate.
    """
    var pi = 3.141592653589793
    if step <= warmup_steps:
        if warmup_steps <= 0.0:
            return lr_max
        return lr_max * step / warmup_steps
    var decay_steps = total_steps - warmup_steps
    if decay_steps <= 0.0:
        return lr_min
    var t = step - warmup_steps
    return lr_min + 0.5 * (lr_max - lr_min) * (1.0 + cos(pi * t / decay_steps))


fn ema_weight_update(
    ema_param: Float64, model_param: Float64, decay: Float64
) -> Float64:
    """Exponential moving average of model weights (EMA model).

    ema = decay × ema + (1 - decay) × param

    Args:
        ema_param: EMA model parameter.
        model_param: Current training model parameter.
        decay: EMA decay (0.9999 typical for large models).

    Returns:
        Updated EMA parameter.
    """
    return decay * ema_param + (1.0 - decay) * model_param


fn overflow_skip_step(
    has_overflow: Float64, optimizer_step_count: Float64
) -> Float64:
    """Return updated step count, skipping if overflow occurred.

    Args:
        has_overflow: 1.0 if gradient overflow detected.
        optimizer_step_count: Current optimizer step count.

    Returns:
        New step count (unchanged if skipped).
    """
    if has_overflow > 0.5:
        return optimizer_step_count  # Skip this step
    return optimizer_step_count + 1.0


fn grad_norm_finite(
    grad_norm: Float64, max_allowed: Float64
) -> Float64:
    """Check gradient norm is finite and within reasonable range.

    Returns 1.0 if healthy, 0.0 if NaN/Inf/too large.

    Args:
        grad_norm: Computed gradient L2 norm.
        max_allowed: Maximum sane gradient norm.

    Returns:
        1.0 if gradient is healthy.
    """
    if grad_norm != grad_norm:  # NaN
        return 0.0
    if grad_norm > 1e8:  # Inf-like
        return 0.0
    if grad_norm > max_allowed:
        return 0.0
    return 1.0


fn loss_spike_detector(
    current_loss: Float64, running_mean: Float64,
    spike_threshold: Float64
) -> Float64:
    """Detect anomalous loss spikes relative to running mean.

    Returns 1.0 if spike detected (loss >> recent mean).

    Args:
        current_loss: Loss at current step.
        running_mean: EMA of recent losses.
        spike_threshold: Ratio threshold (e.g. 4.0 = 4× mean = spike).

    Returns:
        1.0 if loss spike detected.
    """
    if running_mean <= 0.0:
        return 0.0
    if current_loss / running_mean > spike_threshold:
        return 1.0
    return 0.0


fn training_step_budget(
    compute_budget_flops: Float64, flops_per_step: Float64
) -> Float64:
    """Remaining training steps within Chinchilla compute budget.

    Args:
        compute_budget_flops: Total FLOPs budget (e.g. 1e21).
        flops_per_step: FLOPs consumed per training step.

    Returns:
        Remaining training steps.
    """
    if flops_per_step <= 0.0:
        return 0.0
    return compute_budget_flops / flops_per_step
