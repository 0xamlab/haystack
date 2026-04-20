"""test_museum.mojo — auto-generated tests for museum library."""
from std.math import isnan, isinf
from museum import lux_hours_annual, uv_exposure, relative_humidity_from_temps, moisture_content_equilibrium, time_weighted_preservation_index, light_damage_reciprocity, climate_stability_score, storage_density, collection_growth_rate, insurance_value_appreciation, visitor_density, conservation_priority_score

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

    var _v_lux_hours_annual = lux_hours_annual(0.5, 0.5, 0.5)
    if is_finite(_v_lux_hours_annual): passed += 1; print("  ✅ museum::lux_hours_annual =", _v_lux_hours_annual)
    else: failed += 1; print("  ❌ museum::lux_hours_annual → non-finite:", _v_lux_hours_annual)
    var _v_uv_exposure = uv_exposure(0.5, 0.5)
    if is_finite(_v_uv_exposure): passed += 1; print("  ✅ museum::uv_exposure =", _v_uv_exposure)
    else: failed += 1; print("  ❌ museum::uv_exposure → non-finite:", _v_uv_exposure)
    var _v_relative_humidity_from_temps = relative_humidity_from_temps(0.5, 0.5)
    if is_finite(_v_relative_humidity_from_temps): passed += 1; print("  ✅ museum::relative_humidity_from_temps =", _v_relative_humidity_from_temps)
    else: failed += 1; print("  ❌ museum::relative_humidity_from_temps → non-finite:", _v_relative_humidity_from_temps)
    var _v_moisture_content_equilibrium = moisture_content_equilibrium(0.5, 0.5)
    if is_finite(_v_moisture_content_equilibrium): passed += 1; print("  ✅ museum::moisture_content_equilibrium =", _v_moisture_content_equilibrium)
    else: failed += 1; print("  ❌ museum::moisture_content_equilibrium → non-finite:", _v_moisture_content_equilibrium)
    var _v_time_weighted_preservation_index = time_weighted_preservation_index(0.5, 0.5, 0.5)
    if is_finite(_v_time_weighted_preservation_index): passed += 1; print("  ✅ museum::time_weighted_preservation_index =", _v_time_weighted_preservation_index)
    else: failed += 1; print("  ❌ museum::time_weighted_preservation_index → non-finite:", _v_time_weighted_preservation_index)
    var _v_light_damage_reciprocity = light_damage_reciprocity(0.5, 0.5)
    if is_finite(_v_light_damage_reciprocity): passed += 1; print("  ✅ museum::light_damage_reciprocity =", _v_light_damage_reciprocity)
    else: failed += 1; print("  ❌ museum::light_damage_reciprocity → non-finite:", _v_light_damage_reciprocity)
    var _v_climate_stability_score = climate_stability_score(0.5, 0.5)
    if is_finite(_v_climate_stability_score): passed += 1; print("  ✅ museum::climate_stability_score =", _v_climate_stability_score)
    else: failed += 1; print("  ❌ museum::climate_stability_score → non-finite:", _v_climate_stability_score)
    var _v_storage_density = storage_density(0.5, 0.5)
    if is_finite(_v_storage_density): passed += 1; print("  ✅ museum::storage_density =", _v_storage_density)
    else: failed += 1; print("  ❌ museum::storage_density → non-finite:", _v_storage_density)
    var _v_collection_growth_rate = collection_growth_rate(0.5, 0.5, 0.5)
    if is_finite(_v_collection_growth_rate): passed += 1; print("  ✅ museum::collection_growth_rate =", _v_collection_growth_rate)
    else: failed += 1; print("  ❌ museum::collection_growth_rate → non-finite:", _v_collection_growth_rate)
    var _v_insurance_value_appreciation = insurance_value_appreciation(0.5, 0.5, 0.5)
    if is_finite(_v_insurance_value_appreciation): passed += 1; print("  ✅ museum::insurance_value_appreciation =", _v_insurance_value_appreciation)
    else: failed += 1; print("  ❌ museum::insurance_value_appreciation → non-finite:", _v_insurance_value_appreciation)
    var _v_visitor_density = visitor_density(0.5, 0.5)
    if is_finite(_v_visitor_density): passed += 1; print("  ✅ museum::visitor_density =", _v_visitor_density)
    else: failed += 1; print("  ❌ museum::visitor_density → non-finite:", _v_visitor_density)
    var _v_conservation_priority_score = conservation_priority_score(0.5, 0.5, 0.5)
    if is_finite(_v_conservation_priority_score): passed += 1; print("  ✅ museum::conservation_priority_score =", _v_conservation_priority_score)
    else: failed += 1; print("  ❌ museum::conservation_priority_score → non-finite:", _v_conservation_priority_score)

    print("  [museum] Passed:", passed, "Failed:", failed)
