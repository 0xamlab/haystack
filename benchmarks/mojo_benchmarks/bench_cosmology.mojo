"""bench_cosmology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from cosmology import hubble_velocity, hubble_distance, lookback_time_approx, comoving_distance_approx, luminosity_distance, angular_diameter_distance, redshift_from_wavelength, cosmic_scale_factor, critical_density, schwarzschild_radius, stefan_boltzmann_luminosity, wien_peak_wavelength
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

    var _acc_hubble_velocity: Float64 = 0.0
    var _t0_hubble_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_hubble_velocity += hubble_velocity(0.5, 0.5)
    var _t1_hubble_velocity = perf_counter_ns()
    var _ns_hubble_velocity = Float64(_t1_hubble_velocity - _t0_hubble_velocity) / Float64(N)
    print("MOJO_TIMING cosmology::hubble_velocity", _ns_hubble_velocity, _acc_hubble_velocity)
    var _result_hubble_velocity = hubble_velocity(0.5, 0.5)
    var _summary_hubble_velocity = _summary_float64(_result_hubble_velocity)
    print("MOJO_RESULT cosmology::hubble_velocity", _summary_hubble_velocity)
    var _acc_hubble_distance: Float64 = 0.0
    var _t0_hubble_distance = perf_counter_ns()
    for _ in range(N):
        _acc_hubble_distance += hubble_distance(0.5, 0.5)
    var _t1_hubble_distance = perf_counter_ns()
    var _ns_hubble_distance = Float64(_t1_hubble_distance - _t0_hubble_distance) / Float64(N)
    print("MOJO_TIMING cosmology::hubble_distance", _ns_hubble_distance, _acc_hubble_distance)
    var _result_hubble_distance = hubble_distance(0.5, 0.5)
    var _summary_hubble_distance = _summary_float64(_result_hubble_distance)
    print("MOJO_RESULT cosmology::hubble_distance", _summary_hubble_distance)
    var _acc_lookback_time_approx: Float64 = 0.0
    var _t0_lookback_time_approx = perf_counter_ns()
    for _ in range(N):
        _acc_lookback_time_approx += lookback_time_approx(0.5, 0.5)
    var _t1_lookback_time_approx = perf_counter_ns()
    var _ns_lookback_time_approx = Float64(_t1_lookback_time_approx - _t0_lookback_time_approx) / Float64(N)
    print("MOJO_TIMING cosmology::lookback_time_approx", _ns_lookback_time_approx, _acc_lookback_time_approx)
    var _result_lookback_time_approx = lookback_time_approx(0.5, 0.5)
    var _summary_lookback_time_approx = _summary_float64(_result_lookback_time_approx)
    print("MOJO_RESULT cosmology::lookback_time_approx", _summary_lookback_time_approx)
    var _acc_comoving_distance_approx: Float64 = 0.0
    var _t0_comoving_distance_approx = perf_counter_ns()
    for _ in range(N):
        _acc_comoving_distance_approx += comoving_distance_approx(0.5, 0.5, 0.5)
    var _t1_comoving_distance_approx = perf_counter_ns()
    var _ns_comoving_distance_approx = Float64(_t1_comoving_distance_approx - _t0_comoving_distance_approx) / Float64(N)
    print("MOJO_TIMING cosmology::comoving_distance_approx", _ns_comoving_distance_approx, _acc_comoving_distance_approx)
    var _result_comoving_distance_approx = comoving_distance_approx(0.5, 0.5, 0.5)
    var _summary_comoving_distance_approx = _summary_float64(_result_comoving_distance_approx)
    print("MOJO_RESULT cosmology::comoving_distance_approx", _summary_comoving_distance_approx)
    var _acc_luminosity_distance: Float64 = 0.0
    var _t0_luminosity_distance = perf_counter_ns()
    for _ in range(N):
        _acc_luminosity_distance += luminosity_distance(0.5, 0.5)
    var _t1_luminosity_distance = perf_counter_ns()
    var _ns_luminosity_distance = Float64(_t1_luminosity_distance - _t0_luminosity_distance) / Float64(N)
    print("MOJO_TIMING cosmology::luminosity_distance", _ns_luminosity_distance, _acc_luminosity_distance)
    var _result_luminosity_distance = luminosity_distance(0.5, 0.5)
    var _summary_luminosity_distance = _summary_float64(_result_luminosity_distance)
    print("MOJO_RESULT cosmology::luminosity_distance", _summary_luminosity_distance)
    var _acc_angular_diameter_distance: Float64 = 0.0
    var _t0_angular_diameter_distance = perf_counter_ns()
    for _ in range(N):
        _acc_angular_diameter_distance += angular_diameter_distance(0.5, 0.5)
    var _t1_angular_diameter_distance = perf_counter_ns()
    var _ns_angular_diameter_distance = Float64(_t1_angular_diameter_distance - _t0_angular_diameter_distance) / Float64(N)
    print("MOJO_TIMING cosmology::angular_diameter_distance", _ns_angular_diameter_distance, _acc_angular_diameter_distance)
    var _result_angular_diameter_distance = angular_diameter_distance(0.5, 0.5)
    var _summary_angular_diameter_distance = _summary_float64(_result_angular_diameter_distance)
    print("MOJO_RESULT cosmology::angular_diameter_distance", _summary_angular_diameter_distance)
    var _acc_redshift_from_wavelength: Float64 = 0.0
    var _t0_redshift_from_wavelength = perf_counter_ns()
    for _ in range(N):
        _acc_redshift_from_wavelength += redshift_from_wavelength(0.5, 0.5)
    var _t1_redshift_from_wavelength = perf_counter_ns()
    var _ns_redshift_from_wavelength = Float64(_t1_redshift_from_wavelength - _t0_redshift_from_wavelength) / Float64(N)
    print("MOJO_TIMING cosmology::redshift_from_wavelength", _ns_redshift_from_wavelength, _acc_redshift_from_wavelength)
    var _result_redshift_from_wavelength = redshift_from_wavelength(0.5, 0.5)
    var _summary_redshift_from_wavelength = _summary_float64(_result_redshift_from_wavelength)
    print("MOJO_RESULT cosmology::redshift_from_wavelength", _summary_redshift_from_wavelength)
    var _acc_cosmic_scale_factor: Float64 = 0.0
    var _t0_cosmic_scale_factor = perf_counter_ns()
    for _ in range(N):
        _acc_cosmic_scale_factor += cosmic_scale_factor(0.5)
    var _t1_cosmic_scale_factor = perf_counter_ns()
    var _ns_cosmic_scale_factor = Float64(_t1_cosmic_scale_factor - _t0_cosmic_scale_factor) / Float64(N)
    print("MOJO_TIMING cosmology::cosmic_scale_factor", _ns_cosmic_scale_factor, _acc_cosmic_scale_factor)
    var _result_cosmic_scale_factor = cosmic_scale_factor(0.5)
    var _summary_cosmic_scale_factor = _summary_float64(_result_cosmic_scale_factor)
    print("MOJO_RESULT cosmology::cosmic_scale_factor", _summary_cosmic_scale_factor)
    var _acc_critical_density: Float64 = 0.0
    var _t0_critical_density = perf_counter_ns()
    for _ in range(N):
        _acc_critical_density += critical_density(0.5)
    var _t1_critical_density = perf_counter_ns()
    var _ns_critical_density = Float64(_t1_critical_density - _t0_critical_density) / Float64(N)
    print("MOJO_TIMING cosmology::critical_density", _ns_critical_density, _acc_critical_density)
    var _result_critical_density = critical_density(0.5)
    var _summary_critical_density = _summary_float64(_result_critical_density)
    print("MOJO_RESULT cosmology::critical_density", _summary_critical_density)
    var _acc_schwarzschild_radius: Float64 = 0.0
    var _t0_schwarzschild_radius = perf_counter_ns()
    for _ in range(N):
        _acc_schwarzschild_radius += schwarzschild_radius(0.5)
    var _t1_schwarzschild_radius = perf_counter_ns()
    var _ns_schwarzschild_radius = Float64(_t1_schwarzschild_radius - _t0_schwarzschild_radius) / Float64(N)
    print("MOJO_TIMING cosmology::schwarzschild_radius", _ns_schwarzschild_radius, _acc_schwarzschild_radius)
    var _result_schwarzschild_radius = schwarzschild_radius(0.5)
    var _summary_schwarzschild_radius = _summary_float64(_result_schwarzschild_radius)
    print("MOJO_RESULT cosmology::schwarzschild_radius", _summary_schwarzschild_radius)
    var _acc_stefan_boltzmann_luminosity: Float64 = 0.0
    var _t0_stefan_boltzmann_luminosity = perf_counter_ns()
    for _ in range(N):
        _acc_stefan_boltzmann_luminosity += stefan_boltzmann_luminosity(0.5, 0.5)
    var _t1_stefan_boltzmann_luminosity = perf_counter_ns()
    var _ns_stefan_boltzmann_luminosity = Float64(_t1_stefan_boltzmann_luminosity - _t0_stefan_boltzmann_luminosity) / Float64(N)
    print("MOJO_TIMING cosmology::stefan_boltzmann_luminosity", _ns_stefan_boltzmann_luminosity, _acc_stefan_boltzmann_luminosity)
    var _result_stefan_boltzmann_luminosity = stefan_boltzmann_luminosity(0.5, 0.5)
    var _summary_stefan_boltzmann_luminosity = _summary_float64(_result_stefan_boltzmann_luminosity)
    print("MOJO_RESULT cosmology::stefan_boltzmann_luminosity", _summary_stefan_boltzmann_luminosity)
    var _acc_wien_peak_wavelength: Float64 = 0.0
    var _t0_wien_peak_wavelength = perf_counter_ns()
    for _ in range(N):
        _acc_wien_peak_wavelength += wien_peak_wavelength(0.5)
    var _t1_wien_peak_wavelength = perf_counter_ns()
    var _ns_wien_peak_wavelength = Float64(_t1_wien_peak_wavelength - _t0_wien_peak_wavelength) / Float64(N)
    print("MOJO_TIMING cosmology::wien_peak_wavelength", _ns_wien_peak_wavelength, _acc_wien_peak_wavelength)
    var _result_wien_peak_wavelength = wien_peak_wavelength(0.5)
    var _summary_wien_peak_wavelength = _summary_float64(_result_wien_peak_wavelength)
    print("MOJO_RESULT cosmology::wien_peak_wavelength", _summary_wien_peak_wavelength)
