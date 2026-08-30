---
icon: dice
description: Sampling and MLE/method-of-moments fitting for twenty-six probability distributions, core probability theory (Bayes, combinatorics, entropy), a Gaussian copula with rank-correlation measures, and Cholesky-based generation of correlated normals.
---

# Probability distributions and dependence kernels

Five modules for the mechanics underneath a Monte Carlo model: what shape a random draw takes
(`distributions`), how to recover that shape's parameters from observed data (`distribution_fit`),
what a probability calculation is logically allowed to say (`probability`), and how two or more
variables move together when a single correlation number does not capture the whole relationship
(`copula`, `correlation`). None of the five imports another — each is a flat set of `Float64`
formulas over `std.math`/`std.random`, with no shared struct or status-code vocabulary.

**`correlation` is not the module that measures correlation.** Reading its source is what catches
this: `correlation.mojo`'s docstring is "Cholesky decomposition for correlated Normal sampling +
inverse CDF for QMC/LHS," and every function in it either factors a correlation matrix
(`cholesky_lower`) so it can be used to *generate* correlated draws (`sample_correlated_normal`),
or maps a uniform variate to a distribution's quantile (`probit`, `icdf`) for stratified/QMC
sampling. It has no Pearson, Spearman, or Kendall calculation anywhere in it. Those live one file
over, in `copula.mojo`, alongside the Gaussian copula sampler — `rank_correlation` (Spearman) and
`kendall_tau` sit in the module named for dependence *modeling*, not the one named for correlation
itself.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# A screening test: 99% sensitive, 5% false-positive rate, 1% base rate in the population.
# P(positive) = 0.99*0.01 + 0.05*0.99 = 0.0594
runtime.execute("probability", "bayes", [0.01, 0.99, 0.0594])["result"]
# 0.16666666666666669 -- a positive result is still only 1-in-6 odds of actually having it

# Which distribution family (by AIC) best explains [1, 2, 3, 4, 5]?
runtime.execute("distribution_fit", "best_fit", [[1.0, 2.0, 3.0, 4.0, 5.0]])["result"]
# 2 -- uniform, not normal (0) or exponential (1); see the worked comparison below
```

## The modules

| Module | What it does |
| --- | --- |
| `distributions` | Twenty-six single-draw Monte Carlo samplers (normal through hypergeometric), a universal `sample_one` dispatcher plus a `sample_one_simd4` batch variant, and SIMD4 batch samplers for the ten distributions used most often in hot loops — all drawing from the process's shared, unseeded RNG |
| `distribution_fit` | MLE fitting for normal and exponential, min/max fitting for uniform, a method-of-moments approximation for Weibull, their log-likelihoods, AIC/BIC, an AIC-based best-of-three selector, and normal QQ-plot residuals |
| `probability` | Bayes' theorem, joint/total probability, combinatorics (factorial, combinations, permutations), binomial and Poisson PMFs, and information theory (Shannon entropy, KL divergence, mutual information) |
| `copula` | A bivariate Gaussian copula sampler with its own from-scratch normal CDF/inverse-CDF approximations, plus two rank-based dependence measures — Spearman's rho and Kendall's tau-b |
| `correlation` | Cholesky factorization of a correlation matrix for generating correlated normals, a separate (coarser) inverse-normal-CDF approximation (`probit`), and a distribution-quantile dispatcher (`icdf`) for QMC/Latin-hypercube sampling — no correlation-measurement function lives here |

## `distributions`: twenty-six samplers behind one dispatcher, an unseeded RNG, and a gap at code 6

Every `sample_*` function draws directly from `std.random`'s `random_float64`/`randn_float64` with
no seed argument anywhere in the module — unlike `discrete_event.queue_sim` elsewhere in this
corpus, which takes an explicit seed and reproduces bit-for-bit on request, calling any function
here twice with identical arguments gives two different draws. That makes a literal "here is the
output" example misleading for most of these functions; what follows instead is what each family
guarantees, plus the handful of genuinely deterministic edge cases.

| Family | Functions | Method |
| --- | --- | --- |
| Location-scale, closed-form inverse CDF | `sample_normal`, `sample_uniform`, `sample_lognormal`, `sample_exponential`, `sample_weibull`, `sample_laplace`, `sample_logistic`, `sample_gumbel`, `sample_rayleigh`, `sample_cauchy`, `sample_pareto`, `sample_arcsine`, `sample_halfnormal` | Transform a uniform (or normal) draw directly through the distribution's inverse CDF |
| Shape-parameterized, rejection sampling | `sample_gamma_mt` (Marsaglia-Tsang), `sample_beta` (ratio of two gammas), `sample_student_t` (normal over sqrt of a scaled chi-squared draw), `sample_vonmises` (Best-Fisher rejection loop) | An unbounded `while True` accept/reject loop — almost surely terminates, but has no iteration cap |
| Bounded / project-specific | `sample_triangular`, `sample_pert` (Beta-PERT via `sample_beta`) | Closed-form inverse CDF (triangular) or a beta reparameterization (PERT) |
| Discrete counting | `sample_bernoulli`, `sample_poisson`, `sample_neg_binomial` (gamma-Poisson mixture), `sample_hypergeometric` | Direct simulation (hypergeometric draws without replacement in a loop) or inversion; `sample_poisson` switches to a normal approximation above `lam = 30` |
| Universal dispatch | `sample_one(dt, p0, p1, p2, p3, dv, dp)` | One `Int` type code selects among all of the above, plus `dt=4` (fixed constant, returns `p0`), `dt=13` (custom discrete via a cumulative-probability list `dp` and value list `dv`), and `dt=26` (categorical, returns the index) |
| SIMD4 batch path | `sample_normal_simd4`, `sample_uniform_simd4`, `sample_triangular_simd4`, `sample_lognormal_simd4`, `sample_exponential_simd4`, `sample_bernoulli_simd4`, `sample_gamma_simd4`, `sample_beta_simd4`, `sample_weibull_simd4`, `sample_pert_simd4`, plus `sample_one_simd4` | The same ten distributions, using an explicit `xorshift64` state threaded through the call (`mut s: UInt64`) instead of the stdlib RNG — four draws per call |

**Two deterministic edge cases survive the randomness.** `sample_uniform(5.0, 5.0)` always returns
exactly `5.0` — the formula is `lo + (hi - lo) * u`, and when `hi == lo` the `(hi - lo)` factor
zeroes out whatever `u` was, independent of any RNG state. `sample_triangular(5.0, 5.0, 5.0)` and
`sample_pert(5.0, 5.0, 5.0, 4.0)` are the same: both check `hi - lo == 0.0` and return `lo`
directly before touching the RNG at all. These are the only calls in the module whose output does
not depend on the draw.

**`dt = 6` is a genuine gap, not a hidden distribution.** `mojo/engine/types.mojo`'s own canonical
`dist_type` table — the comment block that defines which integer means which distribution
elsewhere in the engine — lists `5=beta` then jumps straight to `7=exponential`; `6` is not
assigned to anything. `sample_one`'s dispatch chain matches that gap exactly: there is no
`elif dt == 6` arm, so passing `dt=6` falls through to the same `return p0` fallback used for any
unrecognized code (`dt=99` would behave identically) — a caller cannot tell "type 6" apart from a
typo by the return value alone. Both the type table and the dispatcher agree with each other, so
this is a deliberate numbering gap carried consistently through the codebase, not a mismatch
between two disagreeing sources — but it does mean the module's own docstring, "all 27 native Mojo
distributions," is counting slots `0`-`26` (27 of them), not 27 *distinct behaviors*: 26 codes are
wired to a real sampler or discrete-value lookup, and one (`6`) is not.

## `distribution_fit`: MLE for two families, method-of-moments for a third, and an AIC upset

| Function | What it does |
| --- | --- |
| `fit_normal(data)` | MLE: `[mean(data), population_std(data)]`. Empty input returns `[]` rather than dividing by zero. |
| `fit_exponential(data)` | MLE: `rate = 1 / mean(data)`. Returns `1.0` if the mean is non-positive, `0.0` on empty input. |
| `fit_uniform(data)` | `[min(data), max(data)]` — the MLE support bounds for a uniform distribution. |
| `fit_weibull(data)` | Method-of-moments approximation: coefficient of variation → shape (`1.2 / cv`, floored at `0.1`), then scale = `mean / Γ(1 + 1/shape)` using a quadratic gamma-function stand-in, `_gamma_approx`. |
| `log_likelihood_normal(data, mean, std)` / `log_likelihood_exponential(data, rate)` | Closed-form log-likelihood for each family, evaluated at the given parameters. |
| `aic(log_likelihood, k)` | `2k - 2·LL`. |
| `bic(log_likelihood, k, n)` | `k·ln(n) - 2·LL`. |
| `best_fit(data)` | Fits normal, exponential, and a uniform-with-support-check log-likelihood, computes AIC for each (`k=2, 1, 2` parameters respectively), and returns the index (`0`/`1`/`2`) of the lowest. Returns `-1` on empty input, guarding the `params[0]`/`params[1]` reads the three fits would otherwise need. |
| `qq_residuals(data, mean, std)` | Sorts `data`, then returns `sorted[i] - (mean + std·Φ⁻¹((i+0.5)/n))` per point, using its own inverse-erf-based `_normal_quantile`. |

**Worked comparison — `best_fit` genuinely can pick the "wrong-looking" family.** For
`data = [1.0, 2.0, 3.0, 4.0, 5.0]`, `fit_normal` gives `mean = 3.0`, `std = 1.4142135623730951`
(population standard deviation, dividing by `n` not `n-1`), and that plugged into
`log_likelihood_normal` gives `LL = -8.827560617423226`, so `aic(LL, 2) = 21.65512123484645`.
`fit_exponential` gives `rate = 0.3333333333333333`, `LL = -10.49306144334055`,
`aic(LL, 1) = 22.9861228866811`. `fit_uniform` gives `[1.0, 5.0]`; its own internal
`_log_likelihood_uniform` (not exposed on its own) gives `LL = -6.931471805599453`
(`= -n·ln(4)`), so `aic(LL, 2) = 17.862943611198908`. Uniform's AIC is the lowest of the three, so
`best_fit([1.0, 2.0, 3.0, 4.0, 5.0])` returns `2`, not `0` — on five evenly-spaced points, a flat
distribution over `[1, 5]` really is a better AIC fit than a bell curve centered at `3`, because
AIC only rewards likelihood at the cost of parameter count, and evenly-spaced data has no tails
for a normal distribution to explain away. Every number above was independently re-derived from the
formulas in `mojo/engine/distribution_fit.mojo` in plain Python (see
[Verification](#verification)).

**`fit_weibull`'s docstring says "iterative estimation"; the code takes one direct pass.** For the
same five points, `cv = std/mean = 0.4714...`, `shape = 1.2/cv = 2.5455844122715705`, and
`_gamma_approx(1 + 1/shape) = 0.8914274653601822` (against SciPy's/`math.gamma`'s true
`Γ(1.3928371...) = 0.8876774286375584` — about a 0.42% relative error from the quadratic
interpolation `_gamma_approx` uses for its `[1, 2)` range), giving
`scale = mean / gamma_approx = 3.365388791097935`. There is no loop refining `shape` or `scale`
against the data a second time; "iterative" in the docstring is closer to describing
`_gamma_approx`'s own recursive range-reduction (it recurses to shift its argument into `[1, 2)`
before applying the quadratic) than to the fit itself, which is a single closed-form CV-matching
step.

## `probability`: Bayes, combinatorics, and information theory

| Function | What it does |
| --- | --- |
| `bayes(prior, likelihood, evidence)` | `P(A\|B) = likelihood · prior / evidence`; returns `0.0` if `evidence` is within `1e-15` of zero. |
| `joint_probability(p_a, p_b_given_a)` | `P(A∩B) = p_b_given_a · p_a`. |
| `total_probability(priors, likelihoods)` | `Σ priors[i]·likelihoods[i]` over `min(len(priors), len(likelihoods))` terms. |
| `factorial(n)` | Iterative `n!`; `1.0` for `n <= 1`. |
| `combinations(n, k)` | `C(n,k)` via the multiplicative formula (using the smaller of `k`, `n-k`); `0.0` outside `0 <= k <= n`. |
| `permutations(n, k)` | `P(n,k) = n!/(n-k)!`; `0.0` outside `0 <= k <= n`. |
| `binomial_pmf(k, n, p)` | `C(n,k)·pᵏ·(1-p)ⁿ⁻ᵏ`; `0.0` outside `0 <= k <= n`. |
| `poisson_pmf(k, lam)` | `λᵏ·e⁻λ/k!`; `0.0` for `k < 0`. |
| `entropy(probs)` | Shannon entropy in **bits**: `-Σ p·log₂(p)`, skipping entries with `p <= 1e-15` (the `0·log 0 = 0` convention). |
| `kl_divergence(p, q)` | `Σ p·log₂(p/q)` in bits over the shared prefix of both lists; adds a `1e10` sentinel term per entry where `p > 0` but `q ≈ 0` (undefined KL) instead of producing `inf`. |
| `mutual_information(joint)` | `I(X;Y) = ΣΣ p(x,y)·log₂(p(x,y)/(p(x)p(y)))` in bits, computing the marginals from the 2-D `joint` table itself. |

**The disease-test example in the opening code block is the classic illustration of why `bayes`
matters**: even at 99% sensitivity, a 1% base rate and a 5% false-positive rate combine to an
evidence term of `0.0594`, and `bayes(0.01, 0.99, 0.0594) = 0.16666...` — a positive result moves
the odds from 1-in-100 to only 1-in-6, not to near-certainty. `total_probability([0.3, 0.7],
[0.9, 0.2]) = 0.3·0.9 + 0.7·0.2 = 0.41` is the same law applied without collapsing to a single
posterior.

**Entropy, KL, and mutual information all check out against their textbook extremes.**
`entropy([0.5, 0.5]) = 1.0` bit exactly (a fair coin carries one bit of surprise) and
`entropy([0.25, 0.25, 0.25, 0.25]) = 2.0` bits exactly (four equally likely outcomes, `log₂4`).
`kl_divergence([0.5, 0.5], [0.9, 0.1]) = 0.7369655941662062` bits — the cost, in bits, of coding a
fair-coin source with a model that expects it to land heads 90% of the time. For a joint table with
independent margins (`[[0.25, 0.25], [0.25, 0.25]]`), `mutual_information` returns exactly `0.0`;
for a dependent one concentrated on the diagonal (`[[0.4, 0.1], [0.1, 0.4]]`), it returns
`0.2780719051126378` bits of shared information between the two variables. Every one of these was
independently recomputed in Python from the formulas above and matches to full double precision.

## `copula` and `correlation`: dependence beyond a single number, in two unrelated files

**`copula.gaussian_copula_sample(n, rho)`** draws `n` bivariate pairs `(u1, u2)`, each marginally
uniform on `[0, 1]`, whose *underlying* Gaussian latent variables are correlated at `rho`. It does
this entirely by hand: its own `_box_muller_pair` (Box-Muller via a from-scratch Taylor-series
`_sin_approx`/`_cos_approx`, not `std.math`'s), a hardcoded 2×2 Cholesky (`x2 = rho·z1 +
sqrt(1-rho²)·z2`) rather than a call to `correlation.cholesky_lower`, and its own
`norm_cdf_approx` to map the correlated normals back to `[0, 1]`. Because the RNG is unseeded, no
single call's output is reproducible, but the *statistical* property is checkable: running the
exact algorithm 200,000 times at `rho = 0.7` (Python's own RNG standing in for Mojo's, since the
shape of the construction — not the specific stream — is what's being checked) gives a Spearman
correlation of the resulting `u1, u2` pairs of `0.6827`, against the closed-form Gaussian-copula
identity `6/π·arcsin(ρ/2) = 0.68291`, and a Kendall's tau of `0.4938` against
`2/π·arcsin(ρ) = 0.49363` — both within the noise expected at that sample size, confirming the
implementation reproduces the standard Gaussian copula rather than some other dependence structure.

**`copula.rank_correlation` and `copula.kendall_tau`** are ordinary Spearman and Kendall's tau-b,
computed deterministically from data (no RNG involved) and independently verified against SciPy.
For `x = [1, 2, 3, 4, 5]`, `y = [2, 1, 4, 3, 5]`: `rank_correlation(x, y) = 0.8` and
`kendall_tau(x, y) = 0.6`, matching `scipy.stats.spearmanr`/`kendalltau` exactly. Both guard the
same failure mode the same way — `n < 2` or mismatched lengths return `0.0` rather than reading
past the shorter list's end (an uncatchable abort otherwise), per the source's own comments. Tied
values are handled correctly too: `_rank` assigns the average rank across a tie block before either
function runs Pearson-on-ranks (Spearman) or counts concordant/discordant pairs with a separate
tie tally (Kendall's tau-b denominator), verified against SciPy on a tied input as well.

**`copula.norm_cdf_approx`/`norm_ppf_approx` and `correlation.probit` are two independent
implementations of the same two functions, at two different precisions.** `norm_cdf_approx` is the
Abramowitz & Stegun 26.2.17 approximation (stated max error `7.5e-8`); `norm_ppf_approx` is Peter
Acklam's rational approximation, accurate to about `1e-9` — reproducing it in Python and comparing
to `scipy.stats.norm.ppf` confirms errors of `1.6e-9` to `3.5e-10` across `p = 0.9, 0.975, 0.99`.
`correlation.probit`, by contrast, uses the coarser Abramowitz & Stegun 26.2.23 rational
approximation (stated max error `4.5e-4`) — the same comparison shows errors of `1.8e-4` to
`4.4e-4` at the same `p` values, three to four orders of magnitude worse than `norm_ppf_approx`.
Neither module imports the other's version; a caller who needs the more accurate inverse CDF and
reaches for `correlation.probit` instead of `copula.norm_ppf_approx` gets a real, measurable
accuracy loss, not a rounding difference.

**`correlation.cholesky_lower` and `correlation.icdf`** are the two building blocks for
scenario generation. `cholesky_lower(corr, n)` factors an `n×n` correlation matrix into a lower
triangular `L` with `L·Lᵀ = corr`; for
`corr = [[1.0, 0.5, 0.3], [0.5, 1.0, 0.2], [0.3, 0.2, 1.0]]` it returns
`[[1.0, 0, 0], [0.5, 0.8660254037844386, 0], [0.3, 0.0577350269189626, 0.9521904571390466]]`,
matching NumPy's `linalg.cholesky` to full double precision. A non-positive-semidefinite `corr`
does not crash it: a negative diagonal term is clamped to `0.0` before the square root
(`sqrt(max(diag, 0.0))`) rather than producing a `NaN`. `sample_correlated_normal(L, n_vars)` then
multiplies `L` by `n_vars` fresh `randn_float64()` draws to produce one vector of correlated
standard normals — non-deterministic per call, like everything in `distributions`.
`icdf(u, dt, p0, p1, p2)` is a separate, closed-form quantile dispatcher for QMC/Latin-hypercube
sampling, covering the subset of `distributions.sample_one`'s type codes that have a closed-form
inverse CDF — normal (via `probit`), uniform, triangular, lognormal, exponential, and Weibull, plus
`dt=4` for a fixed constant — and deliberately omits the ones that don't, such as beta, gamma, and
Poisson, which `sample_one` only reaches via rejection sampling or a series expansion.

{% hint style="warning" %}
**`cholesky_lower` has no guard against a `corr` shorter than `n`; `sample_correlated_normal` does.**
Reading `cholesky_lower`'s body directly: it indexes `corr[i][i]` and `corr[i][j]` for every
`i, j < n` with no bounds check at all — if the caller passes a `corr` with fewer than `n` rows,
that is an unguarded, uncatchable out-of-bounds read that aborts the worker. `sample_correlated_normal`,
by contrast, explicitly checks `len(L) < n_vars` and every row's length before touching `L[i][j]`,
returning an empty list rather than aborting, and its own comment says why: "an unguarded `L[i][j]`
read aborts the worker (uncatchable)." The runtime contract's `count_relations` entry for
`cholesky_lower` (binding `corr`'s length to `n`) is exactly the enforcement point that has to catch
a mismatch before the call reaches this kernel, since the kernel itself will not.
{% endhint %}

## Verification

All five `mojo/tests/libs/test_{distributions,distribution_fit,probability,copula,correlation}.mojo`
files are the same auto-generated coverage-smoke pattern used across this corpus: every function is
called once on a shared `0.5`-valued fixture (or `5`/`0.5` for the `Int`-typed distribution-type
codes) and the test only checks that the result is finite (or, for list-returning functions, merely
non-empty) — none of the five pin a specific expected number, and none of them exercise
`cholesky_lower` or `sample_correlated_normal` at all (only `probit` and `icdf` are covered in
`test_correlation.mojo`, since the auto-generator's shared fixture has no ready-made `List[List[Float64]]`
value to hand `cholesky_lower`'s `corr` parameter).

Every worked number in this page — the Bayes disease-test posterior, the `best_fit` AIC comparison
and its normal/exponential/uniform log-likelihoods, the `fit_weibull` shape/scale/gamma-approximation
figures, the entropy/KL/mutual-information triple, the Spearman/Kendall pair on `[1,2,3,4,5]` vs.
`[2,1,4,3,5]`, the Gaussian-copula rank-correlation identities, the `norm_ppf_approx`-vs-`probit`
precision comparison, and the 3×3 Cholesky factorization — was independently re-derived from the
real formulas in `mojo/engine/{distributions,distribution_fit,probability,copula,correlation}.mojo`
using a standalone Python script (plain `math`, cross-checked against `scipy.stats` and `numpy.linalg`
where a reference implementation exists), not lifted from a test file or asserted from memory. Values
that depend on `exp`/`log`/`sqrt` may differ from a live Mojo run in the last one to a few
representable digits — Mojo's own transcendental functions round a fraction of an ULP differently
from CPython's, the same caveat noted elsewhere in this corpus — but no worked number here depends on
that last-digit agreement to make its point.

**Next:** [Statistical inference](statistical-inference.md) covers the question that comes after a
distribution is fit — is an observed difference real, and how much data does it take to know — and
[Discrete-event simulation](discrete-event-simulation.md) is the one place elsewhere in this corpus
where a random draw *is* seeded and reproducible, the opposite of every sampler in `distributions`
here.
