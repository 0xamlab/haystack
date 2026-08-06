"""test_ensembles.mojo — known-value tests for ensembles."""
from ensembles import (
    voting_classify,
    blend_regression,
    stack_fit_ridge,
    stack_predict,
)

from std.math import abs as fabs


def _int_lists_equal(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


def _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    return fabs(a - b) <= tol


def check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ ensembles::" + name)
    else:
        failed += 1
        print("  ❌ ensembles::" + name)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── voting_classify: majority vote, hand-computed ────────────────────────
    # 3 models x 4 samples, 3 classes (flat model-major):
    #   m0: 0 1 2 1
    #   m1: 0 1 1 2
    #   m2: 1 1 2 2
    # sample0: {0:2, 1:1} -> 0; sample1: all 1 -> 1;
    # sample2: {2:2, 1:1} -> 2; sample3: {1:1, 2:2} -> 2.
    var labels = List[Int]()
    labels.append(0); labels.append(1); labels.append(2); labels.append(1)
    labels.append(0); labels.append(1); labels.append(1); labels.append(2)
    labels.append(1); labels.append(1); labels.append(2); labels.append(2)
    var no_w = List[Float64]()
    var maj = voting_classify(labels, 3, 4, 3, no_w)
    var maj_expect = List[Int]()
    maj_expect.append(0); maj_expect.append(1)
    maj_expect.append(2); maj_expect.append(2)
    check(
        _int_lists_equal(maj, maj_expect),
        "voting_classify majority hand case",
        passed,
        failed,
    )

    # ── voting_classify: weighted vote flips the outcome ─────────────────────
    # weights [0.2, 0.2, 0.6]: sample0 class0=0.4 < class1=0.6 -> 1;
    # samples 1..3 unchanged -> [1, 1, 2, 2].
    var wv = List[Float64]()
    wv.append(0.2); wv.append(0.2); wv.append(0.6)
    var wmaj = voting_classify(labels, 3, 4, 3, wv)
    var wmaj_expect = List[Int]()
    wmaj_expect.append(1); wmaj_expect.append(1)
    wmaj_expect.append(2); wmaj_expect.append(2)
    check(
        _int_lists_equal(wmaj, wmaj_expect),
        "voting_classify weighted hand case",
        passed,
        failed,
    )

    # ── voting_classify: exact tie -> lowest class index ─────────────────────
    # 2 models, 1 sample: m0 says 1, m1 says 0, uniform weights -> tie -> 0.
    var tie = List[Int]()
    tie.append(1); tie.append(0)
    var tie_out = voting_classify(tie, 2, 1, 2, no_w)
    check(
        len(tie_out) == 1 and tie_out[0] == 0,
        "voting_classify tie -> lowest class index",
        passed,
        failed,
    )

    # ── voting_classify: out-of-range labels ignored ─────────────────────────
    # m0 predicts 5 (invalid for n_classes=3), m1 predicts 1 -> 1 wins.
    var oor = List[Int]()
    oor.append(5); oor.append(1)
    var oor_out = voting_classify(oor, 2, 1, 3, no_w)
    check(
        len(oor_out) == 1 and oor_out[0] == 1,
        "voting_classify out-of-range labels ignored",
        passed,
        failed,
    )

    # ── voting_classify: all models agree / n=1 minimal ──────────────────────
    var agree = List[Int]()
    agree.append(2)
    var agree_out = voting_classify(agree, 1, 1, 3, no_w)
    check(
        len(agree_out) == 1 and agree_out[0] == 2,
        "voting_classify single model single sample",
        passed,
        failed,
    )

    # ── voting_classify: invalid dims -> empty ───────────────────────────────
    var empty_labels = List[Int]()
    check(
        len(voting_classify(empty_labels, 0, 4, 3, no_w)) == 0
        and len(voting_classify(labels, 3, 4, 0, no_w)) == 0
        and len(voting_classify(labels, 3, 5, 3, no_w)) == 0
        and len(voting_classify(empty_labels, 2, 2, 2, no_w)) == 0,
        "voting_classify invalid dims -> empty",
        passed,
        failed,
    )

    # ── blend_regression: hand-computed weighted average ─────────────────────
    # m0 = [1, 2], m1 = [3, 6], weights [0.25, 0.75]:
    #   sample0 = 0.25*1 + 0.75*3 = 2.5; sample1 = 0.25*2 + 0.75*6 = 5.0.
    var bp = List[Float64]()
    bp.append(1.0); bp.append(2.0); bp.append(3.0); bp.append(6.0)
    var bw = List[Float64]()
    bw.append(0.25); bw.append(0.75)
    var blend = blend_regression(bp, 2, 2, bw)
    check(
        len(blend) == 2
        and _close(blend[0], 2.5, 1e-12)
        and _close(blend[1], 5.0, 1e-12),
        "blend_regression weighted hand case",
        passed,
        failed,
    )

    # ── blend_regression: unnormalized weights [1,3] == [0.25,0.75] ─────────
    var bw2 = List[Float64]()
    bw2.append(1.0); bw2.append(3.0)
    var blend2 = blend_regression(bp, 2, 2, bw2)
    check(
        len(blend2) == 2
        and _close(blend2[0], 2.5, 1e-12)
        and _close(blend2[1], 5.0, 1e-12),
        "blend_regression normalizes weights",
        passed,
        failed,
    )

    # ── blend_regression: empty weights -> uniform mean ──────────────────────
    # means: (1+3)/2 = 2, (2+6)/2 = 4.
    var blend3 = blend_regression(bp, 2, 2, no_w)
    check(
        len(blend3) == 2
        and _close(blend3[0], 2.0, 1e-12)
        and _close(blend3[1], 4.0, 1e-12),
        "blend_regression empty weights -> uniform mean",
        passed,
        failed,
    )

    # ── blend_regression: zero-sum weights fall back to uniform ─────────────
    var bw3 = List[Float64]()
    bw3.append(1.0); bw3.append(-1.0)
    var blend4 = blend_regression(bp, 2, 2, bw3)
    check(
        len(blend4) == 2
        and _close(blend4[0], 2.0, 1e-12)
        and _close(blend4[1], 4.0, 1e-12),
        "blend_regression zero-sum weights -> uniform",
        passed,
        failed,
    )

    # ── blend_regression: invalid dims -> empty ──────────────────────────────
    var empty_f = List[Float64]()
    check(
        len(blend_regression(empty_f, 0, 2, no_w)) == 0
        and len(blend_regression(bp, 3, 2, no_w)) == 0,
        "blend_regression invalid dims -> empty",
        passed,
        failed,
    )

    # ── stack_fit_ridge: 1-model hand value ──────────────────────────────────
    # X = [1, 2] (2 samples x 1 model), y = [2, 4], l2 = 1:
    #   (X'X + 1) w = X'y  ->  (5 + 1) w = 10  ->  w = 10/6.
    var sx = List[Float64]()
    sx.append(1.0); sx.append(2.0)
    var sy = List[Float64]()
    sy.append(2.0); sy.append(4.0)
    var w1 = stack_fit_ridge(sx, 2, 1, sy, 1.0)
    check(
        len(w1) == 1 and _close(w1[0], 10.0 / 6.0, 1e-12),
        "stack_fit_ridge 1-model hand value",
        passed,
        failed,
    )
    # Same system with l2 = 0: w = 10/5 = 2 (exact least squares).
    var w1b = stack_fit_ridge(sx, 2, 1, sy, 0.0)
    check(
        len(w1b) == 1 and _close(w1b[0], 2.0, 1e-12),
        "stack_fit_ridge l2=0 exact least squares",
        passed,
        failed,
    )

    # ── stack_fit_ridge: model1 == y exactly -> w ~ [1, 0] ───────────────────
    # y = [1..5]; model1 = y, model2 = const 3 (sample-major flat).
    # Hand normal equations: X'X = [[55,45],[45,45]], X'y = [55,45];
    # with tiny l2 the solution is ~[1, 0].
    var oof = List[Float64]()
    var y5 = List[Float64]()
    for i in range(1, 6):
        oof.append(Float64(i))    # model1 = y
        oof.append(3.0)           # model2 = constant
        y5.append(Float64(i))
    var wst = stack_fit_ridge(oof, 5, 2, y5, 0.001)
    check(
        len(wst) == 2
        and _close(wst[0], 1.0, 0.05)
        and _close(wst[1], 0.0, 0.05),
        "stack_fit_ridge perfect model -> weight ~[1,0]",
        passed,
        failed,
    )

    # ── stack_fit_ridge + stack_predict roundtrip reproduces y ───────────────
    var yhat = stack_predict(oof, 5, 2, wst)
    var round_ok = len(yhat) == 5
    if round_ok:
        for i in range(5):
            if not _close(yhat[i], y5[i], 0.05):
                round_ok = False
    check(round_ok, "stack fit+predict roundtrip ~ y", passed, failed)

    # ── stack_fit_ridge: duplicated models, l2=0 -> singular -> empty ────────
    var dup = List[Float64]()
    for i in range(1, 6):
        dup.append(Float64(i))
        dup.append(Float64(i))
    check(
        len(stack_fit_ridge(dup, 5, 2, y5, 0.0)) == 0,
        "stack_fit_ridge singular (dup models, l2=0) -> empty",
        passed,
        failed,
    )
    # Same duplicated system with l2 > 0 becomes solvable; by symmetry the
    # two weights are equal and sum to ~1 (they split the perfect model).
    var wdup = stack_fit_ridge(dup, 5, 2, y5, 0.001)
    check(
        len(wdup) == 2
        and _close(wdup[0], wdup[1], 1e-9)
        and _close(wdup[0] + wdup[1], 1.0, 0.05),
        "stack_fit_ridge dup models + ridge -> symmetric split",
        passed,
        failed,
    )

    # ── stack_fit_ridge: invalid dims -> empty ───────────────────────────────
    check(
        len(stack_fit_ridge(empty_f, 0, 1, sy, 1.0)) == 0
        and len(stack_fit_ridge(sx, 2, 1, y5, 1.0)) == 0
        and len(stack_fit_ridge(sx, 2, 2, sy, 1.0)) == 0,
        "stack_fit_ridge invalid dims -> empty",
        passed,
        failed,
    )

    # ── stack_predict: hand-computed dot products ────────────────────────────
    # preds (2 samples x 2 models) = [[1,2],[3,4]], weights [0.5, 2.0]:
    #   sample0 = 0.5*1 + 2*2 = 4.5; sample1 = 0.5*3 + 2*4 = 9.5.
    var sp = List[Float64]()
    sp.append(1.0); sp.append(2.0); sp.append(3.0); sp.append(4.0)
    var spw = List[Float64]()
    spw.append(0.5); spw.append(2.0)
    var spo = stack_predict(sp, 2, 2, spw)
    check(
        len(spo) == 2
        and _close(spo[0], 4.5, 1e-12)
        and _close(spo[1], 9.5, 1e-12),
        "stack_predict hand case",
        passed,
        failed,
    )

    # ── stack_predict: invalid dims -> empty ─────────────────────────────────
    check(
        len(stack_predict(sp, 2, 2, no_w)) == 0
        and len(stack_predict(sp, 3, 2, spw)) == 0
        and len(stack_predict(empty_f, 0, 2, spw)) == 0,
        "stack_predict invalid dims -> empty",
        passed,
        failed,
    )

    print("  [ensembles] Passed:", passed, "Failed:", failed)
