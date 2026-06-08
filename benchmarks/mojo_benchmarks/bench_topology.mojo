"""bench_topology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from topology import distance_matrix, vietoris_rips_edges, connected_components_from_edges, betti_0, filtration_values, persistence_diagram_0, total_persistence, bottleneck_distance, euler_characteristic, rips_triangle_count
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

    var _acc_distance_matrix: Float64 = 0.0
    var _t0_distance_matrix = perf_counter_ns()
    for _ in range(N):
        var _r_distance_matrix = distance_matrix([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_distance_matrix += Float64(len(_r_distance_matrix))
    var _t1_distance_matrix = perf_counter_ns()
    var _ns_distance_matrix = Float64(_t1_distance_matrix - _t0_distance_matrix) / Float64(N)
    print("MOJO_TIMING topology::distance_matrix", _ns_distance_matrix, _acc_distance_matrix)
    var _result_distance_matrix = distance_matrix([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_distance_matrix = _summary_list_list_float64(_result_distance_matrix)
    print("MOJO_RESULT topology::distance_matrix", _summary_distance_matrix)
    var _acc_vietoris_rips_edges: Float64 = 0.0
    var _t0_vietoris_rips_edges = perf_counter_ns()
    for _ in range(N):
        var _r_vietoris_rips_edges = vietoris_rips_edges([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
        _acc_vietoris_rips_edges += Float64(len(_r_vietoris_rips_edges))
    var _t1_vietoris_rips_edges = perf_counter_ns()
    var _ns_vietoris_rips_edges = Float64(_t1_vietoris_rips_edges - _t0_vietoris_rips_edges) / Float64(N)
    print("MOJO_TIMING topology::vietoris_rips_edges", _ns_vietoris_rips_edges, _acc_vietoris_rips_edges)
    var _result_vietoris_rips_edges = vietoris_rips_edges([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
    var _summary_vietoris_rips_edges = _summary_list_list_int(_result_vietoris_rips_edges)
    print("MOJO_RESULT topology::vietoris_rips_edges", _summary_vietoris_rips_edges)
    var _acc_connected_components_from_edges: Float64 = 0.0
    var _t0_connected_components_from_edges = perf_counter_ns()
    for _ in range(N):
        _acc_connected_components_from_edges += Float64(connected_components_from_edges(5, [[0,1,1],[1,0,1],[1,1,0]]))
    var _t1_connected_components_from_edges = perf_counter_ns()
    var _ns_connected_components_from_edges = Float64(_t1_connected_components_from_edges - _t0_connected_components_from_edges) / Float64(N)
    print("MOJO_TIMING topology::connected_components_from_edges", _ns_connected_components_from_edges, _acc_connected_components_from_edges)
    var _result_connected_components_from_edges = connected_components_from_edges(5, [[0,1,1],[1,0,1],[1,1,0]])
    var _summary_connected_components_from_edges = _summary_int(_result_connected_components_from_edges)
    print("MOJO_RESULT topology::connected_components_from_edges", _summary_connected_components_from_edges)
    var _acc_betti_0: Float64 = 0.0
    var _t0_betti_0 = perf_counter_ns()
    for _ in range(N):
        _acc_betti_0 += Float64(betti_0(5, [[0,1,1],[1,0,1],[1,1,0]]))
    var _t1_betti_0 = perf_counter_ns()
    var _ns_betti_0 = Float64(_t1_betti_0 - _t0_betti_0) / Float64(N)
    print("MOJO_TIMING topology::betti_0", _ns_betti_0, _acc_betti_0)
    var _result_betti_0 = betti_0(5, [[0,1,1],[1,0,1],[1,1,0]])
    var _summary_betti_0 = _summary_int(_result_betti_0)
    print("MOJO_RESULT topology::betti_0", _summary_betti_0)
    var _acc_filtration_values: Float64 = 0.0
    var _t0_filtration_values = perf_counter_ns()
    for _ in range(N):
        var _r_filtration_values = filtration_values([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_filtration_values += Float64(len(_r_filtration_values))
    var _t1_filtration_values = perf_counter_ns()
    var _ns_filtration_values = Float64(_t1_filtration_values - _t0_filtration_values) / Float64(N)
    print("MOJO_TIMING topology::filtration_values", _ns_filtration_values, _acc_filtration_values)
    var _result_filtration_values = filtration_values([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_filtration_values = _summary_list_float64(_result_filtration_values)
    print("MOJO_RESULT topology::filtration_values", _summary_filtration_values)
    var _acc_persistence_diagram_0: Float64 = 0.0
    var _t0_persistence_diagram_0 = perf_counter_ns()
    for _ in range(N):
        var _r_persistence_diagram_0 = persistence_diagram_0([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_persistence_diagram_0 += Float64(len(_r_persistence_diagram_0))
    var _t1_persistence_diagram_0 = perf_counter_ns()
    var _ns_persistence_diagram_0 = Float64(_t1_persistence_diagram_0 - _t0_persistence_diagram_0) / Float64(N)
    print("MOJO_TIMING topology::persistence_diagram_0", _ns_persistence_diagram_0, _acc_persistence_diagram_0)
    var _result_persistence_diagram_0 = persistence_diagram_0([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_persistence_diagram_0 = _summary_list_list_float64(_result_persistence_diagram_0)
    print("MOJO_RESULT topology::persistence_diagram_0", _summary_persistence_diagram_0)
    var _acc_total_persistence: Float64 = 0.0
    var _t0_total_persistence = perf_counter_ns()
    for _ in range(N):
        _acc_total_persistence += total_persistence([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_total_persistence = perf_counter_ns()
    var _ns_total_persistence = Float64(_t1_total_persistence - _t0_total_persistence) / Float64(N)
    print("MOJO_TIMING topology::total_persistence", _ns_total_persistence, _acc_total_persistence)
    var _result_total_persistence = total_persistence([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_total_persistence = _summary_float64(_result_total_persistence)
    print("MOJO_RESULT topology::total_persistence", _summary_total_persistence)
    var _acc_bottleneck_distance: Float64 = 0.0
    var _t0_bottleneck_distance = perf_counter_ns()
    for _ in range(N):
        _acc_bottleneck_distance += bottleneck_distance([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_bottleneck_distance = perf_counter_ns()
    var _ns_bottleneck_distance = Float64(_t1_bottleneck_distance - _t0_bottleneck_distance) / Float64(N)
    print("MOJO_TIMING topology::bottleneck_distance", _ns_bottleneck_distance, _acc_bottleneck_distance)
    var _result_bottleneck_distance = bottleneck_distance([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_bottleneck_distance = _summary_float64(_result_bottleneck_distance)
    print("MOJO_RESULT topology::bottleneck_distance", _summary_bottleneck_distance)
    var _acc_euler_characteristic: Float64 = 0.0
    var _t0_euler_characteristic = perf_counter_ns()
    for _ in range(N):
        _acc_euler_characteristic += Float64(euler_characteristic(5, 5, 5))
    var _t1_euler_characteristic = perf_counter_ns()
    var _ns_euler_characteristic = Float64(_t1_euler_characteristic - _t0_euler_characteristic) / Float64(N)
    print("MOJO_TIMING topology::euler_characteristic", _ns_euler_characteristic, _acc_euler_characteristic)
    var _result_euler_characteristic = euler_characteristic(5, 5, 5)
    var _summary_euler_characteristic = _summary_int(_result_euler_characteristic)
    print("MOJO_RESULT topology::euler_characteristic", _summary_euler_characteristic)
    var _acc_rips_triangle_count: Float64 = 0.0
    var _t0_rips_triangle_count = perf_counter_ns()
    for _ in range(N):
        _acc_rips_triangle_count += Float64(rips_triangle_count(5, [[0,1,1],[1,0,1],[1,1,0]]))
    var _t1_rips_triangle_count = perf_counter_ns()
    var _ns_rips_triangle_count = Float64(_t1_rips_triangle_count - _t0_rips_triangle_count) / Float64(N)
    print("MOJO_TIMING topology::rips_triangle_count", _ns_rips_triangle_count, _acc_rips_triangle_count)
    var _result_rips_triangle_count = rips_triangle_count(5, [[0,1,1],[1,0,1],[1,1,0]])
    var _summary_rips_triangle_count = _summary_int(_result_rips_triangle_count)
    print("MOJO_RESULT topology::rips_triangle_count", _summary_rips_triangle_count)
