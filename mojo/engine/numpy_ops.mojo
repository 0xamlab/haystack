"""
numpy_ops.mojo — NumPy-equivalent element-wise ufunc math operations.
Zero Python imports.

Public API:
  np_clip                        — element-wise clip
  np_log1p                       — log(1 + x) stable
  np_expm1                       — exp(x) - 1 stable
  np_sign                        — sign function
  np_heaviside                   — Heaviside step function
  np_sinc                        — sinc(x) = sin(πx)/(πx)
  np_logaddexp                   — log(exp(a) + exp(b)) stable
  np_hypot                       — sqrt(a² + b²)
  np_lerp                        — linear interpolation
  np_digitize_bin                — find bin index for value
"""
from std.math import sqrt, log, exp, sin, cos


def np_clip(x: Float64, x_min: Float64, x_max: Float64) -> Float64:
    """Element-wise clip: min(max(x, x_min), x_max).

    Args:
        x: Input value.
        x_min: Minimum bound.
        x_max: Maximum bound.

    Returns:
        Clipped value.
    """
    if x < x_min:
        return x_min
    if x > x_max:
        return x_max
    return x


def np_log1p(x: Float64) -> Float64:
    """Numerically stable log(1 + x).

    For |x| < 1e-4 uses Taylor expansion: x - x²/2 + x³/3.

    Args:
        x: Input (x > -1).

    Returns:
        log(1 + x).
    """
    if x <= -1.0:
        return -1e300
    if x > -1e-4 and x < 1e-4:
        return x - x * x / 2.0 + x * x * x / 3.0
    return log(1.0 + x)


def np_expm1(x: Float64) -> Float64:
    """Numerically stable exp(x) - 1.

    For |x| < 1e-4 uses Taylor: x + x²/2 + x³/6.

    Args:
        x: Input.

    Returns:
        exp(x) - 1.
    """
    if x > -1e-4 and x < 1e-4:
        return x + x * x / 2.0 + x * x * x / 6.0
    return exp(x) - 1.0


def np_sign(x: Float64) -> Float64:
    """Sign function: -1, 0, or +1.

    Args:
        x: Input.

    Returns:
        Sign of x.
    """
    if x > 0.0:
        return 1.0
    if x < 0.0:
        return -1.0
    return 0.0


def np_heaviside(x: Float64, at_zero: Float64) -> Float64:
    """Heaviside step function.

    H(x) = 0 if x < 0, at_zero if x == 0, 1 if x > 0.

    Args:
        x: Input.
        at_zero: Value when x = 0 (0.5 typical).

    Returns:
        Heaviside value.
    """
    if x < 0.0:
        return 0.0
    if x == 0.0:
        return at_zero
    return 1.0


def np_sinc(x: Float64) -> Float64:
    """Normalised sinc: sin(πx) / (πx), with sinc(0) = 1.

    Args:
        x: Input.

    Returns:
        sinc(x).
    """
    var pi = 3.141592653589793
    if x == 0.0:
        return 1.0
    var pix = pi * x
    return sin(pix) / pix


def np_logaddexp(a: Float64, b: Float64) -> Float64:
    """log(exp(a) + exp(b)) computed stably.

    log(exp(a) + exp(b)) = max(a,b) + log(1 + exp(-|a-b|))

    Args:
        a: First log-space value.
        b: Second log-space value.

    Returns:
        Stable log-sum-exp.
    """
    var m = a
    if b > a:
        m = b
    return m + np_log1p(exp(-( (a - b) if a >= b else (b - a) )))


def np_hypot(a: Float64, b: Float64) -> Float64:
    """Hypotenuse: sqrt(a² + b²).

    Args:
        a: First leg.
        b: Second leg.

    Returns:
        Hypotenuse length.
    """
    return sqrt(a * a + b * b)


def np_lerp(a: Float64, b: Float64, t: Float64) -> Float64:
    """Linear interpolation: a + t × (b - a).

    Args:
        a: Start value.
        b: End value.
        t: Interpolation factor (0–1).

    Returns:
        Interpolated value.
    """
    return a + t * (b - a)


def np_digitize_bin(
    x: Float64, bin_edge_left: Float64, bin_edge_right: Float64
) -> Float64:
    """Check if x falls in [left, right) bin.

    Returns 1.0 if x is in this bin, 0.0 otherwise.

    Args:
        x: Value to classify.
        bin_edge_left: Left edge (inclusive).
        bin_edge_right: Right edge (exclusive).

    Returns:
        1.0 if in bin, 0.0 if not.
    """
    if x >= bin_edge_left and x < bin_edge_right:
        return 1.0
    return 0.0
