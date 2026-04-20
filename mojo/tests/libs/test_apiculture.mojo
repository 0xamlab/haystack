"""test_apiculture.mojo — auto-generated tests for apiculture library."""
from std.math import isnan, isinf
from apiculture import honey_yield_per_hive, colony_strength_estimate, varroa_infestation_rate, sugar_syrup_ratio, foraging_range_area, nectar_to_honey_ratio, brood_viability, winter_feed_requirement, queen_laying_rate, pollination_value, hive_density_per_hectare, overwintering_survival_rate

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

    var _v_honey_yield_per_hive = honey_yield_per_hive(0.5, 0.5)
    if is_finite(_v_honey_yield_per_hive): passed += 1; print("  ✅ apiculture::honey_yield_per_hive =", _v_honey_yield_per_hive)
    else: failed += 1; print("  ❌ apiculture::honey_yield_per_hive → non-finite:", _v_honey_yield_per_hive)
    var _v_colony_strength_estimate = colony_strength_estimate(0.5, 0.5)
    if is_finite(_v_colony_strength_estimate): passed += 1; print("  ✅ apiculture::colony_strength_estimate =", _v_colony_strength_estimate)
    else: failed += 1; print("  ❌ apiculture::colony_strength_estimate → non-finite:", _v_colony_strength_estimate)
    var _v_varroa_infestation_rate = varroa_infestation_rate(0.5, 0.5)
    if is_finite(_v_varroa_infestation_rate): passed += 1; print("  ✅ apiculture::varroa_infestation_rate =", _v_varroa_infestation_rate)
    else: failed += 1; print("  ❌ apiculture::varroa_infestation_rate → non-finite:", _v_varroa_infestation_rate)
    var _v_sugar_syrup_ratio = sugar_syrup_ratio(0.5, 0.5)
    if is_finite(_v_sugar_syrup_ratio): passed += 1; print("  ✅ apiculture::sugar_syrup_ratio =", _v_sugar_syrup_ratio)
    else: failed += 1; print("  ❌ apiculture::sugar_syrup_ratio → non-finite:", _v_sugar_syrup_ratio)
    var _v_foraging_range_area = foraging_range_area(0.5)
    if is_finite(_v_foraging_range_area): passed += 1; print("  ✅ apiculture::foraging_range_area =", _v_foraging_range_area)
    else: failed += 1; print("  ❌ apiculture::foraging_range_area → non-finite:", _v_foraging_range_area)
    var _v_nectar_to_honey_ratio = nectar_to_honey_ratio(0.5)
    if is_finite(_v_nectar_to_honey_ratio): passed += 1; print("  ✅ apiculture::nectar_to_honey_ratio =", _v_nectar_to_honey_ratio)
    else: failed += 1; print("  ❌ apiculture::nectar_to_honey_ratio → non-finite:", _v_nectar_to_honey_ratio)
    var _v_brood_viability = brood_viability(0.5, 0.5)
    if is_finite(_v_brood_viability): passed += 1; print("  ✅ apiculture::brood_viability =", _v_brood_viability)
    else: failed += 1; print("  ❌ apiculture::brood_viability → non-finite:", _v_brood_viability)
    var _v_winter_feed_requirement = winter_feed_requirement(0.5, 0.5, 0.5)
    if is_finite(_v_winter_feed_requirement): passed += 1; print("  ✅ apiculture::winter_feed_requirement =", _v_winter_feed_requirement)
    else: failed += 1; print("  ❌ apiculture::winter_feed_requirement → non-finite:", _v_winter_feed_requirement)
    var _v_queen_laying_rate = queen_laying_rate(0.5)
    if is_finite(_v_queen_laying_rate): passed += 1; print("  ✅ apiculture::queen_laying_rate =", _v_queen_laying_rate)
    else: failed += 1; print("  ❌ apiculture::queen_laying_rate → non-finite:", _v_queen_laying_rate)
    var _v_pollination_value = pollination_value(0.5, 0.5)
    if is_finite(_v_pollination_value): passed += 1; print("  ✅ apiculture::pollination_value =", _v_pollination_value)
    else: failed += 1; print("  ❌ apiculture::pollination_value → non-finite:", _v_pollination_value)
    var _v_hive_density_per_hectare = hive_density_per_hectare(0.5, 0.5)
    if is_finite(_v_hive_density_per_hectare): passed += 1; print("  ✅ apiculture::hive_density_per_hectare =", _v_hive_density_per_hectare)
    else: failed += 1; print("  ❌ apiculture::hive_density_per_hectare → non-finite:", _v_hive_density_per_hectare)
    var _v_overwintering_survival_rate = overwintering_survival_rate(0.5, 0.5)
    if is_finite(_v_overwintering_survival_rate): passed += 1; print("  ✅ apiculture::overwintering_survival_rate =", _v_overwintering_survival_rate)
    else: failed += 1; print("  ❌ apiculture::overwintering_survival_rate → non-finite:", _v_overwintering_survival_rate)

    print("  [apiculture] Passed:", passed, "Failed:", failed)
