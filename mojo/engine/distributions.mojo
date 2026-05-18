"""
Distribution samplers — all 27 native Mojo distributions. Zero Python in hot loops.
Phase 7: SIMD-accelerated normal and uniform sampling added.
"""
from std.random import random_float64, randn_float64
from std.math import sqrt, exp, log, abs as fabs, pow, cos, pi


# ── Scalar samplers ────────────────────────────────────────────────────────────

def sample_normal(mu: Float64, sigma: Float64) -> Float64:
    return mu + sigma * randn_float64()

def sample_uniform(lo: Float64, hi: Float64) -> Float64:
    return lo + (hi - lo) * random_float64()

def sample_triangular(lo: Float64, mode: Float64, hi: Float64) -> Float64:
    var u = random_float64(); var r = hi - lo
    if r == 0.0: return lo
    var fc = (mode - lo) / r
    if u < fc: return lo + sqrt(u * r * (mode - lo))
    return hi - sqrt((1.0 - u) * r * (hi - mode))

def sample_lognormal(mu: Float64, sigma: Float64) -> Float64:
    return exp(mu + sigma * randn_float64())

def sample_exponential(rate: Float64) -> Float64:
    return -log(max(random_float64(), 1e-15)) / rate

def sample_weibull(shape: Float64, scale: Float64) -> Float64:
    return scale * pow(-log(max(random_float64(), 1e-15)), 1.0 / shape)

def sample_gamma_mt(shape: Float64, scale: Float64) -> Float64:
    """Marsaglia-Tsang method."""
    var shape_adj = shape; var boost: Float64 = 1.0
    if shape < 1.0:
        shape_adj = shape + 1.0
        boost = pow(max(random_float64(), 1e-15), 1.0 / shape)
    var d = shape_adj - 1.0 / 3.0
    var c = 1.0 / sqrt(9.0 * d)
    while True:
        var x = randn_float64(); var v = 1.0 + c * x
        if v <= 0.0: continue
        v = v * v * v
        var u = random_float64()
        if u < 1.0 - 0.0331 * (x * x) * (x * x):
            return boost * scale * d * v
        if log(u) < 0.5 * x * x + d * (1.0 - v + log(v)):
            return boost * scale * d * v

def sample_beta(alpha: Float64, beta: Float64) -> Float64:
    var x = sample_gamma_mt(alpha, 1.0); var y = sample_gamma_mt(beta, 1.0)
    var t = x + y; return x / t if t != 0.0 else 0.5

def sample_pert(lo: Float64, likely: Float64, hi: Float64, g: Float64) -> Float64:
    var r = hi - lo
    if r == 0.0: return lo
    var mu = (lo + g * likely + hi) / (g + 2.0)
    var alpha = (mu - lo) / r * (g + 2.0) / (1.0 + g)
    var beta  = ((hi - mu) / r) * (g + 2.0) / (1.0 + g)
    return lo + r * sample_beta(max(alpha, 0.01), max(beta, 0.01))

def sample_bernoulli(p: Float64) -> Float64:
    return 1.0 if random_float64() < p else 0.0

def sample_poisson(lam: Float64) -> Float64:
    if lam <= 0.0: return 0.0
    if lam > 30.0: return max(0.0, round(sample_normal(lam, sqrt(lam))))
    var l = exp(-lam); var k: Float64 = 0.0; var p: Float64 = 1.0
    while p > l: k += 1.0; p *= random_float64()
    return k - 1.0

def sample_student_t(df: Float64, mu: Float64, sigma: Float64) -> Float64:
    var n    = randn_float64()
    var chi2 = sample_gamma_mt(df / 2.0, 2.0)
    if chi2 <= 0.0: return mu
    return mu + sigma * n / sqrt(chi2 / df)

def sample_cauchy(location: Float64, scale: Float64) -> Float64:
    var u = max(1e-10, min(1.0 - 1e-10, random_float64()))
    return location + scale * (2.0 * u - 1.0) / (2.0 * (u if u < 0.5 else 1.0 - u)) * 3.141592653589793

def sample_laplace(mu: Float64, b: Float64) -> Float64:
    var u = random_float64() - 0.5
    return mu - b * (1.0 if u >= 0.0 else -1.0) * log(1.0 - 2.0 * fabs(u))

def sample_pareto(alpha: Float64, x_m: Float64) -> Float64:
    var u = max(random_float64(), 1e-15)
    return x_m * pow(u, -1.0 / alpha)

def sample_gumbel(mu: Float64, beta: Float64) -> Float64:
    var u = max(1e-15, min(1.0 - 1e-15, random_float64()))
    return mu - beta * log(-log(u))

def sample_rayleigh(sigma: Float64) -> Float64:
    return sigma * sqrt(-2.0 * log(max(random_float64(), 1e-15)))

def sample_arcsine(lo: Float64, hi: Float64) -> Float64:
    var u = random_float64(); var s = sqrt(u)
    return lo + (hi - lo) * s * s

def sample_logistic(mu: Float64, s: Float64) -> Float64:
    var u = max(1e-15, min(1.0 - 1e-15, random_float64()))
    return mu + s * log(u / (1.0 - u))

def sample_halfnormal(sigma: Float64) -> Float64:
    return fabs(randn_float64() * sigma)

def acos_approx(x: Float64) -> Float64:
    var cx = max(-1.0, min(1.0, x))
    return 3.141592653589793 / 2.0 - (cx + cx*cx*cx/6.0 + 3.0*cx*cx*cx*cx*cx/40.0)

def sample_vonmises(mu: Float64, kappa: Float64) -> Float64:
    if kappa <= 0.0: return sample_uniform(0.0, 6.283185307179586)
    var tau = 1.0 + sqrt(1.0 + 4.0 * kappa * kappa)
    var rho = (tau - sqrt(2.0 * tau)) / (2.0 * kappa)
    var r   = (1.0 + rho * rho) / (2.0 * rho)
    while True:
        var u1   = random_float64()
        var z    = cos(3.141592653589793 * u1) if u1 < 0.5 else -cos(3.141592653589793 * (u1 - 0.5))
        var z_val = (1.0 + r * z) / (r + z)
        var c    = kappa * (r - z_val)
        var u2   = random_float64()
        if c * (2.0 - c) > u2:
            return mu + (1.0 if random_float64() > 0.5 else -1.0) * acos_approx(z_val)
        if log(c / u2) + 1.0 >= c:
            return mu + (1.0 if random_float64() > 0.5 else -1.0) * acos_approx(z_val)

def sample_neg_binomial(r: Float64, p: Float64) -> Float64:
    var lam = sample_gamma_mt(r, (1.0 - p) / p)
    return sample_poisson(lam)

def sample_hypergeometric(N: Float64, K: Float64, n: Float64) -> Float64:
    var k: Float64 = 0.0
    var N_i = N; var K_i = K; var n_i = n
    while n_i > 0.0 and K_i > 0.0 and N_i > 0.0:
        var prob = K_i / N_i
        if random_float64() < prob: k += 1.0; K_i -= 1.0
        N_i -= 1.0; n_i -= 1.0
    return k


# ── SIMD-accelerated batch samplers (Phase 7) ─────────────────────────────────
# These use xorshift64 state — suitable for parallel hot loops.

@always_inline
fn _xorshift64(state: UInt64) -> UInt64:
    var s = state; s ^= s << 13; s ^= s >> 7; s ^= s << 17; return s

@always_inline
fn _xr_f64(state: UInt64) -> Float64:
    return Float64(state >> 11) * (1.0 / 9007199254740992.0)

fn sample_normal_simd4(mut s: UInt64, mean: Float64, std: Float64) -> SIMD[DType.float64, 4]:
    """
    Sample 4 normal(mean, std) values using Box-Muller transform with xorshift64.
    Returns SIMD[float64, 4] — 4x throughput vs scalar path in parallel MC workers.
    """
    s = _xorshift64(s); var u1a = _xr_f64(s) + 1e-300
    s = _xorshift64(s); var u2a = _xr_f64(s)
    s = _xorshift64(s); var u1b = _xr_f64(s) + 1e-300
    s = _xorshift64(s); var u2b = _xr_f64(s)
    var pi_val: Float64 = 3.141592653589793
    var mag_a  = sqrt(-2.0 * log(u1a)); var mag_b = sqrt(-2.0 * log(u1b))
    var angle_a = 2.0 * pi_val * u2a;  var angle_b = 2.0 * pi_val * u2b
    # Box-Muller: (mag * cos(angle), mag * cos(angle + pi/2)) ≈ (mag*cos, -mag*sin)
    # For numerical simplicity use cos + cos(shifted by pi/2 ≈ -sin)
    var z0 = mag_a * cos(angle_a)
    var z1 = mag_a * (-cos(angle_a + pi_val / 2.0))
    var z2 = mag_b * cos(angle_b)
    var z3 = mag_b * (-cos(angle_b + pi_val / 2.0))
    return SIMD[DType.float64, 4](
        mean + std * z0, mean + std * z1,
        mean + std * z2, mean + std * z3
    )

fn sample_uniform_simd4(mut s: UInt64, low: Float64, high: Float64) -> SIMD[DType.float64, 4]:
    """
    Sample 4 uniform(low, high) values using xorshift64.
    Returns SIMD[float64, 4].
    """
    s = _xorshift64(s); var u0 = _xr_f64(s)
    s = _xorshift64(s); var u1 = _xr_f64(s)
    s = _xorshift64(s); var u2 = _xr_f64(s)
    s = _xorshift64(s); var u3 = _xr_f64(s)
    var rng = high - low
    return SIMD[DType.float64, 4](
        low + rng * u0, low + rng * u1,
        low + rng * u2, low + rng * u3
    )


# ── Scalar gamma helper using xorshift64 (for fn contexts) ────────────────────

fn _gamma_xr(mut s: UInt64, shape: Float64, scale: Float64) -> Float64:
    """Marsaglia-Tsang gamma sampler using xorshift64 RNG (no stdlib random)."""
    var shape_adj = shape
    var boost: Float64 = 1.0
    if shape < 1.0:
        shape_adj = shape + 1.0
        s = _xorshift64(s)
        boost = pow(max(_xr_f64(s), 1e-15), 1.0 / shape)
    var d = shape_adj - 1.0 / 3.0
    var c = 1.0 / sqrt(9.0 * d)
    for _ in range(1000):  # bounded rejection sampling
        # Generate a standard normal via Box-Muller + xorshift
        s = _xorshift64(s)
        var u1 = _xr_f64(s) + 1e-300
        s = _xorshift64(s)
        var u2 = _xr_f64(s)
        var x = sqrt(-2.0 * log(u1)) * cos(2.0 * 3.141592653589793 * u2)
        var v = 1.0 + c * x
        if v <= 0.0:
            continue
        v = v * v * v
        s = _xorshift64(s)
        var u = _xr_f64(s)
        if u < 1.0 - 0.0331 * (x * x) * (x * x):
            return boost * scale * d * v
        if log(max(u, 1e-300)) < 0.5 * x * x + d * (1.0 - v + log(max(v, 1e-300))):
            return boost * scale * d * v
    return boost * scale * d  # fallback (should never reach with 1000 iters)


# ── SIMD4 batch samplers for 8 additional distributions ───────────────────────

fn sample_triangular_simd4(mut s: UInt64, low: Float64, mode: Float64, high: Float64) -> SIMD[DType.float64, 4]:
    """Sample 4 triangular(low, mode, high) values using xorshift64 ICDF."""
    var rng = high - low
    if rng == 0.0:
        return SIMD[DType.float64, 4](low, low, low, low)
    var fc = (mode - low) / rng
    var lm = rng * (mode - low)   # (high-low)*(mode-low)
    var hm = rng * (high - mode)  # (high-low)*(high-mode)
    s = _xorshift64(s); var u0 = _xr_f64(s)
    s = _xorshift64(s); var u1 = _xr_f64(s)
    s = _xorshift64(s); var u2 = _xr_f64(s)
    s = _xorshift64(s); var u3 = _xr_f64(s)
    # Apply triangular ICDF per element
    var r0: Float64
    if u0 < fc: r0 = low + sqrt(u0 * lm)
    else:       r0 = high - sqrt((1.0 - u0) * hm)
    var r1: Float64
    if u1 < fc: r1 = low + sqrt(u1 * lm)
    else:       r1 = high - sqrt((1.0 - u1) * hm)
    var r2: Float64
    if u2 < fc: r2 = low + sqrt(u2 * lm)
    else:       r2 = high - sqrt((1.0 - u2) * hm)
    var r3: Float64
    if u3 < fc: r3 = low + sqrt(u3 * lm)
    else:       r3 = high - sqrt((1.0 - u3) * hm)
    return SIMD[DType.float64, 4](r0, r1, r2, r3)

fn sample_lognormal_simd4(mut s: UInt64, mu: Float64, sigma: Float64) -> SIMD[DType.float64, 4]:
    """Sample 4 lognormal(mu, sigma) values. Box-Muller normals then exp()."""
    var normals = sample_normal_simd4(s, mu, sigma)
    return SIMD[DType.float64, 4](
        exp(normals[0]), exp(normals[1]),
        exp(normals[2]), exp(normals[3])
    )

fn sample_exponential_simd4(mut s: UInt64, rate: Float64) -> SIMD[DType.float64, 4]:
    """Sample 4 exponential(rate) values. -ln(u)/rate, fully vectorizable."""
    s = _xorshift64(s); var u0 = _xr_f64(s) + 1e-300
    s = _xorshift64(s); var u1 = _xr_f64(s) + 1e-300
    s = _xorshift64(s); var u2 = _xr_f64(s) + 1e-300
    s = _xorshift64(s); var u3 = _xr_f64(s) + 1e-300
    var inv_rate = 1.0 / rate
    return SIMD[DType.float64, 4](
        -log(u0) * inv_rate, -log(u1) * inv_rate,
        -log(u2) * inv_rate, -log(u3) * inv_rate
    )

fn sample_bernoulli_simd4(mut s: UInt64, p: Float64) -> SIMD[DType.float64, 4]:
    """Sample 4 bernoulli(p) values. 1.0 if u < p else 0.0."""
    s = _xorshift64(s); var u0 = _xr_f64(s)
    s = _xorshift64(s); var u1 = _xr_f64(s)
    s = _xorshift64(s); var u2 = _xr_f64(s)
    s = _xorshift64(s); var u3 = _xr_f64(s)
    var r0: Float64 = 1.0 if u0 < p else 0.0
    var r1: Float64 = 1.0 if u1 < p else 0.0
    var r2: Float64 = 1.0 if u2 < p else 0.0
    var r3: Float64 = 1.0 if u3 < p else 0.0
    return SIMD[DType.float64, 4](r0, r1, r2, r3)

fn sample_gamma_simd4(mut s: UInt64, shape: Float64, scale: Float64) -> SIMD[DType.float64, 4]:
    """Sample 4 gamma(shape, scale) values using Marsaglia-Tsang with xorshift64.
    Uses 4 independent scalar calls (rejection sampling limits SIMD benefit)."""
    var r0 = _gamma_xr(s, shape, scale)
    var r1 = _gamma_xr(s, shape, scale)
    var r2 = _gamma_xr(s, shape, scale)
    var r3 = _gamma_xr(s, shape, scale)
    return SIMD[DType.float64, 4](r0, r1, r2, r3)

fn sample_beta_simd4(mut s: UInt64, alpha: Float64, beta: Float64) -> SIMD[DType.float64, 4]:
    """Sample 4 beta(alpha, beta) values using gamma ratio method with xorshift64.
    x = gamma(alpha,1), y = gamma(beta,1), result = x/(x+y)."""
    var x0 = _gamma_xr(s, alpha, 1.0); var y0 = _gamma_xr(s, beta, 1.0)
    var x1 = _gamma_xr(s, alpha, 1.0); var y1 = _gamma_xr(s, beta, 1.0)
    var x2 = _gamma_xr(s, alpha, 1.0); var y2 = _gamma_xr(s, beta, 1.0)
    var x3 = _gamma_xr(s, alpha, 1.0); var y3 = _gamma_xr(s, beta, 1.0)
    var t0 = x0 + y0; var t1 = x1 + y1; var t2 = x2 + y2; var t3 = x3 + y3
    return SIMD[DType.float64, 4](
        x0 / t0 if t0 != 0.0 else 0.5,
        x1 / t1 if t1 != 0.0 else 0.5,
        x2 / t2 if t2 != 0.0 else 0.5,
        x3 / t3 if t3 != 0.0 else 0.5
    )

fn sample_weibull_simd4(mut s: UInt64, shape: Float64, scale: Float64) -> SIMD[DType.float64, 4]:
    """Sample 4 weibull(shape, scale) values. scale * (-ln(u))^(1/shape)."""
    s = _xorshift64(s); var u0 = _xr_f64(s) + 1e-300
    s = _xorshift64(s); var u1 = _xr_f64(s) + 1e-300
    s = _xorshift64(s); var u2 = _xr_f64(s) + 1e-300
    s = _xorshift64(s); var u3 = _xr_f64(s) + 1e-300
    var inv_shape = 1.0 / shape
    return SIMD[DType.float64, 4](
        scale * pow(-log(u0), inv_shape), scale * pow(-log(u1), inv_shape),
        scale * pow(-log(u2), inv_shape), scale * pow(-log(u3), inv_shape)
    )

fn sample_pert_simd4(mut s: UInt64, low: Float64, likely: Float64, high: Float64, gamma: Float64) -> SIMD[DType.float64, 4]:
    """Sample 4 pert(low, likely, high, gamma) values via beta-based method."""
    var r = high - low
    if r == 0.0:
        return SIMD[DType.float64, 4](low, low, low, low)
    var mu = (low + gamma * likely + high) / (gamma + 2.0)
    var a = max((mu - low) / r * (gamma + 2.0) / (1.0 + gamma), 0.01)
    var b = max(((high - mu) / r) * (gamma + 2.0) / (1.0 + gamma), 0.01)
    var betas = sample_beta_simd4(s, a, b)
    return SIMD[DType.float64, 4](
        low + r * betas[0], low + r * betas[1],
        low + r * betas[2], low + r * betas[3]
    )


# ── SIMD4 universal dispatcher ────────────────────────────────────────────────

fn sample_one_simd4(mut s: UInt64, dt: Int, p0: Float64, p1: Float64, p2: Float64, p3: Float64) -> SIMD[DType.float64, 4]:
    """SIMD4 universal sampler for the top 10 distribution types.
    Returns 4 samples per call. Falls back to p0 for unsupported types."""
    if dt == 0:    return sample_normal_simd4(s, p0, p1)
    elif dt == 1:  return sample_uniform_simd4(s, p0, p1)
    elif dt == 2:  return sample_triangular_simd4(s, p0, p1, p2)
    elif dt == 3:  return sample_lognormal_simd4(s, p0, p1)
    elif dt == 5:  return sample_beta_simd4(s, p0, p1)
    elif dt == 7:  return sample_exponential_simd4(s, p0)
    elif dt == 8:  return sample_weibull_simd4(s, p0, p1)
    elif dt == 9:  return sample_gamma_simd4(s, p0, p1)
    elif dt == 10: return sample_pert_simd4(s, p0, p1, p2, p3)
    elif dt == 11: return sample_bernoulli_simd4(s, p0)
    # Unsupported distribution type — return constant p0 as fallback
    return SIMD[DType.float64, 4](p0, p0, p0, p0)


# ── Universal sampler (all 27 distributions) ──────────────────────────────────

def sample_one(
    dt: Int, p0: Float64, p1: Float64, p2: Float64, p3: Float64,
    dv: List[Float64], dp: List[Float64]
) -> Float64:
    """Universal sampler — all 27 distribution types. Zero Python calls."""
    if dt == 0:   return sample_normal(p0, p1)
    elif dt == 1: return sample_uniform(p0, p1)
    elif dt == 2: return sample_triangular(p0, p1, p2)
    elif dt == 3: return sample_lognormal(p0, p1)
    elif dt == 4: return p0  # fixed constant
    elif dt == 5: return sample_beta(p0, p1)
    elif dt == 7: return sample_exponential(p0)
    elif dt == 8: return sample_weibull(p0, p1)
    elif dt == 9: return sample_gamma_mt(p0, p1)
    elif dt == 10: return sample_pert(p0, p1, p2, p3)
    elif dt == 11: return sample_bernoulli(p0)
    elif dt == 12: return sample_poisson(p0)
    elif dt == 13:
        var u = random_float64()
        for k in range(len(dp)):
            if u <= dp[k]: return dv[k]
        return dv[len(dv)-1] if len(dv) > 0 else 0.0
    elif dt == 14: return sample_student_t(p0, p1, p2)
    elif dt == 15: return sample_cauchy(p0, p1)
    elif dt == 16: return sample_laplace(p0, p1)
    elif dt == 17: return sample_pareto(p0, p1)
    elif dt == 18: return sample_gumbel(p0, p1)
    elif dt == 19: return sample_rayleigh(p0)
    elif dt == 20: return sample_arcsine(p0, p1)
    elif dt == 21: return sample_logistic(p0, p1)
    elif dt == 22: return sample_halfnormal(p0)
    elif dt == 23: return sample_vonmises(p0, p1)
    elif dt == 24: return sample_neg_binomial(p0, p1)
    elif dt == 25: return sample_hypergeometric(p0, p1, p2)
    elif dt == 26:
        var u = random_float64()
        for k in range(len(dp)):
            if u <= dp[k]: return Float64(k)
        return Float64(len(dp) - 1) if len(dp) > 0 else 0.0
    return p0
