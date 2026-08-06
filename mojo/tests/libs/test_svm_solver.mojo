"""test_svm_solver.mojo — known-value tests for svm_solver."""
from svm_solver import (
    SVMModel,
    svm_fit_linear,
    svm_fit_rbf,
    svm_decision,
    svm_predict,
    svm_predict_batch,
)
from std.math import abs as fabs


def _close(a: Float64, b: Float64, eps: Float64) -> Bool:
    return fabs(a - b) <= eps


def check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ svm_solver::" + name)
    else:
        failed += 1
        print("  ❌ svm_solver::" + name)


def _point(x0: Float64, x1: Float64, mut X: List[Float64]):
    X.append(x0)
    X.append(x1)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── two-point 1D problem: exact hand-computed SMO solution ──────────────
    # X = [-1, +1], y = [-1, +1], C = 10. Max-margin: w = 1, b = 0.
    # Dual: sum a_i y_i = 0 and w = a0 + a1 => a0 = a1 = 0.5 exactly.
    # First SMO step: eta = 2K01-K00-K11 = -4, a_j = 0 - 1*(1-(-1))/(-4) = 0.5,
    # a_i = 0.5, b1 = b2 = 0 -> converged, no further updates possible.
    var x1d = List[Float64]()
    x1d.append(-1.0)
    x1d.append(1.0)
    var y1d = List[Float64]()
    y1d.append(-1.0)
    y1d.append(1.0)
    var m1 = svm_fit_linear(x1d, y1d, 1, 10.0, 1e-3, 5, 1)
    check(
        len(m1.alphas) == 2
        and _close(m1.alphas[0], 0.5, 1e-9)
        and _close(m1.alphas[1], 0.5, 1e-9),
        "two-point exact alphas [0.5, 0.5]",
        passed,
        failed,
    )
    check(_close(m1.b, 0.0, 1e-9), "two-point exact b = 0", passed, failed)
    check(
        len(m1.w) == 1 and _close(m1.w[0], 1.0, 1e-9),
        "two-point exact w = [1.0]",
        passed,
        failed,
    )
    var q = List[Float64]()
    q.append(2.0)
    check(
        _close(svm_decision(m1, q), 2.0, 1e-9),
        "two-point decision(2.0) = 2.0 exactly",
        passed,
        failed,
    )
    var qn = List[Float64]()
    qn.append(-0.5)
    var qp = List[Float64]()
    qp.append(0.5)
    check(
        svm_predict(m1, qn) == -1.0 and svm_predict(m1, qp) == 1.0,
        "two-point predict signs",
        passed,
        failed,
    )
    check(
        m1.n_support == 2
        and _close(m1.support_coef[0] + m1.support_coef[1], 0.0, 1e-9),
        "two-point support coefs sum to 0 (dual constraint)",
        passed,
        failed,
    )

    # ── linearly separable 2D: 100% train accuracy + margin signs ───────────
    # pos {(3,3),(4,3),(3,4),(4,4),(5,2.5)}  neg {(0,0),(1,0),(0,1),(1,1),(-1,0.5)}
    # True max-margin boundary is x0 + x1 = 4 (supports (3,3) and (1,1)).
    var X2 = List[Float64]()
    _point(3.0, 3.0, X2)
    _point(4.0, 3.0, X2)
    _point(3.0, 4.0, X2)
    _point(4.0, 4.0, X2)
    _point(5.0, 2.5, X2)
    _point(0.0, 0.0, X2)
    _point(1.0, 0.0, X2)
    _point(0.0, 1.0, X2)
    _point(1.0, 1.0, X2)
    _point(-1.0, 0.5, X2)
    var y2 = List[Float64]()
    for _ in range(5):
        y2.append(1.0)
    for _ in range(5):
        y2.append(-1.0)
    var m2 = svm_fit_linear(X2, y2, 2, 10.0, 1e-4, 30, 42)
    var preds2 = svm_predict_batch(m2, X2)
    var correct2 = 0
    for i in range(10):
        if preds2[i] == y2[i]:
            correct2 += 1
    check(correct2 == 10, "separable 2D 100% train accuracy", passed, failed)

    var min_margin: Float64 = 1e30
    for i in range(10):
        var row = List[Float64]()
        row.append(X2[2 * i])
        row.append(X2[2 * i + 1])
        var fm = y2[i] * svm_decision(m2, row)
        if fm < min_margin:
            min_margin = fm
    check(min_margin > 0.0, "separable 2D all functional margins positive", passed, failed)
    check(
        min_margin >= 0.9,
        "separable 2D min functional margin >= 0.9 (~1 at optimum)",
        passed,
        failed,
    )
    check(
        len(m2.w) == 2 and m2.w[0] > 0.0 and m2.w[1] > 0.0,
        "separable 2D w points toward positive class",
        passed,
        failed,
    )
    # Boundary near x0 + x1 = 4: (0.5,0.5) negative side, (3.5,3.5) positive.
    var qlo = List[Float64]()
    _point(0.5, 0.5, qlo)
    var qhi = List[Float64]()
    _point(3.5, 3.5, qhi)
    check(
        svm_decision(m2, qlo) < 0.0 and svm_decision(m2, qhi) > 0.0,
        "separable 2D boundary side checks",
        passed,
        failed,
    )
    # Dual equality constraint sum alpha_i y_i = 0 preserved by SMO updates.
    var asum: Float64 = 0.0
    for i in range(10):
        asum += m2.alphas[i] * y2[i]
    check(_close(asum, 0.0, 1e-9), "separable 2D sum(alpha*y) = 0", passed, failed)
    # Batch and single-point predictions agree.
    var agree = True
    for i in range(10):
        var row = List[Float64]()
        row.append(X2[2 * i])
        row.append(X2[2 * i + 1])
        if svm_predict(m2, row) != preds2[i]:
            agree = False
    check(agree, "predict_batch matches per-row predict", passed, failed)

    # ── XOR with RBF kernel: >90% accuracy ───────────────────────────────────
    # 4 corner clusters of 4 points each: (0,0)/(1,1) -> -1, (0,1)/(1,0) -> +1.
    var Xx = List[Float64]()
    var yx = List[Float64]()
    var cx = List[Float64]()
    cx.append(0.0)
    cx.append(1.0)
    cx.append(0.0)
    cx.append(1.0)
    var cy = List[Float64]()
    cy.append(0.0)
    cy.append(1.0)
    cy.append(1.0)
    cy.append(0.0)
    var cl = List[Float64]()
    cl.append(-1.0)
    cl.append(-1.0)
    cl.append(1.0)
    cl.append(1.0)
    var ox = List[Float64]()
    ox.append(0.0)
    ox.append(0.1)
    ox.append(0.0)
    ox.append(0.1)
    var oy = List[Float64]()
    oy.append(0.0)
    oy.append(0.0)
    oy.append(0.1)
    oy.append(0.1)
    for c in range(4):
        for o in range(4):
            _point(cx[c] + ox[o], cy[c] + oy[o], Xx)
            yx.append(cl[c])
    var mx = svm_fit_rbf(Xx, yx, 2, 10.0, 1e-3, 30, 2.0, 7)
    var predsx = svm_predict_batch(mx, Xx)
    var correctx = 0
    for i in range(16):
        if predsx[i] == yx[i]:
            correctx += 1
    check(correctx >= 15, "XOR RBF train accuracy > 90% (>=15/16)", passed, failed)
    # Exact corner sign checks.
    var c00 = List[Float64]()
    _point(0.0, 0.0, c00)
    var c11 = List[Float64]()
    _point(1.0, 1.0, c11)
    var c01 = List[Float64]()
    _point(0.0, 1.0, c01)
    var c10 = List[Float64]()
    _point(1.0, 0.0, c10)
    check(
        svm_predict(mx, c00) == -1.0
        and svm_predict(mx, c11) == -1.0
        and svm_predict(mx, c01) == 1.0
        and svm_predict(mx, c10) == 1.0,
        "XOR RBF corner labels exact",
        passed,
        failed,
    )
    check(
        mx.n_support > 0 and mx.kernel_type == 1,
        "XOR RBF keeps support alphas",
        passed,
        failed,
    )
    var csum: Float64 = 0.0
    for s in range(mx.n_support):
        csum += mx.support_coef[s]
    check(_close(csum, 0.0, 1e-6), "XOR RBF sum(support coefs) = 0", passed, failed)

    # ── determinism under fixed seed ─────────────────────────────────────────
    var mx2 = svm_fit_rbf(Xx, yx, 2, 10.0, 1e-3, 30, 2.0, 7)
    var det_rbf = len(mx2.alphas) == len(mx.alphas) and mx2.b == mx.b
    if det_rbf:
        for i in range(len(mx.alphas)):
            if mx2.alphas[i] != mx.alphas[i]:
                det_rbf = False
    check(det_rbf, "RBF fit deterministic for seed=7", passed, failed)

    var m2b = svm_fit_linear(X2, y2, 2, 10.0, 1e-4, 30, 42)
    var det_lin = m2b.b == m2.b and len(m2b.w) == 2
    if det_lin:
        for f in range(2):
            if m2b.w[f] != m2.w[f]:
                det_lin = False
        for i in range(len(m2.alphas)):
            if m2b.alphas[i] != m2.alphas[i]:
                det_lin = False
    check(det_lin, "linear fit deterministic for seed=42", passed, failed)

    # Different seed on separable data still classifies perfectly.
    var m2c = svm_fit_linear(X2, y2, 2, 10.0, 1e-4, 30, 99)
    var preds2c = svm_predict_batch(m2c, X2)
    var correct2c = 0
    for i in range(10):
        if preds2c[i] == y2[i]:
            correct2c += 1
    check(correct2c == 10, "separable 2D 100% accuracy under seed=99", passed, failed)

    # ── edge cases ───────────────────────────────────────────────────────────
    var Xe = List[Float64]()
    var ye = List[Float64]()
    var me = svm_fit_linear(Xe, ye, 2, 1.0, 1e-3, 10, 0)
    var q00 = List[Float64]()
    _point(0.0, 0.0, q00)
    check(
        len(me.alphas) == 0
        and me.n_support == 0
        and svm_decision(me, q00) == 0.0
        and svm_predict(me, q00) == 1.0,
        "empty input -> empty model, decision 0, predict +1",
        passed,
        failed,
    )

    var X1 = List[Float64]()
    _point(1.0, 2.0, X1)
    var y1 = List[Float64]()
    y1.append(1.0)
    var ms = svm_fit_linear(X1, y1, 2, 1.0, 1e-3, 10, 3)
    check(
        len(ms.alphas) == 1
        and ms.alphas[0] == 0.0
        and ms.b == 0.0
        and ms.n_support == 0
        and svm_predict(ms, X1) == 1.0,
        "n=1 -> zero alphas, no SMO, predict +1",
        passed,
        failed,
    )

    # All-equal labels: no KKT-violating pair (L == H always) -> alphas stay 0.
    var Xs = List[Float64]()
    _point(0.0, 0.0, Xs)
    _point(1.0, 0.0, Xs)
    _point(0.0, 1.0, Xs)
    _point(1.0, 1.0, Xs)
    var ys = List[Float64]()
    for _ in range(4):
        ys.append(1.0)
    var msame = svm_fit_linear(Xs, ys, 2, 1.0, 1e-3, 10, 5)
    var all_zero = len(msame.alphas) == 4
    for i in range(len(msame.alphas)):
        if msame.alphas[i] != 0.0:
            all_zero = False
    var preds_same = svm_predict_batch(msame, Xs)
    var all_pos = len(preds_same) == 4
    for i in range(len(preds_same)):
        if preds_same[i] != 1.0:
            all_pos = False
    check(
        all_zero and msame.b == 0.0 and all_pos,
        "all-same-label -> zero alphas, b=0, all predicted +1",
        passed,
        failed,
    )

    # Bad shapes / bad params -> empty model.
    var Xbad = List[Float64]()
    Xbad.append(1.0)
    Xbad.append(2.0)
    Xbad.append(3.0)
    var ybad = List[Float64]()
    ybad.append(1.0)
    ybad.append(-1.0)
    var mbad = svm_fit_linear(Xbad, ybad, 2, 1.0, 1e-3, 10, 0)
    var mc0 = svm_fit_linear(X2, y2, 2, 0.0, 1e-3, 10, 0)
    var mp0 = svm_fit_rbf(X2, y2, 2, 1.0, 1e-3, 0, 1.0, 0)
    check(
        len(mbad.alphas) == 0 and len(mc0.alphas) == 0 and len(mp0.alphas) == 0,
        "bad shape / C<=0 / max_passes<=0 -> empty model",
        passed,
        failed,
    )

    print("  [svm_solver] Passed:", passed, "Failed:", failed)
