"""
autograd_ops.mojo — Automatic differentiation gradient primitives.
Zero Python imports.

Public API:
  grad_add                       — ∂/∂x of x + y = 1
  grad_mul                       — ∂/∂x of x × y = y
  grad_exp                       — ∂/∂x of exp(x) = exp(x)
  grad_log                       — ∂/∂x of log(x) = 1/x
  grad_relu                      — ∂/∂x of ReLU(x)
  grad_sigmoid                   — ∂/∂x of sigmoid(x)
  grad_tanh                      — ∂/∂x of tanh(x)
  grad_pow                       — ∂/∂x of x^n = n x^(n-1)
  chain_rule                     — chain rule: ∂L/∂x = ∂L/∂y × ∂y/∂x
  grad_softmax_diag              — diagonal of softmax Jacobian
"""
from std.math import sqrt, log, exp


fn grad_add(upstream: Float64) -> Float64:
    """Gradient of addition w.r.t. either input: ∂(x+y)/∂x = 1.

    Args:
        upstream: Upstream gradient ∂L/∂(x+y).

    Returns:
        Local gradient ∂L/∂x = upstream.
    """
    return upstream


fn grad_mul(other: Float64, upstream: Float64) -> Float64:
    """Gradient of multiplication w.r.t. x: ∂(x×y)/∂x = y.

    Args:
        other: The other operand value (y).
        upstream: Upstream gradient ∂L/∂(x×y).

    Returns:
        Local gradient ∂L/∂x = y × upstream.
    """
    return other * upstream


fn grad_exp(x: Float64, upstream: Float64) -> Float64:
    """Gradient of exp: ∂exp(x)/∂x = exp(x).

    Args:
        x: Forward pass input.
        upstream: Upstream gradient.

    Returns:
        Local gradient.
    """
    return exp(x) * upstream


fn grad_log(x: Float64, upstream: Float64) -> Float64:
    """Gradient of log: ∂log(x)/∂x = 1/x.

    Args:
        x: Forward pass input (must be > 0).
        upstream: Upstream gradient.

    Returns:
        Local gradient.
    """
    if x <= 0.0:
        return 0.0
    return upstream / x


fn grad_relu(x: Float64, upstream: Float64) -> Float64:
    """Gradient of ReLU: ∂ReLU(x)/∂x = 1 if x > 0 else 0.

    Args:
        x: Forward pass input.
        upstream: Upstream gradient.

    Returns:
        Local gradient.
    """
    if x > 0.0:
        return upstream
    return 0.0


fn grad_sigmoid(sigmoid_out: Float64, upstream: Float64) -> Float64:
    """Gradient of sigmoid: ∂σ(x)/∂x = σ(x)(1 - σ(x)).

    Args:
        sigmoid_out: σ(x) from forward pass.
        upstream: Upstream gradient.

    Returns:
        Local gradient.
    """
    return sigmoid_out * (1.0 - sigmoid_out) * upstream


fn grad_tanh(tanh_out: Float64, upstream: Float64) -> Float64:
    """Gradient of tanh: ∂tanh(x)/∂x = 1 - tanh²(x).

    Args:
        tanh_out: tanh(x) from forward pass.
        upstream: Upstream gradient.

    Returns:
        Local gradient.
    """
    return (1.0 - tanh_out * tanh_out) * upstream


fn grad_pow(x: Float64, n: Float64, upstream: Float64) -> Float64:
    """Gradient of x^n: ∂x^n/∂x = n × x^(n-1).

    Args:
        x: Base value from forward pass.
        n: Exponent.
        upstream: Upstream gradient.

    Returns:
        Local gradient.
    """
    if x == 0.0 and n < 1.0:
        return 0.0
    return n * exp((n - 1.0) * log(x if x > 0.0 else 1e-300)) * upstream


fn chain_rule(upstream: Float64, local_grad: Float64) -> Float64:
    """Chain rule: ∂L/∂x = ∂L/∂y × ∂y/∂x.

    Args:
        upstream: ∂L/∂y (gradient from above).
        local_grad: ∂y/∂x (local Jacobian element).

    Returns:
        ∂L/∂x.
    """
    return upstream * local_grad


fn grad_softmax_diag(softmax_i: Float64, upstream: Float64) -> Float64:
    """Diagonal of softmax Jacobian: ∂s_i/∂z_i = s_i(1 - s_i).

    For the diagonal contribution in a softmax backward pass.

    Args:
        softmax_i: Softmax output s_i from forward pass.
        upstream: Upstream gradient ∂L/∂s_i.

    Returns:
        Diagonal gradient contribution.
    """
    return softmax_i * (1.0 - softmax_i) * upstream
