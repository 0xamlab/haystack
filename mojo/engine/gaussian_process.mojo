"""
gaussian_process.mojo — Exact Gaussian process regression. Zero Python imports.

Replaces sklearn.gaussian_process (GaussianProcessRegressor with RBF / Matern
nu=1.5 kernels) and basic GPy usage: covariance construction, own Cholesky
factorization, posterior mean/variance prediction, and log marginal
likelihood for exact GPs on flat row-major feature matrices (n <= 2000).

Public API:
  KERNEL_RBF        — kernel selector constant (squared exponential)
  KERNEL_MATERN32   — kernel selector constant (Matern nu = 3/2)
  kernel_rbf        — RBF covariance at distance r
  kernel_matern32   — Matern-3/2 covariance at distance r
  GPFit             — fitted GP: lower Cholesky factor of K, alpha = K^-1 y
  GPPrediction      — posterior means + variances for query points
  gp_fit            — fit exact GP (builds K, Cholesky, alpha)
  gp_predict        — posterior (mean, variance) at new points
  gp_loglik         — log marginal likelihood of training targets
"""

from std.math import sqrt, log, exp, abs as fabs

alias KERNEL_RBF = 0
alias KERNEL_MATERN32 = 1

alias _SQRT3 = 1.7320508075688772
alias _LOG_2PI = 1.8378770664093453


# ── kernel functions ─────────────────────────────────────────────────────────


fn kernel_rbf(r: Float64, lengthscale: Float64, signal_var: Float64) -> Float64:
    """RBF (squared-exponential) covariance at Euclidean distance r.

    k(r) = signal_var * exp(-r^2 / (2 * lengthscale^2)). Returns 0.0 when
    lengthscale <= 0. Negative r is treated as |r|.
    """
    if lengthscale <= 0.0:
        return 0.0
    var z = fabs(r) / lengthscale
    return signal_var * exp(-0.5 * z * z)


fn kernel_matern32(
    r: Float64, lengthscale: Float64, signal_var: Float64
) -> Float64:
    """Matern nu=3/2 covariance at Euclidean distance r.

    k(r) = signal_var * (1 + sqrt(3) r / lengthscale) * exp(-sqrt(3) r /
    lengthscale). Returns 0.0 when lengthscale <= 0. Negative r -> |r|.
    """
    if lengthscale <= 0.0:
        return 0.0
    var z = _SQRT3 * fabs(r) / lengthscale
    return signal_var * (1.0 + z) * exp(-z)


fn _kernel_from_r2(
    r2: Float64, lengthscale: Float64, signal_var: Float64, kernel: Int
) -> Float64:
    """Dispatch on squared distance (avoids sqrt for RBF)."""
    if kernel == KERNEL_RBF:
        var z2 = r2 / (lengthscale * lengthscale)
        return signal_var * exp(-0.5 * z2)
    return kernel_matern32(sqrt(r2), lengthscale, signal_var)


fn _sq_dist(
    a: List[Float64], ai: Int, b: List[Float64], bi: Int, dim: Int
) -> Float64:
    """Squared Euclidean distance between row ai of a and row bi of b."""
    var s: Float64 = 0.0
    for d in range(dim):
        var diff = a[ai * dim + d] - b[bi * dim + d]
        s += diff * diff
    return s


# ── GPFit ────────────────────────────────────────────────────────────────────


struct GPFit(Copyable, Movable):
    """Fitted exact GP: lower Cholesky factor of K + noise*I, alpha = K^-1 y.

    chol is the row-major n x n lower-triangular factor L (upper strictly 0);
    alpha solves (L L^T) alpha = y. jitter is any extra diagonal that had to
    be added for the factorization to succeed (0.0 normally). ok=False marks
    invalid inputs or a failed factorization; all other fields are then empty.
    """
    var chol: List[Float64]
    var alpha: List[Float64]
    var n: Int
    var dim: Int
    var lengthscale: Float64
    var signal_var: Float64
    var noise_var: Float64
    var kernel: Int
    var jitter: Float64
    var ok: Bool

    fn __init__(out self):
        self.chol = List[Float64]()
        self.alpha = List[Float64]()
        self.n = 0
        self.dim = 0
        self.lengthscale = 0.0
        self.signal_var = 0.0
        self.noise_var = 0.0
        self.kernel = KERNEL_RBF
        self.jitter = 0.0
        self.ok = False


struct GPPrediction(Copyable, Movable):
    """Posterior prediction: per-query mean and latent-function variance.

    variance excludes observation noise (add fit.noise_var for a noisy-
    observation predictive variance). ok=False -> empty lists.
    """
    var mean: List[Float64]
    var variance: List[Float64]
    var ok: Bool

    fn __init__(out self):
        self.mean = List[Float64]()
        self.variance = List[Float64]()
        self.ok = False


# ── internal linear algebra ──────────────────────────────────────────────────


fn _cholesky_lower(k_mat: List[Float64], n: Int, mut l_out: List[Float64]) -> Bool:
    """Own Cholesky: K = L L^T for symmetric positive-definite K (row-major).

    Writes the lower factor into l_out (must be pre-sized n*n, zero-filled
    by caller). Returns False on a non-positive pivot (K not PD).
    """
    for i in range(n):
        for j in range(i + 1):
            var s = k_mat[i * n + j]
            for p in range(j):
                s -= l_out[i * n + p] * l_out[j * n + p]
            if i == j:
                if s <= 0.0:
                    return False
                l_out[i * n + i] = sqrt(s)
            else:
                l_out[i * n + j] = s / l_out[j * n + j]
    return True


fn _forward_solve(l_mat: List[Float64], n: Int, b: List[Float64]) -> List[Float64]:
    """Solve L z = b for lower-triangular L (row-major n x n)."""
    var z = List[Float64](capacity=n)
    for i in range(n):
        var s = b[i]
        for p in range(i):
            s -= l_mat[i * n + p] * z[p]
        z.append(s / l_mat[i * n + i])
    return z^


fn _backward_solve_t(l_mat: List[Float64], n: Int, b: List[Float64]) -> List[Float64]:
    """Solve L^T x = b for lower-triangular L (row-major n x n)."""
    var x = List[Float64](capacity=n)
    for _ in range(n):
        x.append(0.0)
    for i in range(n - 1, -1, -1):
        var s = b[i]
        for p in range(i + 1, n):
            s -= l_mat[p * n + i] * x[p]
        x[i] = s / l_mat[i * n + i]
    return x^


# ── gp_fit ───────────────────────────────────────────────────────────────────


fn gp_fit(
    x: List[Float64],
    y: List[Float64],
    dim: Int,
    lengthscale: Float64,
    signal_var: Float64,
    noise_var: Float64,
    kernel: Int,
) -> GPFit:
    """Fit an exact zero-mean GP to (x, y).

    x is a flat row-major n x dim feature matrix (dim=1 for plain 1-D
    inputs), y the n targets. Builds K with K_ij = k(x_i, x_j) + noise_var
    on the diagonal, factorizes with its own Cholesky, and solves for
    alpha = K^-1 y. Deterministic. If the factorization hits a non-positive
    pivot (e.g. noise_var = 0 with duplicate rows), it retries with a small
    escalating diagonal jitter (1e-10, 1e-8, 1e-6 scaled by signal_var +
    noise_var), recorded in the returned fit. ok=False on invalid input
    (empty data, length mismatch, lengthscale <= 0, signal_var <= 0,
    noise_var < 0, unknown kernel) or if all jitter attempts fail.
    O(n^3): sub-ms up to n ~ 200; ~n=2000 is the practical exact-GP cap.
    """
    var out = GPFit()
    var n = len(y)
    if n <= 0 or dim <= 0 or len(x) != n * dim:
        return out^
    if lengthscale <= 0.0 or signal_var <= 0.0 or noise_var < 0.0:
        return out^
    if kernel != KERNEL_RBF and kernel != KERNEL_MATERN32:
        return out^

    # Covariance matrix K + noise_var * I (symmetric, row-major).
    var k_mat = List[Float64](capacity=n * n)
    for _ in range(n * n):
        k_mat.append(0.0)
    for i in range(n):
        k_mat[i * n + i] = signal_var + noise_var
        for j in range(i + 1, n):
            var v = _kernel_from_r2(
                _sq_dist(x, i, x, j, dim), lengthscale, signal_var, kernel
            )
            k_mat[i * n + j] = v
            k_mat[j * n + i] = v

    # Cholesky with escalating jitter fallback (deterministic ladder).
    var scale = signal_var + noise_var
    var jitters = List[Float64]()
    jitters.append(0.0)
    jitters.append(1e-10 * scale)
    jitters.append(1e-8 * scale)
    jitters.append(1e-6 * scale)
    var l_mat = List[Float64]()
    var used_jitter: Float64 = 0.0
    var success = False
    for a in range(len(jitters)):
        l_mat = List[Float64](capacity=n * n)
        for _ in range(n * n):
            l_mat.append(0.0)
        if a > 0:
            for i in range(n):
                k_mat[i * n + i] += jitters[a] - jitters[a - 1]
        if _cholesky_lower(k_mat, n, l_mat):
            used_jitter = jitters[a]
            success = True
            break
    if not success:
        return out^

    # alpha = K^-1 y via two triangular solves.
    var z = _forward_solve(l_mat, n, y)
    var alpha = _backward_solve_t(l_mat, n, z)

    out.chol = l_mat.copy()
    out.alpha = alpha.copy()
    out.n = n
    out.dim = dim
    out.lengthscale = lengthscale
    out.signal_var = signal_var
    out.noise_var = noise_var
    out.kernel = kernel
    out.jitter = used_jitter
    out.ok = True
    return out^


# ── gp_predict ───────────────────────────────────────────────────────────────


fn gp_predict(
    x_train: List[Float64], fit: GPFit, x_new: List[Float64]
) -> GPPrediction:
    """Posterior mean and variance at each row of x_new.

    x_train must be the same flat matrix passed to gp_fit; x_new is a flat
    m x dim matrix (a single point of length dim is m = 1). Per point:
    mean = k_*^T alpha, variance = signal_var - ||L^-1 k_*||^2 (latent
    variance, clamped at 0; excludes noise_var). Far from all training
    points k_* -> 0, so mean -> 0 (prior mean) and variance -> signal_var.
    ok=False if the fit is invalid or shapes mismatch. O(n^2) per query
    point (triangular solve); ~40k flops per point at n = 200.
    """
    var out = GPPrediction()
    var n = fit.n
    var dim = fit.dim
    if not fit.ok or len(x_train) != n * dim:
        return out^
    if len(x_new) <= 0 or len(x_new) % dim != 0:
        return out^
    var m = len(x_new) // dim

    for q in range(m):
        var k_star = List[Float64](capacity=n)
        for i in range(n):
            k_star.append(
                _kernel_from_r2(
                    _sq_dist(x_train, i, x_new, q, dim),
                    fit.lengthscale,
                    fit.signal_var,
                    fit.kernel,
                )
            )
        var mean: Float64 = 0.0
        for i in range(n):
            mean += k_star[i] * fit.alpha[i]
        var v = _forward_solve(fit.chol, n, k_star)
        var reduction: Float64 = 0.0
        for i in range(n):
            reduction += v[i] * v[i]
        var variance = fit.signal_var - reduction
        if variance < 0.0:
            variance = 0.0
        out.mean.append(mean)
        out.variance.append(variance)
    out.ok = True
    return out^


# ── gp_loglik ────────────────────────────────────────────────────────────────


fn gp_loglik(fit: GPFit, y: List[Float64]) -> Float64:
    """Log marginal likelihood of training targets y under the fitted GP.

    log p(y) = -1/2 y^T alpha - sum_i log L_ii - n/2 log(2 pi), evaluated
    with the fit's Cholesky factor (any recorded jitter is part of K).
    y must be the same targets passed to gp_fit. Returns NaN when the fit
    is invalid or len(y) != fit.n. O(n).
    """
    if not fit.ok or len(y) != fit.n:
        return Float64(0.0) / Float64(0.0)  # NaN
    var quad: Float64 = 0.0
    for i in range(fit.n):
        quad += y[i] * fit.alpha[i]
    var logdet_half: Float64 = 0.0
    for i in range(fit.n):
        logdet_half += log(fit.chol[i * fit.n + i])
    return -0.5 * quad - logdet_half - 0.5 * Float64(fit.n) * _LOG_2PI
