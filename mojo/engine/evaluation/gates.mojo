"""
evaluation.gates — regression and drift gates that can actually FAIL. Zero Python imports.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int, bool
backend: mojo
surfaces: library_execute, batch_execute
complexity: O(n log n + h)
golden_vectors: mojo/tests/libs/test_evaluation_gates.mojo
benchmark: benchmarks/mojo_benchmarks/bench_evaluation.mojo
docs: gitbook/engine/evaluation-calibration.md
version_introduced: unreleased
deprecation_state: active
@endcapability

A gate that has never been shown to fail is decoration
------------------------------------------------------
Both gates here have a constructed failing case in
`mojo/tests/libs/test_evaluation_gates.mojo` and in
`benchmarks/mojo_benchmarks/bench_evaluation.mojo`, asserted to FAIL, alongside the passing
case. A gate is a claim about rejection; a test that only ever exercises acceptance proves
the opposite of what it appears to prove.

`decided` is separate from `passed`
----------------------------------
Three outcomes exist, not two: pass, fail, and "this comparison cannot be made". A gate that
collapses the third into either of the first two either blocks a release for a reason that
does not exist or lets one through unexamined. So `decided` says whether a verdict was
reached and `passed` is meaningless unless it is True. Every refusal returns
`decided == False` with a status naming the reason.

The direction belongs to the metric
-----------------------------------
`eval_metric_higher_is_better(metric_id)` owns whether a decrease is a regression. A gate
parameterised on the direction is a gate that will eventually be told a lower Brier score is
a regression. `base_rate` has no better direction — it is a property of the labels, not of
the model — so gating on it is refused rather than silently treated as lower-is-better.

Comparing two ECEs across two binnings is refused
-------------------------------------------------
`metric_regression_gate_flat` takes ONE `n_bins` and ONE `policy` and applies them to both
sides, so incomparable binnings are unrepresentable rather than merely discouraged. When a
caller supplies the two provenances itself, `eval_ece_comparable` is the predicate and
`EVAL_ERR_INCOMPARABLE_BINNING` is the refusal.

The float slop is derived from the difference and from nothing else
------------------------------------------------------------------
The quantity being judged is `delta = candidate - baseline`. IEEE subtraction is correct to
within half an ulp of its own result, so the representation slop is
`EVAL_DBL_EPSILON * |delta|`. It is NOT `eps * (|baseline| + |candidate|)`, not
`eps * max(...)`, not `1 + |delta|` (whose 1.0 floor would silently permit a whole unit of
regression), and the caller's `abs_tolerance` is never multiplied by a magnitude — that
tolerance is a business threshold in the metric's own units and is used exactly as given.

The consequence, stated because it WILL be met: the comparison is exact on the values as
represented, and a decimal "tie" is usually not a tie. Measured:
`metric_gate(0.09, 0.10, 0.01, higher_is_better=False)` FAILS, because
`fl(0.10) - fl(0.09)` is 0.010000000000000009 and exceeds `fl(0.01)` by 8.67e-18 — five ulps,
carried in by the two operands' own decimal-to-binary conversion, not introduced here.
`margin` reports exactly that number, so a build log shows a rejection of -8.67e-18 rather
than an unexplained failure. A tie that IS exact in binary passes:
`metric_gate(0.25, 0.5, 0.25, False)` has `delta == 0.25 == abs_tolerance` and passes.

Widening the slop to `eps * (|baseline| + |candidate| + abs_tolerance)` would absorb that
case, and is rejected: it is a tolerance built from an aggregate over quantities other than
the one being judged, which is the family of defect that let an infeasible program report
`LP_OPTIMAL` elsewhere in this tree. A gate with no hidden slack is reproducible; a gate with
a little is a gate whose threshold nobody can state.

PSI: an incomplete index is reported as a LOWER BOUND, not as a number
---------------------------------------------------------------------
The frozen `evaluation_feedback.population_stability_index` returns 0.0 for a bin where
either proportion is zero. That is the correct local decision — the term is `+inf` there and
an infinity cannot travel — but summing over it produces an index that UNDERSTATES drift
exactly when the drift is most extreme: a bin the reference never populated and the candidate
now fills is infinite drift, contributing nothing.

So this driver counts those bins. With any unmatched bin the sum is only a lower bound,
`present` is False and the status is `EVAL_ERR_PSI_INCOMPLETE`. A lower bound above the
threshold is still a decision — drift is confirmed — so `decided` stays True in that case
and False otherwise. That distinction is the whole value of the wrapper.

Public API:
  GateResult                        — pass/fail/undecided with the margin
  DriftResult                       — PSI, its completeness, and the verdict
  metric_gate(...)                  — two scalars and a tolerance
  metric_regression_gate_flat(...)  — two datasets, one metric, one binning
  psi_drift_gate_flat(...)          — reference vs candidate score distributions
"""

from std.math import abs as fabs

from evaluation_feedback import population_stability_index

from evaluation.binning import eval_bin_counts_flat
from evaluation.contract import (
    EVAL_BIN_EQUAL_WIDTH,
    EVAL_DBL_EPSILON,
    EVAL_ERR_INCOMPARABLE_BINNING,
    EVAL_ERR_NON_FINITE,
    EVAL_ERR_NO_OCCUPIED_BINS,
    EVAL_ERR_PSI_INCOMPLETE,
    EVAL_ERR_THRESHOLD,
    EVAL_ERR_TOLERANCE,
    EVAL_ERR_UNKNOWN_METRIC,
    EVAL_METRIC_BASE_RATE,
    EVAL_METRIC_ECE,
    EVAL_OK,
    eval_bins_status,
    eval_finite,
    eval_metric_higher_is_better,
    eval_scores_status,
)
from evaluation.scores import metric_value_flat


struct GateResult(Copyable, Movable):
    """A gate verdict.

    `decided == False` means no verdict was reached; `passed` must be ignored, and `status`
    names why. `margin` is how much room was left: positive is slack, negative is the amount
    by which the tolerance was exceeded. It is 0.0 and meaningless when `decided` is False.
    """

    var status: Int
    var decided: Bool
    var passed: Bool
    var baseline: Float64
    var candidate: Float64
    var delta: Float64
    var margin: Float64
    var abs_tolerance: Float64
    var higher_is_better: Bool
    var metric_id: Int
    var bins_used: Int
    var bin_policy: Int

    fn __init__(out self, status: Int, metric_id: Int):
        self.status = status
        self.decided = False
        self.passed = False
        self.baseline = 0.0
        self.candidate = 0.0
        self.delta = 0.0
        self.margin = 0.0
        self.abs_tolerance = 0.0
        self.higher_is_better = False
        self.metric_id = metric_id
        self.bins_used = 0
        self.bin_policy = -1


struct DriftResult(Copyable, Movable):
    """A population-stability verdict over two score distributions.

    `present` is True only when every bin contributed a finite term, i.e. `bins_unmatched`
    is 0 — then `psi` is the index. Otherwise `psi` is 0.0 and not a measurement, and
    `psi_lower_bound` carries the partial sum, which is always finite and always a valid
    lower bound on the true index.

    `decided` is True when the verdict does not depend on the missing terms: either the index
    is complete, or the lower bound already exceeds the threshold.
    """

    var status: Int
    var present: Bool
    var psi: Float64
    var psi_lower_bound: Float64
    var threshold: Float64
    var decided: Bool
    var drifted: Bool
    var n_reference: Int
    var n_candidate: Int
    var bins_used: Int
    var bins_matched: Int
    var bins_unmatched: Int
    var bin_policy: Int

    fn __init__(
        out self, status: Int, n_reference: Int, n_candidate: Int, n_bins: Int
    ):
        self.status = status
        self.present = False
        self.psi = 0.0
        self.psi_lower_bound = 0.0
        self.threshold = 0.0
        self.decided = False
        self.drifted = False
        self.n_reference = n_reference
        self.n_candidate = n_candidate
        self.bins_used = n_bins
        self.bins_matched = 0
        self.bins_unmatched = 0
        self.bin_policy = EVAL_BIN_EQUAL_WIDTH


fn metric_gate(
    baseline: Float64, candidate: Float64, abs_tolerance: Float64,
    higher_is_better: Bool
) -> GateResult:
    """Gate two already-computed metric values against an absolute tolerance.

    `abs_tolerance` is how much movement in the WRONG direction is acceptable, in the
    metric's own units. It must be finite and non-negative; a negative tolerance is refused
    rather than clamped to zero, because a negative allowance is most likely a sign error in
    the caller and silently treating it as zero would make a stricter gate than was asked
    for while reporting success.

    The verdict:
      * `higher_is_better`: pass when `candidate - baseline >= -(abs_tolerance + slop)`
      * otherwise:          pass when `baseline - candidate >= -(abs_tolerance + slop)`

    with `slop = EVAL_DBL_EPSILON * |delta|` — the representation error of the subtraction
    itself, scaled by the magnitude of the quantity being judged and by nothing else. A tie
    that is exact in BINARY therefore passes; a decimal near-tie such as
    `(0.09, 0.10, 0.01)` fails by 8.67e-18 and `margin` says so. The module docstring gives
    the measurement and the reason the slop is not widened to hide it.

    `margin` is `abs_tolerance` minus the movement in the wrong direction: positive is slack,
    negative is the overshoot. It is the number to put in a build log.

    Three refusals, all `decided == False`:
      * either metric value non-finite — `EVAL_ERR_NON_FINITE`
      * `abs_tolerance` non-finite or negative — `EVAL_ERR_TOLERANCE`
      * `candidate - baseline` or the margin not REPRESENTABLE even though both operands are
        — also `EVAL_ERR_NON_FINITE`. See the comment on the guard: without it the largest
        regression representable PASSED a zero-tolerance gate, because an infinite slop
        satisfies every comparison.

    @capability metric_gate
    complexity: O(1)
    counts: none
    @endcapability
    """
    if not eval_finite(baseline) or not eval_finite(candidate):
        return GateResult(EVAL_ERR_NON_FINITE, -1)
    if not eval_finite(abs_tolerance) or abs_tolerance < 0.0:
        return GateResult(EVAL_ERR_TOLERANCE, -1)

    # Both operands are finite; their DIFFERENCE need not be. `candidate - baseline` for
    # `(-DBL_MAX, +DBL_MAX)` is `+inf`, and two things then go wrong at once:
    #
    #   * `delta` and `margin` are returned Float64 FIELDS. A raw non-finite in either makes
    #     the whole response a typed transport error rather than a verdict, because the
    #     dispatch refuses to serialise one — JSON has no infinity.
    #   * far worse, the verdict would be WRONG rather than merely absent. `slop` becomes
    #     `eps * inf == inf`, and `wrong_way <= abs_tolerance + inf` is True for EVERY
    #     tolerance — so the largest regression representable would PASS a gate whose
    #     tolerance is 0.0. Measured before this guard existed:
    #     `metric_gate(-DBL_MAX, DBL_MAX, 0.0, higher_is_better=False)` returned
    #     `passed == True`. A gate that cannot fail is not a gate.
    #
    # So the overflow is REFUSED, not answered: two values further apart than Float64 can
    # represent are not comparable at this precision, and `decided == False` says exactly
    # that. `test_evaluation_gates.mojo` asserts all three inputs below stay undecided.
    var delta = candidate - baseline
    if not eval_finite(delta):
        return GateResult(EVAL_ERR_NON_FINITE, -1)
    var wrong_way = -delta if higher_is_better else delta
    # `margin` overflows independently of `delta`: `(0.0, DBL_MAX, DBL_MAX, True)` has a
    # finite delta and a margin of `DBL_MAX - (-DBL_MAX) == +inf`. Checked on its own value
    # rather than inferred from delta's.
    var margin = abs_tolerance - wrong_way
    if not eval_finite(margin):
        return GateResult(EVAL_ERR_NON_FINITE, -1)

    var out = GateResult(EVAL_OK, -1)
    out.baseline = baseline
    out.candidate = candidate
    out.abs_tolerance = abs_tolerance
    out.higher_is_better = higher_is_better
    out.delta = delta
    out.margin = margin
    # `abs_tolerance + slop` may still round up to `+inf`, which requires `abs_tolerance`
    # itself to be within `slop` of DBL_MAX. `wrong_way <= |delta|` is finite by the guard
    # above, so `wrong_way <= abs_tolerance` already holds in every such case and True is the
    # correct answer, not a permissive one.
    var slop = EVAL_DBL_EPSILON * fabs(delta)
    out.passed = wrong_way <= abs_tolerance + slop
    out.decided = True
    return out^


fn metric_regression_gate_flat(
    base_probs: List[Float64], base_labels: List[Float64], n_base: Int,
    cand_probs: List[Float64], cand_labels: List[Float64], n_cand: Int,
    metric_id: Int, n_bins: Int, policy: Int, abs_tolerance: Float64
) -> GateResult:
    """Compute one metric on both datasets under ONE binning and gate the movement.

    The two evaluation sets may differ in size — a candidate is often scored on a fresh
    slice — but they share the metric, the bin count and the binning policy, which is what
    makes the two numbers comparable at all. Supplying them separately is the mechanism by
    which an "improved" ECE is usually manufactured, so it is not offered here.

    The direction comes from `eval_metric_higher_is_better(metric_id)` and not from the
    caller. `EVAL_METRIC_BASE_RATE` is refused with `EVAL_ERR_UNKNOWN_METRIC`: the positive
    rate of an evaluation set is a property of the labels, and "the base rate regressed" is
    not a statement about a model.

    Either side failing its own input contract refuses the whole gate — a verdict from one
    valid side and one invalid side is worse than no verdict.

    @capability metric_regression_gate_flat
    complexity: O(n log n + h)
    counts:
    - n_base <= len(base_probs, base_labels) [kernel_validated]
    - n_cand <= len(cand_probs, cand_labels) [kernel_validated]
    - dim n_bins [kernel_validated]
    @endcapability

    `n_bins` is bounded by `contract.EVAL_MAX_BINS`, and both sample counts by
    `contract.EVAL_MAX_SAMPLES`, inside `eval_bins_status` and `eval_pairs_status`
    respectively. The ceilings are not written as declared bounds here because a declared
    ceiling must name a `comptime` constant in the same file, and a copy of the value would
    be free to drift from the one the kernel tests.
    """
    if metric_id < 0 or metric_id > EVAL_METRIC_ECE:
        return GateResult(EVAL_ERR_UNKNOWN_METRIC, metric_id)
    if metric_id == EVAL_METRIC_BASE_RATE:
        return GateResult(EVAL_ERR_UNKNOWN_METRIC, metric_id)

    var base = metric_value_flat(
        base_probs, base_labels, n_base, metric_id, n_bins, policy
    )
    if not base.present:
        return GateResult(base.status, metric_id)
    var cand = metric_value_flat(
        cand_probs, cand_labels, n_cand, metric_id, n_bins, policy
    )
    if not cand.present:
        return GateResult(cand.status, metric_id)
    # Both sides were binned with the same arguments, so this can only fail if a driver
    # stopped reporting its provenance. Checked rather than assumed: a certificate must
    # check every condition it claims, including the ones the current code cannot violate.
    if base.bins_used != cand.bins_used or base.bin_policy != cand.bin_policy:
        return GateResult(EVAL_ERR_INCOMPARABLE_BINNING, metric_id)

    var verdict = metric_gate(
        base.value,
        cand.value,
        abs_tolerance,
        eval_metric_higher_is_better(metric_id),
    )
    if not verdict.decided:
        return GateResult(verdict.status, metric_id)
    var out = verdict^
    out.metric_id = metric_id
    out.bins_used = cand.bins_used
    out.bin_policy = cand.bin_policy
    return out^


fn psi_drift_gate_flat(
    reference: List[Float64], n_reference: Int, candidate: List[Float64],
    n_candidate: Int, n_bins: Int, threshold: Float64
) -> DriftResult:
    """Population Stability Index between two score distributions, honestly incomplete.

    Both distributions are binned with equal-width bins on [0, 1] — the same frozen
    `calibration.calibration_curve` partition every other driver here uses — and each bin's
    term comes from the frozen `evaluation_feedback.population_stability_index`. Quantile
    bins are deliberately NOT offered: a PSI compares two distributions against a FIXED
    partition, and edges derived from one of the two datasets would make the index depend on
    which dataset was called the reference.

    The conventional reading of the index is `< 0.1` stable, `> 0.25` drifted; `threshold` is
    the caller's own cut and must be finite and non-negative.

    A bin where either proportion is zero has an infinite term. It is counted in
    `bins_unmatched` and omitted from the sum, so the sum is a LOWER BOUND on the true index
    — see the module docstring. `decided` is True when the verdict does not depend on those
    missing terms.

    @capability psi_drift_gate_flat
    complexity: O(n_reference + n_candidate + h)
    counts:
    - n_reference <= len(reference) [kernel_validated]
    - n_candidate <= len(candidate) [kernel_validated]
    - dim n_bins [kernel_validated]
    @endcapability

    `n_bins` is bounded by `contract.EVAL_MAX_BINS` and both counts by
    `contract.EVAL_MAX_SAMPLES`, checked in `eval_bins_status` and `eval_scores_status`.
    """
    var ref_status = eval_scores_status(reference, n_reference)
    if ref_status != EVAL_OK:
        return DriftResult(ref_status, n_reference, n_candidate, n_bins)
    var cand_status = eval_scores_status(candidate, n_candidate)
    if cand_status != EVAL_OK:
        return DriftResult(cand_status, n_reference, n_candidate, n_bins)
    var bin_status = eval_bins_status(n_bins, EVAL_BIN_EQUAL_WIDTH)
    if bin_status != EVAL_OK:
        return DriftResult(bin_status, n_reference, n_candidate, n_bins)
    if not eval_finite(threshold) or threshold < 0.0:
        return DriftResult(
            EVAL_ERR_THRESHOLD, n_reference, n_candidate, n_bins
        )

    # `eval_bin_counts_flat`, not `eval_bins_build`: a drift comparison has no labels, and
    # `eval_pairs_status` correctly refuses anything that is not exactly 0.0 or 1.0 in the
    # label position. Inventing a zero label vector to get past that check would be a lie
    # about the data for the sake of reusing a function.
    var ref_bins = eval_bin_counts_flat(
        reference, n_reference, n_bins, EVAL_BIN_EQUAL_WIDTH
    )
    if ref_bins.status != EVAL_OK:
        return DriftResult(ref_bins.status, n_reference, n_candidate, n_bins)
    var cand_bins = eval_bin_counts_flat(
        candidate, n_candidate, n_bins, EVAL_BIN_EQUAL_WIDTH
    )
    if cand_bins.status != EVAL_OK:
        return DriftResult(cand_bins.status, n_reference, n_candidate, n_bins)
    if ref_bins.occupied == 0 or cand_bins.occupied == 0:
        return DriftResult(
            EVAL_ERR_NO_OCCUPIED_BINS, n_reference, n_candidate, n_bins
        )

    var out = DriftResult(EVAL_OK, n_reference, n_candidate, n_bins)
    out.threshold = threshold
    var ref_total = Float64(n_reference)
    var cand_total = Float64(n_candidate)
    var partial = 0.0
    for b in range(n_bins):
        var p_ref = Float64(ref_bins.count[b]) / ref_total
        var p_cand = Float64(cand_bins.count[b]) / cand_total
        if p_ref <= 0.0 and p_cand <= 0.0:
            # Neither distribution occupies this bin. The term is 0 * log(0/0), which is not
            # a missing measurement — there is simply nothing here to compare, in either
            # direction. Counting it as unmatched would report drift information as absent
            # for every empty region of the score space.
            continue
        if p_ref <= 0.0 or p_cand <= 0.0:
            out.bins_unmatched += 1
            continue
        out.bins_matched += 1
        partial += population_stability_index(p_cand, p_ref)
    out.psi_lower_bound = partial

    if out.bins_unmatched == 0:
        out.present = True
        out.psi = partial
        out.decided = True
        out.drifted = partial > threshold
        return out^

    out.status = EVAL_ERR_PSI_INCOMPLETE
    if partial > threshold:
        # The missing terms are all positive, so a lower bound already past the threshold
        # settles the question: this is drift, whatever the unmatched bins would have added.
        out.decided = True
        out.drifted = True
    return out^
