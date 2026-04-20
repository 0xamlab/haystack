"""bench_bayesian_inference.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from bayesian_inference import bayes_update_log, prior_predictive, variational_elbo_term, mean_field_update_mean, mean_field_update_var, laplace_approx_log_posterior, expected_information_gain, credible_interval_half_width, kl_gaussians, jeffreys_prior_gaussian
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_bayes_update_log: Float64 = 0.0
    var _t0_bayes_update_log = perf_counter_ns()
    for _ in range(N):
        _acc_bayes_update_log += bayes_update_log(0.5, 0.5)
    var _t1_bayes_update_log = perf_counter_ns()
    var _ns_bayes_update_log = Float64(_t1_bayes_update_log - _t0_bayes_update_log) / Float64(N)
    print("MOJO_TIMING bayesian_inference::bayes_update_log", _ns_bayes_update_log, _acc_bayes_update_log)
    var _acc_prior_predictive: Float64 = 0.0
    var _t0_prior_predictive = perf_counter_ns()
    for _ in range(N):
        _acc_prior_predictive += prior_predictive(0.5, 0.5)
    var _t1_prior_predictive = perf_counter_ns()
    var _ns_prior_predictive = Float64(_t1_prior_predictive - _t0_prior_predictive) / Float64(N)
    print("MOJO_TIMING bayesian_inference::prior_predictive", _ns_prior_predictive, _acc_prior_predictive)
    var _acc_variational_elbo_term: Float64 = 0.0
    var _t0_variational_elbo_term = perf_counter_ns()
    for _ in range(N):
        _acc_variational_elbo_term += variational_elbo_term(0.5, 0.5)
    var _t1_variational_elbo_term = perf_counter_ns()
    var _ns_variational_elbo_term = Float64(_t1_variational_elbo_term - _t0_variational_elbo_term) / Float64(N)
    print("MOJO_TIMING bayesian_inference::variational_elbo_term", _ns_variational_elbo_term, _acc_variational_elbo_term)
    var _acc_mean_field_update_mean: Float64 = 0.0
    var _t0_mean_field_update_mean = perf_counter_ns()
    for _ in range(N):
        _acc_mean_field_update_mean += mean_field_update_mean(0.5, 0.5)
    var _t1_mean_field_update_mean = perf_counter_ns()
    var _ns_mean_field_update_mean = Float64(_t1_mean_field_update_mean - _t0_mean_field_update_mean) / Float64(N)
    print("MOJO_TIMING bayesian_inference::mean_field_update_mean", _ns_mean_field_update_mean, _acc_mean_field_update_mean)
    var _acc_mean_field_update_var: Float64 = 0.0
    var _t0_mean_field_update_var = perf_counter_ns()
    for _ in range(N):
        _acc_mean_field_update_var += mean_field_update_var(0.5)
    var _t1_mean_field_update_var = perf_counter_ns()
    var _ns_mean_field_update_var = Float64(_t1_mean_field_update_var - _t0_mean_field_update_var) / Float64(N)
    print("MOJO_TIMING bayesian_inference::mean_field_update_var", _ns_mean_field_update_var, _acc_mean_field_update_var)
    var _acc_laplace_approx_log_posterior: Float64 = 0.0
    var _t0_laplace_approx_log_posterior = perf_counter_ns()
    for _ in range(N):
        _acc_laplace_approx_log_posterior += laplace_approx_log_posterior(0.5, 0.5, 0.5, 0.5)
    var _t1_laplace_approx_log_posterior = perf_counter_ns()
    var _ns_laplace_approx_log_posterior = Float64(_t1_laplace_approx_log_posterior - _t0_laplace_approx_log_posterior) / Float64(N)
    print("MOJO_TIMING bayesian_inference::laplace_approx_log_posterior", _ns_laplace_approx_log_posterior, _acc_laplace_approx_log_posterior)
    var _acc_expected_information_gain: Float64 = 0.0
    var _t0_expected_information_gain = perf_counter_ns()
    for _ in range(N):
        _acc_expected_information_gain += expected_information_gain(0.5, 0.5)
    var _t1_expected_information_gain = perf_counter_ns()
    var _ns_expected_information_gain = Float64(_t1_expected_information_gain - _t0_expected_information_gain) / Float64(N)
    print("MOJO_TIMING bayesian_inference::expected_information_gain", _ns_expected_information_gain, _acc_expected_information_gain)
    var _acc_credible_interval_half_width: Float64 = 0.0
    var _t0_credible_interval_half_width = perf_counter_ns()
    for _ in range(N):
        _acc_credible_interval_half_width += credible_interval_half_width(0.5, 0.5)
    var _t1_credible_interval_half_width = perf_counter_ns()
    var _ns_credible_interval_half_width = Float64(_t1_credible_interval_half_width - _t0_credible_interval_half_width) / Float64(N)
    print("MOJO_TIMING bayesian_inference::credible_interval_half_width", _ns_credible_interval_half_width, _acc_credible_interval_half_width)
    var _acc_kl_gaussians: Float64 = 0.0
    var _t0_kl_gaussians = perf_counter_ns()
    for _ in range(N):
        _acc_kl_gaussians += kl_gaussians(0.5, 0.5, 0.5, 0.5)
    var _t1_kl_gaussians = perf_counter_ns()
    var _ns_kl_gaussians = Float64(_t1_kl_gaussians - _t0_kl_gaussians) / Float64(N)
    print("MOJO_TIMING bayesian_inference::kl_gaussians", _ns_kl_gaussians, _acc_kl_gaussians)
    var _acc_jeffreys_prior_gaussian: Float64 = 0.0
    var _t0_jeffreys_prior_gaussian = perf_counter_ns()
    for _ in range(N):
        _acc_jeffreys_prior_gaussian += jeffreys_prior_gaussian(0.5)
    var _t1_jeffreys_prior_gaussian = perf_counter_ns()
    var _ns_jeffreys_prior_gaussian = Float64(_t1_jeffreys_prior_gaussian - _t0_jeffreys_prior_gaussian) / Float64(N)
    print("MOJO_TIMING bayesian_inference::jeffreys_prior_gaussian", _ns_jeffreys_prior_gaussian, _acc_jeffreys_prior_gaussian)
