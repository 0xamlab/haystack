"""
causal_inference.uplift — heterogeneous treatment effects by rank, and the Qini curve.
Zero Python imports.

Why this file exists
--------------------
Every estimator in this package answers "what is the average effect". Uplift answers a different
and often more useful question: "given a score that claims to rank units by how much the
treatment helps them, does it?" That is a question about the effect's HETEROGENEITY, and there is
nothing in the tree that addresses it — `causal.mojo` has no notion of a per-unit effect,
`ab_testing.mojo` compares two arms as wholes, and `clustering_metrics.mojo` is about clusters,
not contrasts.

The distinctive failure mode here is emptiness, and it is exactly rule 4. A bin holding only
treated units has NO uplift — there is nothing to compare against — and the tempting answer is
`mean_treated - 0.0`, which is a large number that looks like a large effect. So a bin's uplift is
a `Float64` beside a `has_uplift` Bool, and an empty arm sets the Bool to False. The same applies
to the Qini curve: `Yt(k) - Yc(k) Nt(k)/Nc(k)` requires `Nc(k) > 0`, and the leading points of a
curve over a score that ranks all the treated units first have no control units at all. Those
points are ABSENT, per point, and the Qini coefficient is absent unless every point exists —
because integrating over a curve with holes in it silently substitutes zero for "unknown".

The Qini definition used, stated because there are several
---------------------------------------------------------
At a cutoff of the top `k` units by score:

    qini(k) = Yt(k) - Yc(k) * Nt(k) / Nc(k)

where `Yt`/`Yc` are the summed outcomes and `Nt`/`Nc` the counts of treated and control units
inside the top `k`. This is the standard Radcliffe form: the control response is rescaled to the
treated group's size so the difference is an incremental-response count on the treated scale. The
`qini_coefficient` is the area between that curve and the straight line from the origin to its
endpoint (the "random targeting" line), by the trapezoid rule with `(0, 0)` included. Positive
means the score ranks responders above non-responders; negative means it ranks them below, which
is a real and actionable finding and is not clamped to zero.

What is REUSED, unchanged
-------------------------
* `causal_inference.base.ci_argsort_desc` — the package's one stable descending index sort. Ties
  break to the LOWER original index, so bins are a pure function of the score values and the curve
  is reproducible. `sorting.mojo` and `stats.fast_sort` sort VALUES and return no permutation, so
  there is no frozen kernel that answers this; the suite therefore validates the permutation
  differentially against the frozen `sorting.mergesort` of the same input.
* `causal_inference.base.ci_is_permutation` — the returned order is CHECKED, not trusted, before
  a single `order[r]` is used as an index.

`math_ext.mean` is deliberately NOT called for the per-bin arm means: the sums and counts are
accumulated in the same single pass that assigns units to bins, so a second traversal per bin
would be pure waste and the division is one line. Rule 3 is about not reimplementing a kernel's
LOGIC; there is none in `sum / count` that could drift.

Status codes: from `base.mojo`'s 340-359 allocation. None are defined here.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_causal_inference_uplift.mojo
benchmark: benchmarks/mojo_benchmarks/bench_causal_inference_report.mojo
docs: none
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from causal_inference.base import (
    CI_ABSENT,
    CI_ERR_INSUFFICIENT_DATA,
    CI_ERR_LENGTH_MISMATCH,
    CI_ERR_NON_FINITE,
    CI_ERR_SHAPE,
    CI_OK,
    ci_all_finite,
    ci_argsort_desc,
    ci_finite,
    ci_is_permutation,
    ci_treatment_defect,
)


# ── result structs (declared HERE; rule 2) ───────────────────────────────────


struct UpliftCurve(Copyable, Movable):
    """Per-bin treatment effect after ranking units by a caller-supplied score, descending.

    `bin_uplift[b]` is meaningful ONLY where `bin_has_uplift[b]` is True. A bin whose treated or
    control arm is empty has no uplift, and the alternative — reporting `mean_treated - 0.0` —
    would be a large number indistinguishable from a large effect. `n_bins_absent` counts them.

    `n_inversions` counts adjacent bin pairs where the uplift RISES as the score falls, over bins
    that both exist. A score that ranks effects correctly produces zero; a score with no
    information produces roughly half the pairs. It is a diagnostic on the SCORE, which is the
    thing being evaluated, and it is not a p-value.
    """

    var status: Int
    var has_curve: Bool
    var n_bins: Int
    var n_units: Int
    var n_bins_absent: Int
    var n_inversions: Int
    var bin_n: List[Int]
    var bin_n_treated: List[Int]
    var bin_n_control: List[Int]
    var bin_mean_treated: List[Float64]
    var bin_mean_control: List[Float64]
    var bin_uplift: List[Float64]
    var bin_has_uplift: List[Bool]
    var bin_score_hi: List[Float64]
    var bin_score_lo: List[Float64]

    def __init__(out self, status: Int):
        self.status = status
        self.has_curve = False
        self.n_bins = 0
        self.n_units = 0
        self.n_bins_absent = 0
        self.n_inversions = 0
        self.bin_n = List[Int]()
        self.bin_n_treated = List[Int]()
        self.bin_n_control = List[Int]()
        self.bin_mean_treated = List[Float64]()
        self.bin_mean_control = List[Float64]()
        self.bin_uplift = List[Float64]()
        self.bin_has_uplift = List[Bool]()
        self.bin_score_hi = List[Float64]()
        self.bin_score_lo = List[Float64]()


struct QiniResult(Copyable, Movable):
    """The Qini curve, its area against random targeting, and which of its points exist.

    `point_x[p]` is the targeted fraction `k / n` and `point_y[p]` the incremental response
    `Yt(k) - Yc(k) Nt(k) / Nc(k)`, defined only where `point_has_value[p]` is True — a prefix with
    no control units has no scaled comparison, and substituting zero there is what makes a bad
    score look good.

    `has_coefficient` requires EVERY point to exist, including the endpoint. Integrating a curve
    with holes silently reads a missing value as zero, and the coefficient is the number a caller
    will quote. `qini_coefficient` is `area_curve - area_random`; `qini_normalized` divides it by
    `area_random` and is absent when the endpoint is zero, because a ratio to nothing does not
    exist.
    """

    var status: Int
    var has_curve: Bool
    var n_points: Int
    var n_units: Int
    var n_points_absent: Int
    var point_x: List[Float64]
    var point_y: List[Float64]
    var point_has_value: List[Bool]
    var point_k: List[Int]
    var endpoint: Float64
    var has_endpoint: Bool
    var area_curve: Float64
    var area_random: Float64
    var qini_coefficient: Float64
    var has_coefficient: Bool
    var qini_normalized: Float64
    var has_normalized: Bool

    def __init__(out self, status: Int):
        self.status = status
        self.has_curve = False
        self.n_points = 0
        self.n_units = 0
        self.n_points_absent = 0
        self.point_x = List[Float64]()
        self.point_y = List[Float64]()
        self.point_has_value = List[Bool]()
        self.point_k = List[Int]()
        self.endpoint = 0.0
        self.has_endpoint = False
        self.area_curve = CI_ABSENT
        self.area_random = CI_ABSENT
        self.qini_coefficient = 0.0
        self.has_coefficient = False
        self.qini_normalized = 0.0
        self.has_normalized = False


# ── shared validation, one implementation ────────────────────────────────────


def _uplift_input_defect(
    scores: List[Float64], treatment: List[Int], outcomes: List[Float64], k: Int
) -> Int:
    """`CI_OK` or the code naming why these three parallel arrays and `k` cannot be used.

    `k` (the bin or point count) must be at least 1 and at most `len(scores)`. The upper bound is
    a payload tie, not a convenience: more bins than units guarantees empty bins, so the count
    came from the caller rather than from the data (rule 1c). It also bounds every array this
    module allocates from `k` against the payload, so no separate ceiling is needed.
    """
    var n = len(scores)
    if n == 0:
        return CI_ERR_INSUFFICIENT_DATA
    if len(treatment) != n or len(outcomes) != n:
        return CI_ERR_LENGTH_MISMATCH
    if not ci_all_finite(scores) or not ci_all_finite(outcomes):
        return CI_ERR_NON_FINITE
    if k < 1 or k > n:
        return CI_ERR_SHAPE
    return ci_treatment_defect(treatment)


# ── uplift_by_bin ────────────────────────────────────────────────────────────


def uplift_by_bin(
    scores: List[Float64], treatment: List[Int], outcomes: List[Float64], n_bins: Int
) -> UpliftCurve:
    """Rank units by `scores` descending, split into `n_bins` equal-count bins, report each bin's
    treatment effect.

    Bin membership is by RANK, not by score value: rank `r` lands in bin `r * n_bins / n` using
    integer arithmetic, so bins have equal counts up to the remainder and no bin boundary depends
    on the score's units. Equal-count is the right choice for a score whose scale is arbitrary,
    which a predicted uplift generally is.

    Ties break to the lower original index (`ci_argsort_desc` is a stable merge sort), so the
    binning is a pure function of the score values and two runs give identical bins.

    A bin missing either arm has no uplift and says so. `n_bins <= n` is required, because more
    bins than units guarantees empty ones.

    @capability uplift_by_bin
    complexity: O(n log n)
    counts:
    - n_bins <= len(scores) [kernel_validated]
    @endcapability
    """
    var defect = _uplift_input_defect(scores, treatment, outcomes, n_bins)
    if defect != CI_OK:
        return UpliftCurve(defect)
    var n = len(scores)
    var order = ci_argsort_desc(scores)
    if not ci_is_permutation(order, n):
        # `ci_argsort_desc` returns empty on a non-finite key, which `_uplift_input_defect`
        # already excluded. Checked anyway: every read below indexes with `order[r]`, and an
        # out-of-range index there is an uncatchable abort rather than an exception.
        return UpliftCurve(CI_ERR_NON_FINITE)

    var out = UpliftCurve(CI_OK)
    out.n_bins = n_bins
    out.n_units = n

    var sum_t = List[Float64](capacity=n_bins)
    var sum_c = List[Float64](capacity=n_bins)
    for _ in range(n_bins):
        sum_t.append(0.0)
        sum_c.append(0.0)
        out.bin_n.append(0)
        out.bin_n_treated.append(0)
        out.bin_n_control.append(0)
        out.bin_score_hi.append(0.0)
        out.bin_score_lo.append(0.0)

    for r in range(n):
        var b = r * n_bins // n
        if b >= n_bins:
            b = n_bins - 1
        var i = order[r]
        if out.bin_n[b] == 0:
            out.bin_score_hi[b] = scores[i]
        out.bin_score_lo[b] = scores[i]
        out.bin_n[b] += 1
        if treatment[i] == 1:
            out.bin_n_treated[b] += 1
            sum_t[b] += outcomes[i]
        else:
            out.bin_n_control[b] += 1
            sum_c[b] += outcomes[i]

    for b in range(n_bins):
        var nt = out.bin_n_treated[b]
        var nc = out.bin_n_control[b]
        if nt > 0 and nc > 0:
            var mt = sum_t[b] / Float64(nt)
            var mc = sum_c[b] / Float64(nc)
            var up = mt - mc
            if not ci_finite(mt) or not ci_finite(mc) or not ci_finite(up):
                return UpliftCurve(CI_ERR_NON_FINITE)
            out.bin_mean_treated.append(mt)
            out.bin_mean_control.append(mc)
            out.bin_uplift.append(up)
            out.bin_has_uplift.append(True)
        else:
            out.bin_mean_treated.append(0.0)
            out.bin_mean_control.append(0.0)
            out.bin_uplift.append(0.0)
            out.bin_has_uplift.append(False)
            out.n_bins_absent += 1

    var prev = -1
    for b in range(n_bins):
        if not out.bin_has_uplift[b]:
            continue
        if prev >= 0 and out.bin_uplift[b] > out.bin_uplift[prev]:
            out.n_inversions += 1
        prev = b

    out.has_curve = out.n_bins_absent < n_bins
    if not out.has_curve:
        out.status = CI_ERR_INSUFFICIENT_DATA
    return out^


# ── qini_curve ───────────────────────────────────────────────────────────────


def qini_curve(
    scores: List[Float64], treatment: List[Int], outcomes: List[Float64], n_points: Int
) -> QiniResult:
    """The Qini curve at `n_points` evenly spaced cutoffs, plus its coefficient.

    `qini(k) = Yt(k) - Yc(k) Nt(k) / Nc(k)` over the top `k` units by score, with cutoff `p`
    placed at `k = (p + 1) n / n_points` (integer arithmetic, so the last cutoff is exactly `n`).
    Prefix sums are accumulated once, so the whole curve is O(n + n_points) after the sort rather
    than one pass per point.

    A cutoff containing no control units has no value: the control response cannot be rescaled to
    the treated group. Those points are marked absent individually, and `has_coefficient` is False
    unless EVERY point exists. That refusal is the point of the function — the leading cutoffs of a
    curve over a score that happens to rank treated units first are exactly the missing ones, and
    treating a missing value as zero in the integral makes such a score look informative.

    `qini_coefficient = area_curve - area_random`, both by the trapezoid rule with the origin
    included, `x` in [0, 1]. Positive means the score ranks responders first. Negative is a real
    answer and is reported as one.

    @capability qini_curve
    complexity: O(n log n + n_points)
    counts:
    - n_points <= len(scores) [kernel_validated]
    @endcapability
    """
    var defect = _uplift_input_defect(scores, treatment, outcomes, n_points)
    if defect != CI_OK:
        return QiniResult(defect)
    var n = len(scores)
    var order = ci_argsort_desc(scores)
    if not ci_is_permutation(order, n):
        return QiniResult(CI_ERR_NON_FINITE)

    # Prefix counts and sums over the ranked order. Index r holds the totals for the top r units,
    # so entry 0 is the empty prefix and entry n the whole sample.
    var pnt = List[Int](capacity=n + 1)
    var pnc = List[Int](capacity=n + 1)
    var pyt = List[Float64](capacity=n + 1)
    var pyc = List[Float64](capacity=n + 1)
    pnt.append(0)
    pnc.append(0)
    pyt.append(0.0)
    pyc.append(0.0)
    for r in range(n):
        var i = order[r]
        var nt = pnt[r]
        var nc = pnc[r]
        var yt = pyt[r]
        var yc = pyc[r]
        if treatment[i] == 1:
            nt += 1
            yt += outcomes[i]
        else:
            nc += 1
            yc += outcomes[i]
        pnt.append(nt)
        pnc.append(nc)
        pyt.append(yt)
        pyc.append(yc)
    if not ci_all_finite(pyt) or not ci_all_finite(pyc):
        return QiniResult(CI_ERR_NON_FINITE)

    var out = QiniResult(CI_OK)
    out.n_points = n_points
    out.n_units = n

    for p in range(n_points):
        var k = (p + 1) * n // n_points
        if k > n:
            k = n
        if k < 1:
            k = 1
        out.point_k.append(k)
        out.point_x.append(Float64(k) / Float64(n))
        if pnc[k] == 0:
            out.point_y.append(0.0)
            out.point_has_value.append(False)
            out.n_points_absent += 1
            continue
        var q = pyt[k] - pyc[k] * Float64(pnt[k]) / Float64(pnc[k])
        if not ci_finite(q):
            return QiniResult(CI_ERR_NON_FINITE)
        out.point_y.append(q)
        out.point_has_value.append(True)
    out.has_curve = True

    if pnc[n] > 0:
        var end = pyt[n] - pyc[n] * Float64(pnt[n]) / Float64(pnc[n])
        if not ci_finite(end):
            return QiniResult(CI_ERR_NON_FINITE)
        out.endpoint = end
        out.has_endpoint = True

    if out.n_points_absent > 0 or not out.has_endpoint:
        # A curve with a hole in it has no area. Absent, not integrated over the holes.
        return out^

    var area_c = 0.0
    var area_r = 0.0
    var prev_x = 0.0
    var prev_y = 0.0
    var prev_r = 0.0
    for p in range(n_points):
        var x = out.point_x[p]
        var y = out.point_y[p]
        var rline = out.endpoint * x
        area_c += 0.5 * (prev_y + y) * (x - prev_x)
        area_r += 0.5 * (prev_r + rline) * (x - prev_x)
        prev_x = x
        prev_y = y
        prev_r = rline
    if not ci_finite(area_c) or not ci_finite(area_r):
        return QiniResult(CI_ERR_NON_FINITE)
    out.area_curve = area_c
    out.area_random = area_r
    var coef = area_c - area_r
    if not ci_finite(coef):
        return QiniResult(CI_ERR_NON_FINITE)
    out.qini_coefficient = coef
    out.has_coefficient = True
    if area_r != 0.0:
        var norm = coef / area_r
        if ci_finite(norm):
            out.qini_normalized = norm
            out.has_normalized = True
    return out^
