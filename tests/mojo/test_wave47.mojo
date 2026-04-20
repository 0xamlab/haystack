"""Tests for Wave 47 — Clustering Metrics, Wavelet Transform, Regression Tree."""

from clustering_metrics import (
    cluster_sizes,
    cluster_centroids,
    inertia,
    davies_bouldin,
    calinski_harabasz,
    contingency_matrix,
    purity,
    adjusted_rand_index,
)
from wavelet import (
    haar_forward,
    haar_inverse,
    haar_multilevel,
    haar_multilevel_inverse,
    threshold_hard,
    threshold_soft,
    denoise_haar,
    energy_ratio,
    detail_coefficients,
    approx_coefficients,
)
from regression_tree import (
    RegressionTree,
    build_tree,
    predict_single,
    predict_batch,
    mse_reduction,
    best_split,
    tree_depth,
    tree_n_leaves,
    tree_mse,
)

from std.math import abs as fabs, sqrt


# ── Helpers ──────────────────────────────────────────────────────────────────


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


fn _assert_eq(a: Int, b: Int, msg: String) raises:
    if a != b:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


fn _lf(a: Float64, b: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a); r.append(b)
    return r^


fn _lf4(a: Float64, b: Float64, c: Float64, d: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a); r.append(b); r.append(c); r.append(d)
    return r^


fn _lf8(a: Float64, b: Float64, c: Float64, d: Float64,
        e: Float64, f: Float64, g: Float64, h: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a); r.append(b); r.append(c); r.append(d)
    r.append(e); r.append(f); r.append(g); r.append(h)
    return r^


fn _li(values: List[Int]) -> List[Int]:
    return values.copy()


# ── Clustering Metrics Tests ─────────────────────────────────────────────────


fn test_cluster_sizes() raises:
    print("  test_cluster_sizes")
    var labels = List[Int]()
    labels.append(0); labels.append(0); labels.append(1)
    labels.append(1); labels.append(1); labels.append(2)
    var sizes = cluster_sizes(labels, 3)
    _assert_eq(sizes[0], 2, "cluster 0 size")      # 1
    _assert_eq(sizes[1], 3, "cluster 1 size")      # 2
    _assert_eq(sizes[2], 1, "cluster 2 size")      # 3
    _assert_eq(len(sizes), 3, "sizes length")       # 4


fn test_cluster_centroids() raises:
    print("  test_cluster_centroids")
    # 2D data, 2 clusters: cluster 0 = {(0,0), (2,2)}, cluster 1 = {(10,10)}
    var data = List[List[Float64]]()
    data.append(_lf(0.0, 0.0))
    data.append(_lf(2.0, 2.0))
    data.append(_lf(10.0, 10.0))
    var labels = List[Int]()
    labels.append(0); labels.append(0); labels.append(1)
    var cents = cluster_centroids(data, labels, 2)
    _assert_close(cents[0][0], 1.0, 1e-9, "centroid 0 x")   # 5
    _assert_close(cents[0][1], 1.0, 1e-9, "centroid 0 y")   # 6
    _assert_close(cents[1][0], 10.0, 1e-9, "centroid 1 x")  # 7
    _assert_close(cents[1][1], 10.0, 1e-9, "centroid 1 y")  # 8


fn test_inertia_perfect() raises:
    print("  test_inertia_perfect")
    # Each point is its own centroid → inertia = 0
    var data = List[List[Float64]]()
    data.append(_lf(1.0, 1.0))
    data.append(_lf(5.0, 5.0))
    var labels = List[Int]()
    labels.append(0); labels.append(1)
    var centroids = List[List[Float64]]()
    centroids.append(_lf(1.0, 1.0))
    centroids.append(_lf(5.0, 5.0))
    var val = inertia(data, labels, centroids)
    _assert_close(val, 0.0, 1e-9, "inertia perfect = 0")    # 9


fn test_inertia_nonzero() raises:
    print("  test_inertia_nonzero")
    var data = List[List[Float64]]()
    data.append(_lf(0.0, 0.0))
    data.append(_lf(2.0, 0.0))
    var labels = List[Int]()
    labels.append(0); labels.append(0)
    var centroids = List[List[Float64]]()
    centroids.append(_lf(1.0, 0.0))
    var val = inertia(data, labels, centroids)
    _assert_close(val, 2.0, 1e-9, "inertia = 2.0")          # 10


fn test_davies_bouldin_separation() raises:
    print("  test_davies_bouldin_separation")
    # Well separated clusters
    var data_good = List[List[Float64]]()
    data_good.append(_lf(0.0, 0.0)); data_good.append(_lf(1.0, 0.0))
    data_good.append(_lf(100.0, 0.0)); data_good.append(_lf(101.0, 0.0))
    var labels_good = List[Int]()
    labels_good.append(0); labels_good.append(0)
    labels_good.append(1); labels_good.append(1)
    var db_good = davies_bouldin(data_good, labels_good, 2)

    # Poorly separated clusters
    var data_bad = List[List[Float64]]()
    data_bad.append(_lf(0.0, 0.0)); data_bad.append(_lf(1.0, 0.0))
    data_bad.append(_lf(2.0, 0.0)); data_bad.append(_lf(3.0, 0.0))
    var labels_bad = List[Int]()
    labels_bad.append(0); labels_bad.append(0)
    labels_bad.append(1); labels_bad.append(1)
    var db_bad = davies_bouldin(data_bad, labels_bad, 2)

    _assert(db_good < db_bad, "DB well-separated < poorly separated")   # 11
    _assert(db_good >= 0.0, "DB >= 0")                                  # 12


fn test_calinski_harabasz_separation() raises:
    print("  test_calinski_harabasz_separation")
    # Well separated clusters
    var data_good = List[List[Float64]]()
    data_good.append(_lf(0.0, 0.0)); data_good.append(_lf(1.0, 0.0))
    data_good.append(_lf(100.0, 0.0)); data_good.append(_lf(101.0, 0.0))
    var labels_good = List[Int]()
    labels_good.append(0); labels_good.append(0)
    labels_good.append(1); labels_good.append(1)
    var ch_good = calinski_harabasz(data_good, labels_good, 2)

    # Poorly separated
    var data_bad = List[List[Float64]]()
    data_bad.append(_lf(0.0, 0.0)); data_bad.append(_lf(1.0, 0.0))
    data_bad.append(_lf(2.0, 0.0)); data_bad.append(_lf(3.0, 0.0))
    var labels_bad = List[Int]()
    labels_bad.append(0); labels_bad.append(0)
    labels_bad.append(1); labels_bad.append(1)
    var ch_bad = calinski_harabasz(data_bad, labels_bad, 2)

    _assert(ch_good > ch_bad, "CH well-separated > poorly separated")   # 13
    _assert(ch_good > 0.0, "CH > 0")                                    # 14


fn test_purity_perfect() raises:
    print("  test_purity_perfect")
    var lt = List[Int]()
    lt.append(0); lt.append(0); lt.append(1); lt.append(1)
    var lp = List[Int]()
    lp.append(0); lp.append(0); lp.append(1); lp.append(1)
    var p = purity(lt, lp, 2, 2)
    _assert_close(p, 1.0, 1e-9, "purity perfect = 1.0")     # 15


fn test_purity_imperfect() raises:
    print("  test_purity_imperfect")
    var lt = List[Int]()
    lt.append(0); lt.append(0); lt.append(1); lt.append(1)
    var lp = List[Int]()
    lp.append(0); lp.append(1); lp.append(0); lp.append(1)
    var p = purity(lt, lp, 2, 2)
    _assert(p >= 0.0, "purity >= 0")                         # 16
    _assert(p <= 1.0, "purity <= 1")                         # 17


fn test_contingency_matrix_dims() raises:
    print("  test_contingency_matrix_dims")
    var lt = List[Int]()
    lt.append(0); lt.append(1); lt.append(2)
    var lp = List[Int]()
    lp.append(0); lp.append(0); lp.append(1)
    var mat = contingency_matrix(lt, lp, 3, 2)
    _assert_eq(len(mat), 3, "contingency rows = 3")          # 18
    _assert_eq(len(mat[0]), 2, "contingency cols = 2")       # 19
    # Check sum = n
    var total: Int = 0
    for i in range(3):
        for j in range(2):
            total += mat[i][j]
    _assert_eq(total, 3, "contingency sum = n")              # 20


fn test_ari_identical() raises:
    print("  test_ari_identical")
    var labels = List[Int]()
    labels.append(0); labels.append(0); labels.append(1)
    labels.append(1); labels.append(2); labels.append(2)
    var ari = adjusted_rand_index(labels, labels)
    _assert_close(ari, 1.0, 1e-9, "ARI identical = 1.0")    # 21


fn test_ari_different() raises:
    print("  test_ari_different")
    var lt = List[Int]()
    lt.append(0); lt.append(0); lt.append(0)
    lt.append(1); lt.append(1); lt.append(1)
    # Completely swapped
    var lp = List[Int]()
    lp.append(1); lp.append(1); lp.append(1)
    lp.append(0); lp.append(0); lp.append(0)
    # Swapped labels but same partition → ARI should be 1
    var ari = adjusted_rand_index(lt, lp)
    _assert_close(ari, 1.0, 1e-9, "ARI swapped = 1.0")      # 22


fn test_ari_random_low() raises:
    print("  test_ari_random_low")
    # Random-ish labels → ARI should be near 0 or at least < 0.5
    var lt = List[Int]()
    lt.append(0); lt.append(0); lt.append(0); lt.append(0)
    lt.append(1); lt.append(1); lt.append(1); lt.append(1)
    var lp = List[Int]()
    lp.append(0); lp.append(1); lp.append(0); lp.append(1)
    lp.append(0); lp.append(1); lp.append(0); lp.append(1)
    var ari = adjusted_rand_index(lt, lp)
    _assert(ari < 0.5, "ARI random-ish < 0.5")              # 23


# ── Wavelet Tests ────────────────────────────────────────────────────────────


fn test_haar_roundtrip() raises:
    print("  test_haar_roundtrip")
    var data = _lf4(1.0, 2.0, 3.0, 4.0)
    var coeffs = haar_forward(data)
    var recon = haar_inverse(coeffs)
    _assert_eq(len(recon), 4, "roundtrip length")            # 24
    _assert_close(recon[0], 1.0, 1e-9, "roundtrip [0]")     # 25
    _assert_close(recon[1], 2.0, 1e-9, "roundtrip [1]")     # 26
    _assert_close(recon[2], 3.0, 1e-9, "roundtrip [2]")     # 27
    _assert_close(recon[3], 4.0, 1e-9, "roundtrip [3]")     # 28


fn test_haar_constant() raises:
    print("  test_haar_constant")
    var data = _lf4(1.0, 1.0, 1.0, 1.0)
    var coeffs = haar_forward(data)
    # Details should be 0 for constant signal
    _assert_close(coeffs[2], 0.0, 1e-9, "detail[0] = 0")    # 29
    _assert_close(coeffs[3], 0.0, 1e-9, "detail[1] = 0")    # 30
    # Approximation values should be equal
    _assert_close(coeffs[0], coeffs[1], 1e-9, "approx equal") # 31


fn test_haar_multilevel_roundtrip() raises:
    print("  test_haar_multilevel_roundtrip")
    var data = _lf8(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0)
    var coeffs = haar_multilevel(data, 3)
    var recon = haar_multilevel_inverse(coeffs, 3)
    _assert_eq(len(recon), 8, "multilevel roundtrip length") # 32
    for i in range(8):
        _assert_close(recon[i], Float64(i + 1), 1e-9,
            "multilevel roundtrip [" + String(i) + "]")      # 33-40


fn test_threshold_hard_zeros() raises:
    print("  test_threshold_hard_zeros")
    var coeffs = _lf4(0.1, -0.05, 2.0, -3.0)
    var th = threshold_hard(coeffs, 0.5)
    _assert_close(th[0], 0.0, 1e-9, "hard: small zeroed")   # 41
    _assert_close(th[1], 0.0, 1e-9, "hard: small zeroed 2") # 42
    _assert_close(th[2], 2.0, 1e-9, "hard: large kept")     # 43
    _assert_close(th[3], -3.0, 1e-9, "hard: large neg kept") # 44


fn test_threshold_soft_shrinks() raises:
    print("  test_threshold_soft_shrinks")
    var coeffs = _lf4(0.1, -0.05, 2.0, -3.0)
    var th = threshold_soft(coeffs, 0.5)
    _assert_close(th[0], 0.0, 1e-9, "soft: small zeroed")   # 45
    _assert_close(th[1], 0.0, 1e-9, "soft: small zeroed 2") # 46
    _assert_close(th[2], 1.5, 1e-9, "soft: 2.0 → 1.5")     # 47
    _assert_close(th[3], -2.5, 1e-9, "soft: -3.0 → -2.5")  # 48


fn test_denoise_haar_smoother() raises:
    print("  test_denoise_haar_smoother")
    # Noisy signal: constant 5 + some noise
    var data = _lf8(5.0, 5.1, 4.9, 5.2, 4.8, 5.0, 5.1, 4.9)
    var denoised = denoise_haar(data, 0.3, 1)
    _assert_eq(len(denoised), 8, "denoised length")          # 49
    # Compute variance of original and denoised
    var mean_orig: Float64 = 0.0
    var mean_den: Float64 = 0.0
    for i in range(8):
        mean_orig += data[i]
        mean_den += denoised[i]
    mean_orig /= 8.0
    mean_den /= 8.0
    var var_orig: Float64 = 0.0
    var var_den: Float64 = 0.0
    for i in range(8):
        var d1 = data[i] - mean_orig
        var_orig += d1 * d1
        var d2 = denoised[i] - mean_den
        var_den += d2 * d2
    _assert(var_den <= var_orig + 1e-9, "denoised variance <= original") # 50


fn test_energy_ratio_bounds() raises:
    print("  test_energy_ratio_bounds")
    var coeffs = _lf4(3.0, 4.0, 0.5, 0.1)
    var er = energy_ratio(coeffs)
    _assert(er >= 0.0, "energy ratio >= 0")                  # 51
    _assert(er <= 1.0, "energy ratio <= 1")                  # 52


fn test_energy_ratio_constant() raises:
    print("  test_energy_ratio_constant")
    # Constant signal → detail = 0 → ratio = 0
    var data = _lf4(1.0, 1.0, 1.0, 1.0)
    var coeffs = haar_forward(data)
    var er = energy_ratio(coeffs)
    _assert_close(er, 0.0, 1e-9, "energy ratio constant = 0") # 53


fn test_detail_coefficients_length() raises:
    print("  test_detail_coefficients_length")
    var coeffs = _lf8(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0)
    var det = detail_coefficients(coeffs)
    _assert_eq(len(det), 4, "detail length = half")          # 54


fn test_approx_coefficients_length() raises:
    print("  test_approx_coefficients_length")
    var coeffs = _lf8(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0)
    var apx = approx_coefficients(coeffs)
    _assert_eq(len(apx), 4, "approx length = half")          # 55


fn test_detail_approx_content() raises:
    print("  test_detail_approx_content")
    var data = _lf4(1.0, 3.0, 5.0, 7.0)
    var coeffs = haar_forward(data)
    var apx = approx_coefficients(coeffs)
    var det = detail_coefficients(coeffs)
    _assert_eq(len(apx), 2, "approx len = 2")               # 56
    _assert_eq(len(det), 2, "detail len = 2")                # 57


# ── Regression Tree Tests ────────────────────────────────────────────────────


fn _make_linear_X() -> List[List[Float64]]:
    """Create X for simple linear data: x in [0..7]."""
    var X = List[List[Float64]]()
    for i in range(8):
        var row = List[Float64]()
        row.append(Float64(i))
        X.append(row^)
    return X^


fn _make_linear_y() -> List[Float64]:
    """Create y for simple linear data: y = 2*x for x in [0..7]."""
    var y = List[Float64]()
    for i in range(8):
        y.append(Float64(i) * 2.0)
    return y^


fn test_build_tree_basic() raises:
    print("  test_build_tree_basic")
    var X = _make_linear_X()
    var y = _make_linear_y()
    var tree = build_tree(X, y, max_depth=3, min_samples=2)
    _assert(tree.n_nodes > 0, "tree has nodes")              # 58
    _assert(tree.n_nodes >= 1, "tree at least 1 node")       # 59


fn test_predict_single_reasonable() raises:
    print("  test_predict_single_reasonable")
    var X = _make_linear_X()
    var y = _make_linear_y()
    var tree = build_tree(X, y, max_depth=5, min_samples=1)
    var x_test = List[Float64]()
    x_test.append(3.0)
    var pred = predict_single(tree, x_test)
    # y = 2*3 = 6; prediction should be close
    _assert(pred >= 0.0, "prediction >= 0")                  # 60
    _assert(pred <= 16.0, "prediction <= max y")             # 61
    _assert_close(pred, 6.0, 3.0, "pred near 6")            # 62


fn test_predict_batch_length() raises:
    print("  test_predict_batch_length")
    var X = _make_linear_X()
    var y = _make_linear_y()
    var tree = build_tree(X, y, max_depth=3)
    var preds = predict_batch(tree, X)
    _assert_eq(len(preds), 8, "batch pred length = 8")      # 63


fn test_tree_depth_limit() raises:
    print("  test_tree_depth_limit")
    var X = _make_linear_X()
    var y = _make_linear_y()
    var tree = build_tree(X, y, max_depth=3, min_samples=1)
    var d = tree_depth(tree)
    _assert(d <= 4, "tree depth <= max_depth + 1")           # 64
    _assert(d >= 1, "tree depth >= 1")                       # 65


fn test_tree_n_leaves_positive() raises:
    print("  test_tree_n_leaves_positive")
    var X = _make_linear_X()
    var y = _make_linear_y()
    var tree = build_tree(X, y, max_depth=3)
    var nl = tree_n_leaves(tree)
    _assert(nl > 0, "n_leaves > 0")                          # 66
    _assert(nl <= tree.n_nodes, "n_leaves <= n_nodes")       # 67


fn test_tree_mse_low() raises:
    print("  test_tree_mse_low")
    var X = _make_linear_X()
    var y = _make_linear_y()
    var tree = build_tree(X, y, max_depth=5, min_samples=1)
    var mse_val = tree_mse(tree, X, y)
    # Variance of y = [0,2,4,6,8,10,12,14]
    var mean_y: Float64 = 7.0
    var var_y: Float64 = 0.0
    for i in range(8):
        var d = y[i] - mean_y
        var_y += d * d
    var_y /= 8.0
    _assert(mse_val < var_y, "tree MSE < variance of y")    # 68
    _assert(mse_val >= 0.0, "MSE >= 0")                     # 69


fn test_mse_reduction_informative() raises:
    print("  test_mse_reduction_informative")
    var y = List[Float64]()
    y.append(1.0); y.append(1.0); y.append(10.0); y.append(10.0)
    var left = List[Int]()
    left.append(0); left.append(1)
    var right = List[Int]()
    right.append(2); right.append(3)
    var red = mse_reduction(y, left, right)
    _assert(red > 0.0, "MSE reduction > 0 for informative") # 70


fn test_mse_reduction_uninformative() raises:
    print("  test_mse_reduction_uninformative")
    var y = List[Float64]()
    y.append(5.0); y.append(5.0); y.append(5.0); y.append(5.0)
    var left = List[Int]()
    left.append(0); left.append(1)
    var right = List[Int]()
    right.append(2); right.append(3)
    var red = mse_reduction(y, left, right)
    _assert_close(red, 0.0, 1e-9, "MSE reduction = 0 for constant") # 71


fn test_best_split_valid() raises:
    print("  test_best_split_valid")
    var X = List[List[Float64]]()
    var y = List[Float64]()
    for i in range(6):
        var row = List[Float64]()
        row.append(Float64(i))
        row.append(Float64(i) * 0.5)
        X.append(row^)
        y.append(Float64(i) * 3.0)
    var indices = List[Int]()
    for i in range(6):
        indices.append(i)
    var result = best_split(X, y, indices)
    _assert(result[0] >= 0.0, "best_split feature >= 0")    # 72
    _assert(result[0] < 2.0, "best_split feature < n_feat") # 73
    _assert(result[2] > 0.0, "best_split reduction > 0")    # 74


fn test_tree_constant_y() raises:
    print("  test_tree_constant_y")
    var X = List[List[Float64]]()
    var y = List[Float64]()
    for i in range(4):
        var row = List[Float64]()
        row.append(Float64(i))
        X.append(row^)
        y.append(5.0)
    var tree = build_tree(X, y, max_depth=3)
    # Should be just a leaf
    _assert_eq(tree_n_leaves(tree), 1, "constant y → 1 leaf") # 75
    var pred = predict_single(tree, X[0])
    _assert_close(pred, 5.0, 1e-9, "constant y pred = 5.0") # 76


fn test_tree_two_groups() raises:
    print("  test_tree_two_groups")
    # Two distinct groups: x<5 → y=0, x>=5 → y=10
    var X = List[List[Float64]]()
    var y = List[Float64]()
    for i in range(10):
        var row = List[Float64]()
        row.append(Float64(i))
        X.append(row^)
        if i < 5:
            y.append(0.0)
        else:
            y.append(10.0)
    var tree = build_tree(X, y, max_depth=5, min_samples=1)
    # Predict on low and high values
    var x_low = List[Float64]()
    x_low.append(2.0)
    var x_high = List[Float64]()
    x_high.append(7.0)
    var pred_low = predict_single(tree, x_low)
    var pred_high = predict_single(tree, x_high)
    _assert_close(pred_low, 0.0, 1.0, "two groups low ≈ 0")  # 77
    _assert_close(pred_high, 10.0, 1.0, "two groups high ≈ 10") # 78


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("=== Wave 47 Tests ===")

    # Clustering metrics
    print("Clustering Metrics:")
    test_cluster_sizes()
    test_cluster_centroids()
    test_inertia_perfect()
    test_inertia_nonzero()
    test_davies_bouldin_separation()
    test_calinski_harabasz_separation()
    test_purity_perfect()
    test_purity_imperfect()
    test_contingency_matrix_dims()
    test_ari_identical()
    test_ari_different()
    test_ari_random_low()

    # Wavelet
    print("Wavelet:")
    test_haar_roundtrip()
    test_haar_constant()
    test_haar_multilevel_roundtrip()
    test_threshold_hard_zeros()
    test_threshold_soft_shrinks()
    test_denoise_haar_smoother()
    test_energy_ratio_bounds()
    test_energy_ratio_constant()
    test_detail_coefficients_length()
    test_approx_coefficients_length()
    test_detail_approx_content()

    # Regression tree
    print("Regression Tree:")
    test_build_tree_basic()
    test_predict_single_reasonable()
    test_predict_batch_length()
    test_tree_depth_limit()
    test_tree_n_leaves_positive()
    test_tree_mse_low()
    test_mse_reduction_informative()
    test_mse_reduction_uninformative()
    test_best_split_valid()
    test_tree_constant_y()
    test_tree_two_groups()

    print("All 78 assertions passed ✓")
