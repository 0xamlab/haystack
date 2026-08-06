"""bench_metallurgy.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from metallurgy import hall_petch, johnson_cook_flow_stress, hardness_to_tensile, carbon_equivalent, jominy_distance_to_hardness, avrami_fraction, quench_severity, tempering_parameter, density_of_alloy_rule_of_mixtures, thermal_conductivity_wiedemann_franz, strain_hardening_exponent_from_points, fatigue_life_basquin
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

    var _acc_hall_petch: Float64 = 0.0
    var _t0_hall_petch = perf_counter_ns()
    for _ in range(N):
        _acc_hall_petch += hall_petch(0.5, 0.5, 0.5)
    var _t1_hall_petch = perf_counter_ns()
    var _ns_hall_petch = Float64(_t1_hall_petch - _t0_hall_petch) / Float64(N)
    print("MOJO_TIMING metallurgy::hall_petch", _ns_hall_petch, _acc_hall_petch)
    var _result_hall_petch = hall_petch(0.5, 0.5, 0.5)
    var _summary_hall_petch = _summary_float64(_result_hall_petch)
    print("MOJO_RESULT metallurgy::hall_petch", _summary_hall_petch)
    var _acc_johnson_cook_flow_stress: Float64 = 0.0
    var _t0_johnson_cook_flow_stress = perf_counter_ns()
    for _ in range(N):
        _acc_johnson_cook_flow_stress += johnson_cook_flow_stress(0.5, 0.5, 0.5, 0.5)
    var _t1_johnson_cook_flow_stress = perf_counter_ns()
    var _ns_johnson_cook_flow_stress = Float64(_t1_johnson_cook_flow_stress - _t0_johnson_cook_flow_stress) / Float64(N)
    print("MOJO_TIMING metallurgy::johnson_cook_flow_stress", _ns_johnson_cook_flow_stress, _acc_johnson_cook_flow_stress)
    var _result_johnson_cook_flow_stress = johnson_cook_flow_stress(0.5, 0.5, 0.5, 0.5)
    var _summary_johnson_cook_flow_stress = _summary_float64(_result_johnson_cook_flow_stress)
    print("MOJO_RESULT metallurgy::johnson_cook_flow_stress", _summary_johnson_cook_flow_stress)
    var _acc_hardness_to_tensile: Float64 = 0.0
    var _t0_hardness_to_tensile = perf_counter_ns()
    for _ in range(N):
        _acc_hardness_to_tensile += hardness_to_tensile(0.5)
    var _t1_hardness_to_tensile = perf_counter_ns()
    var _ns_hardness_to_tensile = Float64(_t1_hardness_to_tensile - _t0_hardness_to_tensile) / Float64(N)
    print("MOJO_TIMING metallurgy::hardness_to_tensile", _ns_hardness_to_tensile, _acc_hardness_to_tensile)
    var _result_hardness_to_tensile = hardness_to_tensile(0.5)
    var _summary_hardness_to_tensile = _summary_float64(_result_hardness_to_tensile)
    print("MOJO_RESULT metallurgy::hardness_to_tensile", _summary_hardness_to_tensile)
    var _acc_carbon_equivalent: Float64 = 0.0
    var _t0_carbon_equivalent = perf_counter_ns()
    for _ in range(N):
        _acc_carbon_equivalent += carbon_equivalent(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_carbon_equivalent = perf_counter_ns()
    var _ns_carbon_equivalent = Float64(_t1_carbon_equivalent - _t0_carbon_equivalent) / Float64(N)
    print("MOJO_TIMING metallurgy::carbon_equivalent", _ns_carbon_equivalent, _acc_carbon_equivalent)
    var _result_carbon_equivalent = carbon_equivalent(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_carbon_equivalent = _summary_float64(_result_carbon_equivalent)
    print("MOJO_RESULT metallurgy::carbon_equivalent", _summary_carbon_equivalent)
    var _acc_jominy_distance_to_hardness: Float64 = 0.0
    var _t0_jominy_distance_to_hardness = perf_counter_ns()
    for _ in range(N):
        _acc_jominy_distance_to_hardness += jominy_distance_to_hardness(0.5, 0.5, 0.5)
    var _t1_jominy_distance_to_hardness = perf_counter_ns()
    var _ns_jominy_distance_to_hardness = Float64(_t1_jominy_distance_to_hardness - _t0_jominy_distance_to_hardness) / Float64(N)
    print("MOJO_TIMING metallurgy::jominy_distance_to_hardness", _ns_jominy_distance_to_hardness, _acc_jominy_distance_to_hardness)
    var _result_jominy_distance_to_hardness = jominy_distance_to_hardness(0.5, 0.5, 0.5)
    var _summary_jominy_distance_to_hardness = _summary_float64(_result_jominy_distance_to_hardness)
    print("MOJO_RESULT metallurgy::jominy_distance_to_hardness", _summary_jominy_distance_to_hardness)
    var _acc_avrami_fraction: Float64 = 0.0
    var _t0_avrami_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_avrami_fraction += avrami_fraction(0.5, 0.5, 0.5)
    var _t1_avrami_fraction = perf_counter_ns()
    var _ns_avrami_fraction = Float64(_t1_avrami_fraction - _t0_avrami_fraction) / Float64(N)
    print("MOJO_TIMING metallurgy::avrami_fraction", _ns_avrami_fraction, _acc_avrami_fraction)
    var _result_avrami_fraction = avrami_fraction(0.5, 0.5, 0.5)
    var _summary_avrami_fraction = _summary_float64(_result_avrami_fraction)
    print("MOJO_RESULT metallurgy::avrami_fraction", _summary_avrami_fraction)
    var _acc_quench_severity: Float64 = 0.0
    var _t0_quench_severity = perf_counter_ns()
    for _ in range(N):
        _acc_quench_severity += quench_severity(0.5, 0.5)
    var _t1_quench_severity = perf_counter_ns()
    var _ns_quench_severity = Float64(_t1_quench_severity - _t0_quench_severity) / Float64(N)
    print("MOJO_TIMING metallurgy::quench_severity", _ns_quench_severity, _acc_quench_severity)
    var _result_quench_severity = quench_severity(0.5, 0.5)
    var _summary_quench_severity = _summary_float64(_result_quench_severity)
    print("MOJO_RESULT metallurgy::quench_severity", _summary_quench_severity)
    var _acc_tempering_parameter: Float64 = 0.0
    var _t0_tempering_parameter = perf_counter_ns()
    for _ in range(N):
        _acc_tempering_parameter += tempering_parameter(0.5, 0.5, 0.5)
    var _t1_tempering_parameter = perf_counter_ns()
    var _ns_tempering_parameter = Float64(_t1_tempering_parameter - _t0_tempering_parameter) / Float64(N)
    print("MOJO_TIMING metallurgy::tempering_parameter", _ns_tempering_parameter, _acc_tempering_parameter)
    var _result_tempering_parameter = tempering_parameter(0.5, 0.5, 0.5)
    var _summary_tempering_parameter = _summary_float64(_result_tempering_parameter)
    print("MOJO_RESULT metallurgy::tempering_parameter", _summary_tempering_parameter)
    var _acc_density_of_alloy_rule_of_mixtures: Float64 = 0.0
    var _t0_density_of_alloy_rule_of_mixtures = perf_counter_ns()
    for _ in range(N):
        _acc_density_of_alloy_rule_of_mixtures += density_of_alloy_rule_of_mixtures(0.5, 0.5, 0.5, 0.5)
    var _t1_density_of_alloy_rule_of_mixtures = perf_counter_ns()
    var _ns_density_of_alloy_rule_of_mixtures = Float64(_t1_density_of_alloy_rule_of_mixtures - _t0_density_of_alloy_rule_of_mixtures) / Float64(N)
    print("MOJO_TIMING metallurgy::density_of_alloy_rule_of_mixtures", _ns_density_of_alloy_rule_of_mixtures, _acc_density_of_alloy_rule_of_mixtures)
    var _result_density_of_alloy_rule_of_mixtures = density_of_alloy_rule_of_mixtures(0.5, 0.5, 0.5, 0.5)
    var _summary_density_of_alloy_rule_of_mixtures = _summary_float64(_result_density_of_alloy_rule_of_mixtures)
    print("MOJO_RESULT metallurgy::density_of_alloy_rule_of_mixtures", _summary_density_of_alloy_rule_of_mixtures)
    var _acc_thermal_conductivity_wiedemann_franz: Float64 = 0.0
    var _t0_thermal_conductivity_wiedemann_franz = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_conductivity_wiedemann_franz += thermal_conductivity_wiedemann_franz(0.5, 0.5, 0.5)
    var _t1_thermal_conductivity_wiedemann_franz = perf_counter_ns()
    var _ns_thermal_conductivity_wiedemann_franz = Float64(_t1_thermal_conductivity_wiedemann_franz - _t0_thermal_conductivity_wiedemann_franz) / Float64(N)
    print("MOJO_TIMING metallurgy::thermal_conductivity_wiedemann_franz", _ns_thermal_conductivity_wiedemann_franz, _acc_thermal_conductivity_wiedemann_franz)
    var _result_thermal_conductivity_wiedemann_franz = thermal_conductivity_wiedemann_franz(0.5, 0.5, 0.5)
    var _summary_thermal_conductivity_wiedemann_franz = _summary_float64(_result_thermal_conductivity_wiedemann_franz)
    print("MOJO_RESULT metallurgy::thermal_conductivity_wiedemann_franz", _summary_thermal_conductivity_wiedemann_franz)
    var _acc_strain_hardening_exponent_from_points: Float64 = 0.0
    var _t0_strain_hardening_exponent_from_points = perf_counter_ns()
    for _ in range(N):
        _acc_strain_hardening_exponent_from_points += strain_hardening_exponent_from_points(0.5, 0.5, 0.5, 0.5)
    var _t1_strain_hardening_exponent_from_points = perf_counter_ns()
    var _ns_strain_hardening_exponent_from_points = Float64(_t1_strain_hardening_exponent_from_points - _t0_strain_hardening_exponent_from_points) / Float64(N)
    print("MOJO_TIMING metallurgy::strain_hardening_exponent_from_points", _ns_strain_hardening_exponent_from_points, _acc_strain_hardening_exponent_from_points)
    var _result_strain_hardening_exponent_from_points = strain_hardening_exponent_from_points(0.5, 0.5, 0.5, 0.5)
    var _summary_strain_hardening_exponent_from_points = _summary_float64(_result_strain_hardening_exponent_from_points)
    print("MOJO_RESULT metallurgy::strain_hardening_exponent_from_points", _summary_strain_hardening_exponent_from_points)
    var _acc_fatigue_life_basquin: Float64 = 0.0
    var _t0_fatigue_life_basquin = perf_counter_ns()
    for _ in range(N):
        _acc_fatigue_life_basquin += fatigue_life_basquin(0.5, 0.5, 0.5)
    var _t1_fatigue_life_basquin = perf_counter_ns()
    var _ns_fatigue_life_basquin = Float64(_t1_fatigue_life_basquin - _t0_fatigue_life_basquin) / Float64(N)
    print("MOJO_TIMING metallurgy::fatigue_life_basquin", _ns_fatigue_life_basquin, _acc_fatigue_life_basquin)
    var _result_fatigue_life_basquin = fatigue_life_basquin(0.5, 0.5, 0.5)
    var _summary_fatigue_life_basquin = _summary_float64(_result_fatigue_life_basquin)
    print("MOJO_RESULT metallurgy::fatigue_life_basquin", _summary_fatigue_life_basquin)
