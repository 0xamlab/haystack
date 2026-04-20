"""test_photonics.mojo — auto-generated tests for photonics library."""
from std.math import isnan, isinf
from photonics import snells_law_angle, critical_angle, brewster_angle, fresnel_reflectance_normal, numerical_aperture, photon_energy, wavelength_to_frequency, frequency_to_wavelength, beer_lambert_transmittance, beer_lambert_absorbance, diffraction_grating_angle, rayleigh_resolution

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_snells_law_angle = snells_law_angle(0.5, 0.5, 0.5)
    if is_finite(_v_snells_law_angle): passed += 1; print("  ✅ photonics::snells_law_angle =", _v_snells_law_angle)
    else: failed += 1; print("  ❌ photonics::snells_law_angle → non-finite:", _v_snells_law_angle)
    var _v_critical_angle = critical_angle(0.5, 0.5)
    if is_finite(_v_critical_angle): passed += 1; print("  ✅ photonics::critical_angle =", _v_critical_angle)
    else: failed += 1; print("  ❌ photonics::critical_angle → non-finite:", _v_critical_angle)
    var _v_brewster_angle = brewster_angle(0.5, 0.5)
    if is_finite(_v_brewster_angle): passed += 1; print("  ✅ photonics::brewster_angle =", _v_brewster_angle)
    else: failed += 1; print("  ❌ photonics::brewster_angle → non-finite:", _v_brewster_angle)
    var _v_fresnel_reflectance_normal = fresnel_reflectance_normal(0.5, 0.5)
    if is_finite(_v_fresnel_reflectance_normal): passed += 1; print("  ✅ photonics::fresnel_reflectance_normal =", _v_fresnel_reflectance_normal)
    else: failed += 1; print("  ❌ photonics::fresnel_reflectance_normal → non-finite:", _v_fresnel_reflectance_normal)
    var _v_numerical_aperture = numerical_aperture(0.5, 0.5)
    if is_finite(_v_numerical_aperture): passed += 1; print("  ✅ photonics::numerical_aperture =", _v_numerical_aperture)
    else: failed += 1; print("  ❌ photonics::numerical_aperture → non-finite:", _v_numerical_aperture)
    var _v_photon_energy = photon_energy(0.5)
    if is_finite(_v_photon_energy): passed += 1; print("  ✅ photonics::photon_energy =", _v_photon_energy)
    else: failed += 1; print("  ❌ photonics::photon_energy → non-finite:", _v_photon_energy)
    var _v_wavelength_to_frequency = wavelength_to_frequency(0.5)
    if is_finite(_v_wavelength_to_frequency): passed += 1; print("  ✅ photonics::wavelength_to_frequency =", _v_wavelength_to_frequency)
    else: failed += 1; print("  ❌ photonics::wavelength_to_frequency → non-finite:", _v_wavelength_to_frequency)
    var _v_frequency_to_wavelength = frequency_to_wavelength(0.5)
    if is_finite(_v_frequency_to_wavelength): passed += 1; print("  ✅ photonics::frequency_to_wavelength =", _v_frequency_to_wavelength)
    else: failed += 1; print("  ❌ photonics::frequency_to_wavelength → non-finite:", _v_frequency_to_wavelength)
    var _v_beer_lambert_transmittance = beer_lambert_transmittance(0.5, 0.5)
    if is_finite(_v_beer_lambert_transmittance): passed += 1; print("  ✅ photonics::beer_lambert_transmittance =", _v_beer_lambert_transmittance)
    else: failed += 1; print("  ❌ photonics::beer_lambert_transmittance → non-finite:", _v_beer_lambert_transmittance)
    var _v_beer_lambert_absorbance = beer_lambert_absorbance(0.5)
    if is_finite(_v_beer_lambert_absorbance): passed += 1; print("  ✅ photonics::beer_lambert_absorbance =", _v_beer_lambert_absorbance)
    else: failed += 1; print("  ❌ photonics::beer_lambert_absorbance → non-finite:", _v_beer_lambert_absorbance)
    var _v_diffraction_grating_angle = diffraction_grating_angle(0.5, 0.5, 0.5)
    if is_finite(_v_diffraction_grating_angle): passed += 1; print("  ✅ photonics::diffraction_grating_angle =", _v_diffraction_grating_angle)
    else: failed += 1; print("  ❌ photonics::diffraction_grating_angle → non-finite:", _v_diffraction_grating_angle)
    var _v_rayleigh_resolution = rayleigh_resolution(0.5, 0.5)
    if is_finite(_v_rayleigh_resolution): passed += 1; print("  ✅ photonics::rayleigh_resolution =", _v_rayleigh_resolution)
    else: failed += 1; print("  ❌ photonics::rayleigh_resolution → non-finite:", _v_rayleigh_resolution)

    print("  [photonics] Passed:", passed, "Failed:", failed)
