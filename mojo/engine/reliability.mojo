"""
reliability.mojo — Reliability Engineering. Zero Python imports.

Replaces the Python reliability package with pure Mojo implementations of
exponential/Weibull reliability, failure rates, MTBF, availability,
series/parallel/k-of-n systems, bathtub curve, and mission reliability.

Public API:
  exponential_reliability  — R(t) = exp(-λt)
  exponential_failure_rate — Constant failure rate = λ
  weibull_reliability      — R(t) = exp(-(t/η)^β)
  weibull_failure_rate     — h(t) = (β/η)(t/η)^(β-1)
  mtbf                     — Mean time between failures: 1/λ
  availability             — A = MTBF / (MTBF + MTTR)
  series_reliability       — R_series = Π(R_i)
  parallel_reliability     — R_parallel = 1 - Π(1-R_i)
  k_of_n_reliability       — k-out-of-n system reliability
  bathtub_rate             — Bathtub curve failure rate
  mission_reliability      — R_mission = exp(-λ*duration)
"""

from std.math import exp, pow, log as math_log


# ── exponential_reliability ──────────────────────────────────────────────────


def exponential_reliability(t: Float64, lambda_rate: Float64) -> Float64:
    """R(t) = exp(-λt)."""
    return exp(-lambda_rate * t)


# ── exponential_failure_rate ─────────────────────────────────────────────────


def exponential_failure_rate(lambda_rate: Float64) -> Float64:
    """Constant failure rate = λ."""
    return lambda_rate


# ── weibull_reliability ──────────────────────────────────────────────────────


def weibull_reliability(t: Float64, beta: Float64, eta: Float64) -> Float64:
    """R(t) = exp(-(t/η)^β)."""
    if t <= 0.0:
        return 1.0
    if eta <= 0.0:
        return 0.0
    return exp(-pow(t / eta, beta))


# ── weibull_failure_rate ─────────────────────────────────────────────────────


def weibull_failure_rate(t: Float64, beta: Float64, eta: Float64) -> Float64:
    """h(t) = (β/η)(t/η)^(β-1)."""
    if t <= 0.0 or eta <= 0.0:
        return 0.0
    return (beta / eta) * pow(t / eta, beta - 1.0)


# ── mtbf ─────────────────────────────────────────────────────────────────────


def mtbf(failure_rate: Float64) -> Float64:
    """Mean time between failures: 1/λ."""
    if failure_rate <= 0.0:
        return 1e30
    return 1.0 / failure_rate


# ── availability ─────────────────────────────────────────────────────────────


def availability(mtbf_val: Float64, mttr: Float64) -> Float64:
    """A = MTBF / (MTBF + MTTR)."""
    var denom = mtbf_val + mttr
    if denom <= 0.0:
        return 0.0
    return mtbf_val / denom


# ── series_reliability ───────────────────────────────────────────────────────


def series_reliability(reliabilities: List[Float64]) -> Float64:
    """R_series = Π(R_i)."""
    var result: Float64 = 1.0
    for i in range(len(reliabilities)):
        result *= reliabilities[i]
    return result


# ── parallel_reliability ─────────────────────────────────────────────────────


def parallel_reliability(reliabilities: List[Float64]) -> Float64:
    """R_parallel = 1 - Π(1-R_i)."""
    var fail_product: Float64 = 1.0
    for i in range(len(reliabilities)):
        fail_product *= (1.0 - reliabilities[i])
    return 1.0 - fail_product


# ── k_of_n_reliability ──────────────────────────────────────────────────────


def _comb(n: Int, k: Int) -> Int:
    """Binomial coefficient C(n, k)."""
    if k < 0 or k > n:
        return 0
    if k == 0 or k == n:
        return 1
    var kk = k
    if kk > n - kk:
        kk = n - kk
    var result = 1
    for i in range(kk):
        result = result * (n - i) // (i + 1)
    return result


def k_of_n_reliability(k: Int, n: Int, r: Float64) -> Float64:
    """k-out-of-n system reliability: Σ(C(n,i)*r^i*(1-r)^(n-i)) for i=k..n."""
    var result: Float64 = 0.0
    var q = 1.0 - r
    for i in range(k, n + 1):
        var c = Float64(_comb(n, i))
        result += c * pow(r, Float64(i)) * pow(q, Float64(n - i))
    return result


# ── bathtub_rate ─────────────────────────────────────────────────────────────


def bathtub_rate(
    t: Float64,
    beta_infant: Float64,
    lambda_useful: Float64,
    beta_wearout: Float64,
    eta_wearout: Float64,
    t_wearout: Float64,
) -> Float64:
    """Bathtub curve: infant mortality (decreasing) + useful life (constant)
    + wearout (increasing).

    - Infant mortality: modelled as Weibull with beta < 1, eta = t_wearout
    - Useful life: constant rate lambda_useful
    - Wearout: Weibull with beta_wearout > 1, eta_wearout, starting at t_wearout
    """
    # Infant mortality component (decreasing with time)
    var infant: Float64 = 0.0
    if t > 0.0 and t_wearout > 0.0:
        infant = (beta_infant / t_wearout) * pow(t / t_wearout, beta_infant - 1.0)

    # Useful life component (constant)
    var useful = lambda_useful

    # Wearout component (increasing, kicks in around t_wearout)
    var wearout: Float64 = 0.0
    if t > t_wearout and eta_wearout > 0.0:
        var tw = t - t_wearout
        wearout = (beta_wearout / eta_wearout) * pow(tw / eta_wearout, beta_wearout - 1.0)

    return infant + useful + wearout


# ── mission_reliability ──────────────────────────────────────────────────────


def mission_reliability(duration: Float64, failure_rate: Float64) -> Float64:
    """R_mission = exp(-λ*duration). Same as exponential but semantically
    for mission planning."""
    return exp(-failure_rate * duration)
