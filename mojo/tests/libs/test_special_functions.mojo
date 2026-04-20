"""test_special_functions.mojo — auto-generated tests for special_functions library."""
from std.math import isnan, isinf
from special_functions import gamma_function, log_gamma, beta_function, digamma, incomplete_gamma_lower, regularized_gamma, erf, erfc, bessel_j0, factorial_float, double_factorial, binomial_coefficient

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

    var _v_gamma_function = gamma_function(0.5)
    if is_finite(_v_gamma_function): passed += 1; print("  ✅ special_functions::gamma_function =", _v_gamma_function)
    else: failed += 1; print("  ❌ special_functions::gamma_function → non-finite:", _v_gamma_function)
    var _v_log_gamma = log_gamma(0.5)
    if is_finite(_v_log_gamma): passed += 1; print("  ✅ special_functions::log_gamma =", _v_log_gamma)
    else: failed += 1; print("  ❌ special_functions::log_gamma → non-finite:", _v_log_gamma)
    var _v_beta_function = beta_function(0.5, 0.5)
    if is_finite(_v_beta_function): passed += 1; print("  ✅ special_functions::beta_function =", _v_beta_function)
    else: failed += 1; print("  ❌ special_functions::beta_function → non-finite:", _v_beta_function)
    var _v_digamma = digamma(0.5)
    if is_finite(_v_digamma): passed += 1; print("  ✅ special_functions::digamma =", _v_digamma)
    else: failed += 1; print("  ❌ special_functions::digamma → non-finite:", _v_digamma)
    var _v_incomplete_gamma_lower = incomplete_gamma_lower(0.5, 0.5)
    if is_finite(_v_incomplete_gamma_lower): passed += 1; print("  ✅ special_functions::incomplete_gamma_lower =", _v_incomplete_gamma_lower)
    else: failed += 1; print("  ❌ special_functions::incomplete_gamma_lower → non-finite:", _v_incomplete_gamma_lower)
    var _v_regularized_gamma = regularized_gamma(0.5, 0.5)
    if is_finite(_v_regularized_gamma): passed += 1; print("  ✅ special_functions::regularized_gamma =", _v_regularized_gamma)
    else: failed += 1; print("  ❌ special_functions::regularized_gamma → non-finite:", _v_regularized_gamma)
    var _v_erf = erf(0.5)
    if is_finite(_v_erf): passed += 1; print("  ✅ special_functions::erf =", _v_erf)
    else: failed += 1; print("  ❌ special_functions::erf → non-finite:", _v_erf)
    var _v_erfc = erfc(0.5)
    if is_finite(_v_erfc): passed += 1; print("  ✅ special_functions::erfc =", _v_erfc)
    else: failed += 1; print("  ❌ special_functions::erfc → non-finite:", _v_erfc)
    var _v_bessel_j0 = bessel_j0(0.5)
    if is_finite(_v_bessel_j0): passed += 1; print("  ✅ special_functions::bessel_j0 =", _v_bessel_j0)
    else: failed += 1; print("  ❌ special_functions::bessel_j0 → non-finite:", _v_bessel_j0)
    var _v_factorial_float = factorial_float(5)
    if is_finite(_v_factorial_float): passed += 1; print("  ✅ special_functions::factorial_float =", _v_factorial_float)
    else: failed += 1; print("  ❌ special_functions::factorial_float → non-finite:", _v_factorial_float)
    var _v_double_factorial = double_factorial(5)
    if is_finite(_v_double_factorial): passed += 1; print("  ✅ special_functions::double_factorial =", _v_double_factorial)
    else: failed += 1; print("  ❌ special_functions::double_factorial → non-finite:", _v_double_factorial)
    var _v_binomial_coefficient = binomial_coefficient(5, 5)
    if is_finite(_v_binomial_coefficient): passed += 1; print("  ✅ special_functions::binomial_coefficient =", _v_binomial_coefficient)
    else: failed += 1; print("  ❌ special_functions::binomial_coefficient → non-finite:", _v_binomial_coefficient)

    print("  [special_functions] Passed:", passed, "Failed:", failed)
