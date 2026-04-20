"""bench_graph_algorithms.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from graph_algorithms import dijkstra_relax, bellman_ford_relax, pagerank_update, betweenness_centrality_norm, clustering_coefficient, degree_centrality, closeness_centrality, eigenvector_centrality_update, modularity_contribution, graph_density
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

    var _acc_dijkstra_relax: Float64 = 0.0
    var _t0_dijkstra_relax = perf_counter_ns()
    for _ in range(N):
        _acc_dijkstra_relax += dijkstra_relax(0.5, 0.5, 0.5)
    var _t1_dijkstra_relax = perf_counter_ns()
    var _ns_dijkstra_relax = Float64(_t1_dijkstra_relax - _t0_dijkstra_relax) / Float64(N)
    print("MOJO_TIMING graph_algorithms::dijkstra_relax", _ns_dijkstra_relax, _acc_dijkstra_relax)
    var _acc_bellman_ford_relax: Float64 = 0.0
    var _t0_bellman_ford_relax = perf_counter_ns()
    for _ in range(N):
        _acc_bellman_ford_relax += bellman_ford_relax(0.5, 0.5, 0.5)
    var _t1_bellman_ford_relax = perf_counter_ns()
    var _ns_bellman_ford_relax = Float64(_t1_bellman_ford_relax - _t0_bellman_ford_relax) / Float64(N)
    print("MOJO_TIMING graph_algorithms::bellman_ford_relax", _ns_bellman_ford_relax, _acc_bellman_ford_relax)
    var _acc_pagerank_update: Float64 = 0.0
    var _t0_pagerank_update = perf_counter_ns()
    for _ in range(N):
        _acc_pagerank_update += pagerank_update(0.5, 0.5, 0.5, 0.5)
    var _t1_pagerank_update = perf_counter_ns()
    var _ns_pagerank_update = Float64(_t1_pagerank_update - _t0_pagerank_update) / Float64(N)
    print("MOJO_TIMING graph_algorithms::pagerank_update", _ns_pagerank_update, _acc_pagerank_update)
    var _acc_betweenness_centrality_norm: Float64 = 0.0
    var _t0_betweenness_centrality_norm = perf_counter_ns()
    for _ in range(N):
        _acc_betweenness_centrality_norm += betweenness_centrality_norm(0.5, 0.5, 0.5)
    var _t1_betweenness_centrality_norm = perf_counter_ns()
    var _ns_betweenness_centrality_norm = Float64(_t1_betweenness_centrality_norm - _t0_betweenness_centrality_norm) / Float64(N)
    print("MOJO_TIMING graph_algorithms::betweenness_centrality_norm", _ns_betweenness_centrality_norm, _acc_betweenness_centrality_norm)
    var _acc_clustering_coefficient: Float64 = 0.0
    var _t0_clustering_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_clustering_coefficient += clustering_coefficient(0.5, 0.5)
    var _t1_clustering_coefficient = perf_counter_ns()
    var _ns_clustering_coefficient = Float64(_t1_clustering_coefficient - _t0_clustering_coefficient) / Float64(N)
    print("MOJO_TIMING graph_algorithms::clustering_coefficient", _ns_clustering_coefficient, _acc_clustering_coefficient)
    var _acc_degree_centrality: Float64 = 0.0
    var _t0_degree_centrality = perf_counter_ns()
    for _ in range(N):
        _acc_degree_centrality += degree_centrality(0.5, 0.5)
    var _t1_degree_centrality = perf_counter_ns()
    var _ns_degree_centrality = Float64(_t1_degree_centrality - _t0_degree_centrality) / Float64(N)
    print("MOJO_TIMING graph_algorithms::degree_centrality", _ns_degree_centrality, _acc_degree_centrality)
    var _acc_closeness_centrality: Float64 = 0.0
    var _t0_closeness_centrality = perf_counter_ns()
    for _ in range(N):
        _acc_closeness_centrality += closeness_centrality(0.5, 0.5)
    var _t1_closeness_centrality = perf_counter_ns()
    var _ns_closeness_centrality = Float64(_t1_closeness_centrality - _t0_closeness_centrality) / Float64(N)
    print("MOJO_TIMING graph_algorithms::closeness_centrality", _ns_closeness_centrality, _acc_closeness_centrality)
    var _acc_eigenvector_centrality_update: Float64 = 0.0
    var _t0_eigenvector_centrality_update = perf_counter_ns()
    for _ in range(N):
        _acc_eigenvector_centrality_update += eigenvector_centrality_update(0.5, 0.5)
    var _t1_eigenvector_centrality_update = perf_counter_ns()
    var _ns_eigenvector_centrality_update = Float64(_t1_eigenvector_centrality_update - _t0_eigenvector_centrality_update) / Float64(N)
    print("MOJO_TIMING graph_algorithms::eigenvector_centrality_update", _ns_eigenvector_centrality_update, _acc_eigenvector_centrality_update)
    var _acc_modularity_contribution: Float64 = 0.0
    var _t0_modularity_contribution = perf_counter_ns()
    for _ in range(N):
        _acc_modularity_contribution += modularity_contribution(0.5, 0.5, 0.5, 0.5)
    var _t1_modularity_contribution = perf_counter_ns()
    var _ns_modularity_contribution = Float64(_t1_modularity_contribution - _t0_modularity_contribution) / Float64(N)
    print("MOJO_TIMING graph_algorithms::modularity_contribution", _ns_modularity_contribution, _acc_modularity_contribution)
    var _acc_graph_density: Float64 = 0.0
    var _t0_graph_density = perf_counter_ns()
    for _ in range(N):
        _acc_graph_density += graph_density(0.5, 0.5, 0.5)
    var _t1_graph_density = perf_counter_ns()
    var _ns_graph_density = Float64(_t1_graph_density - _t0_graph_density) / Float64(N)
    print("MOJO_TIMING graph_algorithms::graph_density", _ns_graph_density, _acc_graph_density)
