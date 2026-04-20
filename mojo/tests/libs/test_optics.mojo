"""test_optics.mojo — auto-generated tests for optics library."""
from std.math import isnan, isinf
from optics import snells_law, critical_angle, fresnel_reflectance_normal, thin_lens_equation, magnification, wavelength_to_frequency, photon_energy, diffraction_limit, brewster_angle, numerical_aperture

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

    var _v_snells_law = snells_law(0.5, 0.5, 0.5)
    if is_finite(_v_snells_law): passed += 1; print("  ✅ optics::snells_law =", _v_snells_law)
    else: failed += 1; print("  ❌ optics::snells_law → non-finite:", _v_snells_law)
    var _v_critical_angle = critical_angle(0.5, 0.5)
    if is_finite(_v_critical_angle): passed += 1; print("  ✅ optics::critical_angle =", _v_critical_angle)
    else: failed += 1; print("  ❌ optics::critical_angle → non-finite:", _v_critical_angle)
    var _v_fresnel_reflectance_normal = fresnel_reflectance_normal(0.5, 0.5)
    if is_finite(_v_fresnel_reflectance_normal): passed += 1; print("  ✅ optics::fresnel_reflectance_normal =", _v_fresnel_reflectance_normal)
    else: failed += 1; print("  ❌ optics::fresnel_reflectance_normal → non-finite:", _v_fresnel_reflectance_normal)
    var _v_thin_lens_equation = thin_lens_equation(0.5, 0.5)
    if is_finite(_v_thin_lens_equation): passed += 1; print("  ✅ optics::thin_lens_equation =", _v_thin_lens_equation)
    else: failed += 1; print("  ❌ optics::thin_lens_equation → non-finite:", _v_thin_lens_equation)
    var _v_magnification = magnification(0.5, 0.5)
    if is_finite(_v_magnification): passed += 1; print("  ✅ optics::magnification =", _v_magnification)
    else: failed += 1; print("  ❌ optics::magnification → non-finite:", _v_magnification)
    var _v_wavelength_to_frequency = wavelength_to_frequency(0.5)
    if is_finite(_v_wavelength_to_frequency): passed += 1; print("  ✅ optics::wavelength_to_frequency =", _v_wavelength_to_frequency)
    else: failed += 1; print("  ❌ optics::wavelength_to_frequency → non-finite:", _v_wavelength_to_frequency)
    var _v_photon_energy = photon_energy(0.5)
    if is_finite(_v_photon_energy): passed += 1; print("  ✅ optics::photon_energy =", _v_photon_energy)
    else: failed += 1; print("  ❌ optics::photon_energy → non-finite:", _v_photon_energy)
    var _v_diffraction_limit = diffraction_limit(0.5, 0.5)
    if is_finite(_v_diffraction_limit): passed += 1; print("  ✅ optics::diffraction_limit =", _v_diffraction_limit)
    else: failed += 1; print("  ❌ optics::diffraction_limit → non-finite:", _v_diffraction_limit)
    var _v_brewster_angle = brewster_angle(0.5, 0.5)
    if is_finite(_v_brewster_angle): passed += 1; print("  ✅ optics::brewster_angle =", _v_brewster_angle)
    else: failed += 1; print("  ❌ optics::brewster_angle → non-finite:", _v_brewster_angle)
    var _v_numerical_aperture = numerical_aperture(0.5, 0.5)
    if is_finite(_v_numerical_aperture): passed += 1; print("  ✅ optics::numerical_aperture =", _v_numerical_aperture)
    else: failed += 1; print("  ❌ optics::numerical_aperture → non-finite:", _v_numerical_aperture)

    print("  [optics] Passed:", passed, "Failed:", failed)
