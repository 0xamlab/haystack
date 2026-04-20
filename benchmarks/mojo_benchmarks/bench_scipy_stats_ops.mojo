"""bench_scipy_stats_ops.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from scipy_stats_ops import normal_pdf, normal_cdf_approx, t_distribution_pdf, chi2_pdf, exponential_pdf, poisson_pmf, beta_pdf_unnorm, gamma_pdf_unnorm, logistic_pdf, weibull_pdf
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

    var _acc_normal_pdf: Float64 = 0.0
    var _t0_normal_pdf = perf_counter_ns()
    for _ in range(N):
        _acc_normal_pdf += normal_pdf(0.5, 0.5, 0.5)
    var _t1_normal_pdf = perf_counter_ns()
    var _ns_normal_pdf = Float64(_t1_normal_pdf - _t0_normal_pdf) / Float64(N)
    print("MOJO_TIMING scipy_stats_ops::normal_pdf", _ns_normal_pdf, _acc_normal_pdf)
    var _acc_normal_cdf_approx: Float64 = 0.0
    var _t0_normal_cdf_approx = perf_counter_ns()
    for _ in range(N):
        _acc_normal_cdf_approx += normal_cdf_approx(0.5, 0.5, 0.5)
    var _t1_normal_cdf_approx = perf_counter_ns()
    var _ns_normal_cdf_approx = Float64(_t1_normal_cdf_approx - _t0_normal_cdf_approx) / Float64(N)
    print("MOJO_TIMING scipy_stats_ops::normal_cdf_approx", _ns_normal_cdf_approx, _acc_normal_cdf_approx)
    var _acc_t_distribution_pdf: Float64 = 0.0
    var _t0_t_distribution_pdf = perf_counter_ns()
    for _ in range(N):
        _acc_t_distribution_pdf += t_distribution_pdf(0.5, 0.5)
    var _t1_t_distribution_pdf = perf_counter_ns()
    var _ns_t_distribution_pdf = Float64(_t1_t_distribution_pdf - _t0_t_distribution_pdf) / Float64(N)
    print("MOJO_TIMING scipy_stats_ops::t_distribution_pdf", _ns_t_distribution_pdf, _acc_t_distribution_pdf)
    var _acc_chi2_pdf: Float64 = 0.0
    var _t0_chi2_pdf = perf_counter_ns()
    for _ in range(N):
        _acc_chi2_pdf += chi2_pdf(0.5, 0.5)
    var _t1_chi2_pdf = perf_counter_ns()
    var _ns_chi2_pdf = Float64(_t1_chi2_pdf - _t0_chi2_pdf) / Float64(N)
    print("MOJO_TIMING scipy_stats_ops::chi2_pdf", _ns_chi2_pdf, _acc_chi2_pdf)
    var _acc_exponential_pdf: Float64 = 0.0
    var _t0_exponential_pdf = perf_counter_ns()
    for _ in range(N):
        _acc_exponential_pdf += exponential_pdf(0.5, 0.5)
    var _t1_exponential_pdf = perf_counter_ns()
    var _ns_exponential_pdf = Float64(_t1_exponential_pdf - _t0_exponential_pdf) / Float64(N)
    print("MOJO_TIMING scipy_stats_ops::exponential_pdf", _ns_exponential_pdf, _acc_exponential_pdf)
    var _acc_poisson_pmf: Float64 = 0.0
    var _t0_poisson_pmf = perf_counter_ns()
    for _ in range(N):
        _acc_poisson_pmf += poisson_pmf(0.5, 0.5)
    var _t1_poisson_pmf = perf_counter_ns()
    var _ns_poisson_pmf = Float64(_t1_poisson_pmf - _t0_poisson_pmf) / Float64(N)
    print("MOJO_TIMING scipy_stats_ops::poisson_pmf", _ns_poisson_pmf, _acc_poisson_pmf)
    var _acc_beta_pdf_unnorm: Float64 = 0.0
    var _t0_beta_pdf_unnorm = perf_counter_ns()
    for _ in range(N):
        _acc_beta_pdf_unnorm += beta_pdf_unnorm(0.5, 0.5, 0.5)
    var _t1_beta_pdf_unnorm = perf_counter_ns()
    var _ns_beta_pdf_unnorm = Float64(_t1_beta_pdf_unnorm - _t0_beta_pdf_unnorm) / Float64(N)
    print("MOJO_TIMING scipy_stats_ops::beta_pdf_unnorm", _ns_beta_pdf_unnorm, _acc_beta_pdf_unnorm)
    var _acc_gamma_pdf_unnorm: Float64 = 0.0
    var _t0_gamma_pdf_unnorm = perf_counter_ns()
    for _ in range(N):
        _acc_gamma_pdf_unnorm += gamma_pdf_unnorm(0.5, 0.5, 0.5)
    var _t1_gamma_pdf_unnorm = perf_counter_ns()
    var _ns_gamma_pdf_unnorm = Float64(_t1_gamma_pdf_unnorm - _t0_gamma_pdf_unnorm) / Float64(N)
    print("MOJO_TIMING scipy_stats_ops::gamma_pdf_unnorm", _ns_gamma_pdf_unnorm, _acc_gamma_pdf_unnorm)
    var _acc_logistic_pdf: Float64 = 0.0
    var _t0_logistic_pdf = perf_counter_ns()
    for _ in range(N):
        _acc_logistic_pdf += logistic_pdf(0.5, 0.5, 0.5)
    var _t1_logistic_pdf = perf_counter_ns()
    var _ns_logistic_pdf = Float64(_t1_logistic_pdf - _t0_logistic_pdf) / Float64(N)
    print("MOJO_TIMING scipy_stats_ops::logistic_pdf", _ns_logistic_pdf, _acc_logistic_pdf)
    var _acc_weibull_pdf: Float64 = 0.0
    var _t0_weibull_pdf = perf_counter_ns()
    for _ in range(N):
        _acc_weibull_pdf += weibull_pdf(0.5, 0.5, 0.5)
    var _t1_weibull_pdf = perf_counter_ns()
    var _ns_weibull_pdf = Float64(_t1_weibull_pdf - _t0_weibull_pdf) / Float64(N)
    print("MOJO_TIMING scipy_stats_ops::weibull_pdf", _ns_weibull_pdf, _acc_weibull_pdf)
