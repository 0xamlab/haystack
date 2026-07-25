"""
svm_solver.mojo — Trainable SVM classifier via simplified SMO (Platt). Zero Python imports.

Replaces sklearn.svm.SVC / LinearSVC fit + predict with a pure-Mojo
sequential minimal optimization solver: simplified SMO (Platt) with the
random second-choice heuristic, driven by a seeded deterministic
xorshift64 RNG. Complements svm_kernel.mojo (kernel functions only) —
kernel math conventions are mirrored, but this file is self-contained.

Labels y must be in {-1.0, +1.0}. X is a flat row-major matrix
(n_samples * n_features).

Public API:
  SVMModel           — fitted model (alphas, b, w, support vectors/coefs)
  svm_fit_linear     — train linear-kernel SVM; also fills primal weights w
  svm_fit_rbf        — train RBF-kernel SVM; keeps support alphas/vectors
  svm_decision       — raw decision value f(x) = Σ αᵢyᵢK(xᵢ,x) + b
  svm_predict        — class label in {-1.0, +1.0} (sign of decision)
  svm_predict_batch  — labels for a flat row-major query matrix

Performance note: svm_fit_linear / svm_fit_rbf are O(passes · n² · d)
worst case (each KKT-violation step re-evaluates f over all samples with
nonzero alpha) and will exceed 1 ms for n in the thousands. Acceptable:
fitting is an offline / per-recalibration step, not a per-tick call.
svm_decision and svm_predict are O(d) (linear) / O(n_support · d) (RBF)
and stay sub-millisecond for any realistic model.
"""
from std.math import exp, abs as fabs


# ── SVMModel ─────────────────────────────────────────────────────────────────


struct SVMModel(Copyable, Movable):
    """Fitted SVM. kernel_type: 0 = linear, 1 = RBF.

    alphas holds the full length-n dual vector from training; support_x /
    support_coef keep only rows with alpha > 1e-8 (coef = alpha·y), which
    is all prediction needs for RBF. For linear models w holds the primal
    weight vector so prediction is a single dot product. An infeasible fit
    (bad shapes, C <= 0, max_passes <= 0, n == 0) yields an empty model:
    len(alphas) == 0, n_support == 0, decision ≡ 0.
    """

    var kernel_type: Int
    var n_features: Int
    var alphas: List[Float64]
    var b: Float64
    var w: List[Float64]
    var gamma: Float64
    var support_x: List[Float64]
    var support_coef: List[Float64]
    var n_support: Int

    fn __init__(out self):
        self.kernel_type = 0
        self.n_features = 0
        self.alphas = List[Float64]()
        self.b = 0.0
        self.w = List[Float64]()
        self.gamma = 0.0
        self.support_x = List[Float64]()
        self.support_coef = List[Float64]()
        self.n_support = 0


# ── seeded RNG helpers (deterministic xorshift64) ────────────────────────────


fn _xorshift64(state: UInt64) -> UInt64:
    var s = state
    s ^= s << 13
    s ^= s >> 7
    s ^= s << 17
    return s


fn _seed_state(seed: Int) -> UInt64:
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


fn _rand_below(mut state: UInt64, bound: Int) -> Int:
    """Uniform-ish integer in [0, bound). bound must be >= 1."""
    state = _xorshift64(state)
    return Int(state % UInt64(bound))


# ── small numeric helpers ────────────────────────────────────────────────────


fn _fmax(a: Float64, b: Float64) -> Float64:
    if a > b:
        return a
    return b


fn _fmin(a: Float64, b: Float64) -> Float64:
    if a < b:
        return a
    return b


fn _kernel_ij(
    X: List[Float64], i: Int, j: Int, d: Int, kernel_type: Int, gamma: Float64
) -> Float64:
    """Kernel between rows i and j of flat row-major X. 0=linear, 1=RBF."""
    if kernel_type == 0:
        var s: Float64 = 0.0
        for f in range(d):
            s += X[i * d + f] * X[j * d + f]
        return s
    var sq: Float64 = 0.0
    for f in range(d):
        var diff = X[i * d + f] - X[j * d + f]
        sq += diff * diff
    return exp(-gamma * sq)


fn _decision_train(
    X: List[Float64],
    y: List[Float64],
    alphas: List[Float64],
    b: Float64,
    i: Int,
    d: Int,
    kernel_type: Int,
    gamma: Float64,
) -> Float64:
    """f(x_i) = Σ_k α_k y_k K(x_k, x_i) + b over the training set."""
    var s = b
    for k in range(len(y)):
        if alphas[k] != 0.0:
            s += alphas[k] * y[k] * _kernel_ij(X, k, i, d, kernel_type, gamma)
    return s


# ── _svm_fit (shared simplified-SMO core) ────────────────────────────────────


fn _svm_fit(
    X: List[Float64],
    y: List[Float64],
    n_features: Int,
    C: Float64,
    tol: Float64,
    max_passes: Int,
    kernel_type: Int,
    gamma: Float64,
    seed: Int,
) -> SVMModel:
    """Simplified SMO (Platt): loop over i; on a KKT violation (beyond tol)
    pick j != i uniformly at random (seeded), solve the 2-variable QP
    analytically, clip to [L, H], update b. Terminates after max_passes
    consecutive full passes without change (hard cap 100·max_passes total
    passes guards pathological non-termination). Deterministic per seed.
    """
    var model = SVMModel()
    model.kernel_type = kernel_type
    model.n_features = n_features
    model.gamma = gamma

    var n = len(y)
    if (
        n <= 0
        or n_features <= 0
        or len(X) != n * n_features
        or C <= 0.0
        or max_passes <= 0
    ):
        model.n_features = 0
        return model^

    var d = n_features
    var alphas = List[Float64](capacity=n)
    for _ in range(n):
        alphas.append(0.0)
    var b: Float64 = 0.0
    var rng = _seed_state(seed)

    if n >= 2:
        var passes = 0
        var total = 0
        var hard_cap = 100 * max_passes
        while passes < max_passes and total < hard_cap:
            total += 1
            var num_changed = 0
            for i in range(n):
                var e_i = (
                    _decision_train(X, y, alphas, b, i, d, kernel_type, gamma)
                    - y[i]
                )
                var r = y[i] * e_i
                if not ((r < -tol and alphas[i] < C) or (r > tol and alphas[i] > 0.0)):
                    continue
                # Random second-choice heuristic: j != i, uniform, seeded.
                var j = _rand_below(rng, n - 1)
                if j >= i:
                    j += 1
                var e_j = (
                    _decision_train(X, y, alphas, b, j, d, kernel_type, gamma)
                    - y[j]
                )
                var a_i_old = alphas[i]
                var a_j_old = alphas[j]
                var lo: Float64
                var hi: Float64
                if y[i] * y[j] < 0.0:
                    lo = _fmax(0.0, a_j_old - a_i_old)
                    hi = _fmin(C, C + a_j_old - a_i_old)
                else:
                    lo = _fmax(0.0, a_i_old + a_j_old - C)
                    hi = _fmin(C, a_i_old + a_j_old)
                if hi - lo < 1e-12:
                    continue
                var k_ii = _kernel_ij(X, i, i, d, kernel_type, gamma)
                var k_jj = _kernel_ij(X, j, j, d, kernel_type, gamma)
                var k_ij = _kernel_ij(X, i, j, d, kernel_type, gamma)
                var eta = 2.0 * k_ij - k_ii - k_jj
                if eta >= 0.0:
                    continue
                var a_j = a_j_old - y[j] * (e_i - e_j) / eta
                if a_j > hi:
                    a_j = hi
                if a_j < lo:
                    a_j = lo
                if fabs(a_j - a_j_old) < 1e-5:
                    continue
                var a_i = a_i_old + y[i] * y[j] * (a_j_old - a_j)
                alphas[i] = a_i
                alphas[j] = a_j
                var b1 = (
                    b
                    - e_i
                    - y[i] * (a_i - a_i_old) * k_ii
                    - y[j] * (a_j - a_j_old) * k_ij
                )
                var b2 = (
                    b
                    - e_j
                    - y[i] * (a_i - a_i_old) * k_ij
                    - y[j] * (a_j - a_j_old) * k_jj
                )
                if a_i > 0.0 and a_i < C:
                    b = b1
                elif a_j > 0.0 and a_j < C:
                    b = b2
                else:
                    b = 0.5 * (b1 + b2)
                num_changed += 1
            if num_changed == 0:
                passes += 1
            else:
                passes = 0

    model.b = b
    model.alphas = alphas.copy()

    # Primal weights for the linear kernel: w = Σ α_i y_i x_i.
    if kernel_type == 0:
        for f in range(d):
            var wf: Float64 = 0.0
            for i in range(n):
                if alphas[i] != 0.0:
                    wf += alphas[i] * y[i] * X[i * d + f]
            model.w.append(wf)

    # Support vectors: rows with alpha > 1e-8; coef = alpha·y.
    for i in range(n):
        if alphas[i] > 1e-8:
            for f in range(d):
                model.support_x.append(X[i * d + f])
            model.support_coef.append(alphas[i] * y[i])
            model.n_support += 1
    return model^


# ── svm_fit_linear ───────────────────────────────────────────────────────────


fn svm_fit_linear(
    X: List[Float64],
    y: List[Float64],
    n_features: Int,
    C: Float64,
    tol: Float64,
    max_passes: Int,
    seed: Int,
) -> SVMModel:
    """Train a soft-margin linear SVM via simplified SMO.

    X flat row-major (len == len(y) * n_features), y in {-1.0, +1.0},
    C > 0 regularization, tol KKT tolerance (e.g. 1e-3), max_passes
    consecutive no-change passes before stopping, seed drives the random
    second-choice heuristic. Returns SVMModel with dual alphas, bias b,
    and primal weights w (decision = w·x + b). Empty model on bad input.
    """
    return _svm_fit(X, y, n_features, C, tol, max_passes, 0, 0.0, seed)


# ── svm_fit_rbf ──────────────────────────────────────────────────────────────


fn svm_fit_rbf(
    X: List[Float64],
    y: List[Float64],
    n_features: Int,
    C: Float64,
    tol: Float64,
    max_passes: Int,
    gamma: Float64,
    seed: Int,
) -> SVMModel:
    """Train a soft-margin RBF-kernel SVM (K = exp(-γ‖a-b‖²)) via SMO.

    Same contract as svm_fit_linear plus gamma > 0. The model keeps the
    support vectors and their alpha·y coefficients, so prediction costs
    O(n_support · n_features). Empty model on bad input.
    """
    return _svm_fit(X, y, n_features, C, tol, max_passes, 1, gamma, seed)


# ── svm_decision ─────────────────────────────────────────────────────────────


fn svm_decision(model: SVMModel, x: List[Float64]) -> Float64:
    """Raw decision value f(x). Linear: w·x + b. RBF: Σ coef_s K(x_s, x) + b.

    Missing trailing features of x are treated as 0. Empty model -> 0.0.
    """
    var d = model.n_features
    if model.kernel_type == 0:
        var s = model.b
        var m = d
        if len(x) < m:
            m = len(x)
        if len(model.w) < m:
            m = len(model.w)
        for f in range(m):
            s += model.w[f] * x[f]
        return s
    var s = model.b
    for sv in range(model.n_support):
        var sq: Float64 = 0.0
        for f in range(d):
            var xf: Float64 = 0.0
            if f < len(x):
                xf = x[f]
            var diff = model.support_x[sv * d + f] - xf
            sq += diff * diff
        s += model.support_coef[sv] * exp(-model.gamma * sq)
    return s


# ── svm_predict ──────────────────────────────────────────────────────────────


fn svm_predict(model: SVMModel, x: List[Float64]) -> Float64:
    """Class label: +1.0 if svm_decision(model, x) >= 0 else -1.0."""
    if svm_decision(model, x) >= 0.0:
        return 1.0
    return -1.0


# ── svm_predict_batch ────────────────────────────────────────────────────────


fn svm_predict_batch(model: SVMModel, X: List[Float64]) -> List[Float64]:
    """Labels for a flat row-major query matrix (n_rows * n_features).

    Returns one label in {-1.0, +1.0} per complete row; empty list if the
    model is empty (n_features == 0).
    """
    var out = List[Float64]()
    var d = model.n_features
    if d <= 0:
        return out^
    var n = len(X) // d
    for i in range(n):
        var row = List[Float64](capacity=d)
        for f in range(d):
            row.append(X[i * d + f])
        out.append(svm_predict(model, row))
    return out^
