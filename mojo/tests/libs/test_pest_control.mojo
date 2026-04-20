"""test_pest_control.mojo — auto-generated tests for pest_control library."""
from std.math import isnan, isinf
from pest_control import economic_threshold, economic_injury_level, pest_density, trap_catch_rate, spray_coverage, dilution_rate, residual_effectiveness, resistance_ratio, biocontrol_release_rate, fumigation_ct, bait_station_density, population_reduction

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

    var _v_economic_threshold = economic_threshold(0.5, 0.5, 0.5)
    if is_finite(_v_economic_threshold): passed += 1; print("  ✅ pest_control::economic_threshold =", _v_economic_threshold)
    else: failed += 1; print("  ❌ pest_control::economic_threshold → non-finite:", _v_economic_threshold)
    var _v_economic_injury_level = economic_injury_level(0.5, 0.5)
    if is_finite(_v_economic_injury_level): passed += 1; print("  ✅ pest_control::economic_injury_level =", _v_economic_injury_level)
    else: failed += 1; print("  ❌ pest_control::economic_injury_level → non-finite:", _v_economic_injury_level)
    var _v_pest_density = pest_density(0.5, 0.5)
    if is_finite(_v_pest_density): passed += 1; print("  ✅ pest_control::pest_density =", _v_pest_density)
    else: failed += 1; print("  ❌ pest_control::pest_density → non-finite:", _v_pest_density)
    var _v_trap_catch_rate = trap_catch_rate(0.5, 0.5, 0.5)
    if is_finite(_v_trap_catch_rate): passed += 1; print("  ✅ pest_control::trap_catch_rate =", _v_trap_catch_rate)
    else: failed += 1; print("  ❌ pest_control::trap_catch_rate → non-finite:", _v_trap_catch_rate)
    var _v_spray_coverage = spray_coverage(0.5, 0.5)
    if is_finite(_v_spray_coverage): passed += 1; print("  ✅ pest_control::spray_coverage =", _v_spray_coverage)
    else: failed += 1; print("  ❌ pest_control::spray_coverage → non-finite:", _v_spray_coverage)
    var _v_dilution_rate = dilution_rate(0.5, 0.5)
    if is_finite(_v_dilution_rate): passed += 1; print("  ✅ pest_control::dilution_rate =", _v_dilution_rate)
    else: failed += 1; print("  ❌ pest_control::dilution_rate → non-finite:", _v_dilution_rate)
    var _v_residual_effectiveness = residual_effectiveness(0.5, 0.5, 0.5)
    if is_finite(_v_residual_effectiveness): passed += 1; print("  ✅ pest_control::residual_effectiveness =", _v_residual_effectiveness)
    else: failed += 1; print("  ❌ pest_control::residual_effectiveness → non-finite:", _v_residual_effectiveness)
    var _v_resistance_ratio = resistance_ratio(0.5, 0.5)
    if is_finite(_v_resistance_ratio): passed += 1; print("  ✅ pest_control::resistance_ratio =", _v_resistance_ratio)
    else: failed += 1; print("  ❌ pest_control::resistance_ratio → non-finite:", _v_resistance_ratio)
    var _v_biocontrol_release_rate = biocontrol_release_rate(0.5, 0.5, 0.5)
    if is_finite(_v_biocontrol_release_rate): passed += 1; print("  ✅ pest_control::biocontrol_release_rate =", _v_biocontrol_release_rate)
    else: failed += 1; print("  ❌ pest_control::biocontrol_release_rate → non-finite:", _v_biocontrol_release_rate)
    var _v_fumigation_ct = fumigation_ct(0.5, 0.5)
    if is_finite(_v_fumigation_ct): passed += 1; print("  ✅ pest_control::fumigation_ct =", _v_fumigation_ct)
    else: failed += 1; print("  ❌ pest_control::fumigation_ct → non-finite:", _v_fumigation_ct)
    var _v_bait_station_density = bait_station_density(0.5, 0.5)
    if is_finite(_v_bait_station_density): passed += 1; print("  ✅ pest_control::bait_station_density =", _v_bait_station_density)
    else: failed += 1; print("  ❌ pest_control::bait_station_density → non-finite:", _v_bait_station_density)
    var _v_population_reduction = population_reduction(0.5, 0.5)
    if is_finite(_v_population_reduction): passed += 1; print("  ✅ pest_control::population_reduction =", _v_population_reduction)
    else: failed += 1; print("  ❌ pest_control::population_reduction → non-finite:", _v_population_reduction)

    print("  [pest_control] Passed:", passed, "Failed:", failed)
