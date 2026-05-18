"""
convex.mojo — Convex Optimization. Zero Python imports.

Replaces cvxpy basics with pure Mojo implementations of gradient descent,
projected gradient descent, Adam optimizer, proximal operators, backtracking
line search, and vector utilities.

Public API:
  eval_function               — Evaluate objective (0=quadratic, 1=Rosenbrock)
  compute_gradient            — Compute gradient for built-in functions
  l2_norm                     — Euclidean norm
  vector_sub                  — Element-wise subtraction
  proximal_l1                 — Soft-thresholding (proximal operator for L1)
  line_search_backtrack       — Backtracking line search (Armijo condition)
  gradient_descent            — Gradient descent optimizer
  projected_gradient_descent  — Gradient descent with box constraints
  adam_optimizer              — Adam optimizer
"""

from std.math import sqrt, abs as fabs


# ── eval_function ────────────────────────────────────────────────────────────


fn eval_function(x: List[Float64], func_id: Int) -> Float64:
    """Evaluate objective function.
    func_id 0: quadratic Σx_i²
    func_id 1: Rosenbrock Σ[100(x_{i+1}-x_i²)² + (1-x_i)²]
    """
    var n = len(x)
    if func_id == 0:
        var s: Float64 = 0.0
        for i in range(n):
            s += x[i] * x[i]
        return s
    elif func_id == 1:
        var s: Float64 = 0.0
        for i in range(n - 1):
            var xi = x[i]
            var xi1 = x[i + 1]
            var a = xi1 - xi * xi
            var b = 1.0 - xi
            s += 100.0 * a * a + b * b
        return s
    return 0.0


# ── compute_gradient ─────────────────────────────────────────────────────────


fn compute_gradient(x: List[Float64], func_id: Int) -> List[Float64]:
    """Compute gradient for built-in functions.
    func_id 0: grad = 2*x_i
    func_id 1: Rosenbrock gradient
    """
    var n = len(x)
    var g = List[Float64]()
    for _ in range(n):
        g.append(0.0)

    if func_id == 0:
        for i in range(n):
            g[i] = 2.0 * x[i]
    elif func_id == 1:
        for i in range(n):
            if i < n - 1:
                var xi = x[i]
                var xi1 = x[i + 1]
                g[i] += -400.0 * xi * (xi1 - xi * xi) - 2.0 * (1.0 - xi)
            if i > 0:
                var xim1 = x[i - 1]
                g[i] += 200.0 * (x[i] - xim1 * xim1)
    return g^


# ── l2_norm ──────────────────────────────────────────────────────────────────


fn l2_norm(x: List[Float64]) -> Float64:
    """Euclidean norm: sqrt(Σx_i²)."""
    var s: Float64 = 0.0
    for i in range(len(x)):
        s += x[i] * x[i]
    return sqrt(s)


# ── vector_sub ───────────────────────────────────────────────────────────────


fn vector_sub(a: List[Float64], b: List[Float64]) -> List[Float64]:
    """Element-wise subtraction: a - b."""
    var n = len(a)
    var result = List[Float64]()
    for i in range(n):
        result.append(a[i] - b[i])
    return result^


# ── proximal_l1 ──────────────────────────────────────────────────────────────


fn proximal_l1(x: List[Float64], lambda_val: Float64) -> List[Float64]:
    """Soft-thresholding (proximal operator for L1):
    sign(x_i) * max(|x_i| - λ, 0)."""
    var n = len(x)
    var result = List[Float64]()
    for i in range(n):
        var ax = fabs(x[i])
        var shrunk = ax - lambda_val
        if shrunk < 0.0:
            shrunk = 0.0
        var sign: Float64 = 1.0
        if x[i] < 0.0:
            sign = -1.0
        elif x[i] == 0.0:
            sign = 0.0
        result.append(sign * shrunk)
    return result^


# ── line_search_backtrack ────────────────────────────────────────────────────


fn line_search_backtrack(
    x: List[Float64],
    grad: List[Float64],
    func_id: Int,
    alpha: Float64 = 1.0,
    beta: Float64 = 0.5,
    sigma: Float64 = 0.1,
) -> Float64:
    """Backtracking line search satisfying Armijo condition.
    Returns step size t such that f(x - t*grad) <= f(x) - sigma*t*||grad||²."""
    var fx = eval_function(x, func_id)
    var grad_sq: Float64 = 0.0
    for i in range(len(grad)):
        grad_sq += grad[i] * grad[i]

    var t = alpha
    var n = len(x)
    for _ in range(50):
        var x_new = List[Float64]()
        for i in range(n):
            x_new.append(x[i] - t * grad[i])
        var fx_new = eval_function(x_new, func_id)
        if fx_new <= fx - sigma * t * grad_sq:
            return t
        t *= beta
    return t


# ── gradient_descent ─────────────────────────────────────────────────────────


fn gradient_descent(
    x0: List[Float64],
    learning_rate: Float64,
    max_iter: Int,
    tol: Float64,
    func_id: Int,
) -> List[Float64]:
    """Gradient descent optimizer. Returns optimized x."""
    var n = len(x0)
    var x = List[Float64]()
    for i in range(n):
        x.append(x0[i])

    for _ in range(max_iter):
        var g = compute_gradient(x, func_id)
        var gnorm = l2_norm(g)
        if gnorm < tol:
            break
        for i in range(n):
            x[i] = x[i] - learning_rate * g[i]
    return x^


# ── projected_gradient_descent ───────────────────────────────────────────────


fn projected_gradient_descent(
    x0: List[Float64],
    lr: Float64,
    max_iter: Int,
    lower: Float64,
    upper: Float64,
    func_id: Int,
) -> List[Float64]:
    """Projected gradient descent: clamp each x_i to [lower, upper] after step."""
    var n = len(x0)
    var x = List[Float64]()
    for i in range(n):
        x.append(x0[i])

    for _ in range(max_iter):
        var g = compute_gradient(x, func_id)
        for i in range(n):
            x[i] = x[i] - lr * g[i]
            # Project onto box
            if x[i] < lower:
                x[i] = lower
            elif x[i] > upper:
                x[i] = upper
    return x^


# ── adam_optimizer ───────────────────────────────────────────────────────────


fn adam_optimizer(
    x0: List[Float64],
    lr: Float64,
    max_iter: Int,
    func_id: Int,
) -> List[Float64]:
    """Adam optimizer with β1=0.9, β2=0.999, ε=1e-8."""
    var beta1: Float64 = 0.9
    var beta2: Float64 = 0.999
    var eps: Float64 = 1e-8
    var n = len(x0)

    var x = List[Float64]()
    var m = List[Float64]()
    var v = List[Float64]()
    for i in range(n):
        x.append(x0[i])
        m.append(0.0)
        v.append(0.0)

    var b1t: Float64 = 1.0
    var b2t: Float64 = 1.0

    for _ in range(max_iter):
        var g = compute_gradient(x, func_id)
        b1t *= beta1
        b2t *= beta2

        for i in range(n):
            m[i] = beta1 * m[i] + (1.0 - beta1) * g[i]
            v[i] = beta2 * v[i] + (1.0 - beta2) * g[i] * g[i]
            var m_hat = m[i] / (1.0 - b1t)
            var v_hat = v[i] / (1.0 - b2t)
            x[i] = x[i] - lr * m_hat / (sqrt(v_hat) + eps)
    return x^
