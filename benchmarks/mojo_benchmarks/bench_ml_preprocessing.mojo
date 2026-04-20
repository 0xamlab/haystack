"""bench_ml_preprocessing.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ml.preprocessing import normalize_minmax, normalize_zscore, normalize_robust, one_hot_encode, polynomial_features, train_test_split
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

    var _acc_normalize_minmax: Float64 = 0.0
    var _t0_normalize_minmax = perf_counter_ns()
    for _ in range(N):
        var _r_normalize_minmax = normalize_minmax(_lf5)
        _acc_normalize_minmax += Float64(len(_r_normalize_minmax))
    var _t1_normalize_minmax = perf_counter_ns()
    var _ns_normalize_minmax = Float64(_t1_normalize_minmax - _t0_normalize_minmax) / Float64(N)
    print("MOJO_TIMING ml_preprocessing::normalize_minmax", _ns_normalize_minmax, _acc_normalize_minmax)
    var _acc_normalize_zscore: Float64 = 0.0
    var _t0_normalize_zscore = perf_counter_ns()
    for _ in range(N):
        var _r_normalize_zscore = normalize_zscore(_lf5)
        _acc_normalize_zscore += Float64(len(_r_normalize_zscore))
    var _t1_normalize_zscore = perf_counter_ns()
    var _ns_normalize_zscore = Float64(_t1_normalize_zscore - _t0_normalize_zscore) / Float64(N)
    print("MOJO_TIMING ml_preprocessing::normalize_zscore", _ns_normalize_zscore, _acc_normalize_zscore)
    var _acc_normalize_robust: Float64 = 0.0
    var _t0_normalize_robust = perf_counter_ns()
    for _ in range(N):
        var _r_normalize_robust = normalize_robust(_lf5)
        _acc_normalize_robust += Float64(len(_r_normalize_robust))
    var _t1_normalize_robust = perf_counter_ns()
    var _ns_normalize_robust = Float64(_t1_normalize_robust - _t0_normalize_robust) / Float64(N)
    print("MOJO_TIMING ml_preprocessing::normalize_robust", _ns_normalize_robust, _acc_normalize_robust)
    var _acc_one_hot_encode: Float64 = 0.0
    var _t0_one_hot_encode = perf_counter_ns()
    for _ in range(N):
        var _r_one_hot_encode = one_hot_encode(_li5, 5)
        _acc_one_hot_encode += Float64(len(_r_one_hot_encode))
    var _t1_one_hot_encode = perf_counter_ns()
    var _ns_one_hot_encode = Float64(_t1_one_hot_encode - _t0_one_hot_encode) / Float64(N)
    print("MOJO_TIMING ml_preprocessing::one_hot_encode", _ns_one_hot_encode, _acc_one_hot_encode)
    var _acc_polynomial_features: Float64 = 0.0
    var _t0_polynomial_features = perf_counter_ns()
    for _ in range(N):
        var _r_polynomial_features = polynomial_features(_lf5, 5)
        _acc_polynomial_features += Float64(len(_r_polynomial_features))
    var _t1_polynomial_features = perf_counter_ns()
    var _ns_polynomial_features = Float64(_t1_polynomial_features - _t0_polynomial_features) / Float64(N)
    print("MOJO_TIMING ml_preprocessing::polynomial_features", _ns_polynomial_features, _acc_polynomial_features)
    var _acc_train_test_split: Float64 = 0.0
    var _t0_train_test_split = perf_counter_ns()
    for _ in range(N):
        _ = train_test_split(_lf5, _lf5, 0.5)
    var _t1_train_test_split = perf_counter_ns()
    var _ns_train_test_split = Float64(_t1_train_test_split - _t0_train_test_split) / Float64(N)
    print("MOJO_TIMING ml_preprocessing::train_test_split", _ns_train_test_split, _acc_train_test_split)
