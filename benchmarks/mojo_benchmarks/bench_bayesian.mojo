"""bench_bayesian.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from bayesian import beta_posterior, beta_mean, beta_variance, beta_credible_interval, normal_posterior, poisson_posterior, bayes_factor, posterior_predictive_beta, hpd_interval_normal, bayesian_ab_test
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

    var _acc_beta_posterior: Float64 = 0.0
    var _t0_beta_posterior = perf_counter_ns()
    for _ in range(N):
        var _r_beta_posterior = beta_posterior(0.5, 0.5, 5, 5)
        _acc_beta_posterior += Float64(len(_r_beta_posterior))
    var _t1_beta_posterior = perf_counter_ns()
    var _ns_beta_posterior = Float64(_t1_beta_posterior - _t0_beta_posterior) / Float64(N)
    print("MOJO_TIMING bayesian::beta_posterior", _ns_beta_posterior, _acc_beta_posterior)
    var _acc_beta_mean: Float64 = 0.0
    var _t0_beta_mean = perf_counter_ns()
    for _ in range(N):
        _acc_beta_mean += beta_mean(0.5, 0.5)
    var _t1_beta_mean = perf_counter_ns()
    var _ns_beta_mean = Float64(_t1_beta_mean - _t0_beta_mean) / Float64(N)
    print("MOJO_TIMING bayesian::beta_mean", _ns_beta_mean, _acc_beta_mean)
    var _acc_beta_variance: Float64 = 0.0
    var _t0_beta_variance = perf_counter_ns()
    for _ in range(N):
        _acc_beta_variance += beta_variance(0.5, 0.5)
    var _t1_beta_variance = perf_counter_ns()
    var _ns_beta_variance = Float64(_t1_beta_variance - _t0_beta_variance) / Float64(N)
    print("MOJO_TIMING bayesian::beta_variance", _ns_beta_variance, _acc_beta_variance)
    var _acc_beta_credible_interval: Float64 = 0.0
    var _t0_beta_credible_interval = perf_counter_ns()
    for _ in range(N):
        var _r_beta_credible_interval = beta_credible_interval(0.5, 0.5, 0.5)
        _acc_beta_credible_interval += Float64(len(_r_beta_credible_interval))
    var _t1_beta_credible_interval = perf_counter_ns()
    var _ns_beta_credible_interval = Float64(_t1_beta_credible_interval - _t0_beta_credible_interval) / Float64(N)
    print("MOJO_TIMING bayesian::beta_credible_interval", _ns_beta_credible_interval, _acc_beta_credible_interval)
    var _acc_normal_posterior: Float64 = 0.0
    var _t0_normal_posterior = perf_counter_ns()
    for _ in range(N):
        var _r_normal_posterior = normal_posterior(0.5, 0.5, 0.5, 0.5, 5)
        _acc_normal_posterior += Float64(len(_r_normal_posterior))
    var _t1_normal_posterior = perf_counter_ns()
    var _ns_normal_posterior = Float64(_t1_normal_posterior - _t0_normal_posterior) / Float64(N)
    print("MOJO_TIMING bayesian::normal_posterior", _ns_normal_posterior, _acc_normal_posterior)
    var _acc_poisson_posterior: Float64 = 0.0
    var _t0_poisson_posterior = perf_counter_ns()
    for _ in range(N):
        var _r_poisson_posterior = poisson_posterior(0.5, 0.5, 5, 5)
        _acc_poisson_posterior += Float64(len(_r_poisson_posterior))
    var _t1_poisson_posterior = perf_counter_ns()
    var _ns_poisson_posterior = Float64(_t1_poisson_posterior - _t0_poisson_posterior) / Float64(N)
    print("MOJO_TIMING bayesian::poisson_posterior", _ns_poisson_posterior, _acc_poisson_posterior)
    var _acc_bayes_factor: Float64 = 0.0
    var _t0_bayes_factor = perf_counter_ns()
    for _ in range(N):
        _acc_bayes_factor += bayes_factor(0.5, 0.5)
    var _t1_bayes_factor = perf_counter_ns()
    var _ns_bayes_factor = Float64(_t1_bayes_factor - _t0_bayes_factor) / Float64(N)
    print("MOJO_TIMING bayesian::bayes_factor", _ns_bayes_factor, _acc_bayes_factor)
    var _acc_posterior_predictive_beta: Float64 = 0.0
    var _t0_posterior_predictive_beta = perf_counter_ns()
    for _ in range(N):
        _acc_posterior_predictive_beta += posterior_predictive_beta(0.5, 0.5)
    var _t1_posterior_predictive_beta = perf_counter_ns()
    var _ns_posterior_predictive_beta = Float64(_t1_posterior_predictive_beta - _t0_posterior_predictive_beta) / Float64(N)
    print("MOJO_TIMING bayesian::posterior_predictive_beta", _ns_posterior_predictive_beta, _acc_posterior_predictive_beta)
    var _acc_hpd_interval_normal: Float64 = 0.0
    var _t0_hpd_interval_normal = perf_counter_ns()
    for _ in range(N):
        var _r_hpd_interval_normal = hpd_interval_normal(0.5, 0.5, 0.5)
        _acc_hpd_interval_normal += Float64(len(_r_hpd_interval_normal))
    var _t1_hpd_interval_normal = perf_counter_ns()
    var _ns_hpd_interval_normal = Float64(_t1_hpd_interval_normal - _t0_hpd_interval_normal) / Float64(N)
    print("MOJO_TIMING bayesian::hpd_interval_normal", _ns_hpd_interval_normal, _acc_hpd_interval_normal)
    var _acc_bayesian_ab_test: Float64 = 0.0
    var _t0_bayesian_ab_test = perf_counter_ns()
    for _ in range(N):
        _acc_bayesian_ab_test += bayesian_ab_test(5, 5, 5, 5, 5)
    var _t1_bayesian_ab_test = perf_counter_ns()
    var _ns_bayesian_ab_test = Float64(_t1_bayesian_ab_test - _t0_bayesian_ab_test) / Float64(N)
    print("MOJO_TIMING bayesian::bayesian_ab_test", _ns_bayesian_ab_test, _acc_bayesian_ab_test)
