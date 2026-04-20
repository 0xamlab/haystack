"""bench_clustering_metrics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from clustering_metrics import cluster_sizes, cluster_centroids, inertia, davies_bouldin, calinski_harabasz, contingency_matrix, purity, adjusted_rand_index
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

    var _acc_cluster_sizes: Float64 = 0.0
    var _t0_cluster_sizes = perf_counter_ns()
    for _ in range(N):
        var _r_cluster_sizes = cluster_sizes(_li5, 5)
        _acc_cluster_sizes += Float64(len(_r_cluster_sizes))
    var _t1_cluster_sizes = perf_counter_ns()
    var _ns_cluster_sizes = Float64(_t1_cluster_sizes - _t0_cluster_sizes) / Float64(N)
    print("MOJO_TIMING clustering_metrics::cluster_sizes", _ns_cluster_sizes, _acc_cluster_sizes)
    var _acc_cluster_centroids: Float64 = 0.0
    var _t0_cluster_centroids = perf_counter_ns()
    for _ in range(N):
        var _r_cluster_centroids = cluster_centroids([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, 5)
        _acc_cluster_centroids += Float64(len(_r_cluster_centroids))
    var _t1_cluster_centroids = perf_counter_ns()
    var _ns_cluster_centroids = Float64(_t1_cluster_centroids - _t0_cluster_centroids) / Float64(N)
    print("MOJO_TIMING clustering_metrics::cluster_centroids", _ns_cluster_centroids, _acc_cluster_centroids)
    var _acc_inertia: Float64 = 0.0
    var _t0_inertia = perf_counter_ns()
    for _ in range(N):
        _acc_inertia += inertia([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_inertia = perf_counter_ns()
    var _ns_inertia = Float64(_t1_inertia - _t0_inertia) / Float64(N)
    print("MOJO_TIMING clustering_metrics::inertia", _ns_inertia, _acc_inertia)
    var _acc_davies_bouldin: Float64 = 0.0
    var _t0_davies_bouldin = perf_counter_ns()
    for _ in range(N):
        _acc_davies_bouldin += davies_bouldin([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, 5)
    var _t1_davies_bouldin = perf_counter_ns()
    var _ns_davies_bouldin = Float64(_t1_davies_bouldin - _t0_davies_bouldin) / Float64(N)
    print("MOJO_TIMING clustering_metrics::davies_bouldin", _ns_davies_bouldin, _acc_davies_bouldin)
    var _acc_calinski_harabasz: Float64 = 0.0
    var _t0_calinski_harabasz = perf_counter_ns()
    for _ in range(N):
        _acc_calinski_harabasz += calinski_harabasz([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, 5)
    var _t1_calinski_harabasz = perf_counter_ns()
    var _ns_calinski_harabasz = Float64(_t1_calinski_harabasz - _t0_calinski_harabasz) / Float64(N)
    print("MOJO_TIMING clustering_metrics::calinski_harabasz", _ns_calinski_harabasz, _acc_calinski_harabasz)
    var _acc_contingency_matrix: Float64 = 0.0
    var _t0_contingency_matrix = perf_counter_ns()
    for _ in range(N):
        var _r_contingency_matrix = contingency_matrix(_li5, _li5, 5, 5)
        _acc_contingency_matrix += Float64(len(_r_contingency_matrix))
    var _t1_contingency_matrix = perf_counter_ns()
    var _ns_contingency_matrix = Float64(_t1_contingency_matrix - _t0_contingency_matrix) / Float64(N)
    print("MOJO_TIMING clustering_metrics::contingency_matrix", _ns_contingency_matrix, _acc_contingency_matrix)
    var _acc_purity: Float64 = 0.0
    var _t0_purity = perf_counter_ns()
    for _ in range(N):
        _acc_purity += purity(_li5, _li5, 5, 5)
    var _t1_purity = perf_counter_ns()
    var _ns_purity = Float64(_t1_purity - _t0_purity) / Float64(N)
    print("MOJO_TIMING clustering_metrics::purity", _ns_purity, _acc_purity)
    var _acc_adjusted_rand_index: Float64 = 0.0
    var _t0_adjusted_rand_index = perf_counter_ns()
    for _ in range(N):
        _acc_adjusted_rand_index += adjusted_rand_index(_li5, _li5)
    var _t1_adjusted_rand_index = perf_counter_ns()
    var _ns_adjusted_rand_index = Float64(_t1_adjusted_rand_index - _t0_adjusted_rand_index) / Float64(N)
    print("MOJO_TIMING clustering_metrics::adjusted_rand_index", _ns_adjusted_rand_index, _acc_adjusted_rand_index)
