"""bench_metallurgy.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from metallurgy import hall_petch, johnson_cook_flow_stress, hardness_to_tensile, carbon_equivalent, jominy_distance_to_hardness, avrami_fraction, quench_severity, tempering_parameter, density_of_alloy_rule_of_mixtures, thermal_conductivity_wiedemann_franz, strain_hardening_exponent_from_points, fatigue_life_basquin
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

    var _acc_hall_petch: Float64 = 0.0
    var _t0_hall_petch = perf_counter_ns()
    for _ in range(N):
        _acc_hall_petch += hall_petch(0.5, 0.5, 0.5)
    var _t1_hall_petch = perf_counter_ns()
    var _ns_hall_petch = Float64(_t1_hall_petch - _t0_hall_petch) / Float64(N)
    print("MOJO_TIMING metallurgy::hall_petch", _ns_hall_petch, _acc_hall_petch)
    var _acc_johnson_cook_flow_stress: Float64 = 0.0
    var _t0_johnson_cook_flow_stress = perf_counter_ns()
    for _ in range(N):
        _acc_johnson_cook_flow_stress += johnson_cook_flow_stress(0.5, 0.5, 0.5, 0.5)
    var _t1_johnson_cook_flow_stress = perf_counter_ns()
    var _ns_johnson_cook_flow_stress = Float64(_t1_johnson_cook_flow_stress - _t0_johnson_cook_flow_stress) / Float64(N)
    print("MOJO_TIMING metallurgy::johnson_cook_flow_stress", _ns_johnson_cook_flow_stress, _acc_johnson_cook_flow_stress)
    var _acc_hardness_to_tensile: Float64 = 0.0
    var _t0_hardness_to_tensile = perf_counter_ns()
    for _ in range(N):
        _acc_hardness_to_tensile += hardness_to_tensile(0.5)
    var _t1_hardness_to_tensile = perf_counter_ns()
    var _ns_hardness_to_tensile = Float64(_t1_hardness_to_tensile - _t0_hardness_to_tensile) / Float64(N)
    print("MOJO_TIMING metallurgy::hardness_to_tensile", _ns_hardness_to_tensile, _acc_hardness_to_tensile)
    var _acc_carbon_equivalent: Float64 = 0.0
    var _t0_carbon_equivalent = perf_counter_ns()
    for _ in range(N):
        _acc_carbon_equivalent += carbon_equivalent(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_carbon_equivalent = perf_counter_ns()
    var _ns_carbon_equivalent = Float64(_t1_carbon_equivalent - _t0_carbon_equivalent) / Float64(N)
    print("MOJO_TIMING metallurgy::carbon_equivalent", _ns_carbon_equivalent, _acc_carbon_equivalent)
    var _acc_jominy_distance_to_hardness: Float64 = 0.0
    var _t0_jominy_distance_to_hardness = perf_counter_ns()
    for _ in range(N):
        _acc_jominy_distance_to_hardness += jominy_distance_to_hardness(0.5, 0.5, 0.5)
    var _t1_jominy_distance_to_hardness = perf_counter_ns()
    var _ns_jominy_distance_to_hardness = Float64(_t1_jominy_distance_to_hardness - _t0_jominy_distance_to_hardness) / Float64(N)
    print("MOJO_TIMING metallurgy::jominy_distance_to_hardness", _ns_jominy_distance_to_hardness, _acc_jominy_distance_to_hardness)
    var _acc_avrami_fraction: Float64 = 0.0
    var _t0_avrami_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_avrami_fraction += avrami_fraction(0.5, 0.5, 0.5)
    var _t1_avrami_fraction = perf_counter_ns()
    var _ns_avrami_fraction = Float64(_t1_avrami_fraction - _t0_avrami_fraction) / Float64(N)
    print("MOJO_TIMING metallurgy::avrami_fraction", _ns_avrami_fraction, _acc_avrami_fraction)
    var _acc_quench_severity: Float64 = 0.0
    var _t0_quench_severity = perf_counter_ns()
    for _ in range(N):
        _acc_quench_severity += quench_severity(0.5, 0.5)
    var _t1_quench_severity = perf_counter_ns()
    var _ns_quench_severity = Float64(_t1_quench_severity - _t0_quench_severity) / Float64(N)
    print("MOJO_TIMING metallurgy::quench_severity", _ns_quench_severity, _acc_quench_severity)
    var _acc_tempering_parameter: Float64 = 0.0
    var _t0_tempering_parameter = perf_counter_ns()
    for _ in range(N):
        _acc_tempering_parameter += tempering_parameter(0.5, 0.5, 0.5)
    var _t1_tempering_parameter = perf_counter_ns()
    var _ns_tempering_parameter = Float64(_t1_tempering_parameter - _t0_tempering_parameter) / Float64(N)
    print("MOJO_TIMING metallurgy::tempering_parameter", _ns_tempering_parameter, _acc_tempering_parameter)
    var _acc_density_of_alloy_rule_of_mixtures: Float64 = 0.0
    var _t0_density_of_alloy_rule_of_mixtures = perf_counter_ns()
    for _ in range(N):
        _acc_density_of_alloy_rule_of_mixtures += density_of_alloy_rule_of_mixtures(0.5, 0.5, 0.5, 0.5)
    var _t1_density_of_alloy_rule_of_mixtures = perf_counter_ns()
    var _ns_density_of_alloy_rule_of_mixtures = Float64(_t1_density_of_alloy_rule_of_mixtures - _t0_density_of_alloy_rule_of_mixtures) / Float64(N)
    print("MOJO_TIMING metallurgy::density_of_alloy_rule_of_mixtures", _ns_density_of_alloy_rule_of_mixtures, _acc_density_of_alloy_rule_of_mixtures)
    var _acc_thermal_conductivity_wiedemann_franz: Float64 = 0.0
    var _t0_thermal_conductivity_wiedemann_franz = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_conductivity_wiedemann_franz += thermal_conductivity_wiedemann_franz(0.5, 0.5, 0.5)
    var _t1_thermal_conductivity_wiedemann_franz = perf_counter_ns()
    var _ns_thermal_conductivity_wiedemann_franz = Float64(_t1_thermal_conductivity_wiedemann_franz - _t0_thermal_conductivity_wiedemann_franz) / Float64(N)
    print("MOJO_TIMING metallurgy::thermal_conductivity_wiedemann_franz", _ns_thermal_conductivity_wiedemann_franz, _acc_thermal_conductivity_wiedemann_franz)
    var _acc_strain_hardening_exponent_from_points: Float64 = 0.0
    var _t0_strain_hardening_exponent_from_points = perf_counter_ns()
    for _ in range(N):
        _acc_strain_hardening_exponent_from_points += strain_hardening_exponent_from_points(0.5, 0.5, 0.5, 0.5)
    var _t1_strain_hardening_exponent_from_points = perf_counter_ns()
    var _ns_strain_hardening_exponent_from_points = Float64(_t1_strain_hardening_exponent_from_points - _t0_strain_hardening_exponent_from_points) / Float64(N)
    print("MOJO_TIMING metallurgy::strain_hardening_exponent_from_points", _ns_strain_hardening_exponent_from_points, _acc_strain_hardening_exponent_from_points)
    var _acc_fatigue_life_basquin: Float64 = 0.0
    var _t0_fatigue_life_basquin = perf_counter_ns()
    for _ in range(N):
        _acc_fatigue_life_basquin += fatigue_life_basquin(0.5, 0.5, 0.5)
    var _t1_fatigue_life_basquin = perf_counter_ns()
    var _ns_fatigue_life_basquin = Float64(_t1_fatigue_life_basquin - _t0_fatigue_life_basquin) / Float64(N)
    print("MOJO_TIMING metallurgy::fatigue_life_basquin", _ns_fatigue_life_basquin, _acc_fatigue_life_basquin)
