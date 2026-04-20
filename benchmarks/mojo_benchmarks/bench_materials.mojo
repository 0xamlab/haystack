"""bench_materials.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from materials import youngs_modulus, shear_modulus, bulk_modulus, stress_from_force, strain_from_deformation, thermal_expansion, safety_factor, stress_concentration, fatigue_life, beam_deflection_cantilever, moment_of_inertia_rect, poisson_ratio_from_moduli
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

    var _acc_youngs_modulus: Float64 = 0.0
    var _t0_youngs_modulus = perf_counter_ns()
    for _ in range(N):
        _acc_youngs_modulus += youngs_modulus(0.5, 0.5)
    var _t1_youngs_modulus = perf_counter_ns()
    var _ns_youngs_modulus = Float64(_t1_youngs_modulus - _t0_youngs_modulus) / Float64(N)
    print("MOJO_TIMING materials::youngs_modulus", _ns_youngs_modulus, _acc_youngs_modulus)
    var _acc_shear_modulus: Float64 = 0.0
    var _t0_shear_modulus = perf_counter_ns()
    for _ in range(N):
        _acc_shear_modulus += shear_modulus(0.5, 0.5)
    var _t1_shear_modulus = perf_counter_ns()
    var _ns_shear_modulus = Float64(_t1_shear_modulus - _t0_shear_modulus) / Float64(N)
    print("MOJO_TIMING materials::shear_modulus", _ns_shear_modulus, _acc_shear_modulus)
    var _acc_bulk_modulus: Float64 = 0.0
    var _t0_bulk_modulus = perf_counter_ns()
    for _ in range(N):
        _acc_bulk_modulus += bulk_modulus(0.5, 0.5)
    var _t1_bulk_modulus = perf_counter_ns()
    var _ns_bulk_modulus = Float64(_t1_bulk_modulus - _t0_bulk_modulus) / Float64(N)
    print("MOJO_TIMING materials::bulk_modulus", _ns_bulk_modulus, _acc_bulk_modulus)
    var _acc_stress_from_force: Float64 = 0.0
    var _t0_stress_from_force = perf_counter_ns()
    for _ in range(N):
        _acc_stress_from_force += stress_from_force(0.5, 0.5)
    var _t1_stress_from_force = perf_counter_ns()
    var _ns_stress_from_force = Float64(_t1_stress_from_force - _t0_stress_from_force) / Float64(N)
    print("MOJO_TIMING materials::stress_from_force", _ns_stress_from_force, _acc_stress_from_force)
    var _acc_strain_from_deformation: Float64 = 0.0
    var _t0_strain_from_deformation = perf_counter_ns()
    for _ in range(N):
        _acc_strain_from_deformation += strain_from_deformation(0.5, 0.5)
    var _t1_strain_from_deformation = perf_counter_ns()
    var _ns_strain_from_deformation = Float64(_t1_strain_from_deformation - _t0_strain_from_deformation) / Float64(N)
    print("MOJO_TIMING materials::strain_from_deformation", _ns_strain_from_deformation, _acc_strain_from_deformation)
    var _acc_thermal_expansion: Float64 = 0.0
    var _t0_thermal_expansion = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_expansion += thermal_expansion(0.5, 0.5, 0.5)
    var _t1_thermal_expansion = perf_counter_ns()
    var _ns_thermal_expansion = Float64(_t1_thermal_expansion - _t0_thermal_expansion) / Float64(N)
    print("MOJO_TIMING materials::thermal_expansion", _ns_thermal_expansion, _acc_thermal_expansion)
    var _acc_safety_factor: Float64 = 0.0
    var _t0_safety_factor = perf_counter_ns()
    for _ in range(N):
        _acc_safety_factor += safety_factor(0.5, 0.5)
    var _t1_safety_factor = perf_counter_ns()
    var _ns_safety_factor = Float64(_t1_safety_factor - _t0_safety_factor) / Float64(N)
    print("MOJO_TIMING materials::safety_factor", _ns_safety_factor, _acc_safety_factor)
    var _acc_stress_concentration: Float64 = 0.0
    var _t0_stress_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_stress_concentration += stress_concentration(0.5, 0.5)
    var _t1_stress_concentration = perf_counter_ns()
    var _ns_stress_concentration = Float64(_t1_stress_concentration - _t0_stress_concentration) / Float64(N)
    print("MOJO_TIMING materials::stress_concentration", _ns_stress_concentration, _acc_stress_concentration)
    var _acc_fatigue_life: Float64 = 0.0
    var _t0_fatigue_life = perf_counter_ns()
    for _ in range(N):
        _acc_fatigue_life += fatigue_life(0.5, 0.5, 0.5)
    var _t1_fatigue_life = perf_counter_ns()
    var _ns_fatigue_life = Float64(_t1_fatigue_life - _t0_fatigue_life) / Float64(N)
    print("MOJO_TIMING materials::fatigue_life", _ns_fatigue_life, _acc_fatigue_life)
    var _acc_beam_deflection_cantilever: Float64 = 0.0
    var _t0_beam_deflection_cantilever = perf_counter_ns()
    for _ in range(N):
        _acc_beam_deflection_cantilever += beam_deflection_cantilever(0.5, 0.5, 0.5, 0.5)
    var _t1_beam_deflection_cantilever = perf_counter_ns()
    var _ns_beam_deflection_cantilever = Float64(_t1_beam_deflection_cantilever - _t0_beam_deflection_cantilever) / Float64(N)
    print("MOJO_TIMING materials::beam_deflection_cantilever", _ns_beam_deflection_cantilever, _acc_beam_deflection_cantilever)
    var _acc_moment_of_inertia_rect: Float64 = 0.0
    var _t0_moment_of_inertia_rect = perf_counter_ns()
    for _ in range(N):
        _acc_moment_of_inertia_rect += moment_of_inertia_rect(0.5, 0.5)
    var _t1_moment_of_inertia_rect = perf_counter_ns()
    var _ns_moment_of_inertia_rect = Float64(_t1_moment_of_inertia_rect - _t0_moment_of_inertia_rect) / Float64(N)
    print("MOJO_TIMING materials::moment_of_inertia_rect", _ns_moment_of_inertia_rect, _acc_moment_of_inertia_rect)
    var _acc_poisson_ratio_from_moduli: Float64 = 0.0
    var _t0_poisson_ratio_from_moduli = perf_counter_ns()
    for _ in range(N):
        _acc_poisson_ratio_from_moduli += poisson_ratio_from_moduli(0.5, 0.5)
    var _t1_poisson_ratio_from_moduli = perf_counter_ns()
    var _ns_poisson_ratio_from_moduli = Float64(_t1_poisson_ratio_from_moduli - _t0_poisson_ratio_from_moduli) / Float64(N)
    print("MOJO_TIMING materials::poisson_ratio_from_moduli", _ns_poisson_ratio_from_moduli, _acc_poisson_ratio_from_moduli)
