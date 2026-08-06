"""
state_space_models.mojo — SSM / Mamba / S4 recurrence calculations.
Zero Python imports.

Public API:
  ssm_discretize_zoh             — ZOH discretisation of A matrix element
  ssm_discretize_b               — ZOH discretised B element
  ssm_recurrence_step            — linear recurrence: h = Ā h + B̄ x
  ssm_output_step                — SSM output: y = C h
  mamba_selective_scan_step      — Mamba selective state update
  mamba_delta_softplus           — softplus-activated Δ (timestep)
  hippo_legt_update              — HiPPO-LegT coefficient update
  s4_kernel_element              — S4 convolution kernel element estimate
  ssm_shift_register_step        — simple shift-register SSM step
  retnet_decay                   — RetNet exponential decay factor
"""
from std.math import sqrt, log, exp


def ssm_discretize_zoh(a: Float64, delta: Float64) -> Float64:
    """Zero-order hold discretisation of SSM A matrix element.

    Ā = exp(Δ × A)

    Args:
        a: Continuous A matrix element (negative for stability).
        delta: Timestep Δ.

    Returns:
        Discretised Ā element.
    """
    return exp(delta * a)


def ssm_discretize_b(
    a: Float64, b: Float64, delta: Float64
) -> Float64:
    """ZOH discretised B element.

    B̄ = (Ā - I) × A^{-1} × B ≈ Δ × B  (first-order approx)

    Args:
        a: Continuous A element.
        b: Continuous B element.
        delta: Timestep Δ.

    Returns:
        Discretised B̄ element.
    """
    if a == 0.0:
        return delta * b
    var a_bar = exp(delta * a)
    return (a_bar - 1.0) / a * b


def ssm_recurrence_step(
    h_prev: Float64, a_bar: Float64, b_bar: Float64, x: Float64
) -> Float64:
    """Linear SSM recurrence: h_t = Ā h_{t-1} + B̄ x_t.

    Args:
        h_prev: Previous hidden state.
        a_bar: Discretised A element.
        b_bar: Discretised B element.
        x: Input at current timestep.

    Returns:
        Updated hidden state h_t.
    """
    return a_bar * h_prev + b_bar * x


def ssm_output_step(c: Float64, h: Float64) -> Float64:
    """SSM output projection: y = C h (single element).

    Args:
        c: C matrix element.
        h: Hidden state element.

    Returns:
        Output contribution.
    """
    return c * h


def mamba_selective_scan_step(
    h_prev: Float64, a: Float64, b: Float64,
    x: Float64, delta: Float64
) -> Float64:
    """Mamba selective state space scan step.

    Ā = exp(Δ A),  B̄ = Δ B
    h_t = Ā h_{t-1} + B̄ x_t

    Args:
        h_prev: Previous state.
        a: A parameter (fixed, negative).
        b: Input-dependent B (from B projection of x).
        x: Input value.
        delta: Input-dependent timestep Δ.

    Returns:
        Updated state h_t.
    """
    var a_bar = exp(delta * a)
    var b_bar = delta * b
    return a_bar * h_prev + b_bar * x


def mamba_delta_softplus(delta_raw: Float64) -> Float64:
    """Softplus activation for Mamba's Δ (ensures Δ > 0).

    softplus(x) = log(1 + exp(x))

    Args:
        delta_raw: Raw Δ before activation.

    Returns:
        Positive timestep Δ.
    """
    return log(1.0 + exp(delta_raw))


def hippo_legt_update(
    h_n: Float64, h_prev_n: Float64,
    x: Float64, n: Float64, t: Float64
) -> Float64:
    """HiPPO-LegT coefficient update (approximation).

    Simplified recurrence for Legendre polynomial coefficient n.

    Args:
        h_n: Current coefficient n.
        h_prev_n: Previous timestep coefficient n.
        x: Input signal.
        n: Polynomial order.
        t: Current time (window size θ).

    Returns:
        Updated coefficient.
    """
    if t <= 0.0:
        return h_n
    var a_nn = (2.0 * n + 1.0) / t
    return h_n - a_nn * h_n + (2.0 * n + 1.0) / t * x


def s4_kernel_element(
    c: Float64, a_power: Float64, b: Float64
) -> Float64:
    """S4 convolution kernel element: K_l = C A^l B.

    Args:
        c: C matrix element.
        a_power: A^l matrix element (power of A at lag l).
        b: B matrix element.

    Returns:
        Kernel value at lag l.
    """
    return c * a_power * b


def ssm_shift_register_step(
    state: Float64, decay: Float64, input_val: Float64
) -> Float64:
    """Simple exponential decay shift-register SSM step.

    h_t = decay × h_{t-1} + input

    Args:
        state: Previous hidden state.
        decay: Decay factor (0 < decay < 1).
        input_val: Current input.

    Returns:
        Updated state.
    """
    return decay * state + input_val


def retnet_decay(
    dim: Float64, n_dims: Float64
) -> Float64:
    """RetNet exponential decay factor γ for dimension d.

    γ_d = 1 - exp(-5 - 8d/D)   (Sun et al. 2023)

    Args:
        dim: Dimension index.
        n_dims: Total retention heads / dimensions.

    Returns:
        Decay factor γ_d (close to 1).
    """
    if n_dims <= 0.0:
        return 0.9
    return 1.0 - exp(-5.0 - 8.0 * dim / n_dims)
