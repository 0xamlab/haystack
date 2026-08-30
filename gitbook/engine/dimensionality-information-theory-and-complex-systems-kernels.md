---
icon: shapes
description: Six unrelated math primitives grouped by name-similarity rather than shared subject -- business unit-consistency checking, PCA, Shannon information theory, special functions, chaotic dynamical systems, and cellular automata.
---

# Dimensionality, information theory, and complex-systems kernels

Six modules that landed on one page because their names cluster (`dimensions` next to
`dimensionality`, `chaos` next to `cellular_automata`), not because they share a subject. Read
individually they are: a business-semantics unit checker for spreadsheet formulas (`dimensions` --
**not** physical-unit dimensional analysis, see the flag below), a from-scratch PCA implementation
(`dimensionality`), Shannon entropy and its relatives (`information_theory`), the gamma/beta/erf/
Bessel function family `scipy.special` provides (`special_functions`), logistic-map and
Lorenz-system chaos theory (`chaos`), and Wolfram-style discrete cellular automata including
Conway's Game of Life (`cellular_automata`). All six are pure-Mojo, zero-Python-import replacements
for a corresponding piece of `scipy`/`sklearn`/`numpy`, called the same way as every other module
in this corpus:

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# fair coin: maximum-entropy binary variable
runtime.execute("information_theory", "entropy", [[0.5, 0.5]])["result"]
# 1.0 -- exactly one bit, the ceiling normalized_entropy and redundancy are measured against

# Conway's Game of Life: a live cell with 3 live neighbors survives
runtime.execute("cellular_automata", "game_of_life_cell", [True, 3])["result"]
# True -- alive with 2 or 3 neighbors survives, everything else dies or stays dead
```

## The modules

| Module | What it does |
| --- | --- |
| `dimensions` | Business-dimension algebra for spreadsheet/tabular formulas: classifies a numeric column as Count, Currency, Rate, Ratio, or Identifier, and checks whether an arithmetic operation between two such dimensions (`price * qty`, `total / count`, …) produces a semantically valid result or a dimensionally inconsistent one. |
| `dimensionality` | Principal Component Analysis from scratch: column means, centering, covariance matrix, power iteration for the dominant eigenvector, matrix deflation to peel off successive components, and a `PCAResult` struct bundling components/explained-variance/mean for downstream projection. |
| `information_theory` | Shannon entropy and its relatives: joint/conditional entropy, mutual information, KL divergence, cross entropy, binary entropy, binary-symmetric-channel capacity, redundancy, and normalized entropy. |
| `special_functions` | The gamma/beta/error/Bessel function family: `gamma_function` (Lanczos approximation), `log_gamma`, `beta_function`, `digamma`, lower incomplete and regularized gamma, `erf`/`erfc`, `bessel_j0`, and the factorial/double-factorial/binomial-coefficient combinatorics built on top of them. |
| `chaos` | Chaos theory: the logistic map, the Lorenz system (single Euler step and full trajectory), a Lyapunov exponent estimator, the Hénon map, the tent map, bifurcation-diagram sampling, a two-trajectory sensitivity (divergence) tracker, and the Feigenbaum ratio. |
| `cellular_automata` | Discrete cellular automata: Wolfram elementary rules (0-255) over a 1D lattice, Conway's Game of Life (cell rule and neighbor counting), Langton's Ant, Wireworld, Rule 110 (Turing-complete), k-color totalistic rules, and majority/parity voting rules. |

## `dimensions` is not physical-unit dimensional analysis

The module name and the task hint both suggest SI-unit tracking (meters, kilograms, `m/s²`) —
reading `mojo/engine/dimensions.mojo`'s own docstring corrects that immediately: this is the
**Business Dimension Engine**, a five-category semantic classifier for tabular/spreadsheet data,
built to replace name-based column heuristics ("a column called `price` is probably a rate") with
math derived from the numeric distribution and the formulas already detected by a profiler. The
five categories, as comptime `Int` constants, are:

| Dimension | Meaning | Example | Can `SUM`? | Can `AVG`? |
| --- | --- | --- | --- | --- |
| `DIM_COUNT` (1) | discrete non-negative integer quantity | units sold | yes | yes |
| `DIM_CURRENCY` (2) | monetary total | line-item total | yes | yes |
| `DIM_RATE` (3) | per-unit value | unit price ($/unit) | no | yes |
| `DIM_RATIO` (4) | bounded proportion | fill rate, tax rate | no | yes |
| `DIM_IDENTIFIER` (5) | surrogate key | order ID | no | no |
| `DIM_UNKNOWN` (0) / `DIM_INVALID` (-1) | not yet classified / dimensionally inconsistent | — | — | — |

`propagate(op, dim_a, dim_b)` encodes a small algebra of which combinations make sense — reading
the function body directly, multiplication is commutative-normalized (`a <= b` by swapping) and
then table-matched: `Count * Rate -> Currency` (`qty * unit_price = total`), `Count * Currency ->
Currency`, `Count * Ratio -> Count` (`qty * fill_rate = effective_qty`), `Currency * Ratio ->
Currency` (`total * tax_rate = tax`), `Ratio * Rate -> Rate` (`price * (1-discount) = net_price`),
while `Rate * Rate` and `Currency * Currency` both return `DIM_INVALID` — "price times price" and
"dollars times dollars" have no business meaning. Addition only makes sense between two operands of
the *same* dimension (`Currency + Currency -> Currency`, `Rate + Rate -> Rate`); any two different,
both-known dimensions added together are `DIM_INVALID` — the module docstring calls out
`Rate + Ratio -> INVALID` by name as "the Unit Cost + Reserve% case," a real spreadsheet mistake
(adding a `$/unit` column to a `%` column) this catches. Division has its own table: `Currency /
Count -> Rate` (deriving a unit cost), `Currency / Currency -> Ratio` (a margin), `Count / Count ->
Ratio` (a utilization rate).

`validate_formula(op, dim_a, dim_b, dim_c)` is the profiler-facing entry point: it gives the
benefit of the doubt (`True`) whenever any operand is still `DIM_UNKNOWN`, to avoid false negatives
before a column has been classified, and otherwise checks `dim_c == propagate(op, dim_a, dim_b)`.
`can_sum`/`can_avg`/`aggregation_valid` apply the same table to aggregation functions: `SUM` is
valid only for Count and Currency (summing a Rate or Ratio column — averaging unit prices by adding
them up — is the classic spreadsheet error this exists to flag), while `AVG` is valid for all four
numeric dimensions. `role_for_dimension`/`dimension_name`/`dimension_from_role` are metadata
round-trip helpers mapping a dimension constant to/from a schema role string (`"base_measure"`,
`"derived_measure"`, `"unit_measure"`, `"ratio"`, `"identifier"`) and a human-readable label.

`infer_from_samples` gives an initial guess from a numeric sample alone, without formula context:
non-negative values where fewer than 5% have a decimal remainder past `1e-4` classify as `DIM_COUNT`;
values bounded by `[0, 1.001]` with more than 10% decimal density classify as `DIM_RATIO`; Currency
and Rate are explicitly **not** distinguishable from the numbers alone (both `[10.50, 25.00, 8.75]`
could be either a currency total or a unit rate) and return `DIM_UNKNOWN` until formula context
resolves them.

```python
runtime.execute("dimensions", "propagate", ["multiply", 3, 3])["result"]
# -1 (DIM_INVALID) -- Rate * Rate, e.g. unit_price * unit_price, is meaningless

runtime.execute("dimensions", "propagate", ["add", 3, 4])["result"]
# -1 (DIM_INVALID) -- Rate + Ratio, the "unit cost + reserve %" spreadsheet bug

runtime.execute("dimensions", "can_sum", [3])["result"]
# False -- DIM_RATE (3): summing per-unit prices across rows is not meaningful
```

## `dimensionality`: PCA via power iteration, not Jacobi rotation

`dimensionality.mojo`'s own docstring states its purpose plainly: "Replaces
`sklearn.decomposition.PCA` with pure Mojo implementations using power iteration for eigenvalue
extraction." The pipeline is `column_means` -> `center_data` -> `covariance_matrix` -> repeated
(`power_iteration`, `eigenvalue_from_vector`, `deflate_matrix`) to peel off one component at a
time -> `pca` orchestrates all of that into a `PCAResult`, and `transform_pca` projects new rows
onto the fitted components.

`covariance_matrix(data)` computes `Cov(j,k) = (1/(n-1)) * Σᵢ data[i][j] * data[i][k]` and expects
already-centered input (the `pca` orchestrator calls `center_data` first). `power_iteration`
initializes the candidate eigenvector to a uniform `[1/√d, ..., 1/√d]` rather than the textbook
`[1, 0, 0, ...]` — the docstring calls this out as chosen "for robustness," since a zero-heavy
starting vector orthogonal to the true dominant eigenvector would converge far more slowly (or, in
a degenerate case, not move at all on the first iteration). `deflate_matrix` implements
`A' = A - λ·v·vᵀ`, subtracting the found component's contribution so the next call to
`power_iteration` converges on the next-largest eigenvalue instead of rediscovering the same one.

This is a genuinely different implementation from [Symmetric eigendecomposition and thin
SVD](ml-eigendecomposition.md)'s `eigen_full` module, not a duplicate under a different name:
`eigen_full.eigh_symmetric` computes a *full* eigendecomposition of a symmetric matrix via cyclic
Jacobi rotation (all eigenpairs, sorted, converging by driving the whole off-diagonal Frobenius norm
to zero), while `dimensionality.pca` extracts only the top `n_components` eigenpairs one at a time
via power iteration and deflation — cheaper when a caller wants 2-3 components out of a
50-column dataset, but progressively less accurate for later components once neighboring
eigenvalues are close together, since each deflation step's numerical error compounds into the
next. `eigen_full` has no notion of centering, explained-variance ratios, or a fitted
transform — it is a general linear-algebra primitive; `dimensionality` is a purpose-built,
opinionated PCA pipeline with a `PCAResult` struct (`components`, `explained_variance`,
`explained_variance_ratio`, `mean`) shaped specifically for that use case. Neither module imports
the other, and grepping the rest of `gitbook/` for `dimensionality` finds nothing outside this page
and the auto-generated catalog.

**Worked example, verified against NumPy's own `eigh`.** Using the ten-point 2-column dataset from
Lindsay Smith's classic PCA tutorial (`[[2.5,2.4],[0.5,0.7],[2.2,2.9],[1.9,2.2],[3.1,3.0],
[2.3,2.7],[2.0,1.6],[1.0,1.1],[1.5,1.6],[1.1,0.9]]`), hand-tracing `column_means` ->
`center_data` -> `covariance_matrix` gives `mean = [1.81, 1.91]` and
`cov = [[0.6166, 0.6154], [0.6154, 0.7166]]` (values rounded to 4 places); tracing
`power_iteration` + `eigenvalue_from_vector` on that matrix converges to eigenvector
`[0.6779, 0.7352]` with eigenvalue `1.28403`, and after one `deflate_matrix` step the second
component converges to `[0.7352, -0.6779]` with eigenvalue `0.04908` — reproducing `numpy.linalg.
eigh`'s eigenvalues (`0.049083`, `1.284028`) and eigenvectors for this exact matrix up to sign,
confirming the power-iteration path lands on the textbook answer. `explained_variance_ratio` works
out to `[0.9632, 0.0368]`: the first component alone captures 96.3% of the variance in this
dataset.

**Edge case: rank-deficient input drives the second component to a meaningless fallback.** Feeding
in perfectly colinear data (`[[1,2],[3,4],[5,6],[7,8]]`, `y = x+1` exactly) gives a covariance
matrix with all four entries equal to `6.667` — rank 1. The first `power_iteration` correctly
converges to `[0.7071, 0.7071]` (the `y=x` direction) with eigenvalue `13.333`, which is the *entire*
total variance — `explained_variance_ratio[0] = 1.0`. But `deflate_matrix` then subtracts that
entire contribution, leaving a residual matrix that is numerically all-zero; `power_iteration`'s
own norm guard (`if norm < 1e-15: return b`) fires on the very first iteration and returns its
*unmoved initial vector*, `[1/√2, 1/√2]` — which happens to be numerically identical to the first
component, not a genuine orthogonal second axis. A caller requesting `n_components=2` on rank-1
data gets two components back, but the second is a degenerate stand-in with `eigval ≈ 0`, not a
meaningful direction; `explained_variance_ratio[1] ≈ 1.3e-16` is the tell that it should be
discarded.

```python
data = [[2.5,2.4],[0.5,0.7],[2.2,2.9],[1.9,2.2],[3.1,3.0],
        [2.3,2.7],[2.0,1.6],[1.0,1.1],[1.5,1.6],[1.1,0.9]]
result = runtime.execute("dimensionality", "pca", [data, 2])["result"]
result["v"][1]              # explained_variance: [1.28403, 0.04908]
result["v"][0][0]           # first component: [0.6779, 0.7352]
```

## `information_theory`: Shannon entropy and its relatives

Every function operates on a `List[Float64]` of probabilities (or a `List[List[Float64]]` joint
distribution) the caller has already normalized — none of these functions renormalize their input.
`entropy` skips `p == 0` terms rather than evaluating `log2(0)`; `joint_entropy` does the same over
a 2D table. `conditional_entropy` and `mutual_information` both derive their answer from
`joint_entropy` plus marginals computed by summing rows/columns of the joint table, matching the
identities `H(Y|X) = H(X,Y) - H(X)` and `I(X;Y) = H(X) + H(Y) - H(X,Y)` exactly as coded.

Hand-verified example — a joint distribution over two correlated binary variables,
`P(X=0,Y=0)=0.4, P(X=0,Y=1)=0.1, P(X=1,Y=0)=0.1, P(X=1,Y=1)=0.4`:

| Quantity | Value |
| --- | --- |
| `entropy([0.5, 0.5])` (either marginal) | `1.0` bit |
| `joint_entropy([[0.4,0.1],[0.1,0.4]])` | `1.721928...` bits |
| `conditional_entropy(...)` = `H(X,Y) - H(X)` | `0.721928...` bits |
| `mutual_information(...)` = `H(X)+H(Y)-H(X,Y)` | `0.278072...` bits |

The two variables share about a quarter of a bit of information — well above `0` (independence)
because `P(X=Y) = 0.8` is far from the `0.5` that pure independence would need at these marginals.

`kl_divergence(p, q)` and `cross_entropy(p, q)` both guard the same way: if `q` is shorter than `p`
they return `0.0` immediately rather than reading `q[i]` past its end (an uncatchable abort in this
runtime), and both skip any index where `p[i] <= 0` or `q[i] <= 0`. The identity
`cross_entropy(p, q) - entropy(p) == kl_divergence(p, q)` holds by construction: for
`p=[0.5,0.5], q=[0.9,0.1]`, `cross_entropy = 1.736966`, `entropy(p) = 1.0`, and
`kl_divergence = 0.736966` — the difference matches exactly.

`binary_entropy(p)` returns `0.0` at the boundaries (`p <= 0` or `p >= 1`, both certain outcomes,
zero uncertainty) rather than evaluating `log2(0)`. `channel_capacity_bsc(error_prob)` is
`1 - binary_entropy(error_prob)`: at `error_prob = 0.5` (a coin-flip channel — the output carries no
information about the input) capacity is exactly `0.0`; at `error_prob = 0.1` capacity is `0.531`
bits per channel use. `redundancy(probs) = log2(n) - H(probs)` and
`normalized_entropy(probs) = H(probs) / log2(n)` are complementary views of the same gap between a
distribution's actual entropy and the `log2(n)` ceiling a uniform distribution over `n` outcomes
would reach — both correctly return `0.0` for `n <= 1` (no gap possible with only one outcome) and
whenever the input distribution is already uniform.

## `special_functions`: gamma, beta, erf, Bessel, and combinatorics

Every function here replaces one `scipy.special` call with a from-scratch numerical approximation,
and each carries a real, checkable accuracy bound rather than an unstated one:

| Function | Method | Accuracy |
| --- | --- | --- |
| `gamma_function` / `log_gamma` | Lanczos approximation (g=7, 9 coefficients), reflection formula `Γ(x)Γ(1-x) = π/sin(πx)` for `x < 0.5` | verified to full `Float64` precision against `Γ(0.5) = √π` and `Γ(5) = 4! = 24` |
| `erf` / `erfc` | Abramowitz & Stegun approximation, eq. 7.1.26 | max error `< 1.5e-7`, stated in the docstring |
| `bessel_j0` | power series for `\|x\| < 8`, asymptotic expansion beyond | matches `scipy`'s `J₀(1.0) = 0.7651976866` to all displayed digits in the series branch |
| `digamma` | recurrence to shift into range, then asymptotic (Bernoulli-number) series for `x >= 6` | standard method, no stated bound |
| `incomplete_gamma_lower` / `regularized_gamma` | series expansion, 200-term cap with early exit at `\|term\| < 1e-15 · \|total\|` | series-truncation error, not a fixed bound |
| `beta_function`, `binomial_coefficient` | built on `log_gamma` for numerical stability rather than direct factorial ratios | avoids overflow for large `n`/`k` that `n!` alone would hit |

Hand-verified worked values (reproduced independently in Python against both the Lanczos formula
and, where available, the standard library):

```python
runtime.execute("special_functions", "gamma_function", [0.5])["result"]
# 1.7724538509055159 -- sqrt(pi), exact to displayed precision

runtime.execute("special_functions", "erf", [1.0])["result"]
# 0.8427006897475899 -- vs math.erf(1.0) = 0.8427007929497148, agreeing to 6 significant figures
# (the approximation's own stated max error is 1.5e-7; the observed gap here is ~1.03e-7, within bound)

runtime.execute("special_functions", "bessel_j0", [2.4048])["result"]
# 1.3268e-05 -- close to zero, since 2.4048 is (to 4 decimal places) J0's first real root

runtime.execute("special_functions", "binomial_coefficient", [10, 3])["result"]
# 119.99999999999987 -- C(10,3) = 120, off by ~1.3e-13 from the log-gamma round trip through exp(log(...))
```

`factorial_float` switches strategy at `n = 20`: direct multiplication up to `20!` (still exactly
representable as `Float64`), then `Γ(n+1)` via the Lanczos path beyond, where direct multiplication
would start losing precision to accumulated rounding faster than the gamma approximation does.

## `chaos`: logistic map, Lorenz system, and Lyapunov exponents

`logistic_map(r, x0, n_steps)` iterates `x_{n+1} = r·x_n·(1-x_n)` and returns the whole trajectory
including `x0` — length `n_steps + 1`. At `r = 3.9` (past the onset of chaos, which for the
logistic map begins around `r ≈ 3.57`), five steps from `x0 = 0.5` give
`[0.5, 0.975, 0.095063, 0.335500, 0.869465, 0.442633]` — already visibly non-periodic.

`lyapunov_exponent_logistic(r, n_iter, n_transient)` estimates `λ = (1/N) Σ log|r - 2r·x_n|` — the
average log-derivative of the map along a trajectory, discarding `n_transient` steps first so the
orbit has settled onto its attractor. Hand-computed at `r = 3.9` (1000 iterations after 100
transient): `λ ≈ 0.505` — positive, confirming chaos. At `r = 2.5` (well before the chaotic regime,
where the map converges to a stable fixed point): `λ ≈ -0.693` — negative, confirming stability.
`is_chaotic(lyapunov)` is exactly `lyapunov > 0.0`, so feeding either computed value through it
returns `True` and `False` respectively, matching the qualitative behavior.

```python
lyap = runtime.execute("chaos", "lyapunov_exponent_logistic", [3.9, 1000, 100])["result"]
lyap                                                            # ~0.505 -- positive
runtime.execute("chaos", "is_chaotic", [lyap])["result"]        # True
```

`lorenz_step` and `lorenz_simulate` implement one (or many) explicit-Euler steps of the classic
Lorenz system `dx/dt = σ(y-x)`, `dy/dt = x(ρ-z)-y`, `dz/dt = xy-βz`. At the textbook chaotic
parameters (`σ=10, ρ=28, β=8/3`) starting from `(1,1,1)` with `dt=0.01`, one step gives
`(1.0, 1.26, 0.983333)` — `x` is momentarily unchanged because `dx/dt = 10·(1-1) = 0` exactly at
that starting point, while `y` and `z` already move. `henon_map(a, b, x0, y0, n_steps)` implements
`x_{n+1} = 1 - a·x_n² + y_n, y_{n+1} = b·x_n`; at the standard chaotic parameters `a=1.4, b=0.3`
from `(0,0)`, five steps visibly diverge from a fixed point rather than settling.

`sensitivity_to_initial(r, x1, x2, n_steps)` tracks `|x1_n - x2_n|` for two trajectories starting
`0.0001` apart at `r=3.9`: the divergence grows from `1e-4` to `~1.7e-6`... and then does **not**
grow monotonically past that — it fluctuates between `~4e-8` and `~7.6e-6` over the next several
steps. That is expected, not a bug: the logistic map is bounded to `[0,1]`, so exponential
divergence (the actual Lyapunov behavior) only holds locally — once the two orbits fold back into
the same bounded interval, their instantaneous distance can shrink again even while the long-run
average log-divergence rate stays positive. A single short trajectory is the wrong tool to observe
the asymptotic rate; `lyapunov_exponent_logistic`'s long-run average is the function built for that.

`feigenbaum_ratio(r1, r2, r3) = (r2-r1)/(r3-r2)` estimates the universal Feigenbaum constant
(`δ ≈ 4.6692...`) from three successive period-doubling bifurcation points. Feeding in the logistic
map's first three known bifurcation points (`r1=3.0, r2=3.449490, r3=3.544090`, the period 1→2,
2→4, and 4→8 transitions) gives `4.7515` — in the right neighborhood of the universal constant but
not yet converged to it, because higher-order corrections only vanish as the bifurcation sequence
extends; three points is the minimum input the formula accepts, not the number needed for
convergence. `bifurcation_diagram(r_start, r_end, n_r, n_iter, n_last)` samples `n_r` values of `r`
across `[r_start, r_end]`, discards `n_iter - n_last` transient iterations per `r`, and records the
final `n_last` values — the standard way to render a logistic-map bifurcation plot.

## `cellular_automata`: Wolfram rules, Game of Life, and named CA variants

`elementary_rule(rule_number, left, center, right)` implements Wolfram's numbering scheme for the
256 possible 1D binary cellular automata directly: the 3-bit neighborhood `(left, center, right)`
packs into an index `0..7`, and bit `idx` of `rule_number` is the output. `rule110_cell` is
literally `elementary_rule(110, left, center, right)` — Rule 110 is proven Turing-complete, the only
one of the 256 elementary rules with that property. `rule_step_1d(cells, n, rule_number)` evolves an
entire 1D lattice one step with wraparound boundaries (`cells[-1]` reads `cells[n-1]`).

`game_of_life_cell(alive, neighbors)` is Conway's rule exactly as usually stated: a live cell
survives with 2 or 3 live neighbors, a dead cell becomes alive with exactly 3, everything else dies
or stays dead. `game_of_life_step(grid, rows, cols, i, j)` is the neighbor-counting half of a GoL
update — despite the name, it does *not* evolve the whole grid; it counts one cell's live
neighbors (out of up to 8, bounds-checked against the grid edges) so the caller can then pass that
count to `game_of_life_cell`.

```python
# a 2x3 grid, row0=[0,1,0], row1=[1,1,0] -- cell (1,1) is alive
grid = [0, 1, 0, 1, 1, 0]
n = runtime.execute("cellular_automata", "game_of_life_step", [grid, 2, 3, 1, 1])["result"]
n
# 2 -- in-bounds neighbors of (1,1) are (0,0)=0, (0,1)=1, (0,2)=0, (1,0)=1, (1,2)=0;
#      the three cells below row 1 (di=1) fall outside a 2-row grid and don't count

runtime.execute("cellular_automata", "game_of_life_cell", [True, n])["result"]
# True -- an alive cell with 2 live neighbors survives
```

`langtons_ant_step(dir, cell_color)` implements the classic ant: on a white cell (`0`), turn right
90° (`(dir+1) % 4`) and flip the cell to black; on a black cell (`1`), turn left 90°
(`(dir+3) % 4`) and flip back to white — the standard rule that produces an initially chaotic,
eventually-periodic "highway" pattern. `wireworld_cell(state, copper_neighbors_excited)` implements
the four-state Wireworld automaton (`0`=empty, `1`=electron head, `2`=electron tail,
`3`=conductor): a head always decays to a tail, a tail always becomes a conductor, and a conductor
becomes a new head only if exactly 1 or 2 of its neighbors are heads — the rule that lets conductor
wires carry discrete "electron" pulses. `totalistic_rule(k, rule_number, total)` generalizes
elementary rules to `k` colors by extracting the digit at position `total` from `rule_number`'s
base-`k` representation. `majority_rule` and `parity_rule` are the two simplest possible
neighbor-counting rules: majority vote (tie goes to `0`) and neighbor-count parity (XOR).

## Verification

None of the six modules behind this page have hand-pinned numeric test assertions.
`test_dimensions.mojo`, `test_chaos.mojo`, `test_information_theory.mojo`,
`test_special_functions.mojo`, and `test_cellular_automata.mojo` are auto-generated coverage smoke
tests — each calls every function once with fixed literal fixtures (`0.5`-style scalars, a
five-element `[0.5, 0.6, 0.7, 0.4, 0.3]` list that is not a valid probability distribution) and
checks only that the result is finite, not that it matches any specific expected value.
`dimensionality` has **no** test file at all under `mojo/tests/libs/` — grepping for `PCAResult`,
`power_iteration`, or `pca(` outside `dimensionality.mojo` itself turns up two unrelated hits
(`test_inference_glm.mojo` and `test_graph_analytics_centrality.mojo`, which use `power_iteration`
for eigenvector-centrality graph analytics, an entirely different call site), not a test for this
module. Every worked number in this page was independently hand-computed in Python from the real
formulas in `mojo/engine/dimensions.mojo`, `dimensionality.mojo`, `information_theory.mojo`,
`special_functions.mojo`, `chaos.mojo`, and `cellular_automata.mojo` — the PCA example was
additionally cross-checked against `numpy.linalg.eigh`'s ground-truth eigenvalues for the same
matrix, and the `erf`/gamma/Bessel values against Python's `math` module and known special-value
identities — before being presented here as fact.

**Next:** see [Symmetric eigendecomposition and thin SVD](ml-eigendecomposition.md) for the
general-purpose eigendecomposition/SVD primitive that `dimensionality`'s power-iteration PCA
pipeline is a purpose-built alternative to, or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
