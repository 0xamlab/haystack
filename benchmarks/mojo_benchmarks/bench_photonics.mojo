"""bench_photonics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from photonics import snells_law_angle, critical_angle, brewster_angle, fresnel_reflectance_normal, numerical_aperture, photon_energy, wavelength_to_frequency, frequency_to_wavelength, beer_lambert_transmittance, beer_lambert_absorbance, diffraction_grating_angle, rayleigh_resolution
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_snells_law_angle: Float64 = 0.0
    var _t0_snells_law_angle = perf_counter_ns()
    for _ in range(N):
        _acc_snells_law_angle += snells_law_angle(0.5, 0.5, 0.5)
    var _t1_snells_law_angle = perf_counter_ns()
    var _ns_snells_law_angle = Float64(_t1_snells_law_angle - _t0_snells_law_angle) / Float64(N)
    print("MOJO_TIMING photonics::snells_law_angle", _ns_snells_law_angle, _acc_snells_law_angle)
    var _result_snells_law_angle = snells_law_angle(0.5, 0.5, 0.5)
    var _summary_snells_law_angle = _summary_float64(_result_snells_law_angle)
    print("MOJO_RESULT photonics::snells_law_angle", _summary_snells_law_angle)
    var _acc_critical_angle: Float64 = 0.0
    var _t0_critical_angle = perf_counter_ns()
    for _ in range(N):
        _acc_critical_angle += critical_angle(0.5, 0.5)
    var _t1_critical_angle = perf_counter_ns()
    var _ns_critical_angle = Float64(_t1_critical_angle - _t0_critical_angle) / Float64(N)
    print("MOJO_TIMING photonics::critical_angle", _ns_critical_angle, _acc_critical_angle)
    var _result_critical_angle = critical_angle(0.5, 0.5)
    var _summary_critical_angle = _summary_float64(_result_critical_angle)
    print("MOJO_RESULT photonics::critical_angle", _summary_critical_angle)
    var _acc_brewster_angle: Float64 = 0.0
    var _t0_brewster_angle = perf_counter_ns()
    for _ in range(N):
        _acc_brewster_angle += brewster_angle(0.5, 0.5)
    var _t1_brewster_angle = perf_counter_ns()
    var _ns_brewster_angle = Float64(_t1_brewster_angle - _t0_brewster_angle) / Float64(N)
    print("MOJO_TIMING photonics::brewster_angle", _ns_brewster_angle, _acc_brewster_angle)
    var _result_brewster_angle = brewster_angle(0.5, 0.5)
    var _summary_brewster_angle = _summary_float64(_result_brewster_angle)
    print("MOJO_RESULT photonics::brewster_angle", _summary_brewster_angle)
    var _acc_fresnel_reflectance_normal: Float64 = 0.0
    var _t0_fresnel_reflectance_normal = perf_counter_ns()
    for _ in range(N):
        _acc_fresnel_reflectance_normal += fresnel_reflectance_normal(0.5, 0.5)
    var _t1_fresnel_reflectance_normal = perf_counter_ns()
    var _ns_fresnel_reflectance_normal = Float64(_t1_fresnel_reflectance_normal - _t0_fresnel_reflectance_normal) / Float64(N)
    print("MOJO_TIMING photonics::fresnel_reflectance_normal", _ns_fresnel_reflectance_normal, _acc_fresnel_reflectance_normal)
    var _result_fresnel_reflectance_normal = fresnel_reflectance_normal(0.5, 0.5)
    var _summary_fresnel_reflectance_normal = _summary_float64(_result_fresnel_reflectance_normal)
    print("MOJO_RESULT photonics::fresnel_reflectance_normal", _summary_fresnel_reflectance_normal)
    var _acc_numerical_aperture: Float64 = 0.0
    var _t0_numerical_aperture = perf_counter_ns()
    for _ in range(N):
        _acc_numerical_aperture += numerical_aperture(0.5, 0.5)
    var _t1_numerical_aperture = perf_counter_ns()
    var _ns_numerical_aperture = Float64(_t1_numerical_aperture - _t0_numerical_aperture) / Float64(N)
    print("MOJO_TIMING photonics::numerical_aperture", _ns_numerical_aperture, _acc_numerical_aperture)
    var _result_numerical_aperture = numerical_aperture(0.5, 0.5)
    var _summary_numerical_aperture = _summary_float64(_result_numerical_aperture)
    print("MOJO_RESULT photonics::numerical_aperture", _summary_numerical_aperture)
    var _acc_photon_energy: Float64 = 0.0
    var _t0_photon_energy = perf_counter_ns()
    for _ in range(N):
        _acc_photon_energy += photon_energy(0.5)
    var _t1_photon_energy = perf_counter_ns()
    var _ns_photon_energy = Float64(_t1_photon_energy - _t0_photon_energy) / Float64(N)
    print("MOJO_TIMING photonics::photon_energy", _ns_photon_energy, _acc_photon_energy)
    var _result_photon_energy = photon_energy(0.5)
    var _summary_photon_energy = _summary_float64(_result_photon_energy)
    print("MOJO_RESULT photonics::photon_energy", _summary_photon_energy)
    var _acc_wavelength_to_frequency: Float64 = 0.0
    var _t0_wavelength_to_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_wavelength_to_frequency += wavelength_to_frequency(0.5)
    var _t1_wavelength_to_frequency = perf_counter_ns()
    var _ns_wavelength_to_frequency = Float64(_t1_wavelength_to_frequency - _t0_wavelength_to_frequency) / Float64(N)
    print("MOJO_TIMING photonics::wavelength_to_frequency", _ns_wavelength_to_frequency, _acc_wavelength_to_frequency)
    var _result_wavelength_to_frequency = wavelength_to_frequency(0.5)
    var _summary_wavelength_to_frequency = _summary_float64(_result_wavelength_to_frequency)
    print("MOJO_RESULT photonics::wavelength_to_frequency", _summary_wavelength_to_frequency)
    var _acc_frequency_to_wavelength: Float64 = 0.0
    var _t0_frequency_to_wavelength = perf_counter_ns()
    for _ in range(N):
        _acc_frequency_to_wavelength += frequency_to_wavelength(0.5)
    var _t1_frequency_to_wavelength = perf_counter_ns()
    var _ns_frequency_to_wavelength = Float64(_t1_frequency_to_wavelength - _t0_frequency_to_wavelength) / Float64(N)
    print("MOJO_TIMING photonics::frequency_to_wavelength", _ns_frequency_to_wavelength, _acc_frequency_to_wavelength)
    var _result_frequency_to_wavelength = frequency_to_wavelength(0.5)
    var _summary_frequency_to_wavelength = _summary_float64(_result_frequency_to_wavelength)
    print("MOJO_RESULT photonics::frequency_to_wavelength", _summary_frequency_to_wavelength)
    var _acc_beer_lambert_transmittance: Float64 = 0.0
    var _t0_beer_lambert_transmittance = perf_counter_ns()
    for _ in range(N):
        _acc_beer_lambert_transmittance += beer_lambert_transmittance(0.5, 0.5)
    var _t1_beer_lambert_transmittance = perf_counter_ns()
    var _ns_beer_lambert_transmittance = Float64(_t1_beer_lambert_transmittance - _t0_beer_lambert_transmittance) / Float64(N)
    print("MOJO_TIMING photonics::beer_lambert_transmittance", _ns_beer_lambert_transmittance, _acc_beer_lambert_transmittance)
    var _result_beer_lambert_transmittance = beer_lambert_transmittance(0.5, 0.5)
    var _summary_beer_lambert_transmittance = _summary_float64(_result_beer_lambert_transmittance)
    print("MOJO_RESULT photonics::beer_lambert_transmittance", _summary_beer_lambert_transmittance)
    var _acc_beer_lambert_absorbance: Float64 = 0.0
    var _t0_beer_lambert_absorbance = perf_counter_ns()
    for _ in range(N):
        _acc_beer_lambert_absorbance += beer_lambert_absorbance(0.5)
    var _t1_beer_lambert_absorbance = perf_counter_ns()
    var _ns_beer_lambert_absorbance = Float64(_t1_beer_lambert_absorbance - _t0_beer_lambert_absorbance) / Float64(N)
    print("MOJO_TIMING photonics::beer_lambert_absorbance", _ns_beer_lambert_absorbance, _acc_beer_lambert_absorbance)
    var _result_beer_lambert_absorbance = beer_lambert_absorbance(0.5)
    var _summary_beer_lambert_absorbance = _summary_float64(_result_beer_lambert_absorbance)
    print("MOJO_RESULT photonics::beer_lambert_absorbance", _summary_beer_lambert_absorbance)
    var _acc_diffraction_grating_angle: Float64 = 0.0
    var _t0_diffraction_grating_angle = perf_counter_ns()
    for _ in range(N):
        _acc_diffraction_grating_angle += diffraction_grating_angle(0.5, 0.5, 0.5)
    var _t1_diffraction_grating_angle = perf_counter_ns()
    var _ns_diffraction_grating_angle = Float64(_t1_diffraction_grating_angle - _t0_diffraction_grating_angle) / Float64(N)
    print("MOJO_TIMING photonics::diffraction_grating_angle", _ns_diffraction_grating_angle, _acc_diffraction_grating_angle)
    var _result_diffraction_grating_angle = diffraction_grating_angle(0.5, 0.5, 0.5)
    var _summary_diffraction_grating_angle = _summary_float64(_result_diffraction_grating_angle)
    print("MOJO_RESULT photonics::diffraction_grating_angle", _summary_diffraction_grating_angle)
    var _acc_rayleigh_resolution: Float64 = 0.0
    var _t0_rayleigh_resolution = perf_counter_ns()
    for _ in range(N):
        _acc_rayleigh_resolution += rayleigh_resolution(0.5, 0.5)
    var _t1_rayleigh_resolution = perf_counter_ns()
    var _ns_rayleigh_resolution = Float64(_t1_rayleigh_resolution - _t0_rayleigh_resolution) / Float64(N)
    print("MOJO_TIMING photonics::rayleigh_resolution", _ns_rayleigh_resolution, _acc_rayleigh_resolution)
    var _result_rayleigh_resolution = rayleigh_resolution(0.5, 0.5)
    var _summary_rayleigh_resolution = _summary_float64(_result_rayleigh_resolution)
    print("MOJO_RESULT photonics::rayleigh_resolution", _summary_rayleigh_resolution)
