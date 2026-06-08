"""bench_distribution_fit.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from distribution_fit import fit_normal, fit_exponential, fit_uniform, fit_weibull, log_likelihood_normal, log_likelihood_exponential, aic, bic, best_fit, qq_residuals
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

    var _acc_fit_normal: Float64 = 0.0
    var _t0_fit_normal = perf_counter_ns()
    for _ in range(N):
        var _r_fit_normal = fit_normal(_lf5)
        _acc_fit_normal += Float64(len(_r_fit_normal))
    var _t1_fit_normal = perf_counter_ns()
    var _ns_fit_normal = Float64(_t1_fit_normal - _t0_fit_normal) / Float64(N)
    print("MOJO_TIMING distribution_fit::fit_normal", _ns_fit_normal, _acc_fit_normal)
    var _result_fit_normal = fit_normal(_lf5)
    var _summary_fit_normal = _summary_list_float64(_result_fit_normal)
    print("MOJO_RESULT distribution_fit::fit_normal", _summary_fit_normal)
    var _acc_fit_exponential: Float64 = 0.0
    var _t0_fit_exponential = perf_counter_ns()
    for _ in range(N):
        _acc_fit_exponential += fit_exponential(_lf5)
    var _t1_fit_exponential = perf_counter_ns()
    var _ns_fit_exponential = Float64(_t1_fit_exponential - _t0_fit_exponential) / Float64(N)
    print("MOJO_TIMING distribution_fit::fit_exponential", _ns_fit_exponential, _acc_fit_exponential)
    var _result_fit_exponential = fit_exponential(_lf5)
    var _summary_fit_exponential = _summary_float64(_result_fit_exponential)
    print("MOJO_RESULT distribution_fit::fit_exponential", _summary_fit_exponential)
    var _acc_fit_uniform: Float64 = 0.0
    var _t0_fit_uniform = perf_counter_ns()
    for _ in range(N):
        var _r_fit_uniform = fit_uniform(_lf5)
        _acc_fit_uniform += Float64(len(_r_fit_uniform))
    var _t1_fit_uniform = perf_counter_ns()
    var _ns_fit_uniform = Float64(_t1_fit_uniform - _t0_fit_uniform) / Float64(N)
    print("MOJO_TIMING distribution_fit::fit_uniform", _ns_fit_uniform, _acc_fit_uniform)
    var _result_fit_uniform = fit_uniform(_lf5)
    var _summary_fit_uniform = _summary_list_float64(_result_fit_uniform)
    print("MOJO_RESULT distribution_fit::fit_uniform", _summary_fit_uniform)
    var _acc_fit_weibull: Float64 = 0.0
    var _t0_fit_weibull = perf_counter_ns()
    for _ in range(N):
        var _r_fit_weibull = fit_weibull(_lf5)
        _acc_fit_weibull += Float64(len(_r_fit_weibull))
    var _t1_fit_weibull = perf_counter_ns()
    var _ns_fit_weibull = Float64(_t1_fit_weibull - _t0_fit_weibull) / Float64(N)
    print("MOJO_TIMING distribution_fit::fit_weibull", _ns_fit_weibull, _acc_fit_weibull)
    var _result_fit_weibull = fit_weibull(_lf5)
    var _summary_fit_weibull = _summary_list_float64(_result_fit_weibull)
    print("MOJO_RESULT distribution_fit::fit_weibull", _summary_fit_weibull)
    var _acc_log_likelihood_normal: Float64 = 0.0
    var _t0_log_likelihood_normal = perf_counter_ns()
    for _ in range(N):
        _acc_log_likelihood_normal += log_likelihood_normal(_lf5, 0.5, 0.5)
    var _t1_log_likelihood_normal = perf_counter_ns()
    var _ns_log_likelihood_normal = Float64(_t1_log_likelihood_normal - _t0_log_likelihood_normal) / Float64(N)
    print("MOJO_TIMING distribution_fit::log_likelihood_normal", _ns_log_likelihood_normal, _acc_log_likelihood_normal)
    var _result_log_likelihood_normal = log_likelihood_normal(_lf5, 0.5, 0.5)
    var _summary_log_likelihood_normal = _summary_float64(_result_log_likelihood_normal)
    print("MOJO_RESULT distribution_fit::log_likelihood_normal", _summary_log_likelihood_normal)
    var _acc_log_likelihood_exponential: Float64 = 0.0
    var _t0_log_likelihood_exponential = perf_counter_ns()
    for _ in range(N):
        _acc_log_likelihood_exponential += log_likelihood_exponential(_lf5, 0.5)
    var _t1_log_likelihood_exponential = perf_counter_ns()
    var _ns_log_likelihood_exponential = Float64(_t1_log_likelihood_exponential - _t0_log_likelihood_exponential) / Float64(N)
    print("MOJO_TIMING distribution_fit::log_likelihood_exponential", _ns_log_likelihood_exponential, _acc_log_likelihood_exponential)
    var _result_log_likelihood_exponential = log_likelihood_exponential(_lf5, 0.5)
    var _summary_log_likelihood_exponential = _summary_float64(_result_log_likelihood_exponential)
    print("MOJO_RESULT distribution_fit::log_likelihood_exponential", _summary_log_likelihood_exponential)
    var _acc_aic: Float64 = 0.0
    var _t0_aic = perf_counter_ns()
    for _ in range(N):
        _acc_aic += aic(0.5, 5)
    var _t1_aic = perf_counter_ns()
    var _ns_aic = Float64(_t1_aic - _t0_aic) / Float64(N)
    print("MOJO_TIMING distribution_fit::aic", _ns_aic, _acc_aic)
    var _result_aic = aic(0.5, 5)
    var _summary_aic = _summary_float64(_result_aic)
    print("MOJO_RESULT distribution_fit::aic", _summary_aic)
    var _acc_bic: Float64 = 0.0
    var _t0_bic = perf_counter_ns()
    for _ in range(N):
        _acc_bic += bic(0.5, 5, 5)
    var _t1_bic = perf_counter_ns()
    var _ns_bic = Float64(_t1_bic - _t0_bic) / Float64(N)
    print("MOJO_TIMING distribution_fit::bic", _ns_bic, _acc_bic)
    var _result_bic = bic(0.5, 5, 5)
    var _summary_bic = _summary_float64(_result_bic)
    print("MOJO_RESULT distribution_fit::bic", _summary_bic)
    var _acc_best_fit: Float64 = 0.0
    var _t0_best_fit = perf_counter_ns()
    for _ in range(N):
        _acc_best_fit += Float64(best_fit(_lf5))
    var _t1_best_fit = perf_counter_ns()
    var _ns_best_fit = Float64(_t1_best_fit - _t0_best_fit) / Float64(N)
    print("MOJO_TIMING distribution_fit::best_fit", _ns_best_fit, _acc_best_fit)
    var _result_best_fit = best_fit(_lf5)
    var _summary_best_fit = _summary_int(_result_best_fit)
    print("MOJO_RESULT distribution_fit::best_fit", _summary_best_fit)
    var _acc_qq_residuals: Float64 = 0.0
    var _t0_qq_residuals = perf_counter_ns()
    for _ in range(N):
        var _r_qq_residuals = qq_residuals(_lf5, 0.5, 0.5)
        _acc_qq_residuals += Float64(len(_r_qq_residuals))
    var _t1_qq_residuals = perf_counter_ns()
    var _ns_qq_residuals = Float64(_t1_qq_residuals - _t0_qq_residuals) / Float64(N)
    print("MOJO_TIMING distribution_fit::qq_residuals", _ns_qq_residuals, _acc_qq_residuals)
    var _result_qq_residuals = qq_residuals(_lf5, 0.5, 0.5)
    var _summary_qq_residuals = _summary_list_float64(_result_qq_residuals)
    print("MOJO_RESULT distribution_fit::qq_residuals", _summary_qq_residuals)
