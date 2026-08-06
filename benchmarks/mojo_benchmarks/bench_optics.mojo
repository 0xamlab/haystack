"""bench_optics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from optics import snells_law, critical_angle, fresnel_reflectance_normal, thin_lens_equation, magnification, wavelength_to_frequency, photon_energy, diffraction_limit, brewster_angle, numerical_aperture
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

    var _acc_snells_law: Float64 = 0.0
    var _t0_snells_law = perf_counter_ns()
    for _ in range(N):
        _acc_snells_law += snells_law(0.5, 0.5, 0.5)
    var _t1_snells_law = perf_counter_ns()
    var _ns_snells_law = Float64(_t1_snells_law - _t0_snells_law) / Float64(N)
    print("MOJO_TIMING optics::snells_law", _ns_snells_law, _acc_snells_law)
    var _result_snells_law = snells_law(0.5, 0.5, 0.5)
    var _summary_snells_law = _summary_float64(_result_snells_law)
    print("MOJO_RESULT optics::snells_law", _summary_snells_law)
    var _acc_critical_angle: Float64 = 0.0
    var _t0_critical_angle = perf_counter_ns()
    for _ in range(N):
        _acc_critical_angle += critical_angle(0.5, 0.5)
    var _t1_critical_angle = perf_counter_ns()
    var _ns_critical_angle = Float64(_t1_critical_angle - _t0_critical_angle) / Float64(N)
    print("MOJO_TIMING optics::critical_angle", _ns_critical_angle, _acc_critical_angle)
    var _result_critical_angle = critical_angle(0.5, 0.5)
    var _summary_critical_angle = _summary_float64(_result_critical_angle)
    print("MOJO_RESULT optics::critical_angle", _summary_critical_angle)
    var _acc_fresnel_reflectance_normal: Float64 = 0.0
    var _t0_fresnel_reflectance_normal = perf_counter_ns()
    for _ in range(N):
        _acc_fresnel_reflectance_normal += fresnel_reflectance_normal(0.5, 0.5)
    var _t1_fresnel_reflectance_normal = perf_counter_ns()
    var _ns_fresnel_reflectance_normal = Float64(_t1_fresnel_reflectance_normal - _t0_fresnel_reflectance_normal) / Float64(N)
    print("MOJO_TIMING optics::fresnel_reflectance_normal", _ns_fresnel_reflectance_normal, _acc_fresnel_reflectance_normal)
    var _result_fresnel_reflectance_normal = fresnel_reflectance_normal(0.5, 0.5)
    var _summary_fresnel_reflectance_normal = _summary_float64(_result_fresnel_reflectance_normal)
    print("MOJO_RESULT optics::fresnel_reflectance_normal", _summary_fresnel_reflectance_normal)
    var _acc_thin_lens_equation: Float64 = 0.0
    var _t0_thin_lens_equation = perf_counter_ns()
    for _ in range(N):
        _acc_thin_lens_equation += thin_lens_equation(0.5, 0.5)
    var _t1_thin_lens_equation = perf_counter_ns()
    var _ns_thin_lens_equation = Float64(_t1_thin_lens_equation - _t0_thin_lens_equation) / Float64(N)
    print("MOJO_TIMING optics::thin_lens_equation", _ns_thin_lens_equation, _acc_thin_lens_equation)
    var _result_thin_lens_equation = thin_lens_equation(0.5, 0.5)
    var _summary_thin_lens_equation = _summary_float64(_result_thin_lens_equation)
    print("MOJO_RESULT optics::thin_lens_equation", _summary_thin_lens_equation)
    var _acc_magnification: Float64 = 0.0
    var _t0_magnification = perf_counter_ns()
    for _ in range(N):
        _acc_magnification += magnification(0.5, 0.5)
    var _t1_magnification = perf_counter_ns()
    var _ns_magnification = Float64(_t1_magnification - _t0_magnification) / Float64(N)
    print("MOJO_TIMING optics::magnification", _ns_magnification, _acc_magnification)
    var _result_magnification = magnification(0.5, 0.5)
    var _summary_magnification = _summary_float64(_result_magnification)
    print("MOJO_RESULT optics::magnification", _summary_magnification)
    var _acc_wavelength_to_frequency: Float64 = 0.0
    var _t0_wavelength_to_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_wavelength_to_frequency += wavelength_to_frequency(0.5)
    var _t1_wavelength_to_frequency = perf_counter_ns()
    var _ns_wavelength_to_frequency = Float64(_t1_wavelength_to_frequency - _t0_wavelength_to_frequency) / Float64(N)
    print("MOJO_TIMING optics::wavelength_to_frequency", _ns_wavelength_to_frequency, _acc_wavelength_to_frequency)
    var _result_wavelength_to_frequency = wavelength_to_frequency(0.5)
    var _summary_wavelength_to_frequency = _summary_float64(_result_wavelength_to_frequency)
    print("MOJO_RESULT optics::wavelength_to_frequency", _summary_wavelength_to_frequency)
    var _acc_photon_energy: Float64 = 0.0
    var _t0_photon_energy = perf_counter_ns()
    for _ in range(N):
        _acc_photon_energy += photon_energy(0.5)
    var _t1_photon_energy = perf_counter_ns()
    var _ns_photon_energy = Float64(_t1_photon_energy - _t0_photon_energy) / Float64(N)
    print("MOJO_TIMING optics::photon_energy", _ns_photon_energy, _acc_photon_energy)
    var _result_photon_energy = photon_energy(0.5)
    var _summary_photon_energy = _summary_float64(_result_photon_energy)
    print("MOJO_RESULT optics::photon_energy", _summary_photon_energy)
    var _acc_diffraction_limit: Float64 = 0.0
    var _t0_diffraction_limit = perf_counter_ns()
    for _ in range(N):
        _acc_diffraction_limit += diffraction_limit(0.5, 0.5)
    var _t1_diffraction_limit = perf_counter_ns()
    var _ns_diffraction_limit = Float64(_t1_diffraction_limit - _t0_diffraction_limit) / Float64(N)
    print("MOJO_TIMING optics::diffraction_limit", _ns_diffraction_limit, _acc_diffraction_limit)
    var _result_diffraction_limit = diffraction_limit(0.5, 0.5)
    var _summary_diffraction_limit = _summary_float64(_result_diffraction_limit)
    print("MOJO_RESULT optics::diffraction_limit", _summary_diffraction_limit)
    var _acc_brewster_angle: Float64 = 0.0
    var _t0_brewster_angle = perf_counter_ns()
    for _ in range(N):
        _acc_brewster_angle += brewster_angle(0.5, 0.5)
    var _t1_brewster_angle = perf_counter_ns()
    var _ns_brewster_angle = Float64(_t1_brewster_angle - _t0_brewster_angle) / Float64(N)
    print("MOJO_TIMING optics::brewster_angle", _ns_brewster_angle, _acc_brewster_angle)
    var _result_brewster_angle = brewster_angle(0.5, 0.5)
    var _summary_brewster_angle = _summary_float64(_result_brewster_angle)
    print("MOJO_RESULT optics::brewster_angle", _summary_brewster_angle)
    var _acc_numerical_aperture: Float64 = 0.0
    var _t0_numerical_aperture = perf_counter_ns()
    for _ in range(N):
        _acc_numerical_aperture += numerical_aperture(0.5, 0.5)
    var _t1_numerical_aperture = perf_counter_ns()
    var _ns_numerical_aperture = Float64(_t1_numerical_aperture - _t0_numerical_aperture) / Float64(N)
    print("MOJO_TIMING optics::numerical_aperture", _ns_numerical_aperture, _acc_numerical_aperture)
    var _result_numerical_aperture = numerical_aperture(0.5, 0.5)
    var _summary_numerical_aperture = _summary_float64(_result_numerical_aperture)
    print("MOJO_RESULT optics::numerical_aperture", _summary_numerical_aperture)
