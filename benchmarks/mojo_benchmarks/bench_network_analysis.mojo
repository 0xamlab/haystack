"""bench_network_analysis.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from network_analysis import degree, degree_distribution, density, bfs_distances, pagerank, degree_centrality, closeness_centrality, clustering_coefficient, avg_clustering_coefficient, is_connected, connected_components
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

    var _acc_degree: Float64 = 0.0
    var _t0_degree = perf_counter_ns()
    for _ in range(N):
        _acc_degree += Float64(degree([[0,1,1],[1,0,1],[1,1,0]], 5))
    var _t1_degree = perf_counter_ns()
    var _ns_degree = Float64(_t1_degree - _t0_degree) / Float64(N)
    print("MOJO_TIMING network_analysis::degree", _ns_degree, _acc_degree)
    var _result_degree = degree([[0,1,1],[1,0,1],[1,1,0]], 5)
    var _summary_degree = _summary_int(_result_degree)
    print("MOJO_RESULT network_analysis::degree", _summary_degree)
    var _acc_degree_distribution: Float64 = 0.0
    var _t0_degree_distribution = perf_counter_ns()
    for _ in range(N):
        var _r_degree_distribution = degree_distribution([[0,1,1],[1,0,1],[1,1,0]])
        _acc_degree_distribution += Float64(len(_r_degree_distribution))
    var _t1_degree_distribution = perf_counter_ns()
    var _ns_degree_distribution = Float64(_t1_degree_distribution - _t0_degree_distribution) / Float64(N)
    print("MOJO_TIMING network_analysis::degree_distribution", _ns_degree_distribution, _acc_degree_distribution)
    var _result_degree_distribution = degree_distribution([[0,1,1],[1,0,1],[1,1,0]])
    var _summary_degree_distribution = _summary_list_int(_result_degree_distribution)
    print("MOJO_RESULT network_analysis::degree_distribution", _summary_degree_distribution)
    var _acc_density: Float64 = 0.0
    var _t0_density = perf_counter_ns()
    for _ in range(N):
        _acc_density += density([[0,1,1],[1,0,1],[1,1,0]])
    var _t1_density = perf_counter_ns()
    var _ns_density = Float64(_t1_density - _t0_density) / Float64(N)
    print("MOJO_TIMING network_analysis::density", _ns_density, _acc_density)
    var _result_density = density([[0,1,1],[1,0,1],[1,1,0]])
    var _summary_density = _summary_float64(_result_density)
    print("MOJO_RESULT network_analysis::density", _summary_density)
    var _acc_bfs_distances: Float64 = 0.0
    var _t0_bfs_distances = perf_counter_ns()
    for _ in range(N):
        var _r_bfs_distances = bfs_distances([[0,1,1],[1,0,1],[1,1,0]], 5)
        _acc_bfs_distances += Float64(len(_r_bfs_distances))
    var _t1_bfs_distances = perf_counter_ns()
    var _ns_bfs_distances = Float64(_t1_bfs_distances - _t0_bfs_distances) / Float64(N)
    print("MOJO_TIMING network_analysis::bfs_distances", _ns_bfs_distances, _acc_bfs_distances)
    var _result_bfs_distances = bfs_distances([[0,1,1],[1,0,1],[1,1,0]], 5)
    var _summary_bfs_distances = _summary_list_int(_result_bfs_distances)
    print("MOJO_RESULT network_analysis::bfs_distances", _summary_bfs_distances)
    var _acc_pagerank: Float64 = 0.0
    var _t0_pagerank = perf_counter_ns()
    for _ in range(N):
        var _r_pagerank = pagerank([[0,1,1],[1,0,1],[1,1,0]], 0.5, 5, 0.5)
        _acc_pagerank += Float64(len(_r_pagerank))
    var _t1_pagerank = perf_counter_ns()
    var _ns_pagerank = Float64(_t1_pagerank - _t0_pagerank) / Float64(N)
    print("MOJO_TIMING network_analysis::pagerank", _ns_pagerank, _acc_pagerank)
    var _result_pagerank = pagerank([[0,1,1],[1,0,1],[1,1,0]], 0.5, 5, 0.5)
    var _summary_pagerank = _summary_list_float64(_result_pagerank)
    print("MOJO_RESULT network_analysis::pagerank", _summary_pagerank)
    var _acc_degree_centrality: Float64 = 0.0
    var _t0_degree_centrality = perf_counter_ns()
    for _ in range(N):
        var _r_degree_centrality = degree_centrality([[0,1,1],[1,0,1],[1,1,0]])
        _acc_degree_centrality += Float64(len(_r_degree_centrality))
    var _t1_degree_centrality = perf_counter_ns()
    var _ns_degree_centrality = Float64(_t1_degree_centrality - _t0_degree_centrality) / Float64(N)
    print("MOJO_TIMING network_analysis::degree_centrality", _ns_degree_centrality, _acc_degree_centrality)
    var _result_degree_centrality = degree_centrality([[0,1,1],[1,0,1],[1,1,0]])
    var _summary_degree_centrality = _summary_list_float64(_result_degree_centrality)
    print("MOJO_RESULT network_analysis::degree_centrality", _summary_degree_centrality)
    var _acc_closeness_centrality: Float64 = 0.0
    var _t0_closeness_centrality = perf_counter_ns()
    for _ in range(N):
        var _r_closeness_centrality = closeness_centrality([[0,1,1],[1,0,1],[1,1,0]])
        _acc_closeness_centrality += Float64(len(_r_closeness_centrality))
    var _t1_closeness_centrality = perf_counter_ns()
    var _ns_closeness_centrality = Float64(_t1_closeness_centrality - _t0_closeness_centrality) / Float64(N)
    print("MOJO_TIMING network_analysis::closeness_centrality", _ns_closeness_centrality, _acc_closeness_centrality)
    var _result_closeness_centrality = closeness_centrality([[0,1,1],[1,0,1],[1,1,0]])
    var _summary_closeness_centrality = _summary_list_float64(_result_closeness_centrality)
    print("MOJO_RESULT network_analysis::closeness_centrality", _summary_closeness_centrality)
    var _acc_clustering_coefficient: Float64 = 0.0
    var _t0_clustering_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_clustering_coefficient += clustering_coefficient([[0,1,1],[1,0,1],[1,1,0]], 5)
    var _t1_clustering_coefficient = perf_counter_ns()
    var _ns_clustering_coefficient = Float64(_t1_clustering_coefficient - _t0_clustering_coefficient) / Float64(N)
    print("MOJO_TIMING network_analysis::clustering_coefficient", _ns_clustering_coefficient, _acc_clustering_coefficient)
    var _result_clustering_coefficient = clustering_coefficient([[0,1,1],[1,0,1],[1,1,0]], 5)
    var _summary_clustering_coefficient = _summary_float64(_result_clustering_coefficient)
    print("MOJO_RESULT network_analysis::clustering_coefficient", _summary_clustering_coefficient)
    var _acc_avg_clustering_coefficient: Float64 = 0.0
    var _t0_avg_clustering_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_avg_clustering_coefficient += avg_clustering_coefficient([[0,1,1],[1,0,1],[1,1,0]])
    var _t1_avg_clustering_coefficient = perf_counter_ns()
    var _ns_avg_clustering_coefficient = Float64(_t1_avg_clustering_coefficient - _t0_avg_clustering_coefficient) / Float64(N)
    print("MOJO_TIMING network_analysis::avg_clustering_coefficient", _ns_avg_clustering_coefficient, _acc_avg_clustering_coefficient)
    var _result_avg_clustering_coefficient = avg_clustering_coefficient([[0,1,1],[1,0,1],[1,1,0]])
    var _summary_avg_clustering_coefficient = _summary_float64(_result_avg_clustering_coefficient)
    print("MOJO_RESULT network_analysis::avg_clustering_coefficient", _summary_avg_clustering_coefficient)
    var _acc_is_connected: Float64 = 0.0
    var _t0_is_connected = perf_counter_ns()
    for _ in range(N):
        _acc_is_connected += Float64(is_connected([[0,1,1],[1,0,1],[1,1,0]]))
    var _t1_is_connected = perf_counter_ns()
    var _ns_is_connected = Float64(_t1_is_connected - _t0_is_connected) / Float64(N)
    print("MOJO_TIMING network_analysis::is_connected", _ns_is_connected, _acc_is_connected)
    var _result_is_connected = is_connected([[0,1,1],[1,0,1],[1,1,0]])
    var _summary_is_connected = _summary_bool(_result_is_connected)
    print("MOJO_RESULT network_analysis::is_connected", _summary_is_connected)
    var _acc_connected_components: Float64 = 0.0
    var _t0_connected_components = perf_counter_ns()
    for _ in range(N):
        var _r_connected_components = connected_components([[0,1,1],[1,0,1],[1,1,0]])
        _acc_connected_components += Float64(len(_r_connected_components))
    var _t1_connected_components = perf_counter_ns()
    var _ns_connected_components = Float64(_t1_connected_components - _t0_connected_components) / Float64(N)
    print("MOJO_TIMING network_analysis::connected_components", _ns_connected_components, _acc_connected_components)
    var _result_connected_components = connected_components([[0,1,1],[1,0,1],[1,1,0]])
    var _summary_connected_components = _summary_list_list_int(_result_connected_components)
    print("MOJO_RESULT network_analysis::connected_components", _summary_connected_components)
