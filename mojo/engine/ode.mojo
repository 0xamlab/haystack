"""
ode.mojo — ODE solver library. Zero Python imports.
Replaces scipy.integrate.odeint / solve_ivp.

Provides Euler and RK4 solvers for systems of ODEs defined by polynomial
coefficient vectors, plus analytical solutions for common ODE patterns.

Public API:
  ODEResult          — struct holding t_values and y_values
  euler_step         — single Euler step for a system
  euler_solve        — solve dy/dt = coeffs*y over time using Euler method
  rk4_step           — single RK4 step for dy/dt = f(t,y) (polynomial form)
  rk4_solve          — full RK4 integration returning ODEResult
  exponential_decay  — analytical y0*exp(-rate*t)
  logistic_growth    — analytical K*y0 / (y0 + (K-y0)*exp(-r*t))
"""
from std.math import sqrt, exp, log, abs as fabs


# ── Result struct ─────────────────────────────────────────────────────────────


struct ODEResult(Copyable, Movable):
    """Result of an ODE integration: stores parallel t and y arrays."""

    var t_values: List[Float64]
    var y_values: List[Float64]

    fn __init__(out self):
        self.t_values = List[Float64]()
        self.y_values = List[Float64]()


# ── Helper: evaluate polynomial ODE  f(t, y) = sum(coeffs[i] * y^i) ─────────


fn _poly_eval(y: Float64, coeffs: List[Float64]) -> Float64:
    """Evaluate dy/dt = coeffs[0] + coeffs[1]*y + coeffs[2]*y^2 + ...
    For a simple linear ODE like dy/dt = -0.5*y, pass coeffs = [-0.5]
    which is interpreted as coeffs[0]*y^1 (i.e. first coefficient multiplies y).

    Convention:
      - If len(coeffs) == 1: dy/dt = coeffs[0] * y   (linear ODE)
      - If len(coeffs) > 1:  dy/dt = coeffs[0] + coeffs[1]*y + coeffs[2]*y^2 + ...
    """
    var n = len(coeffs)
    if n == 0:
        return 0.0
    # Single coefficient → linear: dy/dt = c * y
    if n == 1:
        return coeffs[0] * y

    # Polynomial: dy/dt = c0 + c1*y + c2*y^2 + ...
    var result: Float64 = 0.0
    var y_pow: Float64 = 1.0
    for i in range(n):
        result += coeffs[i] * y_pow
        y_pow *= y
    return result


fn _poly_eval_system(y: List[Float64], coeffs: List[Float64]) -> List[Float64]:
    """For a system of equations, evaluate dy_i/dt = coeffs[i] * y_i.
    This is a simple diagonal system where each variable evolves independently."""
    var n = len(y)
    var dy = List[Float64]()
    for i in range(n):
        if i < len(coeffs):
            dy.append(coeffs[i] * y[i])
        else:
            dy.append(0.0)
    return dy^


# ── Euler method ──────────────────────────────────────────────────────────────


fn euler_step(y: List[Float64], dy: List[Float64], dt: Float64) -> List[Float64]:
    """Single Euler step: y_new = y + dt * dy.

    Args:
        y:  Current state vector.
        dy: Derivative vector (dy/dt evaluated at current state).
        dt: Time step size.

    Returns:
        New state vector after one Euler step.
    """
    var n = len(y)
    var y_new = List[Float64]()
    for i in range(n):
        if i < len(dy):
            y_new.append(y[i] + dt * dy[i])
        else:
            y_new.append(y[i])
    return y_new^


fn euler_solve(
    y0: List[Float64],
    dy_coeffs: List[Float64],
    t_span: Float64,
    dt: Float64,
) -> List[List[Float64]]:
    """Solve dy/dt = coeffs*y over time using Euler method.

    Each component evolves as dy_i/dt = dy_coeffs[i] * y_i (diagonal system).

    Args:
        y0:        Initial state vector.
        dy_coeffs: Coefficient for each state variable.
        t_span:    Total integration time.
        dt:        Time step size.

    Returns:
        List of state vectors at each time step (including initial).
    """
    var n_steps = Int(t_span / dt)
    if n_steps < 1:
        n_steps = 1

    var history = List[List[Float64]]()
    # Store initial state
    var y_curr = List[Float64]()
    for i in range(len(y0)):
        y_curr.append(y0[i])
    history.append(y_curr.copy())

    for step in range(n_steps):
        var dy = _poly_eval_system(y_curr, dy_coeffs)
        y_curr = euler_step(y_curr, dy, dt)
        history.append(y_curr.copy())

    return history^


# ── Runge-Kutta 4th order ────────────────────────────────────────────────────


fn rk4_step(y: Float64, k_coeffs: List[Float64], t: Float64, dt: Float64) -> Float64:
    """Single RK4 step for dy/dt = f(t, y) where f is polynomial in y.

    The ODE is defined by k_coeffs:
      - len==1: dy/dt = k_coeffs[0] * y  (linear)
      - len>1:  dy/dt = k_coeffs[0] + k_coeffs[1]*y + k_coeffs[2]*y^2 + ...

    Args:
        y:        Current value.
        k_coeffs: Polynomial coefficients defining the ODE.
        t:        Current time (used for interface; polynomial ODE is autonomous).
        dt:       Time step.

    Returns:
        New value of y after one RK4 step.
    """
    var k1 = _poly_eval(y, k_coeffs)
    var k2 = _poly_eval(y + 0.5 * dt * k1, k_coeffs)
    var k3 = _poly_eval(y + 0.5 * dt * k2, k_coeffs)
    var k4 = _poly_eval(y + dt * k3, k_coeffs)
    return y + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


fn rk4_solve(
    y0: Float64,
    k_coeffs: List[Float64],
    t_start: Float64,
    t_end: Float64,
    dt: Float64,
) -> ODEResult:
    """Full RK4 integration returning ODEResult with t_values and y_values.

    Args:
        y0:       Initial value at t_start.
        k_coeffs: Polynomial coefficients defining the ODE.
        t_start:  Start time.
        t_end:    End time.
        dt:       Time step.

    Returns:
        ODEResult with t_values and y_values including the initial point.
    """
    var n_steps = Int((t_end - t_start) / dt)
    if n_steps < 1:
        n_steps = 1

    var result = ODEResult()

    var t = t_start
    var y = y0
    result.t_values.append(t)
    result.y_values.append(y)

    for i in range(n_steps):
        y = rk4_step(y, k_coeffs, t, dt)
        t = t_start + Float64(i + 1) * dt
        result.t_values.append(t)
        result.y_values.append(y)

    return result^


# ── Analytical solutions ─────────────────────────────────────────────────────


fn exponential_decay(y0: Float64, rate: Float64, t: Float64) -> Float64:
    """Analytical solution for exponential decay: y(t) = y0 * exp(-rate * t).

    Solves dy/dt = -rate * y with y(0) = y0.

    Args:
        y0:   Initial value.
        rate: Decay rate (positive).
        t:    Time.

    Returns:
        Value at time t.
    """
    return y0 * exp(-rate * t)


fn logistic_growth(y0: Float64, K: Float64, r: Float64, t: Float64) -> Float64:
    """Analytical solution for logistic growth:
    y(t) = K * y0 / (y0 + (K - y0) * exp(-r * t))

    Solves dy/dt = r * y * (1 - y/K) with y(0) = y0.

    Args:
        y0: Initial population.
        K:  Carrying capacity.
        r:  Growth rate.
        t:  Time.

    Returns:
        Population at time t.
    """
    return K * y0 / (y0 + (K - y0) * exp(-r * t))


# ── RK4 for systems (bonus) ──────────────────────────────────────────────────


fn rk4_step_system(
    y: List[Float64], coeffs: List[Float64], t: Float64, dt: Float64
) -> List[Float64]:
    """Single RK4 step for a diagonal system dy_i/dt = coeffs[i]*y_i.

    Args:
        y:      Current state vector.
        coeffs: Coefficient for each component.
        t:      Current time.
        dt:     Time step.

    Returns:
        New state vector after one RK4 step.
    """
    var n = len(y)

    # k1
    var k1 = _poly_eval_system(y, coeffs)

    # y + 0.5*dt*k1
    var y2 = List[Float64]()
    for i in range(n):
        y2.append(y[i] + 0.5 * dt * k1[i])
    var k2 = _poly_eval_system(y2, coeffs)

    # y + 0.5*dt*k2
    var y3 = List[Float64]()
    for i in range(n):
        y3.append(y[i] + 0.5 * dt * k2[i])
    var k3 = _poly_eval_system(y3, coeffs)

    # y + dt*k3
    var y4 = List[Float64]()
    for i in range(n):
        y4.append(y[i] + dt * k3[i])
    var k4 = _poly_eval_system(y4, coeffs)

    # Combine
    var y_new = List[Float64]()
    for i in range(n):
        y_new.append(
            y[i] + (dt / 6.0) * (k1[i] + 2.0 * k2[i] + 2.0 * k3[i] + k4[i])
        )
    return y_new^


fn rk4_solve_system(
    y0: List[Float64],
    coeffs: List[Float64],
    t_start: Float64,
    t_end: Float64,
    dt: Float64,
) -> List[List[Float64]]:
    """Full RK4 integration for a diagonal system.

    Args:
        y0:      Initial state vector.
        coeffs:  Coefficient for each component.
        t_start: Start time.
        t_end:   End time.
        dt:      Time step.

    Returns:
        List of state vectors at each time step.
    """
    var n_steps = Int((t_end - t_start) / dt)
    if n_steps < 1:
        n_steps = 1

    var history = List[List[Float64]]()
    var y_curr = List[Float64]()
    for i in range(len(y0)):
        y_curr.append(y0[i])
    history.append(y_curr.copy())

    var t = t_start
    for step in range(n_steps):
        y_curr = rk4_step_system(y_curr, coeffs, t, dt)
        t = t_start + Float64(step + 1) * dt
        history.append(y_curr.copy())

    return history^
