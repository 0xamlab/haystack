---
icon: sitemap
description: Identification first — d-separation and the backdoor criterion on a declared graph — then IPW, matching, doubly-robust and panel estimation, and sensitivity analysis, refusing when not identified.
---

# Causal inference

Seven kernel families for the question "did it cause that", built so that the estimate refuses
to exist unless it is identified. All run as compiled kernels inside the runtime that ships with
the SDK — there is nothing to start and nothing to install separately.

An unadjusted difference in group means is a causal effect exactly when no backdoor path is
open, and a regression coefficient wearing a causal name otherwise. Nothing in the arithmetic
distinguishes those two situations, so the distinction is made explicitly, first, against a
graph you declare:

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# nodes: 0 = treatment T, 1 = outcome Y, 2 = confounder U
# edges: U -> T,  U -> Y,  T -> Y
edge_from, edge_to = [2, 2, 0], [0, 1, 1]

unadjusted = runtime.execute("causal_inference.dag", "backdoor_check",
                             [edge_from, edge_to, 3, 0, 1, []])["result"]

unadjusted["identified"]        # False
unadjusted["unblocked_path"]    # [0, 2, 1] — T <- U -> Y, the path that is open
unadjusted["status"]            # 347 — "effect_not_identified"

adjusted = runtime.execute("causal_inference.dag", "backdoor_check",
                           [edge_from, edge_to, 3, 0, 1, [2]])["result"]

adjusted["identified"]                  # True
adjusted["blocks_backdoor_paths"]       # True
adjusted["n_descendant_violations"]     # 0
adjusted["n_adjustment"]                # 1
```

A boolean `False` is not actionable. The path `T <- U -> Y` is: it names the variable you have
to measure, or the design you have to change.

## The modules

| Module | What it does |
| --- | --- |
| `causal_inference.dag` | identification as a precondition — acyclicity with a named cycle edge, d-separation with a witness path, the backdoor criterion with the open path, and a minimal sufficient adjustment set with minimality measured |
| `causal_inference.propensity` | a real propensity model over many covariates, the diagnostics that decide whether its output can be used (common support, extreme weights, effective sample size), IPW in both Horvitz-Thompson and Hájek forms, and caliper or optimal matching |
| `propensity` | the pre-`causal_inference` propensity-score toolkit -- single-pass logistic scores, nearest-neighbor and caliper matching, matched-pair ATE, standardized-mean-difference balance checks, overlap and trimming, and stratified ATE by propensity strata |
| `causal_inference.estimators` | per-arm outcome regression, the augmented-IPW doubly-robust estimator with its influence-function standard error and a decomposition that must add up, a stratified estimator that reports the strata it could not use, and a deterministic bootstrap interval |
| `causal_inference.panel` | difference-in-differences over a real panel, reporting the pre-treatment trend difference so you can judge parallel trends, and synthetic control with the pre-period fit that is the only evidence the weights are worth anything |
| `causal_inference.sensitivity` | how strong an unmeasured confounder would have to be — E-values, robustness values, bias-adjusted estimates and the partial R² needed to explain a result away, plus a Rosenbaum bound for matched pairs |
| `causal_inference.uplift` | heterogeneous effects by score bin and the Qini curve, with a bin whose treated or control arm is empty reported absent rather than as an uplift of zero |
| `causal_inference.base` | the package's one status vocabulary, its finiteness test, its rounding-tolerance builder, non-wrapping work budgets and stable index sorts |

{% hint style="warning" %}
**Identification is a separate call, and no estimator makes it for you.** Nothing in
`estimators`, `propensity`, `panel` or `uplift` takes an identification verdict as an argument,
looks at your graph, or checks a backdoor criterion — those surfaces validate their own
preconditions (overlap, arm counts, finiteness, work) and nothing more. Run `backdoor_check`
or `d_separated` yourself, on the graph you are willing to defend, before you quote any number
from the rest of this page as an effect.
{% endhint %}

## A cycle in the declared graph names an edge

"Your graph is invalid" is a bug report with no address, so a cyclic graph comes back with one
of the offending edges:

```python
# 0 -> 1 and 1 -> 0, plus a pendant 1 -> 2
r = runtime.execute("causal_inference.dag", "dag_validate",
                    [[0, 1, 1], [1, 2, 0], 3])["result"]

r["status"]        # 345 — "graph_is_not_acyclic"
r["is_dag"]        # False
r["cycle_from"]    # 0
r["cycle_to"]      # 1
r["has_order"]     # False
r["topo_order"]    # [] — a partial order is not an order

# a self loop is named as itself
runtime.execute("causal_inference.dag", "dag_validate", [[0], [0], 1])["result"]
# cycle_from 0, cycle_to 0, n_self_loops 1

# the acyclic graph from the first example
ok = runtime.execute("causal_inference.dag", "dag_validate",
                     [[2, 2, 0], [0, 1, 1], 3])["result"]
ok["is_dag"]        # True
ok["topo_order"]    # [2, 0, 1]
```

Node ids are `0..n_nodes-1` and carry no names — you already have your own labels, and a name
per node would cross the wire for no analytic content. Every edge endpoint is range-checked
before anything is built, so an out-of-range node is `node_index_out_of_range` rather than a
crash.

## d-separation answers in both directions, and shows its work

```python
# a chain 0 -> 1 -> 2
r = runtime.execute("causal_inference.dag", "d_separated",
                    [[0, 1], [1, 2], 3, [0], [2], []])["result"]
r["separated"]     # False
r["path_nodes"]    # [0, 1, 2] — the open path, as data

r = runtime.execute("causal_inference.dag", "d_separated",
                    [[0, 1], [1, 2], 3, [0], [2], [1]])["result"]
r["separated"]     # True
r["path_nodes"]    # [] — nothing is open, so there is nothing to show

# a collider 0 -> 1 <- 2 behaves the other way round
runtime.execute("causal_inference.dag", "d_separated",
                [[0, 2], [1, 1], 3, [0], [2], []])["result"]["separated"]    # True
runtime.execute("causal_inference.dag", "d_separated",
                [[0, 2], [1, 1], 3, [0], [2], [1]])["result"]["separated"]   # False
```

Conditioning on a collider **opens** a path that was closed — the classic way an adjustment set
introduces the bias it was meant to remove. The test is two linear passes over node-direction
states rather than an enumeration of paths, so it is cheap on a graph where the number of paths
is exponential.

An adjustment set containing a descendant of the treatment is refused for the same reason, and
the offending node is named:

```python
# 2 = U, 3 = M with T -> M -> Y: M is a mediator, not a confounder
r = runtime.execute("causal_inference.dag", "backdoor_check",
                    [[2, 2, 0, 3], [0, 1, 3, 1], 4, 0, 1, [2, 3]])["result"]
r["identified"]                 # False
r["n_descendant_violations"]    # 1
r["first_descendant"]           # 3

r = runtime.execute("causal_inference.dag", "backdoor_minimal_set",
                    [[2, 2, 0, 3], [0, 1, 3, 1], 4, 0, 1, [2, 3]])["result"]
r["chosen"]                     # [2] — the mediator is dropped
r["n_dropped_descendant"]       # 1
r["minimality_measured"]        # True — one re-check per member, not inferred
r["n_checks"]                   # 2
```

`identified = True` asserts **both** halves of the backdoor criterion — no adjustment node
downstream of the treatment, and every backdoor path blocked. A certificate that omits a
condition is worse than no certificate, because you stop looking, so the scope is stated and
the two halves are separate fields.

## No common support means no estimate

Common support is the intersection of the two arms' propensity score ranges. When it is empty,
no treated unit has a control at a comparable propensity and no control has a treated one — a
weighted contrast between the arms is extrapolation, not an effect:

```python
treatment = [1, 1, 1, 0, 0, 0]
outcomes = [12.0, 11.0, 13.0, 4.0, 5.0, 6.0]
scores = [0.7, 0.8, 0.9, 0.1, 0.2, 0.3]      # the arms do not overlap at all

r = runtime.execute("causal_inference.propensity", "ipw_ate",
                    [outcomes, treatment, scores, 0.0, 10.0])["result"]

r["status"]          # 350 — "no_common_support"
r["has_estimate"]    # False
r["ate_ht"]          # 0.0 — padding, and only meaningful when has_estimate is True

d = runtime.execute("causal_inference.propensity", "overlap_report",
                    [scores, treatment, 0.05])["result"]
d["has_support"]           # False
d["support_lo"]            # 0.7
d["support_hi"]            # 0.3 — an empty interval, reported as one
d["overlap_fraction"]      # 0.0
d["n_treated_outside"]     # 3
d["n_control_outside"]     # 3
```

The number that was refused is arithmetically well defined and every weight in it is finite.
That is exactly why it has to be refused: nothing in the value would have told you there was no
region where both outcomes were observable. Thin overlap is **not** refused — that is what
`overlap_fraction` and the four per-arm extremes are for. Only the empty case is, because it is
the one no diagnostic can rescue.

With overlapping scores the same call answers, and reports how hard the weights are working:

```python
scores = [0.4, 0.6, 0.8, 0.2, 0.5, 0.7]

r = runtime.execute("causal_inference.propensity", "ipw_ate",
                    [outcomes, treatment, scores, 0.0, 10.0])["result"]

r["ate_ht"]         # 4.930555555555557  Horvitz-Thompson
r["ate_hajek"]      # 6.606621226874392  Hájek — both, because they answer differently
r["max_weight"]     # 3.333333333333333
r["ess_treated"]    # 2.7704918032786887 out of 3 units
r["ess_control"]    # 2.599333610995419
r["n_extreme"]      # 0 — how many weights passed the threshold you set
```

Kish's effective sample size is the number that stops an estimate being quoted: an ATE built on
three observations with weight 400 has an ESS near 3, and nobody who is told that will quote it.

{% hint style="danger" %}
**A propensity of exactly 0 for a treated unit is not clamped.** It is a statement that the
unit could not have received the treatment it received, and `1/0` is not a weight, so the
answer is `propensity_at_zero_or_one` with no estimate. Clamping into `[0.01, 0.99]` — the
common shortcut — converts an impossible unit into a hundred units of influence and hides the
single most important thing a propensity analysis can discover.

Trimming is available and never automatic, because it changes the estimand: the ATE over the
trimmed region is a different quantity from the ATE over your sample. Measured on the same six
units with one score at exactly 0.0, `trim_eps = 0.05` answers with `n_trimmed = 1`,
`n_used = 5` and a Hájek estimate of 6.540687160940324 against the untrimmed 6.606621226874392
— a different number for a different question, and the count is always reported.
{% endhint %}

## The estimators report the identity they must satisfy

The doubly-robust estimator is consistent if **either** the outcome model or the propensity
model is right, and the reason to prefer it is a property you can check exactly rather than an
asymptotic claim. When the outcome model reproduces the observed outcomes, both correction
terms are exactly zero and the doubly-robust estimate collapses to the outcome-regression one,
bit for bit:

```python
mu0 = [0.0, 0.0, 0.0, 4.0, 5.0, 6.0]     # predicted control outcome per unit
mu1 = [12.0, 11.0, 13.0, 0.0, 0.0, 0.0]  # predicted treated outcome per unit

r = runtime.execute("causal_inference.estimators", "aipw_ate", [
    outcomes, treatment, scores, mu0, mu1,
    0.0, 10.0, 1.96,        # trim_eps, extreme-weight threshold, z for the interval
])["result"]

r["ate"]                        # 3.5
r["ate_regression"]             # 3.5
r["ate_correction"]             # 0.0
r["decomposition_residual"]     # 0.0 — the parts and the whole agree
r["se"]                         # 3.8188130791298667 from the influence function
r["ci_lo"], r["ci_hi"]          # -3.984873635094538, 10.984873635094537
```

`decomposition_residual` is reported on every call, not only on the exact case: the estimate
minus its regression part minus its correction part is zero by construction, so a nonzero value
means the parts and the whole disagree and you can use neither.

The same discipline applies to the weighted contrast. With a constant propensity the Hájek
estimate must equal the plain difference in arm means exactly, because the weights cancel arm by
arm — and it does:

```python
half = [0.5] * 6
w = runtime.execute("causal_inference.propensity", "ipw_ate",
                    [outcomes, treatment, half, 0.0, 10.0])["result"]
n = runtime.execute("causal_inference.estimators", "naive_ate",
                    [outcomes, treatment])["result"]

w["ate_hajek"], n["diff"]    # 7.0, 7.0 — equal, not approximately equal
n["se"]                      # 0.816496580927726
```

## A stratum that cannot be used is reported, not dropped

```python
strata = [0, 0, 0, 0, 1, 1]          # stratum 1 contains treated units only
treatment = [1, 1, 0, 0, 1, 1]

r = runtime.execute("causal_inference.estimators", "strata_ate",
                    [outcomes, treatment, strata, 2])["result"]

r["n_strata"]                 # 2
r["n_usable"]                 # 1 — stratum 1 has no control arm
r["n_covered"]                # 4 of 6 units
r["covered_fraction"]         # 0.6666666666666666
r["is_full_sample"]           # False — the headline number is NOT the sample ATE
r["ate"]                      # 7.0 over the covered part, reweighted to it
r["ate_uncovered_as_zero"]    # 4.666666666666667 — what the naive version reports
r["stratum_has_ate"]          # [True, False]
```

Both numbers are returned because the difference between them is the bias: weighting by
stratum size over the **total** size makes the weights sum to less than one when a stratum is
missing an arm, which drags the estimate toward zero without saying so. `is_full_sample` is the
flag to branch on. When no stratum has both arms at all the answer is `no_control_units` or
`no_treated_units` with no estimate.

## An assumption is reported, never verified

Parallel trends is an assumption, not a checkable condition, so difference-in-differences
reports the evidence and claims nothing:

```python
# 2 units x 4 periods, row-major; unit 0 is treated from period 2
panel = [1.0, 2.0, 6.0, 7.0,
         1.0, 2.0, 3.0, 4.0]

r = runtime.execute("causal_inference.panel", "did_panel",
                    [panel, 2, 4, [1, 0], 2])["result"]

r["att"]                # 3.0
r["has_pre_trend"]      # True
r["pre_trend_diff"]     # 0.0 — the pre-treatment gap was not moving
r["n_pre"], r["n_post"] # 2, 2

# the same design with a single pre-period
r = runtime.execute("causal_inference.panel", "did_panel",
                    [[1.0, 6.0, 1.0, 3.0], 2, 2, [1, 0], 1])["result"]
r["att"]                # 3.0 — still computable
r["has_pre_trend"]      # False — one pre-period cannot exhibit a trend
```

A trend needs two points. Reporting `pre_trend_diff = 0.0` for a single pre-period would be a
claim of parallel trends made out of nothing, so the flag is False and the number beside it is
padding.

Synthetic control reports the same way from the other side. Its weights are found by iteration
over the simplex, and an iteration that stopped early has no weights — not an arbitrary convex
combination of donors:

```python
# 3 units x 6 periods, row-major; unit 0 is treated from period 4 and its path
# is nothing like the two donors'
donors = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0]
treated = [100.0 + 7.0 * t * t + (50.0 if t >= 4 else 0.0) for t in range(6)]
wide_panel = treated + donors

r = runtime.execute("causal_inference.panel", "synthetic_control",
                    [wide_panel, 3, 6, 0, 4, 1, 1e-9])["result"]   # max_iter = 1
r["status"]          # 352 — "fit_did_not_converge"
r["converged"]       # False
r["has_effect"]      # False
r["weights"]         # []
r["fw_gap"]          # 4320.0 — how far from a stationary point it stopped

r = runtime.execute("causal_inference.panel", "synthetic_control",
                    [wide_panel, 3, 6, 0, 4, 64, 1e-9])["result"]
r["converged"]       # True
r["n_iter"]          # 2
r["sum_weights"]     # 1.0 — a convex combination, by construction
r["pre_rmse"]        # 105.63143471523995
```

That last number is the point of reporting it. The weights converged and the pre-period fit is
still terrible, because these donors cannot reproduce this treated unit — and the effect is
only as good as that fit. It comes back beside the effect rather than being left for you to
recompute.

## Matching says how many units found no partner

```python
outcomes, treatment = [12.0, 11.0, 4.0, 5.0], [1, 1, 0, 0]
scores = [0.80, 0.82, 0.20, 0.25]

r = runtime.execute("causal_inference.propensity", "match_nearest",
                    [outcomes, treatment, scores, 0.05, False])["result"]
r["status"]          # 355 — "no_unit_matched_within_caliper"
r["has_estimate"]    # False

r = runtime.execute("causal_inference.propensity", "match_nearest",
                    [outcomes, treatment, scores, 0.9, False])["result"]
r["att"]                  # 7.0
r["n_matched"]            # 2
r["n_unmatched"]          # 0
r["matched_fraction"]     # 1.0
r["is_full_sample"]       # True — every treated unit found a partner
r["total_gap"]            # 1.17 — the propensity distance the matching had to accept
r["max_gap"]              # 0.6199999999999999
```

A caliper nobody satisfies is a refusal, not an empty average. When some treated units match
and others do not, `is_full_sample` is False and `matched_fraction` says how much of the
treated arm the ATT actually covers — the estimand has changed, and the report says so.
`match_optimal` solves the same problem to optimality (measured `total_gap` 1.17 here, never
worse than the greedy pass) and treats a forbidden pairing as a boolean rather than a large
cost, so an impossible match cannot become choosable.

Uplift keeps the rule at bin level:

```python
scores = [0.9, 0.8, 0.7, 0.6, 0.4, 0.3, 0.2, 0.1]
treated = [1, 1, 1, 1, 1, 0, 0, 0]
converted = [1.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 0.0]

r = runtime.execute("causal_inference.uplift", "uplift_by_bin",
                    [scores, treated, converted, 2])["result"]

r["n_bins_absent"]        # 1
r["bin_n_control"]        # [0, 3] — the top bin has no control arm
r["bin_has_uplift"]       # [False, True]
r["bin_uplift"]           # [0.0, -0.3333333333333333]
```

An uplift of zero is a real, ordinary answer — it means the treatment did nothing in that bin.
So it cannot double as "this bin had nobody to compare against", and the top bin here is
absent rather than flat.

## Sensitivity gives you quantities, not reassurances

`sensitivity` answers the question that follows every observational estimate: how strong would
an unmeasured confounder have to be to explain this away?

```python
r = runtime.execute("causal_inference.sensitivity", "e_value_ratio", [2.0])["result"]
r["evalue"]         # 3.414213562373095 — the confounder association, on both arms,
                    # that would move a risk ratio of 2.0 to the null
r["rr_oriented"]    # 2.0
r["inverted"]       # False — a ratio below 1 is oriented before the bound is formed

runtime.execute("causal_inference.sensitivity", "e_value_ratio", [1.0])["result"]["evalue"]
# 1.0 — an estimate already at the null needs no confounding at all
```

E-values put the question on the risk-ratio scale; robustness values put it on the partial-R²
scale; `omitted_variable_bias` reports the bias-adjusted estimate and whether it flips sign;
`sensitivity_curve` sweeps a grid of confounder strengths and names the first one that flips it;
and `rosenbaum_sign_bound` does the matched-pair version, with `rosenbaum_gamma_needed`
inverting it. Every one is a number with a presence flag, because "no answer exists for this
input" and "the answer is zero" are opposite outcomes — an out-of-range argument such as a
non-positive sensitivity parameter is `invalid_parameter` with the value absent, not a bound
computed from it.

## Every refusal names itself

One status vocabulary covers the package and `ci_status_name` turns any code into a name:
`graph_is_not_acyclic`, `node_index_out_of_range`, `effect_not_identified`,
`no_common_support`, `propensity_at_zero_or_one`, `no_treated_units`, `no_control_units`,
`treatment_not_binary`, `no_unit_matched_within_caliper`, `fit_did_not_converge`,
`singular_design`, `insufficient_data`, `duplicate_or_overlapping_node`,
`work_budget_exceeded`, `invalid_parameter`.

A three-arm design is `treatment_not_binary` rather than silently pooling everything that is
not 1 into control. A stratum label out of range is refused rather than indexed. Every estimate
sits beside a `has_*` flag, and where that flag is `False` the number next to it is padding and
not a claim.

## See also

* [Statistical inference](statistical-inference.md) — p-values with their assumptions, and verified sample sizes
* [Forecasting and backtesting](forecasting.md) — out-of-sample measurement and prediction bands
* [Optimization & decision programs](optimization.md) — kernels that report when no answer exists
* [Sparse systems & graph analytics](sparse-and-graph.md) — the graph surface these DAG checks build on
* [Declared capabilities](capabilities.md) — what each kernel says about determinism, seeds and cost
* [Runtime library catalog](runtime-library-catalog.md) — every module and function
