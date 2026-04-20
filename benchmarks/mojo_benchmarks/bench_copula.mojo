"""bench_copula.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from copula import norm_cdf_approx, norm_ppf_approx, gaussian_copula_sample, rank_correlation, kendall_tau
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

    var _acc_norm_cdf_approx: Float64 = 0.0
    var _t0_norm_cdf_approx = perf_counter_ns()
    for _ in range(N):
        _acc_norm_cdf_approx += norm_cdf_approx(0.5)
    var _t1_norm_cdf_approx = perf_counter_ns()
    var _ns_norm_cdf_approx = Float64(_t1_norm_cdf_approx - _t0_norm_cdf_approx) / Float64(N)
    print("MOJO_TIMING copula::norm_cdf_approx", _ns_norm_cdf_approx, _acc_norm_cdf_approx)
    var _acc_norm_ppf_approx: Float64 = 0.0
    var _t0_norm_ppf_approx = perf_counter_ns()
    for _ in range(N):
        _acc_norm_ppf_approx += norm_ppf_approx(0.5)
    var _t1_norm_ppf_approx = perf_counter_ns()
    var _ns_norm_ppf_approx = Float64(_t1_norm_ppf_approx - _t0_norm_ppf_approx) / Float64(N)
    print("MOJO_TIMING copula::norm_ppf_approx", _ns_norm_ppf_approx, _acc_norm_ppf_approx)
    var _acc_gaussian_copula_sample: Float64 = 0.0
    var _t0_gaussian_copula_sample = perf_counter_ns()
    for _ in range(N):
        var _r_gaussian_copula_sample = gaussian_copula_sample(5, 0.5)
        _acc_gaussian_copula_sample += Float64(len(_r_gaussian_copula_sample))
    var _t1_gaussian_copula_sample = perf_counter_ns()
    var _ns_gaussian_copula_sample = Float64(_t1_gaussian_copula_sample - _t0_gaussian_copula_sample) / Float64(N)
    print("MOJO_TIMING copula::gaussian_copula_sample", _ns_gaussian_copula_sample, _acc_gaussian_copula_sample)
    var _acc_rank_correlation: Float64 = 0.0
    var _t0_rank_correlation = perf_counter_ns()
    for _ in range(N):
        _acc_rank_correlation += rank_correlation(_lf5, _lf5)
    var _t1_rank_correlation = perf_counter_ns()
    var _ns_rank_correlation = Float64(_t1_rank_correlation - _t0_rank_correlation) / Float64(N)
    print("MOJO_TIMING copula::rank_correlation", _ns_rank_correlation, _acc_rank_correlation)
    var _acc_kendall_tau: Float64 = 0.0
    var _t0_kendall_tau = perf_counter_ns()
    for _ in range(N):
        _acc_kendall_tau += kendall_tau(_lf5, _lf5)
    var _t1_kendall_tau = perf_counter_ns()
    var _ns_kendall_tau = Float64(_t1_kendall_tau - _t0_kendall_tau) / Float64(N)
    print("MOJO_TIMING copula::kendall_tau", _ns_kendall_tau, _acc_kendall_tau)
