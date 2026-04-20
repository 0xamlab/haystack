"""test_probability.mojo — auto-generated tests for probability library."""
from std.math import isnan, isinf
from probability import bayes, joint_probability, total_probability, factorial, combinations, permutations, binomial_pmf, poisson_pmf, entropy, kl_divergence

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

    var _v_bayes = bayes(0.5, 0.5, 0.5)
    if is_finite(_v_bayes): passed += 1; print("  ✅ probability::bayes =", _v_bayes)
    else: failed += 1; print("  ❌ probability::bayes → non-finite:", _v_bayes)
    var _v_joint_probability = joint_probability(0.5, 0.5)
    if is_finite(_v_joint_probability): passed += 1; print("  ✅ probability::joint_probability =", _v_joint_probability)
    else: failed += 1; print("  ❌ probability::joint_probability → non-finite:", _v_joint_probability)
    var _v_total_probability = total_probability(_lf5, _lf5)
    if is_finite(_v_total_probability): passed += 1; print("  ✅ probability::total_probability =", _v_total_probability)
    else: failed += 1; print("  ❌ probability::total_probability → non-finite:", _v_total_probability)
    var _v_factorial = factorial(5)
    if is_finite(_v_factorial): passed += 1; print("  ✅ probability::factorial =", _v_factorial)
    else: failed += 1; print("  ❌ probability::factorial → non-finite:", _v_factorial)
    var _v_combinations = combinations(5, 5)
    if is_finite(_v_combinations): passed += 1; print("  ✅ probability::combinations =", _v_combinations)
    else: failed += 1; print("  ❌ probability::combinations → non-finite:", _v_combinations)
    var _v_permutations = permutations(5, 5)
    if is_finite(_v_permutations): passed += 1; print("  ✅ probability::permutations =", _v_permutations)
    else: failed += 1; print("  ❌ probability::permutations → non-finite:", _v_permutations)
    var _v_binomial_pmf = binomial_pmf(5, 5, 0.5)
    if is_finite(_v_binomial_pmf): passed += 1; print("  ✅ probability::binomial_pmf =", _v_binomial_pmf)
    else: failed += 1; print("  ❌ probability::binomial_pmf → non-finite:", _v_binomial_pmf)
    var _v_poisson_pmf = poisson_pmf(5, 0.5)
    if is_finite(_v_poisson_pmf): passed += 1; print("  ✅ probability::poisson_pmf =", _v_poisson_pmf)
    else: failed += 1; print("  ❌ probability::poisson_pmf → non-finite:", _v_poisson_pmf)
    var _v_entropy = entropy(_lf5)
    if is_finite(_v_entropy): passed += 1; print("  ✅ probability::entropy =", _v_entropy)
    else: failed += 1; print("  ❌ probability::entropy → non-finite:", _v_entropy)
    var _v_kl_divergence = kl_divergence(_lf5, _lf5)
    if is_finite(_v_kl_divergence): passed += 1; print("  ✅ probability::kl_divergence =", _v_kl_divergence)
    else: failed += 1; print("  ❌ probability::kl_divergence → non-finite:", _v_kl_divergence)

    print("  [probability] Passed:", passed, "Failed:", failed)
