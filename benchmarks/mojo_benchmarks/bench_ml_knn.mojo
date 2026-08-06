"""bench_ml_knn.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ml.knn import euclidean_distance_knn, manhattan_distance, knn_distances, k_nearest_indices, knn_predict, knn_predict_batch, weighted_knn_predict, knn_regression, leave_one_out_cv, optimal_k
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
    var _result_euclidean_distance_knn = euclidean_distance_knn(_lf5, _lf5)
    var _summary_euclidean_distance_knn = _summary_float64(_result_euclidean_distance_knn)
    print("MOJO_RESULT ml_knn::euclidean_distance_knn", _summary_euclidean_distance_knn)
    var _acc_manhattan_distance: Float64 = 0.0
    var _t0_manhattan_distance = perf_counter_ns()
    for _ in range(N):
        _acc_manhattan_distance += manhattan_distance(_lf5, _lf5)
    var _t1_manhattan_distance = perf_counter_ns()
    var _ns_manhattan_distance = Float64(_t1_manhattan_distance - _t0_manhattan_distance) / Float64(N)
    print("MOJO_TIMING ml_knn::manhattan_distance", _ns_manhattan_distance, _acc_manhattan_distance)
    var _result_manhattan_distance = manhattan_distance(_lf5, _lf5)
    var _summary_manhattan_distance = _summary_float64(_result_manhattan_distance)
    print("MOJO_RESULT ml_knn::manhattan_distance", _summary_manhattan_distance)
    var _acc_knn_distances: Float64 = 0.0
    var _t0_knn_distances = perf_counter_ns()
    for _ in range(N):
        var _r_knn_distances = knn_distances([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
        _acc_knn_distances += Float64(len(_r_knn_distances))
    var _t1_knn_distances = perf_counter_ns()
    var _ns_knn_distances = Float64(_t1_knn_distances - _t0_knn_distances) / Float64(N)
    print("MOJO_TIMING ml_knn::knn_distances", _ns_knn_distances, _acc_knn_distances)
    var _result_knn_distances = knn_distances([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
    var _summary_knn_distances = _summary_list_float64(_result_knn_distances)
    print("MOJO_RESULT ml_knn::knn_distances", _summary_knn_distances)
    var _acc_k_nearest_indices: Float64 = 0.0
    var _t0_k_nearest_indices = perf_counter_ns()
    for _ in range(N):
        var _r_k_nearest_indices = k_nearest_indices(_lf5, 5)
        _acc_k_nearest_indices += Float64(len(_r_k_nearest_indices))
    var _t1_k_nearest_indices = perf_counter_ns()
    var _ns_k_nearest_indices = Float64(_t1_k_nearest_indices - _t0_k_nearest_indices) / Float64(N)
    print("MOJO_TIMING ml_knn::k_nearest_indices", _ns_k_nearest_indices, _acc_k_nearest_indices)
    var _result_k_nearest_indices = k_nearest_indices(_lf5, 5)
    var _summary_k_nearest_indices = _summary_list_int(_result_k_nearest_indices)
    print("MOJO_RESULT ml_knn::k_nearest_indices", _summary_k_nearest_indices)
    var _acc_knn_predict: Float64 = 0.0
    var _t0_knn_predict = perf_counter_ns()
    for _ in range(N):
        _acc_knn_predict += Float64(knn_predict([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, _lf5, 5))
    var _t1_knn_predict = perf_counter_ns()
    var _ns_knn_predict = Float64(_t1_knn_predict - _t0_knn_predict) / Float64(N)
    print("MOJO_TIMING ml_knn::knn_predict", _ns_knn_predict, _acc_knn_predict)
    var _result_knn_predict = knn_predict([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, _lf5, 5)
    var _summary_knn_predict = _summary_int(_result_knn_predict)
    print("MOJO_RESULT ml_knn::knn_predict", _summary_knn_predict)
    var _acc_knn_predict_batch: Float64 = 0.0
    var _t0_knn_predict_batch = perf_counter_ns()
    for _ in range(N):
        var _r_knn_predict_batch = knn_predict_batch([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5)
        _acc_knn_predict_batch += Float64(len(_r_knn_predict_batch))
    var _t1_knn_predict_batch = perf_counter_ns()
    var _ns_knn_predict_batch = Float64(_t1_knn_predict_batch - _t0_knn_predict_batch) / Float64(N)
    print("MOJO_TIMING ml_knn::knn_predict_batch", _ns_knn_predict_batch, _acc_knn_predict_batch)
    var _result_knn_predict_batch = knn_predict_batch([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5)
    var _summary_knn_predict_batch = _summary_list_int(_result_knn_predict_batch)
    print("MOJO_RESULT ml_knn::knn_predict_batch", _summary_knn_predict_batch)
    var _acc_weighted_knn_predict: Float64 = 0.0
    var _t0_weighted_knn_predict = perf_counter_ns()
    for _ in range(N):
        _acc_weighted_knn_predict += Float64(weighted_knn_predict([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, _lf5, 5))
    var _t1_weighted_knn_predict = perf_counter_ns()
    var _ns_weighted_knn_predict = Float64(_t1_weighted_knn_predict - _t0_weighted_knn_predict) / Float64(N)
    print("MOJO_TIMING ml_knn::weighted_knn_predict", _ns_weighted_knn_predict, _acc_weighted_knn_predict)
    var _result_weighted_knn_predict = weighted_knn_predict([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, _lf5, 5)
    var _summary_weighted_knn_predict = _summary_int(_result_weighted_knn_predict)
    print("MOJO_RESULT ml_knn::weighted_knn_predict", _summary_weighted_knn_predict)
    var _acc_knn_regression: Float64 = 0.0
    var _t0_knn_regression = perf_counter_ns()
    for _ in range(N):
        _acc_knn_regression += knn_regression([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, _lf5, 5)
    var _t1_knn_regression = perf_counter_ns()
    var _ns_knn_regression = Float64(_t1_knn_regression - _t0_knn_regression) / Float64(N)
    print("MOJO_TIMING ml_knn::knn_regression", _ns_knn_regression, _acc_knn_regression)
    var _result_knn_regression = knn_regression([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, _lf5, 5)
    var _summary_knn_regression = _summary_float64(_result_knn_regression)
    print("MOJO_RESULT ml_knn::knn_regression", _summary_knn_regression)
    var _acc_leave_one_out_cv: Float64 = 0.0
    var _t0_leave_one_out_cv = perf_counter_ns()
    for _ in range(N):
        _acc_leave_one_out_cv += leave_one_out_cv([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, 5)
    var _t1_leave_one_out_cv = perf_counter_ns()
    var _ns_leave_one_out_cv = Float64(_t1_leave_one_out_cv - _t0_leave_one_out_cv) / Float64(N)
    print("MOJO_TIMING ml_knn::leave_one_out_cv", _ns_leave_one_out_cv, _acc_leave_one_out_cv)
    var _result_leave_one_out_cv = leave_one_out_cv([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, 5)
    var _summary_leave_one_out_cv = _summary_float64(_result_leave_one_out_cv)
    print("MOJO_RESULT ml_knn::leave_one_out_cv", _summary_leave_one_out_cv)
    var _acc_optimal_k: Float64 = 0.0
    var _t0_optimal_k = perf_counter_ns()
    for _ in range(N):
        _acc_optimal_k += Float64(optimal_k([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, 5))
    var _t1_optimal_k = perf_counter_ns()
    var _ns_optimal_k = Float64(_t1_optimal_k - _t0_optimal_k) / Float64(N)
    print("MOJO_TIMING ml_knn::optimal_k", _ns_optimal_k, _acc_optimal_k)
    var _result_optimal_k = optimal_k([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, 5)
    var _summary_optimal_k = _summary_int(_result_optimal_k)
    print("MOJO_RESULT ml_knn::optimal_k", _summary_optimal_k)
