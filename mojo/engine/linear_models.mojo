"""
linear_models.mojo — Trainable linear models. Zero Python imports.

Replaces sklearn.linear_model (LogisticRegression, ElasticNet, Lasso) and
statsmodels Logit with pure Mojo implementations. Complements regression.mojo
(closed-form OLS/ridge only) with iterative fits: L2-regularized logistic
regression via damped Newton (IRLS) and elastic-net linear regression via
coordinate descent with soft-thresholding. Fully deterministic (no RNG).

Matrix convention: X is a flat row-major matrix, n rows x p cols,
X[i*p + j] = feature j of observation i. Weights come back per feature
with the intercept ("bias") separate and never penalized.

Public API:
  LogisticResult         — weights, bias, converged, n_iter, log_likelihood
  ElasticNetResult       — weights, bias, converged, n_iter
  logistic_fit           — L2-regularized logistic regression (Newton/IRLS)
  logistic_predict_proba — sigmoid(X·w + b) per row
  logistic_std_errors    — SEs from inverse observed information [w..., bias]
  elasticnet_fit         — elastic net: (1/2n)·RSS + l1·|w|_1 + (l2/2)·|w|_2^2
"""

from std.math import sqrt, exp, log, abs as fabs


# ── result structs ───────────────────────────────────────────────────────────


struct LogisticResult(Copyable, Movable):
    """Fitted logistic model: weights (per feature), bias (intercept),
    convergence flag, iterations used, unpenalized log-likelihood."""

    var weights: List[Float64]
    var bias: Float64
    var converged: Bool
    var n_iter: Int
    var log_likelihood: Float64

    def __init__(out self):
        self.weights = List[Float64]()
        self.bias = 0.0
        self.converged = False
        self.n_iter = 0
        self.log_likelihood = 0.0

    def __init__(
        out self,
        weights: List[Float64],
        bias: Float64,
        converged: Bool,
        n_iter: Int,
        log_likelihood: Float64,
    ):
        self.weights = weights.copy()
        self.bias = bias
        self.converged = converged
        self.n_iter = n_iter
        self.log_likelihood = log_likelihood


struct ElasticNetResult(Copyable, Movable):
    """Fitted elastic-net linear model: weights, bias, convergence, iters."""

    var weights: List[Float64]
    var bias: Float64
    var converged: Bool
    var n_iter: Int

    def __init__(out self):
        self.weights = List[Float64]()
        self.bias = 0.0
        self.converged = False
        self.n_iter = 0

    def __init__(
        out self,
        weights: List[Float64],
        bias: Float64,
        converged: Bool,
        n_iter: Int,
    ):
        self.weights = weights.copy()
        self.bias = bias
        self.converged = converged
        self.n_iter = n_iter


# ── helpers ──────────────────────────────────────────────────────────────────


def _sigmoid(z: Float64) -> Float64:
    """Numerically stable logistic sigmoid."""
    if z >= 0.0:
        var e = exp(-z)
        return 1.0 / (1.0 + e)
    var e = exp(z)
    return e / (1.0 + e)


def _soft_threshold(a: Float64, t: Float64) -> Float64:
    """Soft-thresholding operator S(a, t) = sign(a) * max(|a| - t, 0)."""
    if a > t:
        return a - t
    if a < -t:
        return a + t
    return 0.0


def _solve_linear_system(
    A: List[List[Float64]], b: List[Float64]
) -> List[Float64]:
    """Solve A x = b via Gaussian elimination with partial pivoting.

    Near-zero pivots are skipped (that component stays 0), so a singular
    system degrades gracefully instead of producing NaN.
    """
    var p = len(b)
    var aug = List[List[Float64]]()
    for i in range(p):
        var row = List[Float64](capacity=p + 1)
        for j in range(p):
            row.append(A[i][j])
        row.append(b[i])
        aug.append(row^)

    for col in range(p):
        var max_val = fabs(aug[col][col])
        var max_row = col
        for row in range(col + 1, p):
            if fabs(aug[row][col]) > max_val:
                max_val = fabs(aug[row][col])
                max_row = row
        if max_row != col:
            var tmp = aug[col].copy()
            aug[col] = aug[max_row].copy()
            aug[max_row] = tmp^
        var pivot = aug[col][col]
        if fabs(pivot) < 1e-15:
            continue
        for row in range(col + 1, p):
            var factor = aug[row][col] / pivot
            for j in range(col, p + 1):
                aug[row][j] -= factor * aug[col][j]

    var x = List[Float64](capacity=p)
    for _ in range(p):
        x.append(0.0)
    for i in range(p - 1, -1, -1):
        var s = aug[i][p]
        for j in range(i + 1, p):
            s -= aug[i][j] * x[j]
        if fabs(aug[i][i]) > 1e-15:
            x[i] = s / aug[i][i]
    return x^


def _invert_matrix(A: List[List[Float64]]) -> List[List[Float64]]:
    """Invert a square matrix via Gauss-Jordan with partial pivoting.

    Returns an empty list if the matrix is (numerically) singular.
    """
    var p = len(A)
    var aug = List[List[Float64]]()
    for i in range(p):
        var row = List[Float64](capacity=2 * p)
        for j in range(p):
            row.append(A[i][j])
        for j in range(p):
            row.append(1.0 if j == i else 0.0)
        aug.append(row^)

    for col in range(p):
        var max_val = fabs(aug[col][col])
        var max_row = col
        for row in range(col + 1, p):
            if fabs(aug[row][col]) > max_val:
                max_val = fabs(aug[row][col])
                max_row = row
        if max_val < 1e-12:
            return List[List[Float64]]()
        if max_row != col:
            var tmp = aug[col].copy()
            aug[col] = aug[max_row].copy()
            aug[max_row] = tmp^
        var pivot = aug[col][col]
        for j in range(2 * p):
            aug[col][j] /= pivot
        for row in range(p):
            if row == col:
                continue
            var factor = aug[row][col]
            if factor == 0.0:
                continue
            for j in range(2 * p):
                aug[row][j] -= factor * aug[col][j]

    var inv = List[List[Float64]]()
    for i in range(p):
        var row = List[Float64](capacity=p)
        for j in range(p):
            row.append(aug[i][p + j])
        inv.append(row^)
    return inv^


def _log_likelihood(
    X: List[Float64],
    y: List[Int],
    n: Int,
    p: Int,
    beta: List[Float64],
) -> Float64:
    """Unpenalized Bernoulli log-likelihood at beta = [w_0..w_{p-1}, bias]."""
    var ll: Float64 = 0.0
    for i in range(n):
        var z = beta[p]
        for j in range(p):
            z += X[i * p + j] * beta[j]
        var mu = _sigmoid(z)
        if mu < 1e-12:
            mu = 1e-12
        if mu > 1.0 - 1e-12:
            mu = 1.0 - 1e-12
        if y[i] != 0:
            ll += log(mu)
        else:
            ll += log(1.0 - mu)
    return ll


def _penalized_ll(
    X: List[Float64],
    y: List[Int],
    n: Int,
    p: Int,
    beta: List[Float64],
    l2: Float64,
) -> Float64:
    """Log-likelihood minus (l2/2)·|w|^2 (bias unpenalized)."""
    var pen: Float64 = 0.0
    for j in range(p):
        pen += beta[j] * beta[j]
    return _log_likelihood(X, y, n, p, beta) - 0.5 * l2 * pen


# ── logistic_fit ─────────────────────────────────────────────────────────────


def logistic_fit(
    X: List[Float64],
    y: List[Int],
    l2: Float64,
    max_iter: Int,
    tol: Float64,
) -> LogisticResult:
    """L2-regularized logistic regression via damped Newton (IRLS).

    Maximizes sum_i [y_i log mu_i + (1-y_i) log(1-mu_i)] - (l2/2)|w|^2 with
    mu_i = sigmoid(x_i . w + bias); bias is never penalized. X is flat
    row-major n x p with n = len(y); y entries are 0/1 (any nonzero -> 1).
    Each Newton step solves (X'WX + l2 I) d = grad and backtracks (step
    halving) if the penalized log-likelihood would decrease. Converged when
    the applied step's max component < tol. With l2 = 0 on separable data
    weights grow until max_iter — probabilities stay well-ordered.
    Returns default (converged=False, empty weights) on malformed input.
    """
    var out = LogisticResult()
    var n = len(y)
    if n <= 0:
        return out^
    if len(X) % n != 0:
        return out^
    var p = len(X) // n
    var lam = l2
    if lam < 0.0:
        lam = 0.0

    # beta = [w_0 .. w_{p-1}, bias]; warm-start bias at logit(mean(y)).
    var beta = List[Float64](capacity=p + 1)
    for _ in range(p + 1):
        beta.append(0.0)
    var ybar: Float64 = 0.0
    for i in range(n):
        ybar += 1.0 if y[i] != 0 else 0.0
    ybar /= Float64(n)
    if ybar < 1e-3:
        ybar = 1e-3
    if ybar > 1.0 - 1e-3:
        ybar = 1.0 - 1e-3
    beta[p] = log(ybar / (1.0 - ybar))

    var pll = _penalized_ll(X, y, n, p, beta, lam)
    var converged = False
    var iters = 0

    for _ in range(max_iter):
        iters += 1
        # Score g and observed information H at current beta (ascent step).
        var g = List[Float64](capacity=p + 1)
        for _ in range(p + 1):
            g.append(0.0)
        var H = List[List[Float64]]()
        for _ in range(p + 1):
            var row = List[Float64](capacity=p + 1)
            for _ in range(p + 1):
                row.append(0.0)
            H.append(row^)

        for i in range(n):
            var z = beta[p]
            for j in range(p):
                z += X[i * p + j] * beta[j]
            var mu = _sigmoid(z)
            var wi = mu * (1.0 - mu)
            if wi < 1e-10:
                wi = 1e-10
            var resid = (1.0 if y[i] != 0 else 0.0) - mu
            for a in range(p + 1):
                var xa = X[i * p + a] if a < p else 1.0
                g[a] += xa * resid
                for b in range(p + 1):
                    var xb = X[i * p + b] if b < p else 1.0
                    H[a][b] += wi * xa * xb
        for j in range(p):
            g[j] -= lam * beta[j]
            H[j][j] += lam

        var delta = _solve_linear_system(H, g)

        # Backtracking line search on the penalized log-likelihood.
        var step = 1.0
        var trial = List[Float64](capacity=p + 1)
        for _ in range(p + 1):
            trial.append(0.0)
        var new_pll = pll
        for _ in range(20):
            for j in range(p + 1):
                trial[j] = beta[j] + step * delta[j]
            new_pll = _penalized_ll(X, y, n, p, trial, lam)
            if new_pll >= pll - 1e-12:
                break
            step *= 0.5

        var max_move: Float64 = 0.0
        for j in range(p + 1):
            var mv = fabs(step * delta[j])
            if mv > max_move:
                max_move = mv
            beta[j] = trial[j]
        pll = new_pll

        if max_move < tol:
            converged = True
            break

    var weights = List[Float64](capacity=p)
    for j in range(p):
        weights.append(beta[j])
    var ll = _log_likelihood(X, y, n, p, beta)
    return LogisticResult(weights^, beta[p], converged, iters, ll)


# ── logistic_predict_proba ───────────────────────────────────────────────────


def logistic_predict_proba(
    X: List[Float64], weights: List[Float64], bias: Float64
) -> List[Float64]:
    """P(y=1) = sigmoid(X·w + bias) per row of flat row-major X.

    p = len(weights); n = len(X) / p. Returns empty list when p == 0 or
    len(X) is not a multiple of p.
    """
    var out = List[Float64]()
    var p = len(weights)
    if p <= 0 or len(X) % p != 0:
        return out^
    var n = len(X) // p
    for i in range(n):
        var z = bias
        for j in range(p):
            z += X[i * p + j] * weights[j]
        out.append(_sigmoid(z))
    return out^


# ── logistic_std_errors ──────────────────────────────────────────────────────


def logistic_std_errors(
    X: List[Float64],
    y: List[Int],
    weights: List[Float64],
    bias: Float64,
    l2: Float64,
) -> List[Float64]:
    """Standard errors from the inverse observed information at the fit.

    SE_j = sqrt([ (X'WX + l2 I)^-1 ]_jj) with W = diag(mu(1-mu)). Pass the
    same l2 used in logistic_fit (0 for plain MLE / statsmodels-style SEs).
    Returns p+1 values ordered [se_w0, .., se_w{p-1}, se_bias]; empty list
    on malformed input or a singular information matrix.
    """
    var out = List[Float64]()
    var n = len(y)
    var p = len(weights)
    if n <= 0 or len(X) != n * p:
        return out^
    var lam = l2
    if lam < 0.0:
        lam = 0.0

    var H = List[List[Float64]]()
    for _ in range(p + 1):
        var row = List[Float64](capacity=p + 1)
        for _ in range(p + 1):
            row.append(0.0)
        H.append(row^)
    for i in range(n):
        var z = bias
        for j in range(p):
            z += X[i * p + j] * weights[j]
        var mu = _sigmoid(z)
        var wi = mu * (1.0 - mu)
        for a in range(p + 1):
            var xa = X[i * p + a] if a < p else 1.0
            for b in range(p + 1):
                var xb = X[i * p + b] if b < p else 1.0
                H[a][b] += wi * xa * xb
    for j in range(p):
        H[j][j] += lam

    var inv = _invert_matrix(H)
    if len(inv) == 0:
        return out^
    for j in range(p + 1):
        var v = inv[j][j]
        if v < 0.0:
            v = 0.0
        out.append(sqrt(v))
    return out^


# ── elasticnet_fit ───────────────────────────────────────────────────────────


def elasticnet_fit(
    X: List[Float64],
    y: List[Float64],
    l1: Float64,
    l2: Float64,
    max_iter: Int,
    tol: Float64 = 1e-10,
) -> ElasticNetResult:
    """Elastic-net linear regression via cyclic coordinate descent.

    Minimizes (1/2n)|y - Xw - b|^2 + l1·|w|_1 + (l2/2)|w|^2 (bias b never
    penalized; l1=l2=0 reproduces OLS, l1=0 is ridge on this scaling).
    X is flat row-major n x p with n = len(y). Coordinate update:
    w_j = S(rho_j, l1) / (z_j + l2) with rho_j = (1/n)<x_j, r + x_j w_j>,
    z_j = (1/n)<x_j, x_j> — exact soft-thresholding, so irrelevant features
    land on 0.0 exactly. All-zero columns get weight 0. Converged when the
    largest coordinate move in a sweep (bias included) < tol. Negative
    penalties are clamped to 0. Returns default on malformed input.
    """
    var out = ElasticNetResult()
    var n = len(y)
    if n <= 0:
        return out^
    if len(X) % n != 0:
        return out^
    var p = len(X) // n
    var a1 = l1
    if a1 < 0.0:
        a1 = 0.0
    var a2 = l2
    if a2 < 0.0:
        a2 = 0.0

    var w = List[Float64](capacity=p)
    for _ in range(p):
        w.append(0.0)
    var b: Float64 = 0.0
    # Residual r_i = y_i - x_i·w - b (starts at y since w=0, b=0).
    var r = List[Float64](capacity=n)
    for i in range(n):
        r.append(y[i])
    # z_j = (1/n) sum_i x_ij^2, precomputed once.
    var z = List[Float64](capacity=p)
    for j in range(p):
        var s: Float64 = 0.0
        for i in range(n):
            var v = X[i * p + j]
            s += v * v
        z.append(s / Float64(n))

    var converged = False
    var iters = 0
    for _ in range(max_iter):
        iters += 1
        var max_move: Float64 = 0.0

        # Unpenalized intercept: b <- b + mean(r).
        var shift: Float64 = 0.0
        for i in range(n):
            shift += r[i]
        shift /= Float64(n)
        b += shift
        for i in range(n):
            r[i] -= shift
        if fabs(shift) > max_move:
            max_move = fabs(shift)

        for j in range(p):
            if z[j] <= 0.0:
                # All-zero column: coefficient pinned at 0.
                w[j] = 0.0
                continue
            var rho: Float64 = 0.0
            for i in range(n):
                rho += X[i * p + j] * r[i]
            rho = rho / Float64(n) + z[j] * w[j]
            var w_new = _soft_threshold(rho, a1) / (z[j] + a2)
            var d = w_new - w[j]
            if d != 0.0:
                for i in range(n):
                    r[i] -= X[i * p + j] * d
                w[j] = w_new
            if fabs(d) > max_move:
                max_move = fabs(d)

        if max_move < tol:
            converged = True
            break

    return ElasticNetResult(w^, b, converged, iters)
