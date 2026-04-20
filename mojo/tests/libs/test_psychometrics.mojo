"""test_psychometrics.mojo — auto-generated tests for psychometrics library."""
from std.math import isnan, isinf
from psychometrics import item_difficulty, item_discrimination, point_biserial, kuder_richardson_20, cronbach_alpha, spearman_brown_prophecy, standard_error_of_measurement, z_score, t_score, stanine, irt_1pl_probability, irt_2pl_probability

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

    var _v_item_difficulty = item_difficulty(0.5, 0.5)
    if is_finite(_v_item_difficulty): passed += 1; print("  ✅ psychometrics::item_difficulty =", _v_item_difficulty)
    else: failed += 1; print("  ❌ psychometrics::item_difficulty → non-finite:", _v_item_difficulty)
    var _v_item_discrimination = item_discrimination(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_item_discrimination): passed += 1; print("  ✅ psychometrics::item_discrimination =", _v_item_discrimination)
    else: failed += 1; print("  ❌ psychometrics::item_discrimination → non-finite:", _v_item_discrimination)
    var _v_point_biserial = point_biserial(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_point_biserial): passed += 1; print("  ✅ psychometrics::point_biserial =", _v_point_biserial)
    else: failed += 1; print("  ❌ psychometrics::point_biserial → non-finite:", _v_point_biserial)
    var _v_kuder_richardson_20 = kuder_richardson_20(0.5, 0.5, 0.5)
    if is_finite(_v_kuder_richardson_20): passed += 1; print("  ✅ psychometrics::kuder_richardson_20 =", _v_kuder_richardson_20)
    else: failed += 1; print("  ❌ psychometrics::kuder_richardson_20 → non-finite:", _v_kuder_richardson_20)
    var _v_cronbach_alpha = cronbach_alpha(0.5, 0.5, 0.5)
    if is_finite(_v_cronbach_alpha): passed += 1; print("  ✅ psychometrics::cronbach_alpha =", _v_cronbach_alpha)
    else: failed += 1; print("  ❌ psychometrics::cronbach_alpha → non-finite:", _v_cronbach_alpha)
    var _v_spearman_brown_prophecy = spearman_brown_prophecy(0.5, 0.5)
    if is_finite(_v_spearman_brown_prophecy): passed += 1; print("  ✅ psychometrics::spearman_brown_prophecy =", _v_spearman_brown_prophecy)
    else: failed += 1; print("  ❌ psychometrics::spearman_brown_prophecy → non-finite:", _v_spearman_brown_prophecy)
    var _v_standard_error_of_measurement = standard_error_of_measurement(0.5, 0.5)
    if is_finite(_v_standard_error_of_measurement): passed += 1; print("  ✅ psychometrics::standard_error_of_measurement =", _v_standard_error_of_measurement)
    else: failed += 1; print("  ❌ psychometrics::standard_error_of_measurement → non-finite:", _v_standard_error_of_measurement)
    var _v_z_score = z_score(0.5, 0.5, 0.5)
    if is_finite(_v_z_score): passed += 1; print("  ✅ psychometrics::z_score =", _v_z_score)
    else: failed += 1; print("  ❌ psychometrics::z_score → non-finite:", _v_z_score)
    var _v_t_score = t_score(0.5)
    if is_finite(_v_t_score): passed += 1; print("  ✅ psychometrics::t_score =", _v_t_score)
    else: failed += 1; print("  ❌ psychometrics::t_score → non-finite:", _v_t_score)
    _ = stanine(0.5)
    passed += 1; print("  ✅ psychometrics::stanine")
    var _v_irt_1pl_probability = irt_1pl_probability(0.5, 0.5)
    if is_finite(_v_irt_1pl_probability): passed += 1; print("  ✅ psychometrics::irt_1pl_probability =", _v_irt_1pl_probability)
    else: failed += 1; print("  ❌ psychometrics::irt_1pl_probability → non-finite:", _v_irt_1pl_probability)
    var _v_irt_2pl_probability = irt_2pl_probability(0.5, 0.5, 0.5)
    if is_finite(_v_irt_2pl_probability): passed += 1; print("  ✅ psychometrics::irt_2pl_probability =", _v_irt_2pl_probability)
    else: failed += 1; print("  ❌ psychometrics::irt_2pl_probability → non-finite:", _v_irt_2pl_probability)

    print("  [psychometrics] Passed:", passed, "Failed:", failed)
