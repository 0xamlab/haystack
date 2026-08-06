"""test_gaussian_process.mojo — known-value tests for gaussian_process."""
from gaussian_process import (
    KERNEL_RBF,
    KERNEL_MATERN32,
    kernel_rbf,
    kernel_matern32,
    GPFit,
    GPPrediction,
    gp_fit,
    gp_predict,
    gp_loglik,
)
from std.math import sqrt, log, exp, abs as fabs


def _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    return fabs(a - b) <= tol


def check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ gaussian_process::" + name)
    else:
        failed += 1
        print("  ❌ gaussian_process::" + name)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── kernel_rbf: hand-computed known values ───────────────────────────────
    # k(1; l=1, sv=1) = exp(-0.5) = 0.6065306597126334
    # k(2; l=2, sv=3) = 3*exp(-0.5) = 1.8195919791379003
    check(
        _close(kernel_rbf(1.0, 1.0, 1.0), 0.6065306597126334, 1e-12)
        and _close(kernel_rbf(2.0, 2.0, 3.0), 1.8195919791379003, 1e-12)
        and _close(kernel_rbf(0.0, 1.5, 2.5), 2.5, 1e-15)
        and _close(kernel_rbf(-1.0, 1.0, 1.0), 0.6065306597126334, 1e-12)
        and kernel_rbf(1.0, 0.0, 1.0) == 0.0,
        "kernel_rbf known values + r=0 -> signal_var + |r| + bad lengthscale",
        passed,
        failed,
    )

    # ── kernel_matern32: hand-computed known values ──────────────────────────
    # k(1; 1, 1) = (1+sqrt(3))*exp(-sqrt(3)) = 0.4833577245965077
    # k(0.5; 1, 1) = 0.7848876539574506
    check(
        _close(kernel_matern32(1.0, 1.0, 1.0), 0.4833577245965077, 1e-12)
        and _close(kernel_matern32(0.5, 1.0, 1.0), 0.7848876539574506, 1e-12)
        and _close(kernel_matern32(0.0, 2.0, 1.7), 1.7, 1e-15)
        and kernel_matern32(1.0, -1.0, 1.0) == 0.0,
        "kernel_matern32 known values + r=0 -> signal_var",
        passed,
        failed,
    )
    check(
        kernel_matern32(0.5, 1.0, 1.0) > kernel_matern32(1.0, 1.0, 1.0)
        and kernel_matern32(1.0, 1.0, 1.0) > kernel_matern32(2.0, 1.0, 1.0),
        "kernel_matern32 monotone decreasing in r",
        passed,
        failed,
    )

    # ── gp_fit: shapes + determinism ─────────────────────────────────────────
    var x3 = List[Float64]()
    x3.append(0.0); x3.append(1.0); x3.append(2.0)
    var y3 = List[Float64]()
    y3.append(1.0); y3.append(-1.0); y3.append(0.5)
    var fit3 = gp_fit(x3, y3, 1, 1.0, 1.0, 1e-8, KERNEL_RBF)
    check(
        fit3.ok
        and fit3.n == 3
        and fit3.dim == 1
        and len(fit3.chol) == 9
        and len(fit3.alpha) == 3
        and fit3.jitter == 0.0,
        "gp_fit shapes: n=3 -> 9-entry chol, 3-entry alpha, no jitter",
        passed,
        failed,
    )
    var fit3b = gp_fit(x3, y3, 1, 1.0, 1.0, 1e-8, KERNEL_RBF)
    var det_same = fit3b.ok and len(fit3b.alpha) == 3
    if det_same:
        for i in range(3):
            if fit3.alpha[i] != fit3b.alpha[i]:
                det_same = False
    check(det_same, "gp_fit deterministic: identical alpha on refit", passed, failed)

    # Cholesky upper triangle strictly zero; diagonal positive.
    var tri_ok = True
    for i in range(3):
        if fit3.chol[i * 3 + i] <= 0.0:
            tri_ok = False
        for j in range(i + 1, 3):
            if fit3.chol[i * 3 + j] != 0.0:
                tri_ok = False
    check(tri_ok, "gp_fit chol lower-triangular with positive diagonal", passed, failed)
    # Hand-check L[0][0] = sqrt(K00) = sqrt(1 + 1e-8).
    check(
        _close(fit3.chol[0], sqrt(1.0 + 1e-8), 1e-14),
        "gp_fit chol[0,0] = sqrt(signal_var + noise_var) exact",
        passed,
        failed,
    )

    # ── interpolation (RBF): predict AT training points returns ~y_i ────────
    var pr = gp_predict(x3, fit3, x3)
    var interp_ok = pr.ok and len(pr.mean) == 3 and len(pr.variance) == 3
    if interp_ok:
        for i in range(3):
            if not _close(pr.mean[i], y3[i], 1e-3):
                interp_ok = False
            if pr.variance[i] > 1e-3 or pr.variance[i] < 0.0:
                interp_ok = False
    check(
        interp_ok,
        "RBF interpolation: mean ~= y_i at training points, var ~ 0 (tol 1e-3)",
        passed,
        failed,
    )

    # ── interpolation (Matern-3/2) ───────────────────────────────────────────
    var fitm = gp_fit(x3, y3, 1, 1.0, 1.0, 1e-8, KERNEL_MATERN32)
    var prm = gp_predict(x3, fitm, x3)
    var interp_m = fitm.ok and prm.ok and len(prm.mean) == 3
    if interp_m:
        for i in range(3):
            if not _close(prm.mean[i], y3[i], 1e-3):
                interp_m = False
            if prm.variance[i] > 1e-3:
                interp_m = False
    check(
        interp_m,
        "Matern-3/2 interpolation: mean ~= y_i, var ~ 0 (tol 1e-3)",
        passed,
        failed,
    )

    # ── far from data: mean -> 0 (prior), variance -> signal_var ────────────
    var fit_far = gp_fit(x3, y3, 1, 1.0, 2.5, 1e-8, KERNEL_RBF)
    var far_pt = List[Float64]()
    far_pt.append(100.0)
    var pf = gp_predict(x3, fit_far, far_pt)
    check(
        pf.ok
        and len(pf.mean) == 1
        and _close(pf.mean[0], 0.0, 1e-6)
        and _close(pf.variance[0], 2.5, 1e-6),
        "far from data: mean -> 0, variance -> signal_var (2.5)",
        passed,
        failed,
    )
    var pfm = gp_predict(x3, fitm, far_pt)
    check(
        pfm.ok and _close(pfm.mean[0], 0.0, 1e-6)
        and _close(pfm.variance[0], 1.0, 1e-6),
        "far from data (Matern): variance -> signal_var (1.0)",
        passed,
        failed,
    )

    # ── loglik: 2-point toy vs closed form ───────────────────────────────────
    # x=[0,1], y=[1,2], RBF l=1 sv=1 noise=0.1. K = [[1.1, e^-0.5],[e^-0.5, 1.1]]
    # Closed form (2x2 analytic inverse):
    #   det = 1.1^2 - e^-1, quad = (1.1*(1+4) - 2*e^-0.5*1*2)/det
    #   ll  = -quad/2 - log(det)/2 - log(2*pi) = -3.5770425527832885
    var x2 = List[Float64]()
    x2.append(0.0); x2.append(1.0)
    var y2 = List[Float64]()
    y2.append(1.0); y2.append(2.0)
    var fit2 = gp_fit(x2, y2, 1, 1.0, 1.0, 0.1, KERNEL_RBF)
    var ll2 = gp_loglik(fit2, y2)
    var a2 = 1.1
    var b2 = exp(-0.5)
    var det2 = a2 * a2 - b2 * b2
    var quad2 = (a2 * (1.0 * 1.0 + 2.0 * 2.0) - 2.0 * b2 * 1.0 * 2.0) / det2
    var ll_closed = -0.5 * quad2 - 0.5 * log(det2) - log(2.0 * 3.141592653589793)
    check(
        fit2.ok and _close(ll2, ll_closed, 1e-9),
        "gp_loglik 2-point toy == closed-form 2x2 (tol 1e-9)",
        passed,
        failed,
    )
    # Hand value computed at full Float64 precision; Mojo std.math log/exp
    # are ~1e-10-accurate approximations, hence tol 1e-8 on absolute values.
    check(
        _close(ll2, -3.5770425527832885, 1e-8),
        "gp_loglik 2-point toy == -3.5770425527832885 hand value",
        passed,
        failed,
    )
    # Same toy: alpha = K^-1 y hand-computed = [-0.134257878..., 1.892210472...]
    check(
        _close(fit2.alpha[0], -0.13425787820991109, 1e-9)
        and _close(fit2.alpha[1], 1.8922104722202504, 1e-9),
        "gp_fit alpha == analytic K^-1 y on 2-point toy",
        passed,
        failed,
    )
    # Predict at x*=0.5: k* = [e^-0.125, e^-0.125]
    #   mean = k*.alpha = 1.5513877191046792
    #   var  = 1 - k*^T K^-1 k* = 0.08727009545489339
    var mid = List[Float64]()
    mid.append(0.5)
    var p2 = gp_predict(x2, fit2, mid)
    check(
        p2.ok
        and _close(p2.mean[0], 1.5513877191046792, 1e-9)
        and _close(p2.variance[0], 0.08727009545489339, 1e-9),
        "gp_predict 2-point toy @0.5 == analytic mean/var",
        passed,
        failed,
    )

    # ── loglik: n=1 closed form ──────────────────────────────────────────────
    # y=1.5, sv=2.0, noise=0.5 -> a=2.5:
    #   ll = -0.5*1.5^2/2.5 - 0.5*log(2.5) - 0.5*log(2*pi) = -1.8270838991417502
    var x1 = List[Float64]()
    x1.append(7.0)
    var y1 = List[Float64]()
    y1.append(1.5)
    var fit1 = gp_fit(x1, y1, 1, 1.0, 2.0, 0.5, KERNEL_RBF)
    check(
        fit1.ok and _close(gp_loglik(fit1, y1), -1.8270838991417502, 1e-8),
        "gp_loglik n=1 == closed form -1.8270838991417502",
        passed,
        failed,
    )
    # n=1 predict at the training point: mean = sv/(sv+noise)*y = 2/2.5*1.5 = 1.2
    var p1 = gp_predict(x1, fit1, x1)
    check(
        p1.ok and _close(p1.mean[0], 1.2, 1e-12)
        and _close(p1.variance[0], 2.0 - 4.0 / 2.5, 1e-12),
        "n=1 predict at train point: mean = sv/(sv+noise)*y = 1.2 exact",
        passed,
        failed,
    )

    # ── ties: duplicate training rows ────────────────────────────────────────
    # X=[0,0], y=[1,3], nu=1e-6: mean@0 = (1+3)/(2+nu), var@0 = nu/(2+nu).
    var xd = List[Float64]()
    xd.append(0.0); xd.append(0.0)
    var yd = List[Float64]()
    yd.append(1.0); yd.append(3.0)
    var fitd = gp_fit(xd, yd, 1, 1.0, 1.0, 1e-6, KERNEL_RBF)
    var zero = List[Float64]()
    zero.append(0.0)
    var pd = gp_predict(xd, fitd, zero)
    check(
        fitd.ok
        and pd.ok
        and _close(pd.mean[0], 1.9999990000005, 1e-3)
        and pd.variance[0] < 1e-5,
        "duplicate rows: mean@dup ~= avg(y) = (1+3)/(2+nu), tiny var",
        passed,
        failed,
    )

    # ── all-equal targets ────────────────────────────────────────────────────
    var ye = List[Float64]()
    ye.append(4.0); ye.append(4.0); ye.append(4.0)
    var fite = gp_fit(x3, ye, 1, 1.0, 1.0, 1e-8, KERNEL_RBF)
    var pe = gp_predict(x3, fite, x3)
    var eq_ok = fite.ok and pe.ok
    if eq_ok:
        for i in range(3):
            if not _close(pe.mean[i], 4.0, 1e-3):
                eq_ok = False
    check(eq_ok, "all-equal y: interpolates the constant 4.0", passed, failed)

    # ── 2-D inputs (dim=2) ───────────────────────────────────────────────────
    # Train (0,0),(3,4) -> distance 5. Predict at (0,0) ~= y0; far -> sv.
    var x2d = List[Float64]()
    x2d.append(0.0); x2d.append(0.0)
    x2d.append(3.0); x2d.append(4.0)
    var y2d = List[Float64]()
    y2d.append(1.0); y2d.append(-2.0)
    var fit2d = gp_fit(x2d, y2d, 2, 2.0, 1.0, 1e-8, KERNEL_RBF)
    var origin = List[Float64]()
    origin.append(0.0); origin.append(0.0)
    var p2d = gp_predict(x2d, fit2d, origin)
    var far2d = List[Float64]()
    far2d.append(100.0); far2d.append(100.0)
    var pf2d = gp_predict(x2d, fit2d, far2d)
    check(
        fit2d.ok
        and p2d.ok
        and _close(p2d.mean[0], 1.0, 1e-3)
        and p2d.variance[0] < 1e-3
        and pf2d.ok
        and _close(pf2d.variance[0], 1.0, 1e-6),
        "dim=2: interpolates at (0,0), far point var -> signal_var",
        passed,
        failed,
    )

    # ── multi-point predict batch ────────────────────────────────────────────
    var batch = List[Float64]()
    batch.append(0.0); batch.append(0.5); batch.append(2.0)
    var pb = gp_predict(x3, fit3, batch)
    check(
        pb.ok and len(pb.mean) == 3 and len(pb.variance) == 3
        and _close(pb.mean[0], 1.0, 1e-3)
        and _close(pb.mean[2], 0.5, 1e-3),
        "batch predict: 3 query points -> 3 means/vars",
        passed,
        failed,
    )

    # ── invalid inputs -> ok=False / NaN ─────────────────────────────────────
    var empty = List[Float64]()
    var bad1 = gp_fit(empty, empty, 1, 1.0, 1.0, 0.1, KERNEL_RBF)
    var bad2 = gp_fit(x3, y2, 1, 1.0, 1.0, 0.1, KERNEL_RBF)  # len mismatch
    var bad3 = gp_fit(x3, y3, 1, 0.0, 1.0, 0.1, KERNEL_RBF)  # lengthscale=0
    var bad4 = gp_fit(x3, y3, 1, 1.0, -1.0, 0.1, KERNEL_RBF)  # signal_var<0
    var bad5 = gp_fit(x3, y3, 1, 1.0, 1.0, -0.1, KERNEL_RBF)  # noise<0
    var bad6 = gp_fit(x3, y3, 1, 1.0, 1.0, 0.1, 5)  # unknown kernel
    var bad7 = gp_fit(x3, y3, 2, 1.0, 1.0, 0.1, KERNEL_RBF)  # wrong dim
    check(
        (not bad1.ok) and (not bad2.ok) and (not bad3.ok) and (not bad4.ok)
        and (not bad5.ok) and (not bad6.ok) and (not bad7.ok),
        "gp_fit invalid inputs -> ok=False (7 cases)",
        passed,
        failed,
    )
    var pbad = gp_predict(x3, bad1, x3)
    var pempty = gp_predict(x3, fit3, empty)
    check(
        (not pbad.ok) and len(pbad.mean) == 0
        and (not pempty.ok) and len(pempty.mean) == 0,
        "gp_predict on bad fit / empty query -> ok=False, empty",
        passed,
        failed,
    )
    check(
        gp_loglik(bad1, y3) == 0.0 and gp_loglik(fit3, y2) == 0.0,
        "gp_loglik bad fit or wrong-length y -> 0.0 (NaN cannot cross the JSON result wire)",
        passed,
        failed,
    )

    print("  [gaussian_process] Passed:", passed, "Failed:", failed)
