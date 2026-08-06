"""test_pls.mojo — known-value tests for pls (NIPALS PLS1 regression)."""
from std.math import sqrt, abs as fabs

from pls import PLSResult, pls_fit, pls_predict, pls_predict_rows, pls_r2


def check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ pls::" + name)
    else:
        failed += 1
        print("  ❌ pls::" + name)


def _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    return fabs(a - b) <= tol


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── exact linear data, rank-2 X: 2 components recover y (R² > 0.99) ─────
    # x3 = x1 - 2*x2 exactly (rank 2), y = 2*x1 + x2 - 0.5*x3 + 4 (noiseless,
    # in the column space) -> 2 PLS components reproduce the OLS fit exactly.
    var n1 = 40
    var x1 = List[Float64]()
    var y1 = List[Float64]()
    for i in range(n1):
        var a = 0.5 * Float64(i)
        var b = Float64((i * 7) % 13)
        var c = a - 2.0 * b
        x1.append(a)
        x1.append(b)
        x1.append(c)
        y1.append(2.0 * a + b - 0.5 * c + 4.0)
    var m1 = pls_fit(x1, n1, 3, y1, 2, 100, 1e-10)
    check(m1.n_components == 2, "fit rank2 extracts 2 components", passed, failed)
    var r2_1 = pls_r2(m1, x1, n1, y1)
    check(r2_1 > 0.999, "fit rank2 2-component R2 > 0.99", passed, failed)
    var preds1 = pls_predict_rows(m1, x1, n1)
    var max_err = 0.0
    for i in range(n1):
        var e = fabs(preds1[i] - y1[i])
        if e > max_err:
            max_err = e
    check(max_err < 1e-6, "fit rank2 predictions exact (<1e-6)", passed, failed)
    # Explained variance: y fully explained; X fractions valid and sum <= 1.
    var ev_y_sum = 0.0
    for a in range(m1.n_components):
        ev_y_sum += m1.explained_variance_y[a]
    check(_close(ev_y_sum, 1.0, 1e-6), "explained_variance_y sums to 1", passed, failed)
    var ev_x_sum = 0.0
    var ev_x_ok = True
    for a in range(m1.n_components):
        var v = m1.explained_variance_x[a]
        if v < -1e-9 or v > 1.0 + 1e-9:
            ev_x_ok = False
        ev_x_sum += v
    check(
        ev_x_ok and ev_x_sum <= 1.0 + 1e-9,
        "explained_variance_x fractions valid, sum <= 1",
        passed,
        failed,
    )
    # predict_rows consistent with per-row predict.
    var rows_match = True
    for i in range(0, n1, 7):
        var row = List[Float64]()
        row.append(x1[i * 3 + 0])
        row.append(x1[i * 3 + 1])
        row.append(x1[i * 3 + 2])
        if fabs(pls_predict(m1, row) - preds1[i]) > 1e-12:
            rows_match = False
    check(rows_match, "predict_rows matches pls_predict per row", passed, failed)
    # Requesting more components than rank allows: clamped to <= n_cols.
    var m1b = pls_fit(x1, n1, 3, y1, 10, 100, 1e-10)
    check(m1b.n_components <= 3, "n_components clamped to n_cols", passed, failed)

    # ── single predictor: 1 component is an exact line fit ──────────────────
    var n2 = 10
    var x2 = List[Float64]()
    var y2 = List[Float64]()
    for i in range(n2):
        x2.append(Float64(i))
        y2.append(3.0 * Float64(i) + 1.0)
    var m2 = pls_fit(x2, n2, 1, y2, 1, 100, 1e-10)
    check(m2.n_components == 1, "single predictor 1 component", passed, failed)
    check(pls_r2(m2, x2, n2, y2) > 0.999999, "single predictor R2 ~ 1", passed, failed)
    var probe2 = List[Float64]()
    probe2.append(4.0)
    check(
        _close(pls_predict(m2, probe2), 13.0, 1e-9),
        "single predictor predict(4) = 13",
        passed,
        failed,
    )

    # ── orthogonality: score vectors t_a mutually orthogonal, w unit norm ───
    var n3 = 50
    var p3 = 4
    var x3 = List[Float64]()
    var y3 = List[Float64]()
    for i in range(n3):
        var a = Float64(i)
        var b = Float64((i * i) % 23)
        var c = Float64((i * 5 + 3) % 17)
        var d = Float64((i * 11 + 7) % 29)
        x3.append(a)
        x3.append(b)
        x3.append(c)
        x3.append(d)
        y3.append(a - 2.0 * b + 0.5 * c + 3.0 * d + Float64((i * 13) % 5))
    var m3 = pls_fit(x3, n3, p3, y3, 3, 200, 1e-12)
    check(m3.n_components == 3, "orthogonality fixture 3 components", passed, failed)
    var ortho_ok = True
    for a in range(m3.n_components):
        for b in range(a + 1, m3.n_components):
            var dot = 0.0
            var na = 0.0
            var nb = 0.0
            for i in range(n3):
                var ta = m3.x_scores[a * n3 + i]
                var tb = m3.x_scores[b * n3 + i]
                dot += ta * tb
                na += ta * ta
                nb += tb * tb
            if fabs(dot) / sqrt(na * nb) > 1e-8:
                ortho_ok = False
    check(ortho_ok, "score vectors t_i . t_j ~ 0", passed, failed)
    var wnorm_ok = True
    for a in range(m3.n_components):
        var s = 0.0
        for j in range(p3):
            var w = m3.x_weights[a * p3 + j]
            s += w * w
        if not _close(sqrt(s), 1.0, 1e-9):
            wnorm_ok = False
    check(wnorm_ok, "weight vectors unit norm", passed, failed)

    # ── hand-computed 2x2 sanity ─────────────────────────────────────────────
    # X = [[0,0],[2,4]], y = [1,3]. Standardized (ddof=1):
    # E = [[-1/√2,-1/√2],[1/√2,1/√2]], f = [-1/√2, 1/√2].
    # w = (1/√2, 1/√2); t = (-1, 1); t't = 2; q = 1/√2; p = (1/√2, 1/√2);
    # B = (0.5, 0.5); ev_x = ev_y = 1. Predictions: (0,0)->1 (1,2)->2 (2,4)->3.
    var x4 = List[Float64]()
    x4.append(0.0)
    x4.append(0.0)
    x4.append(2.0)
    x4.append(4.0)
    var y4 = List[Float64]()
    y4.append(1.0)
    y4.append(3.0)
    var m4 = pls_fit(x4, 2, 2, y4, 3, 100, 1e-10)
    var inv_sqrt2 = 0.7071067811865476
    check(m4.n_components == 1, "hand 2x2 clamps to n_rows-1 = 1", passed, failed)
    check(
        _close(m4.x_weights[0], inv_sqrt2, 1e-9)
        and _close(m4.x_weights[1], inv_sqrt2, 1e-9),
        "hand 2x2 weights = (1/√2, 1/√2)",
        passed,
        failed,
    )
    check(
        _close(m4.x_loadings[0], inv_sqrt2, 1e-9)
        and _close(m4.x_loadings[1], inv_sqrt2, 1e-9),
        "hand 2x2 loadings = (1/√2, 1/√2)",
        passed,
        failed,
    )
    check(
        _close(m4.x_scores[0], -1.0, 1e-9) and _close(m4.x_scores[1], 1.0, 1e-9),
        "hand 2x2 scores = (-1, 1)",
        passed,
        failed,
    )
    check(_close(m4.y_loadings[0], inv_sqrt2, 1e-9), "hand 2x2 q = 1/√2", passed, failed)
    check(
        _close(m4.coefs[0], 0.5, 1e-9) and _close(m4.coefs[1], 0.5, 1e-9),
        "hand 2x2 coefs = (0.5, 0.5)",
        passed,
        failed,
    )
    check(
        _close(m4.explained_variance_x[0], 1.0, 1e-9)
        and _close(m4.explained_variance_y[0], 1.0, 1e-9),
        "hand 2x2 explained variance = 1",
        passed,
        failed,
    )
    var p00 = List[Float64]()
    p00.append(0.0)
    p00.append(0.0)
    var p12 = List[Float64]()
    p12.append(1.0)
    p12.append(2.0)
    var p24 = List[Float64]()
    p24.append(2.0)
    p24.append(4.0)
    check(
        _close(pls_predict(m4, p00), 1.0, 1e-9)
        and _close(pls_predict(m4, p12), 2.0, 1e-9)
        and _close(pls_predict(m4, p24), 3.0, 1e-9),
        "hand 2x2 predictions 1/2/3",
        passed,
        failed,
    )

    # ── edge cases ───────────────────────────────────────────────────────────
    # Empty input -> empty model, predict returns 0 (default y_mean).
    var m5 = pls_fit(List[Float64](), 0, 0, List[Float64](), 2, 100, 1e-9)
    check(
        m5.n_components == 0 and m5.n_features == 0
        and pls_predict(m5, List[Float64]()) == 0.0,
        "empty input -> empty model",
        passed,
        failed,
    )
    # n = 1: no components possible; predict = y_mean = y[0].
    var x6 = List[Float64]()
    x6.append(5.0)
    x6.append(7.0)
    var y6 = List[Float64]()
    y6.append(42.0)
    var m6 = pls_fit(x6, 1, 2, y6, 2, 100, 1e-9)
    var probe6 = List[Float64]()
    probe6.append(5.0)
    probe6.append(7.0)
    check(
        m6.n_components == 0 and _close(pls_predict(m6, probe6), 42.0, 1e-12),
        "n=1 -> 0 components, predict = y[0]",
        passed,
        failed,
    )
    # Constant y (all-equal): no covariance, 0 components, predict = mean.
    var n7 = 10
    var x7 = List[Float64]()
    var y7 = List[Float64]()
    for i in range(n7):
        x7.append(Float64(i))
        x7.append(Float64((3 * i) % 7))
        y7.append(5.0)
    var m7 = pls_fit(x7, n7, 2, y7, 2, 100, 1e-9)
    var probe7 = List[Float64]()
    probe7.append(3.0)
    probe7.append(1.0)
    check(
        m7.n_components == 0 and _close(pls_predict(m7, probe7), 5.0, 1e-12),
        "constant y -> 0 components, predict = mean",
        passed,
        failed,
    )
    check(pls_r2(m7, x7, n7, y7) == 1.0, "constant y R2 = 1 (exact mean)", passed, failed)
    # Constant column: ignored (zero-variance guard), fit still exact.
    var n8 = 12
    var x8 = List[Float64]()
    var y8 = List[Float64]()
    for i in range(n8):
        x8.append(Float64(i))
        x8.append(7.0)
        y8.append(2.0 * Float64(i) + 1.0)
    var m8 = pls_fit(x8, n8, 2, y8, 1, 100, 1e-10)
    var probe8 = List[Float64]()
    probe8.append(3.0)
    probe8.append(7.0)
    check(
        pls_r2(m8, x8, n8, y8) > 0.999
        and _close(pls_predict(m8, probe8), 7.0, 1e-6),
        "constant column ignored, fit exact",
        passed,
        failed,
    )
    # Shape mismatch -> empty model.
    var x9 = List[Float64]()
    for _ in range(5):
        x9.append(1.0)
    var y9 = List[Float64]()
    y9.append(1.0)
    y9.append(2.0)
    var m9 = pls_fit(x9, 2, 3, y9, 1, 100, 1e-9)
    check(
        m9.n_components == 0 and m9.n_features == 0,
        "shape mismatch -> empty model",
        passed,
        failed,
    )
    # n_components = 0 requested -> mean model.
    var m10 = pls_fit(x2, n2, 1, y2, 0, 100, 1e-9)
    var probe10 = List[Float64]()
    probe10.append(0.0)
    check(
        m10.n_components == 0 and _close(pls_predict(m10, probe10), 14.5, 1e-12),
        "0 components requested -> predict = y_mean",
        passed,
        failed,
    )

    print("  [pls] Passed:", passed, "Failed:", failed)
