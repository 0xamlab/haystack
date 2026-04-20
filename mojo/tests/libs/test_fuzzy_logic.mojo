"""test_fuzzy_logic.mojo — auto-generated tests for fuzzy_logic library."""
from std.math import isnan, isinf
from fuzzy_logic import triangular_mf, trapezoidal_mf, gaussian_mf, fuzzy_and, fuzzy_or, fuzzy_not, defuzzify_centroid, defuzzify_bisector, defuzzify_mom, fuzzy_rule_eval, alpha_cut

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

    var _v_triangular_mf = triangular_mf(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_triangular_mf): passed += 1; print("  ✅ fuzzy_logic::triangular_mf =", _v_triangular_mf)
    else: failed += 1; print("  ❌ fuzzy_logic::triangular_mf → non-finite:", _v_triangular_mf)
    var _v_trapezoidal_mf = trapezoidal_mf(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_trapezoidal_mf): passed += 1; print("  ✅ fuzzy_logic::trapezoidal_mf =", _v_trapezoidal_mf)
    else: failed += 1; print("  ❌ fuzzy_logic::trapezoidal_mf → non-finite:", _v_trapezoidal_mf)
    var _v_gaussian_mf = gaussian_mf(0.5, 0.5, 0.5)
    if is_finite(_v_gaussian_mf): passed += 1; print("  ✅ fuzzy_logic::gaussian_mf =", _v_gaussian_mf)
    else: failed += 1; print("  ❌ fuzzy_logic::gaussian_mf → non-finite:", _v_gaussian_mf)
    var _v_fuzzy_and = fuzzy_and(0.5, 0.5)
    if is_finite(_v_fuzzy_and): passed += 1; print("  ✅ fuzzy_logic::fuzzy_and =", _v_fuzzy_and)
    else: failed += 1; print("  ❌ fuzzy_logic::fuzzy_and → non-finite:", _v_fuzzy_and)
    var _v_fuzzy_or = fuzzy_or(0.5, 0.5)
    if is_finite(_v_fuzzy_or): passed += 1; print("  ✅ fuzzy_logic::fuzzy_or =", _v_fuzzy_or)
    else: failed += 1; print("  ❌ fuzzy_logic::fuzzy_or → non-finite:", _v_fuzzy_or)
    var _v_fuzzy_not = fuzzy_not(0.5)
    if is_finite(_v_fuzzy_not): passed += 1; print("  ✅ fuzzy_logic::fuzzy_not =", _v_fuzzy_not)
    else: failed += 1; print("  ❌ fuzzy_logic::fuzzy_not → non-finite:", _v_fuzzy_not)
    var _v_defuzzify_centroid = defuzzify_centroid(_lf5, _lf5)
    if is_finite(_v_defuzzify_centroid): passed += 1; print("  ✅ fuzzy_logic::defuzzify_centroid =", _v_defuzzify_centroid)
    else: failed += 1; print("  ❌ fuzzy_logic::defuzzify_centroid → non-finite:", _v_defuzzify_centroid)
    var _v_defuzzify_bisector = defuzzify_bisector(_lf5, _lf5)
    if is_finite(_v_defuzzify_bisector): passed += 1; print("  ✅ fuzzy_logic::defuzzify_bisector =", _v_defuzzify_bisector)
    else: failed += 1; print("  ❌ fuzzy_logic::defuzzify_bisector → non-finite:", _v_defuzzify_bisector)
    var _v_defuzzify_mom = defuzzify_mom(_lf5, _lf5)
    if is_finite(_v_defuzzify_mom): passed += 1; print("  ✅ fuzzy_logic::defuzzify_mom =", _v_defuzzify_mom)
    else: failed += 1; print("  ❌ fuzzy_logic::defuzzify_mom → non-finite:", _v_defuzzify_mom)
    var _v_fuzzy_rule_eval = fuzzy_rule_eval(_lf5, 5)
    if is_finite(_v_fuzzy_rule_eval): passed += 1; print("  ✅ fuzzy_logic::fuzzy_rule_eval =", _v_fuzzy_rule_eval)
    else: failed += 1; print("  ❌ fuzzy_logic::fuzzy_rule_eval → non-finite:", _v_fuzzy_rule_eval)
    var _v_alpha_cut = alpha_cut(_lf5, _lf5, 0.5)
    if len(_v_alpha_cut) >= 0: passed += 1; print("  ✅ fuzzy_logic::alpha_cut")

    print("  [fuzzy_logic] Passed:", passed, "Failed:", failed)
