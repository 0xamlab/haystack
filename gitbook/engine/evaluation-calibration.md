---
icon: gauge-simple-high
description: Brier with Murphy's decomposition, log-loss that says when it was clamped, calibration error that never travels without its binning, reproducible bootstrap intervals
---

# Evaluation & calibration gates

Five kernel modules that turn one predictions-and-labels pair into an evaluation you can put
in a release record. All run as compiled kernels inside the runtime that ships with the SDK —
there is nothing to start and nothing to install separately.

The arithmetic of these metrics is not hard, and that is the problem. A Brier score is four
lines. What takes the time is the part around it: which binning produced the calibration
error, whether a log-loss was censored, whether an empty bin was drawn as a perfectly
calibrated point, and whether the gate that let a model through was ever capable of stopping
one. Every one of those is a field here.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

probs  = [0.1, 0.3, 0.5, 0.7, 0.9]
labels = [0.0, 0.0, 1.0, 1.0, 1.0]

report = runtime.execute(
    "evaluation.scores", "evaluate_flat",
    [probs, labels, 5, 5, 0],   # n = 5, 5 bins, policy 0 = equal width
)["result"]

report["brier"]                  # 0.09
report["base_rate"]              # 0.6
report["accuracy"]               # 1.0   at report["accuracy_threshold"] == 0.5
report["log_loss"]               # 0.3234436203133559
report["log_loss_clamped"]       # 0   — nothing was censored
report["ece"]                    # 0.26
report["mce"]                    # 0.5
report["bins_used"]              # 5
report["bins_occupied"]          # 5
report["residual"]               # 0.0
report["decomposition_closes"]   # True
```

One call, one binning, one pass. Assembling those numbers from separate calls is how two
figures in the same report come to be binned differently.

## The modules

| Module | What it does |
| --- | --- |
| `evaluation.scores` | Brier and Murphy's reliability / resolution / uncertainty with the residual the identity leaves behind, log-loss with its clamp reported, expected and maximum calibration error, reliability-diagram data, and one driver that returns all of it |
| `evaluation.binning` | the one partition every calibration number here is read from — equal-width bins on `[0, 1]`, or equal-count (quantile) bins whose edges are order statistics of your own predictions — plus per-sample bin assignment and the bin edges for an axis |
| `evaluation.resample` | percentile bootstrap confidence intervals for any metric above, seeded so the interval reproduces bit-for-bit, with the draw diagnostics that let you check that claim rather than trust it |
| `evaluation.gates` | a regression gate over two datasets under one binning, a scalar gate with an explicit margin, and a population-stability drift gate that reports an incomplete index as a lower bound |
| `evaluation.contract` | the status vocabulary, the input contract, the binning policy, and the work budgets — the shared refusals, callable on their own so you can validate a request before sending it |

## Expected calibration error is binning-dependent, and here it says so

This is the most useful thing on this page, so it comes first.

Two ECEs computed with different bin counts are two different statistics that share a name.
Not slightly different — here is the same four predictions and the same four labels, binned
two ways:

```python
probs  = [0.2, 0.4, 0.6, 0.8]
labels = [0.0, 1.0, 0.0, 1.0]

two  = runtime.execute("evaluation.scores", "calibration_error_flat",
                       [probs, labels, 4, 2, 0])["result"]
four = runtime.execute("evaluation.scores", "calibration_error_flat",
                       [probs, labels, 4, 4, 0])["result"]

two["ece"],  two["bins_used"]     # 0.19999999999999996, 2
four["ece"], four["bins_used"]    # 0.39999999999999997, 4
four["mce"]                       # 0.6
```

A factor of two, from the bin count alone. Both are correct. Neither is comparable to the
other, and there is a predicate that says so:

```python
runtime.execute("evaluation.contract", "eval_ece_comparable", [2, 0, 4, 0])["result"]  # False
runtime.execute("evaluation.contract", "eval_ece_comparable", [4, 0, 4, 0])["result"]  # True
```

`bins_used` and `bin_policy` are fields of every result that carries an `ece`, so a number
lifted out of one report and compared against another can be checked rather than assumed. The
Brier score, by contrast, does not bin at all and does not move: it is `0.19999999999999998`
at two bins and at four.

{% hint style="warning" %}
**Do not quote an ECE without its bin count and policy.** A calibration error that improved
from 0.4 to 0.2 between two releases may be an improvement, or may be the same model binned
into half as many bins. `eval_ece_comparable` takes the two provenances and answers; it also
returns `False` when either binning was invalid, because two invalid binnings are not
comparable, they are both refusals.
{% endhint %}

## The Brier decomposition does not add up, and the residual is the measure of that

Murphy's decomposition is usually printed as an identity:

```text
Brier = reliability - resolution + uncertainty
```

It is an identity only when every prediction inside a bin is identical. With any real binning
there are within-bin variance and covariance terms as well, so the three printed numbers do
not reconstruct the Brier score — and the gap depends entirely on how coarse the bins are.
Most implementations do not mention this. Here it is a returned field.

```python
# Five bins over five predictions: one sample per bin, so there is no within-bin
# variance and the identity is an identity.
fine = runtime.execute("evaluation.scores", "brier_decomposition_flat",
                       [probs_a, labels_a, 5, 5, 0])["result"]
fine["reliability"], fine["resolution"], fine["uncertainty"]   # 0.09, 0.24, 0.24
fine["residual"], fine["decomposition_closes"]                 # 0.0, True

# The same data in ONE bin. The Brier score is unchanged; the decomposition is not.
coarse = runtime.execute("evaluation.scores", "brier_decomposition_flat",
                         [probs_a, labels_a, 5, 1, 0])["result"]
coarse["brier"]                                                # 0.09, as before
coarse["reliability"], coarse["resolution"]                     # 0.009999999999999995, 0.0
coarse["residual"], coarse["decomposition_closes"]              # -0.16, False
```

`0.09` of Brier score against `0.01 - 0.0 + 0.24 = 0.25` of decomposition. The `-0.16` is not
an error — it is exactly how much the binning is smoothing, and it is the number to look at
before quoting a reliability term as if it were a component of the score.

## Log-loss on a probability of 0 is infinite. You are told when that happened

A confident, wrong prediction has an infinite log-loss, and an infinity cannot travel in a
metric field. The kernel clamps the probability into `[ε, 1 − ε]` with `ε = 1e-7`, which is the
conventional fix — and then reports both the epsilon and how many samples hit it, which is the
part that is usually missing.

```python
saturated = runtime.execute("evaluation.scores", "log_loss_flat",
                            [[0.0, 1.0, 0.0, 1.0], [1.0, 0.0, 1.0, 0.0], 4])["result"]

saturated["log_loss"]        # 16.11809565124531  — finite, and censored
saturated["eps_used"]        # 1e-07
saturated["clamped_count"]   # 4 of 4 samples
saturated["present"]         # True
```

A `log_loss` with `clamped_count > 0` is a lower bound on an infinite quantity, not a
measurement of it. With `clamped_count == 0` it is the mean cross-entropy and nothing has been
suppressed:

```python
ordinary = runtime.execute("evaluation.scores", "log_loss_flat",
                           [[0.2, 0.8, 0.3, 0.7], [0.0, 1.0, 0.0, 1.0], 4])["result"]
ordinary["log_loss"], ordinary["clamped_count"]     # 0.28990924797735085, 0
```

## An empty bin is absent, not a perfectly calibrated point at zero

A reliability diagram built from bin means alone draws an empty bin as a point at observed
frequency zero — which reads as a bin full of negatives that the model was confident about.
That is a picture of nothing, and it is indistinguishable from a real finding.

```python
# Ten predictions all clustered just under 0.07, on five equal-width bins.
diag = runtime.execute("evaluation.scores", "reliability_diagram_flat",
                       [clustered, clustered_labels, 10, 5, 0])["result"]

diag["bins_occupied"]     # 1 of 5
diag["bin_count"]         # [10, 0, 0, 0, 0]
diag["bin_present"]       # [True, False, False, False, False]
diag["bin_conf"]          # [0.05900000000000001, 0.0, 0.0, 0.0, 0.0]
diag["bin_freq"]          # [0.2, 0.0, 0.0, 0.0, 0.0]
```

Read `bin_present` before `bin_conf` or `bin_freq`. Where the flag is `False`, the two values
are `0.0` only because a numeric field has to hold a number; they are not observations. Plot
four fewer points, not four points at the origin.

This is also the case for equal-count binning. A model that puts everything in one corner of
`[0, 1]` — which is what a well-trained classifier on an imbalanced problem does — gets one
occupied bin out of ten under equal width, and useful resolution under equal count, because
the edges are order statistics of the predictions themselves:

```python
quantile = runtime.execute("evaluation.scores", "reliability_diagram_flat",
                           [clustered, clustered_labels, 10, 5, 1])["result"]
quantile["bins_occupied"]   # 5 of 5

runtime.execute("evaluation.binning", "eval_bin_edges_flat",
                [clustered, 10, 5, 1])["result"]
# [0.0, 0.054000000000000006, 0.058, 0.062, 0.066, 1.0]
```

Ties are not split, so with heavily repeated predictions the bins are not actually equal-count
and some are empty. `bins_occupied` says how many carried data; it is never inflated to the
bin count you asked for.

### The published boundaries are boundaries of the partition, not of the arithmetic

`bin_lo`, `bin_hi` and `eval_bin_edges_flat` describe the partition your samples were actually
assigned to, exactly. Two guarantees hold for every bin count and both policies:

* feeding a published boundary back in as a sample returns the bin it opens — bin `b`'s lower
  boundary is a *member* of bin `b`, never of bin `b - 1`;
* `bin_hi[b]` is the identical double to `bin_lo[b + 1]`, so the reported intervals tile the
  domain with no gap and no overlap.

Together those mean a binary search over the published edges reproduces
`eval_bin_assign_flat` for every value you can represent, so an axis you draw from these edges
cannot exclude one of its own points.

This is less obvious than it looks. Under equal width the mathematical boundary of bin `b` is
`b / h`, but the assignment is decided by an integer floor, and for some bin counts the double
nearest `b / h` falls on the low side of that floor: at `h = 22`, the nearest double to
`15 / 22` is assigned to bin 14. Publishing it as bin 15's lower boundary would put the
boundary on the wrong side of itself. The reported boundary is the first double in the bin, at
most one unit in the last place from `b / h`, which is what makes the two guarantees above
true rather than nearly true. At `h = 5` and `h = 10` the boundaries come out as exactly
`0.2, 0.4, 0.6, 0.8` and `0.1 ... 0.9`.

```python
runtime.execute("evaluation.binning", "eval_bin_edges_flat",
                [probs, 400, 5, 0])["result"]
# [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
```

## A confidence interval that reproduces from the record

The bootstrap takes a seed, and the seed reaches every individual draw rather than just the
first one. Re-running the same request returns a bit-identical interval — on any machine, in
any order, whatever else the process did.

```python
ci = runtime.execute(
    "evaluation.resample", "bootstrap_metric_ci_flat",
    #  probs, labels, n,  metric, bins, policy, n_boot, alpha, seed
    [probs, labels, 400,       0,   10,      0,    200,  0.05,   42],
)["result"]

ci["point"]                  # 0.33209999999999995
ci["lo"], ci["hi"]           # 0.3041542999999998, 0.3612285250000001
ci["point_inside"]           # True
ci["n_boot"], ci["n_draws"]  # 200, 80000
ci["distinct_replicates"]    # 200 of 200
ci["seed"]                   # 42 — returned, so the run is re-derivable
```

`distinct_replicates` is the diagnostic that makes "the seed reached every draw" checkable
instead of asserted. If the seed had been consumed once and reused, or the draw coordinates
had collided, the replicate distribution would collapse and this number would be small.

The interval is the percentile method and is not bias-corrected, so for a skewed statistic the
point estimate can legitimately fall outside it. `point_inside` reports that rather than the
interval being quietly widened to hide it.

### Too few replicates for your alpha is a refusal, not a narrow interval

A percentile interval reads the replicate distribution at probability `alpha / 2`, and a
distribution of `n_boot` values carries no information at any probability finer than
`1 / n_boot`. So a 95% interval needs at least `2 / 0.05 = 40` replicates. Below that the
endpoints are decided by the single most extreme replicate rather than estimated from the
distribution — one replicate produces `lo == hi`, an interval of width zero that a caller has
no way to recognise as meaningless.

That request is refused, before any draw is made, and the result says what to ask for instead:

```python
too_few = runtime.execute("evaluation.resample", "bootstrap_metric_ci_flat",
                          [probs, labels, 400, 0, 10, 0, 1, 0.05, 42])["result"]

too_few["status"]       # 371 — invalid_resample_count
too_few["present"]      # False
too_few["n_boot_min"]   # 40 — the smallest replicate count that resolves a 95% interval
too_few["lo"], too_few["hi"]   # 0.0, 0.0 — no interval was produced, so none is reported

runtime.execute("evaluation.resample", "bootstrap_min_replicates", [0.05])["result"]   # 40
runtime.execute("evaluation.resample", "bootstrap_min_replicates", [0.10])["result"]   # 20
```

`n_boot_min` is reported on success too, so a result always carries the bound it satisfied. A
wider interval needs fewer replicates and a narrower one needs more; 40 is the floor for the
usual 95%, not a recommendation. For a stable interval rather than a merely resolvable one,
expect to want hundreds to thousands.

Any metric on this page can be resampled, including the ones that are not means of per-sample
terms. An ECE interval carries its binning like every other ECE:

```python
ece_ci = runtime.execute("evaluation.resample", "bootstrap_metric_ci_flat",
                         [probs, labels, 400, 4, 10, 0, 200, 0.05, 42])["result"]
ece_ci["lo"], ece_ci["hi"]              # 0.2119899999999999, 0.3086075
ece_ci["bins_used"], ece_ci["bin_policy"]   # 10, 0
```

The metric is selected by integer: `0` Brier, `1` log-loss, `2` accuracy at 0.5, `3` base rate,
`4` expected calibration error. An id outside that set is refused, never defaulted to zero — a
request for a metric that does not exist returning a Brier score is a plausible wrong number,
which is the worst outcome an evaluation surface can produce.

## The gates can fail, and the margin says by how much

A gate that has only ever been shown accepting is decoration. Both gates here have a
constructed failing case, and the failure is a number rather than a boolean.

```python
gate = runtime.execute(
    "evaluation.gates", "metric_regression_gate_flat",
    #  baseline set,        candidate set,      metric, bins, policy, tolerance
    [base_p, base_y, 2,  cand_p, cand_y, 2,          0,    4,      0,      0.01],
)["result"]

gate["baseline"], gate["candidate"]   # 0.009999999999999998, 0.36
gate["delta"]                         # 0.35
gate["decided"], gate["passed"]       # True, False
gate["margin"]                        # -0.33999999999999997
gate["higher_is_better"]              # False — Brier, so a rise is a regression
```

`margin` is the number for a build log: positive is slack, negative is the amount by which the
tolerance was exceeded. `-0.34` is a rejection with an explanation attached.

Three things about the direction and the arithmetic are worth knowing before you wire this into
a pipeline.

**The direction belongs to the metric, not to you.** There is no `higher_is_better` argument.
The same two datasets gated on accuracy instead of Brier regress with the opposite sign, and
both fail:

```python
acc = runtime.execute("evaluation.gates", "metric_regression_gate_flat",
                      [base_p, base_y, 2, cand_p, cand_y, 2, 2, 4, 0, 0.01])["result"]
acc["baseline"], acc["candidate"]     # 1.0, 0.0
acc["delta"], acc["passed"]           # -1.0, False
acc["higher_is_better"]               # True
```

Base rate is not gateable at all. It is a property of your labels, not of your model, so
`metric_regression_gate_flat` refuses it with `unknown_metric` and `decided == False` rather
than picking a direction for you.

**`decided` is a separate field from `passed`.** There are three outcomes, not two: pass, fail,
and "this comparison cannot be made". Whenever `decided` is `False` — a non-finite value, a
negative tolerance, either dataset failing its input contract — `passed` is meaningless and
`status` names the reason. A gate that folded the third case into either of the first two would
either block a release for a reason that does not exist or wave one through unexamined.

**The comparison is exact, and a decimal tie is usually not a tie.** The tolerance you supply
is used as given, in the metric's own units, with no hidden widening:

```python
runtime.execute("evaluation.gates", "metric_gate", [0.09, 0.10, 0.01, False])["result"]
# passed  False
# margin -8.673617379884035e-18

runtime.execute("evaluation.gates", "metric_gate", [0.25, 0.5, 0.25, False])["result"]
# passed  True
# margin  0.0
```

The first fails because `0.10 - 0.09` in binary floating point is `0.010000000000000009`, which
is larger than `0.01` — five ulps, carried in by writing those three numbers in decimal, not
introduced by the gate. `margin` shows you the exact overshoot. The second is a tie that is
exact in binary and passes. Widening the tolerance to absorb the first case would make a gate
whose real threshold nobody could state; if you want `0.09 → 0.10` to pass, ask for `0.011`.

Two metric values can also be so far apart that their difference is not a representable
number at all, even though each one is. That is refused rather than answered — `decided` is
`False` with `non_finite_value` — because there is no honest verdict to give and every
alternative is worse: an infinite `delta` cannot travel in a result field, and a gate that
treated it as a comparison would report the largest regression expressible as a pass.

## Drift, and an index that admits when it is incomplete

The population stability index compares two score distributions against a fixed partition. A
bin that one distribution occupies and the other does not has an infinite term, and infinity
cannot be summed — so the conventional implementation contributes zero there, which understates
drift exactly when the drift is most extreme.

```python
shifted = runtime.execute("evaluation.gates", "psi_drift_gate_flat",
                          [reference, 100, candidate, 100, 2, 0.25])["result"]
shifted["psi"]              # 0.16945957191598185
shifted["present"]          # True — every bin contributed a finite term
shifted["bins_matched"]     # 2
shifted["bins_unmatched"]   # 0
shifted["decided"], shifted["drifted"]   # True, False   (0.169 < 0.25)
```

Now the same reference against a candidate that abandoned one of the two bins entirely:

```python
gone = runtime.execute("evaluation.gates", "psi_drift_gate_flat",
                       [reference, 100, abandoned, 100, 2, 0.40])["result"]
gone["status"]              # 376 — psi_incomplete_lower_bound_only
gone["present"]             # False  — there is no index, and psi is 0.0 and means nothing
gone["psi_lower_bound"]     # 0.34657359027997264
gone["bins_unmatched"]      # 1
gone["decided"]             # False — 0.347 is below 0.40, and the missing term could be anything
```

`psi` is absent, not zero. What exists is a lower bound, and whether that is enough to decide
depends on the threshold. Against a stricter cut, the same incomplete index settles the
question — every missing term is positive, so a lower bound already past the threshold is drift
whatever the unmatched bins would have added:

```python
strict = runtime.execute("evaluation.gates", "psi_drift_gate_flat",
                         [reference, 100, abandoned, 100, 2, 0.20])["result"]
strict["psi_lower_bound"]   # 0.34657359027997264 — the same partial sum
strict["present"]           # False — still not an index
strict["decided"]           # True
strict["drifted"]           # True
```

Quantile bins are deliberately not offered for drift. A PSI is a comparison against a fixed
partition; edges derived from one of the two datasets would make the index depend on which one
you called the reference.

## Every refusal is typed, and none of them is a zero

Every function takes an explicit element count and validates it before forming any index. Send
a count larger than your list, a negative count, a probability of `3.0`, a label of `0.5`, a
`NaN`, zero bins, a negative seed, an alpha outside `(0, 1)`, or a bootstrap whose replicate
count multiplied by your sample count would run for minutes, and you get a status code naming
what was wrong. You never get a metric.

| Status | Name | What it means |
| --- | --- | --- |
| 360 | `ok` | the result is present |
| 361 | `empty_input` | an evaluation set of zero samples has no metrics |
| 362 | `count_exceeds_predictions` | the count is larger than the prediction list, or negative |
| 363 | `count_exceeds_labels` | the count is larger than the label list |
| 364 | `non_finite_value` | a `NaN` or infinity in the predictions, labels or a threshold — or two finite gate values whose difference is not representable |
| 365 | `probability_out_of_range` | a prediction outside `[0, 1]` — refused, not clipped |
| 366 | `label_not_binary` | a label that is not exactly `0.0` or `1.0` |
| 367 | `invalid_bin_count` | zero, negative, or above the bin ceiling |
| 368 | `unknown_bin_policy` | not equal-width (`0`) or equal-count (`1`) |
| 369 | `unknown_metric` | a metric id outside the vocabulary, or base rate as a gate subject |
| 370 | `alpha_out_of_range` | a bootstrap alpha outside the open interval `(0, 1)` |
| 371 | `invalid_resample_count` | zero, negative, above the replicate ceiling, or too few replicates to resolve your alpha's tails — `n_boot_min` says how many |
| 372 | `negative_seed` | refused rather than reinterpreted, so your record reproduces the run |
| 373 | `work_budget_exceeded` | replicates times samples would run far longer than you expect |
| 374 | `dimension_too_large` | above the per-call sample ceiling |
| 375 | `invalid_tolerance` | a gate tolerance that is negative or non-finite |
| 376 | `psi_incomplete_lower_bound_only` | a bin one distribution does not occupy; a lower bound, not an index |
| 377 | `no_occupied_bins` | an internal invariant guard — see below |
| 378 | `incomparable_binning` | an internal invariant guard — see below |
| 379 | `invalid_threshold` | a drift threshold that is negative or non-finite |

Two of those are worth being precise about. `no_occupied_bins` and `incomparable_binning` are
invariant guards, not outcomes you can provoke: every accepted sample lands in some bin, so a
partition of a non-empty request always has at least one occupied bin, and a regression gate
applies one bin count and one policy to both sides so their provenances cannot disagree. Both
checks are made anyway — a result that claims a property should verify it rather than assume
it — but if you ever see either code, the report is telling you something is wrong inside the
engine, not something wrong with your request. Every other code in the table is reachable from
a request you can write.

`evaluation.contract` exposes the checks on their own, so a request can be validated before it
is sent and a status integer can be turned back into a name:

```python
runtime.execute("evaluation.contract", "eval_pairs_status",
                [[0.2, 0.4], [0.0, 1.0], 25])["result"]        # 362
runtime.execute("evaluation.contract", "eval_status_name", [362])["result"]
# 'count_exceeds_predictions'
runtime.execute("evaluation.contract", "eval_bins_status", [0, 0])["result"]   # 367
```

A probability outside `[0, 1]` is refused rather than clipped on purpose. Clipping turns a unit
confusion — percentages, logits, a score that was never a probability — into a plausible
metric, and every metric on this page is defined only on `[0, 1]`.

{% hint style="info" %}
**A refused request returns empty lists and absent flags, never zeros.** A reliability diagram
that was refused has no bins, not five bins of zero. A calibration error that could not be
computed has `present == False`, and its `ece` field holds `0.0` only because a numeric field
must hold a number. Test the flag, then read the value.
{% endhint %}

## What is bounded, and why the bootstrap has its own budget

Two ceilings are independent because they bound different things. The sample count is bounded
by memory. The bootstrap is bounded by *work*: replicates and samples are each comfortably
inside their own limits at values whose product is not reachable in an afternoon, and a request
that hangs is indistinguishable, from where you are sitting, from one that failed.

So `bootstrap_metric_ci_flat` charges every factor of that product before drawing anything:
replicates times samples, times the extra logarithmic factor a quantile-binned calibration
error's sort costs per replicate, plus the bin count — because a bootstrapped calibration error
rebuilds the whole partition inside *every* replicate, which makes a large bin count as
expensive as a large sample count. A budget that counts three factors of a product out of four
fails in the same way as one that counts none; it is only harder to notice.

What the budget promises is that two requests it rates the same cost comparable time. It does
not promise a latency: a request sitting exactly at the ceiling is a serious amount of work. If
you need a deadline rather than a guarantee of termination, size the request yourself.

The refusal is cheap. A rejected `8192 × 2^20` request returns in less time than the smallest
legal run of the same shape takes to start.

## Related pages

* [Probability calibration](ml-calibration.md) — isotonic and Platt recalibration, for when
  this page tells you the predictions are miscalibrated
* [Conformal prediction intervals](ml-conformal.md) — distribution-free coverage guarantees
* [Statistical model comparison](ml-model-comparison.md) — paired tests between two models
* [Runtime library catalog](runtime-library-catalog.md) — every module and function
  on quantities that are not model metrics
* [Declared capabilities](capabilities.md) — how determinism, seeding and count handling are
  declared for every kernel
