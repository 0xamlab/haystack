"""bench_social_network.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from social_network import in_degree, out_degree, reciprocity, influence_spread_ic, local_clustering_directed, strongly_connected_check, community_label_propagation, network_density, average_path_length_estimate
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

    var _acc_in_degree: Float64 = 0.0
    var _t0_in_degree = perf_counter_ns()
    for _ in range(N):
        _acc_in_degree += Float64(in_degree([[0,1,1],[1,0,1],[1,1,0]], 5))
    var _t1_in_degree = perf_counter_ns()
    var _ns_in_degree = Float64(_t1_in_degree - _t0_in_degree) / Float64(N)
    print("MOJO_TIMING social_network::in_degree", _ns_in_degree, _acc_in_degree)
    var _result_in_degree = in_degree([[0,1,1],[1,0,1],[1,1,0]], 5)
    var _summary_in_degree = _summary_int(_result_in_degree)
    print("MOJO_RESULT social_network::in_degree", _summary_in_degree)
    var _acc_out_degree: Float64 = 0.0
    var _t0_out_degree = perf_counter_ns()
    for _ in range(N):
        _acc_out_degree += Float64(out_degree([[0,1,1],[1,0,1],[1,1,0]], 5))
    var _t1_out_degree = perf_counter_ns()
    var _ns_out_degree = Float64(_t1_out_degree - _t0_out_degree) / Float64(N)
    print("MOJO_TIMING social_network::out_degree", _ns_out_degree, _acc_out_degree)
    var _result_out_degree = out_degree([[0,1,1],[1,0,1],[1,1,0]], 5)
    var _summary_out_degree = _summary_int(_result_out_degree)
    print("MOJO_RESULT social_network::out_degree", _summary_out_degree)
    var _acc_reciprocity: Float64 = 0.0
    var _t0_reciprocity = perf_counter_ns()
    for _ in range(N):
        _acc_reciprocity += reciprocity([[0,1,1],[1,0,1],[1,1,0]])
    var _t1_reciprocity = perf_counter_ns()
    var _ns_reciprocity = Float64(_t1_reciprocity - _t0_reciprocity) / Float64(N)
    print("MOJO_TIMING social_network::reciprocity", _ns_reciprocity, _acc_reciprocity)
    var _result_reciprocity = reciprocity([[0,1,1],[1,0,1],[1,1,0]])
    var _summary_reciprocity = _summary_float64(_result_reciprocity)
    print("MOJO_RESULT social_network::reciprocity", _summary_reciprocity)
    var _acc_influence_spread_ic: Float64 = 0.0
    var _t0_influence_spread_ic = perf_counter_ns()
    for _ in range(N):
        _acc_influence_spread_ic += influence_spread_ic([[0,1,1],[1,0,1],[1,1,0]], _li5, 0.5, 5)
    var _t1_influence_spread_ic = perf_counter_ns()
    var _ns_influence_spread_ic = Float64(_t1_influence_spread_ic - _t0_influence_spread_ic) / Float64(N)
    print("MOJO_TIMING social_network::influence_spread_ic", _ns_influence_spread_ic, _acc_influence_spread_ic)
    var _result_influence_spread_ic = influence_spread_ic([[0,1,1],[1,0,1],[1,1,0]], _li5, 0.5, 5)
    var _summary_influence_spread_ic = _summary_float64(_result_influence_spread_ic)
    print("MOJO_RESULT social_network::influence_spread_ic", _summary_influence_spread_ic)
    var _acc_local_clustering_directed: Float64 = 0.0
    var _t0_local_clustering_directed = perf_counter_ns()
    for _ in range(N):
        _acc_local_clustering_directed += local_clustering_directed([[0,1,1],[1,0,1],[1,1,0]], 5)
    var _t1_local_clustering_directed = perf_counter_ns()
    var _ns_local_clustering_directed = Float64(_t1_local_clustering_directed - _t0_local_clustering_directed) / Float64(N)
    print("MOJO_TIMING social_network::local_clustering_directed", _ns_local_clustering_directed, _acc_local_clustering_directed)
    var _result_local_clustering_directed = local_clustering_directed([[0,1,1],[1,0,1],[1,1,0]], 5)
    var _summary_local_clustering_directed = _summary_float64(_result_local_clustering_directed)
    print("MOJO_RESULT social_network::local_clustering_directed", _summary_local_clustering_directed)
    var _acc_strongly_connected_check: Float64 = 0.0
    var _t0_strongly_connected_check = perf_counter_ns()
    for _ in range(N):
        _acc_strongly_connected_check += Float64(strongly_connected_check([[0,1,1],[1,0,1],[1,1,0]]))
    var _t1_strongly_connected_check = perf_counter_ns()
    var _ns_strongly_connected_check = Float64(_t1_strongly_connected_check - _t0_strongly_connected_check) / Float64(N)
    print("MOJO_TIMING social_network::strongly_connected_check", _ns_strongly_connected_check, _acc_strongly_connected_check)
    var _result_strongly_connected_check = strongly_connected_check([[0,1,1],[1,0,1],[1,1,0]])
    var _summary_strongly_connected_check = _summary_bool(_result_strongly_connected_check)
    print("MOJO_RESULT social_network::strongly_connected_check", _summary_strongly_connected_check)
    var _acc_community_label_propagation: Float64 = 0.0
    var _t0_community_label_propagation = perf_counter_ns()
    for _ in range(N):
        var _r_community_label_propagation = community_label_propagation([[0,1,1],[1,0,1],[1,1,0]], 5)
        _acc_community_label_propagation += Float64(len(_r_community_label_propagation))
    var _t1_community_label_propagation = perf_counter_ns()
    var _ns_community_label_propagation = Float64(_t1_community_label_propagation - _t0_community_label_propagation) / Float64(N)
    print("MOJO_TIMING social_network::community_label_propagation", _ns_community_label_propagation, _acc_community_label_propagation)
    var _result_community_label_propagation = community_label_propagation([[0,1,1],[1,0,1],[1,1,0]], 5)
    var _summary_community_label_propagation = _summary_list_int(_result_community_label_propagation)
    print("MOJO_RESULT social_network::community_label_propagation", _summary_community_label_propagation)
    var _acc_network_density: Float64 = 0.0
    var _t0_network_density = perf_counter_ns()
    for _ in range(N):
        _acc_network_density += network_density([[0,1,1],[1,0,1],[1,1,0]])
    var _t1_network_density = perf_counter_ns()
    var _ns_network_density = Float64(_t1_network_density - _t0_network_density) / Float64(N)
    print("MOJO_TIMING social_network::network_density", _ns_network_density, _acc_network_density)
    var _result_network_density = network_density([[0,1,1],[1,0,1],[1,1,0]])
    var _summary_network_density = _summary_float64(_result_network_density)
    print("MOJO_RESULT social_network::network_density", _summary_network_density)
    var _acc_average_path_length_estimate: Float64 = 0.0
    var _t0_average_path_length_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_average_path_length_estimate += average_path_length_estimate([[0,1,1],[1,0,1],[1,1,0]], 5)
    var _t1_average_path_length_estimate = perf_counter_ns()
    var _ns_average_path_length_estimate = Float64(_t1_average_path_length_estimate - _t0_average_path_length_estimate) / Float64(N)
    print("MOJO_TIMING social_network::average_path_length_estimate", _ns_average_path_length_estimate, _acc_average_path_length_estimate)
    var _result_average_path_length_estimate = average_path_length_estimate([[0,1,1],[1,0,1],[1,1,0]], 5)
    var _summary_average_path_length_estimate = _summary_float64(_result_average_path_length_estimate)
    print("MOJO_RESULT social_network::average_path_length_estimate", _summary_average_path_length_estimate)
