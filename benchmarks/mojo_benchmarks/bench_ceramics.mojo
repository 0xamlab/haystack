"""bench_ceramics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ceramics import weibull_failure_probability, weibull_characteristic_strength, thermal_shock_resistance, youngs_modulus_porosity, sintering_shrinkage, density_from_archimedes, relative_density, porosity_from_density, fracture_toughness_indentation, dielectric_constant_mixture, coefficient_of_thermal_expansion, glass_transition_estimate
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

    var _acc_weibull_failure_probability: Float64 = 0.0
    var _t0_weibull_failure_probability = perf_counter_ns()
    for _ in range(N):
        _acc_weibull_failure_probability += weibull_failure_probability(0.5, 0.5, 0.5)
    var _t1_weibull_failure_probability = perf_counter_ns()
    var _ns_weibull_failure_probability = Float64(_t1_weibull_failure_probability - _t0_weibull_failure_probability) / Float64(N)
    print("MOJO_TIMING ceramics::weibull_failure_probability", _ns_weibull_failure_probability, _acc_weibull_failure_probability)
    var _acc_weibull_characteristic_strength: Float64 = 0.0
    var _t0_weibull_characteristic_strength = perf_counter_ns()
    for _ in range(N):
        _acc_weibull_characteristic_strength += weibull_characteristic_strength(0.5, 0.5)
    var _t1_weibull_characteristic_strength = perf_counter_ns()
    var _ns_weibull_characteristic_strength = Float64(_t1_weibull_characteristic_strength - _t0_weibull_characteristic_strength) / Float64(N)
    print("MOJO_TIMING ceramics::weibull_characteristic_strength", _ns_weibull_characteristic_strength, _acc_weibull_characteristic_strength)
    var _acc_thermal_shock_resistance: Float64 = 0.0
    var _t0_thermal_shock_resistance = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_shock_resistance += thermal_shock_resistance(0.5, 0.5, 0.5, 0.5)
    var _t1_thermal_shock_resistance = perf_counter_ns()
    var _ns_thermal_shock_resistance = Float64(_t1_thermal_shock_resistance - _t0_thermal_shock_resistance) / Float64(N)
    print("MOJO_TIMING ceramics::thermal_shock_resistance", _ns_thermal_shock_resistance, _acc_thermal_shock_resistance)
    var _acc_youngs_modulus_porosity: Float64 = 0.0
    var _t0_youngs_modulus_porosity = perf_counter_ns()
    for _ in range(N):
        _acc_youngs_modulus_porosity += youngs_modulus_porosity(0.5, 0.5, 0.5)
    var _t1_youngs_modulus_porosity = perf_counter_ns()
    var _ns_youngs_modulus_porosity = Float64(_t1_youngs_modulus_porosity - _t0_youngs_modulus_porosity) / Float64(N)
    print("MOJO_TIMING ceramics::youngs_modulus_porosity", _ns_youngs_modulus_porosity, _acc_youngs_modulus_porosity)
    var _acc_sintering_shrinkage: Float64 = 0.0
    var _t0_sintering_shrinkage = perf_counter_ns()
    for _ in range(N):
        _acc_sintering_shrinkage += sintering_shrinkage(0.5, 0.5)
    var _t1_sintering_shrinkage = perf_counter_ns()
    var _ns_sintering_shrinkage = Float64(_t1_sintering_shrinkage - _t0_sintering_shrinkage) / Float64(N)
    print("MOJO_TIMING ceramics::sintering_shrinkage", _ns_sintering_shrinkage, _acc_sintering_shrinkage)
    var _acc_density_from_archimedes: Float64 = 0.0
    var _t0_density_from_archimedes = perf_counter_ns()
    for _ in range(N):
        _acc_density_from_archimedes += density_from_archimedes(0.5, 0.5, 0.5, 0.5)
    var _t1_density_from_archimedes = perf_counter_ns()
    var _ns_density_from_archimedes = Float64(_t1_density_from_archimedes - _t0_density_from_archimedes) / Float64(N)
    print("MOJO_TIMING ceramics::density_from_archimedes", _ns_density_from_archimedes, _acc_density_from_archimedes)
    var _acc_relative_density: Float64 = 0.0
    var _t0_relative_density = perf_counter_ns()
    for _ in range(N):
        _acc_relative_density += relative_density(0.5, 0.5)
    var _t1_relative_density = perf_counter_ns()
    var _ns_relative_density = Float64(_t1_relative_density - _t0_relative_density) / Float64(N)
    print("MOJO_TIMING ceramics::relative_density", _ns_relative_density, _acc_relative_density)
    var _acc_porosity_from_density: Float64 = 0.0
    var _t0_porosity_from_density = perf_counter_ns()
    for _ in range(N):
        _acc_porosity_from_density += porosity_from_density(0.5, 0.5)
    var _t1_porosity_from_density = perf_counter_ns()
    var _ns_porosity_from_density = Float64(_t1_porosity_from_density - _t0_porosity_from_density) / Float64(N)
    print("MOJO_TIMING ceramics::porosity_from_density", _ns_porosity_from_density, _acc_porosity_from_density)
    var _acc_fracture_toughness_indentation: Float64 = 0.0
    var _t0_fracture_toughness_indentation = perf_counter_ns()
    for _ in range(N):
        _acc_fracture_toughness_indentation += fracture_toughness_indentation(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_fracture_toughness_indentation = perf_counter_ns()
    var _ns_fracture_toughness_indentation = Float64(_t1_fracture_toughness_indentation - _t0_fracture_toughness_indentation) / Float64(N)
    print("MOJO_TIMING ceramics::fracture_toughness_indentation", _ns_fracture_toughness_indentation, _acc_fracture_toughness_indentation)
    var _acc_dielectric_constant_mixture: Float64 = 0.0
    var _t0_dielectric_constant_mixture = perf_counter_ns()
    for _ in range(N):
        _acc_dielectric_constant_mixture += dielectric_constant_mixture(0.5, 0.5, 0.5, 0.5)
    var _t1_dielectric_constant_mixture = perf_counter_ns()
    var _ns_dielectric_constant_mixture = Float64(_t1_dielectric_constant_mixture - _t0_dielectric_constant_mixture) / Float64(N)
    print("MOJO_TIMING ceramics::dielectric_constant_mixture", _ns_dielectric_constant_mixture, _acc_dielectric_constant_mixture)
    var _acc_coefficient_of_thermal_expansion: Float64 = 0.0
    var _t0_coefficient_of_thermal_expansion = perf_counter_ns()
    for _ in range(N):
        _acc_coefficient_of_thermal_expansion += coefficient_of_thermal_expansion(0.5, 0.5, 0.5)
    var _t1_coefficient_of_thermal_expansion = perf_counter_ns()
    var _ns_coefficient_of_thermal_expansion = Float64(_t1_coefficient_of_thermal_expansion - _t0_coefficient_of_thermal_expansion) / Float64(N)
    print("MOJO_TIMING ceramics::coefficient_of_thermal_expansion", _ns_coefficient_of_thermal_expansion, _acc_coefficient_of_thermal_expansion)
    var _acc_glass_transition_estimate: Float64 = 0.0
    var _t0_glass_transition_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_glass_transition_estimate += glass_transition_estimate(0.5)
    var _t1_glass_transition_estimate = perf_counter_ns()
    var _ns_glass_transition_estimate = Float64(_t1_glass_transition_estimate - _t0_glass_transition_estimate) / Float64(N)
    print("MOJO_TIMING ceramics::glass_transition_estimate", _ns_glass_transition_estimate, _acc_glass_transition_estimate)
