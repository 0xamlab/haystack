"""bench_combustion.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from combustion import stoichiometric_air_fuel_ratio, equivalence_ratio, excess_air_percentage, adiabatic_flame_temp_estimate, lower_heating_value_methane, thermal_efficiency, carnot_efficiency, brake_specific_fuel_consumption, combustion_efficiency, flame_speed_laminar, nox_formation_rate, heat_release_rate
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

    var _acc_stoichiometric_air_fuel_ratio: Float64 = 0.0
    var _t0_stoichiometric_air_fuel_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_stoichiometric_air_fuel_ratio += stoichiometric_air_fuel_ratio(0.5, 0.5, 0.5)
    var _t1_stoichiometric_air_fuel_ratio = perf_counter_ns()
    var _ns_stoichiometric_air_fuel_ratio = Float64(_t1_stoichiometric_air_fuel_ratio - _t0_stoichiometric_air_fuel_ratio) / Float64(N)
    print("MOJO_TIMING combustion::stoichiometric_air_fuel_ratio", _ns_stoichiometric_air_fuel_ratio, _acc_stoichiometric_air_fuel_ratio)
    var _acc_equivalence_ratio: Float64 = 0.0
    var _t0_equivalence_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_equivalence_ratio += equivalence_ratio(0.5, 0.5)
    var _t1_equivalence_ratio = perf_counter_ns()
    var _ns_equivalence_ratio = Float64(_t1_equivalence_ratio - _t0_equivalence_ratio) / Float64(N)
    print("MOJO_TIMING combustion::equivalence_ratio", _ns_equivalence_ratio, _acc_equivalence_ratio)
    var _acc_excess_air_percentage: Float64 = 0.0
    var _t0_excess_air_percentage = perf_counter_ns()
    for _ in range(N):
        _acc_excess_air_percentage += excess_air_percentage(0.5)
    var _t1_excess_air_percentage = perf_counter_ns()
    var _ns_excess_air_percentage = Float64(_t1_excess_air_percentage - _t0_excess_air_percentage) / Float64(N)
    print("MOJO_TIMING combustion::excess_air_percentage", _ns_excess_air_percentage, _acc_excess_air_percentage)
    var _acc_adiabatic_flame_temp_estimate: Float64 = 0.0
    var _t0_adiabatic_flame_temp_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_adiabatic_flame_temp_estimate += adiabatic_flame_temp_estimate(0.5, 0.5, 0.5, 0.5)
    var _t1_adiabatic_flame_temp_estimate = perf_counter_ns()
    var _ns_adiabatic_flame_temp_estimate = Float64(_t1_adiabatic_flame_temp_estimate - _t0_adiabatic_flame_temp_estimate) / Float64(N)
    print("MOJO_TIMING combustion::adiabatic_flame_temp_estimate", _ns_adiabatic_flame_temp_estimate, _acc_adiabatic_flame_temp_estimate)
    var _acc_lower_heating_value_methane: Float64 = 0.0
    var _t0_lower_heating_value_methane = perf_counter_ns()
    for _ in range(N):
        _acc_lower_heating_value_methane += lower_heating_value_methane()
    var _t1_lower_heating_value_methane = perf_counter_ns()
    var _ns_lower_heating_value_methane = Float64(_t1_lower_heating_value_methane - _t0_lower_heating_value_methane) / Float64(N)
    print("MOJO_TIMING combustion::lower_heating_value_methane", _ns_lower_heating_value_methane, _acc_lower_heating_value_methane)
    var _acc_thermal_efficiency: Float64 = 0.0
    var _t0_thermal_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_efficiency += thermal_efficiency(0.5, 0.5)
    var _t1_thermal_efficiency = perf_counter_ns()
    var _ns_thermal_efficiency = Float64(_t1_thermal_efficiency - _t0_thermal_efficiency) / Float64(N)
    print("MOJO_TIMING combustion::thermal_efficiency", _ns_thermal_efficiency, _acc_thermal_efficiency)
    var _acc_carnot_efficiency: Float64 = 0.0
    var _t0_carnot_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_carnot_efficiency += carnot_efficiency(0.5, 0.5)
    var _t1_carnot_efficiency = perf_counter_ns()
    var _ns_carnot_efficiency = Float64(_t1_carnot_efficiency - _t0_carnot_efficiency) / Float64(N)
    print("MOJO_TIMING combustion::carnot_efficiency", _ns_carnot_efficiency, _acc_carnot_efficiency)
    var _acc_brake_specific_fuel_consumption: Float64 = 0.0
    var _t0_brake_specific_fuel_consumption = perf_counter_ns()
    for _ in range(N):
        _acc_brake_specific_fuel_consumption += brake_specific_fuel_consumption(0.5, 0.5)
    var _t1_brake_specific_fuel_consumption = perf_counter_ns()
    var _ns_brake_specific_fuel_consumption = Float64(_t1_brake_specific_fuel_consumption - _t0_brake_specific_fuel_consumption) / Float64(N)
    print("MOJO_TIMING combustion::brake_specific_fuel_consumption", _ns_brake_specific_fuel_consumption, _acc_brake_specific_fuel_consumption)
    var _acc_combustion_efficiency: Float64 = 0.0
    var _t0_combustion_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_combustion_efficiency += combustion_efficiency(0.5, 0.5)
    var _t1_combustion_efficiency = perf_counter_ns()
    var _ns_combustion_efficiency = Float64(_t1_combustion_efficiency - _t0_combustion_efficiency) / Float64(N)
    print("MOJO_TIMING combustion::combustion_efficiency", _ns_combustion_efficiency, _acc_combustion_efficiency)
    var _acc_flame_speed_laminar: Float64 = 0.0
    var _t0_flame_speed_laminar = perf_counter_ns()
    for _ in range(N):
        _acc_flame_speed_laminar += flame_speed_laminar(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_flame_speed_laminar = perf_counter_ns()
    var _ns_flame_speed_laminar = Float64(_t1_flame_speed_laminar - _t0_flame_speed_laminar) / Float64(N)
    print("MOJO_TIMING combustion::flame_speed_laminar", _ns_flame_speed_laminar, _acc_flame_speed_laminar)
    var _acc_nox_formation_rate: Float64 = 0.0
    var _t0_nox_formation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_nox_formation_rate += nox_formation_rate(0.5, 0.5)
    var _t1_nox_formation_rate = perf_counter_ns()
    var _ns_nox_formation_rate = Float64(_t1_nox_formation_rate - _t0_nox_formation_rate) / Float64(N)
    print("MOJO_TIMING combustion::nox_formation_rate", _ns_nox_formation_rate, _acc_nox_formation_rate)
    var _acc_heat_release_rate: Float64 = 0.0
    var _t0_heat_release_rate = perf_counter_ns()
    for _ in range(N):
        _acc_heat_release_rate += heat_release_rate(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_heat_release_rate = perf_counter_ns()
    var _ns_heat_release_rate = Float64(_t1_heat_release_rate - _t0_heat_release_rate) / Float64(N)
    print("MOJO_TIMING combustion::heat_release_rate", _ns_heat_release_rate, _acc_heat_release_rate)
