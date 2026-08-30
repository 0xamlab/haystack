---
icon: puzzle-piece
description: Combinatorial search heuristics, an unconstrained convex-optimization sandbox, a frozen two-variable LP solver, quasi-random sampling, and the scalar formulas behind scipy.optimize and scipy.stats.
---

# Combinatorics, convex optimization, and scipy-compatibility kernels

Six small, self-contained modules that either predate or sit underneath the larger
`optimization.*` families documented elsewhere in this corpus: classic combinatorial
search heuristics (0/1 knapsack, nearest-neighbour TSP, bin packing, greedy assignment,
Kadane's algorithm, longest increasing subsequence, coin change), an unconstrained
convex-optimization sandbox (gradient descent, Adam, proximal L1, backtracking line
search) built around exactly two hardcoded test functions, a two-variable linear-program
solver by vertex enumeration, quasi-random low-discrepancy sampling (Halton, Latin
Hypercube, an additive-recurrence sequence, and an L2-star discrepancy measure), and two
"ops" modules that expose the named scalar formulas behind `scipy.optimize`'s
line-search/quasi-Newton machinery and `scipy.stats`'s PDF library. None of the six is a
1:1 drop-in replacement for a `scipy` call signature — verified against their own
docstrings and callers below — and three of the six are described, in the source of the
modules that superseded them, as intentionally frozen "seed" kernels rather than
production entry points.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# 0/1 knapsack: items (weight, value) = (2,3), (3,4), (4,5), (5,6); capacity 5
weights, values, capacity = [2, 3, 4, 5], [3, 4, 5, 6], 5
selected = runtime.execute("combinatorial", "knapsack_01", [weights, values, capacity])["result"]
selected
# [0, 1] -- items 0 and 1 (weight 2+3=5, value 3+4=7); beats item 3 alone (weight 5, value 6)

value = runtime.execute("combinatorial", "knapsack_01_value", [weights, values, capacity])["result"]
value
# 7.0 -- weight-5 alone (value 6) loses to the pair; the DP finds the pair
```

## The modules

| Module | What it does |
| --- | --- |
| `combinatorial` | 0/1 knapsack (selection and value), nearest-neighbour TSP and tour length, first-fit and first-fit-decreasing bin packing, greedy row-to-column assignment, Kadane's maximum subarray, longest increasing subsequence, and minimum-coin change |
| `convex` | Gradient descent, projected (box-constrained) gradient descent, and Adam, all driving one of exactly two built-in test objectives (quadratic or Rosenbrock); plus the L2 norm, vector subtraction, the L1 proximal (soft-threshold) operator, and Armijo backtracking line search used to build them |
| `linear_programming` | A two-variable linear program solved by exhaustive vertex enumeration — optimum, feasibility, objective value, a same-named-but-not-actually-dual value, a finite-difference sensitivity, line intersection, and Northwest-Corner transportation cost |
| `sampling` | Halton (van der Corput) sequences in 1D and 2D, stratified sampling, Latin Hypercube Sampling, an additive-recurrence ("Sobol-like") low-discrepancy sequence, and L2-star discrepancy for 2D point sets |
| `scipy_optimize_ops` | Ten standalone scalar formulas from classical numerical optimisation: the BFGS inverse-Hessian update scalar, Fletcher-Reeves and Polak-Ribière conjugate-gradient betas, the Armijo and Wolfe line-search conditions, a golden-section-search midpoint, Newton, secant and bisection root-finding steps, and a trust-region Cauchy step norm |
| `scipy_stats_ops` | Ten probability-density formulas: normal PDF and a tanh-based CDF approximation, Student's t, chi-squared, exponential, Poisson (log-space), Beta, Gamma, logistic, and Weibull |

## Not drop-in replacements — verified from the source, not assumed from the name

Both `scipy_optimize_ops` and `scipy_stats_ops` look, from their names and file-level
docstrings (`"Numerical optimisation primitives (scipy.optimize)"`,
`"Statistical distribution PDF/CDF/PPF calculations"`), like they might mirror
`scipy.optimize.minimize()` or `scipy.stats.norm(...)` call signatures. Reading every
function signature in both files (above) shows something narrower and, in practice,
more useful as building blocks: there is no `minimize()`, no distribution *object* with
`.pdf()`/`.cdf()`/`.rvs()` methods, and no optimizer that takes an arbitrary Python
callable. Instead each function is one named formula from the literature, taking plain
`Float64` scalars and returning one `Float64` — `bfgs_hessian_update_term(s, y, sy_dot)`
is literally just `ρ = 1/(s·y)`, and `chi2_pdf` is explicitly documented as
`"(unnormalised)"`. These are the arithmetic steps a `scipy.optimize`/`scipy.stats`-style
implementation is built *from*, not a wrapper around one.

That framing is not just a docstring claim — `scipy_optimize_ops.conjugate_gradient_beta_fr`
is imported and called by the real conjugate-gradient solver in
`sparse_numerics/iterative.mojo` (`from scipy_optimize_ops import
conjugate_gradient_beta_fr`), so at least one of these ten formulas is a live component
inside a production Krylov solver elsewhere in the engine, not merely a reference
implementation sitting on its own.

### `scipy_stats_ops`: four PDFs are exact, four are proportional-only, one is a bounded approximation

Hand-checked against `scipy.stats` 1.14.1:

| Function | Normalisation | Checked |
| --- | --- | --- |
| `normal_pdf(x, mu, sigma)` | Exact normal PDF | `normal_pdf(0,0,1) = 0.3989422804014327`, matches `scipy.stats.norm.pdf(0,0,1)` bit for bit |
| `exponential_pdf(x, rate)` | Exact exponential PDF | `exponential_pdf(1,2) = 0.2706705664732254`, matches `scipy.stats.expon.pdf(1, scale=0.5)` exactly |
| `logistic_pdf(x, mu, s)` | Exact logistic PDF | `logistic_pdf(0,0,1) = 0.25`, matches `scipy.stats.logistic.pdf(0,0,1)` exactly |
| `weibull_pdf(x, shape, scale)` | Exact Weibull PDF | `weibull_pdf(1,2,1) = 0.7357588823428847`, matches `scipy.stats.weibull_min.pdf(1,2,scale=1)` exactly |
| `t_distribution_pdf(x, df)` | Unnormalised, `(1+x²/ν)^(-(ν+1)/2)` | Ratio to `scipy.stats.t.pdf` is a constant `2.6343...` at both `x=0` and `x=1`, `df=5` — proportional, as the docstring says, never integrates to 1 |
| `chi2_pdf(x, df)` | Unnormalised | Ratio to `scipy.stats.chi2.pdf(2,3)` is `2.5066...` (`= √(2π)`) — the missing `2^(k/2)Γ(k/2)` term |
| `beta_pdf_unnorm(x, α, β)` | Unnormalised | Ratio to `scipy.stats.beta.pdf(0.3,2,5)` is a constant `1/30` — the missing `B(α,β)` term |
| `gamma_pdf_unnorm(x, shape, rate)` | Unnormalised | Ratio to `scipy.stats.gamma.pdf(2,3,scale=1)` is exactly `2.0` — the missing `Γ(shape)` term |
| `poisson_pmf(k, λ)` | Log-space, Stirling-approximated | `poisson_pmf(0,4) = -4.0`, exact (special-cased); `poisson_pmf(10,4) = -5.233138` vs `scipy.stats.poisson.logpmf(10,4) = -5.241469` — Stirling's approximation for `log(k!)`, off by `8e-3` nats at `k=10` and shrinking as `k` grows |
| `normal_cdf_approx(x, mu, sigma)` | Bounded approximation | `normal_cdf_approx(-1,0,1) = 0.239831` vs the true `0.158655` — an **8.1-percentage-point** error at `z=±1`, `5.6` points at `z=±2`, exact only at `z=0` |

The last row is the one worth flagging on its own: `normal_cdf_approx`'s docstring names
its method (`tanh(0.7978845608 z (1+0.044715 z²))` as a stand-in for `erf`), and the
error above is what that specific approximation actually costs at the two points anyone
computing a p-value would check first. This is not a bug — the function does what its
docstring says — but the error is large enough that a caller wanting a normal CDF
accurate to more than one significant figure at `|z| ≈ 1–2` needs a different function.

## `combinatorial` and `convex`: the code that names them as its own predecessor

`mojo/engine/optimization/routing.mojo`'s docstring states outright why it exists, and
what it leaves alone:

> `combinatorial.tsp_greedy(distances)` is nearest-neighbour from node 0. It is typically
> 25% above optimal and can be arbitrarily bad, it reports no length, ... and it
> validates nothing: with a distance of exactly `1e308` in a row it returns `-1` as the
> next city and then indexes its `visited` list at `-1`.
> `combinatorial.tsp_tour_length(distances, tour)` indexes `distances[tour[i]][tour[i+1]]`
> with no range check at all, so a tour index outside `[0, n)` is an uncatchable process
> crash.
> `combinatorial.bin_packing_first_fit_decreasing(items, capacity)` returns a bin COUNT
> for a capacity-only problem. There is no vehicle routing anywhere.

`optimization.routing` (documented in
[Routing, scheduling & trade-offs](optimization-heuristics.md)) is the 2-opt/Or-opt/
iterated-local-search layer built on top, and by its own account it never reimplements
these three — `grep`ing the tree confirms `optimization/routing.mojo` and
`optimization/assignment.mojo` both still `from combinatorial import ...`.
`combinatorial.assignment_greedy` in particular is not just a reference kernel: it is
called *live* by `optimization.assignment`'s `assignment_solve` to produce the
`greedy_cost` comparison field documented in [Optimization & decision
programs](optimization.md#assignment-and-knowing-the-matching-is-optimal), and that
module's own `1e308` "forbidden pairing" sentinel is a direct quote of
`assignment_greedy`'s internal `best_cost` initial value, not a coincidence of two
modules picking the same large number.

`optimization/quadratic.mojo` (the real constrained convex-QP driver, documented in
[Routing, scheduling & trade-offs](optimization-heuristics.md#a-certified-minimiser-and-a-measured-gap-when-there-is-none))
names `convex.gradient_descent` in its own "what already exists" survey as
`"unconstrained, and blind to the [func_id] table"`. Reading `convex.mojo` confirms why:
`eval_function` and `compute_gradient` recognise exactly two `func_id` values — `0`
(quadratic `Σxᵢ²`) and `1` (Rosenbrock) — and fall through to `0.0` for anything else.
There is no way to hand this module an arbitrary objective, a constraint, or a certified
optimum; it demonstrates gradient descent, projected gradient descent, and Adam against
two textbook functions, and `optimization.quadratic` is the module that actually solves
a general convex QP with a checked KKT certificate.

## `linear_programming` and `optimization.linear`: a name that is reused, not a duplicate implementation

`optimization/linear.mojo`'s own docstring is explicit that `linear_programming.mojo`
(this module) is *"a two-variable vertex enumerator wearing a general name"*, and lists
two real defects independently confirmed against the current source below. `lp_solve_2var`
itself is deliberately kept reachable as a **differential oracle**: `optimization.linear`'s
own test suite (`test_optimization_linear.mojo`) checks that its general simplex agrees
with this module's vertex enumeration on every two-variable problem.

Running the classic textbook LP that also opens [Optimization & decision
programs](optimization.md) — maximise `3x + 5y` subject to `x ≤ 4`, `2y ≤ 12`,
`3x + 2y ≤ 18`, `x, y ≥ 0` — through `lp_solve_2var` reproduces `optimization.linear`'s
answer exactly:

```python
c = [3.0, 5.0]
A = [[1.0, 0.0], [0.0, 2.0], [3.0, 2.0]]
b = [4.0, 12.0, 18.0]

sol = runtime.execute("linear_programming", "lp_solve_2var", [c, A, b])["result"]
sol
# [2.0, 6.0, 36.0] -- x=2, y=6, objective=36.0; the same optimum lp_solve/lp_solve_default
# report for this problem in optimization.md
```

`dual_value(A, b, c)` computes no dual at all — its body is `lp_solve_2var(c, A, b)`
followed by returning the objective, the *primal* optimum, and its own parameter order
`(A, b, c)` is the reverse of `lp_solve_2var`'s `(c, A, b)`:

```python
runtime.execute("linear_programming", "dual_value", [A, b, c])["result"]
# 36.0 -- the same primal optimum as lp_solve_2var above, not a shadow price
```

`sensitivity_rhs` is a finite difference of two `lp_solve_2var` calls, and each missing
solve silently contributes `0.0`. Shrinking the first constraint's right-hand side from
`4.0` to `-96.0` (`delta = -100.0`) makes the perturbed program infeasible, so the
"new" objective defaults to `0.0` and the function reports a "sensitivity" of `-36.0` —
the negative of the *original* optimum, in the right units, with no relationship to a
derivative:

```python
runtime.execute("linear_programming", "sensitivity_rhs", [c, A, b, 0, -100.0])["result"]
# -36.0 -- looks like a shadow price; is actually -1 * the original objective
```

A well-behaved perturbation of a still-feasible constraint reports a sane number by
comparison — tightening the third constraint's right-hand side by `1.0` (`18.0 → 17.0`)
changes the optimum by exactly `-1.0`, the correct marginal value at that vertex:

```python
runtime.execute("linear_programming", "sensitivity_rhs", [c, A, b, 2, -1.0])["result"]
# -1.0
```

`transportation_cost` runs the Northwest-Corner method, which produces a feasible
starting solution, not an optimised one. Supply `[20, 30, 25]`, demand `[10, 25, 40]`,
per-unit costs `[[8,6,10],[9,12,13],[14,9,16]]`:

```python
supply, demand = [20.0, 30.0, 25.0], [10.0, 25.0, 40.0]
costs = [[8.0, 6.0, 10.0], [9.0, 12.0, 13.0], [14.0, 9.0, 16.0]]
runtime.execute("linear_programming", "transportation_cost", [supply, demand, costs])["result"]
# 915.0 -- a feasible shipping cost, not the minimum-cost one (there is no optimisation step)
```

## Worked examples: `combinatorial`

`assignment_greedy` is a per-row cheapest-available rule, and committing early can be
strictly worse than the optimum. Cost matrix `[[1, 2], [2, 100]]`: row 0 greedily takes
column 0 (cost `1`), which forces row 1 into column 1 at cost `100`:

```python
cost = [[1.0, 2.0], [2.0, 100.0]]
runtime.execute("combinatorial", "assignment_greedy", [cost])["result"]
# [0, 1] -- total cost 101.0
```

The true optimum swaps both assignments — row 0 to column 1, row 1 to column 0 — for a
total cost of `4.0`, 25x cheaper. This is exactly the gap `optimization.assignment`'s
`greedy_cost` field (see above) exists to surface.

`max_subarray_sum` (Kadane's algorithm) on `[3, -2, 5, -1, 6, -8, 4]` finds `11.0`, the
sum of the first five elements (`3-2+5-1+6`) — the trailing `-8, 4` never helps, so
Kadane's running-sum reset correctly stops accumulating there.

`longest_increasing_subsequence` on the classic `[3, 1, 4, 1, 5, 9, 2, 6]` returns `4`
(e.g. `1, 4, 5, 6`), computed via patience sorting rather than the naive `O(n²)` DP.

`coin_change([1, 5, 10, 25], 63)` returns `6` — the canonical U.S.-coin greedy answer
(`25+25+10+1+1+1`) is also the DP optimum here, because this coin system happens to be
"canonical" (greedy-optimal); the DP is exact regardless of whether the coin system has
that property.

`bin_packing_first_fit` vs. `bin_packing_first_fit_decreasing` on items
`[4, 8, 1, 4, 6, 5]` with `bin_capacity = 10.0`: first-fit in given order needs `4`
bins; sorting descending first (`8, 6, 5, 4, 4, 1`) before applying the same first-fit
rule needs only `3` — the classic demonstration of why FFD is preferred over FF.

## Worked examples: `convex`

`gradient_descent` on the quadratic objective (`func_id=0`, gradient `2x`) from
`x0=[3.0, 4.0]`, `learning_rate=0.1`: each step multiplies the current point by `0.8`
(`x - 0.1·2x = 0.8x`), so after 1 iteration `x = [2.4, 3.2]`, after 10 iterations
`x ≈ [0.322, 0.429]`, and after 50 iterations `x ≈ [4.28e-5, 5.71e-5]` — geometric
convergence to the unique minimum at the origin, exactly as the closed-form `0.8ⁿ · x0`
predicts.

`proximal_l1([3.0, -2.0, 0.5], lambda_val=1.0)` returns `[2.0, -1.0, 0.0]` — soft
thresholding shrinks every coordinate toward zero by `1.0` and clips at zero, which is
why the `0.5` coordinate (magnitude below `lambda_val`) vanishes entirely rather than
flipping sign.

`line_search_backtrack` from `x=[3.0, 4.0]` with `grad=[6.0, 8.0]` (the true quadratic
gradient at that point) starts at `t=1.0`, which overshoots past the minimum
(`x - grad = [-3.0, -4.0]`, same objective value as the start, `25.0` vs. the required
`≤ 15.0`) and fails Armijo; halving to `t=0.5` lands exactly on the origin
(`x - 0.5·grad = [0.0, 0.0]`, objective `0.0`), which clears the Armijo bound
comfortably and is returned.

`eval_function` on Rosenbrock (`func_id=1`) confirms the textbook shape: `[0.0, 0.0]`
scores `1.0` (the `(1-0)²` term alone) and the true minimum `[1.0, 1.0]` scores exactly
`0.0`.

## Worked examples: `sampling`

`halton_sequence(5, 2)` returns `[0.5, 0.25, 0.75, 0.125, 0.625]` — the van der Corput
sequence in base 2, each value the bit-reversal of its index's binary expansion.
`halton_2d(n)` pairs base-2 and base-3 Halton sequences per point.

`discrepancy_l2_star` is lower for more uniformly spread points, which is the entire
point of low-discrepancy sampling — verified directly, not assumed:

| Point set (n=8, `[0,1]²`) | `discrepancy_l2_star` |
| --- | --- |
| 8 Halton points (`halton_2d(8)`) | `0.0626` |
| A regular 2x2 grid (n=4, for scale) | `0.1241` |
| 8 identical points at `[0.5, 0.5]` | `0.2826` |

The maximally-clustered set (every point on top of every other) scores over 4x worse
than the Halton set of the same size, and the Halton points beat even a small regular
grid — confirming the module does what its docstring claims.

`stratified_sample_1d` and `latin_hypercube_sample` draw from `std.random.random_float64`
with **no seed parameter anywhere in either signature** — the contract above shows
`stratified_sample_1d(n_strata)` and `latin_hypercube_sample(n, d)` take only size
arguments. `mojo/engine/determinism/sampling_keyed.mojo` documents this exact pattern
tree-wide: unseeded callers like these "are frozen and unchanged," and a *separate*,
explicitly-keyed API exists elsewhere in the engine for callers that need a reproducible
draw — `stratified_sample_1d` and `latin_hypercube_sample` are not that API, and two
calls with the same arguments will not return the same samples. `halton_sequence`,
`halton_2d`, and `sobol_like_2d` have no randomness at all and are fully deterministic in
`n` (and `base`).

## Worked examples: `scipy_optimize_ops`

All ten functions are pure scalar formulas; a representative call for each, hand-checked
against the formula in its own docstring:

| Function | Call | Result |
| --- | --- | --- |
| `bfgs_hessian_update_term` | `(s=1.0, y=2.0, sy_dot=2.0)` | `0.5` (= `1/(s·y)`); `sy_dot ≤ 0` returns `0.0` |
| `conjugate_gradient_beta_fr` | `(grad_norm_sq_new=4.0, grad_norm_sq_old=1.0)` | `4.0` |
| `conjugate_gradient_beta_pr` | `(grad_new=2.0, grad_old=1.0, grad_norm_sq_old=1.0)` | `2.0` |
| `armijo_condition` | `(f_new=1.5, f_old=1.0, alpha=0.5, grad_dot_dir=-0.001, c1=1e-4)` | `0.0` — violated (`1.5 > 1.0 - 5e-8`) |
| `wolfe_curvature_condition` | `(grad_new_dot_dir=0.3, grad_old_dot_dir=1.0, c2=0.9)` | `1.0` — satisfied (`0.3 ≤ 0.9`) |
| `golden_section_midpoint` | `(a=0.0, b=1.0, use_left=1.0)` | `0.381966...` (`= 1 - φ`, `φ = 0.618034`) |
| `newton_step` | `(f_val=2.0, f_prime=4.0)` | `-0.5` |
| `secant_step` | `(x0=1.0, x1=2.0, f0=-1.0, f1=1.0)` | `1.5` |
| `bisection_midpoint` | `(a=1.0, b=3.0)` | `2.0` |
| `trust_region_step_norm` | `(grad_norm=10.0, hessian_min_eig=1.0, delta=2.0)` | `2.0` — capped at `delta` (uncapped Cauchy step would be `10.0`) |

## Guarantees and refusal behaviour

`combinatorial`'s DP-based functions bound their own allocation against untrusted input
rather than trusting the caller: `knapsack_01`/`knapsack_01_value` refuse (return an
empty list / `0`) above `capacity > 1_000_000`, `knapsack_01` additionally refuses when
`(n+1)*(capacity+1) > 10_000_000`, and `coin_change` refuses above `amount > 1_000_000`.
All three also refuse outright on any negative weight or negative coin value, because a
negative index would read past the DP table's bounds — an uncatchable abort rather than
a wrong answer, so the guard returns a sentinel (`[]`, `0`, or `-1`) instead.

`linear_programming.is_feasible`, `enumerate_vertices_2d`, and `transportation_cost` all
check `len(b)` (or row lengths) against the declared constraint count before indexing,
and `transportation_cost` additionally refuses non-finite supply or demand — a `NaN`
would never satisfy the Northwest-Corner walk's advance condition, hanging the loop
rather than erroring.

`convex.vector_sub` and `convex.line_search_backtrack` both refuse (empty list / `0.0`)
on mismatched vector lengths, for the same reason: reading `a[i] - b[i]` or
`x[i] - t*grad[i]` past the shorter list's end is an uncatchable process abort, not a
recoverable exception, in this runtime.

## Verification

All six `mojo/tests/libs/test_*.mojo` files behind this page
(`test_combinatorial.mojo`, `test_convex.mojo`, `test_linear_programming.mojo`,
`test_sampling.mojo`, `test_scipy_optimize_ops.mojo`, `test_scipy_stats_ops.mojo`) are
auto-generated coverage smoke tests: each calls a function once with a literal fixture
(`0.5`, `[0.5, 0.6, 0.7, 0.4, 0.3]`, or similar) and checks only that the result is
finite or the returned list's length is non-negative — none pins a specific numeric
output. Two of the six also have **incomplete** function coverage:
`test_linear_programming.mojo` imports and calls only `line_intersection_2d` and
`objective_value`, leaving `lp_solve_2var`, `dual_value`, `is_feasible`,
`enumerate_vertices_2d`, `sensitivity_rhs`, and `transportation_cost` untested by the
generated smoke suite; `test_sampling.mojo` calls `halton_sequence`, `halton_2d`,
`stratified_sample_1d`, and `latin_hypercube_sample`, but not `sobol_like_2d` or
`discrepancy_l2_star`.

Every worked number in this page was hand-computed independently from the real formulas
in `mojo/engine/combinatorial.mojo`, `convex.mojo`, `linear_programming.mojo`,
`sampling.mojo`, `scipy_optimize_ops.mojo`, and `scipy_stats_ops.mojo`, and re-run in
Python (including `scipy` 1.14.1 for every `scipy_stats_ops` comparison) before being
presented above — none is asserted by the generated test suite.

**Next:** [Optimization & decision programs](optimization.md) for the exact linear,
integer, assignment and flow solvers `linear_programming` and `combinatorial` are the
frozen predecessors of; [Routing, scheduling & trade-offs](optimization-heuristics.md)
for the production TSP/VRP and convex-QP drivers built on top of `combinatorial` and
`convex`; or the [Runtime library catalog](runtime-library-catalog.md) for every module
and function.
