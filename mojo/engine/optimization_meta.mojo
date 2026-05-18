"""
optimization_meta.mojo — Metaheuristic optimization. Zero Python imports.

Replaces scipy.optimize + custom metaheuristic code with pure Mojo
implementations of SA, PSO, hill climbing, and random search.

Built-in objectives: 0=sphere, 1=Rastrigin, 2=Ackley.

Public API:
  eval_objective, simulated_annealing, particle_swarm,
  random_search, hill_climbing, acceptance_probability, neighbor
"""
from std.math import sqrt, abs as fabs, pow, log, exp, cos
from std.random import random_float64


# ── Constants ────────────────────────────────────────────────────────────────

comptime PI: Float64 = 3.141592653589793
comptime E_CONST: Float64 = 2.718281828459045


# ── Objective Functions ──────────────────────────────────────────────────────


fn eval_objective(x: List[Float64], func_id: Int) -> Float64:
    """Evaluate objective function.
    0 = sphere (Σx²), 1 = Rastrigin, 2 = Ackley."""
    var n = len(x)
    if func_id == 0:
        # Sphere
        var s: Float64 = 0.0
        for i in range(n):
            s += x[i] * x[i]
        return s
    elif func_id == 1:
        # Rastrigin: 10n + Σ(x² - 10*cos(2πx))
        var s: Float64 = 10.0 * Float64(n)
        for i in range(n):
            s += x[i] * x[i] - 10.0 * cos(2.0 * PI * x[i])
        return s
    else:
        # Ackley
        var sum_sq: Float64 = 0.0
        var sum_cos: Float64 = 0.0
        for i in range(n):
            sum_sq += x[i] * x[i]
            sum_cos += cos(2.0 * PI * x[i])
        var nd = Float64(n)
        var t1 = -20.0 * exp(-0.2 * sqrt(sum_sq / nd))
        var t2 = -exp(sum_cos / nd)
        return t1 + t2 + 20.0 + E_CONST


# ── Acceptance Probability ───────────────────────────────────────────────────


fn acceptance_probability(
    current_cost: Float64, new_cost: Float64, temperature: Float64
) -> Float64:
    """SA acceptance probability. If new_cost < current_cost → 1.0,
    else exp(-(new_cost - current_cost) / temperature)."""
    if new_cost < current_cost:
        return 1.0
    if temperature <= 0.0:
        return 0.0
    var delta = new_cost - current_cost
    return exp(-delta / temperature)


# ── Neighbor Generation ──────────────────────────────────────────────────────


fn neighbor(x: List[Float64], step_size: Float64) -> List[Float64]:
    """Generate random neighbor by adding uniform noise in [-step, +step]."""
    var result = List[Float64]()
    for i in range(len(x)):
        var noise = (random_float64() * 2.0 - 1.0) * step_size
        result.append(x[i] + noise)
    return result^


# ── Simulated Annealing ─────────────────────────────────────────────────────


fn simulated_annealing(
    x0: List[Float64],
    func_id: Int,
    temp: Float64,
    cooling: Float64,
    max_iter: Int,
) -> List[Float64]:
    """Simulated annealing optimizer. Returns best x found."""
    var dim = len(x0)
    var current = List[Float64]()
    for i in range(dim):
        current.append(x0[i])
    var current_cost = eval_objective(current, func_id)

    var best = List[Float64]()
    for i in range(dim):
        best.append(x0[i])
    var best_cost = current_cost

    var t = temp
    for _ in range(max_iter):
        var step = t * 0.1
        if step < 0.001:
            step = 0.001
        var candidate = neighbor(current, step)
        var candidate_cost = eval_objective(candidate, func_id)
        var ap = acceptance_probability(current_cost, candidate_cost, t)
        if random_float64() < ap:
            current = candidate^
            current_cost = candidate_cost
        if current_cost < best_cost:
            best_cost = current_cost
            best = List[Float64]()
            for i in range(len(current)):
                best.append(current[i])
        t *= cooling
    return best^


# ── Particle Swarm Optimization ──────────────────────────────────────────────


fn particle_swarm(
    n_particles: Int,
    dim: Int,
    func_id: Int,
    max_iter: Int,
    bounds_lo: Float64,
    bounds_hi: Float64,
) -> List[Float64]:
    """PSO optimizer. Returns best position found."""
    var w: Float64 = 0.7
    var c1: Float64 = 1.5
    var c2: Float64 = 1.5
    var span = bounds_hi - bounds_lo

    # Initialize particles
    var positions = List[List[Float64]]()
    var velocities = List[List[Float64]]()
    var pbest = List[List[Float64]]()
    var pbest_cost = List[Float64]()

    for _ in range(n_particles):
        var pos = List[Float64]()
        var vel = List[Float64]()
        for _ in range(dim):
            pos.append(bounds_lo + random_float64() * span)
            vel.append((random_float64() * 2.0 - 1.0) * span * 0.1)
        var pb = List[Float64]()
        for j in range(dim):
            pb.append(pos[j])
        pbest_cost.append(eval_objective(pos, func_id))
        positions.append(pos^)
        velocities.append(vel^)
        pbest.append(pb^)

    # Find global best
    var gbest = List[Float64]()
    for j in range(dim):
        gbest.append(pbest[0][j])
    var gbest_cost = pbest_cost[0]
    for i in range(1, n_particles):
        if pbest_cost[i] < gbest_cost:
            gbest_cost = pbest_cost[i]
            gbest = List[Float64]()
            for j in range(dim):
                gbest.append(pbest[i][j])

    # Main loop
    for _ in range(max_iter):
        for i in range(n_particles):
            for j in range(dim):
                var r1 = random_float64()
                var r2 = random_float64()
                velocities[i][j] = (
                    w * velocities[i][j]
                    + c1 * r1 * (pbest[i][j] - positions[i][j])
                    + c2 * r2 * (gbest[j] - positions[i][j])
                )
                positions[i][j] += velocities[i][j]
                # Clamp
                if positions[i][j] < bounds_lo:
                    positions[i][j] = bounds_lo
                if positions[i][j] > bounds_hi:
                    positions[i][j] = bounds_hi
            var cost = eval_objective(positions[i], func_id)
            if cost < pbest_cost[i]:
                pbest_cost[i] = cost
                for j in range(dim):
                    pbest[i][j] = positions[i][j]
                if cost < gbest_cost:
                    gbest_cost = cost
                    for j in range(dim):
                        gbest[j] = positions[i][j]
    return gbest^


# ── Random Search ────────────────────────────────────────────────────────────


fn random_search(
    dim: Int,
    func_id: Int,
    n_samples: Int,
    bounds_lo: Float64,
    bounds_hi: Float64,
) -> List[Float64]:
    """Random search baseline. Returns best position found."""
    var span = bounds_hi - bounds_lo
    var best = List[Float64]()
    for _ in range(dim):
        best.append(bounds_lo + random_float64() * span)
    var best_cost = eval_objective(best, func_id)

    for _ in range(n_samples - 1):
        var candidate = List[Float64]()
        for _ in range(dim):
            candidate.append(bounds_lo + random_float64() * span)
        var cost = eval_objective(candidate, func_id)
        if cost < best_cost:
            best_cost = cost
            best = candidate^
    return best^


# ── Hill Climbing ────────────────────────────────────────────────────────────


fn hill_climbing(
    x0: List[Float64],
    func_id: Int,
    step_size: Float64,
    max_iter: Int,
) -> List[Float64]:
    """Stochastic hill climbing (minimization). Returns best x found."""
    var current = List[Float64]()
    for i in range(len(x0)):
        current.append(x0[i])
    var current_cost = eval_objective(current, func_id)

    for _ in range(max_iter):
        var candidate = neighbor(current, step_size)
        var candidate_cost = eval_objective(candidate, func_id)
        if candidate_cost < current_cost:
            current = candidate^
            current_cost = candidate_cost
    return current^
