"""test_gbdt.mojo — known-value tests for gbdt (gradient-boosted trees)."""
from gbdt import (
    GBDTModel,
    gbdt_fit,
    gbdt_predict,
    gbdt_predict_batch,
    gbdt_n_nodes,
)


def _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    var d = a - b
    if d < 0.0:
        d = -d
    return d <= tol


def _next_unit(mut state: UInt64) -> Float64:
    """Deterministic xorshift64 uniform in [0, 1)."""
    state ^= state << 13
    state ^= state >> 7
    state ^= state << 17
    return Float64(state % UInt64(1048576)) / 1048576.0


def _row(a: Float64) -> List[Float64]:
    var out = List[Float64]()
    out.append(a)
    return out^


def _row2(a: Float64, b: Float64) -> List[Float64]:
    var out = List[Float64]()
    out.append(a)
    out.append(b)
    return out^


def check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ gbdt::" + name)
    else:
        failed += 1
        print("  ❌ gbdt::" + name)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── single depth-1 tree recovers the separating threshold ────────────────
    # X (1 col): 0.0,0.1,0.2,0.3 | 1.0,1.1,1.2,1.3; y: 0 x4, 10 x4.
    # base = 5. Best variance-reduction split = midpoint of the gap = 0.65,
    # leaves -5 / +5 (lr = 1) -> exact 0 / 10 predictions.
    var xs = List[Float64]()
    xs.append(0.0)
    xs.append(0.1)
    xs.append(0.2)
    xs.append(0.3)
    xs.append(1.0)
    xs.append(1.1)
    xs.append(1.2)
    xs.append(1.3)
    var ys = List[Float64]()
    for i in range(8):
        if i < 4:
            ys.append(0.0)
        else:
            ys.append(10.0)
    var m1 = gbdt_fit(xs, ys, 1, 1, 1, 1.0)
    var root1 = m1.tree_root[0]
    check(
        len(m1.tree_root) == 1
        and m1.split_feature[root1] == 0
        and _close(m1.split_value[root1], 0.65, 1e-12),
        "depth-1 tree recovers split threshold 0.65",
        passed,
        failed,
    )
    check(
        _close(m1.base_score, 5.0, 1e-12)
        and _close(gbdt_predict(m1, _row(0.15)), 0.0, 1e-12)
        and _close(gbdt_predict(m1, _row(1.05)), 10.0, 1e-12),
        "depth-1 tree exact leaf predictions",
        passed,
        failed,
    )

    # ── shrinkage: lr = 0.5 halves the residual step ─────────────────────────
    # predict = base + 0.5 * leaf_mean: 5 + 0.5*5 = 7.5 and 5 - 2.5 = 2.5.
    var m_lr = gbdt_fit(xs, ys, 1, 1, 1, 0.5)
    check(
        _close(gbdt_predict(m_lr, _row(1.05)), 7.5, 1e-12)
        and _close(gbdt_predict(m_lr, _row(0.15)), 2.5, 1e-12),
        "shrinkage lr=0.5 scales leaf values",
        passed,
        failed,
    )

    # ── hand-computed depth-1 fit on X=[1,2,3,4], y=[1,2,3,4] ────────────────
    # base 2.5, residuals [-1.5,-0.5,0.5,1.5]. Gains: split 1.5 -> 3.0,
    # split 2.5 -> 4.0, split 3.5 -> 3.0. Best 2.5; preds 1.5,1.5,3.5,3.5.
    var x4 = List[Float64]()
    var y4 = List[Float64]()
    for i in range(4):
        x4.append(Float64(i + 1))
        y4.append(Float64(i + 1))
    var m4 = gbdt_fit(x4, y4, 1, 1, 1, 1.0)
    var p4 = gbdt_predict_batch(m4, x4, 1)
    check(
        _close(m4.split_value[m4.tree_root[0]], 2.5, 1e-12)
        and _close(p4[0], 1.5, 1e-12)
        and _close(p4[1], 1.5, 1e-12)
        and _close(p4[2], 3.5, 1e-12)
        and _close(p4[3], 3.5, 1e-12),
        "hand-computed split 2.5 and preds on y=x",
        passed,
        failed,
    )

    # ── min_leaf constrains the split choice ─────────────────────────────────
    # X=[1,2,3,4], y=[10,0,0,0]: unconstrained best split 1.5 (gain 75);
    # min_leaf=2 only allows 2.5 (gain 25); min_leaf=3 -> no split (m < 2*3).
    var yout = List[Float64]()
    yout.append(10.0)
    yout.append(0.0)
    yout.append(0.0)
    yout.append(0.0)
    var m_ml1 = gbdt_fit(x4, yout, 1, 1, 1, 1.0, 1)
    var m_ml2 = gbdt_fit(x4, yout, 1, 1, 1, 1.0, 2)
    var m_ml3 = gbdt_fit(x4, yout, 1, 1, 1, 1.0, 3)
    check(
        _close(m_ml1.split_value[m_ml1.tree_root[0]], 1.5, 1e-12)
        and _close(gbdt_predict(m_ml1, _row(1.0)), 10.0, 1e-12)
        and _close(gbdt_predict(m_ml1, _row(3.0)), 0.0, 1e-12),
        "min_leaf=1 picks unconstrained best split 1.5",
        passed,
        failed,
    )
    check(
        _close(m_ml2.split_value[m_ml2.tree_root[0]], 2.5, 1e-12)
        and _close(gbdt_predict(m_ml2, _row(1.0)), 5.0, 1e-12)
        and _close(gbdt_predict(m_ml2, _row(3.0)), 0.0, 1e-12),
        "min_leaf=2 forces split 2.5",
        passed,
        failed,
    )
    check(
        m_ml3.split_feature[m_ml3.tree_root[0]] == -1
        and _close(gbdt_predict(m_ml3, _row(1.0)), 2.5, 1e-12),
        "min_leaf=3 on n=4 -> root leaf at mean",
        passed,
        failed,
    )

    # ── fit y = x0 + 2*x1 on 200 synthetic rows -> train R2 > 0.9 ────────────
    var state: UInt64 = 0x9E3779B97F4A7C15
    var Xs = List[Float64]()
    var Ys = List[Float64]()
    for _ in range(200):
        var a = _next_unit(state)
        var b = _next_unit(state)
        Xs.append(a)
        Xs.append(b)
        Ys.append(a + 2.0 * b)
    var mb = gbdt_fit(Xs, Ys, 2, 120, 3, 0.1, 2)
    var pb = gbdt_predict_batch(mb, Xs, 2)
    var ymean: Float64 = 0.0
    for i in range(200):
        ymean += Ys[i]
    ymean /= 200.0
    var sse: Float64 = 0.0
    var sst: Float64 = 0.0
    for i in range(200):
        var e = Ys[i] - pb[i]
        sse += e * e
        var d = Ys[i] - ymean
        sst += d * d
    var r2 = 1.0 - sse / sst
    check(r2 > 0.9, "y = x0 + 2*x1, 200 rows: train R2 > 0.9", passed, failed)
    check(
        _close(gbdt_predict(mb, _row2(Xs[0], Xs[1])), pb[0], 1e-12),
        "gbdt_predict matches gbdt_predict_batch",
        passed,
        failed,
    )

    # ── determinism: same seed + subsample -> identical model ────────────────
    var da = gbdt_fit(Xs, Ys, 2, 25, 3, 0.2, 2, 0.6, 42)
    var db = gbdt_fit(Xs, Ys, 2, 25, 3, 0.2, 2, 0.6, 42)
    var pa = gbdt_predict_batch(da, Xs, 2)
    var pbb = gbdt_predict_batch(db, Xs, 2)
    var same = gbdt_n_nodes(da) == gbdt_n_nodes(db)
    for i in range(200):
        if pa[i] != pbb[i]:
            same = False
            break
    check(same, "fixed seed + subsample=0.6 is deterministic", passed, failed)
    # Subsampled fit still learns the trend.
    var sse_s: Float64 = 0.0
    for i in range(200):
        var e2 = Ys[i] - pa[i]
        sse_s += e2 * e2
    check(
        1.0 - sse_s / sst > 0.5,
        "subsampled fit still explains variance",
        passed,
        failed,
    )

    # ── edge: empty y -> base-only model predicting 0 ────────────────────────
    var me = gbdt_fit(List[Float64](), List[Float64](), 2, 10, 3, 0.1)
    check(
        len(me.tree_root) == 0
        and gbdt_n_nodes(me) == 0
        and _close(gbdt_predict(me, _row2(1.0, 2.0)), 0.0, 1e-15),
        "empty y -> no trees, predict 0",
        passed,
        failed,
    )

    # ── edge: n = 1 reproduces the single target exactly ─────────────────────
    var m_one = gbdt_fit(_row(5.0), _row(3.0), 1, 5, 3, 0.7)
    check(
        _close(gbdt_predict(m_one, _row(5.0)), 3.0, 1e-12),
        "n=1 -> predicts the single y exactly",
        passed,
        failed,
    )

    # ── edge: all-equal y -> every tree is a zero leaf ───────────────────────
    var y_eq = List[Float64]()
    for _ in range(4):
        y_eq.append(2.0)
    var m_eq = gbdt_fit(x4, y_eq, 1, 3, 2, 0.3)
    check(
        _close(gbdt_predict(m_eq, _row(1.5)), 2.0, 1e-12)
        and gbdt_n_nodes(m_eq) == 3,
        "all-equal y -> base only, 3 leaf-only trees",
        passed,
        failed,
    )

    # ── edge: all-tied feature values -> no split possible ───────────────────
    var x_tie = List[Float64]()
    for _ in range(4):
        x_tie.append(1.0)
    var m_tie = gbdt_fit(x_tie, y4, 1, 1, 3, 1.0)
    check(
        gbdt_n_nodes(m_tie) == 1
        and m_tie.split_feature[m_tie.tree_root[0]] == -1
        and _close(gbdt_predict(m_tie, _row(1.0)), 2.5, 1e-12),
        "tied feature values -> single leaf at mean",
        passed,
        failed,
    )

    # ── edge: n_trees = 0 -> plain mean predictor ────────────────────────────
    var m0 = gbdt_fit(x4, y4, 1, 0, 3, 0.1)
    check(
        len(m0.tree_root) == 0
        and _close(gbdt_predict(m0, _row(9.0)), 2.5, 1e-12),
        "n_trees=0 -> base score = mean(y)",
        passed,
        failed,
    )

    # ── edge: tiny subsample clamps to >= 1 row and stays finite ─────────────
    var m_sub = gbdt_fit(xs, ys, 1, 4, 2, 0.5, 1, 0.01, 9)
    var pv = gbdt_predict(m_sub, _row(0.5))
    check(pv == pv, "subsample=0.01 clamps to 1 row, finite preds", passed, failed)

    print("  [gbdt] Passed:", passed, "Failed:", failed)
