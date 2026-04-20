"""bench_structural.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from structural import bending_stress, shear_stress_beam, moment_of_inertia_rect, section_modulus_rect, deflection_cantilever_point, deflection_simply_supported_center, euler_buckling_load, slenderness_ratio, axial_stress, combined_stress_von_mises, safety_factor, natural_frequency_cantilever
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

    var _acc_bending_stress: Float64 = 0.0
    var _t0_bending_stress = perf_counter_ns()
    for _ in range(N):
        _acc_bending_stress += bending_stress(0.5, 0.5)
    var _t1_bending_stress = perf_counter_ns()
    var _ns_bending_stress = Float64(_t1_bending_stress - _t0_bending_stress) / Float64(N)
    print("MOJO_TIMING structural::bending_stress", _ns_bending_stress, _acc_bending_stress)
    var _acc_shear_stress_beam: Float64 = 0.0
    var _t0_shear_stress_beam = perf_counter_ns()
    for _ in range(N):
        _acc_shear_stress_beam += shear_stress_beam(0.5, 0.5)
    var _t1_shear_stress_beam = perf_counter_ns()
    var _ns_shear_stress_beam = Float64(_t1_shear_stress_beam - _t0_shear_stress_beam) / Float64(N)
    print("MOJO_TIMING structural::shear_stress_beam", _ns_shear_stress_beam, _acc_shear_stress_beam)
    var _acc_moment_of_inertia_rect: Float64 = 0.0
    var _t0_moment_of_inertia_rect = perf_counter_ns()
    for _ in range(N):
        _acc_moment_of_inertia_rect += moment_of_inertia_rect(0.5, 0.5)
    var _t1_moment_of_inertia_rect = perf_counter_ns()
    var _ns_moment_of_inertia_rect = Float64(_t1_moment_of_inertia_rect - _t0_moment_of_inertia_rect) / Float64(N)
    print("MOJO_TIMING structural::moment_of_inertia_rect", _ns_moment_of_inertia_rect, _acc_moment_of_inertia_rect)
    var _acc_section_modulus_rect: Float64 = 0.0
    var _t0_section_modulus_rect = perf_counter_ns()
    for _ in range(N):
        _acc_section_modulus_rect += section_modulus_rect(0.5, 0.5)
    var _t1_section_modulus_rect = perf_counter_ns()
    var _ns_section_modulus_rect = Float64(_t1_section_modulus_rect - _t0_section_modulus_rect) / Float64(N)
    print("MOJO_TIMING structural::section_modulus_rect", _ns_section_modulus_rect, _acc_section_modulus_rect)
    var _acc_deflection_cantilever_point: Float64 = 0.0
    var _t0_deflection_cantilever_point = perf_counter_ns()
    for _ in range(N):
        _acc_deflection_cantilever_point += deflection_cantilever_point(0.5, 0.5, 0.5)
    var _t1_deflection_cantilever_point = perf_counter_ns()
    var _ns_deflection_cantilever_point = Float64(_t1_deflection_cantilever_point - _t0_deflection_cantilever_point) / Float64(N)
    print("MOJO_TIMING structural::deflection_cantilever_point", _ns_deflection_cantilever_point, _acc_deflection_cantilever_point)
    var _acc_deflection_simply_supported_center: Float64 = 0.0
    var _t0_deflection_simply_supported_center = perf_counter_ns()
    for _ in range(N):
        _acc_deflection_simply_supported_center += deflection_simply_supported_center(0.5, 0.5, 0.5)
    var _t1_deflection_simply_supported_center = perf_counter_ns()
    var _ns_deflection_simply_supported_center = Float64(_t1_deflection_simply_supported_center - _t0_deflection_simply_supported_center) / Float64(N)
    print("MOJO_TIMING structural::deflection_simply_supported_center", _ns_deflection_simply_supported_center, _acc_deflection_simply_supported_center)
    var _acc_euler_buckling_load: Float64 = 0.0
    var _t0_euler_buckling_load = perf_counter_ns()
    for _ in range(N):
        _acc_euler_buckling_load += euler_buckling_load(0.5, 0.5, 0.5)
    var _t1_euler_buckling_load = perf_counter_ns()
    var _ns_euler_buckling_load = Float64(_t1_euler_buckling_load - _t0_euler_buckling_load) / Float64(N)
    print("MOJO_TIMING structural::euler_buckling_load", _ns_euler_buckling_load, _acc_euler_buckling_load)
    var _acc_slenderness_ratio: Float64 = 0.0
    var _t0_slenderness_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_slenderness_ratio += slenderness_ratio(0.5, 0.5)
    var _t1_slenderness_ratio = perf_counter_ns()
    var _ns_slenderness_ratio = Float64(_t1_slenderness_ratio - _t0_slenderness_ratio) / Float64(N)
    print("MOJO_TIMING structural::slenderness_ratio", _ns_slenderness_ratio, _acc_slenderness_ratio)
    var _acc_axial_stress: Float64 = 0.0
    var _t0_axial_stress = perf_counter_ns()
    for _ in range(N):
        _acc_axial_stress += axial_stress(0.5, 0.5)
    var _t1_axial_stress = perf_counter_ns()
    var _ns_axial_stress = Float64(_t1_axial_stress - _t0_axial_stress) / Float64(N)
    print("MOJO_TIMING structural::axial_stress", _ns_axial_stress, _acc_axial_stress)
    var _acc_combined_stress_von_mises: Float64 = 0.0
    var _t0_combined_stress_von_mises = perf_counter_ns()
    for _ in range(N):
        _acc_combined_stress_von_mises += combined_stress_von_mises(0.5, 0.5, 0.5)
    var _t1_combined_stress_von_mises = perf_counter_ns()
    var _ns_combined_stress_von_mises = Float64(_t1_combined_stress_von_mises - _t0_combined_stress_von_mises) / Float64(N)
    print("MOJO_TIMING structural::combined_stress_von_mises", _ns_combined_stress_von_mises, _acc_combined_stress_von_mises)
    var _acc_safety_factor: Float64 = 0.0
    var _t0_safety_factor = perf_counter_ns()
    for _ in range(N):
        _acc_safety_factor += safety_factor(0.5, 0.5)
    var _t1_safety_factor = perf_counter_ns()
    var _ns_safety_factor = Float64(_t1_safety_factor - _t0_safety_factor) / Float64(N)
    print("MOJO_TIMING structural::safety_factor", _ns_safety_factor, _acc_safety_factor)
    var _acc_natural_frequency_cantilever: Float64 = 0.0
    var _t0_natural_frequency_cantilever = perf_counter_ns()
    for _ in range(N):
        _acc_natural_frequency_cantilever += natural_frequency_cantilever(0.5, 0.5, 0.5)
    var _t1_natural_frequency_cantilever = perf_counter_ns()
    var _ns_natural_frequency_cantilever = Float64(_t1_natural_frequency_cantilever - _t0_natural_frequency_cantilever) / Float64(N)
    print("MOJO_TIMING structural::natural_frequency_cantilever", _ns_natural_frequency_cantilever, _acc_natural_frequency_cantilever)
