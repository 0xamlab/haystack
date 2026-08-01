"""
causal_inference — a causal estimate that refuses to exist unless it is identified. Zero Python.

Named `causal_inference` and not `causal` because `mojo/engine/causal.mojo` already occupies
that top-level name and is FROZEN.

What the tree has today, and why it is not enough
-------------------------------------------------
`causal.mojo` is the whole causal surface: `ate`, `att`, `propensity_score`, `ipw_estimate`,
`diff_in_diff`, `regression_discontinuity`, `iv_estimate`, `stratified_ate`, `cohens_d`,
`needed_sample_size_ate`. Every one of them returns a bare `Float64`, and that is the defect —
not the arithmetic, which is mostly right, but the fact that the return type has no room to say
anything about whether the number means what its name says:

* `ate(treated, control)` is `mean(treated) - mean(control)`. It is the average treatment
  effect exactly when treatment was randomised, and it is a difference in group means
  otherwise. Nothing at the call site distinguishes those two situations, because nothing in
  the signature can carry a confounding structure. There is no DAG anywhere in the tree.
* `propensity_score(features, treatment)` does not use `treatment` at all — it standardises
  ONE feature and pushes it through a logistic curve, `p = sigmoid((x - mean) / sd)`. That is
  not a propensity model; it is a monotone rescaling of a covariate that happens to land in
  (0, 1), and the treatment vector it accepts is discarded. Its output is then clamped into
  [0.01, 0.99], so a unit with no chance of treatment is silently given one in a hundred.
* `ipw_estimate` clamps again, inside the weighting loop, and reads `treatment[i] == 1` with
  everything else pooled into control — so a three-arm design returns a number. It divides by
  `p` with no report of how extreme the weights got, and an ATE resting on three units with
  weight 400 is indistinguishable in the return value from one resting on ten thousand.
* `diff_in_diff` takes four pre-aggregated vectors, so parallel trends — the assumption the
  whole design rests on — cannot even be looked at, let alone reported.
* `stratified_ate` indexes `strata[i]` with no range check, silently DROPS any stratum missing
  an arm, and reports the survivors' weighted average as if it covered the sample. The weights
  are stratum size over TOTAL size, so dropping strata makes the weights sum to less than one
  and biases the result toward zero without saying so.
* `regression_discontinuity` returns `0.0` when one side of the cutoff is empty, which is also
  a perfectly ordinary real answer.

There is no d-separation, no backdoor criterion, no overlap diagnostic, no doubly-robust
estimator, no synthetic control, no uplift curve and no sensitivity analysis anywhere in the
tree. The frozen kernels stay reachable and unchanged; this package is what a caller uses when
the number has to survive being asked "how do you know?".

Modules
-------
  base — the package's one status vocabulary (340-359, all twenty spent), one finiteness test,
        one rounding-tolerance builder sized by `DBL_EPSILON x the judged quantity's own
        magnitude`, the allocation ceilings with their per-unit array arithmetic, the
        non-wrapping work-budget primitives, and the stable index sorts that no frozen kernel
        provides (`sorting.mojo` returns sorted VALUES and no permutation).
  dag — identification as a precondition. `dag_validate` decides acyclicity with the frozen
        `graph.algorithms.topological_sort` and, when it fails, NAMES AN EDGE ON THE CYCLE.
        `d_separated` is Bayes-Ball (two linear passes, never path enumeration) and returns a
        WITNESS PATH when the answer is "not separated". `backdoor_check` enforces both halves
        of Pearl's criterion — no adjustment node downstream of the treatment, and every
        backdoor path blocked — and a failure is `CI_ERR_NOT_IDENTIFIED` carrying the open
        path, never an estimate. `backdoor_minimal_set` shrinks a candidate pool with
        minimality MEASURED one member at a time.
  propensity — a real propensity model (the frozen `linear_models.logistic_fit`, L2 Newton/IRLS,
        called unchanged) with the diagnostics that decide whether its output can be used:
        common support, the extreme-weight count, and Kish's effective sample size, so an ATE
        resting on three units says so. `ipw_ate` reports the Horvitz-Thompson AND Hajek forms
        side by side, refuses a propensity of exactly 0 or 1 for a unit that needs it rather
        than clamping it, and TRIMS ONLY WHEN ASKED. Caliper matching reports how many units
        found no partner, and optimal matching is the frozen Hungarian from
        `optimization.assignment`.
  estimators — outcome regression per arm over the frozen `linear_models.elasticnet_fit`, the
        augmented-IPW doubly-robust estimator with its influence-function standard error, and a
        stratified estimator that reports the strata it could not use instead of quietly
        dropping them. The double-robustness property is asserted as an EXACT identity in both
        directions, which is the only reason the estimator is worth having.
  panel — difference-in-differences over a real panel, reporting the PRE-TREATMENT TREND
        DIFFERENCE so a caller can judge parallel trends, and absent rather than zero when
        there is only one pre-period to judge it from. Synthetic control by Frank-Wolfe over
        the simplex with an exact line search — deterministic, no RNG — reporting the
        pre-period fit that is the only evidence the weights are worth anything.
  sensitivity — how strong an unmeasured confounder would have to be: VanderWeele's E-value,
        Cinelli-Hazlett robustness values and bias-adjusted estimates, and the partial R^2 a
        confounder needs to explain the result away. Quantities, not reassurances.
  uplift — heterogeneous effects by score decile, the Qini curve and its coefficient, with a
        bin whose treated or control arm is empty reported ABSENT rather than as an uplift of
        zero.

Design rules the package keeps
------------------------------
*Identification is a precondition, not a caveat.* If the requested effect is not identified
from the declared DAG under the backdoor criterion, the answer is a refusal naming the
unblocked path. Nothing here estimates an effect it was not able to identify.

*An assumption is reported, never verified.* Parallel trends is an assumption; `panel` reports
the pre-treatment trend difference and nothing in the result claims the assumption holds.
Overlap is checkable, so it is checked and reported. Trimming changes the estimand, so it is
the caller's decision and never a silent default.

*An answer that does not exist is absent, not zero, and never NaN.* A non-finite Float64 on the
result path ENDS THE WORKER PROCESS (measured, and recorded in `stats.compute_mean`'s own
docstring), so absence is a `has_*` Bool beside a finite number.

Public functions take and return only `List`/`Int`/`Float64`/`Bool`/`String` or a return-only
struct declared in the same file, so the package lands in the runtime library contract without
a new message type. It is therefore *not* in `_SKIP_RUNTIME_DIRS`.
"""
