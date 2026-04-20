"""bench_ml_classifiers.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ml.classifiers import euclidean_distance, manhattan_distance, cosine_similarity, logistic_sigmoid, softmax, knn_predict, kmeans_cluster
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

    var _acc_euclidean_distance: Float64 = 0.0
    var _t0_euclidean_distance = perf_counter_ns()
    for _ in range(N):
        _acc_euclidean_distance += euclidean_distance(_lf5, _lf5)
    var _t1_euclidean_distance = perf_counter_ns()
    var _ns_euclidean_distance = Float64(_t1_euclidean_distance - _t0_euclidean_distance) / Float64(N)
    print("MOJO_TIMING ml_classifiers::euclidean_distance", _ns_euclidean_distance, _acc_euclidean_distance)
    var _acc_manhattan_distance: Float64 = 0.0
    var _t0_manhattan_distance = perf_counter_ns()
    for _ in range(N):
        _acc_manhattan_distance += manhattan_distance(_lf5, _lf5)
    var _t1_manhattan_distance = perf_counter_ns()
    var _ns_manhattan_distance = Float64(_t1_manhattan_distance - _t0_manhattan_distance) / Float64(N)
    print("MOJO_TIMING ml_classifiers::manhattan_distance", _ns_manhattan_distance, _acc_manhattan_distance)
    var _acc_cosine_similarity: Float64 = 0.0
    var _t0_cosine_similarity = perf_counter_ns()
    for _ in range(N):
        _acc_cosine_similarity += cosine_similarity(_lf5, _lf5)
    var _t1_cosine_similarity = perf_counter_ns()
    var _ns_cosine_similarity = Float64(_t1_cosine_similarity - _t0_cosine_similarity) / Float64(N)
    print("MOJO_TIMING ml_classifiers::cosine_similarity", _ns_cosine_similarity, _acc_cosine_similarity)
    var _acc_logistic_sigmoid: Float64 = 0.0
    var _t0_logistic_sigmoid = perf_counter_ns()
    for _ in range(N):
        _acc_logistic_sigmoid += logistic_sigmoid(0.5)
    var _t1_logistic_sigmoid = perf_counter_ns()
    var _ns_logistic_sigmoid = Float64(_t1_logistic_sigmoid - _t0_logistic_sigmoid) / Float64(N)
    print("MOJO_TIMING ml_classifiers::logistic_sigmoid", _ns_logistic_sigmoid, _acc_logistic_sigmoid)
    var _acc_softmax: Float64 = 0.0
    var _t0_softmax = perf_counter_ns()
    for _ in range(N):
        var _r_softmax = softmax(_lf5)
        _acc_softmax += Float64(len(_r_softmax))
    var _t1_softmax = perf_counter_ns()
    var _ns_softmax = Float64(_t1_softmax - _t0_softmax) / Float64(N)
    print("MOJO_TIMING ml_classifiers::softmax", _ns_softmax, _acc_softmax)
    var _acc_knn_predict: Float64 = 0.0
    var _t0_knn_predict = perf_counter_ns()
    for _ in range(N):
        _acc_knn_predict += knn_predict([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, _lf5, 5)
    var _t1_knn_predict = perf_counter_ns()
    var _ns_knn_predict = Float64(_t1_knn_predict - _t0_knn_predict) / Float64(N)
    print("MOJO_TIMING ml_classifiers::knn_predict", _ns_knn_predict, _acc_knn_predict)
    var _acc_kmeans_cluster: Float64 = 0.0
    var _t0_kmeans_cluster = perf_counter_ns()
    for _ in range(N):
        var _r_kmeans_cluster = kmeans_cluster([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5, 5)
        _acc_kmeans_cluster += Float64(len(_r_kmeans_cluster))
    var _t1_kmeans_cluster = perf_counter_ns()
    var _ns_kmeans_cluster = Float64(_t1_kmeans_cluster - _t0_kmeans_cluster) / Float64(N)
    print("MOJO_TIMING ml_classifiers::kmeans_cluster", _ns_kmeans_cluster, _acc_kmeans_cluster)
