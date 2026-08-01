---
icon: flask
description: p-values that carry the verdict on their own assumptions, sample sizes verified by re-evaluating power, reproducible resampling, and a critical value that is absent rather than clamped.
---

# Statistical inference

Seven kernel families for the question after the measurement: is this difference real, how many
observations would it take to see it, what does the family of twenty tests do to the answer, and
what happens when an assumption the test rests on does not hold. All run as compiled kernels
inside the runtime that ships with the SDK — there is nothing to start and nothing to install
separately.

The organising idea is that **a number is not the whole answer.** A p-value from a test whose
assumptions were not met is not a p-value; a sample size that was never checked is algebra, not
a design; a confidence interval that changes between runs cannot be used in a decision that has
to be explained. Each of those is a field in the result here, not a caveat in a docstring.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# How many observations per group for a standardized effect of 0.5,
# two-sided at alpha = 0.05, with 80% power?
r = runtime.execute("inference.power", "sample_size_two_means_flat",
                    [0.5, 0.05, 0.80, False])["result"]

r["n_per_group"]           # 63
r["closed_form_n"]         # 63 — what the inversion produced
r["search_steps"]          # 0 — the verification did not have to move it
r["achieved_power"]        # 0.8011822526702241  measured AT n
r["power_at_n_minus_1"]    # 0.7948856284208302  measured at n - 1
r["minimal"]               # True — both halves checked, not asserted
r["method"]                # "normal_approximation_two_sided"
```

## The modules

| Module | What it does |
| --- | --- |
| `inference.core` | the package's one vocabulary: statuses, the finiteness test, the rounding-tolerance builder, non-wrapping work budgets, the t and F tails, the t quantile, and a weighted least-squares solve with a per-row backward-error check |
| `inference.power` | power and per-group sample size for a two-sample mean comparison, normal-approximation and central-t lanes, with every returned size verified |
| `inference.assume` | the checkable assumptions — variance homogeneity, minimum expected cell counts, residual normality — returned as verdicts beside the test they qualify |
| `inference.multiplicity` | Bonferroni, Holm and Benjamini-Hochberg, each carrying the method name and the family size, because an adjusted p-value means nothing without both |
| `inference.resample` | bootstrap confidence intervals and permutation tests that reproduce bit for bit from a seed and a stream |
| `inference.robust` | Huber regression by iteratively reweighted least squares, with a MAD scale and per-observation weights |
| `inference.glm` | logistic and Poisson fits with Wald standard errors, and separable data reported as such rather than fitted |

## A sample size is verified, not asserted

The closed form `n = 2 ((z_alpha + z_beta) / d)^2` inverts the normal approximation. A closed
form that is merely printed is a claim, so every size returned here is checked by re-evaluating
power through the **same** power function you would call yourself, at `n` and at `n - 1`:

```python
runtime.execute("inference.power", "power_two_means_flat", [0.5, 63, 0.05, False])["result"]
# power 0.8011822526702241 — identical to achieved_power above

runtime.execute("inference.power", "power_two_means_flat", [0.5, 62, 0.05, False])["result"]
# power 0.7948856284208302 — identical to power_at_n_minus_1
```

`minimal` is True only when the first reaches your target and the second does not. That makes
minimality a measured property of the number you were given rather than a property of the
algebra, and it is why the two lanes can disagree honestly:

```python
r = runtime.execute("inference.power", "sample_size_two_means_t_flat",
                    [0.5, 0.05, 0.80, False])["result"]

r["n_per_group"]         # 64 — the textbook t-test answer
r["closed_form_n"]       # 63 — the normal inversion is only a starting point here
r["search_steps"]        # 1 — how far the verification had to move it
r["achieved_power"]      # 0.8013829274055866
r["method"]              # "central_t_shift_approximation_two_sided"
```

The one-per-group difference is exactly the variance-estimation penalty the normal
approximation omits, and `method` is part of the answer rather than decoration: which lane
computed a power determines whether `n` should be 63 or 64.

{% hint style="warning" %}
**A target that cannot be reached is refused, not answered with an underpowered `n`.** A
sample-size calculator that returns a plausible number is the worst possible failure here,
because the number goes straight into a study design and the power is missing only once the
data has been collected.

* An effect of exactly zero: `no_sample_size_detects_a_zero_effect`, with no `n`. Power equals
  alpha for every `n`, so there is no answer — and a large round number would be budgeted
  against.
* An effect so small the required size leaves the supported range — measured at
  `effect_size = 1e-7`: `dimension_or_work_exceeds_inference_ceiling`, with no `n`.
* `alpha` or `target_power` outside the open interval `(0, 1)` — including exactly `1.0`:
  `alpha_or_confidence_outside_open_unit_interval`. Nothing is clamped, because at `alpha = 0`
  nothing is ever rejected and at `alpha = 1` everything is, and neither is a decision rule.

When the bounded verification search cannot reach your target from the closed form, the report
comes back `iteration_cap_reached_without_convergence` with the diagnostic fields still
populated — the `n` it got to, the power it achieved and the steps it spent — so you can see
how far it went instead of receiving a blessed number.
{% endhint %}

## A critical value outside the solver's range is absent, not clamped

```python
runtime.execute("inference.core", "inference_t_quantile", [0.975, 10.0])["result"]
# 2.2281388548022187

runtime.execute("inference.core", "inference_t_sf_two_sided", [2.228, 10.0])["result"]
# 0.05001177205584047 — the tail that critical value cuts off
```

The quantile is found by bisection on the t CDF over a fixed bracket, and bisection converges
to *something* whether or not the root is inside that bracket. So the bracket is verified to
actually bracket the answer, and when it does not the result is **absent** — a non-finite
marker that `inference_finite` tests for. What you never receive is the bracket edge dressed
as a critical value:

```python
runtime.execute("inference.core", "inference_t_quantile", [1e-6, 1.0])   # absent
runtime.execute("inference.core", "inference_t_quantile", [0.0, 10.0])   # absent
runtime.execute("inference.core", "inference_t_quantile", [1.0, 10.0])   # absent
```

The 0 and 1 quantiles of an unbounded distribution are minus and plus infinity, which are not
answers. Returning a large finite number in their place is worse than refusing: a critical
value is used as a test threshold, so the error surfaces as a wrong accept or reject rather
than as a visibly wrong number.

`t_cdf_agreement` exists for the same reason in reverse — it reports what two independent
computations of the same t CDF say about one `(t, df)` pair, including whether the value is a
probability at all, so the comparison is a number you can measure rather than a claim.

## Correcting a family changes what a rejection means

```python
p_values = [0.001, 0.008, 0.02, 0.04, 0.3]

bonf = runtime.execute("inference.multiplicity", "bonferroni_flat",
                       [p_values, 5, 0.05])["result"]
holm = runtime.execute("inference.multiplicity", "holm_flat",
                       [p_values, 5, 0.05])["result"]
bh = runtime.execute("inference.multiplicity", "benjamini_hochberg_flat",
                     [p_values, 5, 0.05])["result"]

bonf["adjusted"]     # [0.005, 0.04, 0.1, 0.2, 1.0]
bonf["n_rejected"]   # 2
holm["adjusted"]     # [0.005, 0.032, 0.06, 0.08, 0.3]
holm["n_rejected"]   # 2
bh["adjusted"]       # [0.005, 0.02, 0.03333..., 0.05, 0.3]
bh["n_rejected"]     # 4
bh["method"]         # "benjamini_hochberg_step_up"
bh["n_tests"]        # 5
```

Bonferroni and Holm control the probability of **any** false rejection in the family;
Benjamini-Hochberg controls the expected **proportion** of false rejections among those
rejected. Those are different guarantees, and an adjusted value of 0.04 means something
different under each — which is why `method` and `n_tests` travel with every result, and why a
bare list of adjusted numbers would be the wrong return type. Adjusted values are also capped
at 1.0 and kept monotone, so two equal raw p-values cannot receive two different adjusted ones.

A value offered as a p-value that is not in `[0, 1]` is refused
(`a_value_offered_as_a_p_value_is_not_a_probability`) rather than adjusted, and
`correction_agreement_flat` reports where the three procedures disagree on the same family in
one call.

## A p-value arrives with the verdict on its assumptions

```python
# two groups of three, laid out as one flat list
r = runtime.execute("inference.assume", "t_test_checked_flat",
                    [[1.0, 2.0, 3.0, 7.0, 8.0, 9.0], 3, 3, 0.05])["result"]

r["statistic"]                   # -7.3484692283495345
r["p_value"]                     # 0.0018262606685797622
r["statistic_reproduced"]        # True — recomputed independently and it agreed
r["equal_variance_p"]            # 1.0
r["equal_variance_satisfied"]    # True
r["normality_checked"]           # False — three points per group is too few to judge
r["assumptions_satisfied"]       # False — because one of them was never checked
r["frozen_p_value_usable"]       # False
```

`assumptions_satisfied` is False here even though the variance check passed, and that is the
point: an assumption that could not be checked must not read as an assumption that was met.
Those are different states of knowledge and only one of them is safe to act on.

The individual verdicts are callable on their own — `variance_homogeneity_flat` (Levene on
deviations from group medians, the variant that stays valid on skewed data),
`expected_counts_flat` (the condition under which a chi-squared statistic is chi-squared
distributed at all) and `residual_normality_flat`, which reports two normality tests
separately **and** whether they agree, because two tests that disagree is information a single
reject flag cannot carry. A test whose own p-value comes back as a non-probability is reported
as `a_value_offered_as_a_p_value_is_not_a_probability`, never converted into a verdict.

## A fit that does not exist returns no coefficients

Perfectly separable data has no logistic maximum-likelihood estimate — the weights grow without
bound — so it is reported rather than fitted at whatever the iteration cap happened to reach:

```python
x = [-3.0, -2.0, -1.0, 1.0, 2.0, 3.0]
y = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]

r = runtime.execute("inference.glm", "glm_logistic_fit_flat",
                    [x, y, 6, 1, 0.0, 200, 1e-10])["result"]

r["status"]                  # 329 — "separable_data_so_the_mle_does_not_exist"
r["coefficients"]            # []
r["separation_witnessed"]    # True
r["separation_margin"]       # 51.15477110371069 — how far apart the arms are

# the same data with an L2 penalty has a finite answer, and converges
r = runtime.execute("inference.glm", "glm_logistic_fit_flat",
                    [x, y, 6, 1, 1.0, 200, 1e-10])["result"]
r["converged"]        # True
r["n_iter"]           # 6
r["coefficients"]     # [1.1044042835819403]
r["wald_p"]           # [0.06970975115452127]
```

The robust regression makes the same distinction. Its scale is the median absolute deviation of
the residuals, and a MAD of zero is not a scale — when more than half the residuals sit exactly
at their median, every Huber cutoff collapses and the fit would be decided by the tied half
alone:

```python
runtime.execute("inference.robust", "robust_scale_mad",
                [[0.0, 0.0, 0.0, 0.0, 5.0, 9.0], 6])["result"]      # 0.0
```

An iteratively reweighted fit that reaches its cap without converging returns
`iteration_cap_reached_without_convergence` with an **empty** coefficient list and the
iteration count, not the iterate it happened to be sitting on. There are deliberately no
standard errors on that surface: a Huber estimator's variance needs a sandwich estimator, and a
standard error computed as though the weights were fixed would be a confident understatement.

## Resampling reproduces

```python
sample = [float(i % 7) + 0.5 * (i % 3) for i in range(50)]
STAT_MEAN = 0

a = runtime.execute("inference.resample", "bootstrap_ci_flat",
                    [sample, 50, STAT_MEAN, 2000, 0.95, 12345, 0])["result"]
b = runtime.execute("inference.resample", "bootstrap_ci_flat",
                    [sample, 50, STAT_MEAN, 2000, 0.95, 12345, 0])["result"]
c = runtime.execute("inference.resample", "bootstrap_ci_flat",
                    [sample, 50, STAT_MEAN, 2000, 0.95, 12345, 1])["result"]

a["lo"], a["hi"]            # 2.84, 4.02
b["lo"] == a["lo"]          # True — the same seed and stream, bit for bit
c["lo"], c["hi"]            # 2.87, 4.01 — a second stream, same seed
a["lo_rank"], a["hi_rank"]  # 50, 1950 — which order statistics the endpoints are
a["point_estimate"]         # 3.43
```

Every draw is a pure function of `(seed, stream, draw index)`, so replicate `r` is the same
replicate no matter how many were computed first and no matter what else in your process drew a
number. A second `stream` gives an independent replication without changing the seed you
published, and the endpoint ranks come back so you can see how thin the tail supporting each
endpoint is — a percentile interval from too few resamples is a rank, not a bound.
`permutation_test_flat` reports the same way, including the floor its p-value cannot go below
for the number of permutations you asked for.

## Every refusal names itself

One status vocabulary covers the package and `inference_status_name` turns any code into a
name: `too_few_observations_for_this_estimate`,
`alpha_or_confidence_outside_open_unit_interval`,
`resample_count_not_positive_or_above_ceiling`, `iteration_cap_reached_without_convergence`,
`separable_data_so_the_mle_does_not_exist`, `information_matrix_not_positive_definite`,
`response_outside_the_range_this_family_admits`,
`a_value_offered_as_a_p_value_is_not_a_probability`, `no_sample_size_detects_a_zero_effect`,
`the_statistic_has_no_value_for_this_input`,
`dimension_or_work_exceeds_inference_ceiling`.

Each driver returns a status; the scalar tail and quantile helpers, which have no room for one,
return an absence marker instead of a plausible number. Work is charged against every factor of
its own cost — a bootstrap by resample count and sample size, an iterative fit by iterations,
observations and parameters — so an oversized request is refused up front rather than accepted
and left running.

## See also

* [Forecasting and backtesting](forecasting.md) — out-of-sample error measurement and prediction bands
* [Causal inference](causal-inference.md) — effects that refuse to exist unless they are identified
* [Statistical model comparison](ml-model-comparison.md) — comparing fitted models
* [Probability calibration](ml-calibration.md) — turning scores into calibrated probabilities
* [Trainable linear models](ml-linear-models.md) — the fits these drivers call
* [Runtime library catalog](runtime-library-catalog.md) — every module and function
