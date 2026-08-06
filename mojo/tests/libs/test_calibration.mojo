"""test_calibration.mojo — known-value tests for calibration."""
from std.math import abs as fabs, isnan, isinf
from calibration import (
    isotonic_fit,
    isotonic_transform,
    platt_fit,
    platt_transform,
    calibration_curve,
)


def is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)


def approx(a: Float64, b: Float64, tol: Float64 = 1e-9) -> Bool:
    return fabs(a - b) <= tol


def check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ calibration::" + name)
    else:
        failed += 1
        print("  ❌ calibration::" + name)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── isotonic_fit: canonical PAV known value ──────────────────────────
    # x=[1,2,3,4], y=[1,3,2,4] → pooled fit [1, 2.5, 2.5, 4]
    var x1 = List[Float64]()
    x1.append(1.0); x1.append(2.0); x1.append(3.0); x1.append(4.0)
    var y1 = List[Float64]()
    y1.append(1.0); y1.append(3.0); y1.append(2.0); y1.append(4.0)
    var fit1 = isotonic_fit(x1, y1)
    check(
        len(fit1.thresholds) == 4
        and approx(fit1.thresholds[0], 1.0)
        and approx(fit1.thresholds[1], 2.0)
        and approx(fit1.thresholds[2], 3.0)
        and approx(fit1.thresholds[3], 4.0),
        "isotonic_fit thresholds [1,2,3,4]",
        passed, failed,
    )
    check(
        len(fit1.values) == 4
        and approx(fit1.values[0], 1.0)
        and approx(fit1.values[1], 2.5)
        and approx(fit1.values[2], 2.5)
        and approx(fit1.values[3], 4.0),
        "isotonic_fit PAV values [1,2.5,2.5,4]",
        passed, failed,
    )
    # transform at the training x returns the fitted values exactly
    var t1 = isotonic_transform(fit1.thresholds, fit1.values, x1)
    check(
        len(t1) == 4
        and approx(t1[0], 1.0) and approx(t1[1], 2.5)
        and approx(t1[2], 2.5) and approx(t1[3], 4.0),
        "isotonic_transform at training x = [1,2.5,2.5,4]",
        passed, failed,
    )

    # ── isotonic_fit: unsorted input gives the same fit ─────────────────
    var x1u = List[Float64]()
    x1u.append(4.0); x1u.append(1.0); x1u.append(3.0); x1u.append(2.0)
    var y1u = List[Float64]()
    y1u.append(4.0); y1u.append(1.0); y1u.append(2.0); y1u.append(3.0)
    var fit1u = isotonic_fit(x1u, y1u)
    check(
        len(fit1u.values) == 4
        and approx(fit1u.values[0], 1.0)
        and approx(fit1u.values[1], 2.5)
        and approx(fit1u.values[2], 2.5)
        and approx(fit1u.values[3], 4.0)
        and approx(fit1u.thresholds[0], 1.0)
        and approx(fit1u.thresholds[3], 4.0),
        "isotonic_fit unsorted input sorted internally",
        passed, failed,
    )

    # ── isotonic_fit: ties in x averaged ─────────────────────────────────
    # x=[1,1,2], y=[0,2,3] → thresholds [1,2], values [1,3]
    var x2 = List[Float64]()
    x2.append(1.0); x2.append(1.0); x2.append(2.0)
    var y2 = List[Float64]()
    y2.append(0.0); y2.append(2.0); y2.append(3.0)
    var fit2 = isotonic_fit(x2, y2)
    check(
        len(fit2.thresholds) == 2
        and approx(fit2.thresholds[0], 1.0)
        and approx(fit2.thresholds[1], 2.0)
        and approx(fit2.values[0], 1.0)
        and approx(fit2.values[1], 3.0),
        "isotonic_fit ties in x averaged → [1,3]",
        passed, failed,
    )

    # ── isotonic_fit: fully decreasing pools to the global mean ─────────
    var x3 = List[Float64]()
    x3.append(1.0); x3.append(2.0); x3.append(3.0)
    var y3 = List[Float64]()
    y3.append(3.0); y3.append(2.0); y3.append(1.0)
    var fit3 = isotonic_fit(x3, y3)
    check(
        len(fit3.values) == 3
        and approx(fit3.values[0], 2.0)
        and approx(fit3.values[1], 2.0)
        and approx(fit3.values[2], 2.0),
        "isotonic_fit decreasing y pools to [2,2,2]",
        passed, failed,
    )

    # ── isotonic_transform: clamping + linear interpolation ─────────────
    var xq = List[Float64]()
    xq.append(-5.0)   # below first threshold → clamp to 1.0
    xq.append(0.999)  # still below → 1.0
    xq.append(1.5)    # between (1,1) and (2,2.5) → 1.75
    xq.append(2.5)    # between (2,2.5) and (3,2.5) → 2.5
    xq.append(3.25)   # between (3,2.5) and (4,4) → 2.875
    xq.append(10.0)   # above last threshold → clamp to 4.0
    var tq = isotonic_transform(fit1.thresholds, fit1.values, xq)
    check(
        approx(tq[0], 1.0) and approx(tq[1], 1.0),
        "isotonic_transform clamps below first threshold",
        passed, failed,
    )
    check(
        approx(tq[5], 4.0),
        "isotonic_transform clamps above last threshold",
        passed, failed,
    )
    check(
        approx(tq[2], 1.75) and approx(tq[3], 2.5) and approx(tq[4], 2.875),
        "isotonic_transform linear interp [1.75,2.5,2.875]",
        passed, failed,
    )

    # ── isotonic edge cases: empty, n=1, all-equal ───────────────────────
    var xe = List[Float64]()
    var ye = List[Float64]()
    var fite = isotonic_fit(xe, ye)
    var te = isotonic_transform(fite.thresholds, fite.values, x1)
    check(
        len(fite.thresholds) == 0 and len(fite.values) == 0
        and len(te) == 4 and approx(te[0], 0.0),
        "isotonic empty input → empty fit, transform 0.0",
        passed, failed,
    )
    var xs1 = List[Float64]()
    xs1.append(2.0)
    var ys1 = List[Float64]()
    ys1.append(5.0)
    var fits1 = isotonic_fit(xs1, ys1)
    var qs1 = List[Float64]()
    qs1.append(0.0); qs1.append(2.0); qs1.append(7.0)
    var ts1 = isotonic_transform(fits1.thresholds, fits1.values, qs1)
    check(
        len(fits1.thresholds) == 1 and approx(fits1.values[0], 5.0)
        and approx(ts1[0], 5.0) and approx(ts1[1], 5.0) and approx(ts1[2], 5.0),
        "isotonic n=1 constant fit, transform clamps to 5.0",
        passed, failed,
    )
    var yeq = List[Float64]()
    yeq.append(7.0); yeq.append(7.0); yeq.append(7.0)
    var fiteq = isotonic_fit(x3, yeq)
    check(
        len(fiteq.values) == 3
        and approx(fiteq.values[0], 7.0)
        and approx(fiteq.values[1], 7.0)
        and approx(fiteq.values[2], 7.0),
        "isotonic all-equal y stays [7,7,7]",
        passed, failed,
    )

    # ── platt_fit: perfectly separated set converges ─────────────────────
    # scores [-2,-1,-0.5,0.5,1,2], labels [0,0,0,1,1,1]: symmetric data,
    # optimum has b ≈ 0 and a ≈ -1 (score-probability positively related).
    var ps = List[Float64]()
    ps.append(-2.0); ps.append(-1.0); ps.append(-0.5)
    ps.append(0.5); ps.append(1.0); ps.append(2.0)
    var pl = List[Float64]()
    pl.append(0.0); pl.append(0.0); pl.append(0.0)
    pl.append(1.0); pl.append(1.0); pl.append(1.0)
    var params = platt_fit(ps, pl, 100)
    check(
        is_finite(params.a) and is_finite(params.b) and params.a < 0.0,
        "platt_fit converges with a < 0 on separated data",
        passed, failed,
    )
    var pq = List[Float64]()
    pq.append(4.0); pq.append(-4.0); pq.append(0.0)
    pq.append(-1.0); pq.append(1.0)
    var pp = platt_transform(params.a, params.b, pq)
    check(pp[0] > 0.9, "platt p(high score=4) > 0.9", passed, failed)
    check(pp[1] < 0.1, "platt p(low score=-4) < 0.1", passed, failed)
    check(
        approx(pp[2], 0.5, 1e-3),
        "platt p(0) ≈ 0.5 on symmetric data (b ≈ 0)",
        passed, failed,
    )
    check(
        pp[3] < pp[2] and pp[2] < pp[4] and pp[3] > 0.0 and pp[4] < 1.0,
        "platt_transform monotone increasing in score",
        passed, failed,
    )

    # ── platt edge cases: empty, n=1 single class ────────────────────────
    var pe = platt_fit(xe, ye, 50)
    check(
        approx(pe.a, 0.0) and approx(pe.b, 0.0),
        "platt_fit empty input → (0,0)",
        passed, failed,
    )
    var s1 = List[Float64]()
    s1.append(1.0)
    var l1 = List[Float64]()
    l1.append(1.0)
    var p1 = platt_fit(s1, l1, 50)
    var p1t = platt_transform(p1.a, p1.b, s1)
    check(
        is_finite(p1.a) and is_finite(p1.b)
        and p1t[0] > 0.0 and p1t[0] < 1.0,
        "platt_fit n=1 single class finite, p in (0,1)",
        passed, failed,
    )

    # ── calibration_curve: hand-built known values ───────────────────────
    # probs  [0.05,0.15,0.25,0.35,0.65,0.75,0.85,0.95], 4 bins:
    # bin0 [0,.25): {0.05,0.15} labels {0,0} → freq 0,   count 2
    # bin1 [.25,.5): {0.25,0.35} labels {1,0} → freq 0.5, count 2
    # bin2 [.5,.75): {0.65} label {1}         → freq 1.0, count 1
    # bin3 [.75,1]: {0.75,0.85,0.95} {1,0,1}  → freq 2/3, count 3
    var cp = List[Float64]()
    cp.append(0.05); cp.append(0.15); cp.append(0.25); cp.append(0.35)
    cp.append(0.65); cp.append(0.75); cp.append(0.85); cp.append(0.95)
    var cl = List[Float64]()
    cl.append(0.0); cl.append(0.0); cl.append(1.0); cl.append(0.0)
    cl.append(1.0); cl.append(1.0); cl.append(0.0); cl.append(1.0)
    var curve = calibration_curve(cp, cl, 4)
    check(
        len(curve.counts) == 4
        and curve.counts[0] == 2 and curve.counts[1] == 2
        and curve.counts[2] == 1 and curve.counts[3] == 3,
        "calibration_curve counts [2,2,1,3]",
        passed, failed,
    )
    check(
        approx(curve.observed_freq[0], 0.0)
        and approx(curve.observed_freq[1], 0.5)
        and approx(curve.observed_freq[2], 1.0)
        and approx(curve.observed_freq[3], 2.0 / 3.0),
        "calibration_curve freq [0,0.5,1,2/3]",
        passed, failed,
    )
    check(
        approx(curve.bin_centers[0], 0.125)
        and approx(curve.bin_centers[1], 0.375)
        and approx(curve.bin_centers[2], 0.625)
        and approx(curve.bin_centers[3], 0.875),
        "calibration_curve centers [.125,.375,.625,.875]",
        passed, failed,
    )
    # p=1.0 lands in the last bin (closed at 1.0); empty bin stays 0/0.0
    var cb = List[Float64]()
    cb.append(1.0)
    var lb = List[Float64]()
    lb.append(1.0)
    var curve2 = calibration_curve(cb, lb, 2)
    check(
        curve2.counts[0] == 0 and curve2.counts[1] == 1
        and approx(curve2.observed_freq[0], 0.0)
        and approx(curve2.observed_freq[1], 1.0),
        "calibration_curve p=1.0 → last bin; empty bin 0",
        passed, failed,
    )
    # empty inputs → all-zero bins
    var curve3 = calibration_curve(xe, ye, 3)
    check(
        len(curve3.counts) == 3
        and curve3.counts[0] == 0 and curve3.counts[1] == 0
        and curve3.counts[2] == 0,
        "calibration_curve empty input → zero counts",
        passed, failed,
    )

    print("  [calibration] Passed:", passed, "Failed:", failed)
