"""bench_ml_clustering.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ml.clustering import euclidean_distance, assign_cluster, kmeans, silhouette_score, KMeansResult
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
    print("MOJO_TIMING ml_clustering::euclidean_distance", _ns_euclidean_distance, _acc_euclidean_distance)
    var _acc_assign_cluster: Float64 = 0.0
    var _t0_assign_cluster = perf_counter_ns()
    for _ in range(N):
        _acc_assign_cluster += Float64(assign_cluster(_lf5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]))
    var _t1_assign_cluster = perf_counter_ns()
    var _ns_assign_cluster = Float64(_t1_assign_cluster - _t0_assign_cluster) / Float64(N)
    print("MOJO_TIMING ml_clustering::assign_cluster", _ns_assign_cluster, _acc_assign_cluster)
    var _keeper_kmeans = List[KMeansResult]()
    _keeper_kmeans.append(kmeans([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5, 5, 0.5))
    var _acc_kmeans: Float64 = 0.0
    var _t0_kmeans = perf_counter_ns()
    for _ in range(N):
        _keeper_kmeans[0] = kmeans([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5, 5, 0.5)
        _acc_kmeans += Float64(len(_keeper_kmeans))
    var _t1_kmeans = perf_counter_ns()
    var _ns_kmeans = Float64(_t1_kmeans - _t0_kmeans) / Float64(N)
    print("MOJO_TIMING ml_clustering::kmeans", _ns_kmeans, _acc_kmeans)
    var _acc_silhouette_score: Float64 = 0.0
    var _t0_silhouette_score = perf_counter_ns()
    for _ in range(N):
        _acc_silhouette_score += silhouette_score([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5)
    var _t1_silhouette_score = perf_counter_ns()
    var _ns_silhouette_score = Float64(_t1_silhouette_score - _t0_silhouette_score) / Float64(N)
    print("MOJO_TIMING ml_clustering::silhouette_score", _ns_silhouette_score, _acc_silhouette_score)
