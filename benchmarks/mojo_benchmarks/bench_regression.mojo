"""bench_regression.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from regression import r_squared, mse, rmse, predict, ols_simple, ols_multiple, ridge_regression, polynomial_features, RegressionResult
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_r_squared: Float64 = 0.0
    var _t0_r_squared = perf_counter_ns()
    for _ in range(N):
        _acc_r_squared += r_squared(_lf5, _lf5)
    var _t1_r_squared = perf_counter_ns()
    var _ns_r_squared = Float64(_t1_r_squared - _t0_r_squared) / Float64(N)
    print("MOJO_TIMING regression::r_squared", _ns_r_squared, _acc_r_squared)
    var _acc_mse: Float64 = 0.0
    var _t0_mse = perf_counter_ns()
    for _ in range(N):
        _acc_mse += mse(_lf5, _lf5)
    var _t1_mse = perf_counter_ns()
    var _ns_mse = Float64(_t1_mse - _t0_mse) / Float64(N)
    print("MOJO_TIMING regression::mse", _ns_mse, _acc_mse)
    var _acc_rmse: Float64 = 0.0
    var _t0_rmse = perf_counter_ns()
    for _ in range(N):
        _acc_rmse += rmse(_lf5, _lf5)
    var _t1_rmse = perf_counter_ns()
    var _ns_rmse = Float64(_t1_rmse - _t0_rmse) / Float64(N)
    print("MOJO_TIMING regression::rmse", _ns_rmse, _acc_rmse)
    var _acc_predict: Float64 = 0.0
    var _t0_predict = perf_counter_ns()
    for _ in range(N):
        var _r_predict = predict([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, 0.5)
        _acc_predict += Float64(len(_r_predict))
    var _t1_predict = perf_counter_ns()
    var _ns_predict = Float64(_t1_predict - _t0_predict) / Float64(N)
    print("MOJO_TIMING regression::predict", _ns_predict, _acc_predict)
    var _keeper_ols_simple = List[RegressionResult]()
    _keeper_ols_simple.append(ols_simple(_lf5, _lf5))
    var _acc_ols_simple: Float64 = 0.0
    var _t0_ols_simple = perf_counter_ns()
    for _ in range(N):
        _keeper_ols_simple[0] = ols_simple(_lf5, _lf5)
        _acc_ols_simple += Float64(len(_keeper_ols_simple))
    var _t1_ols_simple = perf_counter_ns()
    var _ns_ols_simple = Float64(_t1_ols_simple - _t0_ols_simple) / Float64(N)
    print("MOJO_TIMING regression::ols_simple", _ns_ols_simple, _acc_ols_simple)
    var _keeper_ols_multiple = List[RegressionResult]()
    _keeper_ols_multiple.append(ols_multiple([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5))
    var _acc_ols_multiple: Float64 = 0.0
    var _t0_ols_multiple = perf_counter_ns()
    for _ in range(N):
        _keeper_ols_multiple[0] = ols_multiple([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
        _acc_ols_multiple += Float64(len(_keeper_ols_multiple))
    var _t1_ols_multiple = perf_counter_ns()
    var _ns_ols_multiple = Float64(_t1_ols_multiple - _t0_ols_multiple) / Float64(N)
    print("MOJO_TIMING regression::ols_multiple", _ns_ols_multiple, _acc_ols_multiple)
    var _keeper_ridge_regression = List[RegressionResult]()
    _keeper_ridge_regression.append(ridge_regression([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, 0.5))
    var _acc_ridge_regression: Float64 = 0.0
    var _t0_ridge_regression = perf_counter_ns()
    for _ in range(N):
        _keeper_ridge_regression[0] = ridge_regression([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, 0.5)
        _acc_ridge_regression += Float64(len(_keeper_ridge_regression))
    var _t1_ridge_regression = perf_counter_ns()
    var _ns_ridge_regression = Float64(_t1_ridge_regression - _t0_ridge_regression) / Float64(N)
    print("MOJO_TIMING regression::ridge_regression", _ns_ridge_regression, _acc_ridge_regression)
    var _acc_polynomial_features: Float64 = 0.0
    var _t0_polynomial_features = perf_counter_ns()
    for _ in range(N):
        var _r_polynomial_features = polynomial_features(_lf5, 5)
        _acc_polynomial_features += Float64(len(_r_polynomial_features))
    var _t1_polynomial_features = perf_counter_ns()
    var _ns_polynomial_features = Float64(_t1_polynomial_features - _t0_polynomial_features) / Float64(N)
    print("MOJO_TIMING regression::polynomial_features", _ns_polynomial_features, _acc_polynomial_features)
