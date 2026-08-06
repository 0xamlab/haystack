"""
evaluation.binning — the binning engine behind every calibration number here. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int
backend: mojo
surfaces: library_execute, batch_execute
complexity: O(n log n)
golden_vectors: mojo/tests/libs/test_evaluation_binning.mojo
benchmark: benchmarks/mojo_benchmarks/bench_evaluation.mojo
docs: gitbook/engine/evaluation-calibration.md
version_introduced: unreleased
deprecation_state: active
@endcapability

One binning, used by everything
-------------------------------
Reliability data, expected calibration error and the Brier decomposition are three readings
of the SAME partition of the predictions. If each computed its own partition they would
eventually disagree, and the decomposition identity would stop closing for reasons nobody
could locate. So there is one builder, `eval_bins_build`, and the three drivers in
`evaluation.scores` read its output.

Equal-width binning is NOT reimplemented
----------------------------------------
`calibration.calibration_curve(probs, labels, n_bins)` is frozen, correct, and already
implements equal-width bins on [0, 1] with the last bin closed at 1.0. It is called here
rather than copied. It reports a per-bin mean LABEL and a per-bin count, and calibration
error also needs a per-bin mean PREDICTION, which it does not report.

Rather than write a second bin-assignment loop — which would be a duplicate of the frozen
index rule, free to drift from it — the mean prediction is obtained by calling the same
frozen kernel with the predictions IN THE LABEL POSITION:

    freq = calibration_curve(p, y, h).observed_freq   # mean label per bin
    conf = calibration_curve(p, p, h).observed_freq   # mean prediction per bin

Both calls use one identical assignment rule, because it is literally the same code. The
two count arrays must therefore agree element for element, and `eval_bins_build` checks
that they do — a self-consistency assertion that would catch the frozen kernel changing
underneath this package.

The published boundary is a boundary OF THE PARTITION, not of the real numbers
-----------------------------------------------------------------------------
The frozen kernel reports bin CENTRES; a plot needs EDGES, so the edges are produced here.
Writing them as the arithmetic `b/h` is the obvious thing and it is WRONG, because the
partition is not defined by `b/h` — it is defined by the frozen index rule `Int(p*h)`, and
in Float64 those two are not the same statement. Two measured cases:

    h = 22, b = 15:  fl(15/22) = 0.6818181818181818,  Int(fl(15/22) * 22) = 14
    h =  7, b =  5:  fl(5/7)   = 0.7142857142857143,  Int(fl(5/7)   *  7) =  5   (agrees)

So for h = 22 the double nearest the real number 15/22 is assigned to bin 14, and a kernel
that published it as "the lower boundary of bin 15" would be publishing a value that is on
the wrong side of the boundary it names. A consumer re-binning that edge — which is exactly
what a plotting axis is for — would disagree with `eval_bin_assign_flat` about the same
sample. Writing the edge as `b * (1/h)` instead of `b/h` is worse again: it is a second,
lower-precision approximation, and it misplaces 810 edges over h in [1, 128] against 235
for `b/h`.

`_equal_width_edge` therefore publishes the EXACT lower boundary of the implemented
partition: the smallest Float64 the frozen rule assigns to bin `b`. It starts from `fl(b/h)`
— the correctly-rounded real boundary, and never more than one ulp away from the answer —
and walks at most `EVAL_EDGE_ULP_STEPS` ulps to the crossing. Verified over every legal bin
count h in [1, 4096] and every interior b: one ulp of movement suffices, every published
edge satisfies `Int(edge * h) == b`, every edge is strictly ascending, and the double just
below `edge[b+1]` is assigned to bin `b`. That last property is the strong one: the half-open
intervals `[edge[b], edge[b+1])` are EXACTLY the sets the frozen rule produces, so a binary
search over the published edges reproduces `eval_bin_assign_flat` for every representable
input rather than for most of them.

`_equal_width_index` is the one restatement of the frozen rule, and `_equal_width_edge` is
defined in terms of it, so the boundary rule cannot drift from the assignment rule — they
are not two copies, they are one function and its inverse.

What is genuinely new: equal-count (quantile) bins
--------------------------------------------------
There is no quantile binning anywhere in the frozen tree. It matters because equal-width
bins are empty wherever a model does not predict: a well-trained classifier on an
imbalanced problem puts almost everything below 0.1, and a 10-bin equal-width ECE is then
one occupied bin and nine reports of nothing. Quantile bins put the resolution where the
predictions are.

Edges are order statistics of the predictions themselves, produced by the frozen
`sorting.heapsort` (O(n log n) worst case, non-recursive — `sorting.quicksort` recurses and
`sorting.insertion_sort` is O(n^2)). Bin b covers `[e[b-1], e[b])` with `e[-1]` unbounded
below and `e[h-1]` unbounded above, and a sample is placed by BINARY SEARCH over the edges,
not a linear scan: a scan would be O(n * h) while the declared cost said O(n + h), which is
the "bounding memory is not bounding work" defect.

Ties are not split. Equal predictions land in the same bin whatever the rank boundaries
say, so with heavy ties the bins are NOT equal-count and some are empty. That is reported
as `occupied`, never smoothed over — a bin count that lies about how many bins carried data
is how a reader concludes an ECE is finer-grained than it is.

An empty bin is ABSENT, not zero
--------------------------------
`count[b] == 0` is the only thing that means "this bin has no data". `mean_prob[b]` and
`mean_label[b]` are then 0.0 because a struct field must hold a representable Float64 — the
dispatch refuses a non-finite and would turn the whole response into a transport error — but
that 0.0 is NOT a measurement and no driver here reads it without first testing the count.
The frozen `calibration_curve` has the same convention and documents it.

Public API:
  EvalBins                  — one labelled partition: edges, counts, per-bin means, status
  BinCounts                 — the same partition of UNLABELLED scores: a histogram
  BinAssignment             — per-sample bin index, for a caller doing its own aggregation
  eval_bins_build(...)      — the one builder for labelled data, both policies
  eval_bin_counts_flat(...) — counts only, for scores that have no labels
  eval_bin_assign_flat(...) — per-sample bin index under either policy
  eval_bin_edges_flat(...)  — the h+1 edge values, for plotting an axis
"""

from std.memory import bitcast

from calibration import calibration_curve
from sorting import heapsort

from evaluation.contract import (
    EVAL_BIN_EQUAL_COUNT,
    EVAL_BIN_EQUAL_WIDTH,
    EVAL_ERR_BIN_COUNT,
    EVAL_OK,
    eval_bins_status,
    eval_pairs_status,
    eval_scores_status,
)


comptime EVAL_EDGE_ULP_STEPS: Int = 4
"""How far `_equal_width_edge` may walk from `fl(b/h)` to reach the partition's boundary.

`fl(b/h)` is the correctly-rounded real boundary, so it is within half an ulp of the true
value and the crossing of `Int(p*h)` is within one. Measured over every legal bin count
`h` in [1, 4096] and every interior `b`: the maximum walk actually needed is ONE ulp. The cap
is 4x that, and it exists so the loop is bounded by construction rather than by an argument —
an unbounded search in a kernel is a hang, which from a caller's side is the same failure as
the abort this package is built to avoid. `test_evaluation_binning.mojo` asserts the
fixed-point property over a bin-count sweep, so a cap that ever became too small would be
caught there rather than silently publishing an unsnapped edge."""


struct EvalBins(Copyable, Movable):
    """One partition of the predictions, plus what fell in each part.

    `status` is `EVAL_OK` or the refusal; on a refusal every list is empty and `occupied`
    is 0, so a caller that ignores the status gets nothing rather than a plausible wrong
    partition.

    A bin with `count[b] == 0` carried no data. `mean_prob[b]` and `mean_label[b]` are 0.0
    there and mean nothing — read `count[b]` first.
    """

    var status: Int
    var n: Int
    var n_bins: Int
    var policy: Int
    var occupied: Int
    var lo: List[Float64]
    var hi: List[Float64]
    var count: List[Int]
    var mean_prob: List[Float64]
    var mean_label: List[Float64]

    def __init__(out self, status: Int, n: Int, n_bins: Int, policy: Int):
        self.status = status
        self.n = n
        self.n_bins = n_bins
        self.policy = policy
        self.occupied = 0
        self.lo = List[Float64]()
        self.hi = List[Float64]()
        self.count = List[Int]()
        self.mean_prob = List[Float64]()
        self.mean_label = List[Float64]()


struct BinCounts(Copyable, Movable):
    """The same partition applied to scores with NO labels — a histogram on [0, 1].

    Exists because a drift comparison has no labels at all: a PSI compares two score
    DISTRIBUTIONS. Routing that through `eval_bins_build` would require inventing labels,
    and `eval_pairs_status` correctly refuses a label that is not exactly 0.0 or 1.0, so
    passing the scores in as their own labels does not work and should not be made to.

    `count[b] == 0` means the bin is empty; there are no means to be absent here.
    """

    var status: Int
    var n: Int
    var n_bins: Int
    var policy: Int
    var occupied: Int
    var lo: List[Float64]
    var hi: List[Float64]
    var count: List[Int]

    def __init__(out self, status: Int, n: Int, n_bins: Int, policy: Int):
        self.status = status
        self.n = n
        self.n_bins = n_bins
        self.policy = policy
        self.occupied = 0
        self.lo = List[Float64]()
        self.hi = List[Float64]()
        self.count = List[Int]()


struct BinAssignment(Copyable, Movable):
    """Per-sample bin index under a stated policy.

    `index` is empty on any refusal — an all-zeros index array would read as "every sample
    is in bin 0", which is a valid-looking partition of a request that was rejected.
    """

    var status: Int
    var n: Int
    var n_bins: Int
    var policy: Int
    var occupied: Int
    var index: List[Int]

    def __init__(out self, status: Int, n: Int, n_bins: Int, policy: Int):
        self.status = status
        self.n = n
        self.n_bins = n_bins
        self.policy = policy
        self.occupied = 0
        self.index = List[Int]()


def _equal_width_index(p: Float64, n_bins: Int) -> Int:
    """The frozen equal-width assignment rule, restated once for this package.

    A byte-faithful restatement of `calibration.calibration_curve`'s own three lines: clamp
    `p` into [0, 1], take `Int(p * h)`, clamp the index down into the last bin so that
    `p == 1.0` is inside it. `calibration_curve` returns counts and not per-sample indices,
    so the rule has to be written out somewhere for `eval_bin_assign_flat` to answer at all.

    This is the ONE place it is written. `_equal_width_edge` is defined in terms of THIS
    function rather than as a second arithmetic expression, so the boundaries this package
    publishes cannot drift from the assignment it publishes; and
    `test_evaluation_binning.mojo` asserts these indices reproduce the frozen kernel's own
    bin counts exactly, at six bin counts, so the restatement cannot drift from the frozen
    kernel either.

    `n_bins >= 1` is the caller's responsibility and is checked by `eval_bins_status` at
    every entry point. It is not re-checked here: this is a private helper on a path that has
    already validated, and a second guard at a different strength is how one invariant ends up
    with three behaviours.
    """
    var q = p
    if q < 0.0:
        q = 0.0
    if q > 1.0:
        q = 1.0
    var idx = Int(q * Float64(n_bins))
    if idx >= n_bins:
        idx = n_bins - 1
    if idx < 0:
        idx = 0
    return idx


def _ulp_step(x: Float64, up: Bool) -> Float64:
    """The adjacent Float64 above (`up`) or below `x`, for `x` strictly inside (0, 1).

    IEEE-754 orders the bit patterns of the positive finite doubles the same way it orders
    their values, so incrementing the pattern as an integer steps to the next double. Only
    ever called on `fl(b/h)` for `1 <= b <= h-1`, which is strictly inside (0, 1), so neither
    the zero boundary nor the infinity boundary is reachable and no special case is needed.
    """
    var bits = bitcast[DType.uint64](x)
    if up:
        bits += 1
    else:
        bits -= 1
    return bitcast[DType.float64](bits)


def _equal_width_edge(b: Int, n_bins: Int) -> Float64:
    """The lower boundary of equal-width bin `b`: the smallest Float64 in that bin.

    Not `b / h`, and emphatically not `b * (1/h)`. The partition is whatever
    `_equal_width_index` says it is, so its boundary is the smallest value that function
    assigns to `b` — see the module docstring for the measured h = 22 case where `fl(15/22)`
    lands in bin 14.

    `b <= 0` is 0.0 and `b >= n_bins` is 1.0, both exactly: bin 0 starts at the bottom of the
    domain and the last bin is closed at 1.0, and those two are definitions rather than
    computations. `b == n_bins` is the top edge, which is why this is called with `b + 1`.
    """
    if b <= 0:
        return 0.0
    if b >= n_bins:
        return 1.0
    var edge = Float64(b) / Float64(n_bins)
    if _equal_width_index(edge, n_bins) >= b:
        # `fl(b/h)` is at or above the crossing: step DOWN while the predecessor is still in
        # bin `b`, so the result is the bin's first value and not merely one of its values.
        for _ in range(EVAL_EDGE_ULP_STEPS):
            var lower = _ulp_step(edge, False)
            if _equal_width_index(lower, n_bins) < b:
                break
            edge = lower
    else:
        # `fl(b/h)` is a hair below the crossing: step UP to the first value in bin `b`.
        for _ in range(EVAL_EDGE_ULP_STEPS):
            if _equal_width_index(edge, n_bins) >= b:
                break
            edge = _ulp_step(edge, True)
    return edge


def _equal_width_edges(n_bins: Int) -> List[Float64]:
    """All `n_bins + 1` equal-width boundaries, ascending, from `_equal_width_edge`.

    One source for every equal-width edge in the package: `eval_bins_build`,
    `eval_bin_counts_flat` and `eval_bin_edges_flat` all read this list, and each bin's `hi`
    is literally the next bin's `lo`, so the reported intervals tile the domain with no gap
    and no overlap by construction rather than by two expressions agreeing.
    """
    var out = List[Float64](capacity=n_bins + 1)
    for b in range(n_bins + 1):
        out.append(_equal_width_edge(b, n_bins))
    return out^


def _truncate(values: List[Float64], n: Int) -> List[Float64]:
    """First `n` values as an owned copy. `n` is already known `<= len(values)`.

    Needed because the frozen `calibration_curve` takes whole lists and derives its own
    `n = min(len(probs), len(labels))`; passing the caller's longer buffers would silently
    evaluate samples the caller excluded.
    """
    var out = List[Float64](capacity=n)
    for i in range(n):
        out.append(values[i])
    return out^


def _quantile_edges(sorted_probs: List[Float64], n: Int, n_bins: Int) -> List[Float64]:
    """The `n_bins - 1` interior edges of an equal-count partition.

    Edge `b` (0-based, for b in [0, n_bins-2]) is the order statistic that STARTS bin
    `b + 1`: rank `r = ((b + 1) * n) // n_bins`. That rank is always a legal index:
    `b + 1 <= n_bins - 1`, so `r <= ((n_bins - 1) * n) // n_bins < n`, and `r >= 0`.

    The result is non-decreasing because its source is sorted, which is what makes the
    binary search in `_edge_bin` correct.
    """
    var edges = List[Float64](capacity=n_bins)
    for b in range(n_bins - 1):
        var rank = ((b + 1) * n) // n_bins
        edges.append(sorted_probs[rank])
    return edges^


def _edge_bin(edges: List[Float64], p: Float64) -> Int:
    """Bin index for `p`: the number of edges `e` with `p >= e`, by binary search.

    O(log h), not O(h). A linear scan here would make a pass over the data O(n * h) while
    every declared cost in this package says O(n + h) — the shape of defect that measured
    0.49s against 23.89s at an identical declared cost elsewhere in this tree.
    """
    var lo = 0
    var hi = len(edges)
    while lo < hi:
        var mid = (lo + hi) // 2
        if p >= edges[mid]:
            lo = mid + 1
        else:
            hi = mid
    return lo


def eval_bins_build(
    probs: List[Float64], labels: List[Float64], n: Int, n_bins: Int, policy: Int
) -> EvalBins:
    """Partition the first `n` predictions into `n_bins` bins under `policy`.

    Equal-width delegates to the frozen `calibration.calibration_curve`, called twice — once
    with the labels and once with the predictions in the label position — so the per-bin mean
    label and the per-bin mean prediction come from ONE assignment rule that this package
    does not own. The two returned count arrays are cross-checked against each other;
    disagreement would mean the frozen kernel had become non-deterministic in its binning
    and is reported as `EVAL_ERR_BIN_COUNT` rather than averaged over.

    Equal-count sorts a copy with the frozen `sorting.heapsort`, takes interior edges at
    ranks `b * n / n_bins`, and places each sample by binary search.

    `lo[b]` and `hi[b]` are boundaries of the partition that was actually applied, not of the
    arithmetic that describes it: `lo[b]` is a member of bin `b`, `hi[b]` is the identical
    Float64 to `lo[b+1]`, and a sample equal to `lo[b]` is inside `[lo[b], hi[b])`. See
    `_equal_width_edge` for why that is a stronger statement than `b/h`.

    Refusals are `eval_pairs_status` and `eval_bins_status` verbatim — this driver adds no
    input rule of its own, so there is one strength of check per invariant in the package.

    @capability eval_bins_build
    complexity: O(n log n + h)
    counts:
    - n <= len(probs, labels) [kernel_validated]
    - dim n_bins [kernel_validated]
    @endcapability
    """
    var pair_status = eval_pairs_status(probs, labels, n)
    if pair_status != EVAL_OK:
        return EvalBins(pair_status, 0, n_bins, policy)
    var bin_status = eval_bins_status(n_bins, policy)
    if bin_status != EVAL_OK:
        return EvalBins(bin_status, n, n_bins, policy)

    var out = EvalBins(EVAL_OK, n, n_bins, policy)
    var probs_n = _truncate(probs, n)

    if policy == EVAL_BIN_EQUAL_WIDTH:
        var labels_n = _truncate(labels, n)
        var freq = calibration_curve(probs_n, labels_n, n_bins)
        var conf = calibration_curve(probs_n, probs_n, n_bins)
        var edges = _equal_width_edges(n_bins)
        for b in range(n_bins):
            if freq.counts[b] != conf.counts[b]:
                return EvalBins(EVAL_ERR_BIN_COUNT, n, n_bins, policy)
            out.lo.append(edges[b])
            out.hi.append(edges[b + 1])
            out.count.append(freq.counts[b])
            if freq.counts[b] > 0:
                out.occupied += 1
                out.mean_prob.append(conf.observed_freq[b])
                out.mean_label.append(freq.observed_freq[b])
            else:
                out.mean_prob.append(0.0)
                out.mean_label.append(0.0)
        return out^

    # EVAL_BIN_EQUAL_COUNT
    var sorted_probs = heapsort(probs_n)
    var edges = _quantile_edges(sorted_probs, n, n_bins)
    var prob_sum = List[Float64](capacity=n_bins)
    var label_sum = List[Float64](capacity=n_bins)
    for b in range(n_bins):
        prob_sum.append(0.0)
        label_sum.append(0.0)
        out.count.append(0)
        if b == 0:
            out.lo.append(0.0)
        else:
            out.lo.append(edges[b - 1])
        if b == n_bins - 1:
            out.hi.append(1.0)
        else:
            out.hi.append(edges[b])
    for i in range(n):
        var b = _edge_bin(edges, probs[i])
        out.count[b] += 1
        prob_sum[b] += probs[i]
        label_sum[b] += labels[i]
    for b in range(n_bins):
        if out.count[b] > 0:
            out.occupied += 1
            var denom = Float64(out.count[b])
            out.mean_prob.append(prob_sum[b] / denom)
            out.mean_label.append(label_sum[b] / denom)
        else:
            out.mean_prob.append(0.0)
            out.mean_label.append(0.0)
    return out^


def eval_bin_counts_flat(
    scores: List[Float64], n: Int, n_bins: Int, policy: Int
) -> BinCounts:
    """Histogram the first `n` scores into `n_bins` bins under `policy`.

    Equal-width delegates to the frozen `calibration.calibration_curve`, whose `counts`
    depend only on the values being binned — the label argument does not influence the
    assignment — so the scores are passed in both positions and only `counts` is read. That
    keeps the assignment rule the frozen one without asserting anything false about labels.

    On a refusal every list is empty, so a caller that ignores the status gets no histogram
    rather than an all-zero one that reads as "the data was empty".

    @capability eval_bin_counts_flat
    complexity: O(n log n + h)
    counts:
    - n <= len(scores) [kernel_validated]
    - dim n_bins [kernel_validated]
    @endcapability
    """
    var score_status = eval_scores_status(scores, n)
    if score_status != EVAL_OK:
        return BinCounts(score_status, 0, n_bins, policy)
    var bin_status = eval_bins_status(n_bins, policy)
    if bin_status != EVAL_OK:
        return BinCounts(bin_status, n, n_bins, policy)

    var out = BinCounts(EVAL_OK, n, n_bins, policy)
    var scores_n = _truncate(scores, n)

    if policy == EVAL_BIN_EQUAL_WIDTH:
        var curve = calibration_curve(scores_n, scores_n, n_bins)
        var edges = _equal_width_edges(n_bins)
        for b in range(n_bins):
            out.lo.append(edges[b])
            out.hi.append(edges[b + 1])
            out.count.append(curve.counts[b])
            if curve.counts[b] > 0:
                out.occupied += 1
        return out^

    var sorted_scores = heapsort(scores_n)
    var edges = _quantile_edges(sorted_scores, n, n_bins)
    for b in range(n_bins):
        out.count.append(0)
        if b == 0:
            out.lo.append(0.0)
        else:
            out.lo.append(edges[b - 1])
        if b == n_bins - 1:
            out.hi.append(1.0)
        else:
            out.hi.append(edges[b])
    for i in range(n):
        out.count[_edge_bin(edges, scores[i])] += 1
    for b in range(n_bins):
        if out.count[b] > 0:
            out.occupied += 1
    return out^


def eval_bin_assign_flat(
    probs: List[Float64], n: Int, n_bins: Int, policy: Int
) -> BinAssignment:
    """Per-sample bin index, for a caller aggregating something this package does not.

    Takes no labels: an assignment depends only on the predictions, and demanding labels
    for it would force a caller to invent them.

    @capability eval_bin_assign_flat
    complexity: O(n log n + h)
    counts:
    - n <= len(probs) [kernel_validated]
    - dim n_bins [kernel_validated]
    @endcapability
    """
    var score_status = eval_scores_status(probs, n)
    if score_status != EVAL_OK:
        return BinAssignment(score_status, 0, n_bins, policy)
    var bin_status = eval_bins_status(n_bins, policy)
    if bin_status != EVAL_OK:
        return BinAssignment(bin_status, n, n_bins, policy)

    var out = BinAssignment(EVAL_OK, n, n_bins, policy)
    var seen = List[Bool](capacity=n_bins)
    for _ in range(n_bins):
        seen.append(False)

    if policy == EVAL_BIN_EQUAL_WIDTH:
        # `_equal_width_index` is the frozen rule restated once, in this file, and
        # `_equal_width_edge` inverts THAT function rather than re-deriving the boundary
        # arithmetically — so the indices returned here and the edges returned by
        # `eval_bin_edges_flat` describe one partition and cannot drift apart.
        for i in range(n):
            var idx = _equal_width_index(probs[i], n_bins)
            out.index.append(idx)
            if not seen[idx]:
                seen[idx] = True
                out.occupied += 1
        return out^

    var probs_n = _truncate(probs, n)
    var sorted_probs = heapsort(probs_n)
    var edges = _quantile_edges(sorted_probs, n, n_bins)
    for i in range(n):
        var b = _edge_bin(edges, probs[i])
        out.index.append(b)
        if not seen[b]:
            seen[b] = True
            out.occupied += 1
    return out^


def eval_bin_edges_flat(
    probs: List[Float64], n: Int, n_bins: Int, policy: Int
) -> List[Float64]:
    """The `n_bins + 1` bin boundaries, ascending — an axis for a reliability plot.

    Every returned boundary is a value OF the bin it opens: `eval_bin_assign_flat(edge)`
    returns exactly `b` for `edge = out[b]`, and the double immediately below `out[b+1]`
    returns `b`. So re-binning any sample against this axis by binary search reproduces
    `eval_bin_assign_flat` for every representable input, and the axis cannot draw an
    interval that excludes one of its own members. Under equal width that costs an at most
    one-ulp adjustment away from the arithmetic `b/h`; see `_equal_width_edge`. Under equal
    count the interior edges are order statistics of the data and are exact already.

    Returns an EMPTY list on any refusal. A boundary list is a description of a partition
    and there is no representable "absent boundary", so emptiness is the only honest
    answer; callers that need a reason call `eval_bins_status` / `eval_scores_status`,
    which is what this function itself does.

    @capability eval_bin_edges_flat
    complexity: O(n log n + h)
    counts:
    - n <= len(probs) [kernel_validated]
    - dim n_bins [kernel_validated]
    @endcapability
    """
    var out = List[Float64]()
    if eval_scores_status(probs, n) != EVAL_OK:
        return out^
    if eval_bins_status(n_bins, policy) != EVAL_OK:
        return out^
    if policy == EVAL_BIN_EQUAL_WIDTH:
        return _equal_width_edges(n_bins)
    var probs_n = _truncate(probs, n)
    var sorted_probs = heapsort(probs_n)
    var edges = _quantile_edges(sorted_probs, n, n_bins)
    out.append(0.0)
    for b in range(len(edges)):
        out.append(edges[b])
    out.append(1.0)
    return out^
