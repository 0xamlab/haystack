"""test_brewing.mojo — auto-generated tests for brewing library."""
from std.math import isnan, isinf
from brewing import original_gravity_to_plato, plato_to_gravity, abv_from_og_fg, apparent_attenuation, real_attenuation, ibu_tinseth, utilization_tinseth, mash_water_volume, strike_water_temp, color_srm_from_mcu, calories_per_12oz, priming_sugar_g

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

    var _v_original_gravity_to_plato = original_gravity_to_plato(0.5)
    if is_finite(_v_original_gravity_to_plato): passed += 1; print("  ✅ brewing::original_gravity_to_plato =", _v_original_gravity_to_plato)
    else: failed += 1; print("  ❌ brewing::original_gravity_to_plato → non-finite:", _v_original_gravity_to_plato)
    var _v_plato_to_gravity = plato_to_gravity(0.5)
    if is_finite(_v_plato_to_gravity): passed += 1; print("  ✅ brewing::plato_to_gravity =", _v_plato_to_gravity)
    else: failed += 1; print("  ❌ brewing::plato_to_gravity → non-finite:", _v_plato_to_gravity)
    var _v_abv_from_og_fg = abv_from_og_fg(0.5, 0.5)
    if is_finite(_v_abv_from_og_fg): passed += 1; print("  ✅ brewing::abv_from_og_fg =", _v_abv_from_og_fg)
    else: failed += 1; print("  ❌ brewing::abv_from_og_fg → non-finite:", _v_abv_from_og_fg)
    var _v_apparent_attenuation = apparent_attenuation(0.5, 0.5)
    if is_finite(_v_apparent_attenuation): passed += 1; print("  ✅ brewing::apparent_attenuation =", _v_apparent_attenuation)
    else: failed += 1; print("  ❌ brewing::apparent_attenuation → non-finite:", _v_apparent_attenuation)
    var _v_real_attenuation = real_attenuation(0.5)
    if is_finite(_v_real_attenuation): passed += 1; print("  ✅ brewing::real_attenuation =", _v_real_attenuation)
    else: failed += 1; print("  ❌ brewing::real_attenuation → non-finite:", _v_real_attenuation)
    var _v_ibu_tinseth = ibu_tinseth(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_ibu_tinseth): passed += 1; print("  ✅ brewing::ibu_tinseth =", _v_ibu_tinseth)
    else: failed += 1; print("  ❌ brewing::ibu_tinseth → non-finite:", _v_ibu_tinseth)
    var _v_utilization_tinseth = utilization_tinseth(0.5, 0.5)
    if is_finite(_v_utilization_tinseth): passed += 1; print("  ✅ brewing::utilization_tinseth =", _v_utilization_tinseth)
    else: failed += 1; print("  ❌ brewing::utilization_tinseth → non-finite:", _v_utilization_tinseth)
    var _v_mash_water_volume = mash_water_volume(0.5, 0.5)
    if is_finite(_v_mash_water_volume): passed += 1; print("  ✅ brewing::mash_water_volume =", _v_mash_water_volume)
    else: failed += 1; print("  ❌ brewing::mash_water_volume → non-finite:", _v_mash_water_volume)
    var _v_strike_water_temp = strike_water_temp(0.5, 0.5, 0.5)
    if is_finite(_v_strike_water_temp): passed += 1; print("  ✅ brewing::strike_water_temp =", _v_strike_water_temp)
    else: failed += 1; print("  ❌ brewing::strike_water_temp → non-finite:", _v_strike_water_temp)
    var _v_color_srm_from_mcu = color_srm_from_mcu(0.5)
    if is_finite(_v_color_srm_from_mcu): passed += 1; print("  ✅ brewing::color_srm_from_mcu =", _v_color_srm_from_mcu)
    else: failed += 1; print("  ❌ brewing::color_srm_from_mcu → non-finite:", _v_color_srm_from_mcu)
    var _v_calories_per_12oz = calories_per_12oz(0.5, 0.5)
    if is_finite(_v_calories_per_12oz): passed += 1; print("  ✅ brewing::calories_per_12oz =", _v_calories_per_12oz)
    else: failed += 1; print("  ❌ brewing::calories_per_12oz → non-finite:", _v_calories_per_12oz)
    var _v_priming_sugar_g = priming_sugar_g(0.5, 0.5, 0.5)
    if is_finite(_v_priming_sugar_g): passed += 1; print("  ✅ brewing::priming_sugar_g =", _v_priming_sugar_g)
    else: failed += 1; print("  ❌ brewing::priming_sugar_g → non-finite:", _v_priming_sugar_g)

    print("  [brewing] Passed:", passed, "Failed:", failed)
