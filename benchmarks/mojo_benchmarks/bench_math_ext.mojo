"""bench_math_ext.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from math_ext import mean, median, mode_approx, stdev, variance, skewness, kurtosis, covariance, correlation, percentile, quantile, iqr, z_score, t_statistic, chi_squared, erf, norm_cdf, norm_pdf, norm_ppf, log_gamma, gamma_fn, beta_fn
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

    var _acc_mean: Float64 = 0.0
    var _t0_mean = perf_counter_ns()
    for _ in range(N):
        _acc_mean += mean(_lf5)
    var _t1_mean = perf_counter_ns()
    var _ns_mean = Float64(_t1_mean - _t0_mean) / Float64(N)
    print("MOJO_TIMING math_ext::mean", _ns_mean, _acc_mean)
    var _result_mean = mean(_lf5)
    var _summary_mean = _summary_float64(_result_mean)
    print("MOJO_RESULT math_ext::mean", _summary_mean)
    var _acc_median: Float64 = 0.0
    var _t0_median = perf_counter_ns()
    for _ in range(N):
        _acc_median += median(_lf5)
    var _t1_median = perf_counter_ns()
    var _ns_median = Float64(_t1_median - _t0_median) / Float64(N)
    print("MOJO_TIMING math_ext::median", _ns_median, _acc_median)
    var _result_median = median(_lf5)
    var _summary_median = _summary_float64(_result_median)
    print("MOJO_RESULT math_ext::median", _summary_median)
    var _acc_mode_approx: Float64 = 0.0
    var _t0_mode_approx = perf_counter_ns()
    for _ in range(N):
        _acc_mode_approx += mode_approx(_lf5, 5)
    var _t1_mode_approx = perf_counter_ns()
    var _ns_mode_approx = Float64(_t1_mode_approx - _t0_mode_approx) / Float64(N)
    print("MOJO_TIMING math_ext::mode_approx", _ns_mode_approx, _acc_mode_approx)
    var _result_mode_approx = mode_approx(_lf5, 5)
    var _summary_mode_approx = _summary_float64(_result_mode_approx)
    print("MOJO_RESULT math_ext::mode_approx", _summary_mode_approx)
    var _acc_stdev: Float64 = 0.0
    var _t0_stdev = perf_counter_ns()
    for _ in range(N):
        _acc_stdev += stdev(_lf5)
    var _t1_stdev = perf_counter_ns()
    var _ns_stdev = Float64(_t1_stdev - _t0_stdev) / Float64(N)
    print("MOJO_TIMING math_ext::stdev", _ns_stdev, _acc_stdev)
    var _result_stdev = stdev(_lf5)
    var _summary_stdev = _summary_float64(_result_stdev)
    print("MOJO_RESULT math_ext::stdev", _summary_stdev)
    var _acc_variance: Float64 = 0.0
    var _t0_variance = perf_counter_ns()
    for _ in range(N):
        _acc_variance += variance(_lf5)
    var _t1_variance = perf_counter_ns()
    var _ns_variance = Float64(_t1_variance - _t0_variance) / Float64(N)
    print("MOJO_TIMING math_ext::variance", _ns_variance, _acc_variance)
    var _result_variance = variance(_lf5)
    var _summary_variance = _summary_float64(_result_variance)
    print("MOJO_RESULT math_ext::variance", _summary_variance)
    var _acc_skewness: Float64 = 0.0
    var _t0_skewness = perf_counter_ns()
    for _ in range(N):
        _acc_skewness += skewness(_lf5)
    var _t1_skewness = perf_counter_ns()
    var _ns_skewness = Float64(_t1_skewness - _t0_skewness) / Float64(N)
    print("MOJO_TIMING math_ext::skewness", _ns_skewness, _acc_skewness)
    var _result_skewness = skewness(_lf5)
    var _summary_skewness = _summary_float64(_result_skewness)
    print("MOJO_RESULT math_ext::skewness", _summary_skewness)
    var _acc_kurtosis: Float64 = 0.0
    var _t0_kurtosis = perf_counter_ns()
    for _ in range(N):
        _acc_kurtosis += kurtosis(_lf5)
    var _t1_kurtosis = perf_counter_ns()
    var _ns_kurtosis = Float64(_t1_kurtosis - _t0_kurtosis) / Float64(N)
    print("MOJO_TIMING math_ext::kurtosis", _ns_kurtosis, _acc_kurtosis)
    var _result_kurtosis = kurtosis(_lf5)
    var _summary_kurtosis = _summary_float64(_result_kurtosis)
    print("MOJO_RESULT math_ext::kurtosis", _summary_kurtosis)
    var _acc_covariance: Float64 = 0.0
    var _t0_covariance = perf_counter_ns()
    for _ in range(N):
        _acc_covariance += covariance(_lf5, _lf5)
    var _t1_covariance = perf_counter_ns()
    var _ns_covariance = Float64(_t1_covariance - _t0_covariance) / Float64(N)
    print("MOJO_TIMING math_ext::covariance", _ns_covariance, _acc_covariance)
    var _result_covariance = covariance(_lf5, _lf5)
    var _summary_covariance = _summary_float64(_result_covariance)
    print("MOJO_RESULT math_ext::covariance", _summary_covariance)
    var _acc_correlation: Float64 = 0.0
    var _t0_correlation = perf_counter_ns()
    for _ in range(N):
        _acc_correlation += correlation(_lf5, _lf5)
    var _t1_correlation = perf_counter_ns()
    var _ns_correlation = Float64(_t1_correlation - _t0_correlation) / Float64(N)
    print("MOJO_TIMING math_ext::correlation", _ns_correlation, _acc_correlation)
    var _result_correlation = correlation(_lf5, _lf5)
    var _summary_correlation = _summary_float64(_result_correlation)
    print("MOJO_RESULT math_ext::correlation", _summary_correlation)
    var _acc_percentile: Float64 = 0.0
    var _t0_percentile = perf_counter_ns()
    for _ in range(N):
        _acc_percentile += percentile(_lf5, 0.5)
    var _t1_percentile = perf_counter_ns()
    var _ns_percentile = Float64(_t1_percentile - _t0_percentile) / Float64(N)
    print("MOJO_TIMING math_ext::percentile", _ns_percentile, _acc_percentile)
    var _result_percentile = percentile(_lf5, 0.5)
    var _summary_percentile = _summary_float64(_result_percentile)
    print("MOJO_RESULT math_ext::percentile", _summary_percentile)
    var _acc_quantile: Float64 = 0.0
    var _t0_quantile = perf_counter_ns()
    for _ in range(N):
        _acc_quantile += quantile(_lf5, 0.5)
    var _t1_quantile = perf_counter_ns()
    var _ns_quantile = Float64(_t1_quantile - _t0_quantile) / Float64(N)
    print("MOJO_TIMING math_ext::quantile", _ns_quantile, _acc_quantile)
    var _result_quantile = quantile(_lf5, 0.5)
    var _summary_quantile = _summary_float64(_result_quantile)
    print("MOJO_RESULT math_ext::quantile", _summary_quantile)
    var _acc_iqr: Float64 = 0.0
    var _t0_iqr = perf_counter_ns()
    for _ in range(N):
        _acc_iqr += iqr(_lf5)
    var _t1_iqr = perf_counter_ns()
    var _ns_iqr = Float64(_t1_iqr - _t0_iqr) / Float64(N)
    print("MOJO_TIMING math_ext::iqr", _ns_iqr, _acc_iqr)
    var _result_iqr = iqr(_lf5)
    var _summary_iqr = _summary_float64(_result_iqr)
    print("MOJO_RESULT math_ext::iqr", _summary_iqr)
    var _acc_z_score: Float64 = 0.0
    var _t0_z_score = perf_counter_ns()
    for _ in range(N):
        _acc_z_score += z_score(0.5, 0.5, 0.5)
    var _t1_z_score = perf_counter_ns()
    var _ns_z_score = Float64(_t1_z_score - _t0_z_score) / Float64(N)
    print("MOJO_TIMING math_ext::z_score", _ns_z_score, _acc_z_score)
    var _result_z_score = z_score(0.5, 0.5, 0.5)
    var _summary_z_score = _summary_float64(_result_z_score)
    print("MOJO_RESULT math_ext::z_score", _summary_z_score)
    var _acc_t_statistic: Float64 = 0.0
    var _t0_t_statistic = perf_counter_ns()
    for _ in range(N):
        _acc_t_statistic += t_statistic(0.5, 0.5, 0.5, 5)
    var _t1_t_statistic = perf_counter_ns()
    var _ns_t_statistic = Float64(_t1_t_statistic - _t0_t_statistic) / Float64(N)
    print("MOJO_TIMING math_ext::t_statistic", _ns_t_statistic, _acc_t_statistic)
    var _result_t_statistic = t_statistic(0.5, 0.5, 0.5, 5)
    var _summary_t_statistic = _summary_float64(_result_t_statistic)
    print("MOJO_RESULT math_ext::t_statistic", _summary_t_statistic)
    var _acc_chi_squared: Float64 = 0.0
    var _t0_chi_squared = perf_counter_ns()
    for _ in range(N):
        _acc_chi_squared += chi_squared(_lf5, _lf5)
    var _t1_chi_squared = perf_counter_ns()
    var _ns_chi_squared = Float64(_t1_chi_squared - _t0_chi_squared) / Float64(N)
    print("MOJO_TIMING math_ext::chi_squared", _ns_chi_squared, _acc_chi_squared)
    var _result_chi_squared = chi_squared(_lf5, _lf5)
    var _summary_chi_squared = _summary_float64(_result_chi_squared)
    print("MOJO_RESULT math_ext::chi_squared", _summary_chi_squared)
    var _acc_erf: Float64 = 0.0
    var _t0_erf = perf_counter_ns()
    for _ in range(N):
        _acc_erf += erf(0.5)
    var _t1_erf = perf_counter_ns()
    var _ns_erf = Float64(_t1_erf - _t0_erf) / Float64(N)
    print("MOJO_TIMING math_ext::erf", _ns_erf, _acc_erf)
    var _result_erf = erf(0.5)
    var _summary_erf = _summary_float64(_result_erf)
    print("MOJO_RESULT math_ext::erf", _summary_erf)
    var _acc_norm_cdf: Float64 = 0.0
    var _t0_norm_cdf = perf_counter_ns()
    for _ in range(N):
        _acc_norm_cdf += norm_cdf(0.5)
    var _t1_norm_cdf = perf_counter_ns()
    var _ns_norm_cdf = Float64(_t1_norm_cdf - _t0_norm_cdf) / Float64(N)
    print("MOJO_TIMING math_ext::norm_cdf", _ns_norm_cdf, _acc_norm_cdf)
    var _result_norm_cdf = norm_cdf(0.5)
    var _summary_norm_cdf = _summary_float64(_result_norm_cdf)
    print("MOJO_RESULT math_ext::norm_cdf", _summary_norm_cdf)
    var _acc_norm_pdf: Float64 = 0.0
    var _t0_norm_pdf = perf_counter_ns()
    for _ in range(N):
        _acc_norm_pdf += norm_pdf(0.5)
    var _t1_norm_pdf = perf_counter_ns()
    var _ns_norm_pdf = Float64(_t1_norm_pdf - _t0_norm_pdf) / Float64(N)
    print("MOJO_TIMING math_ext::norm_pdf", _ns_norm_pdf, _acc_norm_pdf)
    var _result_norm_pdf = norm_pdf(0.5)
    var _summary_norm_pdf = _summary_float64(_result_norm_pdf)
    print("MOJO_RESULT math_ext::norm_pdf", _summary_norm_pdf)
    var _acc_norm_ppf: Float64 = 0.0
    var _t0_norm_ppf = perf_counter_ns()
    for _ in range(N):
        _acc_norm_ppf += norm_ppf(0.5)
    var _t1_norm_ppf = perf_counter_ns()
    var _ns_norm_ppf = Float64(_t1_norm_ppf - _t0_norm_ppf) / Float64(N)
    print("MOJO_TIMING math_ext::norm_ppf", _ns_norm_ppf, _acc_norm_ppf)
    var _result_norm_ppf = norm_ppf(0.5)
    var _summary_norm_ppf = _summary_float64(_result_norm_ppf)
    print("MOJO_RESULT math_ext::norm_ppf", _summary_norm_ppf)
    var _acc_log_gamma: Float64 = 0.0
    var _t0_log_gamma = perf_counter_ns()
    for _ in range(N):
        _acc_log_gamma += log_gamma(0.5)
    var _t1_log_gamma = perf_counter_ns()
    var _ns_log_gamma = Float64(_t1_log_gamma - _t0_log_gamma) / Float64(N)
    print("MOJO_TIMING math_ext::log_gamma", _ns_log_gamma, _acc_log_gamma)
    var _result_log_gamma = log_gamma(0.5)
    var _summary_log_gamma = _summary_float64(_result_log_gamma)
    print("MOJO_RESULT math_ext::log_gamma", _summary_log_gamma)
    var _acc_gamma_fn: Float64 = 0.0
    var _t0_gamma_fn = perf_counter_ns()
    for _ in range(N):
        _acc_gamma_fn += gamma_fn(0.5)
    var _t1_gamma_fn = perf_counter_ns()
    var _ns_gamma_fn = Float64(_t1_gamma_fn - _t0_gamma_fn) / Float64(N)
    print("MOJO_TIMING math_ext::gamma_fn", _ns_gamma_fn, _acc_gamma_fn)
    var _result_gamma_fn = gamma_fn(0.5)
    var _summary_gamma_fn = _summary_float64(_result_gamma_fn)
    print("MOJO_RESULT math_ext::gamma_fn", _summary_gamma_fn)
    var _acc_beta_fn: Float64 = 0.0
    var _t0_beta_fn = perf_counter_ns()
    for _ in range(N):
        _acc_beta_fn += beta_fn(0.5, 0.5)
    var _t1_beta_fn = perf_counter_ns()
    var _ns_beta_fn = Float64(_t1_beta_fn - _t0_beta_fn) / Float64(N)
    print("MOJO_TIMING math_ext::beta_fn", _ns_beta_fn, _acc_beta_fn)
    var _result_beta_fn = beta_fn(0.5, 0.5)
    var _summary_beta_fn = _summary_float64(_result_beta_fn)
    print("MOJO_RESULT math_ext::beta_fn", _summary_beta_fn)
