"""test_seq_training.mojo — known-value tests for seq_training.

LSTM forward reference values (cases A/B/C) were computed with an
independent scalar Python implementation of the same equations.
"""
from seq_training import (
    WindowedDataset,
    TrainResult,
    make_windows,
    lstm_weight_count,
    bptt_train_lstm,
    lstm_predict,
)
from std.math import sqrt, sin, abs as fabs


fn check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ seq_training::" + name)
    else:
        failed += 1
        print("  ❌ seq_training::" + name)


fn _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    return fabs(a - b) <= tol


fn _is_finite(x: Float64) -> Bool:
    return x == x and fabs(x) < 1e300


fn _mse_loss(
    weights: List[Float64], ds: WindowedDataset, input_dim: Int, hidden: Int
) -> Float64:
    """MSE over the dataset via the public lstm_predict — independent of the
    training loop's internal loss computation."""
    var total = 0.0
    for i in range(ds.n_windows):
        var win = List[Float64](capacity=ds.window_len)
        for j in range(ds.window_len):
            win.append(ds.x[i * ds.window_len + j])
        var e = lstm_predict(weights, win, input_dim, hidden) - ds.y[i]
        total += e * e
    return total / Float64(ds.n_windows)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── make_windows: exact hand values ──────────────────────────────────────
    # series [1..6], lb=3, fw=1 -> 3 windows: [1,2,3]->4, [2,3,4]->5, [3,4,5]->6
    var s6 = List[Float64]()
    for i in range(6):
        s6.append(Float64(i + 1))
    var ds = make_windows(s6, 3, 1)
    check(
        ds.n_windows == 3 and ds.window_len == 3 and len(ds.x) == 9
        and len(ds.y) == 3,
        "make_windows shape 6/3/1",
        passed,
        failed,
    )
    check(
        ds.x[0] == 1.0 and ds.x[1] == 2.0 and ds.x[2] == 3.0
        and ds.x[3] == 2.0 and ds.x[4] == 3.0 and ds.x[5] == 4.0
        and ds.x[6] == 3.0 and ds.x[7] == 4.0 and ds.x[8] == 5.0,
        "make_windows window contents exact",
        passed,
        failed,
    )
    check(
        ds.y[0] == 4.0 and ds.y[1] == 5.0 and ds.y[2] == 6.0,
        "make_windows targets fw=1 exact",
        passed,
        failed,
    )

    # fw=2 -> 2 windows: [1,2,3]->5, [2,3,4]->6
    var ds2 = make_windows(s6, 3, 2)
    check(
        ds2.n_windows == 2 and ds2.y[0] == 5.0 and ds2.y[1] == 6.0,
        "make_windows targets fw=2 exact",
        passed,
        failed,
    )

    # exact fit: n = lb + fw -> exactly one window
    var ds3 = make_windows(s6, 5, 1)
    check(
        ds3.n_windows == 1 and ds3.window_len == 5 and ds3.y[0] == 6.0,
        "make_windows exact-fit single window",
        passed,
        failed,
    )

    # ── make_windows: edge cases -> empty ────────────────────────────────────
    var empty = List[Float64]()
    var one = List[Float64]()
    one.append(3.14)
    check(
        make_windows(empty, 3, 1).n_windows == 0
        and make_windows(one, 3, 1).n_windows == 0
        and make_windows(s6, 6, 1).n_windows == 0
        and make_windows(s6, 0, 1).n_windows == 0
        and make_windows(s6, 3, 0).n_windows == 0,
        "make_windows infeasible -> empty",
        passed,
        failed,
    )

    # ── lstm_weight_count: hand values ───────────────────────────────────────
    # D=1,H=1: 4*(1+1+1)+1+1 = 14; D=1,H=2: 4*(2+4+2)+2+1 = 35
    check(
        lstm_weight_count(1, 1) == 14 and lstm_weight_count(1, 2) == 35
        and lstm_weight_count(0, 4) == 0 and lstm_weight_count(2, 0) == 0,
        "lstm_weight_count hand values",
        passed,
        failed,
    )

    # ── lstm_predict: hand-computed known values (D=1, H=1) ──────────────────
    # Layout: [Wi_x,Wi_h,b_i, Wf_x,Wf_h,b_f, Wg_x,Wg_h,b_g, Wo_x,Wo_h,b_o, w_y, b_y]
    # Case A: all zero except b_y=0.7 -> candidate g=0 keeps c=h=0 -> y=0.7
    var wA = List[Float64]()
    for _ in range(14):
        wA.append(0.0)
    wA[13] = 0.7
    var winA = List[Float64]()
    winA.append(123.456)
    check(
        _close(lstm_predict(wA, winA, 1, 1), 0.7, 1e-12),
        "lstm_predict case A (zero gates -> b_y)",
        passed,
        failed,
    )

    # all-zero weights -> exactly 0.0
    wA[13] = 0.0
    check(
        lstm_predict(wA, winA, 1, 1) == 0.0,
        "lstm_predict all-zero weights -> 0",
        passed,
        failed,
    )

    # Case B: Wg_x=1, w_y=2, b_y=0.1
    #   x=[1.0]      -> 0.46339948438905243
    #   x=[1.0,0.5]  -> 0.49815726481608846   (reference: Python impl)
    var wB = List[Float64]()
    for _ in range(14):
        wB.append(0.0)
    wB[6] = 1.0
    wB[12] = 2.0
    wB[13] = 0.1
    var winB1 = List[Float64]()
    winB1.append(1.0)
    check(
        _close(lstm_predict(wB, winB1, 1, 1), 0.46339948438905243, 1e-12),
        "lstm_predict case B 1-step exact",
        passed,
        failed,
    )
    var winB2 = List[Float64]()
    winB2.append(1.0)
    winB2.append(0.5)
    check(
        _close(lstm_predict(wB, winB2, 1, 1), 0.49815726481608846, 1e-12),
        "lstm_predict case B 2-step exact",
        passed,
        failed,
    )

    # Case C: recurrent path exercised (Wi_h=0.3, b_f=1, Wg_x=1, Wg_h=0.5,
    # Wo_x=-0.2, w_y=1.5, b_y=-0.05), window [0.8,-0.4,0.6]
    #   -> 0.17925881009843325 (reference: Python impl)
    var wC = List[Float64]()
    for _ in range(14):
        wC.append(0.0)
    wC[1] = 0.3
    wC[5] = 1.0
    wC[6] = 1.0
    wC[7] = 0.5
    wC[9] = -0.2
    wC[12] = 1.5
    wC[13] = -0.05
    var winC = List[Float64]()
    winC.append(0.8)
    winC.append(-0.4)
    winC.append(0.6)
    check(
        _close(lstm_predict(wC, winC, 1, 1), 0.17925881009843325, 1e-12),
        "lstm_predict case C recurrent 3-step exact",
        passed,
        failed,
    )

    # ── lstm_predict: invalid inputs -> 0.0 ──────────────────────────────────
    var win_bad = List[Float64]()
    win_bad.append(1.0)
    win_bad.append(2.0)
    win_bad.append(3.0)
    check(
        lstm_predict(wB, empty, 1, 1) == 0.0
        and lstm_predict(empty, winB1, 1, 1) == 0.0
        and lstm_predict(wB, win_bad, 2, 1) == 0.0,
        "lstm_predict invalid shapes -> 0",
        passed,
        failed,
    )

    # ── bptt_train_lstm: epochs=0 returns seeded init, empty history ─────────
    var sinser = List[Float64]()
    for i in range(120):
        sinser.append(0.5 * sin(0.35 * Float64(i)))
    var sds = make_windows(sinser, 8, 1)
    check(sds.n_windows == 112, "make_windows sin series 112 windows", passed, failed)

    var init = bptt_train_lstm(sds.x, sds.y, 1, 8, 0, 0.02, 42, 5.0)
    check(
        len(init.weights) == lstm_weight_count(1, 8)
        and len(init.loss_history) == 0,
        "bptt_train_lstm epochs=0 -> init weights, empty history",
        passed,
        failed,
    )
    # documented layout: forget-gate biases (block 1 tail) initialised to 1.0
    var blk = 8 * 1 + 8 * 8 + 8
    check(
        init.weights[blk + 8 * 1 + 8 * 8] == 1.0
        and init.weights[blk + 8 * 1 + 8 * 8 + 7] == 1.0,
        "bptt_train_lstm forget-gate bias init = 1.0",
        passed,
        failed,
    )

    # ── bptt_train_lstm: first Adam step direction matches finite-diff grad ──
    # First bias-corrected Adam step is -lr*sign(grad) per weight, so the
    # sign of (w0 - w1) must match a central finite-difference gradient of
    # the MSE computed independently through lstm_predict.
    var gds = make_windows(sinser, 4, 1)
    var w0r = bptt_train_lstm(gds.x, gds.y, 1, 2, 0, 0.01, 7, 0.0)
    var w1r = bptt_train_lstm(gds.x, gds.y, 1, 2, 1, 0.01, 7, 0.0)
    var nw = lstm_weight_count(1, 2)
    var grad_ok = len(w1r.weights) == nw
    var checked = 0
    if grad_ok:
        var h = 1e-5
        for j in range(nw):
            var wp = w0r.weights.copy()
            var wm = w0r.weights.copy()
            wp[j] += h
            wm[j] -= h
            var fd = (_mse_loss(wp, gds, 1, 2) - _mse_loss(wm, gds, 1, 2)) / (
                2.0 * h
            )
            if fabs(fd) < 1e-5:
                continue  # near-zero gradient: step direction unconstrained
            checked += 1
            var step = w0r.weights[j] - w1r.weights[j]  # = lr*sign(grad)
            if fd > 0.0 and step <= 0.0:
                grad_ok = False
            if fd < 0.0 and step >= 0.0:
                grad_ok = False
            if not _close(fabs(step), 0.01, 0.001):
                grad_ok = False  # |first Adam step| must be ~lr
    check(
        grad_ok and checked >= nw // 2,
        "bptt BPTT gradient signs match finite differences",
        passed,
        failed,
    )

    # ── bptt_train_lstm: determinism + seed sensitivity ──────────────────────
    var ta = bptt_train_lstm(gds.x, gds.y, 1, 2, 3, 0.01, 11, 1.0)
    var tb = bptt_train_lstm(gds.x, gds.y, 1, 2, 3, 0.01, 11, 1.0)
    var same = len(ta.weights) == len(tb.weights) and len(
        ta.loss_history
    ) == 3
    if same:
        for j in range(len(ta.weights)):
            if ta.weights[j] != tb.weights[j]:
                same = False
        for e in range(3):
            if ta.loss_history[e] != tb.loss_history[e]:
                same = False
    check(same, "bptt_train_lstm deterministic for same seed", passed, failed)

    var tc = bptt_train_lstm(gds.x, gds.y, 1, 2, 0, 0.01, 12, 1.0)
    var td = bptt_train_lstm(gds.x, gds.y, 1, 2, 0, 0.01, 11, 1.0)
    var diff = False
    for j in range(len(tc.weights)):
        if tc.weights[j] != td.weights[j]:
            diff = True
    check(diff, "bptt_train_lstm different seed -> different init", passed, failed)

    # ── bptt_train_lstm: invalid shapes -> empty result ──────────────────────
    var bad_y = List[Float64]()
    bad_y.append(1.0)
    bad_y.append(2.0)
    check(
        len(bptt_train_lstm(win_bad, bad_y, 1, 2, 5, 0.01, 1, 1.0).weights)
        == 0  # 3 floats not divisible into 2 windows
        and len(bptt_train_lstm(empty, empty, 1, 2, 5, 0.01, 1, 1.0).weights)
        == 0
        and len(bptt_train_lstm(win_bad, bad_y, 0, 2, 5, 0.01, 1, 1.0).weights)
        == 0,
        "bptt_train_lstm invalid shapes -> empty",
        passed,
        failed,
    )

    # ── CONVERGENCE (flagship): y = 0.5*sin windows, lb=8, fw=1 ──────────────
    var res = bptt_train_lstm(sds.x, sds.y, 1, 8, 200, 0.02, 42, 5.0)
    var ok_hist = len(res.loss_history) == 200
    if ok_hist:
        for e in range(200):
            if not _is_finite(res.loss_history[e]):
                ok_hist = False
    check(ok_hist, "convergence: 200 finite loss entries", passed, failed)

    var init_loss = res.loss_history[0]
    var final_loss = res.loss_history[len(res.loss_history) - 1]
    check(
        final_loss < 0.25 * init_loss,
        "convergence: final loss < 0.25 * initial ("
        + String(final_loss)
        + " vs "
        + String(init_loss)
        + ")",
        passed,
        failed,
    )

    # sign agreement between predictions and targets > 70%
    var agree = 0
    for i in range(sds.n_windows):
        var win = List[Float64](capacity=8)
        for j in range(8):
            win.append(sds.x[i * 8 + j])
        var p = lstm_predict(res.weights, win, 1, 8)
        if p * sds.y[i] > 0.0:
            agree += 1
    var frac = Float64(agree) / Float64(sds.n_windows)
    check(
        frac > 0.70,
        "convergence: sign agreement > 70% (got "
        + String(frac)
        + ")",
        passed,
        failed,
    )

    # training-loop loss agrees with independent lstm_predict-based MSE
    var res1 = bptt_train_lstm(sds.x, sds.y, 1, 8, 1, 0.02, 42, 5.0)
    check(
        _close(res1.loss_history[0], _mse_loss(init.weights, sds, 1, 8), 1e-9),
        "epoch-0 loss matches independent lstm_predict MSE",
        passed,
        failed,
    )

    # ── all-equal series: learns the constant ────────────────────────────────
    var flat = List[Float64]()
    for _ in range(24):
        flat.append(1.0)
    var fds = make_windows(flat, 4, 1)
    var fres = bptt_train_lstm(fds.x, fds.y, 1, 4, 80, 0.05, 3, 5.0)
    check(
        len(fres.loss_history) == 80
        and fres.loss_history[79] < 0.05
        and fres.loss_history[79] < 0.25 * fres.loss_history[0],
        "all-equal series: constant learned (loss -> ~0)",
        passed,
        failed,
    )

    # ── tiny clip_norm still trains stably (finite, non-increasing overall) ──
    var cres = bptt_train_lstm(sds.x, sds.y, 1, 4, 40, 0.02, 5, 0.01)
    var ok_clip = len(cres.loss_history) == 40
    if ok_clip:
        for e in range(40):
            if not _is_finite(cres.loss_history[e]):
                ok_clip = False
        if not (
            cres.loss_history[39] <= cres.loss_history[0] + 1e-12
        ):
            ok_clip = False
    check(ok_clip, "tiny clip_norm: finite + non-diverging", passed, failed)

    print("  [seq_training] Passed:", passed, "Failed:", failed)
