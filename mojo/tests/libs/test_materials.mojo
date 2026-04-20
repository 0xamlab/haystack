"""test_materials.mojo — auto-generated tests for materials library."""
from std.math import isnan, isinf
from materials import youngs_modulus, shear_modulus, bulk_modulus, stress_from_force, strain_from_deformation, thermal_expansion, safety_factor, stress_concentration, fatigue_life, beam_deflection_cantilever, moment_of_inertia_rect, poisson_ratio_from_moduli

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

    var _v_youngs_modulus = youngs_modulus(0.5, 0.5)
    if is_finite(_v_youngs_modulus): passed += 1; print("  ✅ materials::youngs_modulus =", _v_youngs_modulus)
    else: failed += 1; print("  ❌ materials::youngs_modulus → non-finite:", _v_youngs_modulus)
    var _v_shear_modulus = shear_modulus(0.5, 0.5)
    if is_finite(_v_shear_modulus): passed += 1; print("  ✅ materials::shear_modulus =", _v_shear_modulus)
    else: failed += 1; print("  ❌ materials::shear_modulus → non-finite:", _v_shear_modulus)
    var _v_bulk_modulus = bulk_modulus(0.5, 0.5)
    if is_finite(_v_bulk_modulus): passed += 1; print("  ✅ materials::bulk_modulus =", _v_bulk_modulus)
    else: failed += 1; print("  ❌ materials::bulk_modulus → non-finite:", _v_bulk_modulus)
    var _v_stress_from_force = stress_from_force(0.5, 0.5)
    if is_finite(_v_stress_from_force): passed += 1; print("  ✅ materials::stress_from_force =", _v_stress_from_force)
    else: failed += 1; print("  ❌ materials::stress_from_force → non-finite:", _v_stress_from_force)
    var _v_strain_from_deformation = strain_from_deformation(0.5, 0.5)
    if is_finite(_v_strain_from_deformation): passed += 1; print("  ✅ materials::strain_from_deformation =", _v_strain_from_deformation)
    else: failed += 1; print("  ❌ materials::strain_from_deformation → non-finite:", _v_strain_from_deformation)
    var _v_thermal_expansion = thermal_expansion(0.5, 0.5, 0.5)
    if is_finite(_v_thermal_expansion): passed += 1; print("  ✅ materials::thermal_expansion =", _v_thermal_expansion)
    else: failed += 1; print("  ❌ materials::thermal_expansion → non-finite:", _v_thermal_expansion)
    var _v_safety_factor = safety_factor(0.5, 0.5)
    if is_finite(_v_safety_factor): passed += 1; print("  ✅ materials::safety_factor =", _v_safety_factor)
    else: failed += 1; print("  ❌ materials::safety_factor → non-finite:", _v_safety_factor)
    var _v_stress_concentration = stress_concentration(0.5, 0.5)
    if is_finite(_v_stress_concentration): passed += 1; print("  ✅ materials::stress_concentration =", _v_stress_concentration)
    else: failed += 1; print("  ❌ materials::stress_concentration → non-finite:", _v_stress_concentration)
    var _v_fatigue_life = fatigue_life(0.5, 0.5, 0.5)
    if is_finite(_v_fatigue_life): passed += 1; print("  ✅ materials::fatigue_life =", _v_fatigue_life)
    else: failed += 1; print("  ❌ materials::fatigue_life → non-finite:", _v_fatigue_life)
    var _v_beam_deflection_cantilever = beam_deflection_cantilever(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_beam_deflection_cantilever): passed += 1; print("  ✅ materials::beam_deflection_cantilever =", _v_beam_deflection_cantilever)
    else: failed += 1; print("  ❌ materials::beam_deflection_cantilever → non-finite:", _v_beam_deflection_cantilever)
    var _v_moment_of_inertia_rect = moment_of_inertia_rect(0.5, 0.5)
    if is_finite(_v_moment_of_inertia_rect): passed += 1; print("  ✅ materials::moment_of_inertia_rect =", _v_moment_of_inertia_rect)
    else: failed += 1; print("  ❌ materials::moment_of_inertia_rect → non-finite:", _v_moment_of_inertia_rect)
    var _v_poisson_ratio_from_moduli = poisson_ratio_from_moduli(0.5, 0.5)
    if is_finite(_v_poisson_ratio_from_moduli): passed += 1; print("  ✅ materials::poisson_ratio_from_moduli =", _v_poisson_ratio_from_moduli)
    else: failed += 1; print("  ❌ materials::poisson_ratio_from_moduli → non-finite:", _v_poisson_ratio_from_moduli)

    print("  [materials] Passed:", passed, "Failed:", failed)
