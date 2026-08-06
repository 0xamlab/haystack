"""bench_materials.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from materials import youngs_modulus, shear_modulus, bulk_modulus, stress_from_force, strain_from_deformation, thermal_expansion, safety_factor, stress_concentration, fatigue_life, beam_deflection_cantilever, moment_of_inertia_rect, poisson_ratio_from_moduli
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

    var _acc_youngs_modulus: Float64 = 0.0
    var _t0_youngs_modulus = perf_counter_ns()
    for _ in range(N):
        _acc_youngs_modulus += youngs_modulus(0.5, 0.5)
    var _t1_youngs_modulus = perf_counter_ns()
    var _ns_youngs_modulus = Float64(_t1_youngs_modulus - _t0_youngs_modulus) / Float64(N)
    print("MOJO_TIMING materials::youngs_modulus", _ns_youngs_modulus, _acc_youngs_modulus)
    var _result_youngs_modulus = youngs_modulus(0.5, 0.5)
    var _summary_youngs_modulus = _summary_float64(_result_youngs_modulus)
    print("MOJO_RESULT materials::youngs_modulus", _summary_youngs_modulus)
    var _acc_shear_modulus: Float64 = 0.0
    var _t0_shear_modulus = perf_counter_ns()
    for _ in range(N):
        _acc_shear_modulus += shear_modulus(0.5, 0.5)
    var _t1_shear_modulus = perf_counter_ns()
    var _ns_shear_modulus = Float64(_t1_shear_modulus - _t0_shear_modulus) / Float64(N)
    print("MOJO_TIMING materials::shear_modulus", _ns_shear_modulus, _acc_shear_modulus)
    var _result_shear_modulus = shear_modulus(0.5, 0.5)
    var _summary_shear_modulus = _summary_float64(_result_shear_modulus)
    print("MOJO_RESULT materials::shear_modulus", _summary_shear_modulus)
    var _acc_bulk_modulus: Float64 = 0.0
    var _t0_bulk_modulus = perf_counter_ns()
    for _ in range(N):
        _acc_bulk_modulus += bulk_modulus(0.5, 0.5)
    var _t1_bulk_modulus = perf_counter_ns()
    var _ns_bulk_modulus = Float64(_t1_bulk_modulus - _t0_bulk_modulus) / Float64(N)
    print("MOJO_TIMING materials::bulk_modulus", _ns_bulk_modulus, _acc_bulk_modulus)
    var _result_bulk_modulus = bulk_modulus(0.5, 0.5)
    var _summary_bulk_modulus = _summary_float64(_result_bulk_modulus)
    print("MOJO_RESULT materials::bulk_modulus", _summary_bulk_modulus)
    var _acc_stress_from_force: Float64 = 0.0
    var _t0_stress_from_force = perf_counter_ns()
    for _ in range(N):
        _acc_stress_from_force += stress_from_force(0.5, 0.5)
    var _t1_stress_from_force = perf_counter_ns()
    var _ns_stress_from_force = Float64(_t1_stress_from_force - _t0_stress_from_force) / Float64(N)
    print("MOJO_TIMING materials::stress_from_force", _ns_stress_from_force, _acc_stress_from_force)
    var _result_stress_from_force = stress_from_force(0.5, 0.5)
    var _summary_stress_from_force = _summary_float64(_result_stress_from_force)
    print("MOJO_RESULT materials::stress_from_force", _summary_stress_from_force)
    var _acc_strain_from_deformation: Float64 = 0.0
    var _t0_strain_from_deformation = perf_counter_ns()
    for _ in range(N):
        _acc_strain_from_deformation += strain_from_deformation(0.5, 0.5)
    var _t1_strain_from_deformation = perf_counter_ns()
    var _ns_strain_from_deformation = Float64(_t1_strain_from_deformation - _t0_strain_from_deformation) / Float64(N)
    print("MOJO_TIMING materials::strain_from_deformation", _ns_strain_from_deformation, _acc_strain_from_deformation)
    var _result_strain_from_deformation = strain_from_deformation(0.5, 0.5)
    var _summary_strain_from_deformation = _summary_float64(_result_strain_from_deformation)
    print("MOJO_RESULT materials::strain_from_deformation", _summary_strain_from_deformation)
    var _acc_thermal_expansion: Float64 = 0.0
    var _t0_thermal_expansion = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_expansion += thermal_expansion(0.5, 0.5, 0.5)
    var _t1_thermal_expansion = perf_counter_ns()
    var _ns_thermal_expansion = Float64(_t1_thermal_expansion - _t0_thermal_expansion) / Float64(N)
    print("MOJO_TIMING materials::thermal_expansion", _ns_thermal_expansion, _acc_thermal_expansion)
    var _result_thermal_expansion = thermal_expansion(0.5, 0.5, 0.5)
    var _summary_thermal_expansion = _summary_float64(_result_thermal_expansion)
    print("MOJO_RESULT materials::thermal_expansion", _summary_thermal_expansion)
    var _acc_safety_factor: Float64 = 0.0
    var _t0_safety_factor = perf_counter_ns()
    for _ in range(N):
        _acc_safety_factor += safety_factor(0.5, 0.5)
    var _t1_safety_factor = perf_counter_ns()
    var _ns_safety_factor = Float64(_t1_safety_factor - _t0_safety_factor) / Float64(N)
    print("MOJO_TIMING materials::safety_factor", _ns_safety_factor, _acc_safety_factor)
    var _result_safety_factor = safety_factor(0.5, 0.5)
    var _summary_safety_factor = _summary_float64(_result_safety_factor)
    print("MOJO_RESULT materials::safety_factor", _summary_safety_factor)
    var _acc_stress_concentration: Float64 = 0.0
    var _t0_stress_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_stress_concentration += stress_concentration(0.5, 0.5)
    var _t1_stress_concentration = perf_counter_ns()
    var _ns_stress_concentration = Float64(_t1_stress_concentration - _t0_stress_concentration) / Float64(N)
    print("MOJO_TIMING materials::stress_concentration", _ns_stress_concentration, _acc_stress_concentration)
    var _result_stress_concentration = stress_concentration(0.5, 0.5)
    var _summary_stress_concentration = _summary_float64(_result_stress_concentration)
    print("MOJO_RESULT materials::stress_concentration", _summary_stress_concentration)
    var _acc_fatigue_life: Float64 = 0.0
    var _t0_fatigue_life = perf_counter_ns()
    for _ in range(N):
        _acc_fatigue_life += fatigue_life(0.5, 0.5, 0.5)
    var _t1_fatigue_life = perf_counter_ns()
    var _ns_fatigue_life = Float64(_t1_fatigue_life - _t0_fatigue_life) / Float64(N)
    print("MOJO_TIMING materials::fatigue_life", _ns_fatigue_life, _acc_fatigue_life)
    var _result_fatigue_life = fatigue_life(0.5, 0.5, 0.5)
    var _summary_fatigue_life = _summary_float64(_result_fatigue_life)
    print("MOJO_RESULT materials::fatigue_life", _summary_fatigue_life)
    var _acc_beam_deflection_cantilever: Float64 = 0.0
    var _t0_beam_deflection_cantilever = perf_counter_ns()
    for _ in range(N):
        _acc_beam_deflection_cantilever += beam_deflection_cantilever(0.5, 0.5, 0.5, 0.5)
    var _t1_beam_deflection_cantilever = perf_counter_ns()
    var _ns_beam_deflection_cantilever = Float64(_t1_beam_deflection_cantilever - _t0_beam_deflection_cantilever) / Float64(N)
    print("MOJO_TIMING materials::beam_deflection_cantilever", _ns_beam_deflection_cantilever, _acc_beam_deflection_cantilever)
    var _result_beam_deflection_cantilever = beam_deflection_cantilever(0.5, 0.5, 0.5, 0.5)
    var _summary_beam_deflection_cantilever = _summary_float64(_result_beam_deflection_cantilever)
    print("MOJO_RESULT materials::beam_deflection_cantilever", _summary_beam_deflection_cantilever)
    var _acc_moment_of_inertia_rect: Float64 = 0.0
    var _t0_moment_of_inertia_rect = perf_counter_ns()
    for _ in range(N):
        _acc_moment_of_inertia_rect += moment_of_inertia_rect(0.5, 0.5)
    var _t1_moment_of_inertia_rect = perf_counter_ns()
    var _ns_moment_of_inertia_rect = Float64(_t1_moment_of_inertia_rect - _t0_moment_of_inertia_rect) / Float64(N)
    print("MOJO_TIMING materials::moment_of_inertia_rect", _ns_moment_of_inertia_rect, _acc_moment_of_inertia_rect)
    var _result_moment_of_inertia_rect = moment_of_inertia_rect(0.5, 0.5)
    var _summary_moment_of_inertia_rect = _summary_float64(_result_moment_of_inertia_rect)
    print("MOJO_RESULT materials::moment_of_inertia_rect", _summary_moment_of_inertia_rect)
    var _acc_poisson_ratio_from_moduli: Float64 = 0.0
    var _t0_poisson_ratio_from_moduli = perf_counter_ns()
    for _ in range(N):
        _acc_poisson_ratio_from_moduli += poisson_ratio_from_moduli(0.5, 0.5)
    var _t1_poisson_ratio_from_moduli = perf_counter_ns()
    var _ns_poisson_ratio_from_moduli = Float64(_t1_poisson_ratio_from_moduli - _t0_poisson_ratio_from_moduli) / Float64(N)
    print("MOJO_TIMING materials::poisson_ratio_from_moduli", _ns_poisson_ratio_from_moduli, _acc_poisson_ratio_from_moduli)
    var _result_poisson_ratio_from_moduli = poisson_ratio_from_moduli(0.5, 0.5)
    var _summary_poisson_ratio_from_moduli = _summary_float64(_result_poisson_ratio_from_moduli)
    print("MOJO_RESULT materials::poisson_ratio_from_moduli", _summary_poisson_ratio_from_moduli)
