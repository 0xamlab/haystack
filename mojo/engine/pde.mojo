"""
pde.mojo — Partial Differential Equation solvers. Zero Python imports.

Replaces custom PDE solvers with pure Mojo implementations for heat
equation, wave equation, Laplace, CFL checks, and utility functions.

Public API:
  heat_equation_1d          — 1D heat equation (explicit FTCS)
  wave_equation_1d          — 1D wave equation (explicit)
  laplace_2d                — 2D Laplace equation (Jacobi iteration)
  diffusion_cfl             — CFL stability limit for diffusion
  wave_cfl                  — CFL for wave equation
  is_stable_heat            — Check heat equation stability
  finite_difference_second  — Second derivative via central differences
  gaussian_initial          — Gaussian initial condition
  max_norm                  — L∞ norm
  energy                    — Total energy Σu²·dx
"""
from std.math import sqrt, abs as fabs, exp


# ── heat_equation_1d ───────────────────────────────────────────────────────────


fn heat_equation_1d(
    u0: List[Float64], alpha: Float64, dx: Float64, dt: Float64, n_steps: Int,
) -> List[Float64]:
    """Solve 1D heat equation using explicit FTCS scheme.

    Dirichlet BC: u[0] = u[-1] = 0.
    Returns u at final time step.
    """
    var n = len(u0)
    if n < 3:
        return u0.copy()
    var r = alpha * dt / (dx * dx)
    var u = u0.copy()
    var u_new = List[Float64]()
    for _i in range(n):
        u_new.append(0.0)

    for _step in range(n_steps):
        u_new[0] = 0.0
        u_new[n - 1] = 0.0
        for i in range(1, n - 1):
            u_new[i] = u[i] + r * (u[i + 1] - 2.0 * u[i] + u[i - 1])
        # Swap
        for i in range(n):
            u[i] = u_new[i]
    return u^


# ── wave_equation_1d ──────────────────────────────────────────────────────────


fn wave_equation_1d(
    u0: List[Float64], v0: List[Float64], c: Float64,
    dx: Float64, dt: Float64, n_steps: Int,
) -> List[Float64]:
    """Solve 1D wave equation using explicit scheme.

    v0 = initial velocity. Returns u at final time.
    Dirichlet BC: u[0] = u[-1] = 0.
    """
    var n = len(u0)
    if n < 3:
        return u0.copy()
    var r2 = (c * dt / dx) * (c * dt / dx)

    # First time step uses initial velocity
    var u_prev = u0.copy()
    var u_curr = List[Float64]()
    for _i in range(n):
        u_curr.append(0.0)

    # Step 0 -> 1 using Taylor expansion
    u_curr[0] = 0.0
    u_curr[n - 1] = 0.0
    for i in range(1, n - 1):
        u_curr[i] = (
            u_prev[i]
            + v0[i] * dt
            + 0.5 * r2 * (u_prev[i + 1] - 2.0 * u_prev[i] + u_prev[i - 1])
        )

    if n_steps <= 1:
        return u_curr^

    var u_next = List[Float64]()
    for _i in range(n):
        u_next.append(0.0)

    for _step in range(1, n_steps):
        u_next[0] = 0.0
        u_next[n - 1] = 0.0
        for i in range(1, n - 1):
            u_next[i] = (
                2.0 * u_curr[i]
                - u_prev[i]
                + r2 * (u_curr[i + 1] - 2.0 * u_curr[i] + u_curr[i - 1])
            )
        for i in range(n):
            u_prev[i] = u_curr[i]
            u_curr[i] = u_next[i]

    return u_curr^


# ── laplace_2d ─────────────────────────────────────────────────────────────────


fn laplace_2d(u: List[List[Float64]], n_iter: Int) -> List[List[Float64]]:
    """Solve 2D Laplace equation using Jacobi iteration.

    Boundary values are fixed (Dirichlet BC).
    """
    var nrows = len(u)
    if nrows < 3:
        return u.copy()

    var ncols = len(u[0])
    if ncols < 3:
        return u.copy()

    # Deep copy
    var curr = List[List[Float64]]()
    for i in range(nrows):
        var row = List[Float64]()
        for j in range(ncols):
            row.append(u[i][j])
        curr.append(row^)

    var next_ = List[List[Float64]]()
    for i in range(nrows):
        var row = List[Float64]()
        for j in range(ncols):
            row.append(u[i][j])
        next_.append(row^)

    for _it in range(n_iter):
        for i in range(1, nrows - 1):
            for j in range(1, ncols - 1):
                next_[i][j] = 0.25 * (
                    curr[i + 1][j] + curr[i - 1][j]
                    + curr[i][j + 1] + curr[i][j - 1]
                )
        for i in range(1, nrows - 1):
            for j in range(1, ncols - 1):
                curr[i][j] = next_[i][j]

    return curr^


# ── diffusion_cfl ──────────────────────────────────────────────────────────────


fn diffusion_cfl(alpha: Float64, dx: Float64) -> Float64:
    """CFL stability limit for diffusion: dt_max = dx²/(2*alpha)."""
    if alpha <= 0.0:
        return 1e30
    return dx * dx / (2.0 * alpha)


# ── wave_cfl ───────────────────────────────────────────────────────────────────


fn wave_cfl(c: Float64, dx: Float64) -> Float64:
    """CFL for wave equation: dt_max = dx/c."""
    if c <= 0.0:
        return 1e30
    return dx / c


# ── is_stable_heat ─────────────────────────────────────────────────────────────


fn is_stable_heat(alpha: Float64, dx: Float64, dt: Float64) -> Bool:
    """Check if dt ≤ dx²/(2α) for heat equation stability."""
    var dt_max = diffusion_cfl(alpha, dx)
    return dt <= dt_max


# ── finite_difference_second ───────────────────────────────────────────────────


fn finite_difference_second(u: List[Float64], dx: Float64) -> List[Float64]:
    """Second derivative via central finite differences.

    Returns (u[i+1] - 2*u[i] + u[i-1]) / dx² for interior points.
    Boundary values are set to 0.
    """
    var n = len(u)
    var result = List[Float64]()
    for _i in range(n):
        result.append(0.0)
    var dx2 = dx * dx
    for i in range(1, n - 1):
        result[i] = (u[i + 1] - 2.0 * u[i] + u[i - 1]) / dx2
    return result^


# ── gaussian_initial ───────────────────────────────────────────────────────────


fn gaussian_initial(n: Int, center: Float64, width: Float64) -> List[Float64]:
    """Gaussian initial condition: exp(-(x-center)²/width²).

    Domain [0, 1] with n grid points.
    """
    var result = List[Float64]()
    if n <= 1:
        result.append(exp(-(0.0 - center) * (0.0 - center) / (width * width)))
        return result^
    var dx = 1.0 / Float64(n - 1)
    for i in range(n):
        var x = Float64(i) * dx
        var d = x - center
        result.append(exp(-d * d / (width * width)))
    return result^


# ── max_norm ───────────────────────────────────────────────────────────────────


fn max_norm(u: List[Float64]) -> Float64:
    """Maximum absolute value (L∞ norm)."""
    var m: Float64 = 0.0
    for i in range(len(u)):
        var a = fabs(u[i])
        if a > m:
            m = a
    return m


# ── energy ─────────────────────────────────────────────────────────────────────


fn energy(u: List[Float64], dx: Float64) -> Float64:
    """Total energy: Σu²·dx."""
    var s: Float64 = 0.0
    for i in range(len(u)):
        s += u[i] * u[i] * dx
    return s
