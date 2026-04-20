"""bench_radiometry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from radiometry import planck_spectral_radiance, stefan_boltzmann_radiance, photon_energy, photon_flux, solid_angle_cone, lambertian_irradiance, radiant_exitance_blackbody, luminous_efficacy, absorptance_from_reflectance, noise_equivalent_power
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

    var _acc_planck_spectral_radiance: Float64 = 0.0
    var _t0_planck_spectral_radiance = perf_counter_ns()
    for _ in range(N):
        _acc_planck_spectral_radiance += planck_spectral_radiance(0.5, 0.5)
    var _t1_planck_spectral_radiance = perf_counter_ns()
    var _ns_planck_spectral_radiance = Float64(_t1_planck_spectral_radiance - _t0_planck_spectral_radiance) / Float64(N)
    print("MOJO_TIMING radiometry::planck_spectral_radiance", _ns_planck_spectral_radiance, _acc_planck_spectral_radiance)
    var _acc_stefan_boltzmann_radiance: Float64 = 0.0
    var _t0_stefan_boltzmann_radiance = perf_counter_ns()
    for _ in range(N):
        _acc_stefan_boltzmann_radiance += stefan_boltzmann_radiance(0.5, 0.5)
    var _t1_stefan_boltzmann_radiance = perf_counter_ns()
    var _ns_stefan_boltzmann_radiance = Float64(_t1_stefan_boltzmann_radiance - _t0_stefan_boltzmann_radiance) / Float64(N)
    print("MOJO_TIMING radiometry::stefan_boltzmann_radiance", _ns_stefan_boltzmann_radiance, _acc_stefan_boltzmann_radiance)
    var _acc_photon_energy: Float64 = 0.0
    var _t0_photon_energy = perf_counter_ns()
    for _ in range(N):
        _acc_photon_energy += photon_energy(0.5)
    var _t1_photon_energy = perf_counter_ns()
    var _ns_photon_energy = Float64(_t1_photon_energy - _t0_photon_energy) / Float64(N)
    print("MOJO_TIMING radiometry::photon_energy", _ns_photon_energy, _acc_photon_energy)
    var _acc_photon_flux: Float64 = 0.0
    var _t0_photon_flux = perf_counter_ns()
    for _ in range(N):
        _acc_photon_flux += photon_flux(0.5, 0.5)
    var _t1_photon_flux = perf_counter_ns()
    var _ns_photon_flux = Float64(_t1_photon_flux - _t0_photon_flux) / Float64(N)
    print("MOJO_TIMING radiometry::photon_flux", _ns_photon_flux, _acc_photon_flux)
    var _acc_solid_angle_cone: Float64 = 0.0
    var _t0_solid_angle_cone = perf_counter_ns()
    for _ in range(N):
        _acc_solid_angle_cone += solid_angle_cone(0.5)
    var _t1_solid_angle_cone = perf_counter_ns()
    var _ns_solid_angle_cone = Float64(_t1_solid_angle_cone - _t0_solid_angle_cone) / Float64(N)
    print("MOJO_TIMING radiometry::solid_angle_cone", _ns_solid_angle_cone, _acc_solid_angle_cone)
    var _acc_lambertian_irradiance: Float64 = 0.0
    var _t0_lambertian_irradiance = perf_counter_ns()
    for _ in range(N):
        _acc_lambertian_irradiance += lambertian_irradiance(0.5, 0.5)
    var _t1_lambertian_irradiance = perf_counter_ns()
    var _ns_lambertian_irradiance = Float64(_t1_lambertian_irradiance - _t0_lambertian_irradiance) / Float64(N)
    print("MOJO_TIMING radiometry::lambertian_irradiance", _ns_lambertian_irradiance, _acc_lambertian_irradiance)
    var _acc_radiant_exitance_blackbody: Float64 = 0.0
    var _t0_radiant_exitance_blackbody = perf_counter_ns()
    for _ in range(N):
        _acc_radiant_exitance_blackbody += radiant_exitance_blackbody(0.5)
    var _t1_radiant_exitance_blackbody = perf_counter_ns()
    var _ns_radiant_exitance_blackbody = Float64(_t1_radiant_exitance_blackbody - _t0_radiant_exitance_blackbody) / Float64(N)
    print("MOJO_TIMING radiometry::radiant_exitance_blackbody", _ns_radiant_exitance_blackbody, _acc_radiant_exitance_blackbody)
    var _acc_luminous_efficacy: Float64 = 0.0
    var _t0_luminous_efficacy = perf_counter_ns()
    for _ in range(N):
        _acc_luminous_efficacy += luminous_efficacy(0.5, 0.5)
    var _t1_luminous_efficacy = perf_counter_ns()
    var _ns_luminous_efficacy = Float64(_t1_luminous_efficacy - _t0_luminous_efficacy) / Float64(N)
    print("MOJO_TIMING radiometry::luminous_efficacy", _ns_luminous_efficacy, _acc_luminous_efficacy)
    var _acc_absorptance_from_reflectance: Float64 = 0.0
    var _t0_absorptance_from_reflectance = perf_counter_ns()
    for _ in range(N):
        _acc_absorptance_from_reflectance += absorptance_from_reflectance(0.5, 0.5)
    var _t1_absorptance_from_reflectance = perf_counter_ns()
    var _ns_absorptance_from_reflectance = Float64(_t1_absorptance_from_reflectance - _t0_absorptance_from_reflectance) / Float64(N)
    print("MOJO_TIMING radiometry::absorptance_from_reflectance", _ns_absorptance_from_reflectance, _acc_absorptance_from_reflectance)
    var _acc_noise_equivalent_power: Float64 = 0.0
    var _t0_noise_equivalent_power = perf_counter_ns()
    for _ in range(N):
        _acc_noise_equivalent_power += noise_equivalent_power(0.5, 0.5)
    var _t1_noise_equivalent_power = perf_counter_ns()
    var _ns_noise_equivalent_power = Float64(_t1_noise_equivalent_power - _t0_noise_equivalent_power) / Float64(N)
    print("MOJO_TIMING radiometry::noise_equivalent_power", _ns_noise_equivalent_power, _acc_noise_equivalent_power)
