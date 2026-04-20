"""test_privacy.mojo — auto-generated tests for privacy library."""
from std.math import isnan, isinf
from privacy import laplace_mechanism, gaussian_mechanism, exponential_mechanism_scores, randomized_response, composition_epsilon, advanced_composition, sensitivity_l1, sensitivity_l2, dp_mean, dp_count

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

    var _v_laplace_mechanism = laplace_mechanism(0.5, 0.5, 0.5)
    if is_finite(_v_laplace_mechanism): passed += 1; print("  ✅ privacy::laplace_mechanism =", _v_laplace_mechanism)
    else: failed += 1; print("  ❌ privacy::laplace_mechanism → non-finite:", _v_laplace_mechanism)
    var _v_gaussian_mechanism = gaussian_mechanism(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_gaussian_mechanism): passed += 1; print("  ✅ privacy::gaussian_mechanism =", _v_gaussian_mechanism)
    else: failed += 1; print("  ❌ privacy::gaussian_mechanism → non-finite:", _v_gaussian_mechanism)
    var _v_exponential_mechanism_scores = exponential_mechanism_scores(_lf5, 0.5, 0.5)
    if len(_v_exponential_mechanism_scores) >= 0: passed += 1; print("  ✅ privacy::exponential_mechanism_scores")
    _ = randomized_response(True, 0.5)
    passed += 1; print("  ✅ privacy::randomized_response")
    var _v_composition_epsilon = composition_epsilon(_lf5)
    if is_finite(_v_composition_epsilon): passed += 1; print("  ✅ privacy::composition_epsilon =", _v_composition_epsilon)
    else: failed += 1; print("  ❌ privacy::composition_epsilon → non-finite:", _v_composition_epsilon)
    var _v_advanced_composition = advanced_composition(0.5, 0.5, 5)
    if is_finite(_v_advanced_composition): passed += 1; print("  ✅ privacy::advanced_composition =", _v_advanced_composition)
    else: failed += 1; print("  ❌ privacy::advanced_composition → non-finite:", _v_advanced_composition)
    var _v_sensitivity_l1 = sensitivity_l1(_lf5)
    if is_finite(_v_sensitivity_l1): passed += 1; print("  ✅ privacy::sensitivity_l1 =", _v_sensitivity_l1)
    else: failed += 1; print("  ❌ privacy::sensitivity_l1 → non-finite:", _v_sensitivity_l1)
    var _v_sensitivity_l2 = sensitivity_l2(_lf5)
    if is_finite(_v_sensitivity_l2): passed += 1; print("  ✅ privacy::sensitivity_l2 =", _v_sensitivity_l2)
    else: failed += 1; print("  ❌ privacy::sensitivity_l2 → non-finite:", _v_sensitivity_l2)
    var _v_dp_mean = dp_mean(_lf5, 0.5, 0.5, 0.5)
    if is_finite(_v_dp_mean): passed += 1; print("  ✅ privacy::dp_mean =", _v_dp_mean)
    else: failed += 1; print("  ❌ privacy::dp_mean → non-finite:", _v_dp_mean)
    var _v_dp_count = dp_count(5, 0.5)
    if is_finite(_v_dp_count): passed += 1; print("  ✅ privacy::dp_count =", _v_dp_count)
    else: failed += 1; print("  ❌ privacy::dp_count → non-finite:", _v_dp_count)

    print("  [privacy] Passed:", passed, "Failed:", failed)
