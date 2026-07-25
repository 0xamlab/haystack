"""test_imbalance.mojo — known-value tests for imbalance."""
from std.math import abs as fabs

from imbalance import (
    ClassWeights,
    smote_1d,
    smote_nd,
    random_oversample_indices,
    random_undersample_indices,
    class_weights,
)


fn _lists_equal_int(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _lists_equal_f64(a: List[Float64], b: List[Float64]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _approx(a: Float64, b: Float64, tol: Float64) -> Bool:
    return fabs(a - b) <= tol


fn _on_segment_2d(
    sx: Float64, sy: Float64,
    ax: Float64, ay: Float64,
    bx: Float64, by: Float64,
) -> Bool:
    """True if (sx, sy) is a convex combination of A and B (within tol)."""
    var dx = bx - ax
    var dy = by - ay
    var rx = sx - ax
    var ry = sy - ay
    var cross = rx * dy - ry * dx
    if fabs(cross) > 1e-9:
        return False
    var len2 = dx * dx + dy * dy
    if len2 == 0.0:
        return fabs(rx) <= 1e-12 and fabs(ry) <= 1e-12
    var t = (rx * dx + ry * dy) / len2
    return t >= -1e-12 and t <= 1.0 + 1e-12


fn check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ imbalance::" + name)
    else:
        failed += 1
        print("  ❌ imbalance::" + name)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── class_weights: hand-computed n/(k*count) ─────────────────────────────
    # labels [0,0,0,1]: n=4, k=2, counts {0:3, 1:1}
    #   w0 = 4/(2*3) = 2/3,  w1 = 4/(2*1) = 2
    #   normalization: 3*(2/3) + 1*2 = 4 = n
    var cw = class_weights([0, 0, 0, 1])
    check(
        len(cw.classes) == 2 and cw.classes[0] == 0 and cw.classes[1] == 1,
        "class_weights [0,0,0,1] classes first-appearance order",
        passed,
        failed,
    )
    check(
        _approx(cw.weights[0], 2.0 / 3.0, 1e-12)
        and _approx(cw.weights[1], 2.0, 1e-12),
        "class_weights [0,0,0,1] = [2/3, 2] exact",
        passed,
        failed,
    )
    check(
        _approx(3.0 * cw.weights[0] + 1.0 * cw.weights[1], 4.0, 1e-12),
        "class_weights mass preserved: sum count_c*w_c == n",
        passed,
        failed,
    )

    # labels [2,0,2,0,0]: classes [2,0] (first appearance), n=5, k=2,
    # counts {2:2, 0:3} -> w2 = 5/4 = 1.25, w0 = 5/6
    var cw2 = class_weights([2, 0, 2, 0, 0])
    check(
        len(cw2.classes) == 2
        and cw2.classes[0] == 2
        and cw2.classes[1] == 0
        and _approx(cw2.weights[0], 1.25, 1e-12)
        and _approx(cw2.weights[1], 5.0 / 6.0, 1e-12),
        "class_weights [2,0,2,0,0] = [5/4, 5/6] first-appearance order",
        passed,
        failed,
    )

    # balanced -> all 1.0; single class -> [1.0]; empty -> empty
    var cwb = class_weights([1, 1, 2, 2])
    check(
        len(cwb.weights) == 2
        and _approx(cwb.weights[0], 1.0, 1e-12)
        and _approx(cwb.weights[1], 1.0, 1e-12),
        "class_weights balanced -> all 1.0",
        passed,
        failed,
    )
    var cws = class_weights([5, 5, 5])
    check(
        len(cws.classes) == 1
        and cws.classes[0] == 5
        and _approx(cws.weights[0], 1.0, 1e-12),
        "class_weights single class -> [1.0]",
        passed,
        failed,
    )
    var empty_labels = List[Int]()
    var cwe = class_weights(empty_labels)
    check(
        len(cwe.classes) == 0 and len(cwe.weights) == 0,
        "class_weights empty -> empty",
        passed,
        failed,
    )

    # ── smote_1d: outputs confined to minority convex hull ──────────────────
    # minority (label 1) values {0, 10, 20}; majority {100, 101} must never
    # influence any synthetic value -> all outputs in [0, 20].
    var x1 = [0.0, 10.0, 20.0, 100.0, 101.0]
    var lab1 = [1, 1, 1, 0, 0]
    var s1 = smote_1d(x1, lab1, 1, 2, 16, 42)
    check(len(s1) == 16, "smote_1d output length == n_synthetic", passed, failed)
    var in_hull = True
    for i in range(len(s1)):
        if s1[i] < 0.0 or s1[i] > 20.0:
            in_hull = False
    check(
        in_hull,
        "smote_1d all outputs within minority hull [0,20]",
        passed,
        failed,
    )

    # exactly 2 minority points {0, 4}, k=1: every synthetic is
    # 0 + gap*4 or 4 - gap*4 with gap in [0,1) -> value in [0, 4]
    var x2 = [4.0, 9.0, 0.0]
    var lab2 = [3, 7, 3]
    var s2 = smote_1d(x2, lab2, 3, 1, 12, 5)
    var seg_ok = len(s2) == 12
    for i in range(len(s2)):
        if s2[i] < 0.0 or s2[i] > 4.0:
            seg_ok = False
    check(
        seg_ok,
        "smote_1d two minority pts: convex combos of 0 and 4",
        passed,
        failed,
    )

    # ── smote_nd: k=1 known neighbor geometry ────────────────────────────────
    # minority rows A=(0,0), B=(4,0), C=(4,3); squared dists AB=16, AC=25,
    # BC=9 -> 1-NN: A->B, B->C, C->B. Every synthetic row must lie on
    # segment AB or BC (never AC).
    var Xg = [0.0, 0.0, 4.0, 0.0, 4.0, 3.0, 100.0, 100.0, 101.0, 101.0]
    var labg = [1, 1, 1, 0, 0]
    var g = smote_nd(Xg, 2, labg, 1, 1, 24, 9)
    check(len(g) == 48, "smote_nd output length == n_synthetic*n_features", passed, failed)
    var on_known_segments = True
    for r in range(24):
        var sx = g[2 * r]
        var sy = g[2 * r + 1]
        var on_ab = _on_segment_2d(sx, sy, 0.0, 0.0, 4.0, 0.0)
        var on_bc = _on_segment_2d(sx, sy, 4.0, 0.0, 4.0, 3.0)
        if not (on_ab or on_bc):
            on_known_segments = False
    check(
        on_known_segments,
        "smote_nd k=1 rows lie only on 1-NN segments AB/BC",
        passed,
        failed,
    )

    # ── smote_nd: k=2 rows are convex combos of some minority pair ──────────
    var g2 = smote_nd(Xg, 2, labg, 1, 2, 20, 123)
    var convex_ok = len(g2) == 40
    for r in range(20):
        var sx = g2[2 * r]
        var sy = g2[2 * r + 1]
        var hit = (
            _on_segment_2d(sx, sy, 0.0, 0.0, 4.0, 0.0)
            or _on_segment_2d(sx, sy, 0.0, 0.0, 4.0, 3.0)
            or _on_segment_2d(sx, sy, 4.0, 0.0, 4.0, 3.0)
        )
        if not hit:
            convex_ok = False
    check(
        convex_ok,
        "smote_nd k=2 every row on segment between two minority rows",
        passed,
        failed,
    )

    # k_neighbors larger than n_min-1 is clamped, still valid geometry
    var gk = smote_nd(Xg, 2, labg, 1, 10, 10, 3)
    var clamp_ok = len(gk) == 20
    for r in range(10):
        var hit = (
            _on_segment_2d(gk[2 * r], gk[2 * r + 1], 0.0, 0.0, 4.0, 0.0)
            or _on_segment_2d(gk[2 * r], gk[2 * r + 1], 0.0, 0.0, 4.0, 3.0)
            or _on_segment_2d(gk[2 * r], gk[2 * r + 1], 4.0, 0.0, 4.0, 3.0)
        )
        if not hit:
            clamp_ok = False
    check(clamp_ok, "smote_nd k clamped to n_min-1 stays on segments", passed, failed)

    # ── smote determinism + seed sensitivity ─────────────────────────────────
    var da = smote_nd(Xg, 2, labg, 1, 2, 20, 7)
    var db = smote_nd(Xg, 2, labg, 1, 2, 20, 7)
    check(_lists_equal_f64(da, db), "smote_nd same seed -> identical output", passed, failed)
    var dc = smote_nd(Xg, 2, labg, 1, 2, 20, 8)
    check(
        not _lists_equal_f64(da, dc),
        "smote_nd different seed -> different output",
        passed,
        failed,
    )

    # ── smote infeasible configs -> empty ────────────────────────────────────
    var one_min = smote_1d([1.0, 2.0, 3.0], [0, 1, 0], 1, 1, 5, 0)
    var bad_k = smote_nd(Xg, 2, labg, 1, 0, 5, 0)
    var zero_syn = smote_nd(Xg, 2, labg, 1, 2, 0, 0)
    var bad_x = smote_nd([1.0, 2.0, 3.0], 2, labg, 1, 2, 5, 0)
    var empty_f = List[Float64]()
    var no_rows = smote_nd(empty_f, 2, empty_labels, 1, 2, 5, 0)
    check(
        len(one_min) == 0
        and len(bad_k) == 0
        and len(zero_syn) == 0
        and len(bad_x) == 0
        and len(no_rows) == 0,
        "smote infeasible (n_min<2, k<1, n_syn<1, bad X, empty) -> empty",
        passed,
        failed,
    )

    # ── random_oversample_indices: [0,0,0,1] hand-checked ────────────────────
    # counts {0:3, 1:1}, max=3 -> out = [0,1,2,3] + two copies of index 3
    var lab_os = [0, 0, 0, 1]
    var os = random_oversample_indices(lab_os, 42)
    check(len(os) == 6, "oversample [0,0,0,1] length 3+3", passed, failed)
    check(
        os[0] == 0 and os[1] == 1 and os[2] == 2 and os[3] == 3
        and os[4] == 3 and os[5] == 3,
        "oversample [0,0,0,1] = originals + [3,3]",
        passed,
        failed,
    )

    # multi-class [0,0,0,1,1,2]: max=3; class1 dup from {3,4}; class2 dups=5,5
    var lab_m = [0, 0, 0, 1, 1, 2]
    var osm = random_oversample_indices(lab_m, 11)
    var osm_ok = len(osm) == 9
    if osm_ok:
        for i in range(6):
            if osm[i] != i:
                osm_ok = False
        if not (osm[6] == 3 or osm[6] == 4):
            osm_ok = False
        if osm[7] != 5 or osm[8] != 5:
            osm_ok = False
        # class counts after resampling: 3 of each
        var c0 = 0
        var c1 = 0
        var c2 = 0
        for i in range(len(osm)):
            if lab_m[osm[i]] == 0:
                c0 += 1
            elif lab_m[osm[i]] == 1:
                c1 += 1
            else:
                c2 += 1
        if c0 != 3 or c1 != 3 or c2 != 3:
            osm_ok = False
    check(osm_ok, "oversample 3-class balances all classes to max=3", passed, failed)

    # balanced input -> identity; empty -> empty; deterministic
    check(
        _lists_equal_int(random_oversample_indices([0, 1, 0, 1], 5), [0, 1, 2, 3]),
        "oversample balanced -> identity",
        passed,
        failed,
    )
    check(
        len(random_oversample_indices(empty_labels, 5)) == 0,
        "oversample empty -> empty",
        passed,
        failed,
    )
    check(
        _lists_equal_int(
            random_oversample_indices(lab_m, 99),
            random_oversample_indices(lab_m, 99),
        ),
        "oversample same seed -> identical",
        passed,
        failed,
    )

    # ── random_undersample_indices: [0,0,0,1] hand-checked ───────────────────
    # min count 1 -> keep exactly one label-0 index and index 3, ascending
    var us = random_undersample_indices(lab_os, 42)
    check(
        len(us) == 2
        and us[0] >= 0 and us[0] <= 2
        and us[1] == 3,
        "undersample [0,0,0,1] -> {one of 0..2, 3} ascending",
        passed,
        failed,
    )

    # multi-class [0,0,0,1,1,2]: min=1 -> one per class, ascending, has 5
    var usm = random_undersample_indices(lab_m, 17)
    var usm_ok = len(usm) == 3
    if usm_ok:
        usm_ok = (
            usm[0] >= 0 and usm[0] <= 2
            and (usm[1] == 3 or usm[1] == 4)
            and usm[2] == 5
        )
    check(usm_ok, "undersample 3-class keeps one per class ascending", passed, failed)

    # balanced input -> identity; empty -> empty; deterministic
    check(
        _lists_equal_int(random_undersample_indices([0, 1, 0, 1], 5), [0, 1, 2, 3]),
        "undersample balanced -> identity",
        passed,
        failed,
    )
    check(
        len(random_undersample_indices(empty_labels, 5)) == 0,
        "undersample empty -> empty",
        passed,
        failed,
    )
    check(
        _lists_equal_int(
            random_undersample_indices(lab_m, 99),
            random_undersample_indices(lab_m, 99),
        ),
        "undersample same seed -> identical",
        passed,
        failed,
    )

    print("  [imbalance] Passed:", passed, "Failed:", failed)
