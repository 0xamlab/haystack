"""test_polymer.mojo — auto-generated tests for polymer library."""
from std.math import isnan, isinf
from polymer import degree_of_polymerization, number_average_mw, weight_average_mw, polydispersity_index, mark_houwink, glass_transition_fox, flory_huggins_free_energy, end_to_end_distance, radius_of_gyration, carothers_conversion, melt_flow_index_approx, tensile_modulus_rule_of_mixtures

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

    var _v_degree_of_polymerization = degree_of_polymerization(0.5, 0.5)
    if is_finite(_v_degree_of_polymerization): passed += 1; print("  ✅ polymer::degree_of_polymerization =", _v_degree_of_polymerization)
    else: failed += 1; print("  ❌ polymer::degree_of_polymerization → non-finite:", _v_degree_of_polymerization)
    var _v_number_average_mw = number_average_mw(0.5, 0.5)
    if is_finite(_v_number_average_mw): passed += 1; print("  ✅ polymer::number_average_mw =", _v_number_average_mw)
    else: failed += 1; print("  ❌ polymer::number_average_mw → non-finite:", _v_number_average_mw)
    var _v_weight_average_mw = weight_average_mw(0.5, 0.5)
    if is_finite(_v_weight_average_mw): passed += 1; print("  ✅ polymer::weight_average_mw =", _v_weight_average_mw)
    else: failed += 1; print("  ❌ polymer::weight_average_mw → non-finite:", _v_weight_average_mw)
    var _v_polydispersity_index = polydispersity_index(0.5, 0.5)
    if is_finite(_v_polydispersity_index): passed += 1; print("  ✅ polymer::polydispersity_index =", _v_polydispersity_index)
    else: failed += 1; print("  ❌ polymer::polydispersity_index → non-finite:", _v_polydispersity_index)
    var _v_mark_houwink = mark_houwink(0.5, 0.5, 0.5)
    if is_finite(_v_mark_houwink): passed += 1; print("  ✅ polymer::mark_houwink =", _v_mark_houwink)
    else: failed += 1; print("  ❌ polymer::mark_houwink → non-finite:", _v_mark_houwink)
    var _v_glass_transition_fox = glass_transition_fox(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_glass_transition_fox): passed += 1; print("  ✅ polymer::glass_transition_fox =", _v_glass_transition_fox)
    else: failed += 1; print("  ❌ polymer::glass_transition_fox → non-finite:", _v_glass_transition_fox)
    var _v_flory_huggins_free_energy = flory_huggins_free_energy(0.5, 0.5, 0.5)
    if is_finite(_v_flory_huggins_free_energy): passed += 1; print("  ✅ polymer::flory_huggins_free_energy =", _v_flory_huggins_free_energy)
    else: failed += 1; print("  ❌ polymer::flory_huggins_free_energy → non-finite:", _v_flory_huggins_free_energy)
    var _v_end_to_end_distance = end_to_end_distance(0.5, 0.5)
    if is_finite(_v_end_to_end_distance): passed += 1; print("  ✅ polymer::end_to_end_distance =", _v_end_to_end_distance)
    else: failed += 1; print("  ❌ polymer::end_to_end_distance → non-finite:", _v_end_to_end_distance)
    var _v_radius_of_gyration = radius_of_gyration(0.5)
    if is_finite(_v_radius_of_gyration): passed += 1; print("  ✅ polymer::radius_of_gyration =", _v_radius_of_gyration)
    else: failed += 1; print("  ❌ polymer::radius_of_gyration → non-finite:", _v_radius_of_gyration)
    var _v_carothers_conversion = carothers_conversion(0.5)
    if is_finite(_v_carothers_conversion): passed += 1; print("  ✅ polymer::carothers_conversion =", _v_carothers_conversion)
    else: failed += 1; print("  ❌ polymer::carothers_conversion → non-finite:", _v_carothers_conversion)
    var _v_melt_flow_index_approx = melt_flow_index_approx(0.5, 0.5)
    if is_finite(_v_melt_flow_index_approx): passed += 1; print("  ✅ polymer::melt_flow_index_approx =", _v_melt_flow_index_approx)
    else: failed += 1; print("  ❌ polymer::melt_flow_index_approx → non-finite:", _v_melt_flow_index_approx)
    var _v_tensile_modulus_rule_of_mixtures = tensile_modulus_rule_of_mixtures(0.5, 0.5, 0.5)
    if is_finite(_v_tensile_modulus_rule_of_mixtures): passed += 1; print("  ✅ polymer::tensile_modulus_rule_of_mixtures =", _v_tensile_modulus_rule_of_mixtures)
    else: failed += 1; print("  ❌ polymer::tensile_modulus_rule_of_mixtures → non-finite:", _v_tensile_modulus_rule_of_mixtures)

    print("  [polymer] Passed:", passed, "Failed:", failed)
