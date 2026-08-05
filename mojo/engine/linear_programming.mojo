"""
linear_programming.mojo — Linear programming for 2-variable problems.
Replaces scipy.optimize.linprog for simple LP. Zero Python imports.

Public API:
  lp_solve_2var, is_feasible, objective_value, dual_value,
  sensitivity_rhs, line_intersection_2d, enumerate_vertices_2d,
  transportation_cost
"""
from std.math import abs as fabs, isnan, isinf


# ── Helpers ───────────────────────────────────────────────────────────────────


fn _inf() -> Float64:
    return 1e308


# ── Line Intersection ─────────────────────────────────────────────────────────


fn line_intersection_2d(
    a1: Float64, b1: Float64, c1: Float64,
    a2: Float64, b2: Float64, c2: Float64,
) -> List[Float64]:
    """Solve a1*x + b1*y = c1, a2*x + b2*y = c2.
    Returns [x, y] or empty list if parallel."""
    var det = a1 * b2 - a2 * b1
    if fabs(det) < 1e-12:
        return List[Float64]()
    var x = (c1 * b2 - c2 * b1) / det
    var y = (a1 * c2 - a2 * c1) / det
    var result = List[Float64]()
    result.append(x)
    result.append(y)
    return result^


# ── Feasibility ───────────────────────────────────────────────────────────────


fn is_feasible(
    x: List[Float64],
    A: List[List[Float64]],
    b: List[Float64],
) -> Bool:
    """Check if x satisfies Ax <= b and x >= 0."""
    var n = len(x)
    for j in range(n):
        if x[j] < -1e-9:
            return False
    var m = len(A)
    # b[i] is read below for every constraint; a short b would be read past
    # its end (uncatchable abort). Treat a malformed system as infeasible.
    if len(b) < m:
        return False
    for i in range(m):
        var s: Float64 = 0.0
        var cols = len(A[i])
        for j in range(cols):
            if j < n:
                s += A[i][j] * x[j]
        if s > b[i] + 1e-9:
            return False
    return True


# ── Objective Value ───────────────────────────────────────────────────────────


fn objective_value(c: List[Float64], x: List[Float64]) -> Float64:
    """Compute c·x."""
    var s: Float64 = 0.0
    var n = len(c)
    for i in range(n):
        if i < len(x):
            s += c[i] * x[i]
    return s


# ── Vertex Enumeration ────────────────────────────────────────────────────────


fn enumerate_vertices_2d(
    A: List[List[Float64]],
    b: List[Float64],
) -> List[List[Float64]]:
    """Find all feasible vertices for 2-variable LP.
    Considers intersections of constraint lines a*x + b*y = b_i,
    x-axis (y=0), and y-axis (x=0)."""
    var m = len(A)
    var vertices = List[List[Float64]]()
    # A[i][0], A[i][1] and b[i] are read below for every constraint; a short
    # b or a row with fewer than 2 columns would be read past its end
    # (uncatchable abort).
    if len(b) < m:
        return vertices^
    for i in range(m):
        if len(A[i]) < 2:
            return vertices^

    # Build extended system: original constraints + axes x=0, y=0
    var all_a1 = List[Float64]()
    var all_b1 = List[Float64]()
    var all_c1 = List[Float64]()
    for i in range(m):
        all_a1.append(A[i][0])
        all_b1.append(A[i][1])
        all_c1.append(b[i])
    # x = 0  →  1*x + 0*y = 0
    all_a1.append(1.0)
    all_b1.append(0.0)
    all_c1.append(0.0)
    # y = 0  →  0*x + 1*y = 0
    all_a1.append(0.0)
    all_b1.append(1.0)
    all_c1.append(0.0)

    var total = len(all_a1)
    for i in range(total):
        for j in range(i + 1, total):
            var pt = line_intersection_2d(
                all_a1[i], all_b1[i], all_c1[i],
                all_a1[j], all_b1[j], all_c1[j],
            )
            if len(pt) == 2:
                var xv = List[Float64]()
                xv.append(pt[0])
                xv.append(pt[1])
                if is_feasible(xv, A, b):
                    # Check not duplicate
                    var dup = False
                    for k in range(len(vertices)):
                        if fabs(vertices[k][0] - pt[0]) < 1e-9 and fabs(vertices[k][1] - pt[1]) < 1e-9:
                            dup = True
                            break
                    if not dup:
                        vertices.append(xv^)
    return vertices^


# ── LP Solver (2-var) ─────────────────────────────────────────────────────────


fn lp_solve_2var(
    c: List[Float64],
    A: List[List[Float64]],
    b: List[Float64],
) -> List[Float64]:
    """Solve 2-variable LP: maximize c·x s.t. Ax <= b, x >= 0.
    Returns [x1, x2, objective_value]. Empty if infeasible."""
    var verts = enumerate_vertices_2d(A, b)
    if len(verts) == 0:
        return List[Float64]()

    var best_val = -_inf()
    var best_idx: Int = 0
    for i in range(len(verts)):
        var val = objective_value(c, verts[i])
        if val > best_val:
            best_val = val
            best_idx = i

    var result = List[Float64]()
    result.append(verts[best_idx][0])
    result.append(verts[best_idx][1])
    result.append(best_val)
    return result^


# ── Dual Value (weak duality bound) ──────────────────────────────────────────


fn dual_value(
    A: List[List[Float64]],
    b: List[Float64],
    c: List[Float64],
) -> Float64:
    """Weak duality bound: optimal primal value via vertex enumeration.
    For 2-var problems strong duality holds at optimum."""
    var sol = lp_solve_2var(c, A, b)
    if len(sol) == 0:
        return 0.0
    return sol[2]


# ── Sensitivity Analysis ─────────────────────────────────────────────────────


fn sensitivity_rhs(
    c: List[Float64],
    A: List[List[Float64]],
    b: List[Float64],
    constraint_idx: Int,
    delta: Float64,
) -> Float64:
    """Change in optimal objective when b[constraint_idx] changes by delta."""
    var orig = lp_solve_2var(c, A, b)
    var orig_val: Float64 = 0.0
    if len(orig) >= 3:
        orig_val = orig[2]

    var b_new = List[Float64]()
    for i in range(len(b)):
        if i == constraint_idx:
            b_new.append(b[i] + delta)
        else:
            b_new.append(b[i])

    var new_sol = lp_solve_2var(c, A, b_new)
    var new_val: Float64 = 0.0
    if len(new_sol) >= 3:
        new_val = new_sol[2]

    return new_val - orig_val


# ── Transportation Cost (Northwest Corner) ───────────────────────────────────


fn transportation_cost(
    supply: List[Float64],
    demand: List[Float64],
    costs: List[List[Float64]],
) -> Float64:
    """Northwest corner method for transportation problem.
    Returns initial feasible solution cost."""
    var m = len(supply)
    var n = len(demand)
    if m == 0 or n == 0:
        return 0.0
    # costs[i][j] is read for every cell (i<m, j<n); a short costs or narrow
    # row would be read past its end (uncatchable abort). A non-finite
    # supply/demand stalls the northwest-corner walk — NaN never satisfies an
    # advance condition — so refuse it.
    if len(costs) < m:
        return 0.0
    for i in range(m):
        if len(costs[i]) < n:
            return 0.0
        if isnan(supply[i]) or isinf(supply[i]):
            return 0.0
    for j in range(n):
        if isnan(demand[j]) or isinf(demand[j]):
            return 0.0

    # Copy supply/demand
    var s = List[Float64]()
    for i in range(m):
        s.append(supply[i])
    var d = List[Float64]()
    for j in range(n):
        d.append(demand[j])

    var total_cost: Float64 = 0.0
    var i: Int = 0
    var j: Int = 0
    while i < m and j < n:
        var ship: Float64 = s[i]
        if d[j] < ship:
            ship = d[j]
        total_cost += ship * costs[i][j]
        s[i] = s[i] - ship
        d[j] = d[j] - ship
        if s[i] < 1e-12:
            i += 1
        if j < n and d[j] < 1e-12:
            j += 1
    return total_cost
