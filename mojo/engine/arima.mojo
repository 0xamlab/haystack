"""
arima.mojo — AR/MA model estimation (ARIMA building blocks). Zero Python imports.

Replaces statsmodels.tsa (AutoReg / ARIMA Yule-Walker fitting, innovations
MA estimation, conditional-sum-of-squares likelihood). Complements
timeseries_stats.mojo, which provides ACF/PACF diagnostics only — this
module actually fits AR(p)/MA(q) coefficients.

Model convention (statsmodels sign convention, positive theta on lagged
innovations), with mu the sample mean handled internally:
    x_t - mu = sum_i phi_i (x_{t-i} - mu) + e_t + sum_j theta_j e_{t-j}

Public API:
  ARFit / MAFit          — result structs (coefficients + innovation variance)
  ar_fit_yule_walker     — AR(p) via Durbin-Levinson on the sample ACF
  durbin_levinson        — Durbin-Levinson recursion on given autocovariances
  ar_forecast            — h-step-ahead AR forecasts (recursive, mean-reverting)
  ma_fit_innovations     — MA(q) via the innovations algorithm on sample ACF
  innovations_algorithm  — innovations recursion on given autocovariances
  arma_loglik_css        — conditional-sum-of-squares Gaussian log-likelihood
  difference             — order-d differencing (the ARIMA "I" step)
  undifference           — exact inverse of difference given the first d values
"""

from std.math import sqrt, log, abs as fabs


# ── result structs ───────────────────────────────────────────────────────────


struct ARFit(Copyable, Movable):
    """AR(p) fit: phi[i] is the coefficient on lag i+1; sigma2 the innovation
    variance."""
    var phi: List[Float64]
    var sigma2: Float64

    def __init__(out self):
        self.phi = List[Float64]()
        self.sigma2 = 0.0

    def __init__(out self, phi: List[Float64], sigma2: Float64):
        self.phi = phi.copy()
        self.sigma2 = sigma2


struct MAFit(Copyable, Movable):
    """MA(q) fit: theta[j] is the coefficient on innovation lag j+1; sigma2
    the innovation variance."""
    var theta: List[Float64]
    var sigma2: Float64

    def __init__(out self):
        self.theta = List[Float64]()
        self.sigma2 = 0.0

    def __init__(out self, theta: List[Float64], sigma2: Float64):
        self.theta = theta.copy()
        self.sigma2 = sigma2


# ── helpers ──────────────────────────────────────────────────────────────────


def _mean(data: List[Float64]) -> Float64:
    var n = len(data)
    if n == 0:
        return 0.0
    var s: Float64 = 0.0
    for i in range(n):
        s += data[i]
    return s / Float64(n)


def _autocovariances(data: List[Float64], max_lag: Int) -> List[Float64]:
    """Biased (1/n) sample autocovariances gamma[0..max_lag], de-meaned.

    The 1/n normalization keeps the autocovariance sequence non-negative
    definite (standard for Yule-Walker / innovations estimation). Lags
    beyond n-1 are 0. Empty input returns an empty list.
    """
    var out = List[Float64]()
    var n = len(data)
    if n == 0 or max_lag < 0:
        return out^
    var mu = _mean(data)
    for k in range(max_lag + 1):
        var s: Float64 = 0.0
        for t in range(n - k):
            s += (data[t] - mu) * (data[t + k] - mu)
        out.append(s / Float64(n))
    return out^


def _gamma_at(autocov: List[Float64], k: Int) -> Float64:
    """autocov[k] with out-of-range lags treated as 0."""
    if k < 0 or k >= len(autocov):
        return 0.0
    return autocov[k]


# ── durbin_levinson ──────────────────────────────────────────────────────────


def durbin_levinson(autocov: List[Float64], p: Int) -> ARFit:
    """Durbin-Levinson recursion: solve the order-p Yule-Walker equations.

    autocov must hold gamma(0..p) (missing high lags are treated as 0;
    p is clamped to len(autocov)-1). Returns phi[0..p-1] (phi[i] on lag
    i+1) and sigma2 = v_p, the order-p innovation (prediction) variance.
    Degenerate input (empty autocov, or gamma(0) ~ 0 as for an all-equal
    series) returns zero coefficients with sigma2 = 0. O(p^2).
    """
    var out = ARFit()
    if len(autocov) == 0 or p <= 0:
        if len(autocov) > 0:
            out.sigma2 = autocov[0]
        return out^
    var order = p
    if order > len(autocov) - 1:
        order = len(autocov) - 1
    var g0 = autocov[0]
    if g0 <= 1e-300:
        for _ in range(p):
            out.phi.append(0.0)
        out.sigma2 = 0.0
        return out^
    if order == 0:
        # p > 0 but only gamma(0) supplied: no lags to fit.
        for _ in range(p):
            out.phi.append(0.0)
        out.sigma2 = g0
        return out^

    var phi_prev = List[Float64]()
    var v = g0
    for m in range(1, order + 1):
        var num = _gamma_at(autocov, m)
        for j in range(1, m):
            num -= phi_prev[j - 1] * _gamma_at(autocov, m - j)
        var k: Float64 = 0.0
        if v > 1e-300:
            k = num / v
        var phi_cur = List[Float64](capacity=m)
        for j in range(1, m):
            phi_cur.append(phi_prev[j - 1] - k * phi_prev[m - j - 1])
        phi_cur.append(k)
        v = v * (1.0 - k * k)
        if v < 0.0:
            v = 0.0
        phi_prev = phi_cur^

    out.phi = phi_prev^
    # Pad with zeros if p was clamped (caller asked for more lags than data).
    while len(out.phi) < p:
        out.phi.append(0.0)
    out.sigma2 = v
    return out^


# ── ar_fit_yule_walker ───────────────────────────────────────────────────────


def ar_fit_yule_walker(series: List[Float64], p: Int) -> ARFit:
    """Fit AR(p) by Yule-Walker: Durbin-Levinson on the sample ACF.

    The series is de-meaned internally (model on x_t - mean). p is clamped
    to n-1. Returns phi[0..p-1] and sigma2 (innovation variance estimate).
    Empty series or p <= 0 yields empty phi. O(n*p + p^2).
    """
    var n = len(series)
    if n == 0 or p <= 0:
        return ARFit()
    var order = p
    if order > n - 1:
        order = n - 1
    var gam = _autocovariances(series, order)
    var fit = durbin_levinson(gam, order)
    while len(fit.phi) < p:
        fit.phi.append(0.0)
    return fit^


# ── ar_forecast ──────────────────────────────────────────────────────────────


def ar_forecast(
    series: List[Float64], phi: List[Float64], steps: Int
) -> List[Float64]:
    """h-step-ahead AR forecasts, h = 1..steps.

    Uses xhat_{n+h} = mu + sum_i phi[i] * z_{n+h-i} where mu is the sample
    mean of series, z is the de-meaned series extended with prior de-meaned
    forecasts, and indices before the start of the series contribute 0
    (i.e. the mean). Empty series or steps <= 0 returns an empty list.
    Forecasts decay toward the sample mean for stationary phi. O(steps*p).
    """
    var out = List[Float64]()
    var n = len(series)
    if n == 0 or steps <= 0:
        return out^
    # Untrusted count: steps drives the z-buffer allocation; clamp to a
    # documented ceiling.
    var h = steps
    if h > 100000:
        h = 100000
    var mu = _mean(series)
    var p = len(phi)
    var z = List[Float64](capacity=n + h)
    for i in range(n):
        z.append(series[i] - mu)
    for _ in range(h):
        var acc: Float64 = 0.0
        for i in range(p):
            var idx = len(z) - 1 - i
            if idx >= 0:
                acc += phi[i] * z[idx]
        z.append(acc)
        out.append(mu + acc)
    return out^


# ── innovations_algorithm ────────────────────────────────────────────────────


def innovations_algorithm(
    autocov: List[Float64], q: Int, max_iter: Int
) -> MAFit:
    """Innovations algorithm (Brockwell & Davis) on given autocovariances.

    Runs the recursion
      theta_{m,m-k} = (gamma(m-k) - sum_{j<k} theta_{k,k-j} theta_{m,m-j} v_j) / v_k
      v_m = gamma(0) - sum_{j<m} theta_{m,m-j}^2 v_j
    for m = 1..M with M = max(q, max_iter), reading out-of-range lags of
    autocov as 0. Returns theta[j] = theta_{M,j+1} for j = 0..q-1 and
    sigma2 = v_M. theta_{M,1..q} -> the MA(q) coefficients as M grows.
    Degenerate gamma(0) ~ 0 returns zeros. O(M^3) time / O(M^2) space:
    keep max_iter modest (20-50 is typical; see module notes).
    """
    var out = MAFit()
    if q <= 0 or len(autocov) == 0:
        if len(autocov) > 0:
            out.sigma2 = autocov[0]
        return out^
    # Untrusted q / max_iter: the recursion is O(M^3) and theta holds q
    # elements; clamp both to a documented ceiling.
    var q_c = q
    if q_c > 1000:
        q_c = 1000
    var g0 = autocov[0]
    if g0 <= 1e-300:
        for _ in range(q_c):
            out.theta.append(0.0)
        out.sigma2 = 0.0
        return out^
    var big_m = max_iter
    if big_m > 1000:
        big_m = 1000
    if big_m < q_c:
        big_m = q_c

    # rows[m-1][j-1] = theta_{m,j}; v[m] = innovation variance at step m.
    var rows = List[List[Float64]]()
    var v = List[Float64](capacity=big_m + 1)
    v.append(g0)
    for m in range(1, big_m + 1):
        var row = List[Float64](capacity=m)
        for _ in range(m):
            row.append(0.0)
        for k in range(m):
            var s = _gamma_at(autocov, m - k)
            for j in range(k):
                s -= rows[k - 1][k - j - 1] * row[m - j - 1] * v[j]
            if v[k] > 1e-300:
                row[m - k - 1] = s / v[k]
            else:
                row[m - k - 1] = 0.0
        var vm = g0
        for j in range(m):
            vm -= row[m - j - 1] * row[m - j - 1] * v[j]
        if vm < 0.0:
            vm = 0.0
        v.append(vm)
        rows.append(row^)

    for j in range(q_c):
        out.theta.append(rows[big_m - 1][j])
    out.sigma2 = v[big_m]
    return out^


# ── ma_fit_innovations ───────────────────────────────────────────────────────


def ma_fit_innovations(series: List[Float64], q: Int, max_iter: Int) -> MAFit:
    """Fit MA(q) via the innovations algorithm on the sample ACF.

    The series is de-meaned internally. Runs M = max(q, min(max_iter, n-1))
    recursion steps and reads off theta_{M,1..q} and sigma2 = v_M; estimates
    stabilize quickly, so max_iter around 20-50 suffices in practice.
    Empty series or q <= 0 yields empty theta. O(n*M + M^3) — sub-ms for
    M <= ~60 at any n <= 10k; do not pass max_iter ~ n (see module notes).
    """
    var n = len(series)
    if n == 0 or q <= 0:
        return MAFit()
    # Untrusted q / max_iter: both drive the recursion and the autocovariance
    # allocation; clamp to the same documented ceiling as innovations_algorithm.
    var q_c = q
    if q_c > 1000:
        q_c = 1000
    var max_it = max_iter
    if max_it > 1000:
        max_it = 1000
    var big_m = max_it
    if big_m > n - 1:
        big_m = n - 1
    if big_m < q_c:
        big_m = q_c
    var gam = _autocovariances(series, big_m)
    return innovations_algorithm(gam, q_c, big_m)


# ── arma_loglik_css ──────────────────────────────────────────────────────────


def arma_loglik_css(
    series: List[Float64], phi: List[Float64], theta: List[Float64]
) -> Float64:
    """Conditional-sum-of-squares Gaussian log-likelihood of an ARMA(p,q).

    De-means the series, then computes residuals for t = p..n-1:
      e_t = z_t - sum_i phi[i] z_{t-1-i} - sum_j theta[j] e_{t-1-j}
    with pre-sample residuals set to 0 (CSS conditioning). Returns the
    profile log-likelihood at the MLE variance sigma2 = SSE / n_eff,
    n_eff = n - p:
      -n_eff/2 * (log(2*pi) + log(sigma2) + 1)
    Higher is better; compare fits with equal p (same n_eff). Returns 0.0
    when n_eff <= 0. A perfect fit (SSE = 0) is floored at sigma2 = 1e-300
    to stay finite. O(n * (p + q)).
    """
    var n = len(series)
    var p = len(phi)
    var q = len(theta)
    var n_eff = n - p
    if n_eff <= 0:
        return 0.0
    var mu = _mean(series)
    var z = List[Float64](capacity=n)
    for i in range(n):
        z.append(series[i] - mu)
    var e = List[Float64](capacity=n)
    for _ in range(n):
        e.append(0.0)
    var sse: Float64 = 0.0
    for t in range(p, n):
        var acc = z[t]
        for i in range(p):
            acc -= phi[i] * z[t - 1 - i]
        for j in range(q):
            var idx = t - 1 - j
            if idx >= 0:
                acc -= theta[j] * e[idx]
        e[t] = acc
        sse += acc * acc
    var sigma2 = sse / Float64(n_eff)
    if sigma2 < 1e-300:
        sigma2 = 1e-300
    return -0.5 * Float64(n_eff) * (1.8378770664093453 + log(sigma2) + 1.0)


# ── difference ───────────────────────────────────────────────────────────────


def difference(series: List[Float64], order: Int = 1) -> List[Float64]:
    """Order-d differencing: apply diff[i] = x[i+1] - x[i], d times.

    Returns a series of length max(len(series) - order, 0); order <= 0
    returns a copy. Mirrors timeseries_stats.difference so this module is
    self-contained as the exact inverse pair with undifference. O(n*d).
    """
    var current = List[Float64](capacity=len(series))
    for i in range(len(series)):
        current.append(series[i])
    if order <= 0:
        return current^
    for _ in range(order):
        var next_list = List[Float64]()
        for i in range(len(current) - 1):
            next_list.append(current[i + 1] - current[i])
        current = next_list^
    return current^


# ── undifference ─────────────────────────────────────────────────────────────


def undifference(
    diffed: List[Float64], initial: List[Float64]
) -> List[Float64]:
    """Exact inverse of order-d differencing; d = len(initial).

    initial must hold the first d values of the ORIGINAL series. Rebuilds
    by cumulative summation, seeding each level with the first element of
    the k-th difference of initial. Round-trip identity:
      undifference(difference(x, d), x[0:d]) == x   (len(x) >= d).
    Empty initial (d = 0) returns diffed unchanged. Output length is
    len(diffed) + d. O((n + d) * d).
    """
    var d = len(initial)
    var current = List[Float64](capacity=len(diffed) + d)
    for i in range(len(diffed)):
        current.append(diffed[i])
    if d == 0:
        return current^

    # heads[k] = first element of the k-th difference of the original series,
    # computable from its first d values alone (k = 0..d-1).
    var heads = List[Float64](capacity=d)
    var lvl = List[Float64](capacity=d)
    for i in range(d):
        lvl.append(initial[i])
    heads.append(lvl[0])
    for _ in range(1, d):
        var nxt = List[Float64]()
        for i in range(len(lvl) - 1):
            nxt.append(lvl[i + 1] - lvl[i])
        lvl = nxt^
        heads.append(lvl[0])

    for k in range(d - 1, -1, -1):
        var rebuilt = List[Float64](capacity=len(current) + 1)
        rebuilt.append(heads[k])
        for i in range(len(current)):
            rebuilt.append(rebuilt[i] + current[i])
        current = rebuilt^
    return current^
