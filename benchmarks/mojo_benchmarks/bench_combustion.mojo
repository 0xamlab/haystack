"""bench_combustion.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from combustion import stoichiometric_air_fuel_ratio, equivalence_ratio, excess_air_percentage, adiabatic_flame_temp_estimate, lower_heating_value_methane, thermal_efficiency, carnot_efficiency, brake_specific_fuel_consumption, combustion_efficiency, flame_speed_laminar, nox_formation_rate, heat_release_rate
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

    var _acc_stoichiometric_air_fuel_ratio: Float64 = 0.0
    var _t0_stoichiometric_air_fuel_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_stoichiometric_air_fuel_ratio += stoichiometric_air_fuel_ratio(0.5, 0.5, 0.5)
    var _t1_stoichiometric_air_fuel_ratio = perf_counter_ns()
    var _ns_stoichiometric_air_fuel_ratio = Float64(_t1_stoichiometric_air_fuel_ratio - _t0_stoichiometric_air_fuel_ratio) / Float64(N)
    print("MOJO_TIMING combustion::stoichiometric_air_fuel_ratio", _ns_stoichiometric_air_fuel_ratio, _acc_stoichiometric_air_fuel_ratio)
    var _result_stoichiometric_air_fuel_ratio = stoichiometric_air_fuel_ratio(0.5, 0.5, 0.5)
    var _summary_stoichiometric_air_fuel_ratio = _summary_float64(_result_stoichiometric_air_fuel_ratio)
    print("MOJO_RESULT combustion::stoichiometric_air_fuel_ratio", _summary_stoichiometric_air_fuel_ratio)
    var _acc_equivalence_ratio: Float64 = 0.0
    var _t0_equivalence_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_equivalence_ratio += equivalence_ratio(0.5, 0.5)
    var _t1_equivalence_ratio = perf_counter_ns()
    var _ns_equivalence_ratio = Float64(_t1_equivalence_ratio - _t0_equivalence_ratio) / Float64(N)
    print("MOJO_TIMING combustion::equivalence_ratio", _ns_equivalence_ratio, _acc_equivalence_ratio)
    var _result_equivalence_ratio = equivalence_ratio(0.5, 0.5)
    var _summary_equivalence_ratio = _summary_float64(_result_equivalence_ratio)
    print("MOJO_RESULT combustion::equivalence_ratio", _summary_equivalence_ratio)
    var _acc_excess_air_percentage: Float64 = 0.0
    var _t0_excess_air_percentage = perf_counter_ns()
    for _ in range(N):
        _acc_excess_air_percentage += excess_air_percentage(0.5)
    var _t1_excess_air_percentage = perf_counter_ns()
    var _ns_excess_air_percentage = Float64(_t1_excess_air_percentage - _t0_excess_air_percentage) / Float64(N)
    print("MOJO_TIMING combustion::excess_air_percentage", _ns_excess_air_percentage, _acc_excess_air_percentage)
    var _result_excess_air_percentage = excess_air_percentage(0.5)
    var _summary_excess_air_percentage = _summary_float64(_result_excess_air_percentage)
    print("MOJO_RESULT combustion::excess_air_percentage", _summary_excess_air_percentage)
    var _acc_adiabatic_flame_temp_estimate: Float64 = 0.0
    var _t0_adiabatic_flame_temp_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_adiabatic_flame_temp_estimate += adiabatic_flame_temp_estimate(0.5, 0.5, 0.5, 0.5)
    var _t1_adiabatic_flame_temp_estimate = perf_counter_ns()
    var _ns_adiabatic_flame_temp_estimate = Float64(_t1_adiabatic_flame_temp_estimate - _t0_adiabatic_flame_temp_estimate) / Float64(N)
    print("MOJO_TIMING combustion::adiabatic_flame_temp_estimate", _ns_adiabatic_flame_temp_estimate, _acc_adiabatic_flame_temp_estimate)
    var _result_adiabatic_flame_temp_estimate = adiabatic_flame_temp_estimate(0.5, 0.5, 0.5, 0.5)
    var _summary_adiabatic_flame_temp_estimate = _summary_float64(_result_adiabatic_flame_temp_estimate)
    print("MOJO_RESULT combustion::adiabatic_flame_temp_estimate", _summary_adiabatic_flame_temp_estimate)
    var _acc_lower_heating_value_methane: Float64 = 0.0
    var _t0_lower_heating_value_methane = perf_counter_ns()
    for _ in range(N):
        _acc_lower_heating_value_methane += lower_heating_value_methane()
    var _t1_lower_heating_value_methane = perf_counter_ns()
    var _ns_lower_heating_value_methane = Float64(_t1_lower_heating_value_methane - _t0_lower_heating_value_methane) / Float64(N)
    print("MOJO_TIMING combustion::lower_heating_value_methane", _ns_lower_heating_value_methane, _acc_lower_heating_value_methane)
    var _result_lower_heating_value_methane = lower_heating_value_methane()
    var _summary_lower_heating_value_methane = _summary_float64(_result_lower_heating_value_methane)
    print("MOJO_RESULT combustion::lower_heating_value_methane", _summary_lower_heating_value_methane)
    var _acc_thermal_efficiency: Float64 = 0.0
    var _t0_thermal_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_efficiency += thermal_efficiency(0.5, 0.5)
    var _t1_thermal_efficiency = perf_counter_ns()
    var _ns_thermal_efficiency = Float64(_t1_thermal_efficiency - _t0_thermal_efficiency) / Float64(N)
    print("MOJO_TIMING combustion::thermal_efficiency", _ns_thermal_efficiency, _acc_thermal_efficiency)
    var _result_thermal_efficiency = thermal_efficiency(0.5, 0.5)
    var _summary_thermal_efficiency = _summary_float64(_result_thermal_efficiency)
    print("MOJO_RESULT combustion::thermal_efficiency", _summary_thermal_efficiency)
    var _acc_carnot_efficiency: Float64 = 0.0
    var _t0_carnot_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_carnot_efficiency += carnot_efficiency(0.5, 0.5)
    var _t1_carnot_efficiency = perf_counter_ns()
    var _ns_carnot_efficiency = Float64(_t1_carnot_efficiency - _t0_carnot_efficiency) / Float64(N)
    print("MOJO_TIMING combustion::carnot_efficiency", _ns_carnot_efficiency, _acc_carnot_efficiency)
    var _result_carnot_efficiency = carnot_efficiency(0.5, 0.5)
    var _summary_carnot_efficiency = _summary_float64(_result_carnot_efficiency)
    print("MOJO_RESULT combustion::carnot_efficiency", _summary_carnot_efficiency)
    var _acc_brake_specific_fuel_consumption: Float64 = 0.0
    var _t0_brake_specific_fuel_consumption = perf_counter_ns()
    for _ in range(N):
        _acc_brake_specific_fuel_consumption += brake_specific_fuel_consumption(0.5, 0.5)
    var _t1_brake_specific_fuel_consumption = perf_counter_ns()
    var _ns_brake_specific_fuel_consumption = Float64(_t1_brake_specific_fuel_consumption - _t0_brake_specific_fuel_consumption) / Float64(N)
    print("MOJO_TIMING combustion::brake_specific_fuel_consumption", _ns_brake_specific_fuel_consumption, _acc_brake_specific_fuel_consumption)
    var _result_brake_specific_fuel_consumption = brake_specific_fuel_consumption(0.5, 0.5)
    var _summary_brake_specific_fuel_consumption = _summary_float64(_result_brake_specific_fuel_consumption)
    print("MOJO_RESULT combustion::brake_specific_fuel_consumption", _summary_brake_specific_fuel_consumption)
    var _acc_combustion_efficiency: Float64 = 0.0
    var _t0_combustion_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_combustion_efficiency += combustion_efficiency(0.5, 0.5)
    var _t1_combustion_efficiency = perf_counter_ns()
    var _ns_combustion_efficiency = Float64(_t1_combustion_efficiency - _t0_combustion_efficiency) / Float64(N)
    print("MOJO_TIMING combustion::combustion_efficiency", _ns_combustion_efficiency, _acc_combustion_efficiency)
    var _result_combustion_efficiency = combustion_efficiency(0.5, 0.5)
    var _summary_combustion_efficiency = _summary_float64(_result_combustion_efficiency)
    print("MOJO_RESULT combustion::combustion_efficiency", _summary_combustion_efficiency)
    var _acc_flame_speed_laminar: Float64 = 0.0
    var _t0_flame_speed_laminar = perf_counter_ns()
    for _ in range(N):
        _acc_flame_speed_laminar += flame_speed_laminar(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_flame_speed_laminar = perf_counter_ns()
    var _ns_flame_speed_laminar = Float64(_t1_flame_speed_laminar - _t0_flame_speed_laminar) / Float64(N)
    print("MOJO_TIMING combustion::flame_speed_laminar", _ns_flame_speed_laminar, _acc_flame_speed_laminar)
    var _result_flame_speed_laminar = flame_speed_laminar(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_flame_speed_laminar = _summary_float64(_result_flame_speed_laminar)
    print("MOJO_RESULT combustion::flame_speed_laminar", _summary_flame_speed_laminar)
    var _acc_nox_formation_rate: Float64 = 0.0
    var _t0_nox_formation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_nox_formation_rate += nox_formation_rate(0.5, 0.5)
    var _t1_nox_formation_rate = perf_counter_ns()
    var _ns_nox_formation_rate = Float64(_t1_nox_formation_rate - _t0_nox_formation_rate) / Float64(N)
    print("MOJO_TIMING combustion::nox_formation_rate", _ns_nox_formation_rate, _acc_nox_formation_rate)
    var _result_nox_formation_rate = nox_formation_rate(0.5, 0.5)
    var _summary_nox_formation_rate = _summary_float64(_result_nox_formation_rate)
    print("MOJO_RESULT combustion::nox_formation_rate", _summary_nox_formation_rate)
    var _acc_heat_release_rate: Float64 = 0.0
    var _t0_heat_release_rate = perf_counter_ns()
    for _ in range(N):
        _acc_heat_release_rate += heat_release_rate(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_heat_release_rate = perf_counter_ns()
    var _ns_heat_release_rate = Float64(_t1_heat_release_rate - _t0_heat_release_rate) / Float64(N)
    print("MOJO_TIMING combustion::heat_release_rate", _ns_heat_release_rate, _acc_heat_release_rate)
    var _result_heat_release_rate = heat_release_rate(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_heat_release_rate = _summary_float64(_result_heat_release_rate)
    print("MOJO_RESULT combustion::heat_release_rate", _summary_heat_release_rate)
