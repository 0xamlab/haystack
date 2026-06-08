"""bench_scipy_stats_ops.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from scipy_stats_ops import normal_pdf, normal_cdf_approx, t_distribution_pdf, chi2_pdf, exponential_pdf, poisson_pmf, beta_pdf_unnorm, gamma_pdf_unnorm, logistic_pdf, weibull_pdf
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
    var _result_normal_pdf = normal_pdf(0.5, 0.5, 0.5)
    var _summary_normal_pdf = _summary_float64(_result_normal_pdf)
    print("MOJO_RESULT scipy_stats_ops::normal_pdf", _summary_normal_pdf)
    var _acc_normal_cdf_approx: Float64 = 0.0
    var _t0_normal_cdf_approx = perf_counter_ns()
    for _ in range(N):
        _acc_normal_cdf_approx += normal_cdf_approx(0.5, 0.5, 0.5)
    var _t1_normal_cdf_approx = perf_counter_ns()
    var _ns_normal_cdf_approx = Float64(_t1_normal_cdf_approx - _t0_normal_cdf_approx) / Float64(N)
    print("MOJO_TIMING scipy_stats_ops::normal_cdf_approx", _ns_normal_cdf_approx, _acc_normal_cdf_approx)
    var _result_normal_cdf_approx = normal_cdf_approx(0.5, 0.5, 0.5)
    var _summary_normal_cdf_approx = _summary_float64(_result_normal_cdf_approx)
    print("MOJO_RESULT scipy_stats_ops::normal_cdf_approx", _summary_normal_cdf_approx)
    var _acc_t_distribution_pdf: Float64 = 0.0
    var _t0_t_distribution_pdf = perf_counter_ns()
    for _ in range(N):
        _acc_t_distribution_pdf += t_distribution_pdf(0.5, 0.5)
    var _t1_t_distribution_pdf = perf_counter_ns()
    var _ns_t_distribution_pdf = Float64(_t1_t_distribution_pdf - _t0_t_distribution_pdf) / Float64(N)
    print("MOJO_TIMING scipy_stats_ops::t_distribution_pdf", _ns_t_distribution_pdf, _acc_t_distribution_pdf)
    var _result_t_distribution_pdf = t_distribution_pdf(0.5, 0.5)
    var _summary_t_distribution_pdf = _summary_float64(_result_t_distribution_pdf)
    print("MOJO_RESULT scipy_stats_ops::t_distribution_pdf", _summary_t_distribution_pdf)
    var _acc_chi2_pdf: Float64 = 0.0
    var _t0_chi2_pdf = perf_counter_ns()
    for _ in range(N):
        _acc_chi2_pdf += chi2_pdf(0.5, 0.5)
    var _t1_chi2_pdf = perf_counter_ns()
    var _ns_chi2_pdf = Float64(_t1_chi2_pdf - _t0_chi2_pdf) / Float64(N)
    print("MOJO_TIMING scipy_stats_ops::chi2_pdf", _ns_chi2_pdf, _acc_chi2_pdf)
    var _result_chi2_pdf = chi2_pdf(0.5, 0.5)
    var _summary_chi2_pdf = _summary_float64(_result_chi2_pdf)
    print("MOJO_RESULT scipy_stats_ops::chi2_pdf", _summary_chi2_pdf)
    var _acc_exponential_pdf: Float64 = 0.0
    var _t0_exponential_pdf = perf_counter_ns()
    for _ in range(N):
        _acc_exponential_pdf += exponential_pdf(0.5, 0.5)
    var _t1_exponential_pdf = perf_counter_ns()
    var _ns_exponential_pdf = Float64(_t1_exponential_pdf - _t0_exponential_pdf) / Float64(N)
    print("MOJO_TIMING scipy_stats_ops::exponential_pdf", _ns_exponential_pdf, _acc_exponential_pdf)
    var _result_exponential_pdf = exponential_pdf(0.5, 0.5)
    var _summary_exponential_pdf = _summary_float64(_result_exponential_pdf)
    print("MOJO_RESULT scipy_stats_ops::exponential_pdf", _summary_exponential_pdf)
    var _acc_poisson_pmf: Float64 = 0.0
    var _t0_poisson_pmf = perf_counter_ns()
    for _ in range(N):
        _acc_poisson_pmf += poisson_pmf(0.5, 0.5)
    var _t1_poisson_pmf = perf_counter_ns()
    var _ns_poisson_pmf = Float64(_t1_poisson_pmf - _t0_poisson_pmf) / Float64(N)
    print("MOJO_TIMING scipy_stats_ops::poisson_pmf", _ns_poisson_pmf, _acc_poisson_pmf)
    var _result_poisson_pmf = poisson_pmf(0.5, 0.5)
    var _summary_poisson_pmf = _summary_float64(_result_poisson_pmf)
    print("MOJO_RESULT scipy_stats_ops::poisson_pmf", _summary_poisson_pmf)
    var _acc_beta_pdf_unnorm: Float64 = 0.0
    var _t0_beta_pdf_unnorm = perf_counter_ns()
    for _ in range(N):
        _acc_beta_pdf_unnorm += beta_pdf_unnorm(0.5, 0.5, 0.5)
    var _t1_beta_pdf_unnorm = perf_counter_ns()
    var _ns_beta_pdf_unnorm = Float64(_t1_beta_pdf_unnorm - _t0_beta_pdf_unnorm) / Float64(N)
    print("MOJO_TIMING scipy_stats_ops::beta_pdf_unnorm", _ns_beta_pdf_unnorm, _acc_beta_pdf_unnorm)
    var _result_beta_pdf_unnorm = beta_pdf_unnorm(0.5, 0.5, 0.5)
    var _summary_beta_pdf_unnorm = _summary_float64(_result_beta_pdf_unnorm)
    print("MOJO_RESULT scipy_stats_ops::beta_pdf_unnorm", _summary_beta_pdf_unnorm)
    var _acc_gamma_pdf_unnorm: Float64 = 0.0
    var _t0_gamma_pdf_unnorm = perf_counter_ns()
    for _ in range(N):
        _acc_gamma_pdf_unnorm += gamma_pdf_unnorm(0.5, 0.5, 0.5)
    var _t1_gamma_pdf_unnorm = perf_counter_ns()
    var _ns_gamma_pdf_unnorm = Float64(_t1_gamma_pdf_unnorm - _t0_gamma_pdf_unnorm) / Float64(N)
    print("MOJO_TIMING scipy_stats_ops::gamma_pdf_unnorm", _ns_gamma_pdf_unnorm, _acc_gamma_pdf_unnorm)
    var _result_gamma_pdf_unnorm = gamma_pdf_unnorm(0.5, 0.5, 0.5)
    var _summary_gamma_pdf_unnorm = _summary_float64(_result_gamma_pdf_unnorm)
    print("MOJO_RESULT scipy_stats_ops::gamma_pdf_unnorm", _summary_gamma_pdf_unnorm)
    var _acc_logistic_pdf: Float64 = 0.0
    var _t0_logistic_pdf = perf_counter_ns()
    for _ in range(N):
        _acc_logistic_pdf += logistic_pdf(0.5, 0.5, 0.5)
    var _t1_logistic_pdf = perf_counter_ns()
    var _ns_logistic_pdf = Float64(_t1_logistic_pdf - _t0_logistic_pdf) / Float64(N)
    print("MOJO_TIMING scipy_stats_ops::logistic_pdf", _ns_logistic_pdf, _acc_logistic_pdf)
    var _result_logistic_pdf = logistic_pdf(0.5, 0.5, 0.5)
    var _summary_logistic_pdf = _summary_float64(_result_logistic_pdf)
    print("MOJO_RESULT scipy_stats_ops::logistic_pdf", _summary_logistic_pdf)
    var _acc_weibull_pdf: Float64 = 0.0
    var _t0_weibull_pdf = perf_counter_ns()
    for _ in range(N):
        _acc_weibull_pdf += weibull_pdf(0.5, 0.5, 0.5)
    var _t1_weibull_pdf = perf_counter_ns()
    var _ns_weibull_pdf = Float64(_t1_weibull_pdf - _t0_weibull_pdf) / Float64(N)
    print("MOJO_TIMING scipy_stats_ops::weibull_pdf", _ns_weibull_pdf, _acc_weibull_pdf)
    var _result_weibull_pdf = weibull_pdf(0.5, 0.5, 0.5)
    var _summary_weibull_pdf = _summary_float64(_result_weibull_pdf)
    print("MOJO_RESULT scipy_stats_ops::weibull_pdf", _summary_weibull_pdf)
