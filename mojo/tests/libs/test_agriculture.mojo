"""test_agriculture.mojo — auto-generated tests for agriculture library."""
from std.math import isnan, isinf
from agriculture import growing_degree_days, crop_water_need, irrigation_efficiency, fertilizer_rate, seed_rate, harvest_index, yield_per_hectare, soil_ph_lime_requirement, water_use_efficiency, photosynthetically_active_radiation, leaf_area_index, nitrogen_use_efficiency

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

    var _v_growing_degree_days = growing_degree_days(0.5, 0.5, 0.5)
    if is_finite(_v_growing_degree_days): passed += 1; print("  ✅ agriculture::growing_degree_days =", _v_growing_degree_days)
    else: failed += 1; print("  ❌ agriculture::growing_degree_days → non-finite:", _v_growing_degree_days)
    var _v_crop_water_need = crop_water_need(0.5, 0.5)
    if is_finite(_v_crop_water_need): passed += 1; print("  ✅ agriculture::crop_water_need =", _v_crop_water_need)
    else: failed += 1; print("  ❌ agriculture::crop_water_need → non-finite:", _v_crop_water_need)
    var _v_irrigation_efficiency = irrigation_efficiency(0.5, 0.5)
    if is_finite(_v_irrigation_efficiency): passed += 1; print("  ✅ agriculture::irrigation_efficiency =", _v_irrigation_efficiency)
    else: failed += 1; print("  ❌ agriculture::irrigation_efficiency → non-finite:", _v_irrigation_efficiency)
    var _v_fertilizer_rate = fertilizer_rate(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_fertilizer_rate): passed += 1; print("  ✅ agriculture::fertilizer_rate =", _v_fertilizer_rate)
    else: failed += 1; print("  ❌ agriculture::fertilizer_rate → non-finite:", _v_fertilizer_rate)
    var _v_seed_rate = seed_rate(0.5, 0.5, 0.5)
    if is_finite(_v_seed_rate): passed += 1; print("  ✅ agriculture::seed_rate =", _v_seed_rate)
    else: failed += 1; print("  ❌ agriculture::seed_rate → non-finite:", _v_seed_rate)
    var _v_harvest_index = harvest_index(0.5, 0.5)
    if is_finite(_v_harvest_index): passed += 1; print("  ✅ agriculture::harvest_index =", _v_harvest_index)
    else: failed += 1; print("  ❌ agriculture::harvest_index → non-finite:", _v_harvest_index)
    var _v_yield_per_hectare = yield_per_hectare(0.5, 0.5)
    if is_finite(_v_yield_per_hectare): passed += 1; print("  ✅ agriculture::yield_per_hectare =", _v_yield_per_hectare)
    else: failed += 1; print("  ❌ agriculture::yield_per_hectare → non-finite:", _v_yield_per_hectare)
    var _v_soil_ph_lime_requirement = soil_ph_lime_requirement(0.5, 0.5, 0.5)
    if is_finite(_v_soil_ph_lime_requirement): passed += 1; print("  ✅ agriculture::soil_ph_lime_requirement =", _v_soil_ph_lime_requirement)
    else: failed += 1; print("  ❌ agriculture::soil_ph_lime_requirement → non-finite:", _v_soil_ph_lime_requirement)
    var _v_water_use_efficiency = water_use_efficiency(0.5, 0.5)
    if is_finite(_v_water_use_efficiency): passed += 1; print("  ✅ agriculture::water_use_efficiency =", _v_water_use_efficiency)
    else: failed += 1; print("  ❌ agriculture::water_use_efficiency → non-finite:", _v_water_use_efficiency)
    var _v_photosynthetically_active_radiation = photosynthetically_active_radiation(0.5)
    if is_finite(_v_photosynthetically_active_radiation): passed += 1; print("  ✅ agriculture::photosynthetically_active_radiation =", _v_photosynthetically_active_radiation)
    else: failed += 1; print("  ❌ agriculture::photosynthetically_active_radiation → non-finite:", _v_photosynthetically_active_radiation)
    var _v_leaf_area_index = leaf_area_index(0.5, 0.5)
    if is_finite(_v_leaf_area_index): passed += 1; print("  ✅ agriculture::leaf_area_index =", _v_leaf_area_index)
    else: failed += 1; print("  ❌ agriculture::leaf_area_index → non-finite:", _v_leaf_area_index)
    var _v_nitrogen_use_efficiency = nitrogen_use_efficiency(0.5, 0.5)
    if is_finite(_v_nitrogen_use_efficiency): passed += 1; print("  ✅ agriculture::nitrogen_use_efficiency =", _v_nitrogen_use_efficiency)
    else: failed += 1; print("  ❌ agriculture::nitrogen_use_efficiency → non-finite:", _v_nitrogen_use_efficiency)

    print("  [agriculture] Passed:", passed, "Failed:", failed)
