"""bench_battery.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from battery import state_of_charge, depth_of_discharge, coulombic_efficiency, energy_density, power_density, c_rate, discharge_time, peukert_capacity, cycle_life_degradation, internal_resistance_from_voltage, battery_pack_voltage, battery_pack_capacity
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

    var _acc_state_of_charge: Float64 = 0.0
    var _t0_state_of_charge = perf_counter_ns()
    for _ in range(N):
        _acc_state_of_charge += state_of_charge(0.5, 0.5)
    var _t1_state_of_charge = perf_counter_ns()
    var _ns_state_of_charge = Float64(_t1_state_of_charge - _t0_state_of_charge) / Float64(N)
    print("MOJO_TIMING battery::state_of_charge", _ns_state_of_charge, _acc_state_of_charge)
    var _acc_depth_of_discharge: Float64 = 0.0
    var _t0_depth_of_discharge = perf_counter_ns()
    for _ in range(N):
        _acc_depth_of_discharge += depth_of_discharge(0.5)
    var _t1_depth_of_discharge = perf_counter_ns()
    var _ns_depth_of_discharge = Float64(_t1_depth_of_discharge - _t0_depth_of_discharge) / Float64(N)
    print("MOJO_TIMING battery::depth_of_discharge", _ns_depth_of_discharge, _acc_depth_of_discharge)
    var _acc_coulombic_efficiency: Float64 = 0.0
    var _t0_coulombic_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_coulombic_efficiency += coulombic_efficiency(0.5, 0.5)
    var _t1_coulombic_efficiency = perf_counter_ns()
    var _ns_coulombic_efficiency = Float64(_t1_coulombic_efficiency - _t0_coulombic_efficiency) / Float64(N)
    print("MOJO_TIMING battery::coulombic_efficiency", _ns_coulombic_efficiency, _acc_coulombic_efficiency)
    var _acc_energy_density: Float64 = 0.0
    var _t0_energy_density = perf_counter_ns()
    for _ in range(N):
        _acc_energy_density += energy_density(0.5, 0.5)
    var _t1_energy_density = perf_counter_ns()
    var _ns_energy_density = Float64(_t1_energy_density - _t0_energy_density) / Float64(N)
    print("MOJO_TIMING battery::energy_density", _ns_energy_density, _acc_energy_density)
    var _acc_power_density: Float64 = 0.0
    var _t0_power_density = perf_counter_ns()
    for _ in range(N):
        _acc_power_density += power_density(0.5, 0.5)
    var _t1_power_density = perf_counter_ns()
    var _ns_power_density = Float64(_t1_power_density - _t0_power_density) / Float64(N)
    print("MOJO_TIMING battery::power_density", _ns_power_density, _acc_power_density)
    var _acc_c_rate: Float64 = 0.0
    var _t0_c_rate = perf_counter_ns()
    for _ in range(N):
        _acc_c_rate += c_rate(0.5, 0.5)
    var _t1_c_rate = perf_counter_ns()
    var _ns_c_rate = Float64(_t1_c_rate - _t0_c_rate) / Float64(N)
    print("MOJO_TIMING battery::c_rate", _ns_c_rate, _acc_c_rate)
    var _acc_discharge_time: Float64 = 0.0
    var _t0_discharge_time = perf_counter_ns()
    for _ in range(N):
        _acc_discharge_time += discharge_time(0.5, 0.5)
    var _t1_discharge_time = perf_counter_ns()
    var _ns_discharge_time = Float64(_t1_discharge_time - _t0_discharge_time) / Float64(N)
    print("MOJO_TIMING battery::discharge_time", _ns_discharge_time, _acc_discharge_time)
    var _acc_peukert_capacity: Float64 = 0.0
    var _t0_peukert_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_peukert_capacity += peukert_capacity(0.5, 0.5, 0.5, 0.5)
    var _t1_peukert_capacity = perf_counter_ns()
    var _ns_peukert_capacity = Float64(_t1_peukert_capacity - _t0_peukert_capacity) / Float64(N)
    print("MOJO_TIMING battery::peukert_capacity", _ns_peukert_capacity, _acc_peukert_capacity)
    var _acc_cycle_life_degradation: Float64 = 0.0
    var _t0_cycle_life_degradation = perf_counter_ns()
    for _ in range(N):
        _acc_cycle_life_degradation += cycle_life_degradation(0.5, 0.5, 0.5)
    var _t1_cycle_life_degradation = perf_counter_ns()
    var _ns_cycle_life_degradation = Float64(_t1_cycle_life_degradation - _t0_cycle_life_degradation) / Float64(N)
    print("MOJO_TIMING battery::cycle_life_degradation", _ns_cycle_life_degradation, _acc_cycle_life_degradation)
    var _acc_internal_resistance_from_voltage: Float64 = 0.0
    var _t0_internal_resistance_from_voltage = perf_counter_ns()
    for _ in range(N):
        _acc_internal_resistance_from_voltage += internal_resistance_from_voltage(0.5, 0.5, 0.5)
    var _t1_internal_resistance_from_voltage = perf_counter_ns()
    var _ns_internal_resistance_from_voltage = Float64(_t1_internal_resistance_from_voltage - _t0_internal_resistance_from_voltage) / Float64(N)
    print("MOJO_TIMING battery::internal_resistance_from_voltage", _ns_internal_resistance_from_voltage, _acc_internal_resistance_from_voltage)
    var _acc_battery_pack_voltage: Float64 = 0.0
    var _t0_battery_pack_voltage = perf_counter_ns()
    for _ in range(N):
        _acc_battery_pack_voltage += battery_pack_voltage(0.5, 0.5)
    var _t1_battery_pack_voltage = perf_counter_ns()
    var _ns_battery_pack_voltage = Float64(_t1_battery_pack_voltage - _t0_battery_pack_voltage) / Float64(N)
    print("MOJO_TIMING battery::battery_pack_voltage", _ns_battery_pack_voltage, _acc_battery_pack_voltage)
    var _acc_battery_pack_capacity: Float64 = 0.0
    var _t0_battery_pack_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_battery_pack_capacity += battery_pack_capacity(0.5, 0.5)
    var _t1_battery_pack_capacity = perf_counter_ns()
    var _ns_battery_pack_capacity = Float64(_t1_battery_pack_capacity - _t0_battery_pack_capacity) / Float64(N)
    print("MOJO_TIMING battery::battery_pack_capacity", _ns_battery_pack_capacity, _acc_battery_pack_capacity)
