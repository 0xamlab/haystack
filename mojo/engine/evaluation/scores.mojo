"""
evaluation.scores — Brier with its decomposition, log-loss, ECE, reliability data, and one
driver over all of them. Zero Python imports.

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
golden_vectors: mojo/tests/libs/test_evaluation_scores.mojo
benchmark: benchmarks/mojo_benchmarks/bench_evaluation.mojo
docs: gitbook/engine/evaluation-calibration.md
version_introduced: unreleased
deprecation_state: active
@endcapability

Every number here comes from a frozen kernel
--------------------------------------------
  (p - y)^2 per sample                 ml_metrics_extended.brier_score_term
  |acc - conf| * n_bin / n per bin     ml_metrics_extended.calibration_ece_term
  -(y log p + (1-y) log(1-p))          loss_functions.binary_cross_entropy
  equal-width bins on [0, 1]           calibration.calibration_curve (via evaluation.binning)

What this module adds is aggregation, one status, an explicit binning that travels with the
result, and the absent/present split.

The Brier decomposition, and why the residual is REPORTED
--------------------------------------------------------
Murphy's decomposition is usually printed as an identity:

    BS = reliability - resolution + uncertainty

with `reliability = (1/n) sum_b n_b (conf_b - obs_b)^2`,
`resolution = (1/n) sum_b n_b (obs_b - obs)^2` and `uncertainty = obs (1 - obs)`.

It is an identity only when every prediction inside a bin is IDENTICAL. With any real
binning the exact statement is

    BS = reliability - resolution + uncertainty + within_bin_variance
         - 2 * within_bin_covariance

so the three printed terms do not add up to the Brier score, and by an amount that depends
entirely on how coarse the bins are. Almost every implementation hides this. This one
computes `residual = BS - (reliability - resolution + uncertainty)` and returns it, plus
`decomposition_closes` for whether the residual is inside the floating-point error of the
sum itself. A non-zero residual is not a bug — it is the measure of how much the
decomposition is being smoothed by the binning, and it is exactly the number a reader needs
before quoting a reliability term.

`decomposition_closes` uses a tolerance built from the forward error of THIS expression:
`4 * DBL_EPSILON * (n * BS + occupied * (reliability + resolution) + uncertainty)`, because a
sum of `n` non-negative terms carries error up to `n * eps` times its own value, and the two
bin sums carry `occupied * eps` times theirs. Every magnitude in that bound is an operand of
the expression being judged (rule 4b: the tolerance for a quantity comes from that
quantity's own magnitude — here the quantity IS the aggregate, and its operands are its own
error sources). No sample's tolerance is scaled by another sample's magnitude, no caller
tolerance is multiplied by a magnitude, and there is no additive 1.0 floor to dominate the
real scale.

Log-loss: clamped, and it SAYS SO
---------------------------------
Log-loss of a probability of exactly 0 for a positive label is infinite, and an infinity in
a metric field is worse than useless: the dispatch refuses a non-finite value rather than
serialising it, so one saturated prediction would turn the entire response into a transport
error. The frozen `binary_cross_entropy` clamps p into [1e-7, 1 - 1e-7]. That behaviour is
kept, and `LogLossResult` adds the two things it does not report — the epsilon by name and
how many samples were clamped. A log-loss with `clamped_count > 0` is a censored number and
a caller can now see that.

ECE never travels without its binning
-------------------------------------
`bins_used` and `bin_policy` are fields of every result that contains an `ece`, and
`evaluation.contract.eval_ece_comparable` is the predicate for whether two of them may be
compared. Measured on p = [0.2, 0.4, 0.6, 0.8], y = [0, 1, 0, 1]: ECE is 0.2 with 2
equal-width bins and 0.4 with 4. Both are correct; they are not the same statistic.

Public API:
  MetricValue                  — one scalar metric plus status and binning provenance
  BrierDecomposition           — Brier, its three terms, and the residual
  LogLossResult                — log-loss, the clamp epsilon, and the clamped count
  CalibrationErrorResult       — ECE, MCE, bin count, policy, occupancy
  ReliabilityDiagram           — per-bin plot data with an explicit present flag
  EvalReport                   — every scalar above from ONE pass and ONE binning
  metric_value_flat(...)       — one metric by id; the bootstrap and the gates call this
  brier_decomposition_flat(...)
  log_loss_flat(...)
  calibration_error_flat(...)
  reliability_diagram_flat(...)
  evaluate_flat(...)
"""

from std.math import abs as fabs

from loss_functions import binary_cross_entropy
from ml_metrics_extended import brier_score_term, calibration_ece_term

from evaluation.binning import EvalBins, eval_bins_build
from evaluation.contract import (
    EVAL_DBL_EPSILON,
    EVAL_ERR_NO_OCCUPIED_BINS,
    EVAL_ERR_UNKNOWN_METRIC,
    EVAL_LOG_LOSS_EPS,
    EVAL_METRIC_ACCURACY,
    EVAL_METRIC_BASE_RATE,
    EVAL_METRIC_BRIER,
    EVAL_METRIC_ECE,
    EVAL_METRIC_LOG_LOSS,
    EVAL_OK,
    eval_bins_status,
    eval_pairs_status,
)

comptime EVAL_ACCURACY_THRESHOLD: Float64 = 0.5
"""The decision threshold for `EVAL_METRIC_ACCURACY`, fixed and stated.

Accuracy is not a property of a probabilistic forecast until a threshold is chosen, and a
threshold hidden inside a metric is how two "accuracies" come to disagree. 0.5 is the
convention; it is written here so that it is quotable, and a caller who needs a different
operating point wants a precision/recall surface rather than this number."""


# ── result structs — all declared in THIS file ────────────────────────────────
# A struct owned by another module is silently DROPPED from the runtime contract along with
# every function mentioning it, so each public result type lives beside its driver.


struct MetricValue(Copyable, Movable):
    """One scalar metric, its status, and the binning it was computed under.

    `present == False` means the metric does not exist for this input; `value` is then 0.0
    because a struct field must hold a representable Float64, and that 0.0 is not a
    measurement. `bins_used`/`bin_policy` are 0/-1 for metrics that do not bin, so a
    reader cannot mistake a Brier score for something with a binning provenance.
    """

    var status: Int
    var present: Bool
    var value: Float64
    var metric_id: Int
    var n: Int
    var bins_used: Int
    var bin_policy: Int

    def __init__(out self, status: Int, metric_id: Int, n: Int):
        self.status = status
        self.present = False
        self.value = 0.0
        self.metric_id = metric_id
        self.n = n
        self.bins_used = 0
        self.bin_policy = -1


struct BrierDecomposition(Copyable, Movable):
    """Brier score, Murphy's three terms, and the residual the identity leaves behind."""

    var status: Int
    var present: Bool
    var brier: Float64
    var reliability: Float64
    var resolution: Float64
    var uncertainty: Float64
    var base_rate: Float64
    var residual: Float64
    var decomposition_closes: Bool
    var n: Int
    var bins_used: Int
    var bins_occupied: Int
    var bin_policy: Int

    def __init__(out self, status: Int, n: Int, n_bins: Int, policy: Int):
        self.status = status
        self.present = False
        self.brier = 0.0
        self.reliability = 0.0
        self.resolution = 0.0
        self.uncertainty = 0.0
        self.base_rate = 0.0
        self.residual = 0.0
        self.decomposition_closes = False
        self.n = n
        self.bins_used = n_bins
        self.bins_occupied = 0
        self.bin_policy = policy


struct LogLossResult(Copyable, Movable):
    """Log-loss with the clamp made visible.

    `eps_used` is the epsilon the frozen kernel clamps with; `clamped_count` is how many of
    the `n` samples were inside `eps` of 0 or 1 and therefore censored. A `log_loss` with
    `clamped_count > 0` is a lower bound on an infinite quantity, not a measurement of it.
    """

    var status: Int
    var present: Bool
    var log_loss: Float64
    var eps_used: Float64
    var clamped_count: Int
    var n: Int

    def __init__(out self, status: Int, n: Int):
        self.status = status
        self.present = False
        self.log_loss = 0.0
        self.eps_used = EVAL_LOG_LOSS_EPS
        self.clamped_count = 0
        self.n = n


struct CalibrationErrorResult(Copyable, Movable):
    """Expected and maximum calibration error, inseparable from their binning."""

    var status: Int
    var present: Bool
    var ece: Float64
    var mce: Float64
    var n: Int
    var bins_used: Int
    var bins_occupied: Int
    var bin_policy: Int

    def __init__(out self, status: Int, n: Int, n_bins: Int, policy: Int):
        self.status = status
        self.present = False
        self.ece = 0.0
        self.mce = 0.0
        self.n = n
        self.bins_used = n_bins
        self.bins_occupied = 0
        self.bin_policy = policy


struct ReliabilityDiagram(Copyable, Movable):
    """Per-bin reliability plot data, with occupancy stated rather than implied.

    `bin_present[b]` is the answer to "did this bin carry data". Where it is `False`,
    `bin_conf[b]` and `bin_freq[b]` are 0.0 and mean nothing. The frozen
    `calibration.calibration_curve` returns 0.0 for an empty bin with no flag beside it,
    so a plot built directly from it draws an empty bin as a perfectly-calibrated point at
    zero observed frequency. That is the specific wrong picture this struct exists to
    prevent.
    """

    var status: Int
    var n: Int
    var bins_used: Int
    var bins_occupied: Int
    var bin_policy: Int
    var bin_lo: List[Float64]
    var bin_hi: List[Float64]
    var bin_conf: List[Float64]
    var bin_freq: List[Float64]
    var bin_count: List[Int]
    var bin_present: List[Bool]

    def __init__(out self, status: Int, n: Int, n_bins: Int, policy: Int):
        self.status = status
        self.n = n
        self.bins_used = n_bins
        self.bins_occupied = 0
        self.bin_policy = policy
        self.bin_lo = List[Float64]()
        self.bin_hi = List[Float64]()
        self.bin_conf = List[Float64]()
        self.bin_freq = List[Float64]()
        self.bin_count = List[Int]()
        self.bin_present = List[Bool]()


struct EvalReport(Copyable, Movable):
    """Every scalar in this module from ONE pass over the data and ONE binning.

    The point of a single driver is that the numbers are mutually consistent: the Brier
    score in `brier` is the same aggregation the decomposition is built from, and the `ece`
    is binned exactly as `reliability` is. A caller assembling these from separate calls can
    silently mix bin counts, which is how two internally-inconsistent calibration claims end
    up in one report.
    """

    var status: Int
    var n: Int
    var bins_used: Int
    var bins_occupied: Int
    var bin_policy: Int
    var base_rate: Float64
    var accuracy: Float64
    var accuracy_threshold: Float64
    var brier: Float64
    var brier_present: Bool
    var reliability: Float64
    var resolution: Float64
    var uncertainty: Float64
    var residual: Float64
    var decomposition_closes: Bool
    var log_loss: Float64
    var log_loss_present: Bool
    var log_loss_eps: Float64
    var log_loss_clamped: Int
    var ece: Float64
    var mce: Float64
    var ece_present: Bool

    def __init__(out self, status: Int, n: Int, n_bins: Int, policy: Int):
        self.status = status
        self.n = n
        self.bins_used = n_bins
        self.bins_occupied = 0
        self.bin_policy = policy
        self.base_rate = 0.0
        self.accuracy = 0.0
        self.accuracy_threshold = EVAL_ACCURACY_THRESHOLD
        self.brier = 0.0
        self.brier_present = False
        self.reliability = 0.0
        self.resolution = 0.0
        self.uncertainty = 0.0
        self.residual = 0.0
        self.decomposition_closes = False
        self.log_loss = 0.0
        self.log_loss_present = False
        self.log_loss_eps = EVAL_LOG_LOSS_EPS
        self.log_loss_clamped = 0
        self.ece = 0.0
        self.mce = 0.0
        self.ece_present = False


# ── internal aggregations, each over a frozen per-item kernel ─────────────────


def _brier_mean(probs: List[Float64], labels: List[Float64], n: Int) -> Float64:
    """Mean of the frozen `brier_score_term`. `n` is pre-validated `<= len(...)`."""
    var total = 0.0
    for i in range(n):
        total += brier_score_term(probs[i], labels[i])
    return total / Float64(n)


def _base_rate(labels: List[Float64], n: Int) -> Float64:
    """Observed positive rate. Labels are pre-validated to be exactly 0.0 or 1.0."""
    var total = 0.0
    for i in range(n):
        total += labels[i]
    return total / Float64(n)


def _accuracy_at_threshold(
    probs: List[Float64], labels: List[Float64], n: Int
) -> Float64:
    """Fraction of samples whose thresholded prediction equals the label."""
    var hits = 0
    for i in range(n):
        var predicted_positive = probs[i] >= EVAL_ACCURACY_THRESHOLD
        var actually_positive = labels[i] == 1.0
        if predicted_positive == actually_positive:
            hits += 1
    return Float64(hits) / Float64(n)


def _ece_of_bins(bins: EvalBins) -> Float64:
    """Sum of the frozen `calibration_ece_term` over the partition."""
    var total = 0.0
    for b in range(len(bins.count)):
        total += calibration_ece_term(
            bins.mean_prob[b],
            bins.mean_label[b],
            Float64(bins.count[b]),
            Float64(bins.n),
        )
    return total


def _mce_of_bins(bins: EvalBins) -> Float64:
    """Largest |observed - predicted| over OCCUPIED bins only.

    An empty bin holds 0.0 in both slots, so including it would contribute a gap of zero —
    harmless for a maximum, and still wrong to read as a measurement. The occupancy test is
    written out so the intent survives a future change to the maximum.
    """
    var worst = 0.0
    for b in range(len(bins.count)):
        if bins.count[b] > 0:
            var gap = fabs(bins.mean_label[b] - bins.mean_prob[b])
            if gap > worst:
                worst = gap
    return worst


def _log_loss_parts(
    probs: List[Float64], labels: List[Float64], n: Int
) -> List[Float64]:
    """`[mean log-loss, clamped sample count]` from the frozen `binary_cross_entropy`.

    Returned as a two-element list rather than a struct because it is internal and the
    caller unpacks it immediately; the public surface is `LogLossResult`.
    """
    var total = 0.0
    var clamped = 0
    for i in range(n):
        var p = probs[i]
        if p < EVAL_LOG_LOSS_EPS or p > 1.0 - EVAL_LOG_LOSS_EPS:
            clamped += 1
        total += binary_cross_entropy(labels[i], p)
    var out = List[Float64](capacity=2)
    out.append(total / Float64(n))
    out.append(Float64(clamped))
    return out^


def _residual_tolerance(
    brier: Float64,
    reliability: Float64,
    resolution: Float64,
    uncertainty: Float64,
    n: Int,
    occupied: Int,
) -> Float64:
    """Forward floating-point error of `brier - (reliability - resolution + uncertainty)`.

    A sum of `k` non-negative terms is computed with relative error up to `k * eps`, so the
    Brier mean carries `n * eps * brier` and each bin sum carries `occupied * eps` times its
    own value. Every magnitude here is an OPERAND of the expression being judged — this is
    the error bound of that one arithmetic expression, not a scale borrowed from unrelated
    items, and there is no additive floor to dominate it when the values are small.
    """
    var scale = (
        Float64(n) * brier
        + Float64(occupied) * (reliability + resolution)
        + uncertainty
    )
    return 4.0 * EVAL_DBL_EPSILON * scale


# ── public drivers ────────────────────────────────────────────────────────────


def brier_decomposition_flat(
    probs: List[Float64], labels: List[Float64], n: Int, n_bins: Int, policy: Int
) -> BrierDecomposition:
    """Brier score with Murphy's reliability / resolution / uncertainty and the residual.

    The Brier score itself is binning-free: it is the mean of the frozen
    `brier_score_term`. The three decomposition terms are binning-dependent, which is why
    `bins_used`, `bin_policy` and `bins_occupied` are returned beside them, and why
    `residual` is returned at all — see the module docstring.

    `present` covers the whole result: on a refusal every field is 0.0/False and the status
    names the reason.

    @capability brier_decomposition_flat
    complexity: O(n log n + h)
    counts:
    - n <= len(probs, labels) [kernel_validated]
    - dim n_bins [kernel_validated]
    @endcapability
    """
    var bins = eval_bins_build(probs, labels, n, n_bins, policy)
    if bins.status != EVAL_OK:
        return BrierDecomposition(bins.status, n, n_bins, policy)
    if bins.occupied == 0:
        return BrierDecomposition(EVAL_ERR_NO_OCCUPIED_BINS, n, n_bins, policy)

    var out = BrierDecomposition(EVAL_OK, n, n_bins, policy)
    out.bins_occupied = bins.occupied
    out.brier = _brier_mean(probs, labels, n)
    out.base_rate = _base_rate(labels, n)
    out.uncertainty = out.base_rate * (1.0 - out.base_rate)

    var rel = 0.0
    var res = 0.0
    for b in range(n_bins):
        if bins.count[b] > 0:
            var weight = Float64(bins.count[b])
            var gap = bins.mean_prob[b] - bins.mean_label[b]
            rel += weight * gap * gap
            var lift = bins.mean_label[b] - out.base_rate
            res += weight * lift * lift
    out.reliability = rel / Float64(n)
    out.resolution = res / Float64(n)
    out.residual = out.brier - (
        out.reliability - out.resolution + out.uncertainty
    )
    var tol = _residual_tolerance(
        out.brier,
        out.reliability,
        out.resolution,
        out.uncertainty,
        n,
        bins.occupied,
    )
    out.decomposition_closes = fabs(out.residual) <= tol
    out.present = True
    return out^


def log_loss_flat(
    probs: List[Float64], labels: List[Float64], n: Int
) -> LogLossResult:
    """Mean log-loss from the frozen `binary_cross_entropy`, with the clamp reported.

    The kernel clamps p into `[EVAL_LOG_LOSS_EPS, 1 - EVAL_LOG_LOSS_EPS]`, so the returned
    value is always finite and never an infinity in a metric field. `eps_used` names the
    clamp and `clamped_count` says how many samples hit it. Both are the information a
    caller needs to know the number is censored, and neither is available from the frozen
    kernel alone.

    Takes no binning: log-loss is a per-sample loss and has none.

    @capability log_loss_flat
    complexity: O(n)
    counts:
    - n <= len(probs, labels) [kernel_validated]
    @endcapability
    """
    var status = eval_pairs_status(probs, labels, n)
    if status != EVAL_OK:
        return LogLossResult(status, n)
    var out = LogLossResult(EVAL_OK, n)
    var parts = _log_loss_parts(probs, labels, n)
    out.log_loss = parts[0]
    out.clamped_count = Int(parts[1])
    out.present = True
    return out^


def calibration_error_flat(
    probs: List[Float64], labels: List[Float64], n: Int, n_bins: Int, policy: Int
) -> CalibrationErrorResult:
    """Expected and maximum calibration error under an EXPLICIT binning policy.

    ECE is the frozen `calibration_ece_term` summed over the partition built by
    `evaluation.binning`; MCE is the largest per-bin gap over occupied bins. The bin count
    and policy are arguments, not defaults, and they come back in the result: two ECEs
    computed under different binnings are different statistics, and
    `eval_ece_comparable` is the predicate that says whether they may be compared.

    @capability calibration_error_flat
    complexity: O(n log n + h)
    counts:
    - n <= len(probs, labels) [kernel_validated]
    - dim n_bins [kernel_validated]
    @endcapability
    """
    var bins = eval_bins_build(probs, labels, n, n_bins, policy)
    if bins.status != EVAL_OK:
        return CalibrationErrorResult(bins.status, n, n_bins, policy)
    if bins.occupied == 0:
        return CalibrationErrorResult(
            EVAL_ERR_NO_OCCUPIED_BINS, n, n_bins, policy
        )
    var out = CalibrationErrorResult(EVAL_OK, n, n_bins, policy)
    out.bins_occupied = bins.occupied
    out.ece = _ece_of_bins(bins)
    out.mce = _mce_of_bins(bins)
    out.present = True
    return out^


def reliability_diagram_flat(
    probs: List[Float64], labels: List[Float64], n: Int, n_bins: Int, policy: Int
) -> ReliabilityDiagram:
    """Per-bin reliability data with an explicit `bin_present` flag per bin.

    This is the plot data for a calibration curve. It differs from the frozen
    `calibration.calibration_curve` in three ways that all matter to a plot: bin EDGES
    rather than centres (so a quantile binning can be drawn at all), a mean PREDICTION per
    bin (the x coordinate of a reliability point is the mean forecast, not the bin centre),
    and `bin_present`, so an empty bin is not drawn as a perfectly-calibrated point at zero.

    Because the edges are what this function ADDS over the frozen kernel, they are the thing
    most worth being exact about. `bin_lo[b]` and `bin_hi[b]` come from `evaluation.binning`
    and are boundaries of the partition that was applied: `bin_lo[b]` is itself assigned to
    bin `b`, and `bin_hi[b]` is the identical Float64 to `bin_lo[b+1]`. The x-interval drawn
    for a bin therefore contains every sample counted in it — an interval computed as `b/h`
    does not, at some bin counts, which would draw a bin excluding one of its own members.

    On a refusal every list is empty; there is no partially-filled diagram.

    @capability reliability_diagram_flat
    complexity: O(n log n + h)
    counts:
    - n <= len(probs, labels) [kernel_validated]
    - dim n_bins [kernel_validated]
    @endcapability
    """
    var bins = eval_bins_build(probs, labels, n, n_bins, policy)
    if bins.status != EVAL_OK:
        return ReliabilityDiagram(bins.status, n, n_bins, policy)
    var out = ReliabilityDiagram(EVAL_OK, n, n_bins, policy)
    out.bins_occupied = bins.occupied
    for b in range(n_bins):
        out.bin_lo.append(bins.lo[b])
        out.bin_hi.append(bins.hi[b])
        out.bin_count.append(bins.count[b])
        if bins.count[b] > 0:
            out.bin_present.append(True)
            out.bin_conf.append(bins.mean_prob[b])
            out.bin_freq.append(bins.mean_label[b])
        else:
            out.bin_present.append(False)
            out.bin_conf.append(0.0)
            out.bin_freq.append(0.0)
    return out^


def metric_value_flat(
    probs: List[Float64], labels: List[Float64], n: Int, metric_id: Int,
    n_bins: Int, policy: Int
) -> MetricValue:
    """One scalar metric selected by `metric_id`. The bootstrap and the gates call this.

    A metric is selected by integer because a function value cannot cross a JSON frame. An
    unrecognised id is REFUSED with `EVAL_ERR_UNKNOWN_METRIC` and never defaulted: an
    aggregation that silently becomes metric 0 produces a plausible wrong number, which is
    the single worst outcome for an evaluation surface.

    `n_bins`/`policy` are validated for every metric, including the ones that do not bin, so
    a caller cannot get a Brier score out of a request whose binning arguments were
    nonsense and then reuse those arguments for an ECE. The returned `bins_used` and
    `bin_policy` are 0/-1 for the non-binning metrics, so provenance is never implied where
    there is none.

    @capability metric_value_flat
    complexity: O(n log n + h)
    counts:
    - n <= len(probs, labels) [kernel_validated]
    - dim n_bins [kernel_validated]
    @endcapability
    """
    if metric_id < 0 or metric_id > EVAL_METRIC_ECE:
        return MetricValue(EVAL_ERR_UNKNOWN_METRIC, metric_id, n)
    var pair_status = eval_pairs_status(probs, labels, n)
    if pair_status != EVAL_OK:
        return MetricValue(pair_status, metric_id, n)
    var bin_status = eval_bins_status(n_bins, policy)
    if bin_status != EVAL_OK:
        return MetricValue(bin_status, metric_id, n)

    var out = MetricValue(EVAL_OK, metric_id, n)
    if metric_id == EVAL_METRIC_BRIER:
        out.value = _brier_mean(probs, labels, n)
        out.present = True
        return out^
    if metric_id == EVAL_METRIC_LOG_LOSS:
        var parts = _log_loss_parts(probs, labels, n)
        out.value = parts[0]
        out.present = True
        return out^
    if metric_id == EVAL_METRIC_ACCURACY:
        out.value = _accuracy_at_threshold(probs, labels, n)
        out.present = True
        return out^
    if metric_id == EVAL_METRIC_BASE_RATE:
        out.value = _base_rate(labels, n)
        out.present = True
        return out^
    # EVAL_METRIC_ECE — the only branch with a binning provenance to report.
    var bins = eval_bins_build(probs, labels, n, n_bins, policy)
    if bins.status != EVAL_OK:
        return MetricValue(bins.status, metric_id, n)
    if bins.occupied == 0:
        return MetricValue(EVAL_ERR_NO_OCCUPIED_BINS, metric_id, n)
    out.value = _ece_of_bins(bins)
    out.bins_used = n_bins
    out.bin_policy = policy
    out.present = True
    return out^


def evaluate_flat(
    probs: List[Float64], labels: List[Float64], n: Int, n_bins: Int, policy: Int
) -> EvalReport:
    """The unified driver: every scalar in this module, one pass, one binning.

    This is the entry point the family was missing. Nothing in the frozen tree turns a
    predictions-and-labels pair into a complete evaluation: `brier_score_term` scores one
    sample, `calibration_ece_term` scores one bin, `binary_cross_entropy` scores one sample,
    and `calibration_curve` bins without reporting confidence. Assembling them per call site
    is how two numbers in one report come to be binned differently.

    Every value slot is representable even when its `*_present` flag is False — a raw
    non-finite in any field makes the WHOLE response a typed transport error, so absence is
    carried by the flag and never by a sentinel value.

    @capability evaluate_flat
    complexity: O(n log n + h)
    counts:
    - n <= len(probs, labels) [kernel_validated]
    - dim n_bins [kernel_validated]
    @endcapability
    """
    var bins = eval_bins_build(probs, labels, n, n_bins, policy)
    if bins.status != EVAL_OK:
        return EvalReport(bins.status, n, n_bins, policy)
    if bins.occupied == 0:
        return EvalReport(EVAL_ERR_NO_OCCUPIED_BINS, n, n_bins, policy)

    var out = EvalReport(EVAL_OK, n, n_bins, policy)
    out.bins_occupied = bins.occupied
    out.base_rate = _base_rate(labels, n)
    out.accuracy = _accuracy_at_threshold(probs, labels, n)
    out.brier = _brier_mean(probs, labels, n)
    out.brier_present = True
    out.uncertainty = out.base_rate * (1.0 - out.base_rate)

    var rel = 0.0
    var res = 0.0
    for b in range(n_bins):
        if bins.count[b] > 0:
            var weight = Float64(bins.count[b])
            var gap = bins.mean_prob[b] - bins.mean_label[b]
            rel += weight * gap * gap
            var lift = bins.mean_label[b] - out.base_rate
            res += weight * lift * lift
    out.reliability = rel / Float64(n)
    out.resolution = res / Float64(n)
    out.residual = out.brier - (
        out.reliability - out.resolution + out.uncertainty
    )
    out.decomposition_closes = fabs(out.residual) <= _residual_tolerance(
        out.brier, out.reliability, out.resolution, out.uncertainty, n,
        bins.occupied,
    )

    var parts = _log_loss_parts(probs, labels, n)
    out.log_loss = parts[0]
    out.log_loss_clamped = Int(parts[1])
    out.log_loss_present = True

    out.ece = _ece_of_bins(bins)
    out.mce = _mce_of_bins(bins)
    out.ece_present = True
    return out^
