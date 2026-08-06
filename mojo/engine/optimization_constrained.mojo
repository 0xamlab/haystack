"""
optimization_constrained.mojo — Constrained optimization. Zero Python imports.

Replaces scipy.optimize constrained methods with pure Mojo implementations
of penalty, barrier, and augmented Lagrangian methods.

Built-in objective and constraint functions by ID.

Public API:
  eval_objective_c          — Evaluate objective by ID
  eval_constraint           — Evaluate constraint by ID
  penalty_method            — Exterior penalty method
  barrier_method            — Interior barrier method
  is_feasible_c             — Check all constraints satisfied
  penalty_value             — Total constraint violation
  gradient_estimate         — Numerical gradient of penalized objective
  augmented_lagrangian_step — One step of augmented Lagrangian
"""
from std.math import sqrt, abs as fabs, log, exp


# ── Objective Functions ──────────────────────────────────────────────────────


def eval_objective_c(x: List[Float64], func_id: Int) -> Float64:
    """Evaluate objective function by ID.
    0 = x0² + x1², 1 = -(x0*x1), 2 = x0 + x1."""
    if func_id == 0:
        var s: Float64 = 0.0
        for i in range(len(x)):
            s += x[i] * x[i]
        return s
    elif func_id == 1:
        if len(x) >= 2:
            return -(x[0] * x[1])
        return 0.0
    elif func_id == 2:
        var s: Float64 = 0.0
        for i in range(len(x)):
            s += x[i]
        return s
    return 0.0


# ── Constraint Functions ─────────────────────────────────────────────────────


def eval_constraint(x: List[Float64], constraint_id: Int) -> Float64:
    """Evaluate constraint g(x) ≤ 0 by ID.
    0 = x0+x1-1, 1 = x0²+x1²-1, 2 = -x0, 3 = -x1."""
    if len(x) < 2:
        return 0.0
    if constraint_id == 0:
        return x[0] + x[1] - 1.0
    elif constraint_id == 1:
        return x[0] * x[0] + x[1] * x[1] - 1.0
    elif constraint_id == 2:
        return -x[0]
    elif constraint_id == 3:
        return -x[1]
    return 0.0


# ── Feasibility and Penalty ──────────────────────────────────────────────────


def is_feasible_c(
    x: List[Float64], constraints: List[Int], tol: Float64 = 1e-6
) -> Bool:
    """Check if all constraints g_i(x) ≤ 0 are satisfied within tolerance."""
    for i in range(len(constraints)):
        var g = eval_constraint(x, constraints[i])
        if g > tol:
            return False
    return True


def penalty_value(x: List[Float64], constraints: List[Int]) -> Float64:
    """Total constraint violation: Σ max(0, g_i(x))²."""
    var total: Float64 = 0.0
    for i in range(len(constraints)):
        var g = eval_constraint(x, constraints[i])
        if g > 0.0:
            total += g * g
    return total


# ── Penalized Objective ─────────────────────────────────────────────────────


def _penalized_objective(
    x: List[Float64],
    func_id: Int,
    constraints: List[Int],
    mu: Float64,
) -> Float64:
    """f(x) + mu * Σ max(0, g_i(x))²."""
    return eval_objective_c(x, func_id) + mu * penalty_value(x, constraints)


# ── Numerical Gradient ───────────────────────────────────────────────────────


def gradient_estimate(
    x: List[Float64],
    func_id: Int,
    constraints: List[Int],
    mu: Float64,
    h: Float64 = 1e-5,
) -> List[Float64]:
    """Numerical gradient of penalized objective via central differences."""
    var n = len(x)
    var grad = List[Float64]()
    for i in range(n):
        var xp = List[Float64]()
        var xm = List[Float64]()
        for j in range(n):
            xp.append(x[j])
            xm.append(x[j])
        xp[i] = x[i] + h
        xm[i] = x[i] - h
        var fp = _penalized_objective(xp, func_id, constraints, mu)
        var fm = _penalized_objective(xm, func_id, constraints, mu)
        grad.append((fp - fm) / (2.0 * h))
    return grad^


# ── Penalty Method ───────────────────────────────────────────────────────────


def penalty_method(
    x0: List[Float64],
    func_id: Int,
    constraints: List[Int],
    mu: Float64,
    max_iter: Int,
    lr: Float64,
) -> List[Float64]:
    """Exterior penalty method: minimize f(x) + μ*Σmax(0,g_i(x))²."""
    var n = len(x0)
    var x = List[Float64]()
    for i in range(n):
        x.append(x0[i])
    var cur_mu = mu
    for _iter in range(max_iter):
        var grad = gradient_estimate(x, func_id, constraints, cur_mu)
        for i in range(n):
            x[i] = x[i] - lr * grad[i]
        # Increase penalty every 10 iterations
        if (_iter + 1) % 10 == 0:
            cur_mu = cur_mu * 2.0
    return x^


# ── Barrier Method ───────────────────────────────────────────────────────────


def _barrier_objective(
    x: List[Float64],
    func_id: Int,
    constraints: List[Int],
    mu: Float64,
) -> Float64:
    """f(x) - mu * Σ log(-g_i(x)). Returns large value if infeasible."""
    var obj = eval_objective_c(x, func_id)
    for i in range(len(constraints)):
        var g = eval_constraint(x, constraints[i])
        if g >= 0.0:
            return 1e18  # infeasible
        obj -= mu * log(-g)
    return obj


def _barrier_gradient(
    x: List[Float64],
    func_id: Int,
    constraints: List[Int],
    mu: Float64,
    h: Float64 = 1e-5,
) -> List[Float64]:
    """Numerical gradient of barrier objective."""
    var n = len(x)
    var grad = List[Float64]()
    for i in range(n):
        var xp = List[Float64]()
        var xm = List[Float64]()
        for j in range(n):
            xp.append(x[j])
            xm.append(x[j])
        xp[i] = x[i] + h
        xm[i] = x[i] - h
        var fp = _barrier_objective(xp, func_id, constraints, mu)
        var fm = _barrier_objective(xm, func_id, constraints, mu)
        grad.append((fp - fm) / (2.0 * h))
    return grad^


def barrier_method(
    x0: List[Float64],
    func_id: Int,
    constraints: List[Int],
    mu: Float64,
    max_iter: Int,
    lr: Float64,
) -> List[Float64]:
    """Interior barrier: minimize f(x) - μ*Σlog(-g_i(x)).
    x0 must be strictly feasible."""
    var n = len(x0)
    var x = List[Float64]()
    for i in range(n):
        x.append(x0[i])
    var cur_mu = mu
    for _iter in range(max_iter):
        var grad = _barrier_gradient(x, func_id, constraints, cur_mu)
        # Line search with step clamping
        var step = lr
        var x_new = List[Float64]()
        for i in range(n):
            x_new.append(x[i] - step * grad[i])
        # Check feasibility of new point
        var feasible = True
        for i in range(len(constraints)):
            if eval_constraint(x_new, constraints[i]) >= 0.0:
                feasible = False
                break
        if feasible:
            x = x_new^
        else:
            # Halve step until feasible
            for _bt in range(20):
                step = step * 0.5
                x_new = List[Float64]()
                for i in range(n):
                    x_new.append(x[i] - step * grad[i])
                var ok = True
                for i in range(len(constraints)):
                    if eval_constraint(x_new, constraints[i]) >= 0.0:
                        ok = False
                        break
                if ok:
                    x = x_new^
                    break
        # Decrease mu every 10 iterations
        if (_iter + 1) % 10 == 0:
            cur_mu = cur_mu * 0.5
    return x^


# ── Augmented Lagrangian Step ────────────────────────────────────────────────


def augmented_lagrangian_step(
    x: List[Float64],
    lambdas: List[Float64],
    func_id: Int,
    constraints: List[Int],
    mu: Float64,
    lr: Float64,
) -> List[List[Float64]]:
    """One step of augmented Lagrangian. Returns [new_x, new_lambdas]."""
    var n = len(x)
    var nc = len(constraints)
    # Parallel lists: lambdas[ci] is read for each constraint; a short
    # lambdas aborts (uncatchable).
    if len(lambdas) < nc:
        return List[List[Float64]]()
    # Compute gradient of augmented Lagrangian numerically
    var grad = gradient_estimate(x, func_id, constraints, mu)
    # Add Lagrangian terms to gradient numerically
    var h: Float64 = 1e-5
    for i in range(n):
        var extra: Float64 = 0.0
        for ci in range(nc):
            var xp = List[Float64]()
            var xm = List[Float64]()
            for j in range(n):
                xp.append(x[j])
                xm.append(x[j])
            xp[i] = x[i] + h
            xm[i] = x[i] - h
            var gp = eval_constraint(xp, constraints[ci])
            var gm = eval_constraint(xm, constraints[ci])
            var dg = (gp - gm) / (2.0 * h)
            extra += lambdas[ci] * dg
        grad[i] = grad[i] + extra

    # Update x
    var new_x = List[Float64]()
    for i in range(n):
        new_x.append(x[i] - lr * grad[i])

    # Update lambdas: λ_i = max(0, λ_i + μ * g_i(x))
    var new_lambdas = List[Float64]()
    for i in range(nc):
        var g = eval_constraint(new_x, constraints[i])
        var lam = lambdas[i] + mu * g
        if lam < 0.0:
            lam = 0.0
        new_lambdas.append(lam)

    var result = List[List[Float64]]()
    result.append(new_x^)
    result.append(new_lambdas^)
    return result^
