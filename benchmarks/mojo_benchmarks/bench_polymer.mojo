"""bench_polymer.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from polymer import degree_of_polymerization, number_average_mw, weight_average_mw, polydispersity_index, mark_houwink, glass_transition_fox, flory_huggins_free_energy, end_to_end_distance, radius_of_gyration, carothers_conversion, melt_flow_index_approx, tensile_modulus_rule_of_mixtures
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

    var _acc_degree_of_polymerization: Float64 = 0.0
    var _t0_degree_of_polymerization = perf_counter_ns()
    for _ in range(N):
        _acc_degree_of_polymerization += degree_of_polymerization(0.5, 0.5)
    var _t1_degree_of_polymerization = perf_counter_ns()
    var _ns_degree_of_polymerization = Float64(_t1_degree_of_polymerization - _t0_degree_of_polymerization) / Float64(N)
    print("MOJO_TIMING polymer::degree_of_polymerization", _ns_degree_of_polymerization, _acc_degree_of_polymerization)
    var _result_degree_of_polymerization = degree_of_polymerization(0.5, 0.5)
    var _summary_degree_of_polymerization = _summary_float64(_result_degree_of_polymerization)
    print("MOJO_RESULT polymer::degree_of_polymerization", _summary_degree_of_polymerization)
    var _acc_number_average_mw: Float64 = 0.0
    var _t0_number_average_mw = perf_counter_ns()
    for _ in range(N):
        _acc_number_average_mw += number_average_mw(0.5, 0.5)
    var _t1_number_average_mw = perf_counter_ns()
    var _ns_number_average_mw = Float64(_t1_number_average_mw - _t0_number_average_mw) / Float64(N)
    print("MOJO_TIMING polymer::number_average_mw", _ns_number_average_mw, _acc_number_average_mw)
    var _result_number_average_mw = number_average_mw(0.5, 0.5)
    var _summary_number_average_mw = _summary_float64(_result_number_average_mw)
    print("MOJO_RESULT polymer::number_average_mw", _summary_number_average_mw)
    var _acc_weight_average_mw: Float64 = 0.0
    var _t0_weight_average_mw = perf_counter_ns()
    for _ in range(N):
        _acc_weight_average_mw += weight_average_mw(0.5, 0.5)
    var _t1_weight_average_mw = perf_counter_ns()
    var _ns_weight_average_mw = Float64(_t1_weight_average_mw - _t0_weight_average_mw) / Float64(N)
    print("MOJO_TIMING polymer::weight_average_mw", _ns_weight_average_mw, _acc_weight_average_mw)
    var _result_weight_average_mw = weight_average_mw(0.5, 0.5)
    var _summary_weight_average_mw = _summary_float64(_result_weight_average_mw)
    print("MOJO_RESULT polymer::weight_average_mw", _summary_weight_average_mw)
    var _acc_polydispersity_index: Float64 = 0.0
    var _t0_polydispersity_index = perf_counter_ns()
    for _ in range(N):
        _acc_polydispersity_index += polydispersity_index(0.5, 0.5)
    var _t1_polydispersity_index = perf_counter_ns()
    var _ns_polydispersity_index = Float64(_t1_polydispersity_index - _t0_polydispersity_index) / Float64(N)
    print("MOJO_TIMING polymer::polydispersity_index", _ns_polydispersity_index, _acc_polydispersity_index)
    var _result_polydispersity_index = polydispersity_index(0.5, 0.5)
    var _summary_polydispersity_index = _summary_float64(_result_polydispersity_index)
    print("MOJO_RESULT polymer::polydispersity_index", _summary_polydispersity_index)
    var _acc_mark_houwink: Float64 = 0.0
    var _t0_mark_houwink = perf_counter_ns()
    for _ in range(N):
        _acc_mark_houwink += mark_houwink(0.5, 0.5, 0.5)
    var _t1_mark_houwink = perf_counter_ns()
    var _ns_mark_houwink = Float64(_t1_mark_houwink - _t0_mark_houwink) / Float64(N)
    print("MOJO_TIMING polymer::mark_houwink", _ns_mark_houwink, _acc_mark_houwink)
    var _result_mark_houwink = mark_houwink(0.5, 0.5, 0.5)
    var _summary_mark_houwink = _summary_float64(_result_mark_houwink)
    print("MOJO_RESULT polymer::mark_houwink", _summary_mark_houwink)
    var _acc_glass_transition_fox: Float64 = 0.0
    var _t0_glass_transition_fox = perf_counter_ns()
    for _ in range(N):
        _acc_glass_transition_fox += glass_transition_fox(0.5, 0.5, 0.5, 0.5)
    var _t1_glass_transition_fox = perf_counter_ns()
    var _ns_glass_transition_fox = Float64(_t1_glass_transition_fox - _t0_glass_transition_fox) / Float64(N)
    print("MOJO_TIMING polymer::glass_transition_fox", _ns_glass_transition_fox, _acc_glass_transition_fox)
    var _result_glass_transition_fox = glass_transition_fox(0.5, 0.5, 0.5, 0.5)
    var _summary_glass_transition_fox = _summary_float64(_result_glass_transition_fox)
    print("MOJO_RESULT polymer::glass_transition_fox", _summary_glass_transition_fox)
    var _acc_flory_huggins_free_energy: Float64 = 0.0
    var _t0_flory_huggins_free_energy = perf_counter_ns()
    for _ in range(N):
        _acc_flory_huggins_free_energy += flory_huggins_free_energy(0.5, 0.5, 0.5)
    var _t1_flory_huggins_free_energy = perf_counter_ns()
    var _ns_flory_huggins_free_energy = Float64(_t1_flory_huggins_free_energy - _t0_flory_huggins_free_energy) / Float64(N)
    print("MOJO_TIMING polymer::flory_huggins_free_energy", _ns_flory_huggins_free_energy, _acc_flory_huggins_free_energy)
    var _result_flory_huggins_free_energy = flory_huggins_free_energy(0.5, 0.5, 0.5)
    var _summary_flory_huggins_free_energy = _summary_float64(_result_flory_huggins_free_energy)
    print("MOJO_RESULT polymer::flory_huggins_free_energy", _summary_flory_huggins_free_energy)
    var _acc_end_to_end_distance: Float64 = 0.0
    var _t0_end_to_end_distance = perf_counter_ns()
    for _ in range(N):
        _acc_end_to_end_distance += end_to_end_distance(0.5, 0.5)
    var _t1_end_to_end_distance = perf_counter_ns()
    var _ns_end_to_end_distance = Float64(_t1_end_to_end_distance - _t0_end_to_end_distance) / Float64(N)
    print("MOJO_TIMING polymer::end_to_end_distance", _ns_end_to_end_distance, _acc_end_to_end_distance)
    var _result_end_to_end_distance = end_to_end_distance(0.5, 0.5)
    var _summary_end_to_end_distance = _summary_float64(_result_end_to_end_distance)
    print("MOJO_RESULT polymer::end_to_end_distance", _summary_end_to_end_distance)
    var _acc_radius_of_gyration: Float64 = 0.0
    var _t0_radius_of_gyration = perf_counter_ns()
    for _ in range(N):
        _acc_radius_of_gyration += radius_of_gyration(0.5)
    var _t1_radius_of_gyration = perf_counter_ns()
    var _ns_radius_of_gyration = Float64(_t1_radius_of_gyration - _t0_radius_of_gyration) / Float64(N)
    print("MOJO_TIMING polymer::radius_of_gyration", _ns_radius_of_gyration, _acc_radius_of_gyration)
    var _result_radius_of_gyration = radius_of_gyration(0.5)
    var _summary_radius_of_gyration = _summary_float64(_result_radius_of_gyration)
    print("MOJO_RESULT polymer::radius_of_gyration", _summary_radius_of_gyration)
    var _acc_carothers_conversion: Float64 = 0.0
    var _t0_carothers_conversion = perf_counter_ns()
    for _ in range(N):
        _acc_carothers_conversion += carothers_conversion(0.5)
    var _t1_carothers_conversion = perf_counter_ns()
    var _ns_carothers_conversion = Float64(_t1_carothers_conversion - _t0_carothers_conversion) / Float64(N)
    print("MOJO_TIMING polymer::carothers_conversion", _ns_carothers_conversion, _acc_carothers_conversion)
    var _result_carothers_conversion = carothers_conversion(0.5)
    var _summary_carothers_conversion = _summary_float64(_result_carothers_conversion)
    print("MOJO_RESULT polymer::carothers_conversion", _summary_carothers_conversion)
    var _acc_melt_flow_index_approx: Float64 = 0.0
    var _t0_melt_flow_index_approx = perf_counter_ns()
    for _ in range(N):
        _acc_melt_flow_index_approx += melt_flow_index_approx(0.5, 0.5)
    var _t1_melt_flow_index_approx = perf_counter_ns()
    var _ns_melt_flow_index_approx = Float64(_t1_melt_flow_index_approx - _t0_melt_flow_index_approx) / Float64(N)
    print("MOJO_TIMING polymer::melt_flow_index_approx", _ns_melt_flow_index_approx, _acc_melt_flow_index_approx)
    var _result_melt_flow_index_approx = melt_flow_index_approx(0.5, 0.5)
    var _summary_melt_flow_index_approx = _summary_float64(_result_melt_flow_index_approx)
    print("MOJO_RESULT polymer::melt_flow_index_approx", _summary_melt_flow_index_approx)
    var _acc_tensile_modulus_rule_of_mixtures: Float64 = 0.0
    var _t0_tensile_modulus_rule_of_mixtures = perf_counter_ns()
    for _ in range(N):
        _acc_tensile_modulus_rule_of_mixtures += tensile_modulus_rule_of_mixtures(0.5, 0.5, 0.5)
    var _t1_tensile_modulus_rule_of_mixtures = perf_counter_ns()
    var _ns_tensile_modulus_rule_of_mixtures = Float64(_t1_tensile_modulus_rule_of_mixtures - _t0_tensile_modulus_rule_of_mixtures) / Float64(N)
    print("MOJO_TIMING polymer::tensile_modulus_rule_of_mixtures", _ns_tensile_modulus_rule_of_mixtures, _acc_tensile_modulus_rule_of_mixtures)
    var _result_tensile_modulus_rule_of_mixtures = tensile_modulus_rule_of_mixtures(0.5, 0.5, 0.5)
    var _summary_tensile_modulus_rule_of_mixtures = _summary_float64(_result_tensile_modulus_rule_of_mixtures)
    print("MOJO_RESULT polymer::tensile_modulus_rule_of_mixtures", _summary_tensile_modulus_rule_of_mixtures)
