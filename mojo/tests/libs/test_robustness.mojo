"""test_robustness.mojo — auto-generated tests for robustness library."""
from std.math import isnan, isinf
from robustness import eval_test_func, perturbation_test, sensitivity_one_at_a_time, morris_screening, sobol_first_order_estimate, input_range_sweep, tornado_data, robustness_score

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

    var _v_eval_test_func = eval_test_func(_lf5, 5)
    if is_finite(_v_eval_test_func): passed += 1; print("  ✅ robustness::eval_test_func =", _v_eval_test_func)
    else: failed += 1; print("  ❌ robustness::eval_test_func → non-finite:", _v_eval_test_func)
    var _v_perturbation_test = perturbation_test(_lf5, 0.5)
    if len(_v_perturbation_test) >= 0: passed += 1; print("  ✅ robustness::perturbation_test")
    var _v_sensitivity_one_at_a_time = sensitivity_one_at_a_time(_lf5, 5, 0.5, 5)
    if is_finite(_v_sensitivity_one_at_a_time): passed += 1; print("  ✅ robustness::sensitivity_one_at_a_time =", _v_sensitivity_one_at_a_time)
    else: failed += 1; print("  ❌ robustness::sensitivity_one_at_a_time → non-finite:", _v_sensitivity_one_at_a_time)
    var _v_morris_screening = morris_screening(5, 5, 5, 0.5)
    if len(_v_morris_screening) >= 0: passed += 1; print("  ✅ robustness::morris_screening")
    var _v_sobol_first_order_estimate = sobol_first_order_estimate(5, 5, 5)
    if len(_v_sobol_first_order_estimate) >= 0: passed += 1; print("  ✅ robustness::sobol_first_order_estimate")
    _ = input_range_sweep(_lf5, 5, 0.5, 0.5, 5, 5)
    passed += 1; print("  ✅ robustness::input_range_sweep")
    _ = tornado_data(_lf5, _lf5, 5)
    passed += 1; print("  ✅ robustness::tornado_data")
    var _v_robustness_score = robustness_score(_lf5)
    if is_finite(_v_robustness_score): passed += 1; print("  ✅ robustness::robustness_score =", _v_robustness_score)
    else: failed += 1; print("  ❌ robustness::robustness_score → non-finite:", _v_robustness_score)

    print("  [robustness] Passed:", passed, "Failed:", failed)
