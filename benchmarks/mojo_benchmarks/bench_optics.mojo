"""bench_optics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from optics import snells_law, critical_angle, fresnel_reflectance_normal, thin_lens_equation, magnification, wavelength_to_frequency, photon_energy, diffraction_limit, brewster_angle, numerical_aperture
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

    var _acc_snells_law: Float64 = 0.0
    var _t0_snells_law = perf_counter_ns()
    for _ in range(N):
        _acc_snells_law += snells_law(0.5, 0.5, 0.5)
    var _t1_snells_law = perf_counter_ns()
    var _ns_snells_law = Float64(_t1_snells_law - _t0_snells_law) / Float64(N)
    print("MOJO_TIMING optics::snells_law", _ns_snells_law, _acc_snells_law)
    var _acc_critical_angle: Float64 = 0.0
    var _t0_critical_angle = perf_counter_ns()
    for _ in range(N):
        _acc_critical_angle += critical_angle(0.5, 0.5)
    var _t1_critical_angle = perf_counter_ns()
    var _ns_critical_angle = Float64(_t1_critical_angle - _t0_critical_angle) / Float64(N)
    print("MOJO_TIMING optics::critical_angle", _ns_critical_angle, _acc_critical_angle)
    var _acc_fresnel_reflectance_normal: Float64 = 0.0
    var _t0_fresnel_reflectance_normal = perf_counter_ns()
    for _ in range(N):
        _acc_fresnel_reflectance_normal += fresnel_reflectance_normal(0.5, 0.5)
    var _t1_fresnel_reflectance_normal = perf_counter_ns()
    var _ns_fresnel_reflectance_normal = Float64(_t1_fresnel_reflectance_normal - _t0_fresnel_reflectance_normal) / Float64(N)
    print("MOJO_TIMING optics::fresnel_reflectance_normal", _ns_fresnel_reflectance_normal, _acc_fresnel_reflectance_normal)
    var _acc_thin_lens_equation: Float64 = 0.0
    var _t0_thin_lens_equation = perf_counter_ns()
    for _ in range(N):
        _acc_thin_lens_equation += thin_lens_equation(0.5, 0.5)
    var _t1_thin_lens_equation = perf_counter_ns()
    var _ns_thin_lens_equation = Float64(_t1_thin_lens_equation - _t0_thin_lens_equation) / Float64(N)
    print("MOJO_TIMING optics::thin_lens_equation", _ns_thin_lens_equation, _acc_thin_lens_equation)
    var _acc_magnification: Float64 = 0.0
    var _t0_magnification = perf_counter_ns()
    for _ in range(N):
        _acc_magnification += magnification(0.5, 0.5)
    var _t1_magnification = perf_counter_ns()
    var _ns_magnification = Float64(_t1_magnification - _t0_magnification) / Float64(N)
    print("MOJO_TIMING optics::magnification", _ns_magnification, _acc_magnification)
    var _acc_wavelength_to_frequency: Float64 = 0.0
    var _t0_wavelength_to_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_wavelength_to_frequency += wavelength_to_frequency(0.5)
    var _t1_wavelength_to_frequency = perf_counter_ns()
    var _ns_wavelength_to_frequency = Float64(_t1_wavelength_to_frequency - _t0_wavelength_to_frequency) / Float64(N)
    print("MOJO_TIMING optics::wavelength_to_frequency", _ns_wavelength_to_frequency, _acc_wavelength_to_frequency)
    var _acc_photon_energy: Float64 = 0.0
    var _t0_photon_energy = perf_counter_ns()
    for _ in range(N):
        _acc_photon_energy += photon_energy(0.5)
    var _t1_photon_energy = perf_counter_ns()
    var _ns_photon_energy = Float64(_t1_photon_energy - _t0_photon_energy) / Float64(N)
    print("MOJO_TIMING optics::photon_energy", _ns_photon_energy, _acc_photon_energy)
    var _acc_diffraction_limit: Float64 = 0.0
    var _t0_diffraction_limit = perf_counter_ns()
    for _ in range(N):
        _acc_diffraction_limit += diffraction_limit(0.5, 0.5)
    var _t1_diffraction_limit = perf_counter_ns()
    var _ns_diffraction_limit = Float64(_t1_diffraction_limit - _t0_diffraction_limit) / Float64(N)
    print("MOJO_TIMING optics::diffraction_limit", _ns_diffraction_limit, _acc_diffraction_limit)
    var _acc_brewster_angle: Float64 = 0.0
    var _t0_brewster_angle = perf_counter_ns()
    for _ in range(N):
        _acc_brewster_angle += brewster_angle(0.5, 0.5)
    var _t1_brewster_angle = perf_counter_ns()
    var _ns_brewster_angle = Float64(_t1_brewster_angle - _t0_brewster_angle) / Float64(N)
    print("MOJO_TIMING optics::brewster_angle", _ns_brewster_angle, _acc_brewster_angle)
    var _acc_numerical_aperture: Float64 = 0.0
    var _t0_numerical_aperture = perf_counter_ns()
    for _ in range(N):
        _acc_numerical_aperture += numerical_aperture(0.5, 0.5)
    var _t1_numerical_aperture = perf_counter_ns()
    var _ns_numerical_aperture = Float64(_t1_numerical_aperture - _t0_numerical_aperture) / Float64(N)
    print("MOJO_TIMING optics::numerical_aperture", _ns_numerical_aperture, _acc_numerical_aperture)
