"""bench_battery.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from battery import state_of_charge, depth_of_discharge, coulombic_efficiency, energy_density, power_density, c_rate, discharge_time, peukert_capacity, cycle_life_degradation, internal_resistance_from_voltage, battery_pack_voltage, battery_pack_capacity
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

    var _acc_state_of_charge: Float64 = 0.0
    var _t0_state_of_charge = perf_counter_ns()
    for _ in range(N):
        _acc_state_of_charge += state_of_charge(0.5, 0.5)
    var _t1_state_of_charge = perf_counter_ns()
    var _ns_state_of_charge = Float64(_t1_state_of_charge - _t0_state_of_charge) / Float64(N)
    print("MOJO_TIMING battery::state_of_charge", _ns_state_of_charge, _acc_state_of_charge)
    var _result_state_of_charge = state_of_charge(0.5, 0.5)
    var _summary_state_of_charge = _summary_float64(_result_state_of_charge)
    print("MOJO_RESULT battery::state_of_charge", _summary_state_of_charge)
    var _acc_depth_of_discharge: Float64 = 0.0
    var _t0_depth_of_discharge = perf_counter_ns()
    for _ in range(N):
        _acc_depth_of_discharge += depth_of_discharge(0.5)
    var _t1_depth_of_discharge = perf_counter_ns()
    var _ns_depth_of_discharge = Float64(_t1_depth_of_discharge - _t0_depth_of_discharge) / Float64(N)
    print("MOJO_TIMING battery::depth_of_discharge", _ns_depth_of_discharge, _acc_depth_of_discharge)
    var _result_depth_of_discharge = depth_of_discharge(0.5)
    var _summary_depth_of_discharge = _summary_float64(_result_depth_of_discharge)
    print("MOJO_RESULT battery::depth_of_discharge", _summary_depth_of_discharge)
    var _acc_coulombic_efficiency: Float64 = 0.0
    var _t0_coulombic_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_coulombic_efficiency += coulombic_efficiency(0.5, 0.5)
    var _t1_coulombic_efficiency = perf_counter_ns()
    var _ns_coulombic_efficiency = Float64(_t1_coulombic_efficiency - _t0_coulombic_efficiency) / Float64(N)
    print("MOJO_TIMING battery::coulombic_efficiency", _ns_coulombic_efficiency, _acc_coulombic_efficiency)
    var _result_coulombic_efficiency = coulombic_efficiency(0.5, 0.5)
    var _summary_coulombic_efficiency = _summary_float64(_result_coulombic_efficiency)
    print("MOJO_RESULT battery::coulombic_efficiency", _summary_coulombic_efficiency)
    var _acc_energy_density: Float64 = 0.0
    var _t0_energy_density = perf_counter_ns()
    for _ in range(N):
        _acc_energy_density += energy_density(0.5, 0.5)
    var _t1_energy_density = perf_counter_ns()
    var _ns_energy_density = Float64(_t1_energy_density - _t0_energy_density) / Float64(N)
    print("MOJO_TIMING battery::energy_density", _ns_energy_density, _acc_energy_density)
    var _result_energy_density = energy_density(0.5, 0.5)
    var _summary_energy_density = _summary_float64(_result_energy_density)
    print("MOJO_RESULT battery::energy_density", _summary_energy_density)
    var _acc_power_density: Float64 = 0.0
    var _t0_power_density = perf_counter_ns()
    for _ in range(N):
        _acc_power_density += power_density(0.5, 0.5)
    var _t1_power_density = perf_counter_ns()
    var _ns_power_density = Float64(_t1_power_density - _t0_power_density) / Float64(N)
    print("MOJO_TIMING battery::power_density", _ns_power_density, _acc_power_density)
    var _result_power_density = power_density(0.5, 0.5)
    var _summary_power_density = _summary_float64(_result_power_density)
    print("MOJO_RESULT battery::power_density", _summary_power_density)
    var _acc_c_rate: Float64 = 0.0
    var _t0_c_rate = perf_counter_ns()
    for _ in range(N):
        _acc_c_rate += c_rate(0.5, 0.5)
    var _t1_c_rate = perf_counter_ns()
    var _ns_c_rate = Float64(_t1_c_rate - _t0_c_rate) / Float64(N)
    print("MOJO_TIMING battery::c_rate", _ns_c_rate, _acc_c_rate)
    var _result_c_rate = c_rate(0.5, 0.5)
    var _summary_c_rate = _summary_float64(_result_c_rate)
    print("MOJO_RESULT battery::c_rate", _summary_c_rate)
    var _acc_discharge_time: Float64 = 0.0
    var _t0_discharge_time = perf_counter_ns()
    for _ in range(N):
        _acc_discharge_time += discharge_time(0.5, 0.5)
    var _t1_discharge_time = perf_counter_ns()
    var _ns_discharge_time = Float64(_t1_discharge_time - _t0_discharge_time) / Float64(N)
    print("MOJO_TIMING battery::discharge_time", _ns_discharge_time, _acc_discharge_time)
    var _result_discharge_time = discharge_time(0.5, 0.5)
    var _summary_discharge_time = _summary_float64(_result_discharge_time)
    print("MOJO_RESULT battery::discharge_time", _summary_discharge_time)
    var _acc_peukert_capacity: Float64 = 0.0
    var _t0_peukert_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_peukert_capacity += peukert_capacity(0.5, 0.5, 0.5, 0.5)
    var _t1_peukert_capacity = perf_counter_ns()
    var _ns_peukert_capacity = Float64(_t1_peukert_capacity - _t0_peukert_capacity) / Float64(N)
    print("MOJO_TIMING battery::peukert_capacity", _ns_peukert_capacity, _acc_peukert_capacity)
    var _result_peukert_capacity = peukert_capacity(0.5, 0.5, 0.5, 0.5)
    var _summary_peukert_capacity = _summary_float64(_result_peukert_capacity)
    print("MOJO_RESULT battery::peukert_capacity", _summary_peukert_capacity)
    var _acc_cycle_life_degradation: Float64 = 0.0
    var _t0_cycle_life_degradation = perf_counter_ns()
    for _ in range(N):
        _acc_cycle_life_degradation += cycle_life_degradation(0.5, 0.5, 0.5)
    var _t1_cycle_life_degradation = perf_counter_ns()
    var _ns_cycle_life_degradation = Float64(_t1_cycle_life_degradation - _t0_cycle_life_degradation) / Float64(N)
    print("MOJO_TIMING battery::cycle_life_degradation", _ns_cycle_life_degradation, _acc_cycle_life_degradation)
    var _result_cycle_life_degradation = cycle_life_degradation(0.5, 0.5, 0.5)
    var _summary_cycle_life_degradation = _summary_float64(_result_cycle_life_degradation)
    print("MOJO_RESULT battery::cycle_life_degradation", _summary_cycle_life_degradation)
    var _acc_internal_resistance_from_voltage: Float64 = 0.0
    var _t0_internal_resistance_from_voltage = perf_counter_ns()
    for _ in range(N):
        _acc_internal_resistance_from_voltage += internal_resistance_from_voltage(0.5, 0.5, 0.5)
    var _t1_internal_resistance_from_voltage = perf_counter_ns()
    var _ns_internal_resistance_from_voltage = Float64(_t1_internal_resistance_from_voltage - _t0_internal_resistance_from_voltage) / Float64(N)
    print("MOJO_TIMING battery::internal_resistance_from_voltage", _ns_internal_resistance_from_voltage, _acc_internal_resistance_from_voltage)
    var _result_internal_resistance_from_voltage = internal_resistance_from_voltage(0.5, 0.5, 0.5)
    var _summary_internal_resistance_from_voltage = _summary_float64(_result_internal_resistance_from_voltage)
    print("MOJO_RESULT battery::internal_resistance_from_voltage", _summary_internal_resistance_from_voltage)
    var _acc_battery_pack_voltage: Float64 = 0.0
    var _t0_battery_pack_voltage = perf_counter_ns()
    for _ in range(N):
        _acc_battery_pack_voltage += battery_pack_voltage(0.5, 0.5)
    var _t1_battery_pack_voltage = perf_counter_ns()
    var _ns_battery_pack_voltage = Float64(_t1_battery_pack_voltage - _t0_battery_pack_voltage) / Float64(N)
    print("MOJO_TIMING battery::battery_pack_voltage", _ns_battery_pack_voltage, _acc_battery_pack_voltage)
    var _result_battery_pack_voltage = battery_pack_voltage(0.5, 0.5)
    var _summary_battery_pack_voltage = _summary_float64(_result_battery_pack_voltage)
    print("MOJO_RESULT battery::battery_pack_voltage", _summary_battery_pack_voltage)
    var _acc_battery_pack_capacity: Float64 = 0.0
    var _t0_battery_pack_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_battery_pack_capacity += battery_pack_capacity(0.5, 0.5)
    var _t1_battery_pack_capacity = perf_counter_ns()
    var _ns_battery_pack_capacity = Float64(_t1_battery_pack_capacity - _t0_battery_pack_capacity) / Float64(N)
    print("MOJO_TIMING battery::battery_pack_capacity", _ns_battery_pack_capacity, _acc_battery_pack_capacity)
    var _result_battery_pack_capacity = battery_pack_capacity(0.5, 0.5)
    var _summary_battery_pack_capacity = _summary_float64(_result_battery_pack_capacity)
    print("MOJO_RESULT battery::battery_pack_capacity", _summary_battery_pack_capacity)
