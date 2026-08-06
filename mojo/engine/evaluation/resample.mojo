"""
evaluation.resample — bootstrap confidence intervals for any metric in this package, with a
seed that reaches every draw. Zero Python imports.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: required
supported_dtypes: float64, int, bool
backend: mojo
surfaces: library_execute, batch_execute
complexity: O(n_boot * n log n)
golden_vectors: mojo/tests/libs/test_evaluation_resample.mojo
benchmark: benchmarks/mojo_benchmarks/bench_evaluation.mojo
docs: gitbook/engine/evaluation-calibration.md
version_introduced: unreleased
deprecation_state: active
@endcapability

Why this is not `stats_bootstrap`
--------------------------------
`stats_bootstrap.bootstrap_replicate` draws from `random_float64()` — process-global,
unseeded state. Every CI it produces is a different number on the second run and none of
them can be replayed, so a CI that decides a release cannot be re-derived from the record.
`model_compare.paired_bootstrap_diff_ci` does take a seed, and correctly, but it is a CI on
a paired DIFFERENCE of two per-sample metric contributions; it cannot express a metric that
is not a mean of per-sample terms, which is exactly what ECE and log-loss are not.

Both frozen kernels stay reachable and unchanged. This is the additive driver: a CI on ANY
metric this package can compute, resampled with the keyed `determinism` kernels.

The seed reaches every draw, addressably
----------------------------------------
`determinism.sampling_keyed.uniform_int_keyed` is a pure function of its coordinates
(Philox4x64-10). Draw `i` of replicate `b` is addressed as `draw_index = b * n + i`, so:

  * every one of the `n_boot * n` draws has its OWN coordinate — the seed is not consumed by
    the first replicate and then re-used;
  * the same `(seed, b, i)` gives the same index on any machine, in any order, whatever else
    the process did;
  * nothing is drawn from a stream that another part of the run also advances, because the
    stream id is derived by name via `determinism.streams.stream_id`.

`n_boot * n` is bounded by the work budget before any draw is made, so `draw_index` cannot
approach the UInt64 range.

`distinct_replicates` is how you check the above claim rather than trust it. If the seed
reached only the first draw, or the coordinates collided, the replicate distribution would
collapse; a bootstrap with more than one distinct replicate value on non-degenerate data is
the observable that a draw-per-coordinate scheme is actually working.

Each replicate is re-validated
------------------------------
A replicate is passed through the same `metric_value_flat` as the point estimate, which
re-runs `eval_pairs_status` on it. That is an O(n) cost per replicate — the same order as
the metric itself — and it is paid deliberately: the alternative is an unchecked entry point
that trusts a count, and any such function in the runtime contract is a remote
process-abort primitive the moment a caller passes `n` larger than the list. There is one
strength of check in this package, and it is this one.

The interval, and what it is not
--------------------------------
Percentile method: `[alpha/2, 1 - alpha/2]` quantiles of the replicate distribution, taken
with the frozen `stats.quantile` (numpy's linear interpolation) rather than a second
percentile rule written here. It is NOT bias-corrected: for a skewed statistic the point
estimate can fall outside the interval, which is a property of the method and not an error,
so `point_inside` reports it instead of the interval being quietly widened to hide it.

`n_boot` too small for `alpha` is a REFUSAL, not a narrow interval
------------------------------------------------------------------
The percentile method reads the replicate distribution at probability `alpha/2`. An empirical
distribution of `n_boot` values has no information at any probability finer than `1/n_boot`,
so a request for a tail of `alpha/2 < 1/n_boot` is a request for a percentile that is not in
the data: the endpoint is then decided by the single most extreme replicate rather than
estimated from the distribution. The condition is therefore `n_boot * alpha >= 2`.

Measured on non-degenerate data (n = 20 keyed-pseudo-random predictions, Brier, 8 bins,
alpha = 0.05, seed 4) BEFORE this was checked, every row returning status `ok`:

    n_boot =    1   lo == hi == 0.10025972259806666   width 0.0
                    point 0.10532587364706503 — OUTSIDE its own "95% interval"
    n_boot =    2   width 0.015565457483337972
    n_boot = 2000   width 0.09334163657683582

A "95% CI" of width zero, and one six times too narrow, under a success status. A caller
cannot detect either from the result. So the request is refused before any draw is made, with
`EVAL_ERR_RESAMPLE_COUNT` — the resample count IS invalid for the requested tail probability —
and `n_boot_min` reports the smallest count that would be accepted, so the refusal is
actionable rather than merely a rejection. For alpha = 0.05 that is 40.

The refusal reuses an existing code deliberately. `evaluation` owns 360-379 and all twenty are
spent; inventing a twenty-first would mean either stealing a neighbouring package's integer or
widening a range, and the existing name already describes this exactly.

Public API:
  MetricCI                        — interval, point, provenance, and the draw diagnostics
  bootstrap_metric_ci_flat(...)   — the CI
  bootstrap_draw_index(b, i, n)   — the coordinate map, exposed so a test can assert it
  bootstrap_min_replicates(alpha) — the smallest `n_boot` that resolves `alpha`'s tails
"""

from determinism.sampling_keyed import uniform_int_keyed
from determinism.streams import stream_id
from sorting import heapsort
from stats import quantile

from evaluation.contract import (
    EVAL_ERR_ALPHA_RANGE,
    EVAL_ERR_RESAMPLE_COUNT,
    EVAL_ERR_SEED_NEGATIVE,
    EVAL_ERR_UNKNOWN_METRIC,
    EVAL_ERR_WORK_BUDGET,
    EVAL_MAX_RESAMPLES,
    EVAL_METRIC_ECE,
    EVAL_OK,
    eval_bins_status,
    eval_finite,
    eval_pairs_status,
    eval_resample_work_fits,
)
from evaluation.scores import metric_value_flat

comptime EVAL_BOOTSTRAP_STREAM_NAME: String = "evaluation.bootstrap.v1"
"""The name the bootstrap's Philox stream is derived from.

Named, versioned and never a bare integer: `determinism.counter_rng` reserves stream ids 1-7
for the first consumer of the kernel, and reusing one would silently change values that
consumer already drew. `determinism.streams.stream_id` hashes this name into the space above
the reserved block. Changing the string changes every interval this module has ever
produced, which is why it carries a version suffix."""


struct MetricCI(Copyable, Movable):
    """A bootstrap confidence interval, its provenance, and its draw diagnostics.

    `present == False` means no interval exists for this request; `lo`, `hi` and `point` are
    then 0.0 and are not measurements. Every field is a representable Float64 in both cases,
    because a raw non-finite in any slot makes the whole response a typed transport error.

    `seed`, `n_boot`, `alpha`, `metric_id`, `bins_used` and `bin_policy` are all returned so
    the interval can be reproduced exactly from the record.

    `n_boot_min` is the smallest replicate count that resolves this `alpha`'s tails — see the
    module docstring. It is filled on every path where `alpha` has been validated, including
    the refusal it justifies, and is 0 where `alpha` itself was never accepted (so 0 means
    "not determined", never "one replicate is enough"). A value of 0 alongside
    `invalid_resample_count` means no legal replicate count resolves that `alpha` at all.
    """

    var status: Int
    var present: Bool
    var point: Float64
    var lo: Float64
    var hi: Float64
    var alpha: Float64
    var metric_id: Int
    var n: Int
    var n_boot: Int
    var n_boot_min: Int
    var seed: Int
    var bins_used: Int
    var bin_policy: Int
    var n_draws: Int
    var distinct_replicates: Int
    var point_inside: Bool

    def __init__(
        out self, status: Int, metric_id: Int, n: Int, n_boot: Int, seed: Int
    ):
        self.status = status
        self.present = False
        self.point = 0.0
        self.lo = 0.0
        self.hi = 0.0
        self.alpha = 0.0
        self.metric_id = metric_id
        self.n = n
        self.n_boot = n_boot
        self.n_boot_min = 0
        self.seed = seed
        self.bins_used = 0
        self.bin_policy = -1
        self.n_draws = 0
        self.distinct_replicates = 0
        self.point_inside = False


def bootstrap_draw_index(replicate: Int, sample: Int, n: Int) -> Int:
    """The Philox `draw_index` for sample `sample` of replicate `replicate`: `b * n + i`.

    Exposed rather than inlined so a test can assert the coordinate map is injective — the
    property that makes "the seed reaches every draw" true — instead of inferring it from
    the outputs. Returns -1 for a negative argument, which is not a coordinate.

    @capability bootstrap_draw_index
    complexity: O(1)
    counts: none
    @endcapability
    """
    if replicate < 0 or sample < 0 or n <= 0:
        return -1
    if sample >= n:
        return -1
    return replicate * n + sample


def bootstrap_min_replicates(alpha: Float64) -> Int:
    """The smallest `n_boot` whose replicate distribution resolves `alpha`'s tails.

    `n_boot * alpha >= 2`, i.e. the requested tail probability `alpha/2` is at least the
    `1/n_boot` resolution of an empirical distribution of `n_boot` values. Returns 40 for
    alpha = 0.05 and 20 for alpha = 0.10.

    Returns 0 — meaning "no legal count resolves this" — for an `alpha` so small that even
    `EVAL_MAX_RESAMPLES` replicates cannot reach its tails, and for an `alpha` outside the
    open interval (0, 1) or non-finite, which is not a tail probability at all. 0 is never a
    valid answer (`n_boot >= 1` always), so it cannot be mistaken for one.

    Public so a caller can size its own request instead of discovering the bound by being
    refused, and so `test_evaluation_resample.mojo` can assert the boundary from outside.

    The bound is evaluated as the product `Float64(k) * alpha >= 2.0`, on the caller's own
    `alpha`, rather than as `ceil(2/alpha)`: `fl(2/0.4)` is 5.000000000000001, so the
    quotient form would demand 6 replicates where `5 * 0.4 == 2.0` exactly satisfies the
    condition. The truncated quotient is used only as a STARTING point and is then walked to
    the true boundary, at most `MIN_REPLICATE_WALK` steps in either direction — bounded by
    construction, because an unbounded search inside a kernel is a hang.

    @capability bootstrap_min_replicates
    complexity: O(1)
    counts: none
    @endcapability
    """
    comptime MIN_REPLICATE_WALK: Int = 4
    if not eval_finite(alpha) or alpha <= 0.0 or alpha >= 1.0:
        return 0
    if Float64(EVAL_MAX_RESAMPLES) * alpha < 2.0:
        return 0
    # `alpha >= 2 / EVAL_MAX_RESAMPLES` holds here, so `2.0 / alpha <= EVAL_MAX_RESAMPLES`
    # and the conversion cannot overflow.
    var candidate = Int(2.0 / alpha)
    if candidate < 1:
        candidate = 1
    for _ in range(MIN_REPLICATE_WALK):
        if Float64(candidate) * alpha >= 2.0:
            break
        candidate += 1
    for _ in range(MIN_REPLICATE_WALK):
        if candidate <= 1:
            break
        if Float64(candidate - 1) * alpha < 2.0:
            break
        candidate -= 1
    return candidate


def _distinct_sorted(sorted_values: List[Float64]) -> Int:
    """Number of distinct values in an ascending list. Exact `!=`, no tolerance.

    A tolerance here would report a collapsed replicate distribution as merely tightly
    clustered, which is the opposite of what the diagnostic exists to detect.
    """
    var total = len(sorted_values)
    if total == 0:
        return 0
    var distinct = 1
    for i in range(1, total):
        if sorted_values[i] != sorted_values[i - 1]:
            distinct += 1
    return distinct


def bootstrap_metric_ci_flat(
    probs: List[Float64], labels: List[Float64], n: Int, metric_id: Int,
    n_bins: Int, policy: Int, n_boot: Int, alpha: Float64, seed: Int
) -> MetricCI:
    """Percentile bootstrap CI on any metric this package computes. Reproducible from `seed`.

    Pairs are resampled TOGETHER — `(probs[k], labels[k])` for one drawn index `k` — so the
    dependence between a prediction and its label is preserved. Resampling them
    independently would destroy the very association every metric here measures.

    Refusals, all typed, none of which can abort the worker:
      * `metric_id` outside the vocabulary
      * the `eval_pairs_status` contract (count past either list, non-finite, probability
        outside [0, 1], non-binary label, empty, over the sample ceiling)
      * the `eval_bins_status` contract (bin count, unknown policy)
      * `n_boot` below 1 or above `EVAL_MAX_RESAMPLES`
      * `alpha` non-finite or outside the open interval (0, 1)
      * a negative `seed` — refused rather than reinterpreted as a large unsigned value,
        so a caller's record of the seed always reproduces the run
      * `n_boot * alpha < 2` — the requested tail is finer than the replicate distribution can
        resolve, so there is no percentile to report and a narrow interval would be a
        fabrication. `n_boot_min` says what to ask for instead. See the module docstring for
        the measured width-zero "95% CI" this refuses.
      * `n_boot * (n * per_draw_factor + bins)` over `EVAL_MAX_RESAMPLE_WORK`, by division

    @capability bootstrap_metric_ci_flat
    complexity: O(n_boot * n log n)
    counts:
    - n <= len(probs, labels) [kernel_validated]
    - dim n_bins [kernel_validated]
    - dim n_boot [kernel_validated]
    @endcapability

    `n_bins` is bounded by `contract.EVAL_MAX_BINS` and `n_boot` by
    `contract.EVAL_MAX_RESAMPLES`, both checked above. Neither ceiling is written as a
    declared bound because a declared ceiling must name a `comptime` constant in the SAME
    file, and copying the value here is exactly the drift rule 3 warns about — the constants
    stay in `contract.mojo`, which is the one place they are defined.
    """
    if metric_id < 0 or metric_id > EVAL_METRIC_ECE:
        return MetricCI(EVAL_ERR_UNKNOWN_METRIC, metric_id, n, n_boot, seed)
    var pair_status = eval_pairs_status(probs, labels, n)
    if pair_status != EVAL_OK:
        return MetricCI(pair_status, metric_id, n, n_boot, seed)
    var bin_status = eval_bins_status(n_bins, policy)
    if bin_status != EVAL_OK:
        return MetricCI(bin_status, metric_id, n, n_boot, seed)
    if n_boot < 1 or n_boot > EVAL_MAX_RESAMPLES:
        return MetricCI(EVAL_ERR_RESAMPLE_COUNT, metric_id, n, n_boot, seed)
    if not eval_finite(alpha) or alpha <= 0.0 or alpha >= 1.0:
        return MetricCI(EVAL_ERR_ALPHA_RANGE, metric_id, n, n_boot, seed)
    if seed < 0:
        return MetricCI(EVAL_ERR_SEED_NEGATIVE, metric_id, n, n_boot, seed)
    # `alpha` is valid from here on, so every remaining return reports the resolvable minimum.
    var min_boot = bootstrap_min_replicates(alpha)
    if Float64(n_boot) * alpha < 2.0:
        var unresolved = MetricCI(
            EVAL_ERR_RESAMPLE_COUNT, metric_id, n, n_boot, seed
        )
        unresolved.alpha = alpha
        unresolved.n_boot_min = min_boot
        return unresolved^
    if not eval_resample_work_fits(n_boot, n, n_bins, metric_id, policy):
        var over_budget = MetricCI(
            EVAL_ERR_WORK_BUDGET, metric_id, n, n_boot, seed
        )
        over_budget.alpha = alpha
        over_budget.n_boot_min = min_boot
        return over_budget^

    var point = metric_value_flat(probs, labels, n, metric_id, n_bins, policy)
    if not point.present:
        var no_point = MetricCI(point.status, metric_id, n, n_boot, seed)
        no_point.alpha = alpha
        no_point.n_boot_min = min_boot
        return no_point^

    var out = MetricCI(EVAL_OK, metric_id, n, n_boot, seed)
    out.alpha = alpha
    out.n_boot_min = min_boot
    out.bins_used = point.bins_used
    out.bin_policy = point.bin_policy
    out.point = point.value
    out.n_draws = n_boot * n

    var stream = stream_id(EVAL_BOOTSTRAP_STREAM_NAME)
    var master = UInt64(seed)
    var rep_probs = List[Float64](capacity=n)
    var rep_labels = List[Float64](capacity=n)
    for _ in range(n):
        rep_probs.append(0.0)
        rep_labels.append(0.0)

    var replicates = List[Float64](capacity=n_boot)
    for b in range(n_boot):
        for i in range(n):
            var draw = UInt64(b * n + i)
            var k = uniform_int_keyed(0, n - 1, master, stream, draw)
            # `uniform_int_keyed` is documented to return a value in [low, high]; the clamp
            # is kept anyway because `rep_probs[k]` is a subscript and a subscript out of
            # range is an uncatchable process abort, not an exception. A guard on a
            # subscript is never redundant.
            if k < 0:
                k = 0
            if k >= n:
                k = n - 1
            rep_probs[i] = probs[k]
            rep_labels[i] = labels[k]
        var replicate = metric_value_flat(
            rep_probs, rep_labels, n, metric_id, n_bins, policy
        )
        if not replicate.present:
            # A replicate of validated data is validated data, so this cannot happen for
            # the metrics in the vocabulary. Returning the replicate's own status rather
            # than a partial interval means that if it ever does, the caller sees why
            # instead of an interval built from fewer replicates than it claims.
            var bad_replicate = MetricCI(
                replicate.status, metric_id, n, n_boot, seed
            )
            bad_replicate.alpha = alpha
            bad_replicate.n_boot_min = min_boot
            return bad_replicate^
        replicates.append(replicate.value)

    var sorted_reps = heapsort(replicates)
    out.distinct_replicates = _distinct_sorted(sorted_reps)
    var half = alpha / 2.0
    out.lo = quantile(sorted_reps, n_boot, half)
    out.hi = quantile(sorted_reps, n_boot, 1.0 - half)
    out.point_inside = out.point >= out.lo and out.point <= out.hi
    out.present = True
    return out^
