"""test_evaluation_binning.mojo — hand-written tests for the two binning policies.

Hand-written, never machine-emitted.

Reference values, all computable by hand and cross-checked against an independent Python
transcription of the same definitions:

  A = p [0.1, 0.3, 0.5, 0.7, 0.9], y [0, 0, 1, 1, 1]
    equal-width h=5   index Int(p*5) -> [0, 1, 2, 3, 4]   counts [1,1,1,1,1]
    equal-width h=2   index Int(p*2) -> [0, 0, 1, 1, 1]   counts [2,3]
                      mean prediction  bin0 (0.1+0.3)/2 = 0.2 exactly in binary
                                       bin1 (0.5+0.7+0.9)/3 = 0.7000000000000001
                      mean label       bin0 0.0            bin1 1.0
    equal-count h=2   edge = sorted[(1*5)//2] = sorted[2] = 0.5
                      p >= 0.5 -> bin 1, so counts [2,3] — same partition as equal-width
                      here, which is why A alone cannot demonstrate the policies differ

  B = p [0.05, 0.10, 0.15, 0.90], y [0, 0, 1, 1]      (the contrast case)
    equal-width h=2   index Int(p*2) -> [0, 0, 0, 1]      counts [3,1]
    equal-count h=2   edge = sorted[2] = 0.15            counts [2,2]
                      bin0 mean prediction (0.05+0.10)/2 = 0.07500000000000001
                      bin1 mean prediction (0.15+0.90)/2 = 0.525 exactly
    Same data, same bin COUNT, different policy -> a different partition. That is the whole
    reason the policy is an explicit argument and travels back with every result.

  C = p [0.4, 0.4, 0.4, 0.4]                            (the all-ties case)
    equal-count h=2   every edge equals 0.4 and p >= 0.4 for every sample, so all four land
                      in the last bin: counts [0,4], occupied 1. Ties are NOT split, and the
                      occupancy count is what says so.

  D = the published equal-width BOUNDARIES, which are a claim about the partition and are
      therefore checked AGAINST the partition rather than against an arithmetic expression:

        h =  5   edges exactly 0.0, 0.2, 0.4, 0.6, 0.8, 1.0        (all exact in Float64)
        h = 10   edge 3 exactly 0.3, so the sample p = 0.3 is inside bin 3's reported range
        h =  7   edge 5 = 0.7142857142857143 = fl(5/7), NOT fl(5*(1/7)) = 0.7142857142857142
        h = 22   edge 15 = 0.6818181818181819, one ulp ABOVE fl(15/22) = 0.6818181818181818,
                 because Int(fl(15/22) * 22) == 14 — fl(15/22) is not a member of bin 15 and
                 publishing it as bin 15's lower edge would put the boundary on the wrong side
                 of itself

      Every one of those four is a value a reader can check in any IEEE-754 double: `5/7` and
      `5*(1.0/7)` are different doubles, and `0.7142857142857142 * 7 < 5`.

      Then swept as a PROPERTY over h = 1..256 rather than as four spot values: each published
      edge fed back through `eval_bin_assign_flat` must return its own bin index, each `hi[b]`
      must be the identical Float64 to `lo[b+1]`, and the edges must strictly ascend. The
      first of those is the assertion the earlier suite lacked — it checked only that edges
      numbered h+1, ascended, and started at 0.0 and ended at 1.0, all of which the wrong
      boundaries satisfied, at h = 4 (a power of two, where the wrong expression is exact) and
      h = 5 (where only the unchecked interior edges were wrong).

Per-value comparisons use `8 * DBL_EPSILON * |expected|` — that value's OWN magnitude and
nothing else. Never a sum or maximum over the other bins (rule 4b, spellings 1 and 2). The
boundary assertions above use EXACT equality on purpose: a boundary is not an approximation of
a real number, it is one specific Float64, and a tolerance of 8 ulps would accept every value
this section exists to reject.
"""
from std.math import abs as fabs

from evaluation.binning import (
    eval_bin_assign_flat,
    eval_bin_counts_flat,
    eval_bin_edges_flat,
    eval_bins_build,
)
from evaluation.contract import (
    EVAL_BIN_EQUAL_COUNT,
    EVAL_BIN_EQUAL_WIDTH,
    EVAL_DBL_EPSILON,
    EVAL_ERR_BIN_COUNT,
    EVAL_ERR_BIN_POLICY,
    EVAL_ERR_COUNT,
    EVAL_ERR_EMPTY,
    EVAL_ERR_LABEL_NOT_BINARY,
    EVAL_MAX_BINS,
    EVAL_OK,
    eval_status_name,
)


def close(got: Float64, want: Float64) -> Bool:
    """`got == want` within 8 ulps of `want` — scaled by the compared value's own magnitude."""
    return fabs(got - want) <= 8.0 * EVAL_DBL_EPSILON * fabs(want)


def dataset_a_probs() -> List[Float64]:
    var out = List[Float64]()
    out.append(0.1)
    out.append(0.3)
    out.append(0.5)
    out.append(0.7)
    out.append(0.9)
    return out^


def dataset_a_labels() -> List[Float64]:
    var out = List[Float64]()
    out.append(0.0)
    out.append(0.0)
    out.append(1.0)
    out.append(1.0)
    out.append(1.0)
    return out^


def dataset_b_probs() -> List[Float64]:
    var out = List[Float64]()
    out.append(0.05)
    out.append(0.10)
    out.append(0.15)
    out.append(0.90)
    return out^


def dataset_b_labels() -> List[Float64]:
    var out = List[Float64]()
    out.append(0.0)
    out.append(0.0)
    out.append(1.0)
    out.append(1.0)
    return out^


def main() raises:
    var failures = 0
    var checks = 0
    var pa = dataset_a_probs()
    var ya = dataset_a_labels()
    var pb = dataset_b_probs()
    var yb = dataset_b_labels()

    # ── A, equal width, h = 5: one sample per bin, edges at the fifths ────────
    var a5 = eval_bins_build(pa, ya, 5, 5, EVAL_BIN_EQUAL_WIDTH)
    checks += 1
    if a5.status != EVAL_OK or a5.occupied != 5:
        print("  ❌ A/h=5 status", eval_status_name(a5.status), "occupied", a5.occupied)
        failures += 1
    for b in range(5):
        checks += 1
        if a5.count[b] != 1:
            print("  ❌ A/h=5 bin", b, "count", a5.count[b], "want 1")
            failures += 1
    checks += 1
    if a5.lo[0] != 0.0 or a5.hi[4] != 1.0:
        print("  ❌ A/h=5 outer edges must be exactly 0.0 and 1.0:", a5.lo[0], a5.hi[4])
        failures += 1
    # A singleton bin's mean prediction is the prediction itself, exactly.
    checks += 1
    if a5.mean_prob[0] != 0.1 or a5.mean_prob[4] != 0.9:
        print("  ❌ A/h=5 singleton mean prediction is not the value itself")
        failures += 1
    checks += 1
    if a5.mean_label[0] != 0.0 or a5.mean_label[2] != 1.0:
        print("  ❌ A/h=5 singleton mean label is not the label itself")
        failures += 1

    # ── A, equal width, h = 2: the per-bin means, computed by hand ────────────
    var a2 = eval_bins_build(pa, ya, 5, 2, EVAL_BIN_EQUAL_WIDTH)
    checks += 1
    if a2.count[0] != 2 or a2.count[1] != 3:
        print("  ❌ A/h=2 counts", a2.count[0], a2.count[1], "want 2, 3")
        failures += 1
    checks += 1
    if a2.mean_prob[0] != 0.2:
        print("  ❌ A/h=2 bin0 mean prediction", a2.mean_prob[0], "want exactly 0.2")
        failures += 1
    checks += 1
    if not close(a2.mean_prob[1], 0.7):
        print("  ❌ A/h=2 bin1 mean prediction", a2.mean_prob[1], "want 0.7")
        failures += 1
    checks += 1
    if a2.mean_label[0] != 0.0 or a2.mean_label[1] != 1.0:
        print("  ❌ A/h=2 mean labels", a2.mean_label[0], a2.mean_label[1], "want 0.0, 1.0")
        failures += 1

    # ── B: the two policies give DIFFERENT partitions of the same data ────────
    var bw = eval_bins_build(pb, yb, 4, 2, EVAL_BIN_EQUAL_WIDTH)
    var bc = eval_bins_build(pb, yb, 4, 2, EVAL_BIN_EQUAL_COUNT)
    checks += 1
    if bw.count[0] != 3 or bw.count[1] != 1:
        print("  ❌ B/equal-width counts", bw.count[0], bw.count[1], "want 3, 1")
        failures += 1
    checks += 1
    if bc.count[0] != 2 or bc.count[1] != 2:
        print("  ❌ B/equal-count counts", bc.count[0], bc.count[1], "want 2, 2")
        failures += 1
    checks += 1
    if bw.count[0] == bc.count[0]:
        print("  ❌ the two policies produced the SAME partition of B — the contrast case")
        print("     no longer contrasts, so nothing here demonstrates the policy matters")
        failures += 1
    # The equal-count edge is an order statistic of the data, not a fifth of the range.
    checks += 1
    if bc.lo[1] != 0.15 or bc.hi[0] != 0.15:
        print("  ❌ B/equal-count interior edge", bc.lo[1], "want sorted[2] = 0.15")
        failures += 1
    checks += 1
    if bc.lo[0] != 0.0 or bc.hi[1] != 1.0:
        print("  ❌ B/equal-count outer edges must still be 0.0 and 1.0")
        failures += 1
    checks += 1
    if not close(bc.mean_prob[0], 0.07500000000000001):
        print("  ❌ B/equal-count bin0 mean prediction", bc.mean_prob[0], "want 0.075")
        failures += 1
    checks += 1
    if bc.mean_prob[1] != 0.525:
        print("  ❌ B/equal-count bin1 mean prediction", bc.mean_prob[1], "want exactly 0.525")
        failures += 1
    checks += 1
    if bc.mean_label[0] != 0.0 or bc.mean_label[1] != 1.0:
        print("  ❌ B/equal-count mean labels", bc.mean_label[0], bc.mean_label[1])
        failures += 1

    # ── ties are not split, and occupancy says so ────────────────────────────
    var tied = List[Float64]()
    var tied_y = List[Float64]()
    for _ in range(4):
        tied.append(0.4)
        tied_y.append(1.0)
    var tc = eval_bins_build(tied, tied_y, 4, 2, EVAL_BIN_EQUAL_COUNT)
    checks += 1
    if tc.count[0] != 0 or tc.count[1] != 4 or tc.occupied != 1:
        print("  ❌ all-ties equal-count", tc.count[0], tc.count[1], "occupied", tc.occupied)
        print("     want 0, 4, 1 — a quantile binning cannot split equal values")
        failures += 1
    # An empty bin holds 0.0 in both mean slots, and count is the only thing that says so.
    checks += 1
    if tc.mean_prob[0] != 0.0 or tc.mean_label[0] != 0.0:
        print("  ❌ an empty bin's mean slots must be representable zeros")
        failures += 1

    # ── the restated equal-width index rule agrees with the FROZEN kernel ─────
    # `eval_bin_assign_flat` writes out `Int(p*h)` because the frozen `calibration_curve`
    # returns counts and not per-sample indices. This is the assertion that the two cannot
    # drift: the histogram comes from the frozen kernel, the indices from the restatement,
    # and they must agree bin for bin at several bin counts.
    var bin_counts = List[Int]()
    bin_counts.append(1)
    bin_counts.append(2)
    bin_counts.append(3)
    bin_counts.append(5)
    bin_counts.append(10)
    bin_counts.append(64)
    for t in range(len(bin_counts)):
        var h = bin_counts[t]
        var hist = eval_bin_counts_flat(pa, 5, h, EVAL_BIN_EQUAL_WIDTH)
        var assign = eval_bin_assign_flat(pa, 5, h, EVAL_BIN_EQUAL_WIDTH)
        checks += 1
        if hist.status != EVAL_OK or assign.status != EVAL_OK:
            print("  ❌ h =", h, "refused")
            failures += 1
            continue
        var tally = List[Int]()
        for _ in range(h):
            tally.append(0)
        for i in range(5):
            tally[assign.index[i]] += 1
        var mismatches = 0
        for b in range(h):
            if tally[b] != hist.count[b]:
                mismatches += 1
        checks += 1
        if mismatches != 0:
            print("  ❌ h =", h, ":", mismatches, "bin(s) where the restated index rule")
            print("     disagrees with the frozen calibration_curve's own counts")
            failures += 1
        checks += 1
        if assign.occupied != hist.occupied:
            print("  ❌ h =", h, "occupancy disagrees:", assign.occupied, hist.occupied)
            failures += 1

    # ── every sample is placed in exactly one bin, under both policies ────────
    for policy in range(2):
        var assign = eval_bin_assign_flat(pb, 4, 3, policy)
        checks += 1
        if len(assign.index) != 4:
            print("  ❌ policy", policy, "did not place every sample")
            failures += 1
            continue
        var out_of_range = 0
        for i in range(4):
            if assign.index[i] < 0 or assign.index[i] >= 3:
                out_of_range += 1
        checks += 1
        if out_of_range != 0:
            print("  ❌ policy", policy, "produced", out_of_range, "index/indices outside [0, h)")
            failures += 1
        var total = 0
        var hist = eval_bin_counts_flat(pb, 4, 3, policy)
        for b in range(3):
            total += hist.count[b]
        checks += 1
        if total != 4:
            print("  ❌ policy", policy, "histogram totals", total, "want 4")
            failures += 1

    # ── edges: h+1 of them, ascending, spanning [0, 1] ───────────────────────
    for policy in range(2):
        var edges = eval_bin_edges_flat(pb, 4, 4, policy)
        checks += 1
        if len(edges) != 5:
            print("  ❌ policy", policy, "returned", len(edges), "edges, want h+1 = 5")
            failures += 1
            continue
        checks += 1
        if edges[0] != 0.0 or edges[4] != 1.0:
            print("  ❌ policy", policy, "edges do not span [0, 1]")
            failures += 1
        var descents = 0
        for i in range(1, 5):
            if edges[i] < edges[i - 1]:
                descents += 1
        checks += 1
        if descents != 0:
            print("  ❌ policy", policy, "edges are not ascending —", descents, "descent(s);")
            print("     the binary search in _edge_bin is only correct on a sorted list")
            failures += 1

    # ── D. the published equal-width boundaries ARE boundaries of the partition ──
    # The four hand-checkable values first. `eval_bin_edges_flat` needs at least one valid
    # sample to have a request at all; the equal-width edges do not depend on it.
    var one_p = List[Float64]()
    one_p.append(0.3)
    var one_y = List[Float64]()
    one_y.append(1.0)

    var e5 = eval_bin_edges_flat(one_p, 1, 5, EVAL_BIN_EQUAL_WIDTH)
    checks += 1
    if len(e5) != 6:
        print("  ❌ h=5 returned", len(e5), "edges")
        failures += 1
    elif (
        e5[0] != 0.0 or e5[1] != 0.2 or e5[2] != 0.4 or e5[3] != 0.6
        or e5[4] != 0.8 or e5[5] != 1.0
    ):
        print("  ❌ h=5 edges", e5[0], e5[1], e5[2], e5[3], e5[4], e5[5])
        print("     want exactly 0.0 0.2 0.4 0.6 0.8 1.0; edge 3 computed as 3*(1/5) is")
        print("     0.6000000000000001, which is NOT the boundary of bin 3")
        failures += 1

    var e10 = eval_bin_edges_flat(one_p, 1, 10, EVAL_BIN_EQUAL_WIDTH)
    checks += 1
    if e10[3] != 0.3:
        print("  ❌ h=10 edge 3 is", e10[3], "want exactly 0.3. Computed as 3*(1/10) it is")
        print("     0.30000000000000004, which is ABOVE the sample 0.3 that bin 3 contains")
        failures += 1

    var e7 = eval_bin_edges_flat(one_p, 1, 7, EVAL_BIN_EQUAL_WIDTH)
    checks += 1
    if e7[5] != 5.0 / 7.0:
        print("  ❌ h=7 edge 5 is", e7[5], "want fl(5/7) =", 5.0 / 7.0)
        failures += 1
    checks += 1
    if e7[5] == 5.0 * (1.0 / 7.0) and 5.0 / 7.0 != 5.0 * (1.0 / 7.0):
        print("  ❌ h=7 edge 5 is fl(5*(1/7)), a different double from fl(5/7)")
        failures += 1

    var e22 = eval_bin_edges_flat(one_p, 1, 22, EVAL_BIN_EQUAL_WIDTH)
    checks += 1
    if e22[15] <= 15.0 / 22.0:
        print("  ❌ h=22 edge 15 is", e22[15], "which is at or below fl(15/22) =", 15.0 / 22.0)
        print("     Int(fl(15/22) * 22) == 14, so fl(15/22) belongs to bin 14 and cannot be")
        print("     bin 15's lower boundary. The boundary must be the FIRST double in bin 15.")
        failures += 1

    # The property, swept. This is what a spot check cannot do: every interior boundary at
    # every bin count must be a fixed point of the assignment rule it describes.
    var edge_hs = List[Int]()
    edge_hs.append(1)
    edge_hs.append(2)
    edge_hs.append(3)
    edge_hs.append(5)
    edge_hs.append(7)
    edge_hs.append(10)
    edge_hs.append(22)
    edge_hs.append(64)
    edge_hs.append(97)
    edge_hs.append(256)
    var misplaced = 0
    var non_tiling = 0
    var non_ascending = 0
    var edges_checked = 0
    for t in range(len(edge_hs)):
        var h = edge_hs[t]
        var edges = eval_bin_edges_flat(one_p, 1, h, EVAL_BIN_EQUAL_WIDTH)
        if len(edges) != h + 1:
            misplaced += 1
            continue
        # Feed every published boundary back in as a SAMPLE. Bin b's lower boundary must be
        # assigned to bin b: it is a value of that bin, not merely near it.
        var as_samples = List[Float64]()
        for b in range(h):
            as_samples.append(edges[b])
        var back = eval_bin_assign_flat(as_samples, h, h, EVAL_BIN_EQUAL_WIDTH)
        for b in range(h):
            edges_checked += 1
            if back.index[b] != b:
                misplaced += 1
        for b in range(1, h + 1):
            if edges[b] <= edges[b - 1]:
                non_ascending += 1
        # hi[b] and lo[b+1] must be the SAME Float64, so the reported intervals tile the
        # domain with no gap a sample could fall into and no overlap it could fall in twice.
        var built = eval_bins_build(one_p, one_y, 1, h, EVAL_BIN_EQUAL_WIDTH)
        for b in range(h - 1):
            if built.hi[b] != built.lo[b + 1]:
                non_tiling += 1
        if built.lo[0] != 0.0 or built.hi[h - 1] != 1.0:
            non_tiling += 1
    # Derived from the sweep list, not hardcoded: adding a bin count to `edge_hs` must not
    # require editing a number here, but a sweep that silently stopped covering anything must
    # still fail.
    var edges_expected = 0
    for t in range(len(edge_hs)):
        edges_expected += edge_hs[t]
    checks += 1
    if edges_checked != edges_expected or edges_expected < 400:
        print("  ❌ the boundary sweep checked", edges_checked, "boundaries, expected",
              edges_expected, "(floor 400)")
        failures += 1
    checks += 1
    if misplaced != 0:
        print("  ❌", misplaced, "published boundary/boundaries are assigned to a DIFFERENT")
        print("     bin than the one they open. eval_bin_edges_flat and eval_bin_assign_flat")
        print("     then describe two different partitions, and a reliability plot draws an")
        print("     x-interval that excludes one of its own samples.")
        failures += 1
    checks += 1
    if non_ascending != 0:
        print("  ❌", non_ascending, "boundary pair(s) do not strictly ascend")
        failures += 1
    checks += 1
    if non_tiling != 0:
        print("  ❌", non_tiling, "reported interval(s) do not tile: hi[b] != lo[b+1]")
        failures += 1

    # A sample that sits exactly ON a published boundary must be inside the bin whose range
    # is reported as starting there. This is the measured case B, asserted directly.
    var b10 = eval_bins_build(one_p, one_y, 1, 10, EVAL_BIN_EQUAL_WIDTH)
    var where = eval_bin_assign_flat(one_p, 1, 10, EVAL_BIN_EQUAL_WIDTH)
    checks += 1
    if where.index[0] != 3:
        print("  ❌ p=0.3 at h=10 was assigned to bin", where.index[0], "want 3")
        failures += 1
    elif one_p[0] < b10.lo[3] or one_p[0] >= b10.hi[3]:
        print("  ❌ p =", one_p[0], "landed in bin 3 whose reported range is [", b10.lo[3],
              ",", b10.hi[3], ") — the sample is NOT in its own bin's reported range")
        failures += 1

    # ── refusals: every one returns EMPTY, never a plausible partition ────────
    var refused = eval_bins_build(pa, ya, 25, 5, EVAL_BIN_EQUAL_WIDTH)
    checks += 1
    if refused.status != EVAL_ERR_COUNT or len(refused.count) != 0:
        print("  ❌ n past the list end must refuse with empty lists, got",
              eval_status_name(refused.status), len(refused.count))
        failures += 1
    checks += 1
    if eval_bins_build(pa, ya, 0, 5, EVAL_BIN_EQUAL_WIDTH).status != EVAL_ERR_EMPTY:
        print("  ❌ an empty evaluation set has no partition")
        failures += 1
    checks += 1
    if eval_bins_build(pa, ya, 5, 0, EVAL_BIN_EQUAL_WIDTH).status != EVAL_ERR_BIN_COUNT:
        print("  ❌ h=0 must be refused")
        failures += 1
    checks += 1
    if eval_bins_build(pa, ya, 5, EVAL_MAX_BINS + 1, 0).status != EVAL_ERR_BIN_COUNT:
        print("  ❌ the bin ceiling must be refused")
        failures += 1
    checks += 1
    if eval_bins_build(pa, ya, 5, 5, 9).status != EVAL_ERR_BIN_POLICY:
        print("  ❌ an unknown policy must be refused")
        failures += 1
    # The label contract applies here too: the scores of a drift comparison are NOT labels.
    checks += 1
    if eval_bins_build(pa, pa, 5, 5, EVAL_BIN_EQUAL_WIDTH).status != EVAL_ERR_LABEL_NOT_BINARY:
        print("  ❌ passing predictions in the label position must be refused —")
        print("     that is why eval_bin_counts_flat exists for unlabelled scores")
        failures += 1
    checks += 1
    if eval_bin_counts_flat(pa, 5, 5, EVAL_BIN_EQUAL_WIDTH).status != EVAL_OK:
        print("  ❌ the unlabelled histogram must accept plain scores")
        failures += 1
    checks += 1
    if eval_bin_counts_flat(pa, 25, 5, EVAL_BIN_EQUAL_WIDTH).status != EVAL_ERR_COUNT:
        print("  ❌ the histogram's count guard")
        failures += 1
    checks += 1
    if len(eval_bin_edges_flat(pa, 25, 5, EVAL_BIN_EQUAL_WIDTH)) != 0:
        print("  ❌ a refused edge request must be empty, not a plausible axis")
        failures += 1
    checks += 1
    if len(eval_bin_assign_flat(pa, 25, 5, EVAL_BIN_EQUAL_WIDTH).index) != 0:
        print("  ❌ a refused assignment must be empty, not all-zeros")
        failures += 1

    # ── h = 1 degenerates cleanly under both policies ────────────────────────
    for policy in range(2):
        var one = eval_bins_build(pa, ya, 5, 1, policy)
        checks += 1
        if one.status != EVAL_OK or one.count[0] != 5 or one.occupied != 1:
            print("  ❌ h=1 policy", policy, eval_status_name(one.status), one.count[0])
            failures += 1
            continue
        checks += 1
        if one.lo[0] != 0.0 or one.hi[0] != 1.0:
            print("  ❌ h=1 policy", policy, "must span [0, 1]")
            failures += 1
        # One bin means the mean prediction is the mean of everything: 2.5/5 = 0.5.
        checks += 1
        if not close(one.mean_prob[0], 0.5) or not close(one.mean_label[0], 0.6):
            print("  ❌ h=1 policy", policy, "means", one.mean_prob[0], one.mean_label[0],
                  "want 0.5 and 0.6")
            failures += 1

    # ── h > n: more bins than samples is legal and mostly empty ──────────────
    var sparse = eval_bins_build(pa, ya, 5, 50, EVAL_BIN_EQUAL_WIDTH)
    checks += 1
    if sparse.status != EVAL_OK or sparse.occupied != 5 or len(sparse.count) != 50:
        print("  ❌ h > n:", eval_status_name(sparse.status), sparse.occupied,
              len(sparse.count), "want ok, 5, 50")
        failures += 1
    var placed = 0
    for b in range(50):
        placed += sparse.count[b]
    checks += 1
    if placed != 5:
        print("  ❌ h > n placed", placed, "samples, want 5")
        failures += 1

    # ── the invariant behind EVAL_ERR_NO_OCCUPIED_BINS being unreachable ──────
    # `brier_decomposition_flat`, `calibration_error_flat`, `evaluate_flat` and
    # `metric_value_flat` all guard on `bins.occupied == 0` and return 377. That guard is
    # correct and cheap, and it is also DEAD: every accepted sample is placed in exactly one
    # bin, so a partition of a non-empty request has at least one occupied bin. The guard is
    # kept, and the invariant that makes it dead is asserted here instead of assumed — if it
    # ever stops holding, 377 becomes reachable and the docs are wrong about it.
    #
    # Swept over the shapes most likely to break it: one sample, all-identical predictions,
    # everything at 0.0, everything at 1.0, and h from 1 to the bin ceiling, both policies.
    var inv_ns = List[Int]()
    inv_ns.append(1)
    inv_ns.append(2)
    inv_ns.append(9)
    var inv_hs = List[Int]()
    inv_hs.append(1)
    inv_hs.append(3)
    inv_hs.append(64)
    inv_hs.append(4096)
    var inv_worst = 1 << 30
    var inv_trials = 0
    for shape in range(4):
        for ni in range(len(inv_ns)):
            var n = inv_ns[ni]
            var ip = List[Float64]()
            var iy = List[Float64]()
            for i in range(n):
                var v: Float64 = 0.5
                if shape == 0:
                    v = 0.0
                elif shape == 1:
                    v = 1.0
                elif shape == 2:
                    v = 0.5
                else:
                    v = Float64(i) / Float64(n)
                ip.append(v)
                iy.append(1.0 if i % 2 == 0 else 0.0)
            for hj in range(len(inv_hs)):
                for pol in range(2):
                    inv_trials += 1
                    var ib = eval_bins_build(ip, iy, n, inv_hs[hj], pol)
                    if ib.status != EVAL_OK:
                        checks += 1
                        print("  ❌ a valid partition was refused: n", n, "h",
                              inv_hs[hj], "policy", pol, eval_status_name(ib.status))
                        failures += 1
                        continue
                    if ib.occupied < inv_worst:
                        inv_worst = ib.occupied
                    var total = 0
                    for b in range(inv_hs[hj]):
                        total += ib.count[b]
                    if total != n:
                        checks += 1
                        print("  ❌ n", n, "h", inv_hs[hj], "policy", pol, "placed",
                              total, "samples — every sample must land in exactly one bin")
                        failures += 1
    checks += 1
    if inv_worst < 1:
        print("  ❌ some valid partition had 0 occupied bins over", inv_trials,
              "shapes; EVAL_ERR_NO_OCCUPIED_BINS is reachable and the docs must say so")
        failures += 1
    checks += 1
    if inv_trials != 96:
        print("  ❌ the invariant sweep covered", inv_trials, "shapes, expected 96")
        failures += 1

    for _ in range(checks - failures):
        print("  ✅ evaluation.binning check")
    print("  [evaluation.binning] Passed:", checks - failures, "Failed:", failures)
    if failures != 0:
        raise Error("test_evaluation_binning failed")
