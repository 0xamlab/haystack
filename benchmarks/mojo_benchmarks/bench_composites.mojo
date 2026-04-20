"""bench_composites.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from composites import rule_of_mixtures_modulus, inverse_rule_of_mixtures, composite_density, fiber_volume_fraction, laminate_thickness, specific_stiffness, specific_strength, halpin_tsai, critical_fiber_length, shear_lag_stress_transfer, impact_energy_charpy, void_content
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

    var _acc_rule_of_mixtures_modulus: Float64 = 0.0
    var _t0_rule_of_mixtures_modulus = perf_counter_ns()
    for _ in range(N):
        _acc_rule_of_mixtures_modulus += rule_of_mixtures_modulus(0.5, 0.5, 0.5)
    var _t1_rule_of_mixtures_modulus = perf_counter_ns()
    var _ns_rule_of_mixtures_modulus = Float64(_t1_rule_of_mixtures_modulus - _t0_rule_of_mixtures_modulus) / Float64(N)
    print("MOJO_TIMING composites::rule_of_mixtures_modulus", _ns_rule_of_mixtures_modulus, _acc_rule_of_mixtures_modulus)
    var _acc_inverse_rule_of_mixtures: Float64 = 0.0
    var _t0_inverse_rule_of_mixtures = perf_counter_ns()
    for _ in range(N):
        _acc_inverse_rule_of_mixtures += inverse_rule_of_mixtures(0.5, 0.5, 0.5)
    var _t1_inverse_rule_of_mixtures = perf_counter_ns()
    var _ns_inverse_rule_of_mixtures = Float64(_t1_inverse_rule_of_mixtures - _t0_inverse_rule_of_mixtures) / Float64(N)
    print("MOJO_TIMING composites::inverse_rule_of_mixtures", _ns_inverse_rule_of_mixtures, _acc_inverse_rule_of_mixtures)
    var _acc_composite_density: Float64 = 0.0
    var _t0_composite_density = perf_counter_ns()
    for _ in range(N):
        _acc_composite_density += composite_density(0.5, 0.5, 0.5)
    var _t1_composite_density = perf_counter_ns()
    var _ns_composite_density = Float64(_t1_composite_density - _t0_composite_density) / Float64(N)
    print("MOJO_TIMING composites::composite_density", _ns_composite_density, _acc_composite_density)
    var _acc_fiber_volume_fraction: Float64 = 0.0
    var _t0_fiber_volume_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_fiber_volume_fraction += fiber_volume_fraction(0.5, 0.5, 0.5, 0.5)
    var _t1_fiber_volume_fraction = perf_counter_ns()
    var _ns_fiber_volume_fraction = Float64(_t1_fiber_volume_fraction - _t0_fiber_volume_fraction) / Float64(N)
    print("MOJO_TIMING composites::fiber_volume_fraction", _ns_fiber_volume_fraction, _acc_fiber_volume_fraction)
    var _acc_laminate_thickness: Float64 = 0.0
    var _t0_laminate_thickness = perf_counter_ns()
    for _ in range(N):
        _acc_laminate_thickness += laminate_thickness(0.5, 0.5)
    var _t1_laminate_thickness = perf_counter_ns()
    var _ns_laminate_thickness = Float64(_t1_laminate_thickness - _t0_laminate_thickness) / Float64(N)
    print("MOJO_TIMING composites::laminate_thickness", _ns_laminate_thickness, _acc_laminate_thickness)
    var _acc_specific_stiffness: Float64 = 0.0
    var _t0_specific_stiffness = perf_counter_ns()
    for _ in range(N):
        _acc_specific_stiffness += specific_stiffness(0.5, 0.5)
    var _t1_specific_stiffness = perf_counter_ns()
    var _ns_specific_stiffness = Float64(_t1_specific_stiffness - _t0_specific_stiffness) / Float64(N)
    print("MOJO_TIMING composites::specific_stiffness", _ns_specific_stiffness, _acc_specific_stiffness)
    var _acc_specific_strength: Float64 = 0.0
    var _t0_specific_strength = perf_counter_ns()
    for _ in range(N):
        _acc_specific_strength += specific_strength(0.5, 0.5)
    var _t1_specific_strength = perf_counter_ns()
    var _ns_specific_strength = Float64(_t1_specific_strength - _t0_specific_strength) / Float64(N)
    print("MOJO_TIMING composites::specific_strength", _ns_specific_strength, _acc_specific_strength)
    var _acc_halpin_tsai: Float64 = 0.0
    var _t0_halpin_tsai = perf_counter_ns()
    for _ in range(N):
        _acc_halpin_tsai += halpin_tsai(0.5, 0.5, 0.5, 0.5)
    var _t1_halpin_tsai = perf_counter_ns()
    var _ns_halpin_tsai = Float64(_t1_halpin_tsai - _t0_halpin_tsai) / Float64(N)
    print("MOJO_TIMING composites::halpin_tsai", _ns_halpin_tsai, _acc_halpin_tsai)
    var _acc_critical_fiber_length: Float64 = 0.0
    var _t0_critical_fiber_length = perf_counter_ns()
    for _ in range(N):
        _acc_critical_fiber_length += critical_fiber_length(0.5, 0.5, 0.5)
    var _t1_critical_fiber_length = perf_counter_ns()
    var _ns_critical_fiber_length = Float64(_t1_critical_fiber_length - _t0_critical_fiber_length) / Float64(N)
    print("MOJO_TIMING composites::critical_fiber_length", _ns_critical_fiber_length, _acc_critical_fiber_length)
    var _acc_shear_lag_stress_transfer: Float64 = 0.0
    var _t0_shear_lag_stress_transfer = perf_counter_ns()
    for _ in range(N):
        _acc_shear_lag_stress_transfer += shear_lag_stress_transfer(0.5, 0.5, 0.5)
    var _t1_shear_lag_stress_transfer = perf_counter_ns()
    var _ns_shear_lag_stress_transfer = Float64(_t1_shear_lag_stress_transfer - _t0_shear_lag_stress_transfer) / Float64(N)
    print("MOJO_TIMING composites::shear_lag_stress_transfer", _ns_shear_lag_stress_transfer, _acc_shear_lag_stress_transfer)
    var _acc_impact_energy_charpy: Float64 = 0.0
    var _t0_impact_energy_charpy = perf_counter_ns()
    for _ in range(N):
        _acc_impact_energy_charpy += impact_energy_charpy(0.5, 0.5)
    var _t1_impact_energy_charpy = perf_counter_ns()
    var _ns_impact_energy_charpy = Float64(_t1_impact_energy_charpy - _t0_impact_energy_charpy) / Float64(N)
    print("MOJO_TIMING composites::impact_energy_charpy", _ns_impact_energy_charpy, _acc_impact_energy_charpy)
    var _acc_void_content: Float64 = 0.0
    var _t0_void_content = perf_counter_ns()
    for _ in range(N):
        _acc_void_content += void_content(0.5, 0.5)
    var _t1_void_content = perf_counter_ns()
    var _ns_void_content = Float64(_t1_void_content - _t0_void_content) / Float64(N)
    print("MOJO_TIMING composites::void_content", _ns_void_content, _acc_void_content)
