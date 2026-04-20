"""bench_cosmology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from cosmology import hubble_velocity, hubble_distance, lookback_time_approx, comoving_distance_approx, luminosity_distance, angular_diameter_distance, redshift_from_wavelength, cosmic_scale_factor, critical_density, schwarzschild_radius, stefan_boltzmann_luminosity, wien_peak_wavelength
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

    var _acc_hubble_velocity: Float64 = 0.0
    var _t0_hubble_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_hubble_velocity += hubble_velocity(0.5, 0.5)
    var _t1_hubble_velocity = perf_counter_ns()
    var _ns_hubble_velocity = Float64(_t1_hubble_velocity - _t0_hubble_velocity) / Float64(N)
    print("MOJO_TIMING cosmology::hubble_velocity", _ns_hubble_velocity, _acc_hubble_velocity)
    var _acc_hubble_distance: Float64 = 0.0
    var _t0_hubble_distance = perf_counter_ns()
    for _ in range(N):
        _acc_hubble_distance += hubble_distance(0.5, 0.5)
    var _t1_hubble_distance = perf_counter_ns()
    var _ns_hubble_distance = Float64(_t1_hubble_distance - _t0_hubble_distance) / Float64(N)
    print("MOJO_TIMING cosmology::hubble_distance", _ns_hubble_distance, _acc_hubble_distance)
    var _acc_lookback_time_approx: Float64 = 0.0
    var _t0_lookback_time_approx = perf_counter_ns()
    for _ in range(N):
        _acc_lookback_time_approx += lookback_time_approx(0.5, 0.5)
    var _t1_lookback_time_approx = perf_counter_ns()
    var _ns_lookback_time_approx = Float64(_t1_lookback_time_approx - _t0_lookback_time_approx) / Float64(N)
    print("MOJO_TIMING cosmology::lookback_time_approx", _ns_lookback_time_approx, _acc_lookback_time_approx)
    var _acc_comoving_distance_approx: Float64 = 0.0
    var _t0_comoving_distance_approx = perf_counter_ns()
    for _ in range(N):
        _acc_comoving_distance_approx += comoving_distance_approx(0.5, 0.5, 0.5)
    var _t1_comoving_distance_approx = perf_counter_ns()
    var _ns_comoving_distance_approx = Float64(_t1_comoving_distance_approx - _t0_comoving_distance_approx) / Float64(N)
    print("MOJO_TIMING cosmology::comoving_distance_approx", _ns_comoving_distance_approx, _acc_comoving_distance_approx)
    var _acc_luminosity_distance: Float64 = 0.0
    var _t0_luminosity_distance = perf_counter_ns()
    for _ in range(N):
        _acc_luminosity_distance += luminosity_distance(0.5, 0.5)
    var _t1_luminosity_distance = perf_counter_ns()
    var _ns_luminosity_distance = Float64(_t1_luminosity_distance - _t0_luminosity_distance) / Float64(N)
    print("MOJO_TIMING cosmology::luminosity_distance", _ns_luminosity_distance, _acc_luminosity_distance)
    var _acc_angular_diameter_distance: Float64 = 0.0
    var _t0_angular_diameter_distance = perf_counter_ns()
    for _ in range(N):
        _acc_angular_diameter_distance += angular_diameter_distance(0.5, 0.5)
    var _t1_angular_diameter_distance = perf_counter_ns()
    var _ns_angular_diameter_distance = Float64(_t1_angular_diameter_distance - _t0_angular_diameter_distance) / Float64(N)
    print("MOJO_TIMING cosmology::angular_diameter_distance", _ns_angular_diameter_distance, _acc_angular_diameter_distance)
    var _acc_redshift_from_wavelength: Float64 = 0.0
    var _t0_redshift_from_wavelength = perf_counter_ns()
    for _ in range(N):
        _acc_redshift_from_wavelength += redshift_from_wavelength(0.5, 0.5)
    var _t1_redshift_from_wavelength = perf_counter_ns()
    var _ns_redshift_from_wavelength = Float64(_t1_redshift_from_wavelength - _t0_redshift_from_wavelength) / Float64(N)
    print("MOJO_TIMING cosmology::redshift_from_wavelength", _ns_redshift_from_wavelength, _acc_redshift_from_wavelength)
    var _acc_cosmic_scale_factor: Float64 = 0.0
    var _t0_cosmic_scale_factor = perf_counter_ns()
    for _ in range(N):
        _acc_cosmic_scale_factor += cosmic_scale_factor(0.5)
    var _t1_cosmic_scale_factor = perf_counter_ns()
    var _ns_cosmic_scale_factor = Float64(_t1_cosmic_scale_factor - _t0_cosmic_scale_factor) / Float64(N)
    print("MOJO_TIMING cosmology::cosmic_scale_factor", _ns_cosmic_scale_factor, _acc_cosmic_scale_factor)
    var _acc_critical_density: Float64 = 0.0
    var _t0_critical_density = perf_counter_ns()
    for _ in range(N):
        _acc_critical_density += critical_density(0.5)
    var _t1_critical_density = perf_counter_ns()
    var _ns_critical_density = Float64(_t1_critical_density - _t0_critical_density) / Float64(N)
    print("MOJO_TIMING cosmology::critical_density", _ns_critical_density, _acc_critical_density)
    var _acc_schwarzschild_radius: Float64 = 0.0
    var _t0_schwarzschild_radius = perf_counter_ns()
    for _ in range(N):
        _acc_schwarzschild_radius += schwarzschild_radius(0.5)
    var _t1_schwarzschild_radius = perf_counter_ns()
    var _ns_schwarzschild_radius = Float64(_t1_schwarzschild_radius - _t0_schwarzschild_radius) / Float64(N)
    print("MOJO_TIMING cosmology::schwarzschild_radius", _ns_schwarzschild_radius, _acc_schwarzschild_radius)
    var _acc_stefan_boltzmann_luminosity: Float64 = 0.0
    var _t0_stefan_boltzmann_luminosity = perf_counter_ns()
    for _ in range(N):
        _acc_stefan_boltzmann_luminosity += stefan_boltzmann_luminosity(0.5, 0.5)
    var _t1_stefan_boltzmann_luminosity = perf_counter_ns()
    var _ns_stefan_boltzmann_luminosity = Float64(_t1_stefan_boltzmann_luminosity - _t0_stefan_boltzmann_luminosity) / Float64(N)
    print("MOJO_TIMING cosmology::stefan_boltzmann_luminosity", _ns_stefan_boltzmann_luminosity, _acc_stefan_boltzmann_luminosity)
    var _acc_wien_peak_wavelength: Float64 = 0.0
    var _t0_wien_peak_wavelength = perf_counter_ns()
    for _ in range(N):
        _acc_wien_peak_wavelength += wien_peak_wavelength(0.5)
    var _t1_wien_peak_wavelength = perf_counter_ns()
    var _ns_wien_peak_wavelength = Float64(_t1_wien_peak_wavelength - _t0_wien_peak_wavelength) / Float64(N)
    print("MOJO_TIMING cosmology::wien_peak_wavelength", _ns_wien_peak_wavelength, _acc_wien_peak_wavelength)
