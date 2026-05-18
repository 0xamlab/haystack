"""
scipy_optimize_ops.mojo — Numerical optimisation primitives (scipy.optimize).
Zero Python imports.

Public API:
  bfgs_hessian_update_term       — BFGS inverse Hessian update scalar
  conjugate_gradient_beta_fr     — Fletcher-Reeves CG direction update
  conjugate_gradient_beta_pr     — Polak-Ribière CG direction update
  armijo_condition               — Armijo sufficient decrease condition
  wolfe_curvature_condition      — Wolfe curvature condition
  golden_section_midpoint        — golden-section search midpoint
  newton_step                    — Newton-Raphson step
  secant_step                    — Secant method step
  bisection_midpoint             — bisection method midpoint
  trust_region_step_norm         — trust-region step norm estimate
"""
from std.math import sqrt, log, exp


fn bfgs_hessian_update_term(
    s: Float64, y: Float64, sy_dot: Float64
) -> Float64:
    """BFGS inverse Hessian rank-1 update scalar.

    ρ = 1 / (s · y)
    H_new = (I - ρ s yᵀ) H (I - ρ y sᵀ) + ρ s sᵀ

    This returns ρ for use in the update.

    Args:
        s: Step vector element s_k = x_{k+1} - x_k.
        y: Gradient difference element y_k = ∇f_{k+1} - ∇f_k.
        sy_dot: Dot product s · y.

    Returns:
        ρ = 1 / (s · y) if sy_dot > 0, else 0.
    """
    if sy_dot <= 0.0:
        return 0.0
    return 1.0 / sy_dot


fn conjugate_gradient_beta_fr(
    grad_norm_sq_new: Float64, grad_norm_sq_old: Float64
) -> Float64:
    """Fletcher-Reeves CG β coefficient.

    β_FR = ||∇f_new||² / ||∇f_old||²

    Args:
        grad_norm_sq_new: Squared gradient norm at new iterate.
        grad_norm_sq_old: Squared gradient norm at previous iterate.

    Returns:
        β_FR coefficient.
    """
    if grad_norm_sq_old <= 0.0:
        return 0.0
    return grad_norm_sq_new / grad_norm_sq_old


fn conjugate_gradient_beta_pr(
    grad_new: Float64, grad_old: Float64, grad_norm_sq_old: Float64
) -> Float64:
    """Polak-Ribière CG β coefficient (one dimension contribution).

    β_PR = ∇f_new · (∇f_new - ∇f_old) / ||∇f_old||²

    This is the per-element numerator; caller sums across dims.

    Args:
        grad_new: Gradient element at new iterate.
        grad_old: Gradient element at previous iterate.
        grad_norm_sq_old: Squared norm of old gradient.

    Returns:
        Per-element numerator contribution.
    """
    if grad_norm_sq_old <= 0.0:
        return 0.0
    return grad_new * (grad_new - grad_old) / grad_norm_sq_old


fn armijo_condition(
    f_new: Float64, f_old: Float64, alpha: Float64,
    grad_dot_dir: Float64, c1: Float64
) -> Float64:
    """Armijo sufficient decrease condition check.

    Returns positive if condition satisfied: f(x + αd) ≤ f(x) + c1 α ∇f·d

    Args:
        f_new: Function value at new point.
        f_old: Function value at old point.
        alpha: Step size.
        grad_dot_dir: Dot product ∇f · d.
        c1: Armijo parameter (1e-4 typical).

    Returns:
        1.0 if satisfied, 0.0 otherwise.
    """
    if f_new <= f_old + c1 * alpha * grad_dot_dir:
        return 1.0
    return 0.0


fn wolfe_curvature_condition(
    grad_new_dot_dir: Float64, grad_old_dot_dir: Float64, c2: Float64
) -> Float64:
    """Wolfe curvature condition: |∇f_new · d| ≤ c2 |∇f_old · d|.

    Args:
        grad_new_dot_dir: ∇f(x+αd) · d.
        grad_old_dot_dir: ∇f(x) · d.
        c2: Wolfe parameter (0.9 typical).

    Returns:
        1.0 if condition satisfied, 0.0 otherwise.
    """
    var lhs = grad_new_dot_dir
    if lhs < 0.0:
        lhs = -lhs
    var rhs = c2 * grad_old_dot_dir
    if rhs < 0.0:
        rhs = -rhs
    if lhs <= rhs:
        return 1.0
    return 0.0


fn golden_section_midpoint(a: Float64, b: Float64, use_left: Float64) -> Float64:
    """Golden-section search: interior point.

    φ = (√5 - 1) / 2 ≈ 0.618

    Args:
        a: Left bracket.
        b: Right bracket.
        use_left: 1.0 → left interior point, 0.0 → right.

    Returns:
        Interior evaluation point.
    """
    var phi = 0.6180339887498949
    if use_left > 0.5:
        return b - phi * (b - a)
    return a + phi * (b - a)


fn newton_step(f_val: Float64, f_prime: Float64) -> Float64:
    """Newton-Raphson step: x_new = x - f(x) / f'(x).

    Returns the step size -f/f' (caller adds to x).

    Args:
        f_val: Function value f(x).
        f_prime: Derivative f'(x).

    Returns:
        Newton step Δx.
    """
    if f_prime == 0.0:
        return 0.0
    return -f_val / f_prime


fn secant_step(
    x0: Float64, x1: Float64, f0: Float64, f1: Float64
) -> Float64:
    """Secant method step.

    x2 = x1 - f1 × (x1 - x0) / (f1 - f0)

    Args:
        x0: Previous iterate.
        x1: Current iterate.
        f0: f(x0).
        f1: f(x1).

    Returns:
        Next iterate x2.
    """
    var df = f1 - f0
    if df == 0.0:
        return x1
    return x1 - f1 * (x1 - x0) / df


fn bisection_midpoint(a: Float64, b: Float64) -> Float64:
    """Bisection method midpoint.

    Args:
        a: Left bracket.
        b: Right bracket.

    Returns:
        Midpoint (a + b) / 2.
    """
    return (a + b) / 2.0


fn trust_region_step_norm(
    grad_norm: Float64, hessian_min_eig: Float64, delta: Float64
) -> Float64:
    """Trust-region Cauchy point step norm estimate.

    ||p_c|| = min(δ, ||g|| / B) where B ≈ Hessian curvature.

    Args:
        grad_norm: Gradient norm ||∇f||.
        hessian_min_eig: Minimum eigenvalue estimate of Hessian.
        delta: Trust-region radius.

    Returns:
        Cauchy step norm.
    """
    if hessian_min_eig <= 0.0:
        return delta
    var cauchy = grad_norm / hessian_min_eig
    if cauchy > delta:
        return delta
    return cauchy
