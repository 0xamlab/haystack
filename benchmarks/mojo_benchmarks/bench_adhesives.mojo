"""bench_adhesives.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from adhesives import lap_shear_strength, peel_strength, bond_line_thickness, coverage_rate, pot_life_temperature_adjusted, cure_time_temperature, joint_efficiency, thermal_cycle_life, viscosity_temperature, surface_energy_contact_angle, open_time_estimate, bond_area_from_load
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

    var _acc_lap_shear_strength: Float64 = 0.0
    var _t0_lap_shear_strength = perf_counter_ns()
    for _ in range(N):
        _acc_lap_shear_strength += lap_shear_strength(0.5, 0.5)
    var _t1_lap_shear_strength = perf_counter_ns()
    var _ns_lap_shear_strength = Float64(_t1_lap_shear_strength - _t0_lap_shear_strength) / Float64(N)
    print("MOJO_TIMING adhesives::lap_shear_strength", _ns_lap_shear_strength, _acc_lap_shear_strength)
    var _acc_peel_strength: Float64 = 0.0
    var _t0_peel_strength = perf_counter_ns()
    for _ in range(N):
        _acc_peel_strength += peel_strength(0.5, 0.5)
    var _t1_peel_strength = perf_counter_ns()
    var _ns_peel_strength = Float64(_t1_peel_strength - _t0_peel_strength) / Float64(N)
    print("MOJO_TIMING adhesives::peel_strength", _ns_peel_strength, _acc_peel_strength)
    var _acc_bond_line_thickness: Float64 = 0.0
    var _t0_bond_line_thickness = perf_counter_ns()
    for _ in range(N):
        _acc_bond_line_thickness += bond_line_thickness(0.5)
    var _t1_bond_line_thickness = perf_counter_ns()
    var _ns_bond_line_thickness = Float64(_t1_bond_line_thickness - _t0_bond_line_thickness) / Float64(N)
    print("MOJO_TIMING adhesives::bond_line_thickness", _ns_bond_line_thickness, _acc_bond_line_thickness)
    var _acc_coverage_rate: Float64 = 0.0
    var _t0_coverage_rate = perf_counter_ns()
    for _ in range(N):
        _acc_coverage_rate += coverage_rate(0.5, 0.5)
    var _t1_coverage_rate = perf_counter_ns()
    var _ns_coverage_rate = Float64(_t1_coverage_rate - _t0_coverage_rate) / Float64(N)
    print("MOJO_TIMING adhesives::coverage_rate", _ns_coverage_rate, _acc_coverage_rate)
    var _acc_pot_life_temperature_adjusted: Float64 = 0.0
    var _t0_pot_life_temperature_adjusted = perf_counter_ns()
    for _ in range(N):
        _acc_pot_life_temperature_adjusted += pot_life_temperature_adjusted(0.5, 0.5, 0.5, 0.5)
    var _t1_pot_life_temperature_adjusted = perf_counter_ns()
    var _ns_pot_life_temperature_adjusted = Float64(_t1_pot_life_temperature_adjusted - _t0_pot_life_temperature_adjusted) / Float64(N)
    print("MOJO_TIMING adhesives::pot_life_temperature_adjusted", _ns_pot_life_temperature_adjusted, _acc_pot_life_temperature_adjusted)
    var _acc_cure_time_temperature: Float64 = 0.0
    var _t0_cure_time_temperature = perf_counter_ns()
    for _ in range(N):
        _acc_cure_time_temperature += cure_time_temperature(0.5, 0.5, 0.5, 0.5)
    var _t1_cure_time_temperature = perf_counter_ns()
    var _ns_cure_time_temperature = Float64(_t1_cure_time_temperature - _t0_cure_time_temperature) / Float64(N)
    print("MOJO_TIMING adhesives::cure_time_temperature", _ns_cure_time_temperature, _acc_cure_time_temperature)
    var _acc_joint_efficiency: Float64 = 0.0
    var _t0_joint_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_joint_efficiency += joint_efficiency(0.5, 0.5)
    var _t1_joint_efficiency = perf_counter_ns()
    var _ns_joint_efficiency = Float64(_t1_joint_efficiency - _t0_joint_efficiency) / Float64(N)
    print("MOJO_TIMING adhesives::joint_efficiency", _ns_joint_efficiency, _acc_joint_efficiency)
    var _acc_thermal_cycle_life: Float64 = 0.0
    var _t0_thermal_cycle_life = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_cycle_life += thermal_cycle_life(0.5, 0.5, 0.5, 0.5)
    var _t1_thermal_cycle_life = perf_counter_ns()
    var _ns_thermal_cycle_life = Float64(_t1_thermal_cycle_life - _t0_thermal_cycle_life) / Float64(N)
    print("MOJO_TIMING adhesives::thermal_cycle_life", _ns_thermal_cycle_life, _acc_thermal_cycle_life)
    var _acc_viscosity_temperature: Float64 = 0.0
    var _t0_viscosity_temperature = perf_counter_ns()
    for _ in range(N):
        _acc_viscosity_temperature += viscosity_temperature(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_viscosity_temperature = perf_counter_ns()
    var _ns_viscosity_temperature = Float64(_t1_viscosity_temperature - _t0_viscosity_temperature) / Float64(N)
    print("MOJO_TIMING adhesives::viscosity_temperature", _ns_viscosity_temperature, _acc_viscosity_temperature)
    var _acc_surface_energy_contact_angle: Float64 = 0.0
    var _t0_surface_energy_contact_angle = perf_counter_ns()
    for _ in range(N):
        _acc_surface_energy_contact_angle += surface_energy_contact_angle(0.5, 0.5)
    var _t1_surface_energy_contact_angle = perf_counter_ns()
    var _ns_surface_energy_contact_angle = Float64(_t1_surface_energy_contact_angle - _t0_surface_energy_contact_angle) / Float64(N)
    print("MOJO_TIMING adhesives::surface_energy_contact_angle", _ns_surface_energy_contact_angle, _acc_surface_energy_contact_angle)
    var _acc_open_time_estimate: Float64 = 0.0
    var _t0_open_time_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_open_time_estimate += open_time_estimate(0.5, 0.5)
    var _t1_open_time_estimate = perf_counter_ns()
    var _ns_open_time_estimate = Float64(_t1_open_time_estimate - _t0_open_time_estimate) / Float64(N)
    print("MOJO_TIMING adhesives::open_time_estimate", _ns_open_time_estimate, _acc_open_time_estimate)
    var _acc_bond_area_from_load: Float64 = 0.0
    var _t0_bond_area_from_load = perf_counter_ns()
    for _ in range(N):
        _acc_bond_area_from_load += bond_area_from_load(0.5, 0.5, 0.5)
    var _t1_bond_area_from_load = perf_counter_ns()
    var _ns_bond_area_from_load = Float64(_t1_bond_area_from_load - _t0_bond_area_from_load) / Float64(N)
    print("MOJO_TIMING adhesives::bond_area_from_load", _ns_bond_area_from_load, _acc_bond_area_from_load)
