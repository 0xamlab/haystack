"""bench_clustering_metrics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from clustering_metrics import cluster_sizes, cluster_centroids, inertia, davies_bouldin, calinski_harabasz, contingency_matrix, purity, adjusted_rand_index
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

    var _acc_cluster_sizes: Float64 = 0.0
    var _t0_cluster_sizes = perf_counter_ns()
    for _ in range(N):
        var _r_cluster_sizes = cluster_sizes(_li5, 5)
        _acc_cluster_sizes += Float64(len(_r_cluster_sizes))
    var _t1_cluster_sizes = perf_counter_ns()
    var _ns_cluster_sizes = Float64(_t1_cluster_sizes - _t0_cluster_sizes) / Float64(N)
    print("MOJO_TIMING clustering_metrics::cluster_sizes", _ns_cluster_sizes, _acc_cluster_sizes)
    var _result_cluster_sizes = cluster_sizes(_li5, 5)
    var _summary_cluster_sizes = _summary_list_int(_result_cluster_sizes)
    print("MOJO_RESULT clustering_metrics::cluster_sizes", _summary_cluster_sizes)
    var _acc_cluster_centroids: Float64 = 0.0
    var _t0_cluster_centroids = perf_counter_ns()
    for _ in range(N):
        var _r_cluster_centroids = cluster_centroids([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, 5)
        _acc_cluster_centroids += Float64(len(_r_cluster_centroids))
    var _t1_cluster_centroids = perf_counter_ns()
    var _ns_cluster_centroids = Float64(_t1_cluster_centroids - _t0_cluster_centroids) / Float64(N)
    print("MOJO_TIMING clustering_metrics::cluster_centroids", _ns_cluster_centroids, _acc_cluster_centroids)
    var _result_cluster_centroids = cluster_centroids([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, 5)
    var _summary_cluster_centroids = _summary_list_list_float64(_result_cluster_centroids)
    print("MOJO_RESULT clustering_metrics::cluster_centroids", _summary_cluster_centroids)
    var _acc_inertia: Float64 = 0.0
    var _t0_inertia = perf_counter_ns()
    for _ in range(N):
        _acc_inertia += inertia([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_inertia = perf_counter_ns()
    var _ns_inertia = Float64(_t1_inertia - _t0_inertia) / Float64(N)
    print("MOJO_TIMING clustering_metrics::inertia", _ns_inertia, _acc_inertia)
    var _result_inertia = inertia([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_inertia = _summary_float64(_result_inertia)
    print("MOJO_RESULT clustering_metrics::inertia", _summary_inertia)
    var _acc_davies_bouldin: Float64 = 0.0
    var _t0_davies_bouldin = perf_counter_ns()
    for _ in range(N):
        _acc_davies_bouldin += davies_bouldin([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, 5)
    var _t1_davies_bouldin = perf_counter_ns()
    var _ns_davies_bouldin = Float64(_t1_davies_bouldin - _t0_davies_bouldin) / Float64(N)
    print("MOJO_TIMING clustering_metrics::davies_bouldin", _ns_davies_bouldin, _acc_davies_bouldin)
    var _result_davies_bouldin = davies_bouldin([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, 5)
    var _summary_davies_bouldin = _summary_float64(_result_davies_bouldin)
    print("MOJO_RESULT clustering_metrics::davies_bouldin", _summary_davies_bouldin)
    var _acc_calinski_harabasz: Float64 = 0.0
    var _t0_calinski_harabasz = perf_counter_ns()
    for _ in range(N):
        _acc_calinski_harabasz += calinski_harabasz([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, 5)
    var _t1_calinski_harabasz = perf_counter_ns()
    var _ns_calinski_harabasz = Float64(_t1_calinski_harabasz - _t0_calinski_harabasz) / Float64(N)
    print("MOJO_TIMING clustering_metrics::calinski_harabasz", _ns_calinski_harabasz, _acc_calinski_harabasz)
    var _result_calinski_harabasz = calinski_harabasz([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, 5)
    var _summary_calinski_harabasz = _summary_float64(_result_calinski_harabasz)
    print("MOJO_RESULT clustering_metrics::calinski_harabasz", _summary_calinski_harabasz)
    var _acc_contingency_matrix: Float64 = 0.0
    var _t0_contingency_matrix = perf_counter_ns()
    for _ in range(N):
        var _r_contingency_matrix = contingency_matrix(_li5, _li5, 5, 5)
        _acc_contingency_matrix += Float64(len(_r_contingency_matrix))
    var _t1_contingency_matrix = perf_counter_ns()
    var _ns_contingency_matrix = Float64(_t1_contingency_matrix - _t0_contingency_matrix) / Float64(N)
    print("MOJO_TIMING clustering_metrics::contingency_matrix", _ns_contingency_matrix, _acc_contingency_matrix)
    var _result_contingency_matrix = contingency_matrix(_li5, _li5, 5, 5)
    var _summary_contingency_matrix = _summary_list_list_int(_result_contingency_matrix)
    print("MOJO_RESULT clustering_metrics::contingency_matrix", _summary_contingency_matrix)
    var _acc_purity: Float64 = 0.0
    var _t0_purity = perf_counter_ns()
    for _ in range(N):
        _acc_purity += purity(_li5, _li5, 5, 5)
    var _t1_purity = perf_counter_ns()
    var _ns_purity = Float64(_t1_purity - _t0_purity) / Float64(N)
    print("MOJO_TIMING clustering_metrics::purity", _ns_purity, _acc_purity)
    var _result_purity = purity(_li5, _li5, 5, 5)
    var _summary_purity = _summary_float64(_result_purity)
    print("MOJO_RESULT clustering_metrics::purity", _summary_purity)
    var _acc_adjusted_rand_index: Float64 = 0.0
    var _t0_adjusted_rand_index = perf_counter_ns()
    for _ in range(N):
        _acc_adjusted_rand_index += adjusted_rand_index(_li5, _li5)
    var _t1_adjusted_rand_index = perf_counter_ns()
    var _ns_adjusted_rand_index = Float64(_t1_adjusted_rand_index - _t0_adjusted_rand_index) / Float64(N)
    print("MOJO_TIMING clustering_metrics::adjusted_rand_index", _ns_adjusted_rand_index, _acc_adjusted_rand_index)
    var _result_adjusted_rand_index = adjusted_rand_index(_li5, _li5)
    var _summary_adjusted_rand_index = _summary_float64(_result_adjusted_rand_index)
    print("MOJO_RESULT clustering_metrics::adjusted_rand_index", _summary_adjusted_rand_index)
