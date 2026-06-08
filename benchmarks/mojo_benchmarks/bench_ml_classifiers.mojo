"""bench_ml_classifiers.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ml.classifiers import euclidean_distance, manhattan_distance, cosine_similarity, logistic_sigmoid, softmax, knn_predict, kmeans_cluster
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_euclidean_distance: Float64 = 0.0
    var _t0_euclidean_distance = perf_counter_ns()
    for _ in range(N):
        _acc_euclidean_distance += euclidean_distance(_lf5, _lf5)
    var _t1_euclidean_distance = perf_counter_ns()
    var _ns_euclidean_distance = Float64(_t1_euclidean_distance - _t0_euclidean_distance) / Float64(N)
    print("MOJO_TIMING ml_classifiers::euclidean_distance", _ns_euclidean_distance, _acc_euclidean_distance)
    var _result_euclidean_distance = euclidean_distance(_lf5, _lf5)
    var _summary_euclidean_distance = _summary_float64(_result_euclidean_distance)
    print("MOJO_RESULT ml_classifiers::euclidean_distance", _summary_euclidean_distance)
    var _acc_manhattan_distance: Float64 = 0.0
    var _t0_manhattan_distance = perf_counter_ns()
    for _ in range(N):
        _acc_manhattan_distance += manhattan_distance(_lf5, _lf5)
    var _t1_manhattan_distance = perf_counter_ns()
    var _ns_manhattan_distance = Float64(_t1_manhattan_distance - _t0_manhattan_distance) / Float64(N)
    print("MOJO_TIMING ml_classifiers::manhattan_distance", _ns_manhattan_distance, _acc_manhattan_distance)
    var _result_manhattan_distance = manhattan_distance(_lf5, _lf5)
    var _summary_manhattan_distance = _summary_float64(_result_manhattan_distance)
    print("MOJO_RESULT ml_classifiers::manhattan_distance", _summary_manhattan_distance)
    var _acc_cosine_similarity: Float64 = 0.0
    var _t0_cosine_similarity = perf_counter_ns()
    for _ in range(N):
        _acc_cosine_similarity += cosine_similarity(_lf5, _lf5)
    var _t1_cosine_similarity = perf_counter_ns()
    var _ns_cosine_similarity = Float64(_t1_cosine_similarity - _t0_cosine_similarity) / Float64(N)
    print("MOJO_TIMING ml_classifiers::cosine_similarity", _ns_cosine_similarity, _acc_cosine_similarity)
    var _result_cosine_similarity = cosine_similarity(_lf5, _lf5)
    var _summary_cosine_similarity = _summary_float64(_result_cosine_similarity)
    print("MOJO_RESULT ml_classifiers::cosine_similarity", _summary_cosine_similarity)
    var _acc_logistic_sigmoid: Float64 = 0.0
    var _t0_logistic_sigmoid = perf_counter_ns()
    for _ in range(N):
        _acc_logistic_sigmoid += logistic_sigmoid(0.5)
    var _t1_logistic_sigmoid = perf_counter_ns()
    var _ns_logistic_sigmoid = Float64(_t1_logistic_sigmoid - _t0_logistic_sigmoid) / Float64(N)
    print("MOJO_TIMING ml_classifiers::logistic_sigmoid", _ns_logistic_sigmoid, _acc_logistic_sigmoid)
    var _result_logistic_sigmoid = logistic_sigmoid(0.5)
    var _summary_logistic_sigmoid = _summary_float64(_result_logistic_sigmoid)
    print("MOJO_RESULT ml_classifiers::logistic_sigmoid", _summary_logistic_sigmoid)
    var _acc_softmax: Float64 = 0.0
    var _t0_softmax = perf_counter_ns()
    for _ in range(N):
        var _r_softmax = softmax(_lf5)
        _acc_softmax += Float64(len(_r_softmax))
    var _t1_softmax = perf_counter_ns()
    var _ns_softmax = Float64(_t1_softmax - _t0_softmax) / Float64(N)
    print("MOJO_TIMING ml_classifiers::softmax", _ns_softmax, _acc_softmax)
    var _result_softmax = softmax(_lf5)
    var _summary_softmax = _summary_list_float64(_result_softmax)
    print("MOJO_RESULT ml_classifiers::softmax", _summary_softmax)
    var _acc_knn_predict: Float64 = 0.0
    var _t0_knn_predict = perf_counter_ns()
    for _ in range(N):
        _acc_knn_predict += knn_predict([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, _lf5, 5)
    var _t1_knn_predict = perf_counter_ns()
    var _ns_knn_predict = Float64(_t1_knn_predict - _t0_knn_predict) / Float64(N)
    print("MOJO_TIMING ml_classifiers::knn_predict", _ns_knn_predict, _acc_knn_predict)
    var _result_knn_predict = knn_predict([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, _lf5, 5)
    var _summary_knn_predict = _summary_float64(_result_knn_predict)
    print("MOJO_RESULT ml_classifiers::knn_predict", _summary_knn_predict)
    var _acc_kmeans_cluster: Float64 = 0.0
    var _t0_kmeans_cluster = perf_counter_ns()
    for _ in range(N):
        var _r_kmeans_cluster = kmeans_cluster([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5, 5)
        _acc_kmeans_cluster += Float64(len(_r_kmeans_cluster))
    var _t1_kmeans_cluster = perf_counter_ns()
    var _ns_kmeans_cluster = Float64(_t1_kmeans_cluster - _t0_kmeans_cluster) / Float64(N)
    print("MOJO_TIMING ml_classifiers::kmeans_cluster", _ns_kmeans_cluster, _acc_kmeans_cluster)
    var _result_kmeans_cluster = kmeans_cluster([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5, 5)
    var _summary_kmeans_cluster = _summary_list_int(_result_kmeans_cluster)
    print("MOJO_RESULT ml_classifiers::kmeans_cluster", _summary_kmeans_cluster)
