"""
privacy.mojo — Differential Privacy utilities. Zero Python imports.

Replaces diffprivlib with pure Mojo implementations of Laplace/Gaussian
mechanisms, exponential mechanism, randomized response, composition
theorems, sensitivity computation, and differentially private mean/count.

Public API:
  laplace_mechanism          — Add Laplace noise via inverse CDF
  gaussian_mechanism         — Add Gaussian noise with calibrated σ
  exponential_mechanism_scores — Compute exponential mechanism weights
  randomized_response        — Randomized response protocol
  composition_epsilon        — Basic sequential composition
  advanced_composition       — Advanced composition theorem
  sensitivity_l1             — L1 sensitivity (max |data_i|)
  sensitivity_l2             — L2 sensitivity (sqrt of sum of max²)
  dp_mean                    — Differentially private mean
  dp_count                   — Differentially private count
"""
from std.math import sqrt, log, exp, abs as fabs
from std.random import random_float64


# ── Internal: Laplace sample via inverse CDF ─────────────────────────────────


fn _laplace_sample(scale: Float64) -> Float64:
    """Sample from Laplace(0, scale) using inverse CDF method.

    Uses uniform random u in (0,1), then:
      if u < 0.5:  x = scale * ln(2u)
      else:        x = -scale * ln(2(1-u))
    """
    var u = random_float64()
    # Clamp away from exact 0 and 1
    if u < 1e-15:
        u = 1e-15
    if u > 1.0 - 1e-15:
        u = 1.0 - 1e-15
    if u < 0.5:
        return scale * log(2.0 * u)
    else:
        return -scale * log(2.0 * (1.0 - u))


# ── Internal: Gaussian sample via Box-Muller ─────────────────────────────────


fn _gaussian_sample(sigma: Float64) -> Float64:
    """Sample from Normal(0, sigma²) using Box-Muller transform."""
    var u1 = random_float64()
    var u2 = random_float64()
    if u1 < 1e-15:
        u1 = 1e-15
    var z = sqrt(-2.0 * log(u1)) * _cos_approx(2.0 * 3.141592653589793 * u2)
    return sigma * z


fn _cos_approx(x: Float64) -> Float64:
    """Cosine via reduction + Taylor series (sufficient for noise generation)."""
    var pi = 3.141592653589793
    var two_pi = 2.0 * pi
    # Reduce x to [0, 2π)
    var r = x
    while r < 0.0:
        r += two_pi
    while r >= two_pi:
        r -= two_pi
    # Taylor expansion around 0: cos(r) ≈ 1 - r²/2 + r⁴/24 - r⁶/720 + ...
    # Shift to [-π, π] for better convergence
    if r > pi:
        r = r - two_pi
    var r2 = r * r
    var r4 = r2 * r2
    var r6 = r4 * r2
    var r8 = r4 * r4
    var r10 = r6 * r4
    return 1.0 - r2 / 2.0 + r4 / 24.0 - r6 / 720.0 + r8 / 40320.0 - r10 / 3628800.0


# ── laplace_mechanism ────────────────────────────────────────────────────────


fn laplace_mechanism(
    value: Float64, sensitivity: Float64, epsilon: Float64
) -> Float64:
    """Add Laplace noise: value + Laplace(0, sensitivity/epsilon).

    Args:
        value:       True value to protect.
        sensitivity: Query sensitivity (Δf).
        epsilon:     Privacy budget.

    Returns:
        Noisy value.
    """
    var scale = sensitivity / epsilon
    return value + _laplace_sample(scale)


# ── gaussian_mechanism ───────────────────────────────────────────────────────


fn gaussian_mechanism(
    value: Float64, sensitivity: Float64, epsilon: Float64, delta: Float64
) -> Float64:
    """Add Gaussian noise with σ = sensitivity * sqrt(2*ln(1.25/δ)) / ε.

    Args:
        value:       True value to protect.
        sensitivity: Query sensitivity.
        epsilon:     Privacy budget ε.
        delta:       Failure probability δ.

    Returns:
        Noisy value.
    """
    var sigma = sensitivity * sqrt(2.0 * log(1.25 / delta)) / epsilon
    return value + _gaussian_sample(sigma)


# ── exponential_mechanism_scores ─────────────────────────────────────────────


fn exponential_mechanism_scores(
    scores: List[Float64], sensitivity: Float64, epsilon: Float64
) -> List[Float64]:
    """Compute exponential mechanism unnormalized weights.

    weight_i = exp(ε * score_i / (2 * sensitivity))

    Args:
        scores:      Quality scores for each candidate.
        sensitivity: Sensitivity of scoring function.
        epsilon:     Privacy budget.

    Returns:
        List of unnormalized weights (same length as scores).
    """
    var result = List[Float64]()
    for i in range(len(scores)):
        var w = exp(epsilon * scores[i] / (2.0 * sensitivity))
        result.append(w)
    return result^


# ── randomized_response ──────────────────────────────────────────────────────


fn randomized_response(true_value: Bool, p: Float64) -> Bool:
    """Randomized response: with probability p, return true value; else flip.

    Args:
        true_value: The actual answer.
        p:          Probability of truthful response.

    Returns:
        Randomized answer.
    """
    var r = random_float64()
    if r < p:
        return true_value
    else:
        return not true_value


# ── composition_epsilon ──────────────────────────────────────────────────────


fn composition_epsilon(epsilons: List[Float64]) -> Float64:
    """Basic sequential composition: total ε = Σε_i.

    Args:
        epsilons: List of per-query epsilon values.

    Returns:
        Total epsilon.
    """
    var total: Float64 = 0.0
    for i in range(len(epsilons)):
        total += epsilons[i]
    return total


# ── advanced_composition ─────────────────────────────────────────────────────


fn advanced_composition(
    epsilon: Float64, delta: Float64, k: Int
) -> Float64:
    """Advanced composition theorem.

    total_ε = ε * sqrt(2*k*ln(1/δ)) + k*ε*(e^ε - 1)

    Args:
        epsilon: Per-query epsilon.
        delta:   Total failure probability.
        k:       Number of queries.

    Returns:
        Total epsilon under advanced composition.
    """
    var kf = Float64(k)
    var term1 = epsilon * sqrt(2.0 * kf * log(1.0 / delta))
    var term2 = kf * epsilon * (exp(epsilon) - 1.0)
    return term1 + term2


# ── sensitivity_l1 ───────────────────────────────────────────────────────────


fn sensitivity_l1(data: List[Float64]) -> Float64:
    """L1 sensitivity: max(|data_i|) — the maximum absolute value in data.

    For a sum query over bounded data, the sensitivity equals
    the maximum absolute contribution of any single record.

    Args:
        data: Input data values.

    Returns:
        max |data_i|, or 0.0 for empty data.
    """
    var m: Float64 = 0.0
    for i in range(len(data)):
        var a = fabs(data[i])
        if a > m:
            m = a
    return m


# ── sensitivity_l2 ───────────────────────────────────────────────────────────


fn sensitivity_l2(data: List[Float64]) -> Float64:
    """L2 sensitivity: sqrt(max²) = max(|data_i|) for single-query case.

    For bounded data, the L2 sensitivity of a sum query is the
    maximum absolute value (single-record contribution norm).

    Args:
        data: Input data values.

    Returns:
        L2 sensitivity.
    """
    var m: Float64 = 0.0
    for i in range(len(data)):
        var a = fabs(data[i])
        if a > m:
            m = a
    # L2 sensitivity for single query = max abs value
    return m


# ── dp_mean ──────────────────────────────────────────────────────────────────


fn dp_mean(
    data: List[Float64],
    lower: Float64,
    upper: Float64,
    epsilon: Float64,
) -> Float64:
    """Differentially private mean.

    Clips data to [lower, upper], computes mean, adds Laplace noise
    scaled by (upper - lower) / (n * ε).

    Args:
        data:    Input values.
        lower:   Lower clipping bound.
        upper:   Upper clipping bound.
        epsilon: Privacy budget.

    Returns:
        Noisy mean.
    """
    var n = len(data)
    if n == 0:
        return 0.0
    var s: Float64 = 0.0
    for i in range(n):
        var v = data[i]
        if v < lower:
            v = lower
        if v > upper:
            v = upper
        s += v
    var mean = s / Float64(n)
    var sensitivity = (upper - lower) / Float64(n)
    return mean + _laplace_sample(sensitivity / epsilon)


# ── dp_count ─────────────────────────────────────────────────────────────────


fn dp_count(count: Int, epsilon: Float64) -> Float64:
    """Differentially private count: add Laplace(0, 1/ε) noise.

    Args:
        count:   True count.
        epsilon: Privacy budget.

    Returns:
        Noisy count as Float64.
    """
    var scale = 1.0 / epsilon
    return Float64(count) + _laplace_sample(scale)
