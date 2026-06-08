"""bench_fire_safety.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from fire_safety import fire_load_density, heat_release_rate, flashover_mfo, sprinkler_activation_time, smoke_layer_height, evacuation_time, safe_egress_time, fire_resistance_rating, ventilation_factor, fire_severity, co_concentration_danger, occupant_load
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

    var _acc_fire_load_density: Float64 = 0.0
    var _t0_fire_load_density = perf_counter_ns()
    for _ in range(N):
        _acc_fire_load_density += fire_load_density(0.5, 0.5)
    var _t1_fire_load_density = perf_counter_ns()
    var _ns_fire_load_density = Float64(_t1_fire_load_density - _t0_fire_load_density) / Float64(N)
    print("MOJO_TIMING fire_safety::fire_load_density", _ns_fire_load_density, _acc_fire_load_density)
    var _result_fire_load_density = fire_load_density(0.5, 0.5)
    var _summary_fire_load_density = _summary_float64(_result_fire_load_density)
    print("MOJO_RESULT fire_safety::fire_load_density", _summary_fire_load_density)
    var _acc_heat_release_rate: Float64 = 0.0
    var _t0_heat_release_rate = perf_counter_ns()
    for _ in range(N):
        _acc_heat_release_rate += heat_release_rate(0.5, 0.5)
    var _t1_heat_release_rate = perf_counter_ns()
    var _ns_heat_release_rate = Float64(_t1_heat_release_rate - _t0_heat_release_rate) / Float64(N)
    print("MOJO_TIMING fire_safety::heat_release_rate", _ns_heat_release_rate, _acc_heat_release_rate)
    var _result_heat_release_rate = heat_release_rate(0.5, 0.5)
    var _summary_heat_release_rate = _summary_float64(_result_heat_release_rate)
    print("MOJO_RESULT fire_safety::heat_release_rate", _summary_heat_release_rate)
    var _acc_flashover_mfo: Float64 = 0.0
    var _t0_flashover_mfo = perf_counter_ns()
    for _ in range(N):
        _acc_flashover_mfo += flashover_mfo(0.5, 0.5, 0.5)
    var _t1_flashover_mfo = perf_counter_ns()
    var _ns_flashover_mfo = Float64(_t1_flashover_mfo - _t0_flashover_mfo) / Float64(N)
    print("MOJO_TIMING fire_safety::flashover_mfo", _ns_flashover_mfo, _acc_flashover_mfo)
    var _result_flashover_mfo = flashover_mfo(0.5, 0.5, 0.5)
    var _summary_flashover_mfo = _summary_float64(_result_flashover_mfo)
    print("MOJO_RESULT fire_safety::flashover_mfo", _summary_flashover_mfo)
    var _acc_sprinkler_activation_time: Float64 = 0.0
    var _t0_sprinkler_activation_time = perf_counter_ns()
    for _ in range(N):
        _acc_sprinkler_activation_time += sprinkler_activation_time(0.5, 0.5, 0.5, 0.5)
    var _t1_sprinkler_activation_time = perf_counter_ns()
    var _ns_sprinkler_activation_time = Float64(_t1_sprinkler_activation_time - _t0_sprinkler_activation_time) / Float64(N)
    print("MOJO_TIMING fire_safety::sprinkler_activation_time", _ns_sprinkler_activation_time, _acc_sprinkler_activation_time)
    var _result_sprinkler_activation_time = sprinkler_activation_time(0.5, 0.5, 0.5, 0.5)
    var _summary_sprinkler_activation_time = _summary_float64(_result_sprinkler_activation_time)
    print("MOJO_RESULT fire_safety::sprinkler_activation_time", _summary_sprinkler_activation_time)
    var _acc_smoke_layer_height: Float64 = 0.0
    var _t0_smoke_layer_height = perf_counter_ns()
    for _ in range(N):
        _acc_smoke_layer_height += smoke_layer_height(0.5, 0.5, 0.5)
    var _t1_smoke_layer_height = perf_counter_ns()
    var _ns_smoke_layer_height = Float64(_t1_smoke_layer_height - _t0_smoke_layer_height) / Float64(N)
    print("MOJO_TIMING fire_safety::smoke_layer_height", _ns_smoke_layer_height, _acc_smoke_layer_height)
    var _result_smoke_layer_height = smoke_layer_height(0.5, 0.5, 0.5)
    var _summary_smoke_layer_height = _summary_float64(_result_smoke_layer_height)
    print("MOJO_RESULT fire_safety::smoke_layer_height", _summary_smoke_layer_height)
    var _acc_evacuation_time: Float64 = 0.0
    var _t0_evacuation_time = perf_counter_ns()
    for _ in range(N):
        _acc_evacuation_time += evacuation_time(0.5, 0.5, 0.5)
    var _t1_evacuation_time = perf_counter_ns()
    var _ns_evacuation_time = Float64(_t1_evacuation_time - _t0_evacuation_time) / Float64(N)
    print("MOJO_TIMING fire_safety::evacuation_time", _ns_evacuation_time, _acc_evacuation_time)
    var _result_evacuation_time = evacuation_time(0.5, 0.5, 0.5)
    var _summary_evacuation_time = _summary_float64(_result_evacuation_time)
    print("MOJO_RESULT fire_safety::evacuation_time", _summary_evacuation_time)
    var _acc_safe_egress_time: Float64 = 0.0
    var _t0_safe_egress_time = perf_counter_ns()
    for _ in range(N):
        _acc_safe_egress_time += safe_egress_time(0.5, 0.5, 0.5, 0.5)
    var _t1_safe_egress_time = perf_counter_ns()
    var _ns_safe_egress_time = Float64(_t1_safe_egress_time - _t0_safe_egress_time) / Float64(N)
    print("MOJO_TIMING fire_safety::safe_egress_time", _ns_safe_egress_time, _acc_safe_egress_time)
    var _result_safe_egress_time = safe_egress_time(0.5, 0.5, 0.5, 0.5)
    var _summary_safe_egress_time = _summary_float64(_result_safe_egress_time)
    print("MOJO_RESULT fire_safety::safe_egress_time", _summary_safe_egress_time)
    var _acc_fire_resistance_rating: Float64 = 0.0
    var _t0_fire_resistance_rating = perf_counter_ns()
    for _ in range(N):
        _acc_fire_resistance_rating += fire_resistance_rating(0.5, 0.5)
    var _t1_fire_resistance_rating = perf_counter_ns()
    var _ns_fire_resistance_rating = Float64(_t1_fire_resistance_rating - _t0_fire_resistance_rating) / Float64(N)
    print("MOJO_TIMING fire_safety::fire_resistance_rating", _ns_fire_resistance_rating, _acc_fire_resistance_rating)
    var _result_fire_resistance_rating = fire_resistance_rating(0.5, 0.5)
    var _summary_fire_resistance_rating = _summary_float64(_result_fire_resistance_rating)
    print("MOJO_RESULT fire_safety::fire_resistance_rating", _summary_fire_resistance_rating)
    var _acc_ventilation_factor: Float64 = 0.0
    var _t0_ventilation_factor = perf_counter_ns()
    for _ in range(N):
        _acc_ventilation_factor += ventilation_factor(0.5, 0.5)
    var _t1_ventilation_factor = perf_counter_ns()
    var _ns_ventilation_factor = Float64(_t1_ventilation_factor - _t0_ventilation_factor) / Float64(N)
    print("MOJO_TIMING fire_safety::ventilation_factor", _ns_ventilation_factor, _acc_ventilation_factor)
    var _result_ventilation_factor = ventilation_factor(0.5, 0.5)
    var _summary_ventilation_factor = _summary_float64(_result_ventilation_factor)
    print("MOJO_RESULT fire_safety::ventilation_factor", _summary_ventilation_factor)
    var _acc_fire_severity: Float64 = 0.0
    var _t0_fire_severity = perf_counter_ns()
    for _ in range(N):
        _acc_fire_severity += fire_severity(0.5, 0.5)
    var _t1_fire_severity = perf_counter_ns()
    var _ns_fire_severity = Float64(_t1_fire_severity - _t0_fire_severity) / Float64(N)
    print("MOJO_TIMING fire_safety::fire_severity", _ns_fire_severity, _acc_fire_severity)
    var _result_fire_severity = fire_severity(0.5, 0.5)
    var _summary_fire_severity = _summary_float64(_result_fire_severity)
    print("MOJO_RESULT fire_safety::fire_severity", _summary_fire_severity)
    var _acc_co_concentration_danger: Float64 = 0.0
    var _t0_co_concentration_danger = perf_counter_ns()
    for _ in range(N):
        _acc_co_concentration_danger += Float64(co_concentration_danger(0.5))
    var _t1_co_concentration_danger = perf_counter_ns()
    var _ns_co_concentration_danger = Float64(_t1_co_concentration_danger - _t0_co_concentration_danger) / Float64(N)
    print("MOJO_TIMING fire_safety::co_concentration_danger", _ns_co_concentration_danger, _acc_co_concentration_danger)
    var _result_co_concentration_danger = co_concentration_danger(0.5)
    var _summary_co_concentration_danger = _summary_int(_result_co_concentration_danger)
    print("MOJO_RESULT fire_safety::co_concentration_danger", _summary_co_concentration_danger)
    var _acc_occupant_load: Float64 = 0.0
    var _t0_occupant_load = perf_counter_ns()
    for _ in range(N):
        _acc_occupant_load += occupant_load(0.5, 0.5)
    var _t1_occupant_load = perf_counter_ns()
    var _ns_occupant_load = Float64(_t1_occupant_load - _t0_occupant_load) / Float64(N)
    print("MOJO_TIMING fire_safety::occupant_load", _ns_occupant_load, _acc_occupant_load)
    var _result_occupant_load = occupant_load(0.5, 0.5)
    var _summary_occupant_load = _summary_float64(_result_occupant_load)
    print("MOJO_RESULT fire_safety::occupant_load", _summary_occupant_load)
