"""test_causal_inference_uplift.mojo — known-value tests for the uplift curve and Qini.

Hand-written. The Qini areas are computed by hand on a four-unit dataset small enough to write out
in full, which is the only way an area under a curve becomes a known value rather than an
observation.

    scores  (4.0, 3.0, 2.0, 1.0)     — so the ranked order is exactly unit 0, 1, 2, 3
    T       (1,   0,   1,   0)
    Y       (1.0, 0.0, 0.0, 0.0)     — the ONE response is in the top-scored treated unit

    n_points = 2, so the cutoffs are k = 2 and k = 4.

    k = 2:  top two are unit 0 (treated, Y=1) and unit 1 (control, Y=0)
            Nt = 1, Nc = 1, Yt = 1, Yc = 0  ->  qini = 1 - 0 * 1/1 = 1
    k = 4:  Nt = 2, Nc = 2, Yt = 1, Yc = 0  ->  qini = 1 - 0 * 2/2 = 1

    curve with the origin:  (0, 0), (0.5, 1), (1, 1)
    area_curve  = 0.5(0 + 1)(0.5) + 0.5(1 + 1)(0.5) = 0.25 + 0.5 = 0.75
    random line (0, 0), (0.5, 0.5), (1, 1)
    area_random = 0.5(0 + 0.5)(0.5) + 0.5(0.5 + 1)(0.5) = 0.125 + 0.375 = 0.5
    qini_coefficient = 0.75 - 0.5 = 0.25

Reversing the scores to (1, 2, 3, 4) puts the responder LAST, giving (0, 0), (0.5, 0), (1, 1):

    area_curve = 0.25,  coefficient = 0.25 - 0.5 = -0.25

Exactly symmetric, and negative — a score that ranks responders last is reported as such rather
than clamped at zero. Both coefficients are asserted exactly.

THE ABSENCE CASE IS THE POINT
A score that happens to rank every treated unit above every control unit produces a leading cutoff
with NO control units at all, where `Yc(k) Nt(k) / Nc(k)` divides by zero. Those points are
individually absent and `has_coefficient` is False — integrating over the hole would read the
missing value as zero and make exactly such a score look maximally informative. Same for a bin
missing an arm in `uplift_by_bin`: `mean_treated - 0.0` is a large number that looks like a large
effect, so the bin's uplift is absent instead.
"""
from std.math import abs as fabs

from causal_inference.base import (
    CI_ABSENT,
    CI_ERR_INSUFFICIENT_DATA,
    CI_ERR_LENGTH_MISMATCH,
    CI_ERR_NON_FINITE,
    CI_ERR_SHAPE,
    CI_ERR_TREATMENT_NOT_BINARY,
    CI_OK,
    ci_tolerance,
)
from causal_inference.uplift import qini_curve, uplift_by_bin


fn _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _ints(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _close(a: Float64, b: Float64) -> Bool:
    return fabs(a - b) <= ci_tolerance(fabs(a) + fabs(b), 0.0)


fn _lf5() -> List[Float64]:
    return _floats(0.5, 0.6, 0.7, 0.4, 0.3)


fn _li5() -> List[Int]:
    return _ints(1, 2, 3, 4, 5)


fn main() raises:
    var passed = 0
    var failed = 0

    var t = _ints(1, 0, 1, 0)
    var y = _floats(1.0, 0.0, 0.0, 0.0)
    var s_sorted = _floats(4.0, 3.0, 2.0, 1.0)
    var s_reversed = _floats(1.0, 2.0, 3.0, 4.0)

    # ── the Qini areas, by hand ──────────────────────────────────────────────
    var q = qini_curve(s_sorted, t, y, 2)
    if (
        q.status == CI_OK
        and q.has_curve
        and q.n_points == 2
        and q.n_points_absent == 0
        and q.has_endpoint
        and _close(q.endpoint, 1.0)
        and _close(q.area_curve, 0.75)
        and _close(q.area_random, 0.5)
        and q.has_coefficient
        and _close(q.qini_coefficient, 0.25)
        and q.has_normalized
        and _close(q.qini_normalized, 0.5)
        and q.point_x[0] == 0.5
        and q.point_x[1] == 1.0
        and q.point_k[0] == 2
        and q.point_k[1] == 4
        and _close(q.point_y[0], 1.0)
        and _close(q.point_y[1], 1.0)
    ):
        passed += 1
        print("  ✅ Qini: area 0.75, random 0.5, coefficient exactly 0.25; cutoffs at k=2 and 4")
    else:
        failed += 1
        print("  ❌ Qini areas wrong:", q.area_curve, q.area_random, q.qini_coefficient)

    var qr = qini_curve(s_reversed, t, y, 2)
    if (
        qr.status == CI_OK
        and qr.has_coefficient
        and _close(qr.area_curve, 0.25)
        and _close(qr.area_random, 0.5)
        and _close(qr.qini_coefficient, -0.25)
        and _close(qr.point_y[0], 0.0)
        and _close(qr.point_y[1], 1.0)
    ):
        passed += 1
        print("  ✅ reversed scores: coefficient exactly -0.25 — a NEGATIVE answer, not clamped")
    else:
        failed += 1
        print("  ❌ reversed Qini wrong:", qr.area_curve, qr.qini_coefficient)

    # The two are exactly symmetric about zero, which no rounding can fake.
    if q.qini_coefficient == -qr.qini_coefficient and q.area_random == qr.area_random:
        passed += 1
        print("  ✅ the sorted and reversed coefficients are exact negatives of each other")
    else:
        failed += 1
        print("  ❌ symmetry broken:", q.qini_coefficient, qr.qini_coefficient)

    # The endpoint is the total incremental response and does not depend on the ordering.
    if q.endpoint == qr.endpoint:
        passed += 1
        print("  ✅ the endpoint is ordering-invariant — only the PATH to it changes")
    else:
        failed += 1
        print("  ❌ the endpoint moved with the ordering:", q.endpoint, qr.endpoint)

    # ── the absence case: a control-free prefix has NO Qini value ─────────────
    var t_front = _ints(1, 1, 0, 0)
    var q_hole = qini_curve(_floats(9.0, 8.0, 1.0, 0.0), t_front, y, 2)
    if (
        q_hole.status == CI_OK
        and q_hole.has_curve
        and q_hole.n_points_absent == 1
        and not q_hole.point_has_value[0]
        and q_hole.point_y[0] == 0.0
        and q_hole.point_has_value[1]
        and not q_hole.has_coefficient
        and q_hole.area_curve == CI_ABSENT
        and q_hole.area_random == CI_ABSENT
        and not q_hole.has_normalized
    ):
        passed += 1
        print("  ✅ a control-free prefix: that point is ABSENT and there is NO coefficient")
    else:
        failed += 1
        print(
            "  ❌ the hole was integrated over:",
            q_hole.n_points_absent,
            q_hole.has_coefficient,
            q_hole.area_curve,
        )

    # Every point defined but the last cutoff still covering the whole sample: n_points = 4 puts
    # a cutoff at every unit, so cutoff 1 (k=1) is a single TREATED unit and is absent.
    var q_four = qini_curve(s_sorted, t, y, 4)
    if (
        q_four.status == CI_OK
        and q_four.point_k[0] == 1
        and not q_four.point_has_value[0]
        and q_four.point_has_value[1]
        and q_four.n_points_absent == 1
        and not q_four.has_coefficient
    ):
        passed += 1
        print("  ✅ k=1 holds one treated unit: absent, and the coefficient is withheld")
    else:
        failed += 1
        print("  ❌ per-cutoff absence wrong:", q_four.n_points_absent)

    # ── the bin curve, by hand ───────────────────────────────────────────────
    # 2 bins over the ranked order: bin 0 = units 0 (T, Y=1) and 1 (C, Y=0) -> uplift 1.0;
    # bin 1 = units 2 (T, Y=0) and 3 (C, Y=0) -> uplift 0.0.
    var u = uplift_by_bin(s_sorted, t, y, 2)
    if (
        u.status == CI_OK
        and u.has_curve
        and u.n_bins == 2
        and u.n_units == 4
        and u.n_bins_absent == 0
        and u.bin_has_uplift[0]
        and u.bin_has_uplift[1]
        and u.bin_uplift[0] == 1.0
        and u.bin_uplift[1] == 0.0
        and u.bin_n[0] == 2
        and u.bin_n[1] == 2
        and u.bin_n_treated[0] == 1
        and u.bin_n_control[0] == 1
        and u.bin_mean_treated[0] == 1.0
        and u.bin_mean_control[0] == 0.0
        and u.bin_score_hi[0] == 4.0
        and u.bin_score_lo[0] == 3.0
        and u.bin_score_hi[1] == 2.0
        and u.bin_score_lo[1] == 1.0
        and u.n_inversions == 0
    ):
        passed += 1
        print("  ✅ bins: uplift 1.0 then 0.0, score ranges 4..3 and 2..1, zero inversions")
    else:
        failed += 1
        print("  ❌ bin curve wrong:", u.bin_uplift[0], u.bin_uplift[1], u.n_inversions)

    # A reversed score inverts the ordering, and the inversion count says so.
    var u_rev = uplift_by_bin(s_reversed, t, y, 2)
    if (
        u_rev.status == CI_OK
        and u_rev.bin_uplift[0] == 0.0
        and u_rev.bin_uplift[1] == 1.0
        and u_rev.n_inversions == 1
    ):
        passed += 1
        print("  ✅ a reversed score produces exactly 1 inversion — the diagnostic works")
    else:
        failed += 1
        print("  ❌ inversion counting wrong:", u_rev.n_inversions)

    # ── a bin missing an arm has NO uplift ───────────────────────────────────
    var u_hole = uplift_by_bin(_floats(9.0, 8.0, 1.0, 0.0), t_front, y, 2)
    if (
        u_hole.status == CI_OK
        and u_hole.has_curve
        and u_hole.n_bins_absent == 2
        and not u_hole.bin_has_uplift[0]
        and not u_hole.bin_has_uplift[1]
        and u_hole.bin_uplift[0] == 0.0
        and u_hole.bin_n_treated[0] == 2
        and u_hole.bin_n_control[0] == 0
    ):
        failed += 1
        print("  ❌ every bin absent should mean no curve at all")
    else:
        if (
            u_hole.status == CI_ERR_INSUFFICIENT_DATA
            and not u_hole.has_curve
            and u_hole.n_bins_absent == 2
            and not u_hole.bin_has_uplift[0]
            and u_hole.bin_uplift[0] == 0.0
            and u_hole.bin_n_treated[0] == 2
            and u_hole.bin_n_control[0] == 0
        ):
            passed += 1
            print("  ✅ arms split across bins: BOTH bins absent, has_curve False, counts kept")
        else:
            failed += 1
            print("  ❌ absent-bin handling wrong:", u_hole.status, u_hole.n_bins_absent)

    # One usable bin out of two is still a curve, with the absent one flagged.
    var y_mixed = _floats(1.0, 0.0, 2.0, 0.0)
    var u_partial = uplift_by_bin(_floats(9.0, 8.0, 3.0, 1.0), _ints(1, 1, 1, 0), y_mixed, 2)
    if (
        u_partial.status == CI_OK
        and u_partial.has_curve
        and u_partial.n_bins_absent == 1
        and not u_partial.bin_has_uplift[0]
        and u_partial.bin_has_uplift[1]
        and u_partial.bin_uplift[1] == 2.0
    ):
        passed += 1
        print("  ✅ one absent bin and one real one: the curve stands and the gap is flagged")
    else:
        failed += 1
        print("  ❌ partial-bin case wrong:", u_partial.n_bins_absent, u_partial.bin_uplift[1])

    # ── binning is by RANK, so uneven counts land in the earlier bins ─────────
    var u_three = uplift_by_bin(
        _floats(5.0, 4.0, 3.0, 2.0, 1.0), _ints(1, 0, 1, 0, 1),
        _floats(2.0, 0.0, 1.0, 0.0, 3.0), 2,
    )
    if (
        u_three.status == CI_OK
        and u_three.bin_n[0] + u_three.bin_n[1] == 5
        and u_three.bin_n[0] == 3
        and u_three.bin_n[1] == 2
        and u_three.bin_score_hi[0] == 5.0
        and u_three.bin_score_lo[1] == 1.0
    ):
        passed += 1
        print("  ✅ 5 units into 2 bins: 3 then 2, and the counts sum to the sample")
    else:
        failed += 1
        print("  ❌ rank binning wrong:", u_three.bin_n[0], u_three.bin_n[1])

    # ── ties are broken deterministically, so the answer is reproducible ─────
    var flat_scores = _floats(1.0, 1.0, 1.0, 1.0)
    var tie_a = uplift_by_bin(flat_scores, t, y, 2)
    var tie_b = uplift_by_bin(flat_scores, t, y, 2)
    var tie_q_a = qini_curve(flat_scores, t, y, 2)
    var tie_q_b = qini_curve(flat_scores, t, y, 2)
    if (
        tie_a.status == CI_OK
        and tie_a.bin_uplift[0] == tie_b.bin_uplift[0]
        and tie_a.bin_uplift[1] == tie_b.bin_uplift[1]
        and tie_q_a.qini_coefficient == tie_q_b.qini_coefficient
        and tie_a.bin_uplift[0] == 1.0
    ):
        passed += 1
        print("  ✅ all-equal scores: the stable sort keeps original order, so runs are identical")
    else:
        failed += 1
        print("  ❌ tie handling is not deterministic")

    # ── a single bin over the whole sample is the naive contrast ──────────────
    var one_bin = uplift_by_bin(s_sorted, t, y, 1)
    if (
        one_bin.status == CI_OK
        and one_bin.n_bins == 1
        and one_bin.bin_n[0] == 4
        and one_bin.bin_uplift[0] == 0.5
        and one_bin.n_inversions == 0
    ):
        passed += 1
        print("  ✅ one bin reproduces the naive contrast: 0.5 - 0.0 = 0.5")
    else:
        failed += 1
        print("  ❌ single-bin case wrong:", one_bin.bin_uplift[0])

    # ── refusals ─────────────────────────────────────────────────────────────
    if (
        uplift_by_bin(s_sorted, t, y, 0).status == CI_ERR_SHAPE
        and uplift_by_bin(s_sorted, t, y, 5).status == CI_ERR_SHAPE
        and uplift_by_bin(s_sorted, _ints(1, 0), y, 2).status == CI_ERR_LENGTH_MISMATCH
        and uplift_by_bin(s_sorted, _ints(1, 0, 1, 2), y, 2).status
        == CI_ERR_TREATMENT_NOT_BINARY
        and uplift_by_bin(s_sorted, _ints(1, 1, 1, 1), y, 2).status == 349
        and uplift_by_bin(List[Float64](), List[Int](), List[Float64](), 1).status
        == CI_ERR_INSUFFICIENT_DATA
        and qini_curve(s_sorted, t, y, 0).status == CI_ERR_SHAPE
        and qini_curve(s_sorted, t, y, 5).status == CI_ERR_SHAPE
        and qini_curve(s_sorted, t, _floats(1.0), 2).status == CI_ERR_LENGTH_MISMATCH
    ):
        passed += 1
        print("  ✅ more bins than units, mismatched lengths, a third arm and one-armed refused")
    else:
        failed += 1
        print("  ❌ refusals incomplete")

    # A non-finite score has no ordering, so there is no curve.
    var inf_score = _floats(1.0e308 * 10.0, 3.0, 2.0, 1.0)
    if (
        qini_curve(inf_score, t, y, 2).status == CI_ERR_NON_FINITE
        and uplift_by_bin(inf_score, t, y, 2).status == CI_ERR_NON_FINITE
    ):
        passed += 1
        print("  ✅ a non-finite score is refused rather than ordered arbitrarily")
    else:
        failed += 1
        print("  ❌ non-finite score handling wrong")

    # ── the A-Z harness pattern ──────────────────────────────────────────────
    if (
        uplift_by_bin(_lf5(), _li5(), _lf5(), 5).status == CI_ERR_TREATMENT_NOT_BINARY
        and qini_curve(_lf5(), _li5(), _lf5(), 5).status == CI_ERR_TREATMENT_NOT_BINARY
    ):
        passed += 1
        print("  ✅ the fixed 5-element / 5-integer harness pattern is refused, not indexed")
    else:
        failed += 1
        print("  ❌ the A-Z argument pattern was mishandled")

    print("  [causal_inference.uplift] Passed:", passed, "Failed:", failed)
