---
icon: sliders
description: Constrained nonlinear optimization by penalty/barrier/Lagrangian methods, four metaheuristic search strategies, scalar root-finding and minimization on polynomials, and ten modern deep-learning optimizer update rules.
---

# General-purpose optimization kernels

Four modules that sit underneath the structured `optimization.*`/`optmodel.*` programs
([Optimization & decision programs](optimization.md),
[Optimization benchmark plane](optimization-model-formulation.md)) rather than inside them: none
of the four takes a linear or integer program as input, and none returns a status code from that
family's vocabulary. `optimization_constrained` minimizes a nonlinear objective subject to
inequality constraints by penalty, barrier, and augmented-Lagrangian methods. `optimization_meta`
searches the same kind of nonlinear landscape by simulated annealing, particle swarm, hill
climbing, and random sampling — no gradient required. `optimize` is a small scalar toolbox:
golden-section and Brent minimization, bisection and Newton root-finding, one-dimensional
gradient descent, all operating on **polynomials** passed as coefficient lists rather than
arbitrary callables, plus a single-predictor least-squares fit bundled in alongside them. And
`optimizer_full` is a second suite of deep-learning parameter-update rules — Adadelta, Nadam,
Sophia, Prodigy, Adan, schedule-free SGD, Muon, gradient centralization, and the L-BFGS two-loop
scale — that complements rather than repeats the classic-optimizer suite already documented in
[Autograd and training-stability kernels](autograd-and-training-stability-kernels.md).

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Newton-Raphson root of f(x) = x² - 4, starting from x0 = 3.
# f_coeffs = [-4, 0, 1] means f(x) = -4 + 0·x + 1·x²
out = runtime.execute("optimize", "root_newton", [3.0, [-4.0, 0.0, 1.0]])["result"]
out["x"]            # 2.0 -- converges to the positive root
out["converged"]    # True
out["iterations"]   # 5
```

## The modules

| Module | What it does |
| --- | --- |
| `optimization_constrained` | Penalty, barrier, and augmented-Lagrangian methods for constrained nonlinear minimization over three built-in objectives and four built-in inequality constraints; feasibility checking, total constraint violation, and central-difference gradients of the penalized/barrier objective. |
| `optimization_meta` | Simulated annealing, particle swarm optimization, stochastic hill climbing, and random search over three built-in benchmark landscapes (sphere, Rastrigin, Ackley); SA's acceptance-probability formula and the shared random-neighbor generator are exposed as their own functions. |
| `optimize` | Golden-section search, Brent's method, bisection and Newton root-finding, and 1D gradient descent — all operating on a polynomial supplied as its coefficient list via Horner's method — plus a closed-form single-predictor OLS fit (slope, intercept, R²). |
| `optimizer_full` | Ten scalar parameter-update-rule formulas from deep-learning optimization research: Adadelta, Nadam, Sophia (with its Hessian-diagonal clip), Prodigy's learning-rate-free `d` estimate, Adan, schedule-free SGD (Defazio 2024), Muon's orthogonalized-gradient step, gradient centralization, and the L-BFGS two-loop-recursion initial Hessian scale. |

## Why these four modules take IDs and coefficients instead of functions

Every solver in this family runs inside the Mojo runtime and is invoked over the same
two-argument-positional-list wire protocol as everything else in this corpus — there is no way to
serialize an arbitrary Python callable across that boundary. Each module works around this
differently, and the workaround is part of the module's real scope, not an implementation detail
to skip past:

* `optimization_constrained` and `optimization_meta` each hardcode their **own** small, fixed set
  of test problems, selected by an integer `func_id`/`constraint_id`. They do not share a
  benchmark suite: `optimization_constrained`'s three objectives are `0 = x0²+x1²`,
  `1 = -(x0·x1)`, `2 = x0+x1`, with four constraints `g(x) ≤ 0` (`0 = x0+x1-1`, `1 = x0²+x1²-1`,
  `2 = -x0`, `3 = -x1`); `optimization_meta`'s three objectives are the classic global-optimization
  benchmarks sphere (`Σx²`), Rastrigin (`10n + Σ(x²-10cos(2πx))`), and Ackley. Both sets are
  distinct again from the unconstrained sandbox's own two hardcoded functions (quadratic and
  Rosenbrock) in [Combinatorics, convex optimization, and scipy-compatibility
  kernels](combinatorics-convex-optimization-and-scipy-compat-kernels.md)'s `convex` module — three
  modules, three unrelated fixed test suites, none of them interchangeable with either of the
  others.
* `optimize` instead accepts a genuine, arbitrary one-dimensional function — but only from the
  family of polynomials, represented as `f_coeffs = [a0, a1, a2, ...]` for
  `f(x) = a0 + a1·x + a2·x² + ...` and evaluated by Horner's method in `eval_poly`/
  `eval_poly_deriv`. That is a real generalization over the other two modules' fixed IDs (any
  polynomial the caller can name), bought at the cost of not covering non-polynomial objectives.
* `optimizer_full` (like the `gradient_descent` module it complements) sidesteps the problem
  entirely: every function is a **pure scalar update rule** — given the current parameter, the
  current gradient, and whatever per-optimizer running statistics that rule needs (momentum,
  second-moment estimate, Hessian diagonal, EMA state), it returns the one updated number. The
  caller supplies the gradient from wherever it comes from — there is no objective function inside
  this module at all, so the "what is being optimized" question never arises.

## `optimization_constrained`: three fixed test problems, three classical methods

```python
# Minimize x0²+x1² subject to x0²+x1²≤1, x0≥0, x1≥0, starting from a strictly
# interior point (0.3, 0.3) — the interior barrier method.
before = runtime.execute("optimization_constrained", "eval_objective_c", [[0.3, 0.3], 0])["result"]
after_x = runtime.execute("optimization_constrained", "barrier_method",
                          [[0.3, 0.3], 0, [1, 2, 3], 1.0, 50, 0.01])["result"]
after = runtime.execute("optimization_constrained", "eval_objective_c", [after_x, 0])["result"]
before, after_x, after
# 0.18, [0.27405459519664305, 0.2740545951965598], 0.1502118422967461
```

Fifty steps of the interior barrier method move the sphere objective from `0.18` down to
`0.1502...`, and every constraint stays strictly satisfied at the end
(`x0²+x1²-1 = -0.8498`, `-x0 = -0.2741`, `-x1 = -0.2741` — all negative). This is the defining
behavior of a barrier method versus a penalty method: `barrier_method` requires a strictly
feasible `x0` and can never cross a constraint boundary, because `_barrier_objective` returns
`1e18` the instant any `g(x) ≥ 0` and the line-search step is halved (up to 20 times) rather than
accepted whenever the trial point would violate a constraint. `penalty_method`, by contrast, is
allowed to start infeasible and cross the boundary freely — its only cost for violating a
constraint is the squared-violation penalty term `μ·Σmax(0, g_i(x))²` added to the objective, which
grows every 10 iterations as `μ *= 2`.

```python
# Minimize x0+x1 on the unit disk x0²+x1²≤1 by the exterior penalty method,
# starting from an interior point (0.5, 0.5). The true constrained optimum is
# at (-1/√2, -1/√2) ≈ (-0.7071, -0.7071), objective -√2 ≈ -1.41421.
result = runtime.execute("optimization_constrained", "penalty_method",
                         [[0.5, 0.5], 2, [1], 1.0, 200, 0.01])["result"]
result
# [-0.5461235067473419, -0.5461235067473419] -- objective -1.0922..., moving
# in the right direction along the disk boundary but not fully converged in
# 200 steps at this learning rate; the penalty coefficient only doubles every
# 10 iterations, so it has grown to 1.0 * 2^20 by the end but the step size
# never adapts to it
```

`augmented_lagrangian_step` returns `[new_x, new_lambdas]` and enforces
`λ_i = max(0, λ_i + μ·g_i(x))` after every step, so a caller who reads back `result[1]` never has
to clamp a multiplier to non-negativity itself; and if the caller passes a `lambdas` list shorter
than `constraints`, the function returns an **empty** result rather than indexing out of bounds —
a real guard, not a silent truncation.

## `optimization_meta`: four search strategies, no gradient anywhere

None of the four optimizers in this module ever calls a derivative — `neighbor` perturbs every
coordinate by uniform noise in `[-step, +step]`, and `simulated_annealing`, `particle_swarm`,
`hill_climbing`, and `random_search` all decide where to go next purely from comparing objective
values at sampled points.

```python
origin = runtime.execute("optimization_meta", "eval_objective", [[0.0, 0.0], 0])["result"]
point = runtime.execute("optimization_meta", "eval_objective", [[1.0, 2.0], 0])["result"]
origin, point
# 0.0, 5.0 -- sphere(0,0) = 0, sphere(1,2) = 1² + 2² = 5

accept_downhill = runtime.execute("optimization_meta", "acceptance_probability",
                                  [10.0, 5.0, 1.0])["result"]
accept_high_cost_low_temp = runtime.execute("optimization_meta", "acceptance_probability",
                                            [10.0, 20.0, 0.001])["result"]
accept_downhill, accept_high_cost_low_temp
# 1.0 -- any cost improvement is always accepted
# 0.0 -- exp(-10/0.001) = exp(-10000) underflows double precision to exactly
# zero: at a near-frozen temperature a worsening move is never accepted
```

Starting `simulated_annealing` from `x0 = [5.0, 5.0]` on the sphere objective with `temp=100.0`,
`cooling=0.995`, `max_iter=5000` drives the returned point's cost under `1.0` (the search cools
from a temperature where almost any move is accepted down to one where only improving moves
survive); `particle_swarm` with 20 particles over 200 iterations on the same objective, bounded to
`[-5, 5]`, likewise lands under cost `1.0`; and `hill_climbing` from `x0 = [3.0, 3.0]` for 1000
iterations always ends with a strictly lower cost than it started, since it only ever accepts a
candidate that is at least as good. Because `neighbor` draws from the runtime's process-seeded
`random_float64()`, none of these three runs is reproducible bit-for-bit the way
[`evolutionary_search`](reproducible-search.md) is — a fresh process gets a fresh random sequence.
This module is deliberately a different family of search from `evolutionary_search`/`genetic`
anyway: there is no population, no crossover, and no generational replacement here, only a single
candidate (or, for PSO, a swarm of independently-moving particles) evaluated against three fixed
benchmark landscapes that `evolutionary_search`'s tests never reference.

## `optimize`: root-finding and minimization, polynomial in, polynomial in

```python
# f(x) = 4 - 4x + x² = (x-2)², minimized by golden section on [-10, 10]
gs = runtime.execute("optimize", "minimize_scalar_golden",
                     [[4.0, -4.0, 1.0], -10.0, 10.0])["result"]
gs["x"], gs["fun"], gs["converged"]
# 2.0 (to 1e-3), 0.0, True

# the same polynomial by Brent's method -- parabolic interpolation plus golden section
br = runtime.execute("optimize", "minimize_brent", [[4.0, -4.0, 1.0], -10.0, 10.0])["result"]
br["x"], br["converged"]
# 2.0, True

# root of x² - 4 = 0 by bisection on [0, 5], and by Newton from x0 = 3
rb = runtime.execute("optimize", "root_bisection", [[-4.0, 0.0, 1.0], 0.0, 5.0])["result"]
rn = runtime.execute("optimize", "root_newton", [3.0, [-4.0, 0.0, 1.0]])["result"]
rb["x"], rn["x"]
# 2.0, 2.0 -- both find the positive root
```

`gradient_descent_1d` follows the polynomial's own derivative (`eval_poly_deriv`, not a
finite-difference estimate) — minimizing `(x-2)²` from `x0 = 0.0` at `lr = 0.1` converges to
`x ≈ 2.0`. Every one of these five solvers returns the same `OptResult{x, fun, iterations,
converged}` struct, so a caller can swap golden section for Brent, or bisection for Newton,
without touching how the result is read.

```python
x = [1.0, 2.0, 3.0, 4.0, 5.0]
y = [2.1, 3.9, 6.2, 7.8, 10.1]
reg = runtime.execute("optimize", "linear_regression", [x, y])["result"]
reg["slope"], reg["r_squared"]
# 2.0 (to within 0.2), > 0.99 -- data generated from y ≈ 2x
```

`linear_regression` is a closed-form single-predictor least-squares fit bundled into this scalar
toolbox as a convenience — it takes the classic-statistics path (`slope = Σ(xᵢ-x̄)(yᵢ-ȳ) /
Σ(xᵢ-x̄)²`) rather than anything iterative, and is a different, much smaller piece of code from the
[trainable linear models](ml-linear-models.md) documented elsewhere (which fit multi-feature
elastic-net and logistic regression by coordinate descent and IRLS). `optimize` itself is a
different family again from [`optmodel.solve`](optimization-model-formulation.md): that module
dispatches whole linear/integer *programs* — declared variables, dense constraint rows, senses —
to `optimization.linear`/`optimization.integer` and certifies the answer; nothing in `optimize`
accepts a constraint matrix or a variable declaration, and nothing in `optmodel` evaluates a
polynomial.

**Divergent iterates are caught before they reach the wire.** `gradient_descent_1d` and its
helpers replace any `NaN` or magnitude-over-`1e300` result with `0.0` (an internal `_wire_finite`
guard) before returning, because JSON cannot carry `NaN`/`Infinity` and a divergent run (too large
a learning rate on a polynomial whose derivative grows without bound) would otherwise fail the
whole call rather than reporting a non-convergent result. A caller relying on `converged == False`
already gets the right signal; `0.0` in `fun` on a failed run is that guard, not a genuine function
value.

## `optimizer_full`: ten update rules, none of them in `gradient_descent`

[`gradient_descent`](autograd-and-training-stability-kernels.md) already covers SGD, SGD+momentum,
Adam, AdamW, RMSProp, AdaGrad, LARS, Lion, gradient-norm clipping, and cosine-annealing schedules.
None of those ten names reappears here — `optimizer_full` is a second, non-overlapping suite,
weighted toward optimizers published after (or alongside) that first set: Sophia (2023), Prodigy
and schedule-free SGD (2024), and Adan and Muon, next to older methods that first suite's ten
functions never covered — Adadelta, Nadam, and the L-BFGS two-loop-recursion scale. Every function
here takes plain `Float64` scalars and running-statistic state the caller owns, exactly like
`gradient_descent`'s own functions — there is no struct, and no persistent state inside the module
itself. Its own test suite (`mojo/tests/libs/test_optimizer_full.mojo`) is an
auto-generated smoke test that calls each function once with literal `0.5` arguments and checks
only that the result is finite; the worked values below were hand-computed independently from the
formulas in `mojo/engine/optimizer_full.mojo` and verified against a plain-Python port of each one.

```python
# L-BFGS initial Hessian scale: H0 = (s·y)/(y·y) — here 3/12
scale = runtime.execute("optimizer_full", "lbfgs_two_loop_scale", [3.0, 12.0])["result"]
# 0.25

# Adadelta: no learning rate at all -- the step size is derived entirely from
# the running average of squared gradients (eg2) and squared updates (edx2)
adadelta = runtime.execute("optimizer_full", "adadelta_update",
                           [1.0, 0.5, 0.0, 0.0, 0.95, 1e-6])["result"]
# 0.9955280429197062

# Sophia clips the Hessian-diagonal estimate to a floor rho before dividing by
# it, so a near-zero (or negative) curvature estimate can't blow up the step
clipped = runtime.execute("optimizer_full", "sophia_hessian_clip", [0.001, 0.04])["result"]
step_a = runtime.execute("optimizer_full", "sophia_update", [1.0, 0.5, 0.001, 0.01, 0.04, 0.0])["result"]
step_b = runtime.execute("optimizer_full", "sophia_update", [1.0, 0.5, 1.0, 0.01, 0.04, 0.0])["result"]
clipped, step_a, step_b
# 0.04 -- h_diag=0.001 is floored to rho=0.04
# 0.875 -- step_a uses the floored 0.04, a big move: 1.0 - 0.01*0.5/0.04
# 0.995 -- step_b uses the true h_diag=1.0, a small move: 1.0 - 0.01*0.5/1.0

# Prodigy's d-estimate only ever grows -- it is a running maximum
d = runtime.execute("optimizer_full", "prodigy_d_estimate", [2.0, 3.0, 0.1, 0.999])["result"]
# 1.0 -- candidate s/sqrt(g_sq_sum+1) = 2/2 = 1.0 exceeds d_prev=0.1, so it wins
# note: the fourth argument, beta3, is accepted but never read by this formula --
# the function's own docstring calls it a "Simplified" d-estimate, and the smoothing
# the real Prodigy paper applies via beta3 is not implemented here

gc = runtime.execute("optimizer_full", "gradient_centralization", [0.8, 0.3])["result"]
# 0.5 -- 0.8 minus the batch's gradient mean of 0.3
```

`sophia_hessian_clip`'s floor is the whole mechanism behind Sophia's claimed stability advantage
over plain second-order methods: a per-parameter Hessian diagonal estimate that is small, zero, or
negative would otherwise produce an enormous or wrong-signed step, and clipping it to `rho` before
the division bounds every possible step to `lr/rho` in magnitude regardless of how bad the Hessian
estimate is. `muon_orthogonal_update` and `adan_update` both fold Nesterov's extrapolation into the
step directly, the same pattern `nadam_update` uses — none of the three calls a separate "look
ahead" function, the extrapolated gradient/momentum term is computed inline before the final
parameter update.

## Verification

`optimize`, `optimization_meta`, and `optimization_constrained` each have a real, hand-written test
suite beyond their auto-generated per-function smoke test: `tests/mojo/test_wave3.mojo` pins
`eval_poly`, `minimize_scalar_golden`, `minimize_brent`, `root_bisection`, `root_newton`,
`gradient_descent_1d`, and `linear_regression` to the exact worked values shown above (and to a
second linear-regression case fit on perfectly linear `y = 3x+1` data, checking slope `≈ 3.0`,
intercept `≈ 1.0`, and `r_squared ≈ 1.0`, each to within `0.001`); `tests/mojo/test_wave52.mojo` pins `eval_objective`,
`acceptance_probability`, and the "converges/improves" behavior of all four search strategies
described above; `tests/mojo/test_wave57.mojo` pins `eval_objective_c`, `eval_constraint`,
`is_feasible_c`, `penalty_value`, and the finiteness/improvement/non-negative-multiplier
guarantees of `penalty_method`, `barrier_method`, and `augmented_lagrangian_step`. `optimizer_full`
has no such suite — only the auto-generated smoke test described above — so every number in its
section was independently derived from the source formulas and double-checked by direct
calculation, not lifted from an existing assertion.

**Next:** see the classic-optimizer suite this module's `optimizer_full` complements in
[Autograd and training-stability kernels](autograd-and-training-stability-kernels.md), or the
reproducible genetic search that `optimization_meta`'s metaheuristics are a different family from
in [Reproducible evolutionary search](reproducible-search.md).
