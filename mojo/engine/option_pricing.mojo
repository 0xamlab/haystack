"""
option_pricing.mojo — Options pricing models. Zero Python imports.

Replaces QuantLib basics with pure Mojo implementations of Black-Scholes,
Greeks, binomial trees, implied volatility, and put-call parity.

Public API:
  norm_cdf              — Standard normal CDF (Abramowitz & Stegun)
  black_scholes_call    — BS European call price
  black_scholes_put     — BS European put price
  delta_call            — Call delta N(d1)
  gamma                 — Gamma (same for call/put)
  vega                  — Vega
  theta_call            — Call theta
  put_call_parity       — Put price from parity
  binomial_tree_call    — CRR binomial tree European call
  implied_volatility    — IV via bisection
"""
from std.math import exp, log, sqrt, abs as fabs, erf


# ── Constants ────────────────────────────────────────────────────────────────


comptime PI: Float64 = 3.141592653589793
comptime SQRT2: Float64 = 1.4142135623730951


# ── norm_cdf ─────────────────────────────────────────────────────────────────


fn norm_cdf(x: Float64) -> Float64:
    """Standard normal CDF using erf: Φ(x) = 0.5*(1 + erf(x/√2))."""
    return 0.5 * (1.0 + erf(x / SQRT2))


# ── _norm_pdf ────────────────────────────────────────────────────────────────


fn _norm_pdf(x: Float64) -> Float64:
    """Standard normal PDF."""
    return exp(-0.5 * x * x) / sqrt(2.0 * PI)


# ── _d1_d2 ───────────────────────────────────────────────────────────────────


fn _d1(S: Float64, K: Float64, T: Float64, r: Float64, sigma: Float64) -> Float64:
    """d1 in Black-Scholes formula."""
    return (log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrt(T))


fn _d2(S: Float64, K: Float64, T: Float64, r: Float64, sigma: Float64) -> Float64:
    """d2 in Black-Scholes formula."""
    return _d1(S, K, T, r, sigma) - sigma * sqrt(T)


# ── black_scholes_call ───────────────────────────────────────────────────────


fn black_scholes_call(
    S: Float64, K: Float64, T: Float64, r: Float64, sigma: Float64
) -> Float64:
    """Black-Scholes European call price: S*N(d1) - K*exp(-rT)*N(d2)."""
    var d1 = _d1(S, K, T, r, sigma)
    var d2 = d1 - sigma * sqrt(T)
    return S * norm_cdf(d1) - K * exp(-r * T) * norm_cdf(d2)


# ── black_scholes_put ────────────────────────────────────────────────────────


fn black_scholes_put(
    S: Float64, K: Float64, T: Float64, r: Float64, sigma: Float64
) -> Float64:
    """Black-Scholes European put price: K*exp(-rT)*N(-d2) - S*N(-d1)."""
    var d1 = _d1(S, K, T, r, sigma)
    var d2 = d1 - sigma * sqrt(T)
    return K * exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)


# ── delta_call ───────────────────────────────────────────────────────────────


fn delta_call(
    S: Float64, K: Float64, T: Float64, r: Float64, sigma: Float64
) -> Float64:
    """Call delta: N(d1)."""
    return norm_cdf(_d1(S, K, T, r, sigma))


# ── gamma ────────────────────────────────────────────────────────────────────


fn gamma(
    S: Float64, K: Float64, T: Float64, r: Float64, sigma: Float64
) -> Float64:
    """Gamma (same for call/put): φ(d1) / (S * σ * √T)."""
    var d1 = _d1(S, K, T, r, sigma)
    return _norm_pdf(d1) / (S * sigma * sqrt(T))


# ── vega ─────────────────────────────────────────────────────────────────────


fn vega(
    S: Float64, K: Float64, T: Float64, r: Float64, sigma: Float64
) -> Float64:
    """Vega: S * φ(d1) * √T."""
    var d1 = _d1(S, K, T, r, sigma)
    return S * _norm_pdf(d1) * sqrt(T)


# ── theta_call ───────────────────────────────────────────────────────────────


fn theta_call(
    S: Float64, K: Float64, T: Float64, r: Float64, sigma: Float64
) -> Float64:
    """Call theta: -(S*φ(d1)*σ)/(2√T) - r*K*exp(-rT)*N(d2)."""
    var d1 = _d1(S, K, T, r, sigma)
    var d2 = d1 - sigma * sqrt(T)
    var term1 = -(S * _norm_pdf(d1) * sigma) / (2.0 * sqrt(T))
    var term2 = -r * K * exp(-r * T) * norm_cdf(d2)
    return term1 + term2


# ── put_call_parity ──────────────────────────────────────────────────────────


fn put_call_parity(
    call_price: Float64, K: Float64, T: Float64, r: Float64, S: Float64
) -> Float64:
    """Put price from put-call parity: P = C - S + K*exp(-rT)."""
    return call_price - S + K * exp(-r * T)


# ── binomial_tree_call ───────────────────────────────────────────────────────


fn binomial_tree_call(
    S: Float64, K: Float64, T: Float64, r: Float64, sigma: Float64, n_steps: Int
) -> Float64:
    """CRR binomial tree for European call option."""
    var dt = T / Float64(n_steps)
    var u = exp(sigma * sqrt(dt))
    var d = 1.0 / u
    var p = (exp(r * dt) - d) / (u - d)
    var disc = exp(-r * dt)

    # Build terminal payoffs
    var prices = List[Float64]()
    for i in range(n_steps + 1):
        var ST = S * _pow_simple(u, n_steps - i) * _pow_simple(d, i)
        var payoff = ST - K
        if payoff < 0.0:
            payoff = 0.0
        prices.append(payoff)

    # Backward induction
    for step in range(n_steps - 1, -1, -1):
        var new_prices = List[Float64]()
        for i in range(step + 1):
            new_prices.append(disc * (p * prices[i] + (1.0 - p) * prices[i + 1]))
        prices = new_prices^

    return prices[0]


fn _pow_simple(base: Float64, n: Int) -> Float64:
    """Simple integer power."""
    var result: Float64 = 1.0
    for _ in range(n):
        result *= base
    return result


# ── implied_volatility ───────────────────────────────────────────────────────


fn implied_volatility(
    market_price: Float64,
    S: Float64,
    K: Float64,
    T: Float64,
    r: Float64,
    is_call: Bool,
) -> Float64:
    """Implied volatility via bisection on BS formula."""
    var lo: Float64 = 0.001
    var hi: Float64 = 5.0
    for _ in range(200):
        var mid = (lo + hi) / 2.0
        var price: Float64
        if is_call:
            price = black_scholes_call(S, K, T, r, mid)
        else:
            price = black_scholes_put(S, K, T, r, mid)
        if price < market_price:
            lo = mid
        else:
            hi = mid
        if fabs(hi - lo) < 1e-10:
            break
    return (lo + hi) / 2.0
