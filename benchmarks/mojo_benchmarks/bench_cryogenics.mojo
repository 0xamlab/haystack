"""bench_cryogenics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from cryogenics import ideal_gas_density, joule_thomson_cooling, carnot_cop_cooling, liquefaction_yield, boiloff_rate, thermal_contraction, heat_leak_through_wall, superconductor_critical_temp_estimate, residual_resistivity_ratio, cryocooler_input_power, vacuum_insulation_heat_flux, helium_lambda_point
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

    var _acc_ideal_gas_density: Float64 = 0.0
    var _t0_ideal_gas_density = perf_counter_ns()
    for _ in range(N):
        _acc_ideal_gas_density += ideal_gas_density(0.5, 0.5, 0.5, 0.5)
    var _t1_ideal_gas_density = perf_counter_ns()
    var _ns_ideal_gas_density = Float64(_t1_ideal_gas_density - _t0_ideal_gas_density) / Float64(N)
    print("MOJO_TIMING cryogenics::ideal_gas_density", _ns_ideal_gas_density, _acc_ideal_gas_density)
    var _result_ideal_gas_density = ideal_gas_density(0.5, 0.5, 0.5, 0.5)
    var _summary_ideal_gas_density = _summary_float64(_result_ideal_gas_density)
    print("MOJO_RESULT cryogenics::ideal_gas_density", _summary_ideal_gas_density)
    var _acc_joule_thomson_cooling: Float64 = 0.0
    var _t0_joule_thomson_cooling = perf_counter_ns()
    for _ in range(N):
        _acc_joule_thomson_cooling += joule_thomson_cooling(0.5, 0.5)
    var _t1_joule_thomson_cooling = perf_counter_ns()
    var _ns_joule_thomson_cooling = Float64(_t1_joule_thomson_cooling - _t0_joule_thomson_cooling) / Float64(N)
    print("MOJO_TIMING cryogenics::joule_thomson_cooling", _ns_joule_thomson_cooling, _acc_joule_thomson_cooling)
    var _result_joule_thomson_cooling = joule_thomson_cooling(0.5, 0.5)
    var _summary_joule_thomson_cooling = _summary_float64(_result_joule_thomson_cooling)
    print("MOJO_RESULT cryogenics::joule_thomson_cooling", _summary_joule_thomson_cooling)
    var _acc_carnot_cop_cooling: Float64 = 0.0
    var _t0_carnot_cop_cooling = perf_counter_ns()
    for _ in range(N):
        _acc_carnot_cop_cooling += carnot_cop_cooling(200.0, 300.0)
    var _t1_carnot_cop_cooling = perf_counter_ns()
    var _ns_carnot_cop_cooling = Float64(_t1_carnot_cop_cooling - _t0_carnot_cop_cooling) / Float64(N)
    print("MOJO_TIMING cryogenics::carnot_cop_cooling", _ns_carnot_cop_cooling, _acc_carnot_cop_cooling)
    var _result_carnot_cop_cooling = carnot_cop_cooling(200.0, 300.0)
    var _summary_carnot_cop_cooling = _summary_float64(_result_carnot_cop_cooling)
    print("MOJO_RESULT cryogenics::carnot_cop_cooling", _summary_carnot_cop_cooling)
    var _acc_liquefaction_yield: Float64 = 0.0
    var _t0_liquefaction_yield = perf_counter_ns()
    for _ in range(N):
        _acc_liquefaction_yield += liquefaction_yield(0.5, 0.5, 0.5, 0.5)
    var _t1_liquefaction_yield = perf_counter_ns()
    var _ns_liquefaction_yield = Float64(_t1_liquefaction_yield - _t0_liquefaction_yield) / Float64(N)
    print("MOJO_TIMING cryogenics::liquefaction_yield", _ns_liquefaction_yield, _acc_liquefaction_yield)
    var _result_liquefaction_yield = liquefaction_yield(0.5, 0.5, 0.5, 0.5)
    var _summary_liquefaction_yield = _summary_float64(_result_liquefaction_yield)
    print("MOJO_RESULT cryogenics::liquefaction_yield", _summary_liquefaction_yield)
    var _acc_boiloff_rate: Float64 = 0.0
    var _t0_boiloff_rate = perf_counter_ns()
    for _ in range(N):
        _acc_boiloff_rate += boiloff_rate(0.5, 0.5, 0.5)
    var _t1_boiloff_rate = perf_counter_ns()
    var _ns_boiloff_rate = Float64(_t1_boiloff_rate - _t0_boiloff_rate) / Float64(N)
    print("MOJO_TIMING cryogenics::boiloff_rate", _ns_boiloff_rate, _acc_boiloff_rate)
    var _result_boiloff_rate = boiloff_rate(0.5, 0.5, 0.5)
    var _summary_boiloff_rate = _summary_float64(_result_boiloff_rate)
    print("MOJO_RESULT cryogenics::boiloff_rate", _summary_boiloff_rate)
    var _acc_thermal_contraction: Float64 = 0.0
    var _t0_thermal_contraction = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_contraction += thermal_contraction(0.5, 0.5, 0.5)
    var _t1_thermal_contraction = perf_counter_ns()
    var _ns_thermal_contraction = Float64(_t1_thermal_contraction - _t0_thermal_contraction) / Float64(N)
    print("MOJO_TIMING cryogenics::thermal_contraction", _ns_thermal_contraction, _acc_thermal_contraction)
    var _result_thermal_contraction = thermal_contraction(0.5, 0.5, 0.5)
    var _summary_thermal_contraction = _summary_float64(_result_thermal_contraction)
    print("MOJO_RESULT cryogenics::thermal_contraction", _summary_thermal_contraction)
    var _acc_heat_leak_through_wall: Float64 = 0.0
    var _t0_heat_leak_through_wall = perf_counter_ns()
    for _ in range(N):
        _acc_heat_leak_through_wall += heat_leak_through_wall(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_heat_leak_through_wall = perf_counter_ns()
    var _ns_heat_leak_through_wall = Float64(_t1_heat_leak_through_wall - _t0_heat_leak_through_wall) / Float64(N)
    print("MOJO_TIMING cryogenics::heat_leak_through_wall", _ns_heat_leak_through_wall, _acc_heat_leak_through_wall)
    var _result_heat_leak_through_wall = heat_leak_through_wall(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_heat_leak_through_wall = _summary_float64(_result_heat_leak_through_wall)
    print("MOJO_RESULT cryogenics::heat_leak_through_wall", _summary_heat_leak_through_wall)
    var _acc_superconductor_critical_temp_estimate: Float64 = 0.0
    var _t0_superconductor_critical_temp_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_superconductor_critical_temp_estimate += superconductor_critical_temp_estimate(0.5, 0.5, 0.5)
    var _t1_superconductor_critical_temp_estimate = perf_counter_ns()
    var _ns_superconductor_critical_temp_estimate = Float64(_t1_superconductor_critical_temp_estimate - _t0_superconductor_critical_temp_estimate) / Float64(N)
    print("MOJO_TIMING cryogenics::superconductor_critical_temp_estimate", _ns_superconductor_critical_temp_estimate, _acc_superconductor_critical_temp_estimate)
    var _result_superconductor_critical_temp_estimate = superconductor_critical_temp_estimate(0.5, 0.5, 0.5)
    var _summary_superconductor_critical_temp_estimate = _summary_float64(_result_superconductor_critical_temp_estimate)
    print("MOJO_RESULT cryogenics::superconductor_critical_temp_estimate", _summary_superconductor_critical_temp_estimate)
    var _acc_residual_resistivity_ratio: Float64 = 0.0
    var _t0_residual_resistivity_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_residual_resistivity_ratio += residual_resistivity_ratio(0.5, 0.5)
    var _t1_residual_resistivity_ratio = perf_counter_ns()
    var _ns_residual_resistivity_ratio = Float64(_t1_residual_resistivity_ratio - _t0_residual_resistivity_ratio) / Float64(N)
    print("MOJO_TIMING cryogenics::residual_resistivity_ratio", _ns_residual_resistivity_ratio, _acc_residual_resistivity_ratio)
    var _result_residual_resistivity_ratio = residual_resistivity_ratio(0.5, 0.5)
    var _summary_residual_resistivity_ratio = _summary_float64(_result_residual_resistivity_ratio)
    print("MOJO_RESULT cryogenics::residual_resistivity_ratio", _summary_residual_resistivity_ratio)
    var _acc_cryocooler_input_power: Float64 = 0.0
    var _t0_cryocooler_input_power = perf_counter_ns()
    for _ in range(N):
        _acc_cryocooler_input_power += cryocooler_input_power(0.5, 0.5)
    var _t1_cryocooler_input_power = perf_counter_ns()
    var _ns_cryocooler_input_power = Float64(_t1_cryocooler_input_power - _t0_cryocooler_input_power) / Float64(N)
    print("MOJO_TIMING cryogenics::cryocooler_input_power", _ns_cryocooler_input_power, _acc_cryocooler_input_power)
    var _result_cryocooler_input_power = cryocooler_input_power(0.5, 0.5)
    var _summary_cryocooler_input_power = _summary_float64(_result_cryocooler_input_power)
    print("MOJO_RESULT cryogenics::cryocooler_input_power", _summary_cryocooler_input_power)
    var _acc_vacuum_insulation_heat_flux: Float64 = 0.0
    var _t0_vacuum_insulation_heat_flux = perf_counter_ns()
    for _ in range(N):
        _acc_vacuum_insulation_heat_flux += vacuum_insulation_heat_flux(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_vacuum_insulation_heat_flux = perf_counter_ns()
    var _ns_vacuum_insulation_heat_flux = Float64(_t1_vacuum_insulation_heat_flux - _t0_vacuum_insulation_heat_flux) / Float64(N)
    print("MOJO_TIMING cryogenics::vacuum_insulation_heat_flux", _ns_vacuum_insulation_heat_flux, _acc_vacuum_insulation_heat_flux)
    var _result_vacuum_insulation_heat_flux = vacuum_insulation_heat_flux(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_vacuum_insulation_heat_flux = _summary_float64(_result_vacuum_insulation_heat_flux)
    print("MOJO_RESULT cryogenics::vacuum_insulation_heat_flux", _summary_vacuum_insulation_heat_flux)
    var _acc_helium_lambda_point: Float64 = 0.0
    var _t0_helium_lambda_point = perf_counter_ns()
    for _ in range(N):
        _acc_helium_lambda_point += helium_lambda_point()
    var _t1_helium_lambda_point = perf_counter_ns()
    var _ns_helium_lambda_point = Float64(_t1_helium_lambda_point - _t0_helium_lambda_point) / Float64(N)
    print("MOJO_TIMING cryogenics::helium_lambda_point", _ns_helium_lambda_point, _acc_helium_lambda_point)
    var _result_helium_lambda_point = helium_lambda_point()
    var _summary_helium_lambda_point = _summary_float64(_result_helium_lambda_point)
    print("MOJO_RESULT cryogenics::helium_lambda_point", _summary_helium_lambda_point)
