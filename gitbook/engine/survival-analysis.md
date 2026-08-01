---
icon: heart-pulse
description: Time-to-event estimation that respects censoring — Kaplan-Meier with confidence bands, Nelson-Aalen, a kernel-smoothed hazard rate, Cox regression with Efron ties
---

# Survival analysis

Six kernel families for the question "how long until it fails, and what does the data actually
support". They run as compiled kernels inside the runtime that ships with the SDK — nothing to
install separately and nothing to start.

Survival data is not ordinary data. Some subjects have not failed yet, and dropping them biases
every estimate toward short lives while treating them as failures biases it the same way twice.
Right-censoring is therefore in the signature of every call, and it is validated rather than
assumed:

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

times = [2.0, 3.0, 4.0, 4.0, 5.0, 6.0, 8.0, 9.0]
event = [1, 0, 1, 1, 0, 1, 0, 1]          # 1 = observed failure, 0 = still under observation

fit = runtime.execute("survival_analysis.km", "km_fit", [times, event, 0.95])["result"]

fit["time"]            # [2.0, 4.0, 6.0, 9.0]      — one row per distinct failure time
fit["at_risk"]         # [8, 6, 3, 1]              — counts the censored rows still at risk
fit["survival"]        # [0.875, 0.5833333, 0.3888889, 0.0]
fit["std_error"]       # [0.1169268, 0.1855610, 0.2012691, 0.0]
fit["has_std_error"]   # [True, True, True, False]  <- the last one does not exist
fit["median_time"]     # 6.0
```

Read the fourth entry of `has_std_error`. At the last failure time the entire remaining risk set
fails at once, and the Greenwood variance of the estimate has a zero denominator there. The value
slot holds `0.0` because a response has to be representable, and the flag says that `0.0` is a
placeholder rather than a measurement of perfect certainty. Every surface in this package works
that way: a quantity that could not be computed is reported **absent**, distinctly from a
computed zero.

## The modules

| Module | What it does |
| --- | --- |
| `survival_analysis.km` | Kaplan-Meier product-limit estimate with Greenwood standard errors and a log-log confidence band that cannot leave `[0, 1]`, restricted mean survival time, step-function lookup, and the median under **both** tie conventions in circulation so you know which one you are holding |
| `survival_analysis.hazard` | Nelson-Aalen cumulative hazard with the Aalen variance and a band on `log H`, plus a kernel-smoothed hazard **rate** with a per-point flag for the boundary region where the estimate is biased toward zero |
| `survival_analysis.cox` | Cox proportional-hazards regression by Newton-Raphson on the **Efron** partial likelihood, with standard errors from the observed information, a likelihood-ratio statistic, the baseline cumulative hazard, and per-subject linear predictors and relative risks |
| `survival_analysis.competing` | Aalen-Johansen cumulative incidence for many causes of failure, the cause-specific cumulative hazards with their standard errors, and the partition identity checked rather than assumed |
| `survival_analysis.parametric` | Weibull and lognormal maximum likelihood **with censoring**, each returning the identities that define its own solution so the fit can be checked without re-deriving it, plus a goodness-of-fit distance against the nonparametric curve |
| `survival_analysis.base` | the shared censoring contract: one status vocabulary, the validation every entry point passes through, canonical tie ordering, the risk table every estimator is built from, and non-wrapping work budgets |

## Competing risks is a different question, and the wrong answer is plausible

With more than one cause of failure, running a survival curve for cause 1 while treating cause 2
as censoring and reporting `1 - S(t)` does not answer "what fraction fail from cause 1 by
time t". It answers it in a world where cause 2 does not exist, and it is biased upward — often
badly:

```python
times  = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
cause  = [1, 2, 1, 0, 2, 1]              # 0 = censored, k = failed from cause k

cif = runtime.execute("survival_analysis.competing", "cif_fit",
                      [times, cause, 2])["result"]

cif["incidence"][:5]        # cause 1: [0.1666667, 0.1666667, 0.3333333, 0.3333333, 0.5833333]
cif["incidence"][5:]        # cause 2: [0.0, 0.1666667, 0.1666667, 0.4166667, 0.4166667]
cif["partition_holds"]      # True  — S(t) + sum_k CIF_k(t) == 1 at every failure time
cif["partition_max_error"]  # 0.0
```

The correct cause-1 incidence at `t = 6` is `7/12 = 0.583`. The `1 - S(t)` shortcut returns
`1.0` on this sample — a 71% overstatement. That is why `cause` is an integer code whose values
are validated: a status column recorded as 1/2/3 and passed with two declared causes is refused,
not quietly folded into the censored bucket.

## A fit is refused when there is nothing to fit

Parametric survival models are usually presented as always available. They are not. If every
observed failure shares one recorded time — which is what inspection-interval logging
produces — and no censored observation lies above it, the lognormal likelihood has **no
maximum**: it grows without bound as the scale shrinks. An estimator that iterates anyway
returns whatever its stopping rule reached, and the answer moves with the tolerance:

```python
runtime.execute("survival_analysis.parametric", "lognormal_mle",
                [[3.0, 3.0, 1.0], [1, 1, 0], 200, 1e-13])["result"]["status"]
# 931 — "likelihood_unbounded_no_mle_exists", at every tolerance and iteration limit
```

The same sample with one censored observation moved above the tied failures has a maximum, and
is fitted. Weibull refuses it too, through its own bracket test, so a model comparison across
the two families cannot be won by whichever one failed to notice.

{% hint style="info" %}
**What the fit returns so you can check it.** `weibull_mle` reports
`shape_equation_residual` and `scale_identity_residual` — the two equations that define the
solution, evaluated at the returned parameters, both zero at a correct fit.
`lognormal_mle` reports `loglik_monotone`, which is a theorem about its algorithm rather than a
tuning knob: a violation is a refusal, not a flag on a returned answer. Both report a
Kolmogorov-Smirnov-style distance against the nonparametric Kaplan-Meier curve, so the parametric
assumption is measurable rather than implied.
{% endhint %}

## Ties, and why the Cox default matters

When several subjects fail at the same recorded time, the Cox partial likelihood is ambiguous and
the two standard treatments give different coefficients. The Efron approximation is used, and on
an eight-row sample with two tied failure times the two conventions differ by 0.033 in the first
coefficient — larger than the standard error's third digit, and enough to move a borderline
conclusion. The tie rule is stated rather than left to be inferred:

```python
x_flat = [0.0, 1.0, 1.0, 0.0, 2.0, 1.0, 0.0, 3.0,
          1.0, 2.0, 3.0, 0.0, 2.0, 2.0, 0.0, 0.0]   # 8 rows x 2 covariates, row-major

cox = runtime.execute("survival_analysis.cox", "cox_fit",
                      [x_flat, 8, 2,
                       [1.0, 1.0, 2.0, 3.0, 3.0, 4.0, 5.0, 6.0],
                       [1, 1, 0, 1, 1, 1, 0, 1], 400, 1e-12])["result"]

cox["beta"]           # [-0.2413840, 0.0445809]
cox["std_error"]      # [ 0.4087651, 0.3983392]
cox["lr_statistic"]   # 2 * (loglik - loglik_null)
cox["max_abs_score"]  # ~1e-16 — the gradient at the returned point, published
```

A Cox fit is refused rather than reported when the data carry no information about a
coefficient: a covariate that never varies, a covariate that separates the failures perfectly
(the estimate is at infinity, not at a large finite value), a likelihood whose curvature has
collapsed, and an information matrix that cannot be inverted. In particular a design with as
many covariates as rows is refused — the alternative was publishing a coefficient of exactly
zero, which reads as "no effect" when it means "no answer".

## What is deliberately not here

{% hint style="warning" %}
**No confidence band for the cumulative incidence.** Its variance has three interacting terms
and no closed form that could be checked against an independent reference here, and a plausible
interval that is wrong is worse than a stated absence. What is provided with uncertainty is the
cause-specific cumulative hazard, whose estimator and variance are both a sum of independent
increments.

**No extrapolation past the last observation.** A survival curve and a cumulative incidence are
step functions defined on the observed follow-up. Beyond the largest observed time the last
level is a continuation, not an estimate, so a lookup there is reported absent and a restricted
mean is refused. This matches what established statistical software reports for the same query.

**No boundary correction on the smoothed hazard.** Within one bandwidth of the first or last
failure time the kernel window extends over a region where no data can exist, so the rate is
biased toward zero. Each point carries a `boundary` flag saying so; applying a boundary kernel
would be a second estimator with its own trade-off, and it would be silent.
{% endhint %}

## Refusals

Every entry point returns a typed status rather than raising, and every status names one defect:

| Status | Meaning |
| --- | --- |
| `empty_observations` | no observations were supplied |
| `censoring_length_mismatch` | the censoring column is not exactly as long as the time column — a shorter one would read past the end of the data and a longer one would silently describe a different dataset |
| `non_finite_time`, `negative_time`, `nonpositive_time` | a time that no estimator can use; the last is specific to the two log-domain parametric fits, which is why a time of exactly zero is accepted by the curve estimators and refused by them |
| `event_code_not_zero_or_one` | a censoring indicator outside `{0, 1}`, which is how a 1/2-coded status column is caught instead of being read as a failure |
| `cause_code_out_of_range`, `too_many_causes`, `selected_cause_absent` | a competing-risks cause code that is not one of the declared causes |
| `confidence_level_out_of_range` | a confidence level outside `[0.5, 0.999999]`, refused rather than turned into a band of meaningless width |
| `truncation_time_out_of_range` | a restricted-mean horizon past the last observation, or not positive |
| `covariate_shape_mismatch`, `too_many_covariates`, `covariate_is_constant` | a Cox design that does not describe the sample, or a covariate carrying no information |
| `information_matrix_not_positive_definite`, `likelihood_flat_or_separating` | a Cox likelihood with no finite maximum in some direction |
| `not_converged`, `iteration_limit_out_of_range`, `tolerance_out_of_range` | an iterative fit that did not reach a solution, or was asked for one with impossible settings |
| `likelihood_unbounded_no_mle_exists` | the sample has no maximum-likelihood estimate at all, at any tolerance |
| `em_log_likelihood_decreased` | an internal invariant of the lognormal fit was violated, so no estimate is returned |
| `work_budget_exceeded` | the request is structurally valid but would take longer than a single synchronous call should; the cost is counted before any of it is performed, not estimated |
| `survival_curve_not_monotone`, `cumulative_incidence_partition_violated` | an algebraic law the estimate must satisfy did not hold, checked on every call |

## See also

* [Evaluation Calibration](evaluation-calibration.md) — scoring and calibrating the models a survival fit feeds
* [Streaming Sketches](streaming-sketches.md) — summarising event streams before they reach a survival model
* [Runtime Library Catalog](runtime-library-catalog.md) — every module and function
