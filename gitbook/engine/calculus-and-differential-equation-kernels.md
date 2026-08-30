---
icon: square-root-variable
description: Interpolation between data points, quadrature over sampled data, initial-value ODE solvers (Euler, RK4), and explicit/Jacobi finite-difference PDE solvers with their CFL stability limits.
---

# Calculus and differential equation kernels

Four modules for turning a handful of numbers -- samples on a curve, a right-hand-side polynomial,
a grid of node values -- into the continuous object calculus talks about: a value between two known
points, the area under a curve, where a state ends up after some time, or how a field evolves on a
grid. `interpolate` reads a value the data didn't give you; `integrate` sums a curve into an area;
`ode` steps a value (or a diagonal system of them) forward in time under a right-hand side of your
choosing; `pde` steps a whole grid forward instead of a single number, or relaxes it to a fixed
point. None of the four import from each other -- each is a self-contained `Float64` library
replacing one corner of `scipy` (`scipy.interpolate`, `scipy.integrate`,
`scipy.integrate.odeint`/`solve_ivp`, and a hand-written PDE stencil, respectively), per their own
module docstrings.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# integral of x^2 over [0, 4], sampled at 5 points (dx=1): Simpson's rule is exact for a quadratic
y = [0.0, 1.0, 4.0, 9.0, 16.0]
runtime.execute("integrate", "simpson", [y, 1.0])["result"]
# 21.333333333333332 -- matches the closed form, 4**3 / 3, to the last bit

# dy/dt = -0.5*y, y(0) = 2, stepped with RK4 from t=0 to t=2 at dt=0.1
r = runtime.execute("ode", "rk4_solve", [2.0, [-0.5], 0.0, 2.0, 0.1])["result"]
r["y_values"][-1]
# 0.7357589222950793 -- vs. the closed form ode.exponential_decay(2.0, 0.5, 2.0) = 0.7357588823428847
```

## The modules

| Module | What it does |
| --- | --- |
| `interpolate` | Linear, nearest-neighbor, natural cubic spline, and Lagrange polynomial interpolation between scattered `(x, y)` points, an array-batched dispatcher over those four, and linear extrapolation beyond the data range. |
| `integrate` | Numerical quadrature over sampled or exact data: trapezoidal rule, Simpson's 1/3 rule, Romberg (Richardson) extrapolation, running (cumulative) trapezoid, exact polynomial integration, and 5-point Gauss-Legendre quadrature. |
| `ode` | Euler and classical 4th-order Runge-Kutta solvers for scalar and diagonal-system initial value problems whose right-hand side is a polynomial in `y`, plus two closed-form reference solutions (exponential decay, logistic growth) to check them against. |
| `pde` | Explicit finite-difference time-stepping for the 1D heat and wave equations, Jacobi relaxation for the 2D Laplace equation, their CFL stability limits, and a few grid utilities (Gaussian bump, L∞ norm, energy, standalone second difference). |

## `interpolate`: four ways to read between the data, one way to step outside it

| Function | Signature | What it does |
| --- | --- | --- |
| `linear_interp` | `(x_data, y_data, x) -> Float64` | Piecewise-linear interpolation via binary search for the bracketing interval; **clamps** to the boundary `y` value for `x` outside `[x_data[0], x_data[n-1]]`. |
| `nearest_interp` | `(x_data, y_data, x) -> Float64` | Nearest-neighbor lookup by the same bracketing search; an exact midpoint tie goes to the **left** node (`d_left <= d_right`). |
| `cubic_spline_natural` | `(x_data, y_data, x) -> Float64` | Natural cubic spline (second derivative pinned to `0` at both ends), solved via a tridiagonal system; falls back to `linear_interp` for `n < 3` or a repeated abscissa (`\|x_data[i] - x_data[i-1]\| < 1e-15`). |
| `lagrange_interp` | `(x_data, y_data, x) -> Float64` | Lagrange polynomial through every data point; the module docstring itself flags Runge's phenomenon (oscillation) for high-degree fits. |
| `interp_array` | `(x_data, y_data, x_new, method) -> List[Float64]` | Batched interpolation over `x_new`; `method` selects `"nearest"`, `"cubic"`, `"lagrange"`, or defaults to `"linear"` for anything else, including a typo. |
| `extrapolate_linear` | `(x_data, y_data, x) -> Float64` | `linear_interp` inside the data range; outside it, extends the slope of the nearest **edge segment** (first two points on the left, last two on the right) instead of clamping. |

Every one of the five point-evaluating functions guards `len(y_data) < len(x_data)` and returns
`0.0` rather than indexing `y_data` past its own end -- the source comments call this out explicitly
as "would be read past its end below (uncatchable abort)," the same bounds-check-before-crash
pattern used throughout this corpus wherever a worker-killing abort is one array-length mismatch
away. `cubic_spline_natural` additionally screens every node for `NaN`/`Inf` before touching the
tridiagonal solve, since a non-finite node would otherwise poison every divided difference
downstream.

**Worked example** -- four points sampled from `y = x^2`, queried at `x = 1.5` (true value `2.25`):

```python
x_data = [0.0, 1.0, 2.0, 3.0]
y_data = [0.0, 1.0, 4.0, 9.0]

runtime.execute("interpolate", "linear_interp",        [x_data, y_data, 1.5])["result"]  # 2.5
runtime.execute("interpolate", "nearest_interp",       [x_data, y_data, 1.5])["result"]  # 1.0
runtime.execute("interpolate", "lagrange_interp",      [x_data, y_data, 1.5])["result"]  # 2.25
runtime.execute("interpolate", "cubic_spline_natural", [x_data, y_data, 1.5])["result"]  # 2.1999999999999997
```

`linear_interp` overshoots (`2.5 > 2.25`) because a straight chord across a convex curve always
lies above it. `lagrange_interp` is exact: a degree-`(n-1)` polynomial through `n` points sampled
from a degree-2 function reconstructs that function exactly, regardless of how many extra points
are handed to it. `cubic_spline_natural` lands close (`2.2`) but not exact, because the natural
boundary condition it enforces -- second derivative `= 0` at `x_data[0]` and `x_data[n-1]` -- is a
real constraint that `y = x^2` (constant second derivative `= 2` everywhere) does not itself
satisfy; forcing it introduces a small, correctable bias near the ends.

Boundary handling differs sharply between the "stay inside" and "go outside" functions:
`linear_interp(x_data, y_data, 5.0)` clamps to `9.0` (the last data value, since `5.0 >= x_data[3]`),
while `extrapolate_linear(x_data, y_data, 5.0)` instead extends the slope of the last segment,
`(9 - 4) / (3 - 2) = 5`, giving `9 + 5 * (5 - 3) = 19.0`. On the left edge,
`extrapolate_linear(x_data, y_data, -1.0)` uses the first segment's slope (`(1 - 0) / (1 - 0) = 1`)
to return `0 + 1 * (-1 - 0) = -1.0`.

## `integrate`: quadrature from trapezoid to Gauss-Legendre

| Function | Signature | What it does |
| --- | --- | --- |
| `trapezoid` | `(y, dx) -> Float64` | `dx * (y[0]/2 + y[1] + ... + y[n-1]/2)` for equally-spaced samples. |
| `simpson` | `(y, dx) -> Float64` | Composite Simpson's 1/3 rule; for an even point count it Simpson's the first `n-1` points and trapezoids the last interval, rather than refusing the input. |
| `romberg` | `(y, dx, max_iter=10) -> Float64` | Richardson extrapolation over a table of trapezoid estimates at halving step sizes, up to `max_iter` (or fewer) levels depending on data length. |
| `cumulative_trapezoid` | `(y, dx) -> List[Float64]` | Running trapezoid sum; returns `n - 1` partial integrals, one per interval, rather than a single total. |
| `integrate_poly` | `(coeffs, a, b) -> Float64` | Closed-form `∫ₐᵇ p(x) dx` for `p(x) = Σ coeffs[i]·x^i`, term by term -- no sampling involved. |
| `quad_gauss_legendre` | `(y_values, a, b) -> Float64` | 5-point Gauss-Legendre quadrature; if `y_values` has exactly 5 entries they are taken as function values **already at** the GL nodes, otherwise they are treated as equally-spaced samples and linearly interpolated to the GL node locations first. |

**Worked example** -- `y = x^2` sampled at 5 equally-spaced points on `[0, 4]` (`dx = 1`), true
integral `4^3 / 3 = 21.333333333333332`:

```python
y = [0.0, 1.0, 4.0, 9.0, 16.0]

runtime.execute("integrate", "trapezoid", [y, 1.0])["result"]                          # 22.0
runtime.execute("integrate", "simpson", [y, 1.0])["result"]                            # 21.333333333333332
runtime.execute("integrate", "romberg", [y, 1.0, 5])["result"]                          # 21.333333333333332
runtime.execute("integrate", "integrate_poly", [[0.0, 0.0, 1.0], 0.0, 4.0])["result"]   # 21.333333333333332
runtime.execute("integrate", "cumulative_trapezoid", [y, 1.0])["result"]                # [0.5, 3.0, 9.5, 22.0]
```

`trapezoid` overestimates by exactly `2/3` (a straight-line rule over a convex curve always does);
`simpson` and `romberg` both land on the exact value, because Simpson's rule integrates any cubic
(and therefore any quadratic) exactly, and Romberg's Richardson extrapolation on trapezoid data
eliminates the same leading error term the closed-form `integrate_poly` never had to begin with.
`cumulative_trapezoid`'s last entry (`22.0`) always agrees with a standalone `trapezoid` call over
the same data, since it is the same running sum, just retained at every step instead of only the
last one.

`quad_gauss_legendre` behaves differently depending on whether it receives exactly 5 samples.
Evaluating `y = x^2` directly at the 5 GL nodes mapped into `[0, 4]` and passing those 5 values in
gives `21.33333333333332` -- correct to 13 significant digits (5-point GL integrates polynomials up
to degree 9 exactly; the residual is ordinary floating-point roundoff, not truncation error).
Passing the same 9-point equally-spaced grid used for `dx = 0.5` above instead trips the "not
exactly 5 samples" branch, which **linearly interpolates** the grid to the GL node positions before
weighting them, and returns `21.451196665911862` -- a genuine `~0.55%` error, because linear
interpolation of a convex `x^2` between grid points is itself an approximation, layered on top of a
quadrature rule that would otherwise be exact for this integrand.

## `ode`: Euler vs. RK4, checked against two closed-form solutions

| Function | Signature | What it does |
| --- | --- | --- |
| `euler_step` | `(y, dy, dt) -> List[Float64]` | One first-order Euler step, `y + dt * dy`, for a state vector. |
| `euler_solve` | `(y0, dy_coeffs, t_span, dt) -> List[List[Float64]]` | Euler-steps a **diagonal** system, `dy_i/dt = dy_coeffs[i] * y_i`, returning every intermediate state including the initial one. |
| `rk4_step` | `(y, k_coeffs, t, dt) -> Float64` | One classical RK4 step for a scalar autonomous ODE whose right-hand side is a polynomial in `y`. |
| `rk4_solve` | `(y0, k_coeffs, t_start, t_end, dt) -> ODEResult` | Full RK4 integration; returns an `ODEResult{t_values, y_values}` including the initial point. |
| `rk4_step_system` / `rk4_solve_system` | `(y, coeffs, t, dt)` / `(y0, coeffs, t_start, t_end, dt)` | The diagonal-system analogues of `rk4_step` / `rk4_solve`, one RK4 step (or a full run) applied independently per component. |
| `exponential_decay` | `(y0, rate, t) -> Float64` | Closed form `y0 * exp(-rate * t)`, the exact solution of `dy/dt = -rate * y`. |
| `logistic_growth` | `(y0, K, r, t) -> Float64` | Closed form `K * y0 / (y0 + (K - y0) * exp(-r * t))`, the exact solution of `dy/dt = r*y*(1 - y/K)`. |

{% hint style="warning" %}
**A one-entry coefficient list means "linear," not "constant."** The private helper `_poly_eval`
that backs `rk4_step`/`rk4_solve` reads `k_coeffs` as `dy/dt = k_coeffs[0] * y` when there is
**exactly one** coefficient, and only switches to the polynomial reading
`dy/dt = k_coeffs[0] + k_coeffs[1]*y + k_coeffs[2]*y^2 + ...` once there are two or more.
Passing `[-0.5]` means "linear decay at rate 0.5," not "a constant forcing term of `-0.5`" -- that
constant-only case has to be written as `[-0.5, 0.0]` instead. `euler_solve`/`_poly_eval_system`
has no such ambiguity: a diagonal system is always `dy_i/dt = coeffs[i] * y_i`, one coefficient per
component, regardless of list length.
{% endhint %}

**Worked example** -- exponential decay, `dy/dt = -0.5*y`, `y(0) = 2`, integrated to `t = 2` at
`dt = 0.1` (20 steps):

```python
r = runtime.execute("ode", "rk4_solve", [2.0, [-0.5], 0.0, 2.0, 0.1])["result"]
r["y_values"][-1]     # 0.7357589222950793

runtime.execute("ode", "exponential_decay", [2.0, 0.5, 2.0])["result"]
# 0.7357588823428847 -- RK4 agrees to ~4e-8, the O(dt^4) global error this step size predicts

h = runtime.execute("ode", "euler_solve", [[2.0], [-0.5], 2.0, 0.1])["result"]
h[-1][0]               # 0.7169718448170844 -- off by ~0.0188, a 2.6% relative error at the same dt
```

At the identical step size, RK4's error is roughly six orders of magnitude smaller than Euler's --
the expected gap between a first-order and a fourth-order method on a well-behaved ODE, not a
difference in what problem each one is solving.

The same comparison holds on a nonlinear right-hand side. Logistic growth
`dy/dt = r*y*(1 - y/K)` expands to `k_coeffs = [0, r, -r/K]`; with `K = 10`, `r = 0.8`, `y0 = 1`,
integrated to `t = 5` at `dt = 0.1`:

```python
r2 = runtime.execute("ode", "rk4_solve", [1.0, [0.0, 0.8, -0.08], 0.0, 5.0, 0.1])["result"]
r2["y_values"][-1]    # 8.584864098624374

runtime.execute("ode", "logistic_growth", [1.0, 10.0, 0.8, 5.0])["result"]
# 8.58486449758214 -- agrees to ~4e-7
```

(The last few decimal digits above can differ by roughly `1e-8`-`1e-12` between a Mojo `exp` call
and CPython's, per this corpus's own transcendental-precision notes -- not a sign either
implementation is wrong.)

`n_steps` is never allowed to reach `0`: both `rk4_solve` and `euler_solve` (and their `_system`
variants) compute `n_steps = Int(t_span / dt)` and then force it up to `1` if that came out below
`1` -- so `t_start == t_end`, or a `dt` larger than the whole span, still takes exactly one step
rather than returning the initial condition untouched.

## `pde`: explicit time-stepping under a CFL limit, and Jacobi relaxation to steady state

| Function | Signature | What it does |
| --- | --- | --- |
| `heat_equation_1d` | `(u0, alpha, dx, dt, n_steps) -> List[Float64]` | 1D heat/diffusion equation, explicit FTCS scheme, homogeneous Dirichlet BC (`u[0] = u[n-1] = 0`, reasserted every step); returns the field at the final step. |
| `wave_equation_1d` | `(u0, v0, c, dx, dt, n_steps) -> List[Float64]` | 1D wave equation, explicit central-difference scheme with a Taylor-expansion first step from the initial velocity `v0`; same Dirichlet BC. |
| `laplace_2d` | `(u, n_iter) -> List[List[Float64]]` | 2D Laplace equation via Jacobi iteration; boundary values (row/column `0` and the last row/column) stay fixed at their input values. |
| `diffusion_cfl` | `(alpha, dx) -> Float64` | Stability limit `dt_max = dx^2 / (2*alpha)` for the heat scheme above; `1e30` (effectively unbounded) if `alpha <= 0`. |
| `wave_cfl` | `(c, dx) -> Float64` | Stability limit `dt_max = dx / c` for the wave scheme above; `1e30` if `c <= 0`. |
| `is_stable_heat` | `(alpha, dx, dt) -> Bool` | `dt <= diffusion_cfl(alpha, dx)`. |
| `finite_difference_second` | `(u, dx) -> List[Float64]` | Standalone central second difference, `(u[i+1] - 2u[i] + u[i-1]) / dx^2`; boundary entries are `0`. |
| `gaussian_initial` | `(n, center, width) -> List[Float64]` | `exp(-(x-center)^2 / width^2)` sampled at `n` points over the fixed domain `[0, 1]`. |
| `max_norm` | `(u) -> Float64` | L∞ norm, `max\|u[i]\|`. |
| `energy` | `(u, dx) -> Float64` | `Σ u[i]^2 · dx`. |

**Worked example -- heat equation, stable vs. unstable.** A unit spike `u0 = [0, 0, 1, 0, 0]` on a
5-point grid, `dx = 0.25`, `alpha = 0.5`:

```python
runtime.execute("pde", "diffusion_cfl", [0.5, 0.25])["result"]        # 0.0625 -- dt_max
runtime.execute("pde", "is_stable_heat", [0.5, 0.25, 0.05])["result"] # True  (r = alpha*dt/dx^2 = 0.4)

u0 = [0.0, 0.0, 1.0, 0.0, 0.0]
runtime.execute("pde", "heat_equation_1d", [u0, 0.5, 0.25, 0.05, 1])["result"]
# [0.0, 0.4, 0.19999999999999996, 0.4, 0.0]
runtime.execute("pde", "heat_equation_1d", [u0, 0.5, 0.25, 0.05, 5])["result"]
# [0.0, 0.09535999999999999, 0.12831999999999996, 0.09535999999999999, 0.0]
```

The spike splits into its two neighbors on step 1 and keeps flattening and spreading --
`energy(u0, 0.25) = 0.25` drops to `0.09` after just that first step, consistent with diffusion
dissipating energy rather than conserving it. Pushing `dt` to 1.5x the CFL limit (`0.09375`, where
`is_stable_heat` correctly reports `False`) and running 10 steps instead of 5 does not merely
degrade the answer -- it diverges:

```python
runtime.execute("pde", "heat_equation_1d", [u0, 0.5, 0.25, 0.09375, 10])["result"]
# [0.0, -30.30560302734375, 42.861663818359375, -30.30560302734375, 0.0]
```

An oscillating, growing solution more than 40x the original peak, from the same scheme with no
other change but the step size. The CFL bound is load-bearing here, not a suggestion.

`wave_equation_1d` behaves differently under the same kind of spike, since it propagates rather
than diffuses. With `c = 1.0`, `dx = 0.25` (`wave_cfl = 0.25`, so `dt = 0.2` keeps the Courant
number `r = c*dt/dx = 0.8` just under the stability limit) and zero initial velocity:

```python
v0 = [0.0, 0.0, 0.0, 0.0, 0.0]
runtime.execute("pde", "wave_equation_1d", [u0, v0, 1.0, 0.25, 0.2, 1])["result"]
# [0.0, 0.32000000000000006, 0.3599999999999999, 0.32000000000000006, 0.0]
runtime.execute("pde", "wave_equation_1d", [u0, v0, 1.0, 0.25, 0.2, 5])["result"]
# [0.0, -0.19535544319999987, -0.7232707584000002, -0.19535544319999987, 0.0]
```

By step 5 the field has gone negative at every interior point -- the discrete wave operator
oscillates the way an undamped wave should, where the heat scheme above only ever decayed toward
zero.

**`laplace_2d` on a single free node.** A `3x3` grid with the top boundary row fixed at `1.0` and
every other boundary value `0.0` has exactly one interior (unknown) cell, so Jacobi iteration
converges on its very first update:

```python
grid = [[1.0, 1.0, 1.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
runtime.execute("pde", "laplace_2d", [grid, 1])["result"]
# [[1.0, 1.0, 1.0], [0.0, 0.25, 0.0], [0.0, 0.0, 0.0]]
```

`0.25` is the average of that cell's four neighbors (`1, 0, 0, 0`); running 20 iterations instead
of 1 returns the identical grid, because with only one free cell there is no further coupling left
to relax. A grid with more interior cells would need many more iterations for an update to
propagate corner to corner.

`finite_difference_second` exposes the same stencil `heat_equation_1d` uses internally, standalone:
`finite_difference_second([0, 0, 1, 0, 0], 0.25)` returns `[0.0, 16.0, -32.0, 16.0, 0.0]` -- the
discrete second derivative of the spike, `(u[i+1] - 2u[i] + u[i-1]) / dx^2`, with nothing else
applied to it, so multiplying this result by `alpha * dt` and adding it back to `u` is literally
one FTCS step of `heat_equation_1d`.

{% hint style="info" %}
**The boundary is not "whatever you passed in."** Both `heat_equation_1d` and `wave_equation_1d`
overwrite the first and last entries of the working array to `0.0` at the start of every step,
regardless of what `u0[0]` or `u0[n-1]` were. An initial condition with nonzero edge values has
those values zeroed on the very first step, silently -- there is no error, no status code, and no
way to request a different boundary condition (Neumann, or a nonzero Dirichlet value) from either
function.
{% endhint %}

`laplace_2d` also has no ragged-input guard: it reads `ncols = len(u[0])` once and then indexes
every row up to `ncols - 1`, so a later row shorter than the first hits the same "index past a
list's own end" abort that `interpolate`'s functions specifically guard against with an explicit
length check. Callers need every row of `u` to already share `len(u[0])`.

## Verification

All four `mojo/tests/libs/test_*.mojo` files behind this page (`test_interpolate.mojo`,
`test_integrate.mojo`, `test_ode.mojo`, `test_pde.mojo`) are auto-generated coverage smoke tests:
every function is called once with the literal argument `0.5` (or a `[0.5, 0.6, 0.7, 0.4, 0.3]`
fixture list where a `List[Float64]` is expected), and the check is only that the result is finite
(or, for list/struct results, non-empty) -- none of the four pin a specific numeric output. Every
number in this page's worked examples was independently computed from the real formulas in
`mojo/engine/interpolate.mojo`, `integrate.mojo`, `ode.mojo`, and `pde.mojo`, re-implemented in
plain Python with no `scipy` or other library standing in for the kernel, and cross-checked against
the closed-form solutions the modules themselves provide -- `integrate_poly` as ground truth for
`integrate`'s quadrature rules, `exponential_decay`/`logistic_growth` as ground truth for `ode`'s
solvers -- rather than lifted from a test file or asserted from memory.

**Next:** [Classical ML algorithms](ml-classical-algorithms.md) is the nearest sibling in spirit --
another bundle of small, self-contained, auto-generated-smoke-tested `Float64` modules, each
replacing a different corner of `scipy`/`scikit-learn` rather than sharing a numerical core; see
the [Runtime library catalog](runtime-library-catalog.md) for every module and function.
