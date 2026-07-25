"""test_arima.mojo — known-value tests for arima."""
from arima import (
    ARFit,
    MAFit,
    ar_fit_yule_walker,
    durbin_levinson,
    ar_forecast,
    ma_fit_innovations,
    innovations_algorithm,
    arma_loglik_css,
    difference,
    undifference,
)

from std.math import abs as fabs


fn check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ arima::" + name)
    else:
        failed += 1
        print("  ❌ arima::" + name)


fn _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    return fabs(a - b) <= tol


fn _lists_close(a: List[Float64], b: List[Float64], tol: Float64) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if fabs(a[i] - b[i]) > tol:
            return False
    return True


# ── deterministic seeded RNG for synthetic series (test-local) ───────────────


fn _xorshift64(state: UInt64) -> UInt64:
    var s = state
    s ^= s << 13
    s ^= s >> 7
    s ^= s << 17
    return s


fn _rand_unit(mut state: UInt64) -> Float64:
    state = _xorshift64(state)
    return Float64(state >> 11) / 9007199254740992.0  # 2^53


fn _rand_normal(mut state: UInt64) -> Float64:
    """Irwin-Hall approximate N(0,1): sum of 12 uniforms minus 6."""
    var s: Float64 = 0.0
    for _ in range(12):
        s += _rand_unit(state)
    return s - 6.0


fn _gen_ar1(phi: Float64, n: Int, seed: UInt64) -> List[Float64]:
    """Seeded synthetic AR(1): x_t = phi*x_{t-1} + e_t, 200-sample burn-in."""
    var state = seed ^ UInt64(0x9E3779B97F4A7C15)
    state = _xorshift64(state)
    state = _xorshift64(state)
    var x: Float64 = 0.0
    for _ in range(200):
        x = phi * x + _rand_normal(state)
    var out = List[Float64](capacity=n)
    for _ in range(n):
        x = phi * x + _rand_normal(state)
        out.append(x)
    return out^


fn _gen_ma1(theta: Float64, n: Int, seed: UInt64) -> List[Float64]:
    """Seeded synthetic MA(1): x_t = e_t + theta*e_{t-1}."""
    var state = seed ^ UInt64(0x9E3779B97F4A7C15)
    state = _xorshift64(state)
    state = _xorshift64(state)
    var e_prev = _rand_normal(state)
    var out = List[Float64](capacity=n)
    for _ in range(n):
        var e = _rand_normal(state)
        out.append(e + theta * e_prev)
        e_prev = e
    return out^


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── durbin_levinson vs hand-solved Yule-Walker, p=2 ──────────────────────
    # gamma = [1, 0.5, 0.2]. YW: [1 .5; .5 1][phi1 phi2]' = [.5 .2]'
    #   det = 0.75; phi1 = 0.4/0.75 = 8/15; phi2 = -0.05/0.75 = -1/15
    #   sigma2 = 1 - phi1*0.5 - phi2*0.2 = 11.2/15 = 0.74666...
    # DL check: phi11=.5, v1=.75; phi22=(.2-.25)/.75=-1/15;
    #   phi21=.5-(-1/15)(.5)=8/15; v2=.75(1-1/225)=0.74666...
    var g = List[Float64]()
    g.append(1.0); g.append(0.5); g.append(0.2)
    var dl = durbin_levinson(g, 2)
    check(
        len(dl.phi) == 2
        and _close(dl.phi[0], 0.5333333333333333, 1e-12)
        and _close(dl.phi[1], -0.06666666666666667, 1e-12),
        "durbin_levinson p=2 matches hand-solved Yule-Walker phi",
        passed,
        failed,
    )
    check(
        _close(dl.sigma2, 0.7466666666666666, 1e-12),
        "durbin_levinson p=2 sigma2 = 11.2/15",
        passed,
        failed,
    )
    # p=1 on same ACF: phi = r(1) = 0.5, v1 = 0.75.
    var dl1 = durbin_levinson(g, 1)
    check(
        len(dl1.phi) == 1
        and _close(dl1.phi[0], 0.5, 1e-12)
        and _close(dl1.sigma2, 0.75, 1e-12),
        "durbin_levinson p=1 phi=r(1), v1=gamma0*(1-r1^2)",
        passed,
        failed,
    )

    # ── ar_fit_yule_walker on synthetic AR(1), phi=0.7, n=2000, seeded ──────
    var ar1 = _gen_ar1(0.7, 2000, 42)
    var fit1 = ar_fit_yule_walker(ar1, 1)
    check(
        len(fit1.phi) == 1 and _close(fit1.phi[0], 0.7, 0.05),
        "ar_fit_yule_walker AR(1) synthetic phi within 0.05 of 0.7",
        passed,
        failed,
    )
    check(
        _close(fit1.sigma2, 1.0, 0.15),
        "ar_fit_yule_walker AR(1) sigma2 near true noise variance 1",
        passed,
        failed,
    )
    # Overfit p=2 on the same AR(1): phi2 (the lag-2 PACF) should be ~0.
    var fit2 = ar_fit_yule_walker(ar1, 2)
    check(
        len(fit2.phi) == 2
        and _close(fit2.phi[0], 0.7, 0.08)
        and fabs(fit2.phi[1]) < 0.08,
        "ar_fit_yule_walker p=2 on AR(1): phi2 ~ 0",
        passed,
        failed,
    )
    # Determinism: same series, same fit.
    var fit1b = ar_fit_yule_walker(ar1, 1)
    check(
        fit1.phi[0] == fit1b.phi[0] and fit1.sigma2 == fit1b.sigma2,
        "ar_fit_yule_walker deterministic",
        passed,
        failed,
    )

    # ── ar_fit_yule_walker edge cases ────────────────────────────────────────
    var empty = List[Float64]()
    var fe = ar_fit_yule_walker(empty, 2)
    check(
        len(fe.phi) == 0 and fe.sigma2 == 0.0,
        "ar_fit_yule_walker empty series -> empty fit",
        passed,
        failed,
    )
    var one = List[Float64]()
    one.append(3.0)
    var f1 = ar_fit_yule_walker(one, 3)
    check(
        len(f1.phi) == 3
        and f1.phi[0] == 0.0 and f1.phi[1] == 0.0 and f1.phi[2] == 0.0
        and f1.sigma2 == 0.0,
        "ar_fit_yule_walker n=1 -> zero phi (padded to p), sigma2=0",
        passed,
        failed,
    )
    var flat = List[Float64]()
    for _ in range(50):
        flat.append(5.0)
    var ff = ar_fit_yule_walker(flat, 2)
    check(
        len(ff.phi) == 2
        and ff.phi[0] == 0.0 and ff.phi[1] == 0.0
        and ff.sigma2 == 0.0,
        "ar_fit_yule_walker all-equal series -> zeros, sigma2=0",
        passed,
        failed,
    )
    # Ties / short series with repeats should not blow up.
    var ties = List[Float64]()
    ties.append(1.0); ties.append(1.0); ties.append(2.0)
    ties.append(2.0); ties.append(1.0); ties.append(1.0)
    var ft = ar_fit_yule_walker(ties, 2)
    check(
        len(ft.phi) == 2 and ft.sigma2 >= 0.0
        and fabs(ft.phi[0]) < 10.0 and fabs(ft.phi[1]) < 10.0,
        "ar_fit_yule_walker ties -> finite fit, sigma2 >= 0",
        passed,
        failed,
    )

    # ── ar_forecast known values ─────────────────────────────────────────────
    # series [2,4,6], mean 4, phi=[0.5]: z_n = 2
    #   f1 = 4 + 0.5*2 = 5; f2 = 4 + 0.5*1 = 4.5; f3 = 4.25
    var s246 = List[Float64]()
    s246.append(2.0); s246.append(4.0); s246.append(6.0)
    var ph5 = List[Float64]()
    ph5.append(0.5)
    var fc = ar_forecast(s246, ph5, 3)
    var exp_fc = List[Float64]()
    exp_fc.append(5.0); exp_fc.append(4.5); exp_fc.append(4.25)
    check(
        _lists_close(fc, exp_fc, 1e-12),
        "ar_forecast AR(1) hand values 5, 4.5, 4.25",
        passed,
        failed,
    )
    # AR(2): series [1,2,3] mean 2, z=[-1,0,1], phi=[0.5,0.25]:
    #   f1 = 2 + .5*1 + .25*0 = 2.5; f2 = 2 + .5*.5 + .25*1 = 2.5
    #   f3 = 2 + .5*.5 + .25*.5 = 2.375
    var s123 = List[Float64]()
    s123.append(1.0); s123.append(2.0); s123.append(3.0)
    var ph2 = List[Float64]()
    ph2.append(0.5); ph2.append(0.25)
    var fc2 = ar_forecast(s123, ph2, 3)
    var exp_fc2 = List[Float64]()
    exp_fc2.append(2.5); exp_fc2.append(2.5); exp_fc2.append(2.375)
    check(
        _lists_close(fc2, exp_fc2, 1e-12),
        "ar_forecast AR(2) hand values 2.5, 2.5, 2.375",
        passed,
        failed,
    )
    # Empty phi -> forecasts collapse to the sample mean; steps=0 / empty in.
    var fc_mean = ar_forecast(s246, empty, 2)
    check(
        len(fc_mean) == 2 and fc_mean[0] == 4.0 and fc_mean[1] == 4.0,
        "ar_forecast p=0 -> sample mean",
        passed,
        failed,
    )
    check(
        len(ar_forecast(s246, ph5, 0)) == 0
        and len(ar_forecast(empty, ph5, 3)) == 0,
        "ar_forecast steps=0 / empty series -> empty",
        passed,
        failed,
    )

    # ── innovations_algorithm hand recursion, MA(1) exact ACF ───────────────
    # theta=0.5, sigma2=1: gamma = [1.25, 0.5, 0, ...]
    #   v0=1.25; th11=.4, v1=1.05; th21=.5/1.05, v2=85/84*... hand:
    #   v2 = 1.25 - 0.25/1.05 = 1.0119047619...; th31 = 0.5/v2 = 42/85
    #   v3 = 1.25 - th31^2*v2 = 341/340 = 1.00294117647...
    var gm = List[Float64]()
    gm.append(1.25); gm.append(0.5)
    var inn = innovations_algorithm(gm, 1, 3)
    check(
        len(inn.theta) == 1
        and _close(inn.theta[0], 0.49411764705882355, 1e-12),
        "innovations_algorithm M=3 theta1 = 42/85 (hand recursion)",
        passed,
        failed,
    )
    check(
        _close(inn.sigma2, 1.0029411764705882, 1e-12),
        "innovations_algorithm M=3 sigma2 = 341/340 (hand recursion)",
        passed,
        failed,
    )
    # q=2 on the same ACF: theta2 (lag-2, true value 0) stays exactly 0.
    var inn2 = innovations_algorithm(gm, 2, 3)
    check(
        len(inn2.theta) == 2
        and _close(inn2.theta[0], 0.49411764705882355, 1e-12)
        and inn2.theta[1] == 0.0,
        "innovations_algorithm q=2, gamma(2)=0 -> theta2 = 0",
        passed,
        failed,
    )
    # Convergence: more steps move theta1 toward the true 0.5.
    var inn30 = innovations_algorithm(gm, 1, 30)
    check(
        fabs(inn30.theta[0] - 0.5) < fabs(inn.theta[0] - 0.5)
        and _close(inn30.theta[0], 0.5, 1e-3)
        and _close(inn30.sigma2, 1.0, 1e-3),
        "innovations_algorithm M=30 converges to theta=0.5, sigma2=1",
        passed,
        failed,
    )

    # ── ma_fit_innovations on synthetic MA(1), theta=0.5, n=2000 ────────────
    var ma1 = _gen_ma1(0.5, 2000, 7)
    var mfit = ma_fit_innovations(ma1, 1, 30)
    check(
        len(mfit.theta) == 1 and _close(mfit.theta[0], 0.5, 0.08),
        "ma_fit_innovations MA(1) synthetic theta within 0.08 of 0.5",
        passed,
        failed,
    )
    check(
        _close(mfit.sigma2, 1.0, 0.15),
        "ma_fit_innovations MA(1) sigma2 near true noise variance 1",
        passed,
        failed,
    )
    # Edge cases: empty series, q=0, all-equal.
    var me = ma_fit_innovations(empty, 1, 10)
    var m0 = ma_fit_innovations(ma1, 0, 10)
    var mflat = ma_fit_innovations(flat, 1, 10)
    check(
        len(me.theta) == 0 and me.sigma2 == 0.0
        and len(m0.theta) == 0
        and len(mflat.theta) == 1 and mflat.theta[0] == 0.0
        and mflat.sigma2 == 0.0,
        "ma_fit_innovations edges: empty / q=0 / all-equal",
        passed,
        failed,
    )

    # ── arma_loglik_css hand values ──────────────────────────────────────────
    # series [1,2,1,0] (mean 1, z=[0,1,0,-1]), phi=[0.5], theta=[]:
    #   e = [1, -0.5, -1]; SSE = 2.25; sigma2 = 0.75; n_eff = 3
    #   ll = -1.5*(log(2pi) + log(0.75) + 1) = -3.825292490936347
    var s1210 = List[Float64]()
    s1210.append(1.0); s1210.append(2.0); s1210.append(1.0); s1210.append(0.0)
    var ll_ar = arma_loglik_css(s1210, ph5, empty)
    check(
        _close(ll_ar, -3.825292490936347, 1e-9),
        "arma_loglik_css AR(1) hand value -3.8252924909",
        passed,
        failed,
    )
    # phi=[0.5], theta=[0.25]: e = [1, -0.75, -0.8125]; SSE = 2.22265625
    #   sigma2 = 0.7408854166...; ll = -3.806951651082006
    var th25 = List[Float64]()
    th25.append(0.25)
    var ll_arma = arma_loglik_css(s1210, ph5, th25)
    check(
        _close(ll_arma, -3.806951651082006, 1e-9),
        "arma_loglik_css ARMA(1,1) hand value -3.8069516511",
        passed,
        failed,
    )
    # On the synthetic AR(1), the true phi must beat white noise (phi=0).
    var ph0 = List[Float64]()
    ph0.append(0.0)
    var ph7 = List[Float64]()
    ph7.append(0.7)
    check(
        arma_loglik_css(ar1, ph7, empty) > arma_loglik_css(ar1, ph0, empty),
        "arma_loglik_css phi=0.7 beats phi=0 on AR(1) data",
        passed,
        failed,
    )
    # Infeasible: n_eff <= 0 -> 0.0. All-equal series stays finite.
    check(
        arma_loglik_css(one, ph2, empty) == 0.0
        and arma_loglik_css(empty, empty, empty) == 0.0,
        "arma_loglik_css n_eff<=0 -> 0.0",
        passed,
        failed,
    )
    var ll_flat = arma_loglik_css(flat, ph5, empty)
    check(
        ll_flat == ll_flat and ll_flat > -1.0e9,
        "arma_loglik_css all-equal (SSE=0) stays finite",
        passed,
        failed,
    )

    # ── difference known values ──────────────────────────────────────────────
    # x = [1,4,9,16]: d1 = [3,5,7]; d2 = [2,2]
    var sq = List[Float64]()
    sq.append(1.0); sq.append(4.0); sq.append(9.0); sq.append(16.0)
    var d1 = difference(sq, 1)
    var d2 = difference(sq, 2)
    var exp_d1 = List[Float64]()
    exp_d1.append(3.0); exp_d1.append(5.0); exp_d1.append(7.0)
    var exp_d2 = List[Float64]()
    exp_d2.append(2.0); exp_d2.append(2.0)
    check(
        _lists_close(d1, exp_d1, 0.0) and _lists_close(d2, exp_d2, 0.0),
        "difference d=1 [3,5,7], d=2 [2,2] exact",
        passed,
        failed,
    )
    check(
        len(difference(empty, 1)) == 0
        and len(difference(sq, 4)) == 0
        and len(difference(sq, 9)) == 0
        and _lists_close(difference(sq, 0), sq, 0.0),
        "difference edges: empty / order>=n -> empty / order 0 -> copy",
        passed,
        failed,
    )

    # ── difference/undifference round-trip exact ─────────────────────────────
    # Integer-valued floats -> all intermediate sums exact in IEEE754.
    var x = List[Float64]()
    x.append(3.0); x.append(1.0); x.append(4.0); x.append(1.0)
    x.append(5.0); x.append(9.0); x.append(2.0); x.append(6.0)
    var init1 = List[Float64]()
    init1.append(x[0])
    var rt1 = undifference(difference(x, 1), init1)
    check(
        _lists_close(rt1, x, 0.0),
        "undifference(difference(x,1), x[0:1]) == x exact",
        passed,
        failed,
    )
    var init2 = List[Float64]()
    init2.append(x[0]); init2.append(x[1])
    var rt2 = undifference(difference(x, 2), init2)
    check(
        _lists_close(rt2, x, 0.0),
        "undifference(difference(x,2), x[0:2]) == x exact",
        passed,
        failed,
    )
    var init3 = List[Float64]()
    init3.append(x[0]); init3.append(x[1]); init3.append(x[2])
    var rt3 = undifference(difference(x, 3), init3)
    check(
        _lists_close(rt3, x, 0.0),
        "undifference(difference(x,3), x[0:3]) == x exact",
        passed,
        failed,
    )
    # d=0 (empty initial) is identity; undifference of empty diffed returns
    # just the reconstructed heads (== initial).
    var rt0 = undifference(d1, empty)
    check(
        _lists_close(rt0, d1, 0.0),
        "undifference d=0 -> unchanged",
        passed,
        failed,
    )
    var only_heads = undifference(empty, init2)
    check(
        _lists_close(only_heads, init2, 0.0),
        "undifference(empty, x[0:2]) == x[0:2]",
        passed,
        failed,
    )

    print("  [arima] Passed:", passed, "Failed:", failed)
