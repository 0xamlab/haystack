---
icon: brain
description: Conjugate Bayesian updates and Monte Carlo A/B testing, general-purpose variational/Laplace inference primitives, probability calibration, and cluster-quality metrics across four independent kernel modules.
---

# Bayesian methods, calibration, and clustering metrics

Four small, self-contained modules for a common shape of problem: you have a prior belief or a
raw model output, and you need to turn it into something calibrated, compared, or updated in
light of new evidence. `bayesian` runs the closed-form conjugate updates a working Bayesian
analysis actually reaches for (Beta-Binomial, Normal-Normal, Gamma-Poisson) plus a Monte Carlo
A/B test; `bayesian_inference` is a separate, lower-level toolbox of the primitives that sit
underneath approximate inference (ELBO terms, mean-field variational updates, Laplace
approximation, KL divergence between Gaussians); `calibration` turns raw scores into trustworthy
probabilities (isotonic regression, Platt scaling, reliability curves); and `clustering_metrics`
grades a clustering after the fact, against either its own geometry or a ground-truth labeling.
None of the four import Python or share code with each other.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Beta-Binomial conjugate update: uniform prior Beta(1,1), 7 successes, 3 failures
post = runtime.execute("bayesian", "beta_posterior", [1.0, 1.0, 7, 3])["result"]
post
# [8.0, 4.0] -- posterior is Beta(8, 4)

runtime.execute("bayesian", "beta_mean", [8.0, 4.0])["result"]
# 0.6666666666666666

# Two clusterings of the same 8 points, balanced 2x2 so neither predicts the other
runtime.execute("clustering_metrics", "adjusted_rand_index",
                [[0, 0, 0, 0, 1, 1, 1, 1], [0, 1, 0, 1, 0, 1, 0, 1]])["result"]
# -0.16666666666666666 -- worse than a random assignment scores in expectation
```

## The modules

| Module | What it does |
| --- | --- |
| `bayesian` | Beta-Binomial, Normal-Normal, and Gamma-Poisson conjugate updates; Beta mean, variance, and a normal-approximation credible interval; a Bayes factor; the Beta posterior predictive; a normal HPD interval; and a Monte Carlo Bayesian A/B test (`P(B > A)`). |
| `bayesian_inference` | General-purpose approximate-inference arithmetic: a log-space Bayes update, prior-predictive density terms, the ELBO, mean-field Gaussian variational updates, a Laplace approximation around a MAP estimate, expected information gain, a Gaussian credible-interval half-width, KL divergence between two Gaussians, and the Jeffreys prior for a Gaussian scale. |
| `calibration` | Isotonic regression via Pool Adjacent Violators (with weighted tie handling), Platt scaling (Newton fit with Platt's target smoothing), and equal-width reliability-curve binning. |
| `clustering_metrics` | Cluster sizes and centroids, within-cluster inertia, the Davies-Bouldin and Calinski-Harabasz separation indices, a contingency matrix, purity, and the Adjusted Rand Index. |

## Two Bayesian modules, not one

`bayesian` and `bayesian_inference` sound like they should be the same module, and the contract
entries confirm they are not: zero function names overlap between them. `bayesian` is the
applied layer — conjugate-prior updates you can hand a dataset to directly
(`beta_posterior(prior_alpha, prior_beta, successes, failures)`, `normal_posterior(prior_mean,
prior_var, data_mean, data_var, n)`, `poisson_posterior(prior_alpha, prior_beta, sum_x, n)`) and
a Monte Carlo `bayesian_ab_test` that samples from the two resulting Beta posteriors to estimate
`P(B > A)`. `bayesian_inference` is a level of abstraction down: it has no notion of a
"dataset" at all, only scalars that some other computation (a variational-inference loop, a
Laplace approximation around a fitted MAP estimate) would supply — `variational_elbo_term`
takes an already-computed `log_likelihood` and `kl_divergence` and returns their difference;
`mean_field_update_mean` takes a precomputed `natural_grad_sum` and `precision`. Nothing in
`bayesian_inference` samples, iterates, or reads a list — every function is a closed-form scalar
formula, which is also why every one of its ten functions type-checks as `Float64 -> Float64` in
the contract with no `List` in sight, unlike every function in `bayesian` that returns a
posterior (`beta_posterior`, `normal_posterior`, `poisson_posterior`, `beta_credible_interval`,
`hpd_interval_normal`), which returns a `List[Float64]`.

Two more modules share vocabulary with these without sharing code. `ml.naive_bayes` (documented
in [Classical ML algorithms](ml-classical-algorithms.md)) is a Gaussian Naive Bayes
*classifier* — it applies Bayes' theorem once, at prediction time, to turn per-class Gaussian
likelihoods into a class label, and has no concept of a prior-to-posterior update over an
unbounded number of observations. And `ab_testing.mojo` (not yet narratively documented, so out
of scope here beyond the pointer) is the classical/frequentist counterpart to
`bayesian.bayesian_ab_test`: two-proportion z-tests, a Wilson score confidence interval, and
epsilon-greedy/UCB1 bandit selection, with no Bayesian posterior anywhere in it. If you need "is
B better than A" answered two different ways for a sanity check, `bayesian.bayesian_ab_test`
and `ab_testing.z_test_proportions` are the two functions, in two different modules, that answer
it — not one function each in the same place.

### `bayesian_ab_test` does not take a seed

Every other function on this page is a pure, deterministic formula. `bayesian_ab_test` is the
one exception: reading its body, it draws `n_samples` pairs of Beta variates via a Marsaglia-Tsang
Gamma sampler seeded from `std.random.random_float64()`, and its contract signature —
`bayesian_ab_test(successes_a, trials_a, successes_b, trials_b, n_samples=10000)` — has no seed
parameter at all. That is a real, checkable difference from the rest of the corpus's bootstrap
and resampling surfaces (see [Evaluation & calibration gates](evaluation-calibration.md)'s
`bootstrap_metric_ci_flat`, which takes an explicit seed that reaches every draw so the interval
is bit-reproducible): two calls with identical arguments will not return the same `P(B > A)`
figure. The test suite reflects this directly — `tests/mojo/test_wave25.mojo` asserts
`bayesian_ab_test(10, 100, 50, 100, 5000) > 0.5` (B has a 50% observed rate against A's 10%, so
B should win the large majority of posterior draws) and that the result lies in `[0, 1]`; it does
not, and cannot, assert an exact value. Treat the returned probability as an estimate that moves
by roughly `sqrt(p(1-p)/n_samples)` between runs, not as a number to diff against a golden file.

## `calibration` is already documented in depth — this page adds the coverage row

`calibration`'s five functions (`isotonic_fit`, `isotonic_transform`, `platt_fit`,
`platt_transform`, `calibration_curve`) and its three result structs (`IsotonicFit`,
`PlattParams`, `CalibrationCurve`) are the exact subject of [Probability & prediction
calibration](ml-calibration.md), which already carries a full function table, the isotonic-vs-Platt
tradeoff, and a note that the isotonic fit is verified against sklearn's weighted-tie-pooling PAV.
That page's table is headed `Function`, not `Module`, so it does not register `calibration` as a
narratively-documented module for this corpus's coverage check even though the prose genuinely
covers it — this page's module-table row above closes that specific gap without duplicating the
existing writeup. For the metrics that *grade* a calibrated model once you have one (Brier score,
log-loss, expected/maximum calibration error, reliability diagrams, bootstrap confidence
intervals, regression and drift gates), see [Evaluation & calibration
gates](evaluation-calibration.md) — that page's `evaluation.scores` module is a distinct set of
functions from `calibration` here (no shared names), covering the evaluation side of calibration
rather than the fitting side.

One number worth pinning down independently, since it recurs across both pages: `isotonic_fit`
on `x = [1, 2, 3, 4]`, `y = [1, 3, 2, 4]` produces thresholds `[1, 2, 3, 4]` and pooled values
`[1, 2.5, 2.5, 4]` — the middle two points violate monotonicity (`3 > 2`) so PAV averages them to
`2.5` and leaves the first and last alone. That is a pinned assertion in
`mojo/tests/libs/test_calibration.mojo`, not a smoke test, and it also holds with the four input
points supplied in any order (`test_calibration.mojo` checks the unsorted permutation
`x = [4, 1, 3, 2]` against the same fitted values).

## `clustering_metrics` grades a clustering; `ml.clustering` produces one

The other module this one is easy to conflate with is `ml.clustering`
(in [Classical ML algorithms](ml-classical-algorithms.md)), which owns `kmeans`,
`assign_cluster`, and `silhouette_score` — it runs the clustering algorithm and includes exactly
one evaluation metric (silhouette) alongside it. `clustering_metrics` has no clustering
*algorithm* at all — no `kmeans`, no `assign_cluster` — and no `silhouette_score` either; it takes
`data` and a `labels` assignment (from anywhere: `ml.clustering.kmeans`, `ml.classifiers.kmeans_cluster`,
or a completely different provenance) and computes centroids, inertia, and two competing
separation indices from them, plus three metrics (`contingency_matrix`, `purity`,
`adjusted_rand_index`) that compare one label assignment against another rather than against raw
geometry at all. The two modules are complementary, not redundant: a k-means run from
`ml.clustering` produces `labels`, and `clustering_metrics.davies_bouldin` or
`calinski_harabasz` then grades that assignment's separation, entirely independent of which
module produced the labels.

### Davies-Bouldin and Calinski-Harabasz, computed by hand

Both indices are defined on the same two clusters of 2D points, verified independently against
the formulas in `mojo/engine/clustering_metrics.mojo` (not taken on faith from the test file,
which only asserts the *direction*, not the value):

```python
# Well separated: {(0,0), (1,0)} vs {(100,0), (101,0)}
data_good  = [[0.0, 0.0], [1.0, 0.0], [100.0, 0.0], [101.0, 0.0]]
labels     = [0, 0, 1, 1]

# Poorly separated: {(0,0), (1,0)} vs {(2,0), (3,0)}
data_bad   = [[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [3.0, 0.0]]

runtime.execute("clustering_metrics", "davies_bouldin", [data_good, labels, 2])["result"]
# 0.01  -- centroids (0.5,0) and (100.5,0); within-cluster scatter 0.5 each side;
#          DB = (0.5+0.5) / 100 = 0.01

runtime.execute("clustering_metrics", "davies_bouldin", [data_bad, labels, 2])["result"]
# 0.5   -- centroids (0.5,0) and (2.5,0), same scatter; DB = (0.5+0.5) / 2.0 = 0.5

runtime.execute("clustering_metrics", "calinski_harabasz", [data_good, labels, 2])["result"]
# 20000.0  -- between-cluster dispersion 10000 over 1 degree of freedom,
#             within-cluster dispersion 1.0 over 2 degrees of freedom

runtime.execute("clustering_metrics", "calinski_harabasz", [data_bad, labels, 2])["result"]
# 8.0
```

Davies-Bouldin is lower-is-better and drops by a factor of 50 going from the poorly separated to
the well separated pair; Calinski-Harabasz is higher-is-better and rises by a factor of 2500 over
the same change, because it squares the between-cluster distance while Davies-Bouldin only
divides by it once. Both hand-computed values match `test_wave47.mojo`'s directional assertions
(`db_good < db_bad`, `ch_good > ch_bad`) exactly.

### Adjusted Rand Index: negative is a real, reachable value

`adjusted_rand_index` is corrected for chance, which means a labeling that is actively
*anti-correlated* with the truth — worse than assigning clusters at random — scores below zero,
not just below the identical-labeling score of `1.0`. The code example at the top of this page,
`adjusted_rand_index([0,0,0,0,1,1,1,1], [0,1,0,1,0,1,0,1])`, is exactly that case: both
partitions split 8 points into two even halves of 4, so `n_true = n_pred = 2`, but every
`(true, pred)` combination occurs exactly twice, giving a perfectly uniform 2x2 contingency table
`[[2, 2], [2, 2]]`. Working the formula by hand: `sum_comb = 4 * C(2,2) = 4`, `sum_row = sum_col =
2 * C(4,2) = 12`, `comb_n = C(8,2) = 28`, `expected = 12*12/28 = 36/7`, `max_index = 12`, and
`ARI = (4 - 36/7) / (12 - 36/7) = (-8/7) / (48/7) = -1/6 ≈ -0.1667` — an exact rational value,
not a rounding artifact, and it matches `test_wave47.mojo`'s `test_ari_random_low` assertion
(`ari < 0.5`) with room to spare. `purity`, by contrast, cannot go negative — on the same style
of imbalanced-but-uninformative labeling (`labels_true=[0,0,1,1]`, `labels_pred=[0,1,0,1]`) it
returns exactly `0.5`, because purity only ever credits the best-matching true label per
predicted cluster and never penalizes a wrong split the way ARI's chance-correction does.

### The shared allocation guard

`contingency_matrix`, `purity`, and `adjusted_rand_index` all refuse (returning an empty matrix,
`0.0`, or `0.0` respectively, never aborting) when `n_true > 10000`, `n_pred > 10000`, or
`n_true * n_pred > 1_000_000`. `cluster_centroids` carries the same `k > 10000` cap. This matters
because `adjusted_rand_index` derives `n_true`/`n_pred` from the *maximum label value it sees plus
one* — a single `NaN`-derived or corrupted label of, say, `50000` would otherwise ask for a
50001-row contingency table. The guard converts that failure mode into a returned `0.0` (an
uninformative but finite ARI) rather than an unbounded allocation.

## Verification notes

`bayesian` and `bayesian_inference` each have real, hand-verified pinned-value coverage, but in
different places. `mojo/tests/libs/test_bayesian.mojo` and `test_bayesian_inference.mojo` are the
auto-generated smoke suites (finite-output checks only, no numeric assertions) — but
`tests/mojo/test_wave25.mojo` carries fifteen hand-derived assertions against `bayesian`
specifically, including `beta_posterior(1,1,7,3) == [8,4]`, `poisson_posterior(1,1,10,5) ==
[11,6]`, `bayes_factor(0.8,0.2) == 4.0`, and `hpd_interval_normal(0,1,0.95) ≈ [-1.96, 1.96]`.
`bayesian_inference` has no equivalent wave-file suite — only the auto-generated smoke test — so
its formulas are verified here independently instead: `kl_gaussians(0, 1, 0, 2)` against the
textbook closed form `ln(σ2/σ1) + (σ1² + (μ1−μ2)²)/(2σ2²) − 1/2` gives `ln(2) + 0.125 − 0.5 =
0.31814718...`, which the kernel reproduces to machine precision; `credible_interval_half_width(2.0,
1.96) == 3.92` follows directly from its one-line `z * std` definition; and
`jeffreys_prior_gaussian(2.0) == 0.5` from `1/σ`. `clustering_metrics` has both an auto-generated
smoke suite (`test_clustering_metrics.mojo`, four functions only) and a full hand-verified
suite (`tests/mojo/test_wave47.mojo`, all eight functions, shared with the wavelet-transform and
regression-tree suites in that same wave file). `calibration` is verified in
`mojo/tests/libs/test_calibration.mojo` against known PAV and Platt-scaling values, as already
described on [Probability & prediction calibration](ml-calibration.md).

**Next:** for the fitting side of turning scores into probabilities in more depth, see
[Probability & prediction calibration](ml-calibration.md); for grading how calibrated or accurate
a model's predictions are once you have them, see [Evaluation & calibration
gates](evaluation-calibration.md); for the k-means/silhouette pairing that produces the label
assignments `clustering_metrics` grades, see [Classical ML algorithms](ml-classical-algorithms.md).
