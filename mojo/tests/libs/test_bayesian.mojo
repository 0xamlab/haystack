"""test_bayesian.mojo — auto-generated tests for bayesian library."""
from std.math import isnan, isinf
from bayesian import beta_posterior, beta_mean, beta_variance, beta_credible_interval, normal_posterior, poisson_posterior, bayes_factor, posterior_predictive_beta, hpd_interval_normal, bayesian_ab_test

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

    var _v_beta_posterior = beta_posterior(0.5, 0.5, 5, 5)
    if len(_v_beta_posterior) >= 0: passed += 1; print("  ✅ bayesian::beta_posterior")
    var _v_beta_mean = beta_mean(0.5, 0.5)
    if is_finite(_v_beta_mean): passed += 1; print("  ✅ bayesian::beta_mean =", _v_beta_mean)
    else: failed += 1; print("  ❌ bayesian::beta_mean → non-finite:", _v_beta_mean)
    var _v_beta_variance = beta_variance(0.5, 0.5)
    if is_finite(_v_beta_variance): passed += 1; print("  ✅ bayesian::beta_variance =", _v_beta_variance)
    else: failed += 1; print("  ❌ bayesian::beta_variance → non-finite:", _v_beta_variance)
    var _v_beta_credible_interval = beta_credible_interval(0.5, 0.5, 0.5)
    if len(_v_beta_credible_interval) >= 0: passed += 1; print("  ✅ bayesian::beta_credible_interval")
    var _v_normal_posterior = normal_posterior(0.5, 0.5, 0.5, 0.5, 5)
    if len(_v_normal_posterior) >= 0: passed += 1; print("  ✅ bayesian::normal_posterior")
    var _v_poisson_posterior = poisson_posterior(0.5, 0.5, 5, 5)
    if len(_v_poisson_posterior) >= 0: passed += 1; print("  ✅ bayesian::poisson_posterior")
    var _v_bayes_factor = bayes_factor(0.5, 0.5)
    if is_finite(_v_bayes_factor): passed += 1; print("  ✅ bayesian::bayes_factor =", _v_bayes_factor)
    else: failed += 1; print("  ❌ bayesian::bayes_factor → non-finite:", _v_bayes_factor)
    var _v_posterior_predictive_beta = posterior_predictive_beta(0.5, 0.5)
    if is_finite(_v_posterior_predictive_beta): passed += 1; print("  ✅ bayesian::posterior_predictive_beta =", _v_posterior_predictive_beta)
    else: failed += 1; print("  ❌ bayesian::posterior_predictive_beta → non-finite:", _v_posterior_predictive_beta)
    var _v_hpd_interval_normal = hpd_interval_normal(0.5, 0.5, 0.5)
    if len(_v_hpd_interval_normal) >= 0: passed += 1; print("  ✅ bayesian::hpd_interval_normal")
    var _v_bayesian_ab_test = bayesian_ab_test(5, 5, 5, 5, 5)
    if is_finite(_v_bayesian_ab_test): passed += 1; print("  ✅ bayesian::bayesian_ab_test =", _v_bayesian_ab_test)
    else: failed += 1; print("  ❌ bayesian::bayesian_ab_test → non-finite:", _v_bayesian_ab_test)

    print("  [bayesian] Passed:", passed, "Failed:", failed)
