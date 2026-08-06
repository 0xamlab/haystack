"""bench_structural.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from structural import bending_stress, shear_stress_beam, moment_of_inertia_rect, section_modulus_rect, deflection_cantilever_point, deflection_simply_supported_center, euler_buckling_load, slenderness_ratio, axial_stress, combined_stress_von_mises, safety_factor, natural_frequency_cantilever
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

    var _acc_bending_stress: Float64 = 0.0
    var _t0_bending_stress = perf_counter_ns()
    for _ in range(N):
        _acc_bending_stress += bending_stress(0.5, 0.5)
    var _t1_bending_stress = perf_counter_ns()
    var _ns_bending_stress = Float64(_t1_bending_stress - _t0_bending_stress) / Float64(N)
    print("MOJO_TIMING structural::bending_stress", _ns_bending_stress, _acc_bending_stress)
    var _result_bending_stress = bending_stress(0.5, 0.5)
    var _summary_bending_stress = _summary_float64(_result_bending_stress)
    print("MOJO_RESULT structural::bending_stress", _summary_bending_stress)
    var _acc_shear_stress_beam: Float64 = 0.0
    var _t0_shear_stress_beam = perf_counter_ns()
    for _ in range(N):
        _acc_shear_stress_beam += shear_stress_beam(0.5, 0.5)
    var _t1_shear_stress_beam = perf_counter_ns()
    var _ns_shear_stress_beam = Float64(_t1_shear_stress_beam - _t0_shear_stress_beam) / Float64(N)
    print("MOJO_TIMING structural::shear_stress_beam", _ns_shear_stress_beam, _acc_shear_stress_beam)
    var _result_shear_stress_beam = shear_stress_beam(0.5, 0.5)
    var _summary_shear_stress_beam = _summary_float64(_result_shear_stress_beam)
    print("MOJO_RESULT structural::shear_stress_beam", _summary_shear_stress_beam)
    var _acc_moment_of_inertia_rect: Float64 = 0.0
    var _t0_moment_of_inertia_rect = perf_counter_ns()
    for _ in range(N):
        _acc_moment_of_inertia_rect += moment_of_inertia_rect(0.5, 0.5)
    var _t1_moment_of_inertia_rect = perf_counter_ns()
    var _ns_moment_of_inertia_rect = Float64(_t1_moment_of_inertia_rect - _t0_moment_of_inertia_rect) / Float64(N)
    print("MOJO_TIMING structural::moment_of_inertia_rect", _ns_moment_of_inertia_rect, _acc_moment_of_inertia_rect)
    var _result_moment_of_inertia_rect = moment_of_inertia_rect(0.5, 0.5)
    var _summary_moment_of_inertia_rect = _summary_float64(_result_moment_of_inertia_rect)
    print("MOJO_RESULT structural::moment_of_inertia_rect", _summary_moment_of_inertia_rect)
    var _acc_section_modulus_rect: Float64 = 0.0
    var _t0_section_modulus_rect = perf_counter_ns()
    for _ in range(N):
        _acc_section_modulus_rect += section_modulus_rect(0.5, 0.5)
    var _t1_section_modulus_rect = perf_counter_ns()
    var _ns_section_modulus_rect = Float64(_t1_section_modulus_rect - _t0_section_modulus_rect) / Float64(N)
    print("MOJO_TIMING structural::section_modulus_rect", _ns_section_modulus_rect, _acc_section_modulus_rect)
    var _result_section_modulus_rect = section_modulus_rect(0.5, 0.5)
    var _summary_section_modulus_rect = _summary_float64(_result_section_modulus_rect)
    print("MOJO_RESULT structural::section_modulus_rect", _summary_section_modulus_rect)
    var _acc_deflection_cantilever_point: Float64 = 0.0
    var _t0_deflection_cantilever_point = perf_counter_ns()
    for _ in range(N):
        _acc_deflection_cantilever_point += deflection_cantilever_point(0.5, 0.5, 0.5)
    var _t1_deflection_cantilever_point = perf_counter_ns()
    var _ns_deflection_cantilever_point = Float64(_t1_deflection_cantilever_point - _t0_deflection_cantilever_point) / Float64(N)
    print("MOJO_TIMING structural::deflection_cantilever_point", _ns_deflection_cantilever_point, _acc_deflection_cantilever_point)
    var _result_deflection_cantilever_point = deflection_cantilever_point(0.5, 0.5, 0.5)
    var _summary_deflection_cantilever_point = _summary_float64(_result_deflection_cantilever_point)
    print("MOJO_RESULT structural::deflection_cantilever_point", _summary_deflection_cantilever_point)
    var _acc_deflection_simply_supported_center: Float64 = 0.0
    var _t0_deflection_simply_supported_center = perf_counter_ns()
    for _ in range(N):
        _acc_deflection_simply_supported_center += deflection_simply_supported_center(0.5, 0.5, 0.5)
    var _t1_deflection_simply_supported_center = perf_counter_ns()
    var _ns_deflection_simply_supported_center = Float64(_t1_deflection_simply_supported_center - _t0_deflection_simply_supported_center) / Float64(N)
    print("MOJO_TIMING structural::deflection_simply_supported_center", _ns_deflection_simply_supported_center, _acc_deflection_simply_supported_center)
    var _result_deflection_simply_supported_center = deflection_simply_supported_center(0.5, 0.5, 0.5)
    var _summary_deflection_simply_supported_center = _summary_float64(_result_deflection_simply_supported_center)
    print("MOJO_RESULT structural::deflection_simply_supported_center", _summary_deflection_simply_supported_center)
    var _acc_euler_buckling_load: Float64 = 0.0
    var _t0_euler_buckling_load = perf_counter_ns()
    for _ in range(N):
        _acc_euler_buckling_load += euler_buckling_load(0.5, 0.5, 0.5)
    var _t1_euler_buckling_load = perf_counter_ns()
    var _ns_euler_buckling_load = Float64(_t1_euler_buckling_load - _t0_euler_buckling_load) / Float64(N)
    print("MOJO_TIMING structural::euler_buckling_load", _ns_euler_buckling_load, _acc_euler_buckling_load)
    var _result_euler_buckling_load = euler_buckling_load(0.5, 0.5, 0.5)
    var _summary_euler_buckling_load = _summary_float64(_result_euler_buckling_load)
    print("MOJO_RESULT structural::euler_buckling_load", _summary_euler_buckling_load)
    var _acc_slenderness_ratio: Float64 = 0.0
    var _t0_slenderness_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_slenderness_ratio += slenderness_ratio(0.5, 0.5)
    var _t1_slenderness_ratio = perf_counter_ns()
    var _ns_slenderness_ratio = Float64(_t1_slenderness_ratio - _t0_slenderness_ratio) / Float64(N)
    print("MOJO_TIMING structural::slenderness_ratio", _ns_slenderness_ratio, _acc_slenderness_ratio)
    var _result_slenderness_ratio = slenderness_ratio(0.5, 0.5)
    var _summary_slenderness_ratio = _summary_float64(_result_slenderness_ratio)
    print("MOJO_RESULT structural::slenderness_ratio", _summary_slenderness_ratio)
    var _acc_axial_stress: Float64 = 0.0
    var _t0_axial_stress = perf_counter_ns()
    for _ in range(N):
        _acc_axial_stress += axial_stress(0.5, 0.5)
    var _t1_axial_stress = perf_counter_ns()
    var _ns_axial_stress = Float64(_t1_axial_stress - _t0_axial_stress) / Float64(N)
    print("MOJO_TIMING structural::axial_stress", _ns_axial_stress, _acc_axial_stress)
    var _result_axial_stress = axial_stress(0.5, 0.5)
    var _summary_axial_stress = _summary_float64(_result_axial_stress)
    print("MOJO_RESULT structural::axial_stress", _summary_axial_stress)
    var _acc_combined_stress_von_mises: Float64 = 0.0
    var _t0_combined_stress_von_mises = perf_counter_ns()
    for _ in range(N):
        _acc_combined_stress_von_mises += combined_stress_von_mises(0.5, 0.5, 0.5)
    var _t1_combined_stress_von_mises = perf_counter_ns()
    var _ns_combined_stress_von_mises = Float64(_t1_combined_stress_von_mises - _t0_combined_stress_von_mises) / Float64(N)
    print("MOJO_TIMING structural::combined_stress_von_mises", _ns_combined_stress_von_mises, _acc_combined_stress_von_mises)
    var _result_combined_stress_von_mises = combined_stress_von_mises(0.5, 0.5, 0.5)
    var _summary_combined_stress_von_mises = _summary_float64(_result_combined_stress_von_mises)
    print("MOJO_RESULT structural::combined_stress_von_mises", _summary_combined_stress_von_mises)
    var _acc_safety_factor: Float64 = 0.0
    var _t0_safety_factor = perf_counter_ns()
    for _ in range(N):
        _acc_safety_factor += safety_factor(0.5, 0.5)
    var _t1_safety_factor = perf_counter_ns()
    var _ns_safety_factor = Float64(_t1_safety_factor - _t0_safety_factor) / Float64(N)
    print("MOJO_TIMING structural::safety_factor", _ns_safety_factor, _acc_safety_factor)
    var _result_safety_factor = safety_factor(0.5, 0.5)
    var _summary_safety_factor = _summary_float64(_result_safety_factor)
    print("MOJO_RESULT structural::safety_factor", _summary_safety_factor)
    var _acc_natural_frequency_cantilever: Float64 = 0.0
    var _t0_natural_frequency_cantilever = perf_counter_ns()
    for _ in range(N):
        _acc_natural_frequency_cantilever += natural_frequency_cantilever(0.5, 0.5, 0.5)
    var _t1_natural_frequency_cantilever = perf_counter_ns()
    var _ns_natural_frequency_cantilever = Float64(_t1_natural_frequency_cantilever - _t0_natural_frequency_cantilever) / Float64(N)
    print("MOJO_TIMING structural::natural_frequency_cantilever", _ns_natural_frequency_cantilever, _acc_natural_frequency_cantilever)
    var _result_natural_frequency_cantilever = natural_frequency_cantilever(0.5, 0.5, 0.5)
    var _summary_natural_frequency_cantilever = _summary_float64(_result_natural_frequency_cantilever)
    print("MOJO_RESULT structural::natural_frequency_cantilever", _summary_natural_frequency_cantilever)
