---
icon: list-check
description: Two-arm experiment sizing and bandit selection, a compact single-formula causal-effects toolkit, classical decision theory under uncertainty, an ML-to-decision fusion layer, and five nonparametric hypothesis tests.
---

# A/B testing and causal inference kernels

Five small, independent modules for the question that comes after an experiment or an
observational dataset produces a number: is it real, how big is it, and what should you do about
it. `ab_testing` sizes and reads out a two-arm experiment and runs two multi-armed-bandit
selection rules. `causal` is a compact library of single-formula causal-effect estimators — ATE,
ATT, inverse-propensity weighting, difference-in-differences, an instrumental-variable Wald
estimator, regression discontinuity. `decision_analysis` is textbook decision theory under
uncertainty — expected value, expected utility, and the five classical criteria for choosing an
alternative from a payoff matrix. `decision_ml_fusion` is a set of small formulas for wiring an
ML model's output into a downstream simulation or reinforcement-learning decision loop. And
`hypothesis` is five nonparametric significance tests. None of the five imports any of the
others, and as the sections below work out with real numbers, two of them sit next to a newer,
more rigorous sibling package that already has its own page — `causal` beside
[`causal_inference.*`](causal-inference.md), and `hypothesis` beside
[`inference.assume`'s parametric tests](statistical-inference.md). Nothing in any of these five
modules refuses to run when its assumptions do not hold; each returns a plain number and leaves
the checking to the caller.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Two-proportion z-test: 500/1000 conversions in A, 600/1000 in B
runtime.execute("ab_testing", "z_test_proportions", [500, 1000, 600, 1000])["result"]
# [-4.4946657497549465, 6.974308864871048e-06] -- z-statistic, then p-value

# The same shape of question asked as a causal effect instead of a test:
# mean(treated) - mean(control), no p-value attached
runtime.execute("causal", "ate", [[10.0, 12.0, 11.0], [5.0, 6.0, 7.0]])["result"]
# 5.0
```

## The modules

| Module | What it does |
| --- | --- |
| `ab_testing` | Sample-size and minimum-detectable-effect planning for a two-proportion test, the two-proportion z-test with a Wilson-score confidence interval, relative uplift, a significance check, statistical power, an approximate sequential-testing boundary, and two multi-armed-bandit arm-selection rules (epsilon-greedy, UCB1). |
| `causal` | A compact, single-formula causal-effects toolkit: ATE and ATT as plain mean differences, a single-feature logistic-shaped propensity score, inverse-propensity weighting, difference-in-differences, regression discontinuity, an instrumental-variable Wald estimator, stratified ATE, Cohen's d, and the sample size needed to detect a given ATE. |
| `decision_analysis` | Classical decision theory under uncertainty: expected value and CRRA expected utility over a probability-weighted outcome list, the best alternative from a payoff matrix by expected value, the five textbook non-probabilistic criteria (maximin, maximax, Hurwicz α, Laplace, minimax regret), the expected value of perfect information, and a sensitivity sweep over one state's probability. |
| `decision_ml_fusion` | Ten small formulas for wiring an ML model's output probability or confidence into a downstream simulation, optimization, or RL decision: temperature-sharpened simulation weights, a mean-variance simulation objective, model/prior blending, prediction regret, counterfactual utility, policy-gradient advantage, potential-based reward shaping, Chebyshev multi-objective scalarization, a confidence gate, and a single-action UCB exploration score. |
| `hypothesis` | Five nonparametric significance tests and their shared ranking primitive: rank data with average tie-breaking, Mann-Whitney U, the Wilcoxon signed-rank test, Kruskal-Wallis H, Fisher's exact test for a 2x2 table, and a sign test against a hypothesised median. |

## `ab_testing`: planning and reading a two-arm experiment

```python
runtime.execute("ab_testing", "sample_size_proportion", [0.1, 0.12, 0.05, 0.8])["result"]
# 3842 -- per-group n to detect a 10% -> 12% lift at alpha=0.05, power=0.8

runtime.execute("ab_testing", "confidence_interval_proportion", [50, 100, 0.95])["result"]
# [0.40381116849565724, 0.5961888315043428] -- Wilson score interval, not Wald

runtime.execute("ab_testing", "relative_uplift", [0.1, 0.12])["result"]
# 0.1999999999999999 -- (0.12 - 0.1) / 0.1
```

`z_test_proportions` and `confidence_interval_proportion` share nothing at the code level —
the confidence interval is a genuine Wilson score interval (it inverts the normal approximation
around the *estimated* proportion rather than assuming symmetric Wald error bars), which is why
its bounds in the example above are not simply `0.5 +/- margin`. Both `_norm_cdf` and its inverse
`_norm_ppf` are the module's own Abramowitz-and-Stegun / Beasley-Springer-Moro rational
approximations — the same shape of approximation `inference.core`'s bisection-based t-quantile
solver uses for a *different* distribution, but this module never calls that one; it has its own.

`sequential_test` is explicitly an approximation of its own kind, and says so in its own source
comment: it widens the fixed z-boundary by `1/sqrt(info_frac)` where
`info_frac = total / (total + 100.0)` — a stand-in for "fraction of a planned final sample size"
that is not derived from any sample size you actually declared, just a constant `100` baked into
the formula. It is a plausible-shaped alpha-spending boundary, not a calibrated O'Brien-Fleming or
Pocock boundary; treat its `0`/`1`/`2` (continue / A wins / B wins) as a heuristic stopping
suggestion, not a peeking-safe guarantee.

`epsilon_greedy_select` and `ucb1_select` both take **parallel** `rewards: List[Float64]` and
`counts: List[Int]` lists and guard the case a `causal`/`hypothesis`-family kernel would not: if
`counts` is shorter than `rewards`, indexing `counts[i]` for an out-of-range `i` would otherwise
abort the whole worker uncatchably (the same failure mode documented for other kernel families in
this corpus), so both functions check `len(counts) < n_arms` up front and return arm `0` rather
than reach that index at all.

```python
rewards, counts = [5.0, 3.0, 1.0], [10, 10, 0]
runtime.execute("ab_testing", "ucb1_select", [rewards, counts, 20])["result"]
# 2 -- arm 2 has never been pulled, so it is explored before any UCB score is computed

runtime.execute("ab_testing", "ucb1_select", [rewards, [10, 10, 10], 30])["result"]
# 0 -- all three visited; mean+bonus is 1.3248 / 1.1248 / 0.9248, arm 0 wins
```

## `causal`: the oldest of three causal-effects generations in this codebase

`causal.mojo`'s own docstring names its target plainly: "Replaces: dowhy / causalml basics." It
is a genuine, separate module from the two other causal-effects surfaces already documented on
[Causal inference](causal-inference.md) — the bare `propensity` module (nearest-neighbor and
caliper matching, balance diagnostics, trimming) and the `causal_inference.*` package
(identification via DAGs, doubly-robust estimation, sensitivity analysis, a full status
vocabulary). All three implement some version of "propensity score" and "stratified ATE"
independently, under different function names, with neither newer module calling into this older
one. `causal` is by a wide margin the simplest of the three:

* **`propensity_score`** takes a single `List[Float64]` of one feature (not the
  `List[List[Float64]]` of covariates `causal_inference.propensity` and the bare `propensity`
  module's `propensity_scores` take) and computes `sigmoid((x - mean) / std)`, then clamps to
  `[0.01, 0.99]` **unconditionally**. `causal_inference.propensity`'s equivalent step treats a
  propensity of exactly 0 or 1 as a refusal (`propensity_at_zero_or_one`, no estimate) precisely
  because clamping it "converts an impossible unit into a hundred units of influence" — this
  module makes that exact trade every time, silently, because refusing was never part of its
  design.
* **`ipw_estimate`** clamps the same way inside its own weighting loop and always returns a
  number — there is no common-support check, no effective-sample-size diagnostic, and no
  Horvitz-Thompson-versus-Hájek distinction; it is the single unnormalized Horvitz-Thompson-style
  sum divided by `n`.
* **`stratified_ate`** weights each stratum's within-stratum ATE by `stratum_size / n` and simply
  contributes nothing from a stratum missing either arm — it never reports how much of the sample
  that dropped weight represents. `causal_inference.estimators.strata_ate` computes the same
  overall idea but returns `is_full_sample` and `covered_fraction` alongside the number precisely
  so that gap is visible; here it is not.
* **`needed_sample_size_ate`** solves for the same z-quantiles `ab_testing`'s `_norm_ppf` computes
  with a continuous rational approximation, but does it with a **hardcoded three-band lookup**
  (`alpha <= 0.01 -> 2.576`, `<= 0.05 -> 1.96`, else `1.645`; a four-band table for `power`) —
  an `alpha` of `0.02` is treated identically to `0.05`. Two modules in the same codebase solve
  the identical numerical problem at two different precisions, and neither calls the other.
* **`diff_in_diff`**, **`regression_discontinuity`**, and **`iv_estimate`** have no direct
  counterpart on the `causal_inference` page except `panel.did_panel`, which additionally reports
  a pre-treatment trend check this module's `diff_in_diff` does not attempt — it is the plain
  four-group arithmetic, `(mean(post_t) - mean(pre_t)) - (mean(post_c) - mean(pre_c))`, nothing
  else.

```python
treated, control = [10.0, 12.0, 11.0], [5.0, 6.0, 7.0]
runtime.execute("causal", "ate", [treated, control])["result"]           # 5.0

z = [0.0, 0.0, 1.0, 1.0, 0.0, 1.0]
x = [1.0, 1.0, 3.0, 3.0, 1.0, 3.0]
y = [2.0, 2.0, 6.0, 6.0, 2.0, 6.0]
runtime.execute("causal", "iv_estimate", [z, x, y])["result"]            # 2.0
# cov(z,y)/cov(z,x): z perfectly predicts x, and y = 2*x exactly
```

## `decision_analysis`: expected value, expected utility, and five textbook criteria

Every criterion below runs on the same 2-alternative, 2-state payoff matrix, taken directly from
the hand-verified test suite (`tests/mojo/test_wave24.mojo`):

```python
payoffs = [[100.0, 20.0], [50.0, 80.0]]   # alt 0, alt 1 across state 0, state 1
probs = [0.5, 0.5]

runtime.execute("decision_analysis", "decision_matrix_best", [payoffs, probs])["result"]
# 1 -- EV(alt 0) = 60, EV(alt 1) = 65

runtime.execute("decision_analysis", "maximin", [payoffs])["result"]        # 1 -- min(20,50) picks 50
runtime.execute("decision_analysis", "maximax", [payoffs])["result"]        # 0 -- max(100,80) picks 100
runtime.execute("decision_analysis", "minimax_regret", [payoffs])["result"] # 1 -- worst regret 50 < 60
runtime.execute("decision_analysis", "value_of_perfect_info", [payoffs, probs])["result"]
# 25.0 -- EV with perfect info (0.5*100 + 0.5*80 = 90) minus the best EV without it (65)
```

`hurwicz_criterion(payoffs, 1.0)` equals `maximax(payoffs)` and `hurwicz_criterion(payoffs, 0.0)`
equals `maximin(payoffs)` exactly, by construction — `alpha * max + (1 - alpha) * min` collapses
to one term or the other at the endpoints, and the test suite checks the equality rather than
re-deriving the numbers. `sensitivity_range(payoffs, 0, 50)` sweeps state 0's probability from `0`
to `1` over 50 steps, redistributing the rest of the mass equally across the remaining states —
at `p=0` (state 1 decides everything) the best alternative is `1` (`80 > 20`); at `p=1` it flips to
`0` (`100 > 50`).

{% hint style="danger" %}
**`expected_utility`'s CRRA branch silently returns the wrong sign for realistic risk-aversion and
outcome values.** For `risk_aversion != 1.0` the utility function is `x^(1-gamma) / (1-gamma)`,
computed as `exp((1-gamma) * ln(x))` — and this module implements `exp` itself, as a fixed
30-term Taylor series (`_exp_approx`), rather than importing `std.math.exp` the way `causal.mojo`
and `ab_testing.mojo` do. A Taylor series for `e^x` loses precision from cancellation once `x` is
meaningfully negative, and for this implementation the breakdown is not a rounding-error footnote:

| `(1-gamma) * ln(x)` | `_exp_approx` result | true `e^x` | error |
| --- | --- | --- | --- |
| -7.0 | 0.00091181... | 0.00091188... | ~0.008% |
| -9.0 | **-0.0000002456** | 0.00012341 | wrong sign |
| -9.21 | **-0.0001457** | 0.00010003 | wrong sign, ~1.5x magnitude |
| -20.0 | **-2,448,299** | 0.00000000206 | wrong sign, ~15 orders of magnitude |

Concretely: `expected_utility([10000.0], [1.0], 2.0)` — a risk-aversion coefficient of `2`, a
thoroughly ordinary value in the CRRA literature, and an outcome of ten thousand, an equally
ordinary payoff scale — returns `+0.000146`, when the correct CRRA utility `x^-1 / -1 = -1/x` is
`-0.0001`. At an outcome of `100000.0` with the same `gamma=2.0` it returns `+0.1878` against a
true value of `-0.00001`: off by four orders of magnitude and flipped in sign, with no error, no
status field, and no non-finite marker — `is_finite` alone (all the auto-generated test in
`test_decision_analysis.mojo` checks) would call this a passing result, because a wrong-sign
finite number is still finite. The `gamma == 1.0` branch is unaffected — it takes a direct `log`
path and never calls `_exp_approx`. The failure is specific to `gamma > 1` (a negative exponent)
combined with an outcome large enough that `(1 - gamma) * ln(outcome)` passes roughly `-8`; for
`gamma = 2.0` that threshold is an outcome of about `2,981` — well inside the range of real
dollar-valued payoffs. Until this is fixed, do not use `expected_utility` with `risk_aversion`
above `1.0` unless every outcome is small enough that `(1 - risk_aversion) * ln(outcome)` stays
above roughly `-7`.
{% endhint %}

## `decision_ml_fusion`: wiring an ML model's output into a decision loop

This module's own docstring frames it as "Decision + ML fusion layer: ML -> simulation ->
optimization pipeline" — its ten functions are the connective tissue between a model's raw output
and the objective a downstream optimizer or RL loop consumes, not (despite a plausible-sounding
name) a way of combining a human decision-maker's judgment with a model's. `ml_to_simulation_weight`
sharpens or softens a predicted probability by a temperature (`p^(1/T)`); `simulation_to_objective`
turns a Monte-Carlo mean and standard deviation into a single mean-variance objective;
`expected_value_under_model` blends a model-driven weight and a prior weight by the model's own
stated confidence; and `model_confidence_gate` is a hard cutover — the model's output passes
through unchanged above a confidence threshold, or a fixed fallback value is substituted below it,
with nothing in between.

```python
runtime.execute("decision_ml_fusion", "ml_to_simulation_weight", [0.8, 0.5])["result"]
# 0.64 -- 0.8 ** (1/0.5): a sharpening temperature pushes a confident prediction higher

runtime.execute("decision_ml_fusion", "expected_value_under_model", [100.0, 0.9, 0.5, 0.8])["result"]
# 82.0 -- (0.8*0.9 + 0.2*0.5) * 100: 80% weight on the model's own view, 20% on the prior

runtime.execute("decision_ml_fusion", "adaptive_exploration_rate", [5.0, 10.0, 100.0, 1.4142135623730951])["result"]
# 5.959705182437617
```

That last call is `ab_testing.ucb1_select`'s internal UCB1 bonus term, made callable on its own
for a single action instead of an argmax over parallel lists — but not identically. `ucb1_select`
hardcodes the `sqrt(2 * ln(N) / n)` exploration bonus; `adaptive_exploration_rate` takes the
constant out as its own `ucb_c` argument (`q_value + ucb_c * sqrt(log(total_visits) / visit_count)`)
rather than baking in `sqrt(2)`. Passing `ucb_c = sqrt(2) = 1.4142135623730951` reproduces
`ucb1_select`'s bonus exactly — `1.4142135623730951 * sqrt(log(100)/10) = 0.9597051824376163`,
and `5.0 + 0.9597051824376163` is the `5.959705182437617` above — but any other `ucb_c` is a
genuinely different exploration schedule, not a variant of the same one.

## `hypothesis`: five tests that stop one step short of a p-value

```python
runtime.execute("hypothesis", "rank_data", [[3.0, 1.0, 2.0]])["result"]
# [3.0, 1.0, 2.0] -- already sorted-by-rank order, so ranks equal values here

runtime.execute("hypothesis", "mann_whitney_u", [[1.0, 2.0, 3.0, 4.0, 5.0], [6.0, 7.0, 8.0, 9.0, 10.0]])["result"]
# [0.0, -2.6111648393354674] -- U=0: every rank in the first group is below every rank in the second

runtime.execute("hypothesis", "fisher_exact_2x2", [1, 9, 11, 3])["result"]
# 0.001346076187912241
```

Unlike `ab_testing.z_test_proportions`, which computes an actual p-value from its own
`_norm_cdf`, `hypothesis.mojo` has no normal-CDF helper anywhere in it — `mann_whitney_u` and
`wilcoxon_signed_rank` return `[statistic, z]` and stop there; `kruskal_wallis` returns
`[H, degrees_of_freedom]`; `sign_test` returns raw `[n_positive, n_negative, n_ties]` counts.
Converting any of these into a p-value — feeding `z` through a normal CDF, `H` through a
chi-squared CDF, or the sign counts through a binomial tail — is left entirely to the caller.
`kruskal_wallis` on three clearly-separated groups of three (`[1,2,3]`, `[4,5,6]`, `[7,8,9]`, no
ties) gives `H = 7.2` against `df = 2`: rank sums `6, 15, 24` over `N = 9` produce
`(12/90) * (36/3 + 225/3 + 576/3) - 30 = 37.2 - 30 = 7.2`, worked independently from the source
formula since the wave test for this case only asserts `H > 0`.

{% hint style="warning" %}
**`fisher_exact_2x2` returns the probability of the observed table, not the standard Fisher
exact test p-value** — even though the module docstring lists it as replacing
`scipy.stats.fisher_exact`. For the table `(a=1, b=9, c=11, d=3)`:

* `fisher_exact_2x2(1, 9, 11, 3)` returns **0.0013461** — the single hypergeometric point
  probability `P(a=1 | fixed margins)`.
* The one-sided p-value (summing every table with `a <= 1` under the same margins) is
  **0.0013797** — close, because this table sits at the extreme tail, but not the same number.
* `scipy.stats.fisher_exact([[1, 9], [11, 3]])` reports a two-sided p-value of **0.0027595** —
  almost exactly double the point probability this kernel returns.

For a table far in the tail the point probability happens to be numerically close to a real
p-value, which is exactly what makes this easy to miss: the number "looks like" a small p-value
and the wave test only checks `fe < 0.05`. It is not interchangeable with scipy's return value in
general, and nothing in the return type distinguishes "the point probability of this table" from
"the tail probability of this table or worse."
{% endhint %}

## Verification

`test_ab_testing.mojo`, `test_causal.mojo`, `test_decision_ml_fusion.mojo`, and
`test_hypothesis.mojo` in `mojo/tests/libs/` are auto-generated coverage smoke tests — each calls
every function once with fixed literal arguments and checks only that the result is finite (or,
for `Int`/`Bool` returns, only that the call completes). `test_decision_analysis.mojo` in that
same directory covers exactly two of the module's ten functions this way. The numeric behavior
pinned by a real test suite lives instead in four files under `tests/mojo/`: `test_wave43.mojo`
(`ab_testing`, 27 assertions), `test_wave46.mojo` (`causal`, 20 assertions), `test_wave24.mojo`
(`decision_analysis`, 19 assertions on the payoff matrix used above), and `test_wave19.mojo`
(`hypothesis`, 18 assertions). `decision_ml_fusion` has no hand-verified suite anywhere in the
tree — every worked number for it above was computed independently from
`mojo/engine/decision_ml_fusion.mojo`'s formulas, and the `adaptive_exploration_rate` example was
additionally cross-checked against `ab_testing.ucb1_select`'s own exploration-bonus arithmetic.

**Next:** [Causal inference](causal-inference.md) for the identification-first estimators this
module's `causal` sits beside, [Statistical inference](statistical-inference.md) for the
parametric tests and resampling that `hypothesis` does not attempt, or the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
