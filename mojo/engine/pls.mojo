"""
pls.mojo — Partial least squares (PLS1) regression via NIPALS. Zero Python imports.

Replaces sklearn.cross_decomposition.PLSRegression for a single response
vector, filling the PLS / cross-decomposition gap. Complements
regression.mojo (closed-form OLS/ridge) and linear_models.mojo (iterative
logistic / elastic-net): PLS projects X onto latent components of maximal
covariance with y, staying stable on collinear or wide feature blocks where
normal equations degrade.

Matrix convention: X is a flat row-major matrix, n rows x p cols,
X[i*p + j] = feature j of observation i. X columns and y are centered and
scaled internally (sample std, ddof=1; zero-variance columns get scale 1.0);
prediction maps back to original units. Component-major storage in the
result: x_weights/x_loadings[a*p + j], x_scores[a*n + i]. Fully
deterministic (no RNG).

Public API:
  PLSResult        — weights W, loadings P, scores T, y-loadings q, coefs B
                     (standardized space), centering/scaling state, explained
                     variance per component (X and y), per-component n_iter
  pls_fit          — NIPALS PLS1 fit: X flat, n_rows, n_cols, y,
                     n_components, max_iter, tol
  pls_predict      — predict one raw feature row from the fitted state
  pls_predict_rows — predict every row of a flat raw feature matrix
  pls_r2           — R² of the fitted model on a raw (X, y) set
"""

from std.math import sqrt, abs as fabs


# ── PLSResult ────────────────────────────────────────────────────────────────


struct PLSResult(Copyable, Movable):
    """Fitted PLS1 model.

    n_components is the number actually extracted (may be fewer than
    requested: clamped to min(n_cols, n_rows - 1) and stops early once no
    X/y covariance remains). coefs live in centered/scaled space; predict
    applies x_mean/x_scale/y_mean/y_scale to map raw features to raw y.
    explained_variance_x[a] / explained_variance_y[a] are the fractions of
    total (standardized) X / y variance captured by component a.
    """

    var n_components: Int
    var n_features: Int
    var n_samples: Int
    var x_weights: List[Float64]  # W, component-major: [a*p + j], unit norm
    var x_loadings: List[Float64]  # P, component-major: [a*p + j]
    var x_scores: List[Float64]  # T, component-major: [a*n + i]
    var y_loadings: List[Float64]  # q, length n_components
    var coefs: List[Float64]  # B, length p, standardized space
    var x_mean: List[Float64]
    var x_scale: List[Float64]
    var y_mean: Float64
    var y_scale: Float64
    var explained_variance_x: List[Float64]
    var explained_variance_y: List[Float64]
    var n_iter: List[Int]  # NIPALS iterations per component

    fn __init__(out self):
        self.n_components = 0
        self.n_features = 0
        self.n_samples = 0
        self.x_weights = List[Float64]()
        self.x_loadings = List[Float64]()
        self.x_scores = List[Float64]()
        self.y_loadings = List[Float64]()
        self.coefs = List[Float64]()
        self.x_mean = List[Float64]()
        self.x_scale = List[Float64]()
        self.y_mean = 0.0
        self.y_scale = 1.0
        self.explained_variance_x = List[Float64]()
        self.explained_variance_y = List[Float64]()
        self.n_iter = List[Int]()


# ── helpers ──────────────────────────────────────────────────────────────────


fn _solve_small(m: List[Float64], rhs: List[Float64], k: Int) -> List[Float64]:
    """Solve the k x k system M z = rhs (M flat row-major) by Gaussian
    elimination with partial pivoting. Degenerate pivots (< 1e-14) yield
    z = 0 for that unknown. k is the component count — tiny in practice."""
    var a = m.copy()
    var b = rhs.copy()
    for col in range(k):
        var best = col
        var best_abs = fabs(a[col * k + col])
        for r in range(col + 1, k):
            var v = fabs(a[r * k + col])
            if v > best_abs:
                best_abs = v
                best = r
        if best_abs < 1e-14:
            continue
        if best != col:
            for c in range(k):
                var tmp = a[col * k + c]
                a[col * k + c] = a[best * k + c]
                a[best * k + c] = tmp
            var tb = b[col]
            b[col] = b[best]
            b[best] = tb
        var pivot = a[col * k + col]
        for r in range(col + 1, k):
            var factor = a[r * k + col] / pivot
            if factor != 0.0:
                for c in range(col, k):
                    a[r * k + c] -= factor * a[col * k + c]
                b[r] -= factor * b[col]
    var z = List[Float64](capacity=k)
    for _ in range(k):
        z.append(0.0)
    for col in range(k - 1, -1, -1):
        var diag = a[col * k + col]
        if fabs(diag) < 1e-14:
            z[col] = 0.0
            continue
        var s = b[col]
        for c in range(col + 1, k):
            s -= a[col * k + c] * z[c]
        z[col] = s / diag
    return z^


# ── pls_fit ──────────────────────────────────────────────────────────────────


fn pls_fit(
    x: List[Float64],
    n_rows: Int,
    n_cols: Int,
    y: List[Float64],
    n_components: Int,
    max_iter: Int,
    tol: Float64,
) -> PLSResult:
    """Fit PLS1 regression with the NIPALS algorithm.

    Per component a: w_a = E'f / |E'f| (weights), t_a = E w_a (scores),
    p_a = E't_a / t_a't_a (loadings), q_a = f't_a / t_a't_a (y-loading);
    then deflate E -= t_a p_a', f -= q_a t_a. The inner loop iterates
    u -> w -> t -> q -> u until ||w - w_prev|| < tol or max_iter (for a
    single y it converges by iteration 2). Coefficients B = W (P'W)^-1 q.
    Extraction stops early when residual X/y covariance vanishes.
    Invalid shapes (length mismatches, n_rows/n_cols <= 0) return an
    empty model (n_components == 0, n_features == 0). max_iter < 1 is
    treated as 1.
    """
    var res = PLSResult()
    if n_rows <= 0 or n_cols <= 0:
        return res^
    if len(x) != n_rows * n_cols or len(y) != n_rows:
        return res^

    res.n_features = n_cols
    res.n_samples = n_rows

    # Centering / scaling state (sample std, ddof=1; zero-variance -> 1.0).
    for j in range(n_cols):
        var s = 0.0
        for i in range(n_rows):
            s += x[i * n_cols + j]
        res.x_mean.append(s / Float64(n_rows))
    for j in range(n_cols):
        var sc = 1.0
        if n_rows >= 2:
            var ss = 0.0
            for i in range(n_rows):
                var d = x[i * n_cols + j] - res.x_mean[j]
                ss += d * d
            var sd = sqrt(ss / Float64(n_rows - 1))
            if sd > 1e-12:
                sc = sd
        res.x_scale.append(sc)
    var ys = 0.0
    for i in range(n_rows):
        ys += y[i]
    res.y_mean = ys / Float64(n_rows)
    if n_rows >= 2:
        var yss = 0.0
        for i in range(n_rows):
            var d = y[i] - res.y_mean
            yss += d * d
        var ysd = sqrt(yss / Float64(n_rows - 1))
        if ysd > 1e-12:
            res.y_scale = ysd

    # Coefs default to zeros so predict degrades to y_mean gracefully.
    for _ in range(n_cols):
        res.coefs.append(0.0)

    var a_max = n_components
    if a_max > n_cols:
        a_max = n_cols
    if a_max > n_rows - 1:
        a_max = n_rows - 1
    if a_max <= 0:
        return res^

    # Working residuals E (n x p) and f (n), standardized.
    var e = List[Float64](capacity=n_rows * n_cols)
    for i in range(n_rows):
        for j in range(n_cols):
            e.append((x[i * n_cols + j] - res.x_mean[j]) / res.x_scale[j])
    var f = List[Float64](capacity=n_rows)
    for i in range(n_rows):
        f.append((y[i] - res.y_mean) / res.y_scale)

    var total_ss_x = 0.0
    for i in range(len(e)):
        total_ss_x += e[i] * e[i]
    var total_ss_y = 0.0
    for i in range(n_rows):
        total_ss_y += f[i] * f[i]

    var max_it = max_iter
    if max_it < 1:
        max_it = 1
    var eps = 1e-12

    for _a in range(a_max):
        # No residual covariance left -> stop extracting.
        var cov_norm_sq = 0.0
        for j in range(n_cols):
            var c = 0.0
            for i in range(n_rows):
                c += e[i * n_cols + j] * f[i]
            cov_norm_sq += c * c
        if sqrt(cov_norm_sq) < eps:
            break

        # NIPALS inner loop (PLS1: u starts at f; converges by iter 2).
        var u = f.copy()
        var w = List[Float64](capacity=n_cols)
        var w_prev = List[Float64](capacity=n_cols)
        for _ in range(n_cols):
            w.append(0.0)
            w_prev.append(0.0)
        var t = List[Float64](capacity=n_rows)
        for _ in range(n_rows):
            t.append(0.0)
        var tt = 0.0
        var q = 0.0
        var iters = 0
        var signal = True
        for it in range(max_it):
            iters = it + 1
            var norm_sq = 0.0
            for j in range(n_cols):
                var c = 0.0
                for i in range(n_rows):
                    c += e[i * n_cols + j] * u[i]
                w[j] = c
                norm_sq += c * c
            var norm = sqrt(norm_sq)
            if norm < eps:
                signal = False
                break
            for j in range(n_cols):
                w[j] /= norm
            tt = 0.0
            for i in range(n_rows):
                var s = 0.0
                for j in range(n_cols):
                    s += e[i * n_cols + j] * w[j]
                t[i] = s
                tt += s * s
            if tt < eps:
                signal = False
                break
            var ft = 0.0
            for i in range(n_rows):
                ft += f[i] * t[i]
            q = ft / tt
            var delta_sq = 0.0
            for j in range(n_cols):
                var d = w[j] - w_prev[j]
                delta_sq += d * d
                w_prev[j] = w[j]
            if sqrt(delta_sq) < tol:
                break
            for i in range(n_rows):
                u[i] = f[i] * q
        if not signal:
            break

        # Loadings, bookkeeping, deflation.
        var p_vec = List[Float64](capacity=n_cols)
        var pp = 0.0
        for j in range(n_cols):
            var c = 0.0
            for i in range(n_rows):
                c += e[i * n_cols + j] * t[i]
            var pj = c / tt
            p_vec.append(pj)
            pp += pj * pj
        for j in range(n_cols):
            res.x_weights.append(w[j])
            res.x_loadings.append(p_vec[j])
        for i in range(n_rows):
            res.x_scores.append(t[i])
        res.y_loadings.append(q)
        res.n_iter.append(iters)
        if total_ss_x > 0.0:
            res.explained_variance_x.append(tt * pp / total_ss_x)
        else:
            res.explained_variance_x.append(0.0)
        if total_ss_y > 0.0:
            res.explained_variance_y.append(q * q * tt / total_ss_y)
        else:
            res.explained_variance_y.append(0.0)
        for i in range(n_rows):
            for j in range(n_cols):
                e[i * n_cols + j] -= t[i] * p_vec[j]
            f[i] -= q * t[i]
        res.n_components += 1

    # Coefficients B = W (P'W)^-1 q in standardized space.
    var a_fit = res.n_components
    if a_fit > 0:
        var m = List[Float64](capacity=a_fit * a_fit)
        for r in range(a_fit):
            for c in range(a_fit):
                var s = 0.0
                for j in range(n_cols):
                    s += (
                        res.x_loadings[r * n_cols + j]
                        * res.x_weights[c * n_cols + j]
                    )
                m.append(s)
        var z = _solve_small(m, res.y_loadings, a_fit)
        for j in range(n_cols):
            var b = 0.0
            for a in range(a_fit):
                b += z[a] * res.x_weights[a * n_cols + j]
            res.coefs[j] = b
    return res^


# ── pls_predict ──────────────────────────────────────────────────────────────


fn pls_predict(model: PLSResult, x_row: List[Float64]) -> Float64:
    """Predict y for one raw feature row using the model's coefs and
    centering/scaling state. Wrong-length rows and empty models return
    y_mean (with zero fitted components coefs are zero, so the prediction
    is y_mean as well)."""
    if len(x_row) != model.n_features or model.n_features == 0:
        return model.y_mean
    var acc = 0.0
    for j in range(model.n_features):
        acc += (
            model.coefs[j] * (x_row[j] - model.x_mean[j]) / model.x_scale[j]
        )
    return model.y_mean + model.y_scale * acc


# ── pls_predict_rows ─────────────────────────────────────────────────────────


fn pls_predict_rows(
    model: PLSResult, x: List[Float64], n_rows: Int
) -> List[Float64]:
    """Predict y for every row of a flat row-major raw feature matrix.
    Returns an empty list on shape mismatch."""
    var out = List[Float64]()
    var p = model.n_features
    if n_rows <= 0 or p <= 0 or len(x) != n_rows * p:
        return out^
    for i in range(n_rows):
        var acc = 0.0
        for j in range(p):
            acc += (
                model.coefs[j]
                * (x[i * p + j] - model.x_mean[j])
                / model.x_scale[j]
            )
        out.append(model.y_mean + model.y_scale * acc)
    return out^


# ── pls_r2 ───────────────────────────────────────────────────────────────────


fn pls_r2(
    model: PLSResult, x: List[Float64], n_rows: Int, y: List[Float64]
) -> Float64:
    """R² = 1 - SS_res / SS_tot of model predictions on raw (X, y).
    Shape mismatches return 0. Constant y returns 1 when predictions match
    (SS_res <= 1e-12), else 0."""
    if n_rows <= 0 or len(y) != n_rows:
        return 0.0
    var preds = pls_predict_rows(model, x, n_rows)
    if len(preds) != n_rows:
        return 0.0
    var mean = 0.0
    for i in range(n_rows):
        mean += y[i]
    mean /= Float64(n_rows)
    var ss_tot = 0.0
    var ss_res = 0.0
    for i in range(n_rows):
        var dt = y[i] - mean
        ss_tot += dt * dt
        var dr = y[i] - preds[i]
        ss_res += dr * dr
    if ss_tot <= 0.0:
        if ss_res <= 1e-12:
            return 1.0
        return 0.0
    return 1.0 - ss_res / ss_tot
