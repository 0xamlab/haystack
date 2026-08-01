"""
evaluation — one driver over the frozen evaluation and calibration kernels. Zero Python.

Why a new package when the tree already has these metrics
---------------------------------------------------------
It has the ARITHMETIC and it has none of the composition. Every per-item kernel this package
needs is already present, frozen, correct, and reachable:

  ml_metrics_extended.brier_score_term       one sample's (p - y)^2
  ml_metrics_extended.calibration_ece_term   one bin's |acc - conf| * n_bin / n
  ml_metrics_extended.f_beta_score, matthews_corr_coeff, cohen_kappa
  loss_functions.binary_cross_entropy        one sample's log-loss, clamped at 1e-7
  calibration.calibration_curve              equal-width reliability bins on [0, 1]
  calibration.isotonic_fit / platt_fit       the two recalibration methods
  conformal.*                                split-conformal intervals and coverage
  clustering_metrics.*                       unsupervised quality
  model_compare.*                            paired bootstrap diff CI, McNemar, DM test
  rerank_eval.*                              ranking quality at k
  evaluation_feedback.population_stability_index   one bin's PSI term
  ml.metrics.*                               accuracy, MSE, R^2, confusion, P/R/F1
  stats_bootstrap.*                          bootstrap CIs on mean/median/std

Not one of them is modified, replaced or reimplemented here. What did not exist was anything
that turns a predictions-and-labels pair into an evaluation: a Brier score aggregated at all,
a decomposition of it, an ECE whose binning is stated, a log-loss that says it was clamped,
reliability data that distinguishes an empty bin from a calibrated one, a bootstrap CI for a
metric that is not a mean of per-sample terms, and a gate that can fail.

Modules
-------
  contract   — status codes 360-379, the input contract, binning policy, work budgets
  binning    — the one partition, equal-width (frozen) and equal-count (new)
  scores     — Brier + decomposition, log-loss, ECE/MCE, reliability data, one driver
  resample   — bootstrap CIs on any metric here, keyed and reproducible
  gates      — regression gates and a PSI drift gate, both demonstrated failing

Dependency direction is one-way: `contract` depends on nothing in the package, `binning` on
`contract`, `scores` on both, and `resample` and `gates` on `scores`. There is exactly one
`eval_finite`, one `eval_pairs_status` and one binning builder, because `optimization/` grew
six byte-identical private `_finite` helpers that then drifted and one invariant enforced at
three different strengths under three different status codes.

The three things this package refuses to let happen
---------------------------------------------------
1. **An ECE without its binning.** Different bin counts give materially different numbers:
   0.2 at 2 equal-width bins and 0.4 at 4, on the identical predictions
   p = [0.2, 0.4, 0.6, 0.8] with y = [0, 1, 0, 1]. Every result carrying an `ece` also
   carries `bins_used` and `bin_policy`, and `eval_ece_comparable` is the predicate for
   whether two of them may be compared at all.

2. **A number where there is no answer.** An empty bin is `bin_present == False`, not an
   observed frequency of 0.0. An incomplete PSI is a lower bound under a non-success status,
   not an index. A refused request returns empty lists, not zeros. Rule 4: `0.0` for "could
   not be computed" is the silent wrong answer this tree keeps paying for.

3. **An infinity in a metric field.** Log-loss at p = 0 for a positive label is infinite. The
   frozen kernel clamps; this package reports the epsilon by name and counts the clamped
   samples, so the number is known to be censored. Nothing here can write a non-finite into
   a result field, which would make the whole response a typed transport error rather than a
   metric.
"""
