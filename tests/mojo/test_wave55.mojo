"""Tests for Wave 55 — Time Series Decomposition, Robustness Testing, KNN."""

from time_series_decompose import (
    moving_average_trend,
    detrend,
    seasonal_component,
    residual,
    decompose_additive,
    seasonal_strength,
    trend_strength,
    detect_period,
    stl_like,
)
from robustness import (
    perturbation_test,
    sensitivity_one_at_a_time,
    morris_screening,
    sobol_first_order_estimate,
    input_range_sweep,
    tornado_data,
    robustness_score,
    eval_test_func,
)
from ml.knn import (
    euclidean_distance_knn,
    manhattan_distance,
    knn_distances,
    k_nearest_indices,
    knn_predict,
    knn_predict_batch,
    weighted_knn_predict,
    knn_regression,
    leave_one_out_cv,
    optimal_k,
)
from std.math import abs as fabs, sin


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error(
            "FAIL: " + msg + " | got " + String(a) + " expected " + String(b)
        )


def _make_list1(a: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a)
    return r^


def _make_list2(a: Float64, b: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a)
    r.append(b)
    return r^


def _make_list3(a: Float64, b: Float64, c: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a)
    r.append(b)
    r.append(c)
    return r^


def _make_list5(a: Float64, b: Float64, c: Float64, d: Float64,
               e: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a)
    r.append(b)
    r.append(c)
    r.append(d)
    r.append(e)
    return r^


def _make_int_list6(a: Int, b: Int, c: Int, d: Int,
                   e: Int, f: Int) -> List[Int]:
    var r = List[Int]()
    r.append(a)
    r.append(b)
    r.append(c)
    r.append(d)
    r.append(e)
    r.append(f)
    return r^


def _make_int_list4(a: Int, b: Int, c: Int, d: Int) -> List[Int]:
    var r = List[Int]()
    r.append(a)
    r.append(b)
    r.append(c)
    r.append(d)
    return r^


# ── Time Series Decomposition tests ─────────────────────────────────────────


def test_moving_average_trend() raises:
    print("  test_moving_average_trend")
    # Constant data → trend is constant in the middle
    var data = _make_list5(1.0, 1.0, 1.0, 1.0, 1.0)
    var t = moving_average_trend(data, 3)
    _assert(len(t) == 5, "trend same length")                                 # 1
    _assert_close(t[1], 1.0, 0.01, "constant trend middle")                   # 2
    _assert_close(t[2], 1.0, 0.01, "constant trend center")                   # 3
    _assert_close(t[3], 1.0, 0.01, "constant trend right")                    # 4
    _assert_close(t[0], 0.0, 0.01, "edge padded 0")                           # 5
    _assert_close(t[4], 0.0, 0.01, "edge padded 0 right")                     # 6


def test_detrend() raises:
    print("  test_detrend")
    var data = _make_list3(10.0, 20.0, 30.0)
    var trend = _make_list3(5.0, 10.0, 15.0)
    var dt = detrend(data, trend)
    _assert(len(dt) == 3, "detrend length")                                    # 7
    _assert_close(dt[0], 5.0, 0.01, "detrend[0]")                             # 8
    _assert_close(dt[1], 10.0, 0.01, "detrend[1]")                            # 9
    _assert_close(dt[2], 15.0, 0.01, "detrend[2]")                            # 10

    # Detrend linear data with linear trend → constant
    var lin = List[Float64]()
    var lin_trend = List[Float64]()
    for i in range(4):
        lin.append(Float64(i + 1) * 2.0)
        lin_trend.append(Float64(i + 1) * 2.0)
    var dt2 = detrend(lin, lin_trend)
    _assert_close(dt2[0], 0.0, 0.01, "linear detrend const 0")                # 11
    _assert_close(dt2[3], 0.0, 0.01, "linear detrend const 3")                # 12


def test_seasonal_component() raises:
    print("  test_seasonal_component")
    # Repeating pattern with period 3: [1, 2, 3, 1, 2, 3]
    var detrended = List[Float64]()
    detrended.append(1.0)
    detrended.append(2.0)
    detrended.append(3.0)
    detrended.append(1.0)
    detrended.append(2.0)
    detrended.append(3.0)
    var sc = seasonal_component(detrended, 3)
    _assert(len(sc) == 6, "seasonal length")                                   # 13
    _assert_close(sc[0], 1.0, 0.01, "seasonal[0]")                            # 14
    _assert_close(sc[1], 2.0, 0.01, "seasonal[1]")                            # 15
    _assert_close(sc[3], 1.0, 0.01, "seasonal tiled")                         # 16


def test_residual() raises:
    print("  test_residual")
    var data = _make_list3(10.0, 20.0, 30.0)
    var trend = _make_list3(5.0, 10.0, 15.0)
    var seasonal = _make_list3(2.0, 3.0, 4.0)
    var r = residual(data, trend, seasonal)
    _assert_close(r[0], 3.0, 0.01, "residual[0]=10-5-2")                      # 17
    _assert_close(r[1], 7.0, 0.01, "residual[1]=20-10-3")                     # 18
    _assert_close(r[2], 11.0, 0.01, "residual[2]=30-15-4")                    # 19


def test_decompose_additive() raises:
    print("  test_decompose_additive")
    # Build data: linear trend + seasonal period 4
    var data = List[Float64]()
    for i in range(20):
        var trend_val = Float64(i) * 0.5
        var season_val = Float64(i % 4) * 1.0
        data.append(trend_val + season_val)
    var result = decompose_additive(data, 4)
    _assert(len(result) == 3, "decompose returns 3 components")                # 20
    _assert(len(result[0]) == 20, "trend length")                             # 21
    _assert(len(result[1]) == 20, "seasonal length")                          # 22
    _assert(len(result[2]) == 20, "residual length")                          # 23

    # trend + seasonal + residual ≈ original (for interior points)
    for i in range(4, 16):
        var recon = result[0][i] + result[1][i] + result[2][i]
        _assert_close(recon, data[i], 0.01,
                      "reconstruction at " + String(i))                        # 24-35


def test_seasonal_strength_and_trend_strength() raises:
    print("  test_seasonal_strength_and_trend_strength")
    var resid = List[Float64]()
    resid.append(0.1)
    resid.append(-0.1)
    resid.append(0.05)
    resid.append(-0.05)

    var sr = List[Float64]()
    sr.append(5.1)
    sr.append(-4.9)
    sr.append(5.05)
    sr.append(-4.95)
    var ss = seasonal_strength(resid, sr)
    _assert(ss >= 0.0 and ss <= 1.0, "seasonal strength in [0,1]")            # 36
    _assert(ss > 0.9, "high seasonal strength")                               # 37

    var tr = List[Float64]()
    tr.append(10.1)
    tr.append(10.2)
    tr.append(9.9)
    tr.append(10.0)
    var ts_val = trend_strength(resid, tr)
    _assert(ts_val >= 0.0 and ts_val <= 1.0, "trend strength in [0,1]")       # 38


def test_detect_period() raises:
    print("  test_detect_period")
    # Create clearly periodic data with period 5
    var data = List[Float64]()
    for i in range(50):
        data.append(sin(Float64(i) * 6.2831853 / 5.0))
    var period = detect_period(data, 20)
    _assert(period == 5, "detected period should be 5, got " + String(period)) # 39


def test_stl_like() raises:
    print("  test_stl_like")
    var data = List[Float64]()
    for i in range(24):
        data.append(Float64(i) * 0.3 + sin(Float64(i) * 6.2831853 / 6.0) * 2.0)
    var result = stl_like(data, 6, 3)
    _assert(len(result) == 3, "stl returns 3 components")                     # 40
    _assert(len(result[0]) == 24, "stl trend length")                         # 41
    _assert(len(result[1]) == 24, "stl seasonal length")                      # 42
    _assert(len(result[2]) == 24, "stl residual length")                      # 43

    # Components sum ≈ original (interior)
    for i in range(6, 18):
        var recon = result[0][i] + result[1][i] + result[2][i]
        _assert_close(recon, data[i], 0.01,
                      "stl reconstruction at " + String(i))                    # 44-55


# ── Robustness tests ────────────────────────────────────────────────────────


def test_eval_test_func() raises:
    print("  test_eval_test_func")
    var x = _make_list3(1.0, 2.0, 3.0)
    _assert_close(eval_test_func(x, 0), 6.0, 0.01, "sum func")               # 56
    _assert_close(eval_test_func(x, 1), 6.0, 0.01, "product func")            # 57
    # weighted: 1*1 + 2*2 + 3*3 = 1+4+9 = 14
    _assert_close(eval_test_func(x, 2), 14.0, 0.01, "weighted sum func")      # 58


def test_perturbation_test() raises:
    print("  test_perturbation_test")
    var vals = _make_list5(1.0, 2.0, 3.0, 4.0, 5.0)
    var pert = perturbation_test(vals, 0.5)
    _assert(len(pert) == 5, "perturbation length")                             # 59
    var any_diff = False
    for i in range(5):
        if fabs(pert[i] - vals[i]) > 1e-10:
            any_diff = True
            break
    _assert(any_diff, "perturbation changed at least one value")               # 60


def test_sensitivity_oat() raises:
    print("  test_sensitivity_oat")
    var base = _make_list3(1.0, 2.0, 3.0)
    var s = sensitivity_one_at_a_time(base, 0, 0.01, 0)
    _assert_close(s, 1.0, 0.1, "OAT sum sensitivity ~ 1")                     # 61
    var s2 = sensitivity_one_at_a_time(base, 1, 0.01, 2)
    _assert_close(s2, 2.0, 0.1, "OAT weighted sensitivity ~ 2")               # 62
    _assert(s > -1e10 and s < 1e10, "OAT finite")                             # 63


def test_morris_screening() raises:
    print("  test_morris_screening")
    var effects = morris_screening(3, 0, 20, 0.1)
    _assert(len(effects) == 3, "morris 3 inputs")                             # 64
    for i in range(3):
        _assert(effects[i] > 0.0,
                "morris effect positive " + String(i))                         # 65-67


def test_tornado_data() raises:
    print("  test_tornado_data")
    var base = _make_list3(1.0, 2.0, 3.0)
    var deltas = _make_list3(0.5, 0.5, 0.5)
    var td = tornado_data(base, deltas, 0)
    _assert(len(td) == 3, "tornado 3 pairs")                                  # 68
    # For sum: low = sum(0.5,2,3)=5.5, high = sum(1.5,2,3)=6.5
    _assert_close(td[0][0], 5.5, 0.01, "tornado low[0]")                      # 69
    _assert_close(td[0][1], 6.5, 0.01, "tornado high[0]")                     # 70


def test_robustness_score() raises:
    print("  test_robustness_score")
    var results = _make_list5(10.0, 10.5, 9.5, 10.2, 9.8)
    var rs = robustness_score(results)
    _assert(rs > 0.0, "robustness score positive")                             # 71
    _assert(rs < 1.0, "robustness score < 1 for low variation")                # 72

    var constant = _make_list3(5.0, 5.0, 5.0)
    var rs2 = robustness_score(constant)
    _assert_close(rs2, 0.0, 0.01, "constant robustness = 0")                  # 73


def test_input_range_sweep() raises:
    print("  test_input_range_sweep")
    var base = _make_list3(1.0, 2.0, 3.0)
    var sweep = input_range_sweep(base, 0, 0.0, 10.0, 11, 0)
    _assert(len(sweep) == 11, "sweep 11 points")                              # 74
    _assert_close(sweep[0][0], 0.0, 0.01, "sweep start")                      # 75
    _assert_close(sweep[10][0], 10.0, 0.01, "sweep end")                      # 76
    # At x0=0, sum = 0+2+3=5
    _assert_close(sweep[0][1], 5.0, 0.01, "sweep output at lo")               # 77


def test_sobol_first_order() raises:
    print("  test_sobol_first_order")
    var si = sobol_first_order_estimate(3, 0, 200)
    _assert(len(si) == 3, "sobol 3 indices")                                  # 78
    for i in range(3):
        _assert(si[i] >= 0.0 and si[i] <= 1.0,
                "sobol index in [0,1]")                                        # 79-81


# ── KNN tests ───────────────────────────────────────────────────────────────


def test_euclidean_distance() raises:
    print("  test_euclidean_distance")
    var a = _make_list2(0.0, 0.0)
    var b = _make_list2(3.0, 4.0)
    var d = euclidean_distance_knn(a, b)
    _assert_close(d, 5.0, 0.01, "euclidean (0,0)->(3,4) = 5")                 # 82

    var c = _make_list3(1.0, 1.0, 1.0)
    var e = _make_list3(1.0, 1.0, 1.0)
    _assert_close(euclidean_distance_knn(c, e), 0.0, 0.01, "same point = 0")  # 83


def test_manhattan_distance() raises:
    print("  test_manhattan_distance")
    var a = _make_list2(0.0, 0.0)
    var b = _make_list2(3.0, 4.0)
    _assert_close(manhattan_distance(a, b), 7.0, 0.01, "manhattan = 7")       # 84


def test_knn_distances() raises:
    print("  test_knn_distances")
    var X = List[List[Float64]]()
    X.append(_make_list2(0.0, 0.0))
    X.append(_make_list2(1.0, 0.0))
    X.append(_make_list2(0.0, 1.0))
    var q = _make_list2(0.0, 0.0)
    var dists = knn_distances(X, q)
    _assert(len(dists) == 3, "knn_distances length")                           # 85
    _assert_close(dists[0], 0.0, 0.01, "dist to self")                        # 86
    _assert_close(dists[1], 1.0, 0.01, "dist to (1,0)")                       # 87


def test_k_nearest_indices() raises:
    print("  test_k_nearest_indices")
    var dists = _make_list5(5.0, 1.0, 3.0, 0.5, 2.0)
    var idx = k_nearest_indices(dists, 3)
    _assert(len(idx) == 3, "k_nearest returns k indices")                      # 88
    _assert(idx[0] == 3, "nearest is index 3")                                # 89
    _assert(idx[1] == 1, "2nd nearest is index 1")                            # 90


def test_knn_predict() raises:
    print("  test_knn_predict")
    var X_train = List[List[Float64]]()
    X_train.append(_make_list2(0.0, 0.0))
    X_train.append(_make_list2(0.1, 0.1))
    X_train.append(_make_list2(0.2, 0.0))
    X_train.append(_make_list2(10.0, 10.0))
    X_train.append(_make_list2(10.1, 10.1))
    X_train.append(_make_list2(10.2, 10.0))
    var y_train = _make_int_list6(0, 0, 0, 1, 1, 1)

    var pred0 = knn_predict(X_train, y_train, _make_list2(0.05, 0.05), 3)
    _assert(pred0 == 0, "knn predicts class 0 near origin")                    # 91

    var pred1 = knn_predict(X_train, y_train, _make_list2(10.05, 10.05), 3)
    _assert(pred1 == 1, "knn predicts class 1 far")                            # 92


def test_knn_predict_batch() raises:
    print("  test_knn_predict_batch")
    var X_train = List[List[Float64]]()
    X_train.append(_make_list2(0.0, 0.0))
    X_train.append(_make_list2(0.1, 0.1))
    X_train.append(_make_list2(10.0, 10.0))
    X_train.append(_make_list2(10.1, 10.1))
    var y_train = _make_int_list4(0, 0, 1, 1)
    var X_test = List[List[Float64]]()
    X_test.append(_make_list2(0.05, 0.05))
    X_test.append(_make_list2(10.05, 10.05))
    var preds = knn_predict_batch(X_train, y_train, X_test, 2)
    _assert(len(preds) == 2, "batch correct length")                           # 93
    _assert(preds[0] == 0, "batch pred 0")                                    # 94
    _assert(preds[1] == 1, "batch pred 1")                                    # 95


def test_weighted_knn_predict() raises:
    print("  test_weighted_knn_predict")
    var X_train = List[List[Float64]]()
    X_train.append(_make_list2(0.0, 0.0))
    X_train.append(_make_list2(0.1, 0.1))
    X_train.append(_make_list2(10.0, 10.0))
    var y_train = _make_list3(0.0, 0.0, 1.0)
    # Need Int list for weighted_knn_predict
    var y_int = List[Int]()
    y_int.append(0)
    y_int.append(0)
    y_int.append(1)
    var pred = weighted_knn_predict(X_train, y_int,
                                    _make_list2(0.05, 0.05), 3)
    _assert(pred == 0, "weighted knn predicts 0")                              # 96
    _assert(pred == 0 or pred == 1, "weighted knn valid class")                # 97


def test_knn_regression() raises:
    print("  test_knn_regression")
    var X_train = List[List[Float64]]()
    X_train.append(_make_list1(0.0))
    X_train.append(_make_list1(1.0))
    X_train.append(_make_list1(2.0))
    X_train.append(_make_list1(3.0))
    var y_train = List[Float64]()
    y_train.append(0.0)
    y_train.append(1.0)
    y_train.append(2.0)
    y_train.append(3.0)
    var pred = knn_regression(X_train, y_train, _make_list1(1.5), 2)
    # Nearest are 1.0 and 2.0, avg y = 1.5
    _assert_close(pred, 1.5, 0.01, "knn regression avg")                      # 98
    _assert(pred >= 0.0 and pred <= 3.0, "knn regression reasonable")          # 99


def test_leave_one_out_cv() raises:
    print("  test_leave_one_out_cv")
    var X = List[List[Float64]]()
    X.append(_make_list2(0.0, 0.0))
    X.append(_make_list2(0.1, 0.1))
    X.append(_make_list2(0.2, 0.0))
    X.append(_make_list2(10.0, 10.0))
    X.append(_make_list2(10.1, 10.1))
    X.append(_make_list2(10.2, 10.0))
    var y = _make_int_list6(0, 0, 0, 1, 1, 1)
    var acc = leave_one_out_cv(X, y, 2)
    _assert(acc >= 0.0 and acc <= 1.0, "LOO accuracy in [0,1]")               # 100
    _assert(acc > 0.8, "LOO accuracy high for easy problem")                   # 101


def test_optimal_k() raises:
    print("  test_optimal_k")
    var X = List[List[Float64]]()
    X.append(_make_list2(0.0, 0.0))
    X.append(_make_list2(0.1, 0.1))
    X.append(_make_list2(0.2, 0.0))
    X.append(_make_list2(10.0, 10.0))
    X.append(_make_list2(10.1, 10.1))
    X.append(_make_list2(10.2, 10.0))
    var y = _make_int_list6(0, 0, 0, 1, 1, 1)
    var best = optimal_k(X, y, 4)
    _assert(best >= 1 and best <= 4, "optimal k in valid range")               # 102


# ── main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("=== Wave 55 Tests ===")

    # Time Series Decomposition
    print("Time Series Decomposition:")
    test_moving_average_trend()
    test_detrend()
    test_seasonal_component()
    test_residual()
    test_decompose_additive()
    test_seasonal_strength_and_trend_strength()
    test_detect_period()
    test_stl_like()

    # Robustness
    print("Robustness:")
    test_eval_test_func()
    test_perturbation_test()
    test_sensitivity_oat()
    test_morris_screening()
    test_tornado_data()
    test_robustness_score()
    test_input_range_sweep()
    test_sobol_first_order()

    # KNN
    print("KNN:")
    test_euclidean_distance()
    test_manhattan_distance()
    test_knn_distances()
    test_k_nearest_indices()
    test_knn_predict()
    test_knn_predict_batch()
    test_weighted_knn_predict()
    test_knn_regression()
    test_leave_one_out_cv()
    test_optimal_k()

    print("All Wave 55 tests passed! ✓")
