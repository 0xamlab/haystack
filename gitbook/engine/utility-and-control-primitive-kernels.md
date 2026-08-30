---
icon: toolbox
description: Package-dependency graph resolution, portfolio/Kelly-criterion allocation, statistical anomaly detection, backtracking constraint satisfaction, PID/control-theory step-response math, and numerical (non-autograd) differentiation of sampled data.
---

# Utility and control primitive kernels

Six modules with no shared code path between them, grouped here because each solves one
self-contained utility problem an application layer needs and none of them fits an existing family
in this corpus: resolving a package-dependency graph into an install order, sizing a financial
portfolio (not scheduling a generic resource, despite the module's name — see below), flagging
statistical outliers in a series, solving constraint-satisfaction puzzles by backtracking, running or
characterizing a PID/bang-bang control loop, and taking the derivative of a table of sampled numbers
or a polynomial's coefficients (not the reverse-mode autodiff a training loop uses — see below, too).
Almost everything here is a pure function over `List[Float64]`/`List[Int]`/scalars; the two
exceptions are `constraint.solve_backtrack`, which returns a `CSPResult` struct, and `control`'s PID
pair, which keeps a small mutable `PIDState` struct across calls — the only stateful API in this
batch.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("dependency", "resolve_order", [3, [[0, 1], [1, 2]]])["result"]
# [2, 1, 0] -- package 0 depends on 1, which depends on 2, so install deps-first: C, then B, then A

runtime.execute("control", "bang_bang", [100.0, 90.0, 5.0])["result"]
# 1.0 -- measured (90) is more than 5.0 below setpoint (100), outside the hysteresis band: turn on full
```

## The modules

| Module | What it does |
| --- | --- |
| `dependency` | Package-dependency graph resolution: topological install ordering (Kahn's algorithm), cycle detection, transitive dependency closure, dependency-chain depth, version-range compatibility and conflict detection, a minimal install plan for one target, and reverse-dependency lookup. |
| `allocation` | Portfolio and position-sizing math — equal-weight, inverse-variance and simple risk-parity weighting, analytical min-variance and max-Sharpe weights for a 2-asset portfolio, portfolio return/variance, the Kelly criterion, a 2-asset efficient frontier, and a rebalance-drift threshold check. |
| `anomaly` | Outlier/anomaly detection: Z-score and modified-Z-score (MAD-based) flagging, IQR fencing, the percentile/median/MAD building blocks underneath them, a simplified single-feature isolation-forest score, and the Grubbs test statistic. |
| `constraint` | Backtracking constraint satisfaction: a generic CSP solver over variable domains and binary constraints, N-Queens (solve, validate placement, and count all solutions), graph coloring, Sudoku-board validation, magic-square validation, and an `all_different` check. |
| `control` | PID and on/off (bang-bang) control, plus first-order-plant step/ramp response curves and the settling-time/overshoot/steady-state-error metrics used to characterize them. |
| `differentiate` | Numerical differentiation of sampled data and polynomials: forward/central/backward finite differences, a second derivative, a non-uniform-spacing gradient, and the analytical derivative of a polynomial given by its coefficients. |

## `dependency`: resolving a graph, not npm or pip themselves

| Function | What it does |
| --- | --- |
| `resolve_order(n_packages, dependencies)` | Kahn's-algorithm topological sort; `dependencies[i] = [package, depends_on_package]`. Returns install order, deps first, or an **empty list** if a cycle exists. |
| `has_cycle(n_packages, dependencies)` | `len(resolve_order(...)) == 0` — cycle detection is just topological sort's failure mode. |
| `transitive_deps(package, dependencies)` | BFS closure: every package `package` depends on, directly or indirectly. |
| `dependency_depth(package, dependencies)` | Length of the longest dependency chain below `package` (iterative DFS). |
| `is_compatible(version, min_ver, max_ver)` | `version` inside `[min_ver, max_ver]`, inclusive on both ends. |
| `find_conflicts(requirements)` | `requirements[i] = [package, min_ver, max_ver]`; returns index pairs where two requirements name the same package with non-overlapping version ranges. |
| `install_plan(n_packages, deps, target)` | `target` plus its full transitive closure, filtered out of the whole graph's topological order — so the plan is always internally consistent with the rest of the graph. |
| `reverse_deps(package, dependencies)` | The (deduplicated) list of packages that directly depend on `package`. |

`resolve_order` also reveals the graph orientation the whole module commits to: `dependencies[i][1]`
(what a package depends on) gets the **in-edge** in the Kahn's-algorithm adjacency list
(`adj[depends_on].append(pkg)`, `in_deg[pkg] += 1`), so a leaf with no dependencies (in-degree 0)
is installed first. For the chain `0 depends on 1 depends on 2` —
`resolve_order(3, [[0, 1], [1, 2]])` — package 2 has no dependencies and starts in the queue,
producing `[2, 1, 0]`, exactly the intro example above.

`dependency_depth` and `transitive_deps` share the same chain in `mojo/tests/libs`'s companion
`tests/mojo/test_wave42.mojo`: for `0 → 1 → 2 → 3`, `transitive_deps(0, deps)` returns all three
downstream packages (`{1, 2, 3}`, length 3) and `dependency_depth(0, deps) == 3`, `dependency_depth(1,
deps) == 2`, `dependency_depth(3, deps) == 0` (a leaf has depth zero) — all pinned, hand-written
assertions, not smoke checks.

```python
runtime.execute("dependency", "find_conflicts",
                 [[[0, 1, 3], [0, 5, 7], [1, 2, 4]]])["result"]
# [[0, 1]] -- package 0 needs v1-3 in one requirement and v5-7 in another; those ranges don't
# overlap, so requirement indices 0 and 1 conflict. Package 1's single requirement can't conflict
# with anything.
```

## `allocation`: portfolio sizing, not generic resource scheduling

**This is the one real scope surprise in this batch.** Nothing in `allocation.mojo` allocates a
generic resource — CPU, inventory, tasks to workers. Its own docstring is explicit: *"Replaces
pypfopt with pure Mojo implementations for equal weight, inverse variance, risk parity, Kelly
criterion, and efficient frontier"* — this is Markowitz mean-variance portfolio theory and bet-sizing
math, full stop. Every function takes asset returns, variances, or a correlation, and returns
portfolio weights, a portfolio statistic, or a betting fraction.

| Function | What it does |
| --- | --- |
| `equal_weight(n_assets)` | `1/n` for every asset. |
| `inverse_variance(variances)` | Weight `∝ 1/variance`; a variance `<= 0.0` is treated as `1e-10` rather than dividing by zero. |
| `risk_parity_simple(variances)` | Weight `∝ 1/sqrt(variance)` — the same idea, gentler penalty for high-variance assets. |
| `max_sharpe_2asset(r1, r2, s1, s2, rho, rf)` | Analytical maximum-Sharpe weights `[w1, w2]` for a 2-asset portfolio, clamped to `[0, 1]`. |
| `min_variance_2asset(s1, s2, rho)` | Analytical minimum-variance weights `[w1, w2]`, same clamp. |
| `portfolio_return(weights, returns)` | `Σ w_i · r_i`, truncated to the shorter of the two lists if they differ in length. |
| `portfolio_variance_2asset(w1, s1, s2, rho)` | `w1²s1² + (1-w1)²s2² + 2·w1·(1-w1)·ρ·s1·s2`. |
| `kelly_criterion(win_prob, win_ratio)` | `p - (1-p)/b` — the optimal betting fraction; `0.0` if `win_ratio <= 0`. |
| `efficient_frontier_2asset(r1, r2, s1, s2, rho, n_points)` | `n_points` `[return, risk]` pairs sweeping `w1` from 0 to 1. |
| `rebalance_threshold(current_weights, target_weights, threshold)` | `True` if any weight has drifted more than `threshold` from target. |

`kelly_criterion(0.6, 2.0)` from the intro is a pinned value in `tests/mojo/test_wave50.mojo`:
`0.6 - 0.4/2.0 = 0.4` — risk 40% of capital on a 60%-probability, 2:1-payout bet. `inverse_variance`
is equally easy to hand-check: for variances `[0.01, 0.04]`, the raw weights are `1/0.01 = 100` and
`1/0.04 = 25`, summing to 125, so the normalized weights are `[0.8, 0.2]` — the asset with 4x the
variance gets a quarter of the weight, not an eighth, because inverse-variance weighting only
penalizes variance linearly (`risk_parity_simple`'s `1/sqrt(variance)` penalizes it more gently: the
same two variances give `[1/0.1, 1/0.2]` normalized to `[0.667, 0.333]`, a 2:1 split rather than 4:1).

`min_variance_2asset(0.2, 0.3, 0.5)` — two assets with std devs 0.2 and 0.3, correlation 0.5 — works
out to `cov12 = 0.5·0.2·0.3 = 0.03`, `num = 0.3² - 0.03 = 0.06`, `den = 0.2² + 0.3² - 2·0.03 = 0.07`,
so `w1 = 0.06/0.07 ≈ 0.857`: the minimum-variance portfolio puts 86% of its weight on the *lower*-risk
asset, which is the expected direction but not a 1:1 ratio with the variance gap, because covariance
between the two assets pulls the optimum away from a pure inverse-variance split.

## `anomaly`: real outlier detection, with one function that isn't deterministic

| Function | What it does |
| --- | --- |
| `zscore_detect(data, threshold=3.0)` | Flags `\|z\| > threshold`; all-`False` if `n < 2` or the data has zero spread. |
| `iqr_detect(data, factor=1.5)` | Flags values outside `[Q1 - factor·IQR, Q3 + factor·IQR]`; all-`False` if `n < 4`. |
| `modified_zscore_detect(data, threshold=3.5)` | Flags `\|0.6745·(x - median)/MAD\| > threshold`. |
| `percentile(data, p)` | Linear-interpolation percentile (0–100) on a sorted copy of `data`. |
| `median(data)` | Median value. |
| `mad(data)` | Median Absolute Deviation: `median(\|x_i - median(x)\|)`. |
| `isolation_score(data, point, n_trees=100, sample_size=32)` | Simplified 1D isolation-forest score in `[0, 1]`, higher = more anomalous. |
| `grubbs_test_statistic(data)` | `max\|x_i - mean\| / std`; `0.0` if `n < 3`. |
| `count_anomalies(flags)` | Count of `True` entries in a flag list. |
| `exp_approx(x)` | A 30-term Taylor-series `exp`, clamped to `[-20, 20]` before evaluating — `isolation_score`'s own internal exponentiation, also exported publicly. |

`zscore_detect([1, 2, 3, 100, 2, 3], threshold=2.0)` is a pinned example from
`tests/mojo/test_wave22.mojo`: mean `18.5`, std `≈36.45`, giving `100` a `z ≈ 2.24` (flagged) and `1`
a `z ≈ -0.48` (not flagged). `mad([1, 2, 3, 4, 5])` is `1.0` exactly — median `3.0`, absolute
deviations `[2, 1, 0, 1, 2]`, and the median of *those* is `1.0`.

A hand-checked Grubbs example, verified independently against the formula in the source
(`mojo/engine/anomaly.mojo`): for `[10.0, 10.0, 10.0, 10.0, 20.0]`, mean is `12.0`, the squared
deviations are `[4, 4, 4, 4, 64]` summing to `80`, variance `16.0`, std `4.0`, and the max deviation
`|20 - 12| = 8.0`, so `grubbs_test_statistic([10.0, 10.0, 10.0, 10.0, 20.0]) = 8.0 / 4.0 = 2.0` exactly.

{% hint style="warning" %}
**`isolation_score` is the one non-deterministic function in this whole batch.** Its signature has no
seed parameter, and its body calls `std.random.random_float64()` both to draw each tree's subsample
and to pick each split point — confirmed by reading the source directly, not inferred from the name.
Two calls with identical `data` and `point` will generally return different `Float64` values; only the
*ordering* the algorithm is designed to guarantee (an outlier scores higher than an inlier) is stable,
which is exactly what `tests/mojo/test_wave22.mojo`'s own test checks
(`score_outlier > score_inlier`) rather than pinning either value. A caller wanting a repeatable
number needs to average several calls itself.
{% endhint %}

## `constraint`: backtracking CSP, N-Queens, Sudoku, and graph coloring

| Function | What it does |
| --- | --- |
| `solve_backtrack(domains, constraints)` | Generic backtracking CSP solver; `constraints[i] = [var1, var2, relation]` with `relation` `0`=not-equal, `1`=less-than, `2`=equal. Returns a `CSPResult`. |
| `all_different(values)` | `True` if every value in the list is unique (vacuously `True` for 0 or 1 elements). |
| `n_queens_check(queens)` | Validates a placement (`queens[i]` = column of the queen in row `i`) for column and diagonal attacks. |
| `solve_n_queens(n)` | First valid N-Queens solution via backtracking, or an empty list if `n` has none (impossible only for `n` = 2 or 3). |
| `magic_square_check(square)` | Row, column, and both-diagonal sums all equal the row-0 sum. |
| `graph_coloring(adj, n_colors)` | Backtracking graph coloring; returns an empty list for `n_colors <= 0` or any out-of-range neighbor index, using the same empty-list answer as "no solution found." |
| `sudoku_valid(board)` | Validates a 9x9 board (0 = empty) for row/column/3x3-box duplicates. |
| `count_solutions_nqueens(n)` | Counts *every* N-Queens solution via exhaustive backtracking (not just the first). |

`solve_backtrack` returns a `CSPResult` struct (`solution: List[Int]`, `found: Bool`), the same
struct-as-dict convention used elsewhere in this corpus (see [Sparse and graph
kernels](sparse-and-graph.md)'s `out["result"]["singular"]`): `out["result"]["found"]` and
`out["result"]["solution"]`.

```python
result = runtime.execute("constraint", "solve_backtrack",
                          [[[0, 1], [0, 1]], [[0, 1, 0]]])["result"]
result["found"]      # True
result["solution"]   # [0, 1] -- two binary variables, constrained not_equal (relation 0)
```

`count_solutions_nqueens` is exhaustive rather than heuristic, and its classic values are pinned in
`tests/mojo/test_wave30.mojo`: `count_solutions_nqueens(4) == 2` and `count_solutions_nqueens(5) ==
10`, the textbook N-Queens solution counts. `magic_square_check` is also pinned against the Lo Shu
square — `[[2, 7, 6], [9, 5, 1], [4, 3, 8]]` — which checks out, since every row, column, and
diagonal sums to 15. `graph_coloring` on a 3-node triangle (every node adjacent to both others) finds
a valid assignment with 3 colors but returns an empty list with only 2 (a triangle's chromatic number
is 3, not 2) — both outcomes are pinned assertions, not just smoke checks.

## `control`: PID and step-response math, with a real sign bug in `overshoot`

| Function | What it does |
| --- | --- |
| `create_pid(kp, ki, kd, output_min=-1e18, output_max=1e18)` | Initializes a `PIDState` (`integral` and `prev_error` start at `0.0`). |
| `pid_update(state, setpoint, measured, dt)` | One PID step; **mutates `state.integral` and `state.prev_error` in place** and returns the clamped control output — the one stateful function in this batch. |
| `pid_simulate(kp, ki, kd, setpoint, initial, plant_gain, dt, steps)` | Self-contained closed-loop simulation against a first-order plant (`y[n+1] = y[n] + plant_gain·u·dt`); returns the full trajectory, length `steps + 1`. |
| `bang_bang(setpoint, measured, hysteresis=0.0)` | `1.0` below the hysteresis band, `0.0` above it, `0.5` inside it. |
| `step_response(gain, time_constant, dt, steps)` | `gain·(1 - exp(-t/tau))` sampled at each `dt`. |
| `ramp_response(gain, time_constant, dt, steps)` | `gain·(t - tau·(1 - exp(-t/tau)))` sampled at each `dt`. |
| `settling_time(response, setpoint, tolerance=0.02)` | Index (as `Float64`) after which the response never again leaves the `±tolerance·\|setpoint\|` band; `0.0` if always inside it, `-1.0` if it never settles. |
| `overshoot(response, setpoint)` | `(peak - setpoint) / \|setpoint\|`, clamped to `>= 0`; `0.0` if `setpoint ≈ 0`. |
| `steady_state_error(response, setpoint)` | `\|response[-1] - setpoint\|`. |

`create_pid` returns a `PIDState` struct with fields `kp`, `ki`, `kd`, `integral`, `prev_error`,
`output_min`, `output_max` — `out["result"]["integral"]` etc. — and `pid_update` takes that struct
back as a **mutable** argument (`is_mut: true` in the runtime contract), updating `integral` and
`prev_error` in place rather than returning a new state alongside the output. That is a genuinely
different calling shape from every other function documented on this page, all of which are pure:
a caller driving a real control loop across repeated `pid_update` calls needs to keep round-tripping
the same state value, not just read the returned output each time.

A P-only worked example, pinned in `tests/mojo/test_wave29.mojo`: `create_pid(1.0, 0.0, 0.0)` then
`pid_update(state, 10.0, 0.0, 0.1)` returns `10.0` (`kp · error = 1.0 · 10.0`, since `ki = kd = 0`
zero out the other two terms), and a second call `pid_update(state, 10.0, 5.0, 0.1)` returns `5.0` as
the error shrinks. `step_response(10.0, 1.0, 1.0, 3)` is hand-computable from the formula alone:
`t=0 → 0.0`, `t=1 → 10·(1 - e⁻¹) ≈ 6.321`, `t=2 → 10·(1 - e⁻²) ≈ 8.647` — monotonically approaching
the gain of 10, exactly what `tests/mojo/test_wave29.mojo`'s monotonicity assertion checks.

A hand-derivable `settling_time` example: `response = [0.0, 5.0, 9.0, 11.0, 10.0, 10.0, 10.0]`,
`setpoint = 10.0`, `tolerance = 0.1` (band `±1.0`, i.e. `[9, 11]`). Indices 0 and 1 are outside the
band (`|0-10|=10`, `|5-10|=5`); every index from 2 onward is inside it (`|9-10|=1` is not `> 1`, so it
counts as *inside*, matching this family's "strict `>` for violation" convention elsewhere in this
corpus). The last violating index is 1, so `settling_time` returns `1 + 1 = 2.0`.

{% hint style="danger" %}
**`overshoot` returns the wrong answer — `0.0` instead of a positive fraction — for a genuine
overshoot past a negative setpoint.** Reading the source directly: for `setpoint <= 0.0`, the
function tracks `peak` as the *minimum* value the response reaches (correctly identifying how far past
a negative target the response dips), but then computes `os_val = (peak - setpoint) / |setpoint|`
without changing the sign for this branch. If a response genuinely overshoots — say
`response = [0.0, -5.0, -12.0, -11.0, -10.0]` against `setpoint = -10.0`, dipping 2 units past the
target — `peak = -12.0` and `os_val = (-12.0 - (-10.0)) / 10.0 = -0.2`, which the function's own
`if os_val < 0.0: return 0.0` guard then floors to `0.0`: a real 20% overshoot is reported as none.
The guard is correct for the positive-setpoint branch (where a response that never overshoots
naturally produces a negative `os_val`), but the same guard silently swallows real overshoot whenever
`setpoint < 0`. `tests/mojo/test_wave29.mojo`'s own `test_overshoot` only exercises a positive
setpoint (`10.0`), so this gap is untested, not merely undocumented — this is a real bug found while
reading `mojo/engine/control.mojo` for this page, not a fabricated edge case.
{% endhint %}

## `differentiate`: numerical differentiation of samples, not autograd

| Function | What it does |
| --- | --- |
| `derivative_forward(y, dx)` | `(y[i+1] - y[i]) / dx`; length `n - 1`. |
| `derivative_central(y, dx)` | `(y[i+1] - y[i-1]) / (2·dx)` for interior points, forward/backward difference at the two ends; length `n`. |
| `derivative_backward(y, dx)` | `(y[i] - y[i-1]) / dx`, starting from index 1; length `n - 1`. |
| `second_derivative(y, dx)` | `(y[i+1] - 2·y[i] + y[i-1]) / dx²`, interior points only; length `n - 2`. |
| `gradient(y, x)` | Non-uniform-spacing derivative: a weighted central difference for interior points (forward/backward at the ends), for `x`/`y` pairs that aren't evenly sampled; length `n`. |
| `poly_derivative_coeffs(coeffs)` | Analytical derivative of `coeffs[0] + coeffs[1]x + coeffs[2]x² + ...`, returning `[coeffs[1], 2·coeffs[2], 3·coeffs[3], ...]`; length `n - 1`. |

Every one of these is verified with real, hand-written assertions in `tests/mojo/test_wave13.mojo`,
sampling `y = x²` at integer `x` from 0 to 10 with `dx = 1.0`. Because `x²` is an exact quadratic, the
finite-difference formulas here have **zero truncation error**, not just a close approximation:
`derivative_central(y, 1.0)[5] == 10.0` exactly (analytically `2x` at `x = 5`), and
`second_derivative(y, 1.0)[3] == 2.0` exactly at every interior point (the discrete second difference
of `x²` is exactly `2` for unit spacing, independent of which point you sample). `derivative_forward`
and `derivative_backward` are first-order and do carry truncation error in general, but for this
quadratic input `derivative_forward(y, 1.0)[5] = y[6] - y[5] = 36 - 25 = 11` and
`derivative_backward(y, 1.0)[4] = y[5] - y[4] = 25 - 16 = 9` are both exactly the pinned test values.
`poly_derivative_coeffs([1.0, 2.0, 3.0])` (representing `1 + 2x + 3x²`) returns `[2.0, 6.0]`
(`2 + 6x`), also pinned.

`gradient`'s non-uniform formula is exact for a quadratic too, verified independently against the
source formula (not present as a pinned value in the test, which only checks output length): for
`x = [0, 1, 3, 6]`, `y = [0, 1, 9, 36]` (still `x²`, just irregularly sampled), the interior point at
`x = 1` gives `dy = [1²·9 + (2² - 1²)·1 - 2²·0] / (2·1·3) = 12/6 = 2.0` — exactly `2x` at `x = 1` — and
at `x = 3`, `dy = [2²·36 + (3² - 2²)·9 - 3²·1] / (3·2·5) = 180/30 = 6.0`, exactly `2x` at `x = 3`.

{% hint style="info" %}
**This module has no relationship to the [autograd family](autograd-and-training-stability-kernels.md)
in this corpus** — confirmed by reading both. `differentiate.mojo`'s own docstring says it
*"Replaces: scipy.misc.derivative"*: every function here takes a `List[Float64]` of already-sampled
function values (or polynomial coefficients) and estimates or computes a derivative from finite
differences on that data. `autograd_ops.mojo`'s `grad_*` functions, by contrast, take a single scalar
input to one specific elementary operation (`sigmoid`, `pow`, `log`, ...) and return that operation's
*analytical* local gradient for use in a reverse-mode computation graph — there is no sampled array
anywhere in that family's signatures. Neither module imports the other, and nothing in
`autograd_graph.mojo` calls a `differentiate` function or vice versa: one is numerical calculus over
a table of numbers, the other is symbolic-per-operation calculus for backpropagation, and the shared
word "derivative" is the only thing connecting them.
{% endhint %}

## Verification

Unlike several other batches of this corpus, every module here has more than an auto-generated smoke
test. The `mojo/tests/libs/test_<module>.mojo` files (`test_dependency.mojo`, `test_allocation.mojo`,
`test_anomaly.mojo`, `test_constraint.mojo`, `test_control.mojo`, `test_differentiate.mojo`) are the
usual auto-generated coverage smoke tests — each calls every public function once with a fixed
generic input and checks only that the result is finite or non-negative-length. But each module also
has a real, independently hand-written assertion suite in a numbered wave test:
`dependency` in `tests/mojo/test_wave42.mojo`, `allocation` in `test_wave50.mojo`, `anomaly` in
`test_wave22.mojo`, `constraint` in `test_wave30.mojo`, `control` in `test_wave29.mojo`, and
`differentiate` in `test_wave13.mojo`. Every worked number given on this page that isn't independently
hand-derived in the text above is one of those pinned assertions, cross-checked against the formula in
the corresponding `mojo/engine/*.mojo` source file.

**Next:** see the reverse-mode, computation-graph half of "differentiation" in
[Autograd and training-stability kernels](autograd-and-training-stability-kernels.md), or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
