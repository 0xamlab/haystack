"""test_rubber.mojo — auto-generated tests for rubber library."""
from std.math import isnan, isinf
from rubber import shore_a_to_youngs_modulus, mooney_viscosity_index, tensile_set, compression_set, elongation_at_break, tear_strength, resilience_rebound, hardness_change_aging, swelling_percentage, crosslink_density_estimate, abrasion_loss_volume, heat_buildup

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

    var _v_shore_a_to_youngs_modulus = shore_a_to_youngs_modulus(0.5)
    if is_finite(_v_shore_a_to_youngs_modulus): passed += 1; print("  ✅ rubber::shore_a_to_youngs_modulus =", _v_shore_a_to_youngs_modulus)
    else: failed += 1; print("  ❌ rubber::shore_a_to_youngs_modulus → non-finite:", _v_shore_a_to_youngs_modulus)
    var _v_mooney_viscosity_index = mooney_viscosity_index(0.5, 0.5)
    if is_finite(_v_mooney_viscosity_index): passed += 1; print("  ✅ rubber::mooney_viscosity_index =", _v_mooney_viscosity_index)
    else: failed += 1; print("  ❌ rubber::mooney_viscosity_index → non-finite:", _v_mooney_viscosity_index)
    var _v_tensile_set = tensile_set(0.5, 0.5, 0.5)
    if is_finite(_v_tensile_set): passed += 1; print("  ✅ rubber::tensile_set =", _v_tensile_set)
    else: failed += 1; print("  ❌ rubber::tensile_set → non-finite:", _v_tensile_set)
    var _v_compression_set = compression_set(0.5, 0.5, 0.5)
    if is_finite(_v_compression_set): passed += 1; print("  ✅ rubber::compression_set =", _v_compression_set)
    else: failed += 1; print("  ❌ rubber::compression_set → non-finite:", _v_compression_set)
    var _v_elongation_at_break = elongation_at_break(0.5, 0.5)
    if is_finite(_v_elongation_at_break): passed += 1; print("  ✅ rubber::elongation_at_break =", _v_elongation_at_break)
    else: failed += 1; print("  ❌ rubber::elongation_at_break → non-finite:", _v_elongation_at_break)
    var _v_tear_strength = tear_strength(0.5, 0.5)
    if is_finite(_v_tear_strength): passed += 1; print("  ✅ rubber::tear_strength =", _v_tear_strength)
    else: failed += 1; print("  ❌ rubber::tear_strength → non-finite:", _v_tear_strength)
    var _v_resilience_rebound = resilience_rebound(0.5, 0.5)
    if is_finite(_v_resilience_rebound): passed += 1; print("  ✅ rubber::resilience_rebound =", _v_resilience_rebound)
    else: failed += 1; print("  ❌ rubber::resilience_rebound → non-finite:", _v_resilience_rebound)
    var _v_hardness_change_aging = hardness_change_aging(0.5, 0.5)
    if is_finite(_v_hardness_change_aging): passed += 1; print("  ✅ rubber::hardness_change_aging =", _v_hardness_change_aging)
    else: failed += 1; print("  ❌ rubber::hardness_change_aging → non-finite:", _v_hardness_change_aging)
    var _v_swelling_percentage = swelling_percentage(0.5, 0.5)
    if is_finite(_v_swelling_percentage): passed += 1; print("  ✅ rubber::swelling_percentage =", _v_swelling_percentage)
    else: failed += 1; print("  ❌ rubber::swelling_percentage → non-finite:", _v_swelling_percentage)
    var _v_crosslink_density_estimate = crosslink_density_estimate(0.5, 0.5, 0.5)
    if is_finite(_v_crosslink_density_estimate): passed += 1; print("  ✅ rubber::crosslink_density_estimate =", _v_crosslink_density_estimate)
    else: failed += 1; print("  ❌ rubber::crosslink_density_estimate → non-finite:", _v_crosslink_density_estimate)
    var _v_abrasion_loss_volume = abrasion_loss_volume(0.5, 0.5)
    if is_finite(_v_abrasion_loss_volume): passed += 1; print("  ✅ rubber::abrasion_loss_volume =", _v_abrasion_loss_volume)
    else: failed += 1; print("  ❌ rubber::abrasion_loss_volume → non-finite:", _v_abrasion_loss_volume)
    var _v_heat_buildup = heat_buildup(0.5, 0.5, 0.5)
    if is_finite(_v_heat_buildup): passed += 1; print("  ✅ rubber::heat_buildup =", _v_heat_buildup)
    else: failed += 1; print("  ❌ rubber::heat_buildup → non-finite:", _v_heat_buildup)

    print("  [rubber] Passed:", passed, "Failed:", failed)
