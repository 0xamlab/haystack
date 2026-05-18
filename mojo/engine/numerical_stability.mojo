"""
numerical_stability.mojo — Numerically stable algorithms. Zero Python imports.

Replaces ad-hoc numerical stability Python code with pure Mojo implementations
for logsumexp, softmax, log-softmax, Kahan summation, Welford's algorithm,
stable sigmoid, softplus, and probability normalization.

Public API:
  logsumexp              — log(Σexp(x_i)) stable
  softmax                — Stable softmax
  log_softmax            — Stable log-softmax
  kahan_sum              — Kahan compensated summation
  welford_mean_var       — Welford's online mean/variance
  log_add_exp            — log(exp(a)+exp(b)) stable
  sigmoid_stable         — Numerically stable sigmoid
  log_sigmoid            — log(sigmoid(x)) stable
  softplus               — log(1+exp(x)) stable
  normalize_probabilities — Normalize to sum=1
  relative_error         — |approx-exact|/|exact|
  safe_divide            — Division with zero protection
"""
from std.math import log, exp, abs as fabs


# ── logsumexp ─────────────────────────────────────────────────────────────────


fn logsumexp(values: List[Float64]) -> Float64:
    """log(Σexp(x_i)) = max + log(Σexp(x_i - max)). Avoids overflow."""
    var n = len(values)
    if n == 0:
        return -1e308  # -inf approximation
    var mx = values[0]
    for i in range(1, n):
        if values[i] > mx:
            mx = values[i]
    var s: Float64 = 0.0
    for i in range(n):
        s += exp(values[i] - mx)
    return mx + log(s)


# ── softmax ───────────────────────────────────────────────────────────────────


fn softmax(values: List[Float64]) -> List[Float64]:
    """Stable softmax: exp(x_i - max) / Σexp(x_j - max)."""
    var n = len(values)
    var result = List[Float64]()
    if n == 0:
        return result^
    var mx = values[0]
    for i in range(1, n):
        if values[i] > mx:
            mx = values[i]
    var s: Float64 = 0.0
    for i in range(n):
        var e = exp(values[i] - mx)
        result.append(e)
        s += e
    for i in range(n):
        result[i] = result[i] / s
    return result^


# ── log_softmax ───────────────────────────────────────────────────────────────


fn log_softmax(values: List[Float64]) -> List[Float64]:
    """log-softmax: x_i - logsumexp(values)."""
    var lse = logsumexp(values)
    var result = List[Float64]()
    for i in range(len(values)):
        result.append(values[i] - lse)
    return result^


# ── kahan_sum ─────────────────────────────────────────────────────────────────


fn kahan_sum(values: List[Float64]) -> Float64:
    """Kahan compensated summation for reduced floating-point error."""
    var s: Float64 = 0.0
    var c: Float64 = 0.0  # compensation
    for i in range(len(values)):
        var y = values[i] - c
        var t = s + y
        c = (t - s) - y
        s = t
    return s


# ── welford_mean_var ──────────────────────────────────────────────────────────


fn welford_mean_var(values: List[Float64]) -> List[Float64]:
    """Welford's online algorithm for mean and variance. Returns [mean, variance]."""
    var n = len(values)
    var result = List[Float64]()
    if n == 0:
        result.append(0.0)
        result.append(0.0)
        return result^
    var mean: Float64 = 0.0
    var m2: Float64 = 0.0
    for i in range(n):
        var x = values[i]
        var delta = x - mean
        mean += delta / Float64(i + 1)
        var delta2 = x - mean
        m2 += delta * delta2
    result.append(mean)
    if n > 1:
        result.append(m2 / Float64(n))  # population variance
    else:
        result.append(0.0)
    return result^


# ── log_add_exp ───────────────────────────────────────────────────────────────


fn log_add_exp(a: Float64, b: Float64) -> Float64:
    """log(exp(a) + exp(b)) numerically stable."""
    var mx = a
    if b > a:
        mx = b
    return mx + log(exp(a - mx) + exp(b - mx))


# ── sigmoid_stable ────────────────────────────────────────────────────────────


fn sigmoid_stable(x: Float64) -> Float64:
    """Numerically stable sigmoid: x>=0 → 1/(1+exp(-x)), x<0 → exp(x)/(1+exp(x))."""
    if x >= 0.0:
        return 1.0 / (1.0 + exp(-x))
    else:
        var ex = exp(x)
        return ex / (1.0 + ex)


# ── log_sigmoid ───────────────────────────────────────────────────────────────


fn log_sigmoid(x: Float64) -> Float64:
    """log(sigmoid(x)) = -softplus(-x)."""
    return -softplus(-x)


# ── softplus ──────────────────────────────────────────────────────────────────


fn softplus(x: Float64) -> Float64:
    """log(1 + exp(x)), stable version.

    For large x, returns x directly. For very negative x, returns exp(x).
    """
    if x > 20.0:
        return x
    elif x < -20.0:
        return exp(x)
    else:
        return log(1.0 + exp(x))


# ── normalize_probabilities ───────────────────────────────────────────────────


fn normalize_probabilities(probs: List[Float64]) -> List[Float64]:
    """Normalize to sum to 1.0, handle all-zero case (uniform)."""
    var n = len(probs)
    var result = List[Float64]()
    var s: Float64 = 0.0
    for i in range(n):
        s += probs[i]
    if s <= 0.0:
        # All-zero case: return uniform
        for i in range(n):
            result.append(1.0 / Float64(n))
    else:
        for i in range(n):
            result.append(probs[i] / s)
    return result^


# ── relative_error ────────────────────────────────────────────────────────────


fn relative_error(approx: Float64, exact: Float64) -> Float64:
    """|approx - exact| / |exact|."""
    if fabs(exact) < 1e-300:
        return fabs(approx)
    return fabs(approx - exact) / fabs(exact)


# ── safe_divide ───────────────────────────────────────────────────────────────


fn safe_divide(a: Float64, b: Float64, default: Float64 = 0.0) -> Float64:
    """a/b with divide-by-zero protection. Returns default if b≈0."""
    if fabs(b) < 1e-300:
        return default
    return a / b
