"""
mixture_models.mojo — Gaussian mixture models via EM. Zero Python imports.

Replaces sklearn.mixture.GaussianMixture (diagonal covariance) with pure
Mojo expectation-maximization: seeded k-means++ initialization, log-space
E-step (log-sum-exp), variance-floored M-step, and BIC for choosing k.

Public API:
  GMMResult               — 1D fit result (weights, means, vars, loglik, trace)
  GMMResultND             — N-D diagonal-covariance fit result (flat means/vars)
  gmm_fit                 — fit a k-component 1D Gaussian mixture via EM
  gmm_fit_nd              — fit on flat row-major X (rows x cols), diagonal cov
  gmm_responsibilities    — posterior component probabilities per 1D point
  gmm_responsibilities_nd — posterior component probabilities per N-D row
  gmm_bic                 — Bayesian Information Criterion for a fitted mixture
"""

from std.math import sqrt, log, exp, abs as fabs


# ── constants ────────────────────────────────────────────────────────────────


comptime LOG_TWO_PI: Float64 = 1.8378770664093453
comptime VAR_FLOOR: Float64 = 1e-9
comptime WEIGHT_FLOOR: Float64 = 1e-12
comptime NEG_HUGE: Float64 = -1.7976931348623157e308


# ── result structs ───────────────────────────────────────────────────────────


struct GMMResult(Copyable, Movable):
    """1D Gaussian mixture fit. Components sorted by mean ascending.

    Fields:
      weights      — mixing proportions (length k, sum to 1)
      means        — component means (length k)
      vars         — component variances (length k, >= VAR_FLOOR)
      loglik       — final data log-likelihood
      loglik_trace — log-likelihood after each E-step (non-decreasing)
      iterations   — EM iterations executed
      converged    — True if |Δloglik| < tol before max_iter
    """

    var weights: List[Float64]
    var means: List[Float64]
    var vars: List[Float64]
    var loglik: Float64
    var loglik_trace: List[Float64]
    var iterations: Int
    var converged: Bool

    def __init__(out self):
        self.weights = List[Float64]()
        self.means = List[Float64]()
        self.vars = List[Float64]()
        self.loglik = 0.0
        self.loglik_trace = List[Float64]()
        self.iterations = 0
        self.converged = False


struct GMMResultND(Copyable, Movable):
    """N-D diagonal-covariance Gaussian mixture fit.

    Components sorted by first mean coordinate ascending. means and vars
    are flat row-major (k x cols): component j's dimension d value sits
    at index j * cols + d.
    """

    var weights: List[Float64]
    var means: List[Float64]
    var vars: List[Float64]
    var cols: Int
    var loglik: Float64
    var loglik_trace: List[Float64]
    var iterations: Int
    var converged: Bool

    def __init__(out self):
        self.weights = List[Float64]()
        self.means = List[Float64]()
        self.vars = List[Float64]()
        self.cols = 0
        self.loglik = 0.0
        self.loglik_trace = List[Float64]()
        self.iterations = 0
        self.converged = False


# ── seeded RNG helpers (deterministic xorshift64) ────────────────────────────


def _xorshift64(state: UInt64) -> UInt64:
    var s = state
    s ^= s << 13
    s ^= s >> 7
    s ^= s << 17
    return s


def _seed_state(seed: Int) -> UInt64:
    """Expand an Int seed into a warmed-up nonzero xorshift64 state."""
    var base: UInt64
    if seed < 0:
        base = UInt64(-(seed + 1)) + 1
    else:
        base = UInt64(seed)
    var s = base ^ UInt64(0x9E3779B97F4A7C15)
    if s == 0:
        s = UInt64(0x9E3779B97F4A7C15)
    s = _xorshift64(s)
    s = _xorshift64(s)
    s = _xorshift64(s)
    return s


def _rand_below(mut state: UInt64, bound: Int) -> Int:
    """Uniform-ish integer in [0, bound). bound must be >= 1."""
    state = _xorshift64(state)
    return Int(state % UInt64(bound))


def _rand_unit(mut state: UInt64) -> Float64:
    """Uniform Float64 in [0, 1)."""
    state = _xorshift64(state)
    return Float64(state >> 11) * (1.0 / 9007199254740992.0)


# ── internal helpers ─────────────────────────────────────────────────────────


def _log_gauss_diag(
    X: List[Float64], row: Int, cols: Int,
    means: List[Float64], vars: List[Float64], comp: Int,
) -> Float64:
    """Log density of row `row` of X under diagonal Gaussian `comp`."""
    var acc: Float64 = 0.0
    for d in range(cols):
        var v = vars[comp * cols + d]
        if v < VAR_FLOOR:
            v = VAR_FLOOR
        var dx = X[row * cols + d] - means[comp * cols + d]
        acc += -0.5 * (LOG_TWO_PI + log(v)) - dx * dx / (2.0 * v)
    return acc


def _kmeanspp_means(
    X: List[Float64], rows: Int, cols: Int, k: Int, seed: Int
) -> List[Float64]:
    """Seeded k-means++ pick of k initial component means (flat k x cols)."""
    var rng = _seed_state(seed)
    var chosen = List[Int]()
    chosen.append(_rand_below(rng, rows))

    var d2 = List[Float64](capacity=rows)
    for i in range(rows):
        var s: Float64 = 0.0
        for d in range(cols):
            var dx = X[i * cols + d] - X[chosen[0] * cols + d]
            s += dx * dx
        d2.append(s)

    while len(chosen) < k:
        var total: Float64 = 0.0
        for i in range(rows):
            total += d2[i]
        var pick: Int
        if total <= 0.0:
            pick = _rand_below(rng, rows)
        else:
            var r = _rand_unit(rng) * total
            pick = rows - 1
            var cum: Float64 = 0.0
            for i in range(rows):
                cum += d2[i]
                if r < cum:
                    pick = i
                    break
        chosen.append(pick)
        for i in range(rows):
            var s: Float64 = 0.0
            for d in range(cols):
                var dx = X[i * cols + d] - X[pick * cols + d]
                s += dx * dx
            if s < d2[i]:
                d2[i] = s

    var means = List[Float64](capacity=k * cols)
    for j in range(k):
        for d in range(cols):
            means.append(X[chosen[j] * cols + d])
    return means^


def _sort_components(mut out: GMMResultND, k: Int):
    """Reorder components by first mean coordinate ascending (stable)."""
    var cols = out.cols
    var order = List[Int](capacity=k)
    for j in range(k):
        order.append(j)
    for i in range(1, k):
        var key = order[i]
        var kv = out.means[key * cols]
        var j = i - 1
        while j >= 0 and out.means[order[j] * cols] > kv:
            order[j + 1] = order[j]
            j -= 1
        order[j + 1] = key

    var w = List[Float64](capacity=k)
    var m = List[Float64](capacity=k * cols)
    var v = List[Float64](capacity=k * cols)
    for j in range(k):
        var src = order[j]
        w.append(out.weights[src])
        for d in range(cols):
            m.append(out.means[src * cols + d])
            v.append(out.vars[src * cols + d])
    out.weights = w^
    out.means = m^
    out.vars = v^


# ── gmm_fit_nd ───────────────────────────────────────────────────────────────


def gmm_fit_nd(
    X: List[Float64], rows: Int, cols: Int,
    k: Int, max_iter: Int, tol: Float64, seed: Int,
) -> GMMResultND:
    """Fit a k-component diagonal-covariance Gaussian mixture via EM.

    X is flat row-major (rows x cols). Initialization: seeded k-means++
    means, uniform weights, per-dimension sample variance. E-step runs in
    log space (log-sum-exp), so loglik_trace is non-decreasing; variances
    are floored at VAR_FLOOR to prevent component collapse. Stops when
    |Δloglik| < tol (converged=True) or after max_iter iterations
    (clamped to >= 1). Components are sorted by first mean coordinate
    ascending. Returns an empty result if rows <= 0, cols <= 0, k <= 0,
    k > rows, or len(X) != rows * cols.
    """
    var out = GMMResultND()
    if rows <= 0 or cols <= 0 or k <= 0 or k > rows:
        return out^
    if len(X) != rows * cols:
        return out^
    var iters = max_iter
    if iters < 1:
        iters = 1
    var eps = tol
    if eps < 0.0:
        eps = 0.0

    out.cols = cols
    out.means = _kmeanspp_means(X, rows, cols, k, seed)
    out.weights = List[Float64](capacity=k)
    for _ in range(k):
        out.weights.append(1.0 / Float64(k))

    # Per-dimension sample variance as the shared initial variance.
    var dim_var = List[Float64](capacity=cols)
    for d in range(cols):
        var mu: Float64 = 0.0
        for i in range(rows):
            mu += X[i * cols + d]
        mu /= Float64(rows)
        var ss: Float64 = 0.0
        for i in range(rows):
            var dx = X[i * cols + d] - mu
            ss += dx * dx
        var v = ss / Float64(rows)
        if v < VAR_FLOOR:
            v = VAR_FLOOR
        dim_var.append(v)
    out.vars = List[Float64](capacity=k * cols)
    for _ in range(k):
        for d in range(cols):
            out.vars.append(dim_var[d])

    var resp = List[Float64](capacity=rows * k)
    for _ in range(rows * k):
        resp.append(0.0)
    var logterm = List[Float64](capacity=k)
    for _ in range(k):
        logterm.append(0.0)

    var prev_ll = NEG_HUGE
    for it in range(iters):
        # E-step: responsibilities + log-likelihood via log-sum-exp.
        var ll: Float64 = 0.0
        for i in range(rows):
            var mx = NEG_HUGE
            for j in range(k):
                var w = out.weights[j]
                if w < WEIGHT_FLOOR:
                    w = WEIGHT_FLOOR
                var t = log(w) + _log_gauss_diag(
                    X, i, cols, out.means, out.vars, j
                )
                logterm[j] = t
                if t > mx:
                    mx = t
            var se: Float64 = 0.0
            for j in range(k):
                se += exp(logterm[j] - mx)
            var lse = mx + log(se)
            ll += lse
            for j in range(k):
                resp[i * k + j] = exp(logterm[j] - lse)

        out.loglik_trace.append(ll)
        out.loglik = ll
        out.iterations = it + 1
        if it > 0 and fabs(ll - prev_ll) < eps:
            out.converged = True
            break
        prev_ll = ll

        # M-step: weighted means/variances, floored.
        for j in range(k):
            var nk: Float64 = 0.0
            for i in range(rows):
                nk += resp[i * k + j]
            var nk_safe = nk
            if nk_safe < WEIGHT_FLOOR:
                nk_safe = WEIGHT_FLOOR
            out.weights[j] = nk / Float64(rows)
            if out.weights[j] < WEIGHT_FLOOR:
                out.weights[j] = WEIGHT_FLOOR
            for d in range(cols):
                var mu: Float64 = 0.0
                for i in range(rows):
                    mu += resp[i * k + j] * X[i * cols + d]
                mu /= nk_safe
                out.means[j * cols + d] = mu
                var ss: Float64 = 0.0
                for i in range(rows):
                    var dx = X[i * cols + d] - mu
                    ss += resp[i * k + j] * dx * dx
                var v = ss / nk_safe
                if v < VAR_FLOOR:
                    v = VAR_FLOOR
                out.vars[j * cols + d] = v
        # Renormalize weights (floor above may nudge the sum off 1).
        var wsum: Float64 = 0.0
        for j in range(k):
            wsum += out.weights[j]
        for j in range(k):
            out.weights[j] /= wsum

    _sort_components(out, k)
    return out^


# ── gmm_fit ──────────────────────────────────────────────────────────────────


def gmm_fit(
    x: List[Float64], k: Int, max_iter: Int, tol: Float64, seed: Int
) -> GMMResult:
    """Fit a k-component 1D Gaussian mixture via EM.

    Thin wrapper over gmm_fit_nd with cols=1: seeded k-means++ init,
    log-space E-step, variance floor VAR_FLOOR. Components sorted by
    mean ascending. Returns an empty result if len(x) == 0, k <= 0,
    or k > len(x).
    """
    var out = GMMResult()
    var nd = gmm_fit_nd(x, len(x), 1, k, max_iter, tol, seed)
    out.weights = nd.weights.copy()
    out.means = nd.means.copy()
    out.vars = nd.vars.copy()
    out.loglik = nd.loglik
    out.loglik_trace = nd.loglik_trace.copy()
    out.iterations = nd.iterations
    out.converged = nd.converged
    return out^


# ── gmm_responsibilities ─────────────────────────────────────────────────────


def gmm_responsibilities_nd(
    X: List[Float64], rows: Int, cols: Int,
    weights: List[Float64], means: List[Float64], vars: List[Float64],
) -> List[Float64]:
    """Posterior component probabilities for each row of X.

    Returns flat row-major (rows x k): entry i * k + j is
    P(component j | row i). Each row sums to 1 (computed in log space).
    Variances are floored at VAR_FLOOR, weights at WEIGHT_FLOOR. Returns
    an empty list if rows <= 0, cols <= 0, len(X) != rows * cols, or
    weight/mean/var lengths are inconsistent with k = len(weights).
    """
    var out = List[Float64]()
    var k = len(weights)
    if rows <= 0 or cols <= 0 or k == 0:
        return out^
    if len(X) != rows * cols or len(means) != k * cols or len(vars) != k * cols:
        return out^

    var logterm = List[Float64](capacity=k)
    for _ in range(k):
        logterm.append(0.0)
    for i in range(rows):
        var mx = NEG_HUGE
        for j in range(k):
            var w = weights[j]
            if w < WEIGHT_FLOOR:
                w = WEIGHT_FLOOR
            var t = log(w) + _log_gauss_diag(X, i, cols, means, vars, j)
            logterm[j] = t
            if t > mx:
                mx = t
        var se: Float64 = 0.0
        for j in range(k):
            se += exp(logterm[j] - mx)
        var lse = mx + log(se)
        for j in range(k):
            out.append(exp(logterm[j] - lse))
    return out^


def gmm_responsibilities(
    x: List[Float64],
    weights: List[Float64], means: List[Float64], vars: List[Float64],
) -> List[Float64]:
    """Posterior component probabilities for each 1D point.

    Returns flat row-major (len(x) x k): entry i * k + j is
    P(component j | x[i]); rows sum to 1. Empty list on inconsistent
    input lengths or empty x/weights.
    """
    return gmm_responsibilities_nd(x, len(x), 1, weights, means, vars)


# ── gmm_bic ──────────────────────────────────────────────────────────────────


def gmm_bic(loglik: Float64, n: Int, k: Int, dims: Int) -> Float64:
    """BIC for a k-component diagonal-covariance GMM over n points.

    Free parameters p = k * (2 * dims + 1) - 1 (weights sum to 1;
    per component: dims means + dims variances). BIC = p * ln(n)
    - 2 * loglik; lower is better. Returns 0.0 if n <= 0, k <= 0,
    or dims <= 0.
    """
    if n <= 0 or k <= 0 or dims <= 0:
        return 0.0
    var p = k * (2 * dims + 1) - 1
    return Float64(p) * log(Float64(n)) - 2.0 * loglik
