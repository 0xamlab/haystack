"""
chaos.mojo — Chaos theory tools. Zero Python imports.

Replaces custom chaos code with pure Mojo implementations of logistic map,
Lorenz system, Lyapunov exponents, Hénon map, tent map, bifurcation
diagrams, and sensitivity analysis.

Public API:
  logistic_map               — Iterate x_{n+1} = r*x_n*(1-x_n)
  lorenz_step                — One Euler step of Lorenz system
  lorenz_simulate            — Full Lorenz trajectory
  lyapunov_exponent_logistic — Lyapunov exponent for logistic map
  henon_map                  — Hénon map iterations
  tent_map                   — Tent map iterations
  bifurcation_diagram        — Bifurcation diagram data
  sensitivity_to_initial     — Divergence of two trajectories
  feigenbaum_ratio           — δ = (r2-r1)/(r3-r2)
  is_chaotic                 — Positive Lyapunov → chaotic
"""
from std.math import log, abs as fabs, min as fmin


# ── logistic_map ─────────────────────────────────────────────────────────────


fn logistic_map(r: Float64, x0: Float64, n_steps: Int) -> List[Float64]:
    """Iterate the logistic map: x_{n+1} = r*x_n*(1-x_n).

    Args:
        r:       Growth rate parameter.
        x0:      Initial value (typically in (0,1)).
        n_steps: Number of iterations.

    Returns:
        List of x values from x0 to x_{n_steps}.
    """
    var result = List[Float64]()
    var x = x0
    result.append(x)
    for _i in range(n_steps):
        x = r * x * (1.0 - x)
        result.append(x)
    return result^


# ── lorenz_step ──────────────────────────────────────────────────────────────


fn lorenz_step(
    x: Float64,
    y: Float64,
    z: Float64,
    sigma: Float64,
    rho: Float64,
    beta: Float64,
    dt: Float64,
) -> List[Float64]:
    """One Euler step of the Lorenz system.

    Args:
        x, y, z: Current state.
        sigma:   Lorenz σ parameter.
        rho:     Lorenz ρ parameter.
        beta:    Lorenz β parameter.
        dt:      Time step.

    Returns:
        [x', y', z'] after one step.
    """
    var dx = sigma * (y - x)
    var dy = x * (rho - z) - y
    var dz = x * y - beta * z
    var result = List[Float64]()
    result.append(x + dx * dt)
    result.append(y + dy * dt)
    result.append(z + dz * dt)
    return result^


# ── lorenz_simulate ──────────────────────────────────────────────────────────


fn lorenz_simulate(
    x0: Float64,
    y0: Float64,
    z0: Float64,
    sigma: Float64,
    rho: Float64,
    beta: Float64,
    dt: Float64,
    n_steps: Int,
) -> List[List[Float64]]:
    """Full Lorenz trajectory via Euler integration.

    Args:
        x0, y0, z0: Initial state.
        sigma:       Lorenz σ parameter.
        rho:         Lorenz ρ parameter.
        beta:        Lorenz β parameter.
        dt:          Time step.
        n_steps:     Number of steps.

    Returns:
        List of [x, y, z] states.
    """
    var trajectory = List[List[Float64]]()
    var x = x0
    var y = y0
    var z = z0
    var state0 = List[Float64]()
    state0.append(x)
    state0.append(y)
    state0.append(z)
    trajectory.append(state0^)

    for _i in range(n_steps):
        var dx = sigma * (y - x)
        var dy = x * (rho - z) - y
        var dz = x * y - beta * z
        x = x + dx * dt
        y = y + dy * dt
        z = z + dz * dt
        var state = List[Float64]()
        state.append(x)
        state.append(y)
        state.append(z)
        trajectory.append(state^)

    return trajectory^


# ── lyapunov_exponent_logistic ───────────────────────────────────────────────


fn lyapunov_exponent_logistic(
    r: Float64, n_iter: Int, n_transient: Int
) -> Float64:
    """Lyapunov exponent for the logistic map.

    λ = (1/N) Σ log|r - 2*r*x_n|

    Args:
        r:           Growth rate parameter.
        n_iter:      Number of iterations to average over.
        n_transient: Transient iterations to discard.

    Returns:
        Estimated Lyapunov exponent.
    """
    var x: Float64 = 0.5
    # Transient
    for _i in range(n_transient):
        x = r * x * (1.0 - x)

    var lyap_sum: Float64 = 0.0
    for _i in range(n_iter):
        var deriv = fabs(r - 2.0 * r * x)
        if deriv > 1e-30:
            lyap_sum += log(deriv)
        else:
            lyap_sum += -69.0  # log of very small number
        x = r * x * (1.0 - x)

    return lyap_sum / Float64(n_iter)


# ── henon_map ────────────────────────────────────────────────────────────────


fn henon_map(
    a: Float64, b: Float64, x0: Float64, y0: Float64, n_steps: Int
) -> List[List[Float64]]:
    """Hénon map: x_{n+1} = 1 - a*x_n² + y_n, y_{n+1} = b*x_n.

    Args:
        a, b:     Hénon parameters.
        x0, y0:   Initial state.
        n_steps:  Number of iterations.

    Returns:
        List of [x, y] states.
    """
    var trajectory = List[List[Float64]]()
    var x = x0
    var y = y0
    var state0 = List[Float64]()
    state0.append(x)
    state0.append(y)
    trajectory.append(state0^)

    for _i in range(n_steps):
        var x_new = 1.0 - a * x * x + y
        var y_new = b * x
        x = x_new
        y = y_new
        var state = List[Float64]()
        state.append(x)
        state.append(y)
        trajectory.append(state^)

    return trajectory^


# ── tent_map ─────────────────────────────────────────────────────────────────


fn tent_map(mu: Float64, x0: Float64, n_steps: Int) -> List[Float64]:
    """Tent map: x_{n+1} = mu * min(x, 1-x).

    Args:
        mu:      Tent map parameter (typically 0 to 2).
        x0:      Initial value in [0,1].
        n_steps: Number of iterations.

    Returns:
        List of x values.
    """
    var result = List[Float64]()
    var x = x0
    result.append(x)
    for _i in range(n_steps):
        x = mu * fmin(x, 1.0 - x)
        result.append(x)
    return result^


# ── bifurcation_diagram ─────────────────────────────────────────────────────


fn bifurcation_diagram(
    r_start: Float64,
    r_end: Float64,
    n_r: Int,
    n_iter: Int,
    n_last: Int,
) -> List[List[Float64]]:
    """Generate bifurcation diagram data for the logistic map.

    Args:
        r_start: Start of r range.
        r_end:   End of r range.
        n_r:     Number of r values to sample.
        n_iter:  Total iterations per r value.
        n_last:  Number of final iterations to record.

    Returns:
        List of [r, x] pairs.
    """
    var points = List[List[Float64]]()
    var dr = (r_end - r_start) / Float64(n_r - 1) if n_r > 1 else 0.0

    for i in range(n_r):
        var r = r_start + Float64(i) * dr
        var x: Float64 = 0.5

        # Transient iterations
        var n_transient = n_iter - n_last
        for _j in range(n_transient):
            x = r * x * (1.0 - x)

        # Record last n_last values
        for _j in range(n_last):
            x = r * x * (1.0 - x)
            var point = List[Float64]()
            point.append(r)
            point.append(x)
            points.append(point^)

    return points^


# ── sensitivity_to_initial ───────────────────────────────────────────────────


fn sensitivity_to_initial(
    r: Float64, x1: Float64, x2: Float64, n_steps: Int
) -> List[Float64]:
    """Track divergence |x1_n - x2_n| of two logistic map trajectories.

    Args:
        r:       Growth rate parameter.
        x1:      First initial condition.
        x2:      Second initial condition.
        n_steps: Number of iterations.

    Returns:
        List of |x1_n - x2_n| values.
    """
    var divergence = List[Float64]()
    var a = x1
    var b = x2
    divergence.append(fabs(a - b))
    for _i in range(n_steps):
        a = r * a * (1.0 - a)
        b = r * b * (1.0 - b)
        divergence.append(fabs(a - b))
    return divergence^


# ── feigenbaum_ratio ─────────────────────────────────────────────────────────


fn feigenbaum_ratio(r1: Float64, r2: Float64, r3: Float64) -> Float64:
    """Feigenbaum ratio: δ = (r2-r1)/(r3-r2).

    Args:
        r1: First bifurcation point.
        r2: Second bifurcation point.
        r3: Third bifurcation point.

    Returns:
        Feigenbaum ratio estimate.
    """
    var denom = r3 - r2
    if fabs(denom) < 1e-30:
        return 0.0
    return (r2 - r1) / denom


# ── is_chaotic ───────────────────────────────────────────────────────────────


fn is_chaotic(lyapunov: Float64) -> Bool:
    """Determine if system is chaotic based on Lyapunov exponent.

    Args:
        lyapunov: Lyapunov exponent value.

    Returns:
        True if lyapunov > 0 (chaotic), False otherwise.
    """
    return lyapunov > 0.0
