"""test_corrosion.mojo — auto-generated tests for corrosion library."""
from std.math import isnan, isinf
from corrosion import corrosion_rate_mpy, corrosion_rate_mmpy, pitting_rate, pitting_factor, galvanic_potential_difference, nernst_potential, passivation_current_density, tafel_overpotential, metal_loss_from_rate, remaining_wall_thickness, cathodic_protection_current, service_life_estimate

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

    var _v_corrosion_rate_mpy = corrosion_rate_mpy(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_corrosion_rate_mpy): passed += 1; print("  ✅ corrosion::corrosion_rate_mpy =", _v_corrosion_rate_mpy)
    else: failed += 1; print("  ❌ corrosion::corrosion_rate_mpy → non-finite:", _v_corrosion_rate_mpy)
    var _v_corrosion_rate_mmpy = corrosion_rate_mmpy(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_corrosion_rate_mmpy): passed += 1; print("  ✅ corrosion::corrosion_rate_mmpy =", _v_corrosion_rate_mmpy)
    else: failed += 1; print("  ❌ corrosion::corrosion_rate_mmpy → non-finite:", _v_corrosion_rate_mmpy)
    var _v_pitting_rate = pitting_rate(0.5, 0.5)
    if is_finite(_v_pitting_rate): passed += 1; print("  ✅ corrosion::pitting_rate =", _v_pitting_rate)
    else: failed += 1; print("  ❌ corrosion::pitting_rate → non-finite:", _v_pitting_rate)
    var _v_pitting_factor = pitting_factor(0.5, 0.5)
    if is_finite(_v_pitting_factor): passed += 1; print("  ✅ corrosion::pitting_factor =", _v_pitting_factor)
    else: failed += 1; print("  ❌ corrosion::pitting_factor → non-finite:", _v_pitting_factor)
    var _v_galvanic_potential_difference = galvanic_potential_difference(0.5, 0.5)
    if is_finite(_v_galvanic_potential_difference): passed += 1; print("  ✅ corrosion::galvanic_potential_difference =", _v_galvanic_potential_difference)
    else: failed += 1; print("  ❌ corrosion::galvanic_potential_difference → non-finite:", _v_galvanic_potential_difference)
    var _v_nernst_potential = nernst_potential(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_nernst_potential): passed += 1; print("  ✅ corrosion::nernst_potential =", _v_nernst_potential)
    else: failed += 1; print("  ❌ corrosion::nernst_potential → non-finite:", _v_nernst_potential)
    var _v_passivation_current_density = passivation_current_density(0.5, 0.5)
    if is_finite(_v_passivation_current_density): passed += 1; print("  ✅ corrosion::passivation_current_density =", _v_passivation_current_density)
    else: failed += 1; print("  ❌ corrosion::passivation_current_density → non-finite:", _v_passivation_current_density)
    var _v_tafel_overpotential = tafel_overpotential(0.5, 0.5, 0.5)
    if is_finite(_v_tafel_overpotential): passed += 1; print("  ✅ corrosion::tafel_overpotential =", _v_tafel_overpotential)
    else: failed += 1; print("  ❌ corrosion::tafel_overpotential → non-finite:", _v_tafel_overpotential)
    var _v_metal_loss_from_rate = metal_loss_from_rate(0.5, 0.5)
    if is_finite(_v_metal_loss_from_rate): passed += 1; print("  ✅ corrosion::metal_loss_from_rate =", _v_metal_loss_from_rate)
    else: failed += 1; print("  ❌ corrosion::metal_loss_from_rate → non-finite:", _v_metal_loss_from_rate)
    var _v_remaining_wall_thickness = remaining_wall_thickness(0.5, 0.5)
    if is_finite(_v_remaining_wall_thickness): passed += 1; print("  ✅ corrosion::remaining_wall_thickness =", _v_remaining_wall_thickness)
    else: failed += 1; print("  ❌ corrosion::remaining_wall_thickness → non-finite:", _v_remaining_wall_thickness)
    var _v_cathodic_protection_current = cathodic_protection_current(0.5, 0.5)
    if is_finite(_v_cathodic_protection_current): passed += 1; print("  ✅ corrosion::cathodic_protection_current =", _v_cathodic_protection_current)
    else: failed += 1; print("  ❌ corrosion::cathodic_protection_current → non-finite:", _v_cathodic_protection_current)
    var _v_service_life_estimate = service_life_estimate(0.5, 0.5)
    if is_finite(_v_service_life_estimate): passed += 1; print("  ✅ corrosion::service_life_estimate =", _v_service_life_estimate)
    else: failed += 1; print("  ❌ corrosion::service_life_estimate → non-finite:", _v_service_life_estimate)

    print("  [corrosion] Passed:", passed, "Failed:", failed)
