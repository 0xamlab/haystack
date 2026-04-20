"""bench_ml_knn.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ml.knn import euclidean_distance_knn, manhattan_distance, knn_distances, k_nearest_indices, knn_predict, knn_predict_batch, weighted_knn_predict, knn_regression, leave_one_out_cv, optimal_k
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

    var _acc_euclidean_distance_knn: Float64 = 0.0
    var _t0_euclidean_distance_knn = perf_counter_ns()
    for _ in range(N):
        _acc_euclidean_distance_knn += euclidean_distance_knn(_lf5, _lf5)
    var _t1_euclidean_distance_knn = perf_counter_ns()
    var _ns_euclidean_distance_knn = Float64(_t1_euclidean_distance_knn - _t0_euclidean_distance_knn) / Float64(N)
    print("MOJO_TIMING ml_knn::euclidean_distance_knn", _ns_euclidean_distance_knn, _acc_euclidean_distance_knn)
    var _acc_manhattan_distance: Float64 = 0.0
    var _t0_manhattan_distance = perf_counter_ns()
    for _ in range(N):
        _acc_manhattan_distance += manhattan_distance(_lf5, _lf5)
    var _t1_manhattan_distance = perf_counter_ns()
    var _ns_manhattan_distance = Float64(_t1_manhattan_distance - _t0_manhattan_distance) / Float64(N)
    print("MOJO_TIMING ml_knn::manhattan_distance", _ns_manhattan_distance, _acc_manhattan_distance)
    var _acc_knn_distances: Float64 = 0.0
    var _t0_knn_distances = perf_counter_ns()
    for _ in range(N):
        var _r_knn_distances = knn_distances([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
        _acc_knn_distances += Float64(len(_r_knn_distances))
    var _t1_knn_distances = perf_counter_ns()
    var _ns_knn_distances = Float64(_t1_knn_distances - _t0_knn_distances) / Float64(N)
    print("MOJO_TIMING ml_knn::knn_distances", _ns_knn_distances, _acc_knn_distances)
    var _acc_k_nearest_indices: Float64 = 0.0
    var _t0_k_nearest_indices = perf_counter_ns()
    for _ in range(N):
        var _r_k_nearest_indices = k_nearest_indices(_lf5, 5)
        _acc_k_nearest_indices += Float64(len(_r_k_nearest_indices))
    var _t1_k_nearest_indices = perf_counter_ns()
    var _ns_k_nearest_indices = Float64(_t1_k_nearest_indices - _t0_k_nearest_indices) / Float64(N)
    print("MOJO_TIMING ml_knn::k_nearest_indices", _ns_k_nearest_indices, _acc_k_nearest_indices)
    var _acc_knn_predict: Float64 = 0.0
    var _t0_knn_predict = perf_counter_ns()
    for _ in range(N):
        _acc_knn_predict += Float64(knn_predict([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, _lf5, 5))
    var _t1_knn_predict = perf_counter_ns()
    var _ns_knn_predict = Float64(_t1_knn_predict - _t0_knn_predict) / Float64(N)
    print("MOJO_TIMING ml_knn::knn_predict", _ns_knn_predict, _acc_knn_predict)
    var _acc_knn_predict_batch: Float64 = 0.0
    var _t0_knn_predict_batch = perf_counter_ns()
    for _ in range(N):
        var _r_knn_predict_batch = knn_predict_batch([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5)
        _acc_knn_predict_batch += Float64(len(_r_knn_predict_batch))
    var _t1_knn_predict_batch = perf_counter_ns()
    var _ns_knn_predict_batch = Float64(_t1_knn_predict_batch - _t0_knn_predict_batch) / Float64(N)
    print("MOJO_TIMING ml_knn::knn_predict_batch", _ns_knn_predict_batch, _acc_knn_predict_batch)
    var _acc_weighted_knn_predict: Float64 = 0.0
    var _t0_weighted_knn_predict = perf_counter_ns()
    for _ in range(N):
        _acc_weighted_knn_predict += Float64(weighted_knn_predict([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, _lf5, 5))
    var _t1_weighted_knn_predict = perf_counter_ns()
    var _ns_weighted_knn_predict = Float64(_t1_weighted_knn_predict - _t0_weighted_knn_predict) / Float64(N)
    print("MOJO_TIMING ml_knn::weighted_knn_predict", _ns_weighted_knn_predict, _acc_weighted_knn_predict)
    var _acc_knn_regression: Float64 = 0.0
    var _t0_knn_regression = perf_counter_ns()
    for _ in range(N):
        _acc_knn_regression += knn_regression([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, _lf5, 5)
    var _t1_knn_regression = perf_counter_ns()
    var _ns_knn_regression = Float64(_t1_knn_regression - _t0_knn_regression) / Float64(N)
    print("MOJO_TIMING ml_knn::knn_regression", _ns_knn_regression, _acc_knn_regression)
    var _acc_leave_one_out_cv: Float64 = 0.0
    var _t0_leave_one_out_cv = perf_counter_ns()
    for _ in range(N):
        _acc_leave_one_out_cv += leave_one_out_cv([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, 5)
    var _t1_leave_one_out_cv = perf_counter_ns()
    var _ns_leave_one_out_cv = Float64(_t1_leave_one_out_cv - _t0_leave_one_out_cv) / Float64(N)
    print("MOJO_TIMING ml_knn::leave_one_out_cv", _ns_leave_one_out_cv, _acc_leave_one_out_cv)
    var _acc_optimal_k: Float64 = 0.0
    var _t0_optimal_k = perf_counter_ns()
    for _ in range(N):
        _acc_optimal_k += Float64(optimal_k([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, 5))
    var _t1_optimal_k = perf_counter_ns()
    var _ns_optimal_k = Float64(_t1_optimal_k - _t0_optimal_k) / Float64(N)
    print("MOJO_TIMING ml_knn::optimal_k", _ns_optimal_k, _acc_optimal_k)
