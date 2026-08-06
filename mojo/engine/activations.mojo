"""
activations.mojo — Neural network activation functions. Zero Python imports.

Public API:
  gelu                          — Gaussian Error Linear Unit
  gelu_fast                     — tanh approximation of GELU
  swish                         — Swish / SiLU activation
  swiglu                        — SwiGLU gate (Shazeer 2020)
  mish                          — Mish activation
  elu                           — Exponential Linear Unit
  selu                          — Scaled ELU (self-normalising)
  hard_swish                    — MobileNet hard approximation
  gelu_new                      — GPT-2 exact GELU
  relu6                         — ReLU capped at 6
"""
from std.math import exp, log, sqrt, tanh


def gelu(x: Float64) -> Float64:
    """Gaussian Error Linear Unit (exact): x × Φ(x).

    GELU(x) = x × 0.5 × (1 + erf(x/√2))
    Approximated as x × sigmoid(1.702 × x).

    Args:
        x: Input activation.

    Returns:
        GELU output.
    """
    return x * 0.5 * (1.0 + tanh(0.7978845608 * (x + 0.044715 * x * x * x)))


def gelu_fast(x: Float64) -> Float64:
    """Fast tanh-approximated GELU.

    GELU_fast(x) = 0.5x × (1 + tanh(√(2/π) × (x + 0.044715x³)))

    Args:
        x: Input.

    Returns:
        Approximate GELU.
    """
    var inner = 0.7978845608028654 * (x + 0.044715 * x * x * x)
    return 0.5 * x * (1.0 + tanh(inner))


def swish(x: Float64) -> Float64:
    """Swish / SiLU activation: x × sigmoid(x).

    Args:
        x: Input.

    Returns:
        Swish output.
    """
    return x / (1.0 + exp(-x))


def swiglu(x: Float64, gate: Float64) -> Float64:
    """SwiGLU gated activation (Shazeer 2020).

    SwiGLU(x, gate) = Swish(gate) × x

    Args:
        x: Value branch.
        gate: Gate branch (passed through Swish).

    Returns:
        SwiGLU output.
    """
    return swish(gate) * x


def mish(x: Float64) -> Float64:
    """Mish activation: x × tanh(softplus(x)).

    softplus(x) = log(1 + exp(x))

    Args:
        x: Input.

    Returns:
        Mish output.
    """
    var sp = log(1.0 + exp(x))
    return x * tanh(sp)


def elu(x: Float64, alpha: Float64) -> Float64:
    """Exponential Linear Unit: x if x>0, alpha×(exp(x)-1) otherwise.

    Args:
        x: Input.
        alpha: ELU alpha parameter (typically 1.0).

    Returns:
        ELU output.
    """
    if x >= 0.0:
        return x
    return alpha * (exp(x) - 1.0)


def selu(x: Float64) -> Float64:
    """Scaled ELU (self-normalising networks, Klambauer 2017).

    SELU(x) = λ × (x if x>0 else α(exp(x)-1))
    λ = 1.0507, α = 1.6733

    Args:
        x: Input.

    Returns:
        SELU output.
    """
    var alpha = 1.6732632423543772
    var scale = 1.0507009873554805
    if x >= 0.0:
        return scale * x
    return scale * alpha * (exp(x) - 1.0)


def hard_swish(x: Float64) -> Float64:
    """Hard Swish (MobileNetV3): x × ReLU6(x+3) / 6.

    Args:
        x: Input.

    Returns:
        Hard swish output.
    """
    var relu6_xp3 = x + 3.0
    if relu6_xp3 <= 0.0:
        relu6_xp3 = 0.0
    if relu6_xp3 >= 6.0:
        relu6_xp3 = 6.0
    return x * relu6_xp3 / 6.0


def gelu_new(x: Float64) -> Float64:
    """GPT-2 / BERT exact GELU approximation.

    Same as gelu_fast but named separately for the GPT-2 variant.

    Args:
        x: Input.

    Returns:
        GELU_new output.
    """
    var cdf = 0.5 * (1.0 + tanh(0.7978845608028654 * x * (1.0 + 0.044715 * x * x)))
    return x * cdf


def relu6(x: Float64) -> Float64:
    """ReLU6: min(max(0, x), 6).

    Args:
        x: Input.

    Returns:
        ReLU6 output (in [0, 6]).
    """
    if x <= 0.0:
        return 0.0
    if x >= 6.0:
        return 6.0
    return x
