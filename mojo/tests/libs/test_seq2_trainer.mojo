"""test_seq2_trainer.mojo — correctness tests for the 2-layer LSTM trainer.

Covers: exact head wiring values, full-stack gradient check vs central
finite differences (f64), overfit-to-memorization, early stopping with
best-weight restore, export layout round-trip, and determinism (single
thread and fixed-worker-count parallel).
"""
from seq2_trainer import (
    Seq2Params,
    Seq2TrainResult,
    seq2_weight_count,
    seq2_init,
    seq2_forward,
    seq2_loss,
    seq2_grad,
    seq2_train,
    seq2_train_workers,
    seq2_train_scalar,
    seq2_export,
    seq2_from_flat,
)
from std.math import abs as fabs


def check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ seq2_trainer::" + name)
    else:
        failed += 1
        print("  ❌ seq2_trainer::" + name)


def _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    return fabs(a - b) <= tol


def _is_finite(x: Float64) -> Bool:
    return x == x and fabs(x) < 1e300


def _lcg(mut s: UInt64) -> Float64:
    """Deterministic uniform in [-1, 1) for test data."""
    s = s * UInt64(6364136223846793005) + UInt64(1442695040888963407)
    return Float64(s >> 11) * (1.0 / 9007199254740992.0) * 2.0 - 1.0


def _make_data(
    n: Int, T: Int, D: Int, seed: UInt64, mut x: List[Float64], mut y: List[Float64]
):
    """Random sequences with random (memorizable) targets in [-1, 1)."""
    var s = seed
    x = List[Float64](capacity=n * T * D)
    y = List[Float64](capacity=n)
    for _ in range(n * T * D):
        x.append(_lcg(s))
    for _ in range(n):
        y.append(_lcg(s))


def _same_params(a: Seq2Params, b: Seq2Params) -> Bool:
    var fa = seq2_export(a)
    var fb = seq2_export(b)
    if len(fa) == 0 or len(fa) != len(fb):
        return False
    for j in range(len(fa)):
        if fa[j] != fb[j]:
            return False
    return True


def main():
    var passed: Int = 0
    var failed: Int = 0
    var empty = List[Float64]()

    # ── seq2_weight_count: hand values ───────────────────────────────────────
    # D=2,H=3,Dh=2: 4H=12 rows; l1 = 12*2+12*3+12 = 72; l2 = 12*3+12*3+12 = 84;
    # dense = 2*3+2+2+1 = 11 -> 167.
    check(
        seq2_weight_count(2, 3, 2) == 167
        and seq2_weight_count(0, 3, 2) == 0
        and seq2_weight_count(2, 0, 2) == 0
        and seq2_weight_count(2, 3, 0) == 0,
        "weight_count hand value + invalid dims",
        passed,
        failed,
    )

    # ── seq2_init: shapes, forget-gate bias, determinism ─────────────────────
    var p0 = seq2_init(2, 3, 2, 42)
    check(
        p0.input_dim == 2
        and p0.hidden == 3
        and p0.dense_h == 2
        and len(p0.l1_wx) == 24
        and len(p0.l1_wh) == 36
        and len(p0.l1_b) == 12
        and len(p0.l2_wx) == 36
        and len(p0.l2_wh) == 36
        and len(p0.l2_b) == 12
        and len(p0.d1_w) == 6
        and len(p0.d1_b) == 2
        and len(p0.d2_w) == 2
        and len(p0.d2_b) == 1,
        "init block shapes",
        passed,
        failed,
    )
    var fg_ok = True
    for k in range(3, 6):  # forget-gate rows [H, 2H)
        if p0.l1_b[k] != 1.0 or p0.l2_b[k] != 1.0:
            fg_ok = False
    if p0.l1_b[0] != 0.0 or p0.l2_b[11] != 0.0 or p0.d1_b[0] != 0.0:
        fg_ok = False
    check(fg_ok, "init forget-gate bias = 1.0 in BOTH layers", passed, failed)
    check(
        _same_params(p0, seq2_init(2, 3, 2, 42))
        and not _same_params(p0, seq2_init(2, 3, 2, 43)),
        "init deterministic per seed, seed-sensitive",
        passed,
        failed,
    )
    check(
        seq2_init(0, 3, 2, 1).input_dim == 0 and len(seq2_init(2, -1, 2, 1).l1_wx) == 0,
        "init invalid dims -> empty params",
        passed,
        failed,
    )

    # ── head wiring: exact hand values ───────────────────────────────────────
    # All-zero weights: LSTM outputs 0, relu(0)=0, y = d2_b.
    var pz = seq2_from_flat(_mk_zeros(seq2_weight_count(2, 3, 2)), 2, 3, 2)
    var x1 = List[Float64](capacity=6)
    for i in range(6):
        x1.append(Float64(i) * 0.3 - 0.5)
    var pr = seq2_forward(pz, x1, 1, 3, 2)
    check(len(pr) == 1 and pr[0] == 0.0, "all-zero weights -> exactly 0", passed, failed)

    pz.d2_b[0] = 0.7
    pr = seq2_forward(pz, x1, 1, 3, 2)
    check(_close(pr[0], 0.7, 1e-15), "zero net + d2_b=0.7 -> 0.7", passed, failed)

    # d1_b = 1 (relu(1) = 1), d2_w = 2 each, d2_b = 0.1 -> y = 0.1 + 2*Dh = 4.1
    pz.d2_b[0] = 0.1
    for j in range(2):
        pz.d1_b[j] = 1.0
        pz.d2_w[j] = 2.0
    pr = seq2_forward(pz, x1, 1, 3, 2)
    check(_close(pr[0], 4.1, 1e-15), "dense-head wiring exact (0.1 + 2*Dh)", passed, failed)
    # relu kills negative hidden: d1_b = -1 -> y = d2_b
    for j in range(2):
        pz.d1_b[j] = -1.0
    pr = seq2_forward(pz, x1, 1, 3, 2)
    check(_close(pr[0], 0.1, 1e-15), "relu clamps negative dense hidden", passed, failed)

    # ── gradient check: full 2-layer stack vs central finite differences ─────
    var D = 2
    var H = 3
    var Dh = 2
    var T = 3
    var n = 4
    var gx = List[Float64]()
    var gy = List[Float64]()
    _make_data(n, T, D, 77, gx, gy)
    var gp = seq2_init(D, H, Dh, 42)
    var flat = seq2_export(gp)
    var grad = seq2_grad(gp, gx, gy, n, T, D)
    var n_w = seq2_weight_count(D, H, Dh)
    var grad_ok = len(grad) == n_w
    var worst = 0.0
    if grad_ok:
        var h = 1e-5
        for j in range(n_w):
            var fp = flat.copy()
            var fm = flat.copy()
            fp[j] += h
            fm[j] -= h
            var lp = seq2_loss(seq2_from_flat(fp, D, H, Dh), gx, gy, n, T, D)
            var lm = seq2_loss(seq2_from_flat(fm, D, H, Dh), gx, gy, n, T, D)
            var fd = (lp - lm) / (2.0 * h)
            var denom = fabs(fd)
            if denom < 1.0:
                denom = 1.0
            var rel = fabs(grad[j] - fd) / denom
            if rel > worst:
                worst = rel
        if worst > 1e-6:
            grad_ok = False
    check(
        grad_ok,
        "BPTT gradient matches finite differences (worst rel "
        + String(worst)
        + ")",
        passed,
        failed,
    )

    # loss consistency: seq2_loss == MSE recomputed from seq2_forward
    var preds = seq2_forward(gp, gx, n, T, D)
    var mse = 0.0
    for i in range(n):
        var e = preds[i] - gy[i]
        mse += e * e
    mse /= Float64(n)
    check(
        _close(seq2_loss(gp, gx, gy, n, T, D), mse, 1e-15),
        "seq2_loss matches MSE of seq2_forward",
        passed,
        failed,
    )

    # ── export layout round-trip ─────────────────────────────────────────────
    var rt = seq2_init(4, 5, 3, 9)
    var rt_flat = seq2_export(rt)
    check(
        len(rt_flat) == seq2_weight_count(4, 5, 3)
        and rt_flat[0] == rt.l1_wx[0]
        and rt_flat[4 * 5 * 4] == rt.l1_wh[0]  # l1_wh offset = 4H*D
        and rt_flat[len(rt_flat) - 1] == rt.d2_b[0],
        "export layout block offsets",
        passed,
        failed,
    )
    var rt2 = seq2_from_flat(rt_flat, 4, 5, 3)
    var rx = List[Float64]()
    var ry = List[Float64]()
    _make_data(6, 7, 4, 123, rx, ry)
    var pa = seq2_forward(rt, rx, 6, 7, 4)
    var pb = seq2_forward(rt2, rx, 6, 7, 4)
    var rt_ok = len(pa) == 6 and len(pb) == 6 and _same_params(rt, rt2)
    if rt_ok:
        for i in range(6):
            if pa[i] != pb[i]:
                rt_ok = False
    check(rt_ok, "export -> from_flat -> forward matches exactly", passed, failed)
    check(
        len(seq2_from_flat(rx, 4, 5, 3).l1_wx) == 0
        and seq2_from_flat(rt_flat, 5, 5, 3).input_dim == 0,
        "from_flat wrong length -> empty params",
        passed,
        failed,
    )

    # ── overfit: loss -> ~0 on 32 memorizable sequences ──────────────────────
    var ox = List[Float64]()
    var oy = List[Float64]()
    _make_data(32, 6, 3, 999, ox, oy)
    var op = seq2_init(3, 10, 8, 5)
    var ores = seq2_train_workers(
        op, ox, oy, 32, 6, 3, empty, empty, 0, 400, 8, 0.02, 0.0, 0, 11, 1
    )
    var o_hist_ok = len(ores.train_loss) == 400 and ores.epochs_run == 400
    if o_hist_ok:
        for e in range(400):
            if not _is_finite(ores.train_loss[e]):
                o_hist_ok = False
    check(o_hist_ok, "overfit: 400 finite loss entries", passed, failed)
    var o_final = ores.train_loss[len(ores.train_loss) - 1]
    var o_init = ores.train_loss[0]
    check(
        o_final < 5e-3 and o_final < 0.02 * o_init,
        "overfit: memorizes 32 sequences (final "
        + String(o_final)
        + " vs initial "
        + String(o_init)
        + ")",
        passed,
        failed,
    )
    # returned params reproduce the memorization independently of the loop
    var o_loss = seq2_loss(ores.params, ox, oy, 32, 6, 3)
    check(o_loss < 5e-3, "overfit: returned params reproduce low loss", passed, failed)

    # ── early stopping: stops early and restores best-val weights ────────────
    var tx = List[Float64]()
    var ty = List[Float64]()
    _make_data(24, 5, 2, 314, tx, ty)
    var vx = List[Float64]()
    var vy = List[Float64]()
    _make_data(8, 5, 2, 2718, vx, vy)
    var ep = seq2_init(2, 8, 8, 21)
    var eres = seq2_train_workers(
        ep, tx, ty, 24, 5, 2, vx, vy, 8, 200, 8, 0.03, 0.0, 8, 4, 1
    )
    check(
        eres.epochs_run < 200 and len(eres.val_loss) == eres.epochs_run,
        "early stop: halted before max epochs (ran "
        + String(eres.epochs_run)
        + ")",
        passed,
        failed,
    )
    var best_is_min = eres.best_epoch >= 0 and eres.best_epoch < eres.epochs_run
    if best_is_min:
        var bv = eres.val_loss[eres.best_epoch]
        for e in range(len(eres.val_loss)):
            if eres.val_loss[e] < bv:
                best_is_min = False
    check(best_is_min, "early stop: best_epoch is the val-loss argmin", passed, failed)
    var restored = seq2_loss(eres.params, vx, vy, 8, 5, 2)
    check(
        eres.best_epoch >= 0
        and _close(restored, eres.val_loss[eres.best_epoch], 1e-12),
        "early stop: restored params reproduce best val loss exactly",
        passed,
        failed,
    )
    check(
        eres.best_epoch < eres.epochs_run - 1,
        "early stop: best epoch strictly before last (overfitting observed)",
        passed,
        failed,
    )

    # ── determinism ──────────────────────────────────────────────────────────
    var da = seq2_train_workers(
        ep, tx, ty, 24, 5, 2, vx, vy, 8, 6, 8, 0.02, 0.0, 0, 33, 1
    )
    var db = seq2_train_workers(
        ep, tx, ty, 24, 5, 2, vx, vy, 8, 6, 8, 0.02, 0.0, 0, 33, 1
    )
    var det = _same_params(da.params, db.params) and len(da.train_loss) == len(
        db.train_loss
    )
    if det:
        for e in range(len(da.train_loss)):
            if da.train_loss[e] != db.train_loss[e]:
                det = False
            if da.val_loss[e] != db.val_loss[e]:
                det = False
    check(det, "single-thread: identical runs for same seed", passed, failed)

    var pa4 = seq2_train_workers(
        ep, tx, ty, 24, 5, 2, vx, vy, 8, 6, 8, 0.02, 0.0, 0, 33, 4
    )
    var pb4 = seq2_train_workers(
        ep, tx, ty, 24, 5, 2, vx, vy, 8, 6, 8, 0.02, 0.0, 0, 33, 4
    )
    var det4 = _same_params(pa4.params, pb4.params)
    if det4:
        for e in range(len(pa4.train_loss)):
            if pa4.train_loss[e] != pb4.train_loss[e]:
                det4 = False
    check(
        det4,
        "parallel (4 workers): deterministic run-to-run (fixed-order reduction)",
        passed,
        failed,
    )
    # same per-sample gradients regardless of worker count: first-epoch train
    # loss can differ from the single-thread run only by summation order
    check(
        _close(pa4.train_loss[0], da.train_loss[0], 1e-9 * (1.0 + da.train_loss[0])),
        "parallel: epoch-0 loss matches single-thread up to summation order",
        passed,
        failed,
    )
    var dc = seq2_train_workers(
        ep, tx, ty, 24, 5, 2, vx, vy, 8, 6, 8, 0.02, 0.0, 0, 34, 1
    )
    check(
        not _same_params(da.params, dc.params),
        "different seed -> different trained weights",
        passed,
        failed,
    )

    # ── dropout: trains finitely and deterministically ───────────────────────
    var dra = seq2_train_workers(
        ep, tx, ty, 24, 5, 2, vx, vy, 8, 5, 8, 0.02, 0.3, 0, 55, 2
    )
    var drb = seq2_train_workers(
        ep, tx, ty, 24, 5, 2, vx, vy, 8, 5, 8, 0.02, 0.3, 0, 55, 2
    )
    var dr_ok = len(dra.train_loss) == 5 and _same_params(dra.params, drb.params)
    if dr_ok:
        for e in range(5):
            if not _is_finite(dra.train_loss[e]) or dra.train_loss[e] != drb.train_loss[e]:
                dr_ok = False
    check(dr_ok, "dropout=0.3: finite + deterministic (2 workers)", passed, failed)

    # ── scalar baseline: same loop, close trajectory ─────────────────────────
    var sres = seq2_train_scalar(
        ep, tx, ty, 24, 5, 2, vx, vy, 8, 3, 8, 0.02, 0.0, 0, 33
    )
    check(
        len(sres.train_loss) == 3
        and _close(sres.train_loss[0], da.train_loss[0], 1e-9 * (1.0 + da.train_loss[0])),
        "scalar build: epoch-0 loss matches SIMD build up to reduction order",
        passed,
        failed,
    )

    # ── seq2_train public API (auto workers) smoke ───────────────────────────
    var ares = seq2_train(ep, tx, ty, 24, 5, 2, vx, vy, 8, 4, 8, 0.02, 0.0, 0, 60)
    var a_ok = ares.epochs_run == 4 and len(ares.train_loss) == 4 and len(
        ares.val_loss
    ) == 4 and ares.params.hidden == 8
    if a_ok:
        for e in range(4):
            if not _is_finite(ares.train_loss[e]) or not _is_finite(ares.val_loss[e]):
                a_ok = False
    check(a_ok, "seq2_train (auto workers): runs, finite histories", passed, failed)

    # ── epochs <= 0: returns starting params, empty history ──────────────────
    var zres = seq2_train_workers(
        ep, tx, ty, 24, 5, 2, empty, empty, 0, 0, 8, 0.02, 0.0, 0, 1, 1
    )
    check(
        _same_params(zres.params, ep)
        and len(zres.train_loss) == 0
        and zres.epochs_run == 0,
        "epochs=0 -> input params, empty history",
        passed,
        failed,
    )

    # ── invalid inputs -> empty result ───────────────────────────────────────
    var bad_x = List[Float64]()
    bad_x.append(1.0)
    check(
        len(seq2_train_workers(ep, bad_x, ty, 24, 5, 2, empty, empty, 0, 3, 8, 0.02, 0.0, 0, 1, 1).train_loss) == 0
        and len(seq2_train_workers(ep, tx, bad_x, 24, 5, 2, empty, empty, 0, 3, 8, 0.02, 0.0, 0, 1, 1).train_loss) == 0
        and len(seq2_train_workers(ep, tx, ty, 24, 5, 2, empty, empty, 0, 3, 8, 0.02, 1.0, 0, 1, 1).train_loss) == 0
        and len(seq2_train_workers(ep, tx, ty, 24, 5, 2, empty, empty, 0, 3, 8, 0.0, 0.0, 0, 1, 1).train_loss) == 0
        and len(seq2_train_workers(ep, tx, ty, 24, 5, 3, empty, empty, 0, 3, 8, 0.02, 0.0, 0, 1, 1).train_loss) == 0
        and len(seq2_train_workers(ep, tx, ty, 24, 5, 2, vx, vy, 9, 3, 8, 0.02, 0.0, 0, 1, 1).train_loss) == 0,
        "invalid shapes / dropout>=1 / lr<=0 -> empty result",
        passed,
        failed,
    )
    check(
        len(seq2_forward(ep, bad_x, 24, 5, 2)) == 0
        and len(seq2_forward(ep, tx, 24, 5, 3)) == 0
        and len(seq2_grad(ep, tx, bad_x, 24, 5, 2)) == 0,
        "forward/grad invalid shapes -> empty",
        passed,
        failed,
    )

    print("  [seq2_trainer] Passed:", passed, "Failed:", failed)


def _mk_zeros(n: Int) -> List[Float64]:
    var out = List[Float64](capacity=n)
    for _ in range(n):
        out.append(0.0)
    return out^
