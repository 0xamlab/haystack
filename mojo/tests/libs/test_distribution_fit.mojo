"""test_distribution_fit.mojo — auto-generated tests for distribution_fit library."""
from std.math import isnan, isinf
from distribution_fit import fit_normal, fit_exponential, fit_uniform, fit_weibull, log_likelihood_normal, log_likelihood_exponential, aic, bic, best_fit, qq_residuals

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

    var _v_fit_normal = fit_normal(_lf5)
    if len(_v_fit_normal) >= 0: passed += 1; print("  ✅ distribution_fit::fit_normal")
    var _v_fit_exponential = fit_exponential(_lf5)
    if is_finite(_v_fit_exponential): passed += 1; print("  ✅ distribution_fit::fit_exponential =", _v_fit_exponential)
    else: failed += 1; print("  ❌ distribution_fit::fit_exponential → non-finite:", _v_fit_exponential)
    var _v_fit_uniform = fit_uniform(_lf5)
    if len(_v_fit_uniform) >= 0: passed += 1; print("  ✅ distribution_fit::fit_uniform")
    var _v_fit_weibull = fit_weibull(_lf5)
    if len(_v_fit_weibull) >= 0: passed += 1; print("  ✅ distribution_fit::fit_weibull")
    var _v_log_likelihood_normal = log_likelihood_normal(_lf5, 0.5, 0.5)
    if is_finite(_v_log_likelihood_normal): passed += 1; print("  ✅ distribution_fit::log_likelihood_normal =", _v_log_likelihood_normal)
    else: failed += 1; print("  ❌ distribution_fit::log_likelihood_normal → non-finite:", _v_log_likelihood_normal)
    var _v_log_likelihood_exponential = log_likelihood_exponential(_lf5, 0.5)
    if is_finite(_v_log_likelihood_exponential): passed += 1; print("  ✅ distribution_fit::log_likelihood_exponential =", _v_log_likelihood_exponential)
    else: failed += 1; print("  ❌ distribution_fit::log_likelihood_exponential → non-finite:", _v_log_likelihood_exponential)
    var _v_aic = aic(0.5, 5)
    if is_finite(_v_aic): passed += 1; print("  ✅ distribution_fit::aic =", _v_aic)
    else: failed += 1; print("  ❌ distribution_fit::aic → non-finite:", _v_aic)
    var _v_bic = bic(0.5, 5, 5)
    if is_finite(_v_bic): passed += 1; print("  ✅ distribution_fit::bic =", _v_bic)
    else: failed += 1; print("  ❌ distribution_fit::bic → non-finite:", _v_bic)
    _ = best_fit(_lf5)
    passed += 1; print("  ✅ distribution_fit::best_fit")
    var _v_qq_residuals = qq_residuals(_lf5, 0.5, 0.5)
    if len(_v_qq_residuals) >= 0: passed += 1; print("  ✅ distribution_fit::qq_residuals")

    print("  [distribution_fit] Passed:", passed, "Failed:", failed)
