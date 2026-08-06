"""test_mixture_models.mojo — known-value tests for mixture_models."""
from mixture_models import (
    GMMResult,
    GMMResultND,
    gmm_fit,
    gmm_fit_nd,
    gmm_responsibilities,
    gmm_responsibilities_nd,
    gmm_bic,
)
from std.math import abs as fabs, log


def check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ mixture_models::" + name)
    else:
        failed += 1
        print("  ❌ mixture_models::" + name)


def _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    return fabs(a - b) <= tol


def _two_clusters_1d(n0: Int, n1: Int) -> List[Float64]:
    """Deterministic 1D data: n0 points near 0.0, n1 points near 10.0.

    Offsets cycle through {-0.4, -0.2, 0.0, +0.2, +0.4} so each cluster
    has mean ~center and spread ~0.28.
    """
    var x = List[Float64]()
    for i in range(n0):
        x.append(0.0 + Float64(i % 5) * 0.2 - 0.4)
    for i in range(n1):
        x.append(10.0 + Float64(i % 5) * 0.2 - 0.4)
    return x^


def _monotone_nondecreasing(t: List[Float64], slack: Float64) -> Bool:
    for i in range(1, len(t)):
        if t[i] < t[i - 1] - slack:
            return False
    return True


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── gmm_fit: two well-separated clusters (0 and 10), equal sizes ─────────
    var x = _two_clusters_1d(100, 100)
    var r = gmm_fit(x, 2, 200, 1e-8, 42)
    check(
        len(r.weights) == 2 and len(r.means) == 2 and len(r.vars) == 2,
        "gmm_fit k=2 shapes",
        passed,
        failed,
    )
    # Components sorted by mean ascending: means within 0.5 of 0 and 10.
    check(
        _close(r.means[0], 0.0, 0.5) and _close(r.means[1], 10.0, 0.5),
        "gmm_fit k=2 recovers means 0 and 10 within 0.5",
        passed,
        failed,
    )
    check(
        _close(r.weights[0], 0.5, 0.1) and _close(r.weights[1], 0.5, 0.1),
        "gmm_fit k=2 recovers weights 0.5/0.5 within 0.1",
        passed,
        failed,
    )
    var wsum: Float64 = 0.0
    for j in range(len(r.weights)):
        wsum += r.weights[j]
    check(_close(wsum, 1.0, 1e-9), "gmm_fit weights sum to 1", passed, failed)
    check(
        r.vars[0] > 0.0 and r.vars[1] > 0.0 and r.vars[0] < 1.0,
        "gmm_fit variances positive and tight",
        passed,
        failed,
    )
    # EM guarantee: log-likelihood monotone non-decreasing across iterations.
    check(
        len(r.loglik_trace) == r.iterations
        and _monotone_nondecreasing(r.loglik_trace, 1e-9),
        "gmm_fit loglik monotone non-decreasing",
        passed,
        failed,
    )
    check(r.converged, "gmm_fit k=2 converged", passed, failed)
    check(
        r.loglik == r.loglik_trace[len(r.loglik_trace) - 1],
        "gmm_fit loglik equals last trace entry",
        passed,
        failed,
    )

    # ── gmm_fit: unequal cluster sizes -> unequal weights ────────────────────
    var xu = _two_clusters_1d(150, 50)
    var ru = gmm_fit(xu, 2, 200, 1e-8, 7)
    check(
        _close(ru.weights[0], 0.75, 0.1) and _close(ru.weights[1], 0.25, 0.1)
        and _close(ru.means[0], 0.0, 0.5) and _close(ru.means[1], 10.0, 0.5),
        "gmm_fit unequal weights 0.75/0.25 within 0.1",
        passed,
        failed,
    )
    check(
        _monotone_nondecreasing(ru.loglik_trace, 1e-9),
        "gmm_fit unequal loglik monotone",
        passed,
        failed,
    )

    # ── gmm_fit: determinism for a fixed seed ────────────────────────────────
    var ra = gmm_fit(x, 2, 200, 1e-8, 42)
    check(
        ra.loglik == r.loglik and ra.iterations == r.iterations
        and ra.means[0] == r.means[0] and ra.means[1] == r.means[1],
        "gmm_fit deterministic for fixed seed",
        passed,
        failed,
    )

    # ── gmm_fit: k=1 gives exact MLE (hand-computed) ─────────────────────────
    # x = [1,2,3]: mean = 2, population var = 2/3, weight = 1.
    # loglik at (2, 2/3) = -1.5*ln(2*pi*2/3) - 1.5 = -3.6486179374517715.
    var x3 = List[Float64]()
    x3.append(1.0)
    x3.append(2.0)
    x3.append(3.0)
    var r1 = gmm_fit(x3, 1, 100, 1e-12, 0)
    check(
        len(r1.weights) == 1 and _close(r1.weights[0], 1.0, 1e-12)
        and _close(r1.means[0], 2.0, 1e-12)
        and _close(r1.vars[0], 2.0 / 3.0, 1e-12),
        "gmm_fit k=1 exact mean 2 var 2/3 weight 1",
        passed,
        failed,
    )
    check(
        _close(r1.loglik, -3.6486179374517715, 1e-9),
        "gmm_fit k=1 loglik hand-computed",
        passed,
        failed,
    )
    check(r1.converged, "gmm_fit k=1 converged", passed, failed)

    # ── gmm_fit: edge cases ──────────────────────────────────────────────────
    var empty = List[Float64]()
    var re = gmm_fit(empty, 2, 100, 1e-8, 1)
    check(
        len(re.weights) == 0 and not re.converged and re.iterations == 0,
        "gmm_fit empty x -> empty result",
        passed,
        failed,
    )
    var rk0 = gmm_fit(x3, 0, 100, 1e-8, 1)
    check(len(rk0.weights) == 0, "gmm_fit k=0 -> empty result", passed, failed)
    var rkn = gmm_fit(x3, 4, 100, 1e-8, 1)
    check(len(rkn.weights) == 0, "gmm_fit k>n -> empty result", passed, failed)

    # n=1, k=1: mean = point, variance hits the floor, weight 1.
    var x1 = List[Float64]()
    x1.append(3.5)
    var rn1 = gmm_fit(x1, 1, 50, 1e-10, 9)
    check(
        _close(rn1.means[0], 3.5, 1e-12) and _close(rn1.weights[0], 1.0, 1e-12)
        and rn1.vars[0] <= 1e-9 + 1e-18 and rn1.vars[0] > 0.0,
        "gmm_fit n=1 k=1 mean exact, var floored",
        passed,
        failed,
    )

    # All-equal data with k=2: no NaN/inf, both means at the value.
    var xeq = List[Float64]()
    for _ in range(8):
        xeq.append(5.0)
    var req = gmm_fit(xeq, 2, 100, 1e-10, 3)
    var weq: Float64 = 0.0
    for j in range(len(req.weights)):
        weq += req.weights[j]
    check(
        len(req.means) == 2
        and _close(req.means[0], 5.0, 1e-9) and _close(req.means[1], 5.0, 1e-9)
        and _close(weq, 1.0, 1e-9)
        and req.loglik == req.loglik,
        "gmm_fit all-equal data k=2 degenerate but finite",
        passed,
        failed,
    )

    # Ties: duplicated points across two clusters still recover centers.
    var xt = List[Float64]()
    for _ in range(20):
        xt.append(0.0)
    for _ in range(20):
        xt.append(10.0)
    var rt = gmm_fit(xt, 2, 100, 1e-10, 11)
    check(
        _close(rt.means[0], 0.0, 1e-6) and _close(rt.means[1], 10.0, 1e-6)
        and _close(rt.weights[0], 0.5, 1e-6),
        "gmm_fit ties two point masses exact centers",
        passed,
        failed,
    )

    # ── gmm_responsibilities: hand-computed values ───────────────────────────
    # Model: w=[0.5,0.5], means=[0,10], vars=[1,1].
    # x=5 is equidistant -> [0.5, 0.5] exactly.
    # x=4: log-odds = (-(4-0)^2 + (4-10)^2)/2 = 10 -> r0 = 1/(1+e^-10)
    #      = 0.9999546021312976.
    var w2 = List[Float64]()
    w2.append(0.5)
    w2.append(0.5)
    var m2 = List[Float64]()
    m2.append(0.0)
    m2.append(10.0)
    var v2 = List[Float64]()
    v2.append(1.0)
    v2.append(1.0)
    var pts = List[Float64]()
    pts.append(5.0)
    pts.append(4.0)
    var resp = gmm_responsibilities(pts, w2, m2, v2)
    check(len(resp) == 4, "gmm_responsibilities shape n*k", passed, failed)
    check(
        _close(resp[0], 0.5, 1e-12) and _close(resp[1], 0.5, 1e-12),
        "gmm_responsibilities midpoint -> 0.5/0.5 exact",
        passed,
        failed,
    )
    check(
        _close(resp[2], 0.9999546021312976, 1e-9)
        and _close(resp[2] + resp[3], 1.0, 1e-12),
        "gmm_responsibilities x=4 hand-computed 1/(1+e^-10)",
        passed,
        failed,
    )
    # Inconsistent lengths -> empty.
    var vbad = List[Float64]()
    vbad.append(1.0)
    var rbad = gmm_responsibilities(pts, w2, m2, vbad)
    check(
        len(rbad) == 0,
        "gmm_responsibilities inconsistent lengths -> empty",
        passed,
        failed,
    )

    # Fitted model separates the clusters nearly hard.
    var probe = List[Float64]()
    probe.append(0.0)
    probe.append(10.0)
    var rp = gmm_responsibilities(probe, r.weights, r.means, r.vars)
    check(
        rp[0] > 0.99 and rp[3] > 0.99,
        "gmm_responsibilities fitted model near-hard assignment",
        passed,
        failed,
    )

    # ── gmm_fit_nd: 2D clusters at (0,0) and (5,5) ───────────────────────────
    var X = List[Float64]()
    for i in range(50):
        X.append(0.0 + Float64(i % 5) * 0.1 - 0.2)
        X.append(0.0 + Float64(i % 7) * 0.1 - 0.3)
    for i in range(50):
        X.append(5.0 + Float64(i % 5) * 0.1 - 0.2)
        X.append(5.0 + Float64(i % 7) * 0.1 - 0.3)
    var rnd = gmm_fit_nd(X, 100, 2, 2, 200, 1e-8, 42)
    check(
        len(rnd.weights) == 2 and len(rnd.means) == 4 and len(rnd.vars) == 4
        and rnd.cols == 2,
        "gmm_fit_nd shapes k*cols",
        passed,
        failed,
    )
    check(
        _close(rnd.means[0], 0.0, 0.5) and _close(rnd.means[1], 0.0, 0.5)
        and _close(rnd.means[2], 5.0, 0.5) and _close(rnd.means[3], 5.0, 0.5),
        "gmm_fit_nd recovers (0,0) and (5,5) within 0.5",
        passed,
        failed,
    )
    check(
        _close(rnd.weights[0], 0.5, 0.1) and _close(rnd.weights[1], 0.5, 0.1),
        "gmm_fit_nd weights 0.5/0.5 within 0.1",
        passed,
        failed,
    )
    check(
        _monotone_nondecreasing(rnd.loglik_trace, 1e-9),
        "gmm_fit_nd loglik monotone non-decreasing",
        passed,
        failed,
    )
    check(
        rnd.vars[0] > 0.0 and rnd.vars[1] > 0.0
        and rnd.vars[2] > 0.0 and rnd.vars[3] > 0.0,
        "gmm_fit_nd variances positive",
        passed,
        failed,
    )
    var rbadlen = gmm_fit_nd(X, 100, 3, 2, 50, 1e-8, 1)
    check(
        len(rbadlen.weights) == 0,
        "gmm_fit_nd len(X) != rows*cols -> empty",
        passed,
        failed,
    )

    # gmm_responsibilities_nd: point equidistant from both 2D components.
    var mid = List[Float64]()
    mid.append(2.5)
    mid.append(2.5)
    var wnd = List[Float64]()
    wnd.append(0.5)
    wnd.append(0.5)
    var mnd = List[Float64]()
    mnd.append(0.0)
    mnd.append(0.0)
    mnd.append(5.0)
    mnd.append(5.0)
    var vnd = List[Float64]()
    for _ in range(4):
        vnd.append(1.0)
    var rmid = gmm_responsibilities_nd(mid, 1, 2, wnd, mnd, vnd)
    check(
        len(rmid) == 2 and _close(rmid[0], 0.5, 1e-12)
        and _close(rmid[1], 0.5, 1e-12),
        "gmm_responsibilities_nd 2D midpoint -> 0.5/0.5",
        passed,
        failed,
    )

    # ── gmm_bic: hand-computed ───────────────────────────────────────────────
    # (tolerance 1e-6: std.math.log carries ~1e-10 relative error)
    # k=2, dims=1: p = 5; BIC = 5*ln(100) - 2*(-100) = 223.02585092994047.
    check(
        _close(gmm_bic(-100.0, 100, 2, 1), 223.02585092994047, 1e-6),
        "gmm_bic 1D hand-computed",
        passed,
        failed,
    )
    # k=3, dims=2: p = 14; BIC = 14*ln(200) + 100 = 174.1764431316725.
    check(
        _close(gmm_bic(-50.0, 200, 3, 2), 174.1764431316725, 1e-6),
        "gmm_bic 2D hand-computed",
        passed,
        failed,
    )
    check(
        gmm_bic(-50.0, 0, 2, 1) == 0.0 and gmm_bic(-50.0, 10, 0, 1) == 0.0,
        "gmm_bic invalid args -> 0",
        passed,
        failed,
    )
    # Model selection: on the two-cluster data, k=2 must beat k=1 by BIC.
    var rone = gmm_fit(x, 1, 200, 1e-8, 42)
    var bic1 = gmm_bic(rone.loglik, len(x), 1, 1)
    var bic2 = gmm_bic(r.loglik, len(x), 2, 1)
    check(bic2 < bic1, "gmm_bic prefers k=2 on two clusters", passed, failed)

    print("  [mixture_models] Passed:", passed, "Failed:", failed)
