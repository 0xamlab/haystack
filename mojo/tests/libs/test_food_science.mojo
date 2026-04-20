"""test_food_science.mojo — auto-generated tests for food_science library."""
from std.math import isnan, isinf
from food_science import water_activity, ph_from_h_concentration, shelf_life_q10, thermal_death_time, d_value_from_z, pasteurization_units, brix_to_sugar_g_per_l, caloric_density, moisture_content_wet_basis, moisture_content_dry_basis, freezing_point_depression, blanching_time_estimate

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

    var _v_water_activity = water_activity(0.5)
    if is_finite(_v_water_activity): passed += 1; print("  ✅ food_science::water_activity =", _v_water_activity)
    else: failed += 1; print("  ❌ food_science::water_activity → non-finite:", _v_water_activity)
    var _v_ph_from_h_concentration = ph_from_h_concentration(0.5)
    if is_finite(_v_ph_from_h_concentration): passed += 1; print("  ✅ food_science::ph_from_h_concentration =", _v_ph_from_h_concentration)
    else: failed += 1; print("  ❌ food_science::ph_from_h_concentration → non-finite:", _v_ph_from_h_concentration)
    var _v_shelf_life_q10 = shelf_life_q10(0.5, 0.5, 0.5)
    if is_finite(_v_shelf_life_q10): passed += 1; print("  ✅ food_science::shelf_life_q10 =", _v_shelf_life_q10)
    else: failed += 1; print("  ❌ food_science::shelf_life_q10 → non-finite:", _v_shelf_life_q10)
    var _v_thermal_death_time = thermal_death_time(0.5, 0.5)
    if is_finite(_v_thermal_death_time): passed += 1; print("  ✅ food_science::thermal_death_time =", _v_thermal_death_time)
    else: failed += 1; print("  ❌ food_science::thermal_death_time → non-finite:", _v_thermal_death_time)
    var _v_d_value_from_z = d_value_from_z(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_d_value_from_z): passed += 1; print("  ✅ food_science::d_value_from_z =", _v_d_value_from_z)
    else: failed += 1; print("  ❌ food_science::d_value_from_z → non-finite:", _v_d_value_from_z)
    var _v_pasteurization_units = pasteurization_units(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_pasteurization_units): passed += 1; print("  ✅ food_science::pasteurization_units =", _v_pasteurization_units)
    else: failed += 1; print("  ❌ food_science::pasteurization_units → non-finite:", _v_pasteurization_units)
    var _v_brix_to_sugar_g_per_l = brix_to_sugar_g_per_l(0.5)
    if is_finite(_v_brix_to_sugar_g_per_l): passed += 1; print("  ✅ food_science::brix_to_sugar_g_per_l =", _v_brix_to_sugar_g_per_l)
    else: failed += 1; print("  ❌ food_science::brix_to_sugar_g_per_l → non-finite:", _v_brix_to_sugar_g_per_l)
    var _v_caloric_density = caloric_density(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_caloric_density): passed += 1; print("  ✅ food_science::caloric_density =", _v_caloric_density)
    else: failed += 1; print("  ❌ food_science::caloric_density → non-finite:", _v_caloric_density)
    var _v_moisture_content_wet_basis = moisture_content_wet_basis(0.5, 0.5)
    if is_finite(_v_moisture_content_wet_basis): passed += 1; print("  ✅ food_science::moisture_content_wet_basis =", _v_moisture_content_wet_basis)
    else: failed += 1; print("  ❌ food_science::moisture_content_wet_basis → non-finite:", _v_moisture_content_wet_basis)
    var _v_moisture_content_dry_basis = moisture_content_dry_basis(0.5, 0.5)
    if is_finite(_v_moisture_content_dry_basis): passed += 1; print("  ✅ food_science::moisture_content_dry_basis =", _v_moisture_content_dry_basis)
    else: failed += 1; print("  ❌ food_science::moisture_content_dry_basis → non-finite:", _v_moisture_content_dry_basis)
    var _v_freezing_point_depression = freezing_point_depression(0.5, 0.5)
    if is_finite(_v_freezing_point_depression): passed += 1; print("  ✅ food_science::freezing_point_depression =", _v_freezing_point_depression)
    else: failed += 1; print("  ❌ food_science::freezing_point_depression → non-finite:", _v_freezing_point_depression)
    var _v_blanching_time_estimate = blanching_time_estimate(0.5, 0.5)
    if is_finite(_v_blanching_time_estimate): passed += 1; print("  ✅ food_science::blanching_time_estimate =", _v_blanching_time_estimate)
    else: failed += 1; print("  ❌ food_science::blanching_time_estimate → non-finite:", _v_blanching_time_estimate)

    print("  [food_science] Passed:", passed, "Failed:", failed)
