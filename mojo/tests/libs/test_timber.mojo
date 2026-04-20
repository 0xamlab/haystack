"""test_timber.mojo — auto-generated tests for timber library."""
from std.math import isnan, isinf
from timber import board_feet, moisture_content, allowable_stress, modulus_of_rupture_adjusted, section_modulus_beam, moment_capacity, column_slenderness, wood_density_from_sg, shrinkage_estimate, fire_char_rate, remaining_section, log_volume_doyle

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

    var _v_board_feet = board_feet(0.5, 0.5, 0.5)
    if is_finite(_v_board_feet): passed += 1; print("  ✅ timber::board_feet =", _v_board_feet)
    else: failed += 1; print("  ❌ timber::board_feet → non-finite:", _v_board_feet)
    var _v_moisture_content = moisture_content(0.5, 0.5)
    if is_finite(_v_moisture_content): passed += 1; print("  ✅ timber::moisture_content =", _v_moisture_content)
    else: failed += 1; print("  ❌ timber::moisture_content → non-finite:", _v_moisture_content)
    var _v_allowable_stress = allowable_stress(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_allowable_stress): passed += 1; print("  ✅ timber::allowable_stress =", _v_allowable_stress)
    else: failed += 1; print("  ❌ timber::allowable_stress → non-finite:", _v_allowable_stress)
    var _v_modulus_of_rupture_adjusted = modulus_of_rupture_adjusted(0.5, 0.5)
    if is_finite(_v_modulus_of_rupture_adjusted): passed += 1; print("  ✅ timber::modulus_of_rupture_adjusted =", _v_modulus_of_rupture_adjusted)
    else: failed += 1; print("  ❌ timber::modulus_of_rupture_adjusted → non-finite:", _v_modulus_of_rupture_adjusted)
    var _v_section_modulus_beam = section_modulus_beam(0.5, 0.5)
    if is_finite(_v_section_modulus_beam): passed += 1; print("  ✅ timber::section_modulus_beam =", _v_section_modulus_beam)
    else: failed += 1; print("  ❌ timber::section_modulus_beam → non-finite:", _v_section_modulus_beam)
    var _v_moment_capacity = moment_capacity(0.5, 0.5)
    if is_finite(_v_moment_capacity): passed += 1; print("  ✅ timber::moment_capacity =", _v_moment_capacity)
    else: failed += 1; print("  ❌ timber::moment_capacity → non-finite:", _v_moment_capacity)
    var _v_column_slenderness = column_slenderness(0.5, 0.5)
    if is_finite(_v_column_slenderness): passed += 1; print("  ✅ timber::column_slenderness =", _v_column_slenderness)
    else: failed += 1; print("  ❌ timber::column_slenderness → non-finite:", _v_column_slenderness)
    var _v_wood_density_from_sg = wood_density_from_sg(0.5, 0.5)
    if is_finite(_v_wood_density_from_sg): passed += 1; print("  ✅ timber::wood_density_from_sg =", _v_wood_density_from_sg)
    else: failed += 1; print("  ❌ timber::wood_density_from_sg → non-finite:", _v_wood_density_from_sg)
    var _v_shrinkage_estimate = shrinkage_estimate(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_shrinkage_estimate): passed += 1; print("  ✅ timber::shrinkage_estimate =", _v_shrinkage_estimate)
    else: failed += 1; print("  ❌ timber::shrinkage_estimate → non-finite:", _v_shrinkage_estimate)
    var _v_fire_char_rate = fire_char_rate(0.5, 0.5)
    if is_finite(_v_fire_char_rate): passed += 1; print("  ✅ timber::fire_char_rate =", _v_fire_char_rate)
    else: failed += 1; print("  ❌ timber::fire_char_rate → non-finite:", _v_fire_char_rate)
    var _v_remaining_section = remaining_section(0.5, 0.5)
    if is_finite(_v_remaining_section): passed += 1; print("  ✅ timber::remaining_section =", _v_remaining_section)
    else: failed += 1; print("  ❌ timber::remaining_section → non-finite:", _v_remaining_section)
    var _v_log_volume_doyle = log_volume_doyle(0.5, 0.5)
    if is_finite(_v_log_volume_doyle): passed += 1; print("  ✅ timber::log_volume_doyle =", _v_log_volume_doyle)
    else: failed += 1; print("  ❌ timber::log_volume_doyle → non-finite:", _v_log_volume_doyle)

    print("  [timber] Passed:", passed, "Failed:", failed)
