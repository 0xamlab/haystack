---
icon: ruler-combined
description: Frozen hypothesis-test, survival-curve, operational-metrics, psychometric, and interval-arithmetic primitives that other kernel families call rather than reimplement.
---

# Evaluation, survival, and psychometric kernels

Five modules that share one trait rather than one domain: each is a small, self-contained
arithmetic library that a richer, validated module elsewhere in this codebase calls into rather
than duplicates. `stat_tests` is the hypothesis-test engine `data_quality.leakage` calls for its
correlation checks. `survival` is the unguarded Kaplan-Meier/Nelson-Aalen arithmetic that the
`survival_analysis` family wraps with censoring validation and confidence bands. `metrics_agg`,
`psychometrics`, and `interval` have no such wrapper — they are the whole surface for counters and
latency histograms, classical-test-theory and item-response-theory scoring, and closed-interval
arithmetic, respectively. None of the five import Python; all run as compiled kernels inside the
runtime that ships with the SDK.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Welch's t-test, unequal-variance two-sample -- verified against scipy.stats.ttest_ind
g1 = [1.0, 2.0, 3.0]
g2 = [4.0, 5.0, 6.0]
t = runtime.execute("stat_tests", "t_test_2sample", [g1, g2])["result"]
t["statistic"]   # -3.6742346141747673
t["p_value"]     # 0.021311641128756727
t["reject_h0"]   # True

# Kaplan-Meier on five uncensored failures at t = 1..5
times  = [1.0, 2.0, 3.0, 4.0, 5.0]
events = [True, True, True, True, True]
km = runtime.execute("survival", "kaplan_meier", [times, events])["result"]
km[3]["time"]      # 3.0
km[3]["survival"]  # 0.4  -- S(3) = 0.8 * 0.75 * 0.6667 = 0.4, three subjects still at risk
km[3]["at_risk"]   # 3
```

## The modules

| Module | What it does |
| --- | --- |
| `survival` | Kaplan-Meier, Nelson-Aalen, log-rank, kernel-smoothed hazard rate, restricted mean survival time, life tables and step-function lookup — the frozen product-limit arithmetic, with no input validation of its own |
| `stat_tests` | KS, t-test (one- and two-sample Welch), chi-squared, Anderson-Darling, and approximate Shapiro-Wilk hypothesis tests, plus Pearson and Spearman correlation with p-values and NaN/Inf-raising siblings |
| `metrics_agg` | Counters, bucketed histograms with mean/percentile, rate of change, gauge assignment, throughput, and a six-number `[min, max, mean, p50, p95, p99]` latency summary |
| `psychometrics` | Classical test theory (item difficulty and discrimination, point-biserial, KR-20, Cronbach's alpha, Spearman-Brown), score transforms (z, T, stanine), and 1PL/2PL item-response-theory probability |
| `interval` | Closed-interval `[lo, hi]` creation, the four arithmetic operations, containment, overlap, intersection, convex-hull union, and width/midpoint/radius queries |

## `survival`: the frozen curve arithmetic `survival_analysis` wraps

| Function | What it does |
| --- | --- |
| `kaplan_meier(times, events)` | Product-limit estimator `S(t) = Π(1 - d_i/n_i)`. Returns one `SurvivalPoint` per distinct **event** time, prefixed with `(0.0, 1.0, n, 0)`; censored-only times contribute no row. |
| `nelson_aalen(times, events)` | Cumulative hazard `H(t) = Σ d_i/n_i`, returned as `[[time, H], ...]` rows, prefixed with `[0.0, 0.0]`. |
| `median_survival(km_curve)` | First `time` in the curve where `survival < 0.5` (strict `<`); `-1.0` if the curve never drops below it. |
| `log_rank_statistic(times1, events1, times2, events2)` | Chi-squared statistic (1 df) comparing two groups' event times via observed-minus-expected deaths at each pooled event time. |
| `hazard_rate(times, events, bandwidth)` | Kernel-smoothed hazard rate at each distinct event time, using an Epanechnikov kernel `0.75 * (1 - u^2)` for `\|u\| <= 1`. |
| `restricted_mean(km_curve, tau)` | Area under the KM step function up to `tau`, by trapezoidal integration over constant steps. |
| `life_table(times, events, intervals)` | Per-interval `[start, n_risk, n_event, survival]` rows; the last interval runs to `+inf`. |
| `survival_at_time(km_curve, t)` | `S(t)` by step-function lookup: the survival value at the largest curve time `<= t`. |

**This is not the same page as [Survival analysis](survival-analysis.md).** That page documents
`survival_analysis.km/hazard/cox/competing/parametric/base`, a validated wrapper family whose own
docstrings are explicit that they call this module rather than reimplement it —
`survival_analysis.km`'s header states "The frozen `survival.kaplan_meier` computes the
product-limit estimate correctly... It is CALLED here, never reimplemented," and
`survival_analysis.hazard` copies `nelson_aalen`'s `H` column through unchanged before adding a
variance and a confidence band. What the wrapper family adds and this module does not have at
all: Greenwood/Aalen variance, log-log and log confidence bands, and validation of the censoring
contract. The KM worked example above uses this module's own `kaplan_meier`/`median_survival`
directly — no variance, no band, just the point estimate — which is why `median_survival` here
uses strict `< 0.5` while `survival_analysis.km`'s `median_time` uses `<= 0.5` and reports both
conventions precisely because they disagree whenever a curve lands on exactly 0.5.

**Reading the source closes off one hazard the wrapper's docstring names, and leaves another
live.** `survival_analysis.base`'s docstring describes two failure modes reachable from this
module with unvalidated input: an uncatchable out-of-bounds abort on a length-mismatched
`events`/`times` pair, and an infinite loop on a NaN time. In the current tree, every function
here that takes `times` and `events` opens with `if len(events) != len(times): return <empty>`
— `kaplan_meier` returns `List[SurvivalPoint]()` (not even the `(0, 1.0)` starting point),
`nelson_aalen`/`hazard_rate`/`life_table` return an empty list, `log_rank_statistic` returns
`0.0` — so a length mismatch through the public functions documented here no longer indexes out
of bounds; it silently returns nothing. The NaN case is still real and independently reproducible
by tracing the code: `kaplan_meier` and `nelson_aalen` both group tied times with
`while i < n and times[idx[i]] == t`, and `NaN == NaN` is `False` under IEEE-754, so if the time
at the current sort position is NaN the inner loop never advances `i`, the outer `while i < n`
loop re-enters with identical state, and the call never returns. `hazard_rate`'s own
deduplication of event times uses a bounded `for` loop instead, so it cannot hang the same way —
a NaN there just fails to deduplicate and appears once per occurrence.

## `stat_tests`: hypothesis tests, hand-verified against scipy

| Function | What it does |
| --- | --- |
| `ks_test_2sample(sample1, sample2)` | Two-sample Kolmogorov-Smirnov: `D = max\|ECDF1 - ECDF2\|`, asymptotic p-value from the Kolmogorov distribution. |
| `ks_test_normal(sample)` | One-sample KS against `N(mean(sample), std(sample))` — the sample's own moments, not an externally supplied null. |
| `t_test_1sample(sample, mu0)` | One-sample t-test, `t = (x̄ - μ₀) / (s/√n)`, `df = n - 1`. |
| `t_test_2sample(sample1, sample2)` | Welch's two-sample t-test (unequal variances), df by Welch-Satterthwaite. |
| `chi_squared_test(observed, expected)` | Goodness-of-fit `χ² = Σ(O-E)²/E`, `df = k - 1`; categories with `expected <= 0` are skipped rather than dividing by zero. |
| `anderson_darling_normal(sample)` | Anderson-Darling normality statistic, bias-corrected (`A²*`), p-value from D'Agostino & Stephens (1986) piecewise interpolation. |
| `shapiro_wilk_approx(sample)` | Approximate Shapiro-Wilk (n ≤ 5000) using normal order-statistic weights and a Royston-style log-transform for the p-value. |
| `pearson_r(x, y)` | Pearson correlation and a t-distribution p-value. **Existing-frozen**: `data_quality.leakage` depends on its exact return contract for `n < 3` and a zero denominator (`CorrResult(0.0, 1.0)`). |
| `spearman_r(x, y)` | Spearman's rho: average-tie ranks, then `pearson_r` of the ranks. Also frozen. |
| `pearson_r_strict(x, y)` / `spearman_r_strict(x, y)` | Additive NaN/±Inf-safe siblings — raise a typed error naming the offending list and index (and a length mismatch) instead of silently returning `CorrResult(NaN, NaN)`. Do not change the frozen functions' behavior. |

Every number below is hand-verified against `scipy` in `mojo/tests/libs/test_stat_tests_pvalues.mojo`,
a hand-written suite that exists specifically because the auto-generated smoke test
(`test_stat_tests.mojo`) only proves each function runs without crashing and pins no numeric value
at all — which is how `_regularized_incomplete_beta`'s first-term bug shipped undetected: before
the fix documented in that file, `_regularized_incomplete_beta(0.6, 3.0, 0.5)` returned a negative
probability and `_t_cdf(2.0, 6.0)` returned a value greater than 1.

```python
s1 = [5.1, 4.9, 5.3, 5.0, 4.8, 5.2, 5.05, 4.95, 5.1, 4.9]
one = runtime.execute("stat_tests", "t_test_1sample", [s1, 5.0])["result"]
one["statistic"]  # 0.627059712862443
one["p_value"]    # 0.5461963009225377  -- matches scipy.stats.ttest_1samp

x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
y = [2.1, 3.9, 6.2, 7.8, 10.5, 11.5, 14.2, 15.8, 18.1, 19.9]
corr = runtime.execute("stat_tests", "pearson_r", [x, y])["result"]
corr["r"]         # 0.9989492896628988   -- matches scipy.stats.pearsonr
corr["p_value"]   # 5.325524542227731e-12 (to relative 1e-4)
```

## `metrics_agg`: counters, histograms, and latency percentiles

| Function | What it does |
| --- | --- |
| `counter_create(name)` / `counter_inc(c, amount=1.0)` / `counter_value(c)` | A named `MetricsCounter` that starts at `0.0` and only ever adds. |
| `histogram_create(name, boundaries)` / `histogram_observe(h, value)` | Named `Histogram` that stores every raw observation alongside its bucket boundaries. |
| `histogram_bucket_counts(h)` | One count per boundary (value `<= boundaries[i]`, `> boundaries[i-1]`), plus a final `+Inf` bucket — length `len(boundaries) + 1`. |
| `histogram_mean(h)` / `histogram_percentile(h, p)` | Mean of stored observations; exact nearest-rank percentile (`p` in `[0, 100]`) computed by sorting the stored values on every call. |
| `rate(values, interval)` | `(last - first) / ((n - 1) * interval)`; `0.0` if fewer than two values or `interval == 0`. |
| `gauge_set(value, new_value)` | Sets and returns `new_value` — a gauge has no state of its own beyond the caller's variable. |
| `compute_throughput(count, duration_seconds)` | `count / duration_seconds`; `0.0` for zero duration. |
| `latency_stats(latencies)` | `[min, max, mean, p50, p95, p99]` in one call, sharing the same nearest-rank percentile as `histogram_percentile`. |

**`histogram_bucket_counts` is not Prometheus's cumulative bucket.** The module docstring says
it "replaces prometheus_client basics," but a real Prometheus histogram's `le` buckets are
cumulative (every bucket also counts everything in the buckets below it). This implementation
places each observation in exactly one bucket — the first boundary it is `<=` — so the counts
are a plain per-bin histogram, not a cumulative one. Verified against
`tests/mojo/test_wave36.mojo`: boundaries `[10, 50, 100]` over observations
`[5, 15, 25, 75, 150]` give `histogram_mean = 54.0` and bucket counts `[1, 2, 1, 1]` — one
observation `<= 10`, two more `<= 50` (and `> 10`), one more `<= 100` (and `> 50`), one over `100`
— which sums to the total observation count (5) exactly because the buckets are non-overlapping.

`histogram_percentile` and `latency_stats` truncate the percentile rank toward zero rather than
rounding or interpolating: `histogram_percentile(h, 50.0)` on those same five sorted values
(`5, 15, 25, 75, 150`) computes `rank = 0.5 * 5 = 2.5`, truncates to `2`, and returns the
2nd-smallest value, `15.0` — not the linearly-interpolated `25.0` a `numpy.percentile`-style
midpoint would give. On ten latencies `10, 20, ..., 100`, `latency_stats` returns
`min=10.0, max=100.0, mean=55.0, p50=50.0, p95=90.0, p99=90.0` — `p95` and `p99` collide here
because both `Int(9.5)` and `Int(9.9)` truncate to the same rank `9`.

## `psychometrics`: classical test theory and 1PL/2PL IRT

| Function | What it does |
| --- | --- |
| `item_difficulty(n_correct, n_total)` | `p = correct / total`; `0.0` if `total == 0`. |
| `item_discrimination(upper_correct, upper_total, lower_correct, lower_total)` | `D = p_upper - p_lower`, the difference in pass rate between the top- and bottom-scoring groups. |
| `point_biserial(mean_correct, mean_total, sd_total, p)` | `r_pb = (M1 - M0) / SD * sqrt(p * (1-p))`. |
| `kuder_richardson_20(n_items, variance_total, p_sum_pq)` | `KR-20 = (n/(n-1)) * (1 - Σpq / σ²_total)`. |
| `cronbach_alpha(n_items, sum_item_variance, total_variance)` | `α = (n/(n-1)) * (1 - Σσ²_item / σ²_total)`. |
| `spearman_brown_prophecy(r, n)` | `r_new = n·r / (1 + (n-1)·r)` — reliability if the test were lengthened `n`-fold. |
| `standard_error_of_measurement(sd, reliability)` | `SEM = SD * sqrt(1 - reliability)`, clamped so `reliability > 1` never produces a negative radicand. |
| `z_score(raw, mean, sd)` / `t_score(z)` / `stanine(z)` | `z = (x-μ)/σ`; `T = 50 + 10z`; stanine buckets `z` into `1..9` at `0.5`-SD-wide bands centered on `5`. |
| `irt_1pl_probability(theta, b)` | Rasch model: `P(θ) = 1 / (1 + exp(-(θ - b)))`. |
| `irt_2pl_probability(theta, a, b)` | Two-parameter logistic: `P(θ) = 1 / (1 + exp(-a(θ - b)))` — `a` is discrimination, `b` is difficulty. |

Worked, hand-verified against `tests/mojo/test_wave66.mojo`:

```python
runtime.execute("psychometrics", "cronbach_alpha", [5.0, 10.0, 50.0])["result"]
# 1.0  -- (5/4) * (1 - 10/50) = 1.25 * 0.8

runtime.execute("psychometrics", "point_biserial", [75.0, 70.0, 10.0, 0.6])["result"]
# 0.244949 -- (75-70)/10 * sqrt(0.6*0.4)

runtime.execute("psychometrics", "spearman_brown_prophecy", [0.8, 3.0])["result"]
# 0.923077 -- a test tripled in length: 3*0.8 / (1 + 2*0.8)
```

Both `irt_1pl_probability` and `irt_2pl_probability` return exactly `0.5` whenever `theta == b`
regardless of the discrimination parameter `a` — the item's difficulty is where a test-taker at
that ability has even odds, and the discrimination only changes how steeply the curve rises away
from that point, never where it crosses `0.5`.

## `interval`: closed-interval arithmetic, not confidence intervals

Despite the name overlap with statistics, this module has no connection to confidence or
prediction intervals — it is numerical interval arithmetic in the `portion`/`pyinterval` sense: a
closed range `[lo, hi]` (or `empty`) with its own `+`, `-`, `*`, `/`.

| Function | What it does |
| --- | --- |
| `interval(lo, hi)` / `empty_interval()` | Creates `[lo, hi]`, or `empty` if `lo > hi`; `empty_interval()` builds the empty sentinel directly. |
| `interval_add(a, b)` / `interval_sub(a, b)` | `[a.lo+b.lo, a.hi+b.hi]` and `[a.lo-b.hi, a.hi-b.lo]`; empty if either input is empty. |
| `interval_mul(a, b)` | `[min, max]` over **all four** endpoint products `a.lo*b.lo, a.lo*b.hi, a.hi*b.lo, a.hi*b.hi` — not just the corner products, because a sign change inside either interval can put the extreme product anywhere among the four. |
| `interval_div(a, b)` | `a * [1/b.hi, 1/b.lo]`; **raises** if `b.lo <= 0 <= b.hi` (the divisor straddles or touches zero). |
| `interval_contains(iv, x)` | `x ∈ [lo, hi]`; always `False` for an empty interval. |
| `interval_overlaps(a, b)` / `interval_intersection(a, b)` | Whether two intervals share a point, and the interval of points they share (empty if they don't overlap). |
| `interval_union_hull(a, b)` | The convex hull `[min(lo), max(hi)]` — the smallest interval containing both, even where they don't overlap. |
| `interval_width(iv)` / `interval_midpoint(iv)` / `interval_radius(iv)` | `hi - lo`, `(lo+hi)/2`, `(hi-lo)/2` — all `0.0` for an empty interval. |

`interval_mul` is the one function where the naive "just multiply the two lower bounds and the
two upper bounds" shortcut is wrong, and the test suite exercises exactly that case: multiplying
`[-1, 1]` by `[2, 3]` forms all four endpoint products — `a.lo*b.lo = -2`, `a.lo*b.hi = -3`,
`a.hi*b.lo = 2`, `a.hi*b.hi = 3` — and takes the min and max across all four, `[-3, 3]`. The
naive corner pair (`lo*lo`, `hi*hi`) alone would give `[-2, 3]`, silently missing the true minimum
of `-3`, which comes from the *cross* pair (`a.lo*b.hi`) instead — that cross term only matters
because `a` spans zero, so its sign flips between endpoints. `interval_div` is the only function
in the module that can raise: dividing by `[-1, 1]` (or any interval containing or bordering
zero) is refused rather than returning `[-inf, inf]` or an arbitrary large-but-finite stand-in.

## Verification

`survival`, `metrics_agg`, `psychometrics`, and `interval` each have an auto-generated
`mojo/tests/libs/test_*.mojo` smoke test that calls every public function once and checks only
that it runs without crashing — none of the four pins a numeric value. Real, hand-checked
coverage for all four lives in the corpus's wave test files instead:
`tests/mojo/test_wave31.mojo` (survival, alongside convex optimization and currency math),
`tests/mojo/test_wave36.mojo` (metrics_agg, alongside pattern matching and weighted graphs),
`tests/mojo/test_wave66.mojo` (psychometrics, alongside power-systems formulas), and
`tests/mojo/test_wave27.mojo` (interval, alongside sketch data structures). `stat_tests` is the
exception with two extra layers: `mojo/tests/libs/test_stat_tests_pvalues.mojo` is a dedicated,
hand-written file pinning real `scipy`-matched values (not present for the other four modules in
this family), on top of coverage in `tests/mojo/test_wave3.mojo`. Every number quoted on this page
either comes directly from one of those hand-written assertions or was re-derived independently
from the formulas in `mojo/engine/{survival,stat_tests,metrics_agg,psychometrics,interval}.mojo`.

**Next:** see [Survival analysis](survival-analysis.md) for the validated, variance-and-confidence-band
layer built on top of `survival`, or [Statistical inference](statistical-inference.md) for the
separate `inference.*` family covering power, multiplicity correction, and resampling.
