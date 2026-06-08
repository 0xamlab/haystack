"""bench_graph_algorithms.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from graph_algorithms import dijkstra_relax, bellman_ford_relax, pagerank_update, betweenness_centrality_norm, clustering_coefficient, degree_centrality, closeness_centrality, eigenvector_centrality_update, modularity_contribution, graph_density
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

    var _acc_dijkstra_relax: Float64 = 0.0
    var _t0_dijkstra_relax = perf_counter_ns()
    for _ in range(N):
        _acc_dijkstra_relax += dijkstra_relax(0.5, 0.5, 0.5)
    var _t1_dijkstra_relax = perf_counter_ns()
    var _ns_dijkstra_relax = Float64(_t1_dijkstra_relax - _t0_dijkstra_relax) / Float64(N)
    print("MOJO_TIMING graph_algorithms::dijkstra_relax", _ns_dijkstra_relax, _acc_dijkstra_relax)
    var _result_dijkstra_relax = dijkstra_relax(0.5, 0.5, 0.5)
    var _summary_dijkstra_relax = _summary_float64(_result_dijkstra_relax)
    print("MOJO_RESULT graph_algorithms::dijkstra_relax", _summary_dijkstra_relax)
    var _acc_bellman_ford_relax: Float64 = 0.0
    var _t0_bellman_ford_relax = perf_counter_ns()
    for _ in range(N):
        _acc_bellman_ford_relax += bellman_ford_relax(0.5, 0.5, 0.5)
    var _t1_bellman_ford_relax = perf_counter_ns()
    var _ns_bellman_ford_relax = Float64(_t1_bellman_ford_relax - _t0_bellman_ford_relax) / Float64(N)
    print("MOJO_TIMING graph_algorithms::bellman_ford_relax", _ns_bellman_ford_relax, _acc_bellman_ford_relax)
    var _result_bellman_ford_relax = bellman_ford_relax(0.5, 0.5, 0.5)
    var _summary_bellman_ford_relax = _summary_float64(_result_bellman_ford_relax)
    print("MOJO_RESULT graph_algorithms::bellman_ford_relax", _summary_bellman_ford_relax)
    var _acc_pagerank_update: Float64 = 0.0
    var _t0_pagerank_update = perf_counter_ns()
    for _ in range(N):
        _acc_pagerank_update += pagerank_update(0.5, 0.5, 0.5, 0.5)
    var _t1_pagerank_update = perf_counter_ns()
    var _ns_pagerank_update = Float64(_t1_pagerank_update - _t0_pagerank_update) / Float64(N)
    print("MOJO_TIMING graph_algorithms::pagerank_update", _ns_pagerank_update, _acc_pagerank_update)
    var _result_pagerank_update = pagerank_update(0.5, 0.5, 0.5, 0.5)
    var _summary_pagerank_update = _summary_float64(_result_pagerank_update)
    print("MOJO_RESULT graph_algorithms::pagerank_update", _summary_pagerank_update)
    var _acc_betweenness_centrality_norm: Float64 = 0.0
    var _t0_betweenness_centrality_norm = perf_counter_ns()
    for _ in range(N):
        _acc_betweenness_centrality_norm += betweenness_centrality_norm(0.5, 0.5, 0.5)
    var _t1_betweenness_centrality_norm = perf_counter_ns()
    var _ns_betweenness_centrality_norm = Float64(_t1_betweenness_centrality_norm - _t0_betweenness_centrality_norm) / Float64(N)
    print("MOJO_TIMING graph_algorithms::betweenness_centrality_norm", _ns_betweenness_centrality_norm, _acc_betweenness_centrality_norm)
    var _result_betweenness_centrality_norm = betweenness_centrality_norm(0.5, 0.5, 0.5)
    var _summary_betweenness_centrality_norm = _summary_float64(_result_betweenness_centrality_norm)
    print("MOJO_RESULT graph_algorithms::betweenness_centrality_norm", _summary_betweenness_centrality_norm)
    var _acc_clustering_coefficient: Float64 = 0.0
    var _t0_clustering_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_clustering_coefficient += clustering_coefficient(0.5, 0.5)
    var _t1_clustering_coefficient = perf_counter_ns()
    var _ns_clustering_coefficient = Float64(_t1_clustering_coefficient - _t0_clustering_coefficient) / Float64(N)
    print("MOJO_TIMING graph_algorithms::clustering_coefficient", _ns_clustering_coefficient, _acc_clustering_coefficient)
    var _result_clustering_coefficient = clustering_coefficient(0.5, 0.5)
    var _summary_clustering_coefficient = _summary_float64(_result_clustering_coefficient)
    print("MOJO_RESULT graph_algorithms::clustering_coefficient", _summary_clustering_coefficient)
    var _acc_degree_centrality: Float64 = 0.0
    var _t0_degree_centrality = perf_counter_ns()
    for _ in range(N):
        _acc_degree_centrality += degree_centrality(0.5, 0.5)
    var _t1_degree_centrality = perf_counter_ns()
    var _ns_degree_centrality = Float64(_t1_degree_centrality - _t0_degree_centrality) / Float64(N)
    print("MOJO_TIMING graph_algorithms::degree_centrality", _ns_degree_centrality, _acc_degree_centrality)
    var _result_degree_centrality = degree_centrality(0.5, 0.5)
    var _summary_degree_centrality = _summary_float64(_result_degree_centrality)
    print("MOJO_RESULT graph_algorithms::degree_centrality", _summary_degree_centrality)
    var _acc_closeness_centrality: Float64 = 0.0
    var _t0_closeness_centrality = perf_counter_ns()
    for _ in range(N):
        _acc_closeness_centrality += closeness_centrality(0.5, 0.5)
    var _t1_closeness_centrality = perf_counter_ns()
    var _ns_closeness_centrality = Float64(_t1_closeness_centrality - _t0_closeness_centrality) / Float64(N)
    print("MOJO_TIMING graph_algorithms::closeness_centrality", _ns_closeness_centrality, _acc_closeness_centrality)
    var _result_closeness_centrality = closeness_centrality(0.5, 0.5)
    var _summary_closeness_centrality = _summary_float64(_result_closeness_centrality)
    print("MOJO_RESULT graph_algorithms::closeness_centrality", _summary_closeness_centrality)
    var _acc_eigenvector_centrality_update: Float64 = 0.0
    var _t0_eigenvector_centrality_update = perf_counter_ns()
    for _ in range(N):
        _acc_eigenvector_centrality_update += eigenvector_centrality_update(0.5, 0.5)
    var _t1_eigenvector_centrality_update = perf_counter_ns()
    var _ns_eigenvector_centrality_update = Float64(_t1_eigenvector_centrality_update - _t0_eigenvector_centrality_update) / Float64(N)
    print("MOJO_TIMING graph_algorithms::eigenvector_centrality_update", _ns_eigenvector_centrality_update, _acc_eigenvector_centrality_update)
    var _result_eigenvector_centrality_update = eigenvector_centrality_update(0.5, 0.5)
    var _summary_eigenvector_centrality_update = _summary_float64(_result_eigenvector_centrality_update)
    print("MOJO_RESULT graph_algorithms::eigenvector_centrality_update", _summary_eigenvector_centrality_update)
    var _acc_modularity_contribution: Float64 = 0.0
    var _t0_modularity_contribution = perf_counter_ns()
    for _ in range(N):
        _acc_modularity_contribution += modularity_contribution(0.5, 0.5, 0.5, 0.5)
    var _t1_modularity_contribution = perf_counter_ns()
    var _ns_modularity_contribution = Float64(_t1_modularity_contribution - _t0_modularity_contribution) / Float64(N)
    print("MOJO_TIMING graph_algorithms::modularity_contribution", _ns_modularity_contribution, _acc_modularity_contribution)
    var _result_modularity_contribution = modularity_contribution(0.5, 0.5, 0.5, 0.5)
    var _summary_modularity_contribution = _summary_float64(_result_modularity_contribution)
    print("MOJO_RESULT graph_algorithms::modularity_contribution", _summary_modularity_contribution)
    var _acc_graph_density: Float64 = 0.0
    var _t0_graph_density = perf_counter_ns()
    for _ in range(N):
        _acc_graph_density += graph_density(0.5, 0.5, 0.5)
    var _t1_graph_density = perf_counter_ns()
    var _ns_graph_density = Float64(_t1_graph_density - _t0_graph_density) / Float64(N)
    print("MOJO_TIMING graph_algorithms::graph_density", _ns_graph_density, _acc_graph_density)
    var _result_graph_density = graph_density(0.5, 0.5, 0.5)
    var _summary_graph_density = _summary_float64(_result_graph_density)
    print("MOJO_RESULT graph_algorithms::graph_density", _summary_graph_density)
