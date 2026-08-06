"""test_linear_models.mojo — known-value tests for linear_models."""
from std.math import isnan, isinf, abs as fabs
from linear_models import (
    LogisticResult,
    ElasticNetResult,
    logistic_fit,
    logistic_predict_proba,
    logistic_std_errors,
    elasticnet_fit,
)


def _is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)


def check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ linear_models::" + name)
    else:
        failed += 1
        print("  ❌ linear_models::" + name)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── logistic_fit: perfectly separable 1D data ────────────────────────────
    # x < 0 -> class 0, x > 0 -> class 1. Unpenalized weights grow, but
    # probabilities must be strictly increasing in x and accuracy 100%.
    var xs = List[Float64]()
    xs.append(-2.0); xs.append(-1.5); xs.append(-1.0); xs.append(-0.5)
    xs.append(0.5); xs.append(1.0); xs.append(1.5); xs.append(2.0)
    var ys = List[Int]()
    ys.append(0); ys.append(0); ys.append(0); ys.append(0)
    ys.append(1); ys.append(1); ys.append(1); ys.append(1)
    var sep = logistic_fit(xs, ys, 0.0, 30, 1e-8)
    var proba = logistic_predict_proba(xs, sep.weights, sep.bias)
    # Strict ordering is checked on a tiny-l2 fit: with l2=0 the separable
    # optimum is at infinity and extreme probas saturate to exactly 0/1,
    # which ties adjacent entries. l2=1e-3 keeps the optimum finite/unique.
    var sepr = logistic_fit(xs, ys, 1e-3, 100, 1e-10)
    var probr = logistic_predict_proba(xs, sepr.weights, sepr.bias)
    var monotone = sepr.converged and len(probr) == 8
    if monotone:
        for i in range(7):
            if not (probr[i] < probr[i + 1]):
                monotone = False
    check(monotone, "logistic separable proba strictly increasing", passed, failed)
    var acc100 = len(proba) == 8
    if acc100:
        for i in range(8):
            var pred1 = proba[i] > 0.5
            if pred1 != (ys[i] == 1):
                acc100 = False
            if not _is_finite(proba[i]):
                acc100 = False
    check(acc100, "logistic separable accuracy 100%, finite probas", passed, failed)
    check(
        len(proba) == 8 and proba[0] < 0.05 and proba[7] > 0.95,
        "logistic separable extremes confident (<0.05 / >0.95)",
        passed,
        failed,
    )
    check(
        len(sep.weights) == 1 and sep.weights[0] > 0.0,
        "logistic separable positive slope",
        passed,
        failed,
    )

    # ── logistic_fit: 2x2 table exact MLE (statsmodels-checkable by hand) ────
    # x=0 group: y = 1,0,0,0 (p0 = 1/4); x=1 group: y = 0,1,1,1 (p1 = 3/4).
    # Closed form: bias = logit(1/4) = ln(1/3) = -1.0986122886681098
    #              w    = logit(3/4) - logit(1/4) = 2 ln 3 = 2.1972245773362196
    var xt = List[Float64]()
    xt.append(0.0); xt.append(0.0); xt.append(0.0); xt.append(0.0)
    xt.append(1.0); xt.append(1.0); xt.append(1.0); xt.append(1.0)
    var yt = List[Int]()
    yt.append(1); yt.append(0); yt.append(0); yt.append(0)
    yt.append(0); yt.append(1); yt.append(1); yt.append(1)
    var tab = logistic_fit(xt, yt, 0.0, 100, 1e-10)
    check(tab.converged, "logistic 2x2 table converged", passed, failed)
    check(
        len(tab.weights) == 1
        and fabs(tab.weights[0] - 2.1972245773362196) < 1e-6
        and fabs(tab.bias - (-1.0986122886681098)) < 1e-6,
        "logistic 2x2 table exact MLE w=2ln3, b=ln(1/3)",
        passed,
        failed,
    )
    # Log-likelihood at MLE: 8 * (0.25 ln 0.25 + 0.75 ln 0.75) = -4.4986813...
    check(
        fabs(tab.log_likelihood - (-4.498681156950466)) < 1e-6,
        "logistic 2x2 table log-likelihood exact",
        passed,
        failed,
    )
    # Fitted probabilities: group means 0.25 and 0.75.
    var ptab = logistic_predict_proba(xt, tab.weights, tab.bias)
    check(
        len(ptab) == 8
        and fabs(ptab[0] - 0.25) < 1e-6
        and fabs(ptab[4] - 0.75) < 1e-6,
        "logistic_predict_proba recovers group rates 0.25/0.75",
        passed,
        failed,
    )

    # ── logistic_std_errors: closed form for the 2x2 table ──────────────────
    # I = [[0.75, 0.75],[0.75, 1.5]] (order [w, bias]); inverse diagonal
    # [8/3, 4/3] -> se_w = sqrt(8/3) = 1.632993, se_bias = sqrt(4/3) = 1.154701.
    var se = logistic_std_errors(xt, yt, tab.weights, tab.bias, 0.0)
    check(
        len(se) == 2
        and fabs(se[0] - 1.632993161855452) < 1e-4
        and fabs(se[1] - 1.1547005383792515) < 1e-4,
        "logistic_std_errors match hand inverse-information",
        passed,
        failed,
    )

    # ── logistic_fit: all-equal labels (all ones) stays finite ──────────────
    var xa = List[Float64]()
    xa.append(0.5); xa.append(1.0); xa.append(1.5); xa.append(2.0)
    var ya = List[Int]()
    ya.append(1); ya.append(1); ya.append(1); ya.append(1)
    var allone = logistic_fit(xa, ya, 0.1, 50, 1e-8)
    var pa = logistic_predict_proba(xa, allone.weights, allone.bias)
    var ok_allone = len(pa) == 4 and _is_finite(allone.bias)
    if ok_allone:
        for i in range(4):
            if not (_is_finite(pa[i]) and pa[i] > 0.5):
                ok_allone = False
    check(ok_allone, "logistic all-ones labels finite, probas > 0.5", passed, failed)

    # ── logistic_fit: n=1, zero feature -> weight pinned by L2 at 0 ─────────
    var x1 = List[Float64]()
    x1.append(0.0)
    var y1 = List[Int]()
    y1.append(1)
    var one = logistic_fit(x1, y1, 1.0, 50, 1e-8)
    var p1 = logistic_predict_proba(x1, one.weights, one.bias)
    check(
        len(one.weights) == 1
        and fabs(one.weights[0]) < 1e-6
        and len(p1) == 1
        and _is_finite(p1[0])
        and p1[0] > 0.5,
        "logistic n=1 edge: w=0 under L2, proba > 0.5, finite",
        passed,
        failed,
    )

    # ── logistic_fit / predict_proba: malformed + empty inputs ──────────────
    var y_empty = List[Int]()
    var x_empty = List[Float64]()
    var fit_empty = logistic_fit(x_empty, y_empty, 0.1, 10, 1e-8)
    check(
        not fit_empty.converged and len(fit_empty.weights) == 0,
        "logistic empty input -> default result",
        passed,
        failed,
    )
    var x_bad = List[Float64]()
    x_bad.append(1.0); x_bad.append(2.0); x_bad.append(3.0)
    var y_two = List[Int]()
    y_two.append(0); y_two.append(1)
    var fit_bad = logistic_fit(x_bad, y_two, 0.1, 10, 1e-8)
    var w_empty = List[Float64]()
    check(
        not fit_bad.converged
        and len(fit_bad.weights) == 0
        and len(logistic_predict_proba(x_bad, w_empty, 0.0)) == 0,
        "logistic ragged X / empty weights -> empty",
        passed,
        failed,
    )

    # ── elasticnet_fit: exact solution on centered orthogonal design ────────
    # x0 = [-2,-1,0,1,2], x1 = [1,-1,0,-1,1] (orthogonal to x0, mean 0),
    # y = 2*x0. z0 = 2, <x0,y>/n = 4. With l1=0.5, l2=0.25:
    #   w0 = S(4, 0.5)/(2 + 0.25) = 3.5/2.25 = 1.5555555555555556
    #   w1 = S(0, 0.5) = 0 exactly, bias = 0.
    var Xo = List[Float64]()
    Xo.append(-2.0); Xo.append(1.0)
    Xo.append(-1.0); Xo.append(-1.0)
    Xo.append(0.0); Xo.append(0.0)
    Xo.append(1.0); Xo.append(-1.0)
    Xo.append(2.0); Xo.append(1.0)
    var yo = List[Float64]()
    yo.append(-4.0); yo.append(-2.0); yo.append(0.0); yo.append(2.0); yo.append(4.0)
    var eno = elasticnet_fit(Xo, yo, 0.5, 0.25, 200)
    check(
        eno.converged
        and len(eno.weights) == 2
        and fabs(eno.weights[0] - 1.5555555555555556) < 1e-12
        and fabs(eno.bias) < 1e-12,
        "elasticnet orthogonal design exact w0 = 3.5/2.25",
        passed,
        failed,
    )
    check(
        fabs(eno.weights[1]) < 1e-15,
        "elasticnet l1 zeroes orthogonal irrelevant feature exactly",
        passed,
        failed,
    )

    # ── elasticnet_fit: spec test — y depends only on x0, strong l1 ─────────
    # x1 weakly correlated with x0 (<x0,x1> = -0.1, mean 0), y = 2*x0.
    # Fixed point: w0 = S(4,0.5)/2 = 1.75, |rho1| = 0.005 < l1 -> w1 = 0, b = 0.
    var Xc = List[Float64]()
    Xc.append(-2.0); Xc.append(0.1)
    Xc.append(-1.0); Xc.append(-0.2)
    Xc.append(0.0); Xc.append(0.05)
    Xc.append(1.0); Xc.append(0.2)
    Xc.append(2.0); Xc.append(-0.15)
    var yc = List[Float64]()
    yc.append(-4.0); yc.append(-2.0); yc.append(0.0); yc.append(2.0); yc.append(4.0)
    var enc = elasticnet_fit(Xc, yc, 0.5, 0.0, 200)
    check(
        enc.converged
        and len(enc.weights) == 2
        and fabs(enc.weights[1]) < 1e-3,
        "elasticnet strong l1 zeroes irrelevant x1 (|w1| < 1e-3)",
        passed,
        failed,
    )
    check(
        fabs(enc.weights[0] - 1.75) < 1e-12 and fabs(enc.bias) < 1e-12,
        "elasticnet lasso shrinkage exact: w0 = S(4,0.5)/2 = 1.75",
        passed,
        failed,
    )

    # ── elasticnet_fit: l1=l2=0 recovers OLS exactly ─────────────────────────
    # y = 1 + 2x on x = 0..3 -> w = 2, b = 1 (perfect fit).
    var Xl = List[Float64]()
    Xl.append(0.0); Xl.append(1.0); Xl.append(2.0); Xl.append(3.0)
    var yl = List[Float64]()
    yl.append(1.0); yl.append(3.0); yl.append(5.0); yl.append(7.0)
    var ols = elasticnet_fit(Xl, yl, 0.0, 0.0, 500, 1e-13)
    check(
        ols.converged
        and fabs(ols.weights[0] - 2.0) < 1e-8
        and fabs(ols.bias - 1.0) < 1e-8,
        "elasticnet l1=l2=0 recovers OLS w=2, b=1",
        passed,
        failed,
    )

    # ── elasticnet_fit: ridge-only known value on centered data ─────────────
    # x = [-1,0,1], y = [-2,0,2]: z = 2/3, <x,y>/n = 4/3;
    # l2 = 1/3 -> w = (4/3)/(2/3 + 1/3) = 4/3, b = 0.
    var Xr = List[Float64]()
    Xr.append(-1.0); Xr.append(0.0); Xr.append(1.0)
    var yr = List[Float64]()
    yr.append(-2.0); yr.append(0.0); yr.append(2.0)
    var rid = elasticnet_fit(Xr, yr, 0.0, 1.0 / 3.0, 200)
    check(
        rid.converged
        and fabs(rid.weights[0] - 4.0 / 3.0) < 1e-10
        and fabs(rid.bias) < 1e-10,
        "elasticnet ridge-only exact w = 4/3 on centered data",
        passed,
        failed,
    )

    # ── elasticnet_fit: overwhelming l1 kills all weights, bias = mean(y) ───
    var yk = List[Float64]()
    yk.append(1.0); yk.append(3.0); yk.append(5.0)
    var kill = elasticnet_fit(Xr, yk, 100.0, 0.0, 100)
    check(
        kill.converged
        and fabs(kill.weights[0]) < 1e-15
        and fabs(kill.bias - 3.0) < 1e-10,
        "elasticnet huge l1 -> w=0, bias=mean(y)",
        passed,
        failed,
    )

    # ── elasticnet_fit: constant feature colinear with intercept ────────────
    # x = [1,1,1] (all-equal), y = [2,4,6], l1 = 0.1: intercept absorbs the
    # mean, soft-threshold pins w at 0, b = 4.
    var Xconst = List[Float64]()
    Xconst.append(1.0); Xconst.append(1.0); Xconst.append(1.0)
    var yconst = List[Float64]()
    yconst.append(2.0); yconst.append(4.0); yconst.append(6.0)
    var cst = elasticnet_fit(Xconst, yconst, 0.1, 0.0, 200)
    check(
        cst.converged
        and fabs(cst.weights[0]) < 1e-10
        and fabs(cst.bias - 4.0) < 1e-10,
        "elasticnet all-equal feature -> w=0, b=mean(y)",
        passed,
        failed,
    )

    # ── elasticnet_fit: all-zero column pinned at 0, rest fits OLS ──────────
    # X = [[1,0],[2,0],[3,0]], y = 2x -> w0=2, w1=0, b=0.
    var Xz = List[Float64]()
    Xz.append(1.0); Xz.append(0.0)
    Xz.append(2.0); Xz.append(0.0)
    Xz.append(3.0); Xz.append(0.0)
    var yz = List[Float64]()
    yz.append(2.0); yz.append(4.0); yz.append(6.0)
    var zc = elasticnet_fit(Xz, yz, 0.0, 0.0, 500, 1e-13)
    check(
        zc.converged
        and fabs(zc.weights[0] - 2.0) < 1e-8
        and zc.weights[1] == 0.0
        and fabs(zc.bias) < 1e-8,
        "elasticnet zero column pinned, w0=2 exact",
        passed,
        failed,
    )

    # ── elasticnet_fit: empty and n=1 edges ──────────────────────────────────
    var y_e = List[Float64]()
    var en_empty = elasticnet_fit(x_empty, y_e, 0.1, 0.1, 10)
    check(
        not en_empty.converged and len(en_empty.weights) == 0,
        "elasticnet empty input -> default result",
        passed,
        failed,
    )
    var X1 = List[Float64]()
    X1.append(3.0)
    var y1f = List[Float64]()
    y1f.append(6.0)
    var en1 = elasticnet_fit(X1, y1f, 0.0, 0.0, 100)
    check(
        en1.converged
        and _is_finite(en1.bias)
        and fabs(en1.bias + 3.0 * en1.weights[0] - 6.0) < 1e-10,
        "elasticnet n=1 fits the single point exactly",
        passed,
        failed,
    )

    print("  [linear_models] Passed:", passed, "Failed:", failed)
