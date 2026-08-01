"""
inference — statistical DRIVERS over the frozen statistics kernels. Zero Python imports.

What the tree has, and what it cannot say
-----------------------------------------
`stat_tests` (25 functions), `stats_bootstrap` (17), `distributions`, `hypothesis`,
`correlation`, `linear_models` and `stats` are frozen and are not touched. Between them
they compute nearly every statistic this package quotes. What none of them can do is tell a
caller whether the number they returned means anything, and four of them return a plausible
number where no answer exists:

* `stat_tests.t_test_1sample` / `t_test_2sample` / `chi_squared_test` clamp their p-value
  into `[0, 1]` and return `reject_h0` beside it. When the underlying tail is wrong the
  clamp turns the error into a certainty: measured, `t_test_2sample([1,2,3], [4,5,6])`
  returns `p_value = 0.0, reject_h0 = True` where the true two-sided p is `0.0213`. The
  cause is a defect in `stat_tests._regularized_incomplete_beta` — one missing
  continued-fraction level — and `inference.core` documents it with the reproduction, keeps
  the frozen kernel untouched, and adds the correct primitive plus a `t_cdf_agreement`
  driver so the disagreement is a measurable value rather than folklore.
* `stats_bootstrap`'s nine bootstrap entry points all draw from `std.random.random_float64`,
  so a confidence interval changes between runs of the same code on the same data. An
  interval that cannot be quoted twice cannot be quoted in a decision that has to be
  explained, which is the premise of this whole tree.
* `stats_bootstrap.bootstrap_test` returns `count / n_bootstrap`, which is `0.0` when no
  permutation beat the observed statistic. A p-value of exactly zero does not exist for a
  finite permutation test; the estimator that does is `(1 + count) / (1 + B)`.
* `linear_models.logistic_fit` returns its last iterate with `converged = False` when the
  data are separable — measured, `x = [-2,-1,1,2]`, `y = [0,0,1,1]` gives
  `weight = 26.61` with a standard error of `424777.88` — and a caller that ignores the
  flag gets coefficients for a model whose MLE does not exist.
* `stat_tests.shapiro_wilk_approx([1.0, 2.0, 3.0])` returns `p_value = nan` with
  `reject_h0 = False` — "do not reject normality", decided by a NaN, because `1 - w` is
  -2.2e-16 for collinear order statistics and its own `p < 0` / `p > 1` clamps cannot see a
  NaN. `ab_testing.z_test_proportions(0, 0, 0, 0)` returns `[0.0, 0.99999999895]`, a confident
  "not significant" from a request with no data, and
  `ab_testing.confidence_interval_proportion(0, 0, 0.95)` returns `[nan, nan]`.
* `linear_models._solve_linear_system`, `regression._solve_normal_equations` and
  `linalg.mat_solve` all report a singular system as a solution vector: the first two skip
  a near-zero pivot and leave that coefficient at 0.0, the third returns all zeros.

Nothing here recomputes a statistic that exists. `stat_tests`' normality tests, its
chi-squared tail, `linear_models.logistic_fit` and `logistic_std_errors`,
`stats_bootstrap`'s mean/median/std, `determinism`'s counter-based sampling,
`math_ext.norm_cdf` / `norm_ppf`, `special_functions.log_gamma`,
`linalg_ext.mat_is_positive_definite`, `sorting.mergesort` and
`sparse_numerics.csr.dims_fit` are all called unchanged. The composition, the validation,
the refusals and the seeds are what this package adds.

Modules
-------
  core — the package's single status vocabulary (320-339), finiteness predicate, rule-4b
        tolerance builder, wrapping-safe shape/work budgets, the corrected incomplete beta
        with the t and F tails and the t QUANTILE the tree does not have, and the weighted
        least-squares solve that refuses a rank-deficient system instead of returning zeros
        for it.
  assume — a p-value from a test whose assumptions were not met is not a p-value. Levene's
        variance-homogeneity test on group medians, the chi-squared minimum-expected-cell
        rule, residual normality from two frozen tests with their agreement stated, and
        `t_test_checked_flat`, which returns the corrected two-sided p-value BESIDE the
        frozen kernel's clamped one and every assumption verdict, so a caller cannot read
        the number without the caveat.
  resample — bootstrap confidence intervals and permutation tests that reproduce. Every
        draw comes from `determinism.sampling_keyed` under an explicit `seed` and `stream`,
        so a replicate is a pure function of its coordinates; the result carries `B`, the
        seed, the stream and the Monte-Carlo uncertainty OF THE INTERVAL ENDPOINTS, because
        an interval from `B` resamples has sampling error of its own and a caller cannot
        know its precision otherwise.
  glm — logistic and Poisson regression by IRLS. A fit that hit the iteration cap has no
        coefficients and reports the count; separable data are REFUSED with a separating
        hyperplane as the witness, because the MLE diverges while the fit "succeeds"
        numerically; a singular information matrix is a status, not a zero.
  robust — Huber regression by iteratively reweighted least squares, with the MAD scale
        reported and its own degeneracy (more than half the residuals at the median) as a
        refusal. A huge tuning constant reduces to ordinary least squares to 1e-9, which
        the suite asserts against the frozen `regression.ols_multiple`.
  multiplicity — Bonferroni, Holm and Benjamini-Hochberg. Correction changes what a
        rejection MEANS, so every result names its method and its alpha, carries the
        adjusted values back in the caller's original order, and states how many hypotheses
        the family contained.
  power — power and sample size for a two-sample mean comparison, in a normal-approximation
        lane and a t lane, plus the inversion the tree lacks. A returned sample size is
        VERIFIED by re-evaluating power at `n` and at `n - 1`, so `minimal` is a measured
        property; a zero effect is a refusal, not `1000000`.

Design rules the package keeps
------------------------------
*An answer that does not exist is absent, not zero, and never under a success status.* Every
driver returns a struct with a status field, and the suites assert the status, not only the
numbers. A refusal names the reason from one 320-339 vocabulary.

*Anything randomised takes an explicit seed.* `random_float64` and `seed(` appear nowhere in
this package; every draw is `determinism/counter_rng` through `determinism/sampling_keyed`,
counter-based, so a draw is a pure function of its coordinates rather than of what ran
before it. Same-seed bit-identity is asserted in the suites.

Public functions take and return only `List`/`Int`/`Float64`/`Bool`/`String` or a struct
declared in the same file, so the package lands in the runtime library contract without a
new message type and is callable from both local SDKs as `execute(module, function, args)`.
It is therefore *not* in `_SKIP_RUNTIME_DIRS`.
"""
