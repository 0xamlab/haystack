"""bench_photonics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from photonics import snells_law_angle, critical_angle, brewster_angle, fresnel_reflectance_normal, numerical_aperture, photon_energy, wavelength_to_frequency, frequency_to_wavelength, beer_lambert_transmittance, beer_lambert_absorbance, diffraction_grating_angle, rayleigh_resolution
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

    var _acc_snells_law_angle: Float64 = 0.0
    var _t0_snells_law_angle = perf_counter_ns()
    for _ in range(N):
        _acc_snells_law_angle += snells_law_angle(0.5, 0.5, 0.5)
    var _t1_snells_law_angle = perf_counter_ns()
    var _ns_snells_law_angle = Float64(_t1_snells_law_angle - _t0_snells_law_angle) / Float64(N)
    print("MOJO_TIMING photonics::snells_law_angle", _ns_snells_law_angle, _acc_snells_law_angle)
    var _acc_critical_angle: Float64 = 0.0
    var _t0_critical_angle = perf_counter_ns()
    for _ in range(N):
        _acc_critical_angle += critical_angle(0.5, 0.5)
    var _t1_critical_angle = perf_counter_ns()
    var _ns_critical_angle = Float64(_t1_critical_angle - _t0_critical_angle) / Float64(N)
    print("MOJO_TIMING photonics::critical_angle", _ns_critical_angle, _acc_critical_angle)
    var _acc_brewster_angle: Float64 = 0.0
    var _t0_brewster_angle = perf_counter_ns()
    for _ in range(N):
        _acc_brewster_angle += brewster_angle(0.5, 0.5)
    var _t1_brewster_angle = perf_counter_ns()
    var _ns_brewster_angle = Float64(_t1_brewster_angle - _t0_brewster_angle) / Float64(N)
    print("MOJO_TIMING photonics::brewster_angle", _ns_brewster_angle, _acc_brewster_angle)
    var _acc_fresnel_reflectance_normal: Float64 = 0.0
    var _t0_fresnel_reflectance_normal = perf_counter_ns()
    for _ in range(N):
        _acc_fresnel_reflectance_normal += fresnel_reflectance_normal(0.5, 0.5)
    var _t1_fresnel_reflectance_normal = perf_counter_ns()
    var _ns_fresnel_reflectance_normal = Float64(_t1_fresnel_reflectance_normal - _t0_fresnel_reflectance_normal) / Float64(N)
    print("MOJO_TIMING photonics::fresnel_reflectance_normal", _ns_fresnel_reflectance_normal, _acc_fresnel_reflectance_normal)
    var _acc_numerical_aperture: Float64 = 0.0
    var _t0_numerical_aperture = perf_counter_ns()
    for _ in range(N):
        _acc_numerical_aperture += numerical_aperture(0.5, 0.5)
    var _t1_numerical_aperture = perf_counter_ns()
    var _ns_numerical_aperture = Float64(_t1_numerical_aperture - _t0_numerical_aperture) / Float64(N)
    print("MOJO_TIMING photonics::numerical_aperture", _ns_numerical_aperture, _acc_numerical_aperture)
    var _acc_photon_energy: Float64 = 0.0
    var _t0_photon_energy = perf_counter_ns()
    for _ in range(N):
        _acc_photon_energy += photon_energy(0.5)
    var _t1_photon_energy = perf_counter_ns()
    var _ns_photon_energy = Float64(_t1_photon_energy - _t0_photon_energy) / Float64(N)
    print("MOJO_TIMING photonics::photon_energy", _ns_photon_energy, _acc_photon_energy)
    var _acc_wavelength_to_frequency: Float64 = 0.0
    var _t0_wavelength_to_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_wavelength_to_frequency += wavelength_to_frequency(0.5)
    var _t1_wavelength_to_frequency = perf_counter_ns()
    var _ns_wavelength_to_frequency = Float64(_t1_wavelength_to_frequency - _t0_wavelength_to_frequency) / Float64(N)
    print("MOJO_TIMING photonics::wavelength_to_frequency", _ns_wavelength_to_frequency, _acc_wavelength_to_frequency)
    var _acc_frequency_to_wavelength: Float64 = 0.0
    var _t0_frequency_to_wavelength = perf_counter_ns()
    for _ in range(N):
        _acc_frequency_to_wavelength += frequency_to_wavelength(0.5)
    var _t1_frequency_to_wavelength = perf_counter_ns()
    var _ns_frequency_to_wavelength = Float64(_t1_frequency_to_wavelength - _t0_frequency_to_wavelength) / Float64(N)
    print("MOJO_TIMING photonics::frequency_to_wavelength", _ns_frequency_to_wavelength, _acc_frequency_to_wavelength)
    var _acc_beer_lambert_transmittance: Float64 = 0.0
    var _t0_beer_lambert_transmittance = perf_counter_ns()
    for _ in range(N):
        _acc_beer_lambert_transmittance += beer_lambert_transmittance(0.5, 0.5)
    var _t1_beer_lambert_transmittance = perf_counter_ns()
    var _ns_beer_lambert_transmittance = Float64(_t1_beer_lambert_transmittance - _t0_beer_lambert_transmittance) / Float64(N)
    print("MOJO_TIMING photonics::beer_lambert_transmittance", _ns_beer_lambert_transmittance, _acc_beer_lambert_transmittance)
    var _acc_beer_lambert_absorbance: Float64 = 0.0
    var _t0_beer_lambert_absorbance = perf_counter_ns()
    for _ in range(N):
        _acc_beer_lambert_absorbance += beer_lambert_absorbance(0.5)
    var _t1_beer_lambert_absorbance = perf_counter_ns()
    var _ns_beer_lambert_absorbance = Float64(_t1_beer_lambert_absorbance - _t0_beer_lambert_absorbance) / Float64(N)
    print("MOJO_TIMING photonics::beer_lambert_absorbance", _ns_beer_lambert_absorbance, _acc_beer_lambert_absorbance)
    var _acc_diffraction_grating_angle: Float64 = 0.0
    var _t0_diffraction_grating_angle = perf_counter_ns()
    for _ in range(N):
        _acc_diffraction_grating_angle += diffraction_grating_angle(0.5, 0.5, 0.5)
    var _t1_diffraction_grating_angle = perf_counter_ns()
    var _ns_diffraction_grating_angle = Float64(_t1_diffraction_grating_angle - _t0_diffraction_grating_angle) / Float64(N)
    print("MOJO_TIMING photonics::diffraction_grating_angle", _ns_diffraction_grating_angle, _acc_diffraction_grating_angle)
    var _acc_rayleigh_resolution: Float64 = 0.0
    var _t0_rayleigh_resolution = perf_counter_ns()
    for _ in range(N):
        _acc_rayleigh_resolution += rayleigh_resolution(0.5, 0.5)
    var _t1_rayleigh_resolution = perf_counter_ns()
    var _ns_rayleigh_resolution = Float64(_t1_rayleigh_resolution - _t0_rayleigh_resolution) / Float64(N)
    print("MOJO_TIMING photonics::rayleigh_resolution", _ns_rayleigh_resolution, _acc_rayleigh_resolution)
