"""
evaluation.contract — the one status vocabulary, input validation, binning policy and work
budget for `evaluation`. Zero Python imports.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int, bool
backend: mojo
surfaces: library_execute, batch_execute
complexity: O(n)
golden_vectors: mojo/tests/libs/test_evaluation_contract.mojo
benchmark: benchmarks/mojo_benchmarks/bench_evaluation.mojo
docs: gitbook/engine/evaluation-calibration.md
version_introduced: unreleased
deprecation_state: active
@endcapability

What this package is, and what it deliberately is not
-----------------------------------------------------
`evaluation` is a DRIVER over frozen metric kernels. It contributes composition and
refusals, not arithmetic. Every number it reports is produced by a frozen kernel:

  ml_metrics_extended.brier_score_term      per-sample (p - y)^2
  ml_metrics_extended.calibration_ece_term  one bin's |acc - conf| * n_bin / n
  loss_functions.binary_cross_entropy       per-sample log-loss, with ITS clamp
  calibration.calibration_curve            equal-width binning on [0, 1]
  evaluation_feedback.population_stability_index   one bin's PSI term
  sorting.heapsort                          the O(n log n) sort behind quantile bins
  determinism.sampling_keyed.uniform_int_keyed     every bootstrap index draw

What is added is the part that was missing: one input contract, one status vocabulary, an
explicit binning policy that travels WITH the number, and an absent/present split so that
"could not be computed" is never spelled `0.0`.

Status range
------------
`evaluation` owns **360-379** and uses no other code (rule 4e: ranges are allocated per
package, not per file, so a logged status means one thing). All twenty are spent; a further
outcome needs a new range, not a reused integer. Neighbours at the time of writing:
`tensorx`/`forecasting` 300-319, `gemm`/`inference` 320-339, `causal_inference` 340-359.

Why validation lives here and not in each driver
------------------------------------------------
`optimization/` grew six byte-identical private `_finite` helpers that then drifted, and one
input invariant enforced at three different strengths under three different status codes.
So there is exactly ONE `eval_pairs_status` and every driver in the package calls it. A
duplicated guard reads as defence in depth while providing one arbitrary behaviour per call
site.

The count guard is the whole reason the package has a contract
--------------------------------------------------------------
Reading past the end of a `List` in Mojo is an UNCATCHABLE abort: it kills the worker
process and `try`/`except` above it does not help. Every driver here takes an explicit `n`,
and `eval_pairs_status` refuses `n > len(probs)` and `n > len(labels)` BEFORE any index is
formed. That is `[kernel_validated]`, not `[enforced]`: the check is written below, in this
file, and the caller receives a typed status rather than a refused dispatch.

Why probabilities and labels are validated at all
-------------------------------------------------
A Brier score of a probability of 3.0 is a number, and log-loss of a NaN is a NaN. Both
would travel into a metric field and out to a caller who cannot tell. JSON has no NaN and
the dispatch REFUSES a non-finite rather than serialising it, so one bad sample would turn
the whole response into a transport error with no indication which sample caused it. The
package therefore refuses the input and names what was wrong.

Bounding memory is not bounding work
------------------------------------
`eval_work_fits` and `eval_resample_work_fits` exist because a request can be structurally
valid, inside every length ceiling, and still take minutes. A bootstrap charges
`n_boot * n` draws — the PRODUCT — and a quantile-binned ECE inside that loop charges
another `log2(n)` per replicate for its sort. Charging only `n_boot + n` would be a budget
that bounds nothing. Every product is checked by DIVISION, never by forming the product:
`3 * 6148914691236517206 == 2` is how a wrapping multiply walked past a guard in
`sparse_numerics` and aborted the worker.

Every factor, not most of them. A bootstrapped ECE rebuilds the whole partition inside every
replicate, so `n_bins` is multiplied by `n_boot` in the real cost too. An earlier version of
`eval_resample_work_fits` took `n_bins` and used it only for a sign test, which charged that
term ZERO: measured at an identical declared cost of 4096 units, 9.2 ms at h = 1 against
1231.9 ms at h = 4096. A budget that looks at three of a product's four factors has the same
failure mode as one that looks at none of them, and it is harder to spot because it looks
like it is doing the check.

Public API:
  eval_status_name(code)                    — the status vocabulary, one name per code
  eval_status_is_ok(code)                   — success, spelled once
  eval_bin_policy_name(policy)              — the binning policy, named
  eval_metric_name(metric_id)               — the metric vocabulary, named
  eval_metric_higher_is_better(metric_id)   — gate direction, owned by the metric
  eval_finite(x)                            — one finiteness test for the package
  eval_pairs_status(probs, labels, n)       — the ONE input contract for (p, y, n)
  eval_bins_status(n_bins, policy)          — binning arguments, validated
  eval_ece_comparable(ba, pa, bb, pb)       — refuses to compare across binnings
  eval_log2_ceil(n)                         — ceil(log2(n)), for charging a sort
  eval_work_fits(a, b, ceiling)             — a * b <= ceiling, by division
  eval_resample_work_fits(...)              — the bootstrap's real cost, charged
"""

from std.math import isinf, isnan

# ── status codes: evaluation owns 360-379 ─────────────────────────────────────

comptime EVAL_OK: Int = 360
comptime EVAL_ERR_EMPTY: Int = 361
comptime EVAL_ERR_COUNT: Int = 362
comptime EVAL_ERR_LABEL_LENGTH: Int = 363
comptime EVAL_ERR_NON_FINITE: Int = 364
"""A non-finite value where a metric has to go.

Covers BOTH a non-finite that arrived in the payload and a non-finite that the package's own
arithmetic produced from finite operands — `metric_gate(-DBL_MAX, DBL_MAX, ...)` has two
finite inputs whose difference is `+inf`. Hence `non_finite_value` rather than
`non_finite_input`: the code says a number that cannot travel appeared, not where it came
from."""
comptime EVAL_ERR_PROB_RANGE: Int = 365
comptime EVAL_ERR_LABEL_NOT_BINARY: Int = 366
comptime EVAL_ERR_BIN_COUNT: Int = 367
comptime EVAL_ERR_BIN_POLICY: Int = 368
comptime EVAL_ERR_UNKNOWN_METRIC: Int = 369
comptime EVAL_ERR_ALPHA_RANGE: Int = 370
comptime EVAL_ERR_RESAMPLE_COUNT: Int = 371
comptime EVAL_ERR_SEED_NEGATIVE: Int = 372
comptime EVAL_ERR_WORK_BUDGET: Int = 373
comptime EVAL_ERR_DIM_TOO_LARGE: Int = 374
comptime EVAL_ERR_TOLERANCE: Int = 375
comptime EVAL_ERR_PSI_INCOMPLETE: Int = 376
comptime EVAL_ERR_NO_OCCUPIED_BINS: Int = 377
comptime EVAL_ERR_INCOMPARABLE_BINNING: Int = 378
comptime EVAL_ERR_THRESHOLD: Int = 379

# ── binning policy ────────────────────────────────────────────────────────────
# ECE is binning-dependent and that dependence is usually hidden. Measured on
# p = [0.2, 0.4, 0.6, 0.8], y = [0, 1, 0, 1]: ECE is 0.2 with 2 equal-width bins and 0.4
# with 4 — a factor of two from the binning alone, on identical predictions. So the policy
# is an explicit argument, and the bin count and policy travel back inside every result.

comptime EVAL_BIN_EQUAL_WIDTH: Int = 0
"""Bins of equal width on [0, 1]: bin b is [b/h, (b+1)/h), last bin closed at 1.0.
Delegated to the frozen `calibration.calibration_curve`, so the assignment rule is the
tree's existing one and not a second copy of it.

`b/h` is the definition over the REALS. The reported boundaries are the boundaries of the
partition the frozen rule `Int(p*h)` actually implements, which for some h differ from
`fl(b/h)` by one ulp — measured: `Int(fl(15/22) * 22) == 14`, so `fl(15/22)` is not in bin 15
and must not be published as its lower edge. `evaluation.binning._equal_width_edge` resolves
that, and `eval_bin_edges_flat` documents the guarantee."""

comptime EVAL_BIN_EQUAL_COUNT: Int = 1
"""Bins of equal COUNT — quantile / adaptive binning. Edges are order statistics of the
predictions themselves, so a model whose predictions cluster in one corner of [0, 1] still
produces occupied bins. Costs a sort; `eval_resample_work_fits` charges it."""

# ── metric vocabulary ─────────────────────────────────────────────────────────

comptime EVAL_METRIC_BRIER: Int = 0
comptime EVAL_METRIC_LOG_LOSS: Int = 1
comptime EVAL_METRIC_ACCURACY: Int = 2
comptime EVAL_METRIC_BASE_RATE: Int = 3
comptime EVAL_METRIC_ECE: Int = 4
comptime EVAL_METRIC_COUNT: Int = 5
"""How many metric ids exist. `metric_id >= EVAL_METRIC_COUNT` is refused, never
interpreted: an unrecognised metric that silently becomes metric 0 is a plausible wrong
number, which is the worst outcome for an evaluation."""

# ── ceilings ──────────────────────────────────────────────────────────────────

comptime EVAL_MAX_SAMPLES: Int = 1 << 24
"""16,777,216 samples.

Derived, not chosen: the tree's per-object budget is `1 << 26` Float64 elements (~512 MB,
`sparse_numerics.csr.MAX_CSR_DIM`). A driver here holds up to four independent n-length
Float64 arrays live at once — a truncated probability copy, a truncated label copy, a sorted
copy for quantile binning, and one bootstrap replicate pair — so per rule 1c the per-object
budget is DIVIDED by four rather than applied four times: `(1 << 26) / 4 == 1 << 24`, about
134 MB per array and ~536 MB in total at the ceiling."""

comptime EVAL_MAX_BINS: Int = 1 << 12
"""4096 bins. A reliability diagram allocates six h-length arrays, so this is ~200 KB;
the real reason for a ceiling is that h is a caller integer that no payload length bounds,
and `h` beyond the sample count produces empty bins rather than information."""

comptime EVAL_MAX_RESAMPLE_WORK: Int = 1 << 32
"""Bound on the bootstrap's REAL cost: `n_boot * (n * per_draw_factor + bins_charged)`.

It exists because `n_boot` and `n` are each comfortably inside their own ceilings at values
whose product is not reachable this decade: `n_boot = 100000` with `n = 1 << 24` is 1.7e12
draws, and from the caller's side a hang is indistinguishable from the uncatchable abort that
rule 1 is about.

What this ceiling does and does not promise. It makes the declared cost PROPORTIONAL to the
real work, so two requests the budget rates the same take comparable time — that is the
property `eval_resample_work_fits` is for, and the property whose absence in the `n_bins`
factor was a measured 133x wall-clock spread at one declared cost. It does NOT promise a
wall-clock bound: 4.3e9 units is tens of seconds, not "a few". Measured per-replicate slopes
on a heavily loaded 16-core machine put a sample-draw unit near 400 ns and a bin unit near
140 ns, so a request sitting exactly at this ceiling is minutes of work there and still
seconds-to-a-minute on an idle machine. A caller that needs a latency bound must size its own
request; this ceiling refuses the requests that are not finishable at all."""

comptime EVAL_MAX_RESAMPLES: Int = 1 << 20
"""Per-call replicate ceiling. Separate from the work budget because it bounds a different
thing: the replicate array itself is `n_boot` Float64s and is sorted in place."""

comptime EVAL_DBL_EPSILON: Float64 = 2.220446049250313e-16
"""Machine epsilon for Float64. Used ONLY to scale a comparison by the magnitude of the
quantity being compared — never by a sum or maximum over other samples, and never
multiplied into a caller-supplied tolerance (rule 4b, spellings 1, 2 and 4)."""

comptime EVAL_LOG_LOSS_EPS: Float64 = 1e-7
"""The clamp inside the frozen `loss_functions.binary_cross_entropy`, restated so that a
report can NAME it.

Log-loss of a probability of exactly 0 for a positive label is infinite. The frozen kernel
clamps p into [1e-7, 1 - 1e-7], which is the right behaviour and is kept — but it does not
say that it happened, so a caller cannot distinguish a genuinely confident-and-wrong model
from a saturated one. `log_loss_flat` reports this epsilon and counts the clamped samples.
`test_evaluation_scores.mojo` asserts the frozen kernel really clamps at this value, so the
constant cannot drift away from the kernel it describes."""


fn eval_status_name(code: Int) -> String:
    """Name a status code.

    An unknown code says so rather than borrowing a neighbour's meaning: a caller logging
    an integer must be able to recover exactly one meaning from it.

    @capability eval_status_name
    complexity: O(1)
    counts: none
    @endcapability
    """
    if code == EVAL_OK:
        return String("ok")
    if code == EVAL_ERR_EMPTY:
        return String("empty_input")
    if code == EVAL_ERR_COUNT:
        return String("count_exceeds_predictions")
    if code == EVAL_ERR_LABEL_LENGTH:
        return String("count_exceeds_labels")
    if code == EVAL_ERR_NON_FINITE:
        return String("non_finite_value")
    if code == EVAL_ERR_PROB_RANGE:
        return String("probability_out_of_range")
    if code == EVAL_ERR_LABEL_NOT_BINARY:
        return String("label_not_binary")
    if code == EVAL_ERR_BIN_COUNT:
        return String("invalid_bin_count")
    if code == EVAL_ERR_BIN_POLICY:
        return String("unknown_bin_policy")
    if code == EVAL_ERR_UNKNOWN_METRIC:
        return String("unknown_metric")
    if code == EVAL_ERR_ALPHA_RANGE:
        return String("alpha_out_of_range")
    if code == EVAL_ERR_RESAMPLE_COUNT:
        return String("invalid_resample_count")
    if code == EVAL_ERR_SEED_NEGATIVE:
        return String("negative_seed")
    if code == EVAL_ERR_WORK_BUDGET:
        return String("work_budget_exceeded")
    if code == EVAL_ERR_DIM_TOO_LARGE:
        return String("dimension_too_large")
    if code == EVAL_ERR_TOLERANCE:
        return String("invalid_tolerance")
    if code == EVAL_ERR_PSI_INCOMPLETE:
        return String("psi_incomplete_lower_bound_only")
    if code == EVAL_ERR_NO_OCCUPIED_BINS:
        return String("no_occupied_bins")
    if code == EVAL_ERR_INCOMPARABLE_BINNING:
        return String("incomparable_binning")
    if code == EVAL_ERR_THRESHOLD:
        return String("invalid_threshold")
    return String("unknown_status_code")


fn eval_status_is_ok(code: Int) -> Bool:
    """Success, spelled once, so no caller has to remember which integer means ok.

    @capability eval_status_is_ok
    complexity: O(1)
    counts: none
    @endcapability
    """
    return code == EVAL_OK


fn eval_bin_policy_name(policy: Int) -> String:
    """Name a binning policy, so a reported ECE says how it was binned.

    @capability eval_bin_policy_name
    complexity: O(1)
    counts: none
    @endcapability
    """
    if policy == EVAL_BIN_EQUAL_WIDTH:
        return String("equal_width")
    if policy == EVAL_BIN_EQUAL_COUNT:
        return String("equal_count")
    return String("unknown_bin_policy")


fn eval_metric_name(metric_id: Int) -> String:
    """Name a metric id.

    @capability eval_metric_name
    complexity: O(1)
    counts: none
    @endcapability
    """
    if metric_id == EVAL_METRIC_BRIER:
        return String("brier")
    if metric_id == EVAL_METRIC_LOG_LOSS:
        return String("log_loss")
    if metric_id == EVAL_METRIC_ACCURACY:
        return String("accuracy_at_half")
    if metric_id == EVAL_METRIC_BASE_RATE:
        return String("base_rate")
    if metric_id == EVAL_METRIC_ECE:
        return String("expected_calibration_error")
    return String("unknown_metric")


fn eval_metric_higher_is_better(metric_id: Int) -> Bool:
    """Gate direction for a metric.

    The direction belongs to the METRIC, not to the caller of a gate: a gate that takes
    `higher_is_better` as a free parameter will eventually be told that a lower Brier score
    is a regression. `base_rate` is a property of the labels rather than of the model, so
    it has no better direction; `False` is returned and `metric_regression_gate_flat`
    refuses to gate on it.

    @capability eval_metric_higher_is_better
    complexity: O(1)
    counts: none
    @endcapability
    """
    return metric_id == EVAL_METRIC_ACCURACY


fn eval_finite(x: Float64) -> Bool:
    """One finiteness test for the whole package.

    Public and single so it cannot be copied six times and then drift, which is what
    happened to `_finite` in `optimization/`.

    @capability eval_finite
    complexity: O(1)
    counts: none
    @endcapability
    """
    return not (isnan(x) or isinf(x))


fn eval_pairs_status(
    probs: List[Float64], labels: List[Float64], n: Int
) -> Int:
    """The ONE input contract for a predictions-and-labels pair. `EVAL_OK` or why not.

    Checked in this order, because the earlier checks are what keep the later ones from
    indexing past an end:

    1. `n < 0` and `n == 0` — an empty evaluation set has no metrics (rule 4: a Brier score
       of nothing does not exist and must not be 0.0).
    2. `n > EVAL_MAX_SAMPLES` — the allocation ceiling, derived in this file.
    3. `n > len(probs)` / `n > len(labels)` — the count guard. This is the check whose
       absence is a remote process-abort primitive; it is made BEFORE any subscript.
    4. per sample: `probs[i]` finite, then `probs[i]` in [0, 1], then `labels[i]` exactly
       0.0 or 1.0.

    A probability outside [0, 1] is refused rather than clipped. Clipping would turn a
    unit-confusion bug (percentages, logits, a score that was never a probability) into a
    plausible metric, and every metric here is defined only on [0, 1].

    A label other than 0.0 or 1.0 is refused rather than thresholded. `binary_cross_entropy`
    with y = 0.5 computes a well-formed cross-entropy that is NOT a log-loss, and nothing
    downstream could tell.

    @capability eval_pairs_status
    complexity: O(n)
    counts:
    - n <= len(probs, labels) [kernel_validated]
    @endcapability
    """
    if n < 0:
        return EVAL_ERR_COUNT
    if n == 0:
        return EVAL_ERR_EMPTY
    if n > EVAL_MAX_SAMPLES:
        return EVAL_ERR_DIM_TOO_LARGE
    if n > len(probs):
        return EVAL_ERR_COUNT
    if n > len(labels):
        return EVAL_ERR_LABEL_LENGTH
    for i in range(n):
        var p = probs[i]
        if not eval_finite(p):
            return EVAL_ERR_NON_FINITE
        if p < 0.0 or p > 1.0:
            return EVAL_ERR_PROB_RANGE
        var y = labels[i]
        if not eval_finite(y):
            return EVAL_ERR_NON_FINITE
        if y != 0.0 and y != 1.0:
            return EVAL_ERR_LABEL_NOT_BINARY
    return EVAL_OK


fn eval_scores_status(scores: List[Float64], n: Int) -> Int:
    """`eval_pairs_status` for a single unlabelled score list — the drift-gate input.

    Same order and same ceilings; there is no label to check. Kept beside the paired
    version rather than inside it so neither has an argument that is ignored.

    @capability eval_scores_status
    complexity: O(n)
    counts:
    - n <= len(scores) [kernel_validated]
    @endcapability
    """
    if n < 0:
        return EVAL_ERR_COUNT
    if n == 0:
        return EVAL_ERR_EMPTY
    if n > EVAL_MAX_SAMPLES:
        return EVAL_ERR_DIM_TOO_LARGE
    if n > len(scores):
        return EVAL_ERR_COUNT
    for i in range(n):
        var s = scores[i]
        if not eval_finite(s):
            return EVAL_ERR_NON_FINITE
        if s < 0.0 or s > 1.0:
            return EVAL_ERR_PROB_RANGE
    return EVAL_OK


fn eval_bins_status(n_bins: Int, policy: Int) -> Int:
    """Validate the binning arguments. `EVAL_OK` or why not.

    `n_bins <= 0` is refused rather than defaulted. The frozen
    `calibration.calibration_curve` returns three EMPTY lists for `n_bins <= 0`, which a
    driver that did not check would read as "every bin is empty" and report an ECE of 0.0 —
    a perfectly calibrated model, from a malformed request.

    @capability eval_bins_status
    complexity: O(1)
    counts:
    - dim n_bins <= EVAL_MAX_BINS [kernel_validated]
    @endcapability
    """
    if n_bins <= 0:
        return EVAL_ERR_BIN_COUNT
    if n_bins > EVAL_MAX_BINS:
        return EVAL_ERR_BIN_COUNT
    if policy != EVAL_BIN_EQUAL_WIDTH and policy != EVAL_BIN_EQUAL_COUNT:
        return EVAL_ERR_BIN_POLICY
    return EVAL_OK


fn eval_ece_comparable(
    bins_a: Int, policy_a: Int, bins_b: Int, policy_b: Int
) -> Bool:
    """True only when two calibration errors were produced by the SAME binning.

    Two ECEs computed under different bin counts or different policies are two different
    statistics that happen to share a name, and comparing them is the commonest way an
    "improvement" in calibration is manufactured. Measured, on identical predictions
    p = [0.2, 0.4, 0.6, 0.8] with y = [0, 1, 0, 1]: 0.2 at 2 equal-width bins, 0.4 at 4.

    Both binnings must also be VALID: two invalid binnings are not comparable, they are
    both refusals.

    @capability eval_ece_comparable
    complexity: O(1)
    counts: none
    @endcapability
    """
    if eval_bins_status(bins_a, policy_a) != EVAL_OK:
        return False
    if eval_bins_status(bins_b, policy_b) != EVAL_OK:
        return False
    return bins_a == bins_b and policy_a == policy_b


fn eval_log2_ceil(n: Int) -> Int:
    """`ceil(log2(n))` for `n >= 1`, and 0 for `n <= 1`. Never uses a float.

    This is the per-sample factor a quantile-binned pass costs (a binary search over the
    bin edges) and the per-element factor its heapsort costs. It exists so the work budget
    can charge them instead of pretending the pass is linear.

    @capability eval_log2_ceil
    complexity: O(log n)
    counts: none
    @endcapability
    """
    if n <= 1:
        return 0
    var bits = 0
    var remaining = n - 1
    while remaining > 0:
        remaining //= 2
        bits += 1
    return bits


fn eval_work_fits(a: Int, b: Int, ceiling: Int) -> Bool:
    """True when `a * b <= ceiling`, computed WITHOUT forming `a * b`.

    `a * b` is a wrapping 64-bit multiply, so a guard written as `a * b <= ceiling` is not
    a guard: `3 * 6148914691236517206 == 2` is how a product check was walked past in
    `sparse_numerics` and ended the worker process. Division has no such failure mode.

    A negative factor or a negative ceiling is not a fit; it is a malformed request.

    @capability eval_work_fits
    complexity: O(1)
    counts: none
    @endcapability
    """
    if a < 0 or b < 0 or ceiling < 0:
        return False
    if a == 0 or b == 0:
        return True
    return a <= ceiling // b


fn eval_resample_work_fits(
    n_boot: Int, n: Int, n_bins: Int, metric_id: Int, policy: Int
) -> Bool:
    """True when a bootstrap of this shape is inside `EVAL_MAX_RESAMPLE_WORK`.

    The real cost is `n_boot * (n * factor + bin_charge)`. ONE replicate costs:

      * `n` for the index draws, the re-validation and the accumulation — every metric;
      * `n * ceil(log2(n))` more for a quantile-binned ECE, whose replicate is heapsorted and
        then binary-searched per sample;
      * `n_bins` MORE, once per replicate, for any metric that BINS. That term is the one this
        function got wrong. `EVAL_METRIC_ECE` rebuilds the whole partition inside every
        replicate — two `calibration_curve` calls, each allocating four h-length lists, plus
        the h-loop in `eval_bins_build` and the h-loop that sums the bin terms — so `h` is
        multiplied by `n_boot` in the real cost. Taking `n_bins` as an argument and using it
        only for a sign test charged that at ZERO.

    Measured, on the code before the bin term was charged: at an identical declared cost of
    4096 units, `n_boot = 4096` with `n = 1` took 9.2 ms at h = 1 and 1231.9 ms at h = 4096 —
    a 133x wall-clock spread at one declared cost, rising to ~195x at the legal maximum
    `n_boot = EVAL_MAX_RESAMPLES`, which the budget rated at 0.024% of its own ceiling. That
    is precisely the defect this function exists to prevent, restated in the one factor it
    was not looking at.

    A bin is charged the same as a sample-draw, which is CONSERVATIVE in the safe direction.
    Measured per-replicate slopes on this machine: ~400 ns per additional sample against
    ~140 ns per additional bin, i.e. a bin is about 0.35 of a sample-draw, so `+ n_bins`
    over-charges binning by roughly 3x rather than under-charging it. A fitted fractional
    weight would be a machine-specific constant baked into a contract; the integer 1 is
    defensible on any machine because it bounds from above.

    Charging `n_boot + n`, or charging `n_boot * n` for a metric whose replicate is
    `n log n`, is the defect rule 1c names: a budget that counts one factor of a product is
    not a budget. Measured elsewhere in this tree as 0.49s versus 23.89s at an identical
    declared cost.

    Every product is folded in one at a time by DIVISION, and each addend is bounded by the
    ceiling BEFORE the addition, so no intermediate ever wraps.

    @capability eval_resample_work_fits
    complexity: O(log n)
    counts: none
    @endcapability
    """
    if n_boot < 0 or n < 0 or n_bins < 0:
        return False
    var factor = 1
    var bin_charge = 0
    if metric_id == EVAL_METRIC_ECE:
        # Only ECE bins; `metric_value_flat` sends every other id down a path that never
        # touches `eval_bins_build`. Charging h to a Brier bootstrap would refuse requests
        # that do no binning work at all.
        bin_charge = n_bins
        if policy == EVAL_BIN_EQUAL_COUNT:
            factor += eval_log2_ceil(n)
    # Each addend is bounded by the ceiling on its own, so their sum is at most twice the
    # ceiling and cannot wrap. `n * factor` is checked by division first, never formed blind.
    if bin_charge > EVAL_MAX_RESAMPLE_WORK:
        return False
    if not eval_work_fits(n, factor, EVAL_MAX_RESAMPLE_WORK):
        return False
    var per_replicate = n * factor + bin_charge
    if per_replicate > EVAL_MAX_RESAMPLE_WORK:
        return False
    return eval_work_fits(n_boot, per_replicate, EVAL_MAX_RESAMPLE_WORK)
