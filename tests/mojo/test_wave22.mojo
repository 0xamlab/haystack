"""Tests for Wave 22 — Anomaly Detection, Regression, Unit Conversion."""

from anomaly import (
    zscore_detect,
    iqr_detect,
    modified_zscore_detect,
    percentile,
    median,
    mad,
    isolation_score,
    grubbs_test_statistic,
    count_anomalies,
)
from regression import (
    RegressionResult,
    ols_simple,
    ols_multiple,
    ridge_regression,
    polynomial_features,
    r_squared,
    predict,
    mse,
    rmse,
)
from units import (
    convert_length,
    convert_mass,
    convert_temperature,
    convert_time,
    convert_area,
    convert_volume,
    convert_speed,
    convert_data,
)
from std.math import abs as fabs


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


fn test_anomaly() raises:
    print("── Anomaly Detection tests ──")
    var n_pass: Int = 0

    # 1. zscore_detect on [1,2,3,100,2,3] — 100 flagged
    var data1 = List[Float64]()
    data1.append(1.0)
    data1.append(2.0)
    data1.append(3.0)
    data1.append(100.0)
    data1.append(2.0)
    data1.append(3.0)
    var zflags = zscore_detect(data1, threshold=2.0)
    _assert(len(zflags) == 6, "zscore_detect len == 6")
    n_pass += 1
    _assert(zflags[3] == True, "zscore: 100 flagged")
    n_pass += 1
    _assert(zflags[0] == False, "zscore: 1 not flagged")
    n_pass += 1

    # 2. iqr_detect on data with outlier
    var iqr_flags = iqr_detect(data1)
    _assert(iqr_flags[3] == True, "iqr: 100 flagged")
    n_pass += 1
    _assert(iqr_flags[1] == False, "iqr: 2 not flagged")
    n_pass += 1

    # 3. modified_zscore_detect — outlier flagged
    var mz_flags = modified_zscore_detect(data1)
    _assert(mz_flags[3] == True, "modified_zscore: 100 flagged")
    n_pass += 1
    _assert(mz_flags[0] == False, "modified_zscore: 1 not flagged")
    n_pass += 1

    # 4. percentile([1,2,3,4,5], 50.0) ≈ 3.0
    var data5 = List[Float64]()
    data5.append(1.0)
    data5.append(2.0)
    data5.append(3.0)
    data5.append(4.0)
    data5.append(5.0)
    _assert_close(percentile(data5, 50.0), 3.0, 1e-10, "percentile 50 == 3.0")
    n_pass += 1

    # 5. percentile 0 and 100
    _assert_close(percentile(data5, 0.0), 1.0, 1e-10, "percentile 0 == 1.0")
    n_pass += 1
    _assert_close(percentile(data5, 100.0), 5.0, 1e-10, "percentile 100 == 5.0")
    n_pass += 1

    # 6. median([1,2,3,4,5]) == 3.0
    _assert_close(median(data5), 3.0, 1e-10, "median odd == 3.0")
    n_pass += 1

    # 7. median([1,2,3,4]) == 2.5
    var data4 = List[Float64]()
    data4.append(1.0)
    data4.append(2.0)
    data4.append(3.0)
    data4.append(4.0)
    _assert_close(median(data4), 2.5, 1e-10, "median even == 2.5")
    n_pass += 1

    # 8. mad on known data [1,2,3,4,5]: median=3, |deviations|=[2,1,0,1,2], mad=1.0
    _assert_close(mad(data5), 1.0, 1e-10, "mad([1,2,3,4,5]) == 1.0")
    n_pass += 1

    # 9. isolation_score: outlier > inlier score
    var iso_data = List[Float64]()
    for i in range(50):
        iso_data.append(Float64(i) * 0.1)  # 0 to 4.9, clustered
    var score_inlier = isolation_score(iso_data, 2.5)
    var score_outlier = isolation_score(iso_data, 100.0)
    _assert(score_outlier > score_inlier, "isolation: outlier score > inlier score")
    n_pass += 1

    # 10. grubbs_test_statistic on data with clear outlier > without
    var grubbs_data = List[Float64]()
    grubbs_data.append(10.0)
    grubbs_data.append(10.1)
    grubbs_data.append(9.9)
    grubbs_data.append(10.2)
    grubbs_data.append(50.0)  # outlier
    var g_with = grubbs_test_statistic(grubbs_data)

    var grubbs_clean = List[Float64]()
    grubbs_clean.append(10.0)
    grubbs_clean.append(10.1)
    grubbs_clean.append(9.9)
    grubbs_clean.append(10.2)
    grubbs_clean.append(10.05)
    var g_without = grubbs_test_statistic(grubbs_clean)
    _assert(g_with > g_without, "grubbs: data with outlier > without")
    n_pass += 1

    # 11. count_anomalies
    var flags = List[Bool]()
    flags.append(True)
    flags.append(False)
    flags.append(True)
    flags.append(False)
    flags.append(True)
    _assert(count_anomalies(flags) == 3, "count_anomalies == 3")
    n_pass += 1

    # 12. count_anomalies on zscore result
    _assert(count_anomalies(zflags) == 1, "count_anomalies zscore == 1")
    n_pass += 1

    print("  Anomaly: " + String(n_pass) + " assertions passed")


fn test_regression() raises:
    print("── Regression tests ──")
    var n_pass: Int = 0

    # 1-2. ols_simple on y = 2x + 1
    var x = List[Float64]()
    var y = List[Float64]()
    for i in range(10):
        x.append(Float64(i))
        y.append(2.0 * Float64(i) + 1.0)
    var res = ols_simple(x, y)
    _assert_close(res.coefficients[0], 2.0, 1e-10, "ols_simple slope ≈ 2.0")
    n_pass += 1
    _assert_close(res.intercept, 1.0, 1e-10, "ols_simple intercept ≈ 1.0")
    n_pass += 1

    # 3. R² on perfect fit ≈ 1.0
    _assert_close(res.r_squared, 1.0, 1e-10, "ols_simple R² ≈ 1.0")
    n_pass += 1

    # 4. r_squared on perfect prediction
    var y_pred = List[Float64]()
    for i in range(10):
        y_pred.append(y[i])
    _assert_close(r_squared(y, y_pred), 1.0, 1e-10, "r_squared perfect == 1.0")
    n_pass += 1

    # 5. mse on identical predictions ≈ 0.0
    _assert_close(mse(y, y_pred), 0.0, 1e-10, "mse identical == 0.0")
    n_pass += 1

    # 6. rmse on known residuals: y=[1,2,3], yhat=[1.5,2.5,3.5] -> mse=0.25, rmse=0.5
    var ya = List[Float64]()
    ya.append(1.0)
    ya.append(2.0)
    ya.append(3.0)
    var yp = List[Float64]()
    yp.append(1.5)
    yp.append(2.5)
    yp.append(3.5)
    _assert_close(rmse(ya, yp), 0.5, 1e-10, "rmse == 0.5")
    n_pass += 1

    # 7. polynomial_features([2,3], 3) — n=2, degree=3
    var pf_x = List[Float64]()
    pf_x.append(2.0)
    pf_x.append(3.0)
    var pf = polynomial_features(pf_x, 3)
    _assert(len(pf) == 2, "poly_features n == 2")
    n_pass += 1
    _assert(len(pf[0]) == 3, "poly_features degree == 3 cols")
    n_pass += 1
    # pf[0] = [2, 4, 8], pf[1] = [3, 9, 27]
    _assert_close(pf[0][0], 2.0, 1e-10, "pf[0][0] == 2")
    n_pass += 1
    _assert_close(pf[0][1], 4.0, 1e-10, "pf[0][1] == 4")
    n_pass += 1
    _assert_close(pf[0][2], 8.0, 1e-10, "pf[0][2] == 8")
    n_pass += 1
    _assert_close(pf[1][2], 27.0, 1e-10, "pf[1][2] == 27")
    n_pass += 1

    # 8. predict with known coefficients
    # X = [[1,0],[0,1],[1,1]], β=[2,3], intercept=5 -> [7,8,10]
    var Xp = List[List[Float64]]()
    var r0 = List[Float64]()
    r0.append(1.0)
    r0.append(0.0)
    Xp.append(r0^)
    var r1 = List[Float64]()
    r1.append(0.0)
    r1.append(1.0)
    Xp.append(r1^)
    var r2 = List[Float64]()
    r2.append(1.0)
    r2.append(1.0)
    Xp.append(r2^)
    var beta = List[Float64]()
    beta.append(2.0)
    beta.append(3.0)
    var pred_vals = predict(Xp, beta, 5.0)
    _assert_close(pred_vals[0], 7.0, 1e-10, "predict [1,0] -> 7")
    n_pass += 1
    _assert_close(pred_vals[1], 8.0, 1e-10, "predict [0,1] -> 8")
    n_pass += 1
    _assert_close(pred_vals[2], 10.0, 1e-10, "predict [1,1] -> 10")
    n_pass += 1

    # 9. ols_multiple on 2-predictor data: y = 3*x1 + 2*x2 + 1
    var Xm = List[List[Float64]]()
    var ym = List[Float64]()
    for i in range(20):
        var x1 = Float64(i)
        var x2 = Float64(i) * 0.5
        var row = List[Float64]()
        row.append(x1)
        row.append(x2)
        Xm.append(row^)
        ym.append(3.0 * x1 + 2.0 * x2 + 1.0)
    var res_m = ols_multiple(Xm, ym)
    _assert(res_m.r_squared > 0.99, "ols_multiple R² > 0.99")
    n_pass += 1

    # 10. ridge_regression coefficients smaller than OLS (more regularized)
    var res_ridge = ridge_regression(Xm, ym, 10.0)
    # With high alpha, coefficients are shrunk
    var ols_norm: Float64 = 0.0
    var ridge_norm: Float64 = 0.0
    for j in range(len(res_m.coefficients)):
        ols_norm += res_m.coefficients[j] * res_m.coefficients[j]
        ridge_norm += res_ridge.coefficients[j] * res_ridge.coefficients[j]
    _assert(ridge_norm <= ols_norm + 1e-6, "ridge coeff norm <= ols coeff norm")
    n_pass += 1

    # 11. ridge still gets reasonable R²
    _assert(res_ridge.r_squared > 0.9, "ridge R² > 0.9")
    n_pass += 1

    # 12. residuals length matches input
    _assert(len(res.residuals) == 10, "ols_simple residuals len == 10")
    n_pass += 1

    print("  Regression: " + String(n_pass) + " assertions passed")


fn test_units() raises:
    print("── Unit Conversion tests ──")
    var n_pass: Int = 0

    # 1. convert_length(1.0, "km", "m") == 1000.0
    _assert_close(convert_length(1.0, "km", "m"), 1000.0, 1e-6, "1km == 1000m")
    n_pass += 1

    # 2. convert_length(1.0, "mi", "km") ≈ 1.60934
    _assert_close(convert_length(1.0, "mi", "km"), 1.609344, 1e-4, "1mi ≈ 1.609km")
    n_pass += 1

    # 3. convert_length(1.0, "ft", "in") == 12.0
    _assert_close(convert_length(1.0, "ft", "in"), 12.0, 1e-6, "1ft == 12in")
    n_pass += 1

    # 4. convert_mass(1.0, "kg", "lb") ≈ 2.20462
    _assert_close(convert_mass(1.0, "kg", "lb"), 2.20462, 1e-3, "1kg ≈ 2.205lb")
    n_pass += 1

    # 5. convert_mass(1.0, "kg", "g") == 1000.0
    _assert_close(convert_mass(1.0, "kg", "g"), 1000.0, 1e-6, "1kg == 1000g")
    n_pass += 1

    # 6. convert_temperature(0.0, "C", "F") ≈ 32.0
    _assert_close(convert_temperature(0.0, "C", "F"), 32.0, 1e-6, "0C == 32F")
    n_pass += 1

    # 7. convert_temperature(100.0, "C", "K") ≈ 373.15
    _assert_close(convert_temperature(100.0, "C", "K"), 373.15, 1e-6, "100C == 373.15K")
    n_pass += 1

    # 8. convert_temperature(32.0, "F", "C") ≈ 0.0
    _assert_close(convert_temperature(32.0, "F", "C"), 0.0, 1e-6, "32F == 0C")
    n_pass += 1

    # 9. convert_temperature(212.0, "F", "K") ≈ 373.15
    _assert_close(convert_temperature(212.0, "F", "K"), 373.15, 1e-6, "212F == 373.15K")
    n_pass += 1

    # 10. convert_time(1.0, "hr", "min") == 60.0
    _assert_close(convert_time(1.0, "hr", "min"), 60.0, 1e-6, "1hr == 60min")
    n_pass += 1

    # 11. convert_time(1.0, "day", "hr") == 24.0
    _assert_close(convert_time(1.0, "day", "hr"), 24.0, 1e-6, "1day == 24hr")
    n_pass += 1

    # 12. convert_time(1.0, "week", "day") == 7.0
    _assert_close(convert_time(1.0, "week", "day"), 7.0, 1e-6, "1week == 7day")
    n_pass += 1

    # 13. convert_area(1.0, "km2", "m2") == 1000000.0
    _assert_close(convert_area(1.0, "km2", "m2"), 1000000.0, 1e-3, "1km2 == 1000000m2")
    n_pass += 1

    # 14. convert_volume(1.0, "gal", "L") ≈ 3.78541
    _assert_close(convert_volume(1.0, "gal", "L"), 3.785411784, 1e-4, "1gal ≈ 3.785L")
    n_pass += 1

    # 15. convert_speed(1.0, "km/h", "m/s") ≈ 0.27778
    _assert_close(convert_speed(1.0, "km/h", "m/s"), 0.27778, 1e-3, "1km/h ≈ 0.278m/s")
    n_pass += 1

    # 16. convert_data(1.0, "GB", "MB") == 1024.0
    _assert_close(convert_data(1.0, "GB", "MB"), 1024.0, 1e-6, "1GB == 1024MB")
    n_pass += 1

    # 17. convert_data(1.0, "TB", "GB") == 1024.0
    _assert_close(convert_data(1.0, "TB", "GB"), 1024.0, 1e-6, "1TB == 1024GB")
    n_pass += 1

    # 18. Roundtrip: convert(convert(5.0, "mi", "km"), "km", "mi") ≈ 5.0
    var rt_len = convert_length(convert_length(5.0, "mi", "km"), "km", "mi")
    _assert_close(rt_len, 5.0, 1e-10, "length roundtrip mi->km->mi == 5.0")
    n_pass += 1

    # 19. Roundtrip temperature: C -> F -> C
    var rt_temp = convert_temperature(convert_temperature(37.0, "C", "F"), "F", "C")
    _assert_close(rt_temp, 37.0, 1e-10, "temp roundtrip C->F->C == 37.0")
    n_pass += 1

    # 20. convert_speed(1.0, "knot", "km/h") ≈ 1.852
    _assert_close(convert_speed(1.0, "knot", "km/h"), 1.852, 1e-3, "1knot ≈ 1.852km/h")
    n_pass += 1

    # 21. convert_volume(1.0, "m3", "L") == 1000.0
    _assert_close(convert_volume(1.0, "m3", "L"), 1000.0, 1e-6, "1m3 == 1000L")
    n_pass += 1

    print("  Units: " + String(n_pass) + " assertions passed")


fn main() raises:
    print("=== Wave 22 Tests: Anomaly, Regression, Units ===")
    test_anomaly()
    test_regression()
    test_units()
    print("=== All Wave 22 tests passed ===")
