"""test_ergonomics.mojo — auto-generated tests for ergonomics library."""
from std.math import isnan, isinf
from ergonomics import niosh_rwl, lifting_index, metabolic_rate_walking, heat_stress_index, decibel_addition, noise_dose, cumulative_noise_dose_2, visual_angle_minutes, fitts_law_movement_time, hicks_law_reaction_time, comfort_temperature_pmv_simplified, body_mass_index

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

    var _v_niosh_rwl = niosh_rwl(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_niosh_rwl): passed += 1; print("  ✅ ergonomics::niosh_rwl =", _v_niosh_rwl)
    else: failed += 1; print("  ❌ ergonomics::niosh_rwl → non-finite:", _v_niosh_rwl)
    var _v_lifting_index = lifting_index(0.5, 0.5)
    if is_finite(_v_lifting_index): passed += 1; print("  ✅ ergonomics::lifting_index =", _v_lifting_index)
    else: failed += 1; print("  ❌ ergonomics::lifting_index → non-finite:", _v_lifting_index)
    var _v_metabolic_rate_walking = metabolic_rate_walking(0.5, 0.5, 0.5)
    if is_finite(_v_metabolic_rate_walking): passed += 1; print("  ✅ ergonomics::metabolic_rate_walking =", _v_metabolic_rate_walking)
    else: failed += 1; print("  ❌ ergonomics::metabolic_rate_walking → non-finite:", _v_metabolic_rate_walking)
    var _v_heat_stress_index = heat_stress_index(0.5, 0.5)
    if is_finite(_v_heat_stress_index): passed += 1; print("  ✅ ergonomics::heat_stress_index =", _v_heat_stress_index)
    else: failed += 1; print("  ❌ ergonomics::heat_stress_index → non-finite:", _v_heat_stress_index)
    var _v_decibel_addition = decibel_addition(0.5, 0.5)
    if is_finite(_v_decibel_addition): passed += 1; print("  ✅ ergonomics::decibel_addition =", _v_decibel_addition)
    else: failed += 1; print("  ❌ ergonomics::decibel_addition → non-finite:", _v_decibel_addition)
    var _v_noise_dose = noise_dose(0.5, 0.5)
    if is_finite(_v_noise_dose): passed += 1; print("  ✅ ergonomics::noise_dose =", _v_noise_dose)
    else: failed += 1; print("  ❌ ergonomics::noise_dose → non-finite:", _v_noise_dose)
    var _v_cumulative_noise_dose_2 = cumulative_noise_dose_2(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_cumulative_noise_dose_2): passed += 1; print("  ✅ ergonomics::cumulative_noise_dose_2 =", _v_cumulative_noise_dose_2)
    else: failed += 1; print("  ❌ ergonomics::cumulative_noise_dose_2 → non-finite:", _v_cumulative_noise_dose_2)
    var _v_visual_angle_minutes = visual_angle_minutes(0.5, 0.5)
    if is_finite(_v_visual_angle_minutes): passed += 1; print("  ✅ ergonomics::visual_angle_minutes =", _v_visual_angle_minutes)
    else: failed += 1; print("  ❌ ergonomics::visual_angle_minutes → non-finite:", _v_visual_angle_minutes)
    var _v_fitts_law_movement_time = fitts_law_movement_time(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_fitts_law_movement_time): passed += 1; print("  ✅ ergonomics::fitts_law_movement_time =", _v_fitts_law_movement_time)
    else: failed += 1; print("  ❌ ergonomics::fitts_law_movement_time → non-finite:", _v_fitts_law_movement_time)
    var _v_hicks_law_reaction_time = hicks_law_reaction_time(0.5, 0.5, 0.5)
    if is_finite(_v_hicks_law_reaction_time): passed += 1; print("  ✅ ergonomics::hicks_law_reaction_time =", _v_hicks_law_reaction_time)
    else: failed += 1; print("  ❌ ergonomics::hicks_law_reaction_time → non-finite:", _v_hicks_law_reaction_time)
    var _v_comfort_temperature_pmv_simplified = comfort_temperature_pmv_simplified(0.5, 0.5, 0.5)
    if is_finite(_v_comfort_temperature_pmv_simplified): passed += 1; print("  ✅ ergonomics::comfort_temperature_pmv_simplified =", _v_comfort_temperature_pmv_simplified)
    else: failed += 1; print("  ❌ ergonomics::comfort_temperature_pmv_simplified → non-finite:", _v_comfort_temperature_pmv_simplified)
    var _v_body_mass_index = body_mass_index(0.5, 0.5)
    if is_finite(_v_body_mass_index): passed += 1; print("  ✅ ergonomics::body_mass_index =", _v_body_mass_index)
    else: failed += 1; print("  ❌ ergonomics::body_mass_index → non-finite:", _v_body_mass_index)

    print("  [ergonomics] Passed:", passed, "Failed:", failed)
