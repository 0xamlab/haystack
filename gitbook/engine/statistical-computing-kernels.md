---
icon: dice
description: Descriptive statistics with a bundled introsort, bootstrap and jackknife resampling for confidence intervals and bias, and Monte Carlo simulation of random walks, diffusions, and point processes.
---

# Statistical computing kernels

Three kernel modules for three related but separate jobs. `stats` answers "what does this sample
look like" — mean, variance, standard deviation, percentiles, median — over flat `List[Float64]`
buffers, and carries its own introsort to get there. `stats_bootstrap` answers "how much would that
answer move if I had drawn a different sample" — bootstrap confidence intervals, bias, standard
error, a permutation test, jackknife leave-one-out estimates, and a BCa-corrected interval — by
resampling with replacement rather than assuming a parametric form. `stochastic` answers a different
question again: given a generative model (a biased coin flip, a diffusion, an arrival process),
what does one simulated path or one Monte Carlo estimate look like. None of the three calls into
either of the others.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

data = [0.5, 0.6, 0.7, 0.4, 0.3]

runtime.execute("stats", "compute_mean", [data, 5])["result"]
# 0.5
runtime.execute("stats", "compute_std_from_values", [data, 5])["result"]
# 0.15811388300841894 -- ddof=1 sample standard deviation, mean computed internally

runtime.execute("stats_bootstrap", "jackknife_se", [data])["result"]
# 0.07071067811865478 -- jackknife standard error of the mean (deterministic, no resampling RNG)

runtime.execute("stochastic", "expected_hitting_time", [0.5, 5])["result"]
# 25.0 -- an unbiased +-1 walk starting at 0 takes target^2 steps to reach +5 on average
```

## The modules

| Module | What it does |
| --- | --- |
| `stats` | descriptive statistics (mean, variance, standard deviation, percentile, quantile, median) over `List[Float64]` buffers, plus the introsort that the percentile-family functions sort with |
| `stats_bootstrap` | bootstrap resampling: replicate generation, percentile confidence intervals for mean/std/median, bootstrap bias and standard error, a permutation test, jackknife leave-one-out estimates, and a BCa-corrected interval |
| `stochastic` | stochastic-process simulation: 1D/2D random walks, Brownian motion, geometric Brownian motion, a Poisson arrival process, Ornstein-Uhlenbeck mean reversion, a birth-death chain, Monte Carlo estimation of π, and hitting/first-passage times |

## `stats`: descriptive statistics and the introsort underneath them

| Function | What it does |
| --- | --- |
| `compute_mean(v, n)` | Arithmetic mean of `v[0..n)`: `Σv / n`. |
| `compute_variance(v, n, mean)` | Sample variance (ddof=1) about a caller-supplied `mean`; returns `0.0` for `n <= 1`. |
| `compute_std(v, n, mean)` | `sqrt(compute_variance(v, n, mean))`, in one kernel call rather than a caller-side square root of a value it already fetched. |
| `compute_std_from_values(v, n)` | Computes the mean internally, then the ddof=1 std — no `mean` parameter for a caller to supply a wrong or stale one. |
| `pctile(v, n, p)` | O(1) index into a buffer the caller must have **already sorted**; not part of the discoverable capability catalog (see below). |
| `count_below_zero(v, n)` | Count of `v[0..n)` that are negative. |
| `fast_sort(a, n)` | Introsort (median-of-3 quicksort with a depth-limited fallback and an insertion-sort floor) of `a[0..n)`, in place. |
| `ins_sort(a, lo, hi)` | Insertion sort of `a[lo..hi]`, in place — `fast_sort`'s base case for small partitions and its fallback when the recursion-depth budget runs out. |
| `part3(a, lo, hi)` | Median-of-3 partition of `a[lo..hi]`; returns the pivot's final index, or `-1` if the window has fewer than three elements. |
| `ilog2(n)` | Integer `floor(log2(n))`; sets `fast_sort`'s recursion-depth budget (`2 * ilog2(n)`). |
| `sort_values(v, n)` | Ascending-sorted **copy** of the finite values among the first `n` (drops NaN/±inf); leaves `v` untouched. |
| `quantile(v, n, q)` | Linear-interpolated quantile of **unsorted** input (numpy `'linear'` convention), `q` in `[0, 1]`; sorts a private copy via `sort_values`. |
| `percentile(v, n, p)` | `quantile(v, n, p / 100.0)`, `p` in `[0, 100]`. |
| `median(v, n)` | `quantile(v, n, 0.5)` — the mean of the two middle values for even `n`. |

**`pctile` and `percentile` are not interchangeable, and the name similarity is the trap.**
`percentile`/`quantile`/`median` all sort a private copy first, so they are safe on unsorted input.
`pctile` does not sort — its own docstring calls this out explicitly as a deliberate, unfixed hazard
(`surfaces: internal` keeps it out of `algenta.capabilities()`'s discoverable catalog for exactly
this reason) — it is an O(1) lookup into a buffer that must already be sorted. Calling it on
unsorted data returns a plausible, wrong number with no error. Concretely, on the unsorted
`[0.5, 0.6, 0.7, 0.4, 0.3]`:

```python
runtime.execute("stats", "pctile", [data, 5, 5])["result"]
# 0.5 -- WRONG: this is just data[0], because the p=5 index (n-1)*p//100 = 0
runtime.execute("stats", "percentile", [data, 5, 5])["result"]
# 0.32 -- correct: sorts a copy to [0.3, 0.4, 0.5, 0.6, 0.7] first, then interpolates
```

Both calls return a finite `Float64` and neither raises — the only way to tell `pctile` was fed
the wrong kind of input is to already know the precondition. Internally, `pctile` is used by
`engines/monte_carlo.mojo`, which always sorts before calling it.

**Passing `n = 0` (or a negative `n`) to `compute_mean`, `compute_variance`, `compute_std`, or
`compute_std_from_values` is worse than a wrong answer.** The module's own docstrings describe this
as measured on a compiled worker, not theoretical: `compute_mean(five_values, 0)` divides `0.0` by
`0.0`, and a non-finite `Float64` return on this serialization path ends the serving process
outright — not an exception the caller can catch. `sort_values`, `quantile`, `percentile`, and
`median` are the safer family: they clamp `n` to `len(v)` and return `0.0` for an empty result
instead, at the cost of silently answering a question ("what if I ask for more values than exist")
that arguably should have been refused rather than clamped.

## `stats_bootstrap`: resampling for confidence intervals, bias, and significance

| Function | What it does |
| --- | --- |
| `bootstrap_replicate(data)` | One resample-with-replacement replicate, the same size as `data`. |
| `bootstrap_mean_ci(data, n_bootstrap, confidence=0.95)` | Percentile bootstrap CI for the mean: resamples `n_bootstrap` times, sorts the resampled means, and reads off the `[α/2, 1-α/2]` order statistics. |
| `bootstrap_std_ci(data, n_bootstrap, confidence=0.95)` | Same percentile-bootstrap recipe, for the sample standard deviation. |
| `bootstrap_median_ci(data, n_bootstrap, confidence=0.95)` | Same recipe, for the median. |
| `bootstrap_bias(data, n_bootstrap, stat_type=0)` | `E[θ*] - θ`: the mean of the bootstrap replicates' statistic, minus that statistic on the original data. `stat_type`: `0` = mean, `1` = median. |
| `bootstrap_se(data, n_bootstrap, stat_type=0)` | Standard deviation of the bootstrap replicates' statistic. |
| `bootstrap_test(data1, data2, n_bootstrap)` | Permutation-test p-value for "these two groups have the same mean": pools both samples, shuffles, and counts how often a random split's mean-difference is at least as extreme as the one actually observed. |
| `jackknife_mean(data)` | The `n` leave-one-out means. |
| `jackknife_se(data)` | Jackknife standard error of the mean, computed from the leave-one-out means; `0.0` for `n < 2`. |
| `bca_correction(data, n_bootstrap, confidence=0.95)` | Bias-corrected and accelerated (BCa) CI for the mean — adjusts the percentile endpoints by a bias factor `z0` (how many bootstrap means fall below the original) and an acceleration factor `a` (from the jackknife replicates' skew), rather than reading off the plain `[α/2, 1-α/2]` order statistics. |

### A deterministic worked example: jackknife

Unlike everything else in this module, `jackknife_mean` and `jackknife_se` involve no resampling —
they are a closed-form pass over the data, so they are the one pair here whose output is exactly
reproducible. On `[0.5, 0.6, 0.7, 0.4, 0.3]` (mean `0.5`, `n = 5`), each leave-one-out mean is
`(total - data[i]) / (n - 1)` with `total = mean * n = 2.5`:

```python
runtime.execute("stats_bootstrap", "jackknife_mean", [data])["result"]
# [0.5, 0.475, 0.45, 0.525, 0.55]
runtime.execute("stats_bootstrap", "jackknife_se", [data])["result"]
# 0.07071067811865478
```

Independently: the leave-one-out means average to `0.5`, their squared deviations from that average
sum to `0.00875`, and `jackknife_se`'s `sqrt((n-1)/n * Σ(d²))` gives
`sqrt(4/5 * 0.00875) = sqrt(0.007) = 0.0707106781...` — matching the kernel's value to every digit.

### `n_bootstrap` is silently capped for the CI functions, but not for their siblings

`bootstrap_mean_ci`, `bootstrap_std_ci`, `bootstrap_median_ci`, and `bca_correction` each clamp
`n_bootstrap` to `10000` before the resampling loop runs, with the same comment in the source at
every occurrence: the module's `_sort_floats` helper is a plain insertion sort, `O(n_bootstrap²)`,
run over the resampled statistics to find the percentile endpoints — so an uncapped request would
scale quadratically. `bootstrap_bias`, `bootstrap_se`, and `bootstrap_test` never sort anything and
carry no such ceiling; a caller can request an arbitrarily large `n_bootstrap` for those three, at
a cost that scales linearly rather than being refused.

**`bootstrap_test` is also the one function in this module with no `n_bootstrap <= 0` guard at
all.** The three CI functions and `bca_correction` explicitly check `n_bootstrap <= 0` and return an
empty list; `bootstrap_test` divides `Float64(count) / Float64(n_bootstrap)` unconditionally, so
`bootstrap_test(data1, data2, 0)` computes `0.0 / 0.0` — a non-finite `Float64` return of exactly
the shape `stats.mojo`'s docstrings measure ending a worker process for `compute_mean`. This one is
a logic observation from reading the source directly, not a claim of a measurement on this specific
function — but the arithmetic is unambiguous, and a caller passing `n_bootstrap = 0` here is not
protected the way the CI functions protect it.

**`jackknife_mean` has no `n < 2` guard, unlike its sibling `jackknife_se`.** `jackknife_se` checks
`n < 2` and returns `0.0`; `jackknife_mean` does not, so a single-element `data` divides by
`n - 1 = 0`. Concretely, `jackknife_mean([5.0])` computes `(5.0 - 5.0) / (1 - 1) = 0.0 / 0.0`, i.e.
its one-element result is `[nan]` rather than a refusal or a sentinel — the same asymmetry pattern
as `bootstrap_test` above, this time between two functions in the same file rather than within one.

### Distinct from `inference.resample`

[Statistical inference](statistical-inference.md) documents a different bootstrap: `inference
.resample`'s `bootstrap_ci_flat` and `permutation_test_flat` take explicit `seed` and `stream`
arguments and are built to reproduce bit-for-bit — "every draw is a pure function of `(seed,
stream, draw index)`," per that page — and return a status-coded struct with rank diagnostics and
Monte Carlo half-widths for the endpoints. Nothing in `stats_bootstrap` takes a seed at all: every
function here draws from the same process-global, unseeded `random_float64()`, so two calls to
`bootstrap_mean_ci` with identical arguments produce different intervals, and there is no way from
this module's signatures to fix that. The two modules solve the same statistical problem with
different reproducibility guarantees, not one problem solved twice.

## `stochastic`: random walks, diffusions, and Monte Carlo

| Function | What it does |
| --- | --- |
| `random_walk_1d(n_steps)` | Simple symmetric walk: each step is `+1.0` or `-1.0` with equal probability. Returns `n_steps + 1` values starting at `0.0`. |
| `random_walk_2d(n_steps)` | The lattice version: each step moves `+1`/`-1` in `x` or `y`, chosen among the four cardinal directions with equal probability. Returns `n_steps + 1` `[x, y]` pairs. |
| `brownian_motion(n_steps, dt=0.01)` | A discretized Wiener process: cumulative sum of `N(0, sqrt(dt))` increments, via a Box-Muller polar-rejection normal generator. Continuous-valued, unlike the lattice walks above. |
| `geometric_brownian_motion(s0, mu, sigma, dt, n_steps)` | `S(t+dt) = S(t) * exp((μ - σ²/2)dt + σ√dt·Z)`. Every value stays strictly positive, since it is `s0` times a product of exponentials. |
| `poisson_process(rate, duration)` | Event times from a Poisson process of the given `rate`, built from exponential inter-arrival times `-ln(U)/rate`. Returns sorted event times, all `< duration`; empty if `rate <= 0` or `duration <= 0`. |
| `ornstein_uhlenbeck(x0, theta, mu, sigma, dt, n_steps)` | Euler-Maruyama discretization of the mean-reverting SDE `dx = θ(μ - x)dt + σdW`. |
| `birth_death_process(birth_rate, death_rate, initial, n_steps)` | A population that gains one with probability `birth_rate / (birth_rate + death_rate)` or loses one otherwise, each step; floored at `0` and never negative. |
| `monte_carlo_pi(n_samples)` | Estimates π as `4 * (points inside the unit quarter-circle) / n_samples`, from uniform points in the unit square. |
| `expected_hitting_time(p, target)` | Closed-form expected steps for a biased `±1` walk to first reach `target > 0`: `target²` when unbiased (`p = 0.5`), `target / (2p - 1)` when `p > 0.5`, and `-1.0` (infinite) when `p < 0.5`. |
| `first_passage_time(n_simulations, target)` | Monte Carlo estimate of the same quantity: simulates `n_simulations` unbiased walks (each capped at 100,000 steps) and averages the steps taken until `\|position\| >= \|target\|`. |

### `expected_hitting_time` is exact; `first_passage_time` estimates the unbiased case of it

`expected_hitting_time` is a closed-form formula with no randomness, so — unlike the rest of this
module — its output is exactly reproducible:

```python
runtime.execute("stochastic", "expected_hitting_time", [0.5, 5])["result"]
# 25.0  -- unbiased: target^2 = 5^2
runtime.execute("stochastic", "expected_hitting_time", [0.7, 5])["result"]
# 12.500000000000004  -- biased toward +1: target / (2p - 1) = 5 / 0.4 = 12.5
runtime.execute("stochastic", "expected_hitting_time", [0.3, 5])["result"]
# -1.0  -- biased toward -1: a positive target is never reached in expectation
```

`first_passage_time` simulates the same question for the unbiased case only (`p = 0.5` is not a
parameter it takes) by actually running `n_simulations` random walks and averaging how long each
took to reach `|target|`; its answer is a Monte Carlo estimate of the `25.0` above, not the same
closed form, and will vary from call to call around that true value as `n_simulations` grows.

### Every simulation function here is unseeded

None of the ten functions in `stochastic` take a seed, RNG state, or stream argument — every one
draws from the same process-global `random_float64()` that `stats_bootstrap` uses. `expected_hitting_time`
is the sole exception because it has no randomness to seed: it is a formula, not a simulation.
Two calls to `random_walk_1d(10)`, `brownian_motion(100)`, or `monte_carlo_pi(10000)` with identical
arguments will not produce the same path or estimate. `monte_carlo_pi`'s convergence rate follows
directly from its own construction — each of the `n_samples` points falls inside the quarter-circle
independently with probability `p = π/4 ≈ 0.7853982`, so the returned estimate `4 * mean(indicator)`
has standard error `4 * sqrt(p(1-p)/n_samples) ≈ 1.642 / sqrt(n_samples)`: about `0.0164` at
10,000 samples and `0.00164` at 1,000,000 — shrinking with the square root of the sample count, as
any Monte Carlo average does, and never reaching zero at any finite `n_samples`.

## Verification

All three `mojo/tests/libs/test_*.mojo` files behind this page (`test_stats.mojo`,
`test_stats_bootstrap.mojo`, `test_stochastic.mojo`) are auto-generated coverage smoke tests: each
calls every function once with a fixed `[0.5, 0.6, 0.7, 0.4, 0.3]`-style fixture (or the literal
`0.5`/`5` for scalar arguments) and checks only that the result is finite (or, for list-returning
functions, that the returned length is non-negative) — none of them pins a specific numeric output.
The worked examples above were computed independently in plain Python from the real formulas in
`mojo/engine/stats.mojo`, `stats_bootstrap.mojo`, and `stochastic.mojo`, and every deterministic one
(`compute_mean`, `compute_std_from_values`, `percentile`/`pctile`, `jackknife_mean`/`jackknife_se`,
`expected_hitting_time`) can be reproduced exactly by re-running the same arithmetic; the genuinely
random functions (everything in `stochastic` except `expected_hitting_time`, and everything in
`stats_bootstrap` except `jackknife_mean`/`jackknife_se`) are instead characterized by the
deterministic guarantees their formulas do provide — value ranges, monotonicity, and convergence
rates — rather than by a single pinned number that a rerun would not reproduce.

**Next:** see [Statistical inference](statistical-inference.md) for the seeded, status-coded sibling
of the bootstrap CI here, or browse the [Runtime library catalog](runtime-library-catalog.md) for
every module and function.
