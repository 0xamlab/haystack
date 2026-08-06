"""bench_rubber.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from rubber import shore_a_to_youngs_modulus, mooney_viscosity_index, tensile_set, compression_set, elongation_at_break, tear_strength, resilience_rebound, hardness_change_aging, swelling_percentage, crosslink_density_estimate, abrasion_loss_volume, heat_buildup
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

    var _acc_shore_a_to_youngs_modulus: Float64 = 0.0
    var _t0_shore_a_to_youngs_modulus = perf_counter_ns()
    for _ in range(N):
        _acc_shore_a_to_youngs_modulus += shore_a_to_youngs_modulus(0.5)
    var _t1_shore_a_to_youngs_modulus = perf_counter_ns()
    var _ns_shore_a_to_youngs_modulus = Float64(_t1_shore_a_to_youngs_modulus - _t0_shore_a_to_youngs_modulus) / Float64(N)
    print("MOJO_TIMING rubber::shore_a_to_youngs_modulus", _ns_shore_a_to_youngs_modulus, _acc_shore_a_to_youngs_modulus)
    var _result_shore_a_to_youngs_modulus = shore_a_to_youngs_modulus(0.5)
    var _summary_shore_a_to_youngs_modulus = _summary_float64(_result_shore_a_to_youngs_modulus)
    print("MOJO_RESULT rubber::shore_a_to_youngs_modulus", _summary_shore_a_to_youngs_modulus)
    var _acc_mooney_viscosity_index: Float64 = 0.0
    var _t0_mooney_viscosity_index = perf_counter_ns()
    for _ in range(N):
        _acc_mooney_viscosity_index += mooney_viscosity_index(0.5, 0.5)
    var _t1_mooney_viscosity_index = perf_counter_ns()
    var _ns_mooney_viscosity_index = Float64(_t1_mooney_viscosity_index - _t0_mooney_viscosity_index) / Float64(N)
    print("MOJO_TIMING rubber::mooney_viscosity_index", _ns_mooney_viscosity_index, _acc_mooney_viscosity_index)
    var _result_mooney_viscosity_index = mooney_viscosity_index(0.5, 0.5)
    var _summary_mooney_viscosity_index = _summary_float64(_result_mooney_viscosity_index)
    print("MOJO_RESULT rubber::mooney_viscosity_index", _summary_mooney_viscosity_index)
    var _acc_tensile_set: Float64 = 0.0
    var _t0_tensile_set = perf_counter_ns()
    for _ in range(N):
        _acc_tensile_set += tensile_set(0.5, 0.5, 0.5)
    var _t1_tensile_set = perf_counter_ns()
    var _ns_tensile_set = Float64(_t1_tensile_set - _t0_tensile_set) / Float64(N)
    print("MOJO_TIMING rubber::tensile_set", _ns_tensile_set, _acc_tensile_set)
    var _result_tensile_set = tensile_set(0.5, 0.5, 0.5)
    var _summary_tensile_set = _summary_float64(_result_tensile_set)
    print("MOJO_RESULT rubber::tensile_set", _summary_tensile_set)
    var _acc_compression_set: Float64 = 0.0
    var _t0_compression_set = perf_counter_ns()
    for _ in range(N):
        _acc_compression_set += compression_set(0.5, 0.5, 0.5)
    var _t1_compression_set = perf_counter_ns()
    var _ns_compression_set = Float64(_t1_compression_set - _t0_compression_set) / Float64(N)
    print("MOJO_TIMING rubber::compression_set", _ns_compression_set, _acc_compression_set)
    var _result_compression_set = compression_set(0.5, 0.5, 0.5)
    var _summary_compression_set = _summary_float64(_result_compression_set)
    print("MOJO_RESULT rubber::compression_set", _summary_compression_set)
    var _acc_elongation_at_break: Float64 = 0.0
    var _t0_elongation_at_break = perf_counter_ns()
    for _ in range(N):
        _acc_elongation_at_break += elongation_at_break(0.5, 0.5)
    var _t1_elongation_at_break = perf_counter_ns()
    var _ns_elongation_at_break = Float64(_t1_elongation_at_break - _t0_elongation_at_break) / Float64(N)
    print("MOJO_TIMING rubber::elongation_at_break", _ns_elongation_at_break, _acc_elongation_at_break)
    var _result_elongation_at_break = elongation_at_break(0.5, 0.5)
    var _summary_elongation_at_break = _summary_float64(_result_elongation_at_break)
    print("MOJO_RESULT rubber::elongation_at_break", _summary_elongation_at_break)
    var _acc_tear_strength: Float64 = 0.0
    var _t0_tear_strength = perf_counter_ns()
    for _ in range(N):
        _acc_tear_strength += tear_strength(0.5, 0.5)
    var _t1_tear_strength = perf_counter_ns()
    var _ns_tear_strength = Float64(_t1_tear_strength - _t0_tear_strength) / Float64(N)
    print("MOJO_TIMING rubber::tear_strength", _ns_tear_strength, _acc_tear_strength)
    var _result_tear_strength = tear_strength(0.5, 0.5)
    var _summary_tear_strength = _summary_float64(_result_tear_strength)
    print("MOJO_RESULT rubber::tear_strength", _summary_tear_strength)
    var _acc_resilience_rebound: Float64 = 0.0
    var _t0_resilience_rebound = perf_counter_ns()
    for _ in range(N):
        _acc_resilience_rebound += resilience_rebound(0.5, 0.5)
    var _t1_resilience_rebound = perf_counter_ns()
    var _ns_resilience_rebound = Float64(_t1_resilience_rebound - _t0_resilience_rebound) / Float64(N)
    print("MOJO_TIMING rubber::resilience_rebound", _ns_resilience_rebound, _acc_resilience_rebound)
    var _result_resilience_rebound = resilience_rebound(0.5, 0.5)
    var _summary_resilience_rebound = _summary_float64(_result_resilience_rebound)
    print("MOJO_RESULT rubber::resilience_rebound", _summary_resilience_rebound)
    var _acc_hardness_change_aging: Float64 = 0.0
    var _t0_hardness_change_aging = perf_counter_ns()
    for _ in range(N):
        _acc_hardness_change_aging += hardness_change_aging(0.5, 0.5)
    var _t1_hardness_change_aging = perf_counter_ns()
    var _ns_hardness_change_aging = Float64(_t1_hardness_change_aging - _t0_hardness_change_aging) / Float64(N)
    print("MOJO_TIMING rubber::hardness_change_aging", _ns_hardness_change_aging, _acc_hardness_change_aging)
    var _result_hardness_change_aging = hardness_change_aging(0.5, 0.5)
    var _summary_hardness_change_aging = _summary_float64(_result_hardness_change_aging)
    print("MOJO_RESULT rubber::hardness_change_aging", _summary_hardness_change_aging)
    var _acc_swelling_percentage: Float64 = 0.0
    var _t0_swelling_percentage = perf_counter_ns()
    for _ in range(N):
        _acc_swelling_percentage += swelling_percentage(0.5, 0.5)
    var _t1_swelling_percentage = perf_counter_ns()
    var _ns_swelling_percentage = Float64(_t1_swelling_percentage - _t0_swelling_percentage) / Float64(N)
    print("MOJO_TIMING rubber::swelling_percentage", _ns_swelling_percentage, _acc_swelling_percentage)
    var _result_swelling_percentage = swelling_percentage(0.5, 0.5)
    var _summary_swelling_percentage = _summary_float64(_result_swelling_percentage)
    print("MOJO_RESULT rubber::swelling_percentage", _summary_swelling_percentage)
    var _acc_crosslink_density_estimate: Float64 = 0.0
    var _t0_crosslink_density_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_crosslink_density_estimate += crosslink_density_estimate(0.5, 0.5, 0.5)
    var _t1_crosslink_density_estimate = perf_counter_ns()
    var _ns_crosslink_density_estimate = Float64(_t1_crosslink_density_estimate - _t0_crosslink_density_estimate) / Float64(N)
    print("MOJO_TIMING rubber::crosslink_density_estimate", _ns_crosslink_density_estimate, _acc_crosslink_density_estimate)
    var _result_crosslink_density_estimate = crosslink_density_estimate(0.5, 0.5, 0.5)
    var _summary_crosslink_density_estimate = _summary_float64(_result_crosslink_density_estimate)
    print("MOJO_RESULT rubber::crosslink_density_estimate", _summary_crosslink_density_estimate)
    var _acc_abrasion_loss_volume: Float64 = 0.0
    var _t0_abrasion_loss_volume = perf_counter_ns()
    for _ in range(N):
        _acc_abrasion_loss_volume += abrasion_loss_volume(0.5, 0.5)
    var _t1_abrasion_loss_volume = perf_counter_ns()
    var _ns_abrasion_loss_volume = Float64(_t1_abrasion_loss_volume - _t0_abrasion_loss_volume) / Float64(N)
    print("MOJO_TIMING rubber::abrasion_loss_volume", _ns_abrasion_loss_volume, _acc_abrasion_loss_volume)
    var _result_abrasion_loss_volume = abrasion_loss_volume(0.5, 0.5)
    var _summary_abrasion_loss_volume = _summary_float64(_result_abrasion_loss_volume)
    print("MOJO_RESULT rubber::abrasion_loss_volume", _summary_abrasion_loss_volume)
    var _acc_heat_buildup: Float64 = 0.0
    var _t0_heat_buildup = perf_counter_ns()
    for _ in range(N):
        _acc_heat_buildup += heat_buildup(0.5, 0.5, 0.5)
    var _t1_heat_buildup = perf_counter_ns()
    var _ns_heat_buildup = Float64(_t1_heat_buildup - _t0_heat_buildup) / Float64(N)
    print("MOJO_TIMING rubber::heat_buildup", _ns_heat_buildup, _acc_heat_buildup)
    var _result_heat_buildup = heat_buildup(0.5, 0.5, 0.5)
    var _summary_heat_buildup = _summary_float64(_result_heat_buildup)
    print("MOJO_RESULT rubber::heat_buildup", _summary_heat_buildup)
