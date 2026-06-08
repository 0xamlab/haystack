"""bench_radiometry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from radiometry import planck_spectral_radiance, stefan_boltzmann_radiance, photon_energy, photon_flux, solid_angle_cone, lambertian_irradiance, radiant_exitance_blackbody, luminous_efficacy, absorptance_from_reflectance, noise_equivalent_power
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

    var _acc_planck_spectral_radiance: Float64 = 0.0
    var _t0_planck_spectral_radiance = perf_counter_ns()
    for _ in range(N):
        _acc_planck_spectral_radiance += planck_spectral_radiance(0.5, 0.5)
    var _t1_planck_spectral_radiance = perf_counter_ns()
    var _ns_planck_spectral_radiance = Float64(_t1_planck_spectral_radiance - _t0_planck_spectral_radiance) / Float64(N)
    print("MOJO_TIMING radiometry::planck_spectral_radiance", _ns_planck_spectral_radiance, _acc_planck_spectral_radiance)
    var _result_planck_spectral_radiance = planck_spectral_radiance(0.5, 0.5)
    var _summary_planck_spectral_radiance = _summary_float64(_result_planck_spectral_radiance)
    print("MOJO_RESULT radiometry::planck_spectral_radiance", _summary_planck_spectral_radiance)
    var _acc_stefan_boltzmann_radiance: Float64 = 0.0
    var _t0_stefan_boltzmann_radiance = perf_counter_ns()
    for _ in range(N):
        _acc_stefan_boltzmann_radiance += stefan_boltzmann_radiance(0.5, 0.5)
    var _t1_stefan_boltzmann_radiance = perf_counter_ns()
    var _ns_stefan_boltzmann_radiance = Float64(_t1_stefan_boltzmann_radiance - _t0_stefan_boltzmann_radiance) / Float64(N)
    print("MOJO_TIMING radiometry::stefan_boltzmann_radiance", _ns_stefan_boltzmann_radiance, _acc_stefan_boltzmann_radiance)
    var _result_stefan_boltzmann_radiance = stefan_boltzmann_radiance(0.5, 0.5)
    var _summary_stefan_boltzmann_radiance = _summary_float64(_result_stefan_boltzmann_radiance)
    print("MOJO_RESULT radiometry::stefan_boltzmann_radiance", _summary_stefan_boltzmann_radiance)
    var _acc_photon_energy: Float64 = 0.0
    var _t0_photon_energy = perf_counter_ns()
    for _ in range(N):
        _acc_photon_energy += photon_energy(0.5)
    var _t1_photon_energy = perf_counter_ns()
    var _ns_photon_energy = Float64(_t1_photon_energy - _t0_photon_energy) / Float64(N)
    print("MOJO_TIMING radiometry::photon_energy", _ns_photon_energy, _acc_photon_energy)
    var _result_photon_energy = photon_energy(0.5)
    var _summary_photon_energy = _summary_float64(_result_photon_energy)
    print("MOJO_RESULT radiometry::photon_energy", _summary_photon_energy)
    var _acc_photon_flux: Float64 = 0.0
    var _t0_photon_flux = perf_counter_ns()
    for _ in range(N):
        _acc_photon_flux += photon_flux(0.5, 0.5)
    var _t1_photon_flux = perf_counter_ns()
    var _ns_photon_flux = Float64(_t1_photon_flux - _t0_photon_flux) / Float64(N)
    print("MOJO_TIMING radiometry::photon_flux", _ns_photon_flux, _acc_photon_flux)
    var _result_photon_flux = photon_flux(0.5, 0.5)
    var _summary_photon_flux = _summary_float64(_result_photon_flux)
    print("MOJO_RESULT radiometry::photon_flux", _summary_photon_flux)
    var _acc_solid_angle_cone: Float64 = 0.0
    var _t0_solid_angle_cone = perf_counter_ns()
    for _ in range(N):
        _acc_solid_angle_cone += solid_angle_cone(0.5)
    var _t1_solid_angle_cone = perf_counter_ns()
    var _ns_solid_angle_cone = Float64(_t1_solid_angle_cone - _t0_solid_angle_cone) / Float64(N)
    print("MOJO_TIMING radiometry::solid_angle_cone", _ns_solid_angle_cone, _acc_solid_angle_cone)
    var _result_solid_angle_cone = solid_angle_cone(0.5)
    var _summary_solid_angle_cone = _summary_float64(_result_solid_angle_cone)
    print("MOJO_RESULT radiometry::solid_angle_cone", _summary_solid_angle_cone)
    var _acc_lambertian_irradiance: Float64 = 0.0
    var _t0_lambertian_irradiance = perf_counter_ns()
    for _ in range(N):
        _acc_lambertian_irradiance += lambertian_irradiance(0.5, 0.5)
    var _t1_lambertian_irradiance = perf_counter_ns()
    var _ns_lambertian_irradiance = Float64(_t1_lambertian_irradiance - _t0_lambertian_irradiance) / Float64(N)
    print("MOJO_TIMING radiometry::lambertian_irradiance", _ns_lambertian_irradiance, _acc_lambertian_irradiance)
    var _result_lambertian_irradiance = lambertian_irradiance(0.5, 0.5)
    var _summary_lambertian_irradiance = _summary_float64(_result_lambertian_irradiance)
    print("MOJO_RESULT radiometry::lambertian_irradiance", _summary_lambertian_irradiance)
    var _acc_radiant_exitance_blackbody: Float64 = 0.0
    var _t0_radiant_exitance_blackbody = perf_counter_ns()
    for _ in range(N):
        _acc_radiant_exitance_blackbody += radiant_exitance_blackbody(0.5)
    var _t1_radiant_exitance_blackbody = perf_counter_ns()
    var _ns_radiant_exitance_blackbody = Float64(_t1_radiant_exitance_blackbody - _t0_radiant_exitance_blackbody) / Float64(N)
    print("MOJO_TIMING radiometry::radiant_exitance_blackbody", _ns_radiant_exitance_blackbody, _acc_radiant_exitance_blackbody)
    var _result_radiant_exitance_blackbody = radiant_exitance_blackbody(0.5)
    var _summary_radiant_exitance_blackbody = _summary_float64(_result_radiant_exitance_blackbody)
    print("MOJO_RESULT radiometry::radiant_exitance_blackbody", _summary_radiant_exitance_blackbody)
    var _acc_luminous_efficacy: Float64 = 0.0
    var _t0_luminous_efficacy = perf_counter_ns()
    for _ in range(N):
        _acc_luminous_efficacy += luminous_efficacy(0.5, 0.5)
    var _t1_luminous_efficacy = perf_counter_ns()
    var _ns_luminous_efficacy = Float64(_t1_luminous_efficacy - _t0_luminous_efficacy) / Float64(N)
    print("MOJO_TIMING radiometry::luminous_efficacy", _ns_luminous_efficacy, _acc_luminous_efficacy)
    var _result_luminous_efficacy = luminous_efficacy(0.5, 0.5)
    var _summary_luminous_efficacy = _summary_float64(_result_luminous_efficacy)
    print("MOJO_RESULT radiometry::luminous_efficacy", _summary_luminous_efficacy)
    var _acc_absorptance_from_reflectance: Float64 = 0.0
    var _t0_absorptance_from_reflectance = perf_counter_ns()
    for _ in range(N):
        _acc_absorptance_from_reflectance += absorptance_from_reflectance(0.5, 0.5)
    var _t1_absorptance_from_reflectance = perf_counter_ns()
    var _ns_absorptance_from_reflectance = Float64(_t1_absorptance_from_reflectance - _t0_absorptance_from_reflectance) / Float64(N)
    print("MOJO_TIMING radiometry::absorptance_from_reflectance", _ns_absorptance_from_reflectance, _acc_absorptance_from_reflectance)
    var _result_absorptance_from_reflectance = absorptance_from_reflectance(0.5, 0.5)
    var _summary_absorptance_from_reflectance = _summary_float64(_result_absorptance_from_reflectance)
    print("MOJO_RESULT radiometry::absorptance_from_reflectance", _summary_absorptance_from_reflectance)
    var _acc_noise_equivalent_power: Float64 = 0.0
    var _t0_noise_equivalent_power = perf_counter_ns()
    for _ in range(N):
        _acc_noise_equivalent_power += noise_equivalent_power(0.5, 0.5)
    var _t1_noise_equivalent_power = perf_counter_ns()
    var _ns_noise_equivalent_power = Float64(_t1_noise_equivalent_power - _t0_noise_equivalent_power) / Float64(N)
    print("MOJO_TIMING radiometry::noise_equivalent_power", _ns_noise_equivalent_power, _acc_noise_equivalent_power)
    var _result_noise_equivalent_power = noise_equivalent_power(0.5, 0.5)
    var _summary_noise_equivalent_power = _summary_float64(_result_noise_equivalent_power)
    print("MOJO_RESULT radiometry::noise_equivalent_power", _summary_noise_equivalent_power)
