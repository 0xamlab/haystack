"""test_seq_nn.mojo — known-value + numerical-gradient tests for seq_nn.

Forward known values were hand-computed independently (sigmoid/tanh chain on
small hand-set weights). Gradient checks compare the analytic backward against
central finite differences on a tiny cell (input 3, hidden 2): max relative
error < 1e-4 required for EVERY parameter, input, and prior state.
"""
from std.math import abs as fabs, sqrt
from seq_nn import (
    LSTMState,
    LSTMGrads,
    GRUState,
    GRUGrads,
    RNNParams,
    lstm_cell_forward,
    lstm_cell_backward,
    gru_cell_forward,
    gru_cell_backward,
    lstm_param_count,
    gru_param_count,
    xavier_flat,
    init_lstm_params,
    init_gru_params,
)


fn check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ seq_nn::" + name)
    else:
        failed += 1
        print("  ❌ seq_nn::" + name)


fn _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    return fabs(a - b) <= tol


fn _max_rel_err(analytic: List[Float64], numeric: List[Float64]) -> Float64:
    """Max elementwise relative error with a small absolute floor."""
    if len(analytic) != len(numeric):
        return 1.0e9
    var m: Float64 = 0.0
    for i in range(len(analytic)):
        var denom = fabs(analytic[i])
        if fabs(numeric[i]) > denom:
            denom = fabs(numeric[i])
        if denom < 1.0e-6:
            denom = 1.0e-6
        var e = fabs(analytic[i] - numeric[i]) / denom
        if e > m:
            m = e
    return m


fn _lstm_loss(
    x: List[Float64],
    h_prev: List[Float64],
    c_prev: List[Float64],
    W: List[Float64],
    U: List[Float64],
    b: List[Float64],
    alpha: List[Float64],
    beta: List[Float64],
    hidden: Int,
) -> Float64:
    """Scalar probe loss L = sum_k alpha_k*h_k + beta_k*c_k after one step."""
    var st = lstm_cell_forward(x, h_prev, c_prev, W, U, b, hidden)
    var loss: Float64 = 0.0
    for k in range(hidden):
        loss += alpha[k] * st.h[k] + beta[k] * st.c[k]
    return loss


fn _gru_loss(
    x: List[Float64],
    h_prev: List[Float64],
    W: List[Float64],
    U: List[Float64],
    b: List[Float64],
    alpha: List[Float64],
    hidden: Int,
) -> Float64:
    """Scalar probe loss L = sum_k alpha_k*h_k after one step."""
    var st = gru_cell_forward(x, h_prev, W, U, b, hidden)
    var loss: Float64 = 0.0
    for k in range(hidden):
        loss += alpha[k] * st.h[k]
    return loss


def main() raises:
    var passed: Int = 0
    var failed: Int = 0
    var tol: Float64 = 1.0e-12
    var gtol: Float64 = 1.0e-4
    var eps: Float64 = 1.0e-5

    # ═══ LSTM forward: known value, input=2 hidden=1, hand-set weights ═══
    # x=[1,-0.5] h_prev=[0.25] c_prev=[0.5]
    # W(i,f,g,o)=[[.1,.2],[.3,-.1],[.5,.4],[-.2,.3]] U=[.1,-.3,.2,.4]
    # b=[.05,.1,-.05,.2]
    # preacts: i=0.075 f=0.375 g=0.3 o=-0.05
    # i=0.5187412158785352 f=0.5926665999540697 g=0.2913126124515909
    # o=0.4875026035157896 c=0.4474491587609256 h=0.20465357159216882
    var x1 = List[Float64]()
    x1.append(1.0)
    x1.append(-0.5)
    var hp1 = List[Float64]()
    hp1.append(0.25)
    var cp1 = List[Float64]()
    cp1.append(0.5)
    var W1 = List[Float64]()
    W1.append(0.1)
    W1.append(0.2)
    W1.append(0.3)
    W1.append(-0.1)
    W1.append(0.5)
    W1.append(0.4)
    W1.append(-0.2)
    W1.append(0.3)
    var U1 = List[Float64]()
    U1.append(0.1)
    U1.append(-0.3)
    U1.append(0.2)
    U1.append(0.4)
    var b1 = List[Float64]()
    b1.append(0.05)
    b1.append(0.1)
    b1.append(-0.05)
    b1.append(0.2)
    var st1 = lstm_cell_forward(x1, hp1, cp1, W1, U1, b1, 1)
    check(
        len(st1.h) == 1
        and _close(st1.h[0], 0.20465357159216882, tol)
        and _close(st1.c[0], 0.4474491587609256, tol),
        "lstm_cell_forward known-value h,c",
        passed,
        failed,
    )
    check(
        _close(st1.i_gate[0], 0.5187412158785352, tol)
        and _close(st1.f_gate[0], 0.5926665999540697, tol)
        and _close(st1.g_gate[0], 0.2913126124515909, tol)
        and _close(st1.o_gate[0], 0.4875026035157896, tol),
        "lstm_cell_forward known-value gates i,f,g,o",
        passed,
        failed,
    )

    # ═══ LSTM forward: all-zero weights/bias (edge: neutral gates) ═══
    # i=f=o=0.5, g=0, c_prev=1 -> c=0.5, h=0.5*tanh(0.5)=0.23105857863000487
    var Wz = List[Float64]()
    var Uz = List[Float64]()
    var bz = List[Float64]()
    for _ in range(4):
        Wz.append(0.0)
        Uz.append(0.0)
        bz.append(0.0)
    var xz = List[Float64]()
    xz.append(0.7)
    var hz = List[Float64]()
    hz.append(-0.4)
    var cz = List[Float64]()
    cz.append(1.0)
    var stz = lstm_cell_forward(xz, hz, cz, Wz, Uz, bz, 1)
    check(
        _close(stz.c[0], 0.5, tol)
        and _close(stz.h[0], 0.23105857863000487, tol),
        "lstm_cell_forward zero-weight neutral gates",
        passed,
        failed,
    )

    # ═══ LSTM edge cases: hidden=0 and inconsistent sizes -> empty ═══
    var st_bad0 = lstm_cell_forward(x1, hp1, cp1, W1, U1, b1, 0)
    var Wshort = List[Float64]()
    Wshort.append(0.1)
    var st_bad1 = lstm_cell_forward(x1, hp1, cp1, Wshort, U1, b1, 1)
    check(
        len(st_bad0.h) == 0 and len(st_bad1.h) == 0,
        "lstm_cell_forward invalid config -> empty state",
        passed,
        failed,
    )
    var dh_bad = List[Float64]()  # wrong length (0) for hidden=1
    var g_bad = lstm_cell_backward(dh_bad, dh_bad, st1, x1, hp1, cp1, W1, U1, 1)
    check(
        len(g_bad.dx) == 0 and len(g_bad.dW) == 0,
        "lstm_cell_backward invalid config -> empty grads",
        passed,
        failed,
    )

    # ═══ LSTM gradient check: input=3, hidden=2, seeded xavier params ═══
    var p = init_lstm_params(3, 2, 42)
    var x = List[Float64]()
    x.append(0.5)
    x.append(-0.3)
    x.append(0.8)
    var hp = List[Float64]()
    hp.append(0.1)
    hp.append(-0.2)
    var cp = List[Float64]()
    cp.append(0.3)
    cp.append(0.05)
    var alpha = List[Float64]()
    alpha.append(1.0)
    alpha.append(-0.7)
    var beta = List[Float64]()
    beta.append(0.4)
    beta.append(0.9)

    var cache = lstm_cell_forward(x, hp, cp, p.W, p.U, p.b, 2)
    var g = lstm_cell_backward(alpha, beta, cache, x, hp, cp, p.W, p.U, 2)
    check(
        len(g.dW) == 24 and len(g.dU) == 16 and len(g.db) == 8
        and len(g.dx) == 3 and len(g.dh_prev) == 2 and len(g.dc_prev) == 2,
        "lstm_cell_backward grad shapes",
        passed,
        failed,
    )

    # numeric dW
    var num_dW = List[Float64]()
    for idx in range(len(p.W)):
        var Wp = p.W.copy()
        Wp[idx] += eps
        var Wm = p.W.copy()
        Wm[idx] -= eps
        num_dW.append(
            (
                _lstm_loss(x, hp, cp, Wp, p.U, p.b, alpha, beta, 2)
                - _lstm_loss(x, hp, cp, Wm, p.U, p.b, alpha, beta, 2)
            )
            / (2.0 * eps)
        )
    check(
        _max_rel_err(g.dW, num_dW) < gtol,
        "lstm_cell_backward dW vs finite differences (24 params)",
        passed,
        failed,
    )

    # numeric dU
    var num_dU = List[Float64]()
    for idx in range(len(p.U)):
        var Up = p.U.copy()
        Up[idx] += eps
        var Um = p.U.copy()
        Um[idx] -= eps
        num_dU.append(
            (
                _lstm_loss(x, hp, cp, p.W, Up, p.b, alpha, beta, 2)
                - _lstm_loss(x, hp, cp, p.W, Um, p.b, alpha, beta, 2)
            )
            / (2.0 * eps)
        )
    check(
        _max_rel_err(g.dU, num_dU) < gtol,
        "lstm_cell_backward dU vs finite differences (16 params)",
        passed,
        failed,
    )

    # numeric db
    var num_db = List[Float64]()
    for idx in range(len(p.b)):
        var bp = p.b.copy()
        bp[idx] += eps
        var bm = p.b.copy()
        bm[idx] -= eps
        num_db.append(
            (
                _lstm_loss(x, hp, cp, p.W, p.U, bp, alpha, beta, 2)
                - _lstm_loss(x, hp, cp, p.W, p.U, bm, alpha, beta, 2)
            )
            / (2.0 * eps)
        )
    check(
        _max_rel_err(g.db, num_db) < gtol,
        "lstm_cell_backward db vs finite differences (8 params)",
        passed,
        failed,
    )

    # numeric dx
    var num_dx = List[Float64]()
    for idx in range(len(x)):
        var xp = x.copy()
        xp[idx] += eps
        var xm = x.copy()
        xm[idx] -= eps
        num_dx.append(
            (
                _lstm_loss(xp, hp, cp, p.W, p.U, p.b, alpha, beta, 2)
                - _lstm_loss(xm, hp, cp, p.W, p.U, p.b, alpha, beta, 2)
            )
            / (2.0 * eps)
        )
    check(
        _max_rel_err(g.dx, num_dx) < gtol,
        "lstm_cell_backward dx vs finite differences",
        passed,
        failed,
    )

    # numeric dh_prev
    var num_dhp = List[Float64]()
    for idx in range(len(hp)):
        var hpp = hp.copy()
        hpp[idx] += eps
        var hpm = hp.copy()
        hpm[idx] -= eps
        num_dhp.append(
            (
                _lstm_loss(x, hpp, cp, p.W, p.U, p.b, alpha, beta, 2)
                - _lstm_loss(x, hpm, cp, p.W, p.U, p.b, alpha, beta, 2)
            )
            / (2.0 * eps)
        )
    check(
        _max_rel_err(g.dh_prev, num_dhp) < gtol,
        "lstm_cell_backward dh_prev vs finite differences",
        passed,
        failed,
    )

    # numeric dc_prev
    var num_dcp = List[Float64]()
    for idx in range(len(cp)):
        var cpp = cp.copy()
        cpp[idx] += eps
        var cpm = cp.copy()
        cpm[idx] -= eps
        num_dcp.append(
            (
                _lstm_loss(x, hp, cpp, p.W, p.U, p.b, alpha, beta, 2)
                - _lstm_loss(x, hp, cpm, p.W, p.U, p.b, alpha, beta, 2)
            )
            / (2.0 * eps)
        )
    check(
        _max_rel_err(g.dc_prev, num_dcp) < gtol,
        "lstm_cell_backward dc_prev vs finite differences",
        passed,
        failed,
    )

    # ═══ GRU forward: known value, input=2 hidden=1, hand-set weights ═══
    # x=[0.5,-1] h_prev=[0.4]
    # W(r,z,n)=[[.2,.1],[-.3,.4],[.25,-.5]] U=[.3,-.2,.15] b=[.1,-.05,.2]
    # preacts: r=0.22 z=-0.68  s=r*0.4  n_pre=0.825+0.15*s
    # r=0.5547792351072148 z=0.3362613025956473 s=0.22191169404288594
    # n=0.6953739117984645 h=0.596051095464341
    var gx = List[Float64]()
    gx.append(0.5)
    gx.append(-1.0)
    var ghp = List[Float64]()
    ghp.append(0.4)
    var GW = List[Float64]()
    GW.append(0.2)
    GW.append(0.1)
    GW.append(-0.3)
    GW.append(0.4)
    GW.append(0.25)
    GW.append(-0.5)
    var GU = List[Float64]()
    GU.append(0.3)
    GU.append(-0.2)
    GU.append(0.15)
    var Gb = List[Float64]()
    Gb.append(0.1)
    Gb.append(-0.05)
    Gb.append(0.2)
    var gst = gru_cell_forward(gx, ghp, GW, GU, Gb, 1)
    check(
        len(gst.h) == 1 and _close(gst.h[0], 0.596051095464341, tol),
        "gru_cell_forward known-value h",
        passed,
        failed,
    )
    check(
        _close(gst.r_gate[0], 0.5547792351072148, tol)
        and _close(gst.z_gate[0], 0.3362613025956473, tol)
        and _close(gst.s_reset[0], 0.22191169404288594, tol)
        and _close(gst.n_cand[0], 0.6953739117984645, tol),
        "gru_cell_forward known-value gates r,z,s,n",
        passed,
        failed,
    )

    # ═══ GRU forward: all-zero weights (edge) -> h = 0.5*h_prev ═══
    # r=z=0.5, n=tanh(0)=0, h = 0.5*0.8 + 0.5*0 = 0.4
    var GWz = List[Float64]()
    var GUz = List[Float64]()
    var Gbz = List[Float64]()
    for _ in range(3):
        GWz.append(0.0)
        GUz.append(0.0)
        Gbz.append(0.0)
    var gxz = List[Float64]()
    gxz.append(0.3)
    var ghz = List[Float64]()
    ghz.append(0.8)
    var gstz = gru_cell_forward(gxz, ghz, GWz, GUz, Gbz, 1)
    check(
        _close(gstz.h[0], 0.4, tol),
        "gru_cell_forward zero-weight halves h_prev",
        passed,
        failed,
    )

    # ═══ GRU edge cases: hidden=0 and inconsistent sizes -> empty ═══
    var gbad0 = gru_cell_forward(gx, ghp, GW, GU, Gb, 0)
    var gbad1 = gru_cell_forward(gx, ghp, Wshort, GU, Gb, 1)
    check(
        len(gbad0.h) == 0 and len(gbad1.h) == 0,
        "gru_cell_forward invalid config -> empty state",
        passed,
        failed,
    )
    var ggbad = gru_cell_backward(dh_bad, gst, gx, ghp, GW, GU, 1)
    check(
        len(ggbad.dx) == 0 and len(ggbad.dW) == 0,
        "gru_cell_backward invalid config -> empty grads",
        passed,
        failed,
    )

    # ═══ GRU gradient check: input=3, hidden=2, seeded xavier params ═══
    var q = init_gru_params(3, 2, 7)
    var gcache = gru_cell_forward(x, hp, q.W, q.U, q.b, 2)
    var gg = gru_cell_backward(alpha, gcache, x, hp, q.W, q.U, 2)
    check(
        len(gg.dW) == 18 and len(gg.dU) == 12 and len(gg.db) == 6
        and len(gg.dx) == 3 and len(gg.dh_prev) == 2,
        "gru_cell_backward grad shapes",
        passed,
        failed,
    )

    var gnum_dW = List[Float64]()
    for idx in range(len(q.W)):
        var Wp = q.W.copy()
        Wp[idx] += eps
        var Wm = q.W.copy()
        Wm[idx] -= eps
        gnum_dW.append(
            (
                _gru_loss(x, hp, Wp, q.U, q.b, alpha, 2)
                - _gru_loss(x, hp, Wm, q.U, q.b, alpha, 2)
            )
            / (2.0 * eps)
        )
    check(
        _max_rel_err(gg.dW, gnum_dW) < gtol,
        "gru_cell_backward dW vs finite differences (18 params)",
        passed,
        failed,
    )

    var gnum_dU = List[Float64]()
    for idx in range(len(q.U)):
        var Up = q.U.copy()
        Up[idx] += eps
        var Um = q.U.copy()
        Um[idx] -= eps
        gnum_dU.append(
            (
                _gru_loss(x, hp, q.W, Up, q.b, alpha, 2)
                - _gru_loss(x, hp, q.W, Um, q.b, alpha, 2)
            )
            / (2.0 * eps)
        )
    check(
        _max_rel_err(gg.dU, gnum_dU) < gtol,
        "gru_cell_backward dU vs finite differences (12 params)",
        passed,
        failed,
    )

    var gnum_db = List[Float64]()
    for idx in range(len(q.b)):
        var bp = q.b.copy()
        bp[idx] += eps
        var bm = q.b.copy()
        bm[idx] -= eps
        gnum_db.append(
            (
                _gru_loss(x, hp, q.W, q.U, bp, alpha, 2)
                - _gru_loss(x, hp, q.W, q.U, bm, alpha, 2)
            )
            / (2.0 * eps)
        )
    check(
        _max_rel_err(gg.db, gnum_db) < gtol,
        "gru_cell_backward db vs finite differences (6 params)",
        passed,
        failed,
    )

    var gnum_dx = List[Float64]()
    for idx in range(len(x)):
        var xp = x.copy()
        xp[idx] += eps
        var xm = x.copy()
        xm[idx] -= eps
        gnum_dx.append(
            (
                _gru_loss(xp, hp, q.W, q.U, q.b, alpha, 2)
                - _gru_loss(xm, hp, q.W, q.U, q.b, alpha, 2)
            )
            / (2.0 * eps)
        )
    check(
        _max_rel_err(gg.dx, gnum_dx) < gtol,
        "gru_cell_backward dx vs finite differences",
        passed,
        failed,
    )

    var gnum_dhp = List[Float64]()
    for idx in range(len(hp)):
        var hpp = hp.copy()
        hpp[idx] += eps
        var hpm = hp.copy()
        hpm[idx] -= eps
        gnum_dhp.append(
            (
                _gru_loss(x, hpp, q.W, q.U, q.b, alpha, 2)
                - _gru_loss(x, hpm, q.W, q.U, q.b, alpha, 2)
            )
            / (2.0 * eps)
        )
    check(
        _max_rel_err(gg.dh_prev, gnum_dhp) < gtol,
        "gru_cell_backward dh_prev vs finite differences",
        passed,
        failed,
    )

    # ═══ param counts ═══
    check(
        lstm_param_count(3, 2) == 48
        and gru_param_count(3, 2) == 36
        and lstm_param_count(1, 1) == 12
        and gru_param_count(1, 1) == 9,
        "param counts 4h(i+h+1) / 3h(i+h+1)",
        passed,
        failed,
    )
    check(
        lstm_param_count(3, 0) == 0
        and lstm_param_count(-1, 2) == 0
        and gru_param_count(3, 0) == 0,
        "param counts degenerate -> 0",
        passed,
        failed,
    )

    # ═══ init helpers: determinism, bounds, forget bias ═══
    var xa = xavier_flat(4, 3, 3, 2, 123)
    var xb = xavier_flat(4, 3, 3, 2, 123)
    var xc = xavier_flat(4, 3, 3, 2, 124)
    var same = len(xa) == 12 and len(xc) == 12
    for i in range(len(xa)):
        if xa[i] != xb[i]:
            same = False
    var differs = False
    for i in range(len(xa)):
        if xa[i] != xc[i]:
            differs = True
    check(
        same and differs,
        "xavier_flat seeded determinism (seed match + seed differ)",
        passed,
        failed,
    )
    var limit = sqrt(6.0 / 5.0)  # fan_in=3, fan_out=2
    var in_bounds = True
    var any_nonzero = False
    for i in range(len(xa)):
        if fabs(xa[i]) > limit:
            in_bounds = False
        if xa[i] != 0.0:
            any_nonzero = True
    check(
        in_bounds and any_nonzero,
        "xavier_flat values within ±sqrt(6/(fan_in+fan_out))",
        passed,
        failed,
    )
    check(
        len(xavier_flat(0, 3, 3, 2, 1)) == 0,
        "xavier_flat degenerate -> empty",
        passed,
        failed,
    )

    var pi = init_lstm_params(3, 2, 42)
    var pi2 = init_lstm_params(3, 2, 42)
    var det = len(pi.W) == 24 and len(pi.U) == 16 and len(pi.b) == 8
    for i in range(len(pi.W)):
        if pi.W[i] != pi2.W[i]:
            det = False
    for i in range(len(pi.U)):
        if pi.U[i] != pi2.U[i]:
            det = False
    check(det, "init_lstm_params shapes + determinism", passed, failed)
    var fbias_ok = True
    for k in range(8):
        var want: Float64 = 0.0
        if k >= 2 and k < 4:  # forget block rows [hidden, 2*hidden)
            want = 1.0
        if pi.b[k] != want:
            fbias_ok = False
    check(fbias_ok, "init_lstm_params forget-gate bias = 1, rest 0", passed, failed)

    var qi = init_gru_params(3, 2, 7)
    var gb_ok = len(qi.W) == 18 and len(qi.U) == 12 and len(qi.b) == 6
    for k in range(len(qi.b)):
        if qi.b[k] != 0.0:
            gb_ok = False
    check(gb_ok, "init_gru_params shapes + zero bias", passed, failed)

    print("  [seq_nn] Passed:", passed, "Failed:", failed)
