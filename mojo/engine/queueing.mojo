"""
queueing.mojo — Queueing theory formulas. Zero Python imports.

Replaces custom Python queueing models with pure Mojo implementations
for M/M/1, M/M/c, Erlang B/C, and Little's law.

Public API:
  mm1_utilization       — ρ = λ/μ
  mm1_avg_queue_length  — Lq = ρ²/(1-ρ)
  mm1_avg_system_size   — L = ρ/(1-ρ)
  mm1_avg_wait_time     — Wq = ρ/(μ-λ)
  mm1_avg_system_time   — W = 1/(μ-λ)
  mmc_erlang_c          — Erlang C: P(wait) for M/M/c queue
  mmc_avg_wait_time     — Wq for M/M/c queue
  erlang_b              — Erlang B: blocking probability
  factorial             — Factorial as Float64
  littles_law_L         — L = λ*W
  littles_law_W         — W = L/λ
"""


# ── Factorial ────────────────────────────────────────────────────────────────


fn factorial(n: Int) -> Float64:
    """Factorial of n as Float64 for large values."""
    if n <= 0:
        return 1.0
    var result: Float64 = 1.0
    for i in range(1, n + 1):
        result *= Float64(i)
    return result


# ── M/M/1 formulas ──────────────────────────────────────────────────────────


fn mm1_utilization(arrival_rate: Float64, service_rate: Float64) -> Float64:
    """Server utilization: ρ = λ/μ."""
    if service_rate <= 0.0:
        return 0.0
    return arrival_rate / service_rate


fn mm1_avg_queue_length(arrival_rate: Float64, service_rate: Float64) -> Float64:
    """Average queue length (excluding being served): Lq = ρ²/(1-ρ)."""
    var rho = mm1_utilization(arrival_rate, service_rate)
    if rho >= 1.0:
        return 1e18  # unstable
    return (rho * rho) / (1.0 - rho)


fn mm1_avg_system_size(arrival_rate: Float64, service_rate: Float64) -> Float64:
    """Average number in system (queue + service): L = ρ/(1-ρ)."""
    var rho = mm1_utilization(arrival_rate, service_rate)
    if rho >= 1.0:
        return 1e18
    return rho / (1.0 - rho)


fn mm1_avg_wait_time(arrival_rate: Float64, service_rate: Float64) -> Float64:
    """Average wait time in queue: Wq = ρ/(μ-λ)."""
    var diff = service_rate - arrival_rate
    if diff <= 0.0:
        return 1e18
    var rho = arrival_rate / service_rate
    return rho / diff


fn mm1_avg_system_time(arrival_rate: Float64, service_rate: Float64) -> Float64:
    """Average time in system (wait + service): W = 1/(μ-λ)."""
    var diff = service_rate - arrival_rate
    if diff <= 0.0:
        return 1e18
    return 1.0 / diff


# ── M/M/c formulas ──────────────────────────────────────────────────────────


fn _power(base: Float64, exp: Int) -> Float64:
    """Compute base^exp for non-negative integer exponent."""
    if exp == 0:
        return 1.0
    var result: Float64 = 1.0
    for _ in range(exp):
        result *= base
    return result


fn mmc_erlang_c(arrival_rate: Float64, service_rate: Float64, servers: Int) -> Float64:
    """Erlang C formula: probability a customer waits in M/M/c queue.

    C(c, A) where A = λ/μ (total offered traffic).
    P(wait) = [A^c / c! * c/(c-A)] / [sum_{k=0}^{c-1} A^k/k! + A^c/c! * c/(c-A)]
    """
    var a = arrival_rate / service_rate  # total traffic intensity
    if a >= Float64(servers):
        return 1.0  # unstable

    # Numerator: A^c / c! * c / (c - A)
    var ac = _power(a, servers)
    var cf = factorial(servers)
    var numerator = ac / cf * Float64(servers) / (Float64(servers) - a)

    # Denominator: sum_{k=0}^{c-1} A^k / k! + numerator
    var sum_terms: Float64 = 0.0
    for k in range(servers):
        sum_terms += _power(a, k) / factorial(k)

    return numerator / (sum_terms + numerator)


fn mmc_avg_wait_time(arrival_rate: Float64, service_rate: Float64, servers: Int) -> Float64:
    """Average wait time in M/M/c queue: Wq = C(c,A) / (c*μ - λ)."""
    var ec = mmc_erlang_c(arrival_rate, service_rate, servers)
    var denom = Float64(servers) * service_rate - arrival_rate
    if denom <= 0.0:
        return 1e18
    return ec / denom


# ── Erlang B ─────────────────────────────────────────────────────────────────


fn erlang_b(traffic_intensity: Float64, servers: Int) -> Float64:
    """Erlang B formula: blocking probability (recursive).

    B(A, 0) = 1
    B(A, n) = (A * B(A, n-1)) / (n + A * B(A, n-1))
    """
    var b: Float64 = 1.0
    for n in range(1, servers + 1):
        b = (traffic_intensity * b) / (Float64(n) + traffic_intensity * b)
    return b


# ── Little's Law ─────────────────────────────────────────────────────────────


fn littles_law_L(arrival_rate: Float64, avg_time: Float64) -> Float64:
    """Little's Law: L = λ * W."""
    return arrival_rate * avg_time


fn littles_law_W(arrival_rate: Float64, avg_number: Float64) -> Float64:
    """Little's Law: W = L / λ."""
    if arrival_rate <= 0.0:
        return 0.0
    return avg_number / arrival_rate
